"""Create or promote a paper for manual review without replacing existing files."""
import argparse
import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from collector.collect import ROOT, atomic_json, base_id, metadata_record, read_json, stable_id, utcnow

parser = argparse.ArgumentParser(description=__doc__)
sub = parser.add_subparsers(dest="command", required=True)
add = sub.add_parser("add")
add.add_argument("arxiv_id")
add.add_argument("--title", required=True)
promote = sub.add_parser("promote")
promote.add_argument("arxiv_id")
promote.add_argument("--reviewer", required=True)
args = parser.parse_args()
aid, version = base_id(args.arxiv_id)
destination = ROOT / "data/curated" / (stable_id(aid) + ".json")
if destination.exists():
    parser.error("Existing curated record is protected. Review and edit it manually.")
now = utcnow()
if args.command == "add":
    entry = {"arxiv_id": aid, "version": version or 1, "title": args.title, "authors": [], "published": now, "updated": now, "abstract": ""}
    p = metadata_record(entry, now)
    p.update({"publishedAt": None, "versionUpdatedAt": None, "version": version, "paperUrl": f"https://arxiv.org/abs/{aid}" + (f"v{version}" if version else ""), "sources": []})
    p["provenance"].update({"method": "manual", "generatedAt": None, "materialScope": "manual", "materialHash": None, "materialVersion": f"v{version}" if version else None})
else:
    source = ROOT / "data/drafts" / (stable_id(aid) + ".json")
    if not source.exists():
        parser.error("No matching draft")
    p = copy.deepcopy(read_json(source))
    # Promotion starts a human review; it does not invent a completed review.
    p["review"] = {"status": "needs_review", "reviewer": args.reviewer, "reviewedAt": None}
    p["publication"] = "pending"
    p["provenance"]["method"] = "manual"
    p["updatedAt"] = now[:10]
atomic_json(destination, p)
print(f"Created pending manual record: {destination.name}. Fill verified fields, then validate before listing.")
