r"""Create the drawing for the rocker arm's outline template (MHA-CH-006-TL-13).

The face view (``*Front``, 1:1) carries the whole outline from the pivot
hole: both apex heights on the mirror line, both BASIC radii, the arc-end
stations and the tip lands, plus the rod slot's BASIC station; datum A on the
pivot hole, datum C on the rod slot and one surface profile all around the
outline to A|C (``OUTLINE_PROFILE_ZONE``); a cropped 5:1 *Front detail
carries the rod slot's width (a matched fit on its pin gauge) and run; the
right-side edge view carries the plate thickness; a shaded isometric at 1:4
sits above.
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

# The part saves ApexReference and RodSlotReference hidden: this form shows
# each in the view that imports its dimensions.
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_dimensions import (
    assert_imported_precision,
    set_dimension_callouts,
    set_reference_dimension,
)
from _drawing_gdt import add_datum_feature, add_feature_control_frame
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_projection import model_point_in_view
from _drawing_view_display import set_hidden_lines_removed
from _gear_drawing_entities import visible_circle_edge
from _paths import CAD_ROOT
from _session import run_build
import _telemetry
import ch_rocker_arm_tl_outline_template_spec as part_spec
from _feature_requirements import part_metadata, requirement
from _printed_limits import limits
from _gtol_cylinder import CylinderFace
from _gtol_planar import PlanarFace
from ch_rocker_arm_tl_outline_template_spec import (
    ARC_CENTER_CALLOUT,
    DETAIL_SCALE,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    OUTLINE_PROFILE_DATUMS,
    OUTLINE_PROFILE_ZONE,
    PIVOT_CALLOUT,
    PIVOT_DATUM,
    PROFILE_CALLOUT,
    REFERENCE_DIMENSIONS,
    ROD_SLOT_CALLOUT,
    ROD_SLOT_DATUM,
    ROD_SLOT_FLAT_CALLOUT,
    ROD_SLOT_STATION_CALLOUT,
    SHARP_EDGE_CALLOUT,
    STATION_CALLOUT,
    THICK_CALLOUT,
)

SPEC = DRAWINGS_BY_NAME["ch_rocker_arm_tl_outline_template"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"], pdf=SPEC.outputs["pdf"], png=SPEC.outputs["png"]
)
SLDDRW, PDF, PNG = OUTPUTS.slddrw, OUTPUTS.pdf, OUTPUTS.png

# A 292.5 x 29.3 plate: 1:1 is the template's own size and still fits the
# B sheet with every dimension lane outside the outline.
SHEET_SCALE = (1.0, 1.0)
VIEW_SCALE = (1, 1)
ISO_SCALE = (1, 4)
FRONT_CENTER = (0.200, 0.165)
RIGHT_CENTER = (0.400, 0.165)
# Notes start above the title block's top edge so both lines clear it.
NOTES_XY = (0.020, 0.088)
ISO_CENTER = (0.330, 0.240)
ISO_NOTE_XY = (0.250, 0.258)
# The rod slot's 5:1 detail sits in the open field under the notes, left of
# the title block. Its circle takes DETAIL_RADIUS_MM of the part about the
# slot's centre: the whole slot and nothing else.
DETAIL_CENTER = (0.075, 0.040)
DETAIL_RADIUS_MM = 3.0
DETAIL_RATIO = DETAIL_SCALE[0] / DETAIL_SCALE[1]
DETAIL_CROP_RADIUS = DETAIL_RATIO * DETAIL_RADIUS_MM / 1000.0
# Not A or C: those letters are the sheet's datums.
DETAIL_LETTER = "D"
# A model view has no native label the API can show, so the label is a note
# the view owns, in the native detail label's words, anchored at its top
# centre: right of the width's dimension line, under its callout.
DETAIL_LABEL_TEXT = (
    f"DETAIL {DETAIL_LETTER}\nSCALE {DETAIL_SCALE[0]} : {DETAIL_SCALE[1]}"
)
DETAIL_LABEL_XY = (0.116, 0.050)
# The face view's letter goes west of the slot's mark, level with its centre:
# the plate between the pivot and the slot carries nothing else there.
PARENT_LETTER_OFFSET = (
    -(DETAIL_RADIUS_MM * VIEW_SCALE[0] / VIEW_SCALE[1] / 1000.0 + 0.005),
    0.0,
)
# swCropViewErrors_e.swCropViewErrors_NoError
CROP_NO_ERROR = 1
# The slot's centre must land within 0.1 mm of DETAIL_CENTER after the move.
DETAIL_POSITION_TOL_M = 1e-4
NOTE_CENTRING_TOL_M = 0.001
NOTE_CENTRING_PASSES = 2
# Radius text stays outside both circles (below the outline) and each radius
# keeps its arrow outside the arc with no solid leader, so its leader runs
# from the text to its arc and stops: never on to the off-sheet centre.  The
# radius blocks sit inboard of the 132.636 extension lines; the bottom apex
# block sits just left of the centreline so the R800 block clears it.
EXTERIOR_RADII = ("TopRadius", "BottomRadius")
FRONT_KEEP = {
    "TopRadius": (0.095, 0.140),
    "BottomRadius": (0.305, 0.140),
    "BottomBelowPivot": (0.188, 0.137),
    "PivotDia": (0.240, 0.140),
    "BottomTailX": (0.133, 0.118),
    "BottomRodX": (0.267, 0.118),
    "TopAbovePivot": (0.222, 0.190),
    "TopTailX": (0.128, 0.207),
    "TopRodX": (0.272, 0.207),
    "TailTipLen": (0.033, 0.197),
    "RodTipLen": (0.367, 0.197),
    # The slot's BASIC station: x in its own lane under the 132.636 lane, y
    # just outboard of the slot with its value below the arrows, clear of the
    # R816.00 block and the edge view's thickness.
    "RodSlotX": (0.267, 0.097),
    "RodSlotY": (0.352, 0.152),
}
# The width's dimension line stands outboard of the crop circle, right of the
# slot's round end, with its value and fit callout above the circle. The
# run's value and its two-line function flag sit right of and below the
# circle, under the detail label: left of the circle the flag would cross it.
# The flag's widest line prints 51.4 mm wide (farm run 3111b8f0a), so its
# centre stands far enough right that the whole line clears the circle.
DETAIL_KEEP = {
    "RodSlotWidth": (DETAIL_CENTER[0] + 0.020, DETAIL_CENTER[1] + 0.028),
    "RodSlotFlat": (DETAIL_CENTER[0] + 0.042, DETAIL_CENTER[1] - 0.012),
}
# Below the edge view and left of its extension lines (the text is far wider
# than the 3.175 span), clear of the front view's rod tip and the isometric.
RIGHT_KEEP = {"Thick": (0.370, 0.140)}
# Both arc centres lie on the bore's vertical centreline, off the sheet
# above; the apex heights land on each arc's low point there, and the tip
# lands run radially from those centres.  Each scribing edge carries its
# SHARP requirement and each apex height the rocker edge it sets.  SOLIDWORKS
# centres each apex block on its position, so the extra line grows it upward:
# the positions sit low enough that each stacked band keeps its height,
# clear of the bottom arc and the 144.951 line.
CALLOUTS_BELOW = {
    "TopRadius": f"{ARC_CENTER_CALLOUT}\n{SHARP_EDGE_CALLOUT}",
    "BottomRadius": f"{ARC_CENTER_CALLOUT}\n{SHARP_EDGE_CALLOUT}",
    "TopAbovePivot": "TO TOP ARC LOW POINT\nSETS ROCKER TOP EDGE",
    "BottomBelowPivot": "TO BOTTOM ARC LOW POINT\nSETS ROCKER BOTTOM EDGE",
    "PivotDia": PIVOT_CALLOUT,
    "Thick": THICK_CALLOUT,
    "BottomTailX": STATION_CALLOUT,
    "BottomRodX": STATION_CALLOUT,
    # Each tip land's flag fits between the sheet border (tail) or the
    # 144.951 extension line (rod) and its own extension lines, below the
    # value; its end-face direction rides above.
    "TailTipLen": PROFILE_CALLOUT,
    "RodTipLen": PROFILE_CALLOUT,
    "RodSlotX": ROD_SLOT_STATION_CALLOUT,
    # drawing-guidelines.md rule 4: the slot's width is a matched fit, so the
    # print gives its reference nominal and the clearance on the named pin.
    "RodSlotWidth": ROD_SLOT_CALLOUT,
    # The run prints at three places for its minimum's reach: the flag
    # names that function and the hole it reaches (rule 3).
    "RodSlotFlat": ROD_SLOT_FLAT_CALLOUT,
}
# The top stations take their profile flag above the value: below, it would
# land on the apex block.
CALLOUTS_ABOVE = {
    "TopTailX": STATION_CALLOUT,
    "TopRodX": STATION_CALLOUT,
    "TailTipLen": "RADIAL, SHARP",
    "RodTipLen": "RADIAL, SHARP",
}
# The outline's surface profile, all around, to A|C. Its leader lands on the
# top arc's tail half (PROFILE_LANDING_X_MM off the mirror line) and the
# frame stands above the arc, right of the tail tip's block and under the
# 144.951 station line.
PROFILE_LANDING_X_MM = -70.0
PROFILE_FRAME_XY = (0.080, 0.192)
# Datum A: on the pivot hole's upper-left rim, its tag up and left over the
# plate, clear of the apex heights' witness lines (right) and the R800 block.
PIVOT_DATUM_PICK_DEG = 135.0
PIVOT_DATUM_OFFSET = (-0.012, 0.022)
# Datum C: on the 5:1 detail, where the slot is drawn large (at 1:1 its tag
# would sit inside the detail's mark circle, farm run tl13-gdt-r1): on the
# inboard round end's lower-left rim, its tag down and left, clear of the
# run's extension lines (below the slot) and the width's callout (above).
ROD_SLOT_DATUM_PICK_DEG = 225.0
ROD_SLOT_DATUM_OFFSET = (-0.020, -0.014)

_Z = [0.0, 0.0, 1.0]
_PRECISION = DRAWING_PRECISION_BY_NAME

part_metadata(
    precision_sources=("DRAWING_PRECISION_BY_NAME",),
    datums={
        PIVOT_DATUM: (
            {"feature": "pivot_hole", "surface": "pivot hole"},
            ("PIVOT_DATUM", ("draw_ch_rocker_arm_tl_outline_template", "_add_datums")),
        ),
        ROD_SLOT_DATUM: (
            {"feature": "rod_slot", "surface": "rod slot"},
            (
                "ROD_SLOT_DATUM",
                ("draw_ch_rocker_arm_tl_outline_template", "_add_datums"),
            ),
        ),
    },
)

# The outline's one profile frame, all around, as its own printed strings.
OUTLINE_PROFILE_TEXT = f"{OUTLINE_PROFILE_ZONE:.2f}"
_PROFILE_SOURCES = (
    "OUTLINE_PROFILE_ZONE",
    ("draw_ch_rocker_arm_tl_outline_template", "_add_outline_profile"),
)


def _profile_zone(governs: dict[str, str]) -> dict[str, tuple[Any, tuple[Any, ...]]]:
    """The all-around frame's zone and datums; ``governs`` names this
    feature's own BASICs and the way added material moves each."""
    return {
        "surface_profile": (OUTLINE_PROFILE_ZONE, _PROFILE_SOURCES),
        "surface_profile_datums": (
            list(OUTLINE_PROFILE_DATUMS),
            ("OUTLINE_PROFILE_DATUMS", _PROFILE_SOURCES[1]),
        ),
        "surface_profile_governs": (governs, ("BASIC_DIMENSIONS",)),
    }


requirement(
    "top_edge",
    kind="profile",
    faces=(CylinderFace(2.0 * part_spec.R_TOP),),
    requirements=("height_above_pivot", "radius", "station", "surface_profile"),
    fields={
        "height_above_pivot": (
            limits(
                part_spec.TOP_ABOVE_PIVOT,
                _PRECISION["TopAbovePivot"],
                part_spec.LOW_POINT_BAND,
            ),
            (
                "TOP_ABOVE_PIVOT",
                "LOW_POINT_BAND",
                ("ch_rocker_arm_spec", "TOP_EDGE_BAND"),
            ),
        ),
        "height_nominal": (part_spec.TOP_ABOVE_PIVOT, ("TOP_ABOVE_PIVOT",)),
        "height_from": (
            "pivot_hole",
            (("draw_ch_rocker_arm_tl_outline_template", "build"),),
        ),
        # BASIC: the outline profile is the radius's tolerance.
        "radius": (part_spec.R_TOP, ("R_TOP", "BASIC_DIMENSIONS")),
        "dimension_type": ("basic", ("BASIC_DIMENSIONS",)),
        # Material added on the top edge moves it toward the arcs' centre.
        **_profile_zone({"radius": "decreases"}),
        "radius_nominal": (part_spec.R_TOP, ("R_TOP",)),
        "arc_centre": ([0.0, part_spec.CENTER_Y, 0.0], ("CENTER_Y",)),
        "station": (
            limits(part_spec.TOP_END_X, _PRECISION["TopRodX"]),
            ("TOP_END_X", "END_PLACES"),
        ),
        "station_nominal": (part_spec.TOP_END_X, ("TOP_END_X",)),
        "end": (
            [part_spec.TOP_END_X, part_spec.TOP_END_Y, 0.0],
            ("TOP_END_X", "TOP_END_Y"),
        ),
        "mirror_symmetric": (
            True,
            (("draw_ch_rocker_arm_tl_outline_template", "build"),),
        ),
    },
    precision={
        "height_above_pivot": _PRECISION["TopAbovePivot"],
        "radius": _PRECISION["TopRadius"],
        "station": _PRECISION["TopRodX"],
    },
)

requirement(
    "bottom_edge",
    kind="profile",
    faces=(CylinderFace(2.0 * part_spec.R_BOTTOM),),
    requirements=("depth", "radius", "station", "surface_profile"),
    fields={
        # The bottom apex's depth below the pivot, on the mirror line.
        "depth": (
            limits(
                part_spec.BOTTOM_BELOW_PIVOT,
                _PRECISION["BottomBelowPivot"],
                part_spec.LOW_POINT_BAND,
            ),
            (
                "BOTTOM_BELOW_PIVOT",
                "LOW_POINT_BAND",
                ("ch_rocker_arm_spec", "TOP_EDGE_BAND"),
            ),
        ),
        "height_from": (
            "pivot_hole",
            (("draw_ch_rocker_arm_tl_outline_template", "build"),),
        ),
        "radius": (part_spec.R_BOTTOM, ("R_BOTTOM", "BASIC_DIMENSIONS")),
        "dimension_type": ("basic", ("BASIC_DIMENSIONS",)),
        # Material added on the bottom edge moves it away from the centre.
        **_profile_zone({"radius": "increases"}),
        "radius_nominal": (part_spec.R_BOTTOM, ("R_BOTTOM",)),
        "arc_centre": ([0.0, part_spec.CENTER_Y, 0.0], ("CENTER_Y",)),
        "station": (
            limits(part_spec.BOT_END_X, _PRECISION["BottomRodX"]),
            ("BOT_END_X", "END_PLACES"),
        ),
        "station_nominal": (part_spec.BOT_END_X, ("BOT_END_X",)),
        "bottom_end": (
            [part_spec.BOT_END_X, part_spec.BOT_END_Y, 0.0],
            ("BOT_END_X", "BOT_END_Y"),
        ),
        "mirror_symmetric": (
            True,
            (("draw_ch_rocker_arm_tl_outline_template", "build"),),
        ),
    },
    precision={
        "depth": _PRECISION["BottomBelowPivot"],
        "radius": _PRECISION["BottomRadius"],
        "station": _PRECISION["BottomRodX"],
    },
)

requirement(
    "pivot_hole",
    kind="hole",
    faces=(CylinderFace(part_spec.PIVOT_HOLE_DIA),),
    requirements=("dia", "thru"),
    fields={
        "at": ([0.0, 0.0, 0.0], ("__frame__",)),
        "datum": (PIVOT_DATUM, ("PIVOT_DATUM",)),
        "axis": (_Z, ("__frame__",)),
        "dia": (
            limits(
                part_spec.PIVOT_HOLE_DIA,
                _PRECISION["PivotDia"],
                part_spec.PIVOT_HOLE_BAND,
            ),
            ("PIVOT_HOLE_DIA", "PIVOT_HOLE_BAND", "PIN_GAUGE_MAX"),
        ),
        "dia_nominal": (part_spec.PIVOT_HOLE_DIA, ("PIVOT_HOLE_DIA",)),
        "thru": (True, (("draw_ch_rocker_arm_tl_outline_template", "build"),)),
        "process": ("ream", ("PIVOT_CALLOUT",)),
    },
    precision={"dia": _PRECISION["PivotDia"]},
)

# The radial slot that clocks the template on the rocker's rod-pin hole: its
# outboard round end names it (the inboard end shares its diameter, a quarter
# width outboard of the end's centre is inside this end alone). Its station
# is BASIC (the rocker's datum C) and ``end`` is that outboard end's centre,
# on the radial from the pivot; its width is a matched fit on the pin, its
# length the end-centre run.
_ROD_SLOT_OUTER = part_spec.rod_slot_points()[4]
_ROD_SLOT_INNER = part_spec.rod_slot_points()[5]
requirement(
    "rod_slot",
    kind="slot",
    faces=(
        CylinderFace(
            part_spec.ROD_SLOT_WIDTH,
            contains_x_mm=_ROD_SLOT_OUTER[0] + part_spec.ROD_SLOT_WIDTH / 4.0,
        ),
    ),
    requirements=("note", "length", "thru"),
    fields={
        "at": (
            [part_spec.ROD_SLOT_X, part_spec.ROD_SLOT_Y, 0.0],
            ("ROD_SLOT_X", "ROD_SLOT_Y"),
        ),
        "axis": (_Z, ("__frame__",)),
        "datum": (ROD_SLOT_DATUM, ("ROD_SLOT_DATUM",)),
        "end": (
            [_ROD_SLOT_OUTER[0], _ROD_SLOT_OUTER[1], 0.0],
            ("ROD_SLOT_AXIS", "ROD_SLOT_FLAT"),
        ),
        "dimension_type": ("basic", ("BASIC_DIMENSIONS",)),
        "width_nominal": (part_spec.ROD_SLOT_WIDTH, ("ROD_SLOT_WIDTH",)),
        "length": (
            limits(part_spec.ROD_SLOT_FLAT, _PRECISION["RodSlotFlat"]),
            ("ROD_SLOT_FLAT", "ROD_SLOT_PLACES"),
        ),
        "length_nominal": (part_spec.ROD_SLOT_FLAT, ("ROD_SLOT_FLAT",)),
        "note": (
            " ".join(part_spec.ROD_SLOT_CALLOUT.splitlines()),
            ("ROD_SLOT_CALLOUT",),
        ),
        "thru": (True, (("draw_ch_rocker_arm_tl_outline_template", "build"),)),
    },
    precision={"length": _PRECISION["RodSlotFlat"]},
)

for _side, _sign in (("rod", 1.0), ("tail", -1.0)):
    # A radial land: its plane holds the arcs' centre, its outward normal is
    # the top arc's tangent at that end.
    requirement(
        f"{_side}_tip_land",
        kind="face",
        faces=(
            PlanarFace(
                (
                    _sign * math.cos(part_spec.ALPHA_TOP),
                    math.sin(part_spec.ALPHA_TOP),
                    0.0,
                ),
                part_spec.CENTER_Y * math.sin(part_spec.ALPHA_TOP),
            ),
        ),
        requirements=("length", "surface_profile"),
        fields={
            "length": (
                limits(part_spec.TIP_FACE, _PRECISION["RodTipLen"]),
                ("TIP_FACE", "END_PLACES"),
            ),
            "length_nominal": (part_spec.TIP_FACE, ("TIP_FACE",)),
            "top_edge_feature": ("top_edge", ("ALPHA_TOP", "CENTER_Y")),
            "end": (
                [_sign * part_spec.TIP_X, part_spec.TIP_Y, 0.0],
                ("TIP_X", "TIP_Y"),
            ),
            # The land's length is toleranced: the zone governs no BASIC here.
            **_profile_zone({}),
        },
        precision={"length": _PRECISION["RodTipLen"]},
    )

for _name, _normal, _offset in (
    ("arm_face", (0.0, 0.0, -1.0), 0.0),
    ("top_face", (0.0, 0.0, 1.0), part_spec.THICK),
):
    requirement(
        _name,
        kind="face",
        faces=(PlanarFace(_normal, _offset),),
        requirements=("thickness",),
        fields={
            "normal": (list(_normal), ("__frame__",)),
            "plane": ({"frame": "model", "axis": "z", "value": _offset}, ("THICK",)),
            "thickness": (
                limits(part_spec.THICK, _PRECISION["Thick"]),
                ("THICK", "THICK_PLACES"),
            ),
            "thickness_nominal": (part_spec.THICK, ("THICK",)),
        },
        precision={"thickness": _PRECISION["Thick"]},
    )


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open outline-template source", await adapter.open_model(str(SOURCE)))
    required = (
        "Number",
        "Material Specification",
        "Finish",
        "Quantity",
        "Manufacturing Notes",
        "Isometric View Note",
    )
    read_required_properties(
        adapter.currentModel, ("Revision", "Title", *required), required=required
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Rocker Arm Outline Template Drawing",
            1: "Harmonic Analyzer shop gauge drawing",
            2: "Harmonic Analyzer Project",
            3: "rocker arm layout and profile template; annealed O1; MHA-CH-006-TL-13",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=VIEW_SCALE)
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=VIEW_SCALE)
    # finalize_drawing shades the pictorial isometric with edges.
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (front, right, iso):
        set_hidden_lines_removed(adapter, view)

    annotations = [
        *curate_view_dimensions(
            adapter,
            front,
            keep=FRONT_KEEP,
            view_label="face view",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
        *curate_view_dimensions(
            adapter,
            right,
            keep=RIGHT_KEEP,
            view_label="edge view",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
    ]
    # The detail is a standalone 5:1 *Front view, dimensioned uncropped and
    # cropped after: the native detail (CreateDetailViewAt4) imported
    # RodSlotWidth but not RodSlotFlat (farm leaf edd99d0f at 5dea45dfb), the
    # cropped-view loss draw_dt_pinion_spring's _placed_kink_view records.
    detail = _placed_rod_slot_view(adapter)
    set_hidden_lines_removed(adapter, detail)
    annotations += _dimension_then_crop_rod_slot_view(adapter, detail)
    set_dimension_callouts(adapter, annotations, CALLOUTS_BELOW)
    set_dimension_callouts(adapter, annotations, CALLOUTS_ABOVE, location="above")
    for name in sorted(REFERENCE_DIMENSIONS):
        matches = [a for a in annotations if dimension_name(adapter, a) == name]
        if len(matches) != 1:
            raise RuntimeError(f"expected one outline-template {name} on the sheet")
        set_reference_dimension(adapter, matches[0], label=f"outline template {name}")
    _radius_leaders_to_arc(adapter, annotations)
    # Places (and so each dimension's tolerance) are authored on the part; the
    # sheet only proves the import kept them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add the center mark to the template pivot hole")
    # One mark on each of the slot's round ends.
    if not auto_center_marks(adapter, detail, holes=False, slots=True, size=0.0025):
        raise RuntimeError("failed to add the center marks to the template rod slot")
    # The mark and the labels go on once every import is done, so nothing of
    # the face view's own sketch is near its import.
    mark = _mark_rod_slot_on_front(adapter, front)
    _label_rod_slot_detail(adapter, detail, front, mark)
    _add_datums(adapter, front, detail)
    _add_outline_profile(adapter, front)
    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Rocker Arm Outline Template Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
    )


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

    The sheet points go through the view sketch's ModelToSketchTransform.
    Without ``add_to_db`` the circle is left SELECTED, which Crop2 consumes.
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


_ROD_SLOT_CENTRE_M = (part_spec.ROD_SLOT_X / 1000.0, part_spec.ROD_SLOT_Y / 1000.0, 0.0)


def _placed_rod_slot_view(adapter: Any) -> Any:
    """Detail A, uncropped: a standalone 5:1 *Front model view, moved so the
    slot's centre lands on DETAIL_CENTER (checked to DETAIL_POSITION_TOL_M)."""
    draw = adapter.currentModel
    view = _early_bound(
        place_view(adapter, str(SOURCE), "*Front", *DETAIL_CENTER, scale=DETAIL_SCALE),
        "IView",
    )
    ratio = tuple(float(value) for value in view.ScaleRatio)
    if ratio != tuple(float(value) for value in DETAIL_SCALE):
        raise RuntimeError(
            f"rod slot detail scale {ratio!r}, expected {DETAIL_SCALE!r}"
        )
    center = model_point_in_view(
        adapter, view, _ROD_SLOT_CENTRE_M, label="rod slot detail centre"
    )
    position = tuple(float(value) for value in view.Position)
    target = [position[axis] + DETAIL_CENTER[axis] - center[axis] for axis in range(2)]
    if not view.SetViewPosition(double_array(target), False):
        raise RuntimeError("failed to move the rod slot detail onto its sheet position")
    draw.EditRebuild3()
    center = model_point_in_view(
        adapter, view, _ROD_SLOT_CENTRE_M, label="rod slot detail centre"
    )
    if math.dist(center, DETAIL_CENTER) > DETAIL_POSITION_TOL_M:
        raise RuntimeError(f"rod slot centre sits at {center!r}, not {DETAIL_CENTER!r}")
    return view


def _crop_rod_slot_view(adapter: Any, view: Any) -> None:
    """Crop detail D to its 5:1 circle round DETAIL_CENTER: the circle is
    sketched in the view's own sketch and Crop2 consumes it while selected.
    Crop status, IsCropped, the outline and its style are read back."""
    draw = adapter.currentModel
    view = _early_bound(view, "IView")
    uncropped = tuple(float(value) for value in view.GetOutline())
    name = _activate_view(adapter, view, label="rod slot detail")
    _sketch_circle(
        adapter, view, DETAIL_CENTER, DETAIL_CROP_RADIUS, label="rod-slot-detail crop"
    )
    status = int(view.Crop2(False, False, 1))
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    view.UpdateViewDisplayGeometry()
    cropped = bool(view.IsCropped())
    outline = tuple(float(value) for value in view.GetOutline())
    _telemetry.info(
        f"outline-template: rod slot detail {name!r}, Crop2 status {status}, "
        f"IsCropped {cropped}, outline "
        f"{tuple(round(value * 1000, 1) for value in outline)} mm",
        crop_status=status,
        cropped=cropped,
    )
    if status != CROP_NO_ERROR or not cropped:
        raise RuntimeError(
            f"rod slot detail is not cropped: Crop2 status {status}, IsCropped {cropped}"
        )
    # Uncropped, the 5:1 view spans the whole 292.5 mm plate (~1.46 m of
    # sheet), the crop 30 mm, so a crop that took at least halves the width.
    if (
        len(outline) != 4
        or len(uncropped) != 4
        or outline[2] - outline[0] > (uncropped[2] - uncropped[0]) / 2.0
    ):
        raise RuntimeError(
            f"rod-slot-detail crop did not take: outline {outline!r}, before {uncropped!r}"
        )
    boundary = (bool(view.CropViewJaggedOutline), bool(view.CropViewNoOutline))
    if boundary != (False, False):
        raise RuntimeError(
            "rod slot detail's crop boundary is not its plain circle: jagged, "
            f"no-outline {boundary!r}"
        )


def _view_dimension_names(adapter: Any, view: Any) -> list[str]:
    """The model-dimension names ``view`` holds, sorted."""
    return sorted(
        name
        for name in (
            dimension_name(adapter, _early_bound(annotation, "IAnnotation"))
            for annotation in (_early_bound(view, "IView").GetAnnotations() or ())
        )
        if name
    )


def _dimension_then_crop_rod_slot_view(adapter: Any, detail: Any) -> list[Any]:
    """Import and curate detail D's pair while it is uncropped, then crop it;
    either of the pair missing after the crop raises."""
    annotations = curate_view_dimensions(
        adapter,
        detail,
        keep=DETAIL_KEEP,
        view_label="rod slot detail",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    before = _view_dimension_names(adapter, detail)
    _crop_rod_slot_view(adapter, detail)
    after = _view_dimension_names(adapter, detail)
    lost = sorted(set(DETAIL_KEEP) - set(after))
    _telemetry.event(
        "rod_slot_detail.crop",
        dimensions_before=",".join(before),
        dimensions_after=",".join(after),
        lost=",".join(lost),
    )
    if lost:
        raise RuntimeError(
            f"rod slot detail lost {lost} to its crop; before {before}, after {after}"
        )
    return annotations


def _mark_rod_slot_on_front(adapter: Any, front: Any) -> tuple[float, float]:
    """Circle detail D's region on the face view in the outline's black;
    returns its sheet centre."""
    _activate_view(adapter, front, label="face view")
    center = model_point_in_view(
        adapter, front, _ROD_SLOT_CENTRE_M, label="rod slot mark"
    )
    circle = _sketch_circle(
        adapter,
        front,
        center,
        DETAIL_RADIUS_MM * VIEW_SCALE[0] / VIEW_SCALE[1] / 1000.0,
        label="rod-slot-detail mark",
        add_to_db=True,
    )
    segment = _early_bound(circle, "ISketchSegment")
    segment.Color = 0  # COLORREF black, not the under-defined sketch blue.
    if int(segment.Color) != 0:
        raise RuntimeError("rod-slot-detail mark circle colour did not persist")
    adapter.currentModel.ClearSelection2(True)
    adapter.currentModel.EditRebuild3()
    return center


def _plain_text(text: str) -> str:
    """A note's words with its line breaks and spacing folded to single spaces."""
    return " ".join(str(text).split())


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
) -> None:
    """Insert a note owned by ``view``, centred on ``center_x`` by its rendered
    extent; ``top`` pins its top edge, ``center_y`` its middle.  A note that
    does not centre, or lands in another view, raises."""
    _activate_view(adapter, view, label=label)
    y = top if top is not None else center_y
    note = add_note(adapter, text, center_x, y)
    if note is None:
        raise RuntimeError(f"failed to add the {label} note")
    note = _early_bound(note, "INote")
    annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
    box = _note_box(note, label=label)
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
    if max(abs(error_x), abs(error_y)) > NOTE_CENTRING_TOL_M:
        raise RuntimeError(
            f"{label} note did not centre: off by ({error_x * 1000:.2f}, "
            f"{error_y * 1000:.2f}) mm"
        )
    first_line = _plain_text(text.split("\n")[0])
    texts = [
        _plain_text(_early_bound(found, "INote").GetText() or "")
        for found in (_early_bound(view, "IView").GetNotes() or ())
    ]
    if sum(found.startswith(first_line) for found in texts) != 1:
        raise RuntimeError(
            f"{label} note did not land in its view: its notes are {texts!r}"
        )


def _label_rod_slot_detail(
    adapter: Any, detail: Any, front: Any, mark: tuple[float, float]
) -> None:
    """Label detail D beside its crop circle and letter its mark on the face
    view, with the sheet scale pinned first (a 5:1 view must not rescale it)."""
    drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
    sheet = _early_bound(drawing.GetCurrentSheet(), "ISheet")
    if not sheet.SetScale(*SHEET_SCALE, False, False):
        raise RuntimeError(
            "failed to pin sheet scale before labelling the rod slot detail"
        )
    _centred_view_note(
        adapter,
        detail,
        DETAIL_LABEL_TEXT,
        center_x=DETAIL_LABEL_XY[0],
        top=DETAIL_LABEL_XY[1],
        label="rod-slot-detail label",
    )
    _centred_view_note(
        adapter,
        front,
        DETAIL_LETTER,
        center_x=mark[0] + PARENT_LETTER_OFFSET[0],
        center_y=mark[1] + PARENT_LETTER_OFFSET[1],
        label="rod-slot-detail letter",
    )


def _rim_point(
    centre: tuple[float, float], axis: tuple[float, float], radius: float, deg: float
) -> tuple[float, float, float]:
    """Model point (m) on a round rim of ``radius`` (mm) about ``centre`` (mm),
    ``deg`` from ``axis`` toward its left-hand normal, on the face laid on the arm."""
    a = math.radians(deg)
    normal = (-axis[1], axis[0])
    return (
        (centre[0] + radius * (math.cos(a) * axis[0] + math.sin(a) * normal[0]))
        / 1000.0,
        (centre[1] + radius * (math.cos(a) * axis[1] + math.sin(a) * normal[1]))
        / 1000.0,
        0.0,
    )


def _add_datums(adapter: Any, front: Any, detail: Any) -> None:
    """Datum A on the pivot hole (face view) and datum C on the rod slot (its
    5:1 detail), each picked on its own rim by sheet point (an edge-object
    tag ignores SetPosition2)."""
    pivot = model_point_in_view(adapter, front, (0.0, 0.0, 0.0), label="datum A centre")
    pick = model_point_in_view(
        adapter,
        front,
        _rim_point(
            (0.0, 0.0), (1.0, 0.0), part_spec.PIVOT_HOLE_DIA / 2.0, PIVOT_DATUM_PICK_DEG
        ),
        label="datum A rim",
    )
    add_datum_feature(
        adapter,
        front,
        edge_xy=pick,
        symbol_xy=(pivot[0] + PIVOT_DATUM_OFFSET[0], pivot[1] + PIVOT_DATUM_OFFSET[1]),
        datum=PIVOT_DATUM,
        label="pivot hole datum feature",
        shoulder=True,
    )
    slot = model_point_in_view(
        adapter, detail, _ROD_SLOT_CENTRE_M, label="datum C centre"
    )
    pick = model_point_in_view(
        adapter,
        detail,
        _rim_point(
            _ROD_SLOT_INNER,
            part_spec.ROD_SLOT_AXIS,
            part_spec.ROD_SLOT_WIDTH / 2.0,
            ROD_SLOT_DATUM_PICK_DEG,
        ),
        label="datum C rim",
    )
    add_datum_feature(
        adapter,
        detail,
        edge_xy=pick,
        symbol_xy=(
            slot[0] + ROD_SLOT_DATUM_OFFSET[0],
            slot[1] + ROD_SLOT_DATUM_OFFSET[1],
        ),
        datum=ROD_SLOT_DATUM,
        label="rod slot datum feature",
        shoulder=True,
    )


def _add_outline_profile(adapter: Any, front: Any) -> Any:
    """One native surface-profile frame, all around the outline, to A|C."""
    x = PROFILE_LANDING_X_MM
    landing = model_point_in_view(
        adapter,
        front,
        (
            x / 1000.0,
            (part_spec.CENTER_Y - math.sqrt(part_spec.R_TOP**2 - x**2)) / 1000.0,
            0.0,
        ),
        label="outline profile landing",
    )
    return add_feature_control_frame(
        adapter,
        front,
        edge_entity=visible_circle_edge(adapter, front, 2.0 * part_spec.R_TOP),
        leader_attach_xy=landing,
        frame_xy=PROFILE_FRAME_XY,
        characteristic="profile_surface",
        tolerance=OUTLINE_PROFILE_TEXT,
        datums=OUTLINE_PROFILE_DATUMS,
        all_around=True,
        label="outline surface profile",
    )


def _radius_leaders_to_arc(adapter: Any, annotations: list[Any]) -> None:
    """The rocker's exterior-radius dress: text-to-arc leaders only."""
    remaining = set(EXTERIOR_RADII)
    for annotation in annotations:
        name = dimension_name(adapter, annotation)
        if name not in remaining:
            continue
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        display.ShortenedRadius = False
        display.ArcExtensionLineOrOppositeSide = False
        display.ArrowSide = 1  # swDimArrowsOutside
        display.SolidLeader = False
        if (
            bool(display.ShortenedRadius)
            or bool(display.ArcExtensionLineOrOppositeSide)
            or int(display.ArrowSide) != 1
            or bool(display.SolidLeader)
        ):
            raise RuntimeError(f"{name} retained its centre-directed radius leader")
        remaining.remove(name)
    if remaining:
        raise RuntimeError(f"exterior radii missing: {sorted(remaining)}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
