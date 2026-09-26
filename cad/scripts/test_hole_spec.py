"""Offline contracts for part-owned standard-hole definitions."""

from __future__ import annotations

import pytest

import build_pivot_bracket
import crank_arm_spec
from _hole_spec import HoleSpec, blind_cut_dia_mm, drill_process


def test_crank_drill_process_is_derived_from_part_owned_specs() -> None:
    assert blind_cut_dia_mm(crank_arm_spec.PIN_HOLE_SPEC) == 4.623
    assert drill_process(crank_arm_spec.PIN_HOLE_SPEC) == "#14 DRILL"
    assert blind_cut_dia_mm(crank_arm_spec.HANDLE_PIVOT_HOLE_SPEC) == 5.953
    assert drill_process(crank_arm_spec.HANDLE_PIVOT_HOLE_SPEC) == "15/64 DRILL"


def test_drill_process_rejects_non_drill_holes() -> None:
    with pytest.raises(ValueError, match="not a drill-size hole"):
        drill_process(HoleSpec("clearance", "#4"))


def test_pivot_bracket_is_a_true_number_19_drill() -> None:
    assert build_pivot_bracket.HOLD_DOWN_HOLE_SPEC == HoleSpec("drilled_number", "#19")
    assert build_pivot_bracket.HOLE_DIA == 4.216


def test_countersink_thread_loss_and_cone_volume_are_analytic() -> None:
    """#917 S1 (a): a near/far-side countersink on a tapped hole is the
    model-owned edge break.  Ø6.55 x 90 on a 1/4-20 (major 6.35) loses 0.1
    of full thread; the cone beyond the tap drill is a frustum less the
    drilled cylinder."""
    import math

    from _hole_spec import Countersink, countersink_cone_mm3, countersink_thread_loss_mm

    csk = Countersink(6.55, 90.0, max_limit=True)
    assert countersink_thread_loss_mm(csk, 6.35) == pytest.approx(0.1)
    r_face, r_bore = 6.55 / 2.0, 5.105 / 2.0
    h = r_face - r_bore  # 90 deg included: 45 deg half angle
    frustum = math.pi * h / 3.0 * (r_face**2 + r_face * r_bore + r_bore**2)
    assert countersink_cone_mm3(csk, 5.105) == pytest.approx(frustum - math.pi * r_bore**2 * h)
    # A 60 deg countersink of the same diameter loses more thread.
    assert countersink_thread_loss_mm(Countersink(6.55, 60.0), 6.35) == pytest.approx(
        0.1 / math.tan(math.radians(30.0))
    )


def test_tapped_countersinks_ride_the_hole_wizard5_value_slots() -> None:
    """HoleWizard5's straight-tap slots (API remarks): V1 thread depth,
    V2/V3 near csink diameter/angle, V4/V5 far, V6 bottom drill angle,
    V7 cosmetic thread, V8 thread end condition; -1 means unset.  The far
    and near booleans are get-only after creation (memory:
    hole-wizard-com-recipe), so countersinks must be set here."""
    import math

    from _hole_spec import Countersink
    from _holes import tapped_value_slots

    spec = HoleSpec(
        "tapped",
        "1/4-20",
        near_countersink=Countersink(6.55, 90.0),
        far_countersink=Countersink(6.55, 90.0),
    )
    vals = tapped_value_slots(spec, thread_depth_mm=None, drill_angle_rad=None, thread_end=1)
    assert vals == [
        -1,
        6.55 / 1000.0,
        math.radians(90.0),
        6.55 / 1000.0,
        math.radians(90.0),
        -1,
        1,
        1,
        -1,
        -1,
        -1,
        -1,
    ]
    plain = tapped_value_slots(
        HoleSpec("tapped", "#6-32", end="blind", depth_mm=8.0),
        thread_depth_mm=6.0,
        drill_angle_rad=2.0594885,
        thread_end=0,
    )
    assert plain == [0.006, -1, -1, -1, -1, 2.0594885, 1, 0, -1, -1, -1, -1]


def test_countersink_max_band_hook_needs_exactly_the_countersink_diameters() -> None:
    from _holes import countersink_diameter_names

    names = [
        "Tap Drill Dia.@HoleWzd1",
        "Near Csink Dia.@HoleWzd1",
        "Near Csink Angle@HoleWzd1",
        "Far C'Sink Dia.@HoleWzd1",
    ]
    assert countersink_diameter_names(names, expected=2, label="t") == [
        "Near Csink Dia.@HoleWzd1",
        "Far C'Sink Dia.@HoleWzd1",
    ]
    with pytest.raises(RuntimeError, match="exactly 1"):
        countersink_diameter_names(names, expected=1, label="t")
