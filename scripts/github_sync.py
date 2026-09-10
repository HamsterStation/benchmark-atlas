"""Persist automation state or maintain one review PR, only in explicitly enabled CI."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from collector.collect import ROOT, atomic_json, read_json, utcnow


def run(args, cwd=ROOT, check=True):
    return subprocess.run(args, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=check)


def branch_exists(remote, branch):
    result = run(["git", "ls-remote", "--exit-code", "--heads", remote, branch], check=False)
    if result.returncode not in [0, 2]:
        raise RuntimeError("Cannot query remote; refusing to treat an API failure as a missing state branch")
    return result.returncode == 0


def clone_branch(remote, branch, directory, allow_new=False):
    if branch_exists(remote, branch):
        shallow = ["--depth", "1"] if branch == "atlas-state" else []
        run(["git", "clone", "--quiet", "--single-branch", *shallow, "--branch", branch, remote, str(directory)])
    elif allow_new:
        directory.mkdir()
        run(["git", "init", "--initial-branch", branch], directory)
        run(["git", "remote", "add", "origin", remote], directory)
    else:
        return False
    run(["git", "config", "user.name", "github-actions[bot]"], directory)
    run(["git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com"], directory)
    return True


def copy_file(source, destination):
    if source.is_symlink():
        raise ValueError("Symlinks are not accepted as data")
    if source.is_file():
        read_json(source)  # Reject non-JSON data before carrying it between branches.
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)


def copy_drafts(source, destination):
    import re
    for item in (source / "data/drafts").glob("*.json"):
        if not re.fullmatch(r"arxiv-[A-Za-z0-9.-]+\.json", item.name):
            raise ValueError("Unexpected draft filename")
        copy_file(item, destination / "data/drafts" / item.name)


def commit_push(directory, branch, message):
    run(["git", "add", "--all"], directory)
    if run(["git", "diff", "--cached", "--quiet"], directory, check=False).returncode == 0:
        return False
    run(["git", "commit", "-m", message], directory)
    run(["git", "push", "origin", f"HEAD:refs/heads/{branch}"], directory)
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["restore", "persist", "review", "deployment"])
    parser.add_argument("--base", default=os.getenv("DEFAULT_BRANCH", "main"))
    parser.add_argument("--report", type=Path, default=ROOT / "work/collection-report.json")
    args = parser.parse_args()
    if os.getenv("GITHUB_ACTIONS") != "true":
        parser.error("This script only runs in GitHub Actions; local work never pushes or opens PRs")
    if args.action != "restore" and os.getenv("ATLAS_WRITE_ENABLED") != "true":
        parser.error("Explicit CI write enablement is required")
    repository = os.environ["GITHUB_REPOSITORY"]
    remote = f"https://github.com/{repository}.git"
    run(["gh", "auth", "setup-git"])
    with tempfile.TemporaryDirectory(prefix="atlas-sync-") as temp:
        directory = Path(temp) / "repo"
        if args.action in ["restore", "persist", "deployment"]:
            exists = clone_branch(remote, "atlas-state", directory, allow_new=args.action != "restore")
            if not exists:
                print("No persisted state branch yet; starting from checked-in initial state.")
                return
            if args.action == "restore":
                for filename in ["state.json", "deployment.json"]:
                    copy_file(directory / "automation" / filename, ROOT / "automation" / filename)
                copy_drafts(directory, ROOT)
                print("Restored durable queue, cursors, drafts and deployment record.")
                return
            if args.action == "persist":
                copy_file(ROOT / "automation/state.json", directory / "automation/state.json")
                copy_drafts(ROOT, directory)
            else:
                atomic_json(directory / "automation/deployment.json", {"last_successful_deployment_at": utcnow(),
                    "run_url": f"https://github.com/{repository}/actions/runs/{os.environ['GITHUB_RUN_ID']}", "commit": os.environ["GITHUB_SHA"]})
            commit_push(directory, "atlas-state", f"chore: record atlas {args.action}")
            return
        if not clone_branch(remote, args.base, directory):
            raise RuntimeError("Default branch is unavailable")
        branch = "atlas-review"
        if branch_exists(remote, branch):
            run(["git", "fetch", "origin", f"{branch}:refs/remotes/origin/{branch}"], directory)
            run(["git", "switch", "--create", branch, "--track", f"origin/{branch}"], directory)
            # Conflicts or branch protection stop the run; never force push.
            run(["git", "merge", "--no-edit", f"origin/{args.base}"], directory)
        else:
            run(["git", "switch", "--create", branch], directory)
        copy_drafts(ROOT, directory)
        run(["git", "add", "--all"], directory)
        changed = run(["git", "diff", "--cached", "--quiet"], directory, check=False).returncode != 0
        if changed:
            copy_file(ROOT / "automation/state.json", directory / "automation/state.json")
            copy_file(ROOT / "automation/deployment.json", directory / "automation/deployment.json")
            commit_push(directory, branch, "chore: update benchmark paper drafts for review")
        elif not branch_exists(remote, branch):
            print("No new draft changes; no PR required.")
            return
        else:
            run(["git", "push", "origin", f"HEAD:refs/heads/{branch}"], directory)
        # Squash merges can leave old commits on the reusable branch; compare trees.
        if run(["git", "diff", "--quiet", f"origin/{args.base}", "HEAD"], directory, check=False).returncode == 0:
            return
        report = read_json(args.report, {})
        counts = {key: report.get(key, 0) for key in ["new", "updated", "skipped", "pending_review", "failed"]}
        body = ("自动采集的论文草稿等待维护者审核。仅依据 arXiv 元数据与摘要，不代表全文解读或实测复现。\n\n"
                "本次计数：" + json.dumps(counts, ensure_ascii=False) + "\n\n"
                "review 模式只发布 data/curated。请使用手工提升命令创建待审核副本，核对来源、版本与分类后，再将审核完成的条目标为 listed。"
                "仅合并机器草稿不会让它进入正式索引。人工资料与 notes/ 不由采集程序修改。\n\n"
                "此 PR 由 GITHUB_TOKEN 维护；不要依赖机器人推送再次触发 CI。采集工作流已运行字段校验、测试与生产构建，合并前可手动运行 CI 验证此分支。\n")
        body_path = Path(temp) / "pr-body.md"
        body_path.write_text(body)
        prs = json.loads(run(["gh", "pr", "list", "--repo", repository, "--head", branch, "--base", args.base, "--state", "open", "--json", "number"], directory).stdout)
        if prs:
            run(["gh", "pr", "edit", str(prs[0]["number"]), "--repo", repository, "--body-file", str(body_path)], directory)
        else:
            run(["gh", "pr", "create", "--repo", repository, "--base", args.base, "--head", branch, "--title", "审核 Benchmark 论文采集草稿", "--body-file", str(body_path)], directory)


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as error:
        print(f"GitHub synchronization failed ({error.returncode}); no force push or protection bypass attempted.", file=sys.stderr)
        sys.exit(1)
