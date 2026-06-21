"""Reader for the distributed dimension-provenance blocks.

The former ``cad/config/dimensions.yaml`` narrative was spread into per-part
``dimensions:`` blocks (in each part's ``cad/config/parts/<stem>.yaml`` registry
row) plus a handful of standalone narrative files under ``cad/config/dimensions/``
for content that maps to no single part (overall-machine, system-level, the
appendices, the alignment pinion). This module reads those blocks back so
``verify.py`` can still cross-check the build config (machine/*.yaml,
channels.yaml) against the cited research dimensions -- the drift gate.

A "source" is either a part stem (``"cone-gear"``) or a standalone slug
(``"chapter-25-pinion-gear"``); ``find_row`` locates a dimension table row by the
label in its first column.
"""
from __future__ import annotations

import functools
from pathlib import Path
from typing import Any

import yaml

CONFIG = Path(__file__).resolve().parent.parent / "config"
PARTS_DIR = CONFIG / "parts"
STANDALONE_DIR = CONFIG / "dimensions"

# Columns a dimension table may use for its first (label) column.
_LABEL_KEYS = ("dim", "item", "fact", "part")


@functools.lru_cache(maxsize=None)
def content_of(source: str) -> list[dict[str, Any]]:
    """The ordered content list (``notes`` / ``table`` items) for a part stem or
    a standalone ``dimensions/<slug>.yaml`` file."""
    part_file = PARTS_DIR / f"{source}.yaml"
    if part_file.exists():
        data = yaml.safe_load(part_file.read_text(encoding="utf-8"))
        record = next(iter(data.values()))
        block = record.get("dimensions")
        if not block:
            raise KeyError(f"part {source!r} has no dimensions block")
        return block["content"]
    standalone = STANDALONE_DIR / f"{source}.yaml"
    if standalone.exists():
        return yaml.safe_load(standalone.read_text(encoding="utf-8"))["content"]
    raise FileNotFoundError(f"no dimensions source: {source!r}")


def find_row(source: str, label_prefix: str) -> dict[str, Any] | None:
    """First table row in ``source`` whose first-column label starts with
    ``label_prefix``. Returns the row mapping (carrying a ``value`` key), or
    ``None`` if absent / only present as a verbatim (``raw``/``cells``) row."""
    for item in content_of(source):
        for row in item.get("table", []):
            if not isinstance(row, dict):
                continue
            label = next((row[k] for k in _LABEL_KEYS if k in row), None)
            if isinstance(label, str) and label.startswith(label_prefix):
                return row
    return None
