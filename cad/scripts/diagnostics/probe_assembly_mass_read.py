"""ABBA comparison of complete assembly fingerprints on one owned resolved model.

Run with cache off, HARMONIC_SW_AUTOSTART=0 and the inventoried
HARMONIC_DIAGNOSTIC_SW_PID. Opens only this clone's saved drive-train and
dependencies, requires an empty document table, and never saves or recovers.
The production fingerprint code is unchanged: an adapter observer substitutes
only the candidate mass read. Baseline uses the pinned adapter, including its
deep rebuild. Every attempt, state witness and input hash is checkpointed.
"""

from __future__ import annotations

import argparse
from enum import StrEnum
import hashlib
import inspect
import math
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "cad/scripts"))

import win32api  # noqa: E402
import win32process  # noqa: E402
from solidworks_mcp.adapters.base import AdapterResult, AdapterResultStatus  # noqa: E402

import _assembly  # noqa: E402
from _assembly_mass_properties import read_resolved_mass_properties  # noqa: E402
from _common import active_configuration_name  # noqa: E402
import _telemetry  # noqa: E402
from diagnostics._owned_native_session import (  # noqa: E402
    require_owned_diagnostic_environment,
    run_owned_diagnostic,
)
from diagnostics.probe_assembly_health_targets import (  # noqa: E402
    OwnedAssembly, checkpoint, digest, stationary_state,
)


class Variant(StrEnum):
    BASELINE = "adapter_rebuild_then_read"
    CANDIDATE = "resolved_native_read"


ORDER = (Variant.BASELINE, Variant.CANDIDATE, Variant.CANDIDATE, Variant.BASELINE)


class RebuildObserver:
    def __init__(self, native, calls):
        self.native, self.calls = native, calls

    def __getattr__(self, name):
        return getattr(self.native, name)

    def ForceRebuild3(self, top_only):
        call = {"top_only": top_only, "status": "running"}
        self.calls.append(call)
        started = time.perf_counter()
        try:
            with _telemetry.span("probe.mass_baseline_rebuild"):
                result = self.native.ForceRebuild3(top_only)
            call.update(status="returned", result=result)
            return result
        except Exception as error:
            call.update(status="failed", error=repr(error))
            raise
        finally:
            call["elapsed_s"] = time.perf_counter() - started


class MassReadObserver:
    def __init__(self, adapter, owner, variant, trial):
        self.adapter, self.owner, self.variant, self.trial = adapter, owner, variant, trial

    def __getattr__(self, name):
        return getattr(self.adapter, name)

    async def get_mass_properties(self):
        cfg = active_configuration_name(self.adapter)
        if self.variant is Variant.CANDIDATE:
            data = read_resolved_mass_properties(
                self.adapter, expected_model=self.owner.root, expected_configuration=cfg,
            )
            result = AdapterResult(status=AdapterResultStatus.SUCCESS, data=data)
        else:
            native = self.adapter.currentModel
            self.adapter.currentModel = RebuildObserver(native, self.trial["rebuilds"])
            try:
                result = await self.adapter.get_mass_properties()
            finally:
                self.adapter.currentModel = native
        if not result.is_success or result.data is None:
            raise RuntimeError(f"mass read failed: {result.error}")
        self.trial["mass_properties"].append({"configuration": cfg, "value": result.data.model_dump()})
        return result


def require_equivalent(actual, expected, path="witness"):
    """Keep full raw values, allowing only tiny floating-point solve noise."""
    if isinstance(expected, float):
        if not math.isclose(actual, expected, rel_tol=1e-10, abs_tol=1e-9):
            raise RuntimeError(f"{path} changed: {expected!r} -> {actual!r}")
        return
    if isinstance(expected, dict):
        if actual.keys() != expected.keys():
            raise RuntimeError(f"{path} fields changed")
        for key in expected:
            require_equivalent(actual[key], expected[key], f"{path}.{key}")
        return
    if isinstance(expected, (tuple, list)):
        if len(actual) != len(expected):
            raise RuntimeError(f"{path} length changed")
        for index, (left, right) in enumerate(zip(actual, expected, strict=True)):
            require_equivalent(left, right, f"{path}[{index}]")
        return
    if actual != expected:
        raise RuntimeError(f"{path} changed: {expected!r} -> {actual!r}")


async def probe(adapter, directory, blocks):
    import solidworks_mcp.adapters.pywin32_adapter as imported_adapter

    if Path(sys.prefix).resolve() != ROOT / ".venv":
        raise RuntimeError("probe requires this clone's own virtual environment")
    if not Path(imported_adapter.__file__).resolve().is_relative_to(ROOT / "SolidworksMCP-python"):
        raise RuntimeError("adapter import left the pinned clone")
    report_path = directory / "measurements.json"
    owner = OwnedAssembly(adapter, ROOT / "cad/out/sldasm/drive-train.SLDASM")
    pid = int(adapter.swApp.GetProcessID())
    process = win32api.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    try:
        process_started = win32process.GetProcessTimes(process)["CreationTime"].timestamp()
    finally:
        process.Close()
    report = {
        "status": "running", "start_unix_ns": time.time_ns(), "host": platform.node(),
        "root": str(ROOT), "python": sys.executable, "solidworks_pid": pid,
        "solidworks_start_unix_s": process_started,
        "solidworks_revision": str(adapter.swApp.RevisionNumber()),
        "root_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "adapter_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT / "SolidworksMCP-python", text=True).strip(),
        "cache_mode": os.environ["HARMONIC_REMOTE_CACHE_MODE"], "input_hashes": owner.hashes,
        "fingerprint_source_sha256": hashlib.sha256(inspect.getsource(_assembly.assembly_geometry_digest).encode()).hexdigest(),
        "source_sha256": {str(path.relative_to(ROOT)): digest(path) for path in (
            Path(__file__), ROOT / "cad/scripts/_assembly_mass_properties.py",
            ROOT / "cad/scripts/_assembly.py",
        )},
        "timing_scope": "whole production fingerprint; excludes open, shared rebuild, health and state witnesses",
        "raw_comparison": {"relative_tolerance": 1e-10, "absolute_tolerance": 1e-9},
        "trials": [],
    }
    checkpoint(report_path, report)
    errors = []
    try:
        await owner.open()
        _assembly.assert_saved_rebuild_clean(adapter, owner.source.stem)
        with _telemetry.span("probe.mass_shared_rebuild"):
            rebuilt = adapter.currentModel.ForceRebuild3(False)
            if rebuilt is not True:
                raise RuntimeError(f"shared rebuild failed: {rebuilt!r}")
        _assembly.assert_model_healthy(adapter, label=owner.source.stem, deep=True, rebuilt=rebuilt)
        initial = stationary_state(owner)
        report["initial_state"] = initial
        for block in range(blocks):
            for variant in ORDER:
                owner.assert_active()
                trial = {
                    "block": block, "variant": variant, "status": "running",
                    "start_unix_ns": time.time_ns(), "rebuilds": [], "mass_properties": [],
                    "session_age_s": time.time() - report["solidworks_start_unix_s"],
                }
                report["trials"].append(trial)
                checkpoint(report_path, report)
                try:
                    observer = MassReadObserver(adapter, owner, variant, trial)
                    with _telemetry.span("probe.mass_trial", block=block, variant=variant) as span:
                        context = span.get_span_context()
                        trial.update(trace_id=f"0x{context.trace_id:032x}", span_id=f"0x{context.span_id:016x}")
                        started = time.perf_counter()
                        try:
                            trial["fingerprint"] = await _assembly.assembly_geometry_digest(observer, owner.source.stem)
                        finally:
                            trial["elapsed_s"] = time.perf_counter() - started
                    if not trial["mass_properties"]:
                        raise RuntimeError("fingerprint bypassed the mass observer; rerun at the recorded pre-integration revision")
                    if variant is Variant.BASELINE and (
                        len(trial["rebuilds"]) != len(trial["mass_properties"])
                        or any(row.get("result") is not True for row in trial["rebuilds"])
                    ):
                        raise RuntimeError("baseline's hidden rebuild did not succeed exactly once per mass read")
                    trial["state_after"] = stationary_state(owner)
                    require_equivalent(trial["state_after"], initial, "stationary_state")
                    baseline = report["trials"][0]
                    require_equivalent(trial["mass_properties"], baseline["mass_properties"], "mass_properties")
                    if trial["fingerprint"] != baseline["fingerprint"]:
                        raise RuntimeError("complete geometry fingerprint differs from positive control")
                    trial["status"] = "passed"
                except Exception as error:
                    trial.update(status="failed", error=repr(error))
                    raise
                finally:
                    trial["end_unix_ns"] = time.time_ns()
                    checkpoint(report_path, report)
        report["status"] = "passed"
    except Exception as error:
        report.update(status="failed", error=repr(error))
        errors.append(error)
    finally:
        try:
            await owner.close()
        except Exception as error:
            report.update(status="failed", cleanup_error=repr(error))
            errors.append(error)
        report["input_evidence"] = owner.input_evidence()
        if any(row.get("unchanged") is not True for row in report["input_evidence"].values()):
            report["status"] = "failed"
            errors.append(RuntimeError("native inputs changed during no-save comparison"))
        report["end_unix_ns"] = time.time_ns()
        checkpoint(report_path, report)
    if errors:
        raise ExceptionGroup("mass comparison failed; all failures retained", errors)
    return {"report": str(report_path)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blocks", type=int, default=3)
    parser.add_argument("--worker", action="store_true")
    args = parser.parse_args()
    require_owned_diagnostic_environment()
    if os.environ.get("HARMONIC_REMOTE_CACHE_MODE") != "off" or not os.environ.get("HARMONIC_DIAGNOSTIC_SW_PID"):
        raise RuntimeError("probe requires cache off and an inventoried SolidWorks PID")
    if args.blocks < 1:
        raise ValueError("at least one ABBA block is required")
    if not args.worker:
        sys.path.insert(0, str(ROOT))
        import dodo

        label = "assembly mass-read comparison"
        with dodo._com_seat(label) as waited:
            with _telemetry.span(f"task {label}", label=label, seat_wait_s=waited):
                dodo._exec([sys.executable, str(Path(__file__).resolve()), "--blocks", str(args.blocks), "--worker"], label)
        return 0
    reports = ROOT / "cad/out/reports"
    reports.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix="assembly-mass-read-", dir=reports))
    return run_owned_diagnostic(lambda adapter: probe(adapter, directory, args.blocks))


if __name__ == "__main__":
    raise SystemExit(main())
