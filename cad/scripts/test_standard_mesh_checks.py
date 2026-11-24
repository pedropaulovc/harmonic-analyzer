"""Closed-form standard checks of every drive-train mesh, from spec values.

Cone family (owner direction 2026-11-11, #2365: the swing is set by feel,
cone_set_stack). The feel set is what keeps the gears from binding: the
operator locks it where no gear binds, so no pair runs tighter than its own
first bind, and cone_check reports what that leaves there. Against coming
loose, nominal contact ratio >= 1.0 at the loosest running centre a feel
set leaves the cone, what acts after the set taken by root sum square with
the plain sum reported (owner ruling 2026-11-24, audit part 2 P1). The
contact ratio of the printed corners there is
reported only. The crank pair's open-corner figure is a reference, as main
printed it (dt_crank_drive_gear_notes, user ruling 2026-09-30).

Pending exception rulings (#971):
* T006 (user ruling 2026-10-10): no full-depth six-tooth form reaches a
  contact ratio of 1 against the shared 20 deg drum. Its ground relief is
  gated at least 10 um clear of every drum-tip corner's path where the swing
  locks and at the loosest running centre, so the relief never holds the
  swing out; its contact ratio and its backlash where the swing locks are
  reported. The 0.02 mm backlash of the 2026-10-10 feeler set has no
  counterpart under the feel set, which locks wherever no gear binds (owner
  direction 2026-11-11, #2365).
* The alignment pinion is a fit-up mesh: its contact ratio is reported, not
  gated (tolerances/gear_tip.yaml note).
"""
from __future__ import annotations

import math
from dataclasses import replace

import cone_running_axis
import dt_cylinder_gear_spec as drum
from standard_mesh_checks import contact_ratio, plane_gear

import pytest

import alignment_mesh_check
import cone_set_stack
import crank_mesh_stack
import dt_cone_gear_spec as cone
import dt_mesh_checks

EXEMPT_CONE_TEETH = frozenset({6})
CONE_TEETH = tuple(t for t in cone.CONE_TEETH if t not in EXEMPT_CONE_TEETH)
T006_RELIEF_CLEARANCE_MIN_MM = 0.010


def _require_no_bind(check) -> None:
    assert check.backlash_min_mm > 0.0, check.text()
    assert check.root_clearance_min_mm > 0.0, check.text()
    assert check.interference_margin_min_mm >= 0.0, check.text()


@pytest.mark.parametrize("teeth", CONE_TEETH)
def test_cone_drum_mesh_keeps_contact_at_the_loosest_feel_set(teeth: int) -> None:
    check = dt_mesh_checks.cone_check(teeth)
    assert check.contact_ratio_nominal >= cone_set_stack.NOMINAL_CONTACT_RATIO_MIN, check.text()


@pytest.mark.parametrize("teeth", cone.CONE_TEETH)
def test_the_check_takes_what_acts_after_the_set(teeth: int) -> None:
    """P1 (owner ruling 2026-11-24): the set is not a term; the runouts of
    the cone and the drum add (they turn at different speeds); that runout
    and the two seat floats are independent sizes, so the gate takes their
    root sum square and the plain sum is reported beside it."""
    centre = cone_set_stack.cone_centre(teeth)
    runout, cone_float, drum_float = cone_set_stack.after_set_terms_mm(teeth)
    assert runout == pytest.approx(
        2.0 * cone_set_stack.cone_eccentricity_mm(teeth) + cone_set_stack.TOOTH_RUNOUT_TIR_MM
    )
    # A keyed gear runs looser than a bonded holder by its whole float; a
    # bonded gear's float is in its eccentricity.
    expected = cone_set_stack.CONE_SEAT_FLOAT_MM if teeth in cone.KEYED_TEETH else 0.0
    assert cone_float == expected
    assert drum_float == pytest.approx(
        (cone_set_stack.DRUM_SEAT_CLEARANCE[1] - cone_set_stack.DRUM_SEAT_CLEARANCE[0]) / 2.0
    )
    assert centre.ceiling_mm - centre.set_max_mm == pytest.approx(
        math.sqrt(runout**2 + cone_float**2 + drum_float**2)
    )
    assert centre.ceiling_plain_mm - centre.set_max_mm == pytest.approx(
        runout + cone_float + drum_float
    )


@pytest.mark.parametrize("teeth", cone.ROUND_BORE_TEETH)
def test_bonded_gears_book_their_wet_setting(teeth: int) -> None:
    # #3292 and #2473: T012, T018 and T024 cure off their seats by their bond
    # float, so each is tapped true about MHA-DT-04's journal while the 638 is
    # wet, to its sheet 16 limit, which reads the float, the part's own runout
    # and the seat's runout to the journal together. After cure the reading is
    # a record (owner ruling 2026-11-24, audit part 2 C5). The journal axis's
    # offset from the running axis comes on top.
    if teeth in cone.SPIGOT_TEETH:
        eccentricity = cone_set_stack.SPIGOT_ASSEMBLED_RUNOUT_TIR_MM / 2.0
        # The limit is a setting, not a sum the prints guarantee: a part at
        # its .0015 TIR cured at its full bond float is .0033 TIR before the
        # spigot's own float, so the gear is tapped true while wet.
        assert (
            cone_set_stack.SPIGOT_TOOTH_SPACE_RUNOUT_TIR_MM / 2.0
            + cone_set_stack.bond_float_mm(teeth)
            > eccentricity
        )
    else:
        eccentricity = cone_set_stack.LAND_2_ASSEMBLED_RUNOUT_TIR_MM / 2.0
    assert cone_set_stack.seat_eccentricity_mm(teeth) == pytest.approx(eccentricity)
    assert cone_set_stack.cone_eccentricity_mm(teeth) == pytest.approx(
        eccentricity
        + cone_running_axis.journal_axis_offset_mm(
            teeth, cone_set_stack.PIVOT_RUNOUT_TIR_MM / 2.0
        )
    )


def _nominal_contact_ratio(teeth: int, eccentricity_mm: float, *, plain: bool = False) -> float:
    """cone_check's gated figure (or its plain-sum REF) with cone ``teeth``
    at another eccentricity."""
    alpha = cone_set_stack.ALPHA_RAD
    corners = cone_set_stack.drum_corners()
    thickness = [corner.pitch_thickness for corner in corners]
    mate = replace(
        plane_gear(drum.STOCK_FORM, drum.MODULE_MM),
        pitch_thickness=(max(thickness) + min(thickness)) / 2.0,
    )
    terms = (
        2.0 * eccentricity_mm + cone_set_stack.TOOTH_RUNOUT_TIR_MM,
        cone_set_stack.seat_float_mm(teeth),
        cone_set_stack.DRUM_SEAT_FLOAT_SPREAD_MM,
    )
    opening = sum(terms) if plain else math.hypot(*terms)
    centre = cone_set_stack.cone_centre(teeth).set_max_mm + opening
    gear = plane_gear(cone.stock_form_profile(teeth), cone.MODULE_MM)
    return contact_ratio(gear, mate, centre, alpha, cone.MODULE_MM)


def test_the_cone_set_check_reads_both_ways() -> None:
    """The figures of cad/config/checks/cone-set-stack.yaml C-01: the gate
    (root sum square) holds at every station; the plain sum, printed beside
    it, falls under 1.0 on T012 and T030-T054 and is not a gate."""
    pivot = cone_set_stack.PIVOT_RUNOUT_TIR_MM / 2.0
    assert cone_set_stack.PIVOT_RUNOUT_TIR_MM == pytest.approx(0.0020 * 25.4)
    assert cone_set_stack.SPIGOT_ASSEMBLED_RUNOUT_TIR_MM == pytest.approx(0.0030 * 25.4)
    assert set(cone_set_stack.ASSEMBLED_RUNOUT_TIR_MM) == set(cone.ROUND_BORE_TEETH)
    checks = {teeth: dt_mesh_checks.cone_check(teeth) for teeth in CONE_TEETH}
    for teeth, check in checks.items():
        eccentricity = cone_set_stack.cone_eccentricity_mm(teeth)
        assert _nominal_contact_ratio(teeth, eccentricity) == pytest.approx(
            check.contact_ratio_nominal
        )
        assert _nominal_contact_ratio(teeth, eccentricity, plain=True) == pytest.approx(
            check.contact_ratio_nominal_plain
        )
        assert check.contact_ratio_nominal_plain <= check.contact_ratio_nominal
    gate = {teeth: check.contact_ratio_nominal for teeth, check in checks.items()}
    plain = {teeth: check.contact_ratio_nominal_plain for teeth, check in checks.items()}
    # T012 governs the gate; T030 the plain sum (its key float on top).
    assert min(gate, key=gate.get) == 12
    assert gate[12] == pytest.approx(1.0215, abs=5e-4)
    assert gate[30] == pytest.approx(1.0546, abs=5e-4)
    assert min(plain, key=plain.get) == 30
    assert plain[30] == pytest.approx(0.9550, abs=5e-4)
    assert plain[12] == pytest.approx(0.9937, abs=5e-4)
    assert {teeth for teeth, value in plain.items() if value < 1.0} == {12, 30, 36, 42, 48, 54}

    # What the wet tap-true settings buy, from the gate's own figure.
    # T024 left to its part runout and bond float falls under.
    (land_2,) = cone.LAND_2_TEETH
    uncentred = (
        cone_set_stack.TOOTH_RUNOUT_TIR_MM / 2.0
        + cone_set_stack.bond_float_mm(land_2)
        + cone_running_axis.seat_offset_mm(land_2, pivot)
    )
    assert _nominal_contact_ratio(land_2, uncentred) < 1.0
    # T012 left to its part's .0015, its bond float and MHA-DT-37's tilt in a
    # socket taken true to the journal holds; a socket .0005 in TIR off the
    # journal, which no sheet limits, takes it under (Codjiflo review of
    # #3374): so T012 and T018 are read about the journal, not the part.
    spigot_true = (
        cone_set_stack.SPIGOT_TOOTH_SPACE_RUNOUT_TIR_MM / 2.0
        + cone_set_stack.bond_float_mm(12)
        + cone_running_axis.seat_offset_mm(12, pivot)
    )
    assert _nominal_contact_ratio(12, spigot_true) >= 1.0
    socket_off = cone_running_axis.spigot_share(12) * (0.0005 * 25.4 / 2.0)
    assert _nominal_contact_ratio(12, spigot_true + socket_off) < 1.0

    def read_about_the_journal(teeth: int, reading_tir_in: float, pivot_mm: float) -> float:
        return _nominal_contact_ratio(
            teeth,
            reading_tir_in * 25.4 / 2.0
            + cone_running_axis.journal_axis_offset_mm(teeth, pivot_mm),
        )

    # The pivot's tap-true is still needed: the gears' readings are about the
    # journal, not the running axis. At .0030 TIR T012 falls under.
    assert read_about_the_journal(12, 0.0030, 0.0030 * 25.4 / 2.0) < 1.0
    # The keyed gears' .002 TIR to the bore is their booked term: T030 at
    # .004 falls under.
    assert _nominal_contact_ratio(
        30, 0.004 * 25.4 / 2.0 + cone_running_axis.seat_offset_mm(30, pivot)
    ) < 1.0


def test_alignment_drum_fitup_mesh_cannot_bind() -> None:
    _require_no_bind(alignment_mesh_check.alignment_check())


def test_t006_relief_never_holds_the_swing_out() -> None:
    clearance = dt_mesh_checks.t006_relief_clearance_mm()
    assert clearance >= T006_RELIEF_CLEARANCE_MIN_MM, f"T006 relief clearance {clearance:.4f} mm"


def test_t006_relief_centre_lies_inside_its_feel_set_range() -> None:
    """The relief is ground for a centre the T006 mesh actually reaches."""
    floor, ceiling = cone_set_stack.cone_centre(6).range_mm
    relief = (
        cone_set_stack.standard_centre_mm(6)
        + cone.CUSTOM_SIX_RELIEF_CENTRE_ABOVE_STANDARD_MM
    )
    assert floor <= relief <= ceiling


def test_crossed_crank_mesh_passes_the_standard_checks() -> None:
    check = crank_mesh_stack.standard_check()
    _require_no_bind(check)
    assert check.contact_ratio_nominal >= 1.0, check.text()


def test_crank_mesh_station_report_resolves_the_centre_across_the_face() -> None:
    """Reported, not gated (#2481): the axes cross in plan, so the centre
    closes toward the 64T's south face. Mid-face is standard_check's centre.
    The straight tooth thickens away from the cutter's crossing station."""
    import dt_crank_drive_gear_spec as gear64

    rows = crank_mesh_stack.station_checks()
    assert [row.station_mm for row in rows] == list(crank_mesh_stack.FACE_STATIONS_MM)
    shifts = [row.centre_shift_mm for row in rows]
    assert shifts == sorted(shifts) and shifts[0] < 0.0 < shifts[-1]
    middle = rows[len(rows) // 2]
    assert middle.centre_shift_mm == pytest.approx(0.0, abs=1e-12)
    assert middle.backlash_min_mm + middle.tooth_thickening_mm == pytest.approx(
        crank_mesh_stack.standard_check().backlash_min_mm
    )
    # Independent first-order estimate: the space sits s off its radial line,
    # so the pitch circle meets it s^2/2R deeper, where the normal gap is
    # 2 tan(alpha) narrower per unit depth.
    beta = math.radians(gear64.TOOTH_INCLINATION_DEG)
    for row in rows:
        s = (gear64.FACE_WIDTH / 2.0 + row.station_mm - gear64.TOOTH_SPACE_CROSSING) * math.tan(beta)
        estimate = 2.0 * math.tan(math.radians(gear64.CUTTER_PRESSURE_ANGLE_DEG)) * s * s / gear64.PITCH_DIA
        assert row.tooth_thickening_mm == pytest.approx(estimate, rel=0.1, abs=2e-4)
    crossing = gear64.TOOTH_SPACE_CROSSING - gear64.FACE_WIDTH / 2.0
    assert crank_mesh_stack.straight_tooth_thickening(crossing) == pytest.approx(0.0, abs=1e-12)
    assert crank_mesh_stack.straight_root_rise(crossing) == pytest.approx(0.0, abs=1e-12)
    assert rows[-1].tooth_thickening_mm > rows[0].tooth_thickening_mm > 0.0
    assert "REPORTED, not gated; #2481" in crank_mesh_stack.stack_text()


# Backlash the straight tooth takes beyond its thickening, south face to north
# face, from the direct 3D evaluation of #2481 (v3 comment,
# issue_margin_v3.py, "lean check": as-cut straight spaces against the 16T
# with the 64T slid to the axes' common perpendicular, ideal involutes, less
# the same run with the retired screw form and less the thickening), run at
# the .300 in pitch's 12.0247 deg incline and 6.6472 face (#1038) with that
# sampler as #2591 carries it (crank_mesh_free_play.straight_tooth_lean_3d).
STRAIGHT_TOOTH_LEAN_3D_MM = (0.0139, 0.0009, 0.0109, 0.0215, 0.0308)


def test_crank_mesh_station_report_resolves_the_straight_tooth_lean() -> None:
    """Reported, not gated (#2481): off the pitch circle a straight tooth
    space leans against the screw form, so drive and coast contact at
    different radii lose backlash the pitch-circle thickening does not show."""
    import dt_crank_drive_gear_spec as gear64

    rows = crank_mesh_stack.station_checks()
    for row, direct in zip(rows, STRAIGHT_TOOTH_LEAN_3D_MM, strict=True):
        # Control: with the lean off, the sampled mesh is the closed form.
        assert crank_mesh_stack.sampled_station_backlash(
            row.station_mm, lean=False
        ) == pytest.approx(row.backlash_min_mm, abs=2e-4)
        assert row.tooth_lean_mm == pytest.approx(direct, rel=0.12, abs=5e-4)
    crossing = gear64.TOOTH_SPACE_CROSSING - gear64.FACE_WIDTH / 2.0
    assert crank_mesh_stack.straight_tooth_lean(crossing) == pytest.approx(
        0.0, abs=1e-4
    )
    assert rows[-1].tooth_lean_mm > rows[0].tooth_lean_mm > rows[1].tooth_lean_mm >= 0.0
    assert all(
        "lean takes" in line
        for line in crank_mesh_stack.station_text().splitlines()[1:]
    )
