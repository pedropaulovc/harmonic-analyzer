r"""Create the curated machinist drawing for the cone swing platform.

The SLDPRT remains authoritative.  The plan imports the plate outline,
post-mount pattern, lock notch and corner radii; the native Hole Wizard callout
defines the pivot clearance hole; section A-A exposes the shallow pivot-head
relief and plate thickness in solid lines.  Display precision comes from the
model.

The platform is an asymmetric steel wedge with a 1/4-in close-clearance pivot
hole over the stock screw shoulder, paired 1/4-20 post-mount taps, an open
west-edge lock notch and four rounded plan corners.  The three plan views and
pivot section run 1:2; the isometric runs 1:3.

Run with SolidWorks open::

    uv run python cad\scripts\draw_cone_swing_platform.py cone-swing-platform
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, _early_bound, _read_member, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_native_hole_callout,
    add_property_linked_note,
    add_surface_finish,
    assert_imported_precision,
    create_section_view,
    check_drawing_layout,
    curate_view_dimensions,
    finalize_drawing,
    rebuild_drawing,
    new_project_drawing,
    model_point_in_view,
    read_required_properties,
    set_hidden_lines_removed,
    set_reference_dimension,
    stamp_drawing_summary,
    visible_view_entities,
)
from _drawing_registry import DRAWINGS_BY_NAME
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    dimension_name,
    place_view,
)
from _hole_spec import blind_cut_dia_mm
from _surface_finish import surface_finish_by_key
from cone_swing_platform_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    PIVOT_HOLE_DIA,
    PLATE_THICKNESS,
    POST_MOUNT_SPEC,
    SURFACE_FINISHES,
)
from diagnostics.drawing_layout_audit import collect_document, describe_sheet


SPEC = DRAWINGS_BY_NAME["cone_swing_platform"]
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

SHEET_SCALE = (1.0, 3.0)  # 1:3 sheet; the 1:2 plan keeps the 266 mm envelope in-zone

# Sheet layout (meters).  Three 1:2 plan views separate the profile, hole
# pattern and lock-notch definitions instead of routing unrelated leaders
# through one narrow 224-mm wedge.  The section and pictorial occupy the
# right-hand field.
PROFILE_CENTER = (0.075, 0.190)
FEATURE_CENTER = (0.180, 0.190)
NOTCH_CENTER = (0.260, 0.190)
ISO_CENTER = (0.355, 0.205)
SECTION_CENTER = (0.335, 0.105)

PROFILE_KEEP = {
    "PlateLenDim": (0.025, PROFILE_CENTER[1]),
    "NorthEastX": (0.045, 0.105),
    "NorthEdgeZ": (0.078, 0.150),
    "NorthWestX": (0.100, 0.115),
    "SouthWestX": (0.104, 0.258),
    "SouthEastX": (0.045, 0.259),
    # The Top view reverses the authored corner compass.  Place each native
    # radius beside its actual drawing attachment instead of routing four
    # leaders diagonally through the plate.
    "CornerNER": (0.135, 0.118),
    "CornerNWR": (0.025, 0.130),
    "CornerSWR": (0.110, 0.249),
    "CornerSER": (0.040, 0.240),
}
FEATURE_KEEP = {
    "PivotBearingReliefDia": (0.150, 0.155),
    "PostMountWestX": (0.150, 0.185),
    "PostMountWestZ": (0.225, 0.175),
    "PostMountEastX": (0.205, 0.185),
    "PostMountEastZ": (0.130, 0.175),
}
NOTCH_KEEP = {
    "CapECx": (0.250, 0.258),
    "CapECz": (0.305, 0.180),
    "CapEDia": (0.285, 0.259),
}
SECTION_KEEP = {
    "PlateThk": (0.300, 0.120),
    "PivotBearingReliefDepth": (0.365, 0.115),
}




_COSMETIC_THREAD_LAYER = "COSMETIC-THREADS-HIDDEN"


def _hide_profile_cosmetic_threads(adapter: Any, view: Any) -> None:
    """Hide the redundant model cosmetic-thread callout in the profile view."""
    draw = adapter.currentModel
    manager = _early_bound(draw.GetLayerManager(), "ILayerMgr")
    layer = manager.GetLayer(_COSMETIC_THREAD_LAYER)
    if layer is None:
        if (
            int(
                manager.AddLayer(
                    _COSMETIC_THREAD_LAYER,
                    "cosmetic thread ink hidden in profile view",
                    0,
                    0,
                    0,
                )
            )
            != 1
        ):
            raise RuntimeError("failed to add hidden cosmetic-thread layer")
        layer = manager.GetLayer(_COSMETIC_THREAD_LAYER)
    layer = _early_bound(layer, "ILayer")
    layer.Visible = False
    if bool(layer.Visible) or bool(layer.Printable):
        raise RuntimeError("cosmetic-thread layer did not remain hidden")

    hidden = 0
    hidden_callouts = 0
    for raw_annotation in _early_bound(view, "IView").GetAnnotations() or ():
        annotation = _early_bound(raw_annotation, "IAnnotation")
        if int(annotation.GetType()) != 1:  # swCosmeticThread
            continue
        annotation.Layer = _COSMETIC_THREAD_LAYER
        if str(annotation.Layer or "") != _COSMETIC_THREAD_LAYER:
            raise RuntimeError("profile cosmetic thread refused the hidden layer")
        thread = _early_bound(annotation.GetSpecificAnnotation(), "ICThread")
        raw_callout = _read_member(thread, "ThreadCallout")
        if raw_callout is not None:
            callout = _early_bound(raw_callout, "INote")
            callout_annotation = _early_bound(
                _read_member(callout, "GetAnnotation"), "IAnnotation"
            )
            callout_annotation.Layer = _COSMETIC_THREAD_LAYER
            if str(callout_annotation.Layer or "") != _COSMETIC_THREAD_LAYER:
                raise RuntimeError("profile thread callout refused the hidden layer")
            hidden_callouts += 1
        hidden += 1
    if not hidden:
        raise RuntimeError("profile view has no cosmetic thread to hide")
    if not hidden_callouts:
        raise RuntimeError("profile cosmetic threads have no callout note to hide")
    rebuild_drawing(adapter, label="hide profile cosmetic threads")


def _position_section_label(adapter: Any, section: Any) -> None:
    """Keep the native section caption below, rather than inside, the section."""
    notes = tuple(_read_member(section, "GetNotes") or ())
    if len(notes) != 1:
        raise RuntimeError(f"expected one native section label, found {len(notes)}")
    note = _early_bound(notes[0], "INote")
    annotation = _early_bound(_read_member(note, "GetAnnotation"), "IAnnotation")
    target = (0.335, 0.085, 0.0)
    if not annotation.SetPosition2(*target):
        raise RuntimeError("failed to position native section label")
    adapter.currentModel.EditRebuild3()
    actual = tuple(float(value) for value in _read_member(annotation, "GetPosition"))
    if max(abs(actual[i] - target[i]) for i in range(3)) > 1e-8:
        raise RuntimeError(
            f"native section label position did not persist: {actual}; "
            f"requested={target}"
        )


def _visible_plan_controls(adapter: Any, view: Any) -> tuple[Any, Any]:
    """Return the pivot and post-mount rims from the plan view.

    The north-end and long-straight-side edges were dropped with the GD&T that
    referenced them (see ``build``) -- nothing else on this sheet attaches to
    them.
    """
    expected_radius_m = PIVOT_HOLE_DIA / 2000.0
    expected_mount_radius_m = blind_cut_dia_mm(POST_MOUNT_SPEC) / 2000.0
    pivot_edges: list[Any] = []
    mount_edges: list[Any] = []
    components = adapter._attempt(lambda: view.GetVisibleComponents(), default=()) or ()
    for component in components:
        edges = (
            adapter._attempt(
                lambda c=component: view.GetVisibleEntities2(c, 1), default=()
            )
            or ()
        )
        for raw_edge in edges:
            edge = _early_bound(raw_edge, "IEdge")
            curve = _early_bound(edge.GetCurve(), "ICurve")
            if not curve.IsCircle():
                continue
            values = tuple(float(value) for value in curve.CircleParams)
            if abs(values[6] - expected_radius_m) <= 1e-6:
                pivot_edges.append(edge)
            if abs(values[6] - expected_mount_radius_m) <= 1e-6:
                mount_edges.append(edge)
    if not pivot_edges or len(mount_edges) < 2:
        raise RuntimeError("cone-platform plan view is missing pivot/mount controls")
    return pivot_edges[0], mount_edges[0]


def _horizontal_section_edge(
    view: Any, y_mm: float, *, label: str, prefer_right: bool = False
) -> Any:
    """Return a horizontal section edge on one broad-face station."""
    candidates: list[tuple[float, float, Any]] = []
    for raw_edge in visible_view_entities(view, 1, label=f"{label} section edges"):
        edge = _early_bound(raw_edge, "IEdge")
        start = edge.GetStartVertex()
        end = edge.GetEndVertex()
        if start is None or end is None:
            continue
        p0 = tuple(float(value) * 1000.0 for value in _early_bound(start, "IVertex").GetPoint())
        p1 = tuple(float(value) * 1000.0 for value in _early_bound(end, "IVertex").GetPoint())
        if abs(p0[1] - y_mm) <= 0.01 and abs(p1[1] - y_mm) <= 0.01:
            candidates.append((abs(p1[0] - p0[0]), 0.5 * (p0[0] + p1[0]), edge))
    if not candidates:
        raise RuntimeError(f"pivot section has no {label} edge at y={y_mm:.3f} mm")
    key_index = 1 if prefer_right else 0
    return max(candidates, key=lambda item: item[key_index])[2]


def _assert_corner_radius_attachment(adapter: Any, view: Any, annotations: list[Any]) -> None:
    """Prove the native R5 model dimension's arrow lies on its owned visible arc."""
    matches = [item for item in annotations if dimension_name(adapter, item) == "CornerSWR"]
    if len(matches) != 1:
        raise RuntimeError("expected one native CornerSWR radius annotation")
    annotation = _early_bound(matches[0], "IAnnotation")
    # Imported fillet dimensions can return unsupported/null annotation entities.
    # Record that API honestly; model-dimension ownership below is authoritative.
    entities = annotation.GetAttachedEntities3()
    entity_types = annotation.GetAttachedEntityTypes()
    print(
        f"R5 annotation entities_none={entities is None} "
        f"entity_nulls={tuple(item is None for item in (entities or ()))} types={entity_types!r}"
    )
    dangling = annotation.IsDangling()
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    owner = _early_bound(dimension.GetFeatureOwner(), "IFeature")
    print(f"R5 native model dimension owner={owner.Name!r} dangling={dangling!r}")
    if dangling is not False or str(owner.Name) != "CornerSW":
        raise RuntimeError("R5 is dangling or is not owned by native CornerSW")
    data = _early_bound(annotation.GetDisplayData(), "IDisplayData")
    arrows = [
        tuple(float(value) for value in data.GetArrowHeadAtIndex2(index))
        for index in range(int(data.GetArrowHeadCount()))
    ]
    if len(arrows) != 1 or len(arrows[0]) < 3:
        raise RuntimeError(f"expected one R5 arrow tip, found {arrows}")
    arrow = arrows[0]
    visible = visible_view_entities(view, 1, label="R5 visible corner edges")
    candidates = []
    for raw_face in owner.GetFaces() or ():
        face = _early_bound(raw_face, "IFace2")
        if str(_early_bound(face.GetFeature(), "IFeature").Name) != "CornerSW":
            continue
        for raw_edge in face.GetEdges() or ():
            edge = _early_bound(raw_edge, "IEdge")
            if not any(int(adapter.swApp.IsSame(edge, item)) == 1 for item in visible):
                continue
            if any(int(adapter.swApp.IsSame(edge, item[0])) == 1 for item in candidates):
                continue
            curve = _early_bound(edge.GetCurve(), "ICurve")
            if not curve.IsCircle():
                continue
            circle = tuple(float(value) for value in curve.CircleParams)
            if abs(circle[6] - 0.005) > 1e-8:
                continue
            center = model_point_in_view(adapter, view, circle[:3], label="R5 owned circle")
            if abs(center[0] - 0.0875) <= 0.001 and abs(center[1] - 0.2433) <= 0.001:
                candidates.append((edge, circle, center))
    if len(candidates) != 1:
        raise RuntimeError(f"expected one CornerSW-owned visible R5 edge at corner station, found {len(candidates)}")
    edge, circle, center = candidates[0]
    # Invert the measured plan-view X/Z basis at this owned edge's model Y.
    px = model_point_in_view(adapter, view, (circle[0] + 0.001, circle[1], circle[2]), label="R5 X basis")
    pz = model_point_in_view(adapter, view, (circle[0], circle[1], circle[2] + 0.001), label="R5 Z basis")
    xx, xy = px[0] - center[0], px[1] - center[1]
    zx, zy = pz[0] - center[0], pz[1] - center[1]
    det = xx * zy - zx * xy
    if abs(det) < 1e-12:
        raise RuntimeError("R5 plan projection is singular")
    dx, dy = arrow[0] - center[0], arrow[1] - center[1]
    model_tip = (
        circle[0] + 0.001 * (dx * zy - zx * dy) / det,
        circle[1],
        circle[2] + 0.001 * (xx * dy - dx * xy) / det,
    )
    # IEdge, not ICurve: the closest point is on the trimmed physical edge.
    closest = tuple(float(value) for value in edge.GetClosestPointOn(*model_tip))
    trim = _early_bound(edge.GetCurveParams3(), "ICurveParamData")
    distance = math.dist(model_tip, closest[:3])
    print(
        f"R5 owned visible trimmed edge: arrow_sheet_m={arrow[:3]} radius_m={circle[6]} "
        f"center_model_m={circle[:3]} trim_u=({trim.UMinValue},{trim.UMaxValue}) "
        f"closest_u={closest[3]} arrow_model_m={model_tip} "
        f"closest_model_m={closest[:3]} distance_m={distance}"
    )
    if not distance <= 0.00002:  # 0.01 mm on this 1:2 sheet; unchanged physical-edge bound.
        raise RuntimeError("R5 arrow does not land on its owned physical corner arc")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open cone-swing-platform source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "Profile View Note",
            "Feature View Note",
            "Notch View Note",
            "Isometric View Note",
            "Pivot Relief Fit",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Profile View Note",
            "Feature View Note",
            "Notch View Note",
            "Isometric View Note",
            "Pivot Relief Fit",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Cone Swing Platform Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "cone swing platform; wedge plate; pivot; lock notch",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    profile = place_view(
        adapter, str(SOURCE), "*Top", *PROFILE_CENTER, scale=(1, 2)
    )
    feature = place_view(
        adapter, str(SOURCE), "*Top", *FEATURE_CENTER, scale=(1, 2)
    )
    notch = place_view(adapter, str(SOURCE), "*Top", *NOTCH_CENTER, scale=(1, 2))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 3))
    for view in (profile, feature, notch, iso):
        set_hidden_lines_removed(adapter, view)

    pivot_xy = model_point_in_view(
        adapter, feature, (0.0, 0.0, 0.0), label="pivot section station"
    )
    feature_outline = tuple(float(value) for value in feature.GetOutline())
    section = create_section_view(
        adapter,
        feature,
        line_start=(feature_outline[0] - 0.002, pivot_xy[1]),
        line_end=(feature_outline[2] + 0.002, pivot_xy[1]),
        view_xy=SECTION_CENTER,
        section_label="A",
        scale=(2, 1),
        label="pivot bearing section",
    )
    cut = _early_bound(section.GetSection(), "IDrSection")
    cut.SetDisplayOnlySurfaceCut(True)
    rebuild_drawing(adapter, label="pivot section cut faces only")
    if cut.GetDisplayOnlySurfaceCut() is not True:
        raise RuntimeError("pivot section retained geometry beyond the cutting plane")
    _position_section_label(adapter, section)
    set_hidden_lines_removed(adapter, section)

    profile_annotations = curate_view_dimensions(
        adapter,
        profile,
        keep=PROFILE_KEEP,
        view_label="profile plan",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    _hide_profile_cosmetic_threads(adapter, profile)
    feature_annotations = curate_view_dimensions(
        adapter,
        feature,
        keep=FEATURE_KEEP,
        view_label="feature plan",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    notch_annotations = curate_view_dimensions(
        adapter,
        notch,
        keep=NOTCH_KEEP,
        view_label="notch plan",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    section_annotations = curate_view_dimensions(
        adapter,
        section,
        keep=SECTION_KEEP,
        view_label="pivot section",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    for annotation in section_annotations:
        if dimension_name(adapter, annotation) == "PlateThk":
            display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
            for witness_index in (0, 1):
                ok, _use_doc, old_gap = display.GetWitnessLineGap(witness_index, False, 0.0)
                if ok is not True:
                    raise RuntimeError("plate thickness witness gap could not be read")
                # Measured native witness origin is x415; the actual cut edge
                # is x310.2. Leave a visible 1.2 mm gap at x309, without
                # changing the model dimension or hiding either witness.
                gap = float(old_gap) + 0.106
                if display.SetWitnessLineGap(witness_index, False, gap) is not True:
                    raise RuntimeError("plate thickness witness gap was refused")
                ok, use_doc, actual_gap = display.GetWitnessLineGap(witness_index, False, 0.0)
                if ok is not True or use_doc or abs(float(actual_gap) - gap) > 1e-8:
                    raise RuntimeError("plate thickness witness gap did not persist")
                print(f"PlateThk witness {witness_index}: old_gap_m={old_gap} gap_m={actual_gap}")
            rebuild_drawing(adapter, label="plate thickness cut-edge witness gaps")
    relief_annotations = [
        item for item in section_annotations
        if dimension_name(adapter, item) == "PivotBearingReliefDepth"
    ]
    if len(relief_annotations) != 1:
        raise RuntimeError("expected one native pivot relief depth")
    relief_reference = set_reference_dimension(
        adapter, relief_annotations[0], label="matched pivot relief reference depth"
    )
    annotations = [
        *profile_annotations,
        *feature_annotations,
        *notch_annotations,
        *section_annotations,
    ]
    if not auto_center_marks(adapter, feature, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to feature plan")

    pivot_edge, mount_edge = _visible_plan_controls(adapter, feature)
    add_native_hole_callout(
        adapter,
        feature,
        callout_xy=(0.215, 0.150),
        label="pivot close-clearance hole",
        edge=pivot_edge,
    )
    add_native_hole_callout(
        adapter,
        feature,
        callout_xy=(0.200, 0.258),
        label="v2 post-mount tapped holes",
        edge=mount_edge,
    )
    add_surface_finish(
        adapter,
        section,
        symbol_xy=(0.300, 0.128),
        control=surface_finish_by_key(SURFACE_FINISHES, "post_seat"),
        label="post and tip-block seat finish",
        char_height=0.0025,
        entity=_horizontal_section_edge(section, 6.35, label="top seat"),
    )
    add_surface_finish(
        adapter,
        section,
        symbol_xy=(0.365, 0.120),
        control=surface_finish_by_key(SURFACE_FINISHES, "base_slide"),
        label="base sliding-face finish",
        char_height=0.0025,
        entity=_horizontal_section_edge(
            section, 0.0, label="base slide", prefer_right=True
        ),
    )

    add_property_linked_note(adapter, "Profile View Note", 0.045, 0.085)
    add_property_linked_note(adapter, "Feature View Note", 0.150, 0.085)
    add_property_linked_note(adapter, "Notch View Note", 0.245, 0.085)
    add_property_linked_note(adapter, "Isometric View Note", 0.315, 0.158)
    add_property_linked_note(
        adapter, "Pivot Relief Fit", 0.020, 0.065, char_height=0.0025
    )

    # Annotation insertion can invalidate the exported display geometry.
    for view in (profile, feature, notch, section, iso):
        set_hidden_lines_removed(adapter, view)
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    if (str(relief_reference.GetText(1)), str(relief_reference.GetText(2))) != ("(", ")"):
        raise RuntimeError("pivot relief reference state did not persist")
    _assert_corner_radius_attachment(adapter, profile, profile_annotations)
    if cut.GetDisplayOnlySurfaceCut() is not True:
        raise RuntimeError("pivot section lost its cut-only display after annotation")
    for face_name, model_y in (
        ("post_seat", PLATE_THICKNESS / 1000.0),
        ("base_slide", 0.0),
    ):
        projected = model_point_in_view(
            adapter, section, (0.0, model_y, 0.0), label=f"{face_name} projection"
        )
        print(
            f"section face {face_name}: model_y_mm={model_y * 1000:.3f} "
            f"sheet_xy_mm=({projected[0] * 1000:.3f},{projected[1] * 1000:.3f})"
        )
    for sheet_geometry in collect_document(adapter):
        print(describe_sheet(sheet_geometry))
        thickness_geometry = [
            item for item in sheet_geometry.annotations if item.label == "PlateThk"
        ]
        if len(thickness_geometry) != 1:
            raise RuntimeError("expected one measured plate thickness annotation")
        witnesses = [
            segment for segment in thickness_geometry[0].segments
            if abs(segment.y0 - segment.y1) < 1e-8
            and any(abs(segment.y0 - level) < 0.0001 for level in (0.09865, 0.11135))
        ]
        if len(witnesses) != 2 or any(
            abs(max(segment.x0, segment.x1) - 0.309) > 0.0005
            or abs(min(segment.x0, segment.x1) - 0.299) > 0.0005
            for segment in witnesses
        ):
            raise RuntimeError(f"plate thickness witnesses did not shorten to the cut edge: {witnesses}")
    check_drawing_layout(adapter, layout=SPEC.layout, stem=PART_STEM)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Cone Swing Platform Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
