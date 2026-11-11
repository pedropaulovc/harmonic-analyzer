"""The crank mesh's print-worst free play, sampled in 3D, gates the 64T's
mesh thinning (#2481): no binding at the title block's +/-1 deg on the tooth
line, the crossing band and the axis tilts, in both tooth models."""
from __future__ import annotations

import pytest

import crank_mesh_free_play as free_play
import dt_crank_drive_gear_spec as gear64


@pytest.mark.parametrize("forms", free_play.FORMS)
def test_print_worst_corner_keeps_the_margin(forms: str) -> None:
    worst = free_play.print_worst_mm(forms)
    assert worst >= free_play.MARGIN_MM > 0.0, f"{forms}: print-worst free play {worst:+.4f} mm"


def test_mesh_thinning_is_the_least_step_that_keeps_the_margin() -> None:
    """Re-derived on every run: one step less thinning leaves less than the
    margin in some tooth model, so a pitch, centre or face change that needs
    less (or more) fails here with the value to set."""
    thinner = gear64.MESH_THINNING_MM - gear64.MESH_THINNING_STEP_MM
    corners = gear64.profile_corners(gear64.tooth_band(thinner))
    worst = min(free_play.print_worst_mm(forms, corners) for forms in free_play.FORMS)
    assert worst < free_play.MARGIN_MM, (
        f"{thinner:.3f} mm thinning already leaves {worst:+.4f} mm: lower gear64_mesh_thinning_mm"
    )


def test_axis_tilt_terms_come_from_the_stack() -> None:
    assert free_play.AXIS_TILT_DEG == pytest.approx(sum(free_play.AXIS_TILT_TERMS_DEG.values()))
    assert all(value > 0.0 for value in free_play.AXIS_TILT_TERMS_DEG.values())
