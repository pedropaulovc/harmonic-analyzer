"""Offline contracts for the transgear knob bush (MHA-PD-28) and its drawing."""

from __future__ import annotations

import importlib.util
import math
import tomllib
from pathlib import Path

import pytest

import _config
import _printed_tolerance
import _shop_equipment
import build_pd_transgear_knob_bush as part
import draw_pd_transgear_knob_bush as drawing
import paper_drive_arm_registration as REGISTRATION
import pd_transgear_arm_plate_geometry as PLATE
import pd_transgear_knob_bush_geometry as BUSH
import pd_transgear_knob_bush_spec as spec
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _gtol_cylinder import CylinderFace
from _gtol_planar import PlanarFace
from _inch_wall_limits import WALL_FLOOR_MM, WALL_TARGET_MM
from _machinist_review_mode import MachinistReviewMode
from _paths import CAD_ROOT
from _surface_finish import MACHINED_UM
from pd_cluster_stack_band import FIT_LENGTH_BAND_IN


def _in(value_in: float) -> float:
    return value_in * 25.4


def _number(stem: str) -> str:
    return _config.parts(stem)["number"]


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/pd-transgear-knob-bush.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/pd-transgear-knob-bush.pdf")
    assert (
        DRAWINGS_BY_NAME["pd_transgear_knob_bush"].script
        == Path(drawing.__file__).resolve()
    )
    assert Path(drawing.__file__).name in PRECISION_MIGRATED_DRAWINGS
    assert drawing.MACHINIST_REVIEW is MachinistReviewMode.ENFORCE


def test_the_contract_dimensions_are_the_ruled_variant() -> None:
    """#2425: hub Ø.52 x .809 to the shoulder, press Ø.4385 REF (the plate's
    set reamer; fit audit 2026-11-23) on to the rear face, 1.143 overall,
    bore .249 reamed after a .238 (B) drill."""
    assert BUSH.HUB_DIA == pytest.approx(_in(0.52))
    assert BUSH.HUB_LENGTH == pytest.approx(_in(0.809))
    assert BUSH.HUB_LENGTH_BAND == FIT_LENGTH_BAND_IN
    assert BUSH.SHOULDER_SEAT_GAP_MAX == pytest.approx(_in(0.0005))
    assert BUSH.LENGTH == pytest.approx(_in(1.143))
    assert BUSH.LENGTH_BAND == pytest.approx(_in(0.002))
    assert BUSH.STUB_LENGTH == pytest.approx(_in(0.334))
    assert BUSH.PRESS_DIA == pytest.approx(_in(0.4385))
    assert BUSH.BORE_DIA == pytest.approx(_in(0.249))
    assert BUSH.BORE_DIA_LIMITS == pytest.approx((0.0, _in(0.0005)))
    assert BUSH.PRE_REAM_DRILL_DIA == pytest.approx(_in(0.238))
    assert BUSH.KNOB_BORE_LENGTH_MIN_MM == pytest.approx(
        BUSH.LENGTH - BUSH.LENGTH_BAND - 2.0 * BUSH.EDGE_BREAK_MAX_MM
    )
    assert (
        BUSH.HUB_DIA_PLACES,
        BUSH.HUB_LENGTH_PLACES,
        BUSH.LENGTH_PLACES,
        BUSH.PRESS_DIA_PLACES,
        BUSH.BORE_PLACES,
    ) == (2, 3, 3, 4, 4)
    assert BUSH.UNIT == "in"


def test_the_press_is_turned_to_the_measured_hole() -> None:
    """Fit audit 2026-11-23 (rule 4, made to fit): the plate's hole is cut
    by the .4385 set reamer (modelled +.0005/0) and the step is turned
    .0005-.0016 over that hole as measured, a range over .001 wide.  The
    step's own band is the analysis envelope, not a printed limit."""
    hole = tuple(BUSH.PRESS_DIA + deviation for deviation in BUSH.PRESS_HOLE_BAND)
    assert hole == pytest.approx((_in(0.4390), _in(0.4385)))
    assert BUSH.PRESS_INTERFERENCE == pytest.approx((_in(0.0005), _in(0.0016)))
    assert max(BUSH.PRESS_INTERFERENCE) - min(BUSH.PRESS_INTERFERENCE) >= _in(0.001)
    press = tuple(BUSH.PRESS_DIA + deviation for deviation in BUSH.PRESS_DIA_BAND)
    assert min(press) == pytest.approx(min(hole) + BUSH.PRESS_INTERFERENCE[0])
    assert max(press) == pytest.approx(max(hole) + BUSH.PRESS_INTERFERENCE[1])
    assert BUSH.PRESS_DIA_MIN == pytest.approx(min(press))
    # The traveler's pilot only reads the hole and is faced off before the
    # press diameter is cut: the geometry carries no pilot.
    assert not [name for name in vars(BUSH) if name.startswith("PILOT_")]
    assert not hasattr(PLATE, "_STUB_BEHIND_PLATE_MIN_MM")
    assert spec.PRESS_DIA_TEXT_PREFIX == "(<MOD-DIAM>"
    assert spec.PRESS_DIA_TEXT_SUFFIX == ")"


def test_the_plate_hole_is_the_bush_press_band() -> None:
    """MHA-PD-19's press hole takes its size and band from the bush, so the
    interference printed on both sheets is one figure."""
    assert PLATE.PRESS_HOLE_DIA == BUSH.PRESS_DIA
    assert tuple(sorted(PLATE.PRESS_HOLE_LIMITS)) == tuple(sorted(BUSH.PRESS_HOLE_BAND))


def test_the_bands_live_on_the_model_from_named_constants() -> None:
    # The reamed running bore prints the reamer's size and no band (rule 4,
    # fit audit 2026-11-23); BORE_BAND is the analysis band the stacks read.
    assert model_toleranced_dimensions(part) == {
        ("BushProfile", "HubLength"): "HUB_LENGTH_BAND",
        ("BushProfile", "BushLength"): "LENGTH_BAND",
    }
    assert "_press_dia_reference(adapter)" in Path(part.__file__).read_text(
        encoding="utf-8"
    )
    assert spec.BORE_BAND == (max(BUSH.BORE_DIA_LIMITS), min(BUSH.BORE_DIA_LIMITS))
    # Every band is narrower than the title-block row its places claim.
    for band, places in (
        (BUSH.HUB_LENGTH_BAND, BUSH.HUB_LENGTH_PLACES),
        (BUSH.LENGTH_BAND, BUSH.LENGTH_PLACES),
    ):
        assert band < _printed_tolerance.printed_band_mm(places, unit=BUSH.UNIT)


def test_every_marked_dimension_prints_with_model_places() -> None:
    """Rule 11: the turner reads both diameters, both lengths from the hub
    face and the shoulder root on A-A; rule 12: the reamed bore's Ø and
    callout on the face view, where it is a circle."""
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert (
        set(drawing.SECTION_KEEP)
        == spec.DRAWING_DIMENSIONS["BushProfile"]
        == {
            "HubDia",
            "PressDia",
            "HubLength",
            "BushLength",
            "ShoulderR",
        }
    )
    assert (
        set(drawing.FACE_KEEP) == spec.DRAWING_DIMENSIONS["BoreSketch"] == {"BoreDia"}
    )
    assert set(drawing.SECTION_KEEP) | set(drawing.FACE_KEEP) == marked
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked
    assert (
        spec.DRAWING_PRECISION_BY_NAME["ShoulderR"] == BUSH.SHOULDER_ROOT_R_PLACES == 3
    )
    for feature, callouts in spec.DIMENSION_CALLOUTS.items():
        assert set(callouts) <= spec.DRAWING_DIMENSIONS[feature], feature


def test_the_profile_is_solid_to_the_axis_and_the_bore_a_circle_cut() -> None:
    """Farm r3: a fillet feature's radius does not import into the axial
    section, so the shoulder root is a tangent arc in the turned profile and
    its radius a profile dimension like the rest; the solid gate counts the
    arc's fill (Pappus).  Farm r6: the bore is a Top-plane circle cut both
    ways through, its Ø a circle's, so it prints on the face view."""
    assert set(spec.DRAWING_DIMENSIONS) == {"BushProfile", "BoreSketch"}
    built = Path(part.__file__).read_text(encoding="utf-8")
    assert "add_fillet" not in built
    assert "adapter.add_arc(" in built
    assert 'adapter.create_sketch("Top")' in built
    assert "both_directions=True" in built
    assert part.BORE_CUT_DEPTH / 2.0 > BUSH.LENGTH
    r, press_r = BUSH.SHOULDER_ROOT_R_MAX_MM, BUSH.PRESS_DIA / 2.0
    assert part.V_ROOT == pytest.approx(
        2.0
        * math.pi
        * (press_r * r * r * (1.0 - math.pi / 4.0) + r**3 * (5.0 / 6.0 - math.pi / 4.0))
    )
    assert 0.0 < part.V_ROOT < 0.005 * part.V_BUSH
    assert part.V_TURNED - part.V_BUSH == pytest.approx(
        math.pi * (BUSH.BORE_DIA / 2.0) ** 2 * BUSH.LENGTH
    )


def test_the_drawing_reads_the_callouts_back_and_never_writes_them() -> None:
    """Text set from the drawing writes through to the built part (#1942)."""
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "SetText(" not in source
    assert "set_dimension_callouts" not in source
    built = Path(part.__file__).read_text(encoding="utf-8")
    assert "_author_dimension_callouts(adapter)" in built
    assert "_shoulder_root_max_limit(adapter)" in built


def test_each_tight_callout_names_its_mate_by_drawing_number() -> None:
    """Rule 4: the reamed bore and the press each name their mate and fit;
    the hub station and the overall length, bands with no mate to try, print
    no label; no reason is printed (it is in the necessity register); rule
    7: at most two lines of words under the process line, the bore's fit
    statement in its numbered note."""
    plate, shaft = _number("pd-transgear-arm-plate"), _number("pd-transgear-knob-shaft")
    bore = spec.BORE_CALLOUT.splitlines()
    assert bore == [
        f"REAM THRU AFTER PRESSING IN {plate}",
        f"SEE NOTE {spec.BORE_NOTE_NUMBER}",
        spec.WALL_TEXT,
    ]
    # r1: at 59 characters the block left the border; nothing is longer than
    # the process line the block's measured width was read at.
    assert max(map(len, bore)) <= drawing.BORE_BLOCK_LINE_MAX
    # The note: the mate, said to be turned to this bore (its acceptance
    # prints once, on MHA-PD-08's sheet), with no dimension and no reason.
    note = " ".join(spec.BORE_NOTE.split())
    assert (
        note == f"{spec.BORE_NOTE_NUMBER}. KNOB SHAFT {shaft} IS TURNED TO THIS BORE."
    )
    assert not any(char.isdigit() for char in note.replace(shaft, "")[2:])
    assert drawing.DRAWING_NOTES == spec.BORE_NOTE
    press = spec.PRESS_CALLOUT.splitlines()
    assert len(press) == 2
    assert press[0] == f"PRESS FIT IN {plate}"
    assert max(map(len, press)) <= 48
    assert press[1] == "TURN TO MEASURED HOLE (INTERFERENCE .0005-.0016)"
    # The ±.001 station and the ±.002 length are stack terms with no mate to
    # try: they print no label, and the register says what they protect.
    assert not hasattr(spec, "HUB_LENGTH_CALLOUT")
    assert not hasattr(spec, "LENGTH_CALLOUT")
    printed = "\n".join((spec.BORE_CALLOUT, spec.BORE_NOTE, spec.PRESS_CALLOUT))
    for word in ("KEEPS", "SETS", "HOLDS", "FASTENER", "BACKLASH"):
        assert word not in printed, word
    assert spec.DIMENSION_CALLOUTS == {
        "BoreSketch": {"BoreDia": spec.BORE_CALLOUT},
        "BushProfile": {"PressDia": spec.PRESS_CALLOUT},
    }
    # The B pre-drill is the process's, not the sheet's.
    for callouts in spec.DIMENSION_CALLOUTS.values():
        assert ".238" not in "".join(callouts.values())


def test_the_tight_lengths_fail_their_stacks_at_the_title_block_band() -> None:
    """Rule 4's necessity test, re-derived (fit audit 2026-11-23): with the
    hub station at the title block's ±.005 the collar's statistical air
    falls under its floor; with the length looser than ±.002 by more than
    .001 the cup's supplied pilot cannot set the end float."""
    import pd_cluster_air as air
    import pd_transgear_knob_cup_spec as cup

    title_block = _printed_tolerance.printed_band_mm(3, unit=BUSH.UNIT)
    assert BUSH.HUB_LENGTH_BAND < BUSH.LENGTH_BAND < title_block
    label = "MHA-PD-28 hub face station"
    terms = dict(air.COLLAR_AIR.terms)
    assert terms[label] == BUSH.HUB_LENGTH_BAND
    assert air.COLLAR_AIR.air_mm("statistical") >= air.COLLAR_AIR_MIN
    loose = air.AirStack(
        air.COLLAR_AIR.name,
        air.COLLAR_AIR.nominal_mm,
        terms | {label: title_block},
        air.COLLAR_AIR_MIN,
    )
    assert loose.air_mm("statistical") < air.COLLAR_AIR_MIN
    # What the cup's supplied pilot leaves over the stand-out's stack, of
    # which this length's band is one term.
    spare = min(cup.FACING_REMOVAL)
    assert 0.0 <= spare < title_block - BUSH.LENGTH_BAND


def _worst_walls_in() -> dict[str, float]:
    bore_r = (0.249 + 0.0005) / 2.0
    run_off = (1.143 + 0.002) * math.tan(math.radians(0.3))
    breaks = 2.0 * 0.010
    return {
        "press section over the bore": (0.4385 + 0.0005) / 2.0
        - bore_r
        - run_off
        - breaks,
        "hub over the bore": (0.52 - 0.01) / 2.0 - bore_r - run_off - breaks,
    }


def test_walls_hold_at_the_printed_worst_case() -> None:
    """Rule 17: the smallest press section (the least interference over the
    smallest reamed hole) and hub (.XX) over the
    largest reamed bore, less 0.3 deg run-off over the longest bore and the
    title-block break on both rims: press .0688 (between the floor and the
    target, stated on the sheet), hub .1043."""
    expected = _worst_walls_in()
    assert set(BUSH.WALLS) == set(expected)
    for name, worst_in in expected.items():
        assert BUSH.WALLS[name][1] == pytest.approx(_in(worst_in), abs=1e-6), name
    assert BUSH.WALLS["press section over the bore"][1] / 25.4 == pytest.approx(
        0.06875, abs=5e-5
    )
    assert BUSH.WALLS["hub over the bore"][1] >= WALL_TARGET_MM
    assert WALL_FLOOR_MM <= BUSH.WALL_WORST < WALL_TARGET_MM
    assert BUSH.WALL_FLOOR == WALL_FLOOR_MM


def test_the_short_wall_is_stated_as_a_plain_fact() -> None:
    """Rule 20: under the target, the sheet states the wall, floored so it
    never claims more than is left, with no argument words."""
    assert BUSH.WALL_STATED_MIN <= BUSH.WALL_WORST
    assert BUSH.WALL_STATED_MIN == pytest.approx(_in(0.068))
    assert spec.WALL_TEXT == "WALL .068 MIN"
    assert spec.WALL_TEXT in spec.BORE_CALLOUT
    for word in ("EXCEPTION", "ACCEPTED", "RULING", "POLICY"):
        assert word not in spec.BORE_CALLOUT


def test_the_stated_wall_is_an_owner_minor_exception() -> None:
    """Rule 20: approval lives off the sheet, as a minor exception naming the
    stated value, under the 2026-11-01 thin-wall ruling."""
    (rv03,) = [
        row
        for row in _config.parts(part.PART_NAME)["machinist_exceptions"]
        if row["id"] == "RV-03"
    ]
    assert rv03["kind"] == "minor"
    assert spec.WALL_TEXT in rv03["where"]
    assert rv03["reason"].startswith(
        "Owner ruling 2026-11-01: thin walls above the .060 floor but under the"
        " .080 target, with no geometry escape, are accepted as package-specific"
        " minor exceptions."
    )
    press_min = f"{BUSH.PRESS_DIA_MIN / 25.4:.4f}"
    bore_max = f"{(BUSH.BORE_DIA + max(BUSH.BORE_DIA_LIMITS)) / 25.4:.4f}"
    longest = f"{(BUSH.LENGTH + BUSH.LENGTH_BAND) / 25.4:.3f}"
    for fact in (press_min, bore_max, longest):
        assert fact.removeprefix("0") in rv03["reason"], fact


def _bush_geometry_fresh():
    fresh_spec = importlib.util.spec_from_file_location(
        "_bush_geometry_perturbed", BUSH.__file__
    )
    fresh = importlib.util.module_from_spec(fresh_spec)
    fresh_spec.loader.exec_module(fresh)
    return fresh


def test_the_wall_gate_refuses_a_wall_under_the_floor(monkeypatch) -> None:
    # Positive control: the title block as it is.
    assert _bush_geometry_fresh().WALL_WORST == pytest.approx(BUSH.WALL_WORST)
    # Negative control: a coarser edge break thins the press wall under .060.
    monkeypatch.setattr(_printed_tolerance, "edge_break_chamfer_mm", lambda **_: 0.5)
    with pytest.raises(AssertionError, match="floor"):
        _bush_geometry_fresh()


def test_the_shoulder_seats_past_the_plate_hole_mouth() -> None:
    """The root's R.005 MAX sits inside the plate mouth's smallest .015 x 45°
    leg, so the shoulder lands on face A; the flat land left is
    informational."""
    assert BUSH.SHOULDER_ROOT_R_MAX_MM == pytest.approx(_in(0.005))
    assert BUSH.PRESS_HOLE_MOUTH_CHAMFER == pytest.approx(_in(0.015))
    assert BUSH.PRESS_HOLE_MOUTH_CHAMFER_MIN == pytest.approx(_in(0.010))
    assert BUSH.PRESS_HOLE_MOUTH_CHAMFER_MAX == pytest.approx(_in(0.020))
    assert BUSH.PRESS_HOLE_MOUTH_CHAMFER_MIN >= BUSH.SHOULDER_ROOT_R_MAX_MM
    land_in = (0.51 - 0.4390) / 2.0 - 0.020 - 0.010
    assert BUSH.SHOULDER_LAND_WORST == pytest.approx(_in(land_in), abs=1e-6)
    assert BUSH.SHOULDER_LAND_WORST > 0.0
    assert spec.SHOULDER_ROOT_SUFFIX == " MAX"


def test_the_shoulder_is_the_one_datum_and_the_bore_frame() -> None:
    """A is the shoulder face that seats on MHA-PD-19's face A; the bore
    carries ⊥ Ø.002 A, no projected zone (rule 26), and no datum of its own,
    since no frame references one (rule 5)."""
    datums = {datum.letter: datum.face for datum in spec.PART_DATUMS}
    assert datums == {"A": PlanarFace((0.0, 1.0, 0.0), BUSH.HUB_LENGTH)}
    referenced = {
        letter for control in spec.GEOMETRIC_CONTROLS for letter in control.datums
    }
    assert referenced == set(datums)
    (control,) = spec.GEOMETRIC_CONTROLS
    assert control.key == "bore_perpendicularity"
    assert control.characteristic == "perpendicularity"
    assert control.tolerance == ".002"
    assert control.tolerance_zone == "diametral"
    assert control.datums == ("A",)
    assert control.face == CylinderFace(BUSH.BORE_DIA)
    assert control.projected_zone_height_mm is None
    # No tighter than the shop row: .001 per inch over the bore, never under .001.
    assert (
        spec.GEOMETRIC_TOLERANCES_MM["bore_perpendicularity"]
        >= spec.SHOP_PERPENDICULARITY_MM
    )


def test_the_bore_frame_holds_k_inside_the_reducer_axis_zone() -> None:
    """RV-02's arithmetic, moved with the bore from the plate: Ø.002 over
    the shortest bore, carried to K's projected height, inside the zone the
    air stacks charge."""
    zone = (
        _in(0.002) * REGISTRATION.K_PROJECTED_HEIGHT_MM / BUSH.KNOB_BORE_LENGTH_MIN_MM
    )
    assert spec.BORE_AXIS_ZONE_AT_PROJECTED_HEIGHT_MM == pytest.approx(zone)
    assert zone <= REGISTRATION.AXIS_PROJECTED_ZONE_DIAMETER_MM
    (rv02,) = [
        row
        for row in _config.parts(part.PART_NAME)["machinist_exceptions"]
        if row["id"] == "RV-02"
    ]
    assert "datum A (shoulder face)" in rv02["where"]
    reason = rv02["reason"]
    assert f"({BUSH.KNOB_BORE_LENGTH_MIN_MM:.2f} mm)" in reason
    assert f"{zone:.4f} mm" in reason
    assert f"({REGISTRATION.K_PROJECTED_HEIGHT_MM:.2f} mm" in reason
    assert f"{REGISTRATION.AXIS_PROJECTED_ZONE_DIAMETER_MM:.4f} mm zone" in reason
    assert "owner ruling 2026-11-20 (Pedro), #2425" in reason
    assert (
        "Variant of C ; I noticed there was a missing screw and an extra pin" in reason
    )


def test_the_frame_lives_on_the_bush_not_the_plate() -> None:
    plate_rows = _config.parts("pd-transgear-arm-plate").get("machinist_exceptions", ())
    assert not any("perpendicularity" in row["where"] for row in plate_rows)


def test_running_and_thrust_faces_carry_their_finish() -> None:
    """Rule 6: the bore runs on the journal; the hub and rear faces are the
    thrust ring's and the cup's thrust faces, captioned with their mates."""
    finishes = {control.key: control for control in spec.SURFACE_FINISHES}
    assert set(finishes) == {"bore", "hub_face", "rear_face"}
    assert all(control.roughness_um == MACHINED_UM for control in finishes.values())
    assert finishes["bore"].face == CylinderFace(BUSH.BORE_DIA)
    assert finishes["hub_face"].face == PlanarFace((0.0, -1.0, 0.0), 0.0)
    assert finishes["rear_face"].face == PlanarFace((0.0, 1.0, 0.0), BUSH.LENGTH)
    assert spec.FINISH_CAPTIONS == {
        "hub_face": f"THRUST FACE,\nRING {_number('pd-transgear-knob-thrust-ring')}",
        "rear_face": f"THRUST FACE,\nCUP {_number('pd-transgear-knob-cup')}",
    }
    assert set(drawing.FACE_FINISHES) == set(spec.FINISH_CAPTIONS)


def test_the_section_cuts_the_bush_axis_hub_face_left() -> None:
    (x0, y0), (x1, y1) = drawing.SECTION_LINE
    assert x0 == x1 == drawing.FACE_CENTER[0]
    assert y0 < drawing.FACE_CENTER[1] - drawing.HALF_HUB
    assert y1 > drawing.FACE_CENTER[1] + drawing.HALF_HUB
    assert abs(math.remainder(drawing.FACE_VIEW_ANGLE, math.pi)) == pytest.approx(
        math.pi / 2.0
    )
    assert drawing.HUB_FACE_X < drawing.SHOULDER_X < drawing.REAR_FACE_X
    assert drawing.REAR_FACE_X - drawing.HUB_FACE_X == pytest.approx(
        BUSH.LENGTH * drawing._S / 1000.0
    )
    assert drawing.SHOULDER_X - drawing.HUB_FACE_X == pytest.approx(
        BUSH.HUB_LENGTH * drawing._S / 1000.0
    )


def _bore_landing(toward: tuple[float, float]) -> tuple[float, float]:
    """The face view's bore circle point facing ``toward`` (the drawing's
    ``_bore_landing``, with the view centred on FACE_CENTER)."""
    cx, cy = drawing.FACE_CENTER
    dx, dy = toward[0] - cx, toward[1] - cy
    scale = drawing.HALF_BORE / math.hypot(dx, dy)
    return cx + dx * scale, cy + dy * scale


def _finish_ink(symbol: tuple[float, float]) -> dict[str, tuple[float, ...]]:
    """A surface finish's leader start, symbol box and text box (sheet m),
    from the drawing's r6-measured offsets."""
    left, bottom, right, top = drawing.FINISH_TEXT_BOX_M
    x, y = symbol
    return {
        "leader_start": (x + drawing.FINISH_LEADER_DX_M, y),
        "symbol": (x - 0.002, y, x + right, y + drawing.FINISH_SYMBOL_HEIGHT_M),
        "text": (x + left, y + bottom, x + right, y + top),
    }


def _caption_box(xy: tuple[float, float]) -> tuple[float, float, float, float]:
    width, height = drawing.CAPTION_SIZE_M
    return (xy[0], xy[1] - height, xy[0] + width, xy[1])


def _segment_y_at(start, end, x: float) -> float:
    return start[1] + (end[1] - start[1]) * (x - start[0]) / (end[0] - start[0])


def test_the_face_view_leaders_stay_left_of_the_cutting_line() -> None:
    """Farm r5: the bore finish's leader ran through the lower letter A and
    the frame's crossed the cutting line; r6: the finish's leader rose
    through its own text and its text sat on the press circle.  The line runs
    vertically through the bore's centre with its arrows and letters on the
    right, so the frame, the finish and the Ø's leader all land left of it."""
    line_x = drawing.SECTION_LINE[0][0]
    line_bottom, line_top = drawing.SECTION_LINE[0][1], drawing.SECTION_LINE[1][1]
    cx, cy = drawing.FACE_CENTER
    clearance = 0.003
    # The frame below the view at the note column, its right end short of
    # the line, clear under the line's foot; its leader rises to the bore.
    frame_left, frame_top = drawing.FRAME_XY
    assert frame_left >= 0.016
    assert frame_left + drawing.FRAME_WIDTH_M < line_x - clearance
    assert frame_top < line_bottom - 0.005
    frame_landing = _bore_landing(drawing.FRAME_LANDING_TOWARD)
    assert frame_landing[0] < line_x - clearance
    assert frame_top < frame_landing[1] < cy
    # The finish left of the hub circle, its text clear of it; its leader
    # falls onto the bore and passes under its own text.
    ink = _finish_ink(drawing.BORE_FINISH_XY)
    text_left, text_bottom, text_right, _top = ink["text"]
    hub_r = drawing.HALF_HUB
    assert text_right < cx - math.sqrt(hub_r**2 - min(hub_r, text_bottom - cy) ** 2)
    assert ink["symbol"][1] > cy + 0.005  # above the horizontal centre line
    finish_landing = _bore_landing(drawing.BORE_FINISH_XY)
    assert finish_landing[0] < line_x - clearance
    start = ink["leader_start"]
    assert finish_landing[1] <= start[1]
    assert _segment_y_at(start, finish_landing, text_right) < text_bottom
    # The bore Ø's block centred right of the bore's centre, so its leader
    # leaves the shelf's left end, radially onto the bore's upper left; the
    # shelf clears the line's top letter and the leader the finish symbol.
    keep_x, keep_y = drawing.FACE_KEEP["BoreDia"]
    width, height = drawing.BORE_BLOCK_SIZE_M
    shelf = (keep_x - width / 2.0, keep_y - height / 2.0)
    assert keep_x > cx + 0.010
    assert shelf[0] >= 0.016
    assert shelf[1] > line_top + 0.008
    dia_landing = _bore_landing(shelf)
    assert dia_landing[0] < line_x - clearance
    symbol_right, symbol_top = ink["symbol"][2], ink["symbol"][3]
    assert _segment_y_at(shelf, dia_landing, symbol_right) > symbol_top + 0.003
    # Every landing is on the bore, not the hub outline round it.
    for landing in (frame_landing, finish_landing, dia_landing):
        assert math.dist(landing, drawing.FACE_CENTER) == pytest.approx(
            drawing.HALF_BORE
        )


def test_the_section_texts_stay_inside_their_own_extension_lines() -> None:
    """Farm r6: the bore's dimension line ran out across the hub Ø's
    extension line.  Each diameter's text now sits between its own lines,
    the hub's left of the hub face and the press's right of the rear face
    beyond the rear face's finish; both lengths above the part."""
    keep = drawing.SECTION_KEEP
    assert "BoreDia" not in keep
    assert keep["HubDia"][0] < drawing.HUB_FACE_X
    assert keep["HubDia"][1] == keep["PressDia"][1] == drawing.SECTION_CENTER[1]
    assert keep["PressDia"][0] > drawing.REAR_FACE_X
    top = drawing.SECTION_CENTER[1] + drawing.HALF_HUB
    assert top < keep["HubLength"][1] < keep["BushLength"][1]


def test_the_thrust_face_finishes_stay_clear_of_lines_and_captions() -> None:
    """Farm r6: both captions overlapped their symbols, the leaders crossed
    the captions and the hub Ø's extension line, the lengths' extension
    lines struck both.  Each symbol now stands inside its end's diameter's
    extension lines, above its pick so the leader falls to the face away from
    its own ink, its caption over it with 1.27 mm of air; nothing reaches
    the hub face's line (the lengths' extension lines), the hub Ø's text or
    the press Ø's block."""
    centre_y = drawing.SECTION_CENTER[1]
    keep = drawing.SECTION_KEEP
    press_block_left = keep["PressDia"][0] - 0.0605  # r6: 120.5 mm wide, centred
    hub_text_right = keep["HubDia"][0] + 0.006
    for key, half, outboard in (
        ("hub_face", drawing.HALF_HUB, -1.0),
        ("rear_face", drawing.HALF_PRESS, 1.0),
    ):
        pick, symbol, caption = drawing.FACE_FINISHES[key]
        ink = _finish_ink(symbol)
        start = ink["leader_start"]
        assert pick[1] < symbol[1], key  # the leader falls to the face
        assert outboard * (start[0] - pick[0]) > 0.002, key
        assert outboard * (ink["symbol"][0 if outboard > 0 else 2] - pick[0]) > 0, key
        box = _caption_box(caption)
        for low, high in ((ink["symbol"][1], ink["symbol"][3]), (box[1], box[3])):
            assert centre_y - half + 0.002 < low < high < centre_y + half - 0.002, key
        assert box[1] - ink["symbol"][3] >= 0.00127, key
        if outboard < 0:
            assert hub_text_right + 0.003 < box[0] < box[2] < pick[0] - 0.005
            assert ink["symbol"][2] < pick[0] - 0.003
        else:
            assert pick[0] + 0.003 < box[0] < box[2] < press_block_left - 0.003
            assert ink["symbol"][2] < press_block_left - 0.003
            # The leftward leader passes under the symbol's own baseline.
            assert _segment_y_at(start, pick, symbol[0]) < symbol[1] - 0.001


def test_the_section_caption_drops_only_its_scale_row() -> None:
    """Machinist review r10: "SCALE 3 : 1" under SECTION A-A repeated the
    sheet's scale (rule 9)."""
    label = "SECTION <VLNAME>-<VLLABEL>"
    assert drawing.caption_without_scale(f"{label}\r\nSCALE <VLSCALEV>") == label
    for fields in (label, "<VLNAME>\nSCALE <VLSCALEV>", f"{label}\nA\nSCALE <VLSCALE>"):
        with pytest.raises(RuntimeError, match="not separable"):
            drawing.caption_without_scale(fields)


def test_the_press_block_is_taller_than_inside_arrows_leave() -> None:
    """Farm r10: the press Ø's lower inside arrow ran through the "(" of its
    last callout row; the build stands the arrows outside."""
    between = 2.0 * drawing.HALF_PRESS
    shafts = 0.0066 + 0.0072  # read off r10
    block = 0.0222  # stacked limits over the two callout rows, r10
    assert len(spec.PRESS_CALLOUT.splitlines()) == 2
    assert block > between - shafts
    assert block < between - 0.004


def test_datum_a_rides_the_shoulder_line_below_the_hub() -> None:
    """Farm r6: datum A landed on a neighbour of the 3 mm shoulder line and
    its leader crossed the hub Ø's extension line.  The tag stands left of
    the shoulder's line below the hub, so its square leader meets the line's
    extension under the lower extension line, clear of the section caption
    under it."""
    x, y = drawing.DATUM_A_XY
    hub_bottom = drawing.SECTION_CENTER[1] - drawing.HALF_HUB
    assert x < drawing.SHOULDER_X - 0.006
    assert drawing.CAPTION_XY[1] + 0.010 < y < hub_bottom - 0.006


def test_the_root_radius_text_stands_on_its_arc_centre_side() -> None:
    """Farm r9: the radius' leader runs through the arc's centre, outside the
    part above and right of the upper root; with its text below the part it
    crossed both walls and the bore.  The 24.8 mm text now stands right of
    the rear face's extension line and over the press Ø's upper one, left of
    the press Ø's block, so the leader rises from the root over the press Ø."""
    x, y = drawing.SECTION_KEEP["ShoulderR"]
    half_text = 0.0124
    press_top = drawing.SECTION_CENTER[1] + drawing.HALF_PRESS
    root = (drawing.SHOULDER_X, press_top)
    shelf = (x - half_text - 0.003, y - 0.002)
    assert shelf[0] > drawing.REAR_FACE_X + 0.0015
    assert y - 0.002 > press_top + 0.005
    assert y + 0.002 < drawing.SECTION_KEEP["HubLength"][1] - 0.008
    assert x + half_text < drawing.SECTION_KEEP["PressDia"][0] - 0.0605 - 0.010
    # Over the press Ø all the way: the leader only rises from the root.
    assert shelf[1] > root[1] + 0.004


def test_the_isometric_clears_the_title_block_and_the_section() -> None:
    """Farm r6: lower right the isometric ran 8 mm into the title block
    ([216.0, 0.0]..[431.8, 66.0] mm, the audit's keep-out)."""
    (cx, cy), (width, height) = drawing.ISO_CENTER, drawing.ISO_SIZE_M
    left, bottom, right, top = (
        cx - width / 2.0,
        cy - height / 2.0,
        cx + width / 2.0,
        cy + height / 2.0,
    )
    assert right < 0.216 or top < 0.066
    assert left > 0.0127 + 0.003 and bottom > 0.0127 + 0.003  # the border
    assert top < drawing.SECTION_CENTER[1] - drawing.HALF_HUB - 0.010
    assert top < drawing.FRAME_XY[1] - drawing.FRAME_HEIGHT_M - 0.010
    assert right < drawing.CAPTION_XY[0] - 0.030  # the SECTION caption


def test_the_bore_note_stands_in_the_open_sheet_over_the_title_block() -> None:
    """The numbered note (top-left at its xy, about 2.85 mm a character and
    4.5 mm a line): right of the SECTION caption, under the press Ø's lower
    arrow (r1: 0.148), above the title block and left of the right border."""
    x, y = drawing.BORE_NOTE_XY
    lines = spec.BORE_NOTE.splitlines()
    assert max(map(len, lines)) <= spec.BORE_NOTE_WIDTH
    assert len(lines) <= 4  # rule 7
    right = x + max(map(len, lines)) * 0.00285
    bottom = y - len(lines) * 0.0045
    assert x > drawing.CAPTION_XY[0] + 0.040
    assert right < 0.4318 - 0.0127 - 0.003
    assert y < 0.148 - 0.010
    assert bottom > 0.066 + 0.005


def test_registry_row_is_the_turned_steel_mha_pd_28() -> None:
    row = _config.parts(part.PART_NAME)
    assert row["title"] == "Transgear Knob Bush"
    assert row["number"] == "MHA-PD-28"
    assert row["material"] == "AISI 1018 cold-finished steel"
    assert "5/8" in row["material_specification"]
    assert row["finish"] == _config.parts("pd-transgear-arm-plate")["finish"]
    assert int(row["quantity"]) == 1
    assert row["tolerance_class"] == "machined_block"
    assert row["drawing_unit"] == "in"
    process = " ".join(row["process"].split())
    for phrase in (".238 (letter B)", ".0005 feeler", "ream the bore .249 through"):
        assert phrase in process, phrase


def test_the_bush_is_cut_from_the_bought_five_eighths_bar() -> None:
    plan = tomllib.loads(
        (CAD_ROOT / "process" / "pd_transgear_knob_bush" / "plan.toml").read_text(
            encoding="utf-8"
        )
    )
    assert (plan["part"], plan["revision"]) == (
        "{{cad.drawing_number}}",
        "{{cad.revision}}",
    )
    assert plan["stock_refs"] == ["1018-round-5-8"]
    # The B drill only: MHA-PD-00 step 11 reams the bore after pressing.
    refs = {tool["ref"] for tool in plan["tools"]}
    assert "drill-b" in refs and "reamer-2490" not in refs
    bar = _shop_equipment.load()["stock"]["1018-round-5-8"]
    assert "MHA-PD-28 pd-transgear-knob-bush" in bar["note"]
    assert bar["dia_in"] == [0.625]
    assert part.V_BUSH == pytest.approx(
        math.pi
        * (
            (BUSH.HUB_DIA / 2.0) ** 2 * BUSH.HUB_LENGTH
            + (BUSH.PRESS_DIA / 2.0) ** 2 * BUSH.STUB_LENGTH
            - (BUSH.BORE_DIA / 2.0) ** 2 * BUSH.LENGTH
        )
    )


def test_the_pin_check_holds_the_bore_square_to_the_shoulder() -> None:
    params = tomllib.loads(
        (CAD_ROOT / "process" / "pd_transgear_knob_bush" / "plan.toml").read_text(
            encoding="utf-8"
        )
    )["parameters"]
    zone = float(spec.GEOMETRIC_TOLERANCES_IN["bore_perpendicularity"])
    bore = (BUSH.LENGTH + BUSH.LENGTH_BAND) / 25.4
    # The pin can lie tilted by its fit over its depth in the hole; the
    # tilt is read in two planes, and a difference across the turn is twice
    # the pin's offset from the spindle axis.
    tilt = zone / bore - params["pin_fit_max_in"] / params["pin_depth_in"]
    spacing = params["pin_far_in"] - params["pin_near_in"]
    limit_mm = 2.0 * tilt / math.sqrt(2.0) * spacing * 25.4
    assert 0.0 < params["pin_tilt_reading_max_mm"] <= limit_mm
    # A drill run off by the wall stack's budget reads well over the limit.
    run_off = math.tan(math.radians(BUSH.DRILL_RUN_OFF_DEG))
    assert 2.0 * run_off * spacing * 25.4 > 3.0 * limit_mm


def test_the_pilot_reading_guarantees_the_printed_interference() -> None:
    """Codjiflo #3486: the pilot stands in for MHA-PD-19's hole, so the slip
    it may have comes off the interference.  The hole lies between the last
    two pilot readings, at most pilot_step_max_in apart, so the press
    diameter is accepted from PILOT plus the sheet's least interference
    plus that step, up to PILOT plus the greatest interference."""
    plan = tomllib.loads(
        (CAD_ROOT / "process" / "pd_transgear_knob_bush" / "plan.toml").read_text(
            encoding="utf-8"
        )
    )
    params = plan["parameters"]
    least, greatest = (value / 25.4 for value in BUSH.PRESS_INTERFERENCE)
    step = params["pilot_step_max_in"]
    over_min = params["press_over_pilot_min_in"]
    assert over_min == pytest.approx(least + step, abs=1e-9)
    # Worst cases against the hole itself: PILOT <= hole < PILOT + step.
    assert over_min - step >= least - 1e-9
    # The window left to aim at is still wider than the micrometer's .0001.
    assert greatest - over_min >= 0.0008
    # The pilot starts over the largest hole the reamer is modelled to cut.
    hole_max = (BUSH.PRESS_DIA + max(BUSH.PRESS_HOLE_BAND)) / 25.4
    assert params["pilot_rough_dia_in"] >= hole_max + 0.0005
    # The pilot is faced off in its own setup, so it adds nothing to the
    # main setup's stick-out, which stays inside three press diameters.
    stickout = (
        BUSH.LENGTH / 25.4
        + params["regrip_allowance_in"]
        + params["part_kerf_in"]
        + params["jaw_clearance_in"]
        + params["face_allowance_in"]
    )
    assert stickout <= 3.0 * BUSH.PRESS_DIA_MIN / 25.4
    text = " ".join(
        op["instruction"] for setup in plan["setups"] for op in setup["operations"]
    )
    assert "The pilot stays" not in text and "PILOT plus .0005" not in text
