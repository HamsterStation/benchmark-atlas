"""One budgeted request using saved paper materials; no draft writes or publishing."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.error import HTTPError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from collector.collect import ROOT, Collector, atomic_json, metadata_record, read_json, utcnow


def diagnose(root, *, reserve, model=None):
    now = utcnow()
    collector = Collector(root, dry_run=True, model=model, now=now)
    result = {"checked_at": now, "model_configured": collector.model.available,
              "model_calls": 0, "ok": False, "drafts_written": 0, "published": False}
    if not collector.model.available:
        return {**result, "error": "ModelUnavailable"}
    ready = collector.ready_materials()
    if not ready:
        return {**result, "error": "NoCompletedMaterials"}
    aid = next(iter(sorted(ready)))
    entry = collector.state["queue"][aid]["entry"]
    # Reserve from the same persistent daily budget before any model request.
    state = read_json(Path(root) / "automation/state.json")
    day = now[:10]
    used = state.setdefault("model_usage", {}).get(day, 0)
    if used >= collector.config["model_daily_limit"]:
        return {**result, "error": "DailyModelLimit"}
    state["model_usage"][day] = used + 1
    reserve(state)
    result.update(model_calls=1, material_id=aid, model=collector.model.name,
                  protocol=getattr(collector.model, "protocol", "fixture"))
    material = json.dumps({"title": entry["title"], "abstract": entry["abstract"]}, ensure_ascii=False)
    material = material[:collector.config["model_max_input_chars"]]
    try:
        output = collector.model.generate(material, collector.taxonomy)
        fields = {"role", "targets", "scenarios", "capabilities", "summaryZh", "taskFormat", "acronym"}
        if not isinstance(output, dict) or set(output) != fields:
            raise ValueError("Unexpected response shape")
        record = metadata_record(entry, now)
        record.update(output)
        collector.validator.validate(record)
        if not output["summaryZh"] or not re.search(r"[\u3400-\u9fff]", output["summaryZh"]):
            raise ValueError("Missing Chinese summary")
        result.update(ok=True, response_schema_valid=True, chinese_summary_present=True)
    except HTTPError as error:
        categories = {401: "AuthenticationRejected", 402: "PaymentOrQuotaRejected",
                      403: "AccessForbidden", 404: "RouteOrModelUnavailable", 429: "RateLimited"}
        result.update(error="HTTPError", http_status=error.code,
                      category=categories.get(error.code, "ProviderHTTPFailure"))
    except Exception as error:
        # Never log a raw exception, provider body, credential, or generated content.
        result.update(error=type(error).__name__)
    return result


def main():
    if os.getenv("GITHUB_ACTIONS") != "true" or os.getenv("ATLAS_WRITE_ENABLED") != "true":
        raise RuntimeError("Diagnostics require explicit GitHub Actions execution")

    def reserve(state):
        atomic_json(ROOT / "automation/state.json", state)
        subprocess.run([sys.executable, str(ROOT / "scripts/github_sync.py"), "persist"],
                       check=True, stdout=subprocess.DEVNULL)

    result = diagnose(ROOT, reserve=reserve)
    atomic_json(ROOT / "work/model-diagnostic.json", result)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
