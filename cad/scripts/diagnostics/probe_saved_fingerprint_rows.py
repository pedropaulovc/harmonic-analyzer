"""Compare baseline/candidate fingerprint rows on one owned saved assembly.

Read-only native diagnostic: C/A/C order, no save, exact input hashes checked.
The first candidate read is cold: no preparatory rebuild hides save-boundary drift.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / "cad/scripts")]

import _assembly  # noqa: E402
import _telemetry  # noqa: E402
from _assembly_mass_properties import read_resolved_mass_properties  # noqa: E402
from diagnostics._owned_native_session import require_owned_diagnostic_environment, run_owned_diagnostic  # noqa: E402
from diagnostics.probe_assembly_health_targets import OwnedAssembly, checkpoint  # noqa: E402

BASELINE = "fd973ea2e6ebf8c35bbefa85b6648767de5bedd2"
CANDIDATE = "9a4944febdf26d0acad0578a480a746ad1c799a8"


def instrument(source, record):
    """Execute the exact function AST, observing only its hash input bytes."""
    nodes = [node for node in ast.parse(source).body if isinstance(node, ast.AsyncFunctionDef)
             and node.name == "assembly_geometry_digest"]
    if len(nodes) != 1:
        raise RuntimeError("expected exactly one fingerprint function")
    node = nodes[0]
    node.decorator_list = []

    class HashWitness:
        @staticmethod
        def sha256(value):
            record["hash_input"] = value.decode("utf-8")
            record["rows"] = ast.literal_eval(record["hash_input"])
            return hashlib.sha256(value)

    namespace = {**vars(_assembly), "hashlib": HashWitness,
                 "read_resolved_mass_properties": read_resolved_mass_properties}
    exec(compile(ast.Module(body=[node], type_ignores=[]), "<exact-fingerprint-ast>", "exec"), namespace)
    return namespace["assembly_geometry_digest"]


async def probe(adapter, assembly):
    directory = Path(tempfile.mkdtemp(prefix="saved-fingerprint-rows-", dir=ROOT / "cad/out/reports"))
    report_path = directory / "measurements.json"
    source = ROOT / f"cad/out/sldasm/{assembly}.SLDASM"
    old = subprocess.check_output(["git", "show", f"{BASELINE}:cad/scripts/_assembly.py"], cwd=ROOT, text=True)
    current = subprocess.check_output(["git", "show", f"{CANDIDATE}:cad/scripts/_assembly.py"], cwd=ROOT, text=True)
    report = {
        "status": "running", "assembly": assembly, "baseline_commit": BASELINE,
        "candidate_commit": CANDIDATE,
        "harness_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "source_sha256": {"baseline": hashlib.sha256(old.encode()).hexdigest(), "candidate": hashlib.sha256(current.encode()).hexdigest()},
        "saved_fingerprint": (source.parent / f".{assembly}.massprops.sha").read_text().strip(),
        "trials": [], "start_unix_ns": time.time_ns(),
    }
    owner = None
    try:
        owner = OwnedAssembly(adapter, source)
        await owner.open()
        for variant, code in (("cold_candidate", current), ("baseline", old), ("candidate_after_baseline", current)):
            row = {"variant": variant, "status": "running"}
            report["trials"].append(row)
            checkpoint(report_path, report)
            owner.assert_active()
            started = time.perf_counter_ns()
            with _telemetry.span("probe.saved_fingerprint_rows", variant=variant, assembly=assembly) as span:
                row["trace_id"] = f"0x{span.get_span_context().trace_id:032x}"
                row["fingerprint"] = await instrument(code, row)(adapter, assembly)
            row.update(status="passed", elapsed_ns=time.perf_counter_ns() - started)
            owner.assert_active()
            checkpoint(report_path, report)
        report["fingerprints_equal"] = len({row["fingerprint"] for row in report["trials"]}) == 1
        report["saved_matches_cold"] = report["saved_fingerprint"] == report["trials"][0]["fingerprint"]
        report["status"] = "measured"
    except Exception as error:
        report.update(status="failed", error=repr(error))
        raise
    finally:
        try:
            if owner is not None:
                await owner.close()
                report["input_evidence"] = owner.input_evidence()
                if any(row.get("unchanged") is not True for row in report["input_evidence"].values()):
                    raise RuntimeError("read-only diagnostic changed native input bytes")
        except Exception as error:
            report.update(status="failed", cleanup_error=repr(error))
            raise
        finally:
            report["end_unix_ns"] = time.time_ns()
            checkpoint(report_path, report)
            print(f"Fingerprint row report: {report_path}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("assembly", choices=("paper-drive", "drive-train", "harmonic-analyzer"))
    parser.add_argument("--worker", action="store_true")
    args = parser.parse_args()
    require_owned_diagnostic_environment()
    if os.environ.get("HARMONIC_REMOTE_CACHE_MODE") != "off" or not os.environ.get("HARMONIC_DIAGNOSTIC_SW_PID"):
        raise RuntimeError("cache off and expected licensed PID required")
    if args.worker:
        return run_owned_diagnostic(lambda adapter: probe(adapter, args.assembly))
    import dodo
    with dodo._com_seat("saved fingerprint rows") as waited:
        with _telemetry.span("task saved fingerprint rows", seat_wait_s=waited):
            dodo._exec([sys.executable, str(Path(__file__).resolve()), args.assembly, "--worker"], "saved fingerprint rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
