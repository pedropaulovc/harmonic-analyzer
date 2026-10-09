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
from importlib.machinery import SourceFileLoader
import json
from pathlib import Path
import pprint
import sys

# As in the oblique DESIGN collector, the entry and project imports execute
# the exact captured bytes, never a timestamp-only cached .pyc substitution.
if __name__ == "__main__" and "_ENTRY_SOURCE_SHA256" not in globals():
    _entry_path = Path(__file__).resolve()
    _entry_payload = _entry_path.read_bytes()
    _ENTRY_SOURCE_SHA256: str = hashlib.sha256(_entry_payload).hexdigest()
    exec(compile(_entry_payload, str(_entry_path), "exec", dont_inherit=True), globals())
    raise RuntimeError("captured alignment entry returned without completing main")

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
REPO = SCRIPTS.parents[1]
_COMPILED_PROJECT_SHA = {}
_PARSED_CONFIG_SHA = {}
_ORIGINAL_GET_CODE = SourceFileLoader.get_code


def _capture_bytes(manifest: dict[str, str], path: Path, payload: bytes) -> None:
    key = path.resolve().relative_to(REPO).as_posix()
    digest = hashlib.sha256(payload).hexdigest()
    if manifest.setdefault(key, digest) != digest:
        raise RuntimeError(f"alignment source changed across loads: {key}")


def _captured_project_code(loader, fullname):
    path = Path(loader.path).resolve()
    if not path.is_relative_to(SCRIPTS) or path.suffix != ".py":
        return _ORIGINAL_GET_CODE(loader, fullname)
    payload = path.read_bytes()
    _capture_bytes(_COMPILED_PROJECT_SHA, path, payload)
    return compile(payload, str(path), "exec", dont_inherit=True)


if __name__ == "__main__":
    _COMPILED_PROJECT_SHA[Path(__file__).resolve().relative_to(REPO).as_posix()] = (
        _ENTRY_SOURCE_SHA256
    )
    SourceFileLoader.get_code = _captured_project_code

import _config


def _captured_config_load(path):
    path = Path(path).resolve()
    payload = path.read_bytes()
    _capture_bytes(_PARSED_CONFIG_SHA, path, payload)
    return _config.yaml.safe_load(payload.decode("utf-8")) or {}


if __name__ == "__main__":
    if _config._doc.cache_info().currsize or _config._parts_registry.cache_info().currsize:
        raise RuntimeError("alignment source capture requires a fresh CLI process")
    _config._load = _captured_config_load


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
    if __name__ != "__main__" or "_ENTRY_SOURCE_SHA256" not in globals():
        raise RuntimeError("authentic alignment qualification requires the captured CLI entry")
    captured = {
        "actual_compiled_project_sha256": dict(_COMPILED_PROJECT_SHA),
        "actual_parsed_config_sha256": dict(_PARSED_CONFIG_SHA),
    }
    loaded = {**captured["actual_compiled_project_sha256"],
              **captured["actual_parsed_config_sha256"]}
    before = {
        path: hashlib.sha256((REPO / path).read_bytes()).hexdigest() for path in loaded
    }
    if before != loaded or any(before.get(path) != sha for path, sha in source_identity.items()):
        raise RuntimeError("alignment compiled/parsed source differs before DESIGN; no calculation launched")
    repo = SCRIPTS.parents[1]
    destination = full_report_dir.resolve()
    if destination.is_relative_to(repo):
        raise ValueError("full alignment reports must remain outside the repository")
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "source-basis.json").write_text(
        json.dumps({
            "state": "captured before DESIGN; after stability not yet observed",
            **captured,
            "before_design_sha256": before,
            "geometry": geometry,
            "geometry_sha256": qualification.geometry_sha256(geometry),
            "maximum_error_mm": maximum_error_mm,
            "qualified": False,
        }, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
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
    final_compiled = dict(_COMPILED_PROJECT_SHA)
    final_parsed = dict(_PARSED_CONFIG_SHA)
    after = {
        path: hashlib.sha256((REPO / path).read_bytes()).hexdigest()
        for path in final_compiled.keys() | final_parsed.keys()
    }
    stable = (
        before == after
        and captured["actual_compiled_project_sha256"] == _COMPILED_PROJECT_SHA
        and captured["actual_parsed_config_sha256"] == _PARSED_CONFIG_SHA
        and qualification.source_sha256() == source_identity
        and qualification.geometry_sha256() == qualification.geometry_sha256(geometry)
    )
    result = {
        "family": "alignment_fitup",
        "scope": "full actual-material tooth periods, native plus all printed corners, whole centre stack",
        "native_certificate": False,
        "qualified": stable and all(row["qualified"] for row in rows.values()),
        "maximum_error_mm": maximum_error_mm,
        "geometry": geometry,
        "geometry_sha256": qualification.geometry_sha256(geometry),
        "source_sha256": source_identity,
        "source_capture": {
            "entry_source_capture": "CLI recompiles exact captured entry bytes",
            "project_code_capture": "project imports compile exact captured bytes, bypassing .pyc",
            "actual_compiled_project_sha256": final_compiled,
            "actual_parsed_config_sha256": final_parsed,
            "before_design_sha256": before,
            "after_design_sha256": after,
            "source_bytes_stable": stable,
        },
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
