from argparse import Namespace
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from io import StringIO
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from agents.keywords import main, run_standalone
from test_agent import trends_fixture, weekly_fixture


class StandaloneKeywordTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.args = Namespace(research=self.root/'brief.json', database=self.root/'catalog.sqlite',
                              output=self.root/'keywords')
        self.now = datetime(2026, 10, 8, 12, tzinfo=timezone.utc)
        self.args.research.write_text(json.dumps(weekly_fixture()))

    def test_standalone_archives_exact_evidence_without_running_other_agents(self):
        expected = trends_fixture()
        output, errors = StringIO(), StringIO()
        with patch('agents.keywords.load_brief', return_value=weekly_fixture()) as brief, \
                patch('agents.keywords.research_trends', return_value=expected) as provider, \
                patch('agents.trends.TrendAgent.run') as trend, \
                patch('agents.assets.AssetsAgent.run') as creative, \
                redirect_stdout(output), redirect_stderr(errors):
            path = run_standalone(self.args, now=self.now)
            second = run_standalone(self.args, now=self.now)
        self.assertNotEqual(path, second)
        self.assertEqual(brief.call_count, 2)
        self.assertEqual(provider.call_count, 2)
        trend.assert_not_called()
        creative.assert_not_called()
        report = json.loads(path.read_text())
        self.assertEqual(report['markets'], expected)
        self.assertEqual(report['kind'], 'keyword_analysis')
        self.assertEqual(report['created_at'], self.now.isoformat())
        self.assertIn('TOP — indice relativo 0–100', output.getvalue())
        self.assertIn('crema: 89', output.getvalue())
        self.assertIn('IN CRESCITA', output.getvalue())
        self.assertIn('completato', errors.getvalue())
        self.assertTrue(all(p.suffix == '.json' for p in self.args.output.iterdir()))
        with sqlite3.connect(self.args.database) as database:
            self.assertEqual(database.execute('SELECT COUNT(*) FROM generations').fetchone()[0], 0)

    def test_expired_brief_prevents_provider_and_output(self):
        with patch('agents.keywords.research_trends') as provider, redirect_stderr(StringIO()):
            with self.assertRaisesRegex(ValueError, 'aggiornare'):
                run_standalone(self.args, now=datetime(2026, 10, 13, tzinfo=timezone.utc))
        provider.assert_not_called()
        self.assertFalse(self.args.output.exists())

    def test_provider_failure_keeps_previous_report_and_writes_no_partial_file(self):
        self.args.output.mkdir()
        previous = self.args.output/'previous.json'
        previous.write_text('previous')
        with patch('agents.keywords.load_brief', return_value=weekly_fixture()), \
                patch('agents.keywords.research_trends', side_effect=OSError('Google Trends non disponibile')), \
                redirect_stderr(StringIO()):
            with self.assertRaisesRegex(OSError, 'non disponibile'):
                run_standalone(self.args, now=self.now)
        self.assertEqual(list(self.args.output.iterdir()), [previous])
        self.assertEqual(previous.read_text(), 'previous')

    def test_cli_failure_has_nonzero_exit_and_identifies_agent(self):
        errors = StringIO()
        with patch('agents.keywords.run_standalone', side_effect=ValueError('Brief scaduto')), \
                redirect_stderr(errors):
            with self.assertRaises(SystemExit) as failure:
                main(['--research', str(self.args.research)])
        self.assertEqual(failure.exception.code, 1)
        self.assertIn('Keyword & Domanda: Brief scaduto', errors.getvalue())
