from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from argparse import Namespace
from PIL import Image
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
