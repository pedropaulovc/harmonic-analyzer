"""Re-derive the deepened cone/drum mesh (U38 option 1b) from its printed values.

``cone_gear_spec.DEEPENED_MESH_MM`` prints each gear's tip diameter and thick
tooth limit.  These tests rebuild the planar involute mesh at the deep edge of
each drum face -- the slice that carries the load -- from the assembly pose and
the printed bands, and check the design rules the table was sized to:

* tightest case (thickest tooth, runouts closing): backlash >= BL_MIN;
* thinnest tooth at the largest tip: tip land >= 0.10;
* largest tip, runouts closing: cone tip >= 0.10 off the drum's chord floor,
  and the drum tip clear of the printed cone floor (0.30 where it is raised);
* one fly cutter at least 0.43 wide fits every gap at the thickest tooth;
* least engagement (smallest tips, all float opening): contact ratio >= 1.1
  except on the named book-fidelity exception gears;
* each printed value is the limit, not an arbitrary point inside it.

Planar, rigid: the U38 slice sweep found the 3-D stretch costs at most
0.005 of backlash, which is why BL_MIN is 0.06 and not 0.05.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

import _config
import build_drive_train_assembly as assembly
import cone_gear_shaft_spec
import cone_gear_spec as spec
import cylinder_gear_notes
import cylinder_gear_spec as drum


M = spec.MODULE_MM
PRESSURE_ANGLE = math.radians(spec.PRESSURE_ANGLE_DEG)
DRUM_PITCH_R = drum.TEETH * M / 2.0
DRUM_BASE_R = DRUM_PITCH_R * math.cos(PRESSURE_ANGLE)
DRUM_TIP_R = drum.OUTSIDE_DIA / 2.0
DRUM_THICKNESS = spec.STANDARD_TOOTH_THICKNESS  # "FULL STANDARD THICKNESS"
DRUM_OD_LOWER = 0.10  # MHA-027 prints its tip +0/-0.10
DRUM_FLOOR_R = spec.chord_floor_radius_mm(120, thickness_mm=DRUM_THICKNESS)
BASE_PITCH = math.pi * M * math.cos(PRESSURE_ANGLE)

# Radial play.  Runouts turn with their gear, so they close the mesh at some
# angle; float can open it.  The cone runout is sized for the soldered seats
# #839 prints (0/-0.05), the looser of that and the current shaft land band.
SEAT_LAND_LOWER = min(cone_gear_shaft_spec.SECTION_DIA_BAND[1], -0.05)
CONE_RUNOUT = (spec.BORE_DIA_BAND[0] - SEAT_LAND_LOWER) / 2.0
DRUM_RUNOUT = drum.BORE_DIAMETRAL_CLEARANCE_MM[1] / 2.0
_JOURNAL = max(_config.fit("shaft_in_bushing")["diametral_clearance_mm"]) / 2.0
RUNOUT = CONE_RUNOUT + DRUM_RUNOUT
# Cone-shaft journal in its post, and the drum arbor in its pedestal.
FLOAT = RUNOUT + 2.0 * _JOURNAL

LAND_MIN = 0.10
DRUM_FLOOR_MIN = 0.10
CR_EXCEPTION = 1.1
CR_TARGET = 1.20


def _inv(angle: float) -> float:
    return math.tan(angle) - angle


def _interleave(teeth: int) -> float:
    """Standard-tip interleave at the deep edge of the drum face, as posed.

    The assembly places a standard ``(N + 2) / DP`` tip circle; its nearest
    reach to the drum axis inside the drum face band sets the operating centre
    distance of the deep transverse slice.
    """
    j = (120 - teeth) // 6
    axis = np.array([assembly.SIN_I, 0.0, assembly.COS_I])
    e1 = np.cross(axis, [0.0, 1.0, 0.0])
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(axis, e1)
    centre = np.array(
        assembly.cone_station(
            assembly.SHAFT_T120_STATION
            + assembly.GEAR_AXIS_SHIFT
            + (assembly.CONE_FACE_STATION_REFERENCE - assembly.CONE_FACE) / 2.0
            + j * assembly.SEAT_PITCH
        )
    )
    z0 = assembly.Z_DRUM0 + assembly.Z_PITCH * j
    tip_r = teeth * M / 2.0 + M
    theta = np.radians(np.linspace(0.0, 360.0, 36001))
    ring = centre + tip_r * (
        np.cos(theta)[:, None] * e1 + np.sin(theta)[:, None] * e2
    )
    # Along the gear axis a point is ring + a * axis.  Its z is linear in a,
    # so the drum face band and the cone face bound a to one interval, and
    # its squared distance from the drum axis is a quadratic in a: the exact
    # minimum is the vertex clipped to that interval.
    half_band = assembly.DRUM_FACE / 2.0
    a_lo = np.maximum(-assembly.CONE_FACE / 2.0, (z0 - half_band - ring[:, 2]) / axis[2])
    a_hi = np.minimum(assembly.CONE_FACE / 2.0, (z0 + half_band - ring[:, 2]) / axis[2])
    dx = ring[:, 0] - assembly.X_DRUM
    dy = ring[:, 1] - assembly.Y_DRIVE
    slope = axis[0] ** 2 + axis[1] ** 2
    vertex = -(dx * axis[0] + dy * axis[1]) / slope
    along = np.clip(vertex, a_lo, a_hi)
    rho = np.hypot(dx + along * axis[0], dy + along * axis[1])
    return DRUM_TIP_R - float(rho[a_lo <= a_hi].min())


INTERLEAVE = {teeth: _interleave(teeth) for teeth in spec.CONFIGURATION_TEETH}


def _centre(teeth: int) -> float:
    """Nominal operating centre distance of the deep transverse slice."""
    return teeth * M / 2.0 + M + DRUM_TIP_R - INTERLEAVE[teeth]


def _backlash(teeth: int, thickness: float, centre: float) -> float:
    """Exact planar circumferential backlash at the operating pitch circles."""
    r1 = teeth * M / 2.0
    working = math.acos((r1 + DRUM_PITCH_R) * math.cos(PRESSURE_ANGLE) / centre)
    r1w = centre * r1 / (r1 + DRUM_PITCH_R)
    r2w = centre * DRUM_PITCH_R / (r1 + DRUM_PITCH_R)
    delta = _inv(PRESSURE_ANGLE) - _inv(working)
    s1w = 2.0 * r1w * (thickness / (2.0 * r1) + delta)
    s2w = 2.0 * r2w * (DRUM_THICKNESS / (2.0 * DRUM_PITCH_R) + delta)
    return 2.0 * math.pi * r1w / teeth - s1w - s2w


def _tip_land(teeth: int, thickness: float, tip_r: float) -> float:
    r1 = teeth * M / 2.0
    tip_angle = math.acos(r1 * math.cos(PRESSURE_ANGLE) / tip_r)
    return 2.0 * tip_r * (
        thickness / (2.0 * r1) + _inv(PRESSURE_ANGLE) - _inv(tip_angle)
    )


def _contact_ratio(teeth: int, tip_r: float, drum_tip_r: float, centre: float) -> float:
    """Transverse CR with both base-circle interference limits."""
    base_r = teeth * M / 2.0 * math.cos(PRESSURE_ANGLE)
    working = math.acos((base_r + DRUM_BASE_R) / centre)
    line = centre * math.sin(working)
    start = max(line - math.sqrt(drum_tip_r**2 - DRUM_BASE_R**2), 0.0)
    end = min(math.sqrt(tip_r**2 - base_r**2), line)
    return (end - start) / BASE_PITCH


def _worst(teeth: int, tip_dia: float, thickest: float) -> dict[str, float]:
    thinnest = thickest - (spec.TOOTH_THICKNESS_BAND[0] - spec.TOOTH_THICKNESS_BAND[1])
    od_upper, od_lower = spec.BLANK_DIA_BAND
    nominal = _centre(teeth)
    closing = nominal - RUNOUT
    return {
        "tight_backlash": _backlash(teeth, thickest, closing),
        "loose_backlash": _backlash(teeth, thinnest, nominal + RUNOUT),
        "tip_land": _tip_land(teeth, thinnest, (tip_dia + od_upper) / 2.0),
        "drum_floor": closing - (tip_dia + od_upper) / 2.0 - DRUM_FLOOR_R,
        "cone_floor": closing
        - DRUM_TIP_R
        - spec.floor_radius_mm(teeth),
        "contact_ratio": _contact_ratio(
            teeth,
            (tip_dia + od_lower) / 2.0,
            DRUM_TIP_R - DRUM_OD_LOWER / 2.0,
            nominal + FLOAT,
        ),
    }


def test_inputs_are_the_printed_ones() -> None:
    assert f"{drum.OUTSIDE_DIA:.2f} +0/-{DRUM_OD_LOWER:.2f}" in cylinder_gear_notes.GEAR_DATA
    assert spec.BLANK_DIA_BAND == (0.10, -0.10)
    assert set(spec.DEEPENED_MESH_MM) == set(spec.CONFIGURATION_TEETH)
    # The pose puts every gear at the same deep-edge interleave, 0.470 mm.
    # (The U38 study read 0.459 off a 0.05 mm axial sampling grid; the depth
    # changes by tan(12.52 deg) per mm along the face, so the grid missed the
    # face edge by 0.011.)
    assert max(INTERLEAVE.values()) - min(INTERLEAVE.values()) < 0.001
    assert INTERLEAVE[60] == pytest.approx(0.470, abs=0.001)


@pytest.mark.parametrize("teeth", spec.CONFIGURATION_TEETH)
def test_printed_mesh_meets_its_design_rules(teeth: int) -> None:
    tip_dia, thickest = spec.DEEPENED_MESH_MM[teeth]
    worst = _worst(teeth, tip_dia, thickest)
    assert worst["tight_backlash"] >= spec.MESH_BACKLASH_MIN_MM, worst
    assert worst["tip_land"] >= LAND_MIN, worst
    assert worst["drum_floor"] >= DRUM_FLOOR_MIN, worst
    # The drum tip still clears the (risen) chord floor with every runout
    # closing; +0.030 at T006 is the tightest running clearance.
    assert worst["cone_floor"] > 0.0, worst
    low, high = spec.BACKLASH_ACCEPTANCE_MM
    assert low == spec.MESH_BACKLASH_MIN_MM
    assert worst["loose_backlash"] <= high, worst
    if teeth in spec.CONTACT_RATIO_EXCEPTION_TEETH:
        assert worst["contact_ratio"] < CR_EXCEPTION, worst
    else:
        assert worst["contact_ratio"] >= CR_EXCEPTION, worst
    # Deeper than today everywhere: a standard tip and tooth at the same
    # stack.
    standard = _worst(teeth, (teeth + 2) * M, spec.STANDARD_TOOTH_THICKNESS)
    assert worst["contact_ratio"] > standard["contact_ratio"]


@pytest.mark.parametrize("teeth", spec.CONFIGURATION_TEETH)
def test_printed_values_are_the_limits(teeth: int) -> None:
    tip_dia, thickest = spec.DEEPENED_MESH_MM[teeth]
    thicker = _worst(teeth, tip_dia, thickest + 0.001)
    assert thicker["tight_backlash"] < spec.MESH_BACKLASH_MIN_MM
    worst = _worst(teeth, tip_dia, thickest)
    if worst["contact_ratio"] >= CR_TARGET:
        # Smallest tip reaching the target: one step less misses it.
        smaller = _worst(teeth, tip_dia - 0.01, thickest)
        assert smaller["contact_ratio"] < CR_TARGET
        return
    # Otherwise the largest tip the land and drum floor allow.
    larger = _worst(teeth, tip_dia + 0.01, thickest)
    assert larger["tip_land"] < LAND_MIN or larger["drum_floor"] < DRUM_FLOOR_MIN


def _floor_width(teeth: int, thickest: float) -> float:
    """Gap width at the flank feet for the thickest tooth: the widest fly
    cutter tip that fits every gear cut to the printed thickness band."""
    r1 = teeth * M / 2.0
    tmin = spec.floor_tmin(teeth)
    foot_r = r1 * math.cos(PRESSURE_ANGLE) * math.hypot(1.0, tmin)
    roll = tmin - math.atan(tmin)
    half_tooth = thickest / (2.0 * r1) + _inv(PRESSURE_ANGLE) - roll
    return 2.0 * foot_r * math.sin(math.pi / teeth - half_tooth)


@pytest.mark.parametrize("teeth", spec.CONFIGURATION_TEETH)
def test_gap_floor_clears_the_drum_and_fits_one_cutter(teeth: int) -> None:
    tip_dia, thickest = spec.DEEPENED_MESH_MM[teeth]
    clearance = _worst(teeth, tip_dia, thickest)["cone_floor"]
    # Main: one fly cutter at least 0.43 wide fits every gap.
    assert _floor_width(teeth, thickest) >= 0.43
    # Every floor is two-sided (Main, 2026-09-26: the #834 machinist review
    # found sheets 3-20 printed MIN only).  MAX is the shallowest floor keeping
    # 0.02 of drum-tip clearance with every runout closing (a shallow plunge
    # would rub), floored to three places; MIN is the modelled floor.
    minimum, maximum = spec.floor_limits_mm(teeth)
    drum_path = _centre(teeth) - RUNOUT - DRUM_TIP_R
    assert drum_path - maximum / 2.0 >= 0.02
    assert drum_path - (maximum + 0.001) / 2.0 < 0.02
    # Main: T006's window must be at least 0.04 on diameter; every other
    # gear's is wider.
    assert maximum - minimum >= 0.04
    assert minimum == pytest.approx(2.0 * spec.floor_radius_mm(teeth), abs=0.0005)
    if teeth in spec.DIPPED_FLOOR_MIN_MM:
        assert clearance > 0.04  # +0.045 at T006, +0.076 at T012
        return
    if spec.floor_tmin(teeth) == 0.0:
        assert clearance >= 0.10
        return
    # Raised floors sit exactly as high as a 0.30 worst-case clearance allows.
    assert clearance >= 0.30
    higher = spec.chord_floor_radius_mm(
        teeth,
        thickness_mm=spec.tooth_thickness_mm(teeth),
        tmin=spec.floor_tmin(teeth) + 0.0005,
    )
    assert _centre(teeth) - RUNOUT - DRUM_TIP_R - higher < 0.30


# Face-width band (#914 user ruling, 2026-09-25) against the two axial stacks
# it sits in.  The #834 machinist review asked what needs +/-0.10.
# * Upper limit -- neighbour air.  Adjacent gears sit one seat pitch apart and
#   each is soldered to its station within +/-0.13 (#914 user ruling), so two
#   gears at the upper limit, stations closing, keep
#   SEAT_PITCH - upper - 2 x 0.13.  At the .X band (6.8) that is -0.17: the
#   gears would collide, so the face needs a band tighter than .X.
# * Lower limit -- the drum's engaged zone, [-0.75, +1.35] about the narrowed
#   gear's centre (cone_gear_spec), against the in-service cone/drum stack
#   retention743 re-derived for R1 on 2026-09-26 with the fit-up centring:
#   +0.55 north, -1.10 south (dt-logs/handoffs/retention743-routing-notes.md).
SOLDER_STATION_TOL = 0.13
ENGAGED_ZONE = (-0.75, 1.35)
CONE_DRUM_Z_STACK = (-1.10, 0.55)


def test_face_width_band_holds_both_axial_stacks() -> None:
    upper = spec.FACE_WIDTH + spec.FACE_WIDTH_BAND[0]
    lower = spec.FACE_WIDTH + spec.FACE_WIDTH_BAND[1]
    air = assembly.SEAT_PITCH - upper - 2.0 * SOLDER_STATION_TOL
    assert air == pytest.approx(0.529, abs=0.001)
    assert assembly.SEAT_PITCH - (spec.FACE_WIDTH + 0.8) - 2.0 * SOLDER_STATION_TOL < 0.0
    north = lower / 2.0 - ENGAGED_ZONE[1] - CONE_DRUM_Z_STACK[1]
    south = lower / 2.0 + ENGAGED_ZONE[0] + CONE_DRUM_Z_STACK[0]
    assert (round(north, 2), round(south, 2)) == (1.05, 1.10)
