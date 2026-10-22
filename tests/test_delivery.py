from email import policy
from email.parser import BytesParser
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from catalog import load_products
from delivery import (begin_send, bundle_files, create_manifest,
                      prepare_gmail_request, record_sent)
from newsletter import create_email
from agent import main


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.db = self.root / 'catalog.sqlite'
        product = next(p for p in load_products(self.db) if 'Sublime' in p['name'])
        self.campaign = self.root / 'campaign'
        report = {'created_at': '2026-10-22T14:00:00+00:00', 'headline': 'Sublime'}
        for language in ('fr', 'it'):
            directory = self.campaign / language
            directory.mkdir(parents=True)
            Image.new('RGB', (1080, 1350), '#eee4da').save(directory / 'feed.png')
            Image.new('RGB', (1080, 1920), '#eee4da').save(directory / 'story.png')
            (directory / 'caption.txt').write_text('Caption ' + language, encoding='utf-8')
            create_email(product, report, directory / 'feed.png', directory, language=language)

    def hosted(self, url, timeout=30):
        path = self.campaign / '/'.join(url.split('/')[-2:])
        return io.BytesIO(path.read_bytes())

    def prepare(self):
        create_manifest(self.campaign, 'generation-1')
        with patch('delivery.urlopen', side_effect=self.hosted):
            return prepare_gmail_request(self.campaign, 'https://cdn.example.com/campaign')

    def ledger(self):
        return json.loads((self.campaign / 'delivery.json').read_text())

    def test_missing_story_cannot_be_treated_as_a_finished_post(self):
        (self.campaign / 'it/story.png').unlink()
        with self.assertRaisesRegex(ValueError, 'it/story.png'):
            create_manifest(self.campaign, 'generation-1')
        self.assertFalse((self.campaign / 'delivery.json').exists())

    def test_feed_sized_story_and_different_email_image_are_rejected(self):
        Image.new('RGB', (1080, 1350)).save(self.campaign / 'it/story.png')
        with self.assertRaisesRegex(ValueError, 'Formato non valido'):
            bundle_files(self.campaign)
        Image.new('RGB', (1080, 1920)).save(self.campaign / 'it/story.png')
        Image.new('RGB', (1080, 1350), 'red').save(self.campaign / 'it/feed.png')
        with self.assertRaisesRegex(ValueError, 'PNG originale'):
            bundle_files(self.campaign)

    def test_prepares_one_italian_email_for_authorized_recipient_without_spoofed_sender(self):
        request = self.prepare()
        self.assertEqual(request['to'], 'gb77ita@gmail.com')
        self.assertNotIn('from_address', request)
        original = BytesParser(policy=policy.default).parsebytes(
            (self.campaign / 'it/email.eml').read_bytes())
        self.assertEqual(request['subject'], str(original['Subject']))
        html = request['payload']['body']['content']
        self.assertIn('https://cdn.example.com/campaign/it/feed.png', html)
        self.assertIn('https://cdn.example.com/campaign/it/email-logo.png', html)
        self.assertNotIn('cid:', html)
        self.assertNotIn('{% unsubscribe_link %}', html)
        self.assertEqual(self.ledger()['status'], 'pending_email')
        self.assertFalse(self.ledger()['email']['sent'])

    def test_wrong_hosted_image_does_not_make_email_ready(self):
        create_manifest(self.campaign, 'generation-1')
        with patch('delivery.urlopen', return_value=io.BytesIO(b'wrong image')):
            with self.assertRaisesRegex(ValueError, 'asset pubblico'):
                prepare_gmail_request(self.campaign, 'https://cdn.example.com/campaign')
        self.assertEqual(self.ledger()['email']['status'], 'pending')
        self.assertFalse((self.campaign / 'gmail-request.json').exists())

    def test_detects_changed_recipient_request_or_assets_before_send(self):
        self.prepare()
        path = self.campaign / 'gmail-request.json'
        request = json.loads(path.read_text())
        request['to'] = 'someone-else@example.com'
        path.write_text(json.dumps(request))
        with self.assertRaisesRegex(ValueError, 'richiesta Gmail'):
            begin_send(self.campaign)
        with patch('delivery.urlopen', side_effect=self.hosted):
            prepare_gmail_request(self.campaign, 'https://cdn.example.com/campaign')
        (self.campaign / 'it/caption.txt').write_text('Changed caption')
        with self.assertRaisesRegex(ValueError, 'asset sono cambiati'):
            begin_send(self.campaign)

    def test_duplicate_attempt_is_blocked_even_if_sender_times_out(self):
        request = self.prepare()
        self.assertEqual(begin_send(self.campaign), request)
        with self.assertRaisesRegex(ValueError, 'già tentato'):
            begin_send(self.campaign)
        with self.assertRaisesRegex(ValueError, 'già iniziato'):
            prepare_gmail_request(self.campaign, 'https://cdn.example.com/campaign')
        self.assertEqual(self.ledger()['email']['status'], 'sending')
        self.assertFalse(self.ledger()['email']['sent'])

    def test_only_gmail_sent_receipt_completes_and_persists_delivery(self):
        self.prepare()
        with self.assertRaisesRegex(ValueError, 'Nessun tentativo'):
            record_sent(self.campaign, {'id': '123', 'label_ids': ['SENT']})
        begin_send(self.campaign)
        for receipt in ({}, {'id': 'draft-1', 'label_ids': ['DRAFT']}):
            with self.assertRaisesRegex(ValueError, 'ricevuta reale'):
                record_sent(self.campaign, receipt)
        with sqlite3.connect(self.db) as db:
            db.execute('INSERT INTO generations VALUES(?,?,?,?,?)', (
                'generation-1', '2026-10-22T14:00:00+00:00', 'product', 'feed.png',
                json.dumps({'localizations': {'it': {'email': {'sent': False}}}})))
        receipt = {'id': 'gmail-123', 'thread_id': 'thread-123', 'label_ids': ['SENT']}
        completed = record_sent(self.campaign, receipt, self.db)
        self.assertEqual(completed['status'], 'complete')
        self.assertTrue(completed['email']['sent'])
        with sqlite3.connect(self.db) as db:
            report = json.loads(db.execute('SELECT research_json FROM generations WHERE id=?',
                                           ('generation-1',)).fetchone()[0])
        self.assertTrue(report['localizations']['it']['email']['sent'])
        self.assertEqual(report['delivery']['email']['message_id'], 'gmail-123')
        record_sent(self.campaign, receipt, self.db)  # Idempotent receipt persistence.
        with self.assertRaisesRegex(ValueError, 'già tentato'):
            begin_send(self.campaign)
        with self.assertRaises(FileExistsError):
            create_manifest(self.campaign, 'generation-1')

    def test_concurrent_send_claim_is_rejected(self):
        self.prepare()
        lock = self.campaign / '.delivery.lock'
        lock.touch()
        with self.assertRaisesRegex(RuntimeError, 'altra operazione'):
            begin_send(self.campaign)
        self.assertTrue(lock.exists())

    def test_cli_cannot_report_complete_when_only_assets_were_generated(self):
        with patch('agent.run') as generate, patch('sys.argv', ['agent.py']):
            with self.assertRaises(SystemExit) as result:
                main()
            self.assertEqual(result.exception.code, 2)
            generate.assert_called_once()
        with patch('agent.run') as generate, patch('sys.argv', ['agent.py', '--prepare-only']):
            main()
            generate.assert_called_once()


if __name__ == '__main__':
    unittest.main()
