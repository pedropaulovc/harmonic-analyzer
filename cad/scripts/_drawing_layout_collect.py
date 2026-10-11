"""Drawing layout element collection and element-level auditing.

Separate module so edits re-key only recipes that use this concern.
"""

from __future__ import annotations

from typing import Any
from _drawing_layout_check import CollisionScope
from collections import Counter
from _drawing_registry import DRAWING_TEMPLATES
from _drawing_layout_check import DrawableRegion
from _drawing_registry import DrawingLayout
from _drawing_layout_check import LayoutElement
from _drawing_layout_check import LeaderSegment
from _com import _early_bound
from solidworks_mcp.adapters import sw_type_info as _sw_type_info
import _telemetry
from _drawing_layout_audit import annotation_display
from _drawing_layout_check import audit_layout
from itertools import combinations
from _drawing_layout_check import format_findings
from solidworks_mcp.adapters.solidworks.drawing import iter_views
from _layout_audit import line_segment
from dataclasses import replace
from solidworks_mcp.adapters.solidworks.drawing import view_name
from _drawing_balloon_display import rendered_balloon_circle
from _drawing_common import is_pictorial_orientation
from _drawing_gdt_layout import (
    _ANNOT_DATUM,
    _GDT_TYPES,
    _datum_is_dimension_attached,
    _gdt_element,
)
from _drawing_sheet_region import sheet_drawable_region


# swAnnotationType_e.swNote -- the view-owned annotation TYPE that becomes a
# free-standing layout element (the general-notes block, schedule cells). Tables
# are enumerated separately via IView.GetTableAnnotations.
_ANNOT_NOTE = 6


# swAnnotationType_e.swDisplayDimension -- every linear/diameter dimension AND
# the native hole callouts. The element audit gives them NO box: the shared
# layout audit (``_drawing_layout_audit``) boxes their text from its display
# data and checks it against text, lines and model edges on every sheet. The
# 8 mm nominal square they used to get here was never overlap-checked, so
# MHA-DT-021's "20.8"/"8.42" and its callouts over the right view passed.
_ANNOT_DIM = 4


_OWNER_DRAWING_SHEET = 1  # swAnnotationOwner_e.swAnnotationOwner_DrawingSheet


# A note centered inside its owning view is treated as a hole tag / balloon
# (detail on the view) only when it is also SMALL: native hole-table tags span
# ~6 mm, whereas the general-notes block is >50 mm on a side. The size gate keeps
# the exemption narrow so a large general note accidentally dropped onto its own
# view is still audited as a collision (Codex #269).
_TAG_MAX_SPAN_M = 0.015


def _view_scope(adapter: Any, view: Any) -> CollisionScope:
    """``NONE`` for a pictorial view (empty diagonal box), ``ALL`` for an ortho view."""
    orientation = str(adapter._get_attr_or_call(view, "GetOrientationName") or "")
    if is_pictorial_orientation(orientation):
        return CollisionScope.NONE
    return CollisionScope.ALL


def _is_small_tag(element: LayoutElement) -> bool:
    """True if ``element`` is small enough to be a hole tag / balloon, not a block."""
    return (
        element.xmax - element.xmin <= _TAG_MAX_SPAN_M
        and element.ymax - element.ymin <= _TAG_MAX_SPAN_M
    )


def _center_inside(
    element: LayoutElement, outline: tuple[float, float, float, float]
) -> bool:
    """True if ``element``'s center lies within the ``(xmin,ymin,xmax,ymax)`` box."""
    cx = (element.xmin + element.xmax) / 2.0
    cy = (element.ymin + element.ymax) / 2.0
    xmin, ymin, xmax, ymax = outline
    return xmin <= cx <= xmax and ymin <= cy <= ymax


def _note_element(adapter: Any, annotation: Any, name: str) -> LayoutElement | None:
    """Box a free NOTE from ``INote.GetExtent`` (lower-left / upper-right in meters).

    A LEADERED note is deliberately pointing at (and sitting over) view geometry
    -- e.g. an arrowed hole-group tag -- so it is given ``NON_VIEW`` scope: its
    overlap with the view it points at is intended, but a collision with a free
    note / table / title block (and any off-sheet placement) is still audited.
    """
    leadered = int(adapter._get_attr_or_call(annotation, "GetLeaderCount") or 0) > 0
    note = adapter._attempt(
        lambda: adapter._get_attr_or_call(annotation, "GetSpecificAnnotation")
    )
    if note is None:
        return None
    note = _sw_type_info.early_bound_or_flag(
        note, "INote", "GetExtent", "GetText", "IsBomBalloon"
    )
    text = str(adapter._attempt(lambda: note.GetText(), default="") or "")
    diagnostic_name = f"{name} {text!r}" if text else name
    # A BOM balloon's GetExtent includes its leader. Bound the rendered circle,
    # not the annotation origin or INote's potentially stale geometry cache.
    if bool(adapter._attempt(lambda: note.IsBomBalloon(), default=False)):
        cx, cy, half = rendered_balloon_circle(note, label=diagnostic_name)
        return LayoutElement(
            diagnostic_name,
            "note",
            cx - half,
            cy - half,
            cx + half,
            cy + half,
            scope=CollisionScope.NON_VIEW,
        )
    extent = adapter._attempt(lambda: adapter._get_attr_or_call(note, "GetExtent"))
    if not extent:
        return None
    x0, y0, _z0, x1, y1, _z1 = (float(v) for v in extent)
    return LayoutElement(
        diagnostic_name,
        "note",
        min(x0, x1),
        min(y0, y1),
        max(x0, x1),
        max(y0, y1),
        scope=CollisionScope.NON_VIEW if leadered else CollisionScope.ALL,
    )


def _table_element(adapter: Any, table: Any, name: str) -> LayoutElement | None:
    """Box a TABLE (``ITableAnnotation``) from its anchor plus column/row spans.

    The project's hole tables are inserted top-left-anchored
    (``swBOMConfigurationAnchor_TopLeft``), so the anchor position (read off the
    table's underlying ``IAnnotation``) is the top-left corner and the box grows
    right and DOWN from it.  A horizontally split table still reports the
    source table's total ``RowCount``; ``GetSplitInformation`` identifies the
    row range rendered by this piece, which is the only range its box may sum.
    """
    table = _sw_type_info.early_bound_or_flag(
        table, "ITableAnnotation", "GetAnnotation", "GetSplitInformation"
    )
    inner = adapter._attempt(lambda: adapter._get_attr_or_call(table, "GetAnnotation"))
    if inner is None:
        return None
    inner = _sw_type_info.early_bound_or_flag(inner, "IAnnotation", "GetPosition")
    position = adapter._attempt(lambda: adapter._get_attr_or_call(inner, "GetPosition"))
    if not position:
        return None
    rows = int(adapter._get_attr_or_call(table, "RowCount") or 0)
    columns = int(adapter._get_attr_or_call(table, "ColumnCount") or 0)
    row_indices = range(rows)
    split = adapter._attempt(lambda: table.GetSplitInformation(0, 0, 0, 0))
    if split and len(split) >= 5 and int(split[0]) == 1:
        _direction, _index, count, range_start, range_end = (
            int(value) for value in split[:5]
        )
        if count > 1 and 0 <= range_start <= range_end < rows:
            visible = list(range(range_start, range_end + 1))
            if range_start > 0:
                visible.insert(0, 0)  # repeated heading on later pieces
            row_indices = visible
    width = sum(
        float(adapter._attempt(lambda i=i: table.GetColumnWidth(i)) or 0.0)
        for i in range(columns)
    )
    height = sum(
        float(adapter._attempt(lambda i=i: table.GetRowHeight(i)) or 0.0)
        for i in row_indices
    )
    x, y = float(position[0]), float(position[1])
    return LayoutElement(name, "table", x, y - height, x + width, y)


def _iter_view_annotations(adapter: Any, view: Any, *, sheet_notes_only: bool = False):
    """Yield ``(LayoutElement, annotation)`` for each note / GD&T symbol / dimension.

    ``IView.GetAnnotations`` returns dimensions, center marks, cosmetic-thread
    callouts, notes and GD&T symbols; NOTES (swNote), native GD&T symbols (datum
    tag / feature-control frame / surface-finish) and DISPLAY DIMENSIONS / hole
    callouts (swDisplayDimension) become elements. Tables come from
    ``GetTableAnnotations`` instead.

    The live annotation rides along so the caller can pull its leader geometry
    (see :func:`_leader_segments_of`) without a second COM walk. A DISPLAY
    DIMENSION yields ``None`` for its element: it gets no box here (see
    ``_ANNOT_DIM``), only its leaders.

    ``sheet_notes_only`` is the SHEET view's walk: only notes the drawing
    sheet itself owns (``swAnnotationOwner_DrawingSheet``) are boxed. The sheet
    view also returns the template's notes -- the title block and sheet format,
    40 on a B sheet -- and a view's; their type and owner are read first, so
    none of them costs a note box (six COM reads each) only to be dropped.
    """
    annotations = (
        adapter._attempt(lambda: adapter._get_attr_or_call(view, "GetAnnotations"))
        or []
    )
    for annotation in annotations:
        annotation = _sw_type_info.early_bound_or_flag(
            annotation,
            "IAnnotation",
            "GetType",
            "GetName",
            "GetSpecificAnnotation",
            "GetPosition",
            "GetLeaderCount",
        )
        kind = int(adapter._get_attr_or_call(annotation, "GetType") or 0)
        if sheet_notes_only and (
            kind != _ANNOT_NOTE
            or int(
                adapter._attempt(
                    lambda a=annotation: adapter._get_attr_or_call(a, "OwnerType"),
                    default=-1,
                )
                or -1
            )
            != _OWNER_DRAWING_SHEET
        ):
            continue
        name = str(adapter._get_attr_or_call(annotation, "GetName") or "")
        if kind == _ANNOT_NOTE:
            element = _note_element(adapter, annotation, name)
        elif kind in _GDT_TYPES:
            element = _gdt_element(adapter, annotation, name, kind)
        elif kind == _ANNOT_DIM:
            yield None, annotation
            continue
        else:
            continue
        if element is not None:
            yield element, annotation


def _iter_tables(adapter: Any, view: Any):
    """Yield each table ``LayoutElement`` owned by ``view`` (or the sheet view)."""
    tables = (
        adapter._attempt(lambda: adapter._get_attr_or_call(view, "GetTableAnnotations"))
        or []
    )
    for table in tables:
        table = _sw_type_info.early_bound_or_flag(
            table, "ITableAnnotation", "GetAnnotation"
        )
        inner = adapter._attempt(
            lambda: adapter._get_attr_or_call(table, "GetAnnotation")
        )
        if inner is not None:
            inner = _sw_type_info.early_bound_or_flag(inner, "IAnnotation", "GetName")
        name = (
            str(adapter._get_attr_or_call(inner, "GetName") or "")
            if inner is not None
            else "table"
        )
        element = _table_element(adapter, table, name)
        if element is not None:
            yield element


def _closed_rectangle(
    lines: list[tuple[tuple[float, float], tuple[float, float]]], tol: float = 1e-6
) -> set[int]:
    """Indices of the 4 lines forming a closed axis-aligned rectangle, if any.

    A datum tag's geometry is ``[leader..., box(4 lines)]``; this finds the box so
    the caller can treat everything else as leader. Identified STRUCTURALLY (four
    axis-aligned lines meeting at exactly 4 corners, each used twice) rather than
    by position in the list or by its 7 mm size -- both of those are incidental.
    """
    axis = [
        i
        for i, (a, b) in enumerate(lines)
        if abs(a[0] - b[0]) < tol or abs(a[1] - b[1]) < tol
    ]
    for quad in combinations(axis, 4):
        pts = [p for i in quad for p in lines[i]]
        counts = Counter((round(x, 6), round(y, 6)) for x, y in pts)
        if len(counts) != 4 or any(v != 2 for v in counts.values()):
            continue
        if len({p[0] for p in counts}) == 2 and len({p[1] for p in counts}) == 2:
            return set(quad)
    return set()


def _datum_leader_segments(
    adapter: Any, annotation: Any, *, label: str, owner: str
) -> list[LeaderSegment]:
    """A DATUM TAG's leader, which ``_leader_segments_of`` structurally cannot see.

    A leader is only REGISTERED if ``SetLeader3`` created it, and
    ``add_datum_feature`` never calls it -- nor can it: datum FEATURE symbols are
    absent from ``SetLeader3``'s support list (only datum TARGET symbols are). So
    ``GetLeaderCount()`` returns 0 for every ``swDatumTag`` (measured: 3 tags on
    rocker-arm-support report 0, while a ``swGtol`` on the same sheet reports 1).

    But the leader IS DRAWN, and it IS readable -- as the tag's display data
    (``IAnnotation::GetDisplayData`` lines, sheet space). NOT
    ``IDatumTag::GetLineAtIndex``: at 4:1 on MHA-DT-019 those primitives drew the
    box (-9.9, -5.0) mm off its ink and a jog to it the sheet never printed
    (pc-gdt-ink-diag, a89a13a7a), a phantom leader run. Without this, a datum tag routed straight
    across a neighbouring view is invisible to BOTH audits: its box is
    ``CollisionScope.NONE`` so it is never overlap-checked, and it contributes no
    leader segments so it is never crossing-checked (codex #334). That is not
    hypothetical -- the eye pass found exactly this on cone-tip-bushing (datum A's
    leader driven 41.8 mm down through the whole end view) and crank-arm (datum A
    across a 16 mm section), both passing every gate.
    """
    if _datum_is_dimension_attached(adapter, annotation):
        return []

    display, _refused = annotation_display(adapter, annotation)
    lines: list[tuple[tuple[float, float], tuple[float, float]]] = [
        ((segment.x0, segment.y0), (segment.x1, segment.y1))
        for segment in (line_segment(raw) for raw in display.get("lines", ()))
        if segment is not None
    ]
    # Drop the tag's own BOX -- it is not a leader, and a box legitimately abuts
    # its own view. Everything else (the leader run, and the shoulder some tags
    # draw along the attached edge) is a straight run that can cross a view.
    box = _closed_rectangle(lines)
    return [
        LeaderSegment(label, "gdt", a[0], a[1], b[0], b[1], owner)
        for i, (a, b) in enumerate(lines)
        if i not in box
    ]


def _display_dimension_leader_segments(
    adapter: Any, annotation: Any, *, label: str, owner: str
) -> list[LeaderSegment]:
    """A HOLE CALLOUT's ACTUAL leader lines, which ``_leader_segments_of`` cannot see.

    The same blind spot as :func:`_datum_leader_segments`, one annotation type
    over. A native hole callout is an ``IDisplayDimension`` whose leader was NOT
    made by ``SetLeader3``, so ``GetLeaderCount()`` returns 0 (measured: RD3 on
    pen-rod) and ``_leader_segments_of`` yields nothing -- while its box is
    ``CollisionScope.NONE`` and never overlap-checked. So a callout whose offset
    text is routed across a neighbouring view escapes BOTH audits (codex
    #3605215320), and it is not hypothetical: pen-rod's callout text sits at
    sheet (0.104, 0.222), OUTSIDE its owning view (x 0.062..0.078).

    Read the REAL rendered ink, not a reconstruction. SolidWorks may render a
    bent leader as a sloped run from the arrow up to an elbow, then a horizontal
    shoulder to the text. A straight attachment->text chord misses that elbow:
    it can fail a clean print or miss a real crossing when the rendered route
    and the chord fall on opposite sides of a view (codex #3605558274).
    ``IDisplayDimension::GetDisplayData`` hands back the actual per-primitive
    geometry -- the display-dimension analog of ``IDatumTag::GetLineAtIndex`` --
    in SHEET space (probed on RD3: 3 lines, stub (0.069,0.204)->(0.071,0.206),
    slope ->(0.084,0.219), shoulder ->(0.123,0.219); the shoulder runs PAST the
    text at x=0.104, ground the chord never covered). Every line is leader ink
    that can cross a view; a hole callout has no witness/box lines to exclude.
    Only hole callouts get a leader here -- a plain linear/radius dimension keeps
    its text on the dimension line between its witness lines.
    """
    display = adapter._attempt(
        lambda: adapter._get_attr_or_call(annotation, "GetSpecificAnnotation")
    )
    if display is None:
        return []
    display = _sw_type_info.early_bound_or_flag(
        display, "IDisplayDimension", "IsHoleCallout", "GetDisplayData"
    )
    if not adapter._attempt(lambda: display.IsHoleCallout()):
        return []
    data = adapter._attempt(lambda: display.GetDisplayData())
    if data is None:
        return []
    data = _sw_type_info.early_bound_or_flag(
        data, "IDisplayData", "GetLineCount", "GetLineAtIndex2"
    )
    count = int(adapter._attempt(lambda: data.GetLineCount(), default=0) or 0)
    segments: list[LeaderSegment] = []
    for index in range(count):
        raw = adapter._attempt(lambda i=index: data.GetLineAtIndex2(i))
        if not raw or len(raw) < 10:
            continue
        # GetLineAtIndex2 -> [color, lineType, _, _, startPt[3], endPt[3]].
        values = [float(v) for v in raw]
        segments.append(
            LeaderSegment(
                label,
                "dim",
                values[4],
                values[5],
                values[7],
                values[8],
                owner,
            )
        )
    return segments


def _leader_segments_of(
    adapter: Any, annotation: Any, *, label: str, kind: str, owner: str
) -> list[LeaderSegment]:
    """Every straight run of ``annotation``'s leader(s), in sheet meters.

    ``GetLeaderPointsAtIndex`` returns a flat x,y,z triple stream; consecutive
    points are joined, so a bent leader yields its elbow AND its tail. The
    documentation does not state the points' coordinate space -- the sibling
    ``IAnnotation::GetPosition`` is documented as sheet space and the live
    probe agrees, which is why the audit compares them against sheet-space
    ``IView::GetOutline`` boxes.
    """
    count = int(adapter._attempt(lambda: annotation.GetLeaderCount(), default=0) or 0)
    segments: list[LeaderSegment] = []
    for index in range(count):
        raw = adapter._attempt(lambda i=index: annotation.GetLeaderPointsAtIndex(i))
        if not raw:
            continue
        values = [float(v) for v in raw]
        points = [(values[i], values[i + 1]) for i in range(0, len(values) - 2, 3)]
        for start, end in zip(points, points[1:]):
            segments.append(
                LeaderSegment(label, kind, start[0], start[1], end[0], end[1], owner)
            )
    return segments


def collect_layout_elements(
    adapter: Any, *, layout: DrawingLayout
) -> tuple[list[LayoutElement], list[LeaderSegment], DrawableRegion]:
    """Gather every drawing element, its leader geometry, and the drawable region.

    Elements are:

    * every real drawing view (``IView.GetOutline``), pictorial views given
      ``NONE`` collision scope so their empty diagonal box does not drive false
      collisions;
    * each NOTE a real view owns (the general-notes block and schedule cells); a
      SMALL note centered inside its own view is a hole tag / balloon sitting on
      the geometry and is scoped ``NON_VIEW`` (does not collide with its view);
    * every native GD&T symbol (datum tag / feature-control frame /
      surface-finish), boxed and scoped ``NONE`` (they sit on the geometry they
      annotate) -- overflow- and title-block-keep-out-checked only;
    * NO display dimension or hole callout: only their leaders. The shared
      layout audit boxes their text from display data (``_ANNOT_DIM``);
    * every TABLE (hole tables land on the SHEET view, so it is scanned too);
    * two reserved KEEP-OUT boxes -- the checked-in title block and its
      projection symbol -- so no content may land on either.

    Also returned: every annotation's LEADER geometry (for the crossing audit)
    and the sheet's :class:`DrawableRegion`, queried from its zone margins.

    Notes owned by the drawing SHEET are included. Notes owned by the drawing
    TEMPLATE are the sheet-format frame, zone labels, and title block; those are
    excluded while the title block remains covered by its explicit keep-out.
    """
    drawing_model = adapter.currentModel
    ddoc = _early_bound(
        drawing_model, "IDrawingDoc"
    )  # IDrawingDoc view for drawing-only methods (same dispatch)
    sheet = adapter._get_attr_or_call(ddoc, "GetCurrentSheet")
    if sheet is None:
        raise RuntimeError("drawing has no current sheet to audit layout on")
    properties = list(adapter._get_attr_or_call(sheet, "GetProperties") or [])
    if len(properties) < 7:
        raise RuntimeError(f"cannot read sheet size to audit layout: {properties!r}")
    width, height = float(properties[5]), float(properties[6])
    template = DRAWING_TEMPLATES[layout]
    if abs(width - template.width_m) > 1e-6 or abs(height - template.height_m) > 1e-6:
        raise RuntimeError(
            f"drawing layout is {width:g} x {height:g} m, expected "
            f"{template.width_m:g} x {template.height_m:g} m for {layout.value}"
        )

    elements: list[LayoutElement] = []
    leaders: list[LeaderSegment] = []
    # Tables are deduped by name: SolidWorks can surface the same table under both
    # its owning view and the sheet, and a duplicated box would self-collide.
    tables: dict[str, LayoutElement] = {}
    for view in iter_views(adapter):
        name = view_name(adapter, view)
        outline = adapter._attempt(
            lambda v=view: adapter._get_attr_or_call(v, "GetOutline")
        )
        view_box: tuple[float, float, float, float] | None = None
        if outline:
            view_box = tuple(float(v) for v in outline)  # xmin,ymin,xmax,ymax
            elements.append(
                LayoutElement(
                    name,
                    "view",
                    *view_box,
                    scope=_view_scope(adapter, view),
                )
            )
        for element, annotation in _iter_view_annotations(adapter, view):
            if element is None:
                # A display dimension: no box, but its leaders still cross-check.
                label = str(adapter._get_attr_or_call(annotation, "GetName") or "")
                leaders.extend(
                    _leader_segments_of(
                        adapter, annotation, label=label, kind="dim", owner=name
                    )
                )
                # A native hole callout is an IDisplayDimension whose leader is
                # NOT a SetLeader3 leader, so GetLeaderCount()==0 and the call
                # above returns nothing -- yet its offset text can drive a leader
                # across a neighbouring view. Read it from the display data
                # (codex #3605215320); a no-op for non-callout dimensions.
                leaders.extend(
                    _display_dimension_leader_segments(
                        adapter, annotation, label=label, owner=name
                    )
                )
                continue
            # Record the owning view: a NON_VIEW annotation is exempt from
            # colliding with THIS view only, not other drawing views (Codex #269
            # thread 3).
            element = replace(element, owner=name)
            leaders.extend(
                _leader_segments_of(
                    adapter,
                    annotation,
                    label=element.label,
                    kind=element.kind,
                    owner=name,
                )
            )
            # A datum tag registers NO IAnnotation leader (SetLeader3 never made
            # one, and cannot for a datum FEATURE symbol), so the call above
            # returns nothing for it however well it is routed. Its leader is
            # real, drawn, and readable only as IDatumTag geometry -- collect it
            # separately or a datum leader driven through a neighbouring view is
            # invisible to every gate (codex #334).
            if (
                int(
                    adapter._attempt(
                        lambda a=annotation: adapter._get_attr_or_call(a, "GetType")
                    )
                    or 0
                )
                == _ANNOT_DATUM
            ):
                leaders.extend(
                    _datum_leader_segments(
                        adapter, annotation, label=element.label, owner=name
                    )
                )
            # A SMALL note centered inside its owning view is a hole tag / balloon
            # sitting on the geometry -- give it NON_VIEW scope so it does not
            # collide with the view it sits on (but still collides with a free
            # note / table, a DIFFERENT view, and is checked for OVERFLOW). A LARGE
            # note centered in its view is a general-notes block accidentally
            # dropped on the view, so it stays ALL-scope and the audit reports the
            # collision (Codex #269).
            if (
                element.kind == "note"
                and view_box is not None
                and _center_inside(element, view_box)
                and _is_small_tag(element)
            ):
                element = replace(element, scope=CollisionScope.NON_VIEW)
            elements.append(element)
        for table in _iter_tables(adapter, view):
            tables[table.label] = table

    # Hole tables and free drawing notes anchor to the SHEET view, not a drawing
    # view. Template-owned notes are the sheet-format frame + title block and
    # must remain excluded; IAnnotation.OwnerType distinguishes the two without
    # relying on generated annotation names or positions.
    sheet_view = adapter._attempt(lambda: ddoc.GetFirstView())
    if sheet_view is not None:
        for table in _iter_tables(adapter, sheet_view):
            tables[table.label] = table
        for element, annotation in _iter_view_annotations(
            adapter, sheet_view, sheet_notes_only=True
        ):
            element = replace(element, owner="sheet")
            elements.append(element)
            leaders.extend(
                _leader_segments_of(
                    adapter,
                    annotation,
                    label=element.label,
                    kind=element.kind,
                    owner="sheet",
                )
            )

    elements.extend(tables.values())
    # Reserve the checked-in title block as a keep-out: any element overlapping
    # it is flagged (the projection symbol sits INSIDE the block in the manual
    # template, so it needs no box of its own).
    elements.append(
        LayoutElement(
            "title-block",
            "titleblock",
            template.title_block_left_m,
            0.0,
            width,
            template.title_block_top_m,
        )
    )
    region = sheet_drawable_region(adapter, sheet, width=width, height=height)
    return elements, leaders, region


def check_drawing_layout(
    adapter: Any, *, layout: DrawingLayout, stem: str = ""
) -> None:
    """Diagnose a colliding, border-crossing, or leader-crossed layout.

    This is an explicit diagnostic, not part of the drawing build hot path.

    ``stem`` names the sheet in failures. Every sheet is held to ZERO on every
    defect class -- there is no grandfathered case. There WAS one: pen-assembly
    carried 2 leader crossings behind a `_KNOWN_LEADER_CROSSINGS` ratchet, on the
    reasoning that fixing them needed a design decision. It did not -- it needed
    the balloon's rendered radius (see :func:`_spread_balloons`). The ratchet was
    deleted with the defect.
    """
    with _telemetry.span("drawing.layout_audit"):
        elements, leaders, region = collect_layout_elements(adapter, layout=layout)
        overlaps, overflows, crossings = audit_layout(elements, region, leaders=leaders)
        if not overlaps and not overflows and not crossings:
            _telemetry.success(
                f"drawing layout clean: {len(elements)} elements, "
                f"{len(leaders)} leader segment(s); no overlaps, border "
                "crossings or leader crossings"
            )
            return
        raise RuntimeError(
            "drawing layout audit failed "
            f"({len(overlaps)} overlap(s), {len(overflows)} border "
            f"crossing(s), {len(crossings)} leader crossing(s)):\n"
            + format_findings(overlaps, overflows, crossings)
        )
