"""Create the cut-to-length drawing for ZYLtech HW-SC-T8x2-600, the TL-VN-54 Tr8x2 lead screw.

The shop cuts the bought 600 mm screw to length and mills a set-screw flat
under each set screw that locks it, so the sheet is a modified-stock
drawing: one view of the screw lying axis-horizontal, as it sits in the saw
and the mill, carrying the native ``CutLength`` and the far two flats'
stations (the title block's band for each one's places governs it); details
C, D and E at 3:1 of the near end's station, the far KP08's and the
handwheel's, the 1:2 view drawing a flat 0.36 mm deep: C carries the near
station, E the printed flat's length and across-flat; sections A-A and B-B
through the two KP08 stations, each carrying its 120° flat's across-flat and
angle from clock 0, the angle's text offset outboard of its arc; the
isometric; and a note block naming the item, its supplier and SKU.
The thread is bought, not cut: it is not modelled, and a leadered callout on
the main view names it over the full length.

The supplier inset is captured while the source is clean, then imported,
formatted and jointly placed exactly once at the before-save checkpoint,
after manufacturing and finalizer rebuilds. Later checkpoints only verify
the native result; finished-PDF text is checked after native handles close.
The existing source-linked Number alone uses the canonical native title-cell
fit before finalization; read-only checks retain its complete value, original
sheet and fitted presentation through rebuild, save, PDF export and close.

Run with SolidWorks open::

    uv run python cad\\scripts\\draw_ch_rocker_arm_tl_vn_oblique_leadscrew.py ch-rocker-arm-tl-vn-oblique-leadscrew
"""

from __future__ import annotations

import argparse
import math
import sys
from contextlib import closing, contextmanager
from dataclasses import replace
from enum import Enum, auto
from pathlib import Path
from typing import Any, Callable, NamedTuple

import pypdfium2 as pdfium

from solidworks_mcp.adapters import sw_type_info as _sw_type_info
from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    dimension_name,
    place_view,
    view_name,
)

from _com import _early_bound, _read_member
from _drawing_centerline import add_view_centerline
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    stamp_drawing_summary,
)
from _drawing_detail_projection import settle_detail_projection
from _drawing_dimension_import import curate_view_dimensions
from _drawing_hidden_sketches import _show_hidden_owners
from _drawing_dimensions import offset_dimension_text, set_dimension_callouts
from _drawing_layout_audit import annotation_display
from _drawing_leader_notes import add_leader_note
from _drawing_notes import property_link
from _drawing_projection import model_points_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _machinist_review_mode import MachinistReviewMode
from _drawing_sections import create_section_view
from _drawing_view_display import set_hidden_lines_removed
from _layout_audit import _display_segments, display_box
from _layout_geometry import Box, segment_box_distance
from _pdf_ink import POINT_M
from _rebuild import active_configuration_name
from _session import run_build
from _stock_trim_drawing import verify_machining_controls
from _purchased_fastener_drawing import (
    _box,
    _inside,
    _open_supplier_source_read_only,
    _source_file_sha256,
    assert_supplier_annotations_fit,
)
from _purchased_title_fit import (
    _fit_title_note,
    assert_linked_value,
    source_property_expression,
)
from _supplier_spring_drawing import (
    _activate_reference_document,
    _assert_reference_binding,
    _assert_reference_capture_binding,
    _assert_reference_source_restored,
    _capture_reference_views,
    _preserve_reference_source_file,
    _reference_view_bounds,
    _show_reference_configuration,
    reacquire_supplier_dimensions,
)
from _supplier_screw_dimensions import annotate_supplier_screw
from _supplier_screw_reference_names import FEATURE_BY_PLANE
import ch_rocker_arm_tl_vn_oblique_leadscrew_stock_spec as supplier
import _telemetry
from ch_rocker_arm_tl_vn_oblique_leadscrew_stock_spec import (
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
    control_si,
)

MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["ch_rocker_arm_tl_vn_oblique_leadscrew"]
PART_STEM = SPEC.artifact_stem
SOURCE = SPEC.source
OUTPUTS = DrawingOutputs(**SPEC.outputs)

# ASME B landscape, sheet metres: 431.8 x 279.4 with the inner border 12.7 in
# from each edge, so 406.4 mm of drawable width. The title block spans
# x >= 0.2159 below y = 0.0651.
BORDER = (0.0127, 0.0127, 0.4191, 0.2667)
TITLE_BLOCK = (0.2159, 0.0127, 0.4191, 0.0651)
# The 410 screw overruns the 406.4 mm border at 1:1; 1:2, the next project
# scale down, lays it 205 mm long and Ø8 4 mm across.
SHEET_SCALE = (1.0, 2.0)
ISO_SCALE = SHEET_SCALE  # One-scale sheet: no per-view scale label.
_SHEET_PER_MODEL_MM = SHEET_SCALE[0] / SHEET_SCALE[1] / 1000
SCREW_SHEET_LENGTH = LENGTH * _SHEET_PER_MODEL_MM
SCREW_SHEET_DIA = MAJOR_DIA * _SHEET_PER_MODEL_MM

# *Front looks square at the Front-plane profile sketch, so CutLength imports
# into it; turned -90 deg, model +Y (near end y = 0 to the far end) runs to
# sheet right and the axis lies horizontal.
MAIN_VIEW_ANGLE = -math.pi / 2.0
# The main view centred left of the isometric's column: x 0.195 spans the
# screw over 0.0925 .. 0.2975, 80 mm in from the left border; y 0.160 sits
# mid-height, 95 mm above the title block's top.
MAIN_CENTER = (0.195, 0.160)
# The isometric stands the axis up: 410 cos 35.26 deg plus the Ø8 end
# ellipses is about 340 mm, 170 at 1:2, and about 5 wide. Centred 29 mm in
# from the right border, its outline spans y 0.081 .. 0.251, between the
# title block's top (0.0651) and the top border (0.2667).
ISO_CENTER = (0.390, 0.166)
# Initial seed only. Final placement intersects the actual native-frame and
# complete source/annotation ink constraints; no retained frame offset is assumed.
SUPPLIER_STOCK_CENTER = (0.183, 0.2365)
SUPPLIER_STOCK_SCALE = (1, 10)
SUPPLIER_STOCK_FIELD = (0.135, 0.208, 0.245, 0.265)
SUPPLIER_STOCK_CAPTION_XY = (0.140, 0.264)
SUPPLIER_STOCK_CAPTION_GAP = 0.003
# Paper-space clearances, independent of the view/frame's model-space origin.
SUPPLIER_STOCK_GAUGE_GAP = 0.003
SUPPLIER_STOCK_TEXT_GAP = 0.003
SUPPLIER_STOCK_PLACE_AIR = 0.004  # 1 mm settling reserve above the strict 3 mm gap.
SUPPLIER_STOCK_MOVE_TOLERANCE = 1e-6  # Same center readback precision as _center_view.
SUPPLIER_STOCK_CAPTION = (
    "SUPPLIER NOMINAL STOCK GAUGES\nNOT PART SHAPE — SCALE 1:10"
)
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
    flat, 3.5 off its station toward the screw's middle, so the line stands
    clear of the station's extension line), whether it looks toward the far
    end (model +Y, sheet right; its arrows then point right, away from the
    screw's nearer end and the cut length's extension line), and where the
    section's axis stands on the sheet."""

    flat: str
    label: str
    cut_mm: float
    looks_far: bool
    centre: tuple[float, float]


SECTION_SCALE = (3, 1)
_SECTION_CUT_OFF_STATION_MM = FLAT_LENGTH / 2.0 - 0.5
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
_NEAR_XY = (0.043, DETAIL_ROW_Y)
# D: the far KP08's two flats (375.5 .. 383.5); its station is the main
# view's.
_FAR_CENTRE_MM = FLAT_STATIONS["FarKP08"]
_FAR_XY = (0.091, DETAIL_ROW_Y)
# E: the handwheel's flat and the far end (394.5 .. 410), the printed flat's
# length under the fence, right of the flat, and its across-flat left of it,
# square to the axis:
# its extension line off the flat runs back along the flat and out of the
# fence over 0.6 mm of thread (right of it, it would run 7.5 mm along the
# unflatted thread to the far end, reading as the flat running out there).
# The across-flat's text (its widest row, "C, D, E", about 15 mm wide, centred
# on its dimension line) stands between D's fence and E's.
_WHEEL_CENTRE_MM = (FLAT_STATIONS["Handwheel"] - FLAT_LENGTH / 2.0 + LENGTH) / 2.0
_WHEEL_RADIUS_MM = 9.0
_WHEEL_XY = (0.1615, DETAIL_ROW_Y)
# The across-flat runs from the far crest (clock 180, radius -4) to the flat
# (FLAT_AF - 4 toward clock 0): its middle stands at half their sum.
_AF_MID_RADIUS_MM = (FLAT_AF - MAJOR_DIA) / 2.0
# The flat length's text (widest row "5X, ALL FLATS", about 29 mm) is wider
# than the flat's 24 mm at 3:1, so it stands right of the flat's far-end
# extension line, its dimension line run out to it (review jbf-r17, rule 14:
# both extension lines crossed the text).
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
        {},
    ),
    EndDetail(
        "E",
        _WHEEL_CENTRE_MM,
        _WHEEL_RADIUS_MM,
        _WHEEL_XY,
        # Right of the far end, level with the axis.
        (sheet_x(LENGTH) + 0.008, MAIN_CENTER[1]),
        {
            "FlatLength": (
                detail_xy(
                    _WHEEL_CENTRE_MM,
                    _WHEEL_XY,
                    FLAT_STATIONS["Handwheel"] + FLAT_LENGTH / 2.0,
                )[0]
                + FLAT_LENGTH_TEXT_GAP
                + FLAT_LENGTH_TEXT_HALF_WIDTH,
                detail_xy(_WHEEL_CENTRE_MM, _WHEEL_XY, 0.0, _text_row_radius_mm())[1],
            ),
            "FlatAF": detail_xy(
                _WHEEL_CENTRE_MM,
                _WHEEL_XY,
                _WHEEL_CENTRE_MM - _WHEEL_RADIUS_MM - 3.5,
                _AF_MID_RADIUS_MM,
            ),
        },
    ),
)
# Every flat is one size: the printed one says how many (pivot-shaft style)
# and which (review bought-r16, rule 1: "3X" and "5X" on detail E's one flat
# left the reader to work out which flats they cover). The length is every
# flat's; the across-flat is each clock-0 flat's, one in each detail (the
# clock flats print their own in sections A-A and B-B). The across-flat's
# rows stay narrower than the 25 mm between fences D and E.
FLAT_CALLOUTS = {
    "FlatLength": f"{FLAT_LENGTH_CALLOUT}, ALL FLATS",
    "FlatAF": "\n".join(
        (FLAT_AF_CALLOUT, ", ".join(detail.label for detail in END_DETAILS))
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
# and the cut length is the dimension's.
ITEM = "TR8X2 LEAD SCREW"
NOTES = "\n".join(
    (
        f"ITEM: {ITEM}",
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
PDF_TITLE = "Rocker Oblique Trammel Leadscrew — Modified Stock Drawing"


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


def _centre_section(adapter: Any, view: Any, section: ClockSection) -> None:
    """Stand the section's axis on its layout point: a section's outline is no
    measure of its ink (draw_dt_cone_gear_shaft._section_face), so the axis
    is projected and the view moved by the error."""
    bound = _early_bound(view, "IView")
    for _attempt in range(3):
        (axis,) = model_points_in_view(
            adapter,
            view,
            (_axis_point(section.cut_mm),),
            label=f"section {section.label} axis",
        )
        error = (section.centre[0] - axis[0], section.centre[1] - axis[1])
        if max(abs(error[0]), abs(error[1])) < SECTION_SETTLE_M:
            return
        position = tuple(float(value) for value in bound.Position)
        target = [position[0] + error[0], position[1] + error[1]]
        if not bound.SetViewPosition(double_array(target), False):
            raise RuntimeError(f"section {section.label}: failed to position the view")
        rebuild_drawing(adapter, label=f"centre section {section.label}")
    raise RuntimeError(
        f"section {section.label} axis stayed at {axis}, not {section.centre}"
    )


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


def _place_view_caption(
    adapter: Any, view: Any, target: tuple[float, float], *, label: str
) -> None:
    """Move a view's native caption so its box's top centre lands on
    ``target``, its linked fields intact (draw_dt_cone_gear_shaft's
    ``_place_view_caption``: the move is measured by ``INote.GetExtent``, the
    sheet scale pinned first so finalization cannot move it after)."""
    ddoc = _early_bound(adapter.currentModel, "IDrawingDoc")
    sheet = _early_bound(ddoc.GetCurrentSheet(), "ISheet")
    if not sheet.SetScale(*SHEET_SCALE, False, False):
        raise RuntimeError(f"cannot pin sheet scale before {label} placement")
    notes = tuple(_read_member(_early_bound(view, "IView"), "GetNotes") or ())
    if len(notes) != 1:
        raise RuntimeError(f"expected one native {label}, found {len(notes)} notes")
    note = _early_bound(notes[0], "INote")
    linked = str(note.PropertyLinkedText or "")
    if not linked:
        raise RuntimeError(f"{label} carries no linked view fields")
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
        _centre_section(adapter, view, section)
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
    return view


@_telemetry.traced("drawing.end_details")
def _add_end_details(adapter: Any, main: Any) -> list[Any]:
    """Detail each flat station at 3:1, where the main view's 0.36 mm flats
    read: each detail's dimensions, its letter on the main view and its
    caption under the row of texts. Returns the details' dimension
    annotations; ``curate_view_dimensions`` fails the build if one does not
    arrive."""
    annotations: list[Any] = []
    for detail in END_DETAILS:
        view = _create_end_detail(adapter, main, detail)
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
        )
    return annotations


def _measure_supplier_stock_dimensions(adapter: Any, view: Any) -> dict[str, dict]:
    """Reacquire all three native gauges, including their below-callout glyphs."""
    displays = reacquire_supplier_dimensions(
        adapter,
        {"*Front": view},
        expected={"*Front": {
            name: FEATURE_BY_PLANE["Front"]
            for name, _, _ in supplier.SUPPLIER_REFERENCE_DIMENSIONS
        }},
        configurations={"*Front": supplier.SUPPLIER_STOCK_CONFIGURATION},
    )
    records = {}
    for name, display in displays.items():
        annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
        data, refused = annotation_display(adapter, annotation)
        text = display_box({"texts": data.get("texts", ())})
        ink = display_box(data)
        position = tuple(float(value) for value in (annotation.GetPosition() or ()))
        callout = supplier.SUPPLIER_REFERENCE_FORMATS[name][3]
        printed = "".join(str(row.get("t", "")) for row in data.get("texts", ()))
        if (
            refused or text is None or ink is None or len(position) != 3
            or not all(map(math.isfinite, position))
            or any(
                not all(map(math.isfinite, (box.xmin, box.ymin, box.xmax, box.ymax)))
                or box.width <= 0 or box.height <= 0
                for box in (text, ink)
            )
            or "".join(callout.split()) not in "".join(printed.split())
        ):
            raise RuntimeError(
                f"{name}: incomplete native supplier text/ink: {refused!r}; "
                f"position_m={position!r}; native_text={printed!r}"
            )
        records[name] = {
            "display": display, "annotation": annotation, "position": position,
            "data": data, "text": text, "ink": ink,
        }
    return records


def _assert_supplier_stock_clearance(records: dict[str, dict]) -> None:
    """Check glyph-to-glyph and actual stroke-to-other-glyph air, not white boxes."""
    for index, (name, record) in enumerate(records.items()):
        for other_name, other in tuple(records.items())[index + 1:]:
            if record["text"].gap(other["text"]) < SUPPLIER_STOCK_TEXT_GAP:
                raise RuntimeError(
                    f"supplier text clearance: {name}={record['text']!r}, "
                    f"{other_name}={other['text']!r}"
                )
        for segment in _display_segments(record["data"]):
            for other_name, other in records.items():
                if name != other_name and (
                    segment_box_distance(segment, other["text"])
                    < SUPPLIER_STOCK_TEXT_GAP
                ):
                    raise RuntimeError(
                        f"supplier stroke/text clearance: {name} {segment!r} "
                        f"crowds {other_name}={other['text']!r}"
                    )


def _place_supplier_stock_dimensions(
    adapter: Any, view: Any, displays: dict[str, Any],
    curve_bounds: tuple[float, float, float, float],
) -> None:
    """Arrange measured complete glyph blocks around the three source gauges.

    Source-relative paper gaps set line stations. All text, including the
    length's below-callout row, is offset above/right of those lines using its
    measured box; the annotation insertion point is not a glyph-box corner.
    The caller's caption-format rebuild settles these final text moves too.
    """
    rows = supplier.SUPPLIER_REFERENCE_DIMENSIONS
    points = []
    for name, value, orientation in rows:
        x, y = supplier.SUPPLIER_REFERENCE_STARTS[name]
        if orientation == "horizontal":
            x += value / 2.0
        else:
            y += value / 2.0
        points.append((x / 1000.0, y / 1000.0, 0.0))
    centers = dict(zip(
        (name for name, _, _ in rows),
        model_points_in_view(
            adapter, view, points, label="leadscrew supplier gauge centers"
        ),
        strict=True,
    ))
    pitch_line = curve_bounds[3] + SUPPLIER_STOCK_GAUGE_GAP
    diameter_line = curve_bounds[2] + SUPPLIER_STOCK_GAUGE_GAP
    anchors = {
        "SupplierStockLength": (centers["SupplierStockLength"][0], pitch_line),
        "SupplierStockDiameter": (
            diameter_line, centers["SupplierStockDiameter"][1]
        ),
        "SupplierThreadPitch": (centers["SupplierThreadPitch"][0], pitch_line),
    }
    for name, anchor in anchors.items():
        display = _early_bound(displays[name], "IDisplayDimension")
        annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
        display.OffsetText = False
        if display.OffsetText or not annotation.SetPosition2(*anchor, 0.0):
            raise RuntimeError(f"{name}: cannot place supplier gauge line")
    rebuild_drawing(adapter, label="leadscrew supplier gauge line anchors")
    for display in displays.values():
        display.OffsetText = True
        if not display.OffsetText:
            raise RuntimeError("cannot enable native supplier text offset")
    rebuild_drawing(adapter, label="leadscrew supplier native text format")
    adapter.currentModel.GraphicsRedraw2()
    records = _measure_supplier_stock_dimensions(adapter, view)
    pitch_top = (
        pitch_line + SUPPLIER_STOCK_PLACE_AIR
        + records["SupplierThreadPitch"]["text"].height
    )
    length_line = pitch_top + SUPPLIER_STOCK_PLACE_AIR
    length = records["SupplierStockLength"]
    length["display"].OffsetText = False
    if not length["annotation"].SetPosition2(
        centers["SupplierStockLength"][0], length_line, 0.0
    ):
        raise RuntimeError("cannot place supplier length line above pitch glyphs")
    length["display"].OffsetText = True
    if not length["display"].OffsetText:
        raise RuntimeError("cannot offset supplier length text")
    for name, record in records.items():
        annotation = record["annotation"]
        position = tuple(float(value) for value in annotation.GetPosition())
        text = record["text"]
        if name == "SupplierStockLength":
            # Carry its measured glyph-to-insertion offset, not a font baseline.
            moved_x = position[0] - record["position"][0]
            moved_y = position[1] - record["position"][1]
            text = Box(text.xmin + moved_x, text.ymin + moved_y,
                       text.xmax + moved_x, text.ymax + moved_y)
        x_shift = (
            diameter_line + SUPPLIER_STOCK_PLACE_AIR - text.xmin
            if name == "SupplierStockDiameter"
            else centers[name][0] - text.center()[0]
        )
        bottom = (
            curve_bounds[3] + SUPPLIER_STOCK_PLACE_AIR
            if name == "SupplierStockDiameter"
            else (length_line if name == "SupplierStockLength" else pitch_line)
            + SUPPLIER_STOCK_PLACE_AIR
        )
        if name == "SupplierThreadPitch":
            # Printed glyphs rise above the native cap box. Lower only this
            # offset text block; its gauge line and source geometry stay fixed.
            bottom -= 0.001
        if not annotation.SetPosition2(
            position[0] + x_shift, position[1] + bottom - text.ymin, position[2]
        ):
            raise RuntimeError(f"{name}: cannot place measured supplier glyph block")


def _supplier_stock_translation(
    native_outline: tuple, curve_bounds: tuple, records: dict[str, dict],
    caption_box: tuple,
) -> tuple[float, float]:
    """Intersect the frame/full-field and complete-ink/caption-free translations."""
    ink = Box(*curve_bounds)
    for record in records.values():
        ink = ink.union(record["ink"])
    field = SUPPLIER_STOCK_FIELD
    ink_field = (
        field[0], field[1], field[2], caption_box[1] - SUPPLIER_STOCK_CAPTION_GAP
    )
    dx = (
        max(field[0] - native_outline[0], ink_field[0] - ink.xmin),
        min(field[2] - native_outline[2], ink_field[2] - ink.xmax),
    )
    dy = (
        max(field[1] - native_outline[1], ink_field[1] - ink.ymin),
        min(field[3] - native_outline[3], ink_field[3] - ink.ymax),
    )
    offset = (
        (curve_bounds[0] + curve_bounds[2] - native_outline[0] - native_outline[2]) / 2,
        (curve_bounds[1] + curve_bounds[3] - native_outline[1] - native_outline[3]) / 2,
    )
    detail = (
        f"source_curve_bounds_m={curve_bounds!r}; native_outline_m={native_outline!r}; "
        f"curve_frame_offset_m={offset!r}; annotation_ink_m={ink!r}; "
        f"caption_box_m={caption_box!r}; ink_field_m={ink_field!r}; "
        f"permitted_dx_m={dx!r}; permitted_dy_m={dy!r}"
    )
    _telemetry.info(f"supplier stock joint placement before: {detail}")
    if dx[0] > dx[1] or dy[0] > dy[1]:
        raise RuntimeError(f"supplier stock has no joint frame/ink translation; {detail}")
    return ((dx[0] + dx[1]) / 2, (dy[0] + dy[1]) / 2)


@contextmanager
def _supplier_stock_source_scope(
    adapter: Any, view: Any, *, capture: Any, allow_presentation_dirty: bool = False,
):
    """Keep source proxies local to Stock while operating in the original drawing.

    Entry requires the existing drawing sheet-edit context, never template edit.
    Early capture requires a clean source; late authoring and strict checks may
    enter with existing presentation dirtiness. Activation alone must never
    change that flag. Only the body may leave presentation dirtiness, never
    saved source changes. No source feature/sketch/point proxy is retained here
    or by the supplier callbacks across restoration of the captured original
    configuration. Layout readers run outside this scope against that original.
    """
    label = "leadscrew supplier stock source scope"
    state = capture.source
    model = state.model
    stock = supplier.SUPPLIER_STOCK_CONFIGURATION
    stock_state = replace(state, configuration=stock, body_counts=(0, 0))
    drawing_model = _early_bound(adapter.currentModel, "IModelDoc2")
    drawing = _early_bound(drawing_model, "IDrawingDoc")
    sheet_name = str(_early_bound(drawing.GetCurrentSheet(), "ISheet").GetName())
    previous = drawing.ActiveDrawingView
    previous_name = view_name(adapter, previous) if previous is not None else None
    edit_sheet = drawing.GetEditSheet()
    if (
        not sheet_name or edit_sheet is not True
        or (previous is not None and not previous_name)
    ):
        raise RuntimeError(f"{label}: unreadable drawing sheet/view/edit context")

    def restore_drawing() -> None:
        _activate_reference_document(adapter, drawing_model, label=label)
        restored = drawing.ActivateSheet(sheet_name)
        activated = drawing.ActivateView(previous_name or "")
        active = drawing.ActiveDrawingView
        active_name = view_name(adapter, active) if active is not None else None
        if (
            restored is not True
            or (previous_name is not None and activated is not True)
            or active_name != previous_name
            or str(_early_bound(drawing.GetCurrentSheet(), "ISheet").GetName())
            != sheet_name
            or drawing.GetEditSheet() is not edit_sheet
            or (previous is not None and int(adapter.swApp.IsSame(active, previous)) != 1)
        ):
            raise RuntimeError(f"{label}: cannot restore drawing sheet/view/edit context")

    def assert_stock(*, allow_dirty: bool) -> None:
        _assert_reference_source_restored(
            adapter, stock_state, label=label, allow_presentation_dirty=allow_dirty,
        )
        _assert_reference_binding(
            adapter, view, source=state.path, model=model,
            configuration=stock, label=label,
        )

    primary: BaseException | None = None
    callback_started = False
    try:
        _assert_reference_capture_binding(
            adapter, view, capture=capture, source=SOURCE.resolve(), model=model,
            features=(FEATURE_BY_PLANE["Front"],), configuration=stock, label=label,
        )
        _assert_reference_source_restored(
            adapter, state, label=label,
            allow_presentation_dirty=allow_presentation_dirty,
        )
        was_dirty = model.GetSaveFlag()
        _activate_reference_document(adapter, model, label=label)
        _show_reference_configuration(adapter, model, stock, label=label)
        assert_stock(allow_dirty=allow_presentation_dirty)
        restore_drawing()
        assert_stock(allow_dirty=allow_presentation_dirty)
        if model.GetSaveFlag() is not was_dirty:
            raise RuntimeError(f"{label}: activation changed source dirty status")
        callback_started = True
        yield
    except BaseException as error:
        primary = error
        raise
    finally:
        restoration_errors: list[BaseException] = []
        if callback_started:
            try:
                assert_stock(allow_dirty=True)
            except BaseException as restore_error:
                restoration_errors.append(restore_error)
        try:
            active = adapter.swApp.ActiveDoc
            if active is None or int(adapter.swApp.IsSame(active, model)) != 1:
                _activate_reference_document(adapter, model, label=label)
            _show_reference_configuration(adapter, model, state.configuration, label=label)
            _assert_reference_source_restored(
                adapter, state, label=label,
                allow_presentation_dirty=allow_presentation_dirty or callback_started,
            )
        except BaseException as restore_error:
            restoration_errors.append(restore_error)
        try:
            restore_drawing()
        except BaseException as restore_error:
            restoration_errors.append(restore_error)
        if restoration_errors:
            failure = primary if primary is not None else restoration_errors[0]
            additional = restoration_errors if primary is not None else restoration_errors[1:]
            for restore_error in additional:
                failure.add_note(
                    f"{label}: source/drawing restoration also failed: {restore_error!r}"
                )
            if primary is None:
                raise failure


class _SupplierStockAuthoringState(Enum):
    PENDING = auto()
    AUTHORING = auto()
    AUTHORED = auto()
    FAILED = auto()


def _prepare_supplier_stock_inset(adapter: Any) -> Callable[[], Callable[[], None]]:
    """Capture clean source geometry now; return the once-only late author."""
    view = _early_bound(
        place_view(
            adapter,
            str(SOURCE),
            "*Front",
            *SUPPLIER_STOCK_CENTER,
            scale=SUPPLIER_STOCK_SCALE,
        ),
        "IView",
    )
    view.ReferencedConfiguration = supplier.SUPPLIER_STOCK_CONFIGURATION
    if str(view.ReferencedConfiguration) != supplier.SUPPLIER_STOCK_CONFIGURATION:
        raise RuntimeError("leadscrew stock gauges reference the installed solid")
    view.UseSheetScale = 0
    view.ScaleRatio = double_array(SUPPLIER_STOCK_SCALE)
    set_hidden_lines_removed(adapter, view)
    rebuild_drawing(adapter, label="leadscrew supplier stock configuration")
    owner = FEATURE_BY_PLANE["Front"]
    shown = _show_hidden_owners(
        adapter, view, (owner,), view_label="leadscrew supplier stock gauges"
    )
    if shown != [owner]:
        raise RuntimeError("leadscrew supplier stock sketch is not saved hidden")
    rebuild_drawing(adapter, label="show leadscrew supplier stock gauges")
    draw = _early_bound(adapter.currentModel, "IDrawingDoc")
    draw.ActivateView("")
    if not draw.GetEditSheet() or draw.ActiveDrawingView is not None:
        raise RuntimeError("cannot restore sheet context for supplier stock capture")
    source_model = _early_bound(view.ReferencedDocument, "IModelDoc2")
    captures = _capture_reference_views(
        adapter,
        adapter.currentModel,
        {"*Front": view},
        source=SOURCE,
        model=source_model,
        features={"*Front": (owner,)},
        configurations={"*Front": supplier.SUPPLIER_STOCK_CONFIGURATION},
        label="leadscrew supplier stock gauges",
    )

    def reference_bounds(
        *, allow_presentation_dirty: bool
    ) -> tuple[float, float, float, float]:
        return _reference_view_bounds(
            adapter,
            view,
            capture=captures["*Front"],
            source=SOURCE,
            model=source_model,
            features=(owner,),
            configuration=supplier.SUPPLIER_STOCK_CONFIGURATION,
            label="leadscrew supplier stock gauges",
            allow_presentation_dirty=allow_presentation_dirty,
        )

    curve_bounds = reference_bounds(allow_presentation_dirty=False)
    native_outline = _outline(view, "supplier stock captured frame")
    captured_offset = (
        (curve_bounds[0] + curve_bounds[2] - native_outline[0] - native_outline[2]) / 2,
        (curve_bounds[1] + curve_bounds[3] - native_outline[1] - native_outline[3]) / 2,
    )
    _telemetry.info(
        f"supplier stock captured: source_curve_bounds_m={curve_bounds!r}; "
        f"native_outline_m={native_outline!r}; curve_frame_offset_m={captured_offset!r}"
    )
    state = _SupplierStockAuthoringState.PENDING

    def author() -> Callable[[], None]:
        nonlocal state
        if state is not _SupplierStockAuthoringState.PENDING:
            raise RuntimeError(f"supplier stock authoring already consumed: {state.name}")
        state = _SupplierStockAuthoringState.AUTHORING
        try:
            check = _author_supplier_stock_inset(
                adapter, view, captures["*Front"], reference_bounds,
            )
        except BaseException:
            state = _SupplierStockAuthoringState.FAILED
            raise
        state = _SupplierStockAuthoringState.AUTHORED
        return check

    return author


def _author_supplier_stock_inset(
    adapter: Any, view: Any, capture: Any,
    reference_bounds: Callable[..., tuple[float, float, float, float]],
) -> Callable[[], None]:
    """Import/format once and jointly place the unchanged native frame and ink."""
    draw = _early_bound(adapter.currentModel, "IDrawingDoc")
    curve_bounds = reference_bounds(allow_presentation_dirty=True)
    checks = []
    with _supplier_stock_source_scope(
        adapter, view, capture=capture, allow_presentation_dirty=True,
    ):
        displays = annotate_supplier_screw(
            adapter,
            {"*Front": view},
            dimensions=supplier.SUPPLIER_REFERENCE_DIMENSIONS,
            formats=supplier.SUPPLIER_REFERENCE_FORMATS,
            starts=supplier.SUPPLIER_REFERENCE_STARTS,
            units=supplier.SUPPLIER_REFERENCE_UNITS,
            settled_checks=checks,
        )
    _place_supplier_stock_dimensions(adapter, view, displays, curve_bounds)
    draw.ActivateView("")
    if not draw.GetEditSheet() or draw.ActiveDrawingView is not None:
        raise RuntimeError("cannot restore sheet context for supplier stock caption")
    note = add_note(
        adapter, SUPPLIER_STOCK_CAPTION, *SUPPLIER_STOCK_CAPTION_XY
    )
    if note is None:
        raise RuntimeError("cannot add leadscrew supplier stock caption")
    # INote insertion coordinates need not equal its complete extent corner.
    # Seat the measured block at the target without changing its formatting.
    rebuild_drawing(adapter, label="leadscrew supplier caption format")
    adapter.currentModel.GraphicsRedraw2()
    caption = _early_bound(note, "INote")
    caption_box = _box(
        caption.GetExtent(), label="supplier stock caption", kind="note"
    )
    caption_annotation = _early_bound(caption.GetAnnotation(), "IAnnotation")
    position = tuple(
        float(value) for value in (caption_annotation.GetPosition() or ())
    )
    if len(position) != 3 or not all(map(math.isfinite, position)):
        raise RuntimeError(
            f"supplier stock caption has invalid position: {position!r}; "
            f"caption_box_m={caption_box!r}"
        )
    target = (
        position[0] + SUPPLIER_STOCK_CAPTION_XY[0] - caption_box[0],
        position[1] + SUPPLIER_STOCK_CAPTION_XY[1] - caption_box[3],
        position[2],
    )
    if not caption_annotation.SetPosition2(*target):
        raise RuntimeError(
            f"cannot seat supplier stock caption: {position!r} -> {target!r}; "
            f"caption_box_m={caption_box!r}"
        )
    rebuild_drawing(adapter, label="leadscrew supplier caption position")
    before_curves = reference_bounds(allow_presentation_dirty=True)
    adapter.currentModel.GraphicsRedraw2()
    before_frame = _outline(view, "supplier stock joint placement")
    seated_caption = _box(
        caption.GetExtent(), label="seated supplier stock caption", kind="note"
    )
    _telemetry.info(
        f"supplier stock caption: position_m={position!r} -> {target!r}; "
        f"caption_box_m={caption_box!r} -> {seated_caption!r}"
    )
    if not _inside(seated_caption, SUPPLIER_STOCK_FIELD):
        curve_bounds, native_outline = before_curves, before_frame
        ink_field = (
            SUPPLIER_STOCK_FIELD[0], SUPPLIER_STOCK_FIELD[1],
            SUPPLIER_STOCK_FIELD[2],
            seated_caption[1] - SUPPLIER_STOCK_CAPTION_GAP,
        )
        detail = (
            f"source_curve_bounds_m={curve_bounds!r}; "
            f"native_outline_m={native_outline!r}; "
            f"caption_box_m={seated_caption!r}; ink_field_m={ink_field!r}"
        )
        _telemetry.info(f"supplier stock gauges caption seating refused: {detail}")
        raise RuntimeError(f"seated supplier stock caption left its field; {detail}")

    before_records = _measure_supplier_stock_dimensions(adapter, view)
    dx, dy = _supplier_stock_translation(
        before_frame, before_curves, before_records, seated_caption
    )
    _assert_supplier_stock_clearance(before_records)
    view_position = tuple(float(value) for value in (view.Position or ()))
    if len(view_position) != 2 or not all(map(math.isfinite, view_position)):
        raise RuntimeError(f"supplier stock has invalid view position: {view_position!r}")
    if not view.SetViewPosition(
        double_array([view_position[0] + dx, view_position[1] + dy]), False
    ):
        raise RuntimeError("cannot apply joint supplier frame/ink translation")
    rebuild_drawing(adapter, label="leadscrew supplier joint frame/ink placement")

    def assert_translation(label: str, before: tuple, after: tuple) -> None:
        movement = (dx, dy, dx, dy) if len(before) == 4 else (dx, dy, 0.0)
        expected = tuple(value + delta for value, delta in zip(before, movement, strict=True))
        if len(after) != len(expected) or any(
            abs(actual - wanted) > SUPPLIER_STOCK_MOVE_TOLERANCE
            for actual, wanted in zip(after, expected, strict=True)
        ):
            raise RuntimeError(
                f"{label}: native ink did not translate with its view; "
                f"before_m={before!r}; expected_m={expected!r}; actual_m={after!r}"
            )

    def placed_readback(stage: str) -> None:
        curve_bounds = native_outline = caption_box = ink_field = records = offset = None
        try:
            caption = _early_bound(note, "INote")
            annotation = _early_bound(caption.GetAnnotation(), "IAnnotation")
            curve_bounds = reference_bounds(allow_presentation_dirty=True)
            adapter.currentModel.GraphicsRedraw2()
            native_outline = _outline(view, "supplier stock gauges settled")
            caption_extent = caption.GetExtent()
            offset = (
                (curve_bounds[0] + curve_bounds[2] - native_outline[0] - native_outline[2]) / 2,
                (curve_bounds[1] + curve_bounds[3] - native_outline[1] - native_outline[3]) / 2,
            )
            caption_box = _box(
                caption_extent, label="supplier stock caption", kind="note"
            )
            ink_field = (
                SUPPLIER_STOCK_FIELD[0],
                SUPPLIER_STOCK_FIELD[1],
                SUPPLIER_STOCK_FIELD[2],
                caption_box[1] - SUPPLIER_STOCK_CAPTION_GAP,
            )
            records = _measure_supplier_stock_dimensions(adapter, view)
            if (
                str(caption.GetText() or "").replace("\r", "") != SUPPLIER_STOCK_CAPTION
                or int(annotation.OwnerType) != 1
                or not _inside(caption_box, SUPPLIER_STOCK_FIELD)
            ):
                raise RuntimeError(
                    "leadscrew supplier stock caption changed or left its field"
                )
            if not _inside(curve_bounds, ink_field):
                raise RuntimeError(
                    "leadscrew supplier stock curves left their caption-free field"
                )
            if not _inside(native_outline, SUPPLIER_STOCK_FIELD):
                raise RuntimeError(
                    f"leadscrew supplier native frame leaves its field: {native_outline!r}"
                )
            assert_translation("supplier native frame", before_frame, native_outline)
            assert_translation("supplier source curves", before_curves, curve_bounds)
            for name, record in records.items():
                assert_translation(
                    name, before_records[name]["position"], record["position"]
                )
                for kind in ("text", "ink"):
                    before = before_records[name][kind]
                    after = record[kind]
                    assert_translation(
                        f"{name} {kind}",
                        (before.xmin, before.ymin, before.xmax, before.ymax),
                        (after.xmin, after.ymin, after.xmax, after.ymax),
                    )
                if not record["display"].OffsetText:
                    raise RuntimeError(f"{name}: supplier text lost its native offset")
            _assert_supplier_stock_clearance(records)
            assert_supplier_annotations_fit(
                adapter,
                view,
                ink_field,
                label="leadscrew nominal supplier stock gauges below caption",
            )
        except RuntimeError as error:
            raise RuntimeError(
                f"{error}; source_curve_bounds_m={curve_bounds!r}; "
                f"native_outline_m={native_outline!r}; curve_frame_offset_m={offset!r}; "
                f"caption_box_m={caption_box!r}; ink_field_m={ink_field!r}"
            ) from error
        finally:
            _telemetry.info(
                f"supplier stock gauges {stage}: "
                f"source_curve_bounds_m={curve_bounds!r}; native_outline_m={native_outline!r}; "
                f"curve_frame_offset_m={offset!r}; caption_box_m={caption_box!r}; "
                f"ink_field_m={ink_field!r}; translation_m={(dx, dy)!r}"
            )

    placed_readback("after joint placement")

    def settled() -> None:
        with _supplier_stock_source_scope(
            adapter, view, capture=capture, allow_presentation_dirty=True,
        ):
            for check_source in checks:
                check_source()
        if (
            str(view.ReferencedConfiguration) != supplier.SUPPLIER_STOCK_CONFIGURATION
            or tuple(view.ScaleRatio) != SUPPLIER_STOCK_SCALE
            or view.UseSheetScale != 0
        ):
            raise RuntimeError("leadscrew supplier stock configuration/scale changed")
        placed_readback("settled")

    return settled


def _assert_supplier_stock_pdf(path: Path) -> None:
    """Prove the exact three printed stock sizes/callouts in their own field.

    Native strict checks own the diameter symbol: SolidWorks can export it as
    vector ink rather than text. Only the explicit diameter glyph variants
    below (or that vector-only case) are accepted, never alternate values,
    units or callouts. All other comparison normalization is whitespace-only.
    """
    with closing(pdfium.PdfDocument(str(path))) as document:
        if len(document) != 1:
            raise RuntimeError(
                f"supplier stock PDF requires one physical page; got {len(document)}; "
                "raw_stock_text=<not extracted>"
            )
        with closing(document[0]) as page, closing(page.get_textpage()) as text_page:
            left, bottom, right, top = (
                coordinate / POINT_M for coordinate in SUPPLIER_STOCK_FIELD
            )
            raw = text_page.get_text_bounded(
                left=left, bottom=bottom, right=right, top=top,
            )

    remaining = "".join(raw.split())

    def consume(tokens: tuple[str, ...], label: str) -> None:
        nonlocal remaining
        matches = [(token, remaining.count(token)) for token in tokens]
        if sum(count for _token, count in matches) != 1:
            raise RuntimeError(
                f"supplier stock PDF differs for {label}; expected={tokens!r}; "
                f"raw_stock_text={raw!r}"
            )
        token = next(token for token, count in matches if count)
        remaining = remaining.replace(token, "", 1)

    for name, value, _orientation in supplier.SUPPLIER_REFERENCE_DIMENSIONS:
        precision, presentation, denominator, callout = supplier.SUPPLIER_REFERENCE_FORMATS[name]
        units = supplier.SUPPLIER_REFERENCE_UNITS[name]
        if denominator is not None or units != "mm":
            raise RuntimeError(f"{name}: unsupported supplier PDF format; raw_stock_text={raw!r}")
        size = f"{value:.{precision}f}{units}"
        marks = ("", "Ø", "⌀", "∅") if presentation == "diameter" else ("",)
        consume(tuple(f"({mark}{size})" for mark in marks), f"{name} size")
        consume(("".join(callout.split()),), f"{name} callout")

    # The unchanged caption can be in the extraction too; nothing else may
    # impersonate a valid token by adding a prefix/suffix or a fourth gauge.
    remaining = remaining.replace("".join(SUPPLIER_STOCK_CAPTION.split()), "", 1)
    if remaining:
        raise RuntimeError(
            f"supplier stock PDF contains unexpected field text {remaining!r}; "
            f"raw_stock_text={raw!r}"
        )


def _fit_number_title_note(
    adapter: Any, *, expected_number: str,
) -> Callable[[], None]:
    """Fit only the existing source Number; never edit its link or ruled cell."""
    draw = _early_bound(adapter.currentModel, "IModelDoc2")
    ddoc = _early_bound(draw, "IDrawingDoc")
    sheet = _early_bound(ddoc.GetCurrentSheet(), "ISheet")
    sheet_view = _early_bound(ddoc.GetFirstView(), "IView")
    if sheet is None or sheet_view is None:
        raise RuntimeError("leadscrew Number has no native sheet or sheet view")
    sheet_name = str(sheet.GetName() or "")
    if not sheet_name.strip():
        raise RuntimeError("leadscrew Number has no native sheet name")
    expression = property_link("Number")
    found = []
    note = sheet_view.GetFirstNote2()
    while note is not None:
        note = _early_bound(note, "INote")
        if source_property_expression(str(note.PropertyLinkedText)) == expression:
            found.append(note)
        note = note.GetNext()
    if len(found) != 1:
        raise RuntimeError(
            f"leadscrew Number requires exactly one source-linked note; got {len(found)}"
        )
    number = found[0]
    assert_linked_value(
        expression, expected_number, str(number.PropertyLinkedText),
        str(number.GetText()), label="Number",
    )
    number_check = _fit_title_note(
        adapter, draw, sheet, number, label="Number", minimum=0.003,
    )

    def settled() -> None:
        current = _early_bound(ddoc.GetCurrentSheet(), "ISheet")
        actual_name = str(current.GetName()) if current is not None else None
        if actual_name != sheet_name:
            raise RuntimeError(
                f"leadscrew Number current sheet changed: "
                f"{actual_name!r} != {sheet_name!r}"
            )
        number_check()

    return settled


def _assert_installed_source_state(
    adapter: Any, source_model: Any, installed_configuration: str, *, stage: str
) -> None:
    """Observe the still-live source, never closed drawing/view handles."""
    configuration = active_configuration_name(adapter, source_model)
    read_only = source_model.IsOpenedReadOnly()
    path = str(source_model.GetPathName())
    if (
        configuration != installed_configuration
        or read_only is not True
        or SOURCE.resolve() != Path(path).resolve()
    ):
        raise RuntimeError(
            f"leadscrew source {stage}: installed source state changed: "
            f"configuration={configuration!r}; expected={installed_configuration!r}; "
            f"read_only={read_only!r}; path={path!r}"
        )


async def build(adapter: Any) -> dict[str, str]:
    """Preserve source bytes and installed configuration on success or refusal."""
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")
    source_sha256 = _source_file_sha256(SOURCE)
    with _preserve_reference_source_file(
        SOURCE, source_sha256, label="leadscrew modified-stock drawing"
    ):
        source_model = _open_supplier_source_read_only(
            adapter, SOURCE, label="open cut leadscrew"
        )
        installed_configuration = active_configuration_name(adapter, source_model)
        if installed_configuration in ("", supplier.SUPPLIER_STOCK_CONFIGURATION):
            raise RuntimeError(
                "leadscrew source was saved without an installed configuration active: "
                f"{installed_configuration!r}"
            )
        primary = None
        try:
            return await _build_read_only_source(
                adapter, source_model, installed_configuration
            )
        except BaseException as error:
            primary = error
            raise
        finally:
            try:
                _assert_installed_source_state(
                    adapter, source_model, installed_configuration,
                    stage="drawing lifecycle exit",
                )
            except BaseException as integrity_error:
                if primary is None:
                    raise
                primary.add_note(
                    f"leadscrew source integrity check also failed: {integrity_error}"
                )


async def _build_read_only_source(
    adapter: Any, source_model: Any, installed_configuration: str
) -> dict[str, str]:
    if source_model.GetSaveFlag() is not False:
        raise RuntimeError("leadscrew source must be clean before view creation/capture")
    _assert_installed_source_state(
        adapter, source_model, installed_configuration, stage="before view creation"
    )
    required = (
        "Number",
        "Material Specification",
        "Finish",
        "Quantity",
        "Supplier",
        "Supplier SKUs",
    )
    properties = read_required_properties(
        adapter.currentModel, required, required=required
    )
    draw, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        draw,
        {
            0: PDF_TITLE,
            1: "Manufacturing controls for modified purchased stock",
            2: "Harmonic Analyzer Project",
            3: "MHA-CH-06-TL-VN-54; ZYLtech HW-SC-T8x2-600",
            4: "Native dimension-driven cut length and set-screw flats",
        },
    )
    main = place_view(adapter, str(SOURCE), "*Front", *MAIN_CENTER, scale=SHEET_SCALE)
    native = _early_bound(main, "IView")
    native.Angle = MAIN_VIEW_ANGLE
    if abs(math.remainder(float(native.Angle) - MAIN_VIEW_ANGLE, 2.0 * math.pi)) > 1e-9:
        raise RuntimeError("failed to turn the leadscrew view axis-horizontal")
    draw.EditRebuild3()
    _center_view(draw, main, MAIN_CENTER, "leadscrew view")
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    _center_view(draw, iso, ISO_CENTER, "leadscrew isometric")
    for view in (main, iso):
        set_hidden_lines_removed(adapter, view)
    # Capture while source geometry is clean, before any native text formatting.
    author_supplier_stock = _prepare_supplier_stock_inset(adapter)
    annotations = curate_view_dimensions(
        adapter,
        main,
        keep=MAIN_KEEP,
        view_label="cut length and flats",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    annotations += _add_clock_sections(adapter, main)
    annotations += _add_end_details(adapter, main)
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
            f"ITEM: {ITEM}",
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
    number_check = _fit_number_title_note(
        adapter, expected_number=properties["Number"],
    )
    supplier_stock_check: Callable[[], None] | None = None

    def checkpoint(stage: str) -> None:
        nonlocal supplier_stock_check
        if stage == "before_drawing_save":
            supplier_stock_check = author_supplier_stock()
            supplier_stock_check()
        elif stage in (
            "after_drawing_save", "after_pdf_save", "before_drawing_close",
        ):
            if supplier_stock_check is None:
                raise RuntimeError(f"supplier stock was not authored before {stage}")
            supplier_stock_check()
        if stage in (
            "before_drawing_save", "after_drawing_save",
            "after_pdf_save", "before_drawing_close",
        ):
            number_check()
        # An after-event observes an attempted operation, not a successful save.
        # The finalizer preserves any primary operation failure independently.
        if stage != "after_drawing_close":
            _assert_installed_source_state(
                adapter, source_model, installed_configuration, stage=stage,
            )

    artifacts = await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title=PDF_TITLE,
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        settled_checks=(
            number_check,
            lambda: _assert_installed_source_state(
                adapter, source_model, installed_configuration,
                stage="settled before drawing save",
            ),
        ),
        checkpoint=checkpoint,
    )
    # finalize_drawing has closed the drawing. Only PDF/file readers belong here.
    _assert_supplier_stock_pdf(OUTPUTS.pdf)
    return artifacts


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    parser.parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
