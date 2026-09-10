"""Write a compact, escaped GitHub review digest from a collection report."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from collector.report import digest

report = json.loads(Path(sys.argv[1]).read_text())
print(digest(report))
