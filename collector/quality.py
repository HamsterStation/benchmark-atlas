"""Explainable abstract-level triage; evidence is not a quality endorsement."""
import hashlib
import json
import re
from urllib.parse import urlparse

SUBJECT = re.compile(r"\b(?:llms?|(?:large |multimodal )?language models?|foundation models?|(?:general )?ai assistants?|language agents?|llm[- ](?:based |powered )?agents?)\b", re.I)
BENCHMARK = re.compile(r"\b(?:benchmarks?|testbeds?|evaluation (?:frameworks?|suites?|datasets?|environments?)|datasets?|evaluation sets?)\b", re.I)
EVALUATION_RESOURCE = re.compile(r"\b(?:benchmarks?|testbeds?|evaluation (?:frameworks?|suites?|datasets?|environments?|sets?))\b", re.I)
CONTRIBUTION = re.compile(r"\b(?:we|this (?:paper|work|study))\s+(?:(?:therefore|thus|here|also|further|first)\s+)?(?:introduce[sd]?|present[sd]?|propose[sd]?|release[sd]?|construct[sd]?|develop[sd]?|build[sd]?|contribute[sd]?)\b", re.I)
METHOD = re.compile(r"\b(?:method|algorithm|model|training (?:method|framework)|architecture|approach)\b", re.I)
USES = re.compile(r"\b(?:evaluat\w*|test\w*|experiment\w*|outperform\w*|achiev\w*)\b.{0,100}\b(?:on|across|using)\b.{0,100}\b(?:benchmarks?|datasets?)\b", re.I)
PATTERNS = {
    "task_definition": r"\b(?:tasks?|questions?|problems?|interactive environments?|web(?:sites?| browsing)|tool[- ]use|code generation|software engineering)\b",
    "evaluation_protocol": r"\b(?:metrics?|scoring|accuracy|success rate|pass@\d+|evaluation protocol|functional correctness|held[- ]out|train[/-]test|test split|answer correctness|human evaluation)\b",
    "baseline_comparison": r"\b(?:baselines?|compar(?:e|es|ed|ing|ison)|evaluat\w*\s+(?:\w+\s+){0,3}(?:\d+|several|multiple|various|diverse)\s+(?:\w+\s+){0,3}(?:models?|agents?|llms?)|state[- ]of[- ]the[- ]art models?)\b",
    "scale_or_coverage": r"\b\d[\d,.]*\s*(?:k\s+)?(?:\w+\s+){0,2}(?:tasks?|questions?|problems?|domains?|environments?|websites?|instances?|samples?|examples?)\b",
    "validity_analysis": r"\b(?:contamination|data leakage|generalization|generalisation|robustness|human[- ](?:verified|validated|annotated)|expert[- ](?:verified|validated|annotated)|inter[- ]annotator)\b",
}


def sentences(text):
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+(?=[A-Z])|[\r\n]+", text) if part.strip()]


def policy_hash(config):
    return hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()


def assess(entry, config, now):
    abstract = entry.get("abstract", "")
    parts = [(sentence, "abstract") for sentence in sentences(abstract)]
    title = entry["title"]
    paper_url = f"https://arxiv.org/abs/{entry['arxiv_id']}v{entry['version']}"
    evidence = []

    def add(signal, excerpt, source="abstract"):
        rule = config["signals"][signal]
        evidence.append({"signal": signal, "label": rule["label"], "weight": rule["weight"], "excerpt": excerpt[:1200], "source": source, "sourceUrl": paper_url})

    contributions = []
    for sentence, _ in parts:
        verb = CONTRIBUTION.search(sentence)
        if not verb:
            continue
        following = sentence[verb.end():]
        benchmark = BENCHMARK.search(following[:200])
        method = METHOD.search(following[:200])
        evaluation_resource = EVALUATION_RESOURCE.search(following[:200])
        evaluation_purpose = re.search(r"\b(?:to|for)\s+(?:systematically\s+)?(?:evaluat\w*|benchmark\w*|assess\w*)\b(?!\s+(?:our|the proposed)\s+(?:method|model|approach))", following, re.I)
        # A proposed method evaluated on existing benchmarks is not a new benchmark.
        if benchmark and (evaluation_resource or evaluation_purpose) and (not method or benchmark.start() < method.start()) and not re.search(r"\b(?:evaluated|evaluating|tested|using|on existing)\b", following[:benchmark.start()], re.I):
            contributions.append(sentence)
    if contributions:
        add("benchmark_contribution", contributions[0])
    for signal, pattern in PATTERNS.items():
        match = next((sentence for sentence, _ in parts if re.search(pattern, sentence, re.I)), None)
        if match:
            add(signal, match)
    resources = []
    for material, kind in [(abstract, "abstract"), (entry.get("comment", ""), "arxiv_comment")]:
        for match in re.finditer(r"https://[^\s<>\"{}\[\]()\\`|^]+", material):
            url = match.group().rstrip(".,;:)]")
            parsed = urlparse(url)
            if parsed.username or parsed.password or not parsed.hostname:
                continue
            host = parsed.hostname.lower()
            if (host in ["github.com", "huggingface.co", "gitlab.com"] and parsed.path.strip("/")) or host.endswith(".github.io"):
                if url not in resources:
                    resources.append(url)
                if not any(e["signal"] == "resource_link" for e in evidence):
                    add("resource_link", url, kind)

    relevant = bool(SUBJECT.search(title + " " + abstract))
    has_benchmark = bool(BENCHMARK.search(title + " " + abstract))
    review_article = bool(re.search(r"\b(?:survey|systematic review|position paper)\b", title, re.I))
    uses_only = not contributions and bool(USES.search(abstract)) and any(CONTRIBUTION.search(s) and METHOD.search(s) for s, _ in parts)
    signals = {e["signal"] for e in evidence}
    score = sum(e["weight"] for e in evidence)
    reasons = []
    if not relevant or not has_benchmark:
        decision = "excluded"
        reasons.append("未找到 LLM / Agent 评测对象与基准主题的共同证据")
    elif review_article and not contributions:
        decision = "excluded"
        reasons.append("综述或观点文章，当前材料未见提出新基准")
    elif uses_only:
        decision = "excluded"
        reasons.append("材料表明提出方法并使用已有基准评估，未见新基准贡献")
    elif contributions and "evaluation_protocol" in signals and ("resource_link" in signals if config.get("require_resource_link", True) else bool(signals.intersection({"resource_link", "baseline_comparison"}))) and score >= config["min_priority_score"]:
        decision = "priority_review"
        reasons.append("新基准贡献、评分协议和资源证据达到配置的送审门槛；链接内容仍需人工核查")
    else:
        decision = "needs_evidence"
        reasons.append("摘要级材料不足以进入优先审核，等待补充官方材料")
    return {
        "schemaVersion": 1, "id": "arxiv-" + entry["arxiv_id"].replace("/", "-"),
        "arxivId": entry["arxiv_id"], "version": entry["version"], "title": title,
        "paperUrl": paper_url, "assessedAt": now, "policyVersion": config["version"], "policyHash": policy_hash(config),
        "materialHash": hashlib.sha256(json.dumps(entry, ensure_ascii=False, sort_keys=True).encode()).hexdigest(),
        "materialScope": "abstract_and_arxiv_metadata", "decision": decision, "score": score,
        "scoreMax": sum(v["weight"] for v in config["signals"].values()), "reasons": reasons,
        "missingSignals": [rule["label"] for key, rule in config["signals"].items() if key not in signals],
        "evidence": evidence, "resourceCandidates": resources[:10],
        "declaredVenue": entry.get("journal_ref") or entry.get("comment") or None,
        "venueVerified": False, "qualityVerified": False,
    }
