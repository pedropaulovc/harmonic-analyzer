"""Project drawing framework shared by every manufacturing print.

Raw project-agnostic COM calls remain in ``solidworks_mcp``.  This layer owns
the harmonic-analyzer book policy: explicit ASME B orientation, checked-in
templates, exact PDF/PNG output, and fail-loud multi-leader callouts.
Part-specific views, dimensions, and notes belong in ``draw_<part>.py``.
"""

from __future__ import annotations

import contextlib
import enum
import json
import math
import os
import re
import sys
import time
from collections import Counter
from dataclasses import dataclass, replace
from itertools import combinations, product
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator, Literal, Mapping, Sequence

import _config
import _telemetry
import _seat_forensics
from _common import (
    _bind,
    _build_id,
    _com_invoke,
    _early_bound,
    _read_member,
    _visible_document_paths,
    apply_custom_properties,
)
from _gtol_spec import GTOL_SYMBOLS as _GTOL_SYMBOLS
from _gtol_spec import gtol_frame_xml as _gtol_frame_xml
from _surface_finish import SurfaceFinishControl
from _drawing_simplified import simplified_name
from _drawing_layout_check import (
    CollisionScope,
    DrawableRegion,
    LayoutElement,
    LeaderSegment,
    audit_layout,
    format_findings,
)
from _drawing_layout_audit import annotation_display, run_layout_audit
from _layout_audit import display_box, estimated_text_runs, line_segment
from _drawing_registry import DRAWING_TEMPLATES, DrawingLayout, layout_report_path
from solidworks_mcp.adapters import sw_type_info as _sw_type_info
from solidworks_mcp.adapters.com_variant import (
    bool_array,
    bstr_array,
    dispatch_array,
    double_array,
)
from solidworks_mcp.adapters.pywin32_adapter import null_callout
from solidworks_mcp.adapters.solidworks import drawing as _sw_drawing
from solidworks_mcp.adapters.solidworks.drawing import (
    TOL_BASIC,
    add_note,
    curate_dimensions,
    dimension_name,
    iter_views,
    new_drawing,
    place_view,
    remove_notes_matching as remove_notes_matching,
    save_drawing,
    set_units_mm,
    view_name,
    visible_component_entities as visible_component_entities,
)


def _record_center_marks(counts: dict[str, Any]) -> None:
    """Every auto_center_marks call's centre-mark count, before and after
    AutoInsertCenterMarks2, as a span event (#913: each mark printed twice on
    30 views). after == 2 x before would point at a template auto-insert the
    explicit call repeats; before == 0 at duplicates made some other way.

    The observer is process-global and set when this module is imported, so
    a script that never imports _drawing_common records nothing (every
    auto_center_marks caller does). OTel attributes must be primitives: a
    count whose read raised arrives as None and is sent as -1, named in
    ``read_failed``.
    """
    attributes = {key: value for key, value in counts.items() if value is not None}
    failed = sorted(key for key, value in counts.items() if value is None)
    for key in failed:
        attributes[key] = -1
    if failed:
        attributes["read_failed"] = failed
    _telemetry.event("center_marks.auto_insert", **attributes)
    _telemetry.debug(
        f"center marks {counts.get('view')!r}: {counts.get('before')} -> {counts.get('after')}"
        f" (holes={counts.get('holes')}, slots={counts.get('slots')}, ok={counts.get('ok')})"
    )


_sw_drawing.CENTER_MARK_OBSERVER = _record_center_marks


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
_SEL_EDGE = 1  # swSelectType_e.swSelEDGES
_SEL_SILHOUETTE = 46  # swSelectType_e.swSelSILHOUETTES
_SEL_FACE = 2  # swSelectType_e.swSelFACES
_GDT_TYPES = frozenset({_ANNOT_DATUM, _ANNOT_GTOL, _ANNOT_SFSYM})
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
# the native hole callouts. The element audit gives them NO box: the shared
# layout audit (``_drawing_layout_audit``) boxes their text from its display
# data and checks it against text, lines and model edges on every sheet. The
# 8 mm nominal square they used to get here was never overlap-checked, so
# MHA-DT-021's "20.8"/"8.42" and its callouts over the right view passed.
_ANNOT_DIM = 4


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

# Ink gap left between two balloon circles pushed apart on the ring. Their radius
# is measured from its rendered full-circle arc (4.72 mm on pen-assembly), so
# this is only the clearance between them, not a stand-in for the circle itself.
_BALLOON_CLEARANCE_M = 0.0015


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
        selection_manager = _early_bound(draw.SelectionManager, "ISelectionMgr")
        selection_data = selection_manager.CreateSelectData()
        selection_data.View = view
        if entity_type == "SILHOUETTE":
            selectable = _sw_type_info.early_bound_or_flag(
                entity, "ISilhouetteEdge", "Select2"
            )
            selected = bool(selectable.Select2(False, selection_data))
        else:
            selectable = _early_bound(entity, "IEntity")
            selected = bool(selectable.Select4(False, selection_data))
    elif xy is not None:
        # Coordinate hit-testing needs current geometry, not a pending repaint.
        _early_bound(view, "IView").UpdateViewDisplayGeometry()
        selected = bool(
            draw.Extension.SelectByID2(
                "", entity_type, xy[0], xy[1], 0.0, False, 0, null_callout(), 0
            )
        )
    if not selected and xy is not None:
        # A coordinate pick is the seat's interactive hit test: name the
        # window it ran in before raising.
        _seat_forensics.capture_pick_miss(
            adapter,
            f"failed to select {label} {entity_type.lower()} at sheet ({xy[0]:g}, {xy[1]:g})",
            view=name,
            entity_type=entity_type,
            sheet_xy=xy,
        )
    if not selected:
        raise RuntimeError(f"failed to select {label} {entity_type.lower()} by entity")
    count = int(draw.SelectionManager.GetSelectedObjectCount2(-1))
    if entity is not None and count != 1:
        raise RuntimeError(
            f"selecting {label} {entity_type.lower()} produced {count} entities"
        )
    entity = draw.SelectionManager.GetSelectedObject6(count, -1)
    if entity is None:
        raise RuntimeError(f"selected {label} {entity_type.lower()} has no entity")
    return entity


# How far a leader may land from its requested attachment point.  Measured on
# the #1105 idprobe farm leaves (20260928T084216466Z, 14 surface finishes and
# feature-control frames landed by selection point): every leader but one read
# back within 4e-8 m of its request; the pinion-bracket pivot-bore finish,
# whose request sits on the bore circle at 45 deg, re-solved 0.61 mm along the
# edge.  1 mm admits that re-solve and rejects a landing on the neighbouring
# edge, which the earlier 5 mm bound could not.
_LEADER_LANDING_TOLERANCE_M = 0.001
# A BOM balloon's leader lands on an edge the hit test proved drawn at the
# requested point, but the edges beside it can be closer than 1 mm: at 1:8 a
# #4-40 screw head is 0.35 mm across on the sheet, and on run
# 20260928T194845954Z-44f5de00de924735961d14f4aad40337 a 0.46 mm drift left
# the frame's screw balloon ending in the nameplate engraving.
_BALLOON_LANDING_TOLERANCE_M = 0.0002


def _assert_leader_lands(
    annotation: Any,
    leader_attach_xy: tuple[float, float],
    *,
    what: str,
    label: str,
    tolerance: float = _LEADER_LANDING_TOLERANCE_M,
) -> None:
    """Fail unless ``annotation`` keeps one live leader ending within
    ``tolerance`` of ``leader_attach_xy``.  A returned True from a leader or
    selection-point setter proves nothing, so the landing is read back."""
    leaders = int(annotation.GetLeaderCount())
    dangling = bool(annotation.IsDangling())
    if dangling or leaders != 1:
        raise RuntimeError(
            f"{what} leader did not survive ({label}): dangling={dangling}, "
            f"leaders={leaders}"
        )
    points = list(annotation.GetLeaderPointsAtIndex(0) or ())
    if len(points) < 6:
        raise RuntimeError(f"{what} leader is unreadable ({label})")
    actual = (float(points[-3]), float(points[-2]))
    error = math.dist(actual, leader_attach_xy)
    if error > tolerance:
        raise RuntimeError(
            f"{what} leader attachment moved ({label}): actual={actual}, "
            f"requested={leader_attach_xy}, error={error:.6g} m, "
            f"limit={tolerance:g} m"
        )


_ATTACHMENT_SELECT_TYPES = {
    "EDGE": _SEL_EDGE,
    "FACE": _SEL_FACE,
    "SILHOUETTE": _SEL_SILHOUETTE,
}


def _is_same_attachment(adapter: Any, attached: Any, entity: Any, kind: str) -> bool:
    """Whether ``attached`` is the ``kind`` entity an annotation was inserted on.

    ``ISldWorks::IsSame`` reads 1 for the model edge or face itself, and 0 for
    every silhouette, moved or not (probe 3 and run 20260928T081119688Z).  A
    silhouette is identified by its owning face instead: on the #1105 idprobe2
    leaves (20260928T085009031Z) ``ISilhouetteEdge::GetFace`` of the selected
    and of the attached silhouette passed IsSame on all 16 silhouette finishes
    and frames, and the drawing's ``IsSamePersistentID`` agreed.  A cylinder's
    two flank silhouettes share that face; the leader-landing check tells them
    apart.
    """
    if kind != "SILHOUETTE":
        return int(adapter.swApp.IsSame(attached, entity)) == 1
    selected_face = _early_bound(entity, "ISilhouetteEdge").GetFace()
    attached_face = _early_bound(attached, "ISilhouetteEdge").GetFace()
    if selected_face is None or attached_face is None:
        return False
    return int(adapter.swApp.IsSame(attached_face, selected_face)) == 1


def _assert_attached_to(
    adapter: Any,
    annotation: Any,
    entity: Any,
    *,
    entity_type: str,
    what: str,
    label: str,
    expected_leaders: int | None = 1,
) -> None:
    """Fail unless ``annotation`` is attached to exactly ``entity`` of the
    requested EDGE, FACE or SILHOUETTE type, with its required live leader
    proof (exact registered count by default, rendered ink for hole callouts).

    The count, type and entity readbacks must agree on one entity of that
    type -- ``IGtol.IsAttached`` and ``ISFSymbol.IsAttached`` keep reading
    True on a detached symbol -- and that entity must be ``entity`` by
    :func:`_is_same_attachment`.  A leader move re-solves the attachment:
    ``SetLeaderAttachmentPointAtIndex`` detached a feature-control frame
    (entities=0) on the #1105 platen_guide leaf.  A datum tag's triangle is
    not a leader (``GetLeaderCount`` reads 0 on every datum tag), so it
    passes ``expected_leaders=0``.
    Native hole callouts pass ``None``: display dimensions do not support
    SetLeader3 leaders, and their rendered leader ink is checked instead.
    The annotation count is still read, but is not the dimension's rendered
    leader authority. Generic symbols retain their exact-count requirement.
    """
    kind = entity_type.upper()
    if kind not in _ATTACHMENT_SELECT_TYPES:
        raise ValueError(f"{what} cannot verify a {kind} attachment ({label})")
    attached = tuple(annotation.GetAttachedEntities3() or ())
    count = int(annotation.GetAttachedEntityCount3())
    types = tuple(int(t) for t in (annotation.GetAttachedEntityTypes() or ()))
    leaders = int(annotation.GetLeaderCount())
    dangling = bool(annotation.IsDangling())
    one = (
        len(attached) == 1
        and count == 1
        and types == (_ATTACHMENT_SELECT_TYPES[kind],)
        and attached[0] is not None
    )
    same = one and _is_same_attachment(adapter, attached[0], entity, kind)
    if not same or dangling or leaders < 0 or (
        expected_leaders is not None and leaders != expected_leaders
    ):
        raise RuntimeError(
            f"{what} lost its {kind.lower()} attachment ({label}): "
            f"entities={len(attached)}, count={count}, types={types}, "
            f"same_entity={same}, dangling={dangling}, leaders={leaders}"
        )
    if expected_leaders is None:
        _assert_native_hole_callout_leader(adapter, annotation, label=label)


def _expected_pick(
    adapter: Any,
    selected: Any,
    expected: Any | None,
    *,
    entity_type: str,
    what: str,
    label: str,
) -> Any:
    """The entity an annotation must end up on: ``expected`` when the recipe
    named one, else what the pick returned.

    A named entity that was selected directly is ``selected`` itself. One
    named alongside a coordinate hit-test must BE what the hit-test resolved
    to (``_is_same_attachment``): a pick point where two lines meet returns
    whichever SolidWorks tests first, and every later readback then agrees
    on that wrong line, so the only proof is against an independently
    identified entity.
    """
    if expected is None:
        return selected
    if expected is not selected and not _is_same_attachment(
        adapter, selected, expected, entity_type.upper()
    ):
        raise RuntimeError(
            f"{what} pick resolved to a {entity_type.lower()} other than the "
            f"one named ({label}): the hit-test landed on a neighbour"
        )
    return expected


# swSelectType_e names for the kinds a drawing-view pick can resolve to; an
# unlisted code is reported as its number, never mapped to a guess.
_SELECT_TYPE_NAMES = {
    0: "NOTHING",
    1: "EDGE",
    2: "FACE",
    3: "VERTEX",
    9: "SKETCH",
    10: "SKETCHSEGMENT",
    11: "SKETCHPOINT",
    12: "DRAWINGVIEW",
    13: "GTOL",
    14: "DIMENSION",
    15: "NOTE",
    20: "COMPONENT",
    24: "EXTSKETCHSEGMENT",
    25: "EXTSKETCHPOINT",
    28: "CENTERMARKS",
    35: "SFSYMBOL",
    46: "SILHOUETTE",
    103: "CENTERLINE",
}


def _probe(
    bag: dict[str, Any], key: str, read: Callable[[], Any], *, record: bool = True
) -> Any:
    """Record ONE forensic read in ``bag`` -- its value, or its own failure.

    A description that cannot be read must say so under ``<key>_error`` and
    let the next read run: this executes on the success path of every hole
    callout (the BEFORE snapshot) and on the failure path after a refusal,
    and a diagnostic that raises there either fails a good sheet or masks the
    real failure.
    ``record=False`` keeps only the failure (for wrapper bindings, whose value
    is a COM object no telemetry channel can carry).
    """
    try:
        value = read()
    except Exception as exc:  # noqa: BLE001 - forensics never raise (see above)
        bag[f"{key}_error"] = f"{type(exc).__name__}: {exc}"
        return None
    if record:
        bag[key] = value
    return value


def _feature_identity(face: Any) -> str:
    """``<feature name>(<feature type>)`` of the feature that owns ``face``."""
    feature = _early_bound(face, "IFace2").GetFeature()
    if feature is None:
        return "<no feature>"
    feature = _early_bound(feature, "IFeature")
    return f"{feature.Name}({feature.GetTypeName2()})"


def describe_selected_entity(
    adapter: Any,
    view: Any,
    entity: Any,
    *,
    entity_type: str,
    requested_xy: tuple[float, float] | None,
    label: str,
) -> dict[str, Any]:
    """What a drawing-view pick actually resolved to, as scalar telemetry fields.

    The failure this exists for: ``AddHoleCallout2`` answered ``None`` to a
    coordinate pick that had succeeded (drawing:ch_rocker_arm, worker5,
    2026-09-20) and the leaf log could not say whether the selected EDGE was
    the hole rim, the strap arc 2.3 sheet-mm below it, or the hidden back-face
    rim under it. Recorded: the view (name, scale, position, outline), the
    requested sheet point, the selection set (count and every entry's
    ``swSelectType_e``), and for an edge its curve (circle centre/radius or
    line endpoints, model mm), its vertices and the feature owning each
    adjacent face -- which names the hole feature, or does not.

    Called only at the hole-callout boundary (:func:`add_native_hole_callout`),
    not on every pick: it is ~10 COM reads per call, and a generic pick has
    nothing to compare them against. Every read is guarded (:func:`_probe`);
    a value that could not be read is reported as ``<key>_error`` rather than
    raising. Values are scalars or JSON strings so they ride a span event, a
    log record and ``capture.json`` unchanged.
    """
    bag: dict[str, Any] = {
        "label": label,
        "entity_type": entity_type,
        "pick": "coordinate" if requested_xy is not None else "entity",
    }
    if requested_xy is not None:
        bag["requested_x"] = float(requested_xy[0])
        bag["requested_y"] = float(requested_xy[1])
    _probe(bag, "view_name", lambda: view_name(adapter, view))
    bound_view = _probe(bag, "view", lambda: _early_bound(view, "IView"), record=False)
    if bound_view is not None:
        _probe(bag, "view_scale", lambda: float(bound_view.ScaleDecimal))
        _probe(
            bag,
            "view_position",
            lambda: json.dumps([float(v) for v in bound_view.Position]),
        )
        _probe(
            bag,
            "view_outline",
            lambda: json.dumps([float(v) for v in bound_view.GetOutline()]),
        )
        _probe(
            bag,
            "model_to_view_transform",
            lambda: json.dumps(
                [
                    float(value)
                    for value in _early_bound(
                        bound_view.ModelToViewTransform, "IMathTransform"
                    ).ArrayData
                ]
            ),
        )
    selection_manager = _probe(
        bag,
        "selection_manager",
        lambda: _early_bound(adapter.currentModel.SelectionManager, "ISelectionMgr"),
        record=False,
    )
    count = None
    if selection_manager is not None:
        count = _probe(
            bag,
            "selected_count",
            lambda: int(selection_manager.GetSelectedObjectCount2(-1)),
        )
    if count:
        _probe(
            bag,
            "selected_types",
            lambda: json.dumps(
                [
                    _SELECT_TYPE_NAMES.get(code, code)
                    for code in (
                        int(selection_manager.GetSelectedObjectType3(index, -1))
                        for index in range(1, count + 1)
                    )
                ]
            ),
        )
        _probe(
            bag,
            "selection_point_model_m",
            lambda: json.dumps(
                [float(value) for value in selection_manager.GetSelectionPoint2(count, -1)]
            ),
        )
        _probe(
            bag,
            "selected_view_name",
            lambda: view_name(
                adapter, selection_manager.GetSelectedObjectsDrawingView2(count, -1)
            ),
        )
    kind = entity_type.upper()
    if kind == "SILHOUETTE":
        _probe(
            bag,
            "face_feature",
            lambda: _feature_identity(_early_bound(entity, "ISilhouetteEdge").GetFace()),
        )
        return bag
    if kind != "EDGE":
        return bag
    edge = _probe(bag, "edge", lambda: _early_bound(entity, "IEdge"), record=False)
    if edge is None:
        return bag
    curve = _probe(
        bag, "curve", lambda: _early_bound(edge.GetCurve(), "ICurve"), record=False
    )
    if curve is not None:
        if _probe(bag, "is_circle", lambda: bool(curve.IsCircle())):
            # CircleParams = (centre xyz, axis xyz, radius), metres -- ONE
            # property read, then sliced.
            params = _probe(
                bag, "circle_params", lambda: [float(v) for v in curve.CircleParams],
                record=False,
            )
            if params is not None:
                _probe(
                    bag,
                    "circle_mm",
                    lambda: json.dumps(
                        [round(v * 1000.0, 4) for v in params[:3]]
                        + [round(params[6] * 1000.0, 4)]
                    ),
                )
                _probe(bag, "circle_axis", lambda: json.dumps(params[3:6]))
        elif _probe(bag, "is_line", lambda: bool(curve.IsLine())):
            _probe(
                bag,
                "line_mm",
                lambda: json.dumps(
                    [
                        [
                            round(float(v) * 1000.0, 4)
                            for v in _early_bound(vertex, "IVertex").GetPoint()
                        ]
                        for vertex in (edge.GetStartVertex(), edge.GetEndVertex())
                    ]
                ),
            )
    _probe(
        bag,
        "adjacent_features",
        lambda: json.dumps(
            [
                _feature_identity(face)
                for face in (edge.GetTwoAdjacentFaces2() or ())
                if face is not None
            ]
        ),
    )
    return bag


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

    _select_view_entity(
        adapter, view, entity_type, None, label=label, entity=edge_entity
    )
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
    shoulder: bool = False,
    position_tolerance_m: float = 0.02,
    callout_below: str = "",
    expected_entity: Any | None = None,
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
    draw = adapter.currentModel
    if entity_type.upper() not in _ATTACHMENT_SELECT_TYPES:
        raise ValueError(
            f"feature-control frame cannot attach to a {entity_type} ({label})"
        )
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
        if selection_manager.SetSelectionPoint2(
            1, -1, leader_attach_xy[0], leader_attach_xy[1], 0.0
        ) is not True:
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
        "GetAttachedEntities3",
        "GetAttachedEntityTypes",
        "GetLeaderCount",
        "IsDangling",
        "GetLeaderPointsAtIndex",
    )
    if int(annotation.GetAttachedEntityCount3()) != 1:
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
    rebuild_drawing(adapter, label="add_feature_control_frame")
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
    if leader_attach_xy is not None:
        _assert_leader_lands(
            annotation, leader_attach_xy, what="feature-control frame", label=label
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
    char_height: float | None = None,
) -> Any:
    """Attach a native machining-required surface-finish symbol to an edge.

    ``entity_type`` widens a coordinate pick for entities that are not model
    edges — a revolve's flank lines are ``"SILHOUETTE"`` edges.  Pass a model
    ``edge_entity`` obtained from ``IView.GetVisibleEntities2`` when a small or
    overlapping projection makes coordinate selection ambiguous.

    ``leader_attach_xy`` is where the leader lands on that entity (sheet
    metres).  It becomes the selection point of the selected entity before
    insertion (``ISelectionMgr.SetSelectionPoint2``), so SolidWorks attaches
    the leader there.  Do not move the leader afterwards: on #1105's
    sfprobe farm leaves, ``SetLeaderAttachmentPointAtIndex`` dropped every
    symbol's attached entity (count 1 before the call, 0 after) while
    ``ISFSymbol.IsAttached`` still read True.  After the rebuild the symbol
    must be attached to exactly the selected entity, and a moved leader must
    end within 5 mm of ``leader_attach_xy``.
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
    if leader_attach_xy is not None:
        # Coordinates are sheet metres with z 0: the probe landed every
        # leader within 0.01 mm of the requested point this way.
        selection_manager = _early_bound(draw.SelectionManager, "ISelectionMgr")
        if selection_manager.SetSelectionPoint2(
            1, -1, leader_attach_xy[0], leader_attach_xy[1], 0.0
        ) is not True:
            raise RuntimeError(
                f"failed to set the surface-finish landing {leader_attach_xy} ({label})"
            )
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
        "GetTextFormat",
        "SetTextFormat",
        "GetAttachedEntityCount3",
        "GetAttachedEntities3",
        "GetAttachedEntityTypes",
        "GetLeaderCount",
        "IsDangling",
        "GetLeaderPointsAtIndex",
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
    if char_height is not None:
        # The symbol scales with its text: a smaller Ra reads as the routine
        # callout it is instead of a headline (default document height is
        # the dimension height; ~0.7 of it matches the sheet's note text).
        text_format = annotation.GetTextFormat(0)
        if text_format is None:
            raise RuntimeError(f"surface-finish symbol has no text format ({label})")
        text_format.CharHeight = float(char_height)
        if not annotation.SetTextFormat(0, False, text_format):
            raise RuntimeError(f"failed to set surface-finish text height ({label})")
    draw.ClearSelection2(True)
    rebuild_drawing(adapter, label="add_surface_finish")
    _assert_attached_to(
        adapter,
        annotation,
        selected_entity,
        entity_type=entity_type,
        what="surface-finish symbol",
        label=label,
    )
    if leader_attach_xy is not None:
        _assert_leader_lands(
            annotation, leader_attach_xy, what="surface-finish symbol", label=label
        )
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
    rebuild_drawing(adapter, label="add_view_centerline")
    return centerline


# The section cutting line is a GEOMETRIC DATUM, not annotation: the plane it
# defines is where every dimension taken off the section is measured, and a
# cut-face line carries that plane's own coordinate (which is what the part
# recipes pin dimensions to).  ``ISketchManager.CreateLine`` runs the new
# segment through the INFERENCE engine unless the sketch manager is in
# direct-to-DB mode, and sketch inference / automatic relations are
# APPLICATION-level preferences a seat carries from one leaf to the next
# (``diag_mcmaster_lib.SEAT_SKETCH_BASELINE`` restores all three ON), so an
# endpoint authored within snap distance of a view edge is pulled onto it --
# in SCREEN space, which makes the outcome depend on the seat's zoom rather
# than on this recipe.  A snap of a fraction of a millimetre on the sheet
# tilts the plane: top_frame's D-D was cut 4.29 degrees oblique, 0.674 mm off
# station at the rail face, by exactly that (leaf 2026-09-18T14:40Z).  Both
# mechanisms are shut off here, and the placement is then read back, because a
# preference the seat declines to write fails SILENTLY.
_SECTION_LINE_TOLERANCE_M = 1e-9


def _assert_section_line_placed(
    adapter: Any,
    segment: Any,
    points: list[tuple[float, ...]],
    *,
    label: str,
) -> None:
    """Read the created cutting line's endpoints back off the sketch.

    Suppression is not evidence.  Exactness is the right bar: nothing
    legitimately moves an endpoint authored in sketch coordinates, and the
    smallest snap observed on a seat is five orders of magnitude above this
    tolerance, so a real snap can never hide under it and float noise can
    never trip it.
    """
    line = _early_bound(segment, "ISketchLine")
    for expected, accessor, which in (
        (points[0], "GetStartPoint2", "start"),
        (points[1], "GetEndPoint2", "end"),
    ):
        raw = adapter._get_attr_or_call(line, accessor)
        if raw is None:
            raise RuntimeError(f"{label}: the section line has no {which} point")
        point = _early_bound(raw, "ISketchPoint")
        actual = tuple(
            float(adapter._get_attr_or_call(point, axis)) for axis in ("X", "Y", "Z")
        )
        drift = max(abs(a - b) for a, b in zip(actual, expected))
        if drift > _SECTION_LINE_TOLERANCE_M:
            raise RuntimeError(
                f"{label}: the section cutting line's {which} point sits "
                f"{drift * 1000.0:.4g} mm from where it was authored "
                f"({actual} instead of {expected}) -- sketch inference snapped "
                "it onto nearby geometry, so the cut plane is not the requested "
                "one and every dimension taken off the section would be "
                "measured on the wrong plane"
            )


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
    partial: bool = False,
    label: str,
) -> Any:
    """Create an unaligned section from one straight cutting-plane line.

    The public coordinates are drawing-sheet meters; convert them through the
    parent sketch's transform before CreateLine, which takes view-local sketch
    coordinates. Passing sheet coordinates directly offsets and scales the cut
    again (at 1:2, a centre cut can miss the part entirely).
    ``CreateLine`` is placed with the sketch manager in direct-to-DB mode and
    its endpoints are read back (:func:`_assert_section_line_placed`): an
    inferred endpoint snaps, and a snapped cutting line cuts an OBLIQUE plane.
    Direct-to-DB creation does not leave the new segment selected the way an
    inferred draw does, so it is selected explicitly for the
    ``CreateSectionViewAt5`` precondition.  The section is deliberately
    unaligned so a part recipe can place and scale it independently of the
    parent view.

    ``partial=True`` is the ASME removed section: the cutting line spans ONLY
    the feature of interest (one rail of a frame, not the whole plan), and
    with ``swCreateSectionView_Partial`` SolidWorks sections just that span
    instead of the full plane -- so a cut through a symmetric frame shows one
    T profile to dimension, not that profile and its unannotated twin 80 mm
    away. Without the flag a short line is the "olive, unhatched" failure the
    layout-tuning notes describe (the cut does not close); with it the line
    is allowed to stop inside the part. Pair it with
    ``IDrSection::SetDisplayOnlySurfaceCut`` (the recipes' cut-only mode) so
    nothing beyond the plane prints either.
    """
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    sketch_manager = _early_bound(draw.SketchManager, "ISketchManager")
    name = view_name(adapter, parent_view)
    if not ddoc.ActivateView(name):
        raise RuntimeError(f"failed to activate section parent view {name!r} ({label})")
    draw.ClearSelection2(True)
    parent = _early_bound(parent_view, "IView")
    sketch = _early_bound(parent.GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    math_utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    points = []
    for x, y in (line_start, line_end):
        point = _early_bound(
            math_utility.CreatePoint(double_array([float(x), float(y), 0.0])),
            "IMathPoint",
        )
        projected = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
        points.append(tuple(float(value) for value in projected.ArrayData))
    previous_add_to_db = bool(sketch_manager.AddToDB)
    sketch_manager.AddToDB = True
    try:
        segment = sketch_manager.CreateLine(*points[0], *points[1])
    finally:
        sketch_manager.AddToDB = previous_add_to_db
    if segment is None:
        raise RuntimeError(f"failed to create section line ({label})")
    _assert_section_line_placed(adapter, segment, points, label=label)
    selection_manager = _early_bound(draw.SelectionManager, "ISelectionMgr")
    selection_data = selection_manager.CreateSelectData()
    selection_data.View = parent_view
    selectable = _sw_type_info.early_bound_or_flag(
        segment, "ISketchSegment", "Select4"
    )
    if not selectable.Select4(False, selection_data):
        raise RuntimeError(f"failed to select the section line ({label})")
    selected = int(selection_manager.GetSelectedObjectCount2(-1))
    if selected != 1:
        raise RuntimeError(
            f"selecting the section line produced {selected} entities ({label})"
        )
    # swCreateSectionView_NotAligned | swCreateSectionView_ScaleWithModel
    # (| swCreateSectionView_Partial for a removed section).
    options = 0x1 | 0x8 | (0x10 if partial else 0)
    section = ddoc.CreateSectionViewAt5(
        float(view_xy[0]),
        float(view_xy[1]),
        0.0,
        section_label,
        options,
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
    rebuild_drawing(adapter, label="create_section_view")
    return section


def _projection_frame(adapter: Any, view: Any) -> tuple[Any, Any]:
    """The math utility and the view's CURRENT model-to-sheet transform, raw.

    Raw dispatches (``_common._com_invoke``): the generated wrapper would read
    type info and ``QueryInterface`` every object these calls return, which
    is most of what one projection used to cost (p50 71 ms, n=22,839 in 30 d)
    for five round trips of real work.  SolidWorks still does the product, so
    a projected point is the same number it always was.
    """
    utility = _com_invoke(adapter.swApp, "ISldWorks", "GetMathUtility")
    transform = _com_invoke(view, "IView", "ModelToViewTransform")
    return utility, transform


def _project_through(
    utility: Any, transform: Any, xyz: Sequence[float], *, label: str
) -> tuple[float, float]:
    model_point = _com_invoke(
        utility, "IMathUtility", "CreatePoint", double_array([float(v) for v in xyz])
    )
    if model_point is None:
        raise RuntimeError(f"failed to create model point ({label})")
    view_point = _com_invoke(model_point, "IMathPoint", "MultiplyTransform", transform)
    if view_point is None:
        raise RuntimeError(f"failed to project model point into view ({label})")
    coordinates = list(_com_invoke(view_point, "IMathPoint", "ArrayData") or ())
    if len(coordinates) < 2:
        raise RuntimeError(f"projected model point has no sheet coordinates ({label})")
    return (float(coordinates[0]), float(coordinates[1]))


@_telemetry.traced("drawing.model_point_projection", label_param="label")
def model_point_in_view(
    adapter: Any,
    view: Any,
    xyz: tuple[float, float, float],
    *,
    label: str,
) -> tuple[float, float]:
    """Project a model-space point into drawing-sheet coordinates.

    Five raw round trips.  A loop over one view's points projects through
    :func:`model_points_in_view` instead: one transform read and one span for
    the whole batch rather than one per point (up to 422 per trace).
    """
    utility, transform = _projection_frame(adapter, view)
    return _project_through(utility, transform, xyz, label=label)


@_telemetry.traced("drawing.model_point_projection", label_param="label")
def model_points_in_view(
    adapter: Any,
    view: Any,
    points: Sequence[Sequence[float]],
    *,
    label: str,
    names: Sequence[str] | None = None,
) -> list[tuple[float, float]]:
    """:func:`model_point_in_view` for many points of one view at one moment.

    The transform is read once, so nothing may move ``view`` between the
    points; three round trips per point after that.  ``names`` (one per
    point) identify a failing point in the error; its index, model point and
    the count projected before it are raised and set on the span either way.
    """
    if names is not None and len(names) != len(points):
        raise ValueError(f"{label}: {len(names)} names for {len(points)} points")
    _telemetry.annotate(points=len(points))
    utility, transform = _projection_frame(adapter, view)
    projected: list[tuple[float, float]] = []
    for index, xyz in enumerate(points):
        try:
            projected.append(_project_through(utility, transform, xyz, label=label))
        except Exception as exc:
            model = tuple(float(v) for v in xyz)
            point = names[index] if names is not None else f"point {index}"
            _telemetry.annotate(
                failed_index=index, failed_point=point, projected=len(projected)
            )
            raise RuntimeError(
                f"{label}: {point} (index {index} of {len(points)}) at model"
                f" {model} failed after {len(projected)} projected: {exc}"
            ) from exc
    _telemetry.annotate(projected=len(projected))
    return projected


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
    rebuild_drawing(adapter, label="add_property_linked_callout")
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
    attached_to: Any | None = None,
) -> Any:
    """Attach one literal arrowed note to a drawing-view entity.

    Provide EITHER ``entity_xy`` (a sheet-coordinate pick) OR ``entity`` (a
    precise model entity — for an offset/inclined rim whose projected edge has
    no stable sheet coordinate); ``_select_view_entity`` prefers ``entity``.
    ``attached_to`` is the identified model entity a sheet-point pick must
    resolve to: the pick sets where the arrow lands, and the build fails if
    it attached anything else.
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
        "GetAttachedEntities3",
        "GetAttachedEntityTypes",
        "IsDangling",
    )
    if int(annotation.GetAttachedEntityCount3()) != 1:
        if not annotation.SetAttachedEntities(dispatch_array([target])):
            raise RuntimeError(f"failed to attach note ({label})")
    status = annotation.SetLeader3(1, 0, True, False, False, False)
    if status != 0:
        raise RuntimeError(f"failed to create attached-note leader ({label}): {status}")
    if not annotation.SetPosition2(note_xy[0], note_xy[1], 0.0):
        raise RuntimeError(f"failed to position attached note ({label})")
    rebuild_drawing(adapter, label="add_attached_note")
    if (
        int(annotation.GetAttachedEntityCount3()) != 1
        or int(annotation.GetLeaderCount()) != 1
    ):
        raise RuntimeError(f"attached note lacks one arrow ({label})")
    if attached_to is not None:
        _assert_attached_to(
            adapter,
            annotation,
            attached_to,
            entity_type=entity_type,
            what="attached note",
            label=label,
        )
    draw.ClearSelection2(True)
    return note


def compose_hole_callout_prefix(process: str, existing: str) -> str:
    """The hole callout's prefix definition: ``process`` ahead of the native
    format text.  A process ending in a line break puts the native size on
    its own row; otherwise the two join with one space.  (Stripping the
    break put the post's whole size row on one 117 mm line: RD1 probe,
    917-s1-rd1probe.)"""
    separator = "\n" if process.rstrip(" ").endswith("\n") else " "
    return process.rstrip() + separator + existing.lstrip()


def _assert_native_hole_callout_leader(
    adapter: Any, annotation: Any, *, label: str
) -> None:
    """Require one printable arrow joined to the native callout's leader ink.

    GetLeaderCount reads zero on measured callouts despite visible leaders.
    Display data is the rendered authority, as in the layout audit, but this
    proof refuses every unreadable row rather than accepting a partial route.
    One arrow is the explicit one-edge callout contract, not an API-wide rule.
    """
    if int(annotation.Visible) != 1:  # swAnnotationVisibilityState_e.swAnnotationVisible
        raise RuntimeError(f"native hole callout is not visible ({label})")
    display = annotation.GetSpecificAnnotation()
    if display is None:
        raise RuntimeError(f"native hole callout has no display dimension ({label})")
    display = _sw_type_info.early_bound_or_flag(
        display, "IDisplayDimension", "IsHoleCallout", "GetAnnotation", "GetDisplayData"
    )
    owner = display.GetAnnotation()
    if not display.IsHoleCallout() or owner is None or int(
        adapter.swApp.IsSame(owner, annotation)
    ) != 1:
        raise RuntimeError(f"native hole callout lost its annotation ownership ({label})")
    data = display.GetDisplayData()
    if data is None:
        raise RuntimeError(f"native hole callout has no rendered data ({label})")
    data = _sw_type_info.early_bound_or_flag(
        data, "IDisplayData", "GetLineCount", "GetLineAtIndex2",
        "GetArrowHeadCount", "GetArrowHeadAtIndex2",
    )
    if int(data.GetArrowHeadCount()) != 1:
        raise RuntimeError(f"native hole callout has no single rendered arrow ({label})")
    raw_arrow = data.GetArrowHeadAtIndex2(0)
    if raw_arrow is None or len(raw_arrow) != 12:
        raise RuntimeError(f"native hole callout has unreadable rendered arrow ({label})")
    arrow = tuple(float(value) for value in raw_arrow)
    if (
        not all(math.isfinite(value) for value in arrow)
        or arrow[8] == 10  # swArrowStyle_e.swNO_ARROWHEAD; zero is a valid open arrow.
        or arrow[6] <= 0 or arrow[7] <= 0
        or math.hypot(arrow[3], arrow[4]) == 0
    ):
        raise RuntimeError(f"native hole callout has no printable rendered arrow ({label})")
    segments = []
    count = int(data.GetLineCount())
    if count <= 0:
        raise RuntimeError(f"native hole callout has no rendered leader lines ({label})")
    for index in range(count):
        raw = data.GetLineAtIndex2(index)
        if raw is None or len(raw) != 10:
            raise RuntimeError(f"native hole callout has unreadable rendered leader ({label})")
        values = tuple(float(value) for value in raw)
        if not all(math.isfinite(value) for value in values):
            raise RuntimeError(f"native hole callout has nonfinite rendered leader ({label})")
        start, end = values[4:6], values[7:9]
        if start != end:
            segments.append((start, end))
    # Arrow Z can differ from its line Z in native display data. Compare XY;
    # the line may also extend beyond the arrow tip toward the hole centre.
    if not any(
        _segment_distance(arrow[:2], start, end) <= _SILHOUETTE_POINT_TOLERANCE_M
        for start, end in segments
    ):
        raise RuntimeError(f"native hole callout has no connected rendered leader ({label})")


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

    ``edge=`` also requires the callout to remain attached to that native
    edge after insertion rebuild. Coordinate-only callers retain their hit-test
    contract. Recipes retaining an explicit edge must check the final print
    with :func:`assert_native_hole_callout_attachment` in ``settled_checks``.
    """
    try:
        selected = _select_view_entity(
            adapter, view, "EDGE", edge_xy, label=label, entity=edge
        )
    except Exception:
        if edge is not None:
            wanted = describe_selected_entity(
                adapter, view, edge, entity_type="EDGE", requested_xy=edge_xy, label=label
            )
            with contextlib.suppress(Exception):
                _telemetry.event("drawing.hole_callout_selection_failure", **wanted)
                _telemetry.error(
                    f"hole callout {label}: native edge selection failed: "
                    + json.dumps(wanted, default=str, sort_keys=True)
                )
        raise
    # Snapshot what AddHoleCallout2 is about to be handed, BEFORE the call: the
    # API may clear the selection or invalidate the entity, and on a passing
    # leaf this line is the positive control the failing one is read against.
    # DEBUG plus the span event: every record reaches OTLP/App Insights
    # regardless of console verbosity (the OTel handler sits at DEBUG; the
    # verbosity flag filters only stderr), so this is not a task.log line by
    # default. One record per callout. Emission is guarded: telemetry must
    # never fail a sheet (the console formatter prints only the message, hence
    # the JSON in it).
    before = describe_selected_entity(
        adapter, view, selected, entity_type="EDGE", requested_xy=edge_xy, label=label
    )
    with contextlib.suppress(Exception):
        _telemetry.event("drawing.hole_callout_selection", **before)
        _telemetry.debug(
            f"hole callout {label}: selected edge before AddHoleCallout2: "
            + json.dumps(before, default=str, sort_keys=True)
        )
    draw = adapter.currentModel
    ddoc = _early_bound(
        draw, "IDrawingDoc"
    )  # IDrawingDoc view for drawing-only methods (same dispatch)
    display = ddoc.AddHoleCallout2(callout_xy[0], callout_xy[1], 0.0)
    if display is None:
        # A None here says only "no callout": the seat is about to be torn down
        # with the drawing unsaved and the selection undescribed (rocker_arm,
        # worker5, 2026-09-20 -- "no forensic artefacts captured"). Describe the
        # selection again AFTER the refusal -- kept apart from the BEFORE
        # snapshot, never overwriting it, so a cleared selection or an
        # invalidated entity reads as what the API DID, not as what it was
        # given -- then let the capture save the sheet, the seat image,
        # SolidWorks' own error stack and the screen-space pick geometry
        # before raising. Only capture_com_failure raises; the console line
        # is guarded so a failed sink can neither replace the failure nor
        # prevent the capture.
        after = describe_selected_entity(
            adapter, view, selected, entity_type="EDGE", requested_xy=edge_xy, label=label
        )
        with contextlib.suppress(Exception):
            _telemetry.error(
                f"hole callout {label}: AddHoleCallout2 returned None at sheet "
                f"({callout_xy[0]:g}, {callout_xy[1]:g}); selection "
                + json.dumps(
                    {"before": before, "after": after}, default=str, sort_keys=True
                )
            )
        _seat_forensics.capture_com_failure(
            adapter,
            f"hole-callout {label}",
            f"failed to insert native hole callout ({label})",
            api="IDrawingDoc.AddHoleCallout2",
            callout_x=callout_xy[0],
            callout_y=callout_xy[1],
            **{f"before_{key}": value for key, value in before.items()},
            **{f"after_{key}": value for key, value in after.items()},
        )
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
        # Prefix the definition, not GetText(Prefix)'s resolved values: writing
        # resolved thread text severs its Hole Wizard variables. Native save /
        # reopen proof retains all five variables with PrefixDefinition (5).
        display = _sw_type_info.early_bound_or_flag(
            display, "IDisplayDimension", "SetText", "GetText"
        )
        existing = str(display.GetText(5) or "")  # swDimensionTextPrefixDefinition
        if not existing.strip():
            raise RuntimeError(f"hole callout has no format text to prefix ({label})")
        prefix = compose_hole_callout_prefix(process, existing)
        display.SetText(1, prefix)
        if str(display.GetText(5) or "") != prefix:
            raise RuntimeError(
                f"hole callout process prefix did not persist ({label}): "
                f"{display.GetText(5)!r}"
            )
        _telemetry.debug(f"hole callout {label}: prefix {prefix!r}")
    draw.ClearSelection2(True)
    rebuild_drawing(adapter, label="add_native_hole_callout")
    if edge is not None:
        current_annotation = display.GetAnnotation()
        if current_annotation is None:
            raise RuntimeError(f"native hole callout has no annotation ({label})")
        annotation = _sw_type_info.early_bound_or_flag(
            current_annotation,
            "IAnnotation",
            "GetPosition",
            "GetSpecificAnnotation",
            "GetAttachedEntities3",
            "GetAttachedEntityCount3",
            "GetAttachedEntityTypes",
            "GetLeaderCount",
            "IsDangling",
        )
        # Keep native attachment observations separate from successful
        # selection: AddHoleCallout2 can re-solve the annotation on insertion.
        # One aggregate record also retains the selected circle and current
        # transform, so a remote leaf can prove (or disprove) source ownership.
        attachment = dict(before)
        attachment["requested_callout_xy"] = json.dumps(callout_xy)
        _probe(
            attachment,
            "callout_position",
            lambda: json.dumps([float(value) for value in annotation.GetPosition()]),
        )
        attached = _probe(
            attachment,
            "attached_entities",
            lambda: tuple(annotation.GetAttachedEntities3() or ()),
            record=False,
        )
        _probe(
            attachment, "attached_count", lambda: int(annotation.GetAttachedEntityCount3())
        )
        _probe(
            attachment,
            "attached_types",
            lambda: json.dumps(
                [int(kind) for kind in (annotation.GetAttachedEntityTypes() or ())]
            ),
        )
        _probe(attachment, "leaders", lambda: int(annotation.GetLeaderCount()))
        _probe(attachment, "dangling", lambda: bool(annotation.IsDangling()))
        if attached is not None:
            attachment["attached_entities_count"] = len(attached)
            _probe(
                attachment,
                "attached_same_requested_edge",
                lambda: json.dumps(
                    [
                        _is_same_attachment(adapter, actual, edge, "EDGE")
                        for actual in attached
                    ]
                ),
            )
        with contextlib.suppress(Exception):
            _telemetry.event("drawing.hole_callout_attachment", **attachment)
            _telemetry.info(
                f"hole callout {label}: native attachment: "
                + json.dumps(attachment, default=str, sort_keys=True)
            )
        _assert_attached_to(
            adapter,
            annotation,
            edge,
            entity_type="EDGE",
            what="native hole callout",
            label=label,
            expected_leaders=None,
        )
    return display


def assert_native_hole_callout_attachment(
    adapter: Any,
    view: Any,
    display: Any,
    *,
    edge: Any,
    label: str,
) -> None:
    """Prove an explicit-edge callout from the current view's annotations.

    Run in ``finalize_drawing``'s ``settled_checks`` after the last rebuild.
    Re-enumerate the current sheet's views and the owning view's annotations:
    a removed callout or view can leave its old COM handle readable. Native
    ``IsSame == 1``, not Python wrapper identity, identifies both the view and
    display dimension; attachment readbacks come from the live annotation,
    never from the original handle's cached annotation.
    """
    current_views = [
        candidate
        for candidate in iter_views(adapter)
        if int(adapter.swApp.IsSame(candidate, view)) == 1
    ]
    if len(current_views) != 1:
        raise RuntimeError(
            f"native hole callout lost its owning view ({label}): "
            f"matching views={len(current_views)}"
        )
    current_view = _sw_type_info.early_bound_or_flag(
        current_views[0], "IView", "GetAnnotations"
    )
    matches = []
    for raw_annotation in current_view.GetAnnotations() or ():
        annotation = _sw_type_info.early_bound_or_flag(
            raw_annotation, "IAnnotation", "GetType", "GetSpecificAnnotation"
        )
        if int(annotation.GetType()) != _ANNOT_DIM:
            continue
        current_display = annotation.GetSpecificAnnotation()
        if current_display is not None and int(
            adapter.swApp.IsSame(current_display, display)
        ) == 1:
            matches.append((annotation, current_display))
    if len(matches) != 1:
        raise RuntimeError(
            f"native hole callout lost its current annotation ({label}): "
            f"matching dimensions={len(matches)}"
        )
    annotation, current_display = matches[0]
    current_display = _sw_type_info.early_bound_or_flag(
        current_display, "IDisplayDimension", "IsHoleCallout"
    )
    if not current_display.IsHoleCallout():
        raise RuntimeError(f"current annotation is not a native hole callout ({label})")
    annotation = _sw_type_info.early_bound_or_flag(
        annotation,
        "IAnnotation",
        "GetSpecificAnnotation",
        "GetAttachedEntities3",
        "GetAttachedEntityCount3",
        "GetAttachedEntityTypes",
        "GetLeaderCount",
        "IsDangling",
    )
    _assert_attached_to(
        adapter,
        annotation,
        edge,
        entity_type="EDGE",
        what="native hole callout",
        label=label,
        expected_leaders=None,
    )



@_telemetry.traced("drawing.hole_callout_precision", label_param="label")
def set_hole_callout_precision(
    display: Any, precision: Mapping[str, int], *, label: str
) -> None:
    """Set the decimals of named Hole Wizard length variables, natively.

    ``precision`` maps a callout variable name (``"hw-tapdrldepth"``,
    ``"hw-threaddepth"``) to its number of decimals. Per VARIABLE, because
    ``IDisplayDimension::SetPrecision3`` is per callout ("does not support
    setting the Primary ... values for hole callouts") and flattening the
    whole callout would cost the tap-drill DIAMETER its two places; every
    length token carries its own ``ICalloutLengthVariable::Precision``, so
    only the named ones change and each value stays the native variable.
    A blind depth printed ``16.00`` asks the shop for the .XX band; ``16.0``
    puts it under the general .X tolerance it actually needs.
    """
    from win32com.client.dynamic import Dispatch as dynamic_dispatch  # noqa: PLC0415

    remaining = dict(precision)
    for raw in display.GetHoleCalloutVariables() or ():
        name = str(dynamic_dispatch(raw._oleobj_).VariableName)
        decimals = remaining.pop(name, None)
        if decimals is None:
            continue
        length = _early_bound(raw, "ICalloutLengthVariable")
        length.Precision = int(decimals)
        if int(length.Precision) != int(decimals):
            raise RuntimeError(f"{label}: {name} precision did not persist")
    if remaining:
        raise RuntimeError(
            f"{label}: hole callout has no native variables {sorted(remaining)}"
        )


# The general-tolerance custom properties every part carries
# (_common.part_properties, from cad/config/title_block.yaml) and the drawing
# template's title block reads via $PRPSHEET. finalize_drawing requires them on
# the linked model so a stale part can't ship blank tolerance cells.
TITLE_BLOCK_TOLERANCE_PROPERTIES = (
    "TOL_LIN_X",
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
    # Edge-break and thread rows (2026-09 template): $PRPSHEET links, so a
    # source part that predates the stamp would print "REMOVE BURRS AND BREAK
    # SHARP EDGES  OR CHAMFER  MAX" -- fail loud instead.
    "TOL_EDGE_BREAK_R",
    "TOL_CHAMFER_MAX",
    "THREAD_TYPE",
    "THREAD_CLASS",
)
TITLE_BLOCK_REVISION_PROPERTY = "Revision"
# The copyright line's year ($PRPSHEET:{COPYRIGHT_YEAR}); required like the
# tolerance rows so a stale source model cannot print "(c)  Pedro ...".
TITLE_BLOCK_COPYRIGHT_PROPERTY = "COPYRIGHT_YEAR"
# Stamped on the drawing document itself at finalize (see _common._build_id).
DRAWING_BUILD_ID_PROPERTY = "BUILD_ID"


# ``IModelDoc2.IsOpenedViewOnly`` is True for two reasons (API remarks): the
# file is still loading ("Files are loaded using multi-threading ... Until all
# data and references are loaded, the file is in view-only mode ... many API
# queries return NULL or empty data"), or it was DELIBERATELY opened for
# viewing, which only the opener can ask for: ``swOpenDocOptions_ViewOnly``
# (0x4) on ``OpenDoc6``, or ``IDocumentSpecification.ViewOnly`` on
# ``OpenDoc7``. The build asks for neither. Every open passes ``OpenDoc6``
# options without 0x4 (``adapter.open_model`` passes 1, Silent), and
# ``test_failure_forensics`` holds every ``OpenDoc6``/``OpenDoc7`` call in
# cad/scripts and solidworks_mcp to that. So on any document the build opened,
# part or assembly, view-only means "still loading": an empty read waits for
# the flag to clear (bounded and logged), and is re-read once only when the
# document then says it is loaded -- never on a flag it cannot read.
_VIEW_ONLY_WAIT_S = 30.0
_VIEW_ONLY_POLL_S = 0.25


def _opened_view_only(model: Any) -> bool | None:
    """``IsOpenedViewOnly``, or ``None`` when the document gives no boolean."""
    try:
        value = _read_member(model, "IsOpenedViewOnly")
    except Exception:  # noqa: BLE001 - unreadable is "unknown", never a verdict
        return None
    return value if isinstance(value, bool) else None


def _await_document_loaded(model: Any) -> dict[str, Any]:
    """Wait for a view-only (still loading) document to finish loading.

    Returns the observation for the failure capture: ``view_only`` as first
    read; when it had to wait, ``view_only_wait_s`` and the final state; and
    ``loaded``, True only when the document's last answer was a definite
    ``IsOpenedViewOnly=False``.
    """
    view_only = _opened_view_only(model)
    load: dict[str, Any] = {"view_only": "unknown" if view_only is None else view_only}
    if view_only is True:
        _telemetry.info(
            "source document is still loading (IsOpenedViewOnly=True, and the build "
            "never opens view-only) with empty custom properties; waiting up to "
            f"{_VIEW_ONLY_WAIT_S:.0f}s for it to load"
        )
        begun = time.monotonic()
        while view_only is True and time.monotonic() - begun < _VIEW_ONLY_WAIT_S:
            time.sleep(_VIEW_ONLY_POLL_S)
            view_only = _opened_view_only(model)
            # One record per poll keeps the watchdog's idle clock (log records
            # are its heartbeat) from reading this wait as a wedged COM call.
            _telemetry.debug(
                f"source document load poll: IsOpenedViewOnly={view_only} after "
                f"{time.monotonic() - begun:.1f}s"
            )
        load["view_only_wait_s"] = round(time.monotonic() - begun, 2)
        load["view_only_after_wait"] = "unknown" if view_only is None else view_only
        _telemetry.info(
            f"source document view-only wait ended after {load['view_only_wait_s']:.1f}s "
            f"(IsOpenedViewOnly={load['view_only_after_wait']})"
        )
    load["loaded"] = view_only is False
    return load


def read_required_properties(
    model: Any, names: Sequence[str], *, required: Iterable[str]
) -> dict[str, str]:
    """The source document's file-level custom properties ``names``; raise when
    one of ``required`` is empty, or ``Revision`` is not the current release.

    An empty required value is re-read once, and only once the document itself
    reports it is loaded (``IsOpenedViewOnly=False``, after waiting out a load
    in progress; see ``_await_document_loaded``). The first read may have landed
    before a load that finished by the time the flag was asked, so a definite
    "loaded" earns a re-read; an unreadable flag does not. Still empty, the
    failure names the document, its configuration, both property APIs' answers
    and the seat's age and startup state
    (``_seat_forensics.capture_missing_properties``) before raising the same
    ``RuntimeError``.
    """
    required = tuple(required)

    def read() -> dict[str, str]:
        return {name: str(model.GetCustomInfoValue("", name) or "") for name in names}

    properties = read()
    missing = [name for name in required if not properties.get(name)]
    if missing:
        load = _await_document_loaded(model)
        if load["loaded"]:
            properties = read()
            missing = [name for name in required if not properties.get(name)]
        if missing:
            _seat_forensics.capture_missing_properties(
                model,
                f"source part properties are missing: {missing}",
                missing=missing,
                values=properties,
                load=load,
            )
        _telemetry.info("source part properties read after the document finished loading")
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
    layout: DrawingLayout,
    property_view: str | None = None,
    scale: tuple[float, float] = (1.0, 1.0),
    decimals: int = 2,
) -> tuple[Any, Any]:
    """Create a drawing from the selected hand-made project template.

    Each template embeds its own ASME B sheet format (title block, tolerance
    block, projection symbol), so there is no SetupSheet6 format re-apply; the
    only per-drawing knobs are the sheet scale (here) and WHICH view's model
    feeds the sheet's $PRPSHEET property links -- linked in finalize_drawing,
    once views exist (SolidWorks silently ignores a CustomPropertyView naming a
    view that does not exist yet, falling back to 'Default' = first view).
    ``property_view`` is accepted for compatibility and unused.
    """
    _ = property_view
    template = DRAWING_TEMPLATES[layout]
    if not template.path.is_file() or template.path.stat().st_size == 0:
        raise FileNotFoundError(f"project drawing standard is missing: {template.path}")

    draw = new_drawing(
        adapter,
        template=str(template.path),
        width=template.width_m,
        height=template.height_m,
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
        raise RuntimeError(
            f"failed to force drawing sheet to {scale[0]:g}:{scale[1]:g}"
        )
    assert_asme_b_sheet(
        adapter, sheet, layout=layout, phase="initial setup", scale=scale
    )
    # Normalize the viewport: sheet-coordinate picks (the hole-table datum
    # vertex / hole rims) hit-test with a PIXEL tolerance mapped through the
    # current zoom, and a hand-saved template opens at whatever zoom it was
    # saved with (the old generated one happened to be saved fit). Fit once so
    # coordinate picks are deterministic regardless of how the template binary
    # was last saved.
    draw.ViewZoomtofit2()
    draw.ForceRebuild3(False)
    rebuild_drawing(adapter, label="new_project_drawing")
    # The window every coordinate pick in this drawing hit-tests in, as fitted.
    _seat_forensics.record_drawing_display(adapter, f"new {layout.value} drawing")
    return draw, sheet


_LEADER_STRAIGHT = 1  # swLeaderStyle_e.swSTRAIGHT


_OWNER_DRAWING_VIEW = 0  # swAnnotationOwner_e.swAnnotationOwner_DrawingView
_OWNER_DRAWING_SHEET = 1  # swAnnotationOwner_e.swAnnotationOwner_DrawingSheet


@_telemetry.traced("drawing.leader_note", label_param="label")
def add_leader_note(
    adapter: Any,
    text: str,
    *,
    text_xy: tuple[float, float],
    attach_xy: tuple[float, float],
    label: str,
    view: Any = None,
    height: float | None = None,
) -> Any:
    """A free note with one straight leader whose tip sits at ``attach_xy``.

    Both points are sheet metres. The leader is a POINTER, not an attachment:
    it names what it touches (a face on a pictorial, a region of a view) and
    is not associated to any entity, which is what a face label wants -- a
    hidden-lines or scale change moves nothing. The tip is read back from
    ``GetLeaderPointsAtIndex`` so a leader SolidWorks quietly re-routed fails
    the build instead of pointing at the wrong face.

    With ``view`` the note is inserted while that view is active, so
    SolidWorks makes the VIEW its owner (``IAnnotation::OwnerType`` reads
    ``swAnnotationOwner_DrawingView``, proved here): it is listed by the
    view's ``GetAnnotations`` and moves with it, and the layout audit exempts
    a leader from the one view it is owned by -- a sheet-owned label whose
    leader ends ON a view reads as crossing it (12 findings on the priming
    sheet before this).

    ``SetLeaderAttachmentPointAtIndex`` is the right call HERE, unlike for
    surface-finish symbols and feature-control frames, which it detaches: a
    pointer note has no attached entity to lose (farm run
    20260928T080412049Z-77daa98fe5514439bd4ce684c6e19ec7 read
    GetAttachedEntityCount3 0 -> 0, one non-dangling leader, on all four
    cone-swing and crank-pinion notes).
    """
    draw = adapter.currentModel
    if view is not None:
        ddoc = _early_bound(draw, "IDrawingDoc")
        name = view_name(adapter, view)
        if not ddoc.ActivateView(name):
            raise RuntimeError(f"{label}: failed to activate view {name!r} for the note")
    note = add_note(adapter, text, *text_xy, height=height)
    if note is None:
        raise RuntimeError(f"{label}: failed to insert the note {text!r}")
    annotation = _sw_type_info.early_bound_or_flag(
        note.GetAnnotation(),
        "IAnnotation",
        "SetLeader3",
        "SetLeaderAttachmentPointAtIndex",
        "GetLeaderPointsAtIndex",
        "SetPosition2",
        "OwnerType",
    )
    if view is not None and int(annotation.OwnerType) != _OWNER_DRAWING_VIEW:
        raise RuntimeError(
            f"{label}: note is not owned by its view (OwnerType {int(annotation.OwnerType)})"
        )
    status = int(
        annotation.SetLeader3(_LEADER_STRAIGHT, _LEADER_SIDE_SMART, True, False, False, False)
    )
    if status != 0:
        raise RuntimeError(f"{label}: SetLeader3 refused a straight leader (status {status})")
    if not annotation.SetLeaderAttachmentPointAtIndex(0, attach_xy[0], attach_xy[1], 0.0):
        raise RuntimeError(f"{label}: failed to place the leader tip at {attach_xy}")
    if not annotation.SetPosition2(text_xy[0], text_xy[1], 0.0):
        raise RuntimeError(f"{label}: failed to position the note at {text_xy}")
    rebuild_drawing(adapter, label="add_leader_note")
    points = list(annotation.GetLeaderPointsAtIndex(0) or ())
    if len(points) < 6:
        raise RuntimeError(f"{label}: the note's leader is unreadable ({len(points)} values)")
    tip = (float(points[-3]), float(points[-2]))
    if math.dist(tip, attach_xy) > 0.001:
        raise RuntimeError(f"{label}: leader tip landed at {tip}, requested {attach_xy}")
    draw.ClearSelection2(True)
    return note


@dataclass(frozen=True)
class FaceLabel:
    """One face name on a pictorial: ``text`` at ``text_xy`` pointing at ``point_mm``."""

    text: str
    point_mm: tuple[float, float, float]
    text_xy: tuple[float, float]


@dataclass(frozen=True)
class PictorialView:
    """One octant view of the priming sheet.

    ``octant`` is the viewer octant ``(sx, sy, sz)`` from ``_named_views``;
    the part build must have named it. ``center_xy`` is the view centre on the
    sheet in metres; ``labels`` are the face names the view carries.
    """

    octant: tuple[int, int, int]
    center_xy: tuple[float, float]
    labels: tuple[FaceLabel, ...]


@_telemetry.traced("drawing.pictorial_sheet", label_param="label")
def place_pictorial_sheet(
    adapter: Any,
    model_path: str,
    views: Sequence[PictorialView],
    *,
    scale: tuple[float, float],
    label: str,
) -> list[Any]:
    """Place octant pictorials with leadered face names on the ACTIVE sheet.

    The priming sheet a print opens on: two isometrics from opposite octants
    (front-top-left and front-bottom-right show all six faces between them),
    each face named where the reader sees it, so the orthographic sheets that
    follow need no orientation key. Views are placed by the octant's model
    view name (``_named_views.octant_view_name``); the finalizer styles them
    Shaded With Edges and the post-export precision check covers them, the
    same as ``*Isometric``. Returns the ``IView`` objects in order.
    """
    from _named_views import octant_view_name  # noqa: PLC0415 -- part-side module

    placed = []
    for pictorial in views:
        view = place_view(
            adapter, model_path, octant_view_name(*pictorial.octant),
            *pictorial.center_xy, scale=scale,
        )
        set_hidden_lines_removed(adapter, view)
        for face in pictorial.labels:
            attach_xy = model_point_in_view(
                adapter, view, tuple(value / 1000.0 for value in face.point_mm),
                label=f"{label} {face.text} face",
            )
            add_leader_note(
                adapter, face.text, text_xy=face.text_xy, attach_xy=attach_xy,
                view=view, label=f"{label} {face.text} label",
            )
        placed.append(view)
    return placed


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


# IView::SetDisplayMode4 requires swSHADED plus its explicit Edges flag for
# "Shaded With Edges". Faceted=False selects precision geometry; the getter may
# report either swSHADED or the composite swSHADED_EDGES value after the write.
#
# GetFacettedHlrDisplay is NOT read back here. On a fresh view it is transient:
# it reads False for ~10 ms after the write, flips True ~50 ms later, and only
# settles False once SolidWorks first computes the view's display geometry —
# which nothing short of the export does (ForceRebuild3, EditRebuild3,
# IModelDocExtension.Rebuild, GraphicsRedraw2, UpdateViewDisplayGeometry and the
# zoom calls all leave it True; the PDF export clears it —
# `_frame_shading_idempotence_probe --fresh-view-compute`, 2026-09-15). Reading it
# here was a timing lottery (a slow getter under load read True and failed a
# correct view); `assert_precise_isometric_views` proves it after export instead.
_SW_SHADED = 3
_SW_SHADED_EDGES = 7


@_telemetry.traced("drawing.shaded_with_edges", label_param="label")
def set_high_quality_shaded_with_edges(adapter: Any, view: Any, *, label: str) -> None:
    """Set and verify a Shaded With Edges drawing view (precision proven post-export).

    ``SetDisplayMode4`` returns False when the view ALREADY reads the requested
    mode (frame_assembly sets its exploded isometric before the BOM/balloon
    pass, then ``finalize_drawing`` re-applies it: readback mode 3, edges True,
    use_parent False, no COM error -- 2026-09-17), so the setter's bool is not
    the proof. Only a COM exception is fatal here; the readback below is the
    contract either way.
    """
    _ok, error = adapter._attempt_with_error(
        lambda: view.SetDisplayMode4(False, _SW_SHADED, False, True, True)
    )
    if error is not None:
        raise RuntimeError(
            f"{label}: SetDisplayMode4 raised {error!r}"
        ) from error

    mode = adapter._attempt(lambda: view.GetDisplayMode2(), default=None)
    use_parent = adapter._attempt(lambda: view.GetUseParentDisplayMode(), default=None)
    edges = adapter._attempt(lambda: view.GetDisplayEdgesInShadedMode(), default=None)
    cosmetic_threads = adapter._attempt(lambda: view.GetCThreadQuality(), default=None)
    readback = {
        "mode": mode,
        "use_parent": use_parent,
        "edges": edges,
        "cosmetic_threads": cosmetic_threads,
    }
    if any(value is None for value in readback.values()):
        raise RuntimeError(f"{label}: incomplete display-mode readback {readback!r}")

    try:
        mode_value = int(mode)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"{label}: invalid display mode {mode!r}") from exc
    if (
        mode_value not in {_SW_SHADED, _SW_SHADED_EDGES}
        or bool(use_parent)
        or not bool(edges)
        or not bool(cosmetic_threads)
    ):
        raise RuntimeError(
            f"{label}: drawing view is not precise Shaded With Edges {readback!r}"
        )


@_telemetry.traced("drawing.assert_precise_isometrics")
def assert_precise_isometric_views(adapter: Any, sheet_names: Sequence[str]) -> int:
    """Fail unless every exported standard isometric reads precision geometry.

    Runs AFTER the PDF export, the only step that computes a fresh view's
    display geometry and settles ``GetFacettedHlrDisplay`` (see the note above
    ``set_high_quality_shaded_with_edges``), so the flag proves the geometry
    the PDF was cut from. Returns the number of isometric views checked.
    """
    ddoc = _early_bound(adapter.currentModel, "IDrawingDoc")
    checked = 0
    for sheet_name in sheet_names:
        if not ddoc.ActivateSheet(sheet_name):
            raise RuntimeError(
                f"failed to activate {sheet_name!r} for precision readback"
            )
        for view in iter_views(adapter):
            orientation = str(
                adapter._get_attr_or_call(view, "GetOrientationName") or ""
            )
            if not is_pictorial_orientation(orientation):
                continue
            faceted = adapter._attempt(view.GetFacettedHlrDisplay, default=None)
            if faceted is None or bool(faceted):
                raise RuntimeError(
                    f"{sheet_name} {view_name(adapter, view)!r}: exported isometric "
                    f"is not precision geometry (faceted={faceted!r})"
                )
            checked += 1
    return checked


_SW_HLV = 1  # swDisplayMode_e.swHIDDEN_GREYED
_SW_HLR = 2  # swDisplayMode_e.swHIDDEN


def set_hidden_lines_removed(adapter: Any, view: Any) -> None:
    """Remove the hidden edges from ``view`` -- the print's default.

    The mirror of ``set_hidden_lines_visible``, and idempotent for the same
    two reasons: ``SetDisplayMode4`` returns False for a same-mode set (a
    no-op, not a failure), so the RESULT is what gets asserted, and passing
    through the other mode makes the call a real regen -- an annotation
    attached after placement can leave a view's edge set unregenerated.
    """
    bound = _early_bound(view, "IView")
    bound.SetDisplayMode4(False, _SW_HLV, False, False, True)
    mode = int(bound.GetDisplayMode2())
    if mode != _SW_HLV:
        raise RuntimeError(
            f"failed to transition drawing view through HLV (mode reads {mode})"
        )
    bound.SetDisplayMode4(False, _SW_HLR, False, False, True)
    mode = int(bound.GetDisplayMode2())
    if mode != _SW_HLR:
        raise RuntimeError(
            f"failed to set hidden-lines-removed drawing view (mode reads {mode})"
        )


def set_hidden_lines_visible(adapter: Any, view: Any) -> None:
    """Show hidden edges (greyed) in ``view`` -- for a view whose job is to
    communicate internal/cross-drilled features.

    Always passes through HLR first. ``SetDisplayMode4`` returns False for a
    same-mode set (a no-op, not a failure), and a view already reading HLV can
    still export WITHOUT its dashed edges: an annotation attached to it after
    placement (rocker-arm-support's seat finish symbol, 2026-09-09) leaves the
    HLV edge set unregenerated and ``UpdateViewDisplayGeometry`` does not
    rebuild it — only a real mode change does. The toggle makes the call
    idempotent AND a regen, so recipes re-assert it after annotating a view.
    """
    bound = _early_bound(view, "IView")
    bound.SetDisplayMode4(False, _SW_HLR, False, False, True)
    mode = int(bound.GetDisplayMode2())
    if mode != _SW_HLR:
        raise RuntimeError(
            f"failed to transition drawing view through HLR (mode reads {mode})"
        )
    bound.SetDisplayMode4(False, _SW_HLV, False, False, True)
    mode = int(bound.GetDisplayMode2())
    if mode != _SW_HLV:
        raise RuntimeError(
            f"failed to set hidden-lines-visible drawing view (mode reads {mode})"
        )


# Assembly drawing view configurations (the user's ruling, 2026-09-27, widened
# 2026-09-28): at a small scale the modeled gear teeth and screw threads print
# as a black mass wherever edges are inked, so EVERY view at 1:2 or smaller
# whose display draws edges (wireframe, HLV, HLR, their faceted forms, and
# shaded-with-edges) references the source assembly's derived "Default
# Simplified" (_assembly.sync_simplified_configuration), whatever it carries:
# an exploded view shows that configuration's own explode (the builders author
# it there too), and a BOM or balloons bind to its components, whose BOM
# identity is their parent's (_drawing_simplified.child_bom_identity). Only a
# larger view, a pure SHADED one (tone, no edge ink) and the drawing's
# designated full-detail view keep the full-detail Default. Part drawings
# never call this.
ASSEMBLY_VIEW_CONFIGURATION = "Default"
SIMPLIFIED_VIEW_CONFIGURATION = simplified_name(ASSEMBLY_VIEW_CONFIGURATION)
SIMPLIFIED_MAX_SCALE = 0.5
_SW_DISPLAY_MODE_UNKNOWN = -1  # swDisplayMode_e.swDisplayModeUNKNOWN


class ViewRole(enum.Enum):
    """Whether an assembly view follows the scale policy or keeps full detail."""

    PLAIN = "plain"
    # The view that exists to show every modeled tooth and thread.
    FULL_DETAIL = "full-detail"


def view_configuration(
    scale: tuple[float, float], display_mode: int, role: ViewRole = ViewRole.PLAIN
) -> str:
    """The assembly configuration a drawing view references under the policy."""
    numerator, denominator = (float(value) for value in scale)
    if numerator <= 0.0 or denominator <= 0.0:
        raise ValueError(f"view scale must be positive, got {scale!r}")
    if display_mode == _SW_DISPLAY_MODE_UNKNOWN:
        raise ValueError("view display mode reads unknown; its edge ink cannot be judged")
    if (
        role is ViewRole.PLAIN
        and display_mode != _SW_SHADED
        and numerator / denominator <= SIMPLIFIED_MAX_SCALE + 1e-12
    ):
        return SIMPLIFIED_VIEW_CONFIGURATION
    return ASSEMBLY_VIEW_CONFIGURATION


@_telemetry.traced("drawing.view_configuration", label_param="label")
def apply_view_configuration(
    adapter: Any, view: Any, *, role: ViewRole = ViewRole.PLAIN, label: str
) -> str:
    """Point an assembly view at its policy configuration and read it back.

    Call once the view's scale and display mode are final and BEFORE anything
    attaches to its edges or components (dimensions, balloons, leaders, a
    BOM) or sets its exploded state (``set_view_exploded_state``): switching
    the configuration regenerates the view's geometry, and the explode shown
    is the referenced configuration's own. A pictorial view is judged
    shaded-with-edges, because ``finalize_drawing`` shades every one of them
    that way. A section or projected child follows its parent's configuration.
    """
    bound = _early_bound(view, "IView")
    scale = tuple(float(value) for value in bound.ScaleRatio)
    orientation = str(bound.GetOrientationName() or "")
    mode = (
        _SW_SHADED_EDGES
        if is_pictorial_orientation(orientation)
        else int(bound.GetDisplayMode2())
    )
    wanted = view_configuration(scale, mode, role)
    current = str(bound.ReferencedConfiguration)
    if current != wanted:
        bound.ReferencedConfiguration = wanted
        rebuild_drawing(adapter, label=f"{label} configuration")
        current = str(bound.ReferencedConfiguration)
        if current != wanted:
            raise RuntimeError(
                f"{label}: view references {current!r} after setting {wanted!r}"
            )
    _telemetry.annotate(
        configuration=wanted, scale=f"{scale[0]:g}:{scale[1]:g}", mode=mode, role=role.value
    )
    return wanted


@_telemetry.traced("drawing.exploded_state", label_param="label")
def set_view_exploded_state(
    adapter: Any, view: Any, show: bool, *, configuration: str, label: str
) -> None:
    """Explode or collapse an assembly view in its policy configuration.

    ``IView.ShowExploded`` shows the explode of the configuration the view
    references, so this runs AFTER ``apply_view_configuration`` and refuses a
    view that does not reference ``configuration`` (its return). An exploded
    view that already reads exploded (its configuration was just switched) is
    collapsed first, so the explode shown is regenerated from the referenced
    configuration's own steps. Both states are read back.
    """
    bound = _early_bound(view, "IView")
    current = str(bound.ReferencedConfiguration)
    if current != configuration:
        raise RuntimeError(
            f"{label}: set the exploded state after apply_view_configuration; the view "
            f"references {current!r}, not {configuration!r}"
        )
    if show and bool(bound.IsExploded()):
        bound.ShowExploded(False)
        if bool(bound.IsExploded()):
            raise RuntimeError(f"{label}: exploded view did not collapse before re-exploding")
    returned = bool(bound.ShowExploded(show))
    actual = bool(bound.IsExploded())
    if actual != show:
        raise RuntimeError(f"{label}: exploded-state readback is {actual}, expected {show}")
    if show and not returned:
        raise RuntimeError(f"{label}: ShowExploded returned false")
    if not adapter.currentModel.EditRebuild3():
        raise RuntimeError(f"{label}: exploded-state rebuild failed")
    after = str(bound.ReferencedConfiguration)
    if after != configuration:
        raise RuntimeError(
            f"{label}: view references {after!r} after its exploded state was set, "
            f"not {configuration!r}"
        )
    _telemetry.annotate(configuration=configuration, exploded=actual)


def assert_full_detail_view(adapter: Any, *, label: str) -> None:
    """Every assembly drawing keeps at least one full-detail (Default) view."""
    ddoc = _early_bound(adapter.currentModel, "IDrawingDoc")
    configurations = [
        str(_early_bound(raw_view, "IView").ReferencedConfiguration)
        for sheet_name in ddoc.GetSheetNames() or ()
        for raw_view in (_early_bound(ddoc.Sheet(str(sheet_name)), "ISheet").GetViews() or ())
    ]
    if ASSEMBLY_VIEW_CONFIGURATION not in configurations:
        raise RuntimeError(
            f"{label}: no view shows the full-detail {ASSEMBLY_VIEW_CONFIGURATION!r} "
            f"configuration ({configurations!r})"
        )
    _telemetry.annotate(
        views=len(configurations),
        simplified=configurations.count(SIMPLIFIED_VIEW_CONFIGURATION),
    )


def assert_asme_b_sheet(
    adapter: Any,
    sheet: Any,
    *,
    layout: DrawingLayout,
    phase: str,
    scale: tuple[float, float] = (1.0, 1.0),
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
    template = DRAWING_TEMPLATES[layout]
    if (
        abs(properties[5] - template.width_m) > 1e-6
        or abs(properties[6] - template.height_m) > 1e-6
    ):
        raise RuntimeError(
            f"{phase}: drawing sheet is not {layout.value} ASME B size: {properties!r}"
        )


def _contact_preview_grid(page_count: int) -> tuple[int, int]:
    """Return the contact-preview column/row count for a multi-sheet drawing."""
    if page_count < 2:
        raise ValueError(f"contact preview requires at least 2 pages, got {page_count}")
    if page_count <= 4:
        return (2, 2)
    columns = math.ceil(math.sqrt(page_count))
    return (columns, math.ceil(page_count / columns))


@_telemetry.traced("drawing.render_png")
def render_pdf_png(
    pdf: Path,
    png: Path,
    *,
    layout: DrawingLayout,
    expected_pages: int = 1,
    page_layouts: Sequence[DrawingLayout] | None = None,
) -> None:
    """Render a drawing PDF to its preview PNG.

    Single-sheet drawings retain a one-page 300 dpi preview. Multi-sheet
    drawings use the registered preview path for a contact sheet, keeping the
    doit/cache/release artifact contract to one PNG. The historical 2x2 layout
    is retained through four pages; larger drawings use the smallest near-square
    grid that fits every page. Mixed packages validate and render each PDF page
    against its own registered ASME B orientation without stretching the contact
    preview.
    """
    if page_layouts is None:
        layouts = (layout,) * expected_pages
    else:
        layouts = tuple(page_layouts)
        if len(layouts) != expected_pages:
            raise ValueError(
                f"page layout count {len(layouts)} != expected pages {expected_pages}"
            )
        if any(not isinstance(item, DrawingLayout) for item in layouts):
            raise TypeError("every page layout must be a DrawingLayout")
    import pypdfium2 as pdfium
    from PIL import Image

    contact_template = DRAWING_TEMPLATES[layout]
    document = pdfium.PdfDocument(str(pdf))
    if len(document) != expected_pages:
        raise RuntimeError(
            f"drawing PDF has {len(document)} pages, expected {expected_pages}"
        )
    images: list[Any] = []
    for index, page_layout in enumerate(layouts):
        page = document[index]
        page_template = DRAWING_TEMPLATES[page_layout]
        expected_points = (
            page_template.width_m / 0.0254 * 72.0,
            page_template.height_m / 0.0254 * 72.0,
        )
        actual_points = (float(page.get_width()), float(page.get_height()))
        point_tolerance = 72.0 / page_template.dpi + 1e-6
        if any(
            abs(actual - expected) > point_tolerance
            for actual, expected in zip(actual_points, expected_points, strict=True)
        ):
            document.close()
            raise RuntimeError(
                f"PDF page {index + 1} is {actual_points[0]:g} x "
                f"{actual_points[1]:g} pt, expected {expected_points[0]:g} x "
                f"{expected_points[1]:g} pt for {page_layout.value}"
            )
        image = page.render(scale=page_template.dpi / 72.0).to_pil()
        page.close()
        expected_width, expected_height = page_template.pixel_size
        actual_width, actual_height = image.size
        if (
            actual_width in (expected_width, expected_width + 1)
            and actual_height in (expected_height, expected_height + 1)
            and image.size != page_template.pixel_size
        ):
            image = image.crop((0, 0, expected_width, expected_height))
        if image.size != page_template.pixel_size:
            document.close()
            raise RuntimeError(
                f"{page_layout.value} ASME B PNG page {index + 1} is {image.size}, "
                f"expected {page_template.pixel_size}"
            )
        images.append(image)
    document.close()
    png.parent.mkdir(parents=True, exist_ok=True)
    if expected_pages == 1:
        images[0].save(png, dpi=(contact_template.dpi, contact_template.dpi))
        return

    columns, rows = _contact_preview_grid(expected_pages)
    cell_size = (
        contact_template.pixel_size[0] // columns,
        contact_template.pixel_size[1] // rows,
    )
    contact = Image.new("RGB", contact_template.pixel_size, "white")
    for index, image in enumerate(images):
        scale = min(cell_size[0] / image.width, cell_size[1] / image.height)
        preview_size = (
            round(image.width * scale),
            round(image.height * scale),
        )
        cell = image.resize(preview_size, Image.Resampling.LANCZOS)
        column = index % columns
        row = index // columns
        x = column * cell_size[0] + (cell_size[0] - preview_size[0]) // 2
        y = row * cell_size[1] + (cell_size[1] - preview_size[1]) // 2
        contact.paste(cell.convert("RGB"), (x, y))
    contact.save(png, dpi=(contact_template.dpi, contact_template.dpi))


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
        rebuild_drawing(adapter, label="add_hole_group_tags")
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
    rebuild_drawing(adapter, label="delete_unnamed_imports")
    return survivors


def _feature_by_dimension_name(
    dimensions_by_feature: Mapping[str, Iterable[str]],
) -> dict[str, str]:
    """Invert a part spec's ``DRAWING_DIMENSIONS`` to ``{dimension: feature}``.

    ``_common.name_dimensions`` names a dimension per OWNING feature, so the
    inverse is total and unambiguous by construction.  A name claimed by two
    features is a spec bug, not a runtime condition — it would make the
    targeted import silently depend on feature order — so it raises here.
    """
    owner: dict[str, str] = {}
    for feature, names in dimensions_by_feature.items():
        for name in names:
            previous = owner.setdefault(name, feature)
            if previous != feature:
                raise ValueError(
                    f"dimension {name!r} is claimed by features {previous!r} and "
                    f"{feature!r}; parametric names are feature-unique"
                )
    return owner


def _features_owning(
    dimensions_by_feature: Mapping[str, Iterable[str]],
    keep: Iterable[str],
    *,
    view_label: str,
) -> tuple[str, ...]:
    """Name, sorted, the features whose marked dimensions cover ``keep``."""
    owner = _feature_by_dimension_name(dimensions_by_feature)
    unknown = sorted(name for name in keep if name not in owner)
    if unknown:
        raise RuntimeError(
            f"{view_label} view keeps dimensions no feature declares: {unknown}; "
            f"declared={sorted(owner)}"
        )
    return tuple(sorted({owner[name] for name in keep}))


def _drawing_component_name(adapter: Any, view: Any) -> str:
    """Name of the model instance a drawing view shows, e.g. ``"fr-tube-frame-2"``.

    ``SelectByID2`` wants it as the middle qualifier of a model item's name, and
    it is NOT derivable from the part's file name: SolidWorks numbers one
    instance per view (``fr-tube-frame-1`` in the first view, ``-2`` in the
    second), so it is read back per view from
    ``IView::RootDrawingComponent2`` — ``InChildContext=False`` for this view's
    own root component — rather than guessed.
    """
    root = _early_bound(view, "IView").RootDrawingComponent2(False)
    name = _early_bound(root, "IDrawingComponent").Name if root else None
    if not isinstance(name, str) or not name:
        raise RuntimeError(
            f"drawing view {view_name(adapter, view)!r} has no root drawing "
            f"component to qualify model feature names with: {name!r}"
        )
    return name


def _model_item_paths(adapter: Any, view: Any) -> tuple[tuple[str, str], ...]:
    """The ``@component@view`` qualifiers a model item of ``view`` answers to.

    A projected view can answer to its own name.  A derived view may require
    its base view's qualifier.  On top-frame's Section View A-A, every form of
    ``"CapRecessProfile@fr-top-frame-7@Section View A-A"`` with SKETCH,
    BODYFEATURE, "" and SOLIDBODY refuses -- for instance suffixes 1..20
    (``RootDrawingComponent2(True)`` reads 'top-frame-16', which refuses too)
    and for the sheet-qualified view name -- while the section itself selects
    fine as a DRAWINGVIEW and the same two features resolve through its BASE
    view, whose component name it happens to share.

    Naming a feature through the base view does NOT import into the base view:
    ``InsertModelAnnotations3`` follows the SELECTED drawing view, so with the
    section selected the section is what gains the dimensions (measured: A-A's
    census gained a second CapRecessDepth and CapRecessDia, the base view
    gained none).  The base-view chain is therefore walked as a fallback, each
    name paired with the component name THAT view reports (SolidWorks numbers
    one instance per view), and the first qualifier that resolves wins.
    """
    paths = [(_drawing_component_name(adapter, view), view_name(adapter, view))]
    seen = {paths[0][1]}
    base = _early_bound(view, "IView").GetBaseView()
    while base is not None:
        base = _early_bound(base, "IView")
        name = view_name(adapter, base)
        if name in seen:
            break
        seen.add(name)
        paths.append((_drawing_component_name(adapter, base), name))
        base = base.GetBaseView()
    return tuple(paths)


def _select_model_feature(
    adapter: Any, feature: str, *, paths: Sequence[tuple[str, str]]
) -> str:
    """Append one model feature of a drawing view to the selection list.

    A feature is addressed from the drawing as
    ``"<feature>@<drawing component>@<view>"`` — the form
    ``IModelDocExtension::SelectByID2`` documents for model items seen through a
    view (``"Sketch1@model-7@Drawing View1"``, from the "Reset Visibility of
    Sketches in Drawing View" example).  The Type filter must name the real
    kind: a driving dimension's owner is usually a profile ``"SKETCH"`` but can
    be a ``"BODYFEATURE"`` (an extrude, a chamfer, a fillet), and an empty Type
    resolves NEITHER here, so both are tried and the winner is returned.

    ``paths`` are :func:`_model_item_paths`' qualifiers, the view's own first
    and then its base views', as measured for top-frame's section.
    """
    draw = adapter.currentModel
    for component, in_view in paths:
        for type_name in ("SKETCH", "BODYFEATURE"):
            if draw.Extension.SelectByID2(
                f"{feature}@{component}@{in_view}",
                type_name,
                0.0,
                0.0,
                0.0,
                True,  # append: the view itself is already selected
                0,
                null_callout(),
                0,
            ):
                return f"{type_name} via {in_view}"
    raise RuntimeError(
        f"failed to select model feature {feature!r} as a SKETCH or a "
        "BODYFEATURE through any of "
        f"{[f'{feature}@{component}@{in_view}' for component, in_view in paths]}"
    )


def _model_item_read(operation: Callable[[], Any]) -> Any:
    try:
        return operation()
    except Exception as exc:  # diagnostic failure, not an empty observation
        return {"read_error": f"{type(exc).__name__}: {exc}"}


def _model_item_feature_identity(raw: Any) -> dict[str, Any] | None:
    if raw is None:
        return None
    feature = _early_bound(raw, "IFeature")
    return {
        "name": feature.Name,
        "id": int(feature.GetID()),
        "type": str(feature.GetTypeName2()),
    }


def _model_item_dimension_identity(raw: Any) -> dict[str, Any] | None:
    if raw is None:
        return None
    dimension = _early_bound(raw, "IDimension")
    return {
        "full_name": dimension.FullName,
        "feature_owner": _model_item_feature_identity(dimension.GetFeatureOwner()),
    }


def _model_item_annotation_identity(raw: Any) -> dict[str, Any]:
    annotation = _early_bound(raw, "IAnnotation")
    kind = int(annotation.GetType())
    owner_type = int(annotation.OwnerType)
    record = {
        "name": annotation.GetName(),
        "type": kind,
        "visible": int(annotation.Visible),
        "owner_type": owner_type,
    }
    if owner_type == 0:  # swAnnotationOwner_DrawingView
        owner = annotation.Owner
        record["owner_view"] = (
            _early_bound(owner, "IView").GetName2() if owner is not None else None
        )
    if kind == 4:  # swDisplayDimension
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        record["dimension"] = _model_item_dimension_identity(display.GetDimension2(0))
    return record


def _model_item_view_identity(raw: Any) -> dict[str, Any] | None:
    if raw is None:
        return None
    view = _early_bound(raw, "IView")
    record = {
        "name": _model_item_read(view.GetName2),
        "configuration": _model_item_read(lambda: view.ReferencedConfiguration),
    }
    referenced = _model_item_read(lambda: view.ReferencedDocument)
    # The SDK documents an empty reference for section views, not a part.
    if referenced is None or isinstance(referenced, (str, dict)):
        record["source_document"] = referenced
    else:
        model = _model_item_read(lambda: _early_bound(referenced, "IModelDoc2"))
        if isinstance(model, dict):
            record["source_document"] = model
        else:
            record["source_document"] = _model_item_read(model.GetPathName)
            record["source_type"] = _model_item_read(lambda: int(model.GetType()))
    return record


def record_model_item_import(observation: Mapping[str, Any]) -> None:
    """Read-only observer for a caller's native import, including empty returns.

    Inspect only the requested selections and the target/base-view chain.
    Failed diagnostic reads are explicit, never evidence of an empty census.
    This does not alter selections, import options, or the caller's refusal.
    """
    adapter = observation["adapter"]
    view = _early_bound(observation["view"], "IView")
    phase = observation["phase"]
    requested = observation["requested_dimensions"]
    limit = len(requested) + 1  # the requested ink plus a native view label
    report: dict[str, Any] = {
        "caller": observation["caller"],
        "phase": phase,
        "requested_view": observation["view_name"],
        "features": list(observation["features"]),
        "qualifiers": list(observation["paths"]),
        "selected_paths": list(observation.get("types", ())),
    }

    measure = _model_item_read

    drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
    report["active_view"] = measure(
        lambda: _model_item_view_identity(drawing.ActiveDrawingView)
    )
    manager = _early_bound(adapter.currentModel.SelectionManager, "ISelectionMgr")
    count = measure(lambda: int(manager.GetSelectedObjectCount2(-1)))
    report["selection_count"] = count
    if type(count) is int:
        selections = []
        for index in range(1, min(count, len(observation["features"]) + 1) + 1):
            kind = measure(lambda i=index: int(manager.GetSelectedObjectType3(i, -1)))
            item = {
                "index": index,
                "type": kind,
                "view": measure(
                    lambda i=index: _model_item_view_identity(
                        manager.GetSelectedObjectsDrawingView2(i, -1)
                    )
                ),
            }
            if kind in (9, 22):  # swSelSKETCHES, swSelBODYFEATURES return IFeature
                item["feature"] = measure(
                    lambda i=index: _model_item_feature_identity(
                        manager.GetSelectedObject6(i, -1)
                    )
                )
            elif kind == 12:  # swSelDRAWINGVIEWS returns IView
                item["selected_view"] = measure(
                    lambda i=index: _model_item_view_identity(
                        manager.GetSelectedObject6(i, -1)
                    )
                )
            selections.append(item)
        report["selections"] = selections
        report["uninspected_selections"] = count - len(selections)

    if phase != "view_selected":
        states = []
        seen: set[str] = set()
        current = view
        while current is not None:
            name = measure(current.GetName2)
            if not isinstance(name, str):
                report["view_name_read"] = name
                break
            if name in seen:
                break
            seen.add(name)
            state = {"view": measure(lambda v=current: _model_item_view_identity(v))}
            annotations = measure(lambda v=current: tuple(v.GetAnnotations() or ()))
            if isinstance(annotations, tuple):
                state["annotation_count"] = len(annotations)
                state["annotations"] = [
                    measure(lambda a=a: _model_item_annotation_identity(a))
                    for a in annotations[:limit]
                ]
                state["uninspected_annotations"] = max(0, len(annotations) - limit)
            else:
                state["annotations"] = annotations
            states.append(state)
            base = measure(current.GetBaseView)
            if isinstance(base, dict):
                report["base_view_read"] = base
                break
            current = _early_bound(base, "IView") if base is not None else None
        report["view_annotations"] = states

    if phase == "before":
        referenced = measure(lambda: view.ReferencedDocument)
        if isinstance(referenced, dict):
            report["source_document_read"] = referenced
        elif referenced is not None and not isinstance(referenced, str):
            model = measure(lambda: _early_bound(referenced, "IModelDoc2"))
            if isinstance(model, dict):
                report["source_model_read"] = model
            else:
                doc_type = measure(lambda: int(model.GetType()))
                report["source_type_read"] = doc_type
                if doc_type == 1:  # swDocPART
                    part = measure(lambda: _early_bound(referenced, "IPartDoc"))
                    if isinstance(part, dict):
                        report["source_features_read"] = part
                    else:
                        report["source_features"] = {
                            feature: measure(
                                lambda f=feature: _model_item_feature_identity(
                                    part.FeatureByName(f)
                                )
                            )
                            for feature in observation["features"]
                        }
                        report["source_dimensions"] = {
                            f"{name}@{feature}": measure(
                                lambda f=feature, n=name: _model_item_dimension_identity(
                                    model.Parameter(f"{n}@{f}")
                                )
                            )
                            for feature, name in requested
                        }
    if phase == "after":
        result = observation["result"]
        report["native_result_type"] = type(result).__name__
        report["native_exception"] = observation["native_exception"]
        if result is None or isinstance(result, str):
            report["native_result_value"] = result
        else:
            report["native_result_count"] = measure(lambda: len(result))
            report["native_annotations"] = measure(
                lambda: [
                    measure(lambda a=a: _model_item_annotation_identity(a))
                    for a in result[:limit]
                ]
            )
        report["native_arguments"] = observation["native_arguments"]
    data = json.dumps(report, sort_keys=True)
    _telemetry.event(
        "drawing.model_item_import_observation",
        caller=observation["caller"],
        phase=phase,
        requested_view=observation["view_name"],
        observation=data,
    )
    _telemetry.info(f"model-item import observation: {data}")


@_telemetry.traced("drawing.targeted_model_items")
def insert_feature_dimensions(
    adapter: Any,
    view: Any,
    features: Sequence[str],
    *,
    observer: Callable[[Mapping[str, Any]], None] | None = None,
) -> list[tuple[str, Any]]:
    """Import only ``features``' marked dimensions into ``view``.

    ``InsertModelAnnotations3`` imports for the current SELECTION, so selecting
    the view plus the owning features and passing ``swImportModelItemsSource_e``
    ``swImportModelItemsFromSelectedFeature`` (1) rather than
    ``swImportModelItemsFromEntireModel`` (0) delivers exactly the recipe's ink
    — no whole-model marked set to select and ``EditDelete`` afterwards.  The
    mask still applies: the selected-feature import honours
    ``swInsertDimensionsMarkedForDrawing``.

    The selection list is the whole contract, and it is asymmetric: the view
    goes in FIRST (the method "inserts model annotations into this drawing
    document's currently selected drawing view") and every feature is APPENDED
    to it.  With the features alone selected the call silently imports nothing —
    it returns an empty array and no annotation reaches any view — and Option 2
    (``swImportModelItemsFromSelectedComponent``, which the pre-2008-SP3 help
    mislabelled "selected feature") imports nothing either way.  All of that is
    measured on tube-frame by ``diagnostics/probe_targeted_model_items.py``.
    Every feature rides in ONE selection list and ONE import call.

    Returns ``(parametric name, annotation)`` pairs — the import already reads
    every name to log what arrived, so handing them back spares the caller a
    second ``IDimension::Name`` walk over the same annotations.  An annotation
    that is not a model dimension pairs with ``""``.

    ``observer`` receives read-only context while the native selection still
    exists: after selecting the view, before import, and after the native
    return (or exception).  It is opt-in for a failing caller and its positive
    controls; ordinary imports incur no additional native diagnostic reads.
    """
    draw = adapter.currentModel
    ddoc = _early_bound(
        draw, "IDrawingDoc"
    )  # IDrawingDoc view for drawing-only methods (same dispatch)
    name = view_name(adapter, view)
    if not ddoc.ActivateView(name):
        raise RuntimeError(f"failed to activate drawing view {name!r}")
    draw.ClearSelection2(True)
    if not draw.Extension.SelectByID2(
        name, "DRAWINGVIEW", 0.0, 0.0, 0.0, False, 0, null_callout(), 0
    ):
        raise RuntimeError(f"failed to select drawing view {name!r}")
    paths = _model_item_paths(adapter, view)

    def observe(phase: str, **details: Any) -> None:
        if observer is None:
            return
        try:
            observer(
                {
                    "adapter": adapter,
                    "view": view,
                    "view_name": name,
                    "features": features,
                    "paths": paths,
                    "phase": phase,
                    **details,
                }
            )
        except Exception as exc:  # telemetry must not replace native acceptance
            _telemetry.event(
                "drawing.model_item_import_observer_failed",
                requested_view=name,
                phase=phase,
                read_error=f"{type(exc).__name__}: {exc}",
                native_result_type=type(details.get("result")).__name__,
                native_exception=repr(details.get("native_exception")),
            )
            _telemetry.warn(
                f"model-item import observer {name} ({phase}) failed: "
                f"{type(exc).__name__}: {exc}; "
                f"native_exception={details.get('native_exception')!r}"
            )

    observe("view_selected")
    types = [
        _select_model_feature(adapter, feature, paths=paths)
        for feature in features
    ]
    native_arguments = (
        1,  # swImportModelItemsFromSelectedFeature
        _INSERT_DIMS_MARKED | _INSERT_HOLE_WIZARD_LOCATION_DIMS,
        False,
        True,
        True,
        False,
    )
    native_exception = None

    def import_items() -> Any:
        nonlocal native_exception
        try:
            return ddoc.InsertModelAnnotations3(*native_arguments)
        except Exception as exc:
            native_exception = {
                "type": type(exc).__name__,
                "message": str(exc),
                "hresult": getattr(exc, "hresult", None),
                "excepinfo": repr(getattr(exc, "excepinfo", None)),
                "args": repr(exc.args),
            }
            raise  # preserve _attempt's existing exception/null policy

    observe("before", types=types)
    result = adapter._attempt(import_items)
    observe(
        "after",
        types=types,
        result=result,
        native_exception=native_exception,
        native_arguments=native_arguments,
    )
    draw.ClearSelection2(True)
    if not result or isinstance(result, str):
        return []
    named = [
        (dimension_name(adapter, annotation), annotation)
        for annotation in (
            _sw_type_info.early_bound_or_flag(
                annotation, "IAnnotation", "GetSpecificAnnotation"
            )
            for annotation in result
        )
    ]
    _telemetry.info(
        f"targeted model-item import {name}: "
        f"features={[f'{f}[{t}]' for f, t in zip(features, types, strict=True)]}, "
        f"annotations={len(named)}, "
        f"dimensions={sorted(item for item, _ in named if item)}"
    )
    return named


def _curate_entire_model_import(
    adapter: Any,
    view: Any,
    *,
    keep: dict[str, tuple[float, float]],
    view_label: str,
) -> list[Any]:
    """Fallback: import the whole model's marked set, then delete the rest."""
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


# How far a kept dimension may read back from its requested sheet point before
# it is placed again.  SetPosition + EditRebuild3 leaves an unmoved survivor
# exactly on its point (all 17 curate passes on the step-snapshot leaves read
# back equal at 1e-6 m); the two real shifts were 6.97 mm and 0.63 mm.
_REPOSITION_DRIFT_TOLERANCE_M = 1e-5


def _reposition_rerun_reason(
    adapter: Any,
    curated: Sequence[Any],
    names: Sequence[str],
    keep: Mapping[str, tuple[float, float]],
    *,
    deleted: bool,
) -> Literal["deleted", "drifted", "none"]:
    """Whether ``curate_view_dimensions`` must place its kept dimensions again.

    A pass that deleted can shift a survivor it already placed (top_frame
    ``Width`` 6.97 mm), so it is always followed by a second placement.  After
    a reposition-only pass one ``GetPosition`` per kept dimension (~3 ms each,
    against ~0.65 s for the pass) decides instead: any kept dimension off its
    requested point by more than ``_REPOSITION_DRIFT_TOLERANCE_M`` is placed
    again with the rest.  Records ``reposition_rerun_reason`` (and, for the
    readback, its count/cost/drift) on the current span.
    """
    if deleted:
        _telemetry.annotate(reposition_rerun_reason="deleted")
        return "deleted"
    started = time.perf_counter()
    drifted: list[str] = []
    read = 0
    for annotation, name in zip(curated, names):
        if name not in keep:
            continue
        read += 1
        position = adapter._attempt(
            lambda a=annotation: adapter._get_attr_or_call(a, "GetPosition")
        )
        if not position or math.dist(
            (float(position[0]), float(position[1])), keep[name]
        ) > _REPOSITION_DRIFT_TOLERANCE_M:
            drifted.append(name)
    reason: Literal["drifted", "none"] = "drifted" if drifted else "none"
    _telemetry.annotate(
        reposition_rerun_reason=reason,
        reposition_readback_n=read,
        reposition_readback_s=round(time.perf_counter() - started, 4),
        reposition_drifted_n=len(drifted),
    )
    if drifted:
        _telemetry.info(
            f"kept dimensions {sorted(drifted)} read back off their requested "
            "position after the rebuild; placing the view's dimensions again"
        )
    return reason



@_telemetry.traced("drawing.curate_dimensions", label_param="view_label")
def curate_view_dimensions(
    adapter: Any,
    view: Any,
    *,
    keep: dict[str, tuple[float, float]],
    view_label: str,
    dimensions_by_feature: Mapping[str, Iterable[str]] | None = None,
) -> list[Any]:
    """Import a view's marked model dimensions and keep exactly ``keep``.

    ``keep`` maps each surviving dimension's parametric name to its sheet
    position (meters).  A missing expected dimension fails loud — the print
    must carry every manufacturing dimension the recipe promises.

    ``dimensions_by_feature`` is the source part spec's ``DRAWING_DIMENSIONS``
    (``{feature: {dimension names}}``).  Given it, only the features that own
    ``keep`` are selected and imported, so nothing arrives that must be deleted
    again and an empty ``keep`` costs no COM call at all.  Without it the view
    falls back to the entire-model import plus deletion sweep: the same ink for
    many times the round trips, so the fallback WARNS and names the view, which
    keeps every recipe still on it visible in the build log.

    The kept dimensions are positioned again when the first pass deleted some
    (a delete can shift a survivor the same pass already placed: top_frame
    ``Width`` 6.97 mm, ``RibWidth`` 0.63 mm) or when one reads back off its
    requested point after that pass's rebuild.  Otherwise the second pass is
    skipped: after a reposition-only pass it moved nothing and changed no PDF
    pixel on any of 9 views (diag branch pedro/drawing-step-snapshots-diag,
    a0e136c66, leaves cone_pivot_post/pinion_arbor/top_frame) and cost ~0.65 s
    each (one ``EditRebuild3`` plus a name read and ``SetPosition`` per
    dimension); the readback costs one ``GetPosition`` per kept dimension.
    """
    if dimensions_by_feature is None:
        _telemetry.warn(
            f"{view_label} view imports the ENTIRE model's marked dimensions and "
            "deletes the rest; pass dimensions_by_feature=<part>_spec."
            "DRAWING_DIMENSIONS to import only the features it dimensions"
        )
        return _curate_entire_model_import(
            adapter, view, keep=keep, view_label=view_label
        )
    if not keep:
        return []
    features = _features_owning(dimensions_by_feature, keep, view_label=view_label)
    named = insert_feature_dimensions(adapter, view, features)
    annotations = [annotation for _, annotation in named]
    extra = tuple(sorted({name for name, _ in named if name and name not in keep}))
    unnamed = sum(1 for name, _ in named if not name)
    if extra or unnamed:
        # A feature that owns a kept dimension can also own ink the recipe does
        # not place (a cosmetic-thread callout has no parametric name at all).
        # Deleting it keeps the sheet to the recipe; warning makes the surprise
        # visible instead of silently paid for on every build.
        _telemetry.warn(
            f"{view_label} view's targeted import delivered unrequested "
            f"annotations from features={list(features)}: dimensions={list(extra)}, "
            f"unnamed={unnamed}; deleting them"
        )
        if unnamed:
            annotations = delete_unnamed_imports(adapter, annotations)
    curated = curate_dimensions(
        adapter, annotations, delete=extra, reposition=dict(keep)
    )
    names = [dimension_name(adapter, annotation) for annotation in curated]
    missing = sorted(set(keep) - set(names))
    if missing:
        raise RuntimeError(
            f"{view_label} view is missing model dimensions: {missing}; "
            f"available={sorted(set(names))} from features={list(features)}"
        )
    if (
        _reposition_rerun_reason(adapter, curated, names, keep, deleted=bool(extra))
        == "none"
    ):
        return curated
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
    # ``SetText`` takes effect immediately (``GetText`` reads it back without
    # a rebuild); the text EXTENT it changes is only read by the finalizer's
    # layout pass, which rebuilds first. 30 rebuilds on top-frame, ~14 s.


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
    rebuild_drawing(adapter, label="set_dimension_text")


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
    rebuild_drawing(adapter, label="set_reference_dimension")
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
    rebuild_drawing(adapter, label="set_dimension_precision")


@_telemetry.traced("drawing.imported_precision")
def assert_imported_precision(
    adapter: Any, annotations: Iterable[Any], precision: dict[str, int]
) -> None:
    """Prove imported model dimensions kept their PART-authored decimal places.

    Policy rule 2 makes the model own display precision, so a migrated sheet
    may not rewrite it -- but it must still fail loud when an import loses the
    override, because a dimension that silently falls back to the drawing
    document's two-place default prints a tighter band than anyone specified.
    The read-only mirror of :func:`set_dimension_precision`: same name-keyed
    scan, ``GetPrimaryPrecision2`` only, and an unmatched name is an error.
    """
    remaining = dict(precision)
    scanned = 0
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
            display, "IDisplayDimension", "GetPrimaryPrecision2"
        )
        applied = adapter._attempt(lambda d=display: d.GetPrimaryPrecision2())
        if applied != digits:
            raise RuntimeError(
                f"imported dimension {name!r} prints {applied} decimal places, but "
                f"its part authored {digits}; rebuild the source part"
            )
    _span_scan_attrs(scanned=scanned, changed=0)
    if remaining:
        raise RuntimeError(
            f"part-authored precision never reached the sheet: {sorted(remaining)}"
        )


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
    rebuild_drawing(adapter, label="set_reference_dimensions")


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
    rebuild_drawing(adapter, label="offset_dimension_text")


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
    entities: tuple[Any | None, Any | None] | None = None,
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

    ``entities`` may identify either pick exactly; a ``None`` entry retains the
    corresponding coordinate pick. Explicit entities avoid ambiguous hit-test
    results when projected edges are close together.
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
        requested_entity = entities[index] if entities else None
        if requested_entity is None:
            selected = draw.Extension.SelectByID2(
                "", selected_type, x, y, 0.0, index > 0, 0, null_callout(), 0
            )
            location = f"at sheet ({x:g}, {y:g})"
        elif selected_type == "SILHOUETTE":
            manager = _early_bound(draw.SelectionManager, "ISelectionMgr")
            selection_data = manager.CreateSelectData()
            selection_data.View = view
            selectable = _sw_type_info.early_bound_or_flag(
                requested_entity, "ISilhouetteEdge", "Select2"
            )
            selected = selectable.Select2(index > 0, selection_data)
            location = "by entity"
        elif selected_type == "SKETCHSEGMENT":
            # An owned view centreline (``ISketchSegment``, no ``IEntity``
            # face): a bore axis the print dimensions FROM, so a location
            # starts on the feature the shop indicates, not mid-air.
            manager = _early_bound(draw.SelectionManager, "ISelectionMgr")
            selection_data = manager.CreateSelectData()
            selection_data.View = view
            selectable = _sw_type_info.early_bound_or_flag(
                requested_entity, "ISketchSegment", "Select4"
            )
            selected = selectable.Select4(index > 0, selection_data)
            location = "by centreline"
        else:
            manager = _early_bound(draw.SelectionManager, "ISelectionMgr")
            selection_data = manager.CreateSelectData()
            selection_data.View = view
            selectable = _early_bound(requested_entity, "IEntity")
            selected = selectable.Select4(index > 0, selection_data)
            location = "by entity"
        if not selected:
            raise RuntimeError(
                f"failed to select {label} {selected_type.lower()} {index} {location}"
            )
        if requested_entity is not None:
            manager = _early_bound(draw.SelectionManager, "ISelectionMgr")
            count = int(manager.GetSelectedObjectCount2(-1))
            if count != index + 1:
                raise RuntimeError(
                    f"{label} {selected_type.lower()} {index} changed the "
                    f"selection count to {count}"
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
    # No rebuild here: ``Add*Dimension2`` returns an evaluated display
    # dimension (its value, text and position read back at once -- every
    # ``_checked_dimension`` proves the value straight after this call), and
    # at ~0.45 s per ``EditRebuild3`` the per-dimension rebuild was 26 of
    # top-frame's 104 rebuilds. The finalizer rebuilds once before the
    # layout readbacks that do need settled text extents.
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

    Nothing is memoised here, deliberately: a hidden cross-call cache would
    have to invalidate on any visibility change (``set_hidden_lines_removed``,
    the drive-train isolation walk), and a stale entity list picks the wrong
    edge SILENTLY. A recipe that picks MANY entities off one view -- top_frame
    swept its plan view four times in a row and Section A-A five times, 124 s
    of a 270 s build once the per-edge ``GetCurve``/``IsLine``/vertex reads
    were counted -- scans once with :func:`scan_view_edges` and picks off the
    :class:`ViewEdges` it returns, re-scanning EXPLICITLY after it changes the
    view's display. The staleness hazard then lives in one visible line of the
    recipe instead of in a cache nobody can see.
    """
    drawing_view = _early_bound(view, "IView")
    entities: list[Any] = []
    components = drawing_view.GetVisibleComponents() or []
    for component in components:
        entities.extend(visible_component_entities(drawing_view, component, entity_kind))
    # The scan's SIZE, on the span itself. Duration alone cannot separate "this
    # view is huge" from "this seat is slow", and the callers that classify each
    # returned entity scale directly with this count.
    span = _telemetry.trace.get_current_span()
    span.set_attribute("components", len(components))
    span.set_attribute("entities", len(entities))
    span.set_attribute("entity_kind", entity_kind)
    return entities


_VIEW_ENTITY_SILHOUETTE = 4  # swViewEntityType_SilhouetteEdge
# How far a silhouette's projected line may pass from the sheet point it is
# asked for.  Projection is exact to ~1e-9 m, and the lines this separates are
# a cylinder's two flanks, a diameter apart on the sheet.
_SILHOUETTE_POINT_TOLERANCE_M = 1e-5


def _segment_distance(
    point: Sequence[float], start: Sequence[float], end: Sequence[float]
) -> float:
    """Distance on the sheet from ``point`` to the segment ``start``-``end``."""
    dx, dy = end[0] - start[0], end[1] - start[1]
    length_sq = dx * dx + dy * dy
    if length_sq == 0.0:
        return math.dist(point[:2], start[:2])
    t = ((point[0] - start[0]) * dx + (point[1] - start[1]) * dy) / length_sq
    t = min(1.0, max(0.0, t))
    return math.dist(point[:2], (start[0] + t * dx, start[1] + t * dy))


def _same_segment(first: Sequence[Any], second: Sequence[Any]) -> bool:
    """Whether two ``(entity, keys, start, end)`` lines draw the same segment."""
    a0, a1, b0, b1 = first[2], first[3], second[2], second[3]
    tol = _SILHOUETTE_POINT_TOLERANCE_M
    forward = math.dist(a0, b0) <= tol and math.dist(a1, b1) <= tol
    return forward or (math.dist(a0, b1) <= tol and math.dist(a1, b0) <= tol)


@_telemetry.traced("drawing.pick_face_silhouettes", label_param="label")
def face_silhouettes_through(
    adapter: Any,
    view: Any,
    picks: Mapping[str, tuple[Any, tuple[float, float]]],
    *,
    label: str,
) -> dict[str, Any]:
    """Resolve each pick to the one silhouette of its face drawn through its point.

    ``picks`` maps a key to ``(face spec, sheet point)``: the model face a
    silhouette must belong to (a ``_gtol_spec`` face spec, the one a
    ``SurfaceFinishControl`` carries) and a sheet point on the line it draws.
    A cylinder shows two flank silhouettes of one face; the point picks the
    flank.  Returns the silhouette entity per key, for the ``entity=`` path of
    the annotation helpers.

    This replaces ``SelectByID2`` at the sheet point.  That call hit-tests the
    seat's graphics window, so the same point on the same geometry can miss on
    one worker and hit on another: ``drawing:dt_pinion_arbor`` (key 870279bc)
    missed its front-journal flank at sheet (0.25355, 0.166) on
    swmaker00000a@10 and hit on swmaker000004@4, and missed on @10 again at
    the next commit.  The sweep then showed what sits under that point: the
    land's face returns its lower flank TWICE, as two coincident silhouettes,
    so the hit test had a tie to break.  The silhouettes and their faces come
    from the model, and coincident twins are taken as the one line they draw,
    so the pick reads the same on every seat.

    One ``GetVisibleEntities2(..., 4)`` sweep serves every pick (see
    :func:`visible_view_entities` for what a silhouette sweep costs); faces are
    matched before any endpoint is read, and the matched ends are projected in
    one batch.  Fails loud unless each key resolves to exactly one silhouette.
    """
    from _part_pmi import _face_geometry, _face_matches

    silhouettes = visible_view_entities(view, _VIEW_ENTITY_SILHOUETTE, label=label)
    matched: list[tuple[Any, tuple[str, ...], tuple[float, ...], tuple[float, ...]]] = []
    for silhouette in silhouettes:
        face = _com_invoke(silhouette, "ISilhouetteEdge", "GetFace")
        geometry = _face_geometry(face) if face is not None else None
        if geometry is None:
            continue
        keys = tuple(key for key, (spec, _xy) in picks.items() if _face_matches(geometry, spec))
        if not keys:
            continue
        ends = []
        for member in ("GetStartPoint", "GetEndPoint"):
            point = _com_invoke(silhouette, "ISilhouetteEdge", member)
            values = _com_invoke(point, "IMathPoint", "ArrayData") if point is not None else None
            ends.append(tuple(float(v) for v in (values or ())[:3]))
        if all(len(end) == 3 for end in ends):
            matched.append((silhouette, keys, ends[0], ends[1]))
    projected = model_points_in_view(
        adapter,
        view,
        [end for _silhouette, _keys, start, stop in matched for end in (start, stop)],
        label=f"{label} silhouette ends",
    )
    lines = [
        (silhouette, keys, projected[2 * index], projected[2 * index + 1])
        for index, (silhouette, keys, _start, _stop) in enumerate(matched)
    ]
    _telemetry.annotate(silhouettes=len(silhouettes), face_matched=len(matched))
    resolved: dict[str, Any] = {}
    for key, (spec, xy) in picks.items():
        own = [line for line in lines if key in line[1]]
        hits = [
            line
            for line in own
            if _segment_distance(xy, line[2], line[3]) <= _SILHOUETTE_POINT_TOLERANCE_M
        ]
        # One drawn line can come back as several silhouettes of the same face:
        # the arbor's front-land lower flank read twice, (240.55, 166)-(260.55,
        # 166) mm both times, on swmaker000004@4 (run 20260929T224917539Z).
        # Coincident twins are one line; different lines through the point are
        # ambiguous.
        distinct = [
            line
            for index, line in enumerate(hits)
            if not any(_same_segment(line, other) for other in hits[:index])
        ]
        _telemetry.annotate(**{f"{key}_hits": len(hits), f"{key}_lines": len(distinct)})
        if len(distinct) == 1:
            hits = distinct
        if len(hits) != 1:
            drawn = "; ".join(
                f"({a[0] * 1000:.3f}, {a[1] * 1000:.3f})-({b[0] * 1000:.3f}, "
                f"{b[1] * 1000:.3f}) mm"
                for _silhouette, _keys, a, b in own
            )
            raise RuntimeError(
                f"{label}: {len(hits)} silhouettes of {key}'s face {spec!r} pass "
                f"through sheet ({xy[0] * 1000:.3f}, {xy[1] * 1000:.3f}) mm; want "
                f"exactly 1 of the {len(own)} that face draws: {drawn or 'none'} "
                f"({len(silhouettes)} silhouettes in the view)"
            )
        resolved[key] = hits[0][0]
    return resolved


@_telemetry.traced("drawing.rebuild", label_param="label")
def rebuild_drawing(adapter: Any, *, label: str) -> None:
    """The one ``EditRebuild3`` chokepoint for drawing recipes.

    Every annotation helper used to call ``EditRebuild3`` inline -- 31 sites
    in this module, a dozen more in top_frame's recipe -- and each one
    regenerates every view on every sheet. Untraced, that cost was ~50 s of
    a 270 s top_frame build with nothing in the trace to attribute it to.
    Routing them here makes each rebuild a ``drawing.rebuild`` span named for
    the helper that asked, so "which helper's rebuilds are worth removing?"
    is read off ``traces.jsonl`` instead of guessed.
    """
    adapter.currentModel.EditRebuild3()


@dataclass(frozen=True)
class ViewEdge:
    """One visible model edge of a drawing view with its geometry read ONCE.

    ``line`` is ``(start_mm, end_mm)`` for a straight edge; ``circle`` is
    ``(cx, cy, cz, nx, ny, nz, r)`` with the centre and radius in mm and the
    axis a unit vector, straight from ``ICurve::CircleParams``. Both are
    ``None`` for any other curve (an ellipse, a spline). ``vertices`` are the
    ``IVertex`` objects of a straight edge, in ``(start, end)`` order, for
    picks that dimension vertex-to-vertex.
    """

    edge: Any
    line: tuple[tuple[float, float, float], tuple[float, float, float]] | None
    circle: tuple[float, float, float, float, float, float, float] | None
    vertices: tuple[Any, Any] | None

    @property
    def midpoint_mm(self) -> tuple[float, float, float]:
        if self.line is None:
            raise ValueError("midpoint of a non-linear edge")
        start, end = self.line
        return tuple((a + b) / 2.0 for a, b in zip(start, end))

    @property
    def length_mm(self) -> float:
        if self.line is None:
            raise ValueError("length of a non-linear edge")
        return math.dist(*self.line)


@dataclass(frozen=True)
class ViewEdges:
    """Every visible edge of one view, classified, from ONE COM sweep.

    Holds the ``IEdge`` handles plus the geometry a picker reasons about, so
    picking N dimensions off one view costs one sweep and N pure-Python
    filters instead of N sweeps each re-reading every edge's curve and
    vertices over COM (5+ round trips per edge, 60-100 edges per view).

    **Valid only for the display state it was scanned in.** Changing the
    view's display mode, cropping it, or reversing a section's cut direction
    changes what ``GetVisibleEntities2`` returns; the recipe that made such a
    change calls :func:`scan_view_edges` again -- there is no implicit
    invalidation, by design (see ``visible_view_entities``).
    """

    label: str
    edges: tuple[ViewEdge, ...]

    @property
    def lines(self) -> tuple[ViewEdge, ...]:
        return tuple(item for item in self.edges if item.line is not None)

    @property
    def circles(self) -> tuple[ViewEdge, ...]:
        return tuple(item for item in self.edges if item.circle is not None)

    def exact_line_through(
        self, point_mm: tuple[float, float, float], *, label: str
    ) -> ViewEdge:
        """The straight visible edge whose segment passes through ``point_mm``.

        Exact (1e-8 mm^2 squared distance, within the segment's own span), so a
        point that is not ON a visible edge fails loud naming the five nearest
        segment ends -- a coordinate typo or a hidden edge can never resolve to
        the neighbour that happens to be closest.
        """
        matches = []
        for item in self.lines:
            start, end = item.line
            vector = tuple(b - a for a, b in zip(start, end))
            length_sq = sum(value * value for value in vector)
            if length_sq == 0.0:
                continue
            t = sum((p - a) * v for p, a, v in zip(point_mm, start, vector)) / length_sq
            if not -1e-6 <= t <= 1.0 + 1e-6:
                continue
            error = sum((p - a - t * v) ** 2 for p, a, v in zip(point_mm, start, vector))
            matches.append((error, item))
        if not matches or min(matches, key=lambda pair: pair[0])[0] > 1e-8:
            nearest = sorted(
                (
                    (min(math.dist(point_mm, start), math.dist(point_mm, end)), start, end)
                    for start, end in (item.line for item in self.lines)
                ),
                key=lambda row: row[0],
            )[:5]
            raise RuntimeError(
                f"{label}: no exact visible line through {point_mm} in the "
                f"{self.label!r} scan; {len(self.lines)} visible lines, "
                f"nearest by endpoint={nearest}"
            )
        return min(matches, key=lambda pair: pair[0])[1]

    def exact_vertex_at(self, point_mm: tuple[float, float, float], *, label: str) -> Any:
        """The ``IVertex`` of a visible straight edge sitting exactly at ``point_mm``."""
        best = None
        for item in self.lines:
            for point, vertex in zip(item.line, item.vertices):
                error = sum((a - b) ** 2 for a, b in zip(point_mm, point))
                if best is None or error < best[0]:
                    best = (error, vertex)
        if best is None or best[0] > 1e-8:
            raise RuntimeError(
                f"{label}: no exact visible vertex at {point_mm} in the "
                f"{self.label!r} scan"
            )
        return best[1]

    def circle_at(
        self,
        center_mm: tuple[float, float, float],
        radius_mm: float,
        *,
        axis: tuple[float, float, float] | None = None,
        label: str,
        center_tol_mm: float = 0.02,
        radius_tol_mm: float = 0.01,
        selection: Literal["nearest", "unique"] = "nearest",
        adapter: Any | None = None,
    ) -> ViewEdge:
        """The visible circular edge nearest ``center_mm``/``radius_mm``.

        ``axis`` (a unit vector, either sign) pins the circle's plane so the
        two rims of one bore -- same centre in the view, opposite normals --
        cannot be confused. Fails loud past the tolerances with the nearest
        candidate's numbers, so a moved feature is a build error, never a
        dimension quietly hung on the wrong rim.

        ``selection="unique"`` requires exactly one distinct native edge
        within those same limits; ``adapter`` supplies SolidWorks' IsSame
        comparison so repeated wrappers for one edge are not ambiguity.
        The default nearest mode retains the existing ranked-pick behavior.
        """
        if selection not in ("nearest", "unique"):
            raise ValueError(f"{label}: unknown circle selection mode {selection!r}")
        if selection == "unique" and adapter is None:
            raise ValueError(f"{label}: unique circle selection requires an adapter")
        circles = self.circles
        matches: list[ViewEdge] = []
        best = None
        for item in circles:
            cx, cy, cz, nx, ny, nz, r = item.circle
            center_error = sum(abs(a - b) for a, b in zip((cx, cy, cz), center_mm))
            radius_error = abs(r - radius_mm)
            axis_error = 0.0
            if axis is not None:
                dot = nx * axis[0] + ny * axis[1] + nz * axis[2]
                axis_error = 1.0 - abs(dot)
            outside_limits = (
                center_error > center_tol_mm
                or radius_error > radius_tol_mm
                or axis_error > 1e-6
            )
            score = center_error + radius_error + axis_error
            if best is None or score < best[0]:
                best = (score, center_error, radius_error, axis_error, item, outside_limits)
            if selection == "unique" and not outside_limits:
                matches.append(item)
        if best is None:
            raise RuntimeError(f"{label}: the {self.label!r} scan has no circular edge")
        _score, center_error, radius_error, axis_error, item, outside_limits = best
        if selection == "unique":
            distinct: list[ViewEdge] = []
            for candidate in matches:
                if not any(
                    candidate.edge is previous.edge
                    or _is_same_attachment(adapter, candidate.edge, previous.edge, "EDGE")
                    for previous in distinct
                ):
                    distinct.append(candidate)
            _telemetry.annotate(
                visible_circles=len(circles),
                circle_candidates=len(matches),
                distinct_circle_candidates=len(distinct),
            )
            if len(distinct) > 1:
                raise RuntimeError(
                    f"{label}: ambiguous visible circle at {center_mm} "
                    f"r={radius_mm:g} mm in the {self.label!r} scan: "
                    f"{len(distinct)} distinct native edges ({len(matches)} candidates)"
                )
            if distinct:
                return distinct[0]
        if outside_limits:
            raise RuntimeError(
                f"{label}: no visible circle at {center_mm} r={radius_mm:g} mm in "
                f"the {self.label!r} scan; nearest centre error {center_error:.4g} mm, "
                f"radius error {radius_error:.4g} mm, axis error {axis_error:.2g}"
            )
        return item


@_telemetry.traced("drawing.view_edge_scan", label_param="label")
def scan_view_edges(view: Any, *, label: str) -> ViewEdges:
    """Sweep ``view``'s visible edges once and read each one's geometry once.

    The sweep is :func:`visible_view_entities` (kind 1, edges); the
    classification -- ``GetCurve``, ``IsLine``/``IsCircle``, the two vertices
    and their points, ``CircleParams`` -- is the part every picker used to
    repeat per dimension. Its size rides the span (``edges``/``lines``/
    ``circles``) so a slow scan reads as "this view is big", not "this seat
    is slow".
    """
    items: list[ViewEdge] = []
    for raw_edge in visible_view_entities(view, 1, label=label):
        edge = _early_bound(raw_edge, "IEdge")
        curve = edge.GetCurve()
        if curve is None:
            continue
        curve = _early_bound(curve, "ICurve")
        line = circle = vertices = None
        if curve.IsLine():
            raw_vertices = (edge.GetStartVertex(), edge.GetEndVertex())
            if all(vertex is not None for vertex in raw_vertices):
                bound = tuple(_early_bound(vertex, "IVertex") for vertex in raw_vertices)
                start, end = (
                    tuple(float(value) * 1000.0 for value in vertex.GetPoint())
                    for vertex in bound
                )
                line, vertices = (start, end), bound
        elif curve.IsCircle():
            raw = tuple(float(value) for value in curve.CircleParams)
            circle = (
                raw[0] * 1000.0, raw[1] * 1000.0, raw[2] * 1000.0,
                raw[3], raw[4], raw[5], raw[6] * 1000.0,
            )
        items.append(ViewEdge(edge=edge, line=line, circle=circle, vertices=vertices))
    span = _telemetry.trace.get_current_span()
    span.set_attribute("edges", len(items))
    span.set_attribute("lines", sum(1 for item in items if item.line is not None))
    span.set_attribute("circles", sum(1 for item in items if item.circle is not None))
    return ViewEdges(label=label, edges=tuple(items))


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
    rebuild_drawing(adapter, label="set_basic_dimension")
    return dimension


def assert_dimension_measures(
    adapter: Any,
    dimension: Any,
    *,
    expected_mm: float,
    label: str,
    entities: tuple[Any, Any] | None = None,
    entity_types: tuple[str, str] = ("EDGE", "EDGE"),
    tolerance_mm: float = 1e-5,
) -> float:
    """Fail unless a native ``Add*Dimension2`` result spans ``entities`` and
    measures ``expected_mm``.

    A drawing dimension reads whatever its two picks resolved to; when a
    coordinate hit-test lands on the neighbouring line the sheet prints a
    wrong locating number with no error (summing-lever's spring-hole start
    read 3.35 off the rib flange instead of 8.43 off the plate end, #1105).
    The value alone is a weak proof -- a 20-hole row has nineteen pairs at
    the same pitch and twenty rims at the same row X -- so the dimension's
    attached entities (``IAnnotation::GetAttachedEntities3``) must be the
    two the recipe named, each by ``_is_same_attachment``, and only then is
    ``IDimension.SystemValue`` checked against the spec constant. Returns the
    measured millimetres.

    ``entities=None`` is value-only: for a dimension the recipe cannot name
    by entity. The call site says why.
    """
    display = _sw_type_info.early_bound_or_flag(
        dimension, "IDisplayDimension", "GetDimension2", "GetAnnotation"
    )
    if entities is not None:
        annotation = _sw_type_info.early_bound_or_flag(
            display.GetAnnotation(),
            "IAnnotation",
            "GetAttachedEntities3",
            "GetAttachedEntityTypes",
            "IsDangling",
        )
        attached = list(annotation.GetAttachedEntities3() or ())
        types = tuple(int(t) for t in (annotation.GetAttachedEntityTypes() or ()))
        dangling = bool(annotation.IsDangling())
        unmatched = []
        for index, (expected, kind) in enumerate(zip(entities, entity_types)):
            match = next(
                (
                    item
                    for item in attached
                    if item is not None
                    and _is_same_attachment(adapter, item, expected, kind.upper())
                ),
                None,
            )
            if match is None:
                unmatched.append(index)
            else:
                attached.remove(match)
        if unmatched or attached or dangling:
            raise RuntimeError(
                f"{label} is not the dimension between its named entities: "
                f"unmatched picks={unmatched}, extra attachments={len(attached)}, "
                f"types={types}, dangling={dangling}"
            )
    model_dimension = _early_bound(display.GetDimension2(0), "IDimension")
    measured_mm = abs(float(model_dimension.SystemValue)) * 1000.0
    if abs(measured_mm - expected_mm) > tolerance_mm:
        raise RuntimeError(
            f"{label} measures {measured_mm:g} mm, expected {expected_mm:g} mm: "
            "a pick resolved to the wrong entity"
        )
    return measured_mm


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


@_telemetry.traced("drawing.theoretical_datum", label_param="label")
def create_view_theoretical_datum(
    adapter: Any,
    view: Any,
    *,
    point_xy: tuple[float, float],
    label: str,
) -> Any:
    """Create a view-owned datum point at a broken theoretical corner.

    ``point_xy`` is in view-local model metres.  A drawing view has no model
    vertex at a filleted or chamfered theoretical sharp, so this creates a
    retained user ``ISketchPoint`` in the view's drawing sketch.  Native tables
    can use that point as their origin while callers derive its coordinates
    from authoritative model dimensions.
    """
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    name = view_name(adapter, view)
    if not drawing.ActivateView(name):
        raise RuntimeError(f"failed to activate theoretical-datum view {name!r}")
    sketch_manager = _early_bound(draw.SketchManager, "ISketchManager")
    previous_add_to_db = bool(sketch_manager.AddToDB)
    previous_display = bool(sketch_manager.DisplayWhenAdded)
    sketch_manager.AddToDB = True
    sketch_manager.DisplayWhenAdded = True
    try:
        point = sketch_manager.CreatePoint(point_xy[0], point_xy[1], 0.0)
    finally:
        sketch_manager.AddToDB = previous_add_to_db
        sketch_manager.DisplayWhenAdded = previous_display
    if point is None:
        raise RuntimeError(f"failed to create {label} theoretical datum point")
    point = _early_bound(point, "ISketchPoint")
    draw.ClearSelection2(True)
    rebuild_drawing(adapter, label="create_view_theoretical_datum")
    return point


def insert_hole_table(
    adapter: Any,
    view: Any,
    *,
    datum_xy: tuple[float, float],
    hole_points: Sequence[tuple[float, float]],
    datum_entity: Any | None = None,
    datum_point: Any | None = None,
    datum_axes: tuple[Any, Any] | None = None,
    hole_entities: Sequence[Any] | None = None,
    expected_locations_mm: Sequence[tuple[float, float]] | None = None,
    anchor_xy: tuple[float, float],
    basic_locations: bool = True,
    label: str,
    starting_hole_tag: str = "A",
) -> Any:
    """Insert the model-associated TAG/X LOC/Y LOC/SIZE hole table on ``view``.

    ``datum_xy`` picks the origin VERTEX and each ``hole_points`` entry picks a
    hole EDGE, all in sheet meters.  Callers that can identify drawing-context
    entities topologically may additionally supply ``datum_entity`` and
    ``hole_entities``; those are selected directly with the same hole-table
    marks and the coordinates remain the count/diagnostic contract.  A part
    whose plan corners are broken can supply ``datum_axes=(x_axis_edge,
    y_axis_edge)`` for initial insertion.  When ``datum_point`` is also
    supplied, the table's native ``IDatumOrigin`` is then reattached to that
    view-owned theoretical-corner point.  ``starting_hole_tag`` lets multiple
    tables on one sheet use distinct tag families.  The table lands with its
    top-left corner at ``anchor_xy`` and is validated before returning.
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
        raise ValueError(f"{label} supplied multiple initial datum sources")
    if datum_point is not None and datum_axes is None and datum_entity is None:
        raise ValueError(f"{label} datum point requires an initial datum source")
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
        starting_hole_tag,
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
    if datum_point is not None:
        draw.ClearSelection2(True)
        selection_manager = _early_bound(draw.SelectionManager, "ISelectionMgr")
        selection_data = _early_bound(
            selection_manager.CreateSelectData(), "ISelectData"
        )
        selection_data.View = view
        point = _early_bound(datum_point, "ISketchPoint")
        if not point.Select4(False, selection_data):
            raise RuntimeError(f"failed to select {label} theoretical datum point")
        origin = _early_bound(feature.DatumOrigin, "IDatumOrigin")
        if not origin.Reattach():
            raise RuntimeError(f"failed to reattach {label} hole-table datum")
        draw.ClearSelection2(True)
    rebuild_drawing(adapter, label="_select_entity")
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
        rebuild_drawing(adapter, label="_select_entity")
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
    rebuild_drawing(adapter, label="insert_bom_table")
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
        rebuild_drawing(adapter, label="insert_bom_table")
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


def rendered_balloon_circle(note: Any, *, label: str) -> tuple[float, float, float]:
    """Return sheet X/Y/radius from the unique rendered full-circle primitive.

    INote.GetBalloonInfo can retain its original center after a successful move,
    rebuild, redraw, and PDF export. IAnnotation.GetDisplayData reflects the ink.
    """
    note = _sw_type_info.early_bound_or_flag(note, "INote", "GetAnnotation")
    annotation = note.GetAnnotation()
    if annotation is None:
        raise RuntimeError(f"{label}: balloon has no annotation")
    annotation = _sw_type_info.early_bound_or_flag(
        annotation, "IAnnotation", "GetDisplayData"
    )
    display = annotation.GetDisplayData()
    if display is None:
        raise RuntimeError(f"{label}: balloon has no rendered display data")
    display = _sw_type_info.early_bound_or_flag(
        display, "IDisplayData", "GetArcCount", "GetArcAtIndex2"
    )
    circle = None
    for index in range(int(display.GetArcCount())):
        arc = tuple(float(value) for value in (display.GetArcAtIndex2(index) or ()))
        # Native schema: four metadata values, start XYZ, end XYZ, center XYZ,
        # normal XYZ, rotation direction. Closed start/end identifies a circle.
        if len(arc) < 17 or not all(math.isfinite(value) for value in arc[4:16]):
            raise RuntimeError(f"{label}: invalid rendered arc data: {arc!r}")
        if any(abs(arc[4 + axis] - arc[7 + axis]) > 1e-9 for axis in range(3)):
            continue
        radius = math.hypot(arc[4] - arc[10], arc[5] - arc[11])
        if (
            not math.isfinite(radius)
            or radius <= 0.0
            or abs(arc[13]) > 1e-9
            or abs(arc[14]) > 1e-9
            or abs(abs(arc[15]) - 1.0) > 1e-9
        ):
            raise RuntimeError(
                f"{label}: invalid rendered sheet-circle geometry: {arc!r}"
            )
        if circle is not None:
            raise RuntimeError(
                f"{label}: multiple rendered full-circle balloon primitives"
            )
        circle = (arc[10], arc[11], radius)
    if circle is None:
        raise RuntimeError(f"{label}: no rendered full-circle balloon primitive")
    return circle


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
    box. Deterministic fix: place every balloon's rendered CIRCLE centre on an
    ellipse ``margin`` outside the view outline, evenly spaced, and assign the
    ring slots in the angular order of the balloons' ATTACHMENT POINTS. Leaders
    stay attached; only the balloon anchor moves (``IAnnotation.SetPosition``),
    carrying the anchor's constant offset from the circle centre (#866).

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
            note, "INote", "GetAnnotation", "GetBomBalloonText"
        )
        circle_x, circle_y, radius = rendered_balloon_circle(
            note, label="balloon spread"
        )
        radii.append(radius)
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
        # SetPosition moves the ANCHOR, which is not the circle centre: it sits
        # a constant ~(+4.0, -1.7) mm off it (#866, 40 balloons on MHA-DT-000).
        # Carry that offset so the CIRCLE lands on its ring slot.
        anchor = annotation.GetPosition()
        if anchor is None or len(anchor) < 2:
            raise RuntimeError("balloon spread: balloon without a position")
        offset = (float(anchor[0]) - circle_x, float(anchor[1]) - circle_y)
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
            (
                theta,
                attach_x,
                attach_y,
                _balloon_item_key(adapter, note),
                (annotation, offset),
            )
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
    # separation is derived from the rendered full-circle radius, not a guess.
    # A monotone push-apart cannot reorder balloons; placement about a shared centre
    # is what rules crossings out, so this keeps radial's proof while paying
    # radial's price only where circles genuinely touch.
    gap = _min_angular_gap(min(radius_x, radius_y), max(radii), clearance=clearance)
    angles = _push_apart_on_ring(
        [theta for theta, _x, _y, _i, _a in items], min_gap=gap
    )
    for angle, (_theta, _x, _y, _item, (annotation, offset)) in zip(angles, items):
        target_x = center_x + radius_x * math.cos(angle) + offset[0]
        target_y = center_y + radius_y * math.sin(angle) + offset[1]
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
    rebuild_drawing(adapter, label="_create_auto_balloons")
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


def balloon_item_resolved(text: str) -> bool:
    """Whether a BOM balloon's displayed item is a real one: SolidWorks prints
    ``?`` when the balloon's component no longer resolves to a BOM row (the
    feature-suppression preview's balloons did), and nothing when unattached."""
    item = text.strip()
    return bool(item) and "?" not in item


def _balloon_item_number(adapter: Any, note: Any, *, label: str) -> str:
    """Read one BOM balloon's displayed upper item number; refuse an unresolved one."""
    note = _sw_type_info.early_bound_or_flag(note, "INote", "GetBomBalloonText")
    item = str(adapter._attempt(lambda: note.GetBomBalloonText(True)) or "").strip()
    if not balloon_item_resolved(item):
        raise RuntimeError(f"{label}: BOM balloon shows unresolved item {item!r}")
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
    balloons = _create_auto_balloons(adapter, view, label=label)
    if len(balloons) < expected:
        raise RuntimeError(
            f"{label}: {len(balloons)} balloons landed, expected >= {expected}"
        )
    _spread_balloons(adapter, view, balloons)
    rebuild_drawing(adapter, label="add_auto_balloons")
    _telemetry.success(f"{label}: {len(balloons)} BOM balloons inserted")
    return balloons


def _drawing_component_children(drawing_component: Any) -> tuple[Any, ...]:
    """Return children across callable and materialized pywin32 shapes."""
    member = drawing_component.GetChildren
    children = member() if callable(member) else member
    return tuple(children or ())


@dataclass(frozen=True)
class BalloonAnchor:
    """Where one BOM family's balloon attaches: a point on one of its edges.

    ``point_mm`` is in the part's own millimetres, so view scale, placement
    and explode distance do not move it. ``instance`` pins the instance it is
    on by its full component path (``IComponent2.Name2``: ``dt-cone-gear-2``, or
    ``sub-1/dt-cone-gear-2`` inside a sub-assembly); ``None`` means the
    lowest-named instance the view shows (:func:`_shown_instances`).

    ``point_mm=None`` walks the part's own body instead
    (:func:`_select_balloon_anchor`), for a family no single point claims,
    on the pinned instance or else the lowest-named shown one, never another.
    """

    point_mm: tuple[float, float, float] | None = None
    instance: str | None = None


@dataclass(frozen=True)
class _ComponentLeaf:
    """One leaf drawing component and the file identities it answers to.

    ``visible`` is the leaf's own drawing-view flag AND every ancestor's: a
    part under a hidden sub-assembly is not drawn, whatever its own flag says.
    ``path`` is the model component's full instance path
    (:func:`_component_path`), the identity every ownership check compares:
    two sub-assemblies may each hold a ``dt-cone-gear-1``, so the last path
    segment names no instance on its own.
    """

    name: str
    component: Any
    identities: frozenset[str]
    visible: bool = True
    path: str = ""


def _instance_name(name: str) -> str:
    """``dt-drive-train-8/dt-cone-gear-2@Drawing View1`` -> ``dt-cone-gear-2``.

    For file-stem matching only: it drops the sub-assembly path, so it never
    decides which instance an entity belongs to (:func:`_component_path`).
    """
    return name.split("@", 1)[0].replace("\\", "/").rsplit("/", 1)[-1]


def _component_path(adapter: Any, component: Any) -> str:
    """A model component's full instance path, ``IComponent2.Name2``.

    A drawing component's ``Name`` carries the view's root prefix
    (``fr-frame-4/vn-tube-frame-cap-1``) while an edge's owning component reads
    ``fr-tube-frame-3`` (farm probe on the frame drawing): ``Name2`` of the
    model component is the one string both sides share, and it keeps every
    sub-assembly segment (``sub-1/dt-cone-gear-1``).
    """
    if component is None:
        return ""
    name = adapter._attempt(
        lambda: _early_bound(component, "IComponent2").Name2, default=""
    )
    return str(name or "").replace("\\", "/")


def _component_leaf(
    adapter: Any, drawing_component: Any, *, visible: bool = True
) -> _ComponentLeaf:
    """Read one leaf drawing component's model component and identities."""
    component = adapter._attempt(
        lambda dc=drawing_component: dc.Component, default=None
    )
    path = ""
    if component is not None:
        path = adapter._attempt(lambda c=component: c.GetPathName(), default="") or ""
    name = str(drawing_component.Name or "")
    identities = frozenset(
        {
            Path(str(path)).stem.casefold(),
            _instance_name(name).casefold(),
        }
    )
    return _ComponentLeaf(
        name=name, component=component, identities=identities, visible=visible
    )


def _stems_matching(identities: frozenset[str], stems: frozenset[str]) -> set[str]:
    """Return the requested file stems ``identities`` represent."""
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


def _drawing_component_stems(
    adapter: Any, drawing_component: Any, stems: frozenset[str]
) -> set[str]:
    """Return requested file stems represented by one leaf drawing component."""
    return _stems_matching(_component_leaf(adapter, drawing_component).identities, stems)


@_telemetry.traced("drawing.component_leaves", label_param="label")
def _view_component_leaves(
    adapter: Any, view: Any, *, label: str
) -> tuple[_ComponentLeaf, ...]:
    """Every leaf drawing component of ``view``, in depth-first walk order,
    each marked shown or hidden in this view.

    Balloon anchoring used to repeat this walk once PER BALLOON -- ~3 s of
    fixed cost on every ``drawing.pick_balloon_anchor`` span across the farm
    (fit intercept 3.08 s, n=1302). Inserting balloons changes no component
    visibility, so one walk serves a whole balloon set.
    """
    root = adapter._attempt(lambda: view.RootDrawingComponent2(False), default=None)
    if root is None:
        raise RuntimeError(f"{label}: drawing view has no root component")
    leaves: list[_ComponentLeaf] = []
    pending = [(child, True) for child in _drawing_component_children(root)]
    while pending:
        drawing_component, shown = pending.pop()
        shown = shown and bool(
            adapter._attempt(lambda dc=drawing_component: dc.Visible, default=True)
        )
        children = _drawing_component_children(drawing_component)
        pending.extend((child, shown) for child in children)
        if children:
            continue
        leaf = _component_leaf(adapter, drawing_component, visible=shown)
        leaves.append(replace(leaf, path=_component_path(adapter, leaf.component)))
    _span_scan_attrs(leaves=len(leaves))
    return tuple(leaves)


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
    rebuild_drawing(adapter, label="isolate_drawing_view_components")
    _telemetry.success(f"{label}: isolated {', '.join(sorted(found))}")


def _natural_sort_key(name: str) -> tuple[tuple[int, int | str], ...]:
    """``dt-cone-gear-2`` before ``dt-cone-gear-10``: digit runs compare as numbers."""
    return tuple(
        (0, int(part)) if part.isdigit() else (1, part.casefold())
        for part in re.split(r"(\d+)", name)
        if part
    )


def _shown_instances(
    leaves: Sequence[_ComponentLeaf],
    stem: str,
    anchor: BalloonAnchor,
    *,
    label: str,
) -> list[_ComponentLeaf]:
    """The instances ``stem``'s balloon may anchor on, first choice first.

    The drawing-component tree lists children in no stable order: over 26
    frame_assembly runs the old first-match walk anchored the cap balloon on
    tube-frame-cap 1, 2, 3 and 4 in turn. The instance path is the one order
    that cannot move, compared as a machinist reads it (2 before 10). A
    hidden instance (drive-train isolates one cluster per view) is never a
    candidate, and a pinned instance is the only one.
    """
    wanted = frozenset({stem})
    matching = sorted(
        (leaf for leaf in leaves if _stems_matching(leaf.identities, wanted)),
        key=lambda leaf: _natural_sort_key(leaf.path or _instance_name(leaf.name)),
    )
    shown = [
        leaf
        for leaf in matching
        if leaf.visible and leaf.component is not None and leaf.path
    ]
    if anchor.instance is not None:
        shown = [
            leaf for leaf in shown if leaf.path.casefold() == anchor.instance.casefold()
        ]
    if not shown:
        pinned = f" {anchor.instance}" if anchor.instance else ""
        raise RuntimeError(
            f"{label}: {stem} has no shown instance{pinned} to anchor its balloon "
            f"on; matching={[(leaf.path or leaf.name, leaf.visible) for leaf in matching]}"
        )
    return shown


def _path_prefixes(path: str) -> list[str]:
    """``sub-1/dt-cone-gear-2`` -> ``["sub-1", "sub-1/dt-cone-gear-2"]``."""
    parts = path.split("/")
    return ["/".join(parts[: count + 1]) for count in range(len(parts))]


@_telemetry.traced("drawing.explode_offsets", label_param="label")
def _view_explode_offsets(
    adapter: Any, view: Any, *, label: str
) -> dict[str, tuple[float, float, float]]:
    """Each exploded component's explode translation, in model metres, keyed
    by its casefolded full instance path (:func:`_component_path`).

    A drawing view shows its model exploded without exploding the model, so
    every component transform (``Transform2``, ``GetSpecificTransform``,
    ``GetTotalTransform``) still reads the collapsed position -- measured on
    the farm: points projected through them landed on the neighbour each
    part had been exploded away from. The explode itself lives in the
    referenced configuration's steps; both explode builders
    (``build_frame_assembly``, ``_drive_train_explode``) author pure
    translations, and a step that rotates is refused rather than summed wrong.

    Each moved component is read as a component (``IExplodeStep::GetComponent``)
    and keyed by the same ``Name2`` the view's leaves carry: the step's own
    name string is an undocumented format, and cutting it to its last segment
    merged two sub-assemblies' ``cone-gear-1``.

    Two reads that fail once a model owns explodes in more than one
    configuration (``Default`` and ``Default Simplified``), measured on both
    frame and drive-train drawings (farm probe, 2026-09-28):

    * the model's ACTIVE configuration reads zero steps until its named
      explode is shown on the model; showing it and collapsing it again makes
      all of them readable and leaves the drawing view exploded;
    * a NON-active configuration reads every step, but ``GetComponent``
      returns None for every member. ``GetComponentName`` then read exactly
      the member's ``Name2``, so the member is resolved by that name against
      the configuration's own component tree. A name that is not one of that
      tree's instance paths still refuses the view.
    """
    bound = _early_bound(view, "IView")
    if not bool(bound.IsExploded()):
        return {}
    model = _early_bound(bound.ReferencedDocument, "IModelDoc2")
    configuration_name = str(bound.ReferencedConfiguration)
    configuration = model.GetConfigurationByName(configuration_name)
    if configuration is None:
        raise RuntimeError(f"{label}: exploded view has no referenced configuration")
    configuration = _early_bound(configuration, "IConfiguration")
    count = int(configuration.GetNumberOfExplodeSteps())
    read = "direct"
    if count == 0:
        count = _shown_explode_step_count(model, configuration, configuration_name, label=label)
        read = "shown on model"
        if not bool(bound.IsExploded()):
            raise RuntimeError(f"{label}: collapsing the model collapsed the drawing view")
    if count == 0:
        raise RuntimeError(
            f"{label}: exploded view's configuration {configuration_name!r} reads no explode steps"
        )
    offsets: dict[str, list[float]] = {}
    instances: dict[str, str] | None = None
    by_name = 0
    for index in range(count):
        step = _early_bound(configuration.GetExplodeStep(index), "IExplodeStep")
        xform = tuple(float(value) for value in (step.GetComponentXform() or ()))
        if len(xform) < 13 or any(
            abs(xform[k] - (1.0 if k in (0, 4, 8) else 0.0)) > 1e-9 for k in range(9)
        ):
            raise RuntimeError(
                f"{label}: explode step {step.Name!r} is not a pure translation: "
                f"{xform!r}"
            )
        for member in range(int(step.GetNumOfComponents())):
            path = _component_path(adapter, step.GetComponent(member))
            if not path:
                if instances is None:
                    instances = _configuration_instance_paths(adapter, configuration)
                name = str(step.GetComponentName(member) or "").replace("\\", "/")
                path = instances.get(name.casefold(), "")
                if not path:
                    raise RuntimeError(
                        f"{label}: explode step {step.Name!r} moves {name!r}, which reads "
                        f"as no component and names no instance of {configuration_name!r}"
                    )
                by_name += 1
            row = offsets.setdefault(path.casefold(), [0.0, 0.0, 0.0])
            for axis in range(3):
                row[axis] += xform[9 + axis]
    _span_scan_attrs(steps=count, moved=len(offsets), by_name=by_name)
    _telemetry.annotate(explode_read=read)
    return {name: (row[0], row[1], row[2]) for name, row in offsets.items()}


def _shown_explode_step_count(
    model: Any, configuration: Any, configuration_name: str, *, label: str
) -> int:
    """Show the active configuration's one named explode on the model, then
    collapse it again, and return the step count that makes readable."""
    manager = _early_bound(model.ConfigurationManager, "IConfigurationManager")
    active = str(_early_bound(manager.ActiveConfiguration, "IConfiguration").Name)
    if active != configuration_name:
        raise RuntimeError(
            f"{label}: {configuration_name!r} reads no explode steps and is not the "
            f"model's active configuration ({active!r})"
        )
    assembly = _early_bound(model, "IAssemblyDoc")
    names = tuple(str(name) for name in (assembly.GetExplodedViewNames2(configuration_name) or ()))
    if len(names) != 1:
        raise RuntimeError(f"{label}: {configuration_name!r} owns explodes {names!r}, not one")
    if not bool(assembly.ShowExploded2(True, names[0])):
        raise RuntimeError(f"{label}: cannot show {names[0]!r} on the model")
    count = int(configuration.GetNumberOfExplodeSteps())
    if not bool(assembly.ShowExploded2(False, names[0])):
        raise RuntimeError(f"{label}: cannot collapse {names[0]!r} on the model")
    return count


def _configuration_instance_paths(adapter: Any, configuration: Any) -> dict[str, str]:
    """Every component instance path of ``configuration``, casefolded -> as read,
    walked from its own root (``GetRootComponent3(True)`` resolves a
    configuration that is not the model's active one)."""
    root = configuration.GetRootComponent3(True)
    paths: dict[str, str] = {}
    pending = list(root.GetChildren() or ()) if root is not None else []
    while pending:
        component = _early_bound(pending.pop(), "IComponent2")
        path = _component_path(adapter, component)
        if path:
            paths[path.casefold()] = path
        pending.extend(component.GetChildren() or ())
    return paths


def _explode_offset(
    offsets: Mapping[str, tuple[float, float, float]], path: str
) -> tuple[float, float, float]:
    """``path``'s own explode plus every enclosing sub-assembly's."""
    total = [0.0, 0.0, 0.0]
    for prefix in _path_prefixes(path):
        for axis, value in enumerate(offsets.get(prefix.casefold(), (0.0, 0.0, 0.0))):
            total[axis] += value
    return (total[0], total[1], total[2])


def _anchor_model_points(
    adapter: Any,
    leaf: _ComponentLeaf,
    points_m: Sequence[Sequence[float]],
    offsets: Mapping[str, tuple[float, float, float]],
    *,
    stem: str,
    label: str,
) -> list[tuple[float, float, float]]:
    """Part-space points (metres) in the view's model space: transform, then explode."""
    transform = adapter._attempt(
        lambda: _early_bound(leaf.component, "IComponent2").Transform2, default=None
    )
    values = (
        ()
        if transform is None
        else tuple(
            float(v) for v in (_early_bound(transform, "IMathTransform").ArrayData or ())
        )
    )
    if len(values) < 13:
        raise RuntimeError(f"{label}: {stem} instance {leaf.path} has no transform")
    scale = values[12]
    dx, dy, dz = _explode_offset(offsets, leaf.path)
    return [
        (
            scale * (x * values[0] + y * values[3] + z * values[6]) + values[9] + dx,
            scale * (x * values[1] + y * values[4] + z * values[7]) + values[10] + dy,
            scale * (x * values[2] + y * values[5] + z * values[8]) + values[11] + dz,
        )
        for x, y, z in points_m
    ]


# A walk hit-tests at most this many of its instance's extreme points, each a
# zoomed sheet round trip.
_WALK_POINTS_PER_INSTANCE = 12
# The visible-edge fallback samples every visible edge of the instance, so
# it refuses one with more: pins and screws draw 2-50, the keeper bead chain
# 110 (two rod/bead circles per link; its spheres draw only silhouettes, so it
# can only be claimed here), a gear over 1,000.
_VISIBLE_EDGES_PER_INSTANCE = 128
# Where along a listed edge's parameter range the fallback samples points to
# hit-test: inside the edge, off the vertices it shares with its neighbours.
_EDGE_SAMPLE_FRACTIONS = (0.1, 0.3, 0.5, 0.7, 0.9)
_VIEW_ENTITY_EDGE = 1  # swViewEntityType_Edge
_SEL_EDGES = 1  # swSelEDGES
# The walk's probe directions in part space: every sign of (1, 0.618, 0.382)
# in each cyclic order. No component is zero and no two are equal, so none is
# normal to an axis-aligned face or square to an axis-aligned bore, and a
# body's extreme point along one is a single point, on a plane-and-cylinder
# part usually a vertex or a point of an edge.
_WALK_DIRECTIONS: tuple[tuple[float, float, float], ...] = tuple(
    (sx * a, sy * b, sz * c)
    for a, b, c in ((1.0, 0.618, 0.382), (0.382, 1.0, 0.618), (0.618, 0.382, 1.0))
    for sx, sy, sz in product((1.0, -1.0), repeat=3)
)

AnchorMethod = Literal["frozen", "walk", "visible-edge", "shared-edge", "listed-edge"]


@dataclass(frozen=True)
class _AnchorChoice:
    """The edge one family's balloon attaches to, where, and how it was found.

    ``sheet_xy`` is the sheet point (metres) whose hit test returned ``edge``
    as the instance's: the balloon's leader must end there. Selected by entity
    alone, SolidWorks picks its own point on the edge, which on a washer or a
    gear rim is often behind another part: on run
    20260928T194845954Z-44f5de00de924735961d14f4aad40337 the thrust washer's
    leader landed 10.3 mm from its verified point, in the gear teeth.
    """

    instance: str
    edge: Any
    method: AnchorMethod
    sheet_xy: tuple[float, float]


_PointKey = tuple[int, int, int]


def _point_key(point: Sequence[float]) -> _PointKey:
    """A part-space point in whole micrometres: the ranking's stable key."""
    return (round(point[0] * 1e6), round(point[1] * 1e6), round(point[2] * 1e6))


def _spread_order(keys: Iterable[_PointKey], limit: int) -> list[_PointKey]:
    """Up to ``limit`` keys: the one farthest from the set's box centre, then
    each next the farthest from every one already taken.

    Geometry alone decides, ties falling to the smaller key, so points
    gathered in any order rank the same. Outermost first because a part's
    outer edges are the ones its neighbours hide least; spread because a
    family whose first point is hidden is seldom hidden all round.
    """
    pool = sorted(set(keys))
    if not pool or limit <= 0:
        return []
    doubled = [min(k[i] for k in pool) + max(k[i] for k in pool) for i in range(3)]

    def outward(key: _PointKey) -> int:
        return sum((2 * key[i] - doubled[i]) ** 2 for i in range(3))

    def apart(a: _PointKey, b: _PointKey) -> int:
        return sum((a[i] - b[i]) ** 2 for i in range(3))

    chosen = [min(pool, key=lambda key: (-outward(key), key))]
    gap = {key: apart(key, chosen[0]) for key in pool}
    while len(chosen) < min(limit, len(pool)):
        taken = set(chosen)
        best = min((key for key in pool if key not in taken), key=lambda k: (-gap[k], k))
        chosen.append(best)
        for key in pool:
            gap[key] = min(gap[key], apart(key, best))
    return chosen


def _walk_points(adapter: Any, leaf: _ComponentLeaf) -> tuple[tuple[float, float, float], ...]:
    """``leaf``'s body's extreme points along :data:`_WALK_DIRECTIONS`, ranked.

    ``IBody2::GetExtremePoint`` answers from geometry alone, one point per
    direction even on a tie, so which points exist and the order
    :func:`_spread_order` tries them in owe nothing to a face or edge
    enumeration order (which nothing promises), and no face or edge proxy is
    materialised (a gear's toothed face held ~400). Part metres.
    """
    component = _early_bound(leaf.component, "IComponent2")
    body = adapter._attempt(lambda: component.GetBody(), default=None)
    if body is None:
        return ()
    bound = _early_bound(body, "IBody2")
    found: dict[_PointKey, tuple[float, float, float]] = {}
    for direction in _WALK_DIRECTIONS:
        # The wrapper returns the [out] coordinates after the found flag.
        result = tuple(bound.GetExtremePoint(*direction) or ())
        if len(result) == 4 and result[0]:
            point = (float(result[1]), float(result[2]), float(result[3]))
            found.setdefault(_point_key(point), point)
    return tuple(found[key] for key in _spread_order(found, _WALK_POINTS_PER_INSTANCE))


def _entity_owner(adapter: Any, entity: Any) -> str:
    """The full instance path of the component that owns ``entity``; ``""`` if none."""
    if entity is None:
        return ""
    bound = _early_bound(_bind(entity, "IEntity"), "IEntity")
    component = adapter._attempt(lambda: bound.GetComponent(), default=None)
    return _component_path(adapter, component)


# The hit test's zoom window half-span. Fit to sheet, the pick aperture is a
# few pixels of a ~280 mm portrait sheet: millimetres wide, and wider on a
# 1024x640 seat window than on an 820-high one, so the same point returned
# another part's edge on swmaker000008 than on swmaker000004/6. Zoomed ~56x,
# the aperture is a few hundredths of a millimetre on every seat.
_HIT_ZOOM_HALF = 0.0025


@contextlib.contextmanager
def _zoomed_on(adapter: Any, centre: Sequence[float], half: float) -> Iterator[None]:
    """Zoom the drawing window onto a sheet square, then back to fit.

    new_project_drawing fits the sheet so every other coordinate pick sees the
    zoom it was placed under; this restores that zoom on the way out, also
    when the zoom call itself moved the view and then raised. A restore that
    fails after the body failed is noted on the body's error, which is the
    one raised.
    """
    draw = adapter.currentModel
    try:
        draw.ViewZoomTo2(
            centre[0] - half, centre[1] - half, 0.0, centre[0] + half, centre[1] + half, 0.0
        )
        yield
    except BaseException as primary:
        try:
            draw.ViewZoomtofit2()
        except Exception as restore:
            primary.add_note(f"restoring the fit zoom also failed: {restore!r}")
        raise
    draw.ViewZoomtofit2()


def _hit_test_edge(adapter: Any, sheet_xy: Sequence[float]) -> tuple[Any, str]:
    """Select the edge drawn at ``sheet_xy`` of the active view; return it and its owner.

    The pick runs zoomed onto the point (:data:`_HIT_ZOOM_HALF`), so which
    edge it returns does not depend on the seat's window size. In a drawing
    the view is selected alongside the edge; the edge is last. The selection
    is left in place for the caller to use or clear.
    """
    draw = adapter.currentModel
    draw.ClearSelection2(True)
    with _zoomed_on(adapter, sheet_xy, _HIT_ZOOM_HALF):
        selected = draw.Extension.SelectByID2(
            "", "EDGE", sheet_xy[0], sheet_xy[1], 0.0, False, 0, null_callout(), 0
        )
    if not selected:
        return None, ""
    manager = draw.SelectionManager
    edge = manager.GetSelectedObject6(int(manager.GetSelectedObjectCount2(-1)), -1)
    return edge, _entity_owner(adapter, edge)


def _visible_edge_points(
    adapter: Any, view: Any, leaf: _ComponentLeaf
) -> tuple[int, tuple[tuple[tuple[float, float, float], Any], ...]]:
    """How many edges of ``leaf`` the view lists as drawn, and points along them.

    ``IView::GetVisibleEntities2`` lists the edges the view's hidden-line pass
    kept: the fallback for a pin in its bore, whose extreme points sit on an
    outline its neighbour's edge also draws. Listed is not drawn everywhere:
    a washer's rim listed as visible ran behind the gear for most of its
    length. So each listed edge gives points (``ICurve::Evaluate2`` at
    :data:`_EDGE_SAMPLE_FRACTIONS` of its range), each with the listed edge
    it lies on, for the same hit test the walk runs, ranked by
    :func:`_spread_order` since the array's order is undocumented. Counted
    first: an instance drawing more than :data:`_VISIBLE_EDGES_PER_INSTANCE`
    edges is not fetched at all. Part metres.
    """
    bound = _early_bound(view, "IView")
    count = int(bound.GetVisibleEntityCount2(leaf.component, _VIEW_ENTITY_EDGE) or 0)
    if count <= 0 or count > _VISIBLE_EDGES_PER_INSTANCE:
        return count, ()
    found: dict[_PointKey, tuple[tuple[float, float, float], Any]] = {}
    raw = _sw_drawing.raw_visible_entities(view, leaf.component, _VIEW_ENTITY_EDGE)
    for edge in raw[:_VISIBLE_EDGES_PER_INSTANCE]:
        curve = _com_invoke(edge, "IEdge", "GetCurve")
        if curve is None:
            continue
        # GetCurveParams2 reads what GetCurve generated, so GetCurve first.
        params = tuple(float(v) for v in (_com_invoke(edge, "IEdge", "GetCurveParams2") or ()))
        if len(params) < 8:
            continue
        for fraction in _EDGE_SAMPLE_FRACTIONS:
            at = params[6] + fraction * (params[7] - params[6])
            value = tuple(_com_invoke(curve, "ICurve", "Evaluate2", at, 0) or ())
            if len(value) >= 3:
                point = (float(value[0]), float(value[1]), float(value[2]))
                found.setdefault(_point_key(point), (point, edge))
    return count, tuple(found[key] for key in _spread_order(found, _WALK_POINTS_PER_INSTANCE))


@dataclass(frozen=True)
class _PointHit:
    """One hit-tested point: its index in the tried list, sheet point, the
    edge the hit test returned and that edge's owner."""

    index: int
    xy: tuple[float, float]
    edge: Any
    owner: str


def _scan_points(
    adapter: Any,
    view: Any,
    leaf: _ComponentLeaf,
    points: Sequence[tuple[float, float, float]],
    offsets: Mapping[str, tuple[float, float, float]],
    tried: list[tuple[float, float]],
    *,
    stem: str,
    what: str,
    label: str,
) -> tuple[_PointHit | None, _PointHit | None]:
    """Hit-test ``points`` (part metres) in order, stopping at the first
    whose hit returns an edge of exactly ``leaf`` (the claimed point).
    Also returns the first point that hit another part's edge on the way:
    ink is drawn there, shared or in front."""
    if not points:
        return None, None
    projected = model_points_in_view(
        adapter,
        view,
        _anchor_model_points(adapter, leaf, points, offsets, stem=stem, label=label),
        label=f"{label} {stem} {what}",
        names=[f"{stem} {what} {index}" for index in range(len(points))],
    )
    shared = None
    for index, xy in enumerate(projected):
        tried.append(xy)
        hit, owner = _hit_test_edge(adapter, xy)
        found = _PointHit(index=index, xy=xy, edge=hit, owner=owner)
        if owner.casefold() == leaf.path.casefold():
            return found, shared
        if hit is not None and shared is None:
            shared = found
    return None, shared


def _mm_text(values: Sequence[float], scale: float = 1.0) -> str:
    return ",".join(f"{value * scale:.3f}" for value in values)


@_telemetry.traced("drawing.pick_balloon_anchor", label_param="stem")
def _select_balloon_anchor(
    adapter: Any,
    view: Any,
    *,
    stem: str,
    anchor: BalloonAnchor,
    candidates: Sequence[_ComponentLeaf],
    offsets: Mapping[str, tuple[float, float, float]],
    sheet_xy: tuple[float, float] | None,
    label: str,
) -> _AnchorChoice:
    """Find the edge ``stem``'s balloon attaches to, and the sheet point on it.

    One hit test per balloon replaces fetching every visible edge of the
    component and keeping ``edges[0]``: that array's order moved between
    runs (harmonic-base's anchor walk took 17 shapes over 24 frame runs),
    and the nameplate's 37,148 edges cost ~524 s a pick, most of it releasing
    their COM proxies (#1079).

    ``frozen``: hit-test at the anchor's projected ``sheet_xy``. An edge of
    another instance in front of the point, or no edge, raises; the balloon
    never falls back to some other edge.

    ``walk`` (``anchor.point_mm is None``): hit-test the family's first
    instance's body extreme points (:func:`_walk_points`), the instance
    :func:`_shown_instances` put first (the pinned one when the anchor pins
    it), and take the first point the hit test gives back to that exact
    instance. Never a later instance: whether the first instance's points
    are drawn or covered is a hit result, and a hit result must not choose
    which part carries the item (the lag screw walked to lag-screw-2 after
    lag-screw-1's points all hit other parts; that choice is now a pin). A
    pin in its bore draws its outline on its neighbour's, so no extreme
    point may be claimed: ``visible-edge`` then hit-tests points along the
    edges of the same instance the view's hidden-line pass lists as drawn
    (:func:`_visible_edge_points`) and takes the first it claims. When the
    instance claims none but one of those points hits another part's edge,
    the outline is shared ink: ``shared-edge`` attaches to the listed edge
    that point lies on, landing there. When no point finds ink at all, the
    part shows only where no hit test reaches it (cone-tip-bushing-1 sits
    flush in the tip block's bore: none of 24 points hit any edge on runs
    20260928T202401351Z and 20260928T203306681Z): ``listed-edge`` attaches
    to the listed edge holding the first ranked point and lets SolidWorks
    place the leader on it, the one landing no read-back can prove. No
    listed edge fails the sheet, naming what was tried. Which method ran,
    and where, is in the ``drawing.balloon_anchor`` event (``shared`` names
    the other part).

    Every other method returns the hit-tested sheet point, where the
    balloon's leader is then made to land
    (:func:`_create_component_bom_balloon`).
    """
    first = candidates[0]
    instance = first.path
    tried: list[tuple[float, float]] = []
    scan_attrs: dict[str, Any] = {}
    method: AnchorMethod
    if anchor.point_mm is not None:
        if sheet_xy is None:
            raise RuntimeError(f"{label}: {stem} frozen anchor was never projected")
        where = f"sheet ({sheet_xy[0] * 1000.0:.2f}, {sheet_xy[1] * 1000.0:.2f}) mm"
        edge, owner = _hit_test_edge(adapter, sheet_xy)
        tried.append(sheet_xy)
        if edge is None:
            raise RuntimeError(
                f"{label}: {stem} frozen balloon anchor {anchor.point_mm} selects "
                f"no edge at {where} on {instance}"
            )
        if owner.casefold() != instance.casefold():
            adapter.currentModel.ClearSelection2(True)
            raise RuntimeError(
                f"{label}: {stem} frozen balloon anchor {anchor.point_mm} at {where} "
                f"selects an edge of {owner or 'no component'}, not {instance}"
            )
        method, point_mm = "frozen", tuple(anchor.point_mm)
    else:
        walk_points = _walk_points(adapter, first)
        scan_attrs = {"extremes": len(walk_points)}
        claimed, _ = _scan_points(
            adapter, view, first, walk_points, offsets, tried, stem=stem, what="walk", label=label
        )
        if claimed is not None:
            method, point, sheet_xy, edge = "walk", walk_points[claimed.index], claimed.xy, claimed.edge
        else:
            adapter.currentModel.ClearSelection2(True)
            listed, edge_points = _visible_edge_points(adapter, view, first)
            scan_attrs["visible"] = f"{first.path}={listed}"
            claimed, shared = _scan_points(
                adapter, view, first, [point for point, _edge in edge_points], offsets, tried,
                stem=stem, what="edge", label=label,
            )
            if claimed is not None:
                method, edge = "visible-edge", claimed.edge
                point, sheet_xy = edge_points[claimed.index][0], claimed.xy
            elif shared is not None:
                method, (point, edge), sheet_xy = "shared-edge", edge_points[shared.index], shared.xy
                scan_attrs["shared"] = shared.owner or "no component"
            elif edge_points:
                method, (point, edge) = "listed-edge", edge_points[0]
                sheet_xy = tried[len(walk_points)]
            else:
                adapter.currentModel.ClearSelection2(True)
                points_text = "; ".join(
                    f"({x * 1000.0:.2f}, {y * 1000.0:.2f})" for x, y in tried
                )
                raise RuntimeError(
                    f"{label}: {stem} has no verifiably visible edge: no hit test "
                    f"found ink of {first.path} at sheet mm [{points_text}]: "
                    f"{len(walk_points)} body extreme points, then "
                    f"{len(edge_points)} points along its {listed} listed visible "
                    f"edges (sampled when 1-{_VISIBLE_EDGES_PER_INSTANCE})"
                )
        point_mm = tuple(value * 1000.0 for value in point)
    # The span carries what profiling queries group by; the event is what a
    # run-to-run anchor diff compares (App Insights traces, this name).
    _span_scan_attrs(instance=instance, method=method, tried=len(tried), **scan_attrs)
    _telemetry.event(
        "drawing.balloon_anchor",
        stem=stem,
        instance=instance,
        method=method,
        point_mm=_mm_text(point_mm),
        sheet_mm=_mm_text(sheet_xy, 1000.0),
        tried=len(tried),
        **scan_attrs,
    )
    adapter.currentModel.ClearSelection2(True)
    return _AnchorChoice(instance=instance, edge=edge, method=method, sheet_xy=sheet_xy)


def _verify_anchor_attachment(
    adapter: Any, note: Any, *, instance: str, stem: str, label: str
) -> None:
    """The inserted balloon must attach to exactly one edge, of the exact
    instance that was selected (full path, not its last segment)."""
    annotation = _early_bound(_early_bound(note, "INote").GetAnnotation(), "IAnnotation")
    entities = tuple(annotation.GetAttachedEntities3() or ())
    kinds = tuple(int(kind) for kind in (annotation.GetAttachedEntityTypes() or ()))
    owners = [_entity_owner(adapter, entity) for entity in entities]
    if (
        len(entities) != 1
        or kinds != (_SEL_EDGES,)
        or owners[0].casefold() != instance.casefold()
    ):
        raise RuntimeError(
            f"{label}: {stem} balloon must attach to one edge of {instance}; it "
            f"attaches to {len(entities)} entities of types {list(kinds)} owned by "
            f"{owners}"
        )


@dataclass(frozen=True)
class BalloonLanding:
    """One component balloon as :func:`add_component_bom_balloons` proved it:
    attached to one edge of ``instance``, its leader ending at ``sheet_xy``
    (``None`` for a ``listed-edge`` balloon, whose landing SolidWorks chose)."""

    stem: str
    instance: str
    note: Any
    sheet_xy: tuple[float, float] | None
    label: str


def _prove_landing(adapter: Any, landing: BalloonLanding) -> None:
    """``landing``'s balloon attaches to one edge of its instance and, when
    its landing was proven, its leader still ends there."""
    _verify_anchor_attachment(
        adapter, landing.note, instance=landing.instance, stem=landing.stem, label=landing.label
    )
    if landing.sheet_xy is not None:
        _assert_leader_lands(
            _early_bound(_early_bound(landing.note, "INote").GetAnnotation(), "IAnnotation"),
            landing.sheet_xy,
            what=f"{landing.stem} balloon",
            label=landing.label,
            tolerance=_BALLOON_LANDING_TOLERANCE_M,
        )


def assert_balloon_landings(adapter: Any, landings: Sequence[BalloonLanding]) -> None:
    """Prove every balloon's attachment and landing again, all at once.

    The proof at insertion holds only until the next rebuild: each
    ``EditRebuild3`` re-solves every annotation on every sheet, and later
    sheets, notes and the finalizer rebuild after a sheet's balloons are
    checked. Run after the drawing's last rebuild (``finalize_drawing``'s
    ``settled_checks``), this is the state the export prints. Every failing
    balloon is named, not just the first.
    """
    failures = []
    for landing in landings:
        try:
            _prove_landing(adapter, landing)
        except RuntimeError as error:
            failures.append(str(error))
    if failures:
        raise RuntimeError(
            f"{len(failures)} balloon(s) changed after the final rebuild: " + "; ".join(failures)
        )


def _create_component_bom_balloon(
    adapter: Any,
    view: Any,
    *,
    stem: str,
    choice: _AnchorChoice,
    expected_item: str,
    label: str,
) -> BalloonLanding:
    """Attach one BOM balloon to ``stem``'s anchor edge and prove where it landed.

    The edge is selected by entity and the hit-tested sheet point made its
    selection point (``ISelectionMgr.SetSelectionPoint2``), the landing
    :func:`add_surface_finish` measured to 0.01 mm; without it SolidWorks
    ends the leader at its own point on the edge (:class:`_AnchorChoice`).
    A ``shared-edge`` or ``listed-edge`` edge is the model edge the view
    listed, not a hit test's pick, so it is selected through the view. The
    leader must then read back there; a ``listed-edge`` leader has no
    proven point to land on, so SolidWorks places it.
    """
    draw = adapter.currentModel
    listed = choice.method in ("shared-edge", "listed-edge")
    if listed:
        draw.ClearSelection2(True)
        if not _early_bound(view, "IView").SelectEntity(choice.edge, False):
            raise RuntimeError(f"{label}: failed to select {stem}'s listed visible edge")
    else:
        _select_view_entity(
            adapter, view, "EDGE", None, label=f"{label} {stem} anchor", entity=choice.edge
        )
    proven = choice.method != "listed-edge"
    manager = _early_bound(draw.SelectionManager, "ISelectionMgr")
    if proven and manager.SetSelectionPoint2(
        1, -1, choice.sheet_xy[0], choice.sheet_xy[1], 0.0
    ) is not True:
        raise RuntimeError(f"{label}: failed to set {stem}'s balloon landing {choice.sheet_xy}")
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
    landing = BalloonLanding(
        stem=stem,
        instance=choice.instance,
        note=note,
        sheet_xy=choice.sheet_xy if proven else None,
        label=label,
    )
    _prove_landing(adapter, landing)
    return landing


@_telemetry.traced("drawing.component_bom_balloons", label_param="label")
def add_component_bom_balloons(
    adapter: Any,
    view: Any,
    *,
    items: Sequence[tuple[str, str]],
    anchors: Mapping[str, BalloonAnchor],
    label: str,
    margin: float = 0.014,
) -> list[BalloonLanding]:
    """Insert and ring one checked balloon per requested component family.

    Each family's balloon attaches at its anchor in ``anchors``
    (:func:`_select_balloon_anchor`). Every family's instance is chosen and
    every frozen anchor projected in one batch before the first balloon
    exists, so a family without an anchor or a shown instance fails the
    sheet naming it, with nothing half-placed. Returns each balloon's
    :class:`BalloonLanding`, for :func:`assert_balloon_landings` to prove
    again after the drawing's last rebuild.
    """
    if not items:
        raise ValueError(f"{label}: component balloon list must not be empty")
    stems = [stem for stem, _item in items]
    numbers = [item for _stem, item in items]
    if len(stems) != len(set(stems)) or len(numbers) != len(set(numbers)):
        raise ValueError(f"{label}: duplicate component or item number")
    if margin <= 0.0:
        raise ValueError(f"{label}: balloon ring margin must be positive")
    missing = [stem for stem in stems if stem not in anchors]
    if missing:
        raise ValueError(f"{label}: no balloon anchor for {missing}")
    leaves = _view_component_leaves(adapter, view, label=label)
    candidates = {
        stem: _shown_instances(leaves, stem, anchors[stem], label=label)
        for stem in stems
    }
    offsets = _view_explode_offsets(adapter, view, label=label)
    frozen = [stem for stem in stems if anchors[stem].point_mm is not None]
    projected = (
        model_points_in_view(
            adapter,
            view,
            [
                _anchor_model_points(
                    adapter,
                    candidates[stem][0],
                    [tuple(value / 1000.0 for value in anchors[stem].point_mm or ())],
                    offsets,
                    stem=stem,
                    label=label,
                )[0]
                for stem in frozen
            ],
            label=f"{label} balloon anchors",
            names=frozen,
        )
        if frozen
        else []
    )
    sheet_points: dict[str, tuple[float, float]] = dict(zip(frozen, projected))
    draw = adapter.currentModel
    if not _early_bound(draw, "IDrawingDoc").ActivateView(view_name(adapter, view)):
        raise RuntimeError(f"{label}: failed to activate the balloon view")
    # A coordinate hit test reads the view's display geometry: make it current once.
    _early_bound(view, "IView").UpdateViewDisplayGeometry()
    # Every anchor is hit-tested before the first balloon exists: a balloon
    # dropped near its own anchor would otherwise sit on the next family's
    # point and swallow its hit test.
    picks = [
        _select_balloon_anchor(
            adapter,
            view,
            stem=stem,
            anchor=anchors[stem],
            candidates=candidates[stem],
            offsets=offsets,
            sheet_xy=sheet_points.get(stem),
            label=label,
        )
        for stem in stems
    ]
    landings = [
        _create_component_bom_balloon(
            adapter,
            view,
            stem=stem,
            choice=choice,
            expected_item=item,
            label=label,
        )
        for (stem, item), choice in zip(items, picks)
    ]
    _spread_balloons(adapter, view, [landing.note for landing in landings], margin=margin)
    rebuild_drawing(adapter, label="add_component_bom_balloons")
    _telemetry.success(f"{label}: inserted {len(landings)} targeted balloons")
    return landings


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
    rebuild_drawing(adapter, label="add_auto_balloons_across_views")
    _telemetry.success(
        f"{label}: {len(all_balloons)} balloons cover all {expected} BOM items"
    )
    return all_balloons


def drawing_viewport_pixel_size(adapter: Any) -> tuple[float, float]:
    """Return one current viewport pixel in drawing-sheet X/Y metres."""
    view = _early_bound(adapter.currentModel.ActiveView, "IModelView")
    transform = _early_bound(view.Transform, "IMathTransform")
    data = tuple(float(value) for value in transform.ArrayData)
    if len(data) < 13 or not all(math.isfinite(value) for value in data[:13]):
        raise RuntimeError("drawing viewport has no finite model-to-pixel transform")
    scale = abs(data[12])
    pixels_per_metre = (
        scale * math.hypot(data[0], data[1]),
        scale * math.hypot(data[3], data[4]),
    )
    if any(not math.isfinite(value) or value <= 0.0 for value in pixels_per_metre):
        raise RuntimeError("drawing viewport has a degenerate sheet-to-pixel mapping")
    return (1.0 / pixels_per_metre[0], 1.0 / pixels_per_metre[1])


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
    """Move the anchor strictly; ``position_tolerance_m`` floors one-pixel ink bounds."""
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
    circle = rendered_balloon_circle(note, label=label)
    anchor = annotation.GetPosition()
    if anchor is None or len(anchor) < 2:
        raise RuntimeError(f"{label}: item {item_number} has no position read-back")
    target_anchor = (
        float(anchor[0]) + position_xy[0] - circle[0],
        float(anchor[1]) + position_xy[1] - circle[1],
    )
    note.LockPosition = False
    if not annotation.SetPosition(target_anchor[0], target_anchor[1], 0.0):
        raise RuntimeError(f"{label}: failed to position item {item_number}")
    note.LockPosition = True
    rebuild_drawing(adapter, label="position_bom_balloon")
    adapter.currentModel.GraphicsRedraw2()
    current_note = annotation.GetSpecificAnnotation()
    if current_note is None:
        raise RuntimeError(
            f"{label}: item {item_number} note vanished after positioning"
        )
    actual_anchor = tuple(float(value) for value in annotation.GetPosition())
    actual_xy = rendered_balloon_circle(current_note, label=label)[:2]
    pixel_bounds = tuple(
        max(position_tolerance_m, value)
        for value in drawing_viewport_pixel_size(adapter)
    )
    residual = tuple(
        actual - expected for actual, expected in zip(actual_xy, position_xy)
    )
    state = {
        "requested_anchor": target_anchor,
        "actual_anchor": actual_anchor,
        "target_circle": position_xy,
        "actual_circle": actual_xy,
        "residual_xy": residual,
        "pixel_bounds_m": pixel_bounds,
    }
    _telemetry.info(f"{label}: item {item_number} pixel-bounded placement {state!r}")
    if (
        len(actual_anchor) < 2
        or not all(math.isfinite(value) for value in actual_anchor[:2])
        or any(
            abs(actual_anchor[index] - target_anchor[index]) > position_tolerance_m
            for index in range(2)
        )
    ):
        raise RuntimeError(
            f"{label}: item {item_number} native anchor did not persist: {state!r}"
        )
    if any(abs(residual[index]) > pixel_bounds[index] for index in range(2)):
        raise RuntimeError(
            f"{label}: item {item_number} rendered circle exceeds viewport resolution: {state!r}"
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
# projected / section / detail views return "". The part-named octant views
# (``_named_views``, "ISO FRONT-TOP-LEFT") are isometrics of the other seven
# octants and are treated exactly like ``*Isometric`` wherever a pictorial is
# special-cased: this predicate, the finalizer's Shaded With Edges pass and
# the post-export precision assertion.
_PICTORIAL_ORIENTATIONS = frozenset({"*isometric", "*dimetric", "*trimetric"})
_OCTANT_ORIENTATION_PREFIX = "iso "


def is_pictorial_orientation(orientation: str) -> bool:
    """True for ``*Isometric``/``*Dimetric``/``*Trimetric`` and the octant ``ISO …`` views."""
    name = orientation.strip().lower()
    return name in _PICTORIAL_ORIENTATIONS or name.startswith(_OCTANT_ORIENTATION_PREFIX)


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


def _gdt_display(
    adapter: Any, annotation: Any, kind: int, *, name: str
) -> dict[str, Any] | None:
    """A datum tag's or feature-control frame's rendered ink, in sheet space.

    ``IAnnotation::GetDisplayData``, read by the shared layout audit's reader
    (``annotation_display``): lines, arcs, triangles and text runs where
    SolidWorks draws them. NOT the ``IGtol`` / ``IDatumTag`` primitives
    (``GetLineAtIndex`` and kin) this used to read -- on MHA-DT-019 at 4:1
    (pc-gdt-ink-diag, a89a13a7a) a leadered FCF's primitives are a crossed
    2h x 2h placeholder square at the leader's far end plus the leader's last
    run, never the frame, and a datum tag's box lies about (-9.9, -5.0) mm off
    its ink. The display data is where the PDF prints: knife-mount's datum A
    and its leadered three-compartment FCF match their PDF glyphs within
    0.15 mm (layoutcal d09c2b9eb).

    ``None``, with a ``gdt_box.fallback`` event naming the symbol and the
    reason, when there is nothing to read; the caller then falls back.
    A DATUM attached to a display dimension is one such case: its IDatumTag
    primitives were in the dimension's local frame, and whether its display
    data is sheet space is unmeasured, so it keeps the nominal box. A frame
    attached to a dimension reads its display data like any other: a nominal
    square is wrong for an FCF by construction.
    """
    if kind == _ANNOT_DATUM and _datum_is_dimension_attached(adapter, annotation):
        reason = "dimension-attached datum"
    else:
        display, refused = annotation_display(adapter, annotation)
        if display:
            return display
        reason = f"no display data (refused {refused})" if refused else "no display data"
    _telemetry.event("gdt_box.fallback", symbol=name, reason=reason)
    _telemetry.debug(f"{name}: GD&T box falls back to the nominal square: {reason}")
    return None


def _measured_gdt_box(
    adapter: Any, annotation: Any, kind: int, *, name: str
) -> tuple[float, float, float, float] | None:
    """Box a datum tag or feature-control frame from the ink it renders.

    ``_gdt_display``'s display data, every primitive and text run
    (``display_box``). Leader included: that is ink too, and it can cross a
    border on its own. Text below a frame ("BOTH CROWNS") is inside no frame
    line, so its run is boxed at the width SolidWorks reports; a run with
    none is estimated from its glyph count, with a ``gdt_box.text_estimated``
    event.
    """
    display = _gdt_display(adapter, annotation, kind, name=name)
    box = display_box(display) if display else None
    if display and box is None:
        _telemetry.event("gdt_box.fallback", symbol=name, reason="display data draws nothing")
    estimated = estimated_text_runs(display) if display else 0
    if estimated:
        _telemetry.event("gdt_box.text_estimated", symbol=name, runs=estimated)
    return None if box is None else (box.xmin, box.ymin, box.xmax, box.ymax)


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
    measured = _measured_gdt_box(adapter, annotation, kind, name=name)
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


@_telemetry.traced("drawing.finalize")
async def finalize_drawing(
    adapter: Any,
    outputs: DrawingOutputs,
    *,
    layout: DrawingLayout,
    pdf_title: str,
    scale: tuple[float, float] = (1.0, 1.0),
    redundant_note_substrings: Sequence[str] = (),
    expected_redundant_notes: int = 0,
    expected_sheet_names: tuple[str, ...] | None = None,
    sheet_layouts: Mapping[str, DrawingLayout] | None = None,
    sheet_scales: Mapping[str, tuple[float, float]] | None = None,
    settled_checks: Sequence[Callable[[], None]] = (),
) -> dict[str, str]:
    """Enforce the sheet/view contract and export SLDDRW, PDF, and rendered PNG.

    ``settled_checks`` run after the last rebuild, before anything is
    saved: a readback taken when an annotation was placed says nothing
    about the drawing the later rebuilds leave (:func:`assert_balloon_landings`).
    """
    drawing_model = adapter.currentModel
    ddoc = _early_bound(
        drawing_model, "IDrawingDoc"
    )  # IDrawingDoc view for drawing-only methods (same dispatch)
    drawing_model.ClearSelection2(True)
    # The sheet's own build identifier (title block "BUILD $PRP:{BUILD_ID}"):
    # a DRAWING-document property, not a $PRPSHEET link, so it names the build
    # that made this sheet even when the part it shows is older.
    apply_custom_properties(
        adapter, {DRAWING_BUILD_ID_PROPERTY: _build_id()}, model=drawing_model
    )
    sheet_names = tuple(adapter._get_attr_or_call(ddoc, "GetSheetNames") or ())
    if not sheet_names:
        raise RuntimeError("finished drawing has no sheets")
    if expected_sheet_names is not None and sheet_names != expected_sheet_names:
        raise RuntimeError(
            f"drawing sheet contract mismatch: {sheet_names!r} != "
            f"{expected_sheet_names!r}"
        )
    if sheet_layouts is None:
        resolved_layouts = {name: layout for name in sheet_names}
    else:
        if set(sheet_layouts) != set(sheet_names):
            missing = sorted(set(sheet_names) - set(sheet_layouts))
            unknown = sorted(set(sheet_layouts) - set(sheet_names))
            raise ValueError(
                f"sheet layout mapping must cover every sheet exactly; "
                f"missing={missing!r}, unknown={unknown!r}"
            )
        if any(
            not isinstance(sheet_layout, DrawingLayout)
            for sheet_layout in sheet_layouts.values()
        ):
            raise TypeError("every sheet layout must be a DrawingLayout")
        resolved_layouts = dict(sheet_layouts)
    if sheet_scales is not None and set(sheet_scales) != set(sheet_names):
        missing = sorted(set(sheet_names) - set(sheet_scales))
        unknown = sorted(set(sheet_scales) - set(sheet_names))
        raise ValueError(
            f"sheet scale mapping must cover every sheet exactly; "
            f"missing={missing!r}, unknown={unknown!r}"
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
        sheet_scale = scale if sheet_scales is None else sheet_scales[sheet_name]
        # Inserting a model view lets SolidWorks auto-drift the SHEET scale off
        # the 1:1 the template pinned (each view still carries its own explicit
        # scale), so re-pin it once here before asserting the contract.
        if not sheet.SetScale(
            float(sheet_scale[0]), float(sheet_scale[1]), False, False
        ):
            raise RuntimeError(
                f"failed to set final drawing sheet {sheet_name!r} scale"
            )
        assert_asme_b_sheet(
            adapter,
            sheet,
            layout=resolved_layouts[sheet_name],
            phase=f"before save {sheet_name}",
            scale=sheet_scale,
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
                layout=resolved_layouts[sheet_name],
                phase=f"explicit property source {sheet_name}",
                scale=sheet_scale,
            )
        views = tuple(iter_views(adapter))
        first_view = views[0] if views else None
        if first_view is None:
            raise RuntimeError(
                f"drawing sheet {sheet_name!r} has no view for property links"
            )
        for view in views:
            orientation = str(
                adapter._get_attr_or_call(view, "GetOrientationName") or ""
            )
            if not is_pictorial_orientation(orientation):
                continue
            set_high_quality_shaded_with_edges(
                adapter,
                view,
                label=f"{sheet_name} {view_name(adapter, view)!r}",
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
            (
                *TITLE_BLOCK_TOLERANCE_PROPERTIES,
                TITLE_BLOCK_REVISION_PROPERTY,
                TITLE_BLOCK_COPYRIGHT_PROPERTY,
            ),
            required=(
                *TITLE_BLOCK_TOLERANCE_PROPERTIES,
                TITLE_BLOCK_REVISION_PROPERTY,
                TITLE_BLOCK_COPYRIGHT_PROPERTY,
            ),
        )

    # Explicit recipe-requested cleanup remains sheet-scoped. When a standard
    # Isometric view is present, the finalizer owns its high-quality Shaded With
    # Edges mode; every other view keeps the appearance authored by its recipe.
    removed_notes = 0
    # No substrings, no sweep: activating five sheets to match nothing is
    # exactly the cycling a recipe that deletes its own notes is avoiding.
    for sheet_name in sheet_names if redundant_note_substrings else ():
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

    # COM can export before SolidWorks recomputes a changed HLR/HLV view's
    # display geometry: a hidden-lines-visible side view exported as a bare
    # outline while the reopened SLDDRW (which regenerates on load) showed the
    # dashed edges. Flush every view's display geometry HERE, after all the
    # rebuilds above and right before export — the same call at view-placement
    # time is invalidated again by the later annotation/table imports. The
    # views come off each ``ISheet`` by name -- ``ISheet::GetViews`` returns
    # the drawing views alone (unlike ``IDrawingDoc::GetViews``, whose per-sheet
    # rows lead with the sheet's own view) -- so no sheet is activated for this.
    for sheet_name in sheet_names:
        sheet = _early_bound(ddoc.Sheet(str(sheet_name)), "ISheet")
        for raw_view in sheet.GetViews() or ():
            _early_bound(raw_view, "IView").UpdateViewDisplayGeometry()

    if not ddoc.ActivateSheet(sheet_names[0]):
        raise RuntimeError("failed to restore first drawing sheet before export")
    # The ONE settling rebuild for the whole print: per-dimension and
    # per-callout helpers no longer rebuild (their readbacks never needed it),
    # so every text extent and view outline is brought current here, before
    # the SLDDRW/PDF that the blind review and the layout audit read.
    rebuild_drawing(adapter, label="finalize_drawing")
    if settled_checks:
        for settled in settled_checks:
            settled()
        # A check may activate the sheet it reads.
        if not ddoc.ActivateSheet(sheet_names[0]):
            raise RuntimeError("failed to restore first drawing sheet after the settled checks")

    # Persist the native drawing and PDF once from the fully loaded authored
    # document. Reopen/scale/save cycles are deliberately absent from this hot
    # path; the template and precomputed recipe placements own the layout.
    # One child span per SaveAs3: an assembly drawing's save_and_export_pdf
    # runs 42-180 s (harmonic_analyzer_assembly p50 177 s) and nothing said
    # whether the SLDDRW save or the PDF export spends it.
    with _telemetry.span("drawing.save_and_export_pdf"):
        artifacts = save_drawing(
            adapter,
            str(outputs.slddrw),
            pdf_path=str(outputs.pdf),
            artifact_context=lambda kind, _path: _telemetry.span(f"drawing.save_{kind}"),
        )
    if set(artifacts) != {"drawing", "pdf"}:
        raise RuntimeError(f"drawing save/export incomplete: {artifacts!r}")
    # The export just computed every view; the precision flag is truthful now.
    assert_precise_isometric_views(adapter, sheet_names)
    sanitize_pdf_metadata(outputs.pdf, title=pdf_title, expected_pages=len(sheet_names))
    render_pdf_png(
        outputs.pdf,
        outputs.png,
        layout=layout,
        expected_pages=len(sheet_names),
        page_layouts=tuple(resolved_layouts[name] for name in sheet_names),
    )
    artifacts["png"] = str(outputs.png.resolve())
    if set(artifacts) != {"drawing", "pdf", "png"}:
        raise RuntimeError(f"drawing export incomplete: {artifacts!r}")
    # Every sheet of every drawing is audited on the finished, still-open
    # document, next to the PDF it printed (``_drawing_layout_audit``). Under
    # GATE a finding fails the leaf, so no artefact is stored.
    run_layout_audit(
        adapter,
        stem=outputs.slddrw.stem,
        pdf=outputs.pdf,
        report=layout_report_path(outputs.slddrw.stem),
        sheet_layouts=resolved_layouts,
        is_pictorial=is_pictorial_orientation,
    )
    # Release the file: SolidWorks keeps the saved SLDDRW open past the COM
    # session, and the next run (or a from-scratch rebuild deleting the
    # target) then hits "in use by another process".
    title = str(drawing_model.GetTitle())
    adapter.swApp.CloseDoc(title)
    still_open = [
        p
        for p in _visible_document_paths(adapter)
        if Path(p).resolve() == outputs.slddrw.resolve()
    ]
    if still_open:
        raise RuntimeError(f"drawing {title!r} did not close after export")
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
