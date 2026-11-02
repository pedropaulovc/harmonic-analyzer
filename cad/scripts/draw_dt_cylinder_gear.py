r"""Create the simplicity-policy manufacturing drawing for the cylinder gear.

The portrait sheet uses one aligned third-angle row: the cam-side front view
shows the eccentric follower, bore and phase notch, while the right view shows
the axial stack.  A standard isometric supplies pictorial clarity without
replacing those manufacturing views.
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    dimension_name,
    place_view,
    view_name,
)

from _check import check
from _com import _early_bound, _read_member
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    stamp_drawing_summary,
)
from _drawing_dimension_import import curate_view_dimensions
from _drawing_dimensions import (
    assert_imported_precision,
    offset_dimension_text,
    set_dimension_callouts,
    set_reference_dimension,
)
from _drawing_edge_dimensions import assert_dimension_measures
from _drawing_edges import visible_view_entities
from _drawing_finish import add_surface_finish
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed, set_hidden_lines_visible
from _gear_drawing_entities import visible_circle_edge
from _gtol_face_read import face_geometry
from _machinist_review_mode import MachinistReviewMode
from _part_properties import part_drawing_unit
from _paths import CAD_ROOT
from _session import run_build
from _surface_finish import surface_finish_by_key
import _telemetry
from dt_cylinder_gear_notes import BORE_FIT_CALLOUT, STACK_FIT_CALLOUT
from dt_cylinder_gear_spec import (
    BORE_DIA,
    CAM_DIA,
    CAM_THICKNESS,
    DRAWING_PRECISION_BY_NAME,
    DRAWING_REFERENCE_PRECISION,
    ECCENTRICITY,
    FACE_WIDTH,
    NOTCH_CENTER_X,
    NOTCH_FLOOR_RADIUS,
    OVERALL_THICKNESS,
    PATTERN_NOTCH_REF_ANGLE_DEG,
    SURFACE_FINISHES,
    TIP_RADIUS,
)


# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["dt_cylinder_gear"]
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

# Portrait keeps the configured drum readable without crowding the views.
# The cam-side front view exposes every radial feature, so a redundant
# opposite face view would only consume the exterior dimension lanes.
SHEET_SCALE = (3.0, 2.0)
VIEW_SCALE = (3, 2)
FRONT_CENTER = (0.105, 0.270)
RIGHT_CENTER = (0.205, 0.270)
ISO_CENTER = (0.165, 0.145)
GEAR_DATA_POS = (0.015, 0.410)
# The 6:1 boundary prints 25.2 mm off this centre; NotchDepth's two-row text
# hangs left of it at x 13.9..36.1 (fixed by its 0.025 dimension line and the
# 12.7 border zone), so at 0.060 the circle's flank (34.8) crossed "FROM OD"
# (text-on-line).  6 mm right the flank sits at 40.8, 4.7 mm clear, with the
# outline (30..102) still short of the isometric's (122.7).
NOTCH_DETAIL_CENTER = (0.066, 0.155)
NOTCH_DETAIL_SCALE = (6, 1)
NOTCH_DETAIL_RADIUS_MM = 4.0
# The fence's letter, up-left of the 6 mm circle (x 98.4..110.4, y 310.8..
# 322.8): clear of the notch-phase and (90°) extension lines at x 102.6..105
# that crossed it above the circle (r1 layout audit, text-on-line), and of
# the teeth (top y 318.3), whichever corner SolidWorks anchors.
NOTCH_DETAIL_LETTER_XY = (0.093, 0.326)
NOTCH_DETAIL_DIMENSIONS = {
    "NotchWidth": (0.092, 0.199),
    "NotchDepth": (0.027, 0.155),
}

# Machinist review r1 named the mate at every tight band (rule 4), which
# grows the callouts; the lanes below are sized for them (sheet mm, gear
# centre ~(105, 270), tip r 48.3, cam centre (105, 283) r 23.0, bore r 7.2).
#
# * The bore-fit block (nine rows <= 19 characters, x ~18..72, y ~316..364,
#   under the gear data's last row at ~369; r5: at 13.8 its underline nearly
#   met the border) ends its leader shoulder at x ~72: the radial leader to
#   the bore then
#   meets the cam diameter's diametral line only beyond the shoulder, never
#   between it and the bore (r1: the 82 mm block's corner at x 98 crossed it).
# * The cam diameter drops to the gear's lower right; its three mate rows
#   hang to y ~216, left of the side view (194) and above the isometric (212).
# * The eccentricity's text leaves its extension lines (y 270/283) for the
#   free lane below them, so its two function rows sit on no line.  The
#   text hangs RIGHT of its dimension line (r2: from x 174 its 35 mm shelf
#   reached the side view's cam at 205.7), so the line stands just off the
#   tips (153.4) and the shelf ends ~192, short of the side view (194).
# * The notch phase's four rows (x ~112..150, y ~320..344) stay inside the
#   (90°) arc (r 88.6 off the gear centre; r4b: a larger arc reached the side
#   view and the gear data) with the cam finish symbol moved down out of them.
FRONT_KEEP = {
    "BoreDia": (0.045, 0.338),
    "CamDia": (0.166, 0.232),
    "CamCy": (0.157, 0.257),
    "NotchPhase": (0.131, 0.332),
    "PatternNotchPhase": (0.178, 0.321),
}
# The stacking text stands right of the side view's rims (x ~213..261, y
# ~352..374), the dimension line running out under it: centred over the
# 10.6 mm stack, its 29 mm value sat on the line and both extension-line
# ends struck it (machinist r2, r4; offsetting it only added a shelf).
RIGHT_KEEP = {
    "OutsideDia": (0.248, RIGHT_CENTER[1]),
    "FaceWidth": (0.205, 0.220),
    "OverallThickness": (0.237, 0.363),
}
# Face width's text leaves its dimension line for the free lower-right lane:
# at (0.225, 0.220) the OD's lower extension line (y 221.7) ran through it and
# its own dimension line ran 2.2 mm into it (r1 layout audit).
FACE_WIDTH_TEXT = (0.240, 0.207)
# The parenthesised cam thickness moves above the side view, left of its
# rims, so the lower lane is face width's alone (x 172..188, y ~336: left of
# the stacking text, outside the (90°) arc).
CAM_REFERENCE_TEXT = (0.180, 0.336)
CAM_FINISH_SYMBOL = (0.152, 0.303)
DIMENSION_CALLOUTS = {
    "BoreDia": BORE_FIT_CALLOUT,
    "OutsideDia": "MESHES WITH\nCONE GEARS\nMHA-DT-03",
    "FaceWidth": "SETS ROD-RING SLOT\nFOR MHA-CH-03",
    "CamDia": "RUNNING FIT IN\nCONNECTING ROD\nMHA-CH-03 RING",
    "CamCy": "THROW SETS\nCHANNEL GAIN",
    "NotchWidth": "ALIGNMENT NOTCH;\nNO MATING PART;\nMAX CLEARS FLANKS",
    "NotchDepth": "FROM OD",
    "NotchPhase": "NOTCH CCW FROM\nCAM LOBE; SETS\nCHANNEL PHASE",
}
# Decimal places are the part's (cylinder_gear_spec.DRAWING_PRECISION,
# applied by build_cylinder_gear); the sheet only reads them back.


def _project_mm(
    adapter: Any,
    view: Any,
    xyz_mm: tuple[float, float, float],
    *,
    label: str,
) -> tuple[float, float]:
    return model_point_in_view(
        adapter,
        view,
        tuple(value / 1000.0 for value in xyz_mm),
        label=label,
    )


def _notch_detail(adapter: Any, front: Any) -> Any:
    """Enlarge the actual kerf and its neighbouring teeth, without redrawing them."""
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    parent = _early_bound(front, "IView")
    if not ddoc.ActivateView(view_name(adapter, front)):
        raise RuntimeError("failed to activate notch-detail parent")
    draw.ClearSelection2(True)
    center = _project_mm(
        adapter,
        front,
        (NOTCH_CENTER_X, (TIP_RADIUS + NOTCH_FLOOR_RADIUS) / 2.0, 0.0),
        label="notch detail center",
    )
    radius = NOTCH_DETAIL_RADIUS_MM * VIEW_SCALE[0] / VIEW_SCALE[1] / 1000.0
    sketch = _early_bound(parent.GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    math_utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    points = []
    for x, y in (center, (center[0] + radius, center[1])):
        point = _early_bound(
            math_utility.CreatePoint(double_array([x, y, 0.0])), "IMathPoint"
        )
        projected = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
        points.append(tuple(float(value) for value in projected.ArrayData))
    sketch_manager = _early_bound(draw.SketchManager, "ISketchManager")
    if sketch_manager.CreateCircle(*points[0], *points[1]) is None:
        raise RuntimeError("failed to create notch-detail fence")
    detail = ddoc.CreateDetailViewAt4(
        *NOTCH_DETAIL_CENTER,
        0.0,
        0,  # swDetViewSTANDARD
        *NOTCH_DETAIL_SCALE,
        "A",
        1,  # swDetCircleCIRCLE
        True,
        False,
        False,
        5,
    )
    if detail is None:
        raise RuntimeError("failed to create native notch detail")
    detail = _early_bound(detail, "IView")
    detail.ScaleRatio = double_array([float(value) for value in NOTCH_DETAIL_SCALE])
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    initial_outline = tuple(float(value) for value in detail.GetOutline())
    initial_position = tuple(float(value) for value in detail.Position)
    if len(initial_outline) != 4 or len(initial_position) != 2:
        raise RuntimeError(
            f"invalid native notch detail bounds: {initial_outline!r}, {initial_position!r}"
        )
    # A cropped view's Position is not its visible crop center. Translate the
    # native origin by the measured outline-center error, rather than assigning
    # the requested crop center directly to that origin.
    positioned_origin = tuple(
        initial_position[axis]
        + NOTCH_DETAIL_CENTER[axis]
        - (initial_outline[axis] + initial_outline[axis + 2]) / 2.0
        for axis in range(2)
    )
    if not detail.SetViewPosition(double_array(list(positioned_origin)), False):
        raise RuntimeError("failed to position notch detail")
    draw.EditRebuild3()
    ratio = tuple(float(value) for value in detail.ScaleRatio)
    final_outline = tuple(float(value) for value in detail.GetOutline())
    if len(final_outline) != 4:
        raise RuntimeError(f"invalid final notch detail bounds: {final_outline!r}")
    outline_center = (
        (final_outline[0] + final_outline[2]) / 2.0,
        (final_outline[1] + final_outline[3]) / 2.0,
    )
    if len(ratio) != 2 or not math.isclose(
        ratio[0] / ratio[1], NOTCH_DETAIL_SCALE[0] / NOTCH_DETAIL_SCALE[1]
    ):
        raise RuntimeError(f"notch detail scale did not persist: {ratio!r}")
    if math.dist(outline_center, NOTCH_DETAIL_CENTER) > 0.0001:
        raise RuntimeError(
            f"notch detail outline center did not persist: "
            f"initial_outline={initial_outline!r}, initial_position={initial_position!r}, "
            f"requested_origin={positioned_origin!r}, final_outline={final_outline!r}"
        )
    _telemetry.info(
        f"notch detail position: initial_outline={initial_outline!r}, "
        f"initial_position={initial_position!r}, origin={positioned_origin!r}, "
        f"final_outline={final_outline!r}, crop_center={outline_center!r}"
    )
    circles = tuple(_read_member(parent, "GetDetailCircles") or ())
    if len(circles) != 1:
        raise RuntimeError(
            f"expected one detail circle on the front view, found {len(circles)}"
        )
    circle = _early_bound(circles[0], "IDetailCircle")
    circle.SetLabelPosition(*NOTCH_DETAIL_LETTER_XY)
    draw.EditRebuild3()
    letter = tuple(float(value) for value in circle.GetLabelPosition())
    if len(letter) != 2 or math.dist(letter, NOTCH_DETAIL_LETTER_XY) > 1e-8:
        raise RuntimeError(f"notch detail letter did not persist: {letter!r}")
    return detail


def _notch_dimension_state(dimension: Any) -> tuple[Any, ...]:
    """Snapshot the native model parameter, not formatted drawing text."""
    dimension = _early_bound(dimension, "IDimension")
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    return (
        str(dimension.FullName),
        float(dimension.SystemValue),
        int(tolerance.Type),
        tolerance.GetMinValue2(),
        tolerance.GetMaxValue2(),
    )


def _check_notch_dimensions(
    adapter: Any,
    front: Any,
    right: Any,
    detail: Any,
    original: dict[str, tuple[Any, ...]],
) -> list[Any]:
    """Require one native detail annotation matching each original part parameter."""
    target_name = view_name(adapter, detail)
    target_annotations = [
        _early_bound(item, "IAnnotation")
        for item in (_early_bound(detail, "IView").GetAnnotations() or ())
    ]
    target_names = [dimension_name(adapter, item) for item in target_annotations]
    other_names = {
        view_name(adapter, view): [
            dimension_name(adapter, _early_bound(item, "IAnnotation"))
            for item in (_early_bound(view, "IView").GetAnnotations() or ())
        ]
        for view in (front, right)
    }
    for name, text_xy in NOTCH_DETAIL_DIMENSIONS.items():
        matches = [
            item
            for item, item_name in zip(target_annotations, target_names, strict=True)
            if item_name == name
        ]
        if len(matches) != 1 or any(name in names for names in other_names.values()):
            raise RuntimeError(
                f"notch dimension {name} lacks unique detail authority: "
                f"other_views={other_names!r}; "
                f"target={target_name!r} names={target_names!r}"
            )
        display = _early_bound(matches[0].GetSpecificAnnotation(), "IDisplayDimension")
        state = _notch_dimension_state(display.GetDimension2(0))
        if state != original[name]:
            raise RuntimeError(
                f"native notch dimension {name} differs from source part: "
                f"source={original[name]!r}, detail={state!r}"
            )
        position = tuple(float(value) for value in matches[0].GetPosition())
        if math.dist(position[:2], text_xy) > 0.0001:
            raise RuntimeError(f"notch dimension {name} position did not persist")
    return [
        annotation
        for annotation, name in zip(target_annotations, target_names, strict=True)
        if name in NOTCH_DETAIL_DIMENSIONS
    ]


# swDimensionType_e: the cam thickness must read back as a linear type.
_LINEAR_DIMENSION = 2  # swLinearDimension
_HORIZONTAL_LINEAR_DIMENSION = 11  # swHorLinearDimension
_SEL_EDGES = 1  # swSelectType_e.swSelEDGES


def _cam_thickness_rims(view: Any) -> dict[float, Any]:
    """The two circular boundaries of the exposed cam cylinder, by station.

    The cam boss merges into the gear blank at z=FACE_WIDTH and ends at
    z=OVERALL_THICKNESS; both rims are edges of the one controlled cam face
    (``SURFACE_FINISHES["cam_follower"]``), each a circle of the cam's radius
    about the eccentric axis.  Exactly one rim must match at each station.
    """
    control = surface_finish_by_key(SURFACE_FINISHES, "cam_follower")
    faces = []
    for face in visible_view_entities(view, 3, label="cam thickness face"):
        geometry = face_geometry(face)
        if geometry is not None and control.face.matches(geometry):
            faces.append(face)
    if len(faces) != 1:
        raise RuntimeError(
            f"cam thickness reference: expected one cam face, got {len(faces)}"
        )
    matches: dict[float, list[tuple[Any, tuple[float, ...]]]] = {
        FACE_WIDTH: [],
        OVERALL_THICKNESS: [],
    }
    circles = []
    for edge in _early_bound(faces[0], "IFace2").GetEdges() or ():
        curve = _early_bound(edge, "IEdge").GetCurve()
        if curve is None:
            continue
        curve = _early_bound(curve, "ICurve")
        if not curve.IsCircle():
            continue
        # ICurve.CircleParams: centre xyz, axis xyz, radius (metres).
        params = tuple(float(value) for value in curve.CircleParams)
        circles.append(params)
        for station, edges in matches.items():
            centre = (0.0, ECCENTRICITY / 1000.0, station / 1000.0)
            if (
                math.dist(params[:3], centre) <= 1e-7
                and abs(params[6] - CAM_DIA / 2000.0) <= 1e-7
                and abs(abs(params[5]) - 1.0) <= 1e-6
                and math.hypot(params[3], params[4]) <= 1e-6
            ):
                edges.append((edge, params))
    for station, edges in matches.items():
        if len(edges) != 1:
            raise RuntimeError(
                f"cam thickness reference: expected one circular cam rim at "
                f"z={station:g} mm, got {len(edges)}; circular boundaries={circles!r}"
            )
    _telemetry.info(
        "cam thickness reference: selected the cam's circular rims "
        f"(centre xyz, axis xyz, radius; metres) "
        f"{[edges[0][1] for edges in matches.values()]!r}"
    )
    return {station: edges[0][0] for station, edges in matches.items()}


def _cam_thickness_reference(adapter: Any, view: Any) -> Any:
    """Dimension the cam's two rims with an explicitly linear native dimension.

    The parenthesised cam thickness is the stacking thickness less the face
    width (#743): a read-only difference with no model dimension to import, so
    it is built here between the cam's own rims and its places come from the
    spec's ``DRAWING_REFERENCE_PRECISION`` keyed by ``label`` -- never a
    literal.  On the first cold v39 build (farm run 20261002T180658288Z) the
    former coordinate picks -- the gear's rear face below the cam and the
    cam's rear edge -- produced a dimension reading 1570.8 "mm": a SystemValue
    of pi/2, a right angle, not a length.  The rims are selected by entity, the
    dimension type is requested (``swHorLinearDimension``) and read back, and
    the attachment and value are checked against the two named rims.
    """
    label = "cam thickness reference"
    rims = _cam_thickness_rims(view)
    draw = adapter.currentModel
    if not _early_bound(draw, "IDrawingDoc").ActivateView(view_name(adapter, view)):
        raise RuntimeError(f"{label}: failed to activate the right view")
    draw.ClearSelection2(True)
    manager = _early_bound(draw.SelectionManager, "ISelectionMgr")
    for index, (station, edge) in enumerate(rims.items(), 1):
        data = manager.CreateSelectData()
        data.View = view
        if _early_bound(edge, "IEntity").Select4(index > 1, data) is not True:
            raise RuntimeError(
                f"{label}: failed to select the cam rim at z={station:g} mm"
            )
        selected = manager.GetSelectedObject6(index, -1)
        if (
            int(manager.GetSelectedObjectCount2(-1)) != index
            or int(manager.GetSelectedObjectType3(index, -1)) != _SEL_EDGES
            or int(adapter.swApp.IsSame(selected, edge)) != 1
        ):
            raise RuntimeError(
                f"{label}: the selection is not the cam rim at z={station:g} mm"
            )
        landing = _project_mm(
            adapter,
            view,
            (0.0, ECCENTRICITY - CAM_DIA / 2.0, station),
            label=f"{label} rim landing",
        )
        point_set = manager.SetSelectionPoint2(index, -1, landing[0], landing[1], 0.0)
        if point_set is not True:
            raise RuntimeError(f"{label}: failed to set the cam rim selection point")
    # ``Error`` is an [out] VT_I4: the early-bound call returns (display, error).
    display, status = _early_bound(
        draw.Extension, "IModelDocExtension"
    ).AddSpecificDimension(*CAM_REFERENCE_TEXT, 0.0, _HORIZONTAL_LINEAR_DIMENSION, 0)
    draw.ClearSelection2(True)
    if display is None or int(status) != 0:  # swAddSpecificDimension_Success
        raise RuntimeError(
            f"{label}: horizontal linear dimension failed, status={status}"
        )
    display = _early_bound(display, "IDisplayDimension")
    dimension_type = int(display.Type2)
    if dimension_type not in (_LINEAR_DIMENSION, _HORIZONTAL_LINEAR_DIMENSION):
        raise RuntimeError(
            f"{label}: expected a linear dimension, got type {dimension_type}"
        )
    measured_mm = assert_dimension_measures(
        adapter,
        display,
        expected_mm=CAM_THICKNESS,
        label=label,
        entities=(rims[FACE_WIDTH], rims[OVERALL_THICKNESS]),
    )
    _telemetry.info(
        f"{label}: native type {dimension_type}, measured {measured_mm:g} mm"
    )
    places = DRAWING_REFERENCE_PRECISION[label]
    # -1: swDimensionPrecisionSettings_e do-not-change for the dual and both
    # tolerance places.  The subscript is written out again because
    # _drawing_contract only accepts a spec lookup here.
    display.SetPrecision3(DRAWING_REFERENCE_PRECISION[label], -1, -1, -1)
    if int(display.GetPrimaryPrecision2()) != places:
        raise RuntimeError(
            f"{label}: precision {display.GetPrimaryPrecision2()} != {places}"
        )
    return display


def _leader_outside_arrow(adapter: Any, annotations: list[Any], name: str) -> None:
    """Show diameter ``name`` as one outside arrow on the rim, no diametral line.

    Inside arrows draw the dimension line right across the circle, through the
    gear centre -- where every leader to the eccentric bore from the note
    lanes above has to cross it (codex iter4).  Outside arrows plus hidden
    diametral leaders keep the value and its band while leaving a single
    leader to the rim (draw_tube_frame's OD reference does the same).
    """
    matches = [
        annotation
        for annotation in annotations
        if dimension_name(adapter, annotation) == name
    ]
    if len(matches) != 1:
        raise RuntimeError(f"expected one {name} dimension, found {len(matches)}")
    annotation = _early_bound(matches[0], "IAnnotation")
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    display.ArrowSide = 1  # swDimArrowsOutside
    display.SetSecondArrow(False, False)
    display.LeaderVisibility = 3  # swLeaderLineNone; keep only the rim arrow
    if (
        int(display.ArrowSide) != 1
        or bool(display.GetUseDocSecondArrow())
        or bool(display.GetSecondArrow())
        or int(display.LeaderVisibility) != 3
    ):
        raise RuntimeError(f"{name} did not keep its single outside arrow")


def _pattern_notch_reference(adapter: Any, annotations: list[Any]) -> Any:
    """Print the seed-gap-to-kerf 90 degrees as a reference, (90°).

    The kerf is sawn into a root the tooth indexing already cut, so the
    angle has nothing separate to inspect (dt_cylinder_gear_spec).  The
    part leaves the driven dimension untoleranced; it prints (90°) through
    main's prefix/suffix reference form: at f68549253 ShowParenthesis read
    True on this angle but rendered "90°".
    """
    matches = [annotation for annotation in annotations
               if dimension_name(adapter, annotation) == "PatternNotchPhase"]
    if len(matches) != 1:
        raise RuntimeError("expected one actual PatternNotchPhase@NotchProfile locator")
    raw_display = matches[0].GetSpecificAnnotation()
    if raw_display is None:
        raise RuntimeError("pattern-to-CAM-notch locator has no display dimension")
    display = _early_bound(raw_display, "IDisplayDimension")
    raw_dimension = display.GetDimension2(0)
    if raw_dimension is None:
        raise RuntimeError("pattern-to-CAM-notch locator has no model dimension")
    dimension = _early_bound(raw_dimension, "IDimension")
    name = dimension.FullName
    if (type(name) is not str or not name.startswith("PatternNotchPhase@NotchProfile@")
            or int(display.Type2) != 3 or int(dimension.DrivenState) != 1
            or not math.isclose(abs(float(dimension.SystemValue)),
                                math.radians(PATTERN_NOTCH_REF_ANGLE_DEG), abs_tol=1e-8)):
        raise RuntimeError("pattern-to-CAM-notch locator is not the actual driven 90-degree angle")
    if int(dimension.GetToleranceType()) != 0:  # swTolNONE
        raise RuntimeError("pattern-to-CAM-notch reference carries a tolerance")
    return set_reference_dimension(adapter, matches[0], label="pattern-to-CAM-notch reference")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open cylinder-gear source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "Gear Data",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Gear Data",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter,
        property_view=PART_STEM,
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        unit=part_drawing_unit("dt-cylinder-gear"),
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Cylinder Gear Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "cylinder gear; integral eccentric cam; brass; 120T",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=VIEW_SCALE)
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=VIEW_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=VIEW_SCALE)

    detail = _notch_detail(adapter, front)
    set_hidden_lines_visible(adapter, detail)
    # HLV changes remain pending until Windows repaints. This documented view
    # barrier makes the new display geometry available synchronously to import.
    _early_bound(detail, "IView").UpdateViewDisplayGeometry()
    source_model = _early_bound(
        _early_bound(front, "IView").ReferencedDocument, "IModelDoc2"
    )
    original_notch = {
        name: _notch_dimension_state(source_model.Parameter(f"{name}@NotchProfile"))
        for name in NOTCH_DETAIL_DIMENSIONS
    }
    # Author the notch dimensions directly in their final view before any
    # parent-view import can claim them or leave deleted-display history.
    curate_view_dimensions(
        adapter, detail, keep=NOTCH_DETAIL_DIMENSIONS, view_label="notch detail"
    )
    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    right_annotations = curate_view_dimensions(
        adapter, right, keep=RIGHT_KEEP, view_label="right"
    )
    detail_annotations = _check_notch_dimensions(
        adapter, front, right, detail, original_notch
    )
    annotations = [*front_annotations, *right_annotations, *detail_annotations]
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    # Every place the part authored (drawing-simplicity-policy.md `How the repository implements the guidelines`) must have survived the
    # import: a dimension that fell back to the sheet default would print a
    # band nobody specified.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    _pattern_notch_reference(adapter, annotations)
    # Keep the controlled face-width value while moving only its text outside
    # the side-view extension lines; the offset leader returns to the dimension.
    offset_dimension_text(
        adapter,
        right_annotations,
        {"FaceWidth": FACE_WIDTH_TEXT},
    )
    _leader_outside_arrow(adapter, front_annotations, "CamDia")
    overall_annotations = [
        annotation
        for annotation in right_annotations
        if dimension_name(adapter, annotation) == "OverallThickness"
    ]
    if len(overall_annotations) != 1:
        raise RuntimeError("expected one overall (stacking) thickness dimension")
    overall_display = _early_bound(
        overall_annotations[0].GetSpecificAnnotation(), "IDisplayDimension"
    )
    # Keep the stacking requirement with the toleranced nominal in the linear
    # dimension's primary text.  Its callout-above slot did not render in the
    # native export (the former cam-thickness fit callout).
    overall_prefix = f"{STACK_FIT_CALLOUT}\n"
    overall_display.SetText(1, overall_prefix)

    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to cam-side front view")

    # Face width and the overall (stacking) thickness are controlled; the cam
    # thickness between them is their difference, a checked REFERENCE between
    # the cam's two physical rims.
    cam_reference = _cam_thickness_reference(adapter, right)
    cam_reference.ShowParenthesis = True
    if not cam_reference.ShowParenthesis:
        raise RuntimeError("cam thickness was not shown as reference")

    bore_edge = visible_circle_edge(adapter, front, BORE_DIA)
    # Leader attaches at the bore's 225-degree point and runs down-left. The
    # 135-degree route crossed the <MOD-DIAM>30.60 cam diameter line (its lower
    # end sits at sheet (0.085, 0.271)); everything below the bore axis is clear
    # of that dimension and of the eccentricity dimension to its right.
    add_surface_finish(
        adapter,
        front,
        symbol_xy=(0.030, 0.240),
        control=surface_finish_by_key(SURFACE_FINISHES, "cylinder_gear_bore"),
        label="cylinder gear bore finish",
        entity=bore_edge,
        leader_attach_xy=_project_mm(
            adapter,
            front,
            (
                -BORE_DIA / (2.0 * math.sqrt(2.0)),
                -BORE_DIA / (2.0 * math.sqrt(2.0)),
                0.0,
            ),
            label="bore finish leader attachment",
        ),
        char_height=0.0025,
    )

    # The follower finish belongs on the cam's cylindrical flank, which the
    # cam-side front view prints edge-on as the cam circle; it attaches at the
    # circle's 45-degree point.  In the side view the flank sits between
    # OverallThickness's extension lines (x 199.7/210.3 up to y 347), so its
    # leader crossed one (leader-crosses-line).  This leader runs right over
    # the gear teeth to the symbol below the notch-phase callout rows.
    cam_flank = _project_mm(
        adapter,
        front,
        (
            CAM_DIA / (2.0 * math.sqrt(2.0)),
            ECCENTRICITY + CAM_DIA / (2.0 * math.sqrt(2.0)),
            OVERALL_THICKNESS,
        ),
        label="cam follower flank",
    )
    add_surface_finish(
        adapter,
        front,
        edge_xy=cam_flank,
        symbol_xy=CAM_FINISH_SYMBOL,
        control=surface_finish_by_key(SURFACE_FINISHES, "cam_follower"),
        label="cam follower finish",
        leader_attach_xy=cam_flank,
        char_height=0.0025,
    )

    add_property_linked_note(adapter, "Gear Data", *GEAR_DATA_POS, char_height=0.0025)
    # Rule 9 (show internal shape in solid lines): the bore is a standard
    # hole its callout defines, so the parent views carry no hidden lines
    # (the kerf detail keeps its own mode); the isometric is reset too
    # before the finalizer shades it (PR #1436).
    for view in (front, right, iso):
        set_hidden_lines_removed(adapter, view)
    # Check the complete native requirement after all annotation formatting.
    drawing_model.EditRebuild3()
    drawing_model.GraphicsRedraw2()
    if str(overall_display.GetText(1) or "") != overall_prefix:
        raise RuntimeError("overall thickness stacking text did not persist")
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Cylinder Gear Manufacturing Drawing",
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
