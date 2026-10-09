"""Acceptance gates for the actual-stock 3D crossed-crank calibration.

The .62 coverage and .85 row floors are retained. A refused design is not
made green by treating a numerical study as a native contact certificate.
"""
from __future__ import annotations

from copy import deepcopy
import math
from pathlib import Path

import pytest

import crank_mesh_geometry as geometry
import crank_mesh_stack as stack


def test_print_worst_closing_corner_cannot_bind() -> None:
    stack.require_qualified()
    assert stack.TIGHT_BACKLASH_MM > 0.0
    assert stack.TIGHT_BACKLASH_MM <= stack.NOMINAL_TIGHT_BACKLASH_MM


def test_actual_coverage_row_and_continuous_carrier_retain_their_floors() -> None:
    stack.require_qualified()
    assert stack.STOCK_FORM_COVERAGE_WORST >= 0.62
    assert stack.ROW_ENGAGEMENT_FRACTION_WORST >= 0.85
    assert stack.CONTINUOUS_CARRYING_CONTACT
    assert stack.MAX_HANDOVER_JUMP_MM <= 0.005
    assert stack.PHASE_WINDOW_RAD[0] < math.radians(stack.MESH_WINDOW_CENTRE_DEG) < stack.PHASE_WINDOW_RAD[1]


def test_location_stacks_do_not_double_book_rotations_or_runout() -> None:
    assert sum(geometry.CLOSING_Y_TERMS.values()) < 0.0
    assert sum(geometry.OPENING_Y_TERMS.values()) > 0.0
    assert set(geometry.CLOSING_Y_TERMS) == {
        "crank bore spacing","crank float at rest","cone float at rest",
    }
    assert sum(geometry.closing_y_terms(spacing_printed=geometry.SPACING_PRINTED-0.2).values()) < sum(geometry.CLOSING_Y_TERMS.values())
    nominal = next(row for row in geometry.calibration_case_parameters() if row["name"] == "nominal")
    domain = geometry.uniform_pose_domain(nominal["pose"])
    assert domain.all_runout_angles
    assert domain.angularity_full_cone
    assert domain.radial_error_mm == pytest.approx(sum(row[1] for row in domain.components_mm))
    assert domain.axial_error_mm == pytest.approx(sum(row[2] for row in domain.components_mm))


def test_resting_shaft_tilt_increases_with_overhang() -> None:
    near = geometry.float_at_rest(0.05,70.0,0.0)
    far = geometry.float_at_rest(0.05,70.0,10.0)
    assert near == pytest.approx(0.025)
    assert far > near
    assert geometry.float_at_rest(0.05,35.0,10.0) > far


def test_each_journal_uses_its_actual_printed_pair_and_support_span(monkeypatch) -> None:
    assert geometry.CRANK_RUNNING == geometry.shaft.JOURNAL_DIAMETRAL_CLEARANCE_MM
    assert geometry.CONE_RUNNING == geometry.cone_shaft.JOURNAL_DIAMETRAL_CLEARANCE_MM
    assert geometry.CRANK_BEARING_LENGTH == geometry.shaft.JOURNAL_SUPPORT_SPAN_MIN_MM
    assert geometry.CONE_BEARING_LENGTH == geometry.cone_shaft.JOURNAL_SUPPORT_SPAN_MIN_MM
    before = geometry.closing_y_terms()
    monkeypatch.setattr(geometry,"CRANK_RUNNING",(
        geometry.CRANK_RUNNING[0],geometry.CRANK_RUNNING[1]*1.25,
    ))
    after = geometry.closing_y_terms()
    assert after["crank float at rest"] < before["crank float at rest"]
    assert after["cone float at rest"] == before["cone float at rest"]
    monkeypatch.setattr(geometry,"CONE_BEARING_LENGTH",geometry.CONE_BEARING_LENGTH/2)
    shorter = geometry.closing_y_terms()
    assert shorter["cone float at rest"] > after["cone float at rest"]
    assert shorter["crank float at rest"] == after["crank float at rest"]


def test_exact_north_float_and_gravity_are_actual_pose_translations() -> None:
    parameters = {row["name"]:row["pose"] for row in geometry.calibration_case_parameters()}
    opened = parameters["booked_open"]
    nominal = parameters["nominal"]
    assert opened["extra_mm"] == nominal["extra_mm"]
    assert opened["cone_float_mm"] == geometry.CONE_FLOAT_NORTH
    assert opened["cone_dy_mm"] == -geometry.OPENING_Y_TERMS["cone float at rest"]
    reference = geometry.placement_record(dict(opened,cone_float_mm=0.0))
    moved = geometry.placement_record(opened)
    delta = [moved["driven_origin_mm"][i]-reference["driven_origin_mm"][i] for i in range(3)]
    assert delta == pytest.approx([
        geometry.CONE_FLOAT_NORTH*geometry.SIN_I,0.0,
        geometry.CONE_FLOAT_NORTH*geometry.COS_I,
    ])


def test_uniform_domain_pays_axial_station_and_physical_pivot_reach() -> None:
    nominal = next(row for row in geometry.calibration_case_parameters() if row["name"] == "nominal")
    domain = geometry.uniform_pose_domain(nominal["pose"])
    parts = {name:(radial,axial) for name,radial,axial in domain.components_mm}
    station = parts["actual 64T axial station interval"]
    assert station[0] >= geometry.STATION_TRAVEL_MM*abs(geometry.SIN_I)
    assert station[1] == geometry.STATION_TRAVEL_MM
    angular = parts["crank angularity about actual post-axis datum"]
    assert angular[0] > geometry.MESH_LEVER*math.sin(math.radians(geometry.POST_ANGLE_DEG))
    assert angular[1] > 0.0


def test_stock_profiles_are_bound_into_the_calibration_identity() -> None:
    import crank_drive_phase as phase
    stack.require_qualified()

    assert phase.GEOMETRY_SHA256 == phase.geometry_sha256()
    assert geometry.pinion.STOCK_PROFILE.template.reference_teeth == 14
    assert geometry.gear64.STOCK_PROFILE.template.reference_teeth == 55
    assert geometry.gear64.STOCK_PROFILE.teeth == 64
    assert geometry.gear64.STOCK_PROFILE.helix_angle_deg == geometry.gear64.HELIX_ANGLE_DEG


def test_calibration_contains_full_pitch_and_source_owned_corners() -> None:
    stack.require_qualified()
    nominal = stack.CALIBRATION_CASES["nominal"]
    rows = nominal["phase_rows"]
    assert len(rows) >= 65
    assert rows[0]["driver_phase_rad"] == 0.0
    assert rows[-1]["driver_phase_rad"] == pytest.approx(2*math.pi/geometry.pinion.TEETH)
    assert nominal["metric"] == "STOCK-FORM COVERAGE"
    assert not nominal["is_conjugate"]
    assert not nominal["native_certificate"]
    names = set(stack.CALIBRATION_CASES)
    assert names == geometry.required_calibration_case_names()
    assert all(case["numerical_error_bounds"]["surface_mm"] > 0.0 for case in stack.CALIBRATION_CASES.values())


@pytest.mark.parametrize("field,value",[
    ("stock_form_coverage_lower",0.6199),
    ("row_available_fraction_lower",0.8499),
    ("continuous_carrying_contact",False),
    ("tight_backlash_lower_mm",0.0),
])
def test_qualification_refuses_discriminating_coverage_gap_and_corner_mutations(field,value) -> None:
    stack.require_qualified()
    payload = deepcopy(stack.CALIBRATION)
    payload["cases"]["nominal"][field] = value
    with pytest.raises(ValueError):
        stack.require_qualified(payload)


def test_qualification_refuses_stale_profile_identity() -> None:
    stack.require_qualified()
    payload = deepcopy(stack.CALIBRATION)
    payload["geometry_sha256"] = "0"*64
    with pytest.raises(ValueError,match="geometry"):
        stack.require_qualified(payload)


def test_native_stack_does_not_import_the_diagnostic_solver() -> None:
    source = Path(stack.__file__).read_text(encoding="utf-8")
    assert "import crank_mesh_backlash_study" not in source
    assert "import crossed_mesh_study" not in source
    assert "EQUIVALENT_RADIUS_GROWTH" not in source
    assert "def contact_ratio" not in source
    assert "0.30434519716270647" not in source


def test_physical_identity_never_reads_diagnostic_source(monkeypatch) -> None:
    import crank_drive_phase as phase
    original = Path.read_bytes

    def pure_source_only(path):
        assert "diagnostics" not in path.parts
        return original(path)

    monkeypatch.setattr(Path,"read_bytes",pure_source_only)
    identity = phase.geometry_sha256()
    assert len(identity) == 64
    assert set(identity) <= set("0123456789abcdef")


def test_correlated_pose_keeps_each_actual_rotating_runout_source(monkeypatch) -> None:
    nominal = next(row for row in geometry.calibration_case_parameters() if row["name"] == "nominal")
    source = dict(geometry.uniform_pose_domain(nominal["pose"]).correlated_pose_parameters)
    radius16 = geometry.pinion.BORE_DIAMETRAL_CLEARANCE[1]/2+geometry.pinion.TOOTH_RUNOUT_TIR_MM/2
    radius64 = geometry.GEAR_SEAT_CLEARANCE[1]/2+geometry.gear64.TOOTH_RUNOUT_TIR_MM/2
    assert source["driver_ecc_x_mm"] == (-radius16,radius16)
    assert source["driver_ecc_y_mm"] == (-radius16,radius16)
    assert source["driven_ecc_x_mm"] == (-radius64,radius64)
    assert source["driven_ecc_y_mm"] == (-radius64,radius64)
    assert source["driven_dz_mm"] == (-geometry.STATION_TRAVEL_MM,geometry.STATION_TRAVEL_MM)
    assert source["driver_dx_mm"][1] > 0.0
    assert source["driver_rx_rad"][1] > 0.0
    assert source["driven_rx_rad"][1] > 0.0
    monkeypatch.setattr(geometry.pinion,"TOOTH_RUNOUT_TIR_MM",geometry.pinion.TOOTH_RUNOUT_TIR_MM*1.5)
    changed = dict(geometry.uniform_pose_domain(nominal["pose"]).correlated_pose_parameters)
    assert changed["driver_ecc_x_mm"][1] > source["driver_ecc_x_mm"][1]
    assert changed["driven_ecc_x_mm"] == source["driven_ecc_x_mm"]
