"""Worst-case contracts of the transgear knob stack (R9-52, R9-53, R9-54).

The MHA-PD-008 knob shaft's #8-32 stud and D-core, the MHA-PD-022 drive
collar's matching D-bore and rear-face clamp reaction on actual gear face F,
and the MHA-PD-013 thumbnut, each pair judged at the printed worst case
(policy rule 12). Every corner is recomputed from printed values and places,
not read back from derived constants; reloads prove the refusal guards.
"""

from __future__ import annotations

import importlib.util
import math

import pytest

import pd_transgear_drive_collar_spec as collar
import pd_transgear_knob_shaft_spec as shaft
import pd_transgear_removable_spec as removable
import pd_transgear_thumbnut_spec as nut
from _printed_tolerance import angular_band_deg, printed_band_mm

INCH = 25.4
PITCH = INCH / 32.0
# ASME B1.1 #8-32 UNC limits as tabled by Engineers Edge and ITP Bolt:
# https://www.engineersedge.com/screw_threads_chart.htm
# https://itpbolt.com/wp-content/uploads/2015/08/Class-2B-Internal-Threads.pdf
MAJOR_2A = (0.1571 * INCH, 0.1631 * INCH)
PD_2A_MIN = 0.1399 * INCH
MINOR_2B_MIN = 0.130 * INCH
# The shared tap/native-thread registry carries the basic major rounded to mm.
BASIC_MAJOR = 4.166
# The deepest root a die cuts: a basic half-depth under the smallest 2A pitch
# diameter (the assumption crank_handle_pivot_screw_spec makes for #4-40).
ROOT_2A_MIN = PD_2A_MIN - 0.649519 * PITCH
ENGAGEMENT_FLOOR = 1.5 * BASIC_MAJOR


def _limits(value: float, places: int) -> tuple[float, float]:
    band = printed_band_mm(places)
    return value - band, value + band


def _stud_places(name: str) -> int:
    return shaft.DRAWING_PRECISION["StudProfile"][name]


def _reloaded_collar(monkeypatch, module, name: str, value):
    """A fresh execution of the collar spec with one upstream value patched."""
    monkeypatch.setattr(module, name, value)
    fresh_spec = importlib.util.spec_from_file_location(
        "_drive_collar_perturbed", collar.__file__
    )
    fresh = importlib.util.module_from_spec(fresh_spec)
    fresh_spec.loader.exec_module(fresh)
    return fresh


def _reloaded_nut(monkeypatch, included_angle_band: float):
    # Perturb the nut's angular row only; the collar's own break angle reads
    # the same title-block helper and must keep the real row when reloaded.
    with pytest.MonkeyPatch.context() as local:
        local.setattr(
            "_printed_tolerance.angular_band_deg", lambda: included_angle_band
        )
        fresh_spec = importlib.util.spec_from_file_location(
            "_thumbnut_perturbed", nut.__file__
        )
        fresh = importlib.util.module_from_spec(fresh_spec)
        fresh_spec.loader.exec_module(fresh)
    return fresh


def test_true_d_fit_clears_the_core_and_round_stud_at_printed_limits(
    monkeypatch,
) -> None:
    core = tuple(shaft.CORE_DIA + delta for delta in sorted(shaft.CORE_DIA_BAND))
    bore = tuple(collar.BORE_DIA + delta for delta in sorted(collar.BORE_DIA_BAND))
    core_flat = tuple(
        shaft.CORE_FLAT_FROM_AXIS + delta for delta in sorted(shaft.CORE_FLAT_BAND)
    )
    bore_flat = tuple(
        collar.FLAT_TO_AXIS + delta for delta in sorted(collar.FLAT_BAND)
    )
    curved_air = (bore[0] - core[1], bore[1] - core[0])
    flat_air = (bore_flat[0] - core_flat[1], bore_flat[1] - core_flat[0])
    assert core == pytest.approx((4.892, 4.900))
    assert curved_air == pytest.approx((0.010, 0.030))
    assert flat_air == pytest.approx((0.020, 0.050))
    stud_max = shaft.THREAD_BLANK_DIA + max(shaft.THREAD_BLANK_DIA_BAND)
    stud_air = min(bore[0] / 2.0, bore_flat[0]) - stud_max / 2.0
    assert stud_air == pytest.approx(0.110)
    assert collar.STUD_D_BORE_AIR == pytest.approx(stud_air)
    with monkeypatch.context() as patch:
        with pytest.raises(AssertionError, match="the D-flat binds"):
            _reloaded_collar(patch, shaft, "CORE_FLAT_BAND", (0.030, -0.015))
    with monkeypatch.context() as patch:
        with pytest.raises(AssertionError, match="the bore binds"):
            _reloaded_collar(patch, shaft, "CORE_DIA_BAND", (0.020, -0.008))
    with pytest.raises(AssertionError, match="round stud cannot pass the actual D-bore"):
        _reloaded_collar(monkeypatch, shaft, "THREAD_BLANK_LIMITS", (4.50, 4.60))


def test_fitted_rear_face_reacts_on_actual_f_at_every_printed_corner(
    monkeypatch,
) -> None:
    core_r = (shaft.CORE_DIA + min(shaft.CORE_DIA_BAND)) / 2.0
    bore_r = (collar.BORE_DIA + max(collar.BORE_DIA_BAND)) / 2.0
    flat_min = shaft.CORE_FLAT_FROM_AXIS + min(shaft.CORE_FLAT_BAND)
    centre_float = math.sqrt(flat_min**2 + bore_r**2 - core_r**2) - flat_min
    # The D axis is bounded at both support sections and extrapolated to F.
    lever = 1.0 + 2.0 * collar.D_SUPPORT_TO_F_MAX / collar.D_SUPPORT_LENGTH_MIN
    inner = (
        bore_r + collar.BORE_ENTRY_BREAK_LEG_MAX
        + (centre_float + shaft.CORE_TOTAL_RUNOUT / 2.0) * lever
        + shaft.TOOTH_SPACE_RUNOUT_TIR_MM / 2.0
    )
    assert collar.D_CENTRE_FLOAT_MAX == pytest.approx(centre_float)
    assert inner == pytest.approx(2.780889, abs=1e-6)
    assert collar.FRONT_BEARING_INNER_RADIUS_MAX == pytest.approx(inner)
    areas = [
        shaft.gear_bearing_area_lower(profile, inner)
        for profile in shaft.manufactured_profiles()
    ]
    assert areas and min(areas) > 0.0
    assert collar.FRONT_BEARING_AREA_MIN == pytest.approx(min(areas))
    assert collar.BODY_REAR_FACE_FROM_F == 0.0
    assert (collar.LENGTH_FITTED_MIN, collar.LENGTH_FITTED_MAX) == (3.87, 6.90)
    assert collar.BODY_BLANK_LENGTH_MIN >= (
        collar.LENGTH_FITTED_MAX + collar.FACING_ALLOWANCE
    )
    assert "REAR FACE TO FIT, SEATED ON GEAR FRONT F" in collar.BODY_LENGTH_CALLOUT
    # A larger relative axis envelope consumes all real tooth-end support.
    with pytest.raises(
        AssertionError, match="collar rear face has no actual gear support"
    ):
        _reloaded_collar(monkeypatch, shaft, "CORE_TOTAL_RUNOUT", 3.0)


def test_thread_blank_lies_inside_the_2a_major() -> None:
    """The die cuts #8-32 UNC-2A on a blank inside 3.990..4.143."""
    blank = (
        shaft.THREAD_BLANK_DIA + min(shaft.THREAD_BLANK_DIA_BAND),
        shaft.THREAD_BLANK_DIA + max(shaft.THREAD_BLANK_DIA_BAND),
    )
    assert _stud_places("ThreadBlankDia") == 3
    assert blank == pytest.approx((4.020, 4.120))
    assert MAJOR_2A[0] <= blank[0] and blank[1] <= MAJOR_2A[1]
    # The tip chamfer still runs 45 degrees down to the basic minor.
    basic_minor = BASIC_MAJOR - 1.082532 * PITCH
    assert shaft.THREAD_BLANK_DIA - 2.0 * shaft.TIP_CHAMFER == pytest.approx(
        basic_minor
    )
    # Negative control: cutting the thread on the Ø4.9 h6 D-core would leave
    # the smallest core above the 2A major maximum.
    head_blank_min = shaft.CORE_DIA + min(shaft.CORE_DIA_BAND)
    assert head_blank_min > MAJOR_2A[1]


def test_relief_holds_the_die_lead_under_the_deepest_root() -> None:
    """R9-53: full thread ends on the relief's front shoulder; the narrowest
    relief takes a 1.5-pitch die lead, and its largest floor stands under the
    deepest die-cut root and inside the nut's smallest minor."""
    core_max = _limits(shaft.CORE_FRONT_FROM_F, _stud_places("CoreFront"))[1]
    thread_end_min = _limits(shaft.PLAIN_CORE, _stud_places("PlainCore"))[0]
    assert thread_end_min - core_max == pytest.approx(1.99)
    assert thread_end_min - core_max >= 1.5 * PITCH
    relief_max = _limits(shaft.RELIEF_DIA, _stud_places("ReliefDia"))[1]
    assert relief_max == pytest.approx(2.93)
    assert relief_max < ROOT_2A_MIN < MINOR_2B_MIN
    # Negative control: a Ø3.0 relief at its .XXX upper limit would stand
    # above the conservative deepest #8-32 die-cut root.
    assert 3.0 + printed_band_mm(3) > ROOT_2A_MIN


def test_thumbnut_runs_clear_of_the_core_step_at_the_rearward_stop(
    monkeypatch,
) -> None:
    """At the shortest fitted body with its rear face on F and the shortest
    pilot, the nut's seat stands 3.87 + 2.75 = 6.62 in front of F, clear of
    the longest core 5.38; its thread runs only on full thread or relief."""
    seat = collar.LENGTH_FITTED_MIN
    nut_seat = seat + collar.PILOT_LENGTH_FITTED_MIN
    core_max = _limits(shaft.CORE_FRONT_FROM_F, _stud_places("CoreFront"))[1]
    assert nut_seat - core_max == pytest.approx(collar.NUT_CORE_STEP_AIR)
    assert nut_seat - core_max == pytest.approx(1.24)
    assert nut_seat - core_max > 0.0
    # Negative control: a full-thread end 6.5 in front of F, with a
    # one-pitch lead behind it, would put the nut's first full thread on
    # incomplete thread rather than on the relief.
    bad_runout_end = 6.5 + printed_band_mm(3) + PITCH
    assert nut_seat + nut.REAR_THREAD_LOSS < bad_runout_end
    with pytest.raises(AssertionError, match="MHA-PD-013 thumbnut / MHA-PD-008 core step"):
        _reloaded_collar(monkeypatch, shaft, "CORE_FRONT_FROM_F", 6.5)


def test_thumbnut_engages_one_and_a_half_diameters_over_the_travel(
    monkeypatch,
) -> None:
    """Full stud thread inside the nut's full thread at every accepted setting:
    the forward end is the shortest tip (or the deepest cut below the shortest
    nut's rim) less a pitch, inside the rim's countersink; the rear end the
    nut's seat countersink on the longest fitted pilot (R9-70: the nut seats
    on the collar's pilot, not the T24), or the shortest stud's full-thread
    end; each countersink's loss counted from the tap drill at its smallest
    printed angle (R9-63). Least 11.92421 at the shortest fitted body."""
    tip_min = _limits(shaft.TIP_STATION, shaft.TIP_STATION_PLACES)[0]
    thread_end_max = _limits(shaft.PLAIN_CORE, _stud_places("PlainCore"))[1]
    nut_min = _limits(nut.OVERALL_LENGTH, nut.OVERALL_LENGTH_PLACES)[0]
    pilot = (collar.PILOT_LENGTH_FITTED_MIN, collar.PILOT_LENGTH_FITTED_MAX)
    assert pilot[0] - (removable.PLATE + min(removable.PLATE_BAND)) == (
        pytest.approx(min(collar.PILOT_PROUD_RANGE))
    )
    cut_deepest = collar.STUD_CUT_BELOW_RIM[1]
    # Recompute each countersink's thread loss from its actual printed form,
    # including dish depth and the angular row, rather than trusting losses.
    included_band = angular_band_deg()
    half_min = (90.0 - included_band) / 2.0
    assert included_band == 1.0
    assert nut.CSK_INCLUDED_ANGLE_TOL == included_band
    assert nut.CSK_HALF_ANGLE_BAND == pytest.approx((0.5, -0.5))
    assert nut.CSK_HALF_ANGLE_MIN == pytest.approx(half_min)
    rear_loss = (
        (BASIC_MAJOR + 0.4 - nut.TAP_DRILL_DIA) / 2.0
        / math.tan(math.radians(half_min))
    )
    front_loss = nut.DISH_DEPTH + printed_band_mm(nut.DISH_DEPTH_PLACES) + rear_loss
    assert nut.REAR_THREAD_LOSS == pytest.approx(rear_loss)
    assert nut.FRONT_THREAD_LOSS == pytest.approx(front_loss)

    def engagement(seat: float) -> float:
        rim = seat + pilot[0] + nut_min
        tip = min(tip_min, rim - cut_deepest)
        front = min(tip - PITCH, rim - front_loss)
        rear = max(seat + pilot[1] + rear_loss, thread_end_max)
        return front - rear

    settings = [
        collar.LENGTH_FITTED_MIN
        + (collar.LENGTH_FITTED_MAX - collar.LENGTH_FITTED_MIN) * i / 100.0
        for i in range(101)
    ]
    worst = min(engagement(seat) for seat in settings)
    assert worst == pytest.approx(11.92421, abs=1e-5)
    assert worst >= ENGAGEMENT_FLOOR
    assert collar.THUMBNUT_ENGAGEMENT_WORST == pytest.approx(worst)
    # Negative control: a stud tip 8 shorter leaves less than 1.5 D.
    with pytest.raises(AssertionError, match="MHA-PD-013 thumbnut / MHA-PD-008 stud"):
        _reloaded_collar(monkeypatch, shaft, "TIP_STATION", shaft.TIP_STATION - 8.0)


def test_printed_countersink_angle_reaches_the_engagement_refusal(monkeypatch) -> None:
    """A shallower accepted cone removes real full thread; it cannot be nominal."""
    with monkeypatch.context() as patch:
        wider = _reloaded_nut(patch, 2.0)
        loss = (
            (BASIC_MAJOR + 0.4 - wider.TAP_DRILL_DIA) / 2.0
            / math.tan(math.radians(44.0))
        )
        assert wider.CSK_HALF_ANGLE_MIN == 44.0
        assert wider.REAR_THREAD_LOSS == pytest.approx(loss)
        assert wider.REAR_THREAD_LOSS > nut.REAR_THREAD_LOSS
        patch.setattr(nut, "FRONT_THREAD_LOSS", wider.FRONT_THREAD_LOSS)
        perturbed = _reloaded_collar(patch, nut, "REAR_THREAD_LOSS", loss)
        assert ENGAGEMENT_FLOOR < perturbed.THUMBNUT_ENGAGEMENT_WORST
        assert perturbed.THUMBNUT_ENGAGEMENT_WORST < collar.THUMBNUT_ENGAGEMENT_WORST
    with monkeypatch.context() as patch:
        shallow = _reloaded_nut(patch, 80.0)
        assert shallow.CSK_HALF_ANGLE_MIN == 5.0
        patch.setattr(nut, "FRONT_THREAD_LOSS", shallow.FRONT_THREAD_LOSS)
        with pytest.raises(AssertionError, match="MHA-PD-013 thumbnut / MHA-PD-008 stud"):
            _reloaded_collar(patch, nut, "REAR_THREAD_LOSS", shallow.REAR_THREAD_LOSS)


def test_native_placement_metadata_seats_the_actual_collar_rear_face_on_f() -> None:
    """Saved nominal poses, not a claim that native mates have been observed."""
    import build_pd_paper_drive_assembly as assembly

    assert assembly.KNOB_COLLAR_Z0 == pytest.approx(removable.SEAT_FACE_Z)
    assert assembly.KNOB_COLLAR_REAR_Z == pytest.approx(
        assembly.KNOB_COLLAR_Z0 + collar.LENGTH
    )
    assert assembly.KNOB_COLLAR_REAR_Z == pytest.approx(assembly.KNOB_SHAFT_Z0)
    assert assembly.KNOB_SHAFT_Z0 - assembly.KNOB_COLLAR_Z0 == pytest.approx(
        collar.LENGTH
    )


def test_both_retained_drive_pin_poses_follow_the_integral_shaft_clock() -> None:
    """The two real dowels follow the spun collar holes; their tips face forward."""
    import build_pd_paper_drive_assembly as assembly

    angle = math.radians(assembly.THIRD_PHASE_DEG)
    c, s = math.cos(angle), math.sin(angle)
    expected_stack = ((c, s, 0.0), (-s, c, 0.0), (0.0, 0.0, 1.0))
    expected_pin = ((c, s, 0.0), (0.0, 0.0, -1.0), (-s, c, 0.0))
    for actual, expected in zip(
        assembly.KNOB_FRONT_STACK_ROT, expected_stack, strict=True
    ):
        assert actual == pytest.approx(expected)
    for actual, expected in zip(
        assembly.KNOB_DRIVE_PIN_ROT, expected_pin, strict=True
    ):
        assert actual == pytest.approx(expected)

    assert len(assembly.KNOB_DRIVE_PIN_XY) == 2
    for (x, y), side in zip(assembly.KNOB_DRIVE_PIN_XY, (1.0, -1.0), strict=True):
        assert (x, y) == pytest.approx(
            (
                assembly.KNOB_SHAFT_XY[0] - side * collar.PIN_CIRCLE_RADIUS * s,
                assembly.KNOB_SHAFT_XY[1] + side * collar.PIN_CIRCLE_RADIUS * c,
            )
        )
        assert math.hypot(
            x - assembly.KNOB_SHAFT_XY[0], y - assembly.KNOB_SHAFT_XY[1]
        ) == pytest.approx(collar.PIN_CIRCLE_RADIUS)
    assert assembly.KNOB_DRIVE_PIN_Z0 - assembly.KNOB_PIN.LENGTH == pytest.approx(
        removable.DRIVE_PIN_TIP_Z
    )
    assert assembly.REMOVABLE_Z0 < removable.DRIVE_PIN_TIP_Z < assembly.KNOB_COLLAR_Z0
