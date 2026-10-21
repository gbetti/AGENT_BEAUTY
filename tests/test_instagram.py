from contextlib import redirect_stderr, redirect_stdout
from io import BytesIO, StringIO
from email.message import Message
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError

from PIL import Image

from agents.publisher import main
from instagram import (InstagramClient, InstagramError, NoRedirect, load_post,
                       prepare_post, publication_store, publish_post, verify_public_image)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


class Response(BytesIO):
    def __init__(self, raw, content_type='application/json'):
        super().__init__(raw)
        self.headers = Message()
        self.headers['Content-Type'] = content_type


class InstagramTransportTests(unittest.TestCase):
    def test_bearer_stays_in_header_and_profile_is_checked(self):
        opener = Mock()
        opener.open.return_value = Response(json.dumps({'data': [
            {'user_id': '123', 'username': 'gb77ita', 'account_type': 'BUSINESS'}]}).encode())
        client = InstagramClient('secret-token', opener=opener)
        self.assertEqual(client.profile('@gb77ita')['id'], '123')
        req = opener.open.call_args.args[0]
        self.assertEqual(req.get_header('Authorization'), 'Bearer secret-token')
        self.assertNotIn('secret-token', req.full_url)
        self.assertIn('graph.instagram.com/v26.0/me?', req.full_url)
        self.assertIsNone(NoRedirect().redirect_request(req, None, 302, '', {}, 'https://other.test'))

    def test_wrong_profile_and_personal_account_are_rejected(self):
        client = InstagramClient('secret-token')
        for profile in ({'user_id': '123', 'username': 'other', 'account_type': 'BUSINESS'},
                        {'user_id': '123', 'username': 'gb77ita', 'account_type': 'PERSONAL'}):
            with self.subTest(profile=profile), patch.object(client, 'request', return_value=profile):
                with self.assertRaises(InstagramError):
                    client.profile('gb77ita')

    def test_meta_error_does_not_echo_token_or_raw_message(self):
        opener = Mock()
        raw = json.dumps({'error': {'code': 190, 'message': 'secret-token'}}).encode()
        opener.open.side_effect = HTTPError('https://graph.instagram.com', 400, '', {}, BytesIO(raw))
        with self.assertRaises(InstagramError) as error:
            InstagramClient('secret-token', opener=opener).profile('gb77ita')
        self.assertIn('Token scaduto', str(error.exception))
        self.assertNotIn('secret-token', str(error.exception))

    def test_transport_error_is_sanitized_and_write_is_not_retried(self):
        opener = Mock()
        opener.open.side_effect = URLError('could contain secret-token')
        with self.assertRaises(InstagramError) as error:
            InstagramClient('secret-token', opener=opener).request('POST', '123/media', caption='é')
        self.assertNotIn('secret-token', str(error.exception))
        self.assertEqual(opener.open.call_count, 1)

    def test_missing_secret_fails_without_network(self):
        with patch.dict('os.environ', {}, clear=True), patch('instagram.build_opener') as opener:
            with self.assertRaisesRegex(InstagramError, 'INSTAGRAM_ACCESS_TOKEN'):
                InstagramClient.from_environment()
        opener.assert_not_called()


class InstagramPublishingTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root/'feed.png'
        Image.new('RGB', (1080, 1350), '#f4eee6').save(self.source)
        self.source_hash = sha(self.source.read_bytes())
        self.database = self.root/'catalog.sqlite'
        self.report = {'quality': {'technical_checks': 'passed', 'visual_review': 'passed',
                                  'reviewed_sha256': {'fr/feed.png': self.source_hash}},
                       'localizations': {'fr': {'caption': 'Un soin dédié au contour des yeux. #IOMAParis',
                                                'graphics': {'feed': {'path': str(self.source)}}}}}
        with sqlite3.connect(self.database) as db:
            db.execute('CREATE TABLE generations(id TEXT PRIMARY KEY,research_json TEXT)')
            db.execute('INSERT INTO generations VALUES(?,?)', ('generation-1', json.dumps(self.report)))
        self.path = prepare_post(self.database, 'generation-1', 'fr', 'gb77ita', self.root/'prepared')
        self.post = load_post(self.path)
        self.state = self.root/'instagram.sqlite'
        self.client = Mock()
        self.client.profile.return_value = {'id': '123', 'username': 'gb77ita'}
        self.client.request.side_effect = [
            {'id': '456'}, {'status_code': 'FINISHED'}, {'id': '789'},
            {'permalink': 'https://www.instagram.com/p/example/'}]
        self.check_image = Mock()

    def publish(self, **kwargs):
        return publish_post(self.post, 'https://cdn.example.com/feed.jpg', self.state,
                            self.client, check_image=self.check_image, sleep=Mock(), **kwargs)

    def writes(self):
        return [c for c in self.client.request.call_args_list if c.args[0] == 'POST']

    def test_prepare_preserves_png_and_caption_without_network_or_publication(self):
        self.assertEqual(sha(self.source.read_bytes()), self.source_hash)
        self.assertEqual(self.post['caption'], self.report['localizations']['fr']['caption'])
        self.assertEqual(self.post['username'], 'gb77ita')
        with Image.open(self.path.parent/'feed.jpg') as image:
            self.assertEqual(image.size, (1080, 1350))
            self.assertEqual(image.format, 'JPEG')
        self.assertFalse(self.state.exists())
        self.assertFalse(Path(self.post['source_image']).is_absolute())
        with self.assertRaises(FileExistsError):
            prepare_post(self.database, 'generation-1', 'fr', 'gb77ita', self.path.parent)

    def test_prepare_blocks_pending_review_and_changed_source(self):
        for quality in ({'technical_checks': 'passed', 'visual_review': 'pending'},
                        {'technical_checks': 'passed', 'visual_review': 'passed',
                         'reviewed_sha256': {'fr/feed.png': 'incorrect'}}):
            with self.subTest(quality=quality):
                self.report['quality'] = quality
                with sqlite3.connect(self.database) as db:
                    db.execute('UPDATE generations SET research_json=?', (json.dumps(self.report),))
                with self.assertRaises(InstagramError):
                    prepare_post(self.database, 'generation-1', 'fr', 'gb77ita', self.root/'rejected')
                self.assertFalse((self.root/'rejected').exists())

    def test_manifest_changes_are_detected(self):
        self.post['caption'] += ' changed'
        self.path.write_text(json.dumps(self.post))
        with self.assertRaisesRegex(InstagramError, 'caption è cambiata'):
            load_post(self.path)

    def test_public_image_requires_exact_jpeg_and_no_authentication(self):
        raw = (self.path.parent/'feed.jpg').read_bytes()
        opener = Mock()
        opener.open.return_value = Response(raw, 'image/jpeg')
        verify_public_image('https://cdn.example.com/feed.jpg', sha(raw), opener=opener)
        self.assertIsNone(opener.open.call_args.args[0].get_header('Authorization'))
        for data, mime, expected in ((raw, 'text/html', sha(raw)), (raw, 'image/jpeg', 'wrong'),
                                      (self.source.read_bytes(), 'image/jpeg', self.source_hash)):
            with self.subTest(mime=mime, expected=expected):
                opener.open.return_value = Response(data, mime)
                with self.assertRaises(InstagramError):
                    verify_public_image('https://cdn.example.com/feed.jpg', expected, opener=opener)

    def test_publish_records_id_and_retry_never_reposts(self):
        result = self.publish()
        self.assertEqual(result['status'], 'published')
        self.assertEqual(result['media_id'], '789')
        self.assertEqual(result['permalink'], 'https://www.instagram.com/p/example/')
        self.assertEqual(len(self.writes()), 2)
        self.assertEqual(self.writes()[0].kwargs['caption'], self.post['caption'])
        self.assertEqual(self.publish()['media_id'], '789')
        self.assertEqual(len(self.writes()), 2)
        self.assertEqual(self.check_image.call_count, 1)

    def test_missing_public_image_and_wrong_profile_prevent_writes(self):
        self.check_image.side_effect = InstagramError('bad image')
        with self.assertRaises(InstagramError):
            self.publish()
        self.assertEqual(self.writes(), [])
        self.client.profile.side_effect = InstagramError('wrong profile')
        with self.assertRaises(InstagramError):
            self.publish()
        self.assertEqual(self.writes(), [])

    def test_processing_resumes_same_container(self):
        self.client.request.side_effect = [{'id': '456'}, {'status_code': 'IN_PROGRESS'}]
        with self.assertRaisesRegex(InstagramError, 'elaborando'):
            self.publish(polls=1)
        self.client.request.side_effect = [{'status_code': 'FINISHED'}, {'id': '789'}, {}]
        self.assertEqual(self.publish()['media_id'], '789')
        self.assertEqual(len(self.writes()), 2)

    def test_timeout_during_publish_reconciles_without_second_write(self):
        self.client.request.side_effect = [{'id': '456'}, {'status_code': 'FINISHED'}, InstagramError('timeout')]
        with self.assertRaisesRegex(InstagramError, 'Esito da verificare'):
            self.publish()
        self.client.request.side_effect = [{'status_code': 'PUBLISHED'}]
        result = self.publish()
        self.assertEqual(result['status'], 'published')
        self.assertIsNone(result['media_id'])  # Never confuse container and media IDs.
        self.assertEqual(len(self.writes()), 2)

    def test_uncertain_publish_blocks_even_when_container_reports_finished(self):
        self.client.request.side_effect = [{'id': '456'}, {'status_code': 'FINISHED'}, InstagramError('timeout')]
        with self.assertRaises(InstagramError):
            self.publish()
        self.client.request.side_effect = [{'status_code': 'FINISHED'}]
        with self.assertRaisesRegex(InstagramError, 'incerto'):
            self.publish()
        self.assertEqual(len(self.writes()), 2)

    def test_crash_before_publish_response_keeps_uncertain_state(self):
        self.client.request.side_effect = [{'id': '456'}, {'status_code': 'FINISHED'}, KeyboardInterrupt()]
        with self.assertRaises(KeyboardInterrupt):
            self.publish()
        self.client.request.side_effect = [{'status_code': 'PUBLISHED'}]
        self.assertEqual(self.publish()['status'], 'published')
        self.assertEqual(len(self.writes()), 2)

    def test_failed_or_expired_container_never_publishes(self):
        for status in ('ERROR', 'EXPIRED'):
            with self.subTest(status=status):
                self.state = self.root/f'{status}.sqlite'
                self.client.reset_mock()
                self.client.request.side_effect = [{'id': '456'}, {'status_code': status}]
                with self.assertRaisesRegex(InstagramError, 'fallito o scaduto'):
                    self.publish()
                with self.assertRaisesRegex(InstagramError, 'fallito o scaduto'):
                    self.publish()
                self.assertEqual(len(self.writes()), 1)

    def test_permalink_failure_cannot_republish(self):
        self.client.request.side_effect = [{'id': '456'}, {'status_code': 'FINISHED'}, {'id': '789'},
                                           InstagramError('permalink unavailable')]
        self.assertEqual(self.publish()['status'], 'published')
        self.assertEqual(self.publish()['media_id'], '789')
        self.assertEqual(len(self.writes()), 2)

    def test_duplicate_image_and_changed_post_are_blocked(self):
        self.publish()
        original = dict(self.post)
        self.post['generation_id'] = 'different-generation'
        with self.assertRaisesRegex(InstagramError, 'duplicato'):
            self.publish()
        self.post = original
        self.post['caption'] = 'different caption'
        with self.assertRaisesRegex(InstagramError, 'contenuto diverso'):
            self.publish()
        self.assertEqual(len(self.writes()), 2)

    def test_simultaneous_process_is_blocked(self):
        with publication_store(self.state):
            with self.assertRaisesRegex(InstagramError, 'in corso'):
                self.publish()
        self.assertEqual(self.writes(), [])

    def test_check_command_never_calls_publish(self):
        with patch('agents.publisher.InstagramClient') as client, \
                patch('agents.publisher.verify_public_image'), \
                patch('agents.publisher.publish_post') as publish, redirect_stdout(StringIO()) as output:
            client.from_environment.return_value.profile.return_value = {'username': 'gb77ita'}
            main(['check', '--post', str(self.path), '--image-url', 'https://cdn.example.com/feed.jpg'])
        publish.assert_not_called()
        self.assertIn('checked_not_published', output.getvalue())

    def test_cli_missing_secret_has_clear_error_and_nonzero_exit(self):
        with patch.dict('os.environ', {}, clear=True), redirect_stderr(StringIO()) as errors:
            with self.assertRaises(SystemExit) as error:
                main(['connect', '--username', 'gb77ita'])
        self.assertEqual(error.exception.code, 1)
        self.assertIn('INSTAGRAM_ACCESS_TOKEN', errors.getvalue())


if __name__ == '__main__':
    unittest.main()
