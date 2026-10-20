"""Worst-case envelopes for the one south cylinder-bank retaining disc.

No builders or bank layout are imported: the owning disc spec supplies its
sizes and the layout supplies its compensated axial datum band. The 64T test
uses a separating plane normal to that gear's radial axis, so clearing its
complete tooth-tip cylinder also clears its root and every tooth phase.
"""
from __future__ import annotations

import math

import ch_connecting_rod_spec as rod
import cone_line as line
import cone_set_stack as setup
import dt_alignment_pinion_spec as alignment
import dt_crank_drive_gear_spec as drive
import dt_cylinder_gear_shaft_spec as shaft
import dt_cylinder_gear_spec as gear
from gear_seat_fit import GEAR_SEAT_CLEARANCE


def clearance_budget(
    *, outer_dia: float, outer_band: float, bore_max: float,
    thickness_min: float, thickness_max: float, datum_band: float,
) -> dict[str, float]:
    """Millimetres, arithmetic extrema, including bore-permitted disc tilt.

    Face seating against the south strap is still required for the axial
    datum. Radial clearance does not assume perfect face contact or an
    unsupported one-degree normal: use all tilt the bore can accommodate.
    The ring need not have its entire outer rim covered. A positive land
    beyond its farthest bore edge captures its continuous annular face.
    """
    s, c = line.SIN_I, line.COS_I
    seat_x, seat_z = line.cone_seat(0)
    seat_x -= line.X_DRUM
    seat_z -= line.Z_DRUM0
    disc_north_z = gear.FACE_WIDTH / 2.0 - gear.OVERALL_THICKNESS
    drive_south = (
        drive.LAYOUT_CENTRE_STATION - line.SHAFT_T120_STATION
        - drive.LAYOUT_FACE_WIDTH / 2.0 + drive.SOUTH_FACE_SHIFT_NORTH
    )
    pivot_distance = setup.pivot_distance_mm(120)
    set_amplification = (pivot_distance - drive_south) / pivot_distance
    bore_float = (bore_max - (shaft.SHAFT_DIA + shaft.SHAFT_DIA_BAND[1])) / 2.0
    disc_tilt = math.atan(2.0 * bore_float / thickness_min)
    set_stack = (
        setup.TOOTH_RUNOUT_TIR_MM / 2.0 + setup.SET_FEELER_READING_MM
        + (setup.T120_TIP_RADIUS_LIMITS_MM[1] - setup.T120_TIP_RADIUS_LIMITS_MM[0]) / 2.0
        + (setup.DRUM_ROOT_RADIUS_LIMITS_MM[1] - setup.DRUM_ROOT_RADIUS_LIMITS_MM[0]) / 2.0
    )
    pivot_stack = (
        setup.PIVOT_BORE_FLOAT_MM + setup.PIVOT_SEAT_POSITION_MM
        + setup.PIVOT_THREAD_CENTRING_MM + setup.ARBOR_RUNNING_FLOAT_MM
    )
    gear_cock = math.atan(GEAR_SEAT_CLEARANCE[1] / drive.FLAT_ENGAGEMENT_MIN)
    # The south entry chamfer shortens the supporting cylindrical bore and
    # lengthens the far-tip lever; a full-face-width cock estimate understates it.
    cock_lever = (
        drive.FACE_WIDTH + drive.FACE_WIDTH_BAND[0] + drive.BORE_SOUTH_CHAMFER_MAX
    ) / 2.0
    closure = {
        "disc bore float": bore_float,
        "64T tip size": drive.OUTSIDE_DIA_TOLERANCE_MM / 2.0,
        "64T tooth runout": drive.TOOTH_RUNOUT_TIR_MM / 2.0,
        "south datum projected": datum_band * s,
        "T120 set amplified": set_amplification * set_stack,
        "pivot translation residual": abs(1.0 - set_amplification) * pivot_stack,
        "T120 seat floats amplified": set_amplification * (
            setup.CONE_SEAT_FLOAT_MM + setup.DRUM_SEAT_FLOAT_MM
        ),
        "64T seat float": GEAR_SEAT_CLEARANCE[1] / 2.0,
        "64T bore cock": cock_lever * math.sin(gear_cock),
    }
    nominal = (
        c * (-seat_x - outer_dia / 2.0) - s * (disc_north_z - seat_z)
        - drive.OUTSIDE_DIA / 2.0
    )
    size = outer_band / 2.0 * c
    tilted_radius = (outer_dia + outer_band) / 2.0 * (
        math.cos(max(0.0, math.asin(s) - disc_tilt)) - c
    )
    tilted_thickness = thickness_max / 2.0 * c * math.sin(disc_tilt)
    cone_worst = nominal - size - sum(closure.values()) - tilted_radius - tilted_thickness
    # A sphere encloses the complete tilted disc at every normal. This is
    # intentionally more conservative than the engaged pinion's axial section.
    pinion_worst = (
        alignment.ENGAGED_CENTER_DISTANCE_MM - alignment.ENGAGED_CENTER_RADIAL_STACK_MM
        - math.hypot((outer_dia + outer_band) / 2.0, thickness_max / 2.0)
        - bore_float - alignment.outside_dia_limits_mm()[1] / 2.0
    )
    farthest_ring_bore = (
        gear.ECCENTRICITY + gear.ECCENTRICITY_TOLERANCE_MM
        + (rod.RING_BORE_DIA + rod.RING_BORE_DIA_BAND[0]) / 2.0
        + rod.STRAP_DIAMETRAL_CLEARANCE[1] / 2.0
        + gear.BORE_DIAMETRAL_CLEARANCE_MM[1] / 2.0
    )
    retaining_land = (
        (outer_dia - outer_band) / 2.0 * math.cos(disc_tilt)
        - bore_float - farthest_ring_bore
    )
    return {
        "cone nominal": nominal,
        "cone closure": sum(closure.values()),
        "cone OD band": size,
        "cone disc radial tilt": tilted_radius,
        "cone disc thickness tilt": tilted_thickness,
        "cone worst": cone_worst,
        "engaged pinion worst": pinion_worst,
        "retaining land": retaining_land,
        "disc bore float": bore_float,
        "disc tilt radians": disc_tilt,
        **{f"closure: {name}": value for name, value in closure.items()},
    }
