r"""Create the curated machinist drawing for the rocker-arm support.

The SLDPRT remains authoritative.  This recipe supplies only the support's
views, dimension layout, hole table, and make-critical annotations; every
shared sheet/template, import, curation, and export behavior lives in
``_drawing_common``.

The support is a painted gray-iron frame with a trapezoidal wall, two opposed
pockets leaving a central web, a through cavity, a chamfered window rim,
four 5/16 clearance holes through its mounting foot, and a 22.7-deep top rail
carrying the rocker brackets' four #8-32 seats (#743), transferred from the set
brackets at assembly. The sheet runs 1:2, with each view's scale pinned
explicitly.

Run with SolidWorks open::

    uv run python cad\scripts\draw_rocker_arm_support.py rocker-arm-support
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any


import _config
import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_edge_dimension,
    add_leader_note,
    add_native_hole_callout,
    add_surface_finish,
    create_section_view,
    create_view_theoretical_datum,
    curate_view_dimensions,
    finalize_drawing,
    import_cosmetic_threads,
    insert_hole_table,
    model_point_in_view,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    set_dimension_callouts,
    set_dimension_precision,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    stamp_drawing_summary,
    view_name,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _gtol_spec import CylinderFace
from _hole_spec import blind_cut_dia_mm
from _part_pmi import _resolve_faces
from _surface_finish import surface_finish_by_key
from build_rocker_arm_support import (
    BIG,
    BOSS_DEPTH,
    CAV,
    CHAMFER,
    DRAWING_DIMENSIONS,
    HALF_Y,
    HOLES,
    HOLE_DIA,
    NARROW,
    WEB,
    WIDE,
)
from rocker_arm_support_drawing_spec import SURFACE_FINISHES
from rocker_bracket_seat_layout import (
    RAIL_DEPTH,
    SEAT_LOCAL_X,
    SEAT_SPEC,
    WINDOW_TOP_Y,
)
from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["rocker_arm_support"]
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

SHEET_SCALE = (1.0, 2.0)

# Sheet layout (meters). A 177.8 mm casting with four views needs a 1:2 ASME B
# sheet. Section A-A replaces the side view, exposing the opposed pocket floors
# and web; the clearance-hole setup stays aligned below the front. The front
# shifts left of the section, and the bottom view drops to open an exterior
# annotation lane below the front without breaking the projected group.
VIEW_SCALE = SHEET_SCALE[0] / SHEET_SCALE[1]
FRONT_CENTER = (0.105, 0.185)
RIGHT_CENTER = (0.205, 0.185)
BOTTOM_CENTER = (0.105, 0.075)
ISO_CENTER = (0.350, 0.201)

# Per-view survivors of the marked-dimension import: parametric name -> sheet
# position (meters). Every front-view callout is outside the part silhouette:
# overall size above, nested pocket sizes below, radii beside their corners.
FRONT_KEEP = {
    "Depth": (0.105, 0.258),
    "PocketRadius": (0.035, 0.150),
    # CornerFillet's dimension belongs to the cavity's top-right corner (the
    # fix3 render), so the text sits up-right of that corner, on the arc's
    # own bisector. From the left column its leader crossed the whole cavity
    # and landed on the far side of the fillet's circle, off the arc.
    "CavityRadius": (0.160, 0.240),
    # Each stacked width prints its text just above its own dimension line,
    # so the lower one needs a full band: at 0.118 the 127.0 line ran
    # through "165.1" (fix3 render).
    "WinWidth": (0.105, 0.110),
    "CavWidth": (0.105, 0.128),
}
# The cavity corner CornerFillet's dimension attaches to, as sheet signs.
CAVITY_RADIUS_CORNER = (1, 1)
DIMENSION_CALLOUTS = {
    "PocketRadius": "8X",
    "CavityRadius": "4X",
    "WinWidth": " POCKET",
    "CavWidth": "SQ CAVITY THRU",
    "RimChamferSize": " X 45 DEG\n2 FACES",
}
DIMENSION_PRECISION = {
    "Depth": 1,
    "WinWidth": 1,
    "CavWidth": 1,
    "PocketRadius": 2,
    "CavityRadius": 1,
    "WallHeight": 1,
    "FootSpan": 1,
    "TopSpan": 1,
    "RimChamferSize": 2,
    "WebThickness": 2,  # a held thickness: 6.35, routine ±0.51
    "FootThickness": 2,
    "RailDepth": 1,  # the seats' drill point needs the .X band (seat layout)
}


def imported_precision() -> dict[str, int]:
    """Precision for the imported model dimensions only. The sheet-made ones
    (web, foot, rail depth) set their own when they are created, after the
    import; set_dimension_precision fails on a name it cannot find, which
    is how the #743 rail's RailDepth entry broke r743-rocker-fix."""
    kept = set(FRONT_KEEP) | set(RIGHT_KEEP)
    return {
        name: digits for name, digits in DIMENSION_PRECISION.items() if name in kept
    }


# The bracket seats print as ONE native Hole Wizard callout (Codex #936,
# PRRT_kwDOPHDy386mRSOJ): SolidWorks reads the count, thread and both depths
# from BracketSeats, so a model change moves the print. Only the transfer
# instruction is text, and its closing line break puts the native size on a
# row of its own (13be2ca03).
SEAT_CALLOUT_PROCESS = (
    f"TRANSFER FROM {_config.parts('pivot-bracket')['number']}\nAT ASSEMBLY;\n"
)
SEAT_CALLOUT_X_MM = max(SEAT_LOCAL_X)
# The seats are drilled from the rail top, which no principal view shows, so
# they get VIEW B (Main's ruling): a partial top view of the rail strip,
# relocated to the band below Section A-A and right of the bottom view, named
# by a letter arrow looking down on the front view's top edge. The crop keeps
# the rail top (half-width NARROW) and stops short of the foot holes the view
# sees through the cavity: at 16 mm it cut them, leaving half hole symbols on
# its edges (r743-p1s-B2 render). The callout text sits right of VIEW B,
# between the hole table and the title block; its rows centre on its y.
VIEW_B_CENTER = (0.210, 0.108)
VIEW_B_CROP_HALF_Z_MM = 12.0
FOOT_HOLE_INNER_Z = min(abs(z) for _, z in HOLES) - HOLE_DIA / 2.0
if not NARROW < VIEW_B_CROP_HALF_Z_MM < FOOT_HOLE_INNER_Z:
    raise AssertionError(
        f"VIEW B fence half-width {VIEW_B_CROP_HALF_Z_MM} must keep the rail top "
        f"({NARROW}) and clear the foot holes ({FOOT_HOLE_INNER_Z:.2f})"
    )
VIEW_B_CAPTION = f"VIEW B\nSCALE {SHEET_SCALE[0]:g}:{SHEET_SCALE[1]:g}"
VIEW_B_CAPTION_XY = (
    VIEW_B_CENTER[0] - BOSS_DEPTH / 2.0 * VIEW_SCALE / 1000.0,
    VIEW_B_CENTER[1] - VIEW_B_CROP_HALF_Z_MM * VIEW_SCALE / 1000.0 - 0.004,
)
SEAT_CALLOUT_XY = (0.300, 0.081)
# The letter matches the section's A (~5 mm) and stands square above its
# tip, clear of the section line (the cone-tip-block pattern). VIEW_B_ARROW
# is (note upper-left, leader tip) in sheet metres.
VIEW_LETTER_HEIGHT = 0.005
VIEW_B_ARROW = (
    (
        FRONT_CENTER[0] - 0.020 - 0.36 * VIEW_LETTER_HEIGHT,
        FRONT_CENTER[1] + HALF_Y * VIEW_SCALE / 1000.0 + 0.013,
    ),
    (FRONT_CENTER[0] - 0.020, FRONT_CENTER[1] + HALF_Y * VIEW_SCALE / 1000.0),
)
# Section A-A pick for the rail depth: 5 mm off the centreline hits both the
# top face (half-width NARROW less the rim chamfer) and the pocket's top face
# (WEB out to the wall).
RAIL_PICK_Z = 5.0
# The web thickness text sits right of the section, clear of the slanted
# wall (x ~0.2187 at y 0.157) and of the 177.8 dimension line at x 0.240;
# at x 0.221 it printed across the wall line (fix3 render).
WEB_TEXT_XY = (RIGHT_CENTER[0] + 0.026, RIGHT_CENTER[1] - 0.028)
RAIL_TEXT_XY = (RIGHT_CENTER[0] - 0.025, RIGHT_CENTER[1] + 0.039)
# The foot's 6.35 spans only 3.2 mm of sheet, too little for its text: at
# y 0.142 the text sat between the extension lines with its own dimension
# line through it (fix4 render). It prints just above the foot's top
# extension line instead, in the gap between the front view and the
# section's slanted wall.
FOOT_TEXT_XY = (RIGHT_CENTER[0] - 0.025, RIGHT_CENTER[1] - 0.0365)
# The section cuts the window rim in profile, and it is the one view where a
# targeted import of RimChamfer delivers RimChamferSize (r743-diag-c, leaf
# 20260926T100550Z-1-829fb125). The front view only ever got it as a side
# effect of the entire-model import, which the #743 rail took away. The callout
# keeps the lane between the front view and the section.
RIGHT_KEEP = {
    "WallHeight": (0.240, 0.185),
    "FootSpan": (0.205, 0.133),
    "TopSpan": (0.205, 0.238),
    # Below the rail-depth dimension, whose rail depth sits at y 0.224 in the same
    # lane: at 0.225 the two ran together ("X 45 DEG21.0", fix3 render).
    "RimChamferSize": (0.165, 0.200),
}

# Top-left anchor; the native four-row table grows down and right while
# remaining clear of the isometric and title block.
HOLE_TABLE_ANCHOR = (0.270, 0.130)
HOLE_TABLE_DATUM_XZ_MM = (-BOSS_DEPTH / 2.0, -WIDE)
# Native hole tags land up-right of their holes. At the bottom view's right
# end that printed A3 and A4 across the pocket's hidden end lines (fix3
# render), so both move to the mirror spot left of their holes: twice the
# 4.6 mm hole-to-tag gap plus the 5.8 mm tag width, measured on A4 there.
RIGHT_END_HOLE_TAGS = ("A3", "A4")
HOLE_TAG_MIRROR_SHIFT = -0.0150
EXPECTED_HOLE_TABLE_LOCATIONS_MM = (
    (149.22, 49.21),
    (28.58, 49.21),
    (149.22, 14.29),
    (28.58, 14.29),
)


def _bottom_sheet_xy(hole_xz: tuple[float, float]) -> tuple[float, float]:
    """Sheet pick point on a foot-hole rim in the bottom view."""
    x_mm, z_mm = hole_xz
    return (
        BOTTOM_CENTER[0] + x_mm * VIEW_SCALE / 1000.0,
        BOTTOM_CENTER[1] + (z_mm + HOLE_DIA / 2.0) * VIEW_SCALE / 1000.0,
    )


def _seat_entry_edge(view: Any) -> Any:
    """The east seat's entry rim on the rail top, as a part edge.

    Resolved through the part's typed seat cylinder rather than a sheet pick:
    the four seats pair up a few millimetres apart on a 1:2 sheet. It is the
    drill-diameter circle on the top face, not the one where the drill point
    starts.
    """
    model = _early_bound(_early_bound(view, "IView").ReferencedDocument, "IModelDoc2")
    diameter = blind_cut_dia_mm(SEAT_SPEC)
    face = _resolve_faces(
        model, {"seat": CylinderFace(diameter, contains_x_mm=SEAT_CALLOUT_X_MM)}
    )["seat"]
    matches = []
    for raw in _early_bound(face, "IFace2").GetEdges() or ():
        edge = _early_bound(raw, "IEdge")
        curve = _early_bound(edge.GetCurve(), "ICurve")
        if not curve.IsCircle():
            continue
        _x, centre_y, _z, *_axis, radius = (float(v) for v in curve.CircleParams)
        if abs(radius - diameter / 2000.0) > 1e-7:
            continue
        if abs(centre_y - HALF_Y / 1000.0) > 1e-7:
            continue
        matches.append(edge)
    if len(matches) != 1:
        raise RuntimeError(f"expected one east-seat entry rim, found {len(matches)}")
    return matches[0]


def _crop_view_b_to_rail(adapter: Any, view: Any) -> None:
    """Crop VIEW B to the rail strip: the whole rail length and the rail top
    with the upper slopes, not the full 63.5 mm foot width."""
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    native_view = _early_bound(view, "IView")
    # The positive control (draw_pinion_arbor's cropped 2:1 *Top, 3107bfa95)
    # rebuilds after placing and locates the fence from the view's own model
    # transform. r743-p1s-A did neither, and its crop did not take. So: rebuild,
    # then prove where the part landed (origin on VIEW_B_CENTER, +X running
    # along the sheet at 1:2) and fence around THAT, not an assumed centre.
    rebuild_drawing(adapter, label="VIEW B placement")
    half_len = (BOSS_DEPTH / 2.0 + 2.0) * VIEW_SCALE / 1000.0
    half_z = VIEW_B_CROP_HALF_Z_MM * VIEW_SCALE / 1000.0
    origin = model_point_in_view(
        adapter, native_view, (0.0, 0.0, 0.0), label="VIEW B part origin"
    )
    east = model_point_in_view(
        adapter, native_view, (BOSS_DEPTH / 2000.0, 0.0, 0.0), label="VIEW B east end"
    )
    _telemetry.info(f"VIEW B part origin at {origin!r}, east end at {east!r}")
    end_run = BOSS_DEPTH / 2.0 * VIEW_SCALE / 1000.0
    if (
        math.dist(origin, VIEW_B_CENTER) > 0.001
        or abs(abs(east[0] - origin[0]) - end_run) > 1e-4
        or abs(east[1] - origin[1]) > 1e-4
    ):
        raise RuntimeError(
            f"VIEW B is not the rail at 1:2 on {VIEW_B_CENTER!r}: part origin "
            f"{origin!r}, east end {east!r}"
        )
    if not ddoc.ActivateView(view_name(adapter, view)):
        raise RuntimeError("failed to activate VIEW B for its crop")
    draw.ClearSelection2(True)
    before = tuple(float(value) for value in native_view.GetOutline())
    sketch = _early_bound(native_view.GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    math_utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    corners = []
    for x, y in (
        (origin[0] - half_len, origin[1] + half_z),
        (origin[0] + half_len, origin[1] - half_z),
    ):
        point = _early_bound(
            math_utility.CreatePoint(double_array([x, y, 0.0])), "IMathPoint"
        )
        projected = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
        corners.append(tuple(float(value) for value in projected.ArrayData))
    _telemetry.info(
        f"VIEW B before crop: outline={before!r}, "
        f"scale={float(native_view.ScaleDecimal)!r}, "
        f"position={tuple(native_view.Position)!r}, "
        f"fence corners in view-sketch space={corners!r}"
    )
    sketch_manager = _early_bound(draw.SketchManager, "ISketchManager")
    segments = tuple(
        sketch_manager.CreateCornerRectangle(*corners[0], *corners[1]) or ()
    )
    if len(segments) != 4:
        raise RuntimeError(f"VIEW B crop fence has {len(segments)} segments, not 4")
    # Crop2 consumes the selected closed profile. A circle stays selected once
    # sketched (the positive control); whether all four rectangle lines do is
    # unproven, so select them all and log what Crop2 is handed.
    for segment in segments:
        if not _early_bound(segment, "ISketchSegment").Select4(True, None):
            raise RuntimeError("failed to select the VIEW B crop fence")
    selected = int(draw.SelectionManager.GetSelectedObjectCount2(-1))
    # IView.Crop2 returns swCropViewErrors_e, where 1 is NoError.
    status = int(native_view.Crop2(False, True, 0))
    _telemetry.info(f"VIEW B Crop2 status {status} with {selected} entities selected")
    if status != 1:
        raise RuntimeError(
            f"failed to crop VIEW B to the rail strip: Crop2 status {status}"
        )
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    native_view.UpdateViewDisplayGeometry()
    if not bool(native_view.IsCropped()):
        raise RuntimeError("VIEW B did not retain its crop")
    outline = tuple(float(value) for value in native_view.GetOutline())
    _telemetry.info(f"VIEW B outline after crop: {outline!r}")
    # r743-p1s-A read 0.116 x 0.035 here with Crop2 = 1 and IsCropped true:
    # larger than the 0.089 x 0.032 top view, so neither flag proves a fence
    # took. The crop is proved against the same view's outline before it:
    # narrower across the rail (the fence runs 2 mm past each end, so the
    # length is not compared) and still centred on the part.
    centre = ((outline[0] + outline[2]) / 2.0, (outline[1] + outline[3]) / 2.0)
    if (
        len(outline) != 4
        or outline[3] - outline[1] >= before[3] - before[1] - 0.002
        or math.dist(centre, origin) > 0.001
    ):
        raise RuntimeError(
            f"VIEW B crop is not the rail strip: before={before!r}, after={outline!r}"
        )


def _add_view_b_arrow(adapter: Any, front: Any) -> None:
    """The letter arrow on the front view that names VIEW B."""
    text_xy, tip_xy = VIEW_B_ARROW
    note = add_leader_note(
        adapter,
        "B",
        text_xy=text_xy,
        attach_xy=tip_xy,
        view=front,
        label="view B viewing arrow",
    )
    # add_note leaves text at the document height; size the letter here and
    # prove the leader tip did not move with it.
    annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
    text_format = annotation.GetTextFormat(0)
    if text_format is None:
        raise RuntimeError("view B arrow note has no text format")
    text_format.CharHeight = VIEW_LETTER_HEIGHT
    if not annotation.SetTextFormat(0, False, text_format):
        raise RuntimeError("failed to size the view B arrow letter")
    rebuild_drawing(adapter, label="view B arrow letter")
    points = list(annotation.GetLeaderPointsAtIndex(0) or ())
    if len(points) < 6 or math.dist((points[-3], points[-2]), tip_xy) > 0.001:
        raise RuntimeError("view B arrow tip moved when its letter was sized")


def _mirror_right_end_hole_tags(view: Any) -> dict[str, tuple[float, float]]:
    """Shift the right-end hole tags left of their holes; return old -> new x."""
    moved: dict[str, tuple[float, float]] = {}
    for raw in _early_bound(view, "IView").GetAnnotations() or ():
        annotation = _early_bound(raw, "IAnnotation")
        if int(annotation.GetType()) != 6:  # swNote
            continue
        note = _early_bound(annotation.GetSpecificAnnotation(), "INote")
        tag = str(note.GetText()).strip()
        if tag not in RIGHT_END_HOLE_TAGS:
            continue
        if tag in moved:
            raise RuntimeError(f"duplicate bottom-view hole tag {tag}")
        x, y = (float(value) for value in annotation.GetPosition()[:2])
        if x < BOTTOM_CENTER[0]:
            raise RuntimeError(f"hole tag {tag} is not at the right end: x={x:.4f}")
        target = (x + HOLE_TAG_MIRROR_SHIFT, y)
        if not annotation.SetPosition2(*target, 0.0):
            raise RuntimeError(f"failed to move hole tag {tag}")
        after = tuple(float(value) for value in annotation.GetPosition()[:2])
        if max(abs(a - b) for a, b in zip(after, target)) > 1e-6:
            raise RuntimeError(f"hole tag {tag} landed at {after!r}, not {target!r}")
        if str(note.GetText()).strip() != tag:
            raise RuntimeError(f"moving hole tag {tag} changed its text")
        moved[tag] = (x, after[0])
    if set(moved) != set(RIGHT_END_HOLE_TAGS):
        raise RuntimeError(
            f"bottom-view hole tags {sorted(set(RIGHT_END_HOLE_TAGS) - set(moved))} "
            "not found"
        )
    _telemetry.info(f"bottom-view hole tags moved left of their holes: {moved}")
    return moved


def _bottom_datum_axes(adapter: Any, view: Any) -> tuple[Any, Any]:
    """Return the chamfer-inset edges used to create the native table."""
    components = adapter._attempt(lambda: view.GetVisibleComponents(), default=()) or ()
    x_axes: list[Any] = []
    y_axes: list[Any] = []
    for component in components:
        edges = (
            adapter._attempt(
                lambda c=component: view.GetVisibleEntities2(c, 1),
                default=(),
            )
            or ()
        )
        for raw_edge in edges:
            edge = _early_bound(raw_edge, "IEdge")
            curve = _early_bound(edge.GetCurve(), "ICurve")
            if not curve.IsLine():
                continue
            parameters = tuple(float(value) for value in curve.LineParams)
            if (
                abs(parameters[2] + (WIDE - CHAMFER) / 1000.0) <= 2e-6
                and abs(parameters[3]) >= 0.99
            ):
                x_axes.append(edge)
            if (
                abs(parameters[0] + (BOSS_DEPTH / 2.0 - CHAMFER) / 1000.0) <= 2e-6
                and abs(parameters[5]) >= 0.99
            ):
                y_axes.append(edge)
    if not x_axes or not y_axes:
        raise RuntimeError("bottom view is missing a chamfer-inset datum edge")
    return x_axes[0], y_axes[0]


def _right_seat_edge(adapter: Any, view: Any) -> Any:
    """Return the longest right-view edge on the mounting-face plane."""
    span, edge = _longest_right_z_edge(adapter, view, -HALF_Y, label="mounting-face")
    if span < (2.0 * WIDE - 2.0 * CHAMFER - 0.1) / 1000.0:
        raise RuntimeError(f"mounting-face edge spans only {span * 1000.0:.3f} mm")
    return edge


def _right_rail_edges(adapter: Any, view: Any) -> tuple[Any, Any]:
    """The rail's top face and the window's top face, as model edges along Z
    in section A-A. Coordinate picks there returned a 2225.98 mm "rail depth"
    (r743-rocker-fix2, leaf 20260926T101855Z-1-f5fea24f), so the rail depth is
    dimensioned between these exact entities instead."""
    top_span, top = _longest_right_z_edge(adapter, view, HALF_Y, label="rail top-face")
    window_span, window = _longest_right_z_edge(
        adapter, view, WINDOW_TOP_Y, label="window top-face"
    )
    _telemetry.info(
        f"section rail edges: top face {top_span * 1000.0:.3f} mm long at y {HALF_Y}, "
        f"window top {window_span * 1000.0:.3f} mm long at y {WINDOW_TOP_Y}"
    )
    return top, window


def _longest_right_z_edge(
    adapter: Any, view: Any, y_mm: float, *, label: str
) -> tuple[float, Any]:
    """The longest visible model line along Z lying at local height ``y_mm``."""
    components = adapter._attempt(lambda: view.GetVisibleComponents(), default=()) or ()
    candidates: list[tuple[float, Any]] = []
    for component in components:
        edges = (
            adapter._attempt(
                lambda c=component: view.GetVisibleEntities2(c, 1),
                default=(),
            )
            or ()
        )
        for raw_edge in edges:
            edge = _early_bound(raw_edge, "IEdge")
            curve = _early_bound(edge.GetCurve(), "ICurve")
            if not curve.IsLine():
                continue
            parameters = tuple(float(value) for value in curve.LineParams)
            if abs(parameters[1] - y_mm / 1000.0) > 2e-6 or abs(parameters[5]) < 0.99:
                continue
            start = _early_bound(edge.GetStartVertex(), "IVertex").GetPoint()
            end = _early_bound(edge.GetEndVertex(), "IVertex").GetPoint()
            candidates.append((abs(float(end[2]) - float(start[2])), edge))
    if not candidates:
        raise RuntimeError(f"right view has no model edge on the {label} plane")
    return max(candidates, key=lambda item: item[0])


@_telemetry.traced("drawing.planar_centerline", label_param="label")
def _create_view_centerline(
    adapter: Any,
    view: Any,
    *,
    start_xy: tuple[float, float],
    end_xy: tuple[float, float],
    label: str,
) -> Any:
    """Create a retained centerline in one drawing view's sketch."""
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    name = view_name(adapter, view)
    if not ddoc.ActivateView(name):
        raise RuntimeError(f"failed to activate centerline view {name!r}")
    sketch_manager = _early_bound(draw.SketchManager, "ISketchManager")
    previous_add_to_db = bool(sketch_manager.AddToDB)
    previous_display = bool(sketch_manager.DisplayWhenAdded)
    sketch_manager.AddToDB = True
    sketch_manager.DisplayWhenAdded = True
    try:
        centerline = sketch_manager.CreateCenterLine(
            start_xy[0],
            start_xy[1],
            0.0,
            end_xy[0],
            end_xy[1],
            0.0,
        )
    finally:
        sketch_manager.AddToDB = previous_add_to_db
        sketch_manager.DisplayWhenAdded = previous_display
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    if centerline is None:
        raise RuntimeError(f"failed to create {label} centerline")
    return centerline


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open rocker-arm-support source", await adapter.open_model(str(SOURCE)))
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
    drawing_model, sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Rocker-Arm Support Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "rocker-arm support; manufacturing drawing; casting",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    # swDetailingSectionViewLineStyleDisplay (swconst.tlb R2026x): end segments
    # only. Span the full parent view so SolidWorks derives a stable, complete
    # centre section; the dimensions occupy exterior lanes away from its arrows.
    extension = _early_bound(drawing_model.Extension, "IModelDocExtension")
    if not extension.SetUserPreferenceInteger(542, 0, 1):
        raise RuntimeError("failed to set end-only section cutting line")
    if extension.GetUserPreferenceInteger(542, 0) != 1:
        raise RuntimeError("section cutting-line style did not persist")

    # Explicit per-view scale: a view placed without one can silently
    # auto-scale, which shifts every coordinate-based pick on it.
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(1, 2))
    right = create_section_view(
        adapter,
        front,
        line_start=(FRONT_CENTER[0], FRONT_CENTER[1] - 0.050),
        line_end=(FRONT_CENTER[0], FRONT_CENTER[1] + 0.050),
        view_xy=RIGHT_CENTER,
        section_label="A",
        scale=(1, 2),
        label="rocker-arm support centre section",
    )
    bottom = place_view(adapter, str(SOURCE), "*Bottom", *BOTTOM_CENTER, scale=(1, 2))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 2))
    for view in (front, bottom):
        set_hidden_lines_visible(adapter, view)
    set_hidden_lines_removed(adapter, right)
    set_hidden_lines_removed(adapter, iso)

    front_dimensions = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    right_dimensions = curate_view_dimensions(
        adapter,
        right,
        keep=RIGHT_KEEP,
        view_label="right",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    dimensions = [*front_dimensions, *right_dimensions]
    set_dimension_callouts(adapter, dimensions, DIMENSION_CALLOUTS)
    set_dimension_precision(adapter, dimensions, imported_precision())
    _create_view_centerline(
        adapter,
        front,
        start_xy=(-BOSS_DEPTH / 2000.0, 0.0),
        end_xy=(BOSS_DEPTH / 2000.0, 0.0),
        label="front wall",
    )
    _create_view_centerline(
        adapter,
        front,
        start_xy=(0.0, -HALF_Y / 1000.0),
        end_xy=(0.0, HALF_Y / 1000.0),
        label="front vertical",
    )
    _create_view_centerline(
        adapter,
        right,
        start_xy=(0.0, -HALF_Y / 1000.0),
        end_xy=(0.0, HALF_Y / 1000.0),
        label="section web",
    )
    # Pick the two cut pocket floors in the LOWER web band, between the cavity
    # and the foot: the upper band is solid rail since #743. HLR ensures the
    # selected edges are visible section edges.
    web_y = RIGHT_CENTER[1] - (BIG + CAV) / 2.0 * VIEW_SCALE / 1000.0
    half_web = WEB * VIEW_SCALE / 1000.0
    web_dimension = _early_bound(
        add_edge_dimension(
            adapter,
            right,
            p0=(RIGHT_CENTER[0] - half_web, web_y),
            p1=(RIGHT_CENTER[0] + half_web, web_y),
            text_xy=WEB_TEXT_XY,
            orientation="horizontal",
            label="section web thickness",
        ),
        "IDisplayDimension",
    )
    measured = float(
        _early_bound(web_dimension.GetDimension2(0), "IDimension").SystemValue
    )
    if abs(measured * 1000.0 - 2.0 * WEB) > 1e-5:
        raise RuntimeError(f"section web dimension measured {measured * 1000.0:.6f} mm")
    web_dimension.SetPrecision3(DIMENSION_PRECISION["WebThickness"], -1, -1, -1)
    if web_dimension.GetPrimaryPrecision2() != DIMENSION_PRECISION["WebThickness"]:
        raise RuntimeError("section web dimension precision did not persist")
    foot_pick_x = RIGHT_CENTER[0] + 0.010
    foot_dimension = _early_bound(
        add_edge_dimension(
            adapter,
            right,
            p0=(
                foot_pick_x,
                RIGHT_CENTER[1] - HALF_Y * VIEW_SCALE / 1000.0,
            ),
            p1=(
                foot_pick_x,
                RIGHT_CENTER[1] - BIG * VIEW_SCALE / 1000.0,
            ),
            text_xy=FOOT_TEXT_XY,
            orientation="vertical",
            label="section foot thickness",
        ),
        "IDisplayDimension",
    )
    measured = float(
        _early_bound(foot_dimension.GetDimension2(0), "IDimension").SystemValue
    )
    if abs(measured * 1000.0 - (HALF_Y - BIG)) > 1e-5:
        raise RuntimeError(
            f"section foot dimension measured {measured * 1000.0:.6f} mm"
        )
    foot_dimension.SetPrecision3(DIMENSION_PRECISION["FootThickness"], -1, -1, -1)
    # The rail: top face down to the window's top face, between the exact
    # model edges (the coordinate picks still locate the view, not the ends).
    rail_pick_x = RIGHT_CENTER[0] - RAIL_PICK_Z * VIEW_SCALE / 1000.0
    rail_dimension = _early_bound(
        add_edge_dimension(
            adapter,
            right,
            p0=(rail_pick_x, RIGHT_CENTER[1] + HALF_Y * VIEW_SCALE / 1000.0),
            p1=(rail_pick_x, RIGHT_CENTER[1] + WINDOW_TOP_Y * VIEW_SCALE / 1000.0),
            text_xy=RAIL_TEXT_XY,
            orientation="vertical",
            label="section rail depth",
            entities=_right_rail_edges(adapter, right),
        ),
        "IDisplayDimension",
    )
    measured = float(
        _early_bound(rail_dimension.GetDimension2(0), "IDimension").SystemValue
    )
    if abs(measured * 1000.0 - RAIL_DEPTH) > 1e-5:
        raise RuntimeError(
            f"section rail dimension measured {measured * 1000.0:.6f} mm"
        )
    rail_dimension.SetPrecision3(DIMENSION_PRECISION["RailDepth"], -1, -1, -1)
    if rail_dimension.GetPrimaryPrecision2() != DIMENSION_PRECISION["RailDepth"]:
        raise RuntimeError("section rail dimension precision did not persist")
    if not auto_center_marks(adapter, bottom, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to bottom view")

    # The mounting face is the trapezoid's visible bottom edge in section A-A.
    # Keep the symbol near the foot while clearing the 63.5 width dimension.
    seat_y = RIGHT_CENTER[1] - HALF_Y * VIEW_SCALE / 1000.0
    seat_half_w = WIDE * VIEW_SCALE / 1000.0
    add_surface_finish(
        adapter,
        right,
        edge_entity=_right_seat_edge(adapter, right),
        symbol_xy=(RIGHT_CENTER[0] + seat_half_w + 0.020, seat_y - 0.010),
        control=surface_finish_by_key(SURFACE_FINISHES, "mounting_face"),
        label="mounting face finish",
        char_height=0.0025,
        leader_attach_xy=(RIGHT_CENTER[0] + seat_half_w - 0.002, seat_y),
    )

    datum_axes = _bottom_datum_axes(adapter, bottom)
    datum_point = create_view_theoretical_datum(
        adapter,
        bottom,
        point_xy=(
            HOLE_TABLE_DATUM_XZ_MM[0] / 1000.0,
            HOLE_TABLE_DATUM_XZ_MM[1] / 1000.0,
        ),
        label="rocker-arm-support lower-left theoretical corner",
    )
    # No position frame on this part (simplicity policy rule 3/4), so the hole
    # coordinates are ordinary two-place dimensions under the title block's
    # ±0.51 — NOT basic: a basic dimension is toleranced only by the frame it
    # feeds, and without one it has no tolerance at all.
    insert_hole_table(
        adapter,
        bottom,
        datum_xy=(
            BOTTOM_CENTER[0] + HOLE_TABLE_DATUM_XZ_MM[0] * VIEW_SCALE / 1000.0,
            BOTTOM_CENTER[1] + HOLE_TABLE_DATUM_XZ_MM[1] * VIEW_SCALE / 1000.0,
        ),
        hole_points=tuple(_bottom_sheet_xy(hole) for hole in HOLES),
        datum_point=datum_point,
        expected_locations_mm=EXPECTED_HOLE_TABLE_LOCATIONS_MM,
        datum_axes=datum_axes,
        anchor_xy=HOLE_TABLE_ANCHOR,
        basic_locations=False,
        label="rocker-arm-support",
    )
    _mirror_right_end_hole_tags(bottom)
    # The drawing-sketch datum and hole table leave the bottom view's HLV edge
    # set stale, so restore its complete projected edge set before export.
    set_hidden_lines_visible(adapter, bottom)
    _telemetry.info(
        f"bottom view outline (uncropped 1:2 control): "
        f"{tuple(_early_bound(bottom, 'IView').GetOutline())!r}"
    )
    view_b = place_view(adapter, str(SOURCE), "*Top", *VIEW_B_CENTER, scale=(1, 2))
    set_hidden_lines_removed(adapter, view_b)
    _crop_view_b_to_rail(adapter, view_b)
    if not auto_center_marks(adapter, view_b, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to VIEW B")
    if add_note(adapter, VIEW_B_CAPTION, *VIEW_B_CAPTION_XY) is None:
        raise RuntimeError("failed to caption VIEW B")
    _add_view_b_arrow(adapter, front)
    add_native_hole_callout(
        adapter,
        view_b,
        edge=_seat_entry_edge(view_b),
        callout_xy=SEAT_CALLOUT_XY,
        label="rocker-bracket transfer seats",
        process=SEAT_CALLOUT_PROCESS,
    )

    # Materialize the iso's cosmetic threads before the strict final note
    # cleanup, so BracketSeats' descriptive label exists when it is counted
    # rather than first appearing during the native drawing save.
    # VIEW B shows the same seats face-on, so its cosmetic threads are
    # imported too (the thread circles print; nothing is left for the save to
    # add). r743-p1s-B showed the import brings NO label in that top view:
    # finalize removed exactly the iso's one.
    import_cosmetic_threads(adapter, iso)
    import_cosmetic_threads(adapter, view_b)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Rocker-Arm Support Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        # BracketSeats' descriptive label on the isometric ran past the
        # right border (fix3 render); the seat note already states it. One
        # label per tapped Hole Wizard feature, and only the iso draws one
        # (r743-p1s-B: VIEW B's import brought none).
        redundant_note_substrings=("Tapped Hole",),
        expected_redundant_notes=1,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
