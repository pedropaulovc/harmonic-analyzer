"""Offline contracts for the transgear knob cup (MHA-PD-16) drawing."""

from __future__ import annotations

import importlib.util
import math
from pathlib import Path

import pytest

import _config
import build_pd_transgear_knob_cup as part
import draw_pd_transgear_knob_cup as drawing
import pd_transgear_knob_bush_geometry as bush
import pd_transgear_knob_cup_spec as spec
import pd_transgear_knob_shaft_spec as knob_shaft
import pd_vn_transgear_knob_cup_screw_spec as screw
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _hole_spec import TAP_DRILL_MM
from _inch_wall_limits import WALL_TARGET_MM
from _printed_tolerance import drilled_oversize_mm, printed_band_mm

IN = 25.4


def _band(places: int) -> float:
    """The +/- the title block prints for ``places`` (what the shop reads)."""
    return printed_band_mm(places, unit=spec.UNIT)


def _fresh_spec():
    fresh_spec = importlib.util.spec_from_file_location("_cup_perturbed", spec.__file__)
    fresh = importlib.util.module_from_spec(fresh_spec)
    fresh_spec.loader.exec_module(fresh)
    return fresh


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/pd-transgear-knob-cup.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/pd-transgear-knob-cup.pdf")
    assert (
        DRAWINGS_BY_NAME["pd_transgear_knob_cup"].script
        == Path(drawing.__file__).resolve()
    )
    assert Path(drawing.__file__).name in PRECISION_MIGRATED_DRAWINGS


def test_every_marked_dimension_prints_once_with_model_places() -> None:
    """Rule 11: the turner reads every turned size and both floor corners on
    A-A; the web's drill prints on the face view, where it shows round."""
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    # The floor corners are sketch arcs in the profile: a fillet feature's
    # radius did not import into the section (farm r3).
    assert set(spec.DRAWING_DIMENSIONS["CupProfile"]) == {
        "CupDia",
        "CupLength",
        "BoreDia",
        "PilotDepth",
        "CboreDia",
        "CboreDepth",
        "PilotFloorR",
        "PocketFloorR",
    }
    assert set(spec.DRAWING_DIMENSIONS) == {"CupProfile", "WebHole"}
    assert set(drawing.SECTION_KEEP) == set(spec.DRAWING_DIMENSIONS["CupProfile"])
    assert (
        set(drawing.FACE_KEEP) == set(spec.DRAWING_DIMENSIONS["WebHole"]) == {"HoleDia"}
    )
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked
    assert {
        (feature, name)
        for feature, names in spec.DRAWING_PRECISION.items()
        for name in names
    } == {
        (feature, name)
        for feature, names in spec.DRAWING_DIMENSIONS.items()
        for name in names
    }
    assert set(drawing.SECTION_CALLOUTS) <= set(drawing.SECTION_KEEP)
    assert set(drawing.FACE_CALLOUTS) <= set(drawing.FACE_KEEP)


def test_the_section_cuts_the_cup_axis_and_lies_level_beside_the_face_view() -> None:
    (x0, y0), (x1, y1) = drawing.SECTION_LINE
    assert x0 == x1 == drawing.FACE_CENTER[0]
    assert y0 < drawing.FACE_CENTER[1] - drawing.HALF_OD
    assert y1 > drawing.FACE_CENTER[1] + drawing.HALF_OD
    # A quarter turn makes the vertical cut the Front plane (the profile's).
    assert abs(math.remainder(drawing.FACE_VIEW_ANGLE, math.pi)) == pytest.approx(
        math.pi / 2.0
    )
    assert drawing.SECTION_CENTER[1] == drawing.FACE_CENTER[1]
    assert drawing.SECTION_CENTER[0] > drawing.FACE_CENTER[0]
    assert drawing.FRONT_FACE_X == pytest.approx(
        drawing.SECTION_CENTER[0] + spec.LENGTH * drawing._S / 2000.0
    )


def _block_half_width(text: str, anchor: tuple[float, float]) -> float:
    """The larger of the generic estimate and the 2.45 mm a character
    draw_mg_magnifying_wheel measured on a farm render."""
    from _layout_geometry import estimate_text_box

    halves = []
    for line in text.splitlines():
        box = estimate_text_box(line, anchor=anchor, height=0.0035, reference=5)
        assert box is not None
        halves.append(max(box.xmax - anchor[0], len(line) * 0.00245 / 2.0))
    return max(halves)


def test_pilot_callout_names_its_bonded_mate_and_stands_clear_below_the_pilot() -> None:
    """Rule 23: a bonded fit is a fit; the part sheet gives the mate and the
    diametral clearance."""
    shaft = _config.parts("pd-transgear-knob-shaft")["number"]
    callout = " ".join(drawing.BORE_CALLOUT.split())
    # Rule 7, machinist review r10: no tool or method words; the section
    # draws the flat floor and R.005 MAX limits its corner.
    assert "END MILL" not in callout and "FLAT BOTTOM" not in callout
    assert callout.startswith("BONDED FIT ON ")
    assert "REAM" not in callout
    assert "THRU" not in callout
    assert f"BONDED FIT ON {shaft}" in callout
    assert f"(CLEARANCE {spec.BORE_CLEARANCE_TEXT})" in callout
    assert spec.BORE_CLEARANCE_TEXT == ".0012-.0055"
    # Every printed row stands a space off the dimension line, and a closing
    # no-break-space row keeps the shelf off the parentheses' tails.
    printed = drawing.SECTION_CALLOUTS["BoreDia"]
    rows = printed.splitlines()
    assert rows[:-1] == [f" {row}" for row in drawing.BORE_CALLOUT.splitlines()]
    assert rows[-1] == "\u00a0"
    # Rule 7: two lines of words, 24 characters each.
    assert all(len(row) <= 24 for row in drawing.BORE_CALLOUT.splitlines())

    anchor = drawing.SECTION_KEEP["BoreDia"]
    half = _block_half_width(printed, anchor)
    # Right of the front face, left of the isometric (about the O.D. wide).
    assert anchor[0] - half > drawing.FRONT_FACE_X + 0.010
    assert anchor[0] + half < drawing.ISO_CENTER[0] - drawing.HALF_OD - 0.010
    # Wholly below the pilot's lower extension line, above the title block.
    top = anchor[1] + drawing.BORE_BLOCK_HALF_HEIGHT
    assert top + 0.003 < drawing.SECTION_CENTER[1] - drawing.HALF_BORE
    assert anchor[1] - drawing.BORE_BLOCK_HALF_HEIGHT > 0.075
    # Right of the section caption ("SECTION A-A", 45 mm wide on eecbf88).
    assert anchor[0] - half > drawing.CAPTION_XY[0] + 0.0225 + 0.005


def test_supply_sizes_cite_note_1_and_the_note_gives_the_fitted_depth() -> None:
    """Rule 19: a size set at assembly prints its supply size and its fitted
    range with the step that sets it."""
    import pd_paper_drive_assembly_steps as steps

    for name in ("CupLength", "PilotDepth"):
        assert drawing.SECTION_CALLOUTS[name] == "SEE NOTE 1"
    note = " ".join(drawing.NOTES.split())
    assert note.startswith("NOTES: 1. LENGTH AND PILOT DEPTH ARE SUPPLY SIZES.")
    assert note.endswith(
        f"FITTED PILOT DEPTH {spec.PILOT_DEPTH_FITTED_TEXT} AT "
        f"{steps.step_ref('knob-stack-fitted')}."
    )
    assert spec.PILOT_DEPTH_FITTED_TEXT == ".116-.148"
    # The float and the facing action are the assembly step's, not the part's.
    assert "END FLOAT" not in note and "FACE THE" not in note
    # Below the face view, left of the section.
    assert drawing.NOTES_XY[1] < drawing.FACE_CENTER[1] - drawing.HALF_OD - 0.010


def test_web_hole_prints_its_drill_on_the_face_view() -> None:
    assert drawing.FACE_CALLOUTS == {"HoleDia": "#33 DRILL THRU"}
    x, y = drawing.FACE_KEEP["HoleDia"]
    assert y > drawing.FACE_CENTER[1] + drawing.HALF_OD
    assert x < drawing.FACE_CENTER[0]


def test_depth_rows_stand_above_the_section_clear_of_each_other() -> None:
    top = drawing.SECTION_TOP
    rear, front = drawing.REAR_FACE_X, drawing.FRONT_FACE_X
    cbore_x, cbore_y = drawing.SECTION_KEEP["CboreDepth"]
    pilot_x, pilot_y = drawing.SECTION_KEEP["PilotDepth"]
    length_x, length_y = drawing.SECTION_KEEP["CupLength"]
    assert cbore_y == pilot_y > top + 0.005
    # r6 audit: ".108" (8.5 mm) inside its 11 mm span stood 1.39 mm from the
    # length's extension line (2.0 wanted); it stands outside left of the
    # rear face, 2 mm or more clear of that shared line.  r11: its third
    # place states its function on the row under it, which runs over the
    # O.D.'s upper extension line and ends right of the cutting line's letter.
    import pd_transgear_knob_cup_notes as notes

    assert drawing.CBORE_DEPTH_CALLOUT is notes.CBORE_DEPTH_CALLOUT == "HOLDS WEB .080 MIN"
    assert drawing.SECTION_CALLOUTS["CboreDepth"] == drawing.CBORE_DEPTH_CALLOUT
    assert spec.WEB_MIN == pytest.approx(0.080 * IN, abs=1e-9)
    cbore_half = drawing.CBORE_DEPTH_TEXT_HALF_WIDTH
    assert cbore_x + cbore_half < rear - 0.002
    assert drawing.CBORE_DEPTH_ON_SHEET < 2.0 * (cbore_half + 0.002)
    row_bottom = cbore_y - 0.005 - 0.00175
    assert row_bottom > top + 0.002
    letter_right = drawing.FACE_CENTER[0] + 0.023  # "A" beside the arrow, r11
    assert cbore_x - cbore_half > letter_right + 0.005
    # r5 render: ".152 / SEE NOTE 1" (24 mm) over its 15 mm span was struck
    # by the length's extension line from the front face and by the pocket
    # depth's arrow.  Its text now stands wholly right of the front face.
    half = drawing.DEPTH_TEXT_HALF_WIDTH
    assert drawing.SECTION_CALLOUTS["PilotDepth"] == "SEE NOTE 1"
    assert pilot_x - half > front + 0.002
    assert drawing.PILOT_DEPTH_ON_SHEET < 2.0 * half  # why it cannot sit inside
    # The length a row higher, its NOTE 1 reference clear of the depths.
    assert length_y - pilot_y > 0.012
    assert length_x == drawing.SECTION_CENTER[0]


def test_front_finish_caption_names_the_bush_rear_face() -> None:
    bush_number = _config.parts("pd-transgear-knob-bush")["number"]
    assert bush_number == drawing.BUSH_NUMBER == "MHA-PD-28"
    caption = " ".join(drawing.FRONT_FINISH_CAPTION.split())
    assert "THRUST FACE" in caption
    assert caption == f"THRUST FACE ON {bush_number}"
    assert len(drawing.FRONT_FINISH_CAPTION.splitlines()) == 2
    # Machinist review r10: over the symbol the caption stood on the pilot
    # depth's row and read as that dimension's words.  It hangs on the
    # symbol's row, right of the Ra text, short of the isometric's outline
    # and over the pilot Ø's upper arrow.
    left, top = drawing.FRONT_FINISH_CAPTION_XY
    width, height = drawing.FRONT_FINISH_CAPTION_SIZE_M
    symbol = drawing.FRONT_FINISH[1]
    assert left > symbol[0] + 0.0137 + 0.002
    assert top - height < symbol[1] + 0.0043 < symbol[1] + 0.0068 < top
    assert left + width < drawing.ISO_CENTER[0] - 0.0372 - 0.0015
    upper_extension = drawing.SECTION_CENTER[1] + drawing.HALF_BORE
    assert top - height > upper_extension + 0.0035 + 0.002
    pilot_text_right = (
        drawing.SECTION_KEEP["PilotDepth"][0] + drawing.DEPTH_TEXT_HALF_WIDTH
    )
    assert left > pilot_text_right + 0.020
    # The pick is on the front face's cut edge, above the pilot's upper
    # extension line; the symbol stands level with it, so the leader runs
    # straight in under the pilot depth's text.
    (pick_x, pick_y), (symbol_x, symbol_y) = drawing.FRONT_FINISH
    assert pick_x == drawing.FRONT_FACE_X
    rise = pick_y - drawing.SECTION_CENTER[1]
    assert drawing.HALF_BORE + 0.003 < rise < drawing.HALF_OD - 0.003
    assert symbol_y == pick_y
    # The leader and symbol stay under the pilot depth's row (its text
    # bottom ~2.8 mm under its keep), the caption right of that text.
    pilot_right = drawing.SECTION_KEEP["PilotDepth"][0] + drawing.DEPTH_TEXT_HALF_WIDTH
    assert symbol_x - 0.0015 > pilot_right + 0.003
    assert drawing.FRONT_FINISH_CAPTION_XY[0] > pilot_right + 0.002
    # The Ra text (~14 mm right of the V) ends short of the bore Ø's line.
    assert symbol_x + 0.014 < drawing.SECTION_KEEP["BoreDia"][0] - 0.005


def test_cup_diameters_stand_between_the_face_view_and_the_section() -> None:
    from _layout_geometry import estimate_text_box

    od_anchor = drawing.SECTION_KEEP["CupDia"]
    od_box = estimate_text_box("Ø.44", anchor=od_anchor, height=0.0035, reference=2)
    cbore_anchor = drawing.SECTION_KEEP["CboreDia"]
    cbore_box = estimate_text_box(
        "Ø.19", anchor=cbore_anchor, height=0.0035, reference=2
    )
    assert od_box is not None and cbore_box is not None
    # Clear of the face view's centre-mark tail and of the section.
    assert od_box.xmin > drawing.FACE_CENTER[0] + drawing.HALF_OD + 0.010
    assert cbore_box.xmax < drawing.REAR_FACE_X - 0.003
    assert od_anchor[1] == drawing.SECTION_CENTER[1]
    # The pocket's text stands below the O.D.'s, clear of it.
    assert cbore_box.ymax < od_box.ymin or cbore_box.xmin > od_box.xmax
    assert cbore_anchor[1] < drawing.SECTION_CENTER[1] - drawing.HALF_CBORE
    assert cbore_anchor[1] > drawing.SECTION_CENTER[1] - drawing.HALF_OD
    # The native caption hangs below the section and its corner-radius row.
    assert drawing.CAPTION_XY[1] < drawing.SECTION_CENTER[1] - drawing.HALF_OD - 0.005


def test_floor_corners_print_their_max_radius_under_their_own_corners() -> None:
    """Rule 16: each corner's largest acceptable radius, on one row under the
    section, above the caption and left of the pilot's callout block."""
    pocket = drawing.SECTION_KEEP["PocketFloorR"]
    pilot = drawing.SECTION_KEEP["PilotFloorR"]
    assert pocket[1] == pilot[1] < drawing.SECTION_BOTTOM - 0.005
    assert drawing.CAPTION_XY[1] < pocket[1] - 0.010
    assert drawing.REAR_FACE_X - 0.005 < pocket[0] < pilot[0] < drawing.FRONT_FACE_X
    bore = drawing.SECTION_KEEP["BoreDia"]
    half = _block_half_width(drawing.SECTION_CALLOUTS["BoreDia"], bore)
    assert pilot[0] + 0.012 < bore[0] - half


def test_floor_corners_are_max_limits_that_clear_their_mates() -> None:
    """The journal's least .010 rear chamfer clears the pilot's R.005 MAX
    floor corner, and the head lands inside the pocket's R.010 MAX one."""
    assert spec.PILOT_FLOOR_R_MAX == pytest.approx(0.005 * IN)
    assert spec.POCKET_FLOOR_R_MAX == pytest.approx(0.010 * IN)
    assert spec.CORNER_SUFFIX == " MAX"
    assert spec.CORNER_TOL_TYPE == 0
    assert knob_shaft.REAR_CHAMFER_MIN == pytest.approx(0.010 * IN)
    assert knob_shaft.REAR_CHAMFER_MIN >= spec.PILOT_FLOOR_R_MAX
    cbore_min = spec.CBORE_DIA - _band(spec.CBORE_DIA_PLACES)
    clearance = cbore_min / 2.0 - spec.POCKET_FLOOR_R_MAX - screw.HEAD_DIA / 2.0
    assert spec.HEAD_CORNER_CLEARANCE_MIN == pytest.approx(clearance)
    assert clearance == pytest.approx(0.010 * IN, abs=1e-9)


def test_a_sharper_journal_chamfer_refuses_the_pilot_corner(monkeypatch) -> None:
    monkeypatch.setattr(knob_shaft, "REAR_CHAMFER_MIN", 0.1)
    with pytest.raises(AssertionError, match="pilot floor corner"):
        _fresh_spec()


def test_only_the_pilot_carries_a_model_band() -> None:
    assert model_toleranced_dimensions(part) == {
        ("CupProfile", "BoreDia"): "*deviations(BORE_BAND)",
    }
    # A bonded seat at the DRILLED HOLES row, +.004/0 (fit audit 2026-11-23).
    assert spec.BORE_DIA == pytest.approx(0.250 * IN)
    assert spec.BORE_BAND == pytest.approx((0.004 * IN, 0.0))


def test_owner_sizes_follow_the_bush_stub() -> None:
    """Owner ruling 2026-11-20 (Pedro), #2425: "pd-16 diameter should also be
    reduced to match new knob bush"."""
    assert spec.OD == pytest.approx(0.44 * IN)
    assert round(bush.PRESS_DIA / IN, spec.OD_PLACES) == pytest.approx(spec.OD / IN)
    assert spec.LENGTH == pytest.approx(0.36 * IN)
    assert spec.PILOT_DEPTH == pytest.approx(0.152 * IN)
    assert spec.CLEAR_HOLE_DIA == pytest.approx(0.113 * IN)  # #33
    assert spec.CBORE_DIA == pytest.approx(0.19 * IN)
    assert (spec.CBORE_DIA_PLACES, spec.CBORE_DEPTH_PLACES) == (2, 3)
    assert spec.CBORE_DEPTH == pytest.approx(0.108 * IN)
    assert spec.WEB == pytest.approx(0.100 * IN)


def test_walls_hold_at_the_worst_case_the_sheet_prints() -> None:
    """Rule 17: the web and both rings, recomputed from the printed rows."""
    od_min = spec.OD - _band(spec.OD_PLACES)
    web_min = (
        (spec.LENGTH - _band(spec.LENGTH_PLACES))
        - (spec.PILOT_DEPTH + _band(spec.PILOT_DEPTH_PLACES))
        - (spec.CBORE_DEPTH + _band(spec.CBORE_DEPTH_PLACES))
    )
    pilot_wall = (od_min - (spec.BORE_DIA + max(spec.BORE_BAND))) / 2.0
    cbore_wall = (od_min - (spec.CBORE_DIA + _band(spec.CBORE_DIA_PLACES))) / 2.0
    assert spec.WEB_MIN == pytest.approx(web_min)
    assert spec.PILOT_WALL_WORST == pytest.approx(pilot_wall)
    assert spec.CBORE_WALL_WORST == pytest.approx(cbore_wall)
    # .080 web (exactly the target), .088 (the +.004 pilot) and .115 rings.
    assert web_min == pytest.approx(0.080 * IN, abs=1e-9)
    assert pilot_wall == pytest.approx(0.088 * IN, abs=1e-9)
    assert cbore_wall == pytest.approx(0.115 * IN, abs=1e-9)
    for wall in (web_min, pilot_wall, cbore_wall):
        assert wall >= WALL_TARGET_MM - 1e-9


def test_a_looser_length_row_refuses_the_thin_web(monkeypatch) -> None:
    assert _fresh_spec().WEB_MIN == pytest.approx(spec.WEB_MIN)
    import _printed_tolerance

    real = _printed_tolerance.printed_deviations

    def looser_two_place_row(value, places, limits=None, **kwargs):
        if places == 2:  # the O.D. and the length
            return (-0.3, 0.3)
        return real(value, places, limits, **kwargs)

    monkeypatch.setattr(_printed_tolerance, "printed_deviations", looser_two_place_row)
    with pytest.raises(AssertionError, match="web"):
        _fresh_spec()


def test_the_bonded_pilot_clears_the_journal_inside_641_gap_fill() -> None:
    tightest = (spec.BORE_DIA + min(spec.BORE_BAND)) - (
        knob_shaft.JOURNAL_DIA + max(knob_shaft.JOURNAL_DIA_BAND)
    )
    loosest = (spec.BORE_DIA + max(spec.BORE_BAND)) - knob_shaft.JOURNAL_DIA_MIN
    assert 0.0 < tightest <= loosest <= spec.LOCTITE_641_GAP_MAX == 0.15
    assert spec.BORE_JOURNAL_CLEARANCE == pytest.approx((tightest, loosest))


def test_cup_bore_refuses_binding_on_the_actual_journal(monkeypatch) -> None:
    assert spec.BORE_JOURNAL_CLEARANCE == pytest.approx((0.03048, 0.1397))
    # The .254 limit is what keeps the bond gap inside LOCTITE 641's fill:
    # one more thousandth on the pilot passes it.
    assert max(spec.BORE_JOURNAL_CLEARANCE) + 0.0254 > spec.LOCTITE_641_GAP_MAX
    monkeypatch.setattr(knob_shaft, "JOURNAL_DIA_BAND", (0.030, 0.0))
    with pytest.raises(AssertionError, match="bore binds"):
        _fresh_spec()


def test_the_front_facing_sets_the_float_on_every_stack() -> None:
    """Rule 19: the supplied pilot is never shallower than the float needs;
    the fitter faces .001-.039 off the front and leaves .116-.148."""
    assert spec.PILOT_DEPTH_FITTED == pytest.approx(
        knob_shaft.JOURNAL_STANDOUT - knob_shaft.END_FLOAT
    )
    assert tuple(v / IN for v in spec.FACING_REMOVAL) == pytest.approx((0.001, 0.039))
    assert tuple(v / IN for v in spec.PILOT_DEPTH_FITTED_RANGE) == pytest.approx(
        (0.116, 0.148)
    )
    assert spec.PILOT_DEPTH_FITTED_RANGE[0] >= spec.PILOT_DEPTH_FITTED_FLOOR


def test_a_shallow_supplied_pilot_refuses(monkeypatch) -> None:
    # A stand-out stack .040 wider than the supplied pilot can take up.
    monkeypatch.setattr(
        knob_shaft,
        "JOURNAL_STANDOUT_BAND",
        knob_shaft.JOURNAL_STANDOUT_BAND + 0.040 * IN,
    )
    with pytest.raises(AssertionError, match="shallower"):
        _fresh_spec()


def test_the_screw_engages_the_journal_tap_and_never_bottoms() -> None:
    """Rule 18 at the worst case: the shortest screw through the thickest
    web, less the tap mouth's first thread and break and the screw's point."""
    engagement = (
        screw.LENGTH
        - screw.LENGTH_MINUS
        - spec.WEB_MAX
        - (screw.PITCH + knob_shaft.EDGE_BREAK_MAX)
        - 2.0 * screw.PITCH
    )
    assert spec.SCREW_ENGAGEMENT_MIN == pytest.approx(engagement)
    assert engagement / screw.MAJOR_DIA >= 1.5
    assert spec.SCREW_ENGAGEMENT_MIN_D == pytest.approx(1.877, abs=1e-3)
    reach = screw.LENGTH - spec.WEB_MIN
    assert reach == pytest.approx(0.295 * IN, abs=1e-9)
    assert knob_shaft.REAR_TAP_FULL_THREAD_MIN - reach == pytest.approx(
        0.045 * IN, abs=1e-9
    )


def test_the_head_seats_on_the_web_inside_the_pocket() -> None:
    hole_min = spec.CLEAR_HOLE_DIA
    hole_max = spec.CLEAR_HOLE_DIA + drilled_oversize_mm(unit=spec.UNIT)
    assert hole_min - 1.3 * screw.MAJOR_DIA == pytest.approx(
        spec.HOLE_FILLET_CLEARANCE_MIN
    )
    assert spec.HOLE_FILLET_CLEARANCE_MIN > 0.0
    assert spec.HEAD_BEARING_LAND == pytest.approx((screw.HEAD_DIA - hole_max) / 2.0)
    assert spec.HEAD_BEARING_LAND > 0.0
    cbore_min = spec.CBORE_DIA - _band(spec.CBORE_DIA_PLACES)
    assert (cbore_min - screw.HEAD_DIA) / 2.0 == pytest.approx(0.020 * IN, abs=1e-9)
    depth_min = spec.CBORE_DEPTH - _band(spec.CBORE_DEPTH_PLACES)
    assert depth_min - screw.HEAD_H == pytest.approx(0.020 * IN, abs=1e-9)
    # The screw's clearance drill is the #2 close fit, never the tap drill.
    assert spec.CLEAR_HOLE_DIA > TAP_DRILL_MM[knob_shaft.REAR_TAP_THREAD]


def test_the_part_volume_is_the_turned_cup_less_the_web_drill() -> None:
    r = spec.OD / 2.0
    turned = math.pi * (
        r**2 * spec.LENGTH
        - (spec.BORE_DIA / 2.0) ** 2 * spec.PILOT_DEPTH
        - (spec.CBORE_DIA / 2.0) ** 2 * spec.CBORE_DEPTH
    )
    assert part.V_TURNED == pytest.approx(turned)
    # Each floor arc's spandrel, by Pappus at its centroid.
    corners = 0.0
    for radius, wall_r in (
        (spec.PILOT_FLOOR_R_MAX, spec.BORE_DIA / 2.0),
        (spec.POCKET_FLOOR_R_MAX, spec.CBORE_DIA / 2.0),
    ):
        centroid = wall_r - radius * (10.0 - 3.0 * math.pi) / (3.0 * (4.0 - math.pi))
        corners += (1.0 - math.pi / 4.0) * radius**2 * 2.0 * math.pi * centroid
    assert part.V_CORNERS == pytest.approx(corners)
    assert part.V_CUP == pytest.approx(
        turned - math.pi * (spec.CLEAR_HOLE_DIA / 2.0) ** 2 * spec.WEB + corners
    )


def test_registry_row_is_the_turned_brass_mha_157() -> None:
    row = _config.parts(part.PART_NAME)
    assert row["number"] == "MHA-PD-16"
    assert int(row["quantity"]) == 1
    assert "C36000" in row["material_specification"]
    assert row["material"] == part.MATERIAL
    assert row["tolerance_class"] == "machined_block"
    process = row["process"]
    assert "#33" in process and "LOCTITE 641" in process
    assert "spring-pin" not in process


def _plane_face(normal: tuple[float, float, float], offset_mm: float):
    from _gtol_face import SURFACE_PLANE, FaceGeometry

    point = tuple(value * offset_mm / 1000 for value in normal)
    return FaceGeometry(None, SURFACE_PLANE, (*normal, *point), normal, ())


def _cylinder_face(dia_mm: float):
    from _gtol_face import SURFACE_CYLINDER, FaceGeometry

    return FaceGeometry(
        None, SURFACE_CYLINDER, (0.0, 0.0, 0.0, 0.0, 1.0, 0.0, dia_mm / 2000), None, ()
    )


def test_each_declared_cup_face_has_exactly_one_owner() -> None:
    import export_features

    selectors = export_features.feature_selectors("pd_transgear_knob_cup")
    faces = {
        "front_face": [_plane_face((0.0, -1.0, 0.0), 0.0)],
        "rear_face": [_plane_face((0.0, 1.0, 0.0), spec.LENGTH)],
        "outside": [_cylinder_face(spec.OD)],
        "pilot": [
            _cylinder_face(spec.BORE_DIA),
            _plane_face((0.0, -1.0, 0.0), -spec.PILOT_DEPTH),
        ],
        "web_hole": [_cylinder_face(spec.CLEAR_HOLE_DIA)],
        "pocket": [
            _cylinder_face(spec.CBORE_DIA),
            _plane_face((0.0, 1.0, 0.0), spec.LENGTH - spec.CBORE_DEPTH),
        ],
    }
    assert set(selectors) == set(faces)
    for name, geometries in faces.items():
        for face in geometries:
            owners = [
                owner
                for owner, specs in selectors.items()
                if any(selector.matches(face) for selector in specs)
            ]
            assert owners == [name]


def test_declarations_print_the_sheets_bands_and_supply_sizes() -> None:
    import export_features

    manifest = export_features.requirement_manifest("pd_transgear_knob_cup")
    features = manifest["features"]

    def inch(values: list[float]) -> list[float]:
        return [round(value / IN, 4) for value in values]

    assert inch(features["outside"]["dia"]) == [0.43, 0.45]
    assert inch(features["rear_face"]["length"]) == [0.35, 0.37]
    assert inch(features["pilot"]["dia"]) == [0.25, 0.254]
    assert inch(features["pilot"]["depth"]) == [0.147, 0.157]
    assert inch(features["pilot"]["diametral_clearance"]) == [0.0012, 0.0055]
    assert inch([features["pilot"]["corner_radius_max"]]) == [0.005]
    assert inch(features["web_hole"]["dia"]) == [0.113, 0.117]
    assert inch(features["pocket"]["dia"]) == [0.18, 0.2]
    assert inch(features["pocket"]["depth"]) == [0.103, 0.113]
    assert inch([features["pocket"]["corner_radius_max"]]) == [0.01]
    # Note 1: length and pilot depth are supply sizes; the front face is
    # faced at MHA-PD-00 to the fitted pilot depth.
    assert features["rear_face"]["supply"] and features["pilot"]["supply"]
    assert features["front_face"]["faced_at"] == "assembly"
    assert manifest["notes"]["manufacturing"] == drawing.NOTES.splitlines()


def test_the_travelers_name_the_assembly_steps_they_leave_work_for():
    # The cup's and the bush's travelers print MHA-PD-00's step numbers as
    # text; they must follow the assembly sequence when steps are inserted.
    import re

    import pd_paper_drive_assembly_steps as steps

    process = Path(__file__).resolve().parents[1] / "process"
    for stem, key in (
        ("pd_transgear_knob_cup", "knob-stack-fitted"),
        ("pd_transgear_knob_bush", "pin-pressed"),
    ):
        text = "".join(
            path.read_text(encoding="utf-8")
            for path in (
                process / stem / "plan.toml",
                *(process / stem).glob("diagrams/*.svg"),
            )
        )
        cited = set(re.findall(r"MHA-PD-00 step (\d+)", text))
        assert cited == {str(steps.step_number(key))}, stem
