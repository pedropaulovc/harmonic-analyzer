"""Rulings R9-48 and R9-49: the MHA-176 guide-lock screw joint at the worst case.

Each test recomputes the worst-case corner from the catalogue and the printed
bands, not from the specs' derived constants, then holds the spec to it; the
negative controls reload ``guide_lock_screw_spec`` with the old part and show
its import-time assert refuses it.
"""

from __future__ import annotations

import importlib.util
import re
from dataclasses import replace

import pytest

import guide_lock_screw_spec as screw
import guide_lock_spec as lock
import platen_guide_spec as guide
import transgear_pivot_spacer_spec as spacer
from _hole_spec import HoleSpec, blind_cut_dia_mm

IN = 25.4
# #4-40 UNC (ASME B1.1): basic major (the class-3A max) and the class-2A min.
MAJOR_MAX = 0.112 * IN
MAJOR_MIN = 0.1061 * IN
PITCH = IN / 40.0
# Title block: 3-place linear +/-0.13; drilled holes +0.10/-0; edge break 0.25.
THREE_PLACE = 0.13
DRILLED_PLUS = 0.10
EDGE_BREAK = 0.25


def _reload_screw_spec() -> None:
    spec = importlib.util.spec_from_file_location(
        "_guide_lock_screw_spec_perturbed", screw.__file__
    )
    fresh = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fresh)


def test_lock_screw_engages_1_5d_in_the_guide_at_the_worst_case() -> None:
    """R9-48: the shortest 3/8 screw (B18.6.3 +0/-0.03 in) under the thickest
    2.000 strip, less one pitch for the first thread and the tap mouth's
    break, in the guide's through tap."""
    length_min = 0.375 * IN - 0.03 * IN
    strip_max = 2.0 + THREE_PLACE
    worst = length_min - strip_max - PITCH - EDGE_BREAK
    assert worst == pytest.approx(5.748, abs=1e-3)
    assert worst / MAJOR_MAX == pytest.approx(2.02, abs=5e-3)
    assert worst >= 1.5 * MAJOR_MAX
    assert screw.SHANK_LEN == pytest.approx(0.375 * IN)
    assert screw.ENGAGEMENT_WORST == pytest.approx(worst)


def test_the_quarter_inch_screw_is_refused(monkeypatch) -> None:
    from diagnostics import diag_build_91255A108 as recipe

    monkeypatch.setattr(recipe, "DIMS", replace(recipe.DIMS, length=0.25 * IN))
    with pytest.raises(AssertionError, match="MHA-176 guide-lock screw"):
        _reload_screw_spec()


def test_lock_and_guide_hole_positions_fit_the_fixed_fastener_stack() -> None:
    """R9-49: H - F >= the lock's 2X Ø0.10 plus the guide's Ø0.20, with the
    1/8 drill at its smallest and the screw major at its largest."""
    hole_min = 0.125 * IN
    positions = float(lock.GEOMETRIC_TOLERANCES_MM["screw-hole position"]) + float(
        guide.GEOMETRIC_TOLERANCES_MM["guide hole-pattern position"]
    )
    # The printed bands, untightened.
    assert positions == pytest.approx(0.30)
    assert blind_cut_dia_mm(lock.HOLE_SPEC) == pytest.approx(hole_min)
    assert hole_min - MAJOR_MAX >= positions
    # Pushed off the bar onto the screws, the lock gains at least the radial
    # clearance less the position error, and at most the loosest clearance
    # plus it.
    set_min = (hole_min - MAJOR_MAX) / 2.0 - positions / 2.0
    set_max = (hole_min + DRILLED_PLUS - MAJOR_MIN) / 2.0 + positions / 2.0
    assert set_min == pytest.approx(0.0151, abs=1e-4)
    assert set_max == pytest.approx(0.4400, abs=1e-4)
    assert screw.LOCK_SET_OFFSET == pytest.approx((set_min, set_max))


def test_the_close_number_4_clearance_is_refused(monkeypatch) -> None:
    monkeypatch.setattr(lock, "HOLE_SPEC", HoleSpec("clearance", "#4", fit="close"))
    with pytest.raises(AssertionError, match="MHA-112 guide lock"):
        _reload_screw_spec()


def test_set_locks_clear_the_pivot_spacer_in_the_sweep(monkeypatch) -> None:
    """The lock-station sweep reads the as-set window: each lock's spacer-side
    edge recedes by the least set offset, so the spacer gap grows by it."""
    import build_paper_drive_assembly as assembly

    hole_min = 0.125 * IN
    set_min = (hole_min - MAJOR_MAX) / 2.0 - (0.10 + 0.20) / 2.0
    spacer_r = (spacer.OD + spacer.OD_BAND) / 2.0
    pivot_y = assembly.PIVOT_XY[1]
    (_, bottom_top), (top_bottom, _) = assembly.LOCK_PLATE_Y
    gap = min(
        pivot_y - spacer_r - (bottom_top - set_min),
        (top_bottom + set_min) - (pivot_y + spacer_r),
    )
    assert gap >= assembly.LOCK_SWEEP_FLOOR
    lines: list[str] = []
    monkeypatch.setattr(assembly, "log", lines.append)
    assembly._assert_lock_station_sweep()
    (line,) = lines
    reported = float(re.search(r"pivot spacer (-?\d+\.\d+)", line).group(1))
    assert reported == pytest.approx(gap, abs=1e-3)


def test_sweep_refuses_a_lock_set_toward_the_spacer(monkeypatch) -> None:
    import build_paper_drive_assembly as assembly

    lo, hi = assembly.LOCK_SET_OFFSET
    # A lock left 0.10 nearer the spacer than the model (the screw float the
    # bias-set step removes) runs under the sweep floor.
    monkeypatch.setattr(assembly, "LOCK_SET_OFFSET", (-0.10, hi))
    monkeypatch.setattr(assembly, "log", lambda *_a: None)
    with pytest.raises(AssertionError, match="pivot spacer"):
        assembly._assert_lock_station_sweep()
    assert lo >= 0.0
