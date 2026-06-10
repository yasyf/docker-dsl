from __future__ import annotations

import re
from pathlib import Path

# Great Docs copies this script into the build dir (great-docs/scripts/) and
# Quarto runs it from there as a pre-render step, with the staged .qmd pages
# under the build dir and the repo at its parent. parents[1] is therefore the
# build dir either way (build copy or in-place run), so examples/ resolves to
# the repo-root recipes the snapshot suite tests.
BUILD_DIR = Path(__file__).resolve().parents[1]
EXAMPLES = BUILD_DIR.parent / "examples"
MARKER = re.compile(r"<!-- gd-embed: (\w+)\.py -->")


def embed(match: re.Match[str]) -> str:
    return f"```python\n{(EXAMPLES / f'{match.group(1)}.py').read_text().rstrip()}\n```"


def main() -> None:
    for qmd in BUILD_DIR.rglob("*.qmd"):
        if (new := MARKER.sub(embed, text := qmd.read_text())) != text:
            qmd.write_text(new)


if __name__ == "__main__":
    main()
