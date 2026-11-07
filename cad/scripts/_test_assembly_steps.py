"""Test-only: the rule-22 step-structure lint for an assembly package's steps.

drawing-guidelines rule 22: a step does one thing and is at most six printed
lines; a check and its remedy are separate steps; directions and codes are
ones the sheet defines.  An assembly drawing's focused tests call
``step_structure_violations`` on the note blocks exactly as they print (after
the drawing's own wrapping) and assert it returns nothing.

A block is printed note text: heading and preamble lines, then steps.  A step
starts at a line whose first token is a head (``12.`` or ``12A.``; I and O are
never sub-step letters) and runs to the next head, a blank line or the end.

What "one action" means here, deterministically:

* one sentence, and no ``;`` joining two clauses;
* no imperative verb (``IMPERATIVE_VERBS``) opens a second clause: after the
  first action, a verb following ``,``, ``:``, ``AND`` or ``THEN`` is a second
  action.  The first may follow a leading condition or label (``IF IT BINDS,
  STONE ...``, ``COSINES: TURN ...``).  A verb that is also a common noun or
  adjective (``AMBIGUOUS_VERBS``: the BACK STATIONS, the CONE SET) counts only
  when an object follows it (THE, EACH, IT, a part number...).  The hole
  operations in ``COMPOUND_ACTIONS`` (``DRILL AND TAP``, ``DRILL AND REAM``)
  make one hole to its callout and count once;
* no gerund clause does a second thing (``..., SQUARING BOTH ...``);
* no absolute phrase states a second condition to establish in the action
  (``..., BANK CLOSED UP, ...``: a comma, a few words, then a participle in
  -ED or CLEAR / FREE / FLUSH ending the phrase).  An acceptance after the
  action's colon (``TAP IT IN: FLUSH BOTH SIDES``) is the action's own stop,
  as rule 23 asks, and is not read;
* no design reason rides along (``SO IT ...``, ``IT HOLDS ...``,
  ``BECAUSE``, ``WHICH``).

A check and its remedy: ``IF`` opens a step (the remedy) or not at all, and a
remedy follows a check or another remedy of the same numbered step.  A check
is a step led by a check verb, or one stating its acceptance (``ACCEPT``,
``MUST``, ``DOES NOT``, ``PASSES``...), or a declarative line with no
imperative at all (a functional check).

A press and its slip fit (rule 23: "a press whose part slides in by hand is
a slip fit; the step says what to do then"): a step led by a ``PRESS_VERBS``
verb is followed, in its own numbered step, by a check and then by a remedy
(``4. PRESS ...``, ``4A. CHECK THAT NEITHER ... PULLS OUT BY HAND``, ``4B. IF
ONE DOES, BOND IT IN ...``).

Codes and directions: a lettered step reference (``AS 8S``, ``4K-4P``,
``STEP 18D``, ``CHECKS 4-7``) names a printed head; a short code such as
``HD1`` or ``T120`` is one the caller declares defined (the BOM or a labelled
table defines it); compass words are refused; FRONT, BACK, LEFT, RIGHT and
CLOCKWISE are used only when the caller's direction key prints them.

A step the rules over-reach on is allowlisted per (namespace, head, rule) with
a written reason; an allowlist entry that no longer matches a violation is
itself reported, so the list cannot rot.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

MAX_STEP_LINES = 6

# Imperative verbs that can open an assembly instruction.
IMPERATIVE_VERBS = frozenset(
    """
    ADJUST ALIGN APPLY BACK BLOW BOND BREAK CHECK CLAMP CLEAN COAT CORRECT CURE
    CUT DEBURR DEGREASE DIAL-INDICATE DO DRILL DRIVE EASE EDGE-FIND EPOXY FACE
    FILE FILL FIND FIT GREASE GRIND HANG HOLD INSERT JOURNAL KEEP LAP LEAVE
    LIFT LIGHT-DRIVE LOAD LOCATE LOCK LOOSEN MARK MATCH-DRILL MATCH-REAM
    MEASURE MIC MOVE OIL PARK PEEN PLACE PRESS PUSH PUT REAM RECHECK RECORD
    REDO REFIT REFACE RE-FACE REMAKE REMOVE REPEAT RESET RE-SET RESTACK RETURN
    RUN SCREW SEAT SET SHIM SLIDE SLIP SNAP SPOT SQUARE STAKE STAND STONE SWING
    TAKE TAP TAPER-REAM THREAD TIGHTEN TORQUE TRIM TURN VERIFY WAX WIPE WRITE
    ZERO
    """.split()
)
# Spelt like a noun or adjective as often as a verb: a verb only with an object.
AMBIGUOUS_VERBS = frozenset(
    """
    BACK CHECK CUT DRILL FACE FILE FIT HOLD LOCK MARK OIL PARK PRESS RUN SEAT
    SET SPOT SQUARE STAND STOP TAP THREAD TURN WAX
    """.split()
)
_OBJECT = re.compile(r"(?:THE|EACH|BOTH|ITS|IT|THEM|A|AN|ALL|ONE|MHA-[\w-]+|\d[\w.-]*)\b")
# One hole made to its callout: the second verb finishes the first's hole.
COMPOUND_ACTIONS = frozenset({("DRILL", "TAP"), ("DRILL", "REAM"), ("MATCH-DRILL", "REAM")})
CHECK_VERBS = frozenset({"CHECK", "RECHECK", "VERIFY", "MEASURE", "DIAL-INDICATE"})
# A press-fit insertion: its next two steps are its hand check and remedy.
PRESS_VERBS = frozenset({"PRESS"})
_ACCEPTANCE = re.compile(r"\b(ACCEPT|MUST|SHALL|DOES NOT|PASSES|STILL)\b")
_REASON = re.compile(r"\b(SO (?:IT|THAT|THE|EACH|BOTH)|BECAUSE|SINCE|WHICH|IT HOLDS)\b")
# A head: 12. or 12A. at a line start (I and O never letter a sub-step).
_HEAD = re.compile(r"^(\s*)(\d{1,2}[A-HJ-NP-Z]?)\. ")
_JOINER = re.compile(
    r"(?:[,:]\s+(?:(?:AND|THEN)\s+)?|\b(?:AND|THEN)\s+)(?:THEN\s+)?([A-Z][A-Z-]*)(?:\s+(\S+))?"
)
_LEAD_VERB = re.compile(r"^(?:ONLY THEN\s+)?([A-Z][A-Z-]*)")
_GERUND = re.compile(r",\s+([A-Z]+)ING\b")
_SENTENCE = re.compile(r"\.\s+(?=[A-Z(])")
_ABSOLUTE = re.compile(
    r",\s+(?!IS\b|ARE\b)(?:[A-Z0-9#'/()-]+\s+){0,4}?(?:[A-Z]{2,}ED|CLEAR|FREE|FLUSH)\b"
    r"(?=\s*(?:[,.;:]|$)|\s+(?:UP|DOWN|IN|OUT|OFF|AT|ON|TO|BY|WITH|OF|HARD|BOTH|THROUGHOUT)\b)"
)
# A lettered reference: bare (4H, 8S-8U, 18C-18D) or after STEP(S)/CHECK(S),
# where a plain number also refers (STEP 19, CHECKS 4-7).  A quantity (2X), a
# tooth count (16T:64T), a decimal (0.88D) and a thread (#4-40) are not refs.
_REF = re.compile(
    r"(?:\b(?P<kind>STEPS?|CHECKS?)\s+)?(?<![\w.#/:-])(?P<first>\d{1,2}[A-HJ-NP-Z]?)"
    r"(?:-(?P<last>\d{1,2}[A-HJ-NP-Z]?))?(?![\w:]|\.\d)"
)
_CODE = re.compile(r"(?<![\w-])[A-Z]{1,3}\d+[A-Z]?(?![\w-])")
_COMPASS = re.compile(r"\b(NORTH|SOUTH|EAST|WEST)(?:ERN|WARDS?)?\b")
_DIRECTIONS = ("FRONT", "BACK", "LEFT", "RIGHT", "CLOCKWISE", "COUNTERCLOCKWISE")


@dataclass(frozen=True)
class Step:
    """One printed step: its namespace, head, printed lines and folded body."""

    namespace: str
    head: str
    lines: tuple[str, ...]

    @property
    def number(self) -> str:
        return re.match(r"\d+", self.head).group(0)

    @property
    def body(self) -> str:
        """The step's words, head removed and whitespace folded."""
        text = " ".join(" ".join(self.lines).split())
        return text.split(". ", 1)[1] if ". " in text else text


def parse_steps(namespace: str, text: str) -> list[Step]:
    """Every step of one printed block, in order."""
    found: list[Step] = []
    head: str | None = None
    lines: list[str] = []

    def close() -> None:
        if head is not None:
            found.append(Step(namespace, head, tuple(lines)))

    for line in text.splitlines():
        match = _HEAD.match(line)
        if match:
            close()
            head, lines = match.group(2), [line]
        elif not line.strip():
            close()
            head, lines = None, []
        elif head is not None:
            lines.append(line)
    close()
    return found


def _strip_lead(body: str) -> str:
    """The body after a leading condition or label (``IF ...,``,
    ``WITH ...,``, ``COSINES:``), so the first action is the first verb."""
    words = body.split()
    if words and words[0] not in IMPERATIVE_VERBS and words[0] != "ONLY":
        match = re.search(r"[,:]\s+", body)
        if match:
            return body[match.end():]
    return body


def _action_part(body: str) -> str:
    """The action itself: the stripped body up to an acceptance colon.  A
    declarative check keeps its whole statement, less a short state label
    (``PARKED, ...``), since every clause of it is something to check."""
    if not _actions(body):
        lead = re.match(r"^(?:[A-Z]+\s?){1,3}[,:]\s+", body)
        return body[lead.end():] if lead else body
    return _strip_lead(body).split(": ", 1)[0]


def _actions(body: str) -> list[str]:
    """Each imperative verb that opens a clause, in order."""
    rest = _strip_lead(body)
    verbs: list[str] = []
    lead = _LEAD_VERB.match(rest)
    start = 0
    if lead and lead.group(1) in IMPERATIVE_VERBS:
        verbs.append(lead.group(1))
        start = lead.end()
    for match in _JOINER.finditer(rest, start):
        verb, following = match.group(1), match.group(2) or ""
        if verb not in IMPERATIVE_VERBS:
            continue
        if verb in AMBIGUOUS_VERBS and not _OBJECT.match(following):
            continue
        joined_by_and = re.match(r"\s*AND\b", rest[match.start():]) is not None
        if verbs and (verbs[-1], verb) in COMPOUND_ACTIONS and joined_by_and:
            continue
        verbs.append(verb)
    return verbs


def _is_remedy(step: Step) -> bool:
    return step.body.startswith("IF ")


def _is_check(step: Step) -> bool:
    body = step.body
    if _is_remedy(step):
        return False
    lead = _LEAD_VERB.match(_strip_lead(body))
    verb = lead.group(1) if lead else ""
    return verb in CHECK_VERBS or bool(_ACCEPTANCE.search(body)) or not _actions(body)


def _structure(step: Step, previous: Step | None) -> list[tuple[str, str]]:
    body = step.body
    found: list[tuple[str, str]] = []
    if len(step.lines) > MAX_STEP_LINES:
        found.append(("lines", f"{len(step.lines)} printed lines > {MAX_STEP_LINES}"))
    if ";" in body:
        found.append(("one-action", "';' joins two clauses"))
    if _SENTENCE.search(body):
        found.append(("one-action", "a second sentence"))
    actions = _actions(body)
    if len(actions) > 1:
        found.append(("one-action", f"second action {actions[1]!r} after {actions[0]!r}"))
    for match in _GERUND.finditer(body):
        stem = match.group(1)
        if {stem, f"{stem}E", stem[:-1]} & IMPERATIVE_VERBS:
            found.append(("one-action", f"gerund clause {match.group(0)[1:].strip()!r}"))
    absolute = _ABSOLUTE.search(_action_part(body))
    if absolute:
        found.append(("one-action", f"absolute phrase {absolute.group(0)[1:].strip()!r}"))
    reason = _REASON.search(body)
    if reason:
        found.append(("reason", f"design reason {reason.group(0)!r}"))
    if re.search(r"\bIF\b", body) and not _is_remedy(step):
        found.append(("check-remedy", "'IF' inside a step: a remedy opens its own step"))
    if _is_remedy(step) and not (
        previous is not None
        and previous.number == step.number
        and (_is_check(previous) or _is_remedy(previous))
    ):
        found.append(("check-remedy", "remedy follows no check of its step"))
    return found


def _press(step: Step, following: Sequence[Step]) -> list[tuple[str, str]]:
    lead = _LEAD_VERB.match(_strip_lead(step.body))
    if lead is None or lead.group(1) not in PRESS_VERBS or _is_remedy(step):
        return []
    check, remedy = (*following[:2], None, None)[:2]
    if check is None or check.number != step.number or not _is_check(check):
        return [("press-check", "the press is not followed by a hand check of its step")]
    if remedy is None or remedy.number != step.number or not _is_remedy(remedy):
        return [("press-check", f"the {check.head} check has no slip-fit remedy after it")]
    return []


def _references(
    step: Step, heads: Mapping[str, frozenset[str]], kinds: Mapping[str, str]
) -> list[tuple[str, str]]:
    found = []
    for match in _REF.finditer(step.body):
        kind, first, last = match.group("kind"), match.group("first"), match.group("last")
        if kind and re.search(r"MHA-[\w-]+\s+$", step.body[: match.start()]):
            continue  # another package's step (MHA-FR-00 STEP 8)
        lettered = any(ref[-1].isalpha() for ref in (first, last) if ref)
        if not kind and not lettered:
            continue
        if not kind and first[-1] == "X" and not last:
            continue  # a quantity, 2X MHA-...
        namespace = kinds[kind.rstrip("S")] if kind else step.namespace
        for ref in (first, last):
            if ref is not None and ref not in heads.get(namespace, frozenset()):
                label = f"{kind} {ref}" if kind else ref
                found.append(("reference", f"{label} names no printed head"))
    return found


def _codes(step: Step, defined: Sequence[re.Pattern[str]], direction_key: str) -> list[tuple[str, str]]:
    found = []
    for code in sorted(set(_CODE.findall(step.body))):
        if not any(pattern.fullmatch(code) for pattern in defined):
            found.append(("code", f"code {code!r} is not defined on the sheet"))
    for compass in sorted(set(_COMPASS.findall(step.body))):
        found.append(("direction", f"compass word {compass!r}"))
    for word in _DIRECTIONS:
        if re.search(rf"\b{word}\b", step.body) and not re.search(rf"\b{word}\b", direction_key):
            found.append(("direction", f"{word} is not defined by the direction key"))
    return found


def step_structure_violations(
    blocks: Mapping[str, Iterable[str]],
    *,
    reference_kinds: Mapping[str, str],
    defined_codes: Iterable[str] = (),
    direction_key: str = "",
    allow: Mapping[tuple[str, str, str], str] | None = None,
) -> list[str]:
    """Every rule-22 structure violation in ``blocks``, one line each.

    ``blocks`` maps a namespace (``"STEP"``, ``"CHECK"``) to the printed note
    blocks numbered in it; ``reference_kinds`` maps the reference words
    ``STEP`` and ``CHECK`` to a namespace.  ``defined_codes`` are regular
    expressions for the short codes the sheet defines.  ``allow`` maps
    (namespace, head, rule) to the reason the step stands as printed.
    """
    allow = dict(allow or {})
    for key, reason in allow.items():
        if not reason.strip():
            raise ValueError(f"allowlist entry {key} has no reason")
    defined = [re.compile(pattern) for pattern in defined_codes]
    parsed = {name: [s for text in texts for s in parse_steps(name, text)] for name, texts in blocks.items()}
    heads = {name: frozenset(step.head for step in found) for name, found in parsed.items()}
    report, used = [], set()
    for name, found in parsed.items():
        for index, step in enumerate(found):
            previous = found[index - 1] if index else None
            for rule, detail in (
                *_structure(step, previous),
                *_press(step, found[index + 1 :]),
                *_references(step, heads, reference_kinds),
                *_codes(step, defined, direction_key),
            ):
                key = (name, step.head, rule)
                if key in allow:
                    used.add(key)
                    continue
                report.append(f"{name} {step.head} [{rule}]: {detail}: {step.body}")
    for key in sorted(set(allow) - used):
        report.append(f"allowlist entry {key} matches no violation")
    return report
