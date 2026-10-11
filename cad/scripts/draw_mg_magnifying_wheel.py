r"""Create the curated machinist drawing for the magnifying wheel.

A Ø100 cast-iron spider: six tapered spokes, a grooved rim, a Ø25 boss with
the Ø14.5 drum spigot, a reamed axle bore and two wire-tie holes.  The wheel
axis is local +Z, so the FRONT view is the face (rim, spokes, fillets, bore,
ties) and the RIGHT view is the side elevation carrying the hub profile, the
groove and the axial widths.  Every size rides the part's marked dimensions;
only the rim's axial width is added on the sheet.

Run with SolidWorks open::

    uv run python cad\scripts\draw_mg_magnifying_wheel.py mg-magnifying-wheel
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

import _telemetry
from _check import check
from _com import _early_bound
from _paths import CAD_ROOT
from _session import run_build
from _drawing_common import (
    DrawingOutputs,
    add_edge_dimension,
    add_property_linked_note,
    assert_dimension_measures,
    assert_imported_precision,
    curate_view_dimensions,
    finalize_drawing,
    model_points_in_view,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    scan_view_edges,
    set_dimension_callouts,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    stamp_drawing_summary,
)
from _drawing_leaders import (
    assert_leaders_clear,
    dimension_segments,
    set_near_side_diameter,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _layout_geometry import Box, estimate_text_box
from mg_magnifying_wheel_geom import HUB_BACK_Z, HUB_FRONT_Z, SPOKE_X0
from mg_magnifying_wheel_spec import (
    BORE_DIA,
    CAST_ROUND_R,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    HUB_DIA,
    HUB_FILLET_R,
    RIM_AXIAL,
    RIM_FILLET_R,
    RIM_INNER_DIA,
    RIM_OUTER_DIA,
    TIE1_CLOCK_DEG,
    TIE1_R,
    TIE2_CLOCK_DEG,
    clock_to_local_deg,
    fillet,
)
from solidworks_mcp.adapters.solidworks.drawing import dimension_name, place_view


SPEC = DRAWINGS_BY_NAME["mg_magnifying_wheel"]
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
FRONT_CENTER = (0.125, 0.150)
RIGHT_CENTER = (0.255, 0.150)
# The isometric stands right of the side view's Ø14.5 text, ISO_CLEAR off it.
ISO_CENTER = (0.367, 0.150)
ISO_CLEAR = 0.005

_RIM_R = RIM_OUTER_DIA * SHEET_SCALE[0] / 2000.0

DRAWING_PRECISION_BY_NAME = {
    name: digits
    for names in DRAWING_PRECISION.values()
    for name, digits in names.items()
}

# Face view.  The sheet's front view is the model's XY plane at 1:1 (sheet x
# = model x), so each text point below is derived from the feature it names.
# Every text sits in a window between the spokes (spokes at 0, 60, ... deg),
# and no leader or shoulder may cross another's line (policy rule 8).  Farm
# run 7 (396077c3e) failed on exactly that: the native Ø100 and Ø88 lines
# ran rim to rim through the centre, so the Tie1Y and SpokeRootWidth
# shoulders under them crossed them.  The three diameters now take one arrow
# on their near rim (set_near_side_diameter), so nothing but the bore's own
# short leader enters the face.
#
# A dimension's position is its text block's mid-height above the point its
# leader or shoulder meets (run 7 readback: the one-line Tie1Y shoulder ran
# 2.8 mm under its point, the two-line SpokeRootWidth one 5.6 mm), and its
# text runs away from the feature it measures.
_TEXT_LINE = 0.0056
# A leadered Ø callout's shoulder starts this far (mm) left of its point, and
# its stacked tolerance tops out this far over it (run 8 readback).
_CALLOUT_SHOULDER_LEFT = 15.3
_CALLOUT_ABOVE = 6.3


def _face(x_mm: float, y_mm: float) -> tuple[float, float]:
    """A model XY point (mm) on the sheet (m)."""
    return (
        FRONT_CENTER[0] + x_mm * SHEET_SCALE[0] / 1000.0,
        FRONT_CENTER[1] + y_mm * SHEET_SCALE[0] / 1000.0,
    )


def _polar(origin_mm: tuple[float, float], bearing_deg: float, reach_mm: float):
    """The model point ``reach_mm`` from ``origin_mm`` along ``bearing_deg``."""
    bearing = math.radians(bearing_deg)
    return (
        origin_mm[0] + reach_mm * math.cos(bearing),
        origin_mm[1] + reach_mm * math.sin(bearing),
    )


def _over(attach_mm: tuple[float, float], lines: int) -> tuple[float, float]:
    """The text point whose ``lines``-line block stands on ``attach_mm``."""
    x, y = _face(*attach_mm)
    return (x, y + lines * _TEXT_LINE / 2.0)


_HUB_FILLET_CENTRE = fillet(HUB_DIA / 2.0, HUB_FILLET_R, outside=True)["centre"]
_RIM_FILLET_CENTRE = fillet(RIM_INNER_DIA / 2.0, RIM_FILLET_R, outside=False)["centre"]
_TIE1 = _polar((0.0, 0.0), clock_to_local_deg(TIE1_CLOCK_DEG), TIE1_R)
# TIE 2's angle is driven between its radial axis (outward at 223 deg) and the
# horizontal inner end, where the axis enters the rim bore; its text reads the
# same acute 43 deg in the sector opposite the sketch's, [0, 43] deg from that
# inner point, which opens into the 180-240 window instead of out across the
# rim and the hole's Ø.
_TIE2_OUTWARD = clock_to_local_deg(TIE2_CLOCK_DEG) % 360.0
_TIE2_INNER = _polar((0.0, 0.0), _TIE2_OUTWARD, RIM_INNER_DIA / 2.0)
_TIE2_ANGLE_SECTOR = (0.0, _TIE2_OUTWARD - 180.0)
FRONT_KEEP = {
    # Near-side, one arrow each: Ø100 up-left on the OD, clear of everything;
    # Ø88 straight up the 60-120 window to the rim bore; the bore up-left
    # along the 120-180 window's bisector to its rim.
    "RimOuterDiaDim": _over(_polar((0.0, 0.0), 125.0, RIM_OUTER_DIA / 2.0 + 35.0), 1),
    "RimInnerDiaDim": _over(_polar((0.0, 0.0), 90.0, RIM_OUTER_DIA / 2.0 + 13.2), 1),
    "BoreDiaDim": _over(_polar((0.0, 0.0), 150.0, RIM_OUTER_DIA / 2.0 + 16.0), 2),
    # The R3 (concave, inside the 0-60 window) on its centre's 45 deg ray;
    # the R4 (convex, from outside the rim) on its centre's -3 deg ray, past
    # the OD and above the tip width's extension lines.
    "HubFilletR": _over(_polar(_HUB_FILLET_CENTRE, 45.0, 14.0), 2),
    "RimFilletR": _over(_polar(_RIM_FILLET_CENTRE, -3.0, 26.0), 2),
    # Each spoke width beside its own end, its text down into the 300-360
    # window: the root's line inside the hub fillets' feet, the tip's outside
    # the rim, so neither's extension lines reach the other's line.
    "SpokeRootWidth": _over((SPOKE_X0 + 4.5, -22.0), 2),
    "SpokeTipWidth": _over((RIM_OUTER_DIA / 2.0 + 3.0, -22.0), 2),
    # TIE 1's 9.85 between its own extension lines, left of the axis in the
    # 180-240 window, clear of the bore and tie centre marks: a quarter line
    # under mid-span, so the block stays between the lines whether its point
    # reads as the block's middle or (inside the lines) its bottom.
    "Tie1Y": _face(-17.0, _TIE1[1] / 2.0 - _TEXT_LINE * 1000.0 / 4.0),
    # The two tie Ø callouts hang off the face, the block's leader from its
    # shoulder's near end (the shoulder runs 7.3 mm under the point).  Run 8
    # put TIE 1's block across its own sloped leader in the 240-300 window:
    # now below the wheel, its top 3.2 mm under the OD, the shoulder starting
    # 2 mm right of the hole, so the leader drops near-vertically clear of
    # the text.
    "Tie1HoleDia": _face(
        _TIE1[0] + 2.0 + _CALLOUT_SHOULDER_LEFT,
        -RIM_OUTER_DIA / 2.0 - 3.2 - _CALLOUT_ABOVE,
    ),
    "Tie2Angle": _face(*_polar(_TIE2_INNER, sum(_TIE2_ANGLE_SECTOR) / 2.0, 10.0)),
    # TIE 2's Ø is a linear width across the radial hole: its extension lines
    # run out along the hole's axis to the dimension line's foot, ~1 mm past
    # the text's projection onto the axis.  Run 8 hung the block ON that foot,
    # so both lines ran through it: now 18 mm to the axis's upper side, past
    # the OD, the block's projection 66 mm out along the axis, and a one-line
    # "TIE 2" (the hole's run, groove to rim bore, is in the notes).
    "Tie2HoleDia": _face(
        *_polar(_polar((0.0, 0.0), _TIE2_OUTWARD, 66.0), _TIE2_OUTWARD - 90.0, 18.0)
    ),
}
# Near-side leaders: no segment of these comes nearer the axis than half the
# circle's radius, and each ends on its own circle (sheet metres; a reading
# outside the band means the ink is not in sheet space).
NEAR_SIDE_DIAMETERS = {
    "RimOuterDiaDim": RIM_OUTER_DIA,
    "RimInnerDiaDim": RIM_INNER_DIA,
    "BoreDiaDim": BORE_DIA,
}
# The template centre-marks each hole as the view is placed, so an explicit
# AutoInsertCenterMarks2 printed a second, identical mark (run 7: two
# duplicate-annotation findings; sm_knife_mount #913).  Each mark keeps its
# cross only: the extended lines ran 47.5 mm along the axes, through the
# bore's Ø text and every window's dimension.  The face view is 1:1, so the
# mark's model-length arm is its sheet length.
CENTRE_MARK_ARM = 0.0025
_CENTER_MARK_ANNOTATION = 13  # swAnnotationType_e.swCenterMarkSym
_MARK_ON_HOLE = 0.0005
# Side view: sheet right = model -Z (the pen side, where the spigot stands).
# The view centres on the part's axial extent, the hub's back face to its
# spigot end, so each hub face's sheet x follows from its z.
_SIDE_MID_Z = (HUB_BACK_Z + HUB_FRONT_Z) / 2.0


def _side_x(z_mm: float) -> float:
    """The side view's sheet x (m) of the model plane at ``z_mm``."""
    return RIGHT_CENTER[0] + (_SIDE_MID_Z - z_mm) * SHEET_SCALE[0] / 1000.0


# Run 7 printed "9.85 ±0.05" (10 characters) 24.5 mm wide.
_TEXT_CHAR = 0.00245
# Text kept this far off any extension line it does not own, past the half
# text height inside which the audit gates a crossing (DIM_CROSSING_TEXT_HEIGHTS).
_TEXT_OFF_LINE = 0.004


def _beside(face_x: float, side: int, chars: int, y: float) -> tuple[float, float]:
    """A ``chars``-wide text centred ``side`` (-1 left, +1 right) of ``face_x``."""
    return (face_x + side * (_TEXT_OFF_LINE + chars * _TEXT_CHAR / 2.0), y)


# Side-view text points (run 8 readback): a size whose text stands between
# its extension lines prints it centred on the point, breaking its line round
# it; one whose text stands outside hangs it off the line's end, centred on
# the point (axial) or running from the point away from the view (diameters).
# A one-line text's point stands _ONE_LINE_UP over its dimension line, a
# stacked tolerance's _STACK_UP; the line runs 6.3 mm past the extension line
# away from its text.
_ONE_LINE_UP = 0.0028
_STACK_UP = 0.0045
# Run 8 printed "Ø25.00 +0.1/-0.1" 30.1 mm wide.
_DIA_TEXT_HALF = 0.0151
# Run 8 stacked all three diameters right of the view, where the Ø14.5 printed
# over the isometric and the Ø97.6's line ran through it, and the axial sizes
# below the hub, where the 4.0's line crossed three hub extension lines.
#
# Left of the view, the Ø25 and the Ø97.6 print BETWEEN their extension
# lines: the Ø25 centred on the hub, its line _TEXT_OFF_LINE plus half its
# text left of the back face; the Ø97.6 up between the hub and the rim bore,
# its line as far again left of the Ø25's, so neither line nor text reaches
# the other's, and the hub's extension lines stop short of the Ø97.6's line.
_HUB_DIA_X = _side_x(HUB_BACK_Z) - _TEXT_OFF_LINE - _DIA_TEXT_HALF
_GROOVE_DIA_X = _HUB_DIA_X - _DIA_TEXT_HALF - _TEXT_OFF_LINE
# Above the hub, two rows left of the back face, the spokes' 4.0 under the
# rim's 8.00 (added below): both lines run from the part leftward to their
# text, above the hub's extension lines and under the rim bore.
_SPOKE_ROW = RIGHT_CENTER[1] + HUB_DIA / 2000.0 + 0.0055
_RIM_WIDTH_ROW = _SPOKE_ROW + 0.010
# The hub's three axial sizes below the rim, one row each, each text OUTSIDE
# its span so no extension line runs through a text (run 7: four
# extension-through-own-text findings): HubBackZ ("7.09") left of the back
# face; SpigotLength ("9.00 +0.10/0") right of the spigot end; the overall
# HubLength ("19.60 ±0.10") left of the back face under HubBackZ, clear of
# "SIDE VIEW SCALE 1:1" under it (run 8 printed it right, 3.4 mm off it).
_HUB_ROWS = tuple(RIGHT_CENTER[1] - _RIM_R - 0.007 * row for row in (1, 2, 3))
RIGHT_KEEP = {
    "HubDia": (_HUB_DIA_X, RIGHT_CENTER[1]),
    "GrooveBottomDia": (_GROOVE_DIA_X, RIGHT_CENTER[1] + 0.035),
    # Right of the view only the spigot's Ø, its text from 7.2 mm past the
    # spigot end, above the spigot: ISO_CLEAR off the isometric, proven at
    # build (_assert_text_off_iso).
    "SpigotDia": (_side_x(HUB_FRONT_Z) + 0.0072, RIGHT_CENTER[1] + 0.016),
    "SpokeAxial": _beside(_side_x(HUB_BACK_Z), -1, 3, _SPOKE_ROW + _ONE_LINE_UP),
    "HubBackZ": _beside(_side_x(HUB_BACK_Z), -1, 4, _HUB_ROWS[0] + _ONE_LINE_UP),
    "SpigotLength": _beside(_side_x(HUB_FRONT_Z), 1, 12, _HUB_ROWS[1] + _STACK_UP),
    "HubLength": _beside(_side_x(HUB_BACK_Z), -1, 11, _HUB_ROWS[2] + _STACK_UP),
    # The groove's R up right, its leader down-left onto the groove clear of
    # the rim's front corner, so the Ø97.6's extension line, which leaves the
    # groove bottom leftward, runs nowhere near its arrow.
    "GrooveR": (RIGHT_CENTER[0] + 0.020, RIGHT_CENTER[1] + 0.060),
    # The rim-bore round's callout right, between the spigot's Ø and the
    # groove's R, its shoulder 10 mm under the rim bore: the Ø97.6 holds the
    # left (run 8 hung it there).
    "CastRoundR": (RIGHT_CENTER[0] + 0.0292, RIGHT_CENTER[1] + 0.0413),
}
DIMENSION_CALLOUTS = {
    "BoreDiaDim": "THRU - REAM",
    "SpokeRootWidth": "6X ROOT",
    "SpokeTipWidth": "6X TIP",
    "HubFilletR": "12X",
    "RimFilletR": "12X",
    "CastRoundR": "2X RIM BORE EDGES",
    "Tie1HoleDia": "THRU - TIE 1",
    "Tie2HoleDia": "TIE 2",
}

RIGHT_HALF_RIM = RIM_AXIAL * SHEET_SCALE[0] / 2000.0
# The rim's axial width spans its two OD corner circles (r = RIM_OUTER_DIA/2 at
# z = +/-RIM_AXIAL/2; the rim is extruded both ways off the mid-plane). Edge-on
# in the side view each is a vertical line; the coordinate picks ride their
# mid-span, between the rim-bore round's tangent (r 45) and the OD (r 50), the
# only band where the OD circle stands alone on that line.
_RIM_FACE_MID_Y = (RIM_INNER_DIA / 2.0 + CAST_ROUND_R + RIM_OUTER_DIA / 2.0) / 2000.0
_RIM_AXIS = (0.0, 0.0, 1.0)


def _near_side_diameters(
    adapter: Any, annotations: list[Any], *, axis: tuple[float, float]
) -> None:
    """One arrow on each face-view diameter's near rim, proven off the face."""
    named = {dimension_name(adapter, annotation): annotation for annotation in annotations}
    for name in NEAR_SIDE_DIAMETERS:
        set_near_side_diameter(named[name], f"wheel {name}")
    rebuild_drawing(adapter, label="wheel near-side diameters")
    radii = {
        name: diameter * SHEET_SCALE[0] / 2000.0
        for name, diameter in NEAR_SIDE_DIAMETERS.items()
    }
    assert_leaders_clear(
        {name: dimension_segments(named[name]) for name in NEAR_SIDE_DIAMETERS},
        centre=axis,
        keep_out={name: radius / 2.0 for name, radius in radii.items()},
        lands_within={name: (0.8 * radius, 1.2 * radius) for name, radius in radii.items()},
        label="wheel near-side diameters",
    )


def _trim_centre_marks(
    adapter: Any, view: Any, holes: dict[str, tuple[float, float]]
) -> None:
    """Keep the template's centre marks as bare crosses, one per hole, and
    fail on a second mark at any hole or a mark at no hole."""
    marks = [
        _early_bound(annotation, "IAnnotation")
        for annotation in _early_bound(view, "IView").GetAnnotationsByType(
            _CENTER_MARK_ANNOTATION
        )
        or ()
    ]
    for annotation in marks:
        mark = _early_bound(annotation.GetSpecificAnnotation(), "ICenterMark")
        mark.UseDocDisplaySettings = False
        mark.ShowLines = False
        mark.Size = CENTRE_MARK_ARM
    rebuild_drawing(adapter, label="trim wheel centre marks")
    marked = []
    for annotation in marks:
        mark = _early_bound(annotation.GetSpecificAnnotation(), "ICenterMark")
        if bool(mark.UseDocDisplaySettings) or bool(mark.ShowLines):
            raise RuntimeError("a wheel centre mark kept its extended lines")
        data = _early_bound(annotation.GetDisplayData(), "IDisplayData")
        lines = [
            tuple(float(value) for value in data.GetLineAtIndex2(index))
            for index in range(int(data.GetLineCount()))
        ]
        if not lines:
            raise RuntimeError("a wheel centre mark draws no line")
        xs = [value for line in lines for value in (line[4], line[7])]
        ys = [value for line in lines for value in (line[5], line[8])]
        centre = ((min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0)
        marked.append(
            next(
                (
                    name
                    for name, hole in holes.items()
                    if math.dist(hole, centre) <= _MARK_ON_HOLE
                ),
                f"no hole at {centre}",
            )
        )
    if marked.count("bore") != 1 or marked.count("tie 1") > 1 or set(marked) - set(holes):
        raise RuntimeError(f"expected one centre mark per wheel hole, found {marked}")
    _telemetry.info(f"wheel centre marks: {sorted(marked)}")


def _assert_text_off_iso(adapter: Any, annotations: list[Any], iso: Any) -> None:
    """Fail when any dimension's text block comes within ISO_CLEAR of the
    isometric's outline (run 8 printed the side view's Ø14.5 over the iso
    wheel).  Every text item a dimension draws (value, stacked tolerance,
    callout lines) is boxed by the layout audit's estimator, as
    draw_dt_cone_gear_shaft does: no API returns a text's width."""
    iso_box = Box(*(float(value) for value in _early_bound(iso, "IView").GetOutline()))
    nearest = math.inf
    crowding = []
    for annotation in annotations:
        annotation = _early_bound(annotation, "IAnnotation")
        label = dimension_name(adapter, annotation) or "unnamed dimension"
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        data = _early_bound(display.GetDisplayData(), "IDisplayData")
        for index in range(int(data.GetTextCount())):
            anchor = [float(value) for value in data.GetTextPositionAtIndex(index)]
            reference = int(data.GetTextRefPositionAtIndex(index))
            box = estimate_text_box(
                str(data.GetTextAtIndex(index) or ""),
                anchor=(anchor[0], anchor[1]),
                height=float(data.GetTextHeightAtIndex(index)),
                reference=reference if 0 <= reference <= 5 else 0,
                angle=float(data.GetTextAngleAtIndex(index)),
            )
            if box is None:
                continue
            gap = box.gap(iso_box)
            nearest = min(nearest, gap)
            if gap < ISO_CLEAR:
                crowding.append(f"{label} {box.format_mm()}")
    if crowding:
        raise RuntimeError(
            f"dimension text within {ISO_CLEAR * 1000:.0f} mm of the isometric "
            f"{iso_box.format_mm()}: {crowding}"
        )
    _telemetry.info(
        f"wheel dimension text clears the isometric {iso_box.format_mm()} by "
        f"{nearest * 1000:.1f} mm"
    )


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open magnifying-wheel source", await adapter.open_model(str(SOURCE)))
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
            "Section View Note",
            "Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Section View Note",
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
            0: "Magnifying Wheel Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "magnifying wheel; cast-iron spider; six spokes",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(1, 1))
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(1, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 1))
    for view in (iso,):
        set_hidden_lines_removed(adapter, view)
    for view in (front, right):
        set_hidden_lines_visible(adapter, view)

    annotations = [
        *curate_view_dimensions(
            adapter,
            front,
            keep=FRONT_KEEP,
            view_label="front",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
        *curate_view_dimensions(
            adapter,
            right,
            keep=RIGHT_KEEP,
            view_label="right",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
    ]
    # Decimal places (and so the general-tolerance row each dimension claims)
    # are authored on the part; the sheet only proves the import kept them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    axis, tie1 = model_points_in_view(
        adapter,
        front,
        ((0.0, 0.0, 0.0), (_TIE1[0] / 1000.0, _TIE1[1] / 1000.0, 0.0)),
        label="wheel hole centres",
        names=("bore", "tie 1"),
    )
    _near_side_diameters(adapter, annotations, axis=axis)
    _trim_centre_marks(adapter, front, {"bore": axis, "tie 1": tie1})

    # The rim's axial width across the side view, its text left of the rim's
    # back face on its own row (above). The two OD corner circles are
    # selected as native entities: a coordinate hit-test at the corner where
    # each edge-on circle ends on the OD silhouette found no edge on farm run
    # 4 (85a5d462d), and the side view's asymmetric hub (HUB_FRONT_Z..
    # HUB_BACK_Z) means its origin need not sit on RIGHT_CENTER.
    right_edges = scan_view_edges(right, label="wheel right rim corners")
    rim_corners = tuple(
        right_edges.circle_at(
            (0.0, 0.0, z),
            RIM_OUTER_DIA / 2.0,
            axis=_RIM_AXIS,
            label=f"rim OD corner at z={z:+g}",
        ).edge
        for z in (RIM_AXIAL / 2.0, -RIM_AXIAL / 2.0)
    )
    rim_width = add_edge_dimension(
        adapter,
        right,
        p0=(RIGHT_CENTER[0] - RIGHT_HALF_RIM, RIGHT_CENTER[1] + _RIM_FACE_MID_Y),
        p1=(RIGHT_CENTER[0] + RIGHT_HALF_RIM, RIGHT_CENTER[1] + _RIM_FACE_MID_Y),
        text_xy=_beside(
            _side_x(RIM_AXIAL / 2.0), -1, 4, _RIM_WIDTH_ROW + _ONE_LINE_UP
        ),
        label="rim axial width",
        orientation="horizontal",
        entities=rim_corners,
    )
    assert_dimension_measures(
        adapter,
        rim_width,
        expected_mm=RIM_AXIAL,
        label="rim axial width",
        entities=rim_corners,
    )
    rebuild_drawing(adapter, label="wheel dimension layout")
    _assert_text_off_iso(
        adapter,
        [*annotations, _early_bound(rim_width, "IDisplayDimension").GetAnnotation()],
        iso,
    )

    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.075)
    add_property_linked_note(
        adapter, "Section View Note", RIGHT_CENTER[0] - 0.022, 0.075
    )
    add_property_linked_note(
        adapter, "Isometric View Note", ISO_CENTER[0] - 0.030, 0.085
    )

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Magnifying Wheel Manufacturing Drawing",
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
