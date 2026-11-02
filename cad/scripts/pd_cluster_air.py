"""The disc cluster's two air stacks: collar to disc, and disc to platen.

The cluster's lengths print (``transgear_cluster_fit``; its end float is
shimmed at assembly, owner ruling 2026-11-01, #2124) and its air stacks use
the repository's air-stack method (machining-dfm.md, ``dt_tip_collar_air``
precedent): worst-case arithmetic over every source if both stacks clear;
otherwise, for both, the nominal air minus the arithmetic sum of the
in-service clearances (the parts can take them all up together) minus the
root sum of squares of the independent printed manufacturing and set
tolerances (the shim fit-up's window is one).  Every source is in exactly
one class; an unclassified source is refused.  The projections of one error
are summed into that one source.  The disc's end float and the hub's recess
stay worst case (``transgear_cluster_fit``).

Collar air: the MHA-PD-22 drive collar's rear face (seated on F) to the MHA-PD-06
disc's front face where they overlap, cluster, hub and disc forward and the
knob rearward (the floats taken up by that pose).  The governing point Q is
the disc's tip circle under the collar's rim.  A rigid tilt of an axis moves
Q by the tilt times Q's reach beyond the edge of the axial stop it pivots on
(the face cannot pass its stop); a face's own error about its axis moves Q by
its slope times Q's radius.  The collar's rim reaches over the disc only
toward the knob, so the knob's tilts lever from its own stop's edge.

Platen air: the disc's rear face to the MHA-PD-02 platen's front face, cluster
rearward on the rear bushing; its terms are the paper-drive assembly's
(``build_pd_paper_drive_assembly`` builds that stack with these classes).

Pure data; no SolidWorks.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import paper_drive_arm_registration as REGISTRATION
import pd_rack_pinion_spec as DISC
import pd_transgear_arm_plate_geometry as ARM_PLATE
import pd_transgear_disc_hub_spec as HUB
import pd_transgear_drive_collar_spec as COLLAR
import pd_transgear_feed_pinion_spec as SLEEVE
import pd_transgear_front_bushing_spec as FRONT_BUSHING
import pd_transgear_knob_shaft_spec as KNOB_SHAFT
import pd_transgear_knob_thrust_ring_spec as KNOB_RING
import pd_transgear_pin_spec as PIN
import transgear_cluster_fit as FIT
from _printed_tolerance import edge_break_chamfer_mm, printed_band_mm

COLLAR_AIR_MIN = COLLAR.COLLAR_DISC_AIR_MIN  # 0.10
PLATEN_AIR_MIN = 0.03  # R9-68

# --- classification ------------------------------------------------------------
# In-service clearances and motions: running fits, floats and the arm
# plate's accepted loaded-minus-snug seat movement (a service motion, not a
# made size: codjiflo P2 on 6228b6ead) can all be taken up together; they
# add arithmetically.
IN_SERVICE_CLEARANCES = frozenset(
    {
        "hub rock on the sleeve boss",
        "sleeve cocking on the pin",
        "front bushing and ring cocking on the pin",
        "knob journal tilt in the plate bore",
        "platen float at the near lock",
        "arm plate loaded-seat change",
    }
)
_LENGTHS = (
    FIT.PH,
    FIT.TR,
    FIT.FW,
    FIT.GS,
    FIT.RT,
    FIT.AT,
    FIT.OL,
    FIT.TL,
    FIT.SP,
    FIT.LHUB,
    FIT.LFB,
    FIT.LRB,
)
# Independent printed manufacturing and set tolerances: root sum of squares.
INDEPENDENT_TOLERANCES = frozenset(
    {
        *(label for label, _, _ in _LENGTHS),
        FIT.SHIM_WINDOW_LABEL,
        "sleeve step face perpendicularity",
        "hub spigot end perpendicularity",
        "hub flange rear face perpendicularity",
        "pin S projected axis zone",
        "knob K projected axis zone",
        "arm opposite-face parallelism",
        "MHA-PD-20 spacer length",
        "MHA-PD-07 support bar depth",
        "MHA-PD-02 platen thickness",
        "MHA-PD-06 disc thickness",
        "MHA-PD-20 spacer rear face perpendicularity",
        "MHA-PD-20 spacer front face perpendicularity",
        "MHA-PD-06 disc rear face parallelism",
    }
)
if IN_SERVICE_CLEARANCES & INDEPENDENT_TOLERANCES:
    raise AssertionError(
        "a cluster air source cannot be both a clearance and a tolerance"
    )


@dataclass(frozen=True)
class AirStack:
    """One air: its nominal and its closing sources (mm, each >= 0)."""

    name: str
    nominal_mm: float
    terms: dict[str, float]
    minimum_mm: float

    def __post_init__(self):
        unclassified = (
            self.terms.keys() - IN_SERVICE_CLEARANCES - INDEPENDENT_TOLERANCES
        )
        if unclassified:
            raise ValueError(
                f"{self.name} has an unclassified source: {sorted(unclassified)}"
            )
        if not all(math.isfinite(v) and v >= 0.0 for v in self.terms.values()):
            raise ValueError(f"{self.name} has an invalid closing term: {self.terms}")

    @property
    def clearances_mm(self) -> float:
        return sum(v for k, v in self.terms.items() if k in IN_SERVICE_CLEARANCES)

    @property
    def tolerance_sum_mm(self) -> float:
        return sum(v for k, v in self.terms.items() if k in INDEPENDENT_TOLERANCES)

    @property
    def tolerance_rss_mm(self) -> float:
        return math.hypot(
            *(v for k, v in self.terms.items() if k in INDEPENDENT_TOLERANCES)
        )

    @property
    def arithmetic_mm(self) -> float:
        return self.nominal_mm - self.clearances_mm - self.tolerance_sum_mm

    @property
    def statistical_mm(self) -> float:
        return self.nominal_mm - self.clearances_mm - self.tolerance_rss_mm

    def air_mm(self, method: str) -> float:
        return self.arithmetic_mm if method == "arithmetic" else self.statistical_mm


# --- the governing point and the stops' edges ------------------------------------
# The cluster's parts print inch, whose .010 edge break also covers the
# metric knob ring's 0.25.
EDGE_BREAK_MAX = edge_break_chamfer_mm(unit=PIN.UNIT)
DISC_TIP_R = DISC.OUTSIDE_DIA / 2.0
COLLAR_RIM_R = (COLLAR.OD + max(COLLAR.OD_BAND)) / 2.0  # 8.75
# Q: the disc's tip under the collar's rim (the rim reaches past the tips).
Q_FROM_DISC_AXIS = min(DISC_TIP_R, DISC.CENTRE_DISTANCE + COLLAR_RIM_R)
# The disc's forward stop, cluster forward: the hub's front face on the front
# bushing (recess 0) or the sleeve's nose on it with the spigot's end on the
# sleeve's step (recess > 0); every contact edge less the title block's
# break, the step's tooth tips excepted (never broken, HUB.SEAT_CONTACT_R).
# The disc's tilts pivot on the least of these edges.
HUB_FACE_STOP_R = (
    min(
        HUB.HUB_DIA - printed_band_mm(HUB.HUB_DIA_PLACES, unit=HUB.UNIT),
        FRONT_BUSHING.OD
        - printed_band_mm(FRONT_BUSHING.OD_PLACES, unit=FRONT_BUSHING.UNIT),
    )
    / 2.0
    - EDGE_BREAK_MAX
)
NOSE_STOP_R = (SLEEVE.BOSS_DIA + min(SLEEVE.BOSS_DIA_BAND)) / 2.0 - EDGE_BREAK_MAX
DISC_STOP_R = min(HUB.SEAT_CONTACT_R, HUB_FACE_STOP_R, NOSE_STOP_R)
# The bushing is loose on the pin and held by the MHA-PD-VN-61 ring, which
# bears only on the groove's load wall (codjiflo P2 on 69223db92): bushing
# and ring cock together on the pin, as far as the bushing's bore lets them,
# about the load wall's broken outer edge, the one fixed support.  That moves
# the disc's contact on the bushing forward by the cock times its reach
# beyond that edge; the disc's own tilts then pivot on its contact.
PIN_LOAD_WALL_R = PIN.DIA_MIN / 2.0 - EDGE_BREAK_MAX
FRONT_BUSHING_COCK = math.atan(
    FIT.BORE_DIAMETRAL_CLEARANCE[1]
    / (FRONT_BUSHING.LENGTH - FRONT_BUSHING.LENGTH_BAND - 2.0 * EDGE_BREAK_MAX)
)
FRONT_BUSHING_COCK_REACH = max(HUB_FACE_STOP_R, NOSE_STOP_R) - PIN_LOAD_WALL_R
# The knob's axial stop: the 15T's rear tooth ends (never broken) on the
# thrust ring (its O.D. edge broken), the ring on the plate's hub face.
KNOB_STOP_R = min(
    KNOB_SHAFT.OUTSIDE_DIA / 2.0,
    (KNOB_RING.OD - printed_band_mm(KNOB_RING.OD_PLACES)) / 2.0 - EDGE_BREAK_MAX,
)
DISC_TILT_LEVER = Q_FROM_DISC_AXIS - DISC_STOP_R
KNOB_TILT_LEVER = max(0.0, COLLAR_RIM_R - KNOB_STOP_R)

# --- angles (rad) ------------------------------------------------------------------
HUB_ROCK = HUB.ROCK_ANGLE_MAX  # boss clearance over the least engagement
# The sleeve's bore on the pin over its span less both edge breaks
# (paper_drive_geom.reducer_axis_tilt_maxima_rad's disc term).
SLEEVE_COCK = math.atan(
    SLEEVE.BORE_DIAMETRAL_CLEARANCE[1]
    / (SLEEVE.OVERALL_LENGTH - SLEEVE.OVERALL_LENGTH_BAND - 2.0 * EDGE_BREAK_MAX)
)
KNOB_JOURNAL_TILT = math.atan(
    (max(ARM_PLATE.BORE_DIA_LIMITS) - min(KNOB_SHAFT.JOURNAL_DIA_BAND))
    / REGISTRATION.KNOB_JOURNAL_CONTACT_SPAN_MIN_MM
)
S_ZONE_TILT = math.atan(
    REGISTRATION.AXIS_PROJECTED_ZONE_DIAMETER_MM / REGISTRATION.S_PROJECTED_HEIGHT_MM
)
K_ZONE_TILT = math.atan(
    REGISTRATION.AXIS_PROJECTED_ZONE_DIAMETER_MM / REGISTRATION.K_PROJECTED_HEIGHT_MM
)
STEP_SLOPE = (
    SLEEVE.STEP_FACE_PERPENDICULARITY / SLEEVE.STEP_FACE_PERPENDICULARITY_ZONE_DIA
)
SPIGOT_SLOPE = (
    HUB.SPIGOT_END_PERPENDICULARITY / HUB.SPIGOT_END_PERPENDICULARITY_ZONE_DIA
)
FLANGE_SLOPE = (
    HUB.FLANGE_FACE_PERPENDICULARITY / HUB.FLANGE_FACE_PERPENDICULARITY_ZONE_DIA
)
_SEAT_SPAN = REGISTRATION.ARM_SEAT_SPAN_MIN_MM


def collar_terms() -> dict[str, float]:
    """The collar air's closing sources at Q, one entry per physical source."""
    terms = {label: band for label, _, band in (term for term, _ in FIT.M_FWD_CHAIN)}
    terms.update(
        {
            "hub rock on the sleeve boss": HUB_ROCK * DISC_TILT_LEVER,
            "sleeve cocking on the pin": SLEEVE_COCK * DISC_TILT_LEVER,
            "front bushing and ring cocking on the pin": FRONT_BUSHING_COCK
            * FRONT_BUSHING_COCK_REACH,
            "knob journal tilt in the plate bore": KNOB_JOURNAL_TILT * KNOB_TILT_LEVER,
            "sleeve step face perpendicularity": STEP_SLOPE * Q_FROM_DISC_AXIS,
            "hub spigot end perpendicularity": SPIGOT_SLOPE * Q_FROM_DISC_AXIS,
            "hub flange rear face perpendicularity": FLANGE_SLOPE * Q_FROM_DISC_AXIS,
            "pin S projected axis zone": S_ZONE_TILT * DISC_TILT_LEVER,
            "knob K projected axis zone": K_ZONE_TILT * KNOB_TILT_LEVER,
            # The rear face under the pin's head and under the plate at K may
            # stand the whole zone apart, and the plate seated on it tilts.
            "arm opposite-face parallelism": REGISTRATION.ARM_OPPOSITE_FACE_PARALLELISM_MM
            * (1.0 + KNOB_TILT_LEVER / _SEAT_SPAN),
            # The plate's seat accepted loaded minus snug: the normal change at K
            # and the tilt it allows.
            "arm plate loaded-seat change": REGISTRATION.gear_plane_k_loaded_normal_change_bound_mm()
            + 2.0
            * REGISTRATION.ARM_PLATE_LOADED_NORMAL_CHANGE_MAX_MM
            / _SEAT_SPAN
            * KNOB_TILT_LEVER,
        }
    )
    return terms


COLLAR_AIR = AirStack(
    "MHA-PD-22 collar to MHA-PD-06 disc air",
    FIT.M_FWD_NOMINAL,
    collar_terms(),
    COLLAR_AIR_MIN,
)


def require_air(platen: AirStack) -> dict[str, float | str]:
    """Both airs by the governing method; raises if either closes under its MIN."""
    stacks = (COLLAR_AIR, platen)
    method = (
        "arithmetic"
        if all(s.arithmetic_mm >= s.minimum_mm for s in stacks)
        else "statistical"
    )
    for s in stacks:
        air = s.air_mm(method)
        if not math.isfinite(air) or air < s.minimum_mm - 1e-9:
            raise AssertionError(
                f"{s.name}: {method} air {air:.4f} under {s.minimum_mm} (nominal "
                f"{s.nominal_mm:.4f}, clearances {s.clearances_mm:.4f}, tolerances "
                f"sum {s.tolerance_sum_mm:.4f} / RSS {s.tolerance_rss_mm:.4f}): {s.terms}"
            )
    return {
        "method": method,
        "collar_air": COLLAR_AIR.air_mm(method),
        "platen_air": platen.air_mm(method),
        "collar_air_arithmetic": COLLAR_AIR.arithmetic_mm,
        "platen_air_arithmetic": platen.arithmetic_mm,
    }
