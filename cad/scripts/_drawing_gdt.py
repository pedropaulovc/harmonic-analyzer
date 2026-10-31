"""Drawing datums, feature-control frames and model-owned PMI projection.

Datum and feature-control-frame drawings share GD&T authoring and model PMI
projection here without re-keying unconstrained sheets.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Sequence

from solidworks_mcp.adapters import sw_type_info as _sw_type_info
from solidworks_mcp.adapters.com_variant import dispatch_array
from solidworks_mcp.adapters.solidworks.drawing import view_name

from _com import _early_bound
from _drawing_attachment import (
    _ATTACHMENT_SELECT_TYPES,
    _LEADER_BENT,
    _LEADER_SIDE_SMART,
    _assert_attached_to,
    _assert_leader_lands,
    _expected_pick,
)
from _drawing_common import rebuild_drawing
from _drawing_selection import _select_annotation_entity
from _gtol_frame import (
    gtol_frame_signature as _gtol_frame_signature,
    gtol_frame_xml as _gtol_frame_xml,
    translation_print_problem as _translation_print_problem,
)
from _gtol_symbols import GTOL_SYMBOLS as _GTOL_SYMBOLS
from _native_projected_zone import capture_projected_gtol
import _telemetry


@dataclass(frozen=True)
class PmiDrawingPlacement:
    """Drawing-view routing and layout contract for one model-owned PMI item."""

    view: Any
    position: tuple[float, float]
    attachment_xy: tuple[float, float] | None = None
    edge_entity: Any | None = None
    entity: Any | None = None
    attachment_type: str = "EDGE"
    position_tolerance_m: float = 1.5e-5
    leader_attachment_xy: tuple[float, float] | None = None

    def __post_init__(self) -> None:
        supplied = sum(
            value is not None
            for value in (self.attachment_xy, self.edge_entity, self.entity)
        )
        if supplied != 1:
            raise ValueError(
                "projected PMI placement needs exactly one attachment coordinate/entity"
            )
        if self.position_tolerance_m <= 0.0:
            raise ValueError("projected PMI position tolerance must be positive")


def _gtol_frame_persisted(
    applied: str, authored: str, *, shared_symbol: str | None = None
) -> bool:
    """Whether a frame's read-back XML states every semantic ``authored`` does.

    The parsed signature, not substrings: a dropped datum or a 0.05 inside
    another value passed a substring test (CodeRabbit PRRT_kwDOPHDy386rADCQ).
    The _part_pmi readback precedent; an unparsable readback did not persist.
    ``shared_symbol`` reads a composite lower segment's empty symbol cell
    (``gtol_frame_signature``).
    """
    try:
        return _gtol_frame_signature(
            applied, shared_symbol=shared_symbol
        ) == _gtol_frame_signature(authored)
    except ValueError:
        return False


@_telemetry.traced("drawing.datum_feature", label_param="label")
def add_datum_feature(
    adapter: Any,
    view: Any,
    *,
    edge_xy: tuple[float, float] | None = None,
    edge_entity: Any | None = None,
    symbol_xy: tuple[float, float],
    datum: str,
    label: str,
    entity_type: str = "EDGE",
    entity: Any | None = None,
    shoulder: bool = False,
    position_tolerance_m: float = 0.02,
    callout_below: str = "",
    expected_entity: Any | None = None,
    leader_attach_xy: tuple[float, float] | None = None,
) -> Any:
    """Attach a native datum-feature symbol to a drawing-view edge.

    ``entity_type`` widens the pick for entities that are not model edges —
    a revolve's flank lines are ``"SILHOUETTE"`` edges.

    The tag is proved, after the rebuild, to sit on ONE entity that IS the
    feature the recipe named (``_assert_attached_to``, ``IsSame``). A recipe
    names it by ``edge_entity``/``entity`` (selected directly), or by
    ``expected_entity`` with an ``edge_xy`` hit-test -- the pick keeps its
    landing point and must resolve to that entity, else the sheet fails
    before insertion. With ``edge_xy`` alone the proof is only that the tag
    sits on what the hit-test returned: a neighbouring line within the pick
    radius passes, so that form is for datums whose feature has no
    neighbour there (the recipe says so where it picks).

    ``position_tolerance_m`` bounds how far ``IAnnotation::GetPosition`` may
    read from ``symbol_xy`` after the move. That readback is the point where
    the leader meets the symbol, not the symbol centre, and an edge attachment
    re-solves along its edge once the tag moves, so a correctly placed tag
    reads up to its half-extent plus that re-solve away from the request:
    measured 4.8 mm on ``drawing:dt_pinion_cam`` datum D and 17.3 mm on its
    OD-attached datum C (2026-09-16, identical on two seats; both print at the
    request). An ignored ``SetPosition2`` leaves the tag at its default drop,
    12-20 mm off the attachment and 40 mm+ from any request it was aimed at,
    which the 20 mm default rejects. The readback is not a ray from the picked
    point (datum C's bearing swung 4.7 deg), so decomposing it about that ray
    rejects good placements; and in the authoring session
    ``IDatumTag::GetLineAtIndex`` stays frozen at the insertion geometry through
    a rebuild, so it cannot serve as a readback here.

    ``leader_attach_xy`` sets the selected entity's insertion point, never a
    coordinate hit-test or a post-insertion attachment setter. Its rendered
    landing is read back through ``IAnnotation::GetDisplayData`` after rebuild:
    datum-feature triangles are not registered leaders (GetLeaderCount is 0).
    """
    draw = adapter.currentModel
    selected = _select_annotation_entity(
        adapter,
        view,
        edge_xy=edge_xy,
        edge_entity=edge_entity,
        entity=entity,
        entity_type=entity_type,
        label=label,
    )
    expected = _expected_pick(
        adapter,
        selected,
        expected_entity if expected_entity is not None else edge_entity or entity,
        entity_type=entity_type,
        what=f"datum {datum}",
        label=label,
    )
    if leader_attach_xy is not None:
        manager = _early_bound(draw.SelectionManager, "ISelectionMgr")
        if manager.SetSelectionPoint2(
            1, -1, leader_attach_xy[0], leader_attach_xy[1], 0.0
        ) is not True:
            raise RuntimeError(f"failed to set datum {datum} landing ({label})")
    tag = draw.InsertDatumTag2()
    if tag is None:
        raise RuntimeError(f"failed to insert datum {datum} ({label})")
    tag = _sw_type_info.early_bound_or_flag(
        tag,
        "IDatumTag",
        "SetLabel",
        "GetAnnotation",
        "GetLabel",
        "SetText",
        "Shoulder",
        "ForcedShoulder",
    )
    if not tag.SetLabel(datum):
        raise RuntimeError(f"failed to label datum feature {datum} ({label})")
    if shoulder:
        tag.Shoulder = True
    tag_annotation = _sw_type_info.early_bound_or_flag(
        tag.GetAnnotation(),
        "IAnnotation",
        "GetPosition",
        "SetPosition2",
        "GetAttachedEntities3",
        "GetAttachedEntityCount3",
        "GetAttachedEntityTypes",
        "GetLeaderCount",
        "IsDangling",
    )
    forced_shoulder = bool(tag.ForcedShoulder)
    if not tag_annotation.SetPosition2(symbol_xy[0], symbol_xy[1], 0.0):
        raise RuntimeError(f"failed to position datum {datum} ({label})")
    if forced_shoulder and not tag.ForcedShoulder:
        # Moving an angular edge attachment onto a horizontal/vertical ray
        # removes its forced shoulder (IDatumTag::ForcedShoulder). SolidWorks
        # first solves that leader transition using the old shoulder geometry;
        # finish placement in the new mode before checking the same XY contract.
        # No rebuild is needed, and a still-constrained/failed move must reject.
        if not tag_annotation.SetPosition2(symbol_xy[0], symbol_xy[1], 0.0):
            raise RuntimeError(f"failed to position datum {datum} ({label})")
    actual_position = tag_annotation.GetPosition()
    if not actual_position:
        raise RuntimeError(f"datum {datum} reports no position ({label})")
    actual_xy = (float(actual_position[0]), float(actual_position[1]))
    offset = math.hypot(actual_xy[0] - symbol_xy[0], actual_xy[1] - symbol_xy[1])
    _telemetry.event(
        "datum.placement",
        datum=datum,
        requested_x=symbol_xy[0],
        requested_y=symbol_xy[1],
        reported_x=actual_xy[0],
        reported_y=actual_xy[1],
        offset_m=offset,
    )
    if offset > position_tolerance_m:
        raise RuntimeError(
            f"datum {datum} position did not persist ({label}): {actual_xy}; "
            f"requested={symbol_xy}, offset={offset:.6g} m, "
            f"limit={position_tolerance_m:.6g} m"
        )
    if str(tag.GetLabel()) != datum:
        raise RuntimeError(f"datum feature label did not persist ({label})")
    if callout_below and not tag.SetText(4, callout_below):
        raise RuntimeError(f"failed to set datum callout text ({label})")
    draw.ClearSelection2(True)
    rebuild_drawing(adapter, label="add_datum_feature")
    # The tag proves it sits on the feature the recipe NAMED, not merely on
    # whatever the pick returned: a coordinate hit-test resolves whichever
    # line is nearest, and insertion and readback then agree on the neighbour
    # (summing-lever datum B on the rib flange instead of the plate end,
    # #1105). A re-solved attachment fails here rather than printing. No
    # leader count: the triangle is not a ``SetLeader3`` leader
    # (``_datum_leader_segments``).
    _assert_attached_to(
        adapter,
        tag_annotation,
        expected,
        entity_type=entity_type,
        what="datum feature",
        label=label,
        expected_leaders=0,
    )
    if leader_attach_xy is not None:
        assert_datum_landing(
            adapter, tag, expected_xy=leader_attach_xy, label=label
        )
    return tag


def assert_datum_landing(
    adapter: Any,
    tag: Any,
    *,
    expected_xy: tuple[float, float],
    label: str,
    tolerance_m: float = 0.00005,
) -> tuple[float, float]:
    """Prove a datum triangle's explicit sheet-space landing from rendered ink.

    Reuse the layout audit's documented GetDisplayData decoder, not the frozen
    IDatumTag primitives or GetLeaderPointsAtIndex (datum tags have no registered
    leaders). SOLIDWORKS exposes the triangle as an arrowhead, triangle, or line
    vertices; each representation includes the actual feature-side tip.
    """
    from _drawing_layout_audit import annotation_display

    annotation = _early_bound(tag.GetAnnotation(), "IAnnotation")
    if annotation is None:
        raise RuntimeError(f"datum landing has no annotation ({label})")
    if annotation.IsDangling():
        raise RuntimeError(f"datum landing is dangling ({label})")
    display, refused = annotation_display(adapter, annotation)
    if refused or not display:
        raise RuntimeError(f"datum landing has no readable display data ({label}): {refused}")
    points = []
    for raw in display.get("arrows", ()):
        if len(raw) >= 3:
            points.append((float(raw[0]), float(raw[1])))
    for raw in display.get("triangles", ()):
        if len(raw) >= 9:
            points.extend((float(raw[i]), float(raw[i + 1])) for i in (0, 3, 6))
    # Datum tags can draw their open triangle as line primitives instead.
    for raw in display.get("lines", ()):
        if len(raw) >= 8:
            points.extend(
                ((float(raw[-6]), float(raw[-5])), (float(raw[-3]), float(raw[-2])))
            )
    if not points or not all(math.isfinite(v) for point in points for v in point):
        raise RuntimeError(f"datum landing has no finite rendered tip ({label})")
    actual = min(points, key=lambda point: math.dist(point, expected_xy))
    error = math.dist(actual, expected_xy)
    if not math.isfinite(error) or error > tolerance_m:
        raise RuntimeError(
            f"datum landing moved ({label}): actual={actual}, requested={expected_xy}, "
            f"error={error:g} m, limit={tolerance_m:g} m"
        )
    return actual


@_telemetry.traced("drawing.feature_control_frame", label_param="label")
def add_feature_control_frame(
    adapter: Any,
    view: Any,
    *,
    edge_xy: tuple[float, float] | None = None,
    edge_entity: Any | None = None,
    frame_xy: tuple[float, float],
    characteristic: str,
    tolerance: str,
    datums: Sequence[str] = (),
    diameter: bool = False,
    projected_zone_height_mm: float | None = None,
    projection_unit: str = "mm",
    quantity: str = "",
    all_around: bool = False,
    label: str,
    entity_type: str = "EDGE",
    entity: Any | None = None,
    leader_attach_xy: tuple[float, float] | None = None,
    translated: Sequence[str] = (),
    outside_disposition: str | None = None,
    lower_frame: tuple[str, str, Sequence[str]] | None = None,
    composite: bool = False,
) -> Any:
    """Attach a native feature-control frame to a drawing-view edge.

    ``translated`` names datum references printed with the translation
    modifier (``_gtol_frame.gtol_frame_xml``).  ``lower_frame`` is a second,
    stacked frame ``(characteristic, tolerance, datums)`` on the same leader
    (``IGtol.AddFrame``), printed with its own symbol -- not composite
    (``GetCompositeFrame2(1)`` must read False) -- its XML read back.
    ``composite=True`` joins it to the first instead
    (``IGtol.SetCompositeFrame2(True, 1)``; both frames must share the
    characteristic, which prints once across the two segments):
    ``GetCompositeFrame2(1)`` must read True, and each segment's XML is read
    back, the lower's empty shared symbol cell standing for the upper's.

    ``outside_disposition`` applies the native circled-U profile modifier to
    the upper frame (None: symmetric; "0": wholly inside; total: wholly outside).

    ``entity_type`` widens the pick for entities that are not model edges —
    a revolve's flank lines are ``"SILHOUETTE"`` edges.  Only the kinds
    :func:`_assert_attached_to` can prove (EDGE, FACE, SILHOUETTE) are
    accepted; the former DIMENSION path, which took ``IGtol.IsAttached`` as
    proof, had no caller and is gone.

    ``leader_attach_xy`` is where the leader lands on that entity (sheet
    metres): it becomes the selection point before ``InsertGtol``, the same
    way :func:`add_surface_finish` lands.  It is never applied with
    ``SetLeaderAttachmentPointAtIndex``: on farm run
    20260928T080412049Z-77daa98fe5514439bd4ce684c6e19ec7 that call, re-setting
    six frames' leaders to the tip they already had, dropped every frame's
    attached entity (GetAttachedEntityCount3 1 -> 0, types (EDGE,) -> ())
    while IGtol.IsAttached kept reading True with one non-dangling leader.
    """
    if entity_type.upper() not in _ATTACHMENT_SELECT_TYPES:
        raise ValueError(
            f"feature-control frame cannot attach to a {entity_type} ({label})"
        )
    if composite and (lower_frame is None or lower_frame[0] != characteristic):
        raise ValueError(
            f"a composite frame needs a lower segment of the same characteristic ({label})"
        )
    xml = _gtol_frame_xml(
        characteristic,
        tolerance,
        datums=datums,
        diameter=diameter,
        projected_zone_height_mm=projected_zone_height_mm,
        translated=translated,
        outside_disposition=outside_disposition,
        projection_unit=projection_unit,
    )
    draw = adapter.currentModel
    expected_signature = _gtol_frame_signature(xml)
    edge = _select_annotation_entity(
        adapter,
        view,
        edge_xy=edge_xy,
        edge_entity=edge_entity,
        entity=entity,
        entity_type=entity_type,
        label=label,
    )
    if leader_attach_xy is not None:
        selection_manager = _early_bound(draw.SelectionManager, "ISelectionMgr")
        if (
            selection_manager.SetSelectionPoint2(
                1, -1, leader_attach_xy[0], leader_attach_xy[1], 0.0
            )
            is not True
        ):
            raise RuntimeError(
                f"failed to set the feature-control-frame landing {leader_attach_xy} ({label})"
            )
    gtol = draw.InsertGtol()
    if gtol is None:
        raise RuntimeError(f"failed to insert feature-control frame ({label})")
    gtol = _sw_type_info.early_bound_or_flag(
        gtol,
        "IGtol",
        "GetFrameCount",
        "AddFrame",
        "GetFrame",
        "GetAnnotation",
        "SetLeader",
        "IsAttached",
        "GetLeaderCount",
        "GetCompositeFrame2",
        "SetCompositeFrame2",
    )
    frame_count = int(gtol.GetFrameCount() or 0)
    if frame_count == 0:
        if gtol.AddFrame() is not True:
            raise RuntimeError(f"failed to create feature-control frame ({label})")
        frame_count = int(gtol.GetFrameCount() or 0)
    if frame_count < 1:
        raise RuntimeError(f"feature-control frame has no frame ({label})")
    frame = gtol.GetFrame(1)
    migrated = frame is None
    if migrated:
        # Current SOLIDWORKS can instantiate an old-format empty GTol from the
        # project template. Seed its simple compartments before conversion:
        # SW 2026 drops tolerance display when an empty frame is converted first
        # and populated afterward. The saved annotation is still required to be
        # current-format IGtolFrame/XML below.
        datum_values = [*datums[:3], "", "", ""][:3]
        gtol.SetFrameSymbols2(
            1,
            f"<{_GTOL_SYMBOLS[characteristic]}>",
            diameter,
            "",
            False,
            "",
            "",
            "",
            "",
        )
        if gtol.SetFrameValues2(1, tolerance, "", *datum_values) is not True:
            raise RuntimeError(
                f"failed to seed feature-control frame for migration ({label})"
            )
        if gtol.CanConvertFormat() is not True:
            raise RuntimeError(
                f"feature-control frame cannot migrate to current format ({label})"
            )
        conversion_error = int(gtol.ConvertFormat())
        if conversion_error != 0:
            raise RuntimeError(
                f"feature-control frame migration failed ({label}): "
                f"error {conversion_error}"
            )
        frame = gtol.GetFrame(1)
    if frame is None:
        raise RuntimeError(
            f"current feature-control frame is unavailable after migration ({label})"
        )
    frame = _sw_type_info.early_bound_or_flag(
        frame, "IGtolFrame", "SetSymbolXml", "GetSymbolXml"
    )
    # The legacy seed carries neither translation, projection nor unequal-profile
    # modifiers; requested modifiers must use current-format XML after migration.
    if (not migrated or translated or projected_zone_height_mm is not None
            or outside_disposition is not None):
        if frame.SetSymbolXml(xml) is not True:
            raise RuntimeError(f"SOLIDWORKS rejected feature-control frame XML ({label})")
    applied = frame.GetSymbolXml()
    if type(applied) is not str:
        raise RuntimeError(f"feature-control frame XML readback is not a string ({label})")
    try:
        applied_signature = _gtol_frame_signature(applied)
    except ValueError as exc:
        raise RuntimeError(
            f"feature-control frame did not persist ({label}): invalid XML readback: {exc}"
        ) from exc
    if translated and applied_signature.translated != tuple(translated):
        raise RuntimeError(
            f"feature-control frame lost its translation modifier ({label}): {applied!r}"
        )
    if applied_signature != expected_signature:
        raise RuntimeError(
            f"feature-control frame did not persist ({label}): {applied!r}"
        )
    if int(gtol.GetFormat()) != 2:  # swGtolFormatType_e.GTOL_SW2022 (current)
        raise RuntimeError(f"feature-control frame remained in old format ({label})")
    if lower_frame is not None:
        kind = "composite lower segment" if composite else "stacked lower frame"
        lower_characteristic, lower_tolerance, lower_datums = lower_frame
        if not gtol.AddFrame() or int(gtol.GetFrameCount() or 0) != 2:
            raise RuntimeError(f"failed to add the {kind} ({label})")
        lower = _sw_type_info.early_bound_or_flag(
            gtol.GetFrame(2), "IGtolFrame", "SetSymbolXml", "GetSymbolXml"
        )
        lower_xml = _gtol_frame_xml(
            lower_characteristic,
            lower_tolerance,
            datums=lower_datums,
            diameter=diameter,
        )
        if not lower.SetSymbolXml(lower_xml):
            raise RuntimeError(f"SOLIDWORKS rejected the {kind} XML ({label})")
        if composite:
            gtol.SetCompositeFrame2(True, 1)
            if gtol.GetCompositeFrame2(1) is not True:
                raise RuntimeError(f"feature-control frame is not composite ({label})")
            # Joining the segments rewrites the shared symbol cell: the upper
            # segment must still read back whole.
            upper_applied = str(frame.GetSymbolXml() or "")
            if not _gtol_frame_persisted(upper_applied, xml):
                raise RuntimeError(
                    f"composite upper segment did not persist ({label}): {upper_applied!r}"
                )
        elif gtol.GetCompositeFrame2(1):
            raise RuntimeError(f"stacked frames read back composite ({label})")
        lower_applied = str(lower.GetSymbolXml() or "")
        shared = _GTOL_SYMBOLS[characteristic] if composite else None
        if not _gtol_frame_persisted(lower_applied, lower_xml, shared_symbol=shared):
            raise RuntimeError(f"{kind} did not persist ({label}): {lower_applied!r}")
    if quantity:
        if not gtol.InsertBelowFrameTextAt(1, quantity):
            raise RuntimeError(f"failed to add feature quantity {quantity!r} ({label})")
        if str(gtol.GetBelowFrameTextAt(1) or "") != quantity:
            raise RuntimeError(f"feature quantity did not persist ({label})")

    annotation = _sw_type_info.early_bound_or_flag(
        gtol.GetAnnotation(),
        "IAnnotation",
        "GetAttachedEntityCount3",
        "SetAttachedEntities",
        "SetPosition2",
        "SetLeader3",
        "GetAttachedEntities3",
        "GetAttachedEntityTypes",
        "GetLeaderCount",
        "IsDangling",
        "GetLeaderPointsAtIndex",
        "GetDisplayData",
    )
    attached_count = int(annotation.GetAttachedEntityCount3())
    if attached_count != 1:
        if not annotation.SetAttachedEntities(dispatch_array([edge])):
            pick = edge_xy if edge_xy is not None else leader_attach_xy
            raise RuntimeError(
                f"failed to attach feature-control frame ({label}): InsertGtol "
                f"left {attached_count} attached entities (types "
                f"{tuple(annotation.GetAttachedEntityTypes() or ())}) and "
                f"SetAttachedEntities rejected the {entity_type.upper()} "
                f"selected at {pick}"
            )
    # Bent leaders keep ordinary feature attachments out of neighbouring views.
    leader_status = int(
        annotation.SetLeader3(
            _LEADER_BENT,
            _LEADER_SIDE_SMART,
            True,  # smart arrowhead
            False,  # perpendicular (GTol-only; not wanted here)
            all_around,
            False,  # dashed
        )
    )
    if leader_status != 0:
        raise RuntimeError(
            f"failed to set a bent leader on the feature-control frame ({label}): "
            f"SetLeader3 status {leader_status}"
        )
    if not annotation.SetPosition2(frame_xy[0], frame_xy[1], 0.0):
        raise RuntimeError(f"failed to position feature-control frame ({label})")
    rebuild_drawing(adapter, label="add_feature_control_frame")
    frame = gtol.GetFrame(1)
    if frame is None:
        raise RuntimeError(f"feature-control frame disappeared after rebuild ({label})")
    frame = _sw_type_info.early_bound_or_flag(
        frame, "IGtolFrame", "SetSymbolXml", "GetSymbolXml"
    )
    applied = frame.GetSymbolXml()
    if type(applied) is not str:
        raise RuntimeError(f"feature-control frame XML readback is not a string ({label})")
    try:
        applied_signature = _gtol_frame_signature(applied)
    except ValueError as exc:
        raise RuntimeError(
            f"invalid feature-control frame XML readback after rebuild ({label}): {exc}"
        ) from exc
    if applied_signature != expected_signature:
        raise RuntimeError(
            f"feature-control frame changed semantics after rebuild ({label})"
        )
    # IGtol.IsAttached reads True on a detached frame (run 20260928T080412049Z
    # above), so the attached entity is what proves the attachment.
    _assert_attached_to(
        adapter,
        annotation,
        edge,
        entity_type=entity_type,
        what="feature-control frame",
        label=label,
    )
    if translated:
        # The XML reading back the modifier does not show what prints: the
        # <Translation> flag read back too, and printed a translation vector
        # (farm runs 20261009T174542021Z, 20261009T182549169Z).  The printed
        # text items must show each letter with its glyph and no brackets.
        texts = _annotation_texts(annotation)
        problem = _translation_print_problem(texts, translated)
        _telemetry.event(
            "gtol.translation_print",
            label=label,
            outcome=problem or "prints",
            texts=" | ".join(texts),
            xml=str(frame.GetSymbolXml() or ""),
        )
        if problem:
            raise RuntimeError(
                f"feature-control frame translation modifier misprints ({label}): {problem}"
            )
    if leader_attach_xy is not None:
        _assert_leader_lands(
            annotation, leader_attach_xy, what="feature-control frame", label=label
        )
    if projected_zone_height_mm is not None:
        capture_projected_gtol(
            draw, gtol, expected_xml=xml, key=label,
            phase="drawing_after_rebuild", migrated=migrated,
        )
    draw.ClearSelection2(True)
    return gtol


def _annotation_texts(annotation: Any) -> list[str]:
    """An annotation's printed text items, in display order.

    ``IAnnotation::GetDisplayData`` -> ``IDisplayData`` text items, the ink
    the layout audit reads (diagnostics/drawing_layout_audit.py): a frame
    prints each compartment's letter, modifier glyph and value as one item.
    """
    data = _sw_type_info.early_bound_or_flag(
        annotation.GetDisplayData(), "IDisplayData", "GetTextCount", "GetTextAtIndex"
    )
    if data is None:
        raise RuntimeError("annotation has no display data")
    return [
        str(data.GetTextAtIndex(i) or "") for i in range(int(data.GetTextCount() or 0))
    ]


def _annotation_text_positions(
    annotation: Any,
) -> list[tuple[str, tuple[float, float]]]:
    """An annotation's printed text items with their sheet positions (m).

    ``IDisplayData::GetTextPositionAtIndex``, the anchor the layout audit
    boxes each text item from (diagnostics/drawing_layout_audit.py).
    """
    data = _sw_type_info.early_bound_or_flag(
        annotation.GetDisplayData(),
        "IDisplayData",
        "GetTextCount",
        "GetTextAtIndex",
        "GetTextPositionAtIndex",
    )
    if data is None:
        raise RuntimeError("annotation has no display data")
    items = []
    for i in range(int(data.GetTextCount() or 0)):
        position = tuple(data.GetTextPositionAtIndex(i) or ())
        if len(position) >= 2:
            items.append(
                (
                    str(data.GetTextAtIndex(i) or ""),
                    (float(position[0]), float(position[1])),
                )
            )
    return items


_SEL_GTOL = 13  # swSelectType_e.swSelGTOLS


# A one-row frame's height: DetailItem354 printed y 219.0 -> 212.0 mm from
# its 0.219 position (farm run 20261009T171439353Z).
_GTOL_ROW_HEIGHT = 0.007


_DATUM_LETTER_FROM_SYMBOL = (-0.00173, 0.00072)


_FRAME_DATUM_CORRECTIONS = 2


def _frame_name(gtol: Any) -> str:
    """The sheet-unique annotation name (``DetailItemNNN``) of one frame.

    A selection or attachment readback may hand back the frame as its
    ``IGtol`` or as its ``IAnnotation``; either names it, anything else
    names nothing (and so matches no frame).
    """
    try:
        annotation = _early_bound(gtol, "IGtol").GetAnnotation()
    except Exception:  # noqa: BLE001 - not an IGtol: try it as the annotation
        annotation = gtol
    try:
        annotation = _sw_type_info.early_bound_or_flag(
            annotation, "IAnnotation", "GetName"
        )
        return str(annotation.GetName() or "")
    except Exception:  # noqa: BLE001 - neither names a frame
        return ""


@_telemetry.traced("drawing.frame_datum_feature", label_param="label")
def add_frame_datum_feature(
    adapter: Any,
    view: Any,
    gtol: Any,
    *,
    datum: str,
    symbol_xy: tuple[float, float],
    label: str,
    position_tolerance_m: float = 0.003,
) -> Any:
    """Attach a native datum-feature symbol to a feature-control frame.

    ASME Y14.5-2018 names a pattern of features of size one datum by the
    datum feature symbol on the frame under the pattern's ``nX`` callout.
    ``IGtol.SetDatumIdentifier`` cannot do that: on farm run
    20261009T171439353Z it read "B" back before and after the rebuild and
    printed nothing.  A tag on the dimension attaches to nothing (run
    20261009T155421516Z and the vm2 datum-placement probe).  So the frame is
    selected and the tag is inserted on that selection, the way a tag goes on
    a selected edge.

    The frame is selected with ``IAnnotation.Select2(False, 0)``; the
    selection must be ONE GTOL whose annotation name is the frame's.  On farm
    run 20261009T182549169Z that attached the knife mount's datum B to its
    frame DetailItem354 (one entity, type 13, named DetailItem354), where
    ``IAnnotation.Select3(False, <view ISelectData>)`` had returned False
    (run 20261009T174542021Z).  After the rebuild the tag must be attached to
    exactly that frame, matched by name: an unattached tag would print a
    letter that defines nothing.

    ``symbol_xy`` is the letter box's bottom middle.  A tag on a frame is
    NOT positioned in sheet coordinates.  On runs 20261009T182549169Z and
    20261009T185542819Z ``SetPosition2(0.1613, 0.2)`` read back from
    ``GetPosition`` as (0.0, 0.2), and the letter printed at (0.15997,
    0.41272).  That is the frame's mid-width, 0.2 m above its bottom edge
    (DetailItem354: top 0.219, one 7.0 mm row) plus the letter's own 0.72 mm
    rise: y is an offset from the frame's bottom edge, and x is held to the
    frame.  So the tag is first set at (0, ``symbol_xy`` y - frame bottom).
    Then the printed letter (display-data text position, the ink the layout
    audit reads) is compared with where ``symbol_xy`` puts it, and the
    position is moved, in the space ``GetPosition`` reports, by the miss: up
    to ``_FRAME_DATUM_CORRECTIONS`` times.  On run 20261009T200747541Z the
    first set, below the frame, printed 7.0 mm low (one tag box: a tag hung
    below a frame takes y at its box's top) and one correction printed the
    letter 0.40 mm from its place.  Each step emits
    ``datum.frame_placement``.  The letter must end within
    ``position_tolerance_m`` of its place, or the sheet fails.
    """
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    name = view_name(adapter, view)
    if not ddoc.ActivateView(name):
        raise RuntimeError(f"failed to activate {label} drawing view {name!r}")
    frame_name = _frame_name(gtol)
    frame_annotation = _sw_type_info.early_bound_or_flag(
        _early_bound(gtol, "IGtol").GetAnnotation(),
        "IAnnotation",
        "Select2",
        "GetPosition",
    )
    frame_bottom = float(frame_annotation.GetPosition()[1]) - _GTOL_ROW_HEIGHT
    selection_manager = _early_bound(draw.SelectionManager, "ISelectionMgr")
    draw.ClearSelection2(True)
    if not frame_annotation.Select2(False, 0):
        raise RuntimeError(
            f"failed to select the frame {frame_name} for datum {datum} ({label})"
        )
    count = int(selection_manager.GetSelectedObjectCount2(-1))
    kind = int(selection_manager.GetSelectedObjectType3(count, -1)) if count else 0
    picked = selection_manager.GetSelectedObject6(count, -1) if count else None
    picked_name = (
        _frame_name(picked) if kind == _SEL_GTOL and picked is not None else ""
    )
    if count != 1 or kind != _SEL_GTOL or picked_name != frame_name:
        draw.ClearSelection2(True)
        raise RuntimeError(
            f"selecting the frame for datum {datum} ({label}) selected {count} "
            f"object(s), type {kind}, name {picked_name!r}; expected one GTOL "
            f"{frame_name!r}"
        )
    tag = draw.InsertDatumTag2()
    if tag is None:
        raise RuntimeError(
            f"failed to insert datum {datum} on frame {frame_name} ({label})"
        )
    tag = _sw_type_info.early_bound_or_flag(
        tag, "IDatumTag", "SetLabel", "GetLabel", "GetAnnotation"
    )
    if not tag.SetLabel(datum):
        raise RuntimeError(f"failed to label datum feature {datum} ({label})")
    tag_annotation = _sw_type_info.early_bound_or_flag(
        tag.GetAnnotation(),
        "IAnnotation",
        "GetPosition",
        "SetPosition2",
        "GetAttachedEntities3",
        "GetAttachedEntityCount3",
        "GetAttachedEntityTypes",
        "GetDisplayData",
    )
    position = (0.0, symbol_xy[1] - frame_bottom)
    if not tag_annotation.SetPosition2(position[0], position[1], 0.0):
        raise RuntimeError(f"failed to position datum {datum} ({label})")
    draw.ClearSelection2(True)
    rebuild_drawing(adapter, label="add_frame_datum_feature")
    attached = tuple(tag_annotation.GetAttachedEntities3() or ())
    attached_count = int(tag_annotation.GetAttachedEntityCount3())
    types = tuple(int(t) for t in (tag_annotation.GetAttachedEntityTypes() or ()))
    # The readback type of an annotation-on-annotation attachment is logged;
    # the NAME decides.
    attached_name = (
        _frame_name(attached[0])
        if len(attached) == 1 and attached[0] is not None
        else ""
    )
    _telemetry.event(
        "datum.frame_attachment",
        datum=datum,
        frame=frame_name,
        count=attached_count,
        types=str(types),
        attached=attached_name,
    )
    if attached_count != 1 or attached_name != frame_name:
        raise RuntimeError(
            f"datum {datum} is not attached to its frame {frame_name} ({label}): "
            f"count={attached_count}, types={types}, attached={attached_name!r}"
        )
    # Where the letter's text item prints for a tag whose letter box has its
    # bottom middle at symbol_xy: datum A's free tag at (0.115, 0.18762)
    # printed its "A" at (0.11327, 0.18834) (half a 3.5 mm letter left, 0.72
    # mm up; farm run 20261009T174542021Z).
    wanted = (
        symbol_xy[0] + _DATUM_LETTER_FROM_SYMBOL[0],
        symbol_xy[1] + _DATUM_LETTER_FROM_SYMBOL[1],
    )
    for step in range(_FRAME_DATUM_CORRECTIONS + 1):
        printed = _annotation_text_positions(tag_annotation)
        reported = tuple(float(v) for v in (tag_annotation.GetPosition() or ())[:2])
        letters = [xy for text, xy in printed if text.strip() == datum]
        miss = (
            (wanted[0] - letters[0][0], wanted[1] - letters[0][1])
            if len(letters) == 1
            else (math.inf, math.inf)
        )
        offset = math.hypot(*miss)
        _telemetry.event(
            "datum.frame_placement",
            datum=datum,
            frame=frame_name,
            step=step,
            set=str(position),
            reported=str(reported),
            wanted=str(wanted),
            printed=str(printed),
            offset_m=offset,
        )
        if offset <= position_tolerance_m or not math.isfinite(offset):
            break
        if step == _FRAME_DATUM_CORRECTIONS or len(reported) != 2:
            break
        position = (reported[0] + miss[0], reported[1] + miss[1])
        if not tag_annotation.SetPosition2(position[0], position[1], 0.0):
            raise RuntimeError(f"failed to move datum {datum} by {miss} ({label})")
        rebuild_drawing(adapter, label="add_frame_datum_feature placement")
    if offset > position_tolerance_m:
        raise RuntimeError(
            f"datum {datum} does not print where it was placed ({label}): "
            f"printed {printed}, wanted letter at {wanted} for symbol {symbol_xy}, "
            f"limit={position_tolerance_m:.6g} m"
        )
    if str(tag.GetLabel()) != datum:
        raise RuntimeError(f"datum feature label did not persist ({label})")
    draw.ClearSelection2(True)
    return tag


def assert_frame_datums_defined(views: Sequence[Any], *, label: str) -> None:
    """Fail unless every datum letter a frame in ``views`` references is
    printed by a datum tag in ``views``.

    A frame naming a datum the sheet never identifies is not a requirement a
    machinist can hold; farm run 20261009T171439353Z printed ⌖Ø0.10|A|B and
    ⌖Ø0.20|A|B on the knife mount with no B on the sheet, because the
    identifier its readback proved does not print.
    """
    from _gtol_frame import gtol_frame_datums

    defined: set[str] = set()
    referenced: dict[str, list[str]] = {}
    for view in views:
        native = _early_bound(view, "IView")
        for tag in native.GetDatumTags() or ():
            defined.add(str(_early_bound(tag, "IDatumTag").GetLabel() or ""))
        for gtol in native.GetGTols() or ():
            gtol = _early_bound(gtol, "IGtol")
            name = _frame_name(gtol)
            for index in range(1, int(gtol.GetFrameCount() or 0) + 1):
                frame = _sw_type_info.early_bound_or_flag(
                    gtol.GetFrame(index), "IGtolFrame", "GetSymbolXml"
                )
                for letter in gtol_frame_datums(str(frame.GetSymbolXml() or "")):
                    referenced.setdefault(letter, []).append(name)
    missing = {
        letter: frames for letter, frames in referenced.items() if letter not in defined
    }
    if missing:
        raise RuntimeError(
            f"{label}: frames reference datum(s) no tag prints: "
            + ", ".join(
                f"{letter} by {sorted(set(frames))}"
                for letter, frames in sorted(missing.items())
            )
            + f"; tags print {sorted(defined)}"
        )


@_telemetry.traced("drawing.project_part_pmi", label_param="label")
def project_part_pmi(
    adapter: Any,
    *,
    placements: dict[str, PmiDrawingPlacement],
    datums: Sequence[Any],
    controls: Sequence[Any],
    label: str,
) -> dict[str, Any]:
    """Project the part's typed PMI spec onto deterministic drawing entities.

    ``author_part_pmi`` authors and verifies the same rows on the ``.SLDPRT``.
    The drawing display is generated from those rows rather than retyping any
    datum or tolerance.  Native drawing annotations are intentional: live SW
    2026 constrains imported datum positions and interprets imported FCF leader
    endpoints in model space, yielding off-sheet leaders even when setter
    readback reports the requested coordinates (reproduced 2026-07-29).
    """
    from _gtol_controls import validate_part_pmi
    from _gtol_frame import gtol_frame_signature

    validate_part_pmi(datums, controls)
    expected_keys = {datum.key for datum in datums} | {
        control.key for control in controls
    }
    if set(placements) != expected_keys:
        raise RuntimeError(
            f"{label}: placement keys {sorted(placements)} != "
            f"spec annotations {sorted(expected_keys)}"
        )

    projected: dict[str, Any] = {}

    def _name(annotation: Any, expected: str, key: str) -> Any:
        annotation = _early_bound(annotation, "IAnnotation")
        if not annotation.SetName(expected):
            raise RuntimeError(f"{label}: failed to name projected PMI {key}")
        if str(annotation.GetName() or "") != expected:
            raise RuntimeError(f"{label}: projected PMI {key} name did not persist")
        return annotation

    for datum in datums:
        placement = placements[datum.key]
        # No position_tolerance_m here: that field bounds an FCF's frame-corner
        # drift; a datum tag's readback is its leader junction (see
        # add_datum_feature) and keeps the helper's measured default.
        tag = add_datum_feature(
            adapter,
            placement.view,
            edge_xy=placement.attachment_xy,
            edge_entity=placement.edge_entity,
            symbol_xy=placement.position,
            datum=datum.letter,
            label=f"{label} {datum.key}",
            entity_type=placement.attachment_type,
            entity=placement.entity,
        )
        projected[datum.key] = _name(
            tag.GetAnnotation(), datum.annotation_name, datum.key
        )

    for control in controls:
        placement = placements[control.key]
        gtol = add_feature_control_frame(
            adapter,
            placement.view,
            edge_xy=placement.attachment_xy,
            edge_entity=placement.edge_entity,
            frame_xy=placement.position,
            characteristic=control.characteristic,
            tolerance=control.tolerance,
            datums=control.datums,
            diameter=control.tolerance_zone == "diametral",
            projected_zone_height_mm=control.projected_zone_height_mm,
            projection_unit=control.projection_unit,
            label=f"{label} {control.key}",
            entity_type=placement.attachment_type,
            entity=placement.entity,
            leader_attach_xy=placement.leader_attachment_xy,
        )
        frame = _early_bound(gtol.GetFrame(1), "IGtolFrame")
        applied = frame.GetSymbolXml()
        if type(applied) is not str:
            raise RuntimeError(f"{label}: projected gtol {control.key} XML is not a string")
        try:
            applied_signature = gtol_frame_signature(applied)
        except ValueError as exc:
            raise RuntimeError(
                f"{label}: projected gtol {control.key} invalid frame XML readback: {exc}"
            ) from exc
        if applied_signature != (
            gtol_frame_signature(control.frame_xml)
        ):
            raise RuntimeError(
                f"{label}: projected gtol {control.key} changed semantics"
            )
        annotation = _name(gtol.GetAnnotation(), control.annotation_name, control.key)
        after = tuple(annotation.GetPosition() or ())
        drift = (
            math.inf
            if len(after) < 2
            else math.hypot(
                float(after[0]) - placement.position[0],
                float(after[1]) - placement.position[1],
            )
        )
        if drift > placement.position_tolerance_m:
            raise RuntimeError(
                f"{label}: {control.key} position drift {drift * 1000:.2f} mm "
                f"exceeds {placement.position_tolerance_m * 1000:.2f} mm"
            )
        owner = _early_bound(annotation.Owner, "IView")
        expected_view = _early_bound(placement.view, "IView")
        if str(owner.GetName2()) != str(expected_view.GetName2()):
            raise RuntimeError(
                f"{label}: {control.key} owner view {owner.GetName2()!r} != "
                f"{expected_view.GetName2()!r}"
            )
        projected[control.key] = annotation

    _telemetry.event("drawing.pmi_projected", count=len(projected))
    return projected
