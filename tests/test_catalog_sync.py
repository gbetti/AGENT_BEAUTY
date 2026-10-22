from io import BytesIO
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import Mock, patch
from urllib.error import URLError

from catalog import ROOT, load_products, apply_snapshot
from catalog_sync import collect_product, collect_reviews, parse_page, plain, product_id, storefront_products, write_review_exports
from PIL import Image
from weekly import fetch_scoped_inci


def review(identity, rating=5):
    return {'uuid': identity, 'rating': rating, 'body': 'Avis public.', 'reviewer_name': 'Client A.',
            'created_at': '2026-10-20T12:00:00Z', 'verified_buyer': True}


class CatalogSyncTests(unittest.TestCase):
    def test_changed_photographs_get_new_paths_without_overwriting_prior_assets(self):
        with tempfile.TemporaryDirectory() as folder, patch('catalog_sync.ROOT', Path(folder)):
            product={'id':1,'handle':'example','title':'Example','vendor':'IOMA','product_type':'Soin',
                     'tags':[],'updated_at':'2026-10-22','body_html':'<p>Official.</p>',
                     'variants':[{'id':2,'sku':'A','price':'25.00'}],
                     'images':[{'src':'https://cdn.shopify.com/example.jpg','width':5,'height':5}]}
            paths=[]
            for color in ('white','pink'):
                raw=BytesIO();Image.new('RGB',(5,5),color).save(raw,'JPEG')
                fetch=Mock(side_effect=[b'<html></html>',b'<html></html>',raw.getvalue()])
                entry=collect_product(product,'2026-10-22T00:00:00Z',fetch)
                paths.append(Path(folder)/entry['local_image']['path'])
            self.assertNotEqual(paths[0],paths[1])
            self.assertTrue(all(path.is_file() for path in paths))

    def test_storefront_collects_every_page_and_rejects_a_repeating_page(self):
        fetch = Mock(side_effect=[json.dumps({'products': [{'id': 1}]}),
                                  json.dumps({'products': [{'id': 2}]}), '{"products":[]}'])
        self.assertEqual([p['id'] for p in storefront_products(fetch)], [1, 2])
        self.assertIn('page=3', fetch.call_args.args[0])
        with self.assertRaisesRegex(ValueError, 'ripetuta'):
            storefront_products(Mock(return_value='{"products":[{"id":1}]}'))

    def test_reviews_follow_pagination_and_keep_scores_separate_from_claims(self):
        widget = {'number_of_reviews': 3, 'average_rating': '4.00', 'reviews': [review('one')]}
        packets = [{'product_external_id': 12, 'reviews': [review('one'), review('two', 2)],
                    'pagination': {'total_pages': 2}},
                   {'product_external_id': 12, 'reviews': [review('three')], 'pagination': {'total_pages': 2}}]
        result = collect_reviews(12, widget, Mock(side_effect=[json.dumps(p) for p in packets]))
        self.assertEqual(result['status'], 'complete')
        self.assertEqual(len(result['items']), 3)
        self.assertEqual(result['items'][1]['rating'], 2)
        self.assertEqual(result['average'], '4.00')

    def test_unavailable_and_partial_reviews_are_never_reported_as_complete(self):
        self.assertIsNone(collect_reviews(1, None)['reported_count'])
        widget = {'number_of_reviews': 2, 'average_rating': '4.50', 'reviews': [review('one')]}
        for fetch in (Mock(side_effect=URLError('offline')), Mock(return_value=json.dumps({'product_external_id': 2}))):
            result = collect_reviews(1, widget, fetch)
            self.assertEqual(result['status'], 'partial')
            self.assertEqual(len(result['items']), 1)

    def test_page_sections_exclude_navigation_and_use_the_requested_review_widget(self):
        html = '''<accordion-disclosure><summary>Navigation</summary>Ignore</accordion-disclosure>
        <div data-block-type="description"><div class="prose">Official description.</div></div>
        <accordion-disclosure class="accordion"><summary>Texture</summary><div class="accordion__content">Silky.</div></accordion-disclosure>
        <script>jdgm.data.reviewWidget[42] = {"product_external_id":42,"number_of_reviews":0};</script>'''
        details, widget = parse_page(html, 42)
        self.assertEqual(details['sections'], {'Texture': 'Silky.'})
        self.assertEqual(widget['number_of_reviews'], 0)
        self.assertIsNone(parse_page(html, 99)[1])
        self.assertEqual(plain('<p>Texte</p><script>unsafe()</script>'), 'Texte')

    def test_snapshot_import_is_idempotent_and_preserves_existing_generations_and_claims(self):
        with tempfile.TemporaryDirectory() as folder:
            database = Path(folder)/'catalog.sqlite'
            first = load_products(database)
            self.assertEqual(len(first), 63)
            self.assertEqual(len({p['id'] for p in first}), 63)
            self.assertEqual(product_id('cc-gel-soin-teinte-eclat-parfait'), 'urn:agent-beauty:manual:ioma:cc-gel')
            with sqlite3.connect(database) as db:
                db.execute('INSERT INTO generations VALUES (?,?,?,?,?)', ('keep', '2026-10-21', 'product', 'feed.png', '{}'))
            second = load_products(database)
            self.assertEqual(len(second), len(first))
            with sqlite3.connect(database) as db:
                self.assertEqual(db.execute('SELECT COUNT(*) FROM product_reviews').fetchone()[0], 2461)
                self.assertEqual(db.execute('SELECT id FROM generations').fetchone()[0], 'keep')
            shampoo = next(p for p in second if p['id'].endswith(':shampooing-soin-hydratant-anti-casse'))
            self.assertEqual(shampoo['data']['editorial']['user_supplied']['price_eur'], '25.00')
            self.assertEqual(shampoo['data']['official']['variants'][0]['price'], '24.90')
            self.assertTrue(shampoo['data']['official']['localizations']['it']['description'])
            self.assertTrue(Path(shampoo['images'][0]['path']).is_file())

    def test_partial_refresh_does_not_erase_previously_collected_reviews(self):
        with tempfile.TemporaryDirectory() as folder:
            database = Path(folder)/'catalog.sqlite'
            load_products(database)
            snapshot = json.loads((ROOT/'assets/catalog/ioma.json').read_text())
            product = next(p for p in snapshot['products'] if p['reviews']['reported_count'] > 1)
            original_count = product['reviews']['reported_count']
            product['reviews'].update(status='partial', items=product['reviews']['items'][:1])
            snapshot['products'] = [product]
            path = Path(folder)/'partial.json'
            path.write_text(json.dumps(snapshot))
            apply_snapshot(database, path)
            with sqlite3.connect(database) as db:
                self.assertEqual(db.execute('SELECT COUNT(*) FROM product_reviews WHERE product_id=?',
                                            (product['id'],)).fetchone()[0], original_count)

    def test_inci_keeps_ingredients_after_perfume_but_not_related_products(self):
        html = b'''<accordion-disclosure class="accordion"><summary>Actifs et composition</summary>
        <div class="accordion__content">AQUA (WATER), PARFUM (FRAGRANCE), ARGANIA SPINOSA KERNEL OIL*, SACCHARIDE ISOMERATE</div>
        </accordion-disclosure><div>Related: CERAMIDE NP</div>'''
        with patch('weekly.urllib.request.urlopen', return_value=BytesIO(html)):
            inci = fetch_scoped_inci('https://ioma-paris.com/products/example')
        self.assertIn('SACCHARIDE ISOMERATE', inci)
        self.assertIn('ARGANIA SPINOSA KERNEL OIL', inci)
        self.assertNotIn('CERAMIDE NP', inci)


if __name__ == '__main__':
    unittest.main()
