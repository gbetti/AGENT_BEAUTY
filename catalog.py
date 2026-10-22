"""Local catalog, reviewed campaign copy and snapshots of the public storefront."""
import hashlib
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
    image_path TEXT NOT NULL, research_json TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS catalog_sources (path TEXT PRIMARY KEY, sha256 TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS product_reviews (
    product_id TEXT NOT NULL, review_id TEXT NOT NULL, rating INTEGER NOT NULL,
    title TEXT, body TEXT, author TEXT, created_at TEXT, verified_buyer INTEGER,
    source_url TEXT NOT NULL, collected_at TEXT NOT NULL, metadata_json TEXT NOT NULL,
    PRIMARY KEY(product_id, review_id));''')


def apply_snapshot(database, snapshot_path=None):
    snapshot_path = snapshot_path or ROOT/'assets/catalog/ioma.json'
    if not snapshot_path.is_file():
        return
    raw = snapshot_path.read_bytes()
    checksum = hashlib.sha256(raw).hexdigest()
    source = str(snapshot_path.resolve())
    with sqlite3.connect(database) as db:
        initialize(db)
        if db.execute('SELECT sha256 FROM catalog_sources WHERE path=?', (source,)).fetchone() == (checksum,):
            return
        snapshot = json.loads(raw)
        if snapshot.get('schema_version') != 1:
            raise ValueError('Snapshot catalogo non supportato.')
        for product in snapshot['products']:
            prior = db.execute('SELECT name,json_ld FROM products WHERE page_url=?', (product['id'],)).fetchone()
            name = prior[0] if prior else product['name']
            data = json.loads(prior[1]) if prior else {}
            # Imported descriptions/reviews never silently overwrite reviewed claims.
            data['official'] = {k: v for k, v in product.items() if k != 'reviews'}
            data['customer_reviews'] = {k: v for k, v in product['reviews'].items() if k != 'items'}
            image = product.get('local_image')
            if image:
                data.update(local_image_path=image['path'], image_source_url=image['source_url'])
                db.execute('INSERT INTO images VALUES (?,?) ON CONFLICT(url) DO UPDATE SET path=excluded.path',
                           (image['source_url'], image['path']))
                db.execute('INSERT OR IGNORE INTO product_images VALUES (?,?,?)',
                           (product['id'], name, image['source_url']))
            sku = next((variant['sku'] for variant in product['variants'] if variant['sku']), None)
            db.execute('INSERT INTO products(page_url,name,sku,description,json_ld,collected_at) VALUES (?,?,?,?,?,?) '
                       'ON CONFLICT(page_url,name) DO UPDATE SET sku=excluded.sku,description=excluded.description,'
                       'json_ld=excluded.json_ld,collected_at=excluded.collected_at',
                       (product['id'], name, sku, product['description'], json.dumps(data, ensure_ascii=False),
                        product['collected_at']))
            # Refresh only complete public review sets. A partial fetch cannot erase prior reviews.
            if product['reviews']['status'] == 'complete':
                db.execute('DELETE FROM product_reviews WHERE product_id=?', (product['id'],))
            for review in product['reviews']['items']:
                db.execute('INSERT OR REPLACE INTO product_reviews VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                           (product['id'], review['id'], review['rating'], review['title'], review['body'],
                            review['author'], review['created_at'], int(review['verified_buyer']),
                            product['source_url']+'#judgeme_product_reviews', product['collected_at'],
                            json.dumps(review, ensure_ascii=False)))
        db.execute('INSERT OR REPLACE INTO catalog_sources VALUES (?,?)', (source, checksum))


def apply_reviewed_copy(database):
    path = ROOT/'assets/catalog/reviewed-copy.json'
    if not path.is_file():
        return
    with sqlite3.connect(database) as db:
        for key, editorial in json.loads(path.read_text(encoding='utf-8')).items():
            identity = 'urn:agent-beauty:ioma:' + key
            row = db.execute('SELECT json_ld FROM products WHERE page_url=?', (identity,)).fetchone()
            if row:
                data = json.loads(row[0])
                if data.get('editorial') != editorial:
                    data['editorial'] = editorial
                    db.execute('UPDATE products SET json_ld=? WHERE page_url=?',
                               (json.dumps(data, ensure_ascii=False), identity))


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
    apply_snapshot(path)
    apply_reviewed_copy(path)
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
