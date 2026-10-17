r"""Pure placement, BOM and clearance contract for ch-rocker-arm-tl-oblique-jig.SLDASM
(MHA-CH-006-TL-000).

Shop fixture, not a machine assembly (cad/docs/subsystem-identities.md): the
rocker arm's oblique-trammel mill jig, set up on the PM-30MV table. It never
enters the harmonic-analyzer assembly tree or a machine BOM
(``_buildgraph.is_shop_fixture``; test_part_coverage.py). Values marked ⚙ are
read from the calculator ``ch_rocker_arm_tl_oblique_trammel_spec`` (imported as
``trammel``), never retyped.

Material: see the component drawings (TL-20 to TL-26, TL-28, TL-29). Overall
envelope at the modelled pose, machine frame: X -460.0 (the far leadscrew
bracket's outer corner) to +457.6 (bar 2's far end), Y -347.5 (the feed
lever's grip end) to +74.7 (the near end bracket's outer corner), Z 0 to
87.7 (the HUB pin's top); see ``MODEL_EXTENT``.

Frame: the MACHINE frame. Origin on the spindle axis at the table top; +X along
the table, +Y toward the column, +Z up. Rotation rows follow ``_transforms``:
``rows[i]`` is the machine-frame image of the part's local axis ``i``.

Modelled pose: the symmetric inner pass (θ = 0). The carrier rides A1/B1 on
the two pivot pins, its pose ``trammel.carrier_pose("inner", 0)`` ⚙; each
pivot block stands at carriage station
``SYMMETRIC_PIN_STATION["inner"] - PIN_OFFSET`` ⚙ on its rail
(``trammel.rail_point``). Heights are the calculator's stack ⚙: base bars on
the table, carriage tops at ``CARRIAGE_TOP_Z`` 40.7, pivot blocks to 64.7, the
carrier from ``CARRIER_UNDERSIDE_Z`` 67.7 to ``CARRIER_TOP_Z`` 79.7; riser and
feed lever on the carrier top; the HUB pin's head under the carrier.

Leadscrew feed (``ch_rocker_arm_tl_oblique_leadscrew_spec``, imported as
``leadscrew``): two TL-28 end brackets screwed up from bar 1's
underside carry the KP08 blocks; the TL-29 nut bracket bolts to pivot block
1's column-side face and carries the flanged nut, so it rides with carriage
1. The Tr8x2 nut does not back-drive: the TL-26 lever feeds (roughing) only
with the nut bracket's block screws out; the handwheel feeds the finish pass.

Bought hardware is NOT modelled (TrammelJig ruling, option (a)): the two
HGR15R rails, the two HGH15CA carriages, the four 6200-2RS bearings, the
CL dowel, the hold-down studs, the leadscrew, its nut, the two KP08 blocks
and the handwheel. The pivot blocks therefore stand on the carriages' top
plane with nothing modelled under them. The drawing's BOM lists each bought
item by its shop-inventory id only, never a vendor SKU, so a source change
needs no edit here (``BOUGHT_ITEMS``), and the clearance check below carries
their catalogue envelopes (the KP08s with ``leadscrew.KP08_MARGIN`` all
round). No skid (user ruling).

The clearance check (``clearance_report``) sweeps both passes over
``trammel.SWEEP`` ⚙ and reports: the clearance of every moving outline to the
column's pleated cover (Y = +``THROAT_TO_COVER`` ⚙), the machine X/Y reached,
each base bar's overhang past its table end, each carriage's margin on its
rail, every plan gap between a moving and a fixed item whose heights overlap,
every height gap where their plans overlap (moving: carriages, pivot blocks
and pins, the nut bracket, carrier, riser, lever and HUB pin head; fixed: the
bars, rails, studs, nuts and the feed's brackets, KP08s, screw and
handwheel), and every outline's margin to the four table edges.
test_ch_rocker_arm_tl_oblique_jig_assembly.py pins the numbers.

The hold-down stud envelope is an ESTIMATE, not a measurement (the
ShopTrammelInventory reply: kit ``fixtures.clamping-kit-pm-52pcck-14mm``, its
sizes not yet measured): 1/2-13 stud bottomed flush with its T-nut's foot,
the foot in the PM-30MV slot's undercut, a Ø28 x 13 flange nut on the bar.
"""

from __future__ import annotations

import math
from collections.abc import Iterator
from dataclasses import dataclass

import ch_rocker_arm_tl_oblique_base_bar_spec as base_bar
import ch_rocker_arm_tl_oblique_carrier_spec as carrier
import ch_rocker_arm_tl_oblique_fasteners_spec as fasteners
import ch_rocker_arm_tl_oblique_feed_lever_spec as feed_lever
import ch_rocker_arm_tl_oblique_hub_pin_spec as hub_pin
import ch_rocker_arm_tl_oblique_leadscrew_spec as leadscrew
import ch_rocker_arm_tl_oblique_nut_bracket_spec as nut_bracket
import ch_rocker_arm_tl_oblique_pivot_block_spec as pivot_block
import ch_rocker_arm_tl_oblique_pivot_pin_spec as pivot_pin
import ch_rocker_arm_tl_oblique_riser_spec as riser
import ch_rocker_arm_tl_oblique_trammel_spec as trammel

ASM_NAME = "ch-rocker-arm-tl-oblique-jig"
DRAWING_NUMBER = "MHA-CH-006-TL-000"

BASE_BAR = "ch-rocker-arm-tl-oblique-base-bar"
PIVOT_BLOCK = "ch-rocker-arm-tl-oblique-pivot-block"
PIVOT_PIN = "ch-rocker-arm-tl-oblique-pivot-pin"
CARRIER = "ch-rocker-arm-tl-oblique-carrier"
RISER = "ch-rocker-arm-tl-oblique-riser"
HUB_PIN = "ch-rocker-arm-tl-oblique-hub-pin"
FEED_LEVER = "ch-rocker-arm-tl-oblique-feed-lever"
END_BRACKET = leadscrew.END_BRACKET
NUT_BRACKET = leadscrew.NUT_BRACKET

# Every component family and its count: the builder places, the explode moves
# and the drawing's BOM proves exactly this inventory (registry order TL-20..29).
QUANTITIES = {
    BASE_BAR: base_bar.QUANTITY,
    PIVOT_BLOCK: 2,
    PIVOT_PIN: 2,
    CARRIER: 1,
    RISER: 1,
    HUB_PIN: 1,
    FEED_LEVER: 1,
    END_BRACKET: leadscrew.END_BRACKET_QUANTITY,
    NUT_BRACKET: leadscrew.NUT_BRACKET_QUANTITY,
}
BOM_ORDER = (
    BASE_BAR,
    PIVOT_BLOCK,
    PIVOT_PIN,
    CARRIER,
    RISER,
    HUB_PIN,
    FEED_LEVER,
    END_BRACKET,
    NUT_BRACKET,
)

Rows = tuple[tuple[float, float, float], ...]
Point3 = tuple[float, float, float]

# --- The modelled pose ⚙ ---------------------------------------------------------
PASS = "inner"
THETA = 0.0
POSE = trammel.carrier_pose(PASS, THETA)
PIN_STATION = trammel.SYMMETRIC_PIN_STATION[PASS]  # ⚙ 227.404 on both rails
CARRIAGE_STATION = PIN_STATION - trammel.PIN_OFFSET  # ⚙ 259.404
RAILS = (1, 2)  # rail 1 on the -X side, rail 2 on the +X side
# One base bar part (TL-20, QTY 2). Rail 1 takes it as saved; rail 2 takes it
# turned over (180° about its long axis), which swaps its slots' sides so
# each slot still lands on its T-slot stud. Every bar feature goes through.
TURNED_OVER = {1: False, 2: True}
if base_bar.QUANTITY != len(RAILS):
    raise AssertionError("one base bar under each rail")


def _unit(vector: tuple[float, float]) -> tuple[float, float]:
    length = math.hypot(*vector)
    return (vector[0] / length, vector[1] / length)


def rail_direction(rail: int) -> tuple[float, float]:
    """Machine XY unit vector along ``rail``, away from the spindle."""
    x0, y0 = trammel.rail_point(rail, 0.0)
    x1, y1 = trammel.rail_point(rail, 1.0)
    return _unit((x1 - x0, y1 - y0))


def rail_rows(rail: int) -> Rows:
    """+X along the rail away from the spindle, +Z up, +Y = Z x X."""
    dx, dy = rail_direction(rail)
    return ((dx, dy, 0.0), (-dy, dx, 0.0), (0.0, 0.0, 1.0))


def _rz(rotation: float, rows: Rows) -> Rows:
    """``rows`` turned about machine Z by ``rotation`` (radians, CCW)."""
    c, s = math.cos(rotation), math.sin(rotation)
    return tuple((c * x - s * y, s * x + c * y, z) for x, y, z in rows)


def _at(point: tuple[float, float], z: float) -> Point3:
    x, y = POSE.to_machine(point)
    return (x, y, z)


def _turned_over(rows: Rows) -> Rows:
    """``rows`` rotated 180° about the part's own X (long) axis."""
    x, y, z = rows
    return (x, tuple(-c for c in y), tuple(-c for c in z))


# Base bars: origin on the spindle-end face, on the rail axis, bottom face on
# the table; the bar runs from RAIL_NEAR_S ⚙ with its rail flush at both ends.
# Turned over, the part's bottom face (its z = 0) is on top, so its origin
# stands BASE_BAR_THICK ⚙ above the table.
BASE_BAR_PLACEMENTS: tuple[tuple[Point3, Rows], ...] = tuple(
    (
        (
            *trammel.rail_point(rail, trammel.RAIL_NEAR_S),
            trammel.BASE_BAR_THICK if TURNED_OVER[rail] else 0.0,
        ),
        _turned_over(rail_rows(rail)) if TURNED_OVER[rail] else rail_rows(rail),
    )
    for rail in RAILS
)

# Pivot blocks: origin at the carriage centre on the block's bottom face (the
# carriage top), +X along the rail away from the spindle, so the bore at
# x = PIN_OFFSET ⚙ lands on the pin station.
PIVOT_BLOCK_PLACEMENTS: tuple[tuple[Point3, Rows], ...] = tuple(
    (
        (*trammel.rail_point(rail, CARRIAGE_STATION), trammel.CARRIAGE_TOP_Z),
        rail_rows(rail),
    )
    for rail in RAILS
)

# Pivot pins: axis Z, origin at the bottom end; the collar seats on the upper
# inner race in the block's top recess, so the bottom end stands
# BEARING_RECESS ⚙ above the block's bottom face (pivot_pin_spec frame).
PIN_BOTTOM_Z = trammel.CARRIAGE_TOP_Z + trammel.BEARING_RECESS
PIVOT_PIN_ORIGINS: tuple[Point3, ...] = tuple(
    _at(pin, PIN_BOTTOM_Z) for pin in trammel.pin_pair(PASS)
)
IDENTITY_ROWS: Rows = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
PIN_ROWS = _rz(POSE.rotation, IDENTITY_ROWS)

# Carrier: the SolidWorks model is Y-up (model X = carrier X, model Y = carrier
# Z, model Z = -carrier Y; carrier_spec), origin at the A1-B1 midpoint on the
# top face.
CARRIER_ORIGIN = _at((0.0, 0.0), trammel.CARRIER_TOP_Z)
CARRIER_ROWS = _rz(POSE.rotation, ((1.0, 0.0, 0.0), (0.0, 0.0, 1.0), (0.0, -1.0, 0.0)))

# Riser: Z-up, origin at the blank corner RISER_BLANK_ORIGIN ⚙ on its bottom
# face, axes parallel to the carrier's.
RISER_ORIGIN = _at(riser.BLANK_ORIGIN, trammel.CARRIER_TOP_Z)
RISER_ROWS = PIN_ROWS

# HUB pin: axis Z, origin at the head's bottom face; the head seats on the
# carrier's underside.
HUB_PIN_ORIGIN = _at(trammel.HUB, trammel.CARRIER_UNDERSIDE_Z - hub_pin.HEAD_LENGTH)
HUB_PIN_ROWS = PIN_ROWS

# Feed lever: Y-up model, +X toward the operator (carrier -Y), +Y up, width
# along model -Z (carrier +X); origin at the inner end on the bottom face and
# the back long side, so the hole line (model z = -HOLE_Y) lands on carrier
# X = 0 and the inner end on LEVER_INNER_END_Y.
FEED_LEVER_ORIGIN = _at(
    (-feed_lever.HOLE_Y, carrier.LEVER_INNER_END_Y), trammel.CARRIER_TOP_Z
)
FEED_LEVER_ROWS = _rz(
    POSE.rotation, ((0.0, -1.0, 0.0), (0.0, 0.0, 1.0), (-1.0, 0.0, 0.0))
)

# Leadscrew feed (leadscrew_spec), on rail 1's column side. End brackets:
# Z-up, origin on the bottom face at the inner end, mid-width, +X outward
# (rail 1's +lateral, the block's -Y), +Y along the rail away from the spindle;
# each stands on bar 1's top under its KP08.
END_BRACKET_ROWS: Rows = (
    tuple(-c for c in rail_rows(leadscrew.RAIL)[1]),
    rail_rows(leadscrew.RAIL)[0],
    (0.0, 0.0, 1.0),
)
END_BRACKET_PLACEMENTS: tuple[tuple[Point3, Rows], ...] = tuple(
    (
        (
            *leadscrew.point(s, leadscrew.BRACKET_INNER_LATERAL),
            trammel.BASE_BAR_THICK,
        ),
        END_BRACKET_ROWS,
    )
    for s in leadscrew.KP08_S
)
# Nut bracket: pivot block 1's axes, origin on the block's -Y face (rail 1's
# +lateral) at the carriage centre, on the bracket's bottom face.
NUT_BRACKET_ORIGIN: Point3 = (
    *leadscrew.point(CARRIAGE_STATION, leadscrew.BLOCK_SIDE_LATERAL),
    leadscrew.NUT_BRACKET_BOTTOM_Z,
)
NUT_BRACKET_ROWS = rail_rows(leadscrew.RAIL)

# --- Heights ⚙ ---------------------------------------------------------------------
RAIL_TOP_Z = trammel.RAIL_SEAT_Z + trammel.RAIL_HEIGHT  # 27.7
CARRIAGE_UNDERSIDE_Z = trammel.RAIL_SEAT_Z + trammel.CARRIAGE_UNDER  # 17.0
HUB_HEAD_BOTTOM_Z = HUB_PIN_ORIGIN[2]  # 63.7
HUB_PIN_TOP_Z = HUB_HEAD_BOTTOM_Z + hub_pin.OVERALL_LENGTH  # 87.7
PIN_TOP_Z = PIN_BOTTOM_Z + pivot_pin.OVERALL_LENGTH  # 78.7
PART_TOP_Z = trammel.CARRIER_TOP_Z + trammel.RISER_THICK + trammel.STRAP_THICK  # 88.2

# --- Hold-down studs (ESTIMATES, unmeasured) ---------------------------------------
# PM-30MV T-slot: 14 throat (⚙ TSLOT_WIDTH) about 14 deep to the undercut; the
# kit's T-nut foot is 8 high and is pulled up against the undercut's roof, and
# the stud bottoms flush with the foot. The kit's 3 in stud only (``fasteners``).
TSLOT_THROAT_DEPTH = 14.0  # estimate
TNUT_FOOT_HEIGHT = 8.0  # estimate (kit T-nut foot 24 x 24 x 8)
STUD_BOTTOM_Z = -(TSLOT_THROAT_DEPTH + TNUT_FOOT_HEIGHT)
STUD_DIA = base_bar.HOLD_DOWN_STUD_DIA  # 1/2-13
STUD_LENGTH = fasteners.HOLD_DOWN_STUD_LENGTH_MM  # the kit's 3 in stud only
STUD_TOP_Z = STUD_BOTTOM_Z + STUD_LENGTH  # 54.2
# The longest stud the sweep clears: the carrier's underside, the lowest moving
# face over a stud, less the stud's bottom. The test pins it equal to the
# sweep's own ``ClearanceReport.stud_length_max``; step 2 states it.
STUD_LENGTH_MAX = trammel.CARRIER_UNDERSIDE_Z - STUD_BOTTOM_Z  # 89.7


def inch_eighths_down(mm: float) -> str:
    """``mm`` in inches rounded down to 1/8, as shop text (``3-1/2``)."""
    eighths = math.floor(mm / trammel.INCH * 8.0 + 1e-9)
    whole, part = divmod(eighths, 8)
    if not part:
        return f"{whole}"
    common = math.gcd(part, 8)
    fraction = f"{part // common}/{8 // common}"
    return f"{whole}-{fraction}" if whole else fraction


FLANGE_NUT_DIA = 28.0  # estimate
FLANGE_NUT_HEIGHT = 13.0  # estimate
FLANGE_NUT_TOP_Z = trammel.BASE_BAR_THICK + FLANGE_NUT_HEIGHT  # 25.7

# --- Table ⚙ --------------------------------------------------------------------------
TABLE_X = (-trammel.TABLE_LENGTH / 2.0, trammel.TABLE_LENGTH / 2.0)
TABLE_Y = (
    trammel.TABLE_CENTRE_Y - trammel.TABLE_WIDTH / 2.0,
    trammel.TABLE_CENTRE_Y + trammel.TABLE_WIDTH / 2.0,
)
COVER_Y = trammel.THROAT_TO_COVER  # the column's pleated cover, 7.5 in from the spindle

# --- Bought items (not modelled) --------------------------------------------------
# Inventory ids from the shop inventory, cad/process/shop/inventory.toml on
# main; the inventory owns each item's source and SKU. Descriptions carry no
# vendor or brand. The rail is a cut-to-440 special order whose E = 40
# symmetric end distance is an unverified vendor quote; the dowel's fit class
# is not published. Only the test reads inventory.toml, so it stays out of the
# build keys.


@dataclass(frozen=True)
class BoughtItem:
    inventory_id: str
    description: str
    quantity: int


BOUGHT_ITEMS: tuple[BoughtItem, ...] = (
    BoughtItem(
        "fixtures.trammel-hgr15-rails",
        f"HGR15R RAIL, {trammel.RAIL_LENGTH:.0f}, E{trammel.RAIL_HOLE_END:.0f} BOTH ENDS",
        2,
    ),
    BoughtItem(
        "fixtures.trammel-hgh15ca-carriages",
        "HGH15CA CARRIAGE, Z0 PRELOAD",
        2,
    ),
    BoughtItem(
        "fixtures.trammel-6200-2rs",
        "6200-2RS BALL BEARING 10 X 30 X 9",
        trammel.BEARINGS_PER_PIN * QUANTITIES[PIVOT_PIN],
    ),
    BoughtItem(
        "fixtures.trammel-cl-dowel",
        "DOWEL PIN 6 X 20 M6, CL LOCATOR",
        1,
    ),
    BoughtItem(
        "fixtures.clamping-kit-pm-52pcck-14mm",
        "HOLD-DOWN: 1/2-13 X 3 IN STUD, T-NUT, FLANGE NUT",
        2 * len(trammel.HOLD_DOWN_STUDS),
    ),
    BoughtItem(
        leadscrew.SCREW_ID,
        f"TR8X2 LEADSCREW, {leadscrew.SCREW_LENGTH:.0f} LONG",
        1,
    ),
    BoughtItem(
        leadscrew.NUT_ID,
        "TR8X2 FLANGED NUT, BRASS",
        1,
    ),
    BoughtItem(
        leadscrew.KP08_ID,
        "PILLOW BLOCK, 8 BORE, SET SCREWS",
        2,
    ),
    BoughtItem(
        leadscrew.HANDWHEEL_ID,
        f"HANDWHEEL {leadscrew.HANDWHEEL_WHEEL_DIA:.0f} DIA, 8 BORE",
        1,
    ),
)

# BOM DESCRIPTION cells for the modelled parts (the parts carry no
# Description property); the steps name the parts the same way.
BOM_DESCRIPTIONS = {
    BASE_BAR: "BASE BAR",
    PIVOT_BLOCK: "PIVOT BLOCK",
    PIVOT_PIN: "PIVOT PIN",
    CARRIER: "CARRIER PLATE",
    RISER: "ACETAL RISER",
    HUB_PIN: "HUB LOCATOR PIN",
    FEED_LEVER: "FEED LEVER",
    END_BRACKET: "END BRACKET",
    NUT_BRACKET: "NUT BRACKET",
}

# --- Native explode (JIG_EXPLODED) -------------------------------------------------
# The disassembly order, ASSEMBLY_STEPS read back to front, along Z so the
# exploded isometric (ISOMETRIC_VIEW, +Z up the sheet) stands the stack in
# its fitting order: base bars on the table with the end brackets on bar
# 1, the pivot blocks (the nut bracket bolted on block 1) over the carriages'
# plane (the rails, carriages and the feed's bought parts are not modelled),
# each pivot pin above its block, bearing end down, as it is pressed in; then
# the carrier with its HUB pin dropped out beneath it, and the riser and the
# feed lever over it. Each step's families move by a signed distance; a
# family's lift is the sum of the steps naming it (``explode_lift``).
# (label, families, axis, signed distance mm).
EXPLODED_VIEW_NAME = "JIG_EXPLODED"
SOURCE_CONFIGURATION = "Default"
EXPLODE_STEPS = (
    ("feed lever lifts off", (FEED_LEVER,), "z", 60.0),
    ("riser lifts off", (RISER,), "z", 60.0),
    ("carrier lifts off the pins", (CARRIER, HUB_PIN, RISER, FEED_LEVER), "z", 190.0),
    ("hub pin presses out down", (HUB_PIN,), "z", -150.0),
    ("pivot blocks lift off", (PIVOT_BLOCK, PIVOT_PIN, NUT_BRACKET), "z", 60.0),
    ("pivot pins press out up", (PIVOT_PIN,), "z", 60.0),
)


def explode_lift(family: str) -> float:
    """``family``'s total exploded displacement along machine Z (mm, signed)."""
    return sum(d for _label, families, _axis, d in EXPLODE_STEPS if family in families)


# The isometric looks down along (-1, +1, -1): a part under the lifted carrier
# shows below it only where its gap to the underside exceeds its plan
# distance to the carrier's -Y edge (a 45° sight line). A1/B1 stand on the
# pin line, 45 from that edge; the HUB pin stands HUB's Y from it.
_CARRIER_UNDERSIDE_EXPLODED = trammel.CARRIER_UNDERSIDE_Z + explode_lift(CARRIER)
if (
    _CARRIER_UNDERSIDE_EXPLODED - (PIN_TOP_Z + explode_lift(PIVOT_PIN))
    <= -carrier.OUTLINE_Y[0]
):
    raise AssertionError("the exploded carrier hides the pivot pins")
if (
    _CARRIER_UNDERSIDE_EXPLODED - (HUB_PIN_TOP_Z + explode_lift(HUB_PIN))
    <= trammel.HUB[1] - carrier.OUTLINE_Y[0]
):
    raise AssertionError("the exploded carrier hides the HUB pin")
if PIN_BOTTOM_Z + explode_lift(PIVOT_PIN) <= (
    trammel.PIVOT_BLOCK_TOP_Z + explode_lift(PIVOT_BLOCK)
):
    raise AssertionError("the exploded pivot pins do not clear their blocks")
# The riser must clear the HUB pin's locator before it moves sideways.
if explode_lift(RISER) - explode_lift(CARRIER) <= HUB_PIN_TOP_Z - trammel.CARRIER_TOP_Z:
    raise AssertionError("the exploded riser does not clear the HUB pin")
EXPLODED_CAPTION = "EXPLODED VIEW - ASSEMBLY SEQUENCE ON SHEET 3"

# --- Drawing views, named in the machine frame -------------------------------------
# SolidWorks' standard views assume a Y-up model; the jig is Z-up. The builder
# names these orientations on the assembly (``IModelView.Orientation3`` then
# ``NameView``, the ``_named_views`` recipe) and the drawing places them by
# name and proves each mapping. Rows: the sheet's right, the sheet's up and
# the line of sight toward the viewer, in machine coordinates.
PLAN_VIEW = "JIG PLAN"
ELEVATION_VIEW = "JIG ELEVATION"
ISOMETRIC_VIEW = "ISO JIG FRONT-TOP-RIGHT"  # "ISO " marks a pictorial (_drawing_common)
_R2, _R3, _R6 = math.sqrt(2.0), math.sqrt(3.0), math.sqrt(6.0)
VIEW_AXES: dict[str, Rows] = {
    PLAN_VIEW: ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
    # The operator's side (-Y), +Z up.
    ELEVATION_VIEW: ((1.0, 0.0, 0.0), (0.0, 0.0, 1.0), (0.0, -1.0, 0.0)),
    # From the operator's front-right, above; +Z straight up the sheet.
    ISOMETRIC_VIEW: (
        (1.0 / _R2, 1.0 / _R2, 0.0),
        (-1.0 / _R6, 1.0 / _R6, 2.0 / _R6),
        (1.0 / _R3, -1.0 / _R3, 1.0 / _R3),
    ),
}
for _name, (_right, _up, _sight) in VIEW_AXES.items():
    _cross = (
        _right[1] * _up[2] - _right[2] * _up[1],
        _right[2] * _up[0] - _right[0] * _up[2],
        _right[0] * _up[1] - _right[1] * _up[0],
    )
    _dots = [
        sum(a * b for a, b in zip(u, v))
        for u in (_right, _up, _sight)
        for v in (_right, _up, _sight)
    ]
    if (
        max(abs(a - b) for a, b in zip(_cross, _sight)) > 1e-12
        or max(
            abs(d - e)
            for d, e in zip(_dots, (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0))
        )
        > 1e-12
    ):
        raise AssertionError(f"{_name}: not a right-handed orthonormal frame")
PLAN_VIEW_LABEL = "PLAN, FROM ABOVE"
ELEVATION_VIEW_LABEL = "ELEVATION FROM THE OPERATOR SIDE (-Y)"


# --- Sheet 1 plan tags ---------------------------------------------------------------
# Each tag's text, the machine point its leader touches and the machine XY of
# the text's top-left corner, laid out for 1:4: a character is about 11.6
# and a line 18 machine mm there. A1-B2 tag the carrier's pass holes (the
# pins in A1/B1), clear of its edges; each rail tag points at its rail's
# axis on the bar, below the bar (the feed is on rail 1's column side); the
# origin tag stands under the carrier, right of the feed lever.
@dataclass(frozen=True)
class PlanTag:
    text: str
    tip: Point3
    text_xy: tuple[float, float]


TAG_GAP = 15.0  # machine mm from an edge to a tag's text
_TAG_CHAR = 11.6
_TAG_LINE = 18.0


def _hole_tag(name: str) -> PlanTag:
    x, y = trammel.PIN_HOLES[name]
    tip = _at((x, y), trammel.CARRIER_TOP_Z)
    if name.endswith("1"):  # the inner pair on the pin line: tag below the front edge
        text_y = _at((x, carrier.OUTLINE_Y[0]), 0.0)[1] - TAG_GAP
    else:  # the outer pair: tag above the back edge
        text_y = _at((x, carrier.OUTLINE_Y[1]), 0.0)[1] + TAG_GAP + _TAG_LINE
    return PlanTag(name, tip, (tip[0] - len(name) * _TAG_CHAR / 2.0, text_y))


RAIL_TAG_S = 380.0  # past the carrier's end and the pivot block, short of the bar's


def _rail_tag(rail: int) -> PlanTag:
    text = f"RAIL {rail} ({'-' if rail == 1 else '+'}X)"
    x, y = trammel.rail_point(rail, RAIL_TAG_S)
    _x, low = trammel.rail_point(rail, RAIL_TAG_S, -base_bar.HALF_WIDTH)
    return PlanTag(
        text,
        (x, y, trammel.BASE_BAR_THICK),
        (x - len(text) * _TAG_CHAR / 2.0, low - TAG_GAP),
    )


# The origin tag stands in the rail 2 tag's column, under it, two lines
# clear: the layout audit reads two blocks stacked closer than its 6.15 mm
# row pitch (1:4) as one, and jig-r7 printed them 3.15 apart.
TAG_STACK_GAP = 2.0 * _TAG_LINE
ORIGIN_TAG = PlanTag(
    "SPINDLE ORIGIN: X 0, Y 0\n+Y UP THE SHEET, TOWARD THE COLUMN",
    (0.0, 0.0, trammel.CARRIER_TOP_Z),
    (40.0, _rail_tag(2).text_xy[1] - _TAG_LINE - TAG_STACK_GAP),
)
PLAN_TAGS: tuple[PlanTag, ...] = (
    *(_hole_tag(name) for name in ("A1", "B1", "A2", "B2")),
    _rail_tag(1),
    _rail_tag(2),
    ORIGIN_TAG,
)

# --- Fitter package text -------------------------------------------------------------
# The rails are set by indicating a pin in each pivot block; the carrier holds
# its own pin spacing to ±POSITION_BAND, the same band the readings use.
ALIGNMENT_BAND = carrier.POSITION_BAND
ASSEMBLED_CAPTION = (
    "INNER PASS AT THE SYMMETRIC POSITION: CARRIER ON A1/B1 (THE OUTER PASS "
    "PUTS A2/B2 ON THE PINS). MACHINE FRAME: ORIGIN ON THE SPINDLE AT THE "
    "TABLE TOP, +Y TOWARD THE COLUMN."
)


def _alignment_rows() -> tuple[str, ...]:
    rows = []
    for station, pins in trammel.ALIGNMENT_TARGETS.items():
        (x1, y1), (x2, y2) = pins["rail 1"], pins["rail 2"]
        rows.append(
            f"S {station:5.1f}: RAIL 1 X {x1:8.3f} Y {y1:8.3f}; "
            f"RAIL 2 X {x2:8.3f} Y {y2:8.3f}"
        )
    return tuple(rows)


ALIGNMENT_NOTE_LINES = (
    "RAIL ALIGNMENT TARGETS: PIVOT PIN AXIS, MACHINE X/Y FROM THE SPINDLE, "
    f"AT STATION S FROM THE SPINDLE ALONG THE RAIL (±{ALIGNMENT_BAND:.2f})",
    *_alignment_rows(),
)

# Every screw by its fastener-table callout (fasteners.FASTENERS).
_RAIL_SCREW = fasteners.callout(fasteners.RAIL_TO_BAR)
_BAR_SCREW = fasteners.callout(fasteners.BRACKET_TO_BAR)
_BLOCK_SCREW = fasteners.callout(fasteners.NUT_BRACKET_TO_BLOCK)
_CARRIAGE_SCREW = fasteners.callout(fasteners.BLOCK_TO_CARRIAGE)
_KP08_SCREW = fasteners.callout(fasteners.KP08_TO_BRACKET)
_NUT_SCREW = fasteners.callout(fasteners.NUT_TO_NUT_BRACKET)
_RISER_SCREW = fasteners.callout(fasteners.RISER_TO_CARRIER)
_LEVER_SCREW = fasteners.callout(fasteners.LEVER_TO_CARRIER)


def _limits(nominal: float, band: tuple[float, float], places: int) -> str:
    """``low/high`` of ``nominal`` and its ``(upper, lower)`` deviation band."""
    upper, lower = band
    return f"{nominal + lower:.{places}f}/{nominal + upper:.{places}f}"


# Step 10 states the two finished holes itself (TL-21 prints only their
# centre-drill spots): the HUB hole's H7 is the HUB pin's press fit, the CL
# hole's N7 the bought m6 dowel's.
_HUB_HOLE = (
    f"HUB Ø{hub_pin.FIT_DIA:.2f} H7 "
    f"({_limits(hub_pin.FIT_DIA, hub_pin.HUB_HOLE_BAND, 3)}) THRU, FOR THE HUB "
    "LOCATOR PIN"
)
_CL_HOLE = (
    f"CL Ø{carrier.CL_DOWEL_DIA:.0f} N7 "
    f"({_limits(carrier.CL_DOWEL_DIA, carrier.CL_HOLE_BAND, 3)}) THRU, FOR THE "
    f"Ø{carrier.CL_DOWEL_DIA:.0f} X 20 M6 DOWEL "
    f"({_limits(carrier.CL_DOWEL_DIA, carrier.CL_DOWEL_BAND, 3)})"
)
ASSEMBLY_STEPS = (
    f"1. SCREW AN HGR15R RAIL ON EACH BASE BAR WITH {trammel.RAIL_HOLE_COUNT} "
    f"{_RAIL_SCREW}, ENDS FLUSH: "
    "ONE BAR AS DRAWN FOR RAIL 1 (-X SIDE), THE OTHER TURNED OVER FOR RAIL 2, "
    "ITS COUNTERBORES UP. SCREW AN END BRACKET "
    f"ON RAIL 1'S BAR AT EACH KP08 STATION WITH 2 {_BAR_SCREW} UP FROM THE "
    "BAR'S UNDERSIDE.",
    "2. SET BOTH BARS ON THE TABLE, NEAR ENDS TOWARD THE SPINDLE, EACH HELD BY "
    "TWO HOLD-DOWNS IN THE OUTER T-SLOTS ON "
    f"{fasteners.HOLD_DOWN_STUD_THREAD} X {fasteners.HOLD_DOWN_STUD_LENGTH} IN "
    "STUDS ONLY; ANY STUD LONGER THAN "
    f"{inch_eighths_down(STUD_LENGTH_MAX)} IN REACHES THE SWINGING CARRIER. "
    "NUTS FINGER TIGHT.",
    "3. SLIDE AN HGH15CA CARRIAGE ONTO EACH RAIL.",
    "4. PRESS TWO 6200-2RS BEARINGS INTO EACH PIVOT BLOCK, ONE FROM EACH FACE, "
    "OUTER RACES ON THE SHOULDER. PRESS A PIVOT PIN DOWN FROM THE BLOCK'S TOP "
    "FACE, BEARING END FIRST, THROUGH BOTH INNER RACES UNTIL ITS COLLAR SEATS "
    "ON THE UPPER RACE.",
    f"5. SCREW EACH BLOCK ON ITS CARRIAGE WITH 4 {_CARRIAGE_SCREW}, BORE "
    "TOWARD THE SPINDLE.",
    "6. INDICATE THE PIVOT PIN AT EACH STATION OF THE ALIGNMENT TABLE (SHEET 1) "
    "AND TAP EACH BAR TO ITS READINGS; TIGHTEN THE HOLD-DOWN NUTS AND READ "
    "AGAIN.",
    f"7. SCREW A KP08 BLOCK ON EACH END BRACKET WITH 2 {_KP08_SCREW} AND THE "
    f"FLANGED NUT ON THE NUT BRACKET WITH 4 {_NUT_SCREW}, FLANGE TOWARD THE "
    "SPINDLE, SNUG. THREAD THE LEADSCREW IN FROM THE BAR'S FAR END THROUGH "
    f"BOTH BLOCKS AND THE NUT, {leadscrew.NEAR_STUB:.0f} PAST THE NEAR "
    "BLOCK; IT TURNS FREELY. CLAMP THE BRACKET ON THE COLUMN SIDE OF RAIL "
    f"1'S PIVOT BLOCK, ITS CENTRE {nut_bracket.X_SET_MID:.2f} "
    f"±{nut_bracket.X_SET_BAND:.2f} FROM THE BLOCK'S SPINDLE END; SPOT THROUGH "
    f"THE BLOCK'S 2 Ø{pivot_block.SIDE_HOLE_DIA:.2f} SIDE HOLES ({nut_bracket.TRANSFER_PUNCH} "
    "TRANSFER PUNCH). RUN THE SCREW OUT, REMOVE THE BRACKET, DRILL AND TAP THE "
    f"SPOTS {nut_bracket.BLOCK_THREAD} PER {nut_bracket.NUMBER}; REFIT AND "
    f"BOLT IT ON WITH 2 {_BLOCK_SCREW} FROM THE FAR FACE, SNUG.",
    "8. TIGHTEN THE NUT SCREWS, THEN THE BRACKET'S BLOCK SCREWS, THEN THE KP08 "
    "SCREWS, SO THE SCREW TURNS FREELY OVER THE WHOLE TRAVEL; LOCK THE KP08 SET "
    f"SCREWS. PUSH THE HANDWHEEL ON, HUB {leadscrew.HUB_GAP:.0f} OFF THE FAR "
    "BLOCK, AND LOCK ITS SET SCREW.",
    "9. LOWER THE CARRIER PLATE ONTO THE PINS, ITS HOLES A1 AND B1 (INNER PASS, "
    "TAGGED ON SHEET 1) ON THE COLLARS.",
    "10. WITH THE CARRIER ON A1/B1, DRILL AND REAM ITS HUB AND CL HOLES OFF "
    "THEIR SPOTS (LOCATED ON MHA-CH-006-TL-21 FROM THE A1-B1 PIN AXES), EACH "
    "IN ONE SETUP SQUARE TO THE CARRIER TOP: "
    f"{_HUB_HOLE}; {_CL_HOLE}; BREAK THE HUB HOLE BELOW "
    f"{hub_pin.HUB_HOLE_UNDERSIDE_BREAK_MIN:.1f} MIN X 45°.",
    "11. CLAMP THE RISER ON THE CARRIER TOP AND SPOT ITS "
    f"{len(riser.SCREW_HOLES) + 3} HOLES ({len(riser.SCREW_HOLES)} "
    f"{riser.SCREW_SIZE} COUNTERSUNK, HUB Ø{riser.HUB_DIA:.0f}, CL DOWEL, CR SCREW "
    f"Ø{riser.CLAMP_DIA:.2f}) FROM BELOW THROUGH THE CARRIER'S FINISHED AND "
    "TAPPED HOLES; DRILL AND COUNTERSINK THEM TO "
    "MHA-CH-006-TL-24, THEN SCREW IT DOWN WITH "
    f"{len(riser.SCREW_HOLES)} {_RISER_SCREW}S. ONLY NOW PRESS "
    "THE HUB PIN UP TO ITS HEAD AND THE CL DOWEL FLUSH UNDERNEATH; FACE THE "
    f"HUB PIN'S TOP {hub_pin.LOCATOR_SET_MIN:.2f}-{hub_pin.LOCATOR_SET_MAX:.2f} "
    f"ABOVE THE RISER AND RECHAMFER IT {hub_pin.LEAD_CHAMFER:.1f} X 45° MAX.",
    f"12. BOLT THE FEED LEVER ON WITH 2 {_LEVER_SCREW}, GRIP END TOWARD THE OPERATOR.",
    "13. TO CHANGE PASS, LIFT THE CARRIER, RUN CARRIAGE 1 BY THE HANDWHEEL AND "
    "SLIDE CARRIAGE 2 UNTIL THE PINS MEET A2/B2, AND LOWER IT; THE STEP 6 "
    "READINGS STAND. SHIP ON A1/B1.",
)
# The Tr8x2 nut does not back-drive: the lever feeds (roughing) only with the
# nut bracket's block screws out; the handwheel feeds the finish pass.
ASSEMBLY_CHECKS = (
    f"CHECK: EVERY ALIGNMENT READING WITHIN ±{ALIGNMENT_BAND:.2f} OF ITS TARGET.",
    "CHECK: WITH THE NUT BRACKET'S 2 BLOCK SCREWS OUT, SWING THE CARRIER BY THE "
    "LEVER THROUGH THE WHOLE SWEEP OF EACH PASS; IT TURNS FREELY, NOTHING "
    "TOUCHES THE STUDS, NUTS OR COLUMN COVER AND BOTH CARRIAGES STAY ON THEIR "
    "RAILS.",
    "CHECK: WITH THE BLOCK SCREWS IN, THE HANDWHEEL RUNS THE SAME SWEEPS "
    "WITHOUT BINDING.",
    "CHECK: THE CARRIER SITS ON BOTH PIN COLLARS; NO PIN STANDS ABOVE ITS TOP.",
)

# --- Assembly extent at the modelled pose (sheet layout reads it) -----------------


def _bar_corners(rail: int) -> list[tuple[float, float]]:
    near, far = trammel.RAIL_NEAR_S, trammel.RAIL_FAR_S
    half = base_bar.HALF_WIDTH
    return [
        trammel.rail_point(rail, s, lat) for s in (near, far) for lat in (-half, half)
    ]


def _rect(x0: float, x1: float, y0: float, y1: float) -> list[tuple[float, float]]:
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


# Carrier-frame plan outlines of the parts riding on the carrier. The lever's
# R6 grip corners are ignored (its full rectangle is the conservative envelope).
CARRIER_OUTLINES: dict[str, list[tuple[float, float]]] = {
    "carrier": _rect(*carrier.OUTLINE_X, *carrier.OUTLINE_Y),
    "riser": _rect(
        riser.BLANK_ORIGIN[0],
        riser.BLANK_ORIGIN[0] + riser.BLANK_LENGTH,
        riser.BLANK_ORIGIN[1],
        riser.BLANK_ORIGIN[1] + riser.BLANK_WIDTH,
    ),
    "feed lever": _rect(
        -feed_lever.HOLE_Y,
        feed_lever.LEVER_WIDTH - feed_lever.HOLE_Y,
        carrier.LEVER_INNER_END_Y - feed_lever.LEVER_LENGTH,
        carrier.LEVER_INNER_END_Y,
    ),
}
# Each moving item's height, underside to top (machine Z).
MOVING_Z = {
    "carrier": (trammel.CARRIER_UNDERSIDE_Z, trammel.CARRIER_TOP_Z),
    "riser": (trammel.CARRIER_TOP_Z, trammel.CARRIER_TOP_Z + trammel.RISER_THICK),
    "feed lever": (
        trammel.CARRIER_TOP_Z,
        trammel.CARRIER_TOP_Z + feed_lever.LEVER_THICK,
    ),
    "HUB pin head": (HUB_HEAD_BOTTOM_Z, trammel.CARRIER_UNDERSIDE_Z),
    "pivot block": (trammel.CARRIAGE_TOP_Z, trammel.PIVOT_BLOCK_TOP_Z),
    "pivot pin": (PIN_BOTTOM_Z, PIN_TOP_Z),
    "carriage": (CARRIAGE_UNDERSIDE_Z, trammel.CARRIAGE_TOP_Z),
    "nut bracket": leadscrew.NUT_BRACKET_Z,  # with its nut
}
# Each fixed item's height, bottom to top (machine Z); the leadscrew feed's
# bought items are leadscrew_spec's envelopes.
FIXED_Z = {
    "base bar": (0.0, trammel.BASE_BAR_THICK),
    "rail": (trammel.RAIL_SEAT_Z, RAIL_TOP_Z),
    "flange nut": (trammel.BASE_BAR_THICK, FLANGE_NUT_TOP_Z),
    "stud": (STUD_BOTTOM_Z, STUD_TOP_Z),
    "end bracket": leadscrew.BRACKET_Z,
    "KP08": leadscrew.KP08_Z,
    "screw": leadscrew.SCREW_Z,
    "handwheel": leadscrew.HANDWHEEL_Z,
}
# Pairs that pass through each other by design: (moving family, fixed family).
THREADED = {("carriage", "rail"), ("nut bracket", "screw")}


def _model_extent() -> tuple[
    tuple[float, float], tuple[float, float], tuple[float, float]
]:
    points = [p for rail in RAILS for p in _bar_corners(rail)]
    points += [
        POSE.to_machine(p) for outline in CARRIER_OUTLINES.values() for p in outline
    ]
    points += [
        p for box in leadscrew.BRACKET_BOXES.values() for p in leadscrew.rect(*box)
    ]
    points += leadscrew.rect(
        CARRIAGE_STATION + leadscrew.NUT_BRACKET_X[0],
        CARRIAGE_STATION + leadscrew.NUT_BRACKET_X[1],
        leadscrew.BLOCK_SIDE_LATERAL,
        leadscrew.BLOCK_SIDE_LATERAL + leadscrew.NUT_BRACKET_DEPTH,
    )
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return (min(xs), max(xs)), (min(ys), max(ys)), (0.0, HUB_PIN_TOP_Z)


MODEL_EXTENT = _model_extent()

# --- Clearance check over the full sweep of both passes -------------------------
SWEEP_SAMPLES = 2001  # per pass, endpoints included: a 0.011 degree step


def sweep_thetas(pass_name: str, samples: int = SWEEP_SAMPLES) -> Iterator[float]:
    """Cutter-centre angles from -SWEEP to +SWEEP ⚙, both ends included."""
    sweep = trammel.SWEEP[pass_name]
    for index in range(samples):
        yield -sweep + 2.0 * sweep * index / (samples - 1)


def _rail_rect(
    rail: int, s0: float, s1: float, half: float
) -> list[tuple[float, float]]:
    return [
        trammel.rail_point(rail, s, lat)
        for s, lat in ((s0, -half), (s1, -half), (s1, half), (s0, half))
    ]


def carriage_stations(pass_name: str, theta: float) -> dict[int, float]:
    """Carriage-centre station on each rail (rail 1 carries pin A)."""
    s_a, s_b = trammel.pin_station(trammel.PASS_RADIUS[pass_name], theta)
    return {1: s_a - trammel.PIN_OFFSET, 2: s_b - trammel.PIN_OFFSET}


def moving_outlines(
    pass_name: str, theta: float
) -> dict[str, list[tuple[float, float]]]:
    """Machine-XY plan polygons of every moving item at one cutter angle."""
    pose = trammel.carrier_pose(pass_name, theta)
    out = {
        name: [pose.to_machine(p) for p in outline]
        for name, outline in CARRIER_OUTLINES.items()
    }
    stations = carriage_stations(pass_name, theta)
    for rail, station in stations.items():
        out[f"pivot block {rail}"] = _rail_rect(
            rail,
            station + pivot_block.BLOCK_X0,
            station + pivot_block.BLOCK_X1,
            pivot_block.BLOCK_WIDTH / 2.0,
        )
        out[f"carriage {rail}"] = _rail_rect(
            rail,
            station - trammel.CARRIAGE_LENGTH / 2.0,
            station + trammel.CARRIAGE_LENGTH / 2.0,
            trammel.CARRIAGE_WIDTH / 2.0,
        )
    out["nut bracket"] = leadscrew.rect(
        *leadscrew.nut_bracket_box(stations[leadscrew.RAIL])
    )
    return out


def pin_circles(
    pass_name: str, theta: float
) -> dict[str, tuple[tuple[float, float], float]]:
    """(machine XY centre, collar radius) of each pivot pin at one cutter angle."""
    return {
        f"pivot pin {rail}": (
            trammel.rail_point(rail, station + trammel.PIN_OFFSET),
            pivot_pin.COLLAR_DIA / 2.0,
        )
        for rail, station in carriage_stations(pass_name, theta).items()
    }


def hub_head(pass_name: str, theta: float) -> tuple[tuple[float, float], float]:
    """(machine XY centre, radius) of the HUB pin's head."""
    return trammel.carrier_pose(pass_name, theta).to_machine(
        trammel.HUB
    ), hub_pin.HEAD_DIA / 2.0


def fixed_outlines() -> dict[str, list[tuple[float, float]]]:
    """Machine-XY plan polygons of the bars and rails."""
    out = {}
    for rail in RAILS:
        out[f"base bar {rail}"] = _bar_corners(rail)
        out[f"rail {rail}"] = _rail_rect(
            rail, trammel.RAIL_NEAR_S, trammel.RAIL_FAR_S, trammel.RAIL_WIDTH / 2.0
        )
    return out


def feed_outlines() -> dict[str, list[tuple[float, float]]]:
    """Machine-XY plan boxes of the leadscrew feed's stationary items."""
    boxes = {
        **leadscrew.BRACKET_BOXES,
        **leadscrew.KP08_BOXES,
        "screw": leadscrew.SCREW_BOX,
        "handwheel": leadscrew.HANDWHEEL_BOX,
    }
    return {name: leadscrew.rect(*box) for name, box in boxes.items()}


def stud_centres() -> dict[str, tuple[float, float]]:
    """Machine XY of the four hold-down studs (near and far on each bar)."""
    return {
        f"{which} stud {rail}": trammel.rail_point(rail, s, lateral)
        for rail in RAILS
        for which, (s, lateral) in zip(("near", "far"), trammel.HOLD_DOWN_STUDS)
    }


def _family(name: str) -> str:
    for family in (*MOVING_Z, *FIXED_Z):
        if name.startswith(family):
            return family
    raise KeyError(name)


def z_span(name: str) -> tuple[float, float]:
    """Machine-Z (bottom, top) of any item the clearance check names."""
    if name.endswith("flange nut"):
        return FIXED_Z["flange nut"]
    if "stud" in name:
        return FIXED_Z["stud"]
    family = _family(name)
    return MOVING_Z[family] if family in MOVING_Z else FIXED_Z[family]


def _segment_distance(
    p: tuple[float, float], a: tuple[float, float], b: tuple[float, float]
) -> float:
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    t = max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(p[0] - ax - t * dx, p[1] - ay - t * dy)


def _inside(p: tuple[float, float], polygon: list[tuple[float, float]]) -> bool:
    """Point in a convex polygon (either winding)."""
    signs = set()
    for a, b in zip(polygon, polygon[1:] + polygon[:1]):
        cross = (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])
        if abs(cross) > 1e-12:
            signs.add(cross > 0.0)
    return len(signs) <= 1


def circle_polygon_gap(
    centre: tuple[float, float], radius: float, polygon: list[tuple[float, float]]
) -> float:
    """Plan gap from a circle to a convex polygon; negative where they overlap."""
    edge = min(
        _segment_distance(centre, a, b)
        for a, b in zip(polygon, polygon[1:] + polygon[:1])
    )
    return -edge - radius if _inside(centre, polygon) else edge - radius


def _polygons_overlap(
    a: list[tuple[float, float]], b: list[tuple[float, float]]
) -> bool:
    """Separating-axis test for two convex polygons (touching counts as apart)."""
    for polygon in (a, b):
        for p, q in zip(polygon, polygon[1:] + polygon[:1]):
            nx, ny = q[1] - p[1], p[0] - q[0]
            pa = [nx * x + ny * y for x, y in a]
            pb = [nx * x + ny * y for x, y in b]
            if max(pa) <= min(pb) or max(pb) <= min(pa):
                return False
    return True


def polygon_gap(a: list[tuple[float, float]], b: list[tuple[float, float]]) -> float:
    """Plan gap between two convex polygons; negative where they overlap."""
    edge = min(
        _segment_distance(p, u, v)
        for polygon, other in ((a, b), (b, a))
        for p in polygon
        for u, v in zip(other, other[1:] + other[:1])
    )
    return -edge if _polygons_overlap(a, b) else edge


@dataclass(frozen=True)
class ClearanceReport:
    """Every number the jig's clearance check pins (mm)."""

    cover_clearance: dict[str, float]  # item -> min gap to the column cover
    moving_x: tuple[float, float]  # machine X reached by any moving item
    moving_y: tuple[float, float]
    fixed_x: tuple[float, float]  # machine X of the bars
    fixed_y: tuple[float, float]
    bar_overhang: dict[int, float]  # rail -> its bar's far end past its table end
    carriage_margin: dict[str, tuple[float, float]]  # pass -> (near, far) on the rail
    plan_gaps: dict[tuple[str, str], float]  # height-overlapping pairs: min plan gap
    height_gaps: dict[tuple[str, str], float]  # plan-overlapping pairs: vertical gap
    table_edge_margins: dict[str, dict[str, float]]  # item -> edge -> min margin
    stud_length_max: float  # longest stud the plan-overlapping moving items clear


def _update_min(store: dict, key, value: float) -> None:
    store[key] = min(store.get(key, value), value)


def _heights_overlap(a: tuple[float, float], b: tuple[float, float]) -> bool:
    return a[0] < b[1] and b[0] < a[1]


def clearance_report(samples: int = SWEEP_SAMPLES) -> ClearanceReport:
    """Sweep both passes over ±SWEEP ⚙ and measure every clearance."""
    bars = fixed_outlines()
    feed = feed_outlines()
    fixed = {**bars, **feed}
    studs = stud_centres()
    cover: dict[str, float] = {}
    edges: dict[str, dict[str, float]] = {}
    plan_gaps: dict[tuple[str, str], float] = {}
    plan_overlap: set[tuple[str, str]] = set()
    moving_xs: list[float] = []
    moving_ys: list[float] = []
    margins: dict[str, tuple[float, float]] = {}

    def table_margins(name: str, xs: list[float], ys: list[float]) -> None:
        store = edges.setdefault(name, {})
        for edge, value in (
            ("-X end", min(xs) - TABLE_X[0]),
            ("+X end", TABLE_X[1] - max(xs)),
            ("front", min(ys) - TABLE_Y[0]),
            ("back", TABLE_Y[1] - max(ys)),
        ):
            _update_min(store, edge, value)

    def pairs(name: str, others: dict, outline=None, circle=None) -> None:
        """``name`` (a plan polygon or a (centre, radius) circle) against each
        of ``others`` (polygons): the plan gap where the heights overlap, the
        plan overlap otherwise."""
        z = z_span(name)
        for other, polygon in others.items():
            if (_family(name), _family(other)) in THREADED:
                continue  # passes through it by design
            key = (name, other)
            heights = _heights_overlap(z, z_span(other))
            if outline is not None:
                if _polygons_overlap(outline, polygon):
                    plan_overlap.add(key)
                if heights:
                    _update_min(plan_gaps, key, polygon_gap(outline, polygon))
            else:
                gap = circle_polygon_gap(*circle, polygon)
                if gap < 0.0:
                    plan_overlap.add(key)
                if heights:
                    _update_min(plan_gaps, key, gap)

    def stud_pairs(name: str, outline=None, circle=None) -> None:
        z = z_span(name)
        for stud_name, centre in studs.items():
            for part, radius in (
                ("stud", STUD_DIA / 2.0),
                ("flange nut", FLANGE_NUT_DIA / 2.0),
            ):
                key = (
                    name,
                    f"{stud_name} {part}" if part == "flange nut" else stud_name,
                )
                if outline is not None:
                    gap = circle_polygon_gap(centre, radius, outline)
                else:
                    gap = math.dist(centre, circle[0]) - radius - circle[1]
                if gap < 0.0:
                    plan_overlap.add(key)
                if _heights_overlap(z, FIXED_Z[part]):
                    _update_min(plan_gaps, key, gap)

    for pass_name in trammel.PASS_RADIUS:
        near, far = math.inf, math.inf
        for theta in sweep_thetas(pass_name, samples):
            for station in carriage_stations(pass_name, theta).values():
                near = min(near, station - trammel.CARRIAGE_S_RANGE[0])
                far = min(far, trammel.CARRIAGE_S_RANGE[1] - station)
            moving = moving_outlines(pass_name, theta)
            for name, outline in moving.items():
                xs = [p[0] for p in outline]
                ys = [p[1] for p in outline]
                moving_xs.extend((min(xs), max(xs)))
                moving_ys.extend((min(ys), max(ys)))
                _update_min(cover, name, COVER_Y - max(ys))
                table_margins(name, xs, ys)
                pairs(name, fixed, outline=outline)
                stud_pairs(name, outline=outline)
            centre, radius = hub_head(pass_name, theta)
            xs = [centre[0] - radius, centre[0] + radius]
            ys = [centre[1] - radius, centre[1] + radius]
            _update_min(cover, "HUB pin head", COVER_Y - ys[1])
            table_margins("HUB pin head", xs, ys)
            pairs("HUB pin head", fixed, circle=(centre, radius))
            stud_pairs("HUB pin head", circle=(centre, radius))
            # The nut bracket rides carriage 1 under the carrier and its parts.
            nut_bracket = {"nut bracket": moving["nut bracket"]}
            pairs(
                "nut bracket",
                {name: moving[name] for name in CARRIER_OUTLINES},
                outline=moving["nut bracket"],
            )
            pairs("HUB pin head", nut_bracket, circle=(centre, radius))
            for name, circle in pin_circles(pass_name, theta).items():
                pairs(name, {**fixed, **nut_bracket}, circle=circle)
                stud_pairs(name, circle=circle)
        margins[pass_name] = (near, far)

    # The feed's stationary items against the hold-downs, the cover and the table.
    for name, polygon in feed.items():
        xs = [p[0] for p in polygon]
        ys = [p[1] for p in polygon]
        _update_min(cover, name, COVER_Y - max(ys))
        table_margins(name, xs, ys)
        stud_pairs(name, outline=polygon)

    fixed_points = [p for polygon in bars.values() for p in polygon]
    fixed_xs = [p[0] for p in fixed_points]
    fixed_ys = [p[1] for p in fixed_points]
    for rail in RAILS:
        bar = bars[f"base bar {rail}"]
        table_margins(f"base bar {rail}", [p[0] for p in bar], [p[1] for p in bar])
    overhang = {
        rail: max(abs(p[0]) for p in bars[f"base bar {rail}"])
        - trammel.TABLE_LENGTH / 2.0
        for rail in RAILS
    }

    def vertical_gap(key: tuple[str, str]) -> float:
        a, b = z_span(key[0]), z_span(key[1])
        return max(a[0] - b[1], b[0] - a[1])

    height_gaps = {key: vertical_gap(key) for key in sorted(plan_overlap)}
    over_studs = [
        z_span(item)[0]
        for item, fixed_name in plan_overlap
        if "stud" in fixed_name and not fixed_name.endswith("flange nut")
    ]
    return ClearanceReport(
        cover_clearance=cover,
        moving_x=(min(moving_xs), max(moving_xs)),
        moving_y=(min(moving_ys), max(moving_ys)),
        fixed_x=(min(fixed_xs), max(fixed_xs)),
        fixed_y=(min(fixed_ys), max(fixed_ys)),
        bar_overhang=overhang,
        carriage_margin=margins,
        plan_gaps=plan_gaps,
        height_gaps=height_gaps,
        table_edge_margins=edges,
        stud_length_max=min(over_studs) - STUD_BOTTOM_Z if over_studs else math.inf,
    )


# --- Self-checks: the pose closes on the calculator --------------------------------
for _rail, _pin in zip(RAILS, PIVOT_PIN_ORIGINS):
    if math.dist(_pin[:2], trammel.rail_point(_rail, PIN_STATION)) > 1e-9:
        raise AssertionError(f"pivot pin on rail {_rail} is off its station")
for (_origin, _rows), _pin in zip(PIVOT_BLOCK_PLACEMENTS, PIVOT_PIN_ORIGINS):
    _bore = tuple(_origin[i] + pivot_block.BORE_X * _rows[0][i] for i in range(2))
    if math.dist(_bore, _pin[:2]) > 1e-9:
        raise AssertionError("pivot block bore is not on its pin")
if abs(PIN_TOP_Z - (trammel.CARRIER_TOP_Z - pivot_pin.CARRIER_TOP_SHORTFALL)) > 1e-9:
    raise AssertionError(
        "the pivot pin top does not sit its shortfall under the carrier top"
    )
if abs(PIN_BOTTOM_Z + pivot_pin.CARRIER_STATION - trammel.CARRIER_UNDERSIDE_Z) > 1e-9:
    raise AssertionError("the pin collar top is not the carrier's seat")
if not HUB_PIN_TOP_Z < PART_TOP_Z:
    raise AssertionError("the HUB pin stands above the strap")


def bar_point(rail: int, point: Point3) -> Point3:
    """Machine image of a base-bar part-frame ``point`` on ``rail``'s bar."""
    origin, rows = BASE_BAR_PLACEMENTS[RAILS.index(rail)]
    return tuple(
        origin[axis] + sum(point[k] * rows[k][axis] for k in range(3))
        for axis in range(3)
    )


# Each bar, as saved or turned over, lies on the table, puts its slots over
# its T-slot studs and its tapped-through rail holes on its rail's axis.
for _rail in RAILS:
    _zs = [bar_point(_rail, (0.0, 0.0, z))[2] for z in (0.0, base_bar.BAR_THICK)]
    if abs(min(_zs)) > 1e-9 or abs(max(_zs) - trammel.BASE_BAR_THICK) > 1e-9:
        raise AssertionError(f"base bar on rail {_rail} is not on the table")
    for _slot, (_s, _lateral) in zip(
        (
            (base_bar.NEAR_SLOT_X, base_bar.NEAR_SLOT_Y),
            (base_bar.FAR_SLOT_X, base_bar.FAR_SLOT_Y),
        ),
        trammel.HOLD_DOWN_STUDS,
    ):
        _at_slot = bar_point(_rail, (*_slot, 0.0))[:2]
        if math.dist(_at_slot, trammel.rail_point(_rail, _s, _lateral)) > 1e-9:
            raise AssertionError(f"base bar slot on rail {_rail} misses its stud")
    for _x in base_bar.RAIL_HOLE_X:
        _hole = bar_point(_rail, (_x, 0.0, 0.0))[:2]
        _s = trammel.RAIL_NEAR_S + _x
        if math.dist(_hole, trammel.rail_point(_rail, _s)) > 1e-9:
            raise AssertionError(f"base bar rail hole on rail {_rail} is off the rail")
if sorted(QUANTITIES) != sorted(BOM_ORDER) or set(BOM_DESCRIPTIONS) != set(BOM_ORDER):
    raise AssertionError("BOM order and descriptions must cover the inventory")
