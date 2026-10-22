from contextlib import redirect_stdout
from io import StringIO
import json
import sqlite3
import unittest
from unittest.mock import Mock, patch

from agents.publisher import main
from instagram import InstagramError, digest, publish_post
from instagram_approval import offer_post, parse_answer, reply_to_offer
import test_instagram


class ApprovalTests(unittest.TestCase):
    setUp = test_instagram.InstagramPublishingTests.setUp

    def offer(self):
        return offer_post(self.path, 'https://cdn.example.com/feed.jpg', self.state,
                          self.client, check_image=self.check_image)

    def reply(self, request, answer):
        def publish(post, url, state, client):
            return publish_post(post, url, state, client, check_image=self.check_image, sleep=Mock())
        with patch('instagram_approval.publish_post', side_effect=publish):
            return reply_to_offer(request, answer, self.state, client=self.client)

    def writes(self):
        return [call for call in self.client.request.call_args_list if call.args[0] == 'POST']

    def test_offer_shows_exact_post_and_reuses_pending_question_without_writes(self):
        first = self.offer()
        self.assertEqual(self.offer()['request_id'], first['request_id'])
        self.assertEqual(first['status'], 'pending')
        self.assertIn('@gb77ita', first['question'])
        self.assertIn('francese', first['question'])
        self.assertEqual(first['caption'], self.post['caption'])
        self.assertEqual(self.writes(), [])

    def test_yes_publishes_once_and_persists_result_across_replies(self):
        request = self.offer()['request_id']
        self.assertEqual(self.reply(request, 'SÌ')['media_id'], '789')
        self.assertEqual(self.reply(request, 'si')['media_id'], '789')
        self.assertEqual(len(self.writes()), 2)
        with sqlite3.connect(self.state) as db:
            self.assertEqual(db.execute('SELECT status FROM instagram_approvals').fetchone()[0], 'published')

    def test_no_requires_no_token_and_cannot_be_overridden_without_a_new_question(self):
        request = self.offer()['request_id']
        with patch.dict('os.environ', {}, clear=True), patch('instagram_approval.InstagramClient') as client:
            self.assertEqual(reply_to_offer(request, 'NO', self.state)['status'], 'declined_not_published')
        client.from_environment.assert_not_called()
        with self.assertRaisesRegex(InstagramError, 'rifiutato'):
            self.reply(request, 'SI')
        self.assertNotEqual(self.offer()['request_id'], request)
        self.assertEqual(self.writes(), [])

    def test_non_explicit_answers_never_publish(self):
        request = self.offer()['request_id']
        for answer in ('', ' ', 'forse', 'SI ma cambia il testo', 'sì no', 'yes', 'ok'):
            with self.subTest(answer=answer), self.assertRaisesRegex(InstagramError, 'Rispondi'):
                self.reply(request, answer)
        self.assertEqual(self.writes(), [])
        self.assertEqual(self.offer()['status'], 'pending')
        for answer in ('SI', 'sì', 'SÌ', ' sí ', 'si'):
            self.assertEqual(parse_answer(answer), 'SI')

    def test_missing_question_never_publishes(self):
        with self.assertRaisesRegex(InstagramError, 'non trovata'):
            self.reply('missing', 'SI')
        self.assertEqual(self.writes(), [])

    def test_valid_but_changed_caption_requires_new_consent(self):
        request = self.offer()['request_id']
        self.post['caption'] = 'Une nouvelle légende.'
        self.post['caption_sha256'] = digest(self.post['caption'].encode())
        self.path.write_text(json.dumps(self.post))
        with self.assertRaisesRegex(InstagramError, 'cambiato dopo la domanda'):
            self.reply(request, 'SI')
        self.assertEqual(self.writes(), [])

    def test_account_id_cannot_change_after_offer(self):
        request = self.offer()['request_id']
        self.client.profile.return_value = {'id': '999', 'username': 'gb77ita'}
        with self.assertRaisesRegex(InstagramError, 'profilo non corrisponde'):
            self.reply(request, 'SI')
        self.assertEqual(self.writes(), [])

    def test_approval_of_one_language_never_authorizes_another(self):
        first = self.offer()['request_id']
        self.post['language'] = 'it'
        self.path.write_text(json.dumps(self.post))
        other = self.offer()
        self.assertNotEqual(other['request_id'], first)
        self.assertEqual(other['status'], 'pending')
        self.assertIn('italiano', other['question'])
        self.assertEqual(self.writes(), [])

    def test_timeout_resumes_the_same_approved_container_without_duplicate_write(self):
        request = self.offer()['request_id']
        self.client.request.side_effect = [{'id': '456'}, {'status_code': 'FINISHED'},
                                           InstagramError('timeout')]
        with self.assertRaisesRegex(InstagramError, 'Esito da verificare'):
            self.reply(request, 'SI')
        self.assertEqual(self.offer()['status'], 'approved')
        self.client.request.side_effect = [{'status_code': 'PUBLISHED'}]
        self.assertEqual(self.reply(request, 'SI')['status'], 'published')
        self.assertEqual(len(self.writes()), 2)

    def test_no_cannot_claim_to_cancel_an_already_approved_post(self):
        request = self.offer()['request_id']
        self.reply(request, 'SI')
        with self.assertRaisesRegex(InstagramError, 'già stato registrato'):
            self.reply(request, 'NO')

    def test_noninteractive_publish_creates_question_without_sending(self):
        with patch('agents.publisher.InstagramClient.from_environment', return_value=self.client), \
                patch('agents.publisher.offer_post', side_effect=lambda *a: self.offer()), \
                patch('agents.publisher.sys.stdin.isatty', return_value=False), \
                patch('builtins.input') as question, redirect_stdout(StringIO()) as output:
            main(['publish', '--post', str(self.path), '--image-url', 'https://cdn.example.com/feed.jpg',
                  '--state', str(self.state)])
        question.assert_not_called()
        self.assertEqual(json.loads(output.getvalue())['status'], 'pending')
        self.assertEqual(self.writes(), [])

    def test_terminal_publish_asks_and_yes_invokes_publisher(self):
        with patch('agents.publisher.InstagramClient.from_environment', return_value=self.client), \
                patch('agents.publisher.offer_post', side_effect=lambda *a: self.offer()), \
                patch('agents.publisher.reply_to_offer', side_effect=lambda req, answer, *a, **kw: self.reply(req, answer)), \
                patch('agents.publisher.sys.stdin.isatty', return_value=True), \
                patch('builtins.input', return_value='SÌ') as question, redirect_stdout(StringIO()):
            main(['publish', '--post', str(self.path), '--image-url', 'https://cdn.example.com/feed.jpg',
                  '--state', str(self.state)])
        self.assertIn('@gb77ita', question.call_args.args[0])
        self.assertEqual(len(self.writes()), 2)

    def test_eof_leaves_question_pending_without_publication(self):
        with patch('agents.publisher.InstagramClient.from_environment', return_value=self.client), \
                patch('agents.publisher.offer_post', side_effect=lambda *a: self.offer()), \
                patch('agents.publisher.sys.stdin.isatty', return_value=True), \
                patch('builtins.input', side_effect=EOFError), redirect_stdout(StringIO()):
            main(['publish', '--post', str(self.path), '--image-url', 'https://cdn.example.com/feed.jpg',
                  '--state', str(self.state)])
        self.assertEqual(self.offer()['status'], 'pending')
        self.assertEqual(self.writes(), [])

    def test_respond_cli_handles_saved_no_without_credentials(self):
        request = self.offer()['request_id']
        with patch.dict('os.environ', {}, clear=True), redirect_stdout(StringIO()) as output:
            main(['respond', '--request', request, '--answer', 'no', '--state', str(self.state)])
        self.assertEqual(json.loads(output.getvalue())['status'], 'declined_not_published')
        self.assertEqual(self.writes(), [])

    def test_respond_cli_publishes_saved_yes(self):
        request = self.offer()['request_id']
        with patch('instagram_approval.InstagramClient.from_environment', return_value=self.client), \
                patch('instagram_approval.publish_post', side_effect=lambda post, url, state, client:
                      publish_post(post, url, state, client, check_image=self.check_image, sleep=Mock())), \
                redirect_stdout(StringIO()) as output:
            main(['respond', '--request', request, '--answer', 'SÌ', '--state', str(self.state)])
        self.assertEqual(json.loads(output.getvalue())['media_id'], '789')
        self.assertEqual(len(self.writes()), 2)

    def test_terminal_resume_does_not_ask_for_the_same_consent_again(self):
        request = self.offer()['request_id']
        self.reply(request, 'SI')
        with patch('agents.publisher.InstagramClient.from_environment', return_value=self.client), \
                patch('agents.publisher.offer_post', side_effect=lambda *a: self.offer()), \
                patch('agents.publisher.reply_to_offer', side_effect=lambda req, answer, *a, **kw: self.reply(req, answer)), \
                patch('agents.publisher.sys.stdin.isatty', return_value=True), \
                patch('builtins.input') as question, redirect_stdout(StringIO()):
            main(['publish', '--post', str(self.path), '--image-url', 'https://cdn.example.com/feed.jpg',
                  '--state', str(self.state)])
        question.assert_not_called()
        self.assertEqual(len(self.writes()), 2)

    def test_offer_relocates_an_identical_manifest_without_reusing_consent_for_other_content(self):
        request = self.offer()['request_id']
        moved = self.path.with_name('moved.json')
        self.path.rename(moved)
        self.path = moved
        self.assertEqual(self.offer()['request_id'], request)
        self.assertEqual(self.reply(request, 'SI')['status'], 'published')


if __name__ == '__main__':
    unittest.main()
