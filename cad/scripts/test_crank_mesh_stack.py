"""Actual-stock crank source and publication gates; no measurement is invented."""
from __future__ import annotations

import math
from pathlib import Path

import pytest

import crank_mesh_geometry as geometry
import crank_mesh_stack as stack


def _nominal():
    return geometry.calibration_case_parameters()[0]


def _conditional(pose=None,**changes):
    return geometry.uniform_pose_domain(
        _nominal()["pose"] if pose is None else pose,
        conditional_lateral_origin_half_width_mm=.01,**changes)


def test_print_worst_closing_corner_cannot_bind():
    stack.require_qualified()
    assert 0 < stack.TIGHT_BACKLASH_MM <= stack.NOMINAL_TIGHT_BACKLASH_MM


def test_actual_coverage_row_and_continuous_carrier_retain_their_floors():
    stack.require_qualified()
    assert stack.STOCK_FORM_COVERAGE_WORST >= .62
    assert stack.ROW_ENGAGEMENT_FRACTION_WORST >= .85
    assert stack.CONTINUOUS_CARRYING_CONTACT
    assert stack.MAX_HANDOVER_JUMP_MM <= .005
    assert stack.PHASE_WINDOW_RAD[0] < math.radians(stack.MESH_WINDOW_CENTRE_DEG) < stack.PHASE_WINDOW_RAD[1]


def test_actual_lateral_origin_missing_grade_is_unknown_not_zero():
    source = _nominal()["continuous_source_domain"]
    assert source["source_domain_status"] == "UNKNOWN"
    assert source["unbound_sources"]
    assert dict(source["correlated_pose_parameters"])["driver_dx_mm"] is None
    assert not source["production_source_domain"]
    assumed = _conditional()
    assert assumed["scope"] == "DESIGN_CONDITIONAL_SOURCE_DOMAIN"
    assert assumed["source_domain_status"] == "BOUND" and not assumed["production_source_domain"]
    assert assumed["conditional_design_assumptions"]["relative_running_bore_lateral_origin_half_width_mm"] == .01
    with pytest.raises(ValueError,match="unbound"):
        geometry.nominal_reference_domain(source,_nominal()["pose"])


def test_every_printed_profile_corner_has_the_whole_continuous_source():
    rows = geometry.calibration_case_parameters(conditional_source={"conditional_lateral_origin_half_width_mm":.01})
    expected = {(a,b) for a,_ in geometry.pinion.STOCK_PROFILE_CORNERS for b,_ in geometry.gear64.STOCK_PROFILE_CORNERS}
    assert len(rows) == 1+len(expected) == 17
    assert {(row["driver_profile_label"],row["driven_profile_label"]) for row in rows[1:]} == expected
    assert all(row["continuous_source_domain"] == rows[0]["continuous_source_domain"] for row in rows)
    assert all(row["pose"]["yaw_deg"] == row["pose"]["tilt_deg"] == row["pose"]["cone_float_mm"] == 0 for row in rows)
    assert not any(name in geometry.required_calibration_case_names() for name in ("booked_open","booked_closed"))


def test_each_journal_keeps_its_own_printed_pair_and_actual_contact_span(monkeypatch):
    assert geometry.CRANK_RUNNING == geometry.shaft.JOURNAL_DIAMETRAL_CLEARANCE_MM
    assert geometry.CONE_RUNNING == geometry.cone_shaft.JOURNAL_DIAMETRAL_CLEARANCE_MM
    assert geometry.CRANK_BEARING_LENGTH == geometry.shaft.JOURNAL_SUPPORT_SPAN_MIN_MM
    assert geometry.CONE_BEARING_LENGTH == geometry.cone_shaft.JOURNAL_SUPPORT_SPAN_MIN_MM
    before = _conditional()
    monkeypatch.setattr(geometry,"CRANK_RUNNING",(geometry.CRANK_RUNNING[0],geometry.CRANK_RUNNING[1]*1.25))
    changed = _conditional()
    a,b = dict(before["correlated_pose_parameters"]),dict(changed["correlated_pose_parameters"])
    assert b["driver_dx_mm"][1] > a["driver_dx_mm"][1]
    assert b["driver_rx_rad"][1] > a["driver_rx_rad"][1]
    assert all(b[name] == bounds for name,bounds in a.items() if name.startswith("driven_"))
    monkeypatch.setattr(geometry,"CONE_BEARING_LENGTH",geometry.CONE_BEARING_LENGTH/2)
    shorter = dict(_conditional()["correlated_pose_parameters"])
    assert shorter["driven_rx_rad"][1] > b["driven_rx_rad"][1]
    assert shorter["driven_dx_mm"][1] > b["driven_dx_mm"][1]
    assert all(shorter[name] == bounds for name,bounds in b.items() if name.startswith("driver_"))


@pytest.mark.parametrize("interval",[(-20.0,-20.0),(-15.0,-2.0),(0.0,0.0)])
def test_journal_origin_inside_retained_span_pays_only_one_radial_float(interval):
    receipt = geometry._journal_origin_motion(.06,20.0,interval)
    assert receipt["outside_support_lever_upper_mm"] == 0
    assert receipt["origin_motion_upper_mm"] == .03
    assert receipt["outside_support_rotation_upper_mm"] == 0


def test_journal_origin_zero_clearance_and_outside_lever_coupling():
    assert geometry._journal_origin_motion(0.0,20.0,(5.0,5.0))["origin_motion_upper_mm"] == 0
    near = geometry._journal_origin_motion(.06,20.0,(5.0,5.0))
    far = geometry._journal_origin_motion(.06,20.0,(-25.0,-25.0))
    assert near["outside_support_lever_upper_mm"] == far["outside_support_lever_upper_mm"] == 5
    assert near["origin_motion_upper_mm"] == far["origin_motion_upper_mm"]
    expected = .03+10*math.sin(near["angle_upper_rad"]/2)
    assert expected <= near["origin_motion_upper_mm"] <= math.nextafter(expected,math.inf)
    assert near["origin_motion_upper_mm"] < .03+2*25*math.sin(near["angle_upper_rad"]/2)
    shorter = geometry._journal_origin_motion(.06,10.0,(5.0,5.0))
    assert shorter["outside_support_lever_upper_mm"] == 5
    assert shorter["origin_motion_upper_mm"] > near["origin_motion_upper_mm"]
    assert shorter["radial_float_upper_mm"] == near["radial_float_upper_mm"] == .03


def test_actual_gear_origins_use_near_contact_coordinates_and_own_spans():
    ledger = _conditional()["physical_source_ledger"]
    driver,driven = (ledger[f"{body}_journal_origin_enclosure"] for body in ("driver","driven"))
    support_low,support_high = ledger["driver_retained_north_contact_shaft_station_interval_mm"]
    seat_low,seat_high = ledger["driver_actual_face_seat_deviation_mm"]
    assert driver["origin_from_north_contact_interval_mm"] == pytest.approx([
        geometry.shaft.SEAT_PINION+seat_low-support_high,
        geometry.shaft.SEAT_PINION+seat_high-support_low],abs=1e-12)
    collar = geometry.pinion.printed_deviations(
        geometry.cone_shaft.COLLAR_THICKNESS,geometry.cone_shaft.DRAWING_PRECISION_BY_NAME["CollarWidth"])
    assert driven["origin_from_north_contact_interval_mm"] == pytest.approx([
        geometry.GEAR64_POST_OFFSET-geometry.post.CONE_BOSS_LENGTH/2+collar[0],
        geometry.GEAR64_POST_OFFSET-geometry.post.CONE_BOSS_LENGTH/2+collar[1]
        +geometry.CONE_FLOAT_NORTH+geometry.cone_shaft.THRUST_EDGE_BREAK_MAX],abs=1e-12)
    for body,receipt,span,clearance in (
            ("driver",driver,geometry.CRANK_BEARING_LENGTH,geometry.CRANK_RUNNING[1]),
            ("driven",driven,geometry.CONE_BEARING_LENGTH,geometry.CONE_RUNNING[1])):
        low,high = receipt["origin_from_north_contact_interval_mm"]
        assert receipt["retained_contact_span_min_mm"] == span
        assert receipt["diametral_clearance_upper_mm"] == clearance
        assert ledger[f"{body}_journal_origin_lever_upper_mm"] == max(0,high,-span-low)
        assert receipt["radial_float_upper_mm"] == clearance/2
    assert "SOUTH face" in ledger["driver_origin_anchor"]
    assert "boss north face cancels" in ledger["driven_origin_anchor"]


def test_shared_boss_north_variation_is_not_another_cone_origin_lever(monkeypatch):
    before = _conditional()["physical_source_ledger"]
    # Shift the SAME boss north face and gear station together, retaining
    # each published fit/span. Only their relative outside lever matters.
    monkeypatch.setattr(geometry.post,"CONE_BOSS_LENGTH",geometry.post.CONE_BOSS_LENGTH+2)
    monkeypatch.setattr(geometry,"GEAR64_POST_OFFSET",geometry.GEAR64_POST_OFFSET+1)
    after = _conditional()["physical_source_ledger"]
    assert after["driven_journal_origin_enclosure"] == before["driven_journal_origin_enclosure"]


def test_north_float_is_one_actual_axial_seat_not_a_prebooked_gravity_shift(monkeypatch):
    before = _conditional()
    old = geometry.CONE_FLOAT_NORTH
    monkeypatch.setattr(geometry,"CONE_FLOAT_NORTH",old+.1)
    after = _conditional()
    a = before["physical_source_ledger"]["driven_actual_south_seat_deviation_mm"]
    b = after["physical_source_ledger"]["driven_actual_south_seat_deviation_mm"]
    assert b[0] == a[0] and b[1]-a[1] == pytest.approx(.1)
    assert after["finite_face_anchor_fraction"] == {"driver":0.0,"driven":0.0}
    assert "cancels" in after["physical_source_ledger"]["common_post_mount_motion"]
    assert "no pre-booked gravity" in after["physical_source_ledger"]["gravity_scope"]


def test_actual_both_per_gear_tir_stays_rotating_disks_not_static_closing_y(monkeypatch):
    before = _conditional()
    disks = before["source_eccentricity_disks"]
    assert geometry.pinion.TOOTH_RUNOUT_TIR_MM == geometry.gear64.TOOTH_RUNOUT_TIR_MM == .05
    for body,clearance,spec in (("driver",geometry.pinion.BORE_DIAMETRAL_CLEARANCE[1],geometry.pinion),
                                ("driven",geometry.GEAR_SEAT_CLEARANCE[1],geometry.gear64)):
        assert disks[body]["shape"] == "closed_disk"
        assert disks[body]["radius_mm"] >= (clearance+spec.TOOTH_RUNOUT_TIR_MM)/2
        axes = dict(before["correlated_pose_parameters"])
        assert axes[f"{body}_ecc_x_mm"] == axes[f"{body}_ecc_y_mm"] == [-disks[body]["radius_mm"],disks[body]["radius_mm"]]
    monkeypatch.setattr(geometry.pinion,"TOOTH_RUNOUT_TIR_MM",.075)
    after = _conditional()
    assert after["source_eccentricity_disks"]["driver"]["radius_mm"] > disks["driver"]["radius_mm"]
    assert after["source_eccentricity_disks"]["driven"] == disks["driven"]
    assert after["physical_source_ledger"]["post_relative_height_deviation_mm"] == before["physical_source_ledger"]["post_relative_height_deviation_mm"]


def test_unprovided_tooth_pattern_clocks_are_not_borrowed_from_cone_or_zeroed():
    axes = dict(_conditional()["correlated_pose_parameters"])
    assert axes["driver_clock_rad"][1] >= math.pi/16
    assert axes["driven_clock_rad"][1] >= math.pi/64
    assumed = _conditional(conditional_driven_clock_half_width_rad=.0001)
    assert dict(assumed["correlated_pose_parameters"])["driven_clock_rad"] == [-.0001,.0001]
    assert not assumed["production_source_domain"]
    assert assumed["conditional_design_assumptions"]["driven_material_clock_half_width_rad"] == .0001


def test_nominal_reference_uses_declared_semantic_point_not_asymmetric_y_midpoint():
    source = _conditional()
    source["correlated_pose_parameters"] = [[name,[0,.37] if name == "driver_dy_mm" else bounds]
                                            for name,bounds in source["correlated_pose_parameters"]]
    point = geometry.nominal_reference_domain(source,_nominal()["pose"])
    assert dict(point["correlated_pose_parameters"])["driver_dy_mm"] == [0,0]
    assert point["scope"] == "DESIGN_NOMINAL_SUBDOMAIN" and not point["production_source_domain"]
    assert point["nominal_reference_of_source"] == source
    assert point["finite_face_width_limits_mm"]["driver"] == [geometry.pinion.FACE_WIDTH]*2
    assert point["driver_retained_band_limits_mm"]["shoulder_z"] == [geometry.pinion.SHOULDER_LENGTH]*2
    source["nominal_source_parameters"]["driver_dy_mm"] = .1
    declared = geometry.nominal_reference_domain(source,_nominal()["pose"])
    assert dict(declared["correlated_pose_parameters"])["driver_dy_mm"] == [.1,.1]
    source["nominal_source_parameters"]["driver_dy_mm"] = -.1
    with pytest.raises(ValueError,match="outside"):
        geometry.nominal_reference_domain(source,_nominal()["pose"])


def test_selected_material_clock_uses_native_degree_order_not_a_driven_tare():
    pose = _nominal()["pose"]
    base = geometry.placement_record(pose)
    delta = .123456789
    selected = geometry.placement_record(pose,selected_phase_offset_deg=delta)
    assert base["driver_clocking_rad"] == -math.radians(geometry.pinion._PINION_DATUM_CLOCK_DEG)
    assert selected["driver_clocking_rad"] == -math.radians(geometry.pinion._PINION_DATUM_CLOCK_DEG+delta)
    assert all(selected[key] == value for key,value in base.items() if key != "driver_clocking_rad")
    assert selected["driven_clocking_rad"] == 0


def test_pure_geometry_digest_excludes_selected_output_packet_and_diagnostic_source(monkeypatch):
    original_read = Path.read_bytes
    def pure_source(path):
        assert "diagnostics" not in path.parts and path.suffix != ".json"
        return original_read(path)
    monkeypatch.setattr(Path,"read_bytes",pure_source)
    before = geometry.geometry_sha256()
    original_machine = geometry._config.machine
    def changed_output(*keys):
        if keys == ("gear_train","crank_mesh_phase_offset_deg"):
            return 123.456
        return original_machine(*keys)
    monkeypatch.setattr(geometry._config,"machine",changed_output)
    assert geometry.geometry_sha256() == before
    monkeypatch.setattr(geometry.pinion,"TOOTH_RUNOUT_TIR_MM",.075)
    assert geometry.geometry_sha256() != before


def test_actual_calibration_spans_complete_material_period_and_all_source_corners():
    payload = stack.require_qualified()
    assert set(payload["cases"]) == geometry.required_calibration_case_names()
    for case in payload["cases"].values():
        rows = case["full_period_cells"]
        assert rows[0]["phase_cell_rad"][0] == 0
        assert rows[-1]["phase_cell_rad"][1] == geometry.pinion.STOCK_PROFILE.angular_pitch_rad
        assert case["numerical_error_bounds"]["surface_mm"] > 0
        assert case["continuous_contact_certificate"]["sides"]["upper"]["periodic_seam"]["status"] == "PROVED"
    assert len(payload["nominal_reference_read_case"]["actual_read_phases"]) == 21


@pytest.mark.parametrize("field,value",[("stock_form_coverage_lower",.6199),("row_available_fraction_lower",.8499),
                                         ("continuous_carrying_contact",False),("tight_backlash_lower_mm",0.0)])
def test_actual_qualification_retains_all_unchanged_functional_floors(field,value):
    original = stack.require_qualified()
    payload = dict(original)
    payload["cases"] = dict(original["cases"])
    payload["cases"]["nominal"] = dict(original["cases"]["nominal"],**{field:value})
    with pytest.raises(ValueError):
        stack.require_qualified(payload)


def test_native_stack_has_no_old_independent_surface_grid_or_solver_import():
    text = Path(stack.__file__).read_text(encoding="utf-8")
    assert "import crank_mesh_backlash_study" not in text and "import crossed_mesh_study" not in text
    assert 'case["phase_rows"]' not in text
    assert "require_continuous_certificate" in text and "require_whole_period_envelope" in text
    assert "require_actual_read_phase" in text and "require_selected_driver_clock_transport" in text


@pytest.mark.parametrize("raw",[
    b'{"test_only_bad_value":1e999}',b'{"test_only_bad_value":NaN}',
    b'{"test_only_bad_value":Infinity}',b'{',
])
def test_actual_packet_parser_names_malformed_or_overflowing_json(tmp_path,monkeypatch,raw):
    import crank_mesh_calibration as calibration
    path = tmp_path/"TESTONLY-malformed-crank.json"
    path.write_bytes(raw)
    monkeypatch.setattr(calibration,"_PACKET_PATH",path)
    with pytest.raises(ValueError,match="malformed committed actual crank calibration packet"):
        calibration._read_packet()


def test_missing_actual_packet_retains_honest_observation_not_synthetic_evidence(tmp_path,monkeypatch):
    import crank_mesh_calibration as calibration
    monkeypatch.setattr(calibration,"_PACKET_PATH",tmp_path/"absent.json")
    payload,raw_sha = calibration._read_packet()
    assert payload["qualified"] is False and payload["cases"] == {}
    assert raw_sha is None and payload["geometry_sha256"] is None
    assert "500000" in payload["refusal"] and "0.849669" in payload["refusal"]
    assert "no physical infeasibility was proved" in payload["refusal"]
