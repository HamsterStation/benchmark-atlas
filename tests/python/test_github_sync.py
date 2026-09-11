import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from collector.collect import ROOT, atomic_json, read_json
from scripts import github_sync as sync


class GitHubSyncTests(unittest.TestCase):
    """Real local Git branches; GitHub PR calls are explicit test doubles."""
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.bare = self.base / "remote.git"
        self.repo = self.base / "working"
        subprocess.run(["git", "init", "--bare", str(self.bare)], check=True, capture_output=True)
        self.repo.mkdir()
        self.git("init", "--initial-branch", "main")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "user.name", "Test")
        (self.repo / "notes").mkdir()
        (self.repo / "notes/human.md").write_text("Manual note remains unchanged.")
        self.git("add", ".")
        self.git("commit", "-m", "initial")
        self.git("remote", "add", "origin", str(self.bare))
        self.git("push", "origin", "main")
        self.calls = []
        self.pr_bodies = []
        self.pr_created = False
        self.env = patch.dict(os.environ, {"GITHUB_ACTIONS": "true", "ATLAS_WRITE_ENABLED": "true", "GITHUB_REPOSITORY": "test/atlas", "GITHUB_RUN_ID": "1", "GITHUB_SHA": "a" * 40})
        self.env.start()
        self.root_patch = patch.object(sync, "ROOT", self.repo)
        self.root_patch.start()

    def tearDown(self):
        self.root_patch.stop()
        self.env.stop()
        self.temp.cleanup()

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.repo, check=True, capture_output=True, text=True).stdout

    def local_run(self, args, cwd=None, check=True):
        if args[0] == "gh":
            self.calls.append(args)
            if "--body-file" in args:
                self.pr_bodies.append(Path(args[args.index("--body-file") + 1]).read_text())
            output = json.dumps([{"number": 1}] if self.pr_created else []) if args[1:3] == ["pr", "list"] else ""
            if args[1:3] == ["pr", "create"]:
                self.pr_created = True
            return subprocess.CompletedProcess(args, 0, output, "")
        args = [str(self.bare) if a == "https://github.com/test/atlas.git" else a for a in args]
        return subprocess.run(args, cwd=cwd or self.repo, check=check, capture_output=True, text=True)

    def invoke(self, action):
        with patch.object(sync, "run", side_effect=self.local_run), patch("sys.argv", ["github_sync.py", action, "--base", "main"]):
            sync.main()

    def test_persistent_branch_restore_and_successful_deployment_record(self):
        state = {"queue": {"paper": {"status": "failed"}}, "last_successful_collection_at": "2026-09-10T00:00:00Z"}
        atomic_json(self.repo / "automation/state.json", state)
        self.invoke("persist")
        atomic_json(self.repo / "automation/state.json", {})
        self.invoke("restore")
        self.assertEqual(read_json(self.repo / "automation/state.json"), state)
        self.assertEqual((self.repo / "notes/human.md").read_text(), "Manual note remains unchanged.")
        self.invoke("deployment")
        self.invoke("restore")
        self.assertEqual(read_json(self.repo / "automation/deployment.json")["commit"], "a" * 40)
        self.assertIsNotNone(read_json(self.repo / "automation/deployment.json")["last_successful_deployment_at"])
        self.invoke("review-complete")
        self.invoke("restore")
        restored = read_json(self.repo / "automation/state.json")
        self.assertIsNotNone(restored["last_review_publication_at"])
        self.assertEqual(restored["queue"], state["queue"])

    def test_review_creates_branch_without_touching_main_or_notes(self):
        atomic_json(self.repo / "data/drafts/arxiv-2609.00001.json", {"test_only": True})
        atomic_json(self.repo / "data/triage/arxiv-2609.00001.json", {"decision": "priority_review", "test_only": True})
        self.invoke("review")
        self.assertTrue(any(c[1:3] == ["pr", "create"] for c in self.calls))
        self.assertIn("累计待审核草稿：1 篇", self.pr_bodies[0])
        self.assertIn("atlas-review/data/drafts/arxiv-2609.00001.json", self.pr_bodies[0])
        main = subprocess.check_output(["git", "--git-dir", str(self.bare), "ls-tree", "-r", "--name-only", "main"], text=True)
        review = subprocess.check_output(["git", "--git-dir", str(self.bare), "ls-tree", "-r", "--name-only", "atlas-review"], text=True)
        self.assertNotIn("data/drafts", main)
        self.assertIn("data/drafts/arxiv-2609.00001.json", review)
        note = subprocess.check_output(["git", "--git-dir", str(self.bare), "show", "atlas-review:notes/human.md"], text=True)
        self.assertEqual(note, "Manual note remains unchanged.")

    def test_remote_errors_are_not_treated_as_empty_state(self):
        with patch.object(sync, "run", return_value=subprocess.CompletedProcess([], 128, "", "network failure")):
            with self.assertRaises(RuntimeError):
                sync.branch_exists("remote", "atlas-state")

    def test_review_reuses_the_existing_branch_and_pr(self):
        path = self.repo / "data/drafts/arxiv-2609.00001.json"
        atomic_json(path, {"title": "TEST ONLY first draft"})
        atomic_json(self.repo / "data/triage/arxiv-2609.00001.json", {"decision": "priority_review"})
        self.invoke("review")
        atomic_json(path, {"title": "TEST ONLY updated draft"})
        self.invoke("review")
        self.assertEqual(sum(c[1:3] == ["pr", "create"] for c in self.calls), 1)
        self.assertEqual(sum(c[1:3] == ["pr", "edit"] for c in self.calls), 1)
        self.assertIn("TEST ONLY updated draft", self.pr_bodies[-1])
        self.assertEqual((self.repo / "notes/human.md").read_text(), "Manual note remains unchanged.")

    def test_local_invocation_cannot_push(self):
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "false"}), patch("sys.argv", ["github_sync.py", "persist"]):
            with self.assertRaises(SystemExit):
                sync.main()


if __name__ == "__main__":
    unittest.main()
