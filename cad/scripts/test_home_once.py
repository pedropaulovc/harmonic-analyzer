"""The mill is homed once a session, not once a setup.

Owner (Pedro) 2026-11-24: FluidNC "keeps G54 (work offsets are stored in
non-volatile settings)" through Feed Hold and Reset, and "it should not be
needed to rehome the mill $H on every setup ; only once at the beginning is
enough". FluidNC's documentation says the same (cad/process/README.md,
"Homing and work offsets", cites the pages): work offsets are stored in
non-volatile memory, a reset with the axes stopped keeps position, and
position is lost at a power cycle, a hard limit, an E-stop or a reset in
motion.

So every plan with a PM-30MV setup carries the session rule once: in its note
(two wordings are on main: the fleet's, and the slitting-saw plans' "once a
session, not at every setup"), or, for a plan that has opted in to the shop's
standing instructions (``standing = true``), on that page's mill rows
(``cad/process/shop/standing.toml``), which the sheet then does not repeat.
No operation homes out of habit or
re-touches a zero because the file was stopped. Homing stays where position
is really lost: a step may say "home ($H)" only in a sentence that names such
an event, says "if not yet homed this session", or depends on the homed
position itself (the slitting saw's touch-off station).

Every ``cad/process/*/plan.toml`` is checked, so a plan added later is held
to the same rule.
"""

from __future__ import annotations

import re
import tomllib

import pytest

import _process_plans

MILL = "pm-30mv"
SESSION_RULE = re.compile(r"Home the mill \(\$H\) once(?:, after switching it on| a session, not at every setup)")
RESET_RULE = re.compile(
    r"Feed Hold, then Reset with the axes stopped keeps position and G54|A Reset after a Feed Hold keeps G54"
)
# Events after which the controller's position is not to be trusted.
_LOST = re.compile(r"power cycle|restart|E-stop|alarm|limit switch|stall|crash", re.IGNORECASE)
# A step that depends on the homed position itself.
_NEEDS_HOME = re.compile(
    r"Only after homing \(\$H\)|if not yet homed this session|if it has not been homed this session"
    r"|a new session: home|do not home|no homing|after homing again",
    re.IGNORECASE,
)
# "the homed Z", "the homed top": a place, not an action.
_HOMED_PLACE = re.compile(r"\bthe homed (?:Z|top)\b", re.IGNORECASE)
_HOMES = re.compile(r"\$H\b|\b(?:re-?)?hom(?:e|ed|ing)\b(?! in the wrench)", re.IGNORECASE)
# The tap guide's point is "pushed home" in the wrench: not the mill's home.
_NOT_THE_MILL = re.compile(r"(?:pushed?|point|push it)(?: \w+){0,3} home|home again and to read", re.IGNORECASE)
_OLD_RULE = re.compile(
    r"a FluidNC reset loses home|at the start of (?:every|each|the) mill setup|a stop resets the controller",
    re.IGNORECASE,
)
_SENTENCE = re.compile(r"(?<=[.;])\s+(?=[A-Z(])")


def _plans() -> list[tuple[str, dict]]:
    plans = []
    for stem in _process_plans.TRAVELER_STEMS:
        plan = tomllib.loads(_process_plans.plan_path(stem).read_text(encoding="utf-8"))
        if any(setup.get("machine_ref") == MILL for setup in plan.get("setups", ())):
            plans.append((stem, plan))
    return plans


def _standing_mill() -> str:
    """The standing page's PM-30MV rows, as one text."""
    path = _process_plans.plan_path(PLANS[0][0]).parent.parent / "shop" / "standing.toml"
    rows = tomllib.loads(path.read_text(encoding="utf-8"))["notes"]["standing-mill"]["rows"]
    return " ".join(f"{label}: {text}" for label, text in rows)


def _strings(node, path=""):
    if isinstance(node, str):
        yield path, node
    elif isinstance(node, dict):
        for key, value in node.items():
            yield from _strings(value, f"{path}.{key}")
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from _strings(value, f"{path}[{index}]")


PLANS = _plans()


def test_some_plan_runs_on_the_mill() -> None:
    assert PLANS


@pytest.mark.parametrize(("stem", "plan"), PLANS, ids=[stem for stem, _plan in PLANS])
def test_the_note_carries_the_session_rule_once(stem: str, plan: dict) -> None:
    note = plan.get("note", "")
    if plan.get("standing") is True:
        page = _standing_mill()
        assert len(re.findall(r"Home the mill \(`?\$H`?\) once", page)) == 1, "the standing page: session rule once"
        assert len(re.findall(r"Reset with the axes stopped: position and G54 are kept", page)) == 1
        assert not SESSION_RULE.search(note) and not RESET_RULE.search(note), f"{stem}: repeats the standing page"
        return
    assert len(SESSION_RULE.findall(note)) == 1, f"{stem}: the note must give the session rule once"
    assert len(RESET_RULE.findall(note)) == 1, f"{stem}: the note must give the Reset rule once"


@pytest.mark.parametrize(("stem", "plan"), PLANS, ids=[stem for stem, _plan in PLANS])
def test_no_step_homes_out_of_habit(stem: str, plan: dict) -> None:
    bad = []
    for path, text in _strings(plan.get("setups", [])):
        for sentence in _SENTENCE.split(text):
            if _OLD_RULE.search(sentence):
                bad.append(f"{path}: old rule: {sentence!r}")
            if not _HOMES.search(sentence) or _NOT_THE_MILL.search(sentence):
                continue
            if _HOMED_PLACE.search(sentence) and "$H" not in sentence:
                continue
            if not (_LOST.search(sentence) or _NEEDS_HOME.search(sentence)):
                bad.append(f"{path}: homes with no lost position named: {sentence!r}")
    assert not bad, f"{stem}:\n" + "\n".join(bad)


@pytest.mark.parametrize(("stem", "plan"), PLANS, ids=[stem for stem, _plan in PLANS])
def test_the_note_keeps_no_old_rule(stem: str, plan: dict) -> None:
    assert not _OLD_RULE.search(plan.get("note", "")), stem
