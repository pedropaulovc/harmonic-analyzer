r"""Magnifying lever -> bracket collar PRESS FIT: CONFIG-free geometry owner
used by ``build_mg_magnifying_lever`` (the rod and its press zone),
``build_mg_magnifying_bracket`` (the collar bore) and the offline tests.
Shared interference oracles restate pinned literals rather than importing it.

PURE DATA: no SolidWorks/COM, no drawing and NO ``_config`` imports.  Kept
SEPARATE from ``mg_magnifying_lever_geom`` on purpose: that module reads the
collar and clamp STATIONS from cad/config/machine/output.yaml, so a shared
contract importing it would drag output.yaml into every recipe closure that
only needs the fit (check:graph's pen-assembly closure must stay free of the
output config).  The stations stay there; the fit lives here, and the lever
geom asserts its configured collar window IS this zone, the rod's tip flush
with the collar's outer face.

p.46 "firmly affixed to the summing lever" (user ruling 2026-10-11; LIGHT PRESS
approved by Main; #1570 PRESS ONLY, no bond): the rod's last PRESS_ZONE_LENGTH
seats end-flush in the bracket collar. Its cylindrical COLLAR_ENGAGEMENT is a
LIGHT PRESS that holds the joint by itself: ``press_holding`` below, which
mg_magnifying_bracket_arm_check sets against the lever's load at the collar.
The R3 dome is not part of the banded cylindrical zone, but the partial
hemisphere still larger than the bore contributes press contact.
The rod is modelled at nominal diameter; the cylinder's stock-select/lap band is
a native (upper, lower) ``_fit_deviations`` band on MHA-MG-003. The collar bore
is a MATCHED fit (#1570 owner ruling): MHA-MG-001 prints a reference nominal
and PRESS_INTERFERENCE_LIMITS on the measured press zone, so the interference
is the bore's own band, independent of the rod's. The model bore is the
tightest corner on the nominal rod.
``_interference_contracts`` restates the print-worst triple
(PRESS_ZONE_DIA, COLLAR_BORE_DIA, COLLAR_ENGAGEMENT_MAX) as literals its test pins
to these names; the model's nominal engagement remains COLLAR_ENGAGEMENT.

The press is sized by the collar's strength, not by the fit class: ANSI FN2
caps the interference, and a free-axial (plane-stress) Lamé solution for the
solid brass rod in the thick 1018 steel collar must keep the collar bore's von
Mises stress under STRENGTH_UTILIZATION of its yield at the tightest corner.
The collar OD carries no native band: its two-place print inherits the title
block's .XX ±0.51 (COLLAR_OD_BAND). Strength and press force are therefore
evaluated at independently conservative print corners: the thinnest wall
(COLLAR_OD_MIN) for bore stress, the stiffest wall (COLLAR_OD_MAX) for contact
pressure and press-in force, each with the tightest interference. Total force
adds full-pressure dome axial normal force over its projected annulus to the
full-pressure friction over COLLAR_ENGAGEMENT_MAX (Lmax 7.2078194326718075),
including partial hemisphere contact. Maximum cylinder length uses the minimum
dome radius; maximum dome extension and projected area use the maximum radius
and minimum bore, independently conservative corners rather than one physical
rod. Stock may itself be Ø6.000, so no clearance outside the selected land is
assumed.
"""

from __future__ import annotations

import math

# --- rod stock (DIMENSIONS.md ch20; Ø6 photo-scaled, low) ---------------------
ROD_DIA = 6.0  # round brass rod, modelled at nominal end to end

# --- press zone (the rod's east end) and the collar bore it enters -----------
PRESS_ZONE_LENGTH = 10.0  # the rod's last 10 = the collar's length
PRESS_ZONE_LENGTH_BAND = (0.0, -0.05)  # tip to the start of the selected/lapped land
COLLAR_LENGTH = PRESS_ZONE_LENGTH  # end-flush collar, modelled at its maximum length
COLLAR_LENGTH_BAND = (0.0, -0.05)
PRESS_ZONE_DIA = ROD_DIA  # the model's rod, 6.000
PRESS_ZONE_DIA_BAND = (0.0, -0.006)  # (upper, lower): select or lap the stock
# (min, max) diametral interference the bore is finished to on the measured
# press zone (#1570): 0.007 so the loosest joint still grips after its surface
# peaks flatten (SMOOTHING below); 0.014 the collar-strength ceiling.
PRESS_INTERFERENCE_LIMITS = (0.007, 0.014)
COLLAR_BORE_DIA = 5.986  # the model: the tightest interference on the 6.000 rod
if abs(COLLAR_BORE_DIA - (PRESS_ZONE_DIA - PRESS_INTERFERENCE_LIMITS[1])) > 1e-12:
    raise AssertionError("the model bore is not the tightest matched corner")
# DIN 7190 smoothing: pressing flattens each surface's peaks, so the effective
# interference is the measured one less SMOOTHING_FACTOR * (Rz bore + Rz rod).
# 0.8 is DIN 7190:1988's factor, twice DIN 7190-1:2017's 0.4. Rz is taken as
# RZ_PER_RA x Ra. The bore prints Ra 0.8 (reamed or honed; _surface_finish
# GROUND). The rod's selected or lapped drawn-brass land is not printed and is
# taken at the same Ra 0.8 (drawn bright stock is that or finer).
COLLAR_BORE_RA_UM = 0.8
ROD_LAND_RA_UM = 0.8
RZ_PER_RA = 4.0
SMOOTHING_FACTOR = 0.8
SMOOTHING = SMOOTHING_FACTOR * RZ_PER_RA * (COLLAR_BORE_RA_UM + ROD_LAND_RA_UM) / 1000.0
# End-flush: the rod's east dome tip sits flush with the collar's outer face
# (mg_magnifying_lever_geom asserts its configured window ends there), so the
# rod's cylinder, which ends where that dome starts (ROD_DIA / 2 back from the
# tip), is gripped from the collar's inner face over this much STRAIGHT rod;
# the dome's shrinking diameter is not full-diameter cylindrical engagement.
COLLAR_ENGAGEMENT = PRESS_ZONE_LENGTH - ROD_DIA / 2.0


def _press_contact_envelope(rod_min: float, rod_max: float, bore_min: float) -> float:
    """Bound end-flush cylinder plus partial-hemisphere contact, in mm.

    The hemisphere radius follows the selected rod OD. Maximum cylinder
    length uses the longest collar and minimum radius; the dome stays wider
    than the bore for ``sqrt(radius_max**2 - bore_radius_min**2)`` past its
    tangent. Combining those radius corners is independently conservative,
    not the contact length of one physical rod. Full tight-corner pressure
    over this entire length bounds friction without integrating the taper.

    A candidate bore at or above the maximum rod OD has no dome contact.
    Keep its cylindrical envelope so the budget's slip guard can reject it,
    rather than failing while evaluating a negative square-root argument.
    """
    dome_radius_min = rod_min / 2.0
    dome_radius_max = rod_max / 2.0
    bore_radius_min = bore_min / 2.0
    dome_extension = (
        math.sqrt(dome_radius_max**2 - bore_radius_min**2)
        if bore_radius_min < dome_radius_max
        else 0.0
    )
    return COLLAR_LENGTH + COLLAR_LENGTH_BAND[0] - dome_radius_min + dome_extension


COLLAR_ENGAGEMENT_MAX = _press_contact_envelope(
    PRESS_ZONE_DIA + PRESS_ZONE_DIA_BAND[1],
    PRESS_ZONE_DIA + PRESS_ZONE_DIA_BAND[0],
    PRESS_ZONE_DIA + PRESS_ZONE_DIA_BAND[0] - PRESS_INTERFERENCE_LIMITS[1],
)
# ANSI B4.1 table 8, class FN2 (medium drive fit) for the rod's size range
# 0.12..0.24 in: 0.2 .. 1.0 thou of diametral interference. A CAP only: the
# collar's strength below binds well inside it.
MM_PER_IN = 25.4
_FN2_SIZE_RANGE_IN = (0.12, 0.24)
PRESS_INTERFERENCE_MAX_FN2 = 0.0010 * MM_PER_IN

# --- collar section and materials for the Lamé check (MPa, mm) ---------------
COLLAR_OD = 12.0  # the bracket's steel collar (build_mg_magnifying_bracket)
# CollarOd prints at two places with no native band, so the title block's
# inherited .XX ±0.51 governs it (upper, lower). Restated, not read from
# _config, to keep this module config-free; the tests pin it to the block.
COLLAR_OD_BAND = (0.51, -0.51)
COLLAR_OD_MIN = COLLAR_OD + COLLAR_OD_BAND[1]  # thinnest wall: bore stress corner
COLLAR_OD_MAX = COLLAR_OD + COLLAR_OD_BAND[0]  # stiffest wall: pressure corner
ROD_E_MPA = 97000.0  # brass rod, Young's modulus
ROD_POISSON = 0.34
COLLAR_E_MPA = 200000.0  # low-carbon steel (1018) collar, Young's modulus
COLLAR_POISSON = 0.29
COLLAR_YIELD_MPA = 370.0  # 1018 cold drawn, minimum tensile yield
STRENGTH_UTILIZATION = 0.9  # the share of collar yield the press may use
COLLAR_STRESS_LIMIT_MPA = STRENGTH_UTILIZATION * COLLAR_YIELD_MPA
PRESS_FRICTION = (0.10, 0.15)  # (low, high) press-in friction coefficient


def _collar_lame(interference: float, collar_od: float) -> tuple[float, float, float]:
    """Free-axial (plane-stress) Lamé, solid rod of diameter d in a collar of
    outer diameter D, diametral interference delta::

        p = delta / (d * ((1 - nu_rod) / E_rod + (k + nu_collar) / E_collar))
        k = (D² + d²) / (D² - d²)

    Returns the contact pressure ``p``, the bore hoop ``p * k`` and the bore's
    plane-stress von Mises stress of that hoop with radial ``-p`` (MPa)."""
    collar_section_ratio = (collar_od**2 + PRESS_ZONE_DIA**2) / (
        collar_od**2 - PRESS_ZONE_DIA**2
    )
    rod_compliance = (1.0 - ROD_POISSON) / ROD_E_MPA
    collar_compliance = (collar_section_ratio + COLLAR_POISSON) / COLLAR_E_MPA
    contact_pressure = interference / (
        PRESS_ZONE_DIA * (rod_compliance + collar_compliance)
    )
    collar_hoop = contact_pressure * collar_section_ratio
    collar_radial = -contact_pressure
    collar_von_mises = math.sqrt(
        collar_hoop**2 + collar_radial**2 - collar_hoop * collar_radial
    )
    return contact_pressure, collar_hoop, collar_von_mises


def press_fit_budget(
    *,
    press_zone_dia_band: tuple[float, float] = PRESS_ZONE_DIA_BAND,
    interference_limits: tuple[float, float] = PRESS_INTERFERENCE_LIMITS,
) -> dict[str, float]:
    """Worst-case diametral interference of the collar press (mm), the
    whole-contact envelope it acts over, and collar stress and press-in force
    at the TIGHT corner. The bore is matched to the measured rod, so
    ``interference_min`` / ``interference_max`` are ``interference_limits``
    themselves, on any rod in its band; ``interference_effective_min`` is the
    loosest corner after SMOOTHING. The keyword arguments default to the
    printed fit; a caller can evaluate a candidate fit without touching these
    constants.

    The collar OD's inherited .XX band moves stress and force in opposite
    directions, so each is read at its own print corner with the tightest
    interference; the two corners are independently conservative, not one
    part. A thinner wall raises the bore's hoop factor faster than it softens
    the contact: ``collar_hoop_mpa`` and ``collar_von_mises_mpa`` are at
    ``strength_outer_diameter_mm`` (COLLAR_OD_MIN), whose contact pressure is
    ``strength_contact_pressure_mpa``. A thicker wall is stiffer:
    ``contact_pressure_mpa`` is the MAXIMUM pressure, at
    ``force_outer_diameter_mm`` (COLLAR_OD_MAX), and both press forces use it.

    The contact envelope includes the cylinder and the partial hemisphere
    still larger than the bore. The longest collar and minimum dome radius
    maximize cylinder length; the maximum radius and minimum bore maximize
    dome extension. Combining those independent corners bounds every physical
    part, giving print-worst Lmax 7.2078194326718075 rather than one coupled
    corner's contact length. Stock OD can also be Ø6.000, so collar length
    outside the qualified land is not assumed clear; the explicit collar-length
    band bounds contact. ``mu * p * pi * d * L`` bounds friction over this
    envelope. Add the dome's axial normal-force bound, ``p * pi *
    (radius_max**2 - bore_radius_min**2)``, using its projected annulus and the
    same full maximum pressure, without taper-pressure integration. Both
    ``press_force_min_n`` and ``press_force_max_n`` are TOTAL force across
    PRESS_FRICTION, not a range across collar-OD corners. Nominal straight
    cylindrical engagement remains 7 mm. Candidate slip fits remain evaluable
    for ``check_press_fit_budget`` to reject; a bore at or above the largest
    rod has zero dome projected area."""
    rod_max = PRESS_ZONE_DIA + press_zone_dia_band[0]
    rod_min = PRESS_ZONE_DIA + press_zone_dia_band[1]
    interference_min, interference_max = interference_limits
    bore_min = rod_max - interference_max  # the smallest bore any rod is matched to
    engagement_max = _press_contact_envelope(rod_min, rod_max, bore_min)
    strength_pressure, collar_hoop, collar_von_mises = _collar_lame(
        interference_max, COLLAR_OD_MIN
    )
    force_pressure, _, _ = _collar_lame(interference_max, COLLAR_OD_MAX)
    seat_area = math.pi * PRESS_ZONE_DIA * engagement_max
    # Projected dome annulus bounds axial normal force at the same full pressure.
    # No-contact candidate fits keep zero dome area for the existing slip guard.
    dome_projected_area = (
        math.pi * ((rod_max / 2.0)**2 - (bore_min / 2.0)**2)
        if bore_min < rod_max
        else 0.0
    )
    dome_normal_force = force_pressure * dome_projected_area
    friction_low, friction_high = PRESS_FRICTION
    return {
        "interference_nominal": PRESS_ZONE_DIA - COLLAR_BORE_DIA,
        "interference_min": interference_min,
        "interference_effective_min": interference_min - SMOOTHING,
        "interference_max": interference_max,
        "engagement": engagement_max,
        "strength_outer_diameter_mm": COLLAR_OD_MIN,
        "strength_contact_pressure_mpa": strength_pressure,
        "collar_hoop_mpa": collar_hoop,
        "collar_von_mises_mpa": collar_von_mises,
        "force_outer_diameter_mm": COLLAR_OD_MAX,
        "contact_pressure_mpa": force_pressure,
        "press_force_min_n": friction_low * force_pressure * seat_area + dome_normal_force,
        "press_force_max_n": friction_high * force_pressure * seat_area + dome_normal_force,
    }


def check_press_fit_budget(budget: dict[str, float]) -> None:
    """Refuse a press that slips at its loosest corner after smoothing,
    exceeds the FN2 cap at its tightest, or loads the collar bore past
    COLLAR_STRESS_LIMIT_MPA at its thinnest-wall strength corner."""
    if budget["interference_effective_min"] <= 0.0:
        raise AssertionError(
            "the collar press must interfere at its loosest band corner after smoothing"
        )
    if budget["interference_max"] > PRESS_INTERFERENCE_MAX_FN2 + 1e-9:
        raise AssertionError("the collar press exceeds ANSI FN2 at its tightest band corner")
    if not budget["collar_von_mises_mpa"] < COLLAR_STRESS_LIMIT_MPA:
        raise AssertionError(
            "the tightest collar press loads the 1018 collar bore past "
            f"{STRENGTH_UTILIZATION:g} x its {COLLAR_YIELD_MPA:g} MPa yield"
        )


PRESS_FIT_BUDGET = press_fit_budget()
if not (
    _FN2_SIZE_RANGE_IN[0] * MM_PER_IN < PRESS_ZONE_DIA <= _FN2_SIZE_RANGE_IN[1] * MM_PER_IN
):
    raise AssertionError("PRESS_INTERFERENCE_MAX_FN2 is the 0.12..0.24 in row")
check_press_fit_budget(PRESS_FIT_BUDGET)
if COLLAR_ENGAGEMENT <= 0.0 or COLLAR_ENGAGEMENT >= PRESS_ZONE_LENGTH:
    raise AssertionError("the dome must start inside the collar, past its inner face")
if not 0.0 < COLLAR_ENGAGEMENT <= COLLAR_ENGAGEMENT_MAX < COLLAR_LENGTH:
    raise AssertionError("print-worst dome contact must remain inside the collar")

# Conservatively round the maximum-pressure, Lmax, high-friction PLUS dome-normal
# total force upward to one decimal kN for the shop instruction. The force reacts
# through a rod held near its end, never through the unsupported lever as a column.
PRESS_FORCE_MAX_KN = math.ceil(PRESS_FIT_BUDGET["press_force_max_n"] / 100.0) / 10.0
PRESS_INSTALLATION_NOTES = "\n".join(
    (
        "LIGHT PRESS COLLAR ONTO LEVER; HOLD ROD NEAR END.",
        f"LEVER END FLUSH WITH OUTER FACE; {PRESS_FORCE_MAX_KN:.1f} kN MAX AT TIGHT FIT.",
    )
)


def press_holding(axial_demand_n: float, torque_demand_nmm: float) -> dict[str, float]:
    """What the press alone holds at its LOOSEST corner (#1570).

    The smallest effective interference (``interference_effective_min``, after
    smoothing) in the thinnest collar wall (COLLAR_OD_MIN, the softest, lowest
    pressure) at low friction, over the SHORTEST straight cylinder: the
    shortest collar less the largest dome radius; the dome's contact is not
    counted. Axial hold is ``mu * p * pi * d * L``; torsional hold is that
    times ``d / 2``. The demands are the caller's (the lever's load at the
    collar). Returns each capacity and its ratio to its demand."""
    pressure, _, _ = _collar_lame(
        PRESS_FIT_BUDGET["interference_effective_min"], COLLAR_OD_MIN
    )
    length = _straight_length_min()
    axial = PRESS_FRICTION[0] * pressure * math.pi * PRESS_ZONE_DIA * length
    torque = axial * PRESS_ZONE_DIA / 2.0
    return {
        "contact_pressure_min_mpa": pressure,
        "length_min": length,
        "axial_hold_n": axial,
        "torque_hold_nmm": torque,
        "axial_margin": axial / axial_demand_n,
        "torque_margin": torque / torque_demand_nmm,
    }


def _straight_length_min() -> float:
    """The shortest straight cylinder in the collar: shortest collar less the
    largest dome radius."""
    return (
        COLLAR_LENGTH
        + COLLAR_LENGTH_BAND[1]
        - (PRESS_ZONE_DIA + PRESS_ZONE_DIA_BAND[0]) / 2.0
    )


def collar_edge_bending(moment_nmm: float) -> dict[str, float]:
    """The collar's bending couple on the rod (#1570): a moment about the rod's
    normal redistributes the press pressure linearly along the straight
    cylinder, adding ``6 M / (d L^2)`` at one collar edge and taking it off
    the other.

    ``opening_moment_loose_nmm`` is the moment that unloads an edge at the
    loosest effective corner, ``p d L^2 / 6``: under it the whole length
    still grips; past it that edge carries the couple in bearing, not
    friction. ``edge_von_mises_tight_mpa`` is the collar bore's Lamé von Mises
    at the tightest, thinnest-wall corner with the edge's added bearing:
    above yield it is a local, self-limiting edge yield (owner ruling b); the
    uniform press stays under COLLAR_STRESS_LIMIT_MPA."""
    length = _straight_length_min()
    edge_bearing = 6.0 * moment_nmm / (PRESS_ZONE_DIA * length**2)
    loose_pressure, _, _ = _collar_lame(
        PRESS_FIT_BUDGET["interference_effective_min"], COLLAR_OD_MIN
    )
    tight_pressure, tight_hoop, _ = _collar_lame(
        PRESS_FIT_BUDGET["interference_max"], COLLAR_OD_MIN
    )
    ratio = tight_hoop / tight_pressure
    edge_pressure = tight_pressure + edge_bearing
    return {
        "edge_bearing_mpa": edge_bearing,
        "opening_moment_loose_nmm": loose_pressure * PRESS_ZONE_DIA * length**2 / 6.0,
        "edge_pressure_tight_mpa": edge_pressure,
        "edge_von_mises_tight_mpa": edge_pressure * math.sqrt(ratio**2 + 1.0 + ratio),
    }
