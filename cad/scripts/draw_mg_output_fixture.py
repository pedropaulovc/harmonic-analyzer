r"""Create the manufacturing drawing for the output fixture (MHA-MG-06).

The SLDPRT is authoritative: every printed dimension, its places and its
band are model dimensions marked for the drawing
(``mg_output_fixture_spec.DRAWING_DIMENSIONS``); this recipe places views,
keeps each dimension where it reads, and proves the import kept the part's
places. Sheet/template and export behavior lives in ``_drawing_common``.
Dimension import and curation live in ``_drawing_dimension_import``.

The side view is the ``*Top`` orientation, as in the lathe: the hex axis
horizontal, looking straight down the drilled rod bore, the flats edge-on
top and bottom.  The rod bore is the axial origin: under the view the
spigot's length from the faced end, then the bore's stations from the free
end and to the spigot face, and the overall length REF; over it the groove
from the spigot face and the bore's Ø.  The groove's root Ø nests inside
the spigot's, right of the face, each a dimension line standing across its
diameter, and the groove's R LIMIT, FULL R on its own row under it, reads
between them and the face, over the root Ø's text.  The shoulder's inside
corner prints no size: the title block's INSIDE CORNERS R1.0 MAX governs it
(nothing seats on the shoulder).  The end view looks at the spigot face: its ``*Right``
orientation is turned by the measured projected axes until -Z points up,
matching the side view, and -Y points right.  Its origin is pinned to the
side view's origin height.  The flats' stock reference, (11.113), stands
vertically, and the #4-40 native callout states the controlling drill depth,
the reference thread depth, (10.1), and, on its own row under the thread,
FULL THREAD TO ROD BORE.  One native centreline identifies the rod bore's Y
axis through the corners, independently of the axial tap's small centre
mark.  Hidden lines stay off: the standard holes' callouts define them.

Run with SolidWorks open::

    uv run python cad\scripts\draw_mg_output_fixture.py mg-output-fixture
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Any

from solidworks_mcp.adapters.com_variant import double_array

from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    dimension_name,
    place_view,
)

from _check import check
from _com import _early_bound
from _drawing_attachment import _assert_attached_to
from _drawing_centerline import add_view_centerline
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    stamp_drawing_summary,
)
from _drawing_dimension_import import curate_view_dimensions
from _drawing_dimensions import (
    assert_imported_precision,
    set_dimension_callouts,
    set_reference_dimension,
)
from _drawing_hole_callout import add_native_hole_callout, set_hole_callout_precision
from _drawing_leaders import Segment, dimension_segments, distance_to_point, segments_cross
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME, layout_report_path
from _drawing_projection import model_point_in_view
from _drawing_view_display import set_hidden_lines_removed
from _machinist_review_mode import MachinistReviewMode
from _paths import CAD_ROOT
from _layout_audit import REPORT_SCHEMA
from _session import run_build
import _telemetry
from _gear_drawing_entities import visible_circle_edge
from mg_output_fixture_geom import (
    FREE_END_X,
    GROOVE_ROOT_DIA,
    GROOVE_CENTRE_R,
    GROOVE_HALF_OPENING,
    GROOVE_RADIUS,
    GROOVE_X,
    HEX_AF,
    HEX_CORNER_RADIUS,
    SHOULDER_X,
    ROD_BORE_DIA,
    SPIGOT_DIA,
    SPIGOT_FACE_X,
    TAP_DRILL_DEPTH,
    TAP_DRILL_DIA,
    TAP_LENGTH,
)
from mg_output_fixture_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    GROOVE_RADIUS_CALLOUT,
    GROOVE_RADIUS_MIN,
    GROOVE_RADIUS_TOL_TYPE,
    GROOVE_STATION,
    LIMIT_BANDS,
    REFERENCE_DIMENSIONS,
    ROD_BORE_CALLOUT,
    TAP_CALLOUT_PRECISION,
    TAP_DEPTH_PLACES,
    TAP_DRILL_DEPTH_VARIABLE,
    TAP_EXTENT_CALLOUT,
    TAP_PROCESS,
    TAP_SPEC,
    TAP_THREAD_DEPTH_VARIABLE,
)

# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["mg_output_fixture"]
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

# An 18.0 x 12.8 part: 4:1 leaves room for the side view's nine dimensions.
SHEET_SCALE = (4.0, 1.0)
VIEW_SCALE = (4, 1)
ISO_SCALE = (3, 1)
_S = SHEET_SCALE[0] / SHEET_SCALE[1]
# Left of the old 125 mm: the radius text now reads right of the spigot face,
# so the two turned Ø stand further out, clear of the end view's AF.
SIDE_CENTER = (0.115, 0.180)
END_CENTER = (0.262, SIDE_CENTER[1])
# Low right, over the title block: the end view's tap callout runs out to
# the right at the hole's height, above it.
ISO_CENTER = (0.372, 0.115)
NOTES_XY = (0.016, 0.078)
# The side view is centred on the part's axial extent.
_AXIAL_MID = (FREE_END_X + SPIGOT_FACE_X) / 2.0
_HALF_AF = HEX_AF / 2.0


def _side_x(model_x_mm: float) -> float:
    """Sheet X of a station along the hex axis on the side view."""
    return SIDE_CENTER[0] + (model_x_mm - _AXIAL_MID) * _S / 1000.0


def _side_y(sketch_v_mm: float) -> float:
    """Sheet Y of a Top-plane sketch height on the side view (sheet up is
    sketch +v, model -Z)."""
    return SIDE_CENTER[1] + sketch_v_mm * _S / 1000.0


_SIDE_TOP = _side_y(_HALF_AF)
_SIDE_BOTTOM = _side_y(-_HALF_AF)
# Printed glyph pitch on the 2026-10-12 farm sheets (the layout audit's
# boxes): retry09's turned Ø text ran 29.8 mm over its 13 glyphs
# (20261012T124257186Z).  Text extents below are estimates at that pitch,
# used to hold each text clear of the lines beside it; the layout audit's
# text-on-line gate (_enforce_fixture_text_on_line) is the proof.
_GLYPH_PITCH = 0.0298 / 13
# A turned Ø prints a space, Ø, the .XX value and a space; the spigot's
# (Ø10.10) is the wider of the two.
TURNED_DIA_GLYPHS = 3 + len(
    f"{max(SPIGOT_DIA, GROOVE_ROOT_DIA):.{DRAWING_PRECISION_BY_NAME['SpigotDia']}f}"
)
TURNED_DIA_TEXT_HALF_WIDTH = TURNED_DIA_GLYPHS * _GLYPH_PITCH / 2.0
# Upper bounds from the larger banded, reamed callout (27.5 x 14.6 mm) this
# bore printed before; the drilled Ø over its one process row is smaller.
BORE_CALLOUT_HALF_WIDTH = 0.0138
BORE_CALLOUT_HALF_HEIGHT = 0.0073
# The rod bore is the axial origin.  The bore's two stations (free end to
# bore, bore to spigot face) hang under the view on one row, sharing the
# bore's witness; the overall length, REF, runs outermost under them.  All
# three are witnessed from axis points, so nothing under the view touches
# the groove.  The spigot's length, from the faced end to the shoulder (r2
# review: the lathe's own length), reads innermost under the spigot: the
# turned profile's corners are on the lower silhouette, so its witnesses
# drop from the shoulder's and the face's lower corners and end above the
# stations' row.  The bore's Ø reads over the hex; the groove's station,
# from the spigot face, over the spigot.  Its face-side witness starts above
# the face's top corner, so it never runs down the face across the radius
# leader.
#
# The two turned Ø stack right of the face, the smaller inside: the groove
# root's extension lines run from the two roots across the face-side lip to
# its dimension line, which stands root to root, and the spigot's stands a
# pitch further out.  Each text breaks its own dimension line, the root's
# below the axis and the spigot's above, so neither text crosses the other's
# line and the two never read as one row.  Retry09 hung the root's text
# under the view instead: SolidWorks ran its dimension line 20 mm down out of
# the groove into a 30 mm horizontal shoulder beside the bore's station, and
# the Ø read as an axial length (machinist review09).
_FACE_SHEET_X = _side_x(SPIGOT_FACE_X)
_HEX_MID_X = _side_x((FREE_END_X + SHOULDER_X) / 2.0)
# The groove's radius reads in the open air right of the spigot face, over
# the root Ø's text and under its upper extension line, inside the root Ø's
# dimension line.  Its radial leader climbs from the elbow to the
# face-side material arc (r1 review: the shelf at the OD ran along the
# spigot Ø's extension and the arrow sat at the mouth).  The leader crosses
# the face outline and the root Ø's extension line, never a dimension line
# (drawing-guidelines.md rule 14).  Native15 measured the full shoulder
# starting 15.2764 mm left of and 2.7781 mm below the keep for its eleven
# radius glyphs: the run-in is the text's half width plus a lead, so the
# stack's is estimated from the glyph pitch.  The proofs below need only the
# arrow on the material arc, the leader radial and the ink clear of the
# dimension lines, whatever run-in SolidWorks draws.
RADIUS_INK_SLOP = 0.0004
RADIUS_STATION_CLEARANCE = 0.002
# The part's LIMIT band (owner ruling 2026-10-17, review r4) prints two rows,
# R and the upper limit over the lower limit, at its places (the part owns
# the text; this only sizes it).  Under them the dimension's own callout row
# reads FULL R (owner ruling, review r5): the widest of the three rows.
RADIUS_GLYPHS = 1 + max(
    len(f"{value:.{DRAWING_PRECISION_BY_NAME['GrooveRadius']}f}")
    for value in (GROOVE_RADIUS, GROOVE_RADIUS_MIN)
)
RADIUS_CALLOUT_GLYPHS = len(GROOVE_RADIUS_CALLOUT)
RADIUS_TEXT_HALF_WIDTH = max(RADIUS_GLYPHS, RADIUS_CALLOUT_GLYPHS) * _GLYPH_PITCH / 2.0
_NATIVE15_RADIUS_GLYPHS = 11
RADIUS_SHOULDER_LEAD = 0.0152764 - _NATIVE15_RADIUS_GLYPHS * _GLYPH_PITCH / 2.0
RADIUS_SHOULDER_RUN_IN = RADIUS_TEXT_HALF_WIDTH + RADIUS_SHOULDER_LEAD
RADIUS_SHOULDER_DROP = 0.0027781
_CALLOUT_BELOW = 4  # swDimensionTextParts_e.swDimensionTextCalloutBelow
# Row pitches from the layout audits' display data (same template): r12's
# GrooveRadius (20261017T053834039Z) printed its upper limit on the keep and
# the lower 4.5257 mm under it, the shoulder under the lower row; a callout
# row prints 5.5563 mm under the last value row (pd-latch-hook's RoundR,
# "FULL ROUND", 20261015T223846658Z), and SolidWorks re-centres the stack
# on the keep, so a callout row under a LIMIT lifts the limits half a
# callout pitch and drops the shoulder, under the callout, as far:
# dt-cone-gear's FloorDia, a LIMIT over "ROOT ENVELOPE", hangs its shoulder
# 7.3038 mm under its keep (20261015T201555493Z).
LIMIT_ROW_PITCH = 0.0045257
CALLOUT_ROW_PITCH = 0.0055563
GROOVE_RADIUS_SHOULDER_DROP = LIMIT_ROW_PITCH + CALLOUT_ROW_PITCH / 2.0
_GROOVE_CENTRE_XY = (_side_x(GROOVE_X), _side_y(GROOVE_CENTRE_R))
# The three rows stand 14.5 mm from the shoulder to the upper limit's ink
# (r12 printed ink from 0.99 mm over a row's position to 4.42 mm over it),
# and the air over the root Ø's text (its ink tops out 2.03 mm under the
# axis, r12) up to the root Ø's upper extension line (15.4 mm over the axis)
# is 17.4 mm.  The shoulder 1 mm under the axis stands the callout row's
# ink 2.0 mm over the root Ø's text, so the two never read as one row, and
# the upper limit's 1.9 mm under the extension line.  On r12's keep the
# callout row would have pushed the upper limit onto that line.  The text
# runs 2 mm plus its run-in right of the face, as r1-r4's did; the run-in
# is the callout row's, the widest.
RADIUS_TEXT_XY = (
    _FACE_SHEET_X + 0.002 + RADIUS_SHOULDER_RUN_IN,
    SIDE_CENTER[1] - 0.001 + GROOVE_RADIUS_SHOULDER_DROP,
)
RADIUS_ELBOW_XY = (
    RADIUS_TEXT_XY[0] - RADIUS_SHOULDER_RUN_IN,
    RADIUS_TEXT_XY[1] - GROOVE_RADIUS_SHOULDER_DROP,
)
# Where the radial line from the elbow meets the groove circle.
_ELBOW_RUN = math.dist(RADIUS_ELBOW_XY, _GROOVE_CENTRE_XY)
RADIUS_PREDICTED_TIP_XY = tuple(
    centre + (elbow - centre) * GROOVE_RADIUS * _S / 1000.0 / _ELBOW_RUN
    for elbow, centre in zip(RADIUS_ELBOW_XY, _GROOVE_CENTRE_XY)
)
# The root Ø's dimension line stands where r1-r4 tuned it, 6 mm right of
# their one-row limit's eight glyphs, centred 2 mm plus that text's run-in
# right of the face.
_SINGLE_ROW_RADIUS_GLYPHS = 8
_R4_RADIUS_TEXT_X = (
    _FACE_SHEET_X
    + 0.002
    + _SINGLE_ROW_RADIUS_GLYPHS * _GLYPH_PITCH / 2.0
    + RADIUS_SHOULDER_LEAD
)
_STACKED_DIA_PITCH = 0.020
# Each Ø text's offset from the axis: the two texts' centres 10 mm apart.
_STACKED_DIA_STAGGER = 0.005
_GROOVE_ROOT_DIA_X = (
    _R4_RADIUS_TEXT_X + _SINGLE_ROW_RADIUS_GLYPHS * _GLYPH_PITCH / 2.0 + 0.006
)
# Rows under the view, 12 mm apart: the spigot's length nearest, then the
# bore's stations, then the overall REF.
_SPIGOT_ROW = _SIDE_BOTTOM - 0.010
_UNDER_ROW = _SIDE_BOTTOM - 0.022
# The groove's station reads over the spigot.  The shoulder's inside corner
# prints no size (ENFORCE review 2026-10-24, rule 4: the bare R0.2 MAX named
# no mate, and nothing seats on the shoulder): the title block's INSIDE
# CORNERS R1.0 MAX governs it.
_GROOVE_STATION_TEXT_Y = _SIDE_TOP + 0.012
SIDE_KEEP = {
    "RodBoreDia": (_HEX_MID_X, _SIDE_TOP + 0.011),
    "GrooveStation": (_side_x((GROOVE_X + SPIGOT_FACE_X) / 2.0), _GROOVE_STATION_TEXT_Y),
    "SpigotLength": (_side_x((SHOULDER_X + SPIGOT_FACE_X) / 2.0), _SPIGOT_ROW),
    "RodStation": (_side_x(FREE_END_X / 2.0), _UNDER_ROW),
    "BoreStation": (_side_x(SPIGOT_FACE_X / 2.0), _UNDER_ROW),
    "OverallLength": (_side_x(_AXIAL_MID), _UNDER_ROW - 0.012),
    "GrooveRootDia": (_GROOVE_ROOT_DIA_X, SIDE_CENTER[1] - _STACKED_DIA_STAGGER),
    "SpigotDia": (
        _GROOVE_ROOT_DIA_X + _STACKED_DIA_PITCH,
        SIDE_CENTER[1] + _STACKED_DIA_STAGGER,
    ),
    "GrooveRadius": RADIUS_TEXT_XY,
}
# The groove's root Ø is a doubled distance, the groove's axis to its root
# point (build_mg_output_fixture._groove_profile: AddSpecificDimension
# swDiametricLinearDimension, Diametric proven on the part), so the sheet
# reads it as a diameter only while its dimension line stands across the
# groove, root to root.  What the sheet's import reads back, by the SDK
# (IDisplayDimension.Type2, swDimensionType_e; IDisplayDimension.Diametric
# "toggles between radial and diameter" and "between radial linear and
# diametric linear" display dimensions, True for "the diameter/doubled
# distance"): retry10 read the imported GrooveRootDia as swDiameterDimension
# (6) with Diametric True (farm 20261012T170144152Z), the diameter family's
# type, the way the obsolete GetType folds radial and diametric into one.
# The proof takes that or the authoring type itself, swDiametricLinearDimension
# (15, "doubled distance linear dimension"), with Diametric set: a plain
# linear (2, 11, 12), the groove's radius (5), a single-distance radial
# linear (14) or any doubled type shown single (Diametric False) fails.
# The type pair alone cannot tell the root Ø from a circle's Ø, which reads
# the same, so the proof also reads the model dimension's value, the
# doubled distance itself, then the ink root to root.
_DOUBLED_DISTANCE_TYPES = {
    6: "swDiameterDimension",
    15: "swDiametricLinearDimension",
}
# IDimension.SystemValue is metres; the import keeps the model's value exactly
# (_ms_drawing_contract, _drawing_edge_dimensions: 1e-5 mm).
GROOVE_ROOT_VALUE_SLOP_MM = 1e-5
GROOVE_ROOT_SHEET_YS = (
    _side_y(-GROOVE_ROOT_DIA / 2.0),
    _side_y(GROOVE_ROOT_DIA / 2.0),
)
# GetDisplayData reads the window's rendering, up to ~1.1 mm off the print at
# fit (the layout doc's COM traps); retry09's stray leg ran 20 mm.
GROOVE_ROOT_INK_SLOP = 0.0015
# SolidWorks starts an extension line 1 mm off its feature (retry09: the
# spigot Ø's, 1.0 mm right of the face).
EXTENSION_START_GAP = 0.001
# After the measured turn, the end view's flats are horizontal, corners
# left/right: AF is its height, AC its width.  AF reads left of the hex as a
# vertical stock reference, away from the tap's right-running leader.
_END_HALF_HEIGHT = HEX_AF / 2.0 * _S / 1000.0
_END_HALF_WIDTH = HEX_CORNER_RADIUS * _S / 1000.0
END_KEEP = {
    "HexAf": (END_CENTER[0] - _END_HALF_WIDTH - 0.013, END_CENTER[1]),
}
# The tap callout reads right of the end view at the hole's height.  Its
# shoulder clears the corner and the small tap cross; AF witnesses run left.
# ``callout_xy`` is the text block's centre both ways (the r3 sheet,
# 20261017T032030239Z: two rows inked centred at (336.9, 189.35) mm for
# (337.2, 189.6)), and the shoulder sits under the bottom row: 5.6 mm under a
# two-row block's centre (the v1 and r3 sheets' ink).  The rows pitch 6.0 mm
# (r3), so the extent row, FULL THREAD TO ROD BORE, grows the block a pitch
# about its centre: the centre rises half a pitch more and the shoulder stays
# 4 mm over the hole, its leader rising to it, not lying along the bore's
# centreline.  Widths, in r3's 3.4 mm capitals: TAP INTO BORE 4-40 UNC - 2B
# (depth) (10.1) printed 85.0 mm; less INTO BORE, the thread row is ~59.3 mm;
# r3's general note FULL THREAD TO ROD BORE. printed 61.2 mm in the same
# capitals, so the extent row is ~60.2 mm without its full stop.  This half
# width holds ~63 mm, the widest row and the 1.5 mm a side the two-row half
# width (87 mm over ~84) kept, so the text still starts ~6 mm off the corner.
_TAP_CALLOUT_HALF_WIDTH = 0.0316
_TAP_CALLOUT_ROW_PITCH = 0.0060
_TAP_CALLOUT_SHOULDER_DROP = 0.0056 + _TAP_CALLOUT_ROW_PITCH / 2.0
TAP_CALLOUT_XY = (
    END_CENTER[0] + _END_HALF_WIDTH + 0.006 + _TAP_CALLOUT_HALF_WIDTH,
    END_CENTER[1] + 0.004 + _TAP_CALLOUT_SHOULDER_DROP,
)
# What the native callout must print: the thread itself, not just the drill.
_TAP_THREAD_TEXT = f"{TAP_SPEC.size.lstrip('#')} UNC"
# A band on either depth: the thread's is REF (bracketed), the drill's is the
# title block's .X.
_BAND_MARKS = ("<MOD-PM>", "±", "+/-")
# SolidWorks' own descriptive "#4-40 Tapped Hole" note: the native callout
# states the thread, so none may reach the print.  How many SolidWorks pins
# is the tap's, measured, not derived: with the same three views, the same
# sketch-only targeted imports (the tap is never imported) and the same
# centre-mark recipe, the up-to-next tap (TAP TO BORE 4-40 UNC - 2B THRU)
# brought one on swmaker000005 and on swmaker000009 (farm runs
# 20261012T025810090Z, 20261012T064524082Z: "removed 1 redundant final
# drawing notes"), and the blind tap that replaced it brings none (retry08,
# 20261012T111849499Z on swmaker000005: "removed 0 ..., expected 1").
# finalize_drawing still sweeps every sheet for the note, so one that comes
# back fails the census instead of printing beside the callout.
TAPPED_HOLE_NOTE = "Tapped Hole"
AUTO_TAPPED_HOLE_NOTES = 0

# Axis projections are geometric readbacks, not manufacturing bands.
PROJECTION_ANGLE_SLOP = 1e-6
PROJECTION_SLOP_M = 1e-5
BORE_FACE_SLOP_M = 1e-8
# GrooveStation's witnesses get local gaps: its centre-side witness starts
# 3 mm above the arc centre, its face-side one 1 mm above the face's top
# corner (the dimension's face point is on the axis).  The root Ø retains
# EXTENSION_START_GAP and its strict root-to-root ink proof.
GROOVE_STATION_GAP = 0.003
GROOVE_STATION_FACE_GAP = SPIGOT_DIA / 2.0 * _S / 1000.0 + EXTENSION_START_GAP


def _axis_direction(
    adapter: Any, view: Any, axis: tuple[float, float, float], label: str
) -> tuple[float, float]:
    origin = model_point_in_view(adapter, view, (0.0, 0.0, 0.0), label=f"{label} origin")
    tip = model_point_in_view(adapter, view, axis, label=f"{label} tip")
    return tip[0] - origin[0], tip[1] - origin[1]


def _require_axis(
    adapter: Any, view: Any, axis: tuple[float, float, float], angle: float, label: str
) -> None:
    dx, dy = _axis_direction(adapter, view, axis, label)
    if (
        abs(math.hypot(dx, dy) - _S / 1000.0) > PROJECTION_SLOP_M
        or abs(math.remainder(math.atan2(dy, dx) - angle, math.tau))
        > PROJECTION_ANGLE_SLOP
    ):
        raise RuntimeError(f"{label}: projected axis {(dx, dy)} is not at {angle:g} rad")


def _project_end_view(adapter: Any, front: Any, end: Any) -> None:
    """The bracket's measured turn and the latch's measured origin pin."""
    _require_axis(adapter, front, (0.001, 0.0, 0.0), 0.0, "front +X")
    _require_axis(adapter, front, (0.0, 0.0, 0.001), -math.pi / 2.0, "front +Z")
    native = _early_bound(end, "IView")
    dx, dy = _axis_direction(adapter, native, (0.0, 0.0, 0.001), "end +Z before")
    if math.hypot(dx, dy) <= PROJECTION_SLOP_M:
        raise RuntimeError("end +Z has no measurable projected direction")
    # No assumed +90/-90: rotate the measured +Z direction to sheet down.
    native.Angle = float(native.Angle) - math.pi / 2.0 - math.atan2(dy, dx)
    rebuild_drawing(adapter, label="turn fixture end view")
    _require_axis(adapter, native, (0.0, 0.0, 0.001), -math.pi / 2.0, "end +Z")
    _require_axis(adapter, native, (0.0, 0.001, 0.0), math.pi, "end +Y")
    front_origin = model_point_in_view(
        adapter, front, (0.0, 0.0, 0.0), label="front origin"
    )
    target = (END_CENTER[0], front_origin[1])
    at = model_point_in_view(adapter, native, (0.0, 0.0, 0.0), label="end origin")
    position = tuple(float(value) for value in native.Position)
    moved = [position[axis] + target[axis] - at[axis] for axis in range(2)]
    if native.SetViewPosition(double_array(moved), False) is not True:
        raise RuntimeError("failed to pin the fixture end view in projection")
    rebuild_drawing(adapter, label="pin fixture end view")
    at = model_point_in_view(adapter, native, (0.0, 0.0, 0.0), label="end origin pinned")
    if math.dist(at, target) > PROJECTION_SLOP_M:
        raise RuntimeError(f"end origin {at} does not share front origin height {target}")
    _telemetry.success(
        f"fixture end in projection: +Z down, +Y left; origin {at}, front {front_origin}"
    )


def _model_display(annotation: Any, name: str, feature: str, value_mm: float) -> Any:
    """Require the imported display's exact model dimension, not typed ink."""
    display = _early_bound(
        _early_bound(annotation, "IAnnotation").GetSpecificAnnotation(),
        "IDisplayDimension",
    )
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    full_name = str(dimension.FullName)
    measured = abs(float(dimension.SystemValue)) * 1000.0
    if (
        full_name.split("@")[:2] != [name, feature]
        or abs(measured - value_mm) > GROOVE_ROOT_VALUE_SLOP_MM
    ):
        raise RuntimeError(f"{name}: wrong model dimension {full_name!r}, {measured:g} mm")
    return display


def _end_af_ink_problem(
    segments: list[Segment], flats: tuple[tuple[float, float], tuple[float, float]]
) -> str | None:
    line_x = END_KEEP["HexAf"][0]
    slop = RADIUS_INK_SLOP
    line_ys: list[float] = []
    witnesses: dict[tuple[float, float], list[float]] = {flat: [] for flat in flats}
    for (x0, y0), (x1, y1) in segments:
        if abs(x0 - line_x) <= slop and abs(x1 - line_x) <= slop:
            line_ys += [y0, y1]
            continue
        matching = [flat for flat in flats if max(abs(y0 - flat[1]), abs(y1 - flat[1])) <= slop]
        if not matching:
            return "stroke is neither the vertical AF line nor a flat witness"
        witnesses[matching[0]] += [x0, x1]
    low, high = sorted(flat[1] for flat in flats)
    if not line_ys or max(abs(min(line_ys) - low), abs(max(line_ys) - high)) > slop:
        return "dimension line does not stand across AF"
    for (flat_x, flat_y), xs in witnesses.items():
        if (
            not xs
            or abs(max(xs) - (flat_x - EXTENSION_START_GAP)) > slop
            or min(xs) > line_x + slop
        ):
            return f"no left-running witness from flat {(flat_x, flat_y)}"
    return None


def _prove_end_stock_reference(adapter: Any, view: Any, annotation: Any) -> None:
    display = _model_display(annotation, "HexAf", "HexProfile", HEX_AF)
    if (str(display.GetText(1)), str(display.GetText(2))) != ("(", ")"):
        raise RuntimeError("HexAf lost its linear stock-reference brackets")
    flats = tuple(
        model_point_in_view(adapter, view, point, label="HexAf flat witness")
        for point in (
            (FREE_END_X / 1000.0, HEX_CORNER_RADIUS / 2000.0, -HEX_AF / 2000.0),
            (FREE_END_X / 1000.0, -HEX_CORNER_RADIUS / 2000.0, HEX_AF / 2000.0),
        )
    )
    problem = _end_af_ink_problem(dimension_segments(annotation), flats)
    if problem is not None:
        raise RuntimeError(f"HexAf does not print in the rotated frame: {problem}")
    _telemetry.success("HexAf stock REF stands across the end view's vertical AF")


def _station_witness(
    station: list[Segment], foot: tuple[float, float], gap: float, label: str
) -> tuple[Segment | None, str | None]:
    """GrooveStation's one vertical witness over ``foot``, starting ``gap``
    above it; or why there is none."""
    slop = RADIUS_INK_SLOP
    witnesses = [
        stroke for stroke in station
        if all(abs(point[0] - foot[0]) <= slop for point in stroke)
        and abs(stroke[1][1] - stroke[0][1]) > slop
    ]
    if len(witnesses) != 1:
        return None, f"station has no unique witness at the {label}"
    witness = witnesses[0]
    if abs(min(point[1] for point in witness) - foot[1] - gap) > slop:
        return None, f"station's {label} witness gap did not reach the rebuilt ink"
    return witness, None


def _groove_radius_ink_problem(
    segments: list[Segment],
    tip: tuple[float, float],
    station: list[Segment],
    centre: tuple[float, float],
    face: tuple[float, float],
) -> str | None:
    """Require a material-arc arrow and real clearance from both of the
    station's witnesses (``face`` is the spigot face's point on the axis)."""
    slop = RADIUS_INK_SLOP
    radius = GROOVE_RADIUS * _S / 1000.0
    root_y = centre[1] - radius
    mouth_y = centre[1] + (SPIGOT_DIA / 2.0 - GROOVE_CENTRE_R) * _S / 1000.0
    mouth_x = centre[0] + GROOVE_HALF_OPENING * _S / 1000.0
    if (
        not all(math.isfinite(v) for v in tip)
        or abs(math.dist(tip, centre) - radius) > slop
        or not centre[0] - slop <= tip[0] <= mouth_x + slop
        or not root_y - slop <= tip[1] <= mouth_y + slop
    ):
        return "radius arrow is not on the face-side material arc"
    if not segments or min(distance_to_point(stroke, tip) for stroke in segments) > slop:
        return "radius arrow has no attached leader ink"
    for foot, gap, label in (
        (centre, GROOVE_STATION_GAP, "groove arc centre"),
        (face, GROOVE_STATION_FACE_GAP, "spigot face"),
    ):
        witness, problem = _station_witness(station, foot, gap, label)
        if problem is not None:
            return problem
        for stroke in segments:
            if segments_cross(stroke, witness) or min(
                *(distance_to_point(witness, point) for point in stroke),
                *(distance_to_point(stroke, point) for point in witness),
            ) < RADIUS_STATION_CLEARANCE:
                return f"radius leader is not clear of the station's {label} witness"
    return None


def _radius_leader_ink_problem(
    segments: list[Segment],
    tip: tuple[float, float],
    centre: tuple[float, float],
    root_dia_line_x: float,
) -> str | None:
    """The radius draws a radial leader through its material tip and one
    horizontal shoulder from the leader's outer end, in the air over the
    root Ø's text and under its upper extension line, short of the root Ø's
    dimension line (rule 14: a leader never crosses a dimension line)."""
    slop = RADIUS_INK_SLOP
    radius = GROOVE_RADIUS * _S / 1000.0
    ink = [stroke for stroke in segments if math.dist(*stroke) > slop]
    ux, uy = ((tip[0] - centre[0]) / radius, (tip[1] - centre[1]) / radius)

    def on_ray(point: tuple[float, float]) -> bool:
        return abs((point[0] - centre[0]) * uy - (point[1] - centre[1]) * ux) <= slop

    # A stroke on the radial line through the tip is leader, even when that
    # line runs nearly level (r1's shelf at the OD); the shoulder is the one
    # level stroke off it.
    radial = [stroke for stroke in ink if all(on_ray(point) for point in stroke)]
    if not radial:
        return "radius draws no radial leader"
    rest = [stroke for stroke in ink if not all(on_ray(point) for point in stroke)]
    shoulders = [
        stroke for stroke in rest
        if abs(stroke[1][1] - stroke[0][1]) <= slop
        and abs(stroke[1][0] - stroke[0][0]) > slop
    ]
    if len(rest) != len(shoulders):
        return "radius leader is not on the radial line through its tip"
    if len(shoulders) != 1:
        return "radius has no unique horizontal shoulder"
    shoulder = shoulders[0]
    ends = [point for stroke in radial for point in stroke]
    elbow = max(ends, key=lambda p: (p[0] - centre[0]) * ux + (p[1] - centre[1]) * uy)
    if (elbow[0] - centre[0]) * ux + (elbow[1] - centre[1]) * uy < radius - slop:
        return "radius leader's outer end stops inside the groove circle"
    start = min(shoulder, key=lambda p: p[0])
    if math.dist(start, elbow) > slop or max(p[0] for p in shoulder) <= elbow[0] + slop:
        return "radius shoulder does not run right from the leader's outer end"
    axis_y = centre[1] - GROOVE_CENTRE_R * _S / 1000.0
    root_y = centre[1] - radius
    # The floor is the root Ø's text, whose ink tops out 2 mm under the axis
    # (r12: 177.97 mm); the shoulder stands 1 mm under the axis so the three
    # rows over it clear the extension line (RADIUS_TEXT_XY).
    if not (
        axis_y - RADIUS_STATION_CLEARANCE
        <= start[1]
        <= root_y - RADIUS_STATION_CLEARANCE
    ):
        return "radius shoulder is not between the root Ø's text and its extension"
    if max(point[0] for stroke in ink for point in stroke) > (
        root_dia_line_x - RADIUS_STATION_CLEARANCE
    ):
        return "radius ink reaches the root Ø's dimension line"
    return None


def _place_groove_radius(adapter: Any, radius: Any, station: Any) -> None:
    display = _model_display(radius, "GrooveRadius", "GrooveProfile", GROOVE_RADIUS)
    if int(display.Type2) != 5 or display.Diametric is not False:  # swRadialDimension
        raise RuntimeError("GrooveRadius is not the model's genuine radial dimension")
    display.ArcExtensionLineOrOppositeSide = False
    if display.ArcExtensionLineOrOppositeSide is not False:
        raise RuntimeError("GrooveRadius still attaches to an arc extension/opposite side")
    # The builder dimensions axis.end (the spigot face on the axis) ->
    # toward_free_end.center: witness 0 is the face, witness 1 the centre.
    # The rebuilt ink below proves each got its own gap.
    station_display = _model_display(
        station, "GrooveStation", "GrooveProfile", GROOVE_STATION
    )
    if station_display.SetWitnessLineGap(1, False, GROOVE_STATION_GAP) is not True:
        raise RuntimeError("GrooveStation refused its centre-side witness gap")
    if station_display.SetWitnessLineGap(0, False, GROOVE_STATION_FACE_GAP) is not True:
        raise RuntimeError("GrooveStation refused its face-side witness gap")
    rebuild_drawing(adapter, label="place fixture material-arc radius")


def _prove_groove_radius(adapter: Any, view: Any, radius: Any, station: Any) -> None:
    annotation = _early_bound(radius, "IAnnotation")
    if annotation.IsDangling() is not False or int(annotation.OwnerType) != 0:
        raise RuntimeError("GrooveRadius is dangling or not owned by its drawing view")
    display = _model_display(radius, "GrooveRadius", "GrooveProfile", GROOVE_RADIUS)
    if (
        int(display.Type2) != 5
        or display.Diametric is not False
        or display.ArcExtensionLineOrOppositeSide is not False
    ):
        raise RuntimeError("GrooveRadius lost its native material-arc radial style")
    tolerance = _early_bound(
        _early_bound(display.GetDimension2(0), "IDimension").Tolerance,
        "IDimensionTolerance",
    )
    # The part's LIMIT band, read back (the sheet never writes a band).
    lower, upper = LIMIT_BANDS["GrooveRadius"][1]
    if (
        int(tolerance.Type) != GROOVE_RADIUS_TOL_TYPE
        or not math.isclose(
            float(tolerance.GetMinValue()), lower / 1000.0, rel_tol=0.0, abs_tol=1e-12
        )
        or not math.isclose(
            float(tolerance.GetMaxValue()), upper / 1000.0, rel_tol=0.0, abs_tol=1e-12
        )
    ):
        raise RuntimeError("GrooveRadius lost the part's LIMIT band")
    # The dimension's own callout row, read back: FULL R defines the groove's
    # width (2R) and walls across the whole band (owner ruling, review r5).
    callout = str(display.GetText(_CALLOUT_BELOW) or "")
    if callout != GROOVE_RADIUS_CALLOUT:
        raise RuntimeError(
            f"GrooveRadius lost its {GROOVE_RADIUS_CALLOUT} callout row: read {callout!r}"
        )
    tip = _single_arrow_tip(display, "GrooveRadius")
    centre = model_point_in_view(
        adapter, view, (GROOVE_X / 1000.0, 0.0, -GROOVE_CENTRE_R / 1000.0),
        label="groove material-arc centre",
    )
    face = model_point_in_view(
        adapter, view, (SPIGOT_FACE_X / 1000.0, 0.0, 0.0), label="spigot face on the axis"
    )
    radius_ink = dimension_segments(radius)
    problem = _groove_radius_ink_problem(
        radius_ink, tip, dimension_segments(station), centre, face
    )
    if problem is not None:
        raise RuntimeError(f"GrooveRadius does not land clear on material: {problem}")
    problem = _radius_leader_ink_problem(
        radius_ink, tip, centre, SIDE_KEEP["GrooveRootDia"][0]
    )
    if problem is not None:
        raise RuntimeError(f"GrooveRadius leader does not read in open air: {problem}")
    _telemetry.success(
        f"genuine GrooveRadius LIMIT over {GROOVE_RADIUS_CALLOUT}, material-arc tip {tip}, "
        f"radial leader to a shoulder over the root Ø's text, inside its dimension line; "
        f"station witness gaps "
        f"{GROOVE_STATION_GAP * 1000:g} mm (centre) and "
        f"{GROOVE_STATION_FACE_GAP * 1000:g} mm (face), leader clearance >= "
        f"{RADIUS_STATION_CLEARANCE * 1000:g} mm from both"
    )


def _single_arrow_tip(display: Any, label: str) -> tuple[float, float]:
    """The rebuilt sheet point of a radial display dimension's one arrow."""
    raw = display.GetDisplayData()
    if raw is None:
        raise RuntimeError(f"{label} has no rebuilt display data")
    data = _early_bound(raw, "IDisplayData")
    if int(data.GetArrowHeadCount()) != 1:
        raise RuntimeError(f"{label} must draw exactly one radial arrow")
    arrow = tuple(float(v) for v in data.GetArrowHeadAtIndex2(0))
    if len(arrow) != 12 or not all(math.isfinite(v) for v in arrow):
        raise RuntimeError(f"{label} has incomplete arrow-head coordinates")
    return (arrow[0], arrow[1])


def _states_depth(text: str, depth_mm: float, *, reference: bool) -> bool:
    """Whether ``text`` prints ``depth_mm`` at the tap's depth places as a
    whole number (10.1 is not 110.1 or 10.15): in reference brackets, (10.1),
    when ``reference``, else bare."""
    printed = re.escape(f"{depth_mm:.{TAP_DEPTH_PLACES}f}")
    number = rf"(?<![\d.]){printed}(?!\d)"
    if reference:
        return re.search(rf"\(\s*{number}\s*\)", text) is not None
    return re.search(rf"(?:^|[^(\s])\s*{number}(?!\s*\))", text) is not None


def _tap_callout_resolved(resolved_parts: dict[int, str]) -> bool:
    """Whether the thumb-screw tap's callout reads as a blind tap into the
    bore: the prefix row opens with the process and carries the thread, its
    class and its nominal thread depth as a reference, (10.1), never bare;
    the below row, under it, the thread's extent, FULL THREAD TO ROD BORE,
    stated nowhere else; the drill row its controlling depth, bare; nothing
    is banded; and nothing says THRU (the tap stops in the bore, short of its
    far wall)."""
    lines = [text for text in resolved_parts.values() if text.strip()]
    thread = [text for text in lines if _TAP_THREAD_TEXT in text]
    drill = [
        text
        for text in lines
        if _TAP_THREAD_TEXT not in text and TAP_EXTENT_CALLOUT not in text
    ]
    prefix = resolved_parts.get(_CALLOUT_DEFINITION_PARTS[_CALLOUT_PREFIX_DEFINITION], "")
    below = resolved_parts.get(_CALLOUT_DEFINITION_PARTS[_CALLOUT_BELOW_DEFINITION], "")
    return (
        not any("THRU" in text for text in lines)
        and not any(mark in text for text in lines for mark in _BAND_MARKS)
        and len(thread) == 1
        and thread[0] == prefix
        and thread[0].lstrip().startswith(f"{TAP_PROCESS} ")
        and TAP_SPEC.thread_class in thread[0]
        and _states_depth(thread[0], TAP_LENGTH, reference=True)
        and not _states_depth(thread[0], TAP_LENGTH, reference=False)
        and below.strip() == TAP_EXTENT_CALLOUT
        and sum(TAP_EXTENT_CALLOUT in text for text in lines) == 1
        and any(_states_depth(text, TAP_DRILL_DEPTH, reference=False) for text in drill)
        and not any(_states_depth(text, TAP_DRILL_DEPTH, reference=True) for text in lines)
    )


# swDimensionTextParts_e: a hole callout's definitions (5-8: prefix, suffix,
# callout above, callout below) and the writable part each is set through
# (1-4), as draw_fr_harmonic_base._set_cross_tap_callout_text writes 3 and
# reads back 7.  The native thread row is the prefix's (retry09), so the
# below definition prints the extent row directly under the thread.
_CALLOUT_DEFINITION_PARTS = {5: 1, 6: 2, 7: 3, 8: 4}
_CALLOUT_PREFIX_DEFINITION = 5
_CALLOUT_BELOW_DEFINITION = 8
_THREAD_DEPTH_TOKEN = f"<{TAP_THREAD_DEPTH_VARIABLE}>"
_DRILL_DEPTH_TOKEN = f"<{TAP_DRILL_DEPTH_VARIABLE}>"


def reference_thread_depth_definitions(definitions: dict[int, str]) -> dict[int, str]:
    """The callout's definitions with the thread depth's variable bracketed,
    ``(<hw-threaddepth>)``, and every other character as it was.

    ASME Y14.5 marks a reference dimension by enclosing it in parentheses.
    The variable stays in the definition, so the bracketed value is still the
    model's thread depth.  Exactly one unbracketed thread-depth variable must
    be defined, and the drill depth's, which governs, exactly once and bare.
    """
    joined = "\n".join(definitions.values())
    if (
        joined.count(_THREAD_DEPTH_TOKEN) != 1
        or f"({_THREAD_DEPTH_TOKEN}" in joined
        or joined.count(_DRILL_DEPTH_TOKEN) != 1
        or f"({_DRILL_DEPTH_TOKEN}" in joined
    ):
        raise RuntimeError(
            f"expected one bare {_THREAD_DEPTH_TOKEN} and one bare "
            f"{_DRILL_DEPTH_TOKEN} in the tap callout's definitions: {definitions!r}"
        )
    return {
        part: text.replace(_THREAD_DEPTH_TOKEN, f"({_THREAD_DEPTH_TOKEN})")
        for part, text in definitions.items()
    }


def thread_extent_definitions(definitions: dict[int, str]) -> dict[int, str]:
    """The callout's definitions with the thread's extent,
    ``TAP_EXTENT_CALLOUT``, written into the empty below definition, so it
    prints as a row under the thread, and every other definition as it was.

    The prefix definition must hold the thread depth (the row the extent
    reads under is the thread's), the below definition must be empty, and
    nothing may state the extent yet (draw_sm_knife_mount's reason row).
    """
    if (
        _THREAD_DEPTH_TOKEN not in definitions[_CALLOUT_PREFIX_DEFINITION]
        or definitions[_CALLOUT_BELOW_DEFINITION].strip()
        or any(TAP_EXTENT_CALLOUT in text for text in definitions.values())
    ):
        raise RuntimeError(
            f"expected {_THREAD_DEPTH_TOKEN} in the prefix definition, an empty "
            f"below definition and no {TAP_EXTENT_CALLOUT!r} in the tap callout's "
            f"definitions: {definitions!r}"
        )
    return {**definitions, _CALLOUT_BELOW_DEFINITION: TAP_EXTENT_CALLOUT}


def _write_tap_definition(
    display: Any,
    wanted_of: Callable[[dict[int, str]], dict[int, str]],
    *,
    failure: str,
    success: str,
) -> None:
    """Write the one callout definition ``wanted_of`` changes and read all
    four back: every other definition, the process prefix and the bare drill
    depth included, must hold as it was."""
    before = {part: str(display.GetText(part) or "") for part in _CALLOUT_DEFINITION_PARTS}
    wanted = wanted_of(before)
    (part,) = [part for part in before if wanted[part] != before[part]]
    display.SetText(_CALLOUT_DEFINITION_PARTS[part], wanted[part])
    after = {part: str(display.GetText(part) or "") for part in _CALLOUT_DEFINITION_PARTS}
    if after != wanted:
        raise RuntimeError(
            f"thumb-screw tap {failure}: wanted {wanted!r}, read {after!r}"
        )
    _telemetry.success(f"thumb-screw tap {success}: definition {part} {wanted[part]!r}")


def _reference_thread_depth(display: Any) -> None:
    """Bracket the native callout's thread depth as REF, in the definition.

    Only the definition holding the thread depth is written; the readback
    must hold all four, the process prefix and the bare drill depth included.
    """
    _write_tap_definition(
        display,
        reference_thread_depth_definitions,
        failure="thread depth did not persist as REF",
        success="thread depth bracketed REF",
    )


def _state_thread_extent(display: Any) -> None:
    """Write the thread's extent as the callout's row under the thread
    (drawing-guidelines.md rule 7: on the feature, not a general note).

    Only the below definition is written; the readback must hold all four,
    the bracketed REF thread depth included.
    """
    _write_tap_definition(
        display,
        thread_extent_definitions,
        failure="extent row did not persist",
        success="extent row stated",
    )


def _check_tap_callout(display: Any) -> None:
    """Prove the callout states the tap, its depths, its process and the
    thread's extent."""
    resolved = {part: str(display.GetText(part) or "") for part in (1, 2, 3, 4)}
    if not _tap_callout_resolved(resolved):
        raise RuntimeError(
            f"thumb-screw tap callout does not state {TAP_PROCESS} "
            f"{_TAP_THREAD_TEXT}-{TAP_SPEC.thread_class} to "
            f"({TAP_LENGTH:.{TAP_DEPTH_PLACES}f}) REF over a bare "
            f"{TAP_DRILL_DEPTH:.{TAP_DEPTH_PLACES}f} drill, {TAP_EXTENT_CALLOUT} "
            f"under the thread: {resolved!r}"
        )
    _telemetry.success(f"thumb-screw tap callout reads {resolved!r}")


def _groove_root_ink_problem(segments: list[Segment], line_x: float) -> str | None:
    """Why the groove root Ø's ink does not read as a diameter across the
    groove, or None.

    Its dimension line stands at ``line_x`` from one root to the other and
    leaves neither; one extension line runs from each root, starting at the
    groove, out to that line; and it draws nothing else: no leg out of the
    groove, no shoulder under a text.
    """
    slop = GROOVE_ROOT_INK_SLOP
    groove_x = _side_x(GROOVE_X)
    line_ys: list[float] = []
    extension_xs: dict[float, list[float]] = {root: [] for root in GROOVE_ROOT_SHEET_YS}
    for (x0, y0), (x1, y1) in segments:
        if abs(x0 - line_x) <= slop and abs(x1 - line_x) <= slop:
            line_ys += [y0, y1]
            continue
        roots = [
            root
            for root in GROOVE_ROOT_SHEET_YS
            if abs(y0 - root) <= slop and abs(y1 - root) <= slop
        ]
        if not roots:
            return (
                f"stroke ({x0 * 1000:.2f}, {y0 * 1000:.2f})-({x1 * 1000:.2f}, "
                f"{y1 * 1000:.2f}) mm is neither its dimension line nor a root's "
                "extension line"
            )
        extension_xs[roots[0]] += [x0, x1]
    low, high = GROOVE_ROOT_SHEET_YS
    if not line_ys:
        return f"no dimension line at x {line_x * 1000:.2f} mm"
    if abs(min(line_ys) - low) > slop or abs(max(line_ys) - high) > slop:
        return (
            f"dimension line spans y {min(line_ys) * 1000:.2f}..{max(line_ys) * 1000:.2f}"
            f" mm, not root to root, {low * 1000:.2f}..{high * 1000:.2f} mm"
        )
    for root, xs in extension_xs.items():
        if not xs:
            return f"no extension line from the root at y {root * 1000:.2f} mm"
        if (
            min(xs) < groove_x - slop
            or min(xs) > groove_x + EXTENSION_START_GAP + slop
            or max(xs) < line_x - slop
        ):
            return (
                f"extension line at y {root * 1000:.2f} mm spans x "
                f"{min(xs) * 1000:.2f}..{max(xs) * 1000:.2f} mm, not the groove at "
                f"{groove_x * 1000:.2f} mm out to the dimension line"
            )
    return None


def _prove_groove_root_diameter(annotation: Any) -> None:
    """Prove the sheet's groove root Ø is the part's doubled distance, by
    type, by value and by ink: a diameter-family display dimension shown
    doubled, measuring the root Ø, printed across the groove, root to root."""
    display = _early_bound(
        _early_bound(annotation, "IAnnotation").GetSpecificAnnotation(),
        "IDisplayDimension",
    )
    kind, diametric = int(display.Type2), bool(display.Diametric)
    if kind not in _DOUBLED_DISTANCE_TYPES or not diametric:
        raise RuntimeError(
            f"GrooveRootDia is dimension type {kind}, Diametric {diametric}: not "
            "the part's doubled distance from the groove's axis to its root"
        )
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    measured_mm = abs(float(dimension.SystemValue)) * 1000.0
    if abs(measured_mm - GROOVE_ROOT_DIA) > GROOVE_ROOT_VALUE_SLOP_MM:
        raise RuntimeError(
            f"GrooveRootDia measures {measured_mm:g} mm, not the groove root Ø "
            f"{GROOVE_ROOT_DIA:g} mm: a single distance or another dimension"
        )
    line_x = SIDE_KEEP["GrooveRootDia"][0]
    segments = dimension_segments(annotation)
    problem = _groove_root_ink_problem(segments, line_x)
    if problem is not None:
        raise RuntimeError(f"GrooveRootDia does not print across the groove: {problem}")
    _telemetry.success(
        f"groove root Ø is {_DOUBLED_DISTANCE_TYPES[kind]} ({kind}), Diametric, "
        f"DisplayAsLinear {bool(display.DisplayAsLinear)}, {measured_mm:g} mm, "
        f"{len(segments)} strokes standing root to root at x {line_x * 1000:.2f} mm"
    )


# The template centre-marks every hole as each view is placed (the knife
# mount's convention, #913), so the end view arrives with its tap marked:
# AutoInsertCenterMarks2 printed a second mark over it (DetailItem347/350,
# 2026-10-12 farm sheet), and so did an explicit InsertCenterMark3 on the
# drill circle (run05: found 2).  The sheet adds none; it proves the one.
_CENTER_MARK_ANNOTATION = 13  # swAnnotationType_e.swCenterMarkSym
# How far the mark's ink centre may sit from the tap's axis on the sheet.
CENTER_MARK_AXIS_SLOP = 0.0005


def _annotation_segments(annotation: Any, label: str) -> list[Segment]:
    data = _early_bound(annotation, "IAnnotation").GetDisplayData()
    if data is None:
        raise RuntimeError(f"{label} has no display data")
    data = _early_bound(data, "IDisplayData")
    lines = [
        tuple(float(value) for value in data.GetLineAtIndex2(index))
        for index in range(int(data.GetLineCount()))
    ]
    if not lines:
        raise RuntimeError(f"{label} draws no line")
    if any(len(line) < 10 or not all(math.isfinite(v) for v in line) for line in lines):
        raise RuntimeError(f"{label} has incomplete line coordinates")
    return [((line[4], line[5]), (line[7], line[8])) for line in lines]


def _ink_centre(annotation: Any, label: str) -> tuple[float, float]:
    """Centre of a symmetric centre mark's sheet-space ink."""
    segments = _annotation_segments(annotation, label)
    xs = [point[0] for stroke in segments for point in stroke]
    ys = [point[1] for stroke in segments for point in stroke]
    return ((min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0)


def _prove_tap_centre_mark(adapter: Any, view: Any, drill_edge: Any) -> Any:
    """Prove the end view carries exactly one centre mark, on the tap's axis
    (the drill circle's centre projected to the sheet)."""
    curve = _early_bound(drill_edge, "IEdge").GetCurve()
    if curve is None:
        raise RuntimeError("the thumb-screw tap drill edge has no curve")
    circle = _early_bound(curve, "ICurve").CircleParams
    if circle is None or len(circle) < 3:
        raise RuntimeError("the thumb-screw tap drill edge reports no circle centre")
    axis = model_point_in_view(
        adapter,
        view,
        (float(circle[0]), float(circle[1]), float(circle[2])),
        label="thumb-screw tap axis",
    )
    marks = tuple(
        _early_bound(view, "IView").GetAnnotationsByType(_CENTER_MARK_ANNOTATION) or ()
    )
    if len(marks) != 1:
        raise RuntimeError(
            f"expected one tap centre mark on the end view, found {len(marks)}"
        )
    centre = _ink_centre(marks[0], "thumb-screw tap centre mark")
    offset = math.hypot(centre[0] - axis[0], centre[1] - axis[1])
    if offset > CENTER_MARK_AXIS_SLOP:
        raise RuntimeError(
            f"the end view's centre mark sits {offset * 1000.0:.2f} mm off the tap "
            f"axis: mark {centre}, axis {axis}"
        )
    return _early_bound(marks[0], "IAnnotation")


def _is_rod_bore_cylinder(parameters: tuple[float, ...]) -> bool:
    """Only the Ø5.2 Y-axis bore, never the X-axis tap/spigot."""
    return (
        len(parameters) == 7
        and all(math.isfinite(v) for v in parameters)
        and max(
            abs(parameters[0]), abs(parameters[2]),
            abs(parameters[3]), abs(parameters[5]),
            abs(abs(parameters[4]) - 1.0),
            abs(parameters[6] - ROD_BORE_DIA / 2000.0),
        ) <= BORE_FACE_SLOP_M
    )


def _rod_bore_cylinder_face(feature: Any, *, context: str) -> Any:
    """Census the true bore in either the source or the view's feature topology."""
    matches = []
    for raw in _early_bound(feature, "IFeature").GetFaces() or ():
        face = _early_bound(raw, "IFace2")
        surface = face.GetSurface()
        if surface is None:
            raise RuntimeError(f"RodBore {context} face has no native surface")
        surface = _early_bound(surface, "ISurface")
        cylinder = surface.IsCylinder()
        if type(cylinder) is not bool:
            raise RuntimeError("RodBore surface IsCylinder did not return a native BOOL")
        if cylinder is True and _is_rod_bore_cylinder(
            tuple(float(v) for v in (surface.CylinderParams or ()))
        ):
            matches.append(face)
    if len(matches) != 1:
        raise RuntimeError(
            f"expected one RodBore Y-axis cylindrical face in {context}, "
            f"found {len(matches)}"
        )
    return matches[0]


def _rod_bore_face(adapter: Any, view: Any) -> Any:
    native = _early_bound(view, "IView")
    model = native.ReferencedDocument
    if model is None:
        raise RuntimeError("rod bore axis view has no referenced part")
    feature = _early_bound(model, "IPartDoc").FeatureByName("RodBore")
    if feature is None:
        raise RuntimeError("rod bore axis source has no RodBore feature")
    source_face = _rod_bore_cylinder_face(feature, context="source part")
    # Map the feature, then reacquire its face in this rotated view's topology.
    # IView::GetCorresponding explicitly supports IFeature; IFeature::GetFaces
    # returns its owned faces. Direct GetCorrespondingEntity(source_face) was
    # null on retry13 despite the source cylinder passing the full census.
    in_view_feature = native.GetCorresponding(feature)
    if in_view_feature is None:
        raise RuntimeError("RodBore feature has no end-view correspondence")
    in_view = _rod_bore_cylinder_face(in_view_feature, context="end view")
    source = _early_bound(
        _early_bound(model, "IModelDoc2").Extension, "IModelDocExtension"
    ).GetCorrespondingEntity2(in_view)
    if source is None or int(adapter.swApp.IsSame(source, source_face)) != 1:
        raise RuntimeError("RodBore cylinder lost its source/view identity")
    return in_view


def _bore_axis_ink_problem(
    segments: list[Segment], corners: tuple[tuple[float, float], tuple[float, float]]
) -> str | None:
    slop = CENTER_MARK_AXIS_SLOP
    left, right = sorted(corners)
    if not segments:
        return "bore centreline draws no lines"
    if any(abs(point[1] - left[1]) > slop for stroke in segments for point in stroke):
        return "bore centreline is not on the projected Y axis"
    xs = [point[0] for stroke in segments for point in stroke]
    if min(xs) > left[0] + slop or max(xs) < right[0] - slop:
        return "bore centreline does not span both hex corners"
    if min(xs) < left[0] - 0.005 or max(xs) > right[0] + 0.005:
        return "bore centreline extends beyond the corner-side stubs"
    return None


def _add_rod_bore_axis(adapter: Any, view: Any, tap_mark: Any) -> tuple[Any, Any]:
    """Native cylinder axis plus a small tap cross, not two coincident marks."""
    native = _early_bound(view, "IView")
    if native.GetAnnotationsByType(15):  # swAnnotationType_e.swCenterLine
        raise RuntimeError("fixture end view already has a centreline")
    mark = _early_bound(tap_mark.GetSpecificAnnotation(), "ICenterMark")
    mark.UseDocDisplaySettings = False
    mark.ShowLines = False
    if mark.UseDocDisplaySettings is not False or mark.ShowLines is not False:
        raise RuntimeError("tap centre mark retained coincident extended axis lines")
    face = _rod_bore_face(adapter, native)
    axis = add_view_centerline(
        adapter, native, entity=face, label="rod bore Y axis through hex corners"
    )
    return axis, face


def _prove_rod_bore_axis(adapter: Any, view: Any, axis: Any, face: Any, tap_mark: Any) -> None:
    native = _early_bound(view, "IView")
    raw_annotation = _early_bound(axis, "ICenterLine").GetAnnotation()
    if raw_annotation is None:
        raise RuntimeError("rod bore native centreline has no annotation")
    annotation = _early_bound(raw_annotation, "IAnnotation")
    lines = tuple(native.GetAnnotationsByType(15) or ())
    if (
        len(lines) != 1
        or int(adapter.swApp.IsSame(lines[0], annotation)) != 1
        or int(annotation.OwnerType) != 0  # swAnnotationOwner_DrawingView
    ):
        raise RuntimeError("rod bore axis is not the end view's one native centreline")
    if annotation.IsDangling() is not False:
        raise RuntimeError("rod bore centreline dangling state is not measured False")
    _assert_attached_to(
        adapter, annotation, face, entity_type="FACE", what="rod bore centreline",
        label="RodBore Y-axis cylinder", expected_leaders=0,
    )
    corners = tuple(
        model_point_in_view(
            adapter, native, (0.0, y / 1000.0, 0.0), label="rod bore axis hex corner"
        )
        for y in (-HEX_CORNER_RADIUS, HEX_CORNER_RADIUS)
    )
    problem = _bore_axis_ink_problem(_annotation_segments(annotation, "rod bore axis"), corners)
    if problem is not None:
        raise RuntimeError(problem)
    mark = _early_bound(tap_mark.GetSpecificAnnotation(), "ICenterMark")
    if mark.UseDocDisplaySettings is not False or mark.ShowLines is not False:
        raise RuntimeError("tap centre mark regained its coincident extended lines")
    # ShowLines' readback alone is not ink proof: no tap-mark arm may still
    # reach the corners alongside the separate, model-associated bore axis.
    centre = _ink_centre(tap_mark, "tap cross")
    if any(
        math.dist(point, centre) >= _END_HALF_HEIGHT
        for stroke in _annotation_segments(tap_mark, "tap cross") for point in stroke
    ):
        raise RuntimeError("tap cross still carries a full-length coincident axis")
    _telemetry.success(
        "one model-associated RodBore Y-axis centreline spans the hex corners; "
        "one small X-axis tap cross, no extended duplicate"
    )


def _enforce_fixture_text_on_line(report: Path) -> None:
    """Gate the existing audit's whole-sheet text-on-line findings locally.

    finalize_drawing has already collected/audited the exported PDF and
    written its declared report.  Consume those findings, never recollect
    COM or interpret text/line geometry a second way.  Native15's real
    radius/spigot crossing must fail even in REPORT mode; missing 0.25 mm
    view edges on this 0.18 mm sheet are unrelated and remain report-only.
    """
    content = json.loads(report.read_text(encoding="utf-8"))
    if (
        not isinstance(content, dict)
        or type(content.get("schema")) is not int
        or content["schema"] != REPORT_SCHEMA
        or content.get("stem") != PART_STEM
        or content.get("mode") not in ("report", "gate")
        or not isinstance(content.get("findings"), list)
        or not isinstance(content.get("sheets"), list)
        or not content["sheets"]
        or not isinstance(content.get("summary"), dict)
    ):
        raise RuntimeError("fixture layout audit report is missing or malformed")
    sheets = content["sheets"]
    if any(
        not isinstance(sheet, dict)
        or sheet.get("stem") != PART_STEM
        or not isinstance(sheet.get("sheet"), str)
        or not sheet["sheet"]
        for sheet in sheets
    ):
        raise RuntimeError("fixture layout audit report has malformed sheets")
    sheet_names = {sheet["sheet"] for sheet in sheets}
    findings = content["findings"]
    if any(
        not isinstance(finding, dict)
        or finding.get("stem") != PART_STEM
        or finding.get("severity") not in ("gating", "advisory")
        or any(
            not isinstance(finding.get(key), str)
            for key in ("kind", "sheet", "a", "b", "detail")
        )
        or not finding["kind"]
        or finding["sheet"] not in sheet_names
        for finding in findings
    ):
        raise RuntimeError("fixture layout audit report has malformed findings")
    summary = content["summary"]
    counts = summary.get("findings")
    if (
        len(sheet_names) != len(sheets)
        or type(summary.get("sheets")) is not int
        or summary["sheets"] != len(sheets)
        or not isinstance(counts, dict)
        or any(
            not isinstance(kind, str) or type(count) is not int or count <= 0
            for kind, count in counts.items()
        )
        or counts != Counter(finding["kind"] for finding in findings)
        or type(summary.get("gating")) is not int
        or summary["gating"] != sum(finding["severity"] == "gating" for finding in findings)
    ):
        raise RuntimeError("fixture layout audit report is incomplete")
    crossed = [finding for finding in findings if finding["kind"] == "text-on-line"]
    if crossed:
        raise RuntimeError(
            f"fixture layout audit failed: {len(crossed)} text-on-line finding(s):\n"
            + "\n".join(f"  - {finding['detail']}" for finding in crossed)
        )


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open output-fixture source", await adapter.open_model(str(SOURCE)))
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
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Output Fixture Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "output fixture; 7/16 hex brass; drilled rod bore; wire groove; #4-40 tap",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    side = place_view(adapter, str(SOURCE), "*Top", *SIDE_CENTER, scale=VIEW_SCALE)
    end = place_view(adapter, str(SOURCE), "*Right", *END_CENTER, scale=VIEW_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (side, end, iso):
        set_hidden_lines_removed(adapter, view)
    _project_end_view(adapter, side, end)

    side_annotations = curate_view_dimensions(
        adapter,
        side,
        keep=SIDE_KEEP,
        view_label="side",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    end_annotations = curate_view_dimensions(
        adapter,
        end,
        keep=END_KEEP,
        view_label="end",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    # Places (and so each dimension's general row) are authored on the part;
    # the sheet only proves the import kept them.
    assert_imported_precision(
        adapter, [*side_annotations, *end_annotations], DRAWING_PRECISION_BY_NAME
    )
    # Each below its value: the bore's process, and the groove radius's
    # profile under its LIMIT (read back in _prove_groove_radius).
    set_dimension_callouts(
        adapter,
        side_annotations,
        {"RodBoreDia": ROD_BORE_CALLOUT, "GrooveRadius": GROOVE_RADIUS_CALLOUT},
    )
    # The flats are the bar's as supplied: a stock reference, not a size the
    # shop holds to three places.  The overall length is the part's driven
    # sum of the bore's two stations: a reference, never a third control.
    side_by_name = {dimension_name(adapter, a): a for a in side_annotations}
    end_by_name = {dimension_name(adapter, a): a for a in end_annotations}
    by_name = {**side_by_name, **end_by_name}
    for name in sorted(REFERENCE_DIMENSIONS):
        set_reference_dimension(
            adapter, by_name[name], label=f"MHA-MG-06 {name} reference"
        )
    if not auto_center_marks(adapter, side, holes=True, size=0.0025):
        raise RuntimeError("failed to add the rod bore's center mark to the side view")
    # The tap drill's edge on the spigot face: the one visible circle of the
    # Hole Wizard feature from the end.  Its axis carries the view's one
    # centre mark, and the native callout prints the drill row, under it the
    # process on the thread row, and under that the thread's extent; both
    # depths print at one place, the thread's bracketed as REF.
    tap_drill = visible_circle_edge(adapter, end, TAP_DRILL_DIA)
    tap_mark = _prove_tap_centre_mark(adapter, end, tap_drill)
    bore_axis, bore_face = _add_rod_bore_axis(adapter, end, tap_mark)
    tap_callout = add_native_hole_callout(
        adapter,
        end,
        edge=tap_drill,
        callout_xy=TAP_CALLOUT_XY,
        label="#4-40 thumb-screw tap",
        process=TAP_PROCESS,
    )
    _reference_thread_depth(tap_callout)
    _state_thread_extent(tap_callout)
    set_hole_callout_precision(
        tap_callout, TAP_CALLOUT_PRECISION, label="#4-40 thumb-screw tap depths"
    )
    _place_groove_radius(
        adapter, side_by_name["GrooveRadius"], side_by_name["GrooveStation"]
    )
    # Rebuilt, final frame/ink: these proofs never exempt the root Ø or tap.
    _prove_end_stock_reference(adapter, end, end_by_name["HexAf"])
    _prove_tap_centre_mark(adapter, end, tap_drill)
    _prove_rod_bore_axis(adapter, end, bore_axis, bore_face, tap_mark)
    _check_tap_callout(tap_callout)
    _prove_groove_radius(
        adapter, side, side_by_name["GrooveRadius"], side_by_name["GrooveStation"]
    )
    _prove_groove_root_diameter(side_by_name["GrooveRootDia"])
    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)

    artifacts = await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Output Fixture Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        # The blind tap pins no descriptive note (``AUTO_TAPPED_HOLE_NOTES``);
        # the sweep proves none reached any sheet.
        redundant_note_substrings=(TAPPED_HOLE_NOTE,),
        expected_redundant_notes=AUTO_TAPPED_HOLE_NOTES,
    )
    _enforce_fixture_text_on_line(layout_report_path(PART_STEM))
    return artifacts


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
