"""Offline contracts for the summing-lever drawing."""

from __future__ import annotations

import math

import draw_summing_lever
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


def test_midrib_right_end_is_in_the_specs_marked_set() -> None:
    """The gusset's right-hand rib end reaches the print as a model dimension.

    ``DRAWING_PRECISION_BY_NAME`` is derived from the marked set, and the spec
    refuses to import while the two disagree, so this one membership check
    covers both the marking and the decimal places that go with it.
    """
    assert "MidRibRightX" in summing_lever_spec.DRAWING_PRECISION_BY_NAME


def test_manufacturing_note_block_stays_four_lines() -> None:
    """The general-note block is the print's only prose and it must not grow.

    The drawing simplicity policy names a lengthening note block as the disease
    the migration cures, so the block stays at the four statements the review
    rounds settled on. Collapsing them into one multi-line note is the same
    failure and trips this too.
    """
    assert len(draw_summing_lever.MANUFACTURING_NOTES) == 4


def test_printed_arc_centre_lays_the_arc_onto_the_boss() -> None:
    """The R138.8 side arcs are laid out from their printed centre and radius.

    The arc's base end is buried in the cylinder, so the shop can only strike it
    from the centre the print locates (2X 123.2 from the cylinder axis, 2X 64.0
    beyond the plate end).  Rounded to the printed places, that centre and radius
    must still land the arc on the boss quadrant and on the buried base corner
    within the one-place title-block band.
    """
    import build_summing_lever as build

    base_end, tip_end, interior = build._summation_top_arc_points()
    cx, cy = build._circumcenter(base_end, tip_end, interior)
    printed_x = round(abs(cx), 1)
    printed_z = round(cy - base_end[1], 1)
    printed_r = round(math.dist((cx, cy), base_end), 1)
    centre = (-printed_x, base_end[1] + printed_z)
    for end in (tip_end, base_end):
        assert abs(math.dist(centre, end) - printed_r) < 0.8
