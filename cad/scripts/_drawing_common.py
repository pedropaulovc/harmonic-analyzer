"""Project drawing framework shared by every manufacturing print.

Raw project-agnostic COM calls remain in ``solidworks_mcp``.  This layer owns
the harmonic-analyzer book policy: ASME B landscape, the checked-in template,
exact PDF/PNG output, and fail-loud multi-leader callouts.
Part-specific views, dimensions, and notes belong in ``draw_<part>.py``.
"""

from __future__ import annotations

import math
import os
import sys
from collections import Counter
from dataclasses import dataclass, replace
from itertools import combinations
from pathlib import Path
from typing import Any, Iterable, Literal, Sequence


import _config
import _telemetry
from _common import _early_bound
from _gtol_spec import GTOL_SYMBOLS as _GTOL_SYMBOLS
from _gtol_spec import gtol_frame_xml as _gtol_frame_xml
from _surface_finish import SurfaceFinishControl
from _drawing_layout_check import (
    CollisionScope,
    DrawableRegion,
    LayoutElement,
    LeaderSegment,
    audit_layout,
    format_findings,
)
from _drawing_registry import PROJECT_DRWDOT
from solidworks_mcp.adapters import sw_type_info as _sw_type_info
from solidworks_mcp.adapters.com_variant import (
    bool_array,
    bstr_array,
    dispatch_array,
    double_array,
)
from solidworks_mcp.adapters.pywin32_adapter import null_callout
from solidworks_mcp.adapters.solidworks.drawing import (
    TOL_BASIC,
    add_note,
    curate_dimensions,
    dimension_name,
    iter_views,
    new_drawing,
    remove_notes_matching as remove_notes_matching,
    save_drawing,
    set_units_mm,
    view_name,
)


# swAnnotationType_e.swNote -- the view-owned annotation TYPE that becomes a
# free-standing layout element (the general-notes block, schedule cells). Tables
# are enumerated separately via IView.GetTableAnnotations.
_ANNOT_NOTE = 6
_DIMENSION_TEXT_CALLOUT_BELOW = 4  # swDimensionTextCalloutBelow
# swInsertAnnotation_e flags used by the curated model-item import. Hole Wizard
# placement dimensions live on an absorbed sketch and require their dedicated
# flag; MarkedForDrawing alone does not make them importable.
_INSERT_DIMS_MARKED = 0x8000
_INSERT_HOLE_WIZARD_LOCATION_DIMS = 0x20000

# swAnnotationType_e for the native GD&T symbols the recipes place at explicit
# sheet coordinates (datum tags, feature-control frames, surface-finish symbols).
# None of these interfaces expose a real bounding box (IDisplayData returns only
# leader-polluted primitives in a non-sheet coordinate space), so each is boxed
# as a nominal square around its GetPosition anchor. That nominal box is reliable
# enough to catch a symbol placed clear OFF the sheet (overflow) but too coarse
# to assert an OVERLAP without false positives -- a datum tag placed beside its
# own feature-control frame, standard GD&T practice, would self-collide -- so the
# symbols get ``NONE`` collision scope (overflow-checked, overlap-exempt).
# (Codex #269 thread 5 overflow; overlap declined with this rationale.)
_ANNOT_DATUM = 2
_ANNOT_GTOL = 5
_ANNOT_SFSYM = 7
_SEL_DIMENSION = 14  # swSelectType_e.swSelDIMENSIONS
_GDT_TYPES = frozenset({_ANNOT_DATUM, _ANNOT_GTOL, _ANNOT_SFSYM})
# The interface each GD&T kind's geometry actually lives on -- reached via
# IAnnotation::GetSpecificAnnotation, never off IAnnotation itself.
_GDT_IFACE = {
    _ANNOT_DATUM: "IDatumTag",
    _ANNOT_GTOL: "IGtol",
    _ANNOT_SFSYM: "ISFSymbol",
}
# Fallback only, for an annotation whose geometry cannot be read. Every GD&T
# symbol that CAN be measured is (see _measured_gdt_box) -- a fixed square is
# wrong for an FCF by construction, since its width tracks its compartments.
_NOMINAL_GDT_HALF_M = 0.008

# A SURFACE-FINISH symbol is NOT centred on its anchor, so the symmetric box
# above is the wrong shape for it and silently under-reports.
# ``GetPosition`` returns the LEADER'S ATTACHMENT POINT -- the bottom vertex of
# the check-mark triangle -- and the whole body draws UP and to the RIGHT of it:
# triangle x [ax-0.006, ax+0.006] y [ay, ay+0.011]; the "Ra 1.6" text
# x [ax+0.013, ax+0.039] y [ay+0.010, ay+0.017]; the arm at y ~= ay+0.018.
# Boxed +/-8 mm about a point that is the symbol's own BOTTOM EDGE, the gate
# missed ~10 mm of body above and ~31 mm of text to the right: wheel_axle's Ra
# printed over the zone label while the audit stayed silent (its real top is
# ay+0.018 = 0.273, 5.6 mm past the rule, but the box topped out at 0.263).
# Measured independently on 3+ sheets by three agents; every sample draws
# up-right regardless of which side the target sits on (a leader running
# up-LEFT out of the vertex does not mirror the body), so the offsets are
# orientation-stable for ``add_surface_finish``'s SetLeader3(BENT, SMART) call.
# LEFT keeps the old 8 mm rather than the measured 7: strictly no less
# conservative than what it replaces, on every side.
_SF_BOX_LEFT_M = 0.008
_SF_BOX_RIGHT_M = 0.039
_SF_BOX_UP_M = 0.018
_SF_BOX_DOWN_M = 0.0

# swAnnotationType_e.swDisplayDimension -- every linear/diameter dimension AND
# the native hole callouts (a diameter dim carrying "/ THRU" text). Like GD&T
# they expose only a text-anchor GetPosition (no clean box) and by design sit
# ON/ACROSS the view geometry they measure, so they get a small nominal box and
# ``NONE`` scope: overflow-checked + title-block keep-out (a callout dragged off
# the sheet or over the title block is caught) but NOT overlap-checked against
# views. Half-span is smaller than GD&T's -- dimension text is compact, and a
# tight box keeps the zero-slack overflow check false-positive-free on interior
# dims (Codex #269 thread 1).
_ANNOT_DIM = 4
_NOMINAL_DIM_HALF_M = 0.004

_OLD_EDGE_BREAK_NOTE = "REMOVE BURRS AND BREAK SHARP EDGES R.01 OR CHAMFER .01 MAX"
_METRIC_EDGE_BREAK_NOTE = "REMOVE BURRS AND BREAK SHARP EDGES R0.25 OR CHAMFER 0.25 MAX"

# swLeaderStyle_e.swBENT / swLeaderSide_e.swLS_SMART. Every leadered annotation
# is bent: a straight leader runs at whatever angle its anchor-to-text vector
# happens to take, which is what drove the old Ra symbol's leader diagonally
# across two views. A bent leader lands its elbow horizontally at the text.
_LEADER_BENT = 2
_LEADER_SIDE_SMART = 0

# These ints are READ OFF the installed swconst.tlb, not the published docs: the
# API reference prints "See System Options and Document Properties" instead of a
# value for every swUserPreferenceIntegerValue_e / swUserPreferenceOption_e
# member, and that page documents none of them. Re-read them from the type
# library (swconst.tlb, SOLIDWORKS Constant type library) rather than guessing
# if they ever need revisiting.
_PREF_DIM_TEXT_AND_LEADER_STYLE = 372
_BROKEN_LEADER_HORIZONTAL_TEXT = 2

# swUserPreferenceOption_e's dimension scopes. Two live-probed facts pin this
# list, neither of them documented:
#
#  * the style REQUIRES a dimension scope -- writing it under
#    swDetailingNoOptionSpecified(0) returns False and leaves the document on
#    swSolidLeaderAlignedText(1), the aligned-text default this fix exists to
#    replace; and
#  * the umbrella swDetailingDimension(200) does NOT propagate -- after setting
#    it, every per-type scope still read 1, so a drawing whose dimensions are
#    linear/radius/diameter would have kept rotated text.
#
# So every scope is set explicitly and read back. Values are from swconst.tlb
# (the docs print no integer for any swUserPreferenceOption_e member).
_DIM_DETAILING_SCOPES = {
    "swDetailingDimension": 200,
    "swDetailingAngleDimension": 201,
    "swDetailingArcLengthDimension": 202,
    "swDetailingChamferDimension": 203,
    "swDetailingDiameterDimension": 204,
    "swDetailingHoleDimension": 205,
    "swDetailingLinearDimension": 206,
    "swDetailingOrdinateDimension": 207,
    "swDetailingRadiusDimension": 208,
    "swDetailingAngularRunningDimension": 209,
}

# A circular 2-character BOM balloon renders ~10-12 mm across at the template
# font; its GetExtent is leader-polluted (see _note_element), so it gets this
# nominal half-span box around its IAnnotation.GetPosition anchor instead.
_NOMINAL_BALLOON_HALF_M = 0.006
# Ink gap left between two balloon circles pushed apart on the ring. Their radius
# is MEASURED per sheet (INote::GetBalloonInfo -- 4.72 mm on pen-assembly), so
# this is only the clearance between them, not a stand-in for the circle itself.
_BALLOON_CLEARANCE_M = 0.0015

# The hand-made harmonic-analyzer.DRWDOT bakes its title block in as sheet-
# format lines + notes rather than a queryable ITitleBlock (sheet.TitleBlock is
# None), so its occupied region is reserved here as a fixed keep-out box. Any
# element overlapping it fails the audit, so content can never land on the title
# block (Codex #269 threads 4). These MUST track the manual template -- if the
# title block moves, re-measure with the sheet-view annotation dump (probe via
# _iter_view_annotations on a fresh drawing; last measured 2026-07-13: notes
# span x 0.2672..0.4229, y <= 0.0611, borders a couple of mm outside).
#
# The block runs from its left rule up to its top rule, extending to the
# sheet's right and bottom edges. The third-angle projection symbol lives
# INSIDE the block (bottom-center cell), so it needs no separate keep-out.
_TITLE_BLOCK_LEFT_M = 0.264
_TITLE_BLOCK_TOP_M = 0.064


ASME_B_WIDTH_M = 0.4318
ASME_B_HEIGHT_M = 0.2794
ASME_B_PNG_SIZE = (5100, 3300)
ASME_B_DPI = 300


@dataclass(frozen=True)
class DrawingOutputs:
    slddrw: Path
    pdf: Path
    png: Path


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


def property_link(property_name: str) -> str:
    """Return a source-model property link suitable for a drawing note."""
    if not property_name or '"' in property_name:
        raise ValueError(f"invalid drawing property name: {property_name!r}")
    return f'$PRPSHEET:"{property_name}"'


def _select_view_entity(
    adapter: Any,
    view: Any,
    entity_type: str,
    xy: tuple[float, float] | None,
    *,
    label: str,
    entity: Any | None = None,
) -> Any:
    draw = adapter.currentModel
    ddoc = _early_bound(
        draw, "IDrawingDoc"
    )  # IDrawingDoc view for drawing-only methods (same dispatch)
    name = view_name(adapter, view)
    if not ddoc.ActivateView(name):
        raise RuntimeError(f"failed to activate {label} drawing view {name!r}")
    draw.ClearSelection2(True)
    selected = False
    if entity is not None:
        if entity_type == "SILHOUETTE":
            selection_manager = _early_bound(draw.SelectionManager, "ISelectionMgr")
            selection_data = selection_manager.CreateSelectData()
            selection_data.View = view
            selectable = _sw_type_info.early_bound_or_flag(
                entity, "ISilhouetteEdge", "Select2"
            )
            selected = bool(selectable.Select2(False, selection_data))
        else:
            selected = bool(view.SelectEntity(entity, False))
    elif xy is not None:
        selected = bool(
            draw.Extension.SelectByID2(
                "", entity_type, xy[0], xy[1], 0.0, False, 0, null_callout(), 0
            )
        )
    if not selected:
        where = "by entity" if xy is None else f"at sheet ({xy[0]:g}, {xy[1]:g})"
        raise RuntimeError(f"failed to select {label} {entity_type.lower()} {where}")
    count = int(draw.SelectionManager.GetSelectedObjectCount2(-1))
    entity = draw.SelectionManager.GetSelectedObject6(count, -1)
    if entity is None:
        raise RuntimeError(f"selected {label} {entity_type.lower()} has no entity")
    return entity


def _select_annotation_entity(
    adapter: Any,
    view: Any,
    *,
    edge_xy: tuple[float, float] | None,
    edge_entity: Any | None,
    entity: Any | None,
    entity_type: str,
    label: str,
) -> Any:
    """Select one drawing-view entity for a native attached annotation."""
    supplied = sum(value is not None for value in (edge_xy, edge_entity, entity))
    if supplied > 1:
        raise ValueError(
            f"{label} cannot specify more than one of edge_xy, edge_entity, or entity"
        )
    if entity is not None:
        return _select_view_entity(
            adapter, view, entity_type, None, label=label, entity=entity
        )
    if edge_entity is None:
        if edge_xy is None:
            raise ValueError(f"{label} requires edge_xy, edge_entity, or entity")
        return _select_view_entity(adapter, view, entity_type, edge_xy, label=label)

    draw = adapter.currentModel
    draw.ClearSelection2(True)
    selection_manager = _early_bound(draw.SelectionManager, "ISelectionMgr")
    selection_data = selection_manager.CreateSelectData()
    selection_data.View = view
    selected = adapter._attempt(lambda: edge_entity.Select2(False, selection_data))
    if not selected:
        selected = adapter._attempt(lambda: view.SelectEntity(edge_entity, False))
    if not selected:
        raise RuntimeError(f"failed to select {label} entity in drawing view")
    return edge_entity


def _surface_finish_entity_faces(
    selected_entity: Any, *, entity_type: str, label: str
) -> tuple[Any, ...]:
    """Return the model face(s) qualified by one drawing annotation entity."""
    entity_type = entity_type.upper()
    if entity_type == "FACE":
        return (selected_entity,)
    if entity_type == "SILHOUETTE":
        silhouette = _early_bound(selected_entity, "ISilhouetteEdge")
        face = silhouette.GetFace()
        return () if face is None else (face,)
    if entity_type == "EDGE":
        edge = _early_bound(selected_entity, "IEdge")
        return tuple(
            face for face in (edge.GetTwoAdjacentFaces2() or ()) if face is not None
        )
    raise ValueError(
        f"{label}: cannot validate a surface finish on entity type {entity_type!r}; "
        "expected EDGE, SILHOUETTE, or FACE"
    )


def _surface_finish_face_signatures(faces: Sequence[Any]) -> tuple[dict[str, Any], ...]:
    """Read candidate face geometry once for validation and optional diagnostics."""
    from _part_pmi import _face_geometry

    signatures: list[dict[str, Any]] = []
    for face in faces:
        geometry = _face_geometry(face)
        if geometry is None:
            continue
        signatures.append(
            {
                "geometry": geometry,
                "identity": geometry.identity,
                "parameters": tuple(round(value, 9) for value in geometry.parameters),
                "normal": geometry.outward_normal,
                "box": tuple(round(value, 9) for value in geometry.box),
            }
        )
    return tuple(signatures)


def _validate_surface_finish_control_face(
    selected_entity: Any,
    *,
    entity_type: str,
    control: SurfaceFinishControl,
    label: str,
) -> tuple[dict[str, Any], ...]:
    """Fail unless a selected drawing entity belongs to the controlled face."""
    from _part_pmi import _face_matches

    faces = _surface_finish_entity_faces(
        selected_entity, entity_type=entity_type, label=label
    )
    signatures = _surface_finish_face_signatures(faces)
    if any(_face_matches(item["geometry"], control.face) for item in signatures):
        return signatures
    diagnostic = tuple(
        {key: value for key, value in item.items() if key != "geometry"}
        for item in signatures
    )
    raise RuntimeError(
        f"{label}: selected {entity_type.lower()} does not touch controlled "
        f"surface-finish face {control.face!r}; candidates={diagnostic!r}"
    )


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
    annotation: Any | None = None,
    shoulder: bool = False,
    position_tolerance_m: float = 1.5e-5,
    callout_below: str = "",
) -> Any:
    """Attach a native datum-feature symbol to a drawing-view edge.

    ``entity_type`` widens the pick for entities that are not model edges —
    a revolve's flank lines are ``"SILHOUETTE"`` edges.
    """
    draw = adapter.currentModel
    if annotation is None:
        _select_annotation_entity(
            adapter,
            view,
            edge_xy=edge_xy,
            edge_entity=edge_entity,
            entity=entity,
            entity_type=entity_type,
            label=label,
        )
    else:
        ddoc = _early_bound(draw, "IDrawingDoc")
        name = view_name(adapter, view)
        if not ddoc.ActivateView(name):
            raise RuntimeError(f"failed to activate {label} drawing view {name!r}")
        draw.ClearSelection2(True)
        annotation = _sw_type_info.early_bound_or_flag(
            annotation, "IAnnotation", "Select3", "GetSpecificAnnotation"
        )
        selected = bool(annotation.Select3(False, null_callout()))
        if not selected:
            display = adapter._attempt(lambda: annotation.GetSpecificAnnotation())
            if display is not None:
                display = _sw_type_info.early_bound_or_flag(
                    display, "IDisplayDimension", "GetNameForSelection"
                )
                selection_name = str(display.GetNameForSelection() or "")
                selected = bool(
                    selection_name
                    and draw.Extension.SelectByID2(
                        selection_name,
                        "DIMENSION",
                        0.0,
                        0.0,
                        0.0,
                        False,
                        0,
                        null_callout(),
                        0,
                    )
                )
        if not selected:
            raise RuntimeError(f"failed to select {label} annotation")
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
    )
    if not tag.SetLabel(datum):
        raise RuntimeError(f"failed to label datum feature {datum} ({label})")
    if shoulder:
        tag.Shoulder = True
    tag_annotation = _sw_type_info.early_bound_or_flag(
        tag.GetAnnotation(), "IAnnotation", "GetPosition", "SetPosition2"
    )
    if not tag_annotation.SetPosition2(symbol_xy[0], symbol_xy[1], 0.0):
        raise RuntimeError(f"failed to position datum {datum} ({label})")
    actual_position = tag_annotation.GetPosition()
    position_error = (
        math.inf
        if not actual_position
        else math.hypot(
            float(actual_position[0]) - symbol_xy[0],
            float(actual_position[1]) - symbol_xy[1],
        )
    )
    if position_error > position_tolerance_m:
        raise RuntimeError(
            f"datum {datum} position did not persist ({label}): "
            f"{tuple(actual_position[:2]) if actual_position else None}; "
            f"requested={symbol_xy}, error={position_error:.6g} m, "
            f"limit={position_tolerance_m:.6g} m"
        )
    if str(tag.GetLabel()) != datum:
        raise RuntimeError(f"datum feature label did not persist ({label})")
    if callout_below and not tag.SetText(4, callout_below):
        raise RuntimeError(f"failed to set datum callout text ({label})")
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    return tag


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
    quantity: str = "",
    all_around: bool = False,
    label: str,
    entity_type: str = "EDGE",
    entity: Any | None = None,
    leader_attach_xy: tuple[float, float] | None = None,
) -> Any:
    """Attach a native feature-control frame to a drawing-view edge.

    ``entity_type`` widens the pick for entities that are not model edges —
    a revolve's flank lines are ``"SILHOUETTE"`` edges.
    """
    draw = adapter.currentModel
    edge = _select_annotation_entity(
        adapter,
        view,
        edge_xy=edge_xy,
        edge_entity=edge_entity,
        entity=entity,
        entity_type=entity_type,
        label=label,
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
    )
    frame_count = int(gtol.GetFrameCount() or 0)
    if frame_count == 0:
        if not gtol.AddFrame():
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
        if not gtol.SetFrameValues2(1, tolerance, "", *datum_values):
            raise RuntimeError(
                f"failed to seed feature-control frame for migration ({label})"
            )
        if not gtol.CanConvertFormat():
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
    xml = _gtol_frame_xml(characteristic, tolerance, datums=datums, diameter=diameter)
    if not migrated and not frame.SetSymbolXml(xml):
        raise RuntimeError(f"SOLIDWORKS rejected feature-control frame XML ({label})")
    applied = str(frame.GetSymbolXml() or "")
    if _GTOL_SYMBOLS[characteristic] not in applied or tolerance not in applied:
        raise RuntimeError(f"feature-control frame did not persist ({label})")
    if int(gtol.GetFormat()) != 2:  # swGtolFormatType_e.GTOL_SW2022 (current)
        raise RuntimeError(f"feature-control frame remained in old format ({label})")
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
        "SetLeaderAttachmentPointAtIndex",
        "GetLeaderPointsAtIndex",
    )
    # A GTol inserted from a selected display dimension reports its association
    # through IGtol.IsAttached/GetLeaderCount; whether the dimension ALSO lands
    # in the annotation's model-entity array is flow-dependent (0 on the
    # pre-merge insertion order, 1 on the current one), so accept either.
    # Ordinary edge/silhouette attachments must register exactly one entity.
    expected_entities = {0, 1} if entity_type == "DIMENSION" else {1}
    if entity_type != "DIMENSION" and int(annotation.GetAttachedEntityCount3()) != 1:
        if not annotation.SetAttachedEntities(dispatch_array([edge])):
            raise RuntimeError(f"failed to attach feature-control frame ({label})")
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
    if leader_attach_xy is not None and not annotation.SetLeaderAttachmentPointAtIndex(
        0, leader_attach_xy[0], leader_attach_xy[1], 0.0
    ):
        raise RuntimeError(f"failed to position feature-control-frame leader ({label})")
    draw.EditRebuild3()
    if (
        int(annotation.GetAttachedEntityCount3()) not in expected_entities
        or not bool(gtol.IsAttached())
        or int(gtol.GetLeaderCount()) != 1
    ):
        raise RuntimeError(
            f"feature-control frame attachment mismatch ({label}): "
            f"entities={annotation.GetAttachedEntityCount3()}, "
            f"expected in {sorted(expected_entities)}; "
            f"attached={bool(gtol.IsAttached())}; "
            f"leaders={gtol.GetLeaderCount()}, expected=1"
        )
    if leader_attach_xy is not None:
        points = list(annotation.GetLeaderPointsAtIndex(0) or ())
        if len(points) < 6:
            raise RuntimeError(f"feature-control-frame leader is unreadable ({label})")
        actual_attach = (float(points[-3]), float(points[-2]))
        attach_error = math.hypot(
            actual_attach[0] - leader_attach_xy[0],
            actual_attach[1] - leader_attach_xy[1],
        )
        if attach_error > 0.005:
            raise RuntimeError(
                f"feature-control-frame leader attachment moved ({label}): "
                f"actual={actual_attach}, requested={leader_attach_xy}, "
                f"error={attach_error:.6g} m"
            )
    draw.ClearSelection2(True)
    return gtol


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
    from _gtol_spec import gtol_frame_signature, validate_part_pmi

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
            position_tolerance_m=placement.position_tolerance_m,
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
            label=f"{label} {control.key}",
            entity_type=placement.attachment_type,
            entity=placement.entity,
            leader_attach_xy=placement.leader_attachment_xy,
        )
        frame = _early_bound(gtol.GetFrame(1), "IGtolFrame")
        if gtol_frame_signature(str(frame.GetSymbolXml() or "")) != (
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


@_telemetry.traced("drawing.surface_finish", label_param="label")
def add_surface_finish(
    adapter: Any,
    view: Any,
    *,
    edge_xy: tuple[float, float] | None = None,
    edge_entity: Any | None = None,
    symbol_xy: tuple[float, float],
    roughness_ra: str | None = None,
    control: SurfaceFinishControl | None = None,
    label: str,
    entity_type: str = "EDGE",
    entity: Any | None = None,
    leader_attach_xy: tuple[float, float] | None = None,
    production_method: str = "",
) -> Any:
    """Attach a native machining-required surface-finish symbol to an edge.

    ``entity_type`` widens a coordinate pick for entities that are not model
    edges — a revolve's flank lines are ``"SILHOUETTE"`` edges.  Pass a model
    ``edge_entity`` obtained from ``IView.GetVisibleEntities2`` when a small or
    overlapping projection makes coordinate selection ambiguous.
    """
    if control is not None:
        if roughness_ra is not None or production_method:
            raise ValueError(
                f"{label}: pass a part-owned control or drawing-owned values, not both"
            )
        roughness_ra = control.roughness_ra
        production_method = control.production_method
    if roughness_ra is None:
        raise ValueError(f"{label}: surface finish requires a part-owned control")
    selected_entity = _select_annotation_entity(
        adapter,
        view,
        edge_xy=edge_xy,
        edge_entity=edge_entity,
        entity=entity,
        entity_type=entity_type,
        label=label,
    )
    signatures: tuple[dict[str, Any], ...] = ()
    if control is not None:
        signatures = _validate_surface_finish_control_face(
            selected_entity,
            entity_type=entity_type,
            control=control,
            label=label,
        )
    elif os.getenv("HARMONIC_SURFACE_AUDIT") == "1":
        faces = _surface_finish_entity_faces(
            selected_entity, entity_type=entity_type, label=label
        )
        signatures = _surface_finish_face_signatures(faces)
    if os.getenv("HARMONIC_SURFACE_AUDIT") == "1":
        diagnostic = tuple(
            {key: value for key, value in item.items() if key != "geometry"}
            for item in signatures
        )
        _telemetry.info(
            f"SURFACE_AUDIT {label}: entity_type={entity_type}, faces={diagnostic!r}"
        )
    draw = adapter.currentModel
    symbol = draw.Extension.InsertSurfaceFinishSymbol3(
        1,  # installed R2026x swSFSymType_e.swSFMachining_Req
        _LEADER_BENT,  # swLeaderStyle_e.swBENT -- see _LEADER_BENT
        symbol_xy[0],
        symbol_xy[1],
        0.0,
        0,  # swSFLaySym_e.swSFNone
        10,  # swArrowStyle_e.swNO_ARROWHEAD
        "",
        "",
        "",
        "",
        "",
        "",
        "",
    )
    if symbol is None:
        raise RuntimeError(f"failed to insert Ra {roughness_ra} symbol ({label})")
    symbol = _sw_type_info.early_bound_or_flag(
        symbol, "ISFSymbol", "SetText", "GetSymbol", "GetText", "GetAnnotation"
    )
    if not symbol.SetText(8, f"Ra {roughness_ra}"):  # current-profile roughness value
        raise RuntimeError(f"failed to set Ra {roughness_ra} ({label})")
    if production_method and not symbol.SetText(2, production_method):
        raise RuntimeError(
            f"failed to set surface target {production_method!r} ({label})"
        )
    if int(symbol.GetSymbol()) != 1:
        raise RuntimeError(f"surface-finish symbol type did not persist ({label})")
    if str(symbol.GetText(8) or "").strip() != f"Ra {roughness_ra}":
        raise RuntimeError(f"surface-finish roughness did not persist ({label})")
    if production_method and str(symbol.GetText(2) or "").strip() != production_method:
        raise RuntimeError(f"surface target did not persist ({label})")
    annotation = _sw_type_info.early_bound_or_flag(
        symbol.GetAnnotation(),
        "IAnnotation",
        "SetPosition2",
        "SetLeader3",
        "SetLeaderAttachmentPointAtIndex",
    )
    leader_status = int(
        annotation.SetLeader3(
            _LEADER_BENT,
            _LEADER_SIDE_SMART,
            True,  # smart arrowhead
            False,  # perpendicular (GTol-only)
            False,  # all-around
            False,  # dashed
        )
    )
    if leader_status != 0:
        raise RuntimeError(
            f"failed to set a bent leader on the Ra {roughness_ra} symbol "
            f"({label}): SetLeader3 status {leader_status}"
        )
    if not annotation.SetPosition2(symbol_xy[0], symbol_xy[1], 0.0):
        raise RuntimeError(f"failed to position surface-finish symbol ({label})")
    if leader_attach_xy is not None and not annotation.SetLeaderAttachmentPointAtIndex(
        0, leader_attach_xy[0], leader_attach_xy[1], 0.0
    ):
        raise RuntimeError(f"failed to position surface-finish leader ({label})")
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    return symbol


@_telemetry.traced("drawing.centerline", label_param="label")
def add_view_centerline(
    adapter: Any,
    view: Any,
    *,
    face_xy: tuple[float, float] | None = None,
    label: str,
    entity: Any | None = None,
    face: Any | None = None,
) -> Any:
    """Insert the axis centerline of a cylindrical face shown in ``view``.

    A rectangular side view of a turned part is ambiguous without its axis
    (which pair of edges is the end faces vs the OD silhouette); the ASME
    centerline disambiguates. The cylinder's straight outline is a SILHOUETTE,
    not a selectable EDGE, so — per the API's own centerline example — select
    the cylindrical FACE and let ``InsertCenterLine2`` derive its axis.
    """
    draw = adapter.currentModel
    ddoc = _early_bound(
        draw, "IDrawingDoc"
    )  # IDrawingDoc view for drawing-only methods (same dispatch)
    _select_view_entity(
        adapter,
        view,
        "FACE",
        face_xy,
        label=label,
        entity=entity if entity is not None else face,
    )
    centerline = adapter._attempt(lambda: ddoc.InsertCenterLine2())
    if centerline is None:
        raise RuntimeError(f"failed to insert view centerline ({label})")
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    return centerline


@_telemetry.traced("drawing.section_view", label_param="label")
def create_section_view(
    adapter: Any,
    parent_view: Any,
    *,
    line_start: tuple[float, float],
    line_end: tuple[float, float],
    view_xy: tuple[float, float],
    section_label: str,
    scale: tuple[int, int] = (1, 1),
    label: str,
) -> Any:
    """Create a full, unaligned section from one straight cutting-plane line.

    The coordinates are drawing-sheet meters.  ``ISketchManager.CreateLine``
    leaves the new sketch segment selected, which is the documented precondition for
    ``CreateSectionViewAt5``.  The section is deliberately unaligned so a part
    recipe can place and scale it independently of the parent view.
    """
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    sketch_manager = _early_bound(draw.SketchManager, "ISketchManager")
    name = view_name(adapter, parent_view)
    if not ddoc.ActivateView(name):
        raise RuntimeError(f"failed to activate section parent view {name!r} ({label})")
    draw.ClearSelection2(True)
    segment = sketch_manager.CreateLine(
        float(line_start[0]),
        float(line_start[1]),
        0.0,
        float(line_end[0]),
        float(line_end[1]),
        0.0,
    )
    if segment is None:
        raise RuntimeError(f"failed to create section line ({label})")
    # swCreateSectionView_NotAligned | swCreateSectionView_ScaleWithModel
    section = ddoc.CreateSectionViewAt5(
        float(view_xy[0]),
        float(view_xy[1]),
        0.0,
        section_label,
        0x1 | 0x8,
        None,
        0.0,
    )
    if section is None:
        raise RuntimeError(f"failed to create section view ({label})")
    section = _sw_type_info.early_bound_or_flag(
        section, "IView", "GetSection", "SetViewPosition"
    )
    section.ScaleRatio = double_array([float(scale[0]), float(scale[1])])
    if not section.SetViewPosition(
        double_array([float(view_xy[0]), float(view_xy[1])]), False
    ):
        raise RuntimeError(f"failed to position section view ({label})")
    dr_section = section.GetSection()
    if dr_section is None:
        raise RuntimeError(f"section view has no section definition ({label})")
    dr_section = _sw_type_info.early_bound_or_flag(
        dr_section, "IDrSection", "SetAutoHatch", "SetLabel2"
    )
    dr_section.SetAutoHatch(True)
    if int(dr_section.SetLabel2(section_label)) < 0:
        raise RuntimeError(f"failed to persist section label ({label})")
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    return section


@_telemetry.traced("drawing.model_point_projection", label_param="label")
def model_point_in_view(
    adapter: Any,
    view: Any,
    xyz: tuple[float, float, float],
    *,
    label: str,
) -> tuple[float, float]:
    """Project a model-space point into drawing-sheet coordinates."""
    math_utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    model_point = math_utility.CreatePoint(double_array([float(v) for v in xyz]))
    if model_point is None:
        raise RuntimeError(f"failed to create model point ({label})")
    model_point = _early_bound(model_point, "IMathPoint")
    transform = _early_bound(view.ModelToViewTransform, "IMathTransform")
    view_point = model_point.MultiplyTransform(transform)
    if view_point is None:
        raise RuntimeError(f"failed to project model point into view ({label})")
    view_point = _early_bound(view_point, "IMathPoint")
    coordinates = list(view_point.ArrayData or ())
    if len(coordinates) < 2:
        raise RuntimeError(f"projected model point has no sheet coordinates ({label})")
    return (float(coordinates[0]), float(coordinates[1]))


@_telemetry.traced("drawing.linked_note", label_param="property_name")
def add_property_linked_note(
    adapter: Any,
    property_name: str,
    x: float,
    y: float,
    *,
    char_height: float | None = None,
) -> Any:
    """Place one note whose displayed text resolves from the source SLDPRT."""
    note = add_note(adapter, property_link(property_name), x, y)
    if note is None:
        raise RuntimeError(f"failed to add linked drawing note {property_name!r}")
    if char_height is None:
        return note

    note = _early_bound(note, "INote")
    annotation = note.GetAnnotation()
    if annotation is None:
        raise RuntimeError(f"linked drawing note {property_name!r} has no annotation")
    annotation = _early_bound(annotation, "IAnnotation")
    text_format = annotation.GetTextFormat(0)
    if text_format is None:
        raise RuntimeError(f"linked drawing note {property_name!r} has no text format")
    text_format.CharHeight = float(char_height)
    if not annotation.SetTextFormat(0, False, text_format):
        raise RuntimeError(
            f"failed to set linked drawing note {property_name!r} text height"
        )
    return note


@_telemetry.traced("drawing.linked_callout", label_param="property_name")
def add_property_linked_callout(
    adapter: Any,
    view: Any,
    *,
    property_name: str,
    edge_xy: tuple[float, float],
    note_xy: tuple[float, float],
) -> Any:
    """Attach one arrowed callout whose text resolves from the source SLDPRT."""
    draw = adapter.currentModel
    ddoc = _early_bound(
        draw, "IDrawingDoc"
    )  # IDrawingDoc view for drawing-only methods (same dispatch)
    name = view_name(adapter, view)
    if not ddoc.ActivateView(name):
        raise RuntimeError(f"failed to activate linked-callout view {name!r}")
    draw.ClearSelection2(True)
    edge = _select_edge(adapter, *edge_xy, append=False)
    note = draw.InsertNote(property_link(property_name))
    if note is None:
        raise RuntimeError(f"failed to insert linked callout {property_name!r}")
    note = _sw_type_info.early_bound_or_flag(note, "INote", "GetAnnotation")
    annotation = note.GetAnnotation()
    if annotation is None:
        raise RuntimeError(f"linked callout has no annotation: {property_name!r}")
    annotation = _sw_type_info.early_bound_or_flag(
        annotation,
        "IAnnotation",
        "GetAttachedEntityCount3",
        "SetAttachedEntities",
        "SetLeader3",
        "SetPosition2",
        "GetLeaderCount",
    )
    if int(annotation.GetAttachedEntityCount3()) != 1:
        if not annotation.SetAttachedEntities(dispatch_array([edge])):
            raise RuntimeError(f"failed to attach linked callout {property_name!r}")
    status = annotation.SetLeader3(1, 0, True, False, False, False)
    if status != 0:
        raise RuntimeError(
            f"failed to create linked-callout leader {property_name!r}: {status}"
        )
    if not annotation.SetPosition2(note_xy[0], note_xy[1], 0.0):
        raise RuntimeError(f"failed to position linked callout {property_name!r}")
    draw.EditRebuild3()
    if (
        int(annotation.GetAttachedEntityCount3()) != 1
        or int(annotation.GetLeaderCount()) != 1
    ):
        raise RuntimeError(f"linked callout {property_name!r} lacks one arrow")
    draw.ClearSelection2(True)
    return note


@_telemetry.traced("drawing.attached_note", label_param="label")
def add_attached_note(
    adapter: Any,
    view: Any,
    *,
    text: str,
    entity_xy: tuple[float, float] | None = None,
    note_xy: tuple[float, float],
    label: str,
    entity_type: str = "EDGE",
    entity: Any | None = None,
) -> Any:
    """Attach one literal arrowed note to a drawing-view entity.

    Provide EITHER ``entity_xy`` (a sheet-coordinate pick) OR ``entity`` (a
    precise model entity — for an offset/inclined rim whose projected edge has
    no stable sheet coordinate); ``_select_view_entity`` prefers ``entity``.
    """
    target = _select_view_entity(
        adapter, view, entity_type, entity_xy, label=label, entity=entity
    )
    draw = adapter.currentModel
    note = draw.InsertNote(text)
    if note is None:
        raise RuntimeError(f"failed to insert attached note ({label})")
    note = _sw_type_info.early_bound_or_flag(note, "INote", "GetAnnotation")
    annotation = note.GetAnnotation()
    if annotation is None:
        raise RuntimeError(f"attached note has no annotation ({label})")
    annotation = _sw_type_info.early_bound_or_flag(
        annotation,
        "IAnnotation",
        "GetAttachedEntityCount3",
        "SetAttachedEntities",
        "SetLeader3",
        "SetPosition2",
        "GetLeaderCount",
    )
    if int(annotation.GetAttachedEntityCount3()) != 1:
        if not annotation.SetAttachedEntities(dispatch_array([target])):
            raise RuntimeError(f"failed to attach note ({label})")
    status = annotation.SetLeader3(1, 0, True, False, False, False)
    if status != 0:
        raise RuntimeError(f"failed to create attached-note leader ({label}): {status}")
    if not annotation.SetPosition2(note_xy[0], note_xy[1], 0.0):
        raise RuntimeError(f"failed to position attached note ({label})")
    draw.EditRebuild3()
    if (
        int(annotation.GetAttachedEntityCount3()) != 1
        or int(annotation.GetLeaderCount()) != 1
    ):
        raise RuntimeError(f"attached note lacks one arrow ({label})")
    draw.ClearSelection2(True)
    return note


@_telemetry.traced("drawing.hole_callout", label_param="label")
def add_native_hole_callout(
    adapter: Any,
    view: Any,
    *,
    edge_xy: tuple[float, float] | None = None,
    callout_xy: tuple[float, float],
    label: str,
    edge: Any | None = None,
    process: str | None = None,
) -> Any:
    """Insert an associative Hole Wizard callout on a selected drawing edge.

    ``process`` is the shop instruction a machinist reads first -- ``"DRILL"``,
    ``"15/64 DRILL"``, ``"REAM"`` -- written into the callout's PREFIX
    compartment so the sheet reads ``15/64 DRILL <MOD-DIAM>5.95 THRU ALL``
    (Harvey #13: say drill or ream; drawing-simplicity-policy.md rule 7).  The
    size and depth stay native and associative; only the prefix is text.

    The callout DISPLAYS the part's hole tolerance; it does not own one. Set the
    fit on the hole feature in the SLDPRT (``_holes.wizard_holes``'s
    ``dia_tolerance_mm``) and it renders here as
    ``<MOD-DIAM>3.05 +0.10/0.00 THRU ALL``. Toleranceing the drawing dimension
    instead silently does nothing: ``IDimensionTolerance::SetValues`` returns
    True and stores the value -- ``GetMaxValue2`` reads it right back -- and the
    callout still prints the bare nominal.
    """
    _select_view_entity(adapter, view, "EDGE", edge_xy, label=label, entity=edge)
    draw = adapter.currentModel
    ddoc = _early_bound(
        draw, "IDrawingDoc"
    )  # IDrawingDoc view for drawing-only methods (same dispatch)
    display = ddoc.AddHoleCallout2(callout_xy[0], callout_xy[1], 0.0)
    if display is None:
        raise RuntimeError(f"failed to insert native hole callout ({label})")
    # AddHoleCallout2 leaves its PropertyManager page open.  Accept it through
    # the documented swCommands_PmOK command so doit remains unattended.
    if not adapter.swApp.RunCommand(-2, ""):  # swCommands_e.swCommands_PmOK
        raise RuntimeError(f"failed to accept native hole callout ({label})")
    display = _sw_type_info.early_bound_or_flag(
        display, "IDisplayDimension", "IsHoleCallout", "GetAnnotation"
    )
    if not display.IsHoleCallout():
        raise RuntimeError(f"inserted annotation is not a hole callout ({label})")
    annotation = _sw_type_info.early_bound_or_flag(
        display.GetAnnotation(), "IAnnotation", "SetPosition2"
    )
    if not annotation.SetPosition2(callout_xy[0], callout_xy[1], 0.0):
        raise RuntimeError(f"failed to position native hole callout ({label})")
    if process:
        # A Hole Wizard callout keeps its whole format string
        # (``<MOD-DIAM><DIM> THRU ALL``) in the PREFIX compartment, so the
        # process is PREPENDED to what is there -- replacing it silently drops
        # the size and depth (measured 2026-09-02: the sheet read "#14 DRILL").
        display = _sw_type_info.early_bound_or_flag(
            display, "IDisplayDimension", "SetText", "GetText"
        )
        existing = str(display.GetText(1) or "")  # swDimensionTextPrefix
        if not existing.strip():
            raise RuntimeError(
                f"hole callout has no format text to prefix ({label})"
            )
        prefix = process.rstrip() + " " + existing.lstrip()
        display.SetText(1, prefix)
        if str(display.GetText(1) or "") != prefix:
            raise RuntimeError(
                f"hole callout process prefix did not persist ({label}): "
                f"{display.GetText(1)!r}"
            )
        _telemetry.debug(f"hole callout {label}: prefix {prefix!r}")
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    return display


# The general-tolerance custom properties every part carries
# (_common.part_properties, from cad/config/title_block.yaml) and the drawing
# template's title block reads via $PRPSHEET. finalize_drawing requires them on
# the linked model so a stale part can't ship blank tolerance cells.
TITLE_BLOCK_TOLERANCE_PROPERTIES = (
    "TOL_LIN_XX",
    "TOL_LIN_XXX",
    "TOL_ANG",
    "TOL_SURFACE",
    # The DRILLED HOLES row's two cells. Required like the rest: with holes now
    # relying on this general tolerance UOS (no per-feature callout), a blank row
    # would silently drop every clearance hole's fit -- so a stale source part
    # that predates the TOL_HOLE_* stamp must fail loud here, not ship blank.
    "TOL_HOLE_MINUS",
    "TOL_HOLE_PLUS",
)
TITLE_BLOCK_REVISION_PROPERTY = "Revision"


def read_required_properties(
    model: Any, names: Sequence[str], *, required: Iterable[str]
) -> dict[str, str]:
    properties = {name: str(model.GetCustomInfoValue("", name) or "") for name in names}
    missing = [name for name in required if not properties.get(name)]
    if missing:
        raise RuntimeError(f"source part properties are missing: {missing}")
    revision = properties.get(TITLE_BLOCK_REVISION_PROPERTY)
    if revision is not None:
        expected = _config.release_revision()
        if revision != expected:
            raise RuntimeError(
                f"source model Revision {revision!r} != current release {expected!r}"
            )
    return properties


@_telemetry.traced("drawing.cosmetic_threads")
def import_cosmetic_threads(adapter: Any, view: Any) -> tuple[int, int]:
    """Import a view's cosmetic threads and count seed plus pattern instances.

    ``IDrawingDoc.InsertModelAnnotations3`` with ``swInsertCThreads`` makes this
    independent of each seat's drawing annotation preferences.
    ``GetCThreadCount`` counts seed objects, while each
    ``ICThread.GetPatternedTransformsCount`` supplies its repeated instances.
    """
    view = _sw_type_info.early_bound_or_flag(
        view, "IView", "GetCThreadCount", "GetFirstCThread"
    )
    draw = adapter.currentModel
    ddoc = _early_bound(
        draw, "IDrawingDoc"
    )  # IDrawingDoc view for drawing-only methods (same dispatch)
    name = view_name(adapter, view)
    ddoc.ActivateView(name)
    draw.ClearSelection2(True)
    selected = draw.Extension.SelectByID2(
        name, "DRAWINGVIEW", 0.0, 0.0, 0.0, False, 0, null_callout(), 0
    )
    if not selected:
        raise RuntimeError(f"failed to select drawing view {name!r}")
    adapter._attempt(
        lambda: ddoc.InsertModelAnnotations3(
            0,  # swImportModelItemsFromEntireModel
            0x1,  # swInsertCThreads
            False,
            True,
            True,
            False,
        )
    )
    adapter._attempt(lambda: adapter.currentModel.EditRebuild3())
    seed_count = int(adapter._get_attr_or_call(view, "GetCThreadCount") or 0)
    instance_count = 0
    thread = adapter._get_attr_or_call(view, "GetFirstCThread")
    visited = 0
    while thread is not None:
        visited += 1
        if visited > 10_000:
            raise RuntimeError("cosmetic-thread traversal exceeded 10,000 entries")
        thread = _sw_type_info.early_bound_or_flag(
            thread, "ICThread", "GetPatternedTransformsCount", "GetNext"
        )
        patterns = int(
            adapter._get_attr_or_call(thread, "GetPatternedTransformsCount") or 0
        )
        instance_count += 1 + patterns
        thread = adapter._get_attr_or_call(thread, "GetNext")
    if visited != seed_count:
        raise RuntimeError(
            f"cosmetic-thread count mismatch: API={seed_count}, traversed={visited}"
        )
    return seed_count, instance_count


# swUserPreferenceIntegerValue_e system colours, read off swconst.tlb R2026x
# (the docs print no integer).  A drawing-ADDED dimension or callout is a
# "non-imported annotation" and SolidWorks draws it in a grey that exports at
# ~level 128 -- the 75.00 / (93.00) / hole callouts read pale beside the black
# model-imported dimensions (machinist review 2026-09-02: "plotted in very
# pale gray ... reducing arm's-length readability"; Lipton: faint lines are
# for accountants).  Both books want every line on the print pressed hard.
_PREF_COLOR_NON_IMPORTED_ANNOTATION = 232
_PREF_COLOR_IMPORTED_DRIVEN_ANNOTATION = 113
_COLORREF_BLACK = 0


def _pin_annotation_ink(adapter: Any) -> None:
    """Pin the seat's driven / non-imported annotation colours to black.

    System (seat) preferences, so every sheet the seat exports gets the same
    ink; read back after each write so a rejected write fails loud instead of
    shipping pale dimensions.
    """
    sw = _early_bound(adapter.swApp, "ISldWorks")
    for pref in (
        _PREF_COLOR_NON_IMPORTED_ANNOTATION,
        _PREF_COLOR_IMPORTED_DRIVEN_ANNOTATION,
    ):
        if int(sw.GetUserPreferenceIntegerValue(pref)) == _COLORREF_BLACK:
            continue
        if not sw.SetUserPreferenceIntegerValue(pref, _COLORREF_BLACK):
            raise RuntimeError(f"failed to set annotation colour pref {pref}")
        if int(sw.GetUserPreferenceIntegerValue(pref)) != _COLORREF_BLACK:
            raise RuntimeError(f"annotation colour pref {pref} did not persist")
        _telemetry.debug(f"annotation colour pref {pref} pinned to black")


def _pin_dimension_text_and_leader_style(draw: Any) -> None:
    """Force every dimension on ``draw`` to a bent leader with HORIZONTAL text.

    Set on the DOCUMENT (``IModelDocExtension::SetUserPreferenceInteger``), not
    the application, so a build can never drift the seat's global preferences.

    This is the only mechanism that reaches dimensions: ``SetLeader3`` covers
    notes / GD&T / surface-finish symbols but explicitly not dimensions. Read
    back and raise on mismatch -- the preference's value enum is undocumented
    (read from swconst.tlb), so a silent no-op is exactly the failure mode to
    guard against.
    """
    for name, option in _DIM_DETAILING_SCOPES.items():
        ok = draw.Extension.SetUserPreferenceInteger(
            _PREF_DIM_TEXT_AND_LEADER_STYLE, option, _BROKEN_LEADER_HORIZONTAL_TEXT
        )
        applied = int(
            draw.Extension.GetUserPreferenceInteger(
                _PREF_DIM_TEXT_AND_LEADER_STYLE, option
            )
        )
        if not ok or applied != _BROKEN_LEADER_HORIZONTAL_TEXT:
            raise RuntimeError(
                "failed to pin dimension text/leader style to broken-leader + "
                f"horizontal-text for {name} (set returned {ok!r}, document "
                f"reads {applied})"
            )
    _telemetry.event(
        "drawing.dim_text_leader_style",
        style=_BROKEN_LEADER_HORIZONTAL_TEXT,
        scopes=len(_DIM_DETAILING_SCOPES),
    )


@_telemetry.traced("drawing.new_from_template")
def new_project_drawing(
    adapter: Any,
    *,
    property_view: str | None = None,
    scale: tuple[float, float] = (1.0, 1.0),
    decimals: int = 2,
) -> tuple[Any, Any]:
    """Create a drawing from the hand-made project template.

    The template embeds its own ASME B sheet format (title block, tolerance
    block, projection symbol), so there is no SetupSheet6 format re-apply; the
    only per-drawing knobs are the sheet scale (here) and WHICH view's model
    feeds the sheet's $PRPSHEET property links -- linked in finalize_drawing,
    once views exist (SolidWorks silently ignores a CustomPropertyView naming a
    view that does not exist yet, falling back to 'Default' = first view).
    ``property_view`` is accepted for compatibility and unused.
    """
    _ = property_view
    if not PROJECT_DRWDOT.is_file() or PROJECT_DRWDOT.stat().st_size == 0:
        raise FileNotFoundError(
            f"project drawing standard is missing: {PROJECT_DRWDOT}"
        )

    draw = new_drawing(
        adapter,
        template=str(PROJECT_DRWDOT),
        width=ASME_B_WIDTH_M,
        height=ASME_B_HEIGHT_M,
    )
    ddoc = _early_bound(
        draw, "IDrawingDoc"
    )  # IDrawingDoc view for drawing-only methods (same dispatch)
    # A hand-saved template can be saved while in Edit Sheet Format mode (it
    # was, the day the title block was drawn) -- a drawing created from it then
    # opens with the FORMAT layer active, where every pick lands on the sheet
    # format and view geometry is inert (all typed SelectByID2 picks fail).
    # EditSheet() drops back to the sheet layer; idempotent when already there.
    ddoc.EditSheet()
    _normalize_metric_edge_break_note(adapter, ddoc)
    sheet = adapter._get_attr_or_call(ddoc, "GetCurrentSheet")
    if sheet is None:
        raise RuntimeError("project drawing template has no current sheet")
    # 2 decimals by default: 3-decimal display (76.000) reads as false precision
    # next to the ±0.25 blanket tolerance. A drawing that genuinely needs finer
    # display (an exact inch conversion like 9.525) can pass decimals=3.
    set_units_mm(adapter, decimals=decimals)
    _pin_dimension_text_and_leader_style(draw)
    _pin_annotation_ink(adapter)
    if not sheet.SetScale(float(scale[0]), float(scale[1]), True, False):
        raise RuntimeError(f"failed to force ASME B sheet to {scale[0]:g}:{scale[1]:g}")
    assert_asme_b_sheet(adapter, sheet, phase="initial setup", scale=scale)
    # Normalize the viewport: sheet-coordinate picks (the hole-table datum
    # vertex / hole rims) hit-test with a PIXEL tolerance mapped through the
    # current zoom, and a hand-saved template opens at whatever zoom it was
    # saved with (the old generated one happened to be saved fit). Fit once so
    # coordinate picks are deterministic regardless of how the template binary
    # was last saved.
    draw.ViewZoomtofit2()
    draw.ForceRebuild3(False)
    draw.EditRebuild3()
    return draw, sheet


@_telemetry.traced("drawing.create_sheets", label_param="label")
def create_blank_drawing_sheets(
    adapter: Any, sheet_names: Sequence[str], *, label: str
) -> None:
    """Rename the initial blank sheet and duplicate it into a checked package."""
    if not sheet_names or len(sheet_names) != len(set(sheet_names)):
        raise ValueError(f"{label}: sheet names must be nonempty and unique")
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    sheet = ddoc.GetCurrentSheet()
    if sheet is None:
        raise RuntimeError(f"{label}: drawing template has no initial sheet")
    initial_names = tuple(adapter._get_attr_or_call(ddoc, "GetSheetNames") or ())
    if len(initial_names) != 1:
        raise RuntimeError(
            f"{label}: drawing template has {len(initial_names)} sheets, expected 1"
        )
    if next(iter_views(adapter), None) is not None:
        raise RuntimeError(f"{label}: initial drawing sheet is not blank")
    sheet.SetName(sheet_names[0])
    renamed = str(adapter._get_attr_or_call(sheet, "GetName") or "")
    if renamed != sheet_names[0]:
        raise RuntimeError(f"{label}: failed to rename initial sheet: {renamed!r}")

    for previous_name, new_name in zip(sheet_names[:-1], sheet_names[1:], strict=True):
        pasted_name = ""
        for attempt in range(1, 4):
            if not ddoc.ActivateSheet(previous_name):
                raise RuntimeError(f"{label}: failed to activate {previous_name!r}")
            before_names = tuple(adapter._get_attr_or_call(ddoc, "GetSheetNames") or ())
            draw.ClearSelection2(True)
            if not draw.Extension.SelectByID2(
                previous_name,
                "SHEET",
                0.0,
                0.0,
                0.0,
                False,
                0,
                null_callout(),
                0,
            ):
                raise RuntimeError(f"{label}: failed to select {previous_name!r}")
            draw.EditCopy()
            returned = bool(ddoc.PasteSheet(2, 2))
            after_names = tuple(adapter._get_attr_or_call(ddoc, "GetSheetNames") or ())
            added = tuple(name for name in after_names if name not in before_names)
            if len(after_names) == len(before_names) + 1 and len(added) == 1:
                pasted_name = added[0]
                if not returned:
                    _telemetry.warn(
                        f"{label}: PasteSheet returned false but created "
                        f"{pasted_name!r}"
                    )
                break
            _telemetry.warn(
                f"{label}: PasteSheet attempt {attempt}/3 created no sheet "
                f"(returned={returned!r}, before={before_names!r}, "
                f"after={after_names!r})"
            )
        if not pasted_name:
            raise RuntimeError(f"{label}: failed to duplicate {previous_name!r}")
        if not ddoc.ActivateSheet(pasted_name):
            raise RuntimeError(f"{label}: failed to activate {pasted_name!r}")
        sheet = ddoc.GetCurrentSheet()
        if sheet is None:
            raise RuntimeError(f"{label}: pasted sheet has no ISheet")
        sheet.SetName(new_name)
        renamed = str(adapter._get_attr_or_call(sheet, "GetName") or "")
        if renamed != new_name:
            raise RuntimeError(f"{label}: failed to rename sheet: {renamed!r}")

    actual = tuple(adapter._get_attr_or_call(ddoc, "GetSheetNames") or ())
    if actual != tuple(sheet_names):
        raise RuntimeError(f"{label}: sheet order mismatch: {actual!r}")


@_telemetry.traced("drawing.normalize_edge_break")
def _normalize_metric_edge_break_note(adapter: Any, ddoc: Any) -> None:
    """Replace the template's inch-origin edge break with its metric value."""
    sheet_view = adapter._attempt(lambda: ddoc.GetFirstView())
    if sheet_view is None:
        raise RuntimeError("drawing template has no sheet view for note normalization")
    annotations = (
        adapter._attempt(
            lambda: adapter._get_attr_or_call(sheet_view, "GetAnnotations")
        )
        or []
    )
    matched = 0
    for annotation in annotations:
        annotation = _sw_type_info.early_bound_or_flag(
            annotation, "IAnnotation", "GetType", "GetSpecificAnnotation"
        )
        if int(adapter._get_attr_or_call(annotation, "GetType") or 0) != _ANNOT_NOTE:
            continue
        specific = adapter._attempt(
            lambda a=annotation: adapter._get_attr_or_call(a, "GetSpecificAnnotation")
        )
        if specific is None:
            continue
        note = _sw_type_info.early_bound_or_flag(
            specific, "INote", "GetText", "SetText"
        )
        raw = str(adapter._get_attr_or_call(note, "GetText") or "")
        normalized = " ".join(raw.upper().split())
        if normalized not in {_OLD_EDGE_BREAK_NOTE, _METRIC_EDGE_BREAK_NOTE}:
            continue
        matched += 1
        if normalized == _METRIC_EDGE_BREAK_NOTE:
            continue
        changed = adapter._attempt(
            lambda n=note: n.SetText(_METRIC_EDGE_BREAK_NOTE), default=False
        )
        if not changed:
            raise RuntimeError("failed to replace drawing edge-break note")
        applied = " ".join(
            str(adapter._get_attr_or_call(note, "GetText") or "").upper().split()
        )
        if applied != _METRIC_EDGE_BREAK_NOTE:
            raise RuntimeError(
                f"drawing edge-break note replacement did not persist: {applied!r}"
            )
    if matched != 1:
        raise RuntimeError(
            "drawing template must contain exactly one recognized edge-break "
            f"note, found {matched}"
        )
    _telemetry.event("drawing.edge_break_normalized", value_mm=0.25)


def set_hidden_lines_removed(adapter: Any, view: Any) -> None:
    ok = adapter._attempt(
        lambda: view.SetDisplayMode4(False, 2, False, False, True), default=False
    )
    if not ok:
        raise RuntimeError("failed to set hidden-lines-removed drawing view")


def set_hidden_lines_visible(adapter: Any, view: Any) -> None:
    """Show hidden edges (greyed) in ``view`` -- for a view whose job is to
    communicate internal/cross-drilled features."""
    ok = adapter._attempt(
        lambda: view.SetDisplayMode4(False, 1, False, False, True), default=False
    )
    if not ok:
        raise RuntimeError("failed to set hidden-lines-visible drawing view")


def assert_asme_b_sheet(
    adapter: Any, sheet: Any, *, phase: str, scale: tuple[float, float] = (1.0, 1.0)
) -> None:
    properties = list(adapter._get_attr_or_call(sheet, "GetProperties2") or [])
    if len(properties) < 7:
        raise RuntimeError(
            f"{phase}: incomplete drawing sheet properties {properties!r}"
        )
    if properties[2:4] != [float(scale[0]), float(scale[1])]:
        raise RuntimeError(
            f"{phase}: drawing sheet scale is not "
            f"{scale[0]:g}:{scale[1]:g}: {properties!r}"
        )
    if (
        abs(properties[5] - ASME_B_WIDTH_M) > 1e-6
        or abs(properties[6] - ASME_B_HEIGHT_M) > 1e-6
    ):
        raise RuntimeError(f"{phase}: drawing sheet is not ASME B size: {properties!r}")


def _contact_preview_grid(page_count: int) -> tuple[int, int]:
    """Return the contact-preview column/row count for a multi-sheet drawing."""
    if page_count < 2:
        raise ValueError(f"contact preview requires at least 2 pages, got {page_count}")
    if page_count <= 4:
        return (2, 2)
    columns = math.ceil(math.sqrt(page_count))
    return (columns, math.ceil(page_count / columns))


@_telemetry.traced("drawing.render_png")
def render_pdf_png(pdf: Path, png: Path, *, expected_pages: int = 1) -> None:
    """Render a drawing PDF to its preview PNG.

    Single-sheet drawings retain the historical one-page 300 dpi preview.
    Multi-sheet drawings use the registered preview path for a contact sheet,
    keeping the doit/cache/release artifact contract to one PNG. The historical
    2x2 layout is retained through four pages; larger drawings use the smallest
    near-square grid that fits every page. Exact page images for a review can be
    rendered from the packaged vector PDF.
    """
    import pypdfium2 as pdfium
    from PIL import Image

    document = pdfium.PdfDocument(str(pdf))
    if len(document) != expected_pages:
        raise RuntimeError(
            f"drawing PDF has {len(document)} pages, expected {expected_pages}"
        )
    images: list[Any] = []
    for index in range(expected_pages):
        page = document[index]
        image = page.render(scale=ASME_B_DPI / 72.0).to_pil()
        page.close()
        if image.size == (ASME_B_PNG_SIZE[0], ASME_B_PNG_SIZE[1] + 1):
            image = image.crop((0, 0, *ASME_B_PNG_SIZE))
        if image.size != ASME_B_PNG_SIZE:
            document.close()
            raise RuntimeError(
                f"ASME B PNG page {index + 1} is {image.size}, "
                f"expected {ASME_B_PNG_SIZE}"
            )
        images.append(image)
    document.close()
    png.parent.mkdir(parents=True, exist_ok=True)
    if expected_pages == 1:
        images[0].save(png, dpi=(ASME_B_DPI, ASME_B_DPI))
        return

    columns, rows = _contact_preview_grid(expected_pages)
    cell_size = (ASME_B_PNG_SIZE[0] // columns, ASME_B_PNG_SIZE[1] // rows)
    scale = min(
        cell_size[0] / ASME_B_PNG_SIZE[0],
        cell_size[1] / ASME_B_PNG_SIZE[1],
    )
    preview_size = (
        round(ASME_B_PNG_SIZE[0] * scale),
        round(ASME_B_PNG_SIZE[1] * scale),
    )
    contact = Image.new("RGB", ASME_B_PNG_SIZE, "white")
    for index, image in enumerate(images):
        cell = image.resize(preview_size, Image.Resampling.LANCZOS)
        column = index % columns
        row = index // columns
        contact.paste(
            cell,
            (
                column * cell_size[0] + (cell_size[0] - preview_size[0]) // 2,
                row * cell_size[1] + (cell_size[1] - preview_size[1]) // 2,
            ),
        )
    contact.save(png, dpi=(ASME_B_DPI, ASME_B_DPI))


def sanitize_pdf_metadata(pdf: Path, *, title: str, expected_pages: int = 1) -> None:
    """Replace seat/user PDF metadata while preserving the vector page."""
    from pypdf import PdfReader, PdfWriter

    reader = PdfReader(pdf)
    if len(reader.pages) != expected_pages:
        raise RuntimeError(
            f"drawing PDF has {len(reader.pages)} pages, expected {expected_pages}"
        )
    writer = PdfWriter()
    writer.clone_document_from_reader(reader)
    metadata = {
        "/Title": title,
        "/Author": "Harmonic Analyzer Project",
        "/Subject": "Hobby-machinist manufacturing drawing",
        "/Keywords": "harmonic analyzer, manufacturing drawing, #4-40 UNC",
        "/Creator": "Harmonic Analyzer SolidWorks drawing pipeline",
        "/Producer": "Harmonic Analyzer Project",
    }
    writer.add_metadata(metadata)
    temporary = pdf.with_suffix(".sanitized.pdf")
    try:
        writer.write(temporary)
        temporary.replace(pdf)
    finally:
        temporary.unlink(missing_ok=True)
    reread = PdfReader(pdf).metadata or {}
    for key, value in metadata.items():
        if reread.get(key) != value:
            raise RuntimeError(f"PDF metadata {key} did not sanitize")


def _select_edge(adapter: Any, x: float, y: float, *, append: bool) -> Any:
    draw = adapter.currentModel
    selected = draw.Extension.SelectByID2(
        "", "EDGE", x, y, 0.0, append, 0, null_callout(), 0
    )
    if not selected:
        raise RuntimeError(f"failed to select hole edge at sheet point ({x}, {y})")
    index = int(draw.SelectionManager.GetSelectedObjectCount2(-1))
    edge = draw.SelectionManager.GetSelectedObject6(index, -1)
    if edge is None:
        raise RuntimeError(f"hole-edge selection {index} returned no entity")
    return edge


def add_hole_group_tags(
    adapter: Any,
    view: Any,
    tag: str,
    *,
    edge_points: Sequence[tuple[float, float]],
    note_positions: Sequence[tuple[float, float]],
) -> list[Any]:
    """Put the same short arrowed group tag on every hole in a group.

    ``IAnnotation.SetAttachedEntities`` throws for multiple edges on a note in
    SolidWorks 2026.  One leadered note per hole is both supported and clearer:
    the nearby schedule owns the full specification while every individual hole
    visibly carries its group letter.
    """
    if not edge_points:
        raise ValueError("hole group tags require at least one edge")
    if len(edge_points) != len(note_positions):
        raise ValueError("hole edge and tag-position counts differ")
    draw = adapter.currentModel
    ddoc = _early_bound(
        draw, "IDrawingDoc"
    )  # IDrawingDoc view for drawing-only methods (same dispatch)
    name = view_name(adapter, view)
    if not ddoc.ActivateView(name):
        raise RuntimeError(f"failed to activate drawing view {name!r}")
    notes: list[Any] = []
    for edge_point, note_position in zip(edge_points, note_positions, strict=True):
        draw.ClearSelection2(True)
        edge = _select_edge(adapter, *edge_point, append=False)
        note = draw.InsertNote(tag)
        if note is None:
            raise RuntimeError(f"failed to insert hole group tag {tag!r}")
        note = _sw_type_info.early_bound_or_flag(note, "INote", "GetAnnotation")
        annotation = note.GetAnnotation()
        if annotation is None:
            raise RuntimeError(f"hole group tag has no annotation: {tag!r}")
        annotation = _sw_type_info.early_bound_or_flag(
            annotation,
            "IAnnotation",
            "GetAttachedEntityCount3",
            "SetAttachedEntities",
            "SetLeader3",
            "SetPosition2",
            "GetLeaderCount",
        )
        if int(annotation.GetAttachedEntityCount3()) != 1:
            if not annotation.SetAttachedEntities(dispatch_array([edge])):
                raise RuntimeError(f"failed to attach hole group tag {tag!r}")
        leader_status = annotation.SetLeader3(1, 0, True, False, False, False)
        if leader_status != 0:
            raise RuntimeError(
                f"failed to create hole-group tag leader: status={leader_status}"
            )
        if not annotation.SetPosition2(*note_position, 0.0):
            raise RuntimeError(f"failed to position hole group tag {tag!r}")
        draw.EditRebuild3()
        if (
            int(annotation.GetAttachedEntityCount3()) != 1
            or int(annotation.GetLeaderCount()) != 1
        ):
            raise RuntimeError(f"hole group tag {tag!r} lacks one attached arrow")
        notes.append(note)
    draw.ClearSelection2(True)
    return notes


@_telemetry.traced("drawing.marked_dimensions")
def insert_marked_dimensions(adapter: Any, view: Any) -> list[Any]:
    """Import the source part's marked-for-drawing dimensions into ``view``.

    Parts mark exactly their manufacturing dimensions
    (``_drawing_marks.mark_dimensions_for_drawing``), so the import mask is
    ``swInsertDimensionsMarkedForDrawing`` only.
    """
    draw = adapter.currentModel
    ddoc = _early_bound(
        draw, "IDrawingDoc"
    )  # IDrawingDoc view for drawing-only methods (same dispatch)
    name = view_name(adapter, view)
    ddoc.ActivateView(name)
    draw.ClearSelection2(True)
    selected = draw.Extension.SelectByID2(
        name, "DRAWINGVIEW", 0.0, 0.0, 0.0, False, 0, null_callout(), 0
    )
    if not selected:
        raise RuntimeError(f"failed to select drawing view {name!r}")
    result = adapter._attempt(
        lambda: ddoc.InsertModelAnnotations3(
            0,  # swImportModelItemsFromEntireModel
            _INSERT_DIMS_MARKED | _INSERT_HOLE_WIZARD_LOCATION_DIMS,
            False,
            True,
            True,
            False,
        )
    )
    if not result or isinstance(result, str):
        return []
    annotations = [
        _sw_type_info.early_bound_or_flag(
            annotation, "IAnnotation", "GetSpecificAnnotation"
        )
        for annotation in result
    ]
    names = sorted(
        name
        for name in (dimension_name(adapter, annotation) for annotation in annotations)
        if name
    )
    _telemetry.info(
        f"model-item import {name}: annotations={len(annotations)}, dimensions={names}"
    )
    return annotations


def delete_unnamed_imports(adapter: Any, annotations: list[Any]) -> list[Any]:
    """Remove automatic cosmetic-thread callouts from model annotation import."""
    draw = adapter.currentModel
    survivors: list[Any] = []
    for annotation in annotations:
        annotation = _sw_type_info.early_bound_or_flag(
            annotation, "IAnnotation", "Select2"
        )
        if dimension_name(adapter, annotation):
            survivors.append(annotation)
            continue
        draw.ClearSelection2(True)
        if not annotation.Select2(False, 0):
            raise RuntimeError("failed to select an automatic model annotation")
        draw.EditDelete()
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    return survivors


@_telemetry.traced("drawing.curate_dimensions", label_param="view_label")
def curate_view_dimensions(
    adapter: Any,
    view: Any,
    *,
    keep: dict[str, tuple[float, float]],
    view_label: str,
) -> list[Any]:
    """Import a view's marked model dimensions and keep exactly ``keep``.

    ``keep`` maps each surviving dimension's parametric name to its sheet
    position (meters).  Everything else the import produced is deleted; a
    missing expected dimension fails loud — the print must carry every
    manufacturing dimension the recipe promises.
    """
    annotations = delete_unnamed_imports(
        adapter, insert_marked_dimensions(adapter, view)
    )
    names = {dimension_name(adapter, annotation) for annotation in annotations}
    delete = tuple(sorted(name for name in names if name and name not in keep))
    curated = curate_dimensions(
        adapter, annotations, delete=delete, reposition=dict(keep)
    )
    present = {dimension_name(adapter, annotation) for annotation in curated}
    missing = sorted(set(keep) - present)
    if missing:
        raise RuntimeError(
            f"{view_label} view is missing model dimensions: {missing}; "
            f"available={sorted(present)}"
        )
    return curate_dimensions(adapter, curated, reposition=dict(keep))


def set_dimension_callouts(
    adapter: Any,
    annotations: Iterable[Any],
    callout_text: dict[str, str],
    *,
    location: Literal["above", "below"] = "below",
) -> None:
    """Append native callout text above or below named dimensions.

    A bare Ø does not tell the machinist whether a hole is through or blind;
    ASME hole callouts carry that below the value.  Keyed on the parametric
    dimension name, so a value collision can never stamp the wrong hole.

    ``above`` is required when a datum feature symbol is attached to the same
    size dimension: SOLIDWORKS places that symbol between the primary value and
    the below-callout lane, while the above-callout lane remains unobstructed.
    """
    text_part = {
        "above": 3,  # swDimensionTextCalloutAbove
        "below": _DIMENSION_TEXT_CALLOUT_BELOW,
    }[location]
    remaining = dict(callout_text)
    for annotation in annotations:
        annotation = _sw_type_info.early_bound_or_flag(
            annotation, "IAnnotation", "GetSpecificAnnotation"
        )
        name = dimension_name(adapter, annotation)
        text = remaining.pop(name, None)
        if text is None:
            continue
        display = adapter._attempt(lambda a=annotation: a.GetSpecificAnnotation())
        if display is None:
            raise RuntimeError(f"dimension {name!r} has no display annotation")
        display = _sw_type_info.early_bound_or_flag(
            display, "IDisplayDimension", "SetText"
        )
        adapter._attempt(lambda d=display, s=text: d.SetText(text_part, s))
    if remaining:
        raise RuntimeError(f"dimension callouts not applied: {sorted(remaining)}")
    adapter.currentModel.EditRebuild3()


def set_dimension_text(
    adapter: Any, annotations: Iterable[Any], replacement: dict[str, str]
) -> None:
    """Replace the entire displayed text of named model dimensions.

    This is for associative size callouts whose model parameter is only the
    view carrier.  In particular, a schematic thread-minor cylinder must read
    as its thread designation rather than masquerading as a manufactured
    plain-diameter feature.
    """
    remaining = dict(replacement)
    for annotation in annotations:
        annotation = _sw_type_info.early_bound_or_flag(
            annotation, "IAnnotation", "GetSpecificAnnotation"
        )
        name = dimension_name(adapter, annotation)
        text = remaining.pop(name, None)
        if text is None:
            continue
        display = adapter._attempt(lambda a=annotation: a.GetSpecificAnnotation())
        if display is None:
            raise RuntimeError(f"dimension {name!r} has no display annotation")
        display = _sw_type_info.early_bound_or_flag(
            display, "IDisplayDimension", "SetText", "GetText"
        )
        # SetText is void.  With swDimensionTextAll it stores the replacement
        # in the prefix compartment and suppresses the numeric value; GetText
        # explicitly rejects swDimensionTextAll, so read back the prefix.
        display.SetText(0, text)  # swDimensionTextAll
        if str(display.GetText(1) or "") != text:  # swDimensionTextPrefix
            raise RuntimeError(f"dimension text did not persist for {name!r}")
    if remaining:
        raise RuntimeError(f"dimension text not applied: {sorted(remaining)}")
    adapter.currentModel.EditRebuild3()


@_telemetry.traced("drawing.reference_dimension", label_param="label")
def set_reference_dimension(
    adapter: Any,
    annotation: Any,
    *,
    label: str,
    diameter: bool = False,
) -> Any:
    """Parenthesize one displayed nominal as an ASME reference dimension."""
    annotation = _sw_type_info.early_bound_or_flag(
        annotation, "IAnnotation", "GetSpecificAnnotation"
    )
    display = adapter._attempt(lambda: annotation.GetSpecificAnnotation())
    if display is None:
        raise RuntimeError(f"{label} has no display dimension")
    display = _sw_type_info.early_bound_or_flag(
        display, "IDisplayDimension", "SetText", "GetText"
    )
    prefix_text = "(<MOD-DIAM>" if diameter else "("
    display.SetText(1, prefix_text)  # swDimensionTextPrefix
    display.SetText(2, ")")  # swDimensionTextSuffix
    prefix = str(display.GetText(1) or "")
    suffix = str(display.GetText(2) or "")
    if (prefix, suffix) != (prefix_text, ")"):
        raise RuntimeError(
            f"failed to parenthesize {label}: prefix={prefix!r}, suffix={suffix!r}"
        )
    adapter.currentModel.EditRebuild3()
    return display


def _span_scan_attrs(**attributes: float) -> None:
    """Attach aggregate scan counts to the CURRENT span.

    ``@traced`` owns the span, so there is no handle to set attributes on.
    A no-op when nothing is recording, so callers never guard.
    """
    span = _telemetry.trace.get_current_span()
    for key, value in attributes.items():
        span.set_attribute(key, value)


def _edge_endpoint_key(adapter: Any, edge: Any) -> tuple[float, ...] | None:
    """Return one model edge's endpoints as a sortable key, or ``None``.

    The stable identity of an edge, for picking purposes. ``IEdge`` offers no
    usable id -- ``GetID`` is documented for IMPORTED bodies only, is not saved
    with the document, and any add-in may reassign it -- so geometry is what
    there is. ``GetCurveParams2`` returns
    ``(start xyz, end xyz, start/end u, 3 packed doubles)``; the first six are
    the endpoints in model space, which is enough to order the visible edges of
    one component totally and identically on every run.

    ``GetCurve()`` must precede it: SolidWorks does not retain the underlying
    curve, and ``GetCurveParams2`` reads what ``GetCurve`` generated.

    ``None`` when the geometry cannot be read, so an unreadable edge drops out
    of the running instead of failing the drawing -- the caller raises only if
    NO edge on the component yields a key.
    """
    edge = _early_bound(edge, "IEdge")
    if adapter._attempt(lambda e=edge: e.GetCurve(), default=None) is None:
        return None
    params = adapter._attempt(lambda e=edge: e.GetCurveParams2(), default=None)
    if not params or len(params) < 6:
        return None
    return tuple(float(value) for value in params[:6])


@_telemetry.traced("drawing.dimension_precision")
def set_dimension_precision(
    adapter: Any, annotations: Iterable[Any], precision: dict[str, int]
) -> None:
    """Override the primary decimal places of specific NAMED dimensions.

    The document default (``set_units_mm``) is 2 decimals, which reads as false
    precision on most dims.  A dimension whose value is an exact conversion the
    notes cite to 3 places — e.g. the crank shaft bore, Ø9.525 = 3/8 in — must
    display 3 so the view matches the note (otherwise 9.53-on-view vs
    9.525-in-note reads as a contradiction).  Keyed on the parametric dimension
    name so a value collision can never repick the wrong dimension.

    The span carries how many annotations were SCANNED alongside how many were
    changed: recipes hand this collections of very different sizes, so without
    the scan count the duration cannot be attributed to its workload -- the same
    distinction the geometry scans in ``_gear_drawing_entities`` record.
    """
    # swDimensionPrecisionSettings_e.swDoNotChangePrecisionSetting: leave the
    # dual / tolerance precisions untouched, override only the primary.
    do_not_change = -1
    remaining = dict(precision)
    scanned = 0
    changed = 0
    for annotation in annotations:
        scanned += 1
        annotation = _sw_type_info.early_bound_or_flag(
            annotation, "IAnnotation", "GetSpecificAnnotation"
        )
        name = dimension_name(adapter, annotation)
        digits = remaining.pop(name, None)
        if digits is None:
            continue
        display = adapter._attempt(lambda a=annotation: a.GetSpecificAnnotation())
        if display is None:
            raise RuntimeError(f"dimension {name!r} has no display annotation")
        display = _sw_type_info.early_bound_or_flag(
            display, "IDisplayDimension", "SetPrecision3", "GetPrimaryPrecision2"
        )
        result = adapter._attempt(
            lambda d=display, n=digits: d.SetPrecision3(
                n, do_not_change, do_not_change, do_not_change
            )
        )
        if result is None:
            raise RuntimeError(f"failed to set precision on dimension {name!r}")
        # SetPrecision3 reports rejection via its RETURN STATUS, not by raising, so a
        # None-only check treats a failure code as success -- and the dim would ship
        # at the 2-decimal sheet default (Ø9.53) against a Ø9.525 note (codex #246).
        # The status enum's success value is undocumented, so verify the SIDE EFFECT:
        # read the primary precision back and confirm it took.
        applied = adapter._attempt(lambda d=display: d.GetPrimaryPrecision2())
        if applied != digits:
            raise RuntimeError(
                f"precision override on dimension {name!r} did not take: "
                f"requested {digits} decimals, dimension reports {applied}"
            )
        changed += 1
    _span_scan_attrs(scanned=scanned, changed=changed)
    if remaining:
        raise RuntimeError(f"dimension precision not applied: {sorted(remaining)}")
    adapter.currentModel.EditRebuild3()


@_telemetry.traced("drawing.reference_dimensions")
def set_reference_dimensions(
    adapter: Any, annotations: Iterable[Any], names: Iterable[str]
) -> None:
    """Parenthesize NAMED dimensions so they read as REFERENCE, not controlling.

    A fastener modeled at its thread MINOR diameter carries the real spec in a
    thread callout; the modeled OD is reference geometry, not a controlling
    dimension.  Showing that OD as a hard value contradicts the thread callout
    (a 5/16-18 thread's Ø6.20 minor cannot grow crests — codex machinist
    review), so the OD dim is boxed in parentheses: ASME reference-dimension
    notation.  Keyed on the parametric name so a value collision can never
    parenthesize the wrong dimension.  Fails loud if any name is unmatched.

    ``IDisplayDimension.ShowParenthesis`` only affects "text above the dimension
    line", which a leadered diameter callout does not have (it sets the flag but
    renders nothing), so instead bracket the value with a "(" prefix and ")"
    suffix via ``SetText`` — the same proven channel ``set_dimension_callouts``
    uses for the below-text — which renders on any dimension form.
    """
    text_prefix = 1  # swDimensionTextParts_e.swDimensionTextPrefix
    text_suffix = 2  # swDimensionTextParts_e.swDimensionTextSuffix
    # A custom prefix REPLACES the auto diameter glyph, so carry SolidWorks'
    # own "<MOD-DIAM>" token to keep the Ø on a diameter dim: "(Ø6.20)".
    open_paren = "(<MOD-DIAM>"
    wanted = set(names)
    marked: set[str] = set()
    for annotation in annotations:
        annotation = _sw_type_info.early_bound_or_flag(
            annotation, "IAnnotation", "GetSpecificAnnotation"
        )
        name = dimension_name(adapter, annotation)
        if name not in wanted:
            continue
        display = adapter._attempt(lambda a=annotation: a.GetSpecificAnnotation())
        if display is None:
            raise RuntimeError(f"dimension {name!r} has no display annotation")
        display = _sw_type_info.early_bound_or_flag(
            display, "IDisplayDimension", "SetText", "GetText"
        )
        adapter._attempt(lambda d=display: d.SetText(text_prefix, open_paren))
        adapter._attempt(lambda d=display: d.SetText(text_suffix, ")"))
        # SetText reports nothing, so verify the SIDE EFFECT: read the parts back
        # (a silent no-op would ship the OD as a controlling dim vs the thread).
        got_prefix = adapter._attempt(lambda d=display: d.GetText(text_prefix))
        got_suffix = adapter._attempt(lambda d=display: d.GetText(text_suffix))
        if str(got_prefix) != open_paren or str(got_suffix) != ")":
            raise RuntimeError(
                f"reference (parenthesis) mark on dimension {name!r} did not take: "
                f"prefix={got_prefix!r} suffix={got_suffix!r}"
            )
        marked.add(name)
    missing = wanted - marked
    if missing:
        raise RuntimeError(f"reference dimensions not applied: {sorted(missing)}")
    adapter.currentModel.EditRebuild3()


def offset_dimension_text(
    adapter: Any,
    annotations: Iterable[Any],
    positions: dict[str, tuple[float, float]],
) -> None:
    """Move named linear-dimension text off its dimension line with a leader."""
    remaining = dict(positions)
    for annotation in annotations:
        annotation = _sw_type_info.early_bound_or_flag(
            annotation, "IAnnotation", "GetSpecificAnnotation", "SetPosition2"
        )
        name = dimension_name(adapter, annotation)
        position = remaining.pop(name, None)
        if position is None:
            continue
        display = adapter._attempt(lambda a=annotation: a.GetSpecificAnnotation())
        if display is None:
            raise RuntimeError(f"dimension {name!r} has no display annotation")
        display = _sw_type_info.early_bound_or_flag(
            display, "IDisplayDimension", "OffsetText"
        )
        display.OffsetText = True
        if not annotation.SetPosition2(position[0], position[1], 0.0):
            raise RuntimeError(f"failed to offset dimension text {name!r}")
    if remaining:
        raise RuntimeError(f"dimension text not offset: {sorted(remaining)}")
    adapter.currentModel.EditRebuild3()


def add_edge_dimension(
    adapter: Any,
    view: Any,
    *,
    p0: tuple[float, float],
    p1: tuple[float, float],
    text_xy: tuple[float, float],
    label: str,
    orientation: str = "smart",
    entity_type: Literal["EDGE", "SILHOUETTE"] = "EDGE",
    entity_types: tuple[str, str] | None = None,
) -> Any:
    """Dimension across two view entities picked at explicit sheet points.

    The adapter's ``add_overall_dimension`` derives its picks from
    ``IView.GetOutline``, which pads the geometry with a whitespace margin, so
    its coordinate picks can miss.  Recipes know their layout exactly — the
    explicit sheet-meter points make the pick deterministic. Revolved outlines
    are drawing silhouettes rather than model edges, so callers must request
    ``SILHOUETTE`` for those flanks. Fails loud on either pick or dimension
    creation.

    ``orientation`` pins the measured direction: ``"smart"`` (default) lets
    SolidWorks infer from the picks and text position, while ``"horizontal"`` /
    ``"vertical"`` force the X/Y component — required when a hole is located by
    coordinate components off a datum rather than a slant centre distance (a
    slant reads ambiguous for holes not collinear with their datum).
    """
    draw = adapter.currentModel
    ddoc = _early_bound(
        draw, "IDrawingDoc"
    )  # IDrawingDoc view for drawing-only methods (same dispatch)
    name = view_name(adapter, view)
    if not ddoc.ActivateView(name):
        raise RuntimeError(f"failed to activate drawing view {name!r}")
    draw.ClearSelection2(True)
    for index, (x, y) in enumerate((p0, p1)):
        selected_type = entity_types[index] if entity_types else entity_type
        selected = draw.Extension.SelectByID2(
            "", selected_type, x, y, 0.0, index > 0, 0, null_callout(), 0
        )
        if not selected:
            raise RuntimeError(
                f"failed to select {label} {selected_type.lower()} {index} "
                f"at sheet ({x:g}, {y:g})"
            )
    if orientation == "horizontal":
        dimension = draw.AddHorizontalDimension2(text_xy[0], text_xy[1], 0.0)
    elif orientation == "vertical":
        dimension = draw.AddVerticalDimension2(text_xy[0], text_xy[1], 0.0)
    elif orientation == "smart":
        dimension = draw.AddDimension2(text_xy[0], text_xy[1], 0.0)
    else:
        raise ValueError(f"unknown dimension orientation {orientation!r}")
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    if dimension is None:
        raise RuntimeError(f"failed to add the {label} {orientation} dimension")
    return dimension


@_telemetry.traced("drawing.find_edge_near", label_param="label")
def find_edge_near(
    adapter: Any,
    view: Any,
    xy: tuple[float, float],
    *,
    axis: Literal["x", "y"],
    label: str,
    span_m: float = 0.0015,
    step_m: float = 0.00025,
    entity_type: str = "EDGE",
) -> tuple[float, float]:
    """Refine an approximate sheet point to a selectable drawing edge."""
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    if not ddoc.ActivateView(view_name(adapter, view)):
        raise RuntimeError(f"failed to activate {label} drawing view")
    steps = int(round(span_m / step_m))
    offsets = sorted((index * step_m for index in range(-steps, steps + 1)), key=abs)
    for offset in offsets:
        x = xy[0] + (offset if axis == "x" else 0.0)
        y = xy[1] + (offset if axis == "y" else 0.0)
        draw.ClearSelection2(True)
        if not draw.Extension.SelectByID2(
            "", entity_type, x, y, 0.0, False, 0, null_callout(), 0
        ):
            continue
        draw.ClearSelection2(True)
        if offset:
            _telemetry.debug(f"{label}: edge found {offset * 1000:+.2f} mm off nominal")
        return x, y
    raise RuntimeError(f"{label}: no edge within {span_m * 1000:.1f} mm")


@_telemetry.traced("drawing.visible_entity_scan", label_param="label")
def visible_view_entities(view: Any, entity_kind: int, *, label: str) -> list[Any]:
    """All visible entities of ``entity_kind`` across the view's components.

    The GetVisibleComponents/GetVisibleEntities2 walk is the COM-expensive
    core of every per-sheet edge/face scanner — one traced chokepoint here so
    each scanner shows up as a named child span instead of an unspanned gap
    (observability invariant). ``entity_kind`` is swViewEntityType_e (1=edge,
    2=vertex, 3=face, 4=silhouette).

    **Every scanner must come through here, and three did not.**
    ``visible_circle_edge``, ``visible_tooth_tip_silhouette`` and spring-hook's
    ``_shank_silhouette`` each re-implemented this walk untraced, which is how
    43.8 min of 193.7 min of drawing build time sat inside ``drawing.build``
    covered by no child span. One spring_hook run took 724 s with every NAMED
    span fast (surface_finish 1.3 s, finalize 8.8 s) — 693 s with nothing to
    attribute it to, on a drawing that has also run 65 s.

    The cost is wildly kind-dependent, so the ``entity_kind`` attribute is not
    decoration: kind 1 returned 481 edges in 7.0 s, while kind 4 spends ~21 s
    deriving outline geometry and returns SIX. Do not reason about "a sweep" as
    one number.

    Nothing is memoised, deliberately. An audit of every call site found no
    drawing that sweeps the same view twice — each gear print picks a circle off
    ``front`` and at most a silhouette off ``right`` — so a per-view cache would
    have a 0% hit rate. A cross-call cache would also have to invalidate on any
    visibility change (``set_hidden_lines_removed``, the drive-train isolation
    walk), and a stale entity list picks the wrong edge SILENTLY.
    """
    drawing_view = _early_bound(view, "IView")
    entities: list[Any] = []
    components = drawing_view.GetVisibleComponents() or []
    for component in components:
        entities.extend(drawing_view.GetVisibleEntities2(component, entity_kind) or [])
    # The scan's SIZE, on the span itself. Duration alone cannot separate "this
    # view is huge" from "this seat is slow", and the callers that classify each
    # returned entity scale directly with this count.
    span = _telemetry.trace.get_current_span()
    span.set_attribute("components", len(components))
    span.set_attribute("entities", len(entities))
    span.set_attribute("entity_kind", entity_kind)
    return entities


_ARC_END_CENTER = 1  # swArcEndCondition_e.swArcEndConditionCenter
_ARC_END_MAX = 3  # swArcEndCondition_e.swArcEndConditionMax (furthest point)


def _set_arc_endpoints(
    adapter: Any, dimension: Any, *, condition: int, label: str
) -> Any:
    display = _sw_type_info.early_bound_or_flag(
        dimension, "IDisplayDimension", "GetDimension"
    )
    model_dimension = _early_bound(display.GetDimension(), "IDimension")
    draw = adapter.currentModel
    arc_end_set = False
    for index in (1, 2):
        if int(model_dimension.GetArcEndCondition(index)) == 0:
            continue
        result = int(model_dimension.SetArcEndCondition(index, condition))
        if result != 0:
            raise RuntimeError(
                f"failed to set {label} endpoint {index} to arc condition "
                f"{condition} (SolidWorks result {result})"
            )
        draw.GraphicsRedraw2()
        if int(model_dimension.GetArcEndCondition(index)) != condition:
            raise RuntimeError(f"{label} did not retain arc condition {condition}")
        arc_end_set = True
    if not arc_end_set:
        raise RuntimeError(f"{label} has no circular endpoint")
    return dimension


@_telemetry.traced("drawing.arc_center_endpoints", label_param="label")
def set_arc_endpoints_to_center(adapter: Any, dimension: Any, *, label: str) -> Any:
    """Re-anchor a dimension's circular endpoint(s) to the arc CENTER.

    A line-to-circle dimension keeps SolidWorks' default tangent/min-max arc
    condition, so the value locates the rim instead of the axis — off by the
    hole radius. Verify each flipped endpoint sticks; fail loud when the
    dimension has no circular endpoint at all.
    """
    return _set_arc_endpoints(
        adapter, dimension, condition=_ARC_END_CENTER, label=label
    )


@_telemetry.traced("drawing.arc_max_endpoints", label_param="label")
def set_arc_endpoints_to_max(adapter: Any, dimension: Any, *, label: str) -> Any:
    """Re-anchor a dimension's circular endpoint(s) to the arc's FURTHEST point.

    The overall length of a part with a rounded end runs to the arc's extreme,
    not its centre (a centre-anchored "overall" reads short by the radius and
    gets the stock sawn short -- Harvey #25).  SolidWorks resolves a
    line-to-arc pick to the centre by default, so the far-tangent condition is
    set explicitly and verified.
    """
    return _set_arc_endpoints(adapter, dimension, condition=_ARC_END_MAX, label=label)


def set_basic_dimension(adapter: Any, dimension: Any, *, label: str) -> Any:
    """Box a drawing-native locating dimension as BASIC and verify the result."""
    display = _sw_type_info.early_bound_or_flag(
        dimension, "IDisplayDimension", "GetDimension", "SetText", "GetText"
    )
    adapter._attempt(lambda: display.SetText(_DIMENSION_TEXT_CALLOUT_BELOW, ""))
    below_text = adapter._attempt(
        lambda: display.GetText(_DIMENSION_TEXT_CALLOUT_BELOW), default=""
    )
    if str(below_text or ""):
        raise RuntimeError(
            f"{label} BASIC dimension retained below-text {below_text!r}"
        )
    model_dimension = _sw_type_info.early_bound_or_flag(
        display.GetDimension(), "IDimension", "SetToleranceType", "GetToleranceType"
    )
    if not model_dimension.SetToleranceType(TOL_BASIC):
        raise RuntimeError(f"failed to make {label} dimension BASIC")
    if int(model_dimension.GetToleranceType()) != TOL_BASIC:
        raise RuntimeError(f"{label} dimension did not retain BASIC tolerance")
    adapter.currentModel.EditRebuild3()
    return dimension


def set_basic_dimensions(
    adapter: Any, annotations: Iterable[Any], names: Iterable[str]
) -> None:
    """Box named imported model dimensions as BASIC location dimensions."""
    remaining = set(names)
    for annotation in annotations:
        annotation = _sw_type_info.early_bound_or_flag(
            annotation, "IAnnotation", "GetSpecificAnnotation"
        )
        name = dimension_name(adapter, annotation)
        if name not in remaining:
            continue
        display = adapter._attempt(lambda a=annotation: a.GetSpecificAnnotation())
        if display is None:
            raise RuntimeError(f"dimension {name!r} has no display annotation")
        set_basic_dimension(adapter, display, label=name)
        remaining.remove(name)
    if remaining:
        raise RuntimeError(f"dimensions not made BASIC: {sorted(remaining)}")


def hole_table_template(adapter: Any) -> Path:
    executable = adapter._attempt(
        lambda: adapter.swApp.GetExecutablePath(), default=None
    )
    if not executable:
        raise RuntimeError("SolidWorks executable path is unavailable")
    install_root = Path(str(executable)).parent
    relative = Path("lang") / "english" / "standard hole table--letters.sldholtbt"
    candidates = (install_root / relative, install_root / "SOLIDWORKS" / relative)
    for template in candidates:
        if template.is_file():
            return template
    raise FileNotFoundError(
        "native hole-table template is missing; checked "
        + ", ".join(str(path) for path in candidates)
    )


def insert_hole_table(
    adapter: Any,
    view: Any,
    *,
    datum_xy: tuple[float, float],
    hole_points: Sequence[tuple[float, float]],
    datum_entity: Any | None = None,
    datum_axes: tuple[Any, Any] | None = None,
    hole_entities: Sequence[Any] | None = None,
    expected_locations_mm: Sequence[tuple[float, float]] | None = None,
    anchor_xy: tuple[float, float],
    basic_locations: bool = True,
    label: str,
) -> Any:
    """Insert the model-associated TAG/X LOC/Y LOC/SIZE hole table on ``view``.

    ``datum_xy`` picks the origin VERTEX and each ``hole_points`` entry picks a
    hole EDGE, all in sheet meters.  Callers that can identify drawing-context
    entities topologically may additionally supply ``datum_entity`` and
    ``hole_entities``; those are selected directly with the same hole-table
    marks and the coordinates remain the count/diagnostic contract.  A part
    whose plan corners are broken (filleted/chamfered) has NO corner vertex to
    anchor: ``datum_axes=(x_axis_edge, y_axis_edge)`` instead selects the two
    datum edges (marks 4/8), and SolidWorks anchors the table origin at their
    VIRTUAL intersection -- the theoretical sharp corner.  The table lands
    with its top-left corner at ``anchor_xy`` and is validated before
    returning.
    """
    draw = adapter.currentModel
    ddoc = _early_bound(
        draw, "IDrawingDoc"
    )  # IDrawingDoc view for drawing-only methods (same dispatch)
    name = view_name(adapter, view)
    if not ddoc.ActivateView(name):
        raise RuntimeError(f"failed to activate hole-table view {name!r}")
    draw.ClearSelection2(True)
    if hole_entities is not None and len(hole_entities) != len(hole_points):
        raise ValueError(
            f"{label} supplied {len(hole_entities)} hole entities for "
            f"{len(hole_points)} hole points"
        )

    def _select_entity(entity: Any, *, append: bool, mark: int) -> bool:
        selection_manager = _early_bound(draw.SelectionManager, "ISelectionMgr")
        selection_data = _early_bound(
            selection_manager.CreateSelectData(), "ISelectData"
        )
        selection_data.Mark = mark
        selectable = _early_bound(entity, "IEntity")
        return bool(selectable.Select4(append, selection_data))

    if datum_axes is not None and datum_entity is not None:
        raise ValueError(f"{label} supplied both a datum vertex and datum axes")
    if datum_axes is not None:
        x_axis, y_axis = datum_axes
        datum = _select_entity(x_axis, append=False, mark=4) and _select_entity(
            y_axis, append=True, mark=8
        )
    elif datum_entity is not None:
        datum = _select_entity(datum_entity, append=False, mark=1)
    else:
        datum = draw.Extension.SelectByID2(
            "", "VERTEX", datum_xy[0], datum_xy[1], 0.0, False, 1, null_callout(), 0
        )
    if not datum:
        raise RuntimeError(f"failed to select {label} hole-table datum origin")
    selections = (
        zip(hole_points, hole_entities, strict=True)
        if hole_entities is not None
        else ((point, None) for point in hole_points)
    )
    for (x, y), entity in selections:
        if entity is not None:
            selected = _select_entity(entity, append=True, mark=2)
        else:
            selected = draw.Extension.SelectByID2(
                "", "EDGE", x, y, 0.0, True, 2, null_callout(), 0
            )
        if not selected:
            raise RuntimeError(
                f"failed to select {label} hole-table edge at sheet ({x:g}, {y:g})"
            )
    table = view.InsertHoleTable3(
        False,
        anchor_xy[0],
        anchor_xy[1],
        1,  # swBOMConfigurationAnchor_TopLeft
        "A",
        str(hole_table_template(adapter)),
        1,  # swHoleTableTagOrder_XY
        1,  # swHoleTable_AlphaNumericTags
        None,
    )
    draw.ClearSelection2(True)
    if table is None:
        raise RuntimeError(f"SolidWorks failed to create the {label} hole table")
    table = _sw_type_info.early_bound_or_flag(table, "IHoleTableAnnotation")
    feature = table.HoleTable
    if feature is None:
        raise RuntimeError("native hole table annotation has no feature")
    feature = _sw_type_info.early_bound_or_flag(feature, "IHoleTable")
    feature.CombineSameSize = False
    feature.CombineTags = False
    adapter.currentModel.EditRebuild3()
    table = _sw_type_info.early_bound(table, "ITableAnnotation")
    # Indexed COM properties such as Text2 are omitted by the late-bound
    # dispatch returned from IHoleTableAnnotation.  Wrap the same dispatch in
    # its generated early-bound interface before using the setter.
    if not _sw_type_info.is_early_bound(table, "ITableAnnotation"):
        raise RuntimeError("ITableAnnotation early-bound wrapper is unavailable")
    if basic_locations:
        for column, heading in ((1, "X LOC (BASIC)"), (2, "Y LOC (BASIC)")):
            if not table.IsCellTextEditable(0, column):
                raise RuntimeError(
                    f"native hole-table header column {column} is not editable"
                )
            table.SetText2(0, column, False, heading)
            applied_heading = str(table.DisplayedText2(0, column, False) or "")
            if applied_heading.upper() != heading:
                raise RuntimeError(
                    f"native hole-table header did not persist: {applied_heading!r}"
                )
        adapter.currentModel.EditRebuild3()
    rows = int(adapter._get_attr_or_call(table, "RowCount") or 0)
    columns = int(adapter._get_attr_or_call(table, "ColumnCount") or 0)
    contents = tuple(
        tuple(
            str(
                adapter._attempt(
                    lambda row=row, column=column: table.DisplayedText(row, column)
                )
                or ""
            )
            for column in range(columns)
        )
        for row in range(rows)
    )
    expected_rows = 1 + len(hole_points)
    if (rows, columns) != (expected_rows, 4):
        raise RuntimeError(
            f"native hole table is {rows}x{columns}, "
            f"expected {expected_rows}x4: {contents!r}"
        )
    header = contents[0]
    expected = (
        "TAG",
        "X LOC (BASIC)" if basic_locations else "X LOC",
        "Y LOC (BASIC)" if basic_locations else "Y LOC",
        "SIZE",
    )
    if tuple(value.upper() for value in header) != expected:
        raise RuntimeError(f"native hole-table header is unexpected: {header!r}")
    if expected_locations_mm is not None:
        _check_hole_table_locations(contents, expected_locations_mm, label=label)
    _telemetry.success(f"native hole table inserted: {rows - 1} holes, header={header}")
    return table


def _check_hole_table_locations(
    contents: Sequence[Sequence[str]],
    expected_mm: Sequence[tuple[float, float]],
    *,
    label: str,
    tol_mm: float = 0.02,
) -> None:
    """Match every printed X/Y LOC cell against an expected station, one-to-one.

    SolidWorks computes the LOC cells from the model against the selected
    datum origin, and ``insert_hole_table`` otherwise validates only the
    header and row count -- so a mis-anchored origin (e.g. a fillet-arc
    endpoint picked instead of the theoretical corner) would shift every
    coordinate SILENTLY. Expected stations are matched as a SET (table rows
    are tag-ordered, not selection-ordered) within ``tol_mm`` (cells print
    at 2 decimals, so the honest floor is 0.005 rounding).
    """
    if len(expected_mm) != len(contents) - 1:
        raise RuntimeError(
            f"{label} hole table: {len(expected_mm)} expected locations for "
            f"{len(contents) - 1} rows"
        )
    printed: list[tuple[float, float, str]] = []
    for row in contents[1:]:
        try:
            printed.append((float(row[1]), float(row[2]), row[0]))
        except ValueError as error:
            raise RuntimeError(
                f"{label} hole table: unparseable LOC cells in row {row!r}"
            ) from error
    unmatched = list(range(len(printed)))
    for ex, ey in expected_mm:
        hit = next(
            (
                index
                for index in unmatched
                if abs(printed[index][0] - ex) <= tol_mm
                and abs(printed[index][1] - ey) <= tol_mm
            ),
            None,
        )
        if hit is None:
            table_dump = ", ".join(f"{tag}({x:g}, {y:g})" for x, y, tag in printed)
            raise RuntimeError(
                f"{label} hole table: no printed row matches expected "
                f"({ex:g}, {ey:g}) mm within {tol_mm}; table: {table_dump}"
            )
        unmatched.remove(hit)
    _telemetry.success(
        f"{label} hole table locations verified: {len(expected_mm)} stations "
        f"within {tol_mm} mm"
    )


def bom_table_template(adapter: Any) -> Path:
    """Path to the install's standard BOM table template (``bom-standard.sldbomtbt``)."""
    executable = adapter._attempt(
        lambda: adapter.swApp.GetExecutablePath(), default=None
    )
    if not executable:
        raise RuntimeError("SolidWorks executable path is unavailable")
    install_root = Path(str(executable)).parent
    relative = Path("lang") / "english" / "bom-standard.sldbomtbt"
    candidates = (install_root / relative, install_root / "SOLIDWORKS" / relative)
    for template in candidates:
        if template.is_file():
            return template
    raise FileNotFoundError(
        "native BOM-table template is missing; checked "
        + ", ".join(str(path) for path in candidates)
    )


def _activate_and_select_view(adapter: Any, view: Any, *, label: str) -> str:
    """Activate ``view`` and select it as a DRAWINGVIEW; return its name."""
    draw = adapter.currentModel
    ddoc = _early_bound(
        draw, "IDrawingDoc"
    )  # IDrawingDoc view for drawing-only methods (same dispatch)
    name = view_name(adapter, view)
    if not ddoc.ActivateView(name):
        raise RuntimeError(f"failed to activate {label} drawing view {name!r}")
    draw.ClearSelection2(True)
    if not draw.Extension.SelectByID2(
        name, "DRAWINGVIEW", 0.0, 0.0, 0.0, False, 0, null_callout(), 0
    ):
        raise RuntimeError(f"failed to select {label} drawing view {name!r}")
    return name


def _bom_identity_map(
    expected_components: Sequence[str], identity_aliases: dict[str, str] | None
) -> dict[str, str]:
    """Map every accepted BOM identity to one normalized component stem."""
    expected = {component.strip().lower() for component in expected_components}
    if len(expected) != len(expected_components):
        raise ValueError("BOM expected-component identities are not unique")
    identities = {component: component for component in expected}
    for alias, component in (identity_aliases or {}).items():
        normalized_alias = alias.strip().lower()
        normalized_component = component.strip().lower()
        if normalized_component not in expected:
            raise ValueError(
                f"BOM identity alias {alias!r} targets unknown component {component!r}"
            )
        existing = identities.get(normalized_alias)
        if existing is not None and existing != normalized_component:
            raise ValueError(
                f"BOM identity alias {alias!r} maps to both "
                f"{existing!r} and {normalized_component!r}"
            )
        identities[normalized_alias] = normalized_component
    return identities


@_telemetry.traced("drawing.bom_table", label_param="label")
def insert_bom_table(
    adapter: Any,
    view: Any,
    *,
    anchor_xy: tuple[float, float],
    expected_components: Sequence[str],
    descriptions: dict[str, str] | None = None,
    identity_aliases: dict[str, str] | None = None,
    configuration_grouping: Literal["separate", "same-part"] = "separate",
    label: str,
) -> Any:
    """Insert a top-level parts BOM for an ASSEMBLY drawing view and validate it.

    ``IView.InsertBomTable6`` (the current variant; ``InsertBomTable4`` is
    obsolete) with the install's standard ITEM NO./PART NUMBER/DESCRIPTION/QTY
    template, anchored top-left at ``anchor_xy`` (sheet meters). Validated hard:
    one data row per ``expected_components`` entry and every expected part
    number present, so a BOM that silently dropped a component can never ship.
    ``identity_aliases`` maps alternate displayed identities (such as released
    part numbers) back to the expected component stems.
    ``descriptions`` maps a part number to its DESCRIPTION cell text (written
    per cell and read-verified) — the components carry no Description custom
    property, and a blank column reads as an unreleased sheet. Returns the
    table rebound as ``ITableAnnotation``.
    """
    _activate_and_select_view(adapter, view, label=label)
    draw = adapter.currentModel
    configuration = str(
        adapter._get_attr_or_call(view, "ReferencedConfiguration") or "Default"
    )
    bom = view.InsertBomTable6(
        False,  # UseAnchorPoint=False -> place at the explicit X/Y below
        anchor_xy[0],
        anchor_xy[1],
        1,  # swBomConfigurationAnchorType_e.swBOMConfigurationAnchor_TopLeft
        2,  # swBomType_e.swBomType_TopLevelOnly
        "",  # Configuration: top-level BOMs bind configs via SetConfigurations
        str(bom_table_template(adapter)),
        False,  # Hidden
        0,  # swNumberingType_e.swNumberingType_None (non-indented BOM)
        False,  # DetailedCutList
        False,  # DissolvePartLevelRows
        configuration_grouping == "same-part",
    )
    draw.ClearSelection2(True)
    if bom is None:
        raise RuntimeError(f"SolidWorks failed to create the {label} BOM table")
    # A COM-inserted top-level BOM starts with NO configuration bound (a
    # header-only table without even its per-configuration QTY column) --
    # IBomFeature::SetConfigurations is the documented binding path for
    # top-level tables, so bind the view's own configuration.
    bom = _sw_type_info.early_bound_or_flag(bom, "IBomTableAnnotation", "BomFeature")
    feature = adapter._get_attr_or_call(bom, "BomFeature")
    if feature is None:
        raise RuntimeError(f"{label} BOM table has no BOM feature")
    feature = _sw_type_info.early_bound_or_flag(
        feature,
        "IBomFeature",
        "SetConfigurations",
        "PartConfigurationGrouping",
        "DisplayAsOneItem",
    )
    if not feature.SetConfigurations(
        True, bool_array([True]), bstr_array([configuration])
    ):
        raise RuntimeError(
            f"failed to bind {label} BOM table to configuration {configuration!r}"
        )
    grouping_value = 2 if configuration_grouping == "same-part" else 1
    setattr(feature, "PartConfigurationGrouping", grouping_value)
    setattr(feature, "DisplayAsOneItem", configuration_grouping == "same-part")
    actual_grouping = int(
        adapter._get_attr_or_call(feature, "PartConfigurationGrouping") or 0
    )
    actual_one_item = bool(adapter._get_attr_or_call(feature, "DisplayAsOneItem"))
    if actual_grouping != grouping_value or actual_one_item != (
        configuration_grouping == "same-part"
    ):
        raise RuntimeError(
            f"{label} BOM configuration grouping did not persist: "
            f"grouping={actual_grouping}, one_item={actual_one_item}"
        )
    draw.ForceRebuild3(False)
    adapter.currentModel.EditRebuild3()
    table = _sw_type_info.early_bound(bom, "ITableAnnotation")
    if not _sw_type_info.is_early_bound(table, "ITableAnnotation"):
        raise RuntimeError("ITableAnnotation early-bound wrapper is unavailable")
    rows = int(adapter._get_attr_or_call(table, "RowCount") or 0)
    columns = int(adapter._get_attr_or_call(table, "ColumnCount") or 0)
    contents = tuple(
        tuple(
            str(
                adapter._attempt(
                    lambda row=row, column=column: table.DisplayedText(row, column)
                )
                or ""
            )
            for column in range(columns)
        )
        for row in range(rows)
    )
    expected_rows = 1 + len(expected_components)
    if rows != expected_rows or columns < 3:
        raise RuntimeError(
            f"{label} BOM table is {rows}x{columns}, expected {expected_rows} rows: "
            f"{contents!r}"
        )
    identities = _bom_identity_map(expected_components, identity_aliases)
    header = [cell.strip().upper() for cell in contents[0]]
    part_column = header.index("PART NUMBER") if "PART NUMBER" in header else None
    if part_column is None:
        observed = {cell.strip().lower() for row in contents[1:] for cell in row}
    else:
        observed = {
            identities.get(
                row[part_column].strip().lower(), row[part_column].strip().lower()
            )
            for row in contents[1:]
        }
    missing = sorted(
        component
        for component in expected_components
        if component.strip().lower() not in observed
    )
    if missing:
        raise RuntimeError(
            f"{label} BOM table is missing components {missing}: {contents!r}"
        )
    if descriptions:
        if "DESCRIPTION" not in header or "PART NUMBER" not in header:
            raise RuntimeError(
                f"{label} BOM header carries no DESCRIPTION/PART NUMBER: {header!r}"
            )
        description_column = header.index("DESCRIPTION")
        part_column = header.index("PART NUMBER")
        remaining = {key.strip().lower(): text for key, text in descriptions.items()}
        for row in range(1, rows):
            part = (
                str(
                    adapter._attempt(lambda r=row: table.DisplayedText(r, part_column))
                    or ""
                )
                .strip()
                .lower()
            )
            text = remaining.pop(identities.get(part, part), None)
            if text is None:
                continue
            if not table.IsCellTextEditable(row, description_column):
                raise RuntimeError(
                    f"{label} BOM description cell {row} is not editable"
                )
            _set_bom_cell_text(
                table,
                row,
                description_column,
                text,
                label=f"{label} BOM description",
            )
        if remaining:
            raise RuntimeError(
                f"{label} BOM descriptions not applied (no matching row): "
                f"{sorted(remaining)}"
            )
        adapter.currentModel.EditRebuild3()
    _telemetry.success(
        f"{label} BOM table inserted: {rows - 1} items, {columns} columns"
    )
    return table


def _set_bom_cell_text(
    table: Any,
    row: int,
    column: int,
    text: str,
    *,
    label: str,
) -> None:
    """Write and verify one visible BOM cell."""
    table.SetText2(row, column, False, text)
    applied = str(table.DisplayedText2(row, column, False) or "")
    if applied != text:
        raise RuntimeError(f"{label} did not persist: {applied!r} != {text!r}")


def _min_angular_gap(
    ring_radius: float, balloon_radius: float, *, clearance: float
) -> float:
    """Smallest angle between two balloon centres that keeps their circles apart.

    Separation is set against the SQUARE the audit boxes a balloon with, not the
    circle the sheet draws: :func:`_note_element` boxes the circle's circumscribed
    square, and two such squares whose centres lie on a ring DIAGONAL still
    intersect after their circles have parted -- ``dx = dy = d/sqrt(2)``, so they
    only clear once ``d >= 2*sqrt(2)*balloon_radius``. Separating to ``2*r`` (the
    circles just touching) measured 9 overlaps on pen-assembly: correct about the
    ink, wrong about the checker. Placement must satisfy the model that grades it.

    Measured against ARC length rather than the true chord, which is conservative
    (arc >= chord) and avoids a domain error as the required separation
    approaches the ring's diameter.

    ``ring_radius`` must be the ring ellipse's SMALLER semi-axis: a point's local
    speed along the ellipse is ``sqrt(Rx^2 sin^2 t + Ry^2 cos^2 t)``, whose
    minimum is ``min(Rx, Ry)`` -- so using it can only over-separate, never leave
    two circles touching.
    """
    if ring_radius <= 0.0:
        raise ValueError("balloon spread: ring radius must be positive")
    return (2.0 * math.sqrt(2.0) * balloon_radius + clearance) / ring_radius


def _wrap_angle(angle: float) -> float:
    """Fold ``angle`` back into ``(-pi, pi]`` -- the range ``atan2`` returns."""
    return (angle + math.pi) % (2.0 * math.pi) - math.pi


def _push_apart_on_ring(
    angles: list[float], *, min_gap: float, iterations: int = 400
) -> list[float]:
    """Separate ``angles`` to at least ``min_gap`` apart, preserving their order.

    ``angles`` must be sorted. Order preservation is the whole point, not a
    nicety: balloons placed about a shared centre in their attachments' angular
    ORDER cannot have crossing leaders, so a separation pass that never reorders
    cannot reintroduce one. That argument only holds if the solver actually
    preserves order, so this does it BY CONSTRUCTION rather than by assertion.

    Substituting ``z_i = x_i - i*min_gap`` turns the spacing constraint
    ``x_{i+1} - x_i >= min_gap`` into plain monotonicity ``z_{i+1} >= z_i``, so
    the minimum-movement placement is the isotonic regression of ``z`` -- solved
    exactly by pool-adjacent-violators, in one pass, with no convergence
    question.

    (History: this WAS an iterative pairwise relaxation, and it silently BROKE
    the order it was written to preserve. It measured each gap as
    ``(x[j] - x[i]) % 2pi``, so an inverted pair read as a ~6 rad gap -- huge,
    apparently fine -- and was never repaired; in-place sequential updates then
    kept inverting more. Probed on pen-assembly, it returned
    ``[..., -1.553, -1.817, ...]`` from sorted input while its own docstring
    claimed "it cannot swap them". Do not reintroduce a relaxation here.)

    Falls back to EVEN spacing when the balloons cannot all fit at ``min_gap``
    (``n * min_gap > 2*pi``); packing them tighter than their own circles would
    trade this function's crossings for overlaps, which is the trade the pure-
    radial experiment already lost.

    **Seam-safe.** Angles are a circular quantity, so the isotonic solver must
    run on a LINEAR run that never crosses the +-pi seam. The occupied
    attachments always leave one largest angular gap; unwrapping the run to
    START just after that gap places the seam inside empty space, where a linear
    chain is exact. Without this, a cluster straddling +-pi (attachments on the
    LEFT of the view) reads as two far-apart sub-runs, the solver under-separates
    them, and the wrap-around re-centre below -- an ORDINARY average of the two
    endpoints -- lands on the OPPOSITE side of the view, hauling every leader
    across the model (Codex #3605056589: ``[-3.10, 3.10]`` -> ``[-0.4, 0.0]``).
    """
    count = len(angles)
    if count < 2:
        return list(angles)
    two_pi = 2.0 * math.pi
    span_needed = count * min_gap
    if span_needed > two_pi:
        _telemetry.warn(
            f"balloon spread: {count} balloons need {span_needed:.2f} rad of "
            f"ring but only {two_pi:.2f} is available -- falling back to "
            "even spacing (leaders may run long)"
        )
        start = angles[0]
        return [start + two_pi * i / count for i in range(count)]

    # Unwrap around the LARGEST gap: sort by angle, find the widest gap between
    # cyclically-adjacent attachments, and read the run off as a single strictly
    # increasing sequence starting just after it. The seam then falls in that
    # empty gap, so nothing below straddles +-pi.
    order = sorted(range(count), key=lambda i: angles[i])
    ordered = [angles[i] for i in order]
    gaps = [(ordered[(j + 1) % count] - ordered[j]) % two_pi for j in range(count)]
    cut = max(range(count), key=lambda j: gaps[j])
    run_index = [order[(cut + 1 + step) % count] for step in range(count)]
    base = angles[run_index[0]]
    run = []
    for i in run_index:
        value = angles[i]
        while value < base - 1e-12:
            value += two_pi
        run.append(value)

    # Blocks of (weighted mean, weight) merged while the previous block outranks
    # the next -- the pool-adjacent-violators algorithm.
    blocks: list[list[float]] = []
    for index, angle in enumerate(run):
        blocks.append([angle - index * min_gap, 1.0])
        while len(blocks) >= 2 and blocks[-2][0] > blocks[-1][0] - 1e-15:
            value_b, weight_b = blocks.pop()
            value_a, weight_a = blocks.pop()
            weight = weight_a + weight_b
            blocks.append([(value_a * weight_a + value_b * weight_b) / weight, weight])
    fitted: list[float] = []
    for value, weight in blocks:
        fitted.extend([value] * int(weight))
    spread = [value + i * min_gap for i, value in enumerate(fitted)]

    # The wrap-around pair (last -> first) is the one constraint the linear chain
    # cannot see. Unwrapping put the widest gap at the seam, so there is room by
    # construction unless the run fills nearly the whole ring; then centre it in
    # the slack. The endpoints share one linear frame now, so their average is
    # the true midpoint -- no seam to jump.
    if (spread[0] + two_pi) - spread[-1] < min_gap:
        centre = (spread[0] + spread[-1]) / 2.0
        start = centre - span_needed / 2.0
        spread = [start + i * min_gap for i in range(count)]

    result = [0.0] * count
    for step, i in enumerate(run_index):
        result[i] = _wrap_angle(spread[step])
    return result


def _balloon_item_key(adapter: Any, note: Any) -> tuple[int, str]:
    """A balloon's BOM item number, as a sort key that never ties on order.

    The last resort in :func:`_spread_balloons`' ring sort. Every field ahead of
    it is geometric and can therefore tie exactly -- two overlapping or coaxial
    components project to one attachment point -- at which point a stable sort
    silently falls back to ``AutoBalloon5``'s arrival order, which is the very
    nondeterminism the sort exists to remove.

    The item number is the only identity here that comes from the component's
    BOM ROW rather than from when its balloon happened to be created, so it is
    the one that actually terminates the chain. ``IAnnotation::GetName`` would
    NOT do: names like ``DetailItem347`` are handed out at creation time, in
    arrival order, so keying on one re-encodes the instability it is meant to
    break.

    Read through ``GetBomBalloonText(True)`` -- the balloon-specific API for the
    displayed UPPER item, the same one :func:`_balloon_item_number` uses -- and
    NOT through ``INote::GetText``. GetText returns the note's generic text,
    which for a BOM balloon is not guaranteed to be the item number and can come
    back empty; every key would then collapse to ``(sys.maxsize, "")``, the sort
    would tie on all four fields, and this tie-break would silently be a no-op
    that still LOOKS like a fix.

    Returns ``(number, text)`` so "2" sorts before "10" rather than after it,
    with the raw text carrying non-numeric balloons (``A``, ``12A``) and ties
    among them. An unreadable balloon sorts last under its own text rather than
    failing the drawing: this is a tie-break, and losing it degrades placement
    determinism, not correctness. (:func:`_balloon_item_number` raises on the
    same read because there the item IS the product; here it is a sort key.)
    """
    note = _sw_type_info.early_bound_or_flag(note, "INote", "GetBomBalloonText")
    text = adapter._attempt(lambda n=note: n.GetBomBalloonText(True), default="") or ""
    text = str(text).strip()
    leading = ""
    for char in text:
        if not char.isdigit():
            break
        leading += char
    return (int(leading) if leading else sys.maxsize, text)


def _spread_balloons(
    adapter: Any,
    view: Any,
    balloons: list[Any],
    *,
    margin: float = 0.014,
    clearance: float = _BALLOON_CLEARANCE_M,
) -> None:
    """Re-ring auto-balloons evenly around ``view`` (the layout audit fails loud).

    ``AutoBalloon5`` stacks balloons whose attachment points cluster, and on a
    pictorial view its square layout can even drop balloons INSIDE the outline
    box. Deterministic fix: place every balloon's box center on an ellipse
    ``margin`` outside the view outline, evenly spaced, and assign the ring slots
    in the angular order of the balloons' ATTACHMENT POINTS. Leaders stay
    attached; only the balloon anchor moves (``IAnnotation.SetPosition``).

    **Sort on the ATTACHMENT, not on where the balloon landed.** For straight
    leaders from points on a convex ring to points inside it, the non-crossing
    condition is that the ring order matches the ATTACHMENTS' angular order --
    ring slot k must serve the k-th attachment going round. Sorting on the
    balloon's own landed angle (the ``GetPosition`` this used to read) merely
    preserves AutoBalloon5's ordering, which was never non-crossing to begin
    with, so the ring was re-spacing the balloons while faithfully reproducing
    the crossings.

    This docstring used to CLAIM "each assigned the ring slot nearest its landed
    angle so leaders do not cross". That claim was never true and never tested;
    the shipped pen-assembly sheet crossed B4xB6 at (0.2285, 0.1161) under it.
    ``find_leader_leader_crossings`` is now the repro, so the claim is a gate
    rather than a comment.

    Attachment = the LAST point of ``GetLeaderPointsAtIndex(0)``; the first is
    the balloon end. Measured on pen-assembly's 8 balloons: the first points
    spread over 61 mm of x (the ring) while the last cluster within 13 mm (the
    tall, skinny pen sub they point at).
    """
    outline = adapter._attempt(lambda: view.GetOutline())
    if not outline:
        raise RuntimeError("balloon spread: view has no outline")
    vxmin, vymin, vxmax, vymax = (float(v) for v in list(outline)[:4])
    center_x, center_y = (vxmin + vxmax) / 2.0, (vymin + vymax) / 2.0
    radius_x = (vxmax - vxmin) / 2.0 + margin
    radius_y = (vymax - vymin) / 2.0 + margin
    items = []
    radii: list[float] = []
    for note in balloons:
        note = _sw_type_info.early_bound_or_flag(
            note, "INote", "GetAnnotation", "GetBalloonInfo", "GetBomBalloonText"
        )
        # The balloon circle's own rendered radius. GetBalloonInfo returns
        # (centre xyz, arc-point xyz, radius) -- unlike GetExtent it describes
        # the CIRCLE, not the note+leader box, so the leader cannot pollute it.
        info = adapter._attempt(lambda n=note: n.GetBalloonInfo())
        if not info or len(info) < 7:
            raise RuntimeError(
                "balloon spread: GetBalloonInfo did not return the balloon "
                "circle -- the separation below is derived from the MEASURED "
                "radius, so a balloon whose circle cannot be read cannot be "
                "placed without guessing"
            )
        radii.append(float(info[6]))
        annotation = adapter._attempt(lambda n=note: n.GetAnnotation())
        if annotation is None:
            raise RuntimeError("balloon spread: balloon without an annotation")
        annotation = _sw_type_info.early_bound_or_flag(
            annotation,
            "IAnnotation",
            "GetPosition",
            "SetPosition",
            "GetLeaderPointsAtIndex",
        )
        # Never GetExtent: a balloon note's extent box includes its LEADER, so it
        # spans to the pointed-at component and is useless for placing the
        # balloon circle itself.
        raw = adapter._attempt(lambda a=annotation: a.GetLeaderPointsAtIndex(0))
        if not raw or len(raw) < 6:
            raise RuntimeError(
                "balloon spread: balloon without a readable leader -- the ring "
                "order is derived from the ATTACHMENT point, so a balloon whose "
                "leader cannot be read cannot be placed without crossing"
            )
        # Flat x,y,z stream; the LAST triple is the attachment on the component.
        attach_x, attach_y = float(raw[-3]), float(raw[-2])
        theta = math.atan2(attach_y - center_y, attach_x - center_x)
        items.append(
            (theta, attach_x, attach_y, _balloon_item_key(adapter, note), annotation)
        )
    # Sort on (theta, attach x, attach y, BOM item), never on theta alone. Two
    # balloons attached at the same angle from the view centre -- coaxial parts
    # in a pictorial view do this routinely -- would otherwise keep whatever
    # relative order the balloons arrived in, which is AutoBalloon5's, which is
    # not stable. Ring order decides whether leaders cross, so an unstable
    # tie-break is an unstable drawing.
    #
    # The BOM item number is the LAST key because the three geometric ones can
    # ALL tie: overlapping or coaxial components can attach at exactly the same
    # projected point, and then the stable sort just re-emits AutoBalloon5's
    # arrival order -- the same nondeterminism, one level down. The item number
    # is the only field here tied to the component's BOM row rather than to when
    # the balloon happened to be created, so it is the one that ends the chain.
    order = sorted(range(len(items)), key=lambda i: items[i][:4])
    items = [items[i] for i in order]
    radii = [radii[i] for i in order]
    _telemetry.event(
        "drawing.balloon_ring",
        count=len(items),
        attachments=[f"{x:.6f},{y:.6f}" for _t, x, y, _i, _a in items],
        items=[str(item) for _t, _x, _y, item, _a in items],
    )

    # Place each balloon at its OWN attachment's angle, then separate only the
    # circles that actually collide. Two earlier placements both failed, each in
    # the way the other avoided, and this is the synthesis of what they proved:
    #
    #   EVEN SPACING (was here) preserved the attachments' ORDER but not their
    #   DIRECTIONS. The pen sub is tall and skinny, so its 8 attachments cluster
    #   in a narrow angular band while evenly-spaced slots span 360 deg. Measured
    #   on the shipped sheet: balloon DetailItem347 sat at y=0.1908 serving an
    #   attachment at y=0.1035 -- an 87 mm near-vertical leader hauled across the
    #   model, and it alone caused BOTH remaining crossings.
    #
    #   PURE RADIAL placement fixed that (crossings 2 -> 0: radial segments about
    #   a shared centre cannot intersect) but piled the clustered balloons on top
    #   of each other -- overlaps 0 -> 9, the very defect AutoBalloon5 has and
    #   this function exists to undo. It failed for ONE reason: nothing separated
    #   the colliding circles.
    #
    # So: keep the radial direction, enforce a minimum angular separation. The
    # separation is derived from the balloon's MEASURED radius (GetBalloonInfo,
    # above), not a guess -- 4.72 mm on this sheet. A monotone push-apart cannot
    # reorder the balloons, and order-preserving placement about a shared centre
    # is what rules crossings out, so this keeps radial's proof while paying
    # radial's price only where circles genuinely touch.
    #
    # (History: this WAS documented as blocked -- "needs the balloon's rendered
    # diameter, which nothing here reads yet". True of this file, never of the
    # API: INote::GetBalloonInfo returns the circle's centre and radius outright,
    # and had been in the generated binding all along. The claim was never tested
    # and the sheet carried the defect for it.)
    gap = _min_angular_gap(min(radius_x, radius_y), max(radii), clearance=clearance)
    angles = _push_apart_on_ring(
        [theta for theta, _x, _y, _i, _a in items], min_gap=gap
    )
    for angle, (_theta, _x, _y, _item, annotation) in zip(angles, items):
        target_x = center_x + radius_x * math.cos(angle)
        target_y = center_y + radius_y * math.sin(angle)
        if not annotation.SetPosition(target_x, target_y, 0.0):
            raise RuntimeError("failed to re-ring a BOM balloon")


@_telemetry.traced("drawing.auto_balloons", label_param="label")
def _create_auto_balloons(
    adapter: Any,
    view: Any,
    *,
    label: str,
    allow_empty: bool = False,
    layout: int = 1,
) -> list[Any]:
    """Create item-number balloons for one selected view without repositioning."""
    if layout not in range(1, 7):
        raise ValueError(f"{label}: invalid auto-balloon layout {layout}")
    _activate_and_select_view(adapter, view, label=label)
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    options = ddoc.CreateAutoBalloonOptions()
    if options is None:
        raise RuntimeError(f"failed to create auto-balloon options ({label})")
    options = _sw_type_info.early_bound_or_flag(options, "IAutoBalloonOptions")
    options.Layout = layout
    options.ReverseDirection = False
    options.IgnoreMultiple = True
    options.InsertMagneticLine = False
    options.LeaderAttachmentToFaces = True
    options.Style = 1
    options.Size = 2
    options.UpperTextContent = 1
    options.ItemNumberStart = 1
    options.ItemNumberIncrement = 1
    options.ItemOrder = 1
    notes = ddoc.AutoBalloon5(options)
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    if not notes or isinstance(notes, str):
        if allow_empty:
            return []
        raise RuntimeError(f"AutoBalloon5 produced no balloons ({label})")
    balloons = list(notes)
    identities: list[str] = []
    for note in balloons:
        item = _balloon_item_number(adapter, note, label=label)
        note = _sw_type_info.early_bound_or_flag(note, "INote", "GetName")
        identities.append(f"{note.GetName()}=item {item}")
    _telemetry.info(f"{label}: AutoBalloon5 identities {identities}")
    return balloons


def _balloon_item_number(adapter: Any, note: Any, *, label: str) -> str:
    """Read one BOM balloon's displayed upper item number."""
    note = _sw_type_info.early_bound_or_flag(note, "INote", "GetBomBalloonText")
    item = str(adapter._attempt(lambda: note.GetBomBalloonText(True)) or "").strip()
    if not item:
        raise RuntimeError(f"{label}: BOM balloon has no upper item number")
    return item


def add_auto_balloons(
    adapter: Any, view: Any, *, expected: int, label: str
) -> list[Any]:
    """Auto-insert circular item-number balloons around one assembly view.

    ``IDrawingDoc.CreateAutoBalloonOptions`` + ``AutoBalloon5`` on the selected
    ``view``: square layout, circular 2-character style, upper text = the BOM
    item number (so balloons and the BOM table cross-reference), one balloon
    per component (``IgnoreMultiple``). Fails loud unless at least ``expected``
    balloons landed. Returns the balloon notes.
    """
    draw = adapter.currentModel
    balloons = _create_auto_balloons(adapter, view, label=label)
    if len(balloons) < expected:
        raise RuntimeError(
            f"{label}: {len(balloons)} balloons landed, expected >= {expected}"
        )
    _spread_balloons(adapter, view, balloons)
    draw.EditRebuild3()
    _telemetry.success(f"{label}: {len(balloons)} BOM balloons inserted")
    return balloons


def _drawing_component_children(drawing_component: Any) -> tuple[Any, ...]:
    """Return children across callable and materialized pywin32 shapes."""
    member = drawing_component.GetChildren
    children = member() if callable(member) else member
    return tuple(children or ())


def _drawing_component_stems(
    adapter: Any, drawing_component: Any, stems: frozenset[str]
) -> set[str]:
    """Return requested file stems represented by one leaf drawing component."""
    component = adapter._attempt(
        lambda dc=drawing_component: dc.Component, default=None
    )
    path = ""
    if component is not None:
        path = adapter._attempt(lambda c=component: c.GetPathName(), default="") or ""
    name = str(drawing_component.Name or "")
    drawing_name = name.split("@", 1)[0].replace("\\", "/")
    identities = {
        Path(str(path)).stem.casefold(),
        drawing_name.rsplit("/", 1)[-1].casefold(),
    }
    return {
        stem
        for stem in stems
        if any(
            identity == stem
            or (
                identity.startswith(f"{stem}-")
                and identity.removeprefix(f"{stem}-").isdigit()
            )
            for identity in identities
        )
    }


@_telemetry.traced("drawing.isolate_components", label_param="label")
def isolate_drawing_view_components(
    adapter: Any,
    view: Any,
    *,
    visible_stems: frozenset[str],
    label: str,
) -> None:
    """Show only requested top-level component families in one drawing view."""
    if not visible_stems:
        raise ValueError(f"{label}: visible component set must not be empty")
    root = adapter._attempt(lambda: view.RootDrawingComponent2(False), default=None)
    if root is None:
        raise RuntimeError(f"{label}: drawing view has no root component")

    pending = list(_drawing_component_children(root))
    found: set[str] = set()
    enumerated: list[str] = []
    while pending:
        drawing_component = pending.pop()
        children = _drawing_component_children(drawing_component)
        pending.extend(children)
        enumerated.append(str(drawing_component.Name or ""))
        if children:
            continue
        matched = _drawing_component_stems(adapter, drawing_component, visible_stems)
        drawing_component.Visible = bool(matched)
        found.update(matched)

    missing = sorted(visible_stems - found)
    if missing:
        raise RuntimeError(
            f"{label}: component families not found: {missing}; "
            f"enumerated={sorted(enumerated)}"
        )
    adapter.currentModel.EditRebuild3()
    _telemetry.success(f"{label}: isolated {', '.join(sorted(found))}")


@_telemetry.traced("drawing.pick_balloon_anchor", label_param="stem")
def _pick_component_anchor_edge(
    adapter: Any, view: Any, *, stem: str, label: str
) -> Any:
    """Return the one visible edge a ``stem``'s balloon leader attaches to.

    The anchor becomes the balloon's leader ATTACHMENT point, and
    :func:`_spread_balloons` assigns ring slots in the attachments' angular
    order, so an anchor that moves between runs can reorder two balloons
    attached at nearly the same angle and turn their leaders into a crossing.
    The drive-train sheet built clean on one fleet pass and failed
    ``check_drawing_layout`` with "1 leader crossing(s)" between items 5 and 27
    on the next, same commit, same cached assembly -- and ``GetVisibleEntities2``
    documents no ordering, which makes a moving anchor the obvious suspect.

    **Suspect, not culprit -- so this MEASURES before it pays.** Ordering the
    edges by geometry would settle it, and was tried: it costs a ``GetCurve`` +
    ``GetCurveParams2`` pair per visible edge -- 24.6 ms + 2.6 ms, MEASURED per
    call, not inferred from a paired total. A gear end view carries 481-577
    visible edges, so that is ~13 s per balloon and ~7 min for the 32-balloon
    sheet, which is why it never finished. Far too much to spend defending
    against an unproven hypothesis.

    So the pick stays ``edges[0]`` of the first matching leaf -- ONE geometry
    read, on the chosen edge only, to record WHERE it landed. Diff the
    ``drawing.balloon_anchor`` events of two passes and the question answers
    itself: identical anchors mean the enumeration is stable and the crossing
    came from somewhere else; different anchors prove the instability and earn
    the cost of fixing it. Nothing in the logs could answer that the first time.

    The traversal order is deterministic given the tree, and the ring sort in
    :func:`_spread_balloons` no longer breaks ties on arrival order, so those
    two sources are closed regardless of what the measurement says.
    """
    root = adapter._attempt(lambda: view.RootDrawingComponent2(False), default=None)
    if root is None:
        raise RuntimeError(f"{label}: drawing view has no root component")
    selected_edge: Any | None = None
    chosen_name = ""
    edge_count = 0
    enumerated: list[str] = []
    visited = 0
    pending = list(_drawing_component_children(root))
    while pending:
        drawing_component = pending.pop()
        children = _drawing_component_children(drawing_component)
        pending.extend(children)
        if children:
            continue
        visited += 1
        if stem not in _drawing_component_stems(
            adapter, drawing_component, frozenset({stem})
        ):
            continue
        chosen_name = str(drawing_component.Name or "")
        enumerated.append(chosen_name)
        component = adapter._attempt(
            lambda dc=drawing_component: dc.Component, default=None
        )
        edges = (
            adapter._attempt(lambda: view.GetVisibleEntities2(component, 1), default=())
            or ()
        )
        if not edges:
            continue
        edge_count = len(edges)
        selected_edge = edges[0]
        break
    if selected_edge is None:
        raise RuntimeError(
            f"{label}: {stem} has no visible edge; matching={enumerated}"
        )
    # One geometry read, on the winner only -- the whole point is that this is
    # cheap enough to leave on in every build, so two passes are comparable
    # without re-running anything under a special flag.
    key = _edge_endpoint_key(adapter, selected_edge) or ()
    # On the SPAN as well as the event: an event's attributes do not appear in
    # the span lines the profiling workflow reads, and this span exists so one
    # component's scan can be timed and attributed on its own rather than
    # disappearing into the whole-sheet balloon span.
    #
    # `visited` is every leaf the walk TOUCHED -- that is the workload, and it is
    # what the duration has to be read against. `matched` is almost always 1,
    # because the walk stops at the first component of the requested family, so
    # reporting only that made the attribute useless for comparing two scans
    # (Codex P2): a span that traversed 80 leaves and one that traversed 3 both
    # read "1".
    _span_scan_attrs(visited=visited, matched=len(enumerated), edges=edge_count)
    _telemetry.event(
        "drawing.balloon_anchor",
        stem=stem,
        component=chosen_name,
        edges=edge_count,
        anchor=",".join(f"{value:.6f}" for value in key),
    )
    return selected_edge


def _create_component_bom_balloon(
    adapter: Any,
    view: Any,
    *,
    stem: str,
    expected_item: str,
    label: str,
) -> Any:
    """Attach one BOM balloon to a visible edge of a requested component."""
    selected_edge = _pick_component_anchor_edge(adapter, view, stem=stem, label=label)
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    if not ddoc.ActivateView(view_name(adapter, view)):
        raise RuntimeError(f"{label}: failed to activate {stem} view")
    draw.ClearSelection2(True)
    if not view.SelectEntity(selected_edge, False):
        raise RuntimeError(f"{label}: failed to select {stem} visible edge")
    extension = _early_bound(draw.Extension, "IModelDocExtension")
    options = extension.CreateBalloonOptions()
    if options is None:
        raise RuntimeError(f"{label}: failed to create {stem} balloon options")
    options = _sw_type_info.early_bound_or_flag(options, "IBalloonOptions")
    options.Style = 1
    options.Size = 2
    options.UpperTextContent = 1
    options.ShowQuantity = False
    options.ItemNumberStart = 1
    options.ItemNumberIncrement = 1
    options.ItemOrder = 1
    note = extension.InsertBOMBalloon2(options)
    draw.ClearSelection2(True)
    if note is None:
        raise RuntimeError(f"{label}: failed to insert {stem} balloon")
    item = _balloon_item_number(adapter, note, label=label)
    if item != expected_item:
        raise RuntimeError(
            f"{label}: {stem} resolved item {item}, expected {expected_item}"
        )
    return note


@_telemetry.traced("drawing.component_bom_balloons", label_param="label")
def add_component_bom_balloons(
    adapter: Any,
    view: Any,
    *,
    items: Sequence[tuple[str, str]],
    label: str,
    margin: float = 0.014,
) -> list[Any]:
    """Insert and ring one checked balloon per requested component family."""
    if not items:
        raise ValueError(f"{label}: component balloon list must not be empty")
    stems = [stem for stem, _item in items]
    numbers = [item for _stem, item in items]
    if len(stems) != len(set(stems)) or len(numbers) != len(set(numbers)):
        raise ValueError(f"{label}: duplicate component or item number")
    balloons = [
        _create_component_bom_balloon(
            adapter,
            view,
            stem=stem,
            expected_item=item,
            label=label,
        )
        for stem, item in items
    ]
    if margin <= 0.0:
        raise ValueError(f"{label}: balloon ring margin must be positive")
    _spread_balloons(adapter, view, balloons, margin=margin)
    adapter.currentModel.EditRebuild3()
    _telemetry.success(f"{label}: inserted {len(balloons)} targeted balloons")
    return balloons


@_telemetry.traced("drawing.auto_balloons_across_views", label_param="label")
def add_auto_balloons_across_views(
    adapter: Any,
    views: Sequence[Any],
    *,
    expected: int,
    label: str,
    existing_balloons: Sequence[Any] = (),
    margin: float = 0.014,
    layout: int = 1,
) -> list[Any]:
    """Balloon successive views until every BOM item number is represented.

    Dense assemblies can hide whole component families in one pictorial view.
    AutoBalloon5 only balloons items visible in the selected view, so run it on
    each orthographic and pictorial view, preserve every placed balloon, and
    validate the union of displayed BOM item numbers against the table's full
    contiguous item range. Each view's balloons are spread around that view.
    """
    if margin <= 0.0:
        raise ValueError(f"{label}: balloon ring margin must be positive")
    all_balloons = list(existing_balloons)
    item_numbers = {
        _balloon_item_number(adapter, note, label=f"{label} existing")
        for note in existing_balloons
    }
    for index, view in enumerate(views, start=1):
        view_label = f"{label} view {index}"
        balloons = _create_auto_balloons(
            adapter, view, label=view_label, allow_empty=True, layout=layout
        )
        if not balloons:
            continue
        _spread_balloons(adapter, view, balloons, margin=margin)
        for note in balloons:
            item_numbers.add(_balloon_item_number(adapter, note, label=view_label))
        all_balloons.extend(balloons)
    expected_numbers = {str(item) for item in range(1, expected + 1)}
    missing = sorted(expected_numbers - item_numbers, key=int)
    unexpected = sorted(item_numbers - expected_numbers)
    if missing or unexpected:
        raise RuntimeError(
            f"{label}: balloon item coverage mismatch; missing={missing}, "
            f"unexpected={unexpected}, seen={sorted(item_numbers)}"
        )
    adapter.currentModel.EditRebuild3()
    _telemetry.success(
        f"{label}: {len(all_balloons)} balloons cover all {expected} BOM items"
    )
    return all_balloons


@_telemetry.traced("drawing.position_bom_balloon", label_param="label")
def position_bom_balloon(
    adapter: Any,
    balloons: Sequence[Any],
    *,
    item_number: str,
    position_xy: tuple[float, float],
    label: str,
    position_tolerance_m: float = 1e-6,
) -> None:
    """Move one uniquely identified BOM balloon to a checked sheet position."""
    if position_tolerance_m <= 0.0:
        raise ValueError("balloon position tolerance must be positive")
    matches = [
        note
        for note in balloons
        if _balloon_item_number(adapter, note, label=label) == item_number
    ]
    if len(matches) != 1:
        raise RuntimeError(
            f"{label}: expected one balloon for item {item_number}, got {len(matches)}"
        )
    note = _sw_type_info.early_bound_or_flag(
        matches[0],
        "INote",
        "GetAnnotation",
        "IsStackedBalloon",
        "IsStackedBalloonMaster",
    )
    annotation = note.GetAnnotation()
    if annotation is None:
        raise RuntimeError(f"{label}: item {item_number} has no annotation")
    annotation = _sw_type_info.early_bound_or_flag(
        annotation,
        "IAnnotation",
        "GetPosition",
        "GetSpecificAnnotation",
        "SetPosition",
    )
    ddoc = _early_bound(adapter.currentModel, "IDrawingDoc")
    sheet = ddoc.GetCurrentSheet()
    magnetic_lines = int(adapter._get_attr_or_call(sheet, "GetMagneticLinesCount") or 0)
    _telemetry.info(
        f"{label}: item {item_number} placement diagnostics "
        f"stacked={bool(note.IsStackedBalloon())}, "
        f"stack_master={bool(note.IsStackedBalloonMaster())}, "
        f"magnetic_lines={magnetic_lines}"
    )
    note.LockPosition = False
    info = note.GetBalloonInfo()
    anchor = annotation.GetPosition()
    if info is None or len(info) < 2 or anchor is None or len(anchor) < 2:
        raise RuntimeError(f"{label}: item {item_number} has no position read-back")
    actual_xy = (float(info[0]), float(info[1]))
    delta = tuple(expected - actual for actual, expected in zip(actual_xy, position_xy))
    target_anchor = (float(anchor[0]) + delta[0], float(anchor[1]) + delta[1])
    # GetBalloonInfo can lag the note's new origin until the graphics pipeline
    # redraws. Retry the SAME absolute anchor, never a cumulative delta against
    # stale circle data, and redraw before judging each rendered-circle readback.
    for _attempt in range(3):
        note.LockPosition = False
        moved = bool(annotation.SetPosition(target_anchor[0], target_anchor[1], 0.0))
        if not moved:
            raise RuntimeError(f"{label}: failed to position item {item_number}")
        note.LockPosition = True
        adapter.currentModel.EditRebuild3()
        adapter.currentModel.GraphicsRedraw2()
        current_note = annotation.GetSpecificAnnotation()
        if current_note is None:
            raise RuntimeError(
                f"{label}: item {item_number} note vanished after positioning"
            )
        note = _sw_type_info.early_bound_or_flag(
            current_note, "INote", "GetBalloonInfo"
        )
        moved_anchor = annotation.GetPosition()
        moved_info = note.GetBalloonInfo()
        _telemetry.info(
            f"{label}: item {item_number} attempt {_attempt + 1} "
            f"anchor={tuple(float(value) for value in moved_anchor[:2]) if moved_anchor else None}, "
            f"circle={tuple(float(value) for value in moved_info[:2]) if moved_info else None}"
        )
        if moved_info and all(
            abs(float(moved_info[index]) - expected) <= position_tolerance_m
            for index, expected in enumerate(position_xy)
        ):
            break
    info = note.GetBalloonInfo()
    if info is None or len(info) < 2:
        raise RuntimeError(f"{label}: item {item_number} circle has no final read-back")
    actual_xy = (float(info[0]), float(info[1]))
    if any(
        abs(actual - expected) > position_tolerance_m
        for actual, expected in zip(actual_xy, position_xy)
    ):
        raise RuntimeError(
            f"{label}: item {item_number} circle moved to {actual_xy}, "
            f"expected {position_xy}"
        )


def stamp_drawing_summary(
    adapter: Any, drawing_model: Any, fields: dict[int, str]
) -> None:
    """Write and read-verify the drawing document summary metadata."""
    model_doc = _sw_type_info.early_bound_or_flag(drawing_model, "IModelDoc2")
    for field, value in fields.items():
        # SummaryInfo is a property: early binding splits it into a getter
        # (SummaryInfo(field)) and a setter (SetSummaryInfo(field, value)).
        # A 2-arg SummaryInfo(field, value) put only worked under late binding.
        model_doc.SetSummaryInfo(field, value)
        if model_doc.SummaryInfo(field) != value:
            raise RuntimeError(f"drawing summary field {field} did not persist")


# An isometric/pictorial view's axis-aligned outline is mostly empty diagonal
# space, so its box is not a faithful collision footprint -- give such views
# ``NONE`` collision scope. ``GetOrientationName`` returns the predefined view
# name (e.g. "*Isometric"); ortho views return "*Front"/"*Right"/... and
# projected / section / detail views return "".
_PICTORIAL_ORIENTATIONS = frozenset({"*isometric", "*dimetric", "*trimetric"})

# A note centered inside its owning view is treated as a hole tag / balloon
# (detail on the view) only when it is also SMALL: native hole-table tags span
# ~6 mm, whereas the general-notes block is >50 mm on a side. The size gate keeps
# the exemption narrow so a large general note accidentally dropped onto its own
# view is still audited as a collision (Codex #269).
_TAG_MAX_SPAN_M = 0.015


def _view_scope(adapter: Any, view: Any) -> CollisionScope:
    """``NONE`` for a pictorial view (empty diagonal box), ``ALL`` for an ortho view."""
    orientation = str(adapter._get_attr_or_call(view, "GetOrientationName") or "")
    if orientation.strip().lower() in _PICTORIAL_ORIENTATIONS:
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
        note, "INote", "GetExtent", "GetText", "IsBomBalloon", "GetBalloonInfo"
    )
    text = str(adapter._attempt(lambda: note.GetText(), default="") or "")
    diagnostic_name = f"{name} {text!r}" if text else name
    # A BOM balloon's GetExtent includes its LEADER -- the box spans from the
    # balloon circle to the pointed-at component (same leader-polluted-box dead
    # end as GD&T symbols), so neighboring balloons' boxes always intersect near
    # the view. GetBalloonInfo describes the CIRCLE instead -- centre + radius,
    # no leader -- so box the circle it actually draws.
    if bool(adapter._attempt(lambda: note.IsBomBalloon(), default=False)):
        info = adapter._attempt(lambda: note.GetBalloonInfo())
        if not info or len(info) < 7:
            raise RuntimeError(
                f"{name}: GetBalloonInfo did not return the balloon circle -- "
                "refusing to fall back to a nominal box, which would audit a "
                "guess against placement derived from the measured radius and "
                "silently disagree with it"
            )
        # Centre from GetBalloonInfo, NOT GetPosition: GetPosition is the
        # annotation ANCHOR, which is measurably offset from the circle centre
        # (probed on pen-assembly), so it boxed the balloon off-centre.
        cx, cy, half = float(info[0]), float(info[1]), float(info[6])
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


def _datum_is_dimension_attached(adapter: Any, annotation: Any) -> bool:
    """Whether a datum tag is attached to a display dimension.

    SolidWorks reports ``IDatumTag`` primitive coordinates for this attachment
    type in the dimension's local frame.  They must not be mixed with the
    sheet-space annotation position used by the layout audit.
    """
    attachment_types = (
        adapter._attempt(
            lambda: adapter._get_attr_or_call(annotation, "GetAttachedEntityTypes")
        )
        or ()
    )
    return _SEL_DIMENSION in (int(value) for value in attachment_types)


def _measured_gdt_box(
    adapter: Any, annotation: Any, kind: int
) -> tuple[float, float, float, float] | None:
    """Box a GD&T symbol from the geometry SolidWorks actually renders.

    ``IDatumTag`` / ``IGtol`` / ``ISFSymbol`` all expose the symbol's real
    primitives -- ``GetLineAtIndex(i)`` -> ``[lineType, startPt[3], endPt[3]]``,
    ``GetTriangleAtIndex(i)`` -> ``[vtx1[3], vtx2[3], vtx3[3], isFilled,
    lineType]``, ``GetArcAtIndex(i)`` -> ``[lineType, startPt[3], endPt[3],
    centerPt[3], rotationDir]``. Their union is the symbol's ink, leader
    included, which is exactly the question an OVERFLOW check asks.

    They are NOT on ``IAnnotation``: go through ``GetSpecificAnnotation()``
    first, or every call raises. (``GetExtent`` is not the route -- the type
    library declares it on ``IBomTable`` and ``INote`` only, verified against a
    working ``INote.GetExtent()`` in the same probe run.)
    """
    if kind == _ANNOT_DATUM:
        if _datum_is_dimension_attached(adapter, annotation):
            # A datum attached to a display dimension reports IDatumTag primitive
            # coordinates in that dimension's local frame, unlike the sheet-space
            # primitives of an edge-attached tag. Its IAnnotation.GetPosition is
            # still the documented sheet-space symbol origin, so the nominal datum
            # box below is the truthful overflow check for this attachment type.
            return None

    spec = adapter._attempt(
        lambda: adapter._get_attr_or_call(annotation, "GetSpecificAnnotation")
    )
    if spec is None:
        return None
    spec = _sw_type_info.early_bound_or_flag(spec, _GDT_IFACE[kind])

    points: list[tuple[float, float]] = []
    for count_name, at_name, offsets in (
        ("GetLineCount", "GetLineAtIndex", ((1, 2), (4, 5))),
        ("GetArcCount", "GetArcAtIndex", ((1, 2), (4, 5))),
        ("GetTriangleCount", "GetTriangleAtIndex", ((0, 1), (3, 4), (6, 7))),
    ):
        n = (
            adapter._attempt(
                lambda c=count_name: int(adapter._get_attr_or_call(spec, c) or 0)
            )
            or 0
        )
        for i in range(n):
            raw = adapter._attempt(lambda a=at_name, j=i: getattr(spec, a)(j))
            if not raw:
                continue
            v = [float(t) for t in raw]
            points.extend((v[ix], v[iy]) for ix, iy in offsets if iy < len(v))
    if not points:
        return None

    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return min(xs), min(ys), max(xs), max(ys)


def _gdt_element(
    adapter: Any, annotation: Any, name: str, kind: int
) -> LayoutElement | None:
    """Box a native GD&T symbol from its rendered geometry where possible.

    Given ``NONE`` collision scope -- a datum tag legitimately sits beside its
    own control frame, so these are overflow-checked only, never overlap-checked.

    Datum tags and feature-control frames are MEASURED (``_measured_gdt_box``).
    They have to be: an FCF's anchor is its frame's TOP-LEFT corner and its width
    grows with compartment count (measured: 41.6 mm for "Ø0.20|A|B|C" vs 32.2 mm
    for "0.10|A|B", both 7.0 mm tall), so the old symmetric ±8 mm square wasted
    8 mm above on empty sheet while missing ~34 mm of frame body to the right --
    a border crossing in an FCF's right half read clean. No fixed box can be
    right when the width depends on the text.

    A surface-finish symbol keeps its measured ``_SF_BOX_*`` constants, because
    measuring it would be WORSE: its "Ra 1.6" text overhangs the bar drawn above
    it by ~1.3 mm, and text is not among the primitives, so a geometry-derived
    box quietly clips it. The constants were measured off renders (which do show
    the text) and cover it. Same reason the box is asymmetric at all: the anchor
    is the leader's attachment at the body's bottom-left, so a symmetric box is
    the wrong SHAPE, not merely the wrong size, and once let an Ra print over the
    sheet border with the audit reporting clean.
    """
    position = adapter._attempt(
        lambda: adapter._get_attr_or_call(annotation, "GetPosition")
    )
    if not position:
        return None
    x, y = float(position[0]), float(position[1])
    if kind == _ANNOT_SFSYM:
        return LayoutElement(
            name,
            "gdt",
            x - _SF_BOX_LEFT_M,
            y - _SF_BOX_DOWN_M,
            x + _SF_BOX_RIGHT_M,
            y + _SF_BOX_UP_M,
            scope=CollisionScope.NONE,
        )
    measured = _measured_gdt_box(adapter, annotation, kind)
    if measured is not None:
        x0, y0, x1, y1 = measured
        return LayoutElement(name, "gdt", x0, y0, x1, y1, scope=CollisionScope.NONE)
    # No geometry came back (an unexpected kind, or a PMI-only annotation whose
    # GetSpecificAnnotation is None). Fall back to the nominal square rather than
    # dropping the symbol from the audit entirely -- a coarse box still catches
    # one placed clear off the sheet.
    half = _NOMINAL_GDT_HALF_M
    return LayoutElement(
        name, "gdt", x - half, y - half, x + half, y + half, scope=CollisionScope.NONE
    )


def _dim_element(adapter: Any, annotation: Any, name: str) -> LayoutElement | None:
    """Box a display dimension / hole callout as a small nominal square (NONE scope).

    Like GD&T, a dimension exposes only a text-anchor ``GetPosition`` and sits on
    the geometry it measures, so it is overflow-checked and title-block-keep-out
    checked only -- never overlap-checked against a view (Codex #269 thread 1).
    """
    position = adapter._attempt(
        lambda: adapter._get_attr_or_call(annotation, "GetPosition")
    )
    if not position:
        return None
    x, y = float(position[0]), float(position[1])
    half = _NOMINAL_DIM_HALF_M
    return LayoutElement(
        name, "dim", x - half, y - half, x + half, y + half, scope=CollisionScope.NONE
    )


def _iter_view_annotations(adapter: Any, view: Any):
    """Yield ``(LayoutElement, annotation)`` for each note / GD&T symbol / dimension.

    ``IView.GetAnnotations`` returns dimensions, center marks, cosmetic-thread
    callouts, notes and GD&T symbols; NOTES (swNote), native GD&T symbols (datum
    tag / feature-control frame / surface-finish) and DISPLAY DIMENSIONS / hole
    callouts (swDisplayDimension) become elements. Tables come from
    ``GetTableAnnotations`` instead.

    The live annotation rides along so the caller can pull its leader geometry
    (see :func:`_leader_segments_of`) without a second COM walk.
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
        name = str(adapter._get_attr_or_call(annotation, "GetName") or "")
        if kind == _ANNOT_NOTE:
            element = _note_element(adapter, annotation, name)
        elif kind in _GDT_TYPES:
            element = _gdt_element(adapter, annotation, name, kind)
        elif kind == _ANNOT_DIM:
            element = _dim_element(adapter, annotation, name)
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


# swZoneMargin_e -- the four margins reserved by the sheet format's zone band.
_ZONE_MARGINS = {"top": 0, "bottom": 1, "right": 2, "left": 3}


def sheet_drawable_region(
    adapter: Any, sheet: Any, *, width: float, height: float
) -> DrawableRegion:
    """The region inside the sheet's border/zone band, QUERIED from the sheet.

    The zone band is sheet metadata (``ISheet::GetZoneMargin``), so the audit
    reads it rather than carrying a measured copy: edit the zone margins in the
    DRWDOT and the keep-out follows automatically.

    A sheet format that declares no zone margins returns 0 for every side; that
    is reported as the whole sheet rather than treated as an error, so a plain
    unzoned sheet still audits.
    """
    margins: dict[str, float] = {}
    for side, code in _ZONE_MARGINS.items():
        value = adapter._attempt(lambda c=code: sheet.GetZoneMargin(c))
        if value is None:
            raise RuntimeError(
                f"cannot read the sheet's {side} zone margin -- the border "
                "keep-out cannot be audited"
            )
        margins[side] = float(value)
    if not any(margins.values()):
        _telemetry.warn(
            "sheet declares no zone margins; auditing against the full sheet"
        )
        return DrawableRegion.whole_sheet(width, height)
    region = DrawableRegion.from_margins(width, height, **margins)
    _telemetry.event(
        "drawing.zone_region",
        left=margins["left"],
        right=margins["right"],
        bottom=margins["bottom"],
        top=margins["top"],
    )
    return region


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

    But the leader IS DRAWN, and it IS readable -- as ordinary geometry via
    ``IDatumTag::GetLineAtIndex``. Without this, a datum tag routed straight
    across a neighbouring view is invisible to BOTH audits: its box is
    ``CollisionScope.NONE`` so it is never overlap-checked, and it contributes no
    leader segments so it is never crossing-checked (codex #334). That is not
    hypothetical -- the eye pass found exactly this on cone-tip-bushing (datum A's
    leader driven 41.8 mm down through the whole end view) and crank-arm (datum A
    across a 16 mm section), both passing every gate.
    """
    if _datum_is_dimension_attached(adapter, annotation):
        return []

    spec = adapter._attempt(
        lambda: adapter._get_attr_or_call(annotation, "GetSpecificAnnotation")
    )
    if spec is None:
        return []
    spec = _sw_type_info.early_bound_or_flag(spec, "IDatumTag")
    count = int(
        adapter._attempt(lambda: adapter._get_attr_or_call(spec, "GetLineCount")) or 0
    )
    lines: list[tuple[tuple[float, float], tuple[float, float]]] = []
    for index in range(count):
        raw = adapter._attempt(lambda i=index: spec.GetLineAtIndex(i))
        if not raw:
            continue
        v = [float(t) for t in raw]  # [lineType, startPt[3], endPt[3]]
        lines.append(((v[1], v[2]), (v[4], v[5])))
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
    adapter: Any,
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
      surface-finish) and DISPLAY DIMENSION / hole callout, boxed nominally and
      scoped ``NONE`` (no real bbox API, and they sit on the geometry they
      annotate) -- overflow- and title-block-keep-out-checked only;
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
            # A native hole callout is an IDisplayDimension whose leader is NOT a
            # SetLeader3 leader, so GetLeaderCount()==0 and the call above returns
            # nothing -- yet its offset text can drive a leader across a
            # neighbouring view. Reconstruct it from the text + the projected
            # attachment (codex #3605215320); a no-op for non-callout dimensions.
            if element.kind == "dim":
                leaders.extend(
                    _display_dimension_leader_segments(
                        adapter,
                        annotation,
                        label=element.label,
                        owner=name,
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
        for element, annotation in _iter_view_annotations(adapter, sheet_view):
            if element.kind != "note":
                continue
            owner_type = int(
                adapter._attempt(
                    lambda a=annotation: adapter._get_attr_or_call(a, "OwnerType"),
                    default=-1,
                )
                or -1
            )
            if owner_type != 1:  # swAnnotationOwner_DrawingSheet
                continue
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
            _TITLE_BLOCK_LEFT_M,
            0.0,
            width,
            _TITLE_BLOCK_TOP_M,
        )
    )
    region = sheet_drawable_region(adapter, sheet, width=width, height=height)
    return elements, leaders, region


def check_drawing_layout(adapter: Any, *, stem: str = "") -> None:
    """Diagnose a colliding, border-crossing, or leader-crossed layout.

    This is an explicit diagnostic, not part of the drawing build hot path.

    ``stem`` names the sheet in failures. Every sheet is held to ZERO on every
    defect class -- there is no grandfathered case. There WAS one: pen-assembly
    carried 2 leader crossings behind a `_KNOWN_LEADER_CROSSINGS` ratchet, on the
    reasoning that fixing them needed a design decision. It did not -- it needed
    the balloon's rendered radius, which INote::GetBalloonInfo had all along (see
    :func:`_spread_balloons`). The ratchet was deleted with the defect.
    """
    with _telemetry.span("drawing.layout_audit"):
        elements, leaders, region = collect_layout_elements(adapter)
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


@_telemetry.traced("drawing.finalize")
async def finalize_drawing(
    adapter: Any,
    outputs: DrawingOutputs,
    *,
    pdf_title: str,
    scale: tuple[float, float] = (1.0, 1.0),
    redundant_note_substrings: Sequence[str] = (),
    expected_redundant_notes: int = 0,
    expected_sheet_names: tuple[str, ...] | None = None,
) -> dict[str, str]:
    """Validate the sheet contract and export SLDDRW, PDF, and rendered PNG."""
    drawing_model = adapter.currentModel
    ddoc = _early_bound(
        drawing_model, "IDrawingDoc"
    )  # IDrawingDoc view for drawing-only methods (same dispatch)
    drawing_model.ClearSelection2(True)
    sheet_names = tuple(adapter._get_attr_or_call(ddoc, "GetSheetNames") or ())
    if not sheet_names:
        raise RuntimeError("finished drawing has no sheets")
    if expected_sheet_names is not None and sheet_names != expected_sheet_names:
        raise RuntimeError(
            f"drawing sheet contract mismatch: {sheet_names!r} != "
            f"{expected_sheet_names!r}"
        )

    # Every sheet owns its own $PRPSHEET link. Point each at that sheet's first
    # real view after all views exist, validate the linked model's tolerance and
    # current-release Revision properties, and hold every sheet to the same ASME B
    # contract.
    for sheet_name in sheet_names:
        if not ddoc.ActivateSheet(sheet_name):
            raise RuntimeError(f"failed to activate drawing sheet {sheet_name!r}")
        sheet = adapter._get_attr_or_call(ddoc, "GetCurrentSheet")
        if sheet is None:
            raise RuntimeError(f"drawing sheet {sheet_name!r} has no ISheet")
        # Inserting a model view lets SolidWorks auto-drift the SHEET scale off
        # the 1:1 the template pinned (each view still carries its own explicit
        # scale), so re-pin it once here before asserting the contract.
        if not sheet.SetScale(float(scale[0]), float(scale[1]), False, False):
            raise RuntimeError(
                f"failed to set final drawing sheet {sheet_name!r} scale"
            )
        assert_asme_b_sheet(
            adapter, sheet, phase=f"before save {sheet_name}", scale=scale
        )
        properties = list(adapter._get_attr_or_call(sheet, "GetProperties2") or [])
        if len(properties) < 8:
            raise RuntimeError(
                f"sheet {sheet_name!r} has incomplete properties: {properties!r}"
            )
        if bool(properties[7]):
            # PasteSheet preserves the source sheet's "same as sheet specified
            # in Document Properties" flag. In that mode SolidWorks silently
            # ignores a per-sheet CustomPropertyView assignment and returns the
            # literal UI label instead of a view name. Clear the mode through
            # the current ISheet API while preserving every other property.
            sheet.SetProperties2(
                int(properties[0]),
                int(properties[1]),
                float(properties[2]),
                float(properties[3]),
                bool(properties[4]),
                float(properties[5]),
                float(properties[6]),
                False,
            )
            sheet = adapter._get_attr_or_call(ddoc, "GetCurrentSheet")
            properties = list(adapter._get_attr_or_call(sheet, "GetProperties2") or [])
            if len(properties) < 8 or bool(properties[7]):
                raise RuntimeError(
                    f"failed to enable explicit property source on {sheet_name!r}"
                )
            assert_asme_b_sheet(
                adapter,
                sheet,
                phase=f"explicit property source {sheet_name}",
                scale=scale,
            )
        first_view = next(iter_views(adapter), None)
        if first_view is None:
            raise RuntimeError(
                f"drawing sheet {sheet_name!r} has no view for property links"
            )
        first_name = view_name(adapter, first_view)
        sheet.CustomPropertyView = first_name
        sheet = adapter._get_attr_or_call(ddoc, "GetCurrentSheet")
        linked = str(adapter._get_attr_or_call(sheet, "CustomPropertyView") or "")
        if linked != first_name:
            raise RuntimeError(
                f"sheet {sheet_name!r} CustomPropertyView did not take: "
                f"{linked!r} != {first_name!r}"
            )
        linked_model = adapter._get_attr_or_call(first_view, "ReferencedDocument")
        if linked_model is None:
            raise RuntimeError(
                f"view {first_name!r} has no referenced document to validate"
            )
        linked_model = _sw_type_info.early_bound_or_flag(
            linked_model, "IModelDoc2", "GetCustomInfoValue"
        )
        read_required_properties(
            linked_model,
            (*TITLE_BLOCK_TOLERANCE_PROPERTIES, TITLE_BLOCK_REVISION_PROPERTY),
            required=(
                *TITLE_BLOCK_TOLERANCE_PROPERTIES,
                TITLE_BLOCK_REVISION_PROPERTY,
            ),
        )

    # The title block's UNIT cell links $PRP:"UNIT_DISPLAY" (a DRAWING-doc
    # property, unlike the $PRPSHEET part-property links), so the declared unit
    # always tracks what set_units_mm actually configured. Flip to "IN" with
    # the inch migration (#290) -- a hardcoded IN cell over mm dimensions would
    # read as inch values and get machined at the wrong scale (Codex P1).
    from _common import apply_custom_properties

    apply_custom_properties(adapter, {"UNIT_DISPLAY": "MM"})

    # Explicit recipe-requested cleanup remains sheet-scoped. Layout and view
    # appearance are otherwise left exactly as SolidWorks produced them.
    removed_notes = 0
    for sheet_name in sheet_names:
        if not ddoc.ActivateSheet(sheet_name):
            raise RuntimeError(
                f"failed to activate drawing sheet {sheet_name!r} for note cleanup"
            )
        removed_notes += sum(
            remove_notes_matching(adapter, substring)
            for substring in redundant_note_substrings
        )
    if removed_notes != expected_redundant_notes:
        raise RuntimeError(
            f"final drawing removed {removed_notes} redundant notes, "
            f"expected {expected_redundant_notes}: "
            f"{tuple(redundant_note_substrings)!r}"
        )
    if removed_notes:
        _telemetry.info(f"removed {removed_notes} redundant final drawing notes")

    if not ddoc.ActivateSheet(sheet_names[0]):
        raise RuntimeError("failed to restore first drawing sheet before export")

    # Persist the native drawing and PDF once from the fully loaded authored
    # document. Reopen/scale/save cycles are deliberately absent from this hot
    # path; the template and precomputed recipe placements own the layout.
    with _telemetry.span("drawing.save_and_export_pdf"):
        artifacts = save_drawing(
            adapter, str(outputs.slddrw), pdf_path=str(outputs.pdf)
        )
    if set(artifacts) != {"drawing", "pdf"}:
        raise RuntimeError(f"drawing save/export incomplete: {artifacts!r}")
    sanitize_pdf_metadata(outputs.pdf, title=pdf_title, expected_pages=len(sheet_names))
    render_pdf_png(outputs.pdf, outputs.png, expected_pages=len(sheet_names))
    artifacts["png"] = str(outputs.png.resolve())
    if set(artifacts) != {"drawing", "pdf", "png"}:
        raise RuntimeError(f"drawing export incomplete: {artifacts!r}")
    return artifacts


def draw_note_table(
    adapter: Any,
    *,
    rows: Sequence[Sequence[str]],
    column_x: Sequence[float],
    row_y: Sequence[float],
) -> None:
    """Place a compact schedule using aligned notes.

    Geometry stays in the checked-in sheet format.  The drawing recipe supplies
    only row content, so future prints can reuse the same uncluttered schedule
    layout without adding table objects or template-specific anchors.
    """
    if len(rows) != len(row_y):
        raise ValueError("table row content and row positions differ")
    for y, row in zip(row_y, rows, strict=True):
        if len(row) != len(column_x):
            raise ValueError("table row has the wrong number of columns")
        for x, text in zip(column_x, row, strict=True):
            if add_note(adapter, text, x, y) is None:
                raise RuntimeError(f"failed to add schedule cell {text!r}")
