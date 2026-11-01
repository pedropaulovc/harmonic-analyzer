"""Rulings R9-48 and R9-49: the MHA-PD-VN-60 guide-lock screw joint at the worst case.

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

import pytest

import pd_vn_guide_lock_screw_spec as screw
import pd_guide_lock_spec as lock
import pd_platen_guide_spec as guide
import pd_transgear_pivot_spacer_spec as spacer
from _hole_spec import HoleSpec, blind_cut_dia_mm
from _printed_tolerance import (
    drilled_oversize_mm,
    edge_break_chamfer_mm,
    printed_band_mm,
    printed_deviations,
)

IN = 25.4
# #4-40 UNC (ASME B1.1): the basic major (above the class-2A max) and the class-2A min.
MAJOR_MAX = 0.112 * IN
MAJOR_MIN = 0.1061 * IN
PITCH = IN / 40.0
# Inch title block (#290): drilled holes +.004/-0; edge break .010.
DRILLED_PLUS = drilled_oversize_mm(unit="in")
EDGE_BREAK = edge_break_chamfer_mm(unit="in")
# The lock: 1/16 in sheet as supplied, +/-0.005 in (McMaster 1388K196).
SHEET_MAX = (1.0 / 16.0 + 0.005) * IN
# The lock's ±.001 hole coordinates; the guide taps' Ø.008 position zone.
LOCK_BAND = 0.001 * IN
GUIDE_ZONE = 0.008 * IN


def _reload_screw_spec() -> None:
    spec = importlib.util.spec_from_file_location(
        "_guide_lock_screw_spec_perturbed", screw.__file__
    )
    fresh = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fresh)


def test_lock_screw_engages_1_5d_in_the_guide_at_the_worst_case() -> None:
    """R9-48: the shortest 3/8 screw (B18.6.3 +0/-0.03 in) through the
    thickest 1/16 sheet, less one pitch for the first thread and the tap
    mouth's break, in the guide's through tap."""
    length_min = 0.375 * IN - 0.03 * IN
    worst = length_min - SHEET_MAX - PITCH - EDGE_BREAK
    assert worst == pytest.approx(6.1595, abs=1e-3)
    assert worst / MAJOR_MAX == pytest.approx(2.165, abs=1e-3)
    assert worst >= 1.5 * MAJOR_MAX
    assert screw.SHANK_LEN == pytest.approx(0.375 * IN)
    assert screw.ENGAGEMENT_WORST == pytest.approx(worst)


def test_the_quarter_inch_screw_is_refused(monkeypatch) -> None:
    import _mcmaster_91792a108 as recipe

    size = list(recipe.PAN_HEAD_SIZE)
    size[1] = 0.25 * IN
    monkeypatch.setattr(recipe, "PAN_HEAD_SIZE", tuple(size))
    with pytest.raises(AssertionError, match="MHA-PD-VN-60 guide-lock screw"):
        _reload_screw_spec()


def test_lock_and_guide_hole_positions_fit_the_fixed_fastener_stack() -> None:
    """R9-49: the hole-over-screw radial clearance covers the radial reach of
    the lock's ±.001 hole coordinates plus half the guide's Ø.008, with the
    1/8 drill at its smallest and the screw major at its largest."""
    hole_min = 0.125 * IN
    radial = (2.0 * LOCK_BAND**2) ** 0.5 + GUIDE_ZONE / 2.0
    # The printed bands, untightened.
    assert lock.HOLE_LOCATION_BAND == pytest.approx(LOCK_BAND)
    assert guide.GEOMETRIC_TOLERANCES_IN["guide hole-pattern position"] == ".008"
    assert blind_cut_dia_mm(lock.HOLE_SPEC) == pytest.approx(hole_min)
    assert (hole_min - MAJOR_MAX) / 2.0 >= radial
    # Pushed off the bar onto the screws, the lock gains at least the radial
    # clearance less the position error, and at most the loosest clearance
    # plus it.
    set_min = (hole_min - MAJOR_MAX) / 2.0 - radial
    set_max = (hole_min + DRILLED_PLUS - MAJOR_MIN) / 2.0 + radial
    assert set_min == pytest.approx(0.0276, abs=1e-4)
    assert set_max == pytest.approx(0.4284, abs=1e-4)
    assert screw.LOCK_SET_OFFSET == pytest.approx((set_min, set_max))


def test_the_hole_coordinates_at_the_arm_tap_band_are_refused(monkeypatch) -> None:
    """±0.065 (the hanger arm's tap band) reaches 0.092 radially: the lock's
    holes could then bear on their screws toward the bar."""
    monkeypatch.setattr(lock, "HOLE_LOCATION_BAND", 0.065)
    with pytest.raises(AssertionError, match="MHA-PD-12 guide lock"):
        _reload_screw_spec()


def test_the_close_number_4_clearance_is_refused(monkeypatch) -> None:
    monkeypatch.setattr(lock, "HOLE_SPEC", HoleSpec("clearance", "#4", fit="close"))
    with pytest.raises(AssertionError, match="MHA-PD-12 guide lock"):
        _reload_screw_spec()


# R9-61 corners, recomputed from the catalogue and the printed bands.
_HOLE_MIN = 0.125 * IN
_CLEARANCE_MIN = (_HOLE_MIN - MAJOR_MAX) / 2.0
_CLEARANCE_MAX = (_HOLE_MIN + DRILLED_PLUS - MAJOR_MIN) / 2.0
_POSITION = (2.0 * LOCK_BAND**2) ** 0.5 + GUIDE_ZONE / 2.0
_SET_MIN = _CLEARANCE_MIN - _POSITION
_SET_MAX = _CLEARANCE_MAX + _POSITION
# Holes at x .157 and .709 (±.001) from the left edge of the .89 (.XX ±.01)
# plate, y .155 from its guide-side edge, on the .29 rail's tap row .140 above
# its datum B (owner ruling 2026-11-01, B2): the plate laps .015 past the
# bottom rail's datum B and .005 past the top rail's top face; the .45 height
# at .XX. PR #1897 grew the plate so every hole wall reaches the wall target.
_HOLE_X = (0.157 * IN, 0.709 * IN)
_HOLE_Y = 0.155 * IN
_RAIL = 0.29 * IN
_TAP_Y = 0.140 * IN
_LIP_BOTTOM = _HOLE_Y - _TAP_Y
_LIP_TOP = _HOLE_Y - (_RAIL - _TAP_Y)
_WIDTH = 0.89 * IN
_HEIGHT = 0.45 * IN
_HEIGHT_BAND = _WIDTH_BAND = printed_band_mm(2, unit="in")
_TAP_R = GUIDE_ZONE / 2.0
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
    """Review of 8689c2a0d: opposite hole-position errors (lock band, guide
    tap just inside its zone) on the tightest holes skew the set plate, and
    its far corner comes toward the spacer (the skew's cosine draws a nearer
    far edge in less) instead of receding."""
    reach = _set_plate_reach(
        (0.0, LOCK_BAND), (0.0, -LOCK_BAND), (0.0, -0.999 * _TAP_R), (0.0, 0.999 * _TAP_R),
        _CLEARANCE_MIN, _CLEARANCE_MIN, _WIDTH,
    )  # fmt: skip
    assert reach[0] == pytest.approx(0.0440, abs=3e-4)
    assert reach[0] > _OLD_FAR_REACH
    assert screw.LOCK_SET_EDGE_REACH[0] >= reach[0]


def test_a_set_plate_skews_further_on_unequal_hole_clearances() -> None:
    """R9-61: each hole's clearance is its own drill and screw, so one hole
    can bear at the least set gain and the other at the most. The skew then
    swings the far corner over the longest overhang further toward the
    spacer than position errors alone do."""
    longest = _WIDTH + _WIDTH_BAND
    reach = _set_plate_reach(
        (LOCK_BAND, LOCK_BAND), (-LOCK_BAND, -LOCK_BAND), (0.0, -_TAP_R), (0.0, _TAP_R),
        _CLEARANCE_MAX, _CLEARANCE_MIN, longest,
    )  # fmt: skip
    assert reach[0] == pytest.approx(0.0928, abs=5e-4)
    # The spec's closed form: the gain window over the shortest pitch, times
    # the longest overhang, less the least gain.
    overhang = longest - _HOLE_X[1] + LOCK_BAND
    skew = (_SET_MAX - _SET_MIN) / (_HOLE_X[1] - _HOLE_X[0] - 2.0 * LOCK_BAND)
    assert screw.LOCK_SET_EDGE_REACH == pytest.approx(
        (overhang * skew - _SET_MIN, _SET_MAX + overhang * skew)
    )
    assert reach[0] <= screw.LOCK_SET_EDGE_REACH[0]


def test_the_set_plate_envelope_bounds_every_corner_of_the_bands() -> None:
    """Every combination of hole-coordinate extremes, tap errors on the
    Ø.008 circle, clearance extremes and plate width stays inside the
    envelope the sweep reads, on both long edges."""
    taps = [
        (_TAP_R * math.cos(k * math.pi / 4.0), _TAP_R * math.sin(k * math.pi / 4.0))
        for k in range(8)
    ]
    clearances = (_CLEARANCE_MIN, _CLEARANCE_MAX)
    far = guide_side = -math.inf
    for e in itertools.product((-LOCK_BAND, LOCK_BAND), repeat=4):
        for w1, w2, c1, c2, width in itertools.product(
            taps,
            taps,
            clearances,
            clearances,
            (_WIDTH - _WIDTH_BAND, _WIDTH + _WIDTH_BAND),
        ):
            reach = _set_plate_reach(e[:2], e[2:], w1, w2, c1, c2, width)
            far, guide_side = max(far, reach[0]), max(guide_side, reach[1])
    assert far <= screw.LOCK_SET_EDGE_REACH[0]
    assert guide_side <= screw.LOCK_SET_EDGE_REACH[1]
    # The old translation-only window misses both.
    assert far > _OLD_FAR_REACH and guide_side > _SET_MAX


def _sweep_gap(monkeypatch, assembly, label: str) -> float:
    lines: list[str] = []
    monkeypatch.setattr(assembly, "log", lines.append)
    assembly._assert_lock_station_sweep()
    (line,) = lines
    return float(re.search(rf"{label} (-?\d+\.\d+)", line).group(1))


def test_set_locks_clear_the_pivot_spacer_in_the_sweep(monkeypatch) -> None:
    """R9-61: the bar prints the pivot tap ±.002, and each set plate's far
    edge stands its skewed reach and its height band toward the bar. The
    .45 plate (user ruling 2026-10-11, grown with the .29 rails) keeps the spacer far off; the 15.65
    plate it replaced needed a +0/-0.50 band to pass it, and at the general
    bands runs into it. R9-71: the spacer is pressed on the shoulder, so its
    O.D. stands off the screw axis only by the bore offset its printed runout
    to A allows."""
    import build_pd_paper_drive_assembly as assembly
    import pd_support_bar_spec as bar

    assert spacer.BORE_DIA_MAX < (0.1875 - 0.001) * IN
    spacer_r = (
        (spacer.OD + spacer.OD_BAND) / 2.0
        + spacer.BORE_ECCENTRICITY
        + bar.HOLE_POSITION_BAND
    )
    pitch_min = _HOLE_X[1] - _HOLE_X[0] - 2.0 * LOCK_BAND
    far_reach = (_WIDTH + _WIDTH_BAND - _HOLE_X[1] + LOCK_BAND) * (
        _SET_MAX - _SET_MIN
    ) / pitch_min - _SET_MIN
    pivot_y = assembly.PIVOT_XY[1]
    bottom_rail, top_rail = assembly.GUIDE_Y

    def gap_at(height: float) -> float:
        bottom_far = bottom_rail - _LIP_BOTTOM + height + _HEIGHT_BAND
        top_far = top_rail + _RAIL + _LIP_TOP - height - _HEIGHT_BAND
        return min(
            pivot_y - spacer_r - (bottom_far + far_reach),
            (top_far - far_reach) - (pivot_y + spacer_r),
        )

    gap = gap_at(_HEIGHT)
    assert gap >= assembly.LOCK_SWEEP_FLOOR
    assert _sweep_gap(monkeypatch, assembly, "pivot spacer") == pytest.approx(
        gap, abs=1e-3
    )
    # The 15.65 plate at the same band runs into the spacer.
    assert gap_at(15.65) < assembly.LOCK_SWEEP_FLOOR
    monkeypatch.setattr(
        assembly,
        "LOCK_PLATE_Y",
        (
            (bottom_rail - 1.0, bottom_rail - 1.0 + 15.65),
            (top_rail + 6.0 - 15.65, top_rail + 6.0),
        ),
    )
    with pytest.raises(AssertionError, match="sweep into the pivot spacer"):
        assembly._assert_lock_station_sweep()


def test_the_bar_pivot_tap_band_moves_the_spacer_in_the_sweep(monkeypatch) -> None:
    """R9-61: the spacer hangs on the bar's pivot tap, so each 0.01 of the
    tap's printed position band costs 0.01 of the spacer gap."""
    import build_pd_paper_drive_assembly as assembly
    import pd_support_bar_spec as bar

    gap = _sweep_gap(monkeypatch, assembly, "pivot spacer")
    monkeypatch.setattr(bar, "HOLE_POSITION_BAND", bar.HOLE_POSITION_BAND + 0.01)
    assert _sweep_gap(monkeypatch, assembly, "pivot spacer") == pytest.approx(
        gap - 0.01, abs=2e-3
    )


def test_sweep_refuses_a_lock_set_toward_the_latch_hook(monkeypatch) -> None:
    """With the spacer far off, the latch hook's base is the nearest part a
    bottom plate's far edge moves toward.  The Ø11.0 spacer now stands nearer
    than the hook (3.79 against 5.38), so the spacer is held at its old
    Ø8.6, with no runout offset, here to isolate the hook's refusal."""
    import build_pd_paper_drive_assembly as assembly

    monkeypatch.setattr(spacer, "OD", 8.6)
    monkeypatch.setattr(spacer, "OD_BAND", 0.13)
    monkeypatch.setattr(spacer, "BORE_ECCENTRICITY", 0.0)

    far, guide_side = assembly.LOCK_SET_EDGE_REACH
    # A far edge reaching 0.01 past the hook gap's margin over the sweep
    # floor runs into it.
    margin = (
        _sweep_gap(monkeypatch, assembly, "latch hook base and ear")
        - assembly.LOCK_SWEEP_FLOOR
    )
    assert margin < _sweep_gap(monkeypatch, assembly, "pivot spacer") - 0.1
    monkeypatch.setattr(
        assembly, "LOCK_SET_EDGE_REACH", (far + margin + 0.01, guide_side)
    )
    monkeypatch.setattr(assembly, "log", lambda *_a: None)
    with pytest.raises(AssertionError, match="latch hook base and ear"):
        assembly._assert_lock_station_sweep()


def _retention(monkeypatch, assembly) -> dict[str, float]:
    lines: list[str] = []
    monkeypatch.setattr(assembly, "log", lines.append)
    assembly._assert_lock_retention()
    (line,) = lines
    return {
        key: float(re.search(rf"{pattern} (-?\d+\.\d+)", line).group(1))
        for key, pattern in (
            ("clearance", "bottom rail under the bar"),
            ("bottom", r"bottom plates \(hanging\) overlap"),
            ("top", r"top plates \(lifted\) overlap"),
        )
    }


def test_one_lock_size_retains_the_platen_on_both_rails(monkeypatch) -> None:
    """User ruling 2026-10-11: the bar runs a clearance over the bottom rail and
    one plate size serves both rails. At the printed worst case (bar 1.010
    at .XXX, rail heights .29 at .XX, plate height .45 at .XX, the set
    plate's guide-side reach) the bottom rail still clears the bar and each
    set plate still overlaps it, the top plates with the platen lifted until
    its bottom rail meets the bar."""
    import build_pd_paper_drive_assembly as assembly
    import pd_support_bar_spec as bar

    bar_height = 1.010 * IN
    assert bar.BAR_HEIGHT == pytest.approx(bar_height)
    bar_band = bar.BAR_HEIGHT_BAND
    rail_low, rail_high = printed_deviations(_RAIL, 2, unit="in")
    height_low, _ = printed_deviations(_HEIGHT, 2, unit="in")
    assert assembly._LOCK_HEIGHT_DEV == pytest.approx((height_low, -height_low))
    bottom_rail, top_rail = assembly.GUIDE_Y
    bar_bottom = top_rail - bar_height
    gap = bar_bottom - (bottom_rail + _RAIL)
    assert gap == pytest.approx(0.98)
    reach = assembly.LOCK_SET_EDGE_REACH[1] - height_low
    lift = gap + bar_band - rail_low
    bottom_plate = (bottom_rail - _LIP_BOTTOM, bottom_rail - _LIP_BOTTOM + _HEIGHT)
    top_plate = (top_rail + _RAIL + _LIP_TOP - _HEIGHT, top_rail + _RAIL + _LIP_TOP)
    assert [y for plate in assembly.LOCK_PLATE_Y for y in plate] == pytest.approx(
        [*bottom_plate, *top_plate]
    )
    expected = {
        "clearance": gap - bar_band - rail_high,
        "bottom": bottom_plate[1] - reach - (bar_bottom + bar_band),
        "top": top_rail - top_plate[0] - reach - lift,
    }
    assert _retention(monkeypatch, assembly) == pytest.approx(expected, abs=1e-3)
    assert min(expected.values()) >= assembly.LOCK_SWEEP_FLOOR
    # Top plates just short of the retention floor lose the lifted platen's
    # top rail.
    short = expected["top"] - assembly.LOCK_RETENTION_FLOOR + 0.01
    monkeypatch.setattr(
        assembly,
        "LOCK_PLATE_Y",
        (bottom_plate, (top_plate[0] + short, top_plate[1])),
    )
    with pytest.raises(AssertionError, match="top plates"):
        assembly._assert_lock_retention()
