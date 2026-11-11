"""Judge two live recordings of one part build beyond request order.

The engine's ``compare_conversations`` aligns two recordings by position and
reports the first request that differs. The shadow's ``ground_truth`` is the
absence of one: request equality. Two live builds of the same source can still
differ there when SolidWorks answers differently. On 2026-11-11
``IBody2.GetFaces`` listed one body's faces in another order between two builds
in the same SolidWorks session, and ``_holes.find_planar_face`` measured them
in that order. Request equality therefore measures the seat as well as the
source. This module adds two judgements, both written by ``com_replay.py
diff``:

* :func:`truth_cause`: what preceded the first request difference. Either a
  response difference beyond noise (``response:<member>``: SolidWorks answered
  differently first) or none (``request``: the script asked something else of
  the same answers).
* :func:`outcome`: whether the two builds made the same part, on signals that
  do not depend on call order (:class:`Outcome`).

Noise, everywhere here: SolidWorks' new-document title counters (``Part11``
against ``Part12``), the masked provenance value
(``_com_conversation.PROVENANCE_MASK``), and floats within :data:`REL_TOL` of
the largest float in their value.

Not part of the engine: the engine's own file digest names the log format and
the sidecar blob prefix, so judging recordings here moves neither. Imported by
the driver only; in no recipe closure.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import math
import re
from collections import Counter
from collections.abc import Iterator, Sequence
from enum import StrEnum
from pathlib import Path
from typing import Any

import _com_conversation as conv

# Relative tolerance of a float: against the largest float of its value (one
# response, one argument list), so the noise of a near-zero component (an
# off-diagonal inertia term) is judged on the quantity's scale.
REL_TOL = 1e-9
# The counter in a new document's title (Part11, Assem3, Draw2): SolidWorks
# numbers documents per session, so the same build reads another one each run.
_TITLE_COUNTER = re.compile(r"\b(Part|Assem|Draw)\d+\b")
# The members answering mass properties: compared in order and within
# tolerance (:func:`_mass_signal`), never as exact multiset members.
_MASS_SITE = re.compile(r"^IMassProperty\d*\.|\.GetMassProperties\d*$")
# Members whose answers describe the session, not the part: the clock
# (SummaryInfo's create and save dates differ on every rebuild) and the seat's
# application preferences (one toggle differed between two request-identical
# fleet builds on 2026-11-10). Their requests stay in the request multiset.
_SESSION_SITE = re.compile(r"^IModelDoc2\.SummaryInfo$|^ISldWorks\.GetUserPreference")
_STL_SUFFIX = ".stl"
_LISTED = 10


class Outcome(StrEnum):
    """Did two builds make the same part?"""

    # Every signal is present in both logs and agrees: same mass properties
    # snapshot by snapshot, the same requests and answers in any order, the
    # same STL triangles.
    SAME = "same"
    # At least one signal disagrees beyond noise: a different part, or the
    # part reached through other requests or answers (a property value, an
    # equation, a dimension's name).
    DIFFERENT = "different"
    # Nothing disagrees, but neither log holds a mass-property snapshot, or
    # neither holds an STL export (or one cannot be read): no evidence about
    # the geometry either way.
    UNKNOWN = "unknown"


class Signal(StrEnum):
    """One signal of :func:`outcome`."""

    SAME = "same"
    DIFFERENT = "different"
    # In neither log, or its capture unreadable (in one log only is
    # DIFFERENT: the builds did not match).
    ABSENT = "absent"


def judge(
    base: conv.Conversation,
    new: conv.Conversation,
    divergence: dict[str, Any] | None,
    base_captures: Path,
    new_captures: Path,
) -> dict[str, Any]:
    """``truth_cause`` and the :func:`outcome` fields of two recordings
    whose request divergence (``compare_conversations``) is ``divergence``;
    ``*_captures`` hold the files each build had SolidWorks write."""
    a, b = conv.recipe_calls(base.calls), conv.recipe_calls(new.calls)
    return {
        "truth_cause": truth_cause(a, b, divergence),
        **outcome(base, new, base_captures, new_captures),
    }


def truth_cause(
    a: Sequence[conv.Call], b: Sequence[conv.Call], divergence: dict[str, Any] | None
) -> str | None:
    """``response:<member>`` for the nearest response before the request
    divergence that differs beyond noise (SolidWorks answered differently
    first), ``request`` when every earlier answer agrees (the script asked
    something else), ``None`` without a divergence."""
    if divergence is None:
        return None
    end = min(int(divergence["index"]), len(a), len(b))
    for index in range(end - 1, -1, -1):
        x, y = a[index], b[index]
        if not _close([x.result, x.raised, x.outs], [y.result, y.raised, y.outs]):
            return f"response:{x.site}"
    return "request"


def outcome(
    base: conv.Conversation,
    new: conv.Conversation,
    base_captures: Path,
    new_captures: Path,
) -> dict[str, Any]:
    """``outcome`` (an :class:`Outcome` value), each signal's
    :class:`Signal` (``outcome_signals``) and what differed
    (``outcome_details``). Signals, all order-independent:

    * ``mass``: every mass-property answer, matched by order per member,
      within :data:`REL_TOL`;
    * ``requests``: the multiset of recipe requests;
    * ``answers``: the multiset of (request, answer) pairs, but for mass
      properties and answers about the session (``_SESSION_SITE``);
    * ``stl``: the triangles of every STL file SolidWorks wrote
      (:func:`_triangles`; last write per path).

    Handles are erased (an object's identity number depends on call order),
    strings and floats are normalised as for noise. SLDPRT and BMP captures
    are no signal: a part file's bytes differ on every save, a screenshot's
    with the seat's window."""
    a, b = conv.recipe_calls(base.calls), conv.recipe_calls(new.calls)
    keyed_a, keyed_b = _keyed_calls(a), _keyed_calls(b)
    mass, mass_detail = _mass_signal(a, b)
    requests, request_detail = _multiset_signal(
        [(site, request) for site, request, _ in keyed_a],
        [(site, request) for site, request, _ in keyed_b],
    )
    answers, answer_detail = _multiset_signal(
        [item for item in keyed_a if item[2] is not None],
        [item for item in keyed_b if item[2] is not None],
    )
    stl_a = _stl_fingerprints(base, base_captures)
    stl_b = _stl_fingerprints(new, new_captures)
    stl = Signal.SAME if stl_a == stl_b else Signal.DIFFERENT
    if stl_a is None or stl_b is None or (not stl_a and not stl_b):
        stl = Signal.ABSENT
    signals = {"mass": mass, "requests": requests, "answers": answers, "stl": stl}
    found = Outcome.SAME
    if Signal.ABSENT in signals.values():
        found = Outcome.UNKNOWN
    if Signal.DIFFERENT in signals.values():
        found = Outcome.DIFFERENT
    return {
        "outcome": found.value,
        "outcome_signals": {name: signal.value for name, signal in signals.items()},
        "outcome_details": {
            "mass": mass_detail,
            "requests": request_detail,
            "answers": answer_detail,
            "stl": {"a": stl_a, "b": stl_b} if stl is Signal.DIFFERENT else None,
        },
    }


def label_after_feature(divergence: dict[str, Any] | None) -> None:
    """Relabel the engine's ``feature`` of a request divergence in place.

    It is the last feature named at or before the divergence, which lies after
    that feature: on 2026-11-11 the face search of the hole that followed
    PostMountHoles was reported as PostMountHoles."""
    if not divergence or not divergence.get("feature"):
        return
    divergence["feature"] = f"after {divergence['feature']}"
    divergence["feature_basis"] = (
        "the divergence lies after the last IFeature.Name put at or before "
        "its index in the base"
    )


# ---------------------------------------------------------------------------
# Signals
# ---------------------------------------------------------------------------


def _mass_signal(
    a: Sequence[conv.Call], b: Sequence[conv.Call]
) -> tuple[Signal, dict[str, Any] | None]:
    """A centre of mass is also judged on the part's length (the cube root of
    its largest volume): a symmetric part's centre is noise around zero."""
    left, right = _by_site(a), _by_site(b)
    if not left and not right:
        return Signal.ABSENT, None
    counts = {
        site: [len(left.get(site, [])), len(right.get(site, []))]
        for site in left.keys() | right.keys()
    }
    unequal = {site: pair for site, pair in counts.items() if pair[0] != pair[1]}
    if unequal:
        return Signal.DIFFERENT, {"counts": unequal}
    volumes = [
        abs(float.fromhex(call.result["f"]))
        for calls in (*left.values(), *right.values())
        for call in calls
        if call.site.endswith(".Volume") and _is_float(call.result)
    ]
    length = max(volumes, default=0.0) ** (1 / 3)
    for site in sorted(left):
        floor = length if site.endswith(".CenterOfMass") else 0.0
        for ordinal, (x, y) in enumerate(zip(left[site], right[site], strict=True)):
            if _close(
                [x.result, x.raised, x.outs], [y.result, y.raised, y.outs], floor
            ):
                continue
            return Signal.DIFFERENT, {
                "member": site,
                "ordinal": ordinal,
                "a": conv.clip(x.result),
                "b": conv.clip(y.result),
            }
    return Signal.SAME, None


def _by_site(calls: Sequence[conv.Call]) -> dict[str, list[conv.Call]]:
    found: dict[str, list[conv.Call]] = {}
    for call in calls:
        if _MASS_SITE.search(call.site):
            found.setdefault(call.site, []).append(call)
    return found


def _keyed_calls(calls: Sequence[conv.Call]) -> list[tuple[str, str, str | None]]:
    """Per call: member, request key, and answer key (``None`` for an answer
    that is no multiset signal: mass properties, the session)."""
    keyed: list[tuple[str, str, str | None]] = []
    for call in calls:
        request = json.dumps([call.op, _keyed(call.args)], separators=(",", ":"))
        answer = None
        if not (_MASS_SITE.search(call.site) or _SESSION_SITE.search(call.site)):
            answer = json.dumps(
                _keyed([call.result, call.raised, call.outs]), separators=(",", ":")
            )
        keyed.append((call.site, request, answer))
    return keyed


def _multiset_signal(
    a: Sequence[tuple[str, ...]], b: Sequence[tuple[str, ...]]
) -> tuple[Signal, dict[str, list[int]] | None]:
    """Same multiset of keys (member first), or the members (with how many
    calls are in the base only and in the new log only) whose calls differ,
    most first."""
    left, right = Counter(a), Counter(b)
    if left == right:
        return Signal.SAME, None
    members: dict[str, list[int]] = {}
    for item, count in (left - right).items():
        members.setdefault(item[0], [0, 0])[0] += count
    for item, count in (right - left).items():
        members.setdefault(item[0], [0, 0])[1] += count
    ranked = sorted(members.items(), key=lambda item: (-sum(item[1]), item[0]))
    return Signal.DIFFERENT, dict(ranked[:_LISTED])


def _stl_fingerprints(
    conversation: conv.Conversation, captures: Path
) -> dict[str, str] | None:
    """Per STL path the build had SolidWorks write, its last write's
    :func:`_triangles`; ``None`` when a capture is missing or not the bytes
    the log describes."""
    captured = conversation.trailer.get("captured", {})
    final: dict[str, dict[str, Any]] = {}
    for seq in sorted(captured, key=int):
        for rel, kept in captured[seq].items():
            if rel.lower().endswith(_STL_SUFFIX):
                final[rel] = kept
    found: dict[str, str] = {}
    for rel, kept in final.items():
        try:
            data = gzip.decompress((captures / kept["file"]).read_bytes())
        except (OSError, EOFError, gzip.BadGzipFile):
            return None
        if hashlib.sha256(data).hexdigest() != kept["sha256"]:
            return None
        found[rel] = _triangles(data)
    return found


def _triangles(data: bytes) -> str:
    """A binary STL's triangles as a multiset: each triangle's corners rotated
    to start at the least (the winding kept), facet normals, attribute bytes
    and the header dropped. Two request-identical builds of dt_crank_pinion
    (2026-11-11) wrote the same triangles in another order, corners rotated
    and normals off in the last bits. Anything else is digested whole."""
    count = int.from_bytes(data[80:84], "little") if len(data) >= 84 else -1
    if len(data) != 84 + 50 * count:
        return "bytes:" + hashlib.sha256(data).hexdigest()
    triangles = []
    for offset in range(84, len(data), 50):
        corners = [data[offset + 12 + 12 * k : offset + 24 + 12 * k] for k in range(3)]
        first = corners.index(min(corners))
        triangles.append(b"".join(corners[first:] + corners[:first]))
    digest = hashlib.sha256()
    for triangle in sorted(triangles):
        digest.update(triangle)
    return "triangles:" + digest.hexdigest()


# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------


def _text(value: str) -> str:
    for rule in conv.PROVENANCE_MASK:
        if rule.pattern.fullmatch(value):
            return f"<masked:{rule.name}>"
    return _TITLE_COUNTER.sub(r"\1#", value)


def _is_float(value: Any) -> bool:
    return isinstance(value, dict) and len(value) == 1 and "f" in value


def _floats(value: Any) -> Iterator[float]:
    if _is_float(value):
        yield float.fromhex(value["f"])
    elif isinstance(value, dict):
        for item in value.values():
            yield from _floats(item)
    elif isinstance(value, list):
        for item in value:
            yield from _floats(item)


def _scale(values: Iterator[float]) -> float:
    return max((abs(v) for v in values if math.isfinite(v)), default=0.0)


def _close(a: Any, b: Any, floor: float = 0.0) -> bool:
    """Equal but for noise: same structure and handles, normalised strings,
    floats within :data:`REL_TOL` of the largest float of either value (or
    of ``floor``, when larger)."""
    left: list[float] = []
    right: list[float] = []
    if not _same_shape(a, b, left, right):
        return False
    tolerance = REL_TOL * max(_scale(iter([*left, *right])), floor)
    return all(
        x == y or abs(x - y) <= tolerance for x, y in zip(left, right, strict=True)
    )


def _same_shape(a: Any, b: Any, left: list[float], right: list[float]) -> bool:
    if _is_float(a) and _is_float(b):
        left.append(float.fromhex(a["f"]))
        right.append(float.fromhex(b["f"]))
        return True
    if type(a) is not type(b):
        return False
    if isinstance(a, str):
        return _text(a) == _text(b)
    if isinstance(a, list):
        return len(a) == len(b) and all(
            _same_shape(x, y, left, right) for x, y in zip(a, b, strict=True)
        )
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(
            _same_shape(a[k], b[k], left, right) for k in a
        )
    return a == b


def _shape(value: Any, scale: float) -> Any:
    """``value`` with handles erased (the interface type kept), strings
    normalised and floats rounded to :data:`REL_TOL` of ``scale`` (a value
    within tolerance rounds apart only across a rounding boundary)."""
    if isinstance(value, str):
        return _text(value)
    if isinstance(value, list):
        return [_shape(item, scale) for item in value]
    if not isinstance(value, dict):
        return value
    if _is_float(value):
        number = float.fromhex(value["f"])
        quantum = REL_TOL * scale
        if quantum == 0.0 or not math.isfinite(number):
            return {"f": repr(number + 0.0)}
        return {"q": round(number / quantum)}
    if "h" in value:
        return {"h": value.get("p", "")}
    return {name: _shape(item, scale) for name, item in value.items()}


def _keyed(value: Any) -> Any:
    scale = _scale(_floats(value))
    return [f"{scale:.9g}", _shape(value, scale)]
