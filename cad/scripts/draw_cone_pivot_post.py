r"""Create the curated machinist drawing for the v2 cone pivot post.

The SLDPRT remains authoritative.  This recipe places the plan, the front
elevation, a true-shape cone-journal view, a native section through the cone
bore plane and a pictorial isometric, and imports exactly the model dimensions
``cone_pivot_post_spec.DRAWING_DIMENSIONS`` marks; shared sheet/template,
import, curation and export behaviour lives in ``_drawing_common``.

The casting has two axes and they are not parallel: the crank journal runs
along part +Z and the cone journal is yawed 12.5182 degrees about the vertical
body axis.  The part therefore persists a named view looking exactly down the
cone axis.  That view retains the boss end face and shows its Ø17.2 OD and
Ø12.281 bore as separate true-shape circles.  A native section in the
horizontal cone-bore plane removes the head from the projection and exposes
the raised boss corners beyond the Ø42 body, together with the boss's axial
length, in a hatched solid-line profile; the elevation keeps the crank
journal, whose own sketch plane is parallel to it.

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
    add_attached_note,
    add_native_hole_callout,
    add_property_linked_note,
    add_surface_finish,
    add_view_centerline,
    assert_imported_precision,
    curate_view_dimensions,
    create_section_view,
    dimension_name,
    finalize_drawing,
    model_point_in_view,
    new_project_drawing,
    offset_dimension_text,
    read_required_properties,
    rebuild_drawing,
    set_dimension_callouts,
    set_hole_callout_precision,
    set_hidden_lines_removed,
    set_reference_dimension,
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
    CONE_BOSS_LENGTH,
    CRANK_BORE_DIA,
    CRANK_BORE_HEIGHT,
    CRANK_BOSS_END_Z,
    CRANK_BOSS_START_Z,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    INCLINE_DEG,
    POST_DOWEL_REAM_DIA,
    POST_DOWEL_XZ,
    SURFACE_FINISHES,
)
from cone_post_dowel_spec import POST_DOWEL_CALLOUT
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
JOURNAL_CENTER = (0.235, 0.160)
ISO_CENTER = (0.360, 0.150)
SECTION_CENTER = (0.295, 0.230)
SECTION_CAPTION = (0.295, 0.201)
SECTION_LABEL_SCALE_TEXT = "SCALE"
SECTION_SCALE = (1, 1)
# #917 S1: the dowel pair opens only on the foot, so a foot view (looking up
# at it, 1:2) carries its callout.  FOOT_CENTER is only where the view is
# inserted: the view, its caption and the dowel callout are then planned
# together from the sheet's READ-BACK boxes (_place_foot_group).  Literal
# guesses failed twice (917-s1-5974: caption over the top border, callout
# leader across the plan; 917-s1-9eb0: no caption spot on a 1-D sweep).
FOOT_CENTER = (0.228, 0.238)
FOOT_SCALE = (1, 2)
FOOT_VIEW_NOTE = "VIEW C - FOOT\nSCALE 1:2"
# Clearance between read-back boxes: caption to border, caption to its view,
# callout text to either neighbouring view outline.
FOOT_LAYOUT_GAP = 0.002
# The dowel callout's prefix, re-wrapped (same words, same order): the break
# at its end puts the native size/band/depth on a row of its own.  Joined to
# "REAM (...) FROM FOOT" that row ran ~120 mm, wider than any free field on
# the sheet (offline search on the 917-s1-9eb0 dump: no spot above ~100 mm).
FOOT_DOWEL_PREFIX = POST_DOWEL_CALLOUT + "\n"

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

# The A-A cutting plane is horizontal at the cone bore's model-Y station.  It
# therefore contains the inclined cone axis, while removing the head that
# hides the boss in the ordinary Top projection.  Its section shows the angled
# 42 x 17.2 boss strip extending past the Ø42 body circle at all four corners.
_CONE_SECTION_HALF_SPAN_MM = 25.0
CONE_SECTION_LINE = (
    (
        _front_x(-_CONE_SECTION_HALF_SPAN_MM),
        _front_y(BORE_HEIGHT),
    ),
    (
        _front_x(_CONE_SECTION_HALF_SPAN_MM),
        _front_y(BORE_HEIGHT),
    ),
)


FRONT_KEEP = {
    "MainBodyHt": (0.040, FRONT_CENTER[1]),
    "MainBodyDia": (0.150, 0.080),
    # A REFERENCE since U31: the crank bore is located from the cone bore
    # (View B), so its height above the foot only follows that chain.
    "CrankAxisY": (0.060, _front_y(CRANK_BORE_HEIGHT / 2.0)),
    "HeadHt": (0.150, _front_y(CRANK_BORE_HEIGHT)),
    "CrankBossDia": (0.132, 0.120),
    # Held 10 mm clear of View B's toleranced crank-above-cone text: at
    # x=0.155 the two sat 4.15 mm apart, under one text height (r7 audit).
    "CrankBoreDia": (0.149, 0.172),
}
# The Ø44 collar is dimensioned on its true-shape plan circle, not across the
# elevation: there its dimension line sat directly under the crank-bore size
# and finish leaders, which both had to cross it to reach the bore.  The text
# sits in the free quadrant between the crank-boss length and the boss.
TOP_KEEP = {
    "HeadDia": (0.071, 0.188),
    "CrankBossLen": (0.056, TOP_CENTER[1]),
    # The spot-face station stands between the crank-boss length and the
    # circle, its value on its own dimension line.  On the right its upper
    # witness line ran level with the counterbore callout's shelf and that
    # callout's leader crossed its dimension line, so its text had to be
    # offset to a distant shelf, where a blind reader took it for a note.
    "CrankBossStartZ": (0.0655, 0.2338),
    "MountEastX": (0.075, 0.2525),
    "MountWestX": (0.110, 0.2525),
    "InclineAngle": (0.142, _top_y(28.0)),
}
SECTION_KEEP = {
    "ConeBossLen": (0.355, 0.235),
}
# The crank bore is located from the cone bore (U31), so its spacing chains
# off the cone-axis height on the same dimension line, in the one view that
# shows both bores.  Its toleranced text stands off the line like 33.37's,
# between the crank-bore size callout and the section-axes label.
JOURNAL_KEEP = {
    "JournalAxisY": (0.208, 0.156),
    "CrankAboveCone": (0.208, 0.170),
    "ConeBossDia": (0.292, 0.172),
    "JournalBoreDia": (0.292, 0.153),
}
# The non-preferred bore limits tell the shop what to inspect without imposing
# a particular cutting method.  Ø21.93 is the crank boss OD -- the elevation
# looks at the boss's far end, so it is labelled as the boss, not as the
# spot-faced near face -- and the 21.3753 mm station locates that near face
# from the post axis without inventing a depth against the curved collar.
DIMENSION_CALLOUTS = {
    "HeadDia": "COLLAR",
    "CrankBossDia": "CRANK BOSS",
    "CrankBossLen": "CRANK BOSS LENGTH",
    "CrankBoreDia": "CRANK BORE THRU",
    "JournalBoreDia": "CONE BORE THRU",
    "ConeBossDia": "CONE JOURNAL BOSS OD",
    "ConeBossLen": "CONE BOSS FACE-TO-FACE",
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
    center_z_mm: float | None = None,
) -> Any:
    """Return the model circular edge matching a radius and a model-Y height.

    ``center_x_mm`` breaks the tie between the two mounting counterbores,
    which differ only in X; without it the scan returns whichever SolidWorks
    enumerated first, and a leader routed for one hole then crosses the plan
    to reach the other.  ``center_z_mm`` does the same for the dowel pair,
    which differ only in Z.
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
        if center_z_mm is not None:
            error += abs(params[2] * 1000.0 - center_z_mm)
        candidates.append((error, edge))
    if not candidates:
        raise RuntimeError("view has no circular model edges")
    error, edge = min(candidates, key=lambda item: item[0])
    if error > _EDGE_MATCH_TOLERANCE_MM:
        where = f"at height {center_y_mm:.4f} mm"
        if center_x_mm is not None:
            where += f", x {center_x_mm:.4f} mm"
        if center_z_mm is not None:
            where += f", z {center_z_mm:.4f} mm"
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

def _prepare_cone_section(adapter: Any, view: Any) -> None:
    """Keep only the full cut surface at an explicitly independent 1:2 scale."""
    bound = _early_bound(view, "IView")
    bound.UseParentScale = False
    bound.UseSheetScale = 0
    bound.ScaleRatio = double_array(
        [float(SECTION_SCALE[0]), float(SECTION_SCALE[1])]
    )
    section = _early_bound(bound.GetSection(), "IDrSection")
    # R2026x declares SetDisplayOnlySurfaceCut as a void setter; only its
    # dedicated bool getter may be truth-tested.
    section.SetDisplayOnlySurfaceCut(True)
    rebuild_drawing(adapter, label="cone boss cut surface and independent scale")
    ratio = tuple(float(value) for value in bound.ScaleRatio)
    uses_parent = bool(bound.UseParentScale)
    uses_sheet = int(bound.UseSheetScale)
    if uses_parent or uses_sheet != 0 or not math.isclose(
        ratio[0] / ratio[1], SECTION_SCALE[0] / SECTION_SCALE[1]
    ):
        raise RuntimeError(
            "independent cone-section scale did not persist: "
            f"{ratio=}, {uses_parent=}, {uses_sheet=}"
        )
    if not bool(section.GetDisplayOnlySurfaceCut()):
        raise RuntimeError("cone boss section retained geometry beyond the cut")
    if bool(section.GetPartialSection()):
        raise RuntimeError("cone boss section cutting line did not close")


# ASME Y14.2 runs a centerline a short, uniform distance past the feature it
# marks; 3 mm clears the boss end faces without reaching the 42.0 witness lines.
_CENTERLINE_OVERSHOOT_MM = 3.0
_SW_LINE_CENTER = 4  # swLineStyles_e.swLineCENTER


def _add_cone_section_centerline(adapter: Any, view: Any) -> None:
    """Draw the cone-bore axis through Section A-A.

    The section is a surface-only cut, so it has no bore face to hand
    ``InsertCenterLine2``; without the axis a blind reader saw two unrelated
    hatched islands.  The endpoints are the model axis projected through the
    section's own transform into sheet space, so the line is the bore axis
    itself, and it runs a centerline overshoot past each boss end face.
    """
    incline = math.radians(INCLINE_DEG)
    reach = (CONE_BOSS_LENGTH / 2.0 + _CENTERLINE_OVERSHOOT_MM) / 1000.0
    centre = (0.0, BORE_HEIGHT / 1000.0, 0.0)
    ends = [
        model_point_in_view(
            adapter,
            view,
            (
                sign * reach * math.sin(incline),
                centre[1],
                sign * reach * math.cos(incline),
            ),
            label=f"cone section axis end {sign:+d}",
        )
        for sign in (-1, 1)
    ]
    middle = model_point_in_view(adapter, view, centre, label="cone section axis")
    outline = tuple(float(value) for value in _early_bound(view, "IView").GetOutline())
    if not (outline[0] < middle[0] < outline[2] and outline[1] < middle[1] < outline[3]):
        raise RuntimeError(
            f"cone section axis {middle!r} falls outside the section {outline!r}"
        )
    printed = math.dist(*ends) * 1000.0 / (SECTION_SCALE[0] / SECTION_SCALE[1])
    if abs(printed - 2.0 * reach * 1000.0) > 0.01:
        raise RuntimeError(
            f"cone section axis projects foreshortened: {printed:.4f} mm"
        )
    drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
    # EditSheet makes the line sheet-owned; the endpoints are already in sheet
    # space, so it stays coincident with the projected model axis.
    drawing.EditSheet()
    sketch_manager = _early_bound(adapter.currentModel.SketchManager, "ISketchManager")
    centerline = sketch_manager.CreateCenterLine(
        ends[0][0], ends[0][1], 0.0, ends[1][0], ends[1][1], 0.0
    )
    if centerline is None:
        raise RuntimeError("failed to create the cone-bore centerline in Section A-A")
    # A sheet sketch line otherwise prints in the under-defined sketch blue;
    # override the layer so it prints like every native centerline.
    segment = _early_bound(centerline, "ISketchSegment")
    segment.Color = 0  # COLORREF black
    segment.Style = _SW_LINE_CENTER
    adapter.currentModel.ClearSelection2(True)
    rebuild_drawing(adapter, label="cone section bore axis")
    if int(segment.Color) != 0 or int(segment.Style) != _SW_LINE_CENTER:
        raise RuntimeError(
            "cone-bore centerline did not keep black centerline font: "
            f"color={int(segment.Color)}, style={int(segment.Style)}"
        )
    _telemetry.info(
        f"cone section bore axis drawn {ends[0]!r} -> {ends[1]!r} through {middle!r}"
    )


def _configure_section_caption(drawing_model: Any) -> None:
    """Make the native section caption print its view-specific scale."""
    extension = _early_bound(drawing_model.Extension, "IModelDocExtension")
    # swDetailingSectionViewLabels_{PerStandard,Scale,CustomScale} =
    # 242/247/84 and swDetailingViewLabelsScale_SCALEcustom = 3 on R2026x.
    if not extension.SetUserPreferenceToggle(242, 0, False):
        raise RuntimeError("failed to release standard section-label defaults")
    if not extension.SetUserPreferenceInteger(247, 0, 3):
        raise RuntimeError("failed to select custom section-label scale text")
    if not extension.SetUserPreferenceString(84, 0, SECTION_LABEL_SCALE_TEXT):
        raise RuntimeError("failed to write section-label scale text")
    if (
        extension.GetUserPreferenceToggle(242, 0)
        or int(extension.GetUserPreferenceInteger(247, 0)) != 3
        or str(extension.GetUserPreferenceString(84, 0))
        != SECTION_LABEL_SCALE_TEXT
    ):
        raise RuntimeError("native section-label scale text did not persist")


def _show_section_scale_in_caption(adapter: Any, view: Any) -> None:
    """Retain the linked native caption fields and place them clear.

    The section is drawn at the sheet scale, so its caption states no scale:
    ASME Y14.3 asks for one only when a view differs from the title block.
    """
    candidates = []
    for raw_note in _early_bound(view, "IView").GetNotes() or ():
        note = _early_bound(raw_note, "INote")
        linked_text = str(note.PropertyLinkedText or "")
        if all(token in linked_text for token in ("<VLNAME>", "<VLLABEL>")):
            candidates.append(note)
    if len(candidates) != 1:
        raise RuntimeError(
            f"expected one native cone-section caption, found {len(candidates)}"
        )
    expected = "<VLNAME> <VLLABEL>"
    note = candidates[0]
    note.PropertyLinkedText = expected
    annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
    if not annotation.SetPosition2(*SECTION_CAPTION, 0.0):
        raise RuntimeError("failed to position native cone-section caption")
    rebuild_drawing(adapter, label="show and position cone-section caption")
    position = tuple(float(value) for value in annotation.GetPosition())
    if math.dist(position[:2], SECTION_CAPTION) > 1e-6:
        raise RuntimeError("native cone-section caption position did not persist")
    if str(note.PropertyLinkedText or "") != expected:
        raise RuntimeError("native cone-section scale caption did not persist")


def _outline_box(view: Any) -> Any:
    from _layout_geometry import Box

    values = tuple(float(value) for value in _early_bound(view, "IView").GetOutline())
    if len(values) != 4 or values[2] <= values[0] or values[3] <= values[1]:
        raise RuntimeError(f"view has an invalid outline {values!r}")
    return Box(*values)


def _note_box(note: Any) -> Any:
    from _layout_geometry import Box

    extent = tuple(float(value) for value in _early_bound(note, "INote").GetExtent())
    if len(extent) != 6:
        raise RuntimeError(f"note has an invalid extent {extent!r}")
    return Box(
        min(extent[0], extent[3]),
        min(extent[1], extent[4]),
        max(extent[0], extent[3]),
        max(extent[1], extent[4]),
    )


def _move_annotation(annotation: Any, delta: tuple[float, float], *, label: str) -> None:
    annotation = _early_bound(annotation, "IAnnotation")
    before = tuple(float(value) for value in annotation.GetPosition())
    target = (before[0] + delta[0], before[1] + delta[1])
    if not annotation.SetPosition2(target[0], target[1], 0.0):
        raise RuntimeError(f"{label}: SetPosition2 refused {target!r}")
    after = tuple(float(value) for value in annotation.GetPosition())
    if math.dist(after[:2], target) > 1e-6:
        raise RuntimeError(f"{label}: moved to {after[:2]!r}, expected {target!r}")


def _collect_sheet(adapter: Any, *, label: str) -> Any:
    """The one sheet, as the layout audit reads it; its full dump at info."""
    from diagnostics.drawing_layout_audit import collect_document, describe_sheet

    sheets = collect_document(adapter)
    if len(sheets) != 1:
        raise RuntimeError(f"cone pivot post must have one drawing sheet: {len(sheets)}")
    _telemetry.info(f"cone pivot post sheet at {label}:\n{describe_sheet(sheets[0])}")
    return sheets[0]


def _owned_annotations(sheet: Any, name: str, owner: str) -> list[Any]:
    """The annotations called ``name`` in view ``owner``.  A name alone is not
    an identity: SolidWorks names hole callouts per view, so the plan's RD1
    and the foot's dowel callout were both 'RD1' (leaf 917-s1-b5d9)."""
    return [a for a in sheet.annotations if a.label == name and a.owner == owner]


def _annotation_text_box(adapter: Any, name: str, owner: str) -> Any:
    """The union of the rendered text boxes of annotation ``name`` in view
    ``owner``, as the layout audit reads them."""
    from _layout_geometry import Box
    from diagnostics.drawing_layout_audit import collect_document

    boxes = [
        box
        for annotation in _owned_annotations(collect_document(adapter)[0], name, owner)
        for box in annotation.text_boxes
    ]
    if not boxes:
        raise RuntimeError(f"no rendered text read back for {owner}'s annotation {name!r}")
    return Box(
        min(box.xmin for box in boxes),
        min(box.ymin for box in boxes),
        max(box.xmax for box in boxes),
        max(box.ymax for box in boxes),
    )


def _hole_callout_shelf(annotation: Any, *, label: str) -> Any:
    """The callout's shelf as the audit reads it: the one horizontal leader
    run under its text."""
    shelves = [
        segment
        for segment in annotation.segments
        if segment.role == "leader" and abs(segment.y1 - segment.y0) < 1e-9
    ]
    if len(shelves) != 1:
        raise RuntimeError(
            f"{label}: expected one horizontal shelf, read "
            f"{[segment.format_mm() for segment in annotation.segments]}"
        )
    return shelves[0]


def _place_foot_group(adapter: Any, foot: Any) -> None:
    """Caption the foot view and call out one dowel ream, all three planned
    together from the sheet's read-back boxes.

    Runs after every other annotation on the sheet, so the plan reads them
    all.  The view shifts nearest-first on a 2 mm grid (its current spot
    first: a clear sheet never moves), the caption goes over or beside it,
    and the callout's text goes where the leader SolidWorks draws from the
    dowel rim crosses nothing (``_layout_planner.plan_view_group``)."""
    from _layout_geometry import Box
    from _layout_planner import HoleCallout, plan_view_group, sheet_obstacles

    gap = FOOT_LAYOUT_GAP
    rebuild_drawing(adapter, label="foot view outline")
    foot_name = str(_early_bound(foot, "IView").Name)
    obstacles = sheet_obstacles(
        _collect_sheet(adapter, label="foot view placement"), skip_views=(foot_name,)
    )
    foot_box = _outline_box(foot)
    note = add_note(adapter, FOOT_VIEW_NOTE, foot_box.xmin, foot_box.ymax)
    if note is None:
        raise RuntimeError("foot view caption was not created")
    caption = _note_box(note)

    # One named dowel, the one lower on the sheet: the pair differs only in
    # z, so an unnamed pick was whichever SolidWorks enumerated first.
    points = {
        (x, z): model_point_in_view(
            adapter, foot, (x / 1000.0, 0.0, z / 1000.0), label=f"foot dowel z {z:.3f}"
        )
        for x, z in POST_DOWEL_XZ
    }
    (dowel_x, dowel_z), dowel_xy = min(points.items(), key=lambda item: item[1][1])
    dowel_callout = add_native_hole_callout(
        adapter,
        foot,
        edge=_circular_edge(
            foot,
            radius_mm=POST_DOWEL_REAM_DIA / 2.0,
            center_y_mm=0.0,
            center_x_mm=dowel_x,
            center_z_mm=dowel_z,
        ),
        # Provisional: the plan below moves it once its real box is read.
        callout_xy=(foot_box.xmin - gap, dowel_xy[1]),
        label="post dowel reamed holes",
        process=FOOT_DOWEL_PREFIX,
    )
    set_hole_callout_precision(
        dowel_callout, {"hw-diam": 3, "hw-depth": 1}, label="post dowel ream"
    )
    rebuild_drawing(adapter, label="post dowel callout text")
    annotation = _early_bound(dowel_callout.GetAnnotation(), "IAnnotation")
    name = str(annotation.GetName())
    read = _owned_annotations(
        _collect_sheet(adapter, label="post dowel callout read-back"), name, foot_name
    )
    if len(read) != 1 or not read[0].text_boxes:
        raise RuntimeError(f"post dowel callout {name!r} was not read back: {read!r}")
    boxes = read[0].text_boxes
    text = Box(
        min(box.xmin for box in boxes),
        min(box.ymin for box in boxes),
        max(box.xmax for box in boxes),
        max(box.ymax for box in boxes),
    )
    scale = FOOT_SCALE[0] / FOOT_SCALE[1]
    plan = plan_view_group(
        foot_box,
        (caption.width, caption.height),
        obstacles,
        label="foot view",
        view_name=foot_name,
        callout=HoleCallout(
            label=name,
            owner=foot_name,
            text=text,
            shelf=_hole_callout_shelf(read[0], label="post dowel callout"),
            rim=(dowel_xy[0], dowel_xy[1], POST_DOWEL_REAM_DIA / 2000.0 * scale),
        ),
        gap=gap,
    )
    if plan.view_dx or plan.view_dy:
        bound = _early_bound(foot, "IView")
        position = tuple(float(value) for value in bound.Position)
        target = [position[0] + plan.view_dx, position[1] + plan.view_dy]
        if not bound.SetViewPosition(double_array(target), False):
            raise RuntimeError(f"foot view: SetViewPosition refused {target!r}")
        rebuild_drawing(adapter, label="foot view placed")
        foot_box = _outline_box(foot)
        if max(abs(foot_box.xmin - plan.view.xmin), abs(foot_box.ymax - plan.view.ymax)) > 0.0002:
            raise RuntimeError(
                f"foot view landed at {foot_box.format_mm()}, planned {plan.view.format_mm()}"
            )
    _move_annotation(
        _early_bound(note, "INote").GetAnnotation(),
        (plan.caption.xmin - caption.xmin, plan.caption.ymax - caption.ymax),
        label="foot caption",
    )
    # The callout belongs to the foot view and may have ridden with it: move
    # it from wherever it reads now to the planned text box.
    current = _annotation_text_box(adapter, name, foot_name)
    _move_annotation(
        annotation,
        (plan.callout_text.xmin - current.xmin, plan.callout_text.ymax - current.ymax),
        label="post dowel callout",
    )
    rebuild_drawing(adapter, label="foot view group placed")
    caption = _note_box(note)
    placed = _annotation_text_box(adapter, name, foot_name)
    for what, got, want in (
        ("foot caption", caption, plan.caption),
        ("post dowel callout", placed, plan.callout_text),
    ):
        if max(abs(got.xmin - want.xmin), abs(got.ymax - want.ymax)) > 0.0002:
            raise RuntimeError(f"{what} landed at {got.format_mm()}, planned {want.format_mm()}")
    _telemetry.info(
        f"foot view group placed from read-back boxes ({plan.how}): "
        f"foot {foot_box.format_mm()} (moved {plan.view_dx * 1000.0:.1f}, "
        f"{plan.view_dy * 1000.0:.1f} mm); caption {caption.format_mm()}; "
        f"dowel callout {name} {placed.format_mm()}, leader "
        + "; ".join(
            f"({s.x0 * 1000:.1f},{s.y0 * 1000:.1f})->({s.x1 * 1000:.1f},{s.y1 * 1000:.1f})"
            for s in plan.callout_leader
        )
        + f" from the dowel at ({dowel_xy[0] * 1000.0:.2f},{dowel_xy[1] * 1000.0:.2f}) mm before the move"
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
    sheet = _collect_sheet(adapter, label="final layout")

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
    own_overlaps = {}
    for label in ("JournalAxisY", "CrankAboveCone"):
        dimensions = [
            annotation for annotation in sheet.annotations if annotation.label == label
        ]
        if len(dimensions) != 1:
            raise RuntimeError(
                f"expected one visible native {label} annotation, found "
                f"{len(dimensions)}"
            )
        dimension = dimensions[0]
        text_interiors = [
            Box(
                box.xmin + DEFAULT_TEXT_TOUCH_TOL_M,
                box.ymin + DEFAULT_TEXT_TOUCH_TOL_M,
                box.xmax - DEFAULT_TEXT_TOUCH_TOL_M,
                box.ymax - DEFAULT_TEXT_TOUCH_TOL_M,
            )
            for box in dimension.text_boxes
        ]
        own_overlap = max(
            (
                segment_box_overlap_length(segment, box)
                for box in text_interiors
                for segment in dimension.segments
            ),
            default=0.0,
        )
        if own_overlap > DEFAULT_TEXT_TOUCH_TOL_M:
            raise RuntimeError(
                f"{label}'s own dimension ink crosses its text by "
                f"{own_overlap * 1000.0:.3f} mm"
            )
        own_overlaps[label] = round(own_overlap * 1000.0, 3)
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
        f"self-overlap mm={own_overlaps}"
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
    _configure_section_caption(drawing_model)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 1))
    foot = place_view(adapter, str(SOURCE), "*Bottom", *FOOT_CENTER, scale=FOOT_SCALE)
    section = create_section_view(
        adapter,
        front,
        line_start=CONE_SECTION_LINE[0],
        line_end=CONE_SECTION_LINE[1],
        view_xy=SECTION_CENTER,
        section_label="A",
        scale=SECTION_SCALE,
        label="cone boss bore-plane profile",
    )
    _prepare_cone_section(adapter, section)
    # The named journal view looks exactly down the inclined model axis.  Unlike
    # the bore-plane section, it retains the uncut boss end face, so its Ø17.2
    # OD and Ø12.281 bore are two visible concentric circles with clear leaders.
    for view in (front, top, journal, section, foot):
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
        view_label="cone boss bore-plane section",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    annotations = [
        *front_annotations,
        *top_annotations,
        *journal_annotations,
        *section_annotations,
    ]
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    crank_height = [
        annotation
        for annotation in front_annotations
        if dimension_name(adapter, annotation) == "CrankAxisY"
    ]
    if len(crank_height) != 1:
        raise RuntimeError(
            f"expected one CrankAxisY in the front view, found {len(crank_height)}"
        )
    set_reference_dimension(
        adapter, crank_height[0], label="crank axis height reference"
    )
    # The part authored these places (cone_pivot_post_spec.DRAWING_PRECISION);
    # this sheet only proves they survived the import.  A silent fallback to
    # the drawing document's two places would print the running bores without
    # the third place their fit band is written in.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)

    offset_dimension_text(
        adapter,
        journal_annotations,
        {"JournalAxisY": (0.190, 0.157), "CrankAboveCone": (0.193, 0.183)},
    )
    # The plan must retain JournalPlanReference: its two native centreline rays
    # and imported dimensions carry the spotface station and 12.52-degree bore
    # azimuth.  Other projections have no use for that witness geometry.
    for view in (front, journal, iso):
        _hide_witness_sketch(adapter, view, "JournalPlanReference")
    # The cone-axis view keeps BoreSpacingReference: its centreline joins the
    # two bore centres and carries the spacing.  Elsewhere it only doubles the
    # post axis.
    for view in (front, top, iso):
        _hide_witness_sketch(adapter, view, "BoreSpacingReference")
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
    _add_cone_section_centerline(adapter, section)
    add_attached_note(
        adapter,
        front,
        text="VIEW B",
        entity=_bore_rim_edge(front, diameter_mm=BORE_DIA),
        note_xy=(0.165, 0.112),
        label="cone-axis auxiliary-view direction",
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
        symbol_xy=(0.055, 0.165),
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
        "VIEW B - CONE JOURNAL\nLOOK ALONG CONE AXIS",
        0.202,
        0.104,
    )
    # Rule 6 caps the block at four lines (about 18 mm); the anchor keeps the
    # r7 clearance to the bottom inner border.
    add_property_linked_note(adapter, "Manufacturing Notes", 0.014, 0.0555)

    # #917 S1: the blind dowel reams.  Size, band and depth stay native (the
    # depth at the part's .X); the prefix names the mating platform and the
    # reamer.  Last, so the plan reads every other box on the sheet.
    _place_foot_group(adapter, foot)
    if not auto_center_marks(adapter, foot, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to the foot view")

    # Attaching dimensions and symbols can leave a stale hidden-line display.
    # Reassert each manufacturing view after its final annotation.
    set_hidden_lines_removed(adapter, front)
    set_hidden_lines_removed(adapter, top)
    set_hidden_lines_removed(adapter, journal)
    set_hidden_lines_removed(adapter, section)
    set_hidden_lines_removed(adapter, foot)
    rebuild_drawing(adapter, label="final cone pivot post native layout")
    _show_section_scale_in_caption(adapter, section)
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
