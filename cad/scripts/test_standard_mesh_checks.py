"""Closed-form standard checks of every drive-train mesh, from spec values.

Cone family (user ruling 2026-10-10; centre set at assembly on T120,
cone_set_stack): nominal contact ratio >= 1.0 at the running mean centre,
and no binding, positive root clearance and no involute interference at the
RSS corner. The RSS contact ratio and the arithmetic worst-corner
interference are reported only. The crank pair's open-corner figure is a
reference, as main printed it (dt_crank_drive_gear_notes, user ruling
2026-09-30).

Named exceptions:
* T006 (user ruling 2026-10-10): no full-depth six-tooth form reaches a
  contact ratio of 1 against the shared 20 deg drum. It is gated for a ground
  relief at least 10 um clear of every drum-tip corner's path over its RSS
  centre range and at least 0.02 backlash at the closing corner; its contact
  ratio is reported.
* The alignment pinion is a fit-up mesh: its contact ratio is reported, not
  gated (tolerances.yaml gear_tip note).
"""
from __future__ import annotations

import pytest

import alignment_mesh_check
import cone_set_stack
import crank_mesh_stack
import dt_cone_gear_spec as cone
import dt_mesh_checks

EXEMPT_CONE_TEETH = frozenset({6})
CONE_TEETH = tuple(t for t in cone.CONFIGURATION_TEETH if t not in EXEMPT_CONE_TEETH)
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
