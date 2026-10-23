import io
from email.message import Message
from unittest import TestCase
from unittest.mock import patch

import test_delivery
from delivery import begin_send, create_manifest, record_sent, write_json
from instagram_story import export_jpeg, publish


class StoryTests(TestCase):
    setUp = test_delivery.DeliveryTests.setUp
    ledger = test_delivery.DeliveryTests.ledger
    hosted = test_delivery.DeliveryTests.hosted
    prepare = test_delivery.DeliveryTests.prepare
    url = 'https://cdn.example.com/campaign/fr/story-instagram.jpg'

    def ready(self):
        create_manifest(self.campaign, 'generation-1')
        export_jpeg(self.campaign)

    def remote(self, url, timeout=30):
        response = io.BytesIO((self.campaign / 'fr/story-instagram.jpg').read_bytes())
        response.headers = Message()
        response.headers['Content-Type'] = 'image/jpeg'
        return response

    def api(self, path, params=None, method='GET'):
        if path == 'me':
            return {'user_id': '17841464260421573', 'username': 'gb77ita'}
        if path.endswith('/media'):
            self.assertEqual(method, 'POST')
            self.assertEqual(params, {'media_type': 'STORIES', 'image_url': self.url})
            self.assertEqual(self.ledger()['instagram_story']['status'], 'creating')
            return {'id': 'container-1'}
        if path == 'container-1':
            return {'status_code': 'FINISHED'}
        if path.endswith('/media_publish'):
            self.assertEqual(method, 'POST')
            self.assertEqual(params, {'creation_id': 'container-1'})
            self.assertEqual(self.ledger()['instagram_story']['status'], 'publishing')
            return {'id': 'media-1'}
        if path == 'media-1':
            return {'id': 'media-1', 'username': 'gb77ita', 'media_product_type': 'STORY',
                    'timestamp': '2026-10-22T13:36:30+0000',
                    'permalink': 'https://www.instagram.com/stories/gb77ita/123'}
        raise AssertionError(path)

    def run_publish(self, api=None):
        with patch('instagram_story.api', side_effect=api or self.api) as calls, \
                patch('instagram_story.urllib.request.urlopen', side_effect=self.remote):
            result = publish(self.campaign, self.url)
        return result, calls

    def test_story_then_email_completes_and_second_publish_is_noop(self):
        self.prepare()
        export_jpeg(self.campaign)
        result, _ = self.run_publish()
        self.assertEqual(result['status'], 'pending_email')
        self.assertTrue(result['instagram_story']['published'])
        begin_send(self.campaign)
        result = record_sent(self.campaign, {'id': 'gmail-1', 'label_ids': ['SENT']})
        self.assertEqual(result['status'], 'complete')
        _, calls = self.run_publish()
        calls.assert_not_called()

    def test_migrates_only_selected_legacy_campaign_preserving_sent_email(self):
        self.prepare()
        begin_send(self.campaign)
        record_sent(self.campaign, {'id': 'gmail-1', 'label_ids': ['SENT']})
        old = self.ledger()
        old.pop('instagram_story')
        old.update(schema_version=1, status='complete')
        write_json(self.campaign / 'delivery.json', old)
        export_jpeg(self.campaign)
        self.assertEqual(self.ledger()['status'], 'pending_story')
        result, _ = self.run_publish()
        self.assertEqual(result['status'], 'complete')
        self.assertEqual(result['email']['message_id'], 'gmail-1')

    def test_wrong_account_cannot_create_container(self):
        self.ready()
        with patch('instagram_story.api', return_value={'user_id': 'other', 'username': 'other'}) as api:
            with self.assertRaisesRegex(ValueError, 'account diverso'):
                publish(self.campaign, self.url)
        self.assertEqual(api.call_count, 1)
        self.assertEqual(self.ledger()['instagram_story']['status'], 'ready')

    def test_new_french_story_preserves_real_italian_email_receipt(self):
        self.ready()
        old = self.ledger()
        old['email'].update(language='it', status='sent', sent=True, message_id='previous-italian')
        write_json(self.campaign / 'delivery.json', old)
        result, _ = self.run_publish()
        self.assertEqual(result['status'], 'complete')
        self.assertEqual(result['instagram_story']['language'], 'fr')
        self.assertEqual(result['email']['language'], 'it')
        self.assertEqual(result['email']['message_id'], 'previous-italian')
        with self.assertRaisesRegex(ValueError, 'già tentato'):
            begin_send(self.campaign)

    def test_unsent_email_cannot_keep_obsolete_language(self):
        self.ready()
        old = self.ledger()
        old['email']['language'] = 'it'
        write_json(self.campaign / 'delivery.json', old)
        with patch('instagram_story.api') as calls:
            with self.assertRaisesRegex(ValueError, 'lingua'):
                publish(self.campaign, self.url)
        calls.assert_not_called()

    def test_remote_byte_mismatch_cannot_create_container(self):
        self.ready()
        response = self.remote(self.url)
        response.seek(0)
        response.write(b'wrong bytes')
        response.seek(0)
        with patch('instagram_story.api', side_effect=self.api) as api, \
                patch('instagram_story.urllib.request.urlopen', return_value=response):
            with self.assertRaisesRegex(ValueError, 'JPEG pubblico'):
                publish(self.campaign, self.url)
        self.assertEqual(api.call_count, 1)

    def test_lost_mutation_responses_do_not_repeat_either_post(self):
        for endpoint, state in (('/media', 'creating'), ('/media_publish', 'publishing')):
            with self.subTest(endpoint=endpoint):
                if (self.campaign / 'delivery.json').exists():
                    (self.campaign / 'delivery.json').unlink()
                self.ready()
                def fail(path, params=None, method='GET'):
                    if path.endswith(endpoint):
                        raise TimeoutError('Lost response')
                    return self.api(path, params, method)
                with self.assertRaises(TimeoutError):
                    self.run_publish(fail)
                self.assertEqual(self.ledger()['instagram_story']['status'], state)
                with patch('instagram_story.api', side_effect=self.api) as calls:
                    with self.assertRaisesRegex(RuntimeError, 'senza ricevuta'):
                        publish(self.campaign, self.url)
                self.assertEqual([call.args[0] for call in calls.call_args_list], ['me'])

    def test_processing_container_is_resumed_without_new_creation(self):
        self.ready()
        def processing(path, params=None, method='GET'):
            if path == 'container-1':
                return {'status_code': 'IN_PROGRESS'}
            return self.api(path, params, method)
        with self.assertRaisesRegex(RuntimeError, 'IN_PROGRESS'):
            self.run_publish(processing)
        self.assertEqual(self.ledger()['instagram_story']['status'], 'created')
        result, calls = self.run_publish()
        self.assertTrue(result['instagram_story']['published'])
        self.assertFalse(any(call.args[0].endswith('/media') for call in calls.call_args_list))

    def test_verification_failure_resumes_without_republishing(self):
        self.ready()
        def wrong_type(path, params=None, method='GET'):
            result = self.api(path, params, method)
            if path == 'media-1':
                result['media_product_type'] = 'FEED'
            return result
        with self.assertRaisesRegex(ValueError, 'non conferma'):
            self.run_publish(wrong_type)
        self.assertEqual(self.ledger()['instagram_story']['status'], 'verifying')
        result, calls = self.run_publish()
        self.assertTrue(result['instagram_story']['published'])
        self.assertEqual([call.args[0] for call in calls.call_args_list], ['me', 'media-1'])
