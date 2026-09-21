r"""Create the curated machinist drawing for the v2 cone pivot post.

The SLDPRT remains authoritative.  This recipe places the plan, the front
elevation, ONE section and a pictorial isometric, and imports exactly the model
dimensions ``cone_pivot_post_spec.DRAWING_DIMENSIONS`` marks; shared
sheet/template, import, curation and export behaviour lives in
``_drawing_common``.

The casting has two axes and they are not parallel: the crank journal runs
along part +Z and the cone journal is yawed 12.5182 degrees about the vertical
body axis.  Sketches on ``ConeShaftNormal`` are therefore not parallel to the
front elevation, so the cone-journal sizes are imported into SECTION A-A -- a
full section cut in the PLAN perpendicular to the journal axis, which looks
straight down that axis and shows the pad and bore in true shape.  The
elevation keeps the crank journal, which its own sketch plane is parallel to.

Run with SolidWorks open::

    uv run python cad\scripts\draw_cone_pivot_post.py cone-pivot-post
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.pywin32_adapter import null_callout
from _drawing_common import (
    DrawingOutputs,
    add_native_hole_callout,
    add_property_linked_note,
    add_surface_finish,
    add_view_centerline,
    assert_imported_precision,
    create_section_view,
    curate_view_dimensions,
    finalize_drawing,
    model_point_in_view,
    new_project_drawing,
    offset_dimension_text,
    read_required_properties,
    rebuild_drawing,
    set_dimension_callouts,
    set_hidden_lines_removed,
    set_high_quality_shaded_with_edges,
    stamp_drawing_summary,
    visible_view_entities,
    view_name,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _surface_finish import surface_finish_by_key
from cone_pivot_post_spec import (
    ATTACHMENT_CBORE_DIA,
    ATTACHMENT_X,
    BLOCK_DIA,
    BLOCK_HEIGHT,
    BORE_DIA,
    BORE_HEIGHT,
    CRANK_BORE_DIA,
    CRANK_BORE_HEIGHT,
    CRANK_BOSS_END_Z,
    CRANK_BOSS_START_Z,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    INCLINE_DEG,
    SURFACE_FINISHES,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["cone_pivot_post"]
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

SHEET_SCALE = (1.0, 1.0)
_S = SHEET_SCALE[0] / 1000.0

# Third-angle: the plan sits above the front elevation, both at sheet scale.
FRONT_CENTER = (0.098, 0.112)
TOP_CENTER = (0.098, 0.209)
SECTION_CENTER = (0.240, 0.168)
ISO_CENTER = (0.360, 0.150)
SECTION_LABEL = "A"

# The checked-in landscape template's FINISH value cell, measured between its
# authored sheet-format rules.  Its linked INote extent is checked natively
# before export so wrapping can never spill into MATERIAL again.
_FINISH_CELL = (0.218, 0.0335, 0.310, 0.0450)

# ``place_view`` centres a view on its projected bounding box, so the model
# origin is offset from the view centre by half that box.  The elevation's box
# runs y=0..BLOCK_HEIGHT; the plan's runs the crank boss's full z extent.
_TOP_Z_CENTER = (CRANK_BOSS_START_Z + CRANK_BOSS_END_Z) / 2.0


def _front_y(model_y: float) -> float:
    return FRONT_CENTER[1] + (model_y - BLOCK_HEIGHT / 2.0) * _S


def _front_x(model_x: float) -> float:
    return FRONT_CENTER[0] + model_x * _S


def _top_x(model_x: float) -> float:
    return TOP_CENTER[0] + model_x * _S


def _top_y(model_z: float) -> float:
    # The *Top orientation looks down -Y: model +Z runs DOWN the sheet.
    return TOP_CENTER[1] + (_TOP_Z_CENTER - model_z) * _S


FRONT_KEEP = {
    "MainBodyHt": (0.040, FRONT_CENTER[1]),
    "MainBodyDia": (0.150, 0.090),
    "CrankAxisY": (0.060, _front_y(CRANK_BORE_HEIGHT / 2.0)),
    "HeadHt": (0.132, _front_y(CRANK_BORE_HEIGHT)),
    "HeadDia": (FRONT_CENTER[0], 0.170),
    "CrankBossDia": (0.158, _front_y(BLOCK_HEIGHT + 2.0)),
    "CrankBoreDia": (0.174, _front_y(CRANK_BORE_HEIGHT)),
}
TOP_KEEP = {
    "CrankBossLen": (0.056, TOP_CENTER[1]),
    "CrankBossStartZ": (0.038, _top_y(CRANK_BOSS_START_Z / 2.0)),
    "MountEastX": (0.075, 0.2525),
    "MountWestX": (0.110, 0.2525),
    "InclineAngle": (0.136, _top_y(28.0)),
}
SECTION_KEEP = {
    "JournalAxisY": (0.208, 0.156),
    "ConeBossDia": (0.292, 0.184),
    "JournalBoreDia": (0.292, 0.163),
}
# Non-preferred finished sizes, so the shop is told to BORE rather than left to
# hunt for a reamer that does not exist; the size limits are the part's.  The
# boss's near face is the one place a process word IS the requirement: on an
# as-cast collar the shop has to know that face is machined back to a station,
# not left as cast.
DIMENSION_CALLOUTS = {
    "CrankBossDia": "BOSS SPOT FACE",
    "CrankBoreDia": "CRANK BORE THRU",
    "JournalBoreDia": "CONE BORE THRU",
    "ConeBossDia": "CONE JOURNAL BOSS",
    "CrankBossStartZ": "TO BOSS SPOT FACE",
    "InclineAngle": "CONE/CRANK BORE AXES",
}


# COM edge-scan match slack; a selection aid, not product definition.
_EDGE_MATCH_TOLERANCE_MM = 0.01


def _circular_edge(
    view: Any,
    *,
    radius_mm: float,
    center_y_mm: float,
    center_x_mm: float | None = None,
) -> Any:
    """Return the model circular edge matching a radius and a model-Y height.

    ``center_x_mm`` breaks the tie between the two mounting counterbores,
    which differ only in X; without it the scan returns whichever SolidWorks
    enumerated first, and a leader routed for one hole then crosses the plan
    to reach the other.
    """
    candidates: list[tuple[float, Any]] = []
    for raw in visible_view_entities(view, 1, label="pivot-post circular edges"):
        edge = _early_bound(raw, "IEdge")
        curve = edge.GetCurve()
        if curve is None:
            continue
        curve = _early_bound(curve, "ICurve")
        if not curve.IsCircle():
            continue
        params = tuple(float(value) for value in curve.CircleParams)
        error = abs(params[6] * 1000.0 - radius_mm) + abs(
            params[1] * 1000.0 - center_y_mm
        )
        if center_x_mm is not None:
            error += abs(params[0] * 1000.0 - center_x_mm)
        candidates.append((error, edge))
    if not candidates:
        raise RuntimeError("view has no circular model edges")
    error, edge = min(candidates, key=lambda item: item[0])
    if error > _EDGE_MATCH_TOLERANCE_MM:
        where = f"at height {center_y_mm:.4f} mm"
        if center_x_mm is not None:
            where += f", x {center_x_mm:.4f} mm"
        raise RuntimeError(
            f"no circular edge matches radius {radius_mm:.4f} mm {where}"
        )
    return edge


@_telemetry.traced("drawing.bore_rim_scan")
def _bore_rim_edge(view: Any, *, diameter_mm: float) -> Any:
    """Return a rim adjacent to the unique cylindrical bore of this diameter."""
    expected_radius_m = diameter_mm / 2000.0
    for raw in visible_view_entities(view, 1, label="pivot-post bore rims"):
        edge = _early_bound(raw, "IEdge")
        for face in edge.GetTwoAdjacentFaces2() or []:
            if face is None:
                continue
            face = _early_bound(face, "IFace2")
            surface = _early_bound(face.GetSurface(), "ISurface")
            if not surface.IsCylinder():
                continue
            if abs(float(surface.CylinderParams[6]) - expected_radius_m) > 1e-6:
                continue
            return edge
    raise RuntimeError(f"view has no rim adjacent to a {diameter_mm:g} mm bore")


def _section_cut() -> tuple[tuple[float, float], tuple[float, float]]:
    """Sheet endpoints of the plan cut taken PERPENDICULAR to the cone journal.

    The journal's plan direction is ``(sin, -cos)`` in sheet axes (model +Z
    runs down the plan), so a cut along its perpendicular makes the section
    look straight down the journal axis -- the only orientation in which the
    inclined pad and bore are true shape and their ConeShaftNormal sketch
    dimensions can be imported at all.
    """
    incline = math.radians(INCLINE_DEG)
    axis = (_top_x(0.0), _top_y(0.0))
    half = 0.032
    step = (half * math.cos(incline), half * math.sin(incline))
    return (
        (axis[0] - step[0], axis[1] - step[1]),
        (axis[0] + step[0], axis[1] + step[1]),
    )


def _orient_section(adapter: Any, view: Any) -> None:
    """Show the journal section upright, with the casting's top at the top.

    The section plane contains model +Y and the plan-normal cross-axis.  Native
    section creation can mirror either axis and inherits the oblique cutting
    line's sheet rotation, so project both model axes, reverse the cut when
    needed, then remove that rotation.  This keeps the mounting counterbores at
    the same end as the front elevation instead of making the shop mentally
    invert SECTION A-A.
    """

    section_view = _early_bound(view, "IView")
    section = section_view.GetSection()
    if section is None:
        raise RuntimeError("cone journal section has no section definition")
    section = _early_bound(section, "IDrSection")
    incline = math.radians(INCLINE_DEG)
    cross_axis = (0.040 * math.cos(incline), 0.0, -0.040 * math.sin(incline))

    def projected_axes() -> tuple[tuple[float, float], tuple[float, float]]:
        origin = model_point_in_view(
            adapter, section_view, (0.0, 0.0, 0.0), label="journal section origin"
        )
        endpoints = (
            model_point_in_view(
                adapter,
                section_view,
                cross_axis,
                label="journal section horizontal axis",
            ),
            model_point_in_view(
                adapter,
                section_view,
                (0.0, 0.040, 0.0),
                label="journal section vertical axis",
            ),
        )
        return tuple(
            tuple(endpoint[index] - origin[index] for index in range(2))
            for endpoint in endpoints
        )

    horizontal, vertical = projected_axes()
    if horizontal[0] * vertical[1] - horizontal[1] * vertical[0] < 0.0:
        reversed_cut = not bool(section.GetReversedCutDirection())
        section.SetReversedCutDirection(reversed_cut)
        rebuild_drawing(adapter, label="orient cone journal section")
        if bool(section.GetReversedCutDirection()) != reversed_cut:
            raise RuntimeError("cone journal section cut reversal did not persist")
        horizontal, vertical = projected_axes()

    section_view.Angle = float(section_view.Angle) - math.atan2(
        horizontal[1], horizontal[0]
    )
    rebuild_drawing(adapter, label="orient cone journal section")
    horizontal, vertical = projected_axes()
    if (
        horizontal[0] <= 0.0
        or abs(horizontal[1]) > 1e-8
        or vertical[1] <= 0.0
        or abs(vertical[0]) > 1e-8
    ):
        raise RuntimeError(
            "cone journal section axes did not persist upright: "
            f"{horizontal=}, {vertical=}"
        )

    # A section's native Position is its cut-plane origin, not its outline
    # centre.  Rotation therefore moved this 86 mm-tall view through the top
    # border; translate the native position by the measured outline-centre
    # error and prove the visible geometry is centred on the declared target.
    outline = tuple(float(value) for value in section_view.GetOutline())
    position = tuple(float(value) for value in section_view.Position)
    if len(outline) != 4 or len(position) != 2:
        raise RuntimeError("cone journal section has invalid bounds")
    target = [
        position[axis]
        + SECTION_CENTER[axis]
        - (outline[axis] + outline[axis + 2]) / 2.0
        for axis in range(2)
    ]
    if not section_view.SetViewPosition(double_array(target), False):
        raise RuntimeError("failed to centre cone journal section")
    rebuild_drawing(adapter, label="centre cone journal section")
    outline = tuple(float(value) for value in section_view.GetOutline())
    outline_center = tuple(
        (outline[axis] + outline[axis + 2]) / 2.0 for axis in range(2)
    )
    if math.dist(outline_center, SECTION_CENTER) > 0.0001:
        raise RuntimeError(
            "cone journal section centre did not persist: "
            f"{outline_center=}, target={SECTION_CENTER}"
        )



def _model_face_evidence(model: Any) -> None:
    """Read the final BREP surfaces behind the four disputed callouts."""
    rows: dict[str, list[tuple[str, tuple[float, ...]]]] = {}
    part = _early_bound(model, "IPartDoc")
    for name in (
        "CrankSprocketBoss",
        "CrankSpotFace",
        "CrankBore",
        "ConeShaftBoss",
        "ConeShaftBore",
    ):
        feature = part.FeatureByName(name)
        if feature is None:
            raise RuntimeError(f"missing model feature for drawing evidence: {name}")
        feature = _early_bound(feature, "IFeature")
        surfaces = []
        seen = set()
        for raw_face in feature.GetFaces() or ():
            face = _early_bound(raw_face, "IFace2")
            surface = _early_bound(face.GetSurface(), "ISurface")
            if surface.IsCylinder():
                item = (
                    "cylinder",
                    tuple(round(float(value), 9) for value in surface.CylinderParams),
                )
            elif surface.IsPlane():
                item = (
                    "plane",
                    tuple(round(float(value), 9) for value in surface.PlaneParams),
                )
            else:
                continue
            if item not in seen:
                seen.add(item)
                surfaces.append(item)
        if not surfaces:
            raise RuntimeError(f"{name} exposes no planar/cylindrical BREP surfaces")
        rows[name] = surfaces
    _telemetry.info(f"cone pivot post final BREP surfaces: {rows!r}")


def _hide_witness_sketch(adapter: Any, view: Any, sketch_name: str) -> None:
    """Hide one model sketch in one drawing view, retaining imported dimensions."""
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    typed_view = _early_bound(view, "IView")
    name = view_name(adapter, typed_view)
    if not drawing.ActivateView(name):
        raise RuntimeError(f"failed to activate {name!r} to hide {sketch_name}")
    root = typed_view.RootDrawingComponent2(False)
    if root is None:
        raise RuntimeError(f"{name!r} has no drawing component for {sketch_name}")
    component = str(_early_bound(root, "IDrawingComponent").Name)
    qualified = f"{sketch_name}@{component}@{name}"
    draw.ClearSelection2(True)
    if not draw.Extension.SelectByID2(
        qualified, "SKETCH", 0.0, 0.0, 0.0, False, 0, null_callout(), 0
    ):
        raise RuntimeError(f"failed to select drawing witness sketch {qualified!r}")
    # BlankSketch is a VT_VOID mutator.  Its drawing-view override has no
    # corresponding getter: IFeature.Visible reports the model feature's
    # global state, not the per-view override (and therefore remains "shown").
    # The selected qualified path above is the API's documented call form; the
    # exported sheet is the authoritative read-back for this view-local change.
    draw.BlankSketch()
    rebuild_drawing(adapter, label=f"hide {sketch_name} in {name}")
    draw.ClearSelection2(True)
    _telemetry.info(f"drawing witness sketch blanked in view: {qualified}")


def _assert_view_geometry(
    adapter: Any,
    *,
    front: Any,
    top: Any,
    section: Any,
    iso: Any,
) -> None:
    """Prove which bore axis each manufacturing view is normal to."""
    incline = math.radians(INCLINE_DEG)
    crank_axis = (0.0, 0.0, 1.0)
    cone_axis = (math.sin(incline), 0.0, math.cos(incline))
    crank_center = (0.0, CRANK_BORE_HEIGHT / 1000.0, 0.0)
    cone_center = (0.0, BORE_HEIGHT / 1000.0, 0.0)
    sample = 0.040

    rows = {}
    for label, raw_view in (
        ("front", front),
        ("top", top),
        ("section", section),
        ("isometric", iso),
    ):
        view = _early_bound(raw_view, "IView")
        transform = _early_bound(view.ModelToViewTransform, "IMathTransform")
        matrix = tuple(round(float(value), 9) for value in transform.ArrayData)

        def projected(
            center: tuple[float, float, float],
            axis: tuple[float, float, float],
        ) -> tuple[float, float]:
            origin = model_point_in_view(
                adapter, view, center, label=f"{label} bore-axis origin"
            )
            endpoint = model_point_in_view(
                adapter,
                view,
                tuple(center[i] + sample * axis[i] for i in range(3)),
                label=f"{label} bore-axis endpoint",
            )
            return tuple(endpoint[i] - origin[i] for i in range(2))

        rows[label] = {
            "transform": matrix,
            "crank_center": model_point_in_view(
                adapter, view, crank_center, label=f"{label} crank centre"
            ),
            "cone_center": model_point_in_view(
                adapter, view, cone_center, label=f"{label} cone centre"
            ),
            "crank_axis": projected(crank_center, crank_axis),
            "cone_axis": projected(cone_center, cone_axis),
        }

    def length(vector: tuple[float, float]) -> float:
        return math.hypot(*vector)

    if length(rows["front"]["crank_axis"]) > 1e-8:
        raise RuntimeError(f"front is not normal to crank bore: {rows['front']!r}")
    if length(rows["section"]["cone_axis"]) > 1e-8:
        raise RuntimeError(
            f"cone journal section is not normal to cone bore: {rows['section']!r}"
        )
    top_crank = rows["top"]["crank_axis"]
    top_cone = rows["top"]["cone_axis"]
    cosine = sum(a * b for a, b in zip(top_crank, top_cone)) / (
        length(top_crank) * length(top_cone)
    )
    acute = math.degrees(math.acos(max(-1.0, min(1.0, abs(cosine)))))
    if abs(acute - INCLINE_DEG) > 0.01:
        raise RuntimeError(
            f"top-view bore-axis angle {acute:.6f} != {INCLINE_DEG:.6f}"
        )
    _telemetry.info(
        f"cone pivot post native view transforms: {rows!r}; "
        f"top acute axis angle={acute:.6f} deg"
    )

def _assert_native_layout(
    adapter: Any,
    section: Any,
    *,
    expected_finish: str,
) -> None:
    """Prove the final live sheet geometry before spending an export."""
    from _layout_geometry import (
        DEFAULT_TEXT_TOUCH_TOL_M,
        Box,
        audit_sheet,
        format_findings,
        segment_box_overlap_length,
    )
    from diagnostics.drawing_layout_audit import collect_document

    sheets = collect_document(adapter)
    if len(sheets) != 1:
        raise RuntimeError(f"cone pivot post must have one drawing sheet: {len(sheets)}")
    sheet = sheets[0]

    section_values = tuple(float(value) for value in section.GetOutline())
    if len(section_values) != 4:
        raise RuntimeError("cone journal section has invalid final outline")
    section_box = Box(*section_values)
    section_escape = section_box.escape(sheet.region)
    if section_escape is not None:
        raise RuntimeError(
            "cone journal section leaves the inner border: "
            f"{section_box.format_mm()}, {section_escape=}"
        )

    finish_notes = []
    drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
    sheet_view = _early_bound(drawing.GetFirstView(), "IView")
    for raw_annotation in sheet_view.GetAnnotations() or ():
        annotation = _early_bound(raw_annotation, "IAnnotation")
        if int(annotation.GetType()) != 6:
            continue
        note = _early_bound(annotation.GetSpecificAnnotation(), "INote")
        linked = str(note.PropertyLinkedText or "")
        if "$prp" in linked.casefold() and "finish" in linked.casefold():
            finish_notes.append(note)
    if len(finish_notes) != 1:
        raise RuntimeError(
            "landscape template must expose exactly one linked Finish note: "
            f"{len(finish_notes)}"
        )
    finish_note = finish_notes[0]
    actual_finish = str(finish_note.GetText() or "").replace("\r\n", "\n")
    if actual_finish != expected_finish:
        raise RuntimeError(
            "Finish title-block readback mismatch: "
            f"{actual_finish!r} != {expected_finish!r}"
        )
    extent = tuple(float(value) for value in finish_note.GetExtent())
    if len(extent) != 6:
        raise RuntimeError(f"Finish title-block note has invalid extent: {extent!r}")
    finish_box = Box(
        min(extent[0], extent[3]),
        min(extent[1], extent[4]),
        max(extent[0], extent[3]),
        max(extent[1], extent[4]),
    )
    finish_cell = Box(*_FINISH_CELL)
    if (
        finish_box.xmin < finish_cell.xmin
        or finish_box.ymin < finish_cell.ymin
        or finish_box.xmax > finish_cell.xmax
        or finish_box.ymax > finish_cell.ymax
    ):
        raise RuntimeError(
            "Finish title-block note leaves its authored cell: "
            f"note={finish_box.format_mm()}, cell={finish_cell.format_mm()}"
        )

    surface_boxes = [
        box
        for annotation in sheet.annotations
        if annotation.kind == "surface-finish"
        for box in annotation.text_boxes
    ]
    if len(surface_boxes) != 3:
        raise RuntimeError(
            "cone pivot post must expose three native Ra text boxes: "
            f"{len(surface_boxes)}"
        )
    journal_dimensions = [
        annotation
        for annotation in sheet.annotations
        if annotation.label == "JournalAxisY"
    ]
    if len(journal_dimensions) != 1:
        raise RuntimeError(
            "expected one native JournalAxisY annotation, found "
            f"{len(journal_dimensions)}"
        )
    journal_dimension = journal_dimensions[0]
    text_interiors = [
        Box(
            box.xmin + DEFAULT_TEXT_TOUCH_TOL_M,
            box.ymin + DEFAULT_TEXT_TOUCH_TOL_M,
            box.xmax - DEFAULT_TEXT_TOUCH_TOL_M,
            box.ymax - DEFAULT_TEXT_TOUCH_TOL_M,
        )
        for box in journal_dimension.text_boxes
    ]
    own_overlap = max(
        (
            segment_box_overlap_length(segment, box)
            for box in text_interiors
            for segment in journal_dimension.segments
        ),
        default=0.0,
    )
    if own_overlap > DEFAULT_TEXT_TOUCH_TOL_M:
        raise RuntimeError(
            "JournalAxisY's own dimension ink crosses its text by "
            f"{own_overlap * 1000.0:.3f} mm"
        )
    findings = audit_sheet(sheet)
    if findings:
        raise RuntimeError(
            "cone pivot post native annotation layout failed:\n"
            f"{format_findings(findings)}"
        )
    _telemetry.info(
        "cone pivot post native layout: "
        f"section={section_box.format_mm()}; "
        f"finish={finish_box.format_mm()} in {finish_cell.format_mm()}; "
        f"Ra={[box.format_mm() for box in surface_boxes]}; "
        f"JournalAxisY self-overlap={own_overlap * 1000.0:.3f}mm"
    )


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open cone-pivot-post source", await adapter.open_model(str(SOURCE)))
    source_properties = read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
        ),
    )
    _model_face_evidence(adapter.currentModel)
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Cone Pivot Post Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "bossed cast-iron post; inclined cone journal; crank journal",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(1, 1))
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(1, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 1))
    set_hidden_lines_removed(adapter, front)
    # SECTION A-A defines the inclined bore and the plan's native 12.52-degree
    # model dimension defines its direction, so dashed bore edges add no
    # manufacturing information here and only crowd the holes and cut line.
    set_hidden_lines_removed(adapter, top)

    cut_start, cut_end = _section_cut()
    section = create_section_view(
        adapter,
        top,
        line_start=cut_start,
        line_end=cut_end,
        view_xy=SECTION_CENTER,
        section_label=SECTION_LABEL,
        label="cone journal section",
    )
    _orient_section(adapter, section)
    set_hidden_lines_removed(adapter, section)
    _assert_view_geometry(
        adapter,
        front=front,
        top=top,
        section=section,
        iso=iso,
    )

    front_annotations = curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
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
    section_annotations = curate_view_dimensions(
        adapter,
        section,
        keep=SECTION_KEEP,
        view_label="section",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    annotations = [*front_annotations, *top_annotations, *section_annotations]
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    # The part authored these places (cone_pivot_post_spec.DRAWING_PRECISION);
    # this sheet only proves they survived the import.  A silent fallback to
    # the drawing document's two places would print the running bores without
    # the third place their fit band is written in.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)

    offset_dimension_text(
        adapter,
        section_annotations,
        {"JournalAxisY": (0.190, 0.157)},
    )
    for view in (front, top, iso):
        _hide_witness_sketch(adapter, view, "JournalPlanReference")
    for view, label in ((front, "front"), (top, "top"), (section, "section")):
        if not auto_center_marks(adapter, view, holes=True, size=0.0025):
            raise RuntimeError(f"failed to add ASME center marks to the {label} view")
    add_view_centerline(
        adapter,
        front,
        face_xy=(_front_x(0.0), _front_y(20.0)),
        label="main body axis",
    )
    add_view_centerline(
        adapter,
        top,
        face_xy=(_top_x(0.0), _top_y(35.0)),
        label="crank boss axis",
    )

    add_native_hole_callout(
        adapter,
        top,
        edge=_circular_edge(
            top,
            radius_mm=ATTACHMENT_CBORE_DIA / 2.0,
            center_y_mm=BLOCK_HEIGHT,
            center_x_mm=ATTACHMENT_X,
        ),
        callout_xy=(0.160, 0.250),
        label="mounting counterbores",
        process="DRILL",
    )

    # The seat is the elevation's bottom line: the O42.011 foot rim seen
    # edge-on.  A coordinate pick on that line failed on the farm (the two
    # mounting-hole exit rims project onto the same line, so the hit-test has
    # nothing unambiguous to return), so the rim is found by its geometry --
    # the ONE circular edge of body radius centred at y=0 -- and the leader is
    # pinned to the seat's left quarter, clear of the MainBodyHt witness line.
    add_surface_finish(
        adapter,
        front,
        edge_entity=_circular_edge(front, radius_mm=BLOCK_DIA / 2.0, center_y_mm=0.0),
        symbol_xy=(_front_x(-26.0), _front_y(-8.0)),
        leader_attach_xy=(_front_x(-10.0), _front_y(0.0)),
        control=surface_finish_by_key(SURFACE_FINISHES, "foot_seat"),
        label="foot seat finish",
        char_height=0.0025,
    )
    add_surface_finish(
        adapter,
        front,
        edge_entity=_bore_rim_edge(front, diameter_mm=CRANK_BORE_DIA),
        symbol_xy=(0.175, 0.108),
        leader_attach_xy=model_point_in_view(
            adapter,
            front,
            (
                0.0,
                (CRANK_BORE_HEIGHT - CRANK_BORE_DIA / 2.0) / 1000.0,
                0.0,
            ),
            label="crank bore finish anchor",
        ),
        control=surface_finish_by_key(SURFACE_FINISHES, "crank_bore"),
        label="crank bore finish",
        char_height=0.0025,
    )
    add_surface_finish(
        adapter,
        section,
        edge_entity=_bore_rim_edge(section, diameter_mm=BORE_DIA),
        symbol_xy=(0.300, 0.120),
        leader_attach_xy=model_point_in_view(
            adapter,
            section,
            (
                0.0,
                (BORE_HEIGHT - BORE_DIA / 2.0) / 1000.0,
                0.0,
            ),
            label="cone journal bore finish anchor",
        ),
        control=surface_finish_by_key(SURFACE_FINISHES, "journal_bore"),
        label="cone journal bore finish",
        char_height=0.0025,
    )

    add_property_linked_note(adapter, "Manufacturing Notes", 0.014, 0.052)

    # Attaching dimensions and symbols can leave a stale hidden-line display.
    # Reassert each manufacturing view after its final annotation.
    set_hidden_lines_removed(adapter, front)
    set_hidden_lines_removed(adapter, top)
    set_hidden_lines_removed(adapter, section)
    rebuild_drawing(adapter, label="final cone pivot post native layout")
    _assert_native_layout(
        adapter,
        section,
        expected_finish=source_properties["Finish"],
    )

    set_high_quality_shaded_with_edges(adapter, iso, label="pictorial isometric")

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Cone Pivot Post Manufacturing Drawing",
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
