"""Local product catalog and original photography; no product scraping."""
import json
from pathlib import Path
import sqlite3

ROOT = Path(__file__).resolve().parent


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
