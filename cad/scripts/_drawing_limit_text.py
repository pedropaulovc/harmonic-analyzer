"""Rendered-text gate: no toleranced dimension prints ISO's limit words (#923).

SolidWorks words a MAX/MIN tolerance (swTolMAX / swTolMIN) in the document's
base dimension standard. Under ISO the post-mount screw's cut-end break reads
`` 0.1 max. ``; under ANSI it reads `` 0.1 MAX ``, which is ASME Y14.5's form
(maxmin-diag leaf, 2026-09-26). The project templates are named ANSI but are
ISO-based (swDetailingDimensionStandard = 2), so every MAX/MIN in the fleet
printed ``max.``.

The gate reads what the sheet prints: ``IAnnotation::GetDisplayData``, the one
rendered-text read-back. It regenerates first, because a read taken straight
after the standard changed still returned the old words (the diag's first
pass). A dimension whose display data cannot be read fails the gate: an
unread string is not a clean one.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Any

import _telemetry
from _common import _early_bound

_ANNOT_DIM = 4  # swAnnotationType_e.swDisplayDimension
_TOL_NONE = 0  # swTolType_e.swTolNONE

ISO_LIMIT_WORD = re.compile(r"\b(?:max|min)\.", re.IGNORECASE)


def regenerate_drawing(draw: Any) -> None:
    """Force every sheet's dimension text current: rebuild, force-rebuild,
    recompute each view's display geometry, rebuild."""
    ddoc = _early_bound(draw, "IDrawingDoc")
    draw.EditRebuild3()
    draw.ForceRebuild3(False)
    views = [raw_view for row in ddoc.GetViews() or () for raw_view in row or ()]
    for raw_view in views:
        _early_bound(raw_view, "IView").UpdateViewDisplayGeometry()
    draw.EditRebuild3()


def _tolerance_type(annotation: Any) -> int | None:
    """The dimension's tolerance type, or None when it has no dimension to read."""
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    if display is None:
        return None
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    if dimension is None:
        return None
    return int(_early_bound(dimension.Tolerance, "IDimensionTolerance").Type)


def _rendered(annotation: Any) -> list[str] | None:
    data = annotation.GetDisplayData()
    if data is None:
        return None
    data = _early_bound(data, "IDisplayData")
    texts = [
        str(data.GetTextAtIndex(index)) for index in range(int(data.GetTextCount()))
    ]
    return texts or None


def _dimensions(draw: Any) -> Iterator[tuple[str, Any]]:
    """Every display dimension on every sheet, named ``view/annotation``.

    ``IDrawingDoc::GetViews`` leads each sheet's row with the sheet's own
    view, so a dimension placed on the sheet is included."""
    ddoc = _early_bound(draw, "IDrawingDoc")
    views = [
        _early_bound(raw_view, "IView")
        for row in ddoc.GetViews() or ()
        for raw_view in row or ()
    ]
    for view in views:
        for raw in view.GetAnnotations() or ():
            annotation = _early_bound(raw, "IAnnotation")
            if int(annotation.GetType()) != _ANNOT_DIM:
                continue
            yield f"{view.GetName2()}/{annotation.GetName()}", annotation


def assert_no_iso_limit_text(draw: Any, *, label: str) -> int:
    """Regenerate, then fail loud if any toleranced dimension on any sheet
    prints ``max.``/``min.`` or cannot be read. Returns the dimensions scanned.
    A dimension whose tolerance cannot be read is scanned as if toleranced.
    """
    with _telemetry.span("drawing.limit_text", drawing=label):
        regenerate_drawing(draw)
        offenders: list[str] = []
        unreadable: list[str] = []
        scanned = 0
        for where, annotation in _dimensions(draw):
            tolerance = _tolerance_type(annotation)
            if tolerance == _TOL_NONE:
                continue
            scanned += 1
            texts = _rendered(annotation)
            if texts is None:
                unreadable.append(where)
                continue
            hits = [text for text in texts if ISO_LIMIT_WORD.search(text)]
            if hits:
                offenders.append(
                    f"{where} (tolerance type {tolerance}) prints {hits!r}"
                )
        _telemetry.event(
            "drawing.limit_text",
            scanned=scanned,
            offenders=len(offenders),
            unreadable=len(unreadable),
        )
        if unreadable:
            raise RuntimeError(
                f"{label}: no display data for {len(unreadable)} toleranced "
                f"dimension(s), so their printed text is unchecked: {unreadable}"
            )
        if offenders:
            raise RuntimeError(
                f"{label}: {len(offenders)} dimension(s) print ISO limit words, "
                f"not ASME MAX/MIN: {offenders}"
            )
        return scanned
