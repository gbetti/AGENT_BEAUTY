"""Import the public IOMA storefront and its public Judge.me review widget."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import re
import time
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup
from PIL import Image

ROOT = Path(__file__).resolve().parent
STORE = 'https://ioma-paris.com'
SHOP = 'ioma-paris.myshopify.com'
SNAPSHOT = ROOT/'assets/catalog/ioma.json'
ALIASES = {'cc-gel-soin-teinte-eclat-parfait': 'cc-gel'}
ORIGINAL_KEYS = {'cc-gel', 'creme-sublime-revitalisante', 'creme-genereuse-contour-des-yeux'}


def product_id(handle):
    key = ALIASES.get(handle, handle)
    prefix = 'urn:agent-beauty:manual:ioma:' if key in ORIGINAL_KEYS else 'urn:agent-beauty:ioma:'
    return prefix + key


def fetch(url):
    parts = urlsplit(url)
    if parts.scheme != 'https' or parts.hostname not in ('ioma-paris.com', 'cdn.shopify.com', 'cdn.judge.me'):
        raise ValueError('Fonte catalogo non autorizzata.')
    request = Request(url, headers={'User-Agent': 'AGENT_BEAUTY/CatalogSync (public product research)'})
    for attempt in range(3):
        try:
            with urlopen(request, timeout=30) as response:
                raw = response.read(12_000_001)
            if len(raw) > 12_000_000:
                raise ValueError('Risposta catalogo troppo grande.')
            return raw
        except HTTPError as error:
            if error.code not in (429, 500, 502, 503, 504) or attempt == 2:
                raise
            time.sleep(2 ** attempt)


def plain(html):
    soup = BeautifulSoup(html or '', 'html.parser')
    for tag in soup(['script', 'style']):
        tag.decompose()
    return soup.get_text(' ', strip=True)


def storefront_products(fetcher=fetch):
    products = {}
    page = 1
    while True:
        batch = json.loads(fetcher(f'{STORE}/products.json?limit=250&page={page}'))['products']
        if not batch:
            break
        before = len(products)
        for product in batch:
            products[product['id']] = product
        if len(products) == before:
            raise ValueError('Paginazione del catalogo ripetuta: importazione incompleta.')
        page += 1
    if not products:
        raise ValueError('Il catalogo pubblico è vuoto.')
    return list(products.values())


def parse_page(html, external_id):
    soup = BeautifulSoup(html, 'html.parser')
    description = soup.select_one('[data-block-type="description"] .prose')
    sections = {}
    for accordion in soup.select('accordion-disclosure.accordion'):
        title = accordion.select_one('summary')
        body = accordion.select_one('.accordion__content')
        if title and body:
            sections[title.get_text(' ', strip=True)] = body.get_text(' ', strip=True)
    widget = None
    marker = re.search(r'jdgm\.data\.reviewWidget\[' + str(external_id) + r'\]\s*=\s*', html)
    if marker:
        widget = json.JSONDecoder().raw_decode(html[marker.end():])[0]
        if str(widget.get('product_external_id')) != str(external_id):
            raise ValueError('Il widget recensioni appartiene a un altro prodotto.')
    return {'description': description.get_text(' ', strip=True) if description else None,
            'sections': sections}, widget


def normalize_review(review):
    # Only public review content; omit location, avatars, private IDs and tracking.
    return {'id': review['uuid'], 'rating': review['rating'],
            'title': review.get('title', ''), 'body': review.get('body') or plain(review.get('body_html')),
            'author': review.get('reviewer_name', ''), 'created_at': review.get('created_at'),
            'verified_buyer': bool(review.get('verified_buyer')),
            'source_product_title': review.get('product_title'),
            'from_group': bool(review.get('is_for_product_from_group') or review.get('is_for_product_from_bundle'))}


def collect_reviews(external_id, widget, fetcher=fetch):
    if widget is None:
        return {'status': 'unavailable', 'reported_count': None, 'average': None, 'items': [],
                'reason': 'Nessun widget pubblico individuato; non equivale a zero recensioni.'}
    expected = widget['number_of_reviews']
    reviews = {item['uuid']: normalize_review(item) for item in widget.get('reviews', [])}
    urls = []
    page = 1
    error_message = None
    while len(reviews) < expected:
        url = 'https://cdn.judge.me/reviews/reviews_for_widget?' + urlencode({
            'shop_domain': SHOP, 'platform': 'shopify', 'product_id': external_id,
            'page': page, 'per_page': 100})
        try:
            packet = json.loads(fetcher(url))
            if str(packet.get('product_external_id')) != str(external_id):
                raise ValueError('Recensioni di un altro prodotto.')
            urls.append(url)
            old_count = len(reviews)
            for item in packet.get('reviews', []):
                reviews[item['uuid']] = normalize_review(item)
            pagination = packet.get('pagination', {})
            if len(reviews) >= expected:
                break
            if (len(reviews) == old_count and page > 1) or page >= pagination.get('total_pages', page):
                error_message = 'La paginazione pubblica non copre il totale dichiarato.'
                break
            page += 1
        except (OSError, ValueError, KeyError) as error:
            error_message = f'{type(error).__name__}: paginazione recensioni non completata.'
            break
    return {'status': 'complete' if len(reviews) == expected else 'partial',
            'reported_count': expected, 'average': widget['average_rating'],
            'items': list(reviews.values()), 'page_urls': urls, 'reason': error_message,
            'policy': 'Opinioni dei clienti, non prove di efficacia o claim ufficiali.'}


def collect_product(product, fetched_at, fetcher=fetch):
    handle = product['handle']
    if not re.fullmatch(r'[a-z0-9-]+', handle):
        raise ValueError('Handle prodotto inatteso.')
    url = f'{STORE}/products/{handle}'
    raw = fetcher(url)
    fr, widget = parse_page(raw.decode('utf-8'), product['id'])
    it_url = f'{STORE}/it/products/{handle}'
    locale_error = None
    try:
        it, _ = parse_page(fetcher(it_url).decode('utf-8'), product['id'])
    except (OSError, ValueError) as error:
        it = {'description': None, 'sections': {}}
        locale_error = type(error).__name__
    image = product['images'][0] if product['images'] else None
    local_image = None
    if image:
        raw_image = fetcher(image['src'])
        with Image.open(io.BytesIO(raw_image)) as photo:
            width, height = photo.size
            photo.verify()
        suffix = Path(urlsplit(image['src']).path).suffix.lower()
        if suffix not in ('.png', '.jpg', '.jpeg', '.webp'):
            raise ValueError('Formato immagine catalogo non supportato.')
        image_hash = hashlib.sha256(raw_image).hexdigest()
        path = ROOT/'assets/catalog/images'/(handle + '-' + image_hash[:16] + suffix)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            if path.read_bytes() != raw_image:
                raise ValueError('Collisione nel percorso immutabile del packshot.')
        else:
            path.write_bytes(raw_image)
        local_image = {'path': str(path.relative_to(ROOT)), 'sha256': image_hash,
                       'source_url': image['src'], 'width': width, 'height': height}
    variants = [{key: variant.get(key) for key in
                 ('id', 'title', 'sku', 'available', 'price', 'compare_at_price')} for variant in product['variants']]
    return {'id': product_id(handle), 'handle': handle, 'external_id': product['id'],
            'name': product['title'], 'brand': product['vendor'], 'category': product['product_type'],
            'tags': product['tags'], 'source_url': url, 'collected_at': fetched_at,
            'source_updated_at': product['updated_at'], 'description': plain(product['body_html']),
            'localizations': {'fr': {**fr, 'source_url': url}, 'it': {**it, 'source_url': it_url, 'error': locale_error}},
            'currency': 'EUR', 'variants': variants, 'images': product['images'], 'local_image': local_image,
            'reviews': collect_reviews(product['id'], widget, fetcher),
            'page_sha256': hashlib.sha256(raw).hexdigest()}


def write_review_exports(snapshot, directory):
    directory = Path(directory)
    (directory/'reviews').mkdir(parents=True, exist_ok=True)
    rows = ['# Catalogo pubblico IOMA', '',
            f"Rilevato: {snapshot['collected_at']}. Articoli: **{len(snapshot['products'])}**. "
            f"Recensioni recuperate: **{sum(len(p['reviews']['items']) for p in snapshot['products'])}**.", '',
            'Schede complete FR/IT, composizioni, varianti, foto e fonti: [snapshot JSON](ioma.json). '
            'I commenti restano opinioni dei clienti, distinti dai benefici ufficiali. '
            'Il prezzo è quello della prima variante del sito, nella data indicata; eventuali prezzi forniti dall’utente restano separati.', '',
            '| Articolo | EUR | Voto / 5 | Recensioni | Copertura |', '| --- | ---: | ---: | ---: | --- |']
    for product in sorted(snapshot['products'], key=lambda p: p['name']):
        relative = 'reviews/'+product['handle']+'.json'
        packet = {'product': product['name'], 'source_url': product['source_url'],
                  'collected_at': product['collected_at'], **product['reviews']}
        (directory/relative).write_text(json.dumps(packet, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        reviews = product['reviews']
        rows.append(f"| [{product['name']}]({product['source_url']}) | {product['variants'][0]['price']} | "
                    f"{reviews['average']} | [{len(reviews['items'])}]({relative}) | {reviews['status']} |")
    (directory/'README.md').write_text('\n'.join(rows)+'\n', encoding='utf-8')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, default=ROOT/'data/catalog.sqlite')
    parser.add_argument('--snapshot', type=Path, default=SNAPSHOT)
    args = parser.parse_args(argv)
    now = datetime.now(timezone.utc).isoformat()
    products = storefront_products()
    # Four readers bound the load on the public storefront. No login or admin API.
    with ThreadPoolExecutor(max_workers=4) as executor:
        entries = list(executor.map(lambda product: collect_product(product, now), products))
    snapshot = {'schema_version': 1, 'source_url': STORE+'/products.json', 'collected_at': now,
                'product_count': len(entries), 'products': entries}
    args.snapshot.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.snapshot.with_suffix('.tmp')
    temporary.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    temporary.replace(args.snapshot)
    from catalog import apply_snapshot, load_products
    load_products(args.database)
    apply_snapshot(args.database, args.snapshot)
    write_review_exports(snapshot, args.snapshot.parent)
    print(json.dumps({'products': len(entries), 'reviews': sum(len(p['reviews']['items']) for p in entries),
                      'review_status': {status: sum(p['reviews']['status'] == status for p in entries)
                                        for status in ('complete', 'partial', 'unavailable')},
                      'snapshot': str(args.snapshot)}, indent=2))


if __name__ == '__main__':
    main()
