"""Copied drive-train dependent-part positive control and A/B refresh probe.

Requires an empty native document table, the inventoried running SolidWorks PID,
cache off and autostart off. Never opens original native outputs. Copies retain
native identities; closed-document reference replacement confines each fixture.
Only the candidate adapter mass read changes; production refresh remains intact.
Fixtures and every attempted phase are retained beside measurements.json.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager, ExitStack
import json
import math
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "cad/scripts"))

from solidworks_mcp.adapters.base import (  # noqa: E402
    AdapterResult, AdapterResultStatus, SetGlobalVariableParameters,
)

import _assembly  # noqa: E402
from _assembly_mass_properties import read_resolved_mass_properties  # noqa: E402
from _common import _early_bound, _read_member, active_configuration_name, check  # noqa: E402
from _interference_contracts import allowed_interference_pairs  # noqa: E402
import _telemetry  # noqa: E402
from diagnostics._owned_native_session import (  # noqa: E402
    require_owned_diagnostic_environment, run_owned_diagnostic,
)
from diagnostics.probe_assembly_health_targets import checkpoint, digest  # noqa: E402
from diagnostics.probe_assembly_mass_read import (  # noqa: E402
    Variant, require_equivalent,
)

ASM = "drive-train"
OLD_BORE_MM = 6.125
NEW_BORE_MM = 6.225
HANDLE_LENGTH_MM = 58.0
NATIVE_SUFFIXES = {".sldasm", ".sldprt"}


class OwnershipError(RuntimeError):
    """Latched failure: no subsequent native work may ignore this error."""


def dependencies(app, path, *, traverse):
    rows = tuple(app.GetDocumentDependencies2(str(path), traverse, False, False) or ())
    if len(rows) % 2:
        raise RuntimeError(f"incomplete native dependency pairs: {path}: {rows!r}")
    return {Path(value).resolve(strict=True) for value in rows[1::2]}


def native_hashes(paths):
    return {str(path): digest(path) for path in sorted(paths)}


def original_outputs():
    return {
        path for folder in (ROOT / "cad/out/sldasm", ROOT / "cad/out/sldprt")
        for path in folder.iterdir()
        if path.is_file() and not path.name.startswith("~$")
        and (path.suffix.lower() in NATIVE_SUFFIXES or path.name.startswith("."))
    }


@contextmanager
def phase(report, report_path, name, **attributes):
    row = {"name": name, "status": "running", "start_unix_ns": time.time_ns(), **attributes}
    report["phases"].append(row)
    checkpoint(report_path, report)
    started = time.perf_counter_ns()
    try:
        with _telemetry.span(f"probe.part_change.{name}", **attributes) as span:
            context = span.get_span_context()
            row.update(trace_id=f"0x{context.trace_id:032x}", span_id=f"0x{context.span_id:016x}")
            yield row
        row["status"] = "passed"
    except Exception as error:
        row.update(status="failed", error=repr(error))
        raise
    finally:
        row.update(end_unix_ns=time.time_ns(), elapsed_ns=time.perf_counter_ns() - started)
        checkpoint(report_path, report)


class FixtureOwner:
    """Explicit copied paths plus per-open identities; never claim originals."""

    def __init__(self, adapter, directory):
        self.adapter = adapter
        self.app = _early_bound(adapter.swApp, "ISldWorks")
        self.directory = directory.resolve()
        self.paths = set()
        self.edges = {}
        self.handles = {}
        self.root = None
        self.failure = None
        self.require_empty()

    def fail(self, message):
        error = OwnershipError(message)
        if self.failure is None:
            self.failure = error
        raise error

    def require_healthy(self):
        if self.failure is not None:
            raise self.failure

    def require_empty(self):
        if self.app.GetDocuments() or self.app.ActiveDoc is not None:
            self.fail("fixture requires an empty native document table; no foreign document closed")

    def register(self, paths, edges):
        self.require_healthy()
        self.require_empty()
        if any(not path.is_relative_to(self.directory) for path in paths):
            self.fail("fixture registration leaves diagnostic directory")
        self.paths, self.edges = set(paths), edges

    def inventory(self, *, claim=False):
        found, titles = {}, set()
        for raw in self.app.GetDocuments() or ():
            model = _early_bound(raw, "IModelDoc2")
            value, title = str(model.GetPathName()), str(model.GetTitle())
            path = Path(value).resolve() if value else None
            if path not in self.paths or path in found or not title or title.casefold() in titles:
                self.fail(f"unowned or ambiguous native document: {value!r}, {title!r}")
            prior = self.handles.get(path)
            if (not claim or prior is not None) and (
                prior is None or int(self.app.IsSame(prior, model)) != 1
            ):
                self.fail(f"native identity changed within one open lifetime: {path}")
            found[path] = model
            titles.add(title.casefold())
        return found

    def assert_current(self):
        self.require_healthy()
        model = self.adapter.currentModel
        if self.root is None or model is None or self.app.ActiveDoc is None:
            self.fail("no active owned model")
        if int(self.app.IsSame(model, self.root)) != 1 or int(self.app.IsSame(self.app.ActiveDoc, self.root)) != 1:
            self.fail("current/active document left the exact owned root")
        native_path = str(self.root.GetPathName())
        path = Path(native_path).resolve() if native_path else None
        known = self.handles.get(path)
        if path not in self.paths or known is None or int(self.app.IsSame(self.root, known)) != 1:
            self.fail("owned root changed its registered native path")
        return self.root

    def assert_closed_references(self):
        self.require_empty()
        for path in sorted(self.paths):
            actual = dependencies(self.app, path, traverse=False)
            if actual != self.edges[path]:
                self.fail(f"closed reference closure differs: {path}: {actual!r} != {self.edges[path]!r}")

    def assert_live_references(self, path):
        expected = dependencies(self.app, path, traverse=True) | {path}
        if not expected <= self.paths or set(self.handles) != expected:
            self.fail(f"open inventory does not equal saved closure: {path}")
        model = self.assert_current()
        if int(model.GetType()) != 2:
            return
        assembly = _early_bound(model, "IAssemblyDoc")
        live = {path}
        for raw in assembly.GetComponents(False) or ():
            component = _early_bound(raw, "IComponent2")
            value = str(component.GetPathName())
            child_path = Path(value).resolve() if value else None
            child = component.GetModelDoc2()
            known = self.handles.get(child_path)
            if known is None or child is None or int(self.app.IsSame(child, known)) != 1:
                self.fail(f"unowned/unresolved live component: {component.Name2}: {value!r}")
            live.add(child_path)
        if live != expected:
            self.fail("live component paths do not equal saved dependency closure")

    async def open(self, path):
        self.require_healthy()
        path = Path(path).resolve(strict=True)
        if path not in self.paths:
            self.fail(f"attempt to open unregistered path: {path}")
        self.assert_closed_references()
        result = await self.adapter.open_model(str(path))
        # Claim only registered copied paths, even if the native open reported an
        # error. This permits safe cleanup without treating a failed open as usable.
        self.handles = self.inventory(claim=True)
        self.root = self.handles.get(path)
        if not result.is_success or self.root is None:
            self.fail(f"fixture open failed: {path}: {result.error}")
        self.assert_live_references(path)
        return result

    def close(self):
        # Cleanup is permitted after a latch only if this fresh inventory still
        # proves every surviving exact path/title/identity. Never SaveReferenced.
        found = self.inventory()
        if not set(found) <= set(self.handles):
            self.fail("unclaimed document prevents cleanup")
        self.handles = found
        while self.handles:
            root_path = Path(str(self.root.GetPathName())).resolve() if self.root is not None else None
            path = root_path if root_path in self.handles else next(iter(self.handles))
            model = self.handles[path]
            self.app.CloseDoc(str(model.GetTitle()))
            remaining = self.inventory()
            if path in remaining or len(remaining) >= len(self.handles):
                self.fail(f"owned document did not close: {path}")
            self.handles = remaining
            self.root = None
        self.adapter.currentModel = None
        self.require_empty()


class OwnedApplication:
    def __init__(self, owner):
        self.owner = owner

    def __getattr__(self, name):
        return getattr(self.owner.app, name)

    def CloseAllDocuments(self, include_unsaved):
        if type(include_unsaved) is not bool:
            self.owner.fail("unexpected CloseAllDocuments argument")
        self.owner.require_healthy()
        try:
            self.owner.close()
        except Exception as error:
            self.owner.fail(f"scoped CloseAllDocuments failed: {error!r}")
        return True

    def CloseDoc(self, title):
        self.owner.fail(f"unexpected direct CloseDoc outside fixture owner: {title!r}")


def poses(model):
    assembly = _early_bound(model, "IAssemblyDoc")
    rows = []
    for raw in assembly.GetComponents(True) or ():
        component = _early_bound(raw, "IComponent2")
        transform = component.Transform2
        if transform is None:
            raise RuntimeError(f"missing transform: {component.Name2}")
        data = tuple(float(value) for value in transform.ArrayData)
        if len(data) != 16 or not all(math.isfinite(value) for value in data):
            raise RuntimeError("invalid component transform")
        rows.append([str(component.Name2), list(data)])
    return sorted(rows)


class FixtureAdapter:
    """Forward native bound methods; specialize only mass and ownership seams."""

    def __init__(self, owner, variant, reads):
        self.owner, self.variant, self.reads = owner, variant, reads
        self.swApp = OwnedApplication(owner)

    def __getattr__(self, name):
        return getattr(self.owner.adapter, name)

    @property
    def currentModel(self):
        return self.owner.assert_current()

    @currentModel.setter
    def currentModel(self, value):
        if value is not None and (
            self.owner.root is None or int(self.owner.app.IsSame(value, self.owner.root)) != 1
        ):
            self.owner.fail("currentModel setter tried to substitute an unowned model")
        self.owner.adapter.currentModel = value

    def _attempt(self, callback, default=None):
        self.owner.require_healthy()
        result = self.owner.adapter._attempt(callback, default=default)
        self.owner.require_healthy()  # native _attempt must not swallow a safety latch
        return result

    async def open_model(self, path):
        return await self.owner.open(path)

    async def get_mass_properties(self):
        model = self.owner.assert_current()
        cfg = active_configuration_name(self.owner.adapter)
        row = {"configuration": cfg, "variant": self.variant, "status": "running"}
        self.reads.append(row)
        started = time.perf_counter_ns()
        try:
            with _telemetry.span("probe.part_change.mass_read", variant=self.variant, config=cfg):
                if self.variant is Variant.CANDIDATE:
                    data = read_resolved_mass_properties(
                        self.owner.adapter, expected_model=model, expected_configuration=cfg,
                    )
                    result = AdapterResult(status=AdapterResultStatus.SUCCESS, data=data)
                else:
                    result = await self.owner.adapter.get_mass_properties()
            data = check("fixture mass read", result)
            self.owner.assert_current()
            row.update(status="passed", value=data.model_dump(), poses=poses(model))
            return result
        except Exception as error:
            row.update(status="failed", error=repr(error))
            raise
        finally:
            row["elapsed_ns"] = time.perf_counter_ns() - started

    async def export_image(self, payload):
        self.owner.assert_current()
        self.owner.inventory()
        if not Path(payload["file_path"]).resolve().is_relative_to(self.owner.directory):
            self.owner.fail("image export leaves fixture directory")
        result = await self.owner.adapter.export_image(payload)
        self.owner.assert_current()
        self.owner.inventory()
        return result


def copy_fixture(owner, source_paths, source_edges, source_root, destination, row):
    owner.require_empty()
    mapping = {
        path: destination / ("sldasm" if path.suffix.lower() == ".sldasm" else "sldprt") / path.name
        for path in source_paths
    }
    if len(set(mapping.values())) != len(mapping):
        raise RuntimeError("duplicate filenames would alias fixture documents")
    row.update(copies=[], replacements=[])
    for source, target in sorted(mapping.items()):
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        before, copied = digest(source), digest(target)
        row["copies"].append({"source": str(source), "target": str(target), "source_sha256": before, "copy_sha256": copied})
        if before != copied:
            raise RuntimeError("native copy changed bytes before reference replacement")
    edges = {mapping[parent]: {mapping[child] for child in children} for parent, children in source_edges.items()}
    owner.register(set(mapping.values()), edges)
    for source, target in sorted(mapping.items()):
        current = dependencies(owner.app, target, traverse=False)
        expected_old, expected_new = source_edges[source], edges[target]
        if not current <= expected_old | expected_new:
            owner.fail(f"copied document has an unexpected reference before relink: {target}")
        for old in sorted(expected_old):
            new = mapping[old]
            replacement = {"parent": str(target), "old": str(old), "new": str(new)}
            row["replacements"].append(replacement)
            owner.require_empty()
            if old in current:
                replacement.update(action="ReplaceReferencedDocument", status="running")
                try:
                    result = owner.app.ReplaceReferencedDocument(str(target), str(old), str(new))
                except Exception as error:
                    replacement.update(status="failed", error=repr(error))
                    raise
                replacement.update(status="returned", result=result)
                if result is not True:
                    raise RuntimeError(f"closed-document reference replacement failed: {replacement}")
            elif new in current:
                replacement["action"] = "already_resolves_to_exact_copy"
            else:
                owner.fail(f"expected direct reference is absent: {replacement}")
    owner.assert_closed_references()
    root = mapping[source_root]
    if dependencies(owner.app, root, traverse=True) | {root} != set(mapping.values()):
        owner.fail("copied root does not reach every registered input")
    for suffix in ("massprops.sha", "dof.json"):
        source = source_root.parent / f".{ASM}.{suffix}"
        target = root.parent / source.name
        shutil.copy2(source, target)
        if digest(source) != digest(target):
            raise RuntimeError(f"sidecar copy differs: {source}")
    row.update(closed_closure_verified=True, native_count=len(mapping), after_relink_sha256=native_hashes(mapping.values()))
    return root


@contextmanager
def fixture_environment(owner, root, gate_calls):
    def no_repair(*args, **kwargs):
        owner.fail("diagnostic refuses AutoMateRepair before any repair action")

    def observe(name, original):
        def call(*args, **kwargs):
            owner.assert_current()
            gate_calls.append(name)
            return original(*args, **kwargs)
        return call

    with ExitStack() as stack:
        stack.enter_context(patch.object(_assembly, "OUT_SLDASM", root.parent))
        stack.enter_context(patch.object(_assembly, "OUT_PNG", root.parent.parent / "png"))
        stack.enter_context(patch.object(_assembly, "repair_dangling_mates", no_repair))
        for name in ("assert_manifest_dof_state", "check_no_interference", "assert_model_healthy"):
            stack.enter_context(patch.object(_assembly, name, observe(name, getattr(_assembly, name))))
        yield


def checked_rebuild(adapter):
    result = adapter.currentModel.ForceRebuild3(False)
    if result is not True:
        raise RuntimeError(f"explicit rebuild failed: {result!r}")
    _assembly.assert_saved_rebuild_clean(adapter, ASM)
    faults = _assembly._rebuild_faults(adapter)
    if faults:
        raise RuntimeError(f"rebuild has hard faults: {faults}")


def gates(adapter):
    _assembly.assert_manifest_dof_state(adapter, ASM, resolve=False)
    _assembly.check_no_interference(adapter, allowed_pairs=allowed_interference_pairs(ASM))
    _assembly.assert_model_healthy(adapter, label=ASM, deep=True, rebuilt=True)


def strict_save(owner):
    model = owner.assert_current()
    owner.inventory()
    _assembly.assert_saved_rebuild_clean(owner.adapter, str(model.GetTitle()))
    result = model.Save3(1, 0, 0)  # Silent only, never SaveReferenced.
    if not isinstance(result, tuple) or len(result) != 3 or result[0] is not True or result[1:] != (0, 0):
        raise RuntimeError(f"Save3 requires success and zero error/warning codes: {result!r}")
    owner.assert_current()
    return list(result)


def dimension_mm(owner, name):
    model = owner.assert_current()
    raw = model.Parameter(name)
    if raw is None:
        raise RuntimeError(f"named dimension missing: {name}")
    dimension = _early_bound(raw, "IDimension")
    value = float(dimension.SystemValue) * 1000.0
    if not math.isfinite(value):
        raise RuntimeError(f"nonfinite dimension: {name}")
    return value


def equations(owner):
    manager = _early_bound(owner.assert_current().GetEquationMgr(), "IEquationMgr")
    if manager is None:
        raise RuntimeError("part equation manager missing")
    rows = [str(manager.Equation(index)) for index in range(int(_read_member(manager, "GetCount")))]
    globals_found = [row for row in rows if row.partition("=")[0].strip() == '"PivotBoreDia"']
    binding = '"PivotBoreDia@PivotBoreProfile"="PivotBoreDia"'
    if len(globals_found) != 1 or binding not in {"".join(row.split()) for row in rows}:
        raise RuntimeError("existing unique bore global and named driving equation are required")
    return rows


async def part_witness(owner):
    owner.assert_current()
    result = await owner.adapter.get_mass_properties()
    data = check("legacy part mass positive control", result)
    owner.assert_current()
    faults = _assembly._rebuild_faults(owner.adapter)
    if faults:
        raise RuntimeError(f"part has hard faults: {faults}")
    _assembly.assert_saved_rebuild_clean(owner.adapter, "crank-handle")
    return {"bore_mm": dimension_mm(owner, "PivotBoreDia@PivotBoreProfile"), "mass_properties": data.model_dump()}


async def set_bore(owner, diameter):
    owner.assert_current()
    owner.inventory()
    before = equations(owner)
    result = await owner.adapter.set_global_variable(SetGlobalVariableParameters(
        name="PivotBoreDia", expression=f"{diameter}mm",
    ))
    data = check("update existing PivotBoreDia global", result)
    if data.get("updated") is not True:
        raise RuntimeError(f"expected update of existing global, not a new equation: {data}")
    after = equations(owner)
    if len(after) != len(before):
        raise RuntimeError("equation update changed equation count")
    for old, new in zip(before, after, strict=True):
        if old.partition("=")[0].strip() != '"PivotBoreDia"' and new != old:
            raise RuntimeError(f"equation update changed an unrelated row: {old!r} -> {new!r}")
    checked_rebuild(owner.adapter)
    require_equivalent(dimension_mm(owner, "PivotBoreDia@PivotBoreProfile"), diameter, "bore_mm")
    return {"adapter_result": data, "equations_before": before, "equations_after": after}


async def change_part(owner, root, report, report_path, label):
    part = root.parent.parent / "sldprt/crank-handle.SLDPRT"
    with phase(report, report_path, f"{label}.part_same_value") as row:
        await owner.open(part)
        configurations = check("part configurations", await owner.adapter.list_configurations())
        if configurations != ["Default"]:
            raise RuntimeError(f"single-configuration part control required: {configurations}")
        require_equivalent(dimension_mm(owner, "HandleLength@HandleProfile"), HANDLE_LENGTH_MM, "handle_length_mm")
        before = await part_witness(owner)
        require_equivalent(before["bore_mm"], OLD_BORE_MM, "initial_bore_mm")
        row["equation_result"] = await set_bore(owner, OLD_BORE_MM)
        same = await part_witness(owner)
        row.update(before=before, after=same)
        require_equivalent(same, before, "same_value_positive_control")
    with phase(report, report_path, f"{label}.part_change") as row:
        row["equation_result"] = await set_bore(owner, NEW_BORE_MM)
        changed = await part_witness(owner)
        loss = before["mass_properties"]["volume"] - changed["mass_properties"]["volume"]
        expected = math.pi / 4 * (NEW_BORE_MM**2 - OLD_BORE_MM**2) * HANDLE_LENGTH_MM
        row.update(before=before, after=changed, volume_loss_mm3=loss, expected_volume_loss_mm3=expected)
        if not math.isclose(loss, expected, rel_tol=1e-8, abs_tol=1e-3):
            raise RuntimeError(f"bore subtraction volume differs: {loss} != {expected} mm3")
        row["save_result"] = strict_save(owner)
        owner.close()
    with phase(report, report_path, f"{label}.part_cold_reopen") as row:
        await owner.open(part)
        _assembly.assert_saved_rebuild_clean(owner.adapter, part.stem)
        reopened = await part_witness(owner)
        row["witness"] = reopened
        require_equivalent(reopened, changed, "saved_part_change")
        owner.close()


async def cold_verify(owner, root, variant, report, report_path, label, expected_digest):
    # Refresh/reconcile retain their production Save3 return handling. This
    # independent closed/reopened clean-state, fingerprint and gate battery is
    # the saved-artifact backstop; strict_save additionally checks our own writes.
    with phase(report, report_path, f"{label}.cold_verify") as row:
        reads, calls = [], []
        row.update(mass_reads=reads, gate_calls=calls)
        adapter = FixtureAdapter(owner, variant, reads)
        with fixture_environment(owner, root, calls):
            await adapter.open_model(str(root))
            _assembly.assert_saved_rebuild_clean(adapter, ASM)  # before resolving anything
            row["saved_rebuild_clean_before_resolve"] = True
            checked_rebuild(adapter)
            row["fingerprint"] = await _assembly.assembly_geometry_digest(adapter, ASM)
            if not reads:
                raise RuntimeError("fingerprint bypassed the mass observer; use the recorded pre-integration revision")
            if row["fingerprint"] != expected_digest:
                raise RuntimeError("cold-reopened full fingerprint differs from gated save")
            gates(adapter)
            owner.assert_live_references(root)
            owner.close()
        return row


async def probe(adapter, directory):
    import solidworks_mcp.adapters.pywin32_adapter as imported_adapter

    if Path(sys.prefix).resolve() != ROOT / ".venv":
        raise RuntimeError("probe requires this clone's own virtual environment")
    if not Path(imported_adapter.__file__).resolve().is_relative_to(ROOT / "SolidworksMCP-python"):
        raise RuntimeError("adapter import left the pinned clone")
    report_path = directory / "measurements.json"
    report = {
        "status": "running", "start_unix_ns": time.time_ns(), "phases": [],
        "root": str(ROOT), "directory": str(directory), "host": platform.node(),
        "python": sys.executable, "solidworks_pid": int(adapter.swApp.GetProcessID()),
        "solidworks_revision": str(adapter.swApp.RevisionNumber()),
        "root_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "adapter_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT / "SolidworksMCP-python", text=True).strip(),
        "source_sha256": {str(path.relative_to(ROOT)): digest(path) for path in (
            Path(__file__), ROOT / "cad/scripts/_assembly.py", ROOT / "cad/scripts/_assembly_mass_properties.py",
        )},
        "comparison": "one relinked legacy control, independent baseline/candidate part-change refreshes and cold gates",
        "timing_scope": "phase wall times include diagnostic witnesses; mass_read elapsed includes its pose witness",
        "original_hashes_before": {},
    }
    checkpoint(report_path, report)
    owner = None
    errors = []
    try:
        owner = FixtureOwner(adapter, directory)
        original_dirs = (ROOT / "cad/out/sldasm", ROOT / "cad/out/sldprt")
        original_paths = original_outputs()
        report["original_hashes_before"] = native_hashes(original_paths)
        source = ROOT / f"cad/out/sldasm/{ASM}.SLDASM"
        inputs = dependencies(owner.app, source, traverse=True) | {source}
        if len(inputs) != 39 or any(path.parent not in original_dirs for path in inputs):
            raise RuntimeError("expected this clone's frozen drive-train closure: root plus 38 native inputs")
        source_edges = {path: dependencies(owner.app, path, traverse=False) for path in inputs}
        if any(not children <= inputs for children in source_edges.values()):
            raise RuntimeError("source direct edge leaves frozen input closure")
        baseline_digest = (source.parent / f".{ASM}.massprops.sha").read_text(encoding="utf-8").strip()
        manifest = json.loads((source.parent / f".{ASM}.dof.json").read_text(encoding="utf-8"))
        if len(manifest["specs"]) != 4:
            raise RuntimeError("expected the drive-train's four saved DOF specifications")
        report.update(source_fingerprint=baseline_digest, dof_manifest=manifest, source_native_count=len(inputs))
        with phase(report, report_path, "control.copy") as row:
            control = copy_fixture(owner, inputs, source_edges, source, directory / "control", row)
        with phase(report, report_path, "control.resolve_gate_save") as row:
            reads, calls = [], []
            row.update(mass_reads=reads, gate_calls=calls)
            control_adapter = FixtureAdapter(owner, Variant.BASELINE, reads)
            with fixture_environment(owner, control, calls):
                await control_adapter.open_model(str(control))
                checked_rebuild(control_adapter)
                row["fingerprint"] = await _assembly.assembly_geometry_digest(control_adapter, ASM)
                if not reads:
                    raise RuntimeError("fingerprint bypassed the mass observer; use the recorded pre-integration revision")
                if row["fingerprint"] != baseline_digest:
                    raise RuntimeError("relinked unchanged control differs from original saved fingerprint")
                gates(control_adapter)
                row["save_result"] = strict_save(owner)
                await _assembly.reconcile_saved_rebuild_state(control_adapter, ASM, control)
                owner.close()
        control_cold = await cold_verify(owner, control, Variant.BASELINE, report, report_path, "control", baseline_digest)
        control_cold["closed_native_sha256"] = native_hashes(owner.paths)
        control_paths, control_edges = set(owner.paths), dict(owner.edges)
        trials = []
        for variant in (Variant.BASELINE, Variant.CANDIDATE):
            label = "baseline" if variant is Variant.BASELINE else "candidate"
            with phase(report, report_path, f"{label}.copy") as row:
                root = copy_fixture(owner, control_paths, control_edges, control, directory / label, row)
            await change_part(owner, root, report, report_path, label)
            with phase(report, report_path, f"{label}.refresh", variant=variant) as row:
                reads, calls = [], []
                row.update(mass_reads=reads, gate_calls=calls)
                trial_adapter = FixtureAdapter(owner, variant, reads)
                with fixture_environment(owner, root, calls):
                    row["artefacts"] = await _assembly.refresh_assembly(
                        trial_adapter, ASM, allowed_pairs=allowed_interference_pairs(ASM),
                    )
                    if not reads:
                        raise RuntimeError("refresh bypassed the mass observer; use the recorded pre-integration revision")
                    if set(calls) != {"assert_manifest_dof_state", "check_no_interference", "assert_model_healthy"}:
                        raise RuntimeError(f"changed refresh did not run all three gates: {calls}")
                    changed_digest = (root.parent / f".{ASM}.massprops.sha").read_text(encoding="utf-8").strip()
                    row["fingerprint"] = changed_digest
                    if changed_digest == baseline_digest:
                        raise RuntimeError("genuine part change did not change assembly fingerprint")
                    owner.assert_live_references(root)
                    owner.close()
            cold = await cold_verify(owner, root, variant, report, report_path, label, changed_digest)
            cold["closed_native_sha256"] = native_hashes(owner.paths)
            require_equivalent(
                [item["poses"] for item in cold["mass_reads"]],
                [item["poses"] for item in control_cold["mass_reads"]], f"{label}.unchanged_component_poses",
            )
            trials.append(cold)
        if trials[0]["fingerprint"] != trials[1]["fingerprint"]:
            raise RuntimeError("A/B changed full fingerprints differ")
        for left, right in zip(trials[0]["mass_reads"], trials[1]["mass_reads"], strict=True):
            require_equivalent(left["configuration"], right["configuration"], "changed_configuration")
            require_equivalent(left["value"], right["value"], "changed_mass_properties")
        report.update(status="passed", changed_fingerprint=trials[0]["fingerprint"], poses_stable=True)
    except Exception as error:
        report.update(status="failed", error=repr(error))
        errors.append(error)
    finally:
        if owner is not None:
            try:
                owner.close()
            except Exception as error:
                report.update(status="failed", cleanup_error=repr(error))
                errors.append(error)
        evidence = {}
        for path, before in report["original_hashes_before"].items():
            try:
                after = digest(Path(path))
                evidence[path] = {"before": before, "after": after, "unchanged": before == after}
            except OSError as error:
                evidence[path] = {"before": before, "unchanged": None, "hash_read_error": repr(error)}
        if not evidence or any(row["unchanged"] is not True for row in evidence.values()):
            report["status"] = "failed"
            errors.append(RuntimeError("original native/sidecar byte preservation was not proven"))
        try:
            report["original_path_set_unchanged"] = {str(path) for path in original_outputs()} == set(report["original_hashes_before"])
            if not report["original_path_set_unchanged"]:
                raise RuntimeError("original native/sidecar path membership changed")
        except OSError as error:
            report["original_path_set_error"] = repr(error)
            report["status"] = "failed"
            errors.append(error)
        except RuntimeError as error:
            report["status"] = "failed"
            errors.append(error)
        report.update(original_evidence=evidence, errors=[repr(error) for error in errors], end_unix_ns=time.time_ns())
        checkpoint(report_path, report)
    print(f"Part-change fixture report: {report_path}", flush=True)
    if errors:
        raise errors[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", action="store_true")
    args = parser.parse_args()
    require_owned_diagnostic_environment()
    if os.environ.get("HARMONIC_REMOTE_CACHE_MODE") != "off" or not os.environ.get("HARMONIC_DIAGNOSTIC_SW_PID"):
        raise RuntimeError("probe requires cache off and an inventoried SolidWorks PID")
    if not args.worker:
        sys.path.insert(0, str(ROOT))
        import dodo

        label = "assembly part-change comparison"
        with dodo._com_seat(label) as waited:
            with _telemetry.span(f"task {label}", label=label, seat_wait_s=waited):
                dodo._exec([sys.executable, str(Path(__file__).resolve()), "--worker"], label)
        return 0
    reports = ROOT / "cad/out/reports"
    reports.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix="assembly-part-change-", dir=reports))
    return run_owned_diagnostic(lambda adapter: probe(adapter, directory))


if __name__ == "__main__":
    raise SystemExit(main())
