r"""Create the six-sheet paper-drive assembly drawing (MHA-PD-000).

Sheet 1 keeps the Front/Right/Isometric views of the whole paper drive and
balloons the chain and the spare sprocket on the isometric. Sheet 2 carries
a ballooned isometric of the transgear (the hanger, the latch, the disc cluster
and the knob stack) and a ballooned right view of its hidden parts. Sheet 3
balloons the bar, its clamps and the platen group on PAPER_DRIVE_EXPLODED and
prints their steps. Sheet 4 prints the transgear's assembly steps; sheet 5
prints the chain fit-up (CONTRACT-paper-drive.md §13.2). Sheet 6 carries the
complete native BOM, split horizontally into two pieces at measured row
heights, and an assembly reference. The BOM identifies the current inch
reducer, finite stock-form integral pinions and rack/backer; sheet 1 gives the
selected chain ratio's reference paper travel. Gear cutting data stays on the
gear sheets. The chain fit-up includes the actual loaded collar/disc overlap
inspection with the trial platen removed and the operating latch pose held;
nominal model clearance does not replace that shop inspection. Engaged feed
uses the source-qualified inward-rounded cut-end operating window, not
unbounded platen travel or nominal first-gap phasing. Build-time formatting
reads the verified frozen isolated-feed-datum report, then guards the complete
located paper sweep; imports require no packet and never run a proof. This
conditional MODEL scope is not whole-unit SHAKE/I+B or shop-hardware admission.
Every step is numbered by ``pd_paper_drive_assembly_steps``; values retain
their owning specs and actual critical gear/seat/load inspections remain required.
"""

from __future__ import annotations

import argparse
import math
import sys
import textwrap
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

import _chain as chain
import _config
import _gear_quality as quality
import _telemetry
import pd_latch_hook_geometry as hook_geometry
import pd_paper_drive_assembly_steps as steps
import pd_paper_drive_explode_spec as explode
import pd_platen_guide_spec as platen_guide
import pd_platen_spec as platen
import pd_rack_pinion_spec as disc
import pd_transgear_arm_geometry as arm_geometry
import vn_transgear_arm_plate_screw_spec as plate_screw
import vn_transgear_arm_plate_locating_pin_spec as plate_locating_pin
import transgear_cluster_fit as cluster_fit
import pd_transgear_disc_hub_geometry as hub_geometry
import pd_transgear_disc_hub_spec as hub
import vn_transgear_disc_screw_spec as disc_screw
import pd_transgear_drive_collar_spec as collar
import transgear_hanger_joints as joints
import vn_transgear_knob_cup_pin_spec as cup_pin
import pd_transgear_knob_cup_spec as knob_cup
import vn_transgear_knob_drive_pin_spec as drive_pin
import pd_transgear_feed_pinion_spec as feed_pinion
import pd_transgear_knob_shaft_spec as knob_shaft
import vn_transgear_pivot_screw_spec as pivot_screw
import vn_transgear_pivot_spring_spec as spring
import pd_transgear_removable_spec as sprocket
from paper_drive_rack_travel import RackOperatingDomain, OPERATING_DIRECTION_TEXT
from _check import check
from _com import _com_invoke, _early_bound
from _session import run_build
from _pd_paper_drive_explode import exploded_view_name
from _drawing_common import (
    SIMPLIFIED_VIEW_CONFIGURATION,
    isolate_drawing_view_components,
    set_view_exploded_state,
    BalloonAnchor,
    BalloonLanding,
    DrawingOutputs,
    ViewRole,
    _SW_SHADED_EDGES,
    _VIEW_ENTITY_EDGE,
    _AnchorChoice,
    _anchor_model_points,
    _create_component_bom_balloon,
    _shown_instances,
    _spread_balloons,
    _view_component_leaves,
    _view_explode_offsets,
    add_component_bom_balloons,
    apply_view_configuration,
    assert_balloon_landings,
    assert_full_detail_view,
    create_blank_drawing_sheets,
    finalize_drawing,
    insert_bom_table,
    model_points_in_view,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    rendered_balloon_circle,
    set_high_quality_shaded_with_edges,
    view_configuration,
)
from _drawing_layout_check import LeaderSegment, find_leader_leader_crossings
from _drawing_registry import DRAWINGS_BY_NAME, DRAWING_TEMPLATES, DrawingLayout
from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    place_view,
    raw_visible_entities,
    view_name,
)


SPEC = DRAWINGS_BY_NAME["pd_paper_drive_assembly"]
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

SHEET_NAMES = (
    "ASSEMBLED VIEWS",
    "TRANSGEAR VIEWS",
    "PLATEN AND SUPPORT",
    "ASSEMBLY AND FIT-UP",
    "CHAIN FIT-UP",
    "BILL OF MATERIALS",
)
if SPEC.layout is not DrawingLayout.LANDSCAPE:
    raise AssertionError("the paper-drive sheet coordinates are landscape")
SHEET_LAYOUTS = {name: DrawingLayout.LANDSCAPE for name in SHEET_NAMES}

# --- sheet 1: the whole paper drive, front, right and isometric -------------
# Farm run 20261001T142942518Z placed the isometric at 1:3 and read its
# outline 187.7 mm tall (ring 221.7 > the 198.0 room); its width passed. The
# outline is the model's projected box, about 1.4x the ink the 1:5 render
# showed, and SolidWorks pads it by a fixed sheet-space margin, so a rescale
# is read back, never predicted (step_down_to_fit). At 1:4 the content alone
# is 140.8 tall, its ring 174.8 inside the room. The front and right views
# (1:5 ink 94 x 59 and 14 x 58 mm) grow to 118 x 74 and 18 x 73 above the
# free lower-left field, the isometric right of them over the title block.
ASSEMBLED_SCALE = (1.0, 4.0)
FRONT_CENTER = (0.095, 0.190)
RIGHT_CENTER = (0.205, 0.190)
ISO_CENTER = (0.330, 0.170)
# The isometric steps down to 1:5 if its native ring overflows at 1:4. It is
# the full-detail view, which references Default at every scale.
ISO_SCALE_LADDER = (ASSEMBLED_SCALE, (1.0, 5.0))
# The isometric's balloon ring: left of it the right view, below it the
# title block (top 0.066), the sheet's drawing border round the rest.
ISO_RING_LIMITS = (0.235, 0.069, 0.418, 0.267)
ASSEMBLED_CAPTION_XY = (0.018, 0.120)

# --- sheet 6: full qualified Numbers and two native BOM pieces ---------------
# f353's 22 mm Number column wrapped the identities: the native audit measured
# the unsplit table 437.2384 mm high, not the requested rows' nominal height.
# Use the drive-train's proven column widths without changing table text size;
# choose the split only after text, widths and row heights have rebuilt.
BOM_COLUMN_WIDTHS = {
    "item": 0.012,
    "part": 0.048,
    "description": 0.118,
    "quantity": 0.012,
}
BOM_DESCRIPTION_MAX_CHARS = 41
BOM_ROW_HEIGHT = 0.0055
BOM_ANCHOR = (0.018, 0.262)
BOM_SECOND_ANCHOR = (
    BOM_ANCHOR[0] + sum(BOM_COLUMN_WIDTHS.values()) + 0.008,
    BOM_ANCHOR[1],
)
BOM_REFERENCE_SCALE = (1.0, 10.0)
BOM_REFERENCE_CENTER = (0.060, 0.065)
BOM_REFERENCE_LIMITS = (0.018, 0.028, 0.095, 0.104)
BOM_REFERENCE_CAPTION_XY = (0.100, 0.088)
BOM_REFERENCE_CAPTION = (
    "REFERENCE 1:10\nBALLOONS: SHEETS 1-3\nASSEMBLY: SHEETS 3-5"
)
# The ASME B landscape sheet's inner border, bottom edge, and the clearance
# the BOM keeps above it.
SHEET_INNER_BORDER_BOTTOM = 0.0127
BOM_BORDER_CLEARANCE = 0.003
# The transgear alone at 2:3, right of the inner view's ring and above the
# title block. The v40 sheet 2 (594749aec's layout) printed its outline at
# x 285.3 to 396.6, y 111.2 to 244.8 mm: a ring top of 261.8 in the 262.0
# limit. The one-piece MHA-PD-014 hook's ear stands at machine x 77.6, 17.6
# further +X than the bracket's flap. The isometric looks along (-1, +1, -1),
# so sheet up is 0.408 x and sheet right -0.707 x, and the outline grew to
# x 278.5 and y 248.8 (farm run of 9055bc155: ring top 265.8). The view is
# 137.6 mm tall, so its ring of 171.6 fits the field's 172.0 only when it is
# centred: transgear_view_shift moves it down before the inner view is
# fitted beside it.
TRANSGEAR_VIEW_SCALE = (2.0, 3.0)
TRANSGEAR_VIEW_CENTER = (0.346, 0.170)
BALLOON_MARGIN = 0.012
TRANSGEAR_CAPTION_XY = (0.222, 0.082)
# The parts the isometric hides, seen from the machine's right (camera at -X:
# sheet x is machine +Z, sheet y is +Y) with every other part hidden in that
# view only. The largest ladder scale whose ring fits beside the isometric's
# (inner_view_scale): the same run read the view 57.3 mm wide at 2:3, a 91.3
# mm ring in the 76.3 mm left of the isometric's ring at x 355; the v40 sheet
# 2 printed it at 1:3, 34.5 mm wide. Every ladder scale is
# at most 1:2, so the view references the simplified configuration whichever
# it takes (apply_view_configuration), and no rescale switches it.
INNER_VIEW_ORIENTATION = "*Right"
INNER_SCALE_LADDER = ((1.0, 2.0), (1.0, 3.0))
if any(
    view_configuration(scale, _SW_SHADED_EDGES) != SIMPLIFIED_VIEW_CONFIGURATION
    for scale in INNER_SCALE_LADDER
):
    raise AssertionError(
        "a rescale on the inner-view ladder would switch configuration"
    )
# Where the inner view lands before inner_view_shift centres it.
INNER_VIEW_START = (0.230, 0.190)
# Sheet 2 retains the established model fields when the BOM moves to sheet 6.
# Its balloon circles still clear the drawing border and caption fields.
SHEET_TWO_RING_LIMITS = (0.185, 0.090, 0.415, 0.262)
BALLOON_RING_REACH = BALLOON_MARGIN + 0.005
SHEET_TWO_RING_GAP = 0.004
INNER_CAPTION_GAP = 0.002

# --- sheet 3: the platen-and-support steps, the ballooned exploded view -----
# The builder's PAPER_DRIVE_EXPLODED shows only these families here. No run
# has read its outline yet, and sheet 1's showed the outline (the projected
# box) well past the ink, so the view takes the largest ladder scale whose
# ring fits right of the steps and over the title block (step_down_to_fit). Every
# ladder scale is 1:2 or smaller, so a rescale keeps the simplified
# configuration the explode is shown in.
EXPLODED_SCALE_LADDER = ((1.0, 3.0), (1.0, 4.0), (1.0, 5.0))
if any(
    view_configuration(scale, _SW_SHADED_EDGES) != SIMPLIFIED_VIEW_CONFIGURATION
    for scale in EXPLODED_SCALE_LADDER
):
    raise AssertionError(
        "a rescale on the exploded-view ladder would switch configuration"
    )
EXPLODED_SCALE = EXPLODED_SCALE_LADDER[0]
EXPLODED_CENTER = (0.318, 0.168)
PLATEN_NOTE_XY = (0.018, 0.262)
# The steps' right limit, left of the exploded view's balloon ring.
PLATEN_NOTE_RIGHT = 0.222
EXPLODED_RING_LIMITS = (PLATEN_NOTE_RIGHT + 0.003, 0.069, 0.418, 0.267)

# --- sheets 4 and 5: ordered steps in two columns, same note-field budgets ----
FITUP_SCALE = (1.0, 10.0)
FITUP_REFERENCE_CENTER = (0.100, 0.045)
FITUP_LINE_WIDTH = 68  # characters; default-format note text
# Each column's top-left corner, then its right limit and lowest y: the left
# column stops above sheet 4's reference view; the right column stops above
# the title block (top 0.066). Sheet 5 retains the same field clearances.
FITUP_NOTE_XY = ((0.018, 0.262), (0.215, 0.262))
FITUP_NOTE_LIMITS = ((0.210, 0.075), (0.418, 0.072))
# Sheet 4 splits after the disc's match-centre/transfer inspection so the
# knob, mesh and hook operations stay together. Sheet 5 begins with the
# loaded full-stroke inspection and splits after the fitted collar rear face.
FITUP_FIRST_COLUMN_KEY = "latch-pin-pressed"
FITUP_SECOND_COLUMN_KEY = "disc-screws-cut"
FITUP_CHAIN_KEY = "loaded-rack-geometry-checked"
CHAIN_SECOND_COLUMN_KEY = "collar-shoulder-seated"

SHEET_SCALES = {
    SHEET_NAMES[0]: ASSEMBLED_SCALE,
    SHEET_NAMES[1]: TRANSGEAR_VIEW_SCALE,
    SHEET_NAMES[2]: EXPLODED_SCALE,
    SHEET_NAMES[3]: FITUP_SCALE,
    SHEET_NAMES[4]: FITUP_SCALE,
    SHEET_NAMES[5]: BOM_REFERENCE_SCALE,
}

# --- BOM identities ------------------------------------------------------------
# Literal stems, so the config-dependency analysis reads exactly these rows.
BOM_PART_NUMBERS = {
    "pd-support-bar": _config.parts("pd-support-bar")["number"],
    "sh-column-clamp-front": _config.parts("sh-column-clamp-front")["number"],
    "sh-column-clamp-back": _config.parts("sh-column-clamp-back")["number"],
    "vn-clamp-screw": _config.parts("vn-clamp-screw")["number"],
    "pd-platen": _config.parts("pd-platen")["number"],
    "pd-platen-rack": _config.parts("pd-platen-rack")["number"],
    "pd-platen-guide": _config.parts("pd-platen-guide")["number"],
    "pd-guide-lock": _config.parts("pd-guide-lock")["number"],
    "pd-platen-clip": _config.parts("pd-platen-clip")["number"],
    "pd-platen-paper": _config.parts("pd-platen-paper")["number"],
    "vn-fillister-screw": _config.parts("vn-fillister-screw")["number"],
    "vn-guide-lock-screw": _config.parts("vn-guide-lock-screw")["number"],
    "vn-chain-inner-link": _config.parts("vn-chain-inner-link")["number"],
    "vn-chain-outer-link": _config.parts("vn-chain-outer-link")["number"],
    "pd-transgear-removable": _config.parts("pd-transgear-removable")["number"],
    "pd-transgear-arm": _config.parts("pd-transgear-arm")["number"],
    "pd-transgear-arm-plate": _config.parts("pd-transgear-arm-plate")["number"],
    "vn-transgear-arm-plate-screw": _config.parts("vn-transgear-arm-plate-screw")["number"],
    "vn-transgear-arm-plate-locating-pin": _config.parts(
        "vn-transgear-arm-plate-locating-pin"
    )["number"],
    "pd-transgear-pivot-spacer": _config.parts("pd-transgear-pivot-spacer")["number"],
    "vn-transgear-pivot-screw": _config.parts("vn-transgear-pivot-screw")["number"],
    "vn-transgear-pivot-spring": _config.parts("vn-transgear-pivot-spring")["number"],
    "vn-transgear-latch-pin": _config.parts("vn-transgear-latch-pin")["number"],
    "vn-latch-hook-bracket-screw": _config.parts("vn-latch-hook-bracket-screw")["number"],
    "pd-latch-hook": _config.parts("pd-latch-hook")["number"],
    "pd-transgear-pin": _config.parts("pd-transgear-pin")["number"],
    "pd-transgear-rear-bushing": _config.parts("pd-transgear-rear-bushing")["number"],
    "pd-transgear-feed-pinion": _config.parts("pd-transgear-feed-pinion")["number"],
    "pd-transgear-disc-hub": _config.parts("pd-transgear-disc-hub")["number"],
    "pd-transgear-front-bushing": _config.parts("pd-transgear-front-bushing")["number"],
    "vn-transgear-retaining-ring": _config.parts("vn-transgear-retaining-ring")["number"],
    "pd-rack-pinion": _config.parts("pd-rack-pinion")["number"],
    "vn-transgear-disc-screw": _config.parts("vn-transgear-disc-screw")["number"],
    "pd-transgear-knob-shaft": _config.parts("pd-transgear-knob-shaft")["number"],
    "pd-transgear-drive-collar": _config.parts("pd-transgear-drive-collar")["number"],
    "vn-transgear-knob-drive-pin": _config.parts("vn-transgear-knob-drive-pin")["number"],
    "pd-transgear-thumbnut": _config.parts("pd-transgear-thumbnut")["number"],
    "pd-transgear-knob-thrust-ring": _config.parts("pd-transgear-knob-thrust-ring")["number"],
    "pd-transgear-knob-cup": _config.parts("pd-transgear-knob-cup")["number"],
    "vn-transgear-knob-cup-pin": _config.parts("vn-transgear-knob-cup-pin")["number"],
}
# A purchased part's registry SKU, printed in its description.
_SKU = {
    "vn-clamp-screw": _config.parts("vn-clamp-screw")["supplier_skus"][0],
    "vn-fillister-screw": _config.parts("vn-fillister-screw")["supplier_skus"][0],
    "vn-guide-lock-screw": _config.parts("vn-guide-lock-screw")["supplier_skus"][0],
    "vn-transgear-arm-plate-screw": _config.parts("vn-transgear-arm-plate-screw")[
        "supplier_skus"
    ][0],
    "vn-transgear-arm-plate-locating-pin": _config.parts(
        "vn-transgear-arm-plate-locating-pin"
    )["supplier_skus"][0],
    "vn-transgear-pivot-screw": _config.parts("vn-transgear-pivot-screw")["supplier_skus"][0],
    "vn-transgear-pivot-spring": _config.parts("vn-transgear-pivot-spring")["supplier_skus"][
        0
    ],
    "vn-transgear-latch-pin": _config.parts("vn-transgear-latch-pin")["supplier_skus"][0],
    "vn-latch-hook-bracket-screw": _config.parts("vn-latch-hook-bracket-screw")[
        "supplier_skus"
    ][0],
    "vn-transgear-disc-screw": _config.parts("vn-transgear-disc-screw")["supplier_skus"][0],
    "vn-transgear-retaining-ring": _config.parts("vn-transgear-retaining-ring")[
        "supplier_skus"
    ][0],
    "vn-transgear-knob-drive-pin": _config.parts("vn-transgear-knob-drive-pin")[
        "supplier_skus"
    ][0],
    "vn-transgear-knob-cup-pin": _config.parts("vn-transgear-knob-cup-pin")["supplier_skus"][
        0
    ],
}
# The description column is drawing wording; a purchased part names its SKU.
BOM_DESCRIPTIONS = {
    "pd-support-bar": "PAPER-DRIVE SUPPORT BAR",
    "sh-column-clamp-front": "COLUMN CLAMP, FRONT",
    "sh-column-clamp-back": "COLUMN CLAMP, BACK",
    "vn-clamp-screw": f"FILLISTER SCREW, MCMASTER {_SKU['vn-clamp-screw']}",
    "pd-platen": "PLATEN",
    "pd-platen-rack": (
        f"PLATEN RACK + BACKER, {feed_pinion.DIAMETRAL_PITCH:g}DP "
        f"PA{feed_pinion.PRESSURE_ANGLE_DEG:g}"
    ),
    "pd-platen-guide": "PLATEN GUIDE",
    "pd-guide-lock": "PLATEN GUIDE LOCK",
    "pd-platen-clip": "PLATEN PAPER CLIP",
    "pd-platen-paper": "PLATEN PAPER",
    "vn-fillister-screw": f"BRASS FILLISTER SCREW, MCMASTER {_SKU['vn-fillister-screw']}",
    "vn-guide-lock-screw": f"BUTTON HEAD SCREW, MCMASTER {_SKU['vn-guide-lock-screw']}",
    "vn-chain-inner-link": "ANSI #25 CHAIN INNER LINK",
    "vn-chain-outer-link": "ANSI #25 CHAIN OUTER LINK",
    # Grouped: its configurations' BOM description wins over a written cell,
    # so the row prints the registry description the builder stamps.
    "pd-transgear-removable": str(_config.parts("pd-transgear-removable")["description"]),
    "pd-transgear-arm": "TRANSGEAR ARM",
    "pd-transgear-arm-plate": "TRANSGEAR ARM PLATE",
    "vn-transgear-arm-plate-screw": (
        f"{plate_screw.THREAD} OVAL HEAD SCREW, MCMASTER "
        f"{_SKU['vn-transgear-arm-plate-screw']}"
    ),
    "vn-transgear-arm-plate-locating-pin": (
        f"PLATE LOCATING DOWEL, MCMASTER {_SKU['vn-transgear-arm-plate-locating-pin']}"
    ),
    "pd-transgear-pivot-spacer": "TRANSGEAR PIVOT SPACER",
    "vn-transgear-pivot-screw": (
        f"{pivot_screw.THREAD} SHOULDER SCREW, MCMASTER {_SKU['vn-transgear-pivot-screw']}"
    ),
    "vn-transgear-pivot-spring": (
        f"CURVED DISC SPRING, MCMASTER {_SKU['vn-transgear-pivot-spring']}"
    ),
    "vn-transgear-latch-pin": f"DOWEL PIN, MCMASTER {_SKU['vn-transgear-latch-pin']}",
    "vn-latch-hook-bracket-screw": (
        f"FILLISTER SCREW, MCMASTER {_SKU['vn-latch-hook-bracket-screw']}"
    ),
    "pd-latch-hook": "LATCH HOOK",
    "pd-transgear-pin": "TRANSGEAR PIN",
    "pd-transgear-rear-bushing": "TRANSGEAR REAR BUSHING",
    "pd-transgear-feed-pinion": (
        f"FEED SLEEVE, STOCK {feed_pinion.TEETH}T "
        f"{feed_pinion.DIAMETRAL_PITCH:g}DP PA{feed_pinion.PRESSURE_ANGLE_DEG:g}"
    ),
    "pd-transgear-disc-hub": "TRANSGEAR DISC HUB",
    "pd-transgear-front-bushing": "TRANSGEAR FRONT BUSHING",
    "vn-transgear-retaining-ring": (
        f"RETAINING RING, MCMASTER {_SKU['vn-transgear-retaining-ring']}"
    ),
    "pd-rack-pinion": (
        f"REDUCER DISC, STOCK {disc.TEETH}T {disc.DIAMETRAL_PITCH:g}DP "
        f"PA{disc.PRESSURE_ANGLE_DEG:g}"
    ),
    "vn-transgear-disc-screw": (
        f"{disc_screw.THREAD} FILLISTER SCREW, MCMASTER {_SKU['vn-transgear-disc-screw']}"
    ),
    "pd-transgear-knob-shaft": (
        f"KNOB SHAFT, STOCK {knob_shaft.TEETH}T "
        f"{knob_shaft.DIAMETRAL_PITCH:g}DP PA{knob_shaft.PRESSURE_ANGLE_DEG:g}"
    ),
    "pd-transgear-drive-collar": "KNOB DRIVE COLLAR",
    "vn-transgear-knob-drive-pin": (
        f"WHEEL DRIVE DOWEL, MCMASTER {_SKU['vn-transgear-knob-drive-pin']}"
    ),
    "pd-transgear-thumbnut": "TRANSGEAR THUMBNUT",
    "pd-transgear-knob-thrust-ring": "KNOB THRUST RING",
    "pd-transgear-knob-cup": "KNOB CUP",
    "vn-transgear-knob-cup-pin": f"SPRING PIN, MCMASTER {_SKU['vn-transgear-knob-cup-pin']}",
}
if set(BOM_DESCRIPTIONS) != set(BOM_PART_NUMBERS):
    raise AssertionError("paper-drive BOM description coverage is incomplete")
# The registry's grouped-row description is the builder's to stamp and may
# wrap; every written description keeps to one line.
GROUPED_DESCRIPTION_STEMS = frozenset({"pd-transgear-removable"})
_LONG = sorted(
    stem
    for stem, text in BOM_DESCRIPTIONS.items()
    if len(text) > BOM_DESCRIPTION_MAX_CHARS and stem not in GROUPED_DESCRIPTION_STEMS
)
if _LONG:
    raise AssertionError(f"paper-drive BOM descriptions wrap: {_LONG}")
BOM_NORMALIZED_ALIASES = {
    number.casefold(): stem for stem, number in BOM_PART_NUMBERS.items()
}

# The transgear instances the contract inserts (instance ``<stem>-<n>``), each
# count read from the geometry that holds its holes: sheet 2 shows and
# balloons exactly these. The mounted knob sprocket is instance 1;
# the crank wheel and spare T18 stay on sheet 1.
TRANSGEAR_QUANTITIES = {
    "pd-transgear-arm": 1,
    "pd-transgear-arm-plate": 1,
    "vn-transgear-arm-plate-screw": len(arm_geometry.PLATE_TAP_STATIONS),
    "vn-transgear-arm-plate-locating-pin": plate_locating_pin.ASSEMBLY_QUANTITY,
    "pd-transgear-pivot-spacer": 1,
    "vn-transgear-pivot-screw": 1,
    "vn-transgear-pivot-spring": spring.COUNT,
    "vn-transgear-latch-pin": 1,
    "vn-latch-hook-bracket-screw": len(hook_geometry.SCREW_X),
    "pd-latch-hook": 1,
    "pd-transgear-pin": 1,
    "pd-transgear-rear-bushing": 1,
    "pd-transgear-feed-pinion": 1,
    "pd-transgear-disc-hub": 1,
    "pd-transgear-front-bushing": 1,
    "vn-transgear-retaining-ring": 1,
    "pd-rack-pinion": 1,
    "vn-transgear-disc-screw": hub_geometry.SCREW_COUNT,
    "pd-transgear-knob-shaft": 1,
    "pd-transgear-drive-collar": 1,
    "vn-transgear-knob-drive-pin": len(sprocket.PIN_HOLE_ANGLES_DEG),
    "pd-transgear-removable": 3,  # two mounted wheels plus the loose T18 spare
    "pd-transgear-thumbnut": 1,
    "pd-transgear-knob-thrust-ring": 1,
    "pd-transgear-knob-cup": 1,
    "vn-transgear-knob-cup-pin": 1,
}
# One assembled inner or outer link spans one pitch; the connecting link
# replaces an outer link, rather than adding a pitch to the closed loop.
CHAIN_QUANTITIES = {
    "vn-chain-inner-link": chain.LINK_COUNT // 2,
    "vn-chain-outer-link": chain.LINK_COUNT // 2,
}
if not set(TRANSGEAR_QUANTITIES) <= set(BOM_PART_NUMBERS):
    raise AssertionError("every transgear family is a BOM row")
TRANSGEAR_INSTANCES = frozenset(
    f"{stem}-{index}"
    for stem, count in TRANSGEAR_QUANTITIES.items()
    for index in range(1, (1 if stem == "pd-transgear-removable" else count) + 1)
)
# The drive collar's balloon (on the inner view, INNER_STEMS) attaches by
# entity to its rear-face rim, never by a sheet hit test. From the right
# (camera at -X, sheet x along +Z) the collar's rims are circles seen
# edge-on: lines at sheet x 216.52 (front) and 218.52 (rear), 1:2, y 171.82
# to 180.57. Hit tests on those lines are unreliable. On farm run
# 20261002T160324403Z (swmaker000005) walk tries 1 to 7 at y +/-4.601 and
# +/-8.174 missed both rims; try 8 hit (3.122, 8.174, 0), which try 3 had
# missed, and its leader landed at the rim's top end, 0.288 mm up. A frozen
# point then selected no edge on the rear rim's middle (7.443, -4.601, 4.0),
# run 20261002T164049933Z (swmaker000005), nor 0.05 mm from its bottom end
# (-1.319, -8.65, 4.0), run 20261002T171234232Z (swmaker00000a). So the rim
# is named by its model geometry, as the disc hub's perpendicularity frames
# name theirs: the circle on the collar's axis at z LENGTH, r OD/2, from the
# edges the view lists for the collar. The rear slot (along local X) splits
# it into a +Y and a -Y arc; the -Y arc holds the landing. That arc's
# assembly-aligned bottom point projects onto the line's bottom end, and the leader lands
# COLLAR_RIM_END_INSET up from it: a leader re-solved to the line's nearer
# end, as run 20261002T160324403Z's was, stays 0.05 mm away at 1:2. The
# landing is 0.23 mm below the drive-pin hole's edge on the same line and
# 2.0 mm from the lower drive pin, which stands proud of the front face only.
# The knob shaft's 12T is 2.2 mm away. The feed sleeve is all above the axis.
COLLAR_STEM = "pd-transgear-drive-collar"
COLLAR_INSTANCE = f"{COLLAR_STEM}-1"
COLLAR_RIM_RADIUS = collar.OD / 2.0
COLLAR_RIM_Z = collar.LENGTH
COLLAR_RIM_END_INSET = 0.1
COLLAR_LANDING_Y = COLLAR_RIM_END_INSET - COLLAR_RIM_RADIUS
# The assembly spins the collar with the knob front stack by
# FRONT_STACK_PHASE_DEG (-3) about its axis. The inner view looks along the
# assembly's X, so the rim's line ends and its edge-on witnesses are the
# assembly-aligned +/-Y and +/-X points, and the landing is placed in that
# frame. Run 10 projected the collar-LOCAL +X point instead: r sin 3 deg =
# 0.458 mm off the line's midpoint, 0.153 mm on the 1:3 sheet.
COLLAR_SPIN_RAD = math.radians(knob_shaft.FRONT_STACK_PHASE_DEG)


def _collar_local(x_mm: float, y_mm: float) -> tuple[float, float, float]:
    """An assembly-aligned point on the rear-rim plane, in collar-local mm."""
    c, s = math.cos(COLLAR_SPIN_RAD), math.sin(COLLAR_SPIN_RAD)
    return (x_mm * c + y_mm * s, -x_mm * s + y_mm * c, COLLAR_RIM_Z)


# Collar-local mm, in order: the -Y end, the +Y end, the +X point, the -X point.
COLLAR_RIM_VIEW_POINTS_MM = tuple(
    _collar_local(x, y)
    for x, y in (
        (0.0, -COLLAR_RIM_RADIUS),
        (0.0, COLLAR_RIM_RADIUS),
        (COLLAR_RIM_RADIUS, 0.0),
        (-COLLAR_RIM_RADIUS, 0.0),
    )
)
# View frame (-1.319, -8.650) -> collar-local mm (-0.865, -8.707, 6.200),
# 0.72 mm outside the lower drive-pin hole.
COLLAR_LANDING_MM = _collar_local(
    -math.sqrt(COLLAR_RIM_RADIUS**2 - COLLAR_LANDING_Y**2), COLLAR_LANDING_Y
)
# A listed circle is the rim within these of its modelled centre and radius,
# its axis along the collar's (both senses), and the arc holding the landing
# when its closest point to it is within 1e-6 m (draw_transgear_disc_hub's).
_RIM_CENTER_TOL_MM = 1e-4
_RIM_RADIUS_TOL_MM = 1e-4
_RIM_AXIS_TOL = 1e-6
_RIM_LANDING_TOL_MM = 1e-3
# Seen edge-on, a rim's +/-X points project onto its line's midpoint; the
# projection is exact to ~1e-9 m.
_EDGE_ON_TOL_M = 1e-6
# The collar has no anchor here: _balloon_collar_on_its_rear_rim places it.
TRANSGEAR_BALLOON_ANCHORS = {
    stem: BalloonAnchor(instance="pd-transgear-removable-1")
    if stem == "pd-transgear-removable"
    else BalloonAnchor()
    for stem in TRANSGEAR_QUANTITIES
    if stem != COLLAR_STEM
}
# Farm run 20261001T051043622Z found no reachable isometric ink for the feed
# sleeve: its extreme-point picks missed, and its gear edges exceeded the
# fallback's edge budget. The inner right view shows that sleeve, the rear
# bushing behind the reducer disc, and the knob drive and hanger hardware
# obscured by their neighbours. The current reducer and feed geometry is
# spec-driven; do not preserve old disc diameters or knob centres here as
# visibility assumptions. Native balloon landings still prove each attachment.
INNER_STEMS = frozenset(
    {
        "pd-transgear-feed-pinion",
        "pd-transgear-knob-shaft",
        "pd-transgear-drive-collar",
        "vn-transgear-knob-drive-pin",
        "vn-transgear-knob-cup-pin",
        "vn-transgear-arm-plate-screw",
        "vn-transgear-arm-plate-locating-pin",
        "vn-transgear-latch-pin",
        "pd-transgear-rear-bushing",
    }
)
if not INNER_STEMS < set(TRANSGEAR_QUANTITIES):
    raise AssertionError("the inner view balloons transgear families only")
INNER_INSTANCES = frozenset(
    name for name in TRANSGEAR_INSTANCES if name.rsplit("-", 1)[0] in INNER_STEMS
)


def transgear_balloon_items(
    items: dict[str, str],
) -> tuple[tuple[tuple[str, str], ...], tuple[tuple[str, str], ...]]:
    """(isometric, inner view) balloon items, each in item order.

    Every transgear family lands on exactly one of the two views; the inner
    view balloons only the families it shows.
    """
    ordered = sorted(
        ((stem, items[stem]) for stem in TRANSGEAR_QUANTITIES),
        key=lambda pair: int(pair[1]),
    )
    return (
        tuple(pair for pair in ordered if pair[0] not in INNER_STEMS),
        tuple(pair for pair in ordered if pair[0] in INNER_STEMS),
    )


@dataclass(frozen=True)
class RimCandidate:
    """One circular edge the inner view lists for the collar: its
    ``ICurve.CircleParams`` (centre and radius in collar-local mm, the axis a
    unit vector) and its ``IEdge.GetClosestPointOn`` the landing (mm)."""

    edge: Any
    circle: tuple[float, float, float, float, float, float, float]
    closest_mm: tuple[float, float, float]


def collar_rear_rim(candidates: Sequence[RimCandidate]) -> RimCandidate:
    """The one listed arc of the collar's rear-face rim that holds the
    landing; none or several raise, listing every circle the view lists."""
    centre = (0.0, 0.0, COLLAR_RIM_Z)

    def is_rim(candidate: RimCandidate) -> bool:
        circle = candidate.circle
        offset = sum(abs(a - b) for a, b in zip(circle[:3], centre))
        return (
            offset <= _RIM_CENTER_TOL_MM
            and abs(circle[6] - COLLAR_RIM_RADIUS) <= _RIM_RADIUS_TOL_MM
            and 1.0 - abs(circle[5]) <= _RIM_AXIS_TOL
            and math.dist(candidate.closest_mm, COLLAR_LANDING_MM)
            <= _RIM_LANDING_TOL_MM
        )

    matches = [candidate for candidate in candidates if is_rim(candidate)]
    if len(matches) != 1:
        listed = "; ".join(
            "r {6:.4f} at ({0:.4f}, {1:.4f}, {2:.4f}) axis ({3:.3f}, {4:.3f}, {5:.3f})".format(
                *candidate.circle
            )
            + f", {math.dist(candidate.closest_mm, COLLAR_LANDING_MM):.4f} from the landing"
            for candidate in candidates
        )
        landing = ", ".join(f"{value:.3f}" for value in COLLAR_LANDING_MM)
        raise RuntimeError(
            f"{COLLAR_INSTANCE}: expected one listed rear-rim arc r "
            f"{COLLAR_RIM_RADIUS:g} mm at z {COLLAR_RIM_Z:g} mm through ({landing}), "
            f"matched {len(matches)} of {len(candidates)} circles: {listed or 'none'}"
        )
    return matches[0]


def collar_rim_landing(
    minus_end: tuple[float, float], plus_end: tuple[float, float]
) -> tuple[float, float]:
    """Where the collar's leader lands: the landing's y along the rear rim's
    projected line, from its -Y end to its +Y end (sheet metres)."""
    t = (COLLAR_LANDING_Y + COLLAR_RIM_RADIUS) / (2.0 * COLLAR_RIM_RADIUS)
    return (
        minus_end[0] + t * (plus_end[0] - minus_end[0]),
        minus_end[1] + t * (plus_end[1] - minus_end[1]),
    )


# _spread_balloons rings a view's balloons in its attachments' angular order
# about the view's centre, then pushes crowded circles apart along the ring.
# An attachment far from that centre can leave its leader across a pushed
# neighbour's: on farm run 20261002T180658288Z (swmaker000009, inner view at
# 1:3, its nine circles 0.60 rad apart on a 27 mm ring) the arm-plate screw's
# (item 17) leader from its attachment (233.3, 188.8) mm crossed the rear
# bushing's (item 24) from (229.0, 180.8) mm at (233.2, 189.0). Swapping two
# crossing leaders' slots uncrosses them and strictly shortens their total
# length (the triangle inequality), so repeated swaps end; the cap only
# bounds a wrong input.
_UNCROSS_SWAPS_MAX = 64


def uncrossed_ring_slots(
    centres: Sequence[tuple[float, float]],
    attachments: Sequence[tuple[float, float]],
) -> list[int]:
    """Which ring slot (an index into ``centres``, the circle centres as
    placed) each balloon takes so that no two leaders, each from its circle's
    centre to its attachment, cross. Leaders that do not cross keep their
    slots, so the slots, and the circles' clearances, are the ring's own."""
    if len(centres) != len(attachments):
        raise ValueError("one ring slot per balloon attachment")
    slots = list(range(len(centres)))
    for _swap in range(_UNCROSS_SWAPS_MAX + 1):
        segments = [
            LeaderSegment(
                label=str(index),
                kind="balloon",
                x0=centres[slots[index]][0],
                y0=centres[slots[index]][1],
                x1=attach[0],
                y1=attach[1],
            )
            for index, attach in enumerate(attachments)
        ]
        crossings = find_leader_leader_crossings(segments)
        if not crossings:
            return slots
        first, second = int(crossings[0].a.label), int(crossings[0].b.label)
        slots[first], slots[second] = slots[second], slots[first]
    raise RuntimeError(
        f"balloon ring: leaders still cross after {_UNCROSS_SWAPS_MAX} slot swaps"
    )


def _uncross_ring(
    adapter: Any, landings: Sequence[BalloonLanding], *, label: str
) -> None:
    """Move ``landings``' ringed balloons between their own ring slots until
    no two leaders cross (:func:`uncrossed_ring_slots`); attachments stay."""
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
            raise RuntimeError(f"{label}: {landing.stem} balloon is unreadable")
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
                f"{label}: failed to move {landings[index].stem} balloon"
            )
    if moved:
        _telemetry.info(
            f"{label}: swapped ring slots to uncross leaders: "
            + ", ".join(
                f"{landings[index].stem} -> {landings[slots[index]].stem}'s"
                for index in moved
            )
        )
        rebuild_drawing(adapter, label=f"{label} uncrossed")


# Sheet 1's isometric balloons what sheets 2 and 3 do not show: the chain,
# and the spare T18 on the base deck (the third removable inserted), whose
# item sheet 2 balloons on the mounted knob wheel.
SPARE_INSTANCE = "pd-transgear-removable-3"
ASSEMBLED_BALLOON_ANCHORS = {
    "vn-chain-inner-link": BalloonAnchor(),
    "vn-chain-outer-link": BalloonAnchor(),
    "pd-transgear-removable": BalloonAnchor(instance=SPARE_INSTANCE),
}
# Sheet 3's exploded view balloons every family it shows.
PLATEN_BALLOON_ANCHORS = {stem: BalloonAnchor() for stem in explode.SHOWN_STEMS}


def _in_item_order(
    items: dict[str, str], stems: Iterable[str]
) -> tuple[tuple[str, str], ...]:
    return tuple(
        sorted(((stem, items[stem]) for stem in stems), key=lambda p: int(p[1]))
    )


def assembled_balloon_items(items: dict[str, str]) -> tuple[tuple[str, str], ...]:
    """Sheet 1's isometric balloons, in item order."""
    return _in_item_order(items, ASSEMBLED_BALLOON_ANCHORS)


def platen_balloon_items(items: dict[str, str]) -> tuple[tuple[str, str], ...]:
    """Sheet 3's exploded-view balloons, in item order."""
    return _in_item_order(items, PLATEN_BALLOON_ANCHORS)


Box = tuple[float, float, float, float]


def _grown(box: Box, by: float) -> Box:
    return (box[0] - by, box[1] - by, box[2] + by, box[3] + by)


def ring_fit_shift(outline: Box, limits: Box, *, name: str) -> tuple[float, float]:
    """Shift that centres a view's balloon ring inside ``limits``.

    Outlines and limits are sheet metres (left, bottom, right, top); the ring
    is the outline grown by BALLOON_RING_REACH. Raises naming each axis on
    which the ring is larger than the room.
    """
    ring = _grown(outline, BALLOON_RING_REACH)
    findings = [
        f"{name} ring {axis} {(ring[hi] - ring[lo]) * 1000:.1f} mm > room "
        f"{(limits[hi] - limits[lo]) * 1000:.1f} mm"
        for axis, lo, hi in (("width", 0, 2), ("height", 1, 3))
        if ring[hi] - ring[lo] > limits[hi] - limits[lo]
    ]
    if findings:
        raise ValueError(f"balloon ring does not fit: {'; '.join(findings)}")
    return (
        (limits[0] + limits[2] - ring[0] - ring[2]) / 2.0,
        (limits[1] + limits[3] - ring[1] - ring[3]) / 2.0,
    )


def step_down_to_fit(
    outline_at: Callable[[tuple[float, float]], Box],
    ladder: tuple[tuple[float, float], ...],
    limits: Box,
    *,
    name: str,
) -> tuple[tuple[float, float], Box]:
    """The first ``ladder`` scale, largest first, whose ring fits ``limits``.

    ``outline_at`` applies a scale to the placed view and returns the outline
    SolidWorks reads back. The outline carries a fixed sheet-space padding, so
    no scale's outline is predicted from another's: each candidate is applied
    and re-read. Returns the scale and its outline; raises naming every
    scale's overflow when the smallest still overflows.
    """
    findings = []
    for scale in ladder:
        outline = outline_at(scale)
        try:
            ring_fit_shift(outline, limits, name=f"{name} at {_scale_text(scale)}")
        except ValueError as error:
            findings.append(str(error))
            continue
        return scale, outline
    raise ValueError(f"no {name} scale fits: {' | '.join(findings)}")


def _native_outline_at(
    adapter: Any, view: Any, placed: tuple[float, float], *, label: str
) -> Callable[[tuple[float, float]], Box]:
    """``outline_at`` for step_down_to_fit on a placed drawing view."""
    current = [placed]

    def outline_at(scale: tuple[float, float]) -> Box:
        if scale != current[0]:
            _set_view_scale(adapter, view, scale, label=label)
            current[0] = scale
        return _view_outline(view)

    return outline_at


def transgear_view_shift(iso_outline: Box) -> tuple[float, float]:
    """Shift that centres the transgear isometric's balloon ring in sheet 2's
    field vertically. It does not move along x, so the room left of it for the
    inner view stays the same.

    The outline is in sheet metres (left, bottom, right, top). Raises if the
    ring is taller than the field.
    """
    _left, bottom, _right, top = SHEET_TWO_RING_LIMITS
    ring = _grown(iso_outline, BALLOON_RING_REACH)
    if ring[3] - ring[1] > top - bottom:
        raise ValueError(
            f"sheet 2 isometric ring height {(ring[3] - ring[1]) * 1000:.1f} mm > "
            f"room {(top - bottom) * 1000:.1f} mm"
        )
    return (0.0, (bottom + top - ring[1] - ring[3]) / 2.0)


def inner_view_shift(iso_outline: Box, inner_outline: Box) -> tuple[float, float]:
    """Shift that centres the inner view's balloon ring between the BOM and
    the isometric's ring, level with the isometric.

    Outlines are sheet metres (left, bottom, right, top). Raises naming every
    side of either ring that leaves SHEET_TWO_RING_LIMITS, or an inner ring
    reaching within SHEET_TWO_RING_GAP of the isometric's.
    """
    left, bottom, right, top = SHEET_TWO_RING_LIMITS
    iso_ring = _grown(iso_outline, BALLOON_RING_REACH)
    room_right = iso_ring[0] - SHEET_TWO_RING_GAP
    shift = (
        (left + room_right) / 2.0 - (inner_outline[0] + inner_outline[2]) / 2.0,
        (iso_outline[1] + iso_outline[3]) / 2.0
        - (inner_outline[1] + inner_outline[3]) / 2.0,
    )
    inner_ring = _grown(
        (
            inner_outline[0] + shift[0],
            inner_outline[1] + shift[1],
            inner_outline[2] + shift[0],
            inner_outline[3] + shift[1],
        ),
        BALLOON_RING_REACH,
    )
    findings = []
    for name, ring in (("isometric", iso_ring), ("inner view", inner_ring)):
        for side, value, limit, outside in (
            ("left", ring[0], left, ring[0] < left),
            ("bottom", ring[1], bottom, ring[1] < bottom),
            ("right", ring[2], right, ring[2] > right),
            ("top", ring[3], top, ring[3] > top),
        ):
            if outside:
                findings.append(
                    f"{name} ring {side} {value * 1000:.1f} mm past {limit * 1000:.1f} mm"
                )
    if inner_ring[2] > room_right:
        findings.append(
            f"inner view ring right {inner_ring[2] * 1000:.1f} mm within "
            f"{SHEET_TWO_RING_GAP * 1000:g} mm of the isometric ring "
            f"({iso_ring[0] * 1000:.1f} mm)"
        )
    if findings:
        raise ValueError(f"sheet 2 balloon rings do not fit: {'; '.join(findings)}")
    return shift


def _scale_text(scale: tuple[float, float]) -> str:
    return f"{scale[0]:g}:{scale[1]:g}"


def inner_view_scale(
    iso_outline: Box, inner_outline: Box, placed: tuple[float, float]
) -> tuple[float, float]:
    """The largest INNER_SCALE_LADDER scale whose ring inner_view_shift fits.

    ``inner_outline`` is the inner view's outline at ``placed``; a view's
    outline scales with its scale about its centre, and the fit reads only
    its size. Raises naming every scale's finding when none fits.
    """
    x0, y0, x1, y1 = inner_outline
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    findings = []
    for scale in INNER_SCALE_LADDER:
        k = (scale[0] / scale[1]) / (placed[0] / placed[1])
        hw, hh = (x1 - x0) / 2.0 * k, (y1 - y0) / 2.0 * k
        try:
            inner_view_shift(iso_outline, (cx - hw, cy - hh, cx + hw, cy + hh))
        except ValueError as error:
            findings.append(f"{_scale_text(scale)}: {error}")
            continue
        return scale
    raise ValueError(f"no inner-view scale fits sheet 2 ({' | '.join(findings)})")


# --- sheet wording ---------------------------------------------------------------
_N = BOM_PART_NUMBERS
KNOB_TEETH = knob_shaft.TEETH
# CONTRACT-paper-drive.md §1, front to rear; None is a feature of the plate.
KNOB_STACK: tuple[tuple[str | None, str], ...] = (
    ("pd-transgear-thumbnut", "THUMBNUT"),
    ("pd-transgear-removable", sprocket.KNOB_CONFIG),
    ("pd-transgear-drive-collar", "COLLAR"),
    ("pd-transgear-knob-shaft", f"SHAFT {KNOB_TEETH}T"),
    ("pd-transgear-knob-thrust-ring", "RING"),
    (None, "PLATE HUB"),
    ("pd-transgear-arm-plate", "PLATE"),
    (None, "REAR BOSS"),
    ("pd-transgear-knob-cup", "CUP"),
    ("vn-transgear-knob-cup-pin", "PIN"),
)
# The knob's end float: the cup set on a feeler END_FLOAT behind the plate's
# boss and pinned there (R9-70, K-1), accepted at the feeler's own band.
KNOB_END_FLOAT_RANGE = (
    knob_shaft.END_FLOAT - knob_shaft.END_FLOAT_SET_TOL,
    knob_shaft.END_FLOAT + knob_shaft.END_FLOAT_SET_TOL,
)
# The platen's screw stations (platen_spec): its front counterbores take the
# guide screws, its through-taps the clip screws.
GUIDE_SCREWS = len(platen.GUIDE_HOLE_X) * len(platen.GUIDE_HOLE_Y)
CLIP_SCREWS = len(platen.SOCKET_XY)


def _stack_text() -> str:
    return ", ".join(
        f"{_N[stem]} {label}" if stem else label for stem, label in KNOB_STACK
    )


def _step_text(*, operating_domain: RackOperatingDomain) -> dict[str, str]:
    pin_lo, pin_hi = joints.LATCH_PIN_PROUD_RANGE
    drive_lo, drive_hi = drive_pin.PROUD_RANGE
    knob_lo, knob_hi = KNOB_END_FLOAT_RANGE
    teeth = f"{KNOB_TEETH}T"
    return {
        "bar-clamped": (
            f"CLAMP THE {_N['pd-support-bar']} BAR TO BOTH COLUMNS, EACH BETWEEN A "
            f"{_N['sh-column-clamp-front']} FRONT AND A {_N['sh-column-clamp-back']} BACK "
            f"ARC, WITH THE {_N['vn-clamp-screw']} SCREWS FROM THE BAR FRONT. SET "
            f"THE BAR TOP {steps.BAR_TOP_ABOVE_DECK:.1f} ABOVE THE BASE DECK AT "
            "BOTH COLUMNS; TIGHTEN."
        ),
        "rack-soldered": (
            f"SOFT-SOLDER THE {_N['pd-platen-rack']} RACK TO THE {_N['pd-platen']} "
            "PLATEN'S BACK, TEETH DOWN, ENDS FLUSH WITH THE PLATEN'S, CRESTS "
            f"{steps.RACK_CREST_TEXT} BELOW "
            "ITS BOTTOM EDGE. SIGHT ALONG IT: TEETH STRAIGHT, NO SOLDER IN THE GAPS."
        ),
        "guides-screwed": (
            f"SCREW THE {len(platen.GUIDE_HOLE_Y)} {_N['pd-platen-guide']} GUIDES TO "
            f"THE PLATEN BACK WITH {GUIDE_SCREWS} {_N['vn-fillister-screw']} SCREWS "
            "FROM THE FRONT, HEADS IN THE COUNTERBORES."
        ),
        "clips-fitted": (
            f"SCREW THE {_N['pd-platen-clip']} CLIPS TO THE PLATEN FRONT WITH "
            f"{CLIP_SCREWS} {_N['vn-fillister-screw']} SCREWS; SLIP THE "
            f"{_N['pd-platen-paper']} PAPER UNDER THEIR SPRING RAILS."
        ),
        "platen-hung": (
            "TRIAL-HANG THE PLATEN ON THE BAR, THE TOP GUIDE ON THE BAR TOP. FIT THE "
            f"{_N['pd-guide-lock']} LOCKS TO THE GUIDE BACKS BEHIND THE BAR WITH "
            f"THEIR {_N['vn-guide-lock-screw']} SCREWS, LOOSE."
        ),
        "guide-locks-set": (
            f"SNUG EACH {_N['pd-guide-lock']} LOCK'S {_N['vn-guide-lock-screw']} SCREWS, "
            "PUSH THE LOCK AT ITS MIDDLE AWAY FROM THE BAR TILL ITS HOLES BEAR ON "
            "THEM; TIGHTEN."
        ),
        "lock-seats-faced": (
            f"FACE LOCK SEATS TO {platen_guide.LOCK_GAP_FIT_TEXT} PLATEN FLOAT; "
            "ELSE STOP AND REPORT."
        ),
        "latch-pin-pressed": (
            f"PRESS THE {_N['vn-transgear-latch-pin']} DOWEL INTO THE "
            f"{_N['pd-transgear-arm']} ARM'S REAMED HOLE TO THE HOLE FLOOR, "
            f"{pin_lo:.2f} TO {pin_hi:.2f} PROUD."
        ),
        "pin-pressed": (
            f"PRESS THE {_N['pd-transgear-pin']} PIN INTO THE {_N['pd-transgear-arm']} "
            "ARM'S REAMED HOLE FROM THE REAR TILL ITS HEAD SEATS ON THE ARM."
        ),
        "arm-plate-located": (
            f"CLAMP {_N['pd-transgear-arm']} AND {_N['pd-transgear-arm-plate']} "
            "TOGETHER IN THE S-K JIG PER THEIR DRAWINGS; "
            "MATCH-DRILL AND REAM THE LOCATING HOLES. "
            f"PRESS {TRANSGEAR_QUANTITIES['vn-transgear-arm-plate-locating-pin']} "
            f"{_N['vn-transgear-arm-plate-locating-pin']} DOWELS INTO THE ARM "
            f"{plate_locating_pin.PROUD_LIMITS_MM[0]:.2f} TO "
            f"{plate_locating_pin.PROUD_LIMITS_MM[1]:.2f} PROUD, NOT TO THE "
            "BLIND FLOOR; MATCH-MARK ARM AND PLATE."
        ),
        "arm-plate-fitted": (
            f"FIT THE {_N['pd-transgear-arm-plate']} PLATE ON THE LOCATING DOWELS. "
            f"FIT {TRANSGEAR_QUANTITIES['vn-transgear-arm-plate-screw']} "
            f"{_N['vn-transgear-arm-plate-screw']} SCREWS IN THE ARM'S THROUGH TAPS; "
            "SNUG BOTH, THEN TIGHTEN THEM IN TURN. DOWELS LOCATE; SCREWS CLAMP ONLY. "
            "PUSH AND ROCK THE PLATE BY HAND: NO SHAKE ON THE DOWELS, NO DAYLIGHT "
            "UNDER IT. RE-CHECK AFTER EVERY REMOVAL."
        ),
        "arm-plate-screws-cut": (
            f"TAKE BOTH {_N['vn-transgear-arm-plate-screw']} SCREWS OUT; CUT THEIR "
            f"TIPS FLUSH TO {joints.PLATE_SCREW_CUT_PROUD_MAX:.2f} PROUD OF THE ARM'S "
            f"FRONT FACE; BREAK THE CUT EDGE {plate_screw.CUT_END_BREAK_TEXT}. "
            "REFIT THE SAME SCREWS IN THE SAME HOLES BEFORE PIVOTING THE HANGER."
        ),
        # R9-71: the spacer is pressed on the shoulder, so its faces' tilt is
        # fixed in the bar; the MHA-VN-049 spring holds the arm on it.
        "hanger-pivoted": (
            f"{_N['vn-transgear-pivot-spring']} SPRING, THEN ARM, ON THE "
            f"{_N['vn-transgear-pivot-screw']} SHOULDER SCREW FROM THE REAR; PRESS "
            f"THE {_N['pd-transgear-pivot-spacer']} SPACER, AS MADE, ON THE SHOULDER, "
            "FLUSH WITH ITS END ON A FLAT. SEAT IT IN THE "
            f"{_N['pd-support-bar']} BAR'S BLIND TAP WITH LOW-STRENGTH THREADLOCKER; "
            "THE ARM FALLS FREELY. THE ARM'S PIVOT BORE IS REAMED TO THIS SCREW: "
            "KEEP THEM TOGETHER."
        ),
        "disc-cluster-assembled": (
            f"FIT THE {_N['pd-rack-pinion']} DISC ON THE {_N['pd-transgear-disc-hub']} "
            f"HUB'S SPIGOT, THEN THE HUB'S D-BORE ON THE {_N['pd-transgear-feed-pinion']} "
            "D-FLAT, SPIGOT TO THE STEP."
        ),
        "hub-faced-to-nose": (
            "AS FITTED, MEASURE THE HUB FRONT FACE BEHIND THE SLEEVE NOSE. HUB "
            f"OFF; FACE ITS FRONT TILL {cluster_fit.HUB_NOSE_WINDOW_TEXT} BEHIND; "
            "REFIT."
        ),
        "disc-taps-transferred": (
            "MOUNT THE CLUSTER ON A MANDREL IN THE "
            f"{_N['pd-transgear-feed-pinion']} BORE. WITH THE {_N['pd-rack-pinion']} "
            "PIN IN EACH TOOTH SPACE IN TURN, TAP THE DISC CENTRAL, FACE SQUARE, "
            f"TILL THE DIAL READS {quality.toothspace_runout_tir_mm():.2f} TIR MAX. "
            "SPOT-DRILL THE DISC THROUGH THE "
            f"{hub_geometry.SCREW_COUNT} FLANGE HOLES; DRILL AND TAP {disc_screw.THREAD}. "
            f"FIX WITH {hub_geometry.SCREW_COUNT} {_N['vn-transgear-disc-screw']} SCREWS. "
            f"LOCK SCREWS; RECHECK ALL {disc.TEETH} SPACES; "
            "THEN MATCH-MARK DISC AND HUB."
        ),
        "disc-screws-cut": (
            f"CUT {_N['vn-transgear-disc-screw']} TIPS "
            f"{disc_screw.TIP_BELOW_REAR_FACE_TEXT} BELOW DISC REAR FACE; "
            f"BREAK {disc_screw.CUT_END_BREAK_TEXT}."
        ),
        "oil-hole-drilled": (
            f"DRILL THE \u00d8{hub.OIL_HOLE_DIA:.1f} OIL HOLE CENTRED ON THE HUB BODY, "
            "THROUGH HUB AND "
            f"SLEEVE IN ONE OPERATION AS {_N['pd-transgear-disc-hub']} SHOWS; "
            "DEBURR THE BORE."
        ),
        "disc-cluster-hung": (
            "OIL THE PIN; CLUSTER ON, PINION REARWARD; A "
            f"{_N['pd-transgear-front-bushing']} BUSHING BLANK ON THE NOSE TRAPS HUB "
            f"AND DISC; {_N['vn-transgear-retaining-ring']} RING SIDEWAYS IN THE PIN "
            "GROOVE. NO REAR BUSHING YET: CLUSTER FORWARD ON THE RING."
        ),
        "collar-pins-pressed": (
            f"PRESS {TRANSGEAR_QUANTITIES['vn-transgear-knob-drive-pin']} "
            f"{_N['vn-transgear-knob-drive-pin']} DOWELS INTO THE "
            f"{_N['pd-transgear-drive-collar']} COLLAR TO A STOP, {drive_lo:.2f} TO "
            f"{drive_hi:.2f} PROUD OF ITS FRONT FACE."
        ),
        "pilot-faced-to-fit": (
            f"FACE THE COLLAR'S PILOT {collar.PILOT_PROUD_TEXT} PROUD OF EACH "
            f"{_N['pd-transgear-removable']} WHEEL FLAT ON THE PINS; ELSE STOP AND "
            "REPORT."
        ),
        "knob-stack-fitted": (
            f"KNOB STACK, FRONT TO REAR: {_stack_text()}. SHAFT THROUGH THE LOOSE "
            "RING INTO THE PLATE BORE FROM THE FRONT, PUSHED REARWARD. CUP ON THE "
            f"JOURNAL ON A {knob_shaft.END_FLOAT:.1f} FEELER AT THE BOSS; "
            f"MATCH-DRILL {cup_pin.HOLE_TEXT} THROUGH BOTH "
            f"{knob_cup.PIN_HOLE_FROM_FRONT:.1f} FROM THE CUP FRONT; PRESS THE PIN "
            "IN, CENTRED. COLLAR ON THE CORE UNPINNED, PINS FORWARD."
        ),
        "latch-hook-fitted": (
            f"SCREW THE {_N['pd-latch-hook']} HOOK'S BASE TO THE BAR'S BACK FACE "
            f"WITH {TRANSGEAR_QUANTITIES['vn-latch-hook-bracket-screw']} "
            f"{_N['vn-latch-hook-bracket-screw']} SCREWS, ARM HANGING DOWN; ITS "
            "PIN HOLE IS NOT YET DRILLED."
        ),
        "hanger-meshed": (
            f"SWING THE HANGER UP TILL THE {_N['pd-transgear-feed-pinion']} TEETH "
            f"ENTER THE {_N['pd-platen-rack']} RACK. ALIGN A FEED TOOTH CENTRE "
            "DIRECTLY BELOW A RACK SPACE CENTRE. KNOB HELD, SET "
            f"{steps.RACK_DATUM_BACKLASH_TEXT} PLATEN SHAKE AT THAT DATUM "
            "(DIAL ALONG THE RACK); CLAMP THE ARM TO THE BAR. "
            f"{operating_domain.operating_window_text} {OPERATING_DIRECTION_TEXT}. "
            "RUN THAT WINDOW: NO TIGHT SPOT, SHAKE AT EVERY TOOTH. "
            "STOP BEFORE EITHER END LIMIT; RESET ONLY WITH FEED DISENGAGED."
        ),
        # The hook's Ø3.3 pin hole is match-drilled from the pin at that mesh,
        # then the hook is hardened and refitted with the hole's lower edge on
        # the pin before its screws are tightened, so the unclamped arm has no
        # room to fall and open the mesh (steps.LATCH_SLACK_ALONG; Codex P1 on
        # b2eb9a0e1).
        "hook-pin-hole-match-drilled": (
            f"HOLDING THAT MESH, MARK THE {_N['vn-transgear-latch-pin']} PIN'S "
            f"AXIS WHERE ITS END BEARS ON THE {_N['pd-latch-hook']} HOOK'S "
            "STRAIGHT RUN. REMOVE THE HOOK; DRILL ITS PIN HOLE AT THE MARK PER "
            f"{_N['pd-latch-hook']}; HARDEN AND TEMPER BLUE. REFIT, ITS HOLE'S "
            f"LOWER EDGE ON THE {_N['vn-transgear-latch-pin']} PIN, THEN TIGHTEN "
            "THE SCREWS. UNCLAMP, LATCH, RE-RUN THE DEFINED ENGAGED-FEED WINDOW."
        ),
        "loaded-rack-geometry-checked": (
            "HANGER LATCHED, KNOB HELD. WITH PAPER LOADED, RUN THE PLATEN THROUGH "
            "THE WHOLE ENGAGED WINDOW: NO TIGHT SPOT, SHAKE AT EVERY TOOTH; ARM, "
            "HOOK AND PLATEN STAY SEATED. ELSE RE-SEAT THE RACK OR GUIDES."
        ),
        "fitup-pose-set": (
            "HANGER LATCHED. PULL THE CRANK SHAFT FORWARD; PUSH THE KNOB SHAFT "
            f"REARWARD ({teeth} ON THE "
            f"RING, RING ON THE HUB). SLIDE THE COLLAR BACK AGAINST THE {teeth}; "
            f"{sprocket.KNOB_CONFIG} AND THUMBNUT ON FINGER-TIGHT, "
            f"{steps.KNOB_HELD_BACK_TEXT}. TURN THE DISC SO A {teeth} GAP FACES S "
            f"AND A {disc.TEETH}T TOOTH FACES K, WITHIN "
            f"{quality.reducer_setup_clock_deviation_mm():.2f} AT THE PITCH CIRCLE. "
            "TURN THE KNOB: NO TIGHT SPOT, SHAKE AT EVERY TOOTH."
        ),
        "front-bushing-faced-to-fit": (
            f"CLUSTER, HUB AND DISC FORWARD, FEEL m ({teeth} TO DISC). FACE THE "
            f"{_N['pd-transgear-front-bushing']} BUSHING'S REAR TILL m IS "
            f"{cluster_fit.FIT_WINDOW_TEXT}; ELSE REPORT."
        ),
        # The blank (MHA-PD-024 BLANK_LENGTH_MIN) is longer than the nominal gap
        # it fills, so it is faced to the gap gauged before it goes on.
        "rear-bushing-faced-to-fit": (
            "CLUSTER FORWARD, DEPTH-GAUGE THE SLEEVE REAR FACE FROM THE ARM; "
            f"FACE THE {_N['pd-transgear-rear-bushing']} BLANK TO THAT LESS "
            f"{cluster_fit.SLEEVE_FLOAT_WINDOW_TEXT}. STRIP TO THE PIN, BLANK ON, "
            f"REFIT. DISC END FLOAT {cluster_fit.FLOAT_WINDOW_TEXT} AND FREE; ELSE "
            "REPORT."
        ),
        "collar-rear-faced-to-fit": (
            f"IN STEP {steps.step_number('fitup-pose-set')}'S POSE, "
            f"{steps.KNOB_HELD_BACK_TEXT}. {collar.BODY_FACE_PHRASE}: SET THE "
            f"{sprocket.KNOB_CONFIG} FRONT FACE {collar.FIT_UP_OFFSET_SET_TEXT} FORWARD "
            f"OF THE {sprocket.CRANK_CONFIG} FRONT FACE. START LONG; STRIP AND FACE "
            "THE REAR TO MOVE THE WHEEL REARWARD, REFITTING WITH THE REAR FACE ON F. "
            f"FINISHED BODY WITHIN {_N['pd-transgear-drive-collar']}'S FITTED LIMITS; "
            f"ELSE REPORT. STEP {steps.step_number('fitup-accepted')} RE-CHECKS."
        ),
        "collar-shoulder-seated": (
            f"SEAT THE {_N['pd-transgear-drive-collar']} D-BORE ON THE SHAFT D-FLAT, "
            "ITS REAR FACE BEARING ON THE ACTUAL GEAR FRONT F. "
            f"{sprocket.KNOB_CONFIG} ON THE DRIVE DOWELS, NUT TIGHT ON THE PILOT."
        ),
        "stud-end-cut": (
            f"IF THE {_N['pd-transgear-knob-shaft']} STUD END STANDS PROUD OF THE "
            f"THUMBNUT RIM, {collar.STUD_CUT_PHRASE}."
        ),
        "collar-disc-air-inspected": (
            "CHAIN OFF. REMOVE THE TRIAL PLATEN, KEEPING THE ARM HELD IN ITS "
            "OPERATING LATCH POSE. "
            f"{collar.COLLAR_DISC_AIR_PHRASE}; "
            f"ONE DISC TURN = {disc.TEETH / KNOB_TEETH:g} KNOB TURNS. "
            "REFIT THE PLATEN AND LOCK THE ASSEMBLY; RE-CHECK THE OVERLAP AIR "
            "AND RACK MESH. ELSE REPORT."
        ),
        "fitup-accepted": (
            f"ACCEPT, IN STEP {steps.step_number('fitup-pose-set')}'S POSE: "
            f"{sprocket.KNOB_CONFIG} FRONT FACE {steps.OFFSET_ACCEPT_TEXT} FORWARD "
            f"OF THE {sprocket.CRANK_CONFIG} FRONT FACE "
            f"(STEP {steps.step_number('collar-rear-faced-to-fit')}'S SETTING, WIDENED "
            f"FOR REFITTING AND GAUGE SPREAD: THE {sprocket.KNOB_CONFIG} UP TO "
            f"{steps.OFFSET_ACCEPT_TOL - collar.FIT_UP_OFFSET_TARGET:.2f} BEHIND "
            f"PASSES); KNOB END FLOAT {knob_lo:.2f} TO {knob_hi:.2f}; "
            f"{sprocket.KNOB_CONFIG} FREE "
            "UNDER THE NUT; THE HANGER FREE; RE-CHECK ACTUAL COLLAR TO DISC AIR "
            f"{steps.COLLAR_DISC_AIR_TEXT} AT OVERLAP AFTER REFITTING AND LOCKING. "
            "ELSE REPORT."
        ),
        "chain-closed": (
            f"LOOP {chain.LINK_COUNT} PITCHES OF ANSI #25 CHAIN, "
            f"{_N['vn-chain-inner-link']} INNER AND {_N['vn-chain-outer-link']} OUTER "
            f"LINKS, OVER THE {sprocket.KNOB_CONFIG} AND THE {sprocket.CRANK_CONFIG}; "
            "JOIN THE ENDS WITH A #25 "
            "CONNECTING LINK AS ONE OUTER LINK, ITS CLIP'S CLOSED END LEADING "
            "IN THE DIRECTION OF TRAVEL. THE CENTRES ARE FIXED: NO TENSIONING, "
            "THE SLACK RUN HANGS FREE."
        ),
        "chain-run-accepted": (
            "TURN THE CRANK 2 TURNS EACH WAY: THE CHAIN SEATS ON EVERY TOOTH OF "
            "BOTH WHEELS WITHOUT CLIMBING OR A TIGHT SPOT, AND THE SLACK RUN "
            "TOUCHES NOTHING. OTHERWISE REPORT."
        ),
    }


def _step_column(heading: str, keys: tuple[str, ...], text: dict[str, str]) -> str:
    lines = textwrap.wrap(
        heading,
        width=FITUP_LINE_WIDTH,
        break_on_hyphens=False,
        break_long_words=False,
    )
    for key in keys:
        lines += textwrap.wrap(
            text[key],
            width=FITUP_LINE_WIDTH,
            initial_indent=f"{steps.step_number(key)}. ",
            subsequent_indent="   ",
            break_on_hyphens=False,
            break_long_words=False,
        )
    return "\n".join(lines)


def _step_columns(
    *, operating_domain: RackOperatingDomain,
) -> tuple[str, tuple[str, str], tuple[str, str]]:
    """Sheet 3's platen steps, then the two columns on sheets 4 and 5."""
    text = _step_text(operating_domain=operating_domain)
    if set(text) != set(steps.SEQUENCE):
        raise AssertionError("paper-drive step text must cover exactly the sequence")
    first = steps.step_number(FITUP_FIRST_COLUMN_KEY) - 1
    second = steps.step_number(FITUP_SECOND_COLUMN_KEY) - 1
    chain_start = steps.step_number(FITUP_CHAIN_KEY) - 1
    chain_second = steps.step_number(CHAIN_SECOND_COLUMN_KEY) - 1
    return (
        _step_column(
            f"PLATEN AND SUPPORT; STEP {steps.step_number(FITUP_FIRST_COLUMN_KEY)} "
            f"ON: SHEET {SHEET_NAMES.index('ASSEMBLY AND FIT-UP') + 1}",
            steps.SEQUENCE[:first],
            text,
        ),
        (
            _step_column("THE TRANSGEAR", steps.SEQUENCE[first:second], text),
            "\n".join(
                (
                    _step_column(
                        "THE TRANSGEAR, CONTINUED",
                        steps.SEQUENCE[second:chain_start],
                        text,
                    ),
                    "",
                    f"CHAIN FIT-UP: SHEET {SHEET_NAMES.index('CHAIN FIT-UP') + 1}, "
                    f"STEP {steps.step_number(FITUP_CHAIN_KEY)} ON",
                )
            ),
        ),
        (
            _step_column(
                "CHAIN FIT-UP, TRANSGEAR DONE PER SHEET "
                f"{SHEET_NAMES.index('ASSEMBLY AND FIT-UP') + 1}; "
                f"CRANK SIDE DONE PER {steps.CRANK_SIDE_REF}",
                steps.SEQUENCE[chain_start:chain_second],
                text,
            ),
            _step_column(
                "CHAIN FIT-UP, CONTINUED", steps.SEQUENCE[chain_second:], text
            ),
        ),
    )


@dataclass(frozen=True)
class StepNotes:
    """Explicitly formatted note fields, not a module-global qualification."""

    platen_steps: str
    fitup_notes: tuple[str, str]
    chain_notes: tuple[str, str]

    @property
    def fitup_steps(self) -> str:
        """Each sheet's columns read left to right; sheet 5 continues sheet 4."""
        return "\n".join((self.platen_steps, *self.fitup_notes, *self.chain_notes))

    @property
    def exploded_caption_xy(self) -> tuple[float, float]:
        """One blank line under the actual steps, at default 4.5 mm line pitch."""
        return (
            PLATEN_NOTE_XY[0],
            PLATEN_NOTE_XY[1] - (len(self.platen_steps.splitlines()) + 1) * 0.0045,
        )


def format_step_notes(*, operating_domain: RackOperatingDomain) -> StepNotes:
    """Format the sheet steps around a supplied engaged-feed window."""
    return StepNotes(*_step_columns(operating_domain=operating_domain))


def require_step_notes() -> StepNotes:
    """Guard the full paper sweep on the finite rack before printing."""
    return format_step_notes(operating_domain=steps.feed_rack_operating_domain())


# The exploded view's caption at each scale it may take.
EXPLODED_CAPTIONS = {
    scale: f"PLATEN AND SUPPORT EXPLODED {_scale_text(scale)}; "
    f"BOM: SHEET {SHEET_NAMES.index('BILL OF MATERIALS') + 1}"
    for scale in EXPLODED_SCALE_LADDER
}
# Sheet 1, at each scale its isometric may take: which removable is which,
# and where every other item balloons.
ASSEMBLED_CAPTIONS = {
    scale: "\n".join(
        (
            "\n".join(
                textwrap.wrap(
                    f"ISOMETRIC {_scale_text(scale)}: THE "
                    f"{_N['pd-transgear-removable']} ON THE BASE DECK IS THE T18 "
                    f"SPARE, STORED LOOSE; THE {sprocket.KNOB_CONFIG} IS ON THE KNOB, "
                    f"THE {sprocket.CRANK_CONFIG} ON THE "
                    "CRANK. PLATEN AND SUPPORT ITEMS: SHEET "
                    f"{SHEET_NAMES.index('PLATEN AND SUPPORT') + 1}; TRANSGEAR "
                    f"ITEMS: SHEET {SHEET_NAMES.index('TRANSGEAR VIEWS') + 1}.",
                    width=FITUP_LINE_WIDTH,
                )
            ),
            steps.PAPER_FEED_REFERENCE_TEXT,
        )
    )
    for scale in ISO_SCALE_LADDER
}
TRANSGEAR_CAPTION = (
    f"TRANSGEAR {TRANSGEAR_VIEW_SCALE[0]:g}:{TRANSGEAR_VIEW_SCALE[1]:g}; "
    f"ASSEMBLY AND FIT-UP: SHEETS {SHEET_NAMES.index('ASSEMBLY AND FIT-UP') + 1} "
    f"AND {SHEET_NAMES.index('CHAIN FIT-UP') + 1}; "
    f"BOM: SHEET {SHEET_NAMES.index('BILL OF MATERIALS') + 1}"
)
# The inner view's caption at each scale it may take.
INNER_CAPTIONS = {
    scale: f"INNER PARTS, RIGHT SIDE {_scale_text(scale)}"
    for scale in INNER_SCALE_LADDER
}
FITUP_REFERENCE_CAPTION = (
    f"REFERENCE {FITUP_SCALE[0]:g}:{FITUP_SCALE[1]:g}; ITEMS: SHEETS 1 TO "
    f"{SHEET_NAMES.index('PLATEN AND SUPPORT') + 1}"
)


def sheet_texts(notes: StepNotes) -> tuple[str, ...]:
    """Every explicitly formatted package text besides the BOM's own cells."""
    return (
        notes.platen_steps,
        *notes.fitup_notes,
        *notes.chain_notes,
        *EXPLODED_CAPTIONS.values(),
        *ASSEMBLED_CAPTIONS.values(),
        TRANSGEAR_CAPTION,
        *INNER_CAPTIONS.values(),
        FITUP_REFERENCE_CAPTION,
        BOM_REFERENCE_CAPTION,
    )


# ============================ COM helpers =======================================


def _activate_sheet(adapter: Any, name: str) -> None:
    ddoc = _early_bound(adapter.currentModel, "IDrawingDoc")
    if not ddoc.ActivateSheet(name):
        raise RuntimeError(f"failed to activate drawing sheet {name!r}")
    current = _early_bound(ddoc.GetCurrentSheet(), "ISheet")
    if str(current.GetName() or "") != name:
        raise RuntimeError(f"active drawing sheet is not {name!r}")


def _place_sheet_note(
    adapter: Any, sheet_name: str, text: str, xy: tuple[float, float], *, label: str
) -> None:
    """A sheet-owned note: activate the sheet so no view owns it."""
    _activate_sheet(adapter, sheet_name)
    note = add_note(adapter, text, *xy)
    if note is None:
        raise RuntimeError(f"failed to place the paper-drive {label}")
    printed = str(_early_bound(note, "INote").GetText() or "")
    if printed.replace("\r\n", "\n").replace("\r", "\n") != text:
        raise RuntimeError(f"paper-drive {label} printed as {printed!r}")


def _source_family_counts(model: Any) -> Counter[str]:
    """Top-level component count per referenced part file stem."""
    assembly = _early_bound(model, "IAssemblyDoc")
    counts: Counter[str] = Counter()
    for raw in tuple(assembly.GetComponents(True) or ()):
        component = _early_bound(raw, "IComponent2")
        path = str(component.GetPathName() or "")
        if not path:
            raise RuntimeError(f"component {component.Name2!r} has no referenced path")
        counts[Path(path).stem.casefold()] += 1
    if set(counts) != set(BOM_PART_NUMBERS):
        raise RuntimeError(
            f"paper-drive families {sorted(counts)!r} != BOM {sorted(BOM_PART_NUMBERS)!r}"
        )
    wrong = {
        stem: counts[stem]
        for stem, quantity in {**TRANSGEAR_QUANTITIES, **CHAIN_QUANTITIES}.items()
        if counts[stem] != quantity
    }
    if wrong:
        raise RuntimeError(f"paper-drive component counts off the contract: {wrong!r}")
    return counts


def _validate_persisted_explode(model: Any) -> None:
    """The builder authored PAPER_DRIVE_EXPLODED in both drawing configurations."""
    assembly = _early_bound(model, "IAssemblyDoc")
    for configuration in (explode.SOURCE_CONFIGURATION, SIMPLIFIED_VIEW_CONFIGURATION):
        wanted = (exploded_view_name(configuration),)
        names = tuple(assembly.GetExplodedViewNames2(configuration) or ())
        if names != wanted:
            raise RuntimeError(
                f"paper-drive source {configuration} exploded views {names!r} "
                f"!= {wanted!r}"
            )


def _create_sheets(adapter: Any) -> None:
    new_project_drawing(adapter, layout=SPEC.layout, scale=ASSEMBLED_SCALE)
    create_blank_drawing_sheets(adapter, SHEET_NAMES, label="paper-drive package")
    ddoc = _early_bound(adapter.currentModel, "IDrawingDoc")
    for name in SHEET_NAMES:
        _activate_sheet(adapter, name)
        sheet = _early_bound(ddoc.GetCurrentSheet(), "ISheet")
        numerator, denominator = SHEET_SCALES[name]
        if not sheet.SetScale(float(numerator), float(denominator), False, False):
            raise RuntimeError(f"failed to set paper-drive sheet scale: {name}")


def _validate_bom(
    adapter: Any, table: Any, counts: Counter[str]
) -> tuple[tuple[str, str], ...]:
    """Rewrite part numbers, prove identities/quantities; return (stem, item)."""
    table = _early_bound(table, "ITableAnnotation")
    rows = int(table.RowCount)
    columns = int(table.ColumnCount)
    if rows != len(BOM_PART_NUMBERS) + 1 or columns < 4:
        raise RuntimeError(
            f"paper-drive BOM is {rows}x{columns}; expected {len(BOM_PART_NUMBERS) + 1} rows"
        )
    contents = tuple(
        tuple(
            str(table.DisplayedText(row, column) or "").strip()
            for column in range(columns)
        )
        for row in range(rows)
    )
    header = tuple(cell.upper() for cell in contents[0])

    def column_named(predicate: Callable[[str], bool], label: str) -> int:
        matches = [index for index, cell in enumerate(header) if predicate(cell)]
        if len(matches) != 1:
            raise RuntimeError(
                f"paper-drive BOM has no unique {label} column: {header!r}"
            )
        return matches[0]

    item_column = column_named(lambda cell: cell.startswith("ITEM NO"), "ITEM NO.")
    part_column = column_named(lambda cell: cell == "PART NUMBER", "PART NUMBER")
    description_column = column_named(lambda cell: cell == "DESCRIPTION", "DESCRIPTION")
    quantity_column = column_named(lambda cell: cell.startswith("QTY"), "QTY.")
    for column, width in (
        (item_column, BOM_COLUMN_WIDTHS["item"]),
        (part_column, BOM_COLUMN_WIDTHS["part"]),
        (description_column, BOM_COLUMN_WIDTHS["description"]),
        (quantity_column, BOM_COLUMN_WIDTHS["quantity"]),
    ):
        if abs(float(table.SetColumnWidth(column, width, 0)) - width) > 1e-6:
            raise RuntimeError(f"paper-drive BOM column {column} width did not persist")

    actual: dict[str, tuple[int, str, str, str]] = {}
    for row_index, row in enumerate(contents[1:], start=1):
        text = row[part_column].casefold()
        stem = BOM_NORMALIZED_ALIASES.get(text, text)
        if stem in actual:
            raise RuntimeError(f"paper-drive BOM repeats component family {stem!r}")
        actual[stem] = (
            row_index,
            row[item_column],
            row[description_column],
            row[quantity_column],
        )
    if set(actual) != set(BOM_PART_NUMBERS):
        raise RuntimeError(
            f"paper-drive BOM identities {sorted(actual)!r} != {sorted(BOM_PART_NUMBERS)!r}"
        )
    items = {values[1] for values in actual.values()}
    if items != {str(item) for item in range(1, len(BOM_PART_NUMBERS) + 1)}:
        raise RuntimeError(
            f"paper-drive BOM item numbers {sorted(items)!r} are not contiguous"
        )
    for stem, (row_index, _item, description, quantity) in actual.items():
        number = BOM_PART_NUMBERS[stem]
        if contents[row_index][part_column] != number:
            if not table.IsCellTextEditable(row_index, part_column):
                raise RuntimeError(
                    f"paper-drive BOM part-number cell for {stem!r} is locked"
                )
            table.SetText2(row_index, part_column, False, number)
        if description != BOM_DESCRIPTIONS[stem]:
            raise RuntimeError(f"paper-drive BOM description mismatch for {stem!r}")
        if quantity != str(counts[stem]):
            raise RuntimeError(
                f"paper-drive BOM quantity for {stem!r} is {quantity!r}, "
                f"model has {counts[stem]}"
            )
    for row in range(rows):
        table.SetRowHeight(row, BOM_ROW_HEIGHT, 0)
    if not adapter.currentModel.EditRebuild3():
        raise RuntimeError("paper-drive BOM rebuild failed")
    for stem, (row_index, *_rest) in actual.items():
        applied = str(table.DisplayedText(row_index, part_column) or "").strip()
        if applied != BOM_PART_NUMBERS[stem]:
            raise RuntimeError(
                f"paper-drive BOM part number for {stem!r} reads {applied!r}"
            )
    return tuple((stem, actual[stem][1]) for stem in BOM_PART_NUMBERS)


def bom_extent_violations(
    anchor: tuple[float, float], width: float, height: float
) -> list[str]:
    """Contain a measured native piece clear of border, title and reference."""
    template = DRAWING_TEMPLATES[SPEC.layout]
    left, top = anchor
    right, bottom = left + width, top - height
    border = SHEET_INNER_BORDER_BOTTOM + BOM_BORDER_CLEARANCE
    tolerance = 1e-9  # floating-point arithmetic, not a paper-clearance allowance
    findings = []
    if left < border - tolerance or right > template.width_m - border + tolerance:
        findings.append("table crosses the inner side border")
    if top > template.height_m - border + tolerance or bottom < border - tolerance:
        findings.append("table crosses the inner top or bottom border")
    if (
        right > template.title_block_left_m
        and bottom < template.title_block_top_m + BOM_BORDER_CLEARANCE - tolerance
    ):
        findings.append("table enters the title block")
    if left < BOM_ANCHOR[0] + sum(BOM_COLUMN_WIDTHS.values()) and (
        bottom < BOM_REFERENCE_LIMITS[3] + BOM_BORDER_CLEARANCE - tolerance
    ):
        findings.append("table enters the assembly reference field")
    return findings


def bom_split_row(row_heights: Sequence[float], header_count: int) -> int:
    """Choose a horizontal split using every rebuilt row, including headers."""
    if header_count < 1 or len(row_heights) - header_count < 2:
        raise ValueError("paper-drive BOM needs a header and two data rows")
    if any(not math.isfinite(height) or height <= 0 for height in row_heights):
        raise ValueError("paper-drive BOM row heights are unreadable")
    width = sum(BOM_COLUMN_WIDTHS.values())
    header_height = sum(row_heights[:header_count])
    candidates = []
    for split_after in range(header_count, len(row_heights) - 1):
        first_height = sum(row_heights[:split_after + 1])
        second_height = header_height + sum(row_heights[split_after + 1:])
        if not bom_extent_violations(BOM_ANCHOR, width, first_height) and not (
            bom_extent_violations(BOM_SECOND_ANCHOR, width, second_height)
        ):
            candidates.append((abs(first_height - second_height), split_after))
    if not candidates:
        raise RuntimeError(
            "complete paper-drive BOM does not fit its two native fields: "
            f"rebuilt rows {tuple(height * 1000 for height in row_heights)!r} mm"
        )
    return min(candidates)[1]


def _assert_bom_pieces(
    pieces: Sequence[Any], *, header_count: int, total_rows: int
) -> None:
    """Read split ranges and physical extents; every logical data row survives."""
    membership: Counter[int] = Counter()
    findings = []
    for index, raw in enumerate(pieces):
        piece = _early_bound(raw, "ITableAnnotation")
        info = tuple(piece.GetSplitInformation(0, 0, 0, 0))
        if len(info) != 5:
            raise RuntimeError(f"paper-drive BOM split information unreadable: {info!r}")
        direction, _index, count, start, end = (int(value) for value in info)
        if direction != 1 or not (0 <= start <= end < total_rows):
            raise RuntimeError(f"paper-drive BOM split range invalid: {info!r}")
        membership.update(range(max(start, header_count), end + 1))
        rows = sorted({*range(header_count), *range(start, end + 1)})
        height = sum(float(piece.GetRowHeight(row)) for row in rows)
        width = sum(
            float(piece.GetColumnWidth(column))
            for column in range(int(piece.ColumnCount))
        )
        annotation = _early_bound(piece.GetAnnotation(), "IAnnotation")
        position = tuple(float(value) for value in annotation.GetPosition())
        if len(position) != 3:
            raise RuntimeError(f"paper-drive BOM position unreadable: {position!r}")
        violations = bom_extent_violations((position[0], position[1]), width, height)
        expected_anchor = (BOM_ANCHOR, BOM_SECOND_ANCHOR)[index]
        if any(
            abs(position[axis] - expected_anchor[axis]) > 1e-6
            for axis in range(2)
        ):
            violations.append("table moved outside its assigned column")
        if abs(width - sum(BOM_COLUMN_WIDTHS.values())) > 1e-6:
            violations.append("table column widths changed after splitting")
        _telemetry.event(
            "drawing.bom_piece", piece=index + 1, split_count=count, split_range=(start, end),
            anchor_mm=(position[0] * 1000, position[1] * 1000),
            width_mm=width * 1000, height_mm=height * 1000,
            violations=tuple(violations),
        )
        findings.extend(violations)
    if membership != Counter(range(header_count, total_rows)):
        findings.append("split pieces omit or repeat logical data rows")
    if findings:
        raise RuntimeError("paper-drive BOM split: " + "; ".join(findings))


def _split_bom(adapter: Any, table: Any) -> tuple[Any, Any]:
    """Keep one native logical parts list, displayed as two complete pieces."""
    table = _early_bound(table, "ITableAnnotation")
    header_count = int(table.GetHeaderCount())
    total_rows = int(table.RowCount)
    heights = tuple(float(table.GetRowHeight(row)) for row in range(total_rows))
    split_after = bom_split_row(heights, header_count)
    second = table.Split(2, split_after)  # swTableSplit_AfterRow
    if second is None:
        raise RuntimeError(f"paper-drive BOM split after row {split_after} failed")
    second = _early_bound(second, "ITableAnnotation")
    annotation = _early_bound(second.GetAnnotation(), "IAnnotation")
    if not annotation.SetPosition(*BOM_SECOND_ANCHOR, 0.0):
        raise RuntimeError("paper-drive BOM second piece refused its position")
    rebuild_drawing(adapter, label="paper-drive BOM split")
    pieces = (table, second)
    _assert_bom_pieces(pieces, header_count=header_count, total_rows=total_rows)
    return pieces


def _isolate_instances(
    adapter: Any, view: Any, names: frozenset[str], *, label: str
) -> None:
    """Show exactly the named top-level instances in one drawing view.

    The shared ``isolate_drawing_view_components`` works per FAMILY, and the
    removable sprocket's family also holds the crank wheel and spare T18
    on the deck; this isolates per instance, as draw_drive_train_assembly
    does, and reads the visibility back.
    """
    _set_instance_visibility(adapter, view, names, shown=True, label=label)


def _hide_instances(
    adapter: Any, view: Any, names: frozenset[str], *, label: str
) -> None:
    """Hide exactly the named top-level instances; show every other one."""
    _set_instance_visibility(adapter, view, names, shown=False, label=label)


def _set_instance_visibility(
    adapter: Any, view: Any, names: frozenset[str], *, shown: bool, label: str
) -> None:
    """Named instances take ``shown``, the rest the opposite; all must exist."""
    view = _early_bound(view, "IView")
    root = view.RootDrawingComponent2(False)
    if root is None:
        raise RuntimeError(f"{label}: drawing view has no root component")
    root = _early_bound(root, "IDrawingComponent")
    found: set[str] = set()
    for raw in tuple(root.GetChildren() or ()):
        drawing_component = _early_bound(raw, "IDrawingComponent")
        raw_name = str(drawing_component.Name or "")
        name = raw_name.split("@", 1)[0].replace("\\", "/").rsplit("/", 1)[-1]
        named = name in names
        drawing_component.Visible = named == shown
        if named:
            found.add(name)
    rebuild_drawing(adapter, label=f"{label} visibility")
    missing = sorted(names - found)
    if missing:
        raise RuntimeError(f"{label}: instances not in the view: {missing!r}")


def _place_assembled_sheet(adapter: Any) -> Any:
    """Front, right and isometric of the whole drive; returns the isometric,
    centred so its balloon ring keeps inside ISO_RING_LIMITS."""
    _activate_sheet(adapter, SHEET_NAMES[0])
    for orientation, center in (
        ("*Front", FRONT_CENTER),
        ("*Right", RIGHT_CENTER),
        ("*Isometric", ISO_CENTER),
    ):
        view = place_view(
            adapter, str(SOURCE), orientation, *center, scale=ASSEMBLED_SCALE
        )
        # The isometric is the drawing's full-detail view.
        role = ViewRole.FULL_DETAIL if orientation == "*Isometric" else ViewRole.PLAIN
        apply_view_configuration(
            adapter, view, role=role, label=f"paper drive {orientation}"
        )
        if orientation != "*Isometric":
            # Lying flat on the deck, the spare T18 shows edge-on in the
            # front and right views as a bare unlabelled bar; the isometric
            # shows and balloons it (eye pass of PD run 11).
            _hide_instances(
                adapter, view, frozenset({SPARE_INSTANCE}),
                label=f"paper drive {orientation} spare",
            )
    label = "sheet 1 isometric"
    scale, outline = step_down_to_fit(
        _native_outline_at(adapter, view, ASSEMBLED_SCALE, label=label),
        ISO_SCALE_LADDER,
        ISO_RING_LIMITS,
        name=label,
    )
    shift = ring_fit_shift(outline, ISO_RING_LIMITS, name=label)
    _shift_view(adapter, view, shift, label=f"{label} ring fit")
    _place_sheet_note(
        adapter,
        SHEET_NAMES[0],
        ASSEMBLED_CAPTIONS[scale],
        ASSEMBLED_CAPTION_XY,
        label="assembled-views caption",
    )
    return view


def _view_outline(view: Any) -> Box:
    outline = tuple(float(value) for value in _early_bound(view, "IView").GetOutline())
    if len(outline) != 4 or outline[2] <= outline[0] or outline[3] <= outline[1]:
        raise RuntimeError(f"view has an invalid outline {outline!r}")
    return outline


def _shift_view(
    adapter: Any, view: Any, delta: tuple[float, float], *, label: str
) -> None:
    """Move a drawing view by a sheet-space delta and read the move back."""
    view = _early_bound(view, "IView")
    before = tuple(float(value) for value in view.Position)
    target = (before[0] + delta[0], before[1] + delta[1])
    if not view.SetViewPosition(double_array(list(target)), False):
        raise RuntimeError(f"{label}: SetViewPosition refused {target!r}")
    adapter.currentModel.EditRebuild3()
    after = tuple(float(value) for value in view.Position)
    if math.dist(after, target) > 1e-6:
        raise RuntimeError(f"{label}: view moved to {after!r}, expected {target!r}")


def _set_view_scale(
    adapter: Any, view: Any, scale: tuple[float, float], *, label: str
) -> None:
    """Re-scale a placed drawing view and read the scale back."""
    view = _early_bound(view, "IView")
    view.ScaleRatio = double_array([float(scale[0]), float(scale[1])])
    adapter.currentModel.EditRebuild3()
    ratio = tuple(float(value) for value in view.ScaleRatio)
    if len(ratio) != 2 or abs(ratio[0] / ratio[1] - scale[0] / scale[1]) > 1e-9:
        raise RuntimeError(f"{label}: view scale reads {ratio!r}, expected {scale!r}")


def _link_view_to_bom(view: Any, table: Any, *, label: str) -> None:
    """Number ``view``'s balloons from the BOM table inserted on another view."""
    bom = _early_bound(table, "IBomTableAnnotation")
    feature = _early_bound(bom.BomFeature, "IBomFeature")
    name = str(feature.Name or "")
    if not name:
        raise RuntimeError("paper-drive BOM feature has no name")
    view = _early_bound(view, "IView")
    if not view.SetKeepLinkedToBOM(True, name):
        raise RuntimeError(f"{label}: SetKeepLinkedToBOM({name!r}) returned false")
    if (
        not bool(view.GetKeepLinkedToBOM())
        or str(view.GetKeepLinkedToBOMName() or "") != name
    ):
        raise RuntimeError(f"{label}: view is not linked to BOM {name!r}")


def _collar_rim_candidates(view: Any, leaf: Any) -> list[RimCandidate]:
    """Every circular edge the view lists as drawn for the collar ``leaf``,
    read in collar-local mm (the listed-edge fallback's part space)."""
    landing_m = tuple(value / 1000.0 for value in COLLAR_LANDING_MM)
    candidates = []
    for edge in raw_visible_entities(view, leaf.component, _VIEW_ENTITY_EDGE):
        curve = _com_invoke(edge, "IEdge", "GetCurve")
        if curve is None or not _com_invoke(curve, "ICurve", "IsCircle"):
            continue
        params = tuple(
            float(v) for v in (_com_invoke(curve, "ICurve", "CircleParams") or ())
        )
        closest = tuple(
            float(v)
            for v in (_com_invoke(edge, "IEdge", "GetClosestPointOn", *landing_m) or ())
        )
        if len(params) < 7 or len(closest) < 3:
            raise RuntimeError(
                f"{leaf.path}: a listed circle read params {params}, closest point {closest}"
            )
        cx, cy, cz, nx, ny, nz, radius = params[:7]
        candidates.append(
            RimCandidate(
                edge=edge,
                circle=(cx * 1e3, cy * 1e3, cz * 1e3, nx, ny, nz, radius * 1e3),
                closest_mm=(closest[0] * 1e3, closest[1] * 1e3, closest[2] * 1e3),
            )
        )
    return candidates


@_telemetry.traced("drawing.collar_rim_balloon", label_param="label")
def _balloon_collar_on_its_rear_rim(
    adapter: Any, view: Any, *, item: str, label: str
) -> BalloonLanding:
    """The drive collar's balloon on its rear-face rim, selected by entity.

    The rim is checked edge-on, then its leader lands at the landing's y
    along the rim's projected line, and is proven there. The rim is a listed
    edge selected through the view with its landing set: the ``shared-edge``
    path of :func:`_create_component_bom_balloon`.
    """
    leaves = _view_component_leaves(adapter, view, label=label)
    leaf = _shown_instances(
        leaves, COLLAR_STEM, BalloonAnchor(instance=COLLAR_INSTANCE), label=label
    )[0]
    offsets = _view_explode_offsets(adapter, view, label=label)
    minus_end, plus_end, plus_x, minus_x = model_points_in_view(
        adapter,
        view,
        _anchor_model_points(
            adapter,
            leaf,
            tuple(
                tuple(value / 1000.0 for value in point)
                for point in COLLAR_RIM_VIEW_POINTS_MM
            ),
            offsets,
            stem=COLLAR_STEM,
            label=label,
        ),
        label=f"{label} {COLLAR_STEM} rear rim",
        names=("-Y end", "+Y end", "+X point", "-X point"),
    )
    middle = ((minus_end[0] + plus_end[0]) / 2.0, (minus_end[1] + plus_end[1]) / 2.0)
    for side, point in (("+X", plus_x), ("-X", minus_x)):
        if math.dist(point, middle) > _EDGE_ON_TOL_M:
            raise RuntimeError(
                f"{label}: {leaf.path}'s rear rim is not edge-on in the inner view: "
                f"its {side} point projects to {point}, its line's midpoint is {middle}"
            )
    rim = collar_rear_rim(_collar_rim_candidates(view, leaf))
    landing = collar_rim_landing(minus_end, plus_end)
    _telemetry.info(
        f"{label}: {leaf.path} rear rim projects from ({minus_end[0]:.5f}, "
        f"{minus_end[1]:.5f}) at -Y to ({plus_end[0]:.5f}, {plus_end[1]:.5f}) at +Y; "
        f"leader lands at ({landing[0]:.5f}, {landing[1]:.5f}); matched arc "
        "r {6:.4f} at ({0:.4f}, {1:.4f}, {2:.4f}) axis ({3:.3f}, {4:.3f}, {5:.3f})".format(
            *rim.circle
        )
        + ", closest point ({:.4f}, {:.4f}, {:.4f}) mm".format(*rim.closest_mm)
    )
    if not _early_bound(adapter.currentModel, "IDrawingDoc").ActivateView(
        view_name(adapter, view)
    ):
        raise RuntimeError(f"{label}: failed to activate the collar's balloon view")
    return _create_component_bom_balloon(
        adapter,
        view,
        stem=COLLAR_STEM,
        choice=_AnchorChoice(
            instance=leaf.path, edge=rim.edge, method="shared-edge", sheet_xy=landing
        ),
        expected_item=item,
        label=label,
    )


def _place_bom_sheet(
    adapter: Any, counts: Counter[str]
) -> tuple[list[Any], Any, dict[str, str], tuple[Any, Any]]:
    """BOM of the whole drive; the transgear isometric and the inner view
    between them balloon every transgear family once. Returns landings,
    the logical table, its (stem: item) numbers and the two native pieces."""
    _activate_sheet(adapter, SHEET_NAMES[5])
    reference = place_view(
        adapter, str(SOURCE), "*Isometric", *BOM_REFERENCE_CENTER,
        scale=BOM_REFERENCE_SCALE,
    )
    set_high_quality_shaded_with_edges(adapter, reference, label="BOM reference")
    apply_view_configuration(adapter, reference, label="BOM reference")
    outline = _view_outline(reference)
    if not (
        BOM_REFERENCE_LIMITS[0] <= outline[0] < outline[2] <= BOM_REFERENCE_LIMITS[2]
        and BOM_REFERENCE_LIMITS[1] <= outline[1] < outline[3] <= BOM_REFERENCE_LIMITS[3]
    ):
        raise RuntimeError(f"paper-drive BOM reference leaves its field: {outline!r}")
    _place_sheet_note(
        adapter, SHEET_NAMES[5], BOM_REFERENCE_CAPTION, BOM_REFERENCE_CAPTION_XY,
        label="BOM reference caption",
    )
    # Insert the complete model's BOM on its own sheet; view-only isolation
    # on sheet 2 cannot alter this reference or the logical parts list.
    table = insert_bom_table(
        adapter,
        reference,
        anchor_xy=BOM_ANCHOR,
        expected_components=tuple(BOM_PART_NUMBERS),
        descriptions=BOM_DESCRIPTIONS,
        identity_aliases={number: stem for stem, number in BOM_PART_NUMBERS.items()},
        configuration_grouping="same-part",
        label="paper-drive",
    )
    items = dict(_validate_bom(adapter, table, counts))
    _activate_sheet(adapter, SHEET_NAMES[1])
    label = "transgear isometric"
    view = place_view(
        adapter, str(SOURCE), "*Isometric", *TRANSGEAR_VIEW_CENTER,
        scale=TRANSGEAR_VIEW_SCALE,
    )
    set_high_quality_shaded_with_edges(adapter, view, label=label)
    apply_view_configuration(adapter, view, label=label)
    _link_view_to_bom(view, table, label=label)
    _isolate_instances(adapter, view, TRANSGEAR_INSTANCES, label=label)
    inner_label = "transgear inner view"
    placed = INNER_SCALE_LADDER[0]
    inner = place_view(
        adapter,
        str(SOURCE),
        INNER_VIEW_ORIENTATION,
        *INNER_VIEW_START,
        scale=placed,
    )
    set_high_quality_shaded_with_edges(adapter, inner, label=inner_label)
    apply_view_configuration(adapter, inner, label=inner_label)
    _isolate_instances(adapter, inner, INNER_INSTANCES, label=inner_label)
    _link_view_to_bom(inner, table, label=inner_label)
    if dict(_validate_bom(adapter, table, counts)) != items:
        raise RuntimeError(
            "paper-drive BOM items moved when the transgear views were isolated"
        )
    _activate_sheet(adapter, SHEET_NAMES[5])
    pieces = _split_bom(adapter, table)
    _activate_sheet(adapter, SHEET_NAMES[1])
    # Both rings fit before any balloon exists. The isometric is centred in
    # the field's height, then the inner view is fitted beside it. Every
    # ladder scale keeps the configuration just applied.
    _shift_view(
        adapter, view, transgear_view_shift(_view_outline(view)), label=f"{label} ring fit"
    )
    iso_outline = _view_outline(view)
    scale = inner_view_scale(iso_outline, _view_outline(inner), placed)
    if scale != placed:
        _set_view_scale(adapter, inner, scale, label=inner_label)
    # The ladder predicted the fit; the re-read outline is the proof.
    shift = inner_view_shift(iso_outline, _view_outline(inner))
    _shift_view(adapter, inner, shift, label=f"{inner_label} ring fit")
    iso_items, inner_items = transgear_balloon_items(items)
    landings = add_component_bom_balloons(
        adapter,
        view,
        items=iso_items,
        anchors=TRANSGEAR_BALLOON_ANCHORS,
        label="paper-drive transgear BOM coverage",
        margin=BALLOON_MARGIN,
    )
    # The collar balloons after the batch, so its balloon cannot cover a
    # point the batch hit-tests; then all of the view's balloons re-ring.
    balloons_label = "paper-drive transgear inner BOM coverage"
    inner_landings = add_component_bom_balloons(
        adapter,
        inner,
        items=tuple(pair for pair in inner_items if pair[0] != COLLAR_STEM),
        anchors=TRANSGEAR_BALLOON_ANCHORS,
        label=balloons_label,
        margin=BALLOON_MARGIN,
    )
    inner_landings.append(
        _balloon_collar_on_its_rear_rim(
            adapter, inner, item=dict(inner_items)[COLLAR_STEM], label=balloons_label
        )
    )
    _spread_balloons(
        adapter,
        inner,
        [landing.note for landing in inner_landings],
        margin=BALLOON_MARGIN,
    )
    rebuild_drawing(adapter, label=f"{balloons_label} ring")
    _uncross_ring(adapter, inner_landings, label=balloons_label)
    landings += inner_landings
    _place_sheet_note(
        adapter,
        SHEET_NAMES[1],
        TRANSGEAR_CAPTION,
        TRANSGEAR_CAPTION_XY,
        label="transgear caption",
    )
    inner_outline = _view_outline(inner)
    _place_sheet_note(
        adapter,
        SHEET_NAMES[1],
        INNER_CAPTIONS[scale],
        (
            inner_outline[0] - BALLOON_RING_REACH,
            inner_outline[1] - BALLOON_RING_REACH - INNER_CAPTION_GAP,
        ),
        label="inner-parts caption",
    )
    return landings, table, items, pieces


def _balloon_assembled_sheet(
    adapter: Any, iso: Any, table: Any, items: dict[str, str]
) -> list[Any]:
    """The chain and the spare T18 on sheet 1's isometric."""
    _activate_sheet(adapter, SHEET_NAMES[0])
    _link_view_to_bom(iso, table, label="sheet 1 isometric")
    return add_component_bom_balloons(
        adapter,
        iso,
        items=assembled_balloon_items(items),
        anchors=ASSEMBLED_BALLOON_ANCHORS,
        label="paper-drive sheet 1 BOM coverage",
        margin=BALLOON_MARGIN,
    )


def _place_exploded_sheet(
    adapter: Any, table: Any, items: dict[str, str], notes: StepNotes,
) -> list[Any]:
    """The builder's PAPER_DRIVE_EXPLODED, only the platen-and-support
    families shown, each ballooned once; their steps left of it."""
    _activate_sheet(adapter, SHEET_NAMES[2])
    label = "platen and support exploded"
    view = place_view(
        adapter, str(SOURCE), "*Isometric", *EXPLODED_CENTER, scale=EXPLODED_SCALE
    )
    set_high_quality_shaded_with_edges(adapter, view, label=label)
    configuration = apply_view_configuration(adapter, view, label=label)
    set_view_exploded_state(
        adapter, view, True, configuration=configuration, label=label
    )
    isolate_drawing_view_components(
        adapter, view, visible_stems=explode.SHOWN_STEMS, label=label
    )
    scale, outline = step_down_to_fit(
        _native_outline_at(adapter, view, EXPLODED_SCALE, label=label),
        EXPLODED_SCALE_LADDER,
        EXPLODED_RING_LIMITS,
        name=label,
    )
    shift = ring_fit_shift(outline, EXPLODED_RING_LIMITS, name=label)
    _shift_view(adapter, view, shift, label=f"{label} ring fit")
    _link_view_to_bom(view, table, label=label)
    landings = add_component_bom_balloons(
        adapter,
        view,
        items=platen_balloon_items(items),
        anchors=PLATEN_BALLOON_ANCHORS,
        label="paper-drive platen BOM coverage",
        margin=BALLOON_MARGIN,
    )
    _place_sheet_note(
        adapter, SHEET_NAMES[2], notes.platen_steps, PLATEN_NOTE_XY, label="platen steps"
    )
    _place_sheet_note(
        adapter,
        SHEET_NAMES[2],
        EXPLODED_CAPTIONS[scale],
        notes.exploded_caption_xy,
        label="exploded-view caption",
    )
    return landings


def _place_fitup_sheets(adapter: Any, step_notes: StepNotes) -> None:
    for sheet_name, notes in (
        (SHEET_NAMES[3], step_notes.fitup_notes),
        (SHEET_NAMES[4], step_notes.chain_notes),
    ):
        _activate_sheet(adapter, sheet_name)
        view = place_view(
            adapter, str(SOURCE), "*Isometric", *FITUP_REFERENCE_CENTER, scale=FITUP_SCALE
        )
        apply_view_configuration(
            adapter, view, label=f"{sheet_name} reference isometric"
        )
        _place_sheet_note(
            adapter,
            sheet_name,
            FITUP_REFERENCE_CAPTION,
            (FITUP_REFERENCE_CENTER[0] - 0.040, FITUP_NOTE_LIMITS[0][1] - 0.002),
            label=f"{sheet_name} reference caption",
        )
        for index, (text, xy) in enumerate(zip(notes, FITUP_NOTE_XY, strict=True)):
            _place_sheet_note(
                adapter, sheet_name, text, xy, label=f"{sheet_name} note {index + 1}"
            )


@_telemetry.traced("drawing.paper_drive_assembly")
async def build(adapter: Any) -> dict[str, str]:
    notes = require_step_notes()
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source assembly is missing: {SOURCE}")

    check("open assembly drawing source", await adapter.open_model(str(SOURCE)))
    properties = read_required_properties(
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
            "Revision",
            "Material Specification",
            "Finish",
            "Quantity",
        ),
    )
    if properties["Number"] != steps.DRAWING_NUMBER:
        raise RuntimeError(
            f"paper-drive source is {properties['Number']!r}, steps name "
            f"{steps.DRAWING_NUMBER!r}"
        )
    counts = _source_family_counts(adapter.currentModel)
    _validate_persisted_explode(adapter.currentModel)
    _create_sheets(adapter)
    iso = _place_assembled_sheet(adapter)
    landings, table, items, pieces = _place_bom_sheet(adapter, counts)
    landings += _balloon_assembled_sheet(adapter, iso, table, items)
    landings += _place_exploded_sheet(adapter, table, items, notes)
    _place_fitup_sheets(adapter, notes)
    assert_full_detail_view(adapter, label="paper-drive assembly")

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        layout=SPEC.layout,
        pdf_title="Paper-Drive Assembly Drawing",
        scale=ASSEMBLED_SCALE,
        expected_sheet_names=SHEET_NAMES,
        sheet_layouts=SHEET_LAYOUTS,
        sheet_scales=SHEET_SCALES,
        settled_checks=(
            lambda: assert_balloon_landings(adapter, landings),
            lambda: _assert_bom_pieces(
                pieces, header_count=int(table.GetHeaderCount()),
                total_rows=len(BOM_PART_NUMBERS) + 1,
            ),
        ),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[ARTIFACT_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
