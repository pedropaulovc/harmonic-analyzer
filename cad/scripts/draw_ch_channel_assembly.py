r"""Create the MHA-CH-00 channel assembly fitter package (six sheets).

1. ASSEMBLED VIEWS: Front and Right at 1:5 and the full-detail isometric at
   1:7. The Front carries the viewing arrows of views D, E and F, the Right
   that of view G.
2. EXPLODED VIEW + BOM: the builder-owned CHANNEL_EXPLODED isometric
   (ch_channel_explode_spec), the native BOM with the registry's part
   numbers, vendor SKUs and ch_channel_assembly_sheet's descriptions, and one
   balloon per BOM row.
3. ROCKER BANK FIT-UP: view D, the bank isolated at 1:1 with the stack
   length, and the first rocker-bank steps. The right bracket is set off a
   wave disc spring that preloads the bank left, and the plain pivot shaft is
   held by a set screw in each ear (#948 ruling R, PR #1292; user,
   2026-10-10).
4. ROCKER BANK FIT-UP (CONT.): detail A, the cropped 4:1 right end with the
   spring set, and the rest of the rocker-bank steps.
5. LEVER BANK FIT-UP: view E, the keepers, fulcrum shaft and levers isolated
   at 1:1 with the keeper lug span, view F, the 1:2 keeper plan with the
   keepers' three settings off the top frame's datums, and the first
   lever-bank steps.
6. LEVER BANK FIT-UP (CONT.): view G, the spring hook-up at 1:2, and the rest
   of the lever-bank steps.

Ends and sides are named as the right side views (D, E) draw them: left and
right, never a compass (drawing-guidelines.md rule 26). Steps name parts by
BOM item (rule 22). The settings are the assembly's own model dimensions (the
hidden rocker-bank, lever-bank and keeper-plan settings sketches,
build_ch_channel_assembly), not numbers in note text; the steps are numbered
by ``ch_channel_assembly_steps``.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import math
import re
import sys
import textwrap
from pathlib import Path
from typing import Any, Callable, Literal

from solidworks_mcp.adapters import sw_type_info as _sw_type_info
from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    dimension_name,
    place_view,
    view_name,
)

from _check import check
from _com import _early_bound
import _config
from _drawing_balloon_display import rendered_balloon_circle
from _drawing_balloons import (
    BalloonAnchor,
    BalloonLanding,
    add_component_bom_balloons,
    assert_balloon_landings,
    isolate_drawing_view_components,
)
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_high_quality_shaded_with_edges,
)
from _drawing_dimension_import import curate_view_dimensions
from _drawing_dimensions import (
    assert_imported_precision,
    set_dimension_callouts,
    set_reference_dimension,
)
from _drawing_hidden_sketches import _show_base_view_sketches
from _drawing_leader_notes import add_leader_note
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_types import DRAWING_TEMPLATES, DrawingLayout
from _drawing_sheets import create_blank_drawing_sheets
from _drawing_tables import insert_bom_table
from _drawing_view_configuration import (
    ASSEMBLY_VIEW_CONFIGURATION,
    SIMPLIFIED_VIEW_CONFIGURATION,
    ViewRole,
    apply_view_configuration,
    assert_full_detail_view,
    set_view_exploded_state,
)
from _drawing_view_display import set_hidden_lines_removed
from _machinist_review_mode import MachinistReviewMode
from _session import run_build
from _simplified_names import simplified_name
import _telemetry
from _printed_tolerance import printed_deviations
from _title_block_units import LENGTH_UNITS, render_number
import ch_channel_assembly_sheet as notes
import ch_channel_assembly_spec as asm
from fr_top_frame_spec import BORE_DIA as SOCKET_BORE_DIA
import ch_channel_explode_spec as explode
import ch_channel_assembly_steps as steps
from ch_channel_lever_spec import (
    HUB_LENGTH as LEVER_HUB_LENGTH,
    HUB_LENGTH_BAND as LEVER_HUB_LENGTH_BAND,
    LEVER_SPRING_X,
)
from ch_fulcrum_keeper_spec import (
    CROWN_TOP_Y as KEEPER_CROWN_TOP_Y,
    FULCRUM_KEEPER_CENTRE_Z,
    KEEPER_FITUP_LOCATION_BAND_MM,
    KEEPER_FITUP_X_FROM_WEB_MM,
    KEEPER_INNER_FACE_FROM_FRONT_SOCKET_MM,
    KEEPER_INNER_FACE_SPAN_MM,
    KEEPER_Z_OFF,
    LUG_HALF_T as KEEPER_LUG_HALF_T,
    SHAFT_AXIS_H as KEEPER_SHAFT_AXIS_H,
)
from ch_pivot_bracket_sides import FOOT_Z1 as BRACKET_FOOT_Z1
from ch_pivot_bracket_spec import (
    APEX_ABOVE_BORE as BRACKET_APEX_ABOVE_BORE,
    FOOT_H as BRACKET_FOOT_H,
    FOOT_W as BRACKET_FOOT_W,
)
from ch_pivot_shaft_spec import (
    DOME_HEIGHT,
    FLAT_DEPTH as PIVOT_FLAT_DEPTH,
    SHAFT_DIA as PIVOT_SHAFT_DIA,
)
from ch_rocker_arm_notes import DRAWING_PRECISION as ARM_DRAWING_PRECISION
from ch_rocker_arm_spec import HUB_LENGTH, HUB_LENGTH_BAND
from ch_rocker_arm_spec import UNIT as ARM_UNIT
from channel_frame_geom import LEVER_FULCRUM_XY, ROCKER_PIVOT_XY
from frame_column_stations import COLUMN_X
from rocker_bank_layout import (
    COUNT,
    PIVOT_BRACKET_Z,
    PIVOT_SHAFT_FLAT_STATIONS,
    ROCKER_SPRING_SET_BAND,
    SHAFT_TIP_SET_BAND,
    STACK_L20_ACCEPT,
    STACK_MID_Z,
)


# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE
SPEC = DRAWINGS_BY_NAME["ch_channel_assembly"]
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
    "EXPLODED VIEW + BOM",
    "ROCKER BANK FIT-UP",
    "ROCKER BANK FIT-UP (CONT.)",
    "LEVER BANK FIT-UP",
    "LEVER BANK FIT-UP (CONT.)",
)
if SPEC.layout is not DrawingLayout.LANDSCAPE:
    raise AssertionError("the channel package is landscape throughout")
SHEET_LAYOUTS = {name: DrawingLayout.LANDSCAPE for name in SHEET_NAMES}
SHEET_SCALE = (1.0, 7.0)
# r5 review: at 1:7 the Front and Right sat small in the sheet's left 60%.
# At 1:5 the bank's 0.197 m height fits the 0.254 m between the borders.
ASSEMBLED_SCALE = (1.0, 5.0)
ASSEMBLED_ISO_SCALE = SHEET_SCALE
FITUP_SCALE = (1.0, 1.0)
SHEET_SCALES = {
    SHEET_NAMES[0]: ASSEMBLED_SCALE,
    SHEET_NAMES[1]: SHEET_SCALE,
    **{name: FITUP_SCALE for name in SHEET_NAMES[2:]},
}
_TEMPLATE = DRAWING_TEMPLATES[DrawingLayout.LANDSCAPE]
BORDER = 0.0127

# --- sheet 1: assembled views -------------------------------------------------
# Front and Right in projection on one centre line, mid-way between the
# borders (outlines 0.042-0.238 at 1:5), the Right's outline ending 13 mm
# west of the title block it stands beside (0.060 and 0.036 wide at 1:5).
FRONT_CENTER = (0.075, 0.140)
RIGHT_CENTER = (0.185, 0.140)
# The isometric over the title block's middle, at 1:7 so its 0.154-tall
# outline stays between the title block (top 0.066) and the caption: at
# y 0.150 it runs 0.073 to 0.227.
ISO_CENTER = (0.320, 0.150)
ISO_LABEL = "ISOMETRIC\nSCALE {} : {}".format(*map(int, ASSEMBLED_ISO_SCALE))
# Under the isometric's drawn bottom (0.096), above the title block.
ISO_LABEL_XY = (ISO_CENTER[0] - 0.022, 0.089)
ASSEMBLED_CAPTION_XY = (0.272, 0.250)
ASSEMBLED_CAPTION = "\n".join(
    (
        "SHEET 2: EXPLODED VIEW AND BILL OF MATERIALS.",
        f"SHEETS 3 TO {len(SHEET_NAMES)}: FIT-UP, STEPS 1 TO {len(steps.SEQUENCE)}.",
    )
)
# The lettered views D-G are partial views of the assembly in principal
# directions on the fit-up sheets (drawing-guidelines.md rule 9): each has a
# viewing arrow on a sheet-1 view, a letter note whose straight leader is the
# arrow (draw_ch_rocker_arm's view F recipe), its tip VIEW_ARROW_TIP_GAP
# outside the parent's outline and level with (or, for a top view, above) the
# part it looks at.
VIEW_ARROW_LETTER_HEIGHT = 0.005
VIEW_ARROW_TIP_GAP = 0.002
VIEW_ARROW_RUN = 0.010

# --- sheet 2: exploded isometric, BOM, balloons ------------------------------
# 10 mm below the sheet's middle, so the ring can grow at the top.
EXPLODED_ISO_CENTER = (0.100, 0.140)
# The lever balloon's leader runs along the bank axis, and the exploded fulcrum
# shaft lies on that axis's south extension. The shaft has no hit-testable
# edge, so SolidWorks picks where its leader lands (listed-edge), and that
# landing moved 15 mm between r8 and r9. The view is tall and narrow, so 8 of
# the 19 balloons crowd its top. At 14 mm the ring's push-apart swung balloon
# 14 down over the shaft, and a south-end landing crossed leader 2 (r9 audit).
# A replay of the ring with the anchor-nut balloon added covers every landing
# on the visible shaft, nut attachments at least 3.5 mm below the anchor's,
# and balloon radius 5.0-5.6 mm. At 28 mm it crosses nothing and keeps
# leader 14 2.1-4.4 mm off the shaft, but the ring's centres ran 5.5 mm inside
# the border at the top, so balloon 4's 5.6 mm circle touched it (machinist
# review, #1660 r1). At 26 mm the top circle clears the border by about 2 mm;
# _assert_view_on_sheet now grows the outline by the ring plus the largest
# balloon radius, so a balloon circle can never reach the border.
BALLOON_MARGIN = 0.026
BALLOON_MAX_RADIUS = 0.0056
# Balloon 3 (the rocker pivot bracket) walked to its ear's apex. Lifted 60
# straight up its foot hole, which lies in front of the ear, the hold-down
# (item 7) now stands right over that apex in the isometric, so leader 3 ran
# down the hold-down's head and shank to its landing (proof run
# 20261017T222049387Z, sheet 2). Its landing is the foot's free end instead:
# the edge drawn sheet-left of it, at half the foot's height, about 9.5 model
# mm left of the hold-down's axis. It falls after the hold-down's landing in
# the ring's attachment order, so leader 3 swaps ring slots with leader 7 and
# runs left of the hold-down. Part frame (ch_pivot_bracket_spec): the foot
# spans x -FOOT_W/2..FOOT_W/2 and z ..FOOT_Z1, the north bracket unturned.
BRACKET_BALLOON_POINT_MM = (
    -BRACKET_FOOT_W / 2.0,
    BRACKET_FOOT_H / 2.0,
    BRACKET_FOOT_Z1,
)
# Balloon 1 (the rocker pivot shaft) walked to the stub of shaft south of hub
# 0, the only part of it the 1:7 view shows, but its ring slot is below the
# view, so its leader climbed through the black rocker-arm fan and read as
# naming the arms (#1895 machinist review, r2 and r3). Its landing is now the
# south flat's edge on the eye's side, at the flat's middle (the south ear's
# mid-plane): the flat faces +y, so both faces at that edge face the eye, and
# in the isometric the edge clears arm 0's top edge (8 over the pivot) by
# about 1.8. Part frame (ch_pivot_shaft_spec): axis along z from the north
# cylinder end, unturned in the assembly.
PIVOT_SHAFT_STEM = "ch-pivot-shaft"
_PIVOT_FLAT_Y = PIVOT_SHAFT_DIA / 2.0 - PIVOT_FLAT_DEPTH
PIVOT_SHAFT_BALLOON_POINT_MM = (
    math.sqrt((PIVOT_SHAFT_DIA / 2.0) ** 2 - _PIVOT_FLAT_Y**2),
    _PIVOT_FLAT_Y,
    -PIVOT_SHAFT_FLAT_STATIONS[0],
)
# Off the ring, its circle stands this far (sheet m) from that landing: up
# the open strip between the east edge of the bank's vertical column and the
# exploded south washer, spring and bracket, which the stub points at. The
# leader then reaches the stub over paper, about 1.3 mm east of the column's
# corner and clear of the washer ring beside the stub's tip (measured on the
# sheet of run 20261023T234951749Z).
PIVOT_SHAFT_BALLOON_OFFSET = (0.012, 0.045)
# The rendered circle's read-back may sit a viewport pixel off the request
# at fit zoom (position_bom_balloon's pixel bound); a millimetre still proves
# the circle left its ring slot for the strip.
BALLOON_PLACEMENT_TOL_M = 0.001
BOM_ANCHOR = (0.205, 0.262)
BOM_COLUMN_WIDTHS = {
    "item": 0.012,
    "part": 0.030,
    "description": 0.078,
    "sku": 0.026,
    "quantity": 0.012,
}
BOM_SKU_TITLE = "VENDOR SKU"
MADE_PART_SKU = "-"
BOM_ROW_HEIGHT = 0.006
# Wrapped full vendor Numbers grow the native table beyond its nominal pitch.
# Follow its rebuilt bottom, then prove the caption's actual gap again at save.
EXPLODED_CAPTION_OFFSET = 0.006
EXPLODED_CAPTION_MIN_GAP = 0.004

# Spring variants: one per distinct amplitude among the built channels, named
# as build_ch_channel_assembly names them (first-occurrence order).
CHANNELS = _config.active_count()
if CHANNELS != COUNT:
    raise AssertionError("the channel package is drawn for the full bank")
SPRING_VARIANT_ISSUE = "https://github.com/pedropaulovc/harmonic-analyzer/issues/1610"


def spring_stems(amplitudes: list[float], channels: int) -> tuple[str, ...]:
    """Installed-spring file stems the channel builder makes for these amplitudes."""
    variants = {
        amplitude: index for index, amplitude in enumerate(dict.fromkeys(amplitudes))
    }
    return tuple(
        dict.fromkeys(
            f"ch-vn-channel-spring-installed-stretch{variants[amplitude]:02d}"
            for amplitude in amplitudes[:channels]
        )
    )


def require_single_spring_variant(stems: tuple[str, ...], preset: str) -> None:
    """Refuse a BOM the drawing cannot print: one MHA-CH-VN-50 row of qty 20.

    Each spring variant is its own SLDPRT, so a preset with several installed
    lengths would print several rows under one part number.
    """
    if len(stems) != 1:
        raise RuntimeError(
            f"MHA-CH-00 is drawn for one installed-spring length, but the "
            f"{preset!r} amplitude preset builds {len(stems)} spring variants "
            f"that share MHA-CH-VN-50; see {SPRING_VARIANT_ISSUE}"
        )


SPRING_STEMS = spring_stems(_config.amplitudes(), CHANNELS)
SPRING_STEM = SPRING_STEMS[0]

BOM_QUANTITIES = {
    "ch-pivot-shaft": 1,
    "ch-fulcrum-shaft": 1,
    explode.BRACKET: 2,
    explode.BRACKET_SET_SCREW: 2,
    explode.WASHER: 2,
    explode.BANK_SPRING: 1,
    explode.BRACKET_HOLD_DOWN: 2,
    explode.KEEPER: 2,
    explode.KEEPER_FOOT_SCREW: 2,
    explode.KEEPER_SET_SCREW: 2,
    "ch-rocker-arm": CHANNELS,
    explode.ROD: CHANNELS,
    explode.BAR: CHANNELS,
    "ch-channel-lever": CHANNELS,
    "ch-rod-pivot-pin": CHANNELS,
    explode.BAR_PIN: CHANNELS,
    SPRING_STEM: CHANNELS,
    explode.HOOK: CHANNELS,
    explode.ANCHOR_NUT: CHANNELS,
}
BOM_COMPONENTS = tuple(BOM_QUANTITIES)
# Literal stems, so the config-dependency analysis reads exactly these rows.
PART_ROWS = {
    "ch-pivot-shaft": _config.parts("ch-pivot-shaft"),
    "ch-fulcrum-shaft": _config.parts("ch-fulcrum-shaft"),
    "ch-pivot-bracket": _config.parts("ch-pivot-bracket"),
    "sh-vn-arbor-set-screw": _config.parts("sh-vn-arbor-set-screw"),
    "ch-vn-rocker-thrust-washer": _config.parts("ch-vn-rocker-thrust-washer"),
    "ch-vn-rocker-bank-spring": _config.parts("ch-vn-rocker-bank-spring"),
    "ch-vn-bracket-hold-down-screw": _config.parts("ch-vn-bracket-hold-down-screw"),
    "ch-fulcrum-keeper": _config.parts("ch-fulcrum-keeper"),
    "ch-vn-frame-side-screw": _config.parts("ch-vn-frame-side-screw"),
    "ch-vn-fulcrum-set-screw": _config.parts("ch-vn-fulcrum-set-screw"),
    "ch-rocker-arm": _config.parts("ch-rocker-arm"),
    "ch-connecting-rod": _config.parts("ch-connecting-rod"),
    "ch-amplitude-bar": _config.parts("ch-amplitude-bar"),
    "ch-channel-lever": _config.parts("ch-channel-lever"),
    "ch-rod-pivot-pin": _config.parts("ch-rod-pivot-pin"),
    "ch-bar-pivot-pin": _config.parts("ch-bar-pivot-pin"),
    SPRING_STEM: _config.parts("ch-vn-channel-spring-installed"),
    "ch-vn-spring-hook": _config.parts("ch-vn-spring-hook"),
    "ch-anchor-jam-nut": _config.parts("ch-anchor-jam-nut"),
}
if set(PART_ROWS) != set(BOM_COMPONENTS):
    raise AssertionError("BOM registry rows must cover exactly the assembly families")
BOM_PART_NUMBERS = {stem: str(row["number"]) for stem, row in PART_ROWS.items()}
BOM_SKUS = {
    stem: " / ".join(str(sku) for sku in row.get("supplier_skus") or ())
    or MADE_PART_SKU
    for stem, row in PART_ROWS.items()
}
BOM_DESCRIPTIONS = {
    stem: notes.BOM_DESCRIPTIONS[
        "ch-vn-channel-spring-installed" if stem == SPRING_STEM else stem
    ]
    for stem in BOM_COMPONENTS
}
BOM_IDENTITY_ALIASES = {number: stem for stem, number in BOM_PART_NUMBERS.items()}
BOM_NORMALIZED_ALIASES = {
    alias.casefold(): stem for alias, stem in BOM_IDENTITY_ALIASES.items()
}
# The BOM's item numbers: the native table numbers the families in component
# order, which is BOM_COMPONENTS (_validate_bom proves the table prints
# exactly these). Steps name parts by item (drawing-guidelines.md rule 22).
ITEM_NUMBERS = {stem: index for index, stem in enumerate(BOM_COMPONENTS, start=1)}


def item(stem: str) -> str:
    """``ITEM 3``: a part as the steps and labels name it."""
    return f"ITEM {ITEM_NUMBERS[stem]}"


def items_text(stems: frozenset[str] | tuple[str, ...], *, compact: bool = False) -> str:
    """``ITEMS 3, 4, 5 AND 7``: several parts, in item order; ``compact``
    (``ITEMS 3,4,5,7``) for a label in the narrow column right of the BOM."""
    numbers = [str(number) for number in sorted(ITEM_NUMBERS[stem] for stem in stems)]
    if compact:
        return f"ITEMS {','.join(numbers)}"
    return f"ITEMS {', '.join(numbers[:-1])} AND {numbers[-1]}"


_KEEPER_DETAIL_STEMS = (
    explode.KEEPER,
    explode.KEEPER_SET_SCREW,
    explode.KEEPER_FOOT_SCREW,
)
EXPLODED_CAPTION = "\n".join(
    (
        f"EXPLODED: ALL {COUNT} CHANNELS ALIKE. ONE CHANNEL IS PULLED",
        "OUT; ONE BALLOON PER BOM ROW, ON THAT CHANNEL.",
        f"{items_text(_KEEPER_DETAIL_STEMS)} ARE BALLOONED IN DETAIL C.",
        f"QTY IS PER {steps.DRAWING_NUMBER} (ALL {COUNT} CHANNELS).",
    )
)
EXPLODED_VIEW_NAMES = {
    ASSEMBLY_VIEW_CONFIGURATION: explode.EXPLODED_VIEW_NAME,
    SIMPLIFIED_VIEW_CONFIGURATION: simplified_name(explode.EXPLODED_VIEW_NAME),
}
if explode.SOURCE_CONFIGURATION != ASSEMBLY_VIEW_CONFIGURATION:
    raise AssertionError("the channel explode is authored in Default")

# --- sheets 3 to 6: isolated bank views, the right-end detail, steps --------
# On a Right view sheet x runs with machine -z (machine north, +z, left) and
# sheet y with machine y.
CROP_NO_ERROR = 1  # swCropViewErrors_e.swCropViewErrors_NoError
VIEW_POSITION_TOL_M = 1e-4
STEPS_LINE_WIDTH = 64  # characters; default-format note text
# Default-format note text, measured on r743-rocker-fix3's render (leaf
# 20260926T112244Z-1-a884759d): the step columns are sized from these.
NOTE_CHAR_WIDTH = 0.00276
NOTE_LINE_PITCH = 0.0045
# A step is at most six printed lines (drawing-guidelines.md rule 22).
STEP_MAX_LINES = 6
STEPS_LEFT_X = 0.018
STEPS_RIGHT_X = 0.214
STEPS_TOP_Y = 0.258
# Columns stop this far above the title block or the bottom border.
STEPS_FOOT_CLEARANCE = 0.005


@dataclass(frozen=True)
class BankView:
    """One isolated model view (a *Right view of a bank unless told
    otherwise), its ``centre_xyz`` (model mm) landing on ``centre`` (sheet m);
    cropped to ``crop_radius_mm`` if set. ``exploded`` shows the
    configuration's channel explode, ``centre_xyz`` then being an exploded
    position."""

    title: str
    scale: tuple[int, int]
    centre_xyz: tuple[float, float, float]
    centre: tuple[float, float]
    stems: frozenset[str]
    crop_radius_mm: float | None = None
    parts: str = ""
    orientation: str = "*Right"
    exploded: bool = False
    letter: str = ""  # a detail's letter, at its boundary in the parent
    letter_corner: tuple[int, int] = (1, 1)  # letter_xy's corner for it
    label_xy: tuple[float, float] | None = None  # caption point, if not under it
    # The scale of the sheet the view is placed on: a view at that scale
    # prints none (drawing-guidelines.md rule 9).
    sheet_scale: tuple[int, int] = (1, 1)

    @property
    def mm(self) -> float:
        """Sheet metres per model millimetre."""
        return self.scale[0] / self.scale[1] / 1000.0

    def sheet_xy(self, z: float, y: float) -> tuple[float, float]:
        """Machine (z, y) in a *Right view's plane, on the sheet."""
        if self.orientation != "*Right":
            raise ValueError(f"{self.title} is not a *Right view")
        return (
            self.centre[0] - (z - self.centre_xyz[2]) * self.mm,
            self.centre[1] + (y - self.centre_xyz[1]) * self.mm,
        )

    def plan_xy(self, x: float, z: float) -> tuple[float, float]:
        """Machine (x, z) in a *Top view's plane, on the sheet: west (+x)
        right, the machine front (-z) up."""
        if self.orientation != "*Top":
            raise ValueError(f"{self.title} is not a *Top view")
        return (
            self.centre[0] + (x - self.centre_xyz[0]) * self.mm,
            self.centre[1] - (z - self.centre_xyz[2]) * self.mm,
        )

    @property
    def model_centre_m(self) -> tuple[float, float, float]:
        return tuple(value / 1000.0 for value in self.centre_xyz)  # type: ignore[return-value]

    @property
    def label_text(self) -> str:
        scale = (
            f"SCALE {self.scale[0]} : {self.scale[1]}"
            if self.scale != self.sheet_scale
            else ""
        )
        return "\n".join(line for line in (self.title, self.parts, scale) if line)

    @property
    def crop_label_xy(self) -> tuple[float, float]:
        """A cropped view's label point, under its circle."""
        if self.crop_radius_mm is None:
            raise ValueError(f"{self.title} has no crop circle")
        return (
            self.centre[0] - 0.016,
            self.centre[1] - self.crop_radius_mm * self.mm - 0.004,
        )


_PIVOT_X, _PIVOT_Y = ROCKER_PIVOT_XY
_FULCRUM_X, _FULCRUM_Y = LEVER_FULCRUM_XY
ROCKER_BANK = BankView(
    "VIEW D",
    (1, 1),
    (_PIVOT_X, _PIVOT_Y, STACK_MID_Z),
    # 188 mm wide at 1:1 (r5 outline 0.0111-0.1995 about x 0.105): centred
    # between the left border and the steps column, and low enough that the
    # view and its label sit in the middle of the sheet's left half (round 1
    # review: no empty field beside a short column).
    (0.111, 0.165),
    frozenset(
        {
            "ch-pivot-shaft",
            explode.BRACKET,
            explode.BRACKET_SET_SCREW,
            explode.BRACKET_HOLD_DOWN,
            explode.WASHER,
            explode.BANK_SPRING,
            "ch-rocker-arm",
        }
    ),
    parts="ROCKER BANK",
)
# The right end at 4:1: the ear's inner face, the spring, the washer and the
# end hub about the circle's centre on the pivot axis. It prints on sheet 4,
# right of that sheet's step column; its boundary is on view D (sheet 3).
DETAIL_LETTER = "A"
DETAIL_SHEET = SHEET_NAMES[3]
_DETAIL_CENTRE_Z = (asm.PIVOT_CHAIN_Z[0] + asm.PIVOT_CHAIN_Z[2]) / 2.0
SOUTH_END = BankView(
    f"DETAIL {DETAIL_LETTER}",
    (4, 1),
    (_PIVOT_X, _PIVOT_Y, _DETAIL_CENTRE_Z),
    (0.300, 0.165),
    frozenset(
        {
            "ch-pivot-shaft",
            explode.BRACKET,
            explode.BRACKET_SET_SCREW,
            explode.WASHER,
            explode.BANK_SPRING,
            "ch-rocker-arm",
        }
    ),
    crop_radius_mm=8.0,
    parts="FROM VIEW D (SHEET 3)",
    letter=DETAIL_LETTER,
)
# The letter sits this far (sheet m) outside the parent's boundary circle, up
# and to the south, clear of the ear (its outer face 8.7 mm south of centre)
# and above the shaft end.
DETAIL_LETTER_OFFSET = 0.002


def detail_boundary(
    parent: BankView, detail: BankView
) -> tuple[tuple[float, float], float]:
    """``detail``'s crop circle as drawn in ``parent``: sheet centre, radius."""
    if detail.crop_radius_mm is None:
        raise ValueError(f"{detail.title} is not a cropped detail")
    centre = parent.sheet_xy(detail.centre_xyz[2], detail.centre_xyz[1])
    return centre, detail.crop_radius_mm * parent.mm


def letter_xy(
    centre: tuple[float, float],
    radius: float,
    corner: tuple[int, int] = (1, 1),
) -> tuple[float, float]:
    """A detail letter's note point, past its boundary toward ``corner``
    (x, y signs: (1, 1) upper right)."""
    offset = radius + DETAIL_LETTER_OFFSET
    return centre[0] + corner[0] * offset, centre[1] + corner[1] * offset


LEVER_BANK = BankView(
    "VIEW E",
    (1, 1),
    (_FULCRUM_X, _FULCRUM_Y, FULCRUM_KEEPER_CENTRE_Z),
    (0.111, 0.195),
    frozenset(
        {
            "ch-fulcrum-shaft",
            explode.KEEPER,
            explode.KEEPER_FOOT_SCREW,
            explode.KEEPER_SET_SCREW,
            "ch-channel-lever",
            explode.BAR_PIN,
        }
    ),
    parts="LEVER BANK",
)
# The keepers on MHA-FR-02 in plan at 1:2, machine front up as the frame's
# own plan prints it (b9ae machinist review: step 10's settings had no view,
# and its X datum, the web centre, is no face to touch). The frame is not in
# this assembly, so the hidden KEEPER_PLAN_FEATURE sketch draws the frame
# features the settings run from (5d5245a review rule 10): in phantom, the
# west front upper socket's bore, boss and keeper relief step, the line of
# the upper socket centres and the web centre line; as a visible line, the
# inner web face, as far as it shows beside the front keeper (r5 review: in
# phantom a face reads as a hidden line through it; the outer face lies
# under the keeper from the boss on). It carries
# the three settings (owner rulings X1+B1, X-A). Placed under the lever bank:
# the socket line 0.120 up. The farm-measured outline (c80bb08be) ran 0.1051
# below the socket line, so its bottom clears the border by 2.2 mm; the boss
# now tops it 0.0113 above.
KEEPER_PLAN_SOCKET_Y = 0.120
_PLAN_CENTRE_Y = 0.070
_TOP_FRAME_NUMBER = str(_config.parts("fr-top-frame")["number"])
KEEPER_PLAN = BankView(
    "VIEW F",
    (1, 2),
    (
        asm.KEEPER_LUG_X,
        _FULCRUM_Y,
        asm.KEEPER_SOCKET_XZ[1] + (KEEPER_PLAN_SOCKET_Y - _PLAN_CENTRE_Y) * 2000.0,
    ),
    (0.112, _PLAN_CENTRE_Y),
    frozenset(
        {
            "ch-fulcrum-shaft",
            explode.KEEPER,
            explode.KEEPER_FOOT_SCREW,
            explode.KEEPER_SET_SCREW,
        }
    ),
    # A standard top view (machine front up); the Z settings name the faces
    # by what they are, the view's own projection says which is which.
    parts=f"KEEPERS ON {_TOP_FRAME_NUMBER}",
    orientation="*Top",
    label_xy=(0.020, 0.090),
)

# --- sheet 6: view G and the rest of the lever-bank steps --------------------
# The front view of the spring hook-up: the fulcrum shaft, a lever, its
# spring, anchor and jam nut, the 20 channels in line behind the nearest. The
# summing plate the anchor threads into belongs to MHA-HA-00, not this
# assembly. The view outline ran from model x 7.4 to 217.1 and y 955.6 to
# 1078.6 (farm leaf on 06616793e): 210 x 123 mm, so at 1:2 about (0.315,
# 0.215) it fills the top of the sheet's right half, beside the full-height
# left step column, with its label and a short column under it.
HOOKUP_DROP_MM = 44.0
HOOKUP = BankView(
    "VIEW G",
    (1, 2),
    (
        _FULCRUM_X - LEVER_SPRING_X / 2.0,
        _FULCRUM_Y - HOOKUP_DROP_MM,
        FULCRUM_KEEPER_CENTRE_Z,
    ),
    (0.315, 0.215),
    frozenset(
        {
            "ch-fulcrum-shaft",
            "ch-channel-lever",
            SPRING_STEM,
            explode.HOOK,
            explode.ANCHOR_NUT,
        }
    ),
    parts="SPRING HOOK-UP\nSUMMING PLATE NOT SHOWN",
    orientation="*Front",
)
# The outline's bottom (sheet m) at 1:2, from the measured model outline.
HOOKUP_BOTTOM_Y = HOOKUP.centre[1] + (955.6 - HOOKUP.centre_xyz[1]) * HOOKUP.mm

_PLAN_LUG = KEEPER_PLAN.plan_xy(asm.KEEPER_LUG_X, asm.KEEPER_SOCKET_XZ[1])
_PLAN_FACES = tuple(
    KEEPER_PLAN.plan_xy(asm.KEEPER_LUG_X, z) for z in asm.LUG_INNER_FACE_Z
)
# The X text above the boss, its dimension line clear of the boss top and
# off the inner-face dimensions' shared extension line on the socket line
# (5d5245a review); each Z text centred on its own dimension line west of
# the keepers, the rear's inside the front's so neither text sits on the
# other's line (the front line stops at the front face, above the rear text;
# the front text clears the rear line by 3 mm).
PLAN_KEEP = {
    asm.KEEPER_X_DIMENSION: (_PLAN_LUG[0] + 0.016, KEEPER_PLAN_SOCKET_Y + 0.017),
    asm.KEEPER_REAR_Z_DIMENSION: (
        _PLAN_LUG[0] + 0.035,
        (KEEPER_PLAN_SOCKET_Y + _PLAN_FACES[1][1]) / 2.0,
    ),
    asm.KEEPER_FRONT_Z_DIMENSION: (
        _PLAN_LUG[0] + 0.066,
        (KEEPER_PLAN_SOCKET_Y + _PLAN_FACES[0][1]) / 2.0,
    ),
}
# The two frame datums the sketch draws, named where they are drawn (owner
# ruling: the web centre is midway between both web faces), the texts
# east of the view: the socket line's leader lands past the boss, the web
# centre's inside the boss annulus, between the bore and the keeper relief
# step.
PLAN_POINTERS = (
    (
        f"{_TOP_FRAME_NUMBER} LINE OF THE\nUPPER SOCKET CENTRES",
        (0.020, 0.131),
        KEEPER_PLAN.plan_xy(
            asm.KEEPER_SOCKET_XZ[0]
            - (asm.SOCKET_BOSS_DIA / 2.0 + asm.KEEPER_PLAN_SOCKET_LINE) / 2.0,
            asm.KEEPER_SOCKET_XZ[1],
        ),
    ),
    (
        f"{_TOP_FRAME_NUMBER} RAIL WEB CENTRE,\nMIDWAY BETWEEN ITS FACES",
        (0.020, 0.114),
        KEEPER_PLAN.plan_xy(
            asm.KEEPER_SOCKET_XZ[0],
            asm.KEEPER_SOCKET_XZ[1]
            + (SOCKET_BORE_DIA / 2.0 + asm.KEEPER_PLAN_RELIEF_FROM_SOCKET) / 2.0,
        ),
    ),
)


def exploded_offset(stem: str, side: explode.Side) -> tuple[float, float, float]:
    """The net channel-explode displacement (model mm) of ``stem``'s
    instance on ``side``: every step that moves its family, summed. The
    north-most instance is on the north side too."""
    sides = {None, side} | ({"north"} if side == "north-most" else set())
    offset = [0.0, 0.0, 0.0]
    for step in explode.EXPLODE_STEPS:
        if explode.family(stem) in step.stems and step.side in sides:
            offset["xyz".index(step.axis)] += step.distance_mm
    return offset[0], offset[1], offset[2]


def _exploded(
    point: tuple[float, float, float], stem: str, side: explode.Side
) -> tuple[float, float, float]:
    dx, dy, dz = exploded_offset(stem, side)
    return point[0] + dx, point[1] + dy, point[2] + dz


# At 1:7 the exploded view shows the small hardware at the bracket and keeper
# ends too small and dark to tell apart (r7 machinist review), so the pulled
# out channel's end hardware (the instances the balloons pin) is enlarged,
# exploded, beside the BOM.
# Each detail is centred on its exploded bore centre; the radii hold the
# exploded set screw, hold-down or foot screw and (the bracket's) the north
# washer, 29 to 40 mm from those centres in the isometric (estimated from the
# spec dimensions, with margin).
EXPLODED_DETAIL_SCALE = (1, 2)
EXPLODED_DETAIL_X = 0.392  # the column between the BOM and the right border
NORTH_BRACKET_DETAIL = BankView(
    "DETAIL B",
    EXPLODED_DETAIL_SCALE,
    _exploded((_PIVOT_X, _PIVOT_Y, PIVOT_BRACKET_Z[1]), explode.BRACKET, "north"),
    (EXPLODED_DETAIL_X, 0.240),
    frozenset(
        {
            explode.BRACKET,
            explode.BRACKET_SET_SCREW,
            explode.BRACKET_HOLD_DOWN,
            explode.WASHER,
        }
    ),
    crop_radius_mm=44.0,
    parts=items_text(
        (explode.BRACKET, explode.BRACKET_SET_SCREW, explode.BRACKET_HOLD_DOWN, explode.WASHER),
        compact=True,
    ),
    sheet_scale=(1, 7),
    orientation="*Isometric",
    exploded=True,
    letter="B",
    # Lower left: at the upper right the letter sat over the rocker bank's
    # stack beside the circle, where the machinist review (PR #1605) could not
    # tell which boundary it named; the lower left of the circle is clear.
    letter_corner=(-1, -1),
)
# The north keeper's balloons (items for MHA-CH-07 and its VN-52/VN-55 screws)
# sit on this enlargement, not on the 1:7 view: there the north keeper stands
# in front of the near-black rocker bank, so their leaders ran across the
# shaded stack and their arrowheads were lost in it (#1895 machinist review,
# DETAIL C). Here every leader runs over open paper to a part drawn at 1:2.
# The column is 56 mm wide, so the ring stays above the keeper: the farm read
# this view's outline 24.1 x 44.1 mm about the crop centre, and the three
# attachments (the crown apex and the two lifted screws) lie above it. 20 mm
# lower than the r7 spot, the ring's top balloon (about 37 mm over the centre)
# clears DETAIL B's label, and its label stays above the title block.
NORTH_KEEPER_DETAIL = BankView(
    "DETAIL C",
    EXPLODED_DETAIL_SCALE,
    _exploded(
        (_FULCRUM_X, _FULCRUM_Y, FULCRUM_KEEPER_CENTRE_Z + KEEPER_Z_OFF),
        explode.KEEPER,
        "north",
    ),
    (EXPLODED_DETAIL_X, 0.150),
    frozenset(_KEEPER_DETAIL_STEMS),
    crop_radius_mm=36.0,
    parts=items_text(_KEEPER_DETAIL_STEMS, compact=True),
    sheet_scale=(1, 7),
    orientation="*Isometric",
    exploded=True,
    letter="C",
    # Lower right: at the upper right, lever balloon 14's leader ran through
    # the letter (r8 layout audit, leader-through-text); r7's leaders pass
    # 10 mm clear of the lower right.
    letter_corner=(1, -1),
)
EXPLODED_DETAILS = (NORTH_BRACKET_DETAIL, NORTH_KEEPER_DETAIL)
# The partial views with a viewing arrow on sheet 1, and every lettered view.
ARROWED_VIEWS = (ROCKER_BANK, LEVER_BANK, KEEPER_PLAN, HOOKUP)
LETTERED_VIEWS = (*EXPLODED_DETAILS, SOUTH_END, *ARROWED_VIEWS)
KEEPER_DETAIL_BALLOON_STEMS = NORTH_KEEPER_DETAIL.stems
# Inside the 56 mm column: a 10 mm ring margin keeps a right-hand balloon
# inside the border and the upper-left one 10 mm clear of the BOM.
KEEPER_DETAIL_BALLOON_MARGIN = 0.010
# The keeper's leader lands on the crown apex of its INNER lug face (part
# frame, build_ch_fulcrum_keeper: +x outboard, so the north keeper's x runs
# with machine +z). In the isometric that apex is the crown's back
# silhouette, drawn against open paper, and it projects right of both lifted
# screws (the set screw on the lug mid-plane, the foot screw 8 outboard), so
# the keeper's ring slot is the right-most and its leader crosses neither.
KEEPER_BALLOON_POINT_MM = (-KEEPER_LUG_HALF_T, KEEPER_CROWN_TOP_Y, 0.0)
BALLOON_POINTS_MM = {
    PIVOT_SHAFT_STEM: PIVOT_SHAFT_BALLOON_POINT_MM,
    explode.BRACKET: BRACKET_BALLOON_POINT_MM,
    explode.KEEPER: KEEPER_BALLOON_POINT_MM,
}
# The north bracket cluster (DETAIL B) is lifted 570 up out of the hanging
# rocker arms (ch_channel_explode_spec), so off its shaft it read as part of
# the lever bank (#1660 r3, rule 22: show which face mates to which). Its
# explode trail, a black phantom line along the path its steps moved it,
# ties it back to the MHA-CH-05 north end (draw_pn_pen_assembly's trails).
TRAIL_LINE_STYLE = 2  # swLineStyles_e.swLinePHANTOM
TRAIL_COLOR = 0  # COLORREF black, the views' outline colour
_STACK_MID = (asm.PIVOT_CHAIN_Z[2] + asm.PIVOT_CHAIN_Z[3]) / 2.0
_SPRING_MID = (asm.PIVOT_CHAIN_Z[0] + asm.PIVOT_CHAIN_Z[1]) / 2.0
_LUG_MID = sum(asm.LUG_INNER_FACE_Z) / 2.0
STACK_KEEP = {
    asm.STACK_LENGTH_DIMENSION: ROCKER_BANK.sheet_xy(_STACK_MID, _PIVOT_Y + 40.0)
}
# Above the 8 mm crop circle: at +6 the circle's arc crossed the callout
# text (r7 layout audit, text-on-line). South of the ear-side extension line,
# not between the two: centred on the 0.60 gap the text sat on its own
# dimension line and the washer-side extension line rose into it (b9ae
# machinist review). 6.5 mm south of the ear face puts the callout's ~40 mm
# block wholly south of that line.
SPRING_KEEP = {
    asm.SPRING_SET_DIMENSION: SOUTH_END.sheet_xy(
        asm.PIVOT_CHAIN_Z[0] - 6.5, _PIVOT_Y + 9.5
    )
}
# Detail A names the four bodies the spring set is read against (b9ae machinist
# review: the caption listed them, nothing in the view said which outline was
# which): (text, text upper-left as an offset from the detail's centre, pointer
# tip in the detail's plane as machine (z, y)). The hub to the left of the
# circle, above the axis; the washer, spring and ear to the right, under the
# set dimension's text, rows in their tips' top-to-bottom order so no two
# leaders cross, each tip below the axis so no leader crosses the set
# dimension's extension lines (they run from the axis up).
_WASHER_MID = sum(asm.SOUTH_WASHER_Z) / 2.0
DETAIL_POINTERS = tuple(
    (
        text,
        (SOUTH_END.centre[0] + dx, SOUTH_END.centre[1] + dy_text),
        SOUTH_END.sheet_xy(z, _PIVOT_Y + dy),
    )
    for text, (dx, dy_text), z, dy in (
        (
            f"{BOM_PART_NUMBERS['ch-rocker-arm']}\nHUB",
            (-0.054, 0.033),
            asm.PIVOT_CHAIN_Z[2] + 1.0,
            3.0,
        ),
        (
            f"{BOM_PART_NUMBERS[explode.WASHER]} WASHER",
            (0.038, 0.023),
            _WASHER_MID,
            -1.5,
        ),
        (
            f"{BOM_PART_NUMBERS[explode.BANK_SPRING]} SPRING",
            (0.038, 0.010),
            _SPRING_MID,
            -3.0,
        ),
        (
            f"{BOM_PART_NUMBERS[explode.BRACKET]} EAR",
            (0.038, -0.003),
            asm.PIVOT_CHAIN_Z[0] - 3.0,
            -4.5,
        ),
    )
)
LUG_KEEP = {asm.LUG_SPAN_DIMENSION: LEVER_BANK.sheet_xy(_LUG_MID, _FULCRUM_Y + 32.0)}
# Rule 23: every stake is in a view (round 2 reviews: steps 30 and 59 staked
# "AT 2 POINTS" and no view showed where). Each set screw's tap enters at the
# top of its ear or keeper on the part's mid-plane; the two stake points sit
# either side of the mouth along the shaft, on the flat top line the bank
# view shows edge-on. The pointer lands on the right-hand (south) part's tap
# mouth; its text stands above the view's settings callout, left of the steps
# column.
STAKE_POINTER_TEXT_XY = {"VIEW D": (0.145, 0.250), "VIEW E": (0.145, 0.262)}


def stake_points(shaft: str) -> str:
    """Where the two stake points go, as the step and the pointer say it."""
    return f"2 POINTS, ONE EACH SIDE ALONG {item(shaft)}"


def _stake_pointer(
    view: BankView, set_screw: str, shaft: str, tip_zy: tuple[float, float]
) -> tuple[str, tuple[float, float], tuple[float, float]]:
    text = f"STAKE EACH {item(set_screw)} TAP\nMOUTH AT {stake_points(shaft)}"
    text = text.replace(", ONE EACH SIDE ALONG", ", ONE\nEACH SIDE ALONG")
    return (text, STAKE_POINTER_TEXT_XY[view.title], view.sheet_xy(*tip_zy))


ROCKER_POINTERS = (
    _stake_pointer(
        ROCKER_BANK,
        explode.BRACKET_SET_SCREW,
        "ch-pivot-shaft",
        (PIVOT_BRACKET_Z[0], _PIVOT_Y + BRACKET_APEX_ABOVE_BORE),
    ),
)
LEVER_POINTERS = (
    _stake_pointer(
        LEVER_BANK,
        explode.KEEPER_SET_SCREW,
        "ch-fulcrum-shaft",
        (
            FULCRUM_KEEPER_CENTRE_Z - KEEPER_Z_OFF,
            _FULCRUM_Y + KEEPER_CROWN_TOP_Y - KEEPER_SHAFT_AXIS_H,
        ),
    ),
)
# swDimensionTextParts_e compartments.
CALLOUT_TEXT_PART = 3  # swDimensionTextCalloutAbove
REFERENCE_PREFIX_PART = 1  # swDimensionTextPrefix
REFERENCE_SUFFIX_PART = 2  # swDimensionTextSuffix
BROKEN_LINE_ALIGNED_TEXT = 3  # swDisplayDimensionLeaderText_e.swBrokenLeaderAlignedText
if any("\n" in text for text in notes.DIMENSION_CALLOUTS.values()):
    raise AssertionError("an above-callout with a line break does not print")


if not asm.KEEPER_SOCKET_XZ[1] < asm.LUG_INNER_FACE_Z[0] < asm.LUG_INNER_FACE_Z[1]:
    raise AssertionError("the keeper plan's front face is not the right end's")


@dataclass(frozen=True)
class StepColumn:
    """One column a step group flows into: its sheet, its top-left note
    point (sheet m) and the lowest y a printed line may reach."""

    sheet: str
    xy: tuple[float, float]
    bottom: float

    @property
    def capacity(self) -> int:
        """Printed lines the column holds."""
        return int((self.xy[1] - self.bottom) / NOTE_LINE_PITCH)


_RIGHT_FOOT = _TEMPLATE.title_block_top_m + STEPS_FOOT_CLEARANCE
_BORDER_FOOT = BORDER + STEPS_FOOT_CLEARANCE
# Sheet 3: right of view D. Sheet 4: the full-height left column, detail A
# right of it. Sheet 5: right of views E and F. Sheet 6: the full-height left
# column, then under view G's label on the right (round 1 review: balanced
# sheets, no lone step in an empty half).
_HOOKUP_LABEL_FOOT = (
    HOOKUP_BOTTOM_Y - 0.004 - len(HOOKUP.label_text.splitlines()) * NOTE_LINE_PITCH
)
ROCKER_COLUMNS = (
    StepColumn(SHEET_NAMES[2], (STEPS_RIGHT_X, STEPS_TOP_Y), _RIGHT_FOOT),
    StepColumn(SHEET_NAMES[3], (STEPS_LEFT_X, STEPS_TOP_Y), _BORDER_FOOT),
)
LEVER_COLUMNS = (
    StepColumn(SHEET_NAMES[4], (STEPS_RIGHT_X, STEPS_TOP_Y), _RIGHT_FOOT),
    StepColumn(SHEET_NAMES[5], (STEPS_LEFT_X, STEPS_TOP_Y), _BORDER_FOOT),
    StepColumn(SHEET_NAMES[5], (STEPS_RIGHT_X, _HOOKUP_LABEL_FOOT - 0.008), _RIGHT_FOOT),
)


# A reference word and its number or letter (ITEM 10, STEP 5, VIEW D) print
# on one line: wrapped with a placeholder space textwrap never breaks at.
_REFERENCE_SPACE = re.compile(r"\b(ITEM|STEP|SHEET|VIEW|DETAIL) (?=\w)")
_UNBROKEN_SPACE = "\x00"


def _wrapped_step(key: str, text: str) -> list[str]:
    lines = textwrap.wrap(
        _REFERENCE_SPACE.sub(rf"\1{_UNBROKEN_SPACE}", text),
        width=STEPS_LINE_WIDTH,
        initial_indent=f"{steps.step_number(key)}. ",
        subsequent_indent="   ",
        # A part number never splits at its hyphens across two lines.
        break_on_hyphens=False,
    )
    if len(lines) > STEP_MAX_LINES:
        raise AssertionError(f"step {key!r} prints {len(lines)} lines, over six")
    return [line.replace(_UNBROKEN_SPACE, " ") for line in lines]


def flow_steps(
    heading: str,
    keys: tuple[str, ...],
    text: dict[str, str],
    columns: tuple[StepColumn, ...],
) -> tuple[tuple[StepColumn, str], ...]:
    """Flow ``keys``' wrapped steps down ``columns`` in order: one blank line
    between consecutive steps (user request), a step never split, each
    column headed by ``heading`` (its continuations ``heading (CONT.)``).
    Columns left over stay empty."""
    blocks: list[tuple[StepColumn, str]] = []
    remaining = iter(columns)
    column = next(remaining)
    lines = [heading]
    for key in keys:
        step = _wrapped_step(key, text[key])
        gap = [""] if len(lines) > 1 else []
        if len(lines) + len(gap) + len(step) > column.capacity:
            if len(lines) == 1:
                raise AssertionError(f"step {key!r} does not fit an empty column")
            blocks.append((column, "\n".join(lines)))
            column = next(remaining, None)  # type: ignore[arg-type]
            if column is None:
                raise AssertionError(f"{heading} overflows its columns at {key!r}")
            lines, gap = [f"{heading} (CONT.)"], []
        lines += gap + step
    blocks.append((column, "\n".join(lines)))
    return tuple(blocks)


# The pivot shaft's tip setting prints .XXX (.050 TO .070).
TIP_SET_PLACES = 3
# The lever bank's end-play leaf prints .XXX, the .001 grid a feeler set is
# sold in.
FEELER_LEAF_PLACES = 3
# The right bracket is set by DRO off a test-indicator zero on its own foot
# end, taken with its ear on the right washer before the wave spring goes on
# (#2337: the spring covers all but .004 of the washer face, so no feeler leaf
# can bear on it beside the spring). The washer, the hub stack, the ear and
# the left ear all cancel: the gap's set error is the two indicator nulls on
# that one face, half a division each (the shop indicator's placeholder
# resolution, as MHA-PD-00 step 10 charges it), and the DRO over the move,
# which must stay inside the detail A band (the band, at the spring-back
# check, is the acceptance).
INDICATOR_DIVISION_MM = 0.0127  # .0005: the shop's dial test indicator
DRO_ACCURACY_MM = 0.00508  # .0002: the PM-30MV DRO, vendor-stated (shop inventory)
SPRING_SET_ERROR_MM = 2.0 * INDICATOR_DIVISION_MM / 2.0 + DRO_ACCURACY_MM
if SPRING_SET_ERROR_MM > ROCKER_SPRING_SET_BAND:
    raise AssertionError("the DRO indicator set misses the detail A spring-set band")


def _fitup_text() -> dict[str, str]:
    """Every step's text, keyed as ``ch_channel_assembly_steps.SEQUENCE``."""
    # Literal stems, so the config-dependency analysis reads exactly these rows.
    arm_number = _config.parts("ch-rocker-arm")["number"]
    keeper_number = _config.parts("ch-fulcrum-keeper")["number"]
    support = _config.parts("fr-rocker-arm-support")["number"]
    top_frame = _config.parts("fr-top-frame")["number"]
    shaft, fulcrum_shaft = item("ch-pivot-shaft"), item("ch-fulcrum-shaft")
    bracket, pivot_set_screw = item(explode.BRACKET), item(explode.BRACKET_SET_SCREW)
    washer, spring = item(explode.WASHER), item(explode.BANK_SPRING)
    hold_down, keeper = item(explode.BRACKET_HOLD_DOWN), item(explode.KEEPER)
    foot_screw = item(explode.KEEPER_FOOT_SCREW)
    fulcrum_set_screw = item(explode.KEEPER_SET_SCREW)
    arm, rod, bar = item("ch-rocker-arm"), item(explode.ROD), item(explode.BAR)
    lever, pin = item("ch-channel-lever"), item("ch-rod-pivot-pin")
    bar_pin, channel_spring = item(explode.BAR_PIN), item(SPRING_STEM)
    anchor, anchor_nut = item(explode.HOOK), item(explode.ANCHOR_NUT)
    rocker_view, lever_view = ROCKER_BANK.title, LEVER_BANK.title
    plan_view, hookup_view = KEEPER_PLAN.title, HOOKUP.title
    detail = f"{SOUTH_END.title}, SHEET {SHEET_NAMES.index(DETAIL_SHEET) + 1}"

    def n(key: str) -> int:
        return steps.step_number(key)

    # Every hub comes at or over its print length (its band is upper-only),
    # so the shortest stack the part band allows still meets the acceptance's
    # low limit: the stack can only be long, and the re-face step covers that.
    # It faces the longest hubs on the end away from datum G, the face each
    # arm registers on in the stack (draw_ch_rocker_arm), keeping each at or
    # over its print. Checked on the PRINTED limits, as a fitter reads both
    # sheets (#2330): twenty .3000 hubs at their low limit make exactly the
    # stack's printed 6.000 low limit.
    hub_low_dev, _ = printed_deviations(
        HUB_LENGTH,
        ARM_DRAWING_PRECISION["Hub"]["HubLength"],
        (HUB_LENGTH_BAND[1], HUB_LENGTH_BAND[0]),
        unit=ARM_UNIT,
    )
    stack_low_dev, _ = printed_deviations(
        STACK_L20_ACCEPT[0],
        asm.DRAWING_PRECISION[asm.PIVOT_FEATURE][asm.STACK_LENGTH_DIMENSION],
        asm.DIMENSION_TOLERANCES[asm.STACK_LENGTH_DIMENSION],
        unit=asm.UNIT,
    )
    hub_low = HUB_LENGTH + hub_low_dev
    stack_low = STACK_L20_ACCEPT[0] + stack_low_dev
    if COUNT * hub_low < stack_low - 1e-9:
        raise AssertionError(
            "the re-face step covers only a long stack, but twenty hubs at "
            "their printed low limit fall under the stack's printed low limit"
        )
    # The pivot shaft comes finished, domed both ends to its overall length
    # (ch_pivot_shaft_spec): its left tip set DOME_HEIGHT proud of the left
    # ear, within SHAFT_TIP_SET_BAND, puts both flats under their screws
    # (rocker_bank_layout checks the worst case).
    tip_low, tip_high = (
        render_number(
            (DOME_HEIGHT + sign * SHAFT_TIP_SET_BAND) / LENGTH_UNITS[asm.UNIT],
            asm.UNIT,
            TIP_SET_PLACES,
        )
        for sign in (-1.0, 1.0)
    )
    # Each keeper lug is set off the top-frame rail web under it (its column's
    # socket axis) in X and off the frame's hole-station origin line, the
    # upper socket centres, in Z (Main's ruling): the lug centre on the
    # fulcrum line, its inner face off the front socket line. The frame is not
    # in this assembly, so view F draws both datums and prints the three
    # settings, each banded (owner ruling X1+B1, b9ae review).
    if abs(LEVER_FULCRUM_XY[0] - COLUMN_X - KEEPER_FITUP_X_FROM_WEB_MM) > 1e-9:
        raise AssertionError("KEEPER_FITUP_X_FROM_WEB_MM is off the fulcrum line")
    front_face, rear_face = KEEPER_INNER_FACE_FROM_FRONT_SOCKET_MM
    # The pair is reamed at the spacing KEEPERS_SET_KEY sets it to (Main's
    # ruling): view E's reference lug span.
    if abs(rear_face - front_face - KEEPER_INNER_FACE_SPAN_MM) > 1e-9:
        raise AssertionError("the pair-ream span is not the fit-up span")
    # The lever bank is never fitted like the rocker stack: the bars on the
    # arms locate it, and twenty hubs at the top of their band still leave end
    # play between the lugs at the extremes of both inner-face bands (#1660
    # r2). The lever-bank-slides check gauges that play on a feeler leaf: the
    # worst case rounded down to .01, so a bank inside its bands always passes
    # (moved here from the MHA-CH-02 hub callout, FoChFab2 round 1).
    lever_stack_max = COUNT * (LEVER_HUB_LENGTH + LEVER_HUB_LENGTH_BAND[0])
    lug_span_min = KEEPER_INNER_FACE_SPAN_MM - 2.0 * KEEPER_FITUP_LOCATION_BAND_MM
    play_min = (lug_span_min - lever_stack_max) / LENGTH_UNITS[asm.UNIT]
    end_play_leaf = math.floor(play_min * 100.0) / 100.0
    if end_play_leaf <= 0.0:
        raise AssertionError(
            "the lever bank must slide between the lugs, but the longest hubs "
            "leave no gaugeable play in the shortest lug span"
        )
    end_play_text = render_number(end_play_leaf, asm.UNIT, FEELER_LEAF_PLACES)
    return {
        # The hub stack is proved on the shaft first, while the arms are
        # loose; each rod + arm pair is then pinned at the bench, before the
        # drive-train cylinder stack captures the rod rings in their cams.
        "rocker-stack-accepted": (
            f"STACK THE {COUNT} {arm} ROCKERS ON {shaft} AS {rocker_view} SHOWS, "
            "HUBS IN CONTACT."
        ),
        "rocker-stack-measured": (
            "MEASURE THE STACK OVER ITS END HUB FACES WITH A CALIPER: IT MUST "
            f"MEET THE {rocker_view} STACK DIMENSION."
        ),
        "rocker-stack-refaced": (
            "IF IT IS LONG, FACE THE LONGEST HUBS ON THEIR ENDS AWAY FROM DATUM "
            f"G ({arm_number} DRAWING), NONE BELOW ITS PRINTED LENGTH, AND "
            f"RETURN TO STEP {n('rocker-stack-measured')}."
        ),
        "rockers-kept-in-order": (
            f"SLIDE THE ROCKERS OFF {shaft} IN ORDER AND KEEP THAT ORDER."
        ),
        steps.RODS_PINNED_KEY: (
            f"BEFORE {steps.CYLINDER_STACK_REF}, AT THE BENCH: PRESS ONE {pin} "
            f"PIN THROUGH EACH {rod} ROD FORK AND THE PIVOT HOLE OF ONE {arm}, "
            "FAR TINE BACKED."
        ),
        "rod-pins-dressed": f"DRESS BOTH ENDS OF EACH {pin} FLUSH WITH THE TINES.",
        "rod-pins-held": f"CHECK EACH {pin} DOES NOT SLIDE IN ITS FORK BY HAND.",
        "rod-arms-swing": (
            f"CHECK EACH {arm} SWINGS FREE ON ITS PIN UNDER ITS OWN WEIGHT."
        ),
        # A press whose part slides in by hand is a slip fit (rule 23): the
        # press-fit ruling (ch_rod_pivot_pin_spec) is kept by a new pin.
        "rod-pin-remade": (
            f"IF AN {pin} SLID IN BY HAND, PRESS IT OUT, REMAKE IT TO THE PRESS "
            f"SIZE ON ITS DRAWING AND RETURN TO STEP {n(steps.RODS_PINNED_KEY)}."
        ),
        "north-bracket-held": (
            f"CHECK THE LEFT {bracket} OF {rocker_view}, SET AT "
            f"{steps.NORTH_BRACKET_SET_REF}, DOES NOT TURN BY HAND."
        ),
        "arms-swung-up": f"SWING EACH {arm} UP ON ITS {rod}.",
        "north-ear-datum": (
            f"PUSH {shaft}, FLATS UP, THROUGH THE LEFT {bracket} EAR, THEN THROUGH "
            f"THE {washer} WASHER MEASURED AT {steps.NORTH_BRACKET_SET_REF}."
        ),
        "rocker-hubs-threaded": (
            f"PUSH {shaft} ON THROUGH THE {arm} HUBS, LEFT TO RIGHT IN THE ORDER "
            f"KEPT AT STEP {n('rockers-kept-in-order')}."
        ),
        "south-washer-fitted": (
            f"SLIP THE OTHER {washer} ONTO {shaft} AGAINST THE RIGHT-HAND HUB."
        ),
        # #2337: the right bracket is zeroed on its foot end with the ear on
        # the washer before the spring covers it, on the mill the left ear was
        # set on; it comes off for the spring, goes back on under a light clamp
        # and is tapped to that zero at the spring set's DRO offset.
        "south-bracket-on-washer": (
            f"WITH THE BASE ON THE MILL AS AT {steps.NORTH_BRACKET_SET_REF}, "
            f"STAND THE RIGHT {bracket} ON {support} WITH {shaft} IN ITS EAR AND "
            f"THE EAR PUSHING {washer} AND THE BANK LEFT."
        ),
        "south-bracket-zeroed": (
            "WITH A TEST INDICATOR IN THE SPINDLE, READ ZERO ON THE RIGHT "
            f"{bracket} FOOT END AND ZERO THE DRO ALONG {shaft} THERE."
        ),
        "south-bracket-slid-off": (
            f"MOVE THE INDICATOR CLEAR AND SLIDE THE RIGHT {bracket} OFF {shaft}, "
            "LEAVING THE BASE UNMOVED ON THE TABLE."
        ),
        # Machinist review (#2108): the BOM carries one spring, so its run
        # along the shaft is a check, with its own remedy.
        "bank-spring-checked": (
            f"CHECK THE {spring} WAVE SPRING SLIDES FREE ALONG {shaft}."
        ),
        "bank-spring-replaced": (
            f"IF IT BINDS, REPLACE THAT {spring} AND REPEAT STEP "
            f"{n('bank-spring-checked')}."
        ),
        "bank-spring-fitted": f"FIT {spring} ON {shaft} AGAINST THAT {washer}.",
        # The light clamp holds the bracket against the spring while it is
        # tapped to the indicator (Codjiflo r1 on #2489: the spring alone
        # leaves nothing holding it at the target).
        "south-bracket-refitted": (
            f"STAND THE RIGHT {bracket} BACK ON {support} WITH {shaft} IN ITS EAR "
            "AND CLAMP IT LIGHTLY."
        ),
        # The spring-back check runs while the bracket is only clamped, so a
        # failed check is re-set before anything is drilled, tapped or staked
        # (machinist review, PR #1605).
        "south-bracket-spring-set": (
            f"WITH THE DRO AT THE SPRING SET OF {detail}, RIGHT OF THE STEP "
            f"{n('south-bracket-zeroed')} ZERO, TAP THE FOOT END UNTIL THE "
            "INDICATOR READS ZERO ON IT."
        ),
        "south-bracket-clamped": (
            f"TIGHTEN THE CLAMP ON THE RIGHT {bracket}, KEEPING THE INDICATOR AT ZERO."
        ),
        "spring-back-checked": (
            "CHECK THE BANK, PUSHED RIGHT AND RELEASED, SPRINGS BACK AGAINST "
            f"THE LEFT {washer}."
        ),
        "south-bracket-reset": (
            "IF IT DOES NOT, EASE THE CLAMP AND RETURN TO STEP "
            f"{n('south-bracket-spring-set')}."
        ),
        "south-foot-transferred": (
            f"STILL CLAMPED, TRANSFER-DRILL THE RIGHT {bracket} FOOT HOLE INTO "
            f"THE {support} RAIL."
        ),
        "south-foot-tapped": f"TAP THAT HOLE TO THE {support} DRAWING.",
        "south-bracket-screwed": (
            f"SCREW THE RIGHT {bracket} DOWN WITH ONE {hold_down}."
        ),
        "south-bracket-unclamped": "REMOVE THE CLAMP.",
        "south-bracket-held": f"CHECK THE RIGHT {bracket} DOES NOT TURN BY HAND.",
        "shaft-set": (
            f"SLIDE {shaft} UNTIL ITS LEFT TIP STANDS {tip_low} TO {tip_high} "
            "PROUD OF THE LEFT EAR'S OUTER FACE (CALIPER DEPTH ROD)."
        ),
        # drawing-guidelines.md rule 23: staked like the keeper set screws
        # (fulcrum-set-screws-staked). The Loctite waiver was retired on
        # 2026-10-16 under the user's standing no-threadlocker rule.
        "set-screws-driven": (
            f"WITH {shaft} FLATS UP, SNUG ONE {pivot_set_screw} DOWN THE TAP AT "
            f"THE TOP OF EACH {bracket} EAR ONTO ITS FLAT, LEFT EAR FIRST."
        ),
        steps.PIVOT_SET_SCREWS_STAKED_KEY: (
            f"STAKE THE MOUTH OF EACH {pivot_set_screw} TAP AT "
            f"{stake_points('ch-pivot-shaft')} ({ROCKER_BANK.title})."
        ),
        "pivot-shaft-held": f"CHECK {shaft} DOES NOT TURN OR SLIDE BY HAND.",
        # The keepers are reamed as a pair at the bench, then each is finished
        # to its own print on the bore this makes: MHA-CH-07 sizes the
        # full-radius top and places the set-screw tap on the bore axis. The
        # steps carry none of that part data (rule 24; #1660 r2).
        "keepers-clamped": (
            f"CLAMP BOTH {keeper} KEEPERS ON A SURFACE PLATE, FEET OUTWARD, "
            f"INNER LUG FACES AT THE {lever_view} LUG SPAN, BORE AXES PARALLEL "
            "TO THE PLATE."
        ),
        steps.KEEPERS_PAIR_REAMED_KEY: (
            f"STILL CLAMPED, MAKE BOTH {keeper} BORES TO THEIR DRAWING IN ONE "
            "SETUP, IN LINE."
        ),
        "keeper-bores-checked": (
            f"CHECK {fulcrum_shaft} SLIDES FREELY THROUGH BOTH BORES."
        ),
        "keeper-tops-finished": (
            f"FINISH EACH {keeper}'S FULL-RADIUS TOP ON ITS BORE AXIS, TO THE "
            f"{keeper_number} DRAWING."
        ),
        "keeper-taps-made": (
            f"MAKE EACH {keeper}'S {fulcrum_set_screw} TAP ON ITS BORE AXIS, TO "
            f"THE {keeper_number} DRAWING."
        ),
        "keepers-on-frame": (
            f"WITH {top_frame} ON THE MILL, STAND BOTH {keeper} ON ITS RAIL AS "
            f"{plan_view} SHOWS, FEET OUTWARD, {fulcrum_shaft} THROUGH BOTH BORES."
        ),
        steps.KEEPERS_SET_KEY: (
            f"BY DRO, SET EACH LUG CENTRE OFF THE RAIL WEB CENTRE, TO {plan_view}."
        ),
        "keeper-faces-set": (
            "BY DRO, SET THE LUG INNER FACES OFF THE LINE OF THE UPPER SOCKET "
            f"CENTRES, TO {plan_view}."
        ),
        "keepers-clamped-on-frame": f"CLAMP BOTH {keeper} TO THE RAIL.",
        "keeper-feet-transferred": (
            f"TRANSFER-DRILL EACH {keeper} FOOT HOLE INTO THE RAIL."
        ),
        "keeper-feet-tapped": f"TAP THOSE HOLES TO THE {top_frame} DRAWING.",
        steps.KEEPERS_SCREWED_KEY: (
            f"SCREW EACH {keeper} DOWN WITH ONE {foot_screw}."
        ),
        "keepers-unclamped": "REMOVE THE CLAMPS.",
        "keepers-held": f"CHECK EACH {keeper} DOES NOT TURN BY HAND.",
        "bar-notches-set": (
            f"AT THE BENCH, SET THE TOP NOTCH OF EACH {bar} BAR ASTRIDE ONE "
            f"{lever} LEVER."
        ),
        steps.BARS_PINNED_KEY: (
            f"PRESS ONE {bar_pin} PIN THROUGH THE CHEEKS OF EACH {bar} AND THE "
            f"HOLE OF ITS {lever}, FAR CHEEK BACKED."
        ),
        "bar-pins-dressed": (
            f"DRESS BOTH ENDS OF EACH {bar_pin} FLUSH WITH THE CHEEKS."
        ),
        "bar-pins-held": f"CHECK EACH {bar_pin} DOES NOT SLIDE IN ITS BAR BY HAND.",
        "bars-swing": f"CHECK EACH {bar} SWINGS FREE ON ITS PIN UNDER ITS OWN WEIGHT.",
        "bar-pin-remade": (
            f"IF AN {bar_pin} SLID IN BY HAND, PRESS IT OUT, REMAKE IT TO THE "
            "PRESS SIZE ON ITS DRAWING AND RETURN TO STEP "
            f"{n(steps.BARS_PINNED_KEY)}."
        ),
        "fulcrum-shaft-withdrawn": (
            f"DRAW {fulcrum_shaft} OUT OF BOTH {keeper} TO THE LEFT ({lever_view})."
        ),
        steps.LEVER_BANK_THREADED_KEY: (
            f"PUSH {fulcrum_shaft} BACK THROUGH THE LEFT {keeper}, THEN THROUGH "
            f"THE {COUNT} {lever} LEVERS, ONE ABOVE EACH {arm}, THEN THROUGH THE "
            f"RIGHT {keeper}."
        ),
        "bar-feet-seated": (
            f"SEAT THE FOOT NOTCH OF EACH {bar} ASTRIDE THE ARM OF THE {arm} "
            "BELOW IT."
        ),
        "levers-swing": f"CHECK EVERY {lever} SWINGS FREE ON {fulcrum_shaft}.",
        "lever-bank-slides": (
            f"CHECK THE LEVERS SLIDE TOGETHER ALONG {fulcrum_shaft}: PUSHED "
            f"AGAINST ONE {keeper} LUG, THEY LEAVE ROOM FOR A {end_play_text} "
            "FEELER GAUGE LEAF AT THE OTHER."
        ),
        "fulcrum-flats-aligned": (
            f"SLIDE {fulcrum_shaft} UNTIL EACH OF ITS FLATS LIES UP, UNDER THE "
            f"{fulcrum_set_screw} TAP OF ITS {keeper}."
        ),
        steps.FULCRUM_SET_SCREWS_DRIVEN_KEY: (
            f"TIGHTEN ONE {fulcrum_set_screw} SET SCREW ONTO EACH FLAT."
        ),
        steps.SET_SCREWS_STAKED_KEY: (
            f"STAKE THE MOUTH OF EACH {fulcrum_set_screw} TAP AT "
            f"{stake_points('ch-fulcrum-shaft')} ({LEVER_BANK.title})."
        ),
        "fulcrum-shaft-held": f"CHECK {fulcrum_shaft} DOES NOT TURN OR SLIDE BY HAND.",
        steps.SPRINGS_HOOKED_KEY: (
            f"HOOK THE TOP LOOP OF EACH {channel_spring} SPRING THROUGH THE "
            f"SPRING HOLE OF ITS {lever} ({hookup_view})."
        ),
        # The anchors thread into the summing plate and are jammed by their
        # nuts at MHA-HA-00, which owns that joint, its lock and its setting
        # (rule 23 at the package boundary: cited by its step).
        "spring-bottom-loops-left": (
            f"LEAVE EACH BOTTOM LOOP FREE: {steps.HA_ANCHORS_SET_REF} THREADS "
            f"EACH {anchor} ANCHOR, JAMS IT WITH ITS {anchor_nut} NUT AND HOOKS "
            "THE LOOP INTO IT."
        ),
    }


FITUP_TEXT = _fitup_text()
if tuple(FITUP_TEXT) != steps.SEQUENCE:
    raise AssertionError("the step text must follow ch_channel_assembly_steps.SEQUENCE")
FITUP_NOTES = flow_steps(
    "ROCKER BANK FIT-UP", steps.ROCKER_SEQUENCE, FITUP_TEXT, ROCKER_COLUMNS
) + flow_steps("LEVER BANK FIT-UP", steps.LEVER_SEQUENCE, FITUP_TEXT, LEVER_COLUMNS)
FITUP_STEPS = "\n".join(text for _column, text in FITUP_NOTES)


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
        raise RuntimeError(f"failed to place the channel {label}")
    note = _early_bound(note, "INote")
    printed = str(note.GetText() or "").replace("\r\n", "\n").replace("\r", "\n")
    if printed != text:
        raise RuntimeError(f"channel {label} printed as {printed!r}")
    return note


def _view_outline(view: Any, *, label: str) -> tuple[float, float, float, float]:
    outline = tuple(float(value) for value in _early_bound(view, "IView").GetOutline())
    if len(outline) != 4 or outline[2] <= outline[0] or outline[3] <= outline[1]:
        raise RuntimeError(f"{label}: invalid view outline {outline!r}")
    return outline[0], outline[1], outline[2], outline[3]


def _assert_box_on_sheet(box: tuple[float, float, float, float], *, label: str) -> None:
    """The actual native box stays inside the border and outside the title block."""
    x0, y0, x1, y1 = box
    border = (BORDER, BORDER, _TEMPLATE.width_m - BORDER, _TEMPLATE.height_m - BORDER)
    title = (
        _TEMPLATE.title_block_left_m,
        0.0,
        _TEMPLATE.width_m,
        _TEMPLATE.title_block_top_m,
    )
    findings = []
    if x0 < border[0] or y0 < border[1] or x1 > border[2] or y1 > border[3]:
        findings.append(f"leaves the inner border {border}")
    if x1 > title[0] and x0 < title[2] and y0 < title[3] and y1 > title[1]:
        findings.append(f"enters the title block {title}")
    if findings:
        raise RuntimeError(
            f"{label}: outline {(x0, y0, x1, y1)!r} " + "; ".join(findings)
        )


def _assert_view_on_sheet(view: Any, *, margin: float = 0.0, label: str) -> None:
    """Keep the view outline and its balloon margin inside the drawing field."""
    x0, y0, x1, y1 = _view_outline(view, label=label)
    _assert_box_on_sheet(
        (x0 - margin, y0 - margin, x1 + margin, y1 + margin), label=label
    )


def _center_view_outline(
    adapter: Any, view: Any, center: tuple[float, float], *, label: str
) -> None:
    """Translate the actual outline using the current native origin."""
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


def _validate_source(source_model: Any) -> dict[str, str]:
    """The builder-owned explodes exist, the source opens collapsed with
    exactly the contracted families; returns each family's north-most
    instance (nearest the isometric's eye), the one its balloon pins."""
    assembly = _early_bound(source_model, "IAssemblyDoc")
    manager = _early_bound(source_model.ConfigurationManager, "IConfigurationManager")
    configuration = _early_bound(manager.ActiveConfiguration, "IConfiguration")
    if str(configuration.Name) != ASSEMBLY_VIEW_CONFIGURATION:
        raise RuntimeError("channel source must open in its Default configuration")
    for owner, wanted in EXPLODED_VIEW_NAMES.items():
        names = tuple(assembly.GetExplodedViewNames2(owner) or ())
        if names != (wanted,):
            raise RuntimeError(
                f"channel {owner} exploded views {names!r} != {(wanted,)!r}"
            )
    counts: Counter[str] = Counter()
    north: dict[str, tuple[float, str]] = {}
    for raw in tuple(assembly.GetComponents(True) or ()):
        component = _early_bound(raw, "IComponent2")
        stem = _component_stem(component)
        counts[stem] += 1
        total = _early_bound(component.GetTotalTransform(True), "IMathTransform")
        base = _early_bound(component.GetTotalTransform(False), "IMathTransform")
        values = tuple(float(value) for value in base.ArrayData)
        if any(
            abs(float(actual) - expected) > 1e-9
            for actual, expected in zip(total.ArrayData, values, strict=True)
        ):
            raise RuntimeError(
                f"channel source must open collapsed: {component.Name2!r} is displaced"
            )
        z = values[11]
        name = str(component.Name2)
        if stem not in north or z > north[stem][0]:
            north[stem] = (z, name)
    if dict(counts) != BOM_QUANTITIES:
        raise RuntimeError(
            f"channel families {dict(counts)!r} != contract {BOM_QUANTITIES!r}"
        )
    return {stem: name for stem, (_z, name) in north.items()}


_INSERT_COLUMN_AFTER = 3  # swTableItemInsertPosition_After
_INSERT_COLUMN_DEFAULT_WIDTH = 0  # swInsertColumn_DefaultWidth


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
        raise RuntimeError(f"channel BOM has no unique {label} column: {header!r}")
    return matches[0]


def _validate_bom(adapter: Any, table: Any) -> tuple[tuple[str, str], ...]:
    """Rewrite part numbers, prove identities/descriptions/quantities, add the
    registry's VENDOR SKU column after DESCRIPTION; return (stem, item number)
    in BOM order. Material and finish remain on component drawings."""
    table = _early_bound(table, "ITableAnnotation")
    contents = _bom_cells(table)
    rows = len(contents)
    columns = len(contents[0]) if contents else 0
    if rows != len(BOM_COMPONENTS) + 1 or columns < 4:
        raise RuntimeError(
            f"channel BOM is {rows}x{columns}; expected "
            f"{len(BOM_COMPONENTS) + 1} rows and at least four columns"
        )
    header = contents[0]
    for title in ("MATERIAL", BOM_SKU_TITLE):
        if title in (cell.upper() for cell in header):
            raise RuntimeError(f"channel BOM template already has {title!r}")
    item_column = _bom_column(
        header, lambda cell: cell.startswith("ITEM NO"), "ITEM NO."
    )
    part_column = _bom_column(header, lambda cell: cell == "PART NUMBER", "PART NUMBER")
    description_column = _bom_column(
        header, lambda cell: cell == "DESCRIPTION", "DESCRIPTION"
    )
    quantity_column = _bom_column(header, lambda cell: cell.startswith("QTY"), "QTY.")

    actual: dict[str, tuple[int, str, str, str]] = {}
    for row_index, row in enumerate(contents[1:], start=1):
        text = row[part_column].casefold()
        stem = BOM_NORMALIZED_ALIASES.get(text, text)
        if stem in actual:
            raise RuntimeError(f"channel BOM repeats component family {stem!r}")
        actual[stem] = (
            row_index,
            row[item_column],
            row[description_column],
            row[quantity_column],
        )
    if set(actual) != set(BOM_COMPONENTS):
        raise RuntimeError(
            f"channel BOM identities {sorted(actual)!r} != {sorted(BOM_COMPONENTS)!r}"
        )
    items = {values[1] for values in actual.values()}
    if items != {str(item) for item in range(1, len(BOM_COMPONENTS) + 1)}:
        raise RuntimeError(
            f"channel BOM item numbers {sorted(items)!r} are not contiguous"
        )
    # The steps and detail labels name parts by ITEM_NUMBERS.
    misnumbered = {
        stem: values[1]
        for stem, values in actual.items()
        if values[1] != str(ITEM_NUMBERS[stem])
    }
    if misnumbered:
        raise RuntimeError(
            f"channel BOM item numbers {misnumbered!r} differ from ITEM_NUMBERS"
        )
    for stem, (row_index, _item, description, quantity) in actual.items():
        number = BOM_PART_NUMBERS[stem]
        if contents[row_index][part_column] != number:
            if not table.IsCellTextEditable(row_index, part_column):
                raise RuntimeError(
                    f"channel BOM part-number cell for {stem!r} is locked"
                )
            table.SetText2(row_index, part_column, False, number)
        if description != BOM_DESCRIPTIONS[stem]:
            raise RuntimeError(f"channel BOM description mismatch for {stem!r}")
        if quantity != str(BOM_QUANTITIES[stem]):
            raise RuntimeError(
                f"channel BOM quantity for {stem!r} is {quantity!r}, "
                f"expected {BOM_QUANTITIES[stem]}"
            )

    # The parts carry no SKU property; made parts print MADE_PART_SKU.
    if not table.InsertColumn2(
        _INSERT_COLUMN_AFTER,
        description_column,
        BOM_SKU_TITLE,
        _INSERT_COLUMN_DEFAULT_WIDTH,
    ):
        raise RuntimeError("channel BOM refused the VENDOR SKU column")
    column = description_column + 1
    if not table.SetColumnTitle2(column, BOM_SKU_TITLE, False):
        raise RuntimeError("channel BOM VENDOR SKU column title did not set")
    for stem, (row_index, *_rest) in actual.items():
        if not table.IsCellTextEditable(row_index, column):
            raise RuntimeError(f"channel BOM VENDOR SKU cell for {stem!r} is locked")
        table.SetText2(row_index, column, False, BOM_SKUS[stem])

    header = _bom_cells(table)[0]
    widths = {
        "item": _bom_column(
            header, lambda cell: cell.startswith("ITEM NO"), "ITEM NO."
        ),
        "part": _bom_column(header, lambda cell: cell == "PART NUMBER", "PART NUMBER"),
        "description": _bom_column(
            header, lambda cell: cell == "DESCRIPTION", "DESCRIPTION"
        ),
        "sku": _bom_column(header, lambda cell: cell == BOM_SKU_TITLE, BOM_SKU_TITLE),
        "quantity": _bom_column(header, lambda cell: cell.startswith("QTY"), "QTY."),
    }
    if len(header) != len(BOM_COLUMN_WIDTHS) or set(widths) != set(BOM_COLUMN_WIDTHS):
        raise RuntimeError(f"channel BOM columns {header!r} are not the contract")
    for key, column in widths.items():
        width = BOM_COLUMN_WIDTHS[key]
        if abs(float(table.SetColumnWidth(column, width, 0)) - width) > 1e-6:
            raise RuntimeError(f"channel BOM {key} column width did not persist")
    for row in range(rows):
        table.SetRowHeight(row, BOM_ROW_HEIGHT, 0)
    if not adapter.currentModel.EditRebuild3():
        raise RuntimeError("channel BOM rebuild failed")
    settled = _bom_cells(table)
    for stem, (row_index, *_rest) in actual.items():
        for key, text in (("part", BOM_PART_NUMBERS[stem]), ("sku", BOM_SKUS[stem])):
            applied = settled[row_index][widths[key]]
            if applied != text:
                raise RuntimeError(
                    f"channel BOM {key} for {stem!r} reads {applied!r}, expected {text!r}"
                )
    return tuple((stem, actual[stem][1]) for stem in BOM_COMPONENTS)


def _bom_vertical_limits(table: Any) -> tuple[float, float]:
    """Read the top-left-anchored BOM after its rows have grown to fit."""
    table = _early_bound(table, "ITableAnnotation")
    annotation = _early_bound(table.GetAnnotation(), "IAnnotation")
    position = tuple(float(value) for value in annotation.GetPosition())
    heights = tuple(float(table.GetRowHeight(row)) for row in range(int(table.RowCount)))
    if len(position) != 3 or not all(math.isfinite(value) for value in position):
        raise RuntimeError("channel BOM has invalid native position")
    if not heights or any(
        not math.isfinite(height) or height <= 0.0 for height in heights
    ):
        raise RuntimeError("channel BOM has invalid native row heights")
    top = position[1]
    return top - sum(heights), top


def exploded_caption_xy(bom_bottom: float) -> tuple[float, float]:
    """Follow the rebuilt BOM without changing its complete identities."""
    return BOM_ANCHOR[0], bom_bottom - EXPLODED_CAPTION_OFFSET


def _assert_exploded_caption(adapter: Any, table: Any, note: Any) -> None:
    _activate_sheet(adapter, SHEET_NAMES[1])
    bottom, top = _bom_vertical_limits(table)
    extent = tuple(float(value) for value in note.GetExtent())
    if len(extent) != 6 or not all(math.isfinite(value) for value in extent):
        raise RuntimeError(f"channel exploded caption has invalid extent {extent!r}")
    box = (extent[0], extent[1], extent[3], extent[4])
    if box[2] <= box[0] or box[3] <= box[1]:
        raise RuntimeError(f"channel exploded caption has empty extent {extent!r}")
    gap = bottom - box[3]
    _telemetry.info(
        "channel BOM and exploded caption native clearance",
        bom_top_mm=top * 1000.0,
        bom_bottom_mm=bottom * 1000.0,
        caption_box_mm=tuple(value * 1000.0 for value in box),
        caption_gap_mm=gap * 1000.0,
    )
    _assert_box_on_sheet(box, label="channel exploded caption")
    if gap < EXPLODED_CAPTION_MIN_GAP:
        raise RuntimeError(
            f"channel exploded caption has {gap * 1000.0:.3f} mm below the BOM; "
            f"requires {EXPLODED_CAPTION_MIN_GAP * 1000.0:.1f} mm"
        )


def _place_assembled_sheet(adapter: Any) -> None:
    _activate_sheet(adapter, SHEET_NAMES[0])
    views: dict[str, Any] = {}
    for orientation, center, scale in (
        ("*Front", FRONT_CENTER, ASSEMBLED_SCALE),
        ("*Right", RIGHT_CENTER, ASSEMBLED_SCALE),
        ("*Isometric", ISO_CENTER, ASSEMBLED_ISO_SCALE),
    ):
        view = place_view(adapter, str(SOURCE), orientation, *center, scale=scale)
        # The isometric is the drawing's full-detail view.
        role = ViewRole.FULL_DETAIL if orientation == "*Isometric" else ViewRole.PLAIN
        configuration = apply_view_configuration(
            adapter, view, role=role, label=f"channel {orientation}"
        )
        set_view_exploded_state(
            adapter,
            view,
            False,
            configuration=configuration,
            label=f"channel {orientation}",
        )
        _assert_view_on_sheet(view, label=f"channel {orientation}")
        views[orientation] = view
    assert_full_detail_view(adapter, label="channel assembly")
    _add_note_block(
        adapter,
        SHEET_NAMES[0],
        ASSEMBLED_CAPTION,
        ASSEMBLED_CAPTION_XY,
        label="assembled-views caption",
    )
    _add_note_block(
        adapter, SHEET_NAMES[0], ISO_LABEL, ISO_LABEL_XY, label="isometric label"
    )
    _add_view_arrows(adapter, views["*Front"], views["*Right"])


def _add_view_arrows(adapter: Any, front: Any, right: Any) -> None:
    """Viewing arrows for views D-G. D and E (*Right views) look at the
    front view from its right, level with the pivot and fulcrum axes; F (a
    *Top view) looks down on it at the keeper lugs; G (a *Front view) looks
    at the right view from its left, level with the spring hook-up."""
    _, _, front_right, front_top = _view_outline(front, label="channel *Front")
    right_left = _view_outline(right, label="channel *Right")[0]

    def sheet(view: Any, xyz_mm: tuple[float, float, float], bank: BankView):
        xyz = (xyz_mm[0] / 1000.0, xyz_mm[1] / 1000.0, xyz_mm[2] / 1000.0)
        return model_point_in_view(adapter, view, xyz, label=f"{bank.title} arrow")

    pivot_y = sheet(front, ROCKER_BANK.centre_xyz, ROCKER_BANK)[1]
    fulcrum_y = sheet(front, LEVER_BANK.centre_xyz, LEVER_BANK)[1]
    lug_x = sheet(
        front, (asm.KEEPER_LUG_X, _FULCRUM_Y, FULCRUM_KEEPER_CENTRE_Z), KEEPER_PLAN
    )[0]
    hookup_y = sheet(right, HOOKUP.centre_xyz, HOOKUP)[1]
    height, gap, run = VIEW_ARROW_LETTER_HEIGHT, VIEW_ARROW_TIP_GAP, VIEW_ARROW_RUN
    # (bank, parent view, arrow tip, letter's note point: upper left).
    arrows = (
        (
            ROCKER_BANK,
            front,
            (front_right + gap, pivot_y),
            (front_right + gap + run, pivot_y + height / 2.0),
        ),
        (
            LEVER_BANK,
            front,
            (front_right + gap, fulcrum_y),
            (front_right + gap + run, fulcrum_y + height / 2.0),
        ),
        (
            KEEPER_PLAN,
            front,
            (lug_x, front_top + gap),
            (lug_x - height / 3.0, front_top + gap + run + height),
        ),
        (
            HOOKUP,
            right,
            (right_left - gap, hookup_y),
            (right_left - gap - run - height, hookup_y + height / 2.0),
        ),
    )
    for bank, view, tip, text_xy in arrows:
        add_leader_note(
            adapter,
            bank.title.removeprefix("VIEW "),
            text_xy=text_xy,
            attach_xy=tip,
            label=f"{bank.title} viewing arrow",
            view=view,
            height=height,
        )


def _place_exploded_sheet(
    adapter: Any, north_instances: dict[str, str]
) -> Callable[[], None]:
    """The exploded isometric, its BOM (with vendor SKU) and one balloon per
    BOM row on the family's north-most instance (the north keeper's on DETAIL
    C); returns the check that proves every balloon again after the last
    rebuild."""
    _activate_sheet(adapter, SHEET_NAMES[1])
    exploded = place_view(
        adapter, str(SOURCE), "*Isometric", *EXPLODED_ISO_CENTER, scale=SHEET_SCALE
    )
    set_high_quality_shaded_with_edges(adapter, exploded, label="channel exploded")
    # Configuration, then its own explode, then the BOM and balloons bind.
    configuration = apply_view_configuration(
        adapter, exploded, label="channel exploded"
    )
    set_view_exploded_state(
        adapter, exploded, True, configuration=configuration, label="channel exploded"
    )
    _center_view_outline(
        adapter, exploded, EXPLODED_ISO_CENTER, label="channel exploded"
    )
    _assert_view_on_sheet(
        exploded, margin=BALLOON_MARGIN + BALLOON_MAX_RADIUS, label="channel exploded"
    )
    table = insert_bom_table(
        adapter,
        exploded,
        anchor_xy=BOM_ANCHOR,
        expected_components=BOM_COMPONENTS,
        descriptions=BOM_DESCRIPTIONS,
        identity_aliases=BOM_IDENTITY_ALIASES,
        configuration_grouping="same-part",
        label="channel",
    )
    items = _validate_bom(adapter, table)
    anchors = {
        stem: BalloonAnchor(
            point_mm=BALLOON_POINTS_MM.get(stem), instance=north_instances[stem]
        )
        for stem in BOM_COMPONENTS
    }
    keeper_items = tuple(
        (stem, item) for stem, item in items if stem in KEEPER_DETAIL_BALLOON_STEMS
    )
    if {stem for stem, _item in keeper_items} != KEEPER_DETAIL_BALLOON_STEMS:
        raise RuntimeError("channel BOM does not list every DETAIL C family")
    landings = add_component_bom_balloons(
        adapter,
        exploded,
        items=tuple(pair for pair in items if pair not in keeper_items),
        anchors=anchors,
        label="channel exploded-view BOM coverage",
        margin=BALLOON_MARGIN,
    )
    shaft_landing = next(
        landing for landing in landings if landing.stem == PIVOT_SHAFT_STEM
    )
    _offset_balloon_from_landing(
        adapter,
        shaft_landing,
        PIVOT_SHAFT_BALLOON_OFFSET,
        label="channel pivot-shaft balloon",
    )
    bom_bottom, _ = _bom_vertical_limits(table)
    caption = _add_note_block(
        adapter,
        SHEET_NAMES[1],
        EXPLODED_CAPTION,
        exploded_caption_xy(bom_bottom),
        label="exploded-view caption",
    )
    # After the balloons, so the boundary circles are never picked as a
    # component's edge.
    _mark_exploded_details(adapter, exploded)
    _add_north_end_trail(adapter, exploded)
    _activate_sheet(adapter, SHEET_NAMES[1])
    details = {detail: _exploded_detail(adapter, detail) for detail in EXPLODED_DETAILS}
    keeper_view = details[NORTH_KEEPER_DETAIL]
    keeper_label = f"channel {NORTH_KEEPER_DETAIL.title} BOM coverage"
    _link_view_to_bom(keeper_view, table, label=keeper_label)
    landings += add_component_bom_balloons(
        adapter,
        keeper_view,
        items=keeper_items,
        anchors=anchors,
        label=keeper_label,
        margin=KEEPER_DETAIL_BALLOON_MARGIN,
    )
    if len(landings) != len(BOM_COMPONENTS):
        raise RuntimeError(
            f"channel exploded sheet carries {len(landings)} balloons, "
            f"expected one per BOM row ({len(BOM_COMPONENTS)})"
        )
    _activate_sheet(adapter, SHEET_NAMES[1])
    if not adapter.currentModel.EditRebuild3():
        raise RuntimeError("channel exploded caption rebuild failed")
    _assert_exploded_caption(adapter, table, caption)

    def settled() -> None:
        assert_balloon_landings(adapter, landings)
        _assert_exploded_caption(adapter, table, caption)

    return settled


def _activate_view(adapter: Any, view: Any, *, label: str) -> str:
    name = view_name(adapter, view)
    if not _early_bound(adapter.currentModel, "IDrawingDoc").ActivateView(name):
        raise RuntimeError(f"failed to activate the {label} {name!r}")
    adapter.currentModel.ClearSelection2(True)
    return name


def _placed_bank_view(adapter: Any, bank: BankView) -> Any:
    """``bank`` uncropped: a model view in its orientation at its scale,
    moved so its model centre lands on ``bank.centre``, isolated to its
    families."""
    view = _early_bound(
        place_view(
            adapter, str(SOURCE), bank.orientation, *bank.centre, scale=bank.scale
        ),
        "IView",
    )
    label = f"{bank.title} centre"
    pictorial = bank.orientation == "*Isometric"
    if pictorial:
        # Display mode first, as the exploded view: the configuration
        # policy judges a pictorial view shaded with edges.
        set_high_quality_shaded_with_edges(adapter, view, label=bank.title)
    configuration = apply_view_configuration(
        adapter, view, role=ViewRole.PLAIN, label=bank.title
    )
    set_view_exploded_state(
        adapter, view, bank.exploded, configuration=configuration, label=bank.title
    )
    centre = model_point_in_view(adapter, view, bank.model_centre_m, label=label)
    position = tuple(float(value) for value in view.Position)
    target = [position[axis] + bank.centre[axis] - centre[axis] for axis in range(2)]
    if not view.SetViewPosition(double_array(target), False):
        raise RuntimeError(f"failed to move {bank.title} onto its spot")
    adapter.currentModel.EditRebuild3()
    centre = model_point_in_view(adapter, view, bank.model_centre_m, label=label)
    if max(abs(a - b) for a, b in zip(centre, bank.centre)) > VIEW_POSITION_TOL_M:
        raise RuntimeError(
            f"{bank.title} centre sits at {centre!r}, not {bank.centre!r}"
        )
    if not pictorial:
        set_hidden_lines_removed(adapter, view)
    view = isolate_drawing_view_components(adapter, view, visible_stems=bank.stems, label=bank.title)
    return view


def _sketch_in_view(
    adapter: Any,
    view: Any,
    sheet_points: tuple[tuple[float, float], tuple[float, float]],
    kind: Literal["circle", "line"],
    *,
    label: str,
) -> Any:
    """Sketch a ``kind`` ("circle": centre, rim point; "line": ends) at two
    sheet points (m) in ``view``'s own sketch, left selected
    (draw_pn_pen_assembly._sketch_in_view)."""
    view = _early_bound(view, "IView")
    _activate_view(adapter, view, label=label)
    sketch = _early_bound(view.GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    points = []
    for x, y in sheet_points:
        point = _early_bound(
            utility.CreatePoint(double_array([x, y, 0.0])), "IMathPoint"
        )
        projected = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
        points.append(tuple(float(value) for value in projected.ArrayData))
    manager = _early_bound(adapter.currentModel.SketchManager, "ISketchManager")
    create = {"circle": manager.CreateCircle, "line": manager.CreateLine}[kind]
    previous = bool(manager.AddToDB)
    manager.AddToDB = False
    try:
        segment = create(*points[0], *points[1])
    finally:
        manager.AddToDB = previous
    if segment is None:
        raise RuntimeError(f"failed to sketch the {label} {kind}")
    return segment


def _sketch_view_circle(
    adapter: Any,
    view: Any,
    centre: tuple[float, float],
    radius_m: float,
    *,
    label: str,
) -> None:
    """Sketch a circle (sheet m) in ``view``'s own sketch, left selected."""
    _sketch_in_view(
        adapter,
        view,
        (centre, (centre[0] + radius_m, centre[1])),
        "circle",
        label=label,
    )


def north_end_trail_mm() -> tuple[tuple[float, float, float], ...]:
    """The north bracket's explode path (model mm): its seat on the
    MHA-CH-05 axis, north along that axis, then up to its exploded bore."""
    seat = (_PIVOT_X, _PIVOT_Y, PIVOT_BRACKET_Z[1])
    dx, dy, dz = exploded_offset(explode.BRACKET, "north")
    if dx != 0.0 or dy <= 0.0 or dz <= 0.0:
        raise RuntimeError(
            f"the north bracket no longer explodes north then up: {(dx, dy, dz)}"
        )
    along = (seat[0], seat[1], seat[2] + dz)
    return seat, along, (along[0], along[1] + dy, along[2])


def _add_north_end_trail(adapter: Any, exploded: Any) -> None:
    """The north bracket cluster's explode trail on the exploded view: black
    phantom segments along ``north_end_trail_mm``, the path its steps moved
    it, so the lifted cluster reads as the rocker shaft's north end (#1660
    r3)."""
    path = north_end_trail_mm()
    label = "north bracket explode trail"
    ends = [
        model_point_in_view(
            adapter, exploded, tuple(value / 1000.0 for value in point), label=label
        )
        for point in path
    ]
    for start, end in zip(ends, ends[1:]):
        segment = _early_bound(
            _sketch_in_view(adapter, exploded, (start, end), "line", label=label),
            "ISketchSegment",
        )
        segment.Style = TRAIL_LINE_STYLE
        segment.Color = TRAIL_COLOR
        adapter.currentModel.ClearSelection2(True)
        adapter.currentModel.EditRebuild3()
        style, color = int(segment.Style), int(segment.Color)
        if (style, color) != (TRAIL_LINE_STYLE, TRAIL_COLOR):
            raise RuntimeError(f"{label}: segment reads style {style}, colour {color}")
        _telemetry.info(f"{label}: {start!r} -> {end!r}")


def _crop(adapter: Any, view: Any, bank: BankView) -> None:
    """Crop ``view`` to the circle round ``bank.centre``: sketch the circle in
    the active view's own sketch and Crop2 while it is still selected (the
    draw_mg_magnifier_assembly detail)."""
    if bank.crop_radius_mm is None:
        raise ValueError(f"{bank.title} has no crop circle")
    view = _early_bound(view, "IView")
    _sketch_view_circle(
        adapter, view, bank.centre, bank.crop_radius_mm * bank.mm, label=bank.title
    )
    status = int(view.Crop2(False, False, 1))
    adapter.currentModel.ClearSelection2(True)
    adapter.currentModel.EditRebuild3()
    view.UpdateViewDisplayGeometry()
    cropped = bool(view.IsCropped())
    _telemetry.info(
        f"channel: {bank.title} Crop2 status {status}, IsCropped {cropped}",
        crop_status=status,
        cropped=cropped,
    )
    if status != CROP_NO_ERROR or not cropped:
        raise RuntimeError(
            f"{bank.title} is not cropped: Crop2 status {status}, IsCropped {cropped}"
        )


def _mark_detail(
    adapter: Any,
    view: Any,
    centre: tuple[float, float],
    radius: float,
    detail: BankView,
    *,
    parent: str,
) -> None:
    """Draw a detail's boundary circle (sheet m) in its parent ``view`` and
    letter it outside, view-owned so both move with the view."""
    label = f"{parent} detail {detail.letter} boundary"
    _sketch_view_circle(adapter, view, centre, radius, label=label)
    adapter.currentModel.ClearSelection2(True)
    _activate_view(adapter, view, label=parent)
    point = letter_xy(centre, radius, detail.letter_corner)
    if add_note(adapter, detail.letter, *point) is None:
        raise RuntimeError(f"failed to letter the {label}")


def _exploded_detail(adapter: Any, detail: BankView) -> Any:
    """One enlarged, exploded hardware cluster: placed, isolated, cropped to
    its circle and labelled under it; returns its view."""
    view = _placed_bank_view(adapter, detail)
    _crop(adapter, view, detail)
    _activate_view(adapter, view, label=detail.title)
    if add_note(adapter, detail.label_text, *detail.crop_label_xy) is None:
        raise RuntimeError(f"failed to label {detail.title}")
    return view


def _offset_balloon_from_landing(
    adapter: Any,
    landing: BalloonLanding,
    offset: tuple[float, float],
    *,
    label: str,
) -> None:
    """Move ``landing``'s balloon off its ring so its circle centre stands
    ``offset`` (sheet m) from its proven landing; the leader stays attached
    (``_spread_balloons``' anchor-to-circle carry) and the circle is read
    back."""
    if landing.sheet_xy is None:
        raise RuntimeError(f"{label}: the balloon's landing was not proven")
    target = (landing.sheet_xy[0] + offset[0], landing.sheet_xy[1] + offset[1])
    note = _early_bound(landing.note, "INote")
    annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
    circle_x, circle_y, _radius = rendered_balloon_circle(note, label=label)
    anchor = tuple(float(value) for value in annotation.GetPosition())
    moved = (anchor[0] + target[0] - circle_x, anchor[1] + target[1] - circle_y)
    if not annotation.SetPosition(moved[0], moved[1], 0.0):
        raise RuntimeError(f"{label}: SetPosition{moved!r} returned false")
    if not adapter.currentModel.EditRebuild3():
        raise RuntimeError(f"{label}: rebuild failed")
    adapter.currentModel.GraphicsRedraw2()
    note = _early_bound(annotation.GetSpecificAnnotation(), "INote")
    circle = rendered_balloon_circle(note, label=label)[:2]
    _telemetry.info(f"{label}: circle at {circle!r}, target {target!r}")
    if max(abs(a - b) for a, b in zip(circle, target)) > BALLOON_PLACEMENT_TOL_M:
        raise RuntimeError(f"{label}: circle sits at {circle!r}, not {target!r}")


def _link_view_to_bom(view: Any, table: Any, *, label: str) -> None:
    """Number ``view``'s balloons from the BOM table inserted on the exploded
    view (draw_pd_paper_drive_assembly's link)."""
    feature = _early_bound(
        _early_bound(table, "IBomTableAnnotation").BomFeature, "IBomFeature"
    )
    name = str(feature.Name or "")
    if not name:
        raise RuntimeError(f"{label}: the channel BOM feature has no name")
    view = _early_bound(view, "IView")
    if not view.SetKeepLinkedToBOM(True, name):
        raise RuntimeError(f"{label}: SetKeepLinkedToBOM({name!r}) returned false")
    if (
        not bool(view.GetKeepLinkedToBOM())
        or str(view.GetKeepLinkedToBOMName() or "") != name
    ):
        raise RuntimeError(f"{label}: view is not linked to BOM {name!r}")


def _mark_exploded_details(adapter: Any, exploded: Any) -> None:
    """Each enlarged cluster's boundary in the 1:7 exploded view, about its
    exploded centre as that view projects it."""
    numerator, denominator = SHEET_SCALE
    for detail in EXPLODED_DETAILS:
        if detail.crop_radius_mm is None:
            raise ValueError(f"{detail.title} has no crop circle")
        centre = model_point_in_view(
            adapter, exploded, detail.model_centre_m, label=f"{detail.title} centre"
        )
        radius = detail.crop_radius_mm * numerator / denominator / 1000.0
        _mark_detail(
            adapter,
            exploded,
            (centre[0], centre[1]),
            radius,
            detail,
            parent="channel exploded",
        )


def _dimensioned_bank(
    adapter: Any,
    bank: BankView,
    keep: dict[str, tuple[float, float]],
    *,
    detail: BankView | None = None,
    pointers: tuple[
        tuple[str, tuple[float, float], tuple[float, float]], ...
    ] = (),
) -> list[Any]:
    """Place ``bank``, show its own settings sketch in it (the other bank's
    lies off the sheet), import ``keep``, crop it if it is a detail, prove the
    kept dimensions survived, and label it. ``detail``, a detail taken from
    ``bank``, gets its boundary circle and letter drawn in ``bank``; each of
    ``pointers`` (text, text point, tip) names a body with a view-owned
    leader."""
    view = _placed_bank_view(adapter, bank)
    features = tuple(dict.fromkeys(asm.DIMENSION_FEATURE[name] for name in keep))
    _show_base_view_sketches(adapter, view, features, label=bank.title)
    annotations = curate_view_dimensions(
        adapter,
        view,
        keep=keep,
        view_label=bank.title,
        dimensions_by_feature=asm.DRAWING_DIMENSIONS,
    )
    if detail is not None:
        centre, radius = detail_boundary(bank, detail)
        _mark_detail(adapter, view, centre, radius, detail, parent=bank.title)
    if bank.crop_radius_mm is not None:
        _crop(adapter, view, bank)
        kept = {
            dimension_name(adapter, _early_bound(annotation, "IAnnotation"))
            for annotation in (_early_bound(view, "IView").GetAnnotations() or ())
        }
        lost = sorted(set(keep) - kept)
        if lost:
            raise RuntimeError(
                f"{bank.title} lost {lost} to its crop; kept {sorted(kept)}"
            )
        x0, y0 = bank.crop_label_xy
    else:
        _assert_view_on_sheet(view, label=bank.title)
        x0, y0 = bank.label_xy or (
            bank.centre[0] - 0.016,
            _view_outline(view, label=bank.title)[1] - 0.004,
        )
    _activate_view(adapter, view, label=bank.title)
    if add_note(adapter, bank.label_text, x0, y0) is None:
        raise RuntimeError(f"failed to label {bank.title}")
    for text, text_xy, tip in pointers:
        add_leader_note(
            adapter,
            text,
            text_xy=text_xy,
            attach_xy=tip,
            label=f"{bank.title} {text.splitlines()[0]}",
            view=view,
        )
    return annotations


def _displays(adapter: Any, annotations: list[Any]) -> dict[str, Any]:
    return {
        dimension_name(adapter, annotation): _early_bound(
            _early_bound(annotation, "IAnnotation").GetSpecificAnnotation(),
            "IDisplayDimension",
        )
        for annotation in annotations
    }


def _assert_settings(displays: dict[str, Any]) -> None:
    """Bands, reference state and callouts read back as the spec states them."""
    for name, display in displays.items():
        dimension = _early_bound(display.GetDimension2(0), "IDimension")
        tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
        reference = (
            str(display.GetText(REFERENCE_PREFIX_PART) or ""),
            str(display.GetText(REFERENCE_SUFFIX_PART) or ""),
        ) == ("(", ")")
        if name in notes.REFERENCE_DIMENSIONS:
            if not reference:
                raise RuntimeError(f"{name}: not shown as a reference")
        else:
            lower, upper = asm.DIMENSION_TOLERANCES[name]
            if (
                reference
                or abs(float(tolerance.GetMaxValue()) - upper / 1000.0) > 1e-9
                or abs(float(tolerance.GetMinValue()) - lower / 1000.0) > 1e-9
                or int(display.GetPrimaryTolPrecision2()) != asm.TOLERANCE_PRECISION[name]
            ):
                raise RuntimeError(
                    f"{name}: band is not {asm.DIMENSION_TOLERANCES[name]}"
                )
        text = str(display.GetText(CALLOUT_TEXT_PART) or "").replace("\r\n", "\n")
        if text != notes.DIMENSION_CALLOUTS[name]:
            raise RuntimeError(f"{name}: callout reads {text!r}")


def _place_steps(adapter: Any, sheet: str) -> None:
    """The step columns ``FITUP_NOTES`` flowed onto ``sheet``."""
    for index, (column, text) in enumerate(FITUP_NOTES):
        if column.sheet == sheet:
            _add_note_block(
                adapter, sheet, text, column.xy, label=f"fit-up steps, column {index}"
            )


def _place_fitup_sheets(adapter: Any) -> Callable[[], None]:
    """Sheets 3 to 5: the isolated banks with their settings, detail A, the
    steps."""
    _activate_sheet(adapter, SHEET_NAMES[2])
    annotations = _dimensioned_bank(
        adapter, ROCKER_BANK, STACK_KEEP, detail=SOUTH_END, pointers=ROCKER_POINTERS
    )
    _place_steps(adapter, SHEET_NAMES[2])

    _activate_sheet(adapter, DETAIL_SHEET)
    annotations += _dimensioned_bank(
        adapter, SOUTH_END, SPRING_KEEP, pointers=DETAIL_POINTERS
    )
    _place_steps(adapter, DETAIL_SHEET)

    _activate_sheet(adapter, SHEET_NAMES[4])
    annotations += _dimensioned_bank(adapter, LEVER_BANK, LUG_KEEP, pointers=LEVER_POINTERS)
    annotations += _dimensioned_bank(
        adapter, KEEPER_PLAN, PLAN_KEEP, pointers=PLAN_POINTERS
    )
    _place_steps(adapter, SHEET_NAMES[4])

    for name, text in notes.DIMENSION_CALLOUTS.items():
        set_dimension_callouts(adapter, annotations, {name: text}, location="above")
    displays = _displays(adapter, annotations)
    for annotation in annotations:
        name = dimension_name(adapter, annotation)
        if name in notes.REFERENCE_DIMENSIONS:
            set_reference_dimension(adapter, annotation, label=f"channel {name}")
    if sorted(displays) != sorted(asm.DIMENSION_FEATURE):
        raise RuntimeError(f"fit-up views imported {sorted(displays)}")
    assert_imported_precision(
        adapter,
        annotations,
        {
            name: places
            for names in asm.DRAWING_PRECISION.values()
            for name, places in names.items()
        },
    )
    _assert_settings(displays)
    _break_line_at_text(displays[asm.LUG_SPAN_DIMENSION], label=asm.LUG_SPAN_DIMENSION)
    return lambda: _assert_settings(displays)


def _place_hookup_sheet(adapter: Any) -> None:
    """Sheet 6: view G, the spring hook-up, and the rest of the lever-bank
    steps."""
    _activate_sheet(adapter, SHEET_NAMES[5])
    view = _placed_bank_view(adapter, HOOKUP)
    _assert_view_on_sheet(view, label=HOOKUP.title)
    _activate_view(adapter, view, label=HOOKUP.title)
    outline = _view_outline(view, label=HOOKUP.title)
    # The label and the short column under it are laid out from the farm-read
    # outline (HOOKUP_BOTTOM_Y); the left column runs beside it.
    left_column_right = STEPS_LEFT_X + STEPS_LINE_WIDTH * NOTE_CHAR_WIDTH
    if outline[1] < HOOKUP_BOTTOM_Y - 0.004 or outline[0] < left_column_right:
        raise RuntimeError(
            f"{HOOKUP.title} outline {outline!r} runs into its step columns "
            f"(bottom estimate {HOOKUP_BOTTOM_Y:.4f}, left column to "
            f"{left_column_right:.4f})"
        )
    label_xy = (HOOKUP.centre[0] - 0.016, outline[1] - 0.004)
    if add_note(adapter, HOOKUP.label_text, *label_xy) is None:
        raise RuntimeError(f"failed to label {HOOKUP.title}")
    _place_steps(adapter, SHEET_NAMES[5])


def _break_line_at_text(display: Any, *, label: str) -> None:
    """Put the value in a break of its dimension line (#1660 r8): on the
    unbroken line the reference parentheses' tails touched the line."""
    display = _sw_type_info.early_bound_or_flag(
        display, "IDisplayDimension", "SetBrokenLeader2", "GetBrokenLeader2"
    )
    if display.SetBrokenLeader2(False, BROKEN_LINE_ALIGNED_TEXT) != 0:
        raise RuntimeError(f"{label}: failed to break the dimension line")
    if int(display.GetBrokenLeader2()) != BROKEN_LINE_ALIGNED_TEXT:
        raise RuntimeError(f"{label}: broken dimension line did not persist")


def _create_sheets(adapter: Any) -> None:
    new_project_drawing(adapter, layout=SPEC.layout, scale=SHEET_SCALE, unit=asm.UNIT)
    create_blank_drawing_sheets(adapter, SHEET_NAMES, label="channel package")
    for name in SHEET_NAMES:
        sheet = _activate_sheet(adapter, name)
        numerator, denominator = SHEET_SCALES[name]
        if not sheet.SetScale(float(numerator), float(denominator), False, False):
            raise RuntimeError(f"failed to set channel sheet scale: {name}")


@_telemetry.traced("drawing.channel_assembly")
async def build(adapter: Any) -> dict[str, str]:
    require_single_spring_variant(
        SPRING_STEMS, str(_config.machine("amplitude", "preset"))
    )
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source assembly is missing: {SOURCE}")

    check("open assembly drawing source", await adapter.open_model(str(SOURCE)))
    source_model = _early_bound(adapter.currentModel, "IModelDoc2")
    read_required_properties(
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
    north_instances = _validate_source(source_model)

    _create_sheets(adapter)
    _place_assembled_sheet(adapter)
    balloons_settled = _place_exploded_sheet(adapter, north_instances)
    settings_settled = _place_fitup_sheets(adapter)
    _place_hookup_sheet(adapter)

    def settled() -> None:
        balloons_settled()
        settings_settled()

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        layout=SPEC.layout,
        pdf_title="Channel Assembly Drawing Package",
        scale=SHEET_SCALE,
        expected_sheet_names=SHEET_NAMES,
        sheet_layouts=SHEET_LAYOUTS,
        sheet_scales=SHEET_SCALES,
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
