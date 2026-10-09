"""Pure reader for genuine frozen full-period alignment FIT-UP qualification.

No mesh engine or diagnostic collector is imported. Missing, stale, partial or
refused evidence cannot release the fit-up mesh. Native parts do not import
this reader; their cached source closure remains purely geometric.
"""
from __future__ import annotations

import hashlib
from importlib import import_module
import json
import math
from pathlib import Path
from typing import NamedTuple

import dt_alignment_pinion_spec as alignment
import dt_cylinder_gear_spec as cylinder
from stock_form_cutter import StockFormProfile

ROOT_AIR_MIN_MM = 0.20
HANDOVER_MAX_MM = 0.005
PROOF_KIND = "bounded_full_period_actual_material"
REVERSE_FLANK_PROOF = "exact_spur_reflection_of_full_physical_period"


class MeshCase(NamedTuple):
    name: str
    driver: StockFormProfile
    driven: StockFormProfile
    centre_distance_mm: float


def qualification_cases() -> tuple[MeshCase, ...]:
    pairs = [("native", alignment.STOCK_FORM, cylinder.STOCK_FORM)]
    pairs.extend(
        (f"profile_{driver_index}_{driven_index}", driver, driven)
        for driver_index, driver in enumerate(alignment.manufacturing_corner_profiles())
        for driven_index, driven in enumerate(cylinder.manufacturing_corner_profiles())
    )
    return tuple(
        MeshCase(
            f"{centre_name}/{pair_name}", driver, driven,
            alignment.ENGAGED_CENTER_DISTANCE_MM
            + side * alignment.ENGAGED_CENTER_RADIAL_STACK_MM,
        )
        for centre_name, side in (("closed", -1), ("nominal", 0), ("open", 1))
        for pair_name, driver, driven in pairs
    )


def profile_record(profile: StockFormProfile) -> dict:
    return {
        "teeth": profile.teeth,
        "reference_teeth": profile.template.reference_teeth,
        "diametral_pitch": profile.template.diametral_pitch,
        "pressure_angle_deg": profile.template.pressure_angle_deg,
        "blank_radius_mm": profile.blank_radius_mm,
        "radial_translation_mm": profile.radial_translation_mm,
        "helix_angle_deg": profile.helix_angle_deg,
    }


def geometry_record() -> dict:
    return {
        "tip_grade": alignment.OUTSIDE_DIA_BAND,
        "alignment_span_limits_mm": alignment.base_tangent_span_limits_mm(),
        "cylinder_plunge_limits_mm": cylinder.whole_depth_limits_mm(),
        "root_air_min_mm": ROOT_AIR_MIN_MM,
        "handover_max_mm": HANDOVER_MAX_MM,
        "cases": {
            case.name: {
                "driver": profile_record(case.driver),
                "driven": profile_record(case.driven),
                "centre_distance_mm": case.centre_distance_mm,
            }
            for case in qualification_cases()
        },
    }


def geometry_sha256(record: dict | None = None) -> str:
    encoded = json.dumps(
        geometry_record() if record is None else record,
        sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def source_sha256() -> dict[str, str]:
    scripts = Path(__file__).resolve().parent
    repo = scripts.parents[1]
    paths = (
        Path(__file__).resolve(),
        scripts / "diagnostics" / "alignment_mesh_study.py",
        scripts / "dt_alignment_pinion_spec.py",
        scripts / "dt_cylinder_gear_spec.py",
        scripts / "stock_form_cutter.py",
        scripts / "stock_form_mesh.py",
        scripts / "_config.py",
        scripts / "_fit_limits.py",
        scripts / "_printed_tolerance.py",
        scripts.parent / "config" / "tolerances.yaml",
        scripts.parent / "config" / "machine" / "alignment_pinion.yaml",
        scripts.parent / "config" / "machine" / "gear_train.yaml",
    )
    return {
        str(path.relative_to(repo)).replace("\\", "/"): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in paths
    }


def require_authentic_source_capture(payload: dict) -> None:
    """Pay actual compiled/parsed bytes, not merely unchanged files after import."""
    capture = payload.get("source_capture")
    if not isinstance(capture, dict) or capture.get("source_bytes_stable") is not True:
        raise ValueError("alignment actual compiled/parsed source capture is missing or changed")
    names = (
        "actual_compiled_project_sha256", "actual_parsed_config_sha256",
        "before_design_sha256", "after_design_sha256",
    )
    if any(not isinstance(capture.get(name), dict) or not capture[name] for name in names):
        raise ValueError("alignment before/compiled/parsed/after manifests are incomplete")
    compiled, parsed, before, after = (capture[name] for name in names)
    if compiled.keys() & parsed.keys():
        raise ValueError("alignment project and configuration capture scopes overlap")
    actual = {**compiled, **parsed}
    if before != actual or after != actual:
        raise ValueError("alignment compiled/parsed/before/after source bytes differ")
    if any(
        not isinstance(path, str) or not path.startswith("cad/scripts/") or not path.endswith(".py")
        for path in compiled
    ) or any(
        not isinstance(path, str) or not path.startswith("cad/config/") or not path.endswith(".yaml")
        for path in parsed
    ):
        raise ValueError("alignment captured source scope is invalid")
    required = source_sha256()
    if any(actual.get(path) != digest for path, digest in required.items()):
        raise ValueError("alignment capture omits a required live geometry/algorithm source")
    repo = Path(__file__).resolve().parents[2]
    for path, digest in actual.items():
        resolved = (repo / path).resolve()
        if not resolved.is_relative_to(repo) or resolved.relative_to(repo).as_posix() != path or (
            not isinstance(digest, str) or len(digest) != 64
            or any(char not in "0123456789abcdef" for char in digest)
        ):
            raise ValueError(f"alignment captured source path/digest is invalid: {path}")
        if not resolved.is_file() or hashlib.sha256(resolved.read_bytes()).hexdigest() != digest:
            raise ValueError(f"alignment actually loaded source identity is stale: {path}")


def qualification_failures(case: dict) -> tuple[str, ...]:
    """Recheck paid fit-up gates without solving or trusting a green flag."""
    errors = case["numerical_error_bounds"]
    required = {"root_air_mm", "backlash_mm", "handover_jump_mm", "uncovered_phase_rad"}
    if not required <= errors.keys() or any(
        not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0.0
        for value in errors.values()
    ):
        return ("invalid_numerical_enclosure",)
    failures = []
    if not math.isfinite(case["root_air_mm"]) or (
        case["root_air_mm"] - errors["root_air_mm"] <= ROOT_AIR_MIN_MM
    ):
        failures.append("root_air")
    if not math.isfinite(case["tight_backlash_mm"]) or (
        case["tight_backlash_mm"] - errors["backlash_mm"] <= 0.0
    ):
        failures.append("positive_backlash")
    if not math.isfinite(case["loose_backlash_mm"]) or (
        case["loose_backlash_mm"] < case["tight_backlash_mm"]
    ):
        failures.append("backlash_interval")
    if case["root_interference"]:
        failures.append("root_interference")
    if case["uncovered_phase_rad"] + errors["uncovered_phase_rad"] != 0.0 or (
        not case["qualified_continuous_contact"]
    ):
        failures.append("union_continuous_carrier")
    uncertain_support = case["support_uncertain_phase_rad"]
    unsupported_samples = case["unsupported_contact_samples_rad"]
    if not isinstance(uncertain_support, (int, float)) or (
        not math.isfinite(uncertain_support) or uncertain_support < 0.0
    ) or not isinstance(unsupported_samples, (tuple, list)) or any(
        not isinstance(phi, (int, float)) or not math.isfinite(phi)
        for phi in unsupported_samples
    ):
        failures.append("invalid_support_diagnostics")
    else:
        if uncertain_support != 0.0:
            failures.append("unresolved_support_enclosure")
        if unsupported_samples:
            failures.append("unsupported_sampled_carrier")
    if not math.isfinite(case["phase_reserve_min_rad"]) or case["phase_reserve_min_rad"] <= 0.0:
        failures.append("supported_branch_reserve")
    if not math.isfinite(case["handover_jump_mm"]) or (
        case["handover_jump_mm"] + errors["handover_jump_mm"] > HANDOVER_MAX_MM
    ):
        failures.append("handover")
    for name in ("smooth_flank_coverage_interval", "corner_inclusive_coverage_interval"):
        interval = case[name]
        if len(interval) != 2 or not all(math.isfinite(value) for value in interval) or (
            interval[0] > interval[1]
        ):
            failures.append(f"invalid_{name}")
    fraction = case["corner_carrying_phase_fraction"]
    if not math.isfinite(fraction) or not 0.0 <= fraction <= 1.0:
        failures.append("invalid_corner_fraction")
    if not case.get("both_flanks_qualified", False):
        failures.append("reverse_flank")
    return tuple(failures)


def require_qualified(payload: dict | None = None) -> dict:
    """Reject missing, stale, wrong-corner, incomplete or unqualified proof."""
    if payload is None:
        try:
            frozen = import_module("alignment_stock_mesh_calibration")
        except ModuleNotFoundError as exc:
            if exc.name != "alignment_stock_mesh_calibration":
                raise
            raise ValueError("alignment full-period calibration is missing; run the explicit collector") from exc
        payload = frozen.CALIBRATION
    if not isinstance(payload, dict) or not payload.get("qualified", False):
        raise ValueError("alignment full-period qualification is absent or refused")
    if not {"geometry", "geometry_sha256", "source_sha256", "cases"} <= payload.keys():
        raise ValueError("alignment full-period qualification is incomplete")
    if payload.get("family") != "alignment_fitup" or payload.get("native_certificate") is not False:
        raise ValueError("alignment fit-up proof is mislabelled")
    expected_geometry = geometry_record()
    if payload.get("geometry_sha256") != geometry_sha256(expected_geometry) or (
        geometry_sha256(payload["geometry"]) != geometry_sha256(expected_geometry)
    ):
        raise ValueError("alignment calibration geometry identity is stale")
    if payload.get("source_sha256") != source_sha256():
        raise ValueError("alignment calibration algorithm/source identity is stale")
    require_authentic_source_capture(payload)
    cases = payload["cases"]
    if not isinstance(cases, dict) or set(cases) != set(expected_geometry["cases"]):
        raise ValueError("alignment calibration lacks the exact whole booked corner family")
    for name, case in cases.items():
        required = {
            "proof_kind", "input", "phase_domain_rad", "phase_sample_count",
            "sampled_phase_limits_rad", "full_report_sha256", "numerical_error_bounds",
            "root_air_mm", "tight_backlash_mm", "loose_backlash_mm",
            "root_interference", "uncovered_phase_rad", "qualified_continuous_contact",
            "support_uncertain_phase_rad", "unsupported_contact_samples_rad",
            "phase_reserve_min_rad", "handover_jump_mm", "smooth_flank_coverage_interval",
            "corner_inclusive_coverage_interval", "corner_carrying_phase_fraction",
            "both_flanks_qualified", "reverse_flank_proof", "binding_constraints",
        }
        if not isinstance(case, dict) or not required <= case.keys():
            raise ValueError(f"{name}: full-period case evidence is incomplete")
        if case.get("proof_kind") != PROOF_KIND or case.get("input") != expected_geometry["cases"][name]:
            raise ValueError(f"{name}: wrong geometry or incomplete full-period proof")
        if case["reverse_flank_proof"] != REVERSE_FLANK_PROOF or any(
            case["input"][part]["helix_angle_deg"] != 0.0 for part in ("driver", "driven")
        ):
            raise ValueError(f"{name}: lower carrying direction lacks the exact spur reflection proof")
        driver_period = 2 * math.pi / case["input"]["driver"]["teeth"]
        if case.get("phase_domain_rad") != (0.0, driver_period):
            raise ValueError(f"{name}: proof does not span a whole tooth period")
        count = case["phase_sample_count"]
        first, last = case["sampled_phase_limits_rad"]
        if not isinstance(count, int) or count < 32 or not 0.0 < first < last < driver_period:
            raise ValueError(f"{name}: full-period adaptive proof witnesses are missing")
        digest = case.get("full_report_sha256", "")
        if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            raise ValueError(f"{name}: full report identity is missing")
        if not case.get("qualified", False) or case.get("binding_constraints") or qualification_failures(case):
            raise ValueError(f"{name}: actual fit-up carrying/backlash/air/handover is refused")
    return payload
