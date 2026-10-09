"""Collect REAL full-period alignment FIT-UP qualification, explicitly.

Ordinary pytest reads the generated geometry/source-bound compact calibration;
it never runs these 51 expensive actual-material studies. Full reports stay
out of tree. No four-point probe, smooth span or authored drum clock is a
continuous-contact or readout-datum substitute::

    uv run python cad/scripts/diagnostics/alignment_mesh_study.py \
        --full-report-dir C:/src/dt-logs/alignment-full --maximum-error-mm 0.002

The numerical target is not an acceptance relaxation: all paid root-air,
positive-backlash, no-gap/reserve and 0.005 mm handover gates remain fixed.
"""
from __future__ import annotations

import argparse
from dataclasses import fields
import hashlib
import json
from pathlib import Path
import pprint
import sys

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import alignment_stock_mesh as qualification
from stock_form_mesh import MeshCertificationError, analyse_planar_mesh


def _compact_case(report, case, full_report_sha256: str) -> dict:
    """Summarize actual full-period evidence, not just sampled point contacts."""
    if case.driver.helix_angle_deg or case.driven.helix_angle_deg:
        raise ValueError("both-flank reflection proof requires genuinely spur profiles")
    summary = {
        "proof_kind": qualification.PROOF_KIND,
        # Canonical spur gaps, translated along X, mirror exactly in Y.
        # Reflection maps upper(phi) to lower(-phi) over a whole period;
        # clearance, support, root air, reserves and absolute jump are invariant.
        "reverse_flank_proof": qualification.REVERSE_FLANK_PROOF,
        "both_flanks_qualified": True,
        "input": {
            "driver": qualification.profile_record(case.driver),
            "driven": qualification.profile_record(case.driven),
            "centre_distance_mm": case.centre_distance_mm,
        },
        "phase_domain_rad": (0.0, report.driver_period_rad),
        "phase_sample_count": len(report.driver_phase_samples_rad),
        "sampled_phase_limits_rad": (
            report.driver_phase_samples_rad[0], report.driver_phase_samples_rad[-1]
        ),
        "full_report_sha256": full_report_sha256,
        "coverage_interval": report.coverage_interval,
        "smooth_flank_coverage_interval": report.smooth_flank_coverage_interval,
        "corner_inclusive_coverage_interval": report.corner_inclusive_coverage_interval,
        "corner_carrying_phase_fraction": report.corner_carrying_phase_fraction,
        "corner_normal_angle_range_rad": report.corner_normal_angle_range_rad,
        "root_air_mm": report.root_air_mm,
        "tight_backlash_mm": report.tight_backlash_mm,
        "loose_backlash_mm": report.loose_backlash_mm,
        "uncovered_phase_rad": report.uncovered_phase_rad,
        # Uncertified swept cells are not measured physical contact gaps.
        "support_uncertain_phase_rad": report.support_uncertain_phase_rad,
        "unsupported_contact_samples_rad": report.unsupported_contact_samples_rad,
        "qualified_continuous_contact": report.qualified_continuous_contact,
        "root_interference": report.root_interference,
        "handover_jump_mm": report.handover_jump_mm,
        "phase_reserve_min_rad": min(report.phase_reserves_rad),
        "handover_phase_reserves_rad": report.handover_phase_reserves_rad,
        "handover_kinds": report.handover_kinds,
        "numerical_error_bounds": report.numerical_error_bounds,
    }
    failures = qualification.qualification_failures(summary)
    summary.update(
        qualified=not failures,
        both_flanks_qualified=not failures,
        binding_constraints=failures,
    )
    return summary


def collect_qualification(full_report_dir: Path, maximum_error_mm: float) -> dict:
    geometry = qualification.geometry_record()
    source_identity = qualification.source_sha256()
    repo = SCRIPTS.parents[1]
    destination = full_report_dir.resolve()
    if destination.is_relative_to(repo):
        raise ValueError("full alignment reports must remain outside the repository")
    destination.mkdir(parents=True, exist_ok=True)
    rows = {}
    for case in qualification.qualification_cases():
        try:
            report = analyse_planar_mesh(
                case.driver, case.driven, case.centre_distance_mm,
                maximum_error_mm=maximum_error_mm,
            )
        except MeshCertificationError as exc:
            full = {"qualified": False, "binding_constraints": ("engine_refusal",),
                    "refusal": str(exc)}
            row = full.copy()
            encoded = (
                json.dumps(full, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
            ).encode("utf-8")
        else:
            # Do not recurse/deepcopy the private live engine object.
            full = {field.name: getattr(report, field.name)
                    for field in fields(report) if not field.name.startswith("_")}
            encoded = (
                json.dumps(full, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
            ).encode("utf-8")
            row = _compact_case(report, case, hashlib.sha256(encoded).hexdigest())
        (destination / f"{case.name.replace('/', '-')}.json").write_bytes(encoded)
        rows[case.name] = row
        print(json.dumps({"case": case.name, "qualified": row["qualified"],
                          "binding_constraints": row["binding_constraints"]}), flush=True)
    if qualification.source_sha256() != source_identity or (
        qualification.geometry_sha256() != qualification.geometry_sha256(geometry)
    ):
        raise RuntimeError("alignment qualification source/geometry changed during collection")
    result = {
        "family": "alignment_fitup",
        "scope": "full actual-material tooth periods, native plus all printed corners, whole centre stack",
        "native_certificate": False,
        "qualified": all(row["qualified"] for row in rows.values()),
        "maximum_error_mm": maximum_error_mm,
        "geometry": geometry,
        "geometry_sha256": qualification.geometry_sha256(geometry),
        "source_sha256": source_identity,
        "full_report_directory": str(destination),
        "cases": rows,
        "phase_scope": "drum fit-up diagnostics only; notches are set by eye, not by a drum index",
    }
    if result["qualified"]:
        qualification.require_qualified(result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--full-report-dir", type=Path, required=True)
    parser.add_argument("--maximum-error-mm", type=float, default=0.002)
    parser.add_argument("--calibration", type=Path, default=SCRIPTS / "alignment_stock_mesh_calibration.py")
    args = parser.parse_args()
    result = collect_qualification(args.full_report_dir, args.maximum_error_mm)
    args.calibration.write_text(
        '"""Actual full-period alignment fit-up design qualification; generated by alignment_mesh_study."""\n'
        + "CALIBRATION = " + pprint.pformat(result, sort_dicts=False, width=100) + "\n",
        encoding="utf-8",
    )
    return 0 if result["qualified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
