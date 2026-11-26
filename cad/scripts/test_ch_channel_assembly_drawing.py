"""Offline contract for the channel assembly drawing (MHA-CH-00)."""

from __future__ import annotations

import math
from pathlib import Path
import re

import _buildgraph
from _assembly_contract import assembly_contract
import _config
import ch_channel_assembly_steps as steps
import draw_ch_channel_assembly as drawing
import dt_drive_train_steps
from ch_rocker_arm_spec import HUB_LENGTH
import pytest
import rocker_bank_layout as bank
from _drawing_registry import DRAWINGS_BY_NAME

STEP_HEAD = re.compile(r"^(\d+)\. ", re.MULTILINE)
# A drive-train or frame sequence head, sub-steps included ("9F. ").
ANY_STEP_HEAD = re.compile(r"^(\d+[A-Z]?)\. ", re.MULTILINE)
STEP_POINTER = re.compile(r"(MHA-[A-Z]{2}-00)\b STEP (\d+[A-Z]?)")
# Default-format note text, measured on r743-rocker-fix3's render (leaf
# 20260926T112244Z-1-a884759d); the drawing sizes its step columns from these.
NOTE_CHAR_WIDTH = drawing.NOTE_CHAR_WIDTH
NOTE_LINE_PITCH = drawing.NOTE_LINE_PITCH


def _step_body(key: str) -> str:
    """The printed text of one step, from its head to the next head or the
    end of its column (never into the next column's heading)."""
    number = steps.step_number(key)
    for _column, block in drawing.FITUP_NOTES:
        heads = list(STEP_HEAD.finditer(block))
        for index, head in enumerate(heads):
            if int(head.group(1)) == number:
                end = heads[index + 1].start() if index + 1 < len(heads) else len(block)
                return " ".join(block[head.end() : end].split())
    raise KeyError(key)


def _sequence_steps(text: str) -> dict[str, str]:
    """Every step of a printed sequence: its head label to its joined text."""
    heads = list(ANY_STEP_HEAD.finditer(text))
    bodies = {}
    for index, head in enumerate(heads):
        end = heads[index + 1].start() if index + 1 < len(heads) else len(text)
        assert head.group(1) not in bodies, f"step {head.group(1)} printed twice"
        bodies[head.group(1)] = " ".join(text[head.end() : end].split())
    return bodies


def test_channel_assembly_keeps_registry_outputs_and_precomputed_placement() -> None:
    spec = DRAWINGS_BY_NAME["ch_channel_assembly"]
    assert spec.source_kind == "assembly"
    assert spec.part == "ch_channel"
    assert drawing.SOURCE == spec.source
    assert drawing.OUTPUTS == drawing.OUTPUTS.__class__(
        spec.outputs["slddrw"], spec.outputs["pdf"], spec.outputs["png"]
    )
    assert drawing.SHEET_SCALE == (1.0, 7.0)
    assert drawing.SHEET_SCALES[drawing.SHEET_NAMES[0]] == (1.0, 5.0)
    assert drawing.ASSEMBLED_ISO_SCALE == drawing.SHEET_SCALE
    assert drawing.FRONT_CENTER == (0.075, 0.140)
    assert drawing.RIGHT_CENTER == (0.185, 0.140)
    assert drawing.ISO_CENTER == (0.320, 0.150)
    # Front and Right in projection: one centre line.
    assert drawing.FRONT_CENTER[1] == drawing.RIGHT_CENTER[1]
    assert drawing.ISO_LABEL == "ISOMETRIC\nSCALE 1 : 7"


def test_step_numbers_follow_the_sequence_and_unknown_steps_are_refused() -> None:
    for index, key in enumerate(steps.SEQUENCE, start=1):
        assert steps.step_number(key) == index
    with pytest.raises(KeyError):
        steps.step_number("no-such-step")


def test_every_cross_sheet_step_pointer_lands_on_the_step_it_names() -> None:
    """Codex #936 (PRRT_kwDOPHDy386mRlAE): step 2 sent the fitter to an A03
    step that did not exist. Each pointer must land on a printed step that
    does what it cites, and every pointer is its registry's, never a typed
    number."""
    import draw_dt_drive_train_assembly as drive_train
    import fr_frame_assembly_sheet as frame
    import fr_frame_assembly_steps as frame_steps
    import ha_harmonic_analyzer_assembly_steps as ha_steps

    bracket = _config.parts("ch-pivot-bracket")["number"]
    channel_number = assembly_contract("ch-channel").number
    fitup_number = assembly_contract("dt-drive-train").number
    frame_number = assembly_contract("fr-frame").number
    north_ref = (
        f"{fitup_number} STEP "
        f"{dt_drive_train_steps.step_number(steps.NORTH_BRACKET_SET_KEY)}"
    )
    stack_ref = (
        f"{fitup_number} STEP "
        f"{dt_drive_train_steps.step_number(steps.CYLINDER_STACK_KEY)}"
    )
    sheets = {
        channel_number: _sequence_steps(drawing.FITUP_STEPS),
        fitup_number: _sequence_steps(
            "\n".join(
                (
                    drive_train.CONE_CRANK_STEPS,
                    drive_train.BANK_STEPS,
                    drive_train.rig_steps(pivot_blocks=2, cams=2, slotted=4),
                )
            )
        ),
        # The frame's steps print in ASSEMBLY.md, one section per group (#2889).
        frame_number: _sequence_steps(
            "\n".join(step for _title, group in frame.STEP_SECTIONS for step in group)
        ),
    }
    # What each pointer's target must name, keyed by (citing sheet, pointer).
    expected = {
        # MHA-DT-00 names directions by its sheet 1 FRONT view: north is BACK.
        (channel_number, north_ref): f"THE BACK {bracket}",
        # The rod rings go onto their cams in the cylinder stack, so the
        # bench-pinned rod + arm pairs must exist by then.
        (channel_number, stack_ref): "AS EACH GEAR GOES ON",
        # The left-hub remedy resets the left bracket by the drive train's own
        # ear-setting sub-step, then its screw and recheck sub-steps.
        (channel_number, f"{north_ref}B"): "SET THE EAR INNER FACE TO ITS Y",
        (channel_number, f"{north_ref}E"): f"SCREW THE {bracket} DOWN",
        (channel_number, f"{north_ref}F"): "RECHECK Y",
        # ... and that drive-train step names the pinning step it relies on.
        (fitup_number, steps.RODS_PINNED_REF): "ROD FORK",
        # The support is screwed down before the north bracket is set on it.
        (
            fitup_number,
            frame_steps.step_ref(frame_steps.SUPPORT_SCREWED_KEY),
        ): f"THROUGH ITEM {frame.ITEM_NUMBERS['fr-rocker-arm-support']} INTO",
    }
    found = set()
    # MHA-HA-00's sequence is not on this branch's base: its pointers are
    # checked by value against its step registry instead.
    foreign = set()
    for sheet, bodies in sheets.items():
        for body in bodies.values():
            for pointer in STEP_POINTER.finditer(body):
                if pointer.group(1) not in sheets:
                    foreign.add((sheet, pointer.group(0)))
                    continue
                found.add((sheet, pointer.group(0)))
                # A numbered step owns its lettered sub-steps (8 = 8, 8A, 8B...).
                label = pointer.group(2)
                owned = rf"{label}[A-Z]?" if label.isdigit() else re.escape(label)
                target = " ".join(
                    text
                    for head, text in sheets[pointer.group(1)].items()
                    if re.fullmatch(owned, head)
                )
                assert expected[(sheet, pointer.group(0))] in target, pointer.group(0)
    assert found == set(expected)
    assert foreign == {
        (channel_number, steps.HA_ANCHORS_SET_REF),
        (frame_number, ha_steps.step_ref("summing-levelled")),
    }
    north_label = str(dt_drive_train_steps.step_number(steps.NORTH_BRACKET_SET_KEY))
    labels = list(sheets[fitup_number])
    north = " ".join(
        text
        for head, text in sheets[fitup_number].items()
        if re.fullmatch(rf"{north_label}[A-Z]?", head)
    )
    assert "SET THE EAR INNER FACE TO ITS Y" in north
    assert f"{drive_train.DRO_ZERO_STEP} ZERO" in north
    # The plain shaft threads through the set ear: the bracket stays down,
    # and nothing is miced there for the channel sheet (#3114: no washer).
    assert "LIFT IT OFF" not in north
    assert "MIC THE" not in north
    # Rule 23 (rubric sample round 9): the one-screw bracket's bench check.
    assert "CHECK THAT THE MHA-CH-08 DOES NOT TURN ON MHA-FR-05 BY HAND" in north
    assert steps.NORTH_BRACKET_SET_REF in _step_body("north-bracket-held")
    # The fitter leaves this list for the drive train's cylinder stack through
    # its north-bracket set and comes back at this check (rule 22 hand-off).
    assert _step_body("north-bracket-held").startswith(
        f"AFTER {steps.CYLINDER_STACK_REF} THROUGH {steps.NORTH_BRACKET_SET_REF},"
    )
    # It follows the bank's last sub-step on the bank sheet; positive control:
    # that sub-step is the bank's, not the ear's.
    bank_last = labels[labels.index(north_label) - 1]
    assert re.fullmatch(r"9[A-Z]", bank_last), bank_last
    assert f"BACK {bracket}" not in sheets[fitup_number][bank_last]
    # The rig's first step is whichever key the registry puts right after the
    # north bracket, so reordering the rig's own steps cannot break this.
    sequence = dt_drive_train_steps.SEQUENCE
    assert steps.NORTH_BRACKET_SET_KEY in sequence[:-1], (
        f"{steps.NORTH_BRACKET_SET_KEY!r} must be in "
        "drive_train_steps.SEQUENCE with a rig step after it"
    )
    rig_first_key = sequence[sequence.index(steps.NORTH_BRACKET_SET_KEY) + 1]
    rig_first = str(dt_drive_train_steps.step_number(rig_first_key))
    numbered = [label for label in labels if label.isdigit()]
    assert numbered.index(rig_first) == numbered.index(north_label) + 1


def test_the_printed_step_heads_are_the_registry_in_order() -> None:
    printed = [int(n) for n in STEP_HEAD.findall(drawing.FITUP_STEPS)]
    assert printed == list(range(1, len(steps.SEQUENCE) + 1))
    assert steps.SEQUENCE == steps.ROCKER_SEQUENCE + steps.LEVER_SEQUENCE
    assert len(set(steps.SEQUENCE)) == len(steps.SEQUENCE)
    assert tuple(drawing.FITUP_TEXT) == steps.SEQUENCE
    # The lever bank's steps all follow the rocker bank's; the strap check
    # (#2343) closes the rocker bank, and the keepers open the lever bank.
    assert steps.ROCKER_SEQUENCE[-1 - len(steps.STRAP_SHAKE_REMEDY)] == (
        "straps-shake-in-forks"
    )
    assert steps.LEVER_SEQUENCE[0] == "keepers-on-frame"
    assert steps.SEQUENCE[-1] == "spring-bottom-loops-left"


def test_every_step_is_one_action_of_at_most_six_lines() -> None:
    """drawing-guidelines.md rule 22: one action per step, at most six
    printed lines; every remedy block ends on a step of its own that loops
    back to the step it repeats (machinist review of PR #3116: no step joins
    actions with commas or AND, none ends "... AND RETURN TO STEP n")."""
    for key in steps.SEQUENCE:
        assert len(drawing._wrapped_step(key, drawing.FITUP_TEXT[key])) <= 6
    returns = {
        "rod-pin-return": steps.RODS_PINNED_KEY,
        "left-hub-return": "bare-shaft-through-ears",
        "right-hub-return": "bare-shaft-through-ears",
        "bar-pin-return": "bars-straight",
        "bar-straightened-return": "bars-straight",
        "strap-set-return": "straps-shake-in-forks",
    }
    for key, target in returns.items():
        assert steps.step_number(target) < steps.step_number(key)
        body = _step_body(key)
        assert re.search(rf"RETURN TO STEP {steps.step_number(target)}\b", body), key
        # The return is the whole step: nothing but its block prefix before it.
        assert re.fullmatch(
            r"((LEFT|RIGHT) HUB: |BONDED PIN: |PIN PUSHED OUT: )?RETURN TO STEP .*", body
        ), key
    for key in steps.SEQUENCE:
        assert ("RETURN TO STEP" in _step_body(key)) == (key in returns), key
    # Each remedy block is consecutive, in order, right after its check.
    for check, block in (
        ("rod-arms-swing", steps.ROD_PIN_REMEDY),
        ("end-hubs-clear", steps.LEFT_HUB_REMEDY + steps.RIGHT_HUB_REMEDY),
        ("bars-straight", ("bar-straightened", "bar-straightened-return")),
        ("bars-swing", steps.BAR_PIN_REMEDY),
        ("straps-shake-in-forks", steps.STRAP_SHAKE_REMEDY),
    ):
        first = steps.SEQUENCE.index(check) + 1
        assert steps.SEQUENCE[first : first + len(block)] == block, check
    # Each hub block opens with its condition; every later step of the block
    # carries the block's prefix, so none reads as part of the main flow.
    for side, block in (
        ("LEFT", steps.LEFT_HUB_REMEDY),
        ("RIGHT", steps.RIGHT_HUB_REMEDY),
    ):
        assert _step_body(block[0]).startswith(
            f"{side} HUB, IF THE LEAF DID NOT PASS THERE: "
        )
        for key in block[1:]:
            assert _step_body(key).startswith(f"{side} HUB: "), key
    # Each bonded-pin block opens with its condition; every later step
    # carries "BONDED PIN:" (#3601 independent read: on the normal path
    # nothing was bonded, so an unprefixed check read as main flow), and the
    # steps after a failed bond's push-out carry "PIN PUSHED OUT:" (#3601
    # Codjiflo r2: a bonded pin that passed never replaces its part).
    for block in (steps.ROD_PIN_REMEDY, steps.BAR_PIN_REMEDY):
        assert _step_body(block[0]).startswith("IF AN ITEM ")
        pushed = next(i for i, key in enumerate(block) if key.endswith("-pin-pushed-out"))
        for key in block[1 : pushed + 1]:
            assert _step_body(key).startswith("BONDED PIN: "), key
        assert block[pushed + 1 :], block
        for key in block[pushed + 1 :]:
            assert _step_body(key).startswith("PIN PUSHED OUT: "), key
    for prefix in ("rod", "bar"):
        assert _step_body(f"{prefix}-pin-bond-held").startswith(
            "BONDED PIN: CURED, CHECK ITEM "
        )
        assert " AND " not in _step_body(f"{prefix}-pin-bond-held")
        assert " AND " not in _step_body(f"{prefix}-pin-bond-swings")
        # A failed bond is not bonded again: the pin comes out and its part is
        # replaced (main's remedy), the new part back to its starting step.
        assert _step_body(f"{prefix}-pin-pushed-out").endswith(
            "PUSH THAT PIN OUT, HEATING THE "
            + ("TINES" if prefix == "rod" else "CHEEKS")
            + " TO ABOUT 250°C."
        )
        # The replace and return steps carry the push-out's own condition, so a
        # bonded pin that passed its cured checks never reaches them.
        assert _step_body(f"{prefix}-replaced").startswith("PIN PUSHED OUT: REPLACE THAT ITEM ")
    # #3563: the right-hub remedy says which way the right ear moves: out,
    # to the span's upper limit as view D prints it (nominal plus band), one
    # action a step: the new setting, then the return on its own.
    span_band = drawing.asm.DIMENSION_TOLERANCES[drawing.asm.EAR_SPAN_DIMENSION]
    upper = (bank.EAR_INNER_SPAN + span_band[1]) / 25.4
    assert drawing.notes.EAR_SPAN_UPPER_TEXT == f"{upper:.3f}" == "6.099"
    assert _step_body("right-hub-span-to-upper-limit") == (
        f"RIGHT HUB: AT STEP {steps.step_number('south-bracket-span-set')}, SET "
        "THE EAR SPAN TO ITS UPPER LIMIT, 6.099."
    )
    assert _step_body("right-hub-return") == (
        f"RIGHT HUB: RETURN TO STEP {steps.step_number('bare-shaft-through-ears')}."
    )
    assert ";" not in drawing.FITUP_STEPS


def test_the_steps_name_parts_by_bom_item() -> None:
    """drawing-guidelines.md rule 22: steps name parts by BOM item; the
    item numbers are the native table's (component order, proved at build
    by _validate_bom)."""
    assert drawing.ITEM_NUMBERS == {
        stem: index for index, stem in enumerate(drawing.BOM_COMPONENTS, start=1)
    }
    for stem in drawing.BOM_COMPONENTS:
        assert drawing.item(stem) in drawing.FITUP_STEPS, stem
    # A part number prints only where a step sends the fitter to that part's
    # own drawing (the keeper's finished top).
    for stem, number in drawing.BOM_PART_NUMBERS.items():
        if stem != drawing.explode.KEEPER:
            assert number not in drawing.FITUP_STEPS, stem
    assert drawing.items_text(drawing.NORTH_KEEPER_DETAIL.stems) == "ITEMS 6, 7 AND 8"
    assert drawing.NORTH_KEEPER_DETAIL.parts == "ITEMS 6,7,8"
    assert drawing.NORTH_BRACKET_DETAIL.parts == "ITEMS 3,4,5"
    assert "ITEMS 6, 7 AND 8 ARE BALLOONED IN DETAIL C." in drawing.EXPLODED_CAPTION


def test_no_compass_or_private_words_print() -> None:
    """Screen review (rubric 8a1a516): NORTH/SOUTH named no edge a fitter
    can see; directions are LEFT/RIGHT as drawn in views D and E."""
    printed = "\n".join(
        (
            drawing.FITUP_STEPS,
            drawing.ASSEMBLED_CAPTION,
            drawing.EXPLODED_CAPTION,
            *(view.label_text for view in drawing.LETTERED_VIEWS),
            *(text for text, _, _ in drawing.DETAIL_POINTERS),
            *(text for text, _, _ in drawing.PLAN_POINTERS),
            *drawing.DIMENSION_CALLOUTS.values(),
            *drawing.DIMENSION_BELOW_CALLOUTS.values(),
        )
    )
    for word in ("NORTH", "SOUTH", "STRAP", "APEX", "CROWN", "CLOSED UP", "HUB 0", "SPLIT OF"):
        assert word not in printed, word


def test_each_lettered_view_has_a_viewing_arrow_letter() -> None:
    """drawing-guidelines.md rule 9: the partial views D-G are lettered and
    each has its viewing arrow on sheet 1; only a view off its sheet's scale
    prints a scale."""
    letters = [view.title.removeprefix("VIEW ") for view in drawing.ARROWED_VIEWS]
    assert letters == ["D", "E", "F", "G"]
    for view in drawing.LETTERED_VIEWS:
        sheet_scale = view.sheet_scale
        assert ("SCALE" in view.label_text) == (view.scale != sheet_scale)
    assert "SCALE" not in drawing.ROCKER_BANK.label_text
    assert drawing.KEEPER_PLAN.label_text.endswith("SCALE 1 : 2")


def test_the_right_bracket_is_set_to_the_ear_span_and_the_end_hubs_checked() -> None:
    """#3114: the arms float on the shaft, each located by its rod, so there is
    no washer, spring or hub stack to set. The right bracket is set by edge
    finder and DRO off the left one to view D's ear inner-face span (named,
    never restated) while the shaft runs bare through both ears (Codjiflo on
    PR #3116: with the arms on, each inner face is .05 from its hub, out of an
    edge finder's reach). The end hubs are then checked clear of their ears
    on a feeler leaf while it is only clamped (machinist review, PR #1605),
    each end with its own remedy block (rule 22), and the arms are checked to slide
    with their rods once the shaft is held."""
    import draw_dt_drive_train_assembly as drive_train

    asm = drawing.asm
    arm = drawing.item("ch-rocker-arm")
    shaft = drawing.item("ch-pivot-shaft")
    bracket = drawing.item(drawing.explode.BRACKET)
    stood = _step_body("south-bracket-stood")
    assert steps.NORTH_BRACKET_SET_REF in stood
    assert shaft not in stood
    bare = _step_body("bare-shaft-through-ears")
    assert f"THE RIGHT {bracket} EAR" in bare and "HUB" not in bare
    span = _step_body("south-bracket-span-set")
    assert "EDGE FINDER" in span and "DRO" in span
    assert f"{drawing.ROCKER_BANK.title} EAR SPAN" in span
    # Rule 4 (Codjiflo, PR #3116): the callout names the faces and what the
    # band protects, the arm by its BOM item; one line (an above-callout).
    assert drawing.DIMENSION_CALLOUTS[asm.EAR_SPAN_DIMENSION] == (
        f"EAR SPAN, INNER FACES: END {arm} HUBS CLEAR"
    )
    nominal = asm.PIVOT_CHAIN_Z[1] - asm.PIVOT_CHAIN_Z[0]
    assert nominal == pytest.approx(bank.EAR_INNER_SPAN)
    # The steps never restate the nominal (view D prints it); the right-hub
    # remedy prints only the band's upper limit (#3563), a different number.
    for text in (f"{nominal / 25.4:.3f}", f"{nominal / 25.4:.2f}"):
        assert not re.search(rf"(?<![\d.]){re.escape(text)}(?![\d])", drawing.FITUP_STEPS)
    assert drawing.notes.EAR_SPAN_UPPER_TEXT in _step_body("right-hub-span-to-upper-limit")
    assert asm.DIMENSION_TOLERANCES[asm.EAR_SPAN_DIMENSION] == (
        -bank.EAR_SPAN_BAND,
        bank.EAR_SPAN_BAND,
    )
    assert asm.DRAWING_PRECISION[asm.PIVOT_FEATURE][asm.EAR_SPAN_DIMENSION] == 3
    assert f"THE RIGHT {bracket} EAR" in _step_body("rocker-hubs-threaded")
    # Codjiflo, PR #3116: a floating end arm would slide away from the leaf
    # and pass a mis-set ear, so one step first pushes each end arm toward
    # its ear until its rod stops it (the extreme END_CLEARANCE_MIN charges)
    # and the check gauges it held there.
    pushed = steps.step_number("end-arms-pushed-to-ears")
    assert pushed == steps.step_number("end-hubs-clear") - 1
    assert _step_body("end-arms-pushed-to-ears") == (
        f"PUSH EACH END {arm} TOWARD ITS EAR UNTIL "
        f"{drawing.item(drawing.explode.ROD)} STOPS IT."
    )
    clear = _step_body("end-hubs-clear")
    assert drawing.notes.setting_row("end-hubs-clear") in clear
    assert f"EACH END {arm} HUB, HELD AS AT STEP {pushed}, AND ITS" in clear
    assert f"({drawing.SOUTH_END.title}, SHEET 4)" in clear
    assert drawing.SHEET_NAMES.index(drawing.DETAIL_SHEET) == 3
    # One remedy block per end, one action a step, each back to the bare
    # shaft with the right bracket still only clamped; the left one re-runs
    # the drive train's set, screw and recheck sub-steps (positive control on
    # their wording). Drawn out of the hubs, the shaft lets the arms hang on
    # their rods: no step swings them down.
    hold_down = drawing.item(drawing.explode.BRACKET_HOLD_DOWN)
    assert f"LOOSEN THE LEFT {hold_down}." in _step_body("left-hub-hold-down-loosened")
    number = dt_drive_train_steps.step_number(steps.NORTH_BRACKET_SET_KEY)
    for key, letter, action in (
        ("left-hub-bracket-reset", "B", f"RESET THE LEFT {bracket}"),
        ("left-hub-hold-down-tightened", "E", f"TIGHTEN THE LEFT {hold_down}"),
        ("left-hub-bracket-rechecked", "F", "RECHECK"),
    ):
        assert _step_body(key).endswith(
            f"{action} PER {steps.NORTH_BRACKET_SET_REF}{letter}."
        ), key
    dt_steps = _sequence_steps(
        "\n".join((drive_train.CONE_CRANK_STEPS, drive_train.BANK_STEPS))
    )
    assert "SET THE EAR INNER FACE" in dt_steps[f"{number}B"]
    assert "SCREW THE MHA-CH-08 DOWN" in dt_steps[f"{number}E"]
    assert "RECHECK" in dt_steps[f"{number}F"]
    drawn = f"DRAW {shaft} BACK AS AT STEP {steps.step_number('shaft-drawn-back')}."
    for side in ("left", "right"):
        assert _step_body(f"{side}-hub-shaft-drawn-back").endswith(drawn)
        assert _step_body(f"{side}-hub-clamp-eased").endswith(
            f"EASE THE CLAMP ON THE RIGHT {bracket}."
        )
    assert not re.search(r"SWING [A-Z0-9 ]*DOWN", drawing.FITUP_STEPS)
    follow = _step_body("arms-follow-rods")
    assert arm in follow and drawing.item(drawing.explode.ROD) in follow
    assert "WASHER" not in _step_body("rocker-hubs-threaded")
    order = [
        "north-bracket-held",
        "south-bracket-stood",
        "bare-shaft-through-ears",
        "south-bracket-span-set",
        "south-bracket-clamped",
        "shaft-drawn-back",
        "arms-swung-up",
        "rocker-hubs-threaded",
        "end-arms-pushed-to-ears",
        "end-hubs-clear",
        *steps.LEFT_HUB_REMEDY,
        *steps.RIGHT_HUB_REMEDY,
        "south-foot-transferred",
        "south-bracket-screwed",
        "south-bracket-held",
        "shaft-set",
        "set-screws-driven",
        "pivot-shaft-held",
        "arms-follow-rods",
    ]
    numbers = [steps.step_number(key) for key in order]
    assert numbers == sorted(numbers)


def test_the_end_hub_leaf_is_the_least_worst_case_air_floored() -> None:
    """#3114: the end-hub feeler leaf is rocker_bank_layout's least worst-case
    air between an end hub and its ear, floored to the .001 a feeler set is
    sold in and never under the running floor (.004)."""
    notes = drawing.notes
    leaf_in = notes.END_HUB_LEAF_MM / 25.4
    least_in = min(bank.END_CLEARANCE_MIN) / 25.4
    assert leaf_in == pytest.approx(math.floor(least_in * 1000.0) / 1000.0)
    assert leaf_in <= least_in
    assert notes.END_HUB_LEAF_MM >= bank.RUNNING_FLOOR
    assert _setting_table_row("end-hubs-clear")[2:] == (
        f"{drawing.item('ch-rocker-arm')} HUB TO EAR",
        "-",
        ".009 MIN",
        "FEELER LEAF",
    )


def test_the_shaft_set_screws_are_not_staked() -> None:
    """Owner ruling 2026-11-20 (#2397, option 2): the pivot and fulcrum
    shafts come out to change one channel part, so their set screws hold on
    the shafts' flats unstaked; the channel contract accepts both unlocked
    joints."""
    from _paths import CAD_ROOT
    from machinist_exceptions import load_exceptions

    assert "STAKE" not in drawing.FITUP_STEPS
    pointers = drawing.DETAIL_POINTERS + drawing.PLAN_POINTERS
    assert not any("STAKE" in text for text, _, _ in pointers)
    entries = {
        entry.id: entry
        for entry in load_exceptions(
            CAD_ROOT / "config", "ch_channel_assembly", "assembly"
        )
    }
    for ruling in ("U-MHA-SH-VN-54-in-CH-08-no-lock", "U-MHA-CH-VN-55-no-lock"):
        assert entries[ruling].kind == "accept"


def test_each_step_column_fits_its_field() -> None:
    template = drawing._TEMPLATE
    right = template.width_m - drawing.BORDER
    for column, block in drawing.FITUP_NOTES:
        lines = block.splitlines()
        left, top = column.xy
        limit = right if left == drawing.STEPS_RIGHT_X else drawing.STEPS_RIGHT_X - 0.005
        assert left + max(map(len, lines)) * NOTE_CHAR_WIDTH < limit
        assert top - len(lines) * NOTE_LINE_PITCH >= column.bottom - 1e-9
        assert top < template.height_m - drawing.BORDER
        if left == drawing.STEPS_RIGHT_X:
            assert column.bottom >= template.title_block_top_m
    sheets = {column.sheet for column, _ in drawing.FITUP_NOTES}
    assert sheets == set(drawing.SHEET_NAMES[2:])
    headings = [block.splitlines()[0] for _, block in drawing.FITUP_NOTES]
    assert headings[0] == "ROCKER BANK FIT-UP"
    lever = headings.index("LEVER BANK FIT-UP")
    assert all(h == "ROCKER BANK FIT-UP (CONT.)" for h in headings[1:lever])
    assert all(h == "LEVER BANK FIT-UP (CONT.)" for h in headings[lever + 1 :])
    # Round 1 review: no near-empty step column beside an empty half sheet
    # (every column is full height or beside a view; sheet 6's right half
    # holds view G and the setting table, not steps).
    for column, block in drawing.FITUP_NOTES:
        assert len(block.splitlines()) > column.capacity // 2, column
    # Each 1:1 bank's right-hand end (the keeper and ear outer faces) clears
    # the right column.
    for view, south_z in (
        (drawing.ROCKER_BANK, -80.4589 - 2.0),
        (drawing.LEVER_BANK, drawing.asm.LUG_INNER_FACE_Z[0] - 10.0),
    ):
        assert view.sheet_xy(south_z, 0.0)[0] < drawing.STEPS_RIGHT_X - 0.010
    # View G's outline (model x 7.4-217.1, y 955.6-1078.6 on the 06616793e
    # farm leaf) sits right of the full-height left column, inside the border,
    # with its label above the short right column.
    hookup = drawing.HOOKUP
    cx, cy, _ = hookup.centre_xyz
    x0, x1 = (hookup.centre[0] + (x - cx) * hookup.mm for x in (7.4, 217.1))
    y0, y1 = (hookup.centre[1] + (y - cy) * hookup.mm for y in (955.6, 1078.6))
    left_column_right = drawing.STEPS_LEFT_X + drawing.STEPS_LINE_WIDTH * NOTE_CHAR_WIDTH
    assert left_column_right + 0.010 < x0 and x1 < right
    assert y1 < template.height_m - drawing.BORDER
    assert y0 == pytest.approx(drawing.HOOKUP_BOTTOM_Y)
    label_lines = len(hookup.label_text.splitlines())
    assert y0 - 0.004 - label_lines * NOTE_LINE_PITCH > drawing.SETTING_TABLE_XY[1]


def test_a_column_never_splits_a_step_and_overflow_is_refused() -> None:
    tiny = (drawing.StepColumn("S", (0.0, 0.1), 0.1 - 6 * NOTE_LINE_PITCH),)
    with pytest.raises(AssertionError, match="overflows"):
        drawing.flow_steps("H", steps.ROCKER_SEQUENCE, drawing.FITUP_TEXT, tiny)


def test_steps_are_one_blank_line_apart_and_never_split() -> None:
    """User request: a blank line between consecutive steps; none before
    the first step of a column, none inside a step."""
    for _column, block in drawing.FITUP_NOTES:
        lines = block.splitlines()
        heads = [i for i, line in enumerate(lines) if STEP_HEAD.match(line)]
        assert heads[0] == 1
        for previous, head in zip(heads, heads[1:]):
            assert lines[head - 1] == ""
            assert "" not in lines[previous : head - 1]
        assert "" not in lines[heads[-1] :]


def test_the_package_sheets_and_settings_contract() -> None:
    assert drawing.SHEET_NAMES == (
        "ASSEMBLED VIEWS",
        "EXPLODED VIEW + BOM",
        "ROCKER BANK FIT-UP",
        "ROCKER BANK FIT-UP (CONT.)",
        "LEVER BANK FIT-UP",
        "LEVER BANK FIT-UP (CONT.)",
    )
    assert set(drawing.SHEET_SCALES) == set(drawing.SHEET_NAMES)
    asm = drawing.asm
    explode = drawing.explode
    kept = {
        **drawing.EAR_SPAN_KEEP,
        **drawing.TIP_KEEP,
        **drawing.LUG_KEEP,
        **drawing.PLAN_KEEP,
    }
    assert drawing.ROCKER_KEEP == {**drawing.EAR_SPAN_KEEP, **drawing.TIP_KEEP}
    assert sorted(kept) == sorted(asm.DIMENSION_FEATURE)
    # Each bank view shows only its own axis's sketch.
    assert {asm.DIMENSION_FEATURE[name] for name in drawing.LUG_KEEP} == {
        asm.FULCRUM_FEATURE
    }
    assert {asm.DIMENSION_FEATURE[name] for name in drawing.ROCKER_KEEP} == {
        asm.PIVOT_FEATURE
    }
    assert {asm.DIMENSION_FEATURE[name] for name in drawing.PLAN_KEEP} == {
        asm.KEEPER_PLAN_FEATURE
    }
    assert set(drawing.notes.DIMENSION_CALLOUTS) == set(kept)
    assert drawing.notes.REFERENCE_DIMENSIONS == {
        asm.LUG_SPAN_DIMENSION,
        asm.KEEPER_REAR_Z_DIMENSION,
    }
    assert set(asm.DIMENSION_TOLERANCES) == set(kept) - drawing.notes.REFERENCE_DIMENSIONS
    # Every kept dimension text lands on view D, E or F, inside the border,
    # left of the right column.
    left_column_right = drawing.STEPS_LEFT_X + drawing.STEPS_LINE_WIDTH * NOTE_CHAR_WIDTH
    right = drawing._TEMPLATE.width_m - drawing.BORDER
    for x, y in kept.values():
        assert drawing.BORDER < x < drawing.STEPS_RIGHT_X
        assert drawing.BORDER < y < drawing._TEMPLATE.height_m - drawing.BORDER
    # The ear span's text sits over the middle of the span it dimensions.
    (span_x, _), = drawing.EAR_SPAN_KEEP.values()
    span_ends = [
        drawing.ROCKER_BANK.sheet_xy(z, 0.0)[0] for z in asm.PIVOT_CHAIN_Z[:2]
    ]
    assert span_x == pytest.approx(sum(span_ends) / 2.0)
    # Its one-line callout stands between the span's two extension lines.
    span_callout = drawing.DIMENSION_CALLOUTS[asm.EAR_SPAN_DIMENSION]
    assert len(span_callout) * NOTE_CHAR_WIDTH / 2.0 + 0.003 < (
        abs(span_ends[0] - span_ends[1]) / 2.0
    )
    # Detail A, right of sheet 4's left column, is centred on the air between
    # the right ear's inner face and the end hub, both inside its circle.
    detail = drawing.SOUTH_END
    radius = detail.crop_radius_mm * detail.mm
    assert detail.centre[0] - radius > left_column_right + 0.010
    assert detail.centre[0] + radius < right
    assert detail.crop_label_xy[1] - 3 * NOTE_LINE_PITCH > drawing._TEMPLATE.title_block_top_m
    ear_z, hub_z = asm.PIVOT_CHAIN_Z[0], bank.HUB0_SOUTH_FACE_Z
    assert detail.centre_xyz[2] == pytest.approx((ear_z + hub_z) / 2.0)
    assert hub_z - ear_z == pytest.approx(bank.END_FLOAT[0])
    assert hub_z - ear_z < detail.crop_radius_mm
    assert detail.stems >= {explode.BRACKET, "ch-rocker-arm", "ch-pivot-shaft"}
    # Detail A names the two bodies the end-hub check is read between, each
    # pointer tip inside the crop circle and each text outside it.
    assert [text.split()[0] for text, _, _ in drawing.DETAIL_POINTERS] == [
        drawing.BOM_PART_NUMBERS[stem] for stem in ("ch-rocker-arm", explode.BRACKET)
    ]
    for text, (tx, ty), (px, py) in drawing.DETAIL_POINTERS:
        assert (px - detail.centre[0]) ** 2 + (py - detail.centre[1]) ** 2 < radius**2
        lines = text.splitlines()
        width = max(map(len, lines)) * NOTE_CHAR_WIDTH
        bottom = ty - len(lines) * NOTE_LINE_PITCH
        near_x = min(max(detail.centre[0], tx), tx + width)
        near_y = min(max(detail.centre[1], bottom), ty)
        assert math.dist((near_x, near_y), detail.centre) > radius
        assert left_column_right < tx and tx + width < right
        assert ty < drawing._TEMPLATE.height_m - drawing.BORDER
    # The parent view D carries the detail's boundary, about the same model
    # point the detail is centred on, lettered outside it.
    (cx, cy), parent_radius = drawing.detail_boundary(drawing.ROCKER_BANK, detail)
    assert (cx, cy) == drawing.ROCKER_BANK.sheet_xy(
        detail.centre_xyz[2], detail.centre_xyz[1]
    )
    assert parent_radius == detail.crop_radius_mm / 1000.0
    lx, ly = drawing.letter_xy((cx, cy), parent_radius)
    assert (lx - cx) ** 2 + (ly - cy) ** 2 > parent_radius**2
    assert drawing.BORDER < lx < drawing.STEPS_RIGHT_X
    assert detail.letter == drawing.DETAIL_LETTER
    assert detail.title == f"DETAIL {drawing.DETAIL_LETTER}"
    assert drawing.ROCKER_BANK.title in detail.parts

def _iso(point: tuple[float, float, float]) -> tuple[float, float]:
    """The *Isometric projection (eye on +x +y +z), model mm on the view."""
    x, y, z = point
    return (x - z) * 0.5**0.5, (2.0 * y - x - z) / 6.0**0.5


def test_the_exploded_details_enlarge_the_north_hardware_beside_the_bom() -> None:
    explode = drawing.explode
    north = "north"
    lug_z = drawing.FULCRUM_KEEPER_CENTRE_Z + drawing.KEEPER_Z_OFF
    # 60 north, then the whole north-end cluster 30 further north and 570 up,
    # clear of the hanging rocker arms (r10 machinist review, DETAIL B), and
    # (r11) between the bank and the north-most channel pulled out of it.
    assert drawing.exploded_offset(explode.BRACKET, north) == (0.0, 570.0, 90.0)
    assert drawing.exploded_offset(explode.BRACKET_SET_SCREW, north) == (0.0, 595.0, 90.0)
    assert drawing.exploded_offset(explode.KEEPER_FOOT_SCREW, north) == (0.0, 50.0, 50.0)
    assert drawing.exploded_offset(explode.BRACKET_HOLD_DOWN, north) == (0.0, 630.0, 90.0)
    assert drawing.exploded_offset(explode.BRACKET, "south") == (0.0, 0.0, -60.0)
    bracket, keeper = drawing.NORTH_BRACKET_DETAIL, drawing.NORTH_KEEPER_DETAIL
    assert drawing.EXPLODED_DETAILS == (bracket, keeper)
    # #1660 r3 (rule 22): lifted, the cluster read as the lever bank's, so an
    # explode trail runs from the bracket's seat on the rocker shaft, north
    # along its axis, then up to DETAIL B's centre (its exploded bore).
    seat, along, lifted = drawing.north_end_trail_mm()
    assert seat == (*drawing.ROCKER_PIVOT_XY, bank.PIVOT_BRACKET_Z[1])
    assert along == (*drawing.ROCKER_PIVOT_XY, seat[2] + 90.0)
    assert lifted == pytest.approx(bracket.centre_xyz)
    assert (drawing.TRAIL_LINE_STYLE, drawing.TRAIL_COLOR) == (2, 0)
    # Machinist review (PR #1605): at the upper right the letter B sat over
    # the rocker bank's stack beside the circle; the lower left is open.
    assert bracket.letter_corner == (-1, -1)
    # PR #2702 machinist review: DETAIL C's letter stood on the bar bank's
    # right edge; it sits farther out than the default, down and right.
    assert keeper.letter_corner == (1, -1)
    assert keeper.letter_offset > drawing.DETAIL_LETTER_OFFSET
    centre, radius = (0.0, 0.0), 0.005
    assert drawing.letter_xy(centre, radius, keeper.letter_corner, keeper.letter_offset)[0] > (
        drawing.letter_xy(centre, radius, keeper.letter_corner)[0]
    )
    # Each cluster member's exploded reference point projects inside its
    # circle with room for the part round it: the set screw above the ear
    # apex, the hold-down over its foot hole.
    pivot_x, pivot_y = drawing.ROCKER_PIVOT_XY
    ear_z = bank.PIVOT_BRACKET_Z[1]
    members = {
        bracket: (
            drawing._exploded(
                (pivot_x, pivot_y + 15.0, ear_z), explode.BRACKET_SET_SCREW, north
            ),
            drawing._exploded(
                (pivot_x, pivot_y - 15.0, ear_z + 8.0), explode.BRACKET_HOLD_DOWN, north
            ),
        ),
        keeper: (
            drawing._exploded(
                (keeper.centre_xyz[0], drawing.LEVER_FULCRUM_XY[1] + 10.0, lug_z),
                explode.KEEPER_SET_SCREW,
                north,
            ),
            drawing._exploded(
                (keeper.centre_xyz[0], drawing.LEVER_FULCRUM_XY[1] - 20.0, lug_z + 8.5),
                explode.KEEPER_FOOT_SCREW,
                north,
            ),
        ),
    }
    for detail, points in members.items():
        assert detail.orientation == "*Isometric" and detail.exploded
        assert detail.title == f"DETAIL {detail.letter}"
        cu, cv = _iso(detail.centre_xyz)
        for point in points:
            u, v = _iso(point)
            assert ((u - cu) ** 2 + (v - cv) ** 2) ** 0.5 < detail.crop_radius_mm - 5.0
    # The column right of the BOM, inside the border and above the title
    # block, the circles apart and each label (under its circle) inside it.
    template = drawing._TEMPLATE
    bom_right = drawing.BOM_ANCHOR[0] + sum(drawing.BOM_COLUMN_WIDTHS.values())
    right = template.width_m - drawing.BORDER
    previous_bottom = template.height_m - drawing.BORDER
    for detail in drawing.EXPLODED_DETAILS:
        (x, y), radius = detail.centre, detail.crop_radius_mm * detail.mm
        assert bom_right + 0.004 < x - radius and x + radius < right
        assert y + radius < previous_bottom
        lines = detail.label_text.splitlines()
        lx, ly = detail.crop_label_xy
        assert lx + max(map(len, lines)) * NOTE_CHAR_WIDTH < right
        previous_bottom = ly - len(lines) * NOTE_LINE_PITCH
    assert previous_bottom > template.title_block_top_m


def test_the_lifted_foot_screws_clear_their_uprights_in_the_isometric() -> None:
    """r2 machinist review (sheet 2, DETAILS B/C): lifted 25, each keeper
    foot screw and bracket hold-down hung in front of its upright (it sits
    outboard of it, nearer the eye) and read as resting against it.  Lifted
    straight up its foot hole's axis, each tip now projects over the
    upright's top silhouette in the isometric (eye on +x +y +z) by 2 mm, on
    both sides, and each north head stays inside its detail's crop."""
    import ch_fulcrum_keeper_spec as keeper
    import ch_pivot_bracket_sides as sides
    import ch_pivot_bracket_spec as bracket
    import ch_vn_bracket_hold_down_screw_spec as hold_down
    import ch_vn_frame_side_screw_spec as foot_screw

    explode = drawing.explode
    root2, root5, root6 = 2.0**0.5, 5.0**0.5, 6.0**0.5
    # 2y - x - z (the isometric's v times root 6) over a round top: the
    # half-round of radius r about height h peaks at 2h + r * root 5, and the
    # upright's inboard face (-z_rel = half its thickness) stands highest.
    lug_top = 2.0 * keeper.SHAFT_AXIS_H + keeper.CROWN_R * root5 + keeper.LUG_HALF_T
    arch_h = bracket.EAR_TOP_Y - bracket.EAR_ARCH_R
    ear_top = 2.0 * arch_h + bracket.EAR_ARCH_R * root5 + bracket.EAR_T / 2.0
    keeper_out = keeper.KEEPER_SCREW_Z_OFF - keeper.KEEPER_Z_OFF
    keeper_seat = keeper.FOOT_H - keeper.CBORE_DEPTH_MM
    keeper_case = (explode.KEEPER_FOOT_SCREW, explode.KEEPER, lug_top, keeper_out)
    bracket_case = (explode.BRACKET_HOLD_DOWN, explode.BRACKET, ear_top, sides.HOLE_Z)
    cases = (
        (*keeper_case, keeper_seat, foot_screw),
        (*bracket_case, bracket.FOOT_H, hold_down),
    )
    for stem, part, top, outboard, seat_y, screw in cases:
        for side, sign in (("south", -1.0), ("north", 1.0)):
            moved = drawing.exploded_offset(stem, side)
            carried = drawing.exploded_offset(part, side)
            # Straight up its foot hole's axis.
            assert (moved[0], moved[2]) == (carried[0], carried[2])
            tip_y = seat_y - screw.SHANK_LEN + moved[1] - carried[1]
            tip = 2.0 * tip_y - sign * outboard - screw.SHANK_DIA / 2.0 * root2
            assert (tip - top) / root6 > 2.0, (stem, side)

    # The lifted north heads inside their details' crops.
    pivot_x, pivot_y = drawing.ROCKER_PIVOT_XY
    fulcrum_x, fulcrum_y = drawing.LEVER_FULCRUM_XY
    keeper_z = drawing.FULCRUM_KEEPER_CENTRE_Z + drawing.KEEPER_Z_OFF
    hold_down_top = (
        pivot_x,
        pivot_y - bracket.BORE_H + bracket.FOOT_H + hold_down.HEAD_H,
        bank.PIVOT_BRACKET_Z[1] + sides.HOLE_Z,
    )
    foot_screw_top = (
        fulcrum_x,
        fulcrum_y - keeper.SHAFT_AXIS_H + keeper.FOOT_H,
        keeper_z + keeper_out,
    )
    bracket_head = (drawing.NORTH_BRACKET_DETAIL, hold_down_top, explode.BRACKET_HOLD_DOWN)
    keeper_head = (drawing.NORTH_KEEPER_DETAIL, foot_screw_top, explode.KEEPER_FOOT_SCREW)
    heads = ((*bracket_head, hold_down), (*keeper_head, foot_screw))
    for detail, head_top, stem, screw in heads:
        cu, cv = _iso(detail.centre_xyz)
        u, v = _iso(drawing._exploded(head_top, stem, "north"))
        reach = ((u - cu) ** 2 + (v - cv) ** 2) ** 0.5 + screw.HEAD_DIA / 2.0
        assert reach < detail.crop_radius_mm - 3.0, stem


def test_the_bracket_balloon_lands_left_of_its_lifted_hold_down() -> None:
    """Proof run 20261017T222049387Z, sheet 2: walked to the ear's apex, the
    bracket's leader 3 ran down the lifted hold-down (item 7) that stands
    over it.  It lands on the foot's free-end edge instead: on the part, at
    half the foot's height, and in the isometric well left of the
    hold-down's head (the north bracket carries its hold-down, so their
    offsets cancel apart from the lift, which moves v only)."""
    import ch_pivot_bracket_sides as sides
    import ch_pivot_bracket_spec as bracket
    import ch_vn_bracket_hold_down_screw_spec as hold_down

    x, y, z = drawing.BRACKET_BALLOON_POINT_MM
    assert x == -bracket.FOOT_W / 2.0
    assert z == sides.FOOT_Z1
    assert 0.0 < y < bracket.FOOT_H
    # The north bracket's part frame runs with the machine's (its foot
    # toward machine +z), so the part point projects like a machine one.
    assert sides.OUTBOARD_SIGN["N"] == 1.0
    moved = drawing.exploded_offset(drawing.explode.BRACKET_HOLD_DOWN, "north")
    carried = drawing.exploded_offset(drawing.explode.BRACKET, "north")
    assert (moved[0], moved[2]) == (carried[0], carried[2])
    head_left = _iso((0.0, 0.0, sides.HOLE_Z))[0] - hold_down.HEAD_DIA / 2.0
    # 6.0 model mm, 0.86 on the sheet at 1:7: a leader's width and more.
    assert head_left - _iso((x, y, z))[0] > 5.0


def test_the_north_keeper_balloons_on_detail_c_right_of_its_lifted_screws() -> None:
    """#1895 machinist review: on the 1:7 view the north keeper stands in
    front of the near-black rocker bank, and leaders 8-10 crossing it were
    lost. Its family balloons on DETAIL C, the caption says so, and the
    keeper's leader lands on its inner crown apex, which projects right of
    both lifted screws (eye on +x +y +z), so its ring slot is the right-most
    and its leader crosses neither screw."""
    from _hole_spec import THREAD_MAJOR_MM
    import ch_fulcrum_keeper_spec as keeper
    import ch_vn_frame_side_screw_spec as foot_screw

    explode = drawing.explode
    detail = drawing.NORTH_KEEPER_DETAIL
    family = {explode.KEEPER, explode.KEEPER_SET_SCREW, explode.KEEPER_FOOT_SCREW}
    assert drawing.KEEPER_DETAIL_BALLOON_STEMS == detail.stems == family
    assert detail.title in drawing.EXPLODED_CAPTION
    assert drawing.BALLOON_POINTS_MM[explode.KEEPER] == (
        -keeper.LUG_HALF_T,
        keeper.CROWN_TOP_Y,
        0.0,
    )
    # North keeper: part +x is outboard, machine +z. Relative to the lug
    # mid-plane, the apex sits 4 inboard, the set screw on the mid-plane and
    # the foot screw SCREW_X outboard; both screws move straight up.
    for stem in (explode.KEEPER_SET_SCREW, explode.KEEPER_FOOT_SCREW):
        moved = drawing.exploded_offset(stem, "north")
        carried = drawing.exploded_offset(explode.KEEPER, "north")
        assert (moved[0], moved[2]) == (carried[0], carried[2])
    apex_u = _iso((0.0, 0.0, -keeper.LUG_HALF_T))[0]
    set_screw_right = THREAD_MAJOR_MM[keeper.SET_SCREW_THREAD] / 2.0
    foot_screw_right = _iso((0.0, 0.0, keeper.SCREW_X))[0] + foot_screw.HEAD_DIA / 2.0
    assert apex_u - set_screw_right > 1.5
    assert apex_u - foot_screw_right > 5.0
    # The ring stays in the column above DETAIL C: the farm read its outline
    # 44.1 mm tall about the crop centre (run 20261023T222629630Z), so the
    # top balloon reaches 22.05 + margin + a balloon radius over it, under
    # DETAIL B's three-line label.
    bracket_label_bottom = (
        drawing.NORTH_BRACKET_DETAIL.crop_label_xy[1]
        - len(drawing.NORTH_BRACKET_DETAIL.label_text.splitlines()) * NOTE_LINE_PITCH
    )
    ring_top = (
        detail.centre[1]
        + 0.02205
        + drawing.KEEPER_DETAIL_BALLOON_MARGIN
        + drawing.BALLOON_MAX_RADIUS
    )
    assert ring_top + 0.004 < bracket_label_bottom


def test_the_pivot_shaft_is_drawn_north_and_ballooned_on_its_bare_run() -> None:
    """#1895, R5 and farm run 20261117T130021685Z machinist reviews: left in
    the hubs, only a stub of the shaft showed and balloon 1 landed on that
    sliver. The explode draws it north, the way the fit-up pushes it in,
    wholly out of the hubs and short of the pulled channel's hub; balloon 1
    lands on its north flat's eye-side edge and stands straight above it."""
    import ch_pivot_shaft_spec as shaft

    explode = drawing.explode
    offset = drawing.exploded_offset(explode.PIVOT_SHAFT, "north")
    assert offset == drawing.exploded_offset(explode.PIVOT_SHAFT, "south")
    assert offset[:2] == (0.0, 0.0) and offset[2] > 0.0
    south_end = bank.PIVOT_SHAFT_SOUTH_Z + offset[2]
    north_tip = bank.PIVOT_SHAFT_NORTH_Z + shaft.DOME_HEIGHT + offset[2]
    assert south_end > bank.HUB19_NORTH_FACE_Z + 20.0
    pulled = drawing.exploded_offset(explode.ARM, "north-most")[2]
    assert north_tip + 50.0 < bank.HUB19_NORTH_FACE_Z - HUB_LENGTH + pulled
    x, y, z = drawing.BALLOON_POINTS_MM[drawing.PIVOT_SHAFT_STEM]
    radius = shaft.SHAFT_DIA / 2.0
    assert y == pytest.approx(radius - shaft.FLAT_DEPTH)
    assert x > 0.0 and math.hypot(x, y) == pytest.approx(radius)
    assert z == pytest.approx(-bank.PIVOT_SHAFT_FLAT_STATIONS[1])
    dx, dy = drawing.PIVOT_SHAFT_BALLOON_OFFSET
    assert dx == 0.0 and dy > drawing.BALLOON_MAX_RADIUS + 0.008


def test_the_fulcrum_shaft_balloon_lands_on_its_bare_run_past_the_south_keeper() -> None:
    """PR #2702 machinist review: leader 2 ended among the stacked lever hubs,
    where the shaft shows only as slivers. It lands on the south flat's
    eye-side edge, which the shaft's withdrawal carries past the exploded
    south keeper onto the shaft's bare run."""
    import ch_fulcrum_shaft_spec as shaft

    x, y, z = drawing.BALLOON_POINTS_MM[drawing.explode.FULCRUM_SHAFT]
    assert y == pytest.approx(shaft.FLAT_HEIGHT)
    assert x > 0.0 and math.hypot(x, y) == pytest.approx(shaft.SHAFT_R)
    assert z == pytest.approx(-shaft.FLAT_PITCH / 2.0)
    shaft_dz = drawing.exploded_offset(drawing.explode.FULCRUM_SHAFT, "south")[2]
    keeper_dz = drawing.exploded_offset(drawing.explode.KEEPER, "south")[2]
    point_z = z + shaft_dz
    tip_z = -shaft.SHAFT_LENGTH / 2.0 + shaft_dz
    keeper_outer_z = -drawing.KEEPER_Z_OFF + keeper_dz - drawing.KEEPER_LUG_HALF_T
    assert tip_z < point_z - shaft.FLAT_LENGTH / 2.0
    assert point_z + shaft.FLAT_LENGTH / 2.0 + 20.0 < keeper_outer_z


def test_the_bom_covers_every_family_once_with_its_sku() -> None:
    assert len(drawing.BOM_COMPONENTS) == 16
    assert set(drawing.BOM_PART_NUMBERS) == set(drawing.BOM_COMPONENTS)
    # One Number per native file: the bought pivot pin's two member rows
    # share MHA-SH-VN-58 and bind by (file, member) instead.
    files = {
        drawing.BOM_COMPONENT_IDENTITIES[key][0] for key in drawing.BOM_COMPONENTS
    }
    # The one file with two member rows is the pin; every other row is its
    # own file (S0 retired the jam nut after #2593 counted 18 files).
    shared = {("sh-vn-pivot-pin", "RodPin"), ("sh-vn-pivot-pin", "BarPin")}
    expected_files = len(drawing.BOM_COMPONENTS) - (len(shared) - 1)
    assert len(set(drawing.BOM_PART_NUMBERS.values())) == len(files) == expected_files
    assert {
        drawing.BOM_COMPONENT_IDENTITIES[key]
        for key in (drawing.explode.ROD_PIN, drawing.explode.BAR_PIN)
    } == shared
    assert (
        drawing.BOM_PART_NUMBERS[drawing.explode.ROD_PIN]
        == drawing.BOM_PART_NUMBERS[drawing.explode.BAR_PIN]
        == _config.parts("sh-vn-pivot-pin")["number"]
    )
    for stem in drawing.BOM_COMPONENTS:
        row = drawing.PART_ROWS[stem]
        skus = row.get("supplier_skus") or ()
        assert drawing.BOM_SKUS[stem] == (
            " / ".join(map(str, skus)) if skus else drawing.MADE_PART_SKU
        )
        assert drawing.BOM_DESCRIPTIONS[stem]
    assert drawing.BOM_QUANTITIES[drawing.SPRING_STEM] == drawing.CHANNELS
    # Two shafts, six pairs of end hardware and eight parts per channel: the
    # builder's 8 * CHANNELS + 14 components (#3114: no washers, no spring).
    assert sum(drawing.BOM_QUANTITIES.values()) == 2 + 6 * 2 + 8 * drawing.CHANNELS
    # The anchor is MHA-HA-00's to set: the channel sheet leaves the spring's
    # bottom loop free and cites that step.
    body = _step_body("spring-bottom-loops-left")
    assert steps.HA_ANCHORS_SET_REF in body
    assert drawing.item(drawing.explode.HOOK) in body


def test_the_sheet_text_stays_out_of_the_assembly_recipe() -> None:
    """Code review C03: the BOM descriptions, dimension callouts and which
    dimension prints as a reference are read by the drawing alone. The
    builder's recipe closure (file-granular, every local import followed)
    must not reach them, or a wording edit would force a full native rebuild
    of the channel assembly."""
    scripts = Path(drawing.__file__).resolve().parent
    sheet = str(scripts / "ch_channel_assembly_sheet.py")
    explode_spec = str(scripts / "ch_channel_explode_spec.py")
    for builder in ("build_ch_channel_assembly.py", "_ch_channel_explode.py"):
        assert sheet not in _buildgraph.module_deps_of(scripts / builder)
        assert explode_spec in _buildgraph.module_deps_of(scripts / builder)
    assert sheet in _buildgraph.module_deps_of(scripts / "draw_ch_channel_assembly.py")
    for text in ("BOM_DESCRIPTIONS", "DIMENSION_CALLOUTS", "REFERENCE_DIMENSIONS"):
        assert not hasattr(drawing.asm, text)
        assert not hasattr(drawing.explode, text)


def test_the_explode_plan_moves_every_family_and_only_them() -> None:
    explode = drawing.explode
    names = {explode.EXPLODED_VIEW_NAME}
    assert names == {drawing.EXPLODED_VIEW_NAMES[drawing.ASSEMBLY_VIEW_CONFIGURATION]}
    instances = []
    for stem, quantity in drawing.BOM_QUANTITIES.items():
        if quantity == 2:
            instances += [
                explode.Instance(f"{stem}-1", stem, -70.0),
                explode.Instance(f"{stem}-2", stem, 70.0),
            ]
        else:
            instances += [
                explode.Instance(f"{stem}-{j + 1}", stem, -70.0 + 7.0 * j)
                for j in range(quantity)
            ]
    plan = explode.plan_explode(instances)
    moved = {name for step in plan for name in step[1]}
    # r11 machinist review: one channel, the north-most (the balloons'), is
    # pulled out of the closed-up bank; every other channel stays in it.
    channel = {
        stem: max(
            (instance for instance in instances if instance.stem == stem),
            key=lambda instance: instance.z_mm,
        ).name
        for stem in explode.EXPLODED_STEMS - explode.FULLY_EXPLODED_STEMS
    }
    assert set(channel) == {explode.ARM, explode.ROD_PIN, explode.LEVER, explode.CHANNEL_SPRING}
    assert moved == {
        instance.name
        for instance in instances
        if instance.stem in explode.FULLY_EXPLODED_STEMS
    } | set(channel.values())
    (pulled,) = [
        names for step, names in plan if step.label == "north-most channel out"
    ]
    assert len(pulled) == 8 and set(channel.values()) <= set(pulled)
    assert all(name.endswith("-20") for name in pulled)
    assert drawing.exploded_offset(explode.ARM, "north-most") == (0.0, 0.0, 300.0)
    assert drawing.exploded_offset(explode.ROD, "north-most") == (0.0, -50.0, 300.0)
    assert drawing.exploded_offset(explode.ROD_PIN, "north-most") == (0.0, 0.0, 325.0)
    # Machinist review (PR #1605): withdrawn north the bar pin sat on the
    # lever's lower edge and balloon 16's arrowhead lay along the lever, so it
    # read as landing on the lever end with 17. South, along its own axis
    # (still coaxial with its bar), it stands in the open past the bar's top.
    assert drawing.exploded_offset(explode.BAR_PIN, "north-most") == (0.0, 20.0, 275.0)
    bar_offset = drawing.exploded_offset(explode.BAR, "north-most")
    pin_offset = drawing.exploded_offset(explode.BAR_PIN, "north-most")
    assert pin_offset[:2] == bar_offset[:2] and pin_offset[2] < bar_offset[2]
    assert drawing.exploded_offset(explode.BAR, "north-most") == (0.0, 20.0, 300.0)
    assert drawing.exploded_offset(explode.BAR, "north") == (0.0, 50.0, 0.0)
    spring = drawing.exploded_offset(drawing.SPRING_STEM, "north-most")
    assert spring == (0.0, 0.0, 300.0)
    assert drawing.exploded_offset(explode.ARM, "north") == (0.0, 0.0, 0.0)
    assert {explode.ARM, explode.LEVER}.isdisjoint(explode.FULLY_EXPLODED_STEMS)
    assert explode.PIVOT_SHAFT in explode.FULLY_EXPLODED_STEMS
    assert explode.FULCRUM_SHAFT in explode.EXPLODED_STEMS


def test_the_fulcrum_keepers_are_set_by_dro_checked_and_screwed() -> None:
    """#2338: each keeper comes finished to its own print (no pair ream at
    assembly, no made-to-order reamer). The pair is set on the top frame by
    DRO with the shaft through both, screwed down, the shaft checked to slide
    through both bores, and each set screw driven onto its flat later,
    unstaked (owner ruling 2026-11-20, #2397)."""
    import ch_fulcrum_keeper_spec as keeper
    from channel_frame_geom import LEVER_FULCRUM_XY
    from frame_column_stations import COLUMN_X

    assert not hasattr(steps, "KEEPERS_PAIR_REAMED_KEY")
    for retired in ("keepers-clamped", "keeper-tops-finished", "keeper-taps-made"):
        assert retired not in steps.SEQUENCE
    assert steps.LEVER_SEQUENCE[0] == "keepers-on-frame"
    order = [
        "keepers-on-frame",
        "fulcrum-shaft-through-keepers",
        steps.KEEPERS_SET_KEY,
        "keeper-faces-set",
        "rear-keeper-to-stack",
        "keepers-clamped-on-frame",
        "rear-keeper-leaf-removed",
        "keeper-feet-transferred",
        steps.KEEPERS_SCREWED_KEY,
        "keepers-held",
        "keeper-bores-checked",
        "fulcrum-shaft-withdrawn",
        "bars-straight",
        steps.BARS_PINNED_KEY,
        steps.LEVER_BANK_THREADED_KEY,
        "lever-bank-slides",
        "fulcrum-flats-aligned",
        steps.FULCRUM_SET_SCREWS_DRIVEN_KEY,
        "fulcrum-shaft-held",
        steps.SPRINGS_HOOKED_KEY,
    ]
    numbers = [steps.step_number(key) for key in order]
    assert numbers == sorted(numbers)
    front, rear = keeper.KEEPER_INNER_FACE_FROM_FRONT_SOCKET_MM
    # The pair is set at view E's lug span.
    assert keeper.KEEPER_INNER_FACE_SPAN_MM == pytest.approx(rear - front)
    assert keeper.KEEPER_INNER_FACE_SPAN_MM == pytest.approx(
        drawing.asm.LUG_INNER_FACE_Z[1] - drawing.asm.LUG_INNER_FACE_Z[0]
    )
    # The slide check carries no keeper part data (rule 24) and names the
    # shaft; the bore band covers it (ch_fulcrum_shaft_spec).
    checked = _step_body("keeper-bores-checked")
    assert drawing.item("ch-fulcrum-shaft") in checked
    assert drawing.item("ch-fulcrum-keeper") in checked
    for part_data in (".2560", "6.50", "REAM"):
        assert part_data not in checked
    import ch_fulcrum_shaft_spec as shaft

    assert shaft.ALIGNED_MIN_CLEARANCE_MM >= keeper.BORE_RUNNING_MIN_CLEARANCE_MM
    # C10 (owner ruling 2026-11-24, fit audit part 2, C10): the bare levers
    # go on with the shaft, the front lug is set by DRO at the title block's
    # band and the rear keeper is pushed up to the hubs over the leaf; the
    # levers come off again before the bars are pinned at the bench.
    lever = drawing.item(drawing.explode.LEVER)
    assert f"{drawing.COUNT} BARE {lever}" in _step_body("fulcrum-shaft-through-keepers")
    assert "RIGHT LUG INNER FACE" in _step_body("keeper-faces-set")
    pushed = _step_body("rear-keeper-to-stack")
    assert drawing.notes.setting_row("rear-keeper-to-stack") in pushed
    assert ".020" not in pushed
    # The leaf comes out once the clamp holds the keeper, before the drill
    # (#3601 independent read: no step removed it).
    assert steps.step_number("rear-keeper-leaf-removed") == (
        steps.step_number("keepers-clamped-on-frame") + 1
    )
    assert _step_body("rear-keeper-leaf-removed") == "REMOVE THE FEELER LEAF."
    # The levers come off with the shaft, in its step (#3571 P3), before the
    # bench work on them.
    assert _step_body("fulcrum-shaft-withdrawn").endswith(
        f"CATCHING EACH {lever} LEVER AS IT COMES OFF."
    )
    # The bank's end play is the leaf less or plus the push's settle; a
    # cocked hub (.012 longer, c10_close_solid.py) never closes it solid,
    # and the slide check's leaf enters at the least play.
    import ch_keeper_fitup as fitup

    assert fitup.REAR_KEEPER_LEAF_MM == pytest.approx(0.020 * 25.4)
    assert [p / 25.4 for p in fitup.END_PLAY_MM] == pytest.approx([0.019, 0.021])
    assert drawing.notes.END_PLAY_LEAF_MM <= fitup.END_PLAY_MM[0]
    deviations = {k: [d / 25.4 for d in v] for k, v in fitup.FACE_DEVIATIONS_MM.items()}
    assert deviations["front"] == pytest.approx([-0.0052, 0.0048], abs=1e-4)
    assert deviations["rear"] == pytest.approx([-0.0262, 0.0058], abs=1e-4)
    assert keeper.SET_SCREW_ENGAGEMENT_D >= keeper.SET_SCREW_MIN_ENGAGEMENT_D
    # Main's ruling: X off the receiving web, Z off the upper socket line; the
    # owner's (X1+B1, b9ae review): the settings are view F's own banded
    # dimensions, the step carries no number of them.
    assert keeper.KEEPER_FITUP_X_FROM_WEB_MM == pytest.approx(
        LEVER_FULCRUM_XY[0] - COLUMN_X
    )
    assert drawing.KEEPER_PLAN.title in _step_body(steps.KEEPERS_SET_KEY)
    asm = drawing.asm
    # Owner ruling X-A: the lug centre carries its own looser band; C10: the
    # front inner face the title block's, the rear a reference.
    assert asm.DIMENSION_TOLERANCES[asm.KEEPER_X_DIMENSION] == (
        -keeper.KEEPER_FITUP_X_BAND_MM,
        keeper.KEEPER_FITUP_X_BAND_MM,
    )
    assert asm.DIMENSION_TOLERANCES[asm.KEEPER_FRONT_Z_DIMENSION] == pytest.approx(
        (-0.127, 0.127)
    )
    assert asm.KEEPER_REAR_Z_DIMENSION not in asm.DIMENSION_TOLERANCES
    assert asm.KEEPER_REAR_Z_DIMENSION in drawing.notes.REFERENCE_DIMENSIONS
    assert asm.KEEPER_LUG_X - asm.KEEPER_SOCKET_XZ[0] == pytest.approx(
        keeper.KEEPER_FITUP_X_FROM_WEB_MM
    )
    assert [z - asm.KEEPER_SOCKET_XZ[1] for z in asm.LUG_INNER_FACE_Z] == pytest.approx(
        [front, rear]
    )
    # The bands' functions (Main's ruling, 2026-10-16): the lug centre's band
    # is charged in the transferred foot tap's wall to the rail web (#1660
    # r6), and the inner faces' fit-up is the shaft flats'
    # (ch_fulcrum_shaft_spec). At the .300 pitch the south foot stands over
    # the K5 relief machined on the front socket boss (#1038, fr_top_frame_spec
    # KEEPER_BOSS_RELIEF_*), so it clears the relief step with the front face
    # at the title block's band.
    import build_fr_top_frame as top

    south_margin, north_margin = top.KEEPER_FOOT_PRINTED_BOSS_MARGINS
    assert (south_margin, north_margin) == pytest.approx((0.635, 1.3716), abs=5e-4)
    assert top.KEEPER_TAP_DRILL_WALL_MARGIN >= top.WALL_FLOOR_MM


def test_each_rod_fork_is_pinned_to_its_arm_at_the_bench_first() -> None:
    """The rod ring is captured in its closed cam slot during the cylinder
    stack, and a pressed pin needs its far tine backed on the press, so the
    pin goes in at the bench, before that drive-train step: the rocker steps
    open with it (#3114: no hub stack to prove first). User ruling
    2026-10-09 (PR #1292 review F1): pressed, ends dressed flush. The pin is
    bought (#2339), so a pin that slides in by hand condemns the fork hole:
    the rod is replaced (rule 23)."""
    from sh_vn_pivot_pin_rod_spec import PIN_END_PROUD_MAX

    order = [
        steps.RODS_PINNED_KEY,
        "rod-pins-dressed",
        "rod-pins-held",
        "rod-arms-swing",
        *steps.ROD_PIN_REMEDY,
        "north-bracket-held",
    ]
    assert list(steps.SEQUENCE[: len(order)]) == order
    assert steps.CYLINDER_STACK_REF in _step_body(steps.RODS_PINNED_KEY)
    assert PIN_END_PROUD_MAX == 0.0  # what "FLUSH" states
    assert "FLUSH" in _step_body("rod-pins-dressed")
    for word in ("PEEN", "COUNTERSINK", "DRIVE OUT"):
        assert word not in drawing.FITUP_STEPS
    # Positive control: only the pin steps name the rod pin (the bond's swing
    # check, like rod-arms-swing, names the arm on "ITS PIN"; the replace and
    # return steps name the rod); only the two pinning steps press.
    pin_steps = {
        steps.RODS_PINNED_KEY,
        "rod-pins-dressed",
        "rod-pins-held",
        *steps.ROD_PIN_REMEDY,
    } - {"rod-pin-bond-swings", "rod-replaced", "rod-pin-return"}
    pressing = {steps.RODS_PINNED_KEY, steps.BARS_PINNED_KEY}
    pin = drawing.item(drawing.explode.ROD_PIN)
    for key in steps.SEQUENCE:
        body = _step_body(key)
        assert (re.search(rf"\b{pin}\b", body) is not None) == (key in pin_steps), key
        assert ("PRESS" in body) == (key in pressing), key
    # Owner ruling 2026-11-24, fit audit question 3: a pin that slid in by
    # hand is bonded with LOCTITE 641 per the pin bond note; the bond is
    # checked cured, one check a step (rule 22), each step after the bond
    # under "BONDED PIN:". A bond that fails its check is not bonded again:
    # the pin comes out hot and its rod or bar is replaced, as main replaced
    # it, the new part going back to the step that starts it (#3601
    # independent read: the old return looped on the bond).
    detail_sheet = drawing.SHEET_NAMES.index(drawing.DETAIL_SHEET) + 1
    for prefix, host_pin, mover, host, start, weight, faces in (
        (
            "rod",
            drawing.explode.ROD_PIN,
            "ch-rocker-arm",
            drawing.item(drawing.explode.ROD),
            steps.RODS_PINNED_KEY,
            "BY",
            "TINES",
        ),
        (
            "bar",
            drawing.explode.BAR_PIN,
            drawing.explode.BAR,
            f"{drawing.item(drawing.explode.BAR)} BAR",
            "bars-straight",
            "UNDER",
            "CHEEKS",
        ),
    ):
        assert _step_body(f"{prefix}-pin-bonded") == (
            f"IF AN {drawing.item(host_pin)} SLID IN BY HAND, BOND IT PER THE "
            f"PIN BOND NOTE (SHEET {detail_sheet})."
        )
        # One check a step (#3563), as the main flow's held and swing checks.
        assert _step_body(f"{prefix}-pin-bond-held") == (
            f"BONDED PIN: CURED, CHECK {drawing.item(host_pin)} DOES NOT SLIDE BY HAND."
        )
        assert _step_body(f"{prefix}-pin-bond-swings") == (
            f"BONDED PIN: CHECK {drawing.item(mover)} SWINGS FREE ON ITS PIN "
            f"{weight} ITS OWN WEIGHT."
        )
        assert _step_body(f"{prefix}-pin-pushed-out") == (
            f"BONDED PIN: IF {drawing.item(host_pin)} SLIDES OR "
            f"{drawing.item(mover)} BINDS, PUSH THAT PIN OUT, HEATING THE {faces} TO "
            "ABOUT 250°C."
        )
        assert _step_body(f"{prefix}-replaced") == f"PIN PUSHED OUT: REPLACE THAT {host}."
        assert _step_body(f"{prefix}-pin-return") == (
            f"PIN PUSHED OUT: RETURN TO STEP {steps.step_number(start)} WITH THE NEW {host}."
        )
        assert "REMAKE" not in drawing.FITUP_STEPS


def test_the_pin_bond_note_keeps_the_compound_off_the_running_joint() -> None:
    """Owner ruling 2026-11-24, fit audit question 3, and rule 23: the note
    names the grade, degreases, coats the trailing end only (no further in
    than half the tine or cheek, so nothing coated passes the arm or lever),
    holds the pin square by its far hole, cures before the check, and says
    how a bonded pin comes out. It prints above detail A's labels."""
    note = drawing.PIN_BOND_NOTE
    flat = " ".join(line.strip() for line in note.splitlines())
    for words in (
        "LOCTITE 641",
        "DEGREASE",
        "COAT ONE END",
        "HALF THE TINE OR CHEEK",
        "COATED END LAST",
        f"THE COMPOUND STAYS OFF THE {drawing.item('ch-rocker-arm')} OR "
        f"{drawing.item('ch-channel-lever')}",
        "CURE 24 H",
        "HOLDING THE PIN SQUARE",
        "HEATING THE TINES OR CHEEKS TO ABOUT 250°C IF IT WAS BONDED",
    ):
        assert words in flat, words
    assert flat.startswith(
        f"PIN BOND (STEPS {steps.step_number('rod-pin-bonded')} AND "
        f"{steps.step_number('bar-pin-bonded')}):"
    )
    lines = note.splitlines()
    assert max(map(len, lines)) <= drawing.STEPS_LINE_WIDTH
    x, top = drawing.PIN_BOND_NOTE_XY
    assert x == drawing.STEPS_RIGHT_X
    hub_label_top = drawing.SOUTH_END.centre[1] + 0.033
    assert top - len(lines) * NOTE_LINE_PITCH > hub_label_top
    assert x + drawing.STEPS_LINE_WIDTH * NOTE_CHAR_WIDTH < (
        drawing._TEMPLATE.width_m - drawing.BORDER
    )


def test_the_finished_shaft_is_set_by_its_tip_before_the_screws() -> None:
    """Machinist review (fleet pass): MHA-CH-05 comes finished, domed both
    ends to its overall length, so nothing is cut at assembly. Between the
    right bracket's screwing and the set screws one step sets the shaft's
    left tip DOME_HEIGHT proud of the left ear, within the layout's band."""
    import ch_pivot_shaft_spec as shaft

    assert "UNCUT" not in shaft.DRAWING_NOTES and "SUPPLY" not in shaft.DRAWING_NOTES
    assert not hasattr(shaft, "LENGTH_CALLOUT")
    for key in steps.SEQUENCE:
        body = _step_body(key)
        assert "CUT THE" not in body and "SCRIBE" not in body and "UNCUT" not in body
    key = "shaft-set"
    number = steps.step_number(key)
    assert steps.step_number("south-bracket-held") < number
    assert number < steps.step_number("set-screws-driven")
    low, high = (
        f"{(shaft.DOME_HEIGHT + sign * bank.SHAFT_TIP_SET_BAND) / 25.4:.3f}".removeprefix("0")
        for sign in (-1.0, 1.0)
    )
    assert (low, high) == (".050", ".070")
    # R5 machinist review (rule 22): the band prints on view D's native tip
    # dimension, the dome's height off the left (north) ear's outer face; the
    # step names the view and carries no number.
    asm = drawing.asm
    nominal = asm.PIVOT_CHAIN_Z[3] - asm.PIVOT_CHAIN_Z[2]
    assert nominal == pytest.approx(shaft.DOME_HEIGHT)
    assert asm.PIVOT_CHAIN_Z[2] == pytest.approx(bank.NORTH_EAR_OUTER_Z)
    lower, upper = asm.DIMENSION_TOLERANCES[asm.TIP_PROUD_DIMENSION]
    assert (lower, upper) == (-bank.SHAFT_TIP_SET_BAND, bank.SHAFT_TIP_SET_BAND)
    assert asm.TOLERANCE_PRECISION[asm.TIP_PROUD_DIMENSION] == 3
    body = _step_body(key)
    assert f"{drawing.ROCKER_BANK.title} TIP PROUD DIMENSION" in body
    assert drawing.notes.DIMENSION_CALLOUTS[asm.TIP_PROUD_DIMENSION] == "TIP PROUD"
    assert low not in body and high not in body
    # The text stands wholly right of the ear-face extension line (centred on
    # the 1.5 mm gap both lines struck its digits, rule 14), inside the
    # border, and over the ear span's callout line.
    ((x, y),) = drawing.TIP_KEEP.values()
    half = len(".060 ±.010") * NOTE_CHAR_WIDTH / 2.0
    ear_x, _ = drawing.ROCKER_BANK.sheet_xy(asm.PIVOT_CHAIN_Z[2], 0.0)
    tip_x, _ = drawing.ROCKER_BANK.sheet_xy(asm.PIVOT_CHAIN_Z[3], 0.0)
    assert tip_x < ear_x < x - half - 0.003
    assert x - half > drawing.BORDER + 0.003
    ((_, span_y),) = drawing.EAR_SPAN_KEEP.values()
    assert y > span_y + 3 * NOTE_LINE_PITCH
    # Positive control: no other step sets the tip.
    for other in steps.SEQUENCE:
        if other != key:
            assert " TIP " not in _step_body(other)


def test_the_set_screws_go_in_after_the_shaft_is_set() -> None:
    """User, 2026-10-10: one MHA-SH-VN-54 down each ear's tap onto the plain
    shaft's flat, once the shaft is set, and the shaft checked held (unstaked:
    owner ruling 2026-11-20, #2397). The end hubs are accepted clear of the
    ears before (machinist review, PR #1605)."""
    set_screw = drawing.item(drawing.explode.BRACKET_SET_SCREW)
    order = [
        "end-hubs-clear",
        "shaft-set",
        "set-screws-driven",
        "pivot-shaft-held",
        "keepers-on-frame",
    ]
    numbers = [steps.step_number(key) for key in order]
    assert numbers == sorted(numbers)
    assert "LOCTITE" not in drawing.FITUP_STEPS
    # Positive control: only these steps name the set screws.
    for other in steps.SEQUENCE:
        named = re.search(rf"\b{set_screw}\b", _step_body(other)) is not None
        assert named == (other == "set-screws-driven"), other


def test_the_set_screw_engagement_needs_no_declaration() -> None:
    """The owner's 2026-10-15 shortfall ruling (#1371) covered the R8 arch's
    1.08D; the lifted arch holds 1.5D, so the engagement is no shortfall and
    the channel contract declares no exception for it. RV-01 (the keeper
    inner faces at ±.001) retired with C10; the lug centre's ±.004 band
    (owner ruling X-A) is in the necessity register."""
    import ch_pivot_bracket_spec as bracket_spec
    from _paths import CAD_ROOT
    from machinist_exceptions import load_exceptions
    from machinist_necessity import load_necessity

    name = "ch_channel_assembly"
    assert DRAWINGS_BY_NAME[name].source_kind == "assembly"
    entries = {
        entry.id: entry
        for entry in load_exceptions(CAD_ROOT / "config", name, "assembly")
    }
    assert "RV-01" not in entries
    assert not [id_ for id_ in entries if "1667" in id_]
    assert not [e for e in entries.values() if "ENGAGEMENT" in e.where.upper()]
    register = load_necessity(CAD_ROOT / "config", name)
    assert [entry.id for entry in register] == ["N-01"]
    assert "KeeperLugX" in register[0].feature
    assert bracket_spec.SET_SCREW_ENGAGEMENT_PRINTED >= 1.5
    assert assembly_contract("ch-channel").number == "MHA-CH-00"


def test_the_set_screw_interference_allowance_is_the_ear_tap() -> None:
    """_ch_channel_interference restates the ear's apex height over the bore
    and the bore as literals (the channel's table stays off the bracket spec);
    they must be the bracket spec's, and the screws' thread its apex tap's."""
    import _ch_channel_interference as ic
    import ch_pivot_bracket_spec as bracket_spec
    import sh_vn_arbor_set_screw_spec as screw_spec

    assert ic.PIVOT_EAR_APEX_AND_BORE == (
        bracket_spec.APEX_ABOVE_BORE,
        bracket_spec.BORE_DIA,
    )
    assert screw_spec.THREAD == bracket_spec.SET_SCREW_THREAD
    pairs = ic.ALLOWED_PAIRS
    for n in (1, 2):
        pair = frozenset((f"sh-vn-arbor-set-screw-{n}", f"ch-pivot-bracket-{n}"))
        assert pairs[pair] == ic.PIVOT_EAR_SET_SCREW_LIMIT


def test_shared_arbor_set_screws_keep_their_two_ear_seats() -> None:
    stem = "sh-vn-arbor-set-screw"
    assert drawing.explode.BRACKET_SET_SCREW == stem
    assert drawing.BOM_QUANTITIES[stem] == 2
    assert drawing.BOM_PART_NUMBERS[stem] == "MHA-SH-VN-54"
    assert drawing.BOM_SKUS[stem] == "91375A106"


def test_a_feeler_leaf_passes_between_every_pair_of_bars() -> None:
    """#2341: once every foot is seated the bars hang side by side at the
    .300 pitch; the bank is accepted on the least worst-case gap (the foot,
    each bar at the bow the surface-plate check allows), floored to the .001
    leaf a bank inside its bands always passes, checked before the levers
    are proved free."""
    import sh_vn_pivot_pin_bar_spec as pin

    order = ["bar-feet-seated", "bars-gapped", "levers-swing"]
    numbers = [steps.step_number(key) for key in order]
    assert numbers == list(range(numbers[0], numbers[0] + 3))
    gaps = drawing.asm.BAR_GAP
    leaf = gaps["leaf"]
    least = min(v for k, v in gaps.items() if k not in ("leaf", "mid_span"))
    assert pin.RUNNING_FLOOR <= leaf <= least
    assert leaf == pytest.approx(0.005 * 25.4)
    body = _step_body("bars-gapped")
    cite = drawing.notes.setting_row("bars-gapped")
    assert f"THE FEELER LEAF OF {cite} PASSES" in body
    assert "EVERY ADJACENT PAIR" in body and "TOP TO BOTTOM" in body
    assert ".005" not in body
    assert _setting_table_row("bars-gapped")[4:] == (".005 MIN", "FEELER LEAF")


def test_each_bar_is_proved_straight_before_it_is_pinned() -> None:
    """#2341 (Repitch1038 2026-11-11): the bow is controlled by acceptance,
    not a frame on MHA-CH-01. Before the bars are pinned, each lies on the
    surface plate on each side face in turn and the allowed bow's leaf must
    not enter; a bar it enters is straightened by hand or exchanged. Two
    neighbours each at that bow keep the mid-span running floor."""
    asm = drawing.asm
    straight = steps.step_number("bars-straight")
    assert straight == steps.step_number("bar-notches-set") - 3
    assert straight < steps.step_number(steps.BARS_PINNED_KEY)
    assert asm.BAR_BOW_MAX_MM == pytest.approx(0.005 * 25.4)
    assert asm.BAR_GAP["mid_span_bowed"] >= asm._BAR_RUNNING_FLOOR
    body = _step_body("bars-straight")
    assert "SURFACE PLATE ON EACH SIDE FACE" in body
    cite = drawing.notes.setting_row("bars-straight")
    assert f"THE FEELER LEAF OF {cite} MUST NOT" in body
    assert _setting_table_row("bars-straight")[4:] == (".005 MAX", "FEELER LEAF")
    # Rule 22: the remedy is its own step, and so is the loop back to the check.
    assert "STRAIGHTEN" not in body
    assert steps.step_number("bar-straightened") == straight + 1
    remedy = _step_body("bar-straightened")
    assert "STRAIGHTEN BY HAND, OR EXCHANGE" in remedy
    assert "RETURN" not in remedy
    assert steps.step_number("bar-straightened-return") == straight + 2
    assert _step_body("bar-straightened-return").startswith(
        f"RETURN TO STEP {straight} WITH EACH "
    )


def _setting_table_row(key: str) -> tuple[str, ...]:
    (row,) = (
        row
        for row in drawing.SETTING_TABLE_ROWS
        if row[1] == str(steps.step_number(key))
    )
    return row


def test_the_feeler_acceptances_are_setting_table_rows_their_steps_cite() -> None:
    """R5 machinist review (rule 22): the feeler acceptances printed only in
    their steps. Each is a setting table row on sheet 6, cited by its step,
    which carries no number; the end-play leaf is the rear keeper's leaf
    less the push's settle, floored to .01 in (C10)."""

    assert drawing.notes.SETTING_TABLE_HEADER == (
        "ROW",
        "STEP",
        "SETTING",
        "MEASURE FIRST",
        "SET TO / ACCEPT",
        "CHECK WITH",
    )
    # C10's rear-keeper row comes last so rows 1-4 keep their numbers.
    keys = (
        "end-hubs-clear",
        "bars-straight",
        "bars-gapped",
        "lever-bank-slides",
        "rear-keeper-to-stack",
    )
    assert [row[0] for row in drawing.SETTING_TABLE_ROWS] == ["1", "2", "3", "4", "5"]
    assert [row[1] for row in drawing.SETTING_TABLE_ROWS] == [
        str(steps.step_number(key)) for key in keys
    ]
    for key in keys:
        assert drawing.notes.setting_row(key) in _step_body(key)
        assert "SHEET 6" in drawing.notes.setting_row(key)
    assert _setting_table_row("rear-keeper-to-stack")[2:] == (
        "LEFT LUG TO LAST HUB",
        "-",
        ".020",
        "FEELER LEAF",
    )
    play_min_in = 0.020 - 0.001
    leaf_in = math.floor(play_min_in * 100.0) / 100.0
    assert leaf_in == pytest.approx(0.01)
    assert _setting_table_row("lever-bank-slides")[2:] == (
        "LEVER END PLAY",
        "-",
        f"{leaf_in:.3f}".removeprefix("0") + " MIN",
        "FEELER LEAF",
    )
    body = _step_body("lever-bank-slides")
    assert f"{leaf_in:.3f}".removeprefix("0") not in body
    assert drawing.SETTING_TABLE_SHEET == drawing.SHEET_NAMES[5]


# The LUG CENTRE block on farm run 20261125T172832344Z's sheet 5 (two rows,
# text point y 0.140): its top 4.5 mm over the text point, its dimension
# line 5.3 mm under it, 5.5 mm between row baselines. SolidWorks centres a
# block on its text point, so each added row moves both ends half a row.
DIMENSION_TWO_ROW_TOP = 0.0045
DIMENSION_TWO_ROW_SHELF = 0.0053
DIMENSION_ROW_PITCH = 0.0055


def _plan_keep_x_block() -> tuple[int, float, float]:
    """View F's lug-centre block: its rows, its top and its dimension line
    (sheet m), from its text point and the rows its callouts print."""
    name = drawing.asm.KEEPER_X_DIMENSION
    rows = 2 + len(drawing.DIMENSION_BELOW_CALLOUTS.get(name, "").splitlines())
    y = drawing.PLAN_KEEP[name][1]
    half_rows = (rows - 2) * DIMENSION_ROW_PITCH / 2.0
    return rows, y + DIMENSION_TWO_ROW_TOP + half_rows, y - DIMENSION_TWO_ROW_SHELF - half_rows


def test_view_e_caption_stands_with_its_own_view() -> None:
    """Machinist review r1/r2 (2026-11-19): view E's caption sat nearer view
    F's LUG CENTRE callout than its own view. It now sits just under view E's
    lowest ink (the keeper foot screws' tips, y 0.172 on the farm sheet), with
    more air above view F's lug-centre block than under view E, and that
    block's top row (LUG CENTRE) starts east of the caption's end."""
    view = drawing.LEVER_BANK
    x, top = view.label_xy
    foot = top - len(view.label_text.splitlines()) * NOTE_LINE_PITCH
    view_ink_bottom = 0.172
    _, block_top, _ = _plan_keep_x_block()
    assert x == pytest.approx(view.centre[0] - 0.016)
    assert 0.002 <= view_ink_bottom - top <= 0.006
    assert foot - block_top > 2.0 * (view_ink_bottom - top)
    name = drawing.asm.KEEPER_X_DIMENSION
    caption_right = x + max(map(len, view.label_text.splitlines())) * NOTE_CHAR_WIDTH
    top_row_left = (
        drawing.PLAN_KEEP[name][0]
        - len(drawing.DIMENSION_CALLOUTS[name]) * NOTE_CHAR_WIDTH / 2.0
    )
    assert top_row_left > caption_right + 0.010


def test_the_lug_centre_states_the_rail_web_wall_once() -> None:
    """Machinist review of farm run 20261125T172832344Z, r1 and r2 (rule 20):
    the lug centre's band holds the keeper's transferred 2-56 tap's wall in
    the MHA-FR-02 rail web at .076, under rule 17's .080 target (necessity
    N-01), and neither view F nor the transfer steps stated it. It prints
    once, as a plain fact, under the lug centre's value: the number and
    wording MHA-FR-02 sheet 7 prints, read off the same accepted wall."""
    from fr_top_frame_callouts import ADDED_DRAFT_WALL_CALLOUT

    name = drawing.asm.KEEPER_X_DIMENSION
    wall = drawing.notes.KEEPER_TAP_WALL_TEXT
    assert drawing.DIMENSION_BELOW_CALLOUTS == {name: wall}
    assert wall == "RAIL WEB " + ADDED_DRAFT_WALL_CALLOUT.removeprefix("HOLDS ")
    assert "\n" not in wall
    for _column, block in drawing.FITUP_NOTES:
        assert "TAP WALL" not in block
    # The wall row is the block's widest. It starts east of the dimension's
    # extension lines (the lug and the web centre) and ends short of the
    # steps column; the third row leaves the dimension line where the
    # two-row block printed it (y 0.1347, over the boss top at 0.1345).
    x, _ = drawing.PLAN_KEEP[name]
    half_width = len(wall) * NOTE_CHAR_WIDTH / 2.0
    assert len(wall) > len(drawing.DIMENSION_CALLOUTS[name])
    extension_east = max(
        drawing._PLAN_LUG[0],
        drawing.KEEPER_PLAN.plan_xy(
            drawing.asm.KEEPER_SOCKET_XZ[0], drawing.asm.KEEPER_SOCKET_XZ[1]
        )[0],
    )
    assert x - half_width > extension_east + 0.005
    assert x + half_width < drawing.STEPS_RIGHT_X - 0.015
    rows, _, shelf = _plan_keep_x_block()
    assert rows == 3
    assert shelf == pytest.approx(0.1347, abs=0.0005)
