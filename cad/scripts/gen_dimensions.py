r"""Render the distributed dimension-provenance blocks into one DIMENSIONS.md view.

The dimension provenance used to live in a single ``cad/config/dimensions.yaml``;
it now lives in per-part ``dimensions:`` blocks (``cad/config/parts/<stem>.yaml``)
plus a few standalone narrative files under ``cad/config/dimensions/`` for content
that maps to no single part. ``verify.py`` reads those blocks directly (via
``_dimensions``) as the drift gate; this script just re-aggregates them, in book
order, into a single human-readable ``cad/DIMENSIONS.md``.

``DIMENSIONS.md`` is NOT committed (a generated copy under version control kept
drifting from its source) — it is an untracked, on-demand view. Edit the YAML,
never the rendered ``.md``.

Usage::

    python cad/scripts/gen_dimensions.py        # render -> cad/DIMENSIONS.md (untracked)

Needs only PyYAML; no SolidWorks. Run with the SW venv python (has PyYAML).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

import _dimensions

ROOT = Path(__file__).resolve().parent.parent
DIMENSIONS_MD = ROOT / "DIMENSIONS.md"

# Sources in book order: each is a part stem (its registry-row dimensions block)
# or a standalone slug under cad/config/dimensions/.
ORDER = [
    "_overview", "overall-machine", "system-level",
    "crank-arm", "cone-gear", "cylinder-gear", "rocker-arm", "amplitude-bar",
    "measuring-stick", "channel-lever", "summing-lever", "counter-spring",
    "magnifying-lever", "magnifying-wheel", "platen", "transgear-removable",
    "pen-marker", "chapter-25-pinion-gear",
    "appendix-a-legacy-constants", "appendix-b-parts-audit", "appendix-c-open-items",
]


def _raw_doc(source: str) -> dict[str, Any]:
    """The full mapping for a source (part dimensions block or standalone file)."""
    part_file = _dimensions.PARTS_DIR / f"{source}.yaml"
    if part_file.exists():
        record = next(iter(yaml.safe_load(part_file.read_text(encoding="utf-8")).values()))
        return record["dimensions"]
    return yaml.safe_load((_dimensions.STANDALONE_DIR / f"{source}.yaml").read_text(encoding="utf-8"))


def _render_table(rows: list[Any]) -> list[str]:
    # Column order = the first keyed row's keys (matches the source column order).
    cols: list[str] = []
    for row in rows:
        if isinstance(row, dict) and "raw" not in row and "cells" not in row:
            cols = list(row.keys())
            break
    out: list[str] = []
    if cols:
        out.append("| " + " | ".join(cols) + " |")
        out.append("|" + "|".join("---" for _ in cols) + "|")
    for row in rows:
        if "raw" in row:
            out.append(row["raw"])
        elif "cells" in row:
            out.append("| " + " | ".join(row["cells"]) + " |")
        else:
            out.append("| " + " | ".join(row.get(c, "") for c in cols) + " |")
    return out


def _render_source(source: str) -> str:
    doc = _raw_doc(source)
    parts: list[str] = ["## " + (doc.get("chapter") or doc.get("title") or source)]
    if "preamble" in doc:
        parts.append(doc["preamble"].rstrip("\n"))
    if "source_hierarchy" in doc:
        parts.append("### " + doc["source_hierarchy"])
    for item in doc["content"]:
        if "notes" in item:
            parts.append(item["notes"].rstrip("\n"))
        else:
            parts.append("\n".join(_render_table(item["table"])))
    return "\n\n".join(parts)


def main() -> int:
    body = "\n\n".join(_render_source(s) for s in ORDER)
    DIMENSIONS_MD.write_text("# Harmonic Analyzer — Dimension provenance\n\n" + body + "\n",
                             encoding="utf-8")
    print(f"generated -> {DIMENSIONS_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
