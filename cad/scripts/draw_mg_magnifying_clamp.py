r"""Create the curated machinist drawing for the magnifying-lever clamp.

A 1.16 length of 1/2 hex brass: the Ø.257 quarter-inch lever bore drilled across
the corners, a #4-40 thumb-screw tap from the top face into the bore and a
blind #4-40 rod tap from the bottom face, both on the hex axis. The sheet
prints decimal inch (#290); each tap callout prints its drill Ø at .XXX.

Views (3:1, hidden lines removed throughout, drawing-guidelines.md rule 9):

* FRONT (``*Right``, looking along the lever bore at a corner): the block
  height, the bore's height from the bottom seat and its Ø callout. One grouped
  common-flat location applies to the bore and both tap entry axes; all three
  native source measurements remain independently checked. The location
  sketch the view shows to import them is blanked again afterwards, so its
  construction lines (the converted flat on the outline, the converted bore
  circle, the tap witnesses) do not print; only their dimensions do.
* TOP and BOTTOM, turned and pinned into third-angle projection above and
  below the front (corners up and down, the flats square to the sheet): the
  controlled stock flats above and to the right of the top view, and each tap's
  native callout.
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
import math
import sys
from typing import Any
from types import SimpleNamespace

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.pywin32_adapter import null_callout
from solidworks_mcp.adapters.solidworks.drawing import (
    dimension_name,
    place_view,
    remove_notes_matching,
    view_name,
)

from _check import check
from _com import _early_bound, _read_member
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    stamp_drawing_summary,
)
from _drawing_dimension_import import _model_item_paths, curate_view_dimensions
from _drawing_dimensions import (
    assert_imported_precision,
    set_dimension_callouts,
)
from _drawing_hidden_sketches import curate_view_dimensions as curate_hidden_dimensions
from _drawing_hole_callout import add_native_hole_callout, set_hole_callout_precision
from _drawing_leader_notes import add_attached_note
from _drawing_notes import add_property_linked_note
from _drawing_precision import _named_dimension
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _part_properties import part_drawing_unit
from _drawing_sections import create_section_view
from _drawing_view_display import set_hidden_lines_removed
from _gear_drawing_entities import visible_circle_edge
from _hole_callout_thread_class import omit_title_block_thread_class
from _machinist_review_mode import MachinistReviewMode
from _paths import CAD_ROOT
from _session import run_build
from _supplier_dimensions import (
    assert_supplier_reference_dimension,
    supplier_reference_dimension,
)
import _telemetry
from build_mg_magnifying_clamp import (
    _assert_location_profiles,
    _assert_ordinary_location,
    _assert_stock_af,
    _assert_stock_af_source,
    _point_flat_attachment,
    _point_identity,
    _segment_identity,
    _sketch_owners,
)
from mg_magnifying_clamp_spec import (
    AREA_HATCH_STYLE_PATTERN,
    BLOCK_HEIGHT,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    DIMENSION_GROUPS,
    GROUPED_HIDDEN_DIMENSIONS,
    Z_FLAT_DIMENSIONS,
    VISIBLE_DIMENSIONS,
    HEX_AC,
    HEX_AF,
    HEX_AF_FRACTION_DENOMINATOR,
    LEVER_BORE_CALLOUT,
    LEVER_BORE_DIA,
    LEVER_BORE_Y,
    PREF_MATERIAL_HATCH_PATTERN,
    PREF_MATERIAL_HATCH_STYLE,
    PREF_NO_OPTION,
    ROD_TAP_DRILL_DIA,
    ROD_TAP_PROCESS,
    SEAT_NOTE,
    SECTION_HATCH_PATTERN,
    STOCK_REFERENCE_DIMENSION,
    TAP_CALLOUT_PRECISION,
    TAP_DRILL_DEPTH_VARIABLE,
    TAP_THREAD_DEPTH_VARIABLE,
    THUMB_TAP_PROCESS,
)


# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

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

# A nominal .577 x 1/2 x 1.16 hex with one common-flat location group.
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
# The iso remains illustrative; keep its scale caption above it.
ISO_NOTE_XY = (0.335, 0.245)
# R27's 146.5 mm seat row needs the full right-hand text lane inside the border.
SEAT_NOTE_XY = (0.260, 0.116)

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
    "LeverBoreDiaDim": (0.165, 0.145),
}
# Keep the 1/2 stock REF outside both native witnesses/arrow tails.
# There is no independent envelope note.
TOP_KEEP = {"HexAf": (0.152, 0.255)}
RIGHT_LOCATION_KEEP = {
    # Move R27's whole three-row label right, away from A and the height witness.
    # Keep its vertical station: raising the flat witness crosses A (R21).
    # All three values are imported/read back; only the verified group leader prints.
    name: (0.150, 0.1755) for name in Z_FLAT_DIMENSIONS
}
TOP_LOCATION_KEEP = {"ThumbTapFromDiagonalFlat": (0.043, 0.186)}
BOTTOM_KEEP = {"RodTapFromDiagonalFlat": (0.043, 0.074)}

DIMENSION_CALLOUTS = {
    "Height": "",
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
# The front view shows LeverBoreLocationProfile only to import its common-flat
# dimensions (_drawing_hidden_sketches); its construction segments duplicate
# the outline and bore circle (machinist review of 2056e3344 read them as
# hidden lines).  After the import the view blanks it again and restores the
# dimensions' visibility, which the re-blank alone hides (r21).  Putting the
# segments' view instances on a hidden layer was refused (Arc2, farm run
# 20261024T122828167Z).
_FRONT_REFERENCE_SKETCH = "LeverBoreLocationProfile"

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


def _front_reference_visibility(view: Any) -> Any:
    """LeverBoreLocationProfile's Visible state as the front view maps it
    (swVisibilityState_e; logged next to the dimension proofs)."""
    native = _early_bound(view, "IView")
    model = native.ReferencedDocument
    if model is None:
        raise RuntimeError("clamp front view references no model")
    feature = _early_bound(model, "IPartDoc").FeatureByName(_FRONT_REFERENCE_SKETCH)
    if feature is None:
        raise RuntimeError(f"clamp part has no {_FRONT_REFERENCE_SKETCH}")
    mapped = native.GetCorresponding(feature)
    if mapped is None:
        return None
    return _read_member(_early_bound(mapped, "IFeature"), "Visible")


def _blank_front_reference_sketch(adapter: Any, view: Any, annotations: list[Any]) -> None:
    """Blank the front view's location sketch once its dimensions are imported
    and grouped, then put each grouped dimension back to its group visibility.

    The re-blank alone hides the imported dimensions (r21); the caller then
    proves every front dimension visible as wanted and attached (forward
    attachment identity, not dangling) before and after the final rebuild."""
    draw = adapter.currentModel
    name = view_name(adapter, view)
    if not _early_bound(draw, "IDrawingDoc").ActivateView(name):
        raise RuntimeError(f"failed to activate clamp front view {name!r}")
    before = _front_reference_visibility(view)
    for component, in_view in _model_item_paths(adapter, view):
        draw.ClearSelection2(True)
        if draw.Extension.SelectByID2(
            f"{_FRONT_REFERENCE_SKETCH}@{component}@{in_view}",
            "SKETCH",
            0.0,
            0.0,
            0.0,
            False,
            0,
            null_callout(),
            0,
        ):
            break
    else:
        raise RuntimeError(f"cannot select {_FRONT_REFERENCE_SKETCH} in the front view")
    draw.BlankSketch()
    draw.ClearSelection2(True)
    rebuild_drawing(adapter, label=f"blank {_FRONT_REFERENCE_SKETCH} in the clamp front view")
    group = _flat_group_annotations(adapter, view, annotations)
    blanked = {item: annotation.Visible for item, annotation in group.items()}
    for item, annotation in group.items():
        annotation.Visible = 3 if item in GROUPED_HIDDEN_DIMENSIONS else 1
    _early_bound(draw, "IModelDoc2").GraphicsRedraw2()
    _assert_grouped_flat_locations(group)
    _telemetry.info(
        f"clamp front {_FRONT_REFERENCE_SKETCH} blanked: sketch Visible "
        f"{before!r} -> {_front_reference_visibility(view)!r}; dimension Visible "
        f"after blank {blanked!r}, restored to the group states",
        dimension_visibility_after_blank=repr(blanked),
    )


def _assert_front_annotations_attached(adapter: Any, annotations: list[Any]) -> None:
    dangling = {}
    for raw in annotations:
        annotation = _early_bound(raw, "IAnnotation")
        state = annotation.IsDangling()
        if state is not False:
            dangling[dimension_name(adapter, annotation)] = state
    if dangling:
        raise RuntimeError(f"clamp front dimensions dangle: {dangling!r}")


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




# The flats as bought: the stock's exact 1/2 in fraction, a native REF the
# supplier's tolerance governs, never a size the shop holds.
HEX_AF_REFERENCE = {
    "label": "MHA-MG-02 HexAf stock reference",
    "units": "in",
    "precision": DRAWING_PRECISION_BY_NAME[STOCK_REFERENCE_DIMENSION],
    "expected_mm": HEX_AF,
    "fraction_denominator": HEX_AF_FRACTION_DENOMINATOR,
}


def _stock_af_display(raw_annotation: Any) -> Any:
    annotation = _early_bound(raw_annotation, "IAnnotation")
    return _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")


def _assert_stock_af_import(adapter: Any, view: Any, raw_annotation: Any, *, stage: str) -> None:
    view = _early_bound(view, "IView")
    model = view.ReferencedDocument
    if model is None:
        raise RuntimeError("HexAf: top view has no source part")
    source = SimpleNamespace(currentModel=model, swApp=adapter.swApp)
    _source_display, source_dimension = _assert_stock_af_source(source, stage=f"{stage}.source")
    annotation = _early_bound(raw_annotation, "IAnnotation")
    display = _stock_af_display(annotation)
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    _assert_stock_af(display, dimension, stage=stage)
    owner, owner_type = annotation.Owner, annotation.OwnerType
    if owner is None:
        raise RuntimeError(f"HexAf: imported annotation has no native owner at {stage}")
    app = _early_bound(adapter.swApp, "ISldWorks")
    codes = (
        app.IsSame(view, view), app.IsSame(owner, owner), app.IsSame(owner, view),
        app.IsSame(source_dimension, source_dimension), app.IsSame(dimension, dimension),
        app.IsSame(dimension, source_dimension),
    )
    dangling = annotation.IsDangling()
    names = (source_dimension.FullName, dimension.FullName)
    _telemetry.info("clamp native stock AF import", operation_stage=stage, identity_codes=repr(codes), owner_type=owner_type, full_names=repr(names), dangling=dangling)
    if any(type(code) is not int or code != 1 for code in codes) or type(owner_type) is not int or owner_type != 0 or names[0] != names[1] or dangling is not False:
        raise RuntimeError(f"HexAf: actual source dimension/top-view ownership changed at {stage}")
    assert_supplier_reference_dimension(adapter, display, **HEX_AF_REFERENCE)




def _require_flat_import(adapter, requested_view, source_display, display, source_entities, source_types, source_point, *, stage, source_owners=None):
    """Prove imported attachments against source entities in the requested view.

    R26 proved this forward route for LeverBoreFromZFlat. Other dimensions must
    satisfy the same guards; no inverse-map fallback or cross-context ID test.
    """
    import pythoncom
    from solidworks_mcp.adapters._generated.sldworks_2026 import (
        IAnnotation, IDimension, IFeature, IModelDoc2, ISketch,
        ISketchPoint, ISketchSegment, IView,
    )

    classes = {
        "IAnnotation": IAnnotation, "IDimension": IDimension, "IFeature": IFeature,
        "IModelDoc2": IModelDoc2, "ISketch": ISketch, "ISketchPoint": ISketchPoint,
        "ISketchSegment": ISketchSegment, "IView": IView,
    }
    audit = {"step": "source", "native": {}, "attachments": []}
    error = error_traceback = None

    def native(label, raw, interface):
        audit["step"] = label
        evidence = {"present": raw is not None, "queries": [], "self": None}
        audit["native"][label] = evidence
        if raw is None:
            raise RuntimeError(f"{label}: required native object unavailable")
        choices = [(interface, classes[interface].CLSID), ("IDispatch", pythoncom.IID_IDispatch)]
        if interface in ("ISketchPoint", "ISketchSegment"):
            other = "ISketchSegment" if interface == "ISketchPoint" else "ISketchPoint"
            choices.append((other, classes[other].CLSID))
        for kind, iid in choices:
            query = {"interface": kind, "iid": str(iid), "supported": None, "hresult": None}
            evidence["queries"].append(query)
            try:
                pointer = raw._oleobj_.QueryInterface(iid, pythoncom.IID_IUnknown)
                if pointer is not None:
                    query.update(supported=True, hresult=0)
            except pythoncom.com_error as exc:
                query["hresult"] = exc.hresult
                if exc.hresult == -2147467262:
                    query["supported"] = False
                else:
                    query["error_type"] = type(exc).__name__
            except Exception as exc:
                query["error_type"] = type(exc).__name__
        if any(query["supported"] is not (query["interface"] in (interface, "IDispatch")) for query in evidence["queries"]):
            raise RuntimeError(f"{label}: native interface differs, is ambiguous, or is unavailable")
        bound = _early_bound(raw, interface)
        if bound is None:
            raise RuntimeError(f"{label}: native interface binding returned no object")
        evidence["self"] = app.IsSame(bound, bound)
        if type(evidence["self"]) is not int or evidence["self"] != 1:
            raise RuntimeError(f"{label}: native self control failed")
        return bound

    try:
        app = _early_bound(adapter.swApp, "ISldWorks")
        view = _early_bound(requested_view, "IView")
        view = native("requested-view", view, "IView")
        model = native("source-document", adapter.currentModel, "IModelDoc2")
        audit["source_document_type"] = model.GetType()
        if type(audit["source_document_type"]) is not int or audit["source_document_type"] != 1:
            raise RuntimeError("source document is not a native part")
        if source_owners is None:
            source_owners = _sketch_owners(adapter)
        source_annotation = native("source-annotation", _early_bound(source_display, "IDisplayDimension").GetAnnotation(), "IAnnotation")
        annotation = native("drawing-annotation", _early_bound(display, "IDisplayDimension").GetAnnotation(), "IAnnotation")
        audit["step"] = "drawing-annotation.GetAttachedEntities3"
        attached = tuple(annotation.GetAttachedEntities3() or ())
        audit["attachment_count"] = len(attached)
        audit["step"] = "drawing-annotation.GetAttachedEntityTypes"
        types = tuple(annotation.GetAttachedEntityTypes() or ())
        audit["attached_types"] = types
        audit["step"] = "drawing-annotation.IsDangling"
        audit["dangling"] = annotation.IsDangling()
        audit.update(source_count=len(source_entities), source_types=source_types)
        if len(attached) != 2 or len(types) != 2 or any(entity is None for entity in attached) or audit["dangling"] is not False or any(type(kind) is not int for kind in types):
            raise RuntimeError("invalid imported native point/flat attachments")
        if len(source_entities) != 2 or len(source_types) != 2 or any(entity is None for entity in source_entities) or any(type(kind) is not int for kind in source_types):
            raise RuntimeError("invalid source native point/flat attachments")
        audit["source_owner_type"] = source_annotation.OwnerType
        audit["drawing_owner_type"] = annotation.OwnerType
        if type(audit["source_owner_type"]) is not int or audit["source_owner_type"] != 3 or type(audit["drawing_owner_type"]) is not int or audit["drawing_owner_type"] != 0:
            raise RuntimeError("native annotation owner types are not part and drawing view")
        source_owner = native("source-annotation-owner", source_annotation.Owner, "IModelDoc2")
        drawing_owner = native("drawing-annotation-owner", annotation.Owner, "IView")
        audit["source_owner_match"] = app.IsSame(source_owner, model)
        audit["drawing_owner_match"] = app.IsSame(drawing_owner, view)
        if any(type(audit[key]) is not int or audit[key] != 1 for key in ("source_owner_match", "drawing_owner_match")):
            raise RuntimeError("native annotation does not belong to the source part/requested view")

        source_dimension = native("source-dimension", _early_bound(source_display, "IDisplayDimension").GetDimension2(0), "IDimension")
        dimension = native("drawing-dimension", _early_bound(display, "IDisplayDimension").GetDimension2(0), "IDimension")
        audit["full_names"] = source_dimension.FullName, dimension.FullName
        audit["dimension_match"] = app.IsSame(source_dimension, dimension)
        if any(type(value) is not str for value in audit["full_names"]) or audit["full_names"][0] != audit["full_names"][1] or type(audit["dimension_match"]) is not int or audit["dimension_match"] != 1:
            raise RuntimeError("imported native dimension differs from its actual source")
        audit["step"] = "source-dimension.GetFeatureOwner"
        source_feature = native("source-dimension-feature", source_dimension.GetFeatureOwner(), "IFeature")
        audit["step"] = "drawing-dimension.GetFeatureOwner"
        drawing_feature = native("drawing-dimension-feature", dimension.GetFeatureOwner(), "IFeature")
        try:
            audit["feature_match"] = app.IsSame(source_feature, drawing_feature)
        except Exception as exc:
            audit["feature_match"] = None
            audit["feature_match_error_type"] = type(exc).__name__
        audit["feature_names"] = source_feature.Name, drawing_feature.Name
        audit["feature_types"] = source_feature.GetTypeName2(), drawing_feature.GetTypeName2()
        if any(value not in ("ProfileFeature", "3DProfileFeature") for value in audit["feature_types"]):
            raise RuntimeError("native dimension feature is not a supported sketch feature")
        # IDimension identity above is authoritative: source_display was
        # enumerated from this named source feature by _named_dimension.
        # IFeature wrappers returned by GetFeatureOwner can differ by context;
        # their IsSame code is diagnostic, not a substitute ownership test.
        if any(type(value) is not str or value != source_point[0] for value in audit["feature_names"]):
            raise RuntimeError("imported native dimension feature differs from its source")
        audit["step"] = "dimension-feature.forward"
        _telemetry.info("clamp dimension-feature forward correspondence before", operation_stage=f"{stage}.feature-forward-before", correspondence_method="IView.GetCorresponding")
        mapped_feature = view.GetCorresponding(source_feature)
        audit["feature_mapped_present"] = mapped_feature is not None
        _telemetry.info("clamp dimension-feature forward correspondence returned", operation_stage=f"{stage}.feature-forward-returned", attachment_role="dimension-feature", mapped_present=audit["feature_mapped_present"])
        mapped_feature = native("forward-dimension-feature", mapped_feature, "IFeature")
        audit["mapped_feature_name"] = mapped_feature.Name
        audit["mapped_feature_type"] = mapped_feature.GetTypeName2()
        if type(audit["mapped_feature_name"]) is not str or audit["mapped_feature_name"] != source_point[0] or audit["mapped_feature_type"] not in ("ProfileFeature", "3DProfileFeature"):
            raise RuntimeError("mapped native dimension feature is not its expected sketch feature")
        # This is DRAWING ownership only. R26 source-point owner vs the sketch
        # obtained from GetFeatureOwner was 0; never use it as part authority.
        audit["step"] = "forward-dimension-feature.GetSpecificFeature2"
        feature_sketch = native("forward-dimension-feature-sketch", mapped_feature.GetSpecificFeature2(), "ISketch")

        for role, interface, selection_types in (("point", "ISketchPoint", (11, 25)), ("flat", "ISketchSegment", (10,))):
            row = {"role": role, "source_key": None, "mapped_present": None, "contexts": {}, "owner_match": None, "feature_owner_match": None}
            audit["attachments"].append(row)
            model_inputs = [entity for entity, kind in zip(source_entities, source_types, strict=True) if kind in selection_types]
            drawing_inputs = [entity for entity, kind in zip(attached, types, strict=True) if kind in selection_types]
            row.update(source_count=len(model_inputs), drawing_count=len(drawing_inputs))
            if len(model_inputs) != 1 or len(drawing_inputs) != 1:
                raise RuntimeError(f"{role}: expected one actual source and imported attachment")
            model_entity = native(f"{role}.source", model_inputs[0], interface)
            if role == "point":
                row["source_key"] = _point_identity(adapter, model_entity, stage=stage, role="forward-source-point", owners=source_owners)
                if row["source_key"] != source_point:
                    raise RuntimeError("point: source attachment changed before forward mapping")
            else:
                row["source_key"] = _segment_identity(adapter, model_entity, stage=stage, role="forward-source-flat", owners=source_owners)
                if row["source_key"][0] != source_point[0] or row["source_key"][1] != 0:
                    raise RuntimeError("flat: source is not the actual common-flat sketch line")
            audit["step"] = f"{role}.forward"
            _telemetry.info("clamp attachment forward correspondence before", operation_stage=f"{stage}.forward-before", attachment_role=role, source_identity=repr(row["source_key"]), correspondence_method="IView.GetCorresponding")
            mapped = view.GetCorresponding(model_entity)
            row["mapped_present"] = mapped is not None
            _telemetry.info("clamp attachment forward correspondence returned", operation_stage=f"{stage}.forward-returned", attachment_role=role, mapped_present=row["mapped_present"])
            owners = {}
            for context, raw in (("actual", drawing_inputs[0]), ("forward", mapped)):
                bound = native(f"{role}.{context}", raw, interface)
                owner = native(f"{role}.{context}.owner", bound.GetSketch(), "ISketch")
                owners[context] = owner
                audit["step"] = f"{role}.{context}.identity"
                ids = bound.GetID()
                ids = tuple(ids) if ids is not None else ()
                kind = bound.GetType() if role == "flat" else "ISketchPoint"
                row["contexts"][context] = {"ids": ids, "type": kind}
                if len(ids) != 2 or any(type(value) is not int for value in ids):
                    raise RuntimeError(f"{role}.{context}: invalid ordered native ID pair")
                if role == "flat" and (type(kind) is not int or kind != 0):
                    raise RuntimeError(f"{role}.{context}: attachment is not a native line")
            audit["step"] = f"{role}.drawing-identity"
            row["owner_match"] = app.IsSame(owners["forward"], owners["actual"])
            row["feature_owner_match"] = app.IsSame(feature_sketch, owners["actual"])
            if any(type(row[key]) is not int or row[key] != 1 for key in ("owner_match", "feature_owner_match")):
                raise RuntimeError(f"{role}: imported owning sketch differs from the requested view/source feature")
            # Compare ONLY the two independently acquired DRAWING-context IDs.
            # The model key above is never compared with either drawing ID.
            if row["contexts"]["actual"] != row["contexts"]["forward"]:
                raise RuntimeError(f"{role}: imported native drawing identity differs from its forward-mapped source")
    except Exception as exc:
        error, error_traceback = exc, exc.__traceback__
    try:
        _telemetry.info(
            f"clamp native forward attachment: stage={stage}, audit={audit!r}, error={error!r}",
            operation_stage=stage, attachment_forward=repr(audit), attachment_readback_error=repr(error),
        )
    finally:
        # Preserve 24c's exact original exception/frames even when logging or
        # formatting fails. Diagnostics never supply an accepted attachment.
        if error is not None:
            raise error.with_traceback(error_traceback)


def _flat_group_annotations(adapter: Any, view: Any, annotations: list[Any]) -> dict[str, Any]:
    """Read all three genuine imported dimensions and their independently checked source."""
    native_view = _early_bound(view, "IView")
    source = _early_bound(native_view.ReferencedDocument, "IModelDoc2")
    if source is None:
        raise RuntimeError("common-flat group has no referenced part")
    source_adapter = SimpleNamespace(currentModel=source, swApp=adapter.swApp)
    owners = _sketch_owners(source_adapter)
    _assert_location_profiles(source_adapter, owners=owners)
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
        source_point = _point_flat_attachment(source_adapter, source_display, flats[0], stage=f"{name}.drawing-source", owners=owners)
        _require_flat_import(
            source_adapter, native_view, source_display, display,
            source_entities, source_types, source_point, stage=f"{name}.drawing-import", source_owners=owners,
        )
        result[name] = annotation
    return result


def _assert_grouped_flat_locations(group: dict[str, Any]) -> None:
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
    _assert_grouped_flat_locations(group)


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
            "Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Isometric View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter,
        property_view=PART_STEM,
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        unit=part_drawing_unit(PART_STEM),
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
    set_dimension_callouts(adapter, [*right_annotations, *top_annotations], DIMENSION_CALLOUTS)
    _group_flat_locations(adapter, right, right_annotations)
    # Blank the location sketch again now its dimensions are in; every front
    # dimension must stay visible as grouped and attached.
    _blank_front_reference_sketch(adapter, right, right_annotations)
    _assert_front_annotations_attached(adapter, right_annotations)
    bore_annotation = next(a for a in right_annotations if dimension_name(adapter, a) == "LeverBoreDiaDim")
    bore_display = _early_bound(_early_bound(bore_annotation, "IAnnotation").GetSpecificAnnotation(), "IDisplayDimension")
    bore_dimension = _early_bound(bore_display.GetDimension2(0), "IDimension")
    if int(_early_bound(bore_dimension.Tolerance, "IDimensionTolerance").Type) != 0 or not math.isclose(float(bore_dimension.SystemValue) * 1000.0, LEVER_BORE_DIA, abs_tol=1e-5):
        raise RuntimeError("LeverBoreDiaDim: drilled diameter/title-block acceptance changed")
    if bore_display.GetText(4) != LEVER_BORE_CALLOUT:
        raise RuntimeError("LeverBoreDiaDim: native process/mate/finished-wall callout did not persist")
    height_annotation = next(a for a in right_annotations if dimension_name(adapter, a) == "Height")
    height_display = _early_bound(_early_bound(height_annotation, "IAnnotation").GetSpecificAnnotation(), "IDisplayDimension")
    if str(height_display.GetText(4) or ""):
        raise RuntimeError("Height: removed top-tap-wall qualifier remained")
    top_by_name = {dimension_name(adapter, a): a for a in top_annotations}
    # The as-bought 1/2 hex prints as its stock REF fraction, untoleranced.
    supplier_reference_dimension(adapter, _stock_af_display(top_by_name["HexAf"]), **HEX_AF_REFERENCE)
    _assert_stock_af_import(adapter, top, top_by_name["HexAf"], stage="HexAf.imported")

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

    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    def settled_dimensions() -> None:
        _assert_grouped_flat_locations(_flat_group_annotations(adapter, right, right_annotations))
        _assert_stock_af_import(adapter, top, top_by_name["HexAf"], stage="HexAf.after-final-rebuild")
        _telemetry.info(f"clamp front {_FRONT_REFERENCE_SKETCH} Visible after final rebuild: {_front_reference_visibility(right)!r}")
        _assert_front_annotations_attached(adapter, right_annotations)
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
        if str(height_display.GetText(4) or "") or bore_display.GetText(4) != LEVER_BORE_CALLOUT or int(_early_bound(bore_dimension.Tolerance, "IDimensionTolerance").Type) != 0:
            raise RuntimeError("clamp settled height qualifier, bore wall callout or title-block acceptance changed")
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
