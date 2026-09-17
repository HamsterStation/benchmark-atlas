import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

import test_collector as fixtures
from collector.collect import atomic_json, read_json
from scripts.diagnose_model import diagnose


class DiagnosticTests(unittest.TestCase):
    setUp = fixtures.CollectorTests.setUp
    tearDown = fixtures.CollectorTests.tearDown
    collector = fixtures.CollectorTests.collector

    def prepare(self):
        self.collector([fixtures.entry()]).run(discover_only=True)

    def test_single_success_is_budgeted_and_never_saves_generated_content(self):
        self.prepare()
        model = fixtures.Model()
        before = {str(p): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        reserved = []
        def reserve(state):
            self.assertEqual(model.calls, 0)
            reserved.append(state)
        with patch('scripts.diagnose_model.utcnow', return_value=self.now):
            result = diagnose(self.root, reserve=reserve, model=model)
        self.assertTrue(result['ok'])
        self.assertEqual((result['model_calls'], model.calls), (1, 1))
        self.assertEqual(reserved[0]['model_usage'][self.now[:10]], 1)
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.root.rglob('*') if p.is_file()})
        self.assertNotIn('summaryZh', result)

    def test_provider_error_only_exposes_numeric_status_not_credentials(self):
        self.prepare()
        model = fixtures.Model()
        for status in [401, 402, 403, 404, 429, 503]:
            with self.subTest(status=status), patch('scripts.diagnose_model.utcnow', return_value=self.now), patch.object(
                    model, 'generate', side_effect=HTTPError('https://private.invalid/SECRET', status, 'SECRET', {}, None)) as call:
                result = diagnose(self.root, reserve=lambda _: None, model=model)
                self.assertEqual(result['http_status'], status)
                self.assertNotIn('SECRET', json.dumps(result))
                self.assertEqual(call.call_count, 1)

    def test_limit_and_failed_reservation_stop_before_request(self):
        self.prepare()
        model = fixtures.Model()
        def failed_reserve(_):
            raise RuntimeError('Cannot persist')
        with patch('scripts.diagnose_model.utcnow', return_value=self.now), self.assertRaises(RuntimeError):
            diagnose(self.root, reserve=failed_reserve, model=model)
        self.assertEqual(model.calls, 0)
        path = self.root / 'automation/state.json'; state = read_json(path)
        state['model_usage'] = {self.now[:10]: self.config['model_daily_limit']}
        atomic_json(path, state)
        with patch('scripts.diagnose_model.utcnow', return_value=self.now):
            result = diagnose(self.root, reserve=failed_reserve, model=model)
        self.assertEqual(result['error'], 'DailyModelLimit')
        self.assertEqual(model.calls, 0)

    def test_production_model_errors_preserve_http_status(self):
        model = fixtures.Model()
        with patch.object(model, 'generate', side_effect=HTTPError('https://private.invalid', 401, 'SECRET', {}, None)):
            result = self.collector([fixtures.entry()], model=model).run()
        self.assertEqual(result['errors'][0]['http_status'], 401)
        self.assertNotIn('SECRET', json.dumps(result))
