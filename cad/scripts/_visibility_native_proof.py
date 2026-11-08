"""Experiment-branch-only channel ABBA qualification; never imported by production.

Run only as the existing admitted channel drawing leaf. Every arm calls the
unchanged complete channel builder, which creates and closes a fresh drawing.
A is the baseline's exact unconditional leaf Visible loop; B is the PR helper.
Witness collection is outside isolation timers and reported separately. After
ABBA, an untimed hidden-leaf hide/show roundtrip qualifies both batch polarities.
"""
from __future__ import annotations

import hashlib
import inspect
import json
import os
from pathlib import Path
import shutil
import time
from typing import Any

from _check import check
from _com import _early_bound
import _drawing_balloons as visibility
from _drawing_common import rebuild_drawing
from solidworks_mcp.adapters.solidworks.drawing import view_name
import _telemetry

ROOT = Path(__file__).resolve().parents[2]
PROOF = ROOT / "cad/out/reports/visibility-proof"
ORDER = ("A", "B", "B", "A")


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def output_paths() -> list[Path]:
    return [PROOF / "report.json", *(
        PROOF / f"{index}-{variant}.{kind}"
        for index, variant in enumerate(ORDER, 1)
        for kind in ("SLDDRW", "pdf", "png", "layout.json")
    )]


def _baseline(adapter, view, *, visible_stems, label):
    # Verbatim behavior of origin/main 441290434f family isolation.
    if not visible_stems:
        raise ValueError(f"{label}: visible component set must not be empty")
    root = adapter._attempt(lambda: view.RootDrawingComponent2(False), default=None)
    if root is None:
        raise RuntimeError(f"{label}: drawing view has no root component")
    pending = list(visibility._drawing_component_children(root))
    found = set()
    enumerated = []
    while pending:
        drawing_component = pending.pop()
        children = visibility._drawing_component_children(drawing_component)
        pending.extend(children)
        enumerated.append(str(drawing_component.Name or ""))
        if children:
            continue
        matched = visibility._drawing_component_stems(adapter, drawing_component, visible_stems)
        drawing_component.Visible = bool(matched)
        found.update(matched)
    missing = sorted(visible_stems - found)
    if missing:
        raise RuntimeError(f"{label}: component families not found: {missing}; enumerated={sorted(enumerated)}")
    rebuild_drawing(adapter, label="isolate_drawing_view_components")
    _telemetry.success(f"{label}: isolated {', '.join(sorted(found))}")


def view_state(view) -> dict[str, Any]:
    view = _early_bound(view, "IView")
    return {
        "configuration": str(view.ReferencedConfiguration),
        "display": [bool(view.GetUseParentDisplayMode()), int(view.GetDisplayMode2()),
                    bool(view.GetFacettedHlrDisplay()), bool(view.GetDisplayEdgesInShadedMode()),
                    bool(view.GetCThreadQuality())],
        "position": list(view.Position), "scale": float(view.ScaleDecimal),
    }


def drawing_flags(view) -> dict[str, bool]:
    return {row.name: row.visible for row in visibility._visibility_components(view, label="proof snapshot")}


def normalized_flags(view) -> dict[str, bool]:
    result = {}
    for row in visibility._visibility_components(view, label="proof normalized snapshot"):
        native = _early_bound(row.component.Component, "IComponent2")
        if native is None:
            raise RuntimeError(f"proof: no model component for {row.name}")
        key = str(native.Name2)
        if not key or key in result:
            raise RuntimeError(f"proof: duplicate/empty model occurrence {key!r}")
        result[key] = row.visible
    return result


def siblings(adapter, target) -> dict[str, Any]:
    result = {}
    target_name = view_name(adapter, target)
    draw = _early_bound(adapter.currentModel, "IDrawingDoc")
    for sheet in tuple(draw.GetViews() or ()):
        for raw in tuple(sheet)[1:]:
            view = _early_bound(raw, "IView")
            name = view_name(adapter, view)
            if name != target_name:
                result[name] = {"state": view_state(view), "flags": drawing_flags(view)}
    return result


def source_state(view) -> dict[str, Any]:
    model = _early_bound(view.ReferencedDocument, "IModelDoc2")
    if model is None or int(model.GetType()) != 2:
        raise RuntimeError("proof: assembly reference unavailable")
    manager = _early_bound(model.ConfigurationManager, "IConfigurationManager")
    configuration = _early_bound(manager.ActiveConfiguration, "IConfiguration")
    components = {}
    files = {str(model.GetPathName())}
    for raw in tuple(_early_bound(model, "IAssemblyDoc").GetComponents(False) or ()):
        component = _early_bound(raw, "IComponent2")
        name = str(component.Name2)
        if not name or name in components:
            raise RuntimeError(f"proof: invalid source occurrence {name!r}")
        path = str(component.GetPathName())
        if path:
            files.add(path)
        components[name] = [int(component.Visible), str(component.ReferencedConfiguration)]
    return {"active_configuration": str(configuration.Name), "components": components, "files": sorted(files)}


def input_hashes(state) -> dict[str, str]:
    return {str(Path(path).relative_to(ROOT)).replace('\\', '/'): digest(Path(path)) for path in state["files"]}


async def run(adapter, recipe, build):
    PROOF.mkdir(parents=True, exist_ok=True)
    report = {"status": "running", "order": list(ORDER), "arms": [],
              "candidate_sha256": hashlib.sha256(inspect.getsource(visibility._apply_drawing_visibility).encode()).hexdigest(),
              "baseline_commit": "441290434f", "pid": int(adapter.swApp.GetProcessID()),
              "revision": str(adapter.swApp.RevisionNumber()), "host": os.environ.get("COMPUTERNAME"),
              "timing_scope": "isolation only; complete-build raw includes separately measured witness overhead"}

    def checkpoint():
        encoded = json.dumps(report, indent=2)
        (PROOF / "report.json").write_text(encoded, encoding="utf-8")
        forensic = ROOT / "cad/out/failures/visibility-proof"
        forensic.mkdir(parents=True, exist_ok=True)
        (forensic / "report.json").write_text(encoded, encoding="utf-8")

    original = recipe.isolate_drawing_view_components
    expected_after = {}
    expected_before = {}
    expected_states = {}
    shared_inputs = None
    try:
        for index, variant in enumerate(ORDER, 1):
            arm = {"index": index, "variant": variant, "isolation": [], "witness_seconds": 0.0}
            report["arms"].append(arm)
            implementation = _baseline if variant == "A" else original

            def measured(adapter, view, *, visible_stems, label):
                nonlocal shared_inputs
                start = time.perf_counter()
                before = normalized_flags(view)
                state = view_state(view)
                other = siblings(adapter, view)
                source = source_state(view)
                hashes = input_hashes(source)
                if shared_inputs is None:
                    shared_inputs = hashes
                    report["input_sha256"] = hashes
                elif hashes != shared_inputs:
                    raise RuntimeError("proof: native input hashes changed between arms")
                if label in expected_before and before != expected_before[label]:
                    raise RuntimeError(f"proof: fresh-view initial flags differ for {label}")
                expected_before[label] = before
                if label in expected_states and state != expected_states[label]:
                    raise RuntimeError(f"proof: fresh-view display/configuration differs for {label}")
                expected_states[label] = state
                witness = time.perf_counter() - start
                start = time.perf_counter()
                implementation(adapter, view, visible_stems=visible_stems, label=label)
                elapsed = time.perf_counter() - start
                start = time.perf_counter()
                after = normalized_flags(view)
                if state != view_state(view) or other != siblings(adapter, view) or source != source_state(view):
                    raise RuntimeError(f"proof: display/configuration, sibling or source changed in {label}")
                rows = visibility._visibility_components(view, label=label)
                desired = {row.name: row.visible if row.parent else bool(visibility._drawing_component_stems(adapter, row.component, visible_stems)) for row in rows}
                if drawing_flags(view) != desired:
                    raise RuntimeError(f"proof: exact selected set mismatch in {label}")
                if label in expected_after and after != expected_after[label]:
                    raise RuntimeError(f"proof: candidate/baseline visible set differs in {label}")
                expected_after[label] = after
                witness += time.perf_counter() - start
                arm["witness_seconds"] += witness
                arm["isolation"].append({"label": label, "seconds": elapsed, "before": before, "after": after, "view_state": state,
                                         "sibling_names": sorted(other), "source_configuration": source["active_configuration"],
                                         "native_inputs_sha256": hashes})
                checkpoint()

            recipe.isolate_drawing_view_components = measured
            checkpoint()
            start = time.perf_counter()
            artifacts = await build(adapter)
            arm["complete_build_seconds"] = time.perf_counter() - start
            arm["complete_build_less_witness_seconds"] = arm["complete_build_seconds"] - arm["witness_seconds"]
            arm["input_sha256_after_build"] = {path: digest(ROOT / path) for path in shared_inputs}
            if arm["input_sha256_after_build"] != shared_inputs:
                raise RuntimeError("proof: complete build changed native input files")
            for kind, source in (("SLDDRW", recipe.OUTPUTS.slddrw), ("pdf", recipe.OUTPUTS.pdf), ("png", recipe.OUTPUTS.png),
                                 ("layout.json", ROOT / "cad/out/reports/layout-audit/ch-channel-assembly.json")):
                target = PROOF / f"{index}-{variant}.{kind}"
                shutil.copy2(source, target)
            checkpoint()
        recipe.isolate_drawing_view_components = original
        check("reopen final drawing for polarity controls", await adapter.open_model(str(recipe.OUTPUTS.slddrw)))
        model = _early_bound(adapter.currentModel, "IModelDoc2")
        title = str(model.GetTitle())
        try:
            views = [view for sheet in _early_bound(model, "IDrawingDoc").GetViews() for view in tuple(sheet)[1:]]
            view = _early_bound(views[0], "IView")
            rows = visibility._visibility_components(view, label="polarity control")
            target = next(row for row in rows if row.visible and not row.parent and not row.ancestors)
            before = {row.name: row.visible for row in rows}
            state, other, source = view_state(view), siblings(adapter, view), source_state(view)
            start = time.perf_counter()
            for mode in ("hide", "show"):
                rows = visibility._visibility_components(view, label="polarity control")
                desired = dict(before)
                desired[target.name] = mode == "show"
                visibility._apply_drawing_visibility(adapter, view, rows, desired, enumerate_seconds=0.0, label=f"proof {mode} hidden leaf")
                if state != view_state(view) or other != siblings(adapter, view) or source != source_state(view):
                    raise RuntimeError("proof: polarity control changed sibling/source/view state")
            if drawing_flags(view) != before or input_hashes(source) != shared_inputs:
                raise RuntimeError("proof: polarity roundtrip did not restore exact state/input hashes")
            report["polarity_control"] = {"component": target.name, "seconds": time.perf_counter() - start, "status": "passed"}
        finally:
            adapter.swApp.CloseDoc(title)
        report["status"] = "passed"
        return artifacts
    except Exception as error:
        report["status"] = "failed"
        report["error"] = repr(error)
        raise
    finally:
        recipe.isolate_drawing_view_components = original
        checkpoint()
