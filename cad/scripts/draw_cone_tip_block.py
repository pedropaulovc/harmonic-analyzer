r"""Create the simplicity-policy machinist drawing for the cone tip block."""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_leader_note,
    add_native_hole_callout,
    add_surface_finish,
    assert_imported_precision,
    create_section_view,
    curate_view_dimensions,
    finalize_drawing,
    model_point_in_view,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    set_dimension_callouts,
    set_hidden_lines_removed,
    set_hole_callout_precision,
    stamp_drawing_summary,
    visible_view_entities,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _surface_finish import surface_finish_by_key
from cone_tip_block_spec import (
    ADJUSTER_AXIS_HEIGHT,
    ADJUSTER_BORE_DIA,
    BLOCK_HEIGHT,
    BLOCK_X,
    BLOCK_Z,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    FOOT_BORE_DIA,
    PINCH_BORE_DIA,
    PINCH_CLEARANCE_DIA,
    PINCH_HEIGHT,
    SHAFT_PASSAGE_DIA,
    SLIT_DEPTH,
    SURFACE_FINISHES,
)
from solidworks_mcp.adapters.solidworks.drawing import add_note, auto_center_marks, place_view


SPEC = DRAWINGS_BY_NAME["cone_tip_block"]
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

SHEET_SCALE = (2.0, 1.0)
_S = SHEET_SCALE[0] / 1000.0
FRONT_CENTER = (0.072, 0.129)
TOP_CENTER = (FRONT_CENTER[0], 0.225)
RIGHT_CENTER = (0.166, FRONT_CENTER[1])
LEFT_CENTER = (0.238, FRONT_CENTER[1])
BACK_CENTER = (0.310, FRONT_CENTER[1])
SECTION_CENTER = (0.190, 0.225)
ISO_CENTER = (0.350, 0.215)
# U30 hold-down tap: the only feature on the foot, so the bottom view sits in
# the free band under the front view and carries just its callout.
BOTTOM_CENTER = (FRONT_CENTER[0], 0.040)


def _elevation_y(model_y: float, center: tuple[float, float]) -> float:
    return center[1] + (model_y - BLOCK_HEIGHT / 2.0) * _S


FRONT_KEEP = {
    "Width": (FRONT_CENTER[0], _elevation_y(0.0, FRONT_CENTER) - 0.012),
    "BlockHt": (FRONT_CENTER[0] - 0.033, FRONT_CENTER[1]),
    "SlitW": (FRONT_CENTER[0], _elevation_y(BLOCK_HEIGHT, FRONT_CENTER) + 0.014),
}
TOP_KEEP = {"Depth": (TOP_CENTER[0] - 0.035, TOP_CENTER[1])}
SECTION_KEEP = {
    "PinchRise": (
        SECTION_CENTER[0] + 0.060,
        _elevation_y(
            (ADJUSTER_AXIS_HEIGHT + PINCH_HEIGHT) / 2.0,
            SECTION_CENTER,
        ),
    )
}
RIGHT_KEEP = {
    "PinchDepthCenter": (
        RIGHT_CENTER[0],
        _elevation_y(BLOCK_HEIGHT, RIGHT_CENTER) + 0.003,
    )
}
LEFT_KEEP: dict[str, tuple[float, float]] = {}
# The foot tap's two locations: FootTapX above the bottom view (between it and
# the front view's 15.0), FootTapZ to its left; the view caption moves under it.
BOTTOM_KEEP = {
    "FootTapX": (BOTTOM_CENTER[0], BOTTOM_CENTER[1] + BLOCK_Z * _S / 2.0 + 0.007),
    "FootTapZ": (BOTTOM_CENTER[0] - BLOCK_X * _S / 2.0 - 0.009, BOTTOM_CENTER[1]),
}
# A centreline runs a short way past the part it marks.
AXIS_OVERRUN = 0.002
# Review C1: the left and rear views sit right of the right view, out of
# third-angle order, so each is a removed view named by a letter arrow on the
# view that shows the face it looks at.  VIEW B looks at the -X (pinch-thread)
# face: the arrow meets the front view's left edge above the 46.83 and 32.27
# extension lines.  VIEW C looks at the -Z (shaft-entry) face, which is the top
# view's upper edge, left of the A-A cutting-plane stem.  Each pair is
# (note upper-left, leader tip), sheet metres.
VIEW_B_ARROW = (
    (FRONT_CENTER[0] - BLOCK_X * _S / 2.0 - 0.013, 0.1625),
    (FRONT_CENTER[0] - BLOCK_X * _S / 2.0, 0.160),
)
VIEW_C_ARROW = (
    (TOP_CENTER[0] - 0.0115, TOP_CENTER[1] + BLOCK_Z * _S / 2.0 + 0.015),
    (TOP_CENTER[0] - 0.010, TOP_CENTER[1] + BLOCK_Z * _S / 2.0),
)
DIMENSION_CALLOUTS = {
    "PassageDiaDim": "DRILL THRU\nCLEARANCE\nCOAXIAL WITH\nADJUSTER BORE",
    "SlitDepth": "SLOT DEPTH",
}


def _foot_edge(adapter: Any, view: Any, *, min_span_mm: float = 13.9) -> Any:
    """Return the longest real edge on the block's locating foot plane."""
    candidates: list[tuple[float, Any]] = []
    for raw_edge in visible_view_entities(view, 1, label="tip-block foot edges"):
        edge = _early_bound(raw_edge, "IEdge")
        start = edge.GetStartVertex()
        end = edge.GetEndVertex()
        if start is None or end is None:
            continue
        p0 = tuple(float(value) * 1000.0 for value in _early_bound(start, "IVertex").GetPoint())
        p1 = tuple(float(value) * 1000.0 for value in _early_bound(end, "IVertex").GetPoint())
        if abs(p0[1]) > 0.01 or abs(p1[1]) > 0.01:
            continue
        span = max(abs(p1[0] - p0[0]), abs(p1[2] - p0[2]))
        candidates.append((span, edge))
    if not candidates:
        raise RuntimeError("front view has no real edge on the locating foot plane")
    span, edge = max(candidates, key=lambda item: item[0])
    if span < min_span_mm:
        raise RuntimeError(f"locating-foot edge span is only {span:.3f} mm")
    return edge


def _add_pinch_axis(adapter: Any, section: Any) -> None:
    """Sketch the pinch bore's axis across section A-A.

    The 8.85 rise runs from the adjuster centre to this axis; without the
    centreline its extension line reads as rising from nothing (review
    2026-09-23).  The cutting plane contains both bore axes, so the axis
    projects from the model and is sketched sheet-owned, as the gear shaft's
    and swing platform's axes are.
    """
    half = BLOCK_X / 2000.0 + AXIS_OVERRUN / SHEET_SCALE[0]
    ends = [
        model_point_in_view(
            adapter,
            section,
            (x, PINCH_HEIGHT / 1000.0, 0.0),
            label=f"pinch axis end {index}",
        )
        for index, x in enumerate((-half, half))
    ]
    drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
    drawing.EditSheet()
    manager = _early_bound(adapter.currentModel.SketchManager, "ISketchManager")
    centerline = manager.CreateCenterLine(
        ends[0][0], ends[0][1], 0.0, ends[1][0], ends[1][1], 0.0
    )
    if centerline is None:
        raise RuntimeError("failed to sketch the pinch axis in section A-A")
    adapter.currentModel.ClearSelection2(True)
    adapter.currentModel.EditRebuild3()


def _circle_entity(
    adapter: Any,
    view: Any,
    *,
    radius_mm: float,
    center_y_mm: float,
    label: str,
) -> Any:
    """Resolve a real circular edge by model size and vertical station."""
    candidates: list[tuple[float, float, Any]] = []
    for raw_edge in visible_view_entities(view, 1, label=f"{label} circles"):
        edge = _early_bound(raw_edge, "IEdge")
        curve = edge.GetCurve()
        if curve is None:
            continue
        curve = _early_bound(curve, "ICurve")
        if not curve.IsCircle():
            continue
        params = tuple(float(value) * 1000.0 for value in curve.CircleParams)
        candidates.append((params[6], params[1], edge))
    if not candidates:
        raise RuntimeError(f"{label} view has no visible circular model edges")
    radius, center_y, edge = min(
        candidates,
        key=lambda item: abs(item[0] - radius_mm) + abs(item[1] - center_y_mm),
    )
    if abs(radius - radius_mm) > 0.01 or abs(center_y - center_y_mm) > 0.01:
        raise RuntimeError(
            f"no {label} circle matches radius {radius_mm:.3f} mm at "
            f"height {center_y_mm:.3f} mm; nearest is "
            f"R{radius:.3f} at {center_y:.3f} mm"
        )
    return edge

def _preferred_entry_circle(
    adapter: Any,
    candidates: tuple[
        tuple[Any, tuple[float, float]],
        tuple[Any, tuple[float, float]],
    ],
    *,
    radius_mm: float,
    center_y_mm: float,
    label: str,
) -> tuple[Any, tuple[float, float], Any]:
    """Use the first opposed view that exposes the requested real model edge."""
    matches: list[tuple[Any, tuple[float, float], Any]] = []
    for view, center in candidates:
        try:
            edge = _circle_entity(
                adapter,
                view,
                radius_mm=radius_mm,
                center_y_mm=center_y_mm,
                label=label,
            )
        except RuntimeError:
            continue
        matches.append((view, center, edge))
    if not matches:
        raise RuntimeError(f"{label} is absent from both opposed views")
    # A through passage can expose the blind tap's entry rim from both sides.
    # Both selections still belong to the same native Hole Wizard feature; the
    # caller's candidate order supplies a stable sheet-side preference.
    return matches[0]

_PINCH_THREAD_QUALIFIER = "LEFT-JAW THREAD\nCOAXIAL WITH CLEARANCE"
_PINCH_THREAD_NATIVE_TOKENS = frozenset(
    {"<hw-thrutapdrldia>", "<hw-threaddesc>", "<hw-threadclass>"}
)


def _pinch_thread_callout_definitions(
    definitions: dict[int, str],
) -> dict[int, str]:
    """Replace only the native extent words; keep every associative variable."""
    if set(definitions) != {5, 6, 7, 8}:
        raise RuntimeError(f"unexpected pinch callout definition parts: {definitions!r}")
    original = "\n".join(definitions.values())
    missing = _PINCH_THREAD_NATIVE_TOKENS - {
        token for token in _PINCH_THREAD_NATIVE_TOKENS if token in original
    }
    if missing or original.count("<hw-thru>") != 2:
        raise RuntimeError(
            "unexpected native pinch-thread callout definition: "
            f"missing={sorted(missing)!r}, definitions={definitions!r}"
        )
    updated = {
        part: text.replace("<hw-thru>", "TO SLOT")
        for part, text in definitions.items()
    }
    updated[5] = (
        f"{_PINCH_THREAD_QUALIFIER}\n{updated[5].lstrip()}"
        if updated[5].strip()
        else _PINCH_THREAD_QUALIFIER
    )
    rewritten = "\n".join(updated.values())
    if (
        "THRU ALL" in rewritten
        or rewritten.count("TO SLOT") != 2
        or any(token not in rewritten for token in _PINCH_THREAD_NATIVE_TOKENS)
    ):
        raise RuntimeError(f"pinch-thread callout rewrite lost semantics: {updated!r}")
    return updated


def _set_pinch_thread_callout_text(display: Any) -> None:
    """State the final two-jaw extent without severing Hole Wizard variables."""
    definitions = {
        part: str(display.GetText(part) or "")
        for part in (5, 6, 7, 8)
    }
    updated = _pinch_thread_callout_definitions(definitions)
    for definition_part, writable_part in ((5, 1), (6, 2), (7, 3), (8, 4)):
        if updated[definition_part] != definitions[definition_part]:
            display.SetText(writable_part, updated[definition_part])
    persisted = {
        part: str(display.GetText(part) or "")
        for part in (5, 6, 7, 8)
    }
    resolved = "\n".join(str(display.GetText(part) or "") for part in (1, 2, 3, 4))
    if (
        persisted != updated
        or "THRU ALL" in resolved
        or resolved.count("TO SLOT") != 2
        or _PINCH_THREAD_QUALIFIER not in resolved
    ):
        raise RuntimeError(
            "pinch-thread native extent override did not persist: "
            f"definitions={persisted!r}, resolved={resolved!r}"
        )




def _audit_isometric_annotation_provenance(adapter: Any, view: Any) -> int:
    """Prove every dashed isometric annotation is native cosmetic-thread ink."""
    annotation_types = [
        int(_early_bound(raw, "IAnnotation").GetType())
        for raw in (_early_bound(view, "IView").GetAnnotations() or ())
    ]
    if not annotation_types or any(kind != 1 for kind in annotation_types):
        raise RuntimeError(
            "cone-tip isometric annotation provenance changed: "
            f"types={annotation_types!r}"
        )
    _telemetry.debug(
        f"cone-tip isometric: {len(annotation_types)} cosmetic-thread annotations"
    )
    return len(annotation_types)


_COSMETIC_THREAD_LAYER = "CONE-TIP-SECTION-THREADS-HIDDEN"


def _hide_section_cosmetic_threads(adapter: Any, view: Any) -> int:
    """Keep cosmetic-thread annotation ink out of the solid-line section."""
    draw = adapter.currentModel
    manager = _early_bound(draw.GetLayerManager(), "ILayerMgr")
    layer = manager.GetLayer(_COSMETIC_THREAD_LAYER)
    if layer is None:
        if int(
            manager.AddLayer(
                _COSMETIC_THREAD_LAYER,
                "cosmetic thread ink hidden in cone-tip section",
                0,
                0,
                0,
            )
        ) != 1:
            raise RuntimeError("failed to add cone-tip section thread layer")
        layer = manager.GetLayer(_COSMETIC_THREAD_LAYER)
    layer = _early_bound(layer, "ILayer")
    layer.Visible = False
    if bool(layer.Visible) or bool(layer.Printable):
        raise RuntimeError("cone-tip section thread layer is not hidden")
    hidden = 0
    for raw_annotation in _early_bound(view, "IView").GetAnnotations() or ():
        annotation = _early_bound(raw_annotation, "IAnnotation")
        if int(annotation.GetType()) != 1:  # swCosmeticThread
            continue
        annotation.Layer = _COSMETIC_THREAD_LAYER
        if str(annotation.Layer or "") != _COSMETIC_THREAD_LAYER:
            raise RuntimeError("cone-tip section cosmetic thread refused hidden layer")
        hidden += 1
    if not hidden:
        raise RuntimeError("cone-tip section has no cosmetic thread to hide")
    rebuild_drawing(adapter, label="_hide_section_cosmetic_threads")
    return hidden




async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open cone-tip-block source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Cone Tip Block Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "cone tip block; adjuster carrier; split pinch clamp",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=SHEET_SCALE)
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=SHEET_SCALE)
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=SHEET_SCALE)
    left = place_view(adapter, str(SOURCE), "*Left", *LEFT_CENTER, scale=SHEET_SCALE)
    back = place_view(adapter, str(SOURCE), "*Back", *BACK_CENTER, scale=SHEET_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=SHEET_SCALE)
    bottom = place_view(adapter, str(SOURCE), "*Bottom", *BOTTOM_CENTER, scale=SHEET_SCALE)
    for view in (front, top, right, left, back, iso, bottom):
        set_hidden_lines_removed(adapter, view)

    # The top-view cutting plane passes through both orthogonal bore axes.  The
    # resulting solid-line section shows the blind adjuster thread, clearance
    # passage, split jaws and pinch bore relationship without dashed inference.
    section = create_section_view(
        adapter,
        top,
        line_start=(TOP_CENTER[0], TOP_CENTER[1] - BLOCK_Z * _S / 2.0 - 0.004),
        line_end=(TOP_CENTER[0], TOP_CENTER[1] + BLOCK_Z * _S / 2.0 + 0.004),
        view_xy=SECTION_CENTER,
        section_label="A",
        scale=SHEET_SCALE,
        label="adjuster and pinch-bore centre section",
    )
    set_hidden_lines_removed(adapter, section)
    _add_pinch_axis(adapter, section)

    adjuster_view, adjuster_center, adjuster_edge = _preferred_entry_circle(
        adapter,
        ((front, FRONT_CENTER), (back, BACK_CENTER)),
        radius_mm=ADJUSTER_BORE_DIA / 2.0,
        center_y_mm=ADJUSTER_AXIS_HEIGHT,
        label="blind adjuster thread",
    )
    if adjuster_view is front:
        passage_view, passage_center = back, BACK_CENTER
    else:
        passage_view, passage_center = front, FRONT_CENTER
    passage_edge = _circle_entity(
        adapter,
        passage_view,
        radius_mm=SHAFT_PASSAGE_DIA / 2.0,
        center_y_mm=ADJUSTER_AXIS_HEIGHT,
        label="shaft clearance passage",
    )
    pinch_clearance_edge = _circle_entity(
        adapter,
        right,
        radius_mm=PINCH_CLEARANCE_DIA / 2.0,
        center_y_mm=PINCH_HEIGHT,
        label="pinch entry-jaw clearance",
    )
    foot_tap_edge = _circle_entity(
        adapter,
        bottom,
        radius_mm=FOOT_BORE_DIA / 2.0,
        center_y_mm=0.0,
        label="foot hold-down thread",
    )
    pinch_thread_edge = _circle_entity(
        adapter,
        left,
        radius_mm=PINCH_BORE_DIA / 2.0,
        center_y_mm=PINCH_HEIGHT,
        label="pinch opposite-jaw thread",
    )
    front_keep = dict(FRONT_KEEP)
    back_keep: dict[str, tuple[float, float]] = {}
    passage_keep = {
        "PassageDiaDim": (
            passage_center[0] + 0.055,
            _elevation_y(ADJUSTER_AXIS_HEIGHT, passage_center) - 0.012,
        ),
    }
    plus_x_side = 1.0 if adjuster_view is front else -1.0
    adjuster_axis_keep = {
        "PassageZ": (
            adjuster_center[0] - 0.045,
            _elevation_y(ADJUSTER_AXIS_HEIGHT / 2.0, adjuster_center),
        ),
        "PassageCenter": (
            adjuster_center[0] + plus_x_side * BLOCK_X * _S / 4.0,
            _elevation_y(BLOCK_HEIGHT, adjuster_center) + 0.030,
        ),
        "SlitDepth": (
            adjuster_center[0] + 0.043,
            _elevation_y(BLOCK_HEIGHT - SLIT_DEPTH / 2.0, adjuster_center),
        ),
    }
    if passage_view is front:
        front_keep.update(passage_keep)
    else:
        back_keep.update(passage_keep)
    if adjuster_view is front:
        front_keep.update(adjuster_axis_keep)
    else:
        back_keep.update(adjuster_axis_keep)

    front_annotations = curate_view_dimensions(
        adapter,
        front,
        keep=front_keep,
        view_label="passage entry elevation",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    top_annotations = curate_view_dimensions(
        adapter,
        top,
        keep=TOP_KEEP,
        view_label="plan",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    section_annotations = curate_view_dimensions(
        adapter,
        section,
        keep=SECTION_KEEP,
        view_label="bore centre section",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    right_annotations = curate_view_dimensions(
        adapter,
        right,
        keep=RIGHT_KEEP,
        view_label="pinch clearance entry",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    left_annotations = curate_view_dimensions(
        adapter,
        left,
        keep=LEFT_KEEP,
        view_label="pinch threaded entry",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    back_annotations = curate_view_dimensions(
        adapter,
        back,
        keep=back_keep,
        view_label="adjuster threaded entry",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    bottom_annotations = curate_view_dimensions(
        adapter,
        bottom,
        keep=BOTTOM_KEEP,
        view_label="foot hold-down entry",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    annotations = [
        *bottom_annotations,
        *front_annotations,
        *top_annotations,
        *section_annotations,
        *right_annotations,
        *left_annotations,
        *back_annotations,
    ]
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)

    for view, label in (
        (front, "shaft-passage entry"),
        (right, "pinch clearance entry"),
        (left, "pinch threaded entry"),
        (back, "adjuster threaded entry"),
        (bottom, "foot hold-down entry"),
    ):
        if not auto_center_marks(adapter, view, holes=True, size=0.0025):
            raise RuntimeError(f"failed to add centre marks to {label} view")

    adjuster_callout = add_native_hole_callout(
        adapter,
        adjuster_view,
        edge=adjuster_edge,
        callout_xy=(
            adjuster_center[0] + 0.043,
            0.115,
        ),
        label="blind adjuster thread",
    )
    set_hole_callout_precision(
        adjuster_callout,
        {"hw-tapdrldepth": 1, "hw-threaddepth": 1},
        label="adjuster tap depths",
    )
    pinch_clearance_callout = add_native_hole_callout(
        adapter,
        right,
        edge=pinch_clearance_edge,
        callout_xy=(0.145, 0.185),
        label="pinch entry-jaw clearance",
    )
    set_hole_callout_precision(
        pinch_clearance_callout,
        {"hw-depth": 1},
        label="pinch clearance depth",
    )
    pinch_thread_callout = add_native_hole_callout(
        adapter,
        left,
        edge=pinch_thread_edge,
        callout_xy=(0.254, 0.190),
        label="pinch opposite-jaw thread",
    )
    _set_pinch_thread_callout_text(pinch_thread_callout)
    foot_tap_callout = add_native_hole_callout(
        adapter,
        bottom,
        edge=foot_tap_edge,
        callout_xy=(BOTTOM_CENTER[0] + 0.040, BOTTOM_CENTER[1] + 0.004),
        label="foot hold-down thread",
    )
    set_hole_callout_precision(
        foot_tap_callout,
        {"hw-tapdrldepth": 1, "hw-threaddepth": 1},
        label="foot tap depths",
    )
    _audit_isometric_annotation_provenance(adapter, iso)

    _hide_section_cosmetic_threads(adapter, section)
    for text, x, y in (
        ("VIEW C\nSHAFT ENTRY", passage_center[0] - 0.021, 0.078),
        ("RIGHT VIEW\nPINCH CLEARANCE ENTRY", RIGHT_CENTER[0] - 0.026, 0.078),
        ("VIEW B\nPINCH THREAD ENTRY", LEFT_CENTER[0] - 0.023, 0.078),
        # Review: named beside the thread callout it describes (the callout
        # text starts ~0.018 right of the adjuster axis, top at ~0.120).
        ("ADJUSTER ENTRY", adjuster_center[0] + 0.023, 0.1285),
        ("BOTTOM VIEW", BOTTOM_CENTER[0] - 0.012, BOTTOM_CENTER[1] - 0.016),
    ):
        if add_note(adapter, text, x, y) is None:
            raise RuntimeError(f"failed to add {text.lower()} view caption")
    if add_note(adapter, "ROTATED 90°", SECTION_CENTER[0] - 0.015, 0.195) is None:
        raise RuntimeError("failed to label the rotated section")
    # C1 verdict (2026-09-23): the native projected-view arrow is not
    # switchable through the documented API -- IProjectionArrow.Visible is
    # get-only and no document preference or IView member sets it; only the
    # PropertyManager "Arrow" box does.  Untested: an IProjectionArrow.SetLabel
    # side effect, a PropertyManager RunCommand route.  So each removed view
    # is named by a letter note whose straight leader is the viewing arrow.
    for letter, view, (text_xy, tip_xy) in (
        ("B", front, VIEW_B_ARROW),
        ("C", top, VIEW_C_ARROW),
    ):
        add_leader_note(
            adapter,
            letter,
            text_xy=text_xy,
            attach_xy=tip_xy,
            view=view,
            label=f"view {letter} viewing arrow",
        )

    foot_edge = _foot_edge(adapter, front)
    foot_y = _elevation_y(0.0, FRONT_CENTER)
    # Onto the foot edge itself, 2 mm in from the corner, so the symbol reads
    # as the seat face and not the side (review 2026-09-23).
    foot_right = (FRONT_CENTER[0] + BLOCK_X * _S / 2.0 - 0.002, foot_y)
    foot_finish = add_surface_finish(
        adapter,
        front,
        edge_entity=foot_edge,
        symbol_xy=(FRONT_CENTER[0] + 0.034, foot_y - 0.013),
        leader_attach_xy=foot_right,
        control=surface_finish_by_key(SURFACE_FINISHES, "foot_seat"),
        char_height=0.003,
        label="swing-platform locating foot seat",
    )
    finish_annotation = _early_bound(foot_finish.GetAnnotation(), "IAnnotation")
    if int(finish_annotation.GetLeaderCount()) != 1:
        raise RuntimeError("foot-seat finish does not have exactly one leader")
    leader_values = tuple(
        float(value) for value in finish_annotation.GetLeaderPointsAtIndex(0)
    )
    leader_points = tuple(
        leader_values[index : index + 3] for index in range(0, len(leader_values), 3)
    )
    if not any(
        abs(point[0] - foot_right[0]) < 1e-6
        and abs(point[1] - foot_right[1]) < 1e-6
        and abs(point[2]) < 1e-6
        for point in leader_points
    ):
        raise RuntimeError(
            "foot-seat finish leader missed the verified bottom-edge endpoint: "
            f"expected={foot_right!r}, points={leader_points!r}"
        )

    # Annotation insertion can regenerate a view with inherited display state;
    # every manufacturing view is explicitly HLR at export.
    for view in (front, top, right, left, back, section, bottom):
        set_hidden_lines_removed(adapter, view)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Cone Tip Block Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        # SolidWorks auto-inserts one descriptive "... Tapped Hole" note per
        # tapped Hole Wizard hole it shows: the adjuster's, and since U30 the
        # #6-32 foot tap's (run 66084ed9 removed 2 against an expected 1).
        redundant_note_substrings=("Tapped Hole",),
        expected_redundant_notes=2,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
