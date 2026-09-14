import unittest
from unittest.mock import MagicMock, patch

from collector.collect import ArxivCooldown, HttpClient, read_json, atomic_json, material_hash
from collector.report import digest
import test_collector as fixtures

entry, Model, Pages = fixtures.entry, fixtures.Model, fixtures.Pages


class CachedProcessingTests(unittest.TestCase):
    setUp = fixtures.CollectorTests.setUp
    tearDown = fixtures.CollectorTests.tearDown
    collector = fixtures.CollectorTests.collector

    def offline(self, **kwargs):
        client = MagicMock()
        client.get.side_effect = AssertionError("Cached processing must never call arXiv")
        return self.collector(client=client, **kwargs), client

    def test_discovery_only_does_not_generate_or_mark_publication_success(self):
        model = Model()
        result = self.collector([entry()], model=model).run(discover_only=True)
        self.assertTrue(result["collection_complete"])
        self.assertFalse(result["processing_complete"])
        self.assertEqual(model.calls, 0)
        state = read_json(self.root / "automation/state.json")
        self.assertIsNone(state["last_publishable_collection_at"])
        self.assertEqual(state["ready_queue"]["2609.00001"]["hash"], material_hash(entry()))
        self.assertFalse((self.root / "data/drafts").exists())

    def test_api_failure_can_only_publish_previously_completed_materials(self):
        self.collector([entry()]).run(discover_only=True)
        latest = [entry(f"2609.0000{i}") for i in range(2, 6)]
        self.collector(client=Pages(latest, fail_at=2), now="2026-09-11T03:00:00Z").run(discover_only=True)
        failed = read_json(self.root / "automation/state.json")
        note = self.root / "notes/human.md"
        note.parent.mkdir(); note.write_text("Human experiment record must survive.")
        model = Model()
        worker, client = self.offline(model=model, now="2026-09-11T04:00:00Z")
        result = worker.run(queue_only=True)
        after = read_json(self.root / "automation/state.json")
        self.assertTrue(result["processing_complete"])
        self.assertFalse(result["collection_complete"])
        self.assertEqual([p["id"] for p in result["changes"]], ["arxiv-2609.00001"])
        self.assertEqual(model.calls, 1); client.get.assert_not_called()
        self.assertEqual(after["last_collection_attempt"], failed["last_collection_attempt"])
        self.assertEqual(after["queries"], failed["queries"])
        self.assertEqual(after["last_successful_collection_at"], self.now)
        self.assertEqual(after["last_successful_processing_at"], "2026-09-11T04:00:00Z")
        self.assertEqual(set(after["queue"]), {"2609.00002", "2609.00003"})
        self.assertIn(self.now, read_json(self.root / "data/drafts/arxiv-2609.00001.json")["sources"][0]["scope"])
        self.assertEqual(note.read_text(), "Human experiment record must survive.")
        self.assertNotIn("分页尚未完成", digest(result))
        self.assertIn("不访问 arXiv", digest(result))

    def test_partial_new_version_cannot_reuse_old_version_proof(self):
        self.collector([entry()]).run(discover_only=True)
        self.config["max_pages_per_run"] = 1
        self.config["page_size"] = 1
        self.collector([entry(version=2), entry("2609.00002")], now="2026-09-11T03:00:00Z").run(discover_only=True)
        model = Model(); worker, client = self.offline(model=model, now="2026-09-11T04:00:00Z")
        result = worker.run(queue_only=True)
        self.assertFalse(result["processing_complete"])
        self.assertEqual(result["errors"][0]["type"], "NoFreshCompletedMaterials")
        self.assertEqual(model.calls, 0); client.get.assert_not_called()
        self.assertEqual(worker.state["queue"]["2609.00001"]["entry"]["version"], 2)

    def test_daily_limit_and_repeat_are_shared_during_cooldown(self):
        quality = read_json(self.root / "config/quality.json")
        quality.update(max_candidates_per_run=2, max_candidates_per_day=2)
        atomic_json(self.root / "config/quality.json", quality)
        self.collector([entry(f"2609.0000{i}") for i in range(1, 5)]).run(discover_only=True)
        path = self.root / "automation/state.json"; state = read_json(path)
        state["arxiv_retry_after"] = "2026-09-14T00:00:00Z"; atomic_json(path, state)
        model = Model(); worker, client = self.offline(model=model)
        first = worker.run(queue_only=True)
        second, _ = self.offline(model=model)
        repeated = second.run(queue_only=True)
        self.assertEqual((model.calls, len(first["changes"]), repeated["changes"]), (2, 2, []))
        self.assertEqual(repeated["daily_intake"]["used"], 2)
        self.assertEqual(read_json(path)["arxiv_retry_after"], state["arxiv_retry_after"])
        tomorrow, _ = self.offline(model=model, now="2026-09-11T03:00:00Z")
        self.assertEqual(len(tomorrow.run(queue_only=True)["changes"]), 2)
        self.assertEqual(model.calls, 4); client.get.assert_not_called()

    def test_expired_or_corrupted_cache_is_not_used(self):
        self.collector([entry()]).run(discover_only=True)
        model = Model(); worker, _ = self.offline(model=model, now="2026-09-18T03:00:00Z")
        self.assertFalse(worker.run(queue_only=True)["processing_complete"])
        path = self.root / "automation/state.json"; state = read_json(path)
        state["queue"]["2609.00001"]["entry"]["abstract"] += " changed"
        atomic_json(path, state)
        worker, _ = self.offline(model=model)
        self.assertFalse(worker.run(queue_only=True)["processing_complete"])
        self.assertEqual(model.calls, 0)

    def test_legacy_queue_requires_matching_pre_success_triage(self):
        self.collector([entry(), entry("2609.00002")]).run()
        path = self.root / "automation/state.json"; state = read_json(path)
        state.pop("ready_queue"); atomic_json(path, state)
        triage_path = self.root / "data/triage/arxiv-2609.00002.json"
        triage = read_json(triage_path); triage["assessedAt"] = "2026-09-11T03:00:00Z"
        atomic_json(triage_path, triage)
        model = Model(); worker, _ = self.offline(model=model, now="2026-09-12T03:00:00Z")
        result = worker.run(queue_only=True)
        self.assertEqual([p["id"] for p in result["changes"]], ["arxiv-2609.00001"])
        self.assertIn("2609.00002", worker.state["queue"])

    def test_no_key_dry_run_is_read_only_and_real_processing_waits(self):
        self.collector([entry()]).run(discover_only=True)
        before = {str(p): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        worker, client = self.offline(dry_run=True)
        result = worker.run(queue_only=True)
        self.assertEqual(result["model_calls"], 0)
        self.assertTrue(result["processing_complete"])
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.root.rglob("*") if p.is_file()})
        client.get.assert_not_called()
        for _ in range(2):
            worker, _ = self.offline()
            result = worker.run(queue_only=True)
            self.assertFalse(result["processing_complete"])
            self.assertEqual(result["errors"][0]["type"], "ModelUnavailable")
            self.assertIsNone(worker.state["last_publishable_collection_at"])

    def test_model_failure_does_not_advance_publication_and_can_recover(self):
        self.collector([entry()]).run(discover_only=True)
        worker, _ = self.offline(model=Model(fail=True))
        self.assertFalse(worker.run(queue_only=True)["processing_complete"])
        self.assertIsNone(worker.state["last_publishable_collection_at"])
        deferred, _ = self.offline(model=Model(), now="2026-09-10T04:00:00Z")
        self.assertFalse(deferred.run(queue_only=True)["processing_complete"])
        self.assertIsNone(deferred.state["last_publishable_collection_at"])
        worker, _ = self.offline(model=Model(), now="2026-09-11T03:00:00Z")
        self.assertTrue(worker.run(queue_only=True)["processing_complete"])

    def test_completed_discovery_is_not_refetched_on_same_local_day(self):
        client = Pages([entry()])
        self.collector(client=client, now="2026-09-10T16:10:00Z").run(discover_only=True)
        result = self.collector(client=client, now="2026-09-11T03:00:00Z").run(discover_only=True)
        self.assertEqual(len(client.urls), 1)
        self.assertTrue(result["collection_complete"])
        self.assertEqual(result["pages"], 0)
        self.assertEqual(result["last_successful_collection_at"], "2026-09-10T16:10:00Z")
        self.collector(client=client, now="2026-09-11T16:10:00Z").run(discover_only=True)
        self.assertEqual(len(client.urls), 2)

    def test_repeated_rate_limits_back_off_across_runs(self):
        client = MagicMock(); client.get.side_effect = ArxivCooldown(429, "2026-09-10T04:00:00Z")
        self.collector(client=client).run(discover_only=True)
        later = self.collector(client=client, now="2026-09-10T04:01:00Z")
        later.run(discover_only=True)
        self.assertEqual(later.state["arxiv_rate_limit_streak"], 2)
        self.assertEqual(later.state["arxiv_retry_after"], "2026-09-10T06:01:00Z")
        self.assertEqual(client.get.call_count, 2)

    def test_request_spacing_starts_after_previous_response_finishes(self):
        sleep = MagicMock()
        client = HttpClient(self.config, sleeper=sleep)
        response = MagicMock()
        response.__enter__.return_value.read.return_value = b"fixture"
        with patch.object(client.opener, "open", return_value=response), patch(
                "collector.collect.time.monotonic", side_effect=[100, 100, 160, 160, 170, 230]):
            client.get("https://export.arxiv.org/api/query?id_list=2609.00001")
            client.get("https://export.arxiv.org/api/query?id_list=2609.00002")
        sleep.assert_called_once_with(10)
