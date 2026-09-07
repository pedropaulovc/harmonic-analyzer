"""Compare production deep-health target collection on stationary saved assemblies.

Run from the checkout whose own native outputs will be measured, after importing
this diagnostic and freezing its sources. No production helper is modified.

    $env:HARMONIC_SW_AUTOSTART = '0'
    $env:HARMONIC_REMOTE_CACHE_MODE = 'off'
    $env:HARMONIC_DIAGNOSTIC_SW_PID = '<locally inventoried running PID>'
    uv run python cad/scripts/diagnostics/probe_assembly_health_targets.py

Requires an EMPTY document inventory. Opens only checkout-local saved assemblies
and their native-resolved checkout-local dependencies. Paths, observed input
hashes and native handles are checked; producer-child authenticity is not proved.
Never saves, launches, recovers or changes preferences. A native failure is
retained and ends the experiment without retry.
Baseline/candidate alternate ABBA on each single opened and deep-rebuilt model.
These are health-gate timings, excluding open, rebuild and witness collection.
Separate untimed gate invocations compare exact target instances, null children,
native document identities and What's Wrong results before and after each block.
This does not replace the full soundness/kinematics gates or render inspection.
"""

from __future__ import annotations

import argparse
from collections import Counter
from enum import StrEnum
import hashlib
import inspect
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import time
from types import FunctionType

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "cad/scripts"))

import _assembly  # noqa: E402
from _common import _early_bound, _read_member, check  # noqa: E402
import _telemetry  # noqa: E402
from diagnostics._owned_native_session import (  # noqa: E402
    require_owned_diagnostic_environment,
    run_owned_diagnostic,
)


class Variant(StrEnum):
    BASELINE = "baseline_descendants"
    CANDIDATE = "candidate_top_level"


ORDER = (Variant.BASELINE, Variant.CANDIDATE, Variant.CANDIDATE, Variant.BASELINE)


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def checkpoint(path, report):
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")


def resolved_dependency_rows(app, source):
    """Use native search rules, restoring any documented directory side effect."""
    before = app.GetCurrentWorkingDirectory()
    if type(before) is not str or not before:
        raise RuntimeError("dependency query returned no working directory")
    errors = []
    rows = None
    try:
        rows = tuple(app.GetDocumentDependencies2(str(source), True, True, False) or ())
    except Exception as error:
        errors.append(error)
    finally:
        try:
            if app.GetCurrentWorkingDirectory() != before:
                if app.SetCurrentWorkingDirectory(before) is not True:
                    raise RuntimeError("dependency query working directory restore rejected")
                if app.GetCurrentWorkingDirectory() != before:
                    raise RuntimeError("dependency query working directory restore differs")
        except Exception as error:
            errors.append(error)
    if errors:
        raise ExceptionGroup("native dependency query or directory restoration failed", errors)
    if not rows:
        raise RuntimeError(
            "native dependency query resolved no dependencies; this diagnostic "
            "requires a built assembly with external children"
        )
    return rows


class OwnedAssembly:
    """Own native-resolved local inputs in an initially empty session.

    Search rules support cached assemblies whose saved paths name a producing
    checkout. No path is rewritten by basename. The observed local hashes prove
    preservation during this run, not equality with a trusted producer manifest.
    """

    def __init__(self, adapter, source):
        self.adapter = adapter
        self.app = _early_bound(adapter.swApp, "ISldWorks")
        self.source = source
        self.handles = {}
        self.root = None
        if self.app.GetDocuments() or self.app.ActiveDoc is not None:
            raise RuntimeError("health probe requires an empty session; no documents closed")
        rows = resolved_dependency_rows(self.app, source)
        if len(rows) % 2:
            raise RuntimeError("resolved dependency API returned an incomplete filename/path pair")
        self.inputs = {source, *(Path(path).resolve(strict=True) for path in rows[1::2])}
        permitted = (ROOT / "cad/out/sldasm", ROOT / "cad/out/sldprt")
        if any(path.parent not in permitted for path in self.inputs):
            raise RuntimeError(f"resolved dependencies leave this checkout's native directories: {self.inputs}")
        self.hashes = {str(path): digest(path) for path in sorted(self.inputs)}

    def inventory(self, *, phase="stable"):
        found = {}
        titles = set()
        for raw in self.app.GetDocuments() or ():
            document = _early_bound(raw, "IModelDoc2")
            native_path = str(document.GetPathName())
            path = Path(native_path).resolve() if native_path else None
            title = str(document.GetTitle())
            if path not in self.inputs or path in found or not title or title.casefold() in titles:
                raise RuntimeError(f"unowned or ambiguous native document prevents operation: {native_path!r}")
            titles.add(title.casefold())
            if phase != "claim":
                prior = self.handles.get(path)
                if prior is None or int(self.app.IsSame(prior, document)) != 1:
                    raise RuntimeError(f"native document identity changed: {path}")
            found[path] = document
        if phase == "stable" and set(found) != set(self.handles):
            raise RuntimeError("native document inventory changed during stationary trial")
        return found

    async def open(self):
        check("open saved assembly for health comparison", await self.adapter.open_model(str(self.source)))
        self.handles = self.inventory(phase="claim")
        self.root = self.handles.get(self.source)
        if self.root is None or int(self.root.GetType()) != 2:
            raise RuntimeError("exact saved source is not an open native assembly")
        self.assert_active()

    def assert_active(self):
        self.inventory()
        if (
            int(self.app.IsSame(self.app.ActiveDoc, self.root)) != 1
            or int(self.app.IsSame(self.adapter.currentModel, self.root)) != 1
        ):
            raise RuntimeError("active document is no longer the exact owned assembly")

    def identity(self, raw):
        if raw is None:
            return None
        document = _early_bound(raw, "IModelDoc2")
        path = Path(str(document.GetPathName())).resolve()
        expected = self.handles.get(path)
        if expected is None or int(self.app.IsSame(expected, document)) != 1:
            raise RuntimeError("health gate returned an unowned/replaced native document")
        return str(path), int(document.GetType())

    async def close(self):
        # On failed open, do not infer ownership from whichever document is active.
        if self.root is None:
            if self.app.GetDocuments():
                raise RuntimeError("failed open left unclaimed documents; cleanup refused")
            return
        self.assert_active()
        while self.handles:
            path = self.source if self.source in self.handles else next(iter(self.handles))
            documents = self.inventory()
            title = str(documents[path].GetTitle())
            self.app.CloseDoc(title)  # exact known title; also may unload known hidden references
            remaining = self.inventory(phase="closing")
            if path in remaining or len(remaining) >= len(self.handles):
                raise RuntimeError(f"owned native document did not close: {path}")
            self.handles = remaining
        self.adapter.currentModel = None
        self.root = None

    def input_evidence(self):
        evidence = {}
        for path, before in self.hashes.items():
            try:
                after = digest(Path(path))
            except OSError as error:
                evidence[path] = {"before": before, "status": "unreadable", "error": repr(error)}
                continue
            evidence[path] = {
                "before": before, "after": after, "unchanged": before == after,
                "status": "unchanged" if before == after else "changed",
            }
        return evidence


class AssemblyEnumeration:
    """Force a variant, retaining the production request as separate evidence.

    Both Boolean requests are intentional: the retained pre-change ABBA ran
    while production still requested False. These synthetic variants compare
    timings and functional equivalence; they do not prove production adopted
    the candidate. The unwrapped production regression tests pin that True call.
    """

    def __init__(self, native, variant, counts):
        self.native, self.variant, self.counts = native, variant, counts

    def GetComponents(self, top_level_only):
        if type(top_level_only) is not bool:
            raise RuntimeError("production health collector must request one boolean enumeration")
        effective = self.variant is Variant.CANDIDATE
        call = {"requested_top_level_only": top_level_only, "effective_top_level_only": effective, "status": "running"}
        self.counts.append(call)
        try:
            rows = self.native.GetComponents(effective)
        except Exception as error:
            call.update(status="failed", error=repr(error))
            raise
        call.update(status="returned", components=len(rows or ()))
        return rows


def require_one_enumeration(counts):
    if len(counts) != 1 or counts[0]["status"] != "returned":
        raise RuntimeError(f"expected exactly one completed native component enumeration: {counts}")


class ComponentWitness:
    """Untimed observer: preserve the actual returned child, including None."""

    def __init__(self, native, children):
        self.native, self.children = native, children

    @property
    def Name2(self):
        return self.native.Name2

    def GetModelDoc2(self):
        try:
            document = self.native.GetModelDoc2()
        except Exception as error:
            self.children.append((str(self.native.Name2), None, repr(error)))
            raise  # Preserve the production adapter._attempt behavior.
        self.children.append((str(self.native.Name2), document, None))
        return document


def health_gate(variant, counts, witness=None):
    """Run the production function's exact code with private diagnostic bindings."""
    production = _assembly.assert_model_healthy
    globals_copy = dict(production.__globals__)
    bind = globals_copy["_early_bound"]
    read_wrong = globals_copy["whats_wrong"]

    def bound(raw, interface):
        native = bind(raw, interface)
        if interface == "IAssemblyDoc":
            return AssemblyEnumeration(native, variant, counts)
        if interface == "IComponent2" and witness is not None:
            return ComponentWitness(native, witness["children"])
        return native

    def observed_wrong(adapter, model):
        result = read_wrong(adapter, model)
        witness["targets"].append((model, result))
        return result

    globals_copy["_early_bound"] = bound
    if witness is not None:
        globals_copy["whats_wrong"] = observed_wrong
    clone = FunctionType(production.__code__, globals_copy, production.__name__, production.__defaults__, production.__closure__)
    clone.__kwdefaults__ = production.__kwdefaults__
    return clone


def collect_witness(owner, variant, rebuilt):
    witness = {"children": [], "targets": []}
    counts = []
    with _telemetry.span("probe.health_target_witness", variant=variant):
        health_gate(variant, counts, witness)(owner.adapter, label=owner.source.stem, deep=True, rebuilt=rebuilt)
        require_one_enumeration(counts)
    children = sorted((name, owner.identity(doc), error) for name, doc, error in witness["children"])
    target_names = [owner.source.stem] + [
        name for name, doc, _ in witness["children"] if doc is not None and doc is not owner.adapter.currentModel
    ]
    if len(target_names) != len(witness["targets"]):
        raise RuntimeError("observed health calls differ from the production target inclusion rule")
    targets = sorted(
        (name, owner.identity(doc), sorted(errors))
        for name, (doc, errors) in zip(target_names, witness["targets"], strict=True)
    )
    return {
        "children": children, "targets": targets,
        "target_name_path_multiset": [(name, identity[0]) for name, identity, _ in targets],
        "null_children": [name for name, doc, error in children if doc is None and error is None],
    }


def stationary_state(owner):
    owner.assert_active()
    rows = []
    assembly = _early_bound(owner.adapter.currentModel, "IAssemblyDoc")
    for raw in assembly.GetComponents(False) or ():
        component = _early_bound(raw, "IComponent2")
        transform = _read_member(component, "Transform2")
        array = None if transform is None else tuple(float(value) for value in _read_member(transform, "ArrayData"))
        rows.append((str(component.Name2), str(component.ReferencedConfiguration), array))
    manager = _early_bound(owner.adapter.currentModel.ConfigurationManager, "IConfigurationManager")
    configuration = str(_early_bound(manager.ActiveConfiguration, "IConfiguration").Name)
    return {"configuration": configuration, "needs_rebuild": _assembly.saved_rebuild_status(owner.adapter), "components": sorted(rows)}


async def measure_assembly(adapter, source, report, report_path, blocks):
    owner = OwnedAssembly(adapter, source)
    assembly = {"source": str(source), "input_hashes": owner.hashes, "trials": [], "witnesses": []}
    report["assemblies"].append(assembly)
    checkpoint(report_path, report)
    errors = []
    try:
        await owner.open()
        _assembly.assert_saved_rebuild_clean(adapter, source.stem)
        with _telemetry.span("probe.health_shared_rebuild", assembly=source.stem):
            rebuilt = adapter.currentModel.ForceRebuild3(False)
            if rebuilt is not True:
                raise RuntimeError(f"shared deep rebuild failed: {rebuilt!r}")
        initial = stationary_state(owner)
        assembly["stationary_state"] = initial
        baseline = collect_witness(owner, Variant.BASELINE, rebuilt)
        assembly["baseline_witness"] = baseline
        checkpoint(report_path, report)
        for block in range(blocks):
            before = collect_witness(owner, Variant.CANDIDATE, rebuilt)
            assembly["witnesses"].append({"block": block, "phase": "before", "value": before})
            if before != baseline:
                raise RuntimeError("candidate target/null/diagnostic witness differs from baseline")
            for variant in ORDER:
                owner.assert_active()
                trial = {"block": block, "variant": variant, "status": "running", "start_unix_ns": time.time_ns()}
                assembly["trials"].append(trial)
                checkpoint(report_path, report)
                counts = []
                gate = health_gate(variant, counts)
                try:
                    with _telemetry.span("probe.health_trial", assembly=source.stem, block=block, variant=variant) as span:
                        context = span.get_span_context()
                        trial.update(trace_id=f"0x{context.trace_id:032x}", span_id=f"0x{context.span_id:016x}")
                        started = time.perf_counter()
                        try:
                            gate(adapter, label=source.stem, deep=True, rebuilt=rebuilt)
                        finally:
                            trial["elapsed_s"] = time.perf_counter() - started
                            trial["enumeration_counts"] = counts
                            trial["end_unix_ns"] = time.time_ns()
                        require_one_enumeration(counts)
                    if stationary_state(owner) != initial:
                        raise RuntimeError("health inspection changed the stationary assembly state")
                    trial["status"] = "passed"
                except Exception as error:
                    trial.update(status="failed", error=repr(error))
                    raise
                finally:
                    checkpoint(report_path, report)
            after = collect_witness(owner, Variant.BASELINE, rebuilt)
            candidate = collect_witness(owner, Variant.CANDIDATE, rebuilt)
            assembly["witnesses"].append({"block": block, "phase": "after", "baseline": after, "candidate": candidate})
            if after != baseline or candidate != baseline or stationary_state(owner) != initial:
                raise RuntimeError("ABBA block did not preserve exact baseline witnesses/state")
        assembly["duplicate_target_documents"] = {
            str(key): count for key, count in Counter(row[1] for row in baseline["targets"]).items() if count > 1
        }
    except Exception as error:
        assembly["error"] = repr(error)
        errors.append(error)
    finally:
        try:
            await owner.close()
        except Exception as error:
            assembly["cleanup_error"] = repr(error)
            errors.append(error)
        finally:
            assembly["input_evidence"] = owner.input_evidence()
            checkpoint(report_path, report)
        if any(row.get("unchanged") is not True for row in assembly["input_evidence"].values()):
            errors.append(RuntimeError("native input preservation is not established; see per-file hash evidence"))
    if len(errors) == 1:
        raise errors[0]
    if errors:
        raise ExceptionGroup("health measurement failed; original, cleanup and input failures retained", errors)


async def probe(adapter, stems, directory, blocks):
    import solidworks_mcp.adapters.pywin32_adapter as imported_adapter

    if not Path(imported_adapter.__file__).resolve().is_relative_to(ROOT / "SolidworksMCP-python"):
        raise RuntimeError("adapter import is not from this checkout's pinned submodule")
    if Path(sys.prefix).resolve() != ROOT / ".venv":
        raise RuntimeError("health measurement requires this checkout's own virtual environment")
    report_path = directory / "measurements.json"
    report = {
        "start_unix_ns": time.time_ns(), "status": "running",
        "host": platform.node(), "root": str(ROOT), "python": sys.executable,
        "root_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "adapter_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT / "SolidworksMCP-python", text=True).strip(),
        "adapter_path": imported_adapter.__file__, "solidworks_pid": int(adapter.swApp.GetProcessID()),
        "solidworks_revision": str(adapter.swApp.RevisionNumber()), "cache_mode": os.environ["HARMONIC_REMOTE_CACHE_MODE"],
        "production_gate_sha256": hashlib.sha256(inspect.getsource(_assembly.assert_model_healthy).encode()).hexdigest(),
        "diagnostic_sha256": digest(Path(__file__)), "assemblies": [],
        "timing_scope": "production health gate after one shared deep rebuild; open/rebuild/witness/state reads excluded",
    }
    checkpoint(report_path, report)
    try:
        for stem in stems:
            await measure_assembly(adapter, (ROOT / "cad/out/sldasm" / f"{stem}.SLDASM").resolve(strict=True), report, report_path, blocks)
        report["status"] = "passed"
    except Exception as error:
        report.update(status="failed", error=repr(error))
        raise
    finally:
        report["end_unix_ns"] = time.time_ns()
        checkpoint(report_path, report)
    return {"report": str(report_path)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("assemblies", nargs="*", choices=("channel", "summing", "harmonic-analyzer"))
    parser.add_argument("--blocks", type=int, default=2)
    parser.add_argument("--worker", action="store_true")
    args = parser.parse_args()
    stems = args.assemblies or ["channel", "summing", "harmonic-analyzer"]
    require_owned_diagnostic_environment()
    if os.environ.get("HARMONIC_REMOTE_CACHE_MODE") != "off" or not os.environ.get("HARMONIC_DIAGNOSTIC_SW_PID"):
        raise RuntimeError("probe requires cache mode off and an explicitly inventoried SolidWorks PID")
    if args.blocks < 1 or len(stems) != len(set(stems)):
        raise ValueError("require at least one ABBA block and unique assembly names")
    if not args.worker:
        sys.path.insert(0, str(ROOT))
        import dodo

        label = "assembly health target comparison"
        # Use existing locked execution primitives WITHOUT lifecycle preflight or
        # automatic recovery: ownership must be inventoried before any mutation.
        with dodo._com_seat(label) as waited:
            with _telemetry.span(f"task {label}", label=label, seat_wait_s=waited):
                dodo._exec([sys.executable, str(Path(__file__).resolve()), *stems, "--blocks", str(args.blocks), "--worker"], label)
        return 0
    reports = ROOT / "cad/out/reports"
    reports.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix="assembly-health-targets-", dir=reports))
    return run_owned_diagnostic(lambda adapter: probe(adapter, stems, directory, args.blocks))


if __name__ == "__main__":
    raise SystemExit(main())
