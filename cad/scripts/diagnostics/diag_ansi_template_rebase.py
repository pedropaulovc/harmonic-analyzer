"""diag (never merge): re-base ONE project template from its ISO base to true ANSI.

Evidence-first leaf for the true-ANSI template change (#923, user ruling
2026-09-26 decision 3 option A). ``argv[1]`` names the drawing template
(``landscape`` or ``portrait``). On a copy of it under ``cad/out/templates``:

B0  open the template and dump every document preference (2191 reads, the
    maxmin blast-radius set) -- the template's OWN baseline;
B1  write swDetailingDimensionStandard 2 then 1 (the ISO -> ANSI sequence that
    printed MAX in maxmin-diag pass 2 / blast v2), dump, and compare the delta
    with ``ansi_template_manifest``: every row must move to ``iso_to_ansi`` and
    nothing else may move;
B2  write the manifest's ``restore`` rows, dump, and require manifest rows ==
    ``target`` and every other preference == B0;
B2R SaveAs the re-based template, close it, reopen the SAVED file, dump, and
    require B2R == B2 (every write, the precision 2 included, survives);
B3  create a drawing from the SAVED file, dump, and require B3 == B2.

Then probes on drawings from the re-based and the ORIGINAL template (the
negative control), each made two ways: plainly (``new_drawing``) and the way
the build makes a sheet (``new_project_drawing``: units, the 372 pin, ink).
``project_delta`` is every setting that differs between the two built sheets;
it may hold only the manifest's unpinned ANSI rows, and the four generic
leader-style rows must read 2 on the re-based built sheet (user ruling). On
each drawing:
* limit text: a sheet-sketch line dimensioned twice, one swTolMAX and one
  swTolMIN, read through ``IAnnotation::GetDisplayData`` (the limit-text gate's
  reader; it agreed with the PDF in the blast leaf), then the limit-text gate
  ``assert_no_iso_limit_text`` itself: it must pass on the re-based probe
  (positive control, >= 2 scanned) and fail on the original (negative control);
* surface finish: three machining-required symbols carrying "Ra 3.2" in text
  index 8 (RoughnessValue1, today's ISO field), 5 (MaximumRoughness) and 4
  (OtherRoughnessValue), each placed and read back as rendered text; text 5
  must print on both re-based sheets (user ruling: every drawing Ra moves
  there); on the plain drawings, one text-8 symbol per
  swDetailingSFSymbolStandard value.

Last, the part template: a copy re-based 13 = 2 -> 1 (nothing else; the part
side is not ruled yet), and a part from it and from the original, each with
one unattached symbol per text field (8/5/4, the ``_part_pmi`` no-face call).
Text 8 must print on the original part, or the read-back proves nothing.

Every document is closed and proven gone before the next step reads a file.
Everything is logged (``ansi-rebase`` lines); the JSON report (every manifest
row's measured value at B0..B3, plus the full dumps) and the PDFs ride the task
log as base64 so a FAILED leaf still leaves its evidence. The leaf fails loud
at the end if any check failed.
"""

from __future__ import annotations

import base64
import dataclasses
import gzip
import hashlib
import json
import shutil
import socket
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _drawing_common
import _maxmin_prefs as tables
import _telemetry
import ansi_template_manifest as manifest
from _common import PART_TEMPLATE, _early_bound, check, run_build
from _drawing_limit_text import ISO_LIMIT_WORD, assert_no_iso_limit_text
from _drawing_registry import DRAWING_TEMPLATES, DrawingLayout
from solidworks_mcp.adapters.solidworks.drawing import new_drawing

OUT_DIR = Path(__file__).resolve().parents[2] / "out" / "templates"
_DOC_PART, _DOC_DRAWING = 1, 3  # swDocumentTypes_e
_OPEN_SILENT = 1  # swOpenDocOptions_e.swOpenDocOptions_Silent
_TOL_MIN, _TOL_MAX = 5, 6  # swTolType_e
_SF_MACHINING_REQUIRED = 1  # swSFSymType_e.swSFMachining_Req (installed R2026x)
_SF_FIELDS = {8: "RoughnessValue1", 5: "MaximumRoughness", 4: "OtherRoughnessValue"}
_SF_TEXT = "Ra 3.2"
_TEXT_FORMAT_FIELDS = (
    "TypeFaceName",
    "CharHeight",
    "CharHeightInPts",
    "IsHeightSpecifiedInPts",
    "Bold",
    "Italic",
    "Underline",
    "Strikeout",
    "WidthFactor",
    "CharSpacingFactor",
    "LineSpacing",
    "LineLength",
    "ObliqueAngle",
    "Escapement",
    "Vertical",
    "BackWards",
    "UpsideDown",
)
_SF_STANDARD_PREF = tables.INTEGER["swDetailingSFSymbolStandard"]

_findings: list[str] = []
_report: dict[str, Any] = {}


def _log(message: str) -> None:
    _telemetry.warn(f"ansi-rebase {message}")


def _finding(message: str) -> None:
    _findings.append(message)
    _log(f"FINDING {message}")


def _stamp(path: Path) -> str:
    return f"size={path.stat().st_size} sha256={hashlib.sha256(path.read_bytes()).hexdigest()}"


def _emit_blob(tag: str, data: bytes) -> None:
    blob = base64.b64encode(gzip.compress(data)).decode("ascii")
    chunks = [blob[i : i + 8000] for i in range(0, len(blob), 8000)]
    for index, chunk in enumerate(chunks):
        print(f"ansi-rebase blob {tag} {index + 1}/{len(chunks)} {chunk}", flush=True)


# --- preference dump (the maxmin blast-radius read set) -----------------------


def _text_format(ext: Any, pref: int, option: int) -> dict[str, object] | None:
    raw = ext.GetUserPreferenceTextFormat(pref, option)
    if raw is None:
        return None
    fmt = _early_bound(raw, "ITextFormat")
    out: dict[str, object] = {}
    for field in _TEXT_FORMAT_FIELDS:
        value = getattr(fmt, field)
        out[field] = value() if callable(value) else value
    return out


def _read(ext: Any, kind: str, pref: int, option: int) -> object:
    if kind == "integer":
        return int(ext.GetUserPreferenceInteger(pref, option))
    if kind == "toggle":
        return bool(ext.GetUserPreferenceToggle(pref, option))
    if kind == "double":
        return round(float(ext.GetUserPreferenceDouble(pref, option)), 9)
    if kind == "string":
        return str(ext.GetUserPreferenceString(pref, option))
    return _text_format(ext, pref, option)


def _dump(ext: Any) -> dict[str, object]:
    reads = [
        (kind, name, "-")
        for kind in ("integer", "toggle", "double", "string", "text_format")
        for name in getattr(tables, kind.upper())
    ]
    reads += list(tables.PAIRS)
    out: dict[str, object] = {}
    for kind, name, option in reads:
        pref = getattr(tables, kind.upper())[name]
        opt = 0 if option == "-" else tables.OPTION[option]
        try:
            out[f"{kind}|{name}|{option}"] = _read(ext, kind, pref, opt)
        except Exception as exc:  # noqa: BLE001 - diagnostic read
            out[f"{kind}|{name}|{option}"] = f"ERR {type(exc).__name__}"
    return out


def _record(state: str, dump: dict[str, object]) -> None:
    """Keep the measured values: the full dump per state, and every manifest
    row's value per state (the user's B0-vs-B3 table reads these, never the
    manifest's own expectations)."""
    _report.setdefault("dumps", {})[state] = dump
    rows = _report.setdefault("rows", {})
    for setting in manifest.SETTINGS:
        key = manifest.key(setting)
        rows.setdefault(key, {})[state] = dump.get(key)


def _noise(key: str, before: object, after: object) -> bool:
    """The two read artefacts the blast leaf proved: DimXpert part doubles read
    as denormals on a drawing, and a text-format field read as a bound method."""
    if "|swPartDimXpert" in key:
        return True
    return "bound method" in repr(before) or "bound method" in repr(after)


def _height(value: object) -> tuple[float, int] | None:
    if not isinstance(value, dict):
        return None
    return (round(float(value["CharHeight"]), 6), int(value["CharHeightInPts"]))


def _matches(setting: manifest.Setting, actual: object, expected: object) -> bool:
    if setting.kind == "text_format":
        return _height(actual) == (round(expected[0], 6), expected[1])
    if setting.kind == "double":
        return abs(float(actual) - float(expected)) < 1e-9
    return actual == expected


def _without_height(value: object) -> object:
    if not isinstance(value, dict):
        return value
    return {
        k: v for k, v in value.items() if k not in ("CharHeight", "CharHeightInPts")
    }


def _compare(
    state: str,
    reference: dict[str, object],
    actual: dict[str, object],
    expected: dict[str, object],
) -> dict[str, int]:
    """Manifest rows must equal ``expected``; every other key must equal
    ``reference``. A text format's non-height fields must equal ``reference``."""
    rows = {manifest.key(s): s for s in manifest.SETTINGS}
    counts = {"checked": 0, "noise": 0, "bad": 0}
    for key, before in reference.items():
        after = actual.get(key)
        counts["checked"] += 1
        setting = rows.get(key)
        if setting is not None:
            if not _matches(setting, after, expected[key]):
                counts["bad"] += 1
                _finding(
                    f"{state}: {key} reads {after!r}, manifest wants {expected[key]!r}"
                )
            if setting.kind == "text_format" and _without_height(
                after
            ) != _without_height(before):
                counts["bad"] += 1
                _finding(
                    f"{state}: {key} moved a non-height field: {before!r} -> {after!r}"
                )
            continue
        if before == after:
            continue
        if _noise(key, before, after):
            counts["noise"] += 1
            continue
        counts["bad"] += 1
        _finding(f"{state}: {key} moved outside the manifest: {before!r} -> {after!r}")
    _log(f"{state}: {counts}")
    return counts


# --- template editing ----------------------------------------------------------


def _standard(ext: Any) -> dict[str, object]:
    return {
        "standard": int(ext.GetUserPreferenceInteger(manifest.STANDARD_PREF, 0)),
        "name": str(ext.GetUserPreferenceString(manifest.STANDARD_NAME_PREF, 0)),
        "sf_standard": int(ext.GetUserPreferenceInteger(_SF_STANDARD_PREF, 0)),
        "uppercase": {
            name: bool(ext.GetUserPreferenceToggle(pref, 0))
            for name, pref in manifest.FORBIDDEN_TOGGLES.items()
        },
    }


def _open(adapter: Any, path: Path, doc_type: int = _DOC_DRAWING) -> Any:
    result = adapter.swApp.OpenDoc6(str(path), doc_type, _OPEN_SILENT, "", 0, 0)
    model = result[0] if isinstance(result, tuple) else result
    if not model:
        raise RuntimeError(f"OpenDoc6 failed for {path}: {result!r}")
    model = _early_bound(model, "IModelDoc2")
    adapter.currentModel = model
    return model


def _resident(adapter: Any) -> list[tuple[str, str]]:
    """(title, path) of every document in the session, hidden ones included."""
    out: list[tuple[str, str]] = []
    doc = adapter.swApp.GetFirstDocument()
    while doc is not None:
        doc = _early_bound(doc, "IModelDoc2")
        out.append((str(doc.GetTitle()), str(doc.GetPathName() or "")))
        doc = doc.GetNext()
    return out


def _close(adapter: Any, model: Any) -> None:
    """Close ``model`` and fail loud if it is still resident, so the next
    step reads the saved file, never the in-memory document."""
    title = str(model.GetTitle())
    path = str(model.GetPathName() or "")
    adapter.swApp.CloseDoc(title)
    adapter.currentModel = None
    left = [
        (t, p)
        for t, p in _resident(adapter)
        if t == title or (path and p and Path(p).resolve() == Path(path).resolve())
    ]
    if left:
        raise RuntimeError(f"{title!r} is still resident after CloseDoc: {left}")
    _log(f"closed {title!r}; resident now {_resident(adapter)!r}")


def _write_restores(ext: Any, baseline: dict[str, object]) -> None:
    for setting in manifest.restores():
        if setting.kind == "double":
            ok = ext.SetUserPreferenceDouble(
                setting.pref, setting.option_id, float(setting.target)
            )
        elif setting.kind == "integer":
            ok = ext.SetUserPreferenceInteger(
                setting.pref, setting.option_id, int(setting.target)
            )
        elif setting.kind == "text_format":
            fmt = _early_bound(
                ext.GetUserPreferenceTextFormat(setting.pref, setting.option_id),
                "ITextFormat",
            )
            before = baseline.get(manifest.key(setting))
            if isinstance(before, dict) and before.get("IsHeightSpecifiedInPts"):
                fmt.CharHeightInPts = int(setting.target[1])
            else:
                fmt.CharHeight = float(setting.target[0])
            # A height write reset LineSpacing 1 mm -> 0 on 8 view-label
            # formats (leaf ansi-rebase-4493): carry every other field from B0.
            if isinstance(before, dict):
                for field in _TEXT_FORMAT_FIELDS:
                    if field in (
                        "CharHeight",
                        "CharHeightInPts",
                        "IsHeightSpecifiedInPts",
                    ):
                        continue
                    current = getattr(fmt, field)
                    if callable(current):
                        continue
                    if current != before[field]:
                        setattr(fmt, field, before[field])
            ok = ext.SetUserPreferenceTextFormat(setting.pref, setting.option_id, fmt)
        else:
            raise RuntimeError(
                f"unexpected restore kind {setting.kind} ({setting.name})"
            )
        if not ok:
            _finding(f"write returned {ok!r} for {manifest.key(setting)}")


def _save_standard(ext: Any, path: Path) -> bool:
    try:
        return bool(ext.SaveDraftingStandard(str(path)))
    except Exception as exc:  # noqa: BLE001 - diagnostic
        _log(f"SaveDraftingStandard({path.name}) raised {exc!r}")
        return False


# --- probes on a drawing made from a template ------------------------------------


def _rendered(annotation: Any) -> list[str] | None:
    data = annotation.GetDisplayData()
    if data is None:
        return None
    data = _early_bound(data, "IDisplayData")
    return [str(data.GetTextAtIndex(i)) for i in range(int(data.GetTextCount()))]


def _sheet_line(
    adapter: Any, draw: Any, start: tuple[float, float], end: tuple[float, float]
) -> Any:
    sketch_manager = _early_bound(draw.SketchManager, "ISketchManager")
    previous = bool(sketch_manager.AddToDB)
    sketch_manager.AddToDB = True
    try:
        segment = sketch_manager.CreateLine(
            start[0], start[1], 0.0, end[0], end[1], 0.0
        )
    finally:
        sketch_manager.AddToDB = previous
    if segment is None:
        raise RuntimeError("sheet-sketch line was not created")
    return segment


def _limit_probe(adapter: Any, draw: Any, tag: str) -> dict[str, object]:
    ddoc = _early_bound(draw, "IDrawingDoc")
    ddoc.EditSheet()
    manager = _early_bound(draw.SelectionManager, "ISelectionMgr")
    out: dict[str, object] = {}
    for tol_type, y in ((_TOL_MAX, 0.18), (_TOL_MIN, 0.13)):
        segment = _sheet_line(adapter, draw, (0.10, y), (0.16, y))
        draw.ClearSelection2(True)
        data = manager.CreateSelectData()
        if not _early_bound(segment, "ISketchSegment").Select4(False, data):
            raise RuntimeError(f"{tag}: could not select the probe line")
        display = draw.AddDimension2(0.13, y + 0.012, 0.0)
        draw.ClearSelection2(True)
        if display is None:
            raise RuntimeError(f"{tag}: AddDimension2 returned None")
        display = _early_bound(display, "IDisplayDimension")
        dimension = _early_bound(display.GetDimension2(0), "IDimension")
        tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
        tolerance.Type = tol_type
        applied = int(tolerance.Type)
        draw.EditRebuild3()
        draw.ForceRebuild3(False)
        texts = _rendered(_early_bound(display.GetAnnotation(), "IAnnotation"))
        word = "MAX" if tol_type == _TOL_MAX else "MIN"
        joined = " ".join(texts or ())
        out[word] = {
            "tolerance_type": applied,
            "texts": texts,
            "iso_word": bool(ISO_LIMIT_WORD.search(joined)),
            "asme_word": word in joined,
        }
        _log(f"{tag}: limit {word} type={applied} texts={texts!r}")
    try:
        scanned = assert_no_iso_limit_text(draw, label=f"ansi-probe-{tag}")
        out["gate"] = {"passed": True, "scanned": scanned}
    except RuntimeError as exc:
        out["gate"] = {"passed": False, "error": str(exc)}
    _log(f"{tag}: assert_no_iso_limit_text {out['gate']!r}")
    return out


def _sf_symbol(
    draw: Any, tag: str, index: int, x: float, y: float
) -> dict[str, object]:
    """Insert one machining-required symbol, write ``Ra 3.2`` to text
    ``index``, regenerate, and read back what it prints."""
    draw.ClearSelection2(True)
    raw = draw.Extension.InsertSurfaceFinishSymbol3(
        _SF_MACHINING_REQUIRED, 0, x, y, 0.0, 0, 10, "", "", "", "", "", "", ""
    )  # no leader, no lay, no arrowhead
    if raw is None:
        raise RuntimeError(f"{tag}: InsertSurfaceFinishSymbol3 returned None ({index})")
    symbol = _early_bound(raw, "ISFSymbol")
    ok = bool(symbol.SetText(index, _SF_TEXT))
    annotation = _early_bound(symbol.GetAnnotation(), "IAnnotation")
    # With no leader the insert ignored X/Y and stacked every symbol at the
    # sheet corner (leaf ansi-rebase-4493); place it explicitly.
    placed = bool(annotation.SetPosition2(x, y, 0.0))
    draw.EditRebuild3()
    draw.ForceRebuild3(False)
    rendered = _rendered(annotation)
    own = [str(symbol.GetTextAtIndex(i)) for i in range(int(symbol.GetTextCount()))]
    return {
        "index": index,
        "set": ok,
        "placed": placed,
        "get_text": str(symbol.GetText(index) or ""),
        "display_data": rendered,
        "symbol_texts": own,
        "prints_value": any("3.2" in text for text in (rendered or []) + own),
    }


def _sf_probe(adapter: Any, draw: Any, tag: str) -> dict[str, object]:
    _early_bound(draw, "IDrawingDoc").EditSheet()
    out: dict[str, object] = {}
    for column, (index, field) in enumerate(_SF_FIELDS.items()):
        out[field] = _sf_symbol(draw, tag, index, 0.10 + 0.04 * column, 0.08)
        _log(f"{tag}: sf {field} {out[field]!r}")
    return out


def _sf_standard_sweep(draw: Any, tag: str) -> dict[str, object]:
    """On the PROBE drawing only (never the template): write each
    swDetailingSFSymbolStandard value and insert one text-8 symbol, so an
    empty Ra field can be told apart from a symbol-standard mismatch."""
    ext = draw.Extension
    before = int(ext.GetUserPreferenceInteger(_SF_STANDARD_PREF, 0))
    out: dict[str, object] = {"before": before}
    for column, value in enumerate((0, 1, 2)):  # swDetailingSFSymbolStandard_e
        ok = bool(ext.SetUserPreferenceInteger(_SF_STANDARD_PREF, 0, value))
        reads = int(ext.GetUserPreferenceInteger(_SF_STANDARD_PREF, 0))
        row = _sf_symbol(draw, tag, 8, 0.10 + 0.04 * column, 0.04)
        out[str(value)] = {"set": ok, "reads": reads, **row}
        _log(f"{tag}: sf standard {value} {out[str(value)]!r}")
    return out


def _project_drawing(adapter: Any, layout: DrawingLayout, template: Path) -> Any:
    """A drawing made the build's way (``new_project_drawing``: mm units at 2
    places, the per-scope 372 pin, annotation ink), from ``template`` instead
    of the tracked one. The registry entry is swapped only for this call."""
    spec = DRAWING_TEMPLATES[layout]
    DRAWING_TEMPLATES[layout] = dataclasses.replace(spec, path=template)
    try:
        draw, _sheet = _drawing_common.new_project_drawing(adapter, layout=layout)
    finally:
        DRAWING_TEMPLATES[layout] = spec
    return draw


def _probe(
    adapter: Any,
    template: Path,
    tag: str,
    layout: DrawingLayout,
    mode: str,  # "plain" (new_drawing) | "project" (new_project_drawing)
) -> dict[str, object]:
    if mode == "project":
        draw = _project_drawing(adapter, layout, template)
    else:
        spec = DRAWING_TEMPLATES[layout]
        draw = new_drawing(
            adapter, template=str(template), width=spec.width_m, height=spec.height_m
        )
    ext = draw.Extension
    result: dict[str, object] = {"standard": _standard(ext), "mode": mode}
    result["prefs"] = _dump(ext)
    result["limit"] = _limit_probe(adapter, draw, tag)
    result["surface_finish"] = _sf_probe(adapter, draw, tag)
    if mode == "plain":
        result["sf_standard_sweep"] = _sf_standard_sweep(draw, tag)
    pdf = OUT_DIR / f"{template.stem}-probe-{tag}.pdf"
    if pdf.exists():
        pdf.unlink()
    draw.SaveAs3(str(pdf), 0, 0)
    if pdf.exists():
        _emit_blob(f"pdf-{tag}", pdf.read_bytes())
    else:
        _finding(f"{tag}: probe PDF was not written")
    _close(adapter, draw)
    return result


# --- the part template (_part_pmi writes Ra into text 8 on every part) -----------


async def _part_sf(adapter: Any, template: Path, tag: str) -> dict[str, object]:
    """A part from ``template`` with one small block, then one unattached
    machining-required symbol per text field (the ``_part_pmi`` no-face path),
    each read back as printed text."""
    from solidworks_mcp.adapters.base import ExtrusionParameters

    raw = adapter.swApp.NewDocument(str(template), 0, 0, 0)
    if not raw:
        raise RuntimeError(f"{tag}: NewDocument failed for {template}")
    model = _early_bound(raw, "IModelDoc2")
    adapter.currentModel = model
    ext = model.Extension
    out: dict[str, object] = {"standard": _standard(ext)}
    check(f"{tag} sketch", await adapter.create_sketch("Top"))
    check(f"{tag} rectangle", await adapter.add_rectangle(-0.01, -0.01, 0.01, 0.01))
    check(f"{tag} exit sketch", await adapter.exit_sketch())
    check(
        f"{tag} block", await adapter.create_extrusion(ExtrusionParameters(depth=0.005))
    )
    for column, (index, field) in enumerate(_SF_FIELDS.items()):
        model.ClearSelection2(True)
        raw_symbol = ext.InsertSurfaceFinishSymbol3(
            _SF_MACHINING_REQUIRED,
            0,
            0.02 + 0.01 * column,
            0.02,
            0.005,
            0,
            1,
            "",
            "",
            "",
            "",
            "",
            "",
            "",
        )  # no leader, no lay, closed arrowhead (the _part_pmi no-face call)
        if raw_symbol is None:
            raise RuntimeError(
                f"{tag}: InsertSurfaceFinishSymbol3 returned None ({field})"
            )
        symbol = _early_bound(raw_symbol, "ISFSymbol")
        ok = bool(symbol.SetText(index, _SF_TEXT))
        model.EditRebuild3()
        rendered = _rendered(_early_bound(symbol.GetAnnotation(), "IAnnotation"))
        out[field] = {
            "index": index,
            "set": ok,
            "get_text": str(symbol.GetText(index) or ""),
            "display_data": rendered,
            "prints_value": any("3.2" in text for text in rendered or []),
        }
        _log(f"{tag}: sf {field} {out[field]!r}")
    _close(adapter, model)
    return out


async def _part_probe(adapter: Any) -> dict[str, object]:
    """Re-base a copy of the part template (13 = 2 -> 1, nothing else: the
    part side is not ruled yet) and read Ra from text 8/5/4 on a part made
    from it and on one made from the original (the read-back control)."""
    source = PART_TEMPLATE
    work = OUT_DIR / f"work-{source.name}"
    result = OUT_DIR / f"rebased-{source.name}"
    for path in (work, result):
        if path.exists():
            path.unlink()
    shutil.copyfile(source, work)
    model = _open(adapter, work, _DOC_PART)
    ext = model.Extension
    out: dict[str, object] = {"source": _stamp(source), "b0": _standard(ext)}
    for value in manifest.REBASE_SEQUENCE:
        ext.SetUserPreferenceInteger(manifest.STANDARD_PREF, 0, value)
    model.EditRebuild3()
    out["b1"] = _standard(ext)
    model.SaveAs3(str(result), 0, 1)
    _close(adapter, model)
    work.unlink()
    _log(f"part template b0={out['b0']!r} b1={out['b1']!r}")
    out["rebased"] = await _part_sf(adapter, result, "part-rebased")
    out["original"] = await _part_sf(adapter, source, "part-original")
    if not out["original"]["RoughnessValue1"]["prints_value"]:
        _finding(
            "part control: text 8 prints no Ra on a part from the ORIGINAL template, "
            f"so the part read-back proves nothing: {out['original']['RoughnessValue1']!r}"
        )
    return out


# --- the leaf ----------------------------------------------------------------------


async def build(adapter: Any) -> dict[str, str]:
    layout = (
        DrawingLayout(sys.argv[1]) if len(sys.argv) > 1 else DrawingLayout.LANDSCAPE
    )
    report = OUT_DIR / f"{DRAWING_TEMPLATES[layout].path.stem}-rebase-report.json"
    try:
        result = await _rebase(adapter, layout)
    except Exception as exc:
        _finding(f"aborted: {type(exc).__name__}: {exc}")
        raise
    finally:
        _report["findings"] = _findings
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(_report, indent=1, default=str), encoding="utf-8")
        _emit_blob("report", report.read_bytes())
        _log(
            f"verdict: {len(_findings)} finding(s); sf fields printing: "
            f"{_report.get('sf_fields_printing')}"
        )
    if _findings:
        raise RuntimeError(
            f"ANSI re-base diag: {len(_findings)} finding(s); first: {_findings[0]}"
        )
    return {"template": str(result), "report": str(report)}


async def _rebase(adapter: Any, layout: DrawingLayout) -> Path:
    source = DRAWING_TEMPLATES[layout].path
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    work = OUT_DIR / f"work-{source.name}"
    result = OUT_DIR / source.name
    for path in (work, result):
        if path.exists():
            path.unlink()
    shutil.copyfile(source, work)
    _report.update(
        host=socket.gethostname(), template=source.name, source=_stamp(source)
    )
    _log(f"host={_report['host']} template={source.name} {_report['source']}")

    model = _open(adapter, work)
    ext = model.Extension
    b0 = _dump(ext)
    _record("b0", b0)
    _report["standard_b0"] = _standard(ext)
    _report["standards_b0"] = list(ext.GetDraftingStandardNames() or ())
    _report["sldstd_b0"] = _save_standard(ext, OUT_DIR / f"{source.stem}-b0.sldstd")
    _log(f"B0 {_report['standard_b0']} names={_report['standards_b0']}")
    for setting in manifest.SETTINGS:
        actual = b0.get(manifest.key(setting))
        if not _matches(setting, actual, setting.as_built):
            pinned = manifest.CODE_PINNED.get((setting.pref, setting.option_id))
            tag = " (code-pinned per drawing)" if pinned is not None else ""
            _log(
                f"B0 differs from v2 as_built{tag}: {manifest.key(setting)} = {actual!r}"
            )

    for value in manifest.REBASE_SEQUENCE:
        ok = ext.SetUserPreferenceInteger(manifest.STANDARD_PREF, 0, value)
        _log(f"set 13={value} -> {ok!r}; {_standard(ext)}")
    model.EditRebuild3()
    b1 = _dump(ext)
    _record("b1", b1)
    _report["standard_b1"] = _standard(ext)
    rebase = {manifest.key(s): s.iso_to_ansi for s in manifest.SETTINGS}
    _report["b1"] = _compare("B1 re-base", b0, b1, rebase)

    _write_restores(ext, b0)
    model.EditRebuild3()
    b2 = _dump(ext)
    _record("b2", b2)
    _report["standard_b2"] = _standard(ext)
    targets = {manifest.key(s): s.target for s in manifest.SETTINGS}
    _report["b2"] = _compare("B2 restored", b0, b2, targets)
    _report["sldstd_b2"] = _save_standard(ext, OUT_DIR / f"{source.stem}-b2.sldstd")
    _log(f"B2 {_report['standard_b2']}")

    model.SaveAs3(str(result), 0, 1)  # swSaveAsCurrentVersion, swSaveAsOptions_Silent
    _close(adapter, model)
    if not result.is_file():
        raise RuntimeError(f"re-based template was not saved: {result}")
    work.unlink()
    _report["result"] = _stamp(result)
    _log(f"saved {result.name} {_report['result']}")

    # B2R: reopen the SAVED template itself; every write (the precision 2
    # included) must survive the file round trip.
    reopened = _open(adapter, result)
    b2r = _dump(reopened.Extension)
    _record("b2_reopen", b2r)
    _report["standard_b2_reopen"] = _standard(reopened.Extension)
    _report["b2_reopen"] = _compare("B2R saved template reopened", b2, b2r, targets)
    _close(adapter, reopened)

    rebased = _probe(adapter, result, "rebased", layout, "plain")
    b3 = rebased.pop("prefs")
    _record("b3", b3)
    _report["b3"] = _compare(
        "B3 new drawing from saved template",
        b2,
        b3,
        {manifest.key(s): s.target for s in manifest.SETTINGS},
    )
    control = _probe(adapter, source, "original", layout, "plain")
    _record("control", control.pop("prefs"))
    _report["probe_rebased"] = rebased
    _report["probe_original"] = control

    # The sheet the build actually makes: new_project_drawing from each
    # template. project_delta is every setting a built sheet would change.
    project_rebased = _probe(adapter, result, "project-rebased", layout, "project")
    project_original = _probe(adapter, source, "project-original", layout, "project")
    sheet_rebased = project_rebased.pop("prefs")
    sheet_original = project_original.pop("prefs")
    _record("project_rebased", sheet_rebased)
    _record("project_original", sheet_original)
    _report["probe_project_rebased"] = project_rebased
    _report["probe_project_original"] = project_original
    _report["project_delta"] = {
        key: [before, sheet_rebased.get(key)]
        for key, before in sheet_original.items()
        if before != sheet_rebased.get(key)
        and not _noise(key, before, sheet_rebased.get(key))
    }
    _log(f"project sheet delta: {len(_report['project_delta'])} setting(s)")
    for key, pair in _report["project_delta"].items():
        _log(f"project delta {key}: {pair[0]!r} -> {pair[1]!r}")
    project_gate = project_rebased["limit"]["gate"]
    if not project_gate["passed"] or project_gate["scanned"] < 2:
        _finding(
            f"project sheet: the limit-text gate on the re-based template {project_gate!r}"
        )
    if project_original["limit"]["gate"]["passed"]:
        _finding("project sheet: the limit-text gate passed the original template")

    # A built sheet may change ONLY the ANSI rows the build does not pin; a
    # restore row, or anything outside the manifest, moving on a sheet is a
    # finding. An ANSI row the build overwrites is reported, not failed.
    ansi_rows = {
        manifest.key(s): s
        for s in manifest.SETTINGS
        if s.decision == "ansi" and (s.pref, s.option_id) not in manifest.CODE_PINNED
    }
    for key, (before, after) in _report["project_delta"].items():
        if key not in ansi_rows:
            _finding(
                f"project sheet: {key} moved outside the ANSI rows: {before!r} -> {after!r}"
            )
    _report["project_overridden"] = {
        key: [sheet_rebased.get(key), s.target]
        for key, s in ansi_rows.items()
        if not _matches(s, sheet_rebased.get(key), s.target)
    }
    _log(
        f"project sheet: ANSI rows the build overrides {_report['project_overridden']!r}"
    )
    # User ruling 2026-09-26: the generic leader-style rows count as proven only
    # if a BUILT sheet from the re-based template reads 2.
    generic = {
        f"integer|{name}|-": sheet_rebased.get(f"integer|{name}|-")
        for name in (
            "swDetailingAngularDimLeaderStyle",
            "swDetailingDimensionTextAndLeaderStyle",
            "swDetailingLinearDimLeaderStyle",
            "swDetailingRadialDimLeaderStyle",
        )
    }
    _report["generic_leader_rows_on_sheet"] = {
        "rebased": generic,
        "original": {key: sheet_original.get(key) for key in generic},
    }
    _log(
        f"generic leader rows on a built sheet {_report['generic_leader_rows_on_sheet']!r}"
    )
    for key, value in generic.items():
        if value != 2:
            _finding(
                f"STOP: built sheet from the re-based template reads {key} = {value!r}, not 2"
            )
    # User ruling 2026-09-26: every drawing Ra moves to text 5.
    for tag, probe in (("plain", rebased), ("project", project_rebased)):
        if not probe["surface_finish"]["MaximumRoughness"]["prints_value"]:
            _finding(f"{tag} re-based sheet: text 5 (MaximumRoughness) prints no Ra")

    _report["part"] = await _part_probe(adapter)

    for word in ("MAX", "MIN"):
        if (
            not rebased["limit"][word]["asme_word"]
            or rebased["limit"][word]["iso_word"]
        ):
            _finding(
                f"re-based template prints {rebased['limit'][word]['texts']!r} for {word}"
            )
        if not control["limit"][word]["iso_word"]:
            _finding(
                f"negative control lost its ISO word: {control['limit'][word]['texts']!r}"
            )
    gate = rebased["limit"]["gate"]
    if not gate["passed"] or gate["scanned"] < 2:
        _finding(
            f"positive control: the limit-text gate on the re-based probe {gate!r}"
        )
    if control["limit"]["gate"]["passed"]:
        _finding(
            f"negative control: the limit-text gate passed the original template "
            f"{control['limit']['gate']!r}"
        )
    fields = [f for f, v in rebased["surface_finish"].items() if v["prints_value"]]
    _report["sf_fields_printing"] = fields
    if not fields:
        _finding("no surface-finish text field prints Ra 3.2 on the re-based template")

    return result


if __name__ == "__main__":
    sys.exit(run_build(build))
