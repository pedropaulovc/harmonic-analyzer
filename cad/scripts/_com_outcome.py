"""Judge two live recordings of one part, assembly or drawing build beyond
request order.

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
  differently first), a title counter the script echoed into the request
  (:data:`TITLE_COUNTER_CAUSE`), or none (``request``: the script asked
  something else of the same answers).
* :func:`outcome`: whether the two builds made the same part (assembly,
  drawing), on signals that do not depend on call order (:class:`Outcome`;
  each kind's in :data:`SIGNALS`).
* :func:`seat_path`: for two builds SolidWorks steered apart (a response
  cause) that made the same geometry (:data:`GEOMETRY`) but not the same
  requests, whether the requests differ only by detours of reads and
  selections (:class:`SeatPath`).
* :func:`title_echo`: for two builds whose first difference was an echoed
  title counter, whether the whole streams are the same requests but for the
  title counters the script echoed: what a replay serving the base's answers
  would have issued.

Noise, everywhere here: SolidWorks' new-document title counters (``Part11``
against ``Part12``), the masked provenance value
(``_com_conversation.PROVENANCE_MASK``), and floats within :data:`REL_TOL` of
the largest float in their value.

Not part of the engine: the engine's own file digest names the log format and
the sidecar blob prefix, so judging recordings here moves neither. Imported by
the driver only; in no recipe closure.
"""

from __future__ import annotations

import functools
import gzip
import hashlib
import itertools
import json
import math
import re
import struct
import sys
from collections import Counter
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, replace
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
# The cause of a request that differs from the base's only in title counters,
# after an answer that differed only in one: the script put the seat's
# document counter into a request (2026-11-12, ms_stick: ``IDimension.FullName``
# ``D3@MinorPattern@Part24.Part`` written into an equation). SolidWorks
# answered differently first, so it is a response cause like any other.
TITLE_COUNTER_CAUSE = "response:title_counter"
# The members answering mass properties: matched as measurements within
# tolerance (:func:`_mass_signal`), never as exact multiset members.
_MASS_SITE = re.compile(r"^IMassProperty\d*\.|\.GetMassProperties\d*$")
# The array the GetMassProperties family answers (SolidWorks API reference:
# IBody2.GetMassProperties, IModelDocExtension.GetMassProperties and
# GetMassProperties2, ISldWorks.GetMassProperties2): CenterOfMassX..Z, then
# volume, area, mass (a sheet body: area, circumference, mass; a wire body:
# length, 0, mass), then MomXX, MomYY, MomZZ, MomXY, MomZX, MomYZ, and in
# the 13-element forms the accuracy. Mixed units: each quantity gets its own
# tolerance, the centre of mass the part's length as well. Named for a solid
# body.
_MASS_ARRAY = re.compile(r"\.GetMassProperties\d*$")
_MASS_ARRAY_QUANTITIES = (
    ("CenterOfMass", slice(0, 3)),
    ("Volume", slice(3, 4)),
    ("SurfaceArea", slice(4, 5)),
    ("Mass", slice(5, 6)),
    ("MomentOfInertia", slice(6, 12)),
    ("Accuracy", slice(12, 13)),
)
# Members whose answers describe the session, not the part: the clock
# (SummaryInfo's create and save dates differ on every rebuild) and the seat's
# application preferences (one toggle differed between two request-identical
# fleet builds on 2026-11-10). Their requests stay in the request multiset.
_SESSION_SITE = re.compile(r"^IModelDoc2\.SummaryInfo$|^ISldWorks\.GetUserPreference")
_STL_SUFFIX = ".stl"
# An STL facet's plane, binned: its unit normal to 1e-4 and its offset from
# the origin to 1e-3 of the STL's unit (millimetres: the build's STL export
# preferences). Bins that touch are one plane (:func:`_planes`).
_NORMAL_STEP = 1e-4
_OFFSET_STEP = 1e-3
_TOUCHING = tuple(d for d in itertools.product((-1, 0, 1), repeat=4) if any(d))
# Two builds' STL vertices within this many float32 ulps of the STL's largest
# |coordinate| (eps: 3.05e-5 mm on the 100 mm fr_nameplate) are one point
# (:func:`_paired`). Measured basis, 2026-11-12: of 13 fresh fr_nameplate
# builds kept in the remote cache, the same model on five workers, 10 wrote
# byte-identical STLs and 3 each moved 415-458 of 25348 vertices, by at most
# 7.2e-7 mm: float64 residues of 2e-16 to 9e-16 mm where the value is exactly
# 0 (float32 keeps them there), elsewhere 1-3 float32 ulps of the coordinate.
_STL_VERTEX_ULPS = 4
# Two builds' answers to one request (member and arguments) whose floats lie
# within this many ulps of the answer's largest |float| are one answer
# (:func:`_answers_signal`). Measured basis, 2026-11-12: over 57 pairs of fleet
# recordings, 553,379 answers to requests both builds made at the same point
# were bit-identical, within REL_TOL, or a billion tolerances and more apart
# (bodies or faces listed in another order, which the multiset pairs); the one
# exception, dt_crank_drive_gear's IFace2.GetClosestPointOn onto an edge of a
# planar face, lay up to 9.5e6 ulps (6.6e-11 m, 1.9 REL_TOL) apart. 2**25 ulps
# is 3.5 times that: at most 2**-27 (7.5e-9) of the answer's largest float,
# 0.23 nm on a 34 mm coordinate.
_ANSWER_ULPS = 2**25
_NEIGHBOURS = tuple(itertools.product((-1, 0, 1), repeat=3))
_LISTED = 10
# Bound on a judge fault's message recorded in the result.
_ERROR_CHARS = 300
_PDF_SUFFIX = ".pdf"
# Sheet coordinates of a drawing PDF's ink are compared rounded to this many
# decimals of a metre (1 um: a PDF point is 353 um, written to a few decimals).
_PDF_ROUND = 6
# A drawing's PDF difference that is only a jagged crop outline drawn again
# (:func:`jagged_outline`): the judgement's ``pdf_cause``.
JAGGED_OUTLINE_CAUSE = "jagged_outline"
# Slack of a jagged view's box against the PDF's rounded ends (metres).
_BOX_SLACK = 2 * 10.0**-_PDF_ROUND
# Requests (not reads) that move or resize a drawing view after its outline
# was read: its box no longer bounds what it draws.
_VIEW_MOVES = frozenset(
    {
        "IView.Angle",
        "IView.Crop2",
        "IView.Position",
        "IView.ScaleDecimal",
        "IView.ScaleRatio",
        "IView.SetViewPosition",
        "IView.UseSheetScale",
    }
)
# The signals of :func:`outcome` per kind of build: a drawing holds no mass
# property and writes no STL; an assembly writes no STL, and the outputs Python
# writes beside it (its geometry proof, DOF manifest, BOM) are compared as
# ``sidecars``.
SIGNALS: dict[str, tuple[str, ...]] = {
    "part": ("mass", "requests", "answers", "stl"),
    "assembly": ("mass", "requests", "answers", "sidecars"),
    "drawing": ("requests", "answers", "pdf"),
}
# The signals of a kind that say its geometry is the base's: the precondition
# of :func:`seat_path`, under which an outcome ``different`` can only come from
# the requests and answers. A drawing's is its sheets' ink.
GEOMETRY: dict[str, tuple[str, ...]] = {
    "part": ("mass", "stl"),
    "assembly": ("mass", "sidecars"),
    "drawing": ("pdf",),
}
# The kinds judged as dependents of other models (assemblies and drawings):
# only telemetry, nothing of their recordings is reused, so these judgements
# name causes more finely than a part's (:func:`truth_cause`,
# :func:`_distance_only`, :func:`jagged_outline`, :func:`name_bound`).
DEPENDENT_KINDS = frozenset({"assembly", "drawing"})
# Members whose answer a dependent's ``answers`` signal compares by its first
# element only: ``IModelDoc2.ClosestDistance`` answers the distance, then a
# witness point on each entity, and between two parallel faces any pair of
# points is a witness. 2026-11-13, dt_drive_train built twice under one key:
# 6.882839 mm both times, the witnesses 17.47 mm apart along the faces.
_DISTANCE_ONLY = frozenset({"IModelDoc2.ClosestDistance"})
# The reads that identify a component in a dependent's array pre-pass
# (:func:`name_bound`): a component's instance name, a drawing component's
# name (the keys #2686's name-order sort reads).
_IDENTITY_READ = re.compile(r"\.Name2$|^IDrawingComponent\.Name$")
# ``_com._early_bound``'s QueryInterface, as the recorder logs it.
_EARLY_BOUND = ("QueryInterface", "early_bound")


class Outcome(StrEnum):
    """Did two builds make the same part?"""

    # Every signal is present in both logs and agrees: the same mass-property
    # measurements, the same requests and answers, in any order, the same STL
    # geometry.
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


class SeatPath(StrEnum):
    """Do two request streams differ only by detours (:func:`seat_path`)?"""

    # Only by blocks of reads and selections one build made and the other
    # did not (:data:`_DETOUR_READS`, :data:`_DETOUR_SELECTS`), each right
    # after the one selection whose answer steered it; every other answer the
    # same, and in both builds the selection cleared on the document the
    # block selected in, after each block, before anything but a read or a
    # selection.
    DETOUR = "detour"
    # No alignment by at most :data:`_DETOUR_BLOCKS` blocks of at most
    # :data:`_DETOUR_CALLS` calls, each resuming on :data:`_RESUME_CALLS`
    # equal requests (or the end): calls replaced, or beyond the bound.
    UNALIGNED = "unaligned"
    # A block holds a call that is no listed read or selection.
    NOT_READ = "not_read"
    # An answer to a request both builds made differs, other than a
    # selection's right before a block (:data:`_SELECTION_OWNERS`).
    ANSWER = "answer"
    # After a block, a call other than a read or a selection before
    # ``ClearSelection2`` on the document the block selected in, or that
    # document not established from the log (:func:`_selection_kept`):
    # the selection the detour made could reach a later request.
    SELECTION_KEPT = "selection_kept"


@dataclass(frozen=True)
class _Streams:
    """Both builds' recipe calls and their keys (:func:`_keyed_calls`; ``None``
    and ``keyed_error`` when keying raised), made once per judgement."""

    a: list[conv.Call]
    b: list[conv.Call]
    keyed: tuple[list[tuple[str, str, str | None]], ...] | None
    keyed_error: str | None


def _streams(base: conv.Conversation, new: conv.Conversation) -> _Streams:
    a, b = conv.recipe_calls(base.calls), conv.recipe_calls(new.calls)
    keyed, keyed_error = _attempt(lambda: (_keyed_calls(a), _keyed_calls(b)))
    return _Streams(a, b, keyed, keyed_error)


def judge(
    base: conv.Conversation,
    new: conv.Conversation,
    divergence: dict[str, Any] | None,
    base_captures: Path,
    new_captures: Path,
    *,
    kind: str = "part",
    base_sidecars: Path | None = None,
    new_sidecars: Path | None = None,
) -> dict[str, Any]:
    """``truth_cause``, the :func:`outcome` fields and ``seat_path`` of two
    recordings whose request divergence (``compare_conversations``) is
    ``divergence``; ``*_captures`` hold the files each build had SolidWorks
    write, ``kind`` names the outcome's signals (:data:`SIGNALS`),
    ``*_sidecars`` an assembly's sidecar files. ``seat_path``
    (:func:`seat_path`, ``None`` when not judged) is judged only for a
    divergence with a ``response:`` cause, a ``different`` outcome, and the
    same geometry signals of ``kind`` (:data:`GEOMETRY`).

    Never raises. A fault of this judgement costs only what it judges: the
    cause reads ``error:<type>``, a signal ``absent`` (so the outcome is at
    best ``unknown``), the seat path ``error``, each with its message in
    ``outcome_details`` (the seat path's in its own ``detail``). The diff's
    result, whose request divergence is the ground truth, is kept.
    ``judge_faults`` lists every fault (``step``: ``truth_cause``, a signal,
    ``outcome`` for all of them, ``seat_path``, ``title_echo`` or
    ``pdf_cause``; ``error``), so a signal absent because its judgement
    raised is told from one absent from both logs. ``title_echo``
    (:func:`title_echo`, ``None`` when not judged) is judged only for a
    :data:`TITLE_COUNTER_CAUSE`; ``pdf_cause`` (:data:`JAGGED_OUTLINE_CAUSE`
    when :func:`jagged_outline`, else ``None``) only for a ``different``
    ``pdf`` signal."""
    streams, streams_error = _attempt(lambda: _streams(base, new))
    inks = _read_once(base, new, base_captures, new_captures)
    cause, cause_error = (None, streams_error)
    found, error = (None, streams_error)
    if streams is not None:
        cause, cause_error = _attempt(
            lambda: truth_cause(streams.a, streams.b, divergence, kind)
        )
        found, error = _attempt(
            lambda: outcome(
                base,
                new,
                base_captures,
                new_captures,
                streams,
                kind,
                base_sidecars,
                new_sidecars,
                inks,
            )
        )
    if error is not None:
        found = {
            "outcome": Outcome.UNKNOWN.value,
            "outcome_signals": {name: Signal.ABSENT.value for name in SIGNALS[kind]},
            "outcome_details": {name: {"error": error} for name in SIGNALS[kind]},
            "judge_faults": [{"step": "outcome", "error": error}],
        }
    if cause_error is not None:
        cause = "error:" + cause_error.split(":", 1)[0]
        found["outcome_details"]["truth_cause"] = {"error": cause_error}
        found["judge_faults"].insert(0, {"step": "truth_cause", "error": cause_error})
    path = None
    signals = found["outcome_signals"]
    if (
        str(cause).startswith("response:")
        and found["outcome"] == Outcome.DIFFERENT.value
        and all(signals.get(name) == Signal.SAME.value for name in GEOMETRY[kind])
    ):
        path, path_error = _attempt(
            lambda: seat_path(streams.a, streams.b, streams.keyed)
        )
        if path_error is not None:
            path = {"path": "error", "detail": path_error}
            found["judge_faults"].append({"step": "seat_path", "error": path_error})
    echo = None
    if cause == TITLE_COUNTER_CAUSE:
        echo, echo_error = _attempt(lambda: title_echo(streams.a, streams.b))
        if echo_error is not None:
            found["judge_faults"].append({"step": "title_echo", "error": echo_error})
    ink = None
    if signals.get("pdf") == Signal.DIFFERENT.value:
        jagged, ink_error = _attempt(lambda: jagged_outline(base, new, *inks()))
        if ink_error is not None:
            found["judge_faults"].append({"step": "pdf_cause", "error": ink_error})
        if jagged:
            ink = JAGGED_OUTLINE_CAUSE
    return {
        "truth_cause": cause,
        **found,
        "seat_path": path,
        "title_echo": echo,
        "pdf_cause": ink,
    }


def truth_cause(
    a: Sequence[conv.Call],
    b: Sequence[conv.Call],
    divergence: dict[str, Any] | None,
    kind: str = "part",
) -> str | None:
    """``response:<member>`` for a response before the request divergence
    that differs beyond noise (SolidWorks answered differently first),
    :data:`TITLE_COUNTER_CAUSE` when every earlier answer agrees but for noise
    and the diverging request echoes a title counter (:func:`_echoes_title`),
    ``request`` when the script asked something else of the same answers,
    ``None`` without a divergence.

    A part names the nearest such response. An assembly or drawing
    (:data:`DEPENDENT_KINDS`) names the earliest (:func:`_earliest_response`),
    and files a request that differs from the base's only by float noise
    after an answer that did (:func:`_noise_carried`) as that answer's
    response cause."""
    if divergence is None:
        return None
    end = min(int(divergence["index"]), len(a), len(b))
    if kind not in DEPENDENT_KINDS:
        for index in range(end - 1, -1, -1):
            if not _close(_answer(a[index]), _answer(b[index])):
                return f"response:{a[index].site}"
    else:
        found = _earliest_response(a, b, end)
        if found is not None:
            return f"response:{a[found].site}"
    if _echoes_title(a, b, end):
        return TITLE_COUNTER_CAUSE
    if kind in DEPENDENT_KINDS:
        carried = _noise_carried(a, b, end, divergence)
        if carried is not None:
            return f"response:{a[carried].site}"
    return "request"


def _earliest_response(
    a: Sequence[conv.Call], b: Sequence[conv.Call], end: int
) -> int | None:
    """The index of the earliest answer before ``end`` that differs beyond
    noise and is no renumbering (:func:`_renumbered`); else of the earliest
    renumbering, which is still SolidWorks answering otherwise first; else
    ``None``. 2026-11-13, pd_transgear_knob_shaft: the nearest difference was
    a QueryInterface answering h1327 against h1319, a renumbering behind the
    first one that matters, one build listing 8 fewer visible edges."""
    newest = [0, 0]  # the largest handle number each build had used
    renumbered = None
    for index in range(end):
        x, y = _answer(a[index]), _answer(b[index])
        if not _close(x, y):
            if not _renumbered(x, y, newest):
                return index
            if renumbered is None:
                renumbered = index
        for side, (call, answer) in enumerate(((a[index], x), (b[index], y))):
            used = _handles([call.args, answer])
            newest[side] = max(newest[side], call.handle, *used)
    return renumbered


def _renumbered(x: Any, y: Any, newest: list[int]) -> bool:
    """Two answers that differ only by handles each build numbered with this
    answer: the same new objects, numbered apart (an object's number is its
    allocation order, so a build that allocated another count of objects
    earlier numbers every later one apart). A handle either build had
    already used (``newest``: the largest number each had) is another
    object than the base's, so a real difference."""
    if not _close(_erased(x), _erased(y)):
        return False
    return all(
        p == q or (p > newest[0] and q > newest[1])
        for p, q in zip(_handles(x), _handles(y), strict=True)
    )


def _noise_carried(
    a: Sequence[conv.Call],
    b: Sequence[conv.Call],
    index: int,
    divergence: dict[str, Any],
) -> int | None:
    """The index of the nearest answer before ``index`` that differed only by
    float noise, when the diverging request is the base's member on the same
    object with arguments the same but for float noise (:func:`_close`): the
    script carried SolidWorks' noise into a request. 2026-11-13,
    dt_cone_tip_gear: an ``IAnnotation.GetPosition`` 1 ulp apart, then
    ``SetPosition2`` 1 ulp apart. Otherwise ``None``: any other difference in
    the request is the script's own."""
    if divergence.get("field") != "args" or index >= min(len(a), len(b)):
        return None
    x, y = a[index], b[index]
    if (x.handle, x.op, x.site) != (y.handle, y.op, y.site) or not _close(
        x.args, y.args
    ):
        return None
    for earlier in range(index - 1, -1, -1):
        p, q = _answer(a[earlier]), _answer(b[earlier])
        if _exact(_mapped(_erased(p), _text)) != _exact(_mapped(_erased(q), _text)):
            return earlier
    return None


def name_bound(
    base: conv.Conversation, new: conv.Conversation
) -> tuple[conv.Conversation, int]:
    """``new`` with each component array SolidWorks enumerated in another
    order bound to the base's by name, and how many arrays were bound (0:
    ``new`` itself). For a dependent's split only (:data:`DEPENDENT_KINDS`).

    The recorder numbers handles in allocation order, so an array answer's
    elements are numbered in the seat's enumeration order: two seats number
    the same components apart, and a script that reads every component's name
    and then visits the components in name order (the sort #2686 brings) asks
    the same of each component under another number. An array is bound only
    when, at a request both builds issued alike (``request_field``) whose
    answers are the same handle numbers, both builds then :func:`_identify`
    every element, each by one distinct name, the same names in both. The new
    build is then read as if SolidWorks had enumerated in the base's order:
    the array's answer stays as recorded (the same numbers as the base's),
    the pre-pass is put in the base's element order, and every handle of an
    element (the element and what its pre-pass calls allocated) is renamed,
    in the pre-pass and in every later call, to the base's handle of the
    component of the same name. Anything else stays positional: components
    visited in enumeration order (as the explode authors' ``by_name`` dicts
    are, in insertion order) still differ, a request on another component
    than the base's still diverges, and a component that is not the base's
    by name binds nothing."""
    a, b = conv.recipe_calls(base.calls), conv.recipe_calls(new.calls)
    bound = 0
    index = 0
    while index < min(len(a), len(b)):
        x, y = a[index], b[index]
        if conv.request_field(x, y.handle, y.op, y.args) is not None:
            break
        found = _bind(a, b, index)
        if found is None:
            index += 1
            continue
        b, index = found
        bound += 1
    if not bound:
        return new, 0
    inert = [call for call in new.calls if call.origin is not conv.Origin.RECIPE]
    return replace(new, calls=[*b, *inert]), bound


@dataclass(frozen=True)
class _Identified:
    """An array's pre-pass (:func:`_identify`): where it ends, per pre-pass
    call its element and that element's call count before it, per element
    its calls, its name and the handles its calls allocated, in order."""

    end: int
    owners: list[tuple[int, int]]
    calls: list[list[conv.Call]]
    names: list[str]
    allocated: list[list[int]]


def _bind(
    a: list[conv.Call], b: list[conv.Call], index: int
) -> tuple[list[conv.Call], int] | None:
    """``b`` with the array answered at ``index`` bound to ``a``'s by name
    (:func:`name_bound`), and where its pre-pass ends; ``None`` when it is
    no such array, or in the same order."""
    elements = _handle_array(a[index].result)
    if elements is None or elements != _handle_array(b[index].result):
        return None
    left, right = _identify(a, index, elements), _identify(b, index, elements)
    if left is None or right is None or left.end != right.end:
        return None
    if len(set(left.names)) != len(elements) or set(left.names) != set(right.names):
        return None
    at = {name: element for element, name in enumerate(left.names)}
    order = [at[name] for name in right.names]  # new element -> base element
    if order == list(range(len(order))):
        return None
    rename: dict[int, int] = {}
    of = [0] * len(order)
    for element, mine in enumerate(order):
        of[mine] = element
        if len(right.calls[element]) != len(left.calls[mine]):
            return None
        if len(right.allocated[element]) != len(left.allocated[mine]):
            return None
        rename[elements[element]] = elements[mine]
        rename.update(zip(right.allocated[element], left.allocated[mine], strict=True))
    if set(rename) != set(rename.values()):
        return None
    prepass = [right.calls[of[element]][count] for element, count in left.owners]
    renamed = [_renamed(call, rename) for call in prepass]
    rest = [_renamed(call, rename) for call in b[left.end :]]
    return [*b[: index + 1], *renamed, *rest], left.end


def _handle_array(answer: Any) -> list[int] | None:
    """The handles of an answer that is an array of two or more of them."""
    if not isinstance(answer, dict) or not isinstance(answer.get("t"), list):
        return None
    items = answer["t"]
    if len(items) < 2 or not all(_is_handle(item) for item in items):
        return None
    return [item["h"] for item in items]


def _is_handle(value: Any) -> bool:
    return isinstance(value, dict) and isinstance(value.get("h"), int)


def _identify(
    calls: list[conv.Call], index: int, elements: list[int]
) -> _Identified | None:
    """The calls right after the array answered at ``index`` when they
    identify every element by name and do nothing else: each addressed to
    an element or a handle an earlier one of its calls allocated, each a
    pywin32 wrap (``GetTypeInfo``), a QueryInterface (``early_bound``) or a
    :data:`_IDENTITY_READ` answering a string, one per element. ``None``
    for anything else before every element was named."""
    owner = {handle: element for element, handle in enumerate(elements)}
    newest = max(elements)
    owners: list[tuple[int, int]] = []
    mine: list[list[conv.Call]] = [[] for _ in elements]
    names: list[str | None] = [None] * len(elements)
    allocated: list[list[int]] = [[] for _ in elements]
    unnamed = len(elements)
    at = index + 1
    while unnamed:
        if at >= len(calls) or calls[at].handle not in owner:
            return None
        call = calls[at]
        element = owner[call.handle]
        if _IDENTITY_READ.search(call.site) and call.kind is conv.Kind.GET:
            if names[element] is not None or not isinstance(call.result, str):
                return None
            names[element] = call.result
            unnamed -= 1
        elif call.op != "GetTypeInfo" and (call.op, call.site) != _EARLY_BOUND:
            return None
        for handle in _handles([call.result, call.outs]):
            if handle > newest:
                newest = handle
                owner[handle] = element
                allocated[element].append(handle)
        owners.append((element, len(mine[element])))
        mine[element].append(call)
        at += 1
    return _Identified(at, owners, mine, [str(name) for name in names], allocated)


def _renamed(call: conv.Call, rename: dict[int, int]) -> conv.Call:
    """``call`` with every handle in ``rename`` renamed: its object, its
    arguments and its answer."""
    return replace(
        call,
        handle=rename.get(call.handle, call.handle),
        args=_rehandled(call.args, rename),
        result=_rehandled(call.result, rename),
        outs=_rehandled(call.outs, rename),
    )


def _rehandled(value: Any, rename: dict[int, int]) -> Any:
    if isinstance(value, list):
        return [_rehandled(item, rename) for item in value]
    if not isinstance(value, dict):
        return value
    if _is_handle(value):
        return {**value, "h": rename.get(value["h"], value["h"])}
    return {name: _rehandled(item, rename) for name, item in value.items()}


def carries_title_counter(value: Any) -> bool:
    """Whether any string in ``value`` (a call's arguments or answer, as
    logged) carries a SolidWorks new-document title counter (``Part24``)."""
    if isinstance(value, str):
        return _TITLE_COUNTER.search(value) is not None
    if isinstance(value, list):
        return any(carries_title_counter(item) for item in value)
    if isinstance(value, dict):
        return any(carries_title_counter(item) for item in value.values())
    return False


def _echoes_title(a: Sequence[conv.Call], b: Sequence[conv.Call], index: int) -> bool:
    """The request at ``index`` is the base's on the same object but for the
    title counters in its arguments (provenance masked), and an earlier answer
    differed in title counters only: the script echoed the seat's document
    counter. Anything else in the request differing is the script's own."""
    if index >= min(len(a), len(b)):
        return False
    x, y = a[index], b[index]
    if (x.handle, x.op, x.site) != (y.handle, y.op, y.site):
        return False
    if not carries_title_counter(y.args):
        return False
    if _exact(_mapped(x.args, _text)) != _exact(_mapped(y.args, _text)):
        return False
    return any(_title_only(_answer(a[i]), _answer(b[i])) for i in range(index))


def _answer(call: conv.Call) -> list[Any]:
    return [call.result, call.raised, call.outs]


def _title_only(a: Any, b: Any) -> bool:
    """Two answers that differ, and only in title counters."""
    if not carries_title_counter(a):
        return False
    exact = _exact(a)
    return exact != _exact(b) and _exact(_mapped(a, _counterless)) == _exact(
        _mapped(b, _counterless)
    )


def title_echo(a: Sequence[conv.Call], b: Sequence[conv.Call]) -> bool:
    """Whether two recipe streams are the same requests but for the title
    counters the script echoed: as many calls, each the same member on the same
    object with the same arguments once title counters (and the provenance
    value) are masked, and every answer the same but for noise (title
    counters included). A replay serving the base's answers would have issued
    the base's requests exactly. A difference anywhere else, a request or an
    answer, is no echo, however late in the streams."""
    if len(a) != len(b):
        return False
    for x, y in zip(a, b, strict=True):
        if (x.handle, x.op, x.site) != (y.handle, y.op, y.site):
            return False
        if _exact(_mapped(x.args, _text)) != _exact(_mapped(y.args, _text)):
            return False
        if not _close(_answer(x), _answer(y)):
            return False
    return True


def _exact(value: Any) -> str:
    """``value`` as logged, compared exactly (``true`` is not ``1``, a float
    is its hex)."""
    return json.dumps(value, sort_keys=True, default=str)


def _mapped(value: Any, text: Callable[[str], str]) -> Any:
    """``value`` with ``text`` applied to every string, the rest as it is."""
    if isinstance(value, str):
        return text(value)
    if isinstance(value, list):
        return [_mapped(item, text) for item in value]
    if isinstance(value, dict):
        return {name: _mapped(item, text) for name, item in value.items()}
    return value


def outcome(
    base: conv.Conversation,
    new: conv.Conversation,
    base_captures: Path,
    new_captures: Path,
    streams: _Streams,
    kind: str = "part",
    base_sidecars: Path | None = None,
    new_sidecars: Path | None = None,
    inks: Callable[[], tuple[Any, Any]] | None = None,
) -> dict[str, Any]:
    """``outcome`` (an :class:`Outcome` value), each signal's
    :class:`Signal` (``outcome_signals``), what differed
    (``outcome_details``) and the signals whose judgement raised
    (``judge_faults``). The signals of ``kind`` (:data:`SIGNALS`), all
    order-independent:

    * ``mass``: every mass-property measurement, matched as a multiset
      within :data:`REL_TOL` (:func:`_mass_signal`);
    * ``requests``: the multiset of recipe requests;
    * ``answers``: the multiset of (request, answer) pairs, but for mass
      properties and answers about the session (``_SESSION_SITE``); answers
      to one request within float noise are one (:func:`_answers_signal`);
    * ``stl``: the geometry of every STL file SolidWorks wrote, vertices
      within float32 noise as one (:func:`_stl_comparison`; last write per
      path);
    * ``pdf``: the ink of every PDF SolidWorks wrote, page by page
      (:func:`_pdf_signal`; last write per path);
    * ``sidecars``: the files in ``base_sidecars`` and ``new_sidecars``, byte
      for byte (:func:`_sidecar_signal`).

    Handles are erased (an object's identity number depends on call order),
    strings and floats are normalised as for noise. SLDPRT, SLDASM, SLDDRW and
    BMP captures are no signal: a model file's bytes differ on every save, a
    screenshot's with the seat's window. A signal whose judgement raises is
    ``absent``, its message its detail. ``streams``: both builds' recipe calls
    and keys, which :func:`judge` made once for every judgement of the pair;
    ``inks``: both builds' :func:`pdf_inks`, read once when first asked for
    (by default here)."""
    if inks is None:
        inks = _read_once(base, new, base_captures, new_captures)
    a, b = streams.a, streams.b
    keyed, keyed_error = streams.keyed, streams.keyed_error
    computed: dict[str, Callable[[], tuple[Signal, Any]]] = {
        "mass": lambda: _mass_signal(a, b),
        "requests": lambda: _multiset_signal(
            [(site, request) for site, request, _ in keyed[0]],
            [(site, request) for site, request, _ in keyed[1]],
        ),
        "answers": lambda: _answers_signal(*_distance_only(keyed, a, b, kind)),
        "stl": lambda: _stl_signal(base, new, base_captures, new_captures),
        "pdf": lambda: _pdf_signal(*inks()),
        "sidecars": lambda: _sidecar_signal(base_sidecars, new_sidecars),
    }
    attempts = {name: computed[name] for name in SIGNALS[kind]}
    signals: dict[str, Signal] = {}
    details: dict[str, Any] = {}
    faults: list[dict[str, str]] = []
    for name, compute in attempts.items():
        keyed_only = keyed_error is not None and name in ("requests", "answers")
        result, error = (None, keyed_error) if keyed_only else _attempt(compute)
        if error is not None:
            result = Signal.ABSENT, {"error": error}
            faults.append({"step": name, "error": error})
        signals[name], details[name] = result
    found = Outcome.SAME
    if Signal.ABSENT in signals.values():
        found = Outcome.UNKNOWN
    if Signal.DIFFERENT in signals.values():
        found = Outcome.DIFFERENT
    return {
        "outcome": found.value,
        "outcome_signals": {name: signal.value for name, signal in signals.items()},
        "outcome_details": details,
        "judge_faults": faults,
    }


def _attempt(compute: Callable[[], Any]) -> tuple[Any, str | None]:
    """``compute()`` and ``None``, or ``None`` and the fault it raised as one
    bounded line."""
    try:
        return compute(), None
    except Exception as exc:  # noqa: BLE001 - a judge fault costs only its signal
        return None, " ".join(f"{type(exc).__name__}: {exc}".split())[:_ERROR_CHARS]


def label_feature(divergence: dict[str, Any] | None) -> None:
    """Relabel the engine's ``feature`` of a request divergence in place.

    It is the last feature named at or before the divergence. When the
    diverging base call is that naming (an ``IFeature.Name`` put) the
    divergence is AT the feature; otherwise it lies AFTER it: on 2026-11-11
    the face search of the hole that followed PostMountHoles was reported as
    PostMountHoles."""
    if not divergence or not divergence.get("feature"):
        return
    expected = divergence.get("expected") or {}
    naming = expected.get("kind") == "put" and str(expected.get("site") or "").endswith(
        "IFeature.Name"
    )
    where = "at" if naming else "after"
    divergence["feature"] = f"{where} {divergence['feature']}"
    divergence["feature_basis"] = (
        f"the divergence lies {where} the last IFeature.Name put at or before "
        "its index in the base"
    )


# ---------------------------------------------------------------------------
# Seat path: detours SolidWorks steered, and nothing else
# ---------------------------------------------------------------------------

# The SolidWorks members a detour may call, by exact site, as a method or a
# property get (never a put): each only reads the document or measures it.
# Listed one by one, from the API reference: a member not listed is no read,
# whatever its name. 2026-11-12, mg_magnifying_wheel: ``SelectByID2`` of an
# edge by a point answered False on one build of five, so the vendored
# ``_select_entity_geometric`` asked the part's type, its body's edges and
# each edge's closest point (164) and selected the nearest; the next
# measurement and every later request matched the other builds'. A face is
# found the same way (its ``_BODY_ENTITY_MEMBERS``: ``IBody2.GetFaces``, one
# ``IFace2.GetClosestPointOn`` per face), as is ``_select_faces_geometric``'s.
_DETOUR_READS = frozenset(
    {
        "IModelDoc2.GetType",
        "IModelDoc2.Extension",
        "IPartDoc.GetBodies2",
        "IBody2.GetEdges",
        "IEdge.GetClosestPointOn",
        "IBody2.GetFaces",
        "IFace2.GetClosestPointOn",
        # A measure tool (IModelDocExtension::CreateMeasure) and what it
        # measures of the selected entities (IMeasure::Calculate, properties).
        "IModelDocExtension.CreateMeasure",
        "IMeasure.Calculate",
        *(
            f"IMeasure.{name}"
            for name in (
                "Angle",
                "Area",
                "ArcLength",
                "CenterDistance",
                "ChordLength",
                "DeltaX",
                "DeltaY",
                "DeltaZ",
                "Diameter",
                "Distance",
                "IsIntersect",
                "IsParallel",
                "IsPerpendicular",
                "Length",
                "Normal",
                "NormalDistance",
                "Perimeter",
                "Projection",
                "Radius",
                "TotalArea",
                "TotalLength",
                "X",
                "Y",
                "Z",
            )
        ),
    }
)
# The members that select (by name or point, or the entity itself), and how
# each reaches the document it selects in from the handle it is called on:
# per step, the members one of whose answers that handle is (through any
# QueryInterface, :func:`_root`); the last step's call is on the document. An
# entity the vendored fallback selects is an edge or face of a body that
# IPartDoc.GetBodies2 answered. Only a selection's answer may steer a detour.
_ENTITY_OWNERS = (
    frozenset({"IBody2.GetEdges", "IBody2.GetFaces"}),
    frozenset({"IPartDoc.GetBodies2"}),
)
_SELECTION_OWNERS: dict[str, tuple[frozenset[str], ...]] = {
    "IModelDocExtension.SelectByID2": (frozenset({"IModelDoc2.Extension"}),),
    "IEntity.Select2": _ENTITY_OWNERS,
    "IEntity.Select4": _ENTITY_OWNERS,
}
# Selections, and the clearing of a document's selection list: the selection
# list is all they change.
_CLEAR_SELECTION = "IModelDoc2.ClearSelection2"
_DETOUR_SELECTS = frozenset({*_SELECTION_OWNERS, _CLEAR_SELECTION})
# pywin32's own protocol on an object SolidWorks already returned (interface
# and name lookups, type information, identity): no SolidWorks member runs.
_PROTOCOL_OPS = frozenset(
    {
        "QueryInterface",
        "GetIDsOfNames",
        "GetTypeInfo",
        "GetTypeInfoCount",
        "GetTypeAttr",
        "__eq__",
        "__ne__",
        "__hash__",
    }
)
# A measurement's own option, put on the IMeasure tool CreateMeasure returned
# (IMeasure::ArcOption, swMeasureArcCircleOption_e): no document state. Allowed
# between a block and the ClearSelection2 after it, never in a block.
_MEASURE_OPTIONS = frozenset({"IMeasure.ArcOption"})
# The alignment's bound (:func:`_detours`): at most this many blocks of at most
# this many calls, each resuming on this many equal requests (or both ends).
# The work is at most blocks x calls x 2 comparisons of that many requests,
# plus one pass over both streams; beyond it the streams are ``unaligned``.
_DETOUR_BLOCKS = 16
_DETOUR_CALLS = 4096
_RESUME_CALLS = 8


def seat_path(
    a: Sequence[conv.Call],
    b: Sequence[conv.Call],
    keyed: tuple[list[tuple[str, str, str | None]], ...],
) -> dict[str, Any]:
    """Whether two recipe request streams (keyed by :func:`_keyed_calls`, in
    ``keyed``) differ only by detours (:class:`SeatPath`): ``path``, and
    ``detail`` (what failed) or, for ``detour``, the blocks (``base`` and
    ``new`` call ranges, ``steered_by``: the selection whose answer before the
    block differs; the first :data:`_LISTED`) and their ``count``.

    Requests are aligned as :func:`_answers_signal` keys them (member and
    arguments, handles erased, floats rounded to :data:`REL_TOL`) by
    :func:`_detours`, then checked in order: every call in a block is pywin32
    protocol or a listed read or selection (:func:`_detour_call`); every
    answer to a request both builds made is the same under the answers
    signal's rules (equal keys, or :func:`_answer_close`; mass properties and
    the session are judged elsewhere), but a selection's right before a block
    (:func:`_selects`); after each block, in both builds, the selection
    before it and those in it selected in one document the log establishes,
    and ``ClearSelection2`` on that document comes before any call but a
    detour call or a measure option (:func:`_selection_kept`)."""
    keyed_a, keyed_b = keyed
    aligned = _detours(
        [f"{site}\n{request}" for site, request, _ in keyed_a],
        [f"{site}\n{request}" for site, request, _ in keyed_b],
    )
    if aligned is None:
        return {
            "path": SeatPath.UNALIGNED.value,
            "detail": f"no alignment by at most {_DETOUR_BLOCKS} blocks of at "
            f"most {_DETOUR_CALLS} calls",
        }
    runs, blocks = aligned
    for i, i_end, j, j_end in blocks:
        for call in (*a[i:i_end], *b[j:j_end]):
            if not _detour_call(call):
                return {
                    "path": SeatPath.NOT_READ.value,
                    "detail": f"{call.site} ({call.kind.value}) in the block at "
                    f"base {i} new {j}",
                }
    steered = {
        (i - 1, j - 1)
        for i, _, j, _ in blocks
        if i and j and _selects(a[i - 1]) and _selects(b[j - 1])
    }
    for i, j, length in runs:
        for x, y in zip(range(i, i + length), range(j, j + length), strict=True):
            left, right = keyed_a[x][2], keyed_b[y][2]
            if (x, y) in steered or left is None or right is None or left == right:
                continue
            if not _answer_close(_erased(_answer(a[x])), _erased(_answer(b[y]))):
                return {
                    "path": SeatPath.ANSWER.value,
                    "detail": f"{a[x].site} answered otherwise at base {x} new {y}",
                }
    origins = (_origins(a), _origins(b))
    for i, i_end, j, j_end in blocks:
        for side, calls, owners, start, end in (
            ("base", a, origins[0], i, i_end),
            ("new", b, origins[1], j, j_end),
        ):
            why = _selection_kept(calls, owners, start, end)
            if why is not None:
                return {
                    "path": SeatPath.SELECTION_KEPT.value,
                    "detail": f"{side}: {why}, after the block at base {i} new {j}",
                }
    return {
        "path": SeatPath.DETOUR.value,
        "count": len(blocks),
        "blocks": [
            {
                "base": [i, i_end],
                "new": [j, j_end],
                "steered_by": a[i - 1].site if (i - 1, j - 1) in steered else None,
            }
            for i, i_end, j, j_end in blocks[:_LISTED]
        ],
    }


def _detours(
    a: Sequence[str], b: Sequence[str]
) -> tuple[list[tuple[int, int, int]], list[tuple[int, int, int, int]]] | None:
    """Align request streams ``a`` and ``b`` as matched runs
    (``(i, j, length)``) and blocks only one stream holds (``(i, i_end, j,
    j_end)``, one range empty), or ``None`` beyond the bound. Greedy: at a
    difference, the shortest block (at most :data:`_DETOUR_CALLS` calls) in
    either stream after which the streams resume on :data:`_RESUME_CALLS`
    equal requests, or end together. Any alignment found is a witness: what
    :func:`seat_path` then requires of it holds of the streams."""
    runs: list[tuple[int, int, int]] = []
    blocks: list[tuple[int, int, int, int]] = []
    i = j = 0
    while True:
        start_i, start_j = i, j
        while i < len(a) and j < len(b) and a[i] == b[j]:
            i += 1
            j += 1
        if i > start_i:
            runs.append((start_i, start_j, i - start_i))
        if i == len(a) and j == len(b):
            return runs, blocks
        if len(blocks) == _DETOUR_BLOCKS:
            return None
        for k in range(1, _DETOUR_CALLS + 1):
            if _resumes(a, i, b, j + k):
                blocks.append((i, i, j, j + k))
                j += k
                break
            if _resumes(b, j, a, i + k):
                blocks.append((i, i + k, j, j))
                i += k
                break
        else:
            return None


def _resumes(x: Sequence[str], p: int, y: Sequence[str], q: int) -> bool:
    """``x`` from ``p`` and ``y`` from ``q`` agree on the next
    :data:`_RESUME_CALLS` requests, or on all that are left of both."""
    if q > len(y):
        return False
    count = min(_RESUME_CALLS, len(x) - p, len(y) - q)
    if count < _RESUME_CALLS and len(x) - p != len(y) - q:
        return False
    return x[p : p + count] == y[q : q + count]


def _detour_call(call: conv.Call) -> bool:
    """A call a detour may make: pywin32 protocol, or a listed read or
    selection called as a method or read as a property (never put)."""
    if call.op in _PROTOCOL_OPS:
        return True
    if call.kind not in (conv.Kind.CALL, conv.Kind.GET):
        return False
    return call.site in _DETOUR_READS or call.site in _DETOUR_SELECTS


def _selects(call: conv.Call) -> bool:
    """A selection (:data:`_SELECTION_OWNERS`) called as a method: the only
    call whose differing answer may steer a detour, since all it changes is
    the selection list, which must then be cleared."""
    return call.site in _SELECTION_OWNERS and call.kind is conv.Kind.CALL


def _selection_kept(
    calls: Sequence[conv.Call],
    origins: dict[int, conv.Call],
    start: int,
    end: int,
) -> str | None:
    """Why the selection made right before a block (``calls[start - 1]``) or
    in it (``calls[start:end]``) could reach a later request, or ``None``.
    Those selections must select in one document the log establishes
    (:func:`_document`), and ``ClearSelection2`` on it must come after the
    block before any call but a detour call or a measure option
    (:func:`_uncleared`)."""
    selections = [call for call in calls[max(start - 1, 0) : end] if _selects(call)]
    documents = {_document(origins, call) for call in selections}
    if not documents:
        return "no selection"
    if None in documents:
        return "a selection's document is not established"
    if len(documents) > 1:
        return f"selections in {len(documents)} documents"
    member = _uncleared(calls, end, documents.pop(), origins)
    if member is None:
        return None
    return f"{member} before {_CLEAR_SELECTION} on the document selected in"


def _document(origins: dict[int, conv.Call], call: conv.Call) -> int | None:
    """The handle (:func:`_root`) of the document selection ``call`` selects
    in, reached from the handle it is called on by :data:`_SELECTION_OWNERS`;
    ``None`` when the log does not establish it."""
    handle = _root(origins, call.handle)
    for members in _SELECTION_OWNERS.get(call.site, (frozenset(),)):
        source = origins.get(handle)
        if source is None or source.site not in members:
            return None
        handle = _root(origins, source.handle)
    return handle


def _origins(calls: Sequence[conv.Call]) -> dict[int, conv.Call]:
    """Per handle, the call whose answer (result or out parameters) first
    held it: the recorder numbers each object it wraps anew."""
    found: dict[int, conv.Call] = {}
    for call in calls:
        for handle in _handles([call.result, call.outs]):
            found.setdefault(handle, call)
    return found


def _handles(value: Any) -> Iterator[int]:
    if isinstance(value, list):
        for item in value:
            yield from _handles(item)
    elif isinstance(value, dict):
        if isinstance(value.get("h"), int):
            yield value["h"]
            return
        for item in value.values():
            yield from _handles(item)


def _root(origins: dict[int, conv.Call], handle: int) -> int:
    """The handle a chain of QueryInterface answers ending at ``handle``
    started from: one COM object, whichever interface the script holds it
    by. Another route to the same document (a second ``ActiveDoc``) is
    another root: the safe direction."""
    seen = set()
    while handle not in seen:
        seen.add(handle)
        source = origins.get(handle)
        if source is None or source.op != "QueryInterface":
            return handle
        handle = source.handle
    return handle


def _uncleared(
    calls: Sequence[conv.Call],
    start: int,
    document: int,
    origins: dict[int, conv.Call],
) -> str | None:
    """The first member from ``start`` that is neither a detour call nor a
    measure option put, if it comes before ``ClearSelection2`` on
    ``document`` (a clear on another document clears nothing of it);
    ``None`` when that selection is cleared first, or nothing else
    follows."""
    for call in calls[start:]:
        if (
            call.site == _CLEAR_SELECTION
            and call.kind is conv.Kind.CALL
            and _root(origins, call.handle) == document
        ):
            return None
        if _detour_call(call):
            continue
        if call.site in _MEASURE_OPTIONS and call.kind is conv.Kind.PUT:
            continue
        return call.site
    return None


# ---------------------------------------------------------------------------
# Signals
# ---------------------------------------------------------------------------


def _mass_signal(
    a: Sequence[conv.Call], b: Sequence[conv.Call]
) -> tuple[Signal, dict[str, Any] | None]:
    """The two builds' mass-property measurements (:func:`_measurements`) as
    a multiset: per kind, every measurement paired with one of the other
    build's within tolerance (:func:`_mass_close`; a centre of mass is also
    judged on the part's length, the cube root of its largest volume, since a
    symmetric part's centre is noise around zero). Order-free: on 2026-11-11
    sh_vn_chain_link measured one configuration's four bodies in another
    order, the same bodies as the base's (``IBody2.GetBodies2`` listed them
    otherwise)."""
    left, right = _measurements(a), _measurements(b)
    if not left and not right:
        return Signal.ABSENT, None
    counts = {
        kind: [len(left.get(kind, [])), len(right.get(kind, []))]
        for kind in left.keys() | right.keys()
    }
    unequal = {kind: pair for kind, pair in counts.items() if pair[0] != pair[1]}
    if unequal:
        return Signal.DIFFERENT, {"counts": unequal}
    length = _part_length(
        [
            call
            for group in (*left.values(), *right.values())
            for m in group
            for call in m
        ]
    )

    def close(x: tuple[conv.Call, ...], y: tuple[conv.Call, ...]) -> bool:
        return all(_mass_close(c, d, length) for c, d in zip(x, y, strict=True))

    for kind in sorted(left):
        unpaired = _unassigned(left[kind], right[kind], close)
        if unpaired is None:
            continue
        stranded, candidates = unpaired
        x = left[kind][stranded]
        detail: dict[str, Any] = {
            "member": kind,
            "ordinal": stranded,
            "a": conv.clip([c.result for c in x]),
        }
        if not candidates:
            return Signal.DIFFERENT, detail
        # The other build's unpaired measurement nearest to it, and the
        # quantity farthest beyond tolerance against that one.
        (off, member, quantity), j = min(
            ((_farthest(x, right[kind][j], length), j) for j in candidates),
            key=lambda item: item[0][0],
        )
        return Signal.DIFFERENT, {
            **detail,
            "member": member,
            "quantity": quantity,
            "tolerances": f"{off:.3g}",
            "nearest": j,
            "b": conv.clip([c.result for c in right[kind][j]]),
        }
    return Signal.SAME, None


def _measurements(calls: Sequence[conv.Call]) -> dict[str, list[tuple[conv.Call, ...]]]:
    """The mass-property measurements of a build by kind, in call order. One
    GetMassProperties-family answer is one measurement (one body's quantities
    in one array). Every answer read from one IMassProperty object is one,
    in the order read, so a volume stays paired with its own centre and
    inertia. The kind is the members read, in that order."""
    objects: dict[int, list[conv.Call]] = {}
    found: list[list[conv.Call]] = []
    for call in calls:
        if not _MASS_SITE.search(call.site):
            continue
        if _MASS_ARRAY.search(call.site):
            found.append([call])
            continue
        if call.handle not in objects:
            objects[call.handle] = []
            found.append(objects[call.handle])
        objects[call.handle].append(call)
    kinds: dict[str, list[tuple[conv.Call, ...]]] = {}
    for measurement in found:
        kind = ",".join(call.site for call in measurement)
        kinds.setdefault(kind, []).append(tuple(measurement))
    return kinds


def _unassigned(
    left: Sequence[Any], right: Sequence[Any], close: Callable[[Any, Any], bool]
) -> tuple[int, list[int]] | None:
    """The first of ``left`` that could not be added to the assignment, with
    the indices of ``right`` the assignment left unpaired then; ``None`` when
    every one of ``left`` is paired (equal lengths).

    Closeness within a tolerance is not transitive: one measurement can be
    close to two of the other build's, so pairing greedily, or in the order of
    a sort key, can strand one that another assignment pairs. Kuhn's
    augmenting paths find a pairing of every one whenever one exists. The
    pairing in call order is tried first, and is the answer whenever the
    builds measured in the same order."""
    if all(close(x, y) for x, y in zip(left, right, strict=True)):
        return None
    near: dict[int, list[int]] = {}
    owner = [-1] * len(right)
    taken = [-1] * len(left)
    for start in range(len(left)):
        reached: dict[int, int] = {}
        stack, free = [start], -1
        while stack and free < 0:
            i = stack.pop()
            if i not in near:
                near[i] = [j for j, y in enumerate(right) if close(left[i], y)]
            for j in near[i]:
                if j in reached:
                    continue
                reached[j] = i
                if owner[j] < 0:
                    free = j
                    break
                stack.append(owner[j])
        if free < 0:
            return start, [j for j, i in enumerate(owner) if i < 0]
        j = free
        while j >= 0:
            i = reached[j]
            previous = taken[i]
            owner[j], taken[i] = i, j
            j = previous
    return None


def _part_length(calls: Sequence[conv.Call]) -> float:
    """The cube root of the largest volume any mass answer reports."""
    volumes = []
    for call in calls:
        if call.site.endswith(".Volume") and _is_float(call.result):
            volumes.append(abs(float.fromhex(call.result["f"])))
        items = _mass_array(call)
        if items is not None:
            volumes.append(abs(float.fromhex(items[3]["f"])))
    return max(volumes, default=0.0) ** (1 / 3)


def _mass_array(call: conv.Call) -> list[Any] | None:
    """The answer of a GetMassProperties-family call in the documented
    layout (12 or 13 floats), else ``None``."""
    if not _MASS_ARRAY.search(call.site) or not isinstance(call.result, dict):
        return None
    items = call.result.get("t") or call.result.get("l")
    if not isinstance(items, list) or len(items) not in (12, 13):
        return None
    return items if all(_is_float(item) for item in items) else None


def _mass_close(x: conv.Call, y: conv.Call, length: float) -> bool:
    """Two answers of one mass member within tolerance, quantity by quantity
    (:func:`_quantities`)."""
    return all(_close(p, q, floor) for _, p, q, floor in _quantities(x, y, length))


def _farthest(
    x: tuple[conv.Call, ...], y: tuple[conv.Call, ...], length: float
) -> tuple[float, str, str]:
    """How far measurement ``y`` is from ``x``, in tolerances (above 1: beyond
    it): the farthest quantity's distance, member and name."""
    found = (0.0, x[0].site, "")
    for c, d in zip(x, y, strict=True):
        for name, p, q, floor in _quantities(c, d, length):
            distance = _distance(p, q, floor)
            if distance > found[0]:
                found = (distance, c.site, name)
    return found


def _quantities(
    x: conv.Call, y: conv.Call, length: float
) -> Iterator[tuple[str, Any, Any, float]]:
    """What two answers of one mass member are compared on: name, both
    values, and the floor of the tolerance. A documented array quantity by
    quantity, the centre of mass on the part's length too; any other answer
    whole, a ``CenterOfMass`` on the part's length too."""
    left, right = _mass_array(x), _mass_array(y)
    if left is None or right is None or len(left) != len(right):
        floor = length if x.site.endswith(".CenterOfMass") else 0.0
        yield (
            x.site.rpartition(".")[2],
            [x.result, x.raised, x.outs],
            [y.result, y.raised, y.outs],
            floor,
        )
        return
    yield "raised", [x.raised, x.outs], [y.raised, y.outs], 0.0
    for name, part in _MASS_ARRAY_QUANTITIES:
        yield name, left[part], right[part], length if part.start == 0 else 0.0


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


def _distance_only(
    keyed: tuple[list[tuple[str, str, str | None]], ...],
    a: Sequence[conv.Call],
    b: Sequence[conv.Call],
    kind: str,
) -> tuple[Sequence[Any], ...]:
    """:func:`_answers_signal`'s arguments: for a dependent
    (:data:`DEPENDENT_KINDS`), each :data:`_DISTANCE_ONLY` answer cut to its
    first element, the distance, and keyed again; a part's as recorded."""
    if kind not in DEPENDENT_KINDS:
        return keyed[0], keyed[1], a, b
    (keys_a, cut_a), (keys_b, cut_b) = _cut(keyed[0], a), _cut(keyed[1], b)
    return keys_a, keys_b, cut_a, cut_b


def _cut(
    keyed: list[tuple[str, str, str | None]], calls: Sequence[conv.Call]
) -> tuple[list[tuple[str, str, str | None]], list[conv.Call]]:
    kept_keys, kept_calls = list(keyed), list(calls)
    for index, call in enumerate(calls):
        answer = call.result
        if call.site not in _DISTANCE_ONLY or keyed[index][2] is None:
            continue
        if not isinstance(answer, dict) or not isinstance(answer.get("t"), list):
            continue
        if not answer["t"]:
            continue
        call = replace(call, result=answer["t"][0])
        kept_calls[index] = call
        key = json.dumps(_keyed(_answer(call)), separators=(",", ":"))
        kept_keys[index] = (call.site, keyed[index][1], key)
    return kept_keys, kept_calls


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


def _answers_signal(
    a: Sequence[tuple[str, str, str | None]],
    b: Sequence[tuple[str, str, str | None]],
    calls_a: Sequence[conv.Call],
    calls_b: Sequence[conv.Call],
) -> tuple[Signal, dict[str, Any] | None]:
    """The multiset of (request, answer) keys (:func:`_keyed_calls`, per call
    of ``calls_a`` and ``calls_b``; no answer key: no signal). Keys that
    differ are not yet another answer: the keys both builds have cancel
    (their multiset intersection), and per request (member and arguments)
    the answers left over in one build must pair one-to-one with the other's
    left over to that request (:func:`_unassigned`) within float noise
    (:func:`_answer_close`). A request with more answers left over in one
    build (answered more often), or an answer left unpaired, is different
    (:func:`_multiset_signal`'s detail). Pairing only the leftovers keeps
    the work to the answers that differ, whatever the request's count; a
    leftover that only some exactly matched answer could have absorbed stays
    unpaired (different: the safe direction). Same after pairing: per member,
    how many answers were paired."""
    left = [(k, c) for k, c in zip(a, calls_a, strict=True) if k[2] is not None]
    right = [(k, c) for k, c in zip(b, calls_b, strict=True) if k[2] is not None]
    signal, detail = _multiset_signal([k for k, _ in left], [k for k, _ in right])
    if signal is Signal.SAME:
        return signal, detail
    keys_a, keys_b = Counter(k for k, _ in left), Counter(k for k, _ in right)
    leftover = (keys_a - keys_b, keys_b - keys_a)
    answers: dict[tuple[str, ...], tuple[list[Any], list[Any]]] = {
        key[:2]: ([], []) for over in leftover for key in over
    }
    for side, items in enumerate((left, right)):
        wanted = Counter(leftover[side])
        for key, call in items:
            if wanted[key] > 0:
                wanted[key] -= 1
                answers[key[:2]][side].append(_erased(_answer(call)))
    for xs, ys in answers.values():
        if len(xs) != len(ys) or _unassigned(xs, ys, _answer_close) is not None:
            return signal, detail
    paired: Counter[str] = Counter()
    for key, count in leftover[0].items():
        paired[key[0]] += count
    return Signal.SAME, {
        member: f"{count} answers within {_ANSWER_ULPS} ulps of the other build's"
        for member, count in sorted(paired.items())
    }


def _answer_close(a: Any, b: Any) -> bool:
    """Two answers (handles erased) equal but for float noise: the same
    structure and normalised strings, every float within
    :data:`_ANSWER_ULPS` ulps of the largest finite |float| of either, a
    subnormal one compared as 0.0 (:func:`_measured`)."""
    left: list[float] = []
    right: list[float] = []
    if not _same_shape(a, b, left, right):
        return False
    left, right = [_measured(x) for x in left], [_measured(y) for y in right]
    tolerance = _ANSWER_ULPS * math.ulp(_scale(iter([*left, *right])))
    return all(
        x == y or abs(x - y) <= tolerance for x, y in zip(left, right, strict=True)
    )


def _measured(x: float) -> float:
    """``x``, or 0.0 for a subnormal: below the smallest normal double
    (``sys.float_info.min``, 2.2e-308) a float is no measurement. SolidWorks
    packs integers into doubles (``IEdge.GetCurveParams2``'s curve type, tag
    and sense), and some answers are memory read as doubles: on 2026-11-12
    ``ISurface.CylinderParams`` of pn_vn_pen_set_screw's faces that are no
    cylinder answered the high half of a module address, 0x00007FF9 on one
    worker and 0x00007FFF on another; nothing else in them differed."""
    return 0.0 if abs(x) < sys.float_info.min else x


def _erased(value: Any) -> Any:
    """``value`` with handles erased (the interface type kept), as
    :func:`_shape` erases them, and nothing else changed."""
    if isinstance(value, list):
        return [_erased(item) for item in value]
    if not isinstance(value, dict) or _is_float(value):
        return value
    if "h" in value:
        return {"h": value.get("p", "")}
    return {name: _erased(item) for name, item in value.items()}


_Point = tuple[float, float, float]
_Triangle = tuple[_Point, _Point, _Point]
_Cell = tuple[int, int, int, int]
_Bin = tuple[int, int, int]


@dataclass(frozen=True)
class _Mesh:
    """A binary STL's geometry (:func:`_mesh`)."""

    # Per plane, its outline (each edge just one of the plane's triangles
    # uses, in that triangle's winding): the plane's area.
    outlines: dict[frozenset[tuple[_Point, _Point]], float]
    area: float


@dataclass(frozen=True)
class _Pairing:
    """Each vertex one STL has and the other lacks, mapped to the point it is
    one with (:func:`_paired`); empty when both have the same vertices."""

    points: dict[_Point, _Point]
    count: int
    eps: float
    shift: float


def _stl_signal(
    base: conv.Conversation,
    new: conv.Conversation,
    base_captures: Path,
    new_captures: Path,
) -> tuple[Signal, dict[str, str] | None]:
    """Per STL path either build had SolidWorks write, whether the two last
    writes are the same geometry (:func:`_stl_comparison`). A path whose
    vertices were paired within eps keeps how in the detail, also when the
    geometry is the same."""
    a, b = _stl_files(base, base_captures), _stl_files(new, new_captures)
    if a is None or b is None or (not a and not b):
        return Signal.ABSENT, None
    differing: dict[str, str] = {}
    paired: dict[str, str] = {}
    for rel in sorted(a.keys() | b.keys()):
        if rel not in b or rel not in a:
            differing[rel] = "base only" if rel in a else "new only"
            continue
        same, detail = _stl_comparison(a[rel], b[rel])
        if not same:
            differing[rel] = detail or "different"
        elif detail is not None:
            paired[rel] = detail
    if differing:
        return Signal.DIFFERENT, differing
    return Signal.SAME, paired or None


def _stl_files(
    conversation: conv.Conversation, captures: Path
) -> dict[str, list[_Triangle] | str] | None:
    """Per STL path the build had SolidWorks write, its last write's
    :func:`_triangles`; ``None`` when a capture is missing or not the bytes
    the log describes."""
    found = _last_writes(conversation, captures, _STL_SUFFIX)
    if found is None:
        return None
    return {rel: _triangles(data) for rel, data in found.items()}


def _last_writes(
    conversation: conv.Conversation, captures: Path, suffix: str
) -> dict[str, bytes] | None:
    """Per path ending in ``suffix`` the build had SolidWorks write, the
    bytes of its last write; ``None`` when a capture is missing or not the
    bytes the log describes."""
    captured = conversation.trailer.get("captured", {})
    final: dict[str, dict[str, Any]] = {}
    for seq in sorted(captured, key=int):
        for rel, kept in captured[seq].items():
            if rel.lower().endswith(suffix):
                final[rel] = kept
    found: dict[str, bytes] = {}
    for rel, kept in final.items():
        try:
            data = gzip.decompress((captures / kept["file"]).read_bytes())
        except (OSError, EOFError, gzip.BadGzipFile):
            return None
        if hashlib.sha256(data).hexdigest() != kept["sha256"]:
            return None
        found[rel] = data
    return found


def pdf_inks(
    conversation: conv.Conversation, captures: Path
) -> dict[str, list[tuple[Any, ...]] | str] | None:
    """Per PDF path the build had SolidWorks write, its last write's
    :func:`_pdf_ink`; ``None`` when a capture is missing or not the bytes
    the log describes. Read once per judgement: :func:`judge` hands both
    builds' to the ``pdf`` signal and to :func:`jagged_outline`."""
    found = _last_writes(conversation, captures, _PDF_SUFFIX)
    if found is None:
        return None
    return {rel: _pdf_ink(data) for rel, data in found.items()}


def _read_once(
    base: conv.Conversation,
    new: conv.Conversation,
    base_captures: Path,
    new_captures: Path,
) -> Callable[[], tuple[Any, Any]]:
    """Both builds' :func:`pdf_inks`, read on the first call and kept."""
    return functools.cache(
        lambda: (pdf_inks(base, base_captures), pdf_inks(new, new_captures))
    )


def _pdf_signal(
    a: dict[str, Any] | None, b: dict[str, Any] | None
) -> tuple[Signal, dict[str, str] | None]:
    """Per PDF path either build had SolidWorks write (:func:`pdf_inks`),
    whether the two last writes print the same ink. A PDF's bytes are no
    signal: SolidWorks writes the export's date into them."""
    if a is None or b is None or (not a and not b):
        return Signal.ABSENT, None
    differing: dict[str, str] = {}
    for rel in sorted(a.keys() | b.keys()):
        if rel not in b or rel not in a:
            differing[rel] = "base only" if rel in a else "new only"
            continue
        found = _ink_difference(a[rel], b[rel])
        if found is not None:
            differing[rel] = found
    if differing:
        return Signal.DIFFERENT, differing
    return Signal.SAME, None


def _pdf_ink(data: bytes) -> list[tuple[Any, ...]] | str:
    """A PDF's ink (``_pdf_ink.read_pdf_ink``), page by page: its size, the
    sorted text runs (text and box) and the sorted path pieces (ends, width,
    colour, dash, fill, stroke), sheet coordinates rounded to
    :data:`_PDF_ROUND`. The order things were drawn in is no part of what
    prints. A PDF pdfium cannot read is its digest."""
    import tempfile

    import _pdf_ink  # pypdfium2: loaded for a drawing's judgement only

    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "ink.pdf"
        path.write_bytes(data)
        try:
            pages = _pdf_ink.read_pdf_ink(path)
        except _pdf_ink.pdfium.PdfiumError:
            return "bytes:" + hashlib.sha256(data).hexdigest()

    def rounded(*values: float) -> tuple[float, ...]:
        return tuple(round(float(value), _PDF_ROUND) for value in values)

    return [
        (
            rounded(page.width, page.height),
            sorted(
                (span.text, rounded(span.xmin, span.ymin, span.xmax, span.ymax))
                for span in page.spans
            ),
            sorted(
                (
                    rounded(s.x0, s.y0, s.x1, s.y1, s.width),
                    s.rgb,
                    s.dashed,
                    s.filled,
                    s.stroked,
                )
                for s in page.strokes
            ),
        )
        for page in pages
    ]


def _ink_difference(
    a: list[tuple[Any, ...]] | str, b: list[tuple[Any, ...]] | str
) -> str | None:
    """What differs between two PDFs' :func:`_pdf_ink`, or None."""
    if isinstance(a, str) or isinstance(b, str):
        return None if a == b else "bytes"
    if len(a) != len(b):
        return f"{len(a)} pages, new {len(b)}"
    for number, (x, y) in enumerate(zip(a, b, strict=True), start=1):
        if x[0] != y[0]:
            return f"page {number}: size {x[0]}, new {y[0]}"
        for what, index in (("text runs", 1), ("path pieces", 2)):
            base_only = Counter(x[index]) - Counter(y[index])
            new_only = Counter(y[index]) - Counter(x[index])
            if base_only or new_only:
                return (
                    f"page {number}: {base_only.total()} {what} base only, "
                    f"{new_only.total()} new only"
                )
    return None


def jagged_outline(
    base: conv.Conversation,
    new: conv.Conversation,
    a: dict[str, Any] | None,
    b: dict[str, Any] | None,
) -> bool:
    """Whether two drawings' PDFs (``a``, ``b``: :func:`pdf_inks`) differ
    only by a jagged crop outline drawn again: SolidWorks breaks a cropped
    view's outline along a random wiggle each time it draws it (2026-11-13,
    dt_pinion_arbor's detail A: three builds of the same requests, three
    wiggles). True only when both builds read the same jagged views
    (:func:`_jagged_boxes`), wrote the same PDFs with the same pages and text
    runs, and on every page that differs the differing path pieces are
    :func:`_rewiggled`. Any doubt is False."""
    boxes = _jagged_boxes(conv.recipe_calls(base.calls))
    if not boxes or boxes != _jagged_boxes(conv.recipe_calls(new.calls)):
        return False
    if not a or not b or a.keys() != b.keys():
        return False
    rewiggled = False
    for rel in sorted(a):
        x, y = a[rel], b[rel]
        if isinstance(x, str) or isinstance(y, str) or len(x) != len(y):
            return False
        for page_a, page_b in zip(x, y, strict=True):
            if page_a[:2] != page_b[:2]:  # size, text runs
                return False
            left, right = Counter(page_a[2]), Counter(page_b[2])
            if left == right:
                continue
            if not _rewiggled(left - right, right - left, left & right, boxes):
                return False
            rewiggled = True
    return rewiggled


def _jagged_boxes(calls: Sequence[conv.Call]) -> list[tuple[float, ...]]:
    """The sheet box (xmin, ymin, xmax, ymax, metres) of each view whose
    ``IView.CropViewJaggedOutline`` last read True: the last
    ``IView.GetOutline`` answer on that view's handle, unless a
    :data:`_VIEW_MOVES` request on the handle followed it."""
    outline: dict[int, tuple[float, ...] | None] = {}
    jagged: dict[int, bool] = {}
    for call in calls:
        if call.site == "IView.GetOutline":
            outline[call.handle] = _box(call.result)
        elif call.site in _VIEW_MOVES and call.kind is not conv.Kind.GET:
            outline[call.handle] = None
        elif call.site == "IView.CropViewJaggedOutline":
            if call.kind is conv.Kind.GET:
                jagged[call.handle] = call.result is True
    return sorted(
        box
        for handle, on in jagged.items()
        if on and (box := outline.get(handle)) is not None
    )


def _box(answer: Any) -> tuple[float, ...] | None:
    if not isinstance(answer, dict) or not isinstance(answer.get("t"), list):
        return None
    values = answer["t"]
    if len(values) != 4 or not all(_is_float(value) for value in values):
        return None
    return tuple(float.fromhex(value["f"]) for value in values)


def _rewiggled(
    base_only: Counter[Any],
    new_only: Counter[Any],
    unchanged: Counter[Any],
    boxes: list[tuple[float, ...]],
) -> bool:
    """Whether one page's differing path pieces (:func:`_pdf_ink`'s) are a
    jagged outline drawn again: all of one solid stroke (one width and
    colour, not dashed, not filled), all inside one jagged view's box, and
    on each side open chains (:func:`_open_ends`) whose ends are the same
    points and each the end of an unchanged piece: the wiggle is the stretch
    of the outline between the same two points of the unbroken outline."""
    pieces = [*base_only.elements(), *new_only.elements()]
    if len({(piece[0][4], *piece[1:]) for piece in pieces}) != 1:
        return False
    _, _, dashed, filled, stroked = pieces[0]
    if dashed or filled or not stroked:
        return False
    if not any(all(_inside(piece[0], box) for piece in pieces) for box in boxes):
        return False
    ends = _open_ends(base_only)
    attached = {end for piece in unchanged for end in _piece_ends(piece)}
    return ends is not None and ends == _open_ends(new_only) and ends <= attached


def _inside(ends: tuple[float, ...], box: tuple[float, ...]) -> bool:
    x0, y0, x1, y1, _ = ends
    xmin, ymin, xmax, ymax = box
    return all(
        xmin - _BOX_SLACK <= x <= xmax + _BOX_SLACK
        and ymin - _BOX_SLACK <= y <= ymax + _BOX_SLACK
        for x, y in ((x0, y0), (x1, y1))
    )


def _piece_ends(piece: tuple[Any, ...]) -> tuple[tuple[float, float], ...]:
    x0, y0, x1, y1, _ = piece[0]
    return (x0, y0), (x1, y1)


def _open_ends(pieces: Counter[Any]) -> frozenset[tuple[float, float]] | None:
    """The points where ``pieces`` (path pieces, ends as rounded) end: those
    an odd number of pieces end at. ``None`` for no pieces or when a
    connected run of them ends nowhere (a closed loop)."""
    degree: Counter[tuple[float, float]] = Counter()
    parent: dict[tuple[float, float], tuple[float, float]] = {}

    def root(point: tuple[float, float]) -> tuple[float, float]:
        while parent.setdefault(point, point) != point:
            point = parent[point]
        return point

    for piece in pieces.elements():
        start, end = _piece_ends(piece)
        degree[start] += 1
        degree[end] += 1
        parent[root(start)] = root(end)
    ends = frozenset(point for point, count in degree.items() if count % 2)
    if not degree or {root(p) for p in degree} != {root(p) for p in ends}:
        return None
    return ends


def _sidecar_signal(
    base: Path | None, new: Path | None
) -> tuple[Signal, dict[str, str] | None]:
    """Per file in either directory, whether the two builds wrote the same
    bytes. These are Python's outputs beside an assembly, written from
    SolidWorks' answers already rounded for noise (the geometry digest), so
    they are compared exactly."""
    a, b = _digests_in(base), _digests_in(new)
    if not a and not b:
        return Signal.ABSENT, None
    differing: dict[str, str] = {}
    for name in sorted(a.keys() | b.keys()):
        if name not in b or name not in a:
            differing[name] = "base only" if name in a else "new only"
        elif a[name] != b[name]:
            differing[name] = "bytes"
    if differing:
        return Signal.DIFFERENT, differing
    return Signal.SAME, None


def _digests_in(directory: Path | None) -> dict[str, str]:
    if directory is None or not directory.is_dir():
        return {}
    return {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in directory.iterdir()
        if path.is_file()
    }


def _triangles(data: bytes) -> list[_Triangle] | str:
    """A binary STL's triangles, three float32 corners each. Triangle order,
    corner rotation, facet normals, attribute bytes and the header are no
    part of its geometry (:func:`_mesh`). Anything but a well-formed binary
    STL of finite corners is its digest."""
    count = int.from_bytes(data[80:84], "little") if len(data) >= 84 else -1
    if len(data) != 84 + 50 * count:
        return "bytes:" + hashlib.sha256(data).hexdigest()
    rows = list(struct.iter_unpack("<12x9f2x", data[84:]))
    # A NaN or an infinity anywhere makes the float64 sum of float32 corners
    # non-finite; finite ones cannot overflow it.
    if not math.isfinite(sum(itertools.chain.from_iterable(rows))):
        return "bytes:" + hashlib.sha256(data).hexdigest()
    return [
        ((x0, y0, z0), (x1, y1, z1), (x2, y2, z2))
        for x0, y0, z0, x1, y1, z1, x2, y2, z2 in rows
    ]


def _stl_comparison(
    a: list[_Triangle] | str, b: list[_Triangle] | str
) -> tuple[bool, str | None]:
    """Whether two STLs are the same geometry, and what differed or how
    vertices were paired. Vertices within eps are one point (:func:`_paired`):
    both STLs take that point's one representative, so the planes, outlines
    and areas compared (:func:`_mesh_difference`) see the same corners on
    both sides, never the residue that told them apart."""
    if isinstance(a, str) or isinstance(b, str):
        return (True, None) if a == b else (False, "bytes")
    pairing = _paired(a, b)
    if isinstance(pairing, str):
        return False, pairing
    note = None
    if pairing.count:
        a, b = _substituted(a, pairing.points), _substituted(b, pairing.points)
        note = (
            f"{pairing.count} vertices paired within eps {pairing.eps:.3g} mm, "
            f"max shift {pairing.shift:.3g} mm"
        )
    found = _mesh_difference(_mesh(a), _mesh(b))
    if found is None:
        return True, note
    return False, found if note is None else f"{found} ({note})"


def _paired(a: Sequence[_Triangle], b: Sequence[_Triangle]) -> _Pairing | str:
    """The two STLs' vertex sets as one: each vertex one has and the other
    lacks paired one-to-one with the other's within eps
    (:data:`_STL_VERTEX_ULPS` float32 ulps of the largest |coordinate|,
    Chebyshev distance), both mapped to the smaller of the two. Otherwise why
    not, as ``vertices: ...``: a count that differs, or a vertex with no
    counterpart within eps, several, one exactly matched, or one that another
    vertex of its own STL is also within eps of. Eps is orders of magnitude
    below any STL's vertex spacing, so a pairing that is not unique is not
    noise; refusing reads it as other geometry, the conservative direction.

    O(n log n) at most: the vertices are hashed into cubes of side eps (a
    point within eps of another lies in its cube or one of the 26 around it)
    and the unmatched ones sorted, for a deterministic first refusal. Work
    stops at the first vertex that does not pair."""
    va = {p for triangle in a for p in triangle}
    vb = {p for triangle in b for p in triangle}
    only_a, only_b = va - vb, vb - va
    if not only_a and not only_b:
        return _Pairing({}, 0, 0.0, 0.0)
    counts = f"vertices: {len(only_a)} base only, {len(only_b)} new only"
    if len(only_a) != len(only_b):
        return counts
    largest = max(abs(c) for p in itertools.chain(va, vb) for c in p)
    eps = _STL_VERTEX_ULPS * math.ldexp(1.0, math.frexp(largest)[1] - 24)
    near_a, near_b = _bins(va, eps), _bins(vb, eps)
    points: dict[_Point, _Point] = {}
    shift = 0.0
    for p in sorted(only_a):
        found = _within(near_b, p, eps)
        if len(found) != 1:
            return f"{counts}: one with {len(found)} within eps {eps:.3g} mm"
        q = found[0]
        if q not in only_b:
            return f"{counts}: one within eps {eps:.3g} mm of a matched vertex"
        if _within(near_a, q, eps) != [p]:
            return f"{counts}: one not mutually unique within eps {eps:.3g} mm"
        points[p] = points[q] = min(p, q)
        shift = max(shift, abs(p[0] - q[0]), abs(p[1] - q[1]), abs(p[2] - q[2]))
    return _Pairing(points, len(only_a), eps, shift)


def _bins(points: set[_Point], eps: float) -> dict[_Bin, list[_Point]]:
    found: dict[_Bin, list[_Point]] = {}
    for p in points:
        found.setdefault(_bin(p, eps), []).append(p)
    return found


def _bin(p: _Point, eps: float) -> _Bin:
    return math.floor(p[0] / eps), math.floor(p[1] / eps), math.floor(p[2] / eps)


def _within(bins: dict[_Bin, list[_Point]], p: _Point, eps: float) -> list[_Point]:
    """The points of ``bins`` within eps of ``p`` in every coordinate."""
    i, j, k = _bin(p, eps)
    return [
        q
        for di, dj, dk in _NEIGHBOURS
        for q in bins.get((i + di, j + dj, k + dk), ())
        if max(abs(q[0] - p[0]), abs(q[1] - p[1]), abs(q[2] - p[2])) <= eps
    ]


def _substituted(
    triangles: Sequence[_Triangle], points: dict[_Point, _Point]
) -> list[_Triangle]:
    return [
        (points.get(p, p), points.get(q, q), points.get(r, r)) for p, q, r in triangles
    ]


def _mesh(triangles: Sequence[_Triangle]) -> _Mesh:
    """An STL's triangles as geometry that does not depend on how SolidWorks
    split its faces into triangles: per plane, the outline of the plane's
    triangles and their area. On 2026-11-11 two builds of
    dt_cone_swing_platform that made the same part wrote 35 of 1226 triangles
    otherwise: the same 724 vertices, a polygon of the top face and two
    rectangles of side walls split along other diagonals.

    A plane is every triangle whose binned plane touches the others' bins
    (:func:`_planes`). Its outline is the edges just one of its triangles
    uses, each in that triangle's winding: any triangulation of the same
    polygons over the same vertices keeps it, and a moved hole, a region of
    another shape or an inside-out patch changes it, whatever the area. A
    triangle without area is in a plane of its own kind. A curved face has no
    plane: each flat facet of it is one, so a curved face re-tessellated over
    the same vertices reads as other geometry. That is the conservative
    direction: a missed reuse, never an unsound one."""
    cells: list[_Cell | None] = []
    areas: list[float] = []
    for a, b, c in triangles:
        u = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
        v = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
        n = (
            u[1] * v[2] - u[2] * v[1],
            u[2] * v[0] - u[0] * v[2],
            u[0] * v[1] - u[1] * v[0],
        )
        length = math.sqrt(n[0] * n[0] + n[1] * n[1] + n[2] * n[2])
        areas.append(0.5 * length)
        if length == 0.0:
            cells.append(None)
            continue
        unit = (n[0] / length, n[1] / length, n[2] / length)
        offset = unit[0] * a[0] + unit[1] * a[1] + unit[2] * a[2]
        cells.append(
            (
                round(unit[0] / _NORMAL_STEP),
                round(unit[1] / _NORMAL_STEP),
                round(unit[2] / _NORMAL_STEP),
                round(offset / _OFFSET_STEP),
            )
        )
    plane_of = _planes({cell for cell in cells if cell is not None})
    planes: dict[_Cell | None, list[int]] = {}
    for index, cell in enumerate(cells):
        planes.setdefault(None if cell is None else plane_of[cell], []).append(index)
    outlines: dict[frozenset[tuple[_Point, _Point]], float] = {}
    for members in planes.values():
        edges = [
            (p, q)
            for index in members
            for p, q in itertools.pairwise((*triangles[index], triangles[index][0]))
        ]
        uses = Counter((p, q) if p <= q else (q, p) for p, q in edges)
        outline = frozenset(
            (p, q) for p, q in edges if uses[(p, q) if p <= q else (q, p)] == 1
        )
        outlines[outline] = outlines.get(outline, 0.0) + sum(areas[i] for i in members)
    return _Mesh(outlines, sum(areas))


def _planes(cells: set[_Cell]) -> dict[_Cell, _Cell]:
    """Each occupied plane bin's plane: bins one step apart in any of normal
    and offset are one, so a plane whose triangles' float32 noise straddles a
    bin edge stays one plane."""
    parent = {cell: cell for cell in cells}

    def root(cell: _Cell) -> _Cell:
        while parent[cell] != cell:
            parent[cell] = parent[parent[cell]]
            cell = parent[cell]
        return cell

    for cell in cells:
        for step in _TOUCHING:
            other = (
                cell[0] + step[0],
                cell[1] + step[1],
                cell[2] + step[2],
                cell[3] + step[3],
            )
            if other in parent:
                parent[root(other)] = root(cell)
    return {cell: root(cell) for cell in cells}


def _mesh_difference(a: _Mesh, b: _Mesh) -> str | None:
    """What differs between two STLs' geometry over one vertex set
    (:func:`_paired`), ``None`` for nothing: a plane's outline, or a plane's
    area beyond :data:`REL_TOL` of the larger total area."""
    if a.outlines.keys() != b.outlines.keys():
        return (
            f"plane outlines: {len(a.outlines.keys() - b.outlines.keys())} base "
            f"only, {len(b.outlines.keys() - a.outlines.keys())} new only"
        )
    tolerance = REL_TOL * max(a.area, b.area)
    off = sum(
        1 for k, area in a.outlines.items() if abs(area - b.outlines[k]) > tolerance
    )
    return f"plane areas: {off} differ" if off else None


# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------


def _text(value: str) -> str:
    for rule in conv.PROVENANCE_MASK:
        if rule.pattern.fullmatch(value):
            return f"<masked:{rule.name}>"
    return _counterless(value)


def _counterless(value: str) -> str:
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


def _distance(a: Any, b: Any, floor: float = 0.0) -> float:
    """How far apart two values are in :func:`_close`'s tolerance: the
    largest float difference over it (at most 1 when close), infinite for
    another structure or a difference no tolerance measures."""
    left: list[float] = []
    right: list[float] = []
    if not _same_shape(a, b, left, right):
        return math.inf
    tolerance = REL_TOL * max(_scale(iter([*left, *right])), floor)
    farthest = 0.0
    for x, y in zip(left, right, strict=True):
        if x == y:
            continue
        gap = abs(x - y)
        if not math.isfinite(gap) or tolerance == 0.0:
            return math.inf
        farthest = max(farthest, gap / tolerance)
    return farthest


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
