"""Draw the ReliaBot T8 kit (Amazon B085DDHJTW), MHA-CH-06-TL-VN-84: three sheets.

Sheet 1 is the configured purchased-part reference: the LeadScrew member as
its isometric only, its header pointing at sheet 2 (at 1:8 its orthographic
views were unreadable, farm run 20261105T035724094Z), the FeedNut member in
four views carrying the listing's nominal sizes as supplier references, the
installed quantities and the kit's supplier footer.

Sheet 2 (LEADSCREW) is the LeadScrew member's modified-stock content: the
shop cuts the bought 600 mm screw to length and mills a set-screw flat under
each set screw that locks it. One view of the screw lies axis-horizontal, as
it sits in the saw and the mill, carrying the native ``CutLength`` and the
far two flats' stations (the title block's band for each one's places governs
it); details C, D and E at 3:1 of the near end's station, the far KP08's and
the handwheel's, the 1:2 view drawing a flat 0.36 mm deep: C carries the near
station, E the printed flat's length and across-flat; sections A-A and B-B
through the two KP08 stations, each carrying its 120° flat's across-flat and
angle from clock 0, the angle's text offset outboard of its arc; the
isometric; and a note block naming the item, its supplier and SKU. The thread
is bought, not cut: it is not modelled, and a leadered callout on the main
view names it over the full length.

Sheet 3 (FEED NUT REWORK) is the FeedNut member's rework and receipt (Codjiflo
P2 and 4475311251 on #2187): section F-F through two countersunk holes,
carrying the native ``FlangeThick`` and ``CskDia`` LIMITs, the countersink's
82° callout and the faced length's LIMIT; and the end view, carrying the native
receipt limits: the flange OD, the body's MAX, the holes and their PCD. TL-00's
F1A cites this sheet (``feed_nut.REWORK_SHEET_REFERENCE``) and types none of
them.

Run with SolidWorks open::

    uv run python cad\\scripts\\draw_ch_rocker_arm_tl_vn_oblique_leadscrew_kit.py ch-rocker-arm-tl-vn-oblique-leadscrew-kit
"""

from __future__ import annotations

import argparse
import math
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Callable, NamedTuple

from solidworks_mcp.adapters import sw_type_info as _sw_type_info
from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    dimension_name,
    iter_views,
    place_view,
    view_name,
)

from _com import _early_bound, _read_member
import _config
from _drawing_annotation_extent import (
    CLEAR_GAP_M,
    callout_ink,
    require_clear,
    require_inside,
    require_leader_clear,
    sheet_region,
)
from _drawing_centerline import add_view_centerline
from _drawing_common import read_required_properties, rebuild_drawing
from _drawing_detail_projection import settle_detail_projection
from _drawing_dimension_import import curate_view_dimensions
from _drawing_dimensions import offset_dimension_text, set_dimension_callouts
import _drawing_hidden_sketches as hidden_sketches
from _drawing_leader_notes import add_leader_note
from _drawing_leaders import dimension_text_points, set_near_side_diameter
from _drawing_notes import property_link
from _drawing_projection import model_points_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_sections import create_section_view
from _drawing_sheet_region import sheet_drawable_region
from _drawing_types import DRAWING_TEMPLATES
from _drawing_view_display import _SW_HLR, set_hidden_lines_removed
from _machinist_review_mode import MachinistReviewMode
from _part_properties import part_drawing_unit
from _purchased_fastener_drawing import (
    _box,
    _inside,
    _literal_note,
    _purchased_title_block,
    _rebuild,
)
from _purchased_title_fit import fit_purchased_title_block
from _purchased_variant_drawing import (
    build_purchased_variant_drawing,
    configure_reference_views,
)
from _rebuild import active_configuration_name
from _session import run_build
from _stock_trim_drawing import verify_machining_controls
from _supplier_screw_dimensions import annotate_supplier_screw
from _supplier_text_shelf import assert_supplier_shelves, shelve_supplier_text
import _telemetry
import ch_rocker_arm_tl_vn_oblique_leadscrew_kit_feed_nut_spec as feed_nut
import ch_rocker_arm_tl_vn_oblique_leadscrew_kit_leadscrew_spec as leadscrew
from ch_rocker_arm_tl_vn_oblique_leadscrew_kit_leadscrew_spec import (
    DIMENSION_CONTROLS,
    DIMENSION_PRECISION,
    DIMENSION_TOLERANCE_TYPES,
    DRAWING_DIMENSIONS,
    FLAT_AF,
    FLAT_AF_CALLOUT,
    FLAT_LENGTH,
    FLAT_LENGTH_CALLOUT,
    FLAT_STARTS,
    FLAT_STATIONS,
    KP08_SET_SCREW_SPACING_DEG,
    LENGTH,
    MAJOR_DIA,
    PRINTED_LENGTH_FLAT,
    control_si,
)

MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["ch_rocker_arm_tl_vn_oblique_leadscrew_kit"]
PART_STEM = SPEC.artifact_stem
SOURCE = SPEC.source

# --- Sheet 1: the configured purchased reference -----------------------------
# The footer's ITEM row: the listing's designation in plain text.
ITEM = "TR8X2 LEAD SCREW, 600 MM, WITH BRASS FLANGE NUT"
# Literal, so the source-property contract can read it without importing.
VARIANTS = (
    ("LeadScrew", "[1] LEADSCREW"),
    ("FeedNut", "[2] FEED NUT"),
)
if tuple(name for name, _label in VARIANTS) != (
    leadscrew.CONFIGURATION,
    feed_nut.CONFIGURATION,
):
    raise AssertionError("sheet 1's members are not the specs' configurations")
PURCHASE_UNIT = "ONE KIT"
LEADSCREW_SHEET_NAME = "LEADSCREW"
REWORK_SHEET_NAME = "FEED NUT REWORK"
# Sheet 1 is the reference sheet; these follow it in order.
SHEET_NAMES = (LEADSCREW_SHEET_NAME, REWORK_SHEET_NAME)
if SHEET_NAMES.index(LEADSCREW_SHEET_NAME) + 2 != leadscrew.MODIFIED_STOCK_SHEET:
    raise AssertionError("the LeadScrew's notes cite another sheet")
if SHEET_NAMES.index(REWORK_SHEET_NAME) + 2 != feed_nut.REWORK_SHEET:
    raise AssertionError("TL-00's rework reference cites another sheet")
GENERAL_TEXT = (
    f"REFERENCE VIEWS; [1] CUT PER SHEET {leadscrew.MODIFIED_STOCK_SHEET}; "
    f"[2] REWORK PER SHEET {feed_nut.REWORK_SHEET}."
)
ADDITIONAL_SHEETS_TITLE = "Member Rework"
# Sheet 2 draws the LeadScrew's views; sheet 1 shows its isometric.
ISOMETRIC_ONLY = {leadscrew.CONFIGURATION: leadscrew.MODIFIED_STOCK_SHEET}
# The only member carrying supplier references. The source part stays active
# in it while the package is drawn (see require_source_configuration).
SUPPLIER_REFERENCE_CONFIGURATION = feed_nut.CONFIGURATION
# The retired TL-VN-55 sheet's shelves for the same nut: every chord's
# horizontal text is wider than its span or crosses its own vertical
# dimension line, so each text slides sideways, just past all of its own line
# ink on its free side; the native tips, witnesses and lines stay put.
SHELVES = {
    name: (orientation == "horizontal", side)
    for (name, _value, orientation), side in zip(
        feed_nut.SUPPLIER_REFERENCE_DIMENSIONS,
        ("right", "left", "right", "right", "right", "left"),
        strict=True,
    )
}

# --- Sheets 2 and 3: shared sheet frame -----------------------------------------
# ASME B landscape, sheet metres: 431.8 x 279.4 with the inner border 12.7 in
# from each edge, so 406.4 mm of drawable width. The title block spans
# x >= 0.2159 below y = 0.0651.
BORDER = (0.0127, 0.0127, 0.4191, 0.2667)
TITLE_BLOCK = (0.2159, 0.0127, 0.4191, 0.0651)
ITEM_LABEL_XY = (0.025, 0.262)
ITEM_LABEL_CELL = (0.015, 0.250, 0.200, 0.264)

# --- Sheet 2: the LeadScrew --------------------------------------------------------
# The installed screw exceeds the 406.4 mm border at 1:1; 1:2 leaves room
# for its native cut-length dimension. All view extents below read LENGTH.
SHEET_SCALE = (1.0, 2.0)
ISO_SCALE = SHEET_SCALE  # One-scale sheet: no per-view scale label.
_SHEET_PER_MODEL_MM = SHEET_SCALE[0] / SHEET_SCALE[1] / 1000
SCREW_SHEET_LENGTH = LENGTH * _SHEET_PER_MODEL_MM
SCREW_SHEET_DIA = MAJOR_DIA * _SHEET_PER_MODEL_MM

# *Front looks square at the Front-plane profile sketch, so CutLength imports
# into it; turned -90 deg, model +Y (near end y = 0 to the far end) runs to
# sheet right and the axis lies horizontal.
MAIN_VIEW_ANGLE = -math.pi / 2.0
# Keep the main view left of the isometric column. The length read from
# the model determines both ends; y .160 clears the title block.
MAIN_CENTER = (0.195, 0.160)
# The isometric stands the axis up. Its physical height follows LENGTH
# and the end diameter; the final native layout audit checks containment.
ISO_CENTER = (0.390, 0.166)
# Model station s (mm from the near end) on the main view's sheet x.
NEAR_END_X = MAIN_CENTER[0] - SCREW_SHEET_LENGTH / 2.0


def sheet_x(station_mm: float) -> float:
    return NEAR_END_X + station_mm * _SHEET_PER_MODEL_MM


# The clock-0 flats face model +X, which the turned view lays toward the
# sheet's bottom: each flat stands edge-on 0.72 mm (0.36 on the sheet) into
# the lower silhouette, too shallow to read, so details C, D and E carry the
# flats. CutLength's text stands 30 mm over the axis, centred on the span, its
# dimension line clear over the sections' letters (12 mm cutting-line reach,
# letters to 20 mm over the axis); its extension lines rise from the end
# faces' centres. Under the screw, the far two flats' stations run from the
# near end's centre to each flat's near edge, each in its own row; the near
# one's is detail C's.
MAIN_KEEP = {
    "CutLength": (MAIN_CENTER[0], MAIN_CENTER[1] + 0.030),
    "FarKP08FlatStation": (
        (NEAR_END_X + sheet_x(FLAT_STARTS["FarKP08"])) / 2.0,
        MAIN_CENTER[1] - 0.024,
    ),
    "HandwheelFlatStation": (
        (NEAR_END_X + sheet_x(FLAT_STARTS["Handwheel"])) / 2.0,
        MAIN_CENTER[1] - 0.032,
    ),
}
# The thread is the stock's: a leadered callout over the screw names it, its
# leader's tip on the upper silhouette, the text (top-left anchored, two rows
# about 9 mm tall and 56 mm wide) between the sections' A letters (x <= 0.121)
# and B letters (x >= 0.263), under the cut length's dimension line (0.187).
THREAD_CALLOUT = "TR8X2 THREAD FULL LENGTH\nAS SUPPLIED"
THREAD_CALLOUT_XY = (0.140, 0.181)
THREAD_LEADER_TIP = (sheet_x(80.0), MAIN_CENTER[1] + SCREW_SHEET_DIA / 2.0)


class ClockSection(NamedTuple):
    """One KP08 station's section: the clock flat it shows, its letter, where
    its cutting line crosses the axis (model mm from the near end: inside the
    flat, 1.5 off its station toward the screw's middle, so the line stands
    2.5 clear of both flat ends and of the far flat's printed start, 375.5:
    3.5 off, it ran almost on that extension line, machinist review), whether
    it looks toward the far end (model +Y, sheet right; its arrows then point
    right, away from the screw's nearer end and the cut length's extension
    line), and where the section's axis stands on the sheet."""

    flat: str
    label: str
    cut_mm: float
    looks_far: bool
    centre: tuple[float, float]


SECTION_SCALE = (3, 1)
_SECTION_CUT_OFF_STATION_MM = FLAT_LENGTH / 2.0 - 2.5
# Above the main view, under the top border: each face 12 mm in radius at
# 3:1, its texts within 24 mm of its axis, its caption under its lowest ink.
CLOCK_SECTIONS = (
    ClockSection(
        "NearKP08",
        "A",
        FLAT_STATIONS["NearKP08"] + _SECTION_CUT_OFF_STATION_MM,
        True,
        (0.090, 0.235),
    ),
    ClockSection(
        "FarKP08",
        "B",
        FLAT_STATIONS["FarKP08"] - _SECTION_CUT_OFF_STATION_MM,
        False,
        (0.280, 0.235),
    ),
)
# The cutting line's reach either side of the axis on the main view's sheet:
# its letters (4.8 .. 6.3 mm in from the line's ends, draw_dt_cone_gear_shaft)
# stand 3.7 mm off the screw's silhouettes.
SECTION_REACH = 0.012
# A section's axis lands within this of its layout point.
SECTION_SETTLE_M = 0.0005
# Each section's across-flat text stands this far (model mm) from the axis,
# square to its flat's radial on the side away from the angle. The angle's
# arc stands on its bisector just outside the face, and its text is offset
# outboard along the bisector onto a leader (the trammel pivot point's tip
# angle), so the arc never runs through its own text.
CLOCK_AF_TEXT_RADIUS_MM = MAJOR_DIA / 2.0 + 3.5
CLOCK_ANGLE_ARC_RADIUS_MM = MAJOR_DIA / 2.0 + 1.5
CLOCK_ANGLE_TEXT_RADIUS_MM = MAJOR_DIA / 2.0 + 5.5
# A dimension's text stands this far either side of its position point.
TEXT_HALF_HEIGHT = 0.003
# The angle's extension line along clock 0 runs this far past its arc.
EXTENSION_OVERSHOOT = 0.0015
SECTION_CAPTION_GAP = 0.003
CAPTION_SETTLE_M = 0.0006
# The section's centre mark keeps only its cross, arms this long on the sheet
# (draw_dt_cone_gear_shaft).
CENTRE_MARK_ARM = 0.003
_CENTER_MARK_ANNOTATION = 13  # swAnnotationType_e.swCenterMarkSym


class EndDetail(NamedTuple):
    """One 3:1 detail of the main view: its letter, its fence (a circle on the
    axis ``centre_mm`` from the near end, ``radius_mm`` across, model mm),
    where the fence's centre stands on the sheet, where its letter stands on
    the main view, and the dimensions it carries, each by its text's sheet
    point."""

    label: str
    centre_mm: float
    radius_mm: float
    centre: tuple[float, float]
    letter: tuple[float, float]
    keep: dict[str, tuple[float, float]]


DETAIL_SCALE = SECTION_SCALE
_DETAIL_PER_MODEL_MM = DETAIL_SCALE[0] / DETAIL_SCALE[1] / 1000.0
# The details stand in a row under the main view (its lowest text, the
# handwheel station's, 32 mm under the axis) and left of the title block,
# each fence's centre on DETAIL_ROW_Y. Their dimension texts stand in one row
# under the fences and their captions in one row under that.
# Reserve the settled native frame, not only the geometric fence. The 0c3
# final audit already put C at x8.518..77.294 mm despite passing its early
# placement check; 84d read that same frame before the check and refused.
# Translate the whole bank +8 mm: C's final left is x16.518, E's final
# right x200.288, preserving all fence/text gaps and the x215.9 title keep-out.
DETAIL_ROW_Y = 0.082
DETAIL_TEXT_ROW_Y = 0.050
DETAIL_CAPTION_TOP = 0.036
# A detail's axis runs as the main view's: model +Y to sheet right, model +X
# (clock 0, where every station's printed flat faces) to sheet down.
DETAIL_ORIENTATION_TOL = 1e-6
# A detail's fence centre lands within this of its layout point.
DETAIL_SETTLE_M = 0.0002


def detail_xy(
    centre_mm: float,
    centre: tuple[float, float],
    station_mm: float,
    radius_mm: float = 0.0,
) -> tuple[float, float]:
    """Sheet point of station ``station_mm``, ``radius_mm`` toward clock 0, in
    a detail whose fence centre (``centre_mm`` on the axis) stands at
    ``centre``."""
    return (
        centre[0] + (station_mm - centre_mm) * _DETAIL_PER_MODEL_MM,
        centre[1] - radius_mm * _DETAIL_PER_MODEL_MM,
    )


def _text_row_radius_mm() -> float:
    """The model radius (toward clock 0) of the details' text row."""
    return (DETAIL_ROW_Y - DETAIL_TEXT_ROW_Y) / _DETAIL_PER_MODEL_MM


# C: the near end and the near KP08's two flats (0 .. 12.5), its station
# from the near end's centre under the fence.
_NEAR_CENTRE_MM = (FLAT_STATIONS["NearKP08"] + FLAT_LENGTH / 2.0) / 2.0
_NEAR_XY = (0.051, DETAIL_ROW_Y)
# D: the far KP08's two flats (375.5 .. 383.5); its station is the main
# view's. The printed flat length (every KP08 flat's) stands under the
# fence, right of the flat: the flat length's text (widest row
# "4X FLATS FOR", about 26 mm) is wider than the flat's 24 mm at 3:1, so
# it stands right of the flat's far-end extension line, its dimension line
# run out to it (review jbf-r17, rule 14: both extension lines crossed the
# text), left of fence E.
_FAR_CENTRE_MM = FLAT_STATIONS["FarKP08"]
_FAR_XY = (0.099, DETAIL_ROW_Y)
# E: the handwheel's open flat and the cut end, its
# across-flat left of it, square to the axis: its extension line off the
# flat runs back along the flat and out of the fence over the thread. The
# flat runs out through the cut end (owner ruling 2026-11-05), so the
# detail shows no land past it. The fence's radius 7 holds the flat's start
# corners and the far end's (each 6.40 off its centre) whole.
# The across-flat's text (its widest row, "C, D, E", about 15 mm wide, centred
# on its dimension line) stands between D's fence and E's.
_WHEEL_CENTRE_MM = (FLAT_STARTS["Handwheel"] + LENGTH) / 2.0
_WHEEL_RADIUS_MM = 7.0
_WHEEL_XY = (0.1695, DETAIL_ROW_Y)
# The across-flat runs from the far crest (clock 180, radius -4) to the flat
# (FLAT_AF - 4 toward clock 0): its middle stands at half their sum.
_AF_MID_RADIUS_MM = (FLAT_AF - MAJOR_DIA) / 2.0
FLAT_LENGTH_TEXT_HALF_WIDTH = 0.0155
FLAT_LENGTH_TEXT_GAP = 0.003
END_DETAILS = (
    EndDetail(
        "C",
        _NEAR_CENTRE_MM,
        8.0,
        _NEAR_XY,
        # Left of the near end, under the cut length's extension line.
        (NEAR_END_X - 0.012, MAIN_CENTER[1] - 0.010),
        {
            "NearKP08FlatStation": detail_xy(
                _NEAR_CENTRE_MM,
                _NEAR_XY,
                FLAT_STARTS["NearKP08"] / 2.0,
                _text_row_radius_mm(),
            ),
        },
    ),
    EndDetail(
        "D",
        _FAR_CENTRE_MM,
        6.0,
        _FAR_XY,
        # Over its fence, between section B-B's cutting line and the cut
        # length's far extension line.
        (sheet_x(FLAT_STATIONS["FarKP08"]) + 0.005, MAIN_CENTER[1] + 0.012),
        {
            "FlatLength": (
                detail_xy(
                    _FAR_CENTRE_MM,
                    _FAR_XY,
                    FLAT_STARTS[PRINTED_LENGTH_FLAT] + FLAT_LENGTH,
                )[0]
                + FLAT_LENGTH_TEXT_GAP
                + FLAT_LENGTH_TEXT_HALF_WIDTH,
                detail_xy(_FAR_CENTRE_MM, _FAR_XY, 0.0, _text_row_radius_mm())[1],
            ),
        },
    ),
    EndDetail(
        "E",
        _WHEEL_CENTRE_MM,
        _WHEEL_RADIUS_MM,
        _WHEEL_XY,
        # Right of the far end, level with the axis.
        (sheet_x(LENGTH) + 0.008, MAIN_CENTER[1]),
        {
            "FlatAF": detail_xy(
                _WHEEL_CENTRE_MM,
                _WHEEL_XY,
                _WHEEL_CENTRE_MM - _WHEEL_RADIUS_MM - 3.5,
                _AF_MID_RADIUS_MM,
            ),
        },
    ),
)
# Every closed flat is one size: the printed one says how many
# (pivot-shaft style) and which (review bought-r16, rule 1: "3X" and "5X" on
# detail E's one flat left the reader to work out which flats they cover).
# The length is every KP08 flat's, the pillow blocks named by their
# same-parent short drawing number (rule 4).
# The handwheel's flat runs to the end, which detail E shows; its start
# station prints bare (rule 7: a location carries no words). The
# across-flat is each clock-0 flat's, one in each detail, all three on one
# clock: "IN LINE" says so, and with "3X" that E has that one flat alone
# (review of farm run 20261108T015328529Z: detail E left its flat count and
# its angle to D's flats undefined); the clock flats print their own in
# sections A-A and B-B. The across-flat's rows stay narrower than the 25 mm
# between fences D and E.
_JIG_PREFIX = "MHA-CH-06-"


def short_number(number: str) -> str:
    """A jig mate's same-parent short form (``TL-VN-56`` for MHA-CH-06-TL-VN-56)."""
    if not number.startswith(_JIG_PREFIX):
        raise ValueError(f"{number} is not in the oblique jig's parent MHA-CH-06")
    return number.removeprefix(_JIG_PREFIX)


KP08_NUMBER = _config.parts("ch-rocker-arm-tl-vn-oblique-pillow-block")["number"]
FLAT_CALLOUTS = {
    "FlatLength": f"{FLAT_LENGTH_CALLOUT} FLATS FOR\n{short_number(KP08_NUMBER)}",
    "FlatAF": "\n".join(
        (f"{FLAT_AF_CALLOUT} IN LINE", ", ".join(detail.label for detail in END_DETAILS))
    ),
}
# The cylinder face on the axis, 50 mm right of centre: 2 mm from either
# silhouette and clear of the dimension above.
CENTERLINE_PICK = (MAIN_CENTER[0] + 0.050, MAIN_CENTER[1])
# Right of the details and over the title block (top-left anchored, three
# rows about 13 mm tall and 70 mm wide): under the handwheel station's text
# (0.128) and left of the isometric.
NOTES_XY = (0.230, 0.105)
# The catalogue designation in plain text: the material is the title block's
# and the cut length is the dimension's. The bought stock's sizes print
# nowhere: the item's thread designation and the SKU identify the stock, and
# a note row typing spec numbers no native dimension owns breaks model
# ownership (rule 7; review of a numeric STOCK row and, before it, a 1:10
# gauge sketch that read as a confusing pseudo-view).
LEADSCREW_ITEM = "[1] TR8X2 LEAD SCREW"
NOTES = "\n".join(
    (
        f"ITEM: {LEADSCREW_ITEM}",
        f"SUPPLIER: {property_link('Supplier')}",
        f"SKU: {property_link('Supplier SKUs')}",
    )
)
EXPECTED_CONTROLS = {
    name: (nominal, -band, band)
    for name, (nominal, band) in (
        (name, control_si(name)) for name in DIMENSION_CONTROLS
    )
}

# --- Sheet 3: the FeedNut REWORK ------------------------------------------------
# 4:1 lays the Ø22 flange 88 mm across and its 3.5 thickness 14 mm.
REWORK_SCALE = (4.0, 1.0)
_REWORK_PER_MODEL_MM = REWORK_SCALE[0] / REWORK_SCALE[1] / 1000.0
# The end view looks down the body onto the head face, turned so model +X runs
# up the sheet: section F-F's vertical cutting line then crosses the two
# countersinks on X, the holes whose profiles (Front) own the printed
# controls, and the section beside it lies axis-horizontal (rule 11). The
# letter F, since sheet 2 already uses A to E.
REWORK_END_ANGLE = math.pi / 2.0
REWORK_END_CENTER = (0.110, 0.160)
REWORK_SECTION_LABEL = "F"
REWORK_SECTION_CENTER = (0.280, 0.160)
# The cutting line runs this far past the flange rim each side (sheet).
REWORK_SECTION_OVERRUN = 0.008
# Text points, model mm (radius toward +X, station from the seat face): the
# flange's thickness beyond its rim, its one callout line above the limits;
# the countersink's past the body's end and above it. That callout prints on
# a leader whose shoulder starts at the text point and runs right under the
# block (run 20261105T010614057Z: shoulder 0.331 to 0.425, past the border at
# 0.419), so the point sits just clear of the body's end. Its rows hang over
# the shoulder from the dimension line, so the shoulder stands over the upper
# outside arrow's tail: at 1.0 mm past the rim the last row straddled the
# upper extension line and the arrow struck its first letter (rule 14,
# machinist review, farm runs 20261108T000844770Z and 20261108T015328529Z;
# the arrow's tail stood 7 mm over the shoulder on the sheet). 3.5 mm lifts
# it 10 mm, the tail then 3 mm under it.
FLANGE_THICK_TEXT_MM = (feed_nut.FLANGE_DIA / 2.0 + 6.0, feed_nut.FLANGE_THICK / 2.0)
CSK_DIA_TEXT_MM = (feed_nut.FLANGE_DIA / 2.0 + 3.5, feed_nut.LENGTH + 2.0)
# The faced length's line stands 2.5 mm under the flange's rim, its witnesses
# down from the body's -X silhouette, over the section's caption
# (REWORK_CAPTION_TOP). Its offset text block is CENTRED on its point (run
# 20261105T023247678Z: point (0.313, 0.106) printed 0.280 .. 0.345 by
# 0.098 .. 0.114, its own line and far witness through it), so the point
# stands right of the far witness and under the line: the block clears both
# and the caption, over the title block.
FACED_LENGTH_LINE_MM = (-(feed_nut.FLANGE_DIA / 2.0 + 2.5), feed_nut.LENGTH_MAX / 2.0)
FACED_LENGTH_TEXT_MM = (-(feed_nut.FLANGE_DIA / 2.0 + 5.4), feed_nut.LENGTH_MAX + 10.5)
# Section F-F's native caption (SECTION F-F over SCALE 4 : 1): its box's top
# centre. Where SolidWorks hung it (run 20261105T054045952Z: printed 0.2586 ..
# 0.3014 by 0.0833 .. 0.0975), the faced length's leader, from its dimension
# line's middle (0.2806, 0.1060) to its shoulder (0.3182, 0.0861), ran through
# the second F (gating review). The leader starts over the caption's span, so
# its shoulder would have to stand 84 mm right of that start to clear the
# caption by the readback's gap, running the text past the border (0.419).
# The caption drops instead, centred under the section: its top 3.5 mm under
# the leader's height (0.0915) at the caption's padded right edge (0.308), its
# two rows (14.2 mm printed) over the title block (0.0651).
REWORK_CAPTION_TOP = (REWORK_SECTION_CENTER[0], 0.086)
# The receipt limits on the end view (4475311251): four diameters, each a
# leadered callout whose block is CENTRED on its text point (run
# 20261105T023247678Z: the body's point (0.171, 0.2175) printed 0.147 .. 0.195
# by 0.209 .. 0.225, and the hole's crossed the flange's Ø22 outline and the
# +Z hole). Each one's arrow lands on its circle's near side
# (set_near_side_diameter), its leader radial from the circle's centre to the
# block's shoulder (the corner of its underline nearer the arrow), so no two
# leaders from the shared centre cross. Two stack in the gap between the end
# view's rim (x 0.154) and the section (x 0.253), under the FlangeThick
# callout row (run 11: from y 0.232) and over the spigot note's extent (to y
# 0.144): the body's five rows (its LIMIT and RV-02's wall), from 31°, and
# the +Z hole's. A radial leader under 23° would cross the +Z countersink,
# so the bolt circle's leaves its circle at its lower right instead, right
# of the cutting line's lower F, for a block under the spigot note; the
# flange OD's leaves its rim at its lower left, for a block left of the
# cutting line.
RECEIPT_TEXT_XY = {
    "ReceiptBodyDia": (0.205, 0.214),
    "ReceiptHoleDia": (0.205, 0.1595),
    "ReceiptHolePcd": (0.185, 0.093),
    "ReceiptFlangeDia": (0.054, 0.093),
}
# The receipt callouts' hole is the +Z one: the end view must lay it right of
# its centre, on the centre's height, for the layout above.
RECEIPT_HOLE_MODEL = (0.0, 0.0, feed_nut.HOLE_PCD / 2000.0)
# Rule 4: each band tighter than the title block's names its mate. The faced
# seat bears on TL-32's lug face and the flange is the four nut screws' grip;
# the countersinks seat those screws' 82° heads. The faced length keeps the
# nut clear of the KP08 at the travel end; the flange OD sits within the lug
# face; the body clears the screws' heads; the holes and their PCD match the
# lug's transferred taps.
# Rule 17: the countersink's and the body's callouts state their walls as a
# plain fact (RV-01, RV-02, as dt-cone-gear-tl-index-plate prints WEB .03
# MIN). Rule 7: each leadered callout is its size line plus at most two
# lines of words, its mate named once by its same-parent short number.
FEED_BLOCK_NUMBER = _config.parts("ch-rocker-arm-tl-oblique-feed-block")["number"]
NUT_SCREW_NUMBER = _config.parts("ch-rocker-arm-tl-vn-oblique-riser-screw")["number"]
if feed_nut.SCREW_SKU not in _config.parts("ch-rocker-arm-tl-vn-oblique-riser-screw")[
    "supplier_skus"
]:
    raise AssertionError("the nut screws' number is not the screw the spec sizes")
# One line: SolidWorks keeps a line-broken ABOVE callout but never prints it
# (run 20261105T010614057Z printed this one's limits alone).
FLANGE_THICK_CALLOUT = (
    f"SEAT FACE ON {FEED_BLOCK_NUMBER} LUG, "
    f"GRIP OF {feed_nut.SCREW_COUNT}X {NUT_SCREW_NUMBER}"
)
# The size line is the dimension's own: "4X ⌵ Ø4.76/4.50 X 82°", the
# countersink symbol in the model's prefix and the angle this sheet's suffix.
CSK_SCREW_CALLOUT = (
    f"FOR {short_number(NUT_SCREW_NUMBER)} ({feed_nut.SCREW_SKU})\n"
    f"{feed_nut.CSK_WALL_TEXT}"
)
# name -> (callout lane, text); swDimensionTextCalloutAbove 3, Below 4.
REWORK_CALLOUTS = {
    "FlangeThick": ("above", FLANGE_THICK_CALLOUT),
    "CskDia": ("below", CSK_SCREW_CALLOUT),
    "FacedLength": ("below", f"CLEARS KP08 AT TRAVEL END\n{KP08_NUMBER}"),
}
RECEIPT_CALLOUTS = {
    "ReceiptFlangeDia": ("below", f"WITHIN {FEED_BLOCK_NUMBER}\nLUG FACE"),
    # Rule 17: the thread's body wall as a plain fact (RV-02), as the
    # countersink's callout states its walls (RV-01).
    "ReceiptBodyDia": (
        "below",
        f"CLEARS HEADS OF {feed_nut.SCREW_COUNT}X {short_number(NUT_SCREW_NUMBER)}\n"
        f"{feed_nut.THREAD_WALL_TEXT}",
    ),
    # The supplied holes are received, not cut (the band feeds RV-01's walls).
    "ReceiptHoleDia": (
        "below", f"AS SUPPLIED, MATCHES TAPS IN\n{FEED_BLOCK_NUMBER} LUG",
    ),
    "ReceiptHolePcd": ("below", f"PCD, MATCHES TAPS IN\n{FEED_BLOCK_NUMBER} LUG"),
}
_CALLOUT_TEXT_PARTS = {"above": 3, "below": 4}
if any(
    "\n" in text
    for lane, text in (*REWORK_CALLOUTS.values(), *RECEIPT_CALLOUTS.values())
    if lane == "above"
):
    raise AssertionError("an above-callout with a line break does not print")
# The faced face: the spigot stood on the seat face, inside the Ø10.2; its
# tip lands midway across that annulus, on the -X half below the axis. The
# note's text sits left of the section, between it and the end view, its
# upper-left at SPIGOT_NOTE_XY; its native extent also spans the leader.
SPIGOT_NOTE = "SPIGOT FACED FLUSH\nWITH FLANGE SEAT FACE"
SPIGOT_TIP_MM = (-(feed_nut.BORE_DIA + feed_nut.BODY_DIA) / 4.0, 0.0)
SPIGOT_NOTE_XY = (0.172, 0.130)
SPIGOT_NOTE_CELL = (0.165, 0.108, 0.248, 0.136)
_LEADER_TIP_MARGIN = 0.001
REWORK_EXPECTED = {
    name: (nominal / 1000.0, lower / 1000.0, upper / 1000.0)
    for name, (nominal, lower, upper, _places) in feed_nut.REWORK_CONTROLS.items()
}
REWORK_PRECISION = {
    name: places for name, (_n, _l, _u, places) in feed_nut.REWORK_CONTROLS.items()
}
RECEIPT_EXPECTED = {
    name: (nominal / 1000.0, lower / 1000.0, upper / 1000.0)
    for name, (nominal, lower, upper, _places) in feed_nut.RECEIPT_CONTROLS.items()
}
RECEIPT_PRECISION = {
    name: places for name, (_n, _l, _u, places) in feed_nut.RECEIPT_CONTROLS.items()
}
if set(RECEIPT_TEXT_XY) != set(RECEIPT_CALLOUTS) or set(RECEIPT_TEXT_XY) != set(RECEIPT_EXPECTED):
    raise AssertionError("the end view's receipt dimensions are not the spec's")
REWORK_ITEM = f"[2] {feed_nut.BOM_DESCRIPTION}"
SOURCE_PROPERTIES = (
    "Number",
    "Material Specification",
    "Finish",
    "Supplier",
    "Supplier SKUs",
)


def _overlaps(box: tuple[float, ...], other: tuple[float, ...]) -> bool:
    return (
        box[0] < other[2]
        and other[0] < box[2]
        and box[1] < other[3]
        and other[1] < box[3]
    )


def _inside_sheet(box: tuple[float, ...]) -> bool:
    """Inside the border and clear of the title block."""
    return (
        box[0] >= BORDER[0]
        and box[1] >= BORDER[1]
        and box[2] <= BORDER[2]
        and box[3] <= BORDER[3]
        and not _overlaps(box, TITLE_BLOCK)
    )


def _outline(view: Any, label: str) -> tuple[float, float, float, float]:
    box = tuple(float(value) for value in (view.GetOutline() or ()))
    if len(box) != 4 or not all(map(math.isfinite, box)):
        raise RuntimeError(f"{label}: invalid view outline {box!r}")
    return box


def _require_detail_bounds(view: Any, detail: EndDetail) -> None:
    """Read the settled native frame; an earlier transient outline is no proof."""
    box = _outline(view, f"detail {detail.label}")
    if not _inside_sheet(box):
        raise RuntimeError(f"detail {detail.label} leaves the drawable sheet: {box!r}")
    centre = ((box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0)
    if max(abs(centre[i] - detail.centre[i]) for i in (0, 1)) > DETAIL_SETTLE_M:
        raise RuntimeError(f"detail {detail.label} moved from its reserved centre: {box!r}")


def _center_view(
    draw: Any,
    view: Any,
    center: tuple[float, float],
    label: str,
) -> None:
    """Center the native frame without replacing its strict outline guard."""
    view = _early_bound(view, "IView")
    box = position = target = None
    phase = "read initial bounds"
    failure = None
    try:
        box = _outline(view, label)
        phase = "read view position"
        position = tuple(float(value) for value in view.Position)
        if len(position) != 2 or not all(map(math.isfinite, position)):
            raise RuntimeError(f"{label}: invalid view position {position!r}")
        target = [
            position[0] + center[0] - (box[0] + box[2]) / 2,
            position[1] + center[1] - (box[1] + box[3]) / 2,
        ]
        phase = "set view position"
        if not view.SetViewPosition(double_array(target), False):
            raise RuntimeError(f"{label}: failed to position the view")
        draw.EditRebuild3()
        phase = "read centered bounds"
        box = _outline(view, label)
        phase = "check native frame center"
        if (
            abs((box[0] + box[2]) / 2 - center[0]) > 1e-6
            or abs((box[1] + box[3]) / 2 - center[1]) > 1e-6
        ):
            raise RuntimeError(f"{label}: view failed to centre: {box!r}")
        phase = "check native sheet outline"
        if not _inside_sheet(box):
            raise RuntimeError(
                f"{label}: view leaves the drawable sheet: {box!r}"
            )
    except BaseException as error:
        failure = error
        raise
    finally:
        if failure is not None:
            actual_center = (
                None if box is None else ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)
            )
            _telemetry.info(
                f"{label}: centering phase={phase!r}; native_outline_m={box!r}; "
                f"initial_position_m={position!r}; "
                f"actual_center_m={actual_center!r}; "
                f"requested_center_m={center!r}; target_position_m={target!r}; "
                f"failure={failure!r}"
            )


def _turn_view(adapter: Any, view: Any, angle: float, label: str) -> None:
    """Turn a placed view by a native angle and prove it held."""
    native = _early_bound(view, "IView")
    native.Angle = angle
    if abs(math.remainder(float(native.Angle) - angle, 2.0 * math.pi)) > 1e-9:
        raise RuntimeError(f"failed to turn the {label}")
    rebuild_drawing(adapter, label=f"turn {label}")


def _axis_point(
    station_mm: float, radius_mm: float = 0.0, clock_deg: float = 0.0
) -> tuple[float, float, float]:
    """Model metres: ``radius_mm`` out from the axis at ``station_mm``, at
    ``clock_deg`` from +X toward +Z (the part's clock, as the builder's)."""
    clock = math.radians(clock_deg)
    return (
        radius_mm * math.cos(clock) / 1000.0,
        station_mm / 1000.0,
        radius_mm * math.sin(clock) / 1000.0,
    )


def _settle_view_point(
    adapter: Any,
    view: Any,
    point: tuple[float, float, float],
    target: tuple[float, float],
    *,
    label: str,
) -> None:
    """Stand a model point of a view on its layout point: a section's outline
    is no measure of its ink (draw_dt_cone_gear_shaft._section_face), so the
    point is projected and the view moved by the error."""
    bound = _early_bound(view, "IView")
    for _attempt in range(3):
        (landed,) = model_points_in_view(adapter, view, (point,), label=label)
        error = (target[0] - landed[0], target[1] - landed[1])
        if max(abs(error[0]), abs(error[1])) < SECTION_SETTLE_M:
            return
        position = tuple(float(value) for value in bound.Position)
        moved = [position[0] + error[0], position[1] + error[1]]
        if not bound.SetViewPosition(double_array(moved), False):
            raise RuntimeError(f"{label}: failed to position the view")
        rebuild_drawing(adapter, label=f"centre {label}")
    raise RuntimeError(f"{label} stayed at {landed}, not {target}")


def _cut_endpoints(
    adapter: Any, main: Any, section: ClockSection
) -> tuple[tuple[float, float], tuple[float, float]]:
    """The cutting line's sheet endpoints across the screw, bottom first."""
    reach_mm = SECTION_REACH * 1000.0 * SHEET_SCALE[1] / SHEET_SCALE[0]
    first, second = model_points_in_view(
        adapter,
        main,
        (_axis_point(section.cut_mm, -reach_mm), _axis_point(section.cut_mm, reach_mm)),
        label=f"section {section.label} cutting line",
        names=("one end", "other end"),
    )
    return (first, second) if first[1] < second[1] else (second, first)


def _looks_far(adapter: Any, view: Any, section: ClockSection) -> bool:
    """Whether the section looks along model +Y. Model +X and +Z land on the
    sheet as ``x`` and ``z``; X x Z is -Y, so a counter-clockwise turn from
    ``x`` to ``z`` puts -Y toward the reader: the view looks along +Y."""
    origin, along_x, along_z = model_points_in_view(
        adapter,
        view,
        (
            _axis_point(section.cut_mm),
            _axis_point(section.cut_mm, 1.0, 0.0),
            _axis_point(section.cut_mm, 1.0, 90.0),
        ),
        label=f"section {section.label} frame",
        names=("axis", "+X", "+Z"),
    )
    x = (along_x[0] - origin[0], along_x[1] - origin[1])
    z = (along_z[0] - origin[0], along_z[1] - origin[1])
    turn = x[0] * z[1] - x[1] * z[0]
    if abs(turn) < 1e-9:
        raise RuntimeError(f"section {section.label} does not look along the axis")
    return turn > 0.0


def _prepare_section(adapter: Any, view: Any, section: ClockSection) -> None:
    """Keep only the cut face, at the section's own scale
    (draw_dt_cone_gear_shaft._prepare_d_section), looking the way the layout
    wants (the reversed-cut readback of draw_fr_nameplate)."""
    bound = _early_bound(view, "IView")
    bound.UseParentScale = False
    bound.UseSheetScale = 0
    bound.ScaleRatio = double_array([float(SECTION_SCALE[0]), float(SECTION_SCALE[1])])
    cut = _early_bound(bound.GetSection(), "IDrSection")
    # R2026x declares SetDisplayOnlySurfaceCut as a void setter; only its
    # dedicated bool getter may be truth-tested.
    cut.SetDisplayOnlySurfaceCut(True)
    rebuild_drawing(adapter, label=f"section {section.label} cut face and scale")
    ratio = tuple(float(value) for value in bound.ScaleRatio)
    if (
        bool(bound.UseParentScale)
        or int(bound.UseSheetScale) != 0
        or not math.isclose(ratio[0] / ratio[1], SECTION_SCALE[0] / SECTION_SCALE[1])
    ):
        raise RuntimeError(f"section {section.label} scale did not persist: {ratio}")
    if not bool(cut.GetDisplayOnlySurfaceCut()):
        raise RuntimeError(f"section {section.label} kept geometry beyond the cut")
    if _looks_far(adapter, view, section) != section.looks_far:
        reversed_cut = not bool(cut.GetReversedCutDirection())
        cut.SetReversedCutDirection(reversed_cut)
        rebuild_drawing(adapter, label=f"section {section.label} cut direction")
        if bool(cut.GetReversedCutDirection()) != reversed_cut:
            raise RuntimeError(f"section {section.label} cut direction did not persist")
        if _looks_far(adapter, view, section) != section.looks_far:
            raise RuntimeError(f"section {section.label} would not turn to the layout")


def _trim_centre_mark(adapter: Any, view: Any, section: ClockSection) -> None:
    """Keep the section's centre mark, if SolidWorks gave it one, as a small
    cross (draw_dt_cone_gear_shaft._trim_centre_mark): its size is model
    length, so the arm is divided by the section's scale."""
    label = f"section {section.label} centre mark"
    marks = tuple(
        _early_bound(view, "IView").GetAnnotationsByType(_CENTER_MARK_ANNOTATION) or ()
    )
    if not marks:
        _telemetry.info(f"{label}: none drawn")
        return
    if len(marks) != 1:
        raise RuntimeError(f"expected at most one {label}, found {len(marks)}")
    annotation = _early_bound(marks[0], "IAnnotation")
    mark = _early_bound(annotation.GetSpecificAnnotation(), "ICenterMark")
    mark.UseDocDisplaySettings = False
    mark.ShowLines = False
    mark.Size = CENTRE_MARK_ARM * SECTION_SCALE[1] / SECTION_SCALE[0]
    rebuild_drawing(adapter, label=f"trim {label}")
    if bool(mark.UseDocDisplaySettings) or bool(mark.ShowLines):
        raise RuntimeError(f"{label} kept its document display or its extended lines")


def caption_without_scale(linked_text: str) -> str:
    """A section caption's linked fields with its scale line removed: the label
    line (``<VLNAME>`` and ``<VLLABEL>``) alone (draw_pd_transgear_disc_hub's
    recipe). Any other field layout fails loud rather than print the scale."""
    lines = [line for line in linked_text.replace("\r\n", "\n").split("\n") if line.strip()]
    scale_lines = [line for line in lines if "<VLSCALE" in line]
    kept = [line for line in lines if "<VLSCALE" not in line]
    if (
        len(scale_lines) != 1
        or len(kept) != 1
        or "<VLNAME>" not in kept[0]
        or "<VLLABEL>" not in kept[0]
    ):
        raise RuntimeError(f"caption scale line is not separable: {linked_text!r}")
    return kept[0]


def _place_view_caption(
    adapter: Any,
    view: Any,
    target: tuple[float, float],
    *,
    label: str,
    sheet_scale: tuple[float, float],
    scale_shown: bool = True,
) -> None:
    """Move a view's native caption so its box's top centre lands on
    ``target``, its linked fields intact (draw_dt_cone_gear_shaft's
    ``_place_view_caption``: the move is measured by ``INote.GetExtent``, the
    sheet's ``sheet_scale`` pinned first so finalization cannot move it
    after). A view drawn at the sheet's own scale passes ``scale_shown=False``:
    its caption drops the scale line, which would restate the title block
    (rule 9; SolidWorks links one for a section given its own ratio)."""
    ddoc = _early_bound(adapter.currentModel, "IDrawingDoc")
    sheet = _early_bound(ddoc.GetCurrentSheet(), "ISheet")
    if not sheet.SetScale(*sheet_scale, False, False):
        raise RuntimeError(f"cannot pin sheet scale before {label} placement")
    native_view = _early_bound(view, "IView")
    notes = tuple(_read_member(native_view, "GetNotes") or ())
    if len(notes) != 1:
        raise RuntimeError(f"expected one native {label}, found {len(notes)} notes")
    note = _early_bound(notes[0], "INote")
    linked = str(note.PropertyLinkedText or "")
    if not linked:
        raise RuntimeError(f"{label} carries no linked view fields")
    if not scale_shown:
        ratio = tuple(float(value) for value in native_view.ScaleRatio)
        if not math.isclose(ratio[0] / ratio[1], sheet_scale[0] / sheet_scale[1]):
            raise RuntimeError(f"{label}: view scale {ratio} is not the sheet's {sheet_scale}")
        if "<VLSCALE" in linked:
            linked = caption_without_scale(linked)
            note.PropertyLinkedText = linked
            rebuild_drawing(adapter, label=f"{label} without scale")
            if str(note.PropertyLinkedText or "") != linked:
                raise RuntimeError(f"{label} kept its scale line")
    annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
    for _attempt in range(4):
        extent = tuple(float(value) for value in note.GetExtent())
        box = (extent[0], extent[1], extent[3], extent[4])
        error = (target[0] - (box[0] + box[2]) / 2.0, target[1] - box[3])
        if max(abs(error[0]), abs(error[1])) < CAPTION_SETTLE_M:
            break
        x, y, z = (float(value) for value in annotation.GetPosition())
        if not annotation.SetPosition2(x + error[0], y + error[1], z):
            raise RuntimeError(f"failed to move the {label}")
        rebuild_drawing(adapter, label=f"place {label}")
    else:
        raise RuntimeError(
            f"{label} stayed at {box}, its top centre requested at {target}"
        )
    if str(note.PropertyLinkedText or "") != linked:
        raise RuntimeError(f"{label} lost its linked view fields")


def _offset_angle_text(
    adapter: Any,
    annotations: list[Any],
    name: str,
    arc_xy: tuple[float, float],
    text_xy: tuple[float, float],
) -> None:
    """Keep the angle's arc at ``arc_xy`` and move only its text to
    ``text_xy`` on a leader (draw_ch_rocker_arm_tl_trammel_pivot_point's
    ``_place_tip_angle``), each position read back."""
    matches = [item for item in annotations if dimension_name(adapter, item) == name]
    if len(matches) != 1:
        raise RuntimeError(f"section needs one native {name}, got {len(matches)}")
    annotation = _early_bound(matches[0], "IAnnotation")
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    # An inherited offset would move only the text, leaving the arc behind.
    display.OffsetText = False
    if bool(display.OffsetText):
        raise RuntimeError(f"{name} text offset could not be reset")
    if not annotation.SetPosition2(*arc_xy, 0.0):
        raise RuntimeError(f"failed to position the {name} arc")
    _require_position(annotation, arc_xy, f"{name} arc")
    offset_dimension_text(adapter, [annotation], {name: text_xy})
    if not bool(display.OffsetText):
        raise RuntimeError(f"{name} text did not stay offset")
    _require_position(annotation, text_xy, f"{name} text")


def _require_position(annotation: Any, target: tuple[float, float], label: str) -> None:
    position = annotation.GetPosition()
    if (
        not position
        or math.dist((float(position[0]), float(position[1])), target) > 1e-5
    ):
        raise RuntimeError(f"{label} did not persist: {position!r}")


@_telemetry.traced("drawing.clock_sections")
def _add_clock_sections(adapter: Any, main: Any) -> list[Any]:
    """Cut each KP08 station across its two flats and print its clock flat's
    across-flat and angle from clock 0 in the section, its centre mark a
    cross and its caption hung under its lowest ink. Returns the sections'
    dimension annotations; ``curate_view_dimensions`` fails the build if one
    does not arrive."""
    annotations: list[Any] = []
    clock = KP08_SET_SCREW_SPACING_DEG
    for section in CLOCK_SECTIONS:
        start, end = _cut_endpoints(adapter, main, section)
        if not section.looks_far:
            start, end = end, start
        view = create_section_view(
            adapter,
            main,
            line_start=start,
            line_end=end,
            view_xy=section.centre,
            section_label=section.label,
            scale=SECTION_SCALE,
            partial=False,
            label=f"{section.flat} clock flat section",
        )
        _prepare_section(adapter, view, section)
        # Precision display, not draft: the hidden-lines-removed transition is
        # a real mode change (draw_fr_nameplate's section A-A).
        set_hidden_lines_removed(adapter, view)
        _settle_view_point(
            adapter,
            view,
            _axis_point(section.cut_mm),
            section.centre,
            label=f"section {section.label} axis",
        )
        angle = f"{section.flat}ClockAngle"
        af_text, arc, angle_text, *extension_ends = model_points_in_view(
            adapter,
            view,
            (
                _axis_point(section.cut_mm, CLOCK_AF_TEXT_RADIUS_MM, clock + 90.0),
                _axis_point(section.cut_mm, CLOCK_ANGLE_ARC_RADIUS_MM, clock / 2.0),
                _axis_point(section.cut_mm, CLOCK_ANGLE_TEXT_RADIUS_MM, clock / 2.0),
                _axis_point(section.cut_mm, CLOCK_ANGLE_ARC_RADIUS_MM, 0.0),
                _axis_point(section.cut_mm, CLOCK_ANGLE_ARC_RADIUS_MM, clock),
            ),
            label=f"section {section.label} texts",
            names=("across-flat", "angle arc", "angle text", "clock 0", "clock"),
        )
        keep = {f"{section.flat}ClockAF": af_text, angle: arc}
        view_annotations = curate_view_dimensions(
            adapter,
            view,
            keep=keep,
            view_label=f"section {section.label}",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        )
        _offset_angle_text(adapter, view_annotations, angle, arc, angle_text)
        annotations += view_annotations
        _trim_centre_mark(adapter, view, section)
        face_half = MAJOR_DIA / 2000.0 * SECTION_SCALE[0] / SECTION_SCALE[1]
        # Under the face, both texts and the angle's extension lines.
        lowest = min(
            section.centre[1] - face_half,
            af_text[1] - TEXT_HALF_HEIGHT,
            angle_text[1] - TEXT_HALF_HEIGHT,
            *(end[1] - EXTENSION_OVERSHOOT for end in extension_ends),
        )
        _place_view_caption(
            adapter,
            view,
            (section.centre[0], lowest - SECTION_CAPTION_GAP),
            label=f"section {section.label} caption",
            sheet_scale=SHEET_SCALE,
        )
    return annotations


def _sketch_fence(adapter: Any, main: Any, detail: EndDetail) -> Any:
    """Sketch the detail's fence in the main view's own sketch space: the
    model points go to the sheet, then through the sketch transform
    (draw_dt_cone_swing_platform's ``_create_detail_view``, the path
    ``create_section_view`` takes for the cutting lines). Returns the circle."""
    draw = adapter.currentModel
    centre, rim = model_points_in_view(
        adapter,
        main,
        (
            _axis_point(detail.centre_mm),
            _axis_point(detail.centre_mm + detail.radius_mm),
        ),
        label=f"detail {detail.label} fence",
        names=("centre", "rim"),
    )
    sketch = _early_bound(_early_bound(main, "IView").GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    points = []
    for x, y in (centre, rim):
        point = _early_bound(
            utility.CreatePoint(double_array([float(x), float(y), 0.0])), "IMathPoint"
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
        raise RuntimeError(f"failed to sketch detail {detail.label}'s fence")
    return circle


def _require_detail_orientation(adapter: Any, view: Any, detail: EndDetail) -> None:
    """The detail's texts are laid out for the main view's turn: model +Y to
    sheet right and +X (clock 0) to sheet down, at the detail's scale."""
    origin, along_y, along_x = model_points_in_view(
        adapter,
        view,
        (
            _axis_point(detail.centre_mm),
            _axis_point(detail.centre_mm + 1.0),
            _axis_point(detail.centre_mm, 1.0, 0.0),
        ),
        label=f"detail {detail.label} frame",
        names=("centre", "+Y", "+X"),
    )
    step = _DETAIL_PER_MODEL_MM
    turned = (
        along_y[0] - origin[0] - step,
        along_y[1] - origin[1],
        along_x[0] - origin[0],
        along_x[1] - origin[1] + step,
    )
    if max(map(abs, turned)) > DETAIL_ORIENTATION_TOL:
        raise RuntimeError(
            f"detail {detail.label} does not run as the main view: +Y at "
            f"{along_y}, +X at {along_x}, centre {origin}"
        )


def _place_detail_letter(adapter: Any, main: Any, detail: EndDetail) -> None:
    """Stand the fence's letter on the main view at ``detail.letter``, off the
    screw and the other annotations (draw_ch_pivot_shaft's letter)."""
    circles = [
        _early_bound(circle, "IDetailCircle")
        for circle in (
            _read_member(_early_bound(main, "IView"), "GetDetailCircles") or ()
        )
    ]
    matches = [circle for circle in circles if str(circle.GetLabel()) == detail.label]
    if len(matches) != 1:
        raise RuntimeError(
            f"expected one detail circle {detail.label} on the main view, "
            f"found {len(matches)} of {len(circles)}"
        )
    matches[0].SetLabelPosition(*detail.letter)
    rebuild_drawing(adapter, label=f"detail {detail.label} letter")
    letter = tuple(float(value) for value in matches[0].GetLabelPosition())
    if len(letter) != 2 or math.dist(letter, detail.letter) > 1e-6:
        raise RuntimeError(f"detail {detail.label}'s letter did not persist: {letter}")


def _create_end_detail(adapter: Any, main: Any, detail: EndDetail) -> Any:
    """A native 3:1 detail of the main view round ``detail``'s fence, its
    fence centre on ``detail.centre``. A fresh detail's transform lags its
    ink (``_drawing_detail_projection``), so it is placed by its outline (the
    fence's square) and its projection settled before anything reads it."""
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    if not ddoc.ActivateView(view_name(adapter, main)):
        raise RuntimeError(f"failed to activate detail {detail.label}'s parent")
    draw.ClearSelection2(True)
    circle = _sketch_fence(adapter, main, detail)
    selection = _early_bound(draw.SelectionManager, "ISelectionMgr").CreateSelectData()
    selection.View = main
    segment = _sw_type_info.early_bound_or_flag(circle, "ISketchSegment", "Select4")
    if not segment.Select4(False, selection):
        raise RuntimeError(f"failed to select detail {detail.label}'s fence")
    view = ddoc.CreateDetailViewAt4(
        *detail.centre,
        0.0,
        0,  # swDetViewSTANDARD
        float(DETAIL_SCALE[0]),
        float(DETAIL_SCALE[1]),
        detail.label,
        1,  # swDetCircleCIRCLE
        True,  # FullOutline
        False,  # JaggedOutline
        False,  # NoOutline
        5,
    )
    draw.ClearSelection2(True)
    if view is None:
        raise RuntimeError(f"CreateDetailViewAt4 returned no detail {detail.label}")
    view = _sw_type_info.early_bound_or_flag(
        view, "IView", "SetViewPosition", "Position"
    )
    rebuild_drawing(adapter, label=f"create detail {detail.label}")
    ratio = tuple(float(value) for value in view.ScaleRatio)
    if not math.isclose(ratio[0] / ratio[1], DETAIL_SCALE[0] / DETAIL_SCALE[1]):
        raise RuntimeError(f"detail {detail.label} scale {ratio}, not {DETAIL_SCALE}")
    for _attempt in range(4):
        box = _outline(view, f"detail {detail.label}")
        landed = ((box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0)
        error = (detail.centre[0] - landed[0], detail.centre[1] - landed[1])
        if max(abs(error[0]), abs(error[1])) < DETAIL_SETTLE_M:
            break
        position = tuple(float(value) for value in view.Position)
        target = [position[0] + error[0], position[1] + error[1]]
        if not view.SetViewPosition(double_array(target), False):
            raise RuntimeError(f"failed to position detail {detail.label}")
        rebuild_drawing(adapter, label=f"place detail {detail.label}")
    else:
        raise RuntimeError(
            f"detail {detail.label}'s outline centre stayed at {landed}, "
            f"not {detail.centre}"
        )
    if not _inside_sheet(box):
        raise RuntimeError(f"detail {detail.label} leaves the drawable sheet: {box!r}")
    settle_detail_projection(
        adapter,
        view,
        _axis_point(detail.centre_mm),
        ink_xy=landed,
        tolerance_xy=(DETAIL_SETTLE_M * 2.5, DETAIL_SETTLE_M * 2.5),
        label=f"detail {detail.label}",
    )
    _require_detail_orientation(adapter, view, detail)
    _require_detail_bounds(view, detail)
    return view


@_telemetry.traced("drawing.end_details")
def _add_end_details(adapter: Any, main: Any) -> tuple[list[Any], list[Any]]:
    """Detail each flat station at 3:1, where the main view's 0.36 mm flats
    read: each detail's dimensions, its letter on the main view and its
    caption under the row of texts. Returns annotations and retained native
    views for final containment checks; ``curate_view_dimensions`` refuses if
    any dimension does not arrive."""
    annotations: list[Any] = []
    views: list[Any] = []
    for detail in END_DETAILS:
        view = _create_end_detail(adapter, main, detail)
        views.append(view)
        set_hidden_lines_removed(adapter, view)
        if detail.keep:
            annotations += curate_view_dimensions(
                adapter,
                view,
                keep=detail.keep,
                view_label=f"detail {detail.label}",
                dimensions_by_feature=DRAWING_DIMENSIONS,
            )
        _place_detail_letter(adapter, main, detail)
        _place_view_caption(
            adapter,
            view,
            (detail.centre[0], DETAIL_CAPTION_TOP),
            label=f"detail {detail.label} caption",
            sheet_scale=SHEET_SCALE,
        )
    return annotations, views


# --- Shared member-sheet plumbing -------------------------------------------------


def _activate(document: Any, sheet_name: str) -> Any:
    if not document.ActivateSheet(sheet_name):
        raise RuntimeError(f"failed to activate sheet {sheet_name!r}")
    return _early_bound(document.GetCurrentSheet(), "ISheet")


def _source_properties(model: Any) -> dict[str, str]:
    return read_required_properties(
        model, SOURCE_PROPERTIES, required=SOURCE_PROPERTIES
    )


def _member_title_block(
    adapter: Any, draw: Any, properties: Mapping[str, str]
) -> tuple[list[tuple[Any, str, str]], Callable[[], None]]:
    """Link this sheet's MATERIAL/FINISH cells as sheet 1's, then fit its
    Name, Material and DWG. NO. in their native cells."""
    title_notes = _purchased_title_block(
        adapter,
        draw,
        material=properties["Material Specification"],
        finish=properties["Finish"],
        material_property="Material Specification",
    )
    _rebuild(draw, phase="member sheet title block")
    return title_notes, fit_purchased_title_block(adapter, spec=SPEC)


def _assert_member_sheet(
    adapter: Any,
    sheet: Any,
    configuration: str,
    view_count: int,
    title_notes: list[tuple[Any, str, str]],
    notes: list[tuple[Any, str, str, tuple[float, ...]]],
    *,
    label: str,
) -> None:
    """Every view on the active member sheet shows the member from this
    source; the title block and notes resolve inside their cells."""
    views = tuple(iter_views(adapter))
    if len(views) != view_count:
        raise RuntimeError(f"{label}: expected {view_count} views, found {len(views)}")
    for view in views:
        if (
            str(view.ReferencedConfiguration) != configuration
            or Path(view.GetReferencedModelName()).resolve() != SOURCE.resolve()
        ):
            raise RuntimeError(f"{label}: a view left the {configuration} member")
    template = DRAWING_TEMPLATES[SPEC.layout]
    region = sheet_drawable_region(
        adapter, sheet, width=template.width_m, height=template.height_m
    )
    border = (region.xmin, region.ymin, region.xmax, region.ymax)
    for note, linked_text, resolved_text in title_notes:
        if (
            note.PropertyLinkedText != linked_text
            or note.GetText().replace("\r\n", "\n") != resolved_text
        ):
            raise RuntimeError(f"{label}: title-block link did not resolve: {linked_text!r}")
    for note, linked_text, resolved_text, cell in notes:
        if (
            note.PropertyLinkedText != linked_text
            or note.GetText().replace("\r\n", "\n") != resolved_text
        ):
            raise RuntimeError(f"{label}: note did not resolve: {linked_text!r}")
        box = _box(note.GetExtent(), label=linked_text, kind="note")
        if not _inside(box, cell) or not _inside(box, border):
            raise RuntimeError(
                f"{label}: note leaves its reserved space/border: {linked_text!r}: {box!r}"
            )


# --- Sheet 2 -----------------------------------------------------------------------


@_telemetry.traced("drawing.leadscrew_sheet")
def _append_leadscrew_sheet(adapter: Any) -> tuple[Callable[[], None], ...]:
    """Author LEADSCREW: the LeadScrew member's cut length and flats."""
    draw = adapter.currentModel
    document = _early_bound(draw, "IDrawingDoc")
    sheet = _activate(document, LEADSCREW_SHEET_NAME)
    if not sheet.SetScale(*SHEET_SCALE, False, False):
        raise RuntimeError("cannot pin the LEADSCREW sheet's scale")
    main = _early_bound(
        place_view(adapter, str(SOURCE), "*Front", *MAIN_CENTER, scale=SHEET_SCALE),
        "IView",
    )
    configure_reference_views(adapter, leadscrew.CONFIGURATION, [main])
    _turn_view(adapter, main, MAIN_VIEW_ANGLE, "leadscrew view axis-horizontal")
    _center_view(draw, main, MAIN_CENTER, "leadscrew view")
    iso = _early_bound(
        place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE),
        "IView",
    )
    configure_reference_views(adapter, leadscrew.CONFIGURATION, [iso])
    _center_view(draw, iso, ISO_CENTER, "leadscrew isometric")
    sheet.CustomPropertyView = view_name(adapter, main)
    properties = _source_properties(_early_bound(main.ReferencedDocument, "IModelDoc2"))
    for view in (main, iso):
        set_hidden_lines_removed(adapter, view)
    annotations = curate_view_dimensions(
        adapter,
        main,
        keep=MAIN_KEEP,
        view_label="cut length and flats",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    annotations += _add_clock_sections(adapter, main)
    detail_annotations, detail_views = _add_end_details(adapter, main)
    annotations += detail_annotations
    verify_machining_controls(
        annotations,
        expected=EXPECTED_CONTROLS,
        tolerance_types=DIMENSION_TOLERANCE_TYPES,
        precision=DIMENSION_PRECISION,
    )
    set_dimension_callouts(adapter, annotations, FLAT_CALLOUTS)
    add_view_centerline(adapter, main, face_xy=CENTERLINE_PICK, label="leadscrew axis")
    note = add_note(adapter, NOTES, *NOTES_XY)
    if note is None:
        raise RuntimeError("failed to add the leadscrew note block")
    resolved = "\n".join(
        (
            f"ITEM: {LEADSCREW_ITEM}",
            f"SUPPLIER: {properties['Supplier']}",
            f"SKU: {properties['Supplier SKUs']}",
        )
    )
    printed = str(_early_bound(note, "INote").GetText() or "")
    if printed.replace("\r\n", "\n").replace("\r", "\n") != resolved:
        raise RuntimeError(f"leadscrew note block did not resolve: {printed!r}")
    thread = add_leader_note(
        adapter,
        THREAD_CALLOUT,
        text_xy=THREAD_CALLOUT_XY,
        attach_xy=THREAD_LEADER_TIP,
        label="leadscrew thread callout",
        view=main,
    )
    callout = str(_early_bound(thread, "INote").GetText() or "")
    if callout.replace("\r\n", "\n").replace("\r", "\n") != THREAD_CALLOUT:
        raise RuntimeError(f"leadscrew thread callout did not print: {callout!r}")
    title_notes, title_fit = _member_title_block(adapter, draw, properties)
    view_count = 2 + len(CLOCK_SECTIONS) + len(END_DETAILS)

    def settled() -> None:
        current = _activate(document, LEADSCREW_SHEET_NAME)
        _assert_member_sheet(
            adapter,
            current,
            leadscrew.CONFIGURATION,
            view_count,
            title_notes,
            [],
            label=LEADSCREW_SHEET_NAME,
        )
        for detail, view in zip(END_DETAILS, detail_views, strict=True):
            _require_detail_bounds(view, detail)
        verify_machining_controls(
            annotations,
            expected=EXPECTED_CONTROLS,
            tolerance_types=DIMENSION_TOLERANCE_TYPES,
            precision=DIMENSION_PRECISION,
        )
        title_fit()

    settled()
    return (settled,)


# --- Sheet 3 -----------------------------------------------------------------------


def _nut_point(radius_mm: float, station_mm: float) -> tuple[float, float, float]:
    """Model metres: ``radius_mm`` toward +X at ``station_mm`` from the seat
    face, in the Front plane (section F-F's)."""
    return (radius_mm / 1000.0, station_mm / 1000.0, 0.0)


def _require_axis_horizontal(adapter: Any, view: Any, *, label: str) -> None:
    """The section lies axis-horizontal at the sheet's scale (rule 11)."""
    origin, along = model_points_in_view(
        adapter,
        view,
        (_nut_point(0.0, 0.0), _nut_point(0.0, 1.0)),
        label=f"{label} axis",
        names=("seat face", "1 mm up the axis"),
    )
    step = (along[0] - origin[0], along[1] - origin[1])
    if (
        abs(step[1]) > DETAIL_ORIENTATION_TOL
        or abs(abs(step[0]) - _REWORK_PER_MODEL_MM) > DETAIL_ORIENTATION_TOL
    ):
        raise RuntimeError(f"{label} does not lie axis-horizontal: {step!r}")


def _assert_callouts(
    adapter: Any, annotations: list[Any], callouts: Mapping[str, tuple[str, str]]
) -> None:
    """Each banded control still prints its mate in its own callout lane."""
    printed = {}
    for raw in annotations:
        annotation = _sw_type_info.early_bound_or_flag(
            raw, "IAnnotation", "GetSpecificAnnotation"
        )
        name = dimension_name(adapter, annotation)
        if name not in callouts:
            continue
        lane, text = callouts[name]
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        actual = str(display.GetText(_CALLOUT_TEXT_PARTS[lane]) or "")
        printed[name] = actual.replace("\r\n", "\n").replace("\r", "\n")
        if printed[name] != text:
            raise RuntimeError(f"{name}: callout reads {printed[name]!r}, not {text!r}")
    if set(printed) != set(callouts):
        raise RuntimeError(f"callouts missing: {sorted(set(callouts) - set(printed))}")


def _set_callouts(
    adapter: Any, annotations: list[Any], callouts: Mapping[str, tuple[str, str]]
) -> None:
    for lane in ("below", "above"):
        texts = {name: text for name, (where, text) in callouts.items() if where == lane}
        if texts:
            set_dimension_callouts(adapter, annotations, texts, location=lane)
    _assert_callouts(adapter, annotations, callouts)


def _countersink_display(adapter: Any, annotations: list[Any]) -> Any:
    matches = [
        annotation
        for annotation in annotations
        if dimension_name(
            adapter,
            _sw_type_info.early_bound_or_flag(
                annotation, "IAnnotation", "GetSpecificAnnotation"
            ),
        )
        == "CskDia"
    ]
    if len(matches) != 1:
        raise RuntimeError(f"section F-F needs one CskDia, got {len(matches)}")
    annotation = _early_bound(matches[0], "IAnnotation")
    return _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")


def _assert_countersink_text(adapter: Any, annotations: list[Any]) -> None:
    """The countersink's size line reads "4X ⌵ Ø4.76/4.50 X 82°": the
    model's symbol prefix and this sheet's angle suffix (rule 26)."""
    display = _countersink_display(adapter, annotations)
    printed = (str(display.GetText(1) or ""), str(display.GetText(2) or ""))
    if printed != (feed_nut.CSK_PREFIX, feed_nut.CSK_SUFFIX):
        raise RuntimeError(f"CskDia prints prefix/suffix {printed!r}")


def _set_countersink_angle(adapter: Any, annotations: list[Any]) -> None:
    display = _countersink_display(adapter, annotations)
    display.SetText(2, feed_nut.CSK_SUFFIX)  # swDimensionTextSuffix
    rebuild_drawing(adapter, label="countersink angle suffix")
    _assert_countersink_text(adapter, annotations)


# The sheet's leadered dimension callouts, each read back as SolidWorks draws
# it: the countersink's and the faced length's in section F-F, the receipt
# limits' on the end view.
LEADERED = ("CskDia", "FacedLength", *RECEIPT_TEXT_XY)


def _named(adapter: Any, annotations: list[Any]) -> dict[str, Any]:
    named: dict[str, Any] = {}
    for annotation in annotations:
        name = dimension_name(
            adapter,
            _sw_type_info.early_bound_or_flag(annotation, "IAnnotation", "GetSpecificAnnotation"),
        )
        if name in named:
            raise RuntimeError(f"sheet 3 holds two {name} dimensions")
        named[name] = annotation
    return named


def _callout_block(adapter: Any, annotation: Any, label: str) -> tuple[Any, tuple[float, ...]]:
    """A leadered callout's ink and its whole text block: ``callout_ink`` boxes
    the text from its shoulder, and the text positions widen that box to every
    line, so a callout row hung below the shoulder counts
    (draw_dt_cone_gear_shaft's collar recipe)."""
    ink = callout_ink(adapter, annotation, label=label)
    points = dimension_text_points(annotation)
    xs = [ink.text[0], ink.text[2], *(x for x, _y in points)]
    ys = [ink.text[1], ink.text[3], *(y for _x, y in points)]
    return ink, (min(xs), min(ys), max(xs), max(ys))


# A callout's text must not be crossed by a line (run 20261105T023247678Z's
# gating findings): its own dimension, extension or leader lines, or a part
# outline of either view. The outlines are the spec's geometry projected into
# each view; a leader ends ON its shoulder, hence the inset. A callout's own
# line may also END just inside its text: run 20261105T030845448Z's CskDia
# extension line ran 1.0 mm past its dimension line, which the text abuts
# (0.2690 .. 0.3160 at y 0.2012, text from x 0.3150), as run 11 printed
# unflagged. So an own line counts only where it runs more than
# _OWN_LINE_TOUCH_M inside the text; run 11's faced-length line and witness
# ran 27.7 and 8.5 mm.
_TEXT_LINE_INSET = 0.0005
_OWN_LINE_TOUCH_M = 0.0015
# End view: (model centre (x, y, z) mm, radius mm); the countersinks' mouths
# and the holes ring each hole centre.
END_VIEW_CIRCLES_MM = {
    "flange OD": ((0.0, 0.0, 0.0), feed_nut.FLANGE_DIA / 2.0),
    "body": ((0.0, 0.0, 0.0), feed_nut.BODY_DIA / 2.0),
    "bore": ((0.0, 0.0, 0.0), feed_nut.BORE_DIA / 2.0),
    **{
        f"{kind} {index}": ((x, 0.0, z), diameter / 2.0)
        for index, (x, z) in enumerate(feed_nut.HOLE_CENTRES, start=1)
        for kind, diameter in (("hole", feed_nut.HOLE_DIA), ("countersink", feed_nut.CSK_DIA))
    },
}
# Section F-F's outer outline, (radius toward +X, station) mm segments.
_R, _B = feed_nut.FLANGE_DIA / 2.0, feed_nut.BODY_DIA / 2.0
SECTION_OUTLINE_MM = {
    "seat face": ((-_R, 0.0), (_R, 0.0)),
    "body end": ((-_B, feed_nut.LENGTH), (_B, feed_nut.LENGTH)),
    **{
        f"{edge} {side}": ((sign * a, s0), (sign * b, s1))
        for side, sign in (("+X", 1.0), ("-X", -1.0))
        for edge, (a, s0), (b, s1) in (
            ("flange rim", (_R, 0.0), (_R, feed_nut.FLANGE_THICK)),
            ("head face", (_R, feed_nut.FLANGE_THICK), (_B, feed_nut.FLANGE_THICK)),
            ("body", (_B, feed_nut.FLANGE_THICK), (_B, feed_nut.LENGTH)),
        )
    },
}


def _circle_crosses_box(circle: tuple[float, float, float], box: tuple[float, ...]) -> bool:
    cx, cy, radius = circle
    near = math.hypot(min(max(cx, box[0]), box[2]) - cx, min(max(cy, box[1]), box[3]) - cy)
    far = max(math.hypot(x - cx, y - cy) for x in (box[0], box[2]) for y in (box[1], box[3]))
    return near < radius < far


def _length_inside(line: tuple[float, float, float, float], box: tuple[float, ...]) -> float:
    """How far ``line`` runs inside ``box`` (Liang-Barsky clip), sheet metres."""
    x0, y0, x1, y1 = line
    dx, dy = x1 - x0, y1 - y0
    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, x0 - box[0]), (dx, box[2] - x0), (-dy, y0 - box[1]), (dy, box[3] - y0)):
        if p == 0.0:
            if q < 0.0:
                return 0.0
            continue
        t = q / p
        if p < 0.0:
            t0 = max(t0, t)
        else:
            t1 = min(t1, t)
    return max(0.0, t1 - t0) * math.hypot(dx, dy)


def text_crossings(
    box: tuple[float, ...],
    *,
    lines: Mapping[str, tuple[float, float, float, float]],
    circles: Mapping[str, tuple[float, float, float]],
    touch: float = 0.0,
) -> list[str]:
    """Which of ``lines`` ((x0, y0, x1, y1)) and ``circles`` ((cx, cy, r)),
    sheet metres, run through ``box`` shrunk by ``_TEXT_LINE_INSET``; a line
    counts only where it runs more than ``touch`` inside."""
    inset = _TEXT_LINE_INSET
    inner = (box[0] + inset, box[1] + inset, box[2] - inset, box[3] - inset)
    return [
        *(name for name, line in lines.items() if _length_inside(line, inner) > touch),
        *(name for name, circle in circles.items() if _circle_crosses_box(circle, inner)),
    ]


def _rework_outlines(
    adapter: Any, end: Any, section: Any
) -> tuple[dict[str, tuple[float, float, float, float]], dict[str, tuple[float, float, float]]]:
    """Both views' part outlines on the sheet: the section's lines and the
    end view's circles, projected from the spec's geometry."""
    names = tuple(END_VIEW_CIRCLES_MM)
    centres = model_points_in_view(
        adapter,
        end,
        tuple(
            tuple(value / 1000.0 for value in centre)
            for centre, _radius in END_VIEW_CIRCLES_MM.values()
        ),
        label="feed nut end view outline",
        names=names,
    )
    circles = {
        name: (x, y, radius * _REWORK_PER_MODEL_MM)
        for name, (x, y), (_centre, radius) in zip(
            names, centres, END_VIEW_CIRCLES_MM.values(), strict=True
        )
    }
    ends = model_points_in_view(
        adapter,
        section,
        tuple(_nut_point(*point) for segment in SECTION_OUTLINE_MM.values() for point in segment),
        label="section F-F outline",
        names=tuple(
            f"{name} {end}" for name in SECTION_OUTLINE_MM for end in ("start", "end")
        ),
    )
    lines = {
        name: (*ends[2 * index][:2], *ends[2 * index + 1][:2])
        for index, name in enumerate(SECTION_OUTLINE_MM)
    }
    return lines, circles


def view_captions(views: Mapping[str, Any]) -> dict[str, tuple[float, float, float, float]]:
    """Each view's native caption box (``INote.GetExtent``), by view label:
    the notes carrying the linked view-label field (draw_pd_support_bar's
    section caption), so a note the view owns, such as the spigot note on
    section F-F, is not one."""
    captions = {}
    for label, view in views.items():
        notes = [
            _early_bound(raw, "INote")
            for raw in _read_member(_early_bound(view, "IView"), "GetNotes") or ()
        ]
        found = [note for note in notes if "<VLLABEL>" in str(note.PropertyLinkedText or "")]
        for index, note in enumerate(found, start=1):
            name = f"{label} caption" if len(found) == 1 else f"{label} caption {index}"
            captions[name] = _box(note.GetExtent(), label=name, kind="note")
    return captions


def caption_leader_keepouts(
    captions: Mapping[str, tuple[float, float, float, float]],
) -> dict[str, tuple[float, float, float, float]]:
    """The boxes a leader must stay out of: each caption grown by the
    readback's gap, so a leader grazing a letter of it refuses too (run
    20261105T054045952Z's faced-length leader across F-F's second F)."""
    gap = CLEAR_GAP_M
    return {
        name: (box[0] - gap, box[1] - gap, box[2] + gap, box[3] + gap)
        for name, box in captions.items()
    }


def _assert_rework_ink(
    adapter: Any, annotations: list[Any], spigot: Any, end: Any, section: Any
) -> None:
    """Every leadered callout block, the spigot note and each view's caption,
    as SolidWorks draws them, stay inside the sheet's zone frame, off the
    title block and clear of each other; no callout's leader runs through
    another callout's text or within the readback's gap of a view caption;
    and no callout's text is crossed by its own dimension, extension or
    leader lines or by either view's part outline. The note's native extent
    spans its own leader down to the seat face, where the faced length's
    witness starts, so leaders are checked against the callouts' text and the
    captions alone. (No readback shows whether an ABOVE callout printed; its
    one-line guard stands in.)"""
    rebuild_drawing(adapter, label="feed nut rework ink")
    region = sheet_region(adapter)
    named = _named(adapter, annotations)
    missing = sorted(set(LEADERED) - set(named))
    if missing:
        raise RuntimeError(f"sheet 3 is missing its leadered callouts {missing}")
    inks = {}
    boxes = {}
    for name in LEADERED:
        inks[name], boxes[name] = _callout_block(adapter, named[name], f"{name} callout")
    note = _box(_early_bound(spigot, "INote").GetExtent(), label="spigot note", kind="note")
    captions = view_captions({"end view": end, "section F-F": section})
    if "section F-F caption" not in captions:
        raise RuntimeError(f"section F-F's caption did not read back: {sorted(captions)}")
    keepouts = caption_leader_keepouts(captions)
    outline_lines, outline_circles = _rework_outlines(adapter, end, section)
    for name, box in {**boxes, "spigot note": note, **captions}.items():
        require_inside(name, box, region)
        if _overlaps(box, TITLE_BLOCK):
            raise RuntimeError(f"{name} {box!r} runs onto the title block {TITLE_BLOCK!r}")
        others = {other: value for other, value in boxes.items() if other != name}
        if name in captions:
            require_clear(name, box, {**others, "spigot note": note})
            continue
        require_clear(name, box, others)
        if name not in inks:
            continue
        require_leader_clear(inks[name], {**others, **keepouts})
        # Own lines against the shoulder's box, whose lower-left corner the
        # leader ends on, each allowed to end just inside it; outlines against
        # the whole text block.
        own = {
            f"own line {index} {_fmt_line(segment)}": (
                segment.x0, segment.y0, segment.x1, segment.y1,
            )
            for index, segment in enumerate(inks[name].leader)
        }
        crossed = [
            *text_crossings(
                inks[name].text, lines=own, circles={}, touch=_OWN_LINE_TOUCH_M
            ),
            *text_crossings(box, lines=outline_lines, circles=outline_circles),
        ]
        if crossed:
            raise RuntimeError(f"{name} callout text {box!r} is crossed by {crossed}")


def _fmt_line(segment: Any) -> str:
    return f"({segment.x0:.4f}, {segment.y0:.4f}, {segment.x1:.4f}, {segment.y1:.4f})"


def _add_spigot_note(adapter: Any, section: Any) -> tuple[Any, tuple[float, float]]:
    """Name the faced face: a leader to the seat face where the spigot stood."""
    (tip,) = model_points_in_view(
        adapter,
        section,
        (_nut_point(*SPIGOT_TIP_MM),),
        label="section F-F faced seat face",
        names=("spigot footprint on the seat face",),
    )
    # The seat face must face the note: right of its cell, the leader short.
    if not SPIGOT_NOTE_CELL[2] < tip[0] < SPIGOT_NOTE_CELL[2] + 0.015:
        raise RuntimeError(f"section F-F's seat face is not beside its note: {tip!r}")
    if not SPIGOT_NOTE_CELL[1] < tip[1] < REWORK_SECTION_CENTER[1]:
        raise RuntimeError(f"the spigot note's tip left the faced half: {tip!r}")
    note = add_leader_note(
        adapter,
        SPIGOT_NOTE,
        text_xy=SPIGOT_NOTE_XY,
        attach_xy=tip,
        label="feed nut spigot facing",
        view=section,
    )
    _assert_spigot_note(adapter, note, tip)
    return note, tip


def spigot_note_bounds(tip: tuple[float, float]) -> tuple[float, float, float, float]:
    """Where the note's native extent may reach: its text cell, widened to the
    leader's tip. ``INote.GetExtent`` spans the leader too (run
    20261105T002852195Z: (0.1716, 0.1211, 0.2526, 0.1440), the tip at the
    seat face 0.253 and 0.1438), and the leader runs through clear sheet left
    of the seat face."""
    left, bottom, right, top = SPIGOT_NOTE_CELL
    return (
        left,
        min(bottom, tip[1] - _LEADER_TIP_MARGIN),
        max(right, tip[0] + _LEADER_TIP_MARGIN),
        max(top, tip[1] + _LEADER_TIP_MARGIN),
    )


def _assert_spigot_note(adapter: Any, note: Any, tip: tuple[float, float]) -> None:
    native = _early_bound(note, "INote")
    text = str(native.GetText() or "").replace("\r\n", "\n").replace("\r", "\n")
    if text != SPIGOT_NOTE:
        raise RuntimeError(f"spigot facing note reads {text!r}")
    box = _box(native.GetExtent(), label="spigot facing note", kind="note")
    bounds = spigot_note_bounds(tip)
    # The text starts in its cell, and the leader reaches the seat face.
    if (
        not _inside(box, bounds)
        or box[0] > SPIGOT_NOTE_CELL[2]
        or box[2] < tip[0] - _LEADER_TIP_MARGIN
    ):
        raise RuntimeError(
            f"spigot facing note leaves its cell and leader: {box!r}; bounds {bounds!r}"
        )


def _receipt_dimensions(adapter: Any, end: Any) -> list[Any]:
    """Import the receipt limits onto the end view as near-side leadered
    diameters, each naming its mate below its limits (4475311251)."""
    centre, hole = model_points_in_view(
        adapter,
        end,
        (_nut_point(0.0, 0.0), RECEIPT_HOLE_MODEL),
        label="feed nut end view receipt",
        names=("axis", "+Z hole centre"),
    )
    pcd_radius = feed_nut.HOLE_PCD / 2.0 * _REWORK_PER_MODEL_MM
    if (
        abs(hole[0] - centre[0] - pcd_radius) > DETAIL_ORIENTATION_TOL
        or abs(hole[1] - centre[1]) > DETAIL_ORIENTATION_TOL
    ):
        raise RuntimeError(
            f"the end view lays the +Z hole at {hole!r}, not right of its axis {centre!r}"
        )
    shift = (centre[0] - REWORK_END_CENTER[0], centre[1] - REWORK_END_CENTER[1])
    receipt = hidden_sketches.curate_view_dimensions(
        adapter,
        end,
        keep={name: (x + shift[0], y + shift[1]) for name, (x, y) in RECEIPT_TEXT_XY.items()},
        view_label="feed nut end view receipt",
        dimensions_by_feature=feed_nut.DRAWING_DIMENSIONS,
    )
    for annotation in receipt:
        name = dimension_name(
            adapter,
            _sw_type_info.early_bound_or_flag(annotation, "IAnnotation", "GetSpecificAnnotation"),
        )
        set_near_side_diameter(annotation, f"{name} near-side diameter")
    rebuild_drawing(adapter, label="feed nut receipt diameters")
    verify_machining_controls(
        receipt,
        expected=RECEIPT_EXPECTED,
        tolerance_types=feed_nut.DIMENSION_TOLERANCE_TYPES,
        precision=RECEIPT_PRECISION,
    )
    _set_callouts(adapter, receipt, RECEIPT_CALLOUTS)
    return receipt


@_telemetry.traced("drawing.feed_nut_rework_sheet")
def _append_feed_nut_rework_sheet(adapter: Any) -> tuple[Callable[[], None], ...]:
    """Author FEED NUT REWORK: the FeedNut's native flange, countersink and
    faced-length limits in section F-F, cut through the two countersinks on X,
    and its native receipt limits on the end view."""
    draw = adapter.currentModel
    document = _early_bound(draw, "IDrawingDoc")
    sheet = _activate(document, REWORK_SHEET_NAME)
    if not sheet.SetScale(*REWORK_SCALE, False, False):
        raise RuntimeError("cannot pin the FEED NUT REWORK sheet's scale")
    end = _early_bound(
        place_view(adapter, str(SOURCE), "*Top", *REWORK_END_CENTER, scale=REWORK_SCALE),
        "IView",
    )
    configure_reference_views(adapter, feed_nut.CONFIGURATION, [end])
    _turn_view(adapter, end, REWORK_END_ANGLE, "feed nut end view")
    _center_view(draw, end, REWORK_END_CENTER, "feed nut end view")
    set_hidden_lines_removed(adapter, end)
    sheet.CustomPropertyView = view_name(adapter, end)
    source_model = _early_bound(end.ReferencedDocument, "IModelDoc2")
    properties = _source_properties(source_model)
    reach_mm = feed_nut.FLANGE_DIA / 2.0 + REWORK_SECTION_OVERRUN / _REWORK_PER_MODEL_MM
    first, second = model_points_in_view(
        adapter,
        end,
        (_nut_point(-reach_mm, 0.0), _nut_point(reach_mm, 0.0)),
        label="section F-F cutting line",
        names=("-X end", "+X end"),
    )
    if abs(first[0] - second[0]) > DETAIL_ORIENTATION_TOL:
        raise RuntimeError(f"section F-F's cutting line is not vertical: {first}, {second}")
    # FacedLengthReference lies in F-F's cutting plane (Front), saved hidden:
    # the section takes it from the part as it stands when it is cut and
    # selects it through the end view, so F-F is cut and curated while the part
    # shows it (draw_fr_nameplate's recipe). In the end view it stands end-on.
    with hidden_sketches.part_sketches_shown(
        adapter,
        source_model,
        (feed_nut.FACED_LENGTH_SKETCH,),
        label="section F-F faced length",
        base_view=end,
    ):
        section = _early_bound(
            create_section_view(
                adapter,
                end,
                line_start=first,
                line_end=second,
                view_xy=REWORK_SECTION_CENTER,
                section_label=REWORK_SECTION_LABEL,
                scale=(int(REWORK_SCALE[0]), int(REWORK_SCALE[1])),
                partial=False,
                label="feed nut countersink section",
            ),
            "IView",
        )
        set_hidden_lines_removed(adapter, section)
        rebuild_drawing(adapter, label="feed nut section")
        _require_axis_horizontal(adapter, section, label="section F-F")
        _settle_view_point(
            adapter,
            section,
            _nut_point(0.0, feed_nut.LENGTH / 2.0),
            REWORK_SECTION_CENTER,
            label="section F-F axis",
        )
        flange_text, csk_text, faced_line, faced_text = model_points_in_view(
            adapter,
            section,
            (
                _nut_point(*FLANGE_THICK_TEXT_MM),
                _nut_point(*CSK_DIA_TEXT_MM),
                _nut_point(*FACED_LENGTH_LINE_MM),
                _nut_point(*FACED_LENGTH_TEXT_MM),
            ),
            label="section F-F texts",
            names=(
                "flange thickness",
                "countersink diameter",
                "faced length line",
                "faced length text",
            ),
        )
        annotations = hidden_sketches.curate_view_dimensions(
            adapter,
            section,
            keep={"FlangeThick": flange_text, "CskDia": csk_text, "FacedLength": faced_line},
            view_label="section F-F rework",
            dimensions_by_feature=feed_nut.DRAWING_DIMENSIONS,
        )
    offset_dimension_text(adapter, annotations, {"FacedLength": faced_text})
    # Before the spigot note joins the section's notes: the caption must be
    # its one note.
    _place_view_caption(
        adapter,
        section,
        REWORK_CAPTION_TOP,
        label="section F-F caption",
        sheet_scale=REWORK_SCALE,
        scale_shown=False,
    )
    verify_machining_controls(
        annotations,
        expected=REWORK_EXPECTED,
        tolerance_types=feed_nut.DIMENSION_TOLERANCE_TYPES,
        precision=REWORK_PRECISION,
    )
    _set_callouts(adapter, annotations, REWORK_CALLOUTS)
    _set_countersink_angle(adapter, annotations)
    receipt = _receipt_dimensions(adapter, end)
    spigot, spigot_tip = _add_spigot_note(adapter, section)
    note = _literal_note(adapter, REWORK_ITEM, *ITEM_LABEL_XY)
    notes = [(note, REWORK_ITEM, REWORK_ITEM, ITEM_LABEL_CELL)]
    title_notes, title_fit = _member_title_block(adapter, draw, properties)

    def settled() -> None:
        current = _activate(document, REWORK_SHEET_NAME)
        _assert_member_sheet(
            adapter,
            current,
            feed_nut.CONFIGURATION,
            2,
            title_notes,
            notes,
            label=REWORK_SHEET_NAME,
        )
        _require_axis_horizontal(adapter, section, label="section F-F")
        verify_machining_controls(
            annotations,
            expected=REWORK_EXPECTED,
            tolerance_types=feed_nut.DIMENSION_TOLERANCE_TYPES,
            precision=REWORK_PRECISION,
        )
        verify_machining_controls(
            receipt,
            expected=RECEIPT_EXPECTED,
            tolerance_types=feed_nut.DIMENSION_TOLERANCE_TYPES,
            precision=RECEIPT_PRECISION,
        )
        _assert_callouts(adapter, annotations, REWORK_CALLOUTS)
        _assert_countersink_text(adapter, annotations)
        _assert_callouts(adapter, receipt, RECEIPT_CALLOUTS)
        _assert_spigot_note(adapter, spigot, spigot_tip)
        _assert_rework_ink(adapter, [*annotations, *receipt], spigot, end, section)
        title_fit()

    settled()
    return (settled,)


def append_member_sheets(adapter: Any) -> tuple[Callable[[], None], ...]:
    """Sheets 2 and 3, in package order."""
    return (
        *_append_leadscrew_sheet(adapter),
        *_append_feed_nut_rework_sheet(adapter),
    )


# --- Sheet 1: the FeedNut panel's supplier references ---------------------------


def _assert_hidden_lines_removed(views: Mapping[str, Any]) -> None:
    """The orthographic views print no hidden edges after the final rebuild.

    The reference chords show in their views as construction lines; they lie
    on the axis or on visible edges, never as dashed edges across a face.
    """
    for name in ("*Front", "*Top", "*Right"):
        mode = int(_early_bound(views[name], "IView").GetDisplayMode2())
        if mode != _SW_HLR:
            raise RuntimeError(f"{name}: nut view is not hidden-lines-removed ({mode})")


def require_source_configuration(adapter: Any, view: Any, configuration: str) -> None:
    """The supplier-reference proof reads the source part's active configuration.

    ``_supplier_screw_dimensions`` resolves ``SupplierReference`` through
    ``IView.ReferencedDocument``, whose features and sketch points belong to
    the part's ACTIVE configuration. A FeedNut view proven against the saved
    LeadScrew default maps every attachment to a different native point
    (farm run 20261104T222143958Z: IsSame 0 for all, source in LeadScrew).
    """
    native = _early_bound(view, "IView")
    if str(native.ReferencedConfiguration) != configuration:
        raise RuntimeError(f"{configuration}: supplier view shows another member")
    active = active_configuration_name(
        adapter, _early_bound(native.ReferencedDocument, "IModelDoc2")
    )
    if active != configuration:
        raise RuntimeError(
            f"{configuration}: source part is active in {active!r}; its supplier "
            "attachments cannot be proven against another configuration"
        )


def annotate_member(
    adapter: Any,
    configuration: str,
    cells: tuple,
    views: list[Any],
) -> tuple[Callable[[], None], ...]:
    """The FeedNut panel's listing sizes; the LeadScrew's views stay plain."""
    if configuration != SUPPLIER_REFERENCE_CONFIGURATION:
        return ()
    by_orientation = {
        orientation: view for view, (orientation, _, _) in zip(views, cells, strict=True)
    }
    checks: list[Callable[[], None]] = []
    require_source_configuration(adapter, by_orientation["*Front"], configuration)
    displays = annotate_supplier_screw(
        adapter,
        by_orientation,
        dimensions=feed_nut.SUPPLIER_REFERENCE_DIMENSIONS,
        formats=feed_nut.SUPPLIER_REFERENCE_FORMATS,
        starts=feed_nut.SUPPLIER_REFERENCE_STARTS,
        planes=feed_nut.SUPPLIER_REFERENCE_PLANES,
        sides=feed_nut.SUPPLIER_REFERENCE_SIDES,
        units=feed_nut.SUPPLIER_REFERENCE_UNITS,
        settled_checks=checks,
    )
    stations = shelve_supplier_text(adapter, displays, SHELVES)
    [settled_references] = checks

    def assert_references() -> None:
        # The final check reacquires every native reference, then re-proves
        # the shelves against the stations measured here.
        require_source_configuration(adapter, by_orientation["*Front"], configuration)
        assert_supplier_shelves(adapter, settled_references(), SHELVES, stations)
        _assert_hidden_lines_removed(by_orientation)

    return (assert_references,)


async def build(adapter: Any) -> dict[str, str]:
    return await build_purchased_variant_drawing(
        adapter,
        SPEC,
        variants=VARIANTS,
        item=ITEM,
        purchase_unit=PURCHASE_UNIT,
        general_text=GENERAL_TEXT,
        annotate_member=annotate_member,
        additional_sheet_scales={
            LEADSCREW_SHEET_NAME: SHEET_SCALE,
            REWORK_SHEET_NAME: REWORK_SCALE,
        },
        append_sheets=append_member_sheets,
        additional_sheets_title=ADDITIONAL_SHEETS_TITLE,
        title_fit=True,
        isometric_only=ISOMETRIC_ONLY,
        source_configuration=SUPPLIER_REFERENCE_CONFIGURATION,
        unit=part_drawing_unit(PART_STEM),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
