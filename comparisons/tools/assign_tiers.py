# /// script
# requires-python = ">=3.11"
# ///
"""Assign photo-fidelity priority tiers to every manifest pair.

Tiers gate iteration order: pose fixing and model tuning work P0 outward.

  p0  the 8 ch30 eight-views stations — canonical full-machine studio shots
  p1  book chapter studio photography (ch06, ch11-25, ch30 details) that is
      sharp, plus technical drawings — the authoritative geometry evidence
  p2  the real device at full fidelity: photogrammetry best-shots and the
      360-turntable frames (v6)
  p3  sharp video macros (v2/v4 synthesis & operation) and sharp machine
      shots from the remaining book chapters
  p4  everything else (remaining videos, soft/mixed shots, front-matter and
      output-trace chapters)

Usage:
    uv run comparisons/tools/assign_tiers.py
"""

import json
import re
from collections import Counter
from pathlib import Path

COMP = Path(__file__).resolve().parents[1]
REPO = COMP.parent
MANIFEST = COMP / "manifest.json"
CATALOG = REPO / "references" / "curation" / "stills_catalog.json"

P0 = {f"harmonic_analyzer--ch30-p{n:03d}-img01" for n in range(2, 10)}
P1_BOOK = {"ch06", *(f"ch{n}" for n in range(11, 26)), "ch30"}


def tier_for(pair: dict, entry: dict | None) -> int:
    if pair["id"] in P0:
        return 0
    if entry is None:  # photogrammetry (not in the stills catalog)
        return 2
    src, quality, cls = entry["source"], entry.get("quality"), entry.get("class")
    if cls == "drawing":
        return 1
    if src in P1_BOOK and quality == "sharp":
        return 1
    if src == "video6":
        return 2
    if src in ("video2", "video4") and quality == "sharp" and cls in ("machine", "machine-detail"):
        return 3
    if src.startswith("ch") and quality == "sharp" and cls in ("machine", "machine-detail"):
        return 3
    return 4


def main() -> int:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    entries = {e["id"]: e for e in json.loads(CATALOG.read_text(encoding="utf-8"))["entries"]}
    counts: Counter[int] = Counter()
    for pair in manifest["pairs"]:
        catalog_id = re.sub(r"^[a-z0-9_]+--", "", pair["id"])
        pair["tier"] = tier_for(pair, entries.get(catalog_id))
        counts[pair["tier"]] += 1
    MANIFEST.write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    for t in sorted(counts):
        print(f"p{t}: {counts[t]} pairs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
