"""Derive GitHub Pages paths from repository metadata, not paper content."""
import os
import re

owner, repository = os.environ["GITHUB_REPOSITORY"].split("/")
if not all(re.fullmatch(r"[A-Za-z0-9_.-]+", part) for part in [owner, repository]):
    raise ValueError("Invalid repository identity")
base = "/" if repository.lower() == f"{owner.lower()}.github.io" else f"/{repository}"
with open(os.environ["GITHUB_ENV"], "a") as output:
    output.write(f"SITE_URL=https://{owner}.github.io\nBASE_PATH={base}\n")
