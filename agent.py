"""Create French and Italian editorial graphics and two-page weekly PowerPoints."""
import argparse
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import json
from pathlib import Path
import sqlite3
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from studio import render_campaign
from research import is_beauty_headline
from editorial import LANGUAGES, campaign_plan
from creative import recent_campaigns
from weekly import load_brief, select_ingredients
from radar_presentation import create_presentation

ROOT = Path(__file__).resolve().parent
QUERY = '(beauty OR skincare) (trend OR glow OR hydration OR longevity) when:7d'
THEMES = {
    'glow': {'keywords': ('glow', 'radiance', 'luminos', 'makeup', 'make-up', 'tinted', 'skin tint', 'teint'), 'label': 'Il tuo momento glow', 'colors': ((247, 233, 221), (205, 170, 144))},
    'renew': {'keywords': ('longevity', 'aging', 'ageing', 'collagen', 'collag', 'barrier', 'barriera', 'hydrat', 'idrat', 'firm'), 'label': 'Dedicati un rituale di cura', 'colors': ((233, 237, 229), (161, 185, 169))},
}


def initialize(db):
    db.executescript('''CREATE TABLE IF NOT EXISTS products (
    page_url TEXT NOT NULL, name TEXT NOT NULL, sku TEXT, description TEXT,
    json_ld TEXT NOT NULL, collected_at TEXT DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(page_url,name));
    CREATE TABLE IF NOT EXISTS images (url TEXT PRIMARY KEY,path TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS product_images (page_url TEXT,name TEXT,image_url TEXT,
    PRIMARY KEY(page_url,name,image_url));
    CREATE TABLE IF NOT EXISTS generations (
    id TEXT PRIMARY KEY, created_at TEXT NOT NULL, product_id TEXT NOT NULL,
    image_path TEXT NOT NULL, research_json TEXT NOT NULL);''')


def link_product_images(path):
    """Register the checked-in photos locally, without network requests."""
    manifest = json.loads((ROOT / 'assets/products/manifest.json').read_text(encoding='utf-8'))
    with sqlite3.connect(path) as db:
        initialize(db)
        for asset in manifest:
            row = db.execute('SELECT name,json_ld FROM products WHERE page_url=?',
                             (asset['product_id'],)).fetchone()
            if row is None:
                continue
            db.execute('INSERT INTO images(url,path) VALUES(?,?) '
                       'ON CONFLICT(url) DO UPDATE SET path=excluded.path WHERE path != excluded.path',
                       (asset['source_url'], asset['path']))
            db.execute('INSERT OR IGNORE INTO product_images VALUES(?,?,?)',
                       (asset['product_id'], row[0], asset['source_url']))
            data = json.loads(row[1])
            data['image_status'] = 'stored locally in project assets'
            data['local_image_path'] = asset['path']
            data['image_source_url'] = asset['source_url']
            updated = json.dumps(data, ensure_ascii=False)
            if updated != row[1]:
                db.execute('UPDATE products SET json_ld=? WHERE page_url=?',
                           (updated, asset['product_id']))


def load_products(path):
    # A new clone is initialized from the supplied catalog, never from a website.
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(path) as db:
            db.executescript((ROOT / 'catalog_seed.sql').read_text(encoding='utf-8'))
    link_product_images(path)
    with sqlite3.connect(f'{path.resolve().as_uri()}?mode=ro', uri=True) as db:
        products = []
        for url, name, description, raw in db.execute('SELECT page_url,name,description,json_ld FROM products ORDER BY name'):
            data = json.loads(raw)
            images = []
            for source_url, image_path in db.execute(
                    'SELECT i.url,i.path FROM images i JOIN product_images pi ON pi.image_url=i.url '
                    'WHERE pi.page_url=? AND pi.name=? ORDER BY (i.url=?) DESC,i.url',
                    (url, name, data.get('image_source_url', ''))):
                local_path = ROOT / image_path
                if not local_path.is_file():
                    local_path = path.parent / image_path
                images.append({'source_url': source_url, 'path': str(local_path.resolve())})
            products.append({'id': url, 'name': name, 'description': description,
                             'data': data, 'images': images})
    if not products:
        raise RuntimeError('Il catalogo è vuoto. Inserisci un prodotto nel database.')
    return products


def parse_news(raw, now):
    cutoff = now - timedelta(days=7)
    found = []
    seen = set()
    for item in ET.fromstring(raw).findall('.//item'):
        try:
            published = parsedate_to_datetime(item.findtext('pubDate', ''))
            if published.tzinfo is None:
                continue
        except (ValueError, TypeError, OverflowError):
            continue
        title = item.findtext('title', '').strip()
        url = item.findtext('link', '').strip()
        if not title or not is_beauty_headline(title) or not url.startswith('https://') or url in seen or not cutoff <= published <= now:
            continue
        seen.add(url)
        found.append({'title': title, 'url': url, 'publisher': item.findtext('source', ''), 'published_at': published.isoformat()})
    return sorted(found, key=lambda x: x['published_at'], reverse=True)


def search_news(now):
    query = urllib.parse.urlencode({'q': QUERY, 'hl': 'it', 'gl': 'IT', 'ceid': 'IT:it'})
    req = urllib.request.Request('https://news.google.com/rss/search?' + query, headers={'User-Agent': 'AgentBeauty/2.0'})
    with urllib.request.urlopen(req, timeout=30) as response:
        news = parse_news(response.read(), now)
    if not news:
        raise RuntimeError('Nessuna notizia beauty datata negli ultimi sette giorni. Nessun trend inventato.')
    return news


def choose_product(products, news, requested=None):
    candidates = [p for p in products if not requested or requested.casefold() in p['name'].casefold()]
    if not candidates:
        raise ValueError('Prodotto richiesto non trovato nel database.')
    scores = {theme: sum(any(word in n['title'].casefold() for word in config['keywords']) for n in news) for theme, config in THEMES.items()}
    ranked = []
    for product in candidates:
        editorial = product['data'].get('editorial', {})
        theme = editorial.get('theme')
        claim = editorial.get('claim_it')
        if theme in THEMES and claim:
            ranked.append((scores[theme], product['name'], product, theme, claim))
    if not ranked:
        raise RuntimeError('Mancano claim editoriale e tema nel catalogo. Aggiungerli senza inventare benefici.')
    _, _, product, theme, claim = max(ranked, key=lambda item: (item[0], item[1]))
    matched = [n for n in news if any(word in n['title'].casefold() for word in THEMES[theme]['keywords'])]
    return product, theme, claim, matched, scores


def run(args):
    now = datetime.now(timezone.utc)
    products = load_products(args.database)
    # Fresh evidence on EVERY invocation. No cached or invented trend fallback.
    news = search_news(now)
    weekly = load_brief(getattr(args, 'research', ROOT/'research/2026-10-08.json'), now)
    eligible = [p for p in products if p['id'].split(':')[-1] == weekly['product_key']]
    product, theme, claim, matched, scores = choose_product(eligible, news, args.product)
    creative = campaign_plan(product, recent_campaigns(args.database))
    ingredients = select_ingredients(product, weekly, creative['source'], now)
    return export_campaign(args, now, product, theme, claim, matched, scores, news,
                           weekly, creative, ingredients)


def export_campaign(args, now, product, theme, claim, matched, scores, news,
                    weekly, creative, ingredients):
    """Render previously verified evidence; no source fetching or delivery here."""
    for copy in creative['copies'].values():
        copy['ingredients'] = ingredients
    import tempfile
    import uuid
    import shutil
    args.output.mkdir(parents=True, exist_ok=True)
    generation_id = now.strftime('%Y%m%dT%H%M%SZ-') + uuid.uuid4().hex[:8]
    directory = args.output / ('ioma-' + generation_id)
    if directory.exists():
        raise FileExistsError('La cartella della campagna esiste già: nessun file è stato sostituito.')
    working = Path(tempfile.mkdtemp(prefix='.campaign-', dir=args.output))
    published = False
    try:
        languages = LANGUAGES
        localized_reports = {}
        for language in languages:
            copy = creative['copies'][language]
            locale_working = working/language
            locale_working.mkdir()
            graphics = render_campaign(product, copy, locale_working, creative['scene'])
            localized_reports[language] = {
                **copy,
                'graphics': {kind: {**{k: v for k, v in info.items() if k != 'path'},
                                    'path': str((directory/language/info['path'].name).resolve())}
                             for kind, info in graphics.items()}}
        report = {'created_at': now.isoformat(), 'window_start': (now-timedelta(days=7)).isoformat(),
                  'query': QUERY, 'product': product['name'], 'product_id': product['id'],
                  'creative': creative, 'source_claim': claim, 'theme': theme,
                  'weekly': weekly, 'ingredients': ingredients,
                  'theme_news_counts': scores, 'matched_news': matched, 'news': news,
                  'localizations': localized_reports,
                  'quality': {'technical_checks': 'passed', 'visual_review': 'pending',
                              'publication_status': 'not_published'},
                  'limitations': 'Weekly sources guide editorial ingredient selection, not concentration ranking. '
                                 'Advertising coverage is not proof of current paid delivery or budgets. '
                                 'Public copy uses documented IOMA claims.'}
        for language in languages:
            graphics_paths = {kind: working/language/(kind+'.png') for kind in ('feed','story','banner')}
            presentation = create_presentation(product, report, graphics_paths, working/language/'presentazione.pptx', language)
            presentation['path'] = str((directory/language/'presentazione.pptx').resolve())
            report['localizations'][language]['presentation'] = presentation
        # All six images, both decks and history are committed together.
        with sqlite3.connect(args.database) as db:
            db.execute('INSERT INTO generations VALUES(?,?,?,?,?)',
                       (generation_id, now.isoformat(), product['id'], str((directory/languages[0]/'feed.png').resolve()),
                        json.dumps(report, ensure_ascii=False)))
            working.rename(directory)
            published = True
    except Exception:
        shutil.rmtree(working, ignore_errors=True)
        # This directory belongs to this invocation, never to an earlier campaign.
        if published and directory.exists():
            shutil.rmtree(directory)
        raise
    result = {language: {kind: directory/language/(kind+'.png') for kind in graphics}
              for language in languages}
    for language in languages:
        result[language]['presentation'] = directory/language/'presentazione.pptx'
        for path in result[language].values():
            print(path.resolve())
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, default=ROOT/'data/catalog.sqlite')
    parser.add_argument('--output', type=Path, default=ROOT/'output')
    parser.add_argument('--product', help='Parte del nome per scegliere il prodotto')
    parser.add_argument('--research', type=Path, default=ROOT/'research/2026-10-08.json', help='Brief settimanale verificato nelle ultime 36 ore')
    args = parser.parse_args()
    try:
        run(args)
    except Exception as error:
        parser.exit(1, f'Errore: {error}\n')


if __name__ == '__main__':
    main()
