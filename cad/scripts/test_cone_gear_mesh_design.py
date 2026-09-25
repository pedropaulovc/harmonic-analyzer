"""Re-derive the deepened cone/drum mesh (U38 option 1b) from its printed values.

``cone_gear_spec.DEEPENED_MESH_MM`` prints each gear's tip diameter and thick
tooth limit.  These tests rebuild the planar involute mesh at the deep edge of
each drum face -- the slice that carries the load -- from the assembly pose and
the printed bands, and check the design rules the table was sized to:

* tightest case (thickest tooth, runouts closing): backlash >= BL_MIN;
* loosest case (thinnest tooth, runouts and journal float opening): backlash
  inside the printed acceptance, whose upper is that limit;
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

import pytest

import build_drive_train_assembly as assembly
import cone_gear_spec as spec
import cylinder_gear_notes
import cylinder_gear_spec as drum
from cone_drum_mesh import (  # noqa: F401  the mesh this test re-derives
    BASE_PITCH,
    CONE_RUNOUT,
    DRUM_BASE_R,
    DRUM_FLOOR_R,
    DRUM_OD_LOWER,
    DRUM_PITCH_R,
    DRUM_RUNOUT,
    DRUM_THICKNESS,
    DRUM_TIP_R,
    FLOAT,
    INTERLEAVE,
    PRESSURE_ANGLE,
    RUNOUT,
    M,
)
from cone_drum_mesh import backlash as _backlash
from cone_drum_mesh import centre as _centre
from cone_drum_mesh import contact_ratio as _contact_ratio
from cone_drum_mesh import inv as _inv
from cone_drum_mesh import tip_land as _tip_land

LAND_MIN = 0.10
DRUM_FLOOR_MIN = 0.10
CR_EXCEPTION = 1.1
CR_TARGET = 1.20


def _worst(teeth: int, tip_dia: float, thickest: float) -> dict[str, float]:
    thinnest = thickest - (spec.TOOTH_THICKNESS_BAND[0] - spec.TOOTH_THICKNESS_BAND[1])
    od_upper, od_lower = spec.BLANK_DIA_BAND
    nominal = _centre(teeth)
    closing = nominal - RUNOUT
    return {
        "tight_backlash": _backlash(teeth, thickest, closing),
        "loose_backlash": _backlash(teeth, thinnest, nominal + FLOAT),
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


def test_backlash_acceptance_upper_is_the_loosest_printed_mesh() -> None:
    # The separating tooth load takes up both journal clearances while the
    # mesh is rocked, so the loosest reading includes FLOAT, not only RUNOUT.
    loosest = max(
        _worst(teeth, *spec.DEEPENED_MESH_MM[teeth])["loose_backlash"]
        for teeth in spec.CONFIGURATION_TEETH
    )
    high = spec.BACKLASH_ACCEPTANCE_MM[1]
    assert high == math.ceil(loosest * 100.0) / 100.0, loosest


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
    if teeth in spec.FLOOR_LIMITS_MM:
        # Two-sided floor: MAX is the shallowest floor keeping 0.02 of
        # drum-tip clearance with every runout closing (a shallow plunge would
        # rub); MIN is the web limit.
        minimum, maximum = spec.FLOOR_LIMITS_MM[teeth]
        drum_path = _centre(teeth) - RUNOUT - DRUM_TIP_R
        assert clearance > 0.04  # +0.045 at T006, +0.076 at T012
        assert drum_path - maximum / 2.0 >= 0.02
        assert drum_path - (maximum + 0.001) / 2.0 < 0.02
        # Main: T006's window must be at least 0.04 on diameter.
        assert maximum - minimum >= 0.04
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


def test_drive_train_clearance_scans_use_the_printed_cone_tip() -> None:
    # Codex (#834): the T120/16T scan kept the standard pitch radius +
    # addendum (Ø62.20) after the long-addendum blank grew the printed tip to
    # Ø62.93.  Every cone-tip clearance check reads the printed OD at its
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
