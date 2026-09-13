"""Offline contracts for the summing-lever drawing."""

from __future__ import annotations

import summing_lever_spec
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
