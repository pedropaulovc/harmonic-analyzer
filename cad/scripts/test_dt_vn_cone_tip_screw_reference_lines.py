"""The tip adjuster's and pinch screw's FRONT supplier lines print no stray ink.

SolidWorks draws the shown construction lines grey OVER the view's edges but
UNDER the dimension extension lines of the same width (see
test_dt_vn_cone_pivot_screw_drawing). Each FRONT line therefore lies under one
of the sheet's own extension lines; only the named gap stubs stay bare (r13
review, run 20261101T142805608Z: a grey chord crossed both threads mid-length).
"""

from __future__ import annotations

from types import ModuleType

import pytest

import _mcmaster_91794a112 as pinch
import _mcmaster_94025a164 as adjuster
from _supplier_screw_layout import supplier_screw_lane_plan

FAR = 1000.0  # witnesses run on to their lanes, beyond the part
# (axis, station, low, high): a horizontal segment on y=station, or vertical on x.
Carrier = tuple[str, float, float, float]


def _rows(sku: ModuleType) -> dict[str, tuple[float, str]]:
    """The FRONT sketch's dimensions; other planes print in other views."""
    return {
        name: (value, orientation)
        for name, value, orientation in sku.SUPPLIER_REFERENCE_DIMENSIONS
        if name not in sku.SUPPLIER_REFERENCE_PLANES
    }


def _line(
    sku: ModuleType, name: str
) -> tuple[tuple[float, float], tuple[float, float]]:
    (x, y), (value, orientation) = sku.SUPPLIER_REFERENCE_STARTS[name], _rows(sku)[name]
    return (x, y), ((x + value, y) if orientation == "horizontal" else (x, y + value))


def _carrier(sku: ModuleType, name: str) -> Carrier:
    (x0, y0), (x1, y1) = _line(sku, name)
    if y0 == y1:
        return ("y", y0, min(x0, x1), max(x0, x1))
    return ("x", x0, min(y0, y1), max(y0, y1))


def _witnesses(sku: ModuleType, gap: float) -> list[Carrier]:
    """Each FRONT dimension's two extension lines, from its gap toward its lane."""
    lanes = supplier_screw_lane_plan(
        sku.SUPPLIER_REFERENCE_DIMENSIONS,
        planes=sku.SUPPLIER_REFERENCE_PLANES,
        sides=sku.SUPPLIER_REFERENCE_SIDES,
    )
    out: list[Carrier] = []
    for name, (_, orientation) in _rows(sku).items():
        side = lanes[name][0]
        for x, y in _line(sku, name):
            if orientation == "vertical":
                out.append(
                    ("y", y, *((x + gap, FAR) if side == "right" else (-FAR, x - gap)))
                )
            else:
                out.append(
                    ("x", x, *((y + gap, FAR) if side == "top" else (-FAR, y - gap)))
                )
    return out


def _bare(line: Carrier, covers: list[Carrier]) -> list[tuple[float, float]]:
    """The spans of ``line`` that no collinear cover overlaps."""
    axis, station, low, high = line
    spans = [(low, high)]
    for kind, at, start, end in covers:
        if kind == axis and abs(at - station) < 1e-9:
            spans = [
                piece
                for lo, hi in spans
                for piece in ((lo, min(hi, start)), (max(lo, end), hi))
                if piece[1] - piece[0] > 1e-9
            ]
    return spans


A_R = adjuster.SS_MAJOR_R
P_SHANK_R, P_HEAD_R = pinch.SHANK_DIA / 2.0, pinch.HEAD_DIA / 2.0


def test_sides_are_pinned_for_every_dimension() -> None:
    for sku in (adjuster, pinch):
        names = {name for name, _, _ in sku.SUPPLIER_REFERENCE_DIMENSIONS}
        assert (
            set(sku.SUPPLIER_REFERENCE_STARTS)
            == set(sku.SUPPLIER_REFERENCE_SIDES)
            == names
        )


def test_adjuster_lines_sit_on_the_slot_end_and_the_right_crest() -> None:
    assert adjuster.SUPPLIER_REFERENCE_PLANES == {}
    assert {name: _line(adjuster, name) for name in _rows(adjuster)} == {
        # Slot face (y=0) to cup rim, under the diameter's right witness.
        "SupplierLength": ((A_R, 0.0), (A_R, adjuster.SS_LEN)),
        # Across the slot-end face, under the length's lower witness.
        "SupplierThreadDiameter": ((-A_R, 0.0), (A_R, 0.0)),
    }


def test_pinch_lines_sit_on_the_head_underside_and_the_right_crest() -> None:
    assert pinch.SUPPLIER_REFERENCE_PLANES == {"SupplierHeadDiameter": "Top"}
    assert {name: _line(pinch, name) for name in _rows(pinch)} == {
        "SupplierLength": ((P_SHANK_R, 0.0), (P_SHANK_R, -pinch.SHANK_LEN)),
        "SupplierHeadHeight": ((P_HEAD_R, 0.0), (P_HEAD_R, pinch.HEAD_H)),
        "SupplierThreadDiameter": ((-P_SHANK_R, 0.0), (P_SHANK_R, 0.0)),
    }


# Measured ~0.76 sheet mm: 0.19 model mm at the adjuster's FRONT 4:1.
@pytest.mark.parametrize("gap", (0.12, 0.19, 0.25))
def test_adjuster_bares_only_the_chamfer_corner_gaps(gap: float) -> None:
    covers = _witnesses(adjuster, gap)
    assert {
        name: _bare(_carrier(adjuster, name), covers) for name in _rows(adjuster)
    } == {
        "SupplierLength": [(0.0, pytest.approx(gap))],
        "SupplierThreadDiameter": [(pytest.approx(A_R - gap), A_R)],
    }
    # The chord's stub lies beyond the end face's edge, in the chamfer corner.
    assert A_R - gap >= adjuster.SS_CHAM_R


# Measured ~0.76 mm at the pinch screw's FRONT 1:1.
@pytest.mark.parametrize("gap", (0.5, 0.76, 1.0))
def test_pinch_bares_only_the_gaps_and_the_head_height(gap: float) -> None:
    covers = _witnesses(pinch, gap)
    assert {name: _bare(_carrier(pinch, name), covers) for name in _rows(pinch)} == {
        "SupplierLength": [(pytest.approx(-gap), 0.0)],
        # The chord's bare end lies inside the head underside edge.
        "SupplierThreadDiameter": [(pytest.approx(P_SHANK_R - gap), P_SHANK_R)],
        # No witness covers it: grey on the head's right silhouette.
        "SupplierHeadHeight": [(0.0, pinch.HEAD_H)],
    }
    assert P_SHANK_R < P_HEAD_R
