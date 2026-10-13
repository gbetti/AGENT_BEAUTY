from argparse import Namespace
from email import policy
from email.parser import BytesParser
from pathlib import Path
import hashlib
import json
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from PIL import Image

from agent import load_products, run
from newsletter import campaign_email_copy, create_email
from test_agent import weekly_fixture, ingredient_fixture, trends_fixture


class NewsletterTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.products = load_products(self.root/'db.sqlite')
        self.product = next(p for p in self.products if 'Sublime' in p['name'])
        self.report = {'created_at':'2026-10-12T10:00:00+00:00',
                       'headline':'Sublime, tout simplement.'}
        self.feed = self.root/'feed.png'
        Image.new('RGB',(108,135),(209,197,180)).save(self.feed)

    def test_draft_embeds_exact_feed_and_preserves_french_text(self):
        result = create_email(self.product,self.report,self.feed,self.root)
        message = BytesParser(policy=policy.default).parsebytes(result['eml_path'].read_bytes())
        self.assertEqual(message['Subject'],'Et si votre routine devenait sublime ?')
        self.assertEqual(message['X-Unsent'],'1')
        images = {str(p['Content-ID']):p.get_payload(decode=True)
                  for p in message.walk() if p.get_content_maintype()=='image'}
        self.assertEqual(images['<campaign-feed>'],self.feed.read_bytes())
        self.assertEqual(hashlib.sha256(images['<campaign-feed>']).hexdigest(),result['image_sha256'])
        html = message.get_body(preferencelist=('html',)).get_content()
        self.assertIn('cid:campaign-feed',html)
        self.assertIn('Crème Sublime Revitalisante',html)
        self.assertIn('barrière cutanée',html)
        self.assertNotIn('{% unsubscribe_link %}',html)
        self.assertNotIn('data:image',html)
        self.assertIsNone(message['To'])
        self.assertFalse(result['sent'])

    def test_html_uses_same_asset_and_esp_tag_with_mobile_and_outlook_layouts(self):
        result=create_email(self.product,self.report,self.feed,self.root,
                            assets_url='https://cdn.example.com/campaign')
        html=result['html_path'].read_text()
        self.assertIn('src="https://cdn.example.com/campaign/feed.png"',html)
        self.assertIn('href="{% unsubscribe_link %}"',html)
        self.assertIn('role="presentation"',html)
        self.assertIn('max-width:620px',html)
        self.assertIn('<v:roundrect',html)
        self.assertIn('utm_medium=email',html)
        self.assertNotIn('<script',html)
        self.assertNotIn('klclick',html)
        self.assertEqual(result['html_images'],'hosted')
        self.assertEqual(result['image_path'],self.feed)

    def test_all_products_have_brief_copy_and_rotate_subject_on_next_run(self):
        for product in self.products:
            for language in ('fr','it'):
                with self.subTest(product=product['name'],language=language):
                    first=campaign_email_copy(product,self.report,language)
                    history=[{'product_id':product['id'],'email':first}]
                    second=campaign_email_copy(product,self.report,language,history)
                    self.assertNotEqual(first['subject'],second['subject'])
                    self.assertLessEqual(len(first['subject']),55)
                    self.assertLessEqual(len(first['preheader']),100)
                    self.assertLessEqual(len(' '.join(first[k] for k in ('lead','body','closing')).split()),70)
                    self.assertTrue(first['product_url'].startswith('https://ioma-paris.com/products/'))
                    utm=parse_qs(urlsplit(first['product_url']).query)
                    self.assertTrue(utm['utm_campaign'][0].startswith(product['id'].rsplit(':',1)[-1]+'-'))
        unknown={**self.product,'id':'urn:unknown'}
        with self.assertRaisesRegex(ValueError,'nessun beneficio inventato'):
            campaign_email_copy(unknown,self.report)
        changed={**self.product,'data':{'editorial':{'claim_it':'Unverified new claim'}}}
        with self.assertRaisesRegex(ValueError,'claim del catalogo'):
            campaign_email_copy(changed,self.report)

    def test_rejects_header_injection_foreign_campaign_asset_and_unsafe_urls(self):
        for subject in ('Objet\r\nBcc: attacker@example.com','x'*56,' '):
            with self.subTest(subject=subject),self.assertRaises(ValueError):
                create_email(self.product,self.report,self.feed,self.root,subject=subject)
        other=self.root/'other.png';other.write_bytes(self.feed.read_bytes())
        with self.assertRaisesRegex(ValueError,'stessa campagna'):
            create_email(self.product,self.report,other,self.root)
        for url in ('javascript:alert(1)','https://example.com/a?token=one','https://user:pass@example.com/a'):
            with self.subTest(url=url),self.assertRaises(ValueError):
                create_email(self.product,self.report,self.feed,self.root,assets_url=url)

    def test_email_failure_does_not_publish_a_partial_campaign(self):
        output=self.root/'out';output.mkdir()
        previous=output/'previous.eml';previous.write_bytes(b'keep')
        args=Namespace(database=self.root/'db.sqlite',output=output,product='Sublime',font=None)
        def graphics(product,copy,directory,scene):
            result={}
            for kind in ('feed','story','banner'):
                path=directory/(kind+'.png');Image.new('RGB',(108,135)).save(path)
                result[kind]={'path':path,'size':[108,135]}
            return result
        def presentation(product,report,images,destination,platform):
            destination.write_bytes(b'deck')
            return {'path':destination}
        def failed_email(product,report,feed,directory,**options):
            (directory/'email.html').write_text('partial')
            raise OSError('Email non esportata')
        with patch('agents.trends.search_news',return_value=[{'title':'Beauty hydration trend'}]), \
                patch('agents.trends.load_brief',return_value=weekly_fixture()), \
                patch('agents.assets.select_ingredients',return_value=ingredient_fixture()), \
                patch('agents.keywords.research_trends',return_value=trends_fixture()), \
                patch('agents.assets.render_campaign',side_effect=graphics), \
                patch('agents.assets.create_presentation',side_effect=presentation), \
                patch('agents.assets.create_email',side_effect=failed_email):
            with self.assertRaisesRegex(RuntimeError,'Email non esportata'):
                run(args)
        self.assertEqual(list(output.iterdir()),[previous])
        self.assertEqual(previous.read_bytes(),b'keep')
        with sqlite3.connect(args.database) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM generations').fetchone()[0],0)
