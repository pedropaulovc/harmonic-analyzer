r"""Create the MHA-CH-00 channel assembly fitter package (six sheets).

1. ASSEMBLED VIEWS: Front and Right at 1:5 and the full-detail isometric at
   1:7. The Front carries the viewing arrows of views D, E and F, the Right
   that of view G.
2. EXPLODED VIEW + BOM: the builder-owned CHANNEL_EXPLODED isometric
   (ch_channel_explode_spec), the native BOM with the registry's part
   numbers, vendor SKUs and ch_channel_assembly_sheet's descriptions, and one
   balloon per BOM row. The spring's installed-length configurations group
   by their stamped part number into one MHA-CH-VN-50 row of 20 (#1610).
3. ROCKER BANK FIT-UP: view D, the bank isolated at 1:1 with the ears'
   inner-face span and the shaft's tip set, and the first rocker-bank steps.
   The arms float on the plain pivot shaft between the ears, each located by
   its own rod (#3114), and the shaft is held by a set screw in each ear
   (PR #1292; user, 2026-10-10).
4. ROCKER BANK FIT-UP (CONT.): detail A, the cropped 4:1 right end (the end
   hub clear of its ear), and the rest of the rocker-bank steps.
5. LEVER BANK FIT-UP: view E, the keepers, fulcrum shaft and levers isolated
   at 1:1 with the keeper lug span, view F, the 1:2 keeper plan with the
   keepers' three settings off the top frame's datums, and the first
   lever-bank steps.
6. LEVER BANK FIT-UP (CONT.): view G, the spring hook-up at 1:2, the rest
   of the lever-bank steps and the setting table of the lever bank's feeler
   acceptances.

Ends and sides are named as the right side views (D, E) draw them: left and
right, never a compass (drawing-guidelines.md rule 26). Steps name parts by
BOM item (rule 22). The settings are the assembly's own model dimensions (the
hidden rocker-bank, lever-bank and keeper-plan settings sketches,
build_ch_channel_assembly), not numbers in note text; the feeler-leaf
acceptances, which no model dimension carries, are setting-table rows the
steps cite. The steps are numbered by ``ch_channel_assembly_steps``.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import math
import re
import sys
import textwrap
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
from _component_order import by_name
import _config
from _drawing_balloon_display import rendered_balloon_circle
from _drawing_balloons import (
    BalloonAnchor,
    BalloonLanding,
    add_component_bom_balloons,
    assert_balloon_landings,
    isolate_drawing_view_components,
)
from _component_references import component_identity
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
from _drawing_tables import (
    bom_row_identities,
    insert_bom_table,
    validate_bom_number_property,
)
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
from _general_table import TABLE_TITLE_DROP, insert_general_table, table_column_widths
import _telemetry
import ch_channel_assembly_sheet as notes
import ch_channel_assembly_spec as asm
from fr_top_frame_spec import BORE_DIA as SOCKET_BORE_DIA
import ch_channel_explode_spec as explode
import ch_channel_assembly_steps as steps
from ch_channel_lever_spec import LEVER_SPRING_X
from ch_fulcrum_keeper_spec import (
    CROWN_TOP_Y as KEEPER_CROWN_TOP_Y,
    FULCRUM_KEEPER_CENTRE_Z,
    KEEPER_FITUP_X_FROM_WEB_MM,
    KEEPER_INNER_FACE_FROM_FRONT_SOCKET_MM,
    KEEPER_INNER_FACE_SPAN_MM,
    KEEPER_Z_OFF,
    LUG_HALF_T as KEEPER_LUG_HALF_T,
)
from ch_fulcrum_shaft_spec import (
    FLAT_HEIGHT as FULCRUM_FLAT_Y,
    FLAT_PITCH as FULCRUM_FLAT_PITCH,
    SHAFT_R as FULCRUM_SHAFT_R,
)
from ch_pivot_bracket_sides import FOOT_Z1 as BRACKET_FOOT_Z1
from ch_pivot_bracket_spec import (
    FOOT_H as BRACKET_FOOT_H,
    FOOT_W as BRACKET_FOOT_W,
)
from ch_pivot_shaft_spec import (
    FLAT_DEPTH as PIVOT_FLAT_DEPTH,
    SHAFT_DIA as PIVOT_SHAFT_DIA,
)
from channel_frame_geom import LEVER_FULCRUM_XY, ROCKER_PIVOT_XY
from frame_column_stations import COLUMN_X
from rocker_bank_layout import (
    COUNT,
    HUB0_SOUTH_FACE_Z,
    PIVOT_BRACKET_Z,
    PIVOT_SHAFT_FLAT_STATIONS,
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
# Centred between the borders: _assert_view_on_sheet grows the outline by
# the balloon ring on all four sides, so either end is the first to reach a
# border (point B at the .300 pitch: 0.2539 of the 0.254 between them, the
# top 0.25 mm over at y 0.140).
EXPLODED_ISO_CENTER = (0.100, _TEMPLATE.height_m / 2.0)
# The lever balloon's leader runs along the bank axis, and the exploded fulcrum
# shaft lies on that axis's south extension. The shaft has no hit-testable
# edge, so SolidWorks picks where its leader lands (listed-edge), and that
# landing moved 15 mm between r8 and r9. The view is tall and narrow, so 8 of
# the 19 balloons crowd its top. At 14 mm the ring's push-apart swung balloon
# 14 down over the shaft, and a south-end landing crossed leader 2 (r9 audit).
# A replay of the ring with the anchor-nut balloon (retired, #2326) added
# covers every landing on the visible shaft, nut attachments at least 3.5 mm
# below the anchor's, and balloon radius 5.0-5.6 mm. At 28 mm it crosses
# nothing and keeps leader 14 2.1-4.4 mm off the shaft, but the ring's
# centres ran 5.5 mm inside the border at the top, so balloon 4's 5.6 mm
# circle touched it (machinist
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
# Balloon 1 (the rocker pivot shaft): left in the hubs only a stub of it
# showed and the balloon landed on that sliver beside the end hardware (#1895 and
# R5 machinist reviews). The shaft is drawn north out of the bank
# (ch_channel_explode_spec), its north half past the hanging rods onto open
# paper; the landing is the north flat's edge on the eye's side, at the
# flat's middle (half an ear from the north end): the flat faces +y, so both
# faces at that edge face the eye. Part frame (ch_pivot_shaft_spec): axis
# along z from the north cylinder end, unturned in the assembly.
PIVOT_SHAFT_STEM = explode.PIVOT_SHAFT
_PIVOT_FLAT_Y = PIVOT_SHAFT_DIA / 2.0 - PIVOT_FLAT_DEPTH
PIVOT_SHAFT_BALLOON_POINT_MM = (
    math.sqrt((PIVOT_SHAFT_DIA / 2.0) ** 2 - _PIVOT_FLAT_Y**2),
    _PIVOT_FLAT_Y,
    -PIVOT_SHAFT_FLAT_STATIONS[1],
)
# Off the ring, its circle stands this far (sheet m) straight above that
# landing: in the open strip between the pulled channel's bar and the bank's
# hanging rods, left of the north bracket's trail (an ink scan of the farm
# run 20261117T130021685Z sheet found no ink in a 6.8 mm disc there or on the
# leader's path).
PIVOT_SHAFT_BALLOON_OFFSET = (0.0, 0.017)
# Balloon 2 (the lever fulcrum shaft) walked to a body extreme among the
# stacked lever hubs, where the shaft shows only as slivers, and read as
# naming the levers (machinist review on PR #2702, three runs of three). Its
# landing is the south flat's eye-side edge at the flat's middle, as balloon
# 1's: withdrawn south (ch_channel_explode_spec), that flat stands on the bare
# run past the exploded south keeper, the shaft's only clear length. Part
# frame (ch_fulcrum_shaft_spec): axis along z centred on 0, flats on +y,
# unturned in the assembly.
FULCRUM_SHAFT_BALLOON_POINT_MM = (
    math.sqrt(FULCRUM_SHAFT_R**2 - FULCRUM_FLAT_Y**2),
    FULCRUM_FLAT_Y,
    -FULCRUM_FLAT_PITCH / 2.0,
)
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

# One spring part whose installed-length configurations
# (build_ch_vn_channel_spring_installed) group into one BOM row.
CHANNELS = _config.active_count()
if CHANNELS != COUNT:
    raise AssertionError("the channel package is drawn for the full bank")
SPRING_STEM = explode.CHANNEL_SPRING

BOM_QUANTITIES = {
    "ch-pivot-shaft": 1,
    "ch-fulcrum-shaft": 1,
    explode.BRACKET: 2,
    explode.BRACKET_SET_SCREW: 2,
    explode.BRACKET_HOLD_DOWN: 2,
    explode.KEEPER: 2,
    explode.KEEPER_FOOT_SCREW: 2,
    explode.KEEPER_SET_SCREW: 2,
    "ch-rocker-arm": CHANNELS,
    explode.ROD: CHANNELS,
    explode.BAR: CHANNELS,
    "ch-channel-lever": CHANNELS,
    explode.ROD_PIN: CHANNELS,
    explode.BAR_PIN: CHANNELS,
    SPRING_STEM: CHANNELS,
    explode.HOOK: CHANNELS,
}
BOM_COMPONENTS = tuple(BOM_QUANTITIES)
# Rows bind to native (file, member) identities, never displayed Number: the
# purchased pivot pin's RodPin and BarPin members share MHA-SH-VN-58.
BOM_COMPONENT_IDENTITIES: dict[str, tuple[str, str | None]] = {
    key: (explode.PIVOT_PIN, key.removeprefix(f"{explode.PIVOT_PIN}--"))
    if key in (explode.ROD_PIN, explode.BAR_PIN)
    else (key, None)
    for key in BOM_COMPONENTS
}
# Literal stems, so the config-dependency analysis reads exactly these rows.
PART_ROWS = {
    "ch-pivot-shaft": _config.parts("ch-pivot-shaft"),
    "ch-fulcrum-shaft": _config.parts("ch-fulcrum-shaft"),
    "ch-pivot-bracket": _config.parts("ch-pivot-bracket"),
    "sh-vn-arbor-set-screw": _config.parts("sh-vn-arbor-set-screw"),
    "ch-vn-bracket-hold-down-screw": _config.parts("ch-vn-bracket-hold-down-screw"),
    "ch-fulcrum-keeper": _config.parts("ch-fulcrum-keeper"),
    "ch-vn-frame-side-screw": _config.parts("ch-vn-frame-side-screw"),
    "ch-vn-fulcrum-set-screw": _config.parts("ch-vn-fulcrum-set-screw"),
    "ch-rocker-arm": _config.parts("ch-rocker-arm"),
    "ch-connecting-rod": _config.parts("ch-connecting-rod"),
    "ch-amplitude-bar": _config.parts("ch-amplitude-bar"),
    "ch-channel-lever": _config.parts("ch-channel-lever"),
    explode.ROD_PIN: _config.parts("sh-vn-pivot-pin"),
    explode.BAR_PIN: _config.parts("sh-vn-pivot-pin"),
    SPRING_STEM: _config.parts("ch-vn-channel-spring-installed"),
    "ch-vn-spring-hook": _config.parts("ch-vn-spring-hook"),
}
if set(PART_ROWS) != set(BOM_COMPONENTS):
    raise AssertionError("BOM registry rows must cover exactly the assembly families")
BOM_PART_NUMBERS = {stem: str(row["number"]) for stem, row in PART_ROWS.items()}
BOM_SKUS = {
    stem: " / ".join(str(sku) for sku in row.get("supplier_skus") or ())
    or MADE_PART_SKU
    for stem, row in PART_ROWS.items()
}
BOM_DESCRIPTIONS = {stem: notes.BOM_DESCRIPTIONS[stem] for stem in BOM_COMPONENTS}
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
# Point B at the .300 pitch: view D's outline grew to 0.2013 wide at 1:1 (the
# 6.85 pivot shaft), exactly the 0.2013 between the border and a column at
# 0.214. At 0.222 the 64-character column ends at 0.399, inside the border.
STEPS_RIGHT_X = 0.222
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
    letter_offset: float | None = None  # sheet m past the boundary; None: default
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
    # 201 mm wide at 1:1 at the .300 pitch (point B outline 0.0106-0.2120
    # about x 0.111; 188 at 7.0565): centred between the left border and the
    # steps column, and low enough that the view and its label sit in the
    # middle of the sheet's left half (round 1 review: no empty field beside a
    # short column).
    (0.117, 0.165),
    frozenset(
        {
            "ch-pivot-shaft",
            explode.BRACKET,
            explode.BRACKET_SET_SCREW,
            explode.BRACKET_HOLD_DOWN,
            "ch-rocker-arm",
        }
    ),
    parts="ROCKER BANK",
)
# The right end at 4:1: the ear's inner face and the end hub, the air between
# them centred in the circle on the pivot axis (the end hub clears its ear,
# #3114). It prints on sheet 4, right of that sheet's step column; its
# boundary is on view D (sheet 3).
DETAIL_LETTER = "A"
DETAIL_SHEET = SHEET_NAMES[3]
_DETAIL_CENTRE_Z = (asm.PIVOT_CHAIN_Z[0] + HUB0_SOUTH_FACE_Z) / 2.0
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
            "ch-rocker-arm",
        }
    ),
    crop_radius_mm=8.0,
    parts="FROM VIEW D (SHEET 3)",
    letter=DETAIL_LETTER,
)
# The letter sits this far (sheet m) outside the parent's boundary circle, up
# and to the south, clear of the ear (its outer face 9.0 mm south of centre)
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
    offset: float | None = None,
) -> tuple[float, float]:
    """A detail letter's note point, ``offset`` (sheet m, default
    DETAIL_LETTER_OFFSET) past its boundary toward ``corner`` (x, y signs:
    (1, 1) upper right)."""
    reach = radius + (DETAIL_LETTER_OFFSET if offset is None else offset)
    return centre[0] + corner[0] * reach, centre[1] + corner[1] * reach


LEVER_BANK = BankView(
    "VIEW E",
    (1, 1),
    (_FULCRUM_X, _FULCRUM_Y, FULCRUM_KEEPER_CENTRE_Z),
    # Over view D's centre line, between the border and the steps column;
    # 3 mm higher than at 7.0565 with view F below it (see KEEPER_PLAN_SOCKET_Y).
    (0.117, 0.198),
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
    # The caption sits 4 mm under the view's lowest ink, the keeper foot
    # screws' tips at y 0.172 (farm sheet at c47b9b6). The default point
    # (4 mm under the view outline, which runs about 10 mm below that ink)
    # put it 6 mm over view F's LUG CENTRE callout and 15 mm under its own
    # view, so it read as view F's (machinist review r1 and r2, 2026-11-19).
    label_xy=(0.101, 0.168),
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
# the socket line 0.123 up. The farm-measured outline (c80bb08be) ran 0.1051
# below the socket line at 7.0565; at the .300 pitch the rear lug face moved
# 7.1852 -> 7.4102 (+5.715, 2.86 at 1:2), so at 0.120 its bottom would cross
# the border by 0.7 mm. At 0.123 it clears it by about 2.3 mm, and view E
# rises 3 mm with it; the boss tops the outline 0.0113 above.
KEEPER_PLAN_SOCKET_Y = 0.123
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
# spring and anchor, the 20 channels in line behind the nearest. The
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
# The X text right of the boss, its dimension line clear of the boss top and
# off the inner-face dimensions' shared extension line on the socket line
# (5d5245a review); each Z text centred on its own dimension line west of
# the keepers, the rear's inside the front's so neither text sits on the
# other's line (the front line stops at the front face, above the rear text;
# the front text clears the rear line by 3 mm). The X text is a three-row
# block (callout, value, the rail web wall under it): SolidWorks centres a
# block on its text position and hangs the dimension line under its last
# row (MHA-FR-02 sheet 7's draft callout, farm run 20261125T172832344Z), so
# the third row lowers that line half a row, about 3 mm; the text rises 3 mm
# to keep the line where the two-row block left it (y 0.1347 on that run's
# sheet 5, over the boss top at 0.1345). The wall row is the block's widest,
# about 75 mm (MHA-FR-02's 28-character HOLDS 2-56 TAP WALL .076 MIN
# measured 68.4 mm), 86 mm at the note glyph width; centred 0.050 east of
# the lug it runs from about 0.125 (0.119 at most), east of both extension
# lines at 0.112, to 0.200 (0.205 at most), short of the steps column at
# 0.222.
PLAN_KEEP = {
    asm.KEEPER_X_DIMENSION: (_PLAN_LUG[0] + 0.050, KEEPER_PLAN_SOCKET_Y + 0.020),
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
        if stem in step.stems and step.side in sides:
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
# exploded set screw, hold-down or foot screw, 29 to 40 mm from those centres
# in the isometric (estimated from the spec dimensions, with margin).
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
        }
    ),
    crop_radius_mm=44.0,
    parts=items_text(
        (explode.BRACKET, explode.BRACKET_SET_SCREW, explode.BRACKET_HOLD_DOWN),
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
    # 10 mm clear of the lower right. 6 mm out, not 2: at 2 the letter stood
    # on the bar bank's right edge and its outline struck through the C
    # (machinist review on PR #2702).
    letter_corner=(1, -1),
    letter_offset=0.006,
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
    explode.FULCRUM_SHAFT: FULCRUM_SHAFT_BALLOON_POINT_MM,
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
_EAR_SPAN_MID = (asm.PIVOT_CHAIN_Z[0] + asm.PIVOT_CHAIN_Z[1]) / 2.0
_LUG_MID = sum(asm.LUG_INNER_FACE_Z) / 2.0
EAR_SPAN_KEEP = {
    asm.EAR_SPAN_DIMENSION: ROCKER_BANK.sheet_xy(_EAR_SPAN_MID, _PIVOT_Y + 40.0)
}
# The left tip's set proud of the left ear's outer face (R5 machinist review,
# rule 22: printed in the shaft-set step only). Its two extension lines stand
# 1.5 mm apart left of the ear span's, so its text rides above the span
# callout. Not between them: centred on the gap, both lines ran up into the
# '6' and '0' of .060 (farm run 20261117T130021685Z machinist review, rule
# 14); 19 mm right of the gap the text stands wholly right of the ear-face
# line, its dimension line carried to it.
_TIP_MID = (asm.PIVOT_CHAIN_Z[2] + asm.PIVOT_CHAIN_Z[3]) / 2.0
TIP_KEEP = {
    asm.TIP_PROUD_DIMENSION: ROCKER_BANK.sheet_xy(_TIP_MID - 19.0, _PIVOT_Y + 62.0)
}
ROCKER_KEEP = {**EAR_SPAN_KEEP, **TIP_KEEP}
# Detail A names the two bodies the end-hub check is read between (b9ae
# machinist review: the caption listed them, nothing in the view said which
# outline was which): (text, text upper-left as an offset from the detail's
# centre, pointer tip in the detail's plane as machine (z, y)). The hub to
# the left of the circle, above the axis; the ear to the right, its tip
# below the axis.
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
            HUB0_SOUTH_FACE_Z + 1.0,
            3.0,
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
# swDimensionTextParts_e compartments.
CALLOUT_TEXT_PART = 3  # swDimensionTextCalloutAbove
CALLOUT_BELOW_PART = 4  # swDimensionTextCalloutBelow
REFERENCE_PREFIX_PART = 1  # swDimensionTextPrefix
REFERENCE_SUFFIX_PART = 2  # swDimensionTextSuffix
BROKEN_LINE_ALIGNED_TEXT = 3  # swDisplayDimensionLeaderText_e.swBrokenLeaderAlignedText
# The sheet module's callouts, the arm named by its BOM item.
DIMENSION_CALLOUTS = {
    name: text.format(arm=item("ch-rocker-arm"))
    for name, text in notes.DIMENSION_CALLOUTS.items()
}
if any("\n" in text for text in DIMENSION_CALLOUTS.values()):
    raise AssertionError("an above-callout with a line break does not print")
DIMENSION_BELOW_CALLOUTS = dict(notes.DIMENSION_BELOW_CALLOUTS)


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
# Sheet 3: right of view D, then under view D's caption. Sheet 4: the
# full-height left column, then under detail A's caption. Sheet 5: right of
# views E and F. Sheet 6: the full-height left column, then the setting table
# under view G's label on the right (round 1 review: balanced sheets, no lone
# step in an empty half). Each right column runs down to the title block.
# With every remedy one action a step (rule 22), the bonded-pin blocks ending
# in a replaced part and the strap check back in its own bank, the rocker
# bank needs the two short columns as well; a check and its remedy block
# print in one column (ROCKER_BLOCKS), so the end-hub check and both hub
# blocks print together beside detail A.
_HOOKUP_LABEL_FOOT = (
    HOOKUP_BOTTOM_Y - 0.004 - len(HOOKUP.label_text.splitlines()) * NOTE_LINE_PITCH
)
# View D's caption foot: the farm render (chms-r3, 2026-11-21) prints its two
# lines under the outline from about y 0.114 to 0.105; the column starts a
# line and more below it, and _dimensioned_bank refuses a caption that
# reaches it.
ROCKER_UNDER_VIEW_TOP = 0.095
# Detail A's caption (under its circle) ends here; the column starts a line
# below it.
_DETAIL_LABEL_FOOT = (
    SOUTH_END.crop_label_xy[1] - len(SOUTH_END.label_text.splitlines()) * NOTE_LINE_PITCH
)
ROCKER_COLUMNS = (
    StepColumn(SHEET_NAMES[2], (STEPS_RIGHT_X, STEPS_TOP_Y), _RIGHT_FOOT),
    StepColumn(SHEET_NAMES[2], (STEPS_LEFT_X, ROCKER_UNDER_VIEW_TOP), _BORDER_FOOT),
    StepColumn(SHEET_NAMES[3], (STEPS_LEFT_X, STEPS_TOP_Y), _BORDER_FOOT),
    StepColumn(
        SHEET_NAMES[3],
        (STEPS_RIGHT_X, _DETAIL_LABEL_FOOT - NOTE_LINE_PITCH),
        _RIGHT_FOOT,
    ),
)
# Each check with the remedy block that follows it prints in one column.
ROCKER_BLOCKS = (
    ("rod-arms-swing", *steps.ROD_PIN_REMEDY),
    ("end-hubs-clear", *steps.LEFT_HUB_REMEDY, *steps.RIGHT_HUB_REMEDY),
    ("straps-shake-in-forks", *steps.STRAP_SHAKE_REMEDY),
)


# A reference word and its number or letter (ITEM 10, STEP 5, VIEW D) print
# on one line: wrapped with a placeholder space textwrap never breaks at.
_REFERENCE_SPACE = re.compile(r"\b(ITEM|STEP|SHEET|VIEW|DETAIL|ROW) (?=\w)")
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
    together: tuple[tuple[str, ...], ...] = (),
) -> tuple[tuple[StepColumn, str], ...]:
    """Flow ``keys``' wrapped steps down ``columns`` in order: one blank line
    between consecutive steps (user request), a step never split, each
    column headed by ``heading`` (its continuations ``heading (CONT.)``).
    Each run of keys in ``together`` (consecutive in ``keys``) prints in one
    column. Columns left over stay empty."""
    wrapped = {key: _wrapped_step(key, text[key]) for key in keys}
    run_lines: dict[str, int] = {}
    for run in together:
        start = keys.index(run[0])
        if keys[start : start + len(run)] != run:
            raise AssertionError(f"{run[0]!r}'s block is not consecutive")
        run_lines[run[0]] = sum(len(wrapped[key]) for key in run) + len(run) - 1
    blocks: list[tuple[StepColumn, str]] = []
    remaining = iter(columns)
    column = next(remaining)
    lines = [heading]
    for key in keys:
        step = wrapped[key]
        gap = [""] if len(lines) > 1 else []
        need = run_lines.get(key, len(step))
        if len(lines) + len(gap) + need > column.capacity:
            if len(lines) == 1:
                raise AssertionError(f"step {key!r} does not fit an empty column")
            blocks.append((column, "\n".join(lines)))
            column = next(remaining, None)  # type: ignore[arg-type]
            if column is None:
                raise AssertionError(f"{heading} overflows its columns at {key!r}")
            lines, gap = [f"{heading} (CONT.)"], []
            if len(lines) + need > column.capacity:
                raise AssertionError(f"step {key!r} does not fit an empty column")
        lines += gap + step
    blocks.append((column, "\n".join(lines)))
    return tuple(blocks)


# --- sheet 6: the setting table ------------------------------------------------
# ch_channel_assembly_sheet owns the rows' values; the drawing numbers each
# row's part from its BOM and places the table under view G's label, right of
# the full-height step column.
SETTING_TABLE_SHEET = SHEET_NAMES[notes.SETTING_TABLE_SHEET_NUMBER - 1]
SETTING_TABLE_ROWS = tuple(
    (
        str(row),
        str(steps.step_number(key)),
        f"{item(stem)} {setting}" if stem else setting,
        "-",
        accept,
        check,
    )
    for row, (key, stem, setting, accept, check) in enumerate(notes.SETTINGS, start=1)
)
SETTING_TABLE_XY = (0.205, _HOOKUP_LABEL_FOOT - 0.008)  # the title's top left
SETTING_TABLE_ROW_HEIGHT = 0.0055  # a general table row at the note font


def setting_table_box() -> tuple[float, float, float, float]:
    """The setting table's planned box (x0, y0, x1, y1) under its title."""
    x, top = SETTING_TABLE_XY
    top -= TABLE_TITLE_DROP
    width = sum(table_column_widths(notes.SETTING_TABLE_HEADER, SETTING_TABLE_ROWS))
    height = (len(SETTING_TABLE_ROWS) + 1) * SETTING_TABLE_ROW_HEIGHT
    return (x, top - height, x + width, top)


_planned = setting_table_box()
if _planned[0] < STEPS_LEFT_X + STEPS_LINE_WIDTH * NOTE_CHAR_WIDTH:
    raise AssertionError("the setting table runs into the left step column")
if _planned[2] > _TEMPLATE.width_m - BORDER - 0.003:
    raise AssertionError("the setting table runs past the right border")
if _planned[1] < _TEMPLATE.title_block_top_m + 0.003:
    raise AssertionError("the setting table runs into the title block")
# C10 (the rear keeper set to the bare stack) adds a step and threads the
# levers at the keepers' fit-up: the lever steps run on under the setting
# table, down to the title block.
LEVER_COLUMNS = (
    StepColumn(SHEET_NAMES[4], (STEPS_RIGHT_X, STEPS_TOP_Y), _RIGHT_FOOT),
    StepColumn(SHEET_NAMES[5], (STEPS_LEFT_X, STEPS_TOP_Y), _BORDER_FOOT),
    StepColumn(SHEET_NAMES[5], (STEPS_RIGHT_X, _planned[1] - 0.006), _RIGHT_FOOT),
)


def _fitup_text() -> dict[str, str]:
    """Every step's text, keyed as ``ch_channel_assembly_steps.SEQUENCE``."""
    # Literal stems, so the config-dependency analysis reads exactly these rows.
    support = _config.parts("fr-rocker-arm-support")["number"]
    top_frame = _config.parts("fr-top-frame")["number"]
    shaft, fulcrum_shaft = item("ch-pivot-shaft"), item("ch-fulcrum-shaft")
    bracket, pivot_set_screw = item(explode.BRACKET), item(explode.BRACKET_SET_SCREW)
    hold_down, keeper = item(explode.BRACKET_HOLD_DOWN), item(explode.KEEPER)
    foot_screw = item(explode.KEEPER_FOOT_SCREW)
    fulcrum_set_screw = item(explode.KEEPER_SET_SCREW)
    arm, rod, bar = item("ch-rocker-arm"), item(explode.ROD), item(explode.BAR)
    lever, pin = item("ch-channel-lever"), item(explode.ROD_PIN)
    bar_pin, channel_spring = item(explode.BAR_PIN), item(SPRING_STEM)
    anchor = item(explode.HOOK)
    rocker_view, lever_view = ROCKER_BANK.title, LEVER_BANK.title
    plan_view, hookup_view = KEEPER_PLAN.title, HOOKUP.title
    detail = f"{SOUTH_END.title}, SHEET {SHEET_NAMES.index(DETAIL_SHEET) + 1}"

    def n(key: str) -> int:
        return steps.step_number(key)

    # Each keeper lug is set off the top-frame rail web under it (its column's
    # socket axis) in X and off the frame's hole-station origin line, the
    # upper socket centres, in Z (Main's ruling): the lug centre on the
    # fulcrum line, its inner face off the front socket line. The frame is not
    # in this assembly, so view F draws both datums and prints the three
    # settings, each banded (owner ruling X1+B1, b9ae review).
    if abs(LEVER_FULCRUM_XY[0] - COLUMN_X - KEEPER_FITUP_X_FROM_WEB_MM) > 1e-9:
        raise AssertionError("KEEPER_FITUP_X_FROM_WEB_MM is off the fulcrum line")
    front_face, rear_face = KEEPER_INNER_FACE_FROM_FRONT_SOCKET_MM
    # The lug span the fit-up sets (KEEPERS_SET_KEY) is view E's reference
    # lug span.
    if abs(rear_face - front_face - KEEPER_INNER_FACE_SPAN_MM) > 1e-9:
        raise AssertionError("the view E lug span is not the fit-up span")
    return {
        # Each rod + arm pair is pinned at the bench, before the drive-train
        # cylinder stack captures the rod rings in their cams; the arms float
        # on the shaft, each located by its rod (#3114), so they go on in any
        # order.
        steps.RODS_PINNED_KEY: (
            f"BEFORE {steps.CYLINDER_STACK_REF}, AT THE BENCH: PRESS ONE {pin} "
            f"PIN THROUGH EACH {rod} ROD FORK AND THE PIVOT HOLE OF ONE {arm}, "
            "FAR TINE BACKED."
        ),
        "rod-pins-dressed": f"DRESS BOTH ENDS OF EACH {pin} FLUSH WITH THE TINES.",
        "rod-pins-held": f"CHECK EACH {pin} DOES NOT SLIDE IN ITS FORK BY HAND.",
        "rod-arms-swing": (
            f"CHECK EACH {arm} SWINGS FREE ON ITS PIN BY ITS OWN WEIGHT."
        ),
        # A press whose pin slides in by hand is bonded with LOCTITE 641, not
        # a replaced rod (owner ruling 2026-11-24, fit audit question 3): the
        # pin bond note on the detail sheet says how (one end only, the
        # compound kept off the arm), and the bond is checked once cured, one
        # check a step as rod-pins-held and rod-arms-swing are. One action a
        # step (rule 22); every step after the bond opens "BONDED PIN:", as
        # the hub blocks open "LEFT HUB:", so none reads as main flow. A bond
        # that fails is not bonded again: the pin comes out hot (641 is the
        # removable grade, the pin bond note's step 1) and the rod is replaced,
        # as main replaced it, the new one going back to the pinning step.
        "rod-pin-bonded": (
            f"IF AN {pin} SLID IN BY HAND, BOND IT PER THE PIN BOND NOTE "
            f"(SHEET {SHEET_NAMES.index(DETAIL_SHEET) + 1})."
        ),
        "rod-pin-bond-held": f"BONDED PIN: CURED, CHECK {pin} DOES NOT SLIDE BY HAND.",
        "rod-pin-bond-swings": (
            f"BONDED PIN: CHECK {arm} SWINGS FREE ON ITS PIN BY ITS OWN WEIGHT."
        ),
        "rod-pin-pushed-out": (
            f"BONDED PIN: IF {pin} SLIDES OR {arm} BINDS, PUSH THAT PIN OUT, "
            "HEATING THE TINES."
        ),
        "rod-replaced": f"BONDED PIN: REPLACE THAT {rod}.",
        "rod-pin-return": (
            f"BONDED PIN: RETURN TO STEP {n(steps.RODS_PINNED_KEY)} WITH THE NEW {rod}."
        ),
        # The fitter leaves this list after the rod pins for the drive train's
        # cylinder stack through its north-bracket set, then comes back here
        # (#2330 machinist review, rule 22: the hand-off is printed).
        "north-bracket-held": (
            f"AFTER {steps.CYLINDER_STACK_REF} THROUGH {steps.NORTH_BRACKET_SET_REF}, "
            f"CHECK THE LEFT {bracket} OF {rocker_view}, SET THERE, DOES NOT TURN "
            "BY HAND."
        ),
        # The right bracket is set off the left one, set at the drive train's
        # north-bracket step on the same mill, to the ears' inner-face span
        # view D prints (rocker_bank_layout.EAR_INNER_SPAN, #3114), while the
        # shaft runs bare through both ears: with the arms on it each inner
        # face is only .05 from its end hub, out of an edge finder's reach.
        "south-bracket-stood": (
            f"WITH THE BASE ON THE MILL AS AT {steps.NORTH_BRACKET_SET_REF}, "
            f"STAND THE RIGHT {bracket} ON {support}."
        ),
        "bare-shaft-through-ears": (
            f"PUSH {shaft}, FLATS UP, THROUGH THE LEFT {bracket} EAR AND ON THROUGH "
            f"THE RIGHT {bracket} EAR, CLEAR OF THE HANGING {arm}."
        ),
        "south-bracket-span-set": (
            f"WITH AN EDGE FINDER, BY DRO, SET THE RIGHT {bracket} EAR INNER FACE "
            f"OFF THE LEFT EAR INNER FACE, TO THE {rocker_view} EAR SPAN."
        ),
        "south-bracket-clamped": f"CLAMP THE RIGHT {bracket} TO {support}.",
        "shaft-drawn-back": (
            f"DRAW {shaft} BACK TO THE LEFT UNTIL ITS RIGHT END IS IN THE LEFT "
            f"{bracket} EAR."
        ),
        "arms-swung-up": f"SWING EACH {arm} UP ON ITS {rod}.",
        "rocker-hubs-threaded": (
            f"PUSH {shaft} ON THROUGH THE {arm} HUBS, LEFT TO RIGHT, AND INTO THE "
            f"RIGHT {bracket} EAR."
        ),
        # The end-hub check runs while the right bracket is only clamped, so a
        # failed check is re-set before anything is drilled or tapped
        # (machinist review, PR #1605). The rods are in their cams, but each
        # end arm floats by its rod's ring and fork play, so a leaf pushed
        # into a tight gap would slide the arm away and pass a mis-set ear:
        # the arm is first pushed toward its ear until its rod stops it, the
        # extreme rocker_bank_layout.END_CLEARANCE_MIN charges, and gauged
        # held there (Codjiflo, PR #3116).
        "end-arms-pushed-to-ears": (
            f"PUSH EACH END {arm} TOWARD ITS EAR UNTIL {rod} STOPS IT."
        ),
        "end-hubs-clear": (
            f"CHECK THE FEELER LEAF OF {notes.setting_row('end-hubs-clear')} "
            f"PASSES BETWEEN EACH END {arm} HUB, HELD AS AT STEP "
            f"{n('end-arms-pushed-to-ears')}, AND ITS {bracket} EAR ({detail})."
        ),
        # Each end its own remedy block (rule 22: one action a step), both
        # back to the bare shaft; the block opens with its condition and every
        # later step carries the block's prefix, so none reads as main flow.
        # Drawn out of the hubs, the shaft lets the arms drop and hang on
        # their rods by themselves. The left bracket was set and screwed at
        # MHA-DT-00 (its Ø.180 foot hole gives the #8 screw room to shift), so
        # it is reset by that sheet's set, screw and recheck sub-steps; the
        # right bracket, re-spanned off it, follows.
        "left-hub-shaft-drawn-back": (
            f"LEFT HUB, IF THE LEAF DID NOT PASS THERE: DRAW {shaft} BACK AS AT "
            f"STEP {n('shaft-drawn-back')}."
        ),
        "left-hub-clamp-eased": f"LEFT HUB: EASE THE CLAMP ON THE RIGHT {bracket}.",
        "left-hub-hold-down-loosened": f"LEFT HUB: LOOSEN THE LEFT {hold_down}.",
        "left-hub-bracket-reset": (
            f"LEFT HUB: RESET THE LEFT {bracket} PER {steps.NORTH_BRACKET_SET_REF}B."
        ),
        "left-hub-hold-down-tightened": (
            f"LEFT HUB: TIGHTEN THE LEFT {hold_down} PER "
            f"{steps.NORTH_BRACKET_SET_REF}E."
        ),
        "left-hub-bracket-rechecked": (
            f"LEFT HUB: RECHECK PER {steps.NORTH_BRACKET_SET_REF}F."
        ),
        "left-hub-return": (
            f"LEFT HUB: RETURN TO STEP {n('bare-shaft-through-ears')}."
        ),
        "right-hub-shaft-drawn-back": (
            f"RIGHT HUB, IF THE LEAF DID NOT PASS THERE: DRAW {shaft} BACK AS AT "
            f"STEP {n('shaft-drawn-back')}."
        ),
        "right-hub-clamp-eased": f"RIGHT HUB: EASE THE CLAMP ON THE RIGHT {bracket}.",
        # A right hub that fails sits too near its ear: the re-set moves the
        # right ear outward, to the span's upper limit as view D prints it.
        # One action a step (rule 22): the span's new setting, then the return.
        "right-hub-span-to-upper-limit": (
            f"RIGHT HUB: AT STEP {n('south-bracket-span-set')}, SET THE EAR SPAN TO "
            f"ITS UPPER LIMIT, {notes.EAR_SPAN_UPPER_TEXT}."
        ),
        "right-hub-return": (
            f"RIGHT HUB: RETURN TO STEP {n('bare-shaft-through-ears')}."
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
            f"SLIDE {shaft} UNTIL ITS LEFT TIP MEETS THE {rocker_view} TIP PROUD "
            "DIMENSION (CALIPER DEPTH ROD)."
        ),
        # Owner ruling 2026-11-20 (#2397, option 2): the shaft is pulled to
        # change one channel part, so its set screws are not staked; each
        # holds on its flat (threaded-joint-retention.md
        # U-MHA-SH-VN-54-in-CH-08-no-lock). The Loctite waiver was retired on
        # 2026-10-16 under the user's standing no-threadlocker rule.
        "set-screws-driven": (
            f"WITH {shaft} FLATS UP, TIGHTEN ONE {pivot_set_screw} DOWN THE TAP "
            f"AT THE TOP OF EACH {bracket} EAR ONTO ITS FLAT, LEFT EAR FIRST."
        ),
        "pivot-shaft-held": f"CHECK {shaft} DOES NOT TURN OR SLIDE BY HAND.",
        "arms-follow-rods": (
            f"CHECK EACH {arm} SLIDES FREELY ON {shaft}, FOLLOWING ITS {rod}."
        ),
        # Owner ruling 2026-11-20 (#2343, option 2): the strap's position
        # frame stays on the arm's sheet, and the fork clearance is its
        # functional check, made with the rocker bank on the shaft and the
        # rods in their cams, before the bars sit on the arms; a strap that
        # binds is set by hand: the strap is a flexure (#2343), bent off the
        # tine it bears on.
        "straps-shake-in-forks": (
            f"CHECK EACH {arm} ARM SHAKES SIDEWAYS IN ITS {rod} FORK."
        ),
        "strap-set-by-hand": f"IF AN {arm} ARM BINDS, BEND IT OFF ITS TINE BY HAND.",
        "strap-set-return": f"RETURN TO STEP {n('straps-shake-in-forks')}.",
        "keepers-on-frame": (
            f"WITH {top_frame} ON THE MILL, STAND BOTH {keeper} ON ITS RAIL AS "
            f"{plan_view} SHOWS, FEET OUTWARD."
        ),
        # C10 (ch_channel_assembly_spec REAR_KEEPER_LEAF_MM): the rear keeper
        # is set to the bare levers, so they go on with the shaft.
        "fulcrum-shaft-through-keepers": (
            f"PUSH {fulcrum_shaft} THROUGH BOTH {keeper} AND {COUNT} BARE {lever} "
            "LEVERS."
        ),
        steps.KEEPERS_SET_KEY: (
            f"BY DRO, SET EACH LUG CENTRE OFF THE RAIL WEB CENTRE, TO {plan_view}."
        ),
        "keeper-faces-set": (
            "BY DRO, SET THE RIGHT LUG INNER FACE OFF THE LINE OF THE UPPER "
            f"SOCKET CENTRES, TO {plan_view}."
        ),
        "rear-keeper-to-stack": (
            f"HOLDING THE RIGHT {keeper}, PUSH THE LEFT ONE UP TO THE {lever} "
            f"HUBS ON THE FEELER LEAF OF {notes.setting_row('rear-keeper-to-stack')}."
        ),
        "keepers-clamped-on-frame": f"CLAMP BOTH {keeper} TO THE RAIL.",
        # The leaf set the left keeper's station; it comes out before the
        # keepers are drilled, not when the shaft is drawn.
        "rear-keeper-leaf-removed": "REMOVE THE FEELER LEAF.",
        "keeper-feet-transferred": (
            f"TRANSFER-DRILL EACH {keeper} FOOT HOLE INTO THE RAIL."
        ),
        "keeper-feet-tapped": f"TAP THOSE HOLES TO THE {top_frame} DRAWING.",
        steps.KEEPERS_SCREWED_KEY: (
            f"SCREW EACH {keeper} DOWN WITH ONE {foot_screw}."
        ),
        "keepers-unclamped": "REMOVE THE CLAMPS.",
        "keepers-held": f"CHECK EACH {keeper} DOES NOT TURN BY HAND.",
        # #2338: each keeper is drilled letter F alone to its print (owner
        # ruling 2026-11-24, fit audit Q1); the bore's band
        # covers both bore heights and the rail seats, so the shaft slides
        # with both screwed down (ch_fulcrum_shaft_spec ALIGNED_MIN_CLEARANCE_MM).
        "keeper-bores-checked": (
            f"CHECK {fulcrum_shaft} SLIDES FREELY THROUGH BOTH {keeper} BORES."
        ),
        # The levers ride the shaft between the screwed keepers, so each
        # comes off as the shaft leaves its hub (#3571): they go to the bench
        # for their bars with the shaft out.
        "fulcrum-shaft-withdrawn": (
            f"DRAW {fulcrum_shaft} OUT OF BOTH {keeper} TO THE LEFT ({lever_view}), "
            f"CATCHING EACH {lever} LEVER AS IT COMES OFF."
        ),
        "bars-straight": (
            f"LAY EACH {bar} BAR ON THE SURFACE PLATE ON EACH SIDE FACE IN TURN: "
            f"THE FEELER LEAF OF {notes.setting_row('bars-straight')} MUST NOT ENTER "
            "UNDER IT."
        ),
        "bar-straightened": (
            f"STRAIGHTEN BY HAND, OR EXCHANGE, ANY {bar} BAR THE LEAF ENTERED."
        ),
        "bar-straightened-return": (
            f"RETURN TO STEP {n('bars-straight')} WITH EACH {bar} BAR "
            "STRAIGHTENED OR EXCHANGED."
        ),
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
        "bar-pin-bonded": (
            f"IF AN {bar_pin} SLID IN BY HAND, BOND IT PER THE PIN BOND NOTE "
            f"(SHEET {SHEET_NAMES.index(DETAIL_SHEET) + 1})."
        ),
        "bar-pin-bond-held": (
            f"BONDED PIN: CURED, CHECK {bar_pin} DOES NOT SLIDE BY HAND."
        ),
        "bar-pin-bond-swings": (
            f"BONDED PIN: CHECK {bar} SWINGS FREE ON ITS PIN UNDER ITS OWN WEIGHT."
        ),
        "bar-pin-pushed-out": (
            f"BONDED PIN: IF {bar_pin} SLIDES OR {bar} BINDS, PUSH THAT PIN OUT, "
            "HEATING THE CHEEKS."
        ),
        "bar-replaced": f"BONDED PIN: REPLACE THAT {bar} BAR.",
        "bar-pin-return": (
            f"BONDED PIN: RETURN TO STEP {n('bars-straight')} WITH THE NEW {bar} BAR."
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
        "bars-gapped": (
            f"CHECK THE FEELER LEAF OF {notes.setting_row('bars-gapped')} PASSES "
            f"BETWEEN EVERY ADJACENT PAIR OF {bar} BARS, TOP TO BOTTOM."
        ),
        "levers-swing": f"CHECK EVERY {lever} SWINGS FREE ON {fulcrum_shaft}.",
        "lever-bank-slides": (
            f"CHECK THE LEVERS SLIDE TOGETHER ALONG {fulcrum_shaft}: PUSHED "
            f"AGAINST ONE {keeper} LUG, THEY LEAVE ROOM FOR THE FEELER LEAF OF "
            f"{notes.setting_row('lever-bank-slides')} AT THE OTHER."
        ),
        "fulcrum-flats-aligned": (
            f"SLIDE {fulcrum_shaft} UNTIL EACH OF ITS FLATS LIES UP, UNDER THE "
            f"{fulcrum_set_screw} TAP OF ITS {keeper}."
        ),
        steps.FULCRUM_SET_SCREWS_DRIVEN_KEY: (
            f"TIGHTEN ONE {fulcrum_set_screw} SET SCREW ONTO EACH FLAT."
        ),
        # Unstaked, as the pivot shaft's (#2397; threaded-joint-retention.md
        # U-MHA-CH-VN-55-no-lock).
        "fulcrum-shaft-held": f"CHECK {fulcrum_shaft} DOES NOT TURN OR SLIDE BY HAND.",
        steps.SPRINGS_HOOKED_KEY: (
            f"HOOK THE TOP LOOP OF EACH {channel_spring} SPRING THROUGH THE "
            f"SPRING HOLE OF ITS {lever} ({hookup_view})."
        ),
        # The anchors thread into the summing plate at MHA-HA-00, which owns
        # that joint and its setting (cited by its step, which the release's
        # ASSEMBLY.md prints, #2889).
        "spring-bottom-loops-left": (
            f"LEAVE EACH BOTTOM LOOP FREE: {steps.HA_ANCHORS_SET_REF} (ASSEMBLY.MD) "
            f"THREADS EACH {anchor} ANCHOR AND HOOKS THE LOOP INTO IT."
        ),
    }


FITUP_TEXT = _fitup_text()
if tuple(FITUP_TEXT) != steps.SEQUENCE:
    raise AssertionError("the step text must follow ch_channel_assembly_steps.SEQUENCE")
FITUP_NOTES = flow_steps(
    "ROCKER BANK FIT-UP",
    steps.ROCKER_SEQUENCE,
    FITUP_TEXT,
    ROCKER_COLUMNS,
    ROCKER_BLOCKS,
) + flow_steps("LEVER BANK FIT-UP", steps.LEVER_SEQUENCE, FITUP_TEXT, LEVER_COLUMNS)
FITUP_STEPS = "\n".join(text for _column, text in FITUP_NOTES)


def _pin_bond_note() -> str:
    """The pin bond the rod-pin-bonded and bar-pin-bonded steps point to.

    Owner ruling 2026-11-24, fit audit question 3: a pivot pin that enters
    its reamed fork or bar hole by hand is bonded with LOCTITE 641 instead of
    its rod or bar being replaced. Rule 23 (and part 1's second pass on the
    audit): degrease, the compound kept off the running joint beside it, the
    pin held square while it cures, and the cure before load. The pin runs in
    the arm or lever between the two tines or cheeks, .002-.0075 off each
    face, so only the trailing end is coated, no further in than half the
    tine or cheek it stops in: the hole's mouth scrapes the excess outboard,
    and nothing coated ever passes the arm or lever. The far hole holds the
    pin square, and the cure lies coated end down so nothing runs inward. A
    pin bonded in 641 (the removable grade) comes out with heat. As a note,
    the bond stays one action of its step (the MHA-PD-00 bond note's form).
    """
    pin, bar_pin = item(explode.ROD_PIN), item(explode.BAR_PIN)
    arm, lever = item("ch-rocker-arm"), item("ch-channel-lever")
    lines = (
        f"PIN BOND (STEPS {steps.step_number('rod-pin-bonded')} AND "
        f"{steps.step_number('bar-pin-bonded')}): AN {pin} OR {bar_pin} THAT "
        "SLID IN BY HAND.",
        "1. PUSH IT OUT, HEATING THE TINES OR CHEEKS IF IT WAS BONDED.",
        "2. DEGREASE THE PIN AND BOTH HOLES IT SLID IN.",
        "3. COAT ONE END WITH LOCTITE 641, NO FURTHER IN THAN HALF THE "
        "TINE OR CHEEK IT STOPS IN; NONE ON THE MIDDLE.",
        "4. AT ONCE PUSH IT BACK, COATED END LAST, FLUSH WITH BOTH FACES: "
        f"THE COMPOUND STAYS OFF THE {arm} OR {lever} BETWEEN THEM.",
        "5. WIPE THAT FACE.",
        "6. CURE 24 H, COATED END DOWN, THE FAR HOLE HOLDING THE PIN SQUARE.",
    )
    wrapped: list[str] = []
    for line in lines:
        wrapped += textwrap.wrap(
            _REFERENCE_SPACE.sub(rf"\1{_UNBROKEN_SPACE}", line),
            width=STEPS_LINE_WIDTH,
            subsequent_indent="   ",
            break_on_hyphens=False,
        )
    return "\n".join(line.replace(_UNBROKEN_SPACE, " ") for line in wrapped)


# The note stands at the top of the detail sheet's right half, over detail
# A's hub label (its text top 0.033 above the detail's centre), which it
# clears by at least a line.
PIN_BOND_NOTE = _pin_bond_note()
PIN_BOND_NOTE_XY = (STEPS_RIGHT_X, STEPS_TOP_Y)
_PIN_BOND_NOTE_FOOT = (
    PIN_BOND_NOTE_XY[1] - len(PIN_BOND_NOTE.splitlines()) * NOTE_LINE_PITCH
)
if _PIN_BOND_NOTE_FOOT < SOUTH_END.centre[1] + 0.033 + NOTE_LINE_PITCH:
    raise AssertionError("the pin bond note runs into detail A's hub label")
if (
    PIN_BOND_NOTE_XY[0] + STEPS_LINE_WIDTH * NOTE_CHAR_WIDTH
    > _TEMPLATE.width_m - BORDER
):
    raise AssertionError("the pin bond note runs past the right border")


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


def _component_family(component: Any) -> str:
    """The BOM row a component counts toward: its file stem, or each pivot pin
    member's ``stem--member`` key."""
    return explode.member_family(*component_identity(component))


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
    for name, component in by_name(assembly.GetComponents(True)):
        stem = _component_family(component)
        counts[stem] += 1
        total = _early_bound(component.GetTotalTransform(True), "IMathTransform")
        base = _early_bound(component.GetTotalTransform(False), "IMathTransform")
        values = tuple(float(value) for value in base.ArrayData)
        if any(
            abs(float(actual) - expected) > 1e-9
            for actual, expected in zip(total.ArrayData, values, strict=True)
        ):
            raise RuntimeError(
                f"channel source must open collapsed: {name!r} is displaced"
            )
        z = values[11]
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


def _validate_bom(
    adapter: Any, table: Any, configuration: str
) -> tuple[tuple[str, str], ...]:
    """Prove associative Numbers, native identities, descriptions, quantities and
    the item numbers the steps cite; add the registry's VENDOR SKU column after
    DESCRIPTION and return (row key, item number) in BOM order. Material and
    finish remain on component drawings."""
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
    identities = bom_row_identities(
        table,
        configuration=configuration,
        component_identities=BOM_COMPONENT_IDENTITIES,
    )
    for stem, row_index in identities.items():
        row = contents[row_index]
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
            raise RuntimeError(
                f"channel BOM Number for {stem!r} is "
                f"{contents[row_index][part_column]!r}, expected {number!r}"
            )
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
    before_rebuild = validate_bom_number_property(
        table,
        configuration=configuration,
        label="channel",
        expected_rows=rows,
        occurrence_quantities=True,
    )
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
    if (
        validate_bom_number_property(
            table,
            configuration=configuration,
            label="channel",
            expected_rows=rows,
            occurrence_quantities=True,
        )
        != before_rebuild
    ):
        raise RuntimeError(
            "channel native BOM membership/quantities changed during rebuild"
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
        component_identities=BOM_COMPONENT_IDENTITIES,
        part_number_property="Number",
        configuration_grouping="same-name",
        label="channel",
    )
    items = _validate_bom(adapter, table, configuration)
    bom_snapshot = validate_bom_number_property(
        table,
        configuration=configuration,
        label="channel",
        expected_rows=1 + len(BOM_COMPONENTS),
        occurrence_quantities=True,
    )
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
        retained = validate_bom_number_property(
            table,
            configuration=configuration,
            label="channel",
            expected_rows=1 + len(BOM_COMPONENTS),
            occurrence_quantities=True,
        )
        if retained != bom_snapshot:
            raise RuntimeError(
                "channel native BOM membership/quantities changed after placement"
            )
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
    point = letter_xy(centre, radius, detail.letter_corner, detail.letter_offset)
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
    lies off the sheet) when it keeps any of its dimensions, import ``keep``,
    crop it if it is a detail, prove the kept dimensions survived, and label
    it. ``detail``, a detail taken from ``bank``, gets its boundary circle and
    letter drawn in ``bank``; each of ``pointers`` (text, text point, tip)
    names a body with a view-owned leader."""
    view = _placed_bank_view(adapter, bank)
    features = tuple(dict.fromkeys(asm.DIMENSION_FEATURE[name] for name in keep))
    if features:
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
    label_foot = y0 - len(bank.label_text.splitlines()) * NOTE_LINE_PITCH
    if bank == ROCKER_BANK and label_foot < ROCKER_UNDER_VIEW_TOP + NOTE_LINE_PITCH:
        raise RuntimeError(
            f"{bank.title}'s caption ends at y {label_foot:.4f}, into the step "
            f"column under it (top {ROCKER_UNDER_VIEW_TOP})"
        )
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
        if text != DIMENSION_CALLOUTS[name]:
            raise RuntimeError(f"{name}: callout reads {text!r}")
        below = str(display.GetText(CALLOUT_BELOW_PART) or "").replace("\r\n", "\n")
        if below != DIMENSION_BELOW_CALLOUTS.get(name, ""):
            raise RuntimeError(f"{name}: below-callout reads {below!r}")


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
    annotations = _dimensioned_bank(adapter, ROCKER_BANK, ROCKER_KEEP, detail=SOUTH_END)
    _place_steps(adapter, SHEET_NAMES[2])

    _activate_sheet(adapter, DETAIL_SHEET)
    annotations += _dimensioned_bank(
        adapter, SOUTH_END, {}, pointers=DETAIL_POINTERS
    )
    _place_steps(adapter, DETAIL_SHEET)
    _add_note_block(
        adapter, DETAIL_SHEET, PIN_BOND_NOTE, PIN_BOND_NOTE_XY, label="pin bond note"
    )

    _activate_sheet(adapter, SHEET_NAMES[4])
    annotations += _dimensioned_bank(adapter, LEVER_BANK, LUG_KEEP)
    annotations += _dimensioned_bank(
        adapter, KEEPER_PLAN, PLAN_KEEP, pointers=PLAN_POINTERS
    )
    _place_steps(adapter, SHEET_NAMES[4])

    for name, text in DIMENSION_CALLOUTS.items():
        set_dimension_callouts(adapter, annotations, {name: text}, location="above")
    set_dimension_callouts(
        adapter, annotations, DIMENSION_BELOW_CALLOUTS, location="below"
    )
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
    """Sheet 6: view G, the spring hook-up, the rest of the lever-bank steps
    and the setting table under view G's label."""
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
    label_foot = label_xy[1] - len(HOOKUP.label_text.splitlines()) * NOTE_LINE_PITCH
    if SETTING_TABLE_XY[1] > label_foot - 0.002:
        raise RuntimeError(
            f"the setting table's title ({SETTING_TABLE_XY!r}) runs into the "
            f"{HOOKUP.title} label (foot {label_foot:.4f})"
        )
    _activate_sheet(adapter, SETTING_TABLE_SHEET)
    box = insert_general_table(
        adapter,
        title=notes.SETTING_TABLE_TITLE,
        header=notes.SETTING_TABLE_HEADER,
        rows=SETTING_TABLE_ROWS,
        top_left=SETTING_TABLE_XY,
        label="setting table",
    )
    if (
        box[0] < left_column_right
        or box[2] > _TEMPLATE.width_m - BORDER - 0.003
        or box[1] < _TEMPLATE.title_block_top_m + 0.003
    ):
        raise RuntimeError(f"the setting table {box!r} leaves its field on sheet 6")


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
def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source assembly is missing: {SOURCE}")

    check("open assembly drawing source", adapter.open_model(str(SOURCE)))
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

    return finalize_drawing(
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
