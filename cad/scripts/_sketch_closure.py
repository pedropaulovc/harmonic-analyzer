"""The sketch-closure VERDICT: did a just-closed profile close, and did it merge?

TRACKED, unlike its forensic neighbour ``_seat_forensics``: a build RAISES on this
verdict mid-authoring (``diag_mcmaster_lib.assert_profile_closed``), so it is
part of every recipe that reads it. A stricter reading must invalidate the
artefacts an older reading passed -- identical inputs must give an identical
verdict -- which a recipe-inert module could not guarantee. The failure capture
reads the same census (:func:`_sketch_state`) from here.
"""

from __future__ import annotations

import contextlib
from collections.abc import Callable, Sequence
from typing import Any

import _common
import _telemetry


# swConstrainedStatus_e, for the captured sketch's solve state.
_CONSTRAINED_STATUS = {
    1: "unknown",
    2: "under-constrained",
    3: "fully-constrained",
    4: "over-constrained",
    5: "no-solution",
    6: "invalid-solution",
    7: "autosolve-off",
}
# Two endpoints at the same place within a nanometre are the same point: far
# below any modelling tolerance in this project (dimensions are millimetres) and
# far above float noise on coordinates computed in metres.
_COINCIDENT_TOL_M = 1e-9


def _resolve_sketch(adapter: Any, sketch: Any | None) -> tuple[Any | None, str]:
    """The sketch to inspect and its NAME: a caller-supplied dispatch, a named
    feature's sketch, or (default) the last profile sketch the document exited.

    The name is RETURNED rather than read off the sketch, because ``ISketch``
    does not declare ``Name``: it is an ``IFeature`` property (dispid 1,
    ``(8, 0)`` VT_BSTR) and appears in neither ``ISketch``'s ``_prop_map_get_``
    nor any of its 103 methods, so a ``Name`` read on a sketch yields nothing
    on a real seat however it is spelled. Same rule ``diag_dump_part``'s entity
    walk already follows ("a face has no Name and goes the GetFeature route").
    ``ISketch`` offers no route back to its feature either, so the identity has
    to come from the side that resolved it; when nothing resolved it by name (a
    caller's live dispatch, or ``GetActiveSketch2``) the name is genuinely
    unknown and :func:`_sketch_state` omits it rather than reporting blank.
    """
    if sketch is not None and not isinstance(sketch, str):
        return sketch, ""
    model = adapter.currentModel
    if model is None:
        return None, ""
    name = sketch or _common.feature_name_by_type(adapter, "ProfileFeature")
    if not name:
        active = adapter._attempt(
            lambda: _common._read_member(model, "GetActiveSketch2"), default=None
        )
        return active, ""
    feature = adapter._attempt(lambda: _common._feature_by_name(adapter, str(name)), default=None)
    if feature is None:
        return None, str(name)
    resolved = adapter._attempt(
        lambda: _common._read_member(feature, "GetSpecificFeature2"), default=None
    )
    return resolved, str(name)


def _point_census(sketch: Any) -> dict[str, Any]:
    """Sketch points vs DISTINCT sketch-point positions.

    This is the inference fingerprint. A closed N-segment chain whose
    exactly-coincident endpoints MERGED keeps N sketch points, all at distinct
    places; the same chain authored with inference off keeps 2N points sitting in
    coincident pairs, no contour closes, and a boss-extrude of it returns
    ``None``. ``coincident_point_pairs > 0`` therefore reads "the endpoints did
    not merge" straight off the artefact, with no re-run.
    """
    points = list(sketch.GetSketchPoints2() or [])
    places: list[tuple[float, float, float]] = []
    for point in points:
        coords = tuple(_common._read_member(point, axis) for axis in ("X", "Y", "Z"))
        if all(isinstance(value, (int, float)) for value in coords):
            quantum = _COINCIDENT_TOL_M
            places.append(
                tuple(round(float(value) / quantum) * quantum for value in coords)
            )
    census: dict[str, Any] = {"point_count": len(points)}
    if places:
        census["distinct_point_positions"] = len(set(places))
        census["coincident_point_pairs"] = len(places) - len(set(places))
    return census


def _sketch_state(
    adapter: Any, sketch: Any | None, expected_points: int | None = None
) -> dict[str, Any]:
    """Contour/region/point census of the sketch a failing feature consumed.

    ``contour_count``/``region_count`` are the direct answer to "did this profile
    close?" -- an open loop yields neither -- and the point census
    (:func:`_point_census`) says whether the endpoints merged, which is WHY.
    This is the EARLIEST detectable symptom: ``exit_sketch`` accepts an open
    profile silently and the failure only surfaces a whole feature later, as
    ``FeatureExtrusion3`` returning ``None`` with no record of which endpoint
    failed to merge.
    """
    resolved, name = _resolve_sketch(adapter, sketch)
    if resolved is None:
        return {"sketch": None}
    probes: dict[str, Callable[[], Any]] = {
        "contour_count": lambda: int(resolved.GetSketchContourCount()),
        "region_count": lambda: int(resolved.GetSketchRegionCount()),
        "segment_count": lambda: len(list(resolved.GetSketchSegments() or [])),
        "line_count": lambda: int(resolved.GetLineCount()),
        "arc_count": lambda: int(resolved.GetArcCount()),
        "automatic_solve": lambda: bool(resolved.GetAutomaticSolve()),
    }
    state: dict[str, Any] = {
        key: adapter._attempt(probe, default=None) for key, probe in probes.items()
    }
    if name:
        # Absent, not blank, when nothing resolved the sketch by name: a "name"
        # that is always "" reads in the artefact as "the seat would not tell
        # us", a claim no read was ever made to support. Same rule the point
        # census follows -- a number nobody measured is omitted, not defaulted.
        state["name"] = name
    status = adapter._attempt(lambda: int(resolved.GetConstrainedStatus()), default=None)
    state["constrained_status"] = status
    state["constrained"] = _CONSTRAINED_STATUS.get(status, "unknown")
    try:
        state.update(_point_census(resolved))
    except Exception as exc:  # noqa: BLE001 - a lost census must SAY it was lost
        state["point_census_error"] = f"{type(exc).__name__}: {exc}"
    if expected_points is not None:
        # Compare against the POINT COUNT, not the distinct positions: coincident
        # endpoints occupy the SAME place whether or not they merged, so distinct
        # positions are identical in both cases and only the point count moves
        # (N when merged, 2N when not). >0 means merges the author declared MUST
        # happen did not.
        state["expected_distinct_points"] = expected_points
        points = state.get("point_count")
        if isinstance(points, int):
            state["unmerged_points"] = points - expected_points
    return state



def log_profile_geometry(
    label: str, points: Sequence[Sequence[float]]
) -> dict[str, Any]:
    """Log what a profile was AUTHORED to be, computed in Python, before COM.

    Per-entity authoring logs are not uniform today: ``shank``, ``hex`` and
    ``cutter`` log every ``add_line`` with coordinates, while ``washer``,
    ``trim``, ``helix seed``, ``runout``, ``dash0/1/2`` and ``logo`` log nothing
    -- and the profile that failed on 2026-09-17 was in the silent group, so the
    recovered log could not say whether it closed into two loops, nine open
    segments, or none. One line per profile makes a SUCCESS comparable with a
    failure, which is the whole point of recording it.

    This is the AUTHOR's intent: how many endpoints were emitted, how many
    distinct places they occupy, and therefore how many coincidences the author
    is asking the seat to merge. Compare it against the seat's own verdict from
    :func:`record_sketch_closure` -- intent from Python, outcome from COM.
    """
    places = [
        tuple(round(float(value) / _COINCIDENT_TOL_M) * _COINCIDENT_TOL_M for value in point)
        for point in points
    ]
    distinct = len(set(places))
    intent: dict[str, Any] = {
        "profile": label,
        "authored_points": len(places),
        "distinct_places": distinct,
        "expected_merges": len(places) - distinct,
    }
    _telemetry.success(
        f"profile {label}: {len(places)} authored points over {distinct} places "
        f"({intent['expected_merges']} coincidences to merge)",
        **intent,
    )
    return intent


def record_sketch_closure(
    adapter: Any,
    label: str,
    sketch: Any | None = None,
    *,
    expected_points: int | None = None,
    expect_contours: int | None = None,
) -> dict[str, Any]:
    """Read a just-closed sketch's CLOSURE VERDICT once, log it, and return it.

    On 2026-09-17 ``exit_sketch logo`` returned OK, ``Sketch11`` was created and
    renamed, and ``FeatureExtrusion3`` found no usable contour 1.9 s later.
    Between those two events nothing was recorded, so a four-hour investigation
    replaced what one line of log would have said: the seat accepted a sketch
    with no closed loop.

    Read ONCE, consumed twice: the returned dict is the same shape the failure
    capture records, so a caller's fail-safe guard decides whether to raise from
    THIS verdict rather than issuing its own second read of an API whose return
    shape is disputed (``ISketch.CheckFeatureUse``). Callers should pass the
    verdict's ``contour_count``/``unmerged_points`` to
    :func:`capture_com_failure` as context instead of re-reading the sketch.

    Never raises: a verdict that cannot be read logs ``unknown`` and returns what
    it has, because a sketch that would have built must not fail on the way to
    being described. Deciding to FAIL on a bad verdict is the caller's job.
    """
    verdict = adapter._attempt(
        lambda: _sketch_state(adapter, sketch, expected_points), default=None
    )
    if not verdict:
        _telemetry.warn(f"sketch {label}: closure verdict unavailable", sketch=label)
        return {"sketch": label, "closure": "unknown"}
    contours = verdict.get("contour_count")
    unmerged = verdict.get("unmerged_points")
    # Tri-state on purpose: "open" is a MEASUREMENT (the seat reported zero
    # contours) and "unknown" is the absence of one. Collapsing them would put a
    # verdict in the log that nothing measured -- the exact move that made
    # 2026-09-17 unfalsifiable.
    readable = isinstance(contours, int)
    closed = readable and contours > 0
    verdict = {
        **verdict,
        "sketch_label": label,
        "closure": ("closed" if closed else "open") if readable else "unknown",
    }
    summary = (
        f"sketch {label}: {contours} contour(s), "
        f"{verdict.get('segment_count')} segment(s), "
        f"{verdict.get('point_count')} point(s), {verdict.get('constrained')}"
    )
    short = {
        key: value
        for key, value in verdict.items()
        if key
        in {
            "sketch_label",
            "closure",
            "contour_count",
            "region_count",
            "segment_count",
            "point_count",
            "distinct_point_positions",
            "coincident_point_pairs",
            "unmerged_points",
            "constrained",
            "point_census_error",
        }
    }
    wanted = 1 if expect_contours is None else expect_contours
    if not readable:
        _telemetry.warn(
            f"sketch {label}: closure verdict unreadable -- a later feature "
            f"failure on this profile cannot be told from a seat-state failure",
            **short,
        )
    elif contours < wanted:
        # The earliest detectable symptom of the 2026-09-17 mechanism: the seat
        # accepted the sketch, so only this count says the loops did not close.
        _telemetry.warn(
            f"{summary} -- expected at least {wanted} closed contour(s); "
            f"a feature consuming this profile will get no usable contour",
            **short,
        )
    elif unmerged:
        _telemetry.warn(
            f"{summary} -- {unmerged} endpoint(s) did not merge", **short
        )
    else:
        _telemetry.success(summary, **short)
    with contextlib.suppress(Exception):
        _telemetry.event("sketch.closure", **_common._attributes_of(short))
    return verdict
