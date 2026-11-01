"""Offline contracts for the guide-lock drawing."""

from __future__ import annotations

from pathlib import Path

import pytest

import build_pd_guide_lock as lock
import draw_pd_guide_lock as drawing
import pd_guide_lock_spec
from _drawing_registry import DRAWINGS_BY_NAME
from _hole_spec import blind_cut_dia_mm
from _inch_wall_limits import WALL_TARGET_MM
from _printed_tolerance import drilled_oversize_mm, printed_band_mm


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/pd-guide-lock.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/pd-guide-lock.pdf")
    assert drawing.PNG.as_posix().endswith("/png/pd-guide-lock_drawing.png")
    assert DRAWINGS_BY_NAME["pd_guide_lock"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    # The drift alarm: the part-side mark set and the drawing-side keep set are
    # BOTH the shared spec's map, and the drawing's view math reads the spec's
    # nominal spans, not a divergent copy.
    assert lock.DRAWING_DIMENSIONS is pd_guide_lock_spec.DRAWING_DIMENSIONS
    marked = set().union(*pd_guide_lock_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP)
    assert kept == marked
    assert (drawing.LOCK_WIDTH, drawing.LOCK_HEIGHT) == (
        pd_guide_lock_spec.LOCK_WIDTH,
        pd_guide_lock_spec.LOCK_HEIGHT,
    )
    assert lock.HOLE_XY is pd_guide_lock_spec.HOLE_XY


def test_hole_contract_is_part_owned_and_resolved() -> None:
    spec = pd_guide_lock_spec.HOLE_SPEC
    assert lock.HOLE_SPEC is spec
    assert drawing.HOLE_SPEC is spec
    # R9-49: the fractional 1/8 drill carries both printed hole positions over
    # the screw majors (guide_lock_screw_spec.LOCK_SET_OFFSET).
    assert spec.kind == "drilled_fractional"
    assert spec.size == "1/8"
    assert lock.HOLE_DIA == blind_cut_dia_mm(spec)
    assert drawing.HOLE_R_SHEET == (
        blind_cut_dia_mm(spec) * drawing.SHEET_SCALE[0] / 2000.0
    )


def test_sheet_runs_at_4_to_1_with_2_to_1_isometric() -> None:
    assert drawing.SHEET_SCALE == (4.0, 1.0)
    assert pd_guide_lock_spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 2:1"


# Inch title block: .XX ±.01; drilled holes +.004/-0.
_TWO_PLACES = printed_band_mm(2, unit="in")
_DRILLED_PLUS = drilled_oversize_mm(unit="in")
_HOLE_BAND = pd_guide_lock_spec.HOLE_LOCATION_BAND
_CHAR_WIDTH = 0.00276  # sheet m per character of 3.5-mm note text


def _ligaments(
    hole_y: float, width: float = pd_guide_lock_spec.LOCK_WIDTH
) -> dict[str, float]:
    r_max = (0.125 * 25.4 + _DRILLED_PLUS) / 2.0
    xs = [x for x, _ in pd_guide_lock_spec.HOLE_XY]
    height_min = pd_guide_lock_spec.LOCK_HEIGHT - _TWO_PLACES
    return {
        "guide-side edge": hole_y - _HOLE_BAND - r_max,
        "far edge": height_min - hole_y - _HOLE_BAND - r_max,
        "left edge": min(xs) - _HOLE_BAND - r_max,
        "right edge": (width - _TWO_PLACES) - max(xs) - _HOLE_BAND - r_max,
    }


def test_screw_holes_reach_the_wall_target_at_the_printed_worst_case() -> None:
    """Review of 19e33c6c2 (blocker): 2.5 from the guide-side edge left 0.81
    of ligament under the largest drilled 1/8 hole.  Machinist review ENFORCE
    (PR #1897): the 1.0 lip and the 22.0 plate left 1.83 and 1.53, under the
    2.0 target, so the plate laps the rail (holes on the .29 rail's tap row,
    .155 from that edge) and runs .89 long with the holes .157 and .709 from
    its left end; the inch print holds the .080 target (#290)."""
    assert min(_ligaments(2.5).values()) < 1.0
    assert min(_ligaments(3.5, width=22.0).values()) < WALL_TARGET_MM
    (hole_y,) = {y for _, y in pd_guide_lock_spec.HOLE_XY}
    assert hole_y == pytest.approx(0.155 * 25.4)
    assert [x for x, _ in pd_guide_lock_spec.HOLE_XY] == pytest.approx(
        [0.157 * 25.4, 0.709 * 25.4]
    )
    worst = _ligaments(hole_y)
    assert min(worst.values()) >= WALL_TARGET_MM
    assert pd_guide_lock_spec.HOLE_LIGAMENTS_WORST == pytest.approx(worst)
    assert pd_guide_lock_spec.HOLE_PATTERN_X == pytest.approx(0.433 * 25.4)
    assert pd_guide_lock_spec.DRAWING_PRECISION_BY_NAME["Height"] == 2
    assert pd_guide_lock_spec.DRAWING_PRECISION_BY_NAME["Width"] == 2


def test_hole_coordinates_print_from_the_corner_without_a_frame() -> None:
    """drawing-guidelines.md rule 5 (avoid excessive GD&T): no frame on this plate; each hole coordinate prints from the
    plate's corner at .XXX under its own band, and the shared Y once, 2X."""
    holes = pd_guide_lock_spec.DRAWING_DIMENSIONS["ScrewHoles"]
    assert holes == {"Hole1X", "Hole2X", "Hole1Y"} <= set(drawing.FRONT_KEEP)
    assert {pd_guide_lock_spec.DRAWING_PRECISION_BY_NAME[name] for name in holes} == {3}
    assert drawing.DIMENSION_PREFIXES["Hole1Y"] == "2X "
    assert len({y for _, y in pd_guide_lock_spec.HOLE_XY}) == 1


def test_the_drill_callout_stands_between_the_plate_and_the_right_view() -> None:
    text = f"2X {drawing.HOLE_CALLOUT_PROCESS} Ø.125 THRU ALL"
    assert text.split()[1] == "DRILL"
    half = len(text) * _CHAR_WIDTH / 2.0
    left, right = (
        drawing.HOLE_CALLOUT_XY[0] - half,
        drawing.HOLE_CALLOUT_XY[0] + half,
    )
    right_view_left = (
        drawing.RIGHT_CENTER[0]
        - pd_guide_lock_spec.LOCK_THICK * drawing.SHEET_SCALE[0] / 2000.0
    )
    assert drawing.RIGHT_EDGE_X < left and right < right_view_left


def test_the_drill_callout_names_the_mate_its_location_bands_serve() -> None:
    """Machinist review ENFORCE r1-r3 (blocker): the banded hole coordinates
    named no mate.  The callout names the platen guide's taps the pattern
    lands on and the screws its holes clear; with every wall at the 2.0
    target it states no shortfall."""
    import _config

    rows = drawing.HOLE_CALLOUT_BELOW.split("\n")
    assert rows == [
        f"MATCHES {_config.parts('pd-platen-guide')['number']} TAPS,",
        "CLEARANCE FIT ON",
        f"{_config.parts('pd-vn-guide-lock-screw')['number']} SCREWS",
    ]
    # Each row is no wider than the native row the plate and right view
    # already bound (test above).
    assert max(len(row) for row in rows) <= len("2X DRILL Ø.125 THRU ALL")


def test_the_hole_coordinates_name_the_taps_they_match() -> None:
    """Machinist review ENFORCE at 2056e3344 (blocker): the 4.000 and 2X
    3.700 ±0.035 edge locations gave no function; at eecbf880d the 18.000
    still lacked it. The coordinates baseline the pattern from the corner,
    and the set window spends each band (±0.065 is refused), so each names
    the guide whose taps it matches."""
    import _config

    guide = _config.parts("pd-platen-guide")["number"]
    assert drawing.DIMENSION_CALLOUTS_BELOW == {
        "Hole1X": f"MATCHES\n{guide}",
        "Hole2X": f"MATCHES\n{guide}",
        "Hole1Y": f"MATCHES\n{guide}",
    }
    # Each block stays inside its value's width, the 4.000's left of the
    # plate's left-edge extension line.
    width = max(len(row) for row in f"MATCHES\n{guide}".split("\n")) * _CHAR_WIDTH
    x_x, _ = drawing.FRONT_KEEP["Hole1X"]
    assert width <= len("2X .155 ±.001") * _CHAR_WIDTH
    assert width <= len(".157 ±.001") * _CHAR_WIDTH
    assert width <= len(".709 ±.001") * _CHAR_WIDTH
    assert x_x + width / 2.0 < drawing.LEFT_EDGE_X - 0.002


# A three-row block (value plus the two-row mate callout) centres on its text
# position; its first row's top stands ~7.3 mm above it and the dimension's
# shelf hangs ~8.3 mm below (layout audit of farm run 20261024T123122680Z).
_BLOCK_TOP = 0.0073
_BLOCK_SHELF = 0.0083


def test_the_edge_coordinate_blocks_clear_each_other_and_the_18_000() -> None:
    """Machinist review r1-r3 of bef0d46b6: at the one-row positions the
    hole Y's line ran down through the 4.000's text and the 4.000's shelf
    fell onto the 18.000's dimension line."""
    y_x, y_y = drawing.FRONT_KEEP["Hole1Y"]
    x_x, x_y = drawing.FRONT_KEEP["Hole1X"]
    # The hole Y's line (at its text x) passes left of the whole 4.000 block.
    assert x_x - len(".157 ±.001") * _CHAR_WIDTH / 2.0 > y_x
    # The 4.000's shelf, its dimension line, stands clear above the 18.000's
    # (the smaller dimension nearer the part); both three-row blocks hang
    # their shelves the same _BLOCK_SHELF below their text positions.
    assert x_y > drawing.FRONT_KEEP["Hole2X"][1] + 0.004
    # All three blocks stay under the Height's bottom arrow and the plate.
    for y in (y_y, x_y, drawing.FRONT_KEEP["Hole2X"][1]):
        assert y + _BLOCK_TOP < drawing.BOTTOM_EDGE_Y - 0.002


def test_the_18_000_block_stands_between_the_hole_extension_lines() -> None:
    """Machinist review at eecbf880d: the 18.000 now carries the mate block.
    Its shelf keeps the one-row line's place above the 22.5's text, and the
    block stands between hole 1's extension line (where the 4.000's line
    ends) and hole 2's."""
    x, y = drawing.FRONT_KEEP["Hole2X"]
    half = len(".709 ±.001") * _CHAR_WIDTH / 2.0
    assert x - half > drawing._sheet_x(pd_guide_lock_spec.HOLE_XY[0][0]) + 0.002
    assert x + half < drawing.HOLE_2_X_SHEET - 0.002
    assert y - _BLOCK_SHELF > drawing.FRONT_KEEP["Width"][1] + 0.003


def test_the_thickness_value_stands_outboard_of_its_extension_lines() -> None:
    """Machinist review ENFORCE r1-r3: centred between the 1/16 sheet's
    extension lines, the value's digits sat on them; it stands right of the
    edge-on view, left of the isometric. Round 2: it prints REF with the
    supplier's band, which governs the stock thickness."""
    band_in = pd_guide_lock_spec.LOCK_THICK_BAND / 25.4
    assert drawing.THICKNESS_SUFFIX.endswith(
        f"\u00b1{band_in:.3f}".replace("0.", ".", 1)
    )
    printed = f"{drawing.THICKNESS_PREFIX}.0625{drawing.THICKNESS_SUFFIX}"
    x, _ = drawing.RIGHT_KEEP["Depth"]
    half = len(printed) * _CHAR_WIDTH / 2.0
    right_view_right = (
        drawing.RIGHT_CENTER[0]
        + pd_guide_lock_spec.LOCK_THICK * drawing.SHEET_SCALE[0] / 2000.0
    )
    assert x - half > right_view_right + 0.002
    stock_half = len(pd_guide_lock_spec.LOCK_STOCK_CALLOUT) * _CHAR_WIDTH / 2.0
    assert x + stock_half < drawing.ISO_CENTER[0] - 0.015


def test_the_hole_y_text_stays_inside_the_border_and_under_the_plate() -> None:
    x, y = drawing.FRONT_KEEP["Hole1Y"]
    half = len("2X .155±.001") * _CHAR_WIDTH / 2.0
    assert x - 2.0 * half > 0.0127  # right-aligned or centred, inside
    assert y < drawing.BOTTOM_EDGE_Y - 0.004
    assert x + half < drawing.LEFT_EDGE_X  # clear of Hole1X's extension


def test_the_hole_1_x_text_stands_outboard_of_its_extension_lines() -> None:
    """Machinist review of 40e51b9a7: between its extension lines the 4.000's
    text sat on hole 1's own extension line. It now stands left of the plate's
    left edge, right of the 2X hole Y's dimension line."""
    x, y = drawing.FRONT_KEEP["Hole1X"]
    half = len(".157 ±.001") * _CHAR_WIDTH / 2.0
    assert x + half < drawing.LEFT_EDGE_X - 0.002
    assert y > drawing.FRONT_KEEP["Hole2X"][1] + 0.004


def test_the_height_text_sits_between_its_extension_lines() -> None:
    """Machinist review of 1c9f9b2a6: inboard of the hole Y dimension the
    height's value sat on the plate's top-edge extension line. It now stands
    mid-way between the top and bottom extension lines, left of the hole Y
    dimension line, where the hole Y extension stops, and carries no callout
    (Codex P1 on #1353: drawing-guidelines.md rule 7 (notes: few, flagged, never a method) bars a design-intent note)."""
    assert "Height" not in drawing.DIMENSION_CALLOUTS
    assert not hasattr(drawing, "HEIGHT_BAND_CALLOUT")
    x, y = drawing.FRONT_KEEP["Height"]
    half_w = len("9.6") * _CHAR_WIDTH / 2.0
    assert x - half_w > 0.0127
    assert x + half_w < drawing.FRONT_KEEP["Hole1Y"][0] - 0.002
    half_h = 0.0035 / 2.0
    assert y + half_h < drawing._sheet_y(pd_guide_lock_spec.LOCK_HEIGHT) - 0.005
    assert y - half_h > drawing.BOTTOM_EDGE_Y + 0.005


def test_the_views_sit_centred_between_the_border_and_title_block() -> None:
    """Machinist review of 40e51b9a7: the group sat low and left under an
    empty upper field. The dimension stack's bottom (Width) and the top
    (4X R, the stock callout) stand about equally off the title block's top
    and the border."""
    border_top, title_top = 0.279 - 0.0127, 0.065
    bottom = drawing.FRONT_KEEP["Width"][1]
    top = max(drawing.FRONT_KEEP["CornerR"][1], drawing.RIGHT_KEEP["Depth"][1] + 0.006)
    assert abs((bottom - title_top) - (border_top - top)) < 0.015
    assert drawing.RIGHT_CENTER[1] == drawing.FRONT_CENTER[1]


def test_the_four_rounded_corners_print_once_4x_clear_of_the_holes() -> None:
    """2026-10-11 (user): the plate's corners are rounded per the ch22 back
    photo (R ~1.75 measured -> R.07); one printed 4X radius at .XX, and the
    holes stay outside every corner's R x R square at the printed worst case,
    so their edge ligaments still run to straight edges."""
    import inspect

    r = pd_guide_lock_spec.CORNER_R
    assert r == pytest.approx(0.07 * 25.4)
    assert pd_guide_lock_spec.DRAWING_DIMENSIONS["Corners"] == {"CornerR"}
    assert pd_guide_lock_spec.DRAWING_PRECISION_BY_NAME["CornerR"] == 2
    # A custom prefix replaces SolidWorks' own "R" (farm run
    # 20261012T061737079Z printed "4X 1.8"), so the prefix carries it.
    assert drawing.DIMENSION_PREFIXES["CornerR"] == "4X R"
    source = inspect.getsource(lock.build)
    assert '("Corners", "CornerR", ((LOCK_WIDTH, LOCK_HEIGHT),))' in source
    assert '"OtherCorners"' in source
    assert source.count("'\"LockCornerR\"'") == 1  # both fillets, one drive loop
    r_max = r + _TWO_PLACES
    x_min = min(x for x, _ in pd_guide_lock_spec.HOLE_XY) - _HOLE_BAND
    x_from_right = (
        pd_guide_lock_spec.LOCK_WIDTH
        - _TWO_PLACES
        - max(x for x, _ in pd_guide_lock_spec.HOLE_XY)
        - _HOLE_BAND
    )
    assert min(x_min, x_from_right) > r_max


def test_the_printed_radius_owns_the_top_right_arc_its_text_stands_off() -> None:
    """The printed fillet's only edge is the top-right corner, and the text
    lies up-right of that arc's centre (inside the arc's 0-90 deg sweep), so
    the leader runs from the arc straight out to the text over no geometry."""
    import math

    x, y = drawing.FRONT_KEEP["CornerR"]
    r_sheet = pd_guide_lock_spec.CORNER_R * drawing.SHEET_SCALE[0] / 1000.0
    cx = drawing.RIGHT_EDGE_X - r_sheet
    cy = drawing._sheet_y(pd_guide_lock_spec.LOCK_HEIGHT) - r_sheet
    angle = math.degrees(math.atan2(y - cy, x - cx))
    assert 15.0 < angle < 75.0


def test_the_corner_radius_stands_off_the_top_right_corner() -> None:
    """The 4X R text rides above and right of the plate: clear of the Height's
    extension lines (left), the drill callout below it, and the right view."""
    x, y = drawing.FRONT_KEEP["CornerR"]
    half = len("4X R.07") * _CHAR_WIDTH / 2.0
    top_edge_y = drawing._sheet_y(pd_guide_lock_spec.LOCK_HEIGHT)
    assert y > top_edge_y + 0.010
    assert x - half > drawing.RIGHT_EDGE_X
    assert y > drawing.HOLE_CALLOUT_XY[1] + 0.015
    right_view_left = (
        drawing.RIGHT_CENTER[0]
        - pd_guide_lock_spec.LOCK_THICK * drawing.SHEET_SCALE[0] / 2000.0
    )
    assert x + half < right_view_left


def test_the_plate_is_1_16_sheet_under_its_own_mill_band() -> None:
    """2026-10-11 (user): the lock is 1/16 in sheet as supplied, McMaster
    1388K196 (+/-0.005 in). The supplier's band governs the stock thickness,
    so it prints as its fraction, REF (#290), with the stock callout above
    it, and the registry names the sheet and its band."""
    import _config

    assert pd_guide_lock_spec.LOCK_THICK == pytest.approx(25.4 / 16.0)
    assert pd_guide_lock_spec.LOCK_THICK_BAND == pytest.approx(0.005 * 25.4)
    assert drawing.DIMENSION_CALLOUTS == {
        "Depth": pd_guide_lock_spec.LOCK_STOCK_CALLOUT
    }
    assert "AS SUPPLIED" in pd_guide_lock_spec.LOCK_STOCK_CALLOUT
    # An above-callout with a line break never prints.
    assert "\n" not in pd_guide_lock_spec.LOCK_STOCK_CALLOUT
    spec = _config.parts("pd-guide-lock")
    assert pd_guide_lock_spec.LOCK_STOCK_SKU in spec["material_specification"]
    assert "+/-.005 in" in spec["material_specification"]
    assert "1/16" in spec["material"]
    # Machinist review ENFORCE (PR #1897, rule 2): the printed band, not a
    # grade or ground form, is the requirement, so the field names the family.
    assert spec["material"].startswith("LOW-CARBON STEEL")
    assert "GROUND" not in spec["material"].upper()


def test_part_registry_row_carries_the_title_block_facts() -> None:
    """Stock, finish and quantity live in the title block, not in notes."""
    import _config

    spec = _config.parts("pd-guide-lock")
    assert spec["material_specification"]
    assert "black oxide" in str(spec["finish"]).lower()
    assert int(spec["quantity"]) == 4
