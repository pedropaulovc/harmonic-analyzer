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


_WIZARD_NAMES = [
    "Tap Drill Dia.@HoleWzd1",
    "Near Csink Dia.@HoleWzd1",
    "Near Csink Angle@HoleWzd1",
    "Far C'Sink Dia.@HoleWzd1",
    "Far C'Sink Angle@HoleWzd1",
]


def _csk_tap(near: object, far: object) -> HoleSpec:
    return HoleSpec("tapped", "1/4-20", near_countersink=near, far_countersink=far)


def test_countersink_hook_maps_each_side_to_its_own_diameter() -> None:
    """Codex on #929 (PRRT_kwDOPHDy386mOPDP): the MAX band is chosen per side,
    so the hook must say WHICH diameter is which side, not just count them."""
    from _hole_spec import Countersink
    from _holes import countersink_diameter_names

    both = _csk_tap(Countersink(6.55, 90.0, max_limit=True), Countersink(6.55, 90.0))
    assert countersink_diameter_names(_WIZARD_NAMES, both, label="t") == {
        "near": "Near Csink Dia.@HoleWzd1",
        "far": "Far C'Sink Dia.@HoleWzd1",
    }
    near_only = _csk_tap(Countersink(6.55, 90.0), None)
    only_near_names = [n for n in _WIZARD_NAMES if not n.startswith("Far")]
    assert countersink_diameter_names(only_near_names, near_only, label="t") == {
        "near": "Near Csink Dia.@HoleWzd1"
    }
    # A side the spec does not countersink is never required ...
    far_only = _csk_tap(None, Countersink(6.55, 90.0, max_limit=True))
    only_far_names = [n for n in _WIZARD_NAMES if not n.startswith("Near")]
    assert countersink_diameter_names(only_far_names, far_only, label="t") == {
        "far": "Far C'Sink Dia.@HoleWzd1"
    }
    # ... nor tolerated when the wizard built it anyway.
    with pytest.raises(RuntimeError, match=r"2 countersink diameter\(s\) for 1"):
        countersink_diameter_names(_WIZARD_NAMES, far_only, label="t")
    # A side the spec countersinks must be found.
    with pytest.raises(RuntimeError, match=r"1 countersink diameter\(s\) for 2"):
        countersink_diameter_names(only_near_names, both, label="t")
    # One diameter per side, but on the wrong side.
    with pytest.raises(RuntimeError, match="missing .*far.*unexpected .*near"):
        countersink_diameter_names(only_near_names, far_only, label="t")
    with pytest.raises(RuntimeError, match="no countersink diameter dimension"):
        countersink_diameter_names(["Tap Drill Dia.@HoleWzd1"], both, label="t")
    # A diameter that names no side (or both) is refused, not guessed.
    with pytest.raises(RuntimeError, match="names no single side"):
        countersink_diameter_names(
            ["C'Sink Dia.@HoleWzd1", "Far C'Sink Dia.@HoleWzd1"], both, label="t"
        )


@pytest.mark.parametrize(
    ("near_max", "far_max", "banded"),
    [
        (True, False, ["Near Csink Dia.@HoleWzd1"]),
        (False, True, ["Far C'Sink Dia.@HoleWzd1"]),
        (True, True, ["Near Csink Dia.@HoleWzd1", "Far C'Sink Dia.@HoleWzd1"]),
        (False, False, []),
    ],
)
def test_only_the_sides_flagged_max_are_banded_max(
    near_max: bool, far_max: bool, banded: list[str]
) -> None:
    """Mixed flags (near MAX, far not, and the reverse) band only their own
    side; the unflagged side keeps its wizard default."""
    from _hole_spec import Countersink
    from _holes import countersink_max_names

    spec = _csk_tap(
        Countersink(6.55, 90.0, max_limit=near_max),
        Countersink(6.55, 90.0, max_limit=far_max),
    )
    assert countersink_max_names(_WIZARD_NAMES, spec, label="t") == banded


# The part's countersink diameters are the FEATURE's dimension FullNames,
# not the drawing callout's hw-nscsdia / hw-fscsdia variables.  The S1 leaf
# proved the pattern finds exactly two on the both-ends post tap but did not
# log the names, so these carry no side word on purpose.
_SIDELESS_NAMES = [
    "Tap Drill Dia.@HoleWzd1",
    "Countersink Dia.@HoleWzd1",
    "Countersink Dia.1@HoleWzd1",
    "Countersink Angle@HoleWzd1",
]


def test_uniform_flags_band_every_countersink_diameter_without_sides() -> None:
    """Both sides MAX (the post taps) needs no side words: every countersink
    diameter takes the flag, exactly the path the S1 leaf proved.  Mixed
    flags on side-less names are refused, not guessed."""
    from _hole_spec import Countersink
    from _holes import countersink_max_names

    both_max = _csk_tap(Countersink(6.55, 90.0, max_limit=True), Countersink(6.55, 90.0, max_limit=True))
    assert countersink_max_names(_SIDELESS_NAMES, both_max, label="t") == [
        "Countersink Dia.@HoleWzd1",
        "Countersink Dia.1@HoleWzd1",
    ]
    plain = _csk_tap(Countersink(6.55, 90.0), Countersink(6.55, 90.0))
    assert countersink_max_names(_SIDELESS_NAMES, plain, label="t") == []
    with pytest.raises(RuntimeError, match=r"3 countersink diameter\(s\) for 2"):
        countersink_max_names([*_SIDELESS_NAMES, "Countersink Dia.2@HoleWzd1"], both_max, label="t")
    mixed = _csk_tap(Countersink(6.55, 90.0, max_limit=True), Countersink(6.55, 90.0))
    with pytest.raises(RuntimeError, match="names no single side"):
        countersink_max_names(_SIDELESS_NAMES, mixed, label="t")

