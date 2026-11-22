"""Cutting-plane strokes of a view carrying MORE than one section line.

``_drawing_leaders.parse_section_line_info`` reads ``IView.GetSectionLineInfo2``
as the API help lays it out: [count, layer, then per line ...]. The seat
repeats the layer ahead of EVERY line: [count, (layer, nSegments, ...) x
count]. With one line the two readings agree; with two, the help's reading
takes the second line one value late (drawing:mg_magnifying_wheel leaf in
farm run 20261121T071639071Z-fef028aba83e419a964489cfba2cea73, A-A and B-B
on the face view: B-B's nSegments 1, lineType 4 and chain start (0.022,
-0.005588, 0) came back as its arrow 1, "chain on the sheet []").

This module holds the per-line reading in its own file so that only the
drawings that import it re-key; everything else (chain-to-sheet mapping,
tail-on-chain proof, arrowhead outlines) is ``_drawing_leaders``'s.
"""

from __future__ import annotations

import math
from typing import Any, Callable, Sequence

import _telemetry
from _drawing_leaders import Point, Point3, Segment, _tail_first, arrowhead_outline
from solidworks_mcp.adapters import sw_type_info as _sw_type_info
from solidworks_mcp.adapters.com_variant import double_array

# Per line: layer, nSegments, then 7 values a segment, 2 arrows of 9, two
# text points and the text height.
_LINE_HEAD = 2
_SEGMENT = 7
_ARROW = 9
_TEXT = 7


# TODO(#3346): move into _drawing_leaders.parse_section_line_info at the next
# change that re-keys _drawing_leaders anyway, then delete this module.
def parse_section_lines(
    values: Sequence[float],
    chain_to_sheet: Callable[[Point3], Point] | None = None,
) -> list[Segment]:
    """Every section line's chain, arrow shafts and arrowhead outlines from
    ``IView.GetSectionLineInfo2``'s flat array, read as [count, (layer,
    nSegments, nSegments x (lineType, start[3], end[3]), arrow1[9],
    arrow2[9], text1[3], text2[3], textHeight) x count].

    The chain is in MODEL space and mapped by ``chain_to_sheet`` (read as
    already on the sheet without it); the arrows come back on the sheet.
    Each arrow's tail must sit on its own line's mapped chain
    (``_drawing_leaders._tail_first``), which raises otherwise.
    """
    values = [float(v) for v in values]
    if not values:
        return []
    count, index, segments = int(values[0]), 1, []
    for _ in range(count):
        n = int(values[index + 1])
        index += _LINE_HEAD
        chain: list[Segment] = []
        for _ in range(n):
            start = (values[index + 1], values[index + 2], values[index + 3])
            end = (values[index + 4], values[index + 5], values[index + 6])
            if chain_to_sheet is None:
                chain.append(((start[0], start[1]), (end[0], end[1])))
            else:
                chain.append((chain_to_sheet(start), chain_to_sheet(end)))
            index += _SEGMENT
        segments.extend(chain)
        for arrow in (1, 2):
            raw = values[index : index + _ARROW]
            start, end = (raw[0], raw[1]), (raw[3], raw[4])
            segments.append((start, end))
            segments.extend(
                arrowhead_outline(
                    _tail_first(start, end, chain, arrow, raw), raw[6], raw[7]
                )
            )
            index += _ARROW
        index += _TEXT
    if index != len(values):
        raise RuntimeError(
            f"section-line info has {len(values)} values, parsed {index}"
        )
    return segments


def section_line_segments(adapter: Any, view: Any) -> list[Segment]:
    """``_drawing_leaders.section_line_segments`` for a view carrying any
    number of section lines: the chain mapped through ``IView.
    ModelToViewTransform``, a broken view refused."""
    view = _sw_type_info.early_bound_or_flag(
        view,
        "IView",
        "GetSectionLineInfo2",
        "ModelToViewTransform",
        "IsBroken",
        "GetName2",
    )
    name = str(view.GetName2())
    if view.IsBroken():
        raise RuntimeError(
            f"section line on broken view {name!r}: its model-to-view transform "
            "does not carry the break gap"
        )
    utility = _sw_type_info.early_bound_or_flag(
        adapter.swApp.GetMathUtility(), "IMathUtility", "CreatePoint"
    )
    transform = _sw_type_info.early_bound_or_flag(
        view.ModelToViewTransform, "IMathTransform", "ArrayData"
    )
    _telemetry.info(
        f"section view {name!r} model-to-view transform {list(transform.ArrayData)}"
    )

    def to_sheet(point: Point3) -> Point:
        # A bare list marshals as VT_ARRAY | VT_VARIANT, which CreatePoint
        # reads as the origin (_drawing_leaders.section_line_segments).
        model = utility.CreatePoint(double_array(list(point)))
        if model is None:
            raise RuntimeError(f"section line: could not create model point {point}")
        model = _sw_type_info.early_bound_or_flag(
            model, "IMathPoint", "MultiplyTransform", "ArrayData"
        )
        created = tuple(float(v) for v in tuple(model.ArrayData)[:3])
        if not all(math.isclose(a, b, abs_tol=1e-12) for a, b in zip(created, point)):
            raise RuntimeError(
                f"section line: CreatePoint({point}) made {created}; the array did not marshal"
            )
        mapped = model.MultiplyTransform(transform)
        if mapped is None:
            raise RuntimeError(f"section line: could not map model point {point}")
        mapped = _sw_type_info.early_bound_or_flag(mapped, "IMathPoint", "ArrayData")
        x, y = (float(v) for v in tuple(mapped.ArrayData)[:2])
        return (x, y)

    raw = tuple(view.GetSectionLineInfo2() or ())
    _telemetry.info(f"section view {name!r} GetSectionLineInfo2 {list(raw)}")
    return parse_section_lines(raw, to_sheet)
