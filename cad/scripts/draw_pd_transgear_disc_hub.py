r"""Create the manufacturing drawing for the transgear disc hub (MHA-PD-17).

The edge view is the ``*Top`` orientation turned a quarter turn so the hub's
axis lies horizontal, as it sits in the lathe (drawing-guidelines.md rule 11 (turned parts read like the lathe)): the hub front
face on the left, the flange and the spigot on the right.  It carries the
turned profile: the three diameters beside their steps, the spigot's and
flange's lengths from the flange's rear face, the overall (spigot end to hub
front), both lengths printed to the disc cluster stack's band, and the
flange's rear face and the
spigot's end square to the bore, datum A.  Looking down on +Y it sees the
radial oil hole end-on, so it also carries the hole's size and its
match-drill callout, and the station of the key pin's chord hole, which
the oil hole shares (a hidden reference line on the hub's O.D.).  The face
view is the ``*Back`` orientation (looking at the hub front) turned to
match -- exactly the third-angle LEFT view of that profile -- so it sits
on the profile's axis to its left and carries the reamed bore (datum A)
and the screw holes on their printed bolt circle.  SECTION A-A, cut across
the edge view at that station and removed right of it, carries the chord
hole: its ream with the pin's press fit, its #56 knockout, its chord
offset and its stop.

The bore imports the model's sleeve-matched dimension and native band.
Decimal-inch sheet (#290); the model keeps its millimetre nominals.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import math
import sys
import textwrap
from typing import Any

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    auto_center_marks,
    dimension_name,
    place_view,
    view_name,
)

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
from _drawing_detail_crop import native_circle_geometry
from _drawing_dimensions import assert_imported_precision, set_dimension_callouts
from _drawing_edges import ViewEdge, ViewEdges, scan_view_edges
from _drawing_gdt import add_datum_feature, add_feature_control_frame
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_leaders import set_near_side_diameter
from _drawing_projection import model_point_in_view, model_points_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_sections import create_section_view
from _drawing_view_display import set_hidden_lines_removed
from _gear_drawing_entities import visible_circle_edge
from _gtol_face_read import face_geometry
from _gtol_planar import PlanarFace
from _layout_geometry import Box
from _machinist_review_mode import MachinistReviewMode
from _paths import CAD_ROOT
from _part_properties import part_drawing_unit
from _section_axis import position_section_caption
from _session import run_build
import _telemetry
from pd_transgear_disc_hub_geometry import BOLT_CIRCLE_DIA
from pd_transgear_disc_hub_spec import (
    BORE_CALLOUT_BELOW,
    BORE_DATUM,
    BORE_DIA,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    FLANGE_DIA,
    FLANGE_THICK,
    FLANGE_THICK_CALLOUT,
    GEOMETRIC_TOLERANCES_IN,
    HUB_DIA,
    HUB_DIA_CALLOUT_BELOW,
    HUB_FRONT_Z,
    HUB_LENGTH_CALLOUT,
    KEY_PIN_CALLOUT_BELOW,
    KEY_PIN_CHORD_OFFSET,
    KEY_PIN_DRILL_CALLOUT_BELOW,
    KEY_PIN_STOP,
    KEY_PIN_Z,
    OIL_HOLE_CALLOUT_BELOW,
    SCREW_HOLE_CALLOUT_ABOVE,
    SCREW_HOLE_CALLOUT_BELOW,
    SPIGOT_CALLOUT_BELOW,
    SPIGOT_DIA,
    SPIGOT_LENGTH,
    SPIGOT_LENGTH_CALLOUT,
    STACK_NOTE,
    STACK_TEXT,
)


# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["pd_transgear_disc_hub"]
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

# A Ø1.01 × .539 part: 3:1 keeps the #0-80 holes, the #57 oil hole and the
# thin flange legible with two views across the landscape sheet.
SHEET_SCALE = (3.0, 1.0)
VIEW_SCALE = (3, 1)
_S = SHEET_SCALE[0] / SHEET_SCALE[1] / 1000.0  # sheet metres per model mm
# *Top turned +90 degrees: model -Z (the hub front) to paper-left, model +X
# up.  *Back turned -90 degrees: model +X up, model +Y (the oil hole) right,
# which is the third-angle left view of that profile.
SIDE_VIEW_ANGLE = math.pi / 2.0
END_VIEW_ANGLE = -math.pi / 2.0
AXIS_Y = 0.165
SIDE_CENTER = (0.225, AXIS_Y)
END_CENTER = (0.090, AXIS_Y)
# Right of the flange's diameter, below the overall's stack callout: the
# view's top-left arc (run 20261028T041908587Z) sat under the callout's
# widest line, so the view drops below that row and steps right of its end.
ISO_CENTER = (0.379, 0.188)


def _side_x(z_mm: float) -> float:
    """Sheet X of a model-Z station on the edge view (the view centres on the
    part's z span, HUB_FRONT_Z..SPIGOT_LENGTH)."""
    return SIDE_CENTER[0] + (z_mm - (HUB_FRONT_Z + SPIGOT_LENGTH) / 2.0) * _S


HUB_FRONT_X = _side_x(HUB_FRONT_Z)
SPIGOT_END_X = _side_x(SPIGOT_LENGTH)
_FLANGE_R = FLANGE_DIA / 2.0 * _S
_SPIGOT_R = SPIGOT_DIA / 2.0 * _S

# The stack note the overall's and the spigot length's callouts link;
# top-left anchored in the empty field above the face view, left of the
# overall's callout.
_NOTE_WIDTH = 92


def _numbered(number: int, text: str) -> str:
    return "\n".join(
        textwrap.wrap(
            f"{number}. {text}",
            width=_NOTE_WIDTH,
            subsequent_indent="   ",
            break_on_hyphens=False,
        )
    )


NOTES_TEXT = _numbered(STACK_NOTE, STACK_TEXT)
NOTES_XY = (0.020, 0.262)

# Every size and callout sits outside the silhouettes.
# - Face view: the bolt circle diameter above-left, its arrows on the
#   circle's centreline drawn through the three hole centres (machinist
#   review: with no circle they ended in air; near-side, its shelf ran
#   into the screw holes' callout), the screw-hole size (3X,
#   drilled through the flange) above-right, each with its callout under
#   it.  The bore's size and fit hang well below-right, one arrow on the
#   bore (near-side): through the centre its line crossed the bolt circle's
#   and ran almost on the vertical centreline (machinist review r6).
#   SolidWorks lands that arrow on the bore's radius toward the shelf's near
#   end, the block's lower-left corner, so the corner stands on the bore's
#   -60° ray, below the oil hole's block: the leader leaves the bore
#   down-right, clear of both centrelines.
# - Edge view: the hub's diameter inline left of the hub front face; the
#   spigot's and then the flange's inline right of the spigot's end, the
#   flange's outermost so the spigot's extension lines end inside it, the
#   spigot's callout under its text, clear of the part, the block set a
#   little low between its extension lines to leave the spigot end's frame
#   room above it.  One row above: the key-pin hole's station from the hub
#   front face, its text between its extension lines left of the flange, and
#   the spigot's length from the flange's rear face, its text right of the
#   spigot, its whole callout block right of the spigot end's extension line
#   (the overall's rises through that row) and so clear of the flange's
#   dimension line.  The overall, printed to the disc cluster stack's band, on the
#   next row up, outermost, its text and stack callout right of the spigot end's
#   extension line.  Its ends are the spigot's and the hub's +X corners, so
#   from a row above its extension lines rise off the part; from below they
#   ran down across the hub front and the spigot end.  Below the part: the
#   flange's thickness, its text and reach callout wholly right of the
#   flange's extension lines (machinist review: they ran through the text),
#   under the flange's frame; and the oil hole's size with its match-drill
#   callout below-left of the hole, its block ending left of the hole so its
#   leader leaves the block's lower-right corner (SolidWorks' shoulder) and
#   rises steeply to the hole through the hub's underside, crossing no
#   dimension (machinist review: from a block centred under the hole the
#   leader left its right end and ran through the flange thickness), and
#   leaning off section A-A's cutting line at the same station.
# - The two perpendicularity frames stand right of the spigot's end, each
#   level with its leader's landing so the leader runs square onto its face's
#   line: the flange's below the spigot, between the spigot's and the
#   flange's extension lines; the spigot end's inside the spigot's, between
#   its upper extension line and its diameter's text, left of that
#   dimension's line.
# Estimated (width, height) of the bore's block: the two size rows, REAM
# THRU, the fit and the wall row (5.3 mm a row, 2.4 mm a character, as run
# 20261101T054343686Z printed the seven-row block; the fit row is the
# widest).  The shoulder sits on the bore's -60° ray, the block's top under
# the oil hole's block and its right end left of the title block.
BORE_TEXT_BLOCK = (0.058, 0.027)
_BORE_SHOULDER_DROP = 0.108
_BORE_SHOULDER = (
    END_CENTER[0] + _BORE_SHOULDER_DROP / math.tan(math.radians(60.0)),
    AXIS_Y - _BORE_SHOULDER_DROP,
)
END_KEEP = {
    "BoltCircleDia": (END_CENTER[0] - 0.030, AXIS_Y + _FLANGE_R + 0.016),
    "ScrewHoleDia": (END_CENTER[0] + 0.036, AXIS_Y + _FLANGE_R + 0.016),
    "BoreDia": (
        _BORE_SHOULDER[0] + BORE_TEXT_BLOCK[0] / 2.0,
        _BORE_SHOULDER[1] + BORE_TEXT_BLOCK[1] / 2.0,
    ),
}
_KEY_PIN_X = _side_x(KEY_PIN_Z)
# Estimated (width, height) of the oil hole's and the flange thickness's
# text blocks (3.5 mm caps, 2.61 mm advance).
OIL_HOLE_TEXT_BLOCK = (0.076, 0.017)
FLANGE_THICK_TEXT_BLOCK = (0.047, 0.017)
# The hub O.D.'s size and the wall it holds, in the lane between the face
# view's datum tag and the hub, 4 mm clear of the hub's front face.
HUB_DIA_TEXT_BLOCK = (0.040, 0.016)
_OIL_HOLE_SHOULDER = (_KEY_PIN_X - 0.008, AXIS_Y - _FLANGE_R - 0.033)
SIDE_KEEP = {
    "HubDia": (HUB_FRONT_X - 0.004 - HUB_DIA_TEXT_BLOCK[0] / 2.0, AXIS_Y),
    "SpigotDia": (SPIGOT_END_X + 0.040, AXIS_Y - 0.003),
    # Clear the spigot's whole fit-callout box, not just its dimension line.
    "FlangeDia": (SPIGOT_END_X + 0.083, AXIS_Y),
    "FlangeThick": (
        _side_x(0.0) + 0.004 + FLANGE_THICK_TEXT_BLOCK[0] / 2.0,
        AXIS_Y - _FLANGE_R - 0.014,
    ),
    "KeyPinStation": (
        (HUB_FRONT_X + _KEY_PIN_X) / 2.0,
        AXIS_Y + _FLANGE_R + 0.009,
    ),
    "SpigotLength": (SPIGOT_END_X + 0.026, AXIS_Y + _FLANGE_R + 0.009),
    "HubLength": (SPIGOT_END_X + 0.056, AXIS_Y + _FLANGE_R + 0.026),
    "OilHoleDia": (
        _OIL_HOLE_SHOULDER[0] - OIL_HOLE_TEXT_BLOCK[0] / 2.0,
        _OIL_HOLE_SHOULDER[1] + OIL_HOLE_TEXT_BLOCK[1] / 2.0,
    ),
}
# Datum A on the bore's round side, its symbol right of the flange, in the
# lane between the face view and the edge view's Ø.540: SolidWorks' own
# placement of an axis datum put the tag inside the flange, on the
# lower-left hole (machinist review).  Once the symbol moves, SolidWorks
# re-solves the triangle onto the bore circle on the RADIAL line from the
# bore centre toward the symbol, whatever landing was requested: with the
# symbol at atan2(.015, _FLANGE_R + .014) = 15.95°, a 15° request printed
# at 15.95° (run 20261101T070124857Z), and a 0° request still printed its
# tip there, the readback's nearest point being the triangle's base corner
# 1.4 mm along the tangent (run 20261101T082409337Z).  So the landing is
# requested at that radial projection itself (_datum_a_landing).  The
# leader climbs from it to the symbol above the lower-right hole's centre
# mark, on the bore's round side.
DATUM_A_SYMBOL = (END_CENTER[0] + _FLANGE_R + 0.014, AXIS_Y + 0.015)
DIMENSION_CALLOUTS_BELOW = {
    "BoreDia": BORE_CALLOUT_BELOW,
    "HubDia": HUB_DIA_CALLOUT_BELOW,
    "ScrewHoleDia": SCREW_HOLE_CALLOUT_BELOW,
    "OilHoleDia": OIL_HOLE_CALLOUT_BELOW,
    "SpigotDia": SPIGOT_CALLOUT_BELOW,
    "SpigotLength": SPIGOT_LENGTH_CALLOUT,
    "HubLength": HUB_LENGTH_CALLOUT,
    "FlangeThick": FLANGE_THICK_CALLOUT,
}
DIMENSION_CALLOUTS_ABOVE = {"ScrewHoleDia": SCREW_HOLE_CALLOUT_ABOVE}
# The bolt circle's centreline: thin, black, centre-line font (Y14.2), in
# the face view's sketch, straight to the database so no inference snaps it
# onto a hole (draw_ch_connecting_rod's detail fence recipe).
CENTER_LINE_STYLE = 4  # swLineStyles_e.swLineCENTER
CENTER_LINE_WEIGHT = 0  # swLineWeights_e.swLW_THIN

# SECTION A-A cuts across the hub at the key pin's station (rule 9: the
# chord hole runs through the bore's wall, which no outside view shows) and
# carries the chord hole's ream, knockout, chord offset and stop.  The
# cutting plane is the hidden station plane the hole's profile is sketched
# on, so those dimensions import from it.  On the edge view (model +X up,
# -Z left) that plane is the vertical at the station.  Drawn bottom to top
# (-X to +X), the line's arrows point right (draw_pd_transgear_feed_pinion:
# drawn top to bottom they point left), so the sight runs along model +Z,
# toward the flange; the section prints its cut face only, so the flange
# beyond never shows.
#
# SolidWorks sets each letter just past its arrow's tip: GetTextInfo's
# upper-left origin .0050 right of the tip and .0019 above the arrow, the
# letter CharHeight .00635 tall, the arrows .0120 long (r6 layout audit).
# That column (x .233-.239) is the flange's: its rear face's line, with the
# spigot length's extension line rising off it to y .2094 and the flange
# thickness's falling to .1017 (r6 audit), struck both letters when the line
# ended 2 mm past the hub's O.D. (r6 machinist review, rule 14).  So the
# line runs on past that ink each side: the upper letter between the spigot
# length's extension end and the overall's dimension line (y .2254), the
# lower under the flange thickness's extension end, each with its air.
SECTION_LABEL = "A"
SECTION_ARROW_LENGTH = 0.012
SECTION_LETTER_ORIGIN = (0.0050, 0.0019)
SECTION_LETTER_HEIGHT = 0.00635
SECTION_LETTER_AIR = 0.0045
REAR_FACE_INK_Y = (0.1017, 0.2094)
OVERALL_LINE_Y = 0.2254
_SECTION_ARROW_Y = (
    REAR_FACE_INK_Y[0] - SECTION_LETTER_AIR - SECTION_LETTER_ORIGIN[1],
    OVERALL_LINE_Y - SECTION_LETTER_AIR - SECTION_LETTER_ORIGIN[1],
)
_HUB_R_MM = HUB_DIA / 2.0
SECTION_LINE_MODEL = tuple(
    ((y - AXIS_Y) / _S, 0.0, KEY_PIN_Z) for y in _SECTION_ARROW_Y
)


def _side_view_xy(point_mm: tuple[float, float, float]) -> tuple[float, float]:
    """Sheet point of a model point on the edge view (model -Z left, +X up,
    the bore's axis on AXIS_Y)."""
    x, _y, z = point_mm
    return _side_x(z), AXIS_Y + x * _S


SECTION_LINE = tuple(_side_view_xy(point) for point in SECTION_LINE_MODEL)


def section_letter_box(tail: tuple[float, float]) -> Box:
    """The letter SolidWorks prints at the right-pointing arrow whose tail is
    ``tail``: one CharHeight square from its upper-left origin."""
    left = tail[0] + SECTION_ARROW_LENGTH + SECTION_LETTER_ORIGIN[0]
    top = tail[1] + SECTION_LETTER_ORIGIN[1]
    return Box(left, top - SECTION_LETTER_HEIGHT, left + SECTION_LETTER_HEIGHT, top)


# The section stands removed at the sheet's 3:1 (so its caption prints no
# scale) in the field right of the edge view's Ø1.05 and over the title
# block, which run 20261107T180459203Z left empty at x .290-.418, y
# .068-.124 (the isometric's shaded ink reaches down to y .147 from x .335).
# Seen along +Z with model +X up, model +Y runs right: the oil hole on the
# right, the key pin's chord hole on the left, the ream entering from the
# top -- the face view's frame.  _orient_section reads that frame back.
SECTION_CENTER = (0.370, 0.105)  # where the hub axis lands
SECTION_POSITION_TOL_M = 1e-4
# A projected 1 mm step reads off the sheet's axes by less than this.
_SECTION_FRAME_TOL_M = 1e-8


def _section_xy(x_mm: float, y_mm: float) -> tuple[float, float]:
    """Sheet point of the model point (``x_mm``, ``y_mm``) on the cutting
    plane, in the laid and centred section."""
    return (
        SECTION_CENTER[0] + y_mm * _S,
        SECTION_CENTER[1] + x_mm * _S,
    )


# The centrelines run 1 mm (3 on the sheet) past the O.D., as the hole's
# profile does past it; the chord's ream starts there.
SECTION_CENTERLINE_OVERRUN_MM = 1.0
_SECTION_REACH_MM = _HUB_R_MM + SECTION_CENTERLINE_OVERRUN_MM
# The chord hole's dimensions, imported from its station-plane profile,
# print left of the section, in the air between the flange thickness's
# block and the ring: the stop's text inline on its dimension line between
# the hub axis's and the stop's extension lines; the ream's size and fit
# beside the ream, under the Ø1.05's lower extension line (y .125), the
# knockout's beside the knockout, both left of the stop's line so their
# dimension lines run straight across the hole; the chord offset above the
# ring, its text right of the hub axis's extension line and clear of the
# chord hole's (r5 review: a line ran into the .17).
SECTION_KEEP = {
    "KeyPinChord": (
        SECTION_CENTER[0] + 0.019,
        _section_xy(_SECTION_REACH_MM, 0.0)[1] + 0.004,
    ),
    "KeyPinStop": (0.335, _section_xy(-KEY_PIN_STOP / 2.0, 0.0)[1]),
    "KeyPinDia": (0.3125, SECTION_CENTER[1] + 0.0065),
    "KeyPinDrillDia": (
        0.315,
        _section_xy(-(KEY_PIN_STOP + _SECTION_REACH_MM) / 2.0, 0.0)[1],
    ),
}
SECTION_CALLOUTS_BELOW = {
    "KeyPinDia": KEY_PIN_CALLOUT_BELOW,
    "KeyPinDrillDia": KEY_PIN_DRILL_CALLOUT_BELOW,
}
# Centrelines across the cut, each ending 1 mm past the O.D. where it crosses
# it: the bore's two, the horizontal one the oil hole's axis, and the chord
# hole's axis.  The section arrives centre-marked, the mark's arms running
# far past the ring through the dimensions, the caption and the isometric
# (r5 review, rule 14); the mark is deleted and these drawn instead.
_CENTER_MARK_ANNOTATION = 13  # swAnnotationType_e.swCenterMarkSym
_SECTION_CHORD_REACH_MM = (
    math.sqrt(_HUB_R_MM**2 - KEY_PIN_CHORD_OFFSET**2) + SECTION_CENTERLINE_OVERRUN_MM
)
SECTION_CENTERLINES_MODEL = (
    ((-_SECTION_REACH_MM, 0.0), (_SECTION_REACH_MM, 0.0)),
    ((0.0, -_SECTION_REACH_MM), (0.0, _SECTION_REACH_MM)),
    (
        (-_SECTION_CHORD_REACH_MM, -KEY_PIN_CHORD_OFFSET),
        (_SECTION_CHORD_REACH_MM, -KEY_PIN_CHORD_OFFSET),
    ),
)
# The native caption, top-centre anchored, stands 3 mm under the lowest
# centreline end, over the title block.
SECTION_CAPTION_XY = (
    SECTION_CENTER[0],
    _section_xy(-_SECTION_REACH_MM, 0.0)[1] - 0.006,
)


@_telemetry.traced("drawing.disc_hub.bolt_circle_centerline")
def _add_bolt_circle_centerline(adapter: Any, view: Any) -> None:
    """Draw the screw holes' bolt circle as a centreline circle on the face
    view and read its centre and radius back."""
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    native = _early_bound(view, "IView")
    if not drawing.ActivateView(view_name(adapter, view)):
        raise RuntimeError("failed to activate the hub face view for its bolt circle")
    draw.ClearSelection2(True)
    centre = model_point_in_view(
        adapter, view, (0.0, 0.0, HUB_FRONT_Z / 1000.0), label="hub bolt circle centre"
    )
    radius = BOLT_CIRCLE_DIA / 2.0 * _S
    sketch = _early_bound(native.GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    points = []
    for x, y in (centre, (centre[0] + radius, centre[1])):
        point = _early_bound(
            utility.CreatePoint(double_array([x, y, 0.0])), "IMathPoint"
        )
        projected = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
        points.append(tuple(float(value) for value in projected.ArrayData))
    manager = _early_bound(draw.SketchManager, "ISketchManager")
    previous_add_to_db = bool(manager.AddToDB)
    manager.AddToDB = True
    try:
        circle = manager.CreateCircle(*points[0], *points[1])
    finally:
        manager.AddToDB = previous_add_to_db
    if circle is None:
        raise RuntimeError("failed to sketch the hub bolt circle centreline")
    placed_centre, placed_radius = native_circle_geometry(
        circle, label="hub bolt circle"
    )
    if math.dist(placed_centre[:2], points[0][:2]) > 1e-9 or not math.isclose(
        placed_radius, math.dist(points[0][:2], points[1][:2]), abs_tol=1e-9
    ):
        raise RuntimeError(
            "the hub bolt circle centreline moved from where it was placed"
        )
    segment = _early_bound(circle, "ISketchSegment")
    # COLORREF black: a view sketch line otherwise prints in the sketch's
    # grey or under-defined blue, which reads as a hidden line.
    segment.Color = 0
    segment.Style = CENTER_LINE_STYLE
    segment.Width = CENTER_LINE_WEIGHT
    font = (int(segment.Color), int(segment.Style), int(segment.Width))
    if font != (0, CENTER_LINE_STYLE, CENTER_LINE_WEIGHT):
        raise RuntimeError(f"hub bolt circle centreline font reads {font!r}")
    draw.ClearSelection2(True)


def _set_near_side_bore(adapter: Any, annotations: list[Any]) -> None:
    """The face view's bore diameter: one arrow on the bore, its leader to
    the block's shelf, no line through the centre."""
    matches = [a for a in annotations if dimension_name(adapter, a) == "BoreDia"]
    if len(matches) != 1:
        raise RuntimeError(f"expected one hub BoreDia dimension, found {len(matches)}")
    set_near_side_diameter(matches[0], "hub bore near-side leader")
    rebuild_drawing(adapter, label="hub bore near-side leader")


def _datum_a_landing(adapter: Any, view: Any) -> tuple[float, float]:
    """The bore circle's point on the ray from the projected bore centre
    toward datum A's symbol: where SolidWorks re-solves the triangle."""
    centre = model_point_in_view(
        adapter, view, (0.0, 0.0, HUB_FRONT_Z / 1000.0), label="hub bore centre"
    )
    dx = DATUM_A_SYMBOL[0] - centre[0]
    dy = DATUM_A_SYMBOL[1] - centre[1]
    reach = math.hypot(dx, dy)
    radius = BORE_DIA / 2.0 * _S
    if not reach > radius:
        raise RuntimeError(f"hub datum A symbol {DATUM_A_SYMBOL!r} is inside the bore")
    return (centre[0] + radius * dx / reach, centre[1] + radius * dy / reach)


# The two perpendicularity frames attach by entity, not by a sheet pick, and
# to the controlled FACE, not to its rim.  A face seen edge-on draws as its
# outer rim, a circle on the hub's axis (model Z) whose projection is the
# face's line; SelectByID2 on such a line found no edge here twice (runs
# 20261002T153039266Z and 20261002T160324403Z, sheet x 0.2346 above and
# below the axis), as it once did on the crankshaft's collar rim (run
# 20261001T035353825Z).  So each frame finds its rim by model geometry, which
# the scan must match exactly once, and takes the one plane of the rim's two
# faces square to the hub axis at the face's station: the rim is also the
# end of a turned diameter, and a frame left on the rim edge (MR #1166 review
# of 6de7230aa) read as controlling the spigot's cylinder, which no cylinder
# can satisfy.  The leader lands on the face's projected line at a model x,
# placed between the rim's projected ends at run time, and the frame stands
# level with the landing, so the leader runs square onto the face's line.
# - Flange rear face, z 0, rim r 13.34: its line spans r 6.36-13.34 each side
#   of the axis.  On +X the 0-degree screw hole's edge on the face projects
#   across r 8.65-10.35 (BC 9.50 +/- 0.85) and the spigot length's extension
#   line rises from the spigot's +X corner along the whole stretch; on -X the
#   120- and 240-degree holes project at r 3.90-5.60, behind the spigot.  The
#   leader lands at x -11.34, 2.00 (6.0 on the sheet) inside the rim: at
#   mid-stretch (r 9.85) it ran level through section A-A's lower letter,
#   then on the flange (r4 layout audit, leader-through-text); the letter now
#   stands under the flange, and the leader keeps its landing, its frame in
#   the band between the spigot's and the flange's extension lines.
# - Spigot end, z 3.65, rim r 6.55: an annulus out from its round bore.
#   Its frame stands inside the spigot's extension
#   lines, its top FRAME_AIR under the upper one; the leader lands level with
#   the frame's middle, at x +4.71, on the annulus at the view's mid-depth
#   and 5.5 on the sheet from the corner the face shares with the spigot's
#   O.D.  The spigot's length and the overall end at its +X corner and print
#   above, so their extension lines rise off the line.
# Each frame stands right of the spigot's end on its landing's side of the
# axis (model +X up: *Top's +X right, turned +90 degrees).
#
# A frame's box, measured on run 20261002T180658288Z: 7.03 tall on the
# sheet, its position its top-left corner, its bent leader leaving its left
# side at mid-height.
FRAME_HEIGHT = 0.00703
FRAME_AIR = 0.002
FRAME_X = SPIGOT_END_X + 0.008
_HUB_AXIS = (0.0, 0.0, 1.0)


@dataclass(frozen=True)
class FaceFrame:
    """A perpendicularity frame on a planar face the edge view shows edge-on:
    the face's station on the hub axis and its outer rim's radius (model mm),
    and the model x its leader lands at on the face's line."""

    label: str
    face_z_mm: float
    rim_radius_mm: float
    landing_x_mm: float

    @property
    def face(self) -> PlanarFace:
        """The controlled face: the plane square to the hub axis at the
        frame's station, facing +Z (toward the spigot's end)."""
        return PlanarFace(normal=_HUB_AXIS, offset_mm=self.face_z_mm)


def frame_position(landing: tuple[float, float]) -> tuple[float, float]:
    """The frame's sheet position for a leader landing at ``landing``: its
    middle level with the landing, so the leader runs square onto the line."""
    return FRAME_X, landing[1] + FRAME_HEIGHT / 2.0


FLANGE_FACE_FRAME = FaceFrame(
    label="flange rear face perpendicularity",
    face_z_mm=0.0,
    rim_radius_mm=FLANGE_DIA / 2.0,
    landing_x_mm=-(FLANGE_DIA / 2.0 - 2.0),
)
SPIGOT_END_FRAME = FaceFrame(
    label="spigot end perpendicularity",
    face_z_mm=SPIGOT_LENGTH,
    rim_radius_mm=SPIGOT_DIA / 2.0,
    landing_x_mm=(_SPIGOT_R - FRAME_AIR - FRAME_HEIGHT / 2.0) / _S,
)
# A rim matches within these of its modelled centre and radius (the part is
# built to the spec's sizes), its axis along the hub's.
_RIM_CENTER_TOL_MM = 1e-4
_RIM_RADIUS_TOL_MM = 1e-4
# Seen edge-on, a rim's +Y point projects onto its line's midpoint; the
# projection is exact to ~1e-9 m.
_EDGE_ON_TOL_M = 1e-6


def face_rim(edges: ViewEdges, frame: FaceFrame) -> ViewEdge:
    """The one visible circle on the hub axis at ``frame``'s face station and
    rim radius; none or several raise, listing every circle the scan holds."""
    centre = (0.0, 0.0, frame.face_z_mm)

    def is_rim(circle: tuple[float, ...]) -> bool:
        offset = sum(abs(a - b) for a, b in zip(circle[:3], centre))
        tilt = 1.0 - abs(sum(a * b for a, b in zip(circle[3:6], _HUB_AXIS)))
        return (
            offset <= _RIM_CENTER_TOL_MM
            and abs(circle[6] - frame.rim_radius_mm) <= _RIM_RADIUS_TOL_MM
            and tilt <= 1e-6
        )

    matches = [item for item in edges.circles if is_rim(item.circle)]
    if len(matches) != 1:
        candidates = "; ".join(
            "r {6:.4f} at ({0:.4f}, {1:.4f}, {2:.4f}) axis ({3:.3f}, {4:.3f}, {5:.3f})".format(
                *item.circle
            )
            for item in edges.circles
        )
        raise RuntimeError(
            f"{frame.label}: expected one visible rim r {frame.rim_radius_mm:g} mm "
            f"at z {frame.face_z_mm:g} mm on the hub axis in the {edges.label!r} "
            f"scan, matched {len(matches)} of {len(edges.circles)} circles: "
            f"{candidates or 'none'}"
        )
    return matches[0]


def controlled_face(rim: ViewEdge, frame: FaceFrame) -> Any:
    """The face ``frame`` controls, of the two its rim joins (the face and the
    turned diameter it ends): the one plane matching ``frame.face``.  Two
    faces with exactly one such plane, or this raises naming each face."""
    adjacent = rim.edge.GetTwoAdjacentFaces2() or ()
    faces = tuple(face for face in adjacent if face is not None)
    geometries = [face_geometry(face) for face in faces]
    matches = [
        geometry.face
        for geometry in geometries
        if geometry is not None and frame.face.matches(geometry)
    ]
    if len(faces) != 2 or len(matches) != 1:
        described = "; ".join(
            "unreadable"
            if geometry is None
            else (
                f"surface {geometry.identity} normal {geometry.outward_normal} "
                f"parameters {tuple(round(value, 6) for value in geometry.parameters)}"
            )
            for geometry in geometries
        )
        raise RuntimeError(
            f"{frame.label}: expected the rim's two faces to hold one plane "
            f"{frame.face!r}, matched {len(matches)} of {len(faces)} faces: "
            f"{described or 'none'}"
        )
    return matches[0]


def face_landing(
    frame: FaceFrame,
    minus_end: tuple[float, float],
    plus_end: tuple[float, float],
) -> tuple[float, float]:
    """Where ``frame``'s leader lands: its model x along the face's projected
    line, from the rim's -X end to its +X end (sheet metres)."""
    t = (frame.landing_x_mm + frame.rim_radius_mm) / (2.0 * frame.rim_radius_mm)
    return (
        minus_end[0] + t * (plus_end[0] - minus_end[0]),
        minus_end[1] + t * (plus_end[1] - minus_end[1]),
    )


def _face_attachment(
    adapter: Any, view: Any, edges: ViewEdges, frame: FaceFrame
) -> tuple[Any, tuple[float, float]]:
    """``frame``'s face and its leader's landing, projected from the face's
    rim at run time; logs where the face's line lies on the sheet."""
    face = controlled_face(face_rim(edges, frame), frame)
    r_m, z_m = frame.rim_radius_mm / 1000.0, frame.face_z_mm / 1000.0
    minus_end, plus_end, side_point = model_points_in_view(
        adapter,
        view,
        ((-r_m, 0.0, z_m), (r_m, 0.0, z_m), (0.0, r_m, z_m)),
        label=f"{frame.label} rim",
        names=("-X end", "+X end", "+Y point"),
    )
    middle = ((minus_end[0] + plus_end[0]) / 2.0, (minus_end[1] + plus_end[1]) / 2.0)
    if math.dist(side_point, middle) > _EDGE_ON_TOL_M:
        raise RuntimeError(
            f"{frame.label}: the face is not edge-on in the edge view: its rim's "
            f"+Y point projects to {side_point}, its line's midpoint is {middle}"
        )
    landing = face_landing(frame, minus_end, plus_end)
    _telemetry.info(
        f"{frame.label} face projects from ({minus_end[0]:.5f}, {minus_end[1]:.5f}) "
        f"at -X to ({plus_end[0]:.5f}, {plus_end[1]:.5f}) at +X; leader lands at "
        f"({landing[0]:.5f}, {landing[1]:.5f}); the layout puts the face at sheet "
        f"x {_side_x(frame.face_z_mm):.5f}"
    )
    return face, landing


def _section_frame(
    adapter: Any, view: Any
) -> tuple[tuple[float, float], tuple[float, float], tuple[float, float]]:
    """Section A-A's sheet point of the hub axis on the cutting plane and the
    sheet steps of 1 mm along model +X and +Y (draw_pd_transgear_drive_collar)."""
    station = KEY_PIN_Z / 1000.0
    centre, plus_x, plus_y = model_points_in_view(
        adapter,
        view,
        ((0.0, 0.0, station), (0.001, 0.0, station), (0.0, 0.001, station)),
        label="disc hub section A-A frame",
        names=("hub axis", "plus x", "plus y"),
    )
    return (
        centre,
        (plus_x[0] - centre[0], plus_x[1] - centre[1]),
        (plus_y[0] - centre[0], plus_y[1] - centre[1]),
    )


def _orient_section(adapter: Any, section: Any) -> None:
    """Hold A-A to its designed frame: seen along +Z (the arrows right),
    model +X up the sheet and +Y right, the chord hole on the left.

    The handedness of +Y and +X on the sheet says which way the section
    looks: seen along -Z, +Y would run left, so the cut is reversed
    (draw_dt_crank_drive_gear).  Then any turn left between +X and the
    sheet's up is taken out (draw_ch_rocker_arm_tl_oblique_end_bracket);
    a turn is logged.
    """
    native = _early_bound(section, "IView")
    _, plus_x, plus_y = _section_frame(adapter, native)
    if plus_y[0] * plus_x[1] - plus_y[1] * plus_x[0] < 0.0:
        raw_cut = native.GetSection()
        if raw_cut is None:
            raise RuntimeError("disc hub section A-A has no native cutting direction")
        cut = _early_bound(raw_cut, "IDrSection")
        reversed_cut = not bool(cut.GetReversedCutDirection())
        cut.SetReversedCutDirection(reversed_cut)  # VT_VOID; read back.
        rebuild_drawing(adapter, label="disc hub section A-A cut reversed")
        if bool(cut.GetReversedCutDirection()) != reversed_cut:
            raise RuntimeError("disc hub section A-A cutting direction did not persist")
        _telemetry.info("disc hub section A-A looked along -Z; its cut was reversed")
        _, plus_x, plus_y = _section_frame(adapter, native)
    turn = math.remainder(
        math.pi / 2.0 - math.atan2(plus_x[1], plus_x[0]), 2.0 * math.pi
    )
    if abs(turn) > 1e-9:
        native.Angle = float(native.Angle) + turn
        rebuild_drawing(adapter, label="disc hub section A-A turned")
        _telemetry.info(
            f"disc hub section A-A turned {math.degrees(turn):.3f} deg to stand "
            "model +X up the sheet"
        )
        _, plus_x, plus_y = _section_frame(adapter, native)
    if (
        plus_x[1] <= 0.0
        or abs(plus_x[0]) > _SECTION_FRAME_TOL_M
        or plus_y[0] <= 0.0
        or abs(plus_y[1]) > _SECTION_FRAME_TOL_M
    ):
        raise RuntimeError(
            f"disc hub section A-A has the wrong frame: {plus_x=}, {plus_y=}"
        )
    _telemetry.info(f"disc hub section A-A angle={float(native.Angle):.6f} rad")


def _show_cut_face_only(adapter: Any, section: Any) -> None:
    """A-A prints its cut face only: looking along +Z the flange stands
    beyond the plane, and a station section shows the hole, not the flange
    (draw_pd_transgear_arm section D-D)."""
    native = _early_bound(section, "IView")
    cut = _early_bound(native.GetSection(), "IDrSection")
    # R2026x declares SetDisplayOnlySurfaceCut as a void setter; only its
    # dedicated bool getter may be truth-tested.
    cut.SetDisplayOnlySurfaceCut(True)
    rebuild_drawing(adapter, label="disc hub section A-A cut face")
    if not bool(cut.GetDisplayOnlySurfaceCut()):
        raise RuntimeError("disc hub section A-A still prints beyond its cut face")


def _centre_section(adapter: Any, section: Any) -> None:
    """Land the hub axis on SECTION_CENTER: a section's Position is its
    cut-plane origin, not its outline's centre
    (draw_ch_rocker_arm_tl_oblique_end_bracket ``_centre_section``)."""
    native = _early_bound(section, "IView")
    for _attempt in range(3):
        centre, _, _ = _section_frame(adapter, native)
        shift = (SECTION_CENTER[0] - centre[0], SECTION_CENTER[1] - centre[1])
        if math.hypot(*shift) <= SECTION_POSITION_TOL_M:
            return
        position = tuple(float(value) for value in native.Position)
        if not native.SetViewPosition(
            double_array([position[0] + shift[0], position[1] + shift[1]]), False
        ):
            raise RuntimeError("failed to centre the disc hub section A-A")
        rebuild_drawing(adapter, label="disc hub section A-A centred")
    centre, _, _ = _section_frame(adapter, native)
    if math.dist(centre, SECTION_CENTER) > SECTION_POSITION_TOL_M:
        raise RuntimeError(
            f"disc hub section A-A hub axis sits at {centre}, not {SECTION_CENTER}"
        )


def _delete_section_centre_marks(adapter: Any, section: Any) -> None:
    """Delete every centre mark the section arrived with and read none back
    (draw_dt_cone_gear_shaft ``_delete_centre_mark``: a full section gets
    one); A-A's own centrelines replace them."""
    label = "disc hub section A-A centre marks"
    native = _early_bound(section, "IView")
    marks = tuple(native.GetAnnotationsByType(_CENTER_MARK_ANNOTATION) or ())
    if not marks:
        _telemetry.info(f"{label}: none drawn")
        return
    draw = adapter.currentModel
    draw.ClearSelection2(True)
    for index, mark in enumerate(marks):
        if not _early_bound(mark, "IAnnotation").Select2(index > 0, 0):
            raise RuntimeError(f"cannot select {label} {index}")
    draw.EditDelete()  # VT_VOID: the re-read below is the proof
    draw.ClearSelection2(True)
    rebuild_drawing(adapter, label=f"delete {label}")
    left = tuple(native.GetAnnotationsByType(_CENTER_MARK_ANNOTATION) or ())
    if left:
        raise RuntimeError(f"{label} survived deletion ({len(left)} left)")
    _telemetry.info(f"{label}: {len(marks)} deleted")


def _precision_of(keep: dict[str, tuple[float, float]]) -> dict[str, int]:
    """The part-authored places of the dimensions one view keeps: each view's
    import proves its own, never another view's."""
    return {name: DRAWING_PRECISION_BY_NAME[name] for name in keep}


@_telemetry.traced("drawing.disc_hub.key_pin_dimensions")
def _key_pin_dimensions(adapter: Any, section: Any) -> None:
    """The chord hole in A-A: the model's marked ream and knockout sizes,
    chord offset and stop, their authored places proven, the ream's
    press-fit and the knockout's drill callouts under them."""
    annotations = curate_view_dimensions(
        adapter,
        section,
        keep=SECTION_KEEP,
        view_label="section A-A",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    assert_imported_precision(adapter, annotations, _precision_of(SECTION_KEEP))
    set_dimension_callouts(adapter, annotations, SECTION_CALLOUTS_BELOW)


@_telemetry.traced("drawing.disc_hub.section_centerlines")
def _add_section_centerlines(adapter: Any, section: Any) -> None:
    """Draw SECTION_CENTERLINES_MODEL across A-A, in the section's own sketch
    frame and straight to the database so no inference snaps them onto the
    bore's or the hole's lines (draw_fr_top_frame ``_add_view_centerlines``);
    their ends are read back."""
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    native = _early_bound(section, "IView")
    if not drawing.ActivateView(view_name(adapter, section)):
        raise RuntimeError(
            "failed to activate the disc hub section A-A for its centrelines"
        )
    draw.ClearSelection2(True)
    sketch = _early_bound(native.GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    manager = _early_bound(draw.SketchManager, "ISketchManager")
    station = KEY_PIN_Z / 1000.0
    for index, (start, end) in enumerate(SECTION_CENTERLINES_MODEL):
        label = f"disc hub section A-A centreline {index}"
        ends = model_points_in_view(
            adapter,
            native,
            tuple(
                (x / 1000.0, y / 1000.0, station) for x, y in (start, end)
            ),
            label=label,
            names=("start", "end"),
        )
        points = []
        for x, y in ends:
            point = _early_bound(
                utility.CreatePoint(double_array([x, y, 0.0])), "IMathPoint"
            )
            projected = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
            points.append(tuple(float(value) for value in projected.ArrayData))
        previous_add_to_db = bool(manager.AddToDB)
        previous_display = bool(manager.DisplayWhenAdded)
        manager.AddToDB = True
        manager.DisplayWhenAdded = True
        try:
            centerline = manager.CreateCenterLine(*points[0], *points[1])
        finally:
            manager.AddToDB = previous_add_to_db
            manager.DisplayWhenAdded = previous_display
        if centerline is None:
            raise RuntimeError(f"failed to sketch {label}")
        line = _early_bound(centerline, "ISketchLine")
        for expected, accessor in zip(points, ("GetStartPoint2", "GetEndPoint2")):
            raw = adapter._get_attr_or_call(line, accessor)
            if raw is None:
                raise RuntimeError(f"{label} has no {accessor} point")
            placed = _early_bound(raw, "ISketchPoint")
            actual = [
                float(adapter._get_attr_or_call(placed, axis))
                for axis in ("X", "Y", "Z")
            ]
            drift = max(abs(a - b) for a, b in zip(actual, expected))
            if drift > 1e-9:
                raise RuntimeError(
                    f"{label} {accessor} point sits "
                    f"{drift * 1000.0:.4g} mm from where it was authored"
                )
        segment = _early_bound(centerline, "ISketchSegment")
        segment.Color = 0  # COLORREF black, not the under-defined sketch blue.
        if int(segment.Color) != 0:
            raise RuntimeError(f"{label} colour did not persist")
        draw.ClearSelection2(True)
    rebuild_drawing(adapter, label="disc hub section A-A centrelines")


def caption_without_scale(linked_text: str) -> str | None:
    """The section caption's linked fields with its scale line removed: the
    label line (``<VLNAME>`` and ``<VLLABEL>``) alone; None unless the text
    is exactly a label line and one scale line (blank lines aside)."""
    lines = [line for line in linked_text.replace("\r\n", "\n").split("\n") if line.strip()]
    scale_lines = [line for line in lines if "<VLSCALE" in line]
    kept = [line for line in lines if "<VLSCALE" not in line]
    if (
        len(scale_lines) != 1
        or len(kept) != 1
        or "<VLNAME>" not in kept[0]
        or "<VLLABEL>" not in kept[0]
    ):
        return None
    return kept[0]


@_telemetry.traced("drawing.disc_hub.section_caption_scale")
def _drop_sheet_scale_from_caption(adapter: Any, section: Any) -> None:
    """SECTION A-A is drawn at the sheet's scale, so its caption prints no
    scale (rule 9: a scale equal to the sheet's restates the title block;
    round 5 machinist review).  SolidWorks links one anyway for a section
    given its own ratio, so the scale line is removed from the native
    caption's linked fields, as draw_pd_transgear_arm sets a section
    caption's fields."""
    native = _early_bound(section, "IView")
    ratio = tuple(float(value) for value in native.ScaleRatio)
    if abs(ratio[0] / ratio[1] - SHEET_SCALE[0] / SHEET_SCALE[1]) > 1e-9:
        raise RuntimeError(f"disc hub section A-A is not at the sheet scale: {ratio!r}")
    captions = []
    for raw_note in native.GetNotes() or ():
        note = _early_bound(raw_note, "INote")
        linked_text = str(note.PropertyLinkedText or "")
        if "<VLLABEL>" in linked_text:
            captions.append((note, linked_text))
    if len(captions) != 1:
        raise RuntimeError(
            f"expected one native section A-A caption, found {len(captions)}"
        )
    note, linked_text = captions[0]
    _telemetry.info(f"disc hub section A-A caption fields {linked_text!r}")
    if "<VLSCALE" not in linked_text:
        return
    wanted = caption_without_scale(linked_text)
    if wanted is None:
        # An unforeseen field layout keeps its scale line rather than lose
        # the sheet: the caption's text is logged above.
        _telemetry.warn(
            f"disc hub section A-A caption scale line not separable: {linked_text!r}"
        )
        return
    note.PropertyLinkedText = wanted
    rebuild_drawing(adapter, label="disc hub section A-A caption without scale")
    if str(note.PropertyLinkedText or "") != wanted:
        raise RuntimeError("disc hub section A-A caption fields did not persist")


def _section_a_a(adapter: Any, side: Any) -> Any:
    """SECTION A-A, cut across the edge view at the key pin's station: cut
    face only, laid +X up, hidden lines removed, centred, captioned, the
    chord hole dimensioned and the centrelines drawn."""
    section = create_section_view(
        adapter,
        side,
        line_start=SECTION_LINE[0],
        line_end=SECTION_LINE[1],
        view_xy=SECTION_CENTER,
        section_label=SECTION_LABEL,
        scale=VIEW_SCALE,
        label="disc hub key-pin chord section A-A",
    )
    _show_cut_face_only(adapter, section)
    _orient_section(adapter, section)
    # A section shows no hidden lines (rule 9), set before centring so the
    # display change cannot shift the ink.
    set_hidden_lines_removed(adapter, section)
    _centre_section(adapter, section)
    _delete_section_centre_marks(adapter, section)
    position_section_caption(
        adapter, section, SECTION_CAPTION_XY, label="disc hub section A-A"
    )
    _drop_sheet_scale_from_caption(adapter, section)
    _key_pin_dimensions(adapter, section)
    _add_section_centerlines(adapter, section)
    _assert_section_letters_clear(section)
    return section


# Each printed letter lands within this of where section_letter_box puts it.
SECTION_LETTER_SETTLE_M = 0.0005


def flange_ink_boxes() -> tuple[Box, Box]:
    """The edge view's flange outline and the vertical ink through the
    letters' column at its rear face (the face's line with the spigot
    length's and the flange thickness's extension lines off it)."""
    rear_x = _side_x(0.0)
    flange = Box(
        _side_x(-FLANGE_THICK), AXIS_Y - _FLANGE_R, rear_x, AXIS_Y + _FLANGE_R
    )
    return flange, Box(rear_x, REAR_FACE_INK_Y[0], rear_x, REAR_FACE_INK_Y[1])


def _assert_section_letters_clear(section: Any) -> None:
    """Read A-A's arrows and letters back (IDrSection.GetArrowInfo: each
    arrow's start and end; GetTextInfo: each letter's upper-left origin, both
    on the sheet, draw_dt_cone_gear_shaft) and fail unless each letter
    printed where section_letter_box puts it, clear of the flange's ink."""
    native = _early_bound(section, "IView")
    cut = _early_bound(native.GetSection(), "IDrSection")
    arrows = [float(value) for value in cut.GetArrowInfo() or ()]
    texts = [float(value) for value in cut.GetTextInfo() or ()]
    height = float(_early_bound(cut.GetTextFormat(), "ITextFormat").CharHeight)
    if len(arrows) != 12 or len(texts) != 6:
        raise RuntimeError(f"section A-A: arrows {arrows!r}, letters {texts!r}")
    ink = flange_ink_boxes()
    for index in range(2):
        tail = (arrows[6 * index], arrows[6 * index + 1])
        tip = (arrows[6 * index + 3], arrows[6 * index + 4])
        left, top = texts[3 * index], texts[3 * index + 1]
        printed = Box(left, top - height, left + height, top)
        planned = section_letter_box(tail)
        drift = max(
            abs(a - b)
            for a, b in zip(
                (printed.xmin, printed.ymin, printed.xmax, printed.ymax),
                (planned.xmin, planned.ymin, planned.xmax, planned.ymax),
            )
        )
        _telemetry.info(
            f"section A-A letter {index}: tail={tail!r} tip={tip!r} "
            f"printed={printed!r} planned={planned!r}"
        )
        if drift > SECTION_LETTER_SETTLE_M:
            raise RuntimeError(
                f"section A-A letter {index} printed at {printed!r}, not {planned!r}"
            )
        if any(printed.gap(box) < SECTION_LETTER_AIR - SECTION_LETTER_SETTLE_M for box in ink):
            raise RuntimeError(f"section A-A letter {index} meets the flange's ink: {printed!r}")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open disc-hub source", await adapter.open_model(str(SOURCE)))
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
    drawing_model, _sheet = new_project_drawing(
        adapter,
        property_view=PART_STEM,
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        unit=part_drawing_unit("pd-transgear-disc-hub"),
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Transgear Disc Hub Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "transgear disc hub; turned brass hub and flange",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    end = place_view(adapter, str(SOURCE), "*Back", *END_CENTER, scale=VIEW_SCALE)
    side = place_view(adapter, str(SOURCE), "*Top", *SIDE_CENTER, scale=VIEW_SCALE)
    for view, angle, label in (
        (end, END_VIEW_ANGLE, "face view"),
        (side, SIDE_VIEW_ANGLE, "edge view"),
    ):
        native = _early_bound(view, "IView")
        native.Angle = angle
        if abs(math.remainder(float(native.Angle) - angle, 2.0 * math.pi)) > 1e-9:
            raise RuntimeError(f"failed to rotate the disc-hub {label}")
    drawing_model.EditRebuild3()
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=VIEW_SCALE)
    for view in (end, side, iso):
        set_hidden_lines_removed(adapter, view)

    end_annotations = curate_view_dimensions(
        adapter,
        end,
        keep=END_KEEP,
        view_label="face",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    side_annotations = curate_view_dimensions(
        adapter,
        side,
        keep=SIDE_KEEP,
        view_label="edge",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    annotations = [*end_annotations, *side_annotations]
    # Decimal places (and so the general-tolerance row each dimension claims)
    # are authored on the part; the sheet only proves the import kept them.
    # Each view proves the names it keeps; every marked name is kept in
    # exactly one view, so the face and edge views here and section A-A
    # (_key_pin_dimensions) prove them all.
    assert_imported_precision(
        adapter, annotations, _precision_of({**END_KEEP, **SIDE_KEEP})
    )
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS_BELOW)
    set_dimension_callouts(
        adapter, annotations, DIMENSION_CALLOUTS_ABOVE, location="above"
    )
    for view, label in ((end, "face"), (side, "edge")):
        if not auto_center_marks(adapter, view, holes=True, size=0.0025):
            raise RuntimeError(
                f"failed to add ASME center marks to the hub {label} view"
            )
    # The bore's diameter lands one arrow from below-right (machinist review).
    _set_near_side_bore(adapter, end_annotations)
    # The bolt circle draws as its centreline, the diameter's arrows on it.
    _add_bolt_circle_centerline(adapter, end)
    # Datum A, the bore, on the face view where it shows round.
    add_datum_feature(
        adapter,
        end,
        entity=visible_circle_edge(adapter, end, BORE_DIA),
        symbol_xy=DATUM_A_SYMBOL,
        leader_attach_xy=_datum_a_landing(adapter, end),
        datum=BORE_DATUM,
        label="hub bore axis",
    )
    side_edges = scan_view_edges(side, label="hub edge view rims")
    for frame, key in (
        (FLANGE_FACE_FRAME, "flange rear face perpendicularity to bore"),
        (SPIGOT_END_FRAME, "spigot end perpendicularity to bore"),
    ):
        face, landing = _face_attachment(adapter, side, side_edges, frame)
        add_feature_control_frame(
            adapter,
            side,
            entity=face,
            entity_type="FACE",
            leader_attach_xy=landing,
            frame_xy=frame_position(landing),
            characteristic="perpendicularity",
            tolerance=GEOMETRIC_TOLERANCES_IN[key],
            datums=(BORE_DATUM,),
            label=frame.label,
        )
    # The stack note the overall's and the spigot length's callouts link.
    if add_note(adapter, NOTES_TEXT, *NOTES_XY) is None:
        raise RuntimeError("failed to add the disc hub's stack note")
    # SECTION A-A, cut last so every face- and edge-view step above runs on
    # the views it was proven on; it imports only the chord hole's sizes and
    # locations.
    section = _section_a_a(adapter, side)
    # Re-assert the display mode now the last annotation has landed: an
    # annotation attached after placement can leave a view's edge set
    # unregenerated, and only a real mode change rebuilds it.
    for view in (end, side, section):
        set_hidden_lines_removed(adapter, view)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Transgear Disc Hub Manufacturing Drawing",
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
