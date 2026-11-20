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
    """#2425: hub Ø.52 x .809 to the shoulder, press Ø.4375 on to the rear
    face, 1.143 overall, bore .249 reamed after a .238 (B) drill."""
    assert BUSH.HUB_DIA == pytest.approx(_in(0.52))
    assert BUSH.HUB_LENGTH == pytest.approx(_in(0.809))
    assert BUSH.HUB_LENGTH_BAND == FIT_LENGTH_BAND_IN
    assert BUSH.SHOULDER_SEAT_GAP_MAX == pytest.approx(_in(0.0005))
    assert BUSH.LENGTH == pytest.approx(_in(1.143))
    assert BUSH.LENGTH_BAND == pytest.approx(_in(0.002))
    assert BUSH.STUB_LENGTH == pytest.approx(_in(0.334))
    assert BUSH.PRESS_DIA == pytest.approx(_in(0.4375))
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


def test_the_fn2_press_limits_and_interference() -> None:
    """ANSI B4.1 FN2, 0.40-0.56 in: hole +.0007/0, shaft +.0016/+.0012,
    interference .0005-.0016; the bush prints .4387/.4391."""
    press = tuple(BUSH.PRESS_DIA + deviation for deviation in BUSH.PRESS_DIA_BAND)
    assert press == pytest.approx((_in(0.4391), _in(0.4387)))
    hole = tuple(BUSH.PRESS_DIA + deviation for deviation in BUSH.PRESS_HOLE_BAND)
    assert hole == pytest.approx((_in(0.4382), _in(0.4375)))
    assert BUSH.PRESS_INTERFERENCE == pytest.approx((_in(0.0005), _in(0.0016)))
    assert min(press) - max(hole) == pytest.approx(BUSH.PRESS_INTERFERENCE[0])
    assert max(press) - min(hole) == pytest.approx(BUSH.PRESS_INTERFERENCE[1])


def test_the_plate_hole_is_the_bush_press_band() -> None:
    """MHA-PD-19's press hole takes its size and band from the bush, so the
    interference printed on both sheets is one figure."""
    assert PLATE.PRESS_HOLE_DIA == BUSH.PRESS_DIA
    assert tuple(sorted(PLATE.PRESS_HOLE_LIMITS)) == tuple(sorted(BUSH.PRESS_HOLE_BAND))


def test_the_bands_live_on_the_model_from_named_constants() -> None:
    assert model_toleranced_dimensions(part) == {
        ("BushProfile", "BoreDia"): "*deviations(BORE_BAND)",
        ("BushProfile", "PressDia"): "*deviations(PRESS_DIA_BAND)",
        ("BushProfile", "HubLength"): "HUB_LENGTH_BAND",
        ("BushProfile", "BushLength"): "LENGTH_BAND",
    }
    assert spec.BORE_BAND == (max(BUSH.BORE_DIA_LIMITS), min(BUSH.BORE_DIA_LIMITS))
    # Every band is narrower than the title-block row its places claim.
    for band, places in (
        (BUSH.HUB_LENGTH_BAND, BUSH.HUB_LENGTH_PLACES),
        (BUSH.LENGTH_BAND, BUSH.LENGTH_PLACES),
    ):
        assert band < _printed_tolerance.printed_band_mm(places, unit=BUSH.UNIT)


def test_every_marked_dimension_prints_on_the_section_with_model_places() -> None:
    """Rule 11: the turner reads both diameters, the bore, both lengths from
    the hub face and the shoulder root on A-A."""
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert (
        set(drawing.SECTION_KEEP)
        == marked
        == {
            "HubDia",
            "PressDia",
            "BoreDia",
            "HubLength",
            "BushLength",
            "ShoulderR",
        }
    )
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked
    assert (
        spec.DRAWING_PRECISION_BY_NAME["ShoulderR"] == BUSH.SHOULDER_ROOT_R_PLACES == 3
    )
    for feature, callouts in spec.DIMENSION_CALLOUTS.items():
        assert set(callouts) <= spec.DRAWING_DIMENSIONS[feature], feature


def test_the_drawing_reads_the_callouts_back_and_never_writes_them() -> None:
    """Text set from the drawing writes through to the built part (#1942)."""
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "SetText(" not in source
    assert "set_dimension_callouts" not in source
    built = Path(part.__file__).read_text(encoding="utf-8")
    assert "_author_dimension_callouts(adapter)" in built
    assert "_shoulder_root_max_limit(adapter)" in built


def test_each_tight_callout_names_its_mate_by_drawing_number() -> None:
    """Rule 4: the reamed bore, the press, the hub station and the overall
    length each name what they fit or set; rule 7: at most two lines of
    words under the process line."""
    plate, shaft = _number("pd-transgear-arm-plate"), _number("pd-transgear-knob-shaft")
    bore = spec.BORE_CALLOUT.splitlines()
    assert bore[0] == f"REAM THRU AFTER PRESSING IN {plate}"
    assert bore[1] == f"RUNNING FIT ON KNOB SHAFT {shaft}"
    assert bore[2] == spec.WALL_TEXT
    press = spec.PRESS_CALLOUT.splitlines()
    assert len(press) == 2
    assert press[0] == f"PRESS FIT IN {plate}"
    assert press[1] == "TURN TO MEASURED HOLE (INTERFERENCE .0005-.0016)"
    assert spec.HUB_LENGTH_CALLOUT == (
        f"SETS {shaft}\nAND {_number('pd-transgear-removable')}"
    )
    # The ±.002 bounds the journal's stand-out, which the cup's supplied
    # pilot absorbs by facing at fit-up.
    assert spec.LENGTH_CALLOUT == (
        f"SETS FACING RANGE\nOF CUP {_number('pd-transgear-knob-cup')}"
    )
    assert spec.DIMENSION_CALLOUTS == {
        "BushProfile": {
            "BoreDia": spec.BORE_CALLOUT,
            "PressDia": spec.PRESS_CALLOUT,
            "HubLength": spec.HUB_LENGTH_CALLOUT,
            "BushLength": spec.LENGTH_CALLOUT,
        },
    }
    # The B pre-drill is the process's, not the sheet's.
    assert ".238" not in "".join(spec.DIMENSION_CALLOUTS["BushProfile"].values())


def _worst_walls_in() -> dict[str, float]:
    bore_r = (0.249 + 0.0005) / 2.0
    run_off = (1.143 + 0.002) * math.tan(math.radians(0.3))
    breaks = 2.0 * 0.010
    return {
        "press section over the bore": (0.4375 + 0.0012) / 2.0
        - bore_r
        - run_off
        - breaks,
        "hub over the bore": (0.52 - 0.01) / 2.0 - bore_r - run_off - breaks,
    }


def test_walls_hold_at_the_printed_worst_case() -> None:
    """Rule 17: the smallest press (FN2 lower limit) and hub (.XX) over the
    largest reamed bore, less 0.3 deg run-off over the longest bore and the
    title-block break on both rims: press .0686 (between the floor and the
    target, stated on the sheet), hub .1043."""
    expected = _worst_walls_in()
    assert set(BUSH.WALLS) == set(expected)
    for name, worst_in in expected.items():
        assert BUSH.WALLS[name][1] == pytest.approx(_in(worst_in), abs=1e-6), name
    assert BUSH.WALLS["press section over the bore"][1] / 25.4 == pytest.approx(
        0.0686, abs=5e-5
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
    press_min = f"{(BUSH.PRESS_DIA + BUSH.PRESS_DIA_BAND[1]) / 25.4:.4f}"
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
    land_in = (0.51 - 0.4382) / 2.0 - 0.020 - 0.010
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


def test_the_diameters_stand_off_the_part_without_crossing() -> None:
    """Left of the hub face the bore's dimension line stands nearer the part
    than the hub's, so the hub's extension lines pass outside it; the press
    Ø stands right of the rear face; both lengths above the part."""
    keep = drawing.SECTION_KEEP
    assert keep["HubDia"][0] < keep["BoreDia"][0] < drawing.HUB_FACE_X
    assert keep["PressDia"][0] > drawing.REAR_FACE_X
    top = drawing.SECTION_CENTER[1] + drawing.HALF_HUB
    assert top < keep["HubLength"][1] < keep["BushLength"][1]
    assert keep["BoreDia"][1] < drawing.SECTION_CENTER[1] - drawing.HALF_HUB


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
    assert plan["revision"] == "placeholder"
    assert plan["part"] == "MHA-PD-28 Transgear Knob Bush"
    assert plan["stock_refs"] == ["1018-round-5-8"]
    assert {tool["ref"] for tool in plan["tools"]} >= {"drill-b", "reamer-2490"}
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
