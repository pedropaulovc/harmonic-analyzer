"""Positive controls for the shared rule-22 step-structure lint
(_test_assembly_steps): each rule catches the step MHA-DT-00 printed at
rubric sample round 9 (R9 head 004044e), verbatim, and passes its rewrite."""

from __future__ import annotations

import pytest

from _test_assembly_steps import step_structure_violations

KINDS = {"STEP": "STEP", "CHECK": "CHECK"}


def _violations(text: str, *, namespace: str = "STEP", **kwargs) -> list[str]:
    return step_structure_violations({namespace: (text,)}, reference_kinds=KINDS, **kwargs)


def _rules(text: str, **kwargs) -> set[str]:
    return {line.split("[", 1)[1].split("]", 1)[0] for line in _violations(text, **kwargs)}


@pytest.mark.parametrize(
    ("printed", "rule"),
    [
        # R9 8K: an absolute phrase sets a second condition in the action.
        (
            "8. SLIDE THE STACK OFF.\n"
            "8K. PUT BASE MHA-FR-01, OUT OF THE FRAME, ON THE MILL TABLE, PAD\n"
            "    TRAMMED, OVERHANG SUPPORTED; CONE SET (MHA-DT-20) NOT FITTED.",
            "one-action",
        ),
        # R9 9B: "BANK CLOSED UP, MANDREL ... PROPPED" rides on the seat.
        (
            "9. LOAD THE STACK.\n"
            "9B. SEAT MHA-DT-26 ON THE FRONT MHA-DT-02, BANK CLOSED UP, MANDREL\n"
            "    BACK END PROPPED AT BORE HEIGHT ON A V-BLOCK.",
            "one-action",
        ),
        # R9 7C: a design reason after the action.
        (
            "7. BOND IT.\n"
            "7C. LEAVE IT 24 H TO CURE: IT HOLDS THE MHA-DT-34 BORE CENTRED ON THE\n"
            "    MHA-DT-08 PIVOT BORE WITHIN .004.",
            "reason",
        ),
        # R9 13: the bond and its acceptance joined by ';'.
        (
            "13. BOND MHA-DT-15 INTO MHA-DT-22 HEAD WITH LOCTITE 638; INSTALLED ROD\n"
            "    SHALL NOT TURN OR SLIDE BY HAND.",
            "one-action",
        ),
        # R9 12: two actions joined by AND.
        (
            "12. SLIDE MHA-DT-22 INTO MHA-DT-01 AND BOND WITH LOCTITE 638.",
            "one-action",
        ),
        # R9 16C: "SO IT BEARS ..." is the reason, not the instruction.
        (
            "16. DRILL IT.\n"
            "16C. SET THE MHA-DT-19 REAR END FLUSH WITH THE MHA-DT-18 REAR FACE\n"
            "     ±.003, SO IT BEARS IN BOTH MHA-DT-18 AND CLEARS MHA-DT-16.",
            "reason",
        ),
        # R9 18's last line: a gerund clause does the squaring.
        (
            "18. SET THE TIP GAP AT THE STATIONS, SQUARING BOTH MHA-DT-18 TO THE DRUM.",
            "one-action",
        ),
        # R9 check 4R: the check and its remedy in one step.
        (
            "4. LOOSEN IT.\n"
            "4R. IF T012 BINDS AFTER THE SET (TIP-TO-ROOT INTERFERENCE UP TO .010\n"
            "    REF), STONE ITS TIP UNTIL IT TURNS FREE; DO NOT RESET T120.",
            "one-action",
        ),
        # R9 check 4Q: a hold and a conditional redo.
        (
            "4. LOOSEN IT.\n"
            "4Q. LEAVE MHA-DT-02 TIGHT AFTER THIS SET; IF LOOSENED, REDO CHECKS\n"
            "    4-7.",
            "check-remedy",
        ),
        # A step past six printed lines.
        ("1. SET IT.\n" + "\n".join("   MORE TEXT" for _ in range(6)), "lines"),
        # A remedy opening a step with no check before it.
        ("5. SLIDE IT ON.\n5A. IF IT BINDS, STONE IT.", "check-remedy"),
        # A cite to a lettered head that is not printed.
        ("7. SLIDE IT ON.\n7C. RE-SET THE RIG AS STEP 18E.", "reference"),
        # A code the sheet never defines.
        ("5. SLIDE MHA-PD-09 T12 ONTO MHA-DT-11.", "code"),
        # A compass word, and a direction with no key.
        ("5. TURN IT NORTH.", "direction"),
        ("5. TURN IT CLOCKWISE.", "direction"),
    ],
)
def test_each_rule_catches_its_round_9_step(printed: str, rule: str) -> None:
    assert rule in _rules(printed, defined_codes=(r"T\d{3}",)), _violations(printed)


@pytest.mark.parametrize(
    "printed",
    [
        "8. SLIDE THE STACK OFF.\n8K. CLAMP BASE MHA-FR-01 ON THE MILL TABLE OUT OF THE FRAME.\n"
        "8L. TRAM ITS PAD.",
        "13. BOND MHA-DT-15 INTO MHA-DT-22 HEAD WITH LOCTITE 638.\n"
        "13A. AFTER THE CURE, CHECK THAT MHA-DT-15 DOES NOT TURN OR SLIDE BY HAND.",
        "4. TURN THE CRANK 4 FULL TURNS: T012 MUST RUN FREE (INTERFERENCE UP TO .010 REF).\n"
        "4A. IF IT BINDS, STONE THE T012 TIP (NEVER RESET T120) UNTIL IT TURNS FREE.",
        # One hole made to its callout counts once.
        "20. DRILL AND TAP EACH PER ITS MHA-FR-01 TRANSFER CALLOUT.",
        # An acceptance after the action's colon is its own stop.
        "6. TAP MHA-DT-34 INTO MHA-DT-08 TO THE SHOULDER: FACES FLUSH.",
        # A leading condition before the one action.
        "5. ZERO IT.\n5A. COSINES: TURN MHA-DT-01 UNTIL ALL NOTCHES POINT UP.",
        "5. TURN IT CLOCKWISE.",
    ],
)
def test_one_action_steps_pass(printed: str) -> None:
    assert (
        _violations(printed, defined_codes=(r"T\d{3}",), direction_key="CLOCKWISE IN THE FRONT VIEW")
        == []
    )


def test_a_lettered_cite_reads_its_own_namespace_and_checks_read_theirs() -> None:
    steps = "4. SLIDE IT ON.\n4K. CHECK THAT IT SWINGS FREE.\n4P. IF IT BINDS, STONE IT AS 4K."
    checks = "4. CHECK IT TURNS.\n4A. REDO CHECKS 4-4A AFTER STEP 4K."
    assert (
        step_structure_violations({"STEP": (steps,), "CHECK": (checks,)}, reference_kinds=KINDS)
        == []
    )


def test_an_allowlist_entry_needs_a_reason_and_must_match() -> None:
    printed = "5. TURN IT NORTH."
    allow = {("STEP", "5", "direction"): "the base print defines NORTH"}
    assert _violations(printed, allow=allow) == []
    with pytest.raises(ValueError, match="no reason"):
        _violations(printed, allow={("STEP", "5", "direction"): " "})
    stale = _violations("5. TURN IT.", allow=allow)
    assert stale == ["allowlist entry ('STEP', '5', 'direction') matches no violation"]
