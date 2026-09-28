"""Offline contracts for the summing-lever drawing."""

from __future__ import annotations

import pytest

import draw_summing_lever as drawing
import summing_lever_spec
from _drawing_common import ViewEdge, ViewEdges
from _hole_spec import blind_cut_dia_mm
from stock_anchor_geom import ANCHOR_9489T111, ANCHOR_9490T1


def test_anchor_seats_are_the_purchased_anchors_own_threads() -> None:
    """Both lower spring anchors are purchased eyebolts threaded straight into
    this casting -- there is no nut -- so a seat that does not match its
    anchor, or a boss its anchor cannot span, is an unassemblable part."""
    plate, boss = summing_lever_spec.HOLE_SPEC, summing_lever_spec.COUNTER_HOLE_SPEC
    assert (plate.kind, plate.end) == ("tapped", "through_all")
    assert (boss.kind, boss.end) == ("tapped", "through_all")
    assert plate.size == ANCHOR_9489T111.thread_size
    assert boss.size == ANCHOR_9490T1.thread_size
    # Each anchor's thread must span the seat it screws into.
    assert ANCHOR_9489T111.thread_length_mm > summing_lever_spec.PLATE_T
    assert ANCHOR_9490T1.thread_length_mm >= summing_lever_spec.ANCHOR_H
    # ...and each tap must fit the feature it passes through.
    assert blind_cut_dia_mm(boss) < 2.0 * summing_lever_spec.ANCHOR_R
    assert blind_cut_dia_mm(plate) < summing_lever_spec.HOLE_EDGE_OFFSET


def _line(start, end):
    return ViewEdge(object(), (start, end), None, None)


def test_end_face_edge_is_the_rib_top_edge_not_the_flange_or_underside() -> None:
    """Datum B and the start-Z BASIC hang on the +Z END face: the rib flange
    5.08 mm inboard reads 3.35 for 8.43 (#1105), and the rib's underside edge
    shares the end plane but is hidden under the plate."""
    z = summing_lever_spec.PLATE_L / 2.0
    top = _line((0.0, 15.24, z), (summing_lever_spec.PLATE_W, 0.0, z))
    flange = _line((0.0, 15.24, z - summing_lever_spec.PLATE_T), (44.45, 0.0, z - 5.08))
    underside = _line((summing_lever_spec.PLATE_W, 0.0, z), (0.0, -15.24, z))
    plate_end = _line((37.04, 2.54, z), (summing_lever_spec.PLATE_W, 2.54, z))
    edges = ViewEdges(label="plan", edges=(flange, underside, plate_end, top))
    assert drawing._end_face_edge(edges, x_mm=10.0) is top
    # The plate's own end edge only shows past the rib taper: two lines there.
    with pytest.raises(RuntimeError, match="expected one visible line"):
        drawing._end_face_edge(edges, x_mm=40.0)
    with pytest.raises(RuntimeError, match="expected one visible line"):
        drawing._end_face_edge(ViewEdges(label="plan", edges=(flange, underside)), x_mm=10.0)
