r"""Create the six-sheet oblique-trammel jig fitter package (MHA-CH-006-TL-000).

Sheet 1 shows the jig assembled at the symmetric inner pass in the machine
frame: the plan (camera down Z) above the operator's elevation, each titled,
the plan tagging the carrier's pass holes A1-B2, both rails and the spindle
origin, beside the pose caption and the rail-alignment targets the fitter
indicates the pivot pins to. Sheet 2 is the BOM: every family TL-20 to TL-49
from the part registry, made and bought, numbered in the spec's BOM order
with its full description and total quantity, one line a row, beside its
parent view, the jig collapsed. Sheets 3 to 5 each show the builder-owned
``JIG_EXPLODED`` presentation with one sub-assembly's families only (rail
bars, leadscrew feed, carrier), at the largest scale whose balloon ring fits
the sheet, each family ballooned once on one ring, on no other sheet. Sheet 6
is the assembly order, whose steps cite the fasteners by item number, in two
columns, the checks, and the finished isometric. Every view is one the
builder named in the machine frame (``spec.VIEW_AXES``), its mapping proven
on the sheet before anything is placed by it. Every text,
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
from _com import _early_bound
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
    add_component_bom_balloons,
    assert_balloon_landings,
    isolate_drawing_view_components,
)
from _drawing_layout_check import LeaderSegment, find_leader_leader_crossings
from _drawing_tables import insert_bom_table
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
from _drawing_projection import model_points_in_view
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME, DrawingLayout
from _simplified_names import simplified_name
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


# All 29 families on one exploded view at 1:10 read as a crowd whose leaders
# converged and crossed, and the small screws could not be told apart (blind
# review r4). So each sub-assembly explodes on its own sheet: what stands on
# the table and rides its rails, the feed bolted along rail 1 and onto pivot
# block 1, and what rides the pins. Each family is shown and ballooned in
# exactly one, in BOM order. Each placed scale is the ladder scale the offline
# layout test fits its estimated ring to.
CLUSTERS = (
    Cluster(
        "RAIL BARS EXPLODED",
        "BASE BARS, RAILS, CARRIAGES AND PIVOT BLOCKS",
        (
            spec.BASE_BAR,
            spec.PIVOT_BLOCK,
            spec.PIVOT_PIN,
            spec.RAIL,
            spec.CARRIAGE,
            spec.BEARING,
            spec.HOLD_DOWN_STUD,
            spec.T_NUT,
            spec.FLANGE_NUT,
            spec.RAIL_SCREW,
            spec.CARRIAGE_SCREW,
        ),
        (1.0, 5.0),
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
)
# The captions cite sheets by these numbers, never typed ones.
BOM_SHEET_NUMBER = SHEET_NAMES.index(BOM_SHEET) + 1
STEPS_SHEET_NUMBER = SHEET_NAMES.index(STEPS_SHEET) + 1
if SPEC.layout is not DrawingLayout.LANDSCAPE:
    raise AssertionError("the jig's primary sheet must remain landscape")
SHEET_LAYOUTS = {name: DrawingLayout.LANDSCAPE for name in SHEET_NAMES}
# The jig is about 970 x 435 in plan: 1:4 for the arrangement, 1:15 for the
# finished isometric and 1:6 for the BOM's collapsed reference, the largest
# ladder rung its room left of the BOM holds (review bought-tl000-r1: at 1:10
# it sat small in that room). The finished
# view sits under the continued steps and the checks; review bought-r15's
# step 4, 6 and 7 rewrites send step 11 to the right column, which leaves its
# room about 63 tall, short of the 94 the view needs at 1:8.
ASSEMBLED_SCALE = (1.0, 4.0)
REFERENCE_SCALE = (1.0, 6.0)
ISOMETRIC_SCALE = (1.0, 15.0)
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
        STEPS_SHEET: ISOMETRIC_SCALE,
    }
    return {
        name: cluster_scales[name] if name in cluster_scales else fixed[name]
        for name in SHEET_NAMES
    }


# The scales each sheet is created at; build() reports the fitted ones.
SHEET_SCALES = package_sheet_scales({c.sheet: c.scale for c in CLUSTERS})
SHEET_SCALE = SHEET_SCALES[ASSEMBLED_SHEET]

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

# Sheet 2: the BOM right, four columns to the inner border. The 29 rows fit
# one table above the title block at one line a row, so the BOM is not
# split: draw_pd_paper_drive_assembly's proven column widths (a 41-character
# description prints on one line in 118 mm) and row height, every row set
# and the rebuilt table measured against its paper.
# Table text runs about 2.9 mm a character (default format).
BOM_CHAR_M = 0.0029
BOM_COLUMN_WIDTHS = {
    "item": 0.012,
    "part": 0.048,
    "description": 0.118,
    "quantity": 0.012,
}
BOM_DESCRIPTION_MAX_CHARS = spec.BOM_DESCRIPTION_CHARS  # one line in 118 mm
BOM_ROW_HEIGHT = 0.0055
BOM_SHEET_CLEARANCE = 0.003  # the paper the BOM keeps off the title block
BOM_ANCHOR = (SHEET_INNER_BORDER[2] - sum(BOM_COLUMN_WIDTHS.values()), 0.262)
REGION_GAP = 0.006  # between a view's room and the text beside it
# Left of the BOM, over the title block's top, the BOM's parent view: the jig
# collapsed, unballooned, a reference for the table. Its measured outline is
# centred in this room and must stay in it.
REFERENCE_REGION = (
    SHEET_INNER_BORDER[0],
    TITLE_BLOCK[3] + BOM_SHEET_CLEARANCE,
    BOM_ANCHOR[0] - REGION_GAP,
    SHEET_INNER_BORDER[3],
)

# Sheets 3-5: one cluster's exploded isometric each, its balloon ring inside
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

# Sheet 6: the assembly sequence in two columns of one width, the heading and
# as many whole steps as fit the left column, which runs down beside the
# title block; the rest at the top of the right column, the checks under
# them, the finished isometric under those, over the title block.
# Default-format note text: 4.525 mm a line (draw_dt_drive_train_assembly's
# measured pitch) and about 2.9 mm a character.
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
    "ch-rocker-arm-tl-oblique-rail": _config.parts("ch-rocker-arm-tl-oblique-rail"),
    "ch-rocker-arm-tl-oblique-carriage": _config.parts(
        "ch-rocker-arm-tl-oblique-carriage"
    ),
    "ch-rocker-arm-tl-oblique-bearing": _config.parts(
        "ch-rocker-arm-tl-oblique-bearing"
    ),
    "ch-rocker-arm-tl-oblique-cl-dowel": _config.parts(
        "ch-rocker-arm-tl-oblique-cl-dowel"
    ),
    "ch-rocker-arm-tl-oblique-leadscrew": _config.parts(
        "ch-rocker-arm-tl-oblique-leadscrew"
    ),
    "ch-rocker-arm-tl-oblique-leadscrew-nut": _config.parts(
        "ch-rocker-arm-tl-oblique-leadscrew-nut"
    ),
    "ch-rocker-arm-tl-oblique-pillow-block": _config.parts(
        "ch-rocker-arm-tl-oblique-pillow-block"
    ),
    "ch-rocker-arm-tl-oblique-handwheel": _config.parts(
        "ch-rocker-arm-tl-oblique-handwheel"
    ),
    "ch-rocker-arm-tl-oblique-hold-down-stud": _config.parts(
        "ch-rocker-arm-tl-oblique-hold-down-stud"
    ),
    "ch-rocker-arm-tl-oblique-t-nut": _config.parts("ch-rocker-arm-tl-oblique-t-nut"),
    "ch-rocker-arm-tl-oblique-flange-nut": _config.parts(
        "ch-rocker-arm-tl-oblique-flange-nut"
    ),
    "ch-rocker-arm-tl-oblique-rail-screw": _config.parts(
        "ch-rocker-arm-tl-oblique-rail-screw"
    ),
    "ch-rocker-arm-tl-oblique-bracket-screw": _config.parts(
        "ch-rocker-arm-tl-oblique-bracket-screw"
    ),
    "ch-rocker-arm-tl-oblique-block-screw": _config.parts(
        "ch-rocker-arm-tl-oblique-block-screw"
    ),
    "ch-rocker-arm-tl-oblique-carriage-screw": _config.parts(
        "ch-rocker-arm-tl-oblique-carriage-screw"
    ),
    "ch-rocker-arm-tl-oblique-kp08-screw": _config.parts(
        "ch-rocker-arm-tl-oblique-kp08-screw"
    ),
    "ch-rocker-arm-tl-oblique-nut-screw": _config.parts(
        "ch-rocker-arm-tl-oblique-nut-screw"
    ),
    "ch-rocker-arm-tl-oblique-riser-screw": _config.parts(
        "ch-rocker-arm-tl-oblique-riser-screw"
    ),
    "ch-rocker-arm-tl-oblique-clamp-screw": _config.parts(
        "ch-rocker-arm-tl-oblique-clamp-screw"
    ),
    "ch-rocker-arm-tl-oblique-lever-screw": _config.parts(
        "ch-rocker-arm-tl-oblique-lever-screw"
    ),
    "ch-rocker-arm-tl-oblique-block-washer": _config.parts(
        "ch-rocker-arm-tl-oblique-block-washer"
    ),
    "ch-rocker-arm-tl-oblique-lever-washer": _config.parts(
        "ch-rocker-arm-tl-oblique-lever-washer"
    ),
}
if set(PART_ROWS) != set(BOM_COMPONENTS):
    raise AssertionError("BOM registry rows must cover exactly the assembly families")
BOM_PART_NUMBERS = {stem: str(row["number"]) for stem, row in PART_ROWS.items()}
BOM_DESCRIPTIONS = dict(spec.BOM_DESCRIPTIONS)
if max(map(len, BOM_DESCRIPTIONS.values())) > BOM_DESCRIPTION_MAX_CHARS:
    raise AssertionError("every BOM description must print on one line")
BOM_IDENTITY_ALIASES = {number: stem for stem, number in BOM_PART_NUMBERS.items()}
BOM_NORMALIZED_ALIASES = {
    alias.casefold(): stem for alias, stem in BOM_IDENTITY_ALIASES.items()
}
# The steps cite items by number, so the BOM must number its rows exactly as
# the spec does (BOM_ORDER); the recipe refuses any other numbering.
BOM_ITEM_NUMBERS = dict(spec.ITEM_NUMBERS)

# One balloon per BOM row, each on its family's lowest-named shown instance,
# on the one cluster sheet that shows the family; each sheet's balloons
# share one ring (_ring_balloons).
BALLOON_ANCHORS = {stem: BalloonAnchor() for stem in BOM_COMPONENTS}
# The base bar's walk landed on rail 2's carriage end seal (review r5): its
# balloon lands on bar 1's long top edge on the operator's side (part +Y,
# ``HIGH_SIDE_Y``, z ``BAR_THICK``), the edge nearest the viewer, 200 from the
# spindle end: what stands on the bar sits behind and above it on the sheet,
# what hangs under it below. The bottom edge 300 out (bought-r15) selected no
# edge on the sheet once C4 widened the bar to 1/2 x 6 (bought-r16).
BALLOON_ANCHORS[spec.BASE_BAR] = BalloonAnchor(
    point_mm=(200.0, base_bar.HIGH_SIDE_Y, base_bar.BAR_THICK)
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


def _wrapped(lines: tuple[str, ...], *, width: int, heading: str | None = None) -> str:
    """Wrap each numbered line (a step or sub-step) under its own label; one
    note per block. A hyphenated word (HOLD-DOWNS, A1-B1), an item citation
    (ITEM 22) and a torque (3.5 N·m) stay whole on their line."""
    out = [heading] if heading else []
    for line in (
        _UNBROKEN.sub(lambda m: m.group(0).replace(" ", _GLUE), text) for text in lines
    ):
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
    return (text.count("\n") + 1) * NOTE_LINE_M


@dataclass(frozen=True)
class StepsLayout:
    """The steps sheet's text blocks, where the checks go, the finished
    view's room."""

    steps: str  # the heading and the steps the left column holds
    continued: str  # the rest, atop the right column; "" when none
    checks: str
    checks_xy: tuple[float, float]
    finished_region: tuple[float, float, float, float]


def steps_sheet_layout(steps: Sequence[str], checks: Sequence[str]) -> StepsLayout:
    """Lay the steps sheet out: the heading and the most whole steps whose
    block ends over ``STEPS_FLOOR`` down the left column, the rest atop the
    right one, the checks under them, and under those, over the title block,
    the finished view's room. Raises when the first step alone overruns."""
    for count in range(len(steps), 0, -1):
        left = _wrapped(
            tuple(steps[:count]), width=STEPS_LINE_WIDTH, heading=STEPS_HEADING
        )
        if _note_height(left) <= STEPS_XY[1] - STEPS_FLOOR:
            break
    else:
        raise ValueError("the first assembly step overruns the steps' left column")
    continued = _wrapped(tuple(steps[count:]), width=STEPS_LINE_WIDTH)
    checks_text = _wrapped(tuple(checks), width=STEPS_LINE_WIDTH)
    x, top = STEPS_CONTINUED_XY
    if continued:
        top -= _note_height(continued) + REGION_GAP
    region = (
        x,
        TITLE_BLOCK[3] + BOM_SHEET_CLEARANCE,
        SHEET_INNER_BORDER[2],
        top - _note_height(checks_text) - REGION_GAP,
    )
    return StepsLayout(left, continued, checks_text, (x, top), region)


STEPS_LAYOUT = steps_sheet_layout(spec.ASSEMBLY_STEPS, spec.ASSEMBLY_CHECKS)
ASSEMBLY_STEPS = STEPS_LAYOUT.steps
ASSEMBLY_STEPS_CONTINUED = STEPS_LAYOUT.continued
ASSEMBLY_CHECKS = STEPS_LAYOUT.checks
CHECKS_XY = STEPS_LAYOUT.checks_xy
FINISHED_REGION = STEPS_LAYOUT.finished_region


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
    return _wrapped((f"{cluster.title} {reference}",), width=EXPLODED_CAPTION_WIDTH)


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
    """A sheet-owned note: activate the sheet so no view owns it."""
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
    component = _early_bound(component, "IComponent2")
    path = str(component.GetPathName() or "")
    if not path:
        raise RuntimeError(f"component {component.Name2!r} has no referenced path")
    return Path(path).stem.casefold()


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


def _bom_cells(table: Any) -> tuple[tuple[str, ...], ...]:
    """Every displayed BOM cell, header row first."""
    return tuple(
        tuple(
            str(table.DisplayedText(row, column) or "").strip()
            for column in range(int(table.ColumnCount))
        )
        for row in range(int(table.RowCount))
    )


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


def _set_cell(table: Any, row: int, column: int, text: str, *, label: str) -> None:
    if not table.IsCellTextEditable(row, column):
        raise RuntimeError(f"jig BOM {label} cell is locked")
    table.SetText2(row, column, False, text)


def bom_extent_violations(
    anchor: tuple[float, float], width: float, height: float
) -> list[str]:
    """Name every way the top-left-anchored BOM leaves its paper: the inner
    border, the title block (``BOM_SHEET_CLEARANCE`` clear of it) and the
    reference view's room left of the table (``REGION_GAP`` clear of it)."""
    left, top = anchor
    right, bottom = left + width, top - height
    tolerance = 1e-9  # floating-point arithmetic, not a paper allowance
    _border_left, border_bottom, border_right, border_top = SHEET_INNER_BORDER
    findings = []
    if left < REFERENCE_REGION[2] + REGION_GAP - tolerance:
        findings.append("enters the reference view's room")
    if right > border_right + tolerance or top > border_top + tolerance:
        findings.append("crosses the inner border")
    if bottom < border_bottom + BOM_SHEET_CLEARANCE - tolerance:
        findings.append("crosses the bottom border")
    if (
        right > TITLE_BLOCK[0]
        and bottom < TITLE_BLOCK[3] + BOM_SHEET_CLEARANCE - tolerance
    ):
        findings.append("enters the title block")
    return findings


def _assert_bom_on_paper(table: Any) -> None:
    """Measure the rebuilt table from its native anchor: every row's height (a
    wrapped description grows its row past ``BOM_ROW_HEIGHT``) and every
    column's width."""
    annotation = _early_bound(table.GetAnnotation(), "IAnnotation")
    position = tuple(float(value) for value in annotation.GetPosition())
    if len(position) != 3:
        raise RuntimeError(f"jig BOM position unreadable: {position!r}")
    rows = int(table.RowCount)
    height = sum(float(table.GetRowHeight(row)) for row in range(rows))
    width = sum(
        float(table.GetColumnWidth(column)) for column in range(int(table.ColumnCount))
    )
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


def _validate_bom(adapter: Any, table: Any) -> tuple[tuple[str, str], ...]:
    """Rewrite part numbers; prove identities, item numbers, descriptions and
    quantities; set the column widths and the one-line row height; measure the
    rebuilt table on its paper. Return (stem, item number) in BOM order."""
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

    actual: dict[str, int] = {}
    for row_index, row in enumerate(contents[1:], start=1):
        text = row[at["part"]].casefold()
        stem = BOM_NORMALIZED_ALIASES.get(text, text)
        if stem in actual:
            raise RuntimeError(f"jig BOM repeats component family {stem!r}")
        actual[stem] = row_index
    if set(actual) != set(BOM_COMPONENTS):
        raise RuntimeError(
            f"jig BOM identities {sorted(actual)!r} != {sorted(BOM_COMPONENTS)!r}"
        )
    for stem, row_index in actual.items():
        row = contents[row_index]
        if row[at["item"]] != BOM_ITEM_NUMBERS[stem]:
            raise RuntimeError(
                f"jig BOM numbers {stem!r} item {row[at['item']]!r}, but the steps "
                f"cite item {BOM_ITEM_NUMBERS[stem]}: the assembly must insert its "
                "families in spec.BOM_ORDER"
            )
        number = BOM_PART_NUMBERS[stem]
        if row[at["part"]] != number:
            _set_cell(table, row_index, at["part"], number, label=f"{stem} part-number")
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
    if not adapter.currentModel.EditRebuild3():
        raise RuntimeError("jig BOM rebuild failed")
    settled = _bom_cells(table)
    for stem, row_index in actual.items():
        applied = settled[row_index][at["part"]]
        if applied != BOM_PART_NUMBERS[stem]:
            raise RuntimeError(f"jig BOM part number for {stem!r} reads {applied!r}")
    _assert_bom_on_paper(table)
    return tuple((stem, BOM_ITEM_NUMBERS[stem]) for stem in BOM_COMPONENTS)


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


def _place_assembled_sheet(adapter: Any) -> None:
    """Plan over the operator's elevation at the modelled pose, each titled,
    the plan's tags, the pose caption, and the rail-alignment targets."""
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


def _place_reference_view(adapter: Any) -> Any:
    """The BOM's parent view: the jig collapsed, centred in its room left of
    the table, unballooned."""
    _activate_sheet(adapter, BOM_SHEET)
    label = "jig reference"
    center = _region_center(REFERENCE_REGION)
    view = _place_named_view(
        adapter, spec.ISOMETRIC_VIEW, center, REFERENCE_SCALE, label=label
    )
    set_high_quality_shaded_with_edges(adapter, view, label=label)
    configuration = apply_view_configuration(adapter, view, label=label)
    set_view_exploded_state(
        adapter, view, False, configuration=configuration, label=label
    )
    _center_view_outline(adapter, view, center, label=label)
    _assert_view_on_sheet(view, bounds=REFERENCE_REGION, label=label)
    return view


def _place_finished_view(adapter: Any) -> None:
    """The finished assembly in full detail, centred in its room under the
    checks."""
    _activate_sheet(adapter, STEPS_SHEET)
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


def _balloon_cluster(
    adapter: Any,
    view: Any,
    cluster: Cluster,
    items: Sequence[tuple[str, str]],
    bom_name: str,
) -> list[BalloonLanding]:
    """Link one cluster view to the BOM, balloon each of its families once,
    all on one ring."""
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
    _ring_balloons(adapter, view, landings, label=f"{label} balloons")
    landings = _relax_cluster_slide(adapter, view, landings, label=f"{label} ring")
    if sorted(landing.stem for landing in landings) != sorted(cluster.stems):
        raise RuntimeError(
            f"{label} carries balloons for "
            f"{sorted(landing.stem for landing in landings)!r}, "
            f"expected one for each of {sorted(cluster.stems)!r}"
        )
    return landings


def _place_steps_notes(adapter: Any) -> None:
    _add_note_block(
        adapter, STEPS_SHEET, ASSEMBLY_STEPS, STEPS_XY, label="assembly sequence"
    )
    if ASSEMBLY_STEPS_CONTINUED:
        _add_note_block(
            adapter,
            STEPS_SHEET,
            ASSEMBLY_STEPS_CONTINUED,
            STEPS_CONTINUED_XY,
            label="assembly sequence, continued",
        )
    _add_note_block(
        adapter, STEPS_SHEET, ASSEMBLY_CHECKS, CHECKS_XY, label="assembly checks"
    )


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
) -> tuple[dict[str, tuple[float, float]], Callable[[], None]]:
    """Every sheet; returns the sheets' fitted scales and the check that
    proves every balloon again after the last rebuild.

    Every view is configured, then exploded or collapsed, before the BOM is
    inserted; after it only BOM links and balloons
    (draw_dt_drive_train_assembly's order)."""
    _create_package_sheets(adapter)
    for sheet_name in SHEET_NAMES:
        sheet = _activate_sheet(adapter, sheet_name)
        scale = SHEET_SCALES[sheet_name]
        if not sheet.SetScale(float(scale[0]), float(scale[1]), False, False):
            raise RuntimeError(f"failed to set jig sheet scale: {sheet_name}")
    _place_assembled_sheet(adapter)
    reference = _place_reference_view(adapter)
    _place_finished_view(adapter)
    placed = [(cluster, *_place_cluster_view(adapter, cluster)) for cluster in CLUSTERS]
    _activate_sheet(adapter, BOM_SHEET)
    table = insert_bom_table(
        adapter,
        reference,
        anchor_xy=BOM_ANCHOR,
        expected_components=BOM_COMPONENTS,
        descriptions=BOM_DESCRIPTIONS,
        identity_aliases=BOM_IDENTITY_ALIASES,
        label="jig",
    )
    items = _validate_bom(adapter, table)
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
    if sorted(landing.stem for landing in landings) != sorted(BOM_COMPONENTS):
        raise RuntimeError(
            f"jig package carries {len(landings)} balloons, expected one per "
            f"BOM row ({len(BOM_COMPONENTS)}) across the exploded sheets"
        )
    _place_steps_notes(adapter)
    scales = package_sheet_scales(
        {cluster.sheet: scale for cluster, _view, scale in placed}
    )
    return scales, lambda: assert_balloon_landings(adapter, landings)


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
        settled_checks=(settled,),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[ARTIFACT_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
