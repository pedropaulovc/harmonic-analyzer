"""Cutting-plane strokes of a view carrying MORE than one section line.

Two readings of ``IView.GetSectionLineInfo2`` that ``_drawing_leaders`` gets
wrong, kept in their own file so that only the drawings importing it re-key
(#3346 folds them back):

- The layout. ``_drawing_leaders.parse_section_line_info`` reads it as the
  API help lays it out: [count, layer, then per line ...]. The seat repeats
  the layer ahead of EVERY line: [count, (layer, nSegments, ...) x count].
  With one line the two readings agree; with two, the help's reading takes
  the second line one value late (drawing:mg_magnifying_wheel leaf in farm
  run 20261121T071639071Z-fef028aba83e419a964489cfba2cea73, A-A and B-B on
  the face view: B-B's nSegments 1, lineType 4 and chain start (0.022,
  -0.005588, 0) came back as its arrow 1, "chain on the sheet []").
- The arrows: where they print (``_printed_arrow``).

The chain-to-sheet mapping is a copy of ``_drawing_leaders.section_line_segments``'s.
"""

from __future__ import annotations

import math
from typing import Any, Callable, Sequence

import _telemetry
from _drawing_leaders import Point, Point3, Segment, arrowhead_outline
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
    """Every section line's chain, arrow shafts and arrowhead outlines, as
    printed, from ``IView.GetSectionLineInfo2``'s flat array, read as
    [count, (layer, nSegments, nSegments x (lineType, start[3], end[3]),
    arrow1[9], arrow2[9], text1[3], text2[3], textHeight) x count].

    The chain is in MODEL space and mapped by ``chain_to_sheet`` (read as
    already on the sheet without it); the arrows come back on the sheet but
    not where they print (``_printed_arrow``).
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
            shaft = _printed_arrow((raw[0], raw[1]), (raw[3], raw[4]), chain, arrow)
            segments.append(shaft)
            segments.extend(arrowhead_outline(shaft, raw[6], raw[7]))
            index += _ARROW
        index += _TEXT
    if index != len(values):
        raise RuntimeError(
            f"section-line info has {len(values)} values, parsed {index}"
        )
    return segments


# How far the reported shaft's end stands in from its chain end along the
# chain (sheet metres): 2.00 mm on every seat read so far (drawing:
# dt_crank_pinion 20260925T210727Z, drawing:mg_magnifying_wheel A-A and B-B
# in runs 20261121T071639071Z and 20261122T184921959Z).
_REPORTED_INSET = 0.002
_INSET_TOLERANCE = 1e-4


def _printed_arrow(
    start: Point, end: Point, chain: Sequence[Segment], arrow: int
) -> Segment:
    """The arrow as printed, tail to tip: tail ON the chain's nearer end,
    pointing along the reported start -> end.

    The reported shaft is not the printed one. MHA-MG-05's A-A (mg-magnifying-
    wheel.pdf of run 20261121T201300466Z; run 20261122T184921959Z logged the
    same view's array) prints its left arrow from the chain's end (0.042,
    0.150) up to (0.042, 0.162), and the array reports it from (0.044, 0.138)
    to (0.044, 0.150): the same direction, one shaft length back and 2 mm in
    along the chain. The direction is the view's sight line (A-A's
    projection looks along +y, toward sheet-up), the end on the chain line is
    the one 2 mm in, and the printed tail is the chain's own end (MHA-DT-07's
    and MHA-MG-05's sheets both print the arrows at the chain's ends).
    ``_drawing_leaders._tail_first`` instead keeps the reported shaft and
    tips it AWAY from the chain, the mirror of the print (#3346).

    Raises unless the reported end sits ``_REPORTED_INSET`` in from a chain
    end along the chain's line and the shaft stands square to it.
    """
    if not chain:
        raise RuntimeError(f"section arrow {arrow}: no chain to stand on")
    vector = (end[0] - start[0], end[1] - start[1])
    length = math.hypot(*vector)
    candidates = []
    for stroke, chain_end in ((chain[0], chain[0][0]), (chain[-1], chain[-1][1])):
        (x0, y0), (x1, y1) = stroke
        along = math.dist((x0, y0), (x1, y1))
        if along == 0.0 or length == 0.0:
            continue
        ux, uy = (x1 - x0) / along, (y1 - y0) / along
        dx, dy = end[0] - chain_end[0], end[1] - chain_end[1]
        candidates.append(
            (
                abs(math.hypot(dx, dy) - _REPORTED_INSET),
                abs(dx * uy - dy * ux),
                abs(vector[0] * ux + vector[1] * uy) / length,
                chain_end,
            )
        )
    if not candidates:
        raise RuntimeError(f"section arrow {arrow}: zero-length shaft or chain")
    inset_error, off_line, slant, tail = min(candidates, key=lambda item: item[0])
    if inset_error > _INSET_TOLERANCE or off_line > _INSET_TOLERANCE or slant > 1e-3:
        raise RuntimeError(
            f"section arrow {arrow}: reported {start} -> {end} is not "
            f"{_REPORTED_INSET * 1000:.1f} mm in from a chain end and square to "
            f"the chain {list(chain)} (inset error {inset_error:.6f}, off line "
            f"{off_line:.6f}, slant {slant:.6f})"
        )
    tip = (tail[0] + vector[0], tail[1] + vector[1])
    _telemetry.info(f"section arrow {arrow}: printed {tail} -> {tip}")
    return (tail, tip)


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
