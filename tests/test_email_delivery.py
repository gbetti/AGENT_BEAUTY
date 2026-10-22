import base64
from email import policy
from email.message import EmailMessage
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError

from email_delivery import (DeliveryError, FILES, OutlookClient, delivery_intent,
                            load_delivery, prepare_delivery, send_delivery, status_rows)


class FakeOutlook:
    def __init__(self):
        self.calls = []
        self.drafts = {}
        self.fail_send = False
        self.fail_attachment = False
        self.account = 'account-1'

    def profile(self):
        return {'id': self.account, 'email': 'sender@example.com'}

    def request(self, method, path, body=None):
        self.calls.append((method, path, body))
        if method == 'GET':
            return {'isDraft': False, 'sentDateTime': '2026-10-22T12:00:00Z'}
        if path == '/me/messages':
            identifier = 'message-'+str(len(self.drafts)+1)
            self.drafts[identifier] = body
            return {'id': identifier}
        if path.endswith('/attachments'):
            if self.fail_attachment:
                raise DeliveryError('Attachment unavailable')
            return {'id': 'attachment'}
        if self.fail_send:
            raise DeliveryError('Timeout after send')
        return {'accepted': True}


class EmailDeliveryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        private_policy = patch('email_delivery.LOCAL_POLICY', self.root/'private-policy.json')
        private_policy.start()
        self.addCleanup(private_policy.stop)
        self.campaign = self.root/'campaign'
        self.output = self.root/'delivery'
        self.state = self.root/'state.sqlite'
        self.review = {'generation_id': 'generation-1', 'quality': {
            'technical_checks': 'passed', 'visual_review': 'passed', 'reviewed_sha256': {}}}
        for language in ('fr', 'it'):
            folder = self.campaign/language
            folder.mkdir(parents=True)
            for name in FILES:
                (folder/name).write_bytes((language+name).encode())
            message = EmailMessage(policy=policy.SMTP)
            message['From'] = 'IOMA <contact@ioma-paris.com>'
            message['Subject'] = 'Un regard soigné' if language == 'fr' else 'Uno sguardo curato'
            message['X-Unsent'] = '1'
            message.set_content('Campaign text')
            message.add_alternative('<p>Campaign</p><img src="cid:campaign-feed"><img src="cid:ioma-logo">', subtype='html')
            html = message.get_payload()[-1]
            for name, cid in [('feed.png', 'campaign-feed'), ('email-logo.png', 'ioma-logo')]:
                html.add_related((folder/name).read_bytes(), maintype='image', subtype='png', cid=f'<{cid}>')
            (folder/'email.eml').write_bytes(message.as_bytes())
            for name in FILES:
                self.review['quality']['reviewed_sha256'][language+'/'+name] = hashlib.sha256((folder/name).read_bytes()).hexdigest()
        self.client = FakeOutlook()

    def prepare(self):
        return prepare_delivery(self.campaign, self.review, self.output)

    def test_prepares_both_languages_without_sending_or_changing_originals(self):
        before = {str(p): p.read_bytes() for p in self.campaign.glob('*/*')}
        manifest = self.prepare()
        data = load_delivery(manifest)
        self.assertEqual([p['recipient'] for p in data['packets']], ['gb77ita@gmail.com']*2)
        self.assertEqual(data['status'], 'prepared_not_sent')
        self.assertEqual(len(data['packets'][0]['files']), 7)
        self.assertEqual(prepare_delivery(self.campaign, self.review, self.output), manifest)
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.campaign.glob('*/*')})
        self.assertFalse(self.state.exists())
        self.assertTrue(delivery_intent()['send_after_visual_review'])

    def test_blocks_pending_review_and_modified_or_large_files_before_any_send(self):
        self.review['quality']['visual_review'] = 'pending'
        with self.assertRaises(DeliveryError):
            self.prepare()
        self.review['quality']['visual_review'] = 'passed'
        (self.campaign/'it/story.png').write_bytes(b'changed')
        with self.assertRaisesRegex(DeliveryError, 'cambiato'):
            self.prepare()
        huge = b'x'*3_000_000
        (self.campaign/'it/story.png').write_bytes(huge)
        self.review['quality']['reviewed_sha256']['it/story.png'] = hashlib.sha256(huge).hexdigest()
        with self.assertRaisesRegex(DeliveryError, '3 MB'):
            send_delivery(self.prepare(), self.state, self.client)
        self.assertEqual(self.client.calls, [])

    def test_modified_second_language_prevents_even_first_language_send(self):
        path = self.prepare()
        (self.campaign/'it/feed.png').write_bytes(b'changed')
        with self.assertRaises(DeliveryError):
            send_delivery(path, self.state, self.client)
        self.assertEqual(self.client.calls, [])

    def test_changed_recipient_is_rejected(self):
        path = self.prepare()
        data = json.loads(path.read_text())
        data['packets'][0]['recipient'] = 'someone@example.com'
        path.write_text(json.dumps(data))
        with self.assertRaisesRegex(DeliveryError, 'Destinatario'):
            send_delivery(path, self.state, self.client)
        self.assertEqual(self.client.calls, [])

    def test_send_uses_verified_bytes_even_if_source_changes_during_connection(self):
        path = self.prepare()
        original = (self.campaign/'it/presentazione.pptx').read_bytes()
        def profile():
            (self.campaign/'it/presentazione.pptx').write_bytes(b'unreviewed replacement')
            return {'id': 'account-1', 'email': 'sender@example.com'}
        self.client.profile = profile
        send_delivery(path, self.state, self.client)
        presentations = [body for _, endpoint, body in self.client.calls
                         if endpoint.endswith('/attachments') and body['name'] == 'presentazione.pptx']
        self.assertEqual(base64.b64decode(presentations[1]['contentBytes']), original)

    def test_sends_two_messages_with_exact_assets_authenticated_sender_and_no_duplicate(self):
        path = self.prepare()
        first = send_delivery(path, self.state, self.client)
        self.assertEqual([m['status'] for m in first['messages']], ['accepted', 'accepted'])
        self.assertEqual(len(self.client.drafts), 2)
        for body in self.client.drafts.values():
            self.assertNotIn('from', body)
            self.assertEqual(body['toRecipients'][0]['emailAddress']['address'], 'gb77ita@gmail.com')
            self.assertIn('cid:campaign-feed', body['body']['content'])
        attachments = [body for _, endpoint, body in self.client.calls if endpoint.endswith('/attachments')]
        self.assertEqual(len(attachments), 14)
        for index, language in enumerate(('fr', 'it')):
            for item in attachments[index*7:(index+1)*7]:
                self.assertEqual(base64.b64decode(item['contentBytes']), (self.campaign/language/item['name']).read_bytes())
                self.assertEqual(item.get('isInline', False), item['name'] in ('feed.png', 'email-logo.png'))
        second = send_delivery(path, self.state, self.client)
        self.assertEqual([m['status'] for m in second['messages']], ['sent', 'sent'])
        send_delivery(path, self.state, self.client)
        self.assertEqual(sum(p.endswith('/send') for _, p, _ in self.client.calls), 2)

    def test_uncertain_send_is_reconciled_without_repeating_it(self):
        path = self.prepare()
        self.client.fail_send = True
        with self.assertRaises(DeliveryError):
            send_delivery(path, self.state, self.client)
        self.assertEqual(status_rows(self.state)[0]['status'], 'uncertain')
        self.client.fail_send = False
        send_delivery(path, self.state, self.client)
        self.assertEqual(sum(p.endswith('/send') for _, p, _ in self.client.calls), 2)
        self.assertEqual(status_rows(self.state)[0]['status'], 'sent')

    def test_uncertain_draft_blocks_resend_and_second_language(self):
        path = self.prepare()
        self.client.fail_send = True
        with self.assertRaises(DeliveryError):
            send_delivery(path, self.state, self.client)
        self.client.request = Mock(return_value={'isDraft': True})
        with self.assertRaisesRegex(DeliveryError, 'nessun reinvio'):
            send_delivery(path, self.state, self.client)
        self.assertEqual(self.client.request.call_count, 1)

    def test_attachment_failure_does_not_send_partial_message(self):
        path = self.prepare()
        self.client.fail_attachment = True
        with self.assertRaises(DeliveryError):
            send_delivery(path, self.state, self.client)
        self.assertFalse(any(p.endswith('/send') for _, p, _ in self.client.calls))
        self.assertEqual(status_rows(self.state)[0]['status'], 'incomplete_draft')

    def test_missing_credentials_do_not_create_a_send_record(self):
        with patch.dict('os.environ', {}, clear=True), self.assertRaisesRegex(DeliveryError, 'Mittente non collegato'):
            send_delivery(self.prepare(), self.state)
        self.assertFalse(self.state.exists())

    def test_different_authenticated_account_cannot_reuse_delivery(self):
        path = self.prepare()
        send_delivery(path, self.state, self.client)
        self.client.account = 'account-2'
        with self.assertRaisesRegex(DeliveryError, 'altro account'):
            send_delivery(path, self.state, self.client)

    def test_graph_client_checks_sender_and_sanitizes_provider_errors(self):
        client = OutlookClient('token-secret', 'sender@example.com', opener=Mock())
        with patch.object(client, 'request', return_value={'id': '1', 'mail': 'other@example.com'}):
            with self.assertRaisesRegex(DeliveryError, 'mittente autenticato'):
                client.profile()
        for error in [HTTPError('url', 401, 'token-secret', {}, io.BytesIO(b'token-secret')),
                      URLError('token-secret')]:
            client.opener.open.side_effect = error
            with self.assertRaises(DeliveryError) as caught:
                client.request('GET', '/me')
            self.assertNotIn('token-secret', str(caught.exception))

    def test_graph_client_uses_immutable_ids_and_acceptance_requires_202(self):
        response = Mock(status=202)
        response.read.return_value = b''
        opener = Mock()
        opener.open.return_value.__enter__ = Mock(return_value=response)
        opener.open.return_value.__exit__ = Mock(return_value=False)
        client = OutlookClient('token-secret', 'sender@example.com', opener=opener)
        self.assertEqual(client.request('POST', '/me/messages/1/send'), {'accepted': True})
        request = opener.open.call_args.args[0]
        self.assertEqual(request.get_header('Prefer'), 'IdType="ImmutableId"')
        self.assertTrue(request.full_url.startswith('https://graph.microsoft.com/'))
        response.status = 204
        with self.assertRaises(DeliveryError):
            client.request('POST', '/me/messages/1/send')


if __name__ == '__main__':
    unittest.main()
