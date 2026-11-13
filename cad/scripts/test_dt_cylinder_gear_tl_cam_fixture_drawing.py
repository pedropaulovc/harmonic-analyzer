"""Offline contracts for the cylinder gears' cam turning fixture (MHA-DT-12-TL-01)."""

from __future__ import annotations

import math

import pytest

import _buildgraph as bg
import _config
import build_dt_cylinder_gear_tl_cam_fixture as part
import draw_dt_cylinder_gear_tl_cam_fixture as drawing
import dt_cylinder_gear_spec as gear
import dt_cylinder_gear_tl_cam_fixture_spec as spec
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_types import DrawingLayout
from _inch_wall_limits import WALL_TARGET_MM

INCH = 25.4
KIT = "dt_cylinder_gear_tl_cam_turning"


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


def test_the_stub_sets_the_gears_printed_throw() -> None:
    # The stub's printed station is the gear's printed throw on the .0001 grid.
    assert spec.STUB_OFFSET == pytest.approx(round(gear.ECCENTRICITY / INCH, 4) * INCH)
    assert abs(spec.STUB_OFFSET - gear.ECCENTRICITY) < 0.0001 * INCH
    # Per gear (the bore's float on the stub) inside the gear's band; the
    # fixed part (station and indication) is the same on all 20 gears.
    assert 0.0 < spec.THROW_PER_PART_MAX_MM <= gear.ECCENTRICITY_TOLERANCE_MM
    assert spec.THROW_FIXED_MAX_MM == pytest.approx(
        abs(spec.STUB_OFFSET - spec.THROW) + spec.POSITION_BAND + spec.REGISTER_OFFSET
    )
    assert spec.THROW_ERROR_MAX_MM == pytest.approx(
        spec.THROW_FIXED_MAX_MM + spec.THROW_PER_PART_MAX_MM
    )


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
        gear.NOTCH_PHASE_DEG, abs=0.01
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


def test_phase_budget_splits_fixed_and_per_part_terms() -> None:
    # (b): gear-to-gear scatter on the worst fixture, inside the printed band.
    assert 0.0 < spec.PHASE_PER_PART_WORST_DEG <= gear.CAM_PHASE_TOLERANCE_DEG
    # (a): common to all 20 gears, from the hole stations and the indication.
    assert spec.PHASE_FIXED_WORST_DEG > 0.0
    # Recorded, not asserted against the band: the open owner question.
    assert spec.PHASE_TOTAL_WORST_DEG >= spec.PHASE_PER_PART_WORST_DEG
    assert spec.PHASE_TOTAL_WORST_DEG >= spec.PHASE_FIXED_WORST_DEG


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
    assert spec.STUB_RETENTION_LBF > spec.CLAMP_PRELOAD_LBF


def test_the_clamp_stays_out_of_the_tools_sweep_and_seats_the_gear() -> None:
    assert spec.TOOL_SWEEP_MARGIN > 0.0
    assert spec.WASHER_BEARING_MIN > 0.0
    assert spec.CUT_TURNS_GEAR_CLOCKWISE
    # A cam no larger than the throw would reverse the cut's moment.
    assert not spec.cut_turns_gear_clockwise(spec.THROW)


def test_the_screw_engagement_shortfall_is_real_and_bounded() -> None:
    assert spec.SCREW_ENGAGEMENT_MAX < spec.DOWEL_THREAD_DEPTH_MIN
    assert spec.SCREW_ENGAGEMENT_MIN_PRINTED * INCH <= spec.SCREW_ENGAGEMENT_MIN
    # Under rule 18's 1.5D floor, which the kit sheet states as fact.
    assert spec.SCREW_ENGAGEMENT_DIAMETERS < 1.5


def test_pins_stand_inside_the_gear_and_the_body_carries_the_gear() -> None:
    assert spec.STUB_STAND + spec.STUB_STAND_BAND < spec.GEAR_THICKNESS_MIN
    assert spec.PIN_STAND < spec.FACE_WIDTH_MIN
    assert spec.BODY_DIA / 2.0 > spec.GEAR_SWING_RADIUS
    for wall, mm in spec.WALLS_MM.items():
        assert mm >= WALL_TARGET_MM, wall


def test_only_the_hole_stations_and_reams_carry_a_model_band() -> None:
    bands = model_toleranced_dimensions(part)
    assert set(bands) == {("feature_name", "dimension_name")}
    assert set(spec.MODEL_BANDS_MM) == {
        ("StubHoleProfile", "StubOffset"),
        ("PinHoleProfile", "PinX"),
        ("PinHoleProfile", "PinY"),
        ("StubHoleProfile", "StubHoleDia"),
        ("PinHoleProfile", "PinHoleDia"),
    }
    for (feature, name), (lower, upper) in spec.MODEL_BANDS_MM.items():
        assert lower < upper
        assert name in spec.DRAWING_DIMENSIONS[feature]
        assert spec.DRAWING_PRECISION[feature][name] == 4


def test_every_marked_dimension_has_a_place_and_callouts_name_their_mates() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.FACE_KEEP) | set(drawing.EDGE_KEEP) == marked
    # Only the two REAM callouts carry words; a location carries its value
    # and band only (rule 7).
    assert set(spec.CALLOUTS_BELOW) == {"StubHoleDia", "PinHoleDia"}
    gear_number = str(_config.parts("dt-cylinder-gear")["number"])
    for name, number in (
        ("StubHoleDia", spec.STUB_NUMBER),
        ("PinHoleDia", spec.CLOCK_PIN_NUMBER),
    ):
        process, *words = spec.CALLOUTS_BELOW[name].splitlines()
        assert process.startswith("REAM")
        assert len(words) <= 2
        assert f"PRESS FIT ON {spec.kit_short_form(number)}" in words[0]
        assert number.endswith(spec.kit_short_form(number))
        assert gear_number in words[1]
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
