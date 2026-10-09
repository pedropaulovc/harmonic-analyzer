"""Actual16/64 crossed-mesh design cases and bounded3D report CLI.

Stock tooth geometry is source-owned; the shared contact engine accepts
explicit physical axes/faces/clocks and imports no machine specifications.
No ideal-N tooth facts, Tredgold contact ratio, old fitted sensitivities, or
native CAD imports are used. JSON output belongs outside the source tree.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, replace
import hashlib
import json
import math
from pathlib import Path
import time

import numpy as np

import crossed_mesh_study as cms
import crank_mesh_geometry as geometry
import crank_drive_phase
from crank_mesh_requirements import (
    HANDOVER_JUMP_MAX_MM, POSITIVE_BACKLASH_MIN_MM,
    ROW_ENGAGEMENT_MIN, STOCK_FORM_COVERAGE_MIN,
)
from stock_form_cutter import StockFormProfile
from stock_form_contact_3d import ContactPair, Placement, analyse_3d_mesh, loaded_driven_contact
from stock_form_root_angles import intersect_intervals


def measurement_engine_identity() -> dict:
    """Capture collector, adapters and actual geometric proof implementation."""
    root = Path(__file__).resolve().parent
    sources = {
        name:hashlib.sha256((root/name).read_bytes()).hexdigest()
        for name in (
            "crank_mesh_backlash_study.py","crossed_mesh_study.py",
            "stock_form_contact_3d.py","stock_form_root_angles.py",
            "stock_form_root_sweep.py","stock_form_contact_continuation.py",
        )
    }
    digest = hashlib.sha256(
        json.dumps(sources,sort_keys=True,separators=(",",":")).encode()
    ).hexdigest()
    return {"measurement_engine_sha256":digest,
            "measurement_engine_sources_sha256":sources}


def crank_pair(name: str, driver: StockFormProfile, driven: StockFormProfile,
               pose: cms.Placement | None = None) -> ContactPair:
    """Map the source physical crank pose to the general3D engine datum."""
    pose = cms.Placement() if pose is None else pose
    placement = Placement(**geometry.placement_record(asdict(pose)))
    return ContactPair(name,driver,driven,placement)


def design_cases(centre_shift_mm: float = 0.0) -> tuple[ContactPair, ...]:
    """Materialise the exact source-owned Cartesian manufacturing case set."""
    drivers = dict(cms.pinion_spec.STOCK_PROFILE_CORNERS,nominal=cms.pinion_spec.STOCK_PROFILE)
    driven = dict(cms.gear64_spec.STOCK_PROFILE_CORNERS,nominal=cms.gear64_spec.STOCK_PROFILE)
    rows = []
    for parameters in geometry.calibration_case_parameters():
        pose = cms.Placement(**parameters["pose"])
        if centre_shift_mm:
            pose = replace(pose,extra_mm=pose.extra_mm+centre_shift_mm)
        rows.append(crank_pair(parameters["name"],drivers[parameters["driver_profile_label"]],
                               driven[parameters["driven_profile_label"]],pose))
    return tuple(rows)


def json_safe(value):
    """Nonfinite geometric refusals are null, never nonstandard JSON numbers."""
    if isinstance(value,np.generic):
        return json_safe(value.item())
    if isinstance(value,float) and not math.isfinite(value):
        return None
    if isinstance(value,np.ndarray):
        return json_safe(value.tolist())
    if isinstance(value,dict):
        return {key:json_safe(item) for key,item in value.items()}
    if isinstance(value,(tuple,list)):
        return [json_safe(item) for item in value]
    return value


def analyse_case(
    case: ContactPair, pose_domain: dict, *, phases: int = 129,
    maximum_error_mm: float = 0.001,
) -> dict:
    """Measure one source case with its continuous, paid pose domain."""
    result = analyse_3d_mesh(
        case,phases=phases,maximum_error_mm=maximum_error_mm,
        coverage_min=STOCK_FORM_COVERAGE_MIN,row_min=ROW_ENGAGEMENT_MIN,
        handover_max_mm=HANDOVER_JUMP_MAX_MM,
        positive_backlash_min_mm=POSITIVE_BACKLASH_MIN_MM,driver_sense=1,
        radial_error_mm=pose_domain["radial_error_mm"],
        axial_error_mm=pose_domain["axial_error_mm"],
        required_root_air_mm=pose_domain["required_root_air_mm"],
    )
    result["pose_domain"] = pose_domain
    return result


def measure_read_stalls(
    nominal: ContactPair, phase_seed_rad: float, *, maximum_error_mm: float = 0.001,
) -> dict:
    """Directly root all21 physical read stalls; no periodicity substitution.

    World +Z crank is the explicit paper/platen +X convention. The cone
    runs about -U, so positive lag means actual-minus-ideal world cone angle.
    This raw study is not budget-qualified until the complete manufacturing
    family and its physical station/clock have also been frozen.
    """
    physical = replace(nominal,placement=replace(
        nominal.placement,
        driver_clocking_rad=nominal.placement.driver_clocking_rad-phase_seed_rad,
    ))
    observations = []
    for index in range(21):
        driver = 4*math.pi*index
        ideal = physical.placement.driven_clocking_rad-driver*physical.driver.teeth/physical.driven.teeth
        half_bracket = physical.driven.angular_pitch_rad/4
        observations.append(loaded_driven_contact(
            physical,driver,driver_sense=1,
            driven_bracket_rad=(ideal-half_bracket,ideal+half_bracket),
            maximum_error_mm=maximum_error_mm,
        ))
    return {
        "geometry_sha256":crank_drive_phase.geometry_sha256(),
        **measurement_engine_identity(),
        "qualified_for_budget":False,
        "qualification_requirement":"complete all-corner calibration and final physical clock/source identity",
        "operating_convention":"paper/platen world +X; crank world +Z; cone about -U",
        "CONE_SHAFT_SENSE":-1,
        "STALL_DRIVER_RAD":[row["driver_phase_rad"] for row in observations],
        "CONE_SHAFT_LAG_RAD":[row["driven_lag_rad"] for row in observations],
        "BOUND_RAD":[row["bound_rad"] for row in observations],
        "alignment_zero_subtracted":False,"native_certificate":False,
        "physical_placement":physical.placement.record(),"observations":observations,
    }


def calibration_payload(results: dict, identity: str, centre_shift_mm: float,
                        engine_identity: dict) -> dict:
    """Separate a complete design candidate from current-source publication."""
    complete = set(results) == geometry.required_calibration_case_names()
    pitch = geometry.pinion.STOCK_PROFILE.angular_pitch_rad
    common = ((-pitch/2,pitch/2),)
    for result in results.values():
        common = intersect_intervals(common,result.get("phase_components_rad",()))
    window = max(common,key=lambda interval:interval[1]-interval[0]) if common else None
    if window is not None:
        for result in results.values():
            result["phase_window_rad"] = next(
                list(interval) for interval in result["phase_components_rad"]
                if interval[0] <= window[0] < window[1] <= interval[1]
            )
    candidate = complete and all(result["qualified"] for result in results.values()) and window is not None
    qualified = candidate and centre_shift_mm == 0.0
    return {
        "qualified":qualified,"candidate_qualified":candidate,"geometry_sha256":identity,
        **engine_identity,
        "refusal":"" if qualified else "Actual complete source case family, common phase window and published physical station are not jointly qualified.",
        "method":"actual 3D finite stock boundary angular-envelope intersection",
        "native_certificate":False,"design_centre_shift_mm":centre_shift_mm,
        "phase_components_rad":common,
        "phase_window_rad":window,
        "phase_seed_deg":math.degrees(sum(window)/2) if window is not None and window[0] < window[1] else None,
        "required_case_names":sorted(geometry.required_calibration_case_names()),
        "cases":results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out",type=Path,required=True)
    parser.add_argument("--phases",type=int,default=129)
    parser.add_argument("--maximum-error-mm",type=float,default=0.001)
    parser.add_argument("--centre-shift-mm",type=float,default=0.0)
    parser.add_argument("--case",action="append")
    args = parser.parse_args()
    available = design_cases(args.centre_shift_mm)
    if args.case and not set(args.case) <= {case.name for case in available}:
        raise ValueError("a requested case is not in the source-owned manufacturing family")
    identity = crank_drive_phase.geometry_sha256()
    engine_identity = measurement_engine_identity()
    domains = geometry.calibration_case_domains()
    results = {}
    case_directory = args.out.with_suffix(".cases")
    case_directory.mkdir(parents=True,exist_ok=True)
    for index,case in enumerate(available):
        if args.case and case.name not in args.case:
            continue
        started = time.perf_counter()
        try:
            result = analyse_case(
                case,domains[case.name],phases=args.phases,maximum_error_mm=args.maximum_error_mm,
            )
        except (ValueError,RuntimeError) as exc:
            result = {"case":case.name,"qualified":False,"refusal":str(exc)}
        result["seconds"] = time.perf_counter()-started
        results[case.name] = json_safe(result)
        checkpoint = {"geometry_sha256":identity,**engine_identity,
                      "design_centre_shift_mm":args.centre_shift_mm,"result":results[case.name]}
        (case_directory/f"{index:04d}.json").write_text(
            json.dumps(checkpoint,separators=(",",":"),allow_nan=False)+"\n",encoding="utf-8")
        print(json.dumps({key:result.get(key) for key in (
            "case","qualified","refusal","seconds","tight_backlash_lower_mm",
            "stock_form_coverage_lower","row_available_fraction_lower",
        )}),flush=True)
    if not results:
        raise ValueError("no requested source-owned design case exists")
    payload = calibration_payload(results,identity,args.centre_shift_mm,engine_identity)
    args.out.write_text(json.dumps(payload,separators=(",",":"),allow_nan=False)+"\n",encoding="utf-8")
    return 0 if payload["qualified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
