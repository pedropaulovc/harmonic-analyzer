r"""Create the manufacturing drawing for the transgear knob bush (MHA-PD-28).

Section A-A is the lathe view (drawing-guidelines.md rule 11): it cuts the
bush on its axis through the Front plane, the plane of the turned profile,
and lies axis-horizontal with the hub face on the left, so the hub and press
diameters, the hub station and the overall length (both from the hub face)
and the shoulder root print together on solid cut edges.  Datum A tags the
shoulder face there, and both thrust faces carry their finish under a
caption naming the part they bear on.  The face view, the ``*Top``
orientation turned a quarter, carries the cutting plane and the reamed bore,
a circle there: its Ø callout (rule 12, the MHA-PD-25 bushing's end view),
its perpendicularity frame to A and its running finish.  Every callout row
is authored on the part; the sheet reads them back.
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    auto_center_marks,
    dimension_name,
    place_view,
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
from _drawing_dimension_import import curate_view_dimensions
from _drawing_dimensions import assert_imported_precision
from _drawing_edges import scan_view_edges
from _drawing_finish import add_surface_finish
from _drawing_gdt import PmiDrawingPlacement, project_part_pmi
from _drawing_projection import model_point_in_view, model_points_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_sections import create_section_view
from _drawing_view_display import set_hidden_lines_removed
from _gear_drawing_entities import visible_circle_edge
from _machinist_review_mode import MachinistReviewMode
from _paths import CAD_ROOT
from _part_properties import part_drawing_unit
from _section_axis import create_section_axis_centerline, position_section_caption
from _session import run_build
from _surface_finish import surface_finish_by_key
import _telemetry
from _feature_requirements import part_metadata, requirement
from _gtol_cylinder import CylinderFace
from _gtol_planar import PlanarFace
from _printed_limits import limits
from pd_transgear_knob_bush_geometry import (
    BORE_DIA,
    HUB_DIA,
    HUB_LENGTH,
    HUB_LENGTH_BAND,
    LENGTH,
    LENGTH_BAND,
    PRESS_DIA,
    PRESS_INTERFERENCE,
    SHOULDER_ROOT_R_MAX_MM,
    UNIT,
    WALL_STATED_MIN,
)
from pd_transgear_knob_bush_spec import (
    BORE_BAND,
    BORE_CALLOUT,
    BORE_NOTE,
    DIMENSION_CALLOUTS,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    FINISH_CAPTIONS,
    GEOMETRIC_CONTROLS,
    GEOMETRIC_TOLERANCES_MM,
    PART_DATUMS,
    PLATE_NUMBER,
    PRESS_CALLOUT,
    SURFACE_FINISHES,
)

# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["pd_transgear_knob_bush"]
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

# A Ø13.2 x 29.0 bush: 3:1 lays the section 87 mm long with room on both
# ends for the diameters' callouts on the landscape sheet.
SHEET_SCALE = (3.0, 1.0)
VIEW_SCALE = (3, 1)
_S = SHEET_SCALE[0] / SHEET_SCALE[1]
# The face view upper left, A-A in the middle, the isometric lower left
# under the hub Ø, clear of the title block (farm r6: lower right it
# intruded 8 mm into it).
FACE_CENTER = (0.060, 0.200)
SECTION_CENTER = (0.200, 0.170)
ISO_CENTER = (0.110, 0.064)
# The isometric's extent, read off r6: 39.6 x 92.2 mm about its centre.
ISO_SIZE_M = (0.0396, 0.0922)
# Half the bush's hub, press and bore Ø and its length on the sheet, and the
# cutting line's overrun past the hub.
HALF_HUB = HUB_DIA * _S / 2000.0
HALF_PRESS = PRESS_DIA * _S / 2000.0
HALF_BORE = BORE_DIA * _S / 2000.0
HALF_LENGTH = LENGTH * _S / 2000.0
SECTION_LINE_OVERRUN = 0.005
# The face view turned a quarter: sheet Y is then model X, so a vertical cut
# on the bush axis is the Front plane, the plane of the turned profile, and
# A-A projects with the bush axis horizontal (the draw_pd_transgear_knob_cup
# layout).
FACE_VIEW_ANGLE = math.pi / 2.0
SECTION_LINE = (
    (FACE_CENTER[0], FACE_CENTER[1] - HALF_HUB - SECTION_LINE_OVERRUN),
    (FACE_CENTER[0], FACE_CENTER[1] + HALF_HUB + SECTION_LINE_OVERRUN),
)
# A-A lays the hub face on the left (``_orient_section``), as the bush sits
# in the lathe with the rear face at the free end.
HUB_FACE_X = SECTION_CENTER[0] - HALF_LENGTH
SHOULDER_X = HUB_FACE_X + HUB_LENGTH * _S / 1000.0
REAR_FACE_X = SECTION_CENTER[0] + HALF_LENGTH
# The native SECTION caption, top-centre anchored, under the section and
# below datum A's tag.  Its scale row is dropped (``_drop_caption_scale``).
CAPTION_XY = (SECTION_CENTER[0], SECTION_CENTER[1] - HALF_HUB - 0.045)

# Section A-A's dimension texts.  Each diameter's text sits between its own
# extension lines, so no dimension line runs out across another's extension
# line (farm r6: the bore's, nested inside the hub's, crossed it; the bore
# now prints on the face view).  Left of the hub face the hub Ø, far enough
# out that the hub face's finish and caption stand between it and the part;
# right of the rear face the press Ø, its block beyond the rear face's
# finish and caption; its arrows stand outside its extension lines
# (``_press_arrows_outside``).  Above: the hub station, then the overall
# length over it.  The root radius' leader runs through the arc's centre, which lies
# outside the part above and right of the upper root (r9: with the text
# below the part it ran 37 mm through both walls and the bore to reach it).
# Its text (24.8 mm) stands just right of the overall's rear extension line,
# over the press Ø's upper extension line, so the leader rises 13 degrees
# from the root clear over the press Ø and crosses only that one extension
# line (rule 14).
SECTION_KEEP = {
    "HubDia": (HUB_FACE_X - 0.060, SECTION_CENTER[1]),
    "HubLength": (
        (HUB_FACE_X + SHOULDER_X) / 2.0,
        SECTION_CENTER[1] + HALF_HUB + 0.022,
    ),
    "BushLength": (SECTION_CENTER[0], SECTION_CENTER[1] + HALF_HUB + 0.050),
    "PressDia": (REAR_FACE_X + 0.108, SECTION_CENTER[1]),
    "ShoulderR": (REAR_FACE_X + 0.0175, SECTION_CENTER[1] + HALF_PRESS + 0.0085),
}
# The face view's bore Ø: its block centred above the view and right of the
# bore's centre, so SolidWorks runs the leader from the shelf's LEFT end
# (the end on the circle's side, as MHA-PD-25's end view lands its right
# end) down onto the bore's upper-left quarter, left of the cutting line,
# the block's shelf clear above the line's top letter.
FACE_KEEP = {
    "BoreDia": (FACE_CENTER[0] + 0.015, FACE_CENTER[1] + HALF_HUB + 0.0265),
}
_ARROWS_OUTSIDE = 1  # swDimensionArrowsSide_e.swDimArrowsOutside
# The bore's block, read off r6's A-A: 96 mm wide (its 37-character process
# line, the longest the callout may carry), 25 mm from shelf to top.
BORE_BLOCK_SIZE_M = (0.096, 0.025)
BORE_BLOCK_LINE_MAX = 37
# The bore's numbered note (its top-left corner): in the open sheet right of
# the SECTION caption and above the title block (its top at 0.066), under
# the press Ø's lower arrow (r1: its tail ends at 0.148).  At most
# BORE_NOTE_WIDTH characters a line, about 2.85 mm each, ends left of the
# right border.
BORE_NOTE_XY = (0.290, 0.110)

# A surface finish's ink, read off r6 relative to its symbol point: the
# leader leaves 6.3 mm right of it, the symbol stands up to 7.2 mm above it,
# its text 5.3-13.7 mm right and 4.3-6.8 mm up; a caption's two rows hang
# 8.1 mm under its point and run 37.5 mm right.  So a leader that leaves
# level or downward clears its own text (r6's face-view leader rose through
# it), and each symbol sits ABOVE its landing.
FINISH_LEADER_DX_M = 0.0063
FINISH_SYMBOL_HEIGHT_M = 0.0072
FINISH_TEXT_BOX_M = (0.0053, 0.0043, 0.0137, 0.0068)
CAPTION_SIZE_M = (0.0375, 0.0081)
# Each thrust face's pick lies on its cut edge on the lower half, midway
# between the bore and its outer Ø.  Its symbol stands just above the pick's
# height outboard of the face, inside that end's diameter's extension lines,
# the leader falling to the face under the symbol; the caption over the
# symbol.  Nothing crosses the hub Ø's or press Ø's extension lines (r6: the
# symbols above the part had their leaders and captions on them and on the
# lengths' extension lines).
_HUB_PICK = (HUB_FACE_X, SECTION_CENTER[1] - (BORE_DIA + HUB_DIA) / 4.0 * _S / 1000.0)
_REAR_PICK = (
    REAR_FACE_X,
    SECTION_CENTER[1] - (BORE_DIA + PRESS_DIA) / 4.0 * _S / 1000.0,
)
_HUB_SYMBOL = (_HUB_PICK[0] - 0.0205, _HUB_PICK[1] + 0.0037)
_REAR_SYMBOL = (_REAR_PICK[0] + 0.005, _REAR_PICK[1] + 0.0036)
FACE_FINISHES = {
    "hub_face": (
        _HUB_PICK,
        _HUB_SYMBOL,
        (HUB_FACE_X - 0.0465, _HUB_SYMBOL[1] + 0.0195),
    ),
    "rear_face": (
        _REAR_PICK,
        _REAR_SYMBOL,
        (REAR_FACE_X + 0.004, _REAR_SYMBOL[1] + 0.019),
    ),
}
# Datum A rides the shoulder face's line, extended below the part, attached
# to the shoulder's lower cut line in A-A (``_shoulder_cut_line``).  An
# edge-attached tag re-solves to the foot of its leader on the edge's line,
# the leader square to it (r6: the tag at (206.2, 128.2) landed at
# (206.1, 153.3), straight above), so the tag stands left of the line at a
# height below the hub: the triangle sits on the shoulder's extension, clear
# under the hub Ø's lower extension line, its leader level.  r6 picked the 3 mm shoulder line by sheet
# point and caught a neighbour instead, its leader crossing the hub Ø's
# extension line; r8 asked for the shoulder's outer rim, which A-A does not
# show (the cut face's own lines cover it, the bore's wall hides the rest).
DATUM_A_XY = (SHOULDER_X - 0.012, SECTION_CENTER[1] - HALF_HUB - 0.010)

# The face view's bore: the cutting line A runs vertically through its
# centre, with its arrows and letters on the right (toward A-A), so the
# frame, the finish and the Ø's leader all land on the bore's left half
# (farm r5: the finish's leader ran through the lower letter, the frame's
# crossed the line).  The frame (its top-left corner) is FRAME_WIDTH_M wide,
# measured on r5 (its leader left the right end 37.2 mm from the corner): it
# stands below the view at the sheet's left note column, its right end short
# of the line, its leader rising to the bore's lower-left.  The finish
# symbol stands left of the view above the horizontal centre line, its
# leader falling onto the bore facing it.
FRAME_WIDTH_M = 0.0375
FRAME_HEIGHT_M = 0.007
FRAME_XY = (0.016, FACE_CENTER[1] - HALF_HUB - 0.012)
FRAME_LANDING_TOWARD = (FACE_CENTER[0] - 0.004, FACE_CENTER[1] - 0.010)
BORE_FINISH_XY = (0.024, FACE_CENTER[1] + 0.008)
FINISH_CHAR_HEIGHT = 0.0025
# A note's read-back position may differ from the one asked by this much.
NOTE_POSITION_TOL_M = 5e-4
# How far A-A's axis may sit from SECTION_CENTER / level before it is moved.
SECTION_POSITION_TOL_M = 1e-4

# Feature-export declarations (export_features; cad/docs/pipeline/
# features-travelers.md): what this sheet prints, in the part frame
# (pd_transgear_knob_bush_geometry: axis +Y; the hub face, the MHA-PD-15
# ring's thrust face, at y = 0 is the datum end the lengths run from; the
# shoulder (datum A) at y = HUB_LENGTH; the rear face, the MHA-PD-16 cup's
# thrust face, at y = LENGTH). The hub takes the title block's .XX row; the
# press prints (Ø.4385) REF, turned to the measured MHA-PD-19 hole for the
# stated interference (its callout; declared as that reference and the
# interference, the MHA-CH-12 land's form, so the traveler's pictures print
# the fit to the measured mate and no analysis band: traveler review r2);
# the shoulder's station its ±.001 and its root the printed R.005 MAX; the
# length its ±.002; the bore its H7 band, reamed through after pressing in
# MHA-PD-19 (MHA-PD-00), square to A, under the stated wall. Each ``span``
# is a diameter's model-Y extent. The sheet's one numbered note is the
# bore's fit statement.  The declarations print nothing.
DRAWING_NOTES = BORE_NOTE
_P = DRAWING_PRECISION_BY_NAME
_SELF = "draw_pd_transgear_knob_bush"
_GEOM = "pd_transgear_knob_bush_geometry"
part_metadata(
    model_sources=(
        (_GEOM, "LENGTH"),
        (_GEOM, "HUB_LENGTH"),
        (_GEOM, "HUB_DIA"),
        (_GEOM, "PRESS_DIA"),
        (_GEOM, "BORE_DIA"),
    ),
    precision_sources=("DRAWING_PRECISION", "DRAWING_PRECISION_BY_NAME"),
)
requirement(
    "datum_end",
    kind="face",
    faces=(PlanarFace((0.0, -1.0, 0.0), 0.0),),
    requirements=("plane",),
    fields={
        "plane": ({"frame": "model", "axis": "y", "value": 0.0}, ("__frame__",)),
        "outward": ([0.0, -1.0, 0.0], ("__frame__",)),
    },
)
requirement(
    "far_end",
    kind="face",
    faces=(PlanarFace((0.0, 1.0, 0.0), LENGTH),),
    requirements=("length",),
    fields={
        "plane": (
            {"frame": "model", "axis": "y", "value": LENGTH},
            ((_GEOM, "LENGTH"),),
        ),
        "outward": ([0.0, 1.0, 0.0], ((_GEOM, "LENGTH"),)),
        "length": (
            limits(LENGTH, _P["BushLength"], (LENGTH_BAND, -LENGTH_BAND), unit=UNIT),
            ((_GEOM, "LENGTH"), (_GEOM, "LENGTH_BAND"), (_SELF, "SECTION_KEEP")),
        ),
        "length_nominal": (LENGTH, ((_GEOM, "LENGTH"),)),
        "length_from": ("datum_end", ((_SELF, "SECTION_KEEP"),)),
    },
    precision={"length": _P["BushLength"]},
)
requirement(
    "shoulder",
    kind="face",
    faces=(PlanarFace((0.0, 1.0, 0.0), HUB_LENGTH),),
    requirements=("station", "root_radius_max"),
    fields={
        "plane": (
            {"frame": "model", "axis": "y", "value": HUB_LENGTH},
            ((_GEOM, "HUB_LENGTH"),),
        ),
        "outward": ([0.0, 1.0, 0.0], ((_GEOM, "HUB_LENGTH"),)),
        "station": (
            limits(
                HUB_LENGTH,
                _P["HubLength"],
                (HUB_LENGTH_BAND, -HUB_LENGTH_BAND),
                unit=UNIT,
            ),
            (
                (_GEOM, "HUB_LENGTH"),
                (_GEOM, "HUB_LENGTH_BAND"),
                (_SELF, "SECTION_KEEP"),
            ),
        ),
        "station_nominal": (HUB_LENGTH, ((_GEOM, "HUB_LENGTH"),)),
        "station_from": ("datum_end", ((_SELF, "SECTION_KEEP"),)),
        "root_radius_max": (
            SHOULDER_ROOT_R_MAX_MM,
            ((_GEOM, "SHOULDER_ROOT_R_MAX_MM"), "SHOULDER_ROOT_SUFFIX"),
        ),
        "datum": ("A", ("PART_DATUMS", (_SELF, "DATUM_A_XY"))),
    },
    precision={"station": _P["HubLength"], "root_radius_max": _P["ShoulderR"]},
)
requirement(
    "outer",
    kind="diameter",
    faces=(CylinderFace(HUB_DIA),),
    requirements=("dia",),
    fields={
        "axis": ([0.0, 1.0, 0.0], ("__frame__",)),
        "at": ([0.0, 0.0, 0.0], ("__frame__",)),
        "span": ([0.0, HUB_LENGTH], ((_GEOM, "HUB_LENGTH"),)),
        "dia": (
            limits(HUB_DIA, _P["HubDia"], unit=UNIT),
            ((_GEOM, "HUB_DIA"), (_GEOM, "UNIT"), (_SELF, "SECTION_KEEP")),
        ),
        "dia_nominal": (HUB_DIA, ((_GEOM, "HUB_DIA"),)),
    },
    precision={"dia": _P["HubDia"]},
)
requirement(
    "step",
    kind="diameter",
    faces=(CylinderFace(PRESS_DIA),),
    requirements=("diametral_interference",),
    fields={
        "axis": ([0.0, 1.0, 0.0], ("__frame__",)),
        "at": ([0.0, 0.0, 0.0], ("__frame__",)),
        "span": ([HUB_LENGTH, LENGTH], ((_GEOM, "HUB_LENGTH"), (_GEOM, "LENGTH"))),
        "dia_ref": (
            PRESS_DIA,
            ((_GEOM, "PRESS_DIA"), "PRESS_DIA_TEXT_PREFIX", (_SELF, "SECTION_KEEP")),
        ),
        "diametral_interference": (
            list(PRESS_INTERFERENCE),
            ((_GEOM, "PRESS_INTERFERENCE"), "PRESS_CALLOUT"),
        ),
        "mate": (f"{PLATE_NUMBER} HOLE", ("PLATE_NUMBER", "PRESS_CALLOUT")),
        "mate_nominal_dia": (PRESS_DIA, ((_GEOM, "PRESS_DIA"),)),
        "turn_to_measured_mate": (True, ("PRESS_CALLOUT",)),
        "callout": (PRESS_CALLOUT, ("PRESS_CALLOUT",)),
    },
    precision={"dia_ref": _P["PressDia"]},
)
requirement(
    "bore",
    kind="hole",
    faces=(CylinderFace(BORE_DIA),),
    requirements=("dia", "thru", "perpendicularity"),
    fields={
        "axis": ([0.0, 1.0, 0.0], ("__frame__",)),
        "at": ([0.0, 0.0, 0.0], ("__frame__",)),
        "span": ([0.0, LENGTH], ((_GEOM, "LENGTH"),)),
        "dia": (
            limits(BORE_DIA, _P["BoreDia"], BORE_BAND, unit=UNIT),
            ((_GEOM, "BORE_DIA"), "BORE_BAND", (_SELF, "FACE_KEEP")),
        ),
        "nominal_dia": (BORE_DIA, ((_GEOM, "BORE_DIA"),)),
        "thru": (True, ("BORE_CALLOUT",)),
        "process": ("ream", ("BORE_CALLOUT",)),
        "made_at": ("assembly", ("BORE_CALLOUT",)),
        "wall_min": (WALL_STATED_MIN, ((_GEOM, "WALL_STATED_MIN"), "WALL_TEXT")),
        "perpendicularity": (
            GEOMETRIC_TOLERANCES_MM["bore_perpendicularity"],
            ("GEOMETRIC_TOLERANCES_IN", "GEOMETRIC_CONTROLS"),
        ),
        "datum": ("shoulder", ("GEOMETRIC_CONTROLS", "PART_DATUMS")),
        "callout": (BORE_CALLOUT, ("BORE_CALLOUT",)),
    },
    precision={"dia": _P["BoreDia"]},
)


def _add_placed_note(
    adapter: Any, text: str, xy: tuple[float, float], label: str
) -> None:
    """Insert a free note and prove it landed at ``xy``.

    ``add_note`` only logs a failed ``IAnnotation.SetPosition``, which would
    leave the note at SolidWorks' default spot, so read the position back.
    """
    raw_note = add_note(adapter, text, *xy)
    if raw_note is None:
        raise RuntimeError(f"failed to add the {label}")
    raw_annotation = _early_bound(raw_note, "INote").GetAnnotation()
    if raw_annotation is None:
        raise RuntimeError(f"the {label} has no annotation")
    annotation = _early_bound(raw_annotation, "IAnnotation")
    position = tuple(float(value) for value in (annotation.GetPosition() or ()))
    if len(position) < 2 or any(
        abs(actual - wanted) > NOTE_POSITION_TOL_M
        for actual, wanted in zip(position[:2], xy, strict=True)
    ):
        raise RuntimeError(f"the {label} sits at {position[:2]}, not {xy}")


def _turn_face_view(adapter: Any, face: Any) -> None:
    """Turn the face view a quarter so the cut on its vertical centreline is
    the Front plane (``FACE_VIEW_ANGLE``)."""
    native = _early_bound(face, "IView")
    native.Angle = FACE_VIEW_ANGLE
    if abs(math.remainder(float(native.Angle) - FACE_VIEW_ANGLE, 2.0 * math.pi)) > 1e-9:
        raise RuntimeError("failed to turn the knob-bush face view a quarter")
    rebuild_drawing(adapter, label="knob bush face view turned")


def _section_axis_ends(adapter: Any, native: Any) -> tuple[tuple[float, float], ...]:
    """Sheet points of the bush axis at the hub face (y = 0) and the rear face."""
    return tuple(
        model_points_in_view(
            adapter,
            native,
            ((0.0, 0.0, 0.0), (0.0, LENGTH / 1000.0, 0.0)),
            label="knob bush section axis",
            names=("hub", "rear"),
        )
    )


def _orient_section(adapter: Any, section: Any) -> None:
    """Lay A-A axis-horizontal, hub face left, its axis on SECTION_CENTER.

    Cut from the quarter-turned face view, A-A lies axis-horizontal; which
    end the hub face takes is read, not assumed, and a half turn (no change
    to a solid of revolution's section) puts it on the left.  Any other turn
    means the cut is not the expected projection: refuse it.
    """
    native = _early_bound(section, "IView")
    hub, rear = _section_axis_ends(adapter, native)
    turn = math.atan2(rear[1] - hub[1], rear[0] - hub[0])
    if abs(turn) > 1e-6:
        if abs(abs(turn) - math.pi) > 1e-6:
            raise RuntimeError(
                f"knob bush A-A axis runs {math.degrees(turn):.3f} deg off the "
                f"sheet's horizontal (hub {hub}, rear {rear})"
            )
        native.Angle = float(native.Angle) - turn
        rebuild_drawing(adapter, label="knob bush section turned")
        hub, rear = _section_axis_ends(adapter, native)
    middle = ((hub[0] + rear[0]) / 2.0, (hub[1] + rear[1]) / 2.0)
    shift = (SECTION_CENTER[0] - middle[0], SECTION_CENTER[1] - middle[1])
    if math.hypot(*shift) > SECTION_POSITION_TOL_M:
        position = tuple(float(value) for value in native.Position)
        if not native.SetViewPosition(
            double_array([position[0] + shift[0], position[1] + shift[1]]), False
        ):
            raise RuntimeError("failed to centre the knob bush section")
        rebuild_drawing(adapter, label="knob bush section centred")
        hub, rear = _section_axis_ends(adapter, native)
    expected = ((HUB_FACE_X, SECTION_CENTER[1]), (REAR_FACE_X, SECTION_CENTER[1]))
    if any(
        math.dist(actual, wanted) > SECTION_POSITION_TOL_M
        for actual, wanted in zip((hub, rear), expected, strict=True)
    ):
        raise RuntimeError(
            f"knob bush A-A axis ends at hub {hub}, rear {rear}; wanted {expected}"
        )
    _telemetry.info(
        f"knob bush A-A angle={float(native.Angle):.6f} rad, turn={turn:.6f}"
    )


def _bore_landing(
    adapter: Any, view: Any, toward: tuple[float, float]
) -> tuple[float, float]:
    """The point on the bore's circle in ``view`` facing ``toward`` (sheet m).

    A leader on a circle runs radially through its pick, so the pick must
    face the symbol (draw_pd_transgear_arm_plate._bore_landing).
    """
    centre = model_point_in_view(
        adapter, view, (0.0, 0.0, 0.0), label="bush bore centre"
    )
    dx, dy = toward[0] - centre[0], toward[1] - centre[1]
    scale = HALF_BORE / math.hypot(dx, dy)
    return centre[0] + dx * scale, centre[1] + dy * scale


def _shoulder_cut_line(adapter: Any, section: Any) -> Any:
    """The shoulder face's lower line in A-A, the edge datum A attaches to.

    A-A shows its cut face's lines, in model mm on the Front plane
    (draw_fr_top_frame._cut_face_edge): the shoulder is the two short lines
    at y = HUB_LENGTH, one each side of the axis, from the hub Ø in to the
    root radius.  The one lower on the sheet is read, not assumed.
    """
    lines = [
        item
        for item in scan_view_edges(section, label="knob bush A-A").lines
        if all(abs(end[1] - HUB_LENGTH) <= 1e-4 for end in item.line)
    ]
    if len(lines) != 2:
        raise RuntimeError(
            f"knob bush A-A shows {len(lines)} shoulder cut lines at "
            f"y={HUB_LENGTH:g} mm, not 2"
        )
    heights = model_points_in_view(
        adapter,
        _early_bound(section, "IView"),
        tuple(tuple(value / 1000.0 for value in item.midpoint_mm) for item in lines),
        label="knob bush shoulder cut lines",
        names=("first", "second"),
    )
    lower = min(range(2), key=lambda index: heights[index][1])
    return lines[lower].edge


def _drop_caption_scale(adapter: Any, section: Any) -> None:
    """Print A-A's caption without its scale row.

    The section is at the sheet's 3:1, yet r9 and r10 printed "SCALE 3 : 1"
    under "SECTION A-A" (machinist review r10, three runs: rule 9 prints a
    view's scale only where it differs from the sheet's).  The caption keeps
    its native label fields; any other field layout fails loud.
    """
    native = _early_bound(section, "IView")
    ratio = tuple(float(value) for value in native.ScaleRatio)
    if ratio != SHEET_SCALE:
        raise RuntimeError(f"knob bush A-A is not at the sheet scale: {ratio!r}")
    captions = []
    for raw_note in native.GetNotes() or ():
        note = _early_bound(raw_note, "INote")
        linked_text = str(note.PropertyLinkedText or "")
        if "<VLLABEL>" in linked_text:
            captions.append((note, linked_text))
    if len(captions) != 1:
        raise RuntimeError(f"expected one knob bush A-A caption, found {len(captions)}")
    note, linked_text = captions[0]
    _telemetry.info(f"knob bush A-A caption fields {linked_text!r}")
    if "<VLSCALE" not in linked_text:
        return
    wanted = caption_without_scale(linked_text)
    note.PropertyLinkedText = wanted
    rebuild_drawing(adapter, label="knob bush A-A caption without scale")
    if str(note.PropertyLinkedText or "") != wanted:
        raise RuntimeError("knob bush A-A caption fields did not persist")


def caption_without_scale(linked_text: str) -> str:
    """The caption's label row (``<VLNAME>`` and ``<VLLABEL>``) alone."""
    rows = [row for row in linked_text.replace("\r\n", "\n").split("\n") if row.strip()]
    kept = [row for row in rows if "<VLSCALE" not in row]
    if (
        len(rows) - len(kept) != 1
        or len(kept) != 1
        or "<VLNAME>" not in kept[0]
        or "<VLLABEL>" not in kept[0]
    ):
        raise RuntimeError(f"caption scale row is not separable: {linked_text!r}")
    return kept[0]


def _press_arrows_outside(adapter: Any, annotations: list[Any]) -> None:
    """Stand the press Ø's arrows outside its extension lines.

    Its block (stacked limits over two callout rows, 22 mm) is taller than
    the 19.6 mm the two inside arrows' shafts leave of the 33.3 mm between
    the lines: r10's lower shaft ran through the "(" of the last row.
    Outside, no line runs between the extension lines (MHA-PD-16's pilot Ø).
    """
    matches = [
        item for item in annotations if dimension_name(adapter, item) == "PressDia"
    ]
    if len(matches) != 1:
        raise RuntimeError(f"expected one PressDia dimension, found {len(matches)}")
    display = _early_bound(
        _early_bound(matches[0], "IAnnotation").GetSpecificAnnotation(),
        "IDisplayDimension",
    )
    display.ArrowSide = _ARROWS_OUTSIDE
    if int(display.ArrowSide) != _ARROWS_OUTSIDE:
        raise RuntimeError("the press Ø's arrows did not move outside")


@_telemetry.traced("drawing.pd_transgear_knob_bush.callouts")
def _assert_dimension_callouts(adapter: Any, annotations: list[Any]) -> None:
    """Import the part-authored callout rows verbatim; never write them here.

    Text set from the drawing writes through to the built part (fleet issue
    #1942), so the sheet only proves each callout dimension printed once with
    the rows its part authored.
    """
    for callouts in DIMENSION_CALLOUTS.values():
        for name, text in callouts.items():
            matches = [
                item for item in annotations if dimension_name(adapter, item) == name
            ]
            if len(matches) != 1:
                raise RuntimeError(f"{name}: expected one imported callout dimension")
            display = _early_bound(
                _early_bound(matches[0], "IAnnotation").GetSpecificAnnotation(),
                "IDisplayDimension",
            )
            if str(display.GetText(4) or "").replace("\r\n", "\n") != text:
                raise RuntimeError(f"{name}: imported callout differs from the part's")


def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open knob-bush source", adapter.open_model(str(SOURCE)))
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
        unit=part_drawing_unit(PART_STEM),
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Transgear Knob Bush Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "transgear knob bush; turned steel",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    face = place_view(adapter, str(SOURCE), "*Top", *FACE_CENTER, scale=VIEW_SCALE)
    _turn_face_view(adapter, face)
    section = create_section_view(
        adapter,
        face,
        line_start=SECTION_LINE[0],
        line_end=SECTION_LINE[1],
        view_xy=SECTION_CENTER,
        section_label="A",
        scale=VIEW_SCALE,
        label="knob bush axial section",
    )
    _orient_section(adapter, section)
    _drop_caption_scale(adapter, section)
    position_section_caption(adapter, section, CAPTION_XY, label="knob bush")
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=VIEW_SCALE)
    for view in (face, section, iso):
        set_hidden_lines_removed(adapter, view)

    section_annotations = curate_view_dimensions(
        adapter,
        section,
        keep=SECTION_KEEP,
        view_label="axial section",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    face_annotations = curate_view_dimensions(
        adapter,
        face,
        keep=FACE_KEEP,
        view_label="face",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    # Decimal places (and so the general-tolerance row each dimension claims),
    # the bands, the root's MAX and every callout row are authored on the
    # part; the sheet only proves the import kept them.
    annotations = [*section_annotations, *face_annotations]
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    _assert_dimension_callouts(adapter, annotations)
    _press_arrows_outside(adapter, section_annotations)
    create_section_axis_centerline(
        adapter, section, length_mm=LENGTH, label="knob bush axis"
    )
    if not auto_center_marks(adapter, face, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to the bush face view")

    # The same native datum and frame authored on the part: A on the
    # shoulder's cut line, the bore's frame on the face view's bore.  The
    # bore carries no datum: no frame references one (rule 5).
    shoulder_line = _shoulder_cut_line(adapter, section)
    bore_edge = visible_circle_edge(adapter, face, BORE_DIA)
    placements = {
        "datum:A": PmiDrawingPlacement(section, DATUM_A_XY, edge_entity=shoulder_line),
        "bore_perpendicularity": PmiDrawingPlacement(
            face,
            FRAME_XY,
            edge_entity=bore_edge,
            leader_attachment_xy=_bore_landing(adapter, face, FRAME_LANDING_TOWARD),
        ),
    }
    project_part_pmi(
        adapter,
        placements=placements,
        datums=PART_DATUMS,
        controls=GEOMETRIC_CONTROLS,
        label="knob bush bore frame",
    )

    add_surface_finish(
        adapter,
        face,
        symbol_xy=BORE_FINISH_XY,
        control=surface_finish_by_key(SURFACE_FINISHES, "bore"),
        label="bush bore (running) finish",
        entity=bore_edge,
        char_height=FINISH_CHAR_HEIGHT,
        leader_attach_xy=_bore_landing(adapter, face, BORE_FINISH_XY),
    )
    for key, label in (
        ("hub_face", "bush hub (thrust ring) face finish"),
        ("rear_face", "bush rear (cup) face finish"),
    ):
        pick, symbol, caption = FACE_FINISHES[key]
        add_surface_finish(
            adapter,
            section,
            edge_xy=pick,
            symbol_xy=symbol,
            control=surface_finish_by_key(SURFACE_FINISHES, key),
            label=label,
            char_height=FINISH_CHAR_HEIGHT,
        )
        _add_placed_note(adapter, FINISH_CAPTIONS[key], caption, f"{label} caption")
    _add_placed_note(adapter, BORE_NOTE, BORE_NOTE_XY, "bore fit note")

    return finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Transgear Knob Bush Manufacturing Drawing",
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
