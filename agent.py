"""Collect public IOMA Product JSON-LD, honoring robots.txt, into SQLite."""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import time
import urllib.parse
import urllib.request
import urllib.robotparser
import xml.etree.ElementTree as ET
from html.parser import HTMLParser


class ProductParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.active = False
        self.buffer = []
        self.products = []

    def handle_starttag(self, tag, attrs):
        if tag == 'script' and dict(attrs).get('type') == 'application/ld+json':
            self.active = True
            self.buffer = []

    def handle_data(self, data):
        if self.active:
            self.buffer.append(data)

    def handle_endtag(self, tag):
        if tag == 'script' and self.active:
            self.active = False
            try:
                self.walk(json.loads(''.join(self.buffer)))
            except json.JSONDecodeError:
                pass

    def walk(self, item):
        if isinstance(item, list):
            for value in item:
                self.walk(value)
        elif isinstance(item, dict):
            kind = item.get('@type', [])
            if kind == 'Product' or isinstance(kind, list) and 'Product' in kind:
                self.products.append(item)
            for value in item.values():
                if isinstance(value, (list, dict)):
                    self.walk(value)


def initialize(db):
    db.executescript('''
    CREATE TABLE IF NOT EXISTS products (
      page_url TEXT NOT NULL, name TEXT NOT NULL, sku TEXT,
      description TEXT, json_ld TEXT NOT NULL,
      collected_at TEXT DEFAULT CURRENT_TIMESTAMP,
      PRIMARY KEY (page_url, name));
    CREATE TABLE IF NOT EXISTS images (
      url TEXT PRIMARY KEY, path TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS product_images (
      page_url TEXT, name TEXT, image_url TEXT,
      PRIMARY KEY (page_url, name, image_url));
    ''')


def run(args):
    base = args.base_url.rstrip('/')
    host = urllib.parse.urlsplit(base).hostname
    if host not in {'ioma-paris.com', 'www.ioma-paris.com'}:
        raise ValueError('Only IOMA hosts are supported')
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    (output / 'images').mkdir(exist_ok=True)
    user_agent = 'AgentBeauty/1.0'
    last_request = 0.0

    def fetch(url):
        nonlocal last_request
        delay = max(args.delay, 1.0) - (time.monotonic() - last_request)
        if delay > 0:
            time.sleep(delay)
        request = urllib.request.Request(url, headers={'User-Agent': user_agent})
        last_request = time.monotonic()
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.read(), response.headers.get_content_type()

    # Fail closed if robots.txt cannot be fetched.
    raw, _ = fetch(base + '/robots.txt')
    robots = urllib.robotparser.RobotFileParser()
    robots.parse(raw.decode('utf-8', errors='replace').splitlines())
    pending = robots.site_maps() or [base + '/sitemap.xml']
    pages = set(args.url)
    visited = set()
    while pending:
        url = pending.pop()
        if url in visited:
            continue
        if urllib.parse.urlsplit(url).hostname != host:
            raise ValueError('Sitemap host differs from base host: ' + url)
        visited.add(url)
        if not robots.can_fetch(user_agent, url):
            raise RuntimeError('robots.txt disallows sitemap: ' + url)
        raw, _ = fetch(url)
        root = ET.fromstring(raw)
        locations = [node.text for node in root.iter() if node.tag.split('}')[-1] == 'loc' and node.text]
        if root.tag.split('}')[-1] == 'sitemapindex':
            pending.extend(locations)
        else:
            pages.update(locations)
    total = 0
    with sqlite3.connect(output / 'catalog.sqlite') as db:
        initialize(db)
        for url in sorted(pages)[:args.max_pages]:
            if urllib.parse.urlsplit(url).hostname != host or not robots.can_fetch(user_agent, url):
                continue
            raw, content_type = fetch(url)
            if content_type != 'text/html':
                continue
            parser = ProductParser()
            parser.feed(raw.decode('utf-8', errors='replace'))
            for product in parser.products:
                name = product.get('name')
                if not isinstance(name, str) or not name:
                    continue
                db.execute('INSERT OR REPLACE INTO products(page_url,name,sku,description,json_ld) VALUES(?,?,?,?,?)',
                           (url, name, str(product.get('sku', '')), str(product.get('description', '')), json.dumps(product, ensure_ascii=False)))
                images = product.get('image', [])
                if not isinstance(images, list):
                    images = [images]
                for image in images:
                    image = image.get('url', image.get('contentUrl')) if isinstance(image, dict) else image
                    if not isinstance(image, str):
                        continue
                    image = urllib.parse.urljoin(url, image)
                    if urllib.parse.urlsplit(image).hostname != host:
                        print('External image host requires separate access/robots verification:', image)
                        continue
                    if not robots.can_fetch(user_agent, image):
                        continue
                    found = db.execute('SELECT path FROM images WHERE url=?', (image,)).fetchone()
                    if not found:
                        data, mime = fetch(image)
                        if not mime.startswith('image/'):
                            raise ValueError('Expected image: ' + image)
                        suffix = {'image/jpeg': '.jpg', 'image/png': '.png', 'image/webp': '.webp', 'image/svg+xml': '.svg'}.get(mime, '.img')
                        path = Path('images') / (hashlib.sha256(image.encode()).hexdigest() + suffix)
                        (output / path).write_bytes(data)
                        db.execute('INSERT INTO images VALUES (?,?)', (image, str(path)))
                    db.execute('INSERT OR IGNORE INTO product_images VALUES (?,?,?)', (url, name, image))
                total += 1
            db.commit()
    print(f'Collected {total} product records into {output / "catalog.sqlite"}')
    if not total:
        raise RuntimeError('No Product JSON-LD found; inspect website structure before claiming collection works')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default='https://ioma-paris.com')
    parser.add_argument('--output', default='data')
    parser.add_argument('--url', action='append', default=[])
    parser.add_argument('--max-pages', type=int, default=300)
    parser.add_argument('--delay', type=float, default=1.5)
    args = parser.parse_args()
    if args.max_pages < 1:
        parser.error('--max-pages must be positive')
    run(args)


if __name__ == '__main__':
    main()
