"""Offline contracts for the cylinder gears' cam turning fixture (MHA-DT-12-TL-01)."""

from __future__ import annotations

import math

import pytest

import _buildgraph as bg
import _config
import build_dt_cylinder_gear_tl_cam_fixture as part
import draw_dt_cylinder_gear_tl_cam_fixture as drawing
import dt_cylinder_gear_phase_band as phase_band
import dt_cylinder_gear_spec as gear
import dt_cylinder_gear_tl_cam_fixture_spec as spec
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
import _shop_equipment
from _drawing_types import DrawingLayout
from _inch_wall_limits import WALL_TARGET_MM

INCH = 25.4
KIT = "dt_cylinder_gear_tl_cam_turning"


def test_each_press_ream_has_a_reamer_to_buy_that_cuts_inside_its_band() -> None:
    tools = _shop_equipment.load()["tools"]
    for key, (dia, (lower, upper)) in {
        "reamer-3740": (spec.STUB_HOLE_DIA, spec.STUB_HOLE_DEVIATIONS),
        "reamer-0365": (spec.PIN_HOLE_DIA, spec.PIN_HOLE_DEVIATIONS),
    }.items():
        record = tools[key]
        assert record["status"] == "to_order"
        assert "read live 2026-11-14" in record["purchase"]
        low, high = record["dia_in"]
        assert (dia + lower) / INCH - 1e-9 <= low < high <= (dia + upper) / INCH + 1e-9


def test_registry_row_is_tooling_in_inch() -> None:
    row = _config.parts(spec.PART_NAME)
    assert row["number"] == spec.PART_NUMBER == "MHA-DT-12-TL-01"
    assert row["drawing_unit"] == "in"
    assert int(row["quantity"]) == 1
    entry = DRAWINGS_BY_NAME["dt_cylinder_gear_tl_cam_fixture"]
    assert entry.artifact_stem == spec.PART_NAME == part.PART_NAME
    assert entry.layout is DrawingLayout.LANDSCAPE
    assert entry.source_kind == "part"
    assert drawing.SPEC is entry


def test_the_throw_is_set_on_the_stub_and_held_to_the_gears_print() -> None:
    # The stub's printed station is the gear's printed throw on the .0001 grid.
    assert spec.STUB_OFFSET == pytest.approx(round(gear.ECCENTRICITY / INCH, 4) * INCH)
    assert abs(spec.STUB_OFFSET - gear.ECCENTRICITY) < 0.0001 * INCH
    # The jaws set the stub against the gauge-block stack, so the station's
    # +/-.002 is not in the throw: half the gap's error and the bore's float
    # are, worst case, inside MHA-DT-12's absolute +/-.0020 (owner ruling
    # 2026-11-08).
    assert spec.THROW_PER_PART_MAX_MM == spec.BORE_FLOAT
    assert spec.THROW_ERROR_MAX_MM == pytest.approx(
        spec.THROW_SET_MAX_MM + spec.THROW_PER_PART_MAX_MM
    )
    assert spec.THROW_ERROR_MAX_MM <= gear.ECCENTRICITY_TOLERANCE_MM
    assert spec.POSITION_BAND > gear.ECCENTRICITY_TOLERANCE_MM - spec.BORE_FLOAT
    for nominal in (gear.ECCENTRICITY, spec.STUB_OFFSET):
        error = abs(spec.THROW_STACK / 2.0 - nominal) + spec.THROW_GAP_ERROR_MAX / 2.0
        assert error + spec.BORE_FLOAT <= gear.ECCENTRICITY_TOLERANCE_MM
    for name in (
        "THROW_FIXED_MAX_MM",
        "FIRST_CAM_CHECK_TEXT",
        "STUB_RUNOUT_TEXT",
        "THROW_TIR_TEXT",
    ):
        assert not hasattr(spec, name), name


def test_the_stations_are_cut_to_the_shop_row_and_no_tighter() -> None:
    # One tool made once: the shop table's +/-.002 for a reamed hole from its
    # datum, the narrowest band cut to a number.
    assert spec.POSITION_BAND == pytest.approx(0.002 * INCH)
    for name in ("StubOffset", "PinX", "PinY"):
        feature = next(f for f, n in spec.DRAWING_DIMENSIONS.items() if name in n)
        assert spec.MODEL_BANDS_MM[(feature, name)] == spec.POSITION_DEVIATIONS


def test_the_clock_pin_stands_at_the_notch_phase() -> None:
    # Every gear turns clockwise onto the pin, so its notched space seats one
    # half-play clockwise of the pin: the pin stands that far counter-clockwise.
    assert spec.SEATED_SIDE == -1.0 and spec.CUT_TURNS_GEAR_CLOCKWISE
    assert spec.SEATED_HALF_PLAY_DEG > 0.0
    assert spec.PIN_PHASE_DEG - spec.SEATED_HALF_PLAY_DEG == pytest.approx(
        phase_band.CAM_NOTCH_PHASE_DEG, abs=0.01
    )
    # Counter-clockwise of the throw line seen from the tailstock (-X).
    assert spec.PIN_X < 0.0 < spec.PIN_Y
    # It enters the space of every corner gear for both pin limits at its
    # nominal radius and at the nearest radius the stations and the bore's
    # float allow, and never so tight it binds.
    for radius in (spec.PIN_RADIUS, spec.PIN_RADIUS - spec._RADIAL_SPREAD):
        for profile in spec.PROFILES:
            for dia in (spec.PIN_DIA_MIN, spec.PIN_DIA_MAX):
                play = spec.pin_half_play_rad(profile, radius, dia)
                assert play is not None and play > 0.0


def test_phase_holds_the_widened_print_and_the_budgets_scatter() -> None:
    # Per gear: the bore's float and tooth form, inside the error budget's
    # per-channel cam_phase (gear to gear).
    assert spec.PHASE_SCATTER_TOLERANCE_DEG == gear.CAM_PHASE_TOLERANCE_DEG == 0.25
    assert 0.0 < spec.PHASE_PER_PART_WORST_DEG <= spec.PHASE_SCATTER_TOLERANCE_DEG
    # Fixed: the hole stations, the register and the jaw pair's line, common
    # to all 20 gears. The total sits inside MHA-DT-12's printed band, widened
    # to +/-.7 deg for it (delegated ruling 2026-11-17, #2361); a reading on
    # the fixture would move the phase .17 deg per .001 read, too coarse to
    # set it.
    assert spec.PHASE_TOLERANCE_DEG == phase_band.NOTCH_PHASE_TOLERANCE_DEG == 0.7
    assert spec.PHASE_FIXED_WORST_DEG == pytest.approx(0.469, abs=0.001)
    assert spec.PHASE_TOTAL_WORST_DEG == pytest.approx(0.684, abs=0.001)
    assert spec.PHASE_TOTAL_WORST_DEG <= spec.PHASE_TOLERANCE_DEG
    assert spec.PHASE_PER_THOU_READING_DEG == pytest.approx(0.168, abs=0.001)


def test_every_gear_seats_on_one_flank_so_the_play_is_not_scatter() -> None:
    # The same pin, the same seated flank: a gear's scatter on one fixture is
    # its bore's float and its tooth form, not twice the pin's play.
    stub = pin = axis = (0.0, 0.0)
    errors = {
        side: spec._phase_errors_deg(stub, pin, axis, spec.PIN_DIA_MIN, side)
        for side in (-1.0, 1.0)
    }
    one_flank = max((max(e) - min(e)) / 2.0 for e in errors.values())
    both = errors[-1.0] + errors[1.0]
    assert one_flank < (max(both) - min(both)) / 2.0


def test_both_pins_press_and_the_gear_slides_on_the_stub() -> None:
    assert min(spec.STUB_PRESS_INTERFERENCE) > 0.0
    assert min(spec.PIN_PRESS_INTERFERENCE) > 0.0
    assert spec.STUB_CLEARANCE[0] > 0.0
    # The .3740 ream: .0006 least interference.
    assert spec.STUB_PRESS_INTERFERENCE[0] / INCH == pytest.approx(0.0006, abs=1e-7)


def test_the_short_arm_grip_neither_pulls_the_stub_nor_yields_the_brass() -> None:
    # Torque = the 5/32 key's longest short arm (.938, ASME B18.3) x an
    # assumed 15 lbf at its end; preload by T = K D P, K .20.
    assert spec.CLAMP_TORQUE_IN_LBF == pytest.approx(15.0 * 0.938)
    assert spec.CLAMP_PRELOAD_LBF == pytest.approx(
        spec.CLAMP_TORQUE_IN_LBF / (0.20 * 0.190), rel=1e-6
    )
    assert spec.STUB_RETENTION_MARGIN == pytest.approx(5.84, abs=0.01)
    # The washer's ring on the gear's C360 (17 ksi): margin pinned as
    # computed, and the torque at which the ring yields.
    assert spec.WASHER_BEARING_MARGIN == pytest.approx(1.09, abs=0.01)
    assert spec.WASHER_YIELD_PRELOAD_LBF == pytest.approx(404, abs=1)
    assert spec.WASHER_YIELD_TORQUE_IN_LBF == pytest.approx(15.4, abs=0.1)


def test_the_clamp_stays_out_of_the_tools_sweep_and_seats_the_gear() -> None:
    assert spec.TOOL_SWEEP_MARGIN > 0.0
    assert spec.WASHER_BEARING_MIN > 0.0
    assert spec.CUT_TURNS_GEAR_CLOCKWISE
    # A cam no larger than the throw would reverse the cut's moment.
    assert not spec.cut_turns_gear_clockwise(spec.THROW)


def test_the_screw_engagement_counts_full_thread_only() -> None:
    assert spec.SCREW_ENGAGEMENT_MAX < spec.DOWEL_THREAD_DEPTH_MIN
    # The screw point and the tap mouth each cost about one thread height.
    lost = spec.SCREW_ENGAGEMENT_MIN - spec.SCREW_FULL_THREAD_MIN
    assert lost == pytest.approx((0.61343 + 0.54127) * spec.SCREW.pitch)
    assert spec.SCREW_ENGAGEMENT_MIN_PRINTED * INCH <= spec.SCREW_FULL_THREAD_MIN
    # Under rule 18's 1.5D floor at both ends, the range MHA-DT-12-TL-00
    # RV-01 accepts (.12-.21, 0.63D-1.10D); the kit sheet prints the value only.
    assert round(spec.SCREW_FULL_THREAD_MAX / INCH, 2) == 0.21
    assert round(spec.SCREW_ENGAGEMENT_DIAMETERS, 2) == 0.63
    assert int(spec.SCREW_FULL_THREAD_MAX / spec.DOWEL_THREAD_MAJOR * 100) == 110
    assert spec.SCREW_ENGAGEMENT_TEXT == ".12 MIN"


def test_pins_stand_inside_the_gear_and_the_body_carries_the_gear() -> None:
    assert spec.STUB_STAND + spec.STUB_STAND_BAND < spec.GEAR_THICKNESS_MIN
    assert spec.PIN_STAND < spec.FACE_WIDTH_MIN
    assert spec.BODY_DIA / 2.0 > spec.GEAR_SWING_RADIUS
    for wall, mm in spec.WALLS_MM.items():
        assert mm >= WALL_TARGET_MM, wall


def test_only_the_hole_stations_carry_a_model_band() -> None:
    bands = model_toleranced_dimensions(part)
    assert set(bands) == {("feature_name", "dimension_name")}
    # Rule 4, form 3: the press reams print the reamer's size, no band.
    assert set(spec.MODEL_BANDS_MM) == {
        ("StubHoleProfile", "StubOffset"),
        ("PinHoleProfile", "PinX"),
        ("PinHoleProfile", "PinY"),
    }
    for (feature, name), (lower, upper) in spec.MODEL_BANDS_MM.items():
        assert lower < upper
        assert name in spec.DRAWING_DIMENSIONS[feature]
        assert spec.DRAWING_PRECISION[feature][name] == 4


def test_every_marked_dimension_has_a_place_and_callouts_name_their_mates() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.FACE_KEEP) | set(drawing.EDGE_KEEP) == marked
    # Only the two REAM callouts carry words; a location carries its value
    # and band only (rule 7), and no callout carries a reason (rule 4).
    assert set(spec.CALLOUTS_BELOW) == {"StubHoleDia", "PinHoleDia"}
    for name, number in (
        ("StubHoleDia", spec.STUB_NUMBER),
        ("PinHoleDia", spec.CLOCK_PIN_NUMBER),
    ):
        process, *words = spec.CALLOUTS_BELOW[name].splitlines()
        assert process.startswith("REAM")
        assert len(words) <= 2
        assert f"PRESS FIT ON {spec.kit_short_form(number)}" in words[0]
        assert number.endswith(spec.kit_short_form(number))
        assert not any(word.startswith(("SETS", "LOCATES")) for word in words)
    assert "DOES NOT TURN BY HAND" in spec.CALLOUTS_BELOW["StubHoleDia"]
    assert spec.PIN_HOLE_DEPTH_TEXT in spec.CALLOUTS_BELOW["PinHoleDia"]
    # A .0375 pin pressed blind has no knockout: the pair is permanent.
    assert "PERMANENT PAIR" in spec.CALLOUTS_BELOW["PinHoleDia"]
    assert not hasattr(spec, "FUNCTION_NOTE")
    assert set(spec.GLOBALS) >= marked


def test_every_station_and_size_stands_outside_the_disc() -> None:
    radius = spec.BODY_DIA / 2.0 * drawing._S
    for name, (x, y) in drawing.FACE_KEEP.items():
        if name == "BodyDia":
            continue
        assert math.dist((x, y), drawing.FACE_CENTER) > radius, name
    # The register's diameter reads on the edge view, right of it.
    assert drawing.BODY_DIA_ON_EDGE[0] > drawing.EDGE_CENTER[0] + (
        spec.THICKNESS / 2.0 * drawing._S
    )


def test_the_build_volume_budget_counts_every_hole() -> None:
    assert math.isclose(
        part.V_FINISHED, part.V_BODY - part.V_STUB_HOLE - part.V_PIN_HOLE
    )
    assert part.THROUGH_CUT_DEPTH > spec.THICKNESS


def test_the_kit_holds_the_fixture_and_stays_out_of_the_machine() -> None:
    assert "dt_cylinder_gear_tl_cam_fixture" in bg.references_of(KIT)
    assert KIT in bg.ASSEMBLY_ORDER
    assert KIT not in bg.MACHINE_ASSEMBLIES
    assert bg.is_shop_fixture(KIT)
