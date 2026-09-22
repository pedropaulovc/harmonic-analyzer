"""Offline contracts for the summing-lever drawing."""

from __future__ import annotations

import math

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


def test_knife_profile_is_the_nonregular_hex_detail_a_states() -> None:
    """Detail A's note states a NONREGULAR 6-SIDED PROFILE, so the model has to
    be one and the flat the note is read against has to be the length the print
    dimension carries.

    "Correcting" HEX_H to the across-corners value its across-flats implies
    would make the sheet contradict itself while every dictionary entry still
    looked right -- this fails loudly on exactly that edit.
    """
    across_flats = summing_lever_spec.HEX_W
    across_corners = summing_lever_spec.HEX_H
    # A regular hexagon locks A/F and A/C together; ours is 0.28 mm outside it.
    assert abs(across_corners - across_flats * 2.0 / math.sqrt(3.0)) > 0.2
    # _hex_collar's vertex-up hexagon puts its shoulders at +-HEX_H/4, so the
    # vertical flat HexKnifeFrontSideFlat names is exactly HEX_H/2 -- and not
    # the regular hexagon's side HEX_W/sqrt(3). A flat is half the A/C measure,
    # so the second gap is half the bound above.
    half_width, quarter_height = across_flats / 2.0, across_corners / 4.0
    flat = math.dist((-half_width, quarter_height), (-half_width, -quarter_height))
    assert math.isclose(flat, across_corners / 2.0, rel_tol=0.0, abs_tol=1e-12)
    assert abs(flat - across_flats / math.sqrt(3.0)) > 0.1
    # ...and the flat must reach the print as a model dimension at its own
    # decimal places, which is what the note is read against.
    assert (
        "HexKnifeFrontSideFlat"
        in summing_lever_spec.DRAWING_DIMENSIONS["HexKnifeFrontProfile"]
    )
    assert (
        "HexKnifeFrontSideFlat"
        in summing_lever_spec.DRAWING_PRECISION["HexKnifeFrontProfile"]
    )
