"""Decide whether a daily run needs collection, publication retry, or no work."""
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import subprocess
from zoneinfo import ZoneInfo


def parse_time(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def decide(state, deployment, *, now, mode="auto", event="schedule", queue_only=False):
    if event != "schedule":
        if queue_only:
            return {"action": "queue", "reason": "手动选择仅整理已完整采集的材料，不请求 arXiv；仍检查材料新鲜度与每日配额。"}
        return {"action": "collect", "reason": "手动触发，执行一次采集；仍遵守每日配额和接口冷却。"}
    ready = state.get("last_publishable_collection_at", state.get("last_successful_collection_at"))
    local = ZoneInfo("Asia/Shanghai")
    if ready and parse_time(ready).astimezone(local).date() == parse_time(now).astimezone(local).date():
        deployed = deployment.get("last_successful_deployment_at")
        reviewed = state.get("last_review_publication_at")
        done = deployed if mode == "auto" else reviewed
        if done and parse_time(done) >= parse_time(ready):
            return {"action": "skip", "reason": "今天已成功整理并完成发布，本次补跑跳过。"}
        return {"action": "publish", "reason": "今天整理已成功，仅重试校验、构建与发布，不重复请求 arXiv 或模型。"}
    retry_at = state.get("arxiv_retry_after")
    if retry_at and parse_time(retry_at) > parse_time(now):
        if state.get("last_successful_collection_at") and state.get("queue"):
            return {"action": "queue", "reason": f"arXiv 冷却至 {retry_at}；仅尝试整理近期完整采集的材料，不请求 arXiv。"}
        return {"action": "skip", "reason": f"arXiv 冷却中，最早重试时间为 {retry_at}，等待后续补跑。"}
    collected = state.get("last_successful_collection_at")
    if collected and parse_time(collected).astimezone(local).date() == parse_time(now).astimezone(local).date():
        return {"action": "queue", "reason": "今天发现步骤已完成，只处理已采集材料，不重复扫描 arXiv。"}
    return {"action": "collect", "reason": "今天尚未完成采集与发布，从持久进度继续。"}


def remote_json(repository, path):
    # Raw content also supports the state file when it grows beyond 1 MB.
    result = subprocess.run(["gh", "api", "-H", "Accept: application/vnd.github.raw+json",
                             f"repos/{repository}/contents/{path}?ref=atlas-state"],
                            capture_output=True, text=True, check=False)
    if result.returncode:
        if "HTTP 404" in result.stderr:
            return {}
        raise RuntimeError("Cannot read durable scheduling state; refusing an unverified retry")
    return json.loads(result.stdout)


def main():
    event = os.getenv("GITHUB_EVENT_NAME", "workflow_dispatch")
    state, deployment = {}, {}
    if event == "schedule":
        repository = os.environ["GITHUB_REPOSITORY"]
        state = remote_json(repository, "automation/state.json")
        deployment = remote_json(repository, "automation/deployment.json")
    result = decide(state, deployment, now=datetime.now(timezone.utc).isoformat(),
                    mode=os.getenv("PUBLISH_MODE", "review"), event=event,
                    queue_only=os.getenv("QUEUE_ONLY", "false").lower() == "true")
    print(json.dumps(result, ensure_ascii=False))
    if os.getenv("GITHUB_OUTPUT"):
        with Path(os.environ["GITHUB_OUTPUT"]).open("a") as handle:
            handle.write(f"action={result['action']}\n")
    if os.getenv("GITHUB_STEP_SUMMARY"):
        with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a") as handle:
            handle.write("## 每日采集检查\n\n" + result["reason"] + "\n")


if __name__ == "__main__":
    main()
