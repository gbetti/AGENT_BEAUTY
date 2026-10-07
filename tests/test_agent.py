from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from argparse import Namespace
from PIL import Image, ImageChops
from agent import load_products, parse_news, choose_product, render, run


class AgentTests(unittest.TestCase):
    def test_news_filters_old_future_invalid_and_duplicate(self):
        xml = b'''<rss><channel>
        <item><title>Glow skincare</title><link>https://example.com/one</link><pubDate>Wed, 07 Oct 2026 10:00:00 GMT</pubDate></item>
        <item><title>Duplicate</title><link>https://example.com/one</link><pubDate>Wed, 07 Oct 2026 10:00:00 GMT</pubDate></item>
        <item><title>Old</title><link>https://example.com/old</link><pubDate>Wed, 23 Sep 2026 10:00:00 GMT</pubDate></item>
        <item><title>Future</title><link>https://example.com/future</link><pubDate>Wed, 14 Oct 2026 10:00:00 GMT</pubDate></item>
        <item><title>No date</title><link>https://example.com/invalid</link></item>
        </channel></rss>'''
        rows = parse_news(xml, datetime(2026, 10, 7, 12, tzinfo=timezone.utc))
        self.assertEqual([r['title'] for r in rows], ['Glow skincare'])

    def test_catalog_initialized_once_and_rendered(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'catalog.sqlite'
            products = load_products(path)
            self.assertEqual(len(products), 3)
            for item in products:
                self.assertEqual(len(item['images']), 1)
                self.assertTrue(Path(item['images'][0]['path']).is_file())
            original = path.read_bytes()
            self.assertEqual(load_products(path), products)
            self.assertEqual(path.read_bytes(), original)
            product, theme, claim, matched, scores = choose_product(products, [{'title': 'The glow skincare trend'}])
            self.assertIn('CC Gel', product['name'])
            self.assertEqual(theme, 'glow')
            render(product, theme, claim, Path(folder)/'post.png')
            with Image.open(Path(folder)/'post.png') as image:
                self.assertEqual(image.size, (1080, 1350))
                self.assertEqual(image.format, 'PNG')
                with Image.open(product['images'][0]['path']) as original_photo:
                    expected = original_photo.convert('RGB')
                    expected.thumbnail((600, 600), Image.Resampling.LANCZOS)
                # Confirm the exported post contains the exact local packshot,
                # scaled to the photo area, rather than a placeholder.
                actual = image.crop((240, 470, 840, 1070))
                self.assertIsNone(ImageChops.difference(actual, expected).getbbox())

    def test_missing_product_photo_is_reported(self):
        with tempfile.TemporaryDirectory() as folder:
            product = load_products(Path(folder)/'catalog.sqlite')[0]
            product['images'][0]['path'] = str(Path(folder)/'missing.jpg')
            with self.assertRaisesRegex(RuntimeError, 'Foto prodotto non trovata'):
                render(product, 'glow', 'Un incarnato luminoso.', Path(folder)/'post.png')
            self.assertFalse((Path(folder)/'post.png').exists())

    def test_network_failure_does_not_create_trend_artwork(self):
        with tempfile.TemporaryDirectory() as folder:
            args = Namespace(database=Path(folder)/'db.sqlite', output=Path(folder)/'output', product=None, font=None)
            with patch('agent.search_news', side_effect=RuntimeError('blocked')):
                with self.assertRaisesRegex(RuntimeError, 'blocked'):
                    run(args)
            self.assertFalse(args.output.exists())

    def test_each_run_searches_and_creates_distinct_output(self):
        with tempfile.TemporaryDirectory() as folder:
            args = Namespace(database=Path(folder)/'db.sqlite', output=Path(folder)/'output', product='Contour', font=None)
            news = [{'title':'Skin barrier trend', 'url':'https://example.com', 'publisher':'Example', 'published_at':'2026-10-07T10:00:00+00:00'}]
            with patch('agent.search_news', return_value=news) as search:
                run(args)
                run(args)
            self.assertEqual(search.call_count, 2)
            directories = list(args.output.iterdir())
            self.assertEqual(len(directories), 2)
            for directory in directories:
                self.assertTrue((directory/'instagram.png').exists())
                self.assertTrue((directory/'research.json').exists())
                self.assertIn('Contour', (directory/'caption.txt').read_text())
