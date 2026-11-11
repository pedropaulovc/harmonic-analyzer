"""Closed-form standard checks of every drive-train mesh, from spec values.

Cone family (user ruling 2026-10-10; centre set at assembly on T120,
cone_set_stack): nominal contact ratio >= 1.0 at the running mean centre,
and no binding, positive root clearance and no involute interference at the
RSS corner. The RSS contact ratio is reported only. The crank pair's
open-corner figure is a reference, as main printed it
(dt_crank_drive_gear_notes, user ruling 2026-09-30).

Pending exception rulings (#971):
* T006 (user ruling 2026-10-10): no full-depth six-tooth form reaches a
  contact ratio of 1 against the shared 20 deg drum. It is gated for a ground
  relief at least 10 um clear of every drum-tip corner's path over its RSS
  centre range and at least 0.02 backlash at the closing corner; its contact
  ratio is reported.
* The alignment pinion is a fit-up mesh: its contact ratio is reported, not
  gated (tolerances/gear_tip.yaml note).
"""
from __future__ import annotations

import math

import pytest

import alignment_mesh_check
import cone_set_stack
import crank_mesh_stack
import dt_cone_gear_spec as cone
import dt_mesh_checks

EXEMPT_CONE_TEETH = frozenset({6})
CONE_TEETH = tuple(t for t in cone.CONE_TEETH if t not in EXEMPT_CONE_TEETH)
CONE_NOMINAL_CONTACT_RATIO_MIN = 1.0
T006_CORNER_BACKLASH_MIN_MM = 0.02
T006_RELIEF_CLEARANCE_MIN_MM = 0.010


def _require_no_bind(check) -> None:
    assert check.backlash_min_mm > 0.0, check.text()
    assert check.root_clearance_min_mm > 0.0, check.text()
    assert check.interference_margin_min_mm >= 0.0, check.text()


@pytest.mark.parametrize("teeth", CONE_TEETH)
def test_cone_drum_mesh_passes_the_standard_checks(teeth: int) -> None:
    check = dt_mesh_checks.cone_check(teeth)
    assert check.contact_ratio_nominal >= CONE_NOMINAL_CONTACT_RATIO_MIN, check.text()
    assert check.backlash_rss_mm > 0.0, check.text()
    assert check.root_clearance_rss_mm > 0.0, check.text()
    assert check.interference_margin_rss_mm >= 0.0, check.text()


def test_alignment_drum_fitup_mesh_cannot_bind() -> None:
    _require_no_bind(alignment_mesh_check.alignment_check())


def test_t006_named_exception_meets_its_ruled_gates() -> None:
    check = dt_mesh_checks.cone_check(6)
    assert check.backlash_corner_min_mm >= T006_CORNER_BACKLASH_MIN_MM, check.text()
    assert check.root_clearance_rss_mm > 0.0, check.text()
    clearance = dt_mesh_checks.t006_relief_clearance_mm()
    assert clearance >= T006_RELIEF_CLEARANCE_MIN_MM, f"T006 relief clearance {clearance:.4f} mm"


def test_t006_relief_centre_lies_inside_its_rss_centre_range() -> None:
    """The relief is ground for a centre the T006 mesh actually reaches."""
    centre = cone_set_stack.cone_centre(6)
    closed = centre.mean_mm - centre.rss_half_range_mm - cone_set_stack.standard_centre_mm(6)
    assert cone.CUSTOM_SIX_RELIEF_CENTRE_ABOVE_STANDARD_MM <= closed


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
# face, from the direct 3D evaluation recorded on #2481 (v3 comment,
# issue_margin_v3.py, "lean check": as-cut straight spaces against the 16T
# with the 64T slid to the axes' common perpendicular, ideal involutes, less
# the same run with the retired screw form and less the thickening).
STRAIGHT_TOOTH_LEAN_3D_MM = (0.0153, 0.0000, 0.0137, 0.0255, 0.0366)


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
