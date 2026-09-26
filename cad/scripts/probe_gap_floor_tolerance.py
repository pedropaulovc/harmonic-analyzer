r"""DIAG (never merge): can one sketch diameter carry a per-configuration
tolerance band in SOLIDWORKS 2026, and does it survive save + reopen?

#834 Codex P1 asks the cone gear's gap-floor MIN/MAX band to be a native model
tolerance.  The band differs per configuration (T006 0.04 window, T012 0.25,
T018.. their own MAX), and ``_drawing_marks.set_dimension_symmetric_tolerance``
records that SW2026 rejected ``SetValues2`` on an EXTRUSION DEPTH.  That was
never tried on a sketch diameter, so this leaf tries it (Main, 2026-09-26):

* V0  positive control: LIMIT type, ``SetValues`` (all configurations), the
      form ``_drawing_marks`` already uses on sketch diameters.
* V1  LIMIT, per configuration: activate it, EditSketch, ``SetValues2(.., 1)``
      (the SOLIDWORKS "Change Dimension Tolerance in a Configuration" example).
* V2  LIMIT, per configuration: activate it, ``SetValues2(.., 1)``, no edit.
* V3  LIMIT, one call per configuration, ``SetValues2(.., 3, [name])`` with
      the name list as an explicit ``VT_ARRAY|VT_BSTR`` VARIANT, no switching.
* V4  BILAT +w/0 through V3's form.
* V5  LIMIT, ``SetValues2(.., 2)`` (all configurations), a second control.

Each variant owns its own concentric construction circle in one hidden-free
probe sketch on a COPY of the built part.  Each probed configuration gets a
distinct window (the real ``floor_limits_mm`` window).  The probe reads every
variant back in session, then saves, closes, reopens and reads back again per
configuration, then renders the T006 and T120 front views with the imported
dimensions to PDF/PNG under ``failures/gapfloor-probe/<stamp>/``, and finally
raises through ``capture_com_failure`` so the leaf stores no cache entry.
"""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import _telemetry
from _common import (
    SketchDims,
    _early_bound,
    check,
    define_circle,
    name_last_feature,
)
from _drawing_marks import _named_dimension, mark_dimensions_for_drawing
from _seat_forensics import OUT_FAILURES, capture_com_failure
from cone_gear_spec import floor_limits_mm

PROBE_SKETCH = "GapFloorProbe"
PROBE_CONFIGS = (("T006", 6), ("T012", 12), ("T060", 60), ("T120", 120))
# name -> (circle radius mm, tolerance type, form)
VARIANTS = {
    "ProbeV0": (4.0, 3, "all_setvalues"),
    "ProbeV1": (5.0, 3, "this_config_edit"),
    "ProbeV2": (6.0, 3, "this_config"),
    "ProbeV3": (7.0, 3, "specific"),
    "ProbeV4": (8.0, 2, "specific"),
    "ProbeV5": (9.0, 3, "all_setvalues2"),
}

def _window_m(teeth: int) -> float:
    minimum, maximum = floor_limits_mm(teeth)
    return (maximum - minimum) / 1000.0


def _tolerance(adapter: Any, name: str) -> Any:
    _display, dimension = _named_dimension(adapter, PROBE_SKETCH, name)
    return _early_bound(dimension.Tolerance, "IDimensionTolerance")


def _activate(model: Any, configuration: str) -> bool:
    ok = bool(model.ShowConfiguration2(configuration))
    active = str(_early_bound(model.ConfigurationManager, "IConfigurationManager")
                 .ActiveConfiguration.Name)
    return ok or active == configuration


def _read(adapter: Any, name: str) -> dict[str, Any]:
    try:
        tol = _tolerance(adapter, name)
        return {
            "type": int(tol.Type),
            "min_mm": round(float(tol.GetMinValue()) * 1000.0, 6),
            "max_mm": round(float(tol.GetMaxValue()) * 1000.0, 6),
        }
    except Exception as exc:  # noqa: BLE001 - a probe records, never stops
        return {"error": f"{type(exc).__name__}: {exc}"}


def _read_all(adapter: Any, phase: str) -> dict[str, dict[str, Any]]:
    model = adapter.currentModel
    table: dict[str, dict[str, Any]] = {}
    for configuration, _teeth in PROBE_CONFIGS:
        activated = _activate(model, configuration)
        model.ForceRebuild3(False)
        row = {name: _read(adapter, name) for name in VARIANTS}
        row["_activated"] = activated
        table[configuration] = row
        _telemetry.warn(f"gapfloor probe [{phase}] {configuration}: {json.dumps(row)}")
    return table


def _call(label: str, action: Any) -> Any:
    try:
        result = action()
    except Exception as exc:  # noqa: BLE001
        result = f"raised {type(exc).__name__}: {exc}"
    _telemetry.warn(f"gapfloor probe call {label}: {result!r}")
    return result if isinstance(result, (bool, int, float, str)) else repr(result)


def _set_variants(adapter: Any) -> dict[str, Any]:
    import pythoncom
    from solidworks_mcp.adapters.pywin32_adapter import null_callout
    from win32com.client import VARIANT

    model = adapter.currentModel
    calls: dict[str, Any] = {}
    widest = _window_m(120)
    for name, (_radius, tol_type, form) in VARIANTS.items():
        tol = _tolerance(adapter, name)
        calls[f"{name}.type"] = _call(
            f"{name} type={tol_type}", lambda t=tol, k=tol_type: setattr(t, "Type", k)
        )
        if form == "all_setvalues":
            calls[name] = _call(
                f"{name} SetValues", lambda t=tol: t.SetValues(0.0, widest)
            )
            continue
        if form == "all_setvalues2":
            calls[name] = _call(
                f"{name} SetValues2 all",
                lambda t=tol: t.SetValues2(0.0, widest, 2, None),
            )
            continue
        for configuration, teeth in PROBE_CONFIGS:
            window = _window_m(teeth)
            key = f"{name}@{configuration}"
            if form == "specific":
                calls[key] = _call(
                    f"{key} SetValues2 specific",
                    lambda t=tol, w=window, c=configuration: t.SetValues2(
                        0.0, w, 3, VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_BSTR, [c])
                    ),
                )
                continue
            calls[f"{key}.activate"] = _activate(model, configuration)
            if form == "this_config_edit":
                model.ClearSelection2(True)
                selected = bool(
                    model.Extension.SelectByID2(
                        PROBE_SKETCH, "SKETCH", 0, 0, 0, False, 0, null_callout(), 0
                    )
                )
                calls[f"{key}.select"] = selected
                model.EditSketch()
            tol = _tolerance(adapter, name)
            calls[key] = _call(
                f"{key} SetValues2 this",
                lambda t=tol, w=window: t.SetValues2(0.0, w, 1, ""),
            )
            if form == "this_config_edit":
                model.SketchManager.InsertSketch(True)
                model.ClearSelection2(True)
    return calls


async def _author_probe_sketch(adapter: Any) -> None:
    dims = SketchDims()
    check("create_sketch gapfloor probe", await adapter.create_sketch("Front"))
    for name, (radius, _type, _form) in VARIANTS.items():
        circle = await define_circle(
            adapter, 0.0, 0.0, radius, f"probe {name}", dims=dims,
            names=(None, None, name),
        )
        segment = _early_bound(adapter._sketch_entities[circle], "ISketchSegment")
        segment.ConstructionGeometry = True
        if not bool(segment.ConstructionGeometry):
            raise RuntimeError(f"probe {name} did not take the construction flag")
    check("exit_sketch gapfloor probe", await adapter.exit_sketch())
    name_last_feature(adapter, PROBE_SKETCH)
    dims.apply(adapter, PROBE_SKETCH)
    mark_dimensions_for_drawing(adapter, PROBE_SKETCH, set(VARIANTS))


def _drawing_reads(imported: list[Any]) -> list[dict[str, Any]]:
    """Name, printed text and tolerance of each imported display dimension."""
    reads: list[dict[str, Any]] = []
    for item in imported:
        try:
            display = _early_bound(item, "IDisplayDimension")
            dimension = _early_bound(display.GetDimension2(0), "IDimension")
            tol = _early_bound(dimension.Tolerance, "IDimensionTolerance")
            reads.append({
                "name": str(dimension.Name),
                "text": [str(display.GetText(k)) for k in range(1, 6)],
                "type": int(tol.Type),
                "min_mm": round(float(tol.GetMinValue()) * 1000.0, 6),
                "max_mm": round(float(tol.GetMaxValue()) * 1000.0, 6),
            })
        except Exception as exc:  # noqa: BLE001
            reads.append({"error": f"{type(exc).__name__}: {exc}"})
    return reads


def _render(adapter: Any, copy: Path, out_dir: Path) -> list[str]:
    import draw_cone_gear as sheet
    from _drawing_common import (
        _INSERT_DIMS_MARKED,
        create_blank_drawing_sheets,
        new_project_drawing,
        render_pdf_png,
    )
    from solidworks_mcp.adapters.pywin32_adapter import null_callout
    from solidworks_mcp.adapters.solidworks.drawing import place_view, save_drawing

    rendered: list[str] = []
    names = [c for c, _t in PROBE_CONFIGS if c in ("T006", "T120")]
    drawing_model, _sheet = new_project_drawing(
        adapter, layout=sheet.SPEC.layout, scale=sheet.SHEET_SCALES["T006"]
    )
    create_blank_drawing_sheets(adapter, names, label="gapfloor probe")
    ddoc = _early_bound(drawing_model, "IDrawingDoc")
    for configuration in names:
        ddoc.ActivateSheet(configuration)
        front = place_view(
            adapter, str(copy), "*Front", *sheet.FRONT_CENTER,
            scale=sheet.SHEET_SCALES[configuration],
        )
        sheet._configure_views(adapter, configuration, (front,))
        name = sheet.view_name(adapter, front)
        activated = bool(ddoc.ActivateView(name))
        drawing_model.ClearSelection2(True)
        selected = bool(
            drawing_model.Extension.SelectByID2(
                name, "DRAWINGVIEW", 0.0, 0.0, 0.0, False, 0, null_callout(), 0
            )
        )
        try:
            result = ddoc.InsertModelAnnotations3(
                0, _INSERT_DIMS_MARKED, False, False, True, False
            )
        except Exception as exc:  # noqa: BLE001
            result = None
            rendered.append(f"{configuration}: import raised {type(exc).__name__}: {exc}")
        drawing_model.ClearSelection2(True)
        imported = [] if not result or isinstance(result, str) else list(result)
        rendered.append(
            f"{configuration}: view {name} activated={activated} selected={selected}"
        )
        rendered.append(f"{configuration}: imported {_drawing_reads(imported)}")
    drawing_model.ClearSelection2(True)
    pdf = out_dir / "gapfloor-probe.pdf"
    png = out_dir / "gapfloor-probe.png"
    try:
        save_drawing(adapter, "", pdf_path=str(pdf))
        render_pdf_png(pdf, png, layout=sheet.SPEC.layout, expected_pages=len(names))
        rendered.append(f"exported {pdf.name} {png.name}")
    except Exception as exc:  # noqa: BLE001
        rendered.append(f"export failed {type(exc).__name__}: {exc}")
    return rendered


async def probe(adapter: Any, source: Path) -> None:
    """Run every variant on a copy of ``source``, then raise with the verdict."""
    out_dir = OUT_FAILURES / "gapfloor-probe" / datetime.now(UTC).strftime(
        "%Y%m%dT%H%M%SZ"
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    copy = out_dir / "cone-gear-gapfloor-probe.SLDPRT"
    shutil.copy2(source, copy)
    report: dict[str, Any] = {"source": str(source), "copy": str(copy)}
    with _telemetry.span("diag.gapfloor_probe"):
        check("open probe copy", await adapter.open_model(str(copy)))
        await _author_probe_sketch(adapter)
        report["calls"] = _set_variants(adapter)
        report["in_session"] = _read_all(adapter, "in-session")
        model = adapter.currentModel
        report["save"] = _call("Save3", lambda: model.Save3(1, 0, 0))
        title = str(model.GetTitle())
        report["close"] = _call("CloseDoc", lambda: adapter.swApp.CloseDoc(title))
        check("reopen probe copy", await adapter.open_model(str(copy)))
        report["reopened"] = _read_all(adapter, "reopened")
        report["expected_window_mm"] = {
            c: round(_window_m(t) * 1000.0, 6) for c, t in PROBE_CONFIGS
        }
        try:
            report["render"] = _render(adapter, copy, out_dir)
        except Exception as exc:  # noqa: BLE001
            report["render"] = f"failed {type(exc).__name__}: {exc}"
    (out_dir / "gapfloor-probe.json").write_text(
        json.dumps(report, indent=2, default=repr), encoding="utf-8"
    )
    verdicts = []
    for name in VARIANTS:
        per = {
            c: report["reopened"][c][name].get("max_mm") for c, _t in PROBE_CONFIGS
        }
        verdicts.append(f"{name}={per}")
    capture_com_failure(
        adapter,
        "gapfloor-probe",
        "gapfloor probe finished (deliberate raise, no cache store): "
        f"expected windows {report['expected_window_mm']}; reopened max per "
        f"variant {'; '.join(verdicts)}; report {out_dir / 'gapfloor-probe.json'}",
        api="IDimensionTolerance.SetValues2",
        sketch=PROBE_SKETCH,
    )
