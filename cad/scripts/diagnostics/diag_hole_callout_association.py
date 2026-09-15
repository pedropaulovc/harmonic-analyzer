"""Verify process-prefixed callouts follow a disposable model's thread-depth edit.

Run from the worktree root with SolidWorks already running:
    uv run python cad/scripts/diagnostics/diag_hole_callout_association.py

The project source is copied, never opened or edited. The diagnostic owns only
its scratch model/drawing, holds dodo's COM seat, and checks the source hash.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "cad/scripts"))
sys.path.insert(0, str(ROOT))

import dodo
from win32com.client.dynamic import Dispatch as dynamic_dispatch
from _common import _early_bound, check
from _drawing_common import add_native_hole_callout, new_project_drawing, render_pdf_png
from _drawing_registry import DRAWINGS_BY_NAME, DrawingLayout
from draw_harmonic_base import _cross_tap_edge
from diagnostics._owned_native_session import run_owned_diagnostic
from solidworks_mcp.adapters.pywin32_adapter import null_callout
from solidworks_mcp.adapters.solidworks.drawing import place_view, save_drawing

SOURCE = DRAWINGS_BY_NAME["harmonic_base"].source.resolve()
OUTPUT = ROOT / "cad/out/reports/hole-callout-association"
PROCESS = "FRONT AND REAR"
SCALE = (1.0, 4.0)


def _sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _callout_record(display) -> dict:
    display = _early_bound(display, "IDisplayDimension")
    variables = {}
    for raw in tuple(display.GetHoleCalloutVariables() or ()):
        # The generic early-bound interface aliases concrete variable DISPIDs.
        # Read metadata by name, then bind only the concrete value interface.
        late = dynamic_dispatch(raw._oleobj_)
        name, kind = str(late.VariableName), int(late.Type)
        if name in variables:
            raise RuntimeError(f"duplicate callout variable {name}")
        if kind == 1:
            variables[name] = float(_early_bound(raw, "ICalloutLengthVariable").Length) * 1000.0
        elif kind == 3:
            variables[name] = str(_early_bound(raw, "ICalloutStringVariable").String or "")
        else:
            raise RuntimeError(f"unexpected callout variable type {kind}: {name}")
    return {
        "resolved_prefix": str(display.GetText(1) or ""),
        "prefix_definition": str(display.GetText(5) or ""),
        "variables": variables,
    }


def _assert_callout(record: dict, thread_mm: float, *, prefixed: bool) -> None:
    variables = record["variables"]
    assert set(variables) == {
        "hw-threaddesc", "hw-threadclass", "hw-threaddepth",
        "hw-tapdrldia", "hw-tapdrldepth",
    }, variables
    for name, value in (("hw-threaddepth", thread_mm), ("hw-tapdrldepth", 48.0), ("hw-tapdrldia", 4.0386)):
        assert math.isclose(variables[name], value, abs_tol=1e-6), variables
    assert variables["hw-threaddesc"] == "10-32 UNF"
    assert variables["hw-threadclass"].strip(" -") == "2B"
    assert "<hw-threaddepth>" in record["prefix_definition"], record
    assert f"{thread_mm:.2f}" in record["resolved_prefix"], record
    assert record["resolved_prefix"].startswith(PROCESS) == prefixed, record


def _drawing_callouts(drawing) -> list:
    callouts = []
    view = _early_bound(drawing, "IDrawingDoc").GetFirstView()
    for _ in range(100):
        if view is None:
            return callouts
        view = _early_bound(view, "IView")
        annotation = view.GetFirstAnnotation3()
        for _ in range(1000):
            if annotation is None:
                break
            annotation = _early_bound(annotation, "IAnnotation")
            if int(annotation.GetType()) == 4:
                display = annotation.GetSpecificAnnotation()
                if display is not None:
                    display = _early_bound(display, "IDisplayDimension")
                    if display.IsHoleCallout():
                        callouts.append(display)
            annotation = annotation.GetNext3()
        else:
            raise RuntimeError("annotation traversal did not terminate")
        view = view.GetNextView()
    raise RuntimeError("drawing view traversal did not terminate")


async def regression(adapter) -> dict:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    scratch = OUTPUT / "association-scratch.SLDPRT"
    drawing_path = OUTPUT / "association-updated.SLDDRW"
    for owned_path in (scratch, drawing_path):
        if adapter.swApp.GetOpenDocumentByName(str(owned_path)) is not None:
            raise RuntimeError(f"diagnostic document is already open: {owned_path}")
    before = _sha256(SOURCE)
    shutil.copy2(SOURCE, scratch)
    report = {"source_sha256_before": before, "scratch": str(scratch)}
    titles = []
    try:
        check("open scratch model", await adapter.open_model(str(scratch)))
        model = _early_bound(adapter.currentModel, "IModelDoc2")
        titles.append(str(model.GetTitle()))
        new_project_drawing(adapter, layout=DrawingLayout.LANDSCAPE, scale=SCALE)
        drawing = _early_bound(adapter.currentModel, "IModelDoc2")
        titles.append(str(drawing.GetTitle()))
        front = place_view(adapter, str(scratch), "*Front", 0.120, 0.145, scale=SCALE)
        edge = _cross_tap_edge(front)
        plain = add_native_hole_callout(adapter, front, edge=edge,
                                       callout_xy=(0.270, 0.205), label="unprefixed positive control")
        prefixed = add_native_hole_callout(adapter, front, edge=edge,
                                          callout_xy=(0.270, 0.175), label="associative process prefix", process=PROCESS)
        report["before_prefix"] = _callout_record(plain)
        report["after_prefix"] = _callout_record(prefixed)
        _assert_callout(report["before_prefix"], 46.0, prefixed=False)
        _assert_callout(report["after_prefix"], 46.0, prefixed=True)

        # Modify only the disposable copy. Both opposing features describe the
        # same process callout, so change both before checking drawing readback.
        for name in ("BaseCrossTapsFront", "BaseCrossTapsRear"):
            feature = _early_bound(_early_bound(model, "IPartDoc").FeatureByName(name), "IFeature")
            definition = _early_bound(feature.GetDefinition(), "IWizardHoleFeatureData2")
            if not definition.AccessSelections(model, None):
                raise RuntimeError(f"cannot access scratch {name}")
            definition.ThreadDepth = 0.043
            if not feature.ModifyDefinition(definition._oleobj_, model, null_callout()):
                raise RuntimeError(f"cannot modify scratch {name}")
            actual = _early_bound(feature.GetDefinition(), "IWizardHoleFeatureData2").ThreadDepth
            assert math.isclose(actual, 0.043, abs_tol=1e-9), (name, actual)
        model.ForceRebuild3(False)
        drawing.ForceRebuild3(False)
        report["after_model_change_control"] = _callout_record(plain)
        report["after_model_change"] = _callout_record(prefixed)
        _assert_callout(report["after_model_change_control"], 43.0, prefixed=False)
        _assert_callout(report["after_model_change"], 43.0, prefixed=True)
        saved = model.Save3(1, 0, 0)
        if not (saved[0] if isinstance(saved, tuple) else saved):
            raise RuntimeError(f"scratch model save failed: {saved!r}")
        pdf_path, png_path = drawing_path.with_suffix(".pdf"), drawing_path.with_suffix(".png")
        artifacts = save_drawing(adapter, str(drawing_path), pdf_path=str(pdf_path))
        titles[-1] = str(drawing.GetTitle())
        render_pdf_png(pdf_path, png_path, layout=DrawingLayout.LANDSCAPE, expected_pages=1)
        report["artifacts"] = {name: str(path) for name, path in artifacts.items()}
        report["artifacts"]["png"] = str(png_path)
        adapter.swApp.CloseDoc(titles.pop())
        adapter.swApp.CloseDoc(titles.pop())
        check("reopen association drawing", await adapter.open_model(str(drawing_path)))
        reopened = _early_bound(adapter.currentModel, "IModelDoc2")
        titles.append(str(reopened.GetTitle()))
        callouts = _drawing_callouts(reopened)
        assert len(callouts) == 2
        report["after_reopen"] = [_callout_record(callout) for callout in callouts]
        for record in report["after_reopen"]:
            _assert_callout(record, 43.0, prefixed=record["resolved_prefix"].startswith(PROCESS))
        assert sum(record["resolved_prefix"].startswith(PROCESS) for record in report["after_reopen"]) == 1
        report["passed"] = True
    finally:
        for title in reversed(titles):
            adapter.swApp.CloseDoc(title)
        loaded = adapter.swApp.GetOpenDocumentByName(str(scratch))
        if loaded is not None:
            adapter.swApp.CloseDoc(str(_early_bound(loaded, "IModelDoc2").GetTitle()))
        report["source_sha256_after"] = _sha256(SOURCE)
        (OUTPUT / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        assert report["source_sha256_after"] == before, "frozen source changed"
    result = {"passed": True, "report": str(OUTPUT / "report.json")}
    print(json.dumps(result))
    return result


if __name__ == "__main__":
    os.environ["HARMONIC_SW_AUTOSTART"] = "0"
    with dodo._com_seat("diagnostic:hole-callout-association"):
        raise SystemExit(run_owned_diagnostic(regression))
