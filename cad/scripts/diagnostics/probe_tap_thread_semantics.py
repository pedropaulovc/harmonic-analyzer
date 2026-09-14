"""Verify native through/blind tap semantics after save-close-reopen.

Run from the checkout with its uv environment::

    uv run python cad/scripts/diagnostics/probe_tap_thread_semantics.py

Creates disposable plates/drawings in a new cad/out/reports directory. Uses
real wizard_holes and unmodified native callouts, not simulated COM objects.
The single-seat lock and normal build watchdog protect the native session.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
import sys
import traceback

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import dodo
from _common import _early_bound, check, run_build
from _drawing_common import (
    add_native_hole_callout,
    new_project_drawing,
    visible_view_entities,
)
from _drawing_registry import DrawingLayout
from _hole_spec import HoleSpec
from _holes import blind_hole_volume_mm3, wizard_holes
from solidworks_mcp.adapters.base import ExtrusionParameters

ROOT = Path(__file__).resolve().parents[3]

PROPERTIES = (
    "Type",
    "FastenerSize",
    "EndCondition",
    "ThreadEndCondition",
    "ThreadClass",
    "CosmeticThreadType",
    "HoleDepth",
    "TapDrillDepth",
    "ThruTapDrillDepth",
    "ThreadDepth",
    "TapDrillDiameter",
    "ThruTapDrillDiameter",
    "ThreadDiameter",
)


def native_state(model):
    feature = _early_bound(
        _early_bound(model, "IPartDoc").FeatureByName("ProbeHole"), "IFeature"
    )
    data = _early_bound(feature.GetDefinition(), "IWizardHoleFeatureData2")
    return {name: getattr(data, name) for name in PROPERTIES}


def require_state(state, spec):
    expected_end = 0 if spec.end == "blind" else 1
    if state["EndCondition"] != expected_end:
        raise RuntimeError(f"wrong drill end: {state}")
    if state["ThreadEndCondition"] != expected_end:
        raise RuntimeError(f"wrong thread end: {state}")
    if state["ThreadClass"] != spec.thread_class:
        raise RuntimeError(f"thread class did not persist: {state}")
    if state["FastenerSize"] != spec.size:
        raise RuntimeError(f"wrong thread size: {state}")
    if spec.end == "blind" and abs(state["ThreadDepth"] * 1000 - 2.0) > 0.005:
        raise RuntimeError(f"wrong full-thread depth: {state}")


def require_callout(callout, spec):
    thread = callout["format_compartments"]["1"]
    drill = callout["format_compartments"]["3"]
    rendered = " ".join(callout["rendered_text"])
    for text in (thread, rendered):
        if spec.size.lstrip("#") not in text or spec.thread_class not in text:
            raise RuntimeError(f"native callout lost thread size/class: {callout}")
    if spec.end == "through_all":
        if any("THRU ALL" not in text for text in (thread, drill, rendered)):
            raise RuntimeError(f"native callout lost through semantics: {callout}")
        if "<HOLE-DEPTH>" in rendered or "<HOLE-DEPTH>" in thread:
            raise RuntimeError(f"through thread still has blind depth: {callout}")
    else:
        for text, depth in ((thread, 2.0), (drill, 3.0)):
            match = re.search(r"<HOLE-DEPTH>\s*([0-9.]+)", text)
            if match is None or abs(float(match[1]) - depth) > 0.005:
                raise RuntimeError(
                    f"native callout lost blind depth {depth}: {callout}"
                )
        depths = [
            float(value) for value in re.findall(r"<HOLE-DEPTH>\s*([0-9.]+)", rendered)
        ]
        if sorted(depths) != [2.0, 3.0] or "THRU" in rendered:
            raise RuntimeError(f"rendered blind depths are incorrect: {callout}")


async def native_callout(adapter, part_path, output, slug):
    draw, _ = new_project_drawing(adapter, layout=DrawingLayout.LANDSCAPE)
    adapter.currentModel = draw
    ddoc = _early_bound(draw, "IDrawingDoc")
    view = ddoc.CreateDrawViewFromModelView3(str(part_path), "*Top", 0.12, 0.15, 0.0)
    if view is None:
        raise RuntimeError("Top view creation failed")
    view = _early_bound(view, "IView")
    draw.EditRebuild3()
    circles = []
    for entity in visible_view_entities(view, 1, label=slug):
        curve = _early_bound(_early_bound(entity, "IEdge").GetCurve(), "ICurve")
        if curve.IsCircle():
            circles.append(entity)
    if len(circles) != 1:
        raise RuntimeError(f"expected one visible hole rim, got {len(circles)}")
    display = add_native_hole_callout(
        adapter, view, edge=circles[0], callout_xy=(0.20, 0.19), label=slug
    )
    annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
    data = _early_bound(annotation.GetDisplayData(), "IDisplayData")
    result = {
        "format_compartments": {
            str(i): str(display.GetText(i) or "") for i in range(5)
        },
        "rendered_text": [
            str(data.GetTextAtIndex(i)) for i in range(data.GetTextCount())
        ],
    }
    path = output / f"{slug}.SLDDRW"
    check("save native probe drawing", await adapter.save_file(str(path)))
    result["drawing"] = str(path)
    return result


def close_documents(adapter):
    if not adapter.swApp.CloseAllDocuments(True):
        raise RuntimeError("closing probe documents failed")
    adapter.currentModel = None


async def build(adapter, output):
    report = {"status": "running", "native_units": "metres/radians", "cases": []}
    receipt = output / "readback.json"
    try:
        for size in ("#6-32", "#10-24"):
            for end in ("through_all", "blind"):
                spec = HoleSpec(
                    "tapped",
                    size,
                    end=end,
                    thread_class="3B",
                    depth_mm=3.0 if end == "blind" else 0.0,
                    overrides_mm={"ThreadDepth": 2.0} if end == "blind" else {},
                )
                slug = size.replace("#", "No") + "-" + end
                row = {"size": size, "end": end, "thread_class": spec.thread_class}
                report["cases"].append(row)
                try:
                    check("create probe plate", await adapter.create_part())
                    check("create plate sketch", await adapter.create_sketch("Top"))
                    sm = _early_bound(
                        adapter.currentModel.SketchManager, "ISketchManager"
                    )
                    if sm.CreateCornerRectangle(-0.01, -0.01, 0, 0.01, 0.01, 0) is None:
                        raise RuntimeError("rectangle creation failed")
                    check("close sketch", await adapter.exit_sketch())
                    check(
                        "extrude plate",
                        await adapter.create_extrusion(
                            ExtrusionParameters(depth=5.08, both_directions=True)
                        ),
                    )
                    before = await adapter.get_mass_properties()
                    check("plate mass", before)
                    result = wizard_holes(
                        adapter, spec, [[0, 2.54, 0]], (0, 1, 0), slug, name="ProbeHole"
                    )
                    after = await adapter.get_mass_properties()
                    check("cut plate mass", after)
                    row["reported_drill_diameter_mm"] = result.hole_dia_mm
                    row["cut_volume_mm3"] = before.data.volume - after.data.volume
                    expected_volume = (
                        blind_hole_volume_mm3(result.hole_dia_mm, spec.depth_mm)
                        if end == "blind"
                        else math.pi * (result.hole_dia_mm / 2) ** 2 * 5.08
                    )
                    row["expected_cut_volume_mm3"] = expected_volume
                    if abs(row["cut_volume_mm3"] - expected_volume) > 0.02:
                        raise RuntimeError(
                            "drill readback disagrees with actual material removed"
                        )
                    part_path = output / f"{slug}.SLDPRT"
                    check("save probe plate", await adapter.save_file(str(part_path)))
                    close_documents(adapter)
                    check(
                        "reopen probe plate", await adapter.open_model(str(part_path))
                    )
                    model = _early_bound(adapter.currentModel, "IModelDoc2")
                    row["reopened_SI"] = native_state(model)
                    require_state(row["reopened_SI"], spec)
                    row["native_callout"] = await native_callout(
                        adapter, part_path, output, slug
                    )
                    require_callout(row["native_callout"], spec)
                    row["status"] = "passed"
                finally:
                    receipt.write_text(json.dumps(report, indent=2), encoding="utf-8")
                    close_documents(adapter)
        report["status"] = "passed"
        return {"readback": str(receipt)}
    except Exception:
        report["status"] = "failed"
        report["error"] = traceback.format_exc()
        raise
    finally:
        receipt.write_text(json.dumps(report, indent=2), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    reports = ROOT / "cad/out/reports"
    output = (
        args.output
        or reports
        / ("tap-thread-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
    ).resolve()
    if not output.is_relative_to(reports.resolve()) or output.exists():
        raise ValueError("choose a new directory under this checkout's cad/out/reports")
    output.mkdir(parents=True)
    with dodo._com_seat("tap-thread-native-regression"):
        return run_build(lambda adapter: build(adapter, output))


if __name__ == "__main__":
    raise SystemExit(main())
