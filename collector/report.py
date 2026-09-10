"""Produce a review digest without treating source text as markup."""
import html
import re


def safe_text(value):
    text = html.escape(str(value), quote=True).replace("@", "&#64;")
    return re.sub(r"([\\`*_{}\[\]()|#!])", r"\\\1", " ".join(text.split()))


def digest(result, limit=2):
    counts = result.get("quality_counts", {})
    lines = ["## 论文采集与质量候选", "",
             "以下是摘要级证据筛选，不是论文质量认证。自动收录仍需人工核对贡献、数据、指标和污染风险。", "",
             f"新增 {result.get('new', 0)} / 更新 {result.get('updated', 0)} / 跳过 {result.get('skipped', 0)} / 失败 {result.get('failed', 0)}；读取 {result.get('pages', 0)} 页。",
             f"优先审核 {counts.get('priority_review', 0)} / 待补充证据 {counts.get('needs_evidence', 0)} / 范围排除 {counts.get('excluded', 0)}。",
             f"本轮保存草稿 {len(result.get('changes', []))}；剩余队列 {result.get('queue_remaining', 0)}。", ""]
    if result.get("daily_intake"):
        intake = result["daily_intake"]
        lines += [f"当日处理名额：{intake['used']}/{intake['limit']}（{safe_text(intake['date'])}，{safe_text(intake['timezone'])}）。", ""]
    if result.get("dry_run"):
        lines += ["**本次为 dry-run：以上保存数量与配额均为预览，不写入资料、不调用模型、不创建 PR、不发布。**", ""]
    if not result.get("model_available"):
        lines += ["**未配置模型：仅保存元数据和原文证据，中文简介留空，未生成任何模型简介。**", ""]
    lines += ["### 优先审核候选", ""]
    changed_ids = {p["id"] for p in result.get("changes", [])}
    candidates = [p for p in result.get("quality_candidates", []) if p["decision"] == "priority_review" and (p["id"] in changed_ids or "changes" not in result)][:limit]
    if not candidates:
        lines += ["本轮没有新增送审草稿；其他候选继续留在队列。完整结果见采集 artifact 和 atlas-state 分支。", ""]
    for p in candidates:
        lines += [f"#### {safe_text(p['title'][:240])}", "",
                  f"[arXiv {safe_text(p['arxivId'])} v{p['version']}]({p['paperUrl']}) · 审核优先级 {p['score']}/{p['scoreMax']}（不是质量评分）", ""]
        for e in p["evidence"]:
            lines += [f"- {safe_text(e['label'])}：{safe_text(e['excerpt'][:360])}"]
        if p["missingSignals"]:
            lines += ["", "待补充：" + "；".join(safe_text(v) for v in p["missingSignals"])]
        lines += [""]
    lines += ["### 人工审核清单", "",
              "- [ ] 论文确实提出基准/环境/评测框架，而非仅报告已有基准成绩。",
              "- [ ] 任务定义、数据构建、数据许可、划分和评价指标可核对。",
              "- [ ] 有合适基线，说明评测覆盖范围、限制和数据污染风险。",
              "- [ ] 官方代码/数据链接实际可用，且来源归属经过核查。",
              "- [ ] 简介材料范围和复现状态如实标注；没有执行论文仓库代码。", ""]
    return "\n".join(lines)
