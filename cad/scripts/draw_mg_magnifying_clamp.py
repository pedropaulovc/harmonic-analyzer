r"""Create the curated machinist drawing for the magnifying-lever clamp.

A 29.50 length of 1/2 hex brass: the Ø6.50 quarter-inch lever bore drilled across
the corners, a #4-40 thumb-screw tap from the top face into the bore and a
blind #4-40 rod tap from the bottom face, both on the hex axis.

Views (3:1, hidden lines removed throughout, drawing-guidelines.md rule 9):

* FRONT (``*Right``, looking along the lever bore at a corner): the block
  height, the bore's height from the bottom seat and its Ø callout. One grouped
  common-flat location applies to the bore and both tap entry axes; all three
  native source measurements remain independently checked.
* TOP and BOTTOM, turned and pinned into third-angle projection above and
  below the front (corners up and down, the flats square to the sheet): the
  flats (stock REF) over the top view, and each tap's native callout.
* SECTION A-A, cut on the hex axis through the corners from the front: the
  bore through the corners, both blind taps in solid lines and the floor
  between the rod tap and the bore, under the part's material crosshatch
  (ANSI31's continuous lines, read back) with the cosmetic threads kept off
  it; the bottom seat carries its flag note.
* Shaded isometric, 2:1.

Run with SolidWorks open::

    uv run python cad\scripts\draw_mg_magnifying_clamp.py mg-magnifying-clamp
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from typing import Any
from types import SimpleNamespace

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    dimension_name,
    place_view,
    remove_notes_matching,
)

from _check import check
from _com import _early_bound
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    stamp_drawing_summary,
)
from _drawing_dimension_import import curate_view_dimensions
from _drawing_dimensions import (
    assert_imported_precision,
    set_dimension_callouts,
    set_reference_dimension,
)
from _drawing_hidden_sketches import curate_view_dimensions as curate_hidden_dimensions
from _drawing_hole_callout import add_native_hole_callout, set_hole_callout_precision
from _drawing_leader_notes import add_attached_note
from _drawing_notes import add_property_linked_note, property_link
from _drawing_precision import _named_dimension
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_sections import create_section_view
from _drawing_view_display import set_hidden_lines_removed
from _gear_drawing_entities import visible_circle_edge
from _gtol_face_read import face_geometry
from _gtol_face_resolve import resolve_faces
from _gtol_planar import PlanarFace
from _hole_callout_thread_class import omit_title_block_thread_class
from _paths import CAD_ROOT
from _session import run_build
import _telemetry
from build_mg_magnifying_clamp import _assert_location_profiles, _assert_ordinary_location, _point_flat_attachment
from mg_magnifying_clamp_spec import (
    AREA_HATCH_STYLE_PATTERN,
    BLOCK_HEIGHT,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    DIMENSION_GROUPS,
    GROUPED_HIDDEN_DIMENSIONS,
    Z_FLAT_DIMENSIONS,
    VISIBLE_DIMENSIONS,
    HEIGHT_CALLOUT,
    HEX_AC,
    HEX_AF,
    LEVER_BORE_CALLOUT,
    LEVER_BORE_DIA,
    LEVER_BORE_Y,
    PREF_MATERIAL_HATCH_PATTERN,
    PREF_MATERIAL_HATCH_STYLE,
    PREF_NO_OPTION,
    REFERENCE_DIMENSIONS,
    ROD_TAP_DRILL_DIA,
    ROD_TAP_PROCESS,
    SEAT_NOTE,
    SECTION_HATCH_PATTERN,
    STOCK_NOTE,
    TAP_CALLOUT_PRECISION,
    TAP_DRILL_DEPTH_VARIABLE,
    TAP_THREAD_DEPTH_VARIABLE,
    THUMB_TAP_PROCESS,
)


SPEC = DRAWINGS_BY_NAME["mg_magnifying_clamp"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"],
    pdf=SPEC.outputs["pdf"],
    png=SPEC.outputs["png"],
)
SLDDRW = OUTPUTS.slddrw
PDF = OUTPUTS.pdf
PNG = OUTPUTS.png

# A nominal 14.66 x 12.70 x 29.50 hex with one common-flat location group.
SHEET_SCALE = (3.0, 1.0)
VIEW_SCALE = (3, 1)
ISO_SCALE = (2, 1)
_S = SHEET_SCALE[0] / SHEET_SCALE[1] / 1000.0  # sheet m per model mm

# The projection column: the front at mid-height, the top and bottom views in
# line with it (their centres pinned to the front's hex axis).
RIGHT_CENTER = (0.085, 0.1272)
TOP_CENTER = (RIGHT_CENTER[0], 0.2175)
BOTTOM_CENTER = (RIGHT_CENTER[0], 0.045)
# The section high enough that its caption clears the title block
# (x > ~0.216, y < ~0.066); the isometric right of it, inside the border.
SECTION_CENTER = (0.250, 0.170)
ISO_CENTER = (0.365, 0.190)
# Note positions are their text's top-left corners.
STOCK_NOTE_XY = (0.305, 0.140)
# Above the iso: R17's real stock-flat leader crosses the lower caption lane.
ISO_NOTE_XY = (0.335, 0.245)
SEAT_NOTE_XY = (0.287, 0.116)

_HALF_AF = HEX_AF / 2.0 * _S
_HALF_AC = HEX_AC / 2.0 * _S


def _elev_y(center: tuple[float, float], model_y_mm: float) -> float:
    """Sheet y of a height above the bottom face in the front view or the
    section (both centred on the block's height)."""
    return center[1] + (model_y_mm - BLOCK_HEIGHT / 2.0) * _S


_BORE_SHEET_Y = _elev_y(RIGHT_CENTER, LEVER_BORE_Y)
_RIGHT_LEFT_X = RIGHT_CENTER[0] - _HALF_AF

# The front view: both heights to the left; the bore callout in its right-hand lane.
RIGHT_KEEP = {
    "Height": (0.036, 0.1555),
    "LeverBoreYDim": (_RIGHT_LEFT_X - 0.012, _elev_y(RIGHT_CENTER, LEVER_BORE_Y / 2.0)),
    "LeverBoreDiaDim": (0.150, 0.145),
}
# The top view: the flats (Z, sheet horizontal) above it, between its upper
# vertices.
TOP_KEEP = {"HexAf": (TOP_CENTER[0], TOP_CENTER[1] + _HALF_AC + 0.010)}
RIGHT_LOCATION_KEEP = {
    # All three values are imported/read back; only the verified group leader prints.
    name: (0.050, 0.1755) for name in Z_FLAT_DIMENSIONS
}
TOP_LOCATION_KEEP = {"ThumbTapFromDiagonalFlat": (0.043, 0.186)}
BOTTOM_KEEP = {"RodTapFromDiagonalFlat": (0.043, 0.074)}

# Preserve the honest height function while wrapping its native below-text.
HEIGHT_DRAWING_CALLOUT = HEIGHT_CALLOUT.replace("TOP-TAP WALL", "TOP-TAP\nWALL")

DIMENSION_CALLOUTS = {
    "Height": HEIGHT_DRAWING_CALLOUT,
    "LeverBoreDiaDim": LEVER_BORE_CALLOUT,
    "LeverBoreFromZFlat": "BORE AND BOTH\nTAP ENTRY AXES",
}

# The tap callouts (their text centres) out to the right of each end view,
# low enough that each leader crosses the right-hand flat, under the flat's
# upper vertex and the HexAf witness standing on it.
THUMB_TAP_CALLOUT_XY = (0.165, TOP_CENTER[1] + 0.010)
ROD_TAP_CALLOUT_XY = (0.150, BOTTOM_CENTER[1] + 0.008)
# SolidWorks' own descriptive note for a Hole Wizard tap ("#4-40 Tapped Hole").
TAPPED_HOLE_NOTE = "Tapped Hole"

# The section's cutting line: vertical through the hex axis on the front view,
# past the block top and bottom.
_SECTION_OVERSHOOT = 0.006
# The seat flag's pick stands a third of the half-width off the hex axis,
# clear of the rod tap; the section is symmetric about the axis, so a
# mirrored section lands it on the same face.
_PICK_DX = 0.35 * _HALF_AC

# Third-angle projection of the front (``*Right``: +Z to sheet left, +Y up):
# the top view sees +X (toward the front's viewer) down the sheet, the bottom
# view up it; both keep +Z to the left.  Model axes, 1 mm long, in metres.
_AXES = {"+X": (0.001, 0.0, 0.0), "+Y": (0.0, 0.001, 0.0), "+Z": (0.0, 0.0, 0.001)}
FRONT_AXES = {"+Z": math.pi, "+Y": math.pi / 2.0}
TOP_AXES = {"+X": -math.pi / 2.0, "+Z": math.pi}
BOTTOM_AXES = {"+X": math.pi / 2.0, "+Z": math.pi}
PROJECTION_ANGLE_SLOP = 1e-6
PROJECTION_SLOP_M = 1e-5

# swAnnotationType_e: swCosmeticThread, swCenterMarkSym.
_COSMETIC_THREAD_ANNOTATION = 1
_CENTER_MARK_ANNOTATION = 13
_SECTION_THREAD_LAYER = "MG-CLAMP-SECTION-THREADS-HIDDEN"

# swDimensionTextParts_e definitions (5-8) and the writable part each is set
# through (1-4) -- the draw_mg_output_fixture convention.
_CALLOUT_DEFINITION_PARTS = {5: 1, 6: 2, 7: 3, 8: 4}
_THREAD_DEPTH_TOKEN = f"<{TAP_THREAD_DEPTH_VARIABLE}>"
_DRILL_DEPTH_TOKEN = f"<{TAP_DRILL_DEPTH_VARIABLE}>"


def reference_thread_depth_definitions(definitions: dict[int, str]) -> dict[int, str]:
    """The thumb tap callout's definitions with the thread depth's variable
    bracketed REF, ``(<hw-threaddepth>)``: the lever bore ends that thread
    (ASME Y14.5 reference); the drill depth governs and stays bare."""
    joined = "\n".join(definitions.values())
    if (
        joined.count(_THREAD_DEPTH_TOKEN) != 1
        or f"({_THREAD_DEPTH_TOKEN}" in joined
        or joined.count(_DRILL_DEPTH_TOKEN) != 1
        or f"({_DRILL_DEPTH_TOKEN}" in joined
    ):
        raise RuntimeError(
            f"expected one bare {_THREAD_DEPTH_TOKEN} and one bare "
            f"{_DRILL_DEPTH_TOKEN} in the thumb tap callout: {definitions!r}"
        )
    return {
        part: text.replace(_THREAD_DEPTH_TOKEN, f"({_THREAD_DEPTH_TOKEN})")
        for part, text in definitions.items()
    }


def _reference_thread_depth(display: Any) -> None:
    before = {
        part: str(display.GetText(part) or "") for part in _CALLOUT_DEFINITION_PARTS
    }
    wanted = reference_thread_depth_definitions(before)
    (part,) = [part for part in before if wanted[part] != before[part]]
    display.SetText(_CALLOUT_DEFINITION_PARTS[part], wanted[part])
    after = {
        part: str(display.GetText(part) or "") for part in _CALLOUT_DEFINITION_PARTS
    }
    if after != wanted:
        raise RuntimeError(
            f"thumb tap thread depth did not persist as REF: wanted {wanted!r}, "
            f"read {after!r}"
        )
    _telemetry.success(f"thumb tap thread depth bracketed REF: {wanted[part]!r}")


def _axis_direction(
    adapter: Any, view: Any, axis: tuple[float, float, float], label: str
) -> tuple[float, float]:
    origin = model_point_in_view(
        adapter, view, (0.0, 0.0, 0.0), label=f"{label} origin"
    )
    tip = model_point_in_view(adapter, view, axis, label=f"{label} tip")
    return tip[0] - origin[0], tip[1] - origin[1]


def _require_axes(adapter: Any, view: Any, axes: dict[str, float], label: str) -> None:
    for name, angle in axes.items():
        dx, dy = _axis_direction(adapter, view, _AXES[name], f"{label} {name}")
        if (
            abs(math.hypot(dx, dy) - _S) > PROJECTION_SLOP_M
            or abs(math.remainder(math.atan2(dy, dx) - angle, math.tau))
            > PROJECTION_ANGLE_SLOP
        ):
            raise RuntimeError(
                f"{label} {name}: projected axis {(dx, dy)} is not at {angle:g} rad"
            )


def _project_end_view(
    adapter: Any,
    front: Any,
    end: Any,
    *,
    axes: dict[str, float],
    center_y: float,
    label: str,
) -> None:
    """Turn a named end view into the front's third-angle projection and pin
    its hex axis under the front's (the draw_mg_output_fixture recipe)."""
    native = _early_bound(end, "IView")
    dx, dy = _axis_direction(adapter, native, _AXES["+X"], f"{label} +X before")
    if math.hypot(dx, dy) <= PROJECTION_SLOP_M:
        raise RuntimeError(f"{label} +X has no measurable projected direction")
    # No assumed quarter turn: rotate the measured +X onto its projection.
    native.Angle = float(native.Angle) + axes["+X"] - math.atan2(dy, dx)
    rebuild_drawing(adapter, label=f"turn clamp {label} view")
    _require_axes(adapter, native, axes, label)
    front_origin = model_point_in_view(
        adapter, front, (0.0, 0.0, 0.0), label="front origin"
    )
    target = (front_origin[0], center_y)
    at = model_point_in_view(adapter, native, (0.0, 0.0, 0.0), label=f"{label} origin")
    position = tuple(float(value) for value in native.Position)
    moved = [position[axis] + target[axis] - at[axis] for axis in range(2)]
    if native.SetViewPosition(double_array(moved), False) is not True:
        raise RuntimeError(f"failed to pin the clamp {label} view in projection")
    rebuild_drawing(adapter, label=f"pin clamp {label} view")
    at = model_point_in_view(
        adapter, native, (0.0, 0.0, 0.0), label=f"{label} origin pinned"
    )
    if math.dist(at, target) > PROJECTION_SLOP_M:
        raise RuntimeError(
            f"clamp {label} origin {at} is not in line with the front's {target}"
        )
    _telemetry.success(f"clamp {label} view in projection: origin {at}")


def _face_hatches(section: Any) -> list[Any]:
    """The section's IFaceHatch objects.  The returned array can carry null
    slots (the API's own VBA example reads from index 1), so drop them."""
    view = _early_bound(section, "IView")
    return [
        _early_bound(raw, "IFaceHatch")
        for raw in (view.GetFaceHatches() or ())
        if raw is not None
    ]


def _assert_material_hatch(section: Any) -> None:
    """Prove section A-A hatches in the part's material crosshatch, ANSI31.

    IFaceHatch's Pattern and Definition are get-only, so the part build sets
    the crosshatch (mg_magnifying_clamp_spec.SECTION_HATCH_PATTERN); this only
    reads back.  The referenced part's two preferences must hold it, and every
    face hatch the view returns (GetFaceHatches may give only null slots on a
    fresh section) must use the material hatch in that pattern."""
    view = _early_bound(section, "IView")
    part = _early_bound(view.ReferencedDocument, "IModelDoc2")
    extension = _early_bound(part.Extension, "IModelDocExtension")
    style = int(
        extension.GetUserPreferenceInteger(PREF_MATERIAL_HATCH_STYLE, PREF_NO_OPTION)
    )
    pattern = str(
        extension.GetUserPreferenceString(PREF_MATERIAL_HATCH_PATTERN, PREF_NO_OPTION)
    )
    if style != AREA_HATCH_STYLE_PATTERN or pattern != SECTION_HATCH_PATTERN:
        raise RuntimeError(
            f"clamp part crosshatch is style {style}, pattern {pattern!r}; "
            f"wanted {AREA_HATCH_STYLE_PATTERN}, {SECTION_HATCH_PATTERN!r}"
        )
    pattern_id = SECTION_HATCH_PATTERN.split()[0]
    read = [
        (bool(hatch.UseMaterialHatch), str(hatch.Pattern))
        for hatch in _face_hatches(section)
    ]
    if any(
        not material or not hatch_pattern.upper().startswith(pattern_id)
        for material, hatch_pattern in read
    ):
        raise RuntimeError(
            f"section A-A face hatch is not the {pattern_id} material hatch: {read!r}"
        )
    _telemetry.success(
        f"section A-A material crosshatch {pattern!r} (style {style}); "
        f"{view.GetFaceHatchCount()} face hatch(es), read {read!r}"
    )


def _hide_cosmetic_threads(adapter: Any, view: Any, *, label: str) -> int:
    """Keep the taps' cosmetic-thread ink out of a section (rule 9: a section
    never carries hidden lines); the callouts state both threads.  The
    draw_dt_cone_tip_block hidden-layer recipe."""
    manager = _early_bound(adapter.currentModel.GetLayerManager(), "ILayerMgr")
    layer = manager.GetLayer(_SECTION_THREAD_LAYER)
    if layer is None:
        if (
            int(
                manager.AddLayer(
                    _SECTION_THREAD_LAYER, "clamp section thread ink hidden", 0, 0, 0
                )
            )
            != 1
        ):
            raise RuntimeError("failed to add the clamp section thread layer")
        layer = manager.GetLayer(_SECTION_THREAD_LAYER)
    layer = _early_bound(layer, "ILayer")
    layer.Visible = False
    if bool(layer.Visible) or bool(layer.Printable):
        raise RuntimeError("the clamp section thread layer is not hidden")
    hidden = 0
    for raw_annotation in _early_bound(view, "IView").GetAnnotations() or ():
        annotation = _early_bound(raw_annotation, "IAnnotation")
        if int(annotation.GetType()) != _COSMETIC_THREAD_ANNOTATION:
            continue
        annotation.Layer = _SECTION_THREAD_LAYER
        if str(annotation.Layer or "") != _SECTION_THREAD_LAYER:
            raise RuntimeError(
                f"clamp {label} cosmetic thread refused the hidden layer"
            )
        hidden += 1
    if not hidden:
        raise RuntimeError(f"clamp {label} has no cosmetic thread to hide")
    rebuild_drawing(adapter, label=f"hide clamp {label} cosmetic threads")
    return hidden


def _require_one_center_mark(view: Any, label: str) -> None:
    """The template's own tap centre mark, once."""
    marks = tuple(
        _early_bound(view, "IView").GetAnnotationsByType(_CENTER_MARK_ANNOTATION) or ()
    )
    if len(marks) != 1:
        raise RuntimeError(
            f"expected one tap centre mark on the {label} view, found {len(marks)}"
        )


def _omit_tap_thread_class(display: Any, *, label: str) -> None:
    omit_title_block_thread_class(display, label=label)
    native = _early_bound(display, "IDisplayDimension")
    if any("2B" in str(native.GetText(part) or "") for part in (1, 2, 3, 4)):
        raise RuntimeError(f"{label}: resolved native callout repeats title-block 2B")


def _add_stock_note(adapter: Any, view: Any) -> None:
    """Use the supplied flat's drawing-context face, with exact source proof."""
    native = _early_bound(view, "IView")
    app = _early_bound(adapter.swApp, "ISldWorks")
    audit = {
        "stage": "stock.source_face", "source_context": "referenced part",
        "selection_context": "target drawing view", "diagnostic_errors": [],
    }
    missing = object()
    source_face = face = extension = None
    notes_before = missing

    def diagnostic(row: dict[str, Any], field: str, member: str, reader: Any, *, record: bool = True) -> Any:
        try:
            value = reader()
        except Exception as exc:
            audit["diagnostic_errors"].append({
                "field": field, "member": member, "type": type(exc).__name__, "message": str(exc),
            })
            return missing
        if record:
            row[field] = value
        return value

    def emit() -> None:
        evidence = json.dumps(audit, sort_keys=True, default=repr)
        _telemetry.info(
            f"clamp stock face audit: {evidence}",
            operation_stage=audit["stage"], auditJSON=evidence,
        )

    try:
        model = native.ReferencedDocument
        if model is None:
            raise RuntimeError("supplied hex stock flat: view has no referenced part")
        selector = PlanarFace((0.0, 0.0, 1.0), HEX_AF / 2.0)
        source_face = resolve_faces(model, {"supplied_hex_flat": selector})["supplied_hex_flat"]
        audit["stage"] = "stock.source_self"
        audit["source_self"] = app.IsSame(source_face, source_face)
        if audit["source_self"] != 1:
            raise RuntimeError("supplied hex stock flat: source face identity is unavailable")
        # Select4 requires an entity from the active document. Follow the
        # output-fixture's feature -> view face -> source correspondence, not
        # a part-body face selected into a drawing or a geometry/FaceID alias.
        audit["stage"] = "stock.view_feature"
        feature = _early_bound(model, "IPartDoc").FeatureByName("Block")
        if feature is None:
            raise RuntimeError("supplied hex stock flat: source has no Block feature")
        view_feature = _early_bound(native.GetCorresponding(feature), "IFeature")
        if view_feature is None:
            raise RuntimeError("supplied hex stock flat: Block has no drawing-view correspondence")
        audit["stage"] = "stock.view_flat"
        feature_faces = tuple(view_feature.GetFaces() or ())
        matches = []
        for candidate in feature_faces:
            geometry = face_geometry(candidate)
            if geometry is not None and selector.matches(geometry):
                matches.append(candidate)
        audit["view_feature_faces"] = len(feature_faces)
        audit["view_flat_candidates"] = len(matches)
        if len(matches) != 1:
            raise RuntimeError(f"supplied hex stock flat: expected one drawing-view flat, found {len(matches)}")
        face = matches[0]
        audit["stage"] = "stock.view_self"
        audit["view_self"] = app.IsSame(face, face)
        if audit["view_self"] != 1:
            raise RuntimeError("supplied hex stock flat: drawing face identity is unavailable")
        audit["stage"] = "stock.source_correspondence"
        extension = _early_bound(_early_bound(model, "IModelDoc2").Extension, "IModelDocExtension")
        canonical = extension.GetCorrespondingEntity2(face)
        audit["canonical_present"] = canonical is not None
        if canonical is None:
            raise RuntimeError("supplied hex stock flat: drawing face has no source correspondence")
        audit["stage"] = "stock.canonical_self"
        audit["canonical_self"] = app.IsSame(canonical, canonical)
        audit["stage"] = "stock.source_same"
        audit["source_same"] = app.IsSame(canonical, source_face)
        if audit["canonical_self"] != 1 or audit["source_same"] != 1:
            raise RuntimeError("supplied hex stock flat: drawing face does not prove exact source identity")
        diagnostic(audit, "raw_source_vs_view", "ISldWorks.IsSame", lambda: app.IsSame(source_face, face))
        notes_before = diagnostic(audit, "notes_before", "IView.GetNotes", lambda: tuple(native.GetNotes() or ()), record=False)
        if notes_before is not missing:
            audit["view_note_count_before"] = len(notes_before)
        audit["stage"] = "stock.attach"
        emit()
        note = add_attached_note(adapter, view, text=property_link("Manufacturing Notes"), entity_type="FACE", entity=face, attached_to=face, note_xy=STOCK_NOTE_XY, label="supplied hex stock flat")
        audit["stage"] = "stock.resolved_property"
        resolved = str(_early_bound(note, "INote").GetText() or "").replace("\r\n", "\n").replace("\r", "\n").strip()
        if resolved != STOCK_NOTE:
            raise RuntimeError(f"supplied hex stock flat: model property did not resolve: {resolved!r}")
        audit["stage"] = "stock.complete"
        emit()
    except Exception as original:
        audit["failure"] = {"type": type(original).__name__, "message": str(original)}
        # A strict helper failure can precede its INote return. Inspect the
        # documented view-note inventory, without guessing which note is new
        # or replacing the original failure with an optional diagnostic error.
        try:
            notes = diagnostic(audit, "view_notes", "IView.GetNotes", lambda: tuple(native.GetNotes() or ()), record=False)
            if notes is not missing:
                audit["view_notes"] = []
                for index, raw_note in enumerate(notes):
                    row: dict[str, Any] = {"index": index}
                    audit["view_notes"].append(row)
                    note = _early_bound(raw_note, "INote")
                    row["note_present"] = note is not None
                    if note is None:
                        continue
                    diagnostic(row, "text", "INote.GetText", lambda: note.GetText())
                    diagnostic(row, "self", f"ISldWorks.IsSame(note[{index}],note[{index}])", lambda: app.IsSame(note, note))
                    if notes_before is not missing:
                        row["same_to_before"] = []
                        for previous_index, previous in enumerate(notes_before):
                            if previous is None:
                                row["same_to_before"].append({"index": previous_index, "unavailable": True, "reason": "prior note handle is None"})
                                continue
                            code = diagnostic(row, f"before[{previous_index}]", "ISldWorks.IsSame", lambda: app.IsSame(note, previous), record=False)
                            row["same_to_before"].append({"index": previous_index, "unavailable": True} if code is missing else {"index": previous_index, "code": code})
                    annotation = diagnostic(row, "annotation", "INote.GetAnnotation", lambda: _early_bound(note.GetAnnotation(), "IAnnotation"), record=False)
                    if annotation is missing or annotation is None:
                        row["annotation_present"] = False if annotation is None else None
                        continue
                    row["annotation_present"] = True
                    diagnostic(row, "count", "IAnnotation.GetAttachedEntityCount3", lambda: annotation.GetAttachedEntityCount3())
                    types = diagnostic(row, "types", "IAnnotation.GetAttachedEntityTypes", lambda: tuple(annotation.GetAttachedEntityTypes() or ()))
                    diagnostic(row, "dangling", "IAnnotation.IsDangling", lambda: annotation.IsDangling())
                    diagnostic(row, "leaders", "IAnnotation.GetLeaderCount", lambda: annotation.GetLeaderCount())
                    diagnostic(row, "owner_type", "IAnnotation.OwnerType", lambda: annotation.OwnerType)
                    owner = diagnostic(row, "owner", "IAnnotation.Owner", lambda: annotation.Owner, record=False)
                    row["owner_present"] = None if owner is missing else owner is not None
                    if owner is not missing and owner is not None:
                        diagnostic(row, "owner_self", f"ISldWorks.IsSame(note_owner[{index}],note_owner[{index}])", lambda: app.IsSame(owner, owner))
                        if row.get("owner_type") == 0:
                            diagnostic(row, "owner_to_view", f"ISldWorks.IsSame(note_owner[{index}],target_view)", lambda: app.IsSame(owner, native))
                    attached = diagnostic(row, "entities", "IAnnotation.GetAttachedEntities3", lambda: tuple(annotation.GetAttachedEntities3() or ()), record=False)
                    if attached is missing:
                        continue
                    row["entities_reported"], row["attachments"] = len(attached), []
                    for entity_index, entity in enumerate(attached):
                        item = {"index": entity_index, "present": entity is not None}
                        row["attachments"].append(item)
                        if entity is None:
                            continue
                        diagnostic(item, "self", f"ISldWorks.IsSame(attached[{entity_index}],attached[{entity_index}])", lambda: app.IsSame(entity, entity))
                        if face is not None:
                            diagnostic(item, "view_same", f"ISldWorks.IsSame(attached[{entity_index}],view_face)", lambda: app.IsSame(entity, face))
                        if extension is not None and types is not missing and entity_index < len(types) and types[entity_index] == 2:
                            canonical = diagnostic(item, "source", "IModelDocExtension.GetCorrespondingEntity2", lambda: extension.GetCorrespondingEntity2(entity), record=False)
                            item["source_present"] = None if canonical is missing else canonical is not None
                            if canonical is not missing and canonical is not None and source_face is not None:
                                diagnostic(item, "source_same", f"ISldWorks.IsSame(attached_source[{entity_index}],source_face)", lambda: app.IsSame(canonical, source_face))
        except Exception as diagnostic_error:
            audit["diagnostic_errors"].append({
                "field": "failure_inventory", "type": type(diagnostic_error).__name__, "message": str(diagnostic_error),
            })
        try:
            emit()
        except Exception:
            pass  # Optional logging must never replace the actual native failure.
        raise


def _flat_group_annotations(adapter: Any, view: Any, annotations: list[Any]) -> dict[str, Any]:
    """Read all three genuine imported dimensions and their independently checked source."""
    native_view = _early_bound(view, "IView")
    source = _early_bound(native_view.ReferencedDocument, "IModelDoc2")
    if source is None:
        raise RuntimeError("common-flat group has no referenced part")
    source_adapter = SimpleNamespace(currentModel=source, swApp=adapter.swApp)
    _assert_location_profiles(source_adapter)
    found = {name: [] for name in Z_FLAT_DIMENSIONS}
    for raw in annotations:
        annotation = _early_bound(raw, "IAnnotation")
        name = dimension_name(adapter, annotation)
        if name in found:
            found[name].append(annotation)
    if any(len(values) != 1 for values in found.values()):
        raise RuntimeError(f"common-flat group requires all three native imports: { {name: len(values) for name, values in found.items()} }")
    result = {}
    for name, (annotation,) in found.items():
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        dimension = _early_bound(display.GetDimension2(0), "IDimension")
        _assert_ordinary_location(display, dimension, name)
        full_name = dimension.FullName
        source_display, source_dimension = _named_dimension(source_adapter, "LeverBoreLocationProfile", name)
        source_full_name = _early_bound(source_dimension, "IDimension").FullName
        if type(full_name) is not str or full_name.split("@")[:2] != [name, "LeverBoreLocationProfile"] or full_name != source_full_name:
            raise RuntimeError(f"{name}: imported source owner differs: actual={full_name!r}, source={source_full_name!r}")
        source_annotation = _early_bound(_early_bound(source_display, "IDisplayDimension").GetAnnotation(), "IAnnotation")
        source_entities = tuple(source_annotation.GetAttachedEntities3() or ())
        source_types = tuple(source_annotation.GetAttachedEntityTypes() or ())
        if len(source_entities) != 2 or len(source_types) != 2:
            raise RuntimeError(f"{name}: source attachment census changed during drawing readback")
        flats = [entity for entity, kind in zip(source_entities, source_types, strict=True) if type(kind) is int and kind == 10]
        if len(flats) != 1:
            raise RuntimeError(f"{name}: source common flat unavailable: types={source_types!r}")
        source_point = _point_flat_attachment(source_adapter, source_display, flats[0], stage=f"{name}.drawing-source")
        imported_point = _point_flat_attachment(source_adapter, display, flats[0], stage=f"{name}.drawing-import", drawing_view=native_view)
        if imported_point != source_point:
            raise RuntimeError(f"{name}: imported native point identity differs: actual={imported_point!r}, source={source_point!r}")
        result[name] = annotation
    return result


def _assert_grouped_flat_locations(adapter: Any, view: Any, annotations: list[Any]) -> None:
    group = _flat_group_annotations(adapter, view, annotations)
    visibility = {name: annotation.Visible for name, annotation in group.items()}
    wanted = {name: 3 if name in GROUPED_HIDDEN_DIMENSIONS else 1 for name in group}
    if any(type(value) is not int for value in visibility.values()) or visibility != wanted:
        raise RuntimeError(f"common-flat group native visibility differs: {visibility!r}")
    for leader, members in DIMENSION_GROUPS.items():
        display = _early_bound(group[leader].GetSpecificAnnotation(), "IDisplayDimension")
        if display.GetText(1) != f"{len(members)}X ":
            raise RuntimeError("common-flat group lost its actual member-count prefix")
    _telemetry.info("clamp common-flat group: three measured sources, one visible native dimension", source_dimension_count=len(group), visible_dimension_count=sum(value == 1 for value in visibility.values()), native_visibility=repr(visibility))


def _group_flat_locations(adapter: Any, view: Any, annotations: list[Any]) -> None:
    group = _flat_group_annotations(adapter, view, annotations)
    for leader, members in DIMENSION_GROUPS.items():
        _early_bound(group[leader].GetSpecificAnnotation(), "IDisplayDimension").SetText(1, f"{len(members)}X ")
    for name, annotation in group.items():
        annotation.Visible = 3 if name in GROUPED_HIDDEN_DIMENSIONS else 1
    _early_bound(adapter.currentModel, "IModelDoc2").GraphicsRedraw2()
    _assert_grouped_flat_locations(adapter, view, annotations)


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open magnifying-clamp source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Isometric View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Magnifying Clamp Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "magnifying clamp; 1/2 hex brass; lever bore across corners; two #4-40 taps",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=VIEW_SCALE)
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=VIEW_SCALE)
    bottom = place_view(
        adapter, str(SOURCE), "*Bottom", *BOTTOM_CENTER, scale=VIEW_SCALE
    )
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (right, top, bottom, iso):
        set_hidden_lines_removed(adapter, view)
    _require_axes(adapter, _early_bound(right, "IView"), FRONT_AXES, "front")
    _project_end_view(
        adapter, right, top, axes=TOP_AXES, center_y=TOP_CENTER[1], label="top"
    )
    _project_end_view(
        adapter,
        right,
        bottom,
        axes=BOTTOM_AXES,
        center_y=BOTTOM_CENTER[1],
        label="bottom",
    )
    section = create_section_view(
        adapter,
        right,
        line_start=(
            RIGHT_CENTER[0],
            _elev_y(RIGHT_CENTER, BLOCK_HEIGHT) + _SECTION_OVERSHOOT,
        ),
        line_end=(RIGHT_CENTER[0], _elev_y(RIGHT_CENTER, 0.0) - _SECTION_OVERSHOOT),
        view_xy=SECTION_CENTER,
        section_label="A",
        scale=VIEW_SCALE,
        label="hex-axis section through the corners",
    )
    set_hidden_lines_removed(adapter, section)
    _assert_material_hatch(section)
    hidden = _hide_cosmetic_threads(adapter, section, label="section A-A")
    _telemetry.info(f"hid {hidden} cosmetic thread(s) in section A-A")

    right_annotations = curate_view_dimensions(
        adapter,
        right,
        keep=RIGHT_KEEP,
        view_label="front",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    top_annotations = curate_view_dimensions(
        adapter,
        top,
        keep=TOP_KEEP,
        view_label="top",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    curate_view_dimensions(
        adapter,
        bottom,
        keep={},
        view_label="bottom",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    for view, feature, keep, view_annotations in (
        (right, "LeverBoreLocationProfile", RIGHT_LOCATION_KEEP, right_annotations),
        (top, "ThumbTapLocationProfile", TOP_LOCATION_KEEP, top_annotations),
    ):
        view_annotations.extend(curate_hidden_dimensions(adapter, view, keep=keep, view_label=feature, dimensions_by_feature={feature: DRAWING_DIMENSIONS[feature]}))
    bottom_annotations = curate_hidden_dimensions(adapter, bottom, keep=BOTTOM_KEEP, view_label="rod tap ordinary entry locations", dimensions_by_feature={"RodTapLocationProfile": DRAWING_DIMENSIONS["RodTapLocationProfile"]})
    # Places are authored on the part; the sheet only proves the import kept them.
    assert_imported_precision(
        adapter, [*right_annotations, *top_annotations, *bottom_annotations], DRAWING_PRECISION_BY_NAME
    )
    locations = set(RIGHT_LOCATION_KEEP) | set(TOP_LOCATION_KEEP) | set(BOTTOM_KEEP)
    for raw_annotation in (*right_annotations, *top_annotations, *bottom_annotations):
        annotation = _early_bound(raw_annotation, "IAnnotation")
        name = dimension_name(adapter, annotation)
        if name not in locations:
            continue
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        dimension = _early_bound(display.GetDimension2(0), "IDimension")
        _assert_ordinary_location(display, dimension, name)
    set_dimension_callouts(adapter, right_annotations, DIMENSION_CALLOUTS)
    _group_flat_locations(adapter, right, right_annotations)
    bore_annotation = next(a for a in right_annotations if dimension_name(adapter, a) == "LeverBoreDiaDim")
    bore_display = _early_bound(_early_bound(bore_annotation, "IAnnotation").GetSpecificAnnotation(), "IDisplayDimension")
    bore_dimension = _early_bound(bore_display.GetDimension2(0), "IDimension")
    if int(_early_bound(bore_dimension.Tolerance, "IDimensionTolerance").Type) != 0 or not math.isclose(float(bore_dimension.SystemValue) * 1000.0, LEVER_BORE_DIA, abs_tol=1e-5):
        raise RuntimeError("LeverBoreDiaDim: drilled diameter/title-block acceptance changed")
    if bore_display.GetText(4) != LEVER_BORE_CALLOUT:
        raise RuntimeError("LeverBoreDiaDim: native process/mate/finished-wall callout did not persist")
    height_annotation = next(a for a in right_annotations if dimension_name(adapter, a) == "Height")
    height_display = _early_bound(_early_bound(height_annotation, "IAnnotation").GetSpecificAnnotation(), "IDisplayDimension")
    if str(height_display.GetText(4) or "") != HEIGHT_DRAWING_CALLOUT:
        raise RuntimeError("Height: truthful top-tap wall function did not remain attached")
    # The flats are the bar's as supplied: a stock reference.
    top_by_name = {dimension_name(adapter, a): a for a in top_annotations}
    for name in sorted(REFERENCE_DIMENSIONS):
        set_reference_dimension(
            adapter, top_by_name[name], label=f"MHA-MG-02 {name} stock reference"
        )

    # The template marks each end view's tap; a second, scripted mark doubled
    # it (the r1 audit's duplicate-annotation), so the sheet only proves the one.
    for view, label in ((top, "top"), (bottom, "bottom")):
        _require_one_center_mark(view, label)
    # Each end view shows one visible tap-drill circle: its native callout
    # prints the drill and thread rows with the process ahead of the thread.
    thumb_callout = add_native_hole_callout(
        adapter,
        top,
        edge=visible_circle_edge(adapter, top, ROD_TAP_DRILL_DIA),
        callout_xy=THUMB_TAP_CALLOUT_XY,
        label="#4-40 thumb-screw tap",
        process=THUMB_TAP_PROCESS,
    )
    _omit_tap_thread_class(thumb_callout, label="#4-40 thumb-screw tap")
    _reference_thread_depth(thumb_callout)
    set_hole_callout_precision(
        thumb_callout, TAP_CALLOUT_PRECISION, label="#4-40 thumb-screw tap depths"
    )
    rod_callout = add_native_hole_callout(
        adapter,
        bottom,
        edge=visible_circle_edge(adapter, bottom, ROD_TAP_DRILL_DIA),
        callout_xy=ROD_TAP_CALLOUT_XY,
        label="#4-40 vertical-rod tap",
        process=ROD_TAP_PROCESS,
    )
    _omit_tap_thread_class(rod_callout, label="#4-40 vertical-rod tap")
    set_hole_callout_precision(
        rod_callout, TAP_CALLOUT_PRECISION, label="#4-40 vertical-rod tap depths"
    )
    # SolidWorks pins its own "#4-40 Tapped Hole" note beside a tap's native
    # callout; the callout already states the thread. Farm run r1
    # (20261016T211740899Z) measured one on the bottom view, its leader
    # crossing the rod tap callout's (leader-crosses-leader). How many the
    # two taps bring is logged here, after both callouts; finalize_drawing's
    # census then proves none reached the print.
    removed = remove_notes_matching(adapter, TAPPED_HOLE_NOTE)
    _telemetry.info(f"removed {removed} automatic {TAPPED_HOLE_NOTE!r} note(s)")

    # The bottom seat's "leave it flat" flag (rule 7), on section A-A's bottom
    # line beside the rod tap, down and to the right clear of the caption.
    add_attached_note(
        adapter,
        section,
        text=SEAT_NOTE,
        entity_xy=(SECTION_CENTER[0] + _PICK_DX, _elev_y(SECTION_CENTER, 0.0)),
        note_xy=SEAT_NOTE_XY,
        label="MHA-MG-04 shoulder seat",
    )

    _add_stock_note(adapter, iso)
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    def settled_dimensions() -> None:
        _assert_grouped_flat_locations(adapter, right, right_annotations)
        visibility = {}
        for raw in (*right_annotations, *top_annotations, *bottom_annotations):
            annotation = _early_bound(raw, "IAnnotation")
            name = dimension_name(adapter, annotation)
            if name in visibility:
                raise RuntimeError(f"{name}: duplicate native drawing dimension")
            visibility[name] = annotation.Visible
        if set(visibility) != set(DRAWING_PRECISION_BY_NAME) or any(type(value) is not int or value not in (1, 3) for value in visibility.values()):
            raise RuntimeError(f"clamp native dimension census changed: {visibility!r}")
        if {name for name, state in visibility.items() if state == 1} != VISIBLE_DIMENSIONS:
            raise RuntimeError(f"clamp visible native dimension census changed: {visibility!r}")
        if height_display.GetText(4) != HEIGHT_DRAWING_CALLOUT or bore_display.GetText(4) != LEVER_BORE_CALLOUT or int(_early_bound(bore_dimension.Tolerance, "IDimensionTolerance").Type) != 0:
            raise RuntimeError("clamp settled height function, bore wall callout or title-block acceptance changed")
        _telemetry.info("clamp native dimension census after final rebuild", source_dimension_count=len(visibility), visible_dimension_count=sum(value == 1 for value in visibility.values()), native_visibility=repr(visibility))

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Magnifying Clamp Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        redundant_note_substrings=(TAPPED_HOLE_NOTE,),
        expected_redundant_notes=0,
        settled_checks=(settled_dimensions,),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
