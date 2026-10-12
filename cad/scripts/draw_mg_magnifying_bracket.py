r"""Create the curated machinist drawing for the magnifying-lever bracket.

The bracket is the black fitting that affixes the Ø6 magnifying lever
(MHA-MG-003) to the summing plate: an extruded COLLAR tube (Ø12 OD, 10 long
about local X) whose bore is the lever's PRESS seat, a rectangular ARM
cantilevering +Z, and a mounting FLANGE whose +Z face butts the summing-plate
front face.  One third-angle set (blind machinist review, mreview09):

- FRONT (the part's ``*Top`` named view: +X right, +Z DOWN): the plan
  rectangles' marked dimensions -- the arm's width, the flange's width and
  banded thickness -- and the collar's length above the collar it measures.
- BOTTOM (``*Front``, under the front view, looking at the mounting face):
  the flange's height, the two mounting holes' coordinates from the flange's
  west end and lower face, and the native counterbore callout; the
  counterbores enter from the -Z face, the FAR SIDE of this view.
- RIGHT SIDE (``*Right`` TURNED so model +Z runs down the sheet and pinned by
  projection at the front view's origin height): the collar end-on with its
  OD and banded bore, and, from the part's blanked ``ArmSection`` witness,
  the arm's thickness and its lower face from the bore axis (controlling) and
  from the flange's hole-datum face (reference), the flange's mounting face
  and the arm's end from the bore axis -- one datum chain for the bore axis.

Run with SolidWorks open::

    uv run python cad\scripts\draw_mg_magnifying_bracket.py mg-magnifying-bracket
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import dimension_name, place_view

from _check import check
from _com import _early_bound
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    stamp_drawing_summary,
)
from _drawing_dimension_import import curate_view_dimensions
from _drawing_dimensions import set_dimension_callouts, set_reference_dimension
from _drawing_edges import scan_view_edges
from _drawing_hidden_sketches import curate_view_dimensions as curate_hidden_dimensions
from _drawing_hole_callout import add_native_hole_callout
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _paths import CAD_ROOT
from _session import run_build
import _telemetry
from magnifying_bracket_joint_layout import (
    BRACKET_HOLE_POINTS,
    CLEARANCE_DIA,
    SIDE_PLATE_Z,
)
from mg_lever_press_fit_geom import COLLAR_BORE_DIA
from mg_magnifying_bracket_spec import DRAWING_DIMENSIONS
from mg_magnifying_lever_geom import COLLAR_HALF_LEN

SPEC = DRAWINGS_BY_NAME["mg_magnifying_bracket"]
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
# The sheet's FRONT view is the part's *Top named view (viewer +Y): sheet
# x = 134 + X, y = 206.15 - Z mm (retry09 native audit, 20261012T124257186Z).
# The BOTTOM view (*Front, viewer +Z) sits under it in third angle: its
# x = 134 + X too.  The *Right named view is placed, then turned and pinned
# into projection by _project_side_view; SIDE_CENTER only drops it nearby.
FRONT_CENTER = (0.115, 0.180)
BOTTOM_CENTER = (0.115, 0.110)
SIDE_CENTER = (0.228, 0.180)
ISO_CENTER = (0.340, 0.130)
# Where the side view's bore axis prints (x) and the front view's origin
# height (y): the collar's Z -6..6 and the arm's end at Z 58.3 centre the
# front view's outline 26.15 mm below the origin.  The build measures the
# origin in both views and pins the side view to the FRONT view's reading;
# these constants only place the side view's texts.
SIDE_AXIS_X = 0.228
FRONT_ORIGIN_Y = FRONT_CENTER[1] + 0.02615

# The three plan dimensions ride the FRONT view (both extruded rectangles lie
# on the part's Top plane), as does the collar's mid-plane extrude length
# (along X).  +Z runs DOWN the front view (the collar, Z -6..6, sits at its
# top, y 200..212 mm; the arm's end, Z 58.3, at its bottom, y 147.8 mm).  The
# collar's length therefore reads above the collar, its witnesses 4 mm long:
# below the view (v41) they ran the full height of the part.  That text sits
# right of the collar's x 139 mm witness, and the flange width's text moves
# left so the collar length's outside arrows clear it.  Its three rows
# (retry09, requested (155, 224) mm) print centred on x 155 mm at y 215.7,
# 221.2 and 226.8 mm, the line at the lowest row's baseline running from the
# collar's x 129 mm end to the widest row's far end (x 175.8 mm); the band
# (+0.00/-0.05, a 15.7 mm stack beside "10.00") widens the value row to
# ~27 mm, still inside "ALONG BORE AXIS" (41.5 mm).
# A HORIZONTAL dimension's rows requested beyond its span print centred on
# the requested x, and its dimension line runs on under the lowest row to that
# row's far end (retry09 native audit: "10.00 / ARM WIDTH" requested at x 88
# mm beside the arm, y 170 mm, printed over x 75..101 mm with the flange
# width's witness at x 91 mm through both rows).  The arm width therefore
# reads BELOW the arm's end (y 147.85 mm), between the aligned front and
# bottom views, hung left of its span (x 129..139 mm): rows over x ~100..126
# mm, y 133..142.5 mm, the dimension line at y 132.4 mm and its witnesses
# dropping through air from the arm's end; 3 mm of air to its own witness,
# 11 mm over the bottom view's top (y 121.9 mm) and clear of the flange
# depth's column at x 89 mm.  The flange depth's block sits a text height
# plus under the flange width's (its value row's top at y 204.5 mm, the
# width's callout row's bottom at 211.4 mm; the audit reads two blocks within
# a text height as one dimension).  The arm's 54.30 length from its buried
# start (Z 4, inside the collar) is gone: the arm's end is located from the
# bore axis in the side view, the same datum as the mounting face.
FRONT_KEEP = {
    "ArmWidth": (0.113, 0.138),
    "FlangeWidth": (0.104, 0.216),
    "FlangeDepth": (0.089, 0.200),
    "CollarLen": (0.155, 0.224),
}
# The flange's height, right of the bottom view (x 148 mm, in its 12.7 mm
# span: text centred on the column, breaking the line, arrows outside).
BOTTOM_KEEP = {"FlangeHeight": (0.148, 0.110)}
# The mounting holes' coordinates on the bottom view (viewer +Z: x = 134 + X,
# y = 110 + Y mm; the flange's west end at x 91 mm, its lower face at y 103.65
# mm, the holes at x 95 and 108.7 mm, y 110 mm).  Each coordinate sketch
# chain runs west corner -> hole station on the lower face -> hole, so the X
# witnesses drop from the lower face (y 102.65 mm) and the holes' row reads
# from the lower face up to the hole.  The two X coordinates share the
# west-end baseline and stack under the view, 8 mm apart, the shorter nearer
# the part, hung LEFT of that baseline (horizontal rule, retry09: a lone row
# prints centred on the requested x with its bottom on the dimension line,
# 2.78 mm under the requested y, and the line runs from the row's far end
# through both witnesses to an outside-arrow tail 6.4 mm past the far one):
# " 4.00 ±0.05 " (24.5 mm) over x 62.75..87.25 mm on the line at y 89 mm, its
# tail to x 101.4 mm; " 17.70 ±0.05 " (27.1 mm) over x 61.45..88.55 mm on the
# line at y 81 mm, its tail to x 115.1 mm; 4.5 mm of air between the rows and
# 11.5 mm over the manufacturing notes' top row (y 69.5 mm).  The holes' row
# from the lower face (6.35 mm, too short a span for its row: requested AT
# its witness it printed centred on its own column, retry09) hangs ABOVE and
# left of its column at x 80 mm, its shoulder 2.78 mm under the requested y:
# the row over x 55.5..80 mm on a shoulder at y 113.8 mm (its box y 114.7..
# 118.3 mm, 4.7 mm over the holes' row witness); the column's outside-arrow
# tail ends 6.4 mm under the lower face, at y 97.25 mm, 3.75 mm over the
# 4.00's row box.  The holes' row witness runs over the flange from 5.4 mm
# past the hole (x 100.4 mm, retry09's measured overrun) to x 79 mm.
BOTTOM_HOLE_KEEP = {
    "MountingX0": (0.075, 0.0918),
    "MountingX1": (0.075, 0.0838),
    "MountingY0": (0.080, 0.1166),
}
# The collar's end-on circles: the annulus sketch lies on the part's Right
# plane, so its two diameters import to the side view, whose collar centre is
# the pinned origin (SIDE_AXIS_X, FRONT_ORIGIN_Y) = (228, 206.15) mm.  A
# diameter's block prints centred on the requested x, its value row's bottom
# at the requested y (1 mm higher with a tolerance stack), the callout rows
# 5.6 mm apart under it (the first 4.5 mm under a toleranced value), its
# elbow 1.6 mm past the lowest row's near end on that row's baseline, and
# the diameter line runs from the elbow through the centre to the far rim
# (retry09: "COLLAR OD" requested at (284, 196) mm printed over x 270.4..
# 297.7 mm, y 190.4..199.5 mm, its elbow at (268.8, 190.4) mm; the bore's
# three rows requested at (226, 147) mm printed y 136.9..156.1 mm, the
# elbow at (258.3, 136.9) mm).  Both read ABOVE the collar, the OD on the
# left ("COLLAR OD" 27.3 mm over x 189.2..216.5 mm, y 219..222.5 mm, "Ø12.00"
# over it, the elbow at (218.05, 219) mm), the bore on the right ("REAM OR
# BORE: PRESS SEAT" 61.5 mm over x 241.6..303.1 mm, y 224.6..228.1 mm, "FOR
# MHA-MG-003 LEVER" under it at y 219 mm, the banded value over it to y
# 238.2 mm, the elbow at (240, 219) mm): each leader runs steeply down to
# the centre, so it meets the origin's witnesses (y 206.15 mm, which start
# 1 mm either side of the origin) only at the origin itself, between their
# ends, and the rows sit 6.9 mm over the collar's top (y 212.15 mm), 12.8 mm
# over those witnesses, 13 mm right of the front view's collar-length rows
# (x <= 175.8 mm) and clear of the sheet's right.  The two diameter lines
# cross each other at the centre (advisory; two concentric diameters).
SIDE_KEEP = {
    "CollarOd": (SIDE_AXIS_X - 0.0252, FRONT_ORIGIN_Y + 0.0185),
    "CollarBore": (SIDE_AXIS_X + 0.0444, FRONT_ORIGIN_Y + 0.0230),
}
# The arm's section, from the part's ArmSection witness (shown in the side
# view by curate_hidden_dimensions).  Turned into projection, the view's
# sheet-right is model -Y: the arm (Y -3..4.5) spans x 223.5..231 mm, the
# flange edge-on (Y +/-6.35) x 221.65..234.35 mm at y 150.96..154.16 mm (its
# mounting face, Z 55.19, at the bottom), the arm's end at y 147.85 mm, the
# collar's centre at (228, 206.15) mm.  A witness leaves its point 1 mm out
# and runs 1 mm past the dimension line (retry09).
# The two Z stations from the bore axis are VERTICAL, in-span (a text
# requested inside a vertical span prints centred on the column and breaks
# the line: the bottom view's 12.70, retry09), their witnesses running along
# model Y (sheet-horizontal) from their corner and from the origin, the one
# from the origin through the collar's end face to the column; each column
# stands clear of the flange's end by half its widest row plus a text height:
#   - the mounting face, "55.19 / MOUNTING FACE / TO BORE AXIS" (~37 mm), on
#     the LEFT: its seat corner is at Y +6.35, the flange's left end
#     (x 221.65 mm), so its witness continues the mounting face's edge
#     leftward; column x 198 mm, rows x ~179.5..216.5 mm, y ~172..186.6 mm,
#     5.15 mm left of the flange;
#   - the arm's end, "58.30 / ARM END / FROM BORE AXIS" (37.8 mm), on the
#     RIGHT: its corner is on the arm's lower face, Y -3 (x 231 mm), so the
#     witness continues the arm's end edge rightward, 3.1 mm under the
#     mounting face; column x 259 mm, rows x ~240.1..277.9 mm, y ~170.5..
#     185.1 mm, 5.75 mm right of the flange.
# The three across the arm are HORIZONTAL (model Y), hung off their short
# spans below the arm's end, 8 mm apart, their witnesses dropping from the
# arm's end corners (y 146.85 mm) and, for the reference offset, from the
# flange's lower-right corner (234.35, 150.96) mm; a short span's
# outside-arrow tail runs 6.4 mm past its far witness, and the dimension
# line runs on under the hung rows to their far end.  The crossings nesting
# forces are the audit's advisory kind -- no text may be crossed:
#   - the reference offset to the hole-datum face (x 231..234.35 mm)
#     nearest, line y 139 mm, hung RIGHT: "(3.35)" (15.1 mm) over x
#     239.45..254.55 mm, y 139..142.5 mm, 5.1 mm right of the flange's end
#     and 5.35 mm under the arm end's witness (y 147.85 mm), which its own
#     witness crosses at x 234.35 mm (extension over extension); its left
#     tail ends at x 224.6 mm, 1.1 mm right of the thickness' witness;
#   - the lower face from the bore axis (x 228..231 mm), line y 131 mm, hung
#     RIGHT: "3.00" over x 261.45..270.55 mm, y 136.6..140.1 mm, 6.9 mm right
#     of the "(3.35)" row; "FROM BORE AXIS" over x 247.1..284.9 mm, y 131..
#     134.5 mm, 4.5 mm under that row and 9.8 mm left of the isometric's
#     outline (x 294.7 mm); its left tail (to x 221.6 mm) is crossed by the
#     thickness' witness at x 223.5 mm (advisory);
#   - the thickness (x 223.5..231 mm), line y 123 mm, hung LEFT: "7.50" over
#     x 195.45..204.55 mm, y 128.6..132.1 mm, "ARM THICKNESS" (~36.5 mm) over
#     x 181.75..218.25 mm, y 123..126.5 mm, 5.25 mm left of its own witness
#     and 4.5 mm under the 3.00's line; its right tail ends at x 237.35 mm.
# Nothing else sits under the arm's end at x 180..285 mm: the counterbore
# callout's block ends at y 92.3 mm, the isometric starts at x 294.7 mm.
SIDE_SECTION_KEEP = {
    "SeatToAxis": (SIDE_AXIS_X - 0.030, 0.1785),
    "ArmEndFromAxis": (SIDE_AXIS_X + 0.031, 0.177),
    "ArmOffset": (SIDE_AXIS_X + 0.019, 0.1418),
    "ArmBelowAxis": (SIDE_AXIS_X + 0.038, 0.1366),
    "ArmThickness": (SIDE_AXIS_X - 0.028, 0.1286),
}
# Blind-review round 1: the plan values read unattached at a glance -- label
# each with the feature it controls.  The collar's length names its
# direction (machinist review: 10.00 vs the Ø12 read as one feature).
DIMENSION_CALLOUTS = {
    "ArmWidth": "ARM WIDTH",
    "FlangeWidth": "FLANGE WIDTH",
    "FlangeDepth": "FLANGE DEPTH",
    "CollarLen": "COLLAR LENGTH\nALONG BORE AXIS",
}
# The bore names its process (policy rule 6) and the part it seats: the lever.
SIDE_CALLOUTS = {
    "CollarOd": "COLLAR OD",
    "CollarBore": "REAM OR BORE: PRESS SEAT\nFOR MHA-MG-003 LEVER",
}
# The bore axis has ONE datum chain (mreview09 blocker 3: 54.30 from the
# arm's buried start and 55.19 from an unnamed seat face located the collar
# twice): the flange's mounting face and the arm's end are both from the
# bore axis, and the face is named as the one the plate sees.
SECTION_CALLOUTS = {
    "ArmThickness": "ARM THICKNESS",
    "ArmBelowAxis": "FROM BORE AXIS",
    "SeatToAxis": "MOUNTING FACE\nTO BORE AXIS",
    "ArmEndFromAxis": "ARM END\nFROM BORE AXIS",
}
# ArmOffset prints in parentheses: the arm is controlled from the bore axis,
# and its offset from the hole-datum face is that same position, read as
# reference against the flange the machinist can measure.  It is a LINEAR
# reference, so it takes the singular set_reference_dimension: the plural
# helper prefixes every name with the diameter glyph, which printed it as
# "(Ø3.35)" on retry08.
SECTION_REFERENCE = ("ArmOffset",)
# The counterbore callout names the entry side: the bottom view looks at the
# mounting face, and the counterbores enter from the opposite, -Z face.
COUNTERBORE_PROCESS = "DRILL / COUNTERBORE FAR SIDE"

# Third-angle projection of the side view: model +Z (down the front view)
# points down the sheet, model +Y left (the viewer is at +X, the front view's
# right).  Angles are sheet radians, counter-clockwise from sheet +x.
SIDE_DOWN_AXIS = (0.0, 0.0, 1.0)
SIDE_LEFT_AXIS = (0.0, 1.0, 0.0)
PROJECTION_ANGLE_TOL = 1e-6
PROJECTION_TOL_M = 1e-4  # the latch hook's _PIN_TOL_M


def _mounting_rims(bottom: Any) -> list[Any]:
    """The through holes' rims on the mounting face: the bottom view looks
    from +Z, and the counterbores open on the far (-Z) face."""
    edges = scan_view_edges(bottom, label="bracket mounting face")
    return [
        edges.circle_at(
            (point[0], point[1], SIDE_PLATE_Z[1]),
            CLEARANCE_DIA / 2.0,
            axis=(0.0, 0.0, 1.0),
            label=f"bracket mounting hole {index}",
        )
        for index, point in enumerate(BRACKET_HOLE_POINTS)
    ]


def _axis_direction(
    adapter: Any, view: Any, axis_mm: tuple[float, float, float], label: str
) -> tuple[float, float]:
    """Sheet direction (metres) of a model axis in ``view``."""
    origin = model_point_in_view(adapter, view, (0.0, 0.0, 0.0), label=f"{label} origin")
    tip = model_point_in_view(
        adapter, view, tuple(v / 1000.0 for v in axis_mm), label=f"{label} tip"
    )
    return tip[0] - origin[0], tip[1] - origin[1]


def _require_axis_along(
    adapter: Any,
    view: Any,
    axis_mm: tuple[float, float, float],
    sheet_angle: float,
    label: str,
) -> None:
    dx, dy = _axis_direction(adapter, view, axis_mm, label)
    error = math.remainder(math.atan2(dy, dx) - sheet_angle, math.tau)
    if abs(error) > PROJECTION_ANGLE_TOL:
        raise RuntimeError(
            f"{label}: model {axis_mm} points {math.atan2(dy, dx):g} rad on the "
            f"sheet, expected {sheet_angle:g}"
        )


def _project_side_view(adapter: Any, front: Any, side: Any) -> None:
    """Turn the side view into third-angle projection with the front view
    and pin its origin to the front view's origin height.

    ``*Right`` arrives with model +Y up and +Z to the sheet's left (mreview09
    blocker 1: the collar's circle beside an arm running left read as a
    different part).  The turn is measured, not assumed: model +Z is
    projected before and after ``IView::Angle`` (the cradle's ``_turn``), and
    +Y must then point left.  The move is by the origin's projection, read
    back (the latch hook's ``_pin_origin``): the side view's origin lands at
    SIDE_AXIS_X on the FRONT view's measured origin height.
    """
    native = _early_bound(side, "IView")
    dx, dy = _axis_direction(adapter, native, SIDE_DOWN_AXIS, "side view +Z")
    native.Angle = float(native.Angle) - math.pi / 2.0 - math.atan2(dy, dx)
    rebuild_drawing(adapter, label="turn side view")
    _require_axis_along(adapter, native, SIDE_DOWN_AXIS, -math.pi / 2.0, "side view +Z")
    _require_axis_along(adapter, native, SIDE_LEFT_AXIS, math.pi, "side view +Y")
    front_origin = model_point_in_view(
        adapter, front, (0.0, 0.0, 0.0), label="front view origin"
    )
    target = (SIDE_AXIS_X, front_origin[1])
    at = model_point_in_view(adapter, native, (0.0, 0.0, 0.0), label="side view origin")
    position = tuple(float(value) for value in native.Position)
    moved = [position[axis] + target[axis] - at[axis] for axis in range(2)]
    if native.SetViewPosition(double_array(moved), False) is not True:
        raise RuntimeError("failed to move the side view into projection")
    rebuild_drawing(adapter, label="project side view")
    at = model_point_in_view(adapter, native, (0.0, 0.0, 0.0), label="side view origin")
    if math.dist(at, target) > PROJECTION_TOL_M:
        raise RuntimeError(
            f"side view origin sits at ({at[0] * 1000.0:.2f}, {at[1] * 1000.0:.2f}) mm, "
            f"not at ({target[0] * 1000.0:.2f}, {target[1] * 1000.0:.2f}) mm"
        )
    _telemetry.success(
        f"side view in third-angle projection: +Z down, +Y left, origin at "
        f"({at[0] * 1000.0:.2f}, {at[1] * 1000.0:.2f}) mm on the front view's "
        f"origin height {front_origin[1] * 1000.0:.2f} mm"
    )


# swAnnotationType_e: swCenterMark (ISO 13).
_CENTER_MARK_ANNOTATION = 13
# A centre mark's ink centre against the projected bore axis: its lines come
# back from GetDisplayData as sheet coordinates, so half a millimetre bounds
# a mark drawn on the wrong circle without arguing over a pixel.
CENTER_MARK_AXIS_SLOP = 0.0005


def _collar_bore_rim(side: Any) -> Any:
    """The bore's rim on the collar's near end face.  The side view looks from
    +X (the arm, +Z, runs down the sheet), so the face at +COLLAR_HALF_LEN
    carries the visible circles; the far rim is coaxial and prints under it."""
    return scan_view_edges(side, label="bracket collar end").circle_at(
        (COLLAR_HALF_LEN, 0.0, 0.0),
        COLLAR_BORE_DIA / 2.0,
        axis=(1.0, 0.0, 0.0),
        label="bracket collar bore rim",
    )


def _ink_centre(annotation: Any, label: str) -> tuple[float, float]:
    """Centre of a centre mark's rendered lines (sheet metres)."""
    data = _early_bound(annotation, "IAnnotation").GetDisplayData()
    if data is None:
        raise RuntimeError(f"{label}: centre mark has no display data")
    data = _early_bound(data, "IDisplayData")
    count = int(data.GetLineCount())
    if count <= 0:
        raise RuntimeError(f"{label}: centre mark draws no lines")
    xs: list[float] = []
    ys: list[float] = []
    for index in range(count):
        line = [float(v) for v in data.GetLineAtIndex2(index)]
        xs.extend((line[4], line[7]))
        ys.extend((line[5], line[8]))
    return ((min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0)


def _prove_collar_centre_mark(adapter: Any, side: Any) -> None:
    """Prove the collar's end view carries exactly ONE centre mark, on the
    bore's axis.

    The project template centre-marks the extruded annulus's bore as the
    view is placed (its extended lines end at the bore radius plus 2.5 mm),
    so the explicit ``auto_center_marks(holes=True)`` the v41 sheet also
    ran printed a second, identical mark over it: retry09 native audit
    (20261012T124257186Z) counted DetailItem351 and DetailItem352 at
    (266.15, 180) mm, the same lines twice (the washer's annulus end view
    read 1 -> 2 the same way, #913).  This sheet adds none and proves the
    template's; zero marks or two fail loud, the proof is not a cleaner.
    """
    rim = _collar_bore_rim(side)
    cx, cy, cz, *_ = rim.circle
    axis = model_point_in_view(
        adapter, side, (cx / 1000.0, cy / 1000.0, cz / 1000.0), label="collar bore axis"
    )
    marks = list(
        _early_bound(side, "IView").GetAnnotationsByType(_CENTER_MARK_ANNOTATION) or ()
    )
    if len(marks) != 1:
        raise RuntimeError(
            f"collar end view carries {len(marks)} centre marks, expected the "
            "template's one on the bore axis"
        )
    ink = _ink_centre(marks[0], "collar bore centre mark")
    offset = math.hypot(ink[0] - axis[0], ink[1] - axis[1])
    if offset > CENTER_MARK_AXIS_SLOP:
        raise RuntimeError(
            f"collar centre mark prints {offset * 1000.0:.2f} mm off the bore axis "
            f"(ink {ink[0] * 1000.0:.2f}, {ink[1] * 1000.0:.2f} mm; axis "
            f"{axis[0] * 1000.0:.2f}, {axis[1] * 1000.0:.2f} mm)"
        )
    _telemetry.success(
        f"collar end view: one centre mark, {offset * 1000.0:.2f} mm off the bore "
        f"axis at ({axis[0] * 1000.0:.2f}, {axis[1] * 1000.0:.2f}) mm"
    )


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open magnifying-bracket source", await adapter.open_model(str(SOURCE)))
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
            "Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
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
            0: "Magnifying Bracket Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "magnifying bracket; collar + arm + flange; steel fitting",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Top", *FRONT_CENTER, scale=(1, 1))
    bottom = place_view(adapter, str(SOURCE), "*Front", *BOTTOM_CENTER, scale=(1, 1))
    side = place_view(adapter, str(SOURCE), "*Right", *SIDE_CENTER, scale=(1, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 1))
    # The collar bore and the counterbores are fully defined by their callouts
    # (mreview09: the front view's dashed lines only cluttered the 10.00 and
    # 3.175), so every view prints hidden lines removed.
    for view in (front, bottom, side, iso):
        set_hidden_lines_removed(adapter, view)
    _project_side_view(adapter, front, side)

    # Targeted imports: each view selects only the features owning its keep
    # map (the entire-model fallback warned on every view and imported the
    # whole marked set to delete most of it).
    front_annotations = curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="front",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    curate_view_dimensions(
        adapter,
        bottom,
        keep=BOTTOM_KEEP,
        view_label="bottom",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    side_annotations = curate_view_dimensions(
        adapter,
        side,
        keep=SIDE_KEEP,
        view_label="side",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    set_dimension_callouts(adapter, front_annotations, DIMENSION_CALLOUTS)
    set_dimension_callouts(adapter, side_annotations, SIDE_CALLOUTS)
    # The arm's section: the part blanks ArmSection, so this targeted import
    # shows it in the side view first (it stays shown there, printing the
    # bore axis as a centerline down to the arm's end; its construction lines
    # lie on the view's own edges).
    section_annotations = curate_hidden_dimensions(
        adapter,
        side,
        keep=SIDE_SECTION_KEEP,
        view_label="side arm section",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    set_dimension_callouts(adapter, section_annotations, SECTION_CALLOUTS)
    # ArmOffset is a LINEAR reference: the plural set_reference_dimensions
    # forces the diameter glyph, printing "(Ø3.35)" (retry08 native audit).
    for name in SECTION_REFERENCE:
        matches = [
            a for a in section_annotations if dimension_name(adapter, a) == name
        ]
        if len(matches) != 1:
            raise RuntimeError(
                f"expected one arm section {name} reference dimension, "
                f"found {len(matches)}"
            )
        set_reference_dimension(adapter, matches[0], label=f"arm section {name}")
    rims = _mounting_rims(bottom)

    add_native_hole_callout(
        adapter,
        bottom,
        # The east hole (x 108.7 mm), nearer the block.  AddHoleCallout2
        # (retry09, requested (337, 78) mm) prints the thru row ("2X Ø 2.59
        # THRU ALL", 43.8 mm) 1.8 mm over the requested y and the prefixed
        # counterbore row ("DRILL / COUNTERBORE ⌴ Ø 3.80 +0.10/0.00 ↧
        # 1.55±0.05", 117.9 mm) 7.3 mm under it, both centred on the
        # requested x; the leader's shoulder runs along the lower row's
        # baseline from an elbow 1.5 mm before its end nearer the hole, and
        # the leader runs from that elbow THROUGH the hole's centre to the far
        # rim.  "FAR SIDE" adds ~23 mm: the lower row ~141 mm.  Centred at
        # (212, 87) mm it spans x ~141.5..282.5 mm, y 79.7..83.2 mm, the thru
        # row x ~190..234 mm, y 88.8..92.3 mm: over the title block (y >= 66
        # mm) and the notes (top row y 69.5 mm), 5 mm under the flange
        # height's tail (x 148 mm, down to y 97.25 mm), 12 mm left of the
        # isometric's outline (x 294.7 mm) and 32 mm left of the iso note
        # (x 315 mm on).  The leader from the elbow at (140, 79.7) mm to the
        # hole at (108.7, 110) mm leaves the flange through its lower edge at
        # x 115.3 mm; it passes the 4.00's line (y 89 mm, ending at x 101.4
        # mm) at x 130.4 mm and the 17.70's (y 81 mm, ending at x 115.1 mm)
        # at x 138.7 mm, and meets no witness: the hole's own drops from the
        # lower face at x 108.7 mm, left of the leader's run; the flange
        # height's reach x 140 mm on at y 103.65 mm, where the leader is at
        # x 115.3 mm, and its column at x 148 mm is right of the elbow.
        edge=rims[1].edge,
        callout_xy=(0.212, 0.087),
        label="two bracket counterbores",
        process=COUNTERBORE_PROCESS,
    )
    curate_hidden_dimensions(
        adapter,
        bottom,
        keep=BOTTOM_HOLE_KEEP,
        view_label="bracket mounting coordinates",
        dimensions_by_feature={
            "MountingCoordinates": ("MountingX0", "MountingX1", "MountingY0"),
        },
    )

    # The collar bore's ASME centre mark is the template's, placed with the
    # end view: the sheet proves it (one, on the axis) rather than adding a
    # second over it.
    _prove_collar_centre_mark(adapter, side)

    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.070)
    add_property_linked_note(adapter, "Isometric View Note", 0.315, 0.095)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Magnifying Bracket Manufacturing Drawing",
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
