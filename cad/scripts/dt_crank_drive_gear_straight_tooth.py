"""The 64T's straight tooth away from its crossing station, and the base
tangent span a flat-anvil micrometer reads on it.

The spec's tooth numbers come from the cutter's normal-section screw model,
which the straight tooth space (straight_gash) matches only at the station
where the cutter's centre plane crosses the gear axis
(``dt_crank_drive_gear_spec.TOOTH_SPACE_CROSSING``).  Away from it the space
shifts sideways off its radial line, so the tooth is thicker on the pitch
circle and the root rises.  Both the fixed-centre mesh's per-station report
(``crank_mesh_stack.station_checks``) and the 64T's printed span acceptance
read them here, from the 64T spec alone, so neither the part nor its sheet
imports the drive-train stack.
"""

from __future__ import annotations

import math

import dt_crank_drive_gear_spec as gear64

R64 = gear64.PITCH_DIA / 2.0
_BETA = math.radians(gear64.TOOTH_INCLINATION_DEG)


def _gap_arc_on_pitch_circle(shift_mm: float) -> float:
    """Arc the straight tooth space takes from the pitch circle where its
    transverse section sits ``shift_mm`` off the radial line (straight_gash:
    (X, Y/cos(beta) + shift))."""
    form, cos_beta = gear64.TOOTH_SPACE_FORM, math.cos(_BETA)

    def azimuth(side: int) -> float:
        def point(u: float) -> tuple[float, float]:
            x, y = form.flank_point(u, side)
            return x, y / cos_beta + shift_mm

        low, high = form.flank_parameter_min, form.flank_parameter_max
        if not math.hypot(*point(low)) < R64 < math.hypot(*point(high)):
            raise AssertionError("the 64T pitch circle must cross the cutter flank")
        for _ in range(80):
            middle = (low + high) / 2.0
            if math.hypot(*point(middle)) < R64:
                low = middle
            else:
                high = middle
        x, y = point((low + high) / 2.0)
        return math.atan2(y, x)

    return R64 * (azimuth(1) - azimuth(-1))


def straight_tooth_thickening(station_mm: float) -> float:
    """Normal circular thickness a straight 64T tooth gains on the pitch
    circle at a face station (mm north of mid-face), over its thickness at the
    crossing station that ``crank_mesh_stack.standard_check`` books."""
    height = gear64.FACE_WIDTH / 2.0 + station_mm
    shift = (height - gear64.TOOTH_SPACE_CROSSING) * math.tan(_BETA)
    return (_gap_arc_on_pitch_circle(0.0) - _gap_arc_on_pitch_circle(shift)) * math.cos(
        _BETA
    )


def straight_root_rise(station_mm: float) -> float:
    """Radial rise of a straight tooth space's root at a face station."""
    height = gear64.FACE_WIDTH / 2.0 + station_mm
    shift = (height - gear64.TOOTH_SPACE_CROSSING) * math.tan(_BETA)
    return math.hypot(gear64.ROOT_DIA / 2.0, shift) - gear64.ROOT_DIA / 2.0


# Owner ruling 2026-11-20 (Pedro, triage of 2026-11-19, #2512 option 1):
# the span acceptance is booked at the station a flat-anvil micrometer seats
# on.  Anvils spanning the whole face bear on the thickest section, the north
# face (the crossing is a quarter face from the south face, so the north face
# is farthest from it), where each tooth is thicker on the pitch circle than
# the screw model by straight_tooth_thickening(+FACE_WIDTH/2); a base tangent
# span grows by a normal thickness change times cos(normal pressure angle).
# The north-face limits are the crossing station's printed limits
# (BASE_TANGENT_SPAN_LIMITS_MM, which set the cutter's translation corners the
# mesh check gates) shifted by that growth, so a part inside them is inside
# the gated corners.  The sheet prints them rounded inward onto the .0001 in
# grid (dt_crank_drive_gear_notes.accept_limits_text); the modelled north face
# (the spec's nominal span plus the growth) must stay inside, which the
# drawing test checks at the printed precision.
FLAT_ANVIL_STATION_MM = gear64.FACE_WIDTH / 2.0
FLAT_ANVIL_SPAN_GROWTH_MM = straight_tooth_thickening(FLAT_ANVIL_STATION_MM) * math.cos(
    math.radians(gear64.CUTTER_PRESSURE_ANGLE_DEG)
)
if not FLAT_ANVIL_SPAN_GROWTH_MM >= max(
    straight_tooth_thickening(station)
    * math.cos(math.radians(gear64.CUTTER_PRESSURE_ANGLE_DEG))
    for station in (-gear64.FACE_WIDTH / 2.0, 0.0)
):
    raise AssertionError("the 64T's north face is no longer its thickest section")
FLAT_ANVIL_SPAN_LIMITS_MM = tuple(
    limit + FLAT_ANVIL_SPAN_GROWTH_MM for limit in gear64.BASE_TANGENT_SPAN_LIMITS_MM
)
