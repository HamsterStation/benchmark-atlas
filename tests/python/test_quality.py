import json
import unittest

from collector.collect import ROOT, read_json
from collector.quality import assess
from collector.report import digest
import test_collector as fixtures

entry = fixtures.entry
Model = fixtures.Model


class QualityTests(unittest.TestCase):
    def setUp(self):
        self.config = read_json(ROOT / "config/quality.json")
        self.now = "2026-09-10T00:00:00Z"

    def check(self, abstract, title="A Benchmark for LLM Agents"):
        e = entry()
        e.update({"abstract": abstract, "title": title})
        return assess(e, self.config, self.now)

    def test_complete_evidence_gets_priority_without_claiming_quality(self):
        abstract = "We introduce TaskBench, a benchmark for LLM agents with 300 tasks. We compare baseline agents using task success rate. Data and code: https://github.com/example/TaskBench. We study contamination and generalization."
        p = self.check(abstract)
        self.assertEqual(p["decision"], "priority_review")
        self.assertFalse(p["qualityVerified"])
        self.assertFalse(p["venueVerified"])
        self.assertEqual(p["score"], p["scoreMax"])
        for e in p["evidence"]:
            self.assertIn(e["excerpt"], abstract)

    def test_method_using_benchmarks_is_excluded_even_with_code(self):
        p = self.check("We propose a new training method for large language models. We evaluate our method on existing benchmarks and compare baseline accuracy. Code: https://github.com/example/method.")
        self.assertEqual(p["decision"], "excluded")
        self.assertNotIn("benchmark_contribution", [e["signal"] for e in p["evidence"]])

    def test_proposed_method_and_benchmark_in_same_sentence_are_not_confused(self):
        p = self.check("We introduce a model evaluated on a benchmark for LLM agents. We compare baseline agents using success rate.")
        self.assertNotEqual(p["decision"], "priority_review")

    def test_title_hype_famous_authors_and_venue_do_not_raise_score(self):
        p = self.check("We discuss language model agent performance.", "World-class Groundbreaking Benchmark at NeurIPS")
        self.assertEqual(p["decision"], "needs_evidence")
        self.assertEqual(p["score"], 0)
        e = entry()
        first = assess(e, self.config, self.now)
        e.update({"authors": ["Famous University"], "journal_ref": "Accepted at a famous conference"})
        second = assess(e, self.config, self.now)
        self.assertEqual(first["score"], second["score"])
        self.assertFalse(second["venueVerified"])

    def test_missing_protocol_is_held_even_with_a_repo(self):
        p = self.check("We introduce a benchmark for language model agents with 300 tasks. Data: https://github.com/example/tasks.")
        self.assertEqual(p["decision"], "needs_evidence")

    def test_unrelated_agent_benchmark_and_survey_are_excluded(self):
        p = self.check("We introduce a benchmark for multi-agent molecular simulation with 300 tasks and success rate.", "Agent simulation benchmark")
        self.assertEqual(p["decision"], "excluded")
        p = self.check("We survey benchmarks for language model agents.", "A Survey of Agent Benchmarks")
        self.assertEqual(p["decision"], "excluded")

    def test_untrusted_links_are_not_fetched_or_treated_as_official(self):
        e = entry()
        e["abstract"] = e["abstract"].split("Code and data:")[0]
        e["comment"] = "See https://user:password@github.com/example/private and https://127.0.0.1/private"
        p = assess(e, self.config, self.now)
        self.assertEqual(p["resourceCandidates"], [])

    def test_markdown_and_latex_resource_links_keep_only_the_url(self):
        e = entry()
        url = "https://example.github.io/test-only/"
        e["abstract"] = e["abstract"].split("Code and data:")[0] + f" \\href{{{url}}}{{project}}"
        e["comment"] = f"Project home: [{url}]({url}) and `{url}`"
        result = assess(e, self.config, self.now)
        self.assertEqual(result["resourceCandidates"], [url])
        self.assertEqual([v["excerpt"] for v in result["evidence"] if v["signal"] == "resource_link"], [url])

    def test_report_escapes_markup_mentions_and_instructions(self):
        p = self.check("We introduce a benchmark for LLM agents. We compare baselines using accuracy. Code: https://github.com/example/test-only.", "<script>alert(1)</script> @someone [click](https://evil.invalid)")
        text = digest({"quality_candidates": [p]})
        self.assertNotIn("<script>", text)
        self.assertNotIn("@someone", text)
        self.assertNotIn("[click]", text)
        self.assertIn("未配置模型", text)

    def test_resource_link_is_required_even_with_baselines(self):
        p = self.check("We introduce a benchmark for LLM agents with 300 tasks. We compare baseline agents using success rate and study contamination.")
        self.assertEqual(p["decision"], "needs_evidence")

    def test_training_dataset_is_not_a_benchmark_contribution(self):
        p = self.check("We introduce a dataset for fine-tuning language models with 300 questions. We compare baseline accuracy. Data: https://github.com/example/training.")
        self.assertEqual(p["decision"], "needs_evidence")
        self.assertNotIn("benchmark_contribution", [e["signal"] for e in p["evidence"]])
        p = self.check("We introduce a dataset to evaluate language model agents with 300 tasks. We compare baseline accuracy. Data: https://github.com/example/evaluation.")
        self.assertEqual(p["decision"], "priority_review")


class IntakeTests(unittest.TestCase):
    setUp = fixtures.CollectorTests.setUp
    tearDown = fixtures.CollectorTests.tearDown
    collector = fixtures.CollectorTests.collector

    def test_quality_gate_reduces_model_calls_and_preserves_uncertain_material(self):
        uncertain = entry("2609.00002")
        uncertain["abstract"] = "We introduce a benchmark for language model agents. Details will follow."
        uses = entry("2609.00003")
        uses["abstract"] = "We propose a new method for LLMs. We evaluate the method on existing benchmarks."
        model = Model()
        c = self.collector([entry(), uncertain, uses], model=model)
        report = c.run()
        self.assertEqual(model.calls, 1)
        self.assertEqual(report["quality_counts"], {"priority_review": 1, "needs_evidence": 1, "excluded": 1})
        self.assertEqual(c.state["queue"]["2609.00002"]["status"], "awaiting_evidence")
        self.assertEqual(c.state["queue"]["2609.00002"]["entry"]["abstract"], uncertain["abstract"])
        self.assertEqual(len(list((self.root / "data/drafts").glob("*.json"))), 1)

    def test_daily_intake_is_bounded_and_continues_after_no_key(self):
        quality = read_json(self.root / "config/quality.json")
        quality["max_candidates_per_run"] = 2
        quality["max_candidates_per_day"] = 2
        (self.root / "config/quality.json").write_text(json.dumps(quality))
        records = [entry(f"2609.0000{i}") for i in range(1, 5)]
        first = self.collector(records).run()
        self.assertEqual(len(first["changes"]), 2)
        second = self.collector(records).run()
        self.assertEqual(len(second["changes"]), 0)
        tomorrow = self.collector(records, now="2026-09-11T03:00:00Z").run()
        self.assertEqual(len(tomorrow["changes"]), 2)
        third = self.collector(records, now="2026-09-11T03:00:00Z").run()
        self.assertEqual(len(third["changes"]), 0)

    def test_daily_budget_uses_beijing_midnight_and_dry_run_does_not_consume(self):
        quality = read_json(self.root / "config/quality.json")
        quality.update({"max_candidates_per_run": 2, "max_candidates_per_day": 2})
        (self.root / "config/quality.json").write_text(json.dumps(quality))
        records = [entry(f"2609.0000{i}") for i in range(1, 5)]
        preview = self.collector(records, dry_run=True).run()
        self.assertEqual(preview["daily_intake"]["used"], 2)
        self.assertFalse((self.root / "automation/state.json").exists())
        self.assertEqual(len(self.collector(records, now="2026-09-10T15:59:00Z").run()["changes"]), 2)
        self.assertEqual(len(self.collector(records, now="2026-09-10T15:59:30Z").run()["changes"]), 0)
        self.assertEqual(len(self.collector(records, now="2026-09-10T16:00:00Z").run()["changes"]), 2)

    def test_reserved_no_key_candidates_can_resume_behind_a_large_queue(self):
        quality = read_json(self.root / "config/quality.json")
        quality.update({"max_candidates_per_run": 2, "max_candidates_per_day": 2})
        (self.root / "config/quality.json").write_text(json.dumps(quality))
        self.config["max_queue_per_run"] = 3
        records = [entry(f"2609.0000{i}") for i in range(1, 7)]
        self.collector(records).run()
        model = Model()
        result = self.collector(records, model=model).run()
        self.assertEqual(model.calls, 2)
        self.assertEqual(result["daily_intake"]["used"], 2)
        self.assertEqual(len(list((self.root / "data/drafts").glob("*.json"))), 2)

    def test_unchanged_triage_is_stable_and_dry_run_does_not_write_it(self):
        self.collector([entry()]).run()
        path = self.root / "data/triage/arxiv-2609.00001.json"
        before = path.read_bytes()
        self.collector([entry()], now="2026-09-11T00:00:00Z").run()
        self.assertEqual(path.read_bytes(), before)
        report = self.collector([entry("2609.00002")], dry_run=True).run()
        self.assertFalse((self.root / "data/triage/arxiv-2609.00002.json").exists())
        self.assertTrue(report["quality_candidates"])

    def test_policy_reassessment_is_not_counted_as_a_paper_version_update(self):
        paper = entry(version=2)
        paper["abstract"] = "We propose a method for LLMs. We evaluate our method on existing benchmarks."
        self.collector([paper]).run()
        quality = read_json(self.root / "config/quality.json")
        quality["version"] += 1
        (self.root / "config/quality.json").write_text(json.dumps(quality))
        again = self.collector([paper]).run()
        self.assertEqual((again["new"], again["updated"], again["reassessed"]), (0, 0, 1))

    def test_policy_changes_cannot_roll_back_a_seen_paper_version(self):
        paper = entry(version=2)
        paper["abstract"] = "We propose a method for LLMs. We evaluate our method on existing benchmarks."
        self.collector([paper]).run()
        quality = read_json(self.root / "config/quality.json")
        quality["version"] += 1
        (self.root / "config/quality.json").write_text(json.dumps(quality))
        paper["version"] = 1
        c = self.collector([paper])
        again = c.run()
        self.assertEqual(again["skipped"], 1)
        self.assertEqual(c.state["seen"][paper["arxiv_id"]]["version"], 2)
