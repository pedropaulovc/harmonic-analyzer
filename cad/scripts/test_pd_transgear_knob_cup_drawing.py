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
    assert set(spec.DRAWING_DIMENSIONS["CupProfile"]) == {
        "CupDia",
        "CupLength",
        "BoreDia",
        "PilotDepth",
        "CboreDia",
        "CboreDepth",
    }
    assert spec.DRAWING_DIMENSIONS[spec.PILOT_FLOOR_FILLET] == {"PilotFloorR"}
    assert spec.DRAWING_DIMENSIONS[spec.POCKET_FLOOR_FILLET] == {"PocketFloorR"}
    assert set(drawing.SECTION_KEEP) == marked - {"HoleDia"}
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
    assert callout.startswith("FLAT BOTTOM END MILL ")
    assert "REAM" not in callout
    assert "THRU" not in callout
    assert f"BONDED FIT ON {shaft}" in callout
    assert f"(CLEARANCE {spec.BORE_CLEARANCE_TEXT})" in callout
    assert spec.BORE_CLEARANCE_TEXT == ".0012-.0025"
    # Every printed row stands a space off the dimension line, and a closing
    # no-break-space row keeps the shelf off the parentheses' tails.
    printed = drawing.SECTION_CALLOUTS["BoreDia"]
    rows = printed.splitlines()
    assert rows[:-1] == [f" {row}" for row in drawing.BORE_CALLOUT.splitlines()]
    assert rows[-1] == "\u00a0"
    # Rule 7: the process line plus two lines of words, 24 characters each.
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


def test_depth_rows_stand_above_the_section_over_their_own_spans() -> None:
    top = drawing.SECTION_TOP
    rear, front = drawing.REAR_FACE_X, drawing.FRONT_FACE_X
    cbore_x, cbore_y = drawing.SECTION_KEEP["CboreDepth"]
    pilot_x, pilot_y = drawing.SECTION_KEEP["PilotDepth"]
    length_x, length_y = drawing.SECTION_KEEP["CupLength"]
    assert cbore_y == pilot_y > top + 0.005
    assert rear < cbore_x < rear + drawing.CBORE_DEPTH_ON_SHEET
    assert front - drawing.PILOT_DEPTH_ON_SHEET < pilot_x < front
    # ".108" and ".152" side by side: 10 mm texts 23 mm apart.
    assert pilot_x - cbore_x > 0.015
    # The length a row higher, its NOTE 1 reference clear of the depths.
    assert length_y - pilot_y > 0.012
    assert length_x == drawing.SECTION_CENTER[0]


def test_front_finish_caption_names_the_bush_rear_face() -> None:
    bush_number = _config.parts("pd-transgear-knob-bush")["number"]
    assert bush_number == drawing.BUSH_NUMBER == "MHA-PD-28"
    caption = " ".join(drawing.FRONT_FINISH_CAPTION.split())
    assert "THRUST FACE" in caption
    assert f"{bush_number} REAR FACE" in caption
    assert drawing.FRONT_FINISH_CAPTION_XY[1] > drawing.FRONT_FINISH[1][1]
    # The pick is on the front face's cut edge, above the pilot's upper
    # extension line; the symbol stands outboard of the length's.
    (pick_x, pick_y), (symbol_x, _) = drawing.FRONT_FINISH
    assert pick_x == drawing.FRONT_FACE_X
    rise = pick_y - drawing.SECTION_CENTER[1]
    assert drawing.HALF_BORE + 0.003 < rise < drawing.HALF_OD - 0.003
    assert symbol_x > drawing.FRONT_FACE_X + 0.010


def test_cup_diameters_stand_between_the_face_view_and_the_section() -> None:
    from _layout_geometry import estimate_text_box

    od_anchor = drawing.SECTION_KEEP["CupDia"]
    od_box = estimate_text_box("Ø.44", anchor=od_anchor, height=0.0035, reference=2)
    cbore_anchor = drawing.SECTION_KEEP["CboreDia"]
    cbore_box = estimate_text_box(
        "Ø.188", anchor=cbore_anchor, height=0.0035, reference=2
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
    cbore_min = spec.CBORE_DIA - _band(spec.CBORE_PLACES)
    clearance = cbore_min / 2.0 - spec.POCKET_FLOOR_R_MAX - screw.HEAD_DIA / 2.0
    assert spec.HEAD_CORNER_CLEARANCE_MIN == pytest.approx(clearance)
    assert clearance == pytest.approx(0.0115 * IN, abs=1e-9)


def test_a_sharper_journal_chamfer_refuses_the_pilot_corner(monkeypatch) -> None:
    monkeypatch.setattr(knob_shaft, "REAR_CHAMFER_MIN", 0.1)
    with pytest.raises(AssertionError, match="pilot floor corner"):
        _fresh_spec()


def test_only_the_pilot_carries_a_model_band() -> None:
    assert model_toleranced_dimensions(part) == {
        ("CupProfile", "BoreDia"): "*deviations(BORE_BAND)",
    }
    # The 1/4 end mill's own -.000/+.001 Ø band.
    assert spec.BORE_DIA == pytest.approx(0.250 * IN)
    assert spec.BORE_BAND == pytest.approx((0.001 * IN, 0.0))


def test_owner_sizes_follow_the_bush_stub() -> None:
    """Owner ruling 2026-11-20 (Pedro), #2425: "pd-16 diameter should also be
    reduced to match new knob bush"."""
    assert spec.OD == pytest.approx(0.44 * IN)
    assert round(bush.PRESS_DIA / IN, spec.OD_PLACES) == pytest.approx(spec.OD / IN)
    assert spec.LENGTH == pytest.approx(0.36 * IN)
    assert spec.PILOT_DEPTH == pytest.approx(0.152 * IN)
    assert spec.CLEAR_HOLE_DIA == pytest.approx(0.113 * IN)  # #33
    assert spec.CBORE_DIA == pytest.approx(0.188 * IN)
    assert spec.CBORE_DEPTH == pytest.approx(0.108 * IN)
    assert spec.WEB == pytest.approx(0.100 * IN)


def test_walls_hold_at_the_worst_case_the_sheet_prints() -> None:
    """Rule 17: the web and both rings, recomputed from the printed rows."""
    od_min = spec.OD - _band(spec.OD_PLACES)
    web_min = (
        (spec.LENGTH - _band(spec.LENGTH_PLACES))
        - (spec.PILOT_DEPTH + _band(spec.PILOT_DEPTH_PLACES))
        - (spec.CBORE_DEPTH + _band(spec.CBORE_PLACES))
    )
    pilot_wall = (od_min - (spec.BORE_DIA + max(spec.BORE_BAND))) / 2.0
    cbore_wall = (od_min - (spec.CBORE_DIA + _band(spec.CBORE_PLACES))) / 2.0
    assert spec.WEB_MIN == pytest.approx(web_min)
    assert spec.PILOT_WALL_WORST == pytest.approx(pilot_wall)
    assert spec.CBORE_WALL_WORST == pytest.approx(cbore_wall)
    # .080 web (exactly the target), .0895 and .1185 rings.
    assert web_min == pytest.approx(0.080 * IN, abs=1e-9)
    assert pilot_wall == pytest.approx(0.0895 * IN, abs=1e-9)
    assert cbore_wall == pytest.approx(0.1185 * IN, abs=1e-9)
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
    assert spec.BORE_JOURNAL_CLEARANCE == pytest.approx((0.03048, 0.0635))
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
    cbore_min = spec.CBORE_DIA - _band(spec.CBORE_PLACES)
    assert (cbore_min - screw.HEAD_DIA) / 2.0 == pytest.approx(0.0215 * IN, abs=1e-9)
    depth_min = spec.CBORE_DEPTH - _band(spec.CBORE_PLACES)
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
    # Each floor fillet's spandrel, by Pappus at its centroid.
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
