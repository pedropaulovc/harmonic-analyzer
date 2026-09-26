"""DIAGNOSTIC ONLY (diag/tolstack branch, never merged): tolerance-stack sweep.

Measures how SolidWorks prints a bilateral/unilateral tolerance stack under
each candidate document-preference combination, on a real seat, from the PDF
it actually exports. Every result is a ``TOLSTACK`` WARN line so it survives
any console verbosity in the farm leaf log.

Enum integers are read off swconst.tlb R2026x (gen_py 4687F359...x0x34x0):
  swUserPreferenceIntegerValue_e.swDetailingDimTrailingZero        = 15
  swUserPreferenceIntegerValue_e.swDetailingTrailingZeroTolerance  = 582
  swUserPreferenceIntegerValue_e.swDetailingToleranceTextSizing    = 23
  swUserPreferenceDoubleValue_e.swDetailingToleranceTextScale      = 21
  swUserPreferenceDoubleValue_e.swDetailingToleranceTextHeight     = 22
  swUserPreferenceToggle_e.swDetailingDimensionsToleranceUseDimensionFont = 157
  swUserPreferenceOption_e.swDetailingNoOptionSpecified            = 0
  swDetailingDimTrailingZero_e: Show 1, RemoveOnlyOnZero 4, Smart 0
  swDetailingToleranceTextSizing_e: UsingScaleValue 1, UsingHeightValue 2
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import _telemetry
from _common import _early_bound
from _pdf_ink import read_pdf_ink

PREF_DIM_TRAILING_ZERO = 15
PREF_TOL_TRAILING_ZERO = 582
PREF_TOL_TEXT_SIZING = 23
PREF_TOL_TEXT_SCALE = 21
PREF_TOL_TEXT_HEIGHT = 22
TOGGLE_TOL_USE_DIM_FONT = 157
NO_OPTION = 0
ZERO_SHOW = 1
ZERO_REMOVE_ONLY_ON_ZERO = 4
SIZING_SCALE = 1
ANNOT_DIM = 4  # swAnnotationType_e.swDisplayDimension

# swUserPreferenceOption_e dimension scopes (same values as _drawing_common).
SCOPES = {
    "dim": 200,
    "angle": 201,
    "arc": 202,
    "chamfer": 203,
    "diameter": 204,
    "hole": 205,
    "linear": 206,
    "ordinate": 207,
    "radius": 208,
    "angular_running": 209,
}


def _say(message: str) -> None:
    _telemetry.warn(f"TOLSTACK {message}")


def _read_prefs(ext: Any) -> dict[str, Any]:
    prefs: dict[str, Any] = {
        "dim_trailing_zero": int(ext.GetUserPreferenceInteger(PREF_DIM_TRAILING_ZERO, NO_OPTION)),
        "tol_trailing_zero": int(ext.GetUserPreferenceInteger(PREF_TOL_TRAILING_ZERO, NO_OPTION)),
    }
    for name, scope in SCOPES.items():
        prefs[f"{name}.use_dim_font"] = bool(ext.GetUserPreferenceToggle(TOGGLE_TOL_USE_DIM_FONT, scope))
        prefs[f"{name}.sizing"] = int(ext.GetUserPreferenceInteger(PREF_TOL_TEXT_SIZING, scope))
        prefs[f"{name}.scale"] = round(float(ext.GetUserPreferenceDouble(PREF_TOL_TEXT_SCALE, scope)), 4)
        prefs[f"{name}.height_mm"] = round(float(ext.GetUserPreferenceDouble(PREF_TOL_TEXT_HEIGHT, scope)) * 1000, 4)
    return prefs


def _set_zero(ext: Any, value: int) -> None:
    ok = ext.SetUserPreferenceInteger(PREF_TOL_TRAILING_ZERO, NO_OPTION, value)
    applied = int(ext.GetUserPreferenceInteger(PREF_TOL_TRAILING_ZERO, NO_OPTION))
    _say(f"set tol_trailing_zero={value}: returned {ok!r}, reads {applied}")


def _set_font(ext: Any, scale: float | None) -> None:
    """``scale=None`` = use the dimension font; otherwise scale-sized text."""
    for name, scope in SCOPES.items():
        use_dim = scale is None
        results = [ext.SetUserPreferenceToggle(TOGGLE_TOL_USE_DIM_FONT, scope, use_dim)]
        if not use_dim:
            results.append(ext.SetUserPreferenceInteger(PREF_TOL_TEXT_SIZING, scope, SIZING_SCALE))
            results.append(ext.SetUserPreferenceDouble(PREF_TOL_TEXT_SCALE, scope, float(scale)))
        read = (
            bool(ext.GetUserPreferenceToggle(TOGGLE_TOL_USE_DIM_FONT, scope)),
            int(ext.GetUserPreferenceInteger(PREF_TOL_TEXT_SIZING, scope)),
            round(float(ext.GetUserPreferenceDouble(PREF_TOL_TEXT_SCALE, scope)), 4),
        )
        _say(f"set font scope={name} scale={scale}: returned {results!r}, reads {read}")


def _toleranced_dimensions(adapter: Any, ddoc: Any, sheet_names: tuple[str, ...]) -> list[tuple[str, Any, Any]]:
    found = []
    for sheet_name in sheet_names:
        sheet = _early_bound(ddoc.Sheet(str(sheet_name)), "ISheet")
        for raw_view in sheet.GetViews() or ():
            view = _early_bound(raw_view, "IView")
            for raw in view.GetAnnotations() or ():
                annotation = _early_bound(raw, "IAnnotation")
                if int(annotation.GetType()) != ANNOT_DIM:
                    continue
                display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
                dimension = display.GetDimension2(0)
                if dimension is None:
                    continue
                dimension = _early_bound(dimension, "IDimension")
                tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
                kind = int(tolerance.Type)
                if kind not in (2, 3, 4):  # BILAT, LIMIT, SYMMETRIC
                    continue
                name = str(dimension.FullName)
                position = annotation.GetPosition() or (0.0, 0.0, 0.0)
                _say(
                    f"dim {name} sheet={sheet_name} view={view.GetName2()} type={kind} "
                    f"min={float(tolerance.GetMinValue())*1000:+.4f} max={float(tolerance.GetMaxValue())*1000:+.4f} "
                    f"font_use_dim={tolerance.GetFontUseDimension()} font_use_scale={tolerance.GetFontUseScale()} "
                    f"font_scale={tolerance.GetFontScale()} font_height_mm={float(tolerance.GetFontHeight())*1000:.4f} "
                    f"tol_precision={display.GetPrimaryTolPrecision2()} "
                    f"pos_mm=({float(position[0])*1000:.2f},{float(position[1])*1000:.2f})"
                )
                found.append((name, tolerance, annotation))
    return found


def _measure(pdf: Path, variant: str) -> list[tuple[int, str]]:
    """Log each nominal span with the spans stacked to its right.

    Returns every printed text span as ``(page, text)`` for the nominal guard.
    """
    printed: list[tuple[int, str]] = []
    for index, page in enumerate(read_pdf_ink(pdf)):
        spans = list(page.spans)
        printed.extend((index, s.text.strip()) for s in spans if s.text.strip())
        for nominal in spans:
            text = nominal.text.strip()
            if not text or not any(ch.isdigit() for ch in text) or "." not in text:
                continue
            h = nominal.ymax - nominal.ymin
            centre = (nominal.ymin + nominal.ymax) / 2
            beside = [
                s
                for s in spans
                if s is not nominal
                and 0.0 <= s.xmin - nominal.xmax <= 4.0 * h
                and abs((s.ymin + s.ymax) / 2 - centre) <= 2.2 * h
                and s.text.strip()
            ]
            above = [
                s
                for s in beside
                if (s.ymin + s.ymax) / 2 > centre + 0.15 * h and any(ch.isdigit() for ch in s.text)
            ]
            if not above:
                continue  # a stack always has a line above the lowest one
            top = max(s.ymax for s in beside)
            bottom = min(s.ymin for s in beside)
            stack_centre = (top + bottom) / 2
            parts = "; ".join(
                f"{s.text.strip()!r} y[{s.ymin*1000:.2f},{s.ymax*1000:.2f}] h={(s.ymax-s.ymin)*1000:.2f} x0={s.xmin*1000:.2f} x1={s.xmax*1000:.2f}"
                for s in sorted(beside, key=lambda s: (-s.ymax, s.xmin))
            )
            _say(
                f"measure variant={variant} page={index} nominal={text!r} "
                f"y[{nominal.ymin*1000:.2f},{nominal.ymax*1000:.2f}] h={h*1000:.2f} x1={nominal.xmax*1000:.2f} "
                f"stack_h={(top-bottom)*1000:.2f} stack_centre_minus_nominal_centre={(stack_centre-centre)*1000:+.2f} "
                f"| {parts}"
            )
    return printed


def _guard(baseline: list[tuple[int, str]], printed: list[tuple[int, str]], variant: str) -> None:
    """Log every printed string a variant added or removed vs the baseline.

    Only tolerance deviations may change; a changed NOMINAL (4.00 -> 4) is
    the stop condition Main set, so every difference is listed verbatim.
    """
    from collections import Counter

    before, after = Counter(baseline), Counter(printed)
    removed = sorted((before - after).elements())
    added = sorted((after - before).elements())
    _say(f"guard variant={variant} spans={len(printed)} removed={removed!r} added={added!r}")


def _export(adapter: Any, draw: Any, pdf: Path, variant: str, rebuild: Any) -> list[tuple[int, str]]:
    rebuild(adapter, label=f"tolstack.{variant}")
    if pdf.exists():
        pdf.unlink()
    draw.SaveAs3(str(pdf), 0, 0)
    if not pdf.is_file():
        _say(f"variant={variant}: PDF export produced no file at {pdf}")
        return []
    return _measure(pdf, variant)


def sweep(adapter: Any, ddoc: Any, sheet_names: tuple[str, ...], out_pdf: Path, rebuild: Any) -> None:
    """Run every variant, then leave the document at the candidate fix."""
    draw = adapter.currentModel
    ext = draw.Extension
    original = _read_prefs(ext)
    _say(f"prefs original {original}")
    dims = _toleranced_dimensions(adapter, ddoc, sheet_names)
    _say(f"toleranced display dimensions: {len(dims)}")
    stem = out_pdf.stem
    folder = out_pdf.parent

    def path(variant: str) -> Path:
        return folder / f"{stem}.tolstack-{variant}.pdf"

    baseline = _export(adapter, draw, path("baseline"), "baseline", rebuild)
    # Main's guard: swDetailingDimTrailingZero (15) is never written here; a
    # refused 582 while 15 reads Smart(0) is reported, not worked around.
    _set_zero(ext, ZERO_REMOVE_ONLY_ON_ZERO)
    # Main's floor: no tolerance scale below 0.84 (Y14.2 3 mm at 3.57 mm text).
    for scale in (None, 1.0, 0.9, 0.85):
        _set_font(ext, scale)
        variant = f"zero4-{'dimfont' if scale is None else f's{scale:g}'}"
        _guard(baseline, _export(adapter, draw, path(variant), variant, rebuild), variant)
    _say(f"prefs after doc sweep {_read_prefs(ext)}")

    # Per-dimension route: doc back to the dimension font, each toleranced
    # dimension scaled on its own IDimensionTolerance.
    _set_font(ext, None)
    saved = []
    for name, tolerance, _annotation in dims:
        saved.append((name, tolerance, bool(tolerance.GetFontUseDimension()), bool(tolerance.GetFontUseScale()), float(tolerance.GetFontScale()), float(tolerance.GetFontHeight())))
        ok = tolerance.SetFont(False, True, 0.85)
        _say(
            f"per-dim SetFont(False, True, 0.85) {name}: returned {ok!r}, reads "
            f"use_dim={tolerance.GetFontUseDimension()} use_scale={tolerance.GetFontUseScale()} scale={tolerance.GetFontScale()}"
        )
    variant = "zero4-perdim-s0.85"
    _guard(baseline, _export(adapter, draw, path(variant), variant, rebuild), variant)
    for name, tolerance, use_dim, use_scale, scale, height in saved:
        ok = tolerance.SetFont(use_dim, use_scale, scale if use_scale else height)
        _say(f"per-dim restore {name}: returned {ok!r}")

    # Candidate left on the document for the declared PDF/PNG: bare-zero
    # tolerances at the dimension font (the size ruling is pending).
    _set_font(ext, None)
    _set_zero(ext, ZERO_REMOVE_ONLY_ON_ZERO)
    rebuild(adapter, label="tolstack.candidate")
    _say(f"prefs candidate {_read_prefs(ext)}")
