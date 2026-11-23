"""The paper-drive transgear interference rows follow their owner specs.

``_pd_paper_drive_interference`` writes every transgear size as a literal so the
paper drive's table does not re-key on a transgear spec edit; these tests re-derive each row from
the owners, so a spec change that moves a fit fails here instead of passing
a stale bound (the MHA-DT-32 precedent in test_dt_crank_handle_pivot_screw_drawing).
"""

from __future__ import annotations

import importlib
import math
from collections.abc import Mapping

import pytest

import _chain
import _pd_paper_drive_interference
import pd_latch_hook_bracket_screw_spec as bracket_screw
import pd_latch_hook_geometry as hook
import pd_rack_pinion_spec as disc
import pd_support_bar_spec as bar
import pd_transgear_arm_geometry as arm
import pd_transgear_arm_plate_geometry as plate
import pd_vn_transgear_arm_plate_screw_spec as plate_screw
import pd_transgear_disc_hub_spec as hub
import pd_transgear_disc_screw_spec as disc_screw
import pd_feed_rack_spec as feed_rack
import pd_feed_rack_screw_spec as rack_screw
import pd_platen_bottom_guide_spec as bottom_guide
import transgear_hanger_joints as joints
import pd_transgear_knob_bush_geometry as bush
import pd_transgear_knob_cup_spec as cup
import pd_vn_transgear_knob_cup_screw_spec as cup_screw
import pd_vn_transgear_knob_drive_pin_spec as drive_pin
import pd_transgear_knob_shaft_spec as shaft
import pd_vn_transgear_latch_pin_spec as latch_pin
import pd_vn_transgear_pivot_screw_spec as pivot_screw
from _mcmaster_90325a174 import NECK_FLAT_END
import pd_transgear_pivot_spacer_spec as spacer
import _sprocket_seat_geometry as removable
import pd_transgear_pin_spec as pin
import pd_vn_transgear_retaining_ring_spec as ring
import pd_transgear_thumbnut_spec as thumbnut
from _hole_spec import TAP_DRILL_MM, THREAD_MAJOR_MM


def _allowed() -> Mapping[frozenset[str], float]:
    return _pd_paper_drive_interference.ALLOWED_PAIRS


def _annulus(major_d: float, tap_d: float, length: float) -> float:
    return 1.10 * math.pi * (major_d**2 - tap_d**2) * length / 4.0


def _pair(first: str, second: str) -> frozenset[str]:
    return frozenset((first, second))


def _collar():
    # MHA-PD-22's spec (KnobShaftRound10); imported here so a missing or
    # renamed collar fails this test rather than the whole module.
    return importlib.import_module("pd_transgear_drive_collar_spec")


def test_hanger_screw_rows_follow_the_arm_plate_and_bar() -> None:
    allowed = _allowed()
    engaged = plate_screw.LENGTH - plate.THICKNESS_OVER_ARM
    assert engaged == pytest.approx(joints.PLATE_SCREW_ENGAGEMENT_NOMINAL)
    plate_limit = _annulus(
        plate_screw.THREAD_MAJOR, TAP_DRILL_MM[arm.PLATE_TAP_SPEC.size], engaged
    )
    for n in (1, 2):
        pair = _pair(f"pd-vn-transgear-arm-plate-screw-{n}", "pd-transgear-arm-1")
        assert allowed[pair] == pytest.approx(plate_limit)

    # The shoulder screw's fitted thread past its neck flat, in the bar's
    # through tap.
    assert allowed[_pair("pd-vn-transgear-pivot-screw-1", "pd-support-bar-1")] == pytest.approx(
        _annulus(
            pivot_screw.THREAD_MAJOR,
            bar.PIVOT_TAP_DRILL_DIA,
            pivot_screw.FITTED_THREAD_LEN - NECK_FLAT_END,
        )
    )
    # R9-71: the spacer's reamed bore pressed on the shoulder, whole length.
    assert allowed[
        _pair("pd-transgear-pivot-spacer-1", "pd-vn-transgear-pivot-screw-1")
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
        pair = _pair(f"sh-vn-fillister-screw-90280a108-{n}", "pd-support-bar-1")
        assert allowed[pair] == pytest.approx(limit)


def test_disc_cluster_rows_follow_the_pin_hub_and_disc() -> None:
    allowed = _allowed()
    # #2415: only the pin's press land grips the arm's reamed bore.
    assert allowed[_pair("pd-transgear-pin-1", "pd-transgear-arm-1")] == pytest.approx(
        _annulus(pin.PRESS_LAND_DIA, arm.PIN_BORE_DIA, pin.PRESS_LAND_LENGTH)
    )
    # Each #0-80 is cut to fit (R9-47): it fills the disc's tap from the
    # flange's front face to its cut end, inside the disc's rear face.
    assert disc_screw.SHANK_DIA == pytest.approx(disc.SCREW_MAJOR_DIA)
    engaged = disc_screw.CUT_LENGTH - hub.FLANGE_THICK
    assert 0.0 < disc.FACE_WIDTH - engaged <= disc_screw.TIP_BELOW_REAR_FACE[1]
    limit = _annulus(disc.SCREW_MAJOR_DIA, disc.TAP_DRILL_DIA, engaged)
    for n in (5, 6, 7):
        pair = _pair(f"sh-vn-fillister-screw-91794a055-{n}", "pd-rack-pinion-1")
        assert allowed[pair] == pytest.approx(limit)


def test_rack_screw_rows_follow_the_strip_and_the_bottom_guide() -> None:
    allowed = _allowed()
    # #2410: each stock RackScrew under-head on MHA-PD-27's counterbore floor,
    # the screw floor above the strip's flat top; the rest of its shank in the
    # strip's tap drill, short of the drill's bottom.
    floor = bottom_guide.GUIDE_HEIGHT - bottom_guide.SCREW_CBORE_DEPTH
    assert floor == pytest.approx(feed_rack.SCREW_FLOOR)
    engaged = rack_screw.LENGTH - floor
    assert 0.0 < engaged < feed_rack.TAP_DRILL_DEPTH
    limit = _annulus(
        feed_rack.TAP_MAJOR_DIA, TAP_DRILL_MM[feed_rack.TAP_SIZE], engaged
    )
    for n in (1, 2, 3, 4):
        pair = _pair(f"sh-vn-fillister-screw-91794a055-{n}", "pd-feed-rack-1")
        assert allowed[pair] == pytest.approx(limit)


def test_ring_row_is_the_free_state_grip_on_its_prong_arcs() -> None:
    """MHA-PD-VN-61 is modelled at its free diameter, so its prongs grip
    inside the MHA-PD-23 groove floor; the overlap is the prong arcs' share
    of the groove-to-free annulus over the ring's thickness."""
    assert pin.GROOVE_DIA == ring.GROOVE_DIA
    assert ring.FREE_DIA < pin.GROOVE_DIA
    # The ring sits wholly in the groove, off the shank.
    assert ring.THICKNESS + ring.THICKNESS_TOL <= pin.GROOVE_WIDTH
    pair = _pair("pd-vn-transgear-retaining-ring-1", "pd-transgear-pin-1")
    assert _allowed()[pair] == pytest.approx(
        _pd_paper_drive_interference._RING_PRONG_SHARE
        * _annulus(pin.GROOVE_DIA, ring.FREE_DIA, ring.THICKNESS)
    )


def test_knob_stack_rows_follow_the_shaft_cup_collar_and_nut() -> None:
    allowed = _allowed()
    # #2425: MHA-PD-VN-71 seated under its head on the cup web's rear face
    # (the counterbore floor), its fully threaded shank into the journal's
    # blind #2-56 tap at its #50 drill from the journal's end, which stands
    # the fitted pilot depth (stand-out less end float) inside the cup's front.
    assert cup_screw.THREAD == shaft.REAR_TAP_THREAD == "#2-56"
    # The table's #2-56 major is the .086 basic major rounded to the micron.
    assert cup_screw.MAJOR_DIA == pytest.approx(THREAD_MAJOR_MM["#2-56"], abs=1e-3)
    assert shaft.REAR_TAP_DRILL_DIA == TAP_DRILL_MM["#2-56"]
    journal_end_in_cup = shaft.JOURNAL_STANDOUT - shaft.END_FLOAT
    assert journal_end_in_cup == pytest.approx(cup.PILOT_DEPTH_FITTED)
    under_head_behind_journal_end = cup.LENGTH - cup.CBORE_DEPTH - journal_end_in_cup
    assert under_head_behind_journal_end == pytest.approx(3.048)
    engaged = cup_screw.LENGTH - under_head_behind_journal_end
    # The table's literal is the placed screw's engagement in the tap.
    assembly = importlib.import_module("build_pd_paper_drive_assembly")
    assert engaged == pytest.approx(assembly.KNOB_CUP_SCREW_ENGAGED)
    assert engaged <= shaft.REAR_TAP_FULL_THREAD_MIN
    pair = _pair("pd-vn-transgear-knob-cup-screw-1", "pd-transgear-knob-shaft-1")
    assert allowed[pair] == pytest.approx(
        _annulus(THREAD_MAJOR_MM["#2-56"], shaft.REAR_TAP_DRILL_DIA, engaged)
    )
    # Its shank passes the web's #33 clearance hole: no row with the cup.
    assert cup_screw.MAJOR_DIA < cup.CLEAR_HOLE_DIA
    assert (
        _pair("pd-vn-transgear-knob-cup-screw-1", "pd-transgear-knob-cup-1")
        not in allowed
    )
    assert not any("knob-cup-pin" in name for p in allowed for name in p)
    assert not any("knob-retaining-screw" in name for p in allowed for name in p)

    # Stud tip less the nut's pilot seat on the .243 nominal collar, whose
    # rear reacts on F (its faced remainder is air at its front). The nominal
    # overlap is all on the blank.
    collar = _collar()
    nut_engaged = shaft.TIP_STATION - collar.LENGTH - collar.PILOT_LENGTH
    assert collar.PILOT_LENGTH == pytest.approx(removable.PLATE + collar.PILOT_PROUD)
    assert collar.BODY_REAR_FACE_FROM_F == 0.0
    assert shaft.TIP_STATION - nut_engaged > shaft.PLAIN_CORE
    assert allowed[_pair("pd-transgear-thumbnut-1", "pd-transgear-knob-shaft-1")] == (
        pytest.approx(
            _annulus(shaft.THREAD_BLANK_DIA, thumbnut.TAP_DRILL_DIA, nut_engaged)
        )
    )

    assert not any("collar-cross-pin" in name for p in allowed for name in p)


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
        pair = _pair(f"pd-vn-transgear-arm-plate-screw-{n}", "pd-transgear-arm-plate-1")
        assert 0.0 < allowed[pair] < cone_area * sink


def test_drive_pins_press_into_the_collar_not_the_shaft() -> None:
    """MHA-PD-VN-54's reams moved from the shaft's integral collar to MHA-PD-22; the
    pins press over their length behind the seat face, inside the collar."""
    collar = _collar()
    allowed = _allowed()
    assert drive_pin.DIA > collar.PIN_HOLE_DIA
    assert drive_pin.PRESS_DEPTH <= collar.LENGTH
    limit = _annulus(drive_pin.DIA, collar.PIN_HOLE_DIA, drive_pin.PRESS_DEPTH)
    for n in (1, 2):
        pin = f"pd-vn-transgear-knob-drive-pin-{n}"
        assert allowed[_pair(pin, "pd-transgear-drive-collar-1")] == pytest.approx(limit)
        assert _pair(pin, "pd-transgear-knob-shaft-1") not in allowed


def test_hub_key_pin_and_collar_flat_pin_rows_follow_their_specs() -> None:
    """#2409: MHA-PD-VN-69 presses along the hub's chord ream over its whole
    length; MHA-PD-VN-70 presses into the collar's blind ream over its faced
    model length; neither pin's side or crest carries a row with the shafts,
    each standing off the flat it keys."""
    import pd_vn_transgear_collar_flat_pin_spec as flat_pin
    import pd_vn_transgear_hub_key_pin_spec as key_pin
    import pd_transgear_feed_pinion_spec as feed_pinion

    collar = _collar()
    allowed = _allowed()
    assert key_pin.DIA > hub.KEY_PIN_HOLE_DIA
    key_limit = _annulus(key_pin.DIA, hub.KEY_PIN_HOLE_DIA, key_pin.LENGTH)
    pair = _pair("pd-vn-transgear-hub-key-pin-1", "pd-transgear-disc-hub-1")
    assert allowed[pair] == pytest.approx(key_limit)
    assert _pair("pd-vn-transgear-hub-key-pin-1", "pd-transgear-feed-pinion-1") not in allowed
    assert hub.KEY_PIN_CHORD_OFFSET - key_pin.DIA / 2.0 > feed_pinion.FLAT_TO_AXIS
    assert flat_pin.DIA > collar.FLAT_PIN_HOLE_DIA
    pin_limit = _annulus(flat_pin.DIA, collar.FLAT_PIN_HOLE_DIA, collar.FLAT_PIN_LENGTH)
    pin = "pd-vn-transgear-collar-flat-pin-1"
    assert allowed[_pair(pin, "pd-transgear-drive-collar-1")] == pytest.approx(pin_limit)
    assert _pair(pin, "pd-transgear-knob-shaft-1") not in allowed
    # The modelled crest stands off the modelled core flat.
    assert collar.FLAT_PIN_CENTRE - flat_pin.DIA / 2.0 > shaft.CORE_FLAT_FROM_AXIS


def test_connecting_link_row_is_the_closing_link_mesh_on_the_t24() -> None:
    """MHA-PD-VN-66 closes the loop at the last station, whose forward pin is
    pin 0 on the knob T24's pitch circle: one bounded mesh row with the
    removable, and no row with any chain link (link joints are clear)."""
    x, y, _ = _chain.loop_point_tangent(_chain.LINK_COUNT * _chain.LINK_PITCH)
    assert math.hypot(x, y) == pytest.approx(_chain.KNOB_PITCH_R, abs=1e-6)
    rows = {
        pair: v for pair, v in _allowed().items() if any("vn-chain" in n for n in pair)
    }
    pair = _pair("pd-transgear-removable-1", "pd-vn-chain-connecting-link-1")
    assert set(rows) == {pair}
    assert rows[pair] == pytest.approx(1.10 * (3.51208627 + 2.10455082))


def test_locating_dowels_press_into_the_arm_and_slip_in_the_plate() -> None:
    """MHA-PD-VN-64 presses into the arm's through reams over its insertion
    (length less proud), short of the front face, and slips in the plate."""
    import pd_vn_transgear_arm_plate_locating_pin_spec as dowel
    import _transgear_arm_plate_locating_interface as interface

    allowed = _allowed()
    insertion = dowel.LENGTH - interface.PROUD_MM
    assert dowel.DIA > arm.LOCATOR_HOLE_DIA_MM
    assert insertion < arm.THICKNESS
    assert dowel.DIA <= plate.LOCATOR_HOLE_DIA_MM
    limit = _annulus(dowel.DIA, arm.LOCATOR_HOLE_DIA_MM, insertion)
    for n in (1, 2):
        pin = f"pd-vn-transgear-arm-plate-locating-pin-{n}"
        assert allowed[_pair(pin, "pd-transgear-arm-1")] == pytest.approx(limit)
        assert _pair(pin, "pd-transgear-arm-plate-1") not in allowed


def test_the_latch_pin_presses_into_the_arms_blind_ream() -> None:
    """MHA-PD-VN-58 in the arm's .1240 ream over its modelled insertion: the
    hole is modelled at its set reamer's size (fit audit 2026-11-23), so the
    press is a modelled overlap and takes a row."""
    assert latch_pin.DIA > arm.PIN_HOLE_DIA
    assert latch_pin.PRESS_DEPTH < arm.PIN_HOLE_DEPTH
    pair = _pair("pd-vn-transgear-latch-pin-1", "pd-transgear-arm-1")
    assert _allowed()[pair] == pytest.approx(
        _annulus(latch_pin.DIA, arm.PIN_HOLE_DIA, latch_pin.PRESS_DEPTH)
    )


def test_pressed_and_slip_joints_without_a_row_do_not_overlap() -> None:
    """A row-less joint is modelled line to line or clear; a spec that turns
    one into a press needs a row here."""
    assert shaft.CORE_DIA <= _collar().BORE_DIA
    # The modelled pin stands on the hook hole's axis offset by the bearing lift.
    assert hook.PIN_BEARING_LIFT + latch_pin.DIA / 2.0 <= hook.PIN_HOLE_DIA / 2.0
    assert drive_pin.DIA <= removable.PIN_HOLE_DIA
    # #2425: the MHA-PD-28 bush's press in the plate is modelled line to
    # line (the step is turned to the measured hole), and the journal runs
    # in its reamed bore.
    assert bush.PRESS_DIA == plate.PRESS_HOLE_DIA
    assert shaft.JOURNAL_DIA <= bush.BORE_DIA
    allowed = _allowed()
    for other in ("pd-transgear-arm-plate-1", "pd-transgear-knob-shaft-1"):
        assert _pair("pd-transgear-knob-bush-1", other) not in allowed


def test_retired_parts_have_no_rows() -> None:
    retired = (
        "transgear-latch",
        "transgear-pinion",
        "transgear-bracket",
        "bracket-screw",
        "pd-latch-hook-bracket",
        "vn-latch-hook-rivet",
        "vn-transgear-collar-cross-pin",
        "pd-vn-transgear-knob-cup-pin",
    )
    named = {name.rsplit("-", 1)[0] for pair in _allowed() for name in pair}
    assert not named & set(retired)
