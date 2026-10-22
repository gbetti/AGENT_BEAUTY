import base64
import hashlib
import json
import unittest

import test_email_delivery
from email_delivery import DeliveryError, status_rows
from gmail_delivery import build_requests, export_requests, record_result, reserve_request


class GmailDeliveryTests(unittest.TestCase):
    setUp = test_email_delivery.EmailDeliveryTests.setUp
    prepare = test_email_delivery.EmailDeliveryTests.prepare

    def test_exact_mime_originals_and_authenticated_sender_recipient(self):
        requests = build_requests(self.prepare(), 'gb77ita@gmail.com')
        for entry in requests:
            request = entry['request']
            self.assertEqual(request['to'], 'gb77ita@gmail.com')
            self.assertEqual(request['from_address'], request['to'])
            self.assertNotIn('cc', request)
            self.assertNotIn('bcc', request)
            root = request['payload']['parts']
            html, *images = root[0]['parts']
            self.assertIn('cid:campaign-feed', html['body']['content'])
            self.assertEqual({p['content_id'] for p in images}, {'campaign-feed', 'ioma-logo'})
            files = images+root[1:]
            self.assertEqual(len(files), 7)
            for part in files:
                self.assertEqual(base64.urlsafe_b64decode(part['body']['base64_url_content']),
                                 (self.campaign/entry['language']/part['filename']).read_bytes())

    def test_wrong_gmail_sender_is_rejected(self):
        with self.assertRaises(DeliveryError):
            build_requests(self.prepare(), 'other@gmail.com')

    def test_gmail_accepts_assets_above_the_outlook_small_attachment_limit(self):
        raw = b'a'*4_000_000
        (self.campaign/'it/story.png').write_bytes(raw)
        self.review['quality']['reviewed_sha256']['it/story.png'] = hashlib.sha256(raw).hexdigest()
        requests = build_requests(self.prepare(), 'gb77ita@gmail.com')
        part = next(p for p in requests[1]['request']['payload']['parts'] if p.get('filename') == 'story.png')
        self.assertEqual(base64.urlsafe_b64decode(part['body']['base64_url_content']), raw)

    def test_reservation_is_durable_and_prevents_a_second_attempt(self):
        export = export_requests(self.prepare(), 'gb77ita@gmail.com')
        attempt = reserve_request(export['requests_path'], 'fr', self.state)
        self.assertEqual(status_rows(self.state)[0]['status'], 'connector_sending')
        with self.assertRaises(DeliveryError):
            reserve_request(export['requests_path'], 'fr', self.state)
        result = record_result(attempt['packet_id'], {'id': 'gmail-1', 'thread_id': 'thread-1', 'label_ids': ['SENT']}, self.state)
        self.assertEqual(result['status'], 'sent')
        with self.assertRaises(DeliveryError):
            reserve_request(export['requests_path'], 'fr', self.state)

    def test_modified_payload_or_source_never_reserves(self):
        export = export_requests(self.prepare(), 'gb77ita@gmail.com')
        path = self.output/'fr-gmail-request.json'
        value = json.loads(path.read_text())
        value['to'] = 'gbetti@live.it'
        path.write_text(json.dumps(value))
        with self.assertRaises(DeliveryError):
            reserve_request(export['requests_path'], 'fr', self.state)
        self.assertEqual(status_rows(self.state), [])
        export_requests(self.prepare(), 'gb77ita@gmail.com')
        (self.campaign/'it/feed.png').write_bytes(b'changed')
        with self.assertRaises(DeliveryError):
            reserve_request(export['requests_path'], 'fr', self.state)

    def test_uncertain_response_is_not_success_and_different_receipt_is_rejected(self):
        export = export_requests(self.prepare(), 'gb77ita@gmail.com')
        attempt = reserve_request(export['requests_path'], 'it', self.state)
        for response in ({}, {'id': '1'}, {'id': '1', 'label_ids': ['DRAFT']}):
            with self.assertRaises(DeliveryError):
                record_result(attempt['packet_id'], response, self.state)
        self.assertEqual(status_rows(self.state)[0]['status'], 'connector_sending')
        record_result(attempt['packet_id'], {'id': '1', 'label_ids': ['SENT']}, self.state)
        with self.assertRaises(DeliveryError):
            record_result(attempt['packet_id'], {'id': '2', 'label_ids': ['SENT']}, self.state)
