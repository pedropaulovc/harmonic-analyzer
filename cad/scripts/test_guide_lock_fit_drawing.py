"""Rulings R9-48 and R9-49: the MHA-176 guide-lock screw joint at the worst case.

Each test recomputes the worst-case corner from the catalogue and the printed
bands, not from the specs' derived constants, then holds the spec to it; the
negative controls reload ``guide_lock_screw_spec`` with the old part and show
its import-time assert refuses it.
"""

from __future__ import annotations

import importlib.util
import itertools
import math
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
    """R9-49: the hole-over-screw radial clearance covers the radial reach of
    the lock's ±0.035 hole coordinates plus half the guide's Ø0.20, with the
    1/8 drill at its smallest and the screw major at its largest."""
    hole_min = 0.125 * IN
    radial = (0.035**2 + 0.035**2) ** 0.5 + 0.20 / 2.0
    # The printed bands, untightened.
    assert lock.HOLE_LOCATION_BAND == pytest.approx(0.035)
    assert float(
        guide.GEOMETRIC_TOLERANCES_MM["guide hole-pattern position"]
    ) == pytest.approx(0.20)
    assert blind_cut_dia_mm(lock.HOLE_SPEC) == pytest.approx(hole_min)
    assert (hole_min - MAJOR_MAX) / 2.0 >= radial
    # Pushed off the bar onto the screws, the lock gains at least the radial
    # clearance less the position error, and at most the loosest clearance
    # plus it.
    set_min = (hole_min - MAJOR_MAX) / 2.0 - radial
    set_max = (hole_min + DRILLED_PLUS - MAJOR_MIN) / 2.0 + radial
    assert set_min == pytest.approx(0.0156, abs=1e-4)
    assert set_max == pytest.approx(0.4395, abs=1e-4)
    assert screw.LOCK_SET_OFFSET == pytest.approx((set_min, set_max))


def test_the_hole_coordinates_at_the_arm_tap_band_are_refused(monkeypatch) -> None:
    """±0.065 (the hanger arm's tap band) reaches 0.092 radially: the lock's
    holes could then bear on their screws toward the bar."""
    monkeypatch.setattr(lock, "HOLE_LOCATION_BAND", 0.065)
    with pytest.raises(AssertionError, match="MHA-112 guide lock"):
        _reload_screw_spec()


def test_the_close_number_4_clearance_is_refused(monkeypatch) -> None:
    monkeypatch.setattr(lock, "HOLE_SPEC", HoleSpec("clearance", "#4", fit="close"))
    with pytest.raises(AssertionError, match="MHA-112 guide lock"):
        _reload_screw_spec()


# R9-61 corners, recomputed from the catalogue and the printed bands.
_HOLE_MIN = 0.125 * IN
_CLEARANCE_MIN = (_HOLE_MIN - MAJOR_MAX) / 2.0
_CLEARANCE_MAX = (_HOLE_MIN + DRILLED_PLUS - MAJOR_MIN) / 2.0
_POSITION = (2 * 0.035**2) ** 0.5 + 0.20 / 2.0
_SET_MIN = _CLEARANCE_MIN - _POSITION
_SET_MAX = _CLEARANCE_MAX + _POSITION
# Holes at x 4 and 18 (±0.035) from the left edge of the 22 (.X ±0.8) plate,
# y 3.5 from its guide-side edge; R9-61's 15.65 height, +0/-0.50.
_HOLE_X = (4.0, 18.0)
_HOLE_Y = 3.5
_HEIGHT = 15.65
# Old (R9-59) model: a set plate only translates, so its far edge recedes.
_OLD_FAR_REACH = -_SET_MIN


def _set_plate_reach(e1, e2, w1, w2, c1, c2, width):
    """(far, guide side): how far a set plate's far edge stands toward the
    bar, and its guide-side edge away from it, beyond the model. Frictionless
    contact: each hole (lock-frame error ``e``) bears on its screw (tap error
    ``w``, radial clearance ``c``) on the bar side, and the push at the
    plate's middle settles it where the two holes' gains sum largest."""
    a1, a2 = e1[0] - w1[0], e2[0] - w2[0]
    lo, hi = max(-c1 - a1, -c2 - a2), min(c1 - a1, c2 - a2)

    def gain(c: float, h: float) -> float:
        return math.sqrt(max(c * c - h * h, 0.0))

    def bearing(t: float) -> float:
        return gain(c1, t + a1) + gain(c2, t + a2)

    for _ in range(80):
        m1, m2 = lo + (hi - lo) / 3.0, hi - (hi - lo) / 3.0
        if bearing(m1) < bearing(m2):
            lo = m1
        else:
            hi = m2
    t = (lo + hi) / 2.0
    world = [
        (x + w[0] + t + a, _HOLE_Y + w[1] - gain(c, t + a))
        for x, w, c, a in ((_HOLE_X[0], w1, c1, a1), (_HOLE_X[1], w2, c2, a2))
    ]
    local = [
        (_HOLE_X[0] + e1[0], _HOLE_Y + e1[1]),
        (_HOLE_X[1] + e2[0], _HOLE_Y + e2[1]),
    ]
    turn = math.atan2(world[1][1] - world[0][1], world[1][0] - world[0][0])
    turn -= math.atan2(local[1][1] - local[0][1], local[1][0] - local[0][0])

    def y_of(x: float, y: float) -> float:
        dx, dy = x - local[0][0], y - local[0][1]
        return world[0][1] + math.sin(turn) * dx + math.cos(turn) * dy

    corners = (0.0, width)
    return (
        max(y_of(x, _HEIGHT) for x in corners) - _HEIGHT,
        -min(y_of(x, 0.0) for x in corners),
    )


def test_a_set_plate_skews_at_the_reviewed_hole_errors() -> None:
    """Review of 8689c2a0d: opposite hole-position errors (lock ±0.035, guide
    tap ±0.0999) on the tightest holes skew the set plate about 1.104°, and
    its far corner comes 0.04458 toward the spacer instead of receding."""
    reach = _set_plate_reach(
        (0.0, 0.035), (0.0, -0.035), (0.0, -0.0999), (0.0, 0.0999),
        _CLEARANCE_MIN, _CLEARANCE_MIN, 22.0,
    )  # fmt: skip
    assert reach[0] == pytest.approx(0.04458, abs=3e-4)
    assert reach[0] > _OLD_FAR_REACH
    assert screw.LOCK_SET_EDGE_REACH[0] >= reach[0]


def test_a_set_plate_skews_further_on_unequal_hole_clearances() -> None:
    """R9-61: each hole's clearance is its own drill and screw, so one hole
    can bear at the least set gain and the other at the most. The skew then
    swings the far corner over the longest overhang (22.8 wide) further toward
    the spacer than position errors alone do."""
    reach = _set_plate_reach(
        (0.035, 0.035), (-0.035, -0.035), (0.0, -0.1), (0.0, 0.1),
        _CLEARANCE_MAX, _CLEARANCE_MIN, 22.8,
    )  # fmt: skip
    assert reach[0] == pytest.approx(0.1034, abs=5e-4)
    # The spec's closed form: the gain window over the shortest pitch, times
    # the longest overhang, less the least gain.
    overhang = 22.8 - _HOLE_X[1] + 0.035
    skew = (_SET_MAX - _SET_MIN) / (_HOLE_X[1] - _HOLE_X[0] - 0.07)
    assert screw.LOCK_SET_EDGE_REACH == pytest.approx(
        (overhang * skew - _SET_MIN, _SET_MAX + overhang * skew)
    )
    assert reach[0] <= screw.LOCK_SET_EDGE_REACH[0]


def test_the_set_plate_envelope_bounds_every_corner_of_the_bands() -> None:
    """Every combination of hole-coordinate extremes, tap errors on the
    Ø0.20 circle, clearance extremes and plate width stays inside the
    envelope the sweep reads, on both long edges."""
    taps = [
        (0.1 * math.cos(k * math.pi / 4.0), 0.1 * math.sin(k * math.pi / 4.0))
        for k in range(8)
    ]
    clearances = (_CLEARANCE_MIN, _CLEARANCE_MAX)
    far = guide_side = -math.inf
    for e in itertools.product((-0.035, 0.035), repeat=4):
        for w1, w2, c1, c2, width in itertools.product(
            taps, taps, clearances, clearances, (22.0 - 0.8, 22.0 + 0.8)
        ):
            reach = _set_plate_reach(e[:2], e[2:], w1, w2, c1, c2, width)
            far, guide_side = max(far, reach[0]), max(guide_side, reach[1])
    assert far <= screw.LOCK_SET_EDGE_REACH[0]
    assert guide_side <= screw.LOCK_SET_EDGE_REACH[1]
    # The old translation-only window misses both.
    assert far > _OLD_FAR_REACH and guide_side > _SET_MAX


def _spacer_gap(monkeypatch, assembly) -> float:
    lines: list[str] = []
    monkeypatch.setattr(assembly, "log", lines.append)
    assembly._assert_lock_station_sweep()
    (line,) = lines
    return float(re.search(r"pivot spacer (-?\d+\.\d+)", line).group(1))


def test_set_locks_clear_the_pivot_spacer_in_the_sweep(monkeypatch) -> None:
    """R9-61: the bar prints the pivot tap ±0.065, and each set plate's far
    edge stands its skewed reach toward the bar; the 15.65 plate keeps the
    floor through both.  R9-71: the spacer is pressed on the shoulder, so its
    O.D. no longer floats off the screw axis (it took 0.14645 on the old
    Ø5.030 bore over the Ø4.7371 shoulder)."""
    import build_paper_drive_assembly as assembly

    assert spacer.BORE_DIA_MAX < (0.1875 - 0.001) * IN
    spacer_r = (spacer.OD + spacer.OD_BAND) / 2.0 + 0.065
    far_reach = (22.8 - _HOLE_X[1] + 0.035) * (_SET_MAX - _SET_MIN) / 13.93 - _SET_MIN
    pivot_y = assembly.PIVOT_XY[1]
    bottom_rail, top_rail = assembly.GUIDE_Y
    bottom_far = bottom_rail - 1.0 + _HEIGHT
    top_far = top_rail + 5.0 + 1.0 - _HEIGHT
    gap = min(
        pivot_y - spacer_r - (bottom_far + far_reach),
        (top_far - far_reach) - (pivot_y + spacer_r),
    )
    assert gap == pytest.approx(0.142 + 0.14645, abs=1e-3)
    assert gap >= assembly.LOCK_SWEEP_FLOOR
    assert _spacer_gap(monkeypatch, assembly) == pytest.approx(gap, abs=1e-3)
    # The 16-high plate the old model passed still runs into the spacer.
    monkeypatch.setattr(
        assembly,
        "LOCK_PLATE_Y",
        (
            (bottom_rail - 1.0, bottom_rail - 1.0 + 16.0),
            (top_rail + 6.0 - 16.0, top_rail + 6.0),
        ),
    )
    with pytest.raises(AssertionError, match="pivot spacer"):
        assembly._assert_lock_station_sweep()


def test_the_bar_pivot_tap_band_moves_the_spacer_in_the_sweep(monkeypatch) -> None:
    """R9-61: the spacer hangs on the bar's pivot tap, so each 0.01 of the
    tap's printed position band costs 0.01 of the spacer gap, and a band
    wider than the gap's margin is refused."""
    import build_paper_drive_assembly as assembly
    import support_bar_spec as bar

    gap = _spacer_gap(monkeypatch, assembly)
    monkeypatch.setattr(bar, "HOLE_POSITION_BAND", bar.HOLE_POSITION_BAND + 0.01)
    assert _spacer_gap(monkeypatch, assembly) == pytest.approx(gap - 0.01, abs=2e-3)
    monkeypatch.setattr(
        bar,
        "HOLE_POSITION_BAND",
        bar.HOLE_POSITION_BAND + (gap - assembly.LOCK_SWEEP_FLOOR) + 0.01,
    )
    with pytest.raises(AssertionError, match="pivot spacer"):
        assembly._assert_lock_station_sweep()


def test_sweep_refuses_a_lock_set_toward_the_spacer(monkeypatch) -> None:
    import build_paper_drive_assembly as assembly

    far, guide_side = assembly.LOCK_SET_EDGE_REACH
    # A far edge reaching 0.01 past the spacer gap's margin over the sweep
    # floor runs under it.
    margin = _spacer_gap(monkeypatch, assembly) - assembly.LOCK_SWEEP_FLOOR
    monkeypatch.setattr(
        assembly, "LOCK_SET_EDGE_REACH", (far + margin + 0.01, guide_side)
    )
    monkeypatch.setattr(assembly, "log", lambda *_a: None)
    with pytest.raises(AssertionError, match="pivot spacer"):
        assembly._assert_lock_station_sweep()
