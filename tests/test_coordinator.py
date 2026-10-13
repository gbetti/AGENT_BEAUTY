from argparse import Namespace
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from agents.assets import AssetsAgent
from agents.contracts import KeywordBrief, TrendBrief
from agents.keywords import KeywordAgent
from agents.trends import TrendAgent
from catalog import load_products
from coordinator import AgentExecutionError, BeautyCoordinator
from test_agent import ingredient_fixture, trends_fixture, weekly_fixture


class CoordinatorTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.args = Namespace(database=Path(folder.name)/'catalog.sqlite',
                              output=Path(folder.name)/'out', product='Sublime')
        self.products = load_products(self.args.database)
        self.product = next(p for p in self.products if 'Sublime' in p['name'])
        self.now = datetime(2026, 10, 8, 12, tzinfo=timezone.utc)
        self.trends = TrendBrief(self.now, self.product, 'renew',
                                 self.product['data']['editorial']['claim_it'],
                                 [{'title': 'Skincare barrier'}], [], {'renew': 1}, weekly_fixture())
        self.keywords = KeywordBrief(self.now, self.product['id'], trends_fixture(),
                                     {'fr': {'interpretation': 'Hypothèse'},
                                      'it': {'interpretation': 'Ipotesi'}})

    def test_coordinator_passes_same_briefs_in_order_and_reports_progress(self):
        agents = [Mock(), Mock(), Mock()]
        calls = []
        def trend(products, args, now):
            calls.append('trends')
            self.assertEqual(now, self.now)
            self.assertEqual({p['id'] for p in products}, {p['id'] for p in self.products})
            return self.trends
        def keyword(trends, now):
            calls.append('keywords')
            self.assertIs(trends, self.trends)
            return self.keywords
        def assets(trends, keywords, args, now, pipeline):
            calls.append('assets')
            self.assertIs(trends, self.trends)
            self.assertIs(keywords, self.keywords)
            self.assertEqual([s['status'] for s in pipeline['stages']],
                             ['completed', 'completed', 'running'])
            return {'fr': {'feed': 'example'}, 'it': {'feed': 'esempio'}}
        for component, action in zip(agents, (trend, keyword, assets)):
            component.run.side_effect = action
        events = []
        result = BeautyCoordinator(*agents).run(
            self.args, now=self.now, progress=lambda *event: events.append(event))
        self.assertEqual(calls, ['trends', 'keywords', 'assets'])
        self.assertEqual(set(result), {'fr', 'it'})
        self.assertEqual(events, [(agent, state) for agent in calls
                                  for state in ('running', 'completed')])

    def test_failed_stage_prevents_all_downstream_agents_and_identifies_cause(self):
        for failed in range(3):
            with self.subTest(failed=failed):
                agents = [Mock(), Mock(), Mock()]
                agents[0].run.return_value = self.trends
                agents[1].run.return_value = self.keywords
                agents[failed].run.side_effect = OSError('Provider non disponibile')
                with self.assertRaisesRegex(AgentExecutionError, 'Provider non disponibile') as caught:
                    BeautyCoordinator(*agents).run(self.args, now=self.now)
                stages = caught.exception.pipeline['stages']
                self.assertEqual([s['status'] for s in stages],
                                 ['completed']*failed+['failed']+['pending']*(2-failed))
                self.assertIsInstance(caught.exception.__cause__, OSError)
                for downstream in agents[failed+1:]:
                    downstream.run.assert_not_called()
                self.assertFalse(self.args.output.exists())

    def test_trend_agent_refreshes_discovery_and_evidence_on_every_run(self):
        with patch('agents.trends.search_news', return_value=self.trends.news) as news, \
                patch('agents.trends.load_brief', side_effect=lambda *a: weekly_fixture()) as brief:
            for _ in range(2):
                result = TrendAgent().run(self.products, self.args, self.now)
                self.assertEqual(result.product['id'], self.product['id'])
        self.assertEqual(news.call_count, 2)
        self.assertEqual(brief.call_count, 2)

    def test_keyword_agent_keeps_raw_scores_and_upstream_evidence_unchanged(self):
        with patch('agents.keywords.research_trends', return_value=trends_fixture()):
            result = KeywordAgent().run(self.trends, self.now)
        self.assertNotIn('google_trends_results', self.trends.weekly)
        self.assertEqual(result.markets['it']['data']['top'][1],
                         {'query': 'crema', 'value': 89, 'source_rank': 2, 'breakout': False})
        self.assertEqual(result.messaging_hypotheses['fr']['status'], 'hypothesis_to_test')
        self.assertEqual(result.product_id, self.product['id'])

    def test_wrong_markets_are_rejected_before_creative_production(self):
        data = trends_fixture()
        data['fr']['data']['geo'] = 'IT'
        with patch('agents.keywords.research_trends', return_value=data):
            with self.assertRaisesRegex(ValueError, 'keyword francesi'):
                KeywordAgent().run(self.trends, self.now)

    def test_creative_rejects_a_different_product_or_run_before_verifying_formula(self):
        for keywords in (replace(self.keywords, product_id='urn:another-product'),
                         replace(self.keywords, created_at=datetime(2026, 10, 7, tzinfo=timezone.utc))):
            with patch('agents.assets.select_ingredients') as ingredients:
                with self.assertRaises(ValueError):
                    AssetsAgent().prepare(self.trends, keywords, self.args, self.now)
                ingredients.assert_not_called()

    def test_shared_campaign_brief_preserves_catalog_claims_and_isolates_inputs(self):
        with patch('agents.assets.select_ingredients', return_value=ingredient_fixture()):
            result = AssetsAgent().prepare(self.trends, self.keywords, self.args, self.now)
        summary = result.summary()
        self.assertEqual(summary['source_claim'], self.trends.source_claim)
        self.assertEqual(summary['keyword_analysis']['it']['top'][1]['query'], 'crema')
        self.assertEqual(summary['ingredient_ids'], ['ceramides', 'peptides'])
        self.assertEqual(summary['original_packshots'], self.product['images'])
        self.assertNotIn('google_trends_results', self.trends.weekly)
        result.weekly['google_trends_results']['it']['data']['top'][1]['value'] = 1
        self.assertEqual(self.keywords.markets['it']['data']['top'][1]['value'], 89)
        self.assertEqual(result.creative['source_claim_it'], self.trends.source_claim)

    def test_research_cannot_replace_the_catalog_claim(self):
        forged = replace(self.trends, source_claim='Résultats cliniques garantis')
        with patch('agents.assets.select_ingredients') as ingredients:
            with self.assertRaisesRegex(ValueError, 'claim.*catalogo'):
                AssetsAgent().prepare(forged, self.keywords, self.args, self.now)
            ingredients.assert_not_called()
