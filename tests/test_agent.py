from argparse import Namespace
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image, ImageChops
from agent import load_products, parse_news, run
from campaign import FORMATS, packshot_layer
from editorial import BRIEFS, LANGUAGES, campaign_plan
from studio import render_campaign, validate

ROOT=Path(__file__).resolve().parents[1]

class AgentTests(unittest.TestCase):
    def test_news_filters_old_future_invalid_and_duplicate(self):
        xml=b'''<rss><channel>
        <item><title>Glow skincare</title><link>https://example.com/one</link><pubDate>Wed, 07 Oct 2026 10:00:00 GMT</pubDate></item>
        <item><title>Glow skincare</title><link>https://example.com/one</link><pubDate>Wed, 07 Oct 2026 10:00:00 GMT</pubDate></item>
        <item><title>Old glow</title><link>https://example.com/old</link><pubDate>Wed, 23 Sep 2026 10:00:00 GMT</pubDate></item>
        <item><title>Future glow</title><link>https://example.com/future</link><pubDate>Wed, 14 Oct 2026 10:00:00 GMT</pubDate></item>
        <item><title>George returns home</title><link>https://example.com/off-topic</link><pubDate>Wed, 07 Oct 2026 11:00:00 GMT</pubDate></item>
        </channel></rss>'''
        self.assertEqual(len(parse_news(xml,datetime(2026,10,7,12,tzinfo=timezone.utc))),1)

    def test_original_assets_are_unchanged_and_high_resolution(self):
        for asset in json.loads((ROOT/'assets/products/manifest.json').read_text()):
            path=ROOT/asset['path']
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),asset['sha256'])
            with Image.open(path) as im: self.assertEqual(im.size,(2000,2000))

    def test_every_product_copy_and_scene_fits_all_formats_without_collisions(self):
        scenes=json.loads((ROOT/'assets/backgrounds/editorial-scenes.json').read_text())
        with tempfile.TemporaryDirectory() as folder:
            products=load_products(Path(folder)/'db.sqlite')
            for product in products:
                photo=packshot_layer(product['images'][0]['path'])
                brief=BRIEFS[product['id'].split(':')[-1]]
                plan=campaign_plan(product,[])
                # Every copy in both languages on both light/background variants.
                for variant in brief['headlines']:
                    for language in LANGUAGES:
                        for scene in scenes:
                            with self.subTest(product=product['name'],headline=variant[language],scene=scene['id']):
                                copy={**plan['copies'][language],'headline':variant[language]}
                                with patch('studio.packshot_layer',return_value=photo):
                                    outputs=render_campaign(product,copy,Path(folder),scene)
                                self.assertEqual(set(outputs),set(FORMATS))
                                for kind,info in outputs.items():
                                    with Image.open(info['path']) as im: self.assertEqual(im.size,FORMATS[kind])
                                    validate(kind,info['elements'])
                                    self.assertLess(info['text_area_ratio'],.20)
                                    logo=next(e['box'] for e in info['elements'] if e['kind']=='logo')
                                    self.assertAlmostEqual((logo[0]+logo[2])/2,FORMATS[kind][0]/2)
                                    for e in info['elements']:
                                        if 'text' in e: self.assertGreaterEqual(e['contrast_ratio'],4.5)
                                    if kind!='banner': self.assertNotIn('cta',[e['kind'] for e in info['elements']])

    def test_packshot_label_pixels_are_preserved_at_final_size(self):
        with tempfile.TemporaryDirectory() as folder:
            product=load_products(Path(folder)/'db.sqlite')[-1]
            plan=campaign_plan(product,[])
            photo=packshot_layer(product['images'][0]['path'])
            with patch('studio.packshot_layer',return_value=photo):
                outputs=render_campaign(product,plan['copies']['fr'],Path(folder),plan['scene'])
            for info in outputs.values():
                box=next(e['box'] for e in info['elements'] if e['kind']=='product')
                l,t,r,b=box
                expected=photo.resize((r-l,b-t),Image.Resampling.LANCZOS)
                with Image.open(info['path']) as im: actual=im.crop(box)
                opaque=expected.getchannel('A').point(lambda v:255 if v==255 else 0)
                delta=ImageChops.difference(actual,expected.convert('RGB'))
                delta.paste((0,0,0),mask=ImageChops.invert(opaque))
                self.assertIsNone(delta.getbbox())

    def test_changed_claim_and_missing_brief_fail_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            product=load_products(Path(folder)/'db.sqlite')[0]
            product['data']['editorial']['claim_it']='Unverified new claim'
            with self.assertRaisesRegex(ValueError,'claim'): campaign_plan(product,[])
            product['id']='unknown'
            with self.assertRaisesRegex(ValueError,'brief'): campaign_plan(product,[])

    def test_consecutive_campaigns_change_scene_and_copy(self):
        with tempfile.TemporaryDirectory() as folder:
            product=load_products(Path(folder)/'db.sqlite')[-1]
            first=campaign_plan(product,[])
            second=campaign_plan(product,[{'product_id':product['id'],'creative':first}])
            self.assertNotEqual(first['variant'],second['variant'])
            self.assertNotEqual(first['scene']['id'],second['scene']['id'])

    def test_exactly_six_outputs_and_fresh_research_each_run(self):
        with tempfile.TemporaryDirectory() as folder:
            args=Namespace(database=Path(folder)/'db.sqlite',output=Path(folder)/'out',product='Sublime')
            news=[{'title':'Skin barrier skincare trend','published_at':datetime.now(timezone.utc).isoformat(),'url':'https://example.com/skin'}]
            with patch('agent.search_news',return_value=news) as search:
                first=run(args);second=run(args)
            self.assertEqual(search.call_count,2)
            self.assertNotEqual(first,second)
            for d in args.output.iterdir():
                self.assertEqual({p.name for p in d.iterdir()},{'fr','it'})
                self.assertEqual({str(p.relative_to(d)) for p in d.rglob('*') if p.is_file()},
                                 {lang+'/'+kind+'.png' for lang in LANGUAGES for kind in FORMATS})
            with sqlite3.connect(args.database) as db:
                rows=db.execute('SELECT research_json FROM generations').fetchall()
            self.assertEqual(len(rows),2)
            for raw, in rows:
                report=json.loads(raw)
                self.assertEqual(set(report['localizations']),{'fr','it'})
                self.assertEqual(report['quality']['visual_review'],'pending')
                self.assertEqual(report['quality']['publication_status'],'not_published')

    def test_second_language_failure_rolls_back_all_new_files_and_history(self):
        with tempfile.TemporaryDirectory() as folder:
            args=Namespace(database=Path(folder)/'db.sqlite',output=Path(folder)/'out',product='Sublime')
            args.output.mkdir();prior=args.output/'prior.png';prior.write_bytes(b'keep')
            def partial(product,copy,directory,scene):
                (directory/'feed.png').write_bytes(b'partial')
                if copy['language']=='it': raise ValueError('Italian failure')
                return {'feed':{'path':directory/'feed.png'}}
            with patch('agent.search_news',return_value=[{'title':'Skincare hydration'}]),patch('agent.render_campaign',side_effect=partial):
                with self.assertRaisesRegex(ValueError,'Italian failure'): run(args)
            self.assertEqual(list(args.output.iterdir()),[prior])
            with sqlite3.connect(args.database) as db:
                self.assertEqual(db.execute('SELECT COUNT(*) FROM generations').fetchone()[0],0)

    def test_network_failure_exports_nothing(self):
        with tempfile.TemporaryDirectory() as folder:
            args=Namespace(database=Path(folder)/'db.sqlite',output=Path(folder)/'out',product=None)
            with patch('agent.search_news',side_effect=RuntimeError('Network unavailable')):
                with self.assertRaises(RuntimeError): run(args)
            self.assertFalse(args.output.exists())

    def test_overflow_is_not_silently_reduced(self):
        from studio import draw_text
        with self.assertRaisesRegex(ValueError,'troppo largo'):
            draw_text(Image.new('RGB',(300,250),'white'),'A title that cannot possibly fit',20,70,130,33,'headline',serif=True)
