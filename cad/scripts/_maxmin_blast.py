"""diag (#923 MAX/MIN v2, never merge): how each candidate fix changes a drawing.

After finalize has saved the SLDDRW and PDF, the wrapped ``save_drawing`` runs
four states on the open document, each followed by the same forced regen, a
dump of every document preference, every annotation's rendered text and a PDF:

* ``baseline`` -- as built;
* ``D`` -- ISO base kept, only swDraftingStandardAllUppercaseForDimensionsAnd-
  HoleCallouts (754) set true;
* ``restored`` -- 754 back to its baseline value (proves D is reversible);
* ``A`` -- swDetailingDimensionStandard 13 = 2 (ISO, renames the standard) then
  13 = 1 (ANSI), the sequence that printed MAX in maxmin-diag pass 2.

Every state is logged against the baseline; the PDFs ride the task log as
base64. Nothing is saved: finalize closes the document, and the SLDDRW is
stamped (size, mtime, sha256) before the diag and after the close.
"""

from __future__ import annotations

import base64
import hashlib
import json
import socket
import time
from pathlib import Path
from typing import Any

import _drawing_common
import _telemetry
from _common import _early_bound

_DIR = Path(__file__).resolve().parents[1] / "out" / "reports" / "maxmin-blast"
_STANDARD = 13  # swDetailingDimensionStandard
_STANDARD_NAME = 65  # swDetailingDimensionStandardName
_UPPERCASE_DIMS = 754  # swDraftingStandardAllUppercaseForDimensionsAndHoleCallouts
_TOGGLES = {
    "swDraftingStandardAllUppercaseForDimensionsAndHoleCallouts": 754,
    "swDraftingStandardUppercase": 552,
    "swDetailingAllUpperCase": 538,
}
_TEXT_FORMAT_FIELDS = (
    "TypeFaceName", "CharHeight", "CharHeightInPts", "IsHeightSpecifiedInPts",
    "Bold", "Italic", "Underline", "Strikeout", "WidthFactor", "CharSpacingFactor",
    "LineSpacing", "LineLength", "ObliqueAngle", "Escapement", "Vertical",
    "BackWards", "UpsideDown",
)


def file_stamp(path: Any) -> str:
    file = Path(path)
    stat = file.stat()
    digest = hashlib.sha256(file.read_bytes()).hexdigest()
    return f"size={stat.st_size} mtime_ns={stat.st_mtime_ns} sha256={digest}"


def _field(fmt: Any, field: str) -> object:
    value = getattr(fmt, field)
    return value() if callable(value) else value


def _value(ext: Any, kind: str, pref: int, option: int) -> object:
    if kind == "integer":
        return int(ext.GetUserPreferenceInteger(pref, option))
    if kind == "toggle":
        return bool(ext.GetUserPreferenceToggle(pref, option))
    if kind == "double":
        return float(ext.GetUserPreferenceDouble(pref, option))
    if kind == "string":
        return str(ext.GetUserPreferenceString(pref, option))
    raw = ext.GetUserPreferenceTextFormat(pref, option)
    if raw is None:
        return None
    fmt = _early_bound(raw, "ITextFormat")
    return {field: _field(fmt, field) for field in _TEXT_FORMAT_FIELDS}


def _dump(ext: Any) -> dict[str, object]:
    import _maxmin_prefs as tables

    reads: list[tuple[str, str, str]] = [
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
            value = _value(ext, kind, pref, opt)
        except Exception as exc:  # noqa: BLE001 - diagnostic
            value = f"ERR {type(exc).__name__}"
        out[f"{kind}|{name}|{option}"] = value
    return out


def _views(ddoc: Any) -> list[Any]:
    return [
        _early_bound(raw_view, "IView")
        for row in ddoc.GetViews() or ()
        for raw_view in row or ()
    ]


def _texts(ddoc: Any) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for view in _views(ddoc):
        for raw in view.GetAnnotations() or ():
            annotation = _early_bound(raw, "IAnnotation")
            key = f"{view.GetName2()}/{annotation.GetName()}"
            data = annotation.GetDisplayData()
            if data is None:
                out[key] = ["<no display data>"]
                continue
            data = _early_bound(data, "IDisplayData")
            out[key] = [str(data.GetTextAtIndex(i)) for i in range(int(data.GetTextCount()))]
    return out


def _regen(draw: Any, ddoc: Any) -> float:
    started = time.perf_counter()
    draw.EditRebuild3()
    draw.ForceRebuild3(False)
    for view in _views(ddoc):
        view.UpdateViewDisplayGeometry()
    draw.EditRebuild3()
    return time.perf_counter() - started


def _emit_pdf(state: str, path: Path) -> None:
    blob = base64.b64encode(path.read_bytes()).decode("ascii")
    chunks = [blob[i : i + 8000] for i in range(0, len(blob), 8000)]
    for index, chunk in enumerate(chunks):
        _telemetry.info(f"maxmin-blast pdf {state} {index + 1}/{len(chunks)} {chunk}")


def _standard(ext: Any) -> str:
    toggles = {name: bool(ext.GetUserPreferenceToggle(pref, 0)) for name, pref in _TOGGLES.items()}
    return (
        f"13={ext.GetUserPreferenceInteger(_STANDARD, 0)!r} "
        f"name={ext.GetUserPreferenceString(_STANDARD_NAME, 0)!r} toggles={toggles!r}"
    )


def _state(
    draw: Any,
    ddoc: Any,
    ext: Any,
    state: str,
    baseline: tuple[dict[str, object], dict[str, list[str]]] | None,
) -> tuple[dict[str, object], dict[str, list[str]]]:
    seconds = _regen(draw, ddoc)
    _telemetry.info(f"maxmin-blast state {state}: regen {seconds:.3f} s; {_standard(ext)}")
    prefs = _dump(ext)
    texts = _texts(ddoc)
    errors = sum(1 for value in prefs.values() if str(value).startswith("ERR "))
    _telemetry.info(f"maxmin-blast state {state}: prefs read {len(prefs)}; read errors {errors}")
    pdf = _DIR / f"{state}.pdf"
    if pdf.exists():
        pdf.unlink()
    draw.SaveAs3(str(pdf), 0, 0)
    if baseline is None:
        for key in sorted(texts):
            _telemetry.info(f"maxmin-blast text {state} base {json.dumps([key, texts[key]])}")
        _emit_pdf(state, pdf)
        return prefs, texts
    base_prefs, base_texts = baseline
    rows = [[key, base_prefs[key], prefs.get(key)] for key in base_prefs if base_prefs[key] != prefs.get(key)]
    _telemetry.info(f"maxmin-blast state {state}: prefs differ from baseline {len(rows)}")
    for row in rows:
        _telemetry.info(f"maxmin-blast diff {state} {json.dumps(row, default=str)}")
    for key in sorted(set(base_texts) | set(texts)):
        before, after = base_texts.get(key), texts.get(key)
        tag = "same" if before == after else "DIFF"
        _telemetry.info(f"maxmin-blast text {state} {tag} {json.dumps([key, before, after])}")
    if state != "restored":
        _emit_pdf(state, pdf)
    return prefs, texts


def _blast(adapter: Any) -> None:
    """The four states; never raises."""
    try:
        draw = adapter.currentModel
        ddoc = _early_bound(draw, "IDrawingDoc")
        ext = draw.Extension
        _DIR.mkdir(parents=True, exist_ok=True)
        _telemetry.info(f"maxmin-blast host={socket.gethostname()} title={draw.GetTitle()!r}")
        baseline = _state(draw, ddoc, ext, "baseline", None)
        base_toggle = bool(ext.GetUserPreferenceToggle(_UPPERCASE_DIMS, 0))

        ok = ext.SetUserPreferenceToggle(_UPPERCASE_DIMS, 0, True)
        _telemetry.info(f"maxmin-blast set 754=True -> {ok!r}; {_standard(ext)}")
        _state(draw, ddoc, ext, "D", baseline)

        ok = ext.SetUserPreferenceToggle(_UPPERCASE_DIMS, 0, base_toggle)
        _telemetry.info(f"maxmin-blast set 754={base_toggle} -> {ok!r}; {_standard(ext)}")
        _state(draw, ddoc, ext, "restored", baseline)

        ok = ext.SetUserPreferenceInteger(_STANDARD, 0, 2)
        _telemetry.info(f"maxmin-blast set 13=2 -> {ok!r}; {_standard(ext)}")
        ok = ext.SetUserPreferenceInteger(_STANDARD, 0, 1)
        _telemetry.info(f"maxmin-blast set 13=1 -> {ok!r}; {_standard(ext)}")
        _state(draw, ddoc, ext, "A", baseline)
    except Exception as exc:  # noqa: BLE001 - diagnostic must never fail the leaf
        _telemetry.warn(f"maxmin-blast failed: {exc!r}")


_ORIGINAL_SAVE_DRAWING = _drawing_common.save_drawing


def _save_drawing(adapter: Any, slddrw_path: str, **kwargs: Any) -> dict[str, str]:
    artifacts = _ORIGINAL_SAVE_DRAWING(adapter, slddrw_path, **kwargs)
    _telemetry.info(f"maxmin-blast slddrw pre-diag {file_stamp(artifacts['drawing'])}")
    _blast(adapter)
    return artifacts


_drawing_common.save_drawing = _save_drawing
