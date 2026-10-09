"""Isolated ALL20 packet-reader contracts; synthetic evidence is never published.

Core cutters/profiles and printed corners are real. Contact/source receipts are
faithful synthetic records at the reader boundary, not numerical or native
observations. Every test uses a temporary JSON file, never cad/out or a real
calibration packet. Parent owns execution and authentic packet qualification.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import itertools
import json
import math
from pathlib import Path

import pytest

import _fit_limits

import dt_cone_gear_notes as notes
import dt_cone_gear_spec as spec
import dt_cylinder_gear_spec as drum
import dt_cone_mesh_domain as domain_supplier
from _stock_contact_test_fixtures import synthetic_case
from stock_form_cutter import StockFormProfile, translation_for_pitch_tooth_thickness


def _profile(profile: StockFormProfile) -> dict:
    return {
        "teeth": profile.teeth, "reference_teeth": profile.template.reference_teeth,
        "dp": profile.template.diametral_pitch, "pa_deg": profile.template.pressure_angle_deg,
        "blank_radius_mm": profile.blank_radius_mm,
        "radial_translation_mm": profile.radial_translation_mm,
        "helix_angle_deg": profile.helix_angle_deg,
    }


def _synthetic_setting(teeth: int) -> tuple[dict, StockFormProfile, tuple]:
    """Derive supported test geometry from core primitives, not final arrays."""
    cutter = spec.cutter_template(teeth)
    pitch = teeth * spec.MODULE_MM / 2.0
    maximum_bore = math.ceil(
        (spec.bore_dia_mm(teeth) + spec.BORE_DIA_BAND[0]) * 1000.0 - 1e-9,
    ) / 1000.0
    root_floor = maximum_bore / 2.0 + spec.WEB_EXCEPTIONS_MM.get(teeth, spec.MACHINED_WEB_TARGET_MM)
    if teeth == 6:
        root_floor = max(root_floor, 1.173) + 0.005
    else:
        root_floor = max(root_floor + 0.005, pitch - 1.25 * spec.MODULE_MM)
    lower = StockFormProfile(teeth, cutter, pitch, root_floor - cutter.root_radius_mm)
    thickness = math.ceil((lower.pitch_tooth_thickness_mm - spec.TOOTH_THICKNESS_BAND[1]) * 1000.0) / 1000.0
    shifts = tuple(translation_for_pitch_tooth_thickness(teeth, cutter, thickness + side)
                   for side in (spec.TOOTH_THICKNESS_BAND[1], spec.TOOTH_THICKNESS_BAND[0]))
    probes = tuple(StockFormProfile(teeth, cutter, pitch, shift) for shift in shifts)
    # Test stock stays near the actual pitch circle, safely inside both finite
    # cutter endpoints; this is not a production OD selection or mesh study.
    supported_od = 2.0 * min(p.support_radius_max_mm for p in probes) - spec.BLANK_DIA_BAND[0] - 0.01
    outside = math.floor(min(2.0 * (pitch + spec.MODULE_MM / 4.0), supported_od) * 100.0) / 100.0
    shift = translation_for_pitch_tooth_thickness(teeth, cutter, thickness)
    nominal = StockFormProfile(teeth, cutter, outside / 2.0, shift)
    corners = tuple(StockFormProfile(teeth, cutter, (outside + side) / 2.0, value)
                    for side, value in itertools.product(spec.BLANK_DIA_BAND, shifts))
    return {
        "outside_dia_mm": outside, "pitch_thickness_mm": thickness,
        "tool_translation_mm": shift, "translation_limits_mm": list(shifts),
        "nominal_plunge_mm": nominal.plunge_mm,
        "root_envelope_mm": [nominal.root_radius_min_mm, nominal.root_radius_max_mm],
        "actual_pitch_tooth_thickness_mm": nominal.pitch_tooth_thickness_mm,
        "reconstructed_from_actual_loaded_core": True,
    }, nominal, corners


def _source_domain(teeth: int) -> dict:
    """Explicit isolated source grades, not live receiving/configuration data."""
    disks = {}
    axes = {"driver_clock_rad": [-1e-7, 1e-7], "driven_clock_rad": [-1e-7, 1e-7]}
    for body, radial_grade in (("driver", .005), ("driven", .004)):
        radius = math.nextafter(radial_grade, math.inf)
        disks[body] = {
            "shape": "closed_disk", "centre_mm": [0.0, 0.0], "radius_mm": radius,
            "source_terms_mm": {"synthetic_received_radial_grade": radial_grade},
        }
        for axis in ("x", "y"):
            axes[f"{body}_ecc_{axis}_mm"] = [-radius, radius]
    return {
        "scope": "FULL_PRODUCTION_SOURCE_DOMAIN", "production_source_domain": True,
        "mechanical_zero_rad": {"driver": 0.0, "driven": math.pi},
        "correlated_pose_parameters": [[name, value] for name, value in sorted(axes.items())],
        "root_air_requirements_mm": {"driver": .02, "driven": .10},
        "source_eccentricity_disks": disks, "radial_error_mm": 0.0, "axial_error_mm": 0.0,
        "manufactured_datum_mapping": domain_supplier.manufactured_datum_mapping(teeth),
        "finite_face_width_limits_mm": {"driver": [2.0, 2.0], "driven": [4.0, 4.0]},
        "finite_face_anchor_fraction": {"driver": .5, "driven": .5},
        "fixture_origin": "reader-only synthetic SOURCE, not a production grade",
    }


def _placement(teeth: int) -> dict:
    centre = (teeth + drum.TEETH) * spec.MODULE_MM / 2.0 + spec._config.fit("cone_drum_oblique_mesh", "edge_slack_mm")
    identity = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    return {
        "driver_origin_mm": [0.0, 0.0, 0.0], "driven_origin_mm": [centre, 0.0, 0.0],
        "driver_frame": identity, "driven_frame": identity,
        "driver_face_mm": [-1.0, 1.0], "driven_face_mm": [-2.0, 2.0],
        "driver_clocking_rad": math.pi / teeth,
        "driven_clocking_rad": math.pi,
        "driver_shoulder_z_mm": None, "driver_turned_radius_mm": None,
    }


def _stock_phase_report(cone: StockFormProfile, mate: StockFormProfile, domain: dict) -> dict:
    """Canonical TEST-ONLY receipt shape; never an engine observation."""
    return synthetic_case(
        cone, mate, _placement(cone.teeth), domain,
        read_phases_rad=tuple(-index * math.pi for index in range(21)),
    )


def _report(cone: StockFormProfile, mate: StockFormProfile) -> dict:
    robust = _stock_phase_report(cone, mate, _source_domain(cone.teeth))
    inspection_radius = (
        (cone.teeth + mate.teeth) * spec.MODULE_MM / 2.0
        + spec._config.fit("cone_drum_oblique_mesh", "edge_slack_mm")
    ) * mate.teeth / (cone.teeth + mate.teeth)
    inspection_cells = []
    for cell in robust["full_period_cells"]:
        angular = cell["correlated_backlash"]["backlash_interval_rad"]
        inspection_cells.append({
            "actual_driver_interval_rad": deepcopy(cell["actual_driver_interval_rad"]),
            "correlated_backlash_interval_rad": deepcopy(angular),
            "source_calibrated_backlash_interval_mm": [
                math.nextafter(angular[0] * inspection_radius, -math.inf),
                math.nextafter(angular[1] * inspection_radius, math.inf),
            ],
            "physical_pitch_arc_backlash_interval_mm": deepcopy(cell["correlated_backlash_interval_mm"]),
        })
    reads = {
        "all_reads_bounded": True, "units": "signed cylinder radians",
        "datum": "physical CAM-NOTCH/cone-lock zero; no alignment-index feature or mean/home subtraction",
        "rows": [{
            "driver_phase_rad": read["actual_driver_phase_rad"],
            "read_phase_interval_rad": [read["actual_driver_phase_rad"]] * 2,
            "qualification": "pointwise bounded",
            "signed_running_te_interval_rad": deepcopy(read["signed_running_te_interval_rad"]),
        } for read in robust["actual_read_phases"]],
    }
    return {
        "qualification": "qualified", "production_qualified": True,
        "margins": dict.fromkeys((
            "supported_union_coverage", "handover_jump_mm", "phase_reserve_rad",
            "continuous_carrying", "tight_backlash_mm", "loose_backlash_mm",
            "cone_root_air_mm", "drum_root_air_mm",
        ), .001),
        "oblique_phase_bound_rad": .003, "nominal_oblique_phase_bound_rad": .002,
        "all_corner_actual3d": robust,
        "signed_read_matrix": reads, "full_period_cells": deepcopy(robust["full_period_cells"]),
        "actual_signed_read_phases": deepcopy(robust["actual_read_phases"]),
        "source_inspection_backlash_cells": inspection_cells,
        "actual_driven_backlash": {
            "tight_lower_mm": min(cell["source_calibrated_backlash_interval_mm"][0] for cell in inspection_cells),
            "loose_upper_mm": max(cell["source_calibrated_backlash_interval_mm"][1] for cell in inspection_cells),
            "source_inspection_radius_mm": inspection_radius,
            "physical_driven_pitch_radius_mm": mate.pitch_radius_mm,
        },
        "fixture_origin": "reader-only synthetic receipts; not geometric qualification",
    }


def _row(teeth: int) -> dict:
    setting, profile, corners = _synthetic_setting(teeth)
    mate_corners = drum.manufacturing_corner_profiles()
    cases = [{
        "case_id": "nominal", "cone_corner_index": None, "drum_corner_index": None,
        "cone": _profile(profile), "drum": _profile(drum.STOCK_FORM),
        "calculation": _report(profile, drum.STOCK_FORM),
    }]
    cases.extend({
        "case_id": f"C{ci:02d}-D{di:02d}", "cone_corner_index": ci, "drum_corner_index": di,
        "cone": _profile(cone), "drum": _profile(mate), "calculation": _report(cone, mate),
    } for (ci, cone), (di, mate) in itertools.product(enumerate(corners), enumerate(mate_corners)))
    source, placement = _source_domain(teeth), _placement(teeth)
    for case in cases:
        ci, di = case["cone_corner_index"], case["drum_corner_index"]
        cone, mate = (profile, drum.STOCK_FORM) if ci is None else (corners[ci], mate_corners[di])
        case["calculation"]["nominal_actual3d"] = _stock_phase_report(
            cone, mate, spec.nominal_source_subdomain(placement, source),
        )
        case["calculation"]["budget_actual3d"] = _stock_phase_report(
            cone, mate, spec.budget_clock_subdomain(source),
        )
    phases = [-index * math.pi for index in range(21)]
    references = cases[0]["calculation"]["nominal_actual3d"]["actual_read_phases"]
    values = [read["reference_signed_running_te_rad"] for read in references]
    bounds = [read["reference_error_bound_rad"] for read in references]
    half_widths, whole_intervals = {}, {}
    for role in ("nominal_actual3d", "budget_actual3d"):
        reports = [case["calculation"][role] for case in cases]
        half_widths[role] = [
            math.nextafter(max(bound, *(
                max(abs(endpoint - value) for endpoint in report["actual_read_phases"][index]["signed_running_te_interval_rad"])
                for report in reports
            )), math.inf)
            for index, (value, bound) in enumerate(zip(values, bounds, strict=True))
        ]
        intervals = [report["whole_period_signed_running_te_interval_rad"] for report in reports]
        whole_intervals[role] = [min(interval[0] for interval in intervals), max(interval[1] for interval in intervals)]
    selected = {
        **deepcopy(cases[0]["calculation"]), "setting": setting,
        "actual3d_mesh_evaluated": True, "actual_profile_cases": cases,
        "integral_cam_body_exclusion": {"qualified": True},
        "driver_profile": _profile(profile), "driven_profile": _profile(drum.STOCK_FORM),
        "manufactured_cone_corners": [_profile(p) for p in corners],
        "manufactured_drum_corners": [_profile(p) for p in mate_corners],
        "stock_phase_3d": {
            "schema": "dt-cone-operating-stock-phase/1", "operating_source_state": "OPERATING_NOTCH_UP",
            "operating_driver_sense": -1, "shaft_advance_included": False, "datum_tare_rad": None,
            "excluded_terms": list(spec.OBLIQUE_PHASE_EXCLUDED_TERMS),
            "manufactured_datum_mapping": domain_supplier.manufactured_datum_mapping(teeth),
            "half_width_scope": "nominal/all16 SAME requested stall; numerical reference bound included once",
            "phase_change_scope": "genuine whole-period intervals bound residual TE(psi+s)-TE(psi); pay the relevant width once when adding crank shaft advance",
            "driver_read_phases_rad": phases,
            "nominal_driven_advance_rad": [value - phase * teeth / drum.TEETH for value, phase in zip(values, phases, strict=True)],
            "nominal_signed_running_te_rad": values,
            "nominal_reference_numerical_bound_rad": bounds,
            "robust_half_width_rad": half_widths["budget_actual3d"],
            "nominal_pose_half_width_rad": half_widths["nominal_actual3d"],
            "robust_signed_te_interval_rad": whole_intervals["budget_actual3d"],
            "nominal_pose_signed_te_interval_rad": whole_intervals["nominal_actual3d"],
            "fixture_origin": "reader-only synthetic 3D root references; not geometric qualification",
        },
    }
    return {
        "teeth": teeth, "qualification": "qualified", "actual3d_mesh_evaluated": True,
        "cutter": spec.cutter_record(teeth), "selected": setting, "candidates": [selected],
        "printed_profile_root_envelope_mm": [
            min(p.root_radius_min_mm for p in corners), max(p.root_radius_max_mm for p in corners),
        ],
        "geometry": {"cone_axis": [0.0, 0.0, 1.0], "cone_centre_mm": [0.0, 0.0, float(teeth)]},
        "continuous_source_domain": _source_domain(teeth),
        "oblique_phase_bound_rad": 0.003,
        "oblique_phase_bound_excluded_terms": list(spec.OBLIQUE_PHASE_EXCLUDED_TERMS),
        "signed_read_matrix": deepcopy(cases[0]["calculation"]["signed_read_matrix"]),
        "stock_phase_3d": deepcopy(selected["stock_phase_3d"]),
    }


@pytest.fixture(scope="module")
def packet_template() -> dict:
    pure = spec.PART_GEOMETRY_SOURCE_PATHS | {
        "cad/scripts/dt_cone_support_pose.py", "cad/scripts/dt_cone_mesh_domain.py",
        "cad/scripts/cone_line.py",
    }
    paths = pure | spec.MEASUREMENT_SOURCE_PATHS
    hashes = {path: hashlib.sha256(f"synthetic captured bytes:{path}".encode()).hexdigest().upper() for path in paths}
    raw = {f"Z:/isolated-factory-fixture/{path}": sha for path, sha in hashes.items()}
    loaded = {path: sha for path, sha in raw.items() if path.endswith(tuple(p.rsplit("/", 1)[1] for p in spec.MEASUREMENT_SOURCE_PATHS))}
    manifest = {path.rsplit("/", 1)[1]: hashes[path] for path in spec.MEASUREMENT_SOURCE_PATHS}
    reads = {"machine:gear_train/diametral_pitch": spec.DIAMETRAL_PITCH}
    rows = [_row(teeth) for teeth in spec.CONFIGURATION_TEETH]
    booked = spec._config.fit("cone_drum_oblique_mesh", "centre_opening_mm")
    payload = {
        "family": "dt_cone_stock_form", "schema_version": 1, "qualified": True,
        "native_certificate": False, "source_inputs_only": False, "nominal_engineering_only": False,
        "geometry_inputs": spec.geometry_inputs(),
        "geometry_inputs_sha256": spec.geometry_sha256(spec.geometry_inputs()),
        "selected_geometry_sha256": spec.geometry_sha256(spec.selected_geometry_record(rows)),
        "measurement_engine_sources_sha256": manifest,
        "measurement_engine_sha256": spec.geometry_sha256(manifest),
        "rows": rows,
        "centre_stack_source_mm": {
            "measured_in_this_scope": True, "opening_total": booked,
            "opening_components": {"booked_total": booked, "derived_total": booked / 2.0, "selected_total": booked},
        },
        "source_identity": {
            "source_bytes_stable": True, "before_design_sha256": raw,
            "after_design_sha256": deepcopy(raw), "actual_preimport_project_sha256": deepcopy(raw),
            "loaded_algorithm_sha256": loaded,
            "actual_config_value_reads": reads, "geometric_config_value_sha256": spec.geometry_sha256(reads),
            "domain_pack_sha256": "A" * 64, "domain_pack_after_sha256": "A" * 64,
            "core_loaded_sha256": hashes["cad/scripts/stock_form_cutter.py"],
            "calculation_arguments": {"source_inputs_only": False, "nominal_engineering_only": False, "six_pitch_thickness_mm": 1.05},
            "all_source_pose_inputs": {str(row["teeth"]): {"geometry": row["geometry"], "domain": row["continuous_source_domain"]} for row in rows},
        },
    }
    return payload


@pytest.fixture
def packet(packet_template: dict, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict:
    payload = deepcopy(packet_template)
    sources = spec._relative_sources(payload["source_identity"]["actual_preimport_project_sha256"], "synthetic fixture")
    pure = {path: sha for path, sha in sources.items() if not path.startswith("cad/scripts/diagnostics/")}
    monkeypatch.setattr(spec, "_current_geometry_source_sha256",
                        lambda paths: {path: pure[path] for path in paths})
    monkeypatch.setattr(domain_supplier, "continuous_source_domain", _source_domain)
    monkeypatch.setattr(domain_supplier, "nominal_placement_record", _placement)
    path = tmp_path / "dt-cone-stock-form.json"
    monkeypatch.setattr(spec, "STOCK_FORM_PACKET_PATH", path)
    path.write_text(json.dumps(payload, allow_nan=False), encoding="utf-8")
    spec._qualified_members.cache_clear()
    yield payload
    spec._qualified_members.cache_clear()


def test_real_native_profile_can_precede_native_observation(packet: dict) -> None:
    assert domain_supplier.require_qualified_stock_family(packet)["native_certificate"] is False
    for teeth in spec.CONFIGURATION_TEETH:
        row = packet["rows"][spec.CONFIGURATION_TEETH.index(teeth)]
        selected = row["selected"]
        actual = spec.stock_form_profile(teeth)
        expected = StockFormProfile(teeth, spec.cutter_template(teeth), selected["outside_dia_mm"] / 2.0, selected["tool_translation_mm"])
        assert actual == expected
        assert spec.outside_dia_mm(teeth) == selected["outside_dia_mm"]
        assert spec.tooth_thickness_mm(teeth) == pytest.approx(selected["pitch_thickness_mm"], abs=1e-9)
        assert spec.floor_radius_min_mm(teeth) == actual.root_radius_min_mm
        assert spec.floor_radius_max_mm(teeth) == actual.root_radius_max_mm
        assert len(spec.manufacturing_corner_profiles(teeth)) == 4
    assert spec.stock_form_profile(6).template.name == "DT6-FORM1"
    assert spec.stock_form_profile(6).template.pitch_tooth_thickness_mm == 1.05
    assert spec.stock_form_profile(120).template.reference_teeth == 55


def test_actual_inspection_and_notes_have_no_planar_or_ideal_fallback(packet: dict) -> None:
    for teeth in spec.CONFIGURATION_TEETH:
        corners = spec.manufacturing_corner_profiles(teeth)
        low, high = spec.floor_limits_mm(teeth)
        assert low <= 2 * min(p.root_radius_min_mm for p in corners)
        assert high >= 2 * max(p.root_radius_max_mm for p in corners)
        data = domain_supplier.stock_form_mesh_data(teeth)
        assert data["coverage_min"] == pytest.approx(1.15)
        cases = packet["rows"][spec.CONFIGURATION_TEETH.index(teeth)]["candidates"][0]["actual_profile_cases"]
        expected_te = max(
            abs(endpoint)
            for case in cases
            for read in case["calculation"]["all_corner_actual3d"]["actual_read_phases"]
            for endpoint in read["signed_running_te_interval_rad"]
        )
        assert data["te_bound_rad"] == expected_te
        assert data["native_certificate"] is False
        text = notes.gear_data(teeth)
        assert "ACTUAL 3D STOCK-FORM COVERAGE" in text
        assert "PLANAR" not in text and "CONTACT RATIO" not in text
        whole_depth = math.ceil(max(
            p.blank_radius_mm - p.root_radius_min_mm for p in corners
        ) * 1e4) / 1e4
        assert f"WHOLE DEPTH MAX / ROOT ARC R (mm, REF):  {whole_depth:.4f}" in text
    for retired in (
        "DEEPENED_MESH_MM", "CONTACT_RATIO_EXCEPTION_TEETH", "DIPPED_FLOOR_MIN_MM",
        "FLOOR_MAX_DIA_MM", "GAP_FLOOR_TMIN", "floor_tmin", "floor_dip_mm",
        "chord_floor_radius_mm", "floor_radius_mm", "OUTSIDE_DIA", "TOOTH_THICKNESS",
        "BORE_BAND_WEB_UPPER",
    ):
        assert not hasattr(spec, retired), retired


def test_missing_packet_refuses_every_native_reader_without_blocking_inputs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(spec, "STOCK_FORM_PACKET_PATH", tmp_path / "absent.json")
    assert len(spec.geometry_inputs()["members"]) == 20
    for reader in (
        spec.stock_form_profile, spec.manufacturing_corner_profiles, domain_supplier.stock_form_mesh_data,
        spec.outside_dia_mm, spec.tooth_thickness_mm, spec.floor_radius_min_mm,
        spec.floor_radius_max_mm, spec.floor_limits_mm, notes.gear_data,
        spec.stock_form_reference_data,
    ):
        with pytest.raises(ValueError, match="qualification is missing"):
            reader(6)


@pytest.mark.parametrize("count", [True, 6.0, 0, 7, 126])
def test_nonphysical_member_is_rejected_before_packet_read(count: object, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(spec, "STOCK_FORM_PACKET_PATH", tmp_path / "absent.json")
    with pytest.raises(ValueError, match="unsupported"):
        spec.stock_form_profile(count)


def test_source_only_stationary_or_unstable_records_never_build(packet: dict) -> None:
    for key in ("source_inputs_only", "nominal_engineering_only"):
        changed = deepcopy(packet)
        changed[key] = True
        with pytest.raises(ValueError):
            domain_supplier.require_qualified_stock_family(changed)
    changed = deepcopy(packet)
    changed["source_identity"]["source_bytes_stable"] = False
    with pytest.raises(ValueError, match="changed"):
        domain_supplier.require_qualified_stock_family(changed)
    changed = deepcopy(packet)
    changed["qualified"] = False
    with pytest.raises(ValueError, match="unqualified"):
        domain_supplier.require_qualified_stock_family(changed)


def test_incomplete_wrong_count_and_selected_geometry_are_refused(packet: dict) -> None:
    for changed_rows in (packet["rows"][:-1], packet["rows"][:-1] + [deepcopy(packet["rows"][0])]):
        changed = deepcopy(packet)
        changed["rows"] = changed_rows
        with pytest.raises(ValueError, match="ALL20|count"):
            domain_supplier.require_qualified_stock_family(changed)
    changed = deepcopy(packet)
    changed["rows"][0]["selected"]["tool_translation_mm"] += 0.001
    changed["selected_geometry_sha256"] = spec.geometry_sha256(spec.selected_geometry_record(changed["rows"]))
    with pytest.raises(ValueError, match="translation"):
        domain_supplier.require_qualified_stock_family(changed)
    changed = deepcopy(packet)
    changed["rows"][0]["printed_profile_root_envelope_mm"][0] += 0.001
    changed["selected_geometry_sha256"] = spec.geometry_sha256(spec.selected_geometry_record(changed["rows"]))
    with pytest.raises(ValueError, match="root MIN"):
        domain_supplier.require_qualified_stock_family(changed)
    changed = deepcopy(packet)
    changed["rows"][0]["selected"]["outside_dia_mm"] = 1000.0
    changed["selected_geometry_sha256"] = spec.geometry_sha256(spec.selected_geometry_record(changed["rows"]))
    with pytest.raises(ValueError, match="FINITE cutter support"):
        domain_supplier.require_qualified_stock_family(changed)


def test_source_manifest_cannot_be_missing_changed_or_ambiguously_relocated(packet: dict) -> None:
    changed = deepcopy(packet)
    changed["measurement_engine_sources_sha256"].pop("stock_form_contact_continuation.py")
    with pytest.raises(ValueError, match="SIX"):
        domain_supplier.require_qualified_stock_family(changed)
    changed = deepcopy(packet)
    path = next(iter(changed["source_identity"]["actual_preimport_project_sha256"]))
    changed["source_identity"]["actual_preimport_project_sha256"][path] = "B" * 64
    with pytest.raises(ValueError, match="compiled|measurement"):
        domain_supplier.require_qualified_stock_family(changed)
    changed = deepcopy(packet)
    before = changed["source_identity"]["before_design_sha256"]
    path, sha = next(iter(before.items()))
    before[f"Q:/another-root/{path.split('/isolated-factory-fixture/')[1]}"] = sha
    with pytest.raises(ValueError, match="ambiguous"):
        domain_supplier.require_qualified_stock_family(changed)


def test_input_and_output_hashes_are_separate_and_stale_inputs_refuse(packet: dict) -> None:
    changed = deepcopy(packet)
    changed["geometry_inputs"]["face_width_mm"] += 0.001
    changed["geometry_inputs_sha256"] = spec.geometry_sha256(changed["geometry_inputs"])
    with pytest.raises(ValueError, match="inputs"):
        domain_supplier.require_qualified_stock_family(changed)
    changed = deepcopy(packet)
    changed["selected_geometry_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="OUTPUT"):
        domain_supplier.require_qualified_stock_family(changed)
    assert spec.geometry_sha256(spec.geometry_inputs()) == packet["geometry_inputs_sha256"]
    assert "selected" not in json.dumps(spec.geometry_inputs())
    changed = deepcopy(packet)
    changed["rows"][0]["cutter"]["source"] = "changed tool-source wording only"
    assert spec.geometry_sha256(spec.selected_geometry_record(changed["rows"])) == packet["selected_geometry_sha256"]


@pytest.mark.parametrize("defect", ["missing_case", "duplicate_case", "wrong_corner", "stationary_case", "cam", "union", "gap", "handover", "reads", "tare", "root_outer", "root_carrying", "period_gap", "continuation"])
def test_full_actual_evidence_refuses_discriminating_defects(packet: dict, defect: str) -> None:
    changed = deepcopy(packet)
    selected = changed["rows"][0]["candidates"][0]
    cases = selected["actual_profile_cases"]
    report = cases[1]["calculation"]
    if defect == "missing_case":
        cases.pop()
    elif defect == "duplicate_case":
        cases[-1] = deepcopy(cases[1])
    elif defect == "wrong_corner":
        cases[1]["cone"]["blank_radius_mm"] += 0.01
    elif defect == "stationary_case":
        cases[1]["actual_source_nominal_pose"] = True
    elif defect == "cam":
        selected["integral_cam_body_exclusion"]["qualified"] = False
    elif defect == "union":
        report["all_corner_actual3d"]["stock_form_coverage_lower"] = 1.099
    elif defect == "gap":
        report["all_corner_actual3d"]["uncovered_phase_rad"] = 0.000001
    elif defect == "handover":
        report["all_corner_actual3d"]["handovers"][0]["pitch_displacement_jump_upper_mm"] = 0.005001
    elif defect == "reads":
        report["signed_read_matrix"]["rows"].pop()
    elif defect == "tare":
        report["signed_read_matrix"]["datum"] = "mean/home tared"
    elif defect == "root_outer":
        report["full_period_cells"][0]["root_air"]["driver_root_proof"]["root_sweep"]["free_inner"] = []
    elif defect == "root_carrying":
        report["full_period_cells"][0]["root_air"]["root_is_carrying"] = True
    elif defect == "period_gap":
        report["full_period_cells"][0]["actual_driver_interval_rad"][0] = 0.000001
    else:
        report["all_corner_actual3d"].pop("continuous_contact_certificate")
    with pytest.raises(ValueError):
        domain_supplier.require_qualified_stock_family(changed)


def test_duplicate_json_keys_and_nonfinite_fields_refuse(packet: dict) -> None:
    spec.STOCK_FORM_PACKET_PATH.write_text('{"qualified":true,"qualified":false}', encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate"):
        spec.stock_form_profile(6)
    changed = deepcopy(packet)
    changed["rows"][0]["selected"]["outside_dia_mm"] = math.nan
    with pytest.raises(ValueError):
        domain_supplier.require_qualified_stock_family(changed)


@pytest.mark.parametrize("field", ["continuous_source_domain", "placement"])
def test_contact_report_is_bound_to_independent_source_supplier(packet: dict, field: str) -> None:
    changed = deepcopy(packet)
    robust = changed["rows"][0]["candidates"][0]["actual_profile_cases"][1]["calculation"]["all_corner_actual3d"]
    if field == "placement":
        robust[field]["driver_origin_mm"][0] += .001
    else:
        robust[field]["correlated_pose_parameters"][0][1][1] *= .5
    with pytest.raises(ValueError, match="SOURCE"):
        domain_supplier.require_qualified_stock_family(changed)


def test_unknown_receiving_grade_is_not_replaced_with_zero(
    packet: dict, monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unknown(_teeth: int) -> dict:
        raise _fit_limits.SourceDomainUnknown("synthetic receiving grade is UNKNOWN")

    monkeypatch.setattr(domain_supplier, "continuous_source_domain", unknown)
    with pytest.raises(ValueError, match="UNKNOWN"):
        domain_supplier.require_qualified_stock_family(packet)


@pytest.mark.parametrize("subsystem, field, part_local", [
    ("gear_train", "diametral_pitch", True),
    ("channels", "station_z0_mm", False),
])
def test_actual_config_changes_refuse_current_source_without_rekeying_world_parts(
    packet: dict, monkeypatch: pytest.MonkeyPatch, subsystem: str, field: str,
    part_local: bool,
) -> None:
    changed = deepcopy(packet)
    original = spec._config.machine
    reads = changed["source_identity"]["actual_config_value_reads"]
    reads[f"machine:{subsystem}/{field}"] = original(subsystem, field)
    changed["source_identity"]["geometric_config_value_sha256"] = spec.geometry_sha256(reads)
    spec.STOCK_FORM_PACKET_PATH.write_text(json.dumps(changed), encoding="utf-8")
    domain_supplier.require_qualified_stock_family(changed)

    def current(*keys):
        value = original(*keys)
        return value + .001 if keys == (subsystem, field) else value

    monkeypatch.setattr(spec._config, "machine", current)
    if part_local:
        with pytest.raises(ValueError, match="part-local config"):
            spec.require_stock_geometry_family(changed)
    else:
        spec.require_stock_geometry_family(changed)
        reference = spec.stock_form_reference_data(6)
        assert reference["qualification"] == "geometry-qualified-reference"
        assert "robust_half_width_rad" not in reference
    with pytest.raises(ValueError, match="config reads"):
        domain_supplier.require_qualified_stock_family(changed)
    with pytest.raises(ValueError, match="config reads"):
        domain_supplier.stock_form_mesh_data(6)


@pytest.mark.parametrize("path", [
    "cad/scripts/dt_cone_support_pose.py",
    "cad/scripts/dt_cone_mesh_domain.py",
    "cad/scripts/cone_line.py",
])
def test_world_source_bytes_refuse_full_api_even_after_geometry_cache(
    packet: dict, monkeypatch: pytest.MonkeyPatch, path: str,
) -> None:
    domain_supplier.require_qualified_stock_family(packet)
    original = spec._current_geometry_source_sha256

    def current(paths):
        values = original(paths)
        if path in values:
            values[path] = "0" * 64
        return values

    monkeypatch.setattr(spec, "_current_geometry_source_sha256", current)
    spec.require_stock_geometry_family(packet)
    with pytest.raises(ValueError, match="full physical source identity is stale"):
        domain_supplier.require_qualified_stock_family(packet)
    with pytest.raises(ValueError, match="full physical source identity is stale"):
        domain_supplier.stock_form_mesh_data(6)


def test_current_world_placement_refuses_full_api_not_recorded_part_reference(
    packet: dict, monkeypatch: pytest.MonkeyPatch,
) -> None:
    domain_supplier.require_qualified_stock_family(packet)

    def moved(teeth):
        placement = _placement(teeth)
        placement["driver_origin_mm"][2] += .001
        return placement

    monkeypatch.setattr(domain_supplier, "nominal_placement_record", moved)
    spec.require_stock_geometry_family(packet)
    with pytest.raises(ValueError, match="actual SOURCE placement"):
        domain_supplier.require_qualified_stock_family(packet)
    with pytest.raises(ValueError, match="actual SOURCE placement"):
        domain_supplier.stock_form_mesh_data(6)



@pytest.mark.parametrize("scope, required", [
    ("DESIGN_CONDITIONAL_SOURCE_DOMAIN", False),
    ("DESIGN_NOMINAL_SUBDOMAIN", False),
    ("BUDGET_CLOCK_NOMINAL_SUBDOMAIN", False),
    ("FULL_PRODUCTION_SOURCE_DOMAIN", False),
    ("FULL_PRODUCTION_SOURCE_DOMAIN", 1),
])
def test_mathematical_or_conditional_domain_cannot_be_promoted_to_native_source(
    packet: dict, monkeypatch: pytest.MonkeyPatch, scope: str, required: object,
) -> None:
    def conditional(teeth: int) -> dict:
        domain = _source_domain(teeth)
        domain["scope"] = scope
        domain["production_source_domain"] = required
        return domain

    monkeypatch.setattr(domain_supplier, "continuous_source_domain", conditional)
    with pytest.raises(ValueError, match="unconditional production SOURCE"):
        domain_supplier.require_qualified_stock_family(packet)


@pytest.mark.parametrize("defect", [
    "one_direction", "wrong_direction", "source_narrowing", "missing_patch",
    "root_carrier", "zero_shaft_moment", "outer_only_root", "native_root_flag",
    "status_only_seam", "unpaid_joint_arc", "hidden_handover_competitor",
    "missing_directed_material", "wrong_material_owner", "surface_only_material",
    "wrong_material_scope", "missing_material_cap", "unpaid_directed_root_floor",
    "missing_fresh_boundary", "wrong_boundary_phase", "wrong_boundary_stratum",
])
def test_actual_continuity_receipts_cannot_be_status_or_surface_summaries(
    packet: dict, defect: str,
) -> None:
    changed = deepcopy(packet)
    report = changed["rows"][0]["candidates"][0]["actual_profile_cases"][1]["calculation"]
    certificate = report["all_corner_actual3d"]["continuous_contact_certificate"]
    lower = certificate["sides"]["lower"]
    cell = lower["phase_cells"][0]
    branch = cell["branch_proofs"][0]
    if defect == "one_direction":
        certificate["sides"].pop("upper")
    elif defect == "wrong_direction":
        lower["closing_driven_sense"] = 1
    elif defect == "source_narrowing":
        next(iter(branch["same_source_pose"].values()))[1] *= .5
    elif defect == "missing_patch":
        cell["first_contact_cover"]["physical_patch_inventory"].pop()
    elif defect == "root_carrier":
        branch["physical_strata"]["driver"]["kind"] = "root_arc"
    elif defect == "zero_shaft_moment":
        branch["common_normal_moments"][0] = [0.0, 0.0]
    elif defect == "outer_only_root":
        cell["root_proof"]["root_sweep"]["free_inner"] = []
    elif defect == "native_root_flag":
        cell["root_proof"]["root_sweep"]["native_solid_certificate"] = True
    elif defect == "status_only_seam":
        lower["periodic_seam"] = {"status": "PROVED", "continuous": True, "native_certificate": False}
    elif defect == "unpaid_joint_arc":
        lower["periodic_seam"]["root_proof"]["additional_geometry_error_mm"] = 0.0
    elif defect == "hidden_handover_competitor":
        lower["handovers"][0]["full_cell_competitor_exclusions"] = []
    elif defect == "missing_directed_material":
        cell.pop("driven_root_material_proof")
    elif defect == "wrong_material_owner":
        cell["driven_root_material_proof"]["root_owner"] = "driver"
    elif defect == "surface_only_material":
        cell["driven_root_material_proof"] = deepcopy(cell["first_contact_cover"])
    elif defect == "wrong_material_scope":
        cell["driven_root_material_proof"]["material_sweep"]["material_scope"] = "root surface only"
    elif defect == "missing_material_cap":
        material = cell["driven_root_material_proof"]["material_sweep"]
        material["physical_patch_inventory"].remove(next(
            patch for patch in material["physical_patch_inventory"] if ":end_face:" in patch
        ))
    elif defect == "unpaid_directed_root_floor":
        cell["driven_root_material_proof"]["root_air_lower_mm"] = .099999
    elif defect == "missing_fresh_boundary":
        lower["boundary_continuations"].pop()
    elif defect == "wrong_boundary_phase":
        lower["boundary_continuations"][0]["phase_rad"] += 1e-5
    elif defect == "wrong_boundary_stratum":
        lower["boundary_continuations"][0]["right_branch_proof"]["physical_strata"]["driver"]["tooth"] = 1
    with pytest.raises(ValueError):
        domain_supplier.require_qualified_stock_family(changed)


@pytest.mark.parametrize("defect", [
    "missing_stock_phase", "missing_whole_period", "read_count", "read_order",
    "nonfinite_reference", "wrong_advance_sign", "unpaid_reference",
    "narrow_nominal_domain", "envelope_omits_reference",
    "wrong_schema", "saved_cad_state", "tare", "crank_already_included",
    "missing_q0_receipt", "source_self_narrowing", "midpoint_instead_of_root",
    "aggregate_without_actual_profile_te", "hidden_case_period_gap",
    "unproved_q0_source", "legacy_q0_admission", "unqualified_production_source",
    "periodic_point_substitution", "not_direct_query", "actual_phase_order",
    "legacy_read_endpoint_alias",
])
def test_operating_3d_stock_reference_refuses_missing_or_unpaid_data(packet: dict, defect: str) -> None:
    changed = deepcopy(packet)
    selected = changed["rows"][0]["candidates"][0]
    record = selected["stock_phase_3d"]
    if defect == "missing_stock_phase":
        selected.pop("stock_phase_3d")
    elif defect == "missing_whole_period":
        record.pop("robust_signed_te_interval_rad")
    elif defect == "read_count":
        record["nominal_signed_running_te_rad"].pop()
    elif defect == "read_order":
        record["driver_read_phases_rad"][1] = math.pi
    elif defect == "nonfinite_reference":
        record["nominal_signed_running_te_rad"][0] = math.nan
    elif defect == "wrong_advance_sign":
        record["nominal_driven_advance_rad"][1] *= -1
    elif defect == "unpaid_reference":
        record["nominal_reference_numerical_bound_rad"][0] *= .5
    elif defect == "narrow_nominal_domain":
        record["nominal_pose_half_width_rad"][0] *= .5
    elif defect == "envelope_omits_reference":
        record["nominal_pose_signed_te_interval_rad"] = [.001, .002]
    elif defect == "wrong_schema":
        record["schema"] = "old-planar-stock-phase"
    elif defect == "saved_cad_state":
        record["operating_source_state"] = "RAW_SAVED_CAD"
    elif defect == "tare":
        record["datum_tare_rad"] = 0.0
    elif defect == "crank_already_included":
        record["shaft_advance_included"] = True
    elif defect == "missing_q0_receipt":
        selected["actual_profile_cases"][1]["calculation"].pop("nominal_actual3d")
    elif defect == "source_self_narrowing":
        actual = selected["actual_profile_cases"][1]["calculation"]["budget_actual3d"]
        actual["continuous_contact_certificate"]["same_source_pose"]["driver_ecc_x_mm"][1] *= .5
    elif defect == "midpoint_instead_of_root":
        selected["actual_profile_cases"][0]["calculation"]["nominal_actual3d"]["actual_read_phases"][0].pop("reference_signed_running_te_rad")
    elif defect == "aggregate_without_actual_profile_te":
        record["robust_half_width_rad"][0] *= .5
    elif defect == "hidden_case_period_gap":
        selected["actual_profile_cases"][1]["calculation"]["budget_actual3d"]["full_period_cells"].pop()
    elif defect == "unproved_q0_source":
        selected["actual_profile_cases"][1]["calculation"]["nominal_actual3d"]["source_domain_proved"] = False
    elif defect == "legacy_q0_admission":
        actual = selected["actual_profile_cases"][1]["calculation"]["nominal_actual3d"]
        actual.pop("source_domain_proved")
        actual["qualified"] = True
        actual["certificate_admitted"] = True
    elif defect == "unqualified_production_source":
        selected["actual_profile_cases"][1]["calculation"]["all_corner_actual3d"]["production_source_qualified"] = False
    elif defect in {"periodic_point_substitution", "not_direct_query", "actual_phase_order", "legacy_read_endpoint_alias"}:
        actual = selected["actual_profile_cases"][1]["calculation"]["budget_actual3d"]
        if defect == "legacy_read_endpoint_alias":
            actual["read_endpoints"] = actual.pop("actual_read_phases")
        elif defect == "periodic_point_substitution":
            actual["actual_read_phases"][0]["periodic_point_substitution"] = True
        elif defect == "not_direct_query":
            actual["actual_read_phases"][0]["direct_actual_phase_query"] = False
        else:
            actual["actual_read_phases"][1]["actual_driver_phase_rad"] = math.pi
    if "stock_phase_3d" in selected:
        # Keep the real producer's mirrored row coherent so this test reaches
        # the named SOURCE/geometry/payment defect, not an unrelated alias.
        changed["rows"][0]["stock_phase_3d"] = deepcopy(record)
    with pytest.raises(ValueError):
        domain_supplier.require_qualified_stock_family(changed)


def test_operating_3d_stock_reference_is_immutable_and_exposes_no_planar_clock(packet: dict) -> None:
    data = domain_supplier.stock_form_mesh_data(6)
    record = packet["rows"][0]["candidates"][0]["stock_phase_3d"]
    for name in (
        "driver_read_phases_rad", "nominal_driven_advance_rad",
        "nominal_signed_running_te_rad", "nominal_reference_numerical_bound_rad",
        "robust_half_width_rad", "nominal_pose_half_width_rad",
        "robust_signed_te_interval_rad", "nominal_pose_signed_te_interval_rad",
    ):
        assert data[name] == tuple(record[name])
    assert "home_gap_clocking_rad" not in data
    assert "home_clocking_rad" not in data


@pytest.mark.parametrize("defect", [
    "point_reference_root", "point_reference_source", "point_reference_error",
    "point_reference_chart", "point_missing_reverse", "point_missing_material",
    "point_missing_surface_cap", "point_missing_free_reference",
    "point_unpaid_surface_period", "point_zero_terminal_stats",
    "point_outer_only_exclusion", "point_wrong_approach",
    "period_uncorrelated_backlash", "period_double_geometry",
    "whole_period_unpaid_hull", "whole_period_status_only_scope",
])
def test_canonical_point_and_period_receipts_refuse_actual_geometry_payment_defects(
    packet: dict, defect: str,
) -> None:
    changed = deepcopy(packet)
    actual = changed["rows"][0]["candidates"][0]["actual_profile_cases"][1]["calculation"]["budget_actual3d"]
    read = actual["actual_read_phases"][1]
    cell = read["direct_first_contact_sides"]["lower"]
    if defect == "point_reference_root":
        read["reference_common_normal_point"][-1] += .001
    elif defect == "point_reference_source":
        read["reference_source_pose"]["driver_clock_rad"] = [.001, .001]
    elif defect == "point_reference_error":
        read["reference_error_bound_rad"] = 0.0
    elif defect == "point_reference_chart":
        read["reference_chart"] = "nonexistent-physical-root"
    elif defect == "point_missing_reverse":
        read["direct_first_contact_sides"].pop("upper")
    elif defect == "point_missing_material":
        read.pop("finite_face_material_enclosure")
    elif defect == "point_missing_surface_cap":
        cell["surface_exclusion_receipts"] = [
            row for row in cell["surface_exclusion_receipts"]
            if ":end_face:" not in row["patch_id"]
        ]
    elif defect == "point_missing_free_reference":
        cell["free_reference_exclusion_receipts"] = []
    elif defect == "point_unpaid_surface_period":
        cell["surface_exclusion_receipts"][0]["additional_geometry_error_mm"] = 0.0
    elif defect == "point_zero_terminal_stats":
        cell["free_reference_exclusion_receipts"][0]["terminal_boxes"] = 0
    elif defect == "point_outer_only_exclusion":
        cell["surface_exclusion_receipts"][0]["free_inner_inverse_offset_components_rad"] = []
    elif defect == "point_wrong_approach":
        cell["surface_exclusion_receipts"][0]["approach_driven_phase_rad"] = [0.0, 0.0]
    elif defect == "period_uncorrelated_backlash":
        actual["full_period_cells"][0]["correlated_backlash"]["branch_pairs"] = []
    elif defect == "period_double_geometry":
        actual["full_period_cells"][0]["side_branch_envelopes"]["lower"][0]["total_geometric_payment_rad"] *= 2.0
    elif defect == "whole_period_unpaid_hull":
        actual["whole_period_signed_running_te_interval_rad"][0] += .001
    else:
        actual["continuous_contact_certificate"]["whole_period_signed_running_te_scope"] = {"status": "PROVED"}
    with pytest.raises(ValueError):
        domain_supplier.require_qualified_stock_family(changed)
