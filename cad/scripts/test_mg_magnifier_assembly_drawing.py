"""Offline contract for the magnifier assembly drawing and its stack settings."""

import json
import math
import re
from dataclasses import replace
from fractions import Fraction
from types import SimpleNamespace

import pytest

import _transforms
import build_mg_magnifier_assembly as assembly
import draw_mg_magnifier_assembly as drawing
import mg_magnifier_assembly_sheet as notes
import mg_magnifier_assembly_spec as stack
import mg_magnifier_assembly_steps as steps
import mg_magnifier_explode_spec as explode
import mg_magnifying_vertical_rod_geom
import mg_magnifying_wheel_geom
import mg_wheel_axle_spacer_spec
import mg_wheel_axle_spec
import mg_wheel_group
from _drawing_common import is_pictorial_orientation
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_types import DRAWING_TEMPLATES, DrawingLayout
from _title_block_units import render_number

# The LANDSCAPE sheet's free field right of the isometric: inside the border
# (about 13 mm in from the trim) and above the title block (sheet metres).
_TEMPLATE = DRAWING_TEMPLATES[DrawingLayout.LANDSCAPE]
BORDER = 0.013
SHEET_RIGHT = _TEMPLATE.width_m - BORDER
SHEET_TOP = _TEMPLATE.height_m - BORDER
TITLE_BLOCK_TOP = _TEMPLATE.title_block_top_m
ISO_RIGHT = 0.255


def test_magnifier_keeps_registry_outputs_and_precomputed_placement() -> None:
    spec = DRAWINGS_BY_NAME["mg_magnifier_assembly"]
    assert spec.source_kind == "assembly"
    assert spec.part == "mg_magnifier"
    assert drawing.SOURCE == spec.source
    assert drawing.OUTPUTS == drawing.OUTPUTS.__class__(
        spec.outputs["slddrw"], spec.outputs["pdf"], spec.outputs["png"]
    )
    assert drawing.SHEET_SCALE == (1.0, 4.0)
    assert drawing.FRONT_CENTER == (0.070, 0.150)
    assert drawing.RIGHT_CENTER == (0.168, 0.150)
    assert drawing.ISO_CENTER == (0.233, 0.140)


@pytest.mark.parametrize(
    "orientation, pictorial",
    [
        (stack.DRAWING_ISOMETRIC_VIEW, True),
        (stack.DRAWING_BACK_VIEW, False),
        (stack.DRAWING_LEFT_VIEW, False),
    ],
)
def test_magnifier_named_views_receive_the_correct_display_rules(
    orientation, pictorial
) -> None:
    assert is_pictorial_orientation(orientation) is pictorial


@pytest.mark.parametrize("detail", [drawing.PRESSED, drawing.ENDSHAKE])
def test_stack_detail_station_increases_right(detail) -> None:
    assert detail.sheet_xy(detail.centre_d + 1.0) == pytest.approx(
        (detail.centre[0] + detail.mm, detail.centre[1])
    )


def test_the_stack_settings_are_the_group_stations_with_their_bands() -> None:
    # Owner ruling 2026-11-21: the gauge runs from the spacer's outer face,
    # .768 +/-.002, the rev-10 19.5 snapped to the .001-in grid.
    assert stack.PRESS_GAUGE == mg_wheel_axle_spec.PRESS_GAUGE == 0.768 * 25.4
    assert stack.PRESS_GAUGE_TOL == 0.002 * 25.4
    assert stack.PRESS_GAUGE_TOL == mg_wheel_axle_spec.PRESS_GAUGE_TOL
    # The printed endshake band is exactly the group's set window.
    assert stack.ENDSHAKE - stack.ENDSHAKE_TOL == pytest.approx(
        mg_wheel_group.ENDSHAKE_MIN
    )
    assert stack.ENDSHAKE + stack.ENDSHAKE_TOL == pytest.approx(
        mg_wheel_group.ENDSHAKE_MAX
    )
    # Chain stations: bar far face, axle plain end, bar front face, spacer
    # outer face, shank step, drum face, spigot face, front washer, locknut
    # face, thread end.
    far, plain, face, spacer, step, drum, hub, washer, locknut, thread = stack.CHAIN_D
    assert stack.CHAIN_D[stack.CHAIN_ORIGIN_INDEX] == face == 0.0
    assert far == -mg_wheel_axle_spec.BAR_DEPTH
    assert plain == mg_wheel_axle_spec.BACK_Y
    assert spacer == mg_wheel_axle_spacer_spec.LENGTH
    assert step - spacer == pytest.approx(stack.PRESS_GAUGE)
    assert step == pytest.approx(mg_wheel_axle_spec.STEP_Y)
    assert hub - drum == pytest.approx(
        mg_magnifying_wheel_geom.SPIGOT_LEN - mg_magnifying_wheel_geom.DRUM_LEN
    )
    assert washer - hub == pytest.approx(stack.ENDSHAKE)
    assert washer == mg_wheel_group.FRONT_WASHER_D
    assert locknut == mg_wheel_group.LOCKNUT_FACE_D
    assert thread == mg_wheel_axle_spec.THREAD_END_Y
    assert far < plain < face < spacer < step < drum < hub < washer < locknut < thread


def test_the_stack_dimensions_are_marked_banded_and_called_out() -> None:
    limits = {
        stack.DRUM_RECESS_DIMENSION,
        stack.THREAD_PAST_LOCKNUT_DIMENSION,
    }
    names = (
        {stack.PRESS_GAUGE_DIMENSION, stack.ENDSHAKE_DIMENSION, stack.BACK_END_SUNK_DIMENSION}
        | limits
    )
    assert notes.DRAWING_DIMENSIONS == {stack.FEATURE: names}
    assert set(stack.DRAWING_PRECISION[stack.FEATURE]) == names
    assert set(stack.DIMENSION_TOLERANCES) == {
        stack.PRESS_GAUGE_DIMENSION,
        stack.ENDSHAKE_DIMENSION,
    }
    assert set(stack.LIMIT_DIMENSIONS) == limits
    assert stack.DIMENSION_TOLERANCES[stack.ENDSHAKE_DIMENSION] == stack.ENDSHAKE_TOL
    assert stack.DIMENSION_TOLERANCES[stack.PRESS_GAUGE_DIMENSION] == stack.PRESS_GAUGE_TOL
    # The sheet is inch; the gauge, the endshake and their bands print
    # exactly at their places (render_number refuses a value off the printed
    # grid), so each printed band is the stack's band; so do the limit pairs.
    assert stack.UNIT == "in"
    places = stack.DRAWING_PRECISION[stack.FEATURE]
    render_number(stack.ENDSHAKE / 25.4, "in", places[stack.ENDSHAKE_DIMENSION])
    render_number(stack.ENDSHAKE_TOL / 25.4, "in", stack.TOLERANCE_PRECISION)
    render_number(stack.PRESS_GAUGE / 25.4, "in", places[stack.PRESS_GAUGE_DIMENSION])
    render_number(stack.PRESS_GAUGE_TOL / 25.4, "in", stack.TOLERANCE_PRECISION)
    for name, pair in stack.LIMIT_DIMENSIONS.items():
        assert places[name] == stack.LIMIT_PRECISION
        for limit in pair:
            render_number(limit / 25.4, "in", stack.LIMIT_PRECISION)
    # Each limit pair carries the window its owner spec proves.
    assert stack.BACK_END_SUNK_LIMITS == (
        mg_wheel_axle_spec.BACK_END_SUNK_MIN,
        mg_wheel_axle_spec.BACK_END_SUNK_MAX,
    )
    # The plain end is where the press setting leaves it: a reference, so
    # DETAIL A sets the axle by the press gauge alone (Codjiflo r1, #3334).
    assert stack.REFERENCE_DIMENSIONS == {stack.BACK_END_SUNK_DIMENSION}
    assert stack.LIMIT_DIMENSIONS[stack.DRUM_RECESS_DIMENSION] == pytest.approx(
        mg_magnifying_wheel_geom.DRUM_RECESS, abs=1e-9
    )
    assert stack.LIMIT_DIMENSIONS[stack.THREAD_PAST_LOCKNUT_DIMENSION] == (
        mg_wheel_axle_spec.TIP_INCOMPLETE,
        mg_wheel_axle_spec.THREAD_PAST_LOCKNUT_LIMIT,
    )
    # DETAIL A imports the press settings; DETAIL B the stack's.
    assert set(drawing.PRESSED_KEEP) == {
        stack.PRESS_GAUGE_DIMENSION,
        stack.BACK_END_SUNK_DIMENSION,
    }
    assert set(drawing.ENDSHAKE_KEEP) == {
        stack.DRUM_RECESS_DIMENSION,
        stack.ENDSHAKE_DIMENSION,
        stack.THREAD_PAST_LOCKNUT_DIMENSION,
    }


def test_the_press_gauge_is_a_setting_accepted_at_the_nuts() -> None:
    # Owner ruling 2026-11-21: the gauge, .768 +/-.002 from the spacer's
    # outer face, is the press's setting. Its acceptance, read at the second
    # nut, prints as DETAIL B's thread-end limits (#2286 option A: farm
    # rounds 1-3 gated it as a DETAIL A callout, a view with no nut). A press
    # inside the band passes it at every corner.
    low = stack.PRESS_GAUGE - stack.PRESS_GAUGE_TOL
    high = stack.PRESS_GAUGE + stack.PRESS_GAUGE_TOL
    assert stack.PRESS_GAUGE_LOW_LIMIT / 25.4 == pytest.approx(0.764, abs=1e-6)
    assert stack.PRESS_GAUGE_HIGH_LIMIT / 25.4 == pytest.approx(0.771, abs=1e-6)
    assert stack.PRESS_GAUGE_LOW_LIMIT <= low < high <= stack.PRESS_GAUGE_HIGH_LIMIT
    assert stack.SETTING_CALLOUTS[stack.FEATURE][stack.PRESS_GAUGE_DIMENSION][
        1
    ].startswith("PRESS SETTING:")
    # The printed limits, in inches: the high side is the axle's own limit
    # and passes the worst stack; the low side keeps the locknut on full
    # thread, the dome's incomplete pitch past it, which the stack's low
    # corner holds (owner ruling 2026-11-06).
    low_limit, high_limit = stack.LIMIT_DIMENSIONS[stack.THREAD_PAST_LOCKNUT_DIMENSION]
    assert mg_wheel_group.THREAD_PAST_LOCKNUT_MAX <= high_limit
    assert low_limit == mg_wheel_axle_spec.TIP_INCOMPLETE
    assert mg_wheel_group.LOCKNUT_THREAD_MARGIN >= 0.0
    assert "LOCKNUT ON FULL THREAD" not in drawing.PRESSED.label_text
    assert stack.SETTING_CALLOUTS[stack.FEATURE][stack.THREAD_PAST_LOCKNUT_DIMENSION][
        1
    ].startswith("ACCEPTANCE:")
    assert "SETTING" not in stack.SETTING_CALLOUTS[stack.FEATURE][
        stack.BACK_END_SUNK_DIMENSION
    ][1]
    # The acceptance is checked on the trial stack, then again once both
    # nuts are set, where DETAIL B dimensions it, with a named instrument;
    # the step names the view, never the value.
    checked = notes.STEP_TEXT[steps.AXLE_CHECKED_KEY]
    assert notes.ENDSHAKE_DETAIL_TITLE in checked and "CALIPER DEPTH ROD" in checked
    assert notes.PRESS_DETAIL_TITLE not in checked
    assert not re.search(r"\.\d{3}", checked)
    accepted = steps.SEQUENCE.index(steps.AXLE_ACCEPTED_KEY)
    assert accepted > steps.SEQUENCE.index(steps.LOCKNUT_JAMMED_KEY)
    assert notes.STEP_TEXT[steps.AXLE_ACCEPTED_KEY].startswith("CHECK ")
    assert f"STEP {steps.step_number(steps.AXLE_CHECKED_KEY)}" in (
        notes.STEP_TEXT[steps.AXLE_ACCEPTED_KEY]
    )
    # The final reading has its own remedy: the stack comes off and the
    # failed trial's remedies run from the press re-check, so a stack that
    # passed the trial low is measured, not re-trialled (Codjiflo r1, #3345).
    assert steps.SEQUENCE[accepted + 1 : accepted + 3] == ("axle-stack-removed", "axle-reset")
    assert notes.STEP_TEXT["axle-reset"].endswith(
        f"RETURN TO STEP {steps.step_number('axle-press-rechecked')}."
    )
    # The endshake callout keeps one reason line; the steps carry the method.
    assert stack.SETTING_CALLOUTS[stack.FEATURE][stack.ENDSHAKE_DIMENSION] == (
        4, "WHEEL FREE, NO RATTLE"
    )
    # The press setting is the axle's one position (owner ruling 2026-11-21):
    # a failed acceptance reads the setting again and presses only back to
    # it, then replaces the stack part outside its limits; no re-press chases
    # the thread end past the DETAIL A band.
    (trial_step,) = (step for step in steps.STEPS if step[0] == steps.AXLE_TRIAL_KEY)
    # #3344: the trial jams its nuts over the endshake's go feeler, the
    # endshake the stack's thread-end corners are booked at, so a conforming
    # stack reads inside DETAIL B at the trial, and no less endshake follows.
    assert trial_step[:4] == (
        steps.AXLE_TRIAL_KEY,
        "trial-feeler-placed",
        "trial-nuts-jammed",
        steps.AXLE_CHECKED_KEY,
    )
    assert stack.ENDSHAKE - stack.ENDSHAKE_TOL == pytest.approx(
        mg_wheel_group.ENDSHAKE_MIN
    )
    trial_low, trial_high = (x / 25.4 for x in notes.TRIAL_THREAD_PAST_LOCKNUT)
    assert (trial_low, trial_high) == pytest.approx((0.031, 0.113), abs=1e-6)
    band = mg_wheel_group.ENDSHAKE_MAX - mg_wheel_group.ENDSHAKE_MIN
    # At the trial, and once the endshake is set anywhere in its band.
    assert low_limit <= notes.TRIAL_THREAD_PAST_LOCKNUT[0] - band
    assert notes.TRIAL_THREAD_PAST_LOCKNUT[1] <= high_limit
    feeler = f"THE {notes.ENDSHAKE_GO_TEXT} FEELER BETWEEN {notes._WASHER}"
    assert feeler in notes.STEP_TEXT["trial-feeler-placed"]
    assert "FEELER" in notes.STEP_TEXT["trial-nuts-jammed"]
    assert "JUST FREE" not in notes.STEP_TEXT["trial-nuts-jammed"]
    for key in ("trial-parts-removed-to-press", "trial-parts-removed"):
        assert "FEELER" in notes.STEP_TEXT[key]
    assert trial_step[4:] == (
        "trial-parts-removed-to-press",
        "axle-press-rechecked",
        "axle-repressed",
        "axle-rechecked",
        "stack-part-replaced",
        "trial-refitted",
        "axle-pressed-out-to-replace",
        "axle-replaced",
    )
    assert notes.PRESS_DETAIL_TITLE in notes.STEP_TEXT["axle-press-rechecked"]
    # The spacer the setting reads from is held to the bar at every reading.
    held = f"{notes._SPACER}, HELD AGAINST {notes._BAR}"
    assert held in notes.STEP_TEXT["axle-press-rechecked"]
    bond_held = f"{notes._SPACER} HELD AGAINST {notes._BAR}"
    assert bond_held in notes.STEP_TEXT["axle-bond-set"]
    assert "TO THAT SETTING" in notes.STEP_TEXT["axle-repressed"]
    assert not any(
        word in text for text in notes.STEP_TEXT.values() for word in ("EXCESS", "SHORTFALL")
    )
    assert notes.STEP_TEXT["axle-rechecked"].endswith(
        f"RETURN TO STEP {steps.step_number(steps.AXLE_HELD_KEY)}."
    )
    assert notes.STEP_TEXT["trial-refitted"].endswith(
        f"RETURN TO STEP {steps.step_number(steps.AXLE_TRIAL_KEY)}."
    )
    # The spacer the press gauges from goes on in a step of its own, before
    # the press (rule 22).
    order = steps.SEQUENCE
    assert order.index(steps.SPACER_FITTED_KEY) < order.index(steps.AXLE_PRESSED_KEY)
    assert notes.STEP_TEXT[steps.SPACER_FITTED_KEY].startswith(f"SLIDE {notes._SPACER} ")


def test_each_press_is_accepted_at_the_bench_with_a_slip_fit_remedy() -> None:
    """Rule 23: a press prints a bench acceptance and what a slip fit gets,
    each a lettered sub-step of the press (rule 22, the shared step lint)."""
    for pressed, held, taken_out, remedy in (
        (steps.AXLE_PRESSED_KEY, steps.AXLE_HELD_KEY, "axle-pressed-out", "axle-cleaned"),
    ):
        (step,) = (step for step in steps.STEPS if step[0] == pressed)
        assert step[1:4] == (held, taken_out, remedy)
        assert notes.STEP_TEXT[held].endswith("DOES NOT TURN OR SLIDE BY HAND.")
        # One action per step (rule 22): the slip test takes the part out,
        # the next step is the remedy.
        assert "BY HAND" in notes.STEP_TEXT[taken_out]
        assert notes.STEP_TEXT[taken_out].count(",") == 2
    # A slip axle is bonded under the one general bond note that prints with
    # the checks, rather than remade from the same as-supplied rod (owner
    # ruling 2026-11-11, #2541 and #2523, amending 2026-11-07).
    def ref(key: str) -> str:
        return f"STEP {steps.step_number(key)}"

    assert not any("REMAKE" in text for text in notes.STEP_TEXT.values())
    # The slip-axle remedies run in order inside step 2: press it out,
    # clean, bond, set, then back to the hold check once cured.
    (axle_step,) = (step for step in steps.STEPS if step[0] == steps.AXLE_PRESSED_KEY)
    assert axle_step[2:] == (
        "axle-pressed-out",
        "axle-cleaned",
        "axle-bonded",
        "axle-spacer-refitted",
        "axle-bond-set",
        "axle-bond-cured",
    )
    # Only an unbonded slip goes back out; a bonded axle that holds passes the
    # hold check once cured (#2579).
    assert "UNBONDED" in notes.STEP_TEXT["axle-pressed-out"]
    assert notes.STEP_TEXT["axle-bonded"].endswith(
        f"{notes.BOND_GRADE}, {notes.BOND_NOTE_REF}."
    )
    # #2578 is moot since the 2026-11-21 ruling: a bond is set inside its
    # fixture time to the DETAIL A setting, the axle's one position.
    bond_set = notes.STEP_TEXT["axle-bond-set"]
    assert "AT ONCE" in bond_set
    assert notes.PRESS_DETAIL_TITLE in bond_set
    assert "CALIPER DEPTH ROD" in bond_set
    assert notes.STEP_TEXT["axle-bond-cured"].startswith(
        f"IF IT WAS BONDED, RETURN TO {ref(steps.AXLE_HELD_KEY)}"
    )
    # Step 3's re-press comes back through the same hold check.
    assert notes.STEP_TEXT["axle-rechecked"].endswith(f"RETURN TO {ref(steps.AXLE_HELD_KEY)}.")
    assert notes.BOND_NOTE in notes.ASSEMBLY_CHECKS
    assert notes.BOND_NOTE.startswith(f"NOTE 1, {notes.BOND_GRADE} BOND:")
    # Rule 23's bond rules: prep, where it goes, the wiped excess, cure,
    # acceptance.
    for rule in ("DEGREASE", "ONLY", "WIPE", "CURE 24 H", "BY HAND"):
        assert rule in notes.BOND_NOTE


def test_the_drum_is_bonded_centred_wet_and_accepted_once_cured() -> None:
    """Owner ruling 2026-11-24, fit audit question 17: the drum is always
    bonded on the spigot turned to slide in its drilled bore, centred on an
    indicator while wet, and accepted at the bench once cured (rule 23)."""
    (drum_step,) = (step for step in steps.STEPS if step[0] == steps.DRUM_BONDED_KEY)
    assert drum_step == (
        steps.DRUM_BONDED_KEY,
        "drum-centred",
        "drum-bond-cured",
        steps.DRUM_HELD_KEY,
        "drum-stripped",
    )
    bonded = notes.STEP_TEXT[steps.DRUM_BONDED_KEY]
    assert f"WITH {notes.BOND_GRADE}, {notes.BOND_NOTE_REF}" in bonded
    assert "NONE IN THE BORE" in bonded
    centred = notes.STEP_TEXT["drum-centred"]
    assert centred.startswith("AT ONCE, BEFORE IT GRABS, TAP ")
    assert "INDICATOR" in centred and "V-BLOCK" in centred
    assert "24 H" in notes.STEP_TEXT["drum-bond-cured"]
    assert notes.STEP_TEXT[steps.DRUM_HELD_KEY].endswith("DOES NOT TURN OR SLIDE BY HAND.")
    assert notes.STEP_TEXT["drum-stripped"].startswith(
        f"IF IT DOES, RETURN TO STEP {steps.step_number(steps.DRUM_BONDED_KEY)} WITH "
    )


def test_the_axle_press_goes_to_the_gauge_past_the_spacer() -> None:
    """Owner ruling 2026-11-21 (fit at assembly): the press step sets the
    shoulder past the outer face of the spacer, slid on the shank against
    the bar, as DETAIL A dimensions it; the plain end's window below the
    bar's far face (the axle spec's limits) is where that press leaves it,
    and the thread-end check is the only acceptance (#2286 option A)."""
    low, high = stack.BACK_END_SUNK_LIMITS
    assert 0.0 < low < stack.BACK_END_D - stack.BAR_FAR_D < high
    pressed = notes.STEP_TEXT[steps.AXLE_PRESSED_KEY]
    assert (
        "UNTIL THE SHOULDER STANDS PAST THE OUTER FACE OF ITEM "
        f"{notes.ITEM_NUMBERS['mg-wheel-axle-spacer']}, HELD AGAINST "
        f"ITEM {notes.ITEM_NUMBERS['mg-wheel-bar']}, AS {notes.PRESS_DETAIL_TITLE} "
        "SETS IT" in pressed
    )
    # The spacer stays on from the press: the trial and final stacks start at
    # the back washer.
    for key in (steps.AXLE_TRIAL_KEY, "wheel-stacked", "axle-stack-removed"):
        assert f"{notes.ITEM_NUMBERS['mg-wheel-axle-spacer']}," not in notes.STEP_TEXT[key]
        assert f"AND {notes.ITEM_NUMBERS['mg-wheel-axle-spacer']}." not in notes.STEP_TEXT[key]
    assert "CALIPER DEPTH ROD" in pressed
    assert not re.search(r"\.\d{3}", pressed)
    assert "GOVERN" not in notes.STEP_TEXT[steps.AXLE_CHECKED_KEY]


def test_the_axle_presses_push_on_the_step_through_a_sleeve() -> None:
    """#2399: a press on the threaded end drives the interference through the
    relief neck. Both presses that drive the axle in push on its shank step
    through one sleeve that clears the thread and dome and lands on the
    step's flat."""
    from _printed_tolerance import (
        drilled_oversize_mm,
        edge_break_chamfer_mm,
        edge_break_radius_mm,
    )

    spec = mg_wheel_axle_spec
    inch = 25.4
    # The sleeve's bore at the title block's drilled limit still lands inside
    # the step's flat, a full edge break in.
    bore_max = notes.PRESS_SLEEVE_BORE + drilled_oversize_mm(unit=spec.UNIT)
    edge_break = max(
        edge_break_radius_mm(unit=spec.UNIT), edge_break_chamfer_mm(unit=spec.UNIT)
    )
    flat = spec.PIN_DIA - spec.PIN_DIA_TOL - 2.0 * edge_break
    assert spec.THREAD_MAJOR < notes.PRESS_SLEEVE_BORE < bore_max < flat
    assert notes.PRESS_SLEEVE_OD > spec.PIN_DIA + spec.PIN_DIA_TOL
    longest_tip = spec.THREAD_LEN + spec.THREAD_LEN_BAND[0] + spec.DOME_H
    assert notes.PRESS_SLEEVE_LENGTH > longest_tip
    # The top press force on the step stays inside the module's bearing
    # limit; on the neck it would be several times the yield.
    assert (
        notes.STEP_BEARING_MAX_KSI <= notes.BEARING_YIELD_FACTOR * notes.AXLE_YIELD_KSI
    )
    neck = math.pi / 4.0 * (spec.RELIEF_DIA_LIMITS[1] / inch) ** 2
    assert notes.PRESS_FORCE_MAX_KIP / neck > 3.0 * notes.AXLE_YIELD_KSI
    # Both presses that drive the axle in name the sleeve, which its own step
    # makes (rule 22: one action per step), as does the oil.
    assert notes.PRESS_SLEEVE in notes.STEP_TEXT[steps.PRESS_SLEEVE_MADE_KEY]
    sleeve = f"STEP {steps.step_number(steps.PRESS_SLEEVE_MADE_KEY)} SLEEVE"
    assert sleeve in notes.STEP_TEXT[steps.AXLE_PRESSED_KEY]
    assert sleeve in notes.STEP_TEXT["axle-repressed"]
    assert "OIL" not in notes.STEP_TEXT[steps.AXLE_PRESSED_KEY]
    assert "OIL" in notes.STEP_TEXT["axle-plain-end-oiled"]


def test_the_drum_bond_accepts_the_recess_window_the_wheel_lengths_prove() -> None:
    """Rule 22: the drum bond step reads the drum face's window below the
    spigot end (DRUM_RECESS) where DETAIL B dimensions it."""
    low, high = stack.LIMIT_DIMENSIONS[stack.DRUM_RECESS_DIMENSION]
    assert low == 0.0
    assert (low, high) == pytest.approx(mg_magnifying_wheel_geom.DRUM_RECESS, abs=1e-9)
    assert low < stack.DRUM_RECESS < high
    pressed = notes.STEP_TEXT[steps.DRUM_BONDED_KEY]
    assert "HARD AGAINST THE BOSS" in pressed
    assert (
        f"ITS OUTER FACE BELOW THE END OF THE SPIGOT AS {notes.ENDSHAKE_DETAIL_TITLE} SETS IT"
        in pressed
    )
    assert "CALIPER DEPTH ROD" in pressed


def test_each_hand_set_clamp_is_checked_to_hold_its_setting() -> None:
    """Rule 23 adjustable clamp: a thumb screw on the round, set and checked."""
    for set_key, held, reset in (
        (steps.CLAMP_SET_KEY, steps.CLAMP_HELD_KEY, "clamp-reset"),
        (steps.FIXTURE_SET_KEY, steps.FIXTURE_HELD_KEY, "fixture-reset"),
    ):
        held_at = steps.SEQUENCE.index(held)
        assert steps.SEQUENCE[held_at - 1].endswith("thumb-screw-tightened")
        assert steps.SEQUENCE[held_at + 1] == reset
        assert notes.STEP_TEXT[held].startswith("CHECK ")
        assert notes.STEP_TEXT[held].endswith(" BY HAND.")
        assert " DOES NOT SLIP ON " in notes.STEP_TEXT[held]
        assert notes.STEP_TEXT[reset].endswith(f"RETURN TO STEP {steps.step_number(set_key)}.")


def test_the_joints_left_loose_cite_the_mha_ha_00_step_that_seats_them() -> None:
    """Rule 23 across the package boundary: drawing and step, by number."""
    import ha_harmonic_analyzer_assembly_steps as ha_steps

    (step,) = (step for step in steps.STEPS if step[0] == steps.COLUMN_CLAMP_STARTED_KEY)
    assert any(ha_steps.step_ref("magnifier-bar-clamped") in notes.STEP_TEXT[key] for key in step[1:])
    assert any(
        ha_steps.step_ref("magnifier-bracket-screwed") in line
        for line in notes.ASSEMBLY_CHECKS
        if line.startswith("LOOSE ITEMS:")
    )


def test_every_printed_step_is_one_short_action_by_the_shared_lint() -> None:
    """Rule 22, offline, by the shared step lint (#2248): each step, wrapped
    at a 100-character line as ASSEMBLY.md is read, is at most six lines and
    one action, a check's remedies follow it as lettered sub-steps of its
    step, a press is followed by its hand check and slip-fit remedy, every
    step cite names a printed head, and every direction word is one the sheet
    defines. No step is allowlisted."""
    import textwrap

    from _test_assembly_steps import step_structure_violations

    printed = "\n".join(
        textwrap.fill(step, width=100, subsequent_indent="   ")
        for step in notes.ASSEMBLY_STEPS
    )
    # The direction words the steps use, each with its definition as printed:
    # a standard view name and a sense seen in a lettered view (rule 26).
    direction_key = "\n".join(
        phrase for phrase in ("RIGHT SIDE VIEW ON SHEET 1", "CLOCKWISE AS SEEN IN VIEW D")
        if phrase in " ".join(printed.split())
    )
    violations = step_structure_violations(
        {"STEP": (printed,)},
        reference_kinds={"STEP": "STEP"},
        direction_key=direction_key,
    )
    assert violations == [], "\n".join(violations)


def _circle_box(detail) -> tuple[float, float, float, float]:
    x, y = detail.centre
    r = detail.crop_radius
    return x - r, y - r, x + r, y + r


@pytest.mark.parametrize("detail", [drawing.PRESSED, drawing.ENDSHAKE])
def test_each_detail_sits_in_the_free_field_with_its_label_under_its_ink(
    detail,
) -> None:
    left, _bottom, right, top = _circle_box(detail)
    assert left > ISO_RIGHT
    assert right < SHEET_RIGHT
    assert top < SHEET_TOP
    label_x, label_top = detail.label_xy
    ink_bottom = detail.sheet_xy(detail.centre_d, -detail.ink_drop_mm)[1]
    # Just under the detail's lowest printed edge, not under its unprinted
    # crop circle.
    assert 0.002 <= ink_bottom - label_top <= 0.005
    # Its lines, about 4.5 mm each, clear the title block.
    lines = detail.label_text.splitlines()
    assert label_top - 0.0045 * len(lines) > TITLE_BLOCK_TOP
    assert left <= label_x


def test_the_pressed_detail_label_clears_the_endshake_crop() -> None:
    label = drawing.PRESSED.label_text
    # The pressed detail's three-line label still clears the endshake crop.
    lines = len(label.splitlines())
    assert (
        drawing.PRESSED.label_xy[1] - 0.0045 * lines > _circle_box(drawing.ENDSHAKE)[3]
    )


def test_each_detail_s_lowest_ink_is_its_geometry() -> None:
    import mg_magnifying_wheel_spec as wheel
    import mg_vn_wheel_axle_front_washer_spec as washer
    import mg_vn_wheel_axle_nut_spec as nut
    from mg_wheel_bar_geom import BAR_SIDE, BAR_TOP_ABOVE_ROW

    # The bar's underside: the row stands BAR_TOP_ABOVE_ROW under the top face.
    assert drawing.PRESSED.ink_drop_mm == pytest.approx(BAR_SIDE - BAR_TOP_ABOVE_ROW)
    # The circle's chord at the spigot face: the spigot fills it there, and
    # the nuts and washer beside it stand higher.
    detail = drawing.ENDSHAKE
    offset = detail.centre_d - stack.HUB_FRONT_D
    assert detail.ink_drop_mm == pytest.approx(
        math.sqrt(detail.radius_mm**2 - offset**2)
    )
    assert detail.ink_drop_mm < wheel.SPIGOT_DIA / 2.0
    assert max(nut.ACROSS_CORNERS, washer.OD) / 2.0 < detail.ink_drop_mm


def test_the_details_and_labels_do_not_overlap() -> None:
    upper_label_bottom = drawing.PRESSED.label_xy[1] - 0.009
    assert _circle_box(drawing.ENDSHAKE)[3] < upper_label_bottom


@pytest.mark.parametrize("feature", [stack.FEATURE, stack.LEVER_FEATURE, stack.THREAD_FEATURE])
@pytest.mark.parametrize("failed_readback", [False, True])
def test_native_setting_text_requires_void_setter_readback(
    monkeypatch, feature, failed_readback
) -> None:
    class Display:
        def __init__(self):
            self.text = {}

        def SetText(self, part, text):
            assert part in (3, 4)  # Never replace the live dimension value.
            if not failed_readback:
                self.text[part] = text
            # The native setter returns void, including when text is unchanged.

        def GetText(self, part):
            return self.text.get(part, "").replace("\n", "\r\n")

    displays = {name: Display() for name in stack.SETTING_CALLOUTS[feature]}
    monkeypatch.setattr(
        assembly,
        "_named_dimension",
        lambda _adapter, _owner, name: (displays[name], object()),
    )
    if failed_readback:
        with pytest.raises(RuntimeError, match="native setting callout reads"):
            assembly._author_setting_callouts(object(), feature)
    else:
        assembly._author_setting_callouts(object(), feature)


def test_each_detail_frames_both_ends_of_its_dimensions() -> None:
    legs = dict(zip(stack.CHAIN_LEG_DIMENSIONS, zip(stack.CHAIN_D, stack.CHAIN_D[1:])))
    for detail, keep in (
        (drawing.PRESSED, drawing.PRESSED_KEEP),
        (drawing.ENDSHAKE, drawing.ENDSHAKE_KEEP),
    ):
        for name in keep:
            for d in legs[name]:
                assert abs(d - detail.centre_d) < detail.radius_mm, (detail.title, name, d)


def test_the_limit_texts_stand_outside_the_parts_clear_of_their_neighbours() -> None:
    import mg_vn_wheel_axle_nut_spec as nut

    # The callouts' longest line, "PLAIN END BELOW", prints about 36 mm wide;
    # an extension line overshoots its dimension line by about 1.5 mm.
    half_width = 0.018
    overshoot = 0.0015
    # The text position sits half its block above the dimension line.
    assert drawing.text_over_line(stack.ENDSHAKE_DIMENSION, 0.0) == pytest.approx(
        2 * drawing.DIM_TEXT_HALF_LINE
    )
    assert drawing.text_over_line(stack.THREAD_PAST_LOCKNUT_DIMENSION, 0.0) == pytest.approx(
        5 * drawing.DIM_TEXT_HALF_LINE
    )
    # DETAIL A: left of the bar's far face, its line level with the gauge's,
    # clear of the isometric and of the bar's far-face extension line.
    x, y = drawing.PRESSED_KEEP[stack.BACK_END_SUNK_DIMENSION]
    far_x = drawing.PRESSED.sheet_xy(stack.BAR_FAR_D)[0]
    assert ISO_RIGHT < x - half_width and x + half_width < far_x
    assert y == pytest.approx(
        drawing.text_over_line(stack.BACK_END_SUNK_DIMENSION, drawing.GAUGE_LINE_Y)
    )
    assert y + drawing.text_over_line(stack.BACK_END_SUNK_DIMENSION, 0.0) < SHEET_TOP
    # DETAIL B: both lines run under the nuts' corners and over the detail's
    # label, extension overshoot included; the drum recess's text left of
    # the circle, the thread end's right of it, both under the endshake's
    # dimension line.
    line_y = drawing.STACK_LINE_Y
    centre_y = drawing.ENDSHAKE.centre[1]
    assert centre_y - line_y > nut.ACROSS_CORNERS / 2.0 * drawing.ENDSHAKE.mm
    assert line_y - overshoot > drawing.ENDSHAKE.label_xy[1] + 0.002
    endshake_line = drawing.ENDSHAKE_KEEP[stack.ENDSHAKE_DIMENSION][1] - drawing.text_over_line(
        stack.ENDSHAKE_DIMENSION, 0.0
    )
    box = _circle_box(drawing.ENDSHAKE)
    for name, side in (
        (stack.DRUM_RECESS_DIMENSION, -1),
        (stack.THREAD_PAST_LOCKNUT_DIMENSION, 1),
    ):
        x, y = drawing.ENDSHAKE_KEEP[name]
        assert y == pytest.approx(drawing.text_over_line(name, line_y))
        assert (x < box[0]) if side < 0 else (x > box[2])
        assert y + drawing.text_over_line(name, 0.0) < endshake_line - 0.004
    assert drawing.ENDSHAKE_KEEP[stack.DRUM_RECESS_DIMENSION][0] - half_width > ISO_RIGHT
    assert drawing.ENDSHAKE_KEEP[stack.THREAD_PAST_LOCKNUT_DIMENSION][0] + half_width < SHEET_RIGHT


def test_the_gauge_line_clears_the_bar_inside_the_crop() -> None:
    from mg_wheel_bar_geom import BAR_TOP_ABOVE_ROW

    assert BAR_TOP_ABOVE_ROW + 5.0 <= drawing.GAUGE_RISE < drawing.PRESSED.radius_mm
    x, y = drawing.PRESSED_KEEP[stack.PRESS_GAUGE_DIMENSION]
    assert math.dist((x, y), drawing.PRESSED.centre) < drawing.PRESSED.crop_radius


def test_the_endshake_line_rides_above_the_nuts_and_text_stands_past_the_crop() -> None:
    import mg_vn_wheel_axle_front_washer_spec as washer
    import mg_vn_wheel_axle_nut_spec as nut

    assert max(nut.ACROSS_CORNERS, washer.OD) / 2.0 < drawing.ENDSHAKE_RISE
    x, _y = drawing.ENDSHAKE_KEEP[stack.ENDSHAKE_DIMENSION]
    assert x > _circle_box(drawing.ENDSHAKE)[2]
    assert x + 0.030 < SHEET_RIGHT


def test_detail_a_breaks_out_the_plain_end_inside_the_bar() -> None:
    """Issue #3031 (rule 9): BackEndSunk ends on the axle's plain end, sunk
    in the bar's bore, so DETAIL A cuts a window from the bar's +x end to the
    axle's mid-plane over the far face and the plain end; it stays inside the
    bar's faces and the crop, and only DETAIL A is broken out."""
    from mg_wheel_bar_geom import (
        AXLE_BORE_DIA,
        BAR_LENGTH,
        BAR_TOP_ABOVE_ROW,
        BORE_ROW_HEIGHT,
        WHEEL_BAR_X0,
    )

    assert drawing.PRESSED.break_out and not drawing.ENDSHAKE.break_out
    assert stack.BAR_FAR_D < stack.BACK_END_D < 0.0
    ds = [d for d, _rise in drawing.BREAK_OUT_WINDOW_MM]
    rises = [rise for _d, rise in drawing.BREAK_OUT_WINDOW_MM]
    assert min(ds) < stack.BAR_FAR_D - 1.0
    assert max(ds) > stack.BACK_END_D + 1.0
    assert min(max(rises), -min(rises)) * 0.92 > AXLE_BORE_DIA / 2.0 + 1.0
    assert max(rises) < BAR_TOP_ABOVE_ROW
    assert -min(rises) < BORE_ROW_HEIGHT
    for d, rise in drawing.BREAK_OUT_WINDOW_MM:
        assert math.hypot(d - drawing.PRESSED.centre_d, rise) < drawing.PRESSED.radius_mm
    # Cut from the bar's +x end (nearest the MG LEFT viewer) to the axle line.
    assert WHEEL_BAR_X0 + BAR_LENGTH / 2.0 - drawing.BREAK_OUT_DEPTH == pytest.approx(
        stack.AXLE_X
    )
    assert 0.0 < drawing.PLAIN_END_PICK_RISE < mg_wheel_axle_spec.PIN_DIA / 2.0 - 0.5


def test_break_out_plain_end_cuts_one_window_and_picks_the_end(monkeypatch) -> None:
    events = []
    detail = drawing.PRESSED
    native = SimpleNamespace(GetBreakOutSectionCount=lambda: 1)
    segment = SimpleNamespace(
        Select4=lambda append, data: events.append(("select", append, data.View)) or True
    )

    def sketch(_adapter, view, kind, points, *, label):
        events.append(("sketch", view, kind, points))
        return segment

    draw = SimpleNamespace(
        SelectionManager=SimpleNamespace(CreateSelectData=lambda: SimpleNamespace()),
        CreateBreakOutSection=lambda depth: events.append(("cut", depth)) or True,
        ClearSelection2=lambda _all: events.append(("clear",)),
    )
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _iface: value)
    monkeypatch.setattr(drawing, "_sketch_in_view", sketch)
    monkeypatch.setattr(
        drawing, "rebuild_drawing", lambda _adapter, *, label: events.append(("rebuild",))
    )
    monkeypatch.setattr(
        drawing,
        "_pick_view_edge",
        lambda _adapter, view, xy, *, label: events.append(("pick", view, xy)),
    )
    drawing._break_out_plain_end(SimpleNamespace(currentModel=draw), native, detail)
    window = tuple(detail.sheet_xy(d, rise) for d, rise in drawing.BREAK_OUT_WINDOW_MM)
    assert events == [
        ("sketch", native, "spline", (*window, window[0])),
        ("select", False, native),
        ("cut", drawing.BREAK_OUT_DEPTH / 1000.0),
        ("clear",),
        ("rebuild",),
        ("pick", native, detail.sheet_xy(stack.BACK_END_D, drawing.PLAIN_END_PICK_RISE)),
    ]


@pytest.mark.parametrize("detail", [drawing.PRESSED, drawing.ENDSHAKE])
def test_only_detail_a_is_broken_out_after_its_chain_and_import(monkeypatch, detail) -> None:
    """Run 20261117T152043680Z: a view holding a broken-out section no
    longer selects its chain sketch to show it, so the breakout follows the
    import."""
    order = []
    keep = drawing.PRESSED_KEEP if detail is drawing.PRESSED else drawing.ENDSHAKE_KEEP
    annotations = [SimpleNamespace(name=name) for name in keep]
    view = SimpleNamespace(GetAnnotations=lambda: annotations)
    monkeypatch.setattr(drawing, "_placed_detail", lambda *_a: order.append("place") or view)
    monkeypatch.setattr(
        drawing, "_break_out_plain_end", lambda *_a: order.append("break out")
    )
    monkeypatch.setattr(
        drawing, "_show_base_view_sketches", lambda *_a, **_k: order.append("chain")
    )
    monkeypatch.setattr(
        drawing, "curate_view_dimensions", lambda *_a, **_k: order.append("import") or annotations
    )
    monkeypatch.setattr(drawing, "_crop", lambda *_a: order.append("crop"))
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _iface: value)
    monkeypatch.setattr(drawing, "dimension_name", lambda _adapter, item: item.name)
    monkeypatch.setattr(drawing, "_activate", lambda *_a, **_k: None)
    monkeypatch.setattr(drawing, "add_note", lambda *_a: order.append("label") or object())
    assert drawing._dimensioned_detail(object(), detail, keep) == annotations
    cut = ["break out"] if detail.break_out else []
    assert order == ["place", "chain", "import", *cut, "crop", "label"]


def test_the_gauge_detail_shows_only_the_bar_the_axle_and_the_spacer() -> None:
    assert drawing.PRESSED.stems == {"mg-wheel-bar", "mg-wheel-axle", "mg-wheel-axle-spacer"}
    assert {
        "mg-vn-wheel-axle-front-washer",
        "mg-vn-wheel-axle-nut",
        "mg-magnifying-wheel",
    } <= (drawing.ENDSHAKE.stems)


def test_the_stack_chain_is_authored_on_the_axle_and_driven_from_globals(
    monkeypatch,
) -> None:
    """Run the builder's chain helper against fakes: every authoring step must
    execute, the chain must lie on the axle line through the nine stations,
    the banded setting must carry its band and the limit settings their
    limits."""
    from types import SimpleNamespace

    import build_mg_magnifier_assembly as builder

    ok = lambda data=None: SimpleNamespace(is_success=True, data=data, error=None)  # noqa: E731
    lines: list[tuple[float, ...]] = []
    globals_authored: dict[str, str] = {}
    equations: dict[str, str] = {}
    toleranced: list[tuple] = []
    limited: list[tuple] = []
    lengths: dict[str, float] = {}
    blanked: list[str] = []

    class Adapter:
        _sketch_entities: dict[str, object] = {}
        currentModel = object()

        def create_sketch(self, plane):
            assert plane == "Right"
            return ok()

        def add_line(self, *coords):
            name = f"leg{len(lines)}"
            lines.append(coords)
            self._sketch_entities[name] = object()
            return ok(name)

        def add_sketch_constraint(self, *args):
            return ok()

        def exit_sketch(self):
            return ok()

    class Dims:
        def __init__(self):
            self.rows = []

        def record(self, name, drive=None):
            self.rows.append((name, drive))

        def apply(self, adapter, feature):
            return [(f"{name}@{feature}", drive) for name, drive in self.rows if drive]

    def early_bound(entity, iface):
        if iface == "IAssemblyDoc":
            return SimpleNamespace(FeatureByName=lambda name: name)
        if iface == "IFeature":
            return SimpleNamespace(Visible=1 if entity in blanked else 2)
        if iface == "IDimensionTolerance":
            return entity
        return SimpleNamespace(ConstructionGeometry=False)

    def set_global(adapter, name, expression):
        globals_authored[name] = expression

    def drive_dimension(adapter, name, expression):
        equations[name] = expression

    def dimension_between(adapter, a, b, kind, value, name):
        lengths[name] = value

    def noop(*args, **kwargs):
        return None

    monkeypatch.setattr(builder, "set_global", set_global)
    monkeypatch.setattr(builder, "drive_dimension", drive_dimension)
    monkeypatch.setattr(builder, "dimension_between", dimension_between)
    monkeypatch.setattr(builder, "SketchDims", Dims)
    monkeypatch.setattr(builder, "_early_bound", early_bound)
    for name in ("anchor_point_to_origin", "ensure_fully_defined"):
        monkeypatch.setattr(builder, name, noop)
    for name in (
        "set_sketch_direct_db",
        "name_last_feature",
        "apply_drawing_precision",
        "mark_dimensions_for_drawing",
        "_author_setting_callouts",
    ):
        monkeypatch.setattr(builder, name, lambda *a, **kw: None)
    references = {}

    def named_dimension(_adapter, feature, name):
        parts = {}
        display = SimpleNamespace(
            ShowParenthesis=True,
            SetText=parts.__setitem__,
            GetText=lambda part: parts.get(part, ""),
        )
        dimension = SimpleNamespace(Tolerance=SimpleNamespace(Type=4))
        references[(feature, name)] = (display, dimension, parts)
        return display, dimension

    monkeypatch.setattr(builder, "_named_dimension", named_dimension)
    monkeypatch.setattr(
        builder,
        "set_dimension_symmetric_tolerance",
        lambda adapter, feature, name, tol, **_kw: toleranced.append(
            (feature, name, tol)
        ),
    )
    monkeypatch.setattr(
        builder,
        "set_limits",
        lambda adapter, feature, name, *, limits, places, display_unit: limited.append(
            (feature, name, limits, places, display_unit)
        ),
    )
    monkeypatch.setattr(
        builder, "blank_sketch", lambda adapter, feature: blanked.append(feature)
    )

    builder._author_axle_stack_reference(Adapter())

    # Right-plane sketch x is machine -z: the chain runs forward from the bar's
    # far face along the axle's height.
    stations = [-stack.BAR_FRONT_Z + d for d in stack.CHAIN_D]
    assert lines == [
        (x0, stack.AXLE_Y, x1, stack.AXLE_Y) for x0, x1 in zip(stations, stations[1:])
    ]
    assert lengths[stack.PRESS_GAUGE_DIMENSION] == pytest.approx(stack.PRESS_GAUGE)
    assert lengths[stack.ENDSHAKE_DIMENSION] == pytest.approx(stack.ENDSHAKE)
    assert lengths[stack.DRUM_RECESS_DIMENSION] == pytest.approx(stack.DRUM_RECESS)
    assert lengths[stack.BACK_END_SUNK_DIMENSION] == pytest.approx(
        stack.BACK_END_D - stack.BAR_FAR_D
    )
    assert lengths[stack.THREAD_PAST_LOCKNUT_DIMENSION] == pytest.approx(
        stack.THREAD_END_D - stack.LOCKNUT_FACE_D
    )
    feature = stack.FEATURE
    assert equations == {
        f"StackFaceX@{feature}": '"AxleBarFrontFace"',
        f"StackAxisY@{feature}": '"AxleAxisY"',
        f"{stack.BACK_END_SUNK_DIMENSION}@{feature}": '"AxleBackEndSunk"',
        f"PlainEndToFrontFace@{feature}": '"AxleBarDepth" - "AxleBackEndSunk"',
        f"FrontFaceToSpacerFace@{feature}": '"AxleSpacerLength"',
        f"{stack.PRESS_GAUGE_DIMENSION}@{feature}": '"AxlePressGauge"',
        f"StepToDrumFace@{feature}": (
            '"HubFrontStation" - "AxleSpacerLength" - "AxlePressGauge" - "WheelDrumRecess"'
        ),
        f"{stack.DRUM_RECESS_DIMENSION}@{feature}": '"WheelDrumRecess"',
        f"{stack.ENDSHAKE_DIMENSION}@{feature}": '"WheelEndshake"',
        f"WasherToLocknutFace@{feature}": (
            '"LocknutFaceStation" - "HubFrontStation" - "WheelEndshake"'
        ),
        f"{stack.THREAD_PAST_LOCKNUT_DIMENSION}@{feature}": '"AxleThreadPastLocknut"',
    }
    assert globals_authored == {
        "AxleBarFrontFace": f"{-stack.BAR_FRONT_Z}mm",
        "AxleAxisY": f"{stack.AXLE_Y}mm",
        "AxleBarDepth": f"{-stack.BAR_FAR_D}mm",
        "AxleBackEndSunk": f"{stack.BACK_END_D - stack.BAR_FAR_D}mm",
        "AxleSpacerLength": f"{stack.SPACER_FACE_D}mm",
        "AxlePressGauge": f"{stack.PRESS_GAUGE}mm",
        "WheelDrumRecess": f"{stack.DRUM_RECESS}mm",
        "HubFrontStation": f"{stack.HUB_FRONT_D}mm",
        "WheelEndshake": f"{stack.ENDSHAKE}mm",
        "LocknutFaceStation": f"{stack.LOCKNUT_FACE_D}mm",
        "AxleThreadPastLocknut": f"{stack.THREAD_END_D - stack.LOCKNUT_FACE_D}mm",
    }
    # The globals close the chain: every station equals its spec value.
    total = 0.0
    for name, (start, end) in zip(
        stack.CHAIN_LEG_DIMENSIONS, zip(stack.CHAIN_D, stack.CHAIN_D[1:])
    ):
        assert lengths[name] == pytest.approx(end - start)
        total += lengths[name]
    assert total == pytest.approx(stack.CHAIN_D[-1] - stack.CHAIN_D[0])
    assert toleranced == [
        (feature, name, band) for name, band in stack.DIMENSION_TOLERANCES.items()
    ]
    assert limited == [
        (feature, name, limits, stack.LIMIT_PRECISION, stack.UNIT)
        for name, limits in stack.LIMIT_DIMENSIONS.items()
    ]
    assert blanked == [feature]
    # The plain end is a bare reference, (value) with no band (Codjiflo r1,
    # #3334); the banded and limit settings get no affixes.
    for (_feature, name), (display, dimension, parts) in references.items():
        if name in stack.REFERENCE_DIMENSIONS:
            assert dimension.Tolerance.Type == 0
            assert display.ShowParenthesis is False
            assert parts == {1: "(", 2: ")"}
        else:
            assert parts == {}
    assert stack.REFERENCE_DIMENSIONS <= {name for _f, name in references}


def test_the_package_has_five_landscape_sheets_with_view_d_on_sheet_5() -> None:
    assert drawing.SHEET_NAMES[3] == "FINISHED ASSEMBLY"
    assert drawing.SHEET_NAMES[-1] == "WHEEL AT REST"
    assert len(drawing.SHEET_NAMES) == 5
    assert set(drawing.SHEET_LAYOUTS.values()) == {DrawingLayout.LANDSCAPE}
    assert set(drawing.SHEET_SCALES) == set(drawing.SHEET_NAMES)
    # The fit-up steps print in the release's ASSEMBLY.md (#2889), not on a
    # sheet; VIEW D, which the wire steps cite, prints alone on sheet 5 at
    # its own scale.
    assert notes.WHEEL_REST_VIEW_SHEET == len(drawing.SHEET_NAMES)
    assert drawing.SHEET_SCALES[drawing.SHEET_NAMES[-1]] == drawing.WHEEL_REST_SCALE
    assert steps.SEQUENCE[-1] == steps.WIRE_TIED_KEY


def test_the_drawing_key_reads_only_the_package_parts_config() -> None:
    # The builder's COM explode (_mg_magnifier_explode -> _assembly_patterns ->
    # _assembly) reads every parts/* and assemblies/* YAML, so importing it
    # re-keyed this sheet on any part edit. The drawing reads the pure spec
    # (which reads its own contract's drawing_unit, as MHA-MS-00's sheet does).
    from pathlib import Path

    import _buildgraph

    script = Path(drawing.__file__)
    names = {Path(dep).name for dep in _buildgraph.module_deps_of(script)}
    assert not names & {
        "_assembly.py",
        "_assembly_patterns.py",
        "_mg_magnifier_explode.py",
    }
    assert not _buildgraph.config_files_of(script) & {"parts/*", "**"}


def test_the_wire_balloon_lands_on_the_mid_run_ring_facing_the_viewer() -> None:
    import math

    import sh_vn_music_wire_lever_geom as wire

    x, station, z = drawing.WIRE_BALLOON_POINT_MM
    # On the build's split ring, mid-run, on the wire's surface.
    assert station == pytest.approx(
        drawing.sh_vn_music_wire_lever_spec.BALLOON_RING_FRACTION * wire.WIRE_LEN
    )
    assert station == pytest.approx(wire.WIRE_LEN / 2.0)
    assert math.hypot(x, z) == pytest.approx(wire.MEMBER_DIA / 2.0)
    assert drawing.BALLOON_ANCHORS[drawing.WIRE_ROW].point_mm == drawing.WIRE_BALLOON_POINT_MM
    # Turned into the machine frame, the point's outward normal faces +X+Y+Z.
    delta = [h - d for h, d in zip(wire.WIRE_START, wire.WIRE_END)]
    axis = [v / math.hypot(*delta) for v in delta]
    n = math.hypot(axis[0], axis[1])
    ex = (axis[1] / n, -axis[0] / n, 0.0)
    ez = (
        ex[1] * axis[2] - ex[2] * axis[1],
        ex[2] * axis[0] - ex[0] * axis[2],
        ex[0] * axis[1] - ex[1] * axis[0],
    )
    normal = [x * a + z * b for a, b in zip(ex, ez)]
    viewer = [1.0 / math.sqrt(3.0)] * 3
    facing = sum(a * b for a, b in zip(normal, viewer)) / math.hypot(*normal)
    along = sum(a * b for a, b in zip(axis, viewer))
    # All of the viewer direction square to the axis points at the ring point.
    assert facing == pytest.approx(math.sqrt(1.0 - along**2))


def test_the_wire_wrap_has_the_required_geometric_margin() -> None:
    assert mg_wheel_group.LEVER_WIRE_WRAP_LEFT_DEG >= mg_wheel_group.WRAP_MARGIN_DEG


def test_the_wire_tie_step_sets_tie_1_at_its_modelled_rest_angle() -> None:
    import mg_magnifying_wheel_geom as wheel

    # VIEW D dimensions TIE 1's axis line from the wheel bar's bottom edge;
    # at the wheel model's rest pose that angle is TIE 1's, midway between
    # two spokes, so the wire is tied in the state its wrap is proved in.
    assert notes.TIE1_ANGLE_DEG == pytest.approx(
        -math.degrees(math.atan2(wheel.TIE1_Y, wheel.TIE1_X))
    )
    assert drawing.TIE1_DIRECTION == pytest.approx(
        (wheel.TIE1_X / math.hypot(wheel.TIE1_X, wheel.TIE1_Y),
         wheel.TIE1_Y / math.hypot(wheel.TIE1_X, wheel.TIE1_Y))
    )
    step = notes.STEP_TEXT[steps.WHEEL_TURNED_KEY]
    assert "VIEW D" in step and notes.WIRE_TIE_HOLE in step and "PROTRACTOR" in step
    printed = " ".join((*notes.ASSEMBLY_STEPS, *notes.ASSEMBLY_CHECKS))
    assert "O'CLOCK" not in printed
    # Rule 26: the hole by its plain name, never the coined TIE 1 label.
    assert "TIE 1" not in printed and drawing.TIE1_LABEL == notes.WIRE_TIE_HOLE
    # The vertex lies on the bar's bottom edge, the picks beyond it.
    vx, vy = drawing.TIE1_VERTEX_MM
    assert vy == -drawing.BORE_ROW_HEIGHT
    assert vy / vx == pytest.approx(wheel.TIE1_Y / wheel.TIE1_X)


def test_the_lettered_views_are_marked_on_the_right_side_view() -> None:
    # Every lettered view has its mark: DETAIL A and B their boundaries,
    # VIEW C and VIEW D their viewing arrows; no view is named in prose.
    assert (drawing.PRESSED.letter, drawing.ENDSHAKE.letter) == ("A", "B")
    assert [arrow.letter for arrow in drawing.VIEW_ARROWS] == ["C", "D"]
    assert drawing.LEVER_TIP.title == "VIEW C"
    assert drawing.WHEEL_REST.title == "VIEW D"
    assert drawing.VIEW_ARROWS[1].sheet_ref == "(SHEET 5)"
    # Each arrow looks from the machine front (-z): its tip stands just in
    # front of the ink it names, the lever's clamp and the axle's nuts.
    lever_z = assembly.LEVER_ROD_Z
    assert lever_z - drawing.CLAMP_HEX_AF < drawing.VIEW_ARROWS[0].tip_mm[2]
    assert drawing.VIEW_ARROWS[0].tip_mm[2] < lever_z - drawing.CLAMP_HEX_AF / 2.0
    assert drawing.VIEW_ARROWS[1].tip_mm[2] < stack.BAR_FRONT_Z - stack.HUB_FRONT_D
    for text in (
        drawing.LEVER_TIP.label_text,
        drawing.WHEEL_REST.label_text,
        drawing.PRESSED.label_text,
        drawing.ENDSHAKE.label_text,
    ):
        assert "VIEW FROM" not in text
    # Each detail's letter stands outside its boundary toward its corner.
    for detail in (drawing.PRESSED, drawing.ENDSHAKE):
        left, top = drawing.boundary_letter_xy((0.0, 0.0), 0.010, detail.letter_corner)
        box = (left, top - drawing.LETTER_BOX[1], left + drawing.LETTER_BOX[0], top)
        nearest = (
            min(max(0.0, box[0]), box[2]) if box[0] > 0 or box[2] < 0 else 0.0,
            min(max(0.0, box[1]), box[3]) if box[1] > 0 or box[3] < 0 else 0.0,
        )
        assert math.hypot(*nearest) > 0.010


def test_every_step_is_numbered_in_sequence() -> None:
    assert tuple(notes.STEP_TEXT) == steps.SEQUENCE
    assert notes.ASSEMBLY_STEPS == tuple(
        f"{steps.step_number(key)}. {notes.STEP_TEXT[key]}" for key in steps.SEQUENCE
    )


def test_the_lever_settings_match_the_placed_lever_group() -> None:
    assert stack.LEVER_TIP_X == pytest.approx(assembly.LEVER_X0)
    assert stack.LEVER_AXIS_Y == pytest.approx(assembly.LEVER_ROD_Y)
    assert stack.CLAMP_CENTRE_X == pytest.approx(assembly.CLAMP_X)
    assert stack.FIXTURE_AXIS_Y == pytest.approx(assembly.FIXTURE_POSITION[1])
    assert stack.CLAMP_STATION > 0.0 and stack.FIXTURE_DROP > 0.0
    assert stack.LEVER_DRAWING_DIMENSIONS == {
        stack.LEVER_FEATURE: {stack.CLAMP_STATION_DIMENSION, stack.FIXTURE_DROP_DIMENSION}
    }


def test_detail_direction_exposes_the_nose_instead_of_the_occluding_flange():
    import magnifying_bracket_joint_layout as joint

    detail = drawing.LEVER_TIP
    radius_mm = detail.crop_radius * 1000 * detail.scale[1] / detail.scale[0]
    x = (stack.THREADED_TIP_X + stack.THREAD_FAR_FACE_X) / 2
    y = stack.LEVER_AXIS_Y
    # The entire former Front crop lies inside the nearer flange's footprint.
    assert joint.SIDE_PLATE_MACHINE_X[0] < x - radius_mm < x + radius_mm < joint.SIDE_PLATE_MACHINE_X[1]
    assert joint.BRACKET_ORIGIN[1] + joint.SIDE_PLATE_Y[0] < y - radius_mm
    assert y + radius_mm < joint.BRACKET_ORIGIN[1] + joint.SIDE_PLATE_Y[1]
    flange_near_z = joint.BRACKET_ORIGIN[2] + joint.SIDE_PLATE_Z[0]
    assert flange_near_z > assembly.LEVER_ROD_Z + drawing.LEVER_ROD_DIA / 2
    # Standard Front now captures old Back, without changing the installation.
    assert detail.orientation == "*Front"
    assert detail.scale == (4, 1)
    from mg_lever_thread_joint import NOSE_R
    assert assembly.LEVER_ROD_Z - NOSE_R < flange_near_z
    assert drawing.VIEW_ARROWS[0].letter == detail.title.removeprefix("VIEW ")


def test_step_seven_uses_the_actual_detail_and_attached_qualifier():
    # The step names the view whose attached callout sets the projection and
    # the instrument that reads it; the value stays on the view.
    step = notes.STEP_TEXT[steps.LEVER_THREADED_KEY]
    assert drawing.LEVER_TIP.title in step
    assert "CALIPER DEPTH ROD" in step
    assert f"ITEM {notes.ITEM_NUMBERS['mg-magnifying-lever']} " in step
    assert f"ITEM {notes.ITEM_NUMBERS['mg-magnifying-bracket']} " in step
    assert "THREAD PROJECTION" not in step
    assert "1.25" not in step


def test_the_explode_moves_every_shown_family_but_the_wire_in_one_group() -> None:
    moved = {
        explode.member_stem(member)
        for step in explode.EXPLODE_STEPS
        for member in step.members
    }
    # The bar with its pressed axle, and the lever with its clamp, stay put
    # as each group's base; everything else moves.
    assert moved == explode.SHOWN_STEMS - {
        explode.WIRE_STEM,
        "mg-wheel-bar",
        "mg-wheel-axle",
        "mg-magnifying-lever",
        "mg-magnifying-clamp",
    }
    assert explode.WHEEL_GROUP_STEMS.isdisjoint(explode.LEVER_GROUP_STEMS)
    assert explode.SHOWN_STEMS == set(notes.BOM_ORDER)


def test_plan_explode_resolves_instances_and_refuses_missing_ones() -> None:
    instances = [
        explode.Instance(f"{stem}-{number}", stem)
        for stem in notes.BOM_ORDER
        for number in range(1, notes.QUANTITIES[stem] + 1)
    ]
    plan = explode.plan_explode(instances)
    assert [step for step, _names in plan] == list(explode.EXPLODE_STEPS)
    for step, names in plan:
        assert names, step.label
        for name in names:
            assert explode.member_stem(name.rsplit("-", 1)[0]) in {
                explode.member_stem(member) for member in step.members
            }
    first_nut = next(
        names for step, names in plan if step.members == ("mg-vn-wheel-axle-nut:1",)
    )
    assert first_nut == ("mg-vn-wheel-axle-nut-1",)
    with pytest.raises(ValueError, match="absent"):
        explode.plan_explode([i for i in instances if i.stem != "mg-output-fixture"])
    with pytest.raises(ValueError, match="no instance"):
        explode.plan_explode([i for i in instances if i.name != "mg-vn-wheel-axle-nut-2"])


def test_the_bom_rows_are_the_registry_parts_with_their_skus() -> None:
    assert drawing.BOM_COMPONENTS == tuple(
        drawing.BOM_ROW_KEYS[stem] for stem in notes.BOM_ORDER
    )
    assert set(notes.BOM_DESCRIPTIONS) == set(notes.BOM_ORDER)
    for stem, row in drawing.PART_ROWS.items():
        assert drawing.BOM_PART_NUMBERS[stem] == row["number"]
        skus = row.get("supplier_skus") or ()
        assert drawing.BOM_SKUS[stem] == (" / ".join(skus) if skus else "-")
    assert drawing.BOM_SKUS["sh-vn-thumb-screw"] == "91882A221"
    assert drawing.BOM_SKUS["mg-magnifying-lever"] == "-"
    assert notes.QUANTITIES["sh-vn-thumb-screw"] == 2


def test_the_bom_screw_lengths_are_the_vendor_specs_fractions() -> None:
    import sh_vn_clamp_screw_spec as clamp_screw
    import mg_vn_magnifying_bracket_screw_spec as bracket_screw
    from sh_vn_thumb_screw_spec import SHANK_LEN as thumb_len

    for stem, length_mm, printed in (
        (notes.CLAMP_SCREW, clamp_screw.SHANK_LEN, "1-1/4"),
        (notes.BRACKET_SCREW, bracket_screw.LENGTH, "5/16"),
        (notes.THUMB_SCREW, thumb_len, "7/16"),
    ):
        assert f" X {printed} " in notes.BOM_DESCRIPTIONS[stem]
        assert float(sum(Fraction(p) for p in printed.split("-"))) == pytest.approx(
            length_mm / 25.4
        )


@pytest.mark.parametrize(
    ("length_mm", "printed"), ((1.5 * 25.4, "1-1/2"), (3.0 / 8.0 * 25.4, "3/8"))
)
def test_a_stock_screw_length_change_reprints_its_bom_fraction(
    monkeypatch, length_mm: float, printed: str
) -> None:
    # Code review C04: a canonical stock-length change must move the printed
    # fraction, not fail an import on a duplicated expected length.
    import importlib

    import sh_vn_clamp_screw_spec as clamp_screw

    monkeypatch.setattr(clamp_screw, "SHANK_LEN", length_mm)
    try:
        importlib.reload(notes)
        assert (
            notes.BOM_DESCRIPTIONS[notes.CLAMP_SCREW]
            == f"#8-32 X {printed} FILLISTER SCREW"
        )
    finally:
        monkeypatch.undo()
        importlib.reload(notes)


def test_a_screw_length_off_the_sixty_fourths_refuses_the_bom(monkeypatch) -> None:
    # A metric 8 mm stock (0.31496 in, 0.0625 mm off 5/16) has no catalogue
    # fraction: the BOM refuses rather than print a rounded one.
    import importlib

    import mg_vn_magnifying_bracket_screw_spec as bracket_screw

    monkeypatch.setattr(bracket_screw, "LENGTH", 8.0)
    try:
        with pytest.raises(ValueError, match="mg-vn-magnifying-bracket-screw length.*1/64"):
            importlib.reload(notes)
    finally:
        monkeypatch.undo()
        importlib.reload(notes)


def _inside(inner, outer) -> bool:
    return (
        inner[0] >= outer[0] - 1e-9
        and inner[1] >= outer[1] - 1e-9
        and inner[2] <= outer[2] + 1e-9
        and inner[3] <= outer[3] + 1e-9
    )


def _overlap(a, b) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def test_the_package_fields_stay_inside_the_border_and_off_the_title_block() -> None:
    bom = (
        drawing.BOM_ANCHOR[0],
        drawing.BOM_BOTTOM,
        drawing.BOM_ANCHOR[0] + sum(drawing.BOM_COLUMN_WIDTHS.values()),
        drawing.BOM_ANCHOR[1],
    )
    for field in (
        drawing.WHEEL_FIELD,
        drawing.LEVER_FIELD,
        drawing.FINISHED_FIELD,
        drawing.BOM_REFERENCE_FIELD,
        bom,
    ):
        assert _inside(field, drawing.INNER_BORDER), field
    for field in (drawing.LEVER_FIELD, drawing.FINISHED_FIELD, drawing.BOM_REFERENCE_FIELD):
        assert not _overlap(field, drawing.TITLE_BLOCK), field
    assert not _overlap(drawing.WHEEL_FIELD, bom)
    assert not _overlap(drawing.WHEEL_FIELD, drawing.TITLE_BLOCK)
    assert not _overlap(drawing.BOM_REFERENCE_FIELD, bom)
    assert drawing.BOM_REFERENCE_FIELD[3] < drawing.BOM_BOTTOM


def test_the_finished_caption_centres_over_its_view() -> None:
    outline = (0.257, 0.080, 0.311, 0.214)
    # The finished view is sheet 4's main view: no scale (rule 9).
    text = drawing.FINISHED_CAPTION
    assert "SCALE" not in text
    left, top = drawing.caption_over(outline, text)
    width = len(text) * drawing.CAPTION_CHAR_WIDTH
    assert left + width / 2.0 == pytest.approx((outline[0] + outline[2]) / 2.0)
    assert left > drawing.FINISHED_FIELD[0]
    assert top - drawing.NOTE_LINE_PITCH > outline[3]
    assert top < drawing.INNER_BORDER[3]


def test_the_wire_balloon_stands_right_of_the_view_on_its_rising_leader() -> None:
    import math

    landing = (0.282, 0.120)
    outline = (0.257, 0.080, 0.311, 0.214)
    x, y = drawing.wire_balloon_centre(
        landing,
        outline,
        rise_deg=drawing.FINISHED_WIRE_BALLOON_RISE_DEG,
        reach=drawing.BALLOON_MARGIN,
    )
    assert x == pytest.approx(outline[2] + drawing.BALLOON_MARGIN)
    assert math.degrees(math.atan2(y - landing[1], x - landing[0])) == pytest.approx(
        drawing.FINISHED_WIRE_BALLOON_RISE_DEG
    )
    assert x < drawing.INNER_BORDER[2] - drawing._PAD
    assert drawing.TITLE_BLOCK[3] < y < drawing.FINISHED_FIELD[3]




def test_the_exploded_ladders_keep_the_simplified_configuration() -> None:
    from _drawing_common import _SW_SHADED_EDGES
    from _drawing_view_configuration import (
        SIMPLIFIED_VIEW_CONFIGURATION,
        view_configuration,
    )

    for ladder in (
        drawing.EXPLODED_SCALE_LADDER,
        drawing.LEVER_SCALE_LADDER,
        drawing.FINISHED_SCALE_LADDER,
        drawing.BOM_REFERENCE_SCALE_LADDER,
    ):
        for scale in ladder:
            assert (
                view_configuration(scale, _SW_SHADED_EDGES)
                == SIMPLIFIED_VIEW_CONFIGURATION
            )
    # Each exploded view is its sheet's main view, whose scale the title
    # block prints, so its caption prints none (rule 9).
    assert "SCALE" not in drawing.exploded_caption("WHEEL GROUP")


def test_the_lever_group_takes_1_2_5_centred_with_its_caption_under_it() -> None:
    # Outlines measured 82.6 x 116.1 mm at 1:3 (r11) and 118.3 x 168.6 at 1:2
    # (r13): size = k / scale + fixed padding.
    def outline_size(denominator: float) -> tuple[float, float]:
        sizes = []
        for at_2, at_3 in ((0.1183, 0.0826), (0.1686, 0.1161)):
            k = (at_2 - at_3) * 6.0
            sizes.append(k / denominator + at_2 - k / 2.0)
        return sizes[0], sizes[1]

    field = drawing.LEVER_FIELD
    reach = 2.0 * drawing.BALLOON_RING_REACH

    def fits(denominator: float) -> bool:
        width, height = outline_size(denominator)
        return width + reach <= field[2] - field[0] and height + reach <= field[3] - field[1]

    assert not fits(2.0)
    assert fits(2.5)
    assert drawing.LEVER_SCALE_LADDER[0] == (1.0, 2.5)
    # Centred in the field, the caption sits under the view, above the title block.
    width, height = outline_size(2.5)
    centre = ((field[0] + field[2]) / 2.0, (field[1] + field[3]) / 2.0)
    outline = (
        centre[0] - width / 2.0,
        centre[1] - height / 2.0,
        centre[0] + width / 2.0,
        centre[1] + height / 2.0,
    )
    text = drawing.exploded_caption(drawing.LEVER_GROUP)
    left, top = drawing.lever_caption_xy(outline, text)
    assert top < outline[1]
    assert left + len(text) * drawing.CAPTION_CHAR_WIDTH / 2.0 == pytest.approx(centre[0])
    assert left > drawing.INNER_BORDER[0]
    assert left + len(text) * 0.00256 < drawing.INNER_BORDER[2]
    with pytest.raises(ValueError, match="reaches the title block"):
        drawing.lever_caption_xy((0.1, 0.075, 0.2, 0.2), text)


def test_the_setting_axis_picks_land_on_the_bare_cylinders_off_the_chain() -> None:
    # r14 (run 20261016T171305106Z), back view at 1:4: the picks stay 5 mm
    # off the clamp block, the 1/2 hex whose bottom face sits LEVER_BORE_Y
    # under the lever axis and whose corners sit HEX_AC/2 either side of the
    # rod axis along the lever (#1559), and off the fixture's top, 5.5 mm
    # over its axis.
    import mg_magnifying_clamp_geom as clamp

    picks = drawing.setting_axis_picks_m()
    rod_x, rod_y, rod_z = (value * 1000.0 for value in picks["vertical rod"])
    lever_x, lever_y, lever_z = (value * 1000.0 for value in picks["lever"])
    assert rod_z == lever_z == 0.0
    assert 0.0 < rod_x - stack.CLAMP_CENTRE_X < drawing._VROD_R
    assert stack.LEVER_AXIS_Y - rod_y > clamp.LEVER_BORE_Y + 5.0
    assert rod_y - stack.FIXTURE_AXIS_Y > 5.5 + 5.0
    assert 0.0 < lever_y - stack.LEVER_AXIS_Y < drawing._LEVER_R
    assert lever_x - stack.CLAMP_CENTRE_X > clamp.HEX_AC / 2.0 + 5.0
    assert stack.LEVER_TIP_X - lever_x > drawing._LEVER_R + 5.0


def test_the_axle_nut_balloons_land_square_to_the_axle_on_distinct_parts() -> None:
    import math

    import mg_vn_wheel_axle_front_washer_spec as washer
    import mg_vn_wheel_axle_nut_spec as nut

    def screen(point):
        # Ry(180) placement, then the preserved fitter (+X+Y+Z) projection.
        x, y, z = -point[0], point[1], -point[2]
        return ((x - z) / math.sqrt(2.0), (-x + 2.0 * y - z) / math.sqrt(6.0))

    wx, wy, wz = drawing.FRONT_WASHER_BALLOON_POINT_MM
    assert wz == 0.0 and math.hypot(wx, wy) == pytest.approx(washer.OD / 2.0)
    nx, ny, nz = drawing.LOCKNUT_BALLOON_POINT_MM
    # On the flat facing 240 deg (corners on the local +-Y meridian).
    normal = math.radians(240.0)
    assert nz == 0.0
    assert nx * math.cos(normal) + ny * math.sin(normal) == pytest.approx(
        nut.ACROSS_FLATS / 2.0
    )
    axle = screen((0.0, 0.0, 1.0))  # the stack's explode runs along local +z
    for point, side in (
        (drawing.FRONT_WASHER_BALLOON_POINT_MM, (-0.5, math.sqrt(3.0) / 2.0)),
        (drawing.LOCKNUT_BALLOON_POINT_MM, (0.5, -math.sqrt(3.0) / 2.0)),
    ):
        sx, sy = screen(point)
        length = math.hypot(sx, sy)
        assert (sx / length, sy / length) == pytest.approx(side)
        assert sx * axle[0] + sy * axle[1] == pytest.approx(0.0, abs=1e-9)
    anchors = drawing.BALLOON_ANCHORS
    assert anchors["mg-vn-wheel-axle-nut"].instance == "mg-vn-wheel-axle-nut-2"
    # Instance 2 is the locknut, exploded farthest out.
    farthest = min(
        (step for step in explode.EXPLODE_STEPS if step.axis == "z"),
        key=lambda step: step.distance_mm,
    )
    assert farthest.members == ("mg-vn-wheel-axle-nut:2",)


def test_step_down_takes_the_largest_scale_whose_ring_fits() -> None:
    field = (0.0, 0.0, 0.200, 0.150)
    widths = {(1.0, 2.0): 0.250, (1.0, 3.0): 0.150, (1.0, 4.0): 0.110}

    def outline_at(scale):
        width = widths[scale]
        return (0.0, 0.0, width, width * 0.5)

    scale, outline = drawing.step_down_to_fit(
        outline_at, drawing.EXPLODED_SCALE_LADDER, field, name="t"
    )
    assert scale == (1.0, 3.0)
    with pytest.raises(ValueError, match="no t scale fits"):
        drawing.step_down_to_fit(
            outline_at, drawing.EXPLODED_SCALE_LADDER, (0.0, 0.0, 0.05, 0.05), name="t"
        )


@pytest.mark.parametrize(
    ("stem", "station", "radius", "rows"),
    [
        (
            "mg-magnifying-lever",
            assembly.LEVER_ROD_DIA / 2.0,
            assembly.LEVER_ROD_DIA / 2.0,
            _transforms.ROT_Y_180,
        ),
        (
            # The shoulder's Ø5 edge (#1559): the old x = R station now falls
            # on the turned-down thread, so a point at radius R is off the rod.
            "mg-magnifying-vertical-rod",
            mg_magnifying_vertical_rod_geom.SHOULDER_X,
            assembly.VROD_DIA / 2.0,
            _transforms.compose_rows(
                _transforms.rot_z_rows(-90.0), _transforms.ROT_Y_180
            ),
        ),
    ],
)
def test_rod_balloon_anchors_sit_on_a_drawn_circle_facing_the_isometric(
    stem: str, station: float, radius: float, rows: list[list[float]]
) -> None:
    x, y, z = drawing.BALLOON_ANCHORS[stem].point_mm
    assert x == pytest.approx(station)
    assert math.hypot(y, z) == pytest.approx(radius)
    normal = [
        sum((0.0, y / radius, z / radius)[i] * rows[i][j] for i in range(3))
        for j in range(3)
    ]
    assert sum(normal) > 0.0  # faces the +X+Y+Z viewer
    if stem == "mg-magnifying-lever":
        # Square to the rod axis, and straight at the viewer.
        assert sum(normal) == pytest.approx(math.sqrt(2.0))
    else:
        # Opposite the revolve seam (x, R, 0): a vertex of the drawn circle
        # for any even segment count (r12 missed mid-chord at 1:2).
        assert (y, z) == pytest.approx((-radius, 0.0))


def _metadata_instances():
    return [
        explode.Instance(f"{stem}-{number}", stem)
        for stem in notes.BOM_ORDER
        for number in range(1, notes.QUANTITIES[stem] + 1)
    ]


def _metadata_offsets():
    """Aggregate the actual component plan, retaining stationary instances."""
    instances = _metadata_instances()
    offsets = {item.name.casefold(): [0.0, 0.0, 0.0] for item in instances}
    for step, names in explode.plan_explode(instances):
        for name in names:
            offsets[name.casefold()]["xyz".index(step.axis)] += step.distance_mm / 1000.0
    return {name: tuple(vector) for name, vector in offsets.items()}


@pytest.mark.parametrize("configuration", ["Default", "Default Simplified"])
def test_mg_builder_owned_offsets_roundtrip_actual_component_plan(configuration) -> None:
    offsets = _metadata_offsets()
    instances = [
        explode.Instance(item.name.upper(), item.stem) for item in _metadata_instances()
    ]
    encoded = explode.encode_explode_offsets(configuration, offsets, instances)
    payload = json.loads(encoded)
    assert set(payload) == {
        "configuration", "view", "steps", "contract_sha256", "offsets_m"
    }
    assert payload["contract_sha256"] == explode.explode_contract_fingerprint(instances)
    assert len(payload["contract_sha256"]) == 64
    assert all(character in "0123456789abcdef" for character in payload["contract_sha256"])
    decoded = explode.decode_explode_offsets(encoded, configuration, instances)
    assert decoded == offsets
    assert any(vector == (0.0, 0.0, 0.0) for vector in decoded.values())
    # The format preserves native aggregate world translations, not a single
    # nominal axis/step. Multiple native steps may move the same component.
    name = next(iter(offsets))
    cumulative = dict(offsets)
    cumulative[name] = (0.030 + 0.012, -0.025, 0.007)
    assert explode.decode_explode_offsets(
        explode.encode_explode_offsets(configuration, cumulative, instances),
        configuration,
        instances,
    )[name] == pytest.approx((0.042, -0.025, 0.007))
    assert explode.explode_offsets_property(configuration) != (
        explode.explode_offsets_property(
            "Default Simplified" if configuration == "Default" else "Default"
        )
    )


@pytest.mark.parametrize(
    "damage",
    [
        "missing configuration", "wrong configuration", "missing view", "wrong view",
        "missing steps", "wrong steps", "missing contract_sha256", "wrong contract_sha256",
        "missing offsets", "missing instance",
        "extra instance", "short vector", "long vector", "nonnumeric", "boolean",
        "nan", "infinity", "malformed", "empty",
    ],
)
def test_mg_builder_owned_offsets_refuse_invalid_metadata(damage) -> None:
    configuration = "Default Simplified"
    payload = json.loads(
        explode.encode_explode_offsets(
            configuration, _metadata_offsets(), _metadata_instances()
        )
    )
    name = next(iter(payload["offsets_m"]))
    field = damage.removeprefix("missing ")
    if field in {"configuration", "view", "steps", "contract_sha256", "offsets"}:
        payload.pop("offsets_m" if field == "offsets" else field)
    elif damage == "wrong configuration":
        payload["configuration"] = "Default"
    elif damage == "wrong view":
        payload["view"] = "unowned view"
    elif damage == "wrong steps":
        payload["steps"] = len(explode.EXPLODE_STEPS) + 1
    elif damage == "wrong contract_sha256":
        payload["contract_sha256"] = "0" * 64
    elif damage == "missing instance":
        payload["offsets_m"].pop(name)
    elif damage == "extra instance":
        payload["offsets_m"]["unexpected-1"] = [0.0, 0.0, 0.0]
    elif damage in {"short vector", "long vector"}:
        payload["offsets_m"][name] = [0.0] * (2 if damage == "short vector" else 4)
    elif damage in {"nonnumeric", "boolean", "nan", "infinity"}:
        value = {
            "nonnumeric": "0.1", "boolean": True,
            "nan": float("nan"), "infinity": float("inf"),
        }[damage]
        payload["offsets_m"][name] = [value, 0.0, 0.0]
    text = json.dumps(payload)
    if damage == "malformed":
        text = "{"
    elif damage == "empty":
        text = ""
    with pytest.raises(ValueError) as caught:
        explode.decode_explode_offsets(
            text, configuration, _metadata_instances()
        )
    assert "builder-owned explode offsets" in str(caught.value)
    assert "rebuild assembly:mg_magnifier" in str(caught.value)


@pytest.mark.parametrize("mutation", ["distance", "axis", "raw members", "resolved members"])
def test_mg_owned_offsets_refuse_same_count_contract_mutations(monkeypatch, mutation):
    configuration = "Default Simplified"
    instances = _metadata_instances()
    offsets = _metadata_offsets()
    encoded = explode.encode_explode_offsets(configuration, offsets, instances)
    old_plan = explode.plan_explode(instances)
    changed_steps = list(explode.EXPLODE_STEPS)
    if mutation == "distance":
        # A changed spec-derived distance must invalidate the readback even
        # when the native step count and every component identity still match.
        changed_steps[0] = replace(
            changed_steps[0], distance_mm=changed_steps[0].distance_mm - 1.0
        )
    elif mutation == "axis":
        changed_steps[0] = replace(changed_steps[0], axis="x")
    elif mutation == "raw members":
        # :02 resolves to exactly the same nut as :2, isolating raw recipe
        # membership from the separately fingerprinted resolved names.
        changed_steps[0] = replace(
            changed_steps[0], members=("mg-vn-wheel-axle-nut:02",)
        )
    else:
        swapped = {
            "mg-magnifying-wheel": "mg-wheel-drum",
            "mg-wheel-drum": "mg-magnifying-wheel",
        }
        instances = [
            replace(item, stem=swapped.get(item.stem, item.stem)) for item in instances
        ]
    monkeypatch.setattr(explode, "EXPLODE_STEPS", tuple(changed_steps))
    current_plan = explode.plan_explode(instances)
    assert len(current_plan) == len(old_plan) == json.loads(encoded)["steps"]
    assert {item.name.casefold() for item in instances} == set(offsets)
    if mutation == "raw members":
        assert [names for _step, names in current_plan] == [
            names for _step, names in old_plan
        ]
    elif mutation == "resolved members":
        assert [step for step, _names in current_plan] == [
            step for step, _names in old_plan
        ]
        assert [names for _step, names in current_plan] != [
            names for _step, names in old_plan
        ]
    with pytest.raises(ValueError, match="explode contract differs"):
        explode.decode_explode_offsets(encoded, configuration, instances)


def _native_mg_author(monkeypatch, configuration_name, mismatch=None):
    """Native readbacks are fixed independently of the recipe being authored."""
    import _explode as steps
    import _mg_magnifier_explode as author
    import _component_references as references
    from solidworks_mcp.adapters import com_variant

    monkeypatch.setattr(
        explode,
        "EXPLODE_STEPS",
        (
            explode.ExplodeStep("group out", ("slider",), "x", 30.0),
            explode.ExplodeStep("first farther", ("slider:1",), "x", 12.0),
            explode.ExplodeStep("first down", ("slider:1",), "y", -25.0),
            explode.ExplodeStep("first back", ("slider:1",), "z", 7.0),
        ),
    )
    monkeypatch.setattr(explode, "SHOWN_STEMS", frozenset({"slider", "stationary"}))
    # Absolute native positions, not recipe vectors or encoder output. All
    # three baseline translations are nonzero. The small final residuals are
    # deliberately inside the author's existing 1e-7 m verification tolerance.
    native_positions = {
        "slider-1": (
            (0.500, -0.250, 0.125),
            (0.53000002, -0.250, 0.125),
            (0.54200003, -0.250, 0.125),
            (0.54200003, -0.27500002, 0.125),
            (0.54200003, -0.27500002, 0.13200004),
        ),
        "slider-2": (
            (-0.200, 0.350, -0.400),
            (-0.16999999, 0.350, -0.400),
            (-0.16999999, 0.350, -0.400),
            (-0.16999999, 0.350, -0.400),
            (-0.16999999, 0.350, -0.400),
        ),
        "stationary-1": ((0.100, 0.200, 0.300),) * 5,
        "sh-vn-music-wire-73": ((0.075, 0.200, 0.300),) * 5,
    }
    requests = (
        (0.030, ("slider-1", "slider-2"), "X", False),
        (0.012, ("slider-1",), "X", False),
        (0.025, ("slider-1",), "Y", True),
        (0.007, ("slider-1",), "Z", False),
    )
    state = SimpleNamespace(
        stage=0, exploded=False, selected=[], axis=None, views=(),
        steps=[SimpleNamespace(Name="automatic seed")], show_calls=[], published=[],
    )

    def transform(name, stage):
        values = [
            1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0,
            *native_positions[name][stage], 1.0, 0.0, 0.0, 0.0,
        ]
        if stage == 4:
            if mismatch == "translation" and name == "slider-1":
                values[9] += 0.001
            elif mismatch == "stationary follower" and name == "stationary-1":
                values[10] += 0.001
            elif mismatch == "rotation" and name == "slider-1":
                values[0] = 0.0
        return SimpleNamespace(ArrayData=tuple(values))

    def select_component(name, append, data, show_popup):
        assert append is True and data.Mark == 1 and show_popup is False
        state.selected.append(name)
        return True

    components = {
        name: SimpleNamespace(
            Name2=name,
            ComponentReference=(
                "LeverWire:1" if name == "sh-vn-music-wire-73" else ""
            ),
            ReferencedConfiguration=(
                "LeverWire" if name == "sh-vn-music-wire-73" else "Default"
            ),
            GetPathName=lambda name=name: f"C:/parts/{name.rsplit('-', 1)[0]}.SLDPRT",
            GetTotalTransform=lambda presentation, name=name: transform(
                name, state.stage if presentation and state.exploded else 0
            ),
            Transform2=transform(name, 0),
            Select4=lambda append, data, popup, name=name: select_component(
                name, append, data, popup
            ),
        )
        for name in native_positions
    }

    def clear_selection(all_selections):
        assert all_selections is True
        state.selected.clear()
        state.axis = None

    def select_axis(name, kind, x, y, z, append, mark, callout, options):
        assert (kind, x, y, z, append, mark, callout, options) == (
            "AXIS", 0.0, 0.0, 0.0, True, 2, None, 0
        )
        state.axis = name
        return True

    def add_step(distance, manipulator, reverse, angle, rotation_axis, *options):
        expected_distance, names, axis, expected_reverse = requests[state.stage]
        assert (distance, tuple(state.selected), state.axis, reverse) == (
            expected_distance, names, axis, expected_reverse
        )
        assert (manipulator, angle, rotation_axis, options) == (
            -1, 0.0, -1, (False, True, False)
        )
        state.stage += 1
        if state.stage == 4 and mismatch == "native members":
            names = ("stationary-1",)
        native = SimpleNamespace(
            Name="unnamed",
            ExplodeDistance=distance + (
                0.001 if state.stage == 4 and mismatch == "native distance" else 0.0
            ),
            GetComponents=lambda: tuple(components[name] for name in names),
        )
        state.steps.append(native)
        return native, 0

    def delete_seed(name):
        assert name == "automatic seed" and state.stage == 0
        state.steps.clear()
        return True

    def show_exploded(show, view_name):
        assert state.views == (view_name,)
        state.exploded = show
        state.show_calls.append(show)
        return True

    configuration = SimpleNamespace(
        Name=configuration_name,
        GetNumberOfExplodeSteps=lambda: len(state.steps),
        GetExplodeStep=lambda index: state.steps[index],
        DeleteExplodeStep=delete_seed,
        AddExplodeStep2=add_step,
    )
    model = SimpleNamespace(
        ConfigurationManager=SimpleNamespace(ActiveConfiguration=configuration),
        GetExplodedViewCount2=lambda owner: len(state.views),
        GetComponents=lambda top_level: tuple(components.values()),
        GetExplodedViewNames2=lambda owner: state.views,
        GetExplodedViewConfigurationName=lambda view: configuration_name,
        ShowExploded2=show_exploded,
        ClearSelection2=clear_selection,
        SelectionManager=SimpleNamespace(
            CreateSelectData=lambda: SimpleNamespace(Mark=0)
        ),
        Extension=SimpleNamespace(SelectByID2=select_axis),
        EditRebuild3=lambda: True,
    )
    adapter = SimpleNamespace(currentModel=model)

    def create_named_view(actual_model, actual_assembly, owner, view_name):
        assert actual_model is model and actual_assembly is model
        assert owner == configuration_name
        state.views = (view_name,)

    def publish(actual_adapter, properties, *, model):
        assert actual_adapter is adapter and model is adapter.currentModel
        assert not state.exploded and state.show_calls == [True, False]
        assert state.stage == len(state.steps) == 4
        state.published.append(properties)

    monkeypatch.setattr(author, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(steps, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(references, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(com_variant, "null_callout", lambda: None)
    monkeypatch.setattr(
        steps, "global_directions",
        lambda _adapter, _assembly: {
            "x": steps.Direction("X", True, (1.0, 0.0, 0.0)),
            "y": steps.Direction("Y", True, (0.0, 1.0, 0.0)),
            "z": steps.Direction("Z", True, (0.0, 0.0, 1.0)),
        },
    )
    monkeypatch.setattr(steps, "_create_named_view", create_named_view)
    monkeypatch.setattr(author, "apply_custom_properties", publish)
    return author, adapter, state


@pytest.mark.parametrize("configuration", ["Default", "Default Simplified"])
def test_actual_mg_author_publishes_final_measured_offsets(monkeypatch, configuration):
    author, adapter, state = _native_mg_author(monkeypatch, configuration)
    author.create_mg_magnifier_explode(adapter, configuration)
    assert len(state.published) == 1
    properties = state.published[0]
    assert set(properties) == {explode.explode_offsets_property(configuration)}
    payload = json.loads(properties[explode.explode_offsets_property(configuration)])
    assert payload["configuration"] == configuration
    assert payload["view"] == explode.exploded_view_name(configuration)
    assert payload["steps"] == 4
    # Tight absolute tolerance distinguishes native residuals from nominal
    # recipe sums, earlier steps, absolute positions, and post-collapse zeros.
    expected = {
        "slider-1": (0.04200003, -0.02500002, 0.00700004),
        "slider-2": (0.03000001, 0.0, 0.0),
        "stationary-1": (0.0, 0.0, 0.0),
        "sh-vn-music-wire-73": (0.0, 0.0, 0.0),
    }
    assert set(payload["offsets_m"]) == set(expected)
    for name, vector in expected.items():
        assert payload["offsets_m"][name] == pytest.approx(vector, abs=1e-14, rel=0)
    instances = [
        explode.Instance(name, name.rsplit("-", 1)[0]) for name in expected
    ]
    decoded = explode.decode_explode_offsets(
        properties[explode.explode_offsets_property(configuration)],
        configuration,
        instances,
    )
    assert decoded["stationary-1"] == (0.0, 0.0, 0.0)
    assert [step.Name for step in state.steps] == [
        f"MG {label}" + (" Simplified" if configuration != "Default" else "")
        for label in ("GROUP OUT", "FIRST FARTHER", "FIRST DOWN", "FIRST BACK")
    ]
    assert state.show_calls == [True, False] and not state.exploded


@pytest.mark.parametrize(
    ("mismatch", "message"),
    [
        ("translation", "slider-1 moved"),
        ("stationary follower", "stationary-1 moved"),
        ("rotation", "presentation rotated or scaled"),
        ("native distance", "step component/distance readback mismatch"),
        ("native members", "step component/distance readback mismatch"),
    ],
)
def test_actual_mg_author_never_publishes_failed_readback(monkeypatch, mismatch, message):
    configuration = "Default Simplified"
    author, adapter, state = _native_mg_author(monkeypatch, configuration, mismatch)
    with pytest.raises(RuntimeError, match=message):
        author.create_mg_magnifier_explode(adapter, configuration)
    assert state.stage == 4
    assert state.show_calls == [True, False] and not state.exploded
    assert state.published == []


def test_mg_source_sha256_streams_known_bytes(tmp_path):
    path = tmp_path / "source.SLDASM"
    path.write_bytes(b"abc")
    assert drawing._source_sha256(path) == (
        "ba7816bf8f01cfea414140de5dae2223"
        "b00361a396177a9cb410ff61f20015ad"
    )
    # Cross two 1 MiB block boundaries; a small fixture alone would not catch
    # hashing only the first chunk.
    path.write_bytes(b"\0" * (2 * 1024 * 1024 + 3))
    import hashlib

    assert drawing._source_sha256(path) == hashlib.sha256(
        b"\0" * (2 * 1024 * 1024 + 3)
    ).hexdigest()


@pytest.mark.parametrize("group", ["lever", "stack"])
@pytest.mark.parametrize("missing", [False, True])
def test_mg_settings_only_read_inherited_native_callouts(
    monkeypatch, group, missing
) -> None:
    import _drawing_dimensions as dimension_helpers

    feature = stack.LEVER_FEATURE if group == "lever" else stack.FEATURE
    callouts = stack.SETTING_CALLOUTS[feature]
    precision = (
        stack.LEVER_DRAWING_PRECISION if group == "lever" else stack.DRAWING_PRECISION
    )[feature]
    annotations = {}
    text_parts = {}

    def forbidden(*_args):
        pytest.fail("drawing settings must not write native callout text")

    # Every imported setting, each with its inherited callout.
    for name in precision:
        part, text = callouts.get(name, (None, ""))
        text_parts[name] = {part: text.replace("\n", "\r\n")} if part else {}
        band_m = stack.DIMENSION_TOLERANCES.get(name, 0.0) / 1000.0
        reference = group == "stack" and name in stack.REFERENCE_DIMENSIONS
        limits = stack.LIMIT_DIMENSIONS.get(name) if group == "stack" else None
        if reference:
            text_parts[name].update({1: "(", 2: ")"})
        legs = dict(zip(stack.CHAIN_LEG_DIMENSIONS, zip(stack.CHAIN_D, stack.CHAIN_D[1:])))
        nominal_m = (legs[name][1] - legs[name][0]) / 1000.0 if limits else 0.0
        if limits:
            tolerance = SimpleNamespace(
                Type=3,
                GetMaxValue=lambda high=limits[1] / 1000.0 - nominal_m: high,
                GetMinValue=lambda low=limits[0] / 1000.0 - nominal_m: low,
            )
        else:
            tolerance = SimpleNamespace(
                Type=0 if reference else 4,
                GetMaxValue=lambda band=band_m: band,
                GetMinValue=lambda band=band_m: -band,
            )
        tol_places = stack.LIMIT_PRECISION if limits else stack.TOLERANCE_PRECISION
        display = SimpleNamespace(
            ShowParenthesis=False,
            SetText=forbidden,
            GetText=lambda part, name=name: text_parts[name].get(part, ""),
            GetPrimaryPrecision2=lambda name=name: precision[name],
            GetPrimaryTolPrecision2=lambda places=tol_places: places,
            GetDimension2=lambda _index, tol=tolerance, value=nominal_m: SimpleNamespace(
                Tolerance=tol, SystemValue=value
            ),
        )
        annotations[name] = SimpleNamespace(
            name=name, GetSpecificAnnotation=lambda display=display: display
        )
    name, (part, _text) = next(iter(callouts.items()))
    if missing:
        text_parts[name][part] = ""
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _iface: value)
    monkeypatch.setattr(
        dimension_helpers._sw_type_info,
        "early_bound_or_flag",
        lambda value, *_args: value,
    )
    for module in (drawing, dimension_helpers):
        monkeypatch.setattr(module, "dimension_name", lambda _adapter, item: item.name)
    monkeypatch.setattr(drawing, "_show_base_view_sketches", lambda *_a, **_k: None)
    monkeypatch.setattr(drawing, "_activate_sheet", lambda *_a: None)
    monkeypatch.setattr(
        drawing,
        "curate_view_dimensions",
        lambda *_a, **_k: list(annotations.values()),
    )
    monkeypatch.setattr(
        drawing,
        "model_points_in_view",
        lambda *_a, **_k: ((0.0, 0.0),) * 3,
    )
    monkeypatch.setattr(drawing, "_add_setting_axes", lambda *_a: None)
    monkeypatch.setattr(
        drawing,
        "_dimensioned_detail",
        lambda _adapter, _detail, keep: [annotations[name] for name in keep],
    )
    adapter = SimpleNamespace(_attempt=lambda action: action())
    source_steps = []

    def import_settings():
        if group == "lever":
            return drawing._lever_settings(adapter, object(), source_steps.append)
        return drawing._stack_dimensions(adapter, source_steps.append)

    if missing:
        with pytest.raises(RuntimeError, match="callout reads ''"):
            import_settings()
        return
    settled = import_settings()
    settled()
    assert source_steps == [
        f"{group} settings import and readback", f"{group} settings settled readback",
    ]
    text_parts[name][part] = ""
    with pytest.raises(RuntimeError, match="callout reads ''"):
        settled()

