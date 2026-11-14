"""Pure R4 workholding contracts; no native imports or execution."""
from __future__ import annotations

import math

import pytest

import ch_rocker_arm_tl_oblique_holding_spec as holding
import ch_rocker_arm_tl_oblique_carrier_spec as carrier
import ch_rocker_arm_tl_oblique_riser_spec as riser
import ch_rocker_arm_tl_vn_oblique_hub_washer_spec as washer
import ch_rocker_arm_tl_oblique_trammel_spec as trammel


def test_three_ordinary_receivers_replace_precision_workholding() -> None:
    assert carrier.CLAMP_THREAD == carrier.HUB_THREAD == "#8-32"
    assert carrier.END_CLAMPS == {"CL": trammel.CL, "CR": trammel.CR}
    for spec in (carrier.CL_SPEC, carrier.CR_SPEC, carrier.HUB_SPEC):
        assert spec.kind == "tapped"
        assert spec.end == "through_all"
    # #2151: every tap location is a native table row, none a printed station.
    assert not {"ClTap", "CrTap", "HubTap"} & carrier.DRAWING_DIMENSIONS.keys()
    for key in ("CL", "CR", "HUB"):
        assert carrier.TABLE_HOLES[key][2] == carrier.CLAMP_TAP_DRILL
    assert "LOCATIONS REF" in carrier.TABLE_ROW_NOTES["HUB"]  # in-situ, not manufactured XY
    assert not {"HubHoleProfile", "HubChamfer", "LeftClampTap"} & carrier.DRAWING_DIMENSIONS.keys()
    assert not hasattr(carrier, "CLAMP_STATION_BAND")
    assert not hasattr(carrier, "HUB_HOLE_DIA")
    assert not hasattr(carrier, "CL_DOWEL_DIA")
    assert not hasattr(carrier, "LEFT_CLAMP_SPEC")


def test_riser_has_relief_two_end_clearances_and_two_loose_stops() -> None:
    assert riser.HUB_DIA == 12.0
    assert riser.CLAMP_DIA == pytest.approx(0.196 * 25.4)
    assert set(riser.HOLES) == {"screw 1", "screw 2", "screw 3", "screw 4", "HUB", "CL", "CR", "stop 1", "stop 2"}
    assert len(riser.CIRCLES) == 3  # stops use actual #30 Hole Wizard, not nominal circles
    assert riser.STOP_DIA == riser.SCREW_DIA
    assert riser.STOP_HOLE_DIA <= riser.SCREW_DRILL_DIA <= riser.STOP_HOLE_MAX
    assert min(riser.CLAMP_BAND_WALLS) >= 2.032
    assert min(riser.WALLS_MM.values()) >= 2.032
    assert "LeftClampDia" not in riser.DRAWING_PRECISION_BY_NAME
    assert not {"Stop1X", "Stop2X", "StopY"} & riser.REFERENCE_DIMENSIONS
    assert riser.BLANK_WIDTH == pytest.approx(1.69 * 25.4)
    assert riser.BLANK_ORIGIN[1] == pytest.approx(0.52 * 25.4)
    assert riser.BLANK_ORIGIN[1] + riser.BLANK_WIDTH == pytest.approx(56.134)
    assert riser.THICKNESS == pytest.approx(0.24 * 25.4)


def test_common_screws_have_supplier_length_engagement_and_no_protrusion() -> None:
    assert holding.COMMON_SCREW.part_no == "91251A197"
    assert holding.SCREW_LENGTH_LIMITS == pytest.approx((18.288, 19.05))
    assert holding.END_FULL_THREAD_MIN == pytest.approx(8.37565)
    assert holding.HUB_FULL_THREAD_MIN == pytest.approx(6.72465)
    assert min(holding.END_FULL_THREAD_MIN, holding.HUB_FULL_THREAD_MIN) >= 1.5 * holding.COMMON_SCREW.major_dia
    assert holding.END_UNDERSIDE_CLEARANCE_MIN == pytest.approx(0.9398)
    assert holding.HUB_UNDERSIDE_CLEARANCE_MIN == pytest.approx(1.8542)
    assert holding.END_FILLET_CLEARANCE_MIN > 0.0
    holding.require_clearance()


def test_end_head_complete_sweeps_not_just_apex() -> None:
    assert holding.END_HEAD_GAPS == pytest.approx({"inner": 6.3477457888, "outer": 6.0592929690})
    assert min(holding.END_HEAD_GAPS_MIN.values()) > 2.0
    for name, radius in trammel.PASS_RADIUS.items():
        for point in carrier.END_CLAMPS.values():
            exact = holding.cutter_gap(point, holding.SCREW_HEAD_DIA_LIMITS[1] / 2.0, name)
            for i in range(101):
                theta = trammel.SWEEP[name] * (2.0 * i / 100.0 - 1.0)
                centre = (radius * math.sin(theta), radius * math.cos(theta) - trammel.H1)
                gap = math.dist(point, centre) - holding.SCREW_HEAD_DIA_LIMITS[1] / 2.0 - trammel.PART_CUTTER_DIA / 2.0
                assert exact <= gap + 1e-9


def test_registration_charges_both_translation_axes_for_end_material() -> None:
    nominal = holding.end_head_material_margins(riser.STRAP_RAW_Y_MIN, 0.0, 0.0)
    placed = holding.end_head_material_margins(riser.STRAP_RAW_Y_MIN, 0.5, 0.6)
    assert min(placed.values()) > 2.032
    assert nominal["square end"] - placed["square end"] == pytest.approx(0.6)
    assert nominal["registered raw edge"] - placed["registered raw edge"] == pytest.approx(0.5)
    assert nominal["outer saw edge"] - placed["outer saw edge"] == pytest.approx(math.hypot(0.5, 0.6))
    with pytest.raises(ValueError):
        holding.end_head_material_margins(19.558, -0.1, 0.0)


def test_plain_stock_pins_clear_self_cut_and_set_retraction_height() -> None:
    assert riser.STOP_PIN_LENGTH == pytest.approx(19.05, rel=0.0, abs=1e-12)
    assert riser.STOP_PIN_LENGTH_BAND == pytest.approx(0.254)
    assert riser.STOP_HOLE_DIA > riser.STOP_PIN_DIA_LIMITS[1]
    assert riser.STOP_PIN_CONTACT_FLOAT_MAX > riser.STOP_PIN_FLOAT_MAX
    assert riser.STOP_REGISTRATION_ERROR <= 0.5
    assert riser.STOP_RAW_Y_LIMITS[0] < riser.STRAP_RAW_Y_MIN < riser.STOP_RAW_Y_LIMITS[1]
    assert min(holding.STOP_PIN_GAPS_MIN.values()) > 5.0
    assert holding.STOP_PIN_TOP_FLOAT_MAX > riser.STOP_PIN_CONTACT_FLOAT_MAX
    theta = math.atan(riser.STOP_PIN_SLOPE_MAX)
    tilted_cylinder_height = (
        riser.STOP_PIN_TOP_LIMITS[1] * math.cos(theta)
        + riser.STOP_PIN_DIA_LIMITS[1] * math.sin(theta)
    )
    assert holding.STOP_PIN_HEIGHT_MAX >= tilted_cylinder_height > 19.304
    assert holding.TOOLING_TOP_Z_MAX == pytest.approx(
        trammel.CARRIER_TOP_Z + holding.STOP_PIN_HEIGHT_MAX
    )
    assert holding.TOOLING_TOP_Z_MAX > max(holding.CLAMP_TOP_Z.values())
    # The rejected screw alternative physically projects into the carrier.
    assert holding.COMMON_SCREW.length > riser.THICKNESS
    assert riser.THICKNESS - riser.THICKNESS_BAND < 1.5 * holding.COMMON_SCREW.major_dia


def test_compatible_standard_reamer_clears_without_counterbore() -> None:
    assert holding.PRODUCT_HOLE_LIMITS == pytest.approx((10.16, 10.1727))
    assert holding.TOOL_BREAKTHROUGH_SPACE_MIN == pytest.approx(5.842)
    assert holding.REAMER_LEAD_MAX == pytest.approx(5.08635)
    assert holding.REAMER_DEPTH_RESERVE == pytest.approx(0.50165)
    assert holding.DRILL_DEPTH_RESERVE > 2.5
    assert holding.tool_depth_reserve(holding.REAMER_LEAD_MAX, 0.127, 0.127) == pytest.approx(0.50165)
    assert holding.tool_depth_reserve(6.0, 0.0, 0.0) < 0.0
    with pytest.raises(ValueError):
        holding.tool_depth_reserve(-1.0, 0.0, 0.0)


def test_screw_centres_bought_washer_and_its_offset_reaches_the_cutter_gaps() -> None:
    # Owner ruling 2026-11-13 (#2448): McMaster 90231A116 to ASME B18.21.1
    # Table 11 No. 8 Type A, ID .188 +.008/-.005, OD .438 +.015/-.005.
    assert washer.SKU == "90231A116" and washer.QUANTITY == 1
    assert (washer.ID_MIN, washer.ID_MAX) == pytest.approx((0.183 * 25.4, 0.196 * 25.4))
    assert (washer.OD_MIN, washer.OD_MAX) == pytest.approx((0.433 * 25.4, 0.453 * 25.4))
    assert (washer.THICKNESS_MIN, washer.THICKNESS_MAX) == pytest.approx((0.036 * 25.4, 0.065 * 25.4))
    assert washer.OD_ID_RUNOUT_MAX == pytest.approx(0.013 * 25.4)
    # The bore's float on the #8-32 least major plus the full runout.
    assert holding.WASHER_FLOAT_MAX == pytest.approx((washer.ID_MAX - holding.SCREW_MAJOR_MIN) / 2.0)
    assert holding.WASHER_FLOAT_MAX == pytest.approx(0.47625)
    assert holding.WASHER_OFFSET_MAX == pytest.approx(0.47625 + 0.3302)
    # The least bore passes the screw; the least O.D. spans the largest hole.
    assert holding.WASHER_SCREW_CLEARANCE_MIN == pytest.approx(0.24130)
    assert holding.PRODUCT_HOLE_LIMITS == pytest.approx((10.16, 10.1727))
    assert holding.STRAP_BEARING_LAND_CONCENTRIC == pytest.approx(0.41275)
    # At the worst offset the rim overhangs the hole on one side: the partial
    # bearing the ruling accepts, disclosed, not gated.
    assert holding.STRAP_BEARING_LAND_MIN == pytest.approx(
        holding.STRAP_BEARING_LAND_CONCENTRIC - holding.WASHER_OFFSET_MAX - carrier.HUB_RADIAL_STACK
    )
    assert holding.STRAP_BEARING_LAND_MIN == pytest.approx(-0.51958, abs=5e-5)
    # The under-head fillet can overlap the least bore by .0025 in; brass coins.
    assert holding.FILLET_BORE_OVERLAP_MAX == pytest.approx(0.0635)
    assert holding.WASHER_GAPS == pytest.approx({
        "inner": trammel.HUB_RADIUS - trammel.R_INNER - washer.OD / 2.0,
        "outer": trammel.R_OUTER - trammel.HUB_RADIUS - washer.OD / 2.0,
    })
    assert min(holding.WASHER_GAPS_MIN.values()) > 0.0
    assert not hasattr(holding, "WASHER_CLEARANCE_MIN")
    assert not hasattr(holding, "SPIGOT_FLOAT_MAX")
    base = holding.washer_cutter_gaps()
    shifted = holding.washer_cutter_gaps(0.1)
    for name, gap in base.items():
        assert gap - shifted[name] == pytest.approx(0.1)
    assert holding.HUB_TORQUE_NM == 1.0
    with pytest.raises(ValueError):
        holding.washer_cutter_gaps(-0.001)


def test_guard_rejects_screw_protrusion_and_real_cutter_floor(monkeypatch) -> None:
    monkeypatch.setattr(holding, "END_UNDERSIDE_CLEARANCE_MIN", -0.001)
    with pytest.raises(AssertionError, match="protrudes"):
        holding.require_clearance()
    monkeypatch.setattr(holding, "END_UNDERSIDE_CLEARANCE_MIN", 1.0)
    monkeypatch.setattr(holding, "WASHER_GAPS_MIN", {"inner": 2.0, "outer": 0.0})
    with pytest.raises(AssertionError, match="cutter sweep"):
        holding.require_clearance()
    monkeypatch.setattr(holding, "WASHER_GAPS_MIN", {"inner": 2.0, "outer": 0.001})
    monkeypatch.setattr(holding, "STRAP_BEARING_LAND_CONCENTRIC", 0.0)
    with pytest.raises(AssertionError, match="drops into the hub hole"):
        holding.require_clearance()


def test_table_layer_charges_each_correlated_pin_error_once() -> None:
    # Washer: each pass's own correlated pin error against the in-situ HUB,
    # beside the washer's offset, HUB setting and carriage play, never the product band.
    base = holding.washer_cutter_gaps()
    for name in trammel.SWEEP:
        assert holding.WASHER_GAPS_MIN[name] == pytest.approx(
            base[name] - carrier.PIN_RELATIVE_ERROR[name]
        )
        assert holding.WASHER_GAPS_MIN[name] == pytest.approx(
            holding.cutter_gap(trammel.HUB, washer.OD_MAX / 2.0, name)
            - holding.WASHER_OFFSET_MAX - carrier.PIN_RELATIVE_STACK[name]
        )
    # OD .453 offset .806 mm plus .02 play, with the 2026-11-13 ream ruling's
    # HUB stack, leaves ~0.920 outer, above the > 0 floor.
    assert holding.WASHER_GAPS_MIN == pytest.approx({"inner": 1.52230, "outer": 0.91983}, abs=5e-5)
    # End heads: each point's own table-row and cut displacement.
    for name in trammel.SWEEP:
        assert holding.END_HEAD_GAPS_MIN[name] == pytest.approx(min(
            holding.cutter_gap(point, holding.SCREW_HEAD_DIA_LIMITS[1] / 2.0, name)
            - carrier.station_sweep_error(point, name)
            for point in carrier.END_CLAMPS.values()
        ) - holding.END_HEAD_AXIS_FLOAT_MAX - holding.SCREW_HEAD_RADIAL_RUNOUT_MAX
            - trammel.RADIUS_FROM_SHOULDER_CLEARANCE)
        assert holding.END_HEAD_GAPS_MIN[name] < holding.END_HEAD_GAPS[name] - min(
            carrier.station_sweep_error(point, name) for point in carrier.END_CLAMPS.values()
        )
    # End material: the table row plus half of B1's error along X.
    half_d1 = max(map(abs, carrier.pin_coordinate_intervals()[0])) / 2.0
    assert holding.END_STATION_ERROR == pytest.approx(max(
        math.hypot(ex + half_d1, ey)
        for ex, ey in map(carrier.table_coordinate_errors, carrier.END_CLAMPS.values())
    ))
    assert holding.END_STATION_ERROR > carrier.TABLE_LOCATION_BAND
    # Stops: the riser's .XX station band, moved with the correlated cut.
    assert holding.STOP_STATION_BAND == pytest.approx(0.254)
    for name in trammel.SWEEP:
        assert holding.STOP_PIN_GAPS_MIN[name] == pytest.approx(min(
            holding.cutter_gap(point, riser.STOP_PIN_DIA_LIMITS[1] / 2.0, name,
                               cutter_diameter=trammel.RISER_CUTTER_DIA)
            - carrier.station_sweep_error(point, name, (holding.STOP_STATION_BAND,) * 2)
            for point in riser.STOP_PIN_CARRIER_POINTS
        ) - holding.STOP_PIN_TOP_FLOAT_MAX - trammel.RADIUS_FROM_SHOULDER_CLEARANCE)
