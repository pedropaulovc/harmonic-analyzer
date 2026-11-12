r"""Create the cone tip gear drawing (MHA-DT-37): T006 with its spigot and pivot.

Sheet 1 draws the part as it sits between the lathe's centres (rule 11): the
side view runs pivot (left) to spigot (right) with every diameter above it and
every length below it, each length from the leaves face it is turned from,
and the spigot-to-pivot overall as a reference. The front view carries the
leaves' inspection sizes the cone family prints on its T006 sheet: the
circular tooth thickness on the +X tooth, its text on its own shelf, and the
root envelope's limits off the near rim; its DETAIL B boundary rings the
12 o'clock tooth space that sheet 2 plots. A shaded isometric gives the
picture. Numbered notes name each mate once: note 1 the pivot's matched press
fit in MHA-DT-38, note 2 the teeth's mesh with MHA-DT-12, and note 3 the
centres. The pivot runs in MHA-DT-39, so it alone carries a roughness symbol.

Sheet 2 defines the T006 tooth space point by point beside its outline (the
custom DT6-FORM1 tool is ground to it); the exact equations stay in the
model's "Cutter Profile" property. Every band is model-owned.

Run with SolidWorks open::

    uv run python cad\scripts\draw_dt_cone_tip_gear.py dt-cone-tip-gear
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path
from typing import Any

from solidworks_mcp.adapters import sw_type_info as _sw_type_info
from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.pywin32_adapter import null_callout
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    dimension_name,
    place_view,
)

import _cone_gear_sheet as cone_sheet
import _drawing_hidden_sketches as hidden_sketches
import _telemetry
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
from _drawing_dimensions import (
    assert_imported_precision,
    set_dimension_callouts,
    set_reference_dimension,
)
from _drawing_edge_dimensions import add_edge_dimension
from _drawing_edges import visible_view_entities
from _drawing_finish import add_surface_finish
from _drawing_layout_collect import check_drawing_layout
from _drawing_leader_notes import add_leader_note
from _drawing_leaders import set_near_side_diameter
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_sheets import create_blank_drawing_sheets
from _drawing_view_display import set_hidden_lines_removed
from _fit_deviations import deviations
from _machinist_review_mode import MachinistReviewMode
from _part_properties import part_drawing_unit
from _paths import CAD_ROOT
from _pdf_ink import read_pdf_ink
from _session import run_build
from _surface_finish import surface_finish_by_key
from dt_cone_gear_spec import (
    FORM_PLACES,
    custom_six_form_points_mm,
    custom_six_gap_half_angle_rad,
)
from dt_cone_tip_gear_notes import (
    CALLOUTS_ABOVE,
    CUTTER_DETAIL_SHEET,
    DIMENSION_CALLOUTS,
    SHEET_NAMES,
    TEETH_NOTE_NUMBER,
)
from dt_cone_tip_gear_spec import (
    BLANK_DIA_BAND,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    DRAWING_REFERENCE_PRECISION,
    FACE_WIDTH,
    FLOOR_DEVIATIONS_MM,
    FLOOR_LIMITS_MM,
    OUTSIDE_DIA,
    OVERALL_LENGTH_MM,
    PART_NUMBER,
    PIVOT_END_Z_MM,
    PIVOT_LENGTH_MM,
    PROFILE,
    SPIGOT_END_Z_MM,
    STEM_DIA_MM,
    SURFACE_FINISHES,
    TEETH,
    TOOTH_THICKNESS,
    TOOTH_THICKNESS_BAND,
    inch_text,
)

# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE


SPEC = DRAWINGS_BY_NAME["dt_cone_tip_gear"]
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

GEAR_SHEET = SHEET_NAMES[0]
# 6:1 keeps the T006 tooth, its thickness witness and root envelope legible
# (the family's T012 sheet's ratio) and the 1.30 in part inside the border.
VIEW_SCALE = (6.0, 1.0)
RATIO = VIEW_SCALE[0] / VIEW_SCALE[1]
SHEET_SCALES = {GEAR_SHEET: VIEW_SCALE, CUTTER_DETAIL_SHEET: (1.0, 1.0)}
SHEET_SCALE = SHEET_SCALES[GEAR_SHEET]
# The pictorial at a third of the sheet's ratio sits in the top-right field.
ISO_SCALE = (2.0, 1.0)

# Both orthographic views stand on one axis height (projection-aligned):
# the gear axis lands on FRONT_CENTER, the model origin (the leaves' south
# face on the axis) on SIDE_ORIGIN (``_place_origin``).
AXIS_Y = 0.135
FRONT_CENTER = (0.075, AXIS_Y)
# x 0.2705: the .76 spigot (#1038) carries its centred bond callout 3.8 mm
# further right than the .71 one did; at 0.2745 the callout's second line
# ended on the inner border (farm run 20261111T234611671Z).
SIDE_ORIGIN = (0.2705, AXIS_Y)
ISO_CENTER = (0.385, 0.222)
# Top-aligned: the numbered notes top-left, Gear Data right of them.
NUMBERED_NOTES_POS = (0.015, 0.263)
GEAR_DATA_POS = (0.215, 0.263)
NOTE_HEIGHT = 0.0025
# 14 rows at ~3.51 mm a row (the family's measured note pitch).
NOTE_LINE_PITCH = 0.00351


def side_x(z_mm: float) -> float:
    """Sheet x of model station ``z_mm`` on the side view: the *Right view
    looks along -X, so model +Z (north, the pivot) runs to the LEFT."""
    return SIDE_ORIGIN[0] - z_mm * RATIO / 1000.0


def sheet_mm(value_mm: float) -> float:
    """A model length on the sheet, metres."""
    return value_mm * RATIO / 1000.0


HALF_OD = sheet_mm(OUTSIDE_DIA / 2.0)
STEM_HALF = sheet_mm(STEM_DIA_MM / 2.0)
PIVOT_END_X = side_x(PIVOT_END_Z_MM)
LEAVES_NORTH_X = side_x(FACE_WIDTH)
LEAVES_SOUTH_X = side_x(0.0)
SPIGOT_END_X = side_x(SPIGOT_END_Z_MM)

# --- Side view: diameters above, lengths below ---------------------------------
# Each diameter's dimension line stands inside the feature it measures, its
# text above the part, in two tiers.
# The spigot's block and the tip's share a tier (they never overlap in x);
# the pivot's two callout lines reach over the leaves, so it stands above,
# under Gear Data.  The spigot's block hangs right of its dimension line and
# its first line names the compound (44 characters, ~114 mm), so the line
# stands a quarter of the spigot from the leaves, which keeps the block's
# end ~8 mm inside the border.
BLANK_DIA_TEXT_Y = AXIS_Y + HALF_OD + 0.016
SPIGOT_DIA_TEXT_Y = BLANK_DIA_TEXT_Y
PIVOT_DIA_TEXT_Y = AXIS_Y + HALF_OD + 0.040
LENGTH_TEXT_Y = AXIS_Y - HALF_OD - 0.014
OVERALL_TEXT_Y = LENGTH_TEXT_Y - 0.018
SIDE_KEEP = {
    "PivotDia": ((PIVOT_END_X + LEAVES_NORTH_X) / 2.0, PIVOT_DIA_TEXT_Y),
    "BlankDia": ((LEAVES_NORTH_X + LEAVES_SOUTH_X) / 2.0, BLANK_DIA_TEXT_Y),
    "SpigotDia": (
        LEAVES_SOUTH_X + (SPIGOT_END_X - LEAVES_SOUTH_X) / 4.0,
        SPIGOT_DIA_TEXT_Y,
    ),
    "PivotLength": ((PIVOT_END_X + LEAVES_NORTH_X) / 2.0, LENGTH_TEXT_Y),
    "FaceWidth": ((LEAVES_NORTH_X + LEAVES_SOUTH_X) / 2.0, LENGTH_TEXT_Y),
    "SpigotLength": ((LEAVES_SOUTH_X + SPIGOT_END_X) / 2.0, LENGTH_TEXT_Y),
}
OVERALL_TEXT_XY = ((PIVOT_END_X + SPIGOT_END_X) / 2.0, OVERALL_TEXT_Y)
# The pivot's roughness symbol stands up-left of its end, its leader on the
# pivot's top flank PIVOT_FINISH_INSET in from the end (the running zone in
# MHA-DT-39), clear of the pivot's callout block above.
PIVOT_FINISH_XY = (PIVOT_END_X - 0.010, AXIS_Y + HALF_OD + 0.010)
PIVOT_FINISH_INSET = sheet_mm(PIVOT_LENGTH_MM / 4.0)
# A centreline runs a short way past the part it marks.
AXIS_OVERRUN = 0.003

# --- Front view: the family's T006 inspection layout at this ratio --------------
# The root-envelope stack stands right of the tip circle, above the thickness
# witness and the thickness text's shelf (_cone_gear_sheet, the cone-gear
# family's layout).
CENTER_MARK_SINGLE = 2  # swCenterMarkStyle_e.swCenterMark_Single
_TOL_LIMIT = 3  # swTolType_e.swTolLIMIT


def floor_dia_y() -> float:
    """Anchor y of the root-envelope stack (``cone_sheet.floor_dia_y``)."""
    return cone_sheet.floor_dia_y(
        FRONT_CENTER[1], HALF_OD, sheet_mm(TOOTH_THICKNESS / 2.0)
    )


FRONT_KEEP = {
    "FloorDia": (FRONT_CENTER[0] + HALF_OD + cone_sheet.FLOOR_DIA_GAP_X, floor_dia_y()),
    # The vertical thickness dimension on the +X tooth; its text then leaves
    # the line for its own shelf (``cone_sheet.shelve_tooth_thickness``).
    "ToothThickness": (
        FRONT_CENTER[0] + HALF_OD + 0.014,
        FRONT_CENTER[1] - HALF_OD - 0.0225,
    ),
}


def tooth_thickness_shelf() -> tuple[float, float]:
    """Where the thickness text's shelf starts
    (``cone_sheet.tooth_thickness_shelf``)."""
    return cone_sheet.tooth_thickness_shelf(
        FRONT_KEEP["ToothThickness"][0], floor_dia_y()
    )


# DETAIL B is sheet 2's plot of the T006 tooth space; its boundary rings the
# 12 o'clock space on the front view (a gap: T006 has teeth every 60 deg from
# +X), upright as the plot draws it, its letter up and right.
FORM_DETAIL_LETTER = "B"
FORM_DETAIL_CENTRE_MM = 1.80
FORM_DETAIL_MARGIN_MM = 0.10
FORM_LETTER_ANGLE_DEG = 45.0


def form_detail() -> cone_sheet.FrontDetail:
    if not math.isclose((90.0 * TEETH / 360.0) % 1.0, 0.5):
        raise AssertionError("DETAIL B's 12 o'clock station is not a tooth space")
    root = PROFILE.template.root_radius_mm
    _radius, corner_x, corner_y = custom_six_form_points_mm()[-1]
    reach = math.hypot(corner_x, corner_y + root - FORM_DETAIL_CENTRE_MM)
    return cone_sheet.FrontDetail(
        FORM_DETAIL_LETTER,
        (0.0, FORM_DETAIL_CENTRE_MM),
        reach + FORM_DETAIL_MARGIN_MM,
        FORM_LETTER_ANGLE_DEG,
        cone_sheet.DETAIL_LETTER_REACH,
    )


def front_detail_on_sheet(
    detail: cone_sheet.FrontDetail,
) -> tuple[tuple[float, float], float]:
    """Nominal sheet centre and radius of ``detail``'s boundary."""
    return (
        (
            FRONT_CENTER[0] + sheet_mm(detail.centre_mm[0]),
            FRONT_CENTER[1] + sheet_mm(detail.centre_mm[1]),
        ),
        sheet_mm(detail.radius_mm),
    )


def sheet_dimension_names() -> set[str]:
    return set().union(*DRAWING_DIMENSIONS.values())


# --- Sheet 2: the T006 tooth space ----------------------------------------------
# A one-line title, the points in a native general table (POINT | R | X | Y)
# under it, two note lines under the table, and the plot (DETAIL B) beside it
# at FORM_PLOT_SCALE with P1 (X0 Y0) on the CL at FORM_PLOT_ORIGIN.
FORM_TEXT_HEIGHT = 0.0025
FORM_TITLE_POS = (0.015, 0.263)
FORM_TABLE_POS = (0.015, 0.257)
FORM_TABLE_HEADINGS = ("POINT", "R", "X", "Y")
FORM_TABLE_COLUMN_WIDTHS = (0.013, 0.015, 0.015, 0.015)
FORM_TABLE_ROW_HEIGHT = 0.0045
FORM_NOTES_GAP = 0.004
_TABLE_ANCHOR_TOP_LEFT = 1  # swBOMConfigurationAnchor_TopLeft
_TABLE_HEADER_TOP = 1  # swTableHeaderPosition_e.swTableHeader_Top
_TABLE_SIZE_CAN_CHANGE = 0  # swTableRowColSizeChangeBehavior_e
# The sheet's hidden title-block source view: clear of the table, inside the
# border.
CUTTER_SOURCE_VIEW_CENTER = (0.325, 0.155)
FORM_PLOT_SCALE = 75.0
FORM_PLOT_ORIGIN = (0.280, 0.140)
FORM_PLOT_CL_OVERRUN = 0.008
FORM_PLOT_X_AXIS_LENGTH = 0.085
FORM_PLOT_STATION_REACH_MM = {"junction": 1.10, "blank": 1.25}
FORM_PLOT_INVOLUTE_SAMPLES = 16
FORM_PLOT_TITLE_POS = (0.205, 0.240)
FORM_PLOT_STATION_LABEL_OFFSET = (-0.019, 0.002)
# Each point tag's text top-left from its landing; neighbours alternate sides
# (round 7 of the cone family's fan-out measured the overlaps).
FORM_TAG_TEXT_OFFSETS = {
    1: (0.004, -0.009),
    2: (0.002, -0.0037),
    12: (-0.011, 0.005),
    13: (0.0047, -0.0014),
    14: (-0.012, 0.007),
    15: (-0.0085, 0.0069),
    16: (0.0048, -0.0008),
    17: (-0.011, 0.0075),
}
FORM_ZONE_TEXT_OFFSETS = {
    "root": (-0.0466, -0.0049),
    "straight": (0.0123, 0.0007),
    "involute": (0.011, -0.007),
}


def form_plot_xy(x_mm: float, y_mm: float) -> tuple[float, float]:
    """Sheet position (m) of table point (X, Y) mm on the tooth-space plot."""
    return (
        FORM_PLOT_ORIGIN[0] + x_mm * FORM_PLOT_SCALE / 1000.0,
        FORM_PLOT_ORIGIN[1] + y_mm * FORM_PLOT_SCALE / 1000.0,
    )


def form_plot_flank_mm() -> list[tuple[float, float]]:
    """One flank (+X) of the T006 space as table (X, Y), root arc end up:
    straight lines row to row up to the junction, then the involute."""
    points = custom_six_form_points_mm()
    template = PROFILE.template
    root = template.root_radius_mm
    junction = template.relief_junction_radius_mm
    blank = points[-1][0]
    flank = [(x, y) for radius, x, y in points[1:] if radius <= junction + 1e-9]
    for index in range(1, FORM_PLOT_INVOLUTE_SAMPLES + 1):
        radius = junction + (blank - junction) * index / FORM_PLOT_INVOLUTE_SAMPLES
        half = custom_six_gap_half_angle_rad(radius)
        flank.append((radius * math.sin(half), radius * math.cos(half) - root))
    return flank


def form_plot_station_mm(radius_mm: float, reach_mm: float) -> tuple[float, float]:
    """Table (X, Y) where the station arc of ``radius_mm`` stops, left of CL."""
    root = PROFILE.template.root_radius_mm
    return (-reach_mm, math.sqrt(radius_mm**2 - reach_mm**2) - root)


def form_plot_label() -> str:
    """Sheet 2's plot title: DETAIL B of sheet 1, at the plot's scale."""
    return (
        f"DETAIL {FORM_DETAIL_LETTER} (SHEET {SHEET_NAMES.index(GEAR_SHEET) + 1})\n"
        f"SCALE {FORM_PLOT_SCALE:g} : 1"
    )


def form_plot_labels() -> list[tuple[str, tuple[float, float]]]:
    """(text, top-left sheet position) of the plot's notes."""
    template = PROFILE.template
    blank = custom_six_form_points_mm()[-1][0]
    junction = template.relief_junction_radius_mm
    top = form_plot_xy(0.0, custom_six_form_points_mm()[-1][2])[1]
    labels = [
        (form_plot_label(), FORM_PLOT_TITLE_POS),
        ("CL", (FORM_PLOT_ORIGIN[0] - 0.003, top + FORM_PLOT_CL_OVERRUN + 0.006)),
        (
            "+X",
            (
                FORM_PLOT_ORIGIN[0] + FORM_PLOT_X_AXIS_LENGTH + 0.002,
                FORM_PLOT_ORIGIN[1] + 0.002,
            ),
        ),
    ]
    for key, radius in (("junction", junction), ("blank", blank)):
        x, y = form_plot_xy(
            *form_plot_station_mm(radius, FORM_PLOT_STATION_REACH_MM[key])
        )
        labels.append(
            (
                f"(R{inch_text(radius, 4)})",
                (
                    x + FORM_PLOT_STATION_LABEL_OFFSET[0],
                    y + FORM_PLOT_STATION_LABEL_OFFSET[1],
                ),
            )
        )
    return labels


def form_point_tags() -> list[tuple[str, tuple[float, float], tuple[float, float]]]:
    """(text, text top-left, leader landing) of each point tag on DETAIL B."""
    points = custom_six_form_points_mm()
    tags = []
    for number, (dx, dy) in FORM_TAG_TEXT_OFFSETS.items():
        _radius, x, y = points[number - 1]
        tip = form_plot_xy(x, y)
        tags.append((f"P{number}", (tip[0] + dx, tip[1] + dy), tip))
    return tags


def form_zones() -> tuple[int, int]:
    """(last root-arc point, junction point), 1-based."""
    points = custom_six_form_points_mm()
    junction = PROFILE.template.relief_junction_radius_mm
    nearest = min(
        range(len(points)), key=lambda index: abs(points[index][0] - junction)
    )
    return 2, nearest + 1


def form_zone_labels() -> list[tuple[str, tuple[float, float], tuple[float, float]]]:
    """(text, text top-left, leader landing) of DETAIL B's three zone labels."""
    template = PROFILE.template
    root = template.root_radius_mm
    points = custom_six_form_points_mm()
    root_end, straight_end = form_zones()
    _r, x2, y2 = points[root_end - 1]
    half = math.atan2(x2, y2 + root) / 2.0
    root_tip = form_plot_xy(-root * math.sin(half), root * math.cos(half) - root)
    middle = (root_end + straight_end) // 2
    (_ra, xa, ya), (_rb, xb, yb) = points[middle - 1], points[middle]
    straight_tip = form_plot_xy((xa + xb) / 2.0, (ya + yb) / 2.0)
    radius = (points[straight_end - 1][0] + points[-1][0]) / 2.0
    angle = custom_six_gap_half_angle_rad(radius)
    involute_tip = form_plot_xy(
        radius * math.sin(angle), radius * math.cos(angle) - root
    )
    zones = (
        ("root", f"ROOT ARC R{inch_text(root, FORM_PLACES)}, P1-P{root_end}", root_tip),
        ("straight", f"STRAIGHT LINES P{root_end}-P{straight_end}", straight_tip),
        (
            "involute",
            f"INVOLUTE, BASE R{inch_text(template.base_radius_mm, FORM_PLACES)}, "
            f"P{straight_end}-P{len(points)}",
            involute_tip,
        ),
    )
    labels = []
    for key, text, tip in zones:
        dx, dy = FORM_ZONE_TEXT_OFFSETS[key]
        labels.append((text, (tip[0] + dx, tip[1] + dy), tip))
    return labels


def form_table_rows() -> list[tuple[str, str, str, str]]:
    """The T006 tooth space, point by point: the heading, then P1-P17, read
    from the same profile the native cut uses. T006 cuts at T=0 on a spur
    gear, so its tooth space IS the custom cutter's edge: the shop grinds its
    own tool to this space and accepts the cut gear by sheet 1's note 2."""
    template = PROFILE.template
    if template.cutter_number is not None or template.name != CUTTER_DETAIL_SHEET:
        raise ValueError("T006 must use the specified DT6-FORM1 custom cutter")
    if PROFILE.radial_translation_mm != 0.0 or PROFILE.helix_angle_deg != 0.0:
        raise ValueError(
            "the T006 tooth space is DT6-FORM1's form only at T=0, helix 0"
        )
    return [
        FORM_TABLE_HEADINGS,
        *(
            (
                f"P{number}",
                inch_text(radius, FORM_PLACES),
                inch_text(x, FORM_PLACES),
                inch_text(y, FORM_PLACES),
            )
            for number, (radius, x, y) in enumerate(custom_six_form_points_mm(), 1)
        ),
    ]


def form_sheet_title() -> str:
    """The one line over the table: whose space this is, in which unit."""
    return (
        f"{PART_NUMBER} TOOTH SPACE, INCH "
        f"(CONTINUED FROM SHEET {SHEET_NAMES.index(GEAR_SHEET) + 1})"
    )


def form_sheet_notes() -> str:
    """What R, X and Y are measured from, and the route by which the form is
    accepted: through the gear it cuts (sheet 1's note 2; no form band of its
    own, #2358)."""
    return "\n".join(
        (
            # The R column and the plot's station radii derive from X and Y
            # (REF); Y is a BASIC station (machinist review of PR #2557).
            "R (REF) FROM GEAR AXIS; Y BASIC, ALONG CL FROM P1; X FROM CL, EACH SIDE.",
            "ACCEPT THE FORM BY THE GEAR IT CUTS, SEE SHEET "
            f"{SHEET_NAMES.index(GEAR_SHEET) + 1} NOTE {TEETH_NOTE_NUMBER}.",
        )
    )


def form_notes_pos(table_height: float | None = None) -> tuple[float, float]:
    """Top-left of the notes under the table: under the rows as set, or as
    the seat measured them (a row grows to fit its text)."""
    if table_height is None:
        table_height = len(form_table_rows()) * FORM_TABLE_ROW_HEIGHT
    return (FORM_TABLE_POS[0], FORM_TABLE_POS[1] - table_height - FORM_NOTES_GAP)


# --- Native helpers ---------------------------------------------------------------


def _place_origin(
    adapter: Any, view: Any, target: tuple[float, float], *, label: str
) -> None:
    """Move ``view`` so the model origin lands on ``target`` (sheet m)."""
    view = _early_bound(view, "IView")
    origin = model_point_in_view(adapter, view, (0.0, 0.0, 0.0), label=label)
    position = tuple(float(value) for value in view.Position)
    moved = [position[i] + target[i] - origin[i] for i in range(2)]
    if not view.SetViewPosition(double_array(moved), False):
        raise RuntimeError(f"failed to move the {label}")
    rebuild_drawing(adapter, label=f"place {label}")
    origin = model_point_in_view(adapter, view, (0.0, 0.0, 0.0), label=label)
    if math.dist(origin, target) > 1e-4:
        raise RuntimeError(f"{label}: origin sits at {origin!r}, not {target!r}")


def _hide_tangent_edges(view: Any) -> None:
    """Drop the front view's tangent edges (a grey root circle read as a hub
    step, ENFORCE round 4 of #971), and prove they went."""
    view = _early_bound(view, "IView")
    view.SetDisplayTangentEdges2(0)  # swTangentEdgesHidden
    if int(view.GetDisplayTangentEdges2()) != 0:
        raise RuntimeError("failed to hide the front view's tangent edges")
    view.UpdateViewDisplayGeometry()


def _assert_tooth_geometry(front: Any) -> None:
    """Prove the view exposes the patterned leaves, not a smooth blank."""
    edge_count = len(visible_view_entities(front, 1, label="T006 front tooth topology"))
    minimum = 2 * TEETH + 2
    if edge_count < minimum:
        raise RuntimeError(
            f"front view exposes {edge_count} model-body edges; expected at least "
            f"{minimum} for {TEETH} teeth"
        )


def _hide_title_block_source(adapter: Any, view: Any) -> None:
    """Hide sheet 2's source view; its title block still reads it."""
    bound = _early_bound(view, "IView")
    bound.SetVisible(False, False)
    rebuild_drawing(adapter, label="hide tooth-space title-block source")
    if bool(bound.GetVisible()):
        raise RuntimeError("the tooth-space sheet's source view still reads visible")


def _mark_form_detail(adapter: Any, front: Any) -> None:
    """Draw DETAIL B's boundary on the front view (a black view-sketch
    circle) and letter it outside, both owned by the view."""
    detail = form_detail()
    label = f"front detail {detail.letter}"
    cone_sheet.activate_view(adapter, front, label=label)
    x_mm, y_mm = detail.centre_mm
    centre, rim = (
        model_point_in_view(
            adapter, front, (x / 1000.0, y_mm / 1000.0, 0.0), label=f"{label} {name}"
        )
        for x, name in ((x_mm, "centre"), (x_mm + detail.radius_mm, "rim"))
    )
    radius = math.dist(centre, rim)
    circle = cone_sheet.sketch_view_circle(
        adapter, front, centre, radius, add_to_db=True, label=f"{label} boundary"
    )
    segment = _early_bound(circle, "ISketchSegment")
    segment.Color = 0  # COLORREF black, not the under-defined sketch blue.
    if int(segment.Color) != 0:
        raise RuntimeError(f"{label} boundary colour did not persist")
    adapter.currentModel.ClearSelection2(True)
    rebuild_drawing(adapter, label=f"{label} boundary")
    letter_x, letter_y = cone_sheet.detail_letter_xy(detail, centre, radius)
    cone_sheet.centred_view_note(
        adapter,
        front,
        detail.letter,
        center_x=letter_x,
        center_y=letter_y,
        height=cone_sheet.DETAIL_LETTER_HEIGHT,
        label=f"{label} letter",
    )


def _center_mark_pivot(adapter: Any, front: Any) -> None:
    """Centre-mark the pivot's end circle on the front view (its -X point,
    picked as an edge and marked directly)."""
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    cone_sheet.activate_view(adapter, front, label="front pivot centre mark")
    pick = model_point_in_view(
        adapter,
        front,
        (-STEM_DIA_MM / 2000.0, 0.0, PIVOT_END_Z_MM / 1000.0),
        label="pivot end circle -X point",
    )
    extension = _early_bound(draw.Extension, "IModelDocExtension")
    if not extension.SelectByID2(
        "", "EDGE", pick[0], pick[1], 0.0, False, 0, null_callout(), 0
    ):
        raise RuntimeError("failed to select the pivot's end circle")
    mark = ddoc.InsertCenterMark3(CENTER_MARK_SINGLE, False, False)
    draw.ClearSelection2(True)
    if mark is None:
        raise RuntimeError("failed to centre-mark the pivot")


def _assert_sheet_bands(adapter: Any, annotations: list[Any]) -> None:
    """Prove the imported root-envelope LIMIT pair and the leaves' own blank
    and tooth-thickness bands read back off the saved part."""
    by_name = {}
    for annotation in annotations:
        by_name.setdefault(dimension_name(adapter, annotation), []).append(annotation)
    for name, kind, expected in (
        ("FloorDia", _TOL_LIMIT, FLOOR_DEVIATIONS_MM),
        ("BlankDia", None, deviations(BLANK_DIA_BAND)),
        ("ToothThickness", None, deviations(TOOTH_THICKNESS_BAND)),
    ):
        found = by_name.get(name, [])
        if len(found) != 1:
            raise RuntimeError(f"expected one {name} on the sheet, found {len(found)}")
        display = _early_bound(
            _early_bound(found[0], "IAnnotation").GetSpecificAnnotation(),
            "IDisplayDimension",
        )
        tolerance = _early_bound(
            _early_bound(display.GetDimension2(0), "IDimension").Tolerance,
            "IDimensionTolerance",
        )
        observed = (
            float(tolerance.GetMinValue()) * 1000.0,
            float(tolerance.GetMaxValue()) * 1000.0,
        )
        if kind is not None and int(tolerance.Type) != kind:
            raise RuntimeError(
                f"sheet {name} reads tolerance type {int(tolerance.Type)}"
            )
        if any(abs(o - e) > 1e-6 for o, e in zip(observed, expected)):
            raise RuntimeError(
                f"sheet {name} reads {observed} mm, expected {expected} mm"
            )
    _telemetry.success(
        f"sheet root-envelope limits {FLOOR_LIMITS_MM} mm and tooth bands"
    )


# The thickness callout's printed rows other than the value, top down.
TOOTH_THICKNESS_ROWS = (
    CALLOUTS_ABOVE["ToothThickness"],
    *DIMENSION_CALLOUTS["ToothThickness"].splitlines(),
)


def assert_tooth_thickness_text_air(pdf: Path) -> None:
    """Refuse the export when a line comes nearer the thickness callout's
    text than ``cone_sheet.TOOTH_THICKNESS_TEXT_AIR`` on sheet 1's printed ink."""
    pages = read_pdf_ink(Path(pdf))
    if len(pages) != len(SHEET_NAMES):
        raise RuntimeError(
            f"{pdf} prints {len(pages)} pages, expected {len(SHEET_NAMES)}"
        )
    air, nearest = cone_sheet.tooth_thickness_text_air(
        pages[SHEET_NAMES.index(GEAR_SHEET)], TOOTH_THICKNESS_ROWS, sheet=GEAR_SHEET
    )
    _telemetry.info(f"thickness text air {air * 1000:.2f} mm")
    if air < cone_sheet.TOOTH_THICKNESS_TEXT_AIR:
        raise RuntimeError(
            f"a line strikes the thickness text (under "
            f"{cone_sheet.TOOTH_THICKNESS_TEXT_AIR * 1000:.1f} mm of air): {nearest}"
        )


def _check_exported_pdf(phase: str) -> None:
    if phase == "after_pdf_save":
        assert_tooth_thickness_text_air(PDF)


def _end_circle(view: Any, *, station_mm: float, label: str) -> Any:
    """The one visible stem end-face circle at model z ``station_mm``."""
    matches: list[Any] = []
    for raw in visible_view_entities(view, 1, label=f"{label} edges"):
        curve = _early_bound(raw, "IEdge").GetCurve()
        if curve is None:
            continue
        curve = _early_bound(curve, "ICurve")
        if not curve.IsCircle():
            continue
        params = tuple(float(value) for value in curve.CircleParams)
        if abs(params[2] * 1000.0 - station_mm) > 1e-3:
            continue
        if abs(params[6] * 2000.0 - STEM_DIA_MM) > 1e-3:
            continue
        matches.append(raw)
    if len(matches) != 1:
        raise RuntimeError(
            f"{label}: {len(matches)} stem circles at z {station_mm:g}, expected 1"
        )
    return matches[0]


def _add_overall_reference(adapter: Any, side: Any) -> Any:
    """Spigot end to pivot end as a REFERENCE: the read-only sum of the three
    toleranced lengths, for the stock, at the spec's places."""
    spigot_end = _end_circle(side, station_mm=SPIGOT_END_Z_MM, label="spigot end")
    pivot_end = _end_circle(side, station_mm=PIVOT_END_Z_MM, label="pivot end")
    display = add_edge_dimension(
        adapter,
        side,
        p0=(0.0, 0.0),
        p1=(0.0, 0.0),
        text_xy=OVERALL_TEXT_XY,
        label="spigot-to-pivot overall",
        orientation="horizontal",
        entities=(pivot_end, spigot_end),
    )
    display = _early_bound(display, "IDisplayDimension")
    measured = abs(
        float(_early_bound(display.GetDimension2(0), "IDimension").SystemValue)
    )
    if abs(measured * 1000.0 - OVERALL_LENGTH_MM) > 1e-4:
        raise RuntimeError(
            f"spigot-to-pivot overall measured {measured * 1000.0:.4f} mm, "
            f"expected {OVERALL_LENGTH_MM:.4f}"
        )
    set_reference_dimension(adapter, display.GetAnnotation(), label="overall reference")
    display.SetPrecision3(DRAWING_REFERENCE_PRECISION, -1, -1, -1)
    if int(display.GetPrimaryPrecision2()) != DRAWING_REFERENCE_PRECISION:
        raise RuntimeError("overall reference precision did not persist")
    return display


def _add_axis(adapter: Any) -> None:
    """The side view's axis as ONE black sheet centreline, end to end."""
    drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
    drawing.EditSheet()
    manager = _early_bound(adapter.currentModel.SketchManager, "ISketchManager")
    centerline = manager.CreateCenterLine(
        PIVOT_END_X - AXIS_OVERRUN,
        AXIS_Y,
        0.0,
        SPIGOT_END_X + AXIS_OVERRUN,
        AXIS_Y,
        0.0,
    )
    if centerline is None:
        raise RuntimeError("failed to sketch the side view's axis")
    segment = _early_bound(centerline, "ISketchSegment")
    segment.Color = 0
    if int(segment.Color) != 0:
        raise RuntimeError("axis centreline colour did not persist")
    adapter.currentModel.ClearSelection2(True)
    adapter.currentModel.EditRebuild3()


def _pivot_face(view: Any) -> Any:
    """The pivot's visible cylindrical face: the stem diameter, its box inside
    the pivot's span (the spigot shares the diameter)."""
    matches = []
    for raw in visible_view_entities(view, 3, label="side view faces"):
        face = _early_bound(raw, "IFace2")
        surface = face.GetSurface()
        if surface is None:
            continue
        surface = _early_bound(surface, "ISurface")
        if not surface.IsCylinder():
            continue
        if abs(float(surface.CylinderParams[6]) * 2000.0 - STEM_DIA_MM) > 1e-3:
            continue
        box = tuple(float(value) * 1000.0 for value in face.GetBox())
        if box[2] > FACE_WIDTH - 1e-3 and box[5] < PIVOT_END_Z_MM + 1e-3:
            matches.append(face)
    if len(matches) != 1:
        raise RuntimeError(f"side view shows {len(matches)} pivot faces, expected 1")
    return matches[0]


def _insert_form_table(adapter: Any) -> Any:
    """The P1-P17 table: a native general table, top-left anchored at
    FORM_TABLE_POS, one heading row, read back cell by cell."""
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    rows = form_table_rows()
    columns = len(FORM_TABLE_HEADINGS)
    draw.ClearSelection2(True)
    raw = ddoc.InsertTableAnnotation2(
        False, *FORM_TABLE_POS, _TABLE_ANCHOR_TOP_LEFT, "", len(rows), columns
    )
    if raw is None:
        raise RuntimeError("InsertTableAnnotation2 refused the T006 point table")
    table = _sw_type_info.early_bound(raw, "ITableAnnotation")
    if not _sw_type_info.is_early_bound(table, "ITableAnnotation"):
        raise RuntimeError("ITableAnnotation early-bound wrapper is unavailable")
    shape = (int(table.RowCount), int(table.ColumnCount))
    if shape != (len(rows), columns):
        raise RuntimeError(
            f"T006 point table is {shape}, expected {(len(rows), columns)}"
        )
    if int(table.GetHeaderCount()) != 1:
        table.SetHeader(_TABLE_HEADER_TOP, 1)
        if int(table.GetHeaderCount()) != 1:
            raise RuntimeError("T006 point table refused its one heading row")
    text_format = _early_bound(table.GetTextFormat(), "ITextFormat")
    text_format.CharHeight = FORM_TEXT_HEIGHT
    if table.SetTextFormat(False, text_format) is not True:
        raise RuntimeError("T006 point table refused its text height")
    for row, cells in enumerate(rows):
        for column, text in enumerate(cells):
            table.SetText2(row, column, False, text)
    for column, width in enumerate(FORM_TABLE_COLUMN_WIDTHS):
        actual = float(table.SetColumnWidth(column, width, _TABLE_SIZE_CAN_CHANGE))
        if abs(actual - width) > 1e-6:
            raise RuntimeError(
                f"T006 point table column {column} width reads {actual!r}"
            )
    for row in range(len(rows)):
        table.SetRowHeight(row, FORM_TABLE_ROW_HEIGHT, _TABLE_SIZE_CAN_CHANGE)
    rebuild_drawing(adapter, label="T006 point table")
    printed = [
        tuple(
            str(table.DisplayedText2(row, column, False) or "")
            for column in range(columns)
        )
        for row in range(len(rows))
    ]
    if printed != [tuple(cells) for cells in rows]:
        raise RuntimeError(f"T006 point table reads {printed!r}, expected {rows!r}")
    heights = [float(table.GetRowHeight(row)) for row in range(len(rows))]
    if any(height < FORM_TABLE_ROW_HEIGHT - 1e-4 for height in heights):
        raise RuntimeError(f"T006 point table row heights read {heights!r}")
    annotation = _early_bound(table.GetAnnotation(), "IAnnotation")
    position = tuple(float(value) for value in (annotation.GetPosition() or ()))
    if len(position) < 2 or math.dist(position[:2], FORM_TABLE_POS) > 1e-4:
        raise RuntimeError(f"T006 point table anchor reads {position!r}")
    draw.ClearSelection2(True)
    return table


def _draw_form_plot(adapter: Any) -> None:
    """Sketch the tooth-space plot on the active sheet and label it. Sheet
    sketch lines carry no dimensions: the sizes stay in the table."""
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    draw.ClearSelection2(True)
    ddoc.EditSheet()
    manager = _early_bound(draw.SketchManager, "ISketchManager")
    template = PROFILE.template
    root = template.root_radius_mm
    axis = form_plot_xy(0.0, -root)
    flank = form_plot_flank_mm()
    created = []
    previous_add_to_db = bool(manager.AddToDB)
    manager.AddToDB = True
    try:
        for side in (1.0, -1.0):
            sheet_points = [form_plot_xy(side * x, y) for x, y in flank]
            for start, end in zip(sheet_points, sheet_points[1:]):
                created.append(("flank", manager.CreateLine(*start, 0.0, *end, 0.0)))
        root_right = form_plot_xy(*flank[0])
        root_left = form_plot_xy(-flank[0][0], flank[0][1])
        # +1: counter-clockwise from the right end over the CL to the left.
        created.append(
            (
                "root arc",
                manager.CreateArc(*axis, 0.0, *root_right, 0.0, *root_left, 0.0, 1),
            )
        )
        top = form_plot_xy(0.0, custom_six_form_points_mm()[-1][2])[1]
        created.append(
            (
                "CL",
                manager.CreateCenterLine(
                    FORM_PLOT_ORIGIN[0],
                    FORM_PLOT_ORIGIN[1] - FORM_PLOT_CL_OVERRUN,
                    0.0,
                    FORM_PLOT_ORIGIN[0],
                    top + FORM_PLOT_CL_OVERRUN,
                    0.0,
                ),
            )
        )
        created.append(
            (
                "X axis",
                manager.CreateCenterLine(
                    *FORM_PLOT_ORIGIN,
                    0.0,
                    FORM_PLOT_ORIGIN[0] + FORM_PLOT_X_AXIS_LENGTH,
                    FORM_PLOT_ORIGIN[1],
                    0.0,
                ),
            )
        )
        blank = custom_six_form_points_mm()[-1][0]
        for key, radius in (
            ("junction", template.relief_junction_radius_mm),
            ("blank", blank),
        ):
            start = form_plot_xy(0.0, radius - root)
            end = form_plot_xy(
                *form_plot_station_mm(radius, FORM_PLOT_STATION_REACH_MM[key])
            )
            arc = manager.CreateArc(*axis, 0.0, *start, 0.0, *end, 0.0, 1)
            created.append((f"R{inch_text(radius, 4)} station", arc))
            if arc is not None:
                _early_bound(arc, "ISketchSegment").ConstructionGeometry = True
    finally:
        manager.AddToDB = previous_add_to_db
    missing = sorted({label for label, segment in created if segment is None})
    if missing:
        raise RuntimeError(f"failed to sketch the tooth-space plot's {missing}")
    draw.ClearSelection2(True)
    for text, position in form_plot_labels():
        if add_note(adapter, text, *position) is None:
            raise RuntimeError(f"failed to add the tooth-space plot note {text!r}")
    for text, text_xy, tip in (*form_point_tags(), *form_zone_labels()):
        note = add_leader_note(
            adapter, text, text_xy=text_xy, attach_xy=tip, label=f"DETAIL B {text}"
        )
        cone_sheet.set_note_height(note, FORM_TEXT_HEIGHT, label=f"DETAIL B {text}")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open cone tip gear source", await adapter.open_model(str(SOURCE)))
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
            "Manufacturing Notes",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Gear Data",
            "Manufacturing Notes",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter,
        property_view=PART_STEM,
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        unit=part_drawing_unit(PART_STEM),
    )
    cone_sheet.assert_dimension_arrow_length(drawing_model)
    create_blank_drawing_sheets(adapter, SHEET_NAMES, label="cone tip gear")
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Cone Tip Gear Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "cone tip gear; T006 with integral spigot and pivot",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    ddoc = _early_bound(drawing_model, "IDrawingDoc")
    if not ddoc.ActivateSheet(GEAR_SHEET):
        raise RuntimeError(f"failed to activate sheet {GEAR_SHEET}")

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=VIEW_SCALE)
    side = place_view(adapter, str(SOURCE), "*Right", *SIDE_ORIGIN, scale=VIEW_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (front, side, iso):
        set_hidden_lines_removed(adapter, view)
    _place_origin(adapter, front, FRONT_CENTER, label="front view")
    _place_origin(adapter, side, SIDE_ORIGIN, label="side view")
    _hide_tangent_edges(front)
    _assert_tooth_geometry(front)

    # The part saves its authoring sketches hidden; the front view shows the
    # tooth and floor witnesses again for their dimensions, the side view the
    # tip-diameter witness (the iso view shows the part as saved).
    front_annotations = hidden_sketches.curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="T006 front",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    floor = [a for a in front_annotations if dimension_name(adapter, a) == "FloorDia"]
    if len(floor) != 1:
        raise RuntimeError(f"expected one FloorDia dimension, found {len(floor)}")
    # The root envelope's leader stops on its near rim (ENFORCE round 4 of #971).
    set_near_side_diameter(floor[0], "T006 FloorDia")
    rebuild_drawing(adapter, label="near-side root envelope")
    side_annotations = hidden_sketches.curate_view_dimensions(
        adapter,
        side,
        keep=SIDE_KEEP,
        view_label="lathe side",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    annotations = [*front_annotations, *side_annotations]
    _assert_sheet_bands(adapter, annotations)
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    set_dimension_callouts(adapter, annotations, CALLOUTS_ABOVE, location="above")
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    printed = {dimension_name(adapter, annotation) for annotation in annotations}
    if printed != sheet_dimension_names():
        raise RuntimeError(
            f"sheet prints {sorted(printed)}, the part marks {sorted(sheet_dimension_names())}"
        )
    sheet = _early_bound(ddoc.GetCurrentSheet(), "ISheet")
    if not sheet.SetScale(*VIEW_SCALE, False, False):
        raise RuntimeError("failed to pin the T006 sheet scale")
    cone_sheet.shelve_tooth_thickness(
        adapter,
        front_annotations,
        line_x=FRONT_KEEP["ToothThickness"][0],
        target=tooth_thickness_shelf(),
        label="T006 thickness text",
    )
    _center_mark_pivot(adapter, front)
    _mark_form_detail(adapter, front)
    _add_overall_reference(adapter, side)
    _add_axis(adapter)
    pivot_top = (PIVOT_END_X + PIVOT_FINISH_INSET, AXIS_Y + STEM_HALF)
    add_surface_finish(
        adapter,
        side,
        symbol_xy=PIVOT_FINISH_XY,
        control=surface_finish_by_key(SURFACE_FINISHES, "pivot_journal"),
        label="pivot journal finish",
        char_height=NOTE_HEIGHT,
        entity_type="FACE",
        entity=_pivot_face(side),
        leader_attach_xy=pivot_top,
    )
    drawing_model.ClearSelection2(True)
    ddoc.EditSheet()
    add_property_linked_note(
        adapter, "Gear Data", *GEAR_DATA_POS, char_height=NOTE_HEIGHT
    )
    add_property_linked_note(
        adapter, "Manufacturing Notes", *NUMBERED_NOTES_POS, char_height=NOTE_HEIGHT
    )
    rebuild_drawing(adapter, label="T006 layout audit")
    check_drawing_layout(adapter, layout=SPEC.layout, stem="cone tip gear T006")

    if not ddoc.ActivateSheet(CUTTER_DETAIL_SHEET):
        raise RuntimeError("failed to activate the T006 tooth-space sheet")
    # The title block reads the part, number and alloy through this view, so
    # it stays on the sheet, hidden.
    source_view = place_view(
        adapter,
        str(SOURCE),
        "*Front",
        *CUTTER_SOURCE_VIEW_CENTER,
        scale=SHEET_SCALES[CUTTER_DETAIL_SHEET],
    )
    _hide_title_block_source(adapter, source_view)
    # The plot first: it puts the sheet in edit mode, so the table and notes
    # below belong to the sheet, not the hidden source view.
    _draw_form_plot(adapter)
    table = _insert_form_table(adapter)
    table_height = sum(
        float(table.GetRowHeight(row)) for row in range(int(table.RowCount))
    )
    notes_xy = form_notes_pos(table_height)
    if notes_xy[1] - len(form_sheet_notes().splitlines()) * NOTE_LINE_PITCH < 0.100:
        raise RuntimeError(f"T006 point table runs {table_height * 1000:.1f} mm tall")
    for text, position, label in (
        (form_sheet_title(), FORM_TITLE_POS, "T006 tooth-space title"),
        (form_sheet_notes(), notes_xy, "T006 tooth-space notes"),
    ):
        note = add_note(adapter, text, *position)
        if note is None:
            raise RuntimeError(f"failed to add the {label}")
        cone_sheet.set_note_height(note, FORM_TEXT_HEIGHT, label=label)
    sheet = _early_bound(ddoc.GetCurrentSheet(), "ISheet")
    if not sheet.SetScale(*SHEET_SCALES[CUTTER_DETAIL_SHEET], False, False):
        raise RuntimeError("failed to pin the DT6-FORM1 sheet scale")
    rebuild_drawing(adapter, label="DT6-FORM1 layout audit")
    check_drawing_layout(adapter, layout=SPEC.layout, stem="cone tip gear DT6-FORM1")

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Cone Tip Gear Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        expected_sheet_names=SHEET_NAMES,
        sheet_layouts={name: SPEC.layout for name in SHEET_NAMES},
        sheet_scales=SHEET_SCALES,
        checkpoint=_check_exported_pdf,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
