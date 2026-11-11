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
# tolerance, the centre of mass the part's length as well.
_MASS_ARRAY = re.compile(r"\.GetMassProperties\d*$")
_MASS_ARRAY_QUANTITIES = (
    slice(0, 3),
    slice(3, 4),
    slice(4, 5),
    slice(5, 6),
    slice(6, 12),
    slice(12, 13),
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
_LISTED = 10


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

    * ``mass``: every mass-property measurement, matched as a multiset
      within :data:`REL_TOL` (:func:`_mass_signal`);
    * ``requests``: the multiset of recipe requests;
    * ``answers``: the multiset of (request, answer) pairs, but for mass
      properties and answers about the session (``_SESSION_SITE``);
    * ``stl``: the geometry of every STL file SolidWorks wrote (:func:`_mesh`;
      last write per path).

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
    stl, stl_detail = _stl_signal(base, new, base_captures, new_captures)
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
            "stl": stl_detail,
        },
    }


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
        return all(_mass_close(c.site, c, d, length) for c, d in zip(x, y, strict=True))

    for kind in sorted(left):
        stranded = _unassigned(left[kind], right[kind], close)
        if stranded is None:
            continue
        # Against the other build's measurement in the same place.
        x, y = left[kind][stranded], right[kind][stranded]
        member = next(
            (c.site for c, d in zip(x, y, strict=True) if not close((c,), (d,))), kind
        )
        return Signal.DIFFERENT, {
            "member": member,
            "ordinal": stranded,
            "a": conv.clip([c.result for c in x]),
            "b": conv.clip([c.result for c in y]),
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
) -> int | None:
    """The first of ``left`` that no assignment pairs with a ``right`` it is
    close to; ``None`` when one pairs them all (equal lengths).

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
            return start
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


def _mass_close(site: str, x: conv.Call, y: conv.Call, length: float) -> bool:
    left, right = _mass_array(x), _mass_array(y)
    if left is None or right is None or len(left) != len(right):
        floor = length if site.endswith(".CenterOfMass") else 0.0
        return _close([x.result, x.raised, x.outs], [y.result, y.raised, y.outs], floor)
    if not _close([x.raised, x.outs], [y.raised, y.outs]):
        return False
    return all(
        _close(left[part], right[part], length if part.start == 0 else 0.0)
        for part in _MASS_ARRAY_QUANTITIES
    )


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
_Cell = tuple[int, int, int, int]


@dataclass(frozen=True)
class _Mesh:
    """A binary STL's geometry (:func:`_mesh`)."""

    vertices: frozenset[_Point]
    # Per plane, its outline (each edge just one of the plane's triangles
    # uses, in that triangle's winding): the plane's area.
    outlines: dict[frozenset[tuple[_Point, _Point]], float]
    area: float


def _stl_signal(
    base: conv.Conversation,
    new: conv.Conversation,
    base_captures: Path,
    new_captures: Path,
) -> tuple[Signal, dict[str, str] | None]:
    """Per STL path either build had SolidWorks write, whether the two last
    writes are the same geometry (:func:`_mesh_difference`)."""
    a, b = _stl_meshes(base, base_captures), _stl_meshes(new, new_captures)
    if a is None or b is None or (not a and not b):
        return Signal.ABSENT, None
    differing: dict[str, str] = {}
    for rel in sorted(a.keys() | b.keys()):
        if rel not in b or rel not in a:
            differing[rel] = "base only" if rel in a else "new only"
            continue
        found = _mesh_difference(a[rel], b[rel])
        if found is not None:
            differing[rel] = found
    if differing:
        return Signal.DIFFERENT, differing
    return Signal.SAME, None


def _stl_meshes(
    conversation: conv.Conversation, captures: Path
) -> dict[str, _Mesh | str] | None:
    """Per STL path the build had SolidWorks write, its last write's
    :func:`_mesh`; ``None`` when a capture is missing or not the bytes the log
    describes."""
    captured = conversation.trailer.get("captured", {})
    final: dict[str, dict[str, Any]] = {}
    for seq in sorted(captured, key=int):
        for rel, kept in captured[seq].items():
            if rel.lower().endswith(_STL_SUFFIX):
                final[rel] = kept
    found: dict[str, _Mesh | str] = {}
    for rel, kept in final.items():
        try:
            data = gzip.decompress((captures / kept["file"]).read_bytes())
        except (OSError, EOFError, gzip.BadGzipFile):
            return None
        if hashlib.sha256(data).hexdigest() != kept["sha256"]:
            return None
        found[rel] = _mesh(data)
    return found


def _mesh(data: bytes) -> _Mesh | str:
    """A binary STL as geometry that does not depend on how SolidWorks split
    its faces into triangles: the set of vertices and, per plane, the outline
    of the plane's triangles and their area. On 2026-11-11 two builds of
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
    direction: a missed reuse, never an unsound one. Triangle order, corner
    rotation, facet normals, attribute bytes and the header are no part of
    it. Anything but a well-formed binary STL is its digest."""
    count = int.from_bytes(data[80:84], "little") if len(data) >= 84 else -1
    if len(data) != 84 + 50 * count:
        return "bytes:" + hashlib.sha256(data).hexdigest()
    triangles = [
        ((x0, y0, z0), (x1, y1, z1), (x2, y2, z2))
        for x0, y0, z0, x1, y1, z1, x2, y2, z2 in struct.iter_unpack(
            "<12x9f2x", data[84:]
        )
    ]
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
    return _Mesh(
        frozenset(p for triangle in triangles for p in triangle),
        outlines,
        sum(areas),
    )


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


def _mesh_difference(a: _Mesh | str, b: _Mesh | str) -> str | None:
    """What differs between two STLs' geometry, ``None`` for nothing: the
    vertex set, a plane's outline, or a plane's area beyond :data:`REL_TOL` of
    the larger total area."""
    if isinstance(a, str) or isinstance(b, str):
        return None if a == b else "bytes"
    if a.vertices != b.vertices:
        return (
            f"vertices: {len(a.vertices - b.vertices)} base only, "
            f"{len(b.vertices - a.vertices)} new only"
        )
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
