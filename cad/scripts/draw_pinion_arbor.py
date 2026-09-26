r"""Create the integral MHA-102 pinion-arbor manufacturing drawing."""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, _early_bound, _read_member, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_property_linked_note,
    add_surface_finish,
    assert_imported_precision,
    curate_view_dimensions,
    dimension_name,
    finalize_drawing,
    model_point_in_view,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    set_dimension_callouts,
    set_hidden_lines_removed,
    set_reference_dimension,
    stamp_drawing_summary,
    view_name,
)
from _drawing_hidden_sketches import (
    curate_view_dimensions as curate_hidden_owner_dimensions,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _layout_geometry import audit_sheet, format_findings
from _surface_finish import surface_finish_by_key
from pinion_arbor_pin_spec import PIN_HOLE_CALLOUT
from pinion_arbor_spec import (
    BACK_JOURNAL_Z,
    BOND_ZONE_DIA_Z,
    CROSS_HOLE_CALLOUT,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    DRUM_STATION,
    FRONT_JOURNAL_Z,
    HEAD_CAP_SAG,
    HEAD_CENTER_Z,
    HEAD_DIA,
    HEAD_FRONT_Z,
    HEAD_REAR_Z,
    JOURNAL_LEN,
    OVERALL_LEN,
    SHAFT_DIA,
    SURFACE_FINISHES,
)
from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.pywin32_adapter import null_callout
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    auto_center_marks,
    delete_view,
    iter_views,
    place_view,
)
from diagnostics.drawing_layout_audit import collect_document

SPEC = DRAWINGS_BY_NAME["pinion_arbor"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"], pdf=SPEC.outputs["pdf"], png=SPEC.outputs["png"]
)
SLDDRW, PDF, PNG = OUTPUTS.slddrw, OUTPUTS.pdf, OUTPUTS.png
SHEET_SCALE = (1.0, 1.0)
PRINCIPAL_CENTER = (0.200, 0.170)
ISO_CENTER = (0.365, 0.225)
DETAIL_CENTER = (0.165, 0.235)
DETAIL_SCALE = (2, 1)
DETAIL_RADIUS_MM = 15.0
DETAIL_RATIO = DETAIL_SCALE[0] / DETAIL_SCALE[1]
# Detail A's crop circle on the sheet: the 15 mm fence round the head centre,
# enlarged 2:1.
DETAIL_CROP_RADIUS = DETAIL_RATIO * DETAIL_RADIUS_MM / 1000.0
# Detail A is a cropped 2:1 MODEL view, not a native detail view.  On this
# arbor's native detail no dimension could be moved in under any variant
# tried (drag from the profile or the end-on donor, move or copy, the
# detail's own feature import, a hidden reference sketch: neckbisect-ecef,
# neckref-84e5, 20260926T141154Z-1-b0f89771).  A cropped model view is the
# MHA-142 pattern: a *Top view at 2:1, turned like the profile, moved so the
# head centre lands on DETAIL_CENTER and cropped by a sketch circle.
DETAIL_LETTER = "A"
# A model view has no native label the API can show, so the label is a note
# the view owns, in the native detail label's words.
DETAIL_LABEL_TEXT = (
    f"DETAIL {DETAIL_LETTER}\nSCALE {DETAIL_SCALE[0]} : {DETAIL_SCALE[1]}"
)
# The label sits centred under the crop circle, its top edge this far below
# it: clear of the HeadLen text that rides the circle's lower edge.
DETAIL_LABEL_DROP = 0.012
DETAIL_LABEL_XY = (
    DETAIL_CENTER[0],
    DETAIL_CENTER[1] - DETAIL_CROP_RADIUS - DETAIL_LABEL_DROP,
)
# The native label measured 32 mm wide (pc-p1 render), and the neighbours'
# clearances are pinned against this half-width.
DETAIL_LABEL_HALF_WIDTH = 0.017
# The letter "A" that names the detail rides the profile's axis just right of
# the fence circle, where the native detail put it (pc-p1 render: centred at
# about (334, 170) mm).
DETAIL_LETTER_OFFSET = (DETAIL_RADIUS_MM / 1000.0 + 0.006, 0.0)
# swCropViewErrors_e.swCropViewErrors_NoError
CROP_NO_ERROR = 1
# The crop boundary where it cuts the neck.  Drawn plain, it was a smooth arc
# with the same curvature sense as the SR10.9 crown, so the neck read as
# domed (Main's F1 on pc-r6).  A thin full boundary circle would cross the
# Ø10.5 dimension line and run through the (3.0) arrowhead, so the neck's
# cut end is drawn as a freehand break instead: Crop2's jagged outline, at
# this shape intensity (1 most .. 5 least).
DETAIL_BREAK_INTENSITY = 3
# The head centre must land within 0.1 mm of DETAIL_CENTER after the move
# (draw_post_mount_screw's tip-view tolerance).
DETAIL_POSITION_TOL_M = 1e-4
# The detail's model axis must run the profile's way on the sheet.
DETAIL_AXIS_MIN_DOT = 0.999
# A note that lands more than this off its centring target did not move.
NOTE_CENTRING_TOL_M = 0.001
NOTE_CENTRING_PASSES = 2
# The head diameter lives in an end-on Front-plane profile sketch, so the
# end-on donor imports it and it moves onto the 1:1 profile.  The Ø8 is
# dimensioned on the profile itself, from the bond zone's flank.  The neck
# diameter is imported straight into detail A (see DETAIL_KEEP).
DONOR_KEEP = {
    "HeadDia": (0.030, 0.215),
}
# Profile scale is 1:1 with the head to the right, so model z maps to sheet
# x = 0.200 - (z - 106.725) / 1000.  The lands are centred on their straps, so
# their centres (x 0.252 front, 0.099 back) hold whatever the derived land
# length; only their ends move.  The front land's length rides above the
# shaft and its diameter hangs below; the back land's are swapped (see
# BACK_JOURNAL_TEXT_X).  The stations from the Ø15 head rear face stack
# below the shaft.
MODEL_Z_AT_SHEET_ORIGIN_X = 106.725


def _sheet_x(model_z: float) -> float:
    return PRINCIPAL_CENTER[0] - (model_z - MODEL_Z_AT_SHEET_ORIGIN_X) / 1000.0


# Each land's Ra arrow lands RA_ARROW_FROM_HEAD_END in from the land's
# head-side end, and its symbol hangs RA_SHOULDER further head side on a short
# bent-leader shoulder.  The front symbol hangs below the shaft, its left edge
# clear of that end's station witness.  At c6eb7f6f the back symbol did the
# same and its shoulder ran through the 199.9 / 19.0 witness below the shaft
# (Main).  Nothing rises from the back land above the shaft, so its symbol
# hangs there, over the land's head-side end and under the raised back
# JOURNAL diameter (BACK_JOURNAL_DIA_Y).
RA_ARROW_FROM_HEAD_END = 2.0
RA_SYMBOL_OFFSET = 0.0033
RA_SHOULDER = RA_SYMBOL_OFFSET + RA_ARROW_FROM_HEAD_END / 1000.0
FRONT_RA_X = _sheet_x(FRONT_JOURNAL_Z) + RA_SYMBOL_OFFSET
BACK_RA_XY = (
    _sheet_x(BACK_JOURNAL_Z + RA_ARROW_FROM_HEAD_END) + RA_SHOULDER,
    0.179,
)
# Rendered extent of an Ra 1.6 symbol about its insertion point (left, right,
# top; the point is the shoulder's end under the triangle's vertex), measured
# on the c6eb7f6f sheet.
RA_SYMBOL_EXTENT = (-0.0019, 0.0151, 0.0062)
FLANK_SIGN = {"lower": -1.0, "upper": 1.0}
# Each land's diameter is measured at a short witness JOURNAL_DIA_POINT_FROM_
# CROWN_END in from its crown-side end (build_pinion_arbor, pinned equal by
# test), and its line stands 1 mm from that point, so its extensions are ~1 mm
# rather than a run along the flank (Main, 2026-09-24).  The text hangs away
# from the side its extensions come from: left of the front line, right of the
# back one.
JOURNAL_DIA_POINT_FROM_CROWN_END = 2.0
JOURNAL_DIA_LINE_OFFSET = 0.001
FRONT_JOURNAL_DIA_POINT_X = _sheet_x(
    FRONT_JOURNAL_Z + JOURNAL_LEN - JOURNAL_DIA_POINT_FROM_CROWN_END
)
BACK_JOURNAL_DIA_POINT_X = _sheet_x(
    BACK_JOURNAL_Z + JOURNAL_LEN - JOURNAL_DIA_POINT_FROM_CROWN_END
)
# The back land is boxed in below the shaft (the back-crown and overall
# witnesses at x 0.079-0.081 on its crown side, the 199.9 witness and the Ra
# leader on its head side), so its diameter hangs ABOVE the shaft, its text
# right of the line over the land and clear of the back-crown sag witnesses,
# and its 19.0 length moves below.  The block rides high enough that the
# back Ra symbol fits under it, over the land.
BACK_JOURNAL_TEXT_X = BACK_JOURNAL_DIA_POINT_X + JOURNAL_DIA_LINE_OFFSET
BACK_JOURNAL_DIA_Y = 0.1945
# The drum station's text block (~35 mm "DRUM STATION" callout) ends 4 mm left
# of its drum-end witness: between that witness and the head face, the
# neck-end witness drops through.
DRUM_STATION_TEXT_WIDTH = 0.035
DRUM_STATION_WITNESS_X = _sheet_x(HEAD_REAR_Z + DRUM_STATION)
DRUM_STATION_TEXT_XY = (
    DRUM_STATION_WITNESS_X - 0.004 - DRUM_STATION_TEXT_WIDTH / 2.0,
    0.123,
)
# The front land's diameter text hangs LEFT of its line (x-0.026 .. x+0.001,
# measured at 4e97c4d8), and the drum station's witness drops through the
# whole band below the shaft (run 059b5b0f: text-on-line at x 246.0).  Its
# line stands on the land 1 mm crown side of its measuring point, the text
# block ending ~2.4 mm short of that witness.
JOURNAL_DIA_TEXT_OVERHANG = 0.001
FRONT_JOURNAL_DIA_X = FRONT_JOURNAL_DIA_POINT_X - JOURNAL_DIA_LINE_OFFSET
# The bond-zone diameter stands over the part's witness (x 0.195) but hangs
# its text ABOVE the shaft: below it, beside the front "JOURNAL" shelf, the
# two read as one paired callout (Main and Fable, 63468ee9).  Above, its line
# rises a few mm off the silhouette to the shelf, right of the DETAIL A label
# and under detail A's "(3.0)", and short of the front land's 19.0 witnesses.
BOND_ZONE_TEXT_XY = (_sheet_x(BOND_ZONE_DIA_Z), 0.190)
# The drum-station and bond-zone reference sketches stand alone, so the
# profile shows them, and each ends on a short construction witness lying ON
# the lower Ø8 outline.  The view paints that witness construction grey over
# the black silhouette, which at 1:1 read as a break in the outline, i.e. a
# groove or relief to a machinist (Main, 5471a6ef).  Each is re-coloured in
# the view to the outline's black; the model sketch and its dimension are
# untouched.  The spans (model z, mm) mirror build_pinion_arbor's
# DRUM_STATION_POINT_LEN / BOND_ZONE_WITNESS_LEN, pinned by test.
REFERENCE_WITNESS_COLOR = 0  # COLORREF black, the outline's colour.
DRUM_STATION_POINT_LEN = 1.0
BOND_ZONE_WITNESS_LEN = 4.0
REFERENCE_WITNESSES = {
    "DrumStationReference": (
        HEAD_REAR_Z + DRUM_STATION - DRUM_STATION_POINT_LEN,
        HEAD_REAR_Z + DRUM_STATION,
    ),
    "BondZoneReference": (BOND_ZONE_DIA_Z, BOND_ZONE_DIA_Z + BOND_ZONE_WITNESS_LEN),
}
SW_SEL_EXT_SKETCH_SEGS = 24  # swSelectType_e.swSelEXTSKETCHSEGS
REFERENCE_WITNESS_LEN_TOL = 0.01  # mm; the witnesses are fully defined sketch lengths
# Exported-raster proof that the outline stays unbroken over each witness:
# the grey witness core measured 107-128 and the black outline 0 (5471a6ef
# PNG), so every raster column over a span needs at least two dark pixels
# within a few rows of the flank.
OUTLINE_DARK_MAX = 60
OUTLINE_CORE_ROWS = 2
OUTLINE_SEARCH_ROWS = 6
# Rendered width and height of a two-place "Ø8.00 -0.01/-0.0x" callout block,
# measured on the 63468ee9 sheet.
DIAMETER_BLOCK_SIZE = (0.027, 0.014)
PRINCIPAL_KEEP = {
    "FrontJournalLen": (0.252, 0.188),
    # Below the shaft, under the back Ra symbol and its leader.
    "BackJournalLen": (0.097, 0.143),
    "FrontJournalDia": (FRONT_JOURNAL_DIA_X, 0.150),
    "BondZoneDia": BOND_ZONE_TEXT_XY,
    "BackJournalDia": (BACK_JOURNAL_TEXT_X, BACK_JOURNAL_DIA_Y),
    "FrontJournalFromHeadRear": (0.283, 0.130),
    # The drum station stacks between the two land stations, its text left of
    # its own drum-end witness.  The back station's text moves left to clear
    # it.
    "DrumStationFromHeadRear": DRUM_STATION_TEXT_XY,
    "BackJournalFromHeadRear": (0.170, 0.115),
    # Right of the overall-length witness at the front crown apex (x 0.3215).
    "NeckLen": (0.340, 0.100),
    "BackRimFromHeadRear": (0.205, 0.095),
    "OverallLen": (0.205, 0.080),
    "BackCapSagDim": (0.055, 0.220),
    # Radial leader down-left from the back crown, below the shaft axis and
    # clear of the (1.2) sag reference above it and the overall witnesses.
    "BackCapR": (0.045, 0.140),
    # R1a's collar pin hole (x 0.269) sits over the front land's Ra symbol,
    # so both its dimensions stand ABOVE the shaft: the station from the head
    # rear face in a row over the Ø15's, and the hole's leader rising left of
    # that row's witness, above the 19.0's right arrow tail.
    "PinStationFromHeadRear": (0.288, 0.207),
    "PinHoleDia": (0.250, 0.222),
}
# In detail A the neck runs from the fence (x ~0.137 at its edges) to the
# head rear face (x 0.1545), its Ø10.5 at y 0.2245-0.2455.  Its end-on
# circle is on the Front plane (model z 0, x 0.152), where the witnesses
# start, so a line at x 0.140 on the neck's fence side keeps both witnesses
# on the neck.  The text runs on past the line, away from that circle (the
# profile rendered it left of its line at a1a694a6), so it rides above-left
# of the crop circle, clear of it like every other detail-A callout; the line
# crosses the circle once, square, to reach it.
NECK_DIA_XY = (0.140, 0.2575)
# Every dimension detail A carries, imported by feature straight into the
# cropped view (DRAWING_DIMENSIONS names the owners: Head, FrontCapProfile,
# CrossHoleProfile, NeckProfile) BEFORE any other view imports, since a
# model dimension already on the sheet is not imported again.
DETAIL_KEEP = {
    "HeadLen": (0.165, 0.201),
    "HeadCapR": (0.195, 0.262),
    "HeadCapSagDim": (0.205, 0.210),
    # Above the hole's centre line, so the leader drops onto the hole edge.
    "CrossHoleDia": (0.245, 0.256),
    "NeckDia": NECK_DIA_XY,
}
# The head sits inside detail A's fence at the right end of the profile (the
# fence spans x 0.298-0.328 on the axis, y 0.170): the Ø15's dimension line
# stands inside the fence and runs up to its text above it.  The line sits
# between the crown apex (x 0.3215) and the fence (x 0.3262 at the head's
# top and bottom edges), so its witnesses stay inside the circle: they used
# to run out through it to x 0.340, reading as part of the detail callout
# with the "A" label between them (Fable r-delta).
DIAMETER_POSITIONS = {
    "HeadDia": (0.3238, 0.192),
}
# The neck's Ø10.5 has no place on the 1:1 profile.  The layout audit boxes
# its text from 15.6 mm left of the dimension line to 11.5 mm right of it,
# 2.8 mm below the text position to 0.7 mm above (stacktop-dbe47ae3 read
# [284.4,191.2]..[311.5,194.7] mm for text at (0.300, 0.194)).  Two gates
# then leave no x for the line:
# - the collar-pin station's head-rear-face witness rises through that row
#   at x 0.3076, so the box must end left of it: line x < 0.2961
#   (stacktop-dbe47ae3);
# - the witnesses overshoot the line by 1 mm (c486b6e1: line 294.5, witness
#   ends 293.5), and at the neck's edges (5.25 mm off the axis) they must
#   stay inside detail A's 15 mm fence round the head centre (x 0.3132):
#   line x >= 0.300 (c486b6e1 failed at 0.2945).
# Above the station row the line would cross the station's own dimension
# line into its "COLLAR PIN" text; below the shaft the head-rear-face
# station witnesses and the neck-end witness drop through the row.  So the
# neck is dimensioned inside detail A, which shows it from the fence to the
# head rear face (Main's ruling).
NECK_DIA_TEXT_BOX_FROM_POSITION = (-0.0156, 0.0115, -0.0028, 0.0007)


def _detail_x(model_z: float) -> float:
    """Sheet x of a model station inside detail A (head centre at its centre)."""
    return DETAIL_CENTER[0] + DETAIL_RATIO * (
        _sheet_x(model_z) - _sheet_x(HEAD_CENTER_Z)
    )


DIMENSION_CALLOUTS = {
    # One name for the axial datum every station runs from (Fable m1): the
    # head end has two shoulders, Ø8-Ø10.5 and Ø10.5-Ø15.
    # <MOD-DIAM> carries its own leading gap, so no space before it.
    "BackRimFromHeadRear": f"FROM BACK CROWN ROOT TO<MOD-DIAM>{HEAD_DIA:.0f} HEAD REAR FACE",
    "DrumStationFromHeadRear": "DRUM STATION",
    "OverallLen": "OVERALL",
    "BackCapSagDim": "BACK CROWN",
    "CrossHoleDia": CROSS_HOLE_CALLOUT,
    "FrontJournalDia": "JOURNAL",
    "BackJournalDia": "JOURNAL",
    "BondZoneDia": "BOND ZONE",
    "PinStationFromHeadRear": "COLLAR PIN",
    "PinHoleDia": PIN_HOLE_CALLOUT,
}
# The turning axis runs the full part and this far past each crown.
AXIS_OVERSHOOT_MM = 3.0
# Each land's Ra symbol hangs off one flank on the land's head side of its
# diameter line, clear of the split-line rings at the land ends.
JOURNAL_FINISHES = {
    "front_journal": (
        FRONT_JOURNAL_Z + RA_ARROW_FROM_HEAD_END,
        (FRONT_RA_X, 0.150),
        "lower",
    ),
    "back_journal": (BACK_JOURNAL_Z + RA_ARROW_FROM_HEAD_END, BACK_RA_XY, "upper"),
}


def _move_dimension(
    adapter: Any,
    annotation: Any,
    target: Any,
    text_xy: tuple[float, float],
    *,
    source_view: Any,
) -> Any:
    """Move a native model dimension and verify its new drawing-view owner."""
    name = dimension_name(adapter, annotation)
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    if not drawing.ActivateView(view_name(adapter, source_view)):
        raise RuntimeError(f"{name}: failed to activate source dimension view")
    draw.ClearSelection2(True)
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    selection_name = str(display.GetNameForSelection() or "")
    if not selection_name or not draw.Extension.SelectByID2(
        selection_name,
        "DIMENSION",
        0.0,
        0.0,
        0.0,
        False,
        0,
        null_callout(),
        0,
    ):
        raise RuntimeError(f"failed to select model dimension {name}: {selection_name!r}")
    drawing.DragModelDimension(view_name(adapter, target), 2, text_xy[0], text_xy[1], 0.0)
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    matches = [
        _early_bound(item, "IAnnotation")
        for item in (_early_bound(target, "IView").GetAnnotations() or ())
        if dimension_name(adapter, _early_bound(item, "IAnnotation")) == name
    ]
    if len(matches) != 1:
        raise RuntimeError(f"{name}: native dimension did not move into target view")
    return matches[0]


def _activate_view(adapter: Any, view: Any, *, label: str) -> str:
    """Make ``view`` the active view (sketch entities and notes land in it)."""
    name = view_name(adapter, view)
    if not _early_bound(adapter.currentModel, "IDrawingDoc").ActivateView(name):
        raise RuntimeError(f"failed to activate the {label} {name!r}")
    adapter.currentModel.ClearSelection2(True)
    return name


def _sketch_circle(
    adapter: Any,
    view: Any,
    center: tuple[float, float],
    radius: float,
    *,
    label: str,
    add_to_db: bool = False,
) -> Any:
    """Sketch a circle in the ACTIVE ``view``'s own sketch from sheet points.

    The sheet points go through the view sketch's ModelToSketchTransform (the
    recipe the native detail fence and draw_crank_arm's crop already used), so
    the circle lands where the sheet says whatever the view's scale.  Without
    ``add_to_db`` the new circle is left SELECTED, which is what Crop2
    consumes.
    """
    sketch = _early_bound(_early_bound(view, "IView").GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    points = []
    for x, y in (center, (center[0] + radius, center[1])):
        point = _early_bound(
            utility.CreatePoint(double_array([x, y, 0.0])), "IMathPoint"
        )
        projected = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
        points.append(tuple(float(value) for value in projected.ArrayData))
    manager = _early_bound(adapter.currentModel.SketchManager, "ISketchManager")
    previous_add_to_db = bool(manager.AddToDB)
    manager.AddToDB = add_to_db
    try:
        circle = manager.CreateCircle(*points[0], *points[1])
    finally:
        manager.AddToDB = previous_add_to_db
    if circle is None:
        raise RuntimeError(f"failed to sketch the {label} circle")
    return circle


def _mark_detail_on_profile(adapter: Any, principal: Any) -> tuple[float, float]:
    """Circle detail A's region on the profile: the 15 mm fence round the head.

    It is the circle the native detail was cut from, now a plain view-sketch
    circle drawn direct to the database (no screen-space inference) in the
    outline's black.  It is drawn before the turning axis so nothing of the
    view's own sketch is near it.  Returns its sheet centre.
    """
    _activate_view(adapter, principal, label="integral-arbor profile")
    center = model_point_in_view(
        adapter,
        principal,
        (0.0, 0.0, HEAD_CENTER_Z / 1000.0),
        label="integral-arbor detail mark centre",
    )
    circle = _sketch_circle(
        adapter,
        principal,
        center,
        DETAIL_RADIUS_MM / 1000.0,
        label="detail-A mark",
        add_to_db=True,
    )
    segment = _early_bound(circle, "ISketchSegment")
    segment.Color = 0  # COLORREF black, not the under-defined sketch blue.
    if int(segment.Color) != 0:
        raise RuntimeError("detail-A mark circle colour did not persist")
    adapter.currentModel.ClearSelection2(True)
    adapter.currentModel.EditRebuild3()
    _telemetry.info(
        f"pinion-arbor: detail-A mark circle R{DETAIL_RADIUS_MM:g} mm at sheet "
        f"({center[0] * 1000:.1f}, {center[1] * 1000:.1f}) mm on the profile"
    )
    return center


def _axis_on_sheet(
    adapter: Any, view: Any, *, label: str
) -> tuple[tuple[float, float], float]:
    """The turning axis's unit direction on the sheet in ``view``, and the
    sheet length one overall part length spans there."""
    ends = [
        model_point_in_view(adapter, view, (0.0, 0.0, z / 1000.0), label=label)
        for z in (HEAD_CENTER_Z, HEAD_CENTER_Z + OVERALL_LEN)
    ]
    dx, dy = ends[1][0] - ends[0][0], ends[1][1] - ends[0][1]
    return _unit(dx, dy), math.hypot(dx, dy)


def _cropped_head_view(adapter: Any, principal: Any) -> Any:
    """Detail A: a standalone 2:1 *Top model view cropped to the head.

    Sequence (the MHA-142 tip view, diag/mha142-bisect b6552f13b, and
    draw_crank_arm's merged top-view crop): place *Top at 2:1 and turn it like
    the profile (IView.Angle -90 deg); prove the model axis runs the profile's
    way at twice its scale; move it so the head centre lands on DETAIL_CENTER
    (ModelToViewTransform, SetViewPosition); ActivateView; a circle of the
    fence's 2:1 radius in the view's own sketch; IView.Crop2 straight after
    it while the circle is still selected (swCropViewErrors_NoError), with
    the jagged outline that draws the neck's cut end as a freehand break;
    IsCropped and outline-style read-backs that raise.
    """
    draw = adapter.currentModel
    view = _early_bound(
        place_view(adapter, str(SOURCE), "*Top", *DETAIL_CENTER, scale=DETAIL_SCALE),
        "IView",
    )
    ratio = tuple(float(value) for value in view.ScaleRatio)
    if ratio != tuple(float(value) for value in DETAIL_SCALE):
        raise RuntimeError(f"detail-A view scale {ratio!r}, expected {DETAIL_SCALE!r}")
    view.Angle = float(_early_bound(principal, "IView").Angle)
    draw.EditRebuild3()
    if abs(math.remainder(float(view.Angle) + math.pi / 2.0, 2.0 * math.pi)) > 1e-9:
        raise RuntimeError("failed to turn detail A like the integral-arbor profile")
    profile_axis, profile_span = _axis_on_sheet(
        adapter, principal, label="profile axis"
    )
    detail_axis, detail_span = _axis_on_sheet(adapter, view, label="detail-A axis")
    dot = profile_axis[0] * detail_axis[0] + profile_axis[1] * detail_axis[1]
    if (
        dot < DETAIL_AXIS_MIN_DOT
        or abs(detail_span / profile_span - DETAIL_RATIO) > 0.01
    ):
        raise RuntimeError(
            f"detail A does not show the profile at {DETAIL_RATIO:g}x: axis "
            f"{detail_axis!r} vs profile {profile_axis!r} (dot {dot:.4f}), span "
            f"ratio {detail_span / profile_span:.4f}"
        )
    head = (0.0, 0.0, HEAD_CENTER_Z / 1000.0)
    center = model_point_in_view(adapter, view, head, label="detail-A head centre")
    position = tuple(float(value) for value in view.Position)
    target = [position[axis] + DETAIL_CENTER[axis] - center[axis] for axis in range(2)]
    if not view.SetViewPosition(double_array(target), False):
        raise RuntimeError("failed to move detail A onto its sheet position")
    draw.EditRebuild3()
    center = model_point_in_view(adapter, view, head, label="detail-A head centre")
    if math.dist(center, DETAIL_CENTER) > DETAIL_POSITION_TOL_M:
        raise RuntimeError(
            f"detail-A head centre sits at {center!r}, not {DETAIL_CENTER!r}"
        )
    uncropped = tuple(float(value) for value in view.GetOutline())
    name = _activate_view(adapter, view, label="detail-A view")
    _sketch_circle(adapter, view, center, DETAIL_CROP_RADIUS, label="detail-A crop")
    status = int(view.Crop2(True, False, DETAIL_BREAK_INTENSITY))
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    view.UpdateViewDisplayGeometry()
    cropped = bool(view.IsCropped())
    outline = tuple(float(value) for value in view.GetOutline())
    _telemetry.info(
        f"pinion-arbor: detail A {name!r} {ratio[0]:g}:{ratio[1]:g}, Crop2 status "
        f"{status}, IsCropped {cropped}, outline "
        f"{tuple(round(value * 1000, 1) for value in outline)} mm",
        crop_status=status,
        cropped=cropped,
    )
    if status != CROP_NO_ERROR or not cropped:
        raise RuntimeError(
            f"detail A is not cropped: Crop2 status {status}, IsCropped {cropped}"
        )
    # The uncropped 2:1 view spans the whole ~466 mm arbor and the crop about
    # 60 mm, so a crop that took at least halves the width (GetOutline's
    # margin round a cropped view is unmeasured, so no tighter bound).
    if (
        len(outline) != 4
        or len(uncropped) != 4
        or outline[2] - outline[0] > (uncropped[2] - uncropped[0]) / 2.0
    ):
        raise RuntimeError(
            f"detail-A crop did not take: outline {outline!r}, before {uncropped!r}"
        )
    boundary = (
        bool(view.CropViewJaggedOutline),
        bool(view.CropViewNoOutline),
        int(view.CropViewJaggedShapeIntensity),
    )
    if boundary != (True, False, DETAIL_BREAK_INTENSITY):
        raise RuntimeError(
            f"detail A's crop boundary is not the freehand break: jagged, "
            f"no-outline, intensity {boundary!r}"
        )
    return view


def _radius_leader_outside(adapter: Any, annotations: list[Any], name: str) -> None:
    """Put a radius's arrow outside its arc (swDimArrowsOutside).

    Drawn from the arc's centre, the SR10.9 leader ran through the Ø6 cross
    hole and its centre mark (Main's F2 on pc-r6).  With the arrow outside,
    the leader reaches the crown from its text and never enters the part.
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
    if int(display.ArrowSide) != 1:
        raise RuntimeError(f"{name} did not keep its arrow outside the arc")


def _plain_text(text: str) -> str:
    """A note's words with its line breaks and spacing folded to single spaces."""
    return " ".join(str(text).split())


def _is_note_text(found: str, text: str) -> bool:
    """Whether a read-back note text is ``text``.

    A one-line note must read back whole.  A multi-line note is recognised by
    its first line: how INote.GetText returns the later lines of a
    multi-line note has never been read on a seat in this repo.
    """
    lines = text.split("\n")
    if len(lines) == 1:
        return found == _plain_text(text)
    return found.startswith(_plain_text(lines[0]))


def _note_texts(view: Any) -> list[str]:
    return [
        _plain_text(_early_bound(note, "INote").GetText() or "")
        for note in (_early_bound(view, "IView").GetNotes() or ())
    ]


def _note_box(note: Any, *, label: str) -> tuple[float, float, float, float]:
    """``INote.GetExtent``'s lower-left and upper-right corners, sheet metres."""
    values = tuple(float(value) for value in (note.GetExtent() or ()))
    if len(values) != 6 or not all(map(math.isfinite, values)):
        raise RuntimeError(f"{label}: invalid note extent {values!r}")
    box = (values[0], values[1], values[3], values[4])
    if box[0] >= box[2] or box[1] >= box[3]:
        raise RuntimeError(f"{label}: empty note extent {values!r}")
    return box


def _note_centring_error(
    box: tuple[float, float, float, float],
    center_x: float,
    top: float | None,
    center_y: float | None,
) -> tuple[float, float]:
    """How far a note's extent sits from its target: its horizontal centre
    against ``center_x``, and its top edge against ``top`` or else its
    vertical centre against ``center_y``."""
    error_x = (box[0] + box[2]) / 2.0 - center_x
    if top is not None:
        return error_x, box[3] - top
    if center_y is None:
        raise ValueError("a centred note needs a top edge or a centre height")
    return error_x, (box[1] + box[3]) / 2.0 - center_y


def _centred_view_note(
    adapter: Any,
    view: Any,
    text: str,
    *,
    center_x: float,
    top: float | None = None,
    center_y: float | None = None,
    label: str,
) -> tuple[float, float, float, float]:
    """Insert a note owned by ``view``, centred on ``center_x`` by its extent.

    A note lands in the ACTIVE view (pms857-diag-9eca), so the view is
    activated first.  The note is placed, its rendered extent read
    (INote.GetExtent) and moved by the centring error (the purchased-part
    caption recipe); ``top`` pins its top edge, ``center_y`` its middle.
    Returns the final extent.
    """
    _activate_view(adapter, view, label=label)
    y = top if top is not None else center_y
    note = add_note(adapter, text, center_x, y)
    if note is None:
        raise RuntimeError(f"failed to add the {label} note")
    note = _early_bound(note, "INote")
    annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
    box = _note_box(note, label=label)
    # A second pass absorbs an anchor that does not move one-for-one with
    # the extent; the read-back below fails loud if neither pass landed it.
    for _ in range(NOTE_CENTRING_PASSES):
        error_x, error_y = _note_centring_error(box, center_x, top, center_y)
        if max(abs(error_x), abs(error_y)) <= NOTE_CENTRING_TOL_M / 10.0:
            break
        position = tuple(
            float(value) for value in _read_member(annotation, "GetPosition")
        )
        if not annotation.SetPosition2(
            position[0] - error_x, position[1] - error_y, 0.0
        ):
            raise RuntimeError(f"failed to centre the {label} note")
        adapter.currentModel.EditRebuild3()
        box = _note_box(note, label=label)
    error_x, error_y = _note_centring_error(box, center_x, top, center_y)
    _telemetry.info(
        f"pinion-arbor: {label} note {text!r} extent "
        f"({box[0] * 1000:.1f}, {box[1] * 1000:.1f})-({box[2] * 1000:.1f}, "
        f"{box[3] * 1000:.1f}) mm",
        label=label,
    )
    if max(abs(error_x), abs(error_y)) > NOTE_CENTRING_TOL_M:
        raise RuntimeError(
            f"{label} note did not centre: off by ({error_x * 1000:.2f}, "
            f"{error_y * 1000:.2f}) mm"
        )
    texts = _note_texts(view)
    if sum(_is_note_text(found, text) for found in texts) != 1:
        raise RuntimeError(
            f"{label} note did not land in its view: its notes are {texts!r}"
        )
    return box


def _label_detail(
    adapter: Any, detail: Any, principal: Any, mark: tuple[float, float]
) -> None:
    """Label detail A under its crop circle and letter its mark on the profile."""
    drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
    sheet = _early_bound(drawing.GetCurrentSheet(), "ISheet")
    if not sheet.SetScale(*SHEET_SCALE, False, False):
        raise RuntimeError(
            "failed to pin sheet scale before placing the detail-A label"
        )
    box = _centred_view_note(
        adapter,
        detail,
        DETAIL_LABEL_TEXT,
        center_x=DETAIL_LABEL_XY[0],
        top=DETAIL_LABEL_XY[1],
        label="detail-A label",
    )
    if (box[2] - box[0]) / 2.0 > DETAIL_LABEL_HALF_WIDTH:
        _telemetry.warn(
            f"pinion-arbor: detail-A label is {(box[2] - box[0]) * 1000:.1f} mm wide, "
            f"past the {2 * DETAIL_LABEL_HALF_WIDTH * 1000:.0f} mm its neighbours "
            "were placed against"
        )
    _centred_view_note(
        adapter,
        principal,
        DETAIL_LETTER,
        center_x=mark[0] + DETAIL_LETTER_OFFSET[0],
        center_y=mark[1] + DETAIL_LETTER_OFFSET[1],
        label="detail-A letter",
    )


def _add_turning_axis(adapter: Any, view: Any) -> None:
    """Draw one centreline over the whole turned axis.

    The journal split lines cut the Ø8 cylinder into five faces, so a
    face-derived ``InsertCenterLine2`` would cover a single zone.  The axis is
    instead a view-sketch centreline between two model points on it, created
    direct-to-database so screen-space inference cannot snap an end onto the
    crown apex.
    """
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    if not drawing.ActivateView(view_name(adapter, view)):
        raise RuntimeError("failed to activate the integral-arbor profile for its axis")
    draw.ClearSelection2(True)
    sketch = _early_bound(_early_bound(view, "IView").GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    front_z = HEAD_FRONT_Z - HEAD_CAP_SAG - AXIS_OVERSHOOT_MM
    points = []
    for z in (front_z, front_z + OVERALL_LEN + 2.0 * AXIS_OVERSHOOT_MM):
        x, y = model_point_in_view(
            adapter, view, (0.0, 0.0, z / 1000.0), label="integral-arbor axis end"
        )
        point = _early_bound(utility.CreatePoint(double_array([x, y, 0.0])), "IMathPoint")
        projected = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
        points.append(tuple(float(value) for value in projected.ArrayData))
    manager = _early_bound(draw.SketchManager, "ISketchManager")
    previous_add_to_db = bool(manager.AddToDB)
    manager.AddToDB = True
    try:
        segment = manager.CreateCenterLine(*points[0], *points[1])
    finally:
        manager.AddToDB = previous_add_to_db
    if segment is None:
        raise RuntimeError("failed to create the integral-arbor turning axis")
    segment = _early_bound(segment, "ISketchSegment")
    segment.Color = 0  # COLORREF black, not the under-defined sketch blue.
    if int(segment.Color) != 0:
        raise RuntimeError("integral-arbor turning axis colour did not persist")
    draw.ClearSelection2(True)
    draw.EditRebuild3()


def _reference_witness_in_view(view: Any, sketch_name: str, length_mm: float) -> Any:
    """The drawing-view instance of one reference sketch's flank witness.

    Chosen on the model -- the named sketch's one construction segment of the
    witness's length -- then mapped into ``view``.  A point pick at the
    witness's midpoint twice resolved to BackRimReference's 227.5 line on the
    same flank (w8 at 437c56d4c, w7 at 7f7fc1717), and the user ruled that a
    fragile pick selects the model entity instead.
    """
    native = _early_bound(view, "IView")
    model = native.ReferencedDocument
    if model is None:
        raise RuntimeError(f"{sketch_name}: the profile view references no model")
    feature = _early_bound(model, "IPartDoc").FeatureByName(sketch_name)
    if feature is None:
        raise RuntimeError(f"{sketch_name}: no such feature in the arbor model")
    sketch = _early_bound(_early_bound(feature, "IFeature").GetSpecificFeature2(), "ISketch")
    matches = []
    for raw in sketch.GetSketchSegments() or ():
        segment = _early_bound(raw, "ISketchSegment")
        length = float(segment.GetLength()) * 1000.0
        construction = bool(segment.ConstructionGeometry)
        if construction and abs(length - length_mm) <= REFERENCE_WITNESS_LEN_TOL:
            matches.append(segment)
    if len(matches) != 1:
        raise RuntimeError(
            f"{sketch_name}: {len(matches)} construction segments are "
            f"{length_mm:.3f} mm long; the witness must be exactly one"
        )
    in_view = native.GetCorresponding(matches[0])
    if in_view is None:
        raise RuntimeError(f"{sketch_name}: the witness has no instance in the profile view")
    return _early_bound(in_view, "ISketchSegment")


def _blacken_reference_witnesses(
    adapter: Any, view: Any
) -> dict[str, tuple[tuple[float, float], tuple[float, float]]]:
    """Draw each reference sketch's flank witness in the outline's black.

    Returns each witness's sheet endpoints for the exported-raster check.
    """
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    if not drawing.ActivateView(view_name(adapter, view)):
        raise RuntimeError("failed to activate the integral-arbor profile for its witnesses")
    flank_x = SHAFT_DIA / 2000.0
    spans = {}
    for sketch_name, (z0, z1) in REFERENCE_WITNESSES.items():
        ends = tuple(
            model_point_in_view(
                adapter, view, (flank_x, 0.0, z / 1000.0), label=f"{sketch_name} witness end"
            )
            for z in (z0, z1)
        )
        mid = ((ends[0][0] + ends[1][0]) / 2.0, (ends[0][1] + ends[1][1]) / 2.0)
        expected = z1 - z0
        witness = _reference_witness_in_view(view, sketch_name, expected)
        draw.ClearSelection2(True)
        selection = _early_bound(draw.SelectionManager, "ISelectionMgr")
        selection_data = selection.CreateSelectData()
        selection_data.View = view
        if not witness.Select4(False, selection_data):
            raise RuntimeError(f"failed to select the {sketch_name} flank witness")
        kind = int(selection.GetSelectedObjectType3(1, -1))
        if kind != SW_SEL_EXT_SKETCH_SEGS:
            raise RuntimeError(f"{sketch_name} witness pick resolved to type {kind}")
        segment = _early_bound(selection.GetSelectedObject6(1, -1), "ISketchSegment")
        # Re-check what the selection holds by its own length, not its
        # sketch's name: an ISketch is not an IFeature dispatch, so rebinding
        # it reads another member (7885c0d9 got a 16-double matrix back for
        # ``Name``).
        name = str(segment.GetName())
        length = float(segment.GetLength()) * 1000.0
        construction = bool(segment.ConstructionGeometry)
        if abs(length - expected) > REFERENCE_WITNESS_LEN_TOL or not construction:
            raise RuntimeError(
                f"{sketch_name} witness pick resolved to {name} "
                f"({length:.3f} mm, want {expected:.3f}; construction={construction})"
            )
        drawing.SetLineColor(REFERENCE_WITNESS_COLOR)
        draw.ClearSelection2(True)
        spans[sketch_name] = ends
        _telemetry.info(
            f"pinion-arbor: {sketch_name} flank witness drawn black at sheet "
            f"({mid[0] * 1000:.1f}, {mid[1] * 1000:.1f}) mm",
            sketch=sketch_name,
        )
    draw.EditRebuild3()
    return spans


def _broken_outline_columns(
    raster: Any,
    spans: dict[str, tuple[tuple[float, float], tuple[float, float]]],
    sheet_size: tuple[float, float],
) -> dict[str, list[int]]:
    """Return, per witness, the raster columns where the outline is not dark."""
    gray = raster.convert("L")
    scale = gray.width / sheet_size[0]
    broken = {}
    for name, ((x0, y), (x1, _)) in spans.items():
        row = round((sheet_size[1] - y) * scale)
        rows = range(row - OUTLINE_SEARCH_ROWS, row + OUTLINE_SEARCH_ROWS + 1)
        columns = range(round(min(x0, x1) * scale), round(max(x0, x1) * scale) + 1)
        broken[name] = [
            column
            for column in columns
            if sum(gray.getpixel((column, r)) <= OUTLINE_DARK_MAX for r in rows)
            < OUTLINE_CORE_ROWS
        ]
    return {name: columns for name, columns in broken.items() if columns}


def _assert_outline_unbroken(
    png: Any,
    spans: dict[str, tuple[tuple[float, float], tuple[float, float]]],
    sheet_size: tuple[float, float],
) -> None:
    from PIL import Image

    with Image.open(png) as raster:
        broken = _broken_outline_columns(raster, spans, sheet_size)
    if broken:
        detail = "; ".join(
            f"{name}: {len(columns)} column(s) from x={columns[0]} px"
            for name, columns in broken.items()
        )
        raise RuntimeError(f"pinion-arbor: Ø8 outline broken over reference witness: {detail}")
    _telemetry.info(
        f"pinion-arbor: Ø8 outline unbroken over {len(spans)} reference witnesses",
        witnesses=len(spans),
    )


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open pinion-arbor source", await adapter.open_model(str(SOURCE)))
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
            0: "Integral Pinion Arbor Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "integral arbor and grip head; reamed, bonded crossrod hole",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    donor = place_view(adapter, str(SOURCE), "*Front", 0.030, 0.180, scale=(2, 1))
    # Looking along model Y presents the reamed cross-hole as a true
    # circle while retaining the entire turned profile in one horizontal view.
    principal = place_view(
        adapter, str(SOURCE), "*Top", *PRINCIPAL_CENTER, scale=SHEET_SCALE
    )
    native_principal = _early_bound(principal, "IView")
    native_principal.Angle = -math.pi / 2.0
    if abs(math.remainder(float(native_principal.Angle) + math.pi / 2.0, 2.0 * math.pi)) > 1e-9:
        raise RuntimeError("failed to orient the integral arbor horizontally")
    drawing_model.EditRebuild3()
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 2))
    for view in (donor, principal, iso):
        set_hidden_lines_removed(adapter, view)

    mark_center = _mark_detail_on_profile(adapter, principal)
    detail = _cropped_head_view(adapter, principal)
    set_hidden_lines_removed(adapter, detail)
    _early_bound(detail, "IView").UpdateViewDisplayGeometry()
    # Detail A imports FIRST, feature by feature: a model dimension already on
    # the sheet is not imported again, so the donor's whole-model import below
    # would otherwise take NeckDia and CrossHoleDia.  A missing dimension
    # fails here, naming what did arrive (insert_feature_dimensions logs it).
    detail_annotations = curate_view_dimensions(
        adapter,
        detail,
        keep=DETAIL_KEEP,
        view_label="integral-arbor head detail",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    donor_annotations = curate_view_dimensions(
        adapter, donor, keep=DONOR_KEEP, view_label="diameter donor"
    )
    # The profile prints every reference-sketch dimension.  The part saves
    # those sketches hidden (#880), so this projected view shows them per view
    # and imports feature by feature (_drawing_hidden_sketches).  The donor and
    # detail A dimension none of them, so neither needs them shown.
    principal_annotations = curate_hidden_owner_dimensions(
        adapter,
        principal,
        keep=PRINCIPAL_KEEP,
        view_label="integral-arbor profile",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    for label, kept in (
        ("detail", detail_annotations),
        ("donor", donor_annotations),
        ("principal", principal_annotations),
    ):
        names = sorted(dimension_name(adapter, annotation) for annotation in kept)
        _telemetry.info(
            f"pinion-arbor {label} view kept {len(kept)} imported dimensions: {names}",
            view=label,
            kept=len(kept),
            names=",".join(names),
        )
    # The donor's diameters move onto the 1:1 profile, a model view (the
    # HeadDia move every build has made); none moves into detail A.
    moved_diameters = []
    moves = []
    for annotation in donor_annotations:
        name = dimension_name(adapter, annotation)
        text_xy = DIAMETER_POSITIONS[name]
        moved_diameters.append(
            _move_dimension(adapter, annotation, principal, text_xy, source_view=donor)
        )
        moves.append(
            f"{name} -> principal ({text_xy[0] * 1000:.1f}, {text_xy[1] * 1000:.1f}) mm"
        )
    principal_count = len(_early_bound(principal, "IView").GetAnnotations() or ())
    detail_count = len(_early_bound(detail, "IView").GetAnnotations() or ())
    _telemetry.info(
        f"pinion-arbor moved {len(moved_diameters)} diameters off the donor: "
        f"{'; '.join(moves)}; principal now carries {principal_count} "
        f"annotations, detail {detail_count}",
        moved=len(moved_diameters),
        moves="; ".join(moves),
        principal_annotations=principal_count,
        detail_annotations=detail_count,
    )
    donor_name = view_name(adapter, donor)
    delete_view(adapter, donor)
    if any(view_name(adapter, view) == donor_name for view in iter_views(adapter)):
        raise RuntimeError("failed to delete the empty diameter donor view")
    annotations = [
        *moved_diameters,
        *principal_annotations,
        *detail_annotations,
    ]
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    _radius_leader_outside(adapter, detail_annotations, "HeadCapR")
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    for name, label in {
        "HeadCapSagDim": "front-crown height reference",
        "BackCapSagDim": "back-crown descriptive reference",
        "OverallLen": "overall length reference",
    }.items():
        matches = [
            annotation
            for annotation in annotations
            if dimension_name(adapter, annotation) == name
        ]
        if len(matches) != 1:
            raise RuntimeError(f"expected one {label}")
        set_reference_dimension(adapter, matches[0], label=label)

    if not auto_center_marks(adapter, detail, holes=True, size=0.0025):
        raise RuntimeError("failed to add center mark to the detailed grip cross-hole")
    _add_turning_axis(adapter, principal)
    witness_spans = _blacken_reference_witnesses(adapter, principal)
    for key, (station_z, symbol_xy, flank) in JOURNAL_FINISHES.items():
        land_x, axis_y = model_point_in_view(
            adapter,
            principal,
            (0.0, 0.0, station_z / 1000.0),
            label=f"arbor {key} finish station",
        )
        add_surface_finish(
            adapter,
            principal,
            edge_xy=(land_x, axis_y + FLANK_SIGN[flank] * SHAFT_DIA / 2000.0),
            symbol_xy=symbol_xy,
            control=surface_finish_by_key(SURFACE_FINISHES, key),
            label=f"arbor {key} finish",
            entity_type="SILHOUETTE",
            char_height=0.0025,
        )
    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.060)
    add_property_linked_note(adapter, "Isometric View Note", 0.335, 0.255)
    _label_detail(adapter, detail, principal, mark_center)
    rebuild_drawing(adapter, label="pinion arbor layout audit")
    sheets = collect_document(adapter)
    _assert_no_text_on_line([f for sheet in sheets for f in audit_sheet(sheet)])
    fence_center = model_point_in_view(
        adapter,
        principal,
        (0.0, 0.0, HEAD_CENTER_Z / 1000.0),
        label="integral-arbor detail fence centre",
    )
    far_on_axis = model_point_in_view(
        adapter,
        principal,
        (0.0, 0.0, (HEAD_CENTER_Z + OVERALL_LEN) / 1000.0),
        label="integral-arbor axis direction",
    )
    arrows = _dimension_arrows(adapter, principal)
    # The tips ride the message text, not only an attribute: a farm leaf's
    # task.log and the fleet workspace carry the text alone.
    directions = ", ".join(
        f"{name} tip ({tx * 1000:.1f}, {ty * 1000:.1f}) mm dir ({dx:.3f}, {dy:.3f})"
        for name, ((tx, ty), (dx, dy)) in sorted(arrows.items())
    )
    _telemetry.info(
        f"pinion-arbor: {len(arrows)} profile dimensions carry a readable "
        f"arrowhead: {directions}",
        arrows=len(arrows),
        directions=directions,
    )
    _assert_witnesses_clear_of_detail_fence(
        _view_dimensions(sheets, view_name(adapter, principal)),
        center=fence_center,
        radius=DETAIL_RADIUS_MM / 1000.0,
        arrows=arrows,
        axis=_unit(far_on_axis[0] - fence_center[0], far_on_axis[1] - fence_center[1]),
    )
    # Every dimension in detail A answers to its crop circle with the same
    # classifier: a witness stays on the part inside the circle unless it is
    # a station witness (HeadLen, the (3.0) crown height, measured along the
    # axis), and only a dimension line may leave for its text.  NeckDia,
    # measured across the axis, must keep both witnesses inside.
    detail_name = view_name(adapter, detail)
    detail_dimensions = _view_dimensions(sheets, detail_name)
    detail_arrows = _dimension_arrows(adapter, detail)
    for annotation in detail_dimensions:
        boxes = " ".join(box.format_mm() for box in annotation.text_boxes) or "(no text)"
        runs = " ".join(segment.format_mm() for segment in annotation.segments)
        arrow = detail_arrows.get(annotation.label)
        tip = (
            "no readable arrowhead"
            if arrow is None
            else f"arrow tip ({arrow[0][0] * 1000:.1f}, {arrow[0][1] * 1000:.1f}) mm "
            f"dir ({arrow[1][0]:.3f}, {arrow[1][1]:.3f})"
        )
        _telemetry.info(
            f"pinion-arbor: detail-A {annotation.label} text {boxes}; runs {runs}; {tip}",
            label=annotation.label,
        )
    audited = sorted(annotation.label for annotation in detail_dimensions)
    if audited != sorted(DETAIL_KEEP):
        raise RuntimeError(
            f"pinion-arbor: the layout audit reads detail A's dimensions as "
            f"{audited}, expected {sorted(DETAIL_KEEP)}"
        )
    detail_axis, _span = _axis_on_sheet(adapter, detail, label="detail-A audit axis")
    _assert_witnesses_clear_of_detail_fence(
        detail_dimensions,
        center=DETAIL_CENTER,
        radius=DETAIL_CROP_RADIUS,
        arrows=detail_arrows,
        axis=detail_axis,
    )

    sheet = _early_bound(
        _early_bound(adapter.currentModel, "IDrawingDoc").GetCurrentSheet(), "ISheet"
    )
    properties = tuple(float(value) for value in sheet.GetProperties2())
    sheet_size = (properties[5], properties[6])
    outputs = await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Integral Pinion Arbor Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
    )
    _assert_outline_unbroken(PNG, witness_spans, sheet_size)
    return outputs


# Text on text joined the gate with the bond-zone callout's move above the
# shaft, beside the DETAIL A label (63468ee9 read 0 advisory findings).
# Leader on leader joined with the back Ra symbol's move above the shaft: at
# c6eb7f6f its shoulder crossed the back land's 19.0 witness (Main).
BLOCKING_LAYOUT_FINDINGS = frozenset(
    {"text-on-line", "text-on-text", "leader-crosses-leader"}
)


def _assert_no_text_on_line(findings: list[Any]) -> None:
    """Fail the sheet when any annotation's text sits on another's line or text.

    Main's eye-pass of 30620a85 found the back-crown and overall witnesses
    running through the back journal's "8.00" and "JOURNAL".  The native audit
    reads every dimension's rendered witness, dimension and leader segments, so
    that defect is now a build failure with sheet-millimetre fix coordinates.
    Text on text is gated too, since the bond-zone callout moved above the
    shaft beside the DETAIL A label.  The audit's other finding kinds are
    logged, not gated: a diametric leader crossing another inside a detail
    is conventional ink.
    """
    blocking = [f for f in findings if f.kind in BLOCKING_LAYOUT_FINDINGS]
    advisory = [f for f in findings if f.kind not in BLOCKING_LAYOUT_FINDINGS]
    if advisory:
        _telemetry.warn(
            f"pinion-arbor layout audit: {len(advisory)} advisory finding(s)\n"
            + format_findings(advisory),
            advisory=len(advisory),
        )
    if blocking:
        raise RuntimeError(
            f"pinion-arbor layout audit: {len(blocking)} blocking finding(s)\n"
            + format_findings(blocking)
        )
    _telemetry.success(
        f"pinion-arbor layout audit: no text on a foreign line or text "
        f"({len(advisory)} advisory)"
    )


FENCE_TOL_M = 0.0002
# A run within this angle of its dimension's measured direction is that
# dimension's line; within this angle of the perpendicular, an extension line.
# Anything between is neither and is judged like an extension line.
DIRECTION_TOL_RAD = math.radians(5.0)
# An arrowhead's tip lies on its own dimension line, or on its extension past
# a run that stops at the arrow's base.
ARROW_ON_LINE_TOL_M = 0.0005
ARROW_REACH_M = 0.005
# swAnnotationType_e.swDisplayDimension
_SW_DISPLAY_DIMENSION = 4

Arrow = tuple[tuple[float, float], tuple[float, float]]


def _unit(dx: float, dy: float) -> tuple[float, float]:
    length = math.hypot(dx, dy)
    if length == 0.0:
        raise ValueError("a direction needs a non-zero vector")
    return dx / length, dy / length


def _dimension_arrows(adapter: Any, view: Any) -> dict[str, Arrow]:
    """Each dimension's first arrowhead on ``view``: its tip and unit direction.

    ``IDisplayData`` labels no run as extension or dimension line, and
    ``IDimension::DimensionLineDirection`` answers feature dimensions only,
    while this sheet mixes feature and sketch dimensions.  An arrowhead, the
    one signal every dimension carries, points along its own
    dimension line (``IDisplayData::GetArrowHeadAtIndex2``: tip[3], dir[3],
    ...), so it names the dimension's measured direction on the sheet.
    """
    arrows = {}
    for item in _early_bound(view, "IView").GetAnnotations() or ():
        annotation = _early_bound(item, "IAnnotation")
        if int(annotation.GetType()) != _SW_DISPLAY_DIMENSION:
            continue
        data = annotation.GetDisplayData()
        if data is None:
            continue
        data = _early_bound(data, "IDisplayData")
        for index in range(int(data.GetArrowHeadCount() or 0)):
            values = [float(value) for value in (data.GetArrowHeadAtIndex2(index) or ())]
            if len(values) < 6 or math.hypot(values[3], values[4]) < 1e-9:
                continue
            arrows[str(annotation.GetName())] = (
                (values[0], values[1]),
                _unit(values[3], values[4]),
            )
            break
    return arrows


def _segment_kind(segment: Any, measured: tuple[float, float]) -> str:
    """Classify one straight run against its own dimension's measured direction."""
    direction = _unit(segment.x1 - segment.x0, segment.y1 - segment.y0)
    along = abs(direction[0] * measured[0] + direction[1] * measured[1])
    if along >= math.cos(DIRECTION_TOL_RAD):
        return "dimension-line"
    if along <= math.sin(DIRECTION_TOL_RAD):
        return "extension-line"
    return "oblique"


def _on_line_through(point: tuple[float, float], segment: Any) -> bool:
    """``point`` lies on ``segment``'s line, within an arrow's reach of its ends."""
    direction = _unit(segment.x1 - segment.x0, segment.y1 - segment.y0)
    dx, dy = point[0] - segment.x0, point[1] - segment.y0
    along = dx * direction[0] + dy * direction[1]
    across = abs(dx * direction[1] - dy * direction[0])
    return (
        across <= ARROW_ON_LINE_TOL_M
        and -ARROW_REACH_M <= along <= segment.length + ARROW_REACH_M
    )


def _measured_direction(annotation: Any, arrow: Arrow | None) -> tuple[float, float] | None:
    """The arrowhead's direction, once its tip is proven to sit on its own line."""
    if arrow is None:
        return None
    tip, measured = arrow
    on_own_line = any(
        _segment_kind(segment, measured) == "dimension-line"
        and _on_line_through(tip, segment)
        for segment in annotation.segments
        if segment.length > 0.0
    )
    if not on_own_line:
        raise RuntimeError(
            f"{annotation.label!r}: arrowhead at ({tip[0] * 1000:.1f},"
            f"{tip[1] * 1000:.1f})mm lies on none of its own parallel runs; "
            "its measured direction is unreadable"
        )
    return measured


def _assert_witnesses_clear_of_detail_fence(
    annotations: list[Any],
    *,
    center: tuple[float, float],
    radius: float,
    arrows: dict[str, Arrow],
    axis: tuple[float, float],
) -> None:
    """No extension line may run out through the detail-A fence on the profile.

    The head sits inside the fence, so every head dimension starts inside it.
    Each crossing run is judged against ITS OWN dimension (Main's ruling on
    run 492a7be5).  The dimension line, parallel to the measured direction,
    may cross the fence to reach its text, as any line may cross a line.  An
    extension line, perpendicular to it, may leave only as a station witness,
    belonging to a dimension measured along the turning axis, which drops to
    the station stack.  Anything else leaving the circle (the Ø15.0 witnesses
    did, with the "A" label between them) reads as part of the detail callout.
    A dimension with no readable arrowhead is judged as all extension lines.
    """
    offenders = []
    for annotation in annotations:
        crossing = []
        for segment in annotation.segments:
            if segment.role != "line":
                continue
            ends = ((segment.x0, segment.y0), (segment.x1, segment.y1))
            far = max(math.dist(end, center) for end in ends)
            near = _segment_distance(center, ends)
            if near < radius - FENCE_TOL_M and far > radius + FENCE_TOL_M:
                crossing.append(segment)
        if not crossing:
            continue
        measured = _measured_direction(annotation, arrows.get(annotation.label))
        axial = measured is not None and abs(
            measured[0] * axis[0] + measured[1] * axis[1]
        ) >= math.cos(DIRECTION_TOL_RAD)
        for segment in crossing:
            kind = "extension-line" if measured is None else _segment_kind(segment, measured)
            if kind == "dimension-line":
                continue
            if kind == "extension-line" and axial:
                continue
            offenders.append(
                f"{annotation.label!r} {kind} "
                f"({segment.x0 * 1000:.1f},{segment.y0 * 1000:.1f})-"
                f"({segment.x1 * 1000:.1f},{segment.y1 * 1000:.1f})mm"
            )
    if offenders:
        raise RuntimeError(
            f"pinion-arbor: {len(offenders)} extension line(s) cross the detail-A "
            "fence:\n  " + "\n  ".join(offenders)
        )
    _telemetry.success("pinion-arbor: no extension line crosses the detail-A fence")


def _view_dimensions(sheets: list[Any], owner: str) -> list[Any]:
    """The layout audit's dimensions owned by the view named ``owner``."""
    return [
        annotation
        for sheet in sheets
        for annotation in sheet.annotations
        if annotation.owner == owner and annotation.kind == "dim"
    ]


def _segment_distance(
    point: tuple[float, float],
    ends: tuple[tuple[float, float], tuple[float, float]],
) -> float:
    (x0, y0), (x1, y1) = ends
    dx, dy = x1 - x0, y1 - y0
    span = dx * dx + dy * dy
    if span == 0.0:
        return math.dist(point, (x0, y0))
    t = max(0.0, min(1.0, ((point[0] - x0) * dx + (point[1] - y0) * dy) / span))
    return math.dist(point, (x0 + t * dx, y0 + t * dy))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
