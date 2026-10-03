"""The paper-drive transgear interference rows follow their owner specs.

``_interference_contracts`` writes every transgear size as a literal so no
assembly re-keys on a transgear spec edit; these tests re-derive each row from
the owners, so a spec change that moves a fit fails here instead of passing
a stale bound (the MHA-139 precedent in test_crank_handle_pivot_screw_drawing).
"""

from __future__ import annotations

import importlib
import math

import pytest

import _holes
import _interference_contracts
import latch_hook_bracket_screw_spec as bracket_screw
import latch_hook_bracket_spec as hook_bracket
import latch_hook_rivet_spec as rivet
import latch_hook_spec as hook
import rack_pinion_spec as disc
import support_bar_spec as bar
import transgear_arm_geometry as arm
import transgear_arm_plate_geometry as plate
import transgear_arm_plate_screw_spec as plate_screw
import transgear_collar_cross_pin_spec as cross_pin
import transgear_disc_hub_spec as hub
import transgear_disc_screw_spec as disc_screw
import transgear_hanger_joints as joints
import transgear_knob_cup_pin_spec as cup_pin
import transgear_knob_cup_spec as cup
import transgear_knob_drive_pin_spec as drive_pin
import transgear_knob_shaft_spec as shaft
import transgear_latch_pin_spec as latch_pin
import transgear_pivot_screw_spec as pivot_screw
import transgear_pivot_spacer_spec as spacer
import transgear_removable_spec as removable
import transgear_pin_spec as pin
import transgear_retaining_ring_spec as ring
import transgear_thumbnut_spec as thumbnut
from _hole_spec import TAP_DRILL_MM


def _allowed() -> dict[frozenset[str], float]:
    return _interference_contracts.allowed_interference_pairs("paper-drive")


def _annulus(major_d: float, tap_d: float, length: float) -> float:
    return 1.10 * math.pi * (major_d**2 - tap_d**2) * length / 4.0


def _pair(first: str, second: str) -> frozenset[str]:
    return frozenset((first, second))


def _collar():
    # MHA-177's spec (KnobShaftRound10); imported here so a missing or
    # renamed collar fails this test rather than the whole module.
    return importlib.import_module("transgear_drive_collar_spec")


def test_hanger_screw_rows_follow_the_arm_plate_and_bar() -> None:
    allowed = _allowed()
    engaged = plate_screw.LENGTH - plate.THICKNESS_OVER_ARM
    assert engaged == pytest.approx(joints.PLATE_SCREW_ENGAGEMENT_NOMINAL)
    plate_limit = _annulus(
        plate_screw.THREAD_MAJOR, TAP_DRILL_MM[arm.PLATE_TAP_SPEC.size], engaged
    )
    for n in (1, 2):
        pair = _pair(f"transgear-arm-plate-screw-{n}", "transgear-arm-1")
        assert allowed[pair] == pytest.approx(plate_limit)

    # The shoulder screw's thread past its neck flat, in the bar's blind tap.
    assert allowed[_pair("transgear-pivot-screw-1", "support-bar-1")] == pytest.approx(
        _annulus(
            pivot_screw.THREAD_MAJOR,
            bar.PIVOT_TAP_DRILL_DIA,
            pivot_screw.THREAD_LEN - pivot_screw.NECK_FLAT_END,
        )
    )
    # R9-71: the spacer's reamed bore pressed on the shoulder, whole length.
    assert allowed[
        _pair("transgear-pivot-spacer-1", "transgear-pivot-screw-1")
    ] == pytest.approx(
        _annulus(pivot_screw.SHOULDER_DIA, spacer.BORE_DIA, spacer.LENGTH)
    )


def test_latch_bracket_screw_rows_follow_the_screw_and_bar_taps() -> None:
    allowed = _allowed()
    limit = _annulus(
        bracket_screw.MAJOR_DIA,
        TAP_DRILL_MM[bar.BRACKET_TAP_SPEC.size],
        bracket_screw.ENGAGEMENT_NOMINAL,
    )
    for n in (1, 2):
        pair = _pair(f"latch-hook-bracket-screw-{n}", "support-bar-1")
        assert allowed[pair] == pytest.approx(limit)


def test_disc_cluster_rows_follow_the_pin_hub_and_disc() -> None:
    allowed = _allowed()
    # The pin presses through the arm's reamed bore over the whole stock.
    assert allowed[_pair("transgear-pin-1", "transgear-arm-1")] == pytest.approx(
        _annulus(pin.DIA, arm.PIN_BORE_DIA, arm.THICKNESS)
    )
    # Each #0-80 is cut to fit (R9-47): it fills the disc's tap from the
    # flange's front face to its cut end, inside the disc's rear face.
    assert disc_screw.SHANK_DIA == pytest.approx(disc.SCREW_MAJOR_DIA)
    engaged = disc_screw.CUT_LENGTH - hub.FLANGE_THICK
    assert 0.0 < disc.FACE_WIDTH - engaged <= disc_screw.TIP_BELOW_REAR_FACE[1]
    limit = _annulus(disc.SCREW_MAJOR_DIA, disc.TAP_DRILL_DIA, engaged)
    for n in (1, 2, 3):
        pair = _pair(f"transgear-disc-screw-{n}", "rack-pinion-1")
        assert allowed[pair] == pytest.approx(limit)


def test_ring_row_is_the_free_state_grip_on_its_prong_arcs() -> None:
    """MHA-182 is the replica-gated vendor body at its free diameter, so its
    prongs grip inside the MHA-179 groove floor; the overlap is the prong
    arcs' share of the groove-to-free annulus over the ring's thickness."""
    from diagnostics import diag_build_97431A260 as recipe

    assert pin.GROOVE_DIA == ring.GROOVE_DIA
    assert ring.FREE_DIA < pin.GROOVE_DIA
    # The ring sits wholly in the groove, off the Ø3.9 land.
    assert ring.THICKNESS + ring.THICKNESS_TOL <= pin.GROOVE_WIDTH
    sweeps = []
    for segment in recipe.outline():
        if isinstance(segment, recipe.Line):
            continue
        if math.hypot(*segment.start) != pytest.approx(ring.FREE_DIA / 2.0):
            continue
        start = math.atan2(segment.start[1], segment.start[0])
        end = math.atan2(segment.end[1], segment.end[0])
        sweeps.append((end - start) % (2.0 * math.pi))
    assert len(sweeps) == 3
    share = sum(sweeps) / (2.0 * math.pi)
    pair = _pair("transgear-retaining-ring-1", "transgear-pin-1")
    assert _allowed()[pair] == pytest.approx(
        share * _annulus(pin.GROOVE_DIA, ring.FREE_DIA, ring.THICKNESS)
    )


def test_knob_stack_rows_follow_the_shaft_cup_collar_and_nut() -> None:
    allowed = _allowed()
    # R9-70 (K-1): MHA-183 across the journal and both walls of the cup ring,
    # its ends inside the cup's O.D.: the journal takes the diametral chord,
    # the cup the rest of the tube.
    tube_d, tube_id = cup_pin.PIN_DIA, cup_pin.PIN_DIA - 2.0 * cup_pin.WALL_T
    in_journal = _holes.cross_hole_volume_mm3(
        tube_d, shaft.JOURNAL_DIA
    ) - _holes.cross_hole_volume_mm3(tube_id, shaft.JOURNAL_DIA)
    tube = math.pi * (tube_d**2 - tube_id**2) / 4.0 * cup_pin.PIN_LEN
    assert shaft.JOURNAL_DIA < cup_pin.PIN_LEN < cup.OD
    assert cup.BORE_DIA == shaft.JOURNAL_DIA
    pair = _pair("transgear-knob-cup-pin-1", "transgear-knob-shaft-1")
    assert allowed[pair] == pytest.approx(1.10 * in_journal, rel=1e-4)
    pair = _pair("transgear-knob-cup-pin-1", "transgear-knob-cup-1")
    assert allowed[pair] == pytest.approx(1.10 * (tube - in_journal), rel=1e-4)
    assert not any("knob-retaining-screw" in name for p in allowed for name in p)

    # Stud tip less the nut's seat (collar set + the fitted pilot, R9-70), at
    # the nominal, all on the thread blank (its full-thread end lies behind
    # the seat).
    collar = _collar()
    nut_engaged = shaft.TIP_STATION - collar.SET_NOMINAL - collar.PILOT_LENGTH
    assert collar.PILOT_LENGTH == pytest.approx(removable.PLATE + collar.PILOT_PROUD)
    assert shaft.TIP_STATION - nut_engaged > shaft.PLAIN_CORE
    assert allowed[_pair("transgear-thumbnut-1", "transgear-knob-shaft-1")] == (
        pytest.approx(
            _annulus(shaft.THREAD_BLANK_DIA, thumbnut.TAP_DRILL_DIA, nut_engaged)
        )
    )

    tube = _holes.cross_hole_volume_mm3(
        cross_pin.PIN_DIA, shaft.CORE_DIA
    ) - _holes.cross_hole_volume_mm3(
        cross_pin.PIN_DIA - 2.0 * cross_pin.WALL_T, shaft.CORE_DIA
    )
    # The pin spans the core, so the bound is its whole diametral chord.
    assert cross_pin.PIN_LEN > shaft.CORE_DIA
    pair = _pair("transgear-collar-cross-pin-1", "transgear-knob-shaft-1")
    assert allowed[pair] == pytest.approx(1.10 * tube)


def test_head_seat_rows_admit_less_than_a_micron_of_sink() -> None:
    """The flush-head rows (R9-35) bound numeric slivers of coincident seats;
    a head sunk 1 um into its seat must still exceed them."""
    allowed = _allowed()
    sink = 0.001
    # The 82-degree countersink cone between the hole and the head rim.
    half = math.radians(plate.CSK_ANGLE_DEG / 2.0)
    r0, r1 = plate.SCREW_HOLE_DIA / 2.0, plate.CSK_DIA / 2.0
    cone_area = math.pi * (r0 + r1) * (r1 - r0) / math.sin(half)
    for n in (1, 2):
        pair = _pair(f"transgear-arm-plate-screw-{n}", "transgear-arm-plate-1")
        assert 0.0 < allowed[pair] < cone_area * sink


def test_drive_pins_press_into_the_collar_not_the_shaft() -> None:
    """MHA-155's reams moved from the shaft's integral collar to MHA-177; the
    pins press over their length behind the seat face, inside the collar."""
    collar = _collar()
    allowed = _allowed()
    assert drive_pin.DIA > collar.PIN_HOLE_DIA
    assert drive_pin.PRESS_DEPTH <= collar.LENGTH
    limit = _annulus(drive_pin.DIA, collar.PIN_HOLE_DIA, drive_pin.PRESS_DEPTH)
    for n in (1, 2):
        pin = f"transgear-knob-drive-pin-{n}"
        assert allowed[_pair(pin, "transgear-drive-collar-1")] == pytest.approx(limit)
        assert _pair(pin, "transgear-knob-shaft-1") not in allowed


def test_pressed_and_slip_joints_without_a_row_do_not_overlap() -> None:
    """A row-less joint is modelled line to line or clear; a spec that turns
    one into a press needs a row here."""
    assert shaft.CORE_DIA <= _collar().BORE_DIA
    assert latch_pin.DIA <= arm.PIN_HOLE_DIA
    assert rivet.DIA <= hook.RIVET_HOLE_DIA
    assert rivet.DIA <= hook_bracket.RIVET_HOLE_DIA
    assert drive_pin.DIA <= removable.PIN_HOLE_DIA


def test_retired_parts_have_no_rows() -> None:
    retired = (
        "transgear-latch",
        "transgear-pinion",
        "transgear-bracket",
        "bracket-screw",
    )
    named = {name.rsplit("-", 1)[0] for pair in _allowed() for name in pair}
    assert not named & set(retired)
