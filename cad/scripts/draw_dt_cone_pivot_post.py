r"""Create the curated machinist drawing for the v2 cone pivot post.

The SLDPRT remains authoritative.  This recipe places the plan, the front
elevation, a true-shape cone-journal view, a native section through the cone
bore plane and a pictorial isometric on one sheet, and imports exactly the
model dimensions ``cone_pivot_post_spec.DRAWING_DIMENSIONS`` marks; shared
sheet/template, import, curation and export behaviour lives in
``_drawing_common``.

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

    uv run python cad\scripts\draw_dt_cone_pivot_post.py dt-cone-pivot-post
"""

from __future__ import annotations

import argparse
import math
import sys
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

import _seat_forensics
import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from solidworks_mcp.adapters.com_variant import double_array
from _drawing_common import (
    DrawingOutputs,
    PmiDrawingPlacement,
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
    project_part_pmi,
    read_required_properties,
    rebuild_drawing,
    set_basic_dimensions,
    set_dimension_callouts,
    set_hidden_lines_removed,
    set_reference_dimension,
    set_high_quality_shaded_with_edges,
    stamp_drawing_summary,
    visible_view_entities,
)
from _drawing_hidden_sketches import (
    curate_view_dimensions as curate_hidden_owner_dimensions,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _surface_finish import surface_finish_by_key
from dt_cone_gear_shaft_spec import POST_JOURNAL_RIM_BREAK
from dt_cone_pivot_post_spec import (
    ATTACHMENT_CBORE_DIA,
    ATTACHMENT_X,
    BASIC_DIMENSIONS,
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
    GEOMETRIC_CONTROLS,
    INCLINE_DEG,
    PART_DATUMS,
    SURFACE_FINISHES,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["dt_cone_pivot_post"]
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

# The landscape template's FINISH rules print at x=215.900/308.328 mm and
# y=33.584/44.485 mm (sheet origin at lower left).  Round inward rather than
# granting a PDF-coordinate rounding tolerance outside the cell.  The old
# x=218 mm limit rejected the correctly contained note starting at 217.8 mm.
# Keep all four boundaries checked so wrapping cannot spill into MATERIAL.
_FINISH_CELL = (0.21595, 0.03360, 0.30830, 0.04445)

# ``place_view`` centres a view on its projected bounding box, so the model
# origin is offset from the view centre by half that box.  The elevation's box
# runs y=0..BLOCK_HEIGHT; the plan's runs the crank boss's full z extent.
_TOP_Z_CENTER = (CRANK_BOSS_START_Z + CRANK_BOSS_END_Z) / 2.0


def _front_y(model_y: float) -> float:
    return FRONT_CENTER[1] + (model_y - BLOCK_HEIGHT / 2.0) * _S


def _front_x(model_x: float) -> float:
    return FRONT_CENTER[0] + model_x * _S


# The manufacturing notes hang from their top-left anchor and grow down.
NOTES_ANCHOR = (0.014, 0.0555)
# Datum B tags the foot seat below the elevation, and its frame hangs 7.0 mm
# down from the tag point (measured on leaf w3-1026: point at 60.0 mm, frame
# 53.0..60.0).  At model y -9 the frame sat on the notes' first line; the tag
# point now sits a frame height plus clearance above the notes' top, still
# below the foot (model y 0) so the leader reaches the seat.
_DATUM_TAG_FRAME_HEIGHT = 0.007
_DATUM_NOTES_CLEARANCE = 0.0015
DATUM_B_TAG_XY = (
    _front_x(-16.0),
    NOTES_ANCHOR[1] + _DATUM_TAG_FRAME_HEIGHT + _DATUM_NOTES_CLEARANCE,
)
if not DATUM_B_TAG_XY[1] < _front_y(0.0):
    raise AssertionError("datum B's tag no longer sits below the foot seat it tags")


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
    # Out past the angularity frame, text above it: at x=0.150 its extension
    # lines fenced the frame off the crank bore (leader-crosses-line, af13).
    "HeadHt": (0.164, 0.1475),
    "CrankBossDia": (0.132, 0.120),
    # Held 10 mm clear of View B's toleranced crank-above-cone text: at
    # x=0.155 the two sat 4.15 mm apart, under one text height (r7 audit).
    "CrankBoreDia": (0.149, 0.172),
}
# The plan's hidden-owner import shows JournalPlanReference's rays for the
# plan angle and CrankBossStationReference's ray for the crank boss's
# north-face station, the face the crank boss length is taken from.
TOP_KEEP = {
    "HeadDia": (0.071, 0.188),
    # The length stands outboard of the station so the station's stacked
    # label clears its dimension line: with the v36 boss face 2.5 further
    # north, a one-line label spanning both lines was crossed by the length.
    "CrankBossLen": (0.040, TOP_CENTER[1]),
    # The station stands between the crank-boss length and the circle, its
    # value on its own dimension line.  On the right its upper witness line
    # ran level with the counterbore callout's shelf and that callout's
    # leader crossed its dimension line, so its text had to be offset to a
    # distant shelf, where a blind reader took it for a note.
    "CrankBossStartZ": (0.062, 0.2338),
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
# Both chained heights share the dimension line at JOURNAL_KEEP's x, and the
# crank spacing's extension line runs up it past the 33.37's text, so that text
# must end left of the line.  Its x here is only a start:
# ``_clear_journal_axis_text`` moves it by the box the layout check itself
# reads once the sheet is complete.  That box is an estimate (glyph count x
# height x an advance calibrated from the sheet's notes), so it outruns the
# printed ink and moves when any note on the sheet changes: leaf w3-1026 read
# it 34.0 mm wide, the 8f4aea333 control 36.0 mm over 27.1 mm of printed ink.
# A width fixed from one reading crossed the line on the next.
_TEXT_LINE_CLEARANCE = 0.002
JOURNAL_TEXT_OFFSETS = {
    "JournalAxisY": (0.1856, 0.157),
    "CrankAboveCone": (0.193, 0.183),
}
# The non-preferred bore limits tell the shop what to inspect without imposing
# a particular cutting method.  Ø21.93 is the crank boss OD -- the elevation
# looks at the boss's far end, so it is labelled as the boss -- and the plan's
# station locates the boss's north face from the post axis; that face stands
# on the head's tangent plane, so no depth is taken against the curved head.
# The station is labelled: Main's rim-8339 ruling found the spot-face era's
# bare 18.88 station was not read as one.
# The cone bore's rims bound the thrust ring the shaft collar bears on, with
# the collar's OD edge (cone_gear_shaft_spec: ring - 2 x break >= 1.5), so the
# bore's callout prints the same break as the collar instead of the title
# block's 0.25.
DIMENSION_CALLOUTS = {
    "HeadDia": "HEAD",
    "CrankBossDia": "CRANK BOSS",
    "CrankBossLen": "CRANK BOSS\nLENGTH",
    "CrankBossStartZ": "CRANK BOSS\nFACE",
    "CrankBoreDia": "CRANK BORE THRU",
    "JournalBoreDia": f"CONE BORE THRU\n{POST_JOURNAL_RIM_BREAK}",
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


# The collar's Ra symbol sits up and left of its leader's landing point, clear
# of the face-to-face dimension on the section's right (sheet metres).
_NORTH_BOSS_FINISH_OFFSET = (-0.018, 0.006)


def _north_boss_end_edge(section: Any) -> Any:
    """Return the sheet-left cut edge of the north cone-boss end face.

    The A-A cut runs through the journal axis, so the north end face shows as
    two short edges split by the bore.  Both vertices of each must lie on the
    controlled plane at the bore height; finding exactly two proves the scan
    found the boss end and not some other plane.
    """
    normal = surface_finish_by_key(SURFACE_FINISHES, "cone_boss_north_face").face.normal
    offset = CONE_BOSS_LENGTH / 2.0
    candidates: list[tuple[float, Any]] = []
    for raw in visible_view_entities(section, 1, label="north cone boss end edges"):
        edge = _early_bound(raw, "IEdge")
        start, end = edge.GetStartVertex(), edge.GetEndVertex()
        if start is None or end is None:
            continue
        points = [
            tuple(float(v) * 1000.0 for v in _early_bound(vertex, "IVertex").GetPoint())
            for vertex in (start, end)
        ]
        if all(
            abs(sum(p[i] * normal[i] for i in range(3)) - offset)
            <= _EDGE_MATCH_TOLERANCE_MM
            and abs(p[1] - BORE_HEIGHT) <= _EDGE_MATCH_TOLERANCE_MM
            for p in points
        ):
            candidates.append((0.5 * (points[0][0] + points[1][0]), edge))
    if len(candidates) != 2:
        raise RuntimeError(
            f"section shows {len(candidates)} north cone boss end edges, expected two"
        )
    return min(candidates, key=lambda item: item[0])[1]


def _north_boss_finish_anchor(
    adapter: Any, section: Any, edge: Any
) -> tuple[float, float]:
    """Sheet point mid-way along the edge, proven to be the section's top left."""
    points = [
        tuple(float(v) for v in _early_bound(vertex, "IVertex").GetPoint())
        for vertex in (edge.GetStartVertex(), edge.GetEndVertex())
    ]
    middle = tuple(0.5 * (points[0][i] + points[1][i]) for i in range(3))
    anchor = model_point_in_view(adapter, section, middle, label="north boss end midpoint")
    centre = model_point_in_view(
        adapter, section, (0.0, BORE_HEIGHT / 1000.0, 0.0), label="cone section centre"
    )
    if not (anchor[0] < centre[0] and anchor[1] > centre[1]):
        raise RuntimeError(
            f"north cone boss end {anchor!r} is not up-left of the section "
            f"centre {centre!r}; the symbol offset assumes it is"
        )
    return (anchor[0], anchor[1])







def _model_face_evidence(
    model: Any,
) -> dict[str, list[tuple[str, tuple[float, ...]]]]:
    """Read the final BREP surfaces behind the four disputed callouts."""
    rows: dict[str, list[tuple[str, tuple[float, ...]]]] = {}
    part = _early_bound(model, "IPartDoc")
    for name in (
        "CrankSprocketBoss",
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


def _plane_centres(
    face_evidence: dict[str, list[tuple[str, tuple[float, ...]]]],
    feature_name: str,
    count: int,
) -> list[tuple[float, float, float]]:
    """A feature's plane root points (model metres)."""
    centres = [
        (values[3], values[4], values[5])
        for kind, values in face_evidence[feature_name]
        if kind == "plane"
    ]
    if len(centres) != count:
        raise RuntimeError(
            f"{feature_name} has {len(centres)} BREP face centres, expected {count}"
        )
    return centres


def _crank_face_centres(
    face_evidence: dict[str, list[tuple[str, tuple[float, ...]]]],
) -> list[tuple[float, float, float]]:
    """The crank boss's north (head-tangent) face and far face, in that order.

    CrankSprocketBoss owns exactly two planes (faces on one surface are listed
    once, so the head's tangent line cannot split the count), and each stands
    at its printed station.
    """
    near, far = sorted(
        _plane_centres(face_evidence, "CrankSprocketBoss", 2), key=lambda p: p[2]
    )
    for label, centre, station in (
        ("north", near, CRANK_BOSS_START_Z),
        ("far", far, CRANK_BOSS_END_Z),
    ):
        if abs(centre[2] * 1000.0 - station) > 1e-3:
            raise RuntimeError(
                f"crank boss {label} face at z={centre[2] * 1000.0:.4f} mm, "
                f"expected {station:.4f}"
            )
    return [near, far]


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
    crank_face_centres = _crank_face_centres(face_evidence)
    cone_face_centres = sorted(
        _plane_centres(face_evidence, "ConeShaftBoss", 2),
        key=lambda point: sum(point[i] * cone_axis[i] for i in range(3)),
    )
    iso_face_centres = {
        "crank_north_face": model_point_in_view(
            adapter,
            iso,
            crank_face_centres[0],
            label="isometric crank north-face centre",
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
        iso_face_centres["crank_north_face"][1],
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


def _view_outline(view: Any) -> tuple[float, float, float, float]:
    outline = tuple(float(value) for value in _early_bound(view, "IView").GetOutline())
    if len(outline) != 4:
        raise RuntimeError(f"view has an invalid outline: {outline!r}")
    return outline


def journal_axis_text_shift(sheet: Any) -> tuple[Any, float, float]:
    """The 33.37 text box the layout check reads, the crank spacing line
    beside it, and the x shift that leaves the box ``_TEXT_LINE_CLEARANCE``
    left of that line (negative moves it left)."""
    from _layout_geometry import union_boxes

    texts = [a for a in sheet.annotations if a.label == "JournalAxisY"]
    if len(texts) != 1:
        raise RuntimeError(
            f"expected one JournalAxisY on the sheet, found {len(texts)}"
        )
    box = union_boxes(list(texts[0].text_boxes))
    if box is None:
        raise RuntimeError("JournalAxisY has no text box to place")
    spacings = [a for a in sheet.annotations if a.label == "CrankAboveCone"]
    if len(spacings) != 1:
        raise RuntimeError(
            f"expected one CrankAboveCone on the sheet, found {len(spacings)}"
        )
    beside = [
        segment.x0
        for segment in spacings[0].segments
        if abs(segment.x1 - segment.x0) < 1e-9
        and segment.x0 > box.xmin
        and min(segment.y0, segment.y1) < box.ymax
        and max(segment.y0, segment.y1) > box.ymin
    ]
    if not beside:
        raise RuntimeError(
            "no vertical CrankAboveCone line beside the JournalAxisY text "
            f"{box.format_mm()}: the 33.37 placement premise no longer holds"
        )
    line_x = min(beside)
    return box, line_x, line_x - _TEXT_LINE_CLEARANCE - box.xmax


def _clear_journal_axis_text(adapter: Any, journal_annotations: list[Any]) -> None:
    """Move the 33.37 text so the box the layout check reads on this finished
    sheet ends ``_TEXT_LINE_CLEARANCE`` left of the crank spacing line."""
    from diagnostics.drawing_layout_audit import collect_document

    sheets = collect_document(adapter)
    if len(sheets) != 1:
        raise RuntimeError(
            f"cone pivot post must have one drawing sheet: {len(sheets)}"
        )
    box, line_x, shift = journal_axis_text_shift(sheets[0])
    dimensions = [
        annotation
        for annotation in journal_annotations
        if dimension_name(adapter, annotation) == "JournalAxisY"
    ]
    if len(dimensions) != 1:
        raise RuntimeError(
            f"expected one JournalAxisY in the cone journal view, found {len(dimensions)}"
        )
    annotation = _early_bound(dimensions[0], "IAnnotation")
    position = tuple(float(value) for value in annotation.GetPosition())
    if len(position) < 2:
        raise RuntimeError(f"JournalAxisY text has no position: {position!r}")
    if not annotation.SetPosition2(position[0] + shift, position[1], 0.0):
        raise RuntimeError("failed to move the JournalAxisY text clear of its line")
    rebuild_drawing(adapter, label="clear the 33.37 text of the crank spacing line")
    _telemetry.info(
        f"JournalAxisY text box {box.format_mm()} vs line x={line_x * 1000.0:.2f} mm: "
        f"moved text {shift * 1000.0:+.2f} mm from x={position[0] * 1000.0:.2f} mm"
    )


def _pin_sheet_scale(adapter: Any) -> None:
    """Re-pin the sheet's scale before the native gate reads (or its failure
    PDF prints) the title block.

    Inserting a model view drifts the sheet scale; ``finalize_drawing``
    re-pins it before export, but the native gate and its evidence PDF come
    first, and rim-8339's evidence printed "SCALE: 1:2" on a 1:1 sheet.
    """
    ddoc = _early_bound(adapter.currentModel, "IDrawingDoc")
    sheet = _early_bound(ddoc.GetCurrentSheet(), "ISheet")
    numerator, denominator = SHEET_SCALE
    if not sheet.SetScale(float(numerator), float(denominator), False, False):
        raise RuntimeError(f"failed to pin the sheet at {numerator:g}:{denominator:g}")


def _assert_native_layout_with_evidence(
    adapter: Any,
    journal: Any,
    *,
    expected_finish: str,
) -> None:
    """The native layout gate, leaving the failing sheet as a PDF.  The
    evidence never masks the failure: the gate's own error is re-raised
    whatever the export does."""
    try:
        _assert_native_layout(adapter, journal, expected_finish=expected_finish)
    except RuntimeError:
        try:
            _export_failure_pdf(adapter, "native-layout")
        except Exception as exc:  # noqa: BLE001 - evidence must not mask the failure
            _telemetry.warn(f"native-layout failure PDF raised: {exc!r}")
        raise


def _export_failure_pdf(adapter: Any, stage: str) -> None:
    """Export the failing sheet under the forensic tree the farm uploads."""
    try:
        folder = (
            _seat_forensics.OUT_FAILURES
            / f"dt-cone-pivot-post-{stage}"
            / datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        )
        folder.mkdir(parents=True, exist_ok=True)
        model = _early_bound(adapter.currentModel, "IModelDoc2")
        path = folder / "dt-cone-pivot-post.pdf"
        model.SaveAs3(str(path), 0, 0)
        paths = [path]
    except Exception as exc:  # noqa: BLE001 - evidence must not mask the failure
        _telemetry.warn(f"{stage}-failure PDF export failed: {exc!r}")
        return
    for path in paths:
        if not path.is_file():
            _telemetry.warn(f"{stage}-failure PDF export produced no file: {path}")
            continue
        _telemetry.event("drawing.failure_pdf", stage=stage, path=str(path))
        _telemetry.info(f"{stage}-failure evidence PDF: {path}")


def view_placement_problems(
    outlines: Mapping[str, tuple[float, float, float, float]],
    region: Any,
    keep_outs: tuple[tuple[str, Any], ...],
) -> list[str]:
    """Views that leave the inner border or reach into a keep-out (the
    title block).  The text audit reads annotations, not view outlines."""
    from _layout_geometry import DEFAULT_TEXT_TOUCH_TOL_M, Box

    problems = []
    for label, outline in outlines.items():
        box = Box(*outline)
        escape = box.escape(region)
        if escape is not None:
            problems.append(f"{label} leaves the inner border: {box.format_mm()}, {escape=}")
        for keep_out_name, keep_out in keep_outs:
            if box.overlaps(keep_out, tol=DEFAULT_TEXT_TOUCH_TOL_M) is not None:
                problems.append(
                    f"{label} reaches into the {keep_out_name}: "
                    f"{box.format_mm()} vs {keep_out.format_mm()}"
                )
    return problems


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

    journal_box = Box(*_view_outline(journal))
    placement = view_placement_problems(
        {"cone journal view": _view_outline(journal)}, sheet.region, ()
    )
    if placement:
        raise RuntimeError("cone pivot post view placement failed:\n" + "\n".join(placement))
    # Hiding a sketch in a view hides the dimensions imported from it
    # (rim-aba9 lost the crank boss station that way), so the plan's two
    # hidden-owner dimensions must each still print, once.
    labels = [annotation.label for annotation in sheet.annotations]
    missing = [
        name for name in ("CrankBossStartZ", "InclineAngle") if labels.count(name) != 1
    ]
    if missing:
        raise RuntimeError(f"the plan must print each of {missing} once: {sorted(labels)}")

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
    if len(surface_boxes) != len(SURFACE_FINISHES):
        raise RuntimeError(
            f"cone pivot post must expose {len(SURFACE_FINISHES)} native Ra "
            f"text boxes: {len(surface_boxes)}"
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
    axis_box, line_x, shift = journal_axis_text_shift(sheet)
    if shift < -1e-4:
        raise RuntimeError(
            f"JournalAxisY text {axis_box.format_mm()} ends "
            f"{(line_x - axis_box.xmax) * 1000.0:.2f} mm left of the crank spacing "
            f"line at x={line_x * 1000.0:.2f} mm; it must clear it by "
            f"{_TEXT_LINE_CLEARANCE * 1000.0:.2f} mm"
        )
    _telemetry.info(
        "cone pivot post native layout: "
        f"journal={journal_box.format_mm()}; "
        f"finish={finish_box.format_mm()} in {finish_cell.format_mm()}; "
        f"Ra={[box.format_mm() for box in surface_boxes]}; "
        f"self-overlap mm={own_overlaps}; "
        f"JournalAxisY text={axis_box.format_mm()} clears x={line_x * 1000.0:.2f} "
        f"by {(line_x - axis_box.xmax) * 1000.0:.2f} mm"
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
    # The part saves its reference sketches hidden.  The plan dimensions the
    # plan angle and the crank boss station and View B the bore spacing, so
    # each shows its owning sketch (JournalPlanReference's two rays,
    # CrankBossStationReference's ray, BoreSpacingReference's centreline
    # joining the bores) in that view only; no other view shows any of them.
    top_annotations = curate_hidden_owner_dimensions(
        adapter,
        top,
        keep=TOP_KEEP,
        view_label="top",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    journal_annotations = curate_hidden_owner_dimensions(
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
    # #906: the plan angle feeds the crank bore's angularity frame (rule 4).
    set_basic_dimensions(adapter, annotations, BASIC_DIMENSIONS)
    # The part authored these places (cone_pivot_post_spec.DRAWING_PRECISION);
    # this sheet only proves they survived the import.  A silent fallback to
    # the drawing document's two places would print the running bores without
    # the third place their fit band is written in.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)

    offset_dimension_text(
        adapter,
        journal_annotations,
        JOURNAL_TEXT_OFFSETS,
    )
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
    # The note's arrow lands on the journal rim's upper-right quarter (35
    # degrees), above the A-A line, so it reaches the rim from the right
    # without crossing that line (leader-crosses-section-line, af13): the
    # native entity's default landing sat below it, on the lower-left.  The
    # rim is the pad end-face circle seen along Z, centred L/2*sin(incline)
    # right of the axis and foreshortened by cos(incline) across; the audit
    # read the old landing within 0.1 mm of this ellipse.  The pick only sets
    # the landing: the note must still attach to the identified bore rim.
    view_b_t = math.radians(35.0)
    view_b_incline = math.radians(INCLINE_DEG)
    add_attached_note(
        adapter,
        front,
        text="VIEW B",
        entity_xy=(
            _front_x(
                CONE_BOSS_LENGTH / 2.0 * math.sin(view_b_incline)
                + BORE_DIA / 2.0 * math.cos(view_b_t) * math.cos(view_b_incline)
            ),
            _front_y(BORE_HEIGHT + BORE_DIA / 2.0 * math.sin(view_b_t)),
        ),
        note_xy=(0.1265, 0.1087),
        label="cone-axis auxiliary-view direction",
        attached_to=_bore_rim_edge(front, diameter_mm=BORE_DIA),
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
    # The crank-bore Ra stands left of the head, between the (72.70)'s witness
    # and the 86.0's top witness: above the view its leader crossed the 86.0's
    # top witness (leader-crosses-line, ha-perf-parts audit).
    add_surface_finish(
        adapter,
        front,
        edge_entity=_bore_rim_edge(front, diameter_mm=CRANK_BORE_DIA),
        symbol_xy=(0.050, 0.1447),
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
    # The shaft collar's thrust face (#914).  Every other view sees it hidden
    # behind the body, so it is called out on its A-A cut edge.
    north_edge = _north_boss_end_edge(section)
    north_anchor = _north_boss_finish_anchor(adapter, section, north_edge)
    add_surface_finish(
        adapter,
        section,
        symbol_xy=(
            north_anchor[0] + _NORTH_BOSS_FINISH_OFFSET[0],
            north_anchor[1] + _NORTH_BOSS_FINISH_OFFSET[1],
        ),
        control=surface_finish_by_key(SURFACE_FINISHES, "cone_boss_north_face"),
        label="north cone boss end finish",
        char_height=0.0025,
        entity=north_edge,
        leader_attach_xy=north_anchor,
    )
    # #906 (USER RULING 2026-09-26): the crank bore's angularity to the cone
    # journal, model PMI (cone_pivot_post_spec.PART_DATUMS /
    # GEOMETRIC_CONTROLS) projected here.  Datum A tags the journal bore in
    # View B, the only view that shows it true; datum B tags the foot seat
    # edge-on in the elevation, left of the body and clear of the foot-seat
    # finish on the right; the frame hangs off the crank bore rim in the
    # elevation, right of the body and below the bore callout.
    project_part_pmi(
        adapter,
        placements={
            "datum:A": PmiDrawingPlacement(
                view=journal,
                position=(0.250, 0.128),
                edge_entity=_bore_rim_edge(journal, diameter_mm=BORE_DIA),
            ),
            "datum:B": PmiDrawingPlacement(
                view=front,
                position=DATUM_B_TAG_XY,
                edge_entity=_circular_edge(
                    front, radius_mm=BLOCK_DIA / 2.0, center_y_mm=0.0
                ),
            ),
            # The frame sits right of the head between HeadHt's extension
            # lines, its leader landing on the bore rim at -28 degrees,
            # between the CRANK BOSS diameter line and the centre-mark arm:
            # from (0.160, 0.128) to the natural lower-left landing it
            # crossed HeadHt's and CrankBossDia's lines (leader-crosses-line,
            # af13).  A sheet-point pick sets the landing; explicit leader
            # placement detached a GTol from its edge (fulcrum 1149f227f).
            "crank_bore_angularity": PmiDrawingPlacement(
                view=front,
                position=(0.124, 0.138),
                attachment_xy=(
                    _front_x(CRANK_BORE_DIA / 2.0 * math.cos(math.radians(-28.0))),
                    _front_y(
                        CRANK_BORE_HEIGHT
                        + CRANK_BORE_DIA / 2.0 * math.sin(math.radians(-28.0))
                    ),
                ),
            ),
        },
        datums=PART_DATUMS,
        controls=GEOMETRIC_CONTROLS,
        label="cone pivot post PMI",
    )
    add_note(
        adapter,
        "VIEW B - CONE JOURNAL\nLOOK ALONG CONE AXIS",
        0.202,
        0.104,
    )
    # Rule 6 caps the block at four lines (about 18 mm); the anchor keeps the
    # r7 clearance to the bottom inner border.
    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_ANCHOR)

    # Attaching dimensions and symbols can leave a stale hidden-line display.
    # Reassert each manufacturing view after its final annotation.
    set_hidden_lines_removed(adapter, front)
    set_hidden_lines_removed(adapter, top)
    set_hidden_lines_removed(adapter, journal)
    set_hidden_lines_removed(adapter, section)
    _pin_sheet_scale(adapter)
    rebuild_drawing(adapter, label="final cone pivot post native layout")
    _show_section_scale_in_caption(adapter, section)
    _clear_journal_axis_text(adapter, journal_annotations)
    _assert_native_layout_with_evidence(
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
