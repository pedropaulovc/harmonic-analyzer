r"""Pure placement, BOM and clearance contract for ch-rocker-arm-tl-oblique-jig.SLDASM
(MHA-CH-06-TL-00).

Shop fixture, not a machine assembly (cad/docs/subsystem-identities.md): the
rocker arm's oblique-trammel mill jig, set up on the PM-30MV table. It never
enters the harmonic-analyzer assembly tree or a machine BOM
(``_buildgraph.is_shop_fixture``; test_part_coverage.py). Values marked ⚙ are
read from the calculator ``ch_rocker_arm_tl_oblique_trammel_spec`` (imported as
``trammel``), never retyped.

Material: see the component drawings (TL-20 to TL-26, TL-28 to TL-31) and the
bought items' (TL-VN drawings through TL-VN-76 and shared SH-VN-57).
Overall envelope at the modelled pose,
machine frame: X -507.3 (the handwheel's rim) to +463.0 (the base bars' far
column-side corners), Y -347.5 (the feed lever's grip end) to +85.8 (the
bars' near column-side corners since the 2026-10-17 1/2 x 6 widening; the
TL-28 brackets end flush with bar 1's column-side edge), Z -22.0 (the
T-nuts' feet in the table slots) to the raised feed lever screws' heads; see
``MODEL_EXTENT``.

Frame: the MACHINE frame. Origin on the spindle axis at the table top; +X along
the table, +Y toward the column, +Z up. Rotation rows follow ``_transforms``:
``rows[i]`` is the machine-frame image of the part's local axis ``i``.

Modelled pose: the symmetric inner pass (θ = 0). The carrier rides A1/B1 on
the two pivot pins, its pose ``trammel.carrier_pose("inner", 0)`` ⚙; each
pivot block stands at carriage station
``SYMMETRIC_PIN_STATION["inner"] - PIN_OFFSET`` ⚙ on its rail
(``trammel.rail_point``). Heights are the calculator's stack ⚙: base bars on
the table, carriage tops at ``CARRIAGE_TOP_Z`` 40.7, pivot blocks to 64.7, the
carrier from ``CARRIER_UNDERSIDE_Z`` 80.2 to ``CARRIER_TOP_Z`` 92.2; riser and
feed lever on the carrier top; the HUB pin's head under the carrier.

Leadscrew feed (``ch_rocker_arm_tl_vn_oblique_leadscrew_spec``, imported as
``leadscrew``): two TL-28 end brackets screwed up from bar 1's
underside carry the KP08 blocks; the TL-29 nut bracket bolts to pivot block
1's column-side face and carries the flanged nut, so it rides with carriage
1. The Tr8x2 nut does not back-drive: the TL-26 lever feeds (roughing) only
with the nut bracket's block screws out; the handwheel feeds the finish pass.

Every bought member is modelled and inserted, each family its own BOM row
(``BOM_ORDER``): the two HGR15R rails and HGH15CA carriages,
the four 6200-2RS bearings, the CL dowel, the leadscrew, its flanged nut, the
two KP08 blocks and the handwheel, the four hold-down studs with their
T-nuts and flange nuts (three configurations of shared SH-VN-57), every screw,
and the wedge-lock washer pair under each block screw's and each feed lever
screw's head. Each instance's pose is
``PLACEMENTS`` (from the part frames each part spec documents), and the BOM
rows, item numbers and descriptions are ``QUANTITIES``, ``ITEM_NUMBERS`` and
``BOM_DESCRIPTIONS``. No skid (user ruling).

Mates and the sweep: the structure is fixed; the carriages slide on their
rails and the carrier rides the two pivot pins (``PIN_MATES``: two hole-on-pin
coaxials and its top face on the ``CARRIER_TOP_Z`` datum), everything else
that moves
lock-mated to what carries it (``LOCKED_TO``, ``MOVING``). That leaves one
free DOF, carriage 1's slide (``SLIDE_KEY``), which the build records and
never drives. The build writes ``sweep_sidecar``: both passes' poses
(``sweep_poses``, the end stops at ``trammel.END_STOPS`` ⚙), which verify.py's
``pass-sweep-interference-free`` gate drives through, running SolidWorks'
own interference check at each pose against the exact press fits and thread
envelopes of ``_interference_contracts``. Discrete native poses do not prove
intersample clearance; ``capture_fixture_clearance_census`` separately records
continuous source arguments and unresolved capture/fixture pairs.

The analytic clearance check (``clearance_report``) keeps what the model
cannot show: over ``trammel.SWEEP`` ⚙ on both passes, the clearance of every
moving outline to the column's pleated cover (Y = +``THROAT_TO_COVER`` ⚙),
the machine X/Y reached, each base bar's overhang past its table end, each
carriage's margin on its rail, and every outline's margin to the four table
edges. test_ch_rocker_arm_tl_oblique_jig_assembly.py pins the numbers.

The hold-down stud envelope is an ESTIMATE, not a measurement (the
ShopTrammelInventory reply: kit ``fixtures.clamping-kit-pm-52pcck-14mm``, its
sizes not yet measured): 1/2-13 stud bottomed flush with its T-nut's foot,
the foot in the PM-30MV slot's undercut, a Ø28 x 13 flange nut on the bar.
"""

from __future__ import annotations

import math
from collections.abc import Iterator
from dataclasses import dataclass

from _printed_tolerance import printed_band_mm
import ch_rocker_arm_tl_oblique_base_bar_spec as base_bar
import ch_rocker_arm_tl_vn_oblique_bearing_spec as bearing
import ch_rocker_arm_tl_vn_oblique_block_washer_spec as block_washer
import ch_rocker_arm_tl_vn_oblique_block_screw_spec as block_screw
import ch_rocker_arm_tl_vn_oblique_bracket_screw_spec as bracket_screw
import ch_rocker_arm_tl_vn_oblique_carriage_screw_spec as carriage_screw
import ch_rocker_arm_tl_vn_oblique_carriage_spec as carriage
import ch_rocker_arm_tl_oblique_carrier_spec as carrier
import ch_rocker_arm_tl_vn_oblique_cl_dowel_spec as cl_dowel
import ch_rocker_arm_tl_vn_oblique_clamp_screw_spec as clamp_screw
import ch_rocker_arm_tl_oblique_fasteners_spec as fasteners
import ch_rocker_arm_tl_oblique_feed_lever_spec as feed_lever
import ch_rocker_arm_tl_oblique_end_bracket_spec as end_bracket
import sh_vn_clamping_kit_flange_nut_spec as flange_nut
import ch_rocker_arm_tl_vn_oblique_handwheel_spec as handwheel
import sh_vn_clamping_kit_hold_down_stud_spec as hold_down_stud
import ch_rocker_arm_tl_oblique_hub_pin_spec as hub_pin
import ch_rocker_arm_tl_vn_oblique_leadscrew_nut_spec as leadscrew_nut
import ch_rocker_arm_tl_vn_oblique_leadscrew_spec as leadscrew
import ch_rocker_arm_tl_oblique_nut_bracket_spec as nut_bracket
import ch_rocker_arm_tl_vn_oblique_leadscrew_stock_spec as leadscrew_stock
import ch_rocker_arm_tl_vn_oblique_lever_screw_spec as lever_screw
import ch_rocker_arm_tl_vn_oblique_lever_washer_spec as lever_washer
import ch_rocker_arm_tl_vn_oblique_nut_screw_spec as nut_screw
import ch_rocker_arm_tl_vn_oblique_kp08_screw_spec as kp08_screw
import ch_rocker_arm_tl_vn_oblique_pillow_block_spec as pillow_block
import ch_rocker_arm_tl_oblique_pivot_block_spec as pivot_block
import ch_rocker_arm_tl_oblique_pivot_pin_spec as pivot_pin
import ch_rocker_arm_tl_oblique_retention_spec as retention
import ch_rocker_arm_tl_oblique_tooling_clearance_spec as tooling
import ch_rocker_arm_tl_oblique_retention_hardware_spec as retention_hardware
import ch_rocker_arm_tl_oblique_pivot_cap_spec as pivot_cap
import ch_rocker_arm_tl_oblique_pivot_retainer_spec as pivot_retainer
import ch_rocker_arm_tl_vn_oblique_pivot_cap_screw_spec as cap_screw
import ch_rocker_arm_tl_vn_oblique_pivot_clevis_pin_spec as clevis_pin
import ch_rocker_arm_tl_vn_oblique_pivot_cotter_spec as pivot_cotter
import ch_rocker_arm_tl_vn_oblique_pivot_lock_wire_spec as pivot_wire
import ch_rocker_arm_tl_vn_oblique_rail_screw_spec as rail_screw
import ch_rocker_arm_tl_vn_oblique_rail_spec as guide_rail
import ch_rocker_arm_tl_vn_oblique_riser_screw_spec as riser_screw
import ch_rocker_arm_tl_oblique_riser_spec as riser
import sh_vn_clamping_kit_t_nut_spec as t_nut
import ch_rocker_arm_tl_oblique_trammel_spec as trammel

ASM_NAME = "ch-rocker-arm-tl-oblique-jig"
DRAWING_NUMBER = "MHA-CH-06-TL-00"

BASE_BAR = "ch-rocker-arm-tl-oblique-base-bar"
PIVOT_BLOCK = "ch-rocker-arm-tl-oblique-pivot-block"
PIVOT_PIN = "ch-rocker-arm-tl-oblique-pivot-pin"
PIVOT_CAP = "ch-rocker-arm-tl-oblique-pivot-cap"
PIVOT_RETAINER = "ch-rocker-arm-tl-oblique-pivot-retainer"
CARRIER = "ch-rocker-arm-tl-oblique-carrier"
RISER = "ch-rocker-arm-tl-oblique-riser"
HUB_PIN = "ch-rocker-arm-tl-oblique-hub-pin"
FEED_LEVER = "ch-rocker-arm-tl-oblique-feed-lever"
END_BRACKET = leadscrew.END_BRACKET
NUT_BRACKET = leadscrew.NUT_BRACKET
# Bought hardware (parent-scoped TL-VN and shared SH-VN-57; VN-72 retired),
# every member modelled and mated.
RAIL = "ch-rocker-arm-tl-vn-oblique-rail"
CARRIAGE = "ch-rocker-arm-tl-vn-oblique-carriage"
BEARING = "ch-rocker-arm-tl-vn-oblique-bearing"
CL_DOWEL = "ch-rocker-arm-tl-vn-oblique-cl-dowel"
LEADSCREW = "ch-rocker-arm-tl-vn-oblique-leadscrew"
LEADSCREW_NUT = "ch-rocker-arm-tl-vn-oblique-leadscrew-nut"
PILLOW_BLOCK = "ch-rocker-arm-tl-vn-oblique-pillow-block"
HANDWHEEL = "ch-rocker-arm-tl-vn-oblique-handwheel"
CLAMPING_KIT = "sh-vn-clamping-kit-hardware"
HOLD_DOWN_STUD = "sh-vn-clamping-kit-hardware--HoldDownStud"
T_NUT = "sh-vn-clamping-kit-hardware--TNut"
FLANGE_NUT = "sh-vn-clamping-kit-hardware--FlangeNut"
RAIL_SCREW = "ch-rocker-arm-tl-vn-oblique-rail-screw"
BRACKET_SCREW = "ch-rocker-arm-tl-vn-oblique-bracket-screw"
BLOCK_SCREW = "ch-rocker-arm-tl-vn-oblique-block-screw"
CARRIAGE_SCREW = "ch-rocker-arm-tl-vn-oblique-carriage-screw"
PILLOW_BLOCK_SCREW = "ch-rocker-arm-tl-vn-oblique-kp08-screw"
NUT_SCREW = "ch-rocker-arm-tl-vn-oblique-nut-screw"
RISER_SCREW = "ch-rocker-arm-tl-vn-oblique-riser-screw"
CLAMP_SCREW = "ch-rocker-arm-tl-vn-oblique-clamp-screw"
LEVER_SCREW = "ch-rocker-arm-tl-vn-oblique-lever-screw"
BLOCK_LOCK_WASHER = "ch-rocker-arm-tl-vn-oblique-block-washer"
LEVER_LOCK_WASHER = "ch-rocker-arm-tl-vn-oblique-lever-washer"
PIVOT_CAP_SCREW = "ch-rocker-arm-tl-vn-oblique-pivot-cap-screw"
PIVOT_CLEVIS_PIN = "ch-rocker-arm-tl-vn-oblique-pivot-clevis-pin"
PIVOT_COTTER = "ch-rocker-arm-tl-vn-oblique-pivot-cotter"
PIVOT_LOCK_WIRE = "ch-rocker-arm-tl-vn-oblique-pivot-lock-wire"

# Every logical component family and its count: the builder places, the explode
# moves and the drawing proves this inventory in its established item order.
# The bought counts are each member's own, never the number of purchased kits.
QUANTITIES = {
    BASE_BAR: base_bar.QUANTITY,
    CARRIER: 1,
    PIVOT_BLOCK: 2,
    PIVOT_PIN: 2,
    RISER: 1,
    HUB_PIN: 1,
    FEED_LEVER: 1,
    END_BRACKET: leadscrew.END_BRACKET_QUANTITY,
    NUT_BRACKET: leadscrew.NUT_BRACKET_QUANTITY,
    PIVOT_CAP: 2,
    PIVOT_RETAINER: 2,
    RAIL: fasteners.RAILS,
    CARRIAGE: fasteners.RAILS,
    BEARING: bearing.QUANTITY,
    CL_DOWEL: cl_dowel.QUANTITY,
    LEADSCREW: leadscrew_stock.QUANTITY,
    LEADSCREW_NUT: leadscrew_nut.QUANTITY,
    PILLOW_BLOCK: pillow_block.QUANTITY,
    HANDWHEEL: handwheel.QUANTITY,
    HOLD_DOWN_STUD: hold_down_stud.QUANTITY,
    T_NUT: t_nut.QUANTITY,
    FLANGE_NUT: flange_nut.QUANTITY,
    RAIL_SCREW: rail_screw.QUANTITY,
    BRACKET_SCREW: bracket_screw.QUANTITY,
    BLOCK_SCREW: block_screw.QUANTITY,
    CARRIAGE_SCREW: carriage_screw.QUANTITY,
    PILLOW_BLOCK_SCREW: kp08_screw.QUANTITY,
    NUT_SCREW: nut_screw.QUANTITY,
    RISER_SCREW: riser_screw.QUANTITY,
    CLAMP_SCREW: clamp_screw.QUANTITY,
    LEVER_SCREW: lever_screw.QUANTITY,
    BLOCK_LOCK_WASHER: block_washer.QUANTITY,
    LEVER_LOCK_WASHER: lever_washer.QUANTITY,
    PIVOT_CAP_SCREW: cap_screw.QUANTITY,
    PIVOT_CLEVIS_PIN: clevis_pin.QUANTITY,
    PIVOT_COTTER: pivot_cotter.QUANTITY,
    PIVOT_LOCK_WIRE: pivot_wire.QUANTITY,
}
# SolidWorks numbers a top-level BOM in FeatureManager order, so BOM_ORDER is
# the builder's insertion order (the builder asserts it) and the steps' item
# numbers (``_item``, ITEM_NUMBERS) read it (c4-r10, rule 25).
BOM_ORDER = (
    BASE_BAR,
    CARRIER,
    PIVOT_BLOCK,
    PIVOT_PIN,
    RISER,
    HUB_PIN,
    FEED_LEVER,
    END_BRACKET,
    NUT_BRACKET,
    PIVOT_CAP,
    PIVOT_RETAINER,
    RAIL,
    CARRIAGE,
    BEARING,
    CL_DOWEL,
    LEADSCREW,
    LEADSCREW_NUT,
    PILLOW_BLOCK,
    HANDWHEEL,
    HOLD_DOWN_STUD,
    T_NUT,
    FLANGE_NUT,
    RAIL_SCREW,
    BRACKET_SCREW,
    BLOCK_SCREW,
    CARRIAGE_SCREW,
    PILLOW_BLOCK_SCREW,
    NUT_SCREW,
    RISER_SCREW,
    CLAMP_SCREW,
    LEVER_SCREW,
    BLOCK_LOCK_WASHER,
    LEVER_LOCK_WASHER,
    PIVOT_CAP_SCREW,
    PIVOT_CLEVIS_PIN,
    PIVOT_COTTER,
    PIVOT_LOCK_WIRE,
)

# Logical BOM families are not filenames. The heterogeneous kit members share
# one physical producer but retain their own placement, count and native row.
KIT_IDENTITIES = {
    HOLD_DOWN_STUD: (CLAMPING_KIT, "HoldDownStud"),
    T_NUT: (CLAMPING_KIT, "TNut"),
    FLANGE_NUT: (CLAMPING_KIT, "FlangeNut"),
}
COMPONENT_IDENTITIES: dict[str, tuple[str, str | None]] = {
    family: (family, None) for family in BOM_ORDER
}
COMPONENT_IDENTITIES.update(KIT_IDENTITIES)


def component_family(native_stem: str, configuration: str) -> str:
    """Resolve a native file/member to its logical placement and BOM family.

    Callers remove only the drawing's Simplified suffix before passing the
    configuration. An unknown kit configuration must never count as a member.
    """
    matches = [
        family
        for family, (stem, member) in COMPONENT_IDENTITIES.items()
        if native_stem.casefold() == stem.casefold() and member in (None, configuration)
    ]
    if len(matches) != 1:
        raise ValueError(
            f"jig component {(native_stem, configuration)!r} has no unique family"
        )
    return matches[0]


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
HUB_PIN_TOP_Z = HUB_HEAD_BOTTOM_Z + hub_pin.OVERALL_LENGTH
PIN_TOP_Z = PIN_BOTTOM_Z + pivot_pin.OVERALL_LENGTH
PART_TOP_Z = trammel.CARRIER_TOP_Z + trammel.RISER_THICK + trammel.STRAP_THICK

# --- Hold-down studs: reworked length on the reference installed stack ------------
# PM-30MV T-slot throat/foot depths are unmeasured reference estimates owned
# by t_nut, not universal machine or delivered-kit tolerances. Procurement
# remains the kit's 3 in stock; only its unused upper end is shortened.
# The stud drawing owns the measured installed-stack acceptance after final
# nut seating: clear the moving block wing and preserve every loaded thread.
STUD_BOTTOM_Z = -(t_nut.THROAT_DEPTH + t_nut.FOOT_HEIGHT)
STUD_DIA = base_bar.HOLD_DOWN_STUD_DIA  # 1/2-13
STUD_LENGTH = fasteners.HOLD_DOWN_STUD_LENGTH_MM
STUD_TOP_Z = STUD_BOTTOM_Z + STUD_LENGTH  # 35.2 on this reference stack


# The flange nut (its spec owns the Ø and height estimates) seats on the bar top.
FLANGE_NUT_SEAT_Z = trammel.BASE_BAR_THICK

# --- Bought hardware placements ⚙ ---------------------------------------------------
# Each bought part's frame is its spec's (the *_spec.py docstrings). A placement
# is (machine origin, rows), rows[i] the machine image of local axis i; hardware
# seated on another part is placed in that part's frame and carried into the
# machine frame by ``compose``.
Placement = tuple[Point3, Rows]
# Axisymmetric hardware (screws, studs, nuts, bearings, the dowel) has its axis
# on local +Y: UPRIGHT puts +Y on the parent's +Z, HEAD_DOWN on its -Z.
UPRIGHT_ROWS: Rows = ((1.0, 0.0, 0.0), (0.0, 0.0, 1.0), (0.0, -1.0, 0.0))
HEAD_DOWN_ROWS: Rows = ((1.0, 0.0, 0.0), (0.0, 0.0, -1.0), (0.0, 1.0, 0.0))


def _image(rows: Rows, vector: Point3) -> Point3:
    """``vector`` in a frame with ``rows``, in the parent's axes."""
    return tuple(sum(vector[i] * rows[i][axis] for i in range(3)) for axis in range(3))


def axis_rows(x_axis: Point3, y_axis: Point3) -> Rows:
    """Right-handed rows whose local X and Y images are ``x_axis`` and ``y_axis``."""
    z_axis = (
        x_axis[1] * y_axis[2] - x_axis[2] * y_axis[1],
        x_axis[2] * y_axis[0] - x_axis[0] * y_axis[2],
        x_axis[0] * y_axis[1] - x_axis[1] * y_axis[0],
    )
    return (tuple(x_axis), tuple(y_axis), z_axis)


def compose(parent: Placement, origin: Point3, rows: Rows = IDENTITY_ROWS) -> Placement:
    """A placement given in ``parent``'s frame, carried into the machine frame."""
    base, parent_rows = parent
    offset = _image(parent_rows, origin)
    return (
        tuple(base[axis] + offset[axis] for axis in range(3)),
        tuple(_image(parent_rows, row) for row in rows),
    )


def frame_point(placement: Placement, point: Point3) -> Point3:
    """Machine image of a part-frame ``point`` of the part at ``placement``."""
    return compose(placement, point)[0]


# Hardware on the carrier turns with it.
CARRIED_ROWS = _rz(POSE.rotation, UPRIGHT_ROWS)


def _carried(point: tuple[float, float], z: float) -> Placement:
    return (_at(point, z), CARRIED_ROWS)


# Rails: on each bar's top, flush with it at RAIL_NEAR_S ⚙ (rail_spec frame:
# origin on the seat face at the near end, on the centreline). Carriages: on
# their rails at CARRIAGE_STATION ⚙ (carriage_spec frame: origin mid-length on
# the seat face), so each carriage top is its pivot block's bottom face.
RAIL_PLACEMENTS: tuple[Placement, ...] = tuple(
    (
        (*trammel.rail_point(rail, trammel.RAIL_NEAR_S), trammel.RAIL_SEAT_Z),
        rail_rows(rail),
    )
    for rail in RAILS
)
CARRIAGE_PLACEMENTS: tuple[Placement, ...] = tuple(
    (
        (*trammel.rail_point(rail, CARRIAGE_STATION), trammel.RAIL_SEAT_Z),
        rail_rows(rail),
    )
    for rail in RAILS
)
# Two bearings in each pivot block (block frame), the lower against the
# shoulder from below, the upper on it from above: block 1's lower and upper,
# then block 2's.
BEARING_SEAT_Z = (
    trammel.BEARING_RECESS,
    trammel.BEARING_RECESS + trammel.BEARING_WIDTH + trammel.BEARING_SHOULDER,
)
BEARING_PLACEMENTS: tuple[Placement, ...] = tuple(
    compose(block, (pivot_block.BORE_X, 0.0, z), UPRIGHT_ROWS)
    for block in PIVOT_BLOCK_PLACEMENTS
    for z in BEARING_SEAT_Z
)
# The CL dowel, pressed chamfered end first from the top, its round tip set
# above the riser (cl_dowel spec); its chamfered end's height follows.
CL_DOWEL_PLACEMENTS = (_carried(trammel.CL, cl_dowel.TIP_BASE_Z),)
# The leadscrew feed (leadscrew_spec): the screw from its near end and the
# handwheel from its hub end, both along rail 1 away from the spindle (local
# +Y), the handwheel's grip up (local +X).
FEED_ROWS = axis_rows((0.0, 0.0, 1.0), rail_rows(leadscrew.RAIL)[0])
# The screw turned half round its axis, its set-screw flats (local +X) down,
# to the handwheel's supplied set screw in its -X tap: step 8 turns the wheel
# to the flats (codex review: as saved, neither tap met the flat).
LEADSCREW_ROWS = axis_rows((0.0, 0.0, -1.0), rail_rows(leadscrew.RAIL)[0])
LEADSCREW_PLACEMENTS = (
    (
        (
            *leadscrew.point(leadscrew.SCREW_NEAR_END_S, leadscrew.SCREW_LATERAL),
            leadscrew.SCREW_AXIS_Z,
        ),
        LEADSCREW_ROWS,
    ),
)
HANDWHEEL_PLACEMENTS = (
    (
        (
            *leadscrew.point(leadscrew.HUB_END_S, leadscrew.SCREW_LATERAL),
            leadscrew.SCREW_AXIS_Z,
        ),
        FEED_ROWS,
    ),
)
# The flanged nut in the nut bracket's frame: its flange face on the bracket's
# spindle-side face, spigot in the counterbore, body toward the spindle (local
# +Y = the bracket's -X); each button head directly on the flange's free face
# at each hole (owner ruling 2026-10-20: no washers).
NUT_BRACKET_PLACEMENT: Placement = (NUT_BRACKET_ORIGIN, NUT_BRACKET_ROWS)
NUT_ROWS: Rows = ((0.0, 1.0, 0.0), (-1.0, 0.0, 0.0), (0.0, 0.0, 1.0))
LEADSCREW_NUT_PLACEMENTS = (
    compose(
        NUT_BRACKET_PLACEMENT,
        (leadscrew.NUT_BRACKET_X[0], *leadscrew.NUT_BORE_YZ),
        NUT_ROWS,
    ),
)
NUT_SCREW_PLACEMENTS: tuple[Placement, ...] = tuple(
    compose(
        NUT_BRACKET_PLACEMENT,
        (
            leadscrew.NUT_FLANGE_X[0],
            leadscrew.NUT_BORE_YZ[0]
            + leadscrew_nut.HOLE_PCD / 2.0 * math.cos(math.radians(angle)),
            leadscrew.NUT_BORE_YZ[1]
            + leadscrew_nut.HOLE_PCD / 2.0 * math.sin(math.radians(angle)),
        ),
        NUT_ROWS,
    )
    for angle in leadscrew_nut.HOLE_ANGLES_DEG
)
# A KP08 block on each end bracket's top over the screw axis (bracket
# frame), its two screws down through the foot.
PILLOW_BLOCK_PLACEMENTS: tuple[Placement, ...] = tuple(
    compose(
        bracket,
        (
            leadscrew.SCREW_LATERAL - leadscrew.BRACKET_INNER_LATERAL,
            0.0,
            leadscrew.BRACKET_THICK,
        ),
    )
    for bracket in END_BRACKET_PLACEMENTS
)
PILLOW_BLOCK_SCREW_PLACEMENTS: tuple[Placement, ...] = tuple(
    compose(kp08, (x, 0.0, pillow_block.FOOT_THICK), UPRIGHT_ROWS)
    for kp08 in PILLOW_BLOCK_PLACEMENTS
    for x in pillow_block.HOLE_X
)
# A hold-down at each bar slot: the stud bottomed flush with its T-nut's foot,
# the flange nut on the bar's top. Near and far on bar 1, then bar 2.
STUD_XY: tuple[tuple[float, float], ...] = tuple(
    trammel.rail_point(rail, s, lateral)
    for rail in RAILS
    for s, lateral in trammel.HOLD_DOWN_STUDS
)
HOLD_DOWN_STUD_PLACEMENTS: tuple[Placement, ...] = tuple(
    ((*xy, STUD_BOTTOM_Z), UPRIGHT_ROWS) for xy in STUD_XY
)
T_NUT_PLACEMENTS = HOLD_DOWN_STUD_PLACEMENTS  # +X along the table's T-slot
FLANGE_NUT_PLACEMENTS: tuple[Placement, ...] = tuple(
    ((*xy, FLANGE_NUT_SEAT_Z), UPRIGHT_ROWS) for xy in STUD_XY
)
# Screws, each head on its seat: rail 1's seven then rail 2's; the bracket
# screws up from bar 1's underside counterbores, near bracket first; the two
# block screws through pivot block 1 into the nut bracket; four per pivot
# block into its carriage, block 1 first; two per KP08, near first.
RAIL_SCREW_PLACEMENTS: tuple[Placement, ...] = tuple(
    compose(rail, (x, 0.0, trammel.RAIL_SCREW_SEAT_ABOVE_BASE), UPRIGHT_ROWS)
    for rail in RAIL_PLACEMENTS
    for x in guide_rail.HOLE_X
)
BRACKET_SCREW_PLACEMENTS: tuple[Placement, ...] = tuple(
    compose(
        BASE_BAR_PLACEMENTS[RAILS.index(leadscrew.RAIL)],
        (*hole, base_bar.BRACKET_CBORE_DEPTH),
        HEAD_DOWN_ROWS,
    )
    for hole in leadscrew.BASE_BAR_HOLES
)
# Each block screw's wedge-lock pair (TL-VN-70) on the floor of TL-22's
# counterbore, the screw's head on the pair: both along the block's +Y.
BLOCK_LOCK_WASHER_PLACEMENTS: tuple[Placement, ...] = tuple(
    compose(
        PIVOT_BLOCK_PLACEMENTS[RAILS.index(leadscrew.RAIL)],
        (
            x,
            -pivot_block.BLOCK_WIDTH / 2.0 + pivot_block.SIDE_UNDER_HEAD,
            pivot_block.SIDE_SCREW_Z,
        ),
    )
    for x in pivot_block.SIDE_SCREW_X
)
BLOCK_SCREW_PLACEMENTS: tuple[Placement, ...] = tuple(
    compose(
        PIVOT_BLOCK_PLACEMENTS[RAILS.index(leadscrew.RAIL)],
        (
            x,
            -pivot_block.BLOCK_WIDTH / 2.0
            + pivot_block.SIDE_UNDER_HEAD
            + block_washer.TOP_Y,
            pivot_block.SIDE_SCREW_Z,
        ),
    )
    for x in pivot_block.SIDE_SCREW_X
)
CARRIAGE_SCREW_PLACEMENTS: tuple[Placement, ...] = tuple(
    compose(block, (*point, pivot_block.CBORE_FLOOR), UPRIGHT_ROWS)
    for block in PIVOT_BLOCK_PLACEMENTS
    for point in pivot_block.BOLT_POINTS
)
# On the carrier: the riser's flat heads seated nominally 0.53 below its top,
# the CR clamp screw's head on the strap, each lever screw's wedge-lock pair
# (TL-VN-71) on the feed lever and the screw's head on the pair.
RISER_SCREW_PLACEMENTS: tuple[Placement, ...] = tuple(
    _carried(
        point,
        trammel.CARRIER_TOP_Z
        + trammel.RISER_THICK
        - riser_screw.HEAD_TOP_BELOW_RISER_TOP,
    )
    for point in trammel.RISER_SCREWS
)
CLAMP_SCREW_PLACEMENTS = (_carried(trammel.CR, PART_TOP_Z),)
LEVER_LOCK_WASHER_PLACEMENTS: tuple[Placement, ...] = tuple(
    _carried(point, trammel.CARRIER_TOP_Z + feed_lever.LEVER_THICK)
    for point in carrier.LEVER_HOLES
)
LEVER_SCREW_PLACEMENTS: tuple[Placement, ...] = tuple(
    _carried(point, trammel.CARRIER_TOP_Z + feed_lever.LEVER_THICK + lever_washer.TOP_Y)
    for point in carrier.LEVER_HOLES
)

# Positive capture stays with each cartridge, not with a removable carrier.
# Retainers are shown at their upper loaded stop: the visible gap is running
# clearance, not a clamping preload. Lock mates preserve these representative
# clearance positions without pretending a loose cross-pin is concentric.
PIVOT_CAP_PLACEMENTS: tuple[Placement, ...] = tuple(
    compose(block, (pivot_block.BORE_X, 0.0, trammel.PIVOT_BLOCK_HEIGHT))
    for block in PIVOT_BLOCK_PLACEMENTS
)
PIVOT_RETAINER_PLACEMENTS: tuple[Placement, ...] = tuple(
    (origin[:2] + (trammel.CARRIER_TOP_Z + sum(retention.TOP_RUNNING_GAP) / 2.0,), PIN_ROWS)
    for origin in PIVOT_PIN_ORIGINS
)
PIVOT_CAP_SCREW_PLACEMENTS: tuple[Placement, ...] = tuple(
    compose(cap, (x, y, retention.CAP_HEIGHT - retention.CAP_COUNTERBORE_DEPTH))
    for cap in PIVOT_CAP_PLACEMENTS
    for x, y in retention.CAP_BOLT_CENTERS
)
PIVOT_CLEVIS_HEAD_X = -13.0
PIVOT_CLEVIS_CENTRE_ABOVE_SEAT = (
    retention.PIN_CROSS_HOLE_FROM_SEAT + retention.PIN_CROSS_HOLE_DIA / 2.0
    - retention_hardware.CLEVIS_DIA / 2.0
)
PIVOT_CLEVIS_PIN_PLACEMENTS: tuple[Placement, ...] = tuple(
    compose(
        (origin, PIN_ROWS),
        (
            PIVOT_CLEVIS_HEAD_X,
            0.0,
            pivot_pin.CARRIER_STATION + PIVOT_CLEVIS_CENTRE_ABOVE_SEAT,
        ),
    )
    for origin in PIVOT_PIN_ORIGINS
)
PIVOT_COTTER_PLACEMENTS: tuple[Placement, ...] = tuple(
    compose(clevis, (retention_hardware.CLEVIS_HOLE_FROM_HEAD, 0.0, 0.0))
    for clevis in PIVOT_CLEVIS_PIN_PLACEMENTS
)
PIVOT_LOCK_WIRE_PLACEMENTS: tuple[Placement, ...] = tuple(
    compose(cap, (0.0, y, retention.CAP_HEIGHT - retention.CAP_COUNTERBORE_DEPTH))
    for cap in PIVOT_CAP_PLACEMENTS
    for y in retention.CAP_BOLT_Y_OFFSETS
)

# Every instance of every logical family, in insertion order. Ordinary families
# keep native <stem>-N names; kit instances use persisted role-local references.
PLACEMENTS: dict[str, tuple[Placement, ...]] = {
    BASE_BAR: BASE_BAR_PLACEMENTS,
    CARRIER: ((CARRIER_ORIGIN, CARRIER_ROWS),),
    PIVOT_BLOCK: PIVOT_BLOCK_PLACEMENTS,
    PIVOT_PIN: tuple((origin, PIN_ROWS) for origin in PIVOT_PIN_ORIGINS),
    RISER: ((RISER_ORIGIN, RISER_ROWS),),
    HUB_PIN: ((HUB_PIN_ORIGIN, HUB_PIN_ROWS),),
    FEED_LEVER: ((FEED_LEVER_ORIGIN, FEED_LEVER_ROWS),),
    END_BRACKET: END_BRACKET_PLACEMENTS,
    NUT_BRACKET: (NUT_BRACKET_PLACEMENT,),
    PIVOT_CAP: PIVOT_CAP_PLACEMENTS,
    PIVOT_RETAINER: PIVOT_RETAINER_PLACEMENTS,
    RAIL: RAIL_PLACEMENTS,
    CARRIAGE: CARRIAGE_PLACEMENTS,
    BEARING: BEARING_PLACEMENTS,
    CL_DOWEL: CL_DOWEL_PLACEMENTS,
    LEADSCREW: LEADSCREW_PLACEMENTS,
    LEADSCREW_NUT: LEADSCREW_NUT_PLACEMENTS,
    PILLOW_BLOCK: PILLOW_BLOCK_PLACEMENTS,
    HANDWHEEL: HANDWHEEL_PLACEMENTS,
    HOLD_DOWN_STUD: HOLD_DOWN_STUD_PLACEMENTS,
    T_NUT: T_NUT_PLACEMENTS,
    FLANGE_NUT: FLANGE_NUT_PLACEMENTS,
    RAIL_SCREW: RAIL_SCREW_PLACEMENTS,
    BRACKET_SCREW: BRACKET_SCREW_PLACEMENTS,
    BLOCK_SCREW: BLOCK_SCREW_PLACEMENTS,
    CARRIAGE_SCREW: CARRIAGE_SCREW_PLACEMENTS,
    PILLOW_BLOCK_SCREW: PILLOW_BLOCK_SCREW_PLACEMENTS,
    NUT_SCREW: NUT_SCREW_PLACEMENTS,
    RISER_SCREW: RISER_SCREW_PLACEMENTS,
    CLAMP_SCREW: CLAMP_SCREW_PLACEMENTS,
    LEVER_SCREW: LEVER_SCREW_PLACEMENTS,
    BLOCK_LOCK_WASHER: BLOCK_LOCK_WASHER_PLACEMENTS,
    LEVER_LOCK_WASHER: LEVER_LOCK_WASHER_PLACEMENTS,
    PIVOT_CAP_SCREW: PIVOT_CAP_SCREW_PLACEMENTS,
    PIVOT_CLEVIS_PIN: PIVOT_CLEVIS_PIN_PLACEMENTS,
    PIVOT_COTTER: PIVOT_COTTER_PLACEMENTS,
    PIVOT_LOCK_WIRE: PIVOT_LOCK_WIRE_PLACEMENTS,
}


def instance_name(stem: str, index: int) -> str:
    """Selector for family instance ``index`` (0-based), not a guessed kit Name2."""
    if stem in KIT_IDENTITIES:
        return f"@{KIT_IDENTITIES[stem][1]}:{index + 1}"
    return f"{stem}-{index + 1}"


KIT_COMPONENT_REFERENCES = {
    instance_name(family, index): identity
    for family, identity in KIT_IDENTITIES.items()
    for index in range(QUANTITIES[family])
}


# --- Mates ⚙ -------------------------------------------------------------------------
# One free DOF, the sweep: carriage 1's slide on rail 1, recorded (never
# authored) as the DOF manifest's SLIDE_KEY. Each carriage rides its fixed rail
# (Front and Top planes coincident); the carrier rides the two pins (two
# coaxials and its top face on the CARRIER_TOP_Z datum), which closes the loop
# through carriage 2. Everything else that moves is lock-mated to its parent;
# the rest is fixed where it is placed.
SLIDE_KEY = "carriage_slide"
SLIDE_RAIL = leadscrew.RAIL  # the rail whose carriage carries the nut bracket
# family -> (parent family, instances per parent instance): instance i locks
# to the parent's instance i // per. Parents before children.
LOCKED_TO: dict[str, tuple[str, int]] = {
    PIVOT_BLOCK: (CARRIAGE, 1),
    PIVOT_PIN: (PIVOT_BLOCK, 1),
    PIVOT_CAP: (PIVOT_BLOCK, 1),
    PIVOT_RETAINER: (PIVOT_PIN, 1),
    PIVOT_CAP_SCREW: (PIVOT_CAP, 4),
    PIVOT_CLEVIS_PIN: (PIVOT_PIN, 1),
    PIVOT_COTTER: (PIVOT_CLEVIS_PIN, 1),
    PIVOT_LOCK_WIRE: (PIVOT_CAP, 2),
    BEARING: (PIVOT_BLOCK, len(BEARING_SEAT_Z)),
    CARRIAGE_SCREW: (PIVOT_BLOCK, len(pivot_block.BOLT_POINTS)),
    NUT_BRACKET: (PIVOT_BLOCK, 1),
    BLOCK_SCREW: (PIVOT_BLOCK, len(pivot_block.SIDE_SCREW_X)),
    LEADSCREW_NUT: (NUT_BRACKET, 1),
    NUT_SCREW: (NUT_BRACKET, len(leadscrew_nut.HOLE_ANGLES_DEG)),
    RISER: (CARRIER, 1),
    RISER_SCREW: (CARRIER, len(trammel.RISER_SCREWS)),
    HUB_PIN: (CARRIER, 1),
    FEED_LEVER: (CARRIER, 1),
    LEVER_SCREW: (CARRIER, len(carrier.LEVER_HOLES)),
    CL_DOWEL: (CARRIER, 1),
    CLAMP_SCREW: (CARRIER, 1),
    BLOCK_LOCK_WASHER: (PIVOT_BLOCK, len(pivot_block.SIDE_SCREW_X)),
    LEVER_LOCK_WASHER: (CARRIER, len(carrier.LEVER_HOLES)),
}
# Every family that rides the sweep, in BOM order: the contract's allowed and
# required free stems.
MOVING = tuple(stem for stem in BOM_ORDER if stem in (CARRIAGE, CARRIER, *LOCKED_TO))


def lock_parent(stem: str, index: int) -> str:
    """The instance that ``stem``'s instance ``index`` (0-based) is locked to."""
    parent, per = LOCKED_TO[stem]
    return instance_name(parent, index // per)


# The carrier's pin mates, by pass: (mate name, carrier hole, pin instance).
# The saved model carries the inner pass; verify's sweep re-mates the outer.
PIN_MATES = {
    "inner": (("carrier A1 on pin 1", "A1", 0), ("carrier B1 on pin 2", "B1", 1)),
    "outer": (("carrier A2 on pin 1", "A2", 0), ("carrier B2 on pin 2", "B2", 1)),
}
# Each pin mate is a coincident of two named axes, the carrier hole's and the
# pin's (hidden in each part): a point pick on a hole wall depends on the
# seat's view (jig-bought-r3 picked a wrong face; test_assembly_named_selection).


def carrier_hole_axis(hole: str) -> str:
    """Carrier pin hole ``hole``'s named axis, qualified by the carrier."""
    return f"{carrier.PIN_HOLE_AXES[hole]}@{instance_name(CARRIER, 0)}"


def pin_axis(pin: int) -> str:
    """Pivot pin instance ``pin``'s (0-based) named axis, qualified by it."""
    return f"{pivot_pin.AXIS_NAME}@{instance_name(PIVOT_PIN, pin)}"


# --- Table ⚙ --------------------------------------------------------------------------
TABLE_X = (-trammel.TABLE_LENGTH / 2.0, trammel.TABLE_LENGTH / 2.0)
TABLE_Y = (
    trammel.TABLE_CENTRE_Y - trammel.TABLE_WIDTH / 2.0,
    trammel.TABLE_CENTRE_Y + trammel.TABLE_WIDTH / 2.0,
)
COVER_Y = trammel.THROAT_TO_COVER  # the column's pleated cover, 7.5 in from the spindle

# --- BOM ------------------------------------------------------------------------------
# DESCRIPTION cells, one printed line each; no vendor or brand (the yaml owns
# each source). Shared kit members use the producer's native Description authority.
# The rail is a cut-to-440 special order whose E = 40 symmetric end distance
# is an unverified vendor quote. Screws by their fastener-table callout.
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
    PIVOT_CAP: "CAPTIVE PIVOT CAP",
    PIVOT_RETAINER: "FITTED PIVOT RETAINER",
    RAIL: (
        f"HGR15R RAIL, {trammel.RAIL_LENGTH:.0f}, "
        f"E{trammel.RAIL_HOLE_END:.0f} BOTH ENDS"
    ),
    CARRIAGE: "HGH15CA CARRIAGE, Z0 PRELOAD",
    BEARING: (
        f"6200-2RS BALL BEARING {bearing.BORE:.0f} X {bearing.OD:.0f} X "
        f"{bearing.WIDTH:.0f}"
    ),
    CL_DOWEL: f"DOWEL PIN {cl_dowel.DIA:.0f} X {cl_dowel.LENGTH:.0f} M6, CL LOCATOR",
    LEADSCREW: f"TR8X2 LEADSCREW, {leadscrew_stock.LENGTH:.0f} LONG",
    LEADSCREW_NUT: "TR8X2 FLANGED NUT, BRASS",
    PILLOW_BLOCK: f"PILLOW BLOCK, {leadscrew.KP08_BORE:.0f} BORE, SET SCREWS",
    HANDWHEEL: f"HANDWHEEL {leadscrew.HANDWHEEL_WHEEL_DIA:.0f} DIA, 8 BORE",
    HOLD_DOWN_STUD: hold_down_stud.BOM_DESCRIPTION,
    T_NUT: t_nut.BOM_DESCRIPTION,
    FLANGE_NUT: flange_nut.BOM_DESCRIPTION,
    RAIL_SCREW: rail_screw.CALLOUT,
    BRACKET_SCREW: bracket_screw.CALLOUT,
    BLOCK_SCREW: block_screw.CALLOUT,
    CARRIAGE_SCREW: carriage_screw.CALLOUT,
    PILLOW_BLOCK_SCREW: kp08_screw.CALLOUT,
    NUT_SCREW: nut_screw.CALLOUT,
    RISER_SCREW: f"{riser_screw.CALLOUT} SCREW",
    CLAMP_SCREW: clamp_screw.CALLOUT,
    LEVER_SCREW: lever_screw.CALLOUT,
    BLOCK_LOCK_WASHER: f"{block_washer.SCREW_SIZE} WEDGE-LOCK WASHER PAIR",
    LEVER_LOCK_WASHER: f"{lever_washer.SCREW_SIZE} WEDGE-LOCK WASHER PAIR",
    PIVOT_CAP_SCREW: f"{cap_screw.SKU} DRILLED SHCS",
    PIVOT_CLEVIS_PIN: "3/16 HEADED CLEVIS PIN",
    PIVOT_COTTER: "1/16 X 1/2 SPLIT COTTER",
    PIVOT_LOCK_WIRE: "0.032 IN STAINLESS LOCK WIRE, FORMED",
}
# BOM item n is BOM_ORDER position n: the builder inserts each family's first
# instance in BOM_ORDER sequence (SolidWorks numbers a top-level BOM in
# FeatureManager order), and the steps cite items by these numbers.
ITEM_NUMBERS = {stem: str(index) for index, stem in enumerate(BOM_ORDER, 1)}

# --- Native explode (JIG_EXPLODED) -------------------------------------------------
# The disassembly order, ASSEMBLY_STEPS read back to front, mostly along Z so
# the exploded isometric (ISOMETRIC_VIEW, +Z up the sheet) stands the stack in
# its fitting order: base bars on the table, T-nuts dropped out beneath them
# and the flange nuts lifted off the studs; the leadscrew in its KP08 blocks
# on the brackets, the handwheel slid off its end, the bracket screws dropped
# out of bar 1's underside and the KP08 screws lifted out; the carriages over
# their rails with the rail screws lifted out between; each pivot block over
# its carriage with its bearings pressed out beneath it, its carriage screws
# and its pivot pin above it, as it is pressed in; block 1 carries the nut
# bracket and the nut, their screws backed out along the axes they are
# driven on, each block screw's wedge-lock pair halfway out to its head;
# then the carrier, its HUB pin dropped out beneath it (step 11 presses it up
# from below once the riser is down) and its CL dowel lifted out above the
# riser (step 11 presses it down through the riser), and the riser and the
# feed lever over it with their screws above them, each lever screw's
# wedge-lock pair halfway out to its head.
# Each step's families move by a signed distance along a machine
# axis; a family's displacement along an axis is the sum of the steps naming
# it (``explode_shift``; ``explode_lift`` along Z). The rail 1 axis runs
# along -X within 9 degrees, so the nut screws back out along +X and the
# handwheel slides off along -X.
# (label, families, axis, signed distance mm).
EXPLODED_VIEW_NAME = "JIG_EXPLODED"
SOURCE_CONFIGURATION = "Default"
_CARRIER_RIDERS = (
    RISER,
    RISER_SCREW,
    CLAMP_SCREW,
    FEED_LEVER,
    LEVER_SCREW,
    LEVER_LOCK_WASHER,
)
_BLOCK_RIDERS = (
    PIVOT_PIN,
    BEARING,
    CARRIAGE_SCREW,
    NUT_BRACKET,
    BLOCK_SCREW,
    LEADSCREW_NUT,
    NUT_SCREW,
    BLOCK_LOCK_WASHER,
    PIVOT_CAP,
    PIVOT_RETAINER,
    PIVOT_CAP_SCREW,
    PIVOT_CLEVIS_PIN,
    PIVOT_COTTER,
    PIVOT_LOCK_WIRE,
)
EXPLODE_STEPS = (
    ("cotters withdraw after straightening", (PIVOT_COTTER,), "y", 40.0),
    ("clevis pins withdraw", (PIVOT_CLEVIS_PIN, PIVOT_COTTER), "x", 40.0),
    (
        "top retainers lift clear",
        (PIVOT_RETAINER, PIVOT_CLEVIS_PIN, PIVOT_COTTER),
        "z",
        170.0,
    ),
    ("discard lock wire", (PIVOT_LOCK_WIRE,), "y", 40.0),
    ("lock wire lifts clear", (PIVOT_LOCK_WIRE,), "z", 170.0),
    ("cap screws lift clear", (PIVOT_CAP_SCREW,), "z", 160.0),
    ("capture caps lift clear", (PIVOT_CAP,), "z", 130.0),
    ("lever screws lift out", (LEVER_SCREW,), "z", 40.0),
    ("lever wedge-lock pairs lift out", (LEVER_LOCK_WASHER,), "z", 20.0),
    (
        "feed lever lifts off",
        (FEED_LEVER, LEVER_SCREW, LEVER_LOCK_WASHER),
        "z",
        60.0,
    ),
    ("clamp screw lifts out", (CLAMP_SCREW,), "z", 40.0),
    ("riser screws lift out", (RISER_SCREW,), "z", 30.0),
    ("riser lifts off", (RISER, RISER_SCREW, CLAMP_SCREW), "z", 60.0),
    (
        "carrier lifts off the pins",
        (CARRIER, HUB_PIN, CL_DOWEL, *_CARRIER_RIDERS),
        "z",
        230.0,
    ),
    ("hub pin presses out down", (HUB_PIN,), "z", -150.0),
    # The dowel goes in from above, down through the riser (step 11), so it
    # lifts out as the clamp screw does, clear above the lifted riser.
    ("cl dowel lifts out", (CL_DOWEL,), "z", 100.0),
    ("nut screws back out", (NUT_SCREW,), "x", 30.0),
    ("block screws back out", (BLOCK_SCREW,), "y", -40.0),
    ("wedge-lock pairs back out", (BLOCK_LOCK_WASHER,), "y", -20.0),
    ("pivot blocks lift off", (PIVOT_BLOCK, *_BLOCK_RIDERS), "z", 90.0),
    ("carriage screws lift out", (CARRIAGE_SCREW,), "z", 60.0),
    ("pivot pins press out up", (PIVOT_PIN,), "z", 60.0),
    ("bearings press out down", (BEARING,), "z", -35.0),
    ("carriages lift off the rails", (CARRIAGE,), "z", 50.0),
    ("rail screws lift out", (RAIL_SCREW,), "z", 35.0),
    ("handwheel slides off", (HANDWHEEL,), "x", -50.0),
    ("kp08 screws lift out", (PILLOW_BLOCK_SCREW,), "z", 40.0),
    ("bracket screws drop out", (BRACKET_SCREW,), "z", -40.0),
    ("flange nuts lift off", (FLANGE_NUT,), "z", 60.0),
    ("t-nuts drop out", (T_NUT,), "z", -30.0),
)
# Shown where they are fitted: the table-side structure and the feed's
# stationary parts every exploded item is read against.
EXPLODE_STATIC = (
    BASE_BAR,
    END_BRACKET,
    RAIL,
    LEADSCREW,
    PILLOW_BLOCK,
    HOLD_DOWN_STUD,
)


def explode_shift(family: str, axis: str) -> float:
    """``family``'s total exploded displacement along machine ``axis`` (mm, signed)."""
    return sum(
        d
        for _label, families, step_axis, d in EXPLODE_STEPS
        if step_axis == axis and family in families
    )


def explode_lift(family: str) -> float:
    """``family``'s total exploded displacement along machine Z (mm, signed)."""
    return explode_shift(family, "z")


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
_moved = {
    family for _label, families, _axis, _d in EXPLODE_STEPS for family in families
}
if _moved & set(EXPLODE_STATIC) or _moved | set(EXPLODE_STATIC) != set(BOM_ORDER):
    raise AssertionError("every family is exploded or deliberately static, not both")
# Each pivot block's stack reads apart: carriage, its rail screws under it,
# the bearings between it and the lifted block.
_CARRIAGE_TOP_EXPLODED = trammel.CARRIAGE_TOP_Z + explode_lift(CARRIAGE)
if not (
    _CARRIAGE_TOP_EXPLODED
    < PIN_BOTTOM_Z + explode_lift(BEARING)
    < BEARING_SEAT_Z[1]
    + trammel.BEARING_WIDTH
    + trammel.CARRIAGE_TOP_Z
    + explode_lift(BEARING)
    < trammel.CARRIAGE_TOP_Z + explode_lift(PIVOT_BLOCK)
):
    raise AssertionError(
        "the exploded bearings do not stand between carriage and block"
    )
_RAIL_SCREW_TOP_EXPLODED = RAIL_TOP_Z + explode_lift(RAIL_SCREW)
if _RAIL_SCREW_TOP_EXPLODED > CARRIAGE_UNDERSIDE_Z + explode_lift(CARRIAGE):
    raise AssertionError("the exploded rail screws stand inside the carriages")
# Each exploded sheet's cross-reference, after its cluster's title; the
# drawing fills in the fitted scale and its own sheet numbers.
EXPLODED_CAPTION = (
    "EXPLODED {scale} - BOM ON SHEET {bom_sheet}, "
    "ASSEMBLY SEQUENCE ON SHEET {steps_sheet}"
)

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

# --- CL dowel tip setting (sheet 1 elevation, native REFERENCE) -------------------
# The CL dowel's round tip above the riser top: a hidden construction line on
# the assembly Top plane (machine X-Z, the plane the operator's elevation
# looks at) up the dowel axis, from the riser top to the modelled round tip.
# Its length is the nominal cl_dowel.TIP_HEIGHT the model is placed at; the
# fitter sets the tip TIP_SET_MIN..TIP_SET_MAX above the ACTUAL riser (step
# 11), so the elevation prints it as a reference, parenthesised, no band.
CL_TIP_FEATURE = "ClTipSetting"
CL_TIP_DIMENSION = "ClTipAboveRiser"
CL_TIP_PRECISION = 1
CL_TIP_RISER_TOP_Z = trammel.CARRIER_TOP_Z + trammel.RISER_THICK
# The round tip: the dowel's local +Y end (cl_dowel frame) in the machine frame.
_CL_TIP = frame_point(CL_DOWEL_PLACEMENTS[0], (0.0, cl_dowel.LENGTH, 0.0))
# Machine (X, Z) of the line's riser-top end, then its tip end.
CL_TIP_LINE = ((_CL_TIP[0], CL_TIP_RISER_TOP_Z), (_CL_TIP[0], _CL_TIP[2]))
# The builder marks exactly these for the drawing, at these places.
DRAWING_DIMENSIONS: dict[str, set[str]] = {CL_TIP_FEATURE: {CL_TIP_DIMENSION}}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    CL_TIP_FEATURE: {CL_TIP_DIMENSION: CL_TIP_PRECISION}
}
if abs(_CL_TIP[2] - CL_TIP_RISER_TOP_Z - cl_dowel.TIP_HEIGHT) > 1e-9:
    raise AssertionError(
        "the modelled CL tip does not stand TIP_HEIGHT above the riser"
    )
if not cl_dowel.TIP_SET_MIN <= cl_dowel.TIP_HEIGHT <= cl_dowel.TIP_SET_MAX:
    raise AssertionError("the CL tip reference lies outside the fitter's setting band")


# --- Sheet 1 plan tags ---------------------------------------------------------------
# Each tag's text, the machine point its leader touches and the machine XY of
# the text's top-left corner, laid out for 1:4: a character is about 11.6
# and a line 18 machine mm there. A1-B2 tag the carrier's pass holes (the
# pins in A1/B1), clear of its edges and the bars'; each rail tag points at
# its rail's axis on the bar, below the bar (the feed is on rail 1's column
# side); the origin tag stands under the carrier, right of the feed lever.
@dataclass(frozen=True)
class PlanTag:
    text: str
    tip: Point3
    text_xy: tuple[float, float]


TAG_GAP = 15.0  # machine mm from an edge to a tag's text
_TAG_CHAR = 11.6
_TAG_LINE = 18.0


def _bar_edge_y(rail: int, lateral: float, x: float) -> float:
    """Machine Y of bar ``rail``'s edge at ``lateral`` where it crosses X ``x``."""
    (x0, y0), (x1, y1) = (trammel.rail_point(rail, s, lateral) for s in (0.0, 1.0))
    return y0 + (x - x0) / (x1 - x0) * (y1 - y0)


def _hole_tag(name: str) -> PlanTag:
    x, y = trammel.PIN_HOLES[name]
    tip = _at((x, y), trammel.CARRIER_TOP_Z)
    left = tip[0] - len(name) * _TAG_CHAR / 2.0
    span = (left, left + len(name) * _TAG_CHAR)
    if name.endswith("1"):  # the inner pair on the pin line: tag below the front edge
        # c3-r6 (rule 14): the 1/2 x 6 bar's operator-side edge runs under
        # the carrier's front edge there and struck the text, so the tag also
        # stands TAG_GAP below that edge, under the text's whole span.
        rail = 1 if name.startswith("A") else 2
        edge = min(
            _bar_edge_y(rail, trammel.BASE_BAR_OPERATOR_EDGE, end) for end in span
        )
        front = _at((x, carrier.OUTLINE_Y[0]), 0.0)[1]
        text_y = min(front, edge) - TAG_GAP
    else:  # the outer pair: tag above the back edge
        text_y = _at((x, carrier.OUTLINE_Y[1]), 0.0)[1] + TAG_GAP + _TAG_LINE
    return PlanTag(name, tip, (left, text_y))


RAIL_TAG_S = 380.0  # past the carrier's end and the pivot block, short of the bar's


def _rail_tag(rail: int) -> PlanTag:
    text = f"RAIL {rail} ({'-' if rail == 1 else '+'}X)"
    x, y = trammel.rail_point(rail, RAIL_TAG_S)
    # Below the bar's operator-side edge, its own calculator edge since the
    # 2026-10-17 widening put the rail off the bar's centreline.
    _x, low = trammel.rail_point(rail, RAIL_TAG_S, trammel.BASE_BAR_OPERATOR_EDGE)
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
    "INNER PASS AT THE SYMMETRIC POSITION: A1/B1; OUTER PASS: A2/B2. BOTH "
    "TOP RETAINERS MUST BE LOCKED IN EITHER PASS. PIN ENDS STAND "
    f"{retention.PIN_PROJECTION_ABOVE_WORK_NOMINAL:.1f} mm ABOVE THE WORK "
    "NOMINALLY. CAPTURE IS NOT COLLISION PROOF: ACCEPT THE INSTALLED "
    "TOOLHOLDER/SPINDLE ENVELOPE INCLUDING UPSET BEFORE USE. MACHINE "
    "ORIGIN: SPINDLE AT TABLE TOP; +Y TOWARD COLUMN."
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


def _sweep_line() -> str:
    # Review bought-tl000-r1: the checks' "sweep of each pass" gets its range,
    # each pin's station over ±trammel.SWEEP, rounded outward.
    spans = ", ".join(
        f"{name.upper()} {math.floor(lo):.0f} TO {math.ceil(hi):.0f}"
        for name, (lo, hi) in trammel.PIN_TRAVEL.items()
    )
    return (
        f"SWEEP OF EACH PASS, EACH PIN AT S: {spans}; NO STOP LIMITS IT, THE "
        "FITTER ENDS EACH PASS THERE."
    )


ALIGNMENT_NOTE_LINES = (
    "RAIL ALIGNMENT TARGETS: PIVOT PIN AXIS, MACHINE X/Y FROM THE SPINDLE, "
    f"AT STATION S FROM THE SPINDLE ALONG THE RAIL (±{ALIGNMENT_BAND:.2f})",
    *_alignment_rows(),
)
SWEEP_NOTE_LINE = _sweep_line()

# Every screw by its fastener-table callout (fasteners.FASTENERS) and every
# bought item by its BOM item number.
_RAIL_SCREW = fasteners.callout(fasteners.RAIL_TO_BAR)
_BAR_SCREW = fasteners.callout(fasteners.BRACKET_TO_BAR)
_BLOCK_SCREW = fasteners.callout(fasteners.NUT_BRACKET_TO_BLOCK)
_CARRIAGE_SCREW = fasteners.callout(fasteners.BLOCK_TO_CARRIAGE)
_KP08_SCREW = fasteners.callout(fasteners.KP08_TO_BRACKET)
_NUT_SCREW = fasteners.callout(fasteners.NUT_TO_NUT_BRACKET)
_RISER_SCREW = fasteners.callout(fasteners.RISER_TO_CARRIER)
_CLAMP_SCREW = fasteners.callout(fasteners.CR_CLAMP)
_LEVER_SCREW = fasteners.callout(fasteners.LEVER_TO_CARRIER)

# --- The nut bracket's block screws: their tightening torque -------------------------
# Rule 23 (review bought-r6): the 2 #8-32 block screws carry the leadscrew's
# reversing thrust into pivot block 1. Wedge-lock pairs under the heads keep
# them from backing off. Preload, by friction between the bracket and block
# faces, carries the thrust; the TL-29 aluminium thread's engagement caps the
# preload, and the cap sets the one torque that steps 7 and 13 print.
# Thrust: a firm one-hand crank on the handwheel grip (DECIDED 70 N at the
# grip offset, 1.0 N·m) through the Tr8x2 screw's efficiency, steel on the
# oiled brass nut.
_CRANK_FORCE_N = 70.0  # DECIDED: a firm one-hand pull on the grip
_CRANK_TORQUE_NM = _CRANK_FORCE_N * leadscrew.HANDWHEEL_GRIP_OFFSET / 1000.0
_TR_FLANK_HALF_ANGLE = math.radians(15.0)  # STANDARD: ISO 2903 30° Tr thread
_TR_PITCH_DIA = leadscrew_stock.MAJOR_DIA - 0.5 * leadscrew_stock.PITCH  # ISO 2904 d2
_NUT_THREAD_FRICTION = (
    0.15  # SOURCED: Machinery's Handbook, steel on oiled bronze/brass
)
_LEAD_ANGLE = math.atan(leadscrew_stock.LEAD / (math.pi * _TR_PITCH_DIA))
_FRICTION_ANGLE = math.atan(_NUT_THREAD_FRICTION / math.cos(_TR_FLANK_HALF_ANGLE))
_SCREW_EFFICIENCY = math.tan(_LEAD_ANGLE) / math.tan(_LEAD_ANGLE + _FRICTION_ANGLE)
FEED_THRUST_N = (
    2.0
    * math.pi
    * _CRANK_TORQUE_NM
    * _SCREW_EFFICIENCY
    / (leadscrew_stock.LEAD / 1000.0)
)  # 1161
# The engaged TL-29 thread's strip load at the worst-case (shortest)
# engagement: shear area ~0.75 pi D Le for an internal thread (Machinery's
# Handbook approximation), 6061-T6 shear ultimate 207 MPa (SOURCED: ASM /
# MatWeb 6061-T6). The preload stays a third of it.
_AL_SHEAR_ULTIMATE_MPA = 207.0
_STRIP_SAFETY = 3.0
_BLOCK_THREAD_STRIP_N = (
    0.75
    * math.pi
    * fasteners.NUT_BRACKET_TO_BLOCK.major_mm
    * block_washer.ENGAGEMENT_MIN
    * _AL_SHEAR_ULTIMATE_MPA
)
# T = K F d: nut factor 0.20 for the black-oxide screws in their as-supplied
# oil (Shigley's torque factors: 0.18 lubricated, 0.30 dry black finish).
_NUT_FACTOR = 0.20
BLOCK_SCREW_TORQUE_NM = (
    math.floor(
        10.0
        * _NUT_FACTOR
        * (_BLOCK_THREAD_STRIP_N / _STRIP_SAFETY)
        * fasteners.NUT_BRACKET_TO_BLOCK.major_mm
        / 1000.0
    )
    / 10.0
)  # rounded down to 0.1 N·m
BLOCK_SCREW_PRELOAD_N = BLOCK_SCREW_TORQUE_NM / (
    _NUT_FACTOR * fasteners.NUT_BRACKET_TO_BLOCK.major_mm / 1000.0
)
# The bracket-to-block faces (6061 on 6061, oiled): slip friction 0.2, taken
# deliberately low for clean machined aluminium faces.
_FACE_SLIP_FRICTION = 0.20
BLOCK_JOINT_SLIP_N = (
    fasteners.NUT_BRACKET_TO_BLOCK.count * BLOCK_SCREW_PRELOAD_N * _FACE_SLIP_FRICTION
)
if not BLOCK_JOINT_SLIP_N >= 1.25 * FEED_THRUST_N:
    raise ValueError(
        f"block screws at {BLOCK_SCREW_TORQUE_NM} N·m hold {BLOCK_JOINT_SLIP_N:.0f} N "
        f"by friction, under 1.25 x the {FEED_THRUST_N:.0f} N feed thrust"
    )

# --- The nut screws: their torque; the nut's flange a static clamp ---------------
# LOAD_CASES: the 4 #4-40 screws clamp the Tr8 nut's brass flange to TL-29.
# The nut's reaction to the screw's turning reverses with the handwheel; the
# flange's clamp friction carries it with margin, so the flange never slips
# and no operating torque reaches the screws: a static clamp (rule 23's last
# bullet). The owner ruled the static clamp on the M3 joint (2026-10-17,
# TL-00 review jbf-r17) and accepted it again for the #4-40 joint (issue
# #1630, 2026-10-19; the jig's exception RV-01): no lock. Each head is a
# #4-40 button head (owner ruling 2026-10-20: button heads, no washers),
# bearing directly on the brass flange beside the nut's Ø10.2 body.
# Engagement: rule 18's worst-case full thread in TL-29's tap
# (leadscrew.NUT_SCREW_FULL_THREAD_MIN).
_NUT_SCREW_STRIP_N = (
    0.75
    * math.pi
    * fasteners.NUT_TO_NUT_BRACKET.major_mm
    * leadscrew.NUT_SCREW_FULL_THREAD_MIN
    * _AL_SHEAR_ULTIMATE_MPA
)
# The head bears on the brass flange round its Ø3.5 hole. The vendor gives
# no temper, so the softest: C36000 free-cutting brass, O60 soft anneal,
# yield 18 ksi = 124 MPa (SOURCED: Copper Development Association C36000
# data). The ring on the brass is the largest one concentric with the hole
# inside the head's least diameter (ASME B18.3 Table 11 A min), the head
# off the hole by its runout to the shank (FIM, so half of it) and the
# shank off the hole by the spot drill's float in it (the TL-29 tap is
# spotted through the hole); the hole at its nominal: the vendor gives it no
# band (UNVERIFIED), and a larger hole shrinks the ring.
_BRASS_YIELD_MPA = 124.0
_NUT_HEAD_OFFSET = nut_screw.HEAD_RUNOUT_FIM / 2.0 + nut_bracket.NUT_SPOT_FLOAT
_NUT_SCREW_BEARING_OD = nut_screw.HEAD_DIA_MIN - 2.0 * _NUT_HEAD_OFFSET  # 4.857
_NUT_SCREW_FLANGE_BEARING_MM2 = (
    math.pi / 4.0 * (_NUT_SCREW_BEARING_OD**2 - leadscrew_nut.HOLE_DIA**2)
)  # 8.90
_NUT_SCREW_PRELOAD_CAP_N = min(
    _NUT_SCREW_STRIP_N / _STRIP_SAFETY,
    _BRASS_YIELD_MPA * _NUT_SCREW_FLANGE_BEARING_MM2,
)
# The owner's torque (2026-10-19, issue #1630, kept 2026-10-20): 0.4 N·m.
NUT_SCREW_TORQUE_NM = 0.4
NUT_SCREW_PRELOAD_N = NUT_SCREW_TORQUE_NM / (
    _NUT_FACTOR * fasteners.NUT_TO_NUT_BRACKET.major_mm / 1000.0
)  # 703
NUT_SCREW_FLANGE_BEARING_MPA = NUT_SCREW_PRELOAD_N / _NUT_SCREW_FLANGE_BEARING_MM2
if NUT_SCREW_PRELOAD_N > _NUT_SCREW_PRELOAD_CAP_N:
    raise ValueError(
        f"nut screws at {NUT_SCREW_TORQUE_NM} N·m preload {NUT_SCREW_PRELOAD_N:.0f} N, "
        f"over the {_NUT_SCREW_PRELOAD_CAP_N:.0f} N the tap and the brass carry"
    )
# The screw: the preload's stress on the #4-40 tensile stress area
# (0.00604 in², ASME B1.1) stays under half the alloy steel socket screw's
# 120,000 psi (SOURCED: Reli-Tool's 91255A110 cross-reference listing, ASTM
# F835).
_NUT_SCREW_STRESS_AREA_MM2 = 0.00604 * trammel.INCH**2
_F835_TENSILE_MPA = 120_000.0 * 0.006894757
if not NUT_SCREW_PRELOAD_N / _NUT_SCREW_STRESS_AREA_MM2 < 0.5 * _F835_TENSILE_MPA:
    raise ValueError(f"nut screw preload {NUT_SCREW_PRELOAD_N:.0f} N overloads it")
# The head seats flat: its underhead fillet (B18.3 F max) stays inside the
# flange's hole with the shank off it by the spot's float, and the head's
# largest diameter, off the hole by its runout and that float, clears the
# nut's Ø10.2 body. Both at the nut's nominal: its tolerances are
# unpublished (UNVERIFIED), so neither is a worst-case certification.
NUT_SCREW_FILLET_MARGIN = (
    leadscrew_nut.HOLE_DIA / 2.0
    - nut_screw.FILLET_DIA_MAX / 2.0
    - nut_bracket.NUT_SPOT_FLOAT
)  # 0.051
NUT_SCREW_HEAD_TO_BODY = (
    leadscrew_nut.HOLE_PCD / 2.0
    - leadscrew_nut.BODY_DIA / 2.0
    - nut_screw.DIMS.head_dia / 2.0
    - _NUT_HEAD_OFFSET
)  # 0.070
if not (NUT_SCREW_FILLET_MARGIN > 0.0 and NUT_SCREW_HEAD_TO_BODY > 0.0):
    raise ValueError("a nut screw's button head does not seat flat on the flange")
# The nut's torque at the 1 kN hand-abuse thrust (leadscrew LOAD_CASES):
# T = F d2/2 tan(lead + friction), the oiled thread above.
NUT_ABUSE_TORQUE_NM = (
    leadscrew.HAND_ABUSE_THRUST
    * _TR_PITCH_DIA
    / 2000.0
    * math.tan(_LEAD_ANGLE + _FRICTION_ANGLE)
)
# The flange's slip torque: the screws' clamp at the Ø16 circle, brass on
# as-machined 6061, μ 0.15 .. 0.20.
_FLANGE_SLIP_FRICTION = (0.15, 0.20)
NUT_FLANGE_SLIP_NM = tuple(
    fasteners.NUT_TO_NUT_BRACKET.count
    * NUT_SCREW_PRELOAD_N
    * friction
    * leadscrew_nut.HOLE_PCD
    / 2000.0
    for friction in _FLANGE_SLIP_FRICTION
)
NUT_FLANGE_SLIP_MARGIN = NUT_FLANGE_SLIP_NM[0] / NUT_ABUSE_TORQUE_NM
if NUT_FLANGE_SLIP_MARGIN < leadscrew.SLIP_MARGIN_MIN:
    raise ValueError(
        f"the nut flange slips at {NUT_FLANGE_SLIP_NM[0]:.1f} N·m, under "
        f"{leadscrew.SLIP_MARGIN_MIN} x the nut's {NUT_ABUSE_TORQUE_NM:.2f} N·m"
    )
_NUT_TORQUE = f"{NUT_SCREW_TORQUE_NM:.1f} N·m"

# Step 7C's nut bracket set (owner ruling 2026-10-17, review jbf-r17, rules
# 4/17): TL-29 cannot grow (FEED_GAP, its 3/4 stock), so 7C prints the
# centre at the bracket's three places, the title block's .XXX band, with its
# reason and no explicit band; TL-29 self-checks each #8 tap's end wall at
# that band (END_WALL_MIN 1.544), and the jig's exception RV-02 states it.

# --- The feed lever screws: their tightening torque -----------------------------------
# Rule 23 (C3 r6 TL-00 review): the 2 5/16-18 lever screws carry the
# operator's push and pull on the TL-26 lever, reversing through every pass.
# Wedge-lock pairs (TL-VN-71) under the heads keep them from backing off. The
# torque takes the block screws' basis: the TL-21 6061-T651 tap's strip load
# at the worst-case engagement (lever_washer.ENGAGEMENT_MIN 9.14: the
# shortest screw through the thickest lever and pair, inside the 12 plate's
# RV-01 1.20D full thread), a third of it as preload, T = K F d.
_LEVER_THREAD_STRIP_N = (
    0.75
    * math.pi
    * fasteners.LEVER_TO_CARRIER.major_mm
    * lever_washer.ENGAGEMENT_MIN
    * _AL_SHEAR_ULTIMATE_MPA
)
LEVER_SCREW_TORQUE_NM = (
    math.floor(
        10.0
        * _NUT_FACTOR
        * (_LEVER_THREAD_STRIP_N / _STRIP_SAFETY)
        * fasteners.LEVER_TO_CARRIER.major_mm
        / 1000.0
    )
    / 10.0
)  # rounded down to 0.1 N·m
LEVER_SCREW_PRELOAD_N = LEVER_SCREW_TORQUE_NM / (
    _NUT_FACTOR * fasteners.LEVER_TO_CARRIER.major_mm / 1000.0
)
# The pair bears on the 6061-T6 lever over the ring outside the drilled hole,
# less its worst-case overhang past the lever's inner end
# (lever_washer.BEARING_AREA_MIN): under the 6061-T6 yield, 276 MPa (SOURCED:
# ASM / MatWeb 6061-T6), taken as the compressive yield.
_AL_YIELD_MPA = 276.0
LEVER_PAIR_BEARING_MPA = LEVER_SCREW_PRELOAD_N / lever_washer.BEARING_AREA_MIN
if not LEVER_PAIR_BEARING_MPA < _AL_YIELD_MPA:
    raise ValueError(
        f"lever screws at {LEVER_SCREW_TORQUE_NM} N·m press the pair on the "
        f"lever at {LEVER_PAIR_BEARING_MPA:.0f} MPa, over 6061-T6's yield"
    )
# The screw: the preload's stress on the 5/16-18 tensile stress area
# (0.0524 in², ASME B1.1) stays under half the A574 screw's 170,000 psi.
_LEVER_STRESS_AREA_MM2 = 0.0524 * trammel.INCH**2
_A574_TENSILE_MPA = 170_000.0 * 0.006894757
if not LEVER_SCREW_PRELOAD_N / _LEVER_STRESS_AREA_MM2 < 0.5 * _A574_TENSILE_MPA:
    raise ValueError(f"lever screw preload {LEVER_SCREW_PRELOAD_N:.0f} N overloads it")
_LEVER_TORQUE = f"{LEVER_SCREW_TORQUE_NM:.1f} N·m"
_BLOCK_TORQUE = f"{BLOCK_SCREW_TORQUE_NM:.1f} N·m"


def _item(stem: str) -> str:
    """``stem``'s BOM item citation, ``(ITEM n)``."""
    return f"(ITEM {ITEM_NUMBERS[stem]})"


def _limits(nominal: float, band: tuple[float, float], places: int) -> str:
    """``low/high`` of ``nominal`` and its ``(upper, lower)`` deviation band."""
    upper, lower = band
    return f"{nominal + lower:.{places}f}/{nominal + upper:.{places}f}"


# Step 10 states the two finished holes itself (TL-21 prints only their
# centre-drill spots): the HUB hole's H7 is the HUB pin's press fit, the CL
# hole's N7 the bought m6 dowel's. c3-r7 (rule 4): H7 alone did not read as
# a press fit, so the HUB hole names the fit, its item and the p6/H7
# interference the pin's spec derives.
_HUB_HOLE = (
    f"HUB Ø{hub_pin.FIT_DIA:.2f} H7 "
    f"({_limits(hub_pin.FIT_DIA, hub_pin.HUB_HOLE_BAND, 3)}) THRU, PRESS FIT ON "
    f"THE HUB LOCATOR PIN, ITEM {ITEM_NUMBERS[HUB_PIN]} "
    f"({hub_pin.SEAT_INTERFERENCE_MIN:.3f}-{hub_pin.SEAT_INTERFERENCE_MAX:.3f} "
    "INTERFERENCE)"
)
_CL_HOLE = (
    f"CL Ø{carrier.CL_DOWEL_DIA:.0f} N7 "
    f"({_limits(carrier.CL_DOWEL_DIA, carrier.CL_HOLE_BAND, 3)}) THRU, FOR THE "
    f"Ø{carrier.CL_DOWEL_DIA:.0f} X 20 M6 DOWEL "
    f"({_limits(carrier.CL_DOWEL_DIA, carrier.CL_DOWEL_BAND, 3)})"
)
ASSEMBLY_STEPS = (
    f"1. SCREW AN HGR15R RAIL {_item(RAIL)} ON EACH BASE BAR WITH "
    f"{trammel.RAIL_HOLE_COUNT} {_RAIL_SCREW} {_item(RAIL_SCREW)}, ENDS FLUSH: "
    # Sheet 1 tags RAIL 1 (-X); the step drops the repeat to hold sheet 6's
    # left column (7F and step 8's lock, review full-bought).
    "ONE BAR AS DRAWN FOR RAIL 1, THE OTHER TURNED OVER FOR RAIL 2, "
    "ITS COUNTERBORES UP. SCREW AN END BRACKET "
    f"{_item(END_BRACKET)} ON RAIL 1'S BAR AT EACH KP08 STATION, "
    f"{len(leadscrew.BAR_SCREW_LATERALS)} {_BAR_SCREW} "
    f"{_item(BRACKET_SCREW)} PER BRACKET FROM BELOW, "
    f"{leadscrew.BAR_SCREW_TORQUE_NM:.1f} N·m "
    f"({leadscrew.BAR_SCREW_TORQUE_IN_LBF} IN·LBF).",
    "2. SET BOTH BARS ON THE TABLE, NEAR ENDS TOWARD THE SPINDLE. USE TWO "
    f"REWORKED {fasteners.HOLD_DOWN_STUD_THREAD} STUDS {_item(HOLD_DOWN_STUD)} "
    "PER BAR IN THE OUTER T-SLOTS, IN T-NUTS "
    f"{_item(T_NUT)} UNDER FINGER-TIGHT FLANGE NUTS {_item(FLANGE_NUT)}. "
    "FOLLOW THE STUD REWORK DRAWING; KEEP ITS LOADED LOWER THREADS AND "
    "INSERTION UNCHANGED. AFTER FINAL ALIGNMENT/NUT SEATING, COMPLETE "
    "THAT DRAWING'S INSTALLED-FIT CHECK BEFORE CUTTING.",
    f"3. SLIDE A FACTORY-GREASED HGH15CA CARRIAGE {_item(CARRIAGE)} ON EACH RAIL.",
    # Review bought-r15: a pin pressed through two seated bearings loads the
    # upper one through its balls and drags the lower one off its shoulder,
    # so each press loads only the ring it fits.
    f"4. ASSEMBLE EACH PIN {_item(PIVOT_PIN)} AND BOTH BEARINGS {_item(BEARING)} "
    "PER C1-C2 (SHEET 8). TRIAL-FIT CAPS FOR C2, THEN LEAVE THEM OFF FOR "
    "FEED FIT-UP; DO NOT COMPLETE C3 YET.",
    f"5. SCREW EACH BLOCK ON ITS CARRIAGE WITH 4 {_CARRIAGE_SCREW} "
    f"{_item(CARRIAGE_SCREW)}, BORE TOWARD THE SPINDLE.",
    # Review bought-r15: the DRO reads the table, not the carriage, so the
    # step zeroes it and moves the table to each station.
    "6. ZERO THE DRO X AND Y ON THE SPINDLE ORIGIN (SHEET 1). AT EACH "
    "ALIGNMENT-TABLE STATION, RUN THE TABLE UNTIL THE DRO READS ITS X AND Y, "
    "SLIDE THE CARRIAGE UNTIL ITS PIN CENTRES IN X UNDER A SPINDLE-MOUNTED "
    "INDICATOR AND TAP THE BAR UNTIL THE PIN CENTRES IN Y; TIGHTEN THE "
    "HOLD-DOWN NUTS AND READ EACH STATION AGAIN.",
    # Review bought-r15: one operation a line, so the taps plainly go in the
    # nut bracket's spots and the pivot block's side holes stay clearance.
    # The nut stays clamped in its seat through all 4 spots, so the spigot's
    # float is one rigid shift of the pattern (nut bracket spec SPIGOT_FLOAT).
    f"7A. FIT A KP08 BLOCK {_item(PILLOW_BLOCK)} TO EACH END BRACKET: 2 "
    f"{_KP08_SCREW} {_item(PILLOW_BLOCK_SCREW)}. CLAMP NUT "
    f"{_item(LEADSCREW_NUT)} IN SEAT; SPOT ALL 4 HOLES, "
    f"{nut_bracket.NUT_SPOT_DRILL} DRILL; MARK CLOCKING, REMOVE, DRILL/TAP "
    f"PER {nut_bracket.NUMBER}; REFIT AT MARK: 4 {_NUT_SCREW} "
    f"{_item(NUT_SCREW)}, SNUG.",
    f"7B. THREAD THE LEADSCREW {_item(LEADSCREW)}, OILED WITH ISO VG 32 OIL, IN "
    "FROM THE BAR'S FAR END THROUGH BOTH BLOCKS AND THE NUT.",
    "7C. CLAMP THE NUT BRACKET ON THE COLUMN SIDE OF RAIL 1'S PIVOT BLOCK (STILL "
    f"ON ITS CARRIAGE), CENTRE {nut_bracket.X_SET_MID:.{nut_bracket.X_SET_PLACES}f} "
    "FROM "
    "THE BLOCK'S SPINDLE END (SETS #8 TAP END WALLS); CHECK F1 (SHEET 8), "
    "THEN SPOT THROUGH THE BLOCK'S 2 "
    f"Ø{pivot_block.SIDE_HOLE_DIA:.2f} SIDE HOLES ({nut_bracket.TRANSFER_PUNCH} "
    "TRANSFER PUNCH).",
    "7D. RUN THE SCREW OUT, UNCLAMP THE NUT BRACKET, DRILL AND TAP ITS 2 "
    f"SPOTS {nut_bracket.BLOCK_THREAD} PER {nut_bracket.NUMBER}; THE BLOCK'S "
    "HOLES STAY PLAIN.",
    "7E. REFIT THE NUT BRACKET FROM THE BLOCK'S FAR FACE WITH 2 "
    f"{_BLOCK_SCREW} {_item(BLOCK_SCREW)} ON WEDGE-LOCK PAIRS "
    f"{_item(BLOCK_LOCK_WASHER)}, SNUG.",
    # Review full-bought (owner ruling 2026-10-18): the screw run out at 7D
    # goes back through the nut to its working stub before step 8 tightens
    # round it (7B threads it only to locate the nut for 7C's spotting).
    "7F. RE-THREAD THE SCREW THROUGH THE NUT, "
    f"{leadscrew.NEAR_STUB:.0f} PAST THE NEAR BLOCK.",
    f"8. TIGHTEN THE NUT SCREWS TO {_NUT_TORQUE}, THE BLOCK SCREWS TO "
    f"{_BLOCK_TORQUE}, THEN THE KP08 "
    "SCREWS, SO THE SCREW TURNS FREELY OVER THE WHOLE TRAVEL. PUSH THE "
    f"HANDWHEEL {_item(HANDWHEEL)} ON, HUB {leadscrew.HUB_GAP:.0f} OFF THE FAR "
    # Owner ruling 2026-10-18 (rule 23, exception RV-03): the set screws are
    # locked with a bought low-strength threadlocker, named, not prescribed.
    "BLOCK; TIGHTEN ITS AND THE KP08 SET SCREWS ON THE SCREW'S FLATS, EACH "
    "LOCKED WITH LOW-STRENGTH (PURPLE) THREADLOCKER. THEN FOLLOW F2 (SHEET 8).",
    "9. LOWER THE CARRIER A1/B1 (INNER PASS) ONTO BOTH PIN SEATS. FIT AND "
    "LOCK BOTH TOP RETAINERS PER THE CAPTURE AND OPERATION SHEET.",
    "10. DRILL AND REAM ITS HUB AND CL HOLES OFF THEIR SPOTS (LOCATED ON "
    "MHA-CH-06-TL-21 FROM THE A1-B1 PIN AXES), EACH IN ONE SETUP SQUARE TO THE "
    "CARRIER TOP: "
    f"{_HUB_HOLE}; {_CL_HOLE}; BREAK THE HUB HOLE BELOW "
    f"{hub_pin.HUB_HOLE_UNDERSIDE_BREAK_MIN:.1f} MIN X 45°.",
    "11. CLAMP THE RISER ON THE CARRIER TOP AND SPOT ITS "
    f"{len(riser.SCREW_HOLES) + 3} HOLES ({len(riser.SCREW_HOLES)} "
    f"{riser.SCREW_SIZE} COUNTERSUNK, HUB Ø{riser.HUB_DIA:.0f}, CL DOWEL, CR SCREW "
    f"Ø{riser.CLAMP_DIA:.2f}) FROM BELOW THROUGH THE CARRIER'S FINISHED AND "
    "TAPPED HOLES; DRILL AND COUNTERSINK THEM TO "
    "MHA-CH-06-TL-24, THEN SCREW IT DOWN WITH "
    f"{len(riser.SCREW_HOLES)} {_RISER_SCREW}S {_item(RISER_SCREW)}. "
    "ONLY NOW PRESS THE HUB PIN UP TO ITS HEAD AND THE CL DOWEL "
    f"{_item(CL_DOWEL)} CHAMFERED END FIRST DOWN THROUGH THE RISER UNTIL ITS "
    f"ROUND TIP IS {cl_dowel.TIP_SET_MIN:.2f}-{cl_dowel.TIP_SET_MAX:.2f} ABOVE "
    "THE RISER; CHECK THE STRAP SEATS FLAT, LOCATES AND SLIDES ON AND OFF, AND "
    "THE TIP IS NOT ABOVE IT. "
    f"FACE THE HUB PIN'S TOP {hub_pin.LOCATOR_SET_MIN:.2f}-"
    f"{hub_pin.LOCATOR_SET_MAX:.2f} ABOVE THE RISER AND RECHAMFER IT "
    f"{hub_pin.LEAD_CHAMFER:.1f} X 45° MAX.",
    f"12. BOLT THE FEED LEVER ON THE CARRIER WITH 2 {_LEVER_SCREW} "
    f"{_item(LEVER_SCREW)} ON WEDGE-LOCK PAIRS {_item(LEVER_LOCK_WASHER)}, "
    f"TIGHTENED TO {_LEVER_TORQUE}, GRIP END TOWARD THE OPERATOR. IN USE THE "
    f"{_CLAMP_SCREW} {_item(CLAMP_SCREW)} GOES DOWN THROUGH THE WORKPIECE, "
    f"THE {carrier.STRAP_NUMBER} STRAP BLANK (NOT SUPPLIED), AND THE RISER "
    "INTO THE CARRIER'S CR TAP.",
    "13. TO CHANGE PASS, ISOLATE THE SPINDLE, WITHDRAW THE TOOL, REMOVE BOTH "
    "TOP RETAINERS, THEN LIFT THE CARRIER. ALIGN A2/B2 AND LOWER; REFIT AND "
    "LOCK BOTH RETAINERS WITH NEW COTTERS BEFORE USE. THE STEP 6 READINGS "
    f"STAND. SHIP ON A1/B1, BLOCK SCREWS {_item(BLOCK_SCREW)} AT {_BLOCK_TORQUE}.",
)
# The Tr8x2 nut does not back-drive: the lever feeds (roughing) only with the
# nut bracket's block screws out; the handwheel feeds the finish pass.
ASSEMBLY_CHECKS = (
    f"CHECK: EVERY ALIGNMENT READING WITHIN ±{ALIGNMENT_BAND:.2f} OF ITS TARGET.",
    "CHECK: WITH THE 2 BLOCK SCREWS OUT, SWING THE CARRIER BY THE LEVER THROUGH "
    "EACH PASS'S SWEEP (SHEET 1); IT TURNS FREELY, CLEAR OF THE STUDS, NUTS AND "
    "COLUMN COVER, BOTH CARRIAGES ON THEIR RAILS.",
    # Review bought-tl000-r3: the check that takes the block screws out puts
    # them back to step 13's ship state.
    f"CHECK: REFIT THE BLOCK SCREWS {_item(BLOCK_SCREW)} ON THEIR WEDGE-LOCK "
    f"PAIRS AT {_BLOCK_TORQUE}; THE HANDWHEEL RUNS THE SAME SWEEPS WITHOUT "
    "BINDING.",
    "CHECK: THE CARRIER SITS ON BOTH PIN SEATS WITHOUT THE TOP RETAINERS "
    "CLAMPING IT; BOTH CLEVIS PINS HAVE NEW BENT COTTERS AND BOTH CAPS "
    "HAVE INTACT TIGHTENING-DIRECTION SAFETY WIRE.",
)

CARTRIDGE_STEPS = (
    "C1. BEFORE FINAL PRESS ASSEMBLY, MEASURE EACH ACTUAL BLOCK SHOULDER/"
    "UPPER-BEARING FACE STACK AND FIT THE PIN'S LOWER BOSS HEIGHT FOR THE "
    "C2 GAPS; DO NOT PLAN POST-PRESS MACHINING. COMPLETE C2A ON "
    "TOPCAPTUREFIT WITH THE FINAL MACHINED PARTS BEFORE PRESSING ANY "
    "BEARING. FOR EACH BLOCK, PRESS THE "
    "UPPER 6200 ON THE PIN'S LOWER JOURNAL UNTIL THE INNER RACE SEATS ON "
    "THE NARROW BOSS, DRIVING THE INNER RACE ONLY. PRESS THIS PAIR INTO "
    "THE UPPER BLOCK SEAT, DRIVING ITS OUTER RACE ONLY. SUPPORT THE PIN "
    "AND PRESS THE LOWER BEARING WITH A DRIVER ON BOTH RACES UNTIL THE "
    "OUTER RACE SEATS; DO NOT PRESS THROUGH BALLS.",
    "C2. AFTER PRESS ASSEMBLY, VERIFY THE LOWER FLANGE-RIM/FLOOR GAP "
    "0.10-0.15 AND TOTAL CHAMBER EXCESS 0.20-0.30, INCLUDING FACE VARIATION; "
    "THE UPPER GAP MUST ALSO "
    "BE 0.10-0.15. MEASURE BOTH GAPS OVER THE FULL FLANGE FACES/RIMS, NOT "
    "ONLY THE STOP CIRCLE, AND VERIFY A COMPLETE FREE PIN TURN. CONTACT "
    "LANDS MUST BE CLEAR OF SEALS. THE FLANGE RIM NORMALLY FLOATS; NO CAP, "
    "BLOCK OR RETAINER MAY DRAG THE ROTATING PIN OR CARRIER. DO NOT "
    "PRELOAD THE BEARINGS TO OBTAIN THESE GAPS.",
    f"F1. AT STEP 7C, BEFORE TRANSFER-PUNCHING, CHECK THAT BOTH ACTUAL "
    f"TL-22 SIDE-HOLE AXES ARE {nut_bracket.TRANSFER_AXIS_TOP_MIN:.1f} MIN "
    "BELOW THE TL-29 TOP. KEEP THE NUT AND SCREW IN FREE-FEED ALIGNMENT; "
    "DO NOT MOVE THEM TO PASS THIS MATERIAL CHECK.",
    f"F2. AFTER STEP 8 ALIGNMENT AND FINAL TIGHTENING, BEFORE FITTING CAPS, "
    "BRIDGE A STRAIGHTEDGE FROM THE ACTUAL TL-22 CAP MOUNTING PLANE OVER "
    f"TL-29. GAUGE {nut_bracket.BLOCK_PLANE_TOP_GAP_MIN:.2f} MIN BELOW THAT "
    "PLANE OVER THE WHOLE BRACKET TOP, INCLUDING ALL HIGH CORNERS, THROUGH "
    "FULL TRAVEL. DO NOT FORCE FEED ALIGNMENT TO OBTAIN THE GAP; RE-MACHINE "
    "OR REPLACE A FAILED BRACKET. THEN COMPLETE C3-C3C.",
    f"C3. AFTER F2 ACCEPTANCE, FIT FOUR {_item(PIVOT_CAP_SCREW)} "
    f"{retention_hardware.SCREW_SKU} SCREWS PER CAP. CLEAN/DRY THREADS AND "
    "FACES; EACH SCREW MUST FREE-RUN "
    "BEFORE SEATING, WITHOUT FILLET INTERFERENCE OR BOTTOMING. TIGHTEN "
    f"CROSSWISE TO {retention.CAP_SEATING_TORQUE_NM:.2f} +/- "
    f"{retention.CAP_SEATING_TORQUE_BAND_NM:.2f} N·m. THIS IS A SEATING "
    "INSTRUCTION, NOT A MINIMUM PRELOAD OR BUMP-LOAD RATING.",
    "C3A. WITH CAPS SEATED, REPEAT C2. BEFORE WIRING, CHECK A SEPARATE "
    "0.05 MAX CAP/BLOCK GAP AROUND "
    "THE WHOLE MOUNTING-LAND PERIMETER AND 0.05 MAX UNDER EACH HEAD OVER "
    "ITS WHOLE ACCESSIBLE BEARING FOOTPRINT. FLAT FACES MUST SEAT; "
    "REGISTERS MUST NOT BOTTOM. DO NOT PULL A GAP SHUT WITH THE SCREWS: "
    "RE-MACHINE OR REPLACE A FAILED PART. THESE TWO GAP ALLOWANCES ARE "
    "INDEPENDENT AND ARE BOTH INCLUDED IN THE UPSET BOUND.",
    "C3B. MEASURE FULL-THREAD INTERVAL [S0,S1] FROM THE SCREW UNDERHEAD, "
    "[B0,B1] DOWN FROM BLOCK TOP, AND SEATED HEAD HEIGHT H ABOVE BLOCK. "
    "ENGAGEMENT = MIN(B1,S1-H)-MAX(B0,S0-H), ALL IN MM; REQUIRE 11.91 MIN "
    "AT EVERY SCREW. CHAMFERS, RUNOUT AND TIP THREADS DO NOT COUNT.",
    f"C3C. LOCK EACH PAIR WITH NEW 0.032 STAINLESS WIRE {_item(PIVOT_LOCK_WIRE)} "
    "PULLING EACH HEAD TOWARD TIGHTENING. ROUTE SINGLE STRANDS THROUGH "
    "DRILLED HEADS; KEEP TWISTED PAIRS AND TURNED-IN TAILS IN THE CHANNELS. "
    "THREADLOCKER IS NOT THE POSITIVE LOCK.",
)

# Complete inspection ink belongs here; the drawing only places this callout.
PIN_TIP_MIN_RECESS_CALLOUT = (
    f"{retention.PIN_TIP_CARRIAGE_CLEARANCE_MIN:.2f} MIN RECESS"
)

TOP_CAPTURE_STEPS = (
    "C2A. BEFORE BEARINGS/CARRIAGE HIDE THE UNDERSIDE, BENCH-TRIAL THE "
    "FINAL PIN/BLOCK WITH THE ACTUAL CAP TEMPORARILY SEATED USING THE C3 "
    "METHOD, NO WIRE. Z=0 IS THE CARRIAGE-MOUNTING PLANE; +Z IS INTO THE "
    "BLOCK. BRIDGE ITS ACTUAL MOUNTING FACES WITH A GROUND STRAIGHTEDGE. "
    "THROUGH THE ENTIRE MECHANICALLY REACHABLE FLANGE-CAPTURE LIFT, SHIFT, "
    f"TILT AND CLOCKING, PASS A {retention.PIN_TIP_CARRIAGE_CLEARANCE_MIN:.2f} "
    "FEELER BETWEEN BRIDGE AND LOWEST PIN TIP: THE TIP MUST STAY ABOVE "
    "Z=0, INTO THE BLOCK, NOT PROTRUDE TOWARD THE CARRIAGE. VERIFY NO ACTUAL "
    "CARRIAGE FEATURE BENEATH THE PIN PROJECTS ABOVE THAT PLANE. RECORD "
    "MINIMUM RECESS WITH UNCERTAINTY AT EACH SUPPORT. DO NOT CREDIT "
    "BEARING RESTRAINT. REJECT/REFIT AND REPEAT A FAILED TRIAL; DO NOT "
    "ALTER JOURNAL OR BEARING-SEAT FITS TO RESCUE IT.",
    "C4. STOP/ISOLATE THE SPINDLE AND WITHDRAW THE CUTTER/TOOLHOLDER. "
    "BEFORE FINAL ASSEMBLY, MEASURE THE RETAINER BORES, CARRIER SUPPORT "
    "LANDS AND CLEVIS FULL-DIAMETER SHANK INTERVALS; EXCLUDE END CHAMFERS. "
    "AT BOTH EXTREMES OF CLEVIS ENDPLAY, REQUIRE MEASURABLE FULL-SECTION "
    "SHANK OVERLAP BEYOND BOTH SIDES OF EACH RETAINER BORE AND SOLID CARRIER "
    "BENEATH BOTH BEARING LANDS. RECORD THE MINIMUM OVERLAPS AFTER "
    "MEASUREMENT UNCERTAINTY; TANGENCY OR CHAMFER-ONLY SUPPORT IS A FAIL.",
    f"C4A. WITH THE CARRIER SEATED, FIT EACH RETAINER {_item(PIVOT_RETAINER)} "
    f"FROM ITS SUPPLY {retention.TOP_WASHER_SUPPLY_MIN_THICKNESS:.0f} MIN BLANK. "
    f"FACE IT TO GIVE {retention.TOP_RUNNING_GAP[0]:.2f}-"
    f"{retention.TOP_RUNNING_GAP[1]:.2f} CARRIER/TOP RETAINER RUNNING GAP "
    "AROUND THE WHOLE WASHER THROUGH THE FREE SWING, WITH THE ACTUAL CLEVIS "
    "HELD AGAINST THE UPPER EDGE OF THE PIN CROSS-HOLE, NOT CENTRED OR ON "
    "THE LOWER EDGE. RECORD FINISHED THICKNESS AND MIN/MAX GAP. KEEP ONE "
    "MATCHED SET AT EACH SUPPORT; THE SAME SET MUST QUALIFY BOTH HOLE PAIRS.",
    f"C5. INSERT BOTH HEADED CLEVIS PINS {_item(PIVOT_CLEVIS_PIN)} AND FIT NEW "
    f"SPLIT COTTERS {_item(PIVOT_COTTER)}. SPREAD BOTH LEGS TO LOCK POSITIVELY. "
    "BOTH ENDS MUST BE RETAINED DURING THE FOLLOWING HAND CHECKS. HEADS AND "
    "COTTERS RETAIN THE CLEVIS AXIALLY; DO NOT CREDIT THEM AS CARRIER "
    "UPLIFT STOPS OR FORCE THEM AGAINST THE CARRIER.",
    "C5A. USE LIGHT HAND TAKE-UP ONLY, NO HAMMER, ADDED LEVER OR PROOF LOAD. "
    "ESTABLISH PRIMARY RETAINER/CLEVIS ENGAGEMENT, NOT SECONDARY CONTACT. "
    "MEASURE THE CHANGE IN PIN PROJECTION WITH A BRIDGE INDICATOR ON "
    "EXPOSED CARRIER FACE AND ITS PROBE ON THE FLAT PIN END, ALIGNED WITH "
    "THE PIN AXIS. USE OPPOSED CARRIER CONTACTS OR AVERAGE OPPOSED READINGS "
    "TO REMOVE ROCKING BIAS. INCLUDE GAUGE/ALIGNMENT UNCERTAINTY. MAXIMUM "
    f"ACTUAL CARRIER-TO-PIN RELATIVE TRAVEL MUST BE "
    f"{retention.TOP_PRIMARY_RELATIVE_TRAVEL_MAX:.2f} OR LESS; BLOCK/CARRIAGE "
    "MOVEMENT IS NOT THIS RELATIVE TRAVEL.",
    f"C5B. AT PRIMARY TAKE-UP, PASS A "
    f"{retention.TOP_SECONDARY_CLEARANCE_MIN:.2f} FEELER BETWEEN THE CARRIER "
    "AND EVERY CLEVIS HEAD, EXPOSED SHANK END, COTTER EYE AND BOTH PRONGS/"
    "ENDS. APPROACH FROM THE OPEN CARRIER ENDS; USE A LIGHT/MIRROR TO PLACE "
    "THE FEELER AT THE CLOSEST POINT, NOT A FACE-ON VISUAL GUESS. RECORD "
    "EACH MINIMUM CLEARANCE WITH UNCERTAINTY. IF SECONDARY HARDWARE TOUCHES "
    "BEFORE PRIMARY ENGAGEMENT, STOP: THAT IS NOT A VALID TAKE-UP POSITION.",
    "C5C. REPEAT C4-C5 AT BOTH SUPPORTS ON BOTH PASS HOLE PAIRS. MOVE THROUGH "
    "ALL REACHABLE CLEVIS/COTTER ENDPLAY AND CLOCKING WHILE TAKING UP LOCAL "
    "CARRIER ROCK, INCLUDING COUPLED POSITIONS, ONE-END LIFT AND HANDLE "
    "TILT BOTH WAYS ABOUT THE SUPPORT LINE. SWEEP BOTH PASSES BY HAND. "
    "RECHECK THE TWO SHANK BRIDGES/UNDER-SUPPORTS THROUGH THIS MOTION. RECORD "
    "THE ACTUAL SECONDARY-HARDWARE XYZ ENVELOPE ABOUT EACH PIN AXIS/SEAT, "
    "USING MEASURED CARRIER THICKNESS, FOR FIXTURE AND INSTALLED-TOOLING "
    "CHECKS; NOMINAL COTTER GEOMETRY IS NOT A SUPPLIER MAXIMUM.",
    "C5D. ANY EXCESS TRAVEL, INSUFFICIENT GAP/SUPPORT OR UNINSPECTED REGION "
    "FAILS. REFIT OR REPLACE THE CORRECT PARTS AND REPEAT BOTH-PAIR "
    "QUALIFICATION. DO NOT REFORM THE COTTER EYE, ARBITRARILY RE-BEND LEGS "
    "TO GAIN CLEARANCE, FORCE A SET TOGETHER OR ACCEPT NO GAP. REPLACE "
    "REMOVED COTTERS AND KEEP THE QUALIFICATION RECORD WITH THE MATCHED SET.",
)

CAPTURE_STEPS = (
    "C6. BEFORE EITHER PASS, CHECK BOTH CAPS/WIRES, BOTH FITTED TOP "
    "RETAINERS AND BOTH BENT COTTERS. BEFORE A PASS CHANGE, STOP/ISOLATE "
    "THE SPINDLE AND WITHDRAW THE CUTTER/TOOLHOLDER; REMOVE BOTH COTTERS, "
    "CLEVIS PINS AND RETAINERS BEFORE LIFTING THE CARRIER. REFIT BOTH "
    "RETAINERS WITH NEW COTTERS AFTER LOWERING ON THE OTHER HOLE PAIR. "
    "RECHECK C4 GAPS AND REPEAT C5 QUALIFICATION BEFORE CUTTING.",
    "C7. SERVICE: REMOVE THE CAP/WIRE AND PRESS THE PIN UPWARD FROM BELOW. "
    "THE INTEGRAL FLANGE PREVENTS DOWNWARD EXTRACTION. DESTRUCTIVE REMOVAL "
    "MAY LOAD THE BALLS: REPLACE THE PIN AND BOTH 6200 BEARINGS AS A SET; "
    "DO NOT PROMISE BEARING REUSE. USE THE EXISTING PULLER CAVITY FOR A "
    "REMAINING BEARING. RE-FIT ALL GAPS AND APPLY NEW WIRE/COTTERS.",
)
CAPTURE_CHECKS = (
    "ACCEPTANCE: POSITIVE GEOMETRIC CAPTURE IS NOT A BUMP-FORCE OR "
    "STRENGTH CERTIFICATION. THE CALCULATED RIGID UPSET EXCLUDES ELASTIC "
    "DEFLECTION, DAMAGE AND LOOSE/ABSENT LOCKS. DO NOT USE IT AS A LOAD RATING.",
    "ACCEPTANCE: RECORD THE ACTUAL CUTTER STICKOUT, EVERY NON-CUTTING "
    "TOOLHOLDER/SPINDLE STEP RADIUS AND MACHINE-Z LIMIT, AND MEASUREMENT/"
    "RUNOUT UNCERTAINTIES. CHECK BOTH COMPLETE SWEEPS AND THE BOUNDED "
    "UPSET WITH THESE INSTALLED DIMENSIONS; NOMINAL CAD CLEARANCE ALONE "
    "DOES NOT ESTABLISH COLLISION SAFETY. NO INSTALLED ENVELOPE IS SUPPLIED.",
    f"ACCEPTANCE: NEW WORK HEIGHT IS {PART_TOP_Z:.1f} ABOVE THE TABLE; "
    f"PIN ENDS ARE NOMINALLY {PIN_TOP_Z:.1f}, "
    f"{retention.PIN_PROJECTION_ABOVE_WORK_NOMINAL:.1f} ABOVE THE WORK. "
    "INCLUDE THE ACTUAL RETAINERS, CLEVIS HEADS AND BENT COTTERS, NOT JUST "
    "THE PIN END, IN THE INSTALLED ENVELOPE AND CHECK IT AFTER ANY TOOL CHANGE.",
    "ACCEPTANCE: NO SKID IS FITTED. CARTRIDGE STOP FACES ARE NORMALLY CLEAR; "
    "THEY LIMIT UPSET ONLY. THE EXISTING CARRIAGE/RAIL AND TABLE ANCHORS "
    "REMAIN IN THE LOAD PATH AND REQUIRE THEIR OWN INSTALLED CONDITION CHECK.",
)

# --- Assembly extent at the modelled pose (sheet layout reads it) -----------------


def _bar_corners(rail: int) -> list[tuple[float, float]]:
    """A bar's plan corners: the operator- and column-side edges (the rail
    off the centreline since the 2026-10-17 widening) at both ends."""
    near, far = trammel.RAIL_NEAR_S, trammel.RAIL_FAR_S
    edges = (trammel.BASE_BAR_OPERATOR_EDGE, trammel.BASE_BAR_COLUMN_EDGE)
    return [trammel.rail_point(rail, s, lat) for s in (near, far) for lat in edges]


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


Box3 = tuple[tuple[float, float], tuple[float, float], tuple[float, float]]


def _box_corners(box: Box3) -> list[Point3]:
    return [(x, y, z) for x in box[0] for y in box[1] for z in box[2]]


def _axis_y_box(radius: float, bottom: float, top: float) -> Box3:
    return ((-radius, radius), (bottom, top), (-radius, radius))


def _component_local_boxes() -> dict[str, Box3]:
    """Native-source material bounds in each part's ACTUAL local frame.

    Voids/chamfers are deliberately not subtracted. Purchased dimensions with
    unknown limits remain nominal authority: the caller must include their
    measured deviations and installation uncertainty in its supplied envelope.
    Wire bounds use every cubic control point plus the swept wire radius, not
    just centreline samples. The two row pieces are combined per cap downstream.
    """
    wire_points = [point for segment in pivot_wire.installed_wire_segments() for point in segment]
    wire_radius = pivot_wire.WIRE_DIA / 2.0
    wire_box = tuple(
        (min(point[axis] for point in wire_points) - wire_radius,
         max(point[axis] for point in wire_points) + wire_radius)
        for axis in range(3)
    )
    flange_radius = pivot_pin.FLANGE_DIA / 2.0
    clevis_radius = retention_hardware.CLEVIS_HEAD_DIA_MAX / 2.0
    nut_radius = leadscrew_nut.FLANGE_DIA / 2.0
    boxes = {
        BASE_BAR: ((0.0, base_bar.BAR_LENGTH), (base_bar.LOW_SIDE_Y, base_bar.HIGH_SIDE_Y), (0.0, base_bar.BAR_THICK)),
        RAIL: ((0.0, guide_rail.LENGTH), (-guide_rail.WIDTH / 2.0, guide_rail.WIDTH / 2.0), (0.0, guide_rail.HEIGHT)),
        CARRIAGE: ((-carriage.LENGTH / 2.0 - carriage.NIPPLE_PROUD, carriage.LENGTH / 2.0 + carriage.PLUG_PROUD), (-carriage.WIDTH / 2.0, carriage.WIDTH / 2.0), (carriage.UNDERSIDE_Z, carriage.MOUNTING_FACE_Z)),
        BEARING: _axis_y_box(trammel.BEARING_OD / 2.0, 0.0, trammel.BEARING_WIDTH),
        PIVOT_BLOCK: ((pivot_block.BLOCK_X0, pivot_block.BLOCK_X1), (-retention.BLOCK_WING_HALF_WIDTH, retention.BLOCK_WING_HALF_WIDTH), (0.0, pivot_block.BLOCK_HEIGHT)),
        PIVOT_PIN: ((-flange_radius, flange_radius), (-flange_radius, flange_radius), (0.0, pivot_pin.OVERALL_LENGTH)),
        PIVOT_CAP: ((-pivot_cap.WIDTH / 2.0, pivot_cap.WIDTH / 2.0), (-pivot_cap.LENGTH / 2.0, pivot_cap.LENGTH / 2.0), (-pivot_cap.REGISTER_PROJECTION, pivot_cap.HEIGHT)),
        PIVOT_RETAINER: ((-pivot_retainer.OUTER_DIA / 2.0, pivot_retainer.OUTER_DIA / 2.0), (-pivot_retainer.OUTER_DIA / 2.0, pivot_retainer.OUTER_DIA / 2.0), (0.0, pivot_retainer.THICKNESS)),
        PIVOT_CLEVIS_PIN: ((-retention_hardware.CLEVIS_HEAD_HEIGHT_MAX, retention_hardware.CLEVIS_LENGTH_MAX), (-clevis_radius, clevis_radius), (-clevis_radius, clevis_radius)),
        PIVOT_COTTER: ((pivot_cotter.INSTALLED_X_MIN, pivot_cotter.INSTALLED_X_MAX), (-pivot_cotter.INSTALLED_Y_HALF_WIDTH, pivot_cotter.INSTALLED_Y_HALF_WIDTH), (pivot_cotter.INSTALLED_Z_MIN, pivot_cotter.INSTALLED_Z_MAX)),
        PIVOT_LOCK_WIRE: wire_box,
        CARRIER: (carrier.OUTLINE_X, (-carrier.THICKNESS, 0.0), (-carrier.OUTLINE_Y[1], -carrier.OUTLINE_Y[0])),
        RISER: ((0.0, riser.BLANK_LENGTH), (0.0, riser.BLANK_WIDTH), (0.0, riser.THICKNESS)),
        HUB_PIN: ((-hub_pin.HEAD_DIA / 2.0, hub_pin.HEAD_DIA / 2.0), (-hub_pin.HEAD_DIA / 2.0, hub_pin.HEAD_DIA / 2.0), (0.0, hub_pin.OVERALL_LENGTH)),
        FEED_LEVER: ((0.0, feed_lever.LEVER_LENGTH), (0.0, feed_lever.LEVER_THICK), (-feed_lever.LEVER_WIDTH, 0.0)),
        CL_DOWEL: _axis_y_box(cl_dowel.DIA_MAX / 2.0, 0.0, cl_dowel.LENGTH),
        END_BRACKET: ((0.0, leadscrew.BRACKET_LENGTH), (-leadscrew.BRACKET_WIDTH / 2.0, leadscrew.BRACKET_WIDTH / 2.0), (0.0, leadscrew.BRACKET_THICK)),
        NUT_BRACKET: (leadscrew.NUT_BRACKET_X, (-leadscrew.NUT_BRACKET_DEPTH, 0.0), (0.0, leadscrew.NUT_BRACKET_HEIGHT)),
        LEADSCREW: _axis_y_box(leadscrew_stock.MAJOR_DIA / 2.0, 0.0, leadscrew_stock.LENGTH),
        LEADSCREW_NUT: _axis_y_box(nut_radius, -leadscrew_nut.SPIGOT_LENGTH, leadscrew_nut.FAR_END_Y),
        PILLOW_BLOCK: ((-pillow_block.LENGTH / 2.0, pillow_block.LENGTH / 2.0), (-pillow_block.WIDTH / 2.0, pillow_block.WIDTH / 2.0), (0.0, pillow_block.HEIGHT)),
        HANDWHEEL: _axis_y_box(handwheel.SWEEP_R, 0.0, handwheel.LENGTH),
        HOLD_DOWN_STUD: _axis_y_box(hold_down_stud.RADIUS, 0.0, hold_down_stud.LENGTH),
        T_NUT: ((-t_nut.LENGTH / 2.0, t_nut.LENGTH / 2.0), (0.0, t_nut.HEIGHT), (-t_nut.FOOT_WIDTH / 2.0, t_nut.FOOT_WIDTH / 2.0)),
        FLANGE_NUT: _axis_y_box(max(flange_nut.FLANGE_DIA / 2.0, flange_nut.ACROSS_FLATS / math.sqrt(3.0)), 0.0, flange_nut.HEIGHT),
        BLOCK_LOCK_WASHER: _axis_y_box(block_washer.OD / 2.0, block_washer.BOTTOM_Y, block_washer.TOP_Y),
        LEVER_LOCK_WASHER: _axis_y_box(lever_washer.OD / 2.0, lever_washer.BOTTOM_Y, lever_washer.TOP_Y),
        RISER_SCREW: _axis_y_box(riser_screw.DIMS.head_dia / 2.0, -riser_screw.DIMS.length, 0.0),
        PIVOT_CAP_SCREW: ((-retention_hardware.SCREW_HEAD_DIA_MAX / 2.0, retention_hardware.SCREW_HEAD_DIA_MAX / 2.0), (-retention_hardware.SCREW_HEAD_DIA_MAX / 2.0, retention_hardware.SCREW_HEAD_DIA_MAX / 2.0), (-retention_hardware.SCREW_LENGTH, retention_hardware.SCREW_HEAD_HEIGHT_MAX)),
    }
    for stem, screw in (
        (RAIL_SCREW, rail_screw), (BRACKET_SCREW, bracket_screw),
        (BLOCK_SCREW, block_screw), (CARRIAGE_SCREW, carriage_screw),
        (PILLOW_BLOCK_SCREW, kp08_screw), (NUT_SCREW, nut_screw),
        (CLAMP_SCREW, clamp_screw), (LEVER_SCREW, lever_screw),
    ):
        boxes[stem] = _axis_y_box(max(screw.DIMS.head_dia, screw.DIMS.major_dia) / 2.0, -screw.DIMS.length, screw.DIMS.head_h)
    if set(boxes) != set(BOM_ORDER):
        raise ValueError("fixture envelope must cover every native BOM family")
    return boxes


def _component_label(stem: str, index: int) -> str:
    names = {
        BASE_BAR: "base bar", RAIL: "rail", CARRIAGE: "carriage",
        PIVOT_BLOCK: "pivot block", PIVOT_PIN: "pivot pin",
        PIVOT_CAP: "pivot cap", PIVOT_RETAINER: "pivot retainer",
        PIVOT_CLEVIS_PIN: "pivot clevis", PIVOT_COTTER: "pivot cotter",
        PIVOT_CAP_SCREW: "pivot cap screw", PIVOT_LOCK_WIRE: "pivot lock wire",
        CARRIER: "carrier", RISER: "riser", FEED_LEVER: "feed lever",
        HUB_PIN: "HUB pin head", CL_DOWEL: "CL dowel", BEARING: "bearing",
        NUT_BRACKET: "nut bracket", LEADSCREW_NUT: "leadscrew nut",
        LEADSCREW: "screw", HANDWHEEL: "handwheel",
        END_BRACKET: "end bracket", PILLOW_BLOCK: "pillow block",
        HOLD_DOWN_STUD: "hold-down stud", T_NUT: "T-nut", FLANGE_NUT: "flange nut",
        RAIL_SCREW: "rail screw", BRACKET_SCREW: "bracket screw",
        BLOCK_SCREW: "block screw", CARRIAGE_SCREW: "carriage screw",
        PILLOW_BLOCK_SCREW: "pillow block screw", NUT_SCREW: "nut screw",
        RISER_SCREW: "riser screw", CLAMP_SCREW: "clamp screw",
        LEVER_SCREW: "lever screw", BLOCK_LOCK_WASHER: "block lock washer",
        LEVER_LOCK_WASHER: "lever lock washer",
    }
    name = names[stem]
    return f"{name} {index + 1}" if QUANTITIES[stem] > 1 else name


def _motion_root(stem: str, index: int) -> tuple[str, int]:
    while stem in LOCKED_TO:
        stem, per = LOCKED_TO[stem]
        index //= per
    return stem, index


def _swept_placement(stem: str, index: int, pass_name: str, theta: float) -> Placement:
    """Actual authored frame: carrier branch rotates, rail branches translate."""
    placement = PLACEMENTS[stem][index]
    root, root_index = _motion_root(stem, index)
    origin, rows = placement
    if root == CARRIER:
        c, s = math.cos(POSE.rotation), math.sin(POSE.rotation)
        dx, dy = origin[0] - POSE.origin[0], origin[1] - POSE.origin[1]
        local = (c * dx + s * dy, -s * dx + c * dy)
        pose = trammel.carrier_pose(pass_name, theta)
        return ((*pose.to_machine(local), origin[2]), _rz(pose.rotation - POSE.rotation, rows))
    if root == CARRIAGE:
        rail = RAILS[root_index]
        delta = carriage_stations(pass_name, theta)[rail] - CARRIAGE_STATION
        dx, dy = rail_direction(rail)
        return ((origin[0] + delta * dx, origin[1] + delta * dy, origin[2]), rows)
    return placement


def _component_records(
    pass_name: str | None = None, theta: float = 0.0,
    boxes: dict[str, Box3] | None = None,
) -> dict[str, tuple[str, int, list[Point3]]]:
    """Complete source census; wire pieces share their cap's one hull record."""
    boxes = _component_local_boxes() if boxes is None else boxes
    records: dict[str, tuple[str, int, list[Point3]]] = {}
    for stem in BOM_ORDER:
        if pass_name is not None and stem not in MOVING:
            continue
        corners = _box_corners(boxes[stem])
        for index, placement in enumerate(PLACEMENTS[stem]):
            if pass_name is not None:
                placement = _swept_placement(stem, index, pass_name, theta)
            label_index = index // 2 if stem == PIVOT_LOCK_WIRE else index
            label = _component_label(stem, label_index)
            points = [frame_point(placement, corner) for corner in corners]
            if label in records:
                records[label][2].extend(points)
            else:
                records[label] = (stem, index, points)
    return records


def _model_extent() -> tuple[
    tuple[float, float], tuple[float, float], tuple[float, float]
]:
    points = [point for _stem, _index, corners in _component_records().values() for point in corners]
    return tuple((min(point[axis] for point in points), max(point[axis] for point in points)) for axis in range(3))


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
    pass_name: str, theta: float, *, _boxes: dict[str, Box3] | None = None,
) -> dict[str, list[tuple[float, float]]]:
    """Machine-XY plan polygons of every moving item at one cutter angle."""
    pose = trammel.carrier_pose(pass_name, theta)
    out = {
        name: [(point[0], point[1]) for point in points]
        for name, (_stem, _index, points) in _component_records(pass_name, theta, _boxes).items()
    }
    # Keep the authored concave block wing and the familiar main-body outlines;
    # the tooling report deliberately wraps these in conservative AABBs.
    out.update({
        name: [pose.to_machine(p) for p in outline]
        for name, outline in CARRIER_OUTLINES.items()
    })
    stations = carriage_stations(pass_name, theta)
    for rail, station in stations.items():
        out[f"pivot block {rail}"] = [
            trammel.rail_point(rail, station + x, y)
            for x, y in (
                (pivot_block.BLOCK_X0, -retention.BLOCK_WING_HALF_WIDTH),
                (retention.BLOCK_WING_END, -retention.BLOCK_WING_HALF_WIDTH),
                (retention.BLOCK_WING_END, -pivot_block.BLOCK_WIDTH / 2.0),
                (pivot_block.BLOCK_X1, -pivot_block.BLOCK_WIDTH / 2.0),
                (pivot_block.BLOCK_X1, pivot_block.BLOCK_WIDTH / 2.0),
                (retention.BLOCK_WING_END, pivot_block.BLOCK_WIDTH / 2.0),
                (retention.BLOCK_WING_END, retention.BLOCK_WING_HALF_WIDTH),
                (pivot_block.BLOCK_X0, retention.BLOCK_WING_HALF_WIDTH),
            )
        ]
        pin_station = station + pivot_block.BORE_X
        out[f"pivot cap {rail}"] = _rail_rect(
            rail,
            pin_station - retention.CAP_WIDTH / 2.0,
            pin_station + retention.CAP_WIDTH / 2.0,
            retention.CAP_LENGTH / 2.0,
        )
        px, py = trammel.rail_point(rail, pin_station)
        out[f"pivot retainer {rail}"] = _rect(
            px - retention.TOP_WASHER_OD / 2.0,
            px + retention.TOP_WASHER_OD / 2.0,
            py - retention.TOP_WASHER_OD / 2.0,
            py + retention.TOP_WASHER_OD / 2.0,
        )
        out[f"pivot pin {rail}"] = _rect(
            px - pivot_pin.FLANGE_DIA / 2.0,
            px + pivot_pin.FLANGE_DIA / 2.0,
            py - pivot_pin.FLANGE_DIA / 2.0,
            py + pivot_pin.FLANGE_DIA / 2.0,
        )
        out[f"pivot clevis {rail}"] = _rect(
            px + PIVOT_CLEVIS_HEAD_X - retention_hardware.CLEVIS_HEAD_HEIGHT_MAX,
            px + PIVOT_CLEVIS_HEAD_X + retention_hardware.CLEVIS_LENGTH_MAX,
            py - retention_hardware.CLEVIS_HEAD_DIA_MAX / 2.0,
            py + retention_hardware.CLEVIS_HEAD_DIA_MAX / 2.0,
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
    centre, radius = hub_head(pass_name, theta)
    out["HUB pin head"] = _rect(
        centre[0] - radius, centre[0] + radius,
        centre[1] - radius, centre[1] + radius,
    )
    return out


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
    names = [f"{which} stud {rail}" for rail in RAILS for which in ("near", "far")]
    return dict(zip(names, STUD_XY, strict=True))


@dataclass(frozen=True)
class ClearanceReport:
    """The jig's clearances to the machine's unmodelled features (mm): the
    column cover, the table and the rails' travel. This is NOT fixture
    self-collision acceptance: inspect ``capture_fixture_clearance_census``
    and retain the mandatory native whole-model interference gates."""

    cover_clearance: dict[str, float]  # item -> min gap to the column cover
    moving_x: tuple[float, float]  # machine X reached by any moving item
    moving_y: tuple[float, float]
    fixed_x: tuple[float, float]  # machine X of the bars
    fixed_y: tuple[float, float]
    bar_overhang: dict[int, float]  # rail -> its bar's far end past its table end
    carriage_margin: dict[str, tuple[float, float]]  # pass -> (near, far) on the rail
    table_edge_margins: dict[str, dict[str, float]]  # item -> edge -> min margin


def _update_min(store: dict, key, value: float) -> None:
    store[key] = min(store.get(key, value), value)


def clearance_report(samples: int = SWEEP_SAMPLES) -> ClearanceReport:
    """Sweep both passes over ±SWEEP ⚙ and measure every clearance to the
    machine's unmodelled features."""
    capture_feed_clearance_bounds()
    bars = fixed_outlines()
    feed = feed_outlines()
    cover: dict[str, float] = {}
    edges: dict[str, dict[str, float]] = {}
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

    for pass_name in trammel.PASS_RADIUS:
        near, far = math.inf, math.inf
        for theta in sweep_thetas(pass_name, samples):
            for station in carriage_stations(pass_name, theta).values():
                near = min(near, station - trammel.CARRIAGE_S_RANGE[0])
                far = min(far, trammel.CARRIAGE_S_RANGE[1] - station)
            for name, outline in moving_outlines(pass_name, theta).items():
                xs = [p[0] for p in outline]
                ys = [p[1] for p in outline]
                moving_xs.extend((min(xs), max(xs)))
                moving_ys.extend((min(ys), max(ys)))
                _update_min(cover, name, COVER_Y - max(ys))
                table_margins(name, xs, ys)
            centre, radius = hub_head(pass_name, theta)
            xs = [centre[0] - radius, centre[0] + radius]
            ys = [centre[1] - radius, centre[1] + radius]
            _update_min(cover, "HUB pin head", COVER_Y - ys[1])
            table_margins("HUB pin head", xs, ys)
        margins[pass_name] = (near, far)

    # The feed's stationary items against the cover and the table.
    for name, polygon in feed.items():
        xs = [p[0] for p in polygon]
        ys = [p[1] for p in polygon]
        _update_min(cover, name, COVER_Y - max(ys))
        table_margins(name, xs, ys)

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
    return ClearanceReport(
        cover_clearance=cover,
        moving_x=(min(moving_xs), max(moving_xs)),
        moving_y=(min(moving_ys), max(moving_ys)),
        fixed_x=(min(fixed_xs), max(fixed_xs)),
        fixed_y=(min(fixed_ys), max(fixed_ys)),
        bar_overhang=overhang,
        carriage_margin=margins,
        table_edge_margins=edges,
    )


def _carrier_coordinates(point: Point3) -> tuple[float, float]:
    c, s = math.cos(POSE.rotation), math.sin(POSE.rotation)
    x, y = point[0] - POSE.origin[0], point[1] - POSE.origin[1]
    return (c * x + s * y, -s * x + c * y)


def fixture_sweep_allowance(pass_name: str, samples: int = SWEEP_SAMPLES) -> float:
    """XY padding proving CONTINUOUS containment between sampled poses.

    For a carried point p, differentiating
    R(theta/2)*(p-(r*sin(theta),r*cos(theta)-H1)) bounds speed by
    .5*hypot(px,py+H1)+1.5*r. Rail-translated parts inherit the speed of
    their pass pin, since their offsets do not rotate. The nearest sample
    is at most half an interval away, including both endpoints.
    """
    if pass_name not in trammel.PASS_RADIUS:
        raise ValueError("unknown pass")
    if type(samples) is not int or samples < 2:
        raise ValueError("continuous fixture sweep needs at least two samples")
    points = list(trammel.pin_pair(pass_name))
    for stem, index, corners in _component_records().values():
        if _motion_root(stem, index)[0] == CARRIER:
            points.extend(_carrier_coordinates(point) for point in corners)
    speed = max(0.5 * math.hypot(x, y + trammel.H1) for x, y in points) + 1.5 * trammel.PASS_RADIUS[pass_name]
    return speed * trammel.SWEEP[pass_name] / (samples - 1)


def _printed_fixture_allowances() -> tuple[float, dict[str, float]]:
    """Deliberately loose L1 printed-dimension bounds, not vendor tolerances.

    Summing a part's displayed linear bands overbounds its source dimension
    chains (even reference/internal dimensions are retained). The separate
    placement stack covers the machined height/station chain to the moving
    carrier and its highest screw/washer seats. Unknown catalogue limits,
    rail alignment, installation and hand-form deviations are NOT invented:
    the supplied installed authority must include those uncertainties.
    """
    specs = {
        BASE_BAR: base_bar, PIVOT_BLOCK: pivot_block, PIVOT_PIN: pivot_pin,
        PIVOT_CAP: pivot_cap, PIVOT_RETAINER: pivot_retainer, CARRIER: carrier,
        RISER: riser, HUB_PIN: hub_pin, FEED_LEVER: feed_lever,
        END_BRACKET: end_bracket, NUT_BRACKET: nut_bracket,
        LEADSCREW: leadscrew_stock,
    }
    local = {
        stem: sum(
            printed_band_mm(places)
            for row in spec.DRAWING_PRECISION.values()
            for places in row.values() if places >= 1
        )
        for stem, spec in specs.items()
    }
    placement = (
        printed_band_mm(base_bar.THICK_PLACES)
        + printed_band_mm(pivot_block.DRAWING_PRECISION_BY_NAME["BlockHeight"])
        + printed_band_mm(retention.PIN_FLANGE_THICK_PLACES)
        + printed_band_mm(retention.PIN_UPPER_BOSS_PLACES)
        + printed_band_mm(carrier.THICKNESS_PLACES)
        + printed_band_mm(riser.THICKNESS_PLACES)
        + printed_band_mm(feed_lever.THICK_PLACES)
        + printed_band_mm(carrier.DRAWING_PRECISION_BY_NAME["A1X"])
        + 3.0 * carrier.POSITION_BAND
        + retention.PIN_LOWER_GAP[1] + retention.TOP_RUNNING_GAP[1]
        + max(block_washer.THICKNESS_MAX - block_washer.THICKNESS,
              lever_washer.THICKNESS_MAX - lever_washer.THICKNESS)
    )
    return placement, local


def _upset_fixture_padding(
    stem: str, index: int, points: list[Point3], pass_name: str,
    bounds: retention.CaptureBounds,
) -> tuple[float, float, float]:
    """Additional (XY, down, up) for the intact rigid captured mechanism."""
    pin_face_angle = bounds.pin_tilt
    seat_height = (
        retention.PIN_LOWER_GAP[1] + retention.PIN_FLANGE_THICK
        + printed_band_mm(retention.PIN_FLANGE_THICK_PLACES)
        + retention.PIN_UPPER_BOSS_HEIGHT + printed_band_mm(retention.PIN_UPPER_BOSS_PLACES)
    )
    pin_lateral = (
        bounds.cap_lateral_shift + bounds.flange_lateral_shift
        + seat_height * math.tan(pin_face_angle)
        + retention.CARRIER_DIAMETRAL_CLEARANCE_MAX / 2.0
    )
    root, root_index = _motion_root(stem, index)
    if root == CARRIER:
        a, b = trammel.pin_pair(pass_name)
        coordinates = [_carrier_coordinates(point) for point in points]
        radius = max(math.hypot(x - (a[0] + b[0]) / 2.0, y - a[1]) for x, y in coordinates)
        span = b[0] - a[0]
        # Opposite pin shifts can yaw the carrier even without bearing rigidity.
        yaw = math.atan2(2.0 * pin_lateral, max(0.0, span - 2.0 * pin_lateral))
        height = max(abs(point[2] - trammel.CARRIER_UNDERSIDE_Z) for point in points)
        xy = (
            pin_lateral + 2.0 * radius * math.sin(yaw / 2.0)
            + height * math.sin(bounds.carrier_tilt)
            + radius * (1.0 - math.cos(bounds.carrier_tilt))
        )
        height_change = height * (1.0 - math.cos(bounds.carrier_tilt))
        # These source prisms start at nominal CAD, whereas point_lift_bound
        # is relative to an actual normal pose. Enclose either datum without
        # adding the fixed carrier-bore manufacturing bias twice.
        slope = max(bounds.carrier_slope_change, math.tan(bounds.carrier_tilt))
        end_slope = min(slope, (bounds.support_lift + bounds.support_drop) / span)
        rise = max(
            bounds.support_lift + max(a[0] - x, x - b[0], 0.0) * end_slope
            + abs(y - a[1]) * slope for x, y in coordinates
        )
        return xy, bounds.support_drop + rise - bounds.support_lift + height_change, rise + height_change
    ancestor = stem
    while ancestor in LOCKED_TO and ancestor != PIVOT_PIN:
        ancestor = LOCKED_TO[ancestor][0]
    if ancestor == PIVOT_PIN:
        pin_origin = PIVOT_PIN_ORIGINS[root_index]
        radius = max(math.hypot(point[0] - pin_origin[0], point[1] - pin_origin[1]) for point in points)
        height = max(abs(point[2] - trammel.PIVOT_BLOCK_TOP_Z) for point in points)
        xy = pin_lateral + height * math.sin(pin_face_angle) + radius * (1.0 - math.cos(pin_face_angle))
        # A freely turning pin can clock its headed clevis/cotter independently
        # of the carrier. A full radial overbound avoids relying on that yaw.
        if stem in (PIVOT_CLEVIS_PIN, PIVOT_COTTER):
            xy += 2.0 * radius
        vertical = (
            retention.CAP_CHAMBER_EXCESS[1] + bounds.cap_roof_rise
            + radius * math.sin(pin_face_angle) + height * (1.0 - math.cos(pin_face_angle))
        )
        return xy, vertical, vertical
    if stem in (PIVOT_CAP, PIVOT_CAP_SCREW, PIVOT_LOCK_WIRE):
        # All three use the actual cap frame, including off-centre screw and
        # physical wire-row placements. A cap-footprint radius alone does not
        # enclose an extended wire endpoint or a screw's below-cap tip.
        cap_origin = PLACEMENTS[PIVOT_CAP][root_index][0]
        radius = max(math.hypot(p[0] - cap_origin[0], p[1] - cap_origin[1]) for p in points)
        height = max(abs(p[2] - cap_origin[2]) for p in points)
        xy = (
            bounds.cap_lateral_shift + 2.0 * radius * math.sin(bounds.cap_yaw / 2.0)
            + height * math.sin(bounds.cap_tilt) + radius * (1.0 - math.cos(bounds.cap_tilt))
        )
        if stem == PIVOT_CAP:
            return xy, retention.CAP_VERTICAL_MOTION_ENCLOSURE, bounds.cap_top_rise
        vertical = (
            retention.CAP_VERTICAL_MOTION_ENCLOSURE + radius * math.sin(bounds.cap_tilt)
            + height * (1.0 - math.cos(bounds.cap_tilt))
        )
        return xy, vertical, vertical
    return 0.0, 0.0, 0.0


def require_wing_bracket_clearance(*, wing_axis_reach: float | None = None) -> float:
    """Worst X gap between the solid wing and TL-29, in their common rail frame.

    Both the bracket centre set and bearing station start at TL-22's -X
    datum, so its absolute position cancels. The bracket's near face takes
    half its finished-length band; the wing end takes ONLY its direct
    bearing-axis reach band, not a second overall-length/end-location chain.
    The core's -Y face is the intended bracket mounting contact. Outside
    that face the positive X gap separates the entire wing, at every slide
    position, without subtracting holes or claiming an interference waiver.
    """
    reach = pivot_block.WING_AXIS_REACH if wing_axis_reach is None else wing_axis_reach
    nominal = (
        nut_bracket.X_SET_MID - nut_bracket.BRACKET_LENGTH / 2.0
        - pivot_block.BORE_STATION_X - reach
    )
    gap = nominal - (
        nut_bracket.X_SET_BAND
        + printed_band_mm(nut_bracket.LENGTH_PLACES) / 2.0
        + printed_band_mm(pivot_block.DRAWING_PRECISION_BY_NAME["BoreStationX"])
        + printed_band_mm(pivot_block.WING_AXIS_REACH_PLACES)
    )
    if gap < retention.WING_BRACKET_CLEARANCE_MIN:
        raise ValueError("pivot wing/nut bracket worst-case clearance is below the required gap")
    return gap


CAPTURE_FIXTURE_FAMILIES = (
    PIVOT_BLOCK, PIVOT_CAP, PIVOT_PIN, PIVOT_RETAINER,
    PIVOT_CAP_SCREW, PIVOT_CLEVIS_PIN, PIVOT_COTTER, PIVOT_LOCK_WIRE,
)


def capture_feed_clearance_bounds(
    *, actual_top_gap: float | None = None, transfer_axis_to_top: float | None = None,
) -> dict[tuple[str, str, str], float]:
    """Conditional source-solid bounds for accepted TL-29 fit-up, both passes.

    The actual whole-top and transfer-axis inspections are prerequisites,
    not inferred from unknown HGH/KP08 or stock-height bands. Purchased nut/
    screw limits and hand-formed wire/cotter deviations remain installed
    authority, not zero-error manufacturing certificates. This fixture-only
    census uses its existing native boxes, motion roots and analytic station
    ranges; no sampled pose or interference allowance substitutes for a gap.
    """
    top_gap = nut_bracket.BLOCK_PLANE_TOP_GAP_MIN if actual_top_gap is None else actual_top_gap
    transfer_gap = nut_bracket.TRANSFER_AXIS_TOP_MIN if transfer_axis_to_top is None else transfer_axis_to_top
    if not math.isfinite(top_gap) or top_gap < nut_bracket.BLOCK_PLANE_TOP_GAP_MIN:
        raise ValueError("TL-29 actual whole-top gap fails the aligned fit-up minimum")
    if not math.isfinite(transfer_gap) or transfer_gap < nut_bracket.TRANSFER_AXIS_TOP_MIN:
        raise ValueError("TL-29 actual transfer-axis/top distance fails its material minimum")
    bounds = retention.capture_bounds()
    gamma = math.radians(retention.GENERAL_ANGULAR_BAND_DEGREES)
    boxes = _component_local_boxes()
    placement_band, part_bands = _printed_fixture_allowances()
    origin, rows = PIVOT_BLOCK_PLACEMENTS[0]

    def in_block_frame(point: Point3) -> Point3:
        return tuple(
            sum((point[a] - origin[a]) * rows[k][a] for a in range(3))
            - (pivot_block.BLOCK_HEIGHT if k == 2 else 0.0)
            for k in range(3)
        )

    def source_box(stem: str, index: int) -> tuple[Box3, list[Point3]]:
        points = [frame_point(PLACEMENTS[stem][index], p) for p in _box_corners(boxes[stem])]
        local = [in_block_frame(point) for point in points]
        return tuple((min(p[a] for p in local), max(p[a] for p in local)) for a in range(3)), points

    x_set_band = nut_bracket.X_SET_BAND + printed_band_mm(nut_bracket.LENGTH_PLACES) / 2.0
    bore_band = printed_band_mm(pivot_block.DRAWING_PRECISION_BY_NAME["BoreStationX"])
    side_band = printed_band_mm(pivot_block.DRAWING_PRECISION_BY_NAME["BoreStationY"])
    seat_band = printed_band_mm(nut_bracket.SEAT_PLACES) + nut_bracket.SPIGOT_FLOAT
    nut_below_top = (
        nut_bracket.BRACKET_HEIGHT - printed_band_mm(nut_bracket.SIZE_PLACES)
        - nut_bracket.BORE_Z - seat_band - leadscrew_nut.FLANGE_DIA / 2.0
    )
    # -infinity deliberately refuses to credit an unmeasured lower datum.
    bracket = (
        (nut_bracket.FACE_X - x_set_band, nut_bracket.FACE_X + nut_bracket.BRACKET_LENGTH + x_set_band),
        (-pivot_block.BLOCK_WIDTH / 2.0 - side_band - nut_bracket.BRACKET_DEPTH
         - printed_band_mm(nut_bracket.SIZE_PLACES), -pivot_block.BLOCK_WIDTH / 2.0 + side_band),
        (-math.inf, -top_gap),
    )
    nut_source, _ = source_box(LEADSCREW_NUT, 0)
    screw_source, _ = source_box(LEADSCREW, 0)
    targets = {
        "nut bracket": bracket,
        "leadscrew nut": (
            (nut_source[0][0] - x_set_band, nut_source[0][1] + x_set_band),
            (nut_source[1][0] - side_band - seat_band, nut_source[1][1] + side_band + seat_band),
            (-math.inf, -top_gap - nut_below_top),
        ),
        "leadscrew": (
            screw_source[0],
            (screw_source[1][0] - side_band - seat_band, screw_source[1][1] + side_band + seat_band),
            (-math.inf, -top_gap - nut_below_top - leadscrew_nut.FLANGE_DIA / 2.0
             + leadscrew_stock.MAJOR_DIA / 2.0),
        ),
    }
    families = CAPTURE_FIXTURE_FAMILIES
    cap_radius = math.hypot(pivot_cap.WIDTH / 2.0, pivot_cap.LENGTH / 2.0)
    cap_xy = (
        bounds.cap_lateral_shift + 2.0 * cap_radius * math.sin(bounds.cap_yaw / 2.0)
        + pivot_cap.HEIGHT * math.sin(bounds.cap_tilt)
    )
    outline_band = printed_band_mm(pivot_cap.OUTLINE_PLACES) + printed_band_mm(pivot_cap.CENTER_LOCATION_PLACES)
    pin_height = (
        retention.PIN_LOWER_GAP[1] + pivot_pin.FLANGE_THICK + printed_band_mm(pivot_pin.FLANGE_THICK_PLACES)
        + pivot_pin.UPPER_BOSS_HEIGHT + printed_band_mm(pivot_pin.UPPER_BOSS_PLACES)
        + pivot_pin.CARRIER_LENGTH + printed_band_mm(pivot_pin.LENGTH_PLACES)
    )
    pin_radius = (
        (pivot_pin.FLANGE_DIA + pivot_pin.FLANGE_DIA_BAND[0]) / 2.0
        + bounds.cap_lateral_shift + bounds.flange_lateral_shift + pin_height * math.sin(bounds.pin_tilt)
    )
    screw_radius = (
        retention_hardware.SCREW_HEAD_DIA_MAX / 2.0 + retention_hardware.SCREW_HEAD_ECCENTRICITY_MAX
        + printed_band_mm(retention.CAP_BOLT_LOCATION_PLACES)
        + (pivot_block.BLOCK_HEIGHT + printed_band_mm(2)) * math.tan(gamma)
    )
    direction_dot = sum(a * b for a, b in zip(rail_direction(1), rail_direction(2), strict=True))
    if direction_dot >= 0.0:
        raise ValueError("capture/feed continuous separator requires the authored opposing rails")
    margins: dict[tuple[str, str, str], float] = {}
    for pass_name, (pin_min, _pin_max) in trammel.PIN_TRAVEL.items():
        for stem in families:
            per_rail = QUANTITIES[stem] // len(RAILS)
            for index in range(QUANTITIES[stem]):
                rail_index = index // per_rail
                box, points = source_box(stem, index)
                xy, drop, rise = _upset_fixture_padding(stem, index, points, pass_name, bounds)
                source = placement_band + part_bands.get(stem, 0.0)
                if rail_index:
                    # For every theta, p1,p2 >= pin_min. Projection onto e1:
                    # e1.(e2*p2-e1*(p1-PIN_OFFSET)) <= c*pin_min-pin_min+PIN_OFFSET.
                    pin_origin = PIVOT_PIN_ORIGINS[rail_index]
                    radius = max(math.hypot(p[0] - pin_origin[0], p[1] - pin_origin[1]) for p in points)
                    radius += source + xy
                    moving_right = direction_dot * pin_min - pin_min + trammel.PIN_OFFSET + radius
                    for target, target_box in targets.items():
                        if target == "leadscrew":
                            # The screw is fixed, so do not cancel carriage-1
                            # motion against this target's near-end station.
                            gap = (
                                leadscrew.SCREW_NEAR_END_S - direction_dot * pin_min - radius
                                - placement_band - part_bands.get(LEADSCREW, 0.0)
                            )
                        else:
                            gap = target_box[0][0] - moving_right
                        margins[pass_name, instance_name(stem, index), target] = gap
                    continue
                if stem == PIVOT_BLOCK:
                    box = (
                        (pivot_block.BLOCK_X0 - printed_band_mm(2), pivot_block.BLOCK_X1 + printed_band_mm(2)),
                        (-pivot_block.WING_WIDTH / 2.0 - printed_band_mm(2) / 2.0,
                         pivot_block.WING_WIDTH / 2.0 + printed_band_mm(2) / 2.0),
                        (-pivot_block.BLOCK_HEIGHT - printed_band_mm(2), 0.0),
                    )
                elif stem == PIVOT_CAP:
                    pad = outline_band + cap_xy
                    box = (
                        (pivot_block.BORE_X - pivot_cap.WIDTH / 2.0 - pad - bore_band,
                         pivot_block.BORE_X + pivot_cap.WIDTH / 2.0 + pad + bore_band),
                        (-pivot_cap.LENGTH / 2.0 - pad - side_band, pivot_cap.LENGTH / 2.0 + pad + side_band),
                        (-pivot_cap.REGISTER_PROJECTION - printed_band_mm(pivot_cap.REGISTER_PROJECTION_PLACES)
                         - retention.CAP_VERTICAL_MOTION_ENCLOSURE,
                         pivot_cap.HEIGHT + printed_band_mm(pivot_cap.HEIGHT_PLACES) + bounds.cap_top_rise),
                    )
                elif stem == PIVOT_PIN:
                    box = (
                        (pivot_block.BORE_X - pin_radius - bore_band, pivot_block.BORE_X + pin_radius + bore_band),
                        (-pin_radius - side_band, pin_radius + side_band),
                        (box[2][0] - source - drop, box[2][1] + source + rise),
                    )
                elif stem == PIVOT_CAP_SCREW:
                    x, y = pivot_block.CAP_TAP_POINTS[index]
                    box = (
                        (x - screw_radius - bore_band, x + screw_radius + bore_band),
                        (y - screw_radius - side_band, y + screw_radius + side_band),
                        (box[2][0] - source, box[2][1] + source),
                    )
                elif stem == PIVOT_LOCK_WIRE:
                    box = (
                        (box[0][0] - xy - outline_band - bore_band,
                         box[0][1] + xy + outline_band + bore_band),
                        (box[1][0] - xy - outline_band - side_band,
                         box[1][1] + xy + outline_band + side_band),
                        (pivot_cap.HEIGHT - printed_band_mm(pivot_cap.HEIGHT_PLACES)
                         - pivot_cap.COUNTERBORE_DEPTH - printed_band_mm(pivot_cap.COUNTERBORE_DEPTH_PLACES)
                         + boxes[stem][2][0] - (pivot_wire.WIRE_AXIS_Z - retention_hardware.SCREW_WIRE_HEIGHT_MIN)
                         - retention.CAP_VERTICAL_MOTION_ENCLOSURE, box[2][1] + source + rise),
                    )
                else:
                    box = (
                        (box[0][0] - source - xy, box[0][1] + source + xy),
                        (box[1][0] - source - xy, box[1][1] + source + xy),
                        (box[2][0] - source - drop, box[2][1] + source + rise),
                    )
                for target, target_box in targets.items():
                    gap = max(
                        max(a[0] - b[1], b[0] - a[1]) for a, b in zip(box, target_box, strict=True)
                    )
                    if stem == PIVOT_BLOCK and target == "nut bracket":
                        # Its core intentionally mounts on the bracket face;
                        # use the separately proved solid wing, not a full-box
                        # collision or a blanket overlapping-pair allowance.
                        gap = require_wing_bracket_clearance()
                    margins[pass_name, instance_name(stem, index), target] = gap
    for pair, gap in margins.items():
        if gap <= 0.0:
            raise ValueError(f"capture/feed source separator is lost for {pair}: {gap:.4f} mm")
    return margins


PRIMARY_CAPTURE_SECONDARY_FEATURES = (
    "clevis head", "clevis exposed end", "cotter eye",
    "cotter long prong/end", "cotter short prong/end",
)
PRIMARY_CAPTURE_REQUIRED_COVERAGE = (
    "complete axial endplay", "complete free pin clocking", "complete local rock",
    "all coupled combinations through the named pass",
    "actual secondary XYZ envelope including uncertainty",
)
PREBEARING_CAPTURE_REQUIRED_COVERAGE = (
    "final boss-fitted pin before any bearing press",
    "actual block and temporarily seated cap using C3 seating without wire",
    "entire mechanically reachable flange/rim hard-capture motion including tilt",
    "minimum tip recess from actual mounting plane including measurement uncertainty",
    "actual carriage under pin has no above-plane obstruction",
)


@dataclass(frozen=True)
class PrimaryCaptureMeasurement:
    """Explicit ACTUAL bench evidence for one physical support/pass pair.

    Extrema cover the complete COUPLED reachable envelope, not independent
    one-axis sweeps or a few nominal corners. Uncertainty is already excluded
    from every reported lower/upper bound. Land overlap is full-diameter
    shank bearing on BOTH opposed bore lands, never chamfer or tangency;
    under-support is the minimum over BOTH lands throughout that envelope.
    Secondary gaps are to the carrier at the mechanically established
    PRIMARY retainer/clevis take-up. A cotter/head touching first is failure,
    not an extra uplift stop. There are no inferred or verified defaults.
    """

    pass_name: str
    support: int
    fitted_retainer_thickness_mm: float
    normal_loaded_running_gap_mm: tuple[float, float]
    max_relative_primary_travel_mm: float
    min_carrier_secondary_gaps_mm: tuple[tuple[str, float], ...]
    min_opposed_land_overlaps_mm: tuple[float, float]
    min_carrier_under_support_mm: float
    # Origin: actual PIN carrier-seating shoulder; +Z: journal axis. XY is
    # the fixed neutral PIN_ROWS reference, not a co-rotating body frame.
    # This box includes ALL secondary parts and all coupled local motions.
    secondary_envelope_in_pin_seat_frame_mm: Box3
    min_tip_recess_mm: float
    carriage_under_pin_not_above_plane: bool
    prebearing_capture_coverage: tuple[str, ...]
    prebearing_capture_evidence: str
    coverage: tuple[str, ...]
    primary_take_up_without_secondary_contact: bool
    evidence: str


def qualify_primary_capture_measurements(
    records: tuple[PrimaryCaptureMeasurement, ...],
) -> dict[tuple[str, int], PrimaryCaptureMeasurement]:
    """Accept only complete, quantified C2A/C4/C5 physical capture evidence.

    This validates supplied evidence, not whether a measurement was performed.
    In particular it is NOT a native CAD build/import prerequisite and makes
    no installed-kit claim without the named physical measurement authority.
    """
    expected = {(pass_name, support) for pass_name, mates in PIN_MATES.items()
                for _name, _hole, support in mates}
    if len(expected) != 4:
        raise ValueError("primary capture qualification needs both physical supports and both passes")
    accepted = {}

    def number(value, label):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(f"primary capture {label} must be a finite measured millimetre bound")
        return float(value)

    for record in records:
        if not isinstance(record, PrimaryCaptureMeasurement):
            raise ValueError("primary capture qualification needs explicit measurement records")
        key = record.pass_name, record.support
        if type(record.support) is not int or key not in expected or key in accepted:
            raise ValueError(f"missing, duplicate or wrong physical primary support/pass identity: {key}")
        if (set(record.coverage) != set(PRIMARY_CAPTURE_REQUIRED_COVERAGE)
                or len(record.coverage) != len(PRIMARY_CAPTURE_REQUIRED_COVERAGE)):
            raise ValueError(f"primary capture {key} lacks complete coupled endplay/clock/rock coverage")
        if record.primary_take_up_without_secondary_contact is not True:
            raise ValueError(f"primary capture {key} must establish primary take-up without a secondary stop")
        if not isinstance(record.evidence, str) or not record.evidence.strip():
            raise ValueError(f"primary capture {key} needs an actual measurement evidence authority")
        if (set(record.prebearing_capture_coverage) != set(PREBEARING_CAPTURE_REQUIRED_COVERAGE)
                or len(record.prebearing_capture_coverage) != len(PREBEARING_CAPTURE_REQUIRED_COVERAGE)):
            raise ValueError(f"primary capture {key} lacks the complete pre-bearing hard-capture trial including tilt")
        if record.carriage_under_pin_not_above_plane is not True:
            raise ValueError(f"primary capture {key} needs the actual carriage under pin at or below the mounting plane")
        if not isinstance(record.prebearing_capture_evidence, str) or not record.prebearing_capture_evidence.strip():
            raise ValueError(f"primary capture {key} needs actual pre-bearing trial evidence")
        if number(record.min_tip_recess_mm, "minimum pre-bearing tip recess") < retention.PIN_TIP_CARRIAGE_CLEARANCE_MIN:
            raise ValueError(f"primary capture {key} lacks minimum net pin-tip/carriage clearance")
        if number(record.fitted_retainer_thickness_mm, "finished retainer thickness") <= 0.0:
            raise ValueError(f"primary capture {key} needs positive actual fitted retainer thickness")
        if len(record.normal_loaded_running_gap_mm) != 2:
            raise ValueError(f"primary capture {key} needs the measured normal loaded-gap interval")
        gap_lo, gap_hi = (number(v, "normal loaded running gap") for v in record.normal_loaded_running_gap_mm)
        if not retention.TOP_RUNNING_GAP[0] <= gap_lo <= gap_hi <= retention.TOP_RUNNING_GAP[1]:
            raise ValueError(f"primary capture {key} normal loaded-gap interval fails C4")
        travel = number(record.max_relative_primary_travel_mm, "maximum relative primary travel")
        if not gap_lo <= travel <= retention.TOP_PRIMARY_RELATIVE_TRAVEL_MAX:
            raise ValueError(f"primary capture {key} maximum relative primary travel contradicts its positive normal gap or exceeds C4")
        gaps = dict(record.min_carrier_secondary_gaps_mm)
        if (set(gaps) != set(PRIMARY_CAPTURE_SECONDARY_FEATURES)
                or len(record.min_carrier_secondary_gaps_mm) != len(PRIMARY_CAPTURE_SECONDARY_FEATURES)):
            raise ValueError(f"primary capture {key} needs every secondary feature, exactly once")
        if any(number(gap, "minimum carrier/secondary clearance") < retention.TOP_SECONDARY_CLEARANCE_MIN
               for gap in gaps.values()):
            raise ValueError(f"primary capture {key} lacks minimum carrier/secondary clearance at primary take-up")
        if len(record.min_opposed_land_overlaps_mm) != 2:
            raise ValueError(f"primary capture {key} needs BOTH opposed full-shank bearing overlaps")
        if any(number(v, "full-shank bearing overlap") <= 0.0 for v in record.min_opposed_land_overlaps_mm):
            raise ValueError(f"primary capture {key} needs positive full-section bearing overlap on BOTH lands")
        if number(record.min_carrier_under_support_mm, "carrier under-support") <= 0.0:
            raise ValueError(f"primary capture {key} needs positive carrier under-support throughout endplay")
        envelope = record.secondary_envelope_in_pin_seat_frame_mm
        if len(envelope) != 3 or any(len(interval) != 2 for interval in envelope):
            raise ValueError(f"primary capture {key} needs a closed finite XYZ secondary envelope")
        for lo, hi in envelope:
            if number(lo, "secondary envelope lower extent") >= number(hi, "secondary envelope upper extent"):
                raise ValueError(f"primary capture {key} needs strictly ordered finite secondary envelope extents")
        accepted[key] = record
    if set(accepted) != expected:
        raise ValueError(f"primary capture measurement coverage is incomplete: missing {sorted(expected - accepted.keys())}")
    for support in {support for _pass, support in expected}:
        thicknesses = {record.fitted_retainer_thickness_mm for (p, s), record in accepted.items() if s == support}
        if len(thicknesses) != 1:
            raise ValueError(f"support {support} must use the SAME measured matched retainer thickness on BOTH passes")
        trials = {(record.min_tip_recess_mm, record.prebearing_capture_evidence)
                  for (_pass, s), record in accepted.items() if s == support}
        if len(trials) != 1:
            raise ValueError(f"support {support} must reuse the SAME physical pre-bearing capture trial on BOTH passes")
    return accepted


def _primary_capture_box(record: PrimaryCaptureMeasurement, stem: str) -> Box3:
    """Installed upper/cut-washer bounds in the SAME actual PIN-seat frame."""
    if stem in (PIVOT_CLEVIS_PIN, PIVOT_COTTER):
        return record.secondary_envelope_in_pin_seat_frame_mm
    if stem == PIVOT_RETAINER:
        radius = (pivot_retainer.OUTER_DIA + printed_band_mm(1)) / 2.0
        return ((-radius, radius), (-radius, radius), (
            carrier.THICKNESS - carrier.THICKNESS_BAND + record.normal_loaded_running_gap_mm[0],
            carrier.THICKNESS + carrier.THICKNESS_BAND + record.normal_loaded_running_gap_mm[1]
            + record.fitted_retainer_thickness_mm,
        ))
    raise ValueError("actual primary box is only for this fixture's retainer/clevis/cotter")


def _primary_capture_world_points(record: PrimaryCaptureMeasurement, stem: str, pin_pose: Placement) -> list[Point3]:
    seat_pose = compose(pin_pose, (0.0, 0.0, pivot_pin.CARRIER_STATION))
    return [frame_point(seat_pose, p) for p in _box_corners(_primary_capture_box(record, stem))]


@dataclass(frozen=True)
class CaptureFixturePairProof:
    """One physical unordered pair/pass, never an installed/strength certificate.

    Nominal common-transform evidence and upset clearance are deliberately
    separate. A native baseline is the caller's attestation of a passed
    WHOLE-MODEL check of these exact solids/placements and unchanged exact fit
    limits. It must not be carried across geometry changes. Empty authority
    cannot qualify an invariant pair.
    """

    nominal: str
    upset: str
    nominal_gap: float
    upset_gap: float
    basis: tuple[str, ...]
    missing: tuple[str, ...]

    @property
    def source_resolved(self) -> bool:
        return self.nominal != "UNRESOLVED" and self.upset != "UNRESOLVED"


def _capture_fixture_joint(
    first: tuple[str, int], second: tuple[str, int], bounds: retention.CaptureBounds, pass_name: str,
    primary: dict[tuple[str, int], PrimaryCaptureMeasurement],
) -> str | None:
    """Only the existing cartridge's named functional surfaces, not a waiver.

    Native nominal qualification is still required by the census for these
    whole-part pairs. The capture bounds then supply the contact/nonpenetration
    argument during rigid upset, rather than disjoint padded material AABBs.
    No headed clevis/cotter/wire inherits the axisymmetric journal argument.
    """
    (a, i), (b, j) = first, second
    if b == CARRIER:
        a, i, b, j = b, j, a, i
    if a == CARRIER and b in (PIVOT_PIN, PIVOT_CAP, PIVOT_RETAINER):
        if j not in {pin for _name, _hole, pin in PIN_MATES[pass_name]}:
            return None
        if b == PIVOT_CAP and bounds.cap_running_clearance > 0.0:
            return "capture_bounds: full cap/carrier running clearance at each support, including coupled tilt"
        if b == PIVOT_PIN and pivot_pin.CARRIER_CLEARANCE_MIN >= 0.0:
            return "coaxial circular carrier bore/journal; lower boss seat; capture_bounds retained engagement and tilt"
        if b == PIVOT_RETAINER and (pass_name, j) in primary:
            return "quantified actual C4 primary take-up: bounded relative travel, full-section bridge on both lands and carrier under-support through all coupled endplay/clock/rock; no secondary uplift stop"
        return None
    if _motion_root(a, i) != _motion_root(b, j):
        return None
    families = {a, b}
    if PIVOT_BLOCK in families:
        other = b if a == PIVOT_BLOCK else a
        existing_fit = {
            CARRIAGE: "original flat block/carriage mounting faces and four-hole matched attachment; actual purchased mounting pattern/height acceptance",
            BEARING: "original exact block/6200 outer-race seat fit and shoulder depths; actual bearing width/seat acceptance, no change to native limits",
            CARRIAGE_SCREW: "original four M4 clearance/counterbore seats into the carriage; actual seated head and mounting-pattern fit",
            BLOCK_SCREW: "original two side clearance/counterbore paths to TL-29, with actual seated wedge-lock pairs",
            BLOCK_LOCK_WASHER: "original side-counterbore floor and matched wedge-lock pair, not clearance through solid block stock",
        }
        if other in existing_fit:
            return existing_fit[other]
    if families == {PIVOT_PIN, BEARING}:
        return "original exact pin/6200 inner-race interference and narrow-boss support; C1-C2 measured axial stack, unchanged native overlap limits"
    if families == {PIVOT_BLOCK, PIVOT_CAP}:
        return "capture_bounds: seated cap lands and both registers, positive assembly/bottom clearance and retained engagement"
    if families == {PIVOT_BLOCK, PIVOT_PIN}:
        return "capture_bounds: integral flange/solid block stop annulus; existing exact bearing-seat fits remain mandatory"
    if families == {PIVOT_CAP, PIVOT_PIN}:
        return "capture_bounds: flange/pocket and roof stop circle; positive pin/aperture and normal corner clearances"
    if families == {PIVOT_BLOCK, PIVOT_CAP_SCREW}:
        return "unchanged exact cap-screw/block thread-major fit only; C3B actual complete-thread interval and seating remain mandatory"
    if families == {PIVOT_CAP, PIVOT_CAP_SCREW}:
        return "capture_bounds: seated drilled head/floor stop circle and retained floor support; shank contact may stop cap upset sooner"
    if families == {PIVOT_PIN, PIVOT_RETAINER}:
        return "C4 actual retainer bore on circular pin journal; fitted whole-face carrier gap and upper clevis stop, not a clamped washer"
    if families == {PIVOT_PIN, PIVOT_CLEVIS_PIN}:
        return "C4-C5 actual cross-hole/clevis diametral fit, full loose-pin travel retained; headed clevis remains a separate external envelope"
    if families == {PIVOT_RETAINER, PIVOT_CLEVIS_PIN} and (pass_name, _motion_root(a, i)[1]) in primary:
        return "quantified actual C4 full-diameter clevis bridge on BOTH retainer lands with positive overlap and carrier under-support through all endplay; not the representative head station"
    if families == {PIVOT_RETAINER, PIVOT_COTTER} and (pass_name, _motion_root(a, i)[1]) in primary:
        return "C5 actual cotter outside this retainer through full endplay; permitted axial keeper contact only, with independently qualified C4 shank bridge/primary take-up; never a cotter uplift stop"
    if families == {PIVOT_CLEVIS_PIN, PIVOT_COTTER}:
        return "C5 measured split-cotter fit in this clevis hole and both bent retaining legs; source form is conditional on installed inspection"
    if families == {PIVOT_PIN, PIVOT_COTTER}:
        return "C5 intact bent cotter is the clevis's axial keeper at the solid pin/cross-hole wall; keeper contact may limit endplay, never a journal exemption for external obstacles"
    if families == {PIVOT_CAP, PIVOT_LOCK_WIRE}:
        return "C3C this cap's two source-routed wire rows in its channels; intact paired-head route and actual turned-in tails required; wire/channel contact can stop rock sooner"
    if families == {PIVOT_CAP_SCREW, PIVOT_LOCK_WIRE}:
        screw_index = i if a == PIVOT_CAP_SCREW else j
        wire_index = i if a == PIVOT_LOCK_WIRE else j
        # BOLT_CENTERS is X-major, not row-major: row 0 joins screws 0/2.
        if retention.CAP_BOLT_CENTERS[screw_index % 4][1] == retention.CAP_BOLT_Y_OFFSETS[wire_index % 2]:
            return "C3C this physical wire row passes through these two drilled heads; actual hole/round-wire fit and seated non-loosening route, not an external collision exemption"
    return None


def _capture_fixture_source_prisms(
    stem: str, index: int, boxes: dict[str, Box3], *, manufactured: bool,
) -> tuple[Box3, ...]:
    """Finite native-source material primitives and their DIRECT extent bands.

    This deliberately does not use the installed-tooling L1 sum of every
    dimension. A hole size cannot enlarge an outside edge. Block edges use
    their one bearing-axis/datum chain; fitted C2/C4 faces replace reference
    boss/washer dimensions. Purchased limits not supplied by the sources stay
    conditional on actual material being contained by the stated envelopes.
    """
    b1, b2 = printed_band_mm(1), printed_band_mm(2)

    def grown(box, lower, upper=None):
        upper = lower if upper is None else upper
        return tuple((lo - lower[a], hi + upper[a]) for a, (lo, hi) in enumerate(box))

    if stem == PIVOT_BLOCK:
        core = ((pivot_block.BLOCK_X0, pivot_block.BLOCK_X1),
                (-pivot_block.BLOCK_WIDTH / 2.0, pivot_block.BLOCK_WIDTH / 2.0),
                (0.0, pivot_block.BLOCK_HEIGHT))
        wing = ((pivot_block.BLOCK_X0, pivot_block.WING_X1),
                (-pivot_block.WING_WIDTH / 2.0, pivot_block.WING_WIDTH / 2.0),
                (0.0, pivot_block.BLOCK_HEIGHT))
        if not manufactured:
            return core, wing
        bore_x = printed_band_mm(pivot_block.DRAWING_PRECISION_BY_NAME["BoreStationX"])
        bore_y = printed_band_mm(pivot_block.DRAWING_PRECISION_BY_NAME["BoreStationY"])
        width = printed_band_mm(pivot_block.DRAWING_PRECISION_BY_NAME["BlockWidth"])
        length = printed_band_mm(pivot_block.DRAWING_PRECISION_BY_NAME["BlockLength"])
        height = printed_band_mm(pivot_block.DRAWING_PRECISION_BY_NAME["BlockHeight"])
        # The integral wing is centred on the core mid-plane, whereas its
        # end is dimensioned DIRECTLY from the bearing axis.
        wing_y = width / 2.0 + bore_y + printed_band_mm(2) / 2.0
        return (
            grown(core, (bore_x, bore_y, 0.0), (bore_x + length, bore_y + width, height)),
            grown(wing, (bore_x, wing_y, 0.0),
                  (printed_band_mm(pivot_block.WING_AXIS_REACH_PLACES), wing_y, height)),
        )
    if stem == PIVOT_PIN:
        bearing_r = (pivot_pin.FIT_DIA + pivot_pin.BEARING_BAND[0]) / 2.0
        boss_r = (pivot_pin.COLLAR_DIA + (printed_band_mm(pivot_pin.COLLAR_PLACES) if manufactured else 0.0)) / 2.0
        flange_r = (pivot_pin.FLANGE_DIA + (pivot_pin.FLANGE_DIA_BAND[0] if manufactured else 0.0)) / 2.0
        flange_bottom, flange_top, seat = pivot_pin.FLANGE_BOTTOM_STATION, pivot_pin.FLANGE_TOP_STATION, pivot_pin.CARRIER_STATION
        lengths = (
            (bearing_r, (0.0, pivot_pin.BEARING_LENGTH)),
            (boss_r, (pivot_pin.BEARING_LENGTH, flange_bottom)),
            (flange_r, (flange_bottom, flange_top)),
            (boss_r, (flange_top, seat)),
            (pivot_pin.FIT_DIA / 2.0, (seat, pivot_pin.OVERALL_LENGTH)),
        )
        if not manufactured:
            return tuple(((-r, r), (-r, r), z) for r, z in lengths)
        # C2 directly sets flange-bottom height above the actual block top.
        # Lower-boss fit follows the measured upper-bearing face, not the
        # reference 1.15 dimension. Bearing-face departures remain purchased
        # receiving authority; the known seat-depth band is retained.
        gap = retention.PIN_LOWER_GAP[1] - retention.PIN_LOWER_GAP[0]
        journal = printed_band_mm(pivot_pin.LENGTH_PLACES)
        depth = printed_band_mm(3)
        flange = printed_band_mm(pivot_pin.FLANGE_THICK_PLACES)
        boss = printed_band_mm(pivot_pin.UPPER_BOSS_PLACES)
        errors = ((gap + depth + journal, gap + depth),
                  (gap + depth, gap),
                  (gap, flange),
                  (gap + flange, flange + boss),
                  (gap + flange + boss, flange + boss + journal))
        return tuple(((-r, r), (-r, r), (z[0] - down, z[1] + up))
                     for (r, z), (down, up) in zip(lengths, errors, strict=True))
    if stem == PIVOT_CLEVIS_PIN:
        head_r = retention_hardware.CLEVIS_HEAD_DIA_MAX / 2.0
        shaft_r = retention_hardware.CLEVIS_DIA_MAX / 2.0
        return (
            ((-retention_hardware.CLEVIS_HEAD_HEIGHT_MAX, 0.0), (-head_r, head_r), (-head_r, head_r)),
            ((0.0, retention_hardware.CLEVIS_LENGTH_MAX), (-shaft_r, shaft_r), (-shaft_r, shaft_r)),
        )
    if stem == PIVOT_COTTER:
        # Native recipe diag_build_CP_062_0500: eye, two narrow necks, and
        # two spread tails. The tail does NOT extend down to the eye bottom.
        r, half = pivot_cotter.EYE_OUTER_RADIUS, pivot_cotter.INSTALLED_Y_HALF_WIDTH
        inner, outer = pivot_cotter.PRONG_GAP / 2.0, pivot_cotter.PRONG_GAP / 2.0 + pivot_cotter.PRONG_THICK
        pieces = [((-r, r), (-half, half), (pivot_cotter.EYE_CENTER - r, pivot_cotter.EYE_CENTER + r))]
        for sign, tail in ((-1, pivot_cotter.SHORT_TAIL), (1, pivot_cotter.LONG_TAIL)):
            neck_x = sorted((sign * inner, sign * outer))
            tail_x = sorted((sign * inner, sign * (outer + tail)))
            pieces.extend(((tuple(neck_x), (-half, half), (pivot_cotter.PRONG_START, pivot_cotter.INSTALLED_Z_MAX)),
                           (tuple(tail_x), (-half, half), (pivot_cotter.PRONG_BEND, pivot_cotter.INSTALLED_Z_MAX))))
        if not manufactured:
            return tuple(pieces)
        # Known supplier WIDTH/DIA/LENGTH limits apply to their own pieces.
        # The eye OD has only a published MIN: its actual containing envelope
        # remains a C5 receiving/installed-form condition, never a fake max.
        width = (retention_hardware.COTTER_WIDTH_MAX - retention_hardware.COTTER_WIDTH) / 2.0
        section = (retention_hardware.COTTER_DIA_MAX - retention_hardware.COTTER_DIA) / 2.0
        clevis_r = (retention_hardware.CLEVIS_DIA_MAX - retention_hardware.CLEVIS_DIA_MIN) / 4.0
        tail = retention_hardware.COTTER_LENGTH_MAX - retention_hardware.COTTER_LENGTH + 2.0 * clevis_r
        return tuple(grown(piece, (0.0 if n == 0 else section + (tail if n % 2 == 0 else 0.0),
                                   width, clevis_r + (section if n else 0.0)))
                     for n, piece in enumerate(pieces))
    if stem == PIVOT_CAP_SCREW:
        # The large head/under-head fillet is NOT present at the low thread
        # tip beside the original block-mounting hardware.
        head_r = retention_hardware.SCREW_HEAD_DIA_MAX / 2.0
        body_r = retention_hardware.SCREW_MAJOR_DIA_MAX / 2.0
        pieces = (
            ((-head_r, head_r), (-head_r, head_r),
             (-retention_hardware.SCREW_FILLET_LENGTH_MAX, retention_hardware.SCREW_HEAD_HEIGHT_MAX)),
            ((-body_r, body_r), (-body_r, body_r), (-retention_hardware.SCREW_LENGTH, 0.0)),
        )
        location = (printed_band_mm(retention.CAP_BOLT_LOCATION_PLACES)
                    + retention_hardware.SCREW_HEAD_ECCENTRICITY_MAX
                    + (pivot_block.BLOCK_HEIGHT + b2) * math.tan(math.radians(retention.GENERAL_ANGULAR_BAND_DEGREES)))
        return tuple(grown(piece, (location, location, 0.0)) for piece in pieces) if manufactured else pieces
    if stem == PILLOW_BLOCK:
        # Its 55-wide foot is below the moving wing; the high pedestal/boss
        # is only 28 wide. A filled 55 x 29 rectangle invents wing material
        # interference. Keep the existing +3 envelope margin on EACH piece.
        pieces = (
            ((-pillow_block.LENGTH / 2.0, pillow_block.LENGTH / 2.0),
             (-pillow_block.WIDTH / 2.0, pillow_block.WIDTH / 2.0), (0.0, pillow_block.FOOT_THICK)),
            ((-pillow_block.BOSS_RADIUS, pillow_block.BOSS_RADIUS),
             (-pillow_block.WIDTH / 2.0, pillow_block.WIDTH / 2.0), (pillow_block.FOOT_THICK, pillow_block.HEIGHT)),
        )
        return tuple(grown(p, (leadscrew.KP08_MARGIN,) * 3) for p in pieces) if manufactured else pieces
    box = boxes[stem]
    if not manufactured:
        return (box,)
    # Only outside-size/locating dimensions that can move these material
    # boundaries. Unknown purchased dimensions are NOT given fictitious bands.
    bands = {
        BASE_BAR: (printed_band_mm(base_bar.STATION_PLACES),
                   printed_band_mm(base_bar.STATION_PLACES) + printed_band_mm(base_bar.RAIL_ROW_PLACES),
                   printed_band_mm(base_bar.THICK_PLACES)),
        CARRIAGE: (b2 + printed_band_mm(pivot_block.HOLE_STATION_PLACES) + pivot_block.SCREW_FLOAT,) * 2 + (0.0,),
        PIVOT_CAP: (printed_band_mm(pivot_cap.OUTLINE_PLACES) + printed_band_mm(pivot_cap.CENTER_LOCATION_PLACES),) * 2
                   + (printed_band_mm(pivot_cap.HEIGHT_PLACES),),
        PIVOT_RETAINER: (printed_band_mm(1) / 2.0, printed_band_mm(1) / 2.0, 0.0),
        PIVOT_LOCK_WIRE: (printed_band_mm(retention.CAP_BOLT_LOCATION_PLACES)
                          + retention_hardware.SCREW_HEAD_ECCENTRICITY_MAX
                          + (retention.CAP_HEIGHT - retention.CAP_COUNTERBORE_DEPTH + b2 + printed_band_mm(3))
                          * math.tan(math.radians(retention.GENERAL_ANGULAR_BAND_DEGREES))
                          + (retention_hardware.SCREW_HEAD_DIA_MAX - retention_hardware.SCREW_HEAD_DIA) / 2.0,) * 2
                         + (max(retention_hardware.SCREW_WIRE_HEIGHT_MAX - pivot_wire.WIRE_AXIS_Z,
                                pivot_wire.WIRE_AXIS_Z - retention_hardware.SCREW_WIRE_HEIGHT_MIN),),
        CARRIER: (b1 + b2 + carrier.POSITION_BAND, b1 + b2 + carrier.POSITION_BAND, 0.0),
        RISER: (b1 + 2.0 * b2, b1 + 2.0 * b2, printed_band_mm(riser.THICKNESS_PLACES)),
        HUB_PIN: (printed_band_mm(hub_pin.HEAD_PLACES) / 2.0,) * 2 + (printed_band_mm(hub_pin.LENGTH_PLACES),),
        FEED_LEVER: (printed_band_mm(feed_lever.SIZE_PLACES) + 2.0 * b2,
                     printed_band_mm(feed_lever.THICK_PLACES), printed_band_mm(feed_lever.SIZE_PLACES) + 2.0 * b2),
        END_BRACKET: (printed_band_mm(end_bracket.LENGTH_PLACES),
                      printed_band_mm(end_bracket.STOCK_PLACES) / 2.0, printed_band_mm(end_bracket.STOCK_PLACES)),
        NUT_BRACKET: (nut_bracket.X_SET_BAND + printed_band_mm(nut_bracket.LENGTH_PLACES) / 2.0,
                      printed_band_mm(nut_bracket.SIZE_PLACES), printed_band_mm(nut_bracket.SIZE_PLACES)),
        LEADSCREW: (0.0, printed_band_mm(leadscrew_stock.LENGTH_PLACES), 0.0),
        # Purchased screw recipes use local +Y as their axis, not local +Z.
        CARRIAGE_SCREW: (b2 + printed_band_mm(pivot_block.HOLE_STATION_PLACES) + pivot_block.SCREW_FLOAT,
                         printed_band_mm(pivot_block.CBORE_FLOOR_PLACES),
                         b2 + printed_band_mm(pivot_block.HOLE_STATION_PLACES) + pivot_block.SCREW_FLOAT),
        BLOCK_SCREW: (b2 + printed_band_mm(pivot_block.SIDE_STATION_PLACES),
                      3.0 * b2, printed_band_mm(pivot_block.SIDE_STATION_PLACES)),
        BLOCK_LOCK_WASHER: (b2 + printed_band_mm(pivot_block.SIDE_STATION_PLACES),
                            3.0 * b2, printed_band_mm(pivot_block.SIDE_STATION_PLACES)),
        NUT_SCREW: (printed_band_mm(nut_bracket.SEAT_PLACES) + nut_bracket.SPIGOT_FLOAT,) * 3,
        # Their supporting thickness moves the placement in height_chain,
        # not the screw's own length/shape a second time.
        RISER_SCREW: (2.0 * b2, 0.0, 2.0 * b2),
        LEVER_SCREW: (2.0 * b2, 0.0, 2.0 * b2),
        LEVER_LOCK_WASHER: (2.0 * b2, 0.0, 2.0 * b2),
    }
    if stem == HOLD_DOWN_STUD:
        # Approved rework's sole new exterior authority, not stock 3-in length
        # tolerance and not an invented purchased-kit band.
        return (grown(box, (0.0, 0.0, 0.0), (0.0, hold_down_stud.LENGTH_BAND, 0.0)),)
    if stem == PIVOT_CAP:
        x, y, height = bands[stem]
        return (grown(box, (x, y, printed_band_mm(pivot_cap.REGISTER_PROJECTION_PLACES)),
                      (x, y, height)),)
    if stem == RISER:
        x, y, height = bands[stem]
        return (grown(box, (x, y, 0.0), (x, y, height)),)
    if stem == FEED_LEVER:
        x, height, z = bands[stem]
        return (grown(box, (x, 0.0, z), (x, height, z)),)
    if stem == CARRIER:
        # Native local +Y is UP and origin is the top face. Anchor the source
        # primitive at its lower pin seat, so thickness grows only the top;
        # do not also translate its bottom by the same thickness uncertainty.
        x, _z, y = box
        plan = bands[stem]
        return (( (x[0] - plan[0], x[1] + plan[0]),
                  (_z[0], _z[1] + carrier.THICKNESS_BAND),
                  (y[0] - plan[1], y[1] + plan[1]) ),)
    if stem == PIVOT_RETAINER:
        # C4 is the authority, not the REF thickness's title-block band.
        cross_band = 2.0 * printed_band_mm(pivot_pin.LENGTH_PLACES)
        top_max = (retention.PIN_CROSS_HOLE_FROM_SEAT + cross_band
                   + (retention.PIN_CROSS_HOLE_DIA + retention.PIN_CROSS_HOLE_BAND[0]) / 2.0
                   - retention_hardware.CLEVIS_DIA_MIN)
        bottom_nominal = carrier.THICKNESS + sum(retention.TOP_RUNNING_GAP) / 2.0
        radial = bands[stem][0]
        return (( (box[0][0] - radial, box[0][1] + radial),
                  (box[1][0] - radial, box[1][1] + radial),
                  (-carrier.THICKNESS_BAND - (retention.TOP_RUNNING_GAP[1] - retention.TOP_RUNNING_GAP[0]) / 2.0,
                   top_max - bottom_nominal) ),)
    return (grown(box, bands.get(stem, (0.0, 0.0, 0.0))),)


def _capture_fixture_height_chain(stem: str, index: int) -> dict[tuple[str, int], float]:
    """Only known independent Z datums; shared terms cancel in a LOCAL pair.

    Catalogue rail/carriage/KP08/bearing heights still require receiving/actual
    fit acceptance. They are not silently treated as known zero tolerances.
    """
    root, support = _motion_root(stem, index)
    bar = printed_band_mm(base_bar.THICK_PLACES)
    block = printed_band_mm(pivot_block.DRAWING_PRECISION_BY_NAME["BlockHeight"])
    seat = (retention.PIN_LOWER_GAP[1] - retention.PIN_LOWER_GAP[0]
            + printed_band_mm(pivot_pin.FLANGE_THICK_PLACES) + printed_band_mm(pivot_pin.UPPER_BOSS_PLACES))
    if root == CARRIER:
        # Either support can set global height. Local carrier/pin comparisons
        # below use the coupled support argument instead of this loose bound.
        chain = {("carrier support height", 0): bar + block + seat}
        if stem != CARRIER:
            chain[("carrier thickness", 0)] = carrier.THICKNESS_BAND
        if stem in (RISER_SCREW, CL_DOWEL, CLAMP_SCREW):
            chain[("riser thickness", 0)] = printed_band_mm(riser.THICKNESS_PLACES)
        if stem in (LEVER_SCREW, LEVER_LOCK_WASHER):
            chain[("lever thickness", 0)] = printed_band_mm(feed_lever.THICK_PLACES)
        if stem == HUB_PIN:
            chain[("head underside", 0)] = printed_band_mm(hub_pin.LENGTH_PLACES)
        return chain
    if root == CARRIAGE:
        chain = {("bar thickness", support): bar}
        if stem in (PIVOT_PIN, PIVOT_CAP, PIVOT_RETAINER, PIVOT_CAP_SCREW,
                    PIVOT_CLEVIS_PIN, PIVOT_COTTER, PIVOT_LOCK_WIRE):
            chain[("block height", support)] = block
        if stem in (PIVOT_RETAINER, PIVOT_CLEVIS_PIN, PIVOT_COTTER):
            chain[("pin seat", support)] = seat
        if stem in (PIVOT_CLEVIS_PIN, PIVOT_COTTER):
            chain[("cross-hole station", support)] = (
                2.0 * printed_band_mm(pivot_pin.LENGTH_PLACES)
                + retention.PIN_CROSS_HOLE_BAND[0] / 2.0
                + (retention_hardware.CLEVIS_DIA_MAX - retention_hardware.CLEVIS_DIA_MIN) / 2.0
            )
        if stem in (PIVOT_CAP_SCREW, PIVOT_LOCK_WIRE):
            chain[("cap height", support)] = printed_band_mm(pivot_cap.HEIGHT_PLACES)
            chain[("head seat", index)] = (printed_band_mm(pivot_cap.COUNTERBORE_DEPTH_PLACES)
                                           + retention.CAP_BASE_SEATING_GAP_MAX + retention.CAP_HEAD_SEATING_GAP_MAX)
        if stem == BEARING:
            chain[("bearing seat depth", index)] = printed_band_mm(3)
            if index % 2:
                chain[("block height", support)] = block
        if stem in (NUT_BRACKET, LEADSCREW_NUT, NUT_SCREW):
            chain[("end bracket height", support)] = printed_band_mm(end_bracket.STOCK_PLACES)
        if stem == NUT_BRACKET:
            chain[("nut bracket seat height", support)] = printed_band_mm(nut_bracket.SEAT_PLACES) + nut_bracket.SPIGOT_FLOAT
        return chain
    if stem in (HOLD_DOWN_STUD, T_NUT):
        return {}
    if stem in (BASE_BAR,):
        return {}
    support = (index if stem == RAIL else index // 7 if stem == RAIL_SCREW else
               index // 4 if stem == BRACKET_SCREW else index // 2 if stem in (FLANGE_NUT, PILLOW_BLOCK) else 0)
    chain = {("bar thickness", support): bar}
    if stem in (PILLOW_BLOCK, PILLOW_BLOCK_SCREW, LEADSCREW, HANDWHEEL):
        chain[("end bracket height", 0)] = printed_band_mm(end_bracket.STOCK_PLACES)
    return chain


def capture_fixture_fitted_retainer_interval() -> tuple[float, float]:
    """C4 fitted thickness from its ONE correlated upper-loaded stack.

    CrossHoleFromSeat = CarrierLength - CrossHoleFromEnd. Neither that
    difference nor the resulting fitted washer is a fixed REF dimension.
    This interval is conditional on C4/C5 actual acceptance; it is not an
    assertion that every independent dimensional extreme is installable.
    """
    station = retention.PIN_CROSS_HOLE_FROM_SEAT
    band = 2.0 * printed_band_mm(pivot_pin.LENGTH_PLACES)
    hole_min = retention.PIN_CROSS_HOLE_DIA
    hole_max = hole_min + retention.PIN_CROSS_HOLE_BAND[0]
    return (
        station - band + hole_min / 2.0 - retention_hardware.CLEVIS_DIA_MAX
        - carrier.THICKNESS - carrier.THICKNESS_BAND - retention.TOP_RUNNING_GAP[1],
        station + band + hole_max / 2.0 - retention_hardware.CLEVIS_DIA_MIN
        - carrier.THICKNESS + carrier.THICKNESS_BAND - retention.TOP_RUNNING_GAP[0],
    )


def capture_fixture_cotter_upset_counterexample() -> dict[str, float | Point3]:
    """A normal-free-only set rejected by quantified primary qualification.

    No dimension changes: select printed-band values and fit the washer.
    The source eye is a ring, not its filled AABB. Lift the carrier by its
    accepted C4 gap without moving the loaded upper hardware. A point
    strictly inside that ring then lies strictly inside the solid carrier.
    Thus normal free swing alone is not an upset external-clearance proof.
    """
    gap = retention.TOP_RUNNING_GAP[1]
    thickness = carrier.THICKNESS + carrier.THICKNESS_BAND
    eye_drop = -pivot_cotter.INSTALLED_Z_MIN - retention_hardware.CLEVIS_DIA / 2.0
    fitted = eye_drop - gap / 2.0
    cross = fitted + thickness + gap + retention_hardware.CLEVIS_DIA - retention.PIN_CROSS_HOLE_DIA / 2.0
    centre = cross + retention.PIN_CROSS_HOLE_DIA / 2.0 - retention_hardware.CLEVIS_DIA / 2.0
    eye_bottom = centre + pivot_cotter.INSTALLED_Z_MIN
    return {
        "carrier_thickness": thickness,
        "running_gap": gap,
        "fitted_retainer_thickness": fitted,
        "cross_hole_from_seat": cross,
        "cross_hole_from_end": pivot_pin.CARRIER_LENGTH - cross,
        "clevis_centre": centre,
        "normal_gap": eye_bottom - thickness,
        "upset_gap": eye_bottom - thickness - gap,
        "witness": (PIVOT_CLEVIS_HEAD_X + retention_hardware.CLEVIS_HOLE_FROM_HEAD,
                    0.0, eye_bottom + gap / 4.0),
    }


def _capture_fixture_carrier_plane_gap(
    stem: str, index: int, points: list[Point3], bounds: retention.CaptureBounds,
) -> float | None:
    """Extend the EXISTING coupled cap/lower-carrier plane separator.

    The head/wire has its actual extent, source bands and actual cap-frame
    lever arm. Shared block top, pin seat, and carrier support stacks cancel
    in this local comparison, rather than being padded independently twice.
    """
    if stem not in (PIVOT_CAP_SCREW, PIVOT_LOCK_WIRE):
        return None
    _root, support = _motion_root(stem, index)
    origin = PLACEMENTS[PIVOT_CAP][support][0]
    radius = max(math.hypot(p[0] - origin[0], p[1] - origin[1]) for p in points)
    top = max(p[2] - origin[2] for p in points)
    top += (printed_band_mm(pivot_cap.HEIGHT_PLACES) + printed_band_mm(pivot_cap.COUNTERBORE_DEPTH_PLACES)
            + retention.CAP_BASE_SEATING_GAP_MAX + retention.CAP_HEAD_SEATING_GAP_MAX)
    edge = printed_band_mm(pivot_cap.OUTLINE_PLACES) + printed_band_mm(pivot_cap.CENTER_LOCATION_PLACES)
    cap_radius = math.hypot(pivot_cap.WIDTH / 2.0 + edge, pivot_cap.LENGTH / 2.0 + edge) + bounds.flange_lateral_shift
    rise = (retention.CAP_VERTICAL_MOTION_ENCLOSURE + radius * math.sin(bounds.cap_tilt)
            + max(abs(p[2] - origin[2]) for p in points) * (1.0 - math.cos(bounds.cap_tilt)))
    return (bounds.cap_running_clearance + retention.CAP_HEIGHT + printed_band_mm(pivot_cap.HEIGHT_PLACES)
            - top + bounds.cap_top_rise - rise + (cap_radius - radius) * math.tan(bounds.carrier_tilt))


def _capture_fixture_upper_axial_shifts() -> tuple[float, float]:
    """Finite EXTERNAL overbound, not a primary washer-bridge proof.

    The enlarged head cannot cross the pin's solid central section. Nor can
    the cotter eye: its lower ring lies below the cross-hole but inside the
    lower part of the carrier journal. Thus the head shoulder remains between
    -hole-from-head and zero. Real perimeter contacts stop it sooner.
    At the extreme of this deliberately loose interval the shaft can leave
    the washer bore: C4 take-up/bridge acceptance must NOT be inferred here.
    """
    cross_r = (retention.PIN_CROSS_HOLE_DIA + retention.PIN_CROSS_HOLE_BAND[0]) / 2.0
    cross_min = retention.PIN_CROSS_HOLE_FROM_SEAT - 2.0 * printed_band_mm(pivot_pin.LENGTH_PLACES)
    eye_drop = -pivot_cotter.INSTALLED_Z_MIN
    if (retention_hardware.CLEVIS_HEAD_DIA_MIN / 2.0 <= cross_r
            or eye_drop <= cross_r or cross_min <= eye_drop):
        raise ValueError("upper keeper source geometry no longer bounds axial clevis endplay")
    return (-retention_hardware.CLEVIS_HOLE_FROM_HEAD - PIVOT_CLEVIS_HEAD_X,
            -PIVOT_CLEVIS_HEAD_X)


def _capture_fixture_retainer_motion(actual_thickness: float | None) -> tuple[float, float, float]:
    """Finite loose-washer motion from its actual full-length cylindrical bore.

    This is only an external enclosure. Actual primary ceiling/bridge and
    carrier contact still need C4/C5 evidence, not disjoint washer/carrier boxes.
    The two bore mouths, including maximum allowed edge breaks, limit
    T*tan(angle) by mouth-pin diametral clearance. Full edge-to-edge
    levers avoid any assumed centre-of-rock or manufactured minimum T.
    """
    low, high = capture_fixture_fitted_retainer_interval()
    if actual_thickness is not None:
        # C4's actual scalar is a measured fitted dimension, not the REF
        # nominal and not a second independent copy of the source fit stack.
        low = high = actual_thickness
    clearance = (pivot_retainer.BORE_DIA + pivot_retainer.DRILLED_BAND[0]
                 + 2.0 * pivot_retainer.EDGE_BREAK_MAX - (pivot_pin.FIT_DIA + pivot_pin.CARRIER_BAND[1]))
    angle = math.atan2(clearance, low)
    radius = (pivot_retainer.OUTER_DIA + printed_band_mm(1)) / 2.0
    lateral = clearance / 2.0 + high * math.sin(angle) + 2.0 * radius * (1.0 - math.cos(angle))
    vertical = 2.0 * radius * math.sin(angle) + high * (1.0 - math.cos(angle))
    return lateral, vertical + retention.TOP_RUNNING_GAP[1], vertical


def capture_fixture_clearance_census(
    *, native_baseline: str | None = None, samples: int = SWEEP_SAMPLES,
    primary_measurements: tuple[PrimaryCaptureMeasurement, ...] | None = None,
) -> dict[tuple[str, str, str], CaptureFixturePairProof]:
    """Finite source proof: all 24 capture instances versus EVERY BOM instance.

    Each unordered physical pair occurs once per pass (self-pairs excluded).
    All four wire pieces remain distinct. Source boxes, printed bands and the
    existing upset enclosure are reused; hold-down stacks include the full
    +/- HOLD_DOWN_ADJUST along their slot whenever an XY separator is credited.
    Rail motion uses the exact PIN_TRAVEL interval. If a global interval box
    cannot separate, simultaneous pose boxes use the existing nearest-sample
    travel allowance on BOTH moving operands, not just sampled clear poses.

    Native baseline + identical ROOT AND INSTANCE preserves nominal relative
    transforms only. It does not establish clearance of independently padded
    upset envelopes. Named capture joints use capture_bounds instead; all
    remaining failed separators are explicitly UNRESOLVED.

    This is conditional source geometry, not as-built acceptance. C2-C5 actual
    gaps, seated heads/registers, full threads, accepted TL-29 fit-up, actual
    purchased dimensions, aligned rails, and measured installed wire/cotter
    envelopes remain prerequisites. Unknown purchased bands are NOT assigned
    invented tolerances. No native ignored pairs or overlap limits are changed.
    """
    if native_baseline is not None and (not isinstance(native_baseline, str) or not native_baseline.strip()):
        raise ValueError("native baseline needs an explicit whole-model evidence authority")
    primary = qualify_primary_capture_measurements(primary_measurements) if primary_measurements is not None else {}
    boxes = _component_local_boxes()
    if set(PLACEMENTS) != set(BOM_ORDER) or set(QUANTITIES) != set(BOM_ORDER):
        raise ValueError("capture/fixture census requires every BOM family")
    for stem in BOM_ORDER:
        if QUANTITIES[stem] <= 0 or len(PLACEMENTS[stem]) != QUANTITIES[stem]:
            raise ValueError(f"capture/fixture census is missing physical instances of {stem}")
    instances = tuple((stem, i) for stem in BOM_ORDER for i in range(QUANTITIES[stem]))
    captures = tuple(item for item in instances if item[0] in CAPTURE_FIXTURE_FAMILIES)
    if len(captures) != 24 or set(trammel.PIN_TRAVEL) != set(trammel.PASS_RADIUS):
        raise ValueError("capture/fixture census requires 24 capture instances and both complete passes")
    bounds = retention.capture_bounds()
    axes = (
        (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0),
        *tuple(axis for rail in RAILS for axis in rail_rows(rail)[:2]),
    )
    local = {
        (item, manufactured): tuple(_box_corners(p) for p in _capture_fixture_source_prisms(*item, boxes, manufactured=manufactured))
        for item in instances for manufactured in (False, True)
    }
    points_by_size = {
        (item, manufactured): [frame_point(PLACEMENTS[item[0]][item[1]], p)
                               for prism in local[item, manufactured] for p in prism]
        for item in instances for manufactured in (False, True)
    }
    height_chains = {item: _capture_fixture_height_chain(*item) for item in instances}
    roots = {item: _motion_root(*item) for item in instances}
    axial_shifts = _capture_fixture_upper_axial_shifts()
    for item in captures:
        if item[0] in (PIVOT_CLEVIS_PIN, PIVOT_COTTER):
            _root, support = roots[item]
            direction = PLACEMENTS[PIVOT_PIN][support][1][0]
            points_by_size[item, True] = [
                tuple(p[a] + shift * direction[a] for a in range(3))
                for p in points_by_size[item, True] for shift in axial_shifts
            ]
    try:
        feed = capture_feed_clearance_bounds()
        feed_failure = None
    except ValueError as exc:
        # A failed old separator must not erase the rest of the finite census.
        # These pairs still get the ordinary source-solid proof or UNRESOLVED.
        feed, feed_failure = {}, str(exc)
    feed_targets = {NUT_BRACKET: "nut bracket", LEADSCREW_NUT: "leadscrew nut", LEADSCREW: "leadscrew"}
    # The accepted F1/F2 theorem has these authored mounting datums.
    # A changed actual obstacle/capture pose must use its real finite
    # primitives, not inherit the old matched-plane shortcut.
    feed_reference = {
        PIVOT_BLOCK: PIVOT_BLOCK_PLACEMENTS,
        PIVOT_CAP: PIVOT_CAP_PLACEMENTS,
        PIVOT_PIN: tuple((origin, PIN_ROWS) for origin in PIVOT_PIN_ORIGINS),
        PIVOT_CAP_SCREW: PIVOT_CAP_SCREW_PLACEMENTS,
        PIVOT_LOCK_WIRE: PIVOT_LOCK_WIRE_PLACEMENTS,
        NUT_BRACKET: (NUT_BRACKET_PLACEMENT,),
        LEADSCREW_NUT: LEADSCREW_NUT_PLACEMENTS,
        LEADSCREW: LEADSCREW_PLACEMENTS,
    }
    result: dict[tuple[str, str, str], CaptureFixturePairProof] = {}
    for pass_name in trammel.PASS_RADIUS:
        travel = fixture_sweep_allowance(pass_name, samples)
        sweep = trammel.SWEEP[pass_name]
        # The original speed proof is retained. Only the extra radius of
        # these directly toleranced carrier primitives is added; the loose
        # installed-tooling padding and its public speed bound are unchanged.
        nominal_carrier_points = [*trammel.pin_pair(pass_name)]
        for stem, index, corners in _component_records().values():
            if _motion_root(stem, index)[0] == CARRIER:
                nominal_carrier_points.extend(_carrier_coordinates(p) for p in corners)
        nominal_radius = max(math.hypot(x, y + trammel.H1) for x, y in nominal_carrier_points)
        source_radius = max(
            math.hypot(x, y + trammel.H1)
            for item in instances if roots[item][0] == CARRIER
            for x, y in (_carrier_coordinates(p) for p in points_by_size[item, True])
        )
        travel += max(0.0, source_radius - nominal_radius) * sweep / (2.0 * (samples - 1))
        if not 0.0 < (trammel.ALPHA - sweep) / 2.0 < (trammel.ALPHA + sweep) / 2.0 < math.pi / 2.0:
            raise ValueError("PIN_TRAVEL separator needs the authored monotone station quadrant")
        pin_min, pin_max = trammel.PIN_TRAVEL[pass_name]
        if not all(math.isfinite(p) for p in (pin_min, pin_max)) or not 0.0 < pin_min <= pin_max:
            raise ValueError("capture/fixture census needs nonempty finite pin travel")
        measured_boxes = {}
        pass_points = dict(points_by_size)
        for item in captures:
            record = primary.get((pass_name, roots[item][1]))
            if record is not None and item[0] in (PIVOT_RETAINER, PIVOT_CLEVIS_PIN, PIVOT_COTTER):
                # Secondary parts retain UNION(source, measured envelope).
                # The fitted washer uses its actual T, retaining printed OD
                # and carrier-thickness bands rather than duplicating the
                # incompatible source fitted-thickness extrema.
                measured_boxes[item] = _box_corners(_primary_capture_box(record, item[0]))
                actual_points = _primary_capture_world_points(record, item[0], PLACEMENTS[PIVOT_PIN][roots[item][1]])
                pass_points[item, True] = actual_points if item[0] == PIVOT_RETAINER else [*points_by_size[item, True], *actual_points]
        upset = {item: _upset_fixture_padding(*item, pass_points[item, True], pass_name, bounds) for item in instances}
        for item in instances:
            if item[0] == PIVOT_RETAINER:
                record = primary.get((pass_name, roots[item][1]))
                extra = _capture_fixture_retainer_motion(None if record is None else record.fitted_retainer_thickness_mm)
                upset[item] = tuple(a + b for a, b in zip(upset[item], extra, strict=True))
        cache: dict[tuple, tuple] = {}

        def projections(item, *, padded: bool, common: bool, theta: float | None = None):
            key = item, padded, common, theta
            if key in cache:
                return cache[key]
            stem, index = item
            root, root_index = roots[item]
            placement = PLACEMENTS[stem][index] if theta is None else _swept_placement(stem, index, pass_name, theta)
            xy, down, up = upset[item] if padded else (0.0, 0.0, 0.0)
            pin_origin = PLACEMENTS[PIVOT_PIN][root_index][0] if root == CARRIAGE else None
            clocked = padded and stem in (PIVOT_CLEVIS_PIN, PIVOT_COTTER)
            if clocked:
                # Replace, do not add to, the old "rectangle + 2R" clocking
                # enclosure. Each source piece sweeps its FULL radial annulus.
                radius = max(math.hypot(p[0] - pin_origin[0], p[1] - pin_origin[1])
                             for p in pass_points[item, True])
                xy -= 2.0 * radius
            projected = []
            pieces = ([] if padded and stem == PIVOT_RETAINER and item in measured_boxes else
                      [(prism, placement, False) for prism in local[item, padded]])
            if padded and item in measured_boxes:
                pin_pose = PLACEMENTS[PIVOT_PIN][root_index] if theta is None else _swept_placement(PIVOT_PIN, root_index, pass_name, theta)
                pieces.append((measured_boxes[item], compose(pin_pose, (0.0, 0.0, pivot_pin.CARRIER_STATION)), True))
            for prism, part_pose, measured in pieces:
                points = [frame_point(part_pose, p) for p in prism]
                clock_radius = 0.0
                clock_centre = None
                if clocked and not measured:
                    clock_centre = _swept_placement(PIVOT_PIN, root_index, pass_name, theta)[0] if theta is not None else pin_origin
                    direction = PLACEMENTS[PIVOT_PIN][root_index][1][0]
                    points = [tuple(p[a] + shift * direction[a] for a in range(3))
                              for p in points for shift in axial_shifts]
                    clock_radius = max(math.hypot(p[0] - clock_centre[0], p[1] - clock_centre[1]) for p in points)
                intervals = []
                for axis in axes:
                    values = [sum(p[a] * axis[a] for a in range(3)) for p in points]
                    lo, hi = min(values), max(values)
                    pad = 0.0
                    if axis[2]:
                        lo -= down
                        hi += up
                        if padded:
                            # Carry these top-face errors as named physical
                            # datums below, so a child located from that SAME
                            # top face does not count its uncertainty twice.
                            if stem == PIVOT_BLOCK:
                                hi -= printed_band_mm(pivot_block.DRAWING_PRECISION_BY_NAME["BlockHeight"])
                            elif stem == PIVOT_CAP:
                                hi -= printed_band_mm(pivot_cap.HEIGHT_PLACES)
                            elif stem == CARRIER:
                                hi -= carrier.THICKNESS_BAND
                            elif stem == RISER:
                                hi -= printed_band_mm(riser.THICKNESS_PLACES)
                            elif stem == FEED_LEVER:
                                hi -= printed_band_mm(feed_lever.THICK_PLACES)
                    else:
                        if clocked and not measured:
                            centre = sum(clock_centre[a] * axis[a] for a in range(3))
                            lo, hi = centre - clock_radius, centre + clock_radius
                        elif stem == PIVOT_PIN:
                            # Each axial source primitive is cylindrical, not
                            # a filled square at its four XY box corners.
                            radius = max(abs(p[0]) for p in prism)
                            centre = sum(part_pose[0][a] * axis[a] for a in range(3))
                            extent = radius * math.hypot(axis[0], axis[1])
                            lo, hi = centre - extent, centre + extent
                        if padded and stem in MOVING:
                            alignment = ALIGNMENT_BAND * (3.0 if root == CARRIER else 1.0)
                            pad += alignment * (abs(axis[0]) + abs(axis[1]))
                        pad += xy * (abs(axis[0]) + abs(axis[1]))
                        if stem in (HOLD_DOWN_STUD, T_NUT, FLANGE_NUT):
                            lateral = rail_rows(RAILS[index // 2])[1]
                            pad += trammel.HOLD_DOWN_ADJUST * abs(sum(a * b for a, b in zip(axis, lateral, strict=True)))
                        if theta is not None and stem in MOVING and not common:
                            pad += travel * (abs(axis[0]) + abs(axis[1]))
                        lo -= pad
                        hi += pad
                    if theta is None and not common and root == CARRIAGE:
                        direction = rail_rows(RAILS[root_index])[0]
                        rate = sum(a * b for a, b in zip(axis, direction, strict=True))
                        offsets = [rate * (p - trammel.PIN_OFFSET - CARRIAGE_STATION) for p in (pin_min, pin_max)]
                        lo += min(offsets)
                        hi += max(offsets)
                    intervals.append((lo, hi))
                projected.append((tuple(intervals), measured))
            cache[key] = tuple(projected)
            return cache[key]

        def separator(first, second, padded: bool) -> float:
            common = roots[first] == roots[second]
            def edge_chain(item, upper, measured):
                chain = dict(height_chains[item])
                stem, index = item
                if measured:
                    # Its measured PIN-seat box already includes the actual
                    # cross-hole station/float: do not add that band again.
                    chain.pop(("cross-hole station", roots[item][1]), None)
                if upper:
                    _root, support = roots[item]
                    if stem == PIVOT_BLOCK:
                        chain["block height", support] = printed_band_mm(pivot_block.DRAWING_PRECISION_BY_NAME["BlockHeight"])
                    elif stem == PIVOT_CAP:
                        chain["cap height", support] = printed_band_mm(pivot_cap.HEIGHT_PLACES)
                    elif stem == CARRIER:
                        chain["carrier thickness", 0] = carrier.THICKNESS_BAND
                    elif stem == RISER:
                        chain["riser thickness", 0] = printed_band_mm(riser.THICKNESS_PLACES)
                    elif stem == FEED_LEVER:
                        chain["lever thickness", 0] = printed_band_mm(feed_lever.THICK_PLACES)
                return chain

            def difference(a, b):
                return sum(abs(a.get(tag, 0.0) - b.get(tag, 0.0)) for tag in a.keys() | b.keys())

            a_modes = (False, True) if padded and first in measured_boxes else (False,)
            b_modes = (False, True) if padded and second in measured_boxes else (False,)
            height_errors = {
                (ma, mb): (
                    difference(edge_chain(first, False, ma), edge_chain(second, True, mb)),
                    difference(edge_chain(second, False, mb), edge_chain(first, True, ma)),
                ) if padded else (0.0, 0.0)
                for ma in a_modes for mb in b_modes
            }

            def gap(theta=None):
                # Two directed face gaps use their own shared-datum chains.
                return min(
                    max(max(a[0] - b[1] - (height_errors[ma, mb][0] if axis == 2 else 0.0),
                            b[0] - a[1] - (height_errors[ma, mb][1] if axis == 2 else 0.0))
                        for axis, (a, b) in enumerate(zip(pa, pb, strict=True)))
                    for pa, ma in projections(first, padded=padded, common=common, theta=theta)
                    for pb, mb in projections(second, padded=padded, common=common, theta=theta)
                )

            if common or all(roots[item][0] != CARRIER for item in (first, second)):
                margin = gap()
                if margin > 0.0 or common:
                    return margin
            # Each sample encloses its closed nearest-sample cell. The positive
            # separating axis can differ between cells and between source prisms.
            return min(gap(theta) for theta in sweep_thetas(pass_name, samples))

        for first in captures:
            for second in instances:
                if first == second:
                    continue
                names = tuple(sorted((instance_name(*first), instance_name(*second))))
                key = (pass_name, *names)
                if key in result:
                    continue
                nominal_gap, upset_gap = separator(first, second, False), separator(first, second, True)
                basis = ["conditional on actual purchased dimensions/installed wire-cotter envelopes being contained by these source primitives, and existing C1-C5/F1-F2 matched-fit acceptance; no as-built or strength certification"]
                if second[0] == CARRIER:
                    plane_gap = _capture_fixture_carrier_plane_gap(*first, points_by_size[first, True], bounds)
                    if plane_gap is not None:
                        nominal_gap, upset_gap = max(nominal_gap, plane_gap), max(upset_gap, plane_gap)
                        if plane_gap > 0.0:
                            basis.append("capture_bounds coupled lower-carrier plane, actual head/wire cap-frame extent and rock/yaw lever; shared support datums cancel")
                families = {first[0], second[0]}
                if first[0] == PIVOT_PIN and second[0] == CARRIAGE and roots[first] == roots[second]:
                    record = primary.get((pass_name, roots[first][1]))
                    if record is not None:
                        upset_gap = max(upset_gap, record.min_tip_recess_mm)
                        basis.append(
                            f"supplied C2A actual pre-bearing hard-capture trial {record.prebearing_capture_evidence}; "
                            f"net minimum tip recess {record.min_tip_recess_mm:g} mm above actual Z0 mounting plane into block, "
                            "actual carriage has no above-plane obstruction; entire free flange/rim motion including tilt, "
                            "not restraint or an invented internal-endplay bound from the pressed bearings"
                        )
                upper = tuple(item for item in (first, second) if item[0] in (PIVOT_CLEVIS_PIN, PIVOT_COTTER))
                if second[0] == CARRIER and upper:
                    record = primary.get((pass_name, roots[upper[0]][1]))
                    if record is not None:
                        measured_gaps = dict(record.min_carrier_secondary_gaps_mm)
                        features = PRIMARY_CAPTURE_SECONDARY_FEATURES[:2] if upper[0][0] == PIVOT_CLEVIS_PIN else PRIMARY_CAPTURE_SECONDARY_FEATURES[2:]
                        upset_gap = max(upset_gap, min(measured_gaps[feature] for feature in features))
                        basis.append(
                            f"supplied actual primary take-up evidence {record.evidence}; max relative travel {record.max_relative_primary_travel_mm:g} mm, "
                            "both full-section shank lands and carrier under-support retained throughout coupled endplay/clock/rock; "
                            "measured carrier/secondary reserve at the established primary ceiling, not a cotter uplift stop"
                        )
                for item in upper:
                    record = primary.get((pass_name, roots[item][1]))
                    if record is not None:
                        basis.append(f"external envelope is UNION(source upper hardware, supplied uncertainty-inclusive PIN-seat XYZ secondary envelope): {record.evidence}")
                joint = _capture_fixture_joint(first, second, bounds, pass_name, primary)
                nominal = "CONTINUOUS_SEPARATOR" if nominal_gap > 0.0 else "UNRESOLVED"
                external = "CONTINUOUS_SEPARATOR" if upset_gap > 0.0 else "UNRESOLVED"
                if nominal == "CONTINUOUS_SEPARATOR" or external == "CONTINUOUS_SEPARATOR":
                    basis.append("positive source-prism projection; exact rail interval or intersample-padded simultaneous poses")
                target = feed_targets.get(second[0])
                own_feed = (roots[first] == roots[second] if second[0] in (NUT_BRACKET, LEADSCREW_NUT)
                            else roots[first][1] == second[1] if second[0] == LEADSCREW else False)
                feed_gap = (feed.get((pass_name, instance_name(*first), target))
                            if target and own_feed and first[0] in feed_reference
                            and PLACEMENTS[first[0]][first[1]] == feed_reference[first[0]][first[1]]
                            and PLACEMENTS[second[0]][second[1]] == feed_reference[second[0]][second[1]]
                            else None)
                if feed_gap is not None:
                    nominal_gap, upset_gap = max(nominal_gap, feed_gap), max(upset_gap, feed_gap)
                    mating_feed = first[0] == PIVOT_BLOCK and second[0] == NUT_BRACKET and roots[first] == roots[second]
                    nominal = external = "SOURCE_FEED_JOINT" if mating_feed else "CONTINUOUS_SEPARATOR"
                    basis.append("accepted TL-29 actual whole-top/transfer-axis fit-up and capture_feed_clearance_bounds")
                common = roots[first] == roots[second]
                if nominal == "UNRESOLVED" and native_baseline is not None:
                    if common:
                        nominal = "NATIVE_BASELINE_INVARIANT"
                        basis.append(f"whole-model native baseline: {native_baseline}; identical motion root AND instance {roots[first]}")
                    elif joint is not None:
                        nominal = "SOURCE_CAPTURE_JOINT"
                        basis.append(f"whole-model native baseline: {native_baseline}")
                if external == "UNRESOLVED" and native_baseline is not None:
                    if joint is not None:
                        external = "SOURCE_CAPTURE_JOINT"
                if joint is not None and (nominal == "SOURCE_CAPTURE_JOINT" or external == "SOURCE_CAPTURE_JOINT"):
                    basis.append(joint)
                # Unknown actual eye/head/end geometry cannot borrow source
                # supplier minima as external maxima, even with a nominal
                # native baseline or the older local feed separator.
                if upper and external != "SOURCE_CAPTURE_JOINT" and any(item not in measured_boxes for item in upper):
                    external = "UNRESOLVED"
                missing = []
                if nominal == "UNRESOLVED":
                    missing.append("nominal: passed whole-model baseline for this exact invariant/joint pair" if common or joint else
                                   f"nominal: source-solid separator for {names}; overlapping enclosures are not clearance")
                if external == "UNRESOLVED":
                    missing.append(f"upset: source-solid external separator or specific mating-surface argument for {names}; nominal baseline alone is insufficient")
                    families = {first[0], second[0]}
                    if families == {PIVOT_PIN, CARRIAGE}:
                        missing.append(
                            f"need C2A actual final boss-fitted pin/block/seated-cap pre-bearing trial: minimum net tip recess >= "
                            f"{retention.PIN_TIP_CARRIAGE_CLEARANCE_MIN:g} mm into block above actual Z0 mounting plane, uncertainty included, "
                            "through ENTIRE free flange/rim capture motion including tilt; actual carriage under pin must have no above-plane obstacle. "
                            "Normal C2 free assembly or assumed pressed-bearing internal endplay is not that lower-tip proof."
                        )
                    if PIVOT_LOCK_WIRE in families:
                        missing.append("wire: this physical installed cubic-control tube/turned-in-tail enclosure loses separation after the cap-frame rock/yaw bound; route/head contacts do not exempt external pairs")
                    if families & {PIVOT_CLEVIS_PIN, PIVOT_COTTER}:
                        missing.append("upper hardware: the UNION of full-clock source-piece bounds, known printed upper-stack bands and any supplied uncertainty-inclusive secondary XYZ box does not positively separate this external pair")
                        if any(item not in measured_boxes for item in upper):
                            missing.append("actual C4/C5 four-pair qualification and uncertainty-inclusive full-coupled PIN-seat secondary XYZ envelope are missing; supplier eye MAX is not published")
                    if PIVOT_RETAINER in families and families & {PIVOT_CLEVIS_PIN, PIVOT_COTTER}:
                        missing.append("need actual full-diameter shank bridge on BOTH retainer bore lands, positive bearing overlap and carrier under-support throughout all endplay; the coarse external head-station interval is not that proof")
                    if CARRIER in families and PIVOT_COTTER in families:
                        witness = capture_fixture_cotter_upset_counterexample()
                        missing.append(
                            f"normal-free-only counterexample rejected by the new actual qualification: fitted retainer {witness['fitted_retainer_thickness']:.4f}, "
                            f"cross-hole-from-seat {witness['cross_hole_from_seat']:.4f}, normal eye gap {witness['normal_gap']:.4f}, "
                            f"eye gap after C4 lift {witness['upset_gap']:.4f} mm; normal C5 free swing is insufficient. "
                            "Need the quantified C4/C5 primary take-up, full bridge/under-support and minimum secondary-gap records, not ordinary normal free swing."
                        )
                    if CARRIER in families and PIVOT_CLEVIS_PIN in families:
                        low, high = capture_fixture_fitted_retainer_interval()
                        missing.append(
                            f"C4 fitted thickness spans {low:.4f}..{high:.4f}, not the REF thickness. "
                            "Need a positive support-local head/washer/carrier contact bound through the allowed relative tilt, "
                            "or actual minimum head-to-carrier reserve for that lift/tilt."
                        )
                if feed_failure is not None and target and missing:
                    missing.append(f"existing feed prerequisite/separator failed: {feed_failure}")
                result[key] = CaptureFixturePairProof(nominal, external, nominal_gap, upset_gap, tuple(basis), tuple(missing))
    expected = len(trammel.PASS_RADIUS) * (len(captures) * (len(instances) - len(captures)) + len(captures) * (len(captures) - 1) // 2)
    if not result or len(result) != expected:
        raise ValueError("capture/fixture pair census is incomplete")
    return result


def require_capture_fixture_clearance(
    *, native_baseline: str | None = None, samples: int = SWEEP_SAMPLES,
    primary_measurements: tuple[PrimaryCaptureMeasurement, ...] | None = None,
) -> dict[tuple[str, str, str], CaptureFixturePairProof]:
    """Refuse unresolved pairs; success remains conditional SOURCE geometry."""
    census = capture_fixture_clearance_census(
        native_baseline=native_baseline, samples=samples, primary_measurements=primary_measurements,
    )
    if native_baseline is None:
        raise ValueError("passed exact whole-model native baseline remains mandatory for fixture acceptance")
    unresolved = [(pair, proof.missing) for pair, proof in census.items() if not proof.source_resolved]
    if unresolved:
        raise ValueError(f"{len(unresolved)} unresolved capture/fixture pair/pass proofs: {unresolved}")
    return census


def captured_fixture_envelopes(
    samples: int = SWEEP_SAMPLES, *,
    primary_measurements: tuple[PrimaryCaptureMeasurement, ...] | None = None,
) -> tuple[tooling.FixtureEnvelope, ...]:
    """Conservative continuous full-sweep AABBs, BOTH passes and all native parts.

    These prisms contain supplied source bounds plus printed size/station bands,
    intersample travel and intact-rigid capture upset. They can overlap empty
    space and yield false potential conflicts. Unmeasured purchased limits,
    machine alignment, deflection and as-installed wire/cotter forms still need
    measured uncertainty in the caller's installed tooling authority.
    Supplied four-record actual secondary bounds are UNIONED with these source
    prisms; their local clock/endplay/rock is already inside the measured box.
    Absence of those records must not become installed-fixture verification.
    """
    capture_feed_clearance_bounds()
    boxes = _component_local_boxes()
    nominal = _component_records(boxes=boxes)
    placement_band, part_bands = _printed_fixture_allowances()
    bounds = retention.capture_bounds()
    primary = {} if primary_measurements is None else qualify_primary_capture_measurements(primary_measurements)
    envelopes = []
    for pass_name in trammel.PASS_RADIUS:
        travel = fixture_sweep_allowance(pass_name, samples)
        extrema: dict[str, list[float]] = {}
        for theta in sweep_thetas(pass_name, samples):
            for name, polygon in moving_outlines(pass_name, theta, _boxes=boxes).items():
                limits = (min(x for x, _ in polygon), max(x for x, _ in polygon),
                          min(y for _, y in polygon), max(y for _, y in polygon))
                stem, index, _points = nominal[name]
                record = primary.get((pass_name, _motion_root(stem, index)[1])) if stem in (PIVOT_RETAINER, PIVOT_CLEVIS_PIN, PIVOT_COTTER) else None
                if record is not None:
                    points = _primary_capture_world_points(record, stem, _swept_placement(PIVOT_PIN, _motion_root(stem, index)[1], pass_name, theta))
                    limits = (min(limits[0], *(p[0] for p in points)), max(limits[1], *(p[0] for p in points)),
                              min(limits[2], *(p[1] for p in points)), max(limits[3], *(p[1] for p in points)))
                if name not in extrema:
                    extrema[name] = list(limits)
                else:
                    current = extrema[name]
                    current[:] = [min(current[0], limits[0]), max(current[1], limits[1]),
                                  min(current[2], limits[2]), max(current[3], limits[3])]
        for name, (x0, x1, y0, y1) in extrema.items():
            stem, index, points = nominal[name]
            source = placement_band + part_bands.get(stem, 0.0)
            lateral, drop, rise = _upset_fixture_padding(stem, index, points, pass_name, bounds)
            xy = source + travel + lateral
            z_min, z_max = min(point[2] for point in points) - source - drop, max(point[2] for point in points) + source + rise
            record = primary.get((pass_name, _motion_root(stem, index)[1])) if stem in (PIVOT_RETAINER, PIVOT_CLEVIS_PIN, PIVOT_COTTER) else None
            if record is not None:
                actual = _primary_capture_world_points(record, stem, PLACEMENTS[PIVOT_PIN][_motion_root(stem, index)[1]])
                actual_xy, actual_drop, actual_rise = _upset_fixture_padding(stem, index, actual, pass_name, bounds)
                if stem in (PIVOT_CLEVIS_PIN, PIVOT_COTTER):
                    origin = PIVOT_PIN_ORIGINS[_motion_root(stem, index)[1]]
                    actual_xy -= 2.0 * max(math.hypot(p[0] - origin[0], p[1] - origin[1]) for p in actual)
                else:
                    extra = _capture_fixture_retainer_motion(record.fitted_retainer_thickness_mm)
                    actual_xy, actual_drop, actual_rise = (a + b for a, b in zip((actual_xy, actual_drop, actual_rise), extra, strict=True))
                xy = max(xy, source + travel + actual_xy)
                z_min = min(z_min, min(p[2] for p in actual) - source - actual_drop)
                z_max = max(z_max, max(p[2] for p in actual) + source + actual_rise)
            envelopes.append(tooling.FixtureEnvelope(
                f"{pass_name}: {name}", tuple(_rect(x0 - xy, x1 + xy, y0 - xy, y1 + xy)),
                z_min, z_max,
            ))
    for name, (stem, _index, points) in nominal.items():
        if stem in MOVING:
            continue
        source = placement_band + part_bands.get(stem, 0.0)
        if stem == PILLOW_BLOCK:
            source += leadscrew.KP08_MARGIN
        envelopes.append(tooling.FixtureEnvelope(
            f"fixed: {name}",
            tuple(_rect(min(p[0] for p in points) - source, max(p[0] for p in points) + source,
                        min(p[1] for p in points) - source, max(p[1] for p in points) + source)),
            min(p[2] for p in points) - source, max(p[2] for p in points) + source,
        ))
    return tuple(envelopes)


def installed_tooling_clearance(
    envelope: tooling.InstalledToolingEnvelope | None = None, *, samples: int = SWEEP_SAMPLES,
    primary_measurements: tuple[PrimaryCaptureMeasurement, ...] | None = None,
) -> tooling.ToolingClearanceReport:
    """Installed acceptance needs BOTH measured tooling and four C4/C5 records.

    With tooling alone the numeric source-prism diagnostic is retained, but
    missing actual primary capture/secondary-shape authority is UNVERIFIED.
    This optional bench boundary is never a mandatory native CAD import gate.
    """
    if envelope is None:
        return tooling.tooling_clearance_report(None, ())
    report = tooling.tooling_clearance_report(
        envelope, captured_fixture_envelopes(samples, primary_measurements=primary_measurements),
    )
    if primary_measurements is None:
        return tooling.ToolingClearanceReport("UNVERIFIED", report.min_clearance, report.limiting_pair, report.authority)
    return report


# --- Native sweep (verify.py ``pass-sweep-interference-free``) ⚙ ----------------
# verify replays the slide's recorded drive (SLIDE_KEY) and walks carriage 1
# through five poses of each pass: both end stops (theta = ±SWEEP, the pass's
# trammel.END_STOPS), the quarter points (±SWEEP/2) and theta 0. End stops
# alone cannot see a mid-sweep collision with a fixed stud or bracket. Each
# pose is reached from its neighbour (SWEEP_VISIT, steps of SWEEP/2 out from
# theta 0 and back), so the linkage re-solves on its own branch, and verify
# reads both carriages back against the calculator before it checks. The
# outer pass starts at its theta-0 station on the inner mates; verify then
# suppresses the inner pin mates and mates holes A2/B2, picking the faces
# through each part's live transform (the sidecar points are part-frame), so
# the re-mate does not depend on how closely the solve hit the station.
# The builder writes sweep_sidecar() beside the DOF manifest; verify.py reads
# that JSON, never this module.
SWEEP_FRACTIONS = (-1.0, -0.5, 0.0, 0.5, 1.0)
SWEEP_VISIT = (2, 1, 0, 1, 2, 3, 4)  # indices into SWEEP_FRACTIONS
SWEEP_POSE_TOLERANCE = 0.05  # mm, a carriage's solved origin from the calculator's


def slide_distance(station: float) -> float:
    """The slide drive's value (mm) with carriage 1 at ``station``: rail 1's
    end face (its Right plane, s = RAIL_NEAR_S) to the carriage's mid-length
    Right plane."""
    return station - trammel.RAIL_NEAR_S


def carriage_origin(rail: int, station: float) -> Point3:
    """Machine origin of the carriage on ``rail`` at ``station``."""
    return (*trammel.rail_point(rail, station), trammel.RAIL_SEAT_Z)


def sweep_poses(pass_name: str) -> list[dict]:
    """``pass_name``'s poses in visit order; ``check`` marks each first visit."""
    sweep = trammel.SWEEP[pass_name]
    seen: set[int] = set()
    poses = []
    for index in SWEEP_VISIT:
        theta = SWEEP_FRACTIONS[index] * sweep
        stations = carriage_stations(pass_name, theta)
        poses.append(
            {
                "theta_rad": theta,
                "drive_mm": slide_distance(stations[SLIDE_RAIL]),
                "check": index not in seen,
                "carriages": {
                    instance_name(CARRIAGE, RAILS.index(rail)): list(
                        carriage_origin(rail, station)
                    )
                    for rail, station in stations.items()
                },
            }
        )
        seen.add(index)
    return poses


def sweep_sidecar() -> dict:
    """The sweep gate's poses and the outer pass's re-mate, as JSON data."""
    remate = {
        "suppress": [label for label, _hole, _pin in PIN_MATES["inner"]],
        "coaxial": [
            {"label": label, "hole": carrier_hole_axis(hole), "pin": pin_axis(pin)}
            for label, hole, pin in PIN_MATES["outer"]
        ],
    }
    return {
        "assembly": ASM_NAME,
        "drive_key": SLIDE_KEY,
        "pose_tolerance_mm": SWEEP_POSE_TOLERANCE,
        "passes": [
            {"pass": "inner", "remate": None, "poses": sweep_poses("inner")},
            {"pass": "outer", "remate": remate, "poses": sweep_poses("outer")},
        ],
    }


# --- Self-checks: the pose closes on the calculator --------------------------------
for _rail, _pin in zip(RAILS, PIVOT_PIN_ORIGINS):
    if math.dist(_pin[:2], trammel.rail_point(_rail, PIN_STATION)) > 1e-9:
        raise AssertionError(f"pivot pin on rail {_rail} is off its station")
for (_origin, _rows), _pin in zip(PIVOT_BLOCK_PLACEMENTS, PIVOT_PIN_ORIGINS):
    _bore = tuple(_origin[i] + pivot_block.BORE_X * _rows[0][i] for i in range(2))
    if math.dist(_bore, _pin[:2]) > 1e-9:
        raise AssertionError("pivot block bore is not on its pin")
if abs(PIN_TOP_Z - (trammel.CARRIER_UNDERSIDE_Z + retention.PIN_CARRIER_JOURNAL_LENGTH)) > 1e-9:
    raise AssertionError("the retained pivot pin journal does not reach its declared end")
if abs(PIN_TOP_Z - PART_TOP_Z - retention.PIN_PROJECTION_ABOVE_WORK_NOMINAL) > 1e-9:
    raise AssertionError("the pin's above-work projection is not represented")
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


def _right_handed(rows: Rows) -> bool:
    """``rows`` orthonormal with determinant +1."""
    unit = all(
        abs(sum(a * b for a, b in zip(rows[i], rows[j])) - (i == j)) < 1e-9
        for i in range(3)
        for j in range(3)
    )
    x, y, z = rows
    det = (
        x[0] * (y[1] * z[2] - y[2] * z[1])
        - x[1] * (y[0] * z[2] - y[2] * z[0])
        + x[2] * (y[0] * z[1] - y[1] * z[0])
    )
    return unit and abs(det - 1.0) < 1e-9


# The bought hardware: one right-handed placement per BOM unit; each carriage
# seats its pivot block; the KP08 bores sit on the leadscrew's axis; the
# rail's holes over the bar's tapped holes, read from the bar's underside on
# rail 1 (the bracket screws come up through bar 1); the underside pick
# clear of the collar and every pin hole; the sweep's end poses at the end stops.
if set(PLACEMENTS) != set(BOM_ORDER) or any(
    len(PLACEMENTS[stem]) != QUANTITIES[stem] for stem in BOM_ORDER
):
    raise AssertionError("one placement per BOM unit")
if not all(_right_handed(_rows) for _all in PLACEMENTS.values() for _o, _rows in _all):
    raise AssertionError("a placement's rows are not a right-handed frame")
for _carriage, (_seat, _rows) in zip(CARRIAGE_PLACEMENTS, PIVOT_BLOCK_PLACEMENTS):
    _top = frame_point(_carriage, (0.0, 0.0, carriage.MOUNTING_FACE_Z))
    if math.dist(_top, _seat) > 1e-9 or _carriage[1] != _rows:
        raise AssertionError("a carriage's mounting face is not its pivot block's seat")
_screw_origin, _screw_rows = LEADSCREW_PLACEMENTS[0]
for _block in PILLOW_BLOCK_PLACEMENTS:
    _bore = frame_point(_block, (0.0, 0.0, pillow_block.AXIS_HEIGHT))
    _off = [_bore[i] - _screw_origin[i] for i in range(3)]
    _along = sum(_off[i] * _screw_rows[1][i] for i in range(3))
    if math.dist(_off, [_along * c for c in _screw_rows[1]]) > 1e-9:
        raise AssertionError("a KP08 bore is off the leadscrew's axis")
# The handwheel's supplied set screw (its first tap) points at the screw's
# set-screw flats, which face the screw's local +X.
_wheel_rows = HANDWHEEL_PLACEMENTS[0][1]
_tap_x, _tap_z = handwheel.SET_SCREW_DIRECTIONS[0]
_tap_out = [_tap_x * _wheel_rows[0][i] + _tap_z * _wheel_rows[2][i] for i in range(3)]
if math.dist(_tap_out, _screw_rows[0]) > 1e-9:
    raise AssertionError("the handwheel's set screw is not clocked to the flats")
if guide_rail.HOLE_X != base_bar.RAIL_HOLE_X or TURNED_OVER[leadscrew.RAIL]:
    raise AssertionError("the rail holes or the bracket screws miss the bar")
if CARRIER_ORIGIN[2] != trammel.CARRIER_TOP_Z:
    raise AssertionError("the carrier's origin (its Top plane) is not its top face")
for _pass, _stops in trammel.END_STOPS.items():
    _ends = [
        carriage_stations(_pass, f * trammel.SWEEP[_pass])[SLIDE_RAIL] for f in (-1, 1)
    ]
    if max(abs(a - b) for a, b in zip(_ends, _stops)) > 1e-9:
        raise AssertionError(f"the {_pass} sweep's end poses are not its end stops")
