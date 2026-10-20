r"""Create the four-sheet magnifier fitter package (MHA-MG-00).

Sheet 1, ASSEMBLED + SETTINGS: the preserved back, left and back-top-left
views at 1:4, and every assembly setting printed as the assembly's own model
dimension (mg_magnifier_assembly_spec). The back view prints the lever group's two
operator settings, the clamp station and the fixture drop. Two cropped
side-view details of the wheel axle print one stack setting each:
- AXLE AS PRESSED (2:1) shows only the bar and the axle. It prints the press
  gauge from the bar's front face to the shank step. The wheel hub hides the
  step once it is fitted.
- WHEEL ENDSHAKE (4:1) shows the stack. It prints the endshake between the
  wheel's spigot face and the front washer.

Each detail is a cropped MG LEFT model view, dimensioned while uncropped and
cropped after. On a native detail, the targeted import delivered nothing
(the ch-amplitude-bar finding). The dimensions belong to construction chains
the assembly saves blanked. Each view shows its chain in that view only
before importing (the ms-measuring-stick ClampedSetting pattern).

Sheet 2, WHEEL GROUP + BOM: the builder-owned MG_MAGNIFIER_EXPLODED
presentation (mg_magnifier_explode_spec) with only the wheel group shown, the
BOM (part number, description, vendor SKU, quantity) and one balloon per
family. Sheet 3, LEVER GROUP: the same explode with only the lever group
shown, ballooned from the same BOM. Sheet 4, ASSEMBLY STEPS: the finished
assembly with the lever wire ballooned, beside the numbered sequence
(mg_magnifier_assembly_steps) and the checks. The instruction column uses
the left 190 mm; the finished view is centred in the remaining right field.
Step text names the settings and never values them. This recipe never edits
the source assembly or its explodes.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import dataclass
import math
from pathlib import Path
import sys
import textwrap
from typing import Any, Callable, Iterator

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    dimension_name,
    place_view,
    view_name,
)

import _config
import _telemetry
import mg_magnifier_assembly_sheet as notes
import mg_magnifier_assembly_spec as stack
import mg_magnifier_explode_spec as explode
import mg_vn_lever_wire_geom
import mg_vn_lever_wire_spec
import mg_vn_wheel_axle_front_washer_spec as front_washer
import mg_vn_wheel_axle_nut_spec as axle_nut
from _check import check
from _com import _early_bound
from _drawing_balloon_display import rendered_balloon_circle
from _drawing_balloons import (
    BalloonAnchor,
    BalloonLanding,
    add_component_bom_balloons,
    assert_balloon_landings,
    isolate_drawing_view_components,
)
from _drawing_centerline import add_view_centerline
from _drawing_common import (
    _SW_SHADED_EDGES,
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    set_high_quality_shaded_with_edges,
)
from _drawing_dimension_import import curate_view_dimensions
from _drawing_dimensions import assert_imported_precision, set_dimension_callouts
from _drawing_hidden_sketches import _show_base_view_sketches
from _drawing_projection import model_point_in_view, model_points_in_view
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME, DrawingLayout
from _drawing_sheets import create_blank_drawing_sheets
from _drawing_tables import insert_bom_table
from _drawing_view_configuration import (
    ASSEMBLY_VIEW_CONFIGURATION,
    SIMPLIFIED_VIEW_CONFIGURATION,
    ViewRole,
    view_configuration,
    apply_view_configuration,
    assert_full_detail_view,
    set_view_exploded_state,
)
from _drawing_view_display import set_hidden_lines_removed
from _machinist_review_mode import MachinistReviewMode
from _session import run_build
from mg_lever_press_fit_geom import ROD_DIA as LEVER_ROD_DIA
from mg_magnifying_vertical_rod_geom import ROD_DIA as VROD_DIA
from mg_magnifying_vertical_rod_geom import SHOULDER_X as VROD_SHOULDER_X
from mg_wheel_axle_spec import TIP_Y
from mg_wheel_bar_geom import BORE_ROW_HEIGHT


# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE
SPEC = DRAWINGS_BY_NAME["mg_magnifier_assembly"]
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
PDF_TITLE = "Magnifier Assembly Drawing Package"

SHEET_NAMES = (
    "ASSEMBLED + SETTINGS",
    "WHEEL GROUP + BOM",
    "LEVER GROUP",
    "ASSEMBLY STEPS",
)
if SPEC.layout is not DrawingLayout.LANDSCAPE:
    raise AssertionError("the magnifier sheet coordinates are landscape")
SHEET_LAYOUTS = {name: DrawingLayout.LANDSCAPE for name in SHEET_NAMES}
SHEET_SCALE = (1.0, 4.0)
# Both exploded sheets at 1:2: small enough to print the simplified
# configuration (no thread ink), large enough to read every washer and nut.
# Each exploded view takes the largest ladder scale whose balloon ring fits
# its field; every rung keeps the simplified configuration.
EXPLODED_SCALE_LADDER = ((1.0, 2.0), (1.0, 3.0), (1.0, 4.0))
if any(
    view_configuration(scale, _SW_SHADED_EDGES) != SIMPLIFIED_VIEW_CONFIGURATION
    for scale in EXPLODED_SCALE_LADDER
):
    raise AssertionError("a rescale on the exploded-view ladder would switch configuration")
EXPLODED_SCALE = EXPLODED_SCALE_LADDER[0]
SHEET_SCALES = {
    SHEET_NAMES[0]: SHEET_SCALE,
    SHEET_NAMES[1]: EXPLODED_SCALE,
    SHEET_NAMES[2]: EXPLODED_SCALE,
    SHEET_NAMES[3]: SHEET_SCALE,
}
FRONT_CENTER = (0.070, 0.150)
# Right sits 18 mm further right than r5's 0.150 so the fixture drop's
# text block (left-justified at FIXTURE_DROP_RUN, ~42 mm wide) clears it:
# r5's audit had "60.0" printing 4.0 mm over Drawing View2.
RIGHT_CENTER = (0.168, 0.150)
ISO_CENTER = (0.225, 0.140)
# Machinist review r3 (run 20261016T120248930Z-2fa1ae0c1aaa4f1ea2370a197868591c):
# the unlabelled principal view shows the bar in front of the wheel, while
# step 11 leads the wire "seen from the front". The preserved MG BACK looks
# from the bar side, +z (mg_magnifying_wheel_geom: the pen-side front view
# mirrors local x), and MG LEFT from +x, the fitter's left as he faces the
# machine front: the drum, at machine -z, prints on its right. Each caption is centred
# under its view (caption_under); the side view's stays short so it ends left
# of the isometric (r8's outlines: Right 153-183 mm, Isometric from 194 mm).
ASSEMBLED_VIEW_CAPTIONS = {
    stack.DRAWING_BACK_VIEW: "VIEW FROM THE BACK",
    stack.DRAWING_LEFT_VIEW: "VIEW FROM THE LEFT",
}

# Sheet geometry, metres: the template's inner border and the title block in
# its lower-right corner. Every view ring and note stays inside the border and
# out of the title block (drawing-guidelines.md rule 13).
_TEMPLATE = DRAWING_TEMPLATES[DrawingLayout.LANDSCAPE]
_BORDER = 0.0127
INNER_BORDER = (_BORDER, _BORDER, _TEMPLATE.width_m - _BORDER, _TEMPLATE.height_m - _BORDER)
TITLE_BLOCK = (
    _TEMPLATE.title_block_left_m,
    0.0,
    _TEMPLATE.width_m,
    _TEMPLATE.title_block_top_m,
)
_PAD = 0.004

# Sheet 1, back view: the lever settings' text, in sheet metres from the
# projected chain points. The clamp station's line runs above the clamp's
# thumb-screw head with its callout above it. The fixture drop's text stands
# right of the vertical rod, clear of the fixture screw (toward the bracket,
# left) and the wire (down-left to the wheel), and BELOW the fixture axis's
# extension line: placed between the two extension lines (r3), its 3-line
# block reached down through the lower one and its left end over the rod
# (machinist review r1).
CLAMP_STATION_RISE = 0.012
FIXTURE_DROP_RUN = 0.018
FIXTURE_DROP_BELOW = 0.006
LEVER_CALLOUT_LOCATION = {
    stack.CLAMP_STATION_DIMENSION: "above",
    stack.FIXTURE_DROP_DIMENSION: "below",
}
LEVER_VIEW_LABEL = "lever settings (back)"

# Sheet 2: the wheel group's exploded view in the field left of the BOM with
# its caption under it (as the lever sheet's), the BOM in the top-right
# corner, and under the BOM the collapsed whole-assembly view the BOM is
# inserted on (the MHA-PD-00 BOM reference): the exploded views are isolated
# afterwards, and view-only isolation must never touch the view that owns the
# parts list. The reference is HIDDEN once the package is laid out: machinist
# review r2 (run 20261016T105658863Z-132a077b63f840489c527e3ef02d296d) found
# the whole assembly unreadable at the 1:16 its field allows, and a repeat of
# sheet 4's 1:4 finished view, so it only carries the parts list.
BALLOON_MARGIN = 0.012
BALLOON_RING_REACH = BALLOON_MARGIN + 0.005
# Wide enough that no description wraps: r3 (run
# 20261016T072448223Z-614c0a10f732427c87668fb67f9db447) wrapped the 0.072
# column's "#4-40 X 7/16 KNURLED THUMB SCREW" to two lines, pushing the BOM's
# last row onto the reference caption.
# Reserve a separate 48 mm column for full parent-scoped MHA-MG-VN-xx
# Numbers. The old 32 mm allocation predates those longer IDs; widening it
# uses the spare gap to the wheel field, not smaller text or description space.
BOM_COLUMN_WIDTHS = {
    "item": 0.012,
    "part": 0.048,
    "description": 0.082,
    "sku": 0.032,
    "quantity": 0.012,
}
BOM_SKU_TITLE = "VENDOR SKU"
MADE_PART_SKU = "-"
BOM_ROW_HEIGHT = 0.006
BOM_ANCHOR = (
    INNER_BORDER[2] - _PAD - sum(BOM_COLUMN_WIDTHS.values()),
    INNER_BORDER[3] - _PAD,
)
WHEEL_FIELD = (
    INNER_BORDER[0] + _PAD,
    TITLE_BLOCK[3] + _PAD,
    TITLE_BLOCK[0] - _PAD,
    INNER_BORDER[3] - _PAD,
)
if WHEEL_FIELD[2] + _PAD > BOM_ANCHOR[0]:
    raise AssertionError("the wheel group's field runs under the BOM")
WHEEL_CAPTION_XY = (INNER_BORDER[0] + _PAD + 0.002, TITLE_BLOCK[3] - _PAD)
WHEEL_GROUP = "WHEEL GROUP"
WHEEL_LABEL = "wheel group exploded"
# The heading's two-line titles ("ITEM NO.", "PART NUMBER") print 14.3 mm
# tall (r4's read-back: 128.3 mm for 19 rows of 6.0), so the plan books three
# rows; the reference view still fits its field at 1:16 (44.3 mm tall on r3).
BOM_HEADING_ROWS = 3
BOM_BOTTOM = BOM_ANCHOR[1] - (len(notes.BOM_ORDER) + BOM_HEADING_ROWS) * BOM_ROW_HEIGHT
BOM_REFERENCE_FIELD = (
    BOM_ANCHOR[0],
    TITLE_BLOCK[3] + _PAD,
    INNER_BORDER[2] - _PAD,
    BOM_BOTTOM - _PAD - 0.006,
)
BOM_REFERENCE_SCALE_LADDER = ((1.0, 8.0), (1.0, 10.0), (1.0, 12.0), (1.0, 16.0))
BOM_REFERENCE_LABEL = "BOM reference"
# Sheet 3: the lever group's exploded view over the full width above the
# title block, its caption centred under it (lever_caption_xy).
# Machinist review r6 (run 20261016T150215480Z) found the group too small at
# 1:3; r7 (run 20261016T162927333Z) took 1:2 left of the title block as
# unbalanced, the right half empty and the caption far from the view. The
# group's outline measured 82.6 x 116.1 mm at 1:3 and 118.3 x 168.6 at 1:2
# (11.1 mm of it fixed padding), so its ring needs 202.6 mm at 1:2, more
# than the 192.7 above the title block, and 171 at 1:2.5, which fits centred
# with room for the caption under it.
LEVER_FIELD = (
    INNER_BORDER[0] + _PAD,
    TITLE_BLOCK[3] + _PAD,
    INNER_BORDER[2] - _PAD,
    INNER_BORDER[3] - _PAD,
)
LEVER_SCALE_LADDER = ((1.0, 2.5), (1.0, 3.0), (1.0, 4.0))
if any(
    view_configuration(scale, _SW_SHADED_EDGES) != SIMPLIFIED_VIEW_CONFIGURATION
    for scale in LEVER_SCALE_LADDER
):
    raise AssertionError("a rescale on the lever ladder would switch configuration")
LEVER_GROUP = "LEVER GROUP"
LEVER_LABEL = "lever group exploded"
# Sheet 4: the sequence and checks down a 190 mm left column, the finished
# assembly centred in the remaining field above the title block, its caption
# centred over it. The wider column keeps full parent-scoped vendor Numbers
# intact without reducing the default text size or its line pitch.
# The lever wire's balloon stands right of the view (FINISHED_WIRE_BALLOON_*).
STEPS_XY = (0.018, 0.258)
STEPS_LINE_WIDTH = 80  # characters; default-format note text (as MHA-MS-00)
# Default-format note line pitch (the MHA-PD-00 stake note measured 0.0045).
NOTE_LINE_PITCH = 0.0046
# Machinist review r2: the caption at the field's left corner sat ~40 mm left
# of the view it names, so it is centred over the view's outline once the view
# has settled. Its width is the character count at the r6 PDF's measured
# pitch ("FINISHED ASSEMBLY (SCALE 1:4)": 29 characters, 68.8 mm).
CAPTION_CHAR_WIDTH = 0.00237
STEPS_RIGHT = STEPS_XY[0] + STEPS_LINE_WIDTH * CAPTION_CHAR_WIDTH
CAPTION_GAP = 0.004
FINISHED_FIELD = (
    STEPS_RIGHT + _PAD,
    TITLE_BLOCK[3] + _PAD,
    INNER_BORDER[2] - _PAD,
    INNER_BORDER[3] - _PAD - 0.008,
)
FINISHED_CENTER = (
    (FINISHED_FIELD[0] + FINISHED_FIELD[2]) / 2.0,
    (FINISHED_FIELD[1] + FINISHED_FIELD[3]) / 2.0,
)
# 1:4 prints the simplified configuration like every rung below it.
FINISHED_SCALE_LADDER = (SHEET_SCALE, (1.0, 5.0), (1.0, 6.0))
FINISHED_LABEL = "finished assembly"
FINISHED_CAPTION = "FINISHED ASSEMBLY"
# Machinist review r4 (run 20261016T123712799Z-1710842d83c44076818f6a515121cce5):
# the wire's only model edges were its two end circles, so balloon 19 landed
# on the drum end inside the wheel and read as pointing at a spoke. MHA-MG-VN-56
# now carries a shape-neutral split ring at BALLOON_RING_FRACTION of its run
# (build_mg_vn_lever_wire.BalloonRingSplit), and the balloon is frozen to the
# ring's point facing the preserved fitter isometric viewer (wire_facing_point). The balloon
# then stands right of the view, its leader dropping this little from the
# ring so it passes under the vertical rod's lower end, the one part right of
# the run.
FINISHED_WIRE_BALLOON_RISE_DEG = -10.0
ISOMETRIC_VIEWER = (1.0, 1.0, 1.0)  # ISO MG BACK-TOP-LEFT looks from +X+Y+Z


def wire_facing_point(
    hook: tuple[float, float, float],
    drum: tuple[float, float, float],
    *,
    radius: float,
    station: float,
) -> tuple[float, float, float]:
    """Part-frame point (mm) on the wire's ring at ``station`` that faces the
    preserved ISO MG BACK-TOP-LEFT viewer.

    The frame is ``build_mg_magnifier_assembly._lever_wire_rows``': part +Y
    onto drum->hook, +X the horizontal perpendicular (d_y, -d_x, 0), +Z = X x Y.
    The viewer direction, projected square to the axis, gives the ring point.
    """
    delta = [h - d for h, d in zip(hook, drum, strict=True)]
    length = math.hypot(*delta)
    axis = [v / length for v in delta]
    horizontal = math.hypot(axis[0], axis[1])
    x = (axis[1] / horizontal, -axis[0] / horizontal, 0.0)
    z = (
        x[1] * axis[2] - x[2] * axis[1],
        x[2] * axis[0] - x[0] * axis[2],
        x[0] * axis[1] - x[1] * axis[0],
    )
    along_x = sum(a * b for a, b in zip(ISOMETRIC_VIEWER, x))
    along_z = sum(a * b for a, b in zip(ISOMETRIC_VIEWER, z))
    scale = radius / math.hypot(along_x, along_z)
    return along_x * scale, station, along_z * scale


WIRE_BALLOON_POINT_MM = wire_facing_point(
    mg_vn_lever_wire_geom.WIRE_START,
    mg_vn_lever_wire_geom.WIRE_END,
    radius=mg_vn_lever_wire_geom.WIRE_DIA / 2.0,
    station=mg_vn_lever_wire_spec.BALLOON_RING_FRACTION * mg_vn_lever_wire_geom.WIRE_LEN,
)

BOM_QUANTITIES = {stem: notes.QUANTITIES[stem] for stem in notes.BOM_ORDER}
BOM_COMPONENTS = tuple(BOM_QUANTITIES)
# Literal stems, so the config-dependency analysis reads exactly these rows.
PART_ROWS = {
    "mg-wheel-axle": _config.parts("mg-wheel-axle"),
    "mg-wheel-bar": _config.parts("mg-wheel-bar"),
    "sh-column-clamp-front": _config.parts("sh-column-clamp-front"),
    "sh-column-clamp-back": _config.parts("sh-column-clamp-back"),
    "mg-vn-clamp-screw": _config.parts("mg-vn-clamp-screw"),
    "mg-wheel-drum": _config.parts("mg-wheel-drum"),
    "mg-magnifying-wheel": _config.parts("mg-magnifying-wheel"),
    "mg-wheel-axle-spacer": _config.parts("mg-wheel-axle-spacer"),
    "mg-vn-wheel-axle-back-washer": _config.parts("mg-vn-wheel-axle-back-washer"),
    "mg-vn-wheel-axle-front-washer": _config.parts("mg-vn-wheel-axle-front-washer"),
    "mg-vn-wheel-axle-nut": _config.parts("mg-vn-wheel-axle-nut"),
    "mg-magnifying-lever": _config.parts("mg-magnifying-lever"),
    "mg-magnifying-bracket": _config.parts("mg-magnifying-bracket"),
    "mg-vn-magnifying-bracket-screw": _config.parts("mg-vn-magnifying-bracket-screw"),
    "mg-magnifying-clamp": _config.parts("mg-magnifying-clamp"),
    "mg-vn-thumb-screw": _config.parts("mg-vn-thumb-screw"),
    "mg-magnifying-vertical-rod": _config.parts("mg-magnifying-vertical-rod"),
    "mg-output-fixture": _config.parts("mg-output-fixture"),
    "mg-vn-lever-wire": _config.parts("mg-vn-lever-wire"),
}
if set(PART_ROWS) != set(BOM_COMPONENTS):
    raise AssertionError("BOM registry rows must cover exactly the assembly families")
if set(BOM_COMPONENTS) != explode.SHOWN_STEMS:
    raise AssertionError("every BOM family must show on one of the package's views")
BOM_PART_NUMBERS = {stem: str(row["number"]) for stem, row in PART_ROWS.items()}
# The registry owns part numbers and vendor SKU; components own material/finish.
BOM_SKUS = {
    stem: " / ".join(str(sku) for sku in row.get("supplier_skus") or ()) or MADE_PART_SKU
    for stem, row in PART_ROWS.items()
}
BOM_DESCRIPTIONS = dict(notes.BOM_DESCRIPTIONS)
BOM_IDENTITY_ALIASES = {number: stem for stem, number in BOM_PART_NUMBERS.items()}
BOM_NORMALIZED_ALIASES = {
    alias.casefold(): stem for alias, stem in BOM_IDENTITY_ALIASES.items()
}
# One balloon per family (row); each walks its family's lowest-named shown
# instance for a visible edge, except the two rods.
#
# MHA-MG-03 is a revolved capsule (a hemispherical dome at each end): no
# flat face, no end circle. Its only model edges are the two dome-to-cylinder
# tangent circles at x = R from each tip, which IView's visible-entity list
# does not report (0 listed, tangent edges shown), and every body extreme
# point sits on a dome silhouette, which no EDGE hit test picks (r1/r2, runs
# 20261016T062016526Z-f9642112ccea4d2ab63c137a71a668ea and
# 20261016T065610791Z-790156178d0b4378a1fd0680e77ece6b: the lever walked 12
# extremes, no ink). MHA-MG-04's top is a #4-40 thread turned down to a
# shoulder (#1559); the shoulder's Ø5 edge is its one full-diameter hard
# circle, 45 below the clamp's bottom face once the explode drops the rod
# (the bottom dome is tangent, like the lever's). Each is
# pinned to the point of a circle that faces the fitter isometric viewer (+X+Y+Z,
# mg_magnifier_explode_spec): its part normal is the view direction
# projected square to the rod axis.
#   lever, Ry(180) in the assembly (local y = +Y, z = -Z): the west junction
#     (x = R, 50 clear of the clamp) at normal machine (0, 1, 1)/sqrt2;
#   vertical rod (local x = -Y, y = -X, z = -Z): the shoulder's outer edge
#     at x = SHOULDER_X, at normal machine (1, 0, 0), the point opposite the
#     circle's seam. Each rod is revolved from a Front (z = 0) half-profile at
#     y > 0, so its circles' seam vertex is (x, R, 0). The hit test's aperture
#     is a few hundredths of a millimetre (_drawing_scan._HIT_ZOOM_HALF) and
#     picks the drawn, tessellated circle: the rod's earlier front point
#     (normal (1, 0, 1)/sqrt2, 135 deg from the seam) hit at 1:3 but drew no
#     edge at 1:2 (r12, run 20261016T155038849Z-7389d03825f14ebd9df43bc29b661e3d),
#     as a 30 deg tessellation's chord sag at 135 deg (0.085 mm on R2.5)
#     would, sheet 0.028 at 1:3 and 0.043 at 1:2. The seam's opposite (180
#     deg) is a tessellation vertex for any even segment count, so lies on the
#     drawn edge.
_LEVER_R = LEVER_ROD_DIA / 2.0
_VROD_R = VROD_DIA / 2.0
# Machinist review r6 (run 20261016T150215480Z): on the wheel sheet the front
# washer, nut and locknut explode in a row up and right along the axle, which
# runs nearly along the rays from the view centre, so walked anchors (washer
# rim, first nut) left 17's leader through both nuts onto 18's arrowhead.
# Washer and nuts are Ry(180) in the assembly (local x = -X, y = +Y, z = -Z),
# so their local z = 0 faces the fitter isometric viewer, and a local polar angle
# phi draws at screen (-cos(phi)/sqrt2, (cos(phi) + 2 sin(phi))/sqrt6): the
# major-axis ends square to the axle's 30 deg sheet direction are phi 45
# (up-left) and 225 (down-right). 17 takes the washer rim's up-left end, so its
# leader passes above the nuts; 18 the locknut's (instance 2, the outermost)
# down-right flat, clear of everything (the nut's corners sit on its local
# +-Y meridian, so phi 225 falls on the flat facing 240, at the apothem over
# cos 15). Ring order then keeps 17 above 18.
_WASHER_R = front_washer.OD / 2.0
_NUT_FLAT_R = axle_nut.ACROSS_FLATS / 2.0 / math.cos(math.radians(15.0))
FRONT_WASHER_BALLOON_POINT_MM = (
    _WASHER_R * math.cos(math.radians(45.0)),
    _WASHER_R * math.sin(math.radians(45.0)),
    0.0,
)
LOCKNUT_BALLOON_POINT_MM = (
    _NUT_FLAT_R * math.cos(math.radians(225.0)),
    _NUT_FLAT_R * math.sin(math.radians(225.0)),
    0.0,
)
LOCKNUT_INSTANCE = "mg-vn-wheel-axle-nut-2"
BALLOON_ANCHORS = {stem: BalloonAnchor() for stem in BOM_COMPONENTS} | {
    "mg-magnifying-lever": BalloonAnchor(
        point_mm=(_LEVER_R, _LEVER_R / math.sqrt(2.0), -_LEVER_R / math.sqrt(2.0))
    ),
    "mg-magnifying-vertical-rod": BalloonAnchor(
        point_mm=(VROD_SHOULDER_X, -_VROD_R, 0.0)
    ),
    "mg-vn-wheel-axle-front-washer": BalloonAnchor(point_mm=FRONT_WASHER_BALLOON_POINT_MM),
    "mg-vn-wheel-axle-nut": BalloonAnchor(
        point_mm=LOCKNUT_BALLOON_POINT_MM, instance=LOCKNUT_INSTANCE
    ),
    explode.WIRE_STEM: BalloonAnchor(point_mm=WIRE_BALLOON_POINT_MM),
}

EXPLODED_VIEW_NAMES = {
    ASSEMBLY_VIEW_CONFIGURATION: explode.exploded_view_name(ASSEMBLY_VIEW_CONFIGURATION),
    SIMPLIFIED_VIEW_CONFIGURATION: explode.exploded_view_name(
        SIMPLIFIED_VIEW_CONFIGURATION
    ),
}
if explode.SOURCE_CONFIGURATION != ASSEMBLY_VIEW_CONFIGURATION:
    raise AssertionError("the magnifier explode is authored in Default")


def _wrapped(lines: tuple[str, ...], *, width: int, heading: str | None = None) -> str:
    """Wrap each numbered line under its own number; one note per block."""
    out = [heading] if heading else []
    for line in lines:
        number, sep, rest = line.partition(". ")
        if sep and number.isdigit():
            out += textwrap.wrap(
                rest,
                width=width,
                initial_indent=f"{number}. ",
                subsequent_indent=" " * (len(number) + 2),
                break_long_words=False,
                break_on_hyphens=False,
            )
        else:
            out += textwrap.wrap(
                line,
                width=width,
                subsequent_indent="   ",
                break_long_words=False,
                break_on_hyphens=False,
            )
    return "\n".join(out)


ASSEMBLY_STEPS = _wrapped(
    notes.ASSEMBLY_STEPS, width=STEPS_LINE_WIDTH, heading="ASSEMBLY SEQUENCE"
)
ASSEMBLY_CHECKS = _wrapped(notes.ASSEMBLY_CHECKS, width=STEPS_LINE_WIDTH)
CHECKS_XY = (
    STEPS_XY[0],
    STEPS_XY[1] - (ASSEMBLY_STEPS.count("\n") + 1) * NOTE_LINE_PITCH - 2 * _PAD,
)
if CHECKS_XY[1] - (ASSEMBLY_CHECKS.count("\n") + 1) * NOTE_LINE_PITCH < INNER_BORDER[1]:
    raise AssertionError("the assembly sequence and checks overrun the sheet")

CROP_NO_ERROR = 1  # swCropViewErrors_e.swCropViewErrors_NoError
DETAIL_POSITION_TOL_M = 1e-4
# A detail's label note: its top-left corner this far under the detail's
# lowest ink and left of the circle's centre.
LABEL_GAP = 0.004
LABEL_INSET = 0.016


@dataclass(frozen=True)
class StackDetail:
    """One cropped MG LEFT model view of the axle station.

    On this preserved view, sheet x runs with machine -z (away from the bar) and
    sheet y with machine y. ``centre_d`` is the circle's centre as a stack
    station d (from the bar front face, on the axle line); ``centre`` is where
    that point lands on the sheet. ``ink_drop_mm`` is how far below the axle
    the detail's lowest printed edge stands, in model mm; the crop circle
    itself does not print.
    """

    title: str
    scale: tuple[int, int]
    centre_d: float
    radius_mm: float
    centre: tuple[float, float]
    stems: frozenset[str]
    ink_drop_mm: float
    # The parts the detail sets, named under its title (a blind reviewer of
    # run 20261012T192552713Z could not tell what the gauge presses).
    parts: str = ""

    @property
    def mm(self) -> float:
        """Sheet metres per model millimetre."""
        return self.scale[0] / self.scale[1] / 1000.0

    def sheet_xy(self, d: float, rise: float = 0.0) -> tuple[float, float]:
        """Stack station ``d``, ``rise`` mm above the axle, on the sheet."""
        return (
            self.centre[0] + (d - self.centre_d) * self.mm,
            self.centre[1] + rise * self.mm,
        )

    @property
    def model_centre_m(self) -> tuple[float, float, float]:
        return (
            stack.AXLE_X / 1000.0,
            stack.AXLE_Y / 1000.0,
            (stack.BAR_FRONT_Z - self.centre_d) / 1000.0,
        )

    @property
    def crop_radius(self) -> float:
        return self.radius_mm * self.mm

    @property
    def label_text(self) -> str:
        lines = (self.title, self.parts, f"SCALE {self.scale[0]} : {self.scale[1]}")
        return "\n".join(line for line in lines if line)

    @property
    def label_xy(self) -> tuple[float, float]:
        return (
            self.centre[0] - LABEL_INSET,
            self.centre[1] - self.ink_drop_mm * self.mm - LABEL_GAP,
        )


# The free field right of the isometric, above the title block. The gauge
# detail spans the bar's front face to past the step; its lowest edge is the
# bar's underside, the bore row height below the axle. Its circle frames the
# gauge with this much of the bar behind the front face and of the axle past
# the step, so it grows with the spacer the gauge carries (about 38 long, the
# circle about 101 across at 2:1). The endshake detail
# spans the spigot face to the axle's tip; the hub and drum fill the circle
# up to the spigot face, so its lowest edge is the circle's chord there.
_PRESSED_MARGIN = 6.25
PRESSED = StackDetail(
    "AXLE AS PRESSED",
    (2, 1),
    stack.PRESS_GAUGE / 2.0,
    stack.PRESS_GAUGE / 2.0 + _PRESSED_MARGIN,
    (0.330, 0.200),
    frozenset({"mg-wheel-bar", "mg-wheel-axle"}),
    BORE_ROW_HEIGHT,
    # The BOM's own part numbers and descriptions (machinist review r1).
    f"{BOM_PART_NUMBERS['mg-wheel-axle']} {BOM_DESCRIPTIONS['mg-wheel-axle']} "
    f"PRESSED\nINTO {BOM_PART_NUMBERS['mg-wheel-bar']} "
    f"{BOM_DESCRIPTIONS['mg-wheel-bar']}",
)
_ENDSHAKE_CENTRE_D = (stack.HUB_FRONT_D + TIP_Y) / 2.0
_ENDSHAKE_RADIUS = 7.0
ENDSHAKE = StackDetail(
    "WHEEL ENDSHAKE",
    (4, 1),
    _ENDSHAKE_CENTRE_D,
    _ENDSHAKE_RADIUS,
    (0.330, 0.112),
    frozenset(
        {
            "mg-wheel-bar",
            "mg-wheel-axle",
            "mg-vn-wheel-axle-back-washer",
            "mg-magnifying-wheel",
            "mg-wheel-drum",
            "mg-vn-wheel-axle-front-washer",
            "mg-vn-wheel-axle-nut",
        }
    ),
    math.sqrt(_ENDSHAKE_RADIUS**2 - (_ENDSHAKE_CENTRE_D - stack.HUB_FRONT_D) ** 2),
)
# The gauge's dimension line runs above the bar, inside the circle, its
# callout above the value; the endshake's text stands right of the stack,
# above the nuts and past the crop, with its callout below.
GAUGE_RISE = 12.0
ENDSHAKE_RISE = 5.5
PRESSED_KEEP = {
    stack.PRESS_GAUGE_DIMENSION: PRESSED.sheet_xy(stack.PRESS_GAUGE / 2.0, GAUGE_RISE),
}
ENDSHAKE_KEEP = {
    stack.ENDSHAKE_DIMENSION: (
        ENDSHAKE.centre[0] + 0.055,
        ENDSHAKE.sheet_xy(stack.HUB_FRONT_D, ENDSHAKE_RISE)[1],
    ),
}
CALLOUT_LOCATION = {
    stack.PRESS_GAUGE_DIMENSION: "above",
    stack.ENDSHAKE_DIMENSION: "below",
}
# swDimensionTextParts_e: the compartment each location writes and reads.
CALLOUT_TEXT_PART = {"above": 3, "below": 4}


def _printable_callouts() -> dict[str, str]:
    """The callouts, refused if an above one holds a line break.

    SolidWorks keeps a line break in the above compartment, and GetText reads
    it back, yet prints none of that callout: the gauge's two-line callout in
    run 20261012T185729782Z, like the thumbnut's and the cone-gear shaft's
    before it. Below-callout line breaks print.
    """
    broken = sorted(
        name
        for name, location in CALLOUT_LOCATION.items()
        if location == "above" and "\n" in notes.DIMENSION_CALLOUTS[name]
    )
    if broken:
        raise RuntimeError(f"above-callouts with a line break do not print: {broken}")
    return {name: notes.DIMENSION_CALLOUTS[name] for name in CALLOUT_LOCATION}


def _assert_callouts(displays: list[tuple[str, Any]], callouts: dict[str, str]) -> None:
    """Each setting's callout reads back from its own compartment."""
    for name, display in displays:
        part = CALLOUT_TEXT_PART[CALLOUT_LOCATION[name]]
        text = str(display.GetText(part) or "")
        if text.replace("\r\n", "\n") != callouts[name]:
            raise RuntimeError(
                f"{name}: {CALLOUT_LOCATION[name]} callout reads {text!r}, "
                f"not {callouts[name]!r}"
            )


def _activate(adapter: Any, view: Any, *, label: str) -> str:
    name = view_name(adapter, view)
    if not _early_bound(adapter.currentModel, "IDrawingDoc").ActivateView(name):
        raise RuntimeError(f"failed to activate the {label} {name!r}")
    adapter.currentModel.ClearSelection2(True)
    return name


def _placed_detail(adapter: Any, detail: StackDetail) -> Any:
    """``detail`` uncropped: an MG LEFT model view at its scale, moved so its
    circle's centre lands on ``detail.centre``."""
    view = _early_bound(
        place_view(
            adapter, str(SOURCE), stack.DRAWING_LEFT_VIEW, *detail.centre, scale=detail.scale
        ),
        "IView",
    )
    label = f"{detail.title} centre"
    apply_view_configuration(adapter, view, role=ViewRole.PLAIN, label=detail.title)
    centre = model_point_in_view(adapter, view, detail.model_centre_m, label=label)
    position = tuple(float(value) for value in view.Position)
    target = [position[axis] + detail.centre[axis] - centre[axis] for axis in range(2)]
    if not view.SetViewPosition(double_array(target), False):
        raise RuntimeError(f"failed to move {detail.title} onto its spot")
    adapter.currentModel.EditRebuild3()
    centre = model_point_in_view(adapter, view, detail.model_centre_m, label=label)
    if max(abs(a - b) for a, b in zip(centre, detail.centre)) > DETAIL_POSITION_TOL_M:
        raise RuntimeError(
            f"{detail.title} centre sits at {centre!r}, not {detail.centre!r}"
        )
    set_hidden_lines_removed(adapter, view)
    isolate_drawing_view_components(
        adapter, view, visible_stems=detail.stems, label=detail.title
    )
    return view


def _crop(adapter: Any, view: Any, detail: StackDetail) -> None:
    """Crop ``view`` to the circle round ``detail.centre``: sketch the circle
    in the active view's own sketch and Crop2 while it is still selected."""
    view = _early_bound(view, "IView")
    _activate(adapter, view, label=detail.title)
    sketch = _early_bound(view.GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    points = []
    for x, y in (
        detail.centre,
        (detail.centre[0] + detail.crop_radius, detail.centre[1]),
    ):
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
        raise RuntimeError(f"failed to sketch the {detail.title} crop circle")
    status = int(view.Crop2(False, False, 1))
    adapter.currentModel.ClearSelection2(True)
    adapter.currentModel.EditRebuild3()
    view.UpdateViewDisplayGeometry()
    cropped = bool(view.IsCropped())
    _telemetry.info(
        f"magnifier: {detail.title} Crop2 status {status}, IsCropped {cropped}",
        crop_status=status,
        cropped=cropped,
    )
    if status != CROP_NO_ERROR or not cropped:
        raise RuntimeError(
            f"{detail.title} is not cropped: Crop2 status {status}, IsCropped {cropped}"
        )


def _dimensioned_detail(
    adapter: Any, detail: StackDetail, keep: dict[str, tuple[float, float]]
) -> list[Any]:
    """Place ``detail``, show the stack chain in it, import ``keep``, crop it
    and prove the kept dimensions survived the crop."""
    view = _placed_detail(adapter, detail)
    _show_base_view_sketches(adapter, view, (stack.FEATURE,), label=detail.title)
    annotations = curate_view_dimensions(
        adapter,
        view,
        keep=keep,
        view_label=detail.title,
        dimensions_by_feature=notes.DRAWING_DIMENSIONS,
    )
    _crop(adapter, view, detail)
    kept = {
        dimension_name(adapter, _early_bound(annotation, "IAnnotation"))
        for annotation in (_early_bound(view, "IView").GetAnnotations() or ())
    }
    lost = sorted(set(keep) - kept)
    if lost:
        raise RuntimeError(
            f"{detail.title} lost {lost} to its crop; kept {sorted(kept)}"
        )
    _activate(adapter, view, label=detail.title)
    if add_note(adapter, detail.label_text, *detail.label_xy) is None:
        raise RuntimeError(f"failed to label {detail.title}")
    return annotations


def _stack_dimensions(adapter: Any) -> Callable[[], None]:
    """Both settings, with their callouts, places and bands read back once
    both details are cropped; the returned check re-reads the bands and the
    callouts once the drawing has settled."""
    callouts = _printable_callouts()
    annotations = [
        *_dimensioned_detail(adapter, PRESSED, PRESSED_KEEP),
        *_dimensioned_detail(adapter, ENDSHAKE, ENDSHAKE_KEEP),
    ]
    for name, location in CALLOUT_LOCATION.items():
        set_dimension_callouts(
            adapter, annotations, {name: callouts[name]}, location=location
        )
    precision = {
        name: places
        for names in stack.DRAWING_PRECISION.values()
        for name, places in names.items()
    }
    assert_imported_precision(adapter, annotations, precision)
    displays = [
        (
            dimension_name(adapter, annotation),
            _early_bound(
                _early_bound(annotation, "IAnnotation").GetSpecificAnnotation(),
                "IDisplayDimension",
            ),
        )
        for annotation in annotations
    ]
    if sorted(name for name, _ in displays) != sorted(stack.DIMENSION_TOLERANCES):
        raise RuntimeError(f"stack details imported {sorted(n for n, _ in displays)}")
    _assert_callouts(displays, callouts)

    def settled() -> None:
        for name, display in displays:
            band_m = stack.DIMENSION_TOLERANCES[name] / 1000.0
            dimension = _early_bound(display.GetDimension2(0), "IDimension")
            tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
            if (
                int(tolerance.Type) != 4  # swTolSYMMETRIC
                or abs(float(tolerance.GetMaxValue()) - band_m) > 1e-9
                or abs(float(tolerance.GetMinValue()) + band_m) > 1e-9
                or int(display.GetPrimaryTolPrecision2()) != stack.TOLERANCE_PRECISION
            ):
                raise RuntimeError(f"{name}: settled band changed")
        _assert_callouts(displays, callouts)

    return settled


def _printable_lever_callouts() -> dict[str, str]:
    """The lever callouts, refused if an above one holds a line break (see
    :func:`_printable_callouts`)."""
    broken = sorted(
        name
        for name, location in LEVER_CALLOUT_LOCATION.items()
        if location == "above" and "\n" in notes.LEVER_CALLOUTS[name]
    )
    if broken:
        raise RuntimeError(f"above-callouts with a line break do not print: {broken}")
    return {name: notes.LEVER_CALLOUTS[name] for name in LEVER_CALLOUT_LOCATION}


def _assert_lever_callouts(
    displays: list[tuple[str, Any]], callouts: dict[str, str]
) -> None:
    for name, display in displays:
        part = CALLOUT_TEXT_PART[LEVER_CALLOUT_LOCATION[name]]
        text = str(display.GetText(part) or "")
        if text.replace("\r\n", "\n") != callouts[name]:
            raise RuntimeError(
                f"{name}: {LEVER_CALLOUT_LOCATION[name]} callout reads {text!r}, "
                f"not {callouts[name]!r}"
            )


def lever_keep(
    tip: tuple[float, float],
    clamp: tuple[float, float],
    fixture: tuple[float, float],
) -> dict[str, tuple[float, float]]:
    """Where each lever setting's text sits, from the chain's three projected
    points (sheet metres): the clamp station over the lever between the tip
    and the clamp, the fixture drop right of the rod below the fixture."""
    return {
        stack.CLAMP_STATION_DIMENSION: (
            (tip[0] + clamp[0]) / 2.0,
            max(tip[1], clamp[1]) + CLAMP_STATION_RISE,
        ),
        stack.FIXTURE_DROP_DIMENSION: (
            clamp[0] + FIXTURE_DROP_RUN,
            fixture[1] - FIXTURE_DROP_BELOW,
        ),
    }


def _lever_settings(adapter: Any, view: Any) -> Callable[[], None]:
    """The clamp station and the fixture drop on the back view, with their
    callouts; the returned check re-reads the callouts once settled."""
    callouts = _printable_lever_callouts()
    tip, clamp, fixture = model_points_in_view(
        adapter,
        view,
        (
            (stack.LEVER_TIP_X / 1000.0, stack.LEVER_AXIS_Y / 1000.0, 0.0),
            (stack.CLAMP_CENTRE_X / 1000.0, stack.LEVER_AXIS_Y / 1000.0, 0.0),
            (stack.CLAMP_CENTRE_X / 1000.0, stack.FIXTURE_AXIS_Y / 1000.0, 0.0),
        ),
        label=LEVER_VIEW_LABEL,
        names=("lever tip", "clamp centre", "fixture axis"),
    )
    _add_setting_axes(adapter, view)
    _show_base_view_sketches(adapter, view, (stack.LEVER_FEATURE,), label=LEVER_VIEW_LABEL)
    annotations = curate_view_dimensions(
        adapter,
        view,
        keep=lever_keep(tip, clamp, fixture),
        view_label=LEVER_VIEW_LABEL,
        dimensions_by_feature=stack.LEVER_DRAWING_DIMENSIONS,
    )
    for name, location in LEVER_CALLOUT_LOCATION.items():
        set_dimension_callouts(
            adapter, annotations, {name: callouts[name]}, location=location
        )
    assert_imported_precision(
        adapter,
        annotations,
        {
            name: places
            for names in stack.LEVER_DRAWING_PRECISION.values()
            for name, places in names.items()
        },
    )
    displays = [
        (
            dimension_name(adapter, annotation),
            _early_bound(
                _early_bound(annotation, "IAnnotation").GetSpecificAnnotation(),
                "IDisplayDimension",
            ),
        )
        for annotation in annotations
    ]
    if sorted(name for name, _ in displays) != sorted(LEVER_CALLOUT_LOCATION):
        raise RuntimeError(
            f"{LEVER_VIEW_LABEL} imported {sorted(n for n, _ in displays)}"
        )
    _assert_lever_callouts(displays, callouts)
    return lambda: _assert_lever_callouts(displays, callouts)


def setting_axis_picks_m() -> dict[str, tuple[float, float, float]]:
    """Model points on the lever and vertical rod's cylinders, clear of the
    clamp, the fixture and the setting chain on their axes."""
    return {
        "vertical rod": (
            stack.CLAMP_CENTRE_X / 1000.0 + 0.4 * _VROD_R / 1000.0,
            (stack.LEVER_AXIS_Y + stack.FIXTURE_AXIS_Y) / 2000.0,
            0.0,
        ),
        "lever": (
            (stack.CLAMP_CENTRE_X + stack.LEVER_TIP_X) / 2000.0,
            stack.LEVER_AXIS_Y / 1000.0 + 0.4 * _LEVER_R / 1000.0,
            0.0,
        ),
    }


def _add_setting_axes(adapter: Any, view: Any) -> None:
    """The vertical rod's and the lever's ASME centrelines on the back view.

    Machinist review r7 (run 20261016T162927333Z) read the lever setting
    chain, construction lines on these two axes in the document's long-short
    font, as hidden lines in a hidden-lines-removed view. The chain must stay
    shown or its 50.0/60.0 hide with it (_drawing_hidden_sketches, r21), and
    r14 (run 20261016T171305106Z) proved the chain-font preference prints the
    same pattern, so each part gets its own black centreline, past its ends,
    and the chain reads as the axes it lies on.
    """
    for name, point in setting_axis_picks_m().items():
        xy = model_point_in_view(adapter, view, point, label=f"{name} axis pick")
        add_view_centerline(
            adapter, view, face_xy=(xy[0], xy[1]), label=f"back view {name} axis"
        )


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
        raise RuntimeError(f"failed to place the magnifier {label}")
    note = _early_bound(note, "INote")
    printed = str(note.GetText() or "").replace("\r\n", "\n").replace("\r", "\n")
    if printed != text:
        raise RuntimeError(f"magnifier {label} printed as {printed!r}")
    return note


Box = tuple[float, float, float, float]


def _view_outline(view: Any, *, label: str) -> Box:
    outline = tuple(float(value) for value in _early_bound(view, "IView").GetOutline())
    if len(outline) != 4 or outline[2] <= outline[0] or outline[3] <= outline[1]:
        raise RuntimeError(f"{label}: invalid view outline {outline!r}")
    return outline[0], outline[1], outline[2], outline[3]


def _grown(box: Box, by: float) -> Box:
    return (box[0] - by, box[1] - by, box[2] + by, box[3] + by)


def ring_fit_shift(outline: Box, field: Box, *, name: str) -> tuple[float, float]:
    """Shift that centres a view's balloon ring (its outline grown by
    BALLOON_RING_REACH) in ``field``; raises naming each axis on which the
    ring is larger than the room. Sheet metres (left, bottom, right, top)."""
    ring = _grown(outline, BALLOON_RING_REACH)
    findings = [
        f"{name} ring {axis} {(ring[hi] - ring[lo]) * 1000:.1f} mm > room "
        f"{(field[hi] - field[lo]) * 1000:.1f} mm"
        for axis, lo, hi in (("width", 0, 2), ("height", 1, 3))
        if ring[hi] - ring[lo] > field[hi] - field[lo]
    ]
    if findings:
        raise ValueError(f"balloon ring does not fit: {'; '.join(findings)}")
    return (
        (field[0] + field[2] - ring[0] - ring[2]) / 2.0,
        (field[1] + field[3] - ring[1] - ring[3]) / 2.0,
    )


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


def scale_text(scale: tuple[float, float]) -> str:
    return f"{scale[0]:g}:{scale[1]:g}"


def step_down_to_fit(
    outline_at: Callable[[tuple[float, float]], Box],
    ladder: tuple[tuple[float, float], ...],
    field: Box,
    *,
    name: str,
) -> tuple[tuple[float, float], Box]:
    """The first ``ladder`` scale, largest first, whose ring fits ``field``.

    ``outline_at`` applies a scale to the placed view and returns the outline
    SolidWorks reads back; the outline carries a fixed sheet-space padding, so
    each candidate is applied and re-read rather than predicted. Raises naming
    every scale's overflow when the smallest still overflows.
    """
    findings = []
    for scale in ladder:
        outline = outline_at(scale)
        try:
            ring_fit_shift(outline, field, name=f"{name} at {scale_text(scale)}")
        except ValueError as error:
            findings.append(str(error))
            continue
        return scale, outline
    raise ValueError(f"no {name} scale fits: {' | '.join(findings)}")


def _fit_ring(
    adapter: Any,
    view: Any,
    ladder: tuple[tuple[float, float], ...],
    field: Box,
    *,
    label: str,
) -> tuple[float, float]:
    """Scale the view down the ladder until its balloon ring fits ``field``,
    centre the ring there and prove it inside; return the scale."""
    current = [tuple(float(value) for value in _early_bound(view, "IView").ScaleRatio)]

    def outline_at(scale: tuple[float, float]) -> Box:
        if scale != current[0]:
            _set_view_scale(adapter, view, scale, label=label)
            current[0] = scale
        return _view_outline(view, label=label)

    try:
        scale, outline = step_down_to_fit(outline_at, ladder, field, name=label)
        shift = ring_fit_shift(outline, field, name=label)
    except ValueError as error:
        raise RuntimeError(str(error)) from error
    _shift_view(adapter, view, shift, label=f"{label} ring fit")
    ring = _grown(_view_outline(view, label=label), BALLOON_RING_REACH)
    if (
        ring[0] < field[0] - 1e-6
        or ring[1] < field[1] - 1e-6
        or ring[2] > field[2] + 1e-6
        or ring[3] > field[3] + 1e-6
    ):
        raise RuntimeError(f"{label}: balloon ring {ring!r} leaves its field {field!r}")
    return scale


def exploded_caption(group: str, scale: tuple[float, float]) -> str:
    return f"{group} {notes.EXPLODED_CAPTION} (SCALE {scale_text(scale)})"


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
        raise RuntimeError("magnifier source must open in its Default configuration")
    for owner, wanted in EXPLODED_VIEW_NAMES.items():
        names = tuple(assembly.GetExplodedViewNames2(owner) or ())
        if names != (wanted,):
            raise RuntimeError(
                f"magnifier {owner} exploded views {names!r} != {(wanted,)!r}"
            )
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
                f"magnifier source must open collapsed: {component.Name2!r} "
                "is displaced"
            )
    if counts != BOM_QUANTITIES:
        raise RuntimeError(
            f"magnifier families {counts!r} != contract {BOM_QUANTITIES!r}"
        )


def _create_sheets(adapter: Any) -> None:
    new_project_drawing(adapter, layout=SPEC.layout, scale=SHEET_SCALE)
    create_blank_drawing_sheets(adapter, SHEET_NAMES, label="magnifier package")
    for name in SHEET_NAMES:
        sheet = _activate_sheet(adapter, name)
        numerator, denominator = SHEET_SCALES[name]
        if not sheet.SetScale(float(numerator), float(denominator), False, False):
            raise RuntimeError(f"failed to set magnifier sheet scale: {name}")


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
        raise RuntimeError(f"magnifier BOM has no unique {label} column: {header!r}")
    return matches[0]


def _bom_rows(table: Any) -> dict[str, tuple[int, str, str, str]]:
    """(row, item, description, quantity) per family, keyed by stem."""
    contents = _bom_cells(table)
    header = contents[0]
    item_column = _bom_column(header, lambda cell: cell.startswith("ITEM NO"), "ITEM NO.")
    part_column = _bom_column(header, lambda cell: cell == "PART NUMBER", "PART NUMBER")
    description_column = _bom_column(
        header, lambda cell: cell == "DESCRIPTION", "DESCRIPTION"
    )
    quantity_column = _bom_column(header, lambda cell: cell.startswith("QTY"), "QTY.")
    rows: dict[str, tuple[int, str, str, str]] = {}
    for row_index, row in enumerate(contents[1:], start=1):
        text = row[part_column].casefold()
        stem = BOM_NORMALIZED_ALIASES.get(text, text)
        if stem in rows:
            raise RuntimeError(f"magnifier BOM repeats component family {stem!r}")
        rows[stem] = (
            row_index,
            row[item_column],
            row[description_column],
            row[quantity_column],
        )
    if set(rows) != set(BOM_COMPONENTS):
        raise RuntimeError(
            f"magnifier BOM identities {sorted(rows)!r} != {sorted(BOM_COMPONENTS)!r}"
        )
    return rows


def _bom_items(table: Any) -> dict[str, str]:
    return {stem: values[1] for stem, values in _bom_rows(table).items()}


def _validate_bom(adapter: Any, table: Any) -> dict[str, str]:
    """Rewrite part numbers, prove identities/descriptions/quantities, add the
    registry's VENDOR SKU column after DESCRIPTION; return each family's item
    number. Material and finish remain on the component drawings."""
    table = _early_bound(table, "ITableAnnotation")
    contents = _bom_cells(table)
    rows = len(contents)
    columns = len(contents[0]) if contents else 0
    if rows != len(BOM_COMPONENTS) + 1 or columns < 4:
        raise RuntimeError(
            f"magnifier BOM is {rows}x{columns}; expected "
            f"{len(BOM_COMPONENTS) + 1} rows and at least four columns"
        )
    header = contents[0]
    for title in ("MATERIAL", BOM_SKU_TITLE):
        if title in (cell.upper() for cell in header):
            raise RuntimeError(f"magnifier BOM template already has {title!r}")
    part_column = _bom_column(header, lambda cell: cell == "PART NUMBER", "PART NUMBER")
    description_column = _bom_column(
        header, lambda cell: cell == "DESCRIPTION", "DESCRIPTION"
    )
    actual = _bom_rows(table)
    items = {values[1] for values in actual.values()}
    if items != {str(item) for item in range(1, len(BOM_COMPONENTS) + 1)}:
        raise RuntimeError(f"magnifier BOM item numbers {sorted(items)!r} are not contiguous")
    for stem, (row_index, _item, description, quantity) in actual.items():
        number = BOM_PART_NUMBERS[stem]
        if contents[row_index][part_column] != number:
            if not table.IsCellTextEditable(row_index, part_column):
                raise RuntimeError(f"magnifier BOM part-number cell for {stem!r} is locked")
            table.SetText2(row_index, part_column, False, number)
        if description != BOM_DESCRIPTIONS[stem]:
            raise RuntimeError(f"magnifier BOM description mismatch for {stem!r}")
        if quantity != str(BOM_QUANTITIES[stem]):
            raise RuntimeError(
                f"magnifier BOM quantity for {stem!r} is {quantity!r}, "
                f"expected {BOM_QUANTITIES[stem]}"
            )

    # The parts carry no SKU property; made parts print MADE_PART_SKU.
    if not table.InsertColumn2(
        _INSERT_COLUMN_AFTER, description_column, BOM_SKU_TITLE, _INSERT_COLUMN_DEFAULT_WIDTH
    ):
        raise RuntimeError("magnifier BOM refused the VENDOR SKU column")
    column = description_column + 1
    if not table.SetColumnTitle2(column, BOM_SKU_TITLE, False):
        raise RuntimeError("magnifier BOM VENDOR SKU column title did not set")
    for stem, (row_index, *_rest) in actual.items():
        if not table.IsCellTextEditable(row_index, column):
            raise RuntimeError(f"magnifier BOM VENDOR SKU cell for {stem!r} is locked")
        table.SetText2(row_index, column, False, BOM_SKUS[stem])

    header = _bom_cells(table)[0]
    widths = {
        "item": _bom_column(header, lambda cell: cell.startswith("ITEM NO"), "ITEM NO."),
        "part": _bom_column(header, lambda cell: cell == "PART NUMBER", "PART NUMBER"),
        "description": _bom_column(
            header, lambda cell: cell == "DESCRIPTION", "DESCRIPTION"
        ),
        "sku": _bom_column(header, lambda cell: cell == BOM_SKU_TITLE, BOM_SKU_TITLE),
        "quantity": _bom_column(header, lambda cell: cell.startswith("QTY"), "QTY."),
    }
    if len(header) != len(BOM_COLUMN_WIDTHS) or set(widths) != set(BOM_COLUMN_WIDTHS):
        raise RuntimeError(f"magnifier BOM columns {header!r} are not the contract")
    for key, column in widths.items():
        width = BOM_COLUMN_WIDTHS[key]
        if abs(float(table.SetColumnWidth(column, width, 0)) - width) > 1e-6:
            raise RuntimeError(f"magnifier BOM {key} column width did not persist")
    for row in range(rows):
        table.SetRowHeight(row, BOM_ROW_HEIGHT, 0)
    if not adapter.currentModel.EditRebuild3():
        raise RuntimeError("magnifier BOM rebuild failed")
    settled = _bom_cells(table)
    for stem, (row_index, *_rest) in actual.items():
        for key, text in (("part", BOM_PART_NUMBERS[stem]), ("sku", BOM_SKUS[stem])):
            applied = settled[row_index][widths[key]]
            if applied != text:
                raise RuntimeError(
                    f"magnifier BOM {key} for {stem!r} reads {applied!r}, "
                    f"expected {text!r}"
                )
    return {stem: values[1] for stem, values in actual.items()}


def _assert_bom_clears_reference_field(table: Any) -> None:
    """The BOM's printed bottom must stay above the reference view's field.

    The reference field is laid out from :data:`BOM_BOTTOM` before the table
    exists; this reads the inserted table's anchor and row heights (top-left
    anchored, as the layout audit boxes it) so a taller heading or a wrapped
    row fails here, naming the measured bottom. The margin is the audit's
    text air (it wanted 2.26 mm on r3); the hidden view keeps its outline.
    """
    bound = _early_bound(table, "ITableAnnotation")
    annotation = _early_bound(bound.GetAnnotation(), "IAnnotation")
    top = float(annotation.GetPosition()[1])
    row_heights = tuple(
        float(bound.GetRowHeight(row)) for row in range(int(bound.RowCount))
    )
    bottom = top - sum(row_heights)
    _telemetry.info(
        f"magnifier BOM spans y {bottom * 1000.0:.1f}..{top * 1000.0:.1f} mm",
        bom_top_mm=round(top * 1000.0, 2),
        bom_bottom_mm=round(bottom * 1000.0, 2),
    )
    if bottom < BOM_REFERENCE_FIELD[3] + 0.0025:
        failure = RuntimeError(
            f"magnifier BOM bottom {bottom * 1000.0:.1f} mm runs into the reference "
            f"field at {BOM_REFERENCE_FIELD[3] * 1000.0:.1f} mm "
            f"(planned {BOM_BOTTOM * 1000.0:.1f} mm)"
        )
        # Keep native width/height and full grown-row contents in the task log:
        # failed farm leaves do not necessarily retain a drawing for inspection.
        try:
            contents = _bom_cells(bound)
            column_widths_mm = tuple(
                round(float(bound.GetColumnWidth(column)) * 1000.0, 3)
                for column in range(int(bound.ColumnCount))
            )
            row_heights_mm = tuple(round(height * 1000.0, 3) for height in row_heights)
            _telemetry.info(
                f"magnifier BOM columns mm {column_widths_mm!r}; "
                f"rows mm {row_heights_mm!r}",
                bom_column_widths_mm=column_widths_mm,
                bom_row_heights_mm=row_heights_mm,
            )
            for row, height in enumerate(row_heights):
                if height <= BOM_ROW_HEIGHT + 1e-6:
                    continue
                text_heights_mm = tuple(
                    round(
                        float(
                            _early_bound(
                                bound.GetCellTextFormat(row, column), "ITextFormat"
                            ).CharHeight
                        )
                        * 1000.0,
                        3,
                    )
                    for column in range(int(bound.ColumnCount))
                )
                _telemetry.info(
                    f"magnifier BOM row {row}: {height * 1000.0:.3f} mm, "
                    f"text heights mm {text_heights_mm!r}, cells {contents[row]!r}",
                    bom_row=row,
                    bom_row_height_mm=height * 1000.0,
                    bom_cell_text_heights_mm=text_heights_mm,
                    bom_cells=contents[row],
                )
        except Exception as exc:
            try:
                _telemetry.warn(f"magnifier BOM failure diagnostics unavailable: {exc}")
            except Exception:
                pass  # Diagnostic logging must not replace the measured overrun.
        raise failure


def _hide_bom_reference(adapter: Any, view: Any, table: Any, items: dict[str, str]) -> None:
    """Hide the view the BOM is inserted on; the parts list must not move.

    ``IView.SetVisible`` returns nothing, so ``GetVisible`` proves the hide;
    the BOM rows are read again because a table that followed its view's
    visibility into its rows would drop the package's parts list.
    """
    bound = _early_bound(view, "IView")
    bound.SetVisible(False, False)
    rebuild_drawing(adapter, label="hide BOM reference")
    if bool(bound.GetVisible()):
        raise RuntimeError(f"{BOM_REFERENCE_LABEL}: view still reads visible")
    if _bom_items(_early_bound(table, "ITableAnnotation")) != items:
        raise RuntimeError("magnifier BOM items moved when its reference view was hidden")


def wire_balloon_centre(
    landing: tuple[float, float], outline: Box, *, rise_deg: float, reach: float
) -> tuple[float, float]:
    """Sheet point for the wire balloon's circle: ``reach`` right of the
    view's outline, on the line rising ``rise_deg`` from its landing."""
    x = outline[2] + reach
    return x, landing[1] + (x - landing[0]) * math.tan(math.radians(rise_deg))


def _move_wire_balloon(
    adapter: Any, view: Any, landing: BalloonLanding, *, label: str
) -> None:
    """Stand the wire balloon right of the finished view (see
    :data:`FINISHED_WIRE_BALLOON_RISE_DEG`), its landing untouched.

    ``SetPosition`` moves the annotation's anchor, a constant offset from the
    circle the sheet draws (``_drawing_balloons._spread_balloons``), so the
    offset is carried and the circle's centre read back. The landing is the
    frozen balloon ring's hit-tested point; the leader's attachment, the LAST
    point of ``GetLeaderPointsAtIndex(0)`` (as ``_spread_balloons`` reads
    it), must end there.
    """
    if landing.sheet_xy is None:
        raise RuntimeError(f"{label}: the wire balloon's ring landing was not proven")
    note = _early_bound(landing.note, "INote")
    annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
    leader = annotation.GetLeaderPointsAtIndex(0)
    if not leader or len(leader) < 6:
        raise RuntimeError(f"{label}: the wire balloon has no readable leader")
    attach = (float(leader[-3]), float(leader[-2]))
    if math.dist(attach, landing.sheet_xy) > 0.0005:
        miss = math.dist(attach, landing.sheet_xy) * 1000.0
        raise RuntimeError(
            f"{label}: the wire balloon's leader ends {miss:.2f} mm from its proven landing"
        )
    circle_x, circle_y, _radius = rendered_balloon_circle(note, label=label)
    anchor = annotation.GetPosition()
    offset = (float(anchor[0]) - circle_x, float(anchor[1]) - circle_y)
    target = wire_balloon_centre(
        attach,
        _view_outline(view, label=label),
        rise_deg=FINISHED_WIRE_BALLOON_RISE_DEG,
        reach=BALLOON_MARGIN,
    )
    _telemetry.info(
        f"{label}: wire balloon landing ({attach[0] * 1000.0:.1f}, "
        f"{attach[1] * 1000.0:.1f}) mm, circle to ({target[0] * 1000.0:.1f}, "
        f"{target[1] * 1000.0:.1f}) mm",
    )
    if not annotation.SetPosition(target[0] + offset[0], target[1] + offset[1], 0.0):
        raise RuntimeError(f"{label}: failed to move the wire balloon")
    rebuild_drawing(adapter, label="move wire balloon")
    # assert_balloon_landings (a settled check) proves the moved balloon still
    # attaches to the wire; this reports any shift of SolidWorks' own point.
    moved = annotation.GetLeaderPointsAtIndex(0)
    _telemetry.info(
        f"{label}: wire balloon leader now ends at "
        f"({float(moved[-3]) * 1000.0:.1f}, {float(moved[-2]) * 1000.0:.1f}) mm",
    )
    moved_x, moved_y, _radius = rendered_balloon_circle(note, label=label)
    if math.dist((moved_x, moved_y), target) > 0.0005:
        raise RuntimeError(
            f"{label}: wire balloon centred at ({moved_x * 1000.0:.1f}, "
            f"{moved_y * 1000.0:.1f}) mm, not ({target[0] * 1000.0:.1f}, "
            f"{target[1] * 1000.0:.1f}) mm"
        )


def caption_under(outline: Box, text: str) -> tuple[float, float]:
    """Top-left of a one-line caption centred under ``outline``."""
    width = len(text) * CAPTION_CHAR_WIDTH
    return (outline[0] + outline[2] - width) / 2.0, outline[1] - CAPTION_GAP


def lever_caption_xy(outline: Box, text: str) -> tuple[float, float]:
    """``caption_under`` the lever view, proved clear of the title block."""
    left, top = caption_under(outline, text)
    if top - NOTE_LINE_PITCH < TITLE_BLOCK[3] + _PAD:
        raise ValueError(
            f"lever caption at {(left, top)!r} reaches the title block: the view "
            f"outline {outline!r} sits too low"
        )
    return left, top


def caption_over(outline: Box, text: str) -> tuple[float, float]:
    """Top-left of a one-line caption centred over ``outline``."""
    width = len(text) * CAPTION_CHAR_WIDTH
    return (
        (outline[0] + outline[2] - width) / 2.0,
        outline[3] + CAPTION_GAP + NOTE_LINE_PITCH,
    )


def _link_view_to_bom(view: Any, table: Any, *, label: str) -> None:
    """Number ``view``'s balloons from the BOM table inserted on another view."""
    bom = _early_bound(table, "IBomTableAnnotation")
    feature = _early_bound(bom.BomFeature, "IBomFeature")
    name = str(feature.Name or "")
    if not name:
        raise RuntimeError("magnifier BOM feature has no name")
    view = _early_bound(view, "IView")
    if not view.SetKeepLinkedToBOM(True, name):
        raise RuntimeError(f"{label}: SetKeepLinkedToBOM({name!r}) returned false")
    if (
        not bool(view.GetKeepLinkedToBOM())
        or str(view.GetKeepLinkedToBOMName() or "") != name
    ):
        raise RuntimeError(f"{label}: view is not linked to BOM {name!r}")


def balloon_items(
    items: dict[str, str], stems: frozenset[str]
) -> tuple[tuple[str, str], ...]:
    """(stem, item) for each BOM family in ``stems``, in BOM order."""
    return tuple((stem, items[stem]) for stem in BOM_COMPONENTS if stem in stems)


@contextmanager
def _source_configuration_active(view: Any, *, label: str) -> Iterator[None]:
    """Read an exploded view's steps with its source configuration active.

    Named model views preserve a camera, not an active-configuration contract.
    On d58d05d82 the simplified MG explode read zero steps while the source
    remained in Default. As on the pen and oblique-jig drawings, activate the
    referenced configuration for the balloon walk; the shared reader still
    shows/collapses its real explode and refuses missing steps. Restore the
    source configuration before any later view or final readback.
    """
    bound = _early_bound(view, "IView")
    if not bool(bound.IsExploded()):
        yield
        return
    wanted = str(bound.ReferencedConfiguration)
    model = _early_bound(bound.ReferencedDocument, "IModelDoc2")
    manager = _early_bound(model.ConfigurationManager, "IConfigurationManager")

    def active() -> str:
        return str(_early_bound(manager.ActiveConfiguration, "IConfiguration").Name)

    rest = active()
    try:
        if rest != wanted and (
            not bool(model.ShowConfiguration2(wanted)) or active() != wanted
        ):
            raise RuntimeError(f"{label}: the source did not activate {wanted!r}")
        if not bool(bound.IsExploded()) or str(bound.ReferencedConfiguration) != wanted:
            raise RuntimeError(
                f"{label}: activating {wanted!r} on the source changed the view"
            )
        yield
    finally:
        primary_error = sys.exception()
        try:
            if active() != rest and (
                not bool(model.ShowConfiguration2(rest)) or active() != rest
            ):
                raise RuntimeError(f"{label}: the source did not re-activate {rest!r}")
            if (
                not bool(bound.IsExploded())
                or str(bound.ReferencedConfiguration) != wanted
            ):
                raise RuntimeError(f"{label}: restoring {rest!r} changed the view")
        except Exception as cleanup_error:
            if primary_error is None:
                raise
            _telemetry.warn(f"{label}: restoring {rest!r}: {cleanup_error}")


def _place_assembled_sheet(adapter: Any) -> tuple[Callable[[], None], ...]:
    """Preserved back, left and isometric at 1:4, the lever settings on the
    back view and the two axle-stack details."""
    _activate_sheet(adapter, SHEET_NAMES[0])
    front = None
    captioned = []
    for name, centre in (
        (stack.DRAWING_BACK_VIEW, FRONT_CENTER),
        (stack.DRAWING_LEFT_VIEW, RIGHT_CENTER),
        (stack.DRAWING_ISOMETRIC_VIEW, ISO_CENTER),
    ):
        view = place_view(adapter, str(SOURCE), name, *centre, scale=SHEET_SCALE)
        # Back and left print the simplified configuration at 1:4; the
        # preserved isometric is the full-detail view.
        role = ViewRole.FULL_DETAIL if name == stack.DRAWING_ISOMETRIC_VIEW else ViewRole.PLAIN
        apply_view_configuration(adapter, view, role=role, label=f"{PDF_TITLE} {name}")
        if name == stack.DRAWING_BACK_VIEW:
            front = view
        if name in ASSEMBLED_VIEW_CAPTIONS:
            captioned.append((view, name))
    lever_settled = _lever_settings(adapter, front)
    stack_settled = _stack_dimensions(adapter)
    for view, name in captioned:
        _add_note_block(
            adapter,
            SHEET_NAMES[0],
            ASSEMBLED_VIEW_CAPTIONS[name],
            caption_under(_view_outline(view, label=name), ASSEMBLED_VIEW_CAPTIONS[name]),
            label=f"{name} caption",
        )
    return lever_settled, stack_settled


def _place_exploded_view(
    adapter: Any, sheet_name: str, field: Box, *, label: str
) -> Any:
    """MG_MAGNIFIER_EXPLODED at EXPLODED_SCALE, configured and exploded before
    anything binds to it; isolated and fitted after the BOM exists."""
    _activate_sheet(adapter, sheet_name)
    view = place_view(
        adapter,
        str(SOURCE),
        stack.DRAWING_ISOMETRIC_VIEW,
        (field[0] + field[2]) / 2.0,
        (field[1] + field[3]) / 2.0,
        scale=EXPLODED_SCALE,
    )
    set_high_quality_shaded_with_edges(adapter, view, label=label)
    configuration = apply_view_configuration(adapter, view, label=label)
    if configuration != SIMPLIFIED_VIEW_CONFIGURATION:
        raise RuntimeError(f"{label} references {configuration!r}")
    set_view_exploded_state(adapter, view, True, configuration=configuration, label=label)
    return view


def _place_collapsed_view(
    adapter: Any,
    sheet_name: str,
    field: Box,
    scale: tuple[float, float],
    *,
    label: str,
) -> Any:
    """A collapsed whole-assembly isometric at ``scale`` in ``field``."""
    _activate_sheet(adapter, sheet_name)
    view = place_view(
        adapter,
        str(SOURCE),
        stack.DRAWING_ISOMETRIC_VIEW,
        (field[0] + field[2]) / 2.0,
        (field[1] + field[3]) / 2.0,
        scale=scale,
    )
    set_high_quality_shaded_with_edges(adapter, view, label=label)
    configuration = apply_view_configuration(adapter, view, label=label)
    set_view_exploded_state(adapter, view, False, configuration=configuration, label=label)
    return view


_TANGENT_EDGES_VISIBLE = 2  # swDisplayTangentEdges_e.swTangentEdgesVisible


def _show_tangent_edges(adapter: Any, view: Any, *, label: str) -> None:
    """Draw the view's tangent edges and read the mode back.

    The lever and vertical rod balloons are pinned to their capsules' dome
    tangent circles (:data:`BALLOON_ANCHORS`), which a hit test can only
    select while the view draws tangent edges. The mode read 2 (visible)
    before any change on r2 (run
    20261016T065610791Z-790156178d0b4378a1fd0680e77ece6b); the read-back keeps
    a template change from silently hiding the anchors' edges.
    """
    bound = _early_bound(view, "IView")
    before = int(bound.GetDisplayTangentEdges2())
    if before != _TANGENT_EDGES_VISIBLE:
        bound.SetDisplayTangentEdges2(_TANGENT_EDGES_VISIBLE)
        if not adapter.currentModel.EditRebuild3():
            raise RuntimeError(f"{label}: tangent-edge rebuild failed")
    after = int(bound.GetDisplayTangentEdges2())
    _telemetry.info(
        f"{label}: tangent edges {before} -> {after}",
        tangent_before=before,
        tangent_after=after,
    )
    if after != _TANGENT_EDGES_VISIBLE:
        raise RuntimeError(f"{label}: tangent edges read {after}, not visible")


@_telemetry.traced("drawing.mg_magnifier_assembly")
async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source assembly is missing: {SOURCE}")
    check("open assembly drawing source", await adapter.open_model(str(SOURCE)))
    source_model = _early_bound(adapter.currentModel, "IModelDoc2")
    properties = read_required_properties(
        source_model,
        ("Number", "Revision", "Title", "Material Specification", "Finish", "Quantity"),
        required=("Number", "Revision", "Material Specification", "Finish", "Quantity"),
    )
    if properties["Number"] != notes.DRAWING_NUMBER:
        raise RuntimeError(
            f"magnifier source Number {properties['Number']!r} != "
            f"{notes.DRAWING_NUMBER!r}"
        )
    _validate_source(source_model)
    _create_sheets(adapter)
    settled_checks = _place_assembled_sheet(adapter)
    # Every drawing view's configuration and exploded state is final before
    # the BOM binds; only the source's active configuration changes for reads.
    wheel = _place_exploded_view(adapter, SHEET_NAMES[1], WHEEL_FIELD, label=WHEEL_LABEL)
    reference = _place_collapsed_view(
        adapter,
        SHEET_NAMES[1],
        BOM_REFERENCE_FIELD,
        BOM_REFERENCE_SCALE_LADDER[0],
        label=BOM_REFERENCE_LABEL,
    )
    lever = _place_exploded_view(adapter, SHEET_NAMES[2], LEVER_FIELD, label=LEVER_LABEL)
    finished = _place_collapsed_view(
        adapter, SHEET_NAMES[3], FINISHED_FIELD, SHEET_SCALE, label=FINISHED_LABEL
    )
    assert_full_detail_view(adapter, label=PDF_TITLE)

    # The reference carries no balloons, so its ring is its outline: fit the
    # outline grown by the balloon reach.
    _activate_sheet(adapter, SHEET_NAMES[1])
    _fit_ring(
        adapter,
        reference,
        BOM_REFERENCE_SCALE_LADDER,
        _grown(BOM_REFERENCE_FIELD, BALLOON_RING_REACH),
        label=BOM_REFERENCE_LABEL,
    )
    table = insert_bom_table(
        adapter,
        reference,
        anchor_xy=BOM_ANCHOR,
        expected_components=BOM_COMPONENTS,
        descriptions=BOM_DESCRIPTIONS,
        identity_aliases=BOM_IDENTITY_ALIASES,
        configuration_grouping="same-part",
        label="magnifier",
    )
    items = _validate_bom(adapter, table)
    _assert_bom_clears_reference_field(table)
    for view, label in (
        (wheel, WHEEL_LABEL),
        (lever, LEVER_LABEL),
        (finished, FINISHED_LABEL),
    ):
        _link_view_to_bom(view, table, label=label)
    for view, stems, label in (
        (wheel, explode.WHEEL_GROUP_STEMS, WHEEL_LABEL),
        (lever, explode.LEVER_GROUP_STEMS, LEVER_LABEL),
    ):
        isolate_drawing_view_components(adapter, view, visible_stems=stems, label=label)
    _show_tangent_edges(adapter, lever, label=LEVER_LABEL)
    # View-only isolation must leave the logical parts list alone.
    if _bom_items(_early_bound(table, "ITableAnnotation")) != items:
        raise RuntimeError("magnifier BOM items moved when the exploded views were isolated")

    landings = []
    scales = {}
    for sheet_name, view, ladder, field, stems, label in (
        (
            SHEET_NAMES[1],
            wheel,
            EXPLODED_SCALE_LADDER,
            WHEEL_FIELD,
            explode.WHEEL_GROUP_STEMS,
            WHEEL_LABEL,
        ),
        (
            SHEET_NAMES[2],
            lever,
            LEVER_SCALE_LADDER,
            LEVER_FIELD,
            explode.LEVER_GROUP_STEMS,
            LEVER_LABEL,
        ),
        (
            SHEET_NAMES[3],
            finished,
            FINISHED_SCALE_LADDER,
            FINISHED_FIELD,
            frozenset({explode.WIRE_STEM}),
            FINISHED_LABEL,
        ),
    ):
        _activate_sheet(adapter, sheet_name)
        scales[label] = _fit_ring(adapter, view, ladder, field, label=label)
        # TODO(#1667): Restore disabled wheel/lever groups only after the linked
        # fix is validated; remove MB-1667-MG and this TODO with restoration.
        # landings += add_component_bom_balloons(
        #     adapter,
        #     view,
        #     items=balloon_items(items, stems),
        #     anchors=BALLOON_ANCHORS,
        #     label=f"magnifier {label} BOM coverage",
        #     margin=BALLOON_MARGIN,
        # )
    # Preserve the finished-wire partial balloon path.
    landings += add_component_bom_balloons(
        adapter,
        finished,
        items=balloon_items(items, frozenset({explode.WIRE_STEM})),
        anchors=BALLOON_ANCHORS,
        label=f"magnifier {FINISHED_LABEL} BOM coverage",
        margin=BALLOON_MARGIN,
    )
    # if len(landings) != len(BOM_COMPONENTS):
    #     raise RuntimeError(
    #         f"magnifier package carries {len(landings)} balloons, expected one per "
    #         f"BOM row ({len(BOM_COMPONENTS)})"
    #     )
    (wire_landing,) = (landing for landing in landings if landing.stem == explode.WIRE_STEM)
    _move_wire_balloon(adapter, finished, wire_landing, label=FINISHED_LABEL)

    _add_note_block(
        adapter,
        SHEET_NAMES[1],
        exploded_caption(WHEEL_GROUP, scales[WHEEL_LABEL]),
        WHEEL_CAPTION_XY,
        label="wheel caption",
    )
    lever_caption = exploded_caption(LEVER_GROUP, scales[LEVER_LABEL])
    _add_note_block(
        adapter,
        SHEET_NAMES[2],
        lever_caption,
        lever_caption_xy(_view_outline(lever, label=LEVER_LABEL), lever_caption),
        label="lever caption",
    )
    finished_caption = f"{FINISHED_CAPTION} (SCALE {scale_text(scales[FINISHED_LABEL])})"
    _add_note_block(
        adapter,
        SHEET_NAMES[3],
        finished_caption,
        caption_over(_view_outline(finished, label=FINISHED_LABEL), finished_caption),
        label="finished caption",
    )
    _add_note_block(
        adapter, SHEET_NAMES[3], ASSEMBLY_STEPS, STEPS_XY, label="assembly sequence"
    )
    _add_note_block(
        adapter, SHEET_NAMES[3], ASSEMBLY_CHECKS, CHECKS_XY, label="assembly checks"
    )
    _activate_sheet(adapter, SHEET_NAMES[1])
    _hide_bom_reference(adapter, reference, table, items)
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        layout=SPEC.layout,
        pdf_title=PDF_TITLE,
        scale=SHEET_SCALE,
        expected_sheet_names=SHEET_NAMES,
        sheet_layouts=SHEET_LAYOUTS,
        # Each sheet's title-block scale is its main view's: the ladder's
        # rung the exploded and finished views settled on.
        sheet_scales={
            SHEET_NAMES[0]: SHEET_SCALE,
            SHEET_NAMES[1]: scales[WHEEL_LABEL],
            SHEET_NAMES[2]: scales[LEVER_LABEL],
            SHEET_NAMES[3]: scales[FINISHED_LABEL],
        },
        settled_checks=(
            *settled_checks,
            lambda: assert_balloon_landings(adapter, landings),
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
