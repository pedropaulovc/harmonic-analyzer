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

The leadscrew axis is raised (``leadscrew``). The bought brass flange nut
supplied with the lead screw (the TL-VN-84 kit's FeedNut, its spigot faced
off at fit-up) screws flat to the feed-block lug with four countersunk flat
heads, which also key it against turning. The KP08s centre the screw in the
lug's clearance at both travel ends (F1B); the lug's taps are then
transferred through the seated nut at assembly (F2).

Every fabricated and purchased family has its own BOM row. Each purchased
kit's members (the TL-VN-83 rail kit, the TL-VN-84 leadscrew kit and the
shared clamping kit) are logical rows backed by one configured native model,
and so are the two TL-20 base bars (oblique simplification PR2: ``Bar1``
drilled for the end brackets, ``Bar2`` plain; one Number). The rail screws and
the three strap clamps share one common 3/4 screw row (TL-VN-61, McMaster
91251A197). The upper KP08 and lower TL-28 screws share the 5/8 family and
one row (TL-VN-62).
PLACEMENTS, QUANTITIES and BOM_ORDER are the builder and drawing authority.

R4 strap holding (owner rulings 2026-11-07): each faced, bandsawn strap blank
arrives with no hub hole and loose CL/CR clearance holes in its end waste.
Its raw edge seats toward -Y against two loose stock 1/8 x 3/4 dowels
(98381A473, the existing MHA-SM-VN-53 native, no new identity) standing in
the TL-24 riser's #30 stop holes on the carrier top; CL and CR clamp the
ends. The strap's hub hole is then drilled and reamed in place at the same
DRO position (step 10) that tapped the carrier's HUB #8-32, through into the
riser's relief, and the HUB clamp seats the brass top-hat washer's spigot in
that hole. CL, CR and HUB are common-screw occurrences that ride the carrier
while the rail and bracket-family bar screws stay fixed: each occurrence, not
each family, is fixed or moving (``LOCKED_TO``'s ``None`` entries,
``is_moving``). ``STRAP_CLAMP_SCREW_INSTANCES`` publishes their stable
``instance_name`` selectors so a view can hide them without the common
screw's rail occurrences.

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
envelopes of ``_ch_rocker_arm_tl_oblique_jig_interference``. Discrete native poses do not prove
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

import itertools
import math
from collections.abc import Iterator
from dataclasses import dataclass

from _assembly_contract import assembly_contract
from _hole_spec import NUMBER_DRILL_MM
from _printed_tolerance import printed_band_mm
from _title_block_units import LENGTH_UNITS

import ch_rocker_arm_tl_oblique_base_bar_spec as base_bar
import ch_rocker_arm_tl_vn_oblique_pivot_screw_spec as pivot_screw
import ch_rocker_arm_tl_vn_oblique_pivot_spacer_spec as pivot_spacer
import ch_rocker_arm_tl_vn_oblique_pivot_shim_spec as pivot_shim
import ch_rocker_arm_tl_vn_oblique_bracket_screw_spec as bracket_screw
import ch_rocker_arm_tl_vn_oblique_carriage_screw_spec as carriage_screw
import ch_rocker_arm_tl_vn_oblique_rail_kit_carriage_spec as carriage
import ch_rocker_arm_tl_oblique_carrier_spec as carrier
import sm_vn_knife_mount_dowel_spec as stop_pin
import ch_rocker_arm_tl_oblique_fasteners_spec as fasteners
import ch_rocker_arm_tl_oblique_end_bracket_spec as end_bracket
import ch_rocker_arm_tl_oblique_feed_lever_spec as feed_lever
import sh_vn_clamping_kit_flange_nut_spec as flange_nut
import ch_rocker_arm_tl_vn_oblique_handwheel_spec as handwheel
import sh_vn_clamping_kit_hold_down_stud_spec as hold_down_stud
import ch_rocker_arm_tl_oblique_hub_washer_spec as hub_washer
import ch_rocker_arm_tl_vn_oblique_leadscrew_kit_feed_nut_spec as feed_nut
import ch_rocker_arm_tl_vn_oblique_leadscrew_spec as leadscrew
import ch_rocker_arm_tl_oblique_feed_block_spec as feed_block
import ch_rocker_arm_tl_vn_oblique_leadscrew_kit_leadscrew_spec as leadscrew_stock
import ch_rocker_arm_tl_vn_oblique_lever_screw_spec as lever_screw
import ch_rocker_arm_tl_vn_oblique_lever_washer_spec as lever_washer
import ch_rocker_arm_tl_vn_oblique_pillow_block_spec as pillow_block
import ch_rocker_arm_tl_oblique_pivot_block_spec as pivot_block
import ch_rocker_arm_tl_vn_oblique_rail_screw_spec as rail_screw
import ch_rocker_arm_tl_vn_oblique_rail_kit_rail_spec as guide_rail
import ch_rocker_arm_tl_vn_oblique_riser_screw_spec as riser_screw
import ch_rocker_arm_tl_oblique_riser_spec as riser
import sh_vn_clamping_kit_t_nut_spec as t_nut
import ch_rocker_arm_tl_oblique_trammel_spec as trammel
import ch_rocker_arm_tl_oblique_holding_spec as holding

holding.require_clearance()

ASM_NAME = "ch-rocker-arm-tl-oblique-jig"
DRAWING_NUMBER = "MHA-CH-06-TL-00"
# The sheet's unit (the contract's ``drawing_unit``); every printed length
# below goes through ``_length``.
UNIT = assembly_contract("ch-rocker-arm-tl-oblique-jig").drawing_unit


def _length(value_mm: float, places: int) -> str:
    """``value_mm`` as the sheet prints it: ``.080`` or ``-15.250`` in inch."""
    text = f"{value_mm / LENGTH_UNITS[UNIT]:.{places}f}"
    if UNIT == "in":
        text = text.replace("0.", ".", 1) if text.lstrip("-").startswith("0.") else text
    return text


def _outward(value_mm: float, places: int, *, up: bool) -> float:
    """``value_mm`` (mm) rounded outward (``up`` or down) to the sheet's ``places``."""
    scale = 10**places / LENGTH_UNITS[UNIT]
    return (math.ceil if up else math.floor)(round(value_mm * scale, 9)) / scale


def _bound(value_mm: float, places: int, *, up: bool) -> str:
    """``value_mm`` rounded outward (``up`` or down) to the sheet's ``places``."""
    return _length(_outward(value_mm, places, up=up), places)


# One in·lbf in N·m (exact: 4.4482216152605 N x 0.0254 m).
_NM_PER_IN_LBF = 4.4482216152605 * 0.0254


def _torque(nm: float) -> str:
    """A tightening torque as the sheet prints it, ``2.8 N·m (25 IN·LBF)``:
    the N·m source value first, its in·lbf conversion in parentheses rounded
    to the nearest two significant figures (owner ruling 3, 2026-11-01)."""
    in_lbf = float(f"{nm / _NM_PER_IN_LBF:.2g}")
    return f"{nm:.1f} N·m ({in_lbf:g} IN·LBF)"



BASE_BAR = "ch-rocker-arm-tl-oblique-base-bar"
# The base bar's two members (one native model, one Number): Bar1 under rail
# 1 carries the TL-28 bracket holes, Bar2 under rail 2 is plain.
BASE_BAR_1 = f"{BASE_BAR}--{base_bar.BAR1}"
BASE_BAR_2 = f"{BASE_BAR}--{base_bar.BAR2}"
BASE_BARS = (BASE_BAR_1, BASE_BAR_2)
PIVOT_BLOCK = "ch-rocker-arm-tl-oblique-pivot-block"
FEED_BLOCK = "ch-rocker-arm-tl-oblique-feed-block"
PIVOT_SCREW = "ch-rocker-arm-tl-vn-oblique-pivot-screw"
PIVOT_SPACER = "ch-rocker-arm-tl-vn-oblique-pivot-spacer"
PIVOT_SHIM = "ch-rocker-arm-tl-vn-oblique-pivot-shim"
CARRIER = "ch-rocker-arm-tl-oblique-carrier"
RISER = "ch-rocker-arm-tl-oblique-riser"
HUB_WASHER = "ch-rocker-arm-tl-oblique-hub-washer"
FEED_LEVER = "ch-rocker-arm-tl-oblique-feed-lever"
END_BRACKET = leadscrew.END_BRACKET
# Bought hardware (parent-scoped TL-VN and shared SH-VN-57; VN-72 retired),
# every member modelled and mated. A kit member's family is
# ``<physical>--<configuration>``.
RAIL_KIT = "ch-rocker-arm-tl-vn-oblique-rail-kit"
RAIL = "ch-rocker-arm-tl-vn-oblique-rail-kit--Rail"
CARRIAGE = "ch-rocker-arm-tl-vn-oblique-rail-kit--Carriage"
# The riser's two loose end stops: the existing MHA-SM-VN-53 native
# (98381A473, 1/8 x 3/4) reused unchanged, no new identity (Main, R4).
STOP_PIN = "sm-vn-knife-mount-dowel"
if (stop_pin.DIA, stop_pin.LENGTH) != (riser.STOP_PIN_DIA, riser.STOP_PIN_LENGTH):
    raise AssertionError("the reused native is not the riser's stock stop pin")
LEADSCREW_KIT = "ch-rocker-arm-tl-vn-oblique-leadscrew-kit"
LEADSCREW = "ch-rocker-arm-tl-vn-oblique-leadscrew-kit--LeadScrew"
FEED_NUT = "ch-rocker-arm-tl-vn-oblique-leadscrew-kit--FeedNut"
PILLOW_BLOCK = "ch-rocker-arm-tl-vn-oblique-pillow-block"
HANDWHEEL = "ch-rocker-arm-tl-vn-oblique-handwheel"
CLAMPING_KIT = "sh-vn-clamping-kit-hardware"
HOLD_DOWN_STUD = "sh-vn-clamping-kit-hardware--HoldDownStud"
T_NUT = "sh-vn-clamping-kit-hardware--TNut"
FLANGE_NUT = "sh-vn-clamping-kit-hardware--FlangeNut"
# The jig's common #8-32 x 3/4 SHCS: the rail screws, then the CL, CR and HUB
# strap clamps (fasteners.COMMON_SCREW_ROWS), one row.
RAIL_SCREW = "ch-rocker-arm-tl-vn-oblique-rail-screw"
CARRIAGE_SCREW = "ch-rocker-arm-tl-vn-oblique-carriage-screw"
# TL-VN-62, #8-32 x 5/8: four KP08 screws, then four lower TL-28 screws.
PILLOW_BLOCK_SCREW = "ch-rocker-arm-tl-vn-oblique-bracket-screw"
RISER_SCREW = "ch-rocker-arm-tl-vn-oblique-riser-screw"
LEVER_SCREW = "ch-rocker-arm-tl-vn-oblique-lever-screw"
LEVER_LOCK_WASHER = "ch-rocker-arm-tl-vn-oblique-lever-washer"

# Every logical component family and its count: the builder places, the explode
# moves and the drawing proves this inventory in its established item order.
# The bought counts are each member's own, never the number of purchased kits.
QUANTITIES = {
    BASE_BAR_1: base_bar.CONFIGURATION_QUANTITIES[base_bar.BAR1],
    BASE_BAR_2: base_bar.CONFIGURATION_QUANTITIES[base_bar.BAR2],
    CARRIER: 1,
    PIVOT_BLOCK: 1,
    FEED_BLOCK: 1,
    PIVOT_SCREW: pivot_screw.QUANTITY,
    PIVOT_SPACER: pivot_spacer.QUANTITY,
    PIVOT_SHIM: pivot_shim.QUANTITY,
    RISER: 1,
    HUB_WASHER: 1,
    FEED_LEVER: 1,
    END_BRACKET: leadscrew.END_BRACKET_QUANTITY,
    RAIL: fasteners.RAILS,
    CARRIAGE: fasteners.RAILS,
    STOP_PIN: len(riser.STOP_PIN_CARRIER_POINTS),
    LEADSCREW: leadscrew_stock.QUANTITY,
    FEED_NUT: feed_nut.QUANTITY,
    PILLOW_BLOCK: pillow_block.QUANTITY,
    HANDWHEEL: handwheel.QUANTITY,
    HOLD_DOWN_STUD: hold_down_stud.QUANTITY,
    T_NUT: t_nut.QUANTITY,
    FLANGE_NUT: flange_nut.QUANTITY,
    RAIL_SCREW: rail_screw.QUANTITY,
    CARRIAGE_SCREW: carriage_screw.QUANTITY,
    PILLOW_BLOCK_SCREW: bracket_screw.QUANTITY,
    RISER_SCREW: riser_screw.QUANTITY,
    LEVER_SCREW: lever_screw.QUANTITY,
    LEVER_LOCK_WASHER: lever_washer.QUANTITY,
}
# SolidWorks numbers a top-level BOM in FeatureManager order, so BOM_ORDER is
# the builder's insertion order (the builder asserts it) and the steps' item
# numbers (``_item``, ITEM_NUMBERS) read it (c4-r10, rule 25).
BOM_ORDER = (
    BASE_BAR_1,
    BASE_BAR_2,
    CARRIER,
    PIVOT_BLOCK,
    FEED_BLOCK,
    PIVOT_SCREW,
    PIVOT_SPACER,
    PIVOT_SHIM,
    RISER,
    HUB_WASHER,
    FEED_LEVER,
    END_BRACKET,
    RAIL,
    CARRIAGE,
    STOP_PIN,
    LEADSCREW,
    FEED_NUT,
    PILLOW_BLOCK,
    HANDWHEEL,
    HOLD_DOWN_STUD,
    T_NUT,
    FLANGE_NUT,
    RAIL_SCREW,
    CARRIAGE_SCREW,
    PILLOW_BLOCK_SCREW,
    RISER_SCREW,
    LEVER_SCREW,
    LEVER_LOCK_WASHER,
)

# Logical BOM families are not filenames. The heterogeneous kit members share
# one physical producer but retain their own placement, count and native row.
KIT_IDENTITIES = {
    RAIL: (RAIL_KIT, "Rail"),
    CARRIAGE: (RAIL_KIT, "Carriage"),
    LEADSCREW: (LEADSCREW_KIT, "LeadScrew"),
    FEED_NUT: (LEADSCREW_KIT, "FeedNut"),
    HOLD_DOWN_STUD: (CLAMPING_KIT, "HoldDownStud"),
    T_NUT: (CLAMPING_KIT, "TNut"),
    FLANGE_NUT: (CLAMPING_KIT, "FlangeNut"),
}
if any(family != f"{physical}--{member}" for family, (physical, member) in KIT_IDENTITIES.items()):
    raise AssertionError("a kit family key is not <physical>--<configuration>")
if (feed_nut.PART_NAME, leadscrew_stock.PART_NAME) != (LEADSCREW_KIT, LEADSCREW_KIT):
    raise AssertionError("the leadscrew kit's member specs name another physical part")
if (
    guide_rail.CONFIGURATION, carriage.CONFIGURATION,
    leadscrew_stock.CONFIGURATION, feed_nut.CONFIGURATION,
) != tuple(KIT_IDENTITIES[family][1] for family in (RAIL, CARRIAGE, LEADSCREW, FEED_NUT)):
    raise AssertionError("a kit family's configuration is not its member spec's")
# The fabricated configured members (not purchased kits: no SKU key).
FABRICATED_MEMBER_IDENTITIES = {
    BASE_BAR_1: (BASE_BAR, base_bar.BAR1),
    BASE_BAR_2: (BASE_BAR, base_bar.BAR2),
}
if tuple(member for _physical, member in FABRICATED_MEMBER_IDENTITIES.values()) != (
    base_bar.CONFIGURATIONS
):
    raise AssertionError("the jig's base bar members are not the part's configurations")
# Every configured member family, fabricated or purchased: each instance is a
# persisted role reference (``instance_name``).
MEMBER_IDENTITIES = {**FABRICATED_MEMBER_IDENTITIES, **KIT_IDENTITIES}
COMPONENT_IDENTITIES: dict[str, tuple[str, str | None]] = {
    family: (family, None) for family in BOM_ORDER
}
COMPONENT_IDENTITIES.update(MEMBER_IDENTITIES)


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
# One base bar part (TL-20, QTY 2), two members: rail 1 takes Bar1 as saved;
# rail 2 takes Bar2 turned over (180° about its long axis), which swaps its
# slots' sides so each slot still lands on its T-slot stud. Every Bar2
# feature goes through.
TURNED_OVER = {1: False, 2: True}
if base_bar.QUANTITY != len(RAILS) or len(BASE_BARS) != len(RAILS):
    raise AssertionError("one base bar under each rail")
if leadscrew.RAIL != RAILS.index(1) + 1 or TURNED_OVER[leadscrew.RAIL]:
    raise AssertionError("the bracket holes' Bar1 lies unturned under the leadscrew rail")


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
# the table; the bar and its datum-trimmed rail both run from
# RAIL_NEAR_S ⚙ to BASE_BAR_FAR_S ⚙, flush at both ends.
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
PIVOT_HEAD_UNDERSIDE_Z = PIVOT_SCREW_BOTTOM_Z + pivot_screw.SHOULDER_LENGTH
PIVOT_HEAD_TOP_Z = PIVOT_HEAD_UNDERSIDE_Z + pivot_screw.HEAD_HEIGHT
PART_TOP_Z = holding.PART_TOP_Z  # the strap's top face; no strap is modelled
if abs(PART_TOP_Z - (trammel.CARRIER_TOP_Z + trammel.RISER_THICK + trammel.STRAP_THICK)) > 1e-9:
    raise AssertionError("the holding proof's strap top is not the jig's stack")

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


# Rails: on each bar's top, flush with its near end at RAIL_NEAR_S ⚙ (rail_spec frame:
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
# The leadscrew feed (leadscrew_spec): the screw from its near end and the
# handwheel from its hub end, both along rail 1 away from the spindle (local
# +Y), the handwheel's grip up (local +X).
FEED_ROWS = axis_rows((0.0, 0.0, 1.0), rail_rows(leadscrew.RAIL)[0])
# The screw turned half round its axis, its set-screw flats (local +X) down,
# to the handwheel's supplied set screw in its -X tap: step 8B turns the wheel
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
# The TL-VN-84 kit's FeedNut seats on the integral lug's -X face, its body toward the
# spindle, its bore on the leadscrew axis: its axis (+Y) along the block's
# -X, its seat face (y = 0) on the lug face. It is turned 45° about that
# axis (+X onto the block's +Y+Z diagonal), so its four holes, at 0/90/180/
# 270° in its own frame, sit on the lug's diagonals over TL-32's taps.
_DIAGONAL = math.sqrt(0.5)
FEED_NUT_ROWS: Rows = axis_rows((0.0, _DIAGONAL, _DIAGONAL), (-1.0, 0.0, 0.0))
FEED_NUT_PLACEMENTS = (
    compose(
        FEED_BLOCK_PLACEMENTS[0],
        (feed_block.NUT_FACE_X, feed_block.NUT_AXIS_Y, feed_block.NUT_AXIS_Z),
        FEED_NUT_ROWS,
    ),
)
_NUT_HOLES_ON_LUG = sorted(
    (
        feed_block.NUT_AXIS_Y + x * FEED_NUT_ROWS[0][1] + z * FEED_NUT_ROWS[2][1],
        feed_block.NUT_AXIS_Z + x * FEED_NUT_ROWS[0][2] + z * FEED_NUT_ROWS[2][2],
    )
    for x, z in feed_nut.HOLE_CENTRES
)
if any(
    math.dist(hole, tap) > 1e-9
    for hole, tap in zip(_NUT_HOLES_ON_LUG, sorted(feed_block.NUT_HOLES_YZ), strict=True)
):
    raise AssertionError("the placed feed nut's holes are not over TL-32's taps")
# The four nut screws, flat heads seated nominally in the flange's
# countersinks: each head top feed_nut.SCREW_GRIP off the lug face, each
# screw's +Y (head) along the block's -X.
NUT_ROWS: Rows = ((0.0, 1.0, 0.0), (-1.0, 0.0, 0.0), (0.0, 0.0, 1.0))
NUT_SCREW_PLACEMENTS: tuple[Placement, ...] = tuple(
    compose(
        FEED_BLOCK_PLACEMENTS[0],
        (feed_block.NUT_FACE_X - feed_nut.SCREW_GRIP, y, z),
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
# Screws, head on its seat: rail 1's then rail 2's; the TL-28 bar screws (the
# same common screw) up from Bar1's underside, two per bracket; four per
# block into its carriage; two per KP08.
RAIL_SCREW_PLACEMENTS: tuple[Placement, ...] = tuple(
    compose(rail, (x, 0.0, trammel.RAIL_SCREW_SEAT_ABOVE_BASE), UPRIGHT_ROWS)
    for rail in RAIL_PLACEMENTS
    for x in guide_rail.HOLE_X
)
BAR_SCREW_PLACEMENTS: tuple[Placement, ...] = tuple(
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
# each lever screw's wedge-lock pair (TL-VN-71) on the feed lever and the
# screw's head on the pair.
RISER_SCREW_PLACEMENTS: tuple[Placement, ...] = tuple(
    _carried(
        point,
        trammel.CARRIER_TOP_Z
        + trammel.RISER_THICK
        - riser_screw.HEAD_TOP_BELOW_RISER_TOP,
    )
    for point in trammel.RISER_SCREWS
)
# The strap's holding (owner rulings 2026-11-07): the CL and CR common screws'
# heads on the strap's end waste; the brass top-hat washer's seat face on the
# strap at HUB (its spigot down into the reamed hub hole), the HUB common
# screw's head on the washer; the two loose stop pins chamfered end down on
# the carrier top in the riser's stop holes. No strap is modelled.
STRAP_CLAMP_ROLES = ("CL", "CR", "HUB")
STRAP_CLAMP_POINTS = {**carrier.END_CLAMPS, "HUB": carrier.HUB}
STRAP_CLAMP_SCREW_PLACEMENTS: tuple[Placement, ...] = (
    *(_carried(STRAP_CLAMP_POINTS[role], PART_TOP_Z) for role in ("CL", "CR")),
    _carried(STRAP_CLAMP_POINTS["HUB"], PART_TOP_Z + hub_washer.THICK),
)
HUB_WASHER_PLACEMENTS = ((_at(carrier.HUB, PART_TOP_Z), PIN_ROWS),)
STOP_PIN_PLACEMENTS: tuple[Placement, ...] = tuple(
    _carried(point, trammel.CARRIER_TOP_Z) for point in riser.STOP_PIN_CARRIER_POINTS
)
if tuple(STRAP_CLAMP_POINTS) != STRAP_CLAMP_ROLES:
    raise AssertionError("the strap clamps are not CL, CR then HUB")
# Each head top is the holding proof's (``holding.CLAMP_TOP_Z``, keyed "hub").
_HOLDING_CLAMP_KEYS = {"CL": "CL", "CR": "CR", "HUB": "hub"}
for _role, (_origin, _rows) in zip(STRAP_CLAMP_ROLES, STRAP_CLAMP_SCREW_PLACEMENTS, strict=True):
    _head_top = _origin[2] + rail_screw.DIMS.head_h
    if abs(_head_top - holding.CLAMP_TOP_Z[_HOLDING_CLAMP_KEYS[_role]]) > 1e-9:
        raise AssertionError(f"the {_role} clamp head is not the holding proof's height")
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
# The thickest nominal pack the worst case needs (.064), and the fewest stock
# shims making it (4: three .020 and one .004; greedy is exact for
# .020/.008/.004): the basis of the buy list below.
_PACK_MAX_THOU = math.ceil((_GAP_HI - _WIN_HI) / _STEP) * _STEP
_WORST_PACK: dict[int, int] = {}  # thou -> shims
_rest = _PACK_MAX_THOU
for _thou in reversed(_FIT_THOU):
    _WORST_PACK[_thou], _rest = divmod(_rest, _thou)
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
# P1's printed bound at the catalogue bands (Codjiflo P3 on #2112): with each
# shim size at either end of its band, every unshimmed gap across the range
# (in .00025 steps) closes into the window with a pack from one support's
# share, and P1 prints the thickest fewest-shim pack any such fit needs.
_SHARE = {thou: count // _SUPPORTS for thou, count in _BUY_THOU.items()}
_PACKS = [
    combo for combo in itertools.product(*(range(_SHARE[t] + 1) for t in _FIT_THOU)) if any(combo)
]
_fits: list[tuple[int, float]] = []
for _ends in itertools.product((0, 1), repeat=len(_FIT_THOU)):
    _actual = [
        thou * _THOU + pivot_shim.FIT_THICKNESS_BANDS[thou][end]
        for thou, end in zip(_FIT_THOU, _ends)
    ]
    for _quarter in range(4 * _GAP_LO, 4 * _GAP_HI + 1):
        _gap = _quarter * _THOU / 4.0
        _in_window = [
            (sum(combo), sum(n * t for n, t in zip(combo, _actual)))
            for combo in _PACKS
            if PIVOT_RUNNING_GAP[0] <= _gap - sum(n * t for n, t in zip(combo, _actual)) <= PIVOT_RUNNING_GAP[1]
        ]
        if not _in_window and _gap > PIVOT_RUNNING_GAP[1]:
            raise AssertionError(f"no banded shim pack fits a {_gap / trammel.INCH:.4f} gap")
        if _in_window:
            _fits.append(min(_in_window, key=lambda fit: (fit[0], -fit[1])))
PIVOT_FIT_SHIMS_MAX = max(count for count, _ in _fits)  # 4
PIVOT_FIT_PACK_MAX = math.ceil(max(pack for _, pack in _fits) / _THOU - 1e-9) * _THOU  # .066

# Every instance of every logical family, in insertion order. Ordinary families
# keep native <stem>-N names; kit instances use persisted role-local references.
PLACEMENTS: dict[str, tuple[Placement, ...]] = {
    BASE_BAR_1: (BASE_BAR_PLACEMENTS[RAILS.index(1)],),
    BASE_BAR_2: (BASE_BAR_PLACEMENTS[RAILS.index(2)],),
    CARRIER: ((CARRIER_ORIGIN, CARRIER_ROWS),),
    PIVOT_BLOCK: PIVOT_BLOCK_PLACEMENTS,
    FEED_BLOCK: FEED_BLOCK_PLACEMENTS,
    PIVOT_SCREW: PIVOT_SCREW_PLACEMENTS,
    PIVOT_SPACER: PIVOT_SPACER_PLACEMENTS,
    PIVOT_SHIM: PIVOT_SHIM_PLACEMENTS,
    RISER: ((RISER_ORIGIN, RISER_ROWS),),
    HUB_WASHER: HUB_WASHER_PLACEMENTS,
    FEED_LEVER: ((FEED_LEVER_ORIGIN, FEED_LEVER_ROWS),),
    END_BRACKET: END_BRACKET_PLACEMENTS,
    RAIL: RAIL_PLACEMENTS,
    CARRIAGE: CARRIAGE_PLACEMENTS,
    STOP_PIN: STOP_PIN_PLACEMENTS,
    LEADSCREW: LEADSCREW_PLACEMENTS,
    FEED_NUT: FEED_NUT_PLACEMENTS,
    PILLOW_BLOCK: PILLOW_BLOCK_PLACEMENTS,
    HANDWHEEL: HANDWHEEL_PLACEMENTS,
    HOLD_DOWN_STUD: HOLD_DOWN_STUD_PLACEMENTS,
    T_NUT: T_NUT_PLACEMENTS,
    FLANGE_NUT: FLANGE_NUT_PLACEMENTS,
    # One BOM row: the rail screws, then the strap's CL, CR and HUB clamps.
    RAIL_SCREW: RAIL_SCREW_PLACEMENTS + STRAP_CLAMP_SCREW_PLACEMENTS,
    CARRIAGE_SCREW: CARRIAGE_SCREW_PLACEMENTS,
    PILLOW_BLOCK_SCREW: PILLOW_BLOCK_SCREW_PLACEMENTS + BAR_SCREW_PLACEMENTS,
    # One BOM row, two joints: the riser's 4, then the feed nut's 4.
    RISER_SCREW: RISER_SCREW_PLACEMENTS + NUT_SCREW_PLACEMENTS,
    LEVER_SCREW: LEVER_SCREW_PLACEMENTS,
    LEVER_LOCK_WASHER: LEVER_LOCK_WASHER_PLACEMENTS,
}


def instance_name(stem: str, index: int) -> str:
    """Selector for family instance ``index`` (0-based), not a guessed member Name2."""
    if stem in MEMBER_IDENTITIES:
        return f"@{MEMBER_IDENTITIES[stem][1]}:{index + 1}"
    return f"{stem}-{index + 1}"


MEMBER_COMPONENT_REFERENCES = {
    instance_name(family, index): identity
    for family, identity in MEMBER_IDENTITIES.items()
    for index in range(QUANTITIES[family])
}
# The rail and bracket screw families' occurrences by joint (PLACEMENTS' order).
RAIL_SCREW_INSTANCES = tuple(
    instance_name(RAIL_SCREW, index) for index in range(len(RAIL_SCREW_PLACEMENTS))
)
KP08_SCREW_INSTANCES = tuple(
    instance_name(PILLOW_BLOCK_SCREW, index)
    for index in range(len(PILLOW_BLOCK_SCREW_PLACEMENTS))
)
BAR_SCREW_INSTANCES = tuple(
    instance_name(PILLOW_BLOCK_SCREW, len(PILLOW_BLOCK_SCREW_PLACEMENTS) + index)
    for index in range(len(BAR_SCREW_PLACEMENTS))
)
# The strap's three common clamp screws, by role: stable 0-based indices into
# the rail screw family after its rail occurrences, and their
# ``instance_name`` selectors (rail-screw-17, -18, -19). A view that hides the
# strap's holding hides exactly these occurrences, never the whole common
# stem, whose rail occurrences stay on the bars.
STRAP_CLAMP_SCREW_INDICES = {
    role: len(RAIL_SCREW_PLACEMENTS) + offset
    for offset, role in enumerate(STRAP_CLAMP_ROLES)
}
STRAP_CLAMP_SCREW_INSTANCES = {
    role: instance_name(RAIL_SCREW, index) for role, index in STRAP_CLAMP_SCREW_INDICES.items()
}
if max(STRAP_CLAMP_SCREW_INDICES.values()) + 1 != QUANTITIES[RAIL_SCREW]:
    raise AssertionError("the strap clamps are not the common screw's last occurrences")
# The riser screw family's occurrences by joint (PLACEMENTS' order).
RISER_SCREW_INSTANCES = tuple(
    instance_name(RISER_SCREW, index) for index in range(len(RISER_SCREW_PLACEMENTS))
)
NUT_SCREW_INSTANCES = tuple(
    instance_name(RISER_SCREW, len(RISER_SCREW_PLACEMENTS) + index)
    for index in range(len(NUT_SCREW_PLACEMENTS))
)


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
# ``None``: an occurrence of a partly moving family that stays fixed (the
# common screw's rail occurrences; its strap clamps ride).
LOCKED_TO: dict[str, tuple[tuple[str, int] | None, ...]] = {
    FEED_BLOCK: ((CARRIAGE, 0),),
    PIVOT_BLOCK: ((CARRIAGE, 1),),
    PIVOT_SCREW: _SUPPORT_PARENTS,
    PIVOT_SPACER: _SUPPORT_PARENTS,
    PIVOT_SHIM: tuple(parent for parent in _SUPPORT_PARENTS for _ in range(pivot_shim.PER_SUPPORT)),
    CARRIAGE_SCREW: tuple(parent for parent in _SUPPORT_PARENTS for _ in pivot_block.BOLT_POINTS),
    FEED_NUT: ((FEED_BLOCK, 0),),
    RISER: ((CARRIER, 0),),
    RISER_SCREW: (
        *((CARRIER, 0) for _ in trammel.RISER_SCREWS),
        *((FEED_BLOCK, 0) for _ in feed_block.NUT_HOLES_YZ),
    ),
    HUB_WASHER: ((CARRIER, 0),),
    FEED_LEVER: ((CARRIER, 0),),
    LEVER_SCREW: tuple((CARRIER, 0) for _ in carrier.LEVER_HOLES),
    STOP_PIN: tuple((CARRIER, 0) for _ in riser.STOP_PIN_CARRIER_POINTS),
    RAIL_SCREW: (
        *(None for _ in RAIL_SCREW_PLACEMENTS),
        *((CARRIER, 0) for _ in STRAP_CLAMP_SCREW_PLACEMENTS),
    ),
    LEVER_LOCK_WASHER: tuple((CARRIER, 0) for _ in carrier.LEVER_HOLES),
}


def is_moving(stem: str, index: int) -> bool:
    """True when ``stem``'s occurrence ``index`` (0-based) rides the sweep."""
    if stem in (CARRIAGE, CARRIER):
        return True
    parents = LOCKED_TO.get(stem)
    return parents is not None and parents[index] is not None


# Every family with an occurrence that rides the sweep, in BOM order.
MOVING = tuple(
    stem for stem in BOM_ORDER
    if any(is_moving(stem, index) for index in range(QUANTITIES[stem]))
)
# Every occurrence that rides the sweep, family by family in BOM order.
MOVING_INSTANCES = tuple(
    instance_name(stem, index)
    for stem in MOVING
    for index in range(QUANTITIES[stem])
    if is_moving(stem, index)
)
# Every occurrence lock-mated directly to the carrier: what a view hides to
# show the slides without the carrier and its load.
CARRIER_RIDERS = tuple(
    instance_name(stem, index)
    for stem in BOM_ORDER
    for index, parent in enumerate(LOCKED_TO.get(stem, ()))
    if parent is not None and parent[0] == CARRIER
)
if not set(STRAP_CLAMP_SCREW_INSTANCES.values()) <= set(CARRIER_RIDERS):
    raise AssertionError("the strap clamp screws do not ride the carrier")
if set(RAIL_SCREW_INSTANCES + BAR_SCREW_INSTANCES) & set(MOVING_INSTANCES):
    raise AssertionError("a rail or TL-28 bar screw rides the sweep")
# Their native files, in the same order: the contract's allowed and required
# free stems. The free-DOF gate reads a component's Name2 less its instance
# suffix, so a moving kit member counts under its kit's physical stem (the
# rail kit's Carriage, the leadscrew kit's FeedNut; Rail and LeadScrew stay
# fixed in the same files).
MOVING_STEMS = tuple(dict.fromkeys(COMPONENT_IDENTITIES[stem][0] for stem in MOVING))


def lock_parent(stem: str, index: int) -> str:
    """The instance that ``stem``'s instance ``index`` (0-based) is locked to."""
    parent = LOCKED_TO[stem][index]
    if parent is None:
        raise ValueError(f"{instance_name(stem, index)} is fixed, not lock-mated")
    return instance_name(*parent)


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
# The TL-VN-83 kit rail and carriages carry the owner's description note
# under the BOM (BOM_NOTE, #2177). Screws by their fastener-table callout.
BOM_DESCRIPTIONS = {
    # The base bar members print their native configuration descriptions.
    BASE_BAR_1: base_bar.CONFIGURATION_DESCRIPTIONS[base_bar.BAR1],
    BASE_BAR_2: base_bar.CONFIGURATION_DESCRIPTIONS[base_bar.BAR2],
    PIVOT_BLOCK: "PIVOT BLOCK",
    FEED_BLOCK: "FEED BLOCK",
    PIVOT_SCREW: "5/16-18 SHOULDER SCREW, 3/8 X 1-1/2",
    PIVOT_SPACER: "SPACER, 3/8 ID X 5/8 OD X 5/8",
    PIVOT_SHIM: "SHIM 3/8 X 5/8, FITTING STOCK",
    CARRIER: "CARRIER PLATE",
    RISER: "6061 RISER",
    HUB_WASHER: "BRASS TOP-HAT HUB CLAMP WASHER",
    FEED_LEVER: "FEED LEVER",
    END_BRACKET: "END BRACKET",
    # Kit members print their native per-configuration descriptions.
    RAIL: guide_rail.BOM_DESCRIPTION,
    CARRIAGE: carriage.BOM_DESCRIPTION,
    STOP_PIN: "DOWEL PIN 1/8 X 3/4, LOOSE END STOP",
    # Vendor-metric rows keep their millimetres, labelled (#290).
    LEADSCREW: leadscrew_stock.BOM_DESCRIPTION,
    FEED_NUT: feed_nut.BOM_DESCRIPTION,
    # TL-00 review (2026-11-02): the row names the KP08 the steps cite.
    PILLOW_BLOCK: f"KP08 PILLOW BLOCK, {leadscrew.KP08_BORE:.0f} MM BORE",
    HANDWHEEL: f"HANDWHEEL {leadscrew.HANDWHEEL_WHEEL_DIA:.0f} MM DIA, 8 MM BORE",
    HOLD_DOWN_STUD: hold_down_stud.BOM_DESCRIPTION,
    T_NUT: t_nut.BOM_DESCRIPTION,
    FLANGE_NUT: flange_nut.BOM_DESCRIPTION,
    RAIL_SCREW: rail_screw.CALLOUT,
    CARRIAGE_SCREW: carriage_screw.CALLOUT,
    PILLOW_BLOCK_SCREW: bracket_screw.CALLOUT,
    RISER_SCREW: f"{riser_screw.CALLOUT} SCREW",
    LEVER_SCREW: lever_screw.CALLOUT,
    LEVER_LOCK_WASHER: f"{lever_washer.SCREW_SIZE} WEDGE-LOCK WASHER PAIR",
}
# BOM item n is BOM_ORDER position n: the builder inserts each family's first
# instance in BOM_ORDER sequence (SolidWorks numbers a top-level BOM in
# FeatureManager order), and the steps cite items by these numbers.
ITEM_NUMBERS = {stem: str(index) for index, stem in enumerate(BOM_ORDER, 1)}

# --- Native explode (JIG_EXPLODED) -------------------------------------------------
# Presentation separates the pivot stacks and carrier. The strap clamps, the
# top-hat washer and the loose stop pins lift out above the carrier's riders.
# (label, selectors, axis, signed distance mm).
EXPLODED_VIEW_NAME = "JIG_EXPLODED"
SOURCE_CONFIGURATION = "Default"
_END_CLAMP_SCREWS = tuple(STRAP_CLAMP_SCREW_INSTANCES[role] for role in ("CL", "CR"))
_HUB_CLAMP_SCREW = STRAP_CLAMP_SCREW_INSTANCES["HUB"]
_BLOCK_RIDERS = (CARRIAGE_SCREW, FEED_NUT, *NUT_SCREW_INSTANCES, PIVOT_SHIM, PIVOT_SPACER)
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
    ("end clamp screws lift out", _END_CLAMP_SCREWS, "z", 40.0),
    ("hub clamp screw lifts out", (_HUB_CLAMP_SCREW,), "z", 110.0),
    ("hub washer lifts off", (HUB_WASHER,), "z", 85.0),
    ("stop pins lift out", (STOP_PIN,), "z", 60.0),
    ("riser screws lift out", RISER_SCREW_INSTANCES, "z", 30.0),
    (
        "riser lifts off",
        (RISER, *RISER_SCREW_INSTANCES, *_END_CLAMP_SCREWS, STOP_PIN),
        "z",
        60.0,
    ),
    ("carrier lifts off the pins", (CARRIER, *CARRIER_RIDERS), "z", 230.0),
    ("nut screws back out", NUT_SCREW_INSTANCES, "x", 30.0),
    ("blocks lift off", (PIVOT_BLOCK, FEED_BLOCK, *_BLOCK_RIDERS), "z", 90.0),
    ("carriage screws lift out", (CARRIAGE_SCREW,), "z", 60.0),
    ("carriages lift off the rails", (CARRIAGE,), "z", 50.0),
    ("rail screws lift out", RAIL_SCREW_INSTANCES, "z", 35.0),
    ("handwheel slides off", (HANDWHEEL,), "x", -50.0),
    ("kp08 screws lift out", KP08_SCREW_INSTANCES, "z", 40.0),
    ("bar screws drop out", BAR_SCREW_INSTANCES, "z", -40.0),
    ("flange nuts lift off", (FLANGE_NUT,), "z", 60.0),
    ("t-nuts drop out", (T_NUT,), "z", -30.0),
)
# Shown where they are fitted: the table-side structure and the feed's
# stationary parts every exploded item is read against.
EXPLODE_STATIC = (
    *BASE_BARS,
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
        identity = MEMBER_COMPONENT_REFERENCES.get(component_or_family)
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


# The lifted stop pins stand clear above the lifted riser, the end clamp
# screws' tips clear above its top, and the hub screw's tip above its washer.
_RISER_TOP_EXPLODED = trammel.CARRIER_TOP_Z + trammel.RISER_THICK + explode_lift(RISER)
if trammel.CARRIER_TOP_Z + explode_lift(STOP_PIN) <= _RISER_TOP_EXPLODED:
    raise AssertionError("the exploded stop pins stand in the riser")
for _screw in _END_CLAMP_SCREWS:
    _tip = PART_TOP_Z - rail_screw.DIMS.length + explode_lift(_screw)
    if _tip <= _RISER_TOP_EXPLODED:
        raise AssertionError(f"the exploded {_screw} stands in the riser")
if (
    PART_TOP_Z + hub_washer.THICK - rail_screw.DIMS.length + explode_lift(_HUB_CLAMP_SCREW)
    <= PART_TOP_Z + hub_washer.THICK + explode_lift(HUB_WASHER)
):
    raise AssertionError("the exploded hub screw stands in its washer")
# Every occurrence's selector, ``instance_name`` by family and index.
INSTANCE_NAMES = frozenset(
    instance_name(family, index)
    for family in BOM_ORDER
    for index in range(QUANTITIES[family])
)


def explode_occurrences(selector: str) -> tuple[str, ...]:
    """The occurrences an explode selector moves: a family's every instance,
    or the one ``instance_name`` occurrence it names (the riser and nut
    screws share a family but explode apart)."""
    if selector in QUANTITIES:
        return tuple(instance_name(selector, index) for index in range(QUANTITIES[selector]))
    if selector in INSTANCE_NAMES:
        return (selector,)
    raise ValueError(f"unknown explode selector: {selector}")


_moved = {
    occurrence
    for _label, _selectors, _axis, _distance in EXPLODE_STEPS
    for _selector in _selectors
    for occurrence in explode_occurrences(_selector)
}
_static = {
    instance_name(family, index)
    for family in EXPLODE_STATIC
    for index in range(QUANTITIES[family])
}
if _moved & _static or _moved | _static != INSTANCE_NAMES:
    raise AssertionError("every occurrence is exploded or deliberately static, not both")
_RAIL_SCREW_TOP_EXPLODED = RAIL_TOP_Z + max(map(explode_lift, RAIL_SCREW_INSTANCES))
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
    "MACHINE ORIGIN: SPINDLE AT TABLE TOP; +Y TOWARD COLUMN. "
    "NO STRAP SHOWN; ITS CLAMPS AND STOP PINS AS FITTED."
)


def _station_row(station: float) -> str:
    """One table row: each rail's pin at ``station``, machine X/Y."""
    (x1, y1), (x2, y2) = (trammel.rail_point(rail, station) for rail in (1, 2))
    x1, y1, x2, y2 = (_length(v, ALIGNMENT_PLACES) for v in (x1, y1, x2, y2))
    return (
        f"S {_length(station, 2):>5}: RAIL 1 X {x1:>8} Y {y1:>7}; "
        f"RAIL 2 X {x2:>8} Y {y2:>7}"
    )


# Review bought-tl000-r1: the checks' "sweep of each pass" gets its range,
# each pin's station over ±trammel.SWEEP, rounded outward. Review jig-asm r2
# (2026-11-02): no stop ends a pass, so step 6 and its HD3 repeat set a pin
# at each limit as at a station and witness-mark its bar at the carriage;
# every complete pass runs mark to mark. Rounded outward to .01, a limit
# stays well inside the leadscrew.FEED_GAP the feed lug keeps to its KP08 at
# the exact travel end.
SWEEP_LIMIT_PLACES = 2
SWEEP_LIMITS = {
    name: (
        _outward(lo, SWEEP_LIMIT_PLACES, up=False),
        _outward(hi, SWEEP_LIMIT_PLACES, up=True),
    )
    for name, (lo, hi) in trammel.PIN_TRAVEL.items()
}


def _sweep_lines() -> tuple[str, ...]:
    spans = ", ".join(
        f"{name.upper()} {_length(lo, SWEEP_LIMIT_PLACES)} TO "
        f"{_length(hi, SWEEP_LIMIT_PLACES)}"
        for name, (lo, hi) in SWEEP_LIMITS.items()
    )
    return (
        f"SWEEP LIMITS, EACH PIN AT S: {spans}; NO STOP ENDS A PASS. STEP 6 "
        "AND HD3 SET EACH PIN AT EACH LIMIT BELOW AS AT A STATION AND "
        "WITNESS-MARK ITS BAR AT THE CARRIAGE'S SPINDLE-END FACE, I OR O BY "
        "PASS. A COMPLETE PASS RUNS EACH CARRIAGE MARK TO MARK:",
        *(
            _station_row(s)
            for s in sorted(s for limits in SWEEP_LIMITS.values() for s in limits)
        ),
    )


ALIGNMENT_NOTE_LINES = (
    "RAIL ALIGNMENT TARGETS: PIVOT PIN AXIS, MACHINE X/Y FROM THE SPINDLE, "
    "AT STATION S FROM THE SPINDLE ALONG THE RAIL "
    f"(±{_length(ALIGNMENT_BAND, ALIGNMENT_PLACES)})",
    *(_station_row(station) for station in trammel.ALIGNMENT_TARGETS),
)
SWEEP_NOTE_LINES = _sweep_lines()

# Every screw by its fastener-table callout (fasteners.FASTENERS) and every
# bought item by its BOM item number.
_RAIL_SCREW = fasteners.callout(fasteners.RAIL_TO_BAR)
_BAR_SCREW = fasteners.callout(fasteners.BRACKET_TO_BAR)
_CARRIAGE_SCREW = fasteners.callout(fasteners.BLOCK_TO_CARRIAGE)
_KP08_SCREW = fasteners.callout(fasteners.KP08_TO_BRACKET)
_RISER_SCREW = fasteners.callout(fasteners.RISER_TO_CARRIER)
_CLAMP_SCREW = fasteners.callout(fasteners.END_CLAMP)  # CL, CR and HUB alike
if fasteners.callout(fasteners.HUB_CLAMP) != _CLAMP_SCREW:
    raise AssertionError("the HUB clamp is not the end clamps' common screw")
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
)  # 1361
# FEED_THRUST_N is the crank's abuse envelope, not the cutting load.
#
# The normal finish feed's thrust, from the cut itself: the 3/8 four-flute
# HSS cutter (trammel.PART_CUTTER_DIA) on the rocker arm's low-carbon steel at
# cutting-data.toml's profile chip load for that cutter (0.0254 mm/tooth).
# Specific cutting force kc = kc1 h^-mc with kc1 1500 N/mm², mc 0.22
# (SOURCED: Machining Doctor, Specific Cutting Force, material group 02,
# low-carbon steel), h the chip load (its maximum, a full-slot entry). Each
# tooth's tangential force kc ap h over the whole strap (ap = STRAP_THICK,
# one pass). AUTHOR'S CHOICE: at most two teeth cut at once (a full slot,
# 4 flutes) and each tooth's radial force is no larger than its tangential,
# so the cutter's resultant is at most 2 sqrt(2) times one tooth's.
_CUT_KC1_MPA = 1500.0
_CUT_MC = 0.22
_CUT_TEETH_ENGAGED = 2
NORMAL_FEED_CHIP_LOAD_MM = 0.0254  # cutting-data.toml: low-carbon steel, HSS profile, 3-12.7
_CUT_KC_MPA = _CUT_KC1_MPA * NORMAL_FEED_CHIP_LOAD_MM ** (-_CUT_MC)  # 3364
_CUT_TOOTH_FORCE_N = _CUT_KC_MPA * trammel.STRAP_THICK * NORMAL_FEED_CHIP_LOAD_MM  # 213
NORMAL_CUT_FORCE_N = _CUT_TEETH_ENGAGED * math.sqrt(2.0) * _CUT_TOOTH_FORCE_N  # 602


def _feed_ratio(theta: float) -> float:
    """Leadscrew thrust per newton along the cutter's path (virtual work):
    the cutter centre moves R dθ while carriage 1's pin moves
    ds_A = R cos((ALPHA + θ)/2) dθ (trammel.pin_station)."""
    return 1.0 / math.cos((trammel.ALPHA + theta) / 2.0)


NORMAL_FEED_RATIO = max(
    _feed_ratio(sign * trammel.SWEEP[name])
    for name in trammel.PASS_RADIUS
    for sign in (-1.0, 1.0)
)  # 1.03 at the sweep's end
NORMAL_FEED_THRUST_N = NORMAL_CUT_FORCE_N * NORMAL_FEED_RATIO  # 619
# Owner ruling Main 2026-11-06 (option B; replaces the 2026-10-27 slip-governs
# criterion for TL-28 on TL-20 only): no slip under the normal feed; above
# leadscrew.BRACKET_SLIP_THRUST (1344 N, handwheel abuse) TL-28 may slip onto
# its bar screws' positive thread stop, which carries the abuse envelope.
# The heel's elastic opening (leadscrew.BRACKET_OPENING_THRUST) is reported.
if leadscrew.BRACKET_SLIP_THRUST < leadscrew.SLIP_MARGIN_MIN * NORMAL_FEED_THRUST_N:
    raise AssertionError(
        f"TL-28 slips at {leadscrew.BRACKET_SLIP_THRUST:.0f} N, under "
        f"{leadscrew.SLIP_MARGIN_MIN} x the {NORMAL_FEED_THRUST_N:.0f} N normal feed"
    )
BRACKET_ABUSE_THRUST_N = max(FEED_THRUST_N, leadscrew.HAND_ABUSE_THRUST)  # 1361
BRACKET_ABUSE_STOP_MARGINS = leadscrew.bracket_stop_margins(BRACKET_ABUSE_THRUST_N)
for _check, _margin in BRACKET_ABUSE_STOP_MARGINS.items():
    if _margin < leadscrew.STOP_MARGIN_MIN:
        raise AssertionError(
            f"TL-28's positive stop fails its {_check} at the "
            f"{BRACKET_ABUSE_THRUST_N:.0f} N crank envelope ({_margin:.2f})"
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

# --- The feed nut: the countersunk heads key it; their preload holds it on -----
# LOAD_CASES: four #4-40 X 5/8 flat heads (TL-VN-67) hold the bought TL-VN-84 FeedNut
# brass nut flat on the feed-block lug (owner ruling 2026-11-04, #2177
# option B). The leadscrew tries to turn the nut, one way then the other as
# the handwheel reverses. The four heads, seated in the nut's 82° countersinks
# and threaded into the lug, take that torque as a positive stop (Main ruling
# 2026-11-03 on #2112 Codjiflo P1: no friction is counted on). Their preload
# alone holds the nut against the leadscrew's pull: a static clamp (rule 23's
# last bullet), no lock, as the owner ruled for the bought nut's flange
# before (TL-00 review jbf-r17; issue #1630). Engagement: the worst-case full
# thread in the lug's THRU tap (feed_nut.SCREW_FULL_THREAD_MIN).
_NUT_SCREW_STRIP_N = (
    0.75
    * math.pi
    * fasteners.NUT_TO_FEED_BLOCK.major_mm
    * feed_nut.SCREW_FULL_THREAD_MIN
    * _AL_SHEAR_ULTIMATE_MPA
)  # 13.0 kN
# Each head's cone bears on the brass over the least countersink's band
# (feed_nut.CSK_BEARING_AREA_MIN, projected). The listing states no brass
# alloy; the jig takes 360-H02 (half hard), yield 17 ksi = 117.2 MPa
# (SOURCED: OnlineMetals #1500 listing, 2026-11-01).
_BRASS_YIELD_MPA = 17_000.0 * 0.006894757
_NUT_SCREW_PRELOAD_CAP_N = min(
    _NUT_SCREW_STRIP_N / _STRIP_SAFETY,
    _BRASS_YIELD_MPA * feed_nut.CSK_BEARING_AREA_MIN,
)
# Separation: with no joint-stiffness credit, the four screws' preload alone
# exceeds the largest thrust that pulls the nut off the lug (below), still
# under the tap's and the brass's caps.
NUT_SCREW_TORQUE_NM = 0.3
NUT_SCREW_PRELOAD_N = NUT_SCREW_TORQUE_NM / (
    _NUT_FACTOR * fasteners.NUT_TO_FEED_BLOCK.major_mm / 1000.0
)  # 527
NUT_SCREW_BEARING_MPA = NUT_SCREW_PRELOAD_N / feed_nut.CSK_BEARING_AREA_MIN  # 102
if NUT_SCREW_PRELOAD_N > _NUT_SCREW_PRELOAD_CAP_N:
    raise ValueError(
        f"nut screws at {NUT_SCREW_TORQUE_NM} N·m preload {NUT_SCREW_PRELOAD_N:.0f} N, "
        f"over the {_NUT_SCREW_PRELOAD_CAP_N:.0f} N the tap and the brass carry"
    )
# The screw: the preload's stress on the #4-40 tensile stress area
# (0.00604 in², ASME B1.1) stays under half the 18-8 screw's 80,000 psi
# (SOURCED: McMaster-Carr 91771A112 page, read 2026-10-19).
_NUT_SCREW_STRESS_AREA_MM2 = 0.00604 * trammel.INCH**2
_NUT_SCREW_TENSILE_MPA = 80_000.0 * 0.006894757
if not NUT_SCREW_PRELOAD_N / _NUT_SCREW_STRESS_AREA_MM2 < 0.5 * _NUT_SCREW_TENSILE_MPA:
    raise ValueError(f"nut screw preload {NUT_SCREW_PRELOAD_N:.0f} N overloads it")
# The largest thrust the nut takes: the firm crank pull (FEED_THRUST_N) or
# the 1 kN hand abuse (leadscrew LOAD_CASES), whichever is greater.
NUT_THRUST_N = max(FEED_THRUST_N, leadscrew.HAND_ABUSE_THRUST)  # 1361
NUT_PULL_OFF_MARGIN = fasteners.NUT_TO_FEED_BLOCK.count * NUT_SCREW_PRELOAD_N / NUT_THRUST_N
if NUT_PULL_OFF_MARGIN < 1.0:
    raise ValueError(
        f"the nut screws' {fasteners.NUT_TO_FEED_BLOCK.count} x "
        f"{NUT_SCREW_PRELOAD_N:.0f} N preload lets the {NUT_THRUST_N:.0f} N "
        "thrust pull the nut off the lug"
    )
# RV-02's thread wall: that thrust runs axially from the thread through the
# nut's body into its flange (the lug seat reacts it one way, the screws'
# preload the other). On the bare annulus between the thread's Ø8.5 major
# and the body's Ø10.0 receipt minimum, its teeth not credited, it stays
# under the brass's yield.
NUT_BODY_WALL_MPA = NUT_THRUST_N / (
    math.pi / 4.0 * (feed_nut.BODY_DIA_MIN**2 - feed_nut.THREAD_MAJOR_DIA**2)
)  # 62
NUT_BODY_WALL_MARGIN = _BRASS_YIELD_MPA / NUT_BODY_WALL_MPA  # 1.9
if NUT_BODY_WALL_MARGIN < 1.5:
    raise ValueError(
        f"the nut's thread wall takes {NUT_BODY_WALL_MPA:.0f} MPa, over 1/1.5 of "
        f"the brass's {_BRASS_YIELD_MPA:.0f} MPa yield"
    )
# The torque that thrust puts on the nut: T = F d2/2 tan(lead + friction),
# the oiled thread above.
NUT_TORQUE_NM = (
    NUT_THRUST_N * _TR_PITCH_DIA / 2000.0 * math.tan(_LEAD_ANGLE + _FRICTION_ANGLE)
)  # 1.19
# The four heads share it at the holes' PCD radius. Each screw takes its
# share across its #4-40 minor section at the nut-lug face (ASME B1.1 basic
# minor .0813 in), against 0.6 x its 80,000 psi tensile as the shear
# ultimate (the common estimate); the countersunk head's own seat carries
# the share into the brass.
NUT_STOP_FORCE_N = NUT_TORQUE_NM * 1000.0 / (
    fasteners.NUT_TO_FEED_BLOCK.count * feed_nut.HOLE_PCD / 2.0
)  # 37
_NUT_SCREW_MINOR_AREA_MM2 = math.pi / 4.0 * (0.0813 * trammel.INCH) ** 2
NUT_STOP_SHEAR_CAPACITY_N = 0.6 * _NUT_SCREW_TENSILE_MPA * _NUT_SCREW_MINOR_AREA_MM2
NUT_STOP_MARGIN = NUT_STOP_SHEAR_CAPACITY_N / NUT_STOP_FORCE_N  # 30
if NUT_STOP_MARGIN < leadscrew.SLIP_MARGIN_MIN:
    raise ValueError(
        f"the nut screws' shear margin {NUT_STOP_MARGIN:.2f} is under "
        f"{leadscrew.SLIP_MARGIN_MIN} at the nut's {NUT_TORQUE_NM:.2f} N·m"
    )
# 6061-T6 yield, 276 MPa (SOURCED: ASM / MatWeb 6061-T6), taken as the
# compressive yield; the lever's wedge-lock pairs below bear on it.
_AL_YIELD_MPA = 276.0
_NUT_TORQUE = _torque(NUT_SCREW_TORQUE_NM)

# --- The KP08 screws: their tightening torque -----------------------------------
# Each #8-32 X 5/8 SHCS (TL-VN-62; owner ruling Main 2026-11-06, option B,
# expressly approves this second length) clamps a KP08's cast foot to TL-28.
# The listing's title says zinc alloy and its description cast iron; the jig
# takes the weaker, zinc (Zamak 3, yield 208 MPa, SOURCED: AZoM
# https://www.azom.com/article.aspx?ArticleID=9565, read 2026-11-04). The
# head's least flat bearing (bracket_screw.HEAD_BEARING_DIA_MIN, .241 in: ASME
# B18.3 Table 1 #8, A min .257 less K .008 each edge, note (12)) bears on
# the foot round the Ø5 hole (UNVERIFIED, #2184) with the
# block floated fully to one side (bracket_screw.HOLE_FLOAT); the tap is the
# worst-case full thread in TL-28's 6061 top-face thread. The torque is kept
# at 1.0 N·m for the zinc foot. This is a seating torque: the KP08-to-TL-28
# joint's slip under thrust was never checked (an inherited open question,
# not certified here).
_ZAMAK_YIELD_MPA = 208.0
KP08_SCREW_TORQUE_NM = 1.0
KP08_SCREW_PRELOAD_N = KP08_SCREW_TORQUE_NM / (
    _NUT_FACTOR * fasteners.KP08_TO_BRACKET.major_mm / 1000.0
)  # 1200
KP08_SCREW_ENGAGEMENT_MIN = leadscrew.full_thread_min(
    fasteners.KP08_TO_BRACKET.length, leadscrew.KP08_FOOT_THICK, fasteners.KP08_TO_BRACKET.thread
)  # 8.67
if KP08_SCREW_ENGAGEMENT_MIN < leadscrew.ENGAGEMENT_TARGET_D * fasteners.KP08_TO_BRACKET.major_mm:
    raise ValueError("the KP08 screws engage TL-28 under 2 D")
_KP08_STRIP_N = (
    0.75
    * math.pi
    * fasteners.KP08_TO_BRACKET.major_mm
    * KP08_SCREW_ENGAGEMENT_MIN
    * _AL_SHEAR_ULTIMATE_MPA
)  # 17.6 kN


def _circle_overlap_mm2(r1: float, r2: float, d: float) -> float:
    """Area common to two circles of radii ``r1`` and ``r2``, ``d`` apart."""
    if d >= r1 + r2:
        return 0.0
    if d <= abs(r1 - r2):
        return math.pi * min(r1, r2) ** 2
    a1 = r1 * r1 * math.acos((d * d + r1 * r1 - r2 * r2) / (2.0 * d * r1))
    a2 = r2 * r2 * math.acos((d * d + r2 * r2 - r1 * r1) / (2.0 * d * r2))
    kite = 0.5 * math.sqrt((-d + r1 + r2) * (d + r1 - r2) * (d - r1 + r2) * (d + r1 + r2))
    return a1 + a2 - kite


KP08_FOOT_BEARING_MM2 = math.pi * bracket_screw.HEAD_BEARING_R**2 - _circle_overlap_mm2(
    bracket_screw.HEAD_BEARING_R, leadscrew.KP08_HOLE_DIA / 2.0, bracket_screw.HOLE_FLOAT
)
KP08_FOOT_BEARING_MPA = KP08_SCREW_PRELOAD_N / KP08_FOOT_BEARING_MM2
# The #8-32 tensile stress area, 0.0140 in² (ASME B1.1), against half the
# 91251A196's tensile (bracket_screw.TENSILE_PSI).
_KP08_SCREW_STRESS_AREA_MM2 = leadscrew.SHCS_8_STRESS_AREA_MM2
_KP08_SCREW_TENSILE_MPA = bracket_screw.TENSILE_PSI * 0.006894757
KP08_SCREW_MARGINS = {
    "foot bearing": _ZAMAK_YIELD_MPA / KP08_FOOT_BEARING_MPA,
    "TL-28 thread strip": _KP08_STRIP_N / _STRIP_SAFETY / KP08_SCREW_PRELOAD_N,
    "screw stress": 0.5 * _KP08_SCREW_TENSILE_MPA
    / (KP08_SCREW_PRELOAD_N / _KP08_SCREW_STRESS_AREA_MM2),
}
for _check, _margin in KP08_SCREW_MARGINS.items():
    if _margin < 1.0:
        raise ValueError(
            f"the KP08 screws at {KP08_SCREW_TORQUE_NM} N·m fail their {_check} "
            f"budget ({_margin:.2f})"
        )
_KP08_TORQUE = _torque(KP08_SCREW_TORQUE_NM)


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
# (lever_washer.BEARING_AREA_MIN): under the 6061-T6 yield (_AL_YIELD_MPA).
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


# The rocker-arm process plan (cad/process/ch_rocker_arm/plan.toml, the held
# route for MHA-CH-06 and its MHA-CH-13 strap) owns the blank, its chords, its
# loose CL/CR holes and the strap hub's drill/ream with its tool envelope;
# TL-00 cites its operations and repeats none of its numbers.
PROCESS_PLAN = "MHA-CH-06 PLAN"
# The in-situ HUB position (owner ruling 3, 2026-11-07): step 10 taps the
# carrier's HUB there and every strap's hub hole is drilled and reamed at the
# same DRO setting, so their relative eccentricity is the DRO's repeatability,
# not an independent table tolerance (carrier.HUB_RADIAL_STACK).
_HUB_DRO = (
    f"X 0, Y {_length(carrier.HUB_OFFSET_PRINTED, carrier.HUB_OFFSET_PLACES)} "
    f"±{_length(carrier.HUB_OFFSET_BAND, carrier.HUB_OFFSET_PLACES)}"
)
_STRAP_CLAMPS = f"{_CLAMP_SCREW} {_item(RAIL_SCREW)}"
# The riser's installed stop-pin axes (R4Geometry, 2026-11-07): ONE ordinary
# 2-place station on the carrier, read on the DRO at the step 10 symmetric
# position, set before any riser hole is spotted from the carrier, so no
# second riser-placement band stacks on it (riser.STOP_RAW_Y_LIMITS).
_STOP_AXIS_PLACES = 2
_STOP_AXIS_BAND = printed_band_mm(_STOP_AXIS_PLACES, unit=UNIT)
if abs(
    riser.STOP_RAW_Y_LIMITS[1] - riser.STOP_PIN_CARRIER_POINTS[0][1]
    - riser.STOP_PIN_DIA_LIMITS[1] / 2.0 - riser.STOP_PIN_TILT_RADIUS - _STOP_AXIS_BAND
) > 1e-9:
    raise AssertionError("the stop-axis band is not the riser's stop-chain band")
_STOP_X = {abs(x) for x, _y in riser.STOP_PIN_CARRIER_POINTS}
_STOP_Y = {y for _x, y in riser.STOP_PIN_CARRIER_POINTS}
if len(_STOP_X) != 1 or len(_STOP_Y) != 1:
    raise AssertionError("the stop pins no longer stand symmetric on one Y")
_STOP_DRO = (
    f"X ±{_length(_STOP_X.pop(), _STOP_AXIS_PLACES)}, "
    f"Y {_length(_STOP_Y.pop(), _STOP_AXIS_PLACES)} "
    f"±{_length(_STOP_AXIS_BAND, _STOP_AXIS_PLACES)}"
)
# The shared stud REWORK sheet points to this installed-stack acceptance.
OPERATION_SHEET_NUMBER = 9
HOLD_DOWN_REFERENCE = f"{DRAWING_NUMBER}, STEPS HD1-HD4 (SHEET {OPERATION_SHEET_NUMBER})"
# Review jig-asm r1 (minor): the screws and nuts whose steps state no
# torque. Their fastener specs carry no torque figure, so rule 24's one
# general note gives the conventional snug instruction, no invented value.
SNUG_FASTENERS = (
    FLANGE_NUT,
    RAIL_SCREW,
    CARRIAGE_SCREW,
    RISER_SCREW,
)
_SNUG_ITEMS = sorted(int(ITEM_NUMBERS[stem]) for stem in SNUG_FASTENERS)
GENERAL_TORQUE_NOTE = (
    "UNSPECIFIED TORQUES (ITEMS "
    f"{', '.join(map(str, _SNUG_ITEMS[:-1]))} AND {_SNUG_ITEMS[-1]}): "
    "SNUG BY HAND WITH A STANDARD-LENGTH HEX KEY OR WRENCH; NO EXTENSION."
)
# Keep sheets 7–8 at the normal note size and paragraph spacing. The BOM owns
# the shim SKU/thickness buy list; P1 cites it rather than printing it twice.
ASSEMBLY_STEPS = (
    "1. COMPLETE RAIL PREPARATION PER BASE-BAR PLAN AND RAIL SHEET 2. "
    f"FIT EACH {guide_rail.STYLE} RAIL {_item(RAIL)} WITH "
    f"{trammel.RAIL_HOLE_COUNT} {_RAIL_SCREW} {_item(RAIL_SCREW)}, NEAR ENDS FLUSH. "
    f"BASE BAR 1 {_item(BASE_BAR_1)}: AS DRAWN, RAIL 1. BASE BAR 2 "
    f"{_item(BASE_BAR_2)}: TURNED OVER, RAIL 2; PLAN MIRROR OF BAR 1. "
    f"AT EACH KP08 STATION ON BAR 1, FIT AN END BRACKET {_item(END_BRACKET)} "
    f"WITH {len(leadscrew.BAR_SCREW_LATERALS)} {_BAR_SCREW} {_item(PILLOW_BLOCK_SCREW)} "
    f"FROM BELOW, NO WASHERS, {_torque(leadscrew.BAR_SCREW_TORQUE_NM)}.",
    "2. SET BARS ON THE TABLE, NEAR ENDS TOWARD THE SPINDLE. PER BAR, FIT "
    f"2 UNCUT {fasteners.HOLD_DOWN_STUD_THREAD} STUDS {_item(HOLD_DOWN_STUD)} "
    f"IN OUTER T-SLOT T-NUTS {_item(T_NUT)}, FLANGE NUTS {_item(FLANGE_NUT)} FINGER-TIGHT. "
    "KEEP STUDS UNCUT UNTIL 13B/HD3; CUT TO BOM LENGTH "
    f"{_length(hold_down_stud.LENGTH, hold_down_stud.LENGTH_PLACES)} THERE. "
    "FOLLOW HD1 FOR UNCUT-STOCK OBSTRUCTIONS.",
    # Owner decisions on #2177: the kit's rails each arrive with two
    # carriages; the play check picks the pair the jig keeps, and a carriage
    # off a rail only ever rides the kit's plastic false rail (loading arbor).
    f"3. EACH RAIL ARRIVES WITH 2 GREASED {carriage.STYLE} CARRIAGES "
    f"{_item(CARRIAGE)}: ROCK ALL 4 SIDEWAYS UNDER AN INDICATOR; KEEP THE 2 "
    "TIGHTEST, ONE PER RAIL. A CARRIAGE LEAVES A RAIL ONLY ONTO A KIT FALSE RAIL. "
    "TRIM EACH RAIL TO ITS ACTUAL BAR, FLUSH BOTH ENDS; CHECK RETAINED WALLS. "
    "TRANSFER ITS HOLES TO THAT BAR PER THE BASE-BAR PROCESS PLAN; "
    "KEEP EACH PAIR IDENTIFIED. ALL EIGHT SCREWS MUST ENTER FREELY BY HAND "
    "WITHOUT MOVING THE RAIL. CLEAN ALL CUTTING GRIT BEFORE RELOADING.",
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
    f"{_length(pivot_block.REACH_MIN, 3)}-{_length(pivot_block.REACH_MAX, 3)} "
    "OF THE CARRIAGE'S M4 X 5 AND NEVER BOTTOMS. "
    f"TEMPORARILY SEAT THE SHOULDER SCREWS {_item(PIVOT_SCREW)} FOR INDICATING.",
    "6. ZERO DRO X/Y AT THE SPINDLE ORIGIN (SHEET 1). AT EACH ALIGNMENT-TABLE "
    "X/Y, CENTRE THE SHOULDER UNDER A SPINDLE INDICATOR: SLIDE THE CARRIAGE "
    "IN X, TAP THE BAR IN Y. TIGHTEN HOLD-DOWN NUTS; RECHECK EVERY STATION. "
    "SET EACH SWEEP LIMIT (SHEET 1) THE SAME WAY, CENTRING IN X ONLY. "
    "WITNESS-MARK EACH BAR AT ITS CARRIAGE'S SPINDLE-END FACE, I OR O BY PASS.",
    # Receipt foot bounds protect the whole upper reach from the opposed
    # hand-tap cut and retain 1.5D full engagement at the thickest foot.
    # The foot remains UNVERIFIED (#2184).
    f"7. CHECK EACH KP08 {_item(PILLOW_BLOCK)} FOOT IS "
    f"{_bound(end_bracket.KP08_FOOT_THICK_MIN, 3, up=True)} TO "
    f"{_bound(end_bracket.KP08_FOOT_THICK_MAX, 3, up=False)} THICK AT ITS 2 HOLES. "
    f"FIT EACH KP08 WITH 2 {_KP08_SCREW} {_item(PILLOW_BLOCK_SCREW)}, LOOSE.",
    # TL-00 review (farm 20261104T210601055Z, blocker): one linear order,
    # every cross-reference one way: F1A, 8A, F1B, F2, 8B, F3.
    # The Tr8 screw's stub and the hub's gap close its metric cut along the
    # KP08 stations: they print exact millimetres (owner ruling 4, 2026-11-01).
    f"8A. COMPLETE F1A (SHEET 8). THREAD THE LEADSCREW {_item(LEADSCREW)}, "
    "OILED WITH ISO VG 32, THROUGH THE KP08S, THE LUG CLEARANCE AND THE "
    f"FEED NUT {_item(FEED_NUT)}, {leadscrew.NEAR_STUB:.1f} MM PAST THE NEAR "
    "BLOCK. COMPLETE F1B-F2.",
    f"8B. PUSH THE HANDWHEEL {_item(HANDWHEEL)} ON, HUB "
    f"{leadscrew.HUB_GAP:.1f} MM OFF THE FAR BLOCK; "
    "TIGHTEN ITS AND THE KP08 SET SCREWS ON THE FLATS WITH LOCTITE 222 "
    "THREADLOCKER. COMPLETE F3.",
    "9. REMOVE THE TEMPORARY SHOULDER SCREWS. FIT THE SPACERS AND CARRIER "
    "ON A1/B1; SELECT SHIMS PER P1 AND COMPLETE P1-P3 (SHEET 8). RECORD HD1 "
    "H THROUGH THE COMPLETE INNER-PASS HAND SWEEP, MARK TO MARK (STEP 6), "
    "USING THE HANDWHEEL.",
    # The carrier stays on its A1/B1 seats from step 9 to 13A: its HUB tap is
    # made in place on the running jig and nothing removes it before 13A. The
    # HUB is set from the spindle origin (the apex) by the printed offset, so
    # the pin spacing moves it with the cut.
    f"10. KEEP CARRIER {_item(CARRIER)} ON A1/B1 THROUGH STEP 11. "
    "FEED TO SYMMETRIC POSITION; MOVE TABLE UNTIL THE DRO READS "
    f"{_HUB_DRO}. RECORD IT: EVERY STRAP'S HUB HOLE IS DRILLED AND REAMED "
    "THERE (O5). SPINDLE-GUIDED, SPOT, TAP-DRILL AND TAP THE CARRIER'S HUB "
    f"{carrier.HUB_THREAD} THRU THERE, NO COUNTERBORE. CL AND CR ARE THE "
    "CARRIER DRAWING'S ORDINARY TAPS; DO NOT REDRILL.",
    f"11. AT THE STEP 10 SYMMETRIC POSITION, STAND THE {QUANTITIES[STOP_PIN]} "
    f"STOP PINS {_item(STOP_PIN)} CHAMFERED END DOWN IN THE RISER'S STOP HOLES "
    f"(DRILLED FIRST, {carrier.RISER_NUMBER}); SET THE RISER ON THE CARRIER SO "
    f"THE PIN AXES READ DRO {_STOP_DRO} AND CLAMP IT. ONLY THEN SPOT "
    f"{len(riser.SCREW_HOLES) + len(STRAP_CLAMP_ROLES)} THROUGH-HOLE CENTRES "
    f"FROM BELOW. FINISH TO {carrier.RISER_NUMBER}; FIT WITH "
    f"{len(riser.SCREW_HOLES)} {_RISER_SCREW}S {_item(RISER_SCREW)}. "
    "KEEP BOTH STOP PINS LOOSE IN THEIR HOLES. OMIT THE TOP-HAT WASHER AND "
    "THE CL, CR AND HUB SCREWS UNTIL O4.",
    f"12. FIT FEED LEVER WITH 2 {_LEVER_SCREW} {_item(LEVER_SCREW)} "
    f"AND WEDGE-LOCK PAIRS {_item(LEVER_LOCK_WASHER)}, {_LEVER_TORQUE}; "
    f"GRIP TOWARD OPERATOR. THE CL, CR AND HUB {_STRAP_CLAMPS} ARE FITTED "
    "AT EACH WORK LOADING (O4-O6). "
    "HANDWHEEL FEED; NEVER FORCE LEVER AGAINST ENGAGED NUT.",
    f"13A. FIT A2/B2 PER O1; COMPLETE HD1 (SHEET {OPERATION_SHEET_NUMBER}).",
    # Review jig-asm r1/r2 (2026-11-02): the carrier stays off from 13B
    # through HD3, so 13B states only O1's removal half and 13C its refit.
    "13B. ISOLATE THE SPINDLE, SUPPORT THE CARRIER, REMOVE BOTH SHOULDER "
    "SCREWS AND LIFT IT OFF; KEEP IT OFF AND REWORK STUDS PER HD2-HD3.",
    "13C. MOVE CARRIAGES TO ALIGN A2/B2 OVER BLOCK COUNTERBORES; "
    "LOWER THE CARRIER ONTO THEM, REFIT BOTH SCREWS PER P2 AND CHECK P1-P3; "
    "DO HD4 AND THE CHECKS.",
    "13D. RETURN TO A1/B1 PER O1; REPEAT HD4 AND THE CHECKS.",
)
ASSEMBLY_CHECKS = (
    "CHECK: ALIGNMENT READINGS WITHIN "
    f"±{_length(ALIGNMENT_BAND, ALIGNMENT_PLACES)} OF TARGET.",
    "CHECK: HANDWHEEL FEEDS BOTH FULL PASSES WITHOUT BINDING; CARRIAGES "
    "STAY ON RAILS; MOVING PARTS CLEAR STUDS, NUTS AND COLUMN COVER.",
    "CHECK: SHOULDER ENDS SEATED, SCREWS TORQUED; BOTH HEADS HAVE P1 "
    "RUNNING GAP WITHOUT CLAMPING CARRIER.",
    # Carriage play moves the cut radius about 1:1; this replaces preload (#2177).
    "CHECK: INDICATE SHOULDER-SCREW HEAD; ROCK CARRIER SIDEWAYS TO RAIL BY "
    f"HAND: {trammel.CARRIAGE_PLAY_TIR_MAX:.2f} MM TIR MAX.",
)
PIVOT_FIT_STEPS = (
    f"P1. SET A LOOSE SPACER {_item(PIVOT_SPACER)} ON EACH BLOCK, NO SHIMS. "
    "LOWER CARRIER ON CHOSEN HOLE PAIR; SEAT BOTH SHOULDER SCREWS. MEASURE "
    "EACH HEAD-TO-CARRIER GAP; LIFT CARRIER. UNDER EACH SPACER FIT SHIMS "
    f"{_item(PIVOT_SHIM)} FROM THE BUY LIST UNDER THE BOM TO GIVE "
    f"{_length(PIVOT_RUNNING_GAP[0], 3)}-{_length(PIVOT_RUNNING_GAP[1], 3)} GAP THROUGH FREE SWING. "
    f"NOMINAL {pivot_shim.PER_SUPPORT} X {_length(pivot_shim.THICKNESS, 3)}; "
    f"MAX PACK {_length(PIVOT_FIT_PACK_MAX, 3)} ({PIVOT_FIT_SHIMS_MAX} SHIMS). "
    "REMEASURE. SAME SHIMS FOR BOTH HOLE PAIRS; NONE BETWEEN SPACER AND CARRIER.",
    f"P2. CLEAN {pivot_screw.THREAD} THREADS; APPLY LOCTITE 222. LIGHTLY GREASE "
    "SHOULDERS AND SPACER FACES WITH NLGI 2 LITHIUM GREASE; KEEP THREADS "
    "GREASE-FREE. SEAT SHOULDERS IN COUNTERBORES; TORQUE "
    f"{_torque(PIVOT_SCREW_TORQUE_NM)}. HEADS MUST NOT CLAMP CARRIER.",
    "P3. HANDWHEEL-SWEEP FITTED PAIR'S FULL PASS: CHECK BOTH SUPPORT GAPS, "
    "FREE ROTATION AND POSITIVE LIFT CAPTURE UNDER BOTH HEADS. REFIT A FAILED "
    "STACK; NEVER LOOSEN A SEATED SCREW FOR CLEARANCE.",
)
# Sheet 2, under the BOM: what item 7's QTY counts and the fitting stock to
# buy, and the owner's description note for the kit rails and carriages
# (#2177, 2026-11-04), in three lines; the rail and carriage registry
# records and inventory entries carry it word for word. No line is longer
# than the shim buy list's 75 characters, the widest the field under the BOM
# already prints.
BOM_NOTE = "\n".join((
    f"ITEM {ITEM_NUMBERS[PIVOT_SHIM]}: SHIM FITTING STOCK, SELECTED PER P1.",
    f"BOM QTY. {pivot_shim.QUANTITY} IS THE NOMINAL PACK, {pivot_shim.PER_SUPPORT} X "
    f"{_length(pivot_shim.THICKNESS, 3)} A SUPPORT.",
    "BUY, COVERING THE WORST CASE AT BOTH SUPPORTS:",
    ", ".join(
        f"{sku} ({_length(thickness, 3)}) X{count}"
        for sku, (thickness, count) in PIVOT_SHIM_BUY.items()
    ) + ".",
    f"ITEMS {ITEM_NUMBERS[RAIL]}-{ITEM_NUMBERS[CARRIAGE]}: HIWIN-STYLE "
    f"{guide_rail.STYLE} RAIL / {carriage.STYLE} CARRIAGE, A MATCHED KIT,",
    "NUIBBYED-BRANDED, NOT GENUINE HIWIN. Z0 PRELOAD AND C ACCURACY NOT",
    "REQUIRED; ACCEPT BY FIT-UP PLAY CHECK "
    f"({trammel.CARRIAGE_PLAY_TIR_MAX:.2f} MM TIR MAX AT THE PIVOT).",
))
if int(ITEM_NUMBERS[CARRIAGE]) != int(ITEM_NUMBERS[RAIL]) + 1:
    raise AssertionError("the BOM note's kit items are no longer consecutive")
# F2's transfer drills, by the names the fitter asks for; TL-32's spec owns
# their sizes (TRANSFER_SPOT_DIA, NUT_TAP_DRILL).
_SPOT_DRILL = "#29"
_TAP_DRILL = "#43"
if abs(NUMBER_DRILL_MM[_SPOT_DRILL] - feed_block.TRANSFER_SPOT_DIA) > 1e-3:
    raise AssertionError("F2's spot drill is not TL-32's transfer spot")
if NUMBER_DRILL_MM[_TAP_DRILL] != feed_block.NUT_TAP_DRILL:
    raise AssertionError("F2's tap drill is not TL-32's nut tap drill")
# F1A-F3 (owner ruling 2026-11-04, option B; Main's tightening procedure),
# in one linear order with step 8: F1A measures and prepares the nut before
# step 8A threads it, F1B aligns the KP08s and seats and clocks the nut, F2
# transfers its taps and screws it down with the leadscrew in it, so it takes
# its centre from the screw, not from the countersinks; step 8B fits the
# handwheel and F3 checks the travel (TL-00 review, farm
# 20261104T210601055Z). The receipt limits, the facing, the countersinks and
# the faced length are native dimensions on the leadscrew kit drawing's FeedNut
# REWORK sheet (feed_nut.REWORK_SHEET_REFERENCE; Codjiflo P2, 4475311251 on
# #2187): F1A and F2 cite that sheet and type none of its limits. F2 opens a
# binding nut's countersinks within the sheet's CskDia band (4475311242), so
# the opened nut is a conforming one and F3 needs no concession for it.
# F2 calipers the nut screws' heads before they go in (owner ruling
# 2026-11-04, #2177 option 3): a head over feed_nut.SCREW_HEAD_DIA_MAX is
# rejected and replaced, and the nut body is never cut (TL-32 spec,
# HEAD_TO_BODY_*).
# F1B sets all four of the nut's holes within TL-32's native tap clocking
# (NutClock, printed 4X on its VIEW D) and cites it by view, typing no angle
# (Codjiflo 4477879822 and 4477879826 on #2187): the supplier gives the holes
# no angular stations, so one clocked hole bounds no other, and TL-32's lug
# walls charge each tap anywhere in that band.
_HEAD_LIMIT = _bound(feed_nut.SCREW_HEAD_DIA_MAX, 3, up=False)
_HEAD_SHARP_MAX = _length(feed_block.HEAD_DIA_SHARP_MAX, 3)
FEED_FIT_STEPS = (
    f"F1A. BEFORE STEP 8A, MEASURE THE FEED NUT {_item(FEED_NUT)} TO THE "
    f"RECEIPT LIMITS ON {feed_nut.REWORK_SHEET_REFERENCE}; REJECT ONE OUTSIDE "
    "THEM. FACE AND COUNTERSINK IT PER THAT SHEET; REJECT ONE OUTSIDE ITS "
    "FACED LENGTH.",
    "F1B. AFTER STEP 8A, NUT SEAT FACE "
    "TOWARD THE LUG, MOVE THE FEED CARRIAGE TO EACH TRAVEL END IN TURN AND "
    "ALIGN EACH KP08 SO THE SCREW RUNS CENTRED IN THE LUG'S "
    f"Ø{_length(feed_block.SCREW_CLEARANCE_DIA, feed_block.NUT_PATTERN_PLACES)} "
    f"CLEARANCE WITHOUT FORCING IT; TIGHTEN THE KP08 SCREWS TO {_KP08_TORQUE}, "
    f"THE SCREW STILL {leadscrew.NEAR_STUB:.1f} MM PAST THE NEAR BLOCK. "
    f"TURN THE NUT UNTIL ALL {feed_nut.SCREW_COUNT} HOLES CENTRE WITHIN THE TAP "
    f"CLOCKING ON {feed_block.NUT_CLOCK_REFERENCE}, EACH CHECKED WITH A MITRE "
    "SQUARE ON THE LUG'S TOP EDGE THROUGH THE SCREW AXIS; REJECT A NUT WHOSE "
    f"{feed_nut.SCREW_COUNT} HOLES CANNOT ALL BE SET WITHIN IT. HOLD IT "
    "THERE AND TURN THE SCREW, NEVER SLIDE IT, UNTIL THE NUT SEATS FLAT ON THE "
    "LUG FACE; CLAMP IT.",
    f"F2. SPOT THE {feed_nut.SCREW_COUNT} TAPS THROUGH THE NUT'S HOLES WITH A "
    f"{_SPOT_DRILL} DRILL, THEN DRILL {_TAP_DRILL} AND TAP "
    f"{feed_nut.SCREW_THREAD} THRU. CALIPER {feed_nut.SCREW_COUNT} FLAT HEADS "
    f"{_item(RISER_SCREW)}: HEAD Ø{_HEAD_LIMIT} MAX, AS B18.6.3'S MAX "
    f"{_HEAD_SHARP_MAX} REACHES THE NUT BODY; REJECT ONE OVER AND FIT A "
    "REPLACEMENT THAT PASSES; NEVER MACHINE THE NUT BODY. WITH THE "
    "SCREW A FEW TURNS IN THE NUT, TIGHTEN THEM CROSSWISE IN 2 STAGES TO "
    f"{_NUT_TORQUE}. IF THE SCREW BINDS, LOOSEN, RE-CENTRE AND RETIGHTEN; IF IT "
    "STILL BINDS, OPEN THE COUNTERSINKS PER "
    f"{feed_nut.REWORK_SHEET_REFERENCE}. GO TO STEP 8B.",
    # End to end is the full feed-carriage travel. This three-line instruction
    # preserves the installed checks without overrunning sheet 8's source view.
    "F3. AFTER STEP 8B, WITH THE HANDWHEEL AND ALL SET SCREWS TIGHT, "
    "FEED END TO END BY HANDWHEEL: NO BINDING, NUT OR LUG CONTACT WITH A "
    "KP08, AND NO MOVING PART CONTACT. REPEAT F1B-F2 IF IT BINDS.",
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
    "COMPLETE PASSES, MARK TO MARK: INNER AT STEP 9, OUTER AT STEP 13A; N, SEATED FLANGE "
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
    "RETIGHTEN AND READ EVERY STATION; THEN RENEW THE SWEEP-LIMIT MARKS THE "
    "SAME WAY, CROSSING OUT ANY OLD MARK THAT MOVED. REMOVE THE TEMPORARY SCREWS.",
    "HD4. WITH THE CARRIER AND BOTH SCREWS FITTED PER O1, HAND-SWEEP ITS "
    "COMPLETE PASS TO THE HD3 MARKS: "
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
    f"O3. SELF-CUT THE 6061 RISER WITH THE {trammel.RISER_CUTTER_IN} CUTTER "
    "BEFORE LOADING WORK, THE TOP-HAT WASHER AND CL, CR AND HUB SCREWS OUT. "
    "KEEP ALL FOUR RISER SCREWS AND BOTH STOP PINS FITTED. THE FINISHED BAND "
    f"CLEARS THE {trammel.PART_CUTTER_IN} STRAP CUTTER BY "
    f"{(trammel.RISER_CUTTER_DIA - trammel.PART_CUTTER_DIA) / 2.0:.2f} MM PER "
    "SIDE; THE STRAP CUTTER DOES NOT CUT THE RISER.",
    f"O4. EACH STRAP BLANK ARRIVES FACED, LAID OUT AND BANDSAWN PER {PROCESS_PLAN} "
    "S0-S1, WITH NO HUB HOLE; ITS LOOSE CL/CR HOLES ARE TRANSFERRED AND "
    "DRILLED OFF-JIG PER S2 OP20. "
    "SEAT IT FLAT ON THE RISER, RAW EDGE TOWARD -Y AGAINST BOTH STOP PINS, "
    "ALONG THE STRAP TO ITS END MARK; FIT THE CL AND CR "
    f"{_STRAP_CLAMPS} DIRECTLY ON THE WORK AND TIGHTEN.",
    f"O5. PER {PROCESS_PLAN} S2 OP30-OP40, MOVE TABLE TO THE STEP 10 DRO POSITION "
    f"({_HUB_DRO}) AND, SPINDLE-GUIDED, DRILL AND REAM THE STRAP'S HUB HOLE "
    "THRU INTO THE RISER'S RELIEF. NEVER REDRILL OR RETAP THE CARRIER.",
    f"O6. SEAT THE TOP-HAT WASHER {_item(HUB_WASHER)} SPIGOT DOWN IN THE REAMED "
    "HOLE, FLANGE FLAT ON THE STRAP. FIT THE HUB "
    f"{_STRAP_CLAMPS} THROUGH IT INTO THE CARRIER'S HUB TAP; TORQUE "
    f"{_torque(holding.HUB_TORQUE_NM)}; THE HEAD NEED NOT BEAR FULLY ON THE FLANGE. CUT "
    f"PER {PROCESS_PLAN} S3 OP10-OP20, RETAINING ALL THREE CLAMPS THROUGH BOTH "
    "PASSES. EACH START IS AN EDGE CUT WITH AIR BESIDE THE CUTTER, NEVER A "
    "FULL-WIDTH SLOT OR PLUNGE.",
)
# The fixture's highest point over the strap: the uncut stock stop pins at
# full length and tilt (holding.TOOLING_TOP_Z_MAX), above every clamp head.
TOOLING_TOP_Z_MAX = holding.TOOLING_TOP_Z_MAX
# The carrier-seated, tilted stock pin (holding.STOP_PIN_HEIGHT_MAX: L_MAX
# plus D_MAX x the hole-play slope), not the bare stock length.
_STOP_PIN_TOP_MAX = trammel.CARRIER_TOP_Z + holding.STOP_PIN_HEIGHT_MAX
_HUB_HEAD_TOP_MAX = trammel.CARRIER_TOP_Z + holding.HUB_GRIP_LIMITS[1] + rail_screw.DIMS.head_h
if not TOOLING_TOP_Z_MAX >= _STOP_PIN_TOP_MAX > max(_HUB_HEAD_TOP_MAX, *holding.CLAMP_TOP_Z.values()):
    raise AssertionError("the stop pins no longer stand tallest over the strap")
if holding.CLAMP_TOP_Z["CL"] != holding.CLAMP_TOP_Z["CR"]:
    raise AssertionError("the CL and CR heads no longer stand at one height")
CAPTURE_CHECKS = (
    "TOOLING CLEARANCE: BEFORE USE, WITH THE SPINDLE ISOLATED, CHECK THE "
    "ACTUAL SPINDLE, CUTTER, NON-CUTTING TOOL AND HOLDER AGAINST THE "
    "FIXTURE THROUGH BOTH PASSES AND THE ENTIRE USED Z RANGE, INCLUDING "
    "BREAKTHROUGH AND RETRACTION. INCLUDE BOTH SHOULDER-SCREW HEADS, THE "
    "CL, CR AND HUB SCREW HEADS, THE TOP-HAT WASHER AND BOTH STOP PINS AT "
    "FULL HEIGHT. "
    "VERIFY VISIBLE OR MEASURED CLEARANCE AT EVERY CLOSEST APPROACH: "
    "NO SPINDLE/TOOL/HOLDER CONTACT WITH THE FIXTURE.",
    "KEEP THE REPEATED STEP 6 ACTUAL SPINDLE-AXIS REGISTER; REINDICATE AFTER "
    "XY CHANGES. RECHECK CLEARANCE AFTER TOOL/DEPTH/SETUP CHANGES.",
    f"REFERENCE TABLE HEIGHTS: WORK {_length(PART_TOP_Z, 3)}; SHOULDER-SCREW HEADS "
    f"{_length(PIVOT_HEAD_TOP_Z, 3)}, NOMINAL. "
    "SET CUTTING DEPTH FROM THE ACTUAL SEATED WORK, NOT THESE REFERENCES.",
    f"CLAMP HEADS FROM TABLE: CL/CR {_length(holding.CLAMP_TOP_Z['CL'], 3)}, "
    f"HUB {_length(holding.CLAMP_TOP_Z['hub'], 3)}, NOMINAL; THE STOP PIN TOPS "
    f"STAND TALLEST, FIXTURE TOP {_bound(TOOLING_TOP_Z_MAX, 3, up=True)} MAX. "
    f"TOP-HAT WASHER {holding.WASHER_CLEARANCE_MIN:.1f} MM MIN TO BOTH CUTTER "
    "FLANKS. CHECK WITH THE WASHER AND CLAMPS FITTED, NOT AS FOR THE RISER "
    "SELF-CUT.",
    "ACCEPTANCE: THE CARRIAGE/RAIL AND TABLE ANCHORS PASS THE ASSEMBLY CHECKS "
    "AFTER FINAL TIGHTENING (EVERY STEP 6 READING WITHIN "
    f"±{_length(ALIGNMENT_BAND, ALIGNMENT_PLACES)}; "
    "FREE SWEEP WITH BOTH CARRIAGES ON THEIR RAILS) AND HD4 AT EVERY STUD.",
)

# --- Assembly extent at the modelled pose (sheet layout reads it) -----------------


def _bar_corners(rail: int) -> list[tuple[float, float]]:
    """A bar's plan corners: the operator- and column-side edges (the rail
    off the centreline since the 2026-10-17 widening) at both ends. The bar
    and its datum-trimmed rail share both end stations."""
    near, far = trammel.RAIL_NEAR_S, trammel.BASE_BAR_FAR_S
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
    nut_r = feed_nut.FLANGE_DIA_MAX / 2.0
    # The fitted nut's flange round its axis (+Y), seat face to faced end.
    nut_box = ((-nut_r, nut_r), (0.0, feed_nut.LENGTH_MAX), (-nut_r, nut_r))
    bar_box = ((0.0, base_bar.BAR_LENGTH), (base_bar.LOW_SIDE_Y, base_bar.HIGH_SIDE_Y), (0.0, base_bar.BAR_THICK))
    boxes = {
        BASE_BAR_1: bar_box,
        BASE_BAR_2: bar_box,
        RAIL: ((0.0, guide_rail.LENGTH), (-guide_rail.WIDTH / 2.0, guide_rail.WIDTH / 2.0), (0.0, guide_rail.HEIGHT)),
        CARRIAGE: ((-carriage.LENGTH / 2.0 - carriage.NIPPLE_PROUD, carriage.LENGTH / 2.0 + carriage.PLUG_PROUD), (-carriage.WIDTH / 2.0, carriage.WIDTH / 2.0), (carriage.UNDERSIDE_Z, carriage.MOUNTING_FACE_Z)),
        PIVOT_BLOCK: ((pivot_block.BLOCK_X0, pivot_block.BLOCK_X1), (-pivot_block.BLOCK_WIDTH / 2.0, pivot_block.BLOCK_WIDTH / 2.0), (0.0, pivot_block.BLOCK_HEIGHT)),
        FEED_BLOCK: ((pivot_block.BLOCK_X0, pivot_block.BLOCK_X1), (feed_block.LUG_Y0, pivot_block.BLOCK_WIDTH / 2.0), (0.0, pivot_block.BLOCK_HEIGHT)),
        PIVOT_SCREW: ((-pivot_screw.HEAD_DIA / 2.0, pivot_screw.HEAD_DIA / 2.0), (-pivot_screw.HEAD_DIA / 2.0, pivot_screw.HEAD_DIA / 2.0), (-pivot_screw.THREAD_LENGTH, pivot_screw.SHOULDER_LENGTH + pivot_screw.HEAD_HEIGHT)),
        PIVOT_SPACER: ((-pivot_spacer.OD / 2.0, pivot_spacer.OD / 2.0), (-pivot_spacer.OD / 2.0, pivot_spacer.OD / 2.0), (0.0, pivot_spacer.LENGTH)),
        PIVOT_SHIM: ((-pivot_shim.OD / 2.0, pivot_shim.OD / 2.0), (-pivot_shim.OD / 2.0, pivot_shim.OD / 2.0), (0.0, pivot_shim.THICKNESS)),
        CARRIER: (carrier.OUTLINE_X, (-carrier.THICKNESS, 0.0), (-carrier.OUTLINE_Y[1], -carrier.OUTLINE_Y[0])),
        RISER: ((0.0, riser.BLANK_LENGTH), (0.0, riser.BLANK_WIDTH), (0.0, riser.THICKNESS)),
        # The top-hat washer: flange above its seat face, spigot below it.
        HUB_WASHER: ((-hub_washer.OD / 2.0, hub_washer.OD / 2.0), (-hub_washer.OD / 2.0, hub_washer.OD / 2.0), (-hub_washer.SPIGOT_LENGTH, hub_washer.THICK)),
        FEED_LEVER: ((0.0, feed_lever.LEVER_LENGTH), (0.0, feed_lever.LEVER_THICK), (-feed_lever.LEVER_WIDTH, 0.0)),
        # The supplier's maximum pin, tilted in its loose hole: the holding
        # proof's height and full top float about its nominal axis.
        STOP_PIN: _axis_y_box(
            riser.STOP_PIN_DIA_LIMITS[1] / 2.0 + holding.STOP_PIN_TOP_FLOAT_MAX,
            0.0,
            holding.STOP_PIN_HEIGHT_MAX,
        ),
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
        (RAIL_SCREW, rail_screw),
        (CARRIAGE_SCREW, carriage_screw),
        (PILLOW_BLOCK_SCREW, bracket_screw),
        (LEVER_SCREW, lever_screw),
    ):
        radius = max(screw.DIMS.head_dia, screw.DIMS.major_dia) / 2.0
        boxes[stem] = _axis_y_box(radius, -screw.DIMS.length, screw.DIMS.head_h)
    if set(boxes) != set(BOM_ORDER):
        raise ValueError("fixture envelope must cover every native BOM family")
    return boxes


def _component_label(stem: str, index: int) -> str:
    names = {
        BASE_BAR_1: "base bar 1", BASE_BAR_2: "base bar 2",
        RAIL: "rail", CARRIAGE: "carriage",
        PIVOT_BLOCK: "pivot block 2", FEED_BLOCK: "feed block",
        PIVOT_SCREW: "pivot screw", PIVOT_SPACER: "pivot spacer",
        PIVOT_SHIM: "pivot shim",
        CARRIER: "carrier", RISER: "riser", FEED_LEVER: "feed lever",
        HUB_WASHER: "HUB top-hat washer", STOP_PIN: "stop pin",
        FEED_NUT: "feed nut",
        LEADSCREW: "screw", HANDWHEEL: "handwheel",
        END_BRACKET: "end bracket", PILLOW_BLOCK: "pillow block",
        HOLD_DOWN_STUD: "hold-down stud", T_NUT: "T-nut", FLANGE_NUT: "flange nut",
        RAIL_SCREW: "rail screw",
        CARRIAGE_SCREW: "carriage screw",
        PILLOW_BLOCK_SCREW: "pillow block screw",
        RISER_SCREW: "riser screw",
        LEVER_SCREW: "lever screw",
        LEVER_LOCK_WASHER: "lever lock washer",
    }
    if stem == PILLOW_BLOCK_SCREW and index >= len(PILLOW_BLOCK_SCREW_PLACEMENTS):
        return f"bar screw {index - len(PILLOW_BLOCK_SCREW_PLACEMENTS) + 1}"
    if stem == RAIL_SCREW:
        for role, clamp in STRAP_CLAMP_SCREW_INDICES.items():
            if index == clamp:
                return f"{role} clamp screw"
    name = names[stem]
    return f"{name} {index + 1}" if QUANTITIES[stem] > 1 else name


def _motion_root(stem: str, index: int) -> tuple[str, int]:
    """The carriage or carrier an occurrence rides, or itself when fixed."""
    while stem in LOCKED_TO and LOCKED_TO[stem][index] is not None:
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
            if pass_name is not None and not is_moving(stem, index):
                continue
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
    """Least gap (mm) from the TL-VN-84 FeedNut and its four screws, swept
    along rail 1 over carriage 1's whole travel, to each occurrence they
    could meet.

    Stationary items (all but the leadscrew they thread) are boxed in rail 1's
    frame: conservative for the turned nut's flange (its box is the flange's
    square, turned 45°) and for the rest. The carrier branch rotates above
    them about machine Z, so its gap is the machine-Z one. The flange stays
    within the lug's face (``feed_block.NUT_Y``).
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

    riders = [
        rail_box(points)
        for stem, index, points in records.values()
        if stem == FEED_NUT or instance_name(stem, index) in NUT_SCREW_INSTANCES
    ]
    swept = (
        (min(b[0][0] for b in riders) + trammel.CARRIAGE_TRAVEL[0] - CARRIAGE_STATION,
         max(b[0][1] for b in riders) + trammel.CARRIAGE_TRAVEL[1] - CARRIAGE_STATION),
        (min(b[1][0] for b in riders), max(b[1][1] for b in riders)),
        (min(b[2][0] for b in riders), max(b[2][1] for b in riders)),
    )
    gaps = {}
    for label, (stem, index, points) in records.items():
        if is_moving(stem, index):
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
# Each stop pin stands in its riser stop hole and each strap clamp over its
# riser clearance (the riser's own model frame carried by its placement).
for (_origin, _rows), _hole in zip(
    (*STOP_PIN_PLACEMENTS, *STRAP_CLAMP_SCREW_PLACEMENTS),
    (*riser.STOP_PIN_HOLES, riser.CL_HOLE, riser.CR_HOLE, riser.HUB_HOLE),
    strict=True,
):
    if math.dist(_origin[:2], frame_point((RISER_ORIGIN, RISER_ROWS), (*_hole, 0.0))[:2]) > 1e-9:
        raise AssertionError("a stop pin or strap clamp is off its riser hole")


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
# rail 1 (the TL-28 bar screws come up through Bar1); the underside pick
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
    raise AssertionError("the rail holes or the TL-28 bar screws miss the bar")
if CARRIER_ORIGIN[2] != trammel.CARRIER_TOP_Z:
    raise AssertionError("the carrier's origin (its Top plane) is not its top face")
for _pass, _stops in trammel.END_STOPS.items():
    _ends = [
        carriage_stations(_pass, f * trammel.SWEEP[_pass])[SLIDE_RAIL] for f in (-1, 1)
    ]
    if max(abs(a - b) for a, b in zip(_ends, _stops)) > 1e-9:
        raise AssertionError(f"the {_pass} sweep's end poses are not its end stops")
