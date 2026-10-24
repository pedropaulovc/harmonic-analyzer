r"""Create the ten-sheet oblique-trammel jig fitter package (MHA-CH-06-TL-00).

Sheet 1 shows the jig assembled at the symmetric inner pass in the machine
frame: the plan (camera down Z) above the operator's elevation, each titled,
the plan tagging the carrier's pass holes A1-B2, both rails and the spindle
origin, beside the pose caption and the rail-alignment targets the fitter
indicates the pivot pins to; the elevation carries the one native dimension,
the CL dowel's round tip above the riser top as a reference (the builder's
hidden ``spec.CL_TIP_FEATURE``). Sheet 2 is the BOM: every fabricated and purchased
family from the part registry, numbered in the spec's BOM order with its full
description and total quantity, one line a row, on the left of the sheet; its
unballooned, collapsed parent view sits on the right above the title block.
Shared kit members retain three native configuration rows with the same
associative SH-VN-57 Number. A BOM-scoped key identifies their common purchased
SKU and maps the native items to named configurations and installed counts,
never kit purchase quantities. Its measured note box stays below the reference
view and clear of the rebuilt BOM, border and title block. Vendor Numbers have
their own 56 mm column. Sheets 3 to 6 show the builder-owned ``JIG_EXPLODED``
presentation with one sub-assembly's families only. Sheet 4 also has a collapsed
plan locator and two real assembled sections; both separated bearings carry
item 14 on the left exploded view's single balloon ring. Other families are
ballooned once. Sheets 7 and 8 are the assembly order, whose steps cite
fasteners by item number; one blank line parts each top-level step, and
Sheet 8 continues with step 13 and the checks under it. Sheet 9 carries the
cartridge bench work in print order (C2A,
C1-C2), with its signed functional inspection schematic, followed by feed
checks F1-F2. Sheet 10 carries cap seating/wiring (C3-C3C), then the actual
carrier and top capture fit (C4-C5D). The schematic is not a manufacturing
view or dimension. These four instruction sheets retain a small, visible
collapsed reference isometric at the largest measured fit from 1:20, 1:25
and 1:30 below the right-column text:
their native model views supply the live ``$PRPSHEET`` title-block links.
Sheet 11 carries operation/service (C6-C7), the hold-down stud measurement,
limits and installed acceptance (HD1-HD3), tooling clearance (C8) and machine acceptance, with the
finished isometric below the right-column checks at 1:15. Every
view is one the builder named in the machine frame (``spec.VIEW_AXES``), its
mapping proven on the sheet before anything is placed by it. Every text,
pose and reference value comes from
``ch_rocker_arm_tl_oblique_jig_assembly_spec`` (and through it the calculator
``ch_rocker_arm_tl_oblique_trammel_spec``) or the part registry; this recipe
only lays the sheets out. It never edits the source assembly or its explodes.
"""

from __future__ import annotations

import argparse
import math
import re
import sys
import textwrap
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable

import _config
import _telemetry
import ch_rocker_arm_tl_oblique_base_bar_spec as base_bar
import ch_rocker_arm_tl_oblique_jig_assembly_spec as spec
from _check import check
from _com import _bind, _early_bound
from _component_references import component_identity, component_reference_names
from _session import run_build
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    set_high_quality_shaded_with_edges,
)
from _drawing_balloon_display import rendered_balloon_circle
from _drawing_balloons import (
    BalloonAnchor,
    BalloonLanding,
    _spread_balloons,
    _view_component_leaves,
    add_component_bom_balloons,
    assert_balloon_landings,
    isolate_drawing_view_components,
)
from _drawing_dimension_import import curate_view_dimensions
from _drawing_detail_crop import native_circle_geometry
from _drawing_dimensions import (
    assert_imported_precision,
    offset_dimension_text,
    set_reference_dimension,
)
from _drawing_hidden_sketches import _show_base_view_sketches
from _drawing_layout_check import LeaderSegment, _segment_crosses_box, find_leader_leader_crossings
from _drawing_tables import (
    bom_row_identities,
    insert_bom_table,
    validate_bom_number_property,
)
from _drawing_sections import create_section_view
from _drawing_scan import _HIT_ZOOM_HALF, _zoomed_on
from _drawing_attachment import _assert_attached_to, _assert_leader_lands
from _section_axis import position_section_caption
from _drawing_view_configuration import (
    ASSEMBLY_VIEW_CONFIGURATION,
    SIMPLIFIED_MAX_SCALE,
    SIMPLIFIED_VIEW_CONFIGURATION,
    ViewRole,
    apply_view_configuration,
    assert_full_detail_view,
    set_view_exploded_state,
)
from _drawing_view_display import set_hidden_lines_removed
from _drawing_leader_notes import add_leader_note
from _drawing_projection import model_point_in_view, model_points_in_view
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME, DrawingLayout
from _simplified_names import simplified_name
from _layout_audit import display_box
from solidworks_mcp.adapters.solidworks.drawing import add_note, place_view
from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.pywin32_adapter import null_callout


SPEC = DRAWINGS_BY_NAME["ch_rocker_arm_tl_oblique_jig_assembly"]
ARTIFACT_STEM = SPEC.artifact_stem
SOURCE = SPEC.source
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"],
    pdf=SPEC.outputs["pdf"],
    png=SPEC.outputs["png"],
)
SLDDRW = OUTPUTS.slddrw
PDF = OUTPUTS.pdf
PNG = OUTPUTS.png

ASSEMBLED_SHEET = "ASSEMBLED AT INNER PASS"
BOM_SHEET = "BILL OF MATERIALS"
STEPS_SHEET = "ASSEMBLY STEPS"
STEPS_CONTINUED_SHEET = "ASSEMBLY STEPS CONTINUED"
CARTRIDGE_SHEET = "CARTRIDGEASSEMBLY"
TOP_CAPTURE_SHEET = "TOPCAPTUREFIT"
CAPTURE_SHEET = "CAPTUREANDOPERATION"
PIVOT_CAPTURE_SHEET = "PIVOTCAPTUREEXPLODED"


@dataclass(frozen=True)
class Cluster:
    """One exploded sheet: the families its view shows, each ballooned there
    and on no other sheet, under its caption's title."""

    sheet: str
    title: str
    stems: tuple[str, ...]
    scale: tuple[float, float]  # placed at; the ring fit then picks its scale
    # Instances shown for what the families mate to, ballooned on their own
    # family's sheet, not here.
    context: tuple[str, ...] = ()


# All 31 logical families on one exploded view at 1:10 read as a crowd whose leaders
# converged and crossed, and the small screws could not be told apart (blind
# review r4). So each sub-assembly explodes on its own sheet: what stands on
# the table and rides its rails, the feed bolted along rail 1 and onto pivot
# block 1, and what rides the pins. Each family belongs to one ballooned
# cluster sheet, in BOM order; Sheet 4 repeats only the separated bearing.
# Each initial scale fits the largest ladder rung holding its measured ring.
CLUSTERS = (
    Cluster(
        "RAIL BARS EXPLODED",
        "BASE BARS, RAILS, CARRIAGES AND PIVOT BLOCKS",
        (
            spec.BASE_BAR,
            spec.PIVOT_BLOCK,
            spec.RAIL,
            spec.CARRIAGE,
            spec.HOLD_DOWN_STUD,
            spec.T_NUT,
            spec.FLANGE_NUT,
            spec.RAIL_SCREW,
            spec.CARRIAGE_SCREW,
        ),
        (1.0, 5.0),
    ),
    Cluster(
        PIVOT_CAPTURE_SHEET,
        "BIDIRECTIONAL CAPTURED PIVOT CARTRIDGES",
        (
            spec.PIVOT_PIN,
            spec.PIVOT_CAP,
            spec.PIVOT_RETAINER,
            spec.BEARING,
            spec.PIVOT_CAP_SCREW,
            spec.PIVOT_CLEVIS_PIN,
            spec.PIVOT_COTTER,
            spec.PIVOT_LOCK_WIRE,
        ),
        (1.0, 4.0),
        context=tuple(spec.instance_name(spec.PIVOT_BLOCK, index) for index in (0, 1)),
    ),
    Cluster(
        "LEADSCREW FEED EXPLODED",
        "LEADSCREW FEED",
        (
            spec.END_BRACKET,
            spec.NUT_BRACKET,
            spec.LEADSCREW,
            spec.LEADSCREW_NUT,
            spec.PILLOW_BLOCK,
            spec.HANDWHEEL,
            spec.BRACKET_SCREW,
            spec.BLOCK_SCREW,
            spec.PILLOW_BLOCK_SCREW,
            spec.NUT_SCREW,
            spec.BLOCK_LOCK_WASHER,
        ),
        (1.0, 3.0),
        # Review full-bought (owner ruling 2026-10-18): the nut bracket and its
        # block screws read against rail 1's pivot block, the face they mate to.
        context=(spec.lock_parent(spec.NUT_BRACKET, 0),),
    ),
    Cluster(
        "CARRIER EXPLODED",
        "CARRIER, RISER AND FEED LEVER",
        (
            spec.CARRIER,
            spec.RISER,
            spec.HUB_PIN,
            spec.FEED_LEVER,
            spec.CL_DOWEL,
            spec.RISER_SCREW,
            spec.CLAMP_SCREW,
            spec.LEVER_SCREW,
            spec.LEVER_LOCK_WASHER,
        ),
        (1.0, 5.0),
    ),
)
SHEET_NAMES = (
    ASSEMBLED_SHEET,
    BOM_SHEET,
    *(cluster.sheet for cluster in CLUSTERS),
    STEPS_SHEET,
    STEPS_CONTINUED_SHEET,
    CARTRIDGE_SHEET,
    TOP_CAPTURE_SHEET,
    CAPTURE_SHEET,
)
# The captions cite sheets by these numbers, never typed ones.
BOM_SHEET_NUMBER = SHEET_NAMES.index(BOM_SHEET) + 1
STEPS_SHEET_NUMBER = SHEET_NAMES.index(STEPS_SHEET) + 1
TOP_CAPTURE_SHEET_NUMBER = SHEET_NAMES.index(TOP_CAPTURE_SHEET) + 1
# The spec's steps type their instruction sheets' numbers, and the stud drawing
# prints spec.HOLD_DOWN_REFERENCE: sheets 8-11 must keep these places.
if (
    SHEET_NAMES.index(STEPS_CONTINUED_SHEET) + 1,
    SHEET_NAMES.index(CARTRIDGE_SHEET) + 1,
    TOP_CAPTURE_SHEET_NUMBER,
    SHEET_NAMES.index(CAPTURE_SHEET) + 1,
) != (8, 9, 10, spec.OPERATION_SHEET_NUMBER):
    raise AssertionError("the steps' typed instruction-sheet numbers moved")
if SPEC.layout is not DrawingLayout.LANDSCAPE:
    raise AssertionError("the jig's primary sheet must remain landscape")
# The jig is about 970 x 435 in plan: 1:4 for the arrangement, 1:15 for the
# finished isometric on the capture sheet, at most 1:20 for the instruction
# references, and 1:6 for the BOM's collapsed reference right of the table.
ASSEMBLED_SCALE = (1.0, 4.0)
REFERENCE_SCALE = (1.0, 6.0)
ISOMETRIC_SCALE = (1.0, 15.0)
NOTES_REFERENCE_SCALE = (1.0, 20.0)
NOTES_REFERENCE_SCALE_LADDER = (
    NOTES_REFERENCE_SCALE,
    (1.0, 25.0),
    (1.0, 30.0),
)
# The exploded clusters' scales, largest first. Every one is at most 1:2, so
# every rung references the simplified configuration (the view policy) and
# re-scaling a cluster never switches its configuration or its explode.
CLUSTER_SCALE_LADDER = (
    (1.0, 3.0),
    (1.0, 4.0),
    (1.0, 5.0),
    (1.0, 6.0),
    (1.0, 8.0),
    (1.0, 10.0),
)
if any(n / d > SIMPLIFIED_MAX_SCALE for n, d in CLUSTER_SCALE_LADDER):
    raise AssertionError("a cluster scale would switch the view's configuration")
if any(cluster.scale not in CLUSTER_SCALE_LADDER for cluster in CLUSTERS):
    raise AssertionError("every cluster is placed at a ladder scale")


def package_sheet_scales(
    cluster_scales: Mapping[str, tuple[float, float]],
) -> dict[str, tuple[float, float]]:
    """Every sheet's scale, the clusters' as fitted, in sheet order."""
    if set(cluster_scales) != {cluster.sheet for cluster in CLUSTERS}:
        raise ValueError(f"cluster scales {sorted(cluster_scales)!r} != the clusters")
    fixed = {
        ASSEMBLED_SHEET: ASSEMBLED_SCALE,
        BOM_SHEET: REFERENCE_SCALE,
        STEPS_SHEET: NOTES_REFERENCE_SCALE,
        STEPS_CONTINUED_SHEET: NOTES_REFERENCE_SCALE,
        CARTRIDGE_SHEET: NOTES_REFERENCE_SCALE,
        TOP_CAPTURE_SHEET: NOTES_REFERENCE_SCALE,
        CAPTURE_SHEET: ISOMETRIC_SCALE,
    }
    return {
        name: cluster_scales[name] if name in cluster_scales else fixed[name]
        for name in SHEET_NAMES
    }



# Sheet geometry, metres: the template's inner border and the title block in
# its lower-right corner. Every view outline and balloon ring stays inside the
# border and out of the title block (drawing-guidelines.md rule 13).
_TEMPLATE = DRAWING_TEMPLATES[DrawingLayout.LANDSCAPE]
SHEET_INNER_BORDER = (
    0.0127,
    0.0127,
    _TEMPLATE.width_m - 0.0127,
    _TEMPLATE.height_m - 0.0127,
)
TITLE_BLOCK = (
    _TEMPLATE.title_block_left_m,
    0.0,
    _TEMPLATE.width_m,
    _TEMPLATE.title_block_top_m,
)

# Sheet 1: the plan over the operator's elevation, third-angle and on one
# vertical, right of the pose caption; the alignment targets under the
# elevation, left of the title block. At 1:4 the plan is about 241 x 106 and
# the elevation 241 x 31 (the handwheel and the screw heads included). Each
# view's title stands centred under it.
PLAN_CENTER = (0.274, 0.205)
ELEVATION_CENTER = (0.274, 0.125)
CAPTION_XY = (0.018, 0.255)
CAPTION_WIDTH = 46  # characters; default-format note text, left of the plan
ALIGNMENT_XY = (0.018, 0.105)
ALIGNMENT_WIDTH = 68  # characters; stops left of the title block
# Default-format note text: about 2.9 mm a character on the farm's templates.
NOTE_CHAR_M = 0.0029
VIEW_LABEL_GAP = 0.003


def _label_under(center: tuple[float, float], height_mm: float, text: str):
    """Top-left of ``text`` centred under a 1:4 view ``height_mm`` tall."""
    half = height_mm / 1000.0 * ASSEMBLED_SCALE[0] / ASSEMBLED_SCALE[1] / 2.0
    return (
        center[0] - len(text) * NOTE_CHAR_M / 2.0,
        center[1] - half - VIEW_LABEL_GAP,
    )


(_EX0, _EX1), (_EY0, _EY1), (_EZ0, _EZ1) = spec.MODEL_EXTENT
PLAN_LABEL_XY = _label_under(PLAN_CENTER, _EY1 - _EY0, spec.PLAN_VIEW_LABEL)
ELEVATION_LABEL_XY = _label_under(
    ELEVATION_CENTER, _EZ1 - _EZ0, spec.ELEVATION_VIEW_LABEL
)

# The elevation's one dimension: the CL dowel's round tip above the riser top
# (``spec.CL_TIP_LINE``), imported from the builder's hidden CL_TIP_FEATURE
# and parenthesised as a reference; step 11 sets the tip against the actual
# riser. Its 1.6 is 0.4 mm on the sheet at 1:4, too short to hold its text.
# Offset the imported text independently of its dimension/witness lines:
# 80 model mm left and 28 above the tip gives it a clear lane above the
# left pivot, below the plan, rather than across the retainer geometry.
CL_TIP_TEXT_MODEL_MM = (
    spec.CL_TIP_LINE[1][0] - 80.0,
    0.0,
    spec.CL_TIP_LINE[1][1] + 28.0,
)
# The dimension line stays near the dowel; only its value is carried into
# the clear text lane. Curation places the whole dimension before offsetting.
CL_TIP_LINE_MODEL_MM = (
    spec.CL_TIP_LINE[1][0] - 12.0,
    0.0,
    sum(point[1] for point in spec.CL_TIP_LINE) / 2.0,
)

# Sheet 2: the full-height BOM left, its collapsed reference right. The table
# can extend below the title block's top because it stays left of that block.
# Keep legible 5.5 mm rows and default-format text; reallocate 8 mm of the
# former description column to the Number column: full 18-character vendor
# Numbers need 52.2 mm at the unchanged default format. Both text columns
# retain 2 mm horizontal clearance. Native table bounds are checked after rebuild.
# Table text runs about 2.9 mm a character.
BOM_CHAR_M = 0.0029
BOM_CELL_PADDING_M = 0.002  # total horizontal clearance inside each text column
BOM_COLUMN_WIDTHS = {
    "item": 0.012,
    "part": 0.056,
    "description": 0.110,
    "quantity": 0.012,
}
BOM_DESCRIPTION_MAX_CHARS = int(
    (BOM_COLUMN_WIDTHS["description"] - BOM_CELL_PADDING_M) / BOM_CHAR_M
)
BOM_ROW_HEIGHT = 0.0055
BOM_SHEET_CLEARANCE = 0.003  # visible air at the border and title block
BOM_ANCHOR = (0.018, 0.260)
REGION_GAP = 0.006  # between a view's room and the text beside it
# The reference fits the right column with its native top aligned to the BOM,
# leaving the lower blank area for the measured configured-kit key.
REFERENCE_REGION = (
    BOM_ANCHOR[0] + sum(BOM_COLUMN_WIDTHS.values()) + REGION_GAP,
    TITLE_BLOCK[3] + BOM_SHEET_CLEARANCE,
    SHEET_INNER_BORDER[2],
    BOM_ANCHOR[1],
)

# Sheets 3-6: one cluster's exploded isometric each, its balloon ring inside
# the border, over the caption, its low arc clear of the title block.
BALLOON_MARGIN = 0.024
# A ring places each balloon's CENTRE margin outside the view outline; its
# ink reaches a radius further (draw_dt_drive_train_assembly's ring reach).
BALLOON_RADIUS = 0.005
BALLOON_RING_REACH = BALLOON_MARGIN + BALLOON_RADIUS
EXPLODED_CAPTION_XY = (0.018, 0.030)
EXPLODED_CAPTION_WIDTH = 68  # characters; stops left of the title block
# Each cluster view's ring room: inside the border, over the caption. The
# ring is centred in it, then slid left until its low arc clears the title
# block (TITLE_BLOCK_KEEP_OUT).
CLUSTER_RING_REGION = (
    SHEET_INNER_BORDER[0],
    EXPLODED_CAPTION_XY[1] + 0.003,
    SHEET_INNER_BORDER[2],
    SHEET_INNER_BORDER[3],
)
CLUSTER_CENTER = (
    (CLUSTER_RING_REGION[0] + CLUSTER_RING_REGION[2]) / 2.0,
    (CLUSTER_RING_REGION[1] + CLUSTER_RING_REGION[3]) / 2.0,
)
TITLE_BLOCK_KEEP_OUT = (
    TITLE_BLOCK[0] - BOM_SHEET_CLEARANCE,
    TITLE_BLOCK[1],
    TITLE_BLOCK[2],
    TITLE_BLOCK[3] + BOM_SHEET_CLEARANCE,
)
# Sheet 4 keeps its reviewed left exploded field and uses the former duplicate
# field for a visible assembled locator, a longitudinal section and one small
# bolt-seat section. These four actual views have independent measured scales.
CAPTURE_EXPLODED_REGION = (
    CLUSTER_RING_REGION[0] + BOM_SHEET_CLEARANCE,
    TITLE_BLOCK_KEEP_OUT[3] + BOM_SHEET_CLEARANCE,
    CLUSTER_CENTER[0] - REGION_GAP,
    CLUSTER_RING_REGION[3] - BOM_SHEET_CLEARANCE,
)
CAPTURE_READING_REGION = (
    CLUSTER_CENTER[0] + REGION_GAP,
    TITLE_BLOCK_KEEP_OUT[3] + BOM_SHEET_CLEARANCE,
    CLUSTER_RING_REGION[2] - BOM_SHEET_CLEARANCE,
    CLUSTER_RING_REGION[3] - BOM_SHEET_CLEARANCE,
)
CAPTURE_VIEW_REGIONS = (
    CAPTURE_EXPLODED_REGION,
    (0.224, 0.220, 0.278, 0.263),
    (0.278, 0.119, 0.364, 0.211),
    (0.360, 0.226, 0.403, 0.261),
)
CAPTURE_LOCATOR_SCALE = (1, 4)
CAPTURE_SECTION_CAPTIONS = ((0.302, 0.115), (0.360, 0.222))
CAPTURE_NOTE_HEIGHT = 0.002


# Sheet 7: the assembly sequence in two columns of one width, the heading and
# as many whole steps as fit the left column, which runs down beside the
# title block; the rest atop the right column. Sheet 8 continues it with the
# last step and the checks under it. One blank line parts each top-level step.
# Sheets 9 and 10 reuse that layout for cartridge assembly and actual top
# capture fit. Sheet 11 separates operation and acceptance, leaving real
# bottom-right room for the finished isometric.
# 4.525 mm line pitch and about 2.9 mm a character.
NOTE_LINE_M = 0.004525
STEPS_LINE_WIDTH = 68  # characters; 197 mm, either column
STEPS_HEADING = "ASSEMBLY SEQUENCE"
STEPS_XY = (0.018, 0.262)
# The left column ends 4 mm over the inner border at the 4.525 mm pitch; farm
# r17's sheet 6 printed this note at 4.34 mm a line, so the real gap is wider.
STEPS_FLOOR = SHEET_INNER_BORDER[1] + 0.004
STEPS_CONTINUED_XY = (0.220, 0.262)
if STEPS_XY[0] + STEPS_LINE_WIDTH * NOTE_CHAR_M >= min(
    STEPS_CONTINUED_XY[0], TITLE_BLOCK[0]
):
    raise AssertionError("the steps' left column runs into the right one")

BOM_QUANTITIES = {stem: spec.QUANTITIES[stem] for stem in spec.BOM_ORDER}
BOM_COMPONENTS = tuple(BOM_QUANTITIES)
BOM_COMPONENT_IDENTITIES = dict(spec.COMPONENT_IDENTITIES)
_CLUSTERED = [stem for cluster in CLUSTERS for stem in cluster.stems]
if sorted(_CLUSTERED) != sorted(BOM_COMPONENTS):
    raise AssertionError("the clusters must partition the BOM's families")
# Literal stems, so the config-dependency analysis reads exactly these rows.
PART_ROWS = {
    "ch-rocker-arm-tl-oblique-base-bar": _config.parts(
        "ch-rocker-arm-tl-oblique-base-bar"
    ),
    "ch-rocker-arm-tl-oblique-carrier": _config.parts(
        "ch-rocker-arm-tl-oblique-carrier"
    ),
    "ch-rocker-arm-tl-oblique-pivot-block": _config.parts(
        "ch-rocker-arm-tl-oblique-pivot-block"
    ),
    "ch-rocker-arm-tl-oblique-pivot-pin": _config.parts(
        "ch-rocker-arm-tl-oblique-pivot-pin"
    ),
    "ch-rocker-arm-tl-oblique-riser": _config.parts("ch-rocker-arm-tl-oblique-riser"),
    "ch-rocker-arm-tl-oblique-hub-pin": _config.parts(
        "ch-rocker-arm-tl-oblique-hub-pin"
    ),
    "ch-rocker-arm-tl-oblique-feed-lever": _config.parts(
        "ch-rocker-arm-tl-oblique-feed-lever"
    ),
    "ch-rocker-arm-tl-oblique-end-bracket": _config.parts(
        "ch-rocker-arm-tl-oblique-end-bracket"
    ),
    "ch-rocker-arm-tl-oblique-nut-bracket": _config.parts(
        "ch-rocker-arm-tl-oblique-nut-bracket"
    ),
    "ch-rocker-arm-tl-oblique-pivot-cap": _config.parts(
        "ch-rocker-arm-tl-oblique-pivot-cap"
    ),
    "ch-rocker-arm-tl-oblique-pivot-retainer": _config.parts(
        "ch-rocker-arm-tl-oblique-pivot-retainer"
    ),
    "ch-rocker-arm-tl-vn-oblique-rail": _config.parts("ch-rocker-arm-tl-vn-oblique-rail"),
    "ch-rocker-arm-tl-vn-oblique-carriage": _config.parts(
        "ch-rocker-arm-tl-vn-oblique-carriage"
    ),
    "ch-rocker-arm-tl-vn-oblique-bearing": _config.parts(
        "ch-rocker-arm-tl-vn-oblique-bearing"
    ),
    "ch-rocker-arm-tl-vn-oblique-cl-dowel": _config.parts(
        "ch-rocker-arm-tl-vn-oblique-cl-dowel"
    ),
    "ch-rocker-arm-tl-vn-oblique-leadscrew": _config.parts(
        "ch-rocker-arm-tl-vn-oblique-leadscrew"
    ),
    "ch-rocker-arm-tl-vn-oblique-leadscrew-nut": _config.parts(
        "ch-rocker-arm-tl-vn-oblique-leadscrew-nut"
    ),
    "ch-rocker-arm-tl-vn-oblique-pillow-block": _config.parts(
        "ch-rocker-arm-tl-vn-oblique-pillow-block"
    ),
    "ch-rocker-arm-tl-vn-oblique-handwheel": _config.parts(
        "ch-rocker-arm-tl-vn-oblique-handwheel"
    ),
    "sh-vn-clamping-kit-hardware--HoldDownStud": _config.parts(
        "sh-vn-clamping-kit-hardware"
    ),
    "sh-vn-clamping-kit-hardware--TNut": _config.parts(
        "sh-vn-clamping-kit-hardware"
    ),
    "sh-vn-clamping-kit-hardware--FlangeNut": _config.parts(
        "sh-vn-clamping-kit-hardware"
    ),
    "ch-rocker-arm-tl-vn-oblique-rail-screw": _config.parts(
        "ch-rocker-arm-tl-vn-oblique-rail-screw"
    ),
    "ch-rocker-arm-tl-vn-oblique-bracket-screw": _config.parts(
        "ch-rocker-arm-tl-vn-oblique-bracket-screw"
    ),
    "ch-rocker-arm-tl-vn-oblique-block-screw": _config.parts(
        "ch-rocker-arm-tl-vn-oblique-block-screw"
    ),
    "ch-rocker-arm-tl-vn-oblique-carriage-screw": _config.parts(
        "ch-rocker-arm-tl-vn-oblique-carriage-screw"
    ),
    "ch-rocker-arm-tl-vn-oblique-kp08-screw": _config.parts(
        "ch-rocker-arm-tl-vn-oblique-kp08-screw"
    ),
    "ch-rocker-arm-tl-vn-oblique-nut-screw": _config.parts(
        "ch-rocker-arm-tl-vn-oblique-nut-screw"
    ),
    "ch-rocker-arm-tl-vn-oblique-riser-screw": _config.parts(
        "ch-rocker-arm-tl-vn-oblique-riser-screw"
    ),
    "ch-rocker-arm-tl-vn-oblique-clamp-screw": _config.parts(
        "ch-rocker-arm-tl-vn-oblique-clamp-screw"
    ),
    "ch-rocker-arm-tl-vn-oblique-lever-screw": _config.parts(
        "ch-rocker-arm-tl-vn-oblique-lever-screw"
    ),
    "ch-rocker-arm-tl-vn-oblique-block-washer": _config.parts(
        "ch-rocker-arm-tl-vn-oblique-block-washer"
    ),
    "ch-rocker-arm-tl-vn-oblique-lever-washer": _config.parts(
        "ch-rocker-arm-tl-vn-oblique-lever-washer"
    ),
    "ch-rocker-arm-tl-vn-oblique-pivot-cap-screw": _config.parts(
        "ch-rocker-arm-tl-vn-oblique-pivot-cap-screw"
    ),
    "ch-rocker-arm-tl-vn-oblique-pivot-clevis-pin": _config.parts(
        "ch-rocker-arm-tl-vn-oblique-pivot-clevis-pin"
    ),
    "ch-rocker-arm-tl-vn-oblique-pivot-cotter": _config.parts(
        "ch-rocker-arm-tl-vn-oblique-pivot-cotter"
    ),
    "ch-rocker-arm-tl-vn-oblique-pivot-lock-wire": _config.parts(
        "ch-rocker-arm-tl-vn-oblique-pivot-lock-wire"
    ),
}
if set(PART_ROWS) != set(BOM_COMPONENTS):
    raise AssertionError("BOM registry rows must cover exactly the assembly families")
BOM_PART_NUMBERS = {stem: str(row["number"]) for stem, row in PART_ROWS.items()}
BOM_DESCRIPTIONS = dict(spec.BOM_DESCRIPTIONS)
if max(map(len, BOM_DESCRIPTIONS.values())) > BOM_DESCRIPTION_MAX_CHARS:
    raise AssertionError("every BOM description must print on one line")
# The steps cite items by number, so the BOM must number its rows exactly as
# the spec does (BOM_ORDER); the recipe refuses any other numbering.
BOM_ITEM_NUMBERS = dict(spec.ITEM_NUMBERS)

# One balloon per BOM row, except Sheet 4's two distinct bearing occurrences
# both carry item 14. All capture landings share the same ring and proofs.
BALLOON_ANCHORS = {stem: BalloonAnchor() for stem in BOM_COMPONENTS}
for _family in spec.KIT_IDENTITIES:
    BALLOON_ANCHORS[_family] = BalloonAnchor(instance=spec.instance_name(_family, 0))
# The base bar's walk landed on rail 2's carriage end seal (review r5): its
# balloon lands on bar 1's long top edge on the operator's side (part +Y,
# ``HIGH_SIDE_Y``, z ``BAR_THICK``), the edge nearest the viewer, 200 from the
# spindle end: what stands on the bar sits behind and above it on the sheet,
# what hangs under it below. The bottom edge 300 out (bought-r15) selected no
# edge on the sheet once C4 widened the bar to 1/2 x 6 (bought-r16).
BALLOON_ANCHORS[spec.BASE_BAR] = BalloonAnchor(
    point_mm=(200.0, base_bar.HIGH_SIDE_Y, base_bar.BAR_THICK)
)
# Keep the rail and T-nut arrows away from the two bars' overlapping inner
# ends. Both remain native edge-attached balloons: the frozen picks must hit
# the requested instance's own visible ink, and their final landings are
# rechecked after the last rebuild.
BALLOON_ANCHORS[spec.RAIL] = BalloonAnchor(
    point_mm=(
        sum(spec.guide_rail.HOLE_X[-2:]) / 2.0,
        max(y for y, z in spec.guide_rail.SECTION if z == spec.guide_rail.HEIGHT),
        spec.guide_rail.HEIGHT,
    ),
    instance=spec.instance_name(spec.RAIL, 0),
)
BALLOON_ANCHORS[spec.T_NUT] = BalloonAnchor(
    point_mm=(0.0, spec.t_nut.FOOT_HEIGHT, spec.t_nut.FOOT_WIDTH / 2.0),
    instance=spec.instance_name(spec.T_NUT, len(spec.T_NUT_PLACEMENTS) - 1),
)

EXPLODED_VIEW_NAMES = {
    ASSEMBLY_VIEW_CONFIGURATION: spec.EXPLODED_VIEW_NAME,
    SIMPLIFIED_VIEW_CONFIGURATION: simplified_name(spec.EXPLODED_VIEW_NAME),
}
if spec.SOURCE_CONFIGURATION != ASSEMBLY_VIEW_CONFIGURATION:
    raise AssertionError("the jig explode is authored in Default")


# Glues an item citation ("ITEM 22") and a value with its unit ("3.5 N·m",
# "25 IN·LBF") into one word while wrapping, so the fitter never reads "ITEM"
# or a number at a line end and what it belongs to on the next.
_UNBROKEN = re.compile(r"\bITEM (?=\d)|(?<=\d) (?=N·m|IN·LBF)")
_GLUE = "\x00"
# A step's label: its number, or a sub-step's ("7A").
_STEP_LABEL = re.compile(r"\d+[A-Z]?")
# Any labelled line's top-level step: "7" of 7A, "C3" of C3B, "HD1" itself.
_STEP_GROUP = re.compile(r"([A-Z]*\d+)[A-Z]?")


def _step_group(line: str) -> str | None:
    number, sep, _rest = line.partition(". ")
    match = _STEP_GROUP.fullmatch(number) if sep else None
    return match[1] if match else None


def _wrapped(
    lines: tuple[str, ...],
    *,
    width: int,
    heading: str | None = None,
    spaced: bool = False,
) -> str:
    """Wrap each numbered line (a step or sub-step) under its own label; one
    note per block. A hyphenated word (HOLD-DOWNS, A1-B1), an item citation
    (ITEM 22) and a torque (3.5 N·m) stay whole on their line. ``spaced``
    parts consecutive top-level steps (6 then 7A, C3 then C4) with one blank
    line; sub-steps (7B, C3A) and unlabelled lines stay tight, and a group
    heading ("...:") takes the blank above its first step."""
    out = [heading] if heading else []
    previous = None  # the last printed step's group; None opening a group
    for line in (
        _UNBROKEN.sub(lambda m: m.group(0).replace(" ", _GLUE), text) for text in lines
    ):
        group = _step_group(line)
        opens = group is None and line.endswith(":")
        if spaced and previous is not None and (opens or group not in (None, previous)):
            out.append("")
        if opens or group is not None:
            previous = group
        number, sep, rest = line.partition(". ")
        if sep and _STEP_LABEL.fullmatch(number):
            out += textwrap.wrap(
                rest,
                width=width,
                initial_indent=f"{number}. ",
                subsequent_indent=" " * (len(number) + 2),
                break_on_hyphens=False,
            )
        else:
            out += textwrap.wrap(
                line, width=width, subsequent_indent="   ", break_on_hyphens=False
            )
    return "\n".join(out).replace(_GLUE, " ")


ASSEMBLED_CAPTION = _wrapped((spec.ASSEMBLED_CAPTION,), width=CAPTION_WIDTH)
ALIGNMENT_NOTE = _wrapped(
    (*spec.ALIGNMENT_NOTE_LINES, spec.SWEEP_NOTE_LINE), width=ALIGNMENT_WIDTH
)


def _note_height(text: str) -> float:
    return (text.count("\n") + 1) * NOTE_LINE_M if text else 0.0


@dataclass(frozen=True)
class StepsLayout:
    """Two-column instructions, with checks below the steps they follow."""

    steps: str  # the heading and the steps the left column holds
    continued: str  # the rest, atop the right column; "" when none
    checks: str
    checks_xy: tuple[float, float]
    room_top: float  # the right column's free room starts below its text


def steps_sheet_layout(
    steps: Sequence[str], checks: Sequence[str], *, heading: str = STEPS_HEADING
) -> StepsLayout:
    """Lay out the heading and whole steps above ``STEPS_FLOOR`` in the left
    column, the rest atop the right column, and the checks below them: under
    the left column when every step fits it and so do they, else in the right.
    The reference views use the unused right-column room without reflowing text."""
    for count in range(len(steps), 0, -1):
        # Keep an instruction-group heading with its first complete step.
        if count < len(steps) and steps[count - 1].endswith(":"):
            continue
        left = _wrapped(
            tuple(steps[:count]), width=STEPS_LINE_WIDTH, heading=heading, spaced=True
        )
        if _note_height(left) <= STEPS_XY[1] - STEPS_FLOOR:
            break
    else:
        raise ValueError("the first assembly step overruns the steps' left column")
    continued = _wrapped(tuple(steps[count:]), width=STEPS_LINE_WIDTH, spaced=True)
    checks_text = _wrapped(tuple(checks), width=STEPS_LINE_WIDTH, spaced=True)
    x, top = STEPS_CONTINUED_XY
    below_left = STEPS_XY[1] - _note_height(left) - REGION_GAP
    if (
        checks_text
        and not continued
        and below_left - _note_height(checks_text) >= STEPS_FLOOR
    ):
        return StepsLayout(
            left, "", checks_text, (STEPS_XY[0], below_left), top - REGION_GAP
        )
    if continued:
        top -= _note_height(continued) + REGION_GAP
    if top - _note_height(checks_text) < TITLE_BLOCK[3] + BOM_SHEET_CLEARANCE:
        raise ValueError("instruction checks overrun the right column")
    return StepsLayout(
        left,
        continued,
        checks_text,
        (x, top),
        top - _note_height(checks_text) - REGION_GAP,
    )


# Spaced, steps 10-13D and the checks would leave the sheet 7 reference too
# little room, so sheet 8 continues the sequence: step 13 (13A-13D) moves
# whole, with the checks its 13C cites below it.
_FINAL_STEP = [_step_group(step) for step in spec.ASSEMBLY_STEPS].index(
    _step_group(spec.ASSEMBLY_STEPS[-1])
)
STEPS_LAYOUT = steps_sheet_layout(spec.ASSEMBLY_STEPS[:_FINAL_STEP], ())
STEPS_CONTINUED_LAYOUT = steps_sheet_layout(
    spec.ASSEMBLY_STEPS[_FINAL_STEP:],
    spec.ASSEMBLY_CHECKS,
    heading=f"{STEPS_HEADING} (CONT.)",
)
CARTRIDGE_LAYOUT = steps_sheet_layout(
    (*spec.CARTRIDGE_STEPS, "FEED FIT-UP CHECKS (F1-F2):", *spec.FEED_STEPS),
    (),
    heading="CARTRIDGE BENCH WORK: C2A, C1-C2",
)
TOP_CAPTURE_LAYOUT = steps_sheet_layout(
    (
        *spec.CAP_SEATING_STEPS,
        "CARRIER AND TOP RETAINERS (C4-C5D):",
        *spec.TOP_CAPTURE_STEPS,
    ),
    (),
    heading="CAP SEATING AND WIRING: C3-C3C",
)
CAPTURE_LAYOUT = steps_sheet_layout(
    spec.CAPTURE_STEPS,
    spec.CAPTURE_CHECKS,
    heading="OPERATION, STUD FIT AND CLEARANCE: C6-C8, HD1-HD3",
)
# Only this sheet has a finished view. Its room follows the filled right
# column, keeping the actual native outline clear of its checks and title.
FINISHED_REGION = (
    STEPS_CONTINUED_XY[0],
    TITLE_BLOCK[3] + BOM_SHEET_CLEARANCE + NOTE_LINE_M + VIEW_LABEL_GAP,
    SHEET_INNER_BORDER[2],
    CAPTURE_LAYOUT.room_top,
)

# draw_dt_drive_train_assembly._reference_iso keeps an actual collapsed model
# view on every instruction sheet for finalize_drawing's per-sheet
# CustomPropertyView association. Follow that visible-reference convention:
# no hidden/off-sheet geometry, copied property text or second instruction
# authority. The original notes and their placements above stay unchanged.
# Reserve one caption line below each reference, clear of the title block.
NOTES_REFERENCE_REGIONS = {
    sheet: (
        STEPS_CONTINUED_XY[0],
        TITLE_BLOCK[3] + BOM_SHEET_CLEARANCE + NOTE_LINE_M + VIEW_LABEL_GAP,
        SHEET_INNER_BORDER[2],
        layout.room_top,
    )
    for sheet, layout in (
        (STEPS_SHEET, STEPS_LAYOUT),
        (STEPS_CONTINUED_SHEET, STEPS_CONTINUED_LAYOUT),
        (CARTRIDGE_SHEET, CARTRIDGE_LAYOUT),
        (TOP_CAPTURE_SHEET, TOP_CAPTURE_LAYOUT),
    )
}
# C2A's functional section shares the unused right-column room with the live
# source-property view. Its exaggerated recess is explicitly not to scale:
# the source instruction and its minimum clearance govern, never sketch size.
CARTRIDGE_PAPER_REGION = NOTES_REFERENCE_REGIONS[CARTRIDGE_SHEET]
PIN_TIP_INSPECTION_REGION = (
    CARTRIDGE_PAPER_REGION[0],
    CARTRIDGE_PAPER_REGION[1],
    CARTRIDGE_PAPER_REGION[0] + 0.126,
    CARTRIDGE_PAPER_REGION[3],
)
NOTES_REFERENCE_REGIONS[CARTRIDGE_SHEET] = (
    PIN_TIP_INSPECTION_REGION[2] + REGION_GAP,
    CARTRIDGE_PAPER_REGION[1],
    CARTRIDGE_PAPER_REGION[2],
    CARTRIDGE_PAPER_REGION[3],
)
PIN_TIP_SECTION_DATUM_Y = PIN_TIP_INSPECTION_REGION[3] - 0.060
PIN_TIP_SECTION_TIP_Y = PIN_TIP_SECTION_DATUM_Y + 0.010
# A tenth of a micron admits native display-coordinate encoding, not a
# placement/scale allowance: every endpoint must match its intended paper
# point, not merely sit somewhere inside the much larger reserved region.
PIN_TIP_LOCATION_TOL_M = 1e-7
SHEET_LAYOUTS = {name: DrawingLayout.LANDSCAPE for name in SHEET_NAMES}
# The scales each sheet is created at; build() reports the fitted ones.
SHEET_SCALES = package_sheet_scales({c.sheet: c.scale for c in CLUSTERS})
SHEET_SCALE = SHEET_SCALES[ASSEMBLED_SHEET]



def pin_tip_inspection_lines() -> tuple[
    tuple[tuple[float, float], tuple[float, float]], ...
]:
    """Paper-only functional section: +Z points into the block, above Z=0."""
    x, _bottom, _right, top = PIN_TIP_INSPECTION_REGION
    datum, tip = PIN_TIP_SECTION_DATUM_Y, PIN_TIP_SECTION_TIP_Y
    upper = top - 0.027
    profiles = (
        # Block material either side of the open pin bore; mount faces at Z=0.
        ((x + 0.024, datum), (x + 0.024, upper),
         (x + 0.042, upper), (x + 0.042, datum)),
        # Open room beside the pin for the inspection bracket and its value.
        ((x + 0.104, datum), (x + 0.104, upper),
         (x + 0.122, upper), (x + 0.122, datum)),
        # The lowest pin tip stays on the +Z side, not in the carriage.
        ((x + 0.049, upper), (x + 0.049, tip),
         (x + 0.057, tip), (x + 0.057, upper)),
        # Ground bridge below the mount faces; its upper face is the datum line.
        ((x + 0.024, datum), (x + 0.024, datum - 0.003),
         (x + 0.122, datum - 0.003), (x + 0.122, datum)),
        # Feeler in the open recess; its paper thickness is not a model size.
        ((x + 0.048, datum + 0.002), (x + 0.060, datum + 0.002),
         (x + 0.060, datum + 0.004), (x + 0.048, datum + 0.004),
         (x + 0.048, datum + 0.002)),
    )
    pointers = []
    for _text, start, end in pin_tip_inspection_leaders():
        dx, dy = end[0] - start[0], end[1] - start[1]
        length = math.hypot(dx, dy)
        ux, uy = dx / length, dy / length
        # Native sheet-sketch arrowheads share the schematic's exact paper proof.
        back = (end[0] - 0.0015 * ux, end[1] - 0.0015 * uy)
        pointers.extend((
            (start, end),
            ((back[0] - 0.0006 * uy, back[1] + 0.0006 * ux), end),
            ((back[0] + 0.0006 * uy, back[1] - 0.0006 * ux), end),
        ))
    return (
        *((a, b) for profile in profiles for a, b in zip(profile, profile[1:])),
        ((x + 0.020, datum), (x + 0.124, datum)),
        ((x + 0.006, datum), (x + 0.006, upper)),
        ((x + 0.003, upper - 0.004), (x + 0.006, upper)),
        ((x + 0.009, upper - 0.004), (x + 0.006, upper)),
        # A drawn inspection bracket, not an imported/manufacturing dimension.
        ((x + 0.057, tip), (x + 0.072, tip)),
        ((x + 0.070, datum), (x + 0.070, tip)),
        ((x + 0.0685, datum), (x + 0.0715, datum)),
        ((x + 0.0685, tip), (x + 0.0715, tip)),
        ((x + 0.070, (datum + tip) / 2.0),
         (x + 0.073, (datum + tip) / 2.0)),
        *pointers,
    )


def pin_tip_inspection_leaders() -> tuple[
    tuple[str, tuple[float, float], tuple[float, float]], ...
]:
    """Each feature caption's pointer starts outside its text and ends on the ink."""
    x, _bottom, _right, top = PIN_TIP_INSPECTION_REGION
    datum = PIN_TIP_SECTION_DATUM_Y
    return (
        ("PIN", (x + 0.059, top - 0.0245), (x + 0.057, top - 0.032)),
        ("BLOCK", (x + 0.111, top - 0.0245), (x + 0.111, top - 0.027)),
        ("FEELER", (x + 0.0425, top - 0.027), (x + 0.048, datum + 0.003)),
        ("Z=0 MOUNTING PLANE", (x + 0.012, top - 0.070), (x + 0.020, datum)),
        ("GROUND BRIDGE", (x + 0.093, top - 0.070), (x + 0.093, datum - 0.003)),
        ("NO PROUD CARRIAGE FEATURE", (x + 0.074, top - 0.087),
         (x + 0.066, datum - 0.007)),
    )


def pin_tip_inspection_labels() -> tuple[tuple[str, tuple[float, float]], ...]:
    """Identify the schematic's signed features; C2A owns the full procedure."""
    x, _bottom, _right, top = PIN_TIP_INSPECTION_REGION
    return (
        ("C2A FUNCTIONAL SECTION", (x, top)),
        ("SCHEMATIC - NOT TO SCALE", (x, top - 0.006)),
        ("+Z INTO BLOCK", (x, top - 0.014)),
        ("FEELER", (x + 0.025, top - 0.020)),
        ("PIN", (x + 0.056, top - 0.0175)),
        ("BLOCK", (x + 0.104, top - 0.0175)),
        (spec.PIN_TIP_MIN_RECESS_CALLOUT, (x + 0.076, top - 0.0525)),
        ("Z=0 MOUNTING PLANE", (x, top - 0.073)),
        ("GROUND BRIDGE", (x + 0.076, top - 0.073)),
        ("NO PROUD CARRIAGE FEATURE", (x, top - 0.087)),
        ("BEARINGS ABSENT; SEE C2A", (x, top - 0.095)),
    )


def _scale_text(scale: tuple[float, float]) -> str:
    return f"{scale[0]:g}:{scale[1]:g}"


def exploded_caption(cluster: Cluster, scale: tuple[float, float]) -> str:
    """A cluster sheet's caption: its title, then the spec's cross-reference
    filled in with the fitted scale and this package's sheet numbers."""
    reference = spec.EXPLODED_CAPTION.format(
        scale=_scale_text(scale),
        bom_sheet=BOM_SHEET_NUMBER,
        steps_sheet=STEPS_SHEET_NUMBER,
    )
    lines = [f"{cluster.title} {reference}"]
    if spec.PIVOT_CAP in cluster.stems:
        # Both supports instantiate the same families, not handed parts.
        # Explain the second cartridge in the existing reserved footer, without
        # duplicating its BOM balloons or introducing text into the balloon ring.
        lines.append("IDENTICAL CAPTURE PARTS AT BOTH SUPPORTS.")
    return _wrapped(lines, width=EXPLODED_CAPTION_WIDTH)


def _activate_sheet(adapter: Any, name: str) -> Any:
    ddoc = _early_bound(adapter.currentModel, "IDrawingDoc")
    if not ddoc.ActivateSheet(name):
        raise RuntimeError(f"failed to activate drawing sheet {name!r}")
    current = _early_bound(ddoc.GetCurrentSheet(), "ISheet")
    actual = str(current.GetName() or "")
    if actual != name:
        raise RuntimeError(f"active drawing sheet is {actual!r}, expected {name!r}")
    return current


def _add_note_block(
    adapter: Any, sheet_name: str, text: str, xy: tuple[float, float], *, label: str
) -> Any:
    """Return a readback-validated native note owned by the activated sheet."""
    _activate_sheet(adapter, sheet_name)
    note = add_note(adapter, text, *xy)
    if note is None:
        raise RuntimeError(f"failed to place the jig {label}")
    note = _early_bound(note, "INote")
    printed = str(note.GetText() or "").replace("\r\n", "\n").replace("\r", "\n")
    if printed != text:
        raise RuntimeError(f"jig {label} printed as {printed!r}")
    return note


def _view_outline(view: Any, *, label: str) -> tuple[float, float, float, float]:
    outline = tuple(float(value) for value in _early_bound(view, "IView").GetOutline())
    if len(outline) != 4 or outline[2] <= outline[0] or outline[3] <= outline[1]:
        raise RuntimeError(f"{label}: invalid view outline {outline!r}")
    return outline[0], outline[1], outline[2], outline[3]


def _assert_view_on_sheet(
    view: Any,
    *,
    margin: float = 0.0,
    bounds: tuple[float, float, float, float] = SHEET_INNER_BORDER,
    label: str,
) -> None:
    """The view's outline, grown by ``margin`` (a balloon ring), stays inside
    ``bounds`` (the inner border unless given) and clear of the title block."""
    x0, y0, x1, y1 = _view_outline(view, label=label)
    x0, y0, x1, y1 = x0 - margin, y0 - margin, x1 + margin, y1 + margin
    left, bottom, right, top = bounds
    findings = []
    if x0 < left or y0 < bottom or x1 > right or y1 > top:
        findings.append(f"leaves {bounds}")
    tx0, ty0, tx1, ty1 = TITLE_BLOCK
    if x1 > tx0 and x0 < tx1 and y0 < ty1 and y1 > ty0:
        findings.append(f"enters the title block {TITLE_BLOCK}")
    if findings:
        raise RuntimeError(
            f"{label}: outline {(x0, y0, x1, y1)!r} " + "; ".join(findings)
        )


def _center_view_outline(
    adapter: Any, view: Any, center: tuple[float, float], *, label: str
) -> None:
    """Translate the actual exploded outline using the current native origin."""
    view = _early_bound(view, "IView")
    x0, y0, x1, y1 = _view_outline(view, label=label)
    before = tuple(float(value) for value in view.Position)
    target = (
        before[0] + center[0] - (x0 + x1) / 2.0,
        before[1] + center[1] - (y0 + y1) / 2.0,
    )
    if not view.SetViewPosition(double_array(list(target)), False):
        raise RuntimeError(f"{label}: SetViewPosition refused {target!r}")
    adapter.currentModel.EditRebuild3()
    after = tuple(float(value) for value in view.Position)
    if len(after) != 2 or any(abs(a - b) > 1e-6 for a, b in zip(after, target)):
        raise RuntimeError(f"{label}: view moved to {after!r}, expected {target!r}")
    x0, y0, x1, y1 = _view_outline(view, label=label)
    if (
        abs((x0 + x1) / 2.0 - center[0]) > 1e-6
        or abs((y0 + y1) / 2.0 - center[1]) > 1e-6
    ):
        raise RuntimeError(f"{label}: measured outline did not centre at {center!r}")


def _component_stem(component: Any) -> str:
    """Logical family from the native file AND member, never its shared Number."""
    component = _early_bound(component, "IComponent2")
    identity = component_identity(component)
    try:
        return spec.component_family(*identity)
    except ValueError as error:
        raise RuntimeError(
            f"component {component.Name2!r} selects unexpected jig identity {identity!r}"
        ) from error


def _validate_source(source_model: Any) -> None:
    """The builder-owned explodes exist, and the source opens collapsed with
    exactly the contracted families."""
    assembly = _early_bound(source_model, "IAssemblyDoc")
    manager = _early_bound(source_model.ConfigurationManager, "IConfigurationManager")
    configuration = _early_bound(manager.ActiveConfiguration, "IConfiguration")
    if str(configuration.Name) != ASSEMBLY_VIEW_CONFIGURATION:
        raise RuntimeError("jig source must open in its Default configuration")
    for owner, wanted in EXPLODED_VIEW_NAMES.items():
        names = tuple(assembly.GetExplodedViewNames2(owner) or ())
        if names != (wanted,):
            raise RuntimeError(f"jig {owner} exploded views {names!r} != {(wanted,)!r}")
    counts: dict[str, int] = {}
    for raw in tuple(assembly.GetComponents(True) or ()):
        component = _early_bound(raw, "IComponent2")
        stem = _component_stem(component)
        counts[stem] = counts.get(stem, 0) + 1
        total = _early_bound(component.GetTotalTransform(True), "IMathTransform")
        base = _early_bound(component.GetTotalTransform(False), "IMathTransform")
        if any(
            abs(float(actual) - float(expected)) > 1e-9
            for actual, expected in zip(total.ArrayData, base.ArrayData, strict=True)
        ):
            raise RuntimeError(
                f"jig source must open collapsed: {component.Name2!r} is displaced"
            )
    if counts != BOM_QUANTITIES:
        raise RuntimeError(f"jig families {counts!r} != contract {BOM_QUANTITIES!r}")
    component_reference_names(source_model, spec.KIT_COMPONENT_REFERENCES)


def _bom_cells(table: Any) -> tuple[tuple[str, ...], ...]:
    """Every physical BOM cell, header row first, with visible native rows."""
    contents = []
    for row in range(int(table.RowCount)):
        if table.RowHidden(row) is not False:
            raise RuntimeError(f"jig BOM physical row {row} is not proven visible")
        contents.append(
            tuple(
                str(table.DisplayedText2(row, column, True) or "").strip()
                for column in range(int(table.ColumnCount))
            )
        )
    return tuple(contents)


def _bom_column(
    header: tuple[str, ...], predicate: Callable[[str], bool], label: str
) -> int:
    matches = [index for index, cell in enumerate(header) if predicate(cell.upper())]
    if len(matches) != 1:
        raise RuntimeError(f"jig BOM has no unique {label} column: {header!r}")
    return matches[0]


def _bom_columns(header: tuple[str, ...]) -> dict[str, int]:
    return {
        "item": _bom_column(
            header, lambda cell: cell.startswith("ITEM NO"), "ITEM NO."
        ),
        "part": _bom_column(header, lambda cell: cell == "PART NUMBER", "PART NUMBER"),
        "description": _bom_column(
            header, lambda cell: cell == "DESCRIPTION", "DESCRIPTION"
        ),
        "quantity": _bom_column(header, lambda cell: cell.startswith("QTY"), "QTY."),
    }


def bom_extent_violations(
    anchor: tuple[float, float], width: float, height: float
) -> list[str]:
    """Name every intersection with the border, title keep-out or reserved
    reference column. A table left of the title may extend below it."""
    left, top = anchor
    right, bottom = left + width, top - height
    tolerance = 1e-9  # floating-point arithmetic, not a paper allowance
    border_left, border_bottom, border_right, border_top = SHEET_INNER_BORDER
    findings = []
    rx0, ry0, rx1, ry1 = REFERENCE_REGION
    if (
        right > rx0 - REGION_GAP + tolerance
        and left < rx1 - tolerance
        and bottom < ry1 - tolerance
        and top > ry0 + tolerance
    ):
        findings.append("enters the reference column")
    if (
        left < border_left + BOM_SHEET_CLEARANCE - tolerance
        or right > border_right - BOM_SHEET_CLEARANCE + tolerance
        or top > border_top - BOM_SHEET_CLEARANCE + tolerance
    ):
        findings.append("crosses the inner border")
    if bottom < border_bottom + BOM_SHEET_CLEARANCE - tolerance:
        findings.append("crosses the bottom border")
    tx0, ty0, tx1, ty1 = TITLE_BLOCK_KEEP_OUT
    if (
        right > tx0 + tolerance
        and left < tx1 - tolerance
        and bottom < ty1 - tolerance
        and top > ty0 + tolerance
    ):
        findings.append("enters the title block")
    return findings


def _bom_bounds(table: Any) -> tuple[float, float, float, float]:
    """The rebuilt table's native top-left anchor, row heights and widths."""
    annotation = _early_bound(table.GetAnnotation(), "IAnnotation")
    position = tuple(float(value) for value in annotation.GetPosition())
    heights = tuple(float(table.GetRowHeight(row)) for row in range(int(table.RowCount)))
    widths = tuple(
        float(table.GetColumnWidth(column)) for column in range(int(table.ColumnCount))
    )
    if (
        len(position) != 3
        or not all(map(math.isfinite, position))
        or not heights
        or not widths
        or any(not math.isfinite(value) or value <= 0 for value in (*heights, *widths))
    ):
        raise RuntimeError("jig BOM has unreadable native geometry")
    return position[0], position[1] - sum(heights), position[0] + sum(widths), position[1]


def _assert_bom_on_paper(table: Any) -> None:
    """Measure the rebuilt table, including any row grown by wrapped text."""
    left, bottom, right, top = _bom_bounds(table)
    position = (left, top)
    rows = int(table.RowCount)
    width, height = right - left, top - bottom
    violations = bom_extent_violations((position[0], position[1]), width, height)
    _telemetry.event(
        "drawing.bom_piece",
        piece=1,
        anchor_mm=(position[0] * 1000.0, position[1] * 1000.0),
        rows=rows,
        width_mm=width * 1000.0,
        height_mm=height * 1000.0,
        violations=tuple(violations),
    )
    if violations:
        raise RuntimeError(
            f"jig BOM ({width * 1000.0:.1f} x {height * 1000.0:.1f} mm at "
            f"{position[0] * 1000.0:.1f}, {position[1] * 1000.0:.1f} mm) "
            + "; ".join(violations)
        )


def _validate_bom(
    adapter: Any,
    table: Any,
    *,
    configuration: str = SIMPLIFIED_VIEW_CONFIGURATION,
) -> tuple[tuple[str, str], ...]:
    """Prove native rows, associative Numbers, item order, descriptions and counts.

    The visible Number is not a row key: all three kit members print SH-VN-57.
    No cell text override may replace the native Number-property association.
    """
    table = _early_bound(table, "ITableAnnotation")
    contents = _bom_cells(table)
    rows = len(contents)
    columns = len(contents[0]) if contents else 0
    if rows != len(BOM_COMPONENTS) + 1 or columns != len(BOM_COLUMN_WIDTHS):
        raise RuntimeError(
            f"jig BOM is {rows}x{columns}; expected "
            f"{len(BOM_COMPONENTS) + 1} rows and {len(BOM_COLUMN_WIDTHS)} columns"
        )
    header = contents[0]
    if "MATERIAL" in (cell.upper() for cell in header):
        raise RuntimeError("jig BOM template already has 'MATERIAL'")
    at = _bom_columns(header)

    actual = bom_row_identities(
        table,
        configuration=configuration,
        component_identities=BOM_COMPONENT_IDENTITIES,
    )
    for stem, row_index in actual.items():
        row = contents[row_index]
        if (
            row_index != int(BOM_ITEM_NUMBERS[stem])
            or row[at["item"]] != BOM_ITEM_NUMBERS[stem]
        ):
            raise RuntimeError(
                f"jig BOM numbers {stem!r} item {row[at['item']]!r}, but the steps "
                f"cite item {BOM_ITEM_NUMBERS[stem]}: the assembly must insert its "
                "families in spec.BOM_ORDER"
            )
        number = BOM_PART_NUMBERS[stem]
        if row[at["part"]] != number:
            raise RuntimeError(
                f"jig BOM associative part number for {stem!r} reads "
                f"{row[at['part']]!r}, expected {number!r}"
            )
        if row[at["description"]] != BOM_DESCRIPTIONS[stem]:
            raise RuntimeError(f"jig BOM description mismatch for {stem!r}")
        if row[at["quantity"]] != str(BOM_QUANTITIES[stem]):
            raise RuntimeError(
                f"jig BOM quantity for {stem!r} is {row[at['quantity']]!r}, "
                f"expected {BOM_QUANTITIES[stem]}"
            )

    for key, column in at.items():
        width = BOM_COLUMN_WIDTHS[key]
        if abs(float(table.SetColumnWidth(column, width, 0)) - width) > 1e-6:
            raise RuntimeError(f"jig BOM {key} column width did not persist")
    for row_index in range(rows):
        table.SetRowHeight(row_index, BOM_ROW_HEIGHT, 0)
    before_rebuild = validate_bom_number_property(
        table,
        configuration=configuration,
        label="jig",
        expected_rows=rows,
        occurrence_quantities=True,
    )
    if not adapter.currentModel.EditRebuild3():
        raise RuntimeError("jig BOM rebuild failed")
    settled = _bom_cells(table)
    if bom_row_identities(
        table,
        configuration=configuration,
        component_identities=BOM_COMPONENT_IDENTITIES,
    ) != actual:
        raise RuntimeError("jig BOM native member rows changed after rebuild")
    for stem, row_index in actual.items():
        applied = settled[row_index][at["part"]]
        if applied != BOM_PART_NUMBERS[stem]:
            raise RuntimeError(f"jig BOM part number for {stem!r} reads {applied!r}")
    if validate_bom_number_property(
        table,
        configuration=configuration,
        label="jig",
        expected_rows=rows,
        occurrence_quantities=True,
    ) != before_rebuild:
        raise RuntimeError(
            "jig native BOM membership/quantities changed during rebuild"
        )
    _assert_bom_on_paper(table)
    return tuple((stem, BOM_ITEM_NUMBERS[stem]) for stem in BOM_COMPONENTS)


def _kit_bom_note_text(table: Any, *, configuration: str) -> str:
    """Resolve kit item citations from native members, never the repeated Number."""
    registry = PART_ROWS[spec.HOLD_DOWN_STUD]
    skus = registry["supplier_skus"]
    if len(skus) != 1:
        raise RuntimeError("jig kit key requires its one authoritative supplier SKU")
    number = str(registry["number"])
    contents = _bom_cells(table)
    columns = _bom_columns(contents[0])
    native_rows = bom_row_identities(
        table,
        configuration=configuration,
        component_identities=BOM_COMPONENT_IDENTITIES,
    )
    lines = [
        f"PURCHASED KIT IDENTITY: {number}",
        f"{str(registry['supplier']).upper()} SKU {skus[0]}",
        "MEMBER CONFIGURATIONS (INSTALLED QTY.):",
    ]
    for family, (_physical, member) in spec.KIT_IDENTITIES.items():
        row = contents[native_rows[family]]
        quantity = str(registry["configuration_quantities"][member])
        if row[columns["part"]] != number or row[columns["quantity"]] != quantity:
            raise RuntimeError(f"jig kit key disagrees with native BOM row for {member}")
        lines.append(f"ITEM {row[columns['item']]}: {member} ({quantity})")
    lines.append("BOM QTY. COUNTS MEMBERS, NOT KITS.")
    return "\n".join(lines)


def kit_bom_note_region(
    bom: tuple[float, float, float, float],
    reference: tuple[float, float, float, float],
) -> tuple[float, float, float, float]:
    """Measured room right of the BOM, below the reference and above the title."""
    return (
        max(bom[2], SHEET_INNER_BORDER[0]) + REGION_GAP,
        max(TITLE_BLOCK[3], SHEET_INNER_BORDER[1]) + REGION_GAP,
        SHEET_INNER_BORDER[2] - REGION_GAP,
        reference[1] - REGION_GAP,
    )


def _kit_bom_note_extent(note: Any) -> tuple[float, float, float, float]:
    values = tuple(float(value) for value in (note.GetExtent() or ()))
    if len(values) != 6 or not all(map(math.isfinite, values)):
        raise RuntimeError(f"jig kit key has unreadable native note extent: {values!r}")
    box = values[0], values[1], values[3], values[4]
    if box[0] >= box[2] or box[1] >= box[3]:
        raise RuntimeError(f"jig kit key has empty native note extent: {values!r}")
    return box


def _place_kit_bom_note(adapter: Any, table: Any, reference: Any) -> Callable[[], None]:
    """Seat the measured BOM key once, then recheck its content and clearance."""
    configuration = str(reference.ReferencedConfiguration)
    text = _kit_bom_note_text(table, configuration=configuration)
    region = kit_bom_note_region(
        _bom_bounds(table), _view_outline(reference, label="jig BOM reference")
    )
    if region[0] >= region[2] or region[1] >= region[3]:
        raise RuntimeError(f"jig kit key has no clear note field: {region!r}")
    note = _add_note_block(
        adapter, BOM_SHEET, text, (region[0], region[3]), label="configured-kit BOM key"
    )
    rebuild_drawing(adapter, label="measure jig configured-kit BOM key")
    adapter.currentModel.GraphicsRedraw2()
    box = _kit_bom_note_extent(note)
    annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
    position = tuple(float(value) for value in (annotation.GetPosition() or ()))
    if len(position) != 3 or not all(map(math.isfinite, position)):
        raise RuntimeError("jig kit key has unreadable native note position")
    # A measured inset, not an assumption that the insertion point is an ink edge.
    inset = BOM_SHEET_CLEARANCE
    if not annotation.SetPosition2(
        position[0] + region[0] + inset - box[0],
        position[1] + region[3] - inset - box[3],
        position[2],
    ):
        raise RuntimeError("jig kit key native note placement failed")
    rebuild_drawing(adapter, label="seat jig configured-kit BOM key")

    def settled() -> None:
        _activate_sheet(adapter, BOM_SHEET)
        adapter.currentModel.GraphicsRedraw2()
        expected = _kit_bom_note_text(table, configuration=configuration)
        printed = str(note.GetText() or "").replace("\r\n", "\n").replace("\r", "\n")
        if expected != text or printed != expected:
            raise RuntimeError("jig kit key no longer agrees with the native BOM")
        if int(annotation.OwnerType) != 1 or int(annotation.Visible) != 1:
            raise RuntimeError("jig kit key is not a visible sheet-owned note")
        if int(annotation.GetLeaderCount()) != 0:
            raise RuntimeError("jig kit key unexpectedly has a leader")
        bom = _bom_bounds(table)
        outline = _view_outline(reference, label="jig BOM reference")
        field = kit_bom_note_region(bom, outline)
        extent = _kit_bom_note_extent(note)
        if not (
            field[0] <= extent[0] < extent[2] <= field[2]
            and field[1] <= extent[1] < extent[3] <= field[3]
        ):
            raise RuntimeError(
                f"jig kit key extent {extent!r} leaves its clear field {field!r}"
            )
        _telemetry.info(
            f"jig configured-kit BOM key: extent_m={extent!r}; "
            f"field_m={field!r}; BOM air_mm={(extent[0] - bom[2]) * 1000:.3f}; "
            f"reference air_mm={(outline[1] - extent[3]) * 1000:.3f}"
        )

    settled()
    return settled


_PROJECTION_TOLERANCE_M = 1e-5
_MAPPING_STATIONS = ((0.0, 0.0, 0.0), (0.1, 0.0, 0.0), (0.0, 0.1, 0.0), (0.0, 0.0, 0.1))


def _require_view_axes(
    adapter: Any, view: Any, name: str, scale: tuple[float, float], *, label: str
) -> None:
    """Fail unless ``view`` draws machine X/Y/Z the way ``spec.VIEW_AXES[name]``
    says at ``scale`` (``draw_fr_harmonic_base._require_bottom_view_mapping``'s
    proof): every title, tag and explode reading on the sheet assumes it."""
    right, up, _sight = spec.VIEW_AXES[name]
    origin, *ends = model_points_in_view(
        adapter,
        view,
        _MAPPING_STATIONS,
        label=f"{label} mapping",
        names=("origin", "+X", "+Y", "+Z"),
    )
    length = 0.1 * scale[0] / scale[1]
    for axis, end in enumerate(ends):
        expected = (right[axis] * length, up[axis] * length)
        drawn = (end[0] - origin[0], end[1] - origin[1])
        if max(abs(d - e) for d, e in zip(drawn, expected)) > _PROJECTION_TOLERANCE_M:
            raise RuntimeError(
                f"{label}: 100 mm along machine {'XYZ'[axis]} draws {drawn}, "
                f"not {expected}: {name!r} is not the spec's view"
            )


def _place_named_view(
    adapter: Any,
    name: str,
    center: tuple[float, float],
    scale: tuple[float, float],
    *,
    label: str,
) -> Any:
    view = place_view(adapter, str(SOURCE), name, *center, scale=scale)
    _require_view_axes(adapter, view, name, scale, label=label)
    return view


def _add_plan_tags(adapter: Any, plan: Any) -> None:
    """Each ``spec.PLAN_TAGS`` text with a leader to its machine point, owned
    by the plan; both ends projected through the plan's measured mapping."""
    names = [tag.text.split("\n")[0] for tag in spec.PLAN_TAGS]
    tips = model_points_in_view(
        adapter,
        plan,
        [tuple(value / 1000.0 for value in tag.tip) for tag in spec.PLAN_TAGS],
        label="jig plan tag tips",
        names=names,
    )
    texts = model_points_in_view(
        adapter,
        plan,
        [(x / 1000.0, y / 1000.0, 0.0) for x, y in (t.text_xy for t in spec.PLAN_TAGS)],
        label="jig plan tag texts",
        names=names,
    )
    for tag, name, tip, text_xy in zip(spec.PLAN_TAGS, names, tips, texts):
        add_leader_note(
            adapter,
            tag.text,
            text_xy=text_xy,
            attach_xy=tip,
            label=f"jig plan tag {name}",
            view=plan,
        )


def _native_dimension_anchor(annotation: Any) -> tuple[float, float, float] | None:
    """``IAnnotation::GetPosition`` of an imported display dimension as
    (sheet x, sheet y, native z), or None when unreadable.

    Only x and y are the documented sheet placement (``types/IAnnotation/
    GetPosition.md``: relative to the sheet's lower-left corner; a display
    dimension's x, y is its text box's bottom-border centre). An imported model
    dimension keeps a native z the move does not set: on farm source 9e0cccd61
    curation's two ``SetPosition(x, y, 0.0)`` passes (it deleted two unrequested
    imports) and ``SetPosition2(x, y, 0.0)`` read back (0.23628, 0.1381095625,
    -0.03273): the line midpoint's sheet y as the offline elevation mapping
    computes it, with z 32.7 mm off the sheet plane. The
    recipes compare ``position[:2]`` (``_reposition_rerun_reason``,
    ``_section_axis``) and carry the native z through a move
    (``_drawing_annotation_extent``).
    """
    position = tuple(float(value) for value in (annotation.GetPosition() or ()))
    if len(position) != 3 or not all(math.isfinite(value) for value in position):
        return None
    return position


def _cl_tip_setting(adapter: Any, elevation: Any) -> Callable[[], None]:
    """Import the builder's CL tip-above-riser dimension into the elevation at
    ``CL_TIP_TEXT_MODEL_MM``, parenthesise it as a reference and prove its
    nominal, places and that it carries no band; returns the same proof for
    the settled drawing. Every native anchor, arrow tip and requested point is
    compared on the sheet plane (x, y); see ``_native_dimension_anchor``."""
    label = "jig elevation CL tip above riser"
    name = spec.CL_TIP_DIMENSION
    line_xy = model_point_in_view(
        adapter, elevation,
        tuple(value / 1000.0 for value in CL_TIP_LINE_MODEL_MM),
        label=f"{label} line",
    )
    text_xy = model_point_in_view(
        adapter, elevation,
        tuple(value / 1000.0 for value in CL_TIP_TEXT_MODEL_MM),
        label=f"{label} text",
    )
    source_ends = model_points_in_view(
        adapter, elevation,
        [(x / 1000.0, 0.0, z / 1000.0) for x, z in spec.CL_TIP_LINE],
        label=f"{label} native witness ends",
    )
    arrow_tips = tuple((line_xy[0], y) for _x, y in source_ends)
    _show_base_view_sketches(adapter, elevation, (spec.CL_TIP_FEATURE,), label=label)
    annotations = curate_view_dimensions(
        adapter,
        elevation,
        keep={name: line_xy},
        view_label=label,
        dimensions_by_feature=spec.DRAWING_DIMENSIONS,
    )
    if len(annotations) != 1:
        raise RuntimeError(f"{label} must import exactly one dimension")
    assert_imported_precision(adapter, annotations, {name: spec.CL_TIP_PRECISION})
    display = _early_bound(
        set_reference_dimension(adapter, annotations[0], label=label),
        "IDisplayDimension",
    )
    annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
    # Reset an inherited offset before positioning the dimension line. With
    # OffsetText on, SetPosition2 moves only the text and cannot repair a line
    # curation previously left in the text lane. The move keeps the native z.
    display.OffsetText = False
    anchor = _native_dimension_anchor(annotation)
    if (
        anchor is None
        or bool(display.OffsetText)
        or not annotation.SetPosition2(*line_xy, anchor[2])
    ):
        raise RuntimeError(f"failed to position {label} dimension line at {anchor!r}")
    position = _native_dimension_anchor(annotation)
    if position is None or math.dist(position[:2], line_xy) > 0.00005:
        raise RuntimeError(
            f"{label}: native dimension-line anchor at {position!r}, "
            f"expected sheet {line_xy!r}"
        )

    def prove_dimension_line() -> None:
        data = _early_bound(display.GetDisplayData(), "IDisplayData")
        if data is None:
            raise RuntimeError(f"{label}: missing native dimension-line display")
        native_tips = []
        for index in range(int(data.GetArrowHeadCount())):
            raw = tuple(float(v) for v in (data.GetArrowHeadAtIndex2(index) or ()))
            if len(raw) != 12 or not all(math.isfinite(value) for value in raw):
                raise RuntimeError(f"{label}: unreadable native dimension-line arrow")
            native_tips.append(raw[:2])
        # Use the same 0.05 mm paper tolerance as native annotation positions,
        # not the schematic's tighter mathematical endpoint-transform proof.
        for expected in arrow_tips:
            match = next((
                index for index, actual in enumerate(native_tips)
                if math.dist(actual, expected) <= 0.00005
            ), None)
            if match is None:
                raise RuntimeError(
                    f"{label}: native dimension line lost arrow at {expected!r}; "
                    f"native arrow tips {native_tips!r}"
                )
            native_tips.pop(match)

    rebuild_drawing(adapter, label=f"{label} dimension-line anchor")
    prove_dimension_line()
    offset_dimension_text(adapter, annotations, {name: text_xy})

    def proven(when: str) -> None:
        dimension = _early_bound(display.GetDimension2(0), "IDimension")
        tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
        value_mm = abs(float(dimension.SystemValue)) * 1000.0
        brackets = (str(display.GetText(1) or ""), str(display.GetText(2) or ""))
        places = int(display.GetPrimaryPrecision2())
        if (
            abs(value_mm - spec.cl_dowel.TIP_HEIGHT) > 1e-6
            or brackets != ("(", ")")
            or int(tolerance.Type) != 0  # swTolNONE: a reference carries no band
            or places != spec.CL_TIP_PRECISION
        ):
            raise RuntimeError(
                f"{when} {label}: {value_mm!r} mm, brackets {brackets!r}, "
                f"tolerance type {int(tolerance.Type)}, {places} places"
            )
        position = _native_dimension_anchor(annotation)
        if (
            not bool(display.OffsetText)
            or position is None
            or math.dist(position[:2], text_xy) > 0.00005
        ):
            raise RuntimeError(
                f"{when} {label}: native offset text at {position!r}, "
                f"expected sheet {text_xy!r}"
            )
        prove_dimension_line()

    proven("placed")
    return lambda: proven("settled")


def _place_assembled_sheet(adapter: Any) -> Callable[[], None]:
    """Plan over the operator's elevation at the modelled pose, each titled,
    the plan's tags, the pose caption, the rail-alignment targets, and the
    elevation's CL tip reference; returns that reference's settled proof."""
    _activate_sheet(adapter, SHEET_NAMES[0])
    plan = _place_named_view(
        adapter, spec.PLAN_VIEW, PLAN_CENTER, ASSEMBLED_SCALE, label="jig plan"
    )
    elevation = _place_named_view(
        adapter,
        spec.ELEVATION_VIEW,
        ELEVATION_CENTER,
        ASSEMBLED_SCALE,
        label="jig elevation",
    )
    for view, label in ((plan, "jig plan"), (elevation, "jig elevation")):
        set_hidden_lines_removed(adapter, view)
        apply_view_configuration(adapter, view, label=label)
        _assert_view_on_sheet(view, label=label)
    _add_plan_tags(adapter, plan)
    for text, xy, label in (
        (spec.PLAN_VIEW_LABEL, PLAN_LABEL_XY, "plan title"),
        (spec.ELEVATION_VIEW_LABEL, ELEVATION_LABEL_XY, "elevation title"),
    ):
        _add_note_block(adapter, SHEET_NAMES[0], text, xy, label=label)
    _add_note_block(
        adapter, SHEET_NAMES[0], ASSEMBLED_CAPTION, CAPTION_XY, label="pose caption"
    )
    _add_note_block(
        adapter,
        SHEET_NAMES[0],
        ALIGNMENT_NOTE,
        ALIGNMENT_XY,
        label="rail-alignment targets",
    )
    return _cl_tip_setting(adapter, elevation)


@contextmanager
def _source_configuration_active(view: Any, *, label: str) -> Iterator[None]:
    """Make the exploded view's configuration the source's active one.

    The balloons read the explode's steps from that configuration
    (``_drawing_balloons._view_explode_offsets``). A non-active one read all
    of them on the first jig drawing but none on jig-r6, and that reader
    refuses a non-active configuration that reads none; an active one's
    steps are made readable by showing its named explode on the source, the
    path the measuring-stick drawing's identical exploded sheet takes. Only
    the open session's active configuration changes; the source is never
    saved, and ``Default`` is active again on exit. Each switch is read
    back.
    """
    bound = _early_bound(view, "IView")
    wanted = str(bound.ReferencedConfiguration)
    model = _early_bound(bound.ReferencedDocument, "IModelDoc2")
    manager = _early_bound(model.ConfigurationManager, "IConfigurationManager")

    def active() -> str:
        return str(_early_bound(manager.ActiveConfiguration, "IConfiguration").Name)

    rest = active()
    if rest != ASSEMBLY_VIEW_CONFIGURATION:
        raise RuntimeError(
            f"{label}: the source is in {rest!r}, not {ASSEMBLY_VIEW_CONFIGURATION!r}"
        )
    if not bool(model.ShowConfiguration2(wanted)) or active() != wanted:
        raise RuntimeError(f"{label}: the source did not activate {wanted!r}")
    try:
        if not bool(bound.IsExploded()) or str(bound.ReferencedConfiguration) != wanted:
            raise RuntimeError(
                f"{label}: activating {wanted!r} on the source changed the view"
            )
        yield
    finally:
        primary_error = sys.exception()
        try:
            if not bool(model.ShowConfiguration2(rest)) or active() != rest:
                raise RuntimeError(f"{label}: the source did not re-activate {rest!r}")
        except Exception as cleanup_error:
            if primary_error is None:
                raise
            _telemetry.warn(f"{label}: restoring {rest!r}: {cleanup_error}")


# Two rings failed the layout audit on both item sets (jig-r7 and c4-r2): a
# second instance attaches near its first, so its outer-ring leader runs in
# across the inner ring at about that angle, through a balloon parked there
# (balloon 3's leader ran 6.32 mm through balloon 4 on jig-r7). One ring,
# ordered by attachment angle, has no balloon inside another's leader path:
# replayed on both runs' logged attachments, every leader stays over 8 mm
# clear of every other balloon. Pushing crowded circles apart can still
# leave two leaders crossed; swapping their slots uncrosses them and
# strictly shortens their total length (the triangle inequality), so
# repeated swaps end. The cap only bounds a wrong input.
# draw_pd_paper_drive_assembly's transgear sheet rings its balloons by the
# same rule.
_UNCROSS_SWAPS_MAX = 64
# jig-r8: balloons 1 and 2 passed the swap step, then the audit found their
# leaders crossed 0.5 mm from balloon 2's attachment (0.16 mm across balloon
# 1's leader at their 19 degree meet). An end that sits on, or a hair short
# of, another leader is a "touch" to find_leader_leader_crossings, and the
# rebuild after the move settles attachments by more than its 0.1 mm. So once
# no leader crosses another, each is run on past its attachment by an
# arrowhead's length (~2.4 mm rendered) and a pair crossing there swaps too,
# but only when the swap crosses nothing and leaves fewer such near-crossings.
# That count falls with every such swap, so this phase ends as well; it has
# to be conditional, because two leaders converging on attachments under
# 2.4 mm apart (c4-r4: 13 balloons, second instances attaching near their
# first) cross once run on whichever slots they take, and unconditional
# swaps toggled that pair until the cap.
_UNCROSS_END_CLEARANCE_M = 2.4e-3


def _leader_past_attachment(
    centre: tuple[float, float], attach: tuple[float, float], run_on: float
) -> tuple[float, float]:
    """``attach`` moved ``run_on`` further from ``centre`` along the leader
    (unchanged for a zero-length leader)."""
    dx, dy = attach[0] - centre[0], attach[1] - centre[1]
    length = math.hypot(dx, dy)
    if length == 0.0:
        return attach
    scale = run_on / length
    return (attach[0] + dx * scale, attach[1] + dy * scale)


def _ring_crossings(
    centres: Sequence[tuple[float, float]],
    attachments: Sequence[tuple[float, float]],
    slots: Sequence[int],
    *,
    run_on: float,
) -> list[tuple[int, int]]:
    """The balloon pairs whose leaders, each from its slot's centre to
    ``run_on`` past its attachment, cross."""
    segments = []
    for index, attach in enumerate(attachments):
        centre = centres[slots[index]]
        end = _leader_past_attachment(centre, attach, run_on)
        segments.append(
            LeaderSegment(
                label=str(index),
                kind="balloon",
                x0=centre[0],
                y0=centre[1],
                x1=end[0],
                y1=end[1],
            )
        )
    return [
        (int(crossing.a.label), int(crossing.b.label))
        for crossing in find_leader_leader_crossings(segments)
    ]


def _swapped(slots: Sequence[int], first: int, second: int) -> list[int]:
    trial = list(slots)
    trial[first], trial[second] = trial[second], trial[first]
    return trial


def uncrossed_ring_slots(
    centres: Sequence[tuple[float, float]],
    attachments: Sequence[tuple[float, float]],
) -> list[int]:
    """Which ring slot (an index into ``centres``, the circle centres as
    placed) each balloon takes so that no two leaders, each from its circle's
    centre to its attachment, cross; then, while a swap that crosses nothing
    can, fewer of them cross within ``_UNCROSS_END_CLEARANCE_M`` past an
    attachment. Leaders that do not cross keep their slots, so the slots, and
    the circles' clearances, are the ring's own."""
    if len(centres) != len(attachments):
        raise ValueError("one ring slot per balloon attachment")
    slots = list(range(len(centres)))
    for _swap in range(_UNCROSS_SWAPS_MAX + 1):
        crossed = _ring_crossings(centres, attachments, slots, run_on=0.0)
        if crossed:
            slots = _swapped(slots, *crossed[0])
            continue
        run_on = _UNCROSS_END_CLEARANCE_M
        near = _ring_crossings(centres, attachments, slots, run_on=run_on)
        for pair in near:
            trial = _swapped(slots, *pair)
            if _ring_crossings(centres, attachments, trial, run_on=0.0):
                continue
            left = _ring_crossings(centres, attachments, trial, run_on=run_on)
            if len(left) < len(near):
                slots = trial
                break
        else:
            return slots
    raise RuntimeError(
        f"balloon ring: leaders still cross after {_UNCROSS_SWAPS_MAX} slot swaps: "
        f"centres {[tuple(round(v, 5) for v in c) for c in centres]}, "
        f"attachments {[tuple(round(v, 5) for v in a) for a in attachments]}, "
        f"slots {slots}"
    )


def _ring_balloons(
    adapter: Any, view: Any, landings: Sequence[BalloonLanding], *, label: str
) -> None:
    """Ring every one of ``view``'s balloons together, ``BALLOON_MARGIN``
    outside its outline, then move them between their own ring slots until no
    two leaders cross (:func:`uncrossed_ring_slots`); attachments stay."""
    _spread_balloons(
        adapter, view, [landing.note for landing in landings], margin=BALLOON_MARGIN
    )
    rebuild_drawing(adapter, label=f"{label} ring")
    annotations, centres, offsets, attachments = [], [], [], []
    for landing in landings:
        x, y, _radius = rendered_balloon_circle(landing.note, label=label)
        annotation = _early_bound(
            _early_bound(landing.note, "INote").GetAnnotation(), "IAnnotation"
        )
        anchor = tuple(float(value) for value in (annotation.GetPosition() or ()))
        points = tuple(
            float(value) for value in (annotation.GetLeaderPointsAtIndex(0) or ())
        )
        if len(anchor) < 2 or len(points) < 6:
            raise RuntimeError(f"{label}: {landing.instance} balloon is unreadable")
        annotations.append(annotation)
        centres.append((x, y))
        offsets.append((anchor[0] - x, anchor[1] - y))
        attachments.append((points[-3], points[-2]))
    slots = uncrossed_ring_slots(centres, attachments)
    moved = [index for index, slot in enumerate(slots) if slot != index]
    for index in moved:
        x, y = centres[slots[index]]
        if not annotations[index].SetPosition(
            x + offsets[index][0], y + offsets[index][1], 0.0
        ):
            raise RuntimeError(
                f"{label}: failed to move {landings[index].instance} balloon"
            )
    if moved:
        _telemetry.info(
            f"{label}: swapped ring slots to uncross leaders: "
            + ", ".join(
                f"{landings[index].instance} -> {landings[slots[index]].instance}'s"
                for index in moved
            )
        )
        rebuild_drawing(adapter, label=f"{label} uncrossed")


# ring_fit_shift, ring_keep_out_shift_x, cluster_ring_fit and the ladder walk
# of cluster_ring_scale are draw_dt_drive_train_assembly's (farm-proven
# there), keyed to this package's ring room, ring and title block.


def ring_fit_shift(
    outline: tuple[float, float, float, float],
    region: tuple[float, float, float, float],
    *,
    grow: float,
) -> tuple[tuple[float, float], list[str]]:
    """Shift that centres an outline's balloon ring in a region, plus overflows."""
    ring = (outline[0] - grow, outline[1] - grow, outline[2] + grow, outline[3] + grow)
    x0, y0, x1, y1 = region
    ring_w, ring_h = ring[2] - ring[0], ring[3] - ring[1]
    overflows = [
        f"{axis} {size * 1000:.1f} mm > {room * 1000:.1f} mm"
        for axis, size, room in (
            ("width", ring_w, x1 - x0),
            ("height", ring_h, y1 - y0),
        )
        if size > room
    ]
    shift = (
        (x0 + x1) / 2.0 - (ring[0] + ring[2]) / 2.0,
        (y0 + y1) / 2.0 - (ring[1] + ring[3]) / 2.0,
    )
    return shift, overflows


def ring_keep_out_shift_x(
    outline: tuple[float, float, float, float],
    shift: tuple[float, float],
    *,
    margin: float,
    balloon_radius: float,
    keep_out: tuple[float, float, float, float],
) -> float:
    """The x shift that keeps the balloon ring's low arc left of a keep-out.

    ``_spread_balloons`` puts every balloon centre on the ellipse ``margin``
    outside the (shifted) outline, so the ellipse bounds where a balloon can
    land.  ``keep_out`` is (left, bottom, right, top), already grown by the
    clearance.  Where the ellipse dips low enough for a balloon to reach below
    the keep-out's top, its right-most balloon must stay left of the keep-out:
    returns ``shift[0]`` when that holds, else the shift that just makes it.
    """
    left, _bottom, _right, top = keep_out
    rx = (outline[2] - outline[0]) / 2.0 + margin
    ry = (outline[3] - outline[1]) / 2.0 + margin
    cx = (outline[0] + outline[2]) / 2.0 + shift[0]
    cy = (outline[1] + outline[3]) / 2.0 + shift[1]
    low = (top + balloon_radius - cy) / ry  # sin of the arc's upper edge
    if low <= -1.0:
        return shift[0]
    reach = rx if low >= 0.0 else rx * math.sqrt(1.0 - low * low)
    limit = left - balloon_radius - reach
    return shift[0] if cx <= limit else shift[0] - (cx - limit)


def cluster_ring_fit(
    outline: tuple[float, float, float, float],
) -> tuple[tuple[float, float], list[str], float]:
    """Shift that fits a cluster view's balloon ring, its overflows, its slide.

    The ring is centred in CLUSTER_RING_REGION, then raised toward the
    region's top until its low arc clears the title block's top (a ring that
    clears it stays centred across the sheet), and only then slid left until
    its low arc clears the title block; a slide past the region's left is an
    overflow. Review bought-r6: a ring only slid left left the sheet's right
    half empty. Only the outline's size matters: the shift re-centres
    wherever it landed.
    """
    shift, overflows = ring_fit_shift(
        outline, CLUSTER_RING_REGION, grow=BALLOON_RING_REACH
    )
    half_height = (outline[3] - outline[1]) / 2.0
    centre_y = (outline[1] + outline[3]) / 2.0
    # The centre that puts the ring's lowest balloon on the keep-out's top,
    # and the one that puts the ring's top on the region's top.
    clears = (
        TITLE_BLOCK_KEEP_OUT[3]
        + BALLOON_RADIUS
        + half_height
        + BALLOON_MARGIN
        - centre_y
    )
    highest = CLUSTER_RING_REGION[3] - BALLOON_RING_REACH - half_height - centre_y
    y = max(shift[1], min(clears, highest))
    x = ring_keep_out_shift_x(
        outline,
        (shift[0], y),
        margin=BALLOON_MARGIN,
        balloon_radius=BALLOON_RADIUS,
        keep_out=TITLE_BLOCK_KEEP_OUT,
    )
    ring_left = outline[0] + x - BALLOON_RING_REACH
    if ring_left < CLUSTER_RING_REGION[0]:
        overflows.append(
            f"left {ring_left * 1000:.1f} mm < {CLUSTER_RING_REGION[0] * 1000:.1f} mm "
            "clearing the title block"
        )
    return (x, y), overflows, x - shift[0]


def cluster_ring_scale(
    outline: tuple[float, float, float, float],
    placed: tuple[float, float],
    *,
    label: str,
) -> tuple[float, float]:
    """The largest ladder scale whose balloon ring fits.

    ``outline`` is the view's outline at ``placed``; a view's outline scales
    with its scale, and the fit reads only its size (cluster_ring_fit). Every
    rung references one configuration, so the walk starts at the ladder's
    top, not at ``placed``. Raises naming every scale's overflow when none
    fits.
    """
    if placed not in CLUSTER_SCALE_LADDER:
        raise ValueError(f"{label}: scale {_scale_text(placed)} is not on the ladder")
    x0, y0, x1, y1 = outline
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    findings = []
    for scale in CLUSTER_SCALE_LADDER:
        k = (scale[0] / scale[1]) / (placed[0] / placed[1])
        hw, hh = (x1 - x0) / 2.0 * k, (y1 - y0) / 2.0 * k
        _shift, overflows, _slide = cluster_ring_fit(
            (cx - hw, cy - hh, cx + hw, cy + hh)
        )
        if not overflows:
            return scale
        findings.append(f"{_scale_text(scale)}: {'; '.join(overflows)}")
    raise ValueError(
        f"{label}: no ladder scale fits the balloon ring in the cluster region "
        f"({' | '.join(findings)})"
    )


def cluster_ring_violations(outline: tuple[float, float, float, float]) -> list[str]:
    """Name every way a placed cluster view's balloon ring leaves its room:
    the ring region, or the title block under its low arc."""
    tolerance = 1e-6  # the view's position read-back, not a paper allowance
    x0, y0, x1, y1 = (
        outline[0] - BALLOON_RING_REACH,
        outline[1] - BALLOON_RING_REACH,
        outline[2] + BALLOON_RING_REACH,
        outline[3] + BALLOON_RING_REACH,
    )
    left, bottom, right, top = CLUSTER_RING_REGION
    findings = []
    if (
        x0 < left - tolerance
        or y0 < bottom - tolerance
        or x1 > right + tolerance
        or y1 > top + tolerance
    ):
        findings.append(f"leaves the ring region {CLUSTER_RING_REGION}")
    slide = ring_keep_out_shift_x(
        outline,
        (0.0, 0.0),
        margin=BALLOON_MARGIN,
        balloon_radius=BALLOON_RADIUS,
        keep_out=TITLE_BLOCK_KEEP_OUT,
    )
    if slide < -tolerance:
        findings.append("its low arc reaches the title block")
    return findings


def _set_view_scale(
    adapter: Any, view: Any, scale: tuple[float, float], *, label: str
) -> None:
    """Re-scale a placed drawing view and read the scale back
    (draw_dt_drive_train_assembly's)."""
    view = _early_bound(view, "IView")
    view.ScaleRatio = double_array([float(scale[0]), float(scale[1])])
    adapter.currentModel.EditRebuild3()
    ratio = tuple(float(value) for value in view.ScaleRatio)
    if len(ratio) != 2 or abs(ratio[0] / ratio[1] - scale[0] / scale[1]) > 1e-9:
        raise RuntimeError(f"{label}: view scale reads {ratio!r}, expected {scale!r}")


def _bom_feature_name(table: Any) -> str:
    """The inserted BOM's feature name, the key a view links to it by
    (draw_dt_drive_train_assembly's)."""
    bom = _early_bound(table, "IBomTableAnnotation")
    feature = _early_bound(bom.BomFeature, "IBomFeature")
    name = str(feature.Name or "")
    if not name:
        raise RuntimeError("jig BOM feature has no name")
    return name


def _link_view_to_bom(view: Any, bom_name: str, *, label: str) -> None:
    """Number a view's balloons from the BOM another view is the parent of
    (draw_dt_drive_train_assembly's), read back."""
    view = _early_bound(view, "IView")
    if not view.SetKeepLinkedToBOM(True, bom_name):
        raise RuntimeError(f"{label}: SetKeepLinkedToBOM({bom_name!r}) returned false")
    if (
        not bool(view.GetKeepLinkedToBOM())
        or str(view.GetKeepLinkedToBOMName() or "") != bom_name
    ):
        raise RuntimeError(f"{label}: view is not linked to BOM {bom_name!r}")


def _region_center(region: tuple[float, float, float, float]) -> tuple[float, float]:
    return ((region[0] + region[2]) / 2.0, (region[1] + region[3]) / 2.0)


def _place_reference_view(
    adapter: Any,
    *,
    sheet_name: str = BOM_SHEET,
    region: tuple[float, float, float, float] = REFERENCE_REGION,
    scale: tuple[float, float] = REFERENCE_SCALE,
    smaller_scales: tuple[tuple[float, float], ...] = (),
    label: str = "jig reference",
) -> Any:
    """A visible collapsed source view, fitted from rebuilt native outlines."""
    _activate_sheet(adapter, sheet_name)
    center = _region_center(region)
    view = _place_named_view(
        adapter, spec.ISOMETRIC_VIEW, center, scale, label=label
    )
    set_high_quality_shaded_with_edges(adapter, view, label=label)
    configuration = apply_view_configuration(adapter, view, label=label)
    set_view_exploded_state(
        adapter, view, False, configuration=configuration, label=label
    )
    # Native outline padding need not shrink with model geometry. Measure each
    # permitted scale rather than assuming the first outline scales in proportion.
    for candidate in (scale, *smaller_scales):
        if candidate != scale:
            _set_view_scale(adapter, view, candidate, label=label)
            scale = candidate
        x0, y0, x1, y1 = _view_outline(view, label=label)
        if x1 - x0 <= region[2] - region[0] and y1 - y0 <= region[3] - region[1]:
            break
    if sheet_name == BOM_SHEET:
        center = (center[0], region[3] - BOM_SHEET_CLEARANCE - (y1 - y0) / 2.0)
    _center_view_outline(adapter, view, center, label=label)
    _assert_view_on_sheet(view, bounds=region, label=label)
    return view


def _place_notes_reference_views(adapter: Any) -> dict[str, tuple[float, float]]:
    """Keep each instruction sheet linked to the live assembly at its fitted scale."""
    scales = {}
    for sheet_name, region in NOTES_REFERENCE_REGIONS.items():
        label = f"jig {sheet_name.lower()} reference"
        view = _place_reference_view(
            adapter,
            sheet_name=sheet_name,
            region=region,
            scale=NOTES_REFERENCE_SCALE,
            smaller_scales=NOTES_REFERENCE_SCALE_LADDER[1:],
            label=label,
        )
        scale = tuple(float(value) for value in _early_bound(view, "IView").ScaleRatio)
        scales[sheet_name] = scale
        caption = f"REFERENCE {_scale_text(scale)}"
        x0, y0, x1, _y1 = _view_outline(view, label=label)
        _add_note_block(
            adapter,
            sheet_name,
            caption,
            ((x0 + x1 - len(caption) * NOTE_CHAR_M) / 2.0, y0 - VIEW_LABEL_GAP),
            label=f"{label} caption",
        )
    return scales


def _inspection_transform_point(
    utility: Any, transform: Any, xyz: tuple[float, float, float]
) -> tuple[float, float, float]:
    """Use the native math pipeline for sheet/sketch coordinates."""
    point = _early_bound(utility.CreatePoint(double_array(list(xyz))), "IMathPoint")
    if point is None:
        raise RuntimeError("C2A functional inspection: cannot create native point")
    projected = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
    if projected is None:
        raise RuntimeError("C2A functional inspection: cannot transform native point")
    coordinates = tuple(float(value) for value in (projected.ArrayData or ()))
    if len(coordinates) != 3 or not all(math.isfinite(v) for v in coordinates):
        raise RuntimeError(f"C2A functional inspection: invalid point {coordinates!r}")
    return coordinates


def _inspection_sheet_sketch(
    adapter: Any, *, when: str
) -> tuple[Any, Any, Any, Any, tuple[float, float]]:
    """The sheet view, its sketch, current transform/utility and native scale."""
    sheet = _activate_sheet(adapter, CARTRIDGE_SHEET)
    properties = tuple(float(value) for value in (sheet.GetProperties2() or ()))
    if (
        len(properties) < 4
        or not all(math.isfinite(value) and value > 0.0 for value in properties[2:4])
    ):
        raise RuntimeError("C2A functional inspection: unreadable native sheet scale")
    scale = (properties[2], properties[3])
    # GetFirstView is the sheet itself, not its first assembly view.
    view = _early_bound(
        _early_bound(adapter.currentModel, "IDrawingDoc").GetFirstView(), "IView"
    )
    sketch = _early_bound(view.GetSketch(), "ISketch")
    if sketch is None:
        raise RuntimeError("C2A functional inspection: missing native sheet sketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    if transform is None:
        raise RuntimeError("C2A functional inspection: missing sheet sketch transform")
    matrix = tuple(float(value) for value in (transform.ArrayData or ()))
    if len(matrix) != 16 or not all(math.isfinite(v) for v in matrix):
        raise RuntimeError(f"C2A functional inspection: invalid transform {matrix!r}")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    if utility is None:
        raise RuntimeError("C2A functional inspection: missing native math utility")
    _telemetry.info(
        f"C2A {when}: native_sheet_properties={properties!r}, "
        f"sheet_scale={scale!r}, sheet_view_xform={tuple(view.GetXform() or ())!r}, "
        f"model_to_sketch={matrix!r}"
    )
    return view, sketch, transform, utility, scale


def _assert_pin_tip_inspection(
    adapter: Any, segments: Sequence[Any], *,
    expected_scale: tuple[float, float] | None = None, when: str = "placed",
) -> None:
    """Prove the entire native schematic's paper location, size and visible ink."""
    view, sketch, transform, utility, scale = _inspection_sheet_sketch(adapter, when=when)
    if expected_scale is not None and scale != expected_scale:
        raise RuntimeError(
            f"C2A functional inspection: {when} sheet scale {scale!r} "
            f"changed from authored {expected_scale!r}"
        )
    inverse = _early_bound(transform.Inverse(), "IMathTransform")
    if inverse is None:
        raise RuntimeError("C2A functional inspection: non-invertible sketch transform")
    expected = pin_tip_inspection_lines()
    if len(segments) != len(expected):
        raise RuntimeError("C2A functional inspection: incomplete native schematic")
    paper_points = []
    for index, (segment, endpoints) in enumerate(zip(segments, expected)):
        bound = _early_bound(segment, "ISketchSegment")
        if (
            int(adapter.swApp.IsSame(bound.GetSketch(), sketch)) != 1
            or int(bound.GetType()) != 0  # swSketchLINE
            or bool(bound.ConstructionGeometry)
        ):
            raise RuntimeError(
                f"C2A functional inspection: line {index} is not sheet-owned ink"
            )
        line = _early_bound(segment, "ISketchLine")
        for which, endpoint in zip(("GetStartPoint2", "GetEndPoint2"), endpoints):
            raw = adapter._get_attr_or_call(line, which)
            if raw is None:
                raise RuntimeError(f"C2A functional inspection: line {index} lost {which}")
            point = _early_bound(raw, "ISketchPoint")
            native = (float(point.X), float(point.Y), float(point.Z))
            if index == 0 and which == "GetStartPoint2":
                _telemetry.info(f"C2A {when}: native_line0_start={native!r}")
            actual = _inspection_transform_point(utility, inverse, native)
            if math.dist(actual, (*endpoint, 0.0)) > PIN_TIP_LOCATION_TOL_M:
                raise RuntimeError(
                    f"C2A functional inspection: line {index} {which} prints at "
                    f"{actual!r}, expected paper {endpoint!r}"
                )
            paper_points.append(actual)
    bounds = (
        min(point[0] for point in paper_points),
        min(point[1] for point in paper_points),
        max(point[0] for point in paper_points),
        max(point[1] for point in paper_points),
    )
    left, bottom, right, top = PIN_TIP_INSPECTION_REGION
    if not (left <= bounds[0] < bounds[2] <= right
            and bottom <= bounds[1] < bounds[3] <= top):
        raise RuntimeError(f"C2A functional inspection: off-region native ink {bounds!r}")
    # GetLines4 is native display data for user-drawn sketch lines (projected
    # model polylines deliberately exclude them). Its coordinates are view-local;
    # GetXform supplies the paper origin and scale. This is independent evidence
    # against the old false green: CreateLine returned all 23 segments, but they
    # printed at 1/20 size near the sheet origin, outside the border.
    raw_lines = tuple(float(value) for value in (view.GetLines4(1) or ()))
    xform = tuple(float(value) for value in (view.GetXform() or ()))
    if (
        len(raw_lines) % 12
        or not raw_lines
        or len(xform) != 3
        or not all(math.isfinite(v) for v in (*raw_lines, *xform))
        or xform[2] <= 0.0
    ):
        raise RuntimeError("C2A functional inspection: missing/invalid native display ink")
    ox, oy, scale = xform
    displayed = [
        ((ox + scale * raw_lines[i + 6], oy + scale * raw_lines[i + 7]),
         (ox + scale * raw_lines[i + 9], oy + scale * raw_lines[i + 10]))
        for i in range(0, len(raw_lines), 12)
    ]
    for index, (start, end) in enumerate(expected):
        match = next((
            i for i, (a, b) in enumerate(displayed)
            if min(max(math.dist(start, a), math.dist(end, b)),
                   max(math.dist(start, b), math.dist(end, a)))
            <= PIN_TIP_LOCATION_TOL_M
        ), None)
        if match is None:
            raise RuntimeError(
                f"C2A functional inspection: line {index} missing at its paper location"
            )
        displayed.pop(match)
    _telemetry.info(
        f"C2A functional inspection: {len(expected)} native/display lines, "
        f"paper bounds {tuple(round(v * 1000.0, 4) for v in bounds)} mm"
    )


def _place_pin_tip_inspection(adapter: Any) -> Callable[[], None]:
    """Create paper-sized sheet ink and retain its post-rebuild location proof."""
    _activate_sheet(adapter, CARTRIDGE_SHEET)
    draw = adapter.currentModel
    draw.ClearSelection2(True)
    _early_bound(draw, "IDrawingDoc").EditSheet()
    _view, _sketch, transform, utility, scale = _inspection_sheet_sketch(
        adapter, when="creation"
    )
    manager = _early_bound(draw.SketchManager, "ISketchManager")
    previous_add_to_db = bool(manager.AddToDB)
    segments = []
    manager.AddToDB = True
    try:
        for start, end in pin_tip_inspection_lines():
            # CreateLine takes native sketch coordinates, not paper metres.
            # Follow create_section_view's sheet -> sketch mapping: the sheet
            # scale/origin belong to this live transform, never a typed ×20.
            a = _inspection_transform_point(utility, transform, (*start, 0.0))
            b = _inspection_transform_point(utility, transform, (*end, 0.0))
            segment = manager.CreateLine(*a, *b)
            if segment is None:
                raise RuntimeError("failed to sketch the C2A functional inspection")
            _early_bound(segment, "ISketchSegment").ConstructionGeometry = False
            segments.append(segment)
    finally:
        manager.AddToDB = previous_add_to_db
    draw.ClearSelection2(True)
    for text, xy in pin_tip_inspection_labels():
        _add_note_block(
            adapter, CARTRIDGE_SHEET, text, xy, label="C2A functional inspection",
        )
    rebuild_drawing(adapter, label="C2A functional inspection")
    _assert_pin_tip_inspection(adapter, segments, expected_scale=scale)
    return lambda: _assert_pin_tip_inspection(
        adapter, segments, expected_scale=scale, when="settled"
    )


def _place_finished_view(adapter: Any) -> None:
    """The full-detail finished assembly below the capture sheet's checks."""
    _activate_sheet(adapter, CAPTURE_SHEET)
    label = "jig finished"
    center = _region_center(FINISHED_REGION)
    finished = _place_named_view(
        adapter, spec.ISOMETRIC_VIEW, center, ISOMETRIC_SCALE, label=label
    )
    set_high_quality_shaded_with_edges(adapter, finished, label=label)
    configuration = apply_view_configuration(
        adapter, finished, role=ViewRole.FULL_DETAIL, label=label
    )
    set_view_exploded_state(
        adapter, finished, False, configuration=configuration, label=label
    )
    _center_view_outline(adapter, finished, center, label=label)
    _assert_view_on_sheet(finished, bounds=FINISHED_REGION, label=label)
    assert_full_detail_view(adapter, label="jig assembly")
    scale = tuple(float(value) for value in _early_bound(finished, "IView").ScaleRatio)
    caption = f"FINISHED ASSEMBLY {_scale_text(scale)}"
    x0, y0, x1, _y1 = _view_outline(finished, label=label)
    _add_note_block(
        adapter,
        CAPTURE_SHEET,
        caption,
        ((x0 + x1 - len(caption) * NOTE_CHAR_M) / 2.0, y0 - VIEW_LABEL_GAP),
        label=f"{label} caption",
    )


def _fit_cluster_view(
    adapter: Any, view: Any, cluster: Cluster, configuration: str, *, label: str
) -> tuple[float, float]:
    """Re-scale the isolated view to the largest ladder scale whose measured
    ring fits, then move its ring into the room; returns the scale."""
    placed = cluster.scale
    scale = cluster_ring_scale(_view_outline(view, label=label), placed, label=label)
    while True:
        if scale != placed:
            _set_view_scale(adapter, view, scale, label=label)
            placed = scale
        outline = _view_outline(view, label=label)
        shift, overflows, slide = cluster_ring_fit(outline)
        if not overflows:
            break
        # The outline did not scale in proportion: the next rung down.
        rung = CLUSTER_SCALE_LADDER.index(scale) + 1
        if rung == len(CLUSTER_SCALE_LADDER):
            raise RuntimeError(
                f"{label}: no ladder scale fits the ring: {'; '.join(overflows)}"
            )
        scale = CLUSTER_SCALE_LADDER[rung]
    bound = _early_bound(view, "IView")
    if str(bound.ReferencedConfiguration) != configuration or not bool(
        bound.IsExploded()
    ):
        raise RuntimeError(f"{label}: re-scaling changed the view's configuration")
    center = _region_center(outline)
    _center_view_outline(
        adapter, view, (center[0] + shift[0], center[1] + shift[1]), label=label
    )
    violations = cluster_ring_violations(_view_outline(view, label=label))
    if violations:
        raise RuntimeError(f"{label}: balloon ring " + "; ".join(violations))
    _telemetry.info(
        f"{label}: {_scale_text(scale)}, ring slid {-slide * 1000.0:.1f} mm left"
    )
    return scale


# The relax leaves this much room to the keep-out for the balloons' lag
# behind their view, and corrects at most this many times.
_RELAX_MARGIN = 0.001
_RELAX_PASSES = 3


def keep_out_overshoot(
    circles: Sequence[tuple[float, float, float]],
    outline: tuple[float, float, float, float],
    *,
    keep_out: tuple[float, float, float, float],
) -> float:
    """How far right of ``keep_out``'s left edge the rightmost balloon circle
    (centre x, y, radius) or outline whose bottom is below the keep-out's top
    reaches; negative when they stay clear, ``-inf`` when none is that low."""
    left, _bottom, _right, top = keep_out
    reach = -math.inf
    for x, y, radius in circles:
        if y - radius < top:
            reach = max(reach, x + radius - left)
    if outline[1] < top:
        reach = max(reach, outline[2] - left)
    return reach


def ring_right_slack(
    circles: Sequence[tuple[float, float, float]],
    outline: tuple[float, float, float, float],
    *,
    keep_out: tuple[float, float, float, float],
    cap: float,
) -> float:
    """How far right a ringed cluster view may move back, up to ``cap``.

    ``cluster_ring_fit`` slides a view left until the whole ellipse its
    balloons can land on clears ``keep_out``; the balloons land only at their
    attachments' angles, so the ones actually placed usually need less:
    every balloon and the outline below the keep-out's top stay left of it
    (:func:`keep_out_overshoot`). Review bought-r6: the full-ellipse slide
    left the sheets' right halves empty.
    """
    return max(0.0, min(cap, -keep_out_overshoot(circles, outline, keep_out=keep_out)))


def _relax_cluster_slide(
    adapter: Any, view: Any, landings: Sequence[BalloonLanding], *, label: str
) -> list[BalloonLanding]:
    """Move a ringed cluster view, its balloons with it, back right by its
    placed balloons' slack (:func:`ring_right_slack`) less ``_RELAX_MARGIN``,
    never past the ring's centred position; then every balloon must clear the
    title block and sit inside the border.

    The balloons do not ride with the view exactly (farm r9: 9.54 to 10.02 for
    a 9.70 move), so a balloon the move still left in the keep-out sends the
    view back left by its overshoot, at most ``_RELAX_PASSES`` times.

    Returns ``landings`` with each proven leader landing carried by the
    view's move (the leaders end on model edges, which move with it; farm
    r11: the final check held them to their pre-move points), for the
    drawing's settled balloon check."""
    outline = _view_outline(view, label=label)
    circles = [rendered_balloon_circle(item.note, label=label) for item in landings]
    centre = start = _region_center(outline)
    move = max(
        0.0,
        ring_right_slack(
            circles,
            outline,
            keep_out=TITLE_BLOCK_KEEP_OUT,
            cap=CLUSTER_CENTER[0] - centre[0],
        )
        - _RELAX_MARGIN,
    )
    for _pass in range(_RELAX_PASSES):
        if abs(move) <= 1e-4:
            break
        _center_view_outline(adapter, view, (centre[0] + move, centre[1]), label=label)
        moved = [rendered_balloon_circle(item.note, label=label) for item in landings]
        follow = max(5e-4, 0.05 * abs(move))
        for item, before, after in zip(landings, circles, moved, strict=True):
            if (
                abs(after[0] - before[0] - move) > follow
                or abs(after[1] - before[1]) > follow
            ):
                raise RuntimeError(
                    f"{label}: {item.instance} balloon did not move with its view "
                    f"({before[:2]!r} -> {after[:2]!r}, view moved {move:.6f})"
                )
        _telemetry.info(
            f"{label}: ring moved {move * 1000.0:.1f} mm right, balloons "
            + ", ".join(
                f"{(after[0] - before[0]) * 1000.0:.2f}"
                for before, after in zip(circles, moved, strict=True)
            )
        )
        circles = moved
        outline = _view_outline(view, label=label)
        centre = _region_center(outline)
        overshoot = keep_out_overshoot(circles, outline, keep_out=TITLE_BLOCK_KEEP_OUT)
        move = -(overshoot + _RELAX_MARGIN) if overshoot > 0.0 else 0.0
    shift = (centre[0] - start[0], centre[1] - start[1])
    landings = [
        item
        if item.sheet_xy is None
        else replace(
            item,
            sheet_xy=(item.sheet_xy[0] + shift[0], item.sheet_xy[1] + shift[1]),
        )
        for item in landings
    ]
    # The relax moves the ring sideways only, so it answers for the side
    # borders, held to the ring's contract (each centre BALLOON_RADIUS
    # inside), and the title block it moves toward, held to the rendered ink.
    # The ring's own heights stand (farm r10/r13: the carrier's top CL-dowel
    # balloon, its 5.20 ink 0.2 over the ring's 5.00, unmoved by the relax).
    left, _bottom, right, _top = SHEET_INNER_BORDER
    k0, k1, k2, k3 = TITLE_BLOCK_KEEP_OUT
    for item, (x, y, radius) in zip(landings, circles, strict=True):
        reach = min(radius, BALLOON_RADIUS)
        if (
            x - reach < left
            or x + reach > right
            or (
                x + radius > k0
                and x - radius < k2
                and y - radius < k3
                and y + radius > k1
            )
        ):
            raise RuntimeError(
                f"{label}: {item.instance} balloon at {(x, y)!r}, radius "
                f"{radius:.5f}, leaves the side borders or enters the title block"
            )
    return landings


def _place_cluster_view(
    adapter: Any, cluster: Cluster
) -> tuple[Any, tuple[float, float]]:
    """One cluster's exploded isometric with only its families shown, fitted
    to its sheet; returns the view and its scale."""
    _activate_sheet(adapter, cluster.sheet)
    label = f"jig {cluster.sheet.lower()}"
    view = _place_named_view(
        adapter, spec.ISOMETRIC_VIEW, CLUSTER_CENTER, cluster.scale, label=label
    )
    set_high_quality_shaded_with_edges(adapter, view, label=label)
    # Configuration, then its own explode, then only its families shown.
    configuration = apply_view_configuration(adapter, view, label=label)
    set_view_exploded_state(
        adapter, view, True, configuration=configuration, label=label
    )
    isolate_drawing_view_components(
        adapter,
        view,
        visible_stems=frozenset(cluster.stems + cluster.context),
        label=label,
    )
    return view, _fit_cluster_view(adapter, view, cluster, configuration, label=label)


def capture_support_instances(cluster: Cluster, support: int) -> frozenset[str]:
    """Exact occurrences of one cartridge, including its unballooned block."""
    if support not in (0, 1):
        raise ValueError("the capture sheet has supports 0 and 1")
    return frozenset(
        spec.instance_name(stem, index)
        for stem in (*cluster.stems, spec.PIVOT_BLOCK)
        for index in range(
            support * (spec.QUANTITIES[stem] // 2),
            (support + 1) * (spec.QUANTITIES[stem] // 2),
        )
    )


@dataclass(frozen=True)
class CaptureReading:
    """One real installed feature, in its occurrence's own millimetres."""

    view_index: int
    stem: str
    local_mm: tuple[float, float, float]
    text: str
    text_xy: tuple[float, float]
    index: int = 0
    pick_local_mm: tuple[float, float, float] | None = None


def _capture_local_point(stem: str, world: Sequence[float]) -> tuple[float, float, float]:
    origin, rows = spec.PLACEMENTS[stem][0]
    return tuple(sum((world[i] - origin[i]) * row[i] for i in range(3)) for row in rows)


def capture_readings() -> tuple[CaptureReading, ...]:
    r, pin, washer = spec.retention, spec.pivot_pin, spec.pivot_retainer
    callouts = spec.CAPTURE_READING_CALLOUTS
    rim = r.PIN_STOP_FACE_MEASUREMENT_DIAMETER / 2.0
    mouth = washer.BORE_DIA / 2.0
    land = (mouth + washer.EDGE_BREAK_MAX + washer.OUTER_DIA / 2.0) / 2.0
    def carrier_face(side):
        origin = spec.PIVOT_PIN_ORIGINS[0]
        world = (origin[0] + side * land * spec.PIN_ROWS[0][0],
                 origin[1] + side * land * spec.PIN_ROWS[0][1],
                 spec.trammel.CARRIER_TOP_Z)
        return _capture_local_point(spec.CARRIER, world)
    top = washer.THICKNESS
    hole_top = pin.CROSS_HOLE_STATION + pin.CROSS_HOLE_DIA / 2.0
    bolt_y = r.CAP_BOLT_Y_OFFSETS[0]
    cap_origin = spec.PIVOT_CAP_PLACEMENTS[0][0]
    roof = _capture_local_point(spec.PIVOT_CAP, (
        spec.PIVOT_PIN_ORIGINS[0][0] + r.CAP_POCKET_DIAMETER / 2.0 * spec.PIN_ROWS[0][0],
        spec.PIVOT_PIN_ORIGINS[0][1] + r.CAP_POCKET_DIAMETER / 2.0 * spec.PIN_ROWS[0][1],
        cap_origin[2] + r.CAP_POCKET_DEPTH,
    ))
    return (
        CaptureReading(2, spec.PIVOT_PIN, (-rim, 0.0, pin.FLANGE_BOTTOM_STATION),
                       callouts["lower_rim"], (0.224, 0.143)),
        CaptureReading(2, spec.PIVOT_PIN, (-rim, 0.0, pin.FLANGE_TOP_STATION),
                       callouts["upper_rim"], (0.224, 0.155)),
        CaptureReading(2, spec.PIVOT_CAP, roof,
                       callouts["chamber_excess"], (0.365, 0.128)),
        *(CaptureReading(2, spec.PIVOT_RETAINER, (side * mouth, 0.0, top),
                         callouts["mouth"], (x, 0.199),
                         pick_local_mm=(side * mouth, 0.0, top / 2.0))
          for side, x in ((-1.0, 0.224), (1.0, 0.365))),
        *(CaptureReading(2, spec.CARRIER, carrier_face(side),
                         callouts["carrier_backing_pin_end" if side > 0.0 else "carrier_backing"],
                         (x, 0.184))
          for side, x in ((-1.0, 0.224), (1.0, 0.365))),
        CaptureReading(2, spec.PIVOT_RETAINER, (land, 0.0, 0.0),
                       callouts["running_gap"], (0.365, 0.157)),
        CaptureReading(2, spec.PIVOT_PIN, (0.0, 0.0, pin.OVERALL_LENGTH),
                       callouts["pin_end"], (0.305, 0.214)),
        CaptureReading(2, spec.PIVOT_PIN, (-pin.FIT_DIA / 2.0, 0.0, hole_top),
                       callouts["cross_hole"], (0.224, 0.216),
                       pick_local_mm=(-pin.FIT_DIA / 2.0, 0.0, (hole_top + pin.OVERALL_LENGTH - pin.LEAD_CHAMFER) / 2.0)),
        CaptureReading(2, spec.PIVOT_CLEVIS_PIN,
                       (-spec.clevis_pin.CLEVIS_HEAD_HEIGHT, 0.0,
                        -spec.clevis_pin.CLEVIS_HEAD_DIA / 2.0),
                       callouts["clevis"], (0.224, 0.190)),
        CaptureReading(1, spec.PIVOT_COTTER,
                       (spec.pivot_cotter.EYE_OUTER_RADIUS, -spec.pivot_cotter.COTTER_WIDTH / 2.0, spec.pivot_cotter.EYE_CENTER),
                       callouts["cotter"], (0.288, 0.205)),
        CaptureReading(3, spec.PIVOT_CAP, (0.0, bolt_y, 0.0),
                       callouts["cap_land"], (0.279, 0.2235)),
        CaptureReading(3, spec.PIVOT_CAP_SCREW, (spec.cap_screw.DIMS.head_dia * 0.35, 0.0, 0.0),
                       callouts["underhead"], (0.282, 0.232)),
    )


def _capture_world_point(
    reading: CaptureReading, *, local_mm: tuple[float, float, float] | None = None
) -> tuple[float, float, float]:
    origin, rows = spec.PLACEMENTS[reading.stem][reading.index]
    local = reading.local_mm if local_mm is None else local_mm
    return tuple((origin[axis] + sum(local[k] * rows[k][axis] for k in range(3))) / 1000.0 for axis in range(3))


def capture_cut_points(section_label: str) -> tuple[tuple[float, float, float], ...]:
    """A-A contains pivot + clevis axes; B-B contains one actual bolt row."""
    if section_label == "A":
        origin, rows = spec.PIVOT_PIN_ORIGINS[0], spec.PIN_ROWS
    elif section_label == "B":
        origin, rows = spec.compose(spec.PIVOT_CAP_PLACEMENTS[0], (0.0, spec.retention.CAP_BOLT_Y_OFFSETS[0], 0.0))
    else:
        raise ValueError(f"unknown cartridge section {section_label!r}")
    return tuple(tuple((origin[i] + distance * rows[0][i]) / 1000.0 for i in range(3)) for distance in (-65.0, 65.0))


def _crop_capture_view(adapter: Any, view: Any, centre: tuple[float, float], radius: float, *, label: str) -> Any:
    """Create the native crop and retain its exact selected profile."""
    view = _early_bound(view, "IView")
    draw = adapter.currentModel
    if not _early_bound(draw, "IDrawingDoc").ActivateView(str(view.GetName2())):
        raise RuntimeError(f"{label}: failed to activate crop view")
    draw.ClearSelection2(True)
    sketch = _early_bound(view.GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    points = [_inspection_transform_point(utility, transform, (x, y, 0.0)) for x, y in (centre, (centre[0] + radius, centre[1]))]
    manager = _early_bound(draw.SketchManager, "ISketchManager")
    previous = bool(manager.AddToDB)
    manager.AddToDB = True
    try:
        circle = manager.CreateCircle(*points[0], *points[1])
    finally:
        manager.AddToDB = previous
    if circle is None:
        raise RuntimeError(f"{label}: failed to create crop circle")
    actual_centre, actual_radius = native_circle_geometry(circle, label=label)
    expected_radius = math.dist(*points)
    if math.dist(actual_centre, points[0]) > 1e-7 or abs(actual_radius - expected_radius) > 1e-7:
        raise RuntimeError(f"{label}: created native crop circle moved or changed radius")
    selection = _early_bound(draw.SelectionManager, "ISelectionMgr")
    data = _early_bound(selection.CreateSelectData(), "ISelectData")
    data.View = view
    if _early_bound(circle, "ISketchSegment").Select4(False, data) is not True:
        raise RuntimeError(f"{label}: failed to select native crop circle")
    if int(selection.GetSelectedObjectCount2(-1)) != 1:
        raise RuntimeError(f"{label}: crop circle selection is not one profile")
    status = int(view.Crop2(False, False, 1))
    draw.ClearSelection2(True)
    rebuild_drawing(adapter, label=label)
    view.UpdateViewDisplayGeometry()
    if status != 1 or not bool(view.IsCropped()):
        raise RuntimeError(f"{label}: native crop failed ({status=})")
    return _early_bound(circle, "ISketchSegment")


def _assert_capture_crop(adapter: Any, view: Any, index: int, profile: Any) -> None:
    """Read the retained selected circle through its actual native owner."""
    label = f"jig capture view {index} crop"
    origin = tuple(value / 1000.0 for value in spec.PIVOT_PIN_ORIGINS[0])
    if index == 1:
        anchor, radius = origin, 0.055
    elif index == 2:
        anchor = tuple(origin[i] + (spec.pivot_pin.OVERALL_LENGTH / 2000.0 if i == 2 else 0.0) for i in range(3))
        radius = 0.039
    elif index == 3:
        anchor = tuple(value / 1000.0 for value in spec.PIVOT_CAP_SCREW_PLACEMENTS[0][0])
        radius = 0.014
    else:
        raise ValueError(f"{label}: not an assembled crop view")
    bound = _early_bound(view, "IView")
    segment = _early_bound(profile, "ISketchSegment")
    actual_centre, actual_radius = native_circle_geometry(segment, label=label)
    sketch = _early_bound(segment.GetSketch(), "ISketch")
    if sketch is None:
        raise RuntimeError(f"{label}: retained native crop circle has no sketch owner")
    # Crop2 absorbs the profile; read its current owner, not view-sketch members.
    # Moved view origins invalidate old paper/sketch maps.
    point = model_point_in_view(adapter, bound, anchor, label=label)
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    expected_centre = _inspection_transform_point(utility, transform, (*point, 0.0))
    if math.dist(actual_centre, expected_centre) > 1e-7 or abs(actual_radius - radius) > 1e-7:
        raise RuntimeError(f"{label}: persisted native crop centre or model radius changed")


def _fit_capture_view(adapter: Any, view: Any, region: tuple[float, float, float, float], ladder: Sequence[tuple[float, float]], *, crop_profile: Any = None, margin: float = 0.0, label: str) -> tuple[float, float]:
    view = _early_bound(view, "IView")
    cropped = bool(view.IsCropped())
    if cropped:
        if len(ladder) != 1:
            raise RuntimeError(f"{label}: cropped view requires one pre-authored scale")
        ratio = tuple(float(value) for value in view.ScaleRatio)
        if len(ratio) != 2 or abs(ratio[0] / ratio[1] - ladder[0][0] / ladder[0][1]) > 1e-9:
            raise RuntimeError(f"{label}: cropped view scale differs from its pre-authored scale")
        if crop_profile is None:
            raise RuntimeError(f"{label}: cropped view lost its selected native profile")
    candidates = []
    for scale in ladder:
        if not cropped:
            _set_view_scale(adapter, view, scale, label=label)
        # HLR and scale changes need current geometry, not a pending repaint.
        view.UpdateViewDisplayGeometry()  # VT_VOID
        outline = _view_outline(view, label=label)
        _shift, misses = ring_fit_shift(outline, region, grow=margin)
        if not misses:
            _center_view_outline(adapter, view, _region_center(region), label=label)
            _assert_view_on_sheet(view, margin=margin, bounds=region, label=label)
            return scale
        crop_circles = []
        sketch_transform = None
        if cropped:
            segment = _early_bound(crop_profile, "ISketchSegment")
            centre, radius = native_circle_geometry(segment, label=label)
            sketch = _early_bound(segment.GetSketch(), "ISketch")
            if sketch is None:
                raise RuntimeError(f"{label}: retained native crop circle has no sketch owner")
            transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
            sketch_transform = tuple(float(value) for value in transform.ArrayData)
            inverse = _early_bound(transform.Inverse(), "IMathTransform")
            utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
            sheet_centre = _inspection_transform_point(utility, inverse, centre)
            sheet_rim = _inspection_transform_point(utility, inverse, (centre[0] + radius, centre[1], centre[2]))
            crop_circles.append({
                "sketch_centre": centre, "sketch_radius": radius,
                "sheet_centre": sheet_centre, "sheet_radius": math.dist(sheet_centre, sheet_rim),
            })
        candidates.append({
            "scale": tuple(float(value) for value in view.ScaleRatio),
            "position": tuple(float(value) for value in view.Position),
            "outline": outline, "overflows": misses, "cropped": cropped,
            "crop_circles": crop_circles, "sketch_transform": sketch_transform,
        })
    raise RuntimeError(
        f"{label}: no measured scale fits its reserved field; "
        f"field={region!r}; margin={margin!r}; candidates={candidates!r}"
    )


def _orient_capture_section(adapter: Any, view: Any, axis: Sequence[float]) -> None:
    def axes():
        points = model_points_in_view(adapter, view, ((0.0, 0.0, 0.0), tuple(v / 1000.0 for v in axis), (0.0, 0.0, 0.001)), label="capture section axes")
        return tuple(tuple(p[i] - points[0][i] for i in range(2)) for p in points[1:])
    horizontal, vertical = axes()
    section = _early_bound(view.GetSection(), "IDrSection")
    if horizontal[0] * vertical[1] - horizontal[1] * vertical[0] < 0.0:
        reverse = not bool(section.GetReversedCutDirection())
        section.SetReversedCutDirection(reverse)
        rebuild_drawing(adapter, label="capture section cut direction")
        if bool(section.GetReversedCutDirection()) != reverse:
            raise RuntimeError("capture section: cut direction did not persist")
        horizontal, vertical = axes()
    view.Angle = float(view.Angle) - math.atan2(horizontal[1], horizontal[0])
    rebuild_drawing(adapter, label="capture section orientation")
    horizontal, vertical = axes()
    if horizontal[0] <= 0.0 or vertical[1] <= 0.0 or abs(horizontal[1]) > 1e-8 or abs(vertical[0]) > 1e-8:
        raise RuntimeError("capture section: model axes did not orient right/up")


def _capture_note_extent(note: Any) -> tuple[float, float, float, float]:
    raw = tuple(float(v) for v in (_early_bound(note, "INote").GetExtent() or ()))
    if len(raw) != 6 or not all(math.isfinite(v) for v in raw) or raw[3] <= raw[0] or raw[4] <= raw[1]:
        raise RuntimeError("jig capture: unreadable native note extents")
    return raw[0], raw[1], raw[3], raw[4]


def _capture_note_bounds(note: Any) -> tuple[float, float, float, float]:
    """Native text only; GetExtent also encloses the attached leader."""
    try:
        annotation = _early_bound(_early_bound(note, "INote").GetAnnotation(), "IAnnotation")
        data = _early_bound(annotation.GetDisplayData(), "IDisplayData")
        count = int(data.GetTextCount())
    except Exception as exc:
        raise RuntimeError(f"jig capture: unreadable native note text interface/count; {type(exc).__name__}: {exc}") from exc
    runs = []
    for index in range(count):
        run = {"index": index}
        for key, getter in (
            ("t", "GetTextAtIndex"), ("w", "GetTextInBoxWidthAtIndex"),
            ("h", "GetTextHeightAtIndex"), ("pos", "GetTextPositionAtIndex"),
            ("ref", "GetTextRefPositionAtIndex"), ("ang", "GetTextAngleAtIndex"),
        ):
            try:
                run[key] = getattr(data, getter)(index)
            except Exception as exc:
                run.setdefault("read_errors", []).append((key, f"{type(exc).__name__}: {exc}"))
        runs.append(run)
    texts = []
    invalid = False
    for run in runs:
        text = run.get("t")
        if isinstance(text, str) and not text.strip():
            continue
        if run.get("read_errors"):
            invalid = True
            continue
        try:
            if not isinstance(text, str):
                raise ValueError("native text is not a string")
            width, height = float(run["w"]), float(run["h"])
            position = tuple(float(value) for value in run["pos"])
            reference, angle = run["ref"], float(run["ang"])
            if (
                min(width, height) <= 0 or len(position) < 2
                or not isinstance(reference, int) or isinstance(reference, bool) or reference not in range(6)
                or not all(math.isfinite(value) for value in (width, height, angle, *position))
            ):
                raise ValueError("native text size, position, angle or reference is invalid")
            # The kit's native swTextPosition_e anchor normalization, not a font-width estimate.
            dx, dy = ((0, -height), (0, 0), (-width / 2, -height / 2),
                      (-width, -height), (-width, 0), (-width / 2, -height))[reference]
            cosine, sine = math.cos(angle), math.sin(angle)
            texts.append({
                "t": text, "w": width, "h": height, "ref": 1, "ang": angle,
                "pos": (position[0] + dx * cosine - dy * sine,
                        position[1] + dx * sine + dy * cosine, 0.0),
            })
        except Exception as exc:
            invalid = True
            run["validation_error"] = f"{type(exc).__name__}: {exc}"
    if invalid or not texts:
        raise RuntimeError(f"jig capture: unreadable native note text geometry; count={count}; runs={runs!r}")
    try:
        box = display_box({"texts": texts})
        bounds = () if box is None else (box.xmin, box.ymin, box.xmax, box.ymax)
        if len(bounds) != 4 or not all(math.isfinite(value) for value in bounds) or bounds[2] <= bounds[0] or bounds[3] <= bounds[1]:
            raise ValueError("native text box is missing or degenerate")
    except Exception as exc:
        raise RuntimeError(f"jig capture: unreadable native note text box; runs={runs!r}; {type(exc).__name__}: {exc}") from exc
    return bounds


def _capture_inside(box: Sequence[float], region: Sequence[float]) -> bool:
    return region[0] <= box[0] < box[2] <= region[2] and region[1] <= box[1] < box[3] <= region[3]


def _capture_overlap(a: Sequence[float], b: Sequence[float]) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def _assert_capture_component_identity(
    adapter: Any, component: Any, leaf: Any, *, view_index: int, label: str
) -> Any:
    """The same exact source-occurrence proof for reading and hidden owners."""
    path = leaf.path.replace("\\", "/")
    source_file = str(SOURCE)
    actual = owner_file = leaf_file = ""
    chain = []
    same_part = same_source = False
    metadata_error = None
    try:
        component = _early_bound(_bind(component, "IComponent2"), "IComponent2")
        if component is not None:
            actual = str(component.Name2 or "").replace("\\", "/")
            owner_file = str(component.GetPathName() or "")
        native_leaf = _early_bound(_bind(leaf.component, "IComponent2"), "IComponent2")
        leaf_file = str(native_leaf.GetPathName() or "") if native_leaf is not None else ""
        parent = _early_bound(_bind(component.GetParent(), "IComponent2"), "IComponent2") if component is not None else None
        if parent is not None:
            chain.append((str(parent.Name2 or "").replace("\\", "/"), str(parent.GetPathName() or "")))
            extra = _early_bound(_bind(parent.GetParent(), "IComponent2"), "IComponent2")
            if extra is not None:
                chain.append((str(extra.Name2 or "").replace("\\", "/"), str(extra.GetPathName() or "")))
        same_part = bool(owner_file and leaf_file and Path(owner_file).resolve() == Path(leaf_file).resolve())
        same_source = bool(
            len(chain) == 1 and chain[0][1] and source_file
            and Path(chain[0][1]).resolve() == Path(source_file).resolve()
        )
    except Exception as exc:
        metadata_error = exc
    evidence = (
        f"actual_owner={actual!r}; occurrence_path={path!r}; owner_file={owner_file!r}; "
        f"leaf_file={leaf_file!r}; source_file={source_file!r}; parent_chain={chain!r}; "
        f"depth={'at least 2' if len(chain) > 1 else len(chain)}"
    )
    if metadata_error is not None:
        raise RuntimeError(f"{label}: cannot read native source occurrence; {evidence}") from metadata_error
    valid = same_part and "/" not in path and (
        (view_index == 1 and actual == path and not chain)
        or (
            view_index in (2, 3) and same_source and chain[0][0]
            and actual == f"{chain[0][0]}/{path}"
        )
    )
    if not valid:
        raise RuntimeError(f"{label}: component did not match source occurrence {path!r}; {evidence}")
    return component


def _capture_reading_component(
    adapter: Any, reading: CaptureReading, entity: Any, leaves: Sequence[Any], *, label: str
) -> Any:
    wanted = spec.instance_name(reading.stem, reading.index)
    matches = [leaf for leaf in leaves if leaf.visible and leaf.path.replace("\\", "/") == wanted]
    if len(matches) != 1:
        raise RuntimeError(f"{label}: expected one visible occurrence {wanted!r}, got {len(matches)}")
    try:
        owner = _early_bound(_bind(entity, "IEntity"), "IEntity").GetComponent() if entity is not None else None
    except Exception as exc:
        raise RuntimeError(f"{label}: cannot read native reading-edge owner for {wanted!r}") from exc
    try:
        return _assert_capture_component_identity(
            adapter, owner, matches[0], view_index=reading.view_index, label=label
        )
    except RuntimeError as exc:
        raise RuntimeError(f"{label}: reading point did not select {wanted!r}'s own edge; {exc}") from exc


def _capture_view_leaves(adapter: Any, view: Any, *, view_index: int, label: str) -> tuple[Any, ...]:
    leaves = _view_component_leaves(adapter, view, label=label)
    if view_index not in (2, 3):
        return leaves
    # Generated section-tree Visible flags stay True for view-hidden parts.
    # Read the native view's hidden occurrences, with the same source proof.
    try:
        hidden_components = tuple(_early_bound(view, "IView").GetHiddenComponents() or ())
    except Exception as exc:
        raise RuntimeError(f"{label}: cannot read native section hidden components") from exc
    by_path: dict[str, list[Any]] = {}
    for leaf in leaves:
        by_path.setdefault(leaf.path.replace("\\", "/"), []).append(leaf)
    hidden_paths = set()
    for owner in hidden_components:
        actual = parent_name = parent_file = ""
        try:
            component = _early_bound(_bind(owner, "IComponent2"), "IComponent2")
            actual = str(component.Name2 or "").replace("\\", "/")
            parent = _early_bound(_bind(component.GetParent(), "IComponent2"), "IComponent2")
            parent_name = str(parent.Name2 or "").replace("\\", "/") if parent is not None else ""
            parent_file = str(parent.GetPathName() or "") if parent is not None else ""
            extra = _early_bound(_bind(parent.GetParent(), "IComponent2"), "IComponent2") if parent is not None else None
        except Exception as exc:
            raise RuntimeError(
                f"{label}: cannot read native hidden occurrence; actual_owner={actual!r}; "
                f"parent_name={parent_name!r}; parent_file={parent_file!r}; source_file={str(SOURCE)!r}"
            ) from exc
        if not parent_name or not parent_file or Path(parent_file).resolve() != SOURCE.resolve() or extra is not None:
            raise RuntimeError(
                f"{label}: hidden occurrence has no unique authored-source parent; actual_owner={actual!r}; "
                f"parent_name={parent_name!r}; parent_file={parent_file!r}; source_file={str(SOURCE)!r}; "
                f"extra_parent={extra is not None}"
            )
        # This validated native prefix is only an index key; full equality and
        # the shared native part/source proof remain the acceptance contract.
        prefix = f"{parent_name}/"
        matches = by_path.get(actual[len(prefix):], ()) if actual.startswith(prefix) else ()
        if len(matches) != 1 or not matches[0].path or actual != prefix + matches[0].path.replace("\\", "/"):
            raise RuntimeError(f"{label}: hidden occurrence has no unique exact view leaf; actual_owner={actual!r}; parent_name={parent_name!r}")
        leaf = matches[0]
        _assert_capture_component_identity(adapter, component, leaf, view_index=view_index, label=f"{label}: hidden occurrence")
        path = leaf.path.replace("\\", "/")
        if path in hidden_paths:
            raise RuntimeError(f"{label}: duplicate native hidden occurrence {path!r}")
        hidden_paths.add(path)
    return tuple(replace(leaf, visible=leaf.path.replace("\\", "/") not in hidden_paths) for leaf in leaves)


def _place_capture_readings(adapter: Any, views: Sequence[Any]) -> tuple[tuple[Any, ...], ...]:
    records = []
    leaves_by_view = {}
    for reading in capture_readings():
        view = views[reading.view_index]
        bound_view = _early_bound(view, "IView")
        label = f"jig capture {reading.text.splitlines()[0]}"
        world = _capture_world_point(reading)
        point = model_point_in_view(adapter, view, world, label=label)
        pick_point = point if reading.pick_local_mm is None else model_point_in_view(
            adapter, view, _capture_world_point(reading, local_mm=reading.pick_local_mm), label=label
        )
        context = f"local_mm={reading.local_mm}; model_m={world}; sheet_m={point}"
        if not _early_bound(adapter.currentModel, "IDrawingDoc").ActivateView(str(view.GetName2())):
            raise RuntimeError(f"{label}: failed to activate reading view; {context}")
        adapter.currentModel.ClearSelection2(True)
        bound_view.UpdateViewDisplayGeometry()
        with _zoomed_on(adapter, pick_point, _HIT_ZOOM_HALF):
            picked = adapter.currentModel.Extension.SelectByID2(
                "", "EDGE", *pick_point, 0.0, False, 0, null_callout(), 0
            )
        if not picked:
            raise RuntimeError(f"{label}: failed to select reading edge; {context}")
        manager = _early_bound(_bind(adapter.currentModel.SelectionManager, "ISelectionMgr"), "ISelectionMgr")
        edge = None
        count = int(manager.GetSelectedObjectCount2(-1))
        for index in range(1, count + 1):
            native_type = int(manager.GetSelectedObjectType3(index, -1))
            selected = manager.GetSelectedObject6(index, -1)
            if native_type == 1 and selected is not None:  # swSelEDGES
                if edge is not None:
                    raise RuntimeError(f"{label}: expected exactly one reading EDGE; {context}")
                edge = _early_bound(_bind(selected, "IEdge"), "IEdge")
            elif (
                native_type == 12 and selected is not None  # swSelDRAWINGVIEWS
                and int(adapter.swApp.IsSame(_early_bound(_bind(selected, "IView"), "IView"), view)) == 1
            ):
                pass
            else:
                raise RuntimeError(
                    f"{label}: unexpected reading selection context at slot {index}, "
                    f"type={native_type}, entity_present={selected is not None}; {context}"
                )
        if edge is None:
            raise RuntimeError(f"{label}: expected exactly one reading EDGE, got none; {context}")
        if reading.view_index not in leaves_by_view:
            leaves_by_view[reading.view_index] = _capture_view_leaves(adapter, view, view_index=reading.view_index, label=label)
        _capture_reading_component(
            adapter, reading, edge, leaves_by_view[reading.view_index], label=label
        )
        if reading.view_index in (2, 3):
            local = tuple(value / 1000.0 for value in reading.local_mm)
            try:
                closest = tuple(float(value) for value in (edge.GetClosestPointOn(*local) or ()))[:3]
            except Exception as exc:
                raise RuntimeError(f"{label}: native edge closest-point query failed; {context}") from exc
            if len(closest) != 3 or not all(math.isfinite(value) for value in closest):
                raise RuntimeError(f"{label}: native edge closest point is invalid: {closest!r}; {context}")
            error_sq = sum((actual - expected) ** 2 for actual, expected in zip(closest, local, strict=True))
            if error_sq > 1e-14:  # ViewEdges.exact_line_through's 1e-8 mm².
                raise RuntimeError(
                    f"{label}: reading edge does not pass through its section point; "
                    f"closest_mm={math.sqrt(error_sq) * 1000.0:g}; {context}"
                )
        elif reading.view_index != 1:
            raise RuntimeError(f"{label}: unsupported reading view role {reading.view_index}")
        # The plan note identifies hardware regions, not a static 3D gap.
        # Reselect just the verified edge: coordinate picks also select its view.
        adapter.currentModel.ClearSelection2(True)
        if not bound_view.SelectEntity(edge, False):
            raise RuntimeError(f"{label}: failed to reselect reading edge; {context}")
        count = int(manager.GetSelectedObjectCount2(-1))
        if count != 1 or int(manager.GetSelectedObjectType3(1, -1)) != 1:
            raise RuntimeError(f"{label}: reading edge reselection is not one native EDGE; {context}")
        entity = _early_bound(_bind(manager.GetSelectedObject6(1, -1), "IEdge"), "IEdge")
        if entity is None or int(adapter.swApp.IsSame(entity, edge)) != 1:
            raise RuntimeError(f"{label}: reading edge reselection substituted another entity; {context}")
        if manager.SetSelectionPoint2(1, -1, *point, 0.0) is not True:
            raise RuntimeError(f"{label}: could not set native reading point")
        note = adapter.currentModel.InsertNote(reading.text)
        if note is None:
            raise RuntimeError(f"{label}: native attached note failed")
        note = _early_bound(note, "INote")
        annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
        format_ = _early_bound(annotation.GetTextFormat(0), "ITextFormat")
        format_.CharHeight = CAPTURE_NOTE_HEIGHT
        if not annotation.SetTextFormat(0, False, format_):
            raise RuntimeError(f"{label}: failed to set reading-label height")
        if annotation.SetLeader3(1, 0, True, False, False, False) != 0:
            raise RuntimeError(f"{label}: failed to create attached leader")
        if not annotation.SetPosition2(*reading.text_xy, 0.0):
            raise RuntimeError(f"{label}: failed to position reading label")
        records.append((reading, note, entity))
        adapter.currentModel.ClearSelection2(True)
    rebuild_drawing(adapter, label="capture attached reading labels")
    return tuple(records)


def _assert_capture_section(adapter: Any, parent: Any, view: Any, letter: str) -> None:
    label = f"jig capture section {letter}-{letter}"
    section = _early_bound(view.GetSection(), "IDrSection")
    if section is None or not bool(section.GetAutoHatch()) or str(section.GetLabel()) != letter:
        raise RuntimeError(f"{label}: missing real labelled auto-hatched section")
    # A deliberately local removed section closes within the large carrier.
    # It is not an accidentally short full cut; keep out-of-plane keeper ink.
    if not bool(section.GetPartialSection()) or bool(section.GetDisplayOnlySurfaceCut()) or bool(section.ExcludeFasteners):
        raise RuntimeError(f"{label}: wrong local cut or hidden fastener/secondary geometry")
    if int(adapter.swApp.IsSame(section.GetView(), parent)) != 1:
        raise RuntimeError(f"{label}: wrong native cutting-line parent")
    if int(view.GetDisplayMode2()) != 2 or bool(view.GetUseParentDisplayMode()):
        raise RuntimeError(f"{label}: section must independently remove hidden lines")
    axis = spec.PIN_ROWS[0] if letter == "A" else spec.PIVOT_CAP_PLACEMENTS[0][1][0]
    axes = model_points_in_view(adapter, view, ((0.0, 0.0, 0.0), tuple(v / 1000.0 for v in axis), (0.0, 0.0, 0.001)), label=label)
    horizontal, vertical = (tuple(p[i] - axes[0][i] for i in range(2)) for p in axes[1:])
    if horizontal[0] <= 0.0 or vertical[1] <= 0.0 or abs(horizontal[1]) > 1e-8 or abs(vertical[0]) > 1e-8:
        raise RuntimeError(f"{label}: settled cut axes are not horizontal/right and vertical/up")
    paper_points = model_points_in_view(adapter, parent, capture_cut_points(letter), label=label)
    sketch = _early_bound(_early_bound(parent, "IView").GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    points = tuple(_inspection_transform_point(utility, transform, (*point, 0.0)) for point in paper_points)
    raw = tuple(float(v) for v in (section.GetLineInfo() or ()))
    # IDrSection.SetLineInfo documents GetLineInfo's paired XYZ endpoints.
    if len(raw) != 6 or not all(math.isfinite(v) for v in raw):
        raise RuntimeError(f"{label}: not one readable straight native cut plane")
    a, b = points
    length = math.dist(a, b)
    actual = (raw[:3], raw[3:])
    endpoint_drift = min(
        max(math.dist(found, wanted) for found, wanted in zip(actual, expected))
        for expected in (points, tuple(reversed(points)))
    )
    if length <= 0.0 or abs(math.dist(*actual) - length) > 1e-7 or endpoint_drift > 1e-7:
        raise RuntimeError(f"{label}: native cut plane misses its model reading axes")
    for accessor, count in (("GetArrowInfo", 12), ("GetTextInfo", 6)):
        values = tuple(float(v) for v in (getattr(section, accessor)() or ()))
        if len(values) != count or not all(math.isfinite(v) for v in values):
            raise RuntimeError(f"{label}: unreadable native cut arrows/labels")
        for i in range(0, count, 3):
            x, y = values[i:i + 2]
            if not (CAPTURE_READING_REGION[0] <= x <= CAPTURE_READING_REGION[2]
                    and CAPTURE_READING_REGION[1] <= y <= CAPTURE_READING_REGION[3]):
                raise RuntimeError(f"{label}: native cut arrows/labels leave reading field")


def _assert_capture_coverage(landings: Sequence[BalloonLanding], stems: Sequence[str]) -> None:
    if sorted(item.stem for item in landings) != sorted((*stems, spec.BEARING)):
        raise RuntimeError("jig capture: require every family once and exactly two bearings")
    bearings = [item for item in landings if item.stem == spec.BEARING]
    if {item.instance for item in bearings} != {spec.instance_name(spec.BEARING, i) for i in (0, 1)}:
        raise RuntimeError("jig capture: item 14 must land on two distinct actual bearings")
    if any(str(_early_bound(item.note, "INote").GetBomBalloonText(True)).strip() != str(BOM_ITEM_NUMBERS[spec.BEARING]) for item in bearings):
        raise RuntimeError("jig capture: both bearing balloons must resolve to item 14")


def _assert_capture_sheet(
    adapter: Any, views: Sequence[Any], scales: Sequence[tuple[float, float]],
    records: Sequence[tuple[Any, ...]], landings: Sequence[BalloonLanding] = (),
    *, crop_profiles: Sequence[Any],
) -> None:
    sheet = _activate_sheet(adapter, PIVOT_CAPTURE_SHEET)
    actual_views = tuple(sheet.GetViews() or ())
    if len(views) != 4 or len(actual_views) != 4 or any(int(adapter.swApp.IsSame(a, b)) != 1 for a, b in zip(actual_views, views)):
        raise RuntimeError("jig capture: expected exactly four ordered native model views")
    if len(crop_profiles) != 3:
        raise RuntimeError("jig capture: expected three selected native crop profiles")
    cluster = next(c for c in CLUSTERS if c.sheet == PIVOT_CAPTURE_SHEET)
    installed = capture_support_instances(cluster, 0) | {spec.instance_name(spec.CARRIER, 0)}
    leaves_by_view = {}
    for index, (view, scale, region) in enumerate(zip(views, scales, CAPTURE_VIEW_REGIONS, strict=True)):
        bound = _early_bound(view, "IView")
        ratio = tuple(float(v) for v in bound.ScaleRatio)
        configuration = SIMPLIFIED_VIEW_CONFIGURATION if index == 0 else ASSEMBLY_VIEW_CONFIGURATION
        if len(ratio) != 2 or abs(ratio[0] / ratio[1] - scale[0] / scale[1]) > 1e-9 or str(bound.ReferencedConfiguration) != configuration or bool(bound.IsExploded()) != (index == 0):
            raise RuntimeError(f"jig capture view {index}: changed scale/configuration/exploded state")
        leaves_by_view[index] = _capture_view_leaves(adapter, view, view_index=index, label="jig capture")
        shown = {leaf.path for leaf in leaves_by_view[index] if leaf.visible}
        expected = capture_support_instances(cluster, 0) if index == 0 else installed
        if shown != expected:
            census = []
            for census_index, census_view in enumerate(views):
                expected = capture_support_instances(cluster, 0) if census_index == 0 else installed
                try:
                    if census_index not in leaves_by_view:
                        leaves_by_view[census_index] = _capture_view_leaves(adapter, census_view, view_index=census_index, label="jig capture isolation census")
                    leaves = leaves_by_view[census_index]
                    actual = {leaf.path for leaf in leaves if leaf.visible}
                    missing, extra = expected - actual, actual - expected
                    offending = sorted(
                        (leaf.name, leaf.path, leaf.visible) for leaf in leaves
                        if not leaf.path or leaf.path in missing | extra
                    )
                    census.append(
                        f"view {census_index}: expected={sorted(expected)!r}; actual={sorted(actual)!r}; "
                        f"missing={sorted(missing)!r}; extra={sorted(extra)!r}; leaves={offending!r}"
                    )
                except Exception as exc:
                    census.append(f"view {census_index}: read_error={exc!r}")
            raise RuntimeError(f"jig capture view {index}: wrong visible occurrence isolation; isolation_census={census!r}")
        if index:
            if not bool(bound.IsCropped()):
                raise RuntimeError(f"jig capture view {index}: assembled reading view lost its crop")
            _assert_capture_crop(adapter, bound, index, crop_profiles[index - 1])
        if index and any(bool(_early_bound(note, "INote").IsBomBalloon()) for note in (bound.GetNotes() or ())):
            raise RuntimeError(f"jig capture view {index}: assembled reading views must remain unballooned")
        _assert_view_on_sheet(view, margin=BALLOON_RING_REACH if index == 0 else 0.0,
                              bounds=region, label=f"jig capture view {index}")
    _assert_capture_section(adapter, views[1], views[2], "A")
    _assert_capture_section(adapter, views[1], views[3], "B")
    notes = []
    locator_captions = [note for note in (views[1].GetNotes() or ())
                        if str(_early_bound(note, "INote").GetText() or "").startswith("ASSEMBLED PLAN")]
    if len(locator_captions) != 1 or str(_early_bound(locator_captions[0], "INote").GetText()) != f"ASSEMBLED PLAN {_scale_text(scales[1])}":
        raise RuntimeError("jig capture: locator lost its independently fitted scale caption")
    notes.append((locator_captions[0], _capture_note_bounds(locator_captions[0]), "locator caption"))
    leaders = []
    for reading, note, entity in records:
        annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
        label = f"jig capture {reading.text.splitlines()[0]} {reading.local_mm}"
        if int(annotation.OwnerType) != 0 or str(note.GetText()).replace("\r\n", "\n") != reading.text:
            raise RuntimeError(f"{label}: changed text or lost drawing-view ownership")
        if not any(int(adapter.swApp.IsSame(note, owned)) == 1 for owned in (views[reading.view_index].GetNotes() or ())):
            raise RuntimeError(f"{label}: reading label is not owned by its actual model view")
        height = float(_early_bound(annotation.GetTextFormat(0), "ITextFormat").CharHeight)
        if abs(height - CAPTURE_NOTE_HEIGHT) > 1e-8:
            raise RuntimeError(f"{label}: native reading-label height changed")
        try:
            _capture_reading_component(
                adapter, reading, entity, leaves_by_view[reading.view_index], label=label
            )
        except RuntimeError as exc:
            raise RuntimeError(f"{label}: lost source occurrence edge ownership; {exc}") from exc
        _assert_attached_to(adapter, annotation, entity, entity_type="EDGE", what="reading label", label=label)
        point = model_point_in_view(adapter, views[reading.view_index], _capture_world_point(reading), label=label)
        _assert_leader_lands(annotation, point, what="reading label", label=label, tolerance=0.0002)
        bounds = _capture_note_bounds(note)
        if not _capture_inside(bounds, CAPTURE_READING_REGION):
            raise RuntimeError(f"{label}: native reading label leaves its field")
        notes.append((note, bounds, label))
        raw = tuple(float(v) for v in annotation.GetLeaderPointsAtIndex(0))
        leaders.extend(LeaderSegment(label=label, kind="note", x0=raw[i], y0=raw[i+1], x1=raw[i+3], y1=raw[i+4]) for i in range(0, len(raw) - 3, 3))
        if any(_segment_crosses_box(segment, _view_outline(other, label=label), inset=0.001)
               for segment in leaders if segment.label == label
               for other in views[1:] if other is not views[reading.view_index]):
            raise RuntimeError(f"{label}: native reading leader crosses another view")
    for view in views[2:]:
        captions = [note for note in (view.GetNotes() or ()) if "<VLLABEL>" in str(_early_bound(note, "INote").PropertyLinkedText or "")]
        if len(captions) != 1:
            raise RuntimeError("jig capture: missing native linked section caption")
        notes.append((captions[0], _capture_note_bounds(captions[0]), "section caption"))
    whole_bounds = tuple(_capture_note_extent(note) for note, _box, _label in notes)
    def refuse_layout(reason: str) -> None:
        rectangles = [
            {
                "index": j, "label": label, "bbox_m": bounds,
                "whole_bbox_m": whole_bounds[j],
                "field_gaps_m": (
                    bounds[0] - CAPTURE_READING_REGION[0], bounds[1] - CAPTURE_READING_REGION[1],
                    CAPTURE_READING_REGION[2] - bounds[2], CAPTURE_READING_REGION[3] - bounds[3],
                ),
                "whole_field_gaps_m": (
                    whole_bounds[j][0] - CAPTURE_READING_REGION[0], whole_bounds[j][1] - CAPTURE_READING_REGION[1],
                    CAPTURE_READING_REGION[2] - whole_bounds[j][2], CAPTURE_READING_REGION[3] - whole_bounds[j][3],
                ),
            }
            for j, (_native_note, bounds, label) in enumerate(notes)
        ]
        view_outlines = []
        for view_index, reading_view in enumerate(views[1:], 1):
            try:
                view_outlines.append({"view_index": view_index, "bbox_m": _view_outline(reading_view, label="jig capture")})
            except Exception as exc:
                view_outlines.append({"view_index": view_index, "error": f"{type(exc).__name__}: {exc}"})
        layout = {
            "field_m": CAPTURE_READING_REGION,
            "rectangles": rectangles,
            "outside": [j for j, (_native_note, bounds, _label) in enumerate(notes) if not _capture_inside(bounds, CAPTURE_READING_REGION)],
            "whole_outside": [j for j, bounds in enumerate(whole_bounds) if not _capture_inside(bounds, CAPTURE_READING_REGION)],
            "overlaps": [
                {
                    "a": j, "b": k,
                    "gaps_m": (
                        max(bounds[0], other[1][0]) - min(bounds[2], other[1][2]),
                        max(bounds[1], other[1][1]) - min(bounds[3], other[1][3]),
                    ),
                }
                for j, (_native_note, bounds, _label) in enumerate(notes)
                for k, other in enumerate(notes[j + 1:], j + 1)
                if _capture_overlap(bounds, other[1])
            ],
            "view_outlines": view_outlines,
            "model_overlaps": [
                (rectangle["index"], outline["view_index"])
                for rectangle in rectangles for outline in view_outlines
                if "bbox_m" in outline and _capture_overlap(rectangle["bbox_m"], outline["bbox_m"])
            ],
            "leaders": [
                (segment.label, segment.kind, segment.x0, segment.y0, segment.x1, segment.y1)
                for segment in leaders
            ],
            "leader_label_crossings": [
                (j, rectangle["index"])
                for j, segment in enumerate(leaders) for rectangle in rectangles
                if segment.label != rectangle["label"] and _segment_crosses_box(segment, rectangle["bbox_m"], inset=0.0)
            ],
            "leader_crossings": [
                (crossing.a.label, crossing.b.label, crossing.x, crossing.y)
                for crossing in find_leader_leader_crossings(leaders)
            ],
        }
        raise RuntimeError(f"{reason}; layout={layout!r}")

    for i, (_note, box, owner_label) in enumerate(notes):
        if not _capture_inside(box, CAPTURE_READING_REGION) or not _capture_inside(whole_bounds[i], CAPTURE_READING_REGION) or any(_capture_overlap(box, other[1]) for other in notes[i + 1:]):
            refuse_layout("jig capture: native captions/reading labels overlap or leave field")
        if any(_capture_overlap(box, _view_outline(view, label="jig capture")) for view in views[1:]):
            refuse_layout("jig capture: native caption/reading label covers model geometry")
        if any(segment.label != owner_label and _segment_crosses_box(segment, box, inset=0.0) for segment in leaders):
            refuse_layout("jig capture: native reading leader crosses another label/caption")
    if find_leader_leader_crossings(leaders):
        refuse_layout("jig capture: reading-label leaders cross")
    if landings:
        _assert_capture_coverage(landings, cluster.stems)
        native_balloons = tuple(note for note in (views[0].GetNotes() or ()) if _early_bound(note, "INote").IsBomBalloon())
        if len(native_balloons) != len(landings) or any(
            not any(int(adapter.swApp.IsSame(note, landing.note)) == 1 for landing in landings)
            for note in native_balloons
        ):
            raise RuntimeError("jig capture: native exploded balloons differ from proved landings")
    for landing in landings:
        x, y, radius = rendered_balloon_circle(landing.note, label="jig capture")
        if not _capture_inside((x-radius, y-radius, x+radius, y+radius), CAPTURE_EXPLODED_REGION):
            raise RuntimeError("jig capture: balloon leaves exploded field")


def _place_capture_sheet(adapter: Any, cluster: Cluster) -> tuple[tuple[Any, ...], tuple[tuple[float, float], ...], tuple[tuple[Any, ...], ...], tuple[Any, ...]]:
    _activate_sheet(adapter, cluster.sheet)
    exploded = _place_named_view(adapter, spec.ISOMETRIC_VIEW, _region_center(CAPTURE_EXPLODED_REGION), cluster.scale, label="jig capture exploded")
    set_high_quality_shaded_with_edges(adapter, exploded, label="jig capture exploded")
    configuration = apply_view_configuration(adapter, exploded, label="jig capture exploded")
    set_view_exploded_state(adapter, exploded, True, configuration=configuration, label="jig capture exploded")
    isolate_drawing_view_components(adapter, exploded, visible_stems=capture_support_instances(cluster, 0), label="jig capture exploded")
    scale = _fit_capture_view(adapter, exploded, CAPTURE_EXPLODED_REGION, CLUSTER_SCALE_LADDER[CLUSTER_SCALE_LADDER.index(cluster.scale):], margin=BALLOON_RING_REACH, label="jig capture exploded")
    installed = capture_support_instances(cluster, 0) | {spec.instance_name(spec.CARRIER, 0)}
    locator = _place_named_view(adapter, spec.PLAN_VIEW, (0.250, 0.242), CAPTURE_LOCATOR_SCALE, label="jig capture locator")
    configuration = apply_view_configuration(adapter, locator, role=ViewRole.FULL_DETAIL, label="jig capture locator")
    set_view_exploded_state(adapter, locator, False, configuration=configuration, label="jig capture locator")
    isolate_drawing_view_components(adapter, locator, visible_stems=installed, label="jig capture locator")
    origin = tuple(v / 1000.0 for v in spec.PIVOT_PIN_ORIGINS[0])
    centre = model_point_in_view(adapter, locator, origin, label="jig capture locator")
    locator_profile = _crop_capture_view(adapter, locator, centre, 0.055 / 4.0, label="jig capture locator")
    set_hidden_lines_removed(adapter, locator)
    locator_scale = _fit_capture_view(adapter, locator, CAPTURE_VIEW_REGIONS[1], (CAPTURE_LOCATOR_SCALE,), crop_profile=locator_profile, label="jig capture locator")
    if not _early_bound(adapter.currentModel, "IDrawingDoc").ActivateView(str(locator.GetName2())):
        raise RuntimeError("jig capture: could not activate locator caption owner")
    if add_note(adapter, f"ASSEMBLED PLAN {_scale_text(locator_scale)}", 0.224, 0.220, height=CAPTURE_NOTE_HEIGHT) is None:
        raise RuntimeError("jig capture: failed to place locator scale caption")
    views = [exploded, locator]
    scales = [scale, locator_scale]
    crop_profiles = [locator_profile]
    for index, letter in enumerate(("A", "B"), start=2):
        section_scale = (1, 2)
        points = model_points_in_view(adapter, locator, capture_cut_points(letter), label=f"jig capture cut {letter}")
        view = _early_bound(create_section_view(adapter, locator, line_start=points[0], line_end=points[1],
                            view_xy=_region_center(CAPTURE_VIEW_REGIONS[index]), section_label=letter,
                            scale=section_scale, partial=True, label=f"jig capture section {letter}"), "IView")
        # Child occurrence flags do not reliably inherit; isolate it explicitly.
        isolate_drawing_view_components(adapter, view, visible_stems=installed, label=f"jig capture section {letter}")
        if str(view.ReferencedConfiguration) != ASSEMBLY_VIEW_CONFIGURATION or bool(view.IsExploded()):
            raise RuntimeError("jig capture: section did not inherit full-detail collapsed parent")
        section = _early_bound(view.GetSection(), "IDrSection")
        section.SetDisplayOnlySurfaceCut(False)
        _orient_capture_section(adapter, view, spec.PIN_ROWS[0] if letter == "A" else spec.PIVOT_CAP_PLACEMENTS[0][1][0])
        if letter == "A":
            anchor = tuple(origin[i] + (spec.pivot_pin.OVERALL_LENGTH / 2000.0 if i == 2 else 0.0) for i in range(3))
            radius = 0.039
        else:
            anchor = tuple(v / 1000.0 for v in spec.PIVOT_CAP_SCREW_PLACEMENTS[0][0])
            radius = 0.014
        centre = model_point_in_view(adapter, view, anchor, label=f"jig capture crop {letter}")
        profile = _crop_capture_view(adapter, view, centre, radius * section_scale[0] / section_scale[1], label=f"jig capture section {letter}")
        set_hidden_lines_removed(adapter, view)
        scales.append(_fit_capture_view(adapter, view, CAPTURE_VIEW_REGIONS[index], (section_scale,), crop_profile=profile, label=f"jig capture section {letter}"))
        position_section_caption(adapter, view, CAPTURE_SECTION_CAPTIONS[index - 2], label=f"jig capture {letter}")
        views.append(view)
        crop_profiles.append(profile)
    records = _place_capture_readings(adapter, views)
    _assert_capture_sheet(adapter, views, scales, records, crop_profiles=crop_profiles)
    return tuple(views), tuple(scales), records, tuple(crop_profiles)


def _balloon_cluster(
    adapter: Any,
    view: Any,
    cluster: Cluster,
    items: Sequence[tuple[str, str]],
    bom_name: str,
) -> list[BalloonLanding]:
    """One BOM-linked ring; only the capture sheet repeats the bearing item."""
    _activate_sheet(adapter, cluster.sheet)
    label = f"jig {cluster.sheet.lower()}"
    _link_view_to_bom(view, bom_name, label=label)
    wanted = tuple(item for item in items if item[0] in cluster.stems)
    with _source_configuration_active(view, label=label):
        landings = add_component_bom_balloons(
            adapter,
            view,
            items=wanted,
            anchors=BALLOON_ANCHORS,
            label=f"{label} BOM coverage",
            margin=BALLOON_MARGIN,
        )
        if cluster.sheet == PIVOT_CAPTURE_SHEET:
            bearing_item = next(item for item in wanted if item[0] == spec.BEARING)
            landings += add_component_bom_balloons(
                adapter, view, items=(bearing_item,),
                anchors={spec.BEARING: replace(
                    BALLOON_ANCHORS[spec.BEARING],
                    instance=spec.instance_name(spec.BEARING, 1),
                )},
                label=f"{label} upper bearing item 14", margin=BALLOON_MARGIN,
            )
    _ring_balloons(adapter, view, landings, label=f"{label} balloons")
    if cluster.sheet != PIVOT_CAPTURE_SHEET:
        landings = _relax_cluster_slide(adapter, view, landings, label=f"{label} ring")
    if cluster.sheet == PIVOT_CAPTURE_SHEET:
        _assert_capture_coverage(landings, cluster.stems)
    elif sorted(landing.stem for landing in landings) != sorted(cluster.stems):
        raise RuntimeError(
            f"{label} carries balloons for "
            f"{sorted(landing.stem for landing in landings)!r}, "
            f"expected one for each of {sorted(cluster.stems)!r}"
        )
    return landings


def _place_instruction_notes(adapter: Any) -> None:
    for sheet, layout, label in (
        (STEPS_SHEET, STEPS_LAYOUT, "assembly sequence"),
        (STEPS_CONTINUED_SHEET, STEPS_CONTINUED_LAYOUT, "assembly sequence (cont.)"),
        (CARTRIDGE_SHEET, CARTRIDGE_LAYOUT, "cartridge assembly"),
        (TOP_CAPTURE_SHEET, TOP_CAPTURE_LAYOUT, "actual top capture fit"),
        (CAPTURE_SHEET, CAPTURE_LAYOUT, "operation and installed-machine acceptance"),
    ):
        _add_note_block(adapter, sheet, layout.steps, STEPS_XY, label=label)
        if layout.continued:
            _add_note_block(
                adapter, sheet, layout.continued, STEPS_CONTINUED_XY,
                label=f"{label}, continued",
            )
        if layout.checks:
            _add_note_block(adapter, sheet, layout.checks, layout.checks_xy, label=f"{label} checks")


def _activate_package(adapter: Any, target: Any) -> None:
    title = str(target.GetTitle() or "")
    if not title:
        raise RuntimeError("jig package drawing has no title")
    activation = adapter.swApp.ActivateDoc3(title, False, 2, 0)
    if not activation:
        raise RuntimeError("failed to reactivate jig package")
    activated, errors = activation
    if int(errors) != 0:
        raise RuntimeError(f"failed to reactivate jig package: {errors}")
    if activated is None:
        activated = adapter.swApp.ActiveDoc
    if activated is None or int(adapter.swApp.IsSame(activated, target)) != 1:
        raise RuntimeError("reactivated document is not the jig package")
    adapter.currentModel = _early_bound(activated, "IModelDoc2")


def _append_template_sheet(adapter: Any, target: Any, *, name: str) -> None:
    """Copy a real project-template sheet, closing its donor even on failure."""
    donor_title = ""
    try:
        donor, donor_sheet = new_project_drawing(
            adapter, layout=SHEET_LAYOUTS[name], scale=SHEET_SCALES[name]
        )
        donor = _early_bound(donor, "IModelDoc2")
        donor_sheet = _early_bound(donor_sheet, "ISheet")
        donor_title = str(donor.GetTitle() or "")
        donor_name = str(donor_sheet.GetName() or "")
        if not donor_title or not donor_name:
            raise RuntimeError(f"{name}: donor drawing is incomplete")
        donor.ClearSelection2(True)
        if not donor.Extension.SelectByID2(
            donor_name, "SHEET", 0.0, 0.0, 0.0, False, 0, null_callout(), 0
        ):
            raise RuntimeError(f"{name}: failed to select donor sheet")
        donor.EditCopy()
        _activate_package(adapter, target)
        ddoc = _early_bound(target, "IDrawingDoc")
        before = tuple(ddoc.GetSheetNames() or ())
        returned = bool(ddoc.PasteSheet(2, 2))  # append; preserve view names
        after = tuple(ddoc.GetSheetNames() or ())
        added = tuple(sheet for sheet in after if sheet not in before)
        if len(after) != len(before) + 1 or len(added) != 1:
            raise RuntimeError(
                f"{name}: sheet paste failed ({returned=}, {before=}, {after=})"
            )
        if not returned:
            _telemetry.warn(
                f"{name}: PasteSheet returned false but created {added[0]!r}"
            )
        if not ddoc.ActivateSheet(added[0]):
            raise RuntimeError(f"{name}: failed to activate pasted sheet")
        sheet = _early_bound(ddoc.GetCurrentSheet(), "ISheet")
        sheet.SetName(name)
        if str(sheet.GetName() or "") != name:
            raise RuntimeError(f"{name}: failed to rename pasted sheet")
    finally:
        primary_error = sys.exception()
        if donor_title:
            try:
                adapter.swApp.CloseDoc(donor_title)
                _activate_package(adapter, target)
            except Exception as exc:
                if primary_error is None:
                    raise
                _telemetry.warn(f"{name}: donor cleanup failed: {exc}")


def _create_package_sheets(adapter: Any) -> None:
    """The primary sheet, then native template copies for the others."""
    target, initial = new_project_drawing(
        adapter,
        layout=SHEET_LAYOUTS[SHEET_NAMES[0]],
        scale=SHEET_SCALES[SHEET_NAMES[0]],
    )
    target = _early_bound(target, "IModelDoc2")
    initial = _early_bound(initial, "ISheet")
    initial.SetName(SHEET_NAMES[0])
    if str(initial.GetName() or "") != SHEET_NAMES[0]:
        raise RuntimeError("failed to name the jig's primary sheet")
    for name in SHEET_NAMES[1:]:
        _append_template_sheet(adapter, target, name=name)
    actual = tuple(_early_bound(target, "IDrawingDoc").GetSheetNames() or ())
    if actual != SHEET_NAMES:
        raise RuntimeError(f"jig sheet order mismatch: {actual!r}")


def _place_package(
    adapter: Any,
) -> tuple[dict[str, tuple[float, float]], tuple[Callable[[], None], ...]]:
    """Every sheet; returns the sheets' fitted scales and the checks that
    prove the BOM, every balloon and the CL tip reference after the last rebuild.

    Every view is configured, then exploded or collapsed, before the BOM is
    inserted; after it only BOM links and balloons
    (draw_dt_drive_train_assembly's order)."""
    _create_package_sheets(adapter)
    for sheet_name in SHEET_NAMES:
        sheet = _activate_sheet(adapter, sheet_name)
        scale = SHEET_SCALES[sheet_name]
        if not sheet.SetScale(float(scale[0]), float(scale[1]), False, False):
            raise RuntimeError(f"failed to set jig sheet scale: {sheet_name}")
    cl_tip_settled = _place_assembled_sheet(adapter)
    reference = _place_reference_view(adapter)
    _place_finished_view(adapter)
    notes_scales = _place_notes_reference_views(adapter)
    capture_cluster = next(
        cluster for cluster in CLUSTERS if cluster.sheet == PIVOT_CAPTURE_SHEET
    )
    capture_views, capture_scales, capture_records, capture_profiles = _place_capture_sheet(adapter, capture_cluster)
    placed = [
        (cluster, capture_views[0], capture_scales[0]) if cluster is capture_cluster
        else (cluster, *_place_cluster_view(adapter, cluster))
        for cluster in CLUSTERS
    ]
    _activate_sheet(adapter, BOM_SHEET)
    table = insert_bom_table(
        adapter,
        reference,
        anchor_xy=BOM_ANCHOR,
        expected_components=BOM_COMPONENTS,
        descriptions=BOM_DESCRIPTIONS,
        component_identities=BOM_COMPONENT_IDENTITIES,
        configuration_grouping="same-name",
        part_number_property="Number",
        label="jig",
    )
    bom_configuration = str(reference.ReferencedConfiguration)
    items = _validate_bom(adapter, table, configuration=bom_configuration)
    bom_snapshot = validate_bom_number_property(
        table,
        configuration=bom_configuration,
        label="jig",
        expected_rows=1 + len(BOM_COMPONENTS),
        occurrence_quantities=True,
    )
    kit_note_settled = _place_kit_bom_note(adapter, table, reference)
    bom_name = _bom_feature_name(table)
    landings: list[BalloonLanding] = []
    for cluster, view, scale in placed:
        landings += _balloon_cluster(adapter, view, cluster, items, bom_name)
        _add_note_block(
            adapter,
            cluster.sheet,
            exploded_caption(cluster, scale),
            EXPLODED_CAPTION_XY,
            label=f"{cluster.sheet.lower()} caption",
        )
    if sorted(landing.stem for landing in landings) != sorted((*BOM_COMPONENTS, spec.BEARING)):
        raise RuntimeError(
            "jig package requires one balloon per BOM row, except the two "
            "distinct item-14 bearings on the capture sheet"
        )
    capture_landings = [
        landing for landing in landings if landing.stem in capture_cluster.stems
    ]
    _assert_capture_sheet(adapter, capture_views, capture_scales, capture_records, capture_landings, crop_profiles=capture_profiles)
    _place_instruction_notes(adapter)
    # The fitted reference can select 1:25 or 1:30. Author paper-only sketch
    # geometry at that final native sheet scale, not the initial 1:20; the
    # finalizer later re-pins this same ratio without rescaling the schematic.
    sheet = _activate_sheet(adapter, CARTRIDGE_SHEET)
    before = tuple(float(value) for value in (sheet.GetProperties2() or ()))
    fitted = notes_scales[CARTRIDGE_SHEET]
    if not sheet.SetScale(float(fitted[0]), float(fitted[1]), False, False):
        raise RuntimeError("failed to set the C2A sheet's fitted reference scale")
    properties = tuple(float(value) for value in (sheet.GetProperties2() or ()))
    if len(properties) < 4 or tuple(properties[2:4]) != fitted:
        raise RuntimeError("C2A sheet did not retain its fitted reference scale")
    _telemetry.info(
        f"C2A fitted sheet scale: before={before!r}, after={properties!r}, "
        f"finalizer_target={fitted!r}"
    )
    rebuild_drawing(adapter, label="C2A fitted sheet scale")
    inspection_settled = _place_pin_tip_inspection(adapter)
    scales = package_sheet_scales(
        {cluster.sheet: scale for cluster, _view, scale in placed}
    )
    scales.update(notes_scales)

    def bom_settled() -> None:
        retained = validate_bom_number_property(
            table,
            configuration=bom_configuration,
            label="jig",
            expected_rows=1 + len(BOM_COMPONENTS),
            occurrence_quantities=True,
        )
        if retained != bom_snapshot:
            raise RuntimeError(
                "jig native BOM membership/quantities changed after placement"
            )

    return scales, (
        bom_settled,
        lambda: assert_balloon_landings(adapter, landings),
        cl_tip_settled,
        kit_note_settled,
        inspection_settled,
        lambda: _assert_capture_sheet(
            adapter, capture_views, capture_scales, capture_records, capture_landings,
            crop_profiles=capture_profiles,
        ),
    )


@_telemetry.traced("drawing.ch_rocker_arm_tl_oblique_jig_assembly")
async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source assembly is missing: {SOURCE}")

    check("open jig drawing source", await adapter.open_model(str(SOURCE)))
    source_model = _early_bound(adapter.currentModel, "IModelDoc2")
    properties = read_required_properties(
        source_model,
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
            "Revision",
            "Material Specification",
            "Finish",
            "Quantity",
        ),
    )
    if properties["Number"] != spec.DRAWING_NUMBER:
        raise RuntimeError(
            f"jig source Number {properties['Number']!r} != {spec.DRAWING_NUMBER!r}"
        )
    _validate_source(source_model)

    sheet_scales, settled = _place_package(adapter)
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        layout=SPEC.layout,
        pdf_title="Rocker Oblique Trammel Jig Assembly Drawing Package",
        scale=SHEET_SCALE,
        expected_sheet_names=SHEET_NAMES,
        sheet_layouts=SHEET_LAYOUTS,
        sheet_scales=sheet_scales,
        settled_checks=settled,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[ARTIFACT_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
