# /// script
# requires-python = ">=3.11"
# ///
"""Merge per-agent curation batch fragments into stills_catalog.json.

Validates component vocabulary against cad/scripts/build_*.py stems, checks
image paths exist, and reports id collisions.

Usage:
    uv run comparisons/tools/merge_catalog.py
"""

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BATCHES = REPO / "references" / "curation" / "batches"
OUT = REPO / "references" / "curation" / "stills_catalog.json"

CLASSES = {"machine", "machine-detail", "diagram", "drawing", "person", "title", "text", "mixed"}
QUALITIES = {"sharp", "soft", "blurred"}


def vocabulary() -> set[str]:
    stems = set()
    for f in (REPO / "cad" / "scripts").glob("build_*.py"):
        stem = f.stem.removeprefix("build_")
        if stem == "all":
            continue
        stems.add(stem.removesuffix("_assembly") if stem.endswith("_assembly") else stem)
    return stems


def main() -> int:
    vocab = vocabulary()
    entries: dict[str, dict] = {}
    problems: list[str] = []

    for frag in sorted(BATCHES.glob("*.json")):
        items = json.loads(frag.read_text(encoding="utf-8"))
        if isinstance(items, dict):
            items = items.get("entries", [])
        for e in items:
            eid = e.get("id", "")
            if not eid:
                problems.append(f"{frag.name}: entry missing id: {e.get('path')}")
                continue
            if eid in entries:
                problems.append(f"{frag.name}: duplicate id {eid}")
                continue
            if e.get("class") not in CLASSES:
                problems.append(f"{frag.name}: {eid}: bad class {e.get('class')!r}")
            if e.get("quality") not in QUALITIES:
                problems.append(f"{frag.name}: {eid}: bad quality {e.get('quality')!r}")
            unknown = [c for c in e.get("components", []) if c not in vocab]
            if unknown:
                problems.append(f"{frag.name}: {eid}: unknown components {unknown}")
            if not (REPO / e.get("path", "")).is_file():
                problems.append(f"{frag.name}: {eid}: path missing {e.get('path')}")
            entries[eid] = e

    kept = sum(1 for e in entries.values() if e.get("keep"))
    OUT.write_text(json.dumps({"entries": sorted(entries.values(), key=lambda e: e["id"])},
                              indent=1), encoding="utf-8")
    print(f"merged {len(entries)} entries ({kept} keep=true) from "
          f"{len(list(BATCHES.glob('*.json')))} fragments -> {OUT}")
    for p in problems:
        print(f"  PROBLEM {p}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
