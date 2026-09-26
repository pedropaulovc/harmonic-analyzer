"""diag (MHA-091 RD3 callout probe, never merge): does a hole callout work on a
CROPPED "*Top" model view of the MHA-151 dowel pair, and can a native
callout's line be broken to print narrower?

Main's ruling (#917 S1, PR #929): RD2 moves to the under-plan band; RD3 goes
on a cropped "*Top" model view of the dowel pair -- on sheet 1 if a view box
plus RD3's box clears everything, else sheet 2.  No in-repo positive control
exists for a hole callout on a cropped model view, so this leaf proves the
mechanism before anything is built on it.

``run`` is called by ``draw_cone_swing_platform.build`` right after the
sheet dump and BEFORE ``check_drawing_layout`` (the ac4f leaf fails that
audit, so a post-save hook would never fire).  It:

* p2 -- on the as-built RD3 (the plan's dowel callout): logs every text part,
  the display lines, the callout variables and RD3's text boxes; then for
  each line-break variant (a newline where the process text meets the native
  tokens; a newline before THRU) writes the prefix definition, rebuilds,
  re-reads and re-measures; then restores the original and re-measures.
* p1 -- places a "*Top" model view, moves it so the dowel pair's midpoint
  lands on PROBE_CROP_CENTRE, sketches a circle in the view's own sketch and
  Crop2's it (the MHA-142 recipe, b6552f13b), logs IsCropped and the outline
  before/after; finds the dowel rims the cropped view exposes; calls
  AddHoleCallout2 on one DIRECTLY (not add_native_hole_callout, whose failure
  path saves a forensic copy of the sheet); applies RD3's recipe (process
  prefix, hw-diam to 3 places); reads back the text, the variables and every
  leader segment against the view outline; runs the sheet audit and logs its
  findings for the new callout.
* exports a PDF of the probed sheet into the log (base64, the maxblast
  pattern), logging the document's path/title before and after;
* discards every open document WITHOUT saving (``discard_open_documents``)
  and logs the source SLDPRT's and the SLDDRW's SHA-256 before and after;
* raises, so the leaf fails on purpose: nothing is saved, nothing reaches the
  remote cache.

Every probe step is guarded: a failure is logged at warn and the next step
still runs.  All result lines start ``mha091-probe``.
"""

from __future__ import annotations

import base64
import hashlib
import json
import math
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
from typing import Any

import _telemetry
from _layout_geometry import Box, Segment

TAG = "mha091-probe"
# Where p1 puts the cropped view and its callout text (sheet metres): the
# offline room search's scenario-A candidate (917-s1-mha091-cropview-room-*.log,
# RD2 off sheet 1), clean there with the pivot note as built: 1:2, margin
# 2 mm, view [196.7,68.7]..[213.7,85.7] mm (crop centre (205.2, 77.2)), RD3
# text [80.7,87.7]..[178.1,105.8] mm, leader (205.9,83.9)->(178.3,87.7) mm.
# So the probe's audit read-back also checks that candidate on the real sheet.
# The callout position is the text box centre corrected by the ac4f RD3
# offset (GetPosition (117.0,222.0) vs its union centre (117.7,220.95)).
PROBE_SCALE = (1, 2)
PROBE_CROP_MARGIN_MM = 2.0
PROBE_CROP_CENTRE = (0.2052, 0.0772)
PROBE_CALLOUT_XY = (0.1287, 0.0978)
_CROP_NO_ERROR = 1  # swCropViewErrors_e.swCropViewErrors_NoError
_TEXT_PARTS = {
    1: "prefix",
    2: "suffix",
    3: "callout-above",
    4: "callout-below",
    5: "prefix-def",
    6: "suffix-def",
    7: "callout-above-def",
    8: "callout-below-def",
}  # swDimensionTextParts_e


# ---------------------------------------------------------------- pure helpers
def file_stamp(path: Path | str) -> dict[str, object]:
    """Size, mtime and SHA-256 of ``path``, or ``{"state": "absent"}``."""
    file = Path(path)
    if not file.is_file():
        return {"state": "absent"}
    data = file.read_bytes()
    return {
        "state": "present",
        "size": len(data),
        "mtime_ns": file.stat().st_mtime_ns,
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def discard_verdict(
    before: Mapping[str, Mapping[str, object]], after: Mapping[str, Mapping[str, object]]
) -> tuple[bool, list[str]]:
    """(every file byte-identical, one row per file)."""
    if set(before) != set(after):
        raise ValueError(f"stamped different files: {sorted(before)} vs {sorted(after)}")
    ok, rows = True, []
    for name in before:
        b, a = before[name], after[name]
        if b.get("state") == "absent" and a.get("state") == "absent":
            rows.append(f"{name}: absent before and after")
        elif b.get("state") == "absent":
            ok = False
            rows.append(f"{name}: CREATED (absent -> sha256 {a.get('sha256')})")
        elif a.get("state") == "absent":
            ok = False
            rows.append(f"{name}: DELETED (sha256 {b.get('sha256')} -> absent)")
        elif b.get("sha256") == a.get("sha256"):
            rows.append(f"{name}: unchanged sha256 {b.get('sha256')}")
        else:
            ok = False
            rows.append(f"{name}: CHANGED sha256 {b.get('sha256')} -> {a.get('sha256')}")
    return ok, rows


def dowel_pair_crop_mm(
    dowels_xz_mm: Iterable[tuple[float, float]], *, ream_dia_mm: float, margin_mm: float
) -> tuple[tuple[float, float], float]:
    """The crop circle (model xz centre, radius) holding both rims + margin."""
    (x0, z0), (x1, z1) = tuple(dowels_xz_mm)
    half = math.hypot(x1 - x0, z1 - z0) / 2.0
    return ((x0 + x1) / 2.0, (z0 + z1) / 2.0), half + ream_dia_mm / 2.0 + margin_mm


def inside_length(segment: Segment, box: Box) -> float:
    """Length of ``segment`` inside ``box`` (Liang-Barsky clip)."""
    x0, y0 = segment.x0, segment.y0
    dx, dy = segment.x1 - x0, segment.y1 - y0
    lo, hi = 0.0, 1.0
    for p, q in (
        (-dx, x0 - box.xmin),
        (dx, box.xmax - x0),
        (-dy, y0 - box.ymin),
        (dy, box.ymax - y0),
    ):
        if p == 0.0:
            if q < 0.0:
                return 0.0
            continue
        t = q / p
        if p < 0.0:
            lo = max(lo, t)
        else:
            hi = min(hi, t)
        if lo > hi:
            return 0.0
    return (hi - lo) * math.hypot(dx, dy)


def break_variants(prefix: str, process: str) -> list[tuple[str, str]]:
    """Line-break rewrites of a callout's prefix DEFINITION.

    ``process|native``: the space joining the process text and the native
    Hole Wizard tokens becomes a newline, so the tokens print on their own
    row.  ``before THRU``: the native row itself breaks before THRU."""
    out: list[tuple[str, str]] = []
    joint = process.rstrip() + " "
    if prefix.startswith(joint):
        native = prefix[len(joint):]
        out.append(("process|native", process.rstrip() + "\n" + native))
        at = prefix.rfind(" THRU")
        if at > len(joint):
            out.append(("before THRU", prefix[:at] + "\nTHRU" + prefix[at + len(" THRU"):]))
    return out


# ------------------------------------------------------------------ COM side
def _info(message: str) -> None:
    _telemetry.info(f"{TAG} {message}")


def _guard(step: str, action: Callable[[], object]) -> object:
    try:
        return action()
    except Exception as exc:  # noqa: BLE001 - diagnostic: log and carry on
        _telemetry.warn(f"{TAG} {step} FAILED: {exc!r}")
        return None


def _texts(display: Any) -> dict[str, str]:
    return {name: str(display.GetText(part) or "") for part, name in _TEXT_PARTS.items()}


def _variables(display: Any) -> list[str]:
    from win32com.client.dynamic import Dispatch as dynamic_dispatch  # noqa: PLC0415

    return [
        str(dynamic_dispatch(raw._oleobj_).VariableName)
        for raw in (display.GetHoleCalloutVariables() or ())
    ]


def _display_lines(annotation: Any) -> list[str]:
    from _common import _early_bound  # noqa: PLC0415

    data = annotation.GetDisplayData()
    if data is None:
        return ["<no display data>"]
    data = _early_bound(data, "IDisplayData")
    return [str(data.GetTextAtIndex(i)) for i in range(int(data.GetTextCount()))]


def _read_callout(label: str, display: Any) -> None:
    from _common import _early_bound  # noqa: PLC0415

    annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
    _info(f"{label} texts {json.dumps(_texts(display))}")
    _info(f"{label} display lines {json.dumps(_display_lines(annotation))}")
    _info(f"{label} variables {_variables(display)}; name {annotation.GetName()!r}; "
          f"attached {int(annotation.GetAttachedEntityCount3())}; leaders {int(annotation.GetLeaderCount())}; "
          f"position {tuple(round(float(v) * 1000, 2) for v in annotation.GetPosition())} mm")


def _sheets(adapter: Any) -> list[Any]:
    from diagnostics.drawing_layout_audit import collect_document  # noqa: PLC0415

    return collect_document(adapter)


def _measure(adapter: Any, label: str, *, names: Iterable[str] = (), owners: Iterable[str] = ()) -> list[Any]:
    """Log the text boxes and segments of the named / owned annotations, and
    the owners' view outlines, as collect_document reads them."""
    names, owners = set(names), set(owners)
    found = []
    for sheet in _sheets(adapter):
        outlines = {view.name: view.outline for view in sheet.views}
        for owner in owners:
            if owner in outlines:
                _info(f"{label} sheet {sheet.name!r} view {owner!r} outline "
                      f"{outlines[owner].format_mm() if outlines[owner] else None}")
        for item in sheet.annotations:
            if item.label not in names and item.owner not in owners:
                continue
            found.append((sheet, item))
            union = None
            for box in item.text_boxes:
                union = box if union is None else union.union(box)
            _info(
                f"{label} {item.kind} {item.label!r} owner {item.owner!r} text union "
                f"{union.format_mm() if union else None} "
                f"({union.width * 1000:.1f} x {union.height * 1000:.1f} mm)" if union else
                f"{label} {item.kind} {item.label!r} owner {item.owner!r} no text boxes"
            )
            _info(f"{label} {item.label!r} rows " + " ".join(box.format_mm() for box in item.text_boxes))
            outline = outlines.get(item.owner)
            for segment in item.segments:
                inside = inside_length(segment, outline) if outline else float("nan")
                _info(
                    f"{label} {item.label!r} {segment.role} {segment.format_mm()} length "
                    f"{segment.length * 1000:.2f} mm, inside own view {inside * 1000:.2f} mm"
                )
    return found


# ------------------------------------------------------------------------ p2
def probe_line_break(adapter: Any, display: Any, *, process: str) -> None:
    from _drawing_common import rebuild_drawing  # noqa: PLC0415

    _read_callout("p2 baseline RD3", display)
    _measure(adapter, "p2 baseline", names=("RD3",))
    original = str(display.GetText(5) or "")
    variants = break_variants(original, process)
    _info(f"p2 prefix definition {original!r}; variants {[name for name, _ in variants]}")
    for name, text in variants:
        display.SetText(1, text)
        readback = str(display.GetText(5) or "")
        _info(f"p2 [{name}] SetText(1) {text!r} -> GetText(5) {readback!r} persisted={readback == text}")
        rebuild_drawing(adapter, label=f"{TAG} p2 {name}")
        _read_callout(f"p2 [{name}] RD3", display)
        _measure(adapter, f"p2 [{name}]", names=("RD3",))
        display.SetText(1, original)
        rebuild_drawing(adapter, label=f"{TAG} p2 restore")
        restored = str(display.GetText(5) or "")
        _info(f"p2 [{name}] restored persisted={restored == original}")
    _measure(adapter, "p2 restored", names=("RD3",))


# ------------------------------------------------------------------------ p1
def _sketch_circle(adapter: Any, view: Any, center: tuple[float, float], radius: float) -> Any:
    """MHA-142's recipe (b6552f13b): sheet points through the view sketch's
    ModelToSketchTransform; the new circle is left SELECTED for Crop2."""
    from _common import _early_bound  # noqa: PLC0415
    from solidworks_mcp.adapters.com_variant import double_array  # noqa: PLC0415

    sketch = _early_bound(_early_bound(view, "IView").GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    points = []
    for x, y in (center, (center[0] + radius, center[1])):
        point = _early_bound(utility.CreatePoint(double_array([x, y, 0.0])), "IMathPoint")
        projected = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
        points.append(tuple(float(value) for value in projected.ArrayData))
    manager = _early_bound(adapter.currentModel.SketchManager, "ISketchManager")
    circle = manager.CreateCircle(*points[0], *points[1])
    if circle is None:
        raise RuntimeError("cannot sketch the crop circle")
    return circle


def _outline(view: Any) -> tuple[float, ...]:
    return tuple(round(float(value) * 1000, 2) for value in view.GetOutline())


def _dowel_edges(adapter: Any, view: Any, *, ream_radius_m: float) -> list[tuple[tuple[float, float, float], Any]]:
    """Every visible circular edge of the ream radius: (model centre, edge)."""
    from _common import _early_bound  # noqa: PLC0415

    out = []
    radii: dict[float, int] = {}
    components = adapter._attempt(lambda: view.GetVisibleComponents(), default=()) or ()
    for component in components:
        edges = adapter._attempt(lambda c=component: view.GetVisibleEntities2(c, 1), default=()) or ()
        for raw in edges:
            edge = _early_bound(raw, "IEdge")
            curve = _early_bound(edge.GetCurve(), "ICurve")
            if not curve.IsCircle():
                continue
            params = tuple(float(value) for value in curve.CircleParams)
            radii[round(params[6] * 1000, 3)] = radii.get(round(params[6] * 1000, 3), 0) + 1
            if abs(params[6] - ream_radius_m) <= 1e-6:
                out.append((params[:3], edge))
    _info(f"p1 cropped view visible circle radii (mm: count) {dict(sorted(radii.items()))}; "
          f"ream-radius rims {[tuple(round(v * 1000, 3) for v in c) for c, _ in out]}")
    return out


def probe_cropped_view(adapter: Any, *, source: Path, process: str) -> None:
    from _common import _early_bound  # noqa: PLC0415
    from _drawing_common import (  # noqa: PLC0415
        _select_view_entity,
        model_point_in_view,
        rebuild_drawing,
        set_hidden_lines_removed,
        set_hole_callout_precision,
    )
    from _layout_geometry import audit_sheet  # noqa: PLC0415
    from cone_post_dowel_spec import PLATE_DOWEL_REAM_DIA, POST_DOWEL_PLATE_XZ  # noqa: PLC0415
    from cone_swing_platform_spec import PLATE_THICKNESS  # noqa: PLC0415
    from solidworks_mcp.adapters.com_variant import double_array  # noqa: PLC0415
    from solidworks_mcp.adapters.solidworks.drawing import place_view, view_name  # noqa: PLC0415

    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    (mx, mz), radius_mm = dowel_pair_crop_mm(
        POST_DOWEL_PLATE_XZ, ream_dia_mm=PLATE_DOWEL_REAM_DIA, margin_mm=PROBE_CROP_MARGIN_MM
    )
    top = PLATE_THICKNESS / 1000.0
    mid_model = (mx / 1000.0, top, mz / 1000.0)
    view = _early_bound(
        place_view(adapter, str(source), "*Top", *PROBE_CROP_CENTRE, scale=PROBE_SCALE), "IView"
    )
    name = view_name(adapter, view)
    ratio = tuple(float(value) for value in view.ScaleRatio)
    landed = model_point_in_view(adapter, view, mid_model, label="dowel pair midpoint")
    position = tuple(float(value) for value in view.Position)
    target = [position[i] + PROBE_CROP_CENTRE[i] - landed[i] for i in range(2)]
    moved = bool(view.SetViewPosition(double_array(target), False))
    draw.EditRebuild3()
    centre = model_point_in_view(adapter, view, mid_model, label="dowel pair midpoint")
    _info(f"p1 view {name!r} scale {ratio}; midpoint landed {tuple(round(v * 1000, 2) for v in landed)} mm, "
          f"SetViewPosition -> {moved}, now {tuple(round(v * 1000, 2) for v in centre)} mm "
          f"(target {tuple(round(v * 1000, 2) for v in PROBE_CROP_CENTRE)}); outline before crop {_outline(view)} mm")
    if not ddoc.ActivateView(name):
        raise RuntimeError(f"cannot activate {name!r}")
    draw.ClearSelection2(True)
    sheet_radius = radius_mm * ratio[0] / ratio[1] / 1000.0
    _sketch_circle(adapter, view, centre, sheet_radius)
    status = int(view.Crop2(False, False, 5))
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    cropped = bool(view.IsCropped())
    expected = tuple(round(v * 1000, 2) for v in (
        centre[0] - sheet_radius, centre[1] - sheet_radius, centre[0] + sheet_radius, centre[1] + sheet_radius))
    _info(f"p1 Crop2 status {status} (1 = no error), IsCropped {cropped}; crop radius {radius_mm:.2f} mm model; "
          f"outline after crop {_outline(view)} mm vs circle bbox {expected} mm")
    if status != _CROP_NO_ERROR or not cropped:
        raise RuntimeError(f"view not cropped: Crop2 {status}, IsCropped {cropped}")
    set_hidden_lines_removed(adapter, view)
    _info(f"p1 outline after HLR {_outline(view)} mm")

    rims = _dowel_edges(adapter, view, ream_radius_m=PLATE_DOWEL_REAM_DIA / 2000.0)
    if not rims:
        raise RuntimeError("the cropped view exposes no ream-radius rim")
    sheet_of = {
        id(edge): model_point_in_view(adapter, view, c, label="rim centre") for c, edge in rims
    }
    edge = min(
        (edge for _, edge in rims),
        key=lambda e: math.dist(sheet_of[id(e)], PROBE_CALLOUT_XY),
    )
    rim_xy = sheet_of[id(edge)]
    _info(f"p1 chosen rim centre on sheet {tuple(round(v * 1000, 2) for v in rim_xy)} mm; "
          f"callout at {tuple(round(v * 1000, 2) for v in PROBE_CALLOUT_XY)} mm")
    _select_view_entity(adapter, view, "EDGE", None, label="p1 dowel rim", entity=edge)
    display = ddoc.AddHoleCallout2(PROBE_CALLOUT_XY[0], PROBE_CALLOUT_XY[1], 0.0)
    _info(f"p1 AddHoleCallout2 -> {'None' if display is None else 'a display dimension'}")
    if display is None:
        raise RuntimeError("AddHoleCallout2 returned None on the cropped view")
    accepted = bool(adapter.swApp.RunCommand(-2, ""))  # swCommands_PmOK
    display = _early_bound(display, "IDisplayDimension")
    annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
    _info(f"p1 PmOK {accepted}; IsHoleCallout {bool(display.IsHoleCallout())}; "
          f"owner view of the annotation: {view_name(adapter, view)!r}")
    annotation.SetPosition2(PROBE_CALLOUT_XY[0], PROBE_CALLOUT_XY[1], 0.0)
    _read_callout("p1 native", display)
    existing = str(display.GetText(5) or "")
    prefixed = process.rstrip() + " " + existing.lstrip()
    display.SetText(1, prefixed)
    _info(f"p1 RD3 prefix persisted={str(display.GetText(5) or '') == prefixed}")
    set_hole_callout_precision(display, {"hw-diam": 3}, label=f"{TAG} p1 dowel ream diameter")
    draw.ClearSelection2(True)
    rebuild_drawing(adapter, label=f"{TAG} p1 callout")
    _read_callout("p1 RD3 recipe", display)
    items = _measure(adapter, "p1", owners=(name,))
    for sheet, item in items:
        findings = [f for f in audit_sheet(sheet) if item.label in (f.a, f.b)]
        _info(f"p1 audit findings naming {item.label!r}: {len(findings)}")
        for finding in findings:
            _info(f"p1 finding {finding.kind} {finding.a}/{finding.b}: {finding.detail}")


# --------------------------------------------------------------- export, run
def _export_pdf(adapter: Any, out_dir: Path) -> None:
    draw = adapter.currentModel
    before = (str(draw.GetPathName() or ""), str(draw.GetTitle() or ""))
    out_dir.mkdir(parents=True, exist_ok=True)
    pdf = out_dir / "mha091-probe.pdf"
    if pdf.exists():
        pdf.unlink()
    result = draw.SaveAs3(str(pdf), 0, 0)
    after = (str(draw.GetPathName() or ""), str(draw.GetTitle() or ""))
    _info(f"pdf SaveAs3 -> {result!r}; path/title before {before} after {after}; "
          f"size {pdf.stat().st_size if pdf.exists() else 'absent'}")
    if not pdf.exists():
        return
    blob = base64.b64encode(pdf.read_bytes()).decode("ascii")
    chunks = [blob[i : i + 8000] for i in range(0, len(blob), 8000)]
    for index, chunk in enumerate(chunks):
        _info(f"pdf {index + 1}/{len(chunks)} {chunk}")


def _describe(adapter: Any, label: str) -> None:
    from diagnostics.drawing_layout_audit import describe_sheet  # noqa: PLC0415

    for sheet in _sheets(adapter):
        for line in describe_sheet(sheet).splitlines():
            _info(f"{label} | {line}")


def run(
    adapter: Any,
    *,
    source: Path,
    slddrw: Path,
    dowel_callout: Any,
    process: str,
    out_dir: Path,
) -> None:
    """Every probe, the discard, the hash proof; always raises at the end."""
    from _common import discard_open_documents  # noqa: PLC0415

    files = {"source SLDPRT": source, "SLDDRW": slddrw}
    before = {name: file_stamp(path) for name, path in files.items()}
    _info(f"stamps before {json.dumps(before)}")
    _guard("p2", lambda: probe_line_break(adapter, dowel_callout, process=process))
    _guard("p1", lambda: probe_cropped_view(adapter, source=source, process=process))
    _guard("sheet dump", lambda: _describe(adapter, "after"))
    _guard("pdf", lambda: _export_pdf(adapter, out_dir))
    discard_open_documents(adapter)
    after = {name: file_stamp(path) for name, path in files.items()}
    _info(f"stamps after discard {json.dumps(after)}")
    ok, rows = discard_verdict(before, after)
    for row in rows:
        _info(f"discard proof {row}")
    _info(f"discard proof verdict: {'NOTHING SAVED' if ok else 'A FILE CHANGED'}")
    raise RuntimeError(
        f"{TAG}: diagnostic complete (discard proof {'ok' if ok else 'FAILED'}); "
        "this leaf fails by design so nothing is saved or cached"
    )
