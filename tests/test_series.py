from datetime import datetime, timedelta, timezone
import json
import unittest
from unittest.mock import Mock, patch

from authorized_batch import publish_authorized
from editorial_modes import sourced_review
from email_delivery import DeliveryError, delivery_policy
from gmail_delivery import build_requests
from instagram import InstagramError, publish_post
from newsletter import create_email
import test_email_delivery
import test_instagram
import test_newsletter


class BatchTests(unittest.TestCase):
    setUp = test_instagram.InstagramPublishingTests.setUp

    def grant(self, **changes):
        value = {'schema_version':1,'id':'batch-test','authorization':'explicit_user_batch',
                 'instruction':'Five posts requested by user','limit':5,'username':'gb77ita','language':'fr',
                 'expires_at':(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()} | changes
        path=self.root/'grant.json';path.write_text(json.dumps(value));return path

    def test_explicit_batch_publishes_once_and_bounds_slots(self):
        grant=self.grant()
        result=publish_authorized(grant,1,self.path,'https://cdn.example.com/post.jpg',self.state,self.client,check_image=Mock())
        self.assertEqual(result['status'],'published')
        self.assertEqual(publish_authorized(grant,1,self.path,'https://cdn.example.com/post.jpg',self.state,self.client)['media_id'],'789')
        self.assertEqual(len([c for c in self.client.request.call_args_list if c.args[0]=='POST']),2)
        with self.assertRaises(InstagramError):
            publish_authorized(grant,6,self.path,'https://cdn.example.com/post.jpg',self.state,self.client)
        with self.assertRaises(InstagramError):
            publish_authorized(self.grant(limit=4),2,self.path,'https://cdn.example.com/post.jpg',self.state,self.client)

    def test_expired_or_wrong_account_grant_never_calls_meta(self):
        for changes in ({'expires_at':'2020-01-01T00:00:00+00:00'},{'username':'other'},{'language':'it'}):
            with self.assertRaises(InstagramError):
                publish_authorized(self.grant(**changes),1,self.path,'https://cdn.example.com/post.jpg',self.state,self.client)
        self.client.request.assert_not_called()

    def test_reel_uses_video_and_shares_to_feed(self):
        post=self.post|{'kind':'reel','video_sha256':'abc'}
        check=Mock()
        publish_post(post,'https://cdn.example.com/reel.mp4',self.state,self.client,check_video=check)
        check.assert_called_once_with('https://cdn.example.com/reel.mp4','abc')
        call=self.client.request.call_args_list[0]
        self.assertEqual(call.kwargs['media_type'],'REELS')
        self.assertEqual(call.kwargs['share_to_feed'],'true')
        self.assertNotIn('image_url',call.kwargs)


class RecipientTests(unittest.TestCase):
    setUp=test_email_delivery.EmailDeliveryTests.setUp
    prepare=test_email_delivery.EmailDeliveryTests.prepare

    def test_exact_private_two_recipient_allowlist_and_no_cc(self):
        private=self.root/'private-policy.json'
        private.write_text(json.dumps({'recipients':['first@example.com','second@example.com']}))
        requests=build_requests(self.prepare(),'gb77ita@gmail.com')
        self.assertEqual(requests[0]['request']['to'],'first@example.com, second@example.com')
        self.assertNotIn('cc',requests[0]['request']);self.assertNotIn('bcc',requests[0]['request'])
        private.write_text(json.dumps({'recipients':['first@example.com','third@example.com']}))
        with self.assertRaises(DeliveryError):
            build_requests(self.output/'delivery.json','gb77ita@gmail.com')


class EmailLinkTests(unittest.TestCase):
    setUp=test_newsletter.NewsletterTests.setUp

    def test_real_permalink_in_html_and_plain_text_without_strapline(self):
        self.report['instagram_url']='https://www.instagram.com/p/actual-post/'
        result=create_email(self.product,self.report,self.feed,self.root)
        html=result['html_path'].read_text()
        self.assertIn(self.report['instagram_url'],html)
        self.assertNotIn('EXPERTISE',html)
        self.assertIn('Voir le post Instagram',html)
        from email.parser import BytesParser
        from email import policy
        message=BytesParser(policy=policy.default).parsebytes(result['eml_path'].read_bytes())
        self.assertIn(self.report['instagram_url'],message.get_body(preferencelist=('plain',)).get_content())
        self.report['instagram_url']='https://example.com/fake'
        with self.assertRaises(ValueError):create_email(self.product,self.report,self.feed,self.root)
