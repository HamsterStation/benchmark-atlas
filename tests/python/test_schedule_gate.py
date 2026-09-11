import json
import subprocess
import unittest
from unittest.mock import patch

from scripts.schedule_gate import decide, remote_json


class ScheduleGateTests(unittest.TestCase):
    def action(self, state=None, deployment=None, **kwargs):
        return decide(state or {}, deployment or {}, now=kwargs.pop("now", "2026-09-11T03:20:00Z"), **kwargs)["action"]

    def test_missed_primary_or_failed_collection_runs_at_backup(self):
        self.assertEqual(self.action(), "collect")
        self.assertEqual(self.action({"last_publishable_collection_at": "2026-09-10T02:30:00Z",
                                      "last_collection_attempt": {"failed": 1}}), "collect")

    def test_successful_day_skips_backup_without_calling_collector(self):
        self.assertEqual(self.action({"last_publishable_collection_at": "2026-09-11T02:30:00Z"},
                                     {"last_successful_deployment_at": "2026-09-11T02:35:00Z"}), "skip")

    def test_build_or_deployment_failure_retries_only_publication(self):
        self.assertEqual(self.action({"last_publishable_collection_at": "2026-09-11T02:30:00Z"},
                                     {"last_successful_deployment_at": "2026-09-10T02:35:00Z"}), "publish")

    def test_model_failure_is_not_a_successful_day(self):
        self.assertEqual(self.action({"last_successful_collection_at": "2026-09-11T02:30:00Z",
                                      "last_publishable_collection_at": None}), "collect")

    def test_cooldown_is_respected_and_expires(self):
        state = {"arxiv_retry_after": "2026-09-11T04:00:00Z"}
        self.assertEqual(self.action(state), "skip")
        self.assertEqual(self.action(state, now="2026-09-11T04:00:00Z"), "collect")

    def test_beijing_day_boundary_and_next_day(self):
        state = {"last_publishable_collection_at": "2026-09-10T16:10:00Z"}
        deploy = {"last_successful_deployment_at": "2026-09-10T16:15:00Z"}
        self.assertEqual(self.action(state, deploy), "skip")
        self.assertEqual(self.action(state, deploy, now="2026-09-11T16:01:00Z"), "collect")

    def test_manual_runs_keep_explicit_control(self):
        self.assertEqual(self.action({"arxiv_retry_after": "2026-09-12T04:00:00Z"}, event="workflow_dispatch"), "collect")

    def test_review_mode_requires_successful_pr_update(self):
        state = {"last_publishable_collection_at": "2026-09-11T02:30:00Z"}
        self.assertEqual(self.action(state, mode="review"), "publish")
        state["last_review_publication_at"] = "2026-09-11T02:35:00Z"
        self.assertEqual(self.action(state, mode="review"), "skip")

    def test_legacy_state_is_supported(self):
        state = {"last_successful_collection_at": "2026-09-11T02:30:00Z"}
        self.assertEqual(self.action(state, {"last_successful_deployment_at": "2026-09-11T02:35:00Z"}), "skip")

    def test_remote_failure_is_not_treated_as_a_missed_day(self):
        with patch("scripts.schedule_gate.subprocess.run", return_value=subprocess.CompletedProcess([], 1, "", "HTTP 403")):
            with self.assertRaises(RuntimeError):
                remote_json("test/repo", "automation/state.json")
        with patch("scripts.schedule_gate.subprocess.run", return_value=subprocess.CompletedProcess([], 1, "", "HTTP 404")):
            self.assertEqual(remote_json("test/repo", "automation/state.json"), {})
        with patch("scripts.schedule_gate.subprocess.run", return_value=subprocess.CompletedProcess([], 0, json.dumps({"queue": {}}), "")):
            self.assertEqual(remote_json("test/repo", "automation/state.json"), {"queue": {}})
