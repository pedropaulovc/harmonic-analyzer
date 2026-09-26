"""Re-derive the deepened cone/drum mesh (U38 option 1b) from its printed values.

``cone_gear_spec.DEEPENED_MESH_MM`` prints each gear's tip diameter and thick
tooth limit.  These tests rebuild the planar involute mesh at the deep edge of
each drum face -- the slice that carries the load -- from the assembly pose and
the printed bands, and check the design rules the table was sized to:

* tightest case (thickest tooth, runouts and fit-up residual closing):
  backlash >= BL_MIN;
* loosest case (thinnest tooth, runouts, journal float and fit-up residual
  opening): backlash inside the printed acceptance, whose limits are the
  derived extremes rounded outward;
* thinnest tooth at the largest tip: tip land >= 0.10;
* largest tip, closing: cone tip >= 0.10 off the drum's chord floor, and the
  drum tip clear of the printed cone floor (0.30 where it is raised);
* one fly cutter at least 0.43 wide fits every gap at the thickest tooth;
* least engagement (smallest tips, everything opening): contact ratio >= 1.1
  except on the named book-fidelity exception gears;
* each printed value is the limit, not an arbitrary point inside it.

The fit-up residual (#917 R1, budget row A5) is what the assembly's mesh
setting leaves: one backlash reading's resolution, plus the post re-seating on
its dowel pair, which swings the shaft about the tip cup and so moves each gear
by its lever from the cup.  It is taken per station.

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
SEAT_LAND_LOWER = min(cone_gear_shaft_spec.GEAR_SEAT_BAND[1], -0.05)
CONE_RUNOUT = (spec.BORE_DIA_BAND[0] - SEAT_LAND_LOWER) / 2.0
DRUM_RUNOUT = drum.BORE_DIAMETRAL_CLEARANCE_MM[1] / 2.0
_JOURNAL = max(_config.fit("shaft_in_bushing")["diametral_clearance_mm"]) / 2.0
RUNOUT = CONE_RUNOUT + DRUM_RUNOUT
# Cone-shaft journal in its post, and the drum arbor in its pedestal.
FLOAT = RUNOUT + 2.0 * _JOURNAL

# Fit-up residual inputs (#917 R1).  The post is set and re-seated between
# the tip cup (MHA-097's apex) and its own station.
BACKLASH_READ = 0.01  # resolution of one backlash reading
DOWEL_REPEAT = 0.01  # lateral repeat of the post re-seating on its dowels
S_CUP = assembly._ADJ_CUP_APEX
S_POST = assembly.POST_STATION

LAND_MIN = 0.10
DRUM_FLOOR_MIN = 0.10
CR_EXCEPTION = 1.1
CR_TARGET = 1.20


def _inv(angle: float) -> float:
    return math.tan(angle) - angle


def _station(teeth: int) -> float:
    """Shaft station of the gear's deep-edge transverse slice."""
    j = (120 - teeth) // 6
    return (
        assembly.SHAFT_T120_STATION
        + assembly.GEAR_AXIS_SHIFT
        + (assembly.CONE_FACE_STATION_REFERENCE - assembly.CONE_FACE) / 2.0
        + j * assembly.SEAT_PITCH
    )


def _fitup_residual_terms(teeth: int) -> dict[str, float]:
    """The fit-up residual at this gear's station, term by term."""
    return {
        "backlash read": BACKLASH_READ / (2.0 * math.tan(PRESSURE_ANGLE)),
        "dowel re-seat": DOWEL_REPEAT
        / assembly.COS_I
        * (S_CUP - _station(teeth))
        / (S_CUP - S_POST),
    }


def _closing_terms(teeth: int) -> dict[str, float]:
    """Everything that can close the mesh from its nominal centre distance."""
    return {
        "cone runout": CONE_RUNOUT,
        "drum runout": DRUM_RUNOUT,
        **_fitup_residual_terms(teeth),
    }


def _opening_terms(teeth: int) -> dict[str, float]:
    """Everything that can open it: the closing terms plus both floats."""
    return {
        **_closing_terms(teeth),
        "cone journal float": _JOURNAL,
        "drum arbor float": _JOURNAL,
    }


def _closing(teeth: int) -> float:
    return sum(_closing_terms(teeth).values())


def _opening(teeth: int) -> float:
    return sum(_opening_terms(teeth).values())


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
    centre = np.array(assembly.cone_station(_station(teeth)))
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
    closing = nominal - _closing(teeth)
    opening = nominal + _opening(teeth)
    return {
        "tight_backlash": _backlash(teeth, thickest, closing),
        "loose_backlash": _backlash(teeth, thinnest, opening),
        "tip_land": _tip_land(teeth, thinnest, (tip_dia + od_upper) / 2.0),
        "drum_floor": closing - (tip_dia + od_upper) / 2.0 - DRUM_FLOOR_R,
        "cone_floor": closing
        - DRUM_TIP_R
        - spec.floor_radius_mm(teeth),
        "contact_ratio": _contact_ratio(
            teeth,
            (tip_dia + od_lower) / 2.0,
            DRUM_TIP_R - DRUM_OD_LOWER / 2.0,
            opening,
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
    # closing; +0.045 at T006 is the tightest running clearance.
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


def test_each_mesh_allowance_counts_once() -> None:
    # #917 C2 (Main): the fit-up residual adds once to each side, on top of
    # RUNOUT and FLOAT; FLOAT already carries both journal clearances
    # (bf1dbc8c2).  A term added twice, or a second float, shows up here by
    # name.
    for teeth in spec.CONFIGURATION_TEETH:
        assert list(_closing_terms(teeth)) == [
            "cone runout",
            "drum runout",
            "backlash read",
            "dowel re-seat",
        ]
        assert list(_opening_terms(teeth)) == [
            *_closing_terms(teeth),
            "cone journal float",
            "drum arbor float",
        ]
        residual = sum(_fitup_residual_terms(teeth).values())
        assert _closing(teeth) == pytest.approx(RUNOUT + residual)
        assert _opening(teeth) == pytest.approx(FLOAT + residual)


def test_fitup_residual_matches_the_917_budget() -> None:
    # Budget row A5: reading backlash to 0.01 is 0.019 of centre distance at
    # 14.5 deg; a 0.01 dowel re-seat at the post adds 0.008 at T120, whose
    # lever from the tip cup is longest, and under 0.001 at T006.
    read = _fitup_residual_terms(120)["backlash read"]
    assert read == pytest.approx(0.0193, abs=0.00005)
    residual = {
        teeth: sum(_fitup_residual_terms(teeth).values()) for teeth in (6, 120)
    }
    assert residual[120] == pytest.approx(0.0276, abs=0.00005)
    assert residual[6] == pytest.approx(0.0201, abs=0.00005)
    stations = [_station(teeth) for teeth in spec.CONFIGURATION_TEETH]
    assert S_POST < min(stations) and max(stations) < S_CUP


def test_backlash_acceptance_is_the_derived_band_rounded_outward() -> None:
    # The separating tooth load takes up both journal clearances while the
    # mesh is rocked, so the loosest reading includes FLOAT, not only RUNOUT.
    # Rounded outward to the printed two places so the band always covers the
    # derived worst cases: the upper up, the lower down.
    worst = [
        _worst(teeth, *spec.DEEPENED_MESH_MM[teeth])
        for teeth in spec.CONFIGURATION_TEETH
    ]
    loosest = max(case["loose_backlash"] for case in worst)
    tightest = min(case["tight_backlash"] for case in worst)
    low, high = spec.BACKLASH_ACCEPTANCE_MM
    assert high == math.ceil(loosest * 100.0) / 100.0, loosest
    assert low == math.floor(tightest * 100.0) / 100.0, tightest
    assert low == spec.MESH_BACKLASH_MIN_MM


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
def test_gap_floor_fits_one_cutter(teeth: int) -> None:
    # Main: one fly cutter at least 0.43 wide fits every gap.
    assert _floor_width(teeth, spec.DEEPENED_MESH_MM[teeth][1]) >= 0.43


# What sets each two-sided floor's MIN: the web (T006's named exception,
# T012's 2.05), or the 0.10 drum-tip clearance every chord floor keeps.
FLOOR_MIN_RULE = {6: "web", 12: "web", 18: "drum"}
T006_FLOOR_PENDING = pytest.mark.xfail(
    strict=True,
    reason=(
        "T006's floor limits predate the fit-up residual and leave no 0.04 "
        "window; morning-brief-20260926.md § Decision: T006 cone-gear floor "
        "under the fit-up residual (C2)"
    ),
)


@pytest.mark.parametrize(
    "teeth",
    [
        pytest.param(teeth, marks=T006_FLOOR_PENDING) if teeth == 6 else teeth
        for teeth in spec.CONFIGURATION_TEETH
    ],
)
def test_gap_floor_clears_the_drum(teeth: int) -> None:
    tip_dia, thickest = spec.DEEPENED_MESH_MM[teeth]
    clearance = _worst(teeth, tip_dia, thickest)["cone_floor"]
    drum_path = _centre(teeth) - _closing(teeth) - DRUM_TIP_R
    assert set(FLOOR_MIN_RULE) == set(spec.FLOOR_LIMITS_MM)
    if teeth in spec.FLOOR_LIMITS_MM:
        # Two-sided floor: MAX is the shallowest floor keeping 0.02 of
        # drum-tip clearance with everything closing (a shallow plunge would
        # rub).
        minimum, maximum = spec.FLOOR_LIMITS_MM[teeth]
        assert clearance > 0.04
        assert drum_path - maximum / 2.0 >= 0.02
        assert drum_path - (maximum + 0.001) / 2.0 < 0.02
        # Main: the window must be at least 0.04 on diameter.
        assert maximum - minimum >= 0.04
        if FLOOR_MIN_RULE[teeth] == "drum":
            # The shallowest MIN keeping the chord floors' 0.10.
            assert drum_path - minimum / 2.0 >= 0.10
            assert drum_path - (minimum + 0.001) / 2.0 < 0.10
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
    assert drum_path - higher < 0.30


def test_drive_train_clearance_scans_use_the_printed_cone_tip() -> None:
    # Codex (#834): the T120/16T scan kept the standard pitch radius +
    # addendum (Ø62.20) after the long-addendum blank grew the printed tip
    # past it.  Every cone-tip clearance check reads the printed OD at its
    # upper limit, and the 16T keeps its 0.25 axial air at that tip.
    assert assembly._TIP120 == pytest.approx(
        (spec.outside_dia_mm(120) + spec.BLANK_DIA_BAND[0]) / 2.0
    )
    for teeth in spec.CONFIGURATION_TEETH:
        assert assembly._cone_tip_radius_max(teeth) == pytest.approx(
            (spec.outside_dia_mm(teeth) + spec.BLANK_DIA_BAND[0]) / 2.0
        )
    pinion_north = assembly.PINION_TOOTH_Z + assembly.PINION_FACE / 2.0
    assert assembly._T120_SOUTH - pinion_north >= 0.25
