r"""Pure placement, BOM and clearance contract for ch-rocker-arm-tl-oblique-jig.SLDASM
(MHA-CH-06-TL-00).

Shop fixture, not a machine assembly (cad/docs/subsystem-identities.md): the
rocker arm's oblique-trammel mill jig, set up on the PM-30MV table. It never
enters the harmonic-analyzer assembly tree or a machine BOM
(``_buildgraph.is_shop_fixture``; test_part_coverage.py). Values marked ⚙ are
read from the calculator ``ch_rocker_arm_tl_oblique_trammel_spec`` (imported as
``trammel``), never retyped.

Material: see the component drawings and purchased-item procurement sheets.
The assembly is saved at the symmetric inner pass. Machine origin is on the
spindle axis at table top; +X along the table, +Y toward the column, +Z up.
Rows give the machine image of each part's local axis.

Rail 1 carries the integral feed block; rail 2 carries the plain pivot block.
Both blocks stand on the carriage tops (``trammel.CARRIAGE_TOP_Z``) and finish
at ``trammel.PIVOT_BLOCK_TOP_Z`` on base bars faced to ``trammel.BASE_BAR_THICK``
(owner ruling 2026-10-30). Selected shims (the nominal pack
``trammel.PIVOT_SHIM_PACK`` a support) and loose spacers support the carrier
at ``trammel.CARRIER_UNDERSIDE_Z``. The sheet prints decimal inch (``UNIT``).
The carrier turns directly on purchased shoulder screws. Their shoulders
bottom in the blocks' counterbores, not on the carrier, and their heads
positively capture it without clamping its running faces.

The leadscrew axis is raised (``leadscrew``). The shop-made feed nut (TL-27) screws directly to the
feed-block lug. KP08 mounting-hole float aligns the screw at both travel ends;
there is no detachable bracket or transfer-spotted interface.

Every fabricated and purchased family has its own BOM row. Shared clamping-kit
members remain three logical rows backed by one configured native model.
PLACEMENTS, QUANTITIES and BOM_ORDER are the builder and drawing authority.

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
intersample clearance or certify the actual installed tooling.

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

from _assembly_contract import assembly_contract
from _printed_tolerance import printed_band_mm
from _title_block_units import LENGTH_UNITS

import ch_rocker_arm_tl_oblique_base_bar_spec as base_bar
import ch_rocker_arm_tl_vn_oblique_pivot_screw_spec as pivot_screw
import ch_rocker_arm_tl_vn_oblique_pivot_spacer_spec as pivot_spacer
import ch_rocker_arm_tl_vn_oblique_pivot_shim_spec as pivot_shim
import ch_rocker_arm_tl_vn_oblique_bracket_screw_spec as bracket_screw
import ch_rocker_arm_tl_vn_oblique_carriage_screw_spec as carriage_screw
import ch_rocker_arm_tl_vn_oblique_carriage_spec as carriage
import ch_rocker_arm_tl_oblique_carrier_spec as carrier
import ch_rocker_arm_tl_vn_oblique_cl_dowel_spec as cl_dowel
import ch_rocker_arm_tl_vn_oblique_clamp_screw_spec as clamp_screw
import ch_rocker_arm_tl_oblique_fasteners_spec as fasteners
import ch_rocker_arm_tl_oblique_feed_lever_spec as feed_lever
import sh_vn_clamping_kit_flange_nut_spec as flange_nut
import ch_rocker_arm_tl_vn_oblique_handwheel_spec as handwheel
import sh_vn_clamping_kit_hold_down_stud_spec as hold_down_stud
import ch_rocker_arm_tl_vn_oblique_hub_pin_spec as hub_pin
import ch_rocker_arm_tl_oblique_feed_nut_spec as feed_nut
import ch_rocker_arm_tl_vn_oblique_leadscrew_spec as leadscrew
import ch_rocker_arm_tl_oblique_feed_block_spec as feed_block
import ch_rocker_arm_tl_vn_oblique_leadscrew_stock_spec as leadscrew_stock
import ch_rocker_arm_tl_vn_oblique_lever_screw_spec as lever_screw
import ch_rocker_arm_tl_vn_oblique_lever_washer_spec as lever_washer
import ch_rocker_arm_tl_vn_oblique_nut_screw_spec as nut_screw
import ch_rocker_arm_tl_vn_oblique_kp08_screw_spec as kp08_screw
import ch_rocker_arm_tl_vn_oblique_pillow_block_spec as pillow_block
import ch_rocker_arm_tl_oblique_pivot_block_spec as pivot_block
import ch_rocker_arm_tl_vn_oblique_rail_screw_spec as rail_screw
import ch_rocker_arm_tl_vn_oblique_rail_spec as guide_rail
import ch_rocker_arm_tl_vn_oblique_riser_screw_spec as riser_screw
import ch_rocker_arm_tl_oblique_riser_spec as riser
import sh_vn_clamping_kit_t_nut_spec as t_nut
import ch_rocker_arm_tl_oblique_trammel_spec as trammel

ASM_NAME = "ch-rocker-arm-tl-oblique-jig"
DRAWING_NUMBER = "MHA-CH-06-TL-00"
# The sheet's unit (the contract's ``drawing_unit``); every printed length
# below goes through ``_length``.
UNIT = assembly_contract(ASM_NAME).drawing_unit


def _length(value_mm: float, places: int) -> str:
    """``value_mm`` as the sheet prints it: ``.080`` or ``-15.250`` in inch."""
    text = f"{value_mm / LENGTH_UNITS[UNIT]:.{places}f}"
    if UNIT == "in":
        text = text.replace("0.", ".", 1) if text.lstrip("-").startswith("0.") else text
    return text


def _bound(value_mm: float, places: int, *, up: bool) -> str:
    """``value_mm`` rounded outward (``up`` or down) to the sheet's ``places``."""
    scale = 10**places / LENGTH_UNITS[UNIT]
    rounded = (math.ceil if up else math.floor)(round(value_mm * scale, 9))
    return _length(rounded / scale, places)


# One in·lbf in N·m (exact: 4.4482216152605 N x 0.0254 m).
_NM_PER_IN_LBF = 4.4482216152605 * 0.0254


def _torque(nm: float) -> str:
    """A tightening torque as the sheet prints it, ``2.8 N·m (25 IN·LBF)``:
    the N·m source value first, its in·lbf conversion in parentheses rounded
    to the nearest two significant figures (owner ruling 3, 2026-11-01)."""
    in_lbf = float(f"{nm / _NM_PER_IN_LBF:.2g}")
    return f"{nm:.1f} N·m ({in_lbf:g} IN·LBF)"



BASE_BAR = "ch-rocker-arm-tl-oblique-base-bar"
PIVOT_BLOCK = "ch-rocker-arm-tl-oblique-pivot-block"
FEED_BLOCK = "ch-rocker-arm-tl-oblique-feed-block"
PIVOT_SCREW = "ch-rocker-arm-tl-vn-oblique-pivot-screw"
PIVOT_SPACER = "ch-rocker-arm-tl-vn-oblique-pivot-spacer"
PIVOT_SHIM = "ch-rocker-arm-tl-vn-oblique-pivot-shim"
CARRIER = "ch-rocker-arm-tl-oblique-carrier"
RISER = "ch-rocker-arm-tl-oblique-riser"
HUB_PIN = "ch-rocker-arm-tl-vn-oblique-hub-pin"
FEED_LEVER = "ch-rocker-arm-tl-oblique-feed-lever"
END_BRACKET = leadscrew.END_BRACKET
FEED_NUT = feed_nut.PART_NAME
# Bought hardware (parent-scoped TL-VN and shared SH-VN-57; VN-72 retired),
# every member modelled and mated.
RAIL = "ch-rocker-arm-tl-vn-oblique-rail"
CARRIAGE = "ch-rocker-arm-tl-vn-oblique-carriage"
CL_DOWEL = "ch-rocker-arm-tl-vn-oblique-cl-dowel"
LEADSCREW = "ch-rocker-arm-tl-vn-oblique-leadscrew"
PILLOW_BLOCK = "ch-rocker-arm-tl-vn-oblique-pillow-block"
HANDWHEEL = "ch-rocker-arm-tl-vn-oblique-handwheel"
CLAMPING_KIT = "sh-vn-clamping-kit-hardware"
HOLD_DOWN_STUD = "sh-vn-clamping-kit-hardware--HoldDownStud"
T_NUT = "sh-vn-clamping-kit-hardware--TNut"
FLANGE_NUT = "sh-vn-clamping-kit-hardware--FlangeNut"
RAIL_SCREW = "ch-rocker-arm-tl-vn-oblique-rail-screw"
BRACKET_SCREW = "ch-rocker-arm-tl-vn-oblique-bracket-screw"
CARRIAGE_SCREW = "ch-rocker-arm-tl-vn-oblique-carriage-screw"
PILLOW_BLOCK_SCREW = "ch-rocker-arm-tl-vn-oblique-kp08-screw"
NUT_SCREW = "ch-rocker-arm-tl-vn-oblique-nut-screw"
RISER_SCREW = "ch-rocker-arm-tl-vn-oblique-riser-screw"
CLAMP_SCREW = "ch-rocker-arm-tl-vn-oblique-clamp-screw"
LEVER_SCREW = "ch-rocker-arm-tl-vn-oblique-lever-screw"
LEVER_LOCK_WASHER = "ch-rocker-arm-tl-vn-oblique-lever-washer"

# Every logical component family and its count: the builder places, the explode
# moves and the drawing proves this inventory in its established item order.
# The bought counts are each member's own, never the number of purchased kits.
QUANTITIES = {
    BASE_BAR: base_bar.QUANTITY,
    CARRIER: 1,
    PIVOT_BLOCK: 1,
    FEED_BLOCK: 1,
    PIVOT_SCREW: pivot_screw.QUANTITY,
    PIVOT_SPACER: pivot_spacer.QUANTITY,
    PIVOT_SHIM: pivot_shim.QUANTITY,
    RISER: 1,
    HUB_PIN: 1,
    FEED_LEVER: 1,
    END_BRACKET: leadscrew.END_BRACKET_QUANTITY,
    RAIL: fasteners.RAILS,
    CARRIAGE: fasteners.RAILS,
    CL_DOWEL: cl_dowel.QUANTITY,
    LEADSCREW: leadscrew_stock.QUANTITY,
    FEED_NUT: feed_nut.QUANTITY,
    PILLOW_BLOCK: pillow_block.QUANTITY,
    HANDWHEEL: handwheel.QUANTITY,
    HOLD_DOWN_STUD: hold_down_stud.QUANTITY,
    T_NUT: t_nut.QUANTITY,
    FLANGE_NUT: flange_nut.QUANTITY,
    RAIL_SCREW: rail_screw.QUANTITY,
    BRACKET_SCREW: bracket_screw.QUANTITY,
    CARRIAGE_SCREW: carriage_screw.QUANTITY,
    PILLOW_BLOCK_SCREW: kp08_screw.QUANTITY,
    NUT_SCREW: nut_screw.QUANTITY,
    RISER_SCREW: riser_screw.QUANTITY,
    CLAMP_SCREW: clamp_screw.QUANTITY,
    LEVER_SCREW: lever_screw.QUANTITY,
    LEVER_LOCK_WASHER: lever_washer.QUANTITY,
}
# SolidWorks numbers a top-level BOM in FeatureManager order, so BOM_ORDER is
# the builder's insertion order (the builder asserts it) and the steps' item
# numbers (``_item``, ITEM_NUMBERS) read it (c4-r10, rule 25).
BOM_ORDER = (
    BASE_BAR,
    CARRIER,
    PIVOT_BLOCK,
    FEED_BLOCK,
    PIVOT_SCREW,
    PIVOT_SPACER,
    PIVOT_SHIM,
    RISER,
    HUB_PIN,
    FEED_LEVER,
    END_BRACKET,
    RAIL,
    CARRIAGE,
    CL_DOWEL,
    LEADSCREW,
    FEED_NUT,
    PILLOW_BLOCK,
    HANDWHEEL,
    HOLD_DOWN_STUD,
    T_NUT,
    FLANGE_NUT,
    RAIL_SCREW,
    BRACKET_SCREW,
    CARRIAGE_SCREW,
    PILLOW_BLOCK_SCREW,
    NUT_SCREW,
    RISER_SCREW,
    CLAMP_SCREW,
    LEVER_SCREW,
    LEVER_LOCK_WASHER,
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

# One block at each carriage, in rail order. The separate native families have
# one occurrence each, but the support-order tuple is useful for the two pivots.
BLOCK_PLACEMENTS: tuple[tuple[Point3, Rows], ...] = tuple(
    (
        (*trammel.rail_point(rail, CARRIAGE_STATION), trammel.CARRIAGE_TOP_Z),
        rail_rows(rail),
    )
    for rail in RAILS
)
FEED_BLOCK_PLACEMENTS = (BLOCK_PLACEMENTS[0],)
PIVOT_BLOCK_PLACEMENTS = (BLOCK_PLACEMENTS[1],)
IDENTITY_ROWS: Rows = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
PIN_ROWS = _rz(POSE.rotation, IDENTITY_ROWS)
PIVOT_SCREW_BOTTOM_Z = trammel.PIVOT_BLOCK_TOP_Z - pivot_block.BORE_DEPTH
PIVOT_SCREW_ORIGINS: tuple[Point3, ...] = tuple(
    _at(pin, PIVOT_SCREW_BOTTOM_Z) for pin in trammel.pin_pair(PASS)
)

# Carrier: the SolidWorks model is Y-up (model X = carrier X, model Y = carrier
# Z, model Z = -carrier Y; carrier_spec), origin at the A1-B1 midpoint on the
# top face.
CARRIER_ORIGIN = _at((0.0, 0.0), trammel.CARRIER_TOP_Z)
CARRIER_ROWS = _rz(POSE.rotation, ((1.0, 0.0, 0.0), (0.0, 0.0, 1.0), (0.0, -1.0, 0.0)))

# Riser: Z-up, origin at the blank corner RISER_BLANK_ORIGIN ⚙ on its bottom
# face, axes parallel to the carrier's.
RISER_ORIGIN = _at(riser.BLANK_ORIGIN, trammel.CARRIER_TOP_Z)
RISER_ROWS = PIN_ROWS

# The cut gauge pin is bonded in the carrier's HUB hole, factory end up, its
# top set hub_pin.TIP_SET above the riser; its bottom lands on the underside.
HUB_SET_ABOVE_RISER = hub_pin.TIP_SET
HUB_PIN_TOP_Z = trammel.CARRIER_TOP_Z + trammel.RISER_THICK + HUB_SET_ABOVE_RISER
HUB_PIN_ORIGIN = _at(trammel.HUB, HUB_PIN_TOP_Z - hub_pin.CUT_LENGTH)
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

# --- Heights ⚙ ---------------------------------------------------------------------
RAIL_TOP_Z = trammel.RAIL_SEAT_Z + trammel.RAIL_HEIGHT  # 27.0
CARRIAGE_UNDERSIDE_Z = trammel.RAIL_SEAT_Z + trammel.CARRIAGE_UNDER  # 16.3
HUB_PIN_BOTTOM_Z = HUB_PIN_ORIGIN[2]
PIVOT_HEAD_UNDERSIDE_Z = PIVOT_SCREW_BOTTOM_Z + pivot_screw.SHOULDER_LENGTH
PIVOT_HEAD_TOP_Z = PIVOT_HEAD_UNDERSIDE_Z + pivot_screw.HEAD_HEIGHT
PART_TOP_Z = trammel.CARRIER_TOP_Z + trammel.RISER_THICK + trammel.STRAP_THICK

# --- Hold-down studs: reworked length on the reference installed stack ------------
# PM-30MV T-slot throat/foot depths are unmeasured reference estimates owned
# by t_nut, not universal machine or delivered-kit tolerances. Procurement
# remains the kit's 3 in stock; only its unused upper end is shortened.
# Sheet 9's HD1-HD4 (HOLD_DOWN_STEPS) own the measured installed-stack
# acceptance after final nut seating: clear every moving block and
# preserve every loaded thread. The stud drawing cites HOLD_DOWN_REFERENCE.
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
# Conventional screws, studs, nuts and the dowel use local +Y.
# UPRIGHT puts +Y on the parent's +Z; HEAD_DOWN puts it on -Z.
UPRIGHT_ROWS: Rows = ((1.0, 0.0, 0.0), (0.0, 0.0, 1.0), (0.0, -1.0, 0.0))
HEAD_DOWN_ROWS: Rows = ((1.0, 0.0, 0.0), (0.0, 0.0, -1.0), (0.0, 1.0, 0.0))


def _image(rows: Rows, vector: Point3) -> Point3:
    """``vector`` in a frame with ``rows``, in the parent's axes.

    Unrolled, with ``sum``'s own starting ``0`` and left-to-right order, so
    each component is the same float the generator sum produced (signed
    zeros included); the sweep calls this millions of times."""
    v0, v1, v2 = vector
    r0, r1, r2 = rows
    return (
        0 + v0 * r0[0] + v1 * r1[0] + v2 * r2[0],
        0 + v0 * r0[1] + v1 * r1[1] + v2 * r2[1],
        0 + v0 * r0[2] + v1 * r1[2] + v2 * r2[2],
    )


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
    """Machine image of a part-frame ``point`` of the part at ``placement``.

    ``compose(placement, point)[0]``, without also rotating the three frame
    rows that ``compose`` would build and this caller discards."""
    base, rows = placement
    offset = _image(rows, point)
    return tuple(base[axis] + offset[axis] for axis in range(3))


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
# The new purchased parts all use model +Z, not the generic screw +Y frame.
PIVOT_SCREW_PLACEMENTS: tuple[Placement, ...] = tuple(
    (origin, PIN_ROWS) for origin in PIVOT_SCREW_ORIGINS
)
# Each support's nominal pack: PER_SUPPORT shims stacked on the block top,
# support-major (the order of LOCKED_TO's parents).
PIVOT_SHIM_PLACEMENTS: tuple[Placement, ...] = tuple(
    (_at(pin, trammel.PIVOT_BLOCK_TOP_Z + k * pivot_shim.THICKNESS), PIN_ROWS)
    for pin in trammel.pin_pair(PASS)
    for k in range(pivot_shim.PER_SUPPORT)
)
PIVOT_SPACER_PLACEMENTS: tuple[Placement, ...] = tuple(
    (_at(pin, trammel.PIVOT_BLOCK_TOP_Z + trammel.PIVOT_SHIM_PACK), PIN_ROWS)
    for pin in trammel.pin_pair(PASS)
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
# The shop-made TL-27 nut seats on the integral lug's -X face, proud toward
# the spindle, its bore on the leadscrew axis: its +X runs along the block's
# -Y (toward the lug end), +Y up, +Z along -X; its frame's origin is the
# seat face's -X/bottom corner. The two socket heads bear directly on its
# far face, each screw's +Y (head) along the block's -X.
FEED_NUT_ROWS: Rows = ((0.0, -1.0, 0.0), (0.0, 0.0, 1.0), (-1.0, 0.0, 0.0))
FEED_NUT_PLACEMENTS = (
    compose(
        FEED_BLOCK_PLACEMENTS[0],
        (
            feed_block.NUT_FACE_X,
            feed_block.NUT_AXIS_Y + feed_nut.BORE_X,
            feed_block.NUT_AXIS_Z - feed_nut.BORE_Y,
        ),
        FEED_NUT_ROWS,
    ),
)
NUT_ROWS: Rows = ((0.0, 1.0, 0.0), (-1.0, 0.0, 0.0), (0.0, 0.0, 1.0))
NUT_SCREW_PLACEMENTS: tuple[Placement, ...] = tuple(
    compose(
        FEED_BLOCK_PLACEMENTS[0],
        (feed_block.NUT_FACE_X - feed_nut.LENGTH, y, z),
        NUT_ROWS,
    )
    for y, z in feed_block.NUT_HOLES_YZ
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
# Screws, head on its seat: rail 1's seven then rail 2's; bracket screws up
# from bar 1's underside; four per block into its carriage; two per KP08.
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
CARRIAGE_SCREW_PLACEMENTS: tuple[Placement, ...] = tuple(
    compose(block, (*point, pivot_block.CBORE_FLOOR), UPRIGHT_ROWS)
    for block in BLOCK_PLACEMENTS
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

# The screw head is the positive carrier lift stop. The shoulder's seating
# plane is independent of the selected support shims. Owner ruling
# 2026-10-31: the measured head-to-carrier running gap is .002-.010, and the
# cut thread's tip stands at least .011 above the block bottom.
_THOU = trammel.INCH / 1000.0
PIVOT_RUNNING_GAP = (2 * _THOU, 10 * _THOU)  # .002-.010
PIVOT_TIP_CLEARANCE_MIN = 11 * _THOU  # .011
PIVOT_SCREW_TORQUE_NM = 4.0
PIVOT_NOMINAL_RUNNING_GAP = PIVOT_HEAD_UNDERSIDE_Z - trammel.CARRIER_TOP_Z
PIVOT_THREAD_ENGAGEMENT = pivot_block.PIVOT_THREAD_ENGAGEMENT  # full form, .487 nominal
PIVOT_THREAD_TIP_Z = PIVOT_SCREW_BOTTOM_Z - pivot_screw.THREAD_LENGTH
if not PIVOT_RUNNING_GAP[0] <= PIVOT_NOMINAL_RUNNING_GAP <= PIVOT_RUNNING_GAP[1]:
    raise AssertionError("the nominal shoulder head must clear the carrier inside the window")
if PIVOT_THREAD_TIP_Z - trammel.CARRIAGE_TOP_Z < PIVOT_TIP_CLEARANCE_MIN - 1e-9:
    raise AssertionError("the shoulder-screw tip must stand inside the block")
if pivot_block.PIVOT_TIP_CLEARANCE_MIN < PIVOT_TIP_CLEARANCE_MIN - 1e-9:
    raise AssertionError("the shoulder-screw tip reaches the block bottom at the worst case")
# Rule 18 at the worst case: the cut thread's full form is at least 1.5D.
if pivot_block.PIVOT_THREAD_ENGAGEMENT_MIN < 1.5 * pivot_screw.THREAD_DIA:
    raise AssertionError("the pivot receiver's full-form engagement is under 1.5D")
if PIVOT_THREAD_ENGAGEMENT != fasteners.PIVOT_SCREW_TO_BLOCK.engagement_mm:
    raise AssertionError("the fastener table's pivot engagement is not the block's")
# Radially, the shoulder clears its block seat and the carrier's pin holes, and
# the spacer and shim bores clear the shoulder: no member locates on another.
_SHOULDER_MAX = pivot_screw.SHOULDER_DIA + pivot_screw.SHOULDER_DIA_BAND[0]
if pivot_block.PIVOT_LOCATING_CLEARANCE_MIN <= 0.0:
    raise AssertionError("the shoulder does not clear its block seat")
if carrier.PIN_HOLE_DIA + min(carrier.PIN_HOLE_BAND) <= _SHOULDER_MAX:
    raise AssertionError("the shoulder does not clear the carrier's pin holes")
if pivot_spacer.ID + min(pivot_spacer.ID_BAND) <= _SHOULDER_MAX:
    raise AssertionError("the spacer bore does not clear the shoulder")
if pivot_shim.ID + min(pivot_shim.ID_BAND) <= _SHOULDER_MAX:
    raise AssertionError("the shim bore does not clear the shoulder")

# With every stack member at its band (the shoulder length at its +/-.005
# envelope, seat depth at its printed places, spacer +/-.005, carrier at .XX)
# the unshimmed head gap stays open; shims, which only close it, are the
# fitting adjustment that brings the measured gap into PIVOT_RUNNING_GAP.
_SEAT_BAND = printed_band_mm(
    pivot_block.DRAWING_PRECISION_BY_NAME["TopBoreDepth"], unit=pivot_block.UNIT,
)
_UNSHIMMED_NOMINAL = (
    pivot_screw.SHOULDER_LENGTH - pivot_block.BORE_DEPTH - pivot_spacer.LENGTH - trammel.CARRIER_THICK
)
# Bands are (upper, lower) deviations.
PIVOT_UNSHIMMED_GAP_RANGE = (
    _UNSHIMMED_NOMINAL + pivot_screw.SHOULDER_LENGTH_BAND[1] - _SEAT_BAND
    - pivot_spacer.LENGTH_BAND[0] - trammel.CARRIER_THICK_BAND,
    _UNSHIMMED_NOMINAL + pivot_screw.SHOULDER_LENGTH_BAND[0] + _SEAT_BAND
    - pivot_spacer.LENGTH_BAND[1] + trammel.CARRIER_THICK_BAND,
)  # .021 .. .071
if abs(trammel.PIVOT_SHIM_PACK - pivot_shim.PER_SUPPORT * pivot_shim.THICKNESS) > 1e-9:
    raise AssertionError("the modeled shim pack is not PER_SUPPORT TL-VN-79 shims")
# Every unshimmed gap in the range reaches the window with a pack in steps of
# the thinnest fitting shim (.004), checked at every .001 across the range.
_FIT_THOU = sorted(pivot_shim.FIT_SKUS)  # .004, .008, .020
_STEP = _FIT_THOU[0]
if any(thou % _STEP for thou in _FIT_THOU):
    raise AssertionError("a fitting shim is not a whole number of .004 steps")
_GAP_LO, _GAP_HI = (round(g / _THOU) for g in PIVOT_UNSHIMMED_GAP_RANGE)
_WIN_LO, _WIN_HI = (round(g / _THOU) for g in PIVOT_RUNNING_GAP)
if _GAP_LO < _WIN_LO:
    raise AssertionError("an unshimmed head can clamp the carrier at the worst case")
for _gap in range(_GAP_LO, _GAP_HI + 1):
    if not any(_WIN_LO <= _gap - _STEP * n <= _WIN_HI for n in range(_gap // _STEP + 1)):
        raise AssertionError(f"no shim pack fits a .{_gap:03d} unshimmed gap")
if not _WIN_LO <= round(PIVOT_NOMINAL_RUNNING_GAP / _THOU) <= _WIN_HI:
    raise AssertionError("the nominal pack does not fit the nominal stack")
# The thickest pack the worst case needs (.064), and the fewest stock shims
# making it (4: three .020 and one .004; greedy is exact for .020/.008/.004).
_PACK_MAX_THOU = math.ceil((_GAP_HI - _WIN_HI) / _STEP) * _STEP
PIVOT_FIT_PACK_MAX = _PACK_MAX_THOU * _THOU
_WORST_PACK: dict[int, int] = {}  # thou -> shims
_rest = _PACK_MAX_THOU
for _thou in reversed(_FIT_THOU):
    _WORST_PACK[_thou], _rest = divmod(_rest, _thou)
PIVOT_FIT_SHIMS_MAX = sum(_WORST_PACK.values())
# Owner ruling 2026-10-27: TL-VN-79 stays one BOM identity, QTY its modeled
# nominal pack (5 x .008 a support); the fitting stock bought with it is that
# pack plus the worst-case pack at both supports. Each support's share of the
# buy builds every pack up to the worst case, so both fit at once.
_SUPPORTS = pivot_shim.QUANTITY // pivot_shim.PER_SUPPORT  # 2
_BUY_THOU = {thou: _SUPPORTS * count for thou, count in _WORST_PACK.items()}
_BUY_THOU[pivot_shim.THICKNESS_THOU] += pivot_shim.QUANTITY
# SKU -> (thickness mm, count), thinnest first: .004 x2, .008 x10, .020 x6.
PIVOT_SHIM_BUY = {
    pivot_shim.FIT_SKUS[thou]: (thou * _THOU, _BUY_THOU[thou]) for thou in _FIT_THOU
}
if any(count % _SUPPORTS for count in _BUY_THOU.values()):
    raise AssertionError("the shim buy list does not split evenly between the supports")
_BUILDABLE = {0}
for _thou, _count in _BUY_THOU.items():
    _BUILDABLE = {
        built + k * _thou for built in _BUILDABLE for k in range(_count // _SUPPORTS + 1)
    }
if not set(range(0, _PACK_MAX_THOU + 1, _STEP)) <= _BUILDABLE:
    raise AssertionError("the shim buy list cannot build every fitting pack at both supports")

# Every instance of every logical family, in insertion order. Ordinary families
# keep native <stem>-N names; kit instances use persisted role-local references.
PLACEMENTS: dict[str, tuple[Placement, ...]] = {
    BASE_BAR: BASE_BAR_PLACEMENTS,
    CARRIER: ((CARRIER_ORIGIN, CARRIER_ROWS),),
    PIVOT_BLOCK: PIVOT_BLOCK_PLACEMENTS,
    FEED_BLOCK: FEED_BLOCK_PLACEMENTS,
    PIVOT_SCREW: PIVOT_SCREW_PLACEMENTS,
    PIVOT_SPACER: PIVOT_SPACER_PLACEMENTS,
    PIVOT_SHIM: PIVOT_SHIM_PLACEMENTS,
    RISER: ((RISER_ORIGIN, RISER_ROWS),),
    HUB_PIN: ((HUB_PIN_ORIGIN, HUB_PIN_ROWS),),
    FEED_LEVER: ((FEED_LEVER_ORIGIN, FEED_LEVER_ROWS),),
    END_BRACKET: END_BRACKET_PLACEMENTS,
    RAIL: RAIL_PLACEMENTS,
    CARRIAGE: CARRIAGE_PLACEMENTS,
    CL_DOWEL: CL_DOWEL_PLACEMENTS,
    LEADSCREW: LEADSCREW_PLACEMENTS,
    FEED_NUT: FEED_NUT_PLACEMENTS,
    PILLOW_BLOCK: PILLOW_BLOCK_PLACEMENTS,
    HANDWHEEL: HANDWHEEL_PLACEMENTS,
    HOLD_DOWN_STUD: HOLD_DOWN_STUD_PLACEMENTS,
    T_NUT: T_NUT_PLACEMENTS,
    FLANGE_NUT: FLANGE_NUT_PLACEMENTS,
    RAIL_SCREW: RAIL_SCREW_PLACEMENTS,
    BRACKET_SCREW: BRACKET_SCREW_PLACEMENTS,
    CARRIAGE_SCREW: CARRIAGE_SCREW_PLACEMENTS,
    PILLOW_BLOCK_SCREW: PILLOW_BLOCK_SCREW_PLACEMENTS,
    NUT_SCREW: NUT_SCREW_PLACEMENTS,
    RISER_SCREW: RISER_SCREW_PLACEMENTS,
    CLAMP_SCREW: CLAMP_SCREW_PLACEMENTS,
    LEVER_SCREW: LEVER_SCREW_PLACEMENTS,
    LEVER_LOCK_WASHER: LEVER_LOCK_WASHER_PLACEMENTS,
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
SLIDE_RAIL = leadscrew.RAIL
# One exact parent per occurrence. The two block designs belong to different
# carriages, while the two identical pivot stacks follow those two blocks.
_SUPPORT_PARENTS = ((FEED_BLOCK, 0), (PIVOT_BLOCK, 0))
LOCKED_TO: dict[str, tuple[tuple[str, int], ...]] = {
    FEED_BLOCK: ((CARRIAGE, 0),),
    PIVOT_BLOCK: ((CARRIAGE, 1),),
    PIVOT_SCREW: _SUPPORT_PARENTS,
    PIVOT_SPACER: _SUPPORT_PARENTS,
    PIVOT_SHIM: tuple(parent for parent in _SUPPORT_PARENTS for _ in range(pivot_shim.PER_SUPPORT)),
    CARRIAGE_SCREW: tuple(parent for parent in _SUPPORT_PARENTS for _ in pivot_block.BOLT_POINTS),
    FEED_NUT: ((FEED_BLOCK, 0),),
    NUT_SCREW: tuple((FEED_BLOCK, 0) for _ in feed_block.NUT_HOLES_YZ),
    RISER: ((CARRIER, 0),),
    RISER_SCREW: tuple((CARRIER, 0) for _ in trammel.RISER_SCREWS),
    HUB_PIN: ((CARRIER, 0),),
    FEED_LEVER: ((CARRIER, 0),),
    LEVER_SCREW: tuple((CARRIER, 0) for _ in carrier.LEVER_HOLES),
    CL_DOWEL: ((CARRIER, 0),),
    CLAMP_SCREW: ((CARRIER, 0),),
    LEVER_LOCK_WASHER: tuple((CARRIER, 0) for _ in carrier.LEVER_HOLES),
}
# Every family that rides the sweep, in BOM order: the contract's allowed and
# required free stems.
MOVING = tuple(stem for stem in BOM_ORDER if stem in (CARRIAGE, CARRIER, *LOCKED_TO))


def lock_parent(stem: str, index: int) -> str:
    """The instance that ``stem``'s instance ``index`` (0-based) is locked to."""
    parent, parent_index = LOCKED_TO[stem][index]
    return instance_name(parent, parent_index)


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
    """Shoulder screw instance's named axis, qualified by the native component."""
    return f"{pivot_screw.AXIS_NAME}@{instance_name(PIVOT_SCREW, pin)}"


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
    FEED_BLOCK: "FEED BLOCK",
    PIVOT_SCREW: "5/16-18 SHOULDER SCREW, 3/8 X 1-1/2",
    PIVOT_SPACER: "SPACER, 3/8 ID X 5/8 OD X 5/8",
    PIVOT_SHIM: "SHIM 3/8 X 5/8, FITTING STOCK",
    CARRIER: "CARRIER PLATE",
    RISER: "ACETAL RISER",
    HUB_PIN: "HUB LOCATOR PIN",
    FEED_LEVER: "FEED LEVER",
    END_BRACKET: "END BRACKET",
    RAIL: (
        f"HGR15R RAIL, {trammel.RAIL_LENGTH:.0f} MM, "
        f"E{trammel.RAIL_HOLE_END:.0f} MM BOTH ENDS"
    ),
    CARRIAGE: "HGH15CA CARRIAGE, Z0 PRELOAD",
    CL_DOWEL: "DOWEL PIN 1/4 X 1, CL LOCATOR",
    # Vendor-metric rows keep their millimetres, labelled (#290).
    LEADSCREW: f"TR8X2 LEADSCREW, {leadscrew_stock.LENGTH:.0f} MM LONG",
    FEED_NUT: "FEED NUT",
    PILLOW_BLOCK: f"PILLOW BLOCK, {leadscrew.KP08_BORE:.0f} MM BORE, SET SCREWS",
    HANDWHEEL: f"HANDWHEEL {leadscrew.HANDWHEEL_WHEEL_DIA:.0f} MM DIA, 8 MM BORE",
    HOLD_DOWN_STUD: hold_down_stud.BOM_DESCRIPTION,
    T_NUT: t_nut.BOM_DESCRIPTION,
    FLANGE_NUT: flange_nut.BOM_DESCRIPTION,
    RAIL_SCREW: rail_screw.CALLOUT,
    BRACKET_SCREW: bracket_screw.CALLOUT,
    CARRIAGE_SCREW: carriage_screw.CALLOUT,
    PILLOW_BLOCK_SCREW: kp08_screw.CALLOUT,
    NUT_SCREW: nut_screw.CALLOUT,
    RISER_SCREW: f"{riser_screw.CALLOUT} SCREW",
    CLAMP_SCREW: clamp_screw.CALLOUT,
    LEVER_SCREW: lever_screw.CALLOUT,
    LEVER_LOCK_WASHER: f"{lever_washer.SCREW_SIZE} WEDGE-LOCK WASHER PAIR",
}
# BOM item n is BOM_ORDER position n: the builder inserts each family's first
# instance in BOM_ORDER sequence (SolidWorks numbers a top-level BOM in
# FeatureManager order), and the steps cite items by these numbers.
ITEM_NUMBERS = {stem: str(index) for index, stem in enumerate(BOM_ORDER, 1)}

# --- Native explode (JIG_EXPLODED) -------------------------------------------------
# Presentation separates each purchased pivot member above its block and the
# carrier above its supports. The bonded hub locator is shown below the
# carrier for identification, not as an instruction for destructive removal.
# (label, selectors, axis, signed distance mm).
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
_BLOCK_RIDERS = (CARRIAGE_SCREW, FEED_NUT, NUT_SCREW, PIVOT_SHIM, PIVOT_SPACER)
EXPLODE_STEPS = (
    ("shoulder screws withdraw", (PIVOT_SCREW,), "z", 250.0),
    ("spacers lift off", (PIVOT_SPACER,), "z", 45.0),
    ("shims lift off", (PIVOT_SHIM,), "z", 15.0),
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
    ("bonded hub locator identification", (HUB_PIN,), "z", -150.0),
    # The dowel goes in from above, down through the riser (step 11), so it
    # lifts out as the clamp screw does, clear above the lifted riser.
    ("cl dowel lifts out", (CL_DOWEL,), "z", 100.0),
    ("nut screws back out", (NUT_SCREW,), "x", 30.0),
    ("blocks lift off", (PIVOT_BLOCK, FEED_BLOCK, *_BLOCK_RIDERS), "z", 90.0),
    ("carriage screws lift out", (CARRIAGE_SCREW,), "z", 60.0),
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


def explode_shift(component_or_family: str, axis: str) -> float:
    """Signed machine-axis presentation shift (mm) of an occurrence or family.

    A family has no common shift on an axis whose occurrences separate; callers
    projecting real geometry must use ``instance_name(stem, index)`` instead.
    Kit occurrences use their persisted role-local references, never the shared
    part file's native instance suffixes.
    """
    if component_or_family in QUANTITIES:
        family = component_or_family
        names = tuple(instance_name(family, index) for index in range(QUANTITIES[family]))
    else:
        identity = KIT_COMPONENT_REFERENCES.get(component_or_family)
        if identity is not None:
            family = component_family(*identity)
        else:
            family, _separator, _suffix = component_or_family.rpartition("-")
        if family not in QUANTITIES or component_or_family not in (
            instance_name(family, index) for index in range(QUANTITIES[family])
        ):
            raise ValueError(f"unknown explode occurrence: {component_or_family!r}")
        names = (component_or_family,)
    shifts = {
        sum(
            distance
            for _label, selectors, step_axis, distance in EXPLODE_STEPS
            if step_axis == axis and (family in selectors or name in selectors)
        )
        for name in names
    }
    if len(shifts) != 1:
        raise ValueError(
            f"{component_or_family}: nonuniform exploded {axis.upper()} displacement; "
            "use an exact instance_name(stem, index)"
        )
    return shifts.pop()


def explode_lift(component_or_family: str) -> float:
    """Signed machine-Z presentation shift (mm); reject nonuniform families."""
    return explode_shift(component_or_family, "z")


_CARRIER_UNDERSIDE_EXPLODED = trammel.CARRIER_UNDERSIDE_Z + explode_lift(CARRIER)
if (
    _CARRIER_UNDERSIDE_EXPLODED - (HUB_PIN_TOP_Z + explode_lift(HUB_PIN))
    <= trammel.HUB[1] - carrier.OUTLINE_Y[0]
):
    raise AssertionError("the exploded carrier hides the HUB pin")
# The riser must clear the HUB pin's locator before it moves sideways.
if explode_lift(RISER) - explode_lift(CARRIER) <= HUB_PIN_TOP_Z - trammel.CARRIER_TOP_Z:
    raise AssertionError("the exploded riser does not clear the HUB pin")
_instances = {
    instance_name(family, index)
    for family in BOM_ORDER
    for index in range(QUANTITIES[family])
}
_moved: set[str] = set()
for _label, _selectors, _axis, _distance in EXPLODE_STEPS:
    for _selector in _selectors:
        if _selector in QUANTITIES:
            _moved.update(
                instance_name(_selector, index)
                for index in range(QUANTITIES[_selector])
            )
        elif _selector in _instances:
            _moved.add(_selector)
        else:
            raise AssertionError(f"unknown explode selector: {_selector}")
_static = {
    instance_name(family, index)
    for family in EXPLODE_STATIC
    for index in range(QUANTITIES[family])
}
if _moved & _static or _moved | _static != _instances:
    raise AssertionError("every occurrence is exploded or deliberately static, not both")
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
CL_TIP_PRECISION = 3
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
# its own pin spacing to ±POSITION_BAND, the same band the readings use. The
# readings and the band print at the carrier's 4 places (a .0001 DRO).
ALIGNMENT_BAND = carrier.POSITION_BAND
ALIGNMENT_PLACES = 4
ASSEMBLED_CAPTION = (
    "INNER PASS AT THE SYMMETRIC POSITION: A1/B1; OUTER PASS: A2/B2. "
    "BOTH SHOULDER SCREWS MUST BE SEATED AND TORQUED BEFORE CUTTING. "
    "CHECK ACTUAL SPINDLE/TOOL/HOLDER CLEARANCE BEFORE USE (OPERATION SHEET). "
    "MACHINE ORIGIN: SPINDLE AT TABLE TOP; +Y TOWARD COLUMN."
)


def _alignment_rows() -> tuple[str, ...]:
    rows = []
    for station, pins in trammel.ALIGNMENT_TARGETS.items():
        (x1, y1), (x2, y2) = pins["rail 1"], pins["rail 2"]
        x1, y1, x2, y2 = (_length(v, ALIGNMENT_PLACES) for v in (x1, y1, x2, y2))
        rows.append(
            f"S {_length(station, 2):>5}: RAIL 1 X {x1:>8} Y {y1:>7}; "
            f"RAIL 2 X {x2:>8} Y {y2:>7}"
        )
    return tuple(rows)


def _sweep_line() -> str:
    # Review bought-tl000-r1: the checks' "sweep of each pass" gets its range,
    # each pin's station over ±trammel.SWEEP, rounded outward.
    spans = ", ".join(
        f"{name.upper()} {_bound(lo, 1, up=False)} TO {_bound(hi, 1, up=True)}"
        for name, (lo, hi) in trammel.PIN_TRAVEL.items()
    )
    return (
        f"SWEEP OF EACH PASS, EACH PIN AT S: {spans}; NO STOP LIMITS IT, THE "
        "FITTER ENDS EACH PASS THERE."
    )


ALIGNMENT_NOTE_LINES = (
    "RAIL ALIGNMENT TARGETS: PIVOT PIN AXIS, MACHINE X/Y FROM THE SPINDLE, "
    "AT STATION S FROM THE SPINDLE ALONG THE RAIL "
    f"(±{_length(ALIGNMENT_BAND, ALIGNMENT_PLACES)})",
    *_alignment_rows(),
)
SWEEP_NOTE_LINE = _sweep_line()

# Every screw by its fastener-table callout (fasteners.FASTENERS) and every
# bought item by its BOM item number.
_RAIL_SCREW = fasteners.callout(fasteners.RAIL_TO_BAR)
_BAR_SCREW = fasteners.callout(fasteners.BRACKET_TO_BAR)
_CARRIAGE_SCREW = fasteners.callout(fasteners.BLOCK_TO_CARRIAGE)
_KP08_SCREW = fasteners.callout(fasteners.KP08_TO_BRACKET)
_NUT_SCREW = fasteners.callout(fasteners.NUT_TO_FEED_BLOCK)
_RISER_SCREW = fasteners.callout(fasteners.RISER_TO_CARRIER)
_CLAMP_SCREW = fasteners.callout(fasteners.CR_CLAMP)
_LEVER_SCREW = fasteners.callout(fasteners.LEVER_TO_CARRIER)

# --- Leadscrew thrust and retained static-clamp torque basis --------------------
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
# Owner ruling 2026-10-27: TL-28 may lift its heel elastically under this
# thrust (it opens at leadscrew.BRACKET_OPENING_THRUST, 704 N); slip governs.
if leadscrew.BRACKET_SLIP_THRUST < leadscrew.SLIP_MARGIN_MIN * FEED_THRUST_N:
    raise AssertionError(
        f"TL-28 slips at {leadscrew.BRACKET_SLIP_THRUST:.0f} N, under "
        f"{leadscrew.SLIP_MARGIN_MIN} x the {FEED_THRUST_N:.0f} N feed thrust"
    )
_AL_SHEAR_ULTIMATE_MPA = 207.0
_STRIP_SAFETY = 3.0
_NUT_FACTOR = 0.20
# A 4 N·m seating torque gives nominal 2.5 kN preload at K=.20 on the 5/16-18.
# The 6061 internal-thread shear estimate on the worst-case full-form
# engagement of the cut thread (.482, about 47 kN, 19x the preload) is
# deliberately limited to one third of ultimate; this is a seating choice,
# not a whole-jig load certification.
PIVOT_SCREW_PRELOAD_N = PIVOT_SCREW_TORQUE_NM / (_NUT_FACTOR * pivot_screw.THREAD_DIA / 1000.0)
PIVOT_THREAD_STRIP_N = (
    0.75 * math.pi * pivot_screw.THREAD_DIA * pivot_block.PIVOT_THREAD_ENGAGEMENT_MIN
    * _AL_SHEAR_ULTIMATE_MPA
)
if PIVOT_SCREW_PRELOAD_N > PIVOT_THREAD_STRIP_N / _STRIP_SAFETY:
    raise ValueError("pivot seating torque exceeds the receiver-thread basis")

# --- The nut screws: their torque; the feed nut a static clamp -----------------
# LOAD_CASES: the two #4-40 X 3/4 SHCS clamp the shop-made TL-27 brass nut to
# the feed-block lug (owner ruling 2026-11-01, item 4). The nut's reaction to
# the screw's turning reverses with the handwheel; its clamp friction on the
# lug carries it with margin, so the nut never shifts in its loose holes and
# no operating torque reaches the screws: a static clamp (rule 23's last
# bullet), as the owner ruled for the bought nut's flange before it (TL-00
# review jbf-r17; issue #1630): no lock. The socket heads bear on the brass.
# Engagement: worst-case full thread in the lug's THRU tap.
_NUT_SCREW_STRIP_N = (
    0.75
    * math.pi
    * fasteners.NUT_TO_FEED_BLOCK.major_mm
    * feed_nut.SCREW_FULL_THREAD_MIN
    * _AL_SHEAR_ULTIMATE_MPA
)
# Each head bears on the nut round its loose hole: the head's least diameter,
# concentric, on the largest drilled hole. Brass 360-H02 (half hard), yield
# 17 ksi = 117.2 MPa (SOURCED: OnlineMetals #1500 listing, 2026-11-01).
_BRASS_YIELD_MPA = 17_000.0 * 0.006894757
_NUT_SCREW_BEARING_MM2 = (
    math.pi
    / 4.0
    * (nut_screw.HEAD_DIA_MIN**2 - (feed_nut.HOLE_DIA + feed_nut.DRILLED_OVERSIZE) ** 2)
)
_NUT_SCREW_PRELOAD_CAP_N = min(
    _NUT_SCREW_STRIP_N / _STRIP_SAFETY,
    _BRASS_YIELD_MPA * _NUT_SCREW_BEARING_MM2,
)
# 0.3 N·m keeps the heads' bearing under the brass's yield (ruling of
# 2026-11-01 on the shop-made nut).
NUT_SCREW_TORQUE_NM = 0.3
NUT_SCREW_PRELOAD_N = NUT_SCREW_TORQUE_NM / (
    _NUT_FACTOR * fasteners.NUT_TO_FEED_BLOCK.major_mm / 1000.0
)  # 527
NUT_SCREW_BEARING_MPA = NUT_SCREW_PRELOAD_N / _NUT_SCREW_BEARING_MM2
if NUT_SCREW_PRELOAD_N > _NUT_SCREW_PRELOAD_CAP_N:
    raise ValueError(
        f"nut screws at {NUT_SCREW_TORQUE_NM} N·m preload {NUT_SCREW_PRELOAD_N:.0f} N, "
        f"over the {_NUT_SCREW_PRELOAD_CAP_N:.0f} N the tap and the brass carry"
    )
# The screw: the preload's stress on the #4-40 tensile stress area
# (0.00604 in², ASME B1.1) stays under half the alloy steel socket screw's
# 170,000 psi (SOURCED: McMaster-Carr 91251A listing, ASTM A574).
_NUT_SCREW_STRESS_AREA_MM2 = 0.00604 * trammel.INCH**2
_SHCS_TENSILE_MPA = 170_000.0 * 0.006894757
if not NUT_SCREW_PRELOAD_N / _NUT_SCREW_STRESS_AREA_MM2 < 0.5 * _SHCS_TENSILE_MPA:
    raise ValueError(f"nut screw preload {NUT_SCREW_PRELOAD_N:.0f} N overloads it")
# The nut's torque at the 1 kN hand-abuse thrust (leadscrew LOAD_CASES):
# T = F d2/2 tan(lead + friction), the oiled thread above.
NUT_ABUSE_TORQUE_NM = (
    leadscrew.HAND_ABUSE_THRUST
    * _TR_PITCH_DIA
    / 2000.0
    * math.tan(_LEAD_ANGLE + _FRICTION_ANGLE)
)
# The nut's slip torque: the screws' clamp at their .34 from the axis, brass
# on as-machined 6061, μ 0.15 .. 0.20.
_NUT_SLIP_FRICTION = (0.15, 0.20)
NUT_SLIP_NM = tuple(
    fasteners.NUT_TO_FEED_BLOCK.count
    * NUT_SCREW_PRELOAD_N
    * friction
    * feed_nut.HOLE_OFFSET
    / 1000.0
    for friction in _NUT_SLIP_FRICTION
)
NUT_SLIP_MARGIN = NUT_SLIP_NM[0] / NUT_ABUSE_TORQUE_NM
if NUT_SLIP_MARGIN < leadscrew.SLIP_MARGIN_MIN:
    raise ValueError(
        f"the feed nut slips at {NUT_SLIP_NM[0]:.2f} N·m, under "
        f"{leadscrew.SLIP_MARGIN_MIN} x the nut's {NUT_ABUSE_TORQUE_NM:.2f} N·m"
    )
_NUT_TORQUE = _torque(NUT_SCREW_TORQUE_NM)


# --- The feed lever screws: their tightening torque -----------------------------------
# The two 5/16-18 screws retain the lever against operator handling loads.
# Wedge-lock pairs remain under the heads. The TL-21 6061-T6511 tap's strip
# load at the worst-case engagement caps the preload at one third of ultimate.
# The feed itself now always uses the handwheel through the integral nut lug.
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
_LEVER_TORQUE = _torque(LEVER_SCREW_TORQUE_NM)


def _item(stem: str) -> str:
    """``stem``'s BOM item citation, ``(ITEM n)``."""
    return f"(ITEM {ITEM_NUMBERS[stem]})"


# TL-21 supplies the CL spot; the HUB is drilled in situ from the apex
# (owner ruling 5, option A, 2026-11-01: carrier HUB_RADIAL_STACK). Fit doc
# F16 (HUB, the purchased .4000 reamer) and F19 (CL, the owned .2490 reamer)
# size the finished holes.
_HUB_HOLE = (
    f"HUB Ø{_length(carrier.HUB_HOLE_LIMITS[0], 4)}-"
    f"{_length(carrier.HUB_HOLE_LIMITS[1], 4)} THRU, BONDED LOCATOR "
    f"{_item(HUB_PIN)}; LOCTITE 638"
)
_CL_HOLE = (
    f"CL Ø{_length(carrier.CL_DOWEL_DIA + min(carrier.CL_HOLE_BAND), 4)}-"
    f"{_length(carrier.CL_DOWEL_DIA + max(carrier.CL_HOLE_BAND), 4)} THRU, FOR THE "
    f"1/4 X 1 DOWEL ({_length(cl_dowel.DIA_MIN, 4)}-{_length(cl_dowel.DIA_MAX, 4)})"
)
# The shared stud REWORK sheet points to this installed-stack acceptance.
OPERATION_SHEET_NUMBER = 9
HOLD_DOWN_REFERENCE = f"{DRAWING_NUMBER}, STEPS HD1-HD4 (SHEET {OPERATION_SHEET_NUMBER})"
ASSEMBLY_STEPS = (
    f"1. SCREW AN HGR15R RAIL {_item(RAIL)} ON EACH BASE BAR WITH "
    f"{trammel.RAIL_HOLE_COUNT} {_RAIL_SCREW} {_item(RAIL_SCREW)}, ENDS FLUSH: "
    "ONE BAR AS DRAWN FOR RAIL 1, THE OTHER TURNED OVER FOR RAIL 2, "
    "ITS COUNTERBORES UP. SCREW AN END BRACKET "
    f"{_item(END_BRACKET)} ON RAIL 1'S BAR AT EACH KP08 STATION, "
    f"{len(leadscrew.BAR_SCREW_LATERALS)} {_BAR_SCREW} "
    f"{_item(BRACKET_SCREW)} PER BRACKET FROM BELOW, "
    f"{_torque(leadscrew.BAR_SCREW_TORQUE_NM)}.",
    "2. SET BOTH BARS ON THE TABLE, NEAR ENDS TOWARD THE SPINDLE. USE TWO "
    f"UNCUT {fasteners.HOLD_DOWN_STUD_THREAD} STUDS {_item(HOLD_DOWN_STUD)} "
    "PER BAR IN THE OUTER T-SLOTS, IN T-NUTS "
    f"{_item(T_NUT)} UNDER FINGER-TIGHT FLANGE NUTS {_item(FLANGE_NUT)}. "
    "FOLLOW HD1 FOR UNCUT-STOCK OBSTRUCTIONS; REWORK AT STEP 13B.",
    f"3. SLIDE A FACTORY-GREASED HGH15CA CARRIAGE {_item(CARRIAGE)} ON EACH RAIL.",
    f"4. FIT THE FEED BLOCK {_item(FEED_BLOCK)} ON RAIL 1'S CARRIAGE, "
    f"THE PLAIN PIVOT BLOCK {_item(PIVOT_BLOCK)} ON RAIL 2'S, "
    "PIVOT COUNTERBORES TOWARD THE SPINDLE AND FEED LUG TOWARD THE COLUMN.",
    # Owner ruling 2026-11-01 (option A): each carriage screw is cut to its own
    # counterbore (rule 19); the jig's RV-05 accepts the reach it leaves.
    "5. MEASURE EACH BLOCK'S 4 COUNTERBORE FLOOR HEIGHTS ABOVE ITS BOTTOM TO "
    f".001. CUT EACH {_CARRIAGE_SCREW} {_item(CARRIAGE_SCREW)} TO ITS OWN FLOOR "
    f"HEIGHT + {_length(pivot_block.SCREW_REACH, 3)} "
    f"(+/-{_length(pivot_block.SCREW_CUT_BAND, 3)}) UNDER THE HEAD; DEBURR THE "
    "CUT END. FASTEN EACH BLOCK WITH ITS 4: EACH TIP ENGAGES "
    f"{_length(pivot_block.ENGAGEMENT_MIN, 3)}-{_length(pivot_block.ENGAGEMENT_MAX, 3)} "
    "OF THE CARRIAGE'S M4 X 5 AND NEVER BOTTOMS. "
    f"TEMPORARILY SEAT THE SHOULDER SCREWS {_item(PIVOT_SCREW)} FOR INDICATING.",
    "6. ZERO THE DRO X AND Y ON THE SPINDLE ORIGIN (SHEET 1). AT EACH "
    "ALIGNMENT-TABLE STATION, RUN THE TABLE UNTIL THE DRO READS ITS X AND Y, "
    "SLIDE THE CARRIAGE UNTIL ITS SCREW SHOULDER CENTRES IN X UNDER A "
    "SPINDLE-MOUNTED INDICATOR AND TAP THE BAR UNTIL IT CENTRES IN Y; "
    "TIGHTEN THE HOLD-DOWN NUTS AND READ EACH STATION AGAIN.",
    f"7. FIT THE FEED NUT {_item(FEED_NUT)} ON THE FEED BLOCK LUG'S "
    f"PRINT-DRILLED TAPS WITH 2 {_NUT_SCREW} {_item(NUT_SCREW)}, FINGER TIGHT; "
    "NO TRANSFER SPOTTING. FIT EACH KP08 "
    f"{_item(PILLOW_BLOCK)} WITH 2 {_KP08_SCREW} {_item(PILLOW_BLOCK_SCREW)}, LOOSE.",
    # The Tr8 screw's stub and the hub's gap close its metric cut along the
    # KP08 stations: they print exact millimetres (owner ruling 4, 2026-11-01).
    f"8. OIL THE LEADSCREW {_item(LEADSCREW)} WITH ISO VG 32 AND THREAD IT "
    f"THROUGH THE KP08S AND NUT, {leadscrew.NEAR_STUB:.1f} MM PAST THE NEAR BLOCK. "
    "COMPLETE F1 (SHEET 8). PUSH THE HANDWHEEL "
    f"{_item(HANDWHEEL)} ON, HUB {leadscrew.HUB_GAP:.1f} MM OFF THE FAR BLOCK; "
    "TIGHTEN ITS AND THE KP08 SET SCREWS ON THE FLATS WITH LOCTITE 222 "
    "THREADLOCKER. THEN COMPLETE F2.",
    "9. REMOVE THE TEMPORARY SHOULDER SCREWS. FIT THE SPACERS AND CARRIER "
    "ON A1/B1; SELECT SHIMS PER P1 AND COMPLETE P1-P3 (SHEET 8). RECORD HD1 "
    "H THROUGH THE COMPLETE INNER-PASS HAND SWEEP USING THE HANDWHEEL.",
    # The carrier stays on its A1/B1 seats from step 9 to 13A: HUB and CL are
    # finished in place on the running jig (carrier spec) and nothing removes
    # it before 13A. The HUB is set from the spindle origin (the apex) by
    # the printed offset, so the pin spacing moves it with the cut.
    f"10. WITH THE CARRIER {_item(CARRIER)} STILL ON A1/B1 THROUGH STEP 11, "
    "FEED IT TO THE SYMMETRIC POSITION AND RUN THE TABLE UNTIL THE DRO READS "
    f"X 0, Y {_length(carrier.HUB_OFFSET_PRINTED, carrier.HUB_OFFSET_PLACES)} "
    f"±{_length(carrier.HUB_OFFSET_BAND, carrier.HUB_OFFSET_PLACES)}. "
    "MATCH-DRILL AND REAM THE HUB THERE, THEN THE CL HOLE OFF ITS SPOT, IN "
    f"ONE SETUP SQUARE TO THE CARRIER TOP: {_HUB_HOLE}; {_CL_HOLE}.",
    "11. CLAMP THE RISER ON THE CARRIER AND SPOT ITS "
    f"{len(riser.SCREW_HOLES) + 3} HOLES FROM BELOW THROUGH THE FINISHED CARRIER "
    "HOLES; FINISH TO MHA-CH-06-TL-24 AND FIT WITH "
    f"{len(riser.SCREW_HOLES)} {_RISER_SCREW}S {_item(RISER_SCREW)}. "
    f"ABRASIVE-CUT THE GAUGE PIN {_item(HUB_PIN)} TO "
    f"{_length(hub_pin.CUT_LENGTH, hub_pin.CUT_PLACES)}; "
    "DEBURR THE CUT END ONLY, CUT END DOWN, FACTORY END UP. CLEAN AND BOND "
    f"WITH LOCTITE 638; SET ITS FACTORY TOP WITH A {_length(hub_pin.TIP_SET, 3)} "
    f"GAUGE ABOVE THE RISER ({_length(hub_pin.TIP_SET, 3)} +/-"
    f"{_length(hub_pin.TIP_SET_BAND, 3)}); LET THE BOND CURE BEFORE USE. "
    f"PRESS THE CL DOWEL {_item(CL_DOWEL)} CHAMFERED END FIRST DOWN UNTIL ITS "
    f"ROUND TIP IS {_length(cl_dowel.TIP_SET_MIN, 3)}-"
    f"{_length(cl_dowel.TIP_SET_MAX, 3)} ABOVE THE RISER. "
    f"CHECK THE {carrier.STRAP_NUMBER} STRAP SEATS FLAT, LOCATES AND SLIDES OFF; "
    "THE CL TIP MUST NOT STAND ABOVE IT.",
    f"12. BOLT THE FEED LEVER ON WITH 2 {_LEVER_SCREW} {_item(LEVER_SCREW)} "
    f"ON WEDGE-LOCK PAIRS {_item(LEVER_LOCK_WASHER)}, {_LEVER_TORQUE}, "
    "GRIP TOWARD THE OPERATOR. THE CR CLAMP SCREW "
    f"{_item(CLAMP_SCREW)} GOES THROUGH WORK, STRAP AND RISER INTO THE CARRIER. "
    "FEED WITH THE HANDWHEEL; DO NOT FORCE THE LEVER AGAINST THE ENGAGED NUT.",
    f"13A. FIT A2/B2 PER O1; COMPLETE HD1 (SHEET {OPERATION_SHEET_NUMBER}).",
    "13B. REMOVE THE CARRIER PER O1; REWORK STUDS PER HD2-HD3.",
    "13C. REFIT A2/B2 PER O1; DO HD4 AND THE CHECKS.",
    "13D. RETURN TO A1/B1 PER O1; REPEAT HD4 AND THE CHECKS.",
)
ASSEMBLY_CHECKS = (
    "CHECK: EVERY ALIGNMENT READING WITHIN "
    f"±{_length(ALIGNMENT_BAND, ALIGNMENT_PLACES)} OF ITS TARGET.",
    "CHECK: HANDWHEEL FEEDS EACH COMPLETE PASS WITHOUT BINDING; BOTH "
    "CARRIAGES STAY ON THEIR RAILS AND ALL MOVING PARTS CLEAR STUDS, NUTS "
    "AND COLUMN COVER.",
    "CHECK: BOTH SHOULDER ENDS ARE SEATED, SCREWS TORQUED AND EACH HEAD "
    "HAS THE P1 RUNNING GAP WITHOUT CLAMPING THE CARRIER.",
)
PIVOT_FIT_STEPS = (
    f"P1. AT EACH SUPPORT SET A LOOSE SPACER {_item(PIVOT_SPACER)} ON THE "
    "BLOCK, NO SHIMS. LOWER THE CARRIER ON THE CHOSEN HOLE PAIR, SEAT BOTH "
    "SHOULDER SCREWS AND MEASURE EACH HEAD-TO-CARRIER GAP. LIFT THE CARRIER; "
    f"UNDER EACH SPACER STACK SHIMS {_item(PIVOT_SHIM)}, FITTING "
    "STOCK PER THE BUY LIST UNDER THE BOM ("
    + ", ".join(f"{sku} {_length(t * _THOU, 3)}" for t, sku in sorted(pivot_shim.FIT_SKUS.items()))
    + f"), THAT CLOSE ITS GAP TO {_length(PIVOT_RUNNING_GAP[0], 3)}-"
    f"{_length(PIVOT_RUNNING_GAP[1], 3)} THROUGH FREE SWING: NOMINAL "
    f"{pivot_shim.PER_SUPPORT} X {_length(pivot_shim.THICKNESS, 3)}, "
    f"WORST CASE UP TO {_length(PIVOT_FIT_PACK_MAX, 3)} ({PIVOT_FIT_SHIMS_MAX} SHIMS). "
    "REMEASURE. THE SAME SHIM SET MUST SERVE BOTH HOLE PAIRS; NO SHIM "
    "BETWEEN SPACER AND CARRIER.",
    f"P2. CLEAN THE {pivot_screw.THREAD} THREADS; APPLY LOCTITE 222. LIGHTLY GREASE THE "
    "SHOULDERS AND SPACER FACES WITH NLGI 2 LITHIUM GREASE, KEEPING THREADS "
    "CLEAN OF GREASE. "
    f"SEAT THE SHOULDERS IN THEIR COUNTERBORES AND TORQUE TO "
    f"{_torque(PIVOT_SCREW_TORQUE_NM)}. THE HEADS MUST NOT CLAMP THE CARRIER.",
    "P3. HANDWHEEL-SWEEP THE FITTED HOLE PAIR'S COMPLETE PASS. CHECK THE GAP AT BOTH "
    "SUPPORTS, FREE ROTATION AND POSITIVE LIFT CAPTURE UNDER BOTH HEADS. "
    "REFIT A FAILED STACK; DO NOT LOOSEN A SEATED SCREW TO MAKE CLEARANCE.",
)
# Sheet 2, under the BOM: what item 7's QTY counts and the fitting stock to buy.
PIVOT_SHIM_STOCK_NOTE = "\n".join((
    f"ITEM {ITEM_NUMBERS[PIVOT_SHIM]}: SHIM FITTING STOCK, SELECTED PER P1.",
    f"BOM QTY. {pivot_shim.QUANTITY} IS THE NOMINAL PACK, {pivot_shim.PER_SUPPORT} X "
    f"{_length(pivot_shim.THICKNESS, 3)} A SUPPORT.",
    "BUY, COVERING THE WORST CASE AT BOTH SUPPORTS:",
    ", ".join(
        f"{sku} ({_length(thickness, 3)}) X{count}"
        for sku, (thickness, count) in PIVOT_SHIM_BUY.items()
    ) + ".",
))
KP08_ALIGNMENT_STEPS = (
    "F1. WITH THE LEADSCREW THREADED THROUGH THE NUT, TIGHTEN BOTH NUT "
    f"SCREWS TO {_NUT_TORQUE}: THE NUT'S LOOSE HOLES LET IT ALIGN TO THE "
    "SCREW. THE KP08S FLOAT "
    "IN THEIR MOUNTING HOLES. MOVE THE FEED CARRIAGE TO EACH TRAVEL "
    "END IN TURN AND ALIGN EACH KP08 TO THE FIXED NUT WITHOUT FORCING "
    "THE SCREW; TIGHTEN THE KP08 MOUNTING SCREWS.",
    "F2. WITH THE HANDWHEEL AND ALL SET SCREWS TIGHT, TURN THE HANDWHEEL "
    "TO BOTH FEED-CARRIAGE TRAVEL ENDS: NO BINDING, NUT OR LUG CONTACT WITH "
    "A KP08, AND NO MOVING PART CONTACT. REPEAT ALIGNMENT IF IT BINDS.",
)

# The studs' measurements, fit limits and installed acceptance, migrated from
# the stud drawing (hold_down_stud.measured_fit_bounds evaluates the same G, Q,
# nut-span, lower-interval and insertion predicates). H is only measurable
# with the blocks on their carriages over both passes.
# The kit's REWORK sheet prints the stud in mm; this inch sheet prints its
# limits and the clearance rounded outward, the conservative side of HD2.
_STUD_CLEARANCE = _bound(hold_down_stud.CLEARANCE_MIN, 3, up=True)
_STUD_PITCH = (
    f"{hold_down_stud.COMPLETE_PROJECTION_PITCHES:g} COMPLETE {hold_down_stud.THREAD} PITCH"
)
# The finished-length limits the kit drawing's stud rework sheet prints (the
# title block's ± at its places); the kit's registry number, pinned by test.
CLAMPING_KIT_NUMBER = "MHA-SH-VN-57"
# HD2-HD3 cut the studs to the kit drawing's REWORK sheet, its second.
STUD_REWORK_SHEET = f"{CLAMPING_KIT_NUMBER} SHEET 2"
_STUD_LIMITS = (
    f"{_bound(hold_down_stud.LENGTH - hold_down_stud.LENGTH_BAND, 3, up=False)}/"
    f"{_bound(hold_down_stud.LENGTH + hold_down_stud.LENGTH_BAND, 3, up=True)}"
)
HOLD_DOWN_STEPS = (
    "HD1. FOR UNCUT-STOCK OBSTRUCTIONS, ISOLATE THE SPINDLE, SUPPORT THE "
    "CARRIER AND SECURE THE OTHER HOLD-DOWNS. MARK/REMOVE ONLY THE "
    "OBSTRUCTING STUD; RESTORE ITS ORIGINAL INSERTION BEFORE REMOVING "
    "ANOTHER. NEVER FORCE MOTION PAST UNCUT STOCK. BEFORE CUTTING THE "
    f"{hold_down_stud.QUANTITY} STUDS {_item(HOLD_DOWN_STUD)}, MEASURE AT EACH "
    "STUD ON THE ACTUAL PARTS, MIN "
    "AND MAX IN INCHES WITH GAUGE UNCERTAINTY INCLUDED: B, BAR THICKNESS; D, "
    "STUD LOWER END TO BAR UNDERSIDE AT THE ORIGINAL INSERTION; H, BAR TOP TO "
    f"MOVING BLOCK UNDERSIDE (ITEMS {ITEM_NUMBERS[FEED_BLOCK]}/{ITEM_NUMBERS[PIVOT_BLOCK]}), LEAST OVER BOTH "
    "COMPLETE PASSES: INNER AT STEP 9, OUTER AT STEP 13A; N, SEATED FLANGE "
    f"NUT {_item(FLANGE_NUT)} BEARING FACE "
    "TO THE FAR END OF ITS COMPLETE THREADS, NOT BODY HEIGHT; W, WASHER "
    "STACK (NONE IS ADDED); U, PROPOSED CUT END TO THE FIRST COMPLETE "
    "THREAD, NOT THE CHAMFER. MARK THE LOWER FACTORY END, THE ORIGINAL "
    "INSERTION AND THE ORIGINAL LOWER LOADED COMPLETE-THREAD INTERVAL.",
    f"HD2. WITH LMIN/LMAX THE STUD'S FINISHED-LENGTH LIMITS ON {STUD_REWORK_SHEET} "
    f"({_STUD_LIMITS}), NOT STOCK "
    "LENGTH, REQUIRE GMIN = BMIN + HMIN + DMIN - LMAX >= "
    f"{_STUD_CLEARANCE} AND QMIN = LMIN - DMAX - BMAX - WMAX - NMAX - UMAX "
    f">= {_STUD_PITCH}. THE NUT'S WHOLE COMPLETE-THREAD SPAN MUST STAY ON "
    "COMPLETE STUD THREAD AND THE ORIGINAL LOWER LOADED INTERVAL MUST STAY "
    "INTACT BELOW THE BAR. AN UNKNOWN MEASUREMENT OR A FAILED LIMIT REJECTS "
    "THE SETUP: NO DEEPER INSERTION, NO CUT THROUGH ENGAGED THREADS.",
    "HD3. AT STEP 13B, KEEP THE CARRIER OFF AND THE OTHER HOLD-DOWNS SECURE. "
    "REMOVE, SHORTEN AND REFIT ONE STUD AT A TIME. SHORTEN ONLY THE UNUSED "
    f"UPPER END TO THE FINISHED LENGTH ON {STUD_REWORK_SHEET}; DEBURR, GAUGE THE COMPLETE THREADS AND "
    "REMEASURE U. RESTORE THE ORIGINAL INSERTION AND SEAT ITS NUT FULLY "
    "WITH NO WASHER BEFORE REMOVING ANOTHER STUD; DO NOT FORCE OR BOTTOM "
    "DEEPER. AFTER THE LAST STUD REFIT, WITH THE CARRIER STILL OFF, REDO "
    f"STEP 6: TEMPORARILY SEAT BOTH SHOULDER SCREWS {_item(PIVOT_SCREW)}, "
    "SLACKEN THE HOLD-DOWN NUTS, BRING THE FEED CARRIAGE TO EACH STATION "
    "WITH THE HANDWHEEL AND THE PIVOT CARRIAGE BY HAND, INDICATE, TAP, "
    "RETIGHTEN AND READ EVERY STATION. REMOVE THE TEMPORARY SCREWS.",
    "HD4. WITH THE CARRIER AND BOTH SCREWS FITTED PER O1, HAND-SWEEP ITS "
    "COMPLETE PASS: "
    f"EVERY STUD CLEARS EVERY MOVING BLOCK BY {_STUD_CLEARANCE} MIN "
    f"THROUGHOUT AND SHOWS {_STUD_PITCH} MIN BEYOND ITS SEATED NUT, THE NUT'S "
    "WHOLE COMPLETE-THREAD SPAN ENGAGED. REJECT ANY INCOMPATIBLE SETUP.",
)

OPERATION_STEPS = (
    "O1. PASS CHANGE: STOP/ISOLATE THE SPINDLE, WITHDRAW CUTTER/HOLDER "
    "AND SUPPORT THE CARRIER. REMOVE BOTH SHOULDER SCREWS AND LIFT THE "
    "CARRIER. MOVE THE FEED CARRIAGE WITH THE HANDWHEEL AND THE PIVOT "
    "CARRIAGE BY HAND UNTIL THE OTHER HOLE PAIR (A2/B2 OR A1/B1) LINES UP "
    "OVER BOTH BLOCK COUNTERBORES; LOWER THE CARRIER ONTO IT. KEEP EACH SUPPORT'S "
    "SHIMS AND SPACER IN PLACE, REFIT BOTH SCREWS PER P2 AND CHECK P1-P3 "
    "BEFORE CUTTING.",
    "O2. SERVICE: SUPPORT THE CARRIER BEFORE REMOVING ITS TWO SCREWS. "
    "KEEP THE SELECTED SHIMS WITH THEIR SUPPORTS. AFTER REASSEMBLY REPEAT "
    "THE PIVOT GAP, FEED ALIGNMENT, HD4 AND ACTUAL TOOLING-CLEARANCE CHECKS.",
)
CAPTURE_CHECKS = (
    "TOOLING CLEARANCE: BEFORE USE, WITH THE SPINDLE ISOLATED, CHECK THE "
    "ACTUAL SPINDLE, CUTTER, NON-CUTTING TOOL AND HOLDER AGAINST THE "
    "FIXTURE THROUGH BOTH PASSES AND THE ENTIRE USED Z RANGE, INCLUDING "
    "BREAKTHROUGH AND RETRACTION. INCLUDE BOTH SHOULDER-SCREW HEADS. "
    "VERIFY VISIBLE OR MEASURED CLEARANCE AT EVERY CLOSEST APPROACH: "
    "NO SPINDLE/TOOL/HOLDER CONTACT WITH THE FIXTURE.",
    "KEEP THE REPEATED STEP 6 ACTUAL SPINDLE-AXIS REGISTER; REINDICATE AFTER "
    "XY CHANGES. RECHECK CLEARANCE AFTER TOOL/DEPTH/SETUP CHANGES.",
    f"REFERENCE TABLE HEIGHTS: WORK {_length(PART_TOP_Z, 3)}; SHOULDER-SCREW HEADS "
    f"{_length(PIVOT_HEAD_TOP_Z, 3)}, NOMINAL. "
    "SET CUTTING DEPTH FROM THE ACTUAL SEATED WORK, NOT THESE REFERENCES.",
    "ACCEPTANCE: THE CARRIAGE/RAIL AND TABLE ANCHORS PASS THE ASSEMBLY CHECKS "
    "AFTER FINAL TIGHTENING (EVERY STEP 6 READING WITHIN "
    f"±{_length(ALIGNMENT_BAND, ALIGNMENT_PLACES)}; "
    "FREE SWEEP WITH BOTH CARRIAGES ON THEIR RAILS) AND HD4 AT EVERY STUD.",
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
    """Conservative source boxes in each part's authored local frame.

    Purchased dimensions without published limits remain nominal references.
    These envelopes do not replace the native whole-model interference gates.
    """
    nut_box = ((0.0, feed_nut.WIDTH), (0.0, feed_nut.HEIGHT), (0.0, feed_nut.LENGTH_MAX))
    boxes = {
        BASE_BAR: ((0.0, base_bar.BAR_LENGTH), (base_bar.LOW_SIDE_Y, base_bar.HIGH_SIDE_Y), (0.0, base_bar.BAR_THICK)),
        RAIL: ((0.0, guide_rail.LENGTH), (-guide_rail.WIDTH / 2.0, guide_rail.WIDTH / 2.0), (0.0, guide_rail.HEIGHT)),
        CARRIAGE: ((-carriage.LENGTH / 2.0 - carriage.NIPPLE_PROUD, carriage.LENGTH / 2.0 + carriage.PLUG_PROUD), (-carriage.WIDTH / 2.0, carriage.WIDTH / 2.0), (carriage.UNDERSIDE_Z, carriage.MOUNTING_FACE_Z)),
        PIVOT_BLOCK: ((pivot_block.BLOCK_X0, pivot_block.BLOCK_X1), (-pivot_block.BLOCK_WIDTH / 2.0, pivot_block.BLOCK_WIDTH / 2.0), (0.0, pivot_block.BLOCK_HEIGHT)),
        FEED_BLOCK: ((pivot_block.BLOCK_X0, pivot_block.BLOCK_X1), (feed_block.LUG_Y0, pivot_block.BLOCK_WIDTH / 2.0), (0.0, pivot_block.BLOCK_HEIGHT)),
        PIVOT_SCREW: ((-pivot_screw.HEAD_DIA / 2.0, pivot_screw.HEAD_DIA / 2.0), (-pivot_screw.HEAD_DIA / 2.0, pivot_screw.HEAD_DIA / 2.0), (-pivot_screw.THREAD_LENGTH, pivot_screw.SHOULDER_LENGTH + pivot_screw.HEAD_HEIGHT)),
        PIVOT_SPACER: ((-pivot_spacer.OD / 2.0, pivot_spacer.OD / 2.0), (-pivot_spacer.OD / 2.0, pivot_spacer.OD / 2.0), (0.0, pivot_spacer.LENGTH)),
        PIVOT_SHIM: ((-pivot_shim.OD / 2.0, pivot_shim.OD / 2.0), (-pivot_shim.OD / 2.0, pivot_shim.OD / 2.0), (0.0, pivot_shim.THICKNESS)),
        CARRIER: (carrier.OUTLINE_X, (-carrier.THICKNESS, 0.0), (-carrier.OUTLINE_Y[1], -carrier.OUTLINE_Y[0])),
        RISER: ((0.0, riser.BLANK_LENGTH), (0.0, riser.BLANK_WIDTH), (0.0, riser.THICKNESS)),
        HUB_PIN: ((-hub_pin.DIA / 2.0, hub_pin.DIA / 2.0), (-hub_pin.DIA / 2.0, hub_pin.DIA / 2.0), (0.0, hub_pin.CUT_LENGTH)),
        FEED_LEVER: ((0.0, feed_lever.LEVER_LENGTH), (0.0, feed_lever.LEVER_THICK), (-feed_lever.LEVER_WIDTH, 0.0)),
        CL_DOWEL: _axis_y_box(cl_dowel.DIA_MAX / 2.0, 0.0, cl_dowel.LENGTH),
        END_BRACKET: ((0.0, leadscrew.BRACKET_LENGTH), (-leadscrew.BRACKET_WIDTH / 2.0, leadscrew.BRACKET_WIDTH / 2.0), (0.0, leadscrew.BRACKET_THICK)),
        LEADSCREW: _axis_y_box(leadscrew_stock.MAJOR_DIA / 2.0, 0.0, leadscrew_stock.LENGTH),
        FEED_NUT: nut_box,
        PILLOW_BLOCK: ((-pillow_block.LENGTH / 2.0, pillow_block.LENGTH / 2.0), (-pillow_block.WIDTH / 2.0, pillow_block.WIDTH / 2.0), (0.0, pillow_block.HEIGHT)),
        HANDWHEEL: _axis_y_box(handwheel.SWEEP_R, 0.0, handwheel.LENGTH),
        HOLD_DOWN_STUD: _axis_y_box(hold_down_stud.RADIUS, 0.0, hold_down_stud.LENGTH),
        T_NUT: ((-t_nut.LENGTH / 2.0, t_nut.LENGTH / 2.0), (0.0, t_nut.HEIGHT), (-t_nut.FOOT_WIDTH / 2.0, t_nut.FOOT_WIDTH / 2.0)),
        FLANGE_NUT: _axis_y_box(max(flange_nut.FLANGE_DIA / 2.0, flange_nut.ACROSS_FLATS / math.sqrt(3.0)), 0.0, flange_nut.HEIGHT),
        LEVER_LOCK_WASHER: _axis_y_box(lever_washer.OD / 2.0, lever_washer.BOTTOM_Y, lever_washer.TOP_Y),
        RISER_SCREW: _axis_y_box(riser_screw.DIMS.head_dia / 2.0, -riser_screw.DIMS.length, 0.0),
    }
    for stem, screw in (
        (RAIL_SCREW, rail_screw), (BRACKET_SCREW, bracket_screw),
        (CARRIAGE_SCREW, carriage_screw),
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
        PIVOT_BLOCK: "pivot block 2", FEED_BLOCK: "feed block",
        PIVOT_SCREW: "pivot screw", PIVOT_SPACER: "pivot spacer",
        PIVOT_SHIM: "pivot shim",
        CARRIER: "carrier", RISER: "riser", FEED_LEVER: "feed lever",
        HUB_PIN: "HUB locator", CL_DOWEL: "CL dowel",
        FEED_NUT: "feed nut",
        LEADSCREW: "screw", HANDWHEEL: "handwheel",
        END_BRACKET: "end bracket", PILLOW_BLOCK: "pillow block",
        HOLD_DOWN_STUD: "hold-down stud", T_NUT: "T-nut", FLANGE_NUT: "flange nut",
        RAIL_SCREW: "rail screw", BRACKET_SCREW: "bracket screw",
        CARRIAGE_SCREW: "carriage screw",
        PILLOW_BLOCK_SCREW: "pillow block screw", NUT_SCREW: "nut screw",
        RISER_SCREW: "riser screw", CLAMP_SCREW: "clamp screw",
        LEVER_SCREW: "lever screw",
        LEVER_LOCK_WASHER: "lever lock washer",
    }
    name = names[stem]
    return f"{name} {index + 1}" if QUANTITIES[stem] > 1 else name


def _motion_root(stem: str, index: int) -> tuple[str, int]:
    while stem in LOCKED_TO:
        stem, index = LOCKED_TO[stem][index]
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
    """One conservative source envelope per actual native occurrence."""
    boxes = _component_local_boxes() if boxes is None else boxes
    records: dict[str, tuple[str, int, list[Point3]]] = {}
    for stem in BOM_ORDER:
        if pass_name is not None and stem not in MOVING:
            continue
        corners = _box_corners(boxes[stem])
        for index, placement in enumerate(PLACEMENTS[stem]):
            if pass_name is not None:
                placement = _swept_placement(stem, index, pass_name, theta)
            label = _component_label(stem, index)
            points = [frame_point(placement, corner) for corner in corners]
            if label in records:
                records[label][2].extend(points)
            else:
                records[label] = (stem, index, points)
    return records


def feed_nut_travel_gaps() -> dict[str, float]:
    """Least gap (mm) from the TL-27 feed nut and its screws, swept along
    rail 1 over carriage 1's whole travel, to each occurrence they could meet.

    Stationary items (all but the leadscrew they thread) are boxed in rail 1's
    frame: exact for the rail-1 feed items, conservative for the rest. The
    carrier branch rotates above them about machine Z, so its gap is the
    machine-Z one. The nut overhangs the lug end by ``feed_block.NUT_OVERHANG``.
    """
    records = _component_records()
    origin = trammel.rail_point(leadscrew.RAIL, 0.0)
    dx, dy = rail_direction(leadscrew.RAIL)

    def rail_box(points: list[Point3]) -> Box3:
        local = [
            ((x - origin[0]) * dx + (y - origin[1]) * dy, (y - origin[1]) * dx - (x - origin[0]) * dy, z)
            for x, y, z in points
        ]
        return tuple((min(p[a] for p in local), max(p[a] for p in local)) for a in range(3))

    riders = [rail_box(points) for stem, _index, points in records.values() if stem in (FEED_NUT, NUT_SCREW)]
    swept = (
        (min(b[0][0] for b in riders) + trammel.CARRIAGE_TRAVEL[0] - CARRIAGE_STATION,
         max(b[0][1] for b in riders) + trammel.CARRIAGE_TRAVEL[1] - CARRIAGE_STATION),
        (min(b[1][0] for b in riders), max(b[1][1] for b in riders)),
        (min(b[2][0] for b in riders), max(b[2][1] for b in riders)),
    )
    gaps = {}
    for label, (stem, index, points) in records.items():
        if stem in MOVING:
            if _motion_root(stem, index)[0] == CARRIER:
                gaps[label] = min(p[2] for p in points) - swept[2][1]
        elif stem != LEADSCREW:
            box = rail_box(points)
            gaps[label] = max(
                max(box[a][0] - swept[a][1], swept[a][0] - box[a][1]) for a in range(3)
            )
    return gaps


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
    # The feed block uses its actual concave L outline, not its bounding box.
    out.update({
        name: [pose.to_machine(p) for p in outline]
        for name, outline in CARRIER_OUTLINES.items()
    })
    stations = carriage_stations(pass_name, theta)
    out["feed block"] = [
        trammel.rail_point(1, stations[1] + x, -y)
        for x, y in (
            (pivot_block.BLOCK_X0, feed_block.LUG_Y1),
            (feed_block.LUG_X0, feed_block.LUG_Y1),
            (feed_block.LUG_X0, feed_block.LUG_Y0),
            (feed_block.LUG_X1, feed_block.LUG_Y0),
            (feed_block.LUG_X1, feed_block.LUG_Y1),
            (pivot_block.BLOCK_X1, feed_block.LUG_Y1),
            (pivot_block.BLOCK_X1, pivot_block.BLOCK_WIDTH / 2.0),
            (pivot_block.BLOCK_X0, pivot_block.BLOCK_WIDTH / 2.0),
        )
    ]
    out["pivot block 2"] = _rail_rect(
        2, stations[2] + pivot_block.BLOCK_X0,
        stations[2] + pivot_block.BLOCK_X1, pivot_block.BLOCK_WIDTH / 2.0,
    )
    return out


def hub_locator(pass_name: str, theta: float) -> tuple[tuple[float, float], float]:
    """Machine XY centre and radius of the straight bonded gauge pin."""
    return trammel.carrier_pose(pass_name, theta).to_machine(trammel.HUB), hub_pin.DIA / 2.0


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
    self-collision acceptance; retain the mandatory native whole-model
    interference gates."""

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
for _rail, _pin in zip(RAILS, PIVOT_SCREW_ORIGINS):
    if math.dist(_pin[:2], trammel.rail_point(_rail, PIN_STATION)) > 1e-9:
        raise AssertionError(f"pivot screw on rail {_rail} is off its station")
for (_origin, _rows), _pin in zip(BLOCK_PLACEMENTS, PIVOT_SCREW_ORIGINS):
    _bore = tuple(_origin[i] + pivot_block.BORE_X * _rows[0][i] for i in range(2))
    if math.dist(_bore, _pin[:2]) > 1e-9:
        raise AssertionError("pivot counterbore is not on its screw axis")
if abs(trammel.PIVOT_BLOCK_TOP_Z + trammel.PIVOT_SHIM_PACK + pivot_spacer.LENGTH - trammel.CARRIER_UNDERSIDE_Z) > 1e-9:
    raise AssertionError("shim and spacer do not support the nominal carrier seat")
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
for _carriage, (_seat, _rows) in zip(CARRIAGE_PLACEMENTS, BLOCK_PLACEMENTS):
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
