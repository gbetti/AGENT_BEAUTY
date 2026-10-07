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
BACKGROUND_PATH = ROOT / 'assets/backgrounds/ioma-campaign.png'
LOGO_PATH = ROOT / 'assets/brand/ioma-logo.png'
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


def packshot_layer(photo_path):
    """Remove only connected white background; keep the original asset unchanged."""
    from PIL import Image, ImageChops, ImageDraw, ImageFilter
    with Image.open(photo_path) as source:
        photo = source.convert('RGB')
    minimum = ImageChops.darker(photo.getchannel('R'),
                               ImageChops.darker(photo.getchannel('G'), photo.getchannel('B')))
    exterior = minimum.point(lambda value: 255 if value >= 250 else 0)
    for corner in [(0, 0), (photo.width-1, 0), (0, photo.height-1),
                   (photo.width-1, photo.height-1)]:
        if exterior.getpixel(corner) == 255:
            ImageDraw.floodfill(exterior, corner, 128)
    alpha = exterior.point(lambda value: 0 if value == 128 else 255)
    # Remove isolated edge speckles from JPEG compression and antialias the cutout.
    alpha = alpha.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.MaxFilter(3))
    alpha = alpha.filter(ImageFilter.GaussianBlur(0.4))
    result = photo.convert('RGBA')
    result.putalpha(alpha)
    bounds = alpha.getbbox()
    if bounds is None:
        raise RuntimeError('La foto non contiene un packshot visibile.')
    return result.crop(bounds)


def render(product, theme, claim, path, font_path=None):
    from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter, ImageChops
    if not product.get('images'):
        raise RuntimeError('Nessuna foto collegata al prodotto nel database: ' + product['name'])
    photo_path = Path(product['images'][0]['path'])
    if not photo_path.is_file():
        raise RuntimeError('Foto prodotto non trovata: ' + str(photo_path))
    for asset in (BACKGROUND_PATH, LOGO_PATH):
        if not asset.is_file():
            raise RuntimeError('Asset grafico non trovato: ' + str(asset))
    def font(size):
        try:
            return ImageFont.truetype(font_path or 'DejaVuSerif.ttf', size)
        except OSError:
            raise RuntimeError('Font non disponibile: usa --font /percorso/font.ttf')
    with Image.open(BACKGROUND_PATH) as original_background:
        image = ImageOps.fit(original_background.convert('RGB'), (1080, 1350)).convert('RGBA')
    # Composite the real packshot, rather than asking a model to recreate it.
    photo = packshot_layer(photo_path)
    photo.thumbnail((430, 800), Image.Resampling.LANCZOS)
    shadow = Image.new('RGBA', image.size)
    ImageDraw.Draw(shadow).ellipse((810-photo.width*0.4, 998,
                                  810+photo.width*0.4, 1020), fill=(35, 24, 15, 95))
    image.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(8)))
    image.alpha_composite(photo, (810-photo.width//2, 1010-photo.height))
    # Preserve the official wordmark's alpha silhouette; use its white brand variant.
    with Image.open(LOGO_PATH) as original_logo:
        original_logo = original_logo.convert('RGBA')
        logo = Image.new('RGBA', original_logo.size, (255, 255, 255, 0))
        logo.putalpha(ImageChops.multiply(original_logo.getchannel('A'),
                                          ImageOps.invert(original_logo.convert('L'))))
    logo.thumbnail((280, 117), Image.Resampling.LANCZOS)
    image.alpha_composite(logo, (82, 90))
    draw = ImageDraw.Draw(image)
    ink = (255, 249, 240)
    def wrapped(text, face, max_width):
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
        return lines
    def block(text, y, size, max_width=470):
        face = font(size)
        lines = wrapped(text, face, max_width)
        for line in lines:
            draw.text((82, y), line, font=face, fill=ink,
                      stroke_width=1, stroke_fill=(88, 66, 53))
            y += int(size * 1.35)
        return y
    claim_size = 56
    while claim_size >= 36:
        lines = wrapped(claim, font(claim_size), 470)
        if len(lines) * int(claim_size*1.35) <= 330:
            break
        claim_size -= 2
    else:
        raise RuntimeError('Claim troppo lungo per la foto: abbrevia il claim editoriale.')
    block(claim, 470, claim_size)
    y = block(product['name'], 1010, 23)
    properties = product['data'].get('additionalProperty', [])
    line = next((p['value'] for p in properties if p.get('name') == 'Gamme'), '')
    block(line, y+22, 19)
    image.convert('RGB').save(path, format='PNG')


def run(args):
    now = datetime.now(timezone.utc)
    products = load_products(args.database)
    # Fetch fresh evidence on EVERY normal invocation. No cached-trend fallback.
    news = search_news(now)
    product, theme, claim, matched, scores = choose_product(products, news, args.product)
    args.output.mkdir(parents=True, exist_ok=True)
    import uuid
    generation_id = now.strftime('%Y%m%dT%H%M%SZ-') + uuid.uuid4().hex[:8]
    image_path = args.output / ('ioma-' + generation_id + '.png')
    render(product, theme, claim, image_path, args.font)
    report = {'created_at': now.isoformat(), 'window_start': (now-timedelta(days=7)).isoformat(), 'query': QUERY,
              'product': product['name'], 'claim': claim, 'theme': theme, 'theme_news_counts': scores,
              'matched_news': matched, 'news': news,
              'product_image': {'project_path': product['data'].get('local_image_path'),
                                'source_url': product['images'][0]['source_url']},
              'limitations': 'Segnali editoriali dalle notizie, non misure di viralità social.'}
    # Keep evidence internally: the user-facing output is one finished image only.
    try:
        with sqlite3.connect(args.database) as db:
            db.execute('INSERT INTO generations VALUES(?,?,?,?,?)',
                       (generation_id, now.isoformat(), product['id'], str(image_path.resolve()),
                        json.dumps(report, ensure_ascii=False)))
    except Exception:
        image_path.unlink(missing_ok=True)
        raise
    print(image_path.resolve())
    return image_path


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
