r"""Create the curated machinist drawing for the v2 cone pivot post.

The SLDPRT remains authoritative.  This recipe places the plan, the front
elevation, a true-shape cone-journal view, a native axial section and a
pictorial isometric, and imports exactly the model dimensions
``cone_pivot_post_spec.DRAWING_DIMENSIONS`` marks; shared sheet/template,
import, curation and export behaviour lives in ``_drawing_common``.

The casting has two axes and they are not parallel: the crank journal runs
along part +Z and the cone journal is yawed 12.5182 degrees about the vertical
body axis.  The part therefore persists a named view looking exactly down the
cone axis.  That view retains the boss end face and shows its Ø17.2 OD and
Ø12.281 bore as separate true-shape circles.  A native section through the
same axis shows the raised boss, its tangent relationship to the body OD and
its axial length in solid-line profile; the elevation keeps the crank journal,
whose own sketch plane is parallel to it.

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
from solidworks_mcp.adapters.pywin32_adapter import null_callout
from _drawing_common import (
    DrawingOutputs,
    add_native_hole_callout,
    add_property_linked_note,
    add_surface_finish,
    add_view_centerline,
    assert_imported_precision,
    curate_view_dimensions,
    create_section_view,
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
    CONE_AXIS_VIEW,
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
    add_note,
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
JOURNAL_CENTER = (0.240, 0.168)
ISO_CENTER = (0.360, 0.150)
SECTION_CENTER = (0.365, 0.242)
SECTION_SCALE = (1, 2)

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

# The A-A cutting plane contains the post axis and the inclined cone-journal
# axis.  Its trace spans the whole Ø44 top silhouette, so SolidWorks creates a
# complete native section rather than an open/partial cut.
_CONE_SECTION_HALF_SPAN_MM = 25.0
_CONE_AXIS_RAD = math.radians(INCLINE_DEG)
CONE_SECTION_LINE = (
    (
        _top_x(-_CONE_SECTION_HALF_SPAN_MM * math.sin(_CONE_AXIS_RAD)),
        _top_y(-_CONE_SECTION_HALF_SPAN_MM * math.cos(_CONE_AXIS_RAD)),
    ),
    (
        _top_x(_CONE_SECTION_HALF_SPAN_MM * math.sin(_CONE_AXIS_RAD)),
        _top_y(_CONE_SECTION_HALF_SPAN_MM * math.cos(_CONE_AXIS_RAD)),
    ),
)


FRONT_KEEP = {
    "MainBodyHt": (0.040, FRONT_CENTER[1]),
    "MainBodyDia": (0.150, 0.090),
    "CrankAxisY": (0.060, _front_y(CRANK_BORE_HEIGHT / 2.0)),
    "HeadHt": (0.132, _front_y(CRANK_BORE_HEIGHT)),
    "HeadDia": (FRONT_CENTER[0], 0.170),
    "CrankBossDia": (0.150, 0.105),
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
    "ConeBossLen": (SECTION_CENTER[0], 0.212),
}
JOURNAL_KEEP = {
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
    "CrankBossDia": "CRANK BOSS OD\nSPOTFACE NEAR END",
    "CrankBossLen": "CRANK BOSS LENGTH",
    "CrankBoreDia": "CRANK BORE THRU",
    "JournalBoreDia": "CONE BORE THRU",
    "ConeBossDia": "CONE JOURNAL BOSS",
    "ConeBossLen": "CONE BOSS LENGTH\nMIDPLANE",
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







def _model_face_evidence(
    model: Any,
) -> dict[str, list[tuple[str, tuple[float, ...]]]]:
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
    for feature, surfaces in rows.items():
        _telemetry.info(
            f"cone pivot post final BREP {feature}: {surfaces!r}"
        )
    return rows


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
    journal: Any,
    iso: Any,
    face_evidence: dict[str, list[tuple[str, tuple[float, ...]]]],
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
        ("journal", journal),
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
    if length(rows["journal"]["cone_axis"]) > 1e-8:
        raise RuntimeError(
            f"cone journal view is not normal to cone bore: {rows['journal']!r}"
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
    iso_crank = rows["isometric"]["crank_center"]
    iso_cone = rows["isometric"]["cone_center"]
    if iso_crank[1] <= iso_cone[1]:
        raise RuntimeError(
            "isometric feature identity is inverted: "
            f"crank y={iso_crank[1]!r}, cone y={iso_cone[1]!r}"
        )
    for label, evidence in rows.items():
        _telemetry.info(
            f"cone pivot post native view {label}: {evidence!r}"
        )
    _telemetry.info(
        "cone pivot post isometric feature identity: "
        f"upper centre={iso_crank!r} is CrankSprocketBoss/CrankBore at "
        f"model Y={CRANK_BORE_HEIGHT:.3f}mm; lower centre={iso_cone!r} is "
        f"ConeShaftBoss/ConeShaftBore at model Y={BORE_HEIGHT:.3f}mm; "
        f"top acute axis angle={acute:.6f} deg"
    )
    def plane_centres(feature_name: str) -> list[tuple[float, float, float]]:
        centres = [
            (values[3], values[4], values[5])
            for kind, values in face_evidence[feature_name]
            if kind == "plane"
        ]
        if len(centres) != 2:
            raise RuntimeError(
                f"{feature_name} has {len(centres)} BREP face centres, expected two"
            )
        return centres

    crank_face_centres = sorted(
        plane_centres("CrankSprocketBoss"),
        key=lambda point: point[2],
    )
    cone_face_centres = sorted(
        plane_centres("ConeShaftBoss"),
        key=lambda point: sum(point[i] * cone_axis[i] for i in range(3)),
    )
    iso_face_centres = {
        "crank_spot_face": model_point_in_view(
            adapter,
            iso,
            crank_face_centres[0],
            label="isometric crank spot-face centre",
        ),
        "crank_far_face": model_point_in_view(
            adapter,
            iso,
            crank_face_centres[1],
            label="isometric crank far-face centre",
        ),
        "cone_minus_face": model_point_in_view(
            adapter,
            iso,
            cone_face_centres[0],
            label="isometric cone minus-face centre",
        ),
        "cone_plus_face": model_point_in_view(
            adapter,
            iso,
            cone_face_centres[1],
            label="isometric cone plus-face centre",
        ),
    }
    crank_face_y = (
        iso_face_centres["crank_spot_face"][1],
        iso_face_centres["crank_far_face"][1],
    )
    cone_face_y = (
        iso_face_centres["cone_minus_face"][1],
        iso_face_centres["cone_plus_face"][1],
    )
    if min(crank_face_y) <= max(cone_face_y):
        raise RuntimeError(
            "isometric projected face bands overlap or invert: "
            f"{iso_face_centres!r}"
        )
    _telemetry.info(
        "cone pivot post isometric projected face centres (sheet metres): "
        f"{iso_face_centres!r}; both CrankSprocketBoss face centres are above "
        "both ConeShaftBoss face centres"
    )

def _assert_native_layout(
    adapter: Any,
    journal: Any,
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

    journal_values = tuple(float(value) for value in journal.GetOutline())
    if len(journal_values) != 4:
        raise RuntimeError("cone journal view has invalid final outline")
    journal_box = Box(*journal_values)
    journal_escape = journal_box.escape(sheet.region)
    if journal_escape is not None:
        raise RuntimeError(
            "cone journal view leaves the inner border: "
            f"{journal_box.format_mm()}, {journal_escape=}"
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
        f"journal={journal_box.format_mm()}; "
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
    face_evidence = _model_face_evidence(adapter.currentModel)
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
    journal = place_view(
        adapter,
        str(SOURCE),
        CONE_AXIS_VIEW,
        *JOURNAL_CENTER,
        scale=(1, 1),
    )
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 1))
    section = create_section_view(
        adapter,
        top,
        line_start=CONE_SECTION_LINE[0],
        line_end=CONE_SECTION_LINE[1],
        view_xy=SECTION_CENTER,
        section_label="A",
        scale=SECTION_SCALE,
        label="cone boss axial profile",
    )
    # The named journal view looks exactly down the inclined model axis.  Unlike
    # the axial section, it retains the boss end face, so its Ø17.2 OD and
    # Ø12.281 bore are two visible concentric circles with unambiguous leaders.
    for view in (front, top, journal, section):
        set_hidden_lines_removed(adapter, view)
    _assert_view_geometry(
        adapter,
        front=front,
        top=top,
        journal=journal,
        iso=iso,
        face_evidence=face_evidence,
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
    journal_annotations = curate_view_dimensions(
        adapter,
        journal,
        keep=JOURNAL_KEEP,
        view_label="cone journal",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    section_annotations = curate_view_dimensions(
        adapter,
        section,
        keep=SECTION_KEEP,
        view_label="cone boss axial section",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    annotations = [
        *front_annotations,
        *top_annotations,
        *journal_annotations,
        *section_annotations,
    ]
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    # The part authored these places (cone_pivot_post_spec.DRAWING_PRECISION);
    # this sheet only proves they survived the import.  A silent fallback to
    # the drawing document's two places would print the running bores without
    # the third place their fit band is written in.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)

    offset_dimension_text(
        adapter,
        journal_annotations,
        {"JournalAxisY": (0.190, 0.157)},
    )
    # On R2026x, SelectByID2 refused the feature-qualified
    # ``JournalPlanReference@cone-pivot-post-2@Section View A-A`` path.  The
    # section derives from the already-blanked Top view, so no second selector
    # call is made for that one observed derived-view path.
    for view in (front, top, journal, iso):
        _hide_witness_sketch(adapter, view, "JournalPlanReference")
    for view, label in ((front, "front"), (top, "top"), (journal, "cone journal")):
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
    # the ONE circular edge of body radius centred at y=0.  Its leader lands
    # on the seat's left quarter while the symbol sits clear of the body at right.
    add_surface_finish(
        adapter,
        front,
        edge_entity=_circular_edge(front, radius_mm=BLOCK_DIA / 2.0, center_y_mm=0.0),
        symbol_xy=(_front_x(30.0), _front_y(-6.0)),
        leader_attach_xy=(_front_x(-10.0), _front_y(0.0)),
        control=surface_finish_by_key(SURFACE_FINISHES, "foot_seat"),
        label="foot seat finish",
        char_height=0.0025,
    )
    add_surface_finish(
        adapter,
        front,
        edge_entity=_bore_rim_edge(front, diameter_mm=CRANK_BORE_DIA),
        symbol_xy=(0.055, 0.145),
        leader_attach_xy=model_point_in_view(
            adapter,
            front,
            (
                -(CRANK_BORE_DIA / 2.0) / math.sqrt(2.0) / 1000.0,
                (
                    CRANK_BORE_HEIGHT
                    + (CRANK_BORE_DIA / 2.0) / math.sqrt(2.0)
                )
                / 1000.0,
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
        journal,
        edge_entity=_bore_rim_edge(journal, diameter_mm=BORE_DIA),
        symbol_xy=(0.300, 0.120),
        leader_attach_xy=model_point_in_view(
            adapter,
            journal,
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
    add_note(
        adapter,
        "CONE JOURNAL VIEW - LOOK ALONG CONE AXIS",
        0.202,
        0.104,
    )
    add_note(
        adapter,
        f"TOP VIEW - AXIS PROFILE\nCRANK / CONE BORE AXES {INCLINE_DEG:.2f}°",
        0.130,
        0.187,
    )
    add_property_linked_note(adapter, "Manufacturing Notes", 0.014, 0.052)

    # Attaching dimensions and symbols can leave a stale hidden-line display.
    # Reassert each manufacturing view after its final annotation.
    set_hidden_lines_removed(adapter, front)
    set_hidden_lines_removed(adapter, top)
    set_hidden_lines_removed(adapter, journal)
    rebuild_drawing(adapter, label="final cone pivot post native layout")
    _assert_native_layout(
        adapter,
        journal,
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
