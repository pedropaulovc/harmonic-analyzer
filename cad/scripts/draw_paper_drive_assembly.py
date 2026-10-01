r"""Create the three-sheet paper-drive assembly drawing (MHA-A06).

Sheet 1 keeps the Front/Right/Isometric views of the whole paper drive.
Sheet 2 carries the bill of materials, a ballooned isometric of the
transgear (the hanger, the latch, the disc cluster and the knob stack) and a
ballooned right view of the parts that isometric hides. Sheet 3 prints the
transgear's assembly steps and the chain fit-up (CONTRACT-paper-drive.md
§13.2), numbered by ``paper_drive_assembly_steps``; every value comes from
the spec that owns it, or from that module for the values only the procedure
owns.
"""

from __future__ import annotations

import argparse
import math
import sys
import textwrap
from collections import Counter
from pathlib import Path
from typing import Any, Callable

import _config
import _telemetry
import latch_hook_bracket_geometry as bracket_geometry
import latch_hook_geometry as hook_geometry
import paper_drive_assembly_steps as steps
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
from _drawing_common import (
    SIMPLIFIED_VIEW_CONFIGURATION,
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

SHEET_NAMES = ("ASSEMBLED VIEWS", "BILL OF MATERIALS", "ASSEMBLY AND FIT-UP")
if SPEC.layout is not DrawingLayout.LANDSCAPE:
    raise AssertionError("the paper-drive sheet coordinates are landscape")
SHEET_LAYOUTS = {name: DrawingLayout.LANDSCAPE for name in SHEET_NAMES}

# --- sheet 1: the whole paper drive (the pre-round-10 three-view layout) -----
ASSEMBLED_SCALE = (1.0, 5.0)
FRONT_CENTER = (0.080, 0.150)
RIGHT_CENTER = (0.200, 0.150)
ISO_CENTER = (0.320, 0.145)

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

# --- sheet 3: the steps in two columns, a small reference view ---------------
FITUP_SCALE = (1.0, 10.0)
FITUP_REFERENCE_CENTER = (0.100, 0.045)
FITUP_LINE_WIDTH = 68  # characters; default-format note text
# Each note's top-left corner, then its right limit and lowest y: the left
# column stops above the reference view; the right column stops above the
# MHA-177 collar's own fit-up note, which stops above the title block (top
# 0.066).
FITUP_NOTE_XY = ((0.018, 0.262), (0.215, 0.262), (0.215, 0.150))
FITUP_NOTE_LIMITS = ((0.210, 0.075), (0.418, 0.152), (0.418, 0.072))
# The chain fit-up (§13.2) opens the second column.
FITUP_SECOND_COLUMN_KEY = "fitup-pose-set"

SHEET_SCALES = {
    SHEET_NAMES[0]: ASSEMBLED_SCALE,
    SHEET_NAMES[1]: TRANSGEAR_VIEW_SCALE,
    SHEET_NAMES[2]: FITUP_SCALE,
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
# * the feed-pinion sleeve: its 12T (z -144.4 to -134.9) is behind the Ø81.5
#   disc, its spigot (to -157.5) inside the hub shank and under the hub cap;
# * the drive collar (Ø17.5, z -154.3 to -150.3) behind the Ø51.2 T24 (2.8
#   thick): its deepest rim point's ray leaves the T24 at radius
#   8.75 + (4.0 + 2.8) * sqrt(2) = 18.4 < 25.6; its spring pin lies in its
#   rear slot and its drive pins in its and the T24's holes;
# * the knob shaft: only its 0.7 mm stud tip stands past the thumbnut, and
#   its 12T and threads are past the edge fallback too;
# * the knob screw inside the knob cup, the arm-plate screws' heads on the
#   plate's rear face, the latch pin in the arm behind the latch bracket.
# From the right, with only these shown, each has at least half its surface
# in view (the knob stack at x -43.8 overlaps the sleeve at x 0 only below
# y 265.6, the sleeve reaching 272.1; the spring pin's end shows down its
# slot; the drive pins stand 2.4 proud of the collar, above and below it).
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


Box = tuple[float, float, float, float]


def _grown(box: Box, by: float) -> Box:
    return (box[0] - by, box[1] - by, box[2] + by, box[3] + by)


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
        "latch-pin-pressed": (
            f"PRESS THE {_N['transgear-latch-pin']} DOWEL INTO THE "
            f"{_N['transgear-arm']} ARM'S REAMED HOLE TO THE HOLE FLOOR, "
            f"{pin_lo:.2f} TO {pin_hi:.2f} PROUD."
        ),
        "stud-fitted": (
            f"SCREW THE {_N['transgear-stub']} STUD'S {stub.REAR_THREAD_CALLOUT} END "
            "INTO THE ARM'S STUD TAP UNTIL ITS COLLAR SEATS ON THE ARM'S FRONT FACE."
        ),
        "arm-plate-fitted": (
            f"FIT THE {_N['transgear-arm-plate']} PLATE TO THE ARM WITH "
            f"{TRANSGEAR_QUANTITIES['transgear-arm-plate-screw']} "
            f"{_N['transgear-arm-plate-screw']} SCREWS IN THE ARM'S THROUGH TAPS."
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
        "oil-hole-drilled": (
            f"DRILL THE \u00d8{hub.OIL_HOLE_DIA:.1f} OIL HOLE THROUGH HUB AND "
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
            f"SCREW THE {_N['latch-hook-bracket']} BRACKET TO THE BAR'S TAPS WITH "
            f"{TRANSGEAR_QUANTITIES['latch-hook-bracket-screw']} "
            f"{_N['latch-hook-bracket-screw']} SCREWS."
        ),
        "hook-set-and-riveted": (
            f"LATCH THE HANGER. SET THE {_N['latch-hook']} HOOK ON THE BRACKET "
            f"FLAP SO THE {_N['transgear-latch-pin']} PIN ENTERS ITS HOLE "
            "WITHOUT TOUCHING; CLAMP IT. DRILL THE FLAP THROUGH THE HOOK'S "
            f"{TRANSGEAR_QUANTITIES['latch-hook-rivet']} RIVET HOLES (SEE "
            f"{_N['latch-hook-bracket']}); SET "
            f"{TRANSGEAR_QUANTITIES['latch-hook-rivet']} "
            f"{_N['latch-hook-rivet']} RIVETS."
        ),
        "fitup-pose-set": (
            "HANGER LATCHED. PULL THE CRANK SHAFT FORWARD AND THE ARM FORWARD "
            f"AGAINST THE SPACER; PUSH THE KNOB SHAFT REARWARD ({teeth} ON THE "
            f"RING, RING ON THE HUB). SLIDE THE COLLAR BACK AGAINST THE {teeth}; "
            "T24 AND THUMBNUT ON FINGER-TIGHT."
        ),
        "collar-gap-measured": (
            "MEASURE d, THE T24 FRONT FACE BEHIND THE T12 FRONT FACE (STRAIGHT "
            "EDGE, OR DEPTH GAUGE THROUGH THE CHAIN WINDOW). COLLAR GAP "
            f"g = d + {collar.FIT_UP_OFFSET_TARGET:.2f} SETS THE T24 "
            f"{collar.FIT_UP_OFFSET_SET_TEXT} FORWARD "
            f"OF THE T12. IF g EXCEEDS {COLLAR_GAP_MAX:.2f}, STOP AND REPORT. IF "
            f"g IS 0 OR LESS, LEAVE THE COLLAR ON THE {teeth} (g = 0) AND "
            "RECORD d."
        ),
        "collar-pinned": (
            f"THUMBNUT AND T24 OFF. SLOTTED SHIM g BETWEEN COLLAR AND {teeth}; "
            f"CLAMP THE COLLAR WITH A \u00d8{steps.CLAMP_SLEEVE_OD:.1f}/"
            f"\u00d8{steps.CLAMP_SLEEVE_ID:.1f} SLEEVE OVER THE STUD ON THE PILOT "
            f"FACE, TIGHTENED BY THE THUMBNUT. {collar.CROSS_PIN_DRILL_PHRASE}; "
            "FIT THE "
            f"{_N['transgear-collar-cross-pin']} SPRING PIN IN THE SLOT. SLEEVE "
            "AND SHIM OUT; T24 ON WITH THE CHAIN LOOPED OVER IT AND THE T12; "
            "THUMBNUT TIGHT."
        ),
        "stud-end-cut": (
            f"IF THE {_N['transgear-knob-shaft']} STUD END STANDS PROUD OF THE "
            f"THUMBNUT RIM, {collar.STUD_CUT_PHRASE}."
        ),
        "fitup-accepted": (
            f"ACCEPT, IN THE POSE OF STEP {steps.step_number('fitup-pose-set')}: "
            f"T24 FRONT FACE {steps.OFFSET_ACCEPT_TEXT} FORWARD OF THE T12 FRONT FACE; "
            f"KNOB END FLOAT {knob_lo:.2f} TO {knob_hi:.2f}; PIVOT HEAD PLAY "
            f"{joints.HEAD_PLAY_MIN:.2f} TO {joints.HEAD_PLAY_MAX:.2f}, THE "
            "HANGER SWINGING FREELY; COLLAR TO DISC AIR "
            f"{steps.COLLAR_DISC_AIR_TEXT}. OTHERWISE REPORT."
        ),
    }


def _fitup_columns() -> tuple[str, str]:
    text = _step_text()
    if set(text) != set(steps.SEQUENCE):
        raise AssertionError("paper-drive step text must cover exactly the sequence")
    split = steps.step_number(FITUP_SECOND_COLUMN_KEY) - 1
    headings = (
        "TRANSGEAR ASSEMBLY",
        "CHAIN FIT-UP, CRANK SIDE COMPLETE PER " + " AND ".join(steps.CRANK_SIDE_REFS),
    )
    columns = []
    for heading, keys in zip(
        headings, (steps.SEQUENCE[:split], steps.SEQUENCE[split:]), strict=True
    ):
        lines = textwrap.wrap(heading, width=FITUP_LINE_WIDTH)
        for key in keys:
            lines += textwrap.wrap(
                text[key],
                width=FITUP_LINE_WIDTH,
                initial_indent=f"{steps.step_number(key)}. ",
                subsequent_indent="   ",
            )
        columns.append("\n".join(lines))
    return columns[0], columns[1]


FITUP_COLUMNS = _fitup_columns()
FITUP_STEPS = "\n".join(FITUP_COLUMNS)
# The collar sheet leaves its fit-up instruction to this assembly (policy
# rule 6); it prints verbatim under the chain fit-up.
FITUP_COLLAR_NOTE = f"{_N['transgear-drive-collar']} COLLAR\n{collar.FIT_UP_NOTE}"
FITUP_NOTES = (*FITUP_COLUMNS, FITUP_COLLAR_NOTE)
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
    f"REFERENCE {FITUP_SCALE[0]:g}:{FITUP_SCALE[1]:g}; ITEMS: SHEET "
    f"{SHEET_NAMES.index('BILL OF MATERIALS') + 1}"
)
# Every text the package prints besides the BOM's own cells.
SHEET_TEXTS = (
    *FITUP_NOTES,
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


def _place_assembled_sheet(adapter: Any) -> None:
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


def _place_bom_sheet(adapter: Any, counts: Counter[str]) -> list[Any]:
    """BOM of the whole drive; the transgear isometric and the inner view
    between them balloon every transgear family once."""
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
    return landings


def _place_fitup_sheet(adapter: Any) -> None:
    _activate_sheet(adapter, SHEET_NAMES[2])
    view = place_view(
        adapter, str(SOURCE), "*Isometric", *FITUP_REFERENCE_CENTER, scale=FITUP_SCALE
    )
    apply_view_configuration(adapter, view, label="fit-up reference isometric")
    for index, (text, xy) in enumerate(zip(FITUP_NOTES, FITUP_NOTE_XY, strict=True)):
        _place_sheet_note(
            adapter, SHEET_NAMES[2], text, xy, label=f"fit-up note {index + 1}"
        )
    _place_sheet_note(
        adapter,
        SHEET_NAMES[2],
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
    _create_sheets(adapter)
    _place_assembled_sheet(adapter)
    landings = _place_bom_sheet(adapter, counts)
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
