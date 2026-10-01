r"""Create the four-sheet paper-drive assembly drawing (MHA-A06).

Sheet 1 keeps the Front/Right/Isometric views of the whole paper drive and
balloons the chain and the spare sprocket on the isometric. Sheet 2 carries
the bill of materials, a ballooned isometric of the transgear (the hanger,
the latch, the disc cluster and the knob stack) and a ballooned right view of
the parts that isometric hides. Sheet 3 balloons the bar, its clamps and the
platen group on the builder's exploded isometric (PAPER_DRIVE_EXPLODED) and
prints their steps. Sheet 4 prints the transgear's assembly steps and the
chain fit-up (CONTRACT-paper-drive.md §13.2). Every step is numbered by
``paper_drive_assembly_steps``; every value comes from the spec that owns it,
or from that module for the values only the procedure owns.
"""

from __future__ import annotations

import argparse
import math
import sys
import textwrap
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Iterable

import _chain as chain
import _config
import _telemetry
import latch_hook_bracket_geometry as bracket_geometry
import latch_hook_geometry as hook_geometry
import paper_drive_assembly_steps as steps
import paper_drive_explode_spec as explode
import platen_guide_spec as platen_guide
import platen_spec as platen
import transgear_arm_geometry as arm_geometry
import transgear_arm_plate_geometry as plate_geometry
import transgear_arm_plate_screw_spec as plate_screw
import transgear_disc_hub_geometry as hub_geometry
import transgear_disc_hub_spec as hub
import transgear_disc_screw_spec as disc_screw
import transgear_drive_collar_spec as collar
import transgear_feed_pinion_spec as sleeve
import transgear_hanger_joints as joints
import transgear_knob_drive_pin_spec as drive_pin
import transgear_knob_retaining_screw_spec as retaining_screw
import transgear_knob_shaft_spec as knob_shaft
import transgear_knob_thrust_ring_spec as thrust_ring
import transgear_pivot_screw_spec as pivot_screw
import transgear_removable_spec as sprocket
import transgear_stub_spec as stub
from _common import _early_bound, check, run_build
from _paper_drive_explode import exploded_view_name
from _drawing_common import (
    SIMPLIFIED_VIEW_CONFIGURATION,
    isolate_drawing_view_components,
    set_view_exploded_state,
    BalloonAnchor,
    DrawingOutputs,
    ViewRole,
    _SW_SHADED_EDGES,
    add_component_bom_balloons,
    apply_view_configuration,
    assert_balloon_landings,
    assert_full_detail_view,
    create_blank_drawing_sheets,
    finalize_drawing,
    insert_bom_table,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    set_high_quality_shaded_with_edges,
    view_configuration,
)
from _drawing_registry import DRAWINGS_BY_NAME, DrawingLayout
from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import add_note, place_view


SPEC = DRAWINGS_BY_NAME["paper_drive_assembly"]
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
    "BILL OF MATERIALS",
    "PLATEN AND SUPPORT",
    "ASSEMBLY AND FIT-UP",
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

# --- sheet 2: BOM left, ballooned transgear isometric right ------------------
# The drive-train BOM's column widths and row height (MHA-A03), on the same
# template: its 118 mm description column held 41 characters on one line.
BOM_COLUMN_WIDTHS = {
    "item": 0.012,
    "part": 0.022,
    "description": 0.118,
    "quantity": 0.012,
}
BOM_DESCRIPTION_MAX_CHARS = 41
BOM_ROW_HEIGHT = 0.006
BOM_ANCHOR = (0.018, 0.262)
# The transgear alone at 2:3, right of the inner view's ring and above the
# title block. Native run 20261001T062924323Z read its outline at x 295.3 to
# 404.8 mm centred at x 355; here it spans 286.3 to 395.8, its ring 269.3 to
# 412.8, 2.2 mm inside the 415 limit (inner_view_shift).
TRANSGEAR_VIEW_SCALE = (2.0, 3.0)
TRANSGEAR_VIEW_CENTER = (0.346, 0.170)
BALLOON_MARGIN = 0.012
TRANSGEAR_CAPTION_XY = (0.222, 0.082)
# The parts the isometric hides, seen from the machine's right (camera at -X:
# sheet x is machine +Z, sheet y is +Y) with every other part hidden in that
# view only. The largest ladder scale whose ring fits beside the isometric's
# (inner_view_scale): the same run read the view 57.3 mm wide at 2:3, a 91.3
# mm ring in the 76.3 mm left of the isometric's ring at x 355; at 1:2 it is
# about 43.0 wide, a 77.0 ring in the 80.3 left here. Every ladder scale is
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
# Sheet-2 balloon rings: left of them the BOM's right edge plus the clearance
# the drive-train BOM keeps (MHA-A03), right the drive-train ring region's
# right edge on the same template, top the BOM's top, bottom over the
# transgear caption. _spread_balloons puts each circle CENTRE BALLOON_MARGIN
# outside its view, so the ink reaches one 10 mm balloon's radius further.
BOM_RIGHT = BOM_ANCHOR[0] + sum(BOM_COLUMN_WIDTHS.values())
SHEET_TWO_RING_LIMITS = (BOM_RIGHT + 0.003, 0.090, 0.415, BOM_ANCHOR[1])
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

# --- sheet 4: the steps in two columns, a small reference view ---------------
FITUP_SCALE = (1.0, 10.0)
FITUP_REFERENCE_CENTER = (0.100, 0.045)
FITUP_LINE_WIDTH = 68  # characters; default-format note text
# Each column's top-left corner, then its right limit and lowest y: the left
# column stops above the reference view; the right column stops above the
# title block (top 0.066).
FITUP_NOTE_XY = ((0.018, 0.262), (0.215, 0.262))
FITUP_NOTE_LIMITS = ((0.210, 0.075), (0.418, 0.072))
# The platen's locks open sheet 4; the hook step, then the chain fit-up (§13.2)
# under its own heading, fill its second column.
FITUP_FIRST_COLUMN_KEY = "guide-locks-set"
FITUP_SECOND_COLUMN_KEY = "hook-set-and-riveted"
FITUP_CHAIN_KEY = "fitup-pose-set"

SHEET_SCALES = {
    SHEET_NAMES[0]: ASSEMBLED_SCALE,
    SHEET_NAMES[1]: TRANSGEAR_VIEW_SCALE,
    SHEET_NAMES[2]: EXPLODED_SCALE,
    SHEET_NAMES[3]: FITUP_SCALE,
}

# --- BOM identities ------------------------------------------------------------
# Literal stems, so the config-dependency analysis reads exactly these rows.
BOM_PART_NUMBERS = {
    "support-bar": _config.parts("support-bar")["number"],
    "column-clamp-front": _config.parts("column-clamp-front")["number"],
    "column-clamp-back": _config.parts("column-clamp-back")["number"],
    "clamp-screw": _config.parts("clamp-screw")["number"],
    "platen": _config.parts("platen")["number"],
    "platen-rack": _config.parts("platen-rack")["number"],
    "platen-guide": _config.parts("platen-guide")["number"],
    "guide-lock": _config.parts("guide-lock")["number"],
    "platen-clip": _config.parts("platen-clip")["number"],
    "platen-paper": _config.parts("platen-paper")["number"],
    "fillister-screw": _config.parts("fillister-screw")["number"],
    "guide-lock-screw": _config.parts("guide-lock-screw")["number"],
    "chain-inner-link": _config.parts("chain-inner-link")["number"],
    "chain-outer-link": _config.parts("chain-outer-link")["number"],
    "transgear-removable": _config.parts("transgear-removable")["number"],
    "transgear-arm": _config.parts("transgear-arm")["number"],
    "transgear-arm-plate": _config.parts("transgear-arm-plate")["number"],
    "transgear-arm-plate-screw": _config.parts("transgear-arm-plate-screw")["number"],
    "transgear-pivot-spacer": _config.parts("transgear-pivot-spacer")["number"],
    "transgear-pivot-screw": _config.parts("transgear-pivot-screw")["number"],
    "transgear-latch-pin": _config.parts("transgear-latch-pin")["number"],
    "latch-hook-bracket": _config.parts("latch-hook-bracket")["number"],
    "latch-hook-bracket-screw": _config.parts("latch-hook-bracket-screw")["number"],
    "latch-hook": _config.parts("latch-hook")["number"],
    "latch-hook-rivet": _config.parts("latch-hook-rivet")["number"],
    "transgear-stub": _config.parts("transgear-stub")["number"],
    "transgear-stud-shim": _config.parts("transgear-stud-shim")["number"],
    "transgear-feed-pinion": _config.parts("transgear-feed-pinion")["number"],
    "transgear-disc-hub": _config.parts("transgear-disc-hub")["number"],
    "transgear-hub-cap": _config.parts("transgear-hub-cap")["number"],
    "rack-pinion": _config.parts("rack-pinion")["number"],
    "transgear-disc-screw": _config.parts("transgear-disc-screw")["number"],
    "transgear-knob-shaft": _config.parts("transgear-knob-shaft")["number"],
    "transgear-drive-collar": _config.parts("transgear-drive-collar")["number"],
    "transgear-collar-cross-pin": _config.parts("transgear-collar-cross-pin")["number"],
    "transgear-knob-drive-pin": _config.parts("transgear-knob-drive-pin")["number"],
    "transgear-thumbnut": _config.parts("transgear-thumbnut")["number"],
    "transgear-knob-thrust-ring": _config.parts("transgear-knob-thrust-ring")["number"],
    "transgear-knob-cup": _config.parts("transgear-knob-cup")["number"],
    "transgear-knob-retaining-screw": _config.parts("transgear-knob-retaining-screw")[
        "number"
    ],
}
# A purchased part's registry SKU, printed in its description.
_SKU = {
    "clamp-screw": _config.parts("clamp-screw")["supplier_skus"][0],
    "fillister-screw": _config.parts("fillister-screw")["supplier_skus"][0],
    "guide-lock-screw": _config.parts("guide-lock-screw")["supplier_skus"][0],
    "transgear-arm-plate-screw": _config.parts("transgear-arm-plate-screw")[
        "supplier_skus"
    ][0],
    "transgear-pivot-screw": _config.parts("transgear-pivot-screw")["supplier_skus"][0],
    "transgear-latch-pin": _config.parts("transgear-latch-pin")["supplier_skus"][0],
    "latch-hook-bracket-screw": _config.parts("latch-hook-bracket-screw")[
        "supplier_skus"
    ][0],
    "latch-hook-rivet": _config.parts("latch-hook-rivet")["supplier_skus"][0],
    "transgear-disc-screw": _config.parts("transgear-disc-screw")["supplier_skus"][0],
    "transgear-collar-cross-pin": _config.parts("transgear-collar-cross-pin")[
        "supplier_skus"
    ][0],
    "transgear-knob-drive-pin": _config.parts("transgear-knob-drive-pin")[
        "supplier_skus"
    ][0],
    "transgear-knob-retaining-screw": _config.parts("transgear-knob-retaining-screw")[
        "supplier_skus"
    ][0],
}
# The description column is drawing wording; a purchased part names its SKU.
BOM_DESCRIPTIONS = {
    "support-bar": "PAPER-DRIVE SUPPORT BAR",
    "column-clamp-front": "COLUMN CLAMP, FRONT",
    "column-clamp-back": "COLUMN CLAMP, BACK",
    "clamp-screw": f"FILLISTER SCREW, MCMASTER {_SKU['clamp-screw']}",
    "platen": "PLATEN",
    "platen-rack": "PLATEN RACK",
    "platen-guide": "PLATEN GUIDE",
    "guide-lock": "PLATEN GUIDE LOCK",
    "platen-clip": "PLATEN PAPER CLIP",
    "platen-paper": "PLATEN PAPER",
    "fillister-screw": f"BRASS FILLISTER SCREW, MCMASTER {_SKU['fillister-screw']}",
    "guide-lock-screw": f"BUTTON HEAD SCREW, MCMASTER {_SKU['guide-lock-screw']}",
    "chain-inner-link": "#25 CHAIN INNER LINK",
    "chain-outer-link": "#25 CHAIN OUTER LINK",
    # Grouped: its configurations' BOM description wins over a written cell,
    # so the row prints the registry description the builder stamps.
    "transgear-removable": str(_config.parts("transgear-removable")["description"]),
    "transgear-arm": "TRANSGEAR ARM",
    "transgear-arm-plate": "TRANSGEAR ARM PLATE",
    "transgear-arm-plate-screw": (
        f"{plate_screw.THREAD} OVAL HEAD SCREW, MCMASTER "
        f"{_SKU['transgear-arm-plate-screw']}"
    ),
    "transgear-pivot-spacer": "TRANSGEAR PIVOT SPACER",
    "transgear-pivot-screw": (
        f"{pivot_screw.THREAD} SHOULDER SCREW, MCMASTER {_SKU['transgear-pivot-screw']}"
    ),
    "transgear-latch-pin": f"DOWEL PIN, MCMASTER {_SKU['transgear-latch-pin']}",
    "latch-hook-bracket": "LATCH HOOK BRACKET",
    "latch-hook-bracket-screw": (
        f"FILLISTER SCREW, MCMASTER {_SKU['latch-hook-bracket-screw']}"
    ),
    "latch-hook": "LATCH HOOK",
    "latch-hook-rivet": f"DOMED SOLID RIVET, MCMASTER {_SKU['latch-hook-rivet']}",
    "transgear-stub": "TRANSGEAR STUD",
    "transgear-stud-shim": "TRANSGEAR STUD SHIM",
    "transgear-feed-pinion": "TRANSGEAR FEED PINION SLEEVE",
    "transgear-disc-hub": "TRANSGEAR DISC HUB",
    "transgear-hub-cap": "TRANSGEAR HUB CAP NUT",
    "rack-pinion": "TRANSGEAR DISC, 120T",
    "transgear-disc-screw": (
        f"{disc_screw.THREAD} FILLISTER SCREW, MCMASTER {_SKU['transgear-disc-screw']}"
    ),
    "transgear-knob-shaft": "TRANSGEAR KNOB SHAFT",
    "transgear-drive-collar": "KNOB DRIVE COLLAR",
    "transgear-collar-cross-pin": (
        f"SPRING PIN, MCMASTER {_SKU['transgear-collar-cross-pin']}"
    ),
    "transgear-knob-drive-pin": f"DOWEL PIN, MCMASTER {_SKU['transgear-knob-drive-pin']}",
    "transgear-thumbnut": "TRANSGEAR THUMBNUT",
    "transgear-knob-thrust-ring": "KNOB THRUST RING",
    "transgear-knob-cup": "KNOB CUP",
    "transgear-knob-retaining-screw": (
        f"{retaining_screw.THREAD} PAN HEAD SCREW, MCMASTER "
        f"{_SKU['transgear-knob-retaining-screw']}"
    ),
}
if set(BOM_DESCRIPTIONS) != set(BOM_PART_NUMBERS):
    raise AssertionError("paper-drive BOM description coverage is incomplete")
# The registry's grouped-row description is the builder's to stamp and may
# wrap; every written description keeps to one line.
GROUPED_DESCRIPTION_STEMS = frozenset({"transgear-removable"})
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
# balloons exactly these. The removable sprocket is the knob's T24 (instance
# 1); the crank's T12 and the spare T18 stay on sheet 1.
TRANSGEAR_QUANTITIES = {
    "transgear-arm": 1,
    "transgear-arm-plate": 1,
    "transgear-arm-plate-screw": len(arm_geometry.PLATE_TAP_STATIONS),
    "transgear-pivot-spacer": 1,
    "transgear-pivot-screw": 1,
    "transgear-latch-pin": 1,
    "latch-hook-bracket": 1,
    "latch-hook-bracket-screw": len(bracket_geometry.SCREW_HOLE_X),
    "latch-hook": 1,
    "latch-hook-rivet": len(hook_geometry.RIVET_YZ),
    "transgear-stub": 1,
    "transgear-stud-shim": 1,
    "transgear-feed-pinion": 1,
    "transgear-disc-hub": 1,
    "transgear-hub-cap": 1,
    "rack-pinion": 1,
    "transgear-disc-screw": hub_geometry.SCREW_COUNT,
    "transgear-knob-shaft": 1,
    "transgear-drive-collar": 1,
    "transgear-collar-cross-pin": 1,
    "transgear-knob-drive-pin": len(sprocket.PIN_HOLE_ANGLES_DEG),
    "transgear-removable": len(sprocket.CONFIGS),
    "transgear-thumbnut": 1,
    "transgear-knob-thrust-ring": 1,
    "transgear-knob-cup": 1,
    "transgear-knob-retaining-screw": 1,
}
if not set(TRANSGEAR_QUANTITIES) <= set(BOM_PART_NUMBERS):
    raise AssertionError("every transgear family is a BOM row")
TRANSGEAR_INSTANCES = frozenset(
    f"{stem}-{index}"
    for stem, count in TRANSGEAR_QUANTITIES.items()
    for index in range(1, (1 if stem == "transgear-removable" else count) + 1)
)
TRANSGEAR_BALLOON_ANCHORS = {
    stem: BalloonAnchor(instance="transgear-removable-1")
    if stem == "transgear-removable"
    else BalloonAnchor()
    for stem in TRANSGEAR_QUANTITIES
}
# The families the isometric draws no reachable ink of (farm run
# 20261001T051043622Z: none of the sleeve's 12 extreme points hit its ink, and
# its 268 gear edges are past the edge fallback's 128), ballooned on the inner
# view instead. Viewed along (-1, +1, -1), the camera at the machine's
# front-left-top:
# * the feed-pinion sleeve: its 12T (z -144.65 to -135.15) is behind the Ø81.5
#   disc, its spigot (to -157.75) inside the hub shank and under the hub cap;
# * the drive collar (Ø17.5, z -154.3 to -150.3) behind the Ø51.2 T24 (2.8
#   thick): its deepest rim point's ray leaves the T24 at radius
#   8.75 + (4.0 + 2.8) * sqrt(2) = 18.4 < 25.6; its spring pin lies in its
#   rear slot and its drive pins in its and the T24's holes;
# * the knob shaft: only its 0.7 mm stud tip stands past the thumbnut, and
#   its 12T and threads are past the edge fallback too;
# * the knob screw inside the knob cup, the arm-plate screws' heads on the
#   plate's rear face, the latch pin in the arm behind the latch bracket;
# * the stud's shim (Ø12, z -127.45 to -124.4) behind the Ø81.5 disc: its
#   rear rim's ray leaves the disc's rear face at radius
#   6 + (144.65 - 124.4) * sqrt(2) = 34.6 < 40.75.
# From the right, with only these shown, each has at least half its surface
# in view (the knob stack at x -43.8 overlaps the sleeve at x 0 only below
# y 265.6, the sleeve reaching 272.1; the spring pin's end shows down its
# slot; the drive pins stand 2.4 proud of the collar, above and below it; the
# shim at x 0 shares no z with the sleeve, and the latch pin nearer the
# eye at x 43.5 stands at y 238.4, under the shim's 260.2).
INNER_STEMS = frozenset(
    {
        "transgear-feed-pinion",
        "transgear-knob-shaft",
        "transgear-drive-collar",
        "transgear-collar-cross-pin",
        "transgear-knob-drive-pin",
        "transgear-knob-retaining-screw",
        "transgear-arm-plate-screw",
        "transgear-latch-pin",
        "transgear-stud-shim",
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


# Sheet 1's isometric balloons what sheets 2 and 3 do not show: the chain,
# and the spare T18 on the base deck (the third removable inserted), whose
# item sheet 2 balloons on the knob's T24.
ASSEMBLED_BALLOON_ANCHORS = {
    "chain-inner-link": BalloonAnchor(),
    "chain-outer-link": BalloonAnchor(),
    "transgear-removable": BalloonAnchor(instance="transgear-removable-3"),
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
    ("transgear-thumbnut", "THUMBNUT"),
    ("transgear-removable", "T24"),
    ("transgear-drive-collar", "COLLAR"),
    ("transgear-knob-shaft", f"SHAFT {KNOB_TEETH}T"),
    ("transgear-knob-thrust-ring", "RING"),
    (None, "PLATE HUB"),
    ("transgear-arm-plate", "PLATE"),
    (None, "REAR BOSS"),
    ("transgear-knob-cup", "CUP"),
    ("transgear-knob-retaining-screw", "SCREW"),
)
# The knob's end float: the shaft journal against the ring and the plate's
# hub-to-boss, each at its own printed band (R9-17: 0.2 nominal).
_KNOB_FLOAT_BAND = (
    knob_shaft.JOURNAL_LENGTH_TOL
    + thrust_ring.LENGTH_TOL
    + plate_geometry.HUB_TO_BOSS_BAND
)
KNOB_END_FLOAT_RANGE = (
    knob_shaft.END_FLOAT - _KNOB_FLOAT_BAND,
    knob_shaft.END_FLOAT + _KNOB_FLOAT_BAND,
)
# §13.2 procedure (4): past this gap the T24 seat would pass the collar's
# SEAT_MAX_FROM_F in front of the 12T front face.
COLLAR_GAP_MAX = collar.SEAT_MAX_FROM_F - collar.LENGTH
# The platen's screw stations (platen_spec): its front counterbores take the
# guide screws, its through-taps the clip screws.
GUIDE_SCREWS = len(platen.GUIDE_HOLE_X) * len(platen.GUIDE_HOLE_Y)
CLIP_SCREWS = len(platen.SOCKET_XY)


def _stack_text() -> str:
    return ", ".join(
        f"{_N[stem]} {label}" if stem else label for stem, label in KNOB_STACK
    )


def _step_text() -> dict[str, str]:
    pin_lo, pin_hi = joints.LATCH_PIN_PROUD_RANGE
    float_lo, float_hi = sleeve.CLUSTER_FLOAT_RANGE
    drive_lo, drive_hi = drive_pin.PROUD_RANGE
    knob_lo, knob_hi = KNOB_END_FLOAT_RANGE
    teeth = f"{KNOB_TEETH}T"
    return {
        "bar-clamped": (
            f"CLAMP THE {_N['support-bar']} BAR TO BOTH COLUMNS, EACH BETWEEN A "
            f"{_N['column-clamp-front']} FRONT AND A {_N['column-clamp-back']} BACK "
            f"ARC, WITH THE {_N['clamp-screw']} SCREWS FROM THE BAR FRONT. SET "
            f"THE BAR TOP {steps.BAR_TOP_ABOVE_DECK:.1f} ABOVE THE BASE DECK AT "
            "BOTH COLUMNS; TIGHTEN."
        ),
        "rack-soldered": (
            f"SOFT-SOLDER THE {_N['platen-rack']} RACK TO THE {_N['platen']} "
            "PLATEN'S BACK, TEETH DOWN, ENDS FLUSH WITH THE PLATEN'S, CRESTS "
            f"{steps.RACK_CREST_TEXT} BELOW "
            "ITS BOTTOM EDGE."
        ),
        "guides-screwed": (
            f"SCREW THE {len(platen.GUIDE_HOLE_Y)} {_N['platen-guide']} GUIDES TO "
            f"THE PLATEN BACK WITH {GUIDE_SCREWS} {_N['fillister-screw']} SCREWS "
            "FROM THE FRONT, HEADS IN THE COUNTERBORES."
        ),
        "clips-fitted": (
            f"SCREW THE {_N['platen-clip']} CLIPS TO THE PLATEN FRONT WITH "
            f"{CLIP_SCREWS} {_N['fillister-screw']} SCREWS; SLIP THE "
            f"{_N['platen-paper']} PAPER UNDER THEIR SPRING RAILS."
        ),
        "platen-hung": (
            "HANG THE PLATEN ON THE BAR, THE TOP GUIDE ON THE BAR TOP. FIT THE "
            f"{_N['guide-lock']} LOCKS TO THE GUIDE BACKS BEHIND THE BAR WITH "
            f"THEIR {_N['guide-lock-screw']} SCREWS, LOOSE."
        ),
        "guide-locks-set": (
            f"SNUG EACH {_N['guide-lock']} LOCK'S {_N['guide-lock-screw']} SCREWS, "
            "PUSH THE LOCK AT ITS MIDDLE AWAY FROM THE BAR TILL ITS HOLES BEAR ON "
            "THEM; TIGHTEN."
        ),
        "lock-seats-faced": (
            f"FACE LOCK SEATS TO {platen_guide.LOCK_GAP_FIT_TEXT} PLATEN FLOAT; "
            "ELSE STOP AND REPORT."
        ),
        "latch-pin-pressed": (
            f"PRESS THE {_N['transgear-latch-pin']} DOWEL INTO THE "
            f"{_N['transgear-arm']} ARM'S REAMED HOLE TO THE HOLE FLOOR, "
            f"{pin_lo:.2f} TO {pin_hi:.2f} PROUD."
        ),
        "stud-fitted": (
            f"SCREW THE {_N['transgear-stub']} STUD'S {stub.REAR_THREAD_CALLOUT} END "
            f"THROUGH THE {_N['transgear-stud-shim']} SHIM INTO THE ARM'S STUD TAP "
            "TILL THE SHIM SEATS ON THE ARM."
        ),
        "arm-plate-fitted": (
            f"FIT THE {_N['transgear-arm-plate']} PLATE TO THE ARM WITH "
            f"{TRANSGEAR_QUANTITIES['transgear-arm-plate-screw']} "
            f"{_N['transgear-arm-plate-screw']} SCREWS IN THE ARM'S THROUGH TAPS; "
            "SNUG BOTH, THEN TIGHTEN THEM IN TURN."
        ),
        "arm-plate-screws-cut": (
            f"CUT BOTH {_N['transgear-arm-plate-screw']} TIPS FLUSH TO "
            f"{joints.PLATE_SCREW_CUT_PROUD_MAX:.2f} PROUD OF THE ARM'S FRONT "
            f"FACE; BREAK THE CUT EDGE {plate_screw.CUT_END_BREAK_TEXT}."
        ),
        "hanger-pivoted": (
            f"HANG THE ARM ON THE {_N['support-bar']} BAR: THE "
            f"{_N['transgear-pivot-spacer']} SPACER AS MADE BETWEEN BAR AND ARM, "
            f"THE {_N['transgear-pivot-screw']} SHOULDER SCREW FROM THE REAR "
            "THROUGH ARM AND SPACER INTO THE BAR'S BLIND TAP WITH LOW-STRENGTH "
            "THREADLOCKER. SEAT IT; THE ARM SWINGS FREELY."
        ),
        "disc-cluster-pressed": (
            f"SLIDE THE {_N['rack-pinion']} DISC ON THE "
            f"{_N['transgear-feed-pinion']} SLEEVE'S SPIGOT AGAINST ITS PINION; "
            f"PRESS THE {_N['transgear-disc-hub']} HUB ON THE SHANK UNTIL ITS "
            "FLANGE CLAMPS THE DISC."
        ),
        "disc-taps-transferred": (
            f"SPOT-DRILL THE DISC THROUGH THE {hub_geometry.SCREW_COUNT} FLANGE "
            f"HOLES, THEN DRILL AND TAP {disc_screw.THREAD}; MATCH-MARK DISC AND "
            f"FLANGE. FIX WITH {hub_geometry.SCREW_COUNT} "
            f"{_N['transgear-disc-screw']} SCREWS."
        ),
        "disc-screws-cut": (
            f"CUT {_N['transgear-disc-screw']} TIPS "
            f"{disc_screw.TIP_BELOW_REAR_FACE_TEXT} BELOW DISC REAR FACE; "
            f"BREAK {disc_screw.CUT_END_BREAK_TEXT}."
        ),
        "oil-hole-drilled": (
            f"DRILL THE \u00d8{hub.OIL_HOLE_DIA:.1f} OIL HOLE CENTRED ON THE HUB BODY, "
            "THROUGH HUB AND "
            f"SLEEVE IN ONE OPERATION AS {_N['transgear-disc-hub']} SHOWS; "
            "DEBURR THE BORE."
        ),
        "disc-cluster-hung": (
            "OIL THE STUD JOURNAL; SLIDE THE CLUSTER ON, PINION REARWARD. RUN "
            f"THE {_N['transgear-hub-cap']} CAP ON THE {stub.FRONT_THREAD_CALLOUT} "
            "THREAD UNTIL IT SEATS ON THE JOURNAL SHOULDER. ACCEPT: CLUSTER END "
            f"FLOAT {float_lo:.2f} TO {float_hi:.2f}; THE CLUSTER SPINS FREELY."
        ),
        "collar-pins-pressed": (
            f"PRESS {TRANSGEAR_QUANTITIES['transgear-knob-drive-pin']} "
            f"{_N['transgear-knob-drive-pin']} PINS INTO THE "
            f"{_N['transgear-drive-collar']} COLLAR TO A STOP, {drive_lo:.2f} TO "
            f"{drive_hi:.2f} PROUD OF ITS FRONT FACE."
        ),
        "knob-stack-fitted": (
            f"KNOB STACK, FRONT TO REAR: {_stack_text()}. PASS THE SHAFT "
            "THROUGH THE LOOSE RING INTO THE PLATE BORE FROM THE FRONT; CLAMP "
            "THE CUP ON THE SHAFT'S END FACE WITH THE SCREW. SLIDE THE COLLAR "
            "ON THE CORE UNPINNED, PINS FORWARD."
        ),
        "latch-bracket-fitted": (
            f"SCREW THE {_N['latch-hook-bracket']} BRACKET TO THE BAR WITH "
            f"{TRANSGEAR_QUANTITIES['latch-hook-bracket-screw']} "
            f"{_N['latch-hook-bracket-screw']} SCREWS."
        ),
        "hanger-meshed": (
            f"SWING THE HANGER UP TILL THE {_N['transgear-feed-pinion']} TEETH "
            f"ENTER THE {_N['platen-rack']} RACK. KNOB HELD, SET "
            f"{steps.MESH_BACKLASH_TEXT} PLATEN SHAKE ALONG THE RACK (DIAL ON ITS "
            "EDGE); CLAMP THE ARM TO THE BAR. RUN THE FULL TRAVEL: NO TIGHT SPOT, "
            "SHAKE AT EVERY TOOTH."
        ),
        "hook-set-and-riveted": (
            f"HOLDING THAT MESH, SET THE {_N['latch-hook']} HOOK ON THE BRACKET "
            f"FLAP, THE {_N['transgear-latch-pin']} PIN CLEAR IN ITS HOLE (HOOK "
            f"OVER {steps.HOOK_SET_TEXT} OFF ITS DRAWN PLACE: STOP AND REPORT); "
            "CLAMP. DRILL THE FLAP THROUGH ITS "
            f"{TRANSGEAR_QUANTITIES['latch-hook-rivet']} RIVET HOLES (SEE "
            f"{_N['latch-hook-bracket']}); SET "
            f"{TRANSGEAR_QUANTITIES['latch-hook-rivet']} "
            f"{_N['latch-hook-rivet']} RIVETS. UNCLAMP, LATCH, RE-RUN THE TRAVEL."
        ),
        "fitup-pose-set": (
            "HANGER LATCHED. PULL THE CRANK SHAFT FORWARD AND THE ARM FORWARD "
            f"AGAINST THE SPACER; PUSH THE KNOB SHAFT REARWARD ({teeth} ON THE "
            f"RING, RING ON THE HUB). SLIDE THE COLLAR BACK AGAINST THE {teeth}; "
            "T24 AND THUMBNUT ON FINGER-TIGHT."
        ),
        "stud-faced-to-fit": (
            "CLUSTER FORWARD, FEEL THE COLLAR TO DISC AIR. FACE THE "
            f"{_N['transgear-stud-shim']} SHIM TILL IT IS "
            f"{stub.STUD_FIT_WINDOW_TEXT}; ELSE STOP AND REPORT."
        ),
        "collar-gap-measured": (
            "MEASURE d, THE T24 FRONT FACE BEHIND THE T12 FRONT FACE (STRAIGHT "
            "EDGE, OR DEPTH GAUGE THROUGH THE CHAIN WINDOW). COLLAR GAP "
            f"g = d + {collar.FIT_UP_OFFSET_TARGET:.2f} SETS THE T24 "
            f"{collar.FIT_UP_OFFSET_SET_TEXT} FORWARD "
            f"OF THE T12, THE SETTING STEP {steps.step_number('fitup-accepted')} "
            f"RE-CHECKS. IF g EXCEEDS {COLLAR_GAP_MAX:.2f} (T24 SEAT "
            f"{steps.T24_SEAT_MAX_TEXT} IN FRONT OF THE {teeth} FRONT FACE), "
            f"STOP AND REPORT. IF g IS 0 OR LESS, LEAVE THE COLLAR ON THE {teeth} "
            f"(COLLAR-TO-{teeth} GAP {steps.COLLAR_GAP_MIN_TEXT}) AND RECORD d."
        ),
        "collar-pinned": (
            f"THUMBNUT AND T24 OFF. SLOTTED SHIM g BETWEEN COLLAR AND {teeth}; "
            f"CLAMP THE COLLAR WITH A \u00d8{steps.CLAMP_SLEEVE_OD:.1f}/"
            f"\u00d8{steps.CLAMP_SLEEVE_ID:.1f} SLEEVE OVER THE STUD ON THE PILOT "
            f"FACE, TIGHTENED BY THE THUMBNUT. {collar.CROSS_PIN_DRILL_PHRASE}; "
            "FIT THE "
            f"{_N['transgear-collar-cross-pin']} SPRING PIN IN THE SLOT. SLEEVE "
            "AND SHIM OUT; T24 ON, THUMBNUT TIGHT."
        ),
        "stud-end-cut": (
            f"IF THE {_N['transgear-knob-shaft']} STUD END STANDS PROUD OF THE "
            f"THUMBNUT RIM, {collar.STUD_CUT_PHRASE}."
        ),
        "fitup-accepted": (
            f"ACCEPT, IN THE POSE OF STEP {steps.step_number('fitup-pose-set')}: "
            f"T24 FRONT FACE {steps.OFFSET_ACCEPT_TEXT} FORWARD OF THE T12 FRONT FACE "
            f"(STEP {steps.step_number('collar-gap-measured')}'S SETTING, WIDENED "
            "FOR PINNING AND GAUGE SPREAD: THE T24 UP TO "
            f"{steps.OFFSET_ACCEPT_TOL - collar.FIT_UP_OFFSET_TARGET:.2f} BEHIND "
            f"PASSES); KNOB END FLOAT {knob_lo:.2f} TO {knob_hi:.2f}; PIVOT HEAD PLAY "
            f"{joints.HEAD_PLAY_MIN:.2f} TO {joints.HEAD_PLAY_MAX:.2f}, THE "
            "HANGER SWINGING FREELY; COLLAR TO DISC AIR "
            f"{steps.COLLAR_DISC_AIR_TEXT}. OTHERWISE REPORT."
        ),
        "chain-closed": (
            f"LOOP {chain.LINK_COUNT} PITCHES OF #25 CHAIN, "
            f"{_N['chain-inner-link']} INNER AND {_N['chain-outer-link']} OUTER "
            "LINKS, OVER THE T24 AND THE T12; JOIN THE ENDS WITH A #25 "
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
    lines = textwrap.wrap(heading, width=FITUP_LINE_WIDTH)
    for key in keys:
        lines += textwrap.wrap(
            text[key],
            width=FITUP_LINE_WIDTH,
            initial_indent=f"{steps.step_number(key)}. ",
            subsequent_indent="   ",
        )
    return "\n".join(lines)


def _step_columns() -> tuple[str, str, str]:
    """Sheet 3's platen-and-support steps, then sheet 4's two columns."""
    text = _step_text()
    if set(text) != set(steps.SEQUENCE):
        raise AssertionError("paper-drive step text must cover exactly the sequence")
    first = steps.step_number(FITUP_FIRST_COLUMN_KEY) - 1
    second = steps.step_number(FITUP_SECOND_COLUMN_KEY) - 1
    chain_start = steps.step_number(FITUP_CHAIN_KEY) - 1
    return (
        _step_column(
            f"PLATEN AND SUPPORT; STEP {steps.step_number(FITUP_FIRST_COLUMN_KEY)} "
            f"ON: SHEET {SHEET_NAMES.index('ASSEMBLY AND FIT-UP') + 1}",
            steps.SEQUENCE[:first],
            text,
        ),
        _step_column(
            "PLATEN LOCKS, THEN THE TRANSGEAR", steps.SEQUENCE[first:second], text
        ),
        "\n".join(
            (
                _step_column("", steps.SEQUENCE[second:chain_start], text),
                _step_column(
                    f"CHAIN FIT-UP, CRANK SIDE DONE PER {steps.CRANK_SIDE_REF}",
                    steps.SEQUENCE[chain_start:],
                    text,
                ),
            )
        ),
    )


PLATEN_STEPS, *_FITUP = _step_columns()
# Sheet 4's two columns, left to right.
FITUP_COLUMNS: tuple[str, str] = (_FITUP[0], _FITUP[1])
FITUP_STEPS = "\n".join((PLATEN_STEPS, *FITUP_COLUMNS))
FITUP_NOTES = FITUP_COLUMNS
# The exploded view's caption at each scale it may take.
EXPLODED_CAPTIONS = {
    scale: f"PLATEN AND SUPPORT EXPLODED {_scale_text(scale)}; "
    f"BOM: SHEET {SHEET_NAMES.index('BILL OF MATERIALS') + 1}"
    for scale in EXPLODED_SCALE_LADDER
}
# One blank line under the steps (default note text, 4.5 mm line pitch).
EXPLODED_CAPTION_XY = (
    PLATEN_NOTE_XY[0],
    PLATEN_NOTE_XY[1] - (len(PLATEN_STEPS.splitlines()) + 1) * 0.0045,
)
# Sheet 1, at each scale its isometric may take: which removable is which,
# and where every other item balloons.
ASSEMBLED_CAPTIONS = {
    scale: "\n".join(
        textwrap.wrap(
            f"ISOMETRIC {_scale_text(scale)}: THE {_N['transgear-removable']} ON "
            "THE BASE DECK IS THE T18 SPARE, STORED LOOSE; THE T24 IS ON THE "
            "KNOB, THE T12 ON THE CRANK. PLATEN AND SUPPORT ITEMS: SHEET "
            f"{SHEET_NAMES.index('PLATEN AND SUPPORT') + 1}; TRANSGEAR ITEMS: SHEET "
            f"{SHEET_NAMES.index('BILL OF MATERIALS') + 1}.",
            width=FITUP_LINE_WIDTH,
        )
    )
    for scale in ISO_SCALE_LADDER
}
TRANSGEAR_CAPTION = (
    f"TRANSGEAR {TRANSGEAR_VIEW_SCALE[0]:g}:{TRANSGEAR_VIEW_SCALE[1]:g}; "
    f"ASSEMBLY AND FIT-UP: SHEET {SHEET_NAMES.index('ASSEMBLY AND FIT-UP') + 1}"
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
# Every text the package prints besides the BOM's own cells.
SHEET_TEXTS = (
    PLATEN_STEPS,
    *FITUP_NOTES,
    *EXPLODED_CAPTIONS.values(),
    *ASSEMBLED_CAPTIONS.values(),
    TRANSGEAR_CAPTION,
    *INNER_CAPTIONS.values(),
    FITUP_REFERENCE_CAPTION,
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
        for stem, quantity in TRANSGEAR_QUANTITIES.items()
        if counts[stem] != quantity
    }
    if wrong:
        raise RuntimeError(f"paper-drive transgear counts off the contract: {wrong!r}")
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
    for row in range(rows):
        table.SetRowHeight(row, BOM_ROW_HEIGHT, 0)

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
    if not adapter.currentModel.EditRebuild3():
        raise RuntimeError("paper-drive BOM rebuild failed")
    for stem, (row_index, *_rest) in actual.items():
        applied = str(table.DisplayedText(row_index, part_column) or "").strip()
        if applied != BOM_PART_NUMBERS[stem]:
            raise RuntimeError(
                f"paper-drive BOM part number for {stem!r} reads {applied!r}"
            )
    return tuple((stem, actual[stem][1]) for stem in BOM_PART_NUMBERS)


def _isolate_instances(
    adapter: Any, view: Any, names: frozenset[str], *, label: str
) -> None:
    """Show exactly the named top-level instances in one drawing view.

    The shared ``isolate_drawing_view_components`` works per FAMILY, and the
    removable sprocket's family also holds the crank's T12 and the spare T18
    on the deck; this isolates per instance, as draw_drive_train_assembly
    does, and reads the visibility back.
    """
    view = _early_bound(view, "IView")
    root = view.RootDrawingComponent2(False)
    if root is None:
        raise RuntimeError(f"{label}: drawing view has no root component")
    root = _early_bound(root, "IDrawingComponent")
    shown: set[str] = set()
    for raw in tuple(root.GetChildren() or ()):
        drawing_component = _early_bound(raw, "IDrawingComponent")
        raw_name = str(drawing_component.Name or "")
        name = raw_name.split("@", 1)[0].replace("\\", "/").rsplit("/", 1)[-1]
        visible = name in names
        drawing_component.Visible = visible
        if visible:
            shown.add(name)
    rebuild_drawing(adapter, label=f"{label} isolation")
    missing = sorted(names - shown)
    if missing:
        raise RuntimeError(f"{label}: instances not in the view: {missing!r}")


def _place_assembled_sheet(adapter: Any) -> Any:
    """Front, right and isometric of the whole drive; returns the isometric,
    centred so its balloon ring keeps inside ISO_RING_LIMITS."""
    _activate_sheet(adapter, SHEET_NAMES[0])
    for view_name, center in (
        ("*Front", FRONT_CENTER),
        ("*Right", RIGHT_CENTER),
        ("*Isometric", ISO_CENTER),
    ):
        view = place_view(
            adapter, str(SOURCE), view_name, *center, scale=ASSEMBLED_SCALE
        )
        # The isometric is the drawing's full-detail view.
        role = ViewRole.FULL_DETAIL if view_name == "*Isometric" else ViewRole.PLAIN
        apply_view_configuration(
            adapter, view, role=role, label=f"paper drive {view_name}"
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


def _place_bom_sheet(
    adapter: Any, counts: Counter[str]
) -> tuple[list[Any], Any, dict[str, str]]:
    """BOM of the whole drive; the transgear isometric and the inner view
    between them balloon every transgear family once. Returns the landings,
    the BOM table and its (stem: item) numbers."""
    _activate_sheet(adapter, SHEET_NAMES[1])
    label = "transgear isometric"
    view = place_view(
        adapter,
        str(SOURCE),
        "*Isometric",
        *TRANSGEAR_VIEW_CENTER,
        scale=TRANSGEAR_VIEW_SCALE,
    )
    set_high_quality_shaded_with_edges(adapter, view, label=label)
    apply_view_configuration(adapter, view, label=label)
    # The BOM binds while every component shows; the isolation below only
    # hides components in this view, and the second read proves the rows held.
    table = insert_bom_table(
        adapter,
        view,
        anchor_xy=BOM_ANCHOR,
        expected_components=tuple(BOM_PART_NUMBERS),
        descriptions=BOM_DESCRIPTIONS,
        identity_aliases={number: stem for stem, number in BOM_PART_NUMBERS.items()},
        configuration_grouping="same-part",
        label="paper-drive",
    )
    items = dict(_validate_bom(adapter, table, counts))
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
    # Both rings fit before any balloon exists; only the inner view moves,
    # the BOM's own view stays where the table was inserted. Every ladder
    # scale keeps the configuration just applied (INNER_SCALE_LADDER).
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
    landings += add_component_bom_balloons(
        adapter,
        inner,
        items=inner_items,
        anchors=TRANSGEAR_BALLOON_ANCHORS,
        label="paper-drive transgear inner BOM coverage",
        margin=BALLOON_MARGIN,
    )
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
    return landings, table, items


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


def _place_exploded_sheet(adapter: Any, table: Any, items: dict[str, str]) -> list[Any]:
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
        adapter, SHEET_NAMES[2], PLATEN_STEPS, PLATEN_NOTE_XY, label="platen steps"
    )
    _place_sheet_note(
        adapter,
        SHEET_NAMES[2],
        EXPLODED_CAPTIONS[scale],
        EXPLODED_CAPTION_XY,
        label="exploded-view caption",
    )
    return landings


def _place_fitup_sheet(adapter: Any) -> None:
    _activate_sheet(adapter, SHEET_NAMES[3])
    view = place_view(
        adapter, str(SOURCE), "*Isometric", *FITUP_REFERENCE_CENTER, scale=FITUP_SCALE
    )
    apply_view_configuration(adapter, view, label="fit-up reference isometric")
    for index, (text, xy) in enumerate(zip(FITUP_NOTES, FITUP_NOTE_XY, strict=True)):
        _place_sheet_note(
            adapter, SHEET_NAMES[3], text, xy, label=f"fit-up note {index + 1}"
        )
    _place_sheet_note(
        adapter,
        SHEET_NAMES[3],
        FITUP_REFERENCE_CAPTION,
        (FITUP_REFERENCE_CENTER[0] - 0.040, FITUP_NOTE_LIMITS[0][1] - 0.002),
        label="fit-up reference caption",
    )


@_telemetry.traced("drawing.paper_drive_assembly")
async def build(adapter: Any) -> dict[str, str]:
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
    landings, table, items = _place_bom_sheet(adapter, counts)
    landings += _balloon_assembled_sheet(adapter, iso, table, items)
    landings += _place_exploded_sheet(adapter, table, items)
    _place_fitup_sheet(adapter)
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
        settled_checks=(lambda: assert_balloon_landings(adapter, landings),),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[ARTIFACT_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
