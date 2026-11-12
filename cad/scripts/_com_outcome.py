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
import itertools
import json
import math
import re
import struct
from collections import Counter
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
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
_NEIGHBOURS = tuple(itertools.product((-1, 0, 1), repeat=3))
_LISTED = 10
# Bound on a judge fault's message recorded in the result.
_ERROR_CHARS = 300
_SIGNALS = ("mass", "requests", "answers", "stl")


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


def judge(
    base: conv.Conversation,
    new: conv.Conversation,
    divergence: dict[str, Any] | None,
    base_captures: Path,
    new_captures: Path,
) -> dict[str, Any]:
    """``truth_cause`` and the :func:`outcome` fields of two recordings
    whose request divergence (``compare_conversations``) is ``divergence``;
    ``*_captures`` hold the files each build had SolidWorks write.

    Never raises. A fault of this judgement costs only what it judges: the
    cause reads ``error:<type>``, a signal ``absent`` (so the outcome is at
    best ``unknown``), each with its message in ``outcome_details``. The
    diff's result, whose request divergence is the ground truth, is kept."""
    cause, cause_error = _attempt(
        lambda: truth_cause(
            conv.recipe_calls(base.calls), conv.recipe_calls(new.calls), divergence
        )
    )
    found, error = _attempt(lambda: outcome(base, new, base_captures, new_captures))
    if error is not None:
        found = {
            "outcome": Outcome.UNKNOWN.value,
            "outcome_signals": {name: Signal.ABSENT.value for name in _SIGNALS},
            "outcome_details": {name: {"error": error} for name in _SIGNALS},
        }
    if cause_error is not None:
        cause = "error:" + cause_error.split(":", 1)[0]
        found["outcome_details"]["truth_cause"] = {"error": cause_error}
    return {"truth_cause": cause, **found}


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

    * ``mass``: every mass-property measurement, matched as a multiset
      within :data:`REL_TOL` (:func:`_mass_signal`);
    * ``requests``: the multiset of recipe requests;
    * ``answers``: the multiset of (request, answer) pairs, but for mass
      properties and answers about the session (``_SESSION_SITE``);
    * ``stl``: the geometry of every STL file SolidWorks wrote, vertices
      within float32 noise as one (:func:`_stl_comparison`; last write per
      path).

    Handles are erased (an object's identity number depends on call order),
    strings and floats are normalised as for noise. SLDPRT and BMP captures
    are no signal: a part file's bytes differ on every save, a screenshot's
    with the seat's window. A signal whose judgement raises is ``absent``,
    its message its detail."""
    a, b = conv.recipe_calls(base.calls), conv.recipe_calls(new.calls)
    keyed, keyed_error = _attempt(lambda: (_keyed_calls(a), _keyed_calls(b)))
    attempts: dict[str, Callable[[], tuple[Signal, Any]]] = {
        "mass": lambda: _mass_signal(a, b),
        "requests": lambda: _multiset_signal(
            [(site, request) for site, request, _ in keyed[0]],
            [(site, request) for site, request, _ in keyed[1]],
        ),
        "answers": lambda: _multiset_signal(
            [item for item in keyed[0] if item[2] is not None],
            [item for item in keyed[1] if item[2] is not None],
        ),
        "stl": lambda: _stl_signal(base, new, base_captures, new_captures),
    }
    signals: dict[str, Signal] = {}
    details: dict[str, Any] = {}
    for name, compute in attempts.items():
        keyed_only = keyed_error is not None and name in ("requests", "answers")
        result, error = (None, keyed_error) if keyed_only else _attempt(compute)
        if error is not None:
            result = Signal.ABSENT, {"error": error}
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
    captured = conversation.trailer.get("captured", {})
    final: dict[str, dict[str, Any]] = {}
    for seq in sorted(captured, key=int):
        for rel, kept in captured[seq].items():
            if rel.lower().endswith(_STL_SUFFIX):
                final[rel] = kept
    found: dict[str, list[_Triangle] | str] = {}
    for rel, kept in final.items():
        try:
            data = gzip.decompress((captures / kept["file"]).read_bytes())
        except (OSError, EOFError, gzip.BadGzipFile):
            return None
        if hashlib.sha256(data).hexdigest() != kept["sha256"]:
            return None
        found[rel] = _triangles(data)
    return found


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
