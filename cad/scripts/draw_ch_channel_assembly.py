r"""Create the MHA-CH-000 channel assembly fitter package (four sheets).

1. ASSEMBLED VIEWS: Front, Right and the full-detail isometric at 1:7.
2. EXPLODED VIEW + BOM: the builder-owned CHANNEL_EXPLODED isometric
   (ch_channel_assembly_spec), the native BOM with the registry's part
   numbers, vendor SKUs and ch_channel_assembly_notes' descriptions, and one
   balloon per BOM row.
3. ROCKER BANK FIT-UP: the bank isolated at 1:1 with the closed-up stack
   length, a cropped 4:1 detail of the south end with the spring set, and
   steps 1-8. The south bracket is set off a wave disc spring that preloads
   the bank north, and the plain pivot shaft is cut to fit and held by a set
   screw in each ear (#948 ruling R, PR #1292; user, 2026-10-10).
4. LEVER BANK FIT-UP: the keepers, fulcrum shaft and levers isolated at 1:1
   with the keeper lug span, the 1:2 keeper plan view with the keepers'
   three settings off the top frame's datums, and the remaining steps: the
   keepers' bench pair-ream and DRO fit-up on the top frame, the bars pinned
   to the levers, the lever bank threaded, the set screws staked and the
   springs hooked.

The settings are the assembly's own model dimensions (the hidden rocker-bank,
lever-bank and keeper-plan settings sketches, build_ch_channel_assembly), not
numbers in note text; the steps are numbered by ``ch_channel_assembly_steps``.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import math
import sys
import textwrap
from pathlib import Path
from typing import Any, Callable

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
from _drawing_balloons import (
    BalloonAnchor,
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
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME, DrawingLayout
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
import ch_channel_assembly_notes as notes
import ch_channel_assembly_spec as asm
import ch_channel_assembly_steps as steps
from ch_fulcrum_keeper_spec import (
    BORE_DIA as KEEPER_BORE_DIA,
    BORE_DIA_BAND as KEEPER_BORE_DIA_BAND,
    CROWN_LEAST_R,
    CROWN_MOST_R,
    CROWN_R,
    FULCRUM_KEEPER_CENTRE_Z,
    KEEPER_FITUP_X_FROM_WEB_MM,
    KEEPER_INNER_FACE_FROM_FRONT_SOCKET_MM,
    KEEPER_INNER_FACE_SPAN_MM,
    KEEPER_Z_OFF,
    SET_SCREW_THREAD as KEEPER_SET_SCREW_THREAD,
)
from ch_pivot_bracket_sides import FOOT_Z1 as BRACKET_FOOT_Z1
from ch_pivot_bracket_spec import (
    FOOT_H as BRACKET_FOOT_H,
    FOOT_W as BRACKET_FOOT_W,
    SET_SCREW_ENGAGEMENT_ASSEMBLY_FACT,
)
from ch_pivot_shaft_spec import DOME_HEIGHT
from ch_rocker_arm_spec import HUB_LENGTH, HUB_LENGTH_BAND
from channel_frame_geom import LEVER_FULCRUM_XY, ROCKER_PIVOT_XY
from frame_column_stations import COLUMN_X
from rocker_bank_layout import (
    COUNT,
    PIVOT_BRACKET_Z,
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
    "LEVER BANK FIT-UP",
)
if SPEC.layout is not DrawingLayout.LANDSCAPE:
    raise AssertionError("the channel package is landscape throughout")
SHEET_LAYOUTS = {name: DrawingLayout.LANDSCAPE for name in SHEET_NAMES}
SHEET_SCALE = (1.0, 7.0)
FITUP_SCALE = (1.0, 1.0)
SHEET_SCALES = {
    SHEET_NAMES[0]: SHEET_SCALE,
    SHEET_NAMES[1]: SHEET_SCALE,
    SHEET_NAMES[2]: FITUP_SCALE,
    SHEET_NAMES[3]: FITUP_SCALE,
}
_TEMPLATE = DRAWING_TEMPLATES[DrawingLayout.LANDSCAPE]
BORDER = 0.0127

# --- sheet 1: assembled views (the v41 single-sheet positions) ---------------
FRONT_CENTER = (0.060, 0.150)
RIGHT_CENTER = (0.130, 0.150)
# r1: at y 0.140 the isometric's outline (0.154 tall) dipped to y 0.063,
# into the title block's 0.066 top; 0.150 leaves it 7 mm clear.
ISO_CENTER = (0.225, 0.150)
ASSEMBLED_CAPTION_XY = (0.272, 0.250)
ASSEMBLED_CAPTION = "\n".join(
    (
        "RIGHT VIEW: NORTH (HUB 19) LEFT, SOUTH (HUB 0) RIGHT.",
        "SHEET 2: EXPLODED VIEW AND BILL OF MATERIALS.",
        f"SHEETS 3 AND 4: FIT-UP, STEPS 1 TO {len(steps.SEQUENCE)}.",
    )
)

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
# leader 14 2.1-4.4 mm off the shaft, with the ring 5 mm inside the border at
# the top and 6 mm at the bottom.
BALLOON_MARGIN = 0.028
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
# Below the BOM's 19 rows (bottom ~0.129 m), above the title block.
EXPLODED_CAPTION_XY = (BOM_ANCHOR[0], 0.124)
EXPLODED_CAPTION = "\n".join(
    (
        f"EXPLODED: ALL {COUNT} CHANNELS ALIKE, THE NORTH-MOST PULLED OUT",
        "NORTH; ONE BALLOON PER BOM ROW, ON THE NORTH-MOST INSTANCE.",
        f"QTY IS PER {steps.DRAWING_NUMBER} (ALL {COUNT} CHANNELS).",
    )
)

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
            f"vn-channel-spring-installed-stretch{variants[amplitude]:02d}"
            for amplitude in amplitudes[:channels]
        )
    )


def require_single_spring_variant(stems: tuple[str, ...], preset: str) -> None:
    """Refuse a BOM the drawing cannot print: one MHA-VN-004 row of qty 20.

    Each spring variant is its own SLDPRT, so a preset with several installed
    lengths would print several rows under one part number.
    """
    if len(stems) != 1:
        raise RuntimeError(
            f"MHA-CH-000 is drawn for one installed-spring length, but the "
            f"{preset!r} amplitude preset builds {len(stems)} spring variants "
            f"that share MHA-VN-004; see {SPRING_VARIANT_ISSUE}"
        )


SPRING_STEMS = spring_stems(_config.amplitudes(), CHANNELS)
SPRING_STEM = SPRING_STEMS[0]

BOM_QUANTITIES = {
    "ch-pivot-shaft": 1,
    "ch-fulcrum-shaft": 1,
    asm.BRACKET: 2,
    asm.BRACKET_SET_SCREW: 2,
    asm.WASHER: 2,
    asm.BANK_SPRING: 1,
    asm.BRACKET_HOLD_DOWN: 2,
    asm.KEEPER: 2,
    asm.KEEPER_FOOT_SCREW: 2,
    asm.KEEPER_SET_SCREW: 2,
    "ch-rocker-arm": CHANNELS,
    asm.ROD: CHANNELS,
    asm.BAR: CHANNELS,
    "ch-channel-lever": CHANNELS,
    "ch-rod-pivot-pin": CHANNELS,
    asm.BAR_PIN: CHANNELS,
    SPRING_STEM: CHANNELS,
    asm.HOOK: CHANNELS,
    asm.ANCHOR_NUT: CHANNELS,
}
BOM_COMPONENTS = tuple(BOM_QUANTITIES)
# Literal stems, so the config-dependency analysis reads exactly these rows.
PART_ROWS = {
    "ch-pivot-shaft": _config.parts("ch-pivot-shaft"),
    "ch-fulcrum-shaft": _config.parts("ch-fulcrum-shaft"),
    "ch-pivot-bracket": _config.parts("ch-pivot-bracket"),
    "vn-arbor-set-screw": _config.parts("vn-arbor-set-screw"),
    "vn-rocker-thrust-washer": _config.parts("vn-rocker-thrust-washer"),
    "vn-rocker-bank-spring": _config.parts("vn-rocker-bank-spring"),
    "vn-bracket-hold-down-screw": _config.parts("vn-bracket-hold-down-screw"),
    "ch-fulcrum-keeper": _config.parts("ch-fulcrum-keeper"),
    "vn-frame-side-screw": _config.parts("vn-frame-side-screw"),
    "vn-fulcrum-set-screw": _config.parts("vn-fulcrum-set-screw"),
    "ch-rocker-arm": _config.parts("ch-rocker-arm"),
    "ch-connecting-rod": _config.parts("ch-connecting-rod"),
    "ch-amplitude-bar": _config.parts("ch-amplitude-bar"),
    "ch-channel-lever": _config.parts("ch-channel-lever"),
    "ch-rod-pivot-pin": _config.parts("ch-rod-pivot-pin"),
    "ch-bar-pivot-pin": _config.parts("ch-bar-pivot-pin"),
    SPRING_STEM: _config.parts("vn-channel-spring-installed"),
    "vn-spring-hook": _config.parts("vn-spring-hook"),
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
        "vn-channel-spring-installed" if stem == SPRING_STEM else stem
    ]
    for stem in BOM_COMPONENTS
}
BOM_IDENTITY_ALIASES = {number: stem for stem, number in BOM_PART_NUMBERS.items()}
BOM_NORMALIZED_ALIASES = {
    alias.casefold(): stem for alias, stem in BOM_IDENTITY_ALIASES.items()
}
EXPLODED_VIEW_NAMES = {
    ASSEMBLY_VIEW_CONFIGURATION: asm.EXPLODED_VIEW_NAME,
    SIMPLIFIED_VIEW_CONFIGURATION: simplified_name(asm.EXPLODED_VIEW_NAME),
}
if asm.SOURCE_CONFIGURATION != ASSEMBLY_VIEW_CONFIGURATION:
    raise AssertionError("the channel explode is authored in Default")

# --- sheets 3 and 4: isolated 1:1 bank views, the south-end detail, steps ----
# On a Right view sheet x runs with machine -z (north left, south right) and
# sheet y with machine y.
CROP_NO_ERROR = 1  # swCropViewErrors_e.swCropViewErrors_NoError
VIEW_POSITION_TOL_M = 1e-4
STEPS_XY = (0.214, 0.258)
STEPS_LINE_WIDTH = 64  # characters; default-format note text
# The layout audit proves the blocks clear the title block; the line width
# keeps them inside the right border (test_ch_channel_assembly_drawing).
END_LABEL_DROP_MM = 52.0  # end labels this far under the shaft axis


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
        lines = (self.title, self.parts, f"SCALE {self.scale[0]} : {self.scale[1]}")
        return "\n".join(line for line in lines if line)

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
    "ROCKER BANK",
    (1, 1),
    (_PIVOT_X, _PIVOT_Y, STACK_MID_Z),
    # 188 mm wide at 1:1 (r5 outline 0.0111-0.1995 about x 0.105): centred
    # between the left border and the steps column.
    (0.111, 0.205),
    frozenset(
        {
            "ch-pivot-shaft",
            asm.BRACKET,
            asm.BRACKET_SET_SCREW,
            asm.BRACKET_HOLD_DOWN,
            asm.WASHER,
            asm.BANK_SPRING,
            "ch-rocker-arm",
        }
    ),
)
# The south end at 4:1: the ear's inner face, the spring, the washer and hub 0
# about the circle's centre on the pivot axis.
DETAIL_LETTER = "A"
_DETAIL_CENTRE_Z = (asm.PIVOT_CHAIN_Z[0] + asm.PIVOT_CHAIN_Z[2]) / 2.0
SOUTH_END = BankView(
    f"DETAIL {DETAIL_LETTER}, SOUTH END",
    (4, 1),
    (_PIVOT_X, _PIVOT_Y, _DETAIL_CENTRE_Z),
    (0.072, 0.098),
    frozenset(
        {
            "ch-pivot-shaft",
            asm.BRACKET,
            asm.BRACKET_SET_SCREW,
            asm.WASHER,
            asm.BANK_SPRING,
            "ch-rocker-arm",
        }
    ),
    crop_radius_mm=8.0,
    parts="EAR, SPRING, WASHER, HUB 0",
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
    "LEVER BANK",
    (1, 1),
    (_FULCRUM_X, _FULCRUM_Y, FULCRUM_KEEPER_CENTRE_Z),
    (0.111, 0.195),
    frozenset(
        {
            "ch-fulcrum-shaft",
            asm.KEEPER,
            asm.KEEPER_FOOT_SCREW,
            asm.KEEPER_SET_SCREW,
            "ch-channel-lever",
            asm.BAR_PIN,
        }
    ),
)
# The keepers on MHA-FR-002 in plan at 1:2, machine front up as the frame's
# own plan prints it (b9ae machinist review: step 10's settings had no view,
# and its X datum, the web centre, is no face to touch). The frame is not in
# this assembly, so the hidden KEEPER_PLAN_FEATURE sketch draws its datums
# as construction lines and carries the three settings (owner ruling
# X1+B1). Placed under the lever bank: the socket line 0.116 up, the rear
# foot tip (z 87.0) 3.5 mm over the border.
KEEPER_PLAN_SOCKET_Y = 0.116
_PLAN_CENTRE_Y = 0.066
_TOP_FRAME_NUMBER = str(_config.parts("fr-top-frame")["number"])
KEEPER_PLAN = BankView(
    "KEEPER PLAN VIEW",
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
            asm.KEEPER,
            asm.KEEPER_FOOT_SCREW,
            asm.KEEPER_SET_SCREW,
        }
    ),
    parts=f"ON {_TOP_FRAME_NUMBER}, FRONT UP",
    orientation="*Top",
    label_xy=(0.020, 0.090),
)
_PLAN_LUG = KEEPER_PLAN.plan_xy(asm.KEEPER_LUG_X, asm.KEEPER_SOCKET_XZ[1])
_PLAN_FACES = tuple(
    KEEPER_PLAN.plan_xy(asm.KEEPER_LUG_X, z) for z in asm.LUG_INNER_FACE_Z
)
# The X text right of its 1.45 mm span, above the socket line; each Z text
# centred on its own dimension line west of the keepers, the rear's inside
# the front's so neither text sits on the other's line (the front line
# stops at the front face, above the rear text; the front text clears the
# rear line by 3 mm).
PLAN_KEEP = {
    asm.KEEPER_X_DIMENSION: (_PLAN_LUG[0] + 0.016, KEEPER_PLAN_SOCKET_Y + 0.005),
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
# ruling: the web centre reads as the split of both web faces), the texts
# east of the view, each leader under or over the other's.
PLAN_POINTERS = (
    (
        f"{_TOP_FRAME_NUMBER} LINE OF THE\nUPPER SOCKET CENTRES",
        (0.020, 0.131),
        KEEPER_PLAN.plan_xy(
            asm.KEEPER_SOCKET_XZ[0] - 2.0 * asm.KEEPER_PLAN_SOCKET_LINE / 3.0,
            asm.KEEPER_SOCKET_XZ[1],
        ),
    ),
    (
        f"{_TOP_FRAME_NUMBER} WEB CENTRE,\nSPLIT OF BOTH WEB FACES",
        (0.020, 0.114),
        KEEPER_PLAN.plan_xy(
            asm.KEEPER_SOCKET_XZ[0],
            asm.KEEPER_SOCKET_XZ[1] + asm.KEEPER_PLAN_WEB_LINE / 2.0,
        ),
    ),
)


def exploded_offset(stem: str, side: asm.Side) -> tuple[float, float, float]:
    """The net channel-explode displacement (model mm) of ``stem``'s
    instance on ``side``: every step that moves its family, summed. The
    north-most instance is on the north side too."""
    sides = {None, side} | ({"north"} if side == "north-most" else set())
    offset = [0.0, 0.0, 0.0]
    for step in asm.EXPLODE_STEPS:
        if asm.family(stem) in step.stems and step.side in sides:
            offset["xyz".index(step.axis)] += step.distance_mm
    return offset[0], offset[1], offset[2]


def _exploded(
    point: tuple[float, float, float], stem: str, side: asm.Side
) -> tuple[float, float, float]:
    dx, dy, dz = exploded_offset(stem, side)
    return point[0] + dx, point[1] + dy, point[2] + dz


# At 1:7 the exploded view shows the small hardware at the bracket and keeper
# ends too small and dark to tell apart (r7 machinist review), so each north
# end (the instances the balloons pin) is enlarged, exploded, beside the BOM.
# Each detail is centred on its exploded bore centre; the radii hold the
# exploded set screw, hold-down or foot screw and (the bracket's) the north
# washer, 29 to 40 mm from those centres in the isometric (estimated from the
# spec dimensions, with margin).
EXPLODED_DETAIL_SCALE = (1, 2)
EXPLODED_DETAIL_X = 0.392  # the column between the BOM and the right border
NORTH_BRACKET_DETAIL = BankView(
    "DETAIL B",
    EXPLODED_DETAIL_SCALE,
    _exploded((_PIVOT_X, _PIVOT_Y, PIVOT_BRACKET_Z[1]), asm.BRACKET, "north"),
    (EXPLODED_DETAIL_X, 0.240),
    frozenset({asm.BRACKET, asm.BRACKET_SET_SCREW, asm.BRACKET_HOLD_DOWN, asm.WASHER}),
    crop_radius_mm=44.0,
    parts="NORTH BRACKET",
    orientation="*Isometric",
    exploded=True,
    letter="B",
    # Lower left: at the upper right the letter sat over the rocker bank's
    # stack beside the circle, where the machinist review (PR #1605) could not
    # tell which boundary it named; the lower left of the circle is clear.
    letter_corner=(-1, -1),
)
NORTH_KEEPER_DETAIL = BankView(
    "DETAIL C",
    EXPLODED_DETAIL_SCALE,
    _exploded(
        (_FULCRUM_X, _FULCRUM_Y, FULCRUM_KEEPER_CENTRE_Z + KEEPER_Z_OFF),
        asm.KEEPER,
        "north",
    ),
    (EXPLODED_DETAIL_X, 0.170),
    frozenset({asm.KEEPER, asm.KEEPER_SET_SCREW, asm.KEEPER_FOOT_SCREW}),
    crop_radius_mm=36.0,
    parts="NORTH KEEPER",
    orientation="*Isometric",
    exploded=True,
    letter="C",
    # Lower right: at the upper right, lever balloon 14's leader ran through
    # the letter (r8 layout audit, leader-through-text); r7's leaders pass
    # 10 mm clear of the lower right.
    letter_corner=(1, -1),
)
EXPLODED_DETAILS = (NORTH_BRACKET_DETAIL, NORTH_KEEPER_DETAIL)
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
# Detail A names the four bodies the blade is read against (b9ae machinist
# review: the caption listed them, nothing in the view said which outline was
# which): (text, text upper-left on the sheet, pointer tip in the detail's
# plane as machine (z, y)). Hub 0 north of the circle, above the axis; the
# washer, spring and ear to the south, under the set dimension's text, rows
# in their tips' top-to-bottom order so no two leaders cross, each tip below
# the axis so no leader crosses the set dimension's extension lines (they
# run from the axis up).
_WASHER_MID = sum(asm.SOUTH_WASHER_Z) / 2.0
DETAIL_POINTERS = tuple(
    (text, xy, SOUTH_END.sheet_xy(z, _PIVOT_Y + dy))
    for text, xy, z, dy in (
        (
            f"{BOM_PART_NUMBERS['ch-rocker-arm']}\nHUB 0",
            (0.018, 0.131),
            asm.PIVOT_CHAIN_Z[2] + 1.0,
            3.0,
        ),
        (
            f"{BOM_PART_NUMBERS[asm.WASHER]} WASHER",
            (0.110, 0.121),
            _WASHER_MID,
            -1.5,
        ),
        (
            f"{BOM_PART_NUMBERS[asm.BANK_SPRING]} SPRING",
            (0.110, 0.108),
            _SPRING_MID,
            -3.0,
        ),
        (
            f"{BOM_PART_NUMBERS[asm.BRACKET]} EAR",
            (0.110, 0.095),
            asm.PIVOT_CHAIN_Z[0] - 3.0,
            -4.5,
        ),
    )
)
LUG_KEEP = {asm.LUG_SPAN_DIMENSION: LEVER_BANK.sheet_xy(_LUG_MID, _FULCRUM_Y + 32.0)}
# swDimensionTextParts_e compartments.
CALLOUT_TEXT_PART = 3  # swDimensionTextCalloutAbove
REFERENCE_PREFIX_PART = 1  # swDimensionTextPrefix
REFERENCE_SUFFIX_PART = 2  # swDimensionTextSuffix
if any("\n" in text for text in notes.DIMENSION_CALLOUTS.values()):
    raise AssertionError("an above-callout with a line break does not print")


def _end_labels(
    view: BankView,
    north_z: float,
    south_z: float,
    y: float,
    names: tuple[str, str],
) -> tuple[tuple[str, tuple[float, float]], ...]:
    """NORTH/SOUTH end labels under a bank's ends (a review asked which end is which)."""
    drop = y - END_LABEL_DROP_MM
    north = view.sheet_xy(north_z, drop)
    south = view.sheet_xy(south_z, drop)
    return (
        (names[0], north),
        (names[1], (south[0] - 0.034, south[1])),
    )


ROCKER_END_LABELS = _end_labels(
    ROCKER_BANK,
    asm.PIVOT_CHAIN_Z[3],
    asm.PIVOT_CHAIN_Z[0],
    _PIVOT_Y,
    ("NORTH END, HUB 19", "SOUTH END, HUB 0"),
)
LEVER_END_LABELS = _end_labels(
    LEVER_BANK,
    asm.LUG_INNER_FACE_Z[1],
    asm.LUG_INNER_FACE_Z[0],
    _FULCRUM_Y,
    ("NORTH END, LEVER 19", "SOUTH END, LEVER 0"),
)

ROCKER_KEYS = tuple(
    steps.SEQUENCE[: steps.SEQUENCE.index(steps.KEEPERS_PAIR_REAMED_KEY)]
)
LEVER_KEYS = tuple(steps.SEQUENCE[len(ROCKER_KEYS) :])
if LEVER_KEYS[0] != steps.KEEPERS_PAIR_REAMED_KEY or LEVER_KEYS[-1] != (
    steps.SPRINGS_HOOKED_KEY
):
    raise AssertionError("the lever-bank steps close the sequence")


def _block(
    heading: str, keys: tuple[str, ...], text: dict[str, str], width: int
) -> str:
    lines = [heading]
    for key in keys:
        lines += textwrap.wrap(
            text[key],
            width=width,
            initial_indent=f"{steps.step_number(key)}. ",
            subsequent_indent="   ",
            # A part number never splits at its hyphens across two lines.
            break_on_hyphens=False,
        )
    return "\n".join(lines)


def _fitup_notes() -> tuple[str, str]:
    # Literal stems, so the config-dependency analysis reads exactly these rows.
    arm = _config.parts("ch-rocker-arm")["number"]
    rod = _config.parts("ch-connecting-rod")["number"]
    pin = _config.parts("ch-rod-pivot-pin")["number"]
    shaft = _config.parts("ch-pivot-shaft")["number"]
    bracket = _config.parts("ch-pivot-bracket")["number"]
    washer = _config.parts("vn-rocker-thrust-washer")["number"]
    spring = _config.parts("vn-rocker-bank-spring")["number"]
    pivot_set_screw = _config.parts("vn-arbor-set-screw")["number"]
    support = _config.parts("fr-rocker-arm-support")["number"]
    hold_down = _config.parts("vn-bracket-hold-down-screw")["number"]
    keeper = _config.parts("ch-fulcrum-keeper")["number"]
    fulcrum_shaft = _config.parts("ch-fulcrum-shaft")["number"]
    fulcrum_set_screw = _config.parts("vn-fulcrum-set-screw")["number"]
    foot_screw = _config.parts("vn-frame-side-screw")["number"]
    top_frame = _config.parts("fr-top-frame")["number"]
    bar = _config.parts("ch-amplitude-bar")["number"]
    lever = _config.parts("ch-channel-lever")["number"]
    bar_pin = _config.parts("ch-bar-pivot-pin")["number"]
    channel_spring = _config.parts("vn-channel-spring-installed")["number"]
    anchor = _config.parts("vn-spring-hook")["number"]
    anchor_nut = _config.parts("ch-anchor-jam-nut")["number"]
    last = COUNT - 1
    # Step 1 prints that the stack is never short (machinist review, PR
    # #1605): every hub comes at or over its print length, so the shortest
    # stack the part band allows must still meet the acceptance's low limit.
    # A long stack is then re-faced on the longest hubs' south faces, each
    # kept at or over its print, and never on the datum face the strap is
    # dimensioned from.
    if COUNT * (HUB_LENGTH + HUB_LENGTH_BAND[1]) < STACK_L20_ACCEPT[0] - 1e-9:
        raise AssertionError(
            "step 1 says the stack is never short, but the hub band allows "
            "a stack under the acceptance's low limit"
        )
    # The pivot shaft comes finished, domed both ends to its overall length
    # (ch_pivot_shaft_spec): its north tip set DOME_HEIGHT proud of the north
    # ear, within SHAFT_TIP_SET_BAND, puts both flats under their screws
    # (rocker_bank_layout checks the worst case).
    tip_low, tip_high = DOME_HEIGHT - SHAFT_TIP_SET_BAND, DOME_HEIGHT + SHAFT_TIP_SET_BAND
    # Each keeper lug is set off the top-frame rail web under it (its column's
    # socket axis) in X and off the frame's hole-station origin line, the
    # upper socket centres, in Z (Main's ruling): the lug centre on the
    # fulcrum line, its inner face off the front socket line. The frame is not
    # in this assembly, so the keeper plan view draws both datums and prints
    # the three settings, each banded (owner ruling X1+B1, b9ae review).
    if abs(LEVER_FULCRUM_XY[0] - COLUMN_X - KEEPER_FITUP_X_FROM_WEB_MM) > 1e-9:
        raise AssertionError("KEEPER_FITUP_X_FROM_WEB_MM is off the fulcrum line")
    front_face, rear_face = KEEPER_INNER_FACE_FROM_FRONT_SOCKET_MM
    # The pair is reamed at the spacing KEEPERS_SET_KEY sets it to (Main's
    # ruling): the lever-bank view's reference lug span.
    if abs(rear_face - front_face - KEEPER_INNER_FACE_SPAN_MM) > 1e-9:
        raise AssertionError("the pair-ream span is not the fit-up span")
    # Each crown is finished at the bench to the MHA-CH-007 crown radius
    # (CrownRadius, printed .X: "FULL ROUND TANGENT TO BOTH SIDES, CENTER AT
    # BORE HEIGHT, PER" this step), turned or filed about a gauge pin in its
    # own reamed bore, and only then tapped through to the bore ("ON BORE AXIS
    # AFTER REAM"). The fitter gauges it as crown top over the pin's underside,
    # the crown radius plus the pin's, across the spec's CROWN_LEAST_R ..
    # CROWN_MOST_R band, with the low limit rounded up (Main's ruling,
    # 2026-10-16).
    pin_r = KEEPER_BORE_DIA / 2.0
    crown_over_pin = (
        math.ceil((CROWN_LEAST_R + pin_r) * 10.0 - 1e-9) / 10.0,
        round(CROWN_MOST_R + pin_r, 1),
    )
    text = {
        # The rings are captured in the closed cam slots as the cylinder stack
        # goes together, and the pressed pin needs its far tine backed on the
        # press, so each rod + arm pair is pinned at the bench before that step -- and
        # after the hub stack is proved on the shaft, while the arms are loose.
        "rocker-stack-accepted": (
            f"STACK THE {COUNT} {arm} ROCKERS ON THE {shaft} SHAFT, CLOSED UP. "
            f"HUB 0 SOUTH FACE TO HUB {last} NORTH FACE TO THE ROCKER BANK "
            f"VIEW'S STACK DIMENSION. EVERY {arm} HUB COMES AT OR OVER PRINT "
            "LENGTH, SO THE STACK IS NEVER SHORT. RE-FACE A LONG STACK ON THE "
            "SOUTH FACES OF THE LONGEST HUBS AS STACKED, NEVER THE DATUM FACE, "
            "NO HUB UNDER PRINT LENGTH. SLIDE THE ROCKERS OFF IN ORDER AND KEEP "
            "THAT ORDER."
        ),
        "rod-forks-pinned": (
            f"BEFORE {steps.CYLINDER_STACK_REF}, AT THE BENCH: PIN EACH {rod} "
            f"ROD FORK TO ITS {arm} ARM WITH ONE {pin}. PRESS IT IN, FAR TINE "
            "BACKED; DRESS BOTH ENDS FLUSH. PIN REMOVABLE WITH PUNCH. "
            "ACCEPT IF THE ARM SWINGS FREE UNDER ITS OWN WEIGHT."
        ),
        "north-ear-datum": (
            f"NORTH {bracket} SET AT {steps.NORTH_BRACKET_SET_REF}: SWING "
            f"EACH ARM UP ON ITS ROD; PUSH THE {shaft} SHAFT, FLATS UP, "
            "SOUTH THROUGH THE EAR, THE "
            f"{washer} WASHER MEASURED AT THAT STEP, THEN HUBS {last} TO 0."
        ),
        "south-washer-fitted": f"SLIP THE OTHER {washer} ON AGAINST HUB 0.",
        # The spring-back check runs while the bracket is only clamped, so a
        # failed check is re-set before anything is drilled, tapped or staked
        # (machinist review, PR #1605).
        "south-bracket-spring-set": (
            f"RUN A {spring} SPRING ALONG THE {shaft}; REJECT ONE THAT BINDS. "
            f"FIT IT ON. SET THE SOUTH {bracket} OFF THE WASHER ON A "
            f"SPRING-SET BLADE (DETAIL {DETAIL_LETTER}) BESIDE THE SPRING, "
            "BANK PUSHED NORTH. CLAMP AND PULL THE BLADE. ACCEPT: PUSHED "
            "SOUTH, THE BANK SPRINGS BACK ONTO THE NORTH WASHER; ELSE UNCLAMP "
            "AND REPEAT THIS STEP."
        ),
        "south-bracket-screwed": (
            f"STILL CLAMPED AS ACCEPTED, TRANSFER THE SOUTH {bracket} FOOT HOLE "
            f"INTO THE {support} RAIL, TAP AS {support}, SCREW DOWN ONE "
            f"{hold_down}."
        ),
        "shaft-set": (
            f"SLIDE THE {shaft} SHAFT UNTIL ITS NORTH TIP STANDS "
            f"{tip_low:.2f} TO {tip_high:.2f} PROUD OF THE NORTH EAR'S OUTER FACE."
        ),
        # drawing-guidelines.md rule 23: staked like the keeper set screws
        # (fulcrum-set-screws-staked). The Loctite waiver was retired on
        # 2026-10-16 under the user's standing no-threadlocker rule.
        "set-screws-driven": (
            f"SHAFT HELD AS SET, FLATS UP: RUN ONE {pivot_set_screw} DOWN EACH "
            "APEX TAP ONTO ITS FLAT, NORTH FIRST; SNUG, AND STAKE EACH TAP "
            "MOUTH AT 2 POINTS. "
            # The bracket's engagement fact; the lifted arch meets rule 18
            # (ch_pivot_bracket_spec), so no exception is declared for it.
            f"{SET_SCREW_ENGAGEMENT_ASSEMBLY_FACT}"
        ),
        steps.KEEPERS_PAIR_REAMED_KEY: (
            f"CLAMP BOTH {keeper}, FEET OUTBOARD ON ONE FLAT, INNER LUG FACES "
            "AT THE LEVER BANK VIEW'S LUG SPAN, BORE AXIS PARALLEL TO THE "
            f"FLAT. BOTH {keeper} BORES "
            f"{KEEPER_BORE_DIA + KEEPER_BORE_DIA_BAND[1]:.3f} TO "
            f"{KEEPER_BORE_DIA + KEEPER_BORE_DIA_BAND[0]:.3f} DIA, IN LINE: THE "
            f"{fulcrum_shaft} SHAFT SLIDES FREELY THROUGH BOTH, CLAMPED. THEN, ON "
            f"A {KEEPER_BORE_DIA:.2f} PIN IN EACH BORE, ROUND ITS CROWN TO THE "
            f"{keeper} CROWN R{CROWN_R:.1f} ABOUT THE PIN AND TAP IT "
            f"{KEEPER_SET_SCREW_THREAD} TO THE BORE. ACCEPT: CROWN TOP "
            f"{crown_over_pin[0]:.1f} TO {crown_over_pin[1]:.1f} OVER THE PIN'S "
            "UNDERSIDE."
        ),
        steps.KEEPERS_SET_KEY: (
            f"{top_frame} ON THE MILL: SHAFT THROUGH BOTH KEEPERS, FEET "
            "OUTBOARD ON THE RAIL. SET EACH LUG CENTRE OFF THE RAIL WEB CENTRE "
            "BELOW IT AND THE LUG INNER FACES OFF THE LINE OF THE UPPER SOCKET "
            "CENTRES, TO THE KEEPER PLAN "
            f"VIEW: THE {fulcrum_shaft} FLATS ARE A FIXED PITCH APART, AND THE "
            "INNER-FACE BANDS LEAVE ONE STEP "
            f"{steps.step_number(steps.SET_SCREWS_STAKED_KEY)} SHAFT POSITION "
            "WITH BOTH FLATS UNDER THEIR CROWN TAPS AND NO LEVER HUB ON A FLAT. "
            f"CLAMP; TRANSFER EACH FOOT HOLE INTO THE RAIL, TAP AS {top_frame}, "
            f"SCREW DOWN ONE {foot_screw}."
        ),
        steps.BARS_PINNED_KEY: (
            f"AT THE BENCH: PIN EACH {bar} BAR TO ITS {lever} LEVER WITH ONE "
            f"{bar_pin}, THE BAR'S TOP NOTCH ASTRIDE THE LEVER. PRESS THE PIN "
            "THROUGH BOTH CHEEKS AND THE LEVER HOLE, FAR CHEEK BACKED; DRESS "
            "BOTH ENDS FLUSH. ACCEPT IF THE BAR SWINGS FREE UNDER ITS OWN WEIGHT."
        ),
        steps.LEVER_BANK_THREADED_KEY: (
            f"DRAW THE {fulcrum_shaft} SHAFT OUT NORTH. PUSH IT BACK SOUTH "
            f"THROUGH THE NORTH {keeper}, LEVERS {last} TO 0 IN CHANNEL ORDER "
            f"AND THE SOUTH {keeper}, EACH BAR'S FOOT NOTCH ASTRIDE ITS {arm} "
            "STRAP. ACCEPT IF EVERY LEVER SWINGS FREE."
        ),
        steps.SET_SCREWS_STAKED_KEY: (
            f"WITH THE LEVER BANK ON IT, SLIDE THE {fulcrum_shaft} SHAFT UNTIL "
            f"EACH FLAT LIES UNDER ITS CROWN TAP; TIGHTEN ONE {fulcrum_set_screw} SET "
            "SCREW ONTO EACH FLAT AND STAKE EACH TAP MOUTH AT 2 POINTS."
        ),
        # The anchors thread into the summing plate and are jammed by their
        # nuts at MHA-HA-000, which owns that joint, its lock and its
        # setting. This sheet only hooks the spring; the pointer is
        # steps.HA_ANCHORS_SET_REF.
        steps.SPRINGS_HOOKED_KEY: (
            f"HOOK EACH {channel_spring} SPRING'S TOP LOOP THROUGH ITS {lever} "
            f"LEVER'S SPRING HOLE. ITS BOTTOM LOOP TAKES ITS {anchor} ANCHOR, "
            f"THREADED AND JAMMED BY ITS {anchor_nut} PER "
            f"{steps.HA_ANCHORS_SET_REF}."
        ),
    }
    return (
        _block("ROCKER BANK FIT-UP", ROCKER_KEYS, text, STEPS_LINE_WIDTH),
        _block("LEVER BANK FIT-UP", LEVER_KEYS, text, STEPS_LINE_WIDTH),
    )


FITUP_NOTES = _fitup_notes()
FITUP_STEPS = "\n".join(FITUP_NOTES)


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


def _assert_view_on_sheet(view: Any, *, margin: float = 0.0, label: str) -> None:
    """The view's outline, grown by ``margin`` (a balloon ring), stays inside
    the inner border and clear of the title block."""
    x0, y0, x1, y1 = _view_outline(view, label=label)
    x0, y0, x1, y1 = x0 - margin, y0 - margin, x1 + margin, y1 + margin
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


def _place_assembled_sheet(adapter: Any) -> None:
    _activate_sheet(adapter, SHEET_NAMES[0])
    for orientation, center in (
        ("*Front", FRONT_CENTER),
        ("*Right", RIGHT_CENTER),
        ("*Isometric", ISO_CENTER),
    ):
        view = place_view(adapter, str(SOURCE), orientation, *center, scale=SHEET_SCALE)
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
    assert_full_detail_view(adapter, label="channel assembly")
    _add_note_block(
        adapter,
        SHEET_NAMES[0],
        ASSEMBLED_CAPTION,
        ASSEMBLED_CAPTION_XY,
        label="assembled-views caption",
    )


def _place_exploded_sheet(
    adapter: Any, north_instances: dict[str, str]
) -> Callable[[], None]:
    """The exploded isometric, its BOM (with vendor SKU) and one balloon per
    BOM row on the family's north-most instance; returns the check that proves
    every balloon again after the last rebuild."""
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
    _assert_view_on_sheet(exploded, margin=BALLOON_MARGIN, label="channel exploded")
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
    landings = add_component_bom_balloons(
        adapter,
        exploded,
        items=items,
        anchors={
            stem: BalloonAnchor(
                point_mm=BRACKET_BALLOON_POINT_MM if stem == asm.BRACKET else None,
                instance=north_instances[stem],
            )
            for stem in BOM_COMPONENTS
        },
        label="channel exploded-view BOM coverage",
        margin=BALLOON_MARGIN,
    )
    if len(landings) != len(BOM_COMPONENTS):
        raise RuntimeError(
            f"channel exploded view carries {len(landings)} balloons, "
            f"expected one per BOM row ({len(BOM_COMPONENTS)})"
        )
    _add_note_block(
        adapter,
        SHEET_NAMES[1],
        EXPLODED_CAPTION,
        EXPLODED_CAPTION_XY,
        label="exploded-view caption",
    )
    # After the balloons, so the boundary circles are never picked as a
    # component's edge.
    _mark_exploded_details(adapter, exploded)
    _activate_sheet(adapter, SHEET_NAMES[1])
    for detail in EXPLODED_DETAILS:
        _exploded_detail(adapter, detail)
    return lambda: assert_balloon_landings(adapter, landings)


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
    isolate_drawing_view_components(
        adapter, view, visible_stems=bank.stems, label=bank.title
    )
    return view


def _sketch_view_circle(
    adapter: Any,
    view: Any,
    centre: tuple[float, float],
    radius_m: float,
    *,
    label: str,
) -> None:
    """Sketch a circle (sheet m) in ``view``'s own sketch, left selected."""
    view = _early_bound(view, "IView")
    _activate_view(adapter, view, label=label)
    sketch = _early_bound(view.GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    points = []
    for x, y in (centre, (centre[0] + radius_m, centre[1])):
        point = _early_bound(
            utility.CreatePoint(double_array([x, y, 0.0])), "IMathPoint"
        )
        projected = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
        points.append(tuple(float(value) for value in projected.ArrayData))
    manager = _early_bound(adapter.currentModel.SketchManager, "ISketchManager")
    previous = bool(manager.AddToDB)
    manager.AddToDB = False
    try:
        circle = manager.CreateCircle(*points[0], *points[1])
    finally:
        manager.AddToDB = previous
    if circle is None:
        raise RuntimeError(f"failed to sketch the {label} circle")


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


def _exploded_detail(adapter: Any, detail: BankView) -> None:
    """One enlarged, exploded hardware cluster: placed, isolated, cropped to
    its circle and labelled under it."""
    view = _placed_bank_view(adapter, detail)
    _crop(adapter, view, detail)
    _activate_view(adapter, view, label=detail.title)
    if add_note(adapter, detail.label_text, *detail.crop_label_xy) is None:
        raise RuntimeError(f"failed to label {detail.title}")


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
        if name in asm.REFERENCE_DIMENSIONS:
            if not reference:
                raise RuntimeError(f"{name}: not shown as a reference")
        else:
            lower, upper = asm.DIMENSION_TOLERANCES[name]
            if (
                reference
                or abs(float(tolerance.GetMaxValue()) - upper / 1000.0) > 1e-9
                or abs(float(tolerance.GetMinValue()) - lower / 1000.0) > 1e-9
                or int(display.GetPrimaryTolPrecision2()) != asm.TOLERANCE_PRECISION
            ):
                raise RuntimeError(
                    f"{name}: band is not {asm.DIMENSION_TOLERANCES[name]}"
                )
        text = str(display.GetText(CALLOUT_TEXT_PART) or "").replace("\r\n", "\n")
        if text != notes.DIMENSION_CALLOUTS[name]:
            raise RuntimeError(f"{name}: callout reads {text!r}")


def _place_labels(
    adapter: Any, sheet: str, labels: tuple[tuple[str, tuple[float, float]], ...]
) -> None:
    for text, xy in labels:
        _add_note_block(adapter, sheet, text, xy, label=f"{text} label")


def _place_steps(adapter: Any, sheet: str, text: str, *, label: str) -> None:
    _add_note_block(adapter, sheet, text, STEPS_XY, label=label)


def _place_fitup_sheets(adapter: Any) -> Callable[[], None]:
    """Sheets 3 and 4: the isolated banks with their settings, the steps."""
    _activate_sheet(adapter, SHEET_NAMES[2])
    annotations = _dimensioned_bank(adapter, ROCKER_BANK, STACK_KEEP, detail=SOUTH_END)
    annotations += _dimensioned_bank(
        adapter, SOUTH_END, SPRING_KEEP, pointers=DETAIL_POINTERS
    )
    _place_labels(adapter, SHEET_NAMES[2], ROCKER_END_LABELS)
    _place_steps(adapter, SHEET_NAMES[2], FITUP_NOTES[0], label="rocker-bank steps")

    _activate_sheet(adapter, SHEET_NAMES[3])
    annotations += _dimensioned_bank(adapter, LEVER_BANK, LUG_KEEP)
    annotations += _dimensioned_bank(
        adapter, KEEPER_PLAN, PLAN_KEEP, pointers=PLAN_POINTERS
    )
    _place_labels(adapter, SHEET_NAMES[3], LEVER_END_LABELS)
    _place_steps(adapter, SHEET_NAMES[3], FITUP_NOTES[1], label="lever-bank steps")

    for name, text in notes.DIMENSION_CALLOUTS.items():
        set_dimension_callouts(adapter, annotations, {name: text}, location="above")
    displays = _displays(adapter, annotations)
    for annotation in annotations:
        name = dimension_name(adapter, annotation)
        if name in asm.REFERENCE_DIMENSIONS:
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
    return lambda: _assert_settings(displays)


def _create_sheets(adapter: Any) -> None:
    new_project_drawing(adapter, layout=SPEC.layout, scale=SHEET_SCALE)
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
