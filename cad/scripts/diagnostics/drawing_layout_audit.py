r"""Live sheet-geometry collector for drawing recipes that place annotations.

WHY THIS EXISTS
---------------
Annotation collisions on a drawing sheet were invisible until the PDF/PNG
export -- five to thirteen minutes per look -- so six agents in one afternoon
resorted to rendering the sheet and scoring pixel straddle to find out whether
a dimension had landed on a line.  Every fact they were guessing at is readable
from the live document in ten seconds:

* ``IView::GetOutline`` -- the view's sheet-space box, metres
  (``types/IView/GetOutline.md``: "bounding box for a view (sheet or drawing)
  in meters on the drawing page", ``[xmin, ymin, xmax, ymax]``).
* ``IAnnotation::GetPosition`` -- the annotation's sheet-space origin, and the
  documented meaning of that origin per annotation type
  (``types/IAnnotation/GetPosition.md``: "In a drawing, the x, y, z origin is
  relative to the origin of the drawing sheet (the lower-left corner)"; notes
  anchor at the text box's UPPER-LEFT, display dimensions at the "point of
  leader attachment centered on a text box border / center point of bottom
  border of text box", GD&T frames at the symbol's upper-left, surface finish
  at its lower-left).  The same table governs ``SetPosition2``, so a finding's
  coordinates feed straight back into the fix.
* ``INote::GetExtent`` -- a note's EXACT box, 6 doubles, lower-left then
  upper-right, "in sheet space" (``types/INote/GetExtent.md``).  Not valid for
  invisible documents.
* ``IAnnotation::GetDisplayData`` -> ``IDisplayData`` -- the annotation's real
  rendered primitives: ``GetLineCount``/``GetLineAtIndex3``
  (``[color, lineType, lineStyle, lineWeight, startPt[3], endPt[3]]``,
  ``types/IDisplayData/GetLineAtIndex3.md``), ``GetArcCount``/
  ``GetArcAtIndex2``, ``GetArrowHeadCount``/``GetArrowHeadAtIndex2``, and the
  text items ``GetTextCount`` / ``GetTextAtIndex`` / ``GetTextHeightAtIndex``
  (metres) / ``GetTextPositionAtIndex`` / ``GetTextRefPositionAtIndex``
  (``swTextPosition_e`` corner) / ``GetTextAngleAtIndex`` (radians).  This is
  the dimension LINE and WITNESS LINE geometry that no bounding box exposes.
* ``ISheet::GetProperties2`` -- ``[paperSize, templateIn, scale1, scale2,
  firstAngle, width, height, sameCustomProp]`` (``types/ISheet/GetProperties2.md``);
  ``ISheet::GetZoneMargin(swZoneMargin_e)`` -- the border/zone band the sheet
  format reserves (12.7 mm on every side of tube-frame's portrait sheet); the
  side is an ARGUMENT, not four separate getters.
* ``IDrawingDoc::GetViews`` -- array of arrays, one per sheet, "the first view
  in the list being the sheet itself" (``types/IDrawingDoc/GetViews.md``), so
  every sheet is walked WITHOUT activating it.  That first entry names the
  sheet (``IView::Name``) but its ``IView::Sheet`` is empty, so the ``ISheet``
  comes from ``IDrawingDoc::Sheet(name)``.

Two deliberate non-uses, both documented:

* ``IView::GetDimensionDisplayInfo5`` returns per-dimension lines, arcs,
  arrowheads and text positions in one array -- but only "for the current
  drawing sheet or the current drawing view", and its remarks state it "does
  not support hole callouts" (``types/IView/GetDimensionDisplayInfo5.md``).
  Activating sheets in someone else's live session, and dropping every hole
  callout, are both worse than walking ``GetAnnotations``.
* ``IView::GetFirstDisplayDimension5`` needs the sheet active;
  ``GetFirstDisplayDimension6`` "obsoletes IView::GetFirstDisplayDimension5 by
  supporting inactive sheets" (``types/IView/GetFirstDisplayDimension6.md``).
  ``IView::GetAnnotations`` covers dimensions, notes and GD&T in one pass.

WHAT IT IS FOR
--------------
``collect_document`` reads the adapter's open drawing into
``_layout_geometry.SheetGeometry`` objects, which a few recipes measure to
place text clear of dimension lines before export (cone pivot post, cone
swing platform, pinion arbor). Layout AUDITING is not done here: every
drawing's sheets are judged on the exported PDF by ``_layout_audit`` from
``finalize_drawing`` (cad/docs/drawing-layout-audit.md).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _drawing_common import is_pictorial_orientation  # noqa: E402
from _drawing_types import DRAWING_TEMPLATES  # noqa: E402
from _layout_audit import (
    classify_segments as classify_callout_segments,  # noqa: E402
)
from _layout_geometry import (  # noqa: E402
    AnnotationGeometry,
    Box,
    DrawableRegion,
    Segment,
    SheetGeometry,
    ViewGeometry,
    calibrate_advance_ratio,
    estimate_text_box,
)
import _telemetry  # noqa: E402

# swAnnotationType_e (enums/swAnnotationType_e.md)
_ANNOT_DATUM = 2
_ANNOT_DATUM_TARGET = 3
_ANNOT_DIM = 4
_ANNOT_GTOL = 5
_ANNOT_NOTE = 6
_ANNOT_SFSYM = 7
_ANNOT_WELD = 8
_ANNOT_CUSTOM = 9
_ANNOT_BLOCK = 12
_ANNOT_TABLE = 14
_ANNOT_REVISION_CLOUD = 18

# Which annotation types carry text the audit must place.  Center marks (13),
# centerlines (15), cosmetic threads (1) and datum origins (16) carry no text
# box, and their ink is view geometry rather than annotation ink.
_TEXT_ANNOTATIONS = {
    _ANNOT_DATUM: "datum",
    _ANNOT_DATUM_TARGET: "datum-target",
    _ANNOT_DIM: "dim",
    _ANNOT_GTOL: "gtol",
    _ANNOT_NOTE: "note",
    _ANNOT_SFSYM: "surface-finish",
    _ANNOT_WELD: "weld",
    _ANNOT_CUSTOM: "custom-symbol",
    _ANNOT_BLOCK: "block",
    _ANNOT_REVISION_CLOUD: "revision-cloud",
}

# swLineTypes_e values that mark a leader rather than dimension/witness ink.
# ``IDisplayData::GetLineAtIndex3`` hands back a lineType per line, but the
# enum does not distinguish "leader" from "extension line" -- SolidWorks
# reports both as annotation geometry.  The audit therefore classifies by
# TOPOLOGY: the run that touches the annotation's own text box is its leader,
# everything else is dimension or witness ink.  See :func:`_classify_segments`.
_LEADER_ROLE = "leader"
_LINE_ROLE = "line"

# swDocumentTypes_e.swDocDRAWING
_SW_DOC_DRAWING = 3

# swAnnotationOwner_e.swAnnotationOwner_DrawingSheet -- excludes the sheet
# format's own frame / zone labels / title-block notes, which are template ink
# and not the author's to move.
_OWNER_DRAWING_SHEET = 1


def _attempt(adapter: Any, call, default=None):
    """Adapter ``_attempt`` when present, else a local equivalent.

    Most SolidWorks accessors return None / raise for "not applicable to this
    annotation type" rather than answering, so a tolerant call is required --
    the project convention is ``adapter._attempt``.
    """
    helper = getattr(adapter, "_attempt", None)
    if helper is not None:
        return helper(call, default)
    try:
        return call()
    except Exception:
        return default


def _get(adapter: Any, obj: Any, name: str, default=None):
    """Read a COM member that may be a property or a zero-arg method."""
    helper = getattr(adapter, "_get_attr_or_call", None)
    if helper is not None:
        return _attempt(adapter, lambda: helper(obj, name), default)

    def read():
        value = getattr(obj, name)
        return value() if callable(value) else value

    return _attempt(adapter, read, default)


def _floats(raw: Any) -> list[float]:
    return [float(value) for value in (raw or ())]


def _bind(obj: Any, interface: str) -> Any:
    """Early-bind ``obj`` to ``interface``, as every project COM caller does.

    This is not optional bookkeeping.  A document handed back as an
    ``IModelDoc2`` early-bound wrapper exposes ONLY ``IModelDoc2`` members, so
    ``GetViews`` (an ``IDrawingDoc`` method on the same dispatch) raises
    AttributeError and a tolerant reader turns that into "the drawing has no
    sheets".  Same for ``IView::Sheet`` -> ``ISheet::GetProperties2`` and for
    ``IAnnotation::GetSpecificAnnotation`` -> ``INote::GetExtent``.

    Falls through unchanged when the project's type info cannot bind the object
    (a plain test double, or an interface the typelib does not carry), so the
    collection stays exercisable without a COM seat.
    """
    if obj is None:
        return None
    try:
        from solidworks_mcp.adapters import sw_type_info

        return sw_type_info.early_bound_or_flag(obj, interface)
    except Exception:
        return obj


def _display_data(adapter: Any, annotation: Any) -> Any:
    """``IAnnotation::GetDisplayData`` -> ``IDisplayData``, or None.

    Every annotation type that renders primitives answers this
    (``types/IAnnotation/GetDisplayData.md``); PMI-only annotations do not.
    """
    return _bind(
        _attempt(adapter, lambda: annotation.GetDisplayData()), "IDisplayData"
    )


def _display_lines(adapter: Any, data: Any, dropped: list[int] | None = None) -> list[Segment]:
    """Every straight run of the annotation's ink, in sheet metres.

    ``GetLineAtIndex3`` -> ``[color, lineType, lineStyle, lineWeight,
    startPt[3], endPt[3]]`` (``types/IDisplayData/GetLineAtIndex3.md``).  The
    older ``GetLineAtIndex2`` drops lineStyle/lineWeight, shifting the points
    two slots left, so the index of the start point is read from the array
    LENGTH rather than assumed.

    A record whose ends coincide on the sheet draws no ink and is dropped,
    wherever it lies, and counted into ``dropped`` (``collect_sheet`` puts
    the sheet's total on its span). Since #906 every linear dimension on
    cone_pivot_post reads back 15 such records, ``[0, swLF_VISIBLE,
    swLineHIDDEN, swLW_THIN, (0,0,0), (0,0,0)]``, between its extension and
    dimension lines (diag/cone-pivot-origin-probe fc2212cd6, leaf run
    20260926T205141966Z); boxed as ink, each dimension's box ran from the
    sheet origin.
    """
    count = int(_get(adapter, data, "GetLineCount", 0) or 0)
    segments: list[Segment] = []
    for index in range(count):
        raw = _attempt(adapter, lambda i=index: data.GetLineAtIndex3(i))
        if not raw:
            raw = _attempt(adapter, lambda i=index: data.GetLineAtIndex2(i))
        values = _floats(raw)
        if len(values) < 10:
            continue
        start = len(values) - 6
        segment = Segment(
            values[start],
            values[start + 1],
            values[start + 3],
            values[start + 4],
            _LINE_ROLE,
        )
        if segment.length == 0.0:
            if dropped is not None:
                dropped.append(index)
            continue
        segments.append(segment)
    return segments


def _display_arcs(adapter: Any, data: Any) -> list[Segment]:
    """Arc runs (radial leaders, reference parentheses) as start->end chords.

    ``GetArcAtIndex2`` -> ``[color, lineType, lineStyle, lineWeight,
    startPt[3], endPt[3], centerPt[3], rotationDir]``.  A chord under-reports a
    strongly curved leader's sweep, which is acceptable here: the audit's
    question is whether ink runs through a text box, and an annotation arc on a
    drawing is a shallow fillet or a parenthesis, never a half turn.
    """
    count = int(_get(adapter, data, "GetArcCount", 0) or 0)
    segments: list[Segment] = []
    for index in range(count):
        raw = _attempt(adapter, lambda i=index: data.GetArcAtIndex2(i))
        if not raw:
            raw = _attempt(adapter, lambda i=index: data.GetArcAtIndex(i))
        values = _floats(raw)
        if len(values) < 10:
            continue
        # Layouts differ by overload; the start/end pair always precedes the
        # centre, and the leading scalars are 4 (2 for the older overload).
        head = 4 if len(values) >= 17 else 1
        segments.append(
            Segment(
                values[head],
                values[head + 1],
                values[head + 3],
                values[head + 4],
                _LINE_ROLE,
            )
        )
    return segments


def _display_text_boxes(
    adapter: Any, data: Any, *, advance_ratio: float
) -> tuple[list[Box], list[tuple[str, float, tuple[float, float], int, float]]]:
    """Boxes for each text item the annotation renders, plus their raw samples.

    ``GetTextPositionAtIndex`` is documented as "offset values from the origin
    of this display data" (``types/IDisplayData/GetTextPositionAtIndex.md``).
    On drawing annotations that origin is the sheet origin -- the sibling line
    primitives come back in sheet space (measured on this project's hole
    callouts), and a
    text offset expressed against a different origin than the lines it labels
    would make the two unusable together.  The audit asserts the consequence
    rather than the claim: a text box that lands outside the sheet is dropped
    with a warning instead of producing a phantom finding.

    There is NO API for the text's rendered WIDTH -- see
    ``_layout_geometry.DEFAULT_ADVANCE_RATIO``.
    """
    count = int(_get(adapter, data, "GetTextCount", 0) or 0)
    boxes: list[Box] = []
    samples: list[tuple[str, float, tuple[float, float], int, float]] = []
    for index in range(count):
        text = str(_attempt(adapter, lambda i=index: data.GetTextAtIndex(i)) or "")
        height = float(
            _attempt(adapter, lambda i=index: data.GetTextHeightAtIndex(i), default=0.0)
            or 0.0
        )
        position = _floats(
            _attempt(adapter, lambda i=index: data.GetTextPositionAtIndex(i))
        )
        if not text.strip() or height <= 0 or len(position) < 2:
            continue
        reference = int(
            _attempt(
                adapter,
                lambda i=index: data.GetTextRefPositionAtIndex(i),
                default=0,
            )
            or 0
        )
        angle = float(
            _attempt(
                adapter, lambda i=index: data.GetTextAngleAtIndex(i), default=0.0
            )
            or 0.0
        )
        anchor = (position[0], position[1])
        box = estimate_text_box(
            text,
            anchor=anchor,
            height=height,
            reference=reference if 0 <= reference <= 5 else 0,
            angle=angle,
            advance_ratio=advance_ratio,
        )
        if box is not None:
            boxes.append(box)
            samples.append((text, height, anchor, reference, angle))
    return boxes, samples


def _classify_segments(
    segments: list[Segment], text_boxes: list[Box], *, hole_callout: bool = False
) -> list[Segment]:
    """Mark the runs that reach the annotation's own text as its LEADER.

    ``IDisplayData`` does not label a line's purpose, and the leader is the one
    run whose routing the leader-crossing audit owns (a witness line is
    anchored to geometry and cannot be rerouted).  Topology answers it: the
    leader is what touches the text.  With no text box -- a bare centre mark,
    a symbol-only annotation -- nothing is promoted, so no phantom leader is
    fed to the crossing audit.

    A hole callout is not classified here: the attach run from the rim to
    the shelf need not touch the text (MHA-DT-20 RD1's did not, so a leader
    crossing it went unreported; swing, #902 case 2), and the shared audit
    already owns that rule (``_layout_audit.classify_segments``: every line
    is leader).  This audit has no shoulder role, so the shelf stays leader.
    """
    if hole_callout:
        return classify_callout_segments(
            "hole-callout", {"dim": {"hole_callout": True}}, segments, ()
        )
    if not text_boxes:
        return segments
    grown = [
        Box(box.xmin - 0.001, box.ymin - 0.001, box.xmax + 0.001, box.ymax + 0.001)
        for box in text_boxes
    ]
    classified = []
    for segment in segments:
        touches = any(
            box.xmin <= x <= box.xmax and box.ymin <= y <= box.ymax
            for box in grown
            for x, y in (
                (segment.x0, segment.y0),
                (segment.x1, segment.y1),
            )
        )
        classified.append(
            Segment(
                segment.x0,
                segment.y0,
                segment.x1,
                segment.y1,
                _LEADER_ROLE if touches else segment.role,
            )
        )
    return classified


def _registered_leader_segments(adapter: Any, annotation: Any) -> list[Segment]:
    """Leaders created by ``SetLeader3``, from ``GetLeaderPointsAtIndex``.

    A flat x,y,z stream per leader; consecutive points are joined so a bent
    leader yields its elbow AND its tail.  Native hole callouts and datum
    FEATURE symbols report ``GetLeaderCount() == 0`` even though their leader
    is drawn -- that ink arrives through ``GetDisplayData`` instead, which is
    why both sources are collected.
    """
    count = int(_get(adapter, annotation, "GetLeaderCount", 0) or 0)
    segments: list[Segment] = []
    for index in range(count):
        values = _floats(
            _attempt(adapter, lambda i=index: annotation.GetLeaderPointsAtIndex(i))
        )
        points = [
            (values[i], values[i + 1]) for i in range(0, max(len(values) - 2, 0), 3)
        ]
        for start, end in zip(points, points[1:]):
            segments.append(
                Segment(start[0], start[1], end[0], end[1], _LEADER_ROLE)
            )
    return segments


def _is_hole_callout(adapter: Any, annotation: Any) -> bool:
    """``IDisplayDimension::IsHoleCallout`` for a dimension annotation."""
    display = _bind(
        _attempt(adapter, lambda: annotation.GetSpecificAnnotation()), "IDisplayDimension"
    )
    return display is not None and bool(_get(adapter, display, "IsHoleCallout", False))


def _note_box(adapter: Any, annotation: Any) -> Box | None:
    """A note's EXACT extent: ``INote::GetExtent`` -> 6 doubles, sheet space."""
    note = _bind(
        _attempt(adapter, lambda: annotation.GetSpecificAnnotation()), "INote"
    )
    if note is None:
        return None
    values = _floats(_get(adapter, note, "GetExtent"))
    if len(values) < 6:
        return None
    return Box(
        min(values[0], values[3]),
        min(values[1], values[4]),
        max(values[0], values[3]),
        max(values[1], values[4]),
    )


def _table_geometry(adapter: Any, table: Any) -> AnnotationGeometry | None:
    """Box a table from its anchor plus its column widths and row heights.

    The project's tables are
    inserted top-left anchored, so ``IAnnotation::GetPosition`` on the table's
    underlying annotation is the top-left corner and the box grows right and
    DOWN.  A horizontally split table still reports the source table's total
    ``RowCount``, so ``GetSplitInformation`` bounds the rows this piece renders.
    """
    table = _bind(table, "ITableAnnotation")
    inner = _bind(_get(adapter, table, "GetAnnotation"), "IAnnotation")
    if inner is None:
        return None
    position = _floats(_get(adapter, inner, "GetPosition"))
    if len(position) < 2:
        return None
    label = str(_get(adapter, inner, "GetName", "") or "table")
    rows = int(_get(adapter, table, "RowCount", 0) or 0)
    columns = int(_get(adapter, table, "ColumnCount", 0) or 0)
    row_indices = list(range(rows))
    split = _attempt(adapter, lambda: table.GetSplitInformation(0, 0, 0, 0))
    if split and len(split) >= 5 and int(split[0]) == 1:
        _direction, _index, count, first, last = (int(value) for value in split[:5])
        if count > 1 and 0 <= first <= last < rows:
            row_indices = list(range(first, last + 1))
            if first > 0:
                row_indices.insert(0, 0)  # repeated heading on later pieces
    width = sum(
        float(_attempt(adapter, lambda i=i: table.GetColumnWidth(i), default=0.0) or 0.0)
        for i in range(columns)
    )
    height = sum(
        float(_attempt(adapter, lambda i=i: table.GetRowHeight(i), default=0.0) or 0.0)
        for i in row_indices
    )
    if width <= 0 or height <= 0:
        return None
    x, y = position[0], position[1]
    return AnnotationGeometry(
        label=label,
        kind="table",
        owner="sheet",
        text_boxes=(Box(x, y - height, x + width, y),),
        position=(x, y),
        exact=True,
    )


def _annotation_geometry(
    adapter: Any,
    annotation: Any,
    *,
    owner: str,
    advance_ratio: float,
    dropped: list[int] | None = None,
) -> tuple[AnnotationGeometry | None, list[tuple[str, float, Box]]]:
    """One annotation's text boxes and ink, plus any exact-box calibration
    sample. Zero-length display lines go to ``dropped`` (``_display_lines``)."""
    annotation = _bind(annotation, "IAnnotation")
    kind_code = int(_get(adapter, annotation, "GetType", 0) or 0)
    kind = _TEXT_ANNOTATIONS.get(kind_code)
    if kind is None:
        return None, []
    # A hidden annotation renders nothing, so it can collide with nothing.
    # tube-frame carries exactly one (a swSFSymbol parked at the sheet origin,
    # ``Visible`` = 3 = swAnnotationHidden per ``enums/
    # swAnnotationVisibilityState_e.md``); auditing it reported a bogus
    # 18 mm border breach at (0,0).  ``swAnnotationHalfHidden`` (2) is hidden
    # once a Hide/Show pass ends, so it is skipped too; 0 (unknown) is kept
    # because the property cannot see layer or suppression state.
    if int(_get(adapter, annotation, "Visible", 1) or 1) in (2, 3):
        return None, []
    label = str(_get(adapter, annotation, "GetName", "") or f"annotation{kind_code}")
    position = _floats(_get(adapter, annotation, "GetPosition"))
    anchor = (position[0], position[1]) if len(position) >= 2 else None

    text_boxes: list[Box] = []
    samples: list[tuple[str, float, Box]] = []
    segments: list[Segment] = []

    data = _display_data(adapter, annotation)
    estimated: list[tuple[str, float, tuple[float, float], int, float]] = []
    if data is not None:
        segments.extend(_display_lines(adapter, data, dropped))
        segments.extend(_display_arcs(adapter, data))
        boxes, estimated = _display_text_boxes(
            adapter, data, advance_ratio=advance_ratio
        )
        text_boxes.extend(boxes)

    exact = False
    if kind_code == _ANNOT_NOTE:
        note_box = _note_box(adapter, annotation)
        if note_box is not None:
            # A note's own extent supersedes the estimate AND calibrates it:
            # same font, exact width.  A balloon's extent includes its leader,
            # so only single-text notes are sampled.
            if len(estimated) == 1:
                samples.append((estimated[0][0], estimated[0][1], note_box))
            text_boxes = [note_box]
            exact = True

    if not text_boxes and anchor is not None:
        # No display text came back (a symbol-only annotation, or PMI).  Fall
        # back to the documented anchor so the annotation still participates in
        # the border and keep-out audits rather than vanishing from them.
        text_boxes = [Box(anchor[0], anchor[1], anchor[0], anchor[1])]

    segments = _classify_segments(
        segments,
        text_boxes,
        hole_callout=kind_code == _ANNOT_DIM and _is_hole_callout(adapter, annotation),
    )
    segments.extend(_registered_leader_segments(adapter, annotation))

    return (
        AnnotationGeometry(
            label=label,
            kind=kind,
            owner=owner,
            text_boxes=tuple(text_boxes),
            segments=tuple(segments),
            position=anchor,
            exact=exact,
        ),
        samples,
    )


def _view_geometry(adapter: Any, view: Any, name: str) -> ViewGeometry:
    outline = _floats(_get(adapter, view, "GetOutline"))
    scale = _floats(_get(adapter, view, "ScaleRatio"))
    orientation = str(_get(adapter, view, "GetOrientationName", "") or "")
    return ViewGeometry(
        name=name,
        outline=Box(*outline[:4]) if len(outline) >= 4 else None,
        scale=(scale[0], scale[1]) if len(scale) >= 2 else (1.0, 1.0),
        display_mode=int(_get(adapter, view, "GetDisplayMode2", -1) or -1),
        uses_parent_display=bool(
            _get(adapter, view, "GetUseParentDisplayMode", False)
        ),
        faceted_hlr=bool(_get(adapter, view, "GetFacettedHlrDisplay", False)),
        view_type=int(_get(adapter, view, "Type", -1) or -1),
        pictorial=is_pictorial_orientation(orientation),
    )


def _sheet_region(adapter: Any, sheet: Any, *, width: float, height: float):
    """The drawable region from ``ISheet::GetZoneMargin`` (swZoneMargin_e order)."""
    margins = {}
    for side, code in (("top", 0), ("bottom", 1), ("right", 2), ("left", 3)):
        value = _attempt(adapter, lambda c=code: sheet.GetZoneMargin(c))
        margins[side] = float(value) if value is not None else 0.0
    if not any(margins.values()):
        _telemetry.warn(
            "sheet declares no zone margins; auditing against the full sheet"
        )
        return DrawableRegion.whole_sheet(width, height)
    return DrawableRegion.from_margins(width, height, **margins)


def _keep_outs(width: float, height: float) -> tuple[tuple[str, Box], ...]:
    """The title-block keep-out for whichever checked-in template this sheet is.

    Matched by sheet size against ``_drawing_types.DRAWING_TEMPLATES``,
    so a sheet from a foreign template simply gets no keep-out instead of a
    fabricated one.
    """
    for template in DRAWING_TEMPLATES.values():
        if (
            abs(width - template.width_m) < 1e-6
            and abs(height - template.height_m) < 1e-6
        ):
            return (
                (
                    "title-block",
                    Box(
                        template.title_block_left_m,
                        0.0,
                        width,
                        template.title_block_top_m,
                    ),
                ),
            )
    _telemetry.warn(
        f"sheet {width:g} x {height:g} m matches no checked-in template; "
        "no title-block keep-out is audited"
    )
    return ()


@_telemetry.traced("layout.collect_sheet")
def collect_sheet(
    adapter: Any, drawing: Any, sheet_view: Any, views: list[Any]
) -> SheetGeometry:
    """Read one sheet's whole layout from the live document.

    ``sheet_view`` is the sheet's own ``IView`` (the first entry of that
    sheet's ``IDrawingDoc::GetViews`` row); ``views`` are its drawing views.
    Notes and tables anchored to the SHEET arrive through ``sheet_view``.
    """
    sheet_view = _bind(sheet_view, "IView")
    views = [_bind(view, "IView") for view in views]
    # The sheet's own view names the sheet (``IView::Name``), but its
    # ``IView::Sheet`` is None -- that property answers only for DRAWING views,
    # measured on tube-frame.  ``IDrawingDoc::Sheet(name)`` is the reliable
    # route, and needs no sheet activation; a drawing view's ``Sheet`` is the
    # fallback for a document whose sheet names have been re-mapped.
    name = str(_get(adapter, sheet_view, "Name", "") or "sheet")
    sheet = _bind(_attempt(adapter, lambda: drawing.Sheet(name)), "ISheet")
    if sheet is None and views:
        sheet = _bind(_get(adapter, views[0], "Sheet"), "ISheet")
    if sheet is None:
        raise RuntimeError(f"cannot reach the ISheet behind view {name!r}")
    name = str(_get(adapter, sheet, "GetName", "") or name)
    properties = _floats(_get(adapter, sheet, "GetProperties2"))
    if len(properties) < 7:
        properties = _floats(_get(adapter, sheet, "GetProperties"))
    if len(properties) < 7:
        raise RuntimeError(f"cannot read the size of sheet {name!r}")
    width, height = properties[5], properties[6]

    view_geometry = [
        _view_geometry(adapter, view, str(_get(adapter, view, "Name", "") or "view"))
        for view in views
    ]

    # Two passes: the first harvests exact note extents to calibrate the glyph
    # advance, the second boxes every annotation with the calibrated value.  A
    # sheet carrying no notes keeps the documented default.
    calibration: list[tuple[str, float, Box]] = []
    for view, geometry in [
        *zip(views, view_geometry),
        (sheet_view, None),
    ]:
        for annotation in _get(adapter, view, "GetAnnotations") or []:
            owner = geometry.name if geometry is not None else "sheet"
            _, samples = _annotation_geometry(
                adapter, annotation, owner=owner, advance_ratio=1.0
            )
            calibration.extend(samples)
    advance_ratio = calibrate_advance_ratio(calibration)

    annotations: list[AnnotationGeometry] = []
    seen_tables: dict[str, AnnotationGeometry] = {}
    dropped: list[int] = []
    for view, geometry in [
        *zip(views, view_geometry),
        (sheet_view, None),
    ]:
        owner = geometry.name if geometry is not None else "sheet"
        for annotation in _get(adapter, view, "GetAnnotations") or []:
            if geometry is None:
                # Sheet-owned annotations only: the sheet FORMAT's frame, zone
                # labels and title-block notes are template ink.
                owner_type = int(_get(adapter, annotation, "OwnerType", -1) or -1)
                if owner_type != _OWNER_DRAWING_SHEET:
                    continue
            item, _samples = _annotation_geometry(
                adapter,
                annotation,
                owner=owner,
                advance_ratio=advance_ratio,
                dropped=dropped,
            )
            if item is not None:
                annotations.append(item)
        for table in _get(adapter, view, "GetTableAnnotations") or []:
            item = _table_geometry(adapter, table)
            if item is not None:
                seen_tables[item.label] = item
    annotations.extend(seen_tables.values())
    # The zero-length display lines _display_lines dropped stay visible.
    _telemetry.annotate(sheet=name, degenerate_lines=len(dropped))
    if dropped:
        _telemetry.debug(f"layout {name}: {len(dropped)} zero-length display line(s) dropped, no ink")

    return SheetGeometry(
        name=name,
        width=width,
        height=height,
        region=_sheet_region(adapter, sheet, width=width, height=height),
        keep_outs=_keep_outs(width, height),
        views=tuple(view_geometry),
        annotations=tuple(annotations),
        advance_ratio=advance_ratio,
    )


def collect_document(adapter: Any) -> list[SheetGeometry]:
    """Every sheet of the drawing, without activating any of them.

    ``IDrawingDoc::GetViews`` returns one array per sheet whose first entry is
    the sheet itself (``types/IDrawingDoc/GetViews.md``); sheet order is
    undetermined, so sheets are reported in the order returned and identified
    by ``ISheet::GetName``.
    """
    model = getattr(adapter, "currentModel", None)
    if model is None:
        raise RuntimeError("no drawing document to audit")
    if int(_get(adapter, model, "GetType", 0) or 0) != _SW_DOC_DRAWING:
        raise RuntimeError("layout audit requires a drawing document")
    # Same dispatch, different interface view: ``GetViews`` is an
    # ``IDrawingDoc`` method, invisible through an ``IModelDoc2`` binding.
    drawing = _bind(model, "IDrawingDoc")
    rows = _get(adapter, drawing, "GetViews")
    if not rows:
        raise RuntimeError("drawing reports no sheets")
    sheets = []
    for row in rows:
        entries = list(row or ())
        if not entries:
            continue
        sheets.append(collect_sheet(adapter, drawing, entries[0], entries[1:]))
    return sheets

