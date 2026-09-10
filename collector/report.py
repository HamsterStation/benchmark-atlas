"""Produce a review digest without treating source text as markup."""
import html
import re


def safe_text(value):
    text = html.escape(str(value), quote=True).replace("@", "&#64;")
    return re.sub(r"([\\`*_{}\[\]()|#!])", r"\\\1", " ".join(text.split()))


def digest(result, limit=2):
    counts = result.get("quality_counts", {})
    lines = ["## 论文采集与质量候选", "",
             "按摘要级证据与首发时间筛选候选，达到门槛即可自动收录；来源范围及复现状态如实记录。", "",
             f"新增 {result.get('new', 0)} / 更新 {result.get('updated', 0)} / 跳过 {result.get('skipped', 0)} / 失败 {result.get('failed', 0)}；读取 {result.get('pages', 0)} 页。",
             f"规则变更复筛 {result.get('reassessed', 0)} 篇（与论文版本更新分开计数）。",
             f"证据达标 {counts.get('priority_review', 0)} / 待补充证据 {counts.get('needs_evidence', 0)} / 范围排除 {counts.get('excluded', 0)}。",
             f"本轮保存草稿 {len(result.get('changes', []))}；剩余队列 {result.get('queue_remaining', 0)}。", ""]
    if result.get("selection_policy"):
        policy = result["selection_policy"]
        windows = " → ".join(str(day) + " 天" for day in policy["freshness_days"])
        candidates = result.get("selection_candidates", [])
        eligible = sum(p["eligible"] and p["decision"] == "priority_review" for p in candidates)
        archived = sum(p["band"] == "archive" and p["decision"] != "excluded" for p in candidates)
        lines += [f"新论文时间档：{windows}；同档优先 Agent / 编程方向，再按证据完整度和首发时间排序，最低 {policy['min_score']} 分。",
                  f"同时满足证据与时间条件 {eligible} 篇；超出近期窗口保留 {archived} 篇，不占当日名额。", ""]
        if policy.get("scope"):
            lines += [safe_text(policy["scope"]["note"]), ""]
    if result.get("daily_intake"):
        intake = result["daily_intake"]
        lines += [f"当日处理名额：{intake['used']}/{intake['limit']}（{safe_text(intake['date'])}，{safe_text(intake['timezone'])}）。", ""]
    if result.get("dry_run"):
        lines += ["**本次为 dry-run：以上保存数量与配额均为预览，不写入资料、不调用模型、不创建 PR、不发布。**", ""]
    if not result.get("model_available"):
        lines += ["**未配置模型：仅保存元数据和原文证据，中文简介留空，未生成任何模型简介。**", ""]
    lines += ["### 本轮处理候选", ""]
    changed_ids = {p["id"] for p in result.get("changes", [])}
    candidates = [p for p in result.get("quality_candidates", []) if p["decision"] == "priority_review" and (p["id"] in changed_ids or "changes" not in result)][:limit]
    if not candidates:
        lines += ["本轮没有新增处理草稿；其他候选继续留在队列。完整结果见采集 artifact 和 atlas-state 分支。", ""]
    for p in candidates:
        lines += [f"#### {safe_text(p['title'][:240])}", "",
                  f"[arXiv {safe_text(p['arxivId'])} v{p['version']}]({p['paperUrl']}) · 证据信号 {p['score']}/{p['scoreMax']}（不是质量评分）", ""]
        for e in p["evidence"]:
            lines += [f"- {safe_text(e['label'])}：{safe_text(e['excerpt'][:360])}"]
        if p["missingSignals"]:
            lines += ["", "待补充：" + "；".join(safe_text(v) for v in p["missingSignals"])]
        lines += [""]
    lines += ["代码和数据链接目前是来源材料提供的线索，完整评测质量与资源内容未逐项核实。没有执行论文仓库代码。", ""]
    return "\n".join(lines)
