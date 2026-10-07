from datetime import datetime, timezone
from pathlib import Path
import json
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from argparse import Namespace

from PIL import Image, ImageChops, ImageDraw
from agent import load_products, parse_news, run
from campaign import FORMATS, campaign_copy, render_campaign, packshot_layer
from presentation import create_presentation, weekly_highlights
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE


class AgentTests(unittest.TestCase):
    def test_news_filters_old_future_invalid_and_duplicate(self):
        xml = b'''<rss><channel>
        <item><title>Glow skincare</title><link>https://example.com/one</link><pubDate>Wed, 07 Oct 2026 10:00:00 GMT</pubDate></item>
        <item><title>Duplicate</title><link>https://example.com/one</link><pubDate>Wed, 07 Oct 2026 10:00:00 GMT</pubDate></item>
        <item><title>Old</title><link>https://example.com/old</link><pubDate>Wed, 23 Sep 2026 10:00:00 GMT</pubDate></item>
        <item><title>Future</title><link>https://example.com/future</link><pubDate>Wed, 14 Oct 2026 10:00:00 GMT</pubDate></item>
        <item><title>No date</title><link>https://example.com/invalid</link></item>
        <item><title>George returns home from Eton</title><link>https://example.com/off-topic</link><pubDate>Wed, 07 Oct 2026 11:00:00 GMT</pubDate></item>
        </channel></rss>'''
        rows = parse_news(xml, datetime(2026, 10, 7, 12, tzinfo=timezone.utc))
        self.assertEqual([r['title'] for r in rows], ['Glow skincare'])

    def test_all_catalog_products_render_three_safe_formats(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'catalog.sqlite'
            products = load_products(path)
            self.assertEqual(len(products), 3)
            original = path.read_bytes()
            self.assertEqual(load_products(path), products)
            self.assertEqual(path.read_bytes(), original)
            for index, product in enumerate(products):
                with self.subTest(product=product['name']):
                    target = Path(folder)/str(index)
                    target.mkdir()
                    headline, cta = campaign_copy(product)
                    result = render_campaign(product, headline, cta, target)
                    self.assertEqual(set(result), set(FORMATS))
                    self.assertEqual({p.name for p in target.iterdir()}, {'feed.png','story.png','banner.png'})
                    for kind, size in FORMATS.items():
                        with Image.open(result[kind]['path']) as image:
                            self.assertEqual(image.size, size)
                            self.assertEqual(image.format, 'PNG')
                        elements = result[kind]['elements']
                        self.assertEqual({e['kind'] for e in elements}, {'product','logo','headline','cta'})
                        self.assertEqual(next(e['text'] for e in elements if e['kind']=='headline'), headline)
                        self.assertEqual(next(e['text'] for e in elements if e['kind']=='cta'), cta)
                        for element in elements:
                            if element['kind'] in ('headline','cta'):
                                self.assertGreaterEqual(element['contrast_ratio'],4.5)
                        margin_top = size[1]*(0.13 if kind=='story' else 0.05)
                        margin_bottom = size[1]*(0.82 if kind=='story' else 0.95)
                        for element in elements:
                            x1,y1,x2,y2 = element['box']
                            self.assertGreaterEqual(x1, size[0]*0.05)
                            self.assertLessEqual(x2, size[0]*0.95)
                            self.assertGreaterEqual(y1, margin_top)
                            self.assertLessEqual(y2, margin_bottom)
                    self.assertLessEqual(result['feed']['text_area_ratio'], 0.20)
                    self.assertEqual(result['feed']['source_size'], (1024,1536))
                    self.assertEqual(result['story']['source_size'], (1024,1536))
                    self.assertEqual(result['banner']['source_size'], (1536,1024))
                    headline_element = next(e for e in result['story']['elements'] if e['kind']=='headline')
                    self.assertLessEqual(headline_element['box'][3], 1920*.13 + (1920*.82-1920*.13)/3)

    def test_exact_italian_copy_and_reject_long_banner_headline(self):
        with tempfile.TemporaryDirectory() as folder:
            product = load_products(Path(folder)/'catalog.sqlite')[0]
            headline, cta = campaign_copy(product, 'È luce naturale!', 'Scopri di più')
            result = render_campaign(product, headline, cta, Path(folder))
            for info in result.values():
                title = next(e for e in info['elements'] if e['kind']=='headline')
                button = next(e for e in info['elements'] if e['kind']=='cta')
                self.assertEqual(' '.join(title['lines']), 'È luce naturale!')
                self.assertEqual(button['lines'], ['Scopri di più'])
            with self.assertRaisesRegex(ValueError, 'massimo 4 parole'):
                campaign_copy(product, 'Una headline con troppe parole qui', cta)

    def test_original_packshot_pixels_survive_banner_composition(self):
        with tempfile.TemporaryDirectory() as folder:
            product = load_products(Path(folder)/'catalog.sqlite')[0]
            headline, cta = campaign_copy(product)
            # Inspect the native master before downsampling: exact original pixel fidelity.
            from campaign import master
            photo = packshot_layer(product['images'][0]['path'])
            image, elements, _ = master(photo, headline, cta, landscape=True)
            fitted = photo.copy()
            fitted.thumbnail((330,600), Image.Resampling.LANCZOS)
            box = next(e['box'] for e in elements if e['kind']=='product')
            actual = image.crop(box).convert('RGB')
            opaque = fitted.getchannel('A').point(lambda value: 255 if value==255 else 0)
            difference = ImageChops.difference(actual, fitted.convert('RGB'))
            difference.paste((0,0,0), mask=ImageChops.invert(opaque))
            self.assertIsNone(difference.getbbox())

    def test_high_resolution_photo_is_preferred_to_older_database_link(self):
        with tempfile.TemporaryDirectory() as folder:
            products = load_products(Path(folder)/'catalog.sqlite')
            for product in products:
                self.assertIn('width=2000', product['images'][0]['source_url'])
                with Image.open(product['images'][0]['path']) as photo:
                    self.assertEqual(photo.size, (2000,2000))
                self.assertTrue(any('width=1000' in image['source_url'] for image in product['images']))

    def test_white_fringe_removed_without_erasing_white_print(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Image.new('RGB',(180,260),'white')
            drawing = ImageDraw.Draw(source)
            drawing.rectangle((45,20,135,240), fill=(245,245,245))
            drawing.rectangle((46,21,134,239), fill=(150,100,60))
            drawing.rectangle((65,105,115,150), fill='white')
            path = Path(folder)/'fringe.png';source.save(path)
            layer = packshot_layer(path)
            row = [layer.getpixel((x,layer.height//4)) for x in range(layer.width)]
            self.assertFalse(any(min(pixel[:3]) >= 240 and pixel[3] > 128 for pixel in row))
            self.assertEqual(layer.getpixel((layer.width//2,layer.height//2)), (255,255,255,255))

    def test_exports_sample_original_photo_once_at_final_resolution(self):
        with tempfile.TemporaryDirectory() as folder:
            product = load_products(Path(folder)/'catalog.sqlite')[0]
            result = render_campaign(product, *campaign_copy(product), Path(folder))
            photo = packshot_layer(product['images'][0]['path'])
            for kind, info in result.items():
                with self.subTest(format=kind):
                    box = next(e['box'] for e in info['elements'] if e['kind']=='product')
                    left, top, right, bottom = [round(value) for value in box]
                    expected = photo.resize((right-left,bottom-top),Image.Resampling.LANCZOS)
                    with Image.open(info['path']) as image:
                        actual = image.crop((left,top,right,bottom)).convert('RGB')
                    opaque = expected.getchannel('A').point(lambda value: 255 if value==255 else 0)
                    difference = ImageChops.difference(actual,expected.convert('RGB'))
                    difference.paste((0,0,0), mask=ImageChops.invert(opaque))
                    self.assertIsNone(difference.getbbox())

    def test_white_banner_has_one_pixel_border(self):
        with tempfile.TemporaryDirectory() as folder:
            product = load_products(Path(folder)/'catalog.sqlite')[0]
            white = Path(folder)/'white.png'
            Image.new('RGB',(1536,1024),'white').save(white)
            target = Path(folder)/'out';target.mkdir()
            with patch('campaign.BACKGROUND_PATH', white):
                result = render_campaign(product, *campaign_copy(product), target)
            with Image.open(result['banner']['path']) as image:
                self.assertEqual(image.getpixel((0,100)), (70,70,70))
                self.assertEqual(image.getpixel((1,100)), (255,255,255))

    def test_failure_preserves_prior_campaign_and_exports_no_partial_set(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)/'out';output.mkdir()
            existing = output/'previous.png';existing.write_bytes(b'preserve')
            args = Namespace(database=Path(folder)/'db.sqlite', output=output, product=None, font=None,
                             headline='Una headline con troppe parole', cta=None)
            news = [{'title':'Glow skincare trend'}]
            with patch('agent.search_news', return_value=news):
                with self.assertRaisesRegex(ValueError, 'massimo 4 parole'):
                    run(args)
            self.assertEqual(list(output.iterdir()), [existing])
            self.assertEqual(existing.read_bytes(), b'preserve')
            args.headline = None
            with patch('agent.search_news', return_value=news), patch('campaign.LOGO_PATH', Path(folder)/'missing.png'):
                with self.assertRaisesRegex(RuntimeError, 'Asset grafico non trovato'):
                    run(args)
            self.assertEqual(list(output.iterdir()), [existing])
            with sqlite3.connect(args.database) as db:
                self.assertEqual(db.execute('SELECT COUNT(*) FROM generations').fetchone()[0], 0)
            def partial_export(*values):
                (values[3]/'feed.png').write_bytes(b'partial')
                raise OSError('Errore di esportazione del secondo formato')
            with patch('agent.search_news', return_value=news), patch('agent.render_campaign', side_effect=partial_export):
                with self.assertRaisesRegex(OSError, 'secondo formato'):
                    run(args)
            self.assertEqual(list(output.iterdir()), [existing])

    def test_network_failure_exports_nothing(self):
        with tempfile.TemporaryDirectory() as folder:
            args = Namespace(database=Path(folder)/'db.sqlite', output=Path(folder)/'out', product=None, font=None)
            with patch('agent.search_news', side_effect=RuntimeError('blocked')):
                with self.assertRaisesRegex(RuntimeError, 'blocked'):
                    run(args)
            self.assertFalse(args.output.exists())

    def test_each_launch_searches_and_exports_three_images_and_powerpoint(self):
        with tempfile.TemporaryDirectory() as folder:
            args = Namespace(database=Path(folder)/'db.sqlite', output=Path(folder)/'out', product='Contour', font=None,
                             headline=None, cta=None)
            news = [{'title':'Skin barrier trend','url':'https://example.com','published_at':'2026-10-07T10:00:00+00:00'}]
            with patch('agent.search_news', return_value=news) as search:
                first = run(args)
                second = run(args)
            self.assertEqual(search.call_count, 2)
            self.assertNotEqual(first, second)
            folders = list(args.output.iterdir())
            self.assertEqual(len(folders), 2)
            for target in folders:
                self.assertEqual({p.name for p in target.iterdir()},
                                 {'feed.png','story.png','banner.png','presentazione.pptx'})
                self.assertEqual(len(Presentation(target/'presentazione.pptx').slides), 3)
            with sqlite3.connect(args.database) as db:
                rows = db.execute('SELECT research_json FROM generations').fetchall()
                self.assertEqual(len(rows),2)
                for row in rows:
                    report = json.loads(row[0])
                    self.assertEqual(set(report['graphics']), set(FORMATS))
                    self.assertEqual(report['headline'], 'Leviga le rughe')
                    self.assertIn('Leviga rughe e linee sottili del contorno occhi.',
                                  report['presentation']['caption'])
                    self.assertIn('#ContornoOcchi', report['presentation']['hashtags'])
                    self.assertEqual(report['presentation']['slides'], 3)

    def test_powerpoint_contains_product_dated_sources_and_original_feed(self):
        report = {'window_start':'2026-09-30T12:00:00+00:00',
                  'created_at':'2026-10-07T12:00:00+00:00',
                  'headline':'Un incarnato luminoso', 'cta':'Scopri il prodotto',
                  'source_claim':'Un incarnato luminoso, dalla coprenza naturale.',
                  'news':[
                      {'title':'Natural glow skincare trend', 'url':'https://example.com/glow',
                       'publisher':'Beauty Journal', 'published_at':'2026-10-07T10:00:00+00:00'},
                      {'title':'Skin barrier and hydration', 'url':'https://example.com/barrier',
                       'publisher':'Skin Journal', 'published_at':'2026-10-06T10:00:00+00:00'},
                      {'title':'Skin longevity news', 'url':'https://example.com/renew',
                       'publisher':'Care Journal', 'published_at':'2026-10-05T10:00:00+00:00'},
                      {'title':'Old glow news', 'url':'https://example.com/old',
                       'published_at':'2026-09-23T10:00:00+00:00'},
                      {'title':'No date', 'url':'https://example.com/no-date'},
                      {'title':'George returns home from Eton', 'url':'https://example.com/off-topic',
                       'published_at':'2026-10-07T11:00:00+00:00'}]}
        with tempfile.TemporaryDirectory() as folder:
            product = load_products(Path(folder)/'db.sqlite')[0]
            feed = Path(folder)/'feed.png'
            Image.new('RGB', FORMATS['feed'], (156,120,90)).save(feed)
            for platform in ('instagram','facebook'):
                with self.subTest(platform=platform):
                    result = create_presentation(product, report, feed, Path(folder)/(platform+'.pptx'), platform)
                    deck = Presentation(result['path'])
                    self.assertEqual(len(deck.slides),3)
                    text = ['\n'.join(shape.text for shape in slide.shapes if shape.has_text_frame)
                            for slide in deck.slides]
                    self.assertIn(product['name'],text[0])
                    self.assertIn('30/09/2026 — 07/10/2026',text[1])
                    self.assertNotIn('Old glow news',text[1])
                    self.assertNotIn('No date',text[1])
                    self.assertNotIn('George returns home',text[1])
                    self.assertEqual(len(result['trends']),3)
                    for article in report['news'][:3]:
                        self.assertIn(article['title'],text[1])
                        links = [run.hyperlink.address for shape in deck.slides[1].shapes if shape.has_text_frame
                                 for paragraph in shape.text_frame.paragraphs for run in paragraph.runs]
                        self.assertIn(article['url'],links)
                    self.assertIn(result['caption'],text[2])
                    self.assertIn(' '.join(result['hashtags']),text[2])
                    self.assertIn(platform.title(),text[2])
                    picture = next(shape for shape in deck.slides[2].shapes
                                   if shape.shape_type==MSO_SHAPE_TYPE.PICTURE and shape.image.blob==feed.read_bytes())
                    self.assertAlmostEqual(picture.width/picture.height,4/5,places=5)
                    self.assertEqual((picture.crop_left,picture.crop_top,picture.crop_right,picture.crop_bottom),
                                     (0,0,0,0))
                    for slide in deck.slides:
                        for shape in slide.shapes:
                            self.assertGreaterEqual(shape.left,0)
                            self.assertGreaterEqual(shape.top,0)
                            self.assertLessEqual(shape.left+shape.width,deck.slide_width)
                            self.assertLessEqual(shape.top+shape.height,deck.slide_height)
            report['news'] = report['news'][3:]
            with self.assertRaisesRegex(ValueError,'Nessuna fonte datata'):
                weekly_highlights(report)

    def test_powerpoint_failure_removes_all_partial_exports(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)/'out';output.mkdir()
            previous = output/'previous.pptx';previous.write_bytes(b'keep')
            args = Namespace(database=Path(folder)/'db.sqlite',output=output,
                             product='CC Gel',font=None,headline=None,cta=None)
            def fake_graphics(product, headline, cta, directory, font):
                result = {}
                for kind,size in FORMATS.items():
                    path = directory/(kind+'.png');Image.new('RGB',size).save(path)
                    result[kind] = {'path':path,'size':size}
                return result
            def fail_presentation(product,report,feed,destination,platform):
                destination.write_bytes(b'partial deck')
                raise OSError('PowerPoint non esportato')
            with patch('agent.search_news',return_value=[{'title':'Glow trend'}]), \
                    patch('agent.render_campaign',side_effect=fake_graphics), \
                    patch('agent.create_presentation',side_effect=fail_presentation):
                with self.assertRaisesRegex(OSError,'PowerPoint non esportato'):
                    run(args)
            self.assertEqual(list(output.iterdir()),[previous])
            self.assertEqual(previous.read_bytes(),b'keep')
            with sqlite3.connect(args.database) as db:
                self.assertEqual(db.execute('SELECT COUNT(*) FROM generations').fetchone()[0],0)
