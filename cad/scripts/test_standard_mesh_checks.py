"""Closed-form standard checks of every drive-train mesh, from spec values.

Gates, at every printed tip/thickness corner over the booked centre range:
no binding (positive backlash at the closing corner), positive root clearance,
no involute interference, and a contact ratio of at least 1 at the nominal
centre. The open-corner contact ratio is a reference figure, as main printed
it for the crank pair (dt_crank_drive_gear_notes, user ruling 2026-09-30).

Named exceptions:
* T006 is below any full-depth count against the 120T drum; its DT6-FORM1
  form cannot be cut deeper (adjacent gaps meet), so the native assembly
  interference/soundness gate at the operating pose governs it alone.
* The alignment pinion is a fit-up mesh: its contact ratio is reported, not
  gated (tolerances.yaml gear_tip note).
"""
from __future__ import annotations

import pytest

import crank_mesh_stack
import dt_cone_gear_spec as cone
import dt_mesh_checks

EXEMPT_CONE_TEETH = frozenset({6})
CONE_TEETH = tuple(t for t in cone.CONFIGURATION_TEETH if t not in EXEMPT_CONE_TEETH)


def _require_no_bind(check) -> None:
    assert check.backlash_min_mm > 0.0, check.text()
    assert check.root_clearance_min_mm > 0.0, check.text()
    assert check.interference_margin_min_mm >= 0.0, check.text()


@pytest.mark.parametrize("teeth", CONE_TEETH)
def test_cone_drum_mesh_passes_the_standard_checks(teeth: int) -> None:
    check = dt_mesh_checks.cone_check(teeth)
    _require_no_bind(check)
    assert check.contact_ratio_nominal >= 1.0, check.text()


def test_alignment_drum_fitup_mesh_cannot_bind() -> None:
    _require_no_bind(dt_mesh_checks.alignment_check())


def test_crossed_crank_mesh_passes_the_standard_checks() -> None:
    check = crank_mesh_stack.standard_check()
    _require_no_bind(check)
    assert check.contact_ratio_nominal >= 1.0, check.text()
