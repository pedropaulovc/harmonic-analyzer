r"""Create the integral MHA-102 pinion-arbor manufacturing drawing."""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
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
# Detail A is a cropped 2:1 *model* view, not a native detail: a native
# detail refused every DragModelDimension into it (neckbisect-ecef: from the
# profile by move, copy and centre drop; pc-r5-860: straight from the donor),
# while a model view takes one every build (HeadDia, donor -> profile).  A
# model view has no native label, so "DETAIL A / SCALE 2 : 1" is a note the
# view owns, centred under its crop circle this far below it (the extent's top
# edge): clear of the HeadLen text that rides the circle's lower edge.  The
# profile keeps the crop's 1:1 circle and an "A" note it owns.
DETAIL_LETTER = "A"
DETAIL_LABEL = f"DETAIL {DETAIL_LETTER}\nSCALE {DETAIL_SCALE[0]} : {DETAIL_SCALE[1]}"
DETAIL_LABEL_HEIGHT = 0.005
DETAIL_LETTER_HEIGHT = 0.007
DETAIL_LABEL_DROP = 0.012
DETAIL_LABEL_XY = (
    DETAIL_CENTER[0],
    DETAIL_CENTER[1]
    - DETAIL_RADIUS_MM * DETAIL_SCALE[0] / DETAIL_SCALE[1] / 1000.0
    - DETAIL_LABEL_DROP,
)
# The profile's "A" stands right of its 1:1 circle on the axis, where the
# native detail letter printed (a1a694a6: 5.4 mm clear of the circle).
DETAIL_LETTER_GAP = 0.0054
_CROP_NO_ERROR = 1  # swCropViewErrors_e.swCropViewErrors_NoError
# The head centre must land within 0.1 mm of DETAIL_CENTER after the move
# (the MHA-142 tip view's tolerance).
DETAIL_POSITION_TOL_M = 1e-4
# The head and neck diameters live in end-on Front-plane profile sketches, so
# the end-on donor imports them: the head's moves onto the 1:1 profile, the
# neck's into detail A (DETAIL_DIAMETER_POSITIONS says why).  The Ø8
# is dimensioned on the profile itself, from the bond zone's flank.
DONOR_KEEP = {
    "NeckDia": (0.055, 0.145),
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
DETAIL_KEEP = {
    "HeadLen": (0.165, 0.201),
    "HeadCapR": (0.195, 0.262),
    "HeadCapSagDim": (0.205, 0.210),
    # Above the hole's centre line, so the leader drops onto the hole edge.
    "CrossHoleDia": (0.245, 0.256),
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
DETAIL_RATIO = DETAIL_SCALE[0] / DETAIL_SCALE[1]


def _detail_x(model_z: float) -> float:
    """Sheet x of a model station inside detail A (head centre at its centre)."""
    return DETAIL_CENTER[0] + DETAIL_RATIO * (
        _sheet_x(model_z) - _sheet_x(HEAD_CENTER_Z)
    )


# In detail A the neck runs from the fence (x ~0.137 at its edges) to the
# head rear face (x 0.1545), its Ø10.5 at y 0.2245-0.2455.  Its end-on
# circle is on the Front plane (model z 0, x 0.152), where the witnesses
# start, so a line at x 0.140 on the neck's fence side keeps both witnesses
# on the neck.  The text runs on past the line, away from that circle (the
# profile rendered it left of its line at a1a694a6), so it rides above-left
# of the fence, clear of the circle like every other detail-A callout; the
# line crosses the fence once, square, to reach it.
DETAIL_DIAMETER_POSITIONS = {
    "NeckDia": (0.140, 0.2575),
}
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


def _sketch_circle_in_view(
    adapter: Any, view: Any, center: tuple[float, float], radius: float, *, label: str
) -> None:
    """Sketch a circle in ``view``'s own sketch from SHEET coordinates and
    leave it selected (what Crop2 consumes).  The caller activates the view."""
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
    if manager.CreateCircle(*points[0], *points[1]) is None:
        raise RuntimeError(f"failed to sketch the {label} circle")


def _activate(adapter: Any, view: Any, *, label: str) -> None:
    drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
    if not drawing.ActivateView(view_name(adapter, view)):
        raise RuntimeError(f"failed to activate the {label}")
    adapter.currentModel.ClearSelection2(True)


def _head_detail(adapter: Any, parent_view: Any) -> Any:
    """Detail A: the profile's *Top at 2:1, turned like it, moved so the head
    centre lands on DETAIL_CENTER and cropped by the fence circle.

    Sequence (the MHA-142 tip view's, b6552f13b): place; set the profile's
    angle and rebuild BEFORE measuring, or the head lands sideways; move by
    the head centre's sheet error; activate; sketch the fence in the view's
    own sketch; Crop2 while the circle is still selected; read back
    IsCropped.  The profile gets the fence at 1:1 and an "A" of its own.
    """
    draw = adapter.currentModel
    parent = _early_bound(parent_view, "IView")
    view = _early_bound(
        place_view(adapter, str(SOURCE), "*Top", *DETAIL_CENTER, scale=DETAIL_SCALE),
        "IView",
    )
    view.Angle = float(parent.Angle)
    draw.EditRebuild3()
    ratio = tuple(float(value) for value in view.ScaleRatio)
    if ratio != tuple(float(value) for value in DETAIL_SCALE):
        raise RuntimeError(f"detail A scale {ratio!r}, expected {DETAIL_SCALE!r}")
    head_center = (0.0, 0.0, HEAD_CENTER_Z / 1000.0)
    center = model_point_in_view(
        adapter, view, head_center, label="detail A head centre"
    )
    position = tuple(float(value) for value in view.Position)
    target = [position[axis] + DETAIL_CENTER[axis] - center[axis] for axis in range(2)]
    if not view.SetViewPosition(double_array(target), False):
        raise RuntimeError("failed to position detail A")
    draw.EditRebuild3()
    center = model_point_in_view(
        adapter, view, head_center, label="detail A head centre"
    )
    if math.dist(center, DETAIL_CENTER) > DETAIL_POSITION_TOL_M:
        raise RuntimeError(
            f"detail A head centre sits at {center!r}, not {DETAIL_CENTER!r}"
        )
    _activate(adapter, view, label="detail A")
    crop_radius = DETAIL_RATIO * DETAIL_RADIUS_MM / 1000.0
    _sketch_circle_in_view(adapter, view, center, crop_radius, label="detail A crop")
    status = int(view.Crop2(False, False, 5))
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    cropped = bool(view.IsCropped())
    _telemetry.info(
        f"detail A {view_name(adapter, view)!r}: {ratio[0]:g}:{ratio[1]:g}, "
        f"Crop2 status {status}, IsCropped {cropped}",
        crop_status=status,
        cropped=cropped,
    )
    if status != _CROP_NO_ERROR or not cropped:
        raise RuntimeError(
            f"detail A is not cropped: Crop2 status {status}, IsCropped {cropped}"
        )

    _activate(adapter, parent_view, label="integral-arbor detail parent")
    fence = model_point_in_view(
        adapter, parent_view, head_center, label="integral-arbor head detail centre"
    )
    radius = DETAIL_RADIUS_MM / 1000.0
    _sketch_circle_in_view(
        adapter, parent_view, fence, radius, label="profile detail fence"
    )
    draw.ClearSelection2(True)
    _view_note(
        adapter,
        parent_view,
        DETAIL_LETTER,
        (fence[0] + radius + DETAIL_LETTER_GAP, fence[1]),
        height=DETAIL_LETTER_HEIGHT,
        anchor="left-middle",
        label="profile detail letter",
    )
    return view


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


def _view_note(
    adapter: Any,
    view: Any,
    text: str,
    xy: tuple[float, float],
    *,
    height: float,
    anchor: str,
    label: str,
) -> Any:
    """A note owned by ``view`` (inserted while it is active), sized, then
    moved so its extent's ``anchor`` point sits on ``xy``.

    A free note's position is not its extent (the anchor is the text's top
    left), so the move reads INote.GetExtent back and shifts by the error.
    ``anchor`` is "centre-top" (a label under its circle) or "left-middle"
    (a letter beside it).  Read back: the view owns the note exactly once.
    """
    _activate(adapter, view, label=label)
    note = add_note(adapter, text, *xy)
    if note is None:
        raise RuntimeError(f"failed to add the {label}")
    note = _early_bound(note, "INote")
    annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
    text_format = annotation.GetTextFormat(0)
    if text_format is None:
        raise RuntimeError(f"the {label} has no text format")
    text_format.CharHeight = float(height)
    if not annotation.SetTextFormat(0, False, text_format):
        raise RuntimeError(f"failed to size the {label}")
    adapter.currentModel.EditRebuild3()
    for _attempt in range(2):
        x0, y0, _z0, x1, y1, _z1 = (float(value) for value in note.GetExtent())
        actual = (
            ((x0 + x1) / 2.0, max(y0, y1))
            if anchor == "centre-top"
            else (min(x0, x1), (y0 + y1) / 2.0)
        )
        error = (xy[0] - actual[0], xy[1] - actual[1])
        if math.hypot(*error) <= 1e-5:
            break
        position = tuple(float(value) for value in annotation.GetPosition())
        moved = (position[0] + error[0], position[1] + error[1], 0.0)
        if not annotation.SetPosition2(*moved):
            raise RuntimeError(f"failed to move the {label}")
        adapter.currentModel.EditRebuild3()
    else:
        raise RuntimeError(f"the {label} extent sits at {actual!r}, not {xy!r}")
    texts = [
        str(_early_bound(item, "INote").GetText())
        for item in (_early_bound(view, "IView").GetNotes() or ())
    ]
    if texts.count(text) != 1:
        raise RuntimeError(
            f"the {label} did not land in its view: its notes are {texts!r}"
        )
    return note


def _position_detail_label(adapter: Any, detail: Any) -> None:
    """Label detail A under its crop circle (a model view has no native one)."""
    _view_note(
        adapter,
        detail,
        DETAIL_LABEL,
        DETAIL_LABEL_XY,
        height=DETAIL_LABEL_HEIGHT,
        anchor="centre-top",
        label="detail A label",
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

    detail = _head_detail(adapter, principal)
    set_hidden_lines_removed(adapter, detail)
    donor_annotations = curate_view_dimensions(
        adapter, donor, keep=DONOR_KEEP, view_label="diameter donor"
    )
    # The profile prints every reference-sketch dimension.  The part saves
    # those sketches hidden (#880), so this projected view shows them per view
    # and imports feature by feature (_drawing_hidden_sketches).  Detail A, a
    # model view too, imports its head features the same way; the donor keeps
    # the whole-model import for the end-on diameters.
    principal_annotations = curate_hidden_owner_dimensions(
        adapter,
        principal,
        keep=PRINCIPAL_KEEP,
        view_label="integral-arbor profile",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    detail_annotations = curate_hidden_owner_dimensions(
        adapter,
        detail,
        keep=DETAIL_KEEP,
        view_label="integral-arbor head detail",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    for label, kept in (
        ("donor", donor_annotations),
        ("principal", principal_annotations),
        ("detail", detail_annotations),
    ):
        names = sorted(dimension_name(adapter, annotation) for annotation in kept)
        _telemetry.info(
            f"pinion-arbor {label} view kept {len(kept)} imported dimensions: {names}",
            view=label,
            kept=len(kept),
            names=",".join(names),
        )
    diameter_targets = {
        **{name: ("principal", principal, xy) for name, xy in DIAMETER_POSITIONS.items()},
        **{name: ("detail", detail, xy) for name, xy in DETAIL_DIAMETER_POSITIONS.items()},
    }
    moved_diameters = []
    moves = []
    for annotation in donor_annotations:
        name = dimension_name(adapter, annotation)
        label, target, text_xy = diameter_targets[name]
        moved_diameters.append(
            _move_dimension(adapter, annotation, target, text_xy, source_view=donor)
        )
        moves.append(f"{name} -> {label} ({text_xy[0] * 1000:.1f}, {text_xy[1] * 1000:.1f}) mm")
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
    _position_detail_label(adapter, detail)
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
        [
            annotation
            for sheet in sheets
            for annotation in sheet.annotations
            if annotation.owner == view_name(adapter, principal)
            and annotation.kind == "dim"
        ],
        center=fence_center,
        radius=DETAIL_RADIUS_MM / 1000.0,
        arrows=arrows,
        axis=_unit(far_on_axis[0] - fence_center[0], far_on_axis[1] - fence_center[1]),
    )
    # The diameters moved INTO detail A answer to its own circle: their
    # witnesses stay on the part inside it, only the dimension line leaves
    # for the text.  The detail's other callouts are leaders and axial
    # stations that leave it by design, so they are not judged here.
    detail_name = view_name(adapter, detail)
    detail_diameters = [
        annotation
        for sheet in sheets
        for annotation in sheet.annotations
        if annotation.owner == detail_name
        and annotation.kind == "dim"
        and annotation.label in DETAIL_DIAMETER_POSITIONS
    ]
    for annotation in detail_diameters:
        boxes = " ".join(box.format_mm() for box in annotation.text_boxes) or "(no text)"
        runs = " ".join(segment.format_mm() for segment in annotation.segments)
        _telemetry.info(
            f"pinion-arbor: detail-A {annotation.label} text {boxes}; runs {runs}",
            label=annotation.label,
        )
    if len(detail_diameters) != len(DETAIL_DIAMETER_POSITIONS):
        raise RuntimeError(
            f"pinion-arbor: detail A carries {len(detail_diameters)} of its "
            f"{len(DETAIL_DIAMETER_POSITIONS)} moved diameters in the layout audit"
        )
    _assert_witnesses_clear_of_detail_fence(
        detail_diameters,
        center=DETAIL_CENTER,
        radius=DETAIL_RATIO * DETAIL_RADIUS_MM / 1000.0,
        arrows=_dimension_arrows(adapter, detail),
        axis=_unit(far_on_axis[0] - fence_center[0], far_on_axis[1] - fence_center[1]),
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
    logged, not gated: the diametric Ø6 leader crossing the SR10.9 leader
    inside detail A is conventional ink.
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
