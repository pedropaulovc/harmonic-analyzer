"""Native dimension text runs, as blocking settled ink checks must read them.

``_dump_annotation`` keeps each run's native reference anchor and the width
SolidWorks reports for it (``w``). Without PDF ink, ``annotation_geometry``
reads every run position as lower-left and estimates each row's last run at a
glyph advance. A check that refuses export normalizes the anchors first and
boxes measured runs at their native widths.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

from _layout_audit import _TEXT_ANCHORS, display_box, text_items
from _layout_geometry import Box


def lower_left_texts(record: dict[str, Any], *, label: str) -> dict[str, Any]:
    """``record`` with each text run's position moved to its lower-left corner.

    ``_dump_annotation`` keeps each run's ``GetTextRefPositionAtIndex`` anchor
    (``ref``), but ``display_box`` and the shared audit's row boxes read the
    position as the lower-left. The audit's ``_TEXT_ANCHORS`` gives each
    anchor as fractions of the run's width and cap height; this sheet's native
    runs are all lower-left (``ref`` 1). A horizontal fraction needs the run's
    width, so a run without one must be left-anchored; an unknown anchor is
    refused rather than read as lower-left.
    """
    texts = record["display"]["texts"]
    runs = []
    for run in texts:
        reference = int(run.get("ref", -1))
        if reference not in _TEXT_ANCHORS:
            raise RuntimeError(
                f"{label}: text run {run.get('t')!r} has unknown anchor {reference}"
            )
        fx, fy = _TEXT_ANCHORS[reference]
        width = float(run.get("w") or 0.0)
        if fx and not width > 0.0:
            raise RuntimeError(
                f"{label}: text run {run.get('t')!r} is anchored {fx:g} along a "
                "width SolidWorks did not report"
            )
        if not (fx or fy):
            runs.append(run)
            continue
        along, up = fx * width, fy * float(run.get("h") or 0.0)
        angle = float(run.get("ang") or 0.0)
        cos_a, sin_a = math.cos(angle), math.sin(angle)
        x, y, *rest = (float(value) for value in run["pos"])
        corner = [x - along * cos_a + up * sin_a, y - along * sin_a - up * cos_a]
        runs.append({**run, "pos": [*corner, *rest], "ref": 1})
    if runs == list(texts):
        return record
    return {**record, "display": {**record["display"], "texts": runs}}


def measured_run_ink(record: Mapping[str, Any]) -> dict[int, Box]:
    """``annotation_geometry``'s ``ink`` map for a lower-left ``record``.

    Keyed by index in ``text_items``: each run SolidWorks reported a width for
    is boxed along its baseline at that width, cap height tall. A run without
    one is absent and keeps the audit's estimate at the caller's advance.
    """
    ink: dict[int, Box] = {}
    index = 0
    for run in record["display"].get("texts", ()):
        if not text_items({"texts": [run]}):
            continue  # text_items drops it, so it takes no index
        if float(run.get("w") or 0.0) > 0.0:
            ink[index] = display_box({"texts": [run]})
        index += 1
    return ink
