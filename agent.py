"""Create Instagram artwork from the local catalog and fresh beauty news."""
import argparse
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import json
from pathlib import Path
import sqlite3
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

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
    PRIMARY KEY(page_url,name,image_url));''')


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
            images = []
            for source_url, image_path in db.execute(
                    'SELECT i.url,i.path FROM images i JOIN product_images pi ON pi.image_url=i.url '
                    'WHERE pi.page_url=? AND pi.name=? ORDER BY i.url', (url, name)):
                local_path = ROOT / image_path
                if not local_path.is_file():
                    local_path = path.parent / image_path
                images.append({'source_url': source_url, 'path': str(local_path.resolve())})
            products.append({'id': url, 'name': name, 'description': description,
                             'data': json.loads(raw), 'images': images})
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
        if not title or not url.startswith('https://') or url in seen or not cutoff <= published <= now:
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


def render(product, theme, claim, path, font_path=None):
    from PIL import Image, ImageDraw, ImageFont
    if not product.get('images'):
        raise RuntimeError('Nessuna foto collegata al prodotto nel database: ' + product['name'])
    photo_path = Path(product['images'][0]['path'])
    if not photo_path.is_file():
        raise RuntimeError('Foto prodotto non trovata: ' + str(photo_path))
    def font(size):
        try:
            return ImageFont.truetype(font_path or 'DejaVuSans.ttf', size)
        except OSError:
            raise RuntimeError('Font non disponibile: usa --font /percorso/font.ttf')
    image = Image.new('RGB', (1080, 1350))
    draw = ImageDraw.Draw(image)
    top, bottom = THEMES[theme]['colors']
    for y in range(1350):
        ratio = y / 1349
        draw.line((0, y, 1080, y), fill=tuple(round(a + (b-a)*ratio) for a,b in zip(top,bottom)))
    draw.ellipse((600, -220, 1400, 580), fill=top)
    draw.ellipse((-340, 940, 420, 1700), outline=(244, 242, 232), width=3)
    ink = (39, 49, 42)
    draw.text((90, 95), 'IOMA PARIS', font=font(36), fill=ink)
    draw.line((90, 169, 990, 169), fill=ink, width=2)
    draw.text((90, 230), THEMES[theme]['label'], font=font(28), fill=ink)
    def block(text, y, size, max_width=890):
        face = font(size)
        lines = []
        current = ''
        for word in text.split():
            trial = (current + ' ' + word).strip()
            if draw.textlength(trial, font=face) > max_width and current:
                lines.append(current)
                current = word
            else:
                current = trial
        if current:
            lines.append(current)
        for line in lines:
            draw.text((90, y), line, font=face, fill=ink)
            y += int(size * 1.35)
        return y
    y = block(claim, 300, 48)
    if y > 460:
        raise RuntimeError('Claim troppo lungo per il layout: abbrevia il claim editoriale.')
    # Keep the original packshot intact: only scale it to fit its photo area.
    with Image.open(photo_path) as original:
        photo = original.convert('RGB')
        photo.thumbnail((600, 600), Image.Resampling.LANCZOS)
    image.paste(photo, ((1080-photo.width)//2, 470+(600-photo.height)//2))
    y = block(product['name'], 1100, 27)
    properties = product['data'].get('additionalProperty', [])
    line = next((p['value'] for p in properties if p.get('name') == 'Gamme'), '')
    block(line, y+12, 22)
    draw.line((90, 1230, 990, 1230), fill=ink, width=2)
    draw.text((90, 1260), 'Il tuo rituale beauty, ogni giorno.', font=font(24), fill=ink)
    image.save(path, format='PNG')


def run(args):
    now = datetime.now(timezone.utc)
    products = load_products(args.database)
    # Fetch fresh evidence on EVERY normal invocation. No cached-trend fallback.
    news = search_news(now)
    product, theme, claim, matched, scores = choose_product(products, news, args.product)
    args.output.mkdir(parents=True, exist_ok=True)
    import tempfile
    directory = Path(tempfile.mkdtemp(prefix=now.strftime('%Y%m%dT%H%M%SZ-'), dir=args.output))
    render(product, theme, claim, directory/'instagram.png', args.font)
    report = {'created_at': now.isoformat(), 'window_start': (now-timedelta(days=7)).isoformat(), 'query': QUERY,
              'product': product['name'], 'claim': claim, 'theme': theme, 'theme_news_counts': scores,
              'matched_news': matched, 'news': news,
              'product_image': {'project_path': product['data'].get('local_image_path'),
                                'source_url': product['images'][0]['source_url']},
              'limitations': 'Segnali editoriali dalle notizie, non misure di viralità social.'}
    (directory/'research.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    caption = f"{claim}\n\n{product['name']} — IOMA Paris\n\n#IOMAParis #Skincare #BeautyRoutine"
    (directory/'caption.txt').write_text(caption, encoding='utf-8')
    print(f'Grafica Instagram 1080×1350: {directory / "instagram.png"}')
    print(f'Fonti recenti: {len(news)}; notizie associate al tema: {len(matched)}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, default=ROOT/'data/catalog.sqlite')
    parser.add_argument('--output', type=Path, default=ROOT/'output')
    parser.add_argument('--product', help='Parte del nome per scegliere il prodotto')
    parser.add_argument('--font', help='Percorso di un font TrueType')
    args = parser.parse_args()
    try:
        run(args)
    except Exception as error:
        parser.exit(1, f'Errore: {error}\n')


if __name__ == '__main__':
    main()
