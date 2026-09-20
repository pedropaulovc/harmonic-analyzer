"""Shared infrastructure for the part reproduction scripts.

Every part/assembly in ``cad/out`` is built by a ``build_<part>.py`` script in
this directory that drives SolidWorks through the ``PyWin32Adapter`` from the
``solidworks-mcp-python`` package — vendored as the ``SolidworksMCP-python``
git submodule and installed editable by ``uv sync`` (``[tool.uv.sources]``), so
``import solidworks_mcp`` resolves to the submodule with no path juggling.

Conventions (see cad/DIMENSIONS.md for the dimension source of truth):

* All sketch geometry is in millimetres; dimension constants are declared at
  the top of each script and traceable to a DIMENSIONS.md row.
* Every sketch must pass ``check_sketch_fully_defined`` before it is consumed
  by a feature — use :func:`ensure_fully_defined`.

Fully-defined recipes (probed live on SW 2026; semantic anchoring via point
refs ``"<EntityId>.center/.start/.end"`` + ``"origin"`` and point-to-point
driving dims, SolidworksMCP-python PRs #55/#56):

* **Circles**: :func:`define_circle` anchors the centre point semantically —
  coincident-to-origin at (0,0), an alignment relation plus one distance dim
  on-axis, two distance dims in general position — then adds a DRIVING
  diameter. ``fix`` is never used.
* **Line chains**: consecutive ``add_line`` calls sharing exact endpoint
  coordinates get merged/coincident vertices; anchor ONE vertex with
  :func:`anchor_point_to_origin`, then horizontal/vertical constraints and
  per-segment length dimensions fully define the chain. Never anchor a
  second vertex of the same chain — the dims already determine it through
  the merged vertices and the sketch goes over-defined. For closed
  axis-parallel chains :func:`define_rectilinear_chain` applies the whole
  recipe (skipping the one redundant dim per direction that closure
  implies); for closed sloped chains use :func:`define_polygon_chain`.
  Revolve profiles whose closing segment lies on the axis need no extra
  treatment: the merged-in centerline carries no constraints of its own.
* **Unsigned distance dims keep the current side**: geometry is created at
  its final coordinates and the dims match, so the solver keeps negative-
  quadrant centres on the negative side through ``ForceRebuild3`` (probed).
* **Over-defined triage**: ``adapter.get_over_defining_relations()`` names
  the conflicting relations; drop the redundant anchor dim, keep the
  semantic relation.
* **fix is a last resort** for reference geometry that genuinely cannot be
  dimensioned (currently only the equation-driven spring-hook curves, which
  have no free endpoints). Every surviving ``fix`` needs an inline comment
  justifying it.
"""

from __future__ import annotations

import asyncio
import contextlib
import ctypes
import functools
import json
import math
import os
import re
import shutil
import sys
import tempfile
import time
from collections.abc import Awaitable, Callable, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from types import MappingProxyType
from typing import Any, NoReturn

import _telemetry  # observability spine: console logging + tracing, preconfigured
import _watchdog  # COM crash/hang watchdog (started per session in run_build)

CAD_ROOT = Path(__file__).resolve().parents[1]
OUT_SLDPRT = CAD_ROOT / "out" / "sldprt"
OUT_SLDASM = CAD_ROOT / "out" / "sldasm"
OUT_PNG = CAD_ROOT / "out" / "png"
OUT_STL = CAD_ROOT / "out" / "stl"
# Forensic artefacts of a failed COM build step: a saved copy of the failing
# document, a BMP of the seat and the capture.json that indexes them, one
# directory per failure label AND per capture instant -- a retried failure must
# not erase the evidence of the failure it is retrying (see
# :func:`capture_com_failure`).
OUT_FAILURES = CAD_ROOT / "out" / "reports" / "failures"
# Vendored input artefacts a build imports at run time (e.g. the nameplate
# engraving DXF). A build script that reads one of these must resolve it under
# this dir so dodo's data_deps_of picks it up as a file_dep + cache-key input.
REFERENCES_DIR = CAD_ROOT / "references"
# The repo-owned part template every part is created from (hand-made in
# SolidWorks; carries the doc properties the COM API cannot write -- the
# DimXpert block-tolerance decimals + angular value). run_build pins the
# seat's default part template to it before building, so NewPart inherits it
# on ANY seat; dodo folds it into every part's recipe/cache key (path
# duplicated there deliberately -- importing _buildgraph here would drag graph
# tooling into every part's dep closure).
PART_TEMPLATE = CAD_ROOT / "templates" / "harmonic-analyzer.PRTDOT"

IN = 25.4  # inch -> mm

# Roller-chain link component prefixes; contact between two of these is an
# articulating-mechanism contact, not an interference fault (check_no_interference).
_CHAIN_LINK_PREFIXES = ("chain-inner-link", "chain-outer-link")

DEFAULT_VIEWS = ("isometric",)
_ROUTINE_PART_VIEWS = frozenset(
    (
        "front",
        "back",
        "left",
        "right",
        "top",
        "bottom",
        "isometric",
        "trimetric",
        "dimetric",
    )
)


_T0 = time.perf_counter()


def log(message: str) -> None:
    """Timestamped progress line, now an OpenTelemetry DEBUG record.

    Kept as a thin alias over :func:`_telemetry.progress` so the ~170 scripts
    importing ``log`` from here are instrumented unchanged: the record is
    bridged into OTel (correlated to the active span) and rendered to the
    console with the historical ``  ..  [stamp] message`` styling.
    """
    _telemetry.progress(message)


def check(label: str, result: Any) -> Any:
    """Raise when an adapter result is not success; return ``result.data``.

    A failure raises inside the active span, where :func:`_telemetry.span`
    records it (ERROR status + exception event); success emits an OTel SUCCESS
    record (the historical ``  OK  `` line).
    """
    if not result.is_success:
        raise RuntimeError(f"{label} failed: {result.error}")
    _telemetry.success(label)
    return result.data


@_telemetry.traced("sketch.ensure_defined", label_param="label")
async def ensure_fully_defined(
    adapter: Any,
    label: str,
    fix_entities: Iterable[str] = (),
    allow_fix_escalation: bool = False,
) -> None:
    """Assert the active sketch is fully defined.

    Raises when the sketch is under- or over-defined. On over-defined, the
    error includes ``get_over_defining_relations()`` so the redundant anchor
    is identifiable without opening SolidWorks.

    ``fix_entities`` + ``allow_fix_escalation=True`` enable the fix-escalation
    loop with a loud WARN. The only legitimate users are the whitelisted
    equation-driven gear-gap sketches (_gear.cut_tooth_gap and its cone/
    removable variants): those curves re-solve from equation globals on
    configuration changes, so no static relation/dimension scheme can define
    them without breaking regeneration. Everything else anchors points to the
    origin with semantic relations/dims.
    """

    async def _state() -> str | None:
        res = await adapter.check_sketch_fully_defined()
        if res.is_success and res.data:
            state = res.data.get("definition_state")
            if state not in ("fully_defined", "under_defined", "over_defined"):
                _telemetry.debug(f"check payload: {res.data!r}")
            return state
        return None

    state = await _state()
    if state == "fully_defined":
        _telemetry.success(f"fully defined: {label}")
        return

    if state == "over_defined":
        over = await adapter.get_over_defining_relations()
        detail = over.data if over.is_success else over.error
        raise RuntimeError(
            f"{label}: sketch OVER-defined; over-defining relations: {detail!r}"
        )

    fix_entities = list(fix_entities)
    if not (allow_fix_escalation and fix_entities):
        hint = (
            " (legacy fix escalation disabled; anchor a point to the origin "
            "with semantic relations/dims instead)"
            if fix_entities
            else ""
        )
        raise RuntimeError(f"{label}: sketch not fully defined (state={state!r}){hint}")

    # Whitelisted equation-curve path: escalate one entity at a time
    # (fixing everything at once makes the driving dimensions redundant
    # and over-defines the sketch). "unknown" is kept fixable as a safety
    # net: the status probe can transiently fail (pywin32 property/method
    # resolution drift on GetConstrainedStatus) and a later read may recover.
    _telemetry.warn(
        f"{label}: fix escalation (equation-curve whitelist only"
        " — anything else must use semantic anchors)"
    )
    for entity_id in fix_entities:
        if state not in ("under_defined", "unknown"):
            break
        fixed = await adapter.add_sketch_constraint(entity_id, None, "fix")
        if not fixed.is_success:
            raise RuntimeError(f"{label}: fix {entity_id} failed: {fixed.error}")
        state = await _state()
        _telemetry.debug(f"fixed {entity_id} -> {state}")
        if state == "fully_defined":
            _telemetry.success(f"fully defined after fixing {entity_id}: {label}")
            return

    raise RuntimeError(f"{label}: sketch not fully defined (state={state!r})")


async def dimension_between(
    adapter: Any, ref1: str, ref2: str, kind: str, value: float, label: str
) -> str:
    """Driving dimension between two point refs (``horizontal_distance``,
    ``vertical_distance``, or aligned ``distance``); value in mm."""
    result = await adapter.add_sketch_dimension(ref1, ref2, kind, value)
    return check(f"{kind} {label} = {value:g}", result)


async def anchor_point_to_origin(
    adapter: Any, point_ref: str, x: float, y: float, label: str
) -> None:
    """Fully anchor a sketch point at (x, y) relative to the sketch origin.

    * (0, 0): coincident to the origin (safe even when creation-time
      inference already snapped it — probed live).
    * On-axis: an alignment relation supplies the zero coordinate (zero-
      valued dims are invalid) plus one distance dim for the other.
    * General: horizontal + vertical distance dims (absolute values — the
      solver keeps the side the geometry was created on, probed live).

    Sub-nanometre coordinates snap to zero (as in :func:`anchor_point_to_point`):
    trig-derived vertices land within ulps of an axis, and a 1e-16 distance dim
    is as invalid to SolidWorks as a zero one.
    """
    if abs(x) < 1e-9:
        x = 0.0
    if abs(y) < 1e-9:
        y = 0.0
    if x == 0.0 and y == 0.0:
        check(
            f"coincident {label} -> origin",
            await adapter.add_sketch_constraint(point_ref, "origin", "coincident"),
        )
        return
    if y == 0.0:
        check(
            f"horizontal_points {label} -> origin",
            await adapter.add_sketch_constraint(
                point_ref, "origin", "horizontal_points"
            ),
        )
        await dimension_between(
            adapter, point_ref, "origin", "horizontal_distance", abs(x), label
        )
        return
    if x == 0.0:
        check(
            f"vertical_points {label} -> origin",
            await adapter.add_sketch_constraint(point_ref, "origin", "vertical_points"),
        )
        await dimension_between(
            adapter, point_ref, "origin", "vertical_distance", abs(y), label
        )
        return
    await dimension_between(
        adapter, point_ref, "origin", "horizontal_distance", abs(x), label
    )
    await dimension_between(
        adapter, point_ref, "origin", "vertical_distance", abs(y), label
    )


async def anchor_point_to_point(
    adapter: Any, ref1: str, ref2: str, dx: float, dy: float, label: str
) -> None:
    """Pin ``ref2`` at offset (dx, dy) from ``ref1``: an alignment relation
    supplies a zero component (zero-valued dims are invalid), distance dims
    the rest. Offsets are unsigned at the dim level — the solver keeps the
    side the geometry was created on (probed live). Sub-nanometre offsets
    snap to zero: trig-derived polygon vertices land within ulps of the
    axes, and a 1e-16 dim is as invalid as a zero one."""
    if abs(dx) < 1e-9:
        dx = 0.0
    if abs(dy) < 1e-9:
        dy = 0.0
    if dx == 0.0 and dy == 0.0:
        raise ValueError(f"{label}: coincident points want a merge, not an anchor")
    if dx == 0.0:
        check(
            f"vertical_points {label}",
            await adapter.add_sketch_constraint(ref1, ref2, "vertical_points"),
        )
        await dimension_between(
            adapter, ref1, ref2, "vertical_distance", abs(dy), label
        )
        return
    if dy == 0.0:
        check(
            f"horizontal_points {label}",
            await adapter.add_sketch_constraint(ref1, ref2, "horizontal_points"),
        )
        await dimension_between(
            adapter, ref1, ref2, "horizontal_distance", abs(dx), label
        )
        return
    await dimension_between(adapter, ref1, ref2, "horizontal_distance", abs(dx), label)
    await dimension_between(adapter, ref1, ref2, "vertical_distance", abs(dy), label)


def _record_point_to_point_cursor(
    rec: "Callable[[], None]", dx: float, dy: float
) -> None:
    """Drive ``rec`` once per dim :func:`anchor_point_to_point` emits for offset
    ``(dx, dy)`` -- one on an axis-aligned segment, two (horizontal then
    vertical) in general -- keeping a cursor record aligned with its emission."""
    sdx = 0.0 if abs(dx) < 1e-9 else dx
    sdy = 0.0 if abs(dy) < 1e-9 else dy
    if sdx == 0.0 and sdy == 0.0:
        return
    if sdx == 0.0 or sdy == 0.0:
        rec()
        return
    rec()
    rec()


@_telemetry.traced("sketch.polygon", label_param="label")
async def define_polygon_chain(
    adapter: Any,
    lines: list[str],
    points: list[tuple[float, float]],
    anchor: int = 0,
    label: str = "polygon",
    *,
    dims: "SketchDims | None" = None,
    names: list[str | None] | None = None,
    drives: list[str | None] | None = None,
) -> None:
    """Fully define a CLOSED line chain of arbitrary slopes semantically.

    Vertex ``anchor`` goes to the origin; every segment then pins its end
    relative to its start via :func:`anchor_point_to_point` — except the
    segment ENDING at the anchored vertex, whose span the closure supplies
    (dimensioning it too over-defines the sketch). Prefer
    :func:`define_rectilinear_chain` for axis-parallel chains: it emits
    segment-length dims instead of per-axis offsets.

    Self-naming: pass ``dims`` plus ``names`` / ``drives`` aligned to the
    EMISSION ORDER -- the anchor dims first (x, then z; only the non-zero ones),
    THEN each kept segment's offset dims in line order (horizontal then vertical
    per general segment; one for an axis-aligned segment). Unnamed slots stay
    auto-named/undriven.
    """
    n = len(lines)
    if n != len(points):
        raise ValueError(
            f"{label}: need a closed chain (lines {n} != points {len(points)})"
        )
    rec = _dim_cursor(dims, names, drives)
    await anchor_point_to_origin(
        adapter, f"{lines[anchor]}.start", *points[anchor], f"{label} anchor"
    )
    _record_origin_anchor_cursor(rec, *points[anchor])
    skip = (anchor - 1) % n  # the segment ending at the anchored vertex
    for i, line in enumerate(lines):
        if i == skip:
            continue
        (x1, y1), (x2, y2) = points[i], points[(i + 1) % n]
        await anchor_point_to_point(
            adapter, f"{line}.start", f"{line}.end", x2 - x1, y2 - y1, f"{label} {line}"
        )
        _record_point_to_point_cursor(rec, x2 - x1, y2 - y1)


class SketchDims:
    """Ordered record of the friendly name + optional driving equation for each
    dimension a ``define_*`` helper creates, captured AS the dim is created so
    naming and driving never re-derive creation order downstream.

    This replaces the old, fragile pattern of a hand-written positional list far
    from the geometry (``RECT_DIMS = ["Width", "Depth", ...]``) cross-fingered to
    match whatever order the helper happened to emit. The emitting helper owns
    the order -- crucially, it also owns the count: an on-axis circle centre is
    ONE dim, an off-axis centre is TWO (see :func:`anchor_point_to_origin`), so a
    script that hard-codes three-per-circle silently mis-maps the moment a circle
    sits on an axis. The helper knows ``x``/``y``, so it records exactly the dims
    it emitted.

    Pass one instance per sketch into the ``define_*`` helpers; after
    ``exit_sketch`` + :func:`name_sketch`, call :meth:`apply` to rename the dims
    and collect their (deferred) drive jobs."""

    def __init__(self) -> None:
        self._rows: list[tuple[str | None, str | None]] = []

    def record(self, name: str | None, drive: str | None = None) -> None:
        """Append one dim's friendly ``name`` (``None`` = leave it auto-named)
        and optional ``drive`` equation expression, in creation order."""
        self._rows.append((name, drive))

    def apply(self, adapter: Any, feature_name: str) -> list[tuple[str, str]]:
        """Rename this sketch's dims (creation order) to the recorded names and
        return the ``(dim@feature, expr)`` drive jobs to run once the whole model
        exists. Naming is immediate; driving is deferred by the caller so every
        equation target resolves after a final rebuild.

        Asserts the recorded count equals the feature's actual display-dimension
        count -- the structural guard that fails loud (naming the sketch) if a
        helper's emission ever drifts from what it recorded, instead of silently
        mis-naming."""
        feat = _feature_by_name(adapter, feature_name)
        return self.apply_feature(adapter, feat, feature_name)

    def apply_feature(
        self, adapter: Any, feature: Any, feature_name: str
    ) -> list[tuple[str, str]]:
        """Apply this record to an already-resolved feature dispatch.

        Hole Wizard placement sketches are subfeatures and therefore absent
        from the document's top-level feature walk. Callers that already hold
        the subfeature use this path; ordinary sketches keep :meth:`apply`.
        """
        actual = len(list(_display_dimensions(feature, feature_name)))
        if actual != len(self._rows):
            raise RuntimeError(
                f"{feature_name}: recorded {len(self._rows)} dims but the feature "
                f"has {actual} -- a define_* helper's dim emission drifted from "
                "what it recorded into SketchDims"
            )
        _name_dimensions_feature(
            feature, feature_name, [name for name, _ in self._rows]
        )
        return [
            (f"{name}@{feature_name}", drive)
            for name, drive in self._rows
            if name and drive
        ]


def _record_origin_anchor(
    dims: SketchDims | None,
    x: float,
    y: float,
    name_x: str | None,
    name_y: str | None,
    drive_x: str | None,
    drive_y: str | None,
) -> None:
    """Record into ``dims`` exactly the centre/anchor dims that
    :func:`anchor_point_to_origin` emits for ``(x, y)``: none at the origin, one
    on an axis, two in general -- so the record mirrors the geometry."""
    if dims is None:
        return
    sx = 0.0 if abs(x) < 1e-9 else x
    sy = 0.0 if abs(y) < 1e-9 else y
    if sx != 0.0:
        dims.record(name_x, drive_x)
    if sy != 0.0:
        dims.record(name_y, drive_y)


@_telemetry.traced("sketch.circle", label_param="label")
async def define_circle(
    adapter: Any,
    x: float,
    y: float,
    radius: float,
    label: str,
    *,
    dims: "SketchDims | None" = None,
    names: tuple[str | None, str | None, str | None] | None = None,
    drives: tuple[str | None, str | None, str | None] | None = None,
) -> str:
    """Add a circle, anchor its centre to the origin semantically, then add
    a DRIVING diameter dimension. No ``fix`` involved.

    The raw ``add_circle`` runs with sketch inference SUPPRESSED (restored
    afterwards): with it on, a second concentric/near circle snaps to the first
    and the call fails (proven live on the coefficients-plate hole column).
    Same rationale as :func:`add_line_chain` -- the centre/diameter are pinned
    explicitly below, so inference during the draw only ever hurts.

    Self-naming: pass ``dims`` (a per-sketch :class:`SketchDims`) plus ``names`` /
    ``drives`` as ``(centre_x, centre_z, diameter)`` tuples to record this
    circle's dims for later renaming/driving. Only the dims actually emitted are
    recorded -- an on-axis centre drops its zero coordinate -- so the same call
    is correct whether the circle is on an axis or not."""
    sketch_mgr = adapter.currentSketchManager
    prev_add_to_db = bool(sketch_mgr.AddToDB)
    sketch_mgr.AddToDB = True
    try:
        circle = await adapter.add_circle(x, y, radius)
        check(f"add_circle {label}", circle)
    finally:
        sketch_mgr.AddToDB = prev_add_to_db
    await anchor_point_to_origin(adapter, f"{circle.data}.center", x, y, label)
    n_x, n_z, n_dia = names or (None, None, None)
    d_x, d_z, d_dia = drives or (None, None, None)
    _record_origin_anchor(dims, x, y, n_x, n_z, d_x, d_z)
    check(
        f"dimension {label} diameter",
        await adapter.add_sketch_dimension(circle.data, None, "diameter", radius * 2.0),
    )
    if dims is not None:
        dims.record(n_dia, d_dia)
    return circle.data


@_telemetry.traced("sketch.rectangle", label_param="label")
async def define_centered_rectangle(
    adapter: Any,
    half_x: float,
    half_z: float,
    label: str,
    *,
    dims: "SketchDims | None" = None,
    name_width: str | None = None,
    name_depth: str | None = None,
    drive_width: str | None = None,
    drive_depth: str | None = None,
) -> list[str]:
    """Draw an origin-centred rectangle with two construction diagonals.

    The midpoint of one corner-to-corner diagonal is coincident with the sketch
    origin, so width and depth are the only driving dimensions. This mirrors a
    native center rectangle without its cursor-inference side effects: an exact
    square passed to ``CreateCenterRectangle`` can acquire a redundant SAME
    LENGTH relation or duplicate origin coincidence and turn dimensions into
    references, which later makes equation assignment warn or fail.
    """
    if abs(half_x - half_z) >= 1e-9:
        sketch_mgr = adapter.currentSketchManager
        previous_add_to_db = bool(sketch_mgr.AddToDB)
        sketch_mgr.AddToDB = False
        try:
            raw = sketch_mgr.CreateCenterRectangle(
                0.0, 0.0, 0.0, half_x / 1000.0, half_z / 1000.0, 0.0
            )
        finally:
            sketch_mgr.AddToDB = previous_add_to_db
        segments = list(raw or [])
        edges: list[tuple[str, float, float]] = []
        diagonal_id: str | None = None
        for segment in segments:
            if bool(_read_member(segment, "ConstructionGeometry")):
                # CreateCenterRectangle returns two corner-to-corner construction
                # diagonals; keep one to anchor the centre to the origin below.
                if diagonal_id is None:
                    diagonal_id = adapter._register_sketch_entity("Line", segment)
                continue
            entity_id = adapter._register_sketch_entity("Line", segment)
            start = _read_member(segment, "GetStartPoint2")
            end = _read_member(segment, "GetEndPoint2")
            dx = (
                float(_read_member(end, "X")) - float(_read_member(start, "X"))
            ) * 1000.0
            dz = (
                float(_read_member(end, "Y")) - float(_read_member(start, "Y"))
            ) * 1000.0
            edges.append((entity_id, dx, dz))
        if len(edges) != 4:
            raise RuntimeError(
                f"{label}: center rectangle returned {len(edges)} profile edges, expected 4"
            )
        horizontal = next(
            (row for row in edges if abs(row[1]) > 1e-9 and abs(row[2]) < 1e-9),
            None,
        )
        vertical = next(
            (row for row in edges if abs(row[2]) > 1e-9 and abs(row[1]) < 1e-9),
            None,
        )
        if horizontal is None or vertical is None:
            raise RuntimeError(
                f"{label}: native center rectangle has no orthogonal edge pair"
            )
        await dimension_between(
            adapter,
            f"{horizontal[0]}.start",
            f"{horizontal[0]}.end",
            "horizontal_distance",
            abs(horizontal[1]),
            f"{label} width",
        )
        await dimension_between(
            adapter,
            f"{vertical[0]}.start",
            f"{vertical[0]}.end",
            "vertical_distance",
            abs(vertical[2]),
            f"{label} depth",
        )
        # Deterministically anchor the rectangle centre to the origin.
        # SolidWorks only auto-adds the centre->origin coincidence when the
        # "add constraints to sketched rectangles" system option
        # (swSketchAddConstToRectEntity) is ON. It is OFF on some seats, which
        # leaves the native centre rectangle free to translate (under_defined)
        # even with width+depth dims — the build must not depend on a per-seat
        # UI toggle. If the profile is not already fully defined, pin one
        # construction diagonal's midpoint to the origin. Idempotent: skipped
        # when the native anchor already fixed it, so it never over-defines the
        # seat where the option is on.
        rect_state = await adapter.check_sketch_fully_defined()
        already_defined = bool(
            rect_state.is_success
            and rect_state.data
            and rect_state.data.get("definition_state") == "fully_defined"
        )
        if not already_defined:
            _telemetry.warn(
                f"{label}: native centre rectangle under-defined after width+depth "
                "dims — the seat's 'add constraints to sketched rectangles' option "
                "(swSketchAddConstToRectEntity) is off, so no centre->origin anchor "
                "was auto-added; pinning one construction diagonal's midpoint to the "
                "origin explicitly."
            )
            if diagonal_id is not None:
                check(
                    f"{label} centre -> origin",
                    await adapter.add_sketch_constraint(
                        "origin", diagonal_id, "midpoint"
                    ),
                )
        if dims is not None:
            dims.record(name_width, drive_width)
            dims.record(name_depth, drive_depth)
        return [entity_id for entity_id, _, _ in edges]

    points = [
        (-half_x, -half_z),
        (half_x, -half_z),
        (half_x, half_z),
        (-half_x, half_z),
    ]
    edges = await add_line_chain(adapter, points)
    sketch_mgr = adapter.currentSketchManager
    previous_add_to_db = bool(sketch_mgr.AddToDB)
    sketch_mgr.AddToDB = True
    diagonals: list[str] = []
    try:
        for start, end in ((points[0], points[2]), (points[1], points[3])):
            result = await adapter.add_line(*start, *end)
            diagonal_id = check(f"add construction diagonal {label}", result)
            # ConstructionGeometry is declared on the base ISketchSegment, not the
            # derived ISketchLine the entity is bound as — rebind before the set.
            diagonal = _early_bound(
                adapter._sketch_entities[diagonal_id], "ISketchSegment"
            )
            diagonal.ConstructionGeometry = True
            diagonals.append(diagonal_id)
    finally:
        sketch_mgr.AddToDB = previous_add_to_db
    for edge, direction in zip(
        edges, ("horizontal", "vertical", "horizontal", "vertical"), strict=True
    ):
        check(
            f"{label} {direction} {edge}",
            await adapter.add_sketch_constraint(edge, None, direction),
        )
    check(
        f"{label} midpoint -> origin",
        await adapter.add_sketch_constraint("origin", diagonals[0], "midpoint"),
    )
    await dimension_between(
        adapter,
        f"{edges[0]}.start",
        f"{edges[0]}.end",
        "horizontal_distance",
        2.0 * half_x,
        f"{label} width",
    )
    await dimension_between(
        adapter,
        f"{edges[1]}.start",
        f"{edges[1]}.end",
        "vertical_distance",
        2.0 * half_z,
        f"{label} depth",
    )
    if dims is not None:
        dims.record(name_width, drive_width)
        dims.record(name_depth, drive_depth)
    return edges


async def add_line_chain(
    adapter: Any, points: list[tuple[float, float]], close: bool = True
) -> list[str]:
    """Draw consecutive lines through ``points`` and return their entity IDs.

    The raw segments are placed with sketch inference SUPPRESSED
    (``SketchManager.AddToDB``); the horizontal/vertical/dimension relations
    are added afterwards by :func:`define_rectilinear_chain` /
    :func:`define_polygon_chain` (or the caller's explicit constraints). Drawing
    through the inference engine is nondeterministic and purely harmful here: it
    snaps a not-quite-axis-parallel segment to an auto relation, or collapses a
    vertex onto a neighbour/axis -- the documented cause of vanished hex
    vertices (a 2/3-volume head) and intermittent "failed to create line" when a
    segment runs near existing geometry. Exact-coordinate endpoints still merge
    in the sketch DB, so the loop closes regardless. The prior ``AddToDB`` state
    is restored, so the manual :func:`set_sketch_direct_db` wraps some callers
    still use nest harmlessly (they are no longer required)."""
    vertices = list(points) + ([points[0]] if close else [])
    sketch_mgr = adapter.currentSketchManager
    prev_add_to_db = bool(sketch_mgr.AddToDB)
    sketch_mgr.AddToDB = True
    ids: list[str] = []
    try:
        for (x1, y1), (x2, y2) in zip(vertices, vertices[1:], strict=False):
            result = await adapter.add_line(x1, y1, x2, y2)
            ids.append(check(f"add_line ({x1:g},{y1:g})->({x2:g},{y2:g})", result))
    finally:
        sketch_mgr.AddToDB = prev_add_to_db
    return ids


def _dim_cursor(
    dims: "SketchDims | None",
    names: list[str | None] | None,
    drives: list[str | None] | None,
) -> "Callable[[], None]":
    """Return a zero-arg ``rec()`` that records the next (name, drive) into
    ``dims`` in emission order, pulling sequentially from ``names``/``drives``
    (``None`` once exhausted). The caller calls it once per dim it emits, in the
    exact order emitted; :meth:`SketchDims.apply` then count-asserts the total
    against the feature's real display-dim count, so a miscount fails loud."""
    _names = list(names) if names else []
    _drives = list(drives) if drives else []
    state = {"k": 0}

    def rec() -> None:
        k = state["k"]
        if dims is not None:
            nm = _names[k] if k < len(_names) else None
            dv = _drives[k] if k < len(_drives) else None
            dims.record(nm, dv)
        state["k"] = k + 1

    return rec


def _record_origin_anchor_cursor(rec: "Callable[[], None]", x: float, y: float) -> None:
    """Drive ``rec`` once per dim :func:`anchor_point_to_origin` emits for
    ``(x, y)`` -- none on the origin, one on an axis (x then y), two in general
    -- so a cursor-based record stays aligned with the anchor's emission."""
    sx = 0.0 if abs(x) < 1e-9 else x
    sy = 0.0 if abs(y) < 1e-9 else y
    if sx != 0.0:
        rec()
    if sy != 0.0:
        rec()


@_telemetry.traced("sketch.rect_chain", label_param="label")
async def define_rectilinear_chain(
    adapter: Any,
    lines: list[str],
    points: list[tuple[float, float]],
    anchor: int = 0,
    label: str = "chain",
    *,
    dims: "SketchDims | None" = None,
    names: list[str | None] | None = None,
    drives: list[str | None] | None = None,
) -> None:
    """Fully define a CLOSED axis-parallel line chain semantically.

    ``lines``/``points`` are :func:`add_line_chain` output and input (line i
    runs points[i] -> points[i+1], wrapping). Every segment gets its
    horizontal/vertical relation; every segment except the LAST one of each
    direction gets a driving point-pair distance dim — closure makes one dim
    per direction redundant, and adding it over-defines the sketch. Vertex
    ``anchor`` is the chain's single origin anchor (one-anchor rule, see the
    module docstring).

    Self-naming: pass ``dims`` plus ``names`` / ``drives`` lists aligned to the
    EMISSION ORDER -- the per-segment distance dims in line order (skipping the
    one redundant segment per direction), THEN the anchor dims (x, then z; only
    the non-zero ones). Unnamed slots (``None`` or past the list end) stay
    auto-named/undriven. For an origin-centred rectangle prefer
    :func:`define_centered_rectangle`, which names width/depth/corner directly.
    """
    n = len(lines)
    if n != len(points):
        raise ValueError(
            f"{label}: need a closed chain (lines {n} != points {len(points)})"
        )
    rec = _dim_cursor(dims, names, drives)
    directions: list[str] = []
    for i, line in enumerate(lines):
        (x1, y1), (x2, y2) = points[i], points[(i + 1) % n]
        if y1 == y2 and x1 != x2:
            direction = "horizontal"
        elif x1 == x2 and y1 != y2:
            direction = "vertical"
        else:
            raise ValueError(
                f"{label}: segment {line} ({x1:g},{y1:g})->({x2:g},{y2:g}) "
                "is not axis-parallel"
            )
        directions.append(direction)
        check(
            f"{label} {direction} {line}",
            await adapter.add_sketch_constraint(line, None, direction),
        )
    last = {
        d: max(i for i, d2 in enumerate(directions) if d2 == d) for d in set(directions)
    }
    for i, (line, direction) in enumerate(zip(lines, directions, strict=True)):
        if last[direction] == i:
            continue  # the closure equation supplies this span
        (x1, y1), (x2, y2) = points[i], points[(i + 1) % n]
        if direction == "horizontal":
            kind, span = "horizontal_distance", abs(x2 - x1)
        else:
            kind, span = "vertical_distance", abs(y2 - y1)
        await dimension_between(
            adapter, f"{line}.start", f"{line}.end", kind, span, f"{label} {line}"
        )
        rec()
    await anchor_point_to_origin(
        adapter, f"{lines[anchor]}.start", *points[anchor], f"{label} anchor"
    )
    _record_origin_anchor_cursor(rec, *points[anchor])


def _read_member(obj: Any, name: str) -> Any:
    """Read a COM accessor that pywin32 may expose as a method or property."""
    member = getattr(obj, name, None)
    if not callable(member):
        return member
    try:
        return member()
    except Exception:
        return member


def feature_name_by_type(adapter: Any, type_name: str) -> str:
    """Return the name of the last feature whose GetTypeName2 matches.

    Recovers features whose creator call returns None on success (e.g. the
    raw-COM ``InsertHelix`` stopgap used until Phase 3 lands), by walking the
    feature tree with method flagging.
    """
    from solidworks_mcp.adapters import sw_type_info

    model = sw_type_info.early_bound_or_flag(
        adapter.currentModel, "IModelDoc2", "FirstFeature"
    )
    found = ""
    feat = _read_member(model, "FirstFeature")
    for _ in range(5000):
        if not feat:
            break
        # Flag only the two methods the walk calls (the c992057 pattern):
        # full IFeature flagging is a GetIDsOfNames round-trip per method
        # name per feature, uncached across walks (fresh CDispatch each
        # GetNextFeature), which taxed every extrude_at_offset with an
        # O(features) flag storm. GetTypeName2 must stay method-dispatched
        # or the comparison below silently never matches.
        feat = sw_type_info.early_bound_or_flag(
            feat, "IFeature", "GetTypeName2", "GetNextFeature"
        )
        try:
            if _read_member(feat, "GetTypeName2") == type_name:
                found = str(_read_member(feat, "Name"))
        except Exception:
            pass
        feat = _read_member(feat, "GetNextFeature")
    return found


def blank_sketch(adapter: Any, sketch_name: str) -> None:
    """Hide (blank) a sketch so it stops rendering in assemblies.

    Unabsorbed sketches default to SHOWN and render in every assembly
    instance (caught as floating tick rows above the top frame: 20 helix
    seed circles + 20 orphan pin-hole circles, one per channel station).
    """
    from solidworks_mcp.adapters.pywin32_adapter import null_callout

    model = adapter.currentModel
    model.ClearSelection2(True)
    selected = model.Extension.SelectByID2(
        sketch_name, "SKETCH", 0, 0, 0, False, 0, null_callout(), 0
    )
    if not selected:
        raise RuntimeError(f"blank_sketch: cannot select sketch {sketch_name!r}")
    model.BlankSketch()
    model.ClearSelection2(True)
    _telemetry.success(f"blanked sketch {sketch_name}")


def set_sketch_direct_db(adapter: Any, enabled: bool) -> None:
    """Toggle ``SketchManager.AddToDB`` around non-axis-parallel geometry.

    With inferencing on (the default), a nearly-horizontal sloped line gets
    snapped to an automatic ``horizontal`` relation — a tapered revolve
    profile silently flattens into a rectangle (caught live on the crank
    pin: the frustum came back as a perfect cylinder; on the channel lever
    a step profile picked up redundant auto-relations and went straight to
    over-defined). ``AddToDB=True`` bypasses inference relations; exactly
    coincident endpoints still merge in the sketch DB (proven live: the
    pin chain closed and defined through fixed neighbours).
    """
    manager = adapter.currentSketchManager
    previous = adapter._attempt(lambda: bool(_read_member(manager, "AddToDB")), default=None)
    manager.AddToDB = enabled
    # AddToDB is SESSION state on a seat that outlives this leaf, and no user
    # preference reflects it, so the transition is recorded: a leaf that dies
    # between an ``enabled=True`` and its matching ``False`` hands the next leaf
    # on this seat a different authoring mode with nothing on disk to show it.
    _telemetry.event(
        "seat.sketch_add_to_db", enabled=enabled, previous=_scalar(previous)
    )
    if enabled and previous:
        # Already ON before this build turned it on: nothing in a healthy
        # sequence leaves it that way, so the seat carried it in from a leaf
        # that died between its True and its matching False.
        _telemetry.warn(
            "sketch AddToDB was already True before this build set it -- a "
            "previous leaf on this seat left its session state behind",
            add_to_db=enabled,
        )
    _telemetry.success(f"sketch AddToDB = {enabled} (was {previous})")


@_telemetry.traced("check.volume", label_param="label")
async def volume_check(adapter: Any, label: str, expected: float, tol: float) -> float:
    """Assert the part volume (mm^3) and return it."""
    mass = await adapter.get_mass_properties()
    if not mass.is_success:
        raise RuntimeError(f"{label}: get_mass_properties failed: {mass.error}")
    volume = float(mass.data.volume)
    if abs(volume - expected) > tol:
        raise RuntimeError(
            f"{label}: volume {volume:.1f} mm^3, expected {expected:.1f} "
            f"(+/- {tol:.1f})"
        )
    _telemetry.success(f"{label}: volume {volume:.1f} mm^3 (analytic {expected:.1f})")
    return volume


@_telemetry.traced("feature.extrude")
def extrude_at_offset(
    adapter: Any,
    depth: float,
    offset: float,
    flip: bool = False,
    *,
    merge_result: bool = True,
) -> str:
    """Boss-extrude the last exited sketch starting at an offset from its plane.

    Raw-COM stopgap (``FeatureExtrusion3`` with ``T0=swStartOffset``) until
    Phase 3 reference geometry lands -- the adapter's ``create_extrusion``
    only starts at the sketch plane. ``depth``/``offset`` are millimetres;
    ``flip=True`` mirrors both the offset and the extrude direction to the
    other side of the sketch plane (legacy SummingLever.cs edge-rib call).
    Returns the new feature name.
    """
    from solidworks_mcp.adapters.pywin32_adapter import null_callout

    sketch_name = feature_name_by_type(adapter, "ProfileFeature")
    if not sketch_name:
        raise RuntimeError("extrude_at_offset: no sketch found to consume")
    model = adapter.currentModel
    model.ClearSelection2(True)
    selected = model.Extension.SelectByID2(
        sketch_name, "SKETCH", 0, 0, 0, False, 0, null_callout(), 0
    )
    if not selected:
        raise RuntimeError(f"extrude_at_offset: cannot select sketch {sketch_name!r}")
    feature = model.FeatureManager.FeatureExtrusion3(
        True,  # Sd: single direction
        False,  # Flip side to cut
        flip,  # Dir: flip extrude direction
        0,  # T1: swEndCondBlind
        0,  # T2
        depth / 1000.0,  # D1
        0.0,  # D2
        False,
        False,  # Dchk1/2
        False,
        False,  # Ddir1/2
        0.0,
        0.0,  # Dang1/2
        False,
        False,  # OffsetReverse1/2
        False,
        False,  # TranslateSurface1/2
        merge_result,  # Merge
        False,  # UseFeatScope
        True,  # UseAutoSelect
        3,  # T0: swStartOffset
        offset / 1000.0,  # StartOffset
        flip,  # FlipStartOffset
    )
    model.ClearSelection2(True)
    if feature is None:
        raise RuntimeError("extrude_at_offset: FeatureExtrusion3 returned None")
    name = str(_read_member(feature, "Name"))
    _telemetry.success(
        f"extrude_at_offset {sketch_name} @ {'-' if flip else '+'}{offset:g} -> {name}"
    )
    return name


# STL export user-preferences (swUserPreferenceIntegerValue / Toggle ids,
# swconst R2026x) -- shared with export_models.py so a build-time part STL and
# the render-cache STL are byte-identical: a fine BINARY mesh in MILLIMETRES,
# left at the model origin. stl_bbox_mm parses exactly this.
PREF_STL_QUALITY = 78  # swSTLQuality -> 2 = fine
PREF_STL_UNITS = 211  # swExportStlUnits -> 0 = swMM
TOGGLE_STL_BINARY = 69  # swSTLBinaryFormat
TOGGLE_STL_ONE_FILE = 72  # swSTLComponentsIntoOneFile
TOGGLE_STL_NO_TRANSLATE = 71  # swSTLDontTranslateToPositive: keep model origin
TOGGLE_STL_SHOW_INFO = 70  # swSTLShowInfoOnSave: the per-file "Save <name>.STL?" modal

# ---------------------------------------------------------------------------
# Process-global SolidWorks preferences: DECLARED baselines, not observed ones
#
# The defect class this replaces: mutate a process-global preference, capture
# the value that happened to be there, restore it in a ``finally``. A leaf that
# dies inside the block strands the seat with the mutated value -- and our OWN
# watchdog exits (86/87/88) are ``os._exit``, which skips ``finally`` BY
# CONSTRUCTION, so this is not a hypothetical. The next run on that seat then
# captures the stranded value as "the original" and faithfully restores it
# forever: self-perpetuating, deterministic per seat, random-looking across a
# fleet -- exactly the signature of the 2026-09-17 "transient" leaf.
#
# Two shapes, one implementation each, and NO observed-value restore anywhere:
#
# * :func:`enforce_preferences` -- the family whose required state IS the
#   baseline (STL/STEP export). Nothing restores anything, so nothing can be
#   stranded; drift found at entry is reported, not inherited.
# * :func:`preference_override` -- a family that must be temporarily different
#   (e.g. suppressing sketch inference). Restores the DECLARED baseline, and is
#   DEPTH-COUNTED so a nested block cannot restore mid-flight for the outer one.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PreferenceSpec:
    """A named family of SolidWorks user preferences and its declared baseline.

    Keys are swconst MEMBER NAMES (resolved at runtime -- ids move between
    releases, names do not) or raw ids for the export families that predate this
    rule and already carry the member name in a comment. ``baseline_*`` is the
    state a seat is left in; when it equals the applied state the family is
    simply enforced and there is nothing to restore.

    The mappings are wrapped read-only at construction: ``frozen=True`` alone
    stops ``spec.toggles = {}`` but not ``spec.toggles[9] = False``, and the
    entire argument for this class is that the baseline is a DECLARED constant
    -- one a recipe cannot quietly accumulate into.
    """

    label: str
    integers: Mapping[str | int, int] = field(default_factory=dict)
    toggles: Mapping[str | int, bool] = field(default_factory=dict)
    baseline_integers: Mapping[str | int, int] = field(default_factory=dict)
    baseline_toggles: Mapping[str | int, bool] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("integers", "toggles", "baseline_integers", "baseline_toggles"):
            object.__setattr__(
                self, name, MappingProxyType(dict(getattr(self, name)))
            )


# SHOW_INFO -> False: every part build now exports an STL, so leaving the modal on
# would block an unattended `doit` run on the first export (cut_release.py disables
# it for the same reason; codex review #12).
#
# Declared baseline == applied state: every STL this repo writes is a fine binary
# mesh in millimetres at the model origin (``stl_bbox_mm`` parses exactly that),
# and no build step wants any other value, so the seat is deliberately LEFT in
# this state instead of being handed back a value an earlier crash invented.
STL_EXPORT_PREFERENCES = PreferenceSpec(
    label="stl-export",
    integers={PREF_STL_QUALITY: 2, PREF_STL_UNITS: 0},
    toggles={
        TOGGLE_STL_BINARY: True,
        TOGGLE_STL_ONE_FILE: True,
        TOGGLE_STL_NO_TRANSLATE: True,
        TOGGLE_STL_SHOW_INFO: False,
    },
)


def _preference_key(adapter: Any, key: str | int) -> int | None:
    """A raw id passes through; a member name is resolved through swconst."""
    if isinstance(key, int) and not isinstance(key, bool):
        return key
    return _preference_id(adapter, str(key))


def _read_preferences(adapter: Any, spec: PreferenceSpec) -> dict[str | int, Any]:
    """Current seat values for every key in ``spec`` (missing ones omitted)."""
    sw = adapter.swApp
    current: dict[str | int, Any] = {}
    for keys, accessor, cast in (
        (spec.integers or spec.baseline_integers, "GetUserPreferenceIntegerValue", int),
        (spec.toggles or spec.baseline_toggles, "GetUserPreferenceToggle", bool),
    ):
        read = getattr(sw, accessor, None)
        for key in keys:
            pref = _preference_key(adapter, key)
            if pref is None or read is None:
                continue
            value = adapter._attempt(lambda p=pref, r=read: r(p), default=None)
            if value is not None:
                current[key] = cast(value)
    return current


def _write_preferences(
    adapter: Any,
    spec: PreferenceSpec,
    integers: Mapping[str | int, int],
    toggles: Mapping[str | int, bool],
) -> dict[str, Any]:
    """Write ``integers``/``toggles``, then VERIFY by read-back.

    A refused write is the whole failure mode being closed here, so it is
    reported rather than assumed: ``SetUserPreference*`` returns nothing useful
    on a preference the seat declines (an unknown id, or one a policy locks).

    Reported, never RAISED: some preferences are write-ignored by design
    (``swSketchAddConstToRectEntity`` reads fine and silently drops the write
    because it is per-document), and a family whose recipe no longer depends on
    the write succeeding is degraded-but-correct when it does. Raising here would
    turn a cosmetic seat-hygiene problem into a build outage.
    """
    sw = adapter.swApp
    refused: dict[str, Any] = {}
    for values, writer, reader, cast in (
        (integers, "SetUserPreferenceIntegerValue", "GetUserPreferenceIntegerValue", int),
        (toggles, "SetUserPreferenceToggle", "GetUserPreferenceToggle", bool),
    ):
        write = getattr(sw, writer, None)
        read = getattr(sw, reader, None)
        for key, wanted in values.items():
            pref = _preference_key(adapter, key)
            if pref is None or write is None:
                refused[str(key)] = "unresolved"
                continue
            adapter._attempt(lambda p=pref, v=wanted, w=write: w(p, v), default=None)
            if read is None:
                continue
            got = adapter._attempt(lambda p=pref, r=read: r(p), default=None)
            if got is None or cast(got) != wanted:
                refused[str(key)] = f"wanted {wanted}, seat reports {got!r}"
    return refused


def _report_preference_state(
    spec: PreferenceSpec,
    stage: str,
    drift: Mapping[str | int, tuple[Any, Any]],
    refused: dict[str, Any],
) -> None:
    """One span event per stage (never one per preference), and a WARN only when
    the seat actually disagreed -- drift is the evidence a seat was stranded."""
    _telemetry.event(
        f"seat.preferences.{stage}",
        family=spec.label,
        drift=json.dumps({str(k): list(v) for k, v in drift.items()}, sort_keys=True),
        refused=json.dumps(refused, sort_keys=True),
    )
    if drift:
        _telemetry.warn(
            f"[seat] {spec.label}: {len(drift)} preference(s) differed from the "
            f"declared baseline at {stage} "
            + ", ".join(
                f"{key}={actual!r} (want {wanted!r})"
                for key, (actual, wanted) in sorted(drift.items(), key=repr)
            )
            + " -- a seat left mutated by an earlier run, now corrected",
            family=spec.label,
            stage=stage,
        )
    if refused:
        _telemetry.warn(
            f"[seat] {spec.label}: the seat refused {len(refused)} preference "
            f"write(s) at {stage}: {refused}",
            family=spec.label,
            stage=stage,
        )


def _drift_against(
    current: Mapping[str | int, Any],
    integers: Mapping[str | int, int],
    toggles: Mapping[str | int, bool],
) -> dict[str | int, tuple[Any, Any]]:
    """Keys whose read value differs from what this family declares."""
    wanted: dict[str | int, Any] = {**integers, **toggles}
    return {
        key: (current[key], value)
        for key, value in wanted.items()
        if key in current and current[key] != value
    }


def enforce_preferences(adapter: Any, spec: PreferenceSpec) -> dict[str | int, Any]:
    """Assert ``spec``'s required state on the seat; return the drift corrected.

    For families whose required state IS the declared baseline: there is no
    save and no restore, so no leaf -- however it dies -- can strand a value,
    and the next leaf cannot mistake a stranded value for "the original".
    Ambient state is never inherited: whatever the seat carried in is compared
    against the declaration, reported, and overwritten.
    """
    current = _read_preferences(adapter, spec)
    drift = _drift_against(current, spec.integers, spec.toggles)
    refused = _write_preferences(adapter, spec, spec.integers, spec.toggles)
    _report_preference_state(spec, "enforce", drift, refused)
    return {key: actual for key, (actual, _wanted) in drift.items()}


# Nesting depth per preference family (see preference_override). Module-global
# because the seat is: two nested overrides of the same family share one seat,
# whatever objects hold them.
_override_depth: dict[str, int] = {}


@contextlib.contextmanager
def preference_override(adapter: Any, spec: PreferenceSpec) -> Iterator[None]:
    """Apply ``spec``'s state for the duration of the block, then restore its
    DECLARED baseline -- once, on the outermost exit.

    Depth counting is load-bearing, not defensive: restoring a declared baseline
    from a NESTED block is worse than the old observed-value latch, because the
    inner exit would restore the baseline mid-flight while the outer block is
    still relying on the override. The innermost blocks therefore do nothing on
    entry or exit, and only the outermost restores.

    This still cannot survive ``os._exit`` (nothing can), but the damage is now
    bounded: the stranded value is a DECLARED one, the next entry reports the
    drift it finds, and the restore target never depends on what an earlier
    crash left behind.
    """
    depth = _override_depth.get(spec.label, 0)
    _override_depth[spec.label] = depth + 1
    try:
        if depth == 0:
            current = _read_preferences(adapter, spec)
            drift = _drift_against(
                current, spec.baseline_integers, spec.baseline_toggles
            )
            refused = _write_preferences(adapter, spec, spec.integers, spec.toggles)
            _report_preference_state(spec, "override", drift, refused)
        yield
    finally:
        # Decrement FIRST and unconditionally: if the restore write throws while
        # unwinding, a depth left above zero would pin this family for the rest
        # of the session -- every later block silently applying nothing and
        # restoring nothing. That is the latch again, just a subtler one.
        _override_depth[spec.label] = depth
        if depth == 0:
            refused = _write_preferences(
                adapter, spec, spec.baseline_integers, spec.baseline_toggles
            )
            _report_preference_state(spec, "restore", {}, refused)


@_telemetry.traced("export.stl")
async def export_part_stl(adapter: Any, out_path: Path) -> None:
    """Write the active part's fine binary STL (mm, model origin) to ``out_path``.

    The assembly build reads these via ``stl_bbox_mm`` to place each
    bbox-mirrored part, so a part build must emit its STL alongside the SLDPRT --
    ``export_models.py`` only refreshes the render cache and can't bootstrap a
    from-empty assembly (its part list is manifest-driven and otherwise needs an
    already-built assembly to scan).

    The export preferences are ENFORCED, not saved-and-restored (see
    :func:`enforce_preferences`). The previous version captured the seat's
    OBSERVED values and restored them in a ``finally``: any death inside the
    block -- including our own watchdog ``os._exit`` paths, which skip ``finally``
    by construction -- stranded the mutated values on the seat, and the next run
    then captured the stranded value as "the original" and restored it forever.
    Nothing in this repo wants any other STL configuration, so the declared state
    is asserted and deliberately left in place, which makes stranding impossible
    rather than unlikely.
    """
    enforce_preferences(adapter, STL_EXPORT_PREFERENCES)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # Delete any prior STL first so a failed SaveAs3 (locked target, export
    # error) cannot leave a stale file that the existence check below would
    # accept as a fresh export (codex review #10). SaveAs3's return is not a
    # reliable success flag here (it yields 0 on a successful write), so the
    # post-delete "file exists" check is the real gate.
    if out_path.exists():
        out_path.unlink()
    rc = adapter._attempt(lambda: adapter.currentModel.SaveAs3(str(out_path), 0, 0))
    if not out_path.exists():
        raise RuntimeError(f"STL export produced no file (SaveAs3 rc={rc!r}): {out_path}")
    _telemetry.success(
        f"export STL -> {out_path.name} ({out_path.stat().st_size / 1e6:.1f} MB)"
    )


@_telemetry.traced("export.part_images", label_param="part_name")
async def save_part_and_images(
    adapter: Any, part_name: str, views: Iterable[str] = DEFAULT_VIEWS
) -> dict[str, str]:
    """Save the part to ``cad/out/sldprt``, its STL to ``cad/out/stl`` (the
    assembly build reads it for mirror placement), and PNG views to
    ``cad/out/png``."""
    # Recorded BEFORE anything touches the camera: this runs at the end of
    # authoring, and set_isometric_view below (like export_image further down) is
    # the first thing in the whole build path that moves the view, so this is the
    # last moment at which the screen-space state the sketches were authored
    # under can still be read. A SUCCESS has to record it too -- otherwise a good
    # run and a bad one cannot be compared (see record_authoring_context).
    record_authoring_context(adapter, part_name)
    OUT_SLDPRT.mkdir(parents=True, exist_ok=True)
    part_path = (OUT_SLDPRT / f"{part_name}.SLDPRT").resolve()
    set_isometric_view(adapter)  # save on isometric so the .SLDPRT opens isometric
    check(f"save_file -> {part_path}", await adapter.save_file(str(part_path)))

    png_dir = OUT_PNG / part_name
    png_dir.mkdir(parents=True, exist_ok=True)
    views = list(views)
    _prune_stale_part_views(png_dir, part_name, views)
    apply_block_tolerances(adapter)
    properties = part_properties(part_name)
    apply_custom_properties(adapter, properties)
    # The drawing template's PART cell resolves the linked model's document
    # summary Title, not its same-named custom property. Keep both identities
    # sourced from part_properties so a registry title override cannot split.
    apply_summary_info(adapter, title=properties["Title"])
    check(
        f"re-save with properties -> {part_path}",
        await adapter.save_file(str(part_path)),
    )

    stl_path = (OUT_STL / f"{part_name}.STL").resolve()
    await export_part_stl(adapter, stl_path)

    artefacts = {"part": str(part_path), "stl": str(stl_path)}
    for view in views:
        img_path = (png_dir / f"{part_name}_{view}.png").resolve()
        check(
            f"export_image {view}",
            await adapter.export_image(
                {
                    "file_path": str(img_path),
                    "format_type": "png",
                    "width": 1600,
                    "height": 1000,
                    "view_orientation": view,
                }
            ),
        )
        artefacts[view] = str(img_path)
    return artefacts


def _prune_stale_part_views(
    png_dir: Path, part_name: str, views: Iterable[str]
) -> None:
    """Remove obsolete routine views without deleting configuration renders."""
    requested = {f"{part_name}_{view}.png" for view in views}
    for view in _ROUTINE_PART_VIEWS:
        stale = png_dir / f"{part_name}_{view}.png"
        if stale.name not in requested:
            stale.unlink(missing_ok=True)


def active_configuration_name(adapter: Any, model: Any = None) -> str:
    """Return the active configuration name without switching or rebuilding."""
    model = model or adapter.currentModel
    manager = _read_member(model, "ConfigurationManager")
    active = (
        _read_member(manager, "ActiveConfiguration") if manager is not None else None
    )
    return str(_read_member(active, "Name") or "") if active is not None else ""


_SW_CUSTOM_TEXT = 30  # swCustomInfoType_e.swCustomInfoText
_SW_PROP_REPLACE = 2  # swCustomPropertyAddOption_e.swCustomPropertyReplaceValue


@functools.lru_cache(maxsize=1)
def _git_executable() -> str:
    """Absolute Git executable used by fixed, repository-internal commands."""
    executable = shutil.which("git")
    if executable is None:
        raise FileNotFoundError("git executable not found on PATH")
    return str(Path(executable).resolve())


@functools.lru_cache(maxsize=1)
def _git_sha() -> str:
    """Short HEAD sha (+ '-dirty'), for a reproducible Generator stamp.

    Deterministic per source state — no wall-clock — so a rebuild from the same
    commit writes the same property (see Part D determinism decision).
    """
    import subprocess

    try:
        sha = subprocess.run(  # noqa: S603 -- resolved Git; fixed internal argv
            [_git_executable(), "rev-parse", "--short", "HEAD"],
            cwd=str(CAD_ROOT),
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        dirty = subprocess.run(  # noqa: S603 -- resolved Git; fixed internal argv
            [_git_executable(), "status", "--porcelain"],
            cwd=str(CAD_ROOT),
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        return f"{sha}{'-dirty' if dirty else ''}"
    except Exception:  # noqa: BLE001 -- not in a git checkout / no git
        return "unknown"


def _build_id() -> str:
    """``<next release>[-dirty]`` -- the release designator, marked when dirty.

    The title block's REV cell is the formal release designator
    (``release.yaml``); a sheet also stamps this on itself
    (``$PRP:{BUILD_ID}``) so a print made from an uncommitted working tree can
    be told from a clean release print by eye.  Source-derived like
    :func:`_git_sha` (no wall clock) and deliberately history-free: only the
    working-tree state is read, never a tag, a commit count or a sha, so a
    shallow checkout -- what every farm leaf clones -- stamps exactly what the
    same commit stamps in a full clone.  Stamped only when a drawing task
    actually runs -- git state is in no cache key or file_dep, so a commit
    never rebuilds anything; a restored sheet keeps the id of the build that
    made it.
    """
    import subprocess

    import _config

    try:
        dirty = subprocess.run(  # noqa: S603 -- resolved Git; fixed internal argv
            [_git_executable(), "status", "--porcelain"],
            cwd=str(CAD_ROOT),
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            "cannot determine Git working-tree state for the build id"
        ) from exc
    return f"{_config.release_revision()}{'-dirty' if dirty else ''}"


def _git_commit_year() -> str:
    """Year of the HEAD commit, for the title block's copyright line.

    Same determinism rule as :func:`_git_sha`: derived from the source state,
    never the wall clock, so a rebuild from the same commit stamps the same
    year and a cache restore cannot disagree with a fresh build.  Outside a
    git checkout there is no source-derived year, so fail loud rather than
    stamp a guess into every part.
    """
    import subprocess

    date = subprocess.run(  # noqa: S603 -- resolved Git; fixed internal argv
        [_git_executable(), "log", "-1", "--format=%cs"],
        cwd=str(CAD_ROOT),
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    year = date[:4]
    if not (len(year) == 4 and year.isdigit()):
        raise RuntimeError(f"HEAD commit date is not ISO-dated: {date!r}")
    return year


def part_properties(part_name: str) -> dict[str, str]:
    """SolidWorks custom properties for ``part_name`` from the parts registry.

    ``Revision`` is the next compact release number from ``release.yaml``;
    per-part registry revisions are retained only as historical source data and
    never override the release identity stamped into shipped CAD.
    """
    import _config

    props: dict[str, str] = {
        "Title": part_name,
        "Revision": _config.release_revision(),
        "Generator": f"harmonic-analyzer @ {_git_sha()}",
        # The title block's "(c) <year> <holder>" line reads this via
        # $PRPSHEET:{COPYRIGHT_YEAR}; SolidWorks has no built-in year-only
        # property and its date built-ins change on every rebuild.
        "COPYRIGHT_YEAR": _git_commit_year(),
    }
    # Title-block general tolerances (title_block.yaml) — read by the drawing
    # template's title block via $PRPSHEET, so EVERY part carries them,
    # registered in the parts registry or not.
    props["TOL_LIN_X"] = str(_config.title_block("linear_1pl")["display"])
    props["TOL_LIN_XX"] = str(_config.title_block("linear_2pl")["display"])
    props["TOL_LIN_XXX"] = str(_config.title_block("linear_3pl")["display"])
    props["TOL_ANG"] = str(_config.title_block("angular")["display"])
    props["TOL_SURFACE"] = str(_config.title_block("surface")["display"])
    # Edge-break and thread-class rows (2026-09 template): the sheet-format
    # notes are $PRPSHEET links, so the numbers live here, not in the DRWDOT.
    props["TOL_EDGE_BREAK_R"] = str(_config.title_block("edge_break")["display_r"])
    props["TOL_CHAMFER_MAX"] = str(_config.title_block("edge_break")["display_chamfer"])
    props["THREAD_TYPE"] = str(_config.title_block("thread")["type"])
    props["THREAD_CLASS"] = str(_config.title_block("thread")["class"])
    # DRILLED HOLES general tolerance (unilateral); the title block's DRILLED
    # HOLES row reads these via $PRPSHEET and supplies the +/- around them.
    props["TOL_HOLE_MINUS"] = str(_config.title_block("drilled_hole")["display_minus"])
    props["TOL_HOLE_PLUS"] = str(_config.title_block("drilled_hole")["display_plus"])
    # Per-channel stretched springs (build_channel_assembly) are length variants of
    # the registered base part -- they inherit its material / tolerance / fit so
    # the tolerance audit stays clean without 10 redundant registry rows.
    registry_name = part_name
    if part_name.startswith("channel-spring-installed-stretch"):
        registry_name = "channel-spring-installed"
    try:
        reg = _config.parts(registry_name)
    except KeyError:
        return props
    props["Title"] = str(reg.get("title") or part_name)
    field_map = {
        "Number": "number",
        "Material": "material",
        "Tolerance Class": "tolerance_class",
        "Fit Class": "fit_class",
        "Process": "process",
        "Confidence": "confidence",
    }
    for prop, key in field_map.items():
        if key in reg and reg[key] is not None:
            props[prop] = str(reg[key])
    return props


# DimXpert block-tolerance document properties (Tools > Options > Document
# Properties > DimXpert), ids extracted from swconst.tlb R2026x. Values from
# title_block.yaml — the same numbers the TOL_* custom properties display in
# the drawing title block.
_PREF_DIMXPERT_METHOD = 637  # swPartDimXpertToleranceMethod -> 0 = BlockTolerance
_PREF_TOL1_DECIMALS = 405  # swPartDimXpertLengthUnitTol1Decimals (get-only, see below)
_PREF_TOL2_DECIMALS = 406  # swPartDimXpertLengthUnitTol2Decimals (get-only, see below)
_PREF_TOL1_VALUE = 123  # swPartDimXpertLengthUnitTol1Value (meters)
_PREF_TOL2_VALUE = 124  # swPartDimXpertLengthUnitTol2Value (meters)
_PREF_ANGULAR_VALUE = (
    126  # swPartDimXpertAngularUnitTolValue (radians; get-only, see below)
)
_PREF_OPT_NONE = 0  # swDetailingNoOptionSpecified
_METERS_PER_INCH = 0.0254


@_telemetry.traced("part.block_tolerances")
def apply_block_tolerances(adapter: Any) -> None:
    """Stamp the title-block general tolerances as DimXpert block-tolerance doc
    properties on the active part, so the SLDPRT's MBD metadata matches what the
    drawing title block states.

    Probe-verified on this seat (3DEXPERIENCE R2026x, 2026-07-13): the method and
    the linear Tolerance 1/2 VALUES set fine, but the decimals prefs (405/406) and
    the angular value (126) reject every write (``SetUserPreference*`` returns
    False under both int encodings, options 0-3, before/after rebuild, on a saved
    doc) despite the API help documenting them settable — get-only in practice.
    The get-only prefs therefore ride the seat's default part TEMPLATE, which
    makes the template a build prerequisite: it must carry the wanted decimals
    split (Tol1=2dp, Tol2=3dp — the stock default) and the title-block angular
    value (set by hand in the .prtdot). This stamps what it can and RAISES on any
    failure — a rejected settable write OR get-only drift. Drift must fail, not
    warn: the template is not a cache-key input, so a drifted seat would publish
    parts whose DimXpert metadata disagrees with title_block.yaml into the shared
    remote cache under the same key as a correct seat.
    """
    import _config

    model = adapter.currentModel
    ext = _read_member(model, "Extension")
    lin2 = float(_config.title_block("linear_2pl")["value_in"]) * _METERS_PER_INCH
    lin3 = float(_config.title_block("linear_3pl")["value_in"]) * _METERS_PER_INCH
    ang = math.radians(float(_config.title_block("angular")["value_deg"]))
    sets = [
        (
            "DimXpert method=block",
            ext.SetUserPreferenceInteger,
            _PREF_DIMXPERT_METHOD,
            0,
        ),
        (
            "DimXpert tol1 (.xx) value",
            ext.SetUserPreferenceDouble,
            _PREF_TOL1_VALUE,
            lin2,
        ),
        (
            "DimXpert tol2 (.xxx) value",
            ext.SetUserPreferenceDouble,
            _PREF_TOL2_VALUE,
            lin3,
        ),
    ]
    for label, setter, pref, value in sets:
        if not adapter._attempt(
            lambda: setter(pref, _PREF_OPT_NONE, value), default=False
        ):
            raise RuntimeError(f"{label} write rejected (pref {pref})")
    _telemetry.success("DimXpert block tolerances stamped")
    drift = []
    if ext.GetUserPreferenceInteger(_PREF_TOL1_DECIMALS, _PREF_OPT_NONE) != 2:
        drift.append("tol1 decimals != 2")
    if ext.GetUserPreferenceInteger(_PREF_TOL2_DECIMALS, _PREF_OPT_NONE) != 3:
        drift.append("tol2 decimals != 3")
    got_ang = ext.GetUserPreferenceDouble(_PREF_ANGULAR_VALUE, _PREF_OPT_NONE)
    if abs(got_ang - ang) > 1e-9:
        drift.append(f"angular {math.degrees(got_ang):g}° != {math.degrees(ang):g}°")
    if drift:
        raise RuntimeError(
            "DimXpert block-tolerance drift on get-only prefs -- the seat's default "
            "part template must carry these (open the default .prtdot, set Document "
            "Properties > DimXpert accordingly, save), else this seat would publish "
            f"metadata-drifted parts into the shared cache: {'; '.join(drift)}"
        )


def apply_custom_properties(
    adapter: Any, props: dict[str, str], *, model: Any | None = None
) -> None:
    """Write file-level custom properties via the CustomPropertyManager, verified.

    The PyWin32 adapter exposes no property writer, so this drives raw COM
    (``IModelDocExtension.CustomPropertyManager("").Add3`` with replace), then
    reads each value back through ``GetCustomInfoValue`` and raises on mismatch
    — same fail-fast posture as the build's other gates. Empty values are skipped.
    ``model`` defaults to the active document; callers that repair a specific
    assembly may pass the explicit target document.
    """
    model = adapter.currentModel if model is None else model
    ext = _read_member(model, "Extension")
    mgr = adapter._attempt(lambda: ext.CustomPropertyManager(""), default=None)
    if mgr is None:
        raise RuntimeError("CustomPropertyManager unavailable")
    mgr = _early_bound(mgr, "ICustomPropertyManager")
    written = []
    for name, value in props.items():
        if value in (None, ""):
            continue
        text = str(value)
        adapter._attempt(
            lambda n=name, v=text: mgr.Add3(n, _SW_CUSTOM_TEXT, v, _SW_PROP_REPLACE),
            default=None,
        )
        back = str(
            adapter._attempt(lambda n=name: model.GetCustomInfoValue("", n), default="")
        )
        if back != text:
            raise RuntimeError(
                f"custom property {name!r} readback {back!r} != {text!r}"
            )
        written.append(name)
    log(f"custom properties [{len(written)}]: {', '.join(written)}")


_PREF_DEFAULT_PART_TEMPLATE = 8  # swUserPreferenceStringValue_e.swDefaultTemplatePart


@_telemetry.traced("seat.pin_part_template")
def _pin_default_part_template(adapter: Any) -> None:
    """Point the seat's default part template at the repo-owned PRTDOT.

    ``NewPart()`` (behind the adapter's ``create_part``) instantiates the
    seat's DEFAULT part template, whose document properties carry the DimXpert
    prefs the COM API cannot write (decimals + angular block tolerance).
    Pinning the default to the checked-in template removes that per-seat
    state: every seat builds from the same template, and dodo folds the file
    into every part's recipe/cache key, so a template edit rebuilds parts and
    busts the remote cache. The setting is seat-global and persists -- that is
    the point. apply_block_tolerances still fail-louds if the template's
    get-only prefs drift from title_block.yaml.
    """
    if not PART_TEMPLATE.is_file() or PART_TEMPLATE.stat().st_size == 0:
        raise FileNotFoundError(f"repo part template missing: {PART_TEMPLATE}")
    sw = adapter.swApp
    ok = adapter._attempt(
        lambda: sw.SetUserPreferenceStringValue(
            _PREF_DEFAULT_PART_TEMPLATE, str(PART_TEMPLATE)
        ),
        default=False,
    )
    got = str(
        adapter._attempt(
            lambda: sw.GetUserPreferenceStringValue(_PREF_DEFAULT_PART_TEMPLATE),
            default="",
        )
        or ""
    )
    if not ok or not got or Path(got).resolve() != PART_TEMPLATE.resolve():
        raise RuntimeError(
            f"failed to pin default part template: set={ok} readback={got!r}"
        )
    _telemetry.success(f"default part template pinned -> {PART_TEMPLATE.name}")


# Document summary metadata (File > Properties > Summary — also what Windows
# Explorer shows). swSummInfoTitle=0, swSummInfoAuthor=2 (swSummInfoField_e).
_SUMMARY_TITLE = 0
_SUMMARY_AUTHOR = 2
PROJECT_AUTHOR = "Pedro Paulo Vezza Campos"


@_telemetry.traced("part.summary_info")
def apply_summary_info(adapter: Any, *, title: str) -> None:
    """Write and read-verify the document summary Title + Author.

    Same early-bound split as the drawing summary stamper: SummaryInfo is a
    property, so early binding exposes the getter as ``SummaryInfo(field)`` and
    the setter as ``SetSummaryInfo(field, value)``.
    """
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    for summary_field, value in ((_SUMMARY_TITLE, title), (_SUMMARY_AUTHOR, PROJECT_AUTHOR)):
        model.SetSummaryInfo(summary_field, value)
        if model.SummaryInfo(summary_field) != value:
            raise RuntimeError(
                f"summary field {summary_field} did not persist ({value!r})"
            )
    _telemetry.success(
        f"summary info stamped (Title={title!r}, Author={PROJECT_AUTHOR!r})"
    )


@_telemetry.traced("appearance.material", label_param="material")
async def apply_material(adapter: Any, material: str) -> None:
    """Assign a SolidWorks-database material (saved with the part).

    Materials follow the book: brass for the polished gauge/lever/pen
    hardware, gray cast iron for the castings (base, levers, supports),
    plain carbon steel for shafts/pins/bars, alloy steel for spring wire,
    oak for the stained-wood crank handle (see DIMENSIONS.md per chapter).
    """
    from solidworks_mcp.adapters.base import ApplyMaterialParameters

    check(
        f"apply_material {material}",
        await adapter.apply_material(ApplyMaterialParameters(material=material)),
    )


CASTING_GREEN = (0.03, 0.45, 0.38)  # re-sampled from the ch30/ch17/ch18 plates
# (2026-07-08): R≈0.05·G, B≈0.85·G — the previous 0.13 red channel rendered teal
# M6.8 photo-tuning palette, all sampled from the ch30 plates:
POLISHED_STEEL = (0.65, 0.64, 0.63)  # frame columns (p006 column average)
PANEL_BLACK = (0.08, 0.08, 0.09)  # platen board / clips / knife hardware
SPRING_BLACK = (0.12, 0.12, 0.13)  # blued spring wire (counter + channel)
STAINED_OAK = (0.16, 0.10, 0.07)  # crank handle (dark-stained wood)
PAPER_WHITE = (0.92, 0.92, 0.88)  # platen paper sheet
BAR_STEEL = (0.42, 0.41, 0.39)  # amplitude-bar curtain (p004 edge-on 0.56,
# back views read darker from shadowing; mid value chosen)


@_telemetry.traced("appearance.color")
async def apply_color(adapter: Any, rgb: tuple[float, float, float]) -> None:
    """Explicit part display colour, overriding the material appearance.

    The real machine's frame castings are green-painted, but their database
    material ("Gray Cast Iron") renders dark gray — those parts call this
    after apply_material. The comparison render cache reads the same
    override (export_models doc_rgb cascade).

    Set at BOTH the doc and the solid-body level: apply_material attaches
    the database material's render appearance at part scope, and doc MPV
    only retints its primary colour — useless against TEXTURED appearances
    (Oak's wood image kept rendering over PAPER_WHITE). Body appearances
    sit above part appearances in the display hierarchy, so the body-level
    colour wins over the texture.
    """
    from solidworks_mcp.adapters.com_variant import double_array

    values = double_array([*rgb, 1.0, 1.0, 0.3, 0.31, 0.0, 0.0])
    doc = adapter.currentModel
    # [R,G,B, ambient, diffuse, specular, shininess, transparency, emission]
    doc.MaterialPropertyValues = values
    back = tuple(float(v) for v in (doc.MaterialPropertyValues or ())[:3])
    # SolidWorks quantises to 8 bits per channel
    if len(back) != 3 or any(abs(b - w) > 1 / 255 for b, w in zip(back, rgb)):
        raise RuntimeError(f"colour readback mismatch: set {rgb}, got {back}")
    n_bodies = 0
    try:
        part_h = _early_bound(
            doc, "IPartDoc"
        )  # IPartDoc for GetBodies2; keep `doc` for MaterialPropertyValues
        bodies = part_h.GetBodies2(0, True) or []  # solid bodies
        for body in bodies:
            body.MaterialPropertyValues2 = values
            n_bodies += 1
    except Exception as exc:
        log(f"body colour skipped ({exc})")
    log(f"colour override {tuple(round(v, 3) for v in back)} ({n_bodies} bodies)")


@_telemetry.traced("check.measure", label_param="label")
async def measure_check(
    adapter: Any,
    label: str,
    entities: list[dict[str, Any]],
    key: str,
    expected: float,
    tol: float = 0.01,
) -> None:
    """Measure entities and assert ``key`` equals ``expected`` (mm/mm²/deg).

    ``entities`` are ``MeasureEntityRef`` kwargs, e.g.
    ``{"entity_type": "EDGE", "point": [x, y, z]}`` or
    ``{"entity_type": "PLANE", "name": "Front Plane"}``. Point-based
    selection is view-dependent (screen projection) — use points visible
    in the default view, same caveat as the live regression suite.
    """
    from solidworks_mcp.adapters.base import MeasureEntityRef, MeasureParameters

    # Point selection projects through the screen, so the whole part must be
    # in the viewport — long parts otherwise miss their far faces.
    adapter._zoom_to_fit(adapter.currentModel)

    refs = [MeasureEntityRef(**entity) for entity in entities]
    res = await adapter.measure(MeasureParameters(entities=refs))
    if not res.is_success:
        raise RuntimeError(f"measure {label} failed: {res.error}")
    value = res.data.get(key)
    if value is None:
        raise RuntimeError(f"measure {label}: no {key!r} in {res.data!r}")
    if abs(value - expected) > tol:
        raise RuntimeError(
            f"measure {label}: {key}={value} outside {expected} +/- {tol}"
        )
    _telemetry.success(f"measure {label}: {key}={value:.4f} (expected {expected:g})")


@_telemetry.traced("check.bbox", label_param="label")
async def bbox_extent_check(
    adapter: Any,
    label: str,
    axis: str,
    expected: float,
    tol: float = 0.05,
) -> None:
    """Assert the part's solid bounding-box extent along ``axis`` (mm).

    The view-independent replacement for a face-to-face ``normal_distance``
    measure of an overall width/height/length. ``measure_check`` selected the
    two opposite faces by a screen-projected point each, but mutually-occluding
    faces collapse to a single pick in every standard view (one face hides the
    other), so the measure came back single-faced -- the same screen-projection
    trap the bar-length measure already dodges with a silhouette edge. Reading
    the bounding box needs no face picking at all.

    Unions the solid bodies' precise extreme points along ``axis`` so an
    unabsorbed, shown sketch can't inflate the extent. Only valid when the measured
    faces ARE the part's bounding faces along ``axis`` (true for these overall-size
    annotations); a feature protruding past them would read larger.

    Uses ``IBody2::GetExtremePoint`` (the exact farthest vertex in a direction),
    NOT ``IBody2::GetBodyBox`` -- the latter is documented as an approximate box
    that varies after rebuilds, so a 0.05 mm gate on it can pass/fail
    nondeterministically (codex review #9).
    """
    index = {"x": 0, "y": 1, "z": 2}[axis]
    pos = [1.0 if i == index else 0.0 for i in range(3)]
    neg = [-v for v in pos]

    def _extreme(body: Any, direction: list[float]) -> float:
        # IBody2::GetExtremePoint(Px,Py,Pz): direction in, the extreme point
        # comes back through three [out] doubles (metres). The early-bound makepy
        # wrapper collects the [out] params into the return tuple
        # (retval_bool, X, Y, Z), so pass only the 3 [in] direction components --
        # NOT the late-binding byref VARIANTs. Returns the axis coord in mm.
        body = _early_bound(body, "IBody2")
        res = adapter._attempt(
            lambda: body.GetExtremePoint(direction[0], direction[1], direction[2]),
            default=None,
        )
        if not res or len(res) < 4:
            raise RuntimeError(f"bbox {label}: GetExtremePoint failed")
        return res[1 + index] * 1000.0

    doc = _early_bound(adapter.currentModel, "IPartDoc")
    bodies = adapter._attempt(lambda: doc.GetBodies2(0, False)) or []  # solid
    if not bodies:
        raise RuntimeError(f"bbox {label}: part has no solid bodies")
    lo, hi = float("inf"), float("-inf")
    for body in bodies:
        lo = min(lo, _extreme(body, neg))
        hi = max(hi, _extreme(body, pos))
    extent = hi - lo
    if abs(extent - expected) > tol:
        raise RuntimeError(
            f"bbox {label}: {axis}-extent={extent:.4f} outside {expected} +/- {tol}"
        )
    _telemetry.success(
        f"bbox {label}: {axis}-extent={extent:.4f} (expected {expected:g})"
    )


async def report_mass_properties(adapter: Any) -> None:
    """Print volume/bounding data for the eyeball-vs-DIMENSIONS.md check."""
    res = await adapter.get_mass_properties()
    if res.is_success:
        _telemetry.debug(f"mass properties: {res.data!r}")
        return
    _telemetry.warn(f"get_mass_properties failed: {res.error}")


# ---------------------------------------------------------------------------
# Assembly helpers (M6)
# ---------------------------------------------------------------------------

# The MIRROR_PLANE per-part chirality table and its consumer mirror_placement
# are GONE (#151): every assembly is authored machine-handed and components
# insert on their exact machine transforms (see _transforms.py).

# swConstrainedStatus_e
UNDER_CONSTRAINED = 2
FULLY_CONSTRAINED = 3


def _flag(obj: Any, interface: str) -> None:
    from solidworks_mcp.adapters import sw_type_info

    try:
        sw_type_info.flag_methods(obj, interface)
    except Exception:
        pass


def _early_bound(obj: Any, interface: str) -> Any:
    """Return the generated interface wrapper, or RAISE -- never a raw dispatch.

    Early-bound wrappers invoke known DISPIDs directly and avoid the repeated
    ``GetIDsOfNames`` calls paid by whole-interface method flagging.

    **This never silently returns the unwrapped object.** It used to
    (``except Exception: return obj``), and that one line is the root of the
    ``[out]``-param trap: 542 SolidWorks methods have ``[out]`` params, and
    which marshalling convention applies depends ENTIRELY on whether the object
    is early-bound. makepy handles all 542 uniformly -- call bare, read the
    return tuple -- but on a raw late-bound dispatch that same call needs
    ``VT_BYREF`` VARIANTs. A silent fallback therefore flipped the convention
    invisibly, and the failure mode is a WRONG ANSWER, not an error: an
    unwritten byref reads as "no data" == "no errors found". That cost a full
    session chasing a non-existent "GetWhatsWrong is blind mid-build" defect.

    So a call site can now TRUST that what it gets back is early-bound, and the
    single calling convention (consume the tuple) is always correct.

    Two quiet passthroughs remain, both provably not COM: ``None``, and an
    object with no ``_oleobj_`` (a test double, which never reaches a COM
    boundary).

    The former ``*method_names`` varargs are GONE, not merely ignored. They only
    ever fed ``flag_method_names``, the exact-name fallback used when no
    generated class resolved -- i.e. the silent late-binding path removed above.
    All 74 call sites that passed them were stripped in the same change, so a
    lingering name is now a ``TypeError`` at the call site rather than an
    argument that silently means nothing.
    """
    from solidworks_mcp.adapters import sw_type_info

    if obj is None or getattr(obj, "_oleobj_", None) is None:
        return obj  # not a COM dispatch -- nothing to bind, nothing to marshal

    # Raises ValueError on an interface absent from the wrapper -- a typo or a
    # wrapper that needs regenerating. Let it out; that is a bug, not a mode.
    typed = sw_type_info.early_bound(obj, interface)
    if sw_type_info.is_early_bound(typed, interface):
        return typed

    raise RuntimeError(
        f"_early_bound({interface}) could not bind a generated wrapper to a live"
        f" COM dispatch ({type(obj).__name__}). Refusing to hand back the raw"
        " late-bound object: [out] params would then need VT_BYREF VARIANTs"
        " instead of the return tuple, and getting that wrong reads as 'no"
        " data' rather than failing. Regenerate the checked-in makepy wrapper"
        " for this SolidWorks version, or bind the interface that declares the"
        " member being called."
    )


def _flag_only(obj: Any, *method_names: str) -> None:
    """Flag ONLY the named zero-arg methods on ``obj`` -- not its whole
    interface.

    Each ``_FlagAsMethod`` is one ``GetIDsOfNames`` COM round-trip (~3 ms over
    the out-of-process bridge). ``_flag(comp, "IComponent2")`` flags all ~165
    IComponent2 methods (~0.45 s) -- a steep tax in a loop over every component
    when only one or two zero-arg methods are actually called (issue #87). Flag
    just those instead, so the per-component cost drops to a couple of ms.

    Property reads (``Name2``, ``Transform2`` …) and methods called WITH args
    (``Select2(True, 0)``, ``GetBox(False, False)``) need NO flagging at all --
    drop the flag entirely there rather than calling this. ``_FlagAsMethod`` is
    a pywin32 ``CDispatch`` method, so this needs no gen_py wrapper; unknown
    names raise inside it and are skipped."""
    flag = getattr(obj, "_FlagAsMethod", None)
    if flag is None:
        return
    for name in method_names:
        try:
            flag(name)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Friendly names: tree (sketches/features) + dimensions, plus globals/equations.
#
# The build calls (create_sketch / create_extrusion / add_sketch_dimension)
# leave SolidWorks' OWN auto names -- ``Sketch1``, ``Boss-Extrude1``,
# ``D1@Sketch1`` -- so anyone who opens the part to fine-tune it must first
# reverse-engineer which "D7" is which. These helpers rename the tree and the
# driving dimensions to stable, human names AS the part is built, so a GUI edit
# references ``OuterWidth@OuterProfile``, never ``D3@Sketch1``. They also wrap
# the equation-manager surface (globals + driving equations) so those named
# dims can later be re-coupled to a handful of editable globals.
#
# All raw COM -- the adapter exposes no rename/enumerate surface. APIs (see the
# developing-solidworks bundle): IFeature.Name (get/set), IFeature.GetFirst/
# GetNextDisplayDimension, IDisplayDimension.GetDimension2, IDimension.Name/
# FullName/SystemValue. A name takes effect immediately for the API; the tree
# label only refreshes on the next rebuild (harmless mid-build).
# ---------------------------------------------------------------------------


def _iter_features(adapter: Any):
    """Yield every top-level feature of the active doc in tree order.

    No in-place method flagging here: this walks the SHARED
    ``adapter.currentModel``, and ``_FlagAsMethod`` mutates that instance in
    place.  A generated early-bound wrapper supplies the DISPIDs without
    touching the adapter-owned dispatch. Flipping ``FirstFeature`` /
    ``GetNextFeature`` to method dispatch would break the adapter's OWN bare
    property reads -- its ``create_cut_extrude`` walks ``FirstFeature`` as a
    property to find the profile to cut, and a flagged model silently yields no
    profile (``FeatureCut3 ... Parameter not optional``). ``_read_member`` reads
    these accessors property-style whether or not they are flagged."""
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    feat = _read_member(model, "FirstFeature")
    for _ in range(5000):
        if not feat:
            return
        feat = _early_bound(feat, "IFeature")
        yield feat
        feat = _read_member(feat, "GetNextFeature")


def _last_feature(adapter: Any) -> Any:
    """The most-recently created top-level feature: a just-exited sketch, or the
    boss/cut that just consumed it."""
    last = None
    for feat in _iter_features(adapter):
        last = feat
    if last is None:
        raise RuntimeError("name_last_feature: the active document has no features")
    return last


def _feature_by_name(adapter: Any, name: str) -> Any:
    for feat in _iter_features(adapter):
        if str(_read_member(feat, "Name")) == name:
            return feat
    raise RuntimeError(f"feature {name!r} not found in the active document")


def name_last_feature(adapter: Any, name: str) -> str:
    """Rename the most-recent feature (a sketch right after ``exit_sketch``, or
    the boss/cut right after its creator) to ``name``. Returns ``name`` so it
    can be threaded straight into :func:`name_dimensions`."""
    feat = _last_feature(adapter)
    old = str(_read_member(feat, "Name"))
    feat.Name = name
    _telemetry.success(f"feature {old!r} -> {name!r}")
    return name


def _display_dimensions(feat: Any, owner: str | None = None):
    """Yield the IDimension of each display dimension of ``feat``, in
    creation order.

    ``owner`` filters to dims whose ``FullName`` names that feature as the
    owning one (the middle ``@`` segment). A sketch created on a REFERENCE
    PLANE also enumerates the plane's own offset dim FIRST
    (``D1@<plane>@...``), which would shift positional renaming and trip the
    recorded-count guard -- proven live on cone-pivot-screw's HeadTop driver
    slot. Pass the feature's (post-rename) name to see only its own dims.

    No in-place method flagging -- generated early-bound wrappers provide the
    DISPIDs without mutating the gen_py type-shared dispatch repr. Flagging one
    ``IFeature`` instance flips ``GetTypeName2``
    to method dispatch on EVERY ``IFeature`` wrapper, including the fresh ones
    the adapter's ``create_cut_extrude`` walk reads as bare properties (the
    "Parameter not optional" cut failure). The adapter itself calls arg-taking
    IFeature methods unflagged (``pf.Select2(...)`` in that same walk), so the
    arg-taking ``GetNextDisplayDimension`` / ``GetDimension2`` need no flag, and
    the zero-arg ``GetFirstDisplayDimension`` resolves to its value via
    ``_read_member``."""
    feat = _early_bound(feat, "IFeature")
    disp = _read_member(feat, "GetFirstDisplayDimension")
    for _ in range(1000):
        if not disp:
            return
        disp = _early_bound(disp, "IDisplayDimension")
        idim = _early_bound(disp.GetDimension2(0), "IDimension")
        if owner is None or _dim_owner_feature(idim) == owner:
            yield idim
        disp = feat.GetNextDisplayDimension(disp)


def _dim_owner_feature(idim: Any) -> str:
    """The owning feature's name from a dim's ``FullName`` (``D1@Sketch1@Part``)."""
    parts = str(_read_member(idim, "FullName")).split("@")
    return parts[1] if len(parts) > 1 else ""


def _dim_value_mm(idim: Any) -> float:
    try:
        return float(_read_member(idim, "SystemValue")) * 1000.0
    except Exception:
        return float("nan")


def dump_dimensions(adapter: Any, feature_name: str) -> list[dict[str, Any]]:
    """Print and return every dimension of ``feature_name`` (full name + value).

    The introspection primitive behind 'edit in the GUI, harvest back into the
    script': run it on any feature to see exactly which named dimensions drive
    it and what they currently read."""
    feat = _feature_by_name(adapter, feature_name)
    rows: list[dict[str, Any]] = []
    for i, idim in enumerate(_display_dimensions(feat)):
        full = str(_read_member(idim, "FullName"))
        val = _dim_value_mm(idim)
        rows.append({"index": i, "full_name": full, "value_mm": val})
        _telemetry.debug(f"dim[{i}] {full} = {val:.4g} mm")
    return rows


def name_dimensions(
    adapter: Any, feature_name: str, names: list[str | None]
) -> list[str]:
    """Rename a feature's display dimensions, in creation order, to ``names``.

    ``names[i]`` renames the i-th dimension (``None`` leaves one untouched).
    Prints each ``old (value mm) -> new`` so a run reveals at a glance whether
    the creation order still matches what the ``define_*`` helpers emit -- if a
    sketch's dimensioning ever changes, cross-check against
    :func:`dump_dimensions`. Returns the new ``leaf@feature`` names."""
    feat = _feature_by_name(adapter, feature_name)
    return _name_dimensions_feature(feat, feature_name, names)


def _name_dimensions_feature(
    feat: Any, feature_name: str, names: list[str | None]
) -> list[str]:
    """Rename dimensions on an already-resolved feature dispatch."""
    dims = list(_display_dimensions(feat, feature_name))
    if len(names) > len(dims):
        raise RuntimeError(
            f"name_dimensions {feature_name}: {len(names)} names for "
            f"{len(dims)} dimensions"
        )
    out: list[str] = []
    for idim, new in zip(dims, names, strict=False):
        old = str(_read_member(idim, "FullName"))
        val = _dim_value_mm(idim)
        if new is None:
            _telemetry.info(f"dim {old} = {val:.4g} mm (kept)")
            continue
        idim.Name = new
        out.append(f"{new}@{feature_name}")
        _telemetry.success(f"dim {old} = {val:.4g} mm -> {new}@{feature_name}")
    return out


@_telemetry.traced("param.global", label_param="name")
async def set_global(adapter: Any, name: str, expr: str | float) -> float:
    """Add or update an equation-manager global variable; returns its value.

    Centralises the pen-driver pattern. ``expr`` is the equation-manager
    expression (a literal like ``197`` or a formula like ``"ColumnX" +
    "RailWidth" / 2``); the dialect takes degrees for trig and ``sqr`` is the
    square root (see SetGlobalVariableParameters)."""
    from solidworks_mcp.adapters.base import SetGlobalVariableParameters

    res = await adapter.set_global_variable(
        SetGlobalVariableParameters(name=name, expression=str(expr))
    )
    if not res.is_success:
        raise RuntimeError(f"set_global {name}={expr!r}: {res.error}")
    value = res.data.get("value") if res.data else None
    _telemetry.success(f"global {name} = {expr}  -> {value}")
    return float(value) if value is not None else float("nan")


@_telemetry.traced("param.dimension", label_param="dim_name")
async def drive_dimension(adapter: Any, dim_name: str, expr: str | float) -> None:
    """Bind a (named) dimension to an equation expression, e.g.::

        await drive_dimension(adapter, "OuterWidth@OuterProfile", '2 * "OuterX"')

    so editing the ``OuterX`` global reshapes the part. ``dim_name`` is the
    ``leaf@feature`` form returned by :func:`name_dimensions`."""
    from solidworks_mcp.adapters.base import CreateEquationParameters

    equation = f'"{dim_name}" = {expr}'
    res = await adapter.create_equation(CreateEquationParameters(equation=equation))
    if not res.is_success:
        raise RuntimeError(f"drive_dimension {equation!r}: {res.error}")
    _telemetry.success(f"equation {equation}")


@_telemetry.traced("feature.rebuild")
async def force_rebuild(adapter: Any) -> None:
    """Force a full rebuild of the active doc, failing loud on error.

    Renamed features/dimensions register for the API immediately, but a rebuild
    makes the new names resolvable as equation targets and refreshes the tree
    labels. Delegates to the adapter's ``rebuild_model`` (``ForceRebuild3``) so
    the COM call runs on the adapter's executor thread and a failed rebuild
    raises through :func:`check` rather than passing silently."""
    check("rebuild", await adapter.rebuild_model())


# ---------------------------------------------------------------------------
# Mate family: semantic kinematic joints + driving dimensions.
#
# Generalised from build_frame_assembly's plane-plane mate. Every component is
# inserted at its exact final (mirrored) transform, so a correctly solved mate
# must NOT move it. distance / angle / coincident (and alignment-sensitive
# concentric) mates can pick the far-side solution; pass ``verify=(comp_name,
# origin_mm)`` and the helper reads back ``Transform2`` and re-adds the mate
# flipped when the origin drifts past tolerance -- the same readback-and-flip
# recovery the frame used inline, now shared.
#
# A ``distance``/``angle`` mate IS a driving dimension: ``distance_driver`` /
# ``angle_driver`` are those mates used to pin a residual DOF to a coefficient
# value (the 21 machine inputs + computed-equilibrium snapshot dims).
# ---------------------------------------------------------------------------

_MATE_TOL_MM = 0.5


async def name_bore_axis(
    adapter: Any,
    plane_a: str,
    offset_a: float,
    plane_b: str,
    offset_b: float,
    label: str,
    drive_a: str | None = None,
    drive_b: str | None = None,
    drive_jobs: list[tuple[str, str]] | None = None,
) -> str:
    """Create a named reference axis through a bore, view-independently.

    The axis is the intersection of two planes, each either a principal plane
    (``offset`` 0, used by name) or a plane offset from one. Coordinate
    face/edge selection is view-dependent (``SelectByID2`` picks at the screen
    projection), so an internal/occluded bore wall never selects by point; a
    name-selected axis does. Assembly mates then pick the axis as
    ``named_ref("Axis<N>@<comp>", "AXIS")``.

    ``drive_a``/``drive_b`` optionally tie each offset plane's distance to an
    equation (e.g. ``'"BarDepth" / 2'``) so the axis -- and any assembly mate to
    it -- TRACKS a GUI edit of those globals instead of staying frozen at the
    as-built offset. When given, the created plane's distance dim (``D1@<plane>``)
    is appended to ``drive_jobs`` for the caller's deferred drive batch (same
    convention as ``_cut_tick``); each equation must evaluate to the as-built
    offset so the placement stays neutral. A drive on a principal-plane (offset
    0) side has no dim to drive and is ignored.

    Returns the new axis's resolved name (e.g. ``"Axis1"``).
    """
    from solidworks_mcp.adapters.base import (
        CreateAxisParameters,
        CreatePlaneParameters,
    )

    planes: list[str] = []
    for base, off, tag, drive in (
        (plane_a, offset_a, "A", drive_a),
        (plane_b, offset_b, "B", drive_b),
    ):
        if abs(off) < 1e-9:
            planes.append(base)
            continue
        plane_name = check(
            f"plane {label} {tag} ({base} + {off:g})",
            await adapter.create_plane(
                CreatePlaneParameters(mode="offset", base_plane=base, offset=off)
            ),
        ).name
        planes.append(plane_name)
        if drive is not None and drive_jobs is not None:
            drive_jobs.append((f"D1@{plane_name}", drive))
    return check(
        f"axis {label} ({planes[0]} ∩ {planes[1]})",
        await adapter.create_axis(
            CreateAxisParameters(mode="two_planes", planes=planes)
        ),
    ).name


# swFeatureError_e: the codes GetWhatsWrong returns. >1 (warning=False) is a
# hard rebuild fault; code 1 with the warning flag is informational.
_FEATURE_ERROR = {
    0: "none",
    1: "warning",
    2: "rebuild-error",
    3: "dangling-no-members",
    4: "dangling-has-members",
    5: "sketch-overdefined",
    6: "sketch-nosolution",
    7: "sketch-overdefined-dangling",
}


def set_isometric_view(adapter: Any) -> None:
    """Orient the active document to the standard Isometric view (+ zoom to fit).

    Every part/assembly build calls this at the START (right after
    ``create_part``/``create_assembly``) and the shared save helpers call it again
    just before writing the document, so every ``.SLDPRT``/``.SLDASM`` OPENS on
    isometric -- the convention the user asked for. ``ShowNamedView2`` with an
    empty ``VName`` and ``swIsometricView`` (7) is the documented orient call (see
    the SolidWorks "Change to Isometric and Zoom to Fit" example); the same
    ``ShowNamedView2``/``_zoom_to_fit`` pair as :func:`remap_front_to_machine_front`.

    Independent of :func:`remap_front_to_machine_front`'s standard-view re-basing:
    on the top assembly that runs AFTER the remap, so the file still opens
    isometric while the gallery's re-based Front/Back/etc. stay correct. Tolerant
    of an empty just-created document -- the orient + zoom-to-fit are best-effort.
    """
    SW_ISOMETRIC = 7  # swStandardViews_e.swIsometricView
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    if model is None:
        return
    adapter._attempt(lambda: model.ShowNamedView2("", SW_ISOMETRIC), default=None)
    adapter._zoom_to_fit(model)
    log("view set to isometric")


def _visible_document_paths(adapter: Any) -> list[str]:
    """Paths of the documents a user could see in the session (not Toolbox
    residents), for the post-CloseAllDocuments check."""
    paths: list[str] = []
    doc = adapter.swApp.GetFirstDocument()
    while doc is not None:
        doc = _early_bound(doc, "IModelDoc2")
        if bool(doc.Visible):
            paths.append(str(doc.GetPathName() or ""))
        doc = doc.GetNext()
    return paths


def _resident_output_documents(adapter: Any) -> list[str]:
    """Paths of EVERY resident document (visible or hidden) under ``cad/out``.

    A hidden resident -- the part behind a closed drawing, the children of a
    reopened assembly -- still holds a Windows share lock on its file, so this
    is the set that would fail a later ``cad/out`` write (a cache restore over
    the file, a from-scratch rebuild deleting it). Toolbox residents live
    outside ``cad/out`` and are excluded by construction."""
    out_root = (CAD_ROOT / "out").resolve()
    paths: list[str] = []
    doc = adapter.swApp.GetFirstDocument()
    while doc is not None:
        doc = _early_bound(doc, "IModelDoc2")
        path = str(doc.GetPathName() or "")
        if path and Path(path).resolve().is_relative_to(out_root):
            paths.append(path)
        doc = doc.GetNext()
    return paths


def _normal_path(path: str | Path) -> Path:
    """``path`` comparable to another Windows path (case-folded, links resolved)."""

    return Path(os.path.normcase(os.path.realpath(path)))


def _seat_park_directory() -> Path:
    """An existing directory no build owns, for the seat to sit in.

    The system temp directory is the intent, but ``tempfile.gettempdir()`` is
    not a constant: it takes ``TMPDIR``/``TEMP``/``TMP`` from the environment
    and, with none of them usable, falls back to the PROCESS CURRENT DIRECTORY
    -- which under the farm helper IS the workspace being torn down. Parking
    there would make this helper a silent no-op for exactly the bug it guards,
    so every candidate is checked and a drive root, which no checkout can be,
    is the last resort.

    Disposable means this checkout AND every sibling checkout: a farm worker
    keeps several source roots under one work root and removes them with the
    same housekeeping, so parking in a sibling only moves which leaf fails.
    ``FARM_WORK_ROOT`` is the worker's own name for that tree and reaches the
    helper in its environment.
    """

    checkout = _normal_path(CAD_ROOT.parent)
    disposable = [checkout]
    work_root = os.environ.get("FARM_WORK_ROOT")
    if work_root:
        disposable.append(_normal_path(work_root))
    windows = os.environ.get("SystemRoot") or os.environ.get("windir")
    candidates = [Path(tempfile.gettempdir())]
    if windows:
        candidates.append(Path(windows) / "Temp")
    candidates.append(Path(_normal_path(CAD_ROOT).anchor))
    for candidate in candidates:
        if not candidate.is_dir():
            continue
        resolved = _normal_path(candidate)
        if any(root == resolved or root in resolved.parents for root in disposable):
            continue
        return candidate
    raise RuntimeError(
        f"no seat working directory outside {disposable}: tried {candidates}"
    )


def release_seat_working_directory(sw: Any) -> str | None:
    """Park the seat's working directory where nothing is disposable; return it.

    SolidWorks follows the documents it opens: after a build that saved into
    ``cad/out/sldprt``, the seat's own PROCESS current directory IS that
    directory, and Windows refuses to remove a directory that is any process's
    current directory. Closing documents does not release it -- the directory
    is the process's, not a document's -- so only a re-point clears it.

    Off the farm that is invisible (the checkout outlives the seat). On a farm
    worker the checkout is a disposable source root the agent removes between
    leaves and evicts to bound the disk, so a seat parked inside one makes an
    UNRELATED leaf's housekeeping fail: observed 2026-09-18 on swmaker000006,
    where ``sldworks.exe`` held
    ``C:\\harmonic\\work\\sources\\6621e07a...\\workspace\\cad\\out\\sldprt``
    from an earlier drawing leaf and the release's first farm ``export`` leaf
    failed three times with ``WinError 32`` before it ran a line.

    Parked UNCONDITIONALLY, not only when the seat sits in *this* checkout: a
    worker keeps several source roots, and the seat this session inherited may
    still be parked in a SIBLING root whose own leaf died before its teardown
    (that is exactly the shape above -- the failing leaf's root was not the
    pinned one). Re-pointing only out of our own checkout would leave that root
    pinned until the seat itself died; re-pointing always heals it.

    Teardown, not connect: the seat drifts back into a workspace on the next
    open/save, so a session that re-points only at startup ends parked again.

    Takes the raw ``ISldWorks`` (``adapter.swApp``, or ``package_native``'s
    comtypes pointer), so both COM entrypoints share this one implementation.

    Returns the directory the seat was left in, or ``None`` when it was already
    there. Raises when the seat will not move -- the caller decides what that is
    worth (both callers warn: it is the NEXT leaf's hazard, not this build's
    failure).
    """

    target = _seat_park_directory()
    before = sw.GetCurrentWorkingDirectory()
    if type(before) is not str or not before:
        raise RuntimeError(f"seat working directory unreadable: {before!r}")
    if _normal_path(before) == _normal_path(target):
        return None
    if sw.SetCurrentWorkingDirectory(str(target)) is not True:
        raise RuntimeError(f"seat refused working directory {target}")
    # A True answer is not evidence: the readback is. Anything else and the
    # caller must not report a directory the seat never took. Emptiness is
    # refused BEFORE normalizing, because ``os.path.realpath("")`` is the
    # PROCESS current directory -- so a seat that answers nothing would
    # normalize onto ``target`` itself whenever this helper runs from there,
    # and an unreadable seat would be reported as parked.
    after = sw.GetCurrentWorkingDirectory()
    if type(after) is not str or not after:
        raise RuntimeError(f"seat working directory unreadable after move: {after!r}")
    if _normal_path(after) != _normal_path(target):
        raise RuntimeError(f"seat working directory did not move: {after!r}")
    return after


def discard_open_documents(adapter: Any) -> None:
    """Close every open document WITHOUT a "Save Modified Documents" prompt.

    The transient-drive paths author real mates (and verify's pen sweep installs
    equations), so the reopened assembly (and its referenced children) are
    DIRTY. ``CloseAllDocuments(True)`` still pops the save modal for a dirty
    referenced child in 3DX R2026x -- headless, that hangs the run forever.
    This mirrors ``package_native._discard_open_documents``: close the active doc
    by TITLE first (``CloseDoc`` discards a dirty doc without saving, and
    closing the assembly title drops its hidden components too), then
    ``CloseAllDocuments(True)`` as a backstop with nothing dirty left to prompt
    about. Bounded so a misbehaving session can't spin; an empty title is
    refused (``CloseDoc("")`` silently no-ops on assemblies and would leave the
    document resident)."""
    for _ in range(500):
        doc = adapter._attempt(lambda: _read_member(adapter.swApp, "IActiveDoc2"),
                               default=None)
        if doc is None:
            break
        title = str(_read_member(doc, "GetTitle") or "")
        if not title:
            raise RuntimeError(
                "active document has an empty title -- refusing CloseDoc(''), which "
                "silently no-ops on assemblies and would leave the document resident"
            )
        adapter._attempt(lambda t=title: adapter.swApp.CloseDoc(t), default=None)
    adapter._attempt(lambda: adapter.swApp.CloseAllDocuments(True), default=None)


# ---------------------------------------------------------------------------
# Seat provenance + COM failure forensics
#
# A leaf that fails once and passes on retry is "transient" only while nothing
# recorded WHICH seat ran it and WHAT that seat looked like when it failed. On
# 2026-09-17 `logo ring extrude failed` (FeatureExtrusion3 -> None) failed one
# leaf on swmaker000005@5 and passed on retry, having passed twice earlier the
# same day; neither the trace nor the log could say which sldworks.exe had run
# it, how old that seat was, or what the seat's sketch-authoring preferences
# were -- the three facts that separate "the geometry is wrong" from "this seat
# authors sketches differently". Both gaps are closed here: every session
# records its seat's provenance, and a null COM return captures the seat's state
# before it raises.
#
# Everything below is BEST-EFFORT by construction. Forensics that can fail a
# build, or that can replace a clear geometry failure with an unrelated crash,
# is worse than no forensics: it moves the diagnosis further away.
# ---------------------------------------------------------------------------

# ``PROCESS_QUERY_LIMITED_INFORMATION`` -- enough for the start time, memory and
# session of a process this one did not create, and granted where the full
# ``PROCESS_QUERY_INFORMATION`` right is not.
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
# FILETIME counts 100 ns ticks from 1601-01-01; Unix time runs from 1970-01-01.
_FILETIME_UNIX_EPOCH_TICKS = 116_444_736_000_000_000


class _MemoryCounters(ctypes.Structure):
    """``PROCESS_MEMORY_COUNTERS_EX``.

    ``PrivateUsage`` is the process's commit charge (Task Manager's "Commit
    size"), ``WorkingSetSize`` its resident set. A seat that has been up for
    hours across dozens of leaves carries a very different footprint from one
    that just started, which is exactly the axis a "only fails on warm seats"
    hypothesis needs.
    """

    _fields_ = (
        ("cb", ctypes.c_uint32),
        ("PageFaultCount", ctypes.c_uint32),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
        ("PrivateUsage", ctypes.c_size_t),
    )


@contextlib.contextmanager
def _process_handle(pid: int):
    """Open ``pid`` for limited query; yields ``None`` when it cannot be opened."""
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
    try:
        yield handle or None
    finally:
        if handle:
            kernel32.CloseHandle(handle)


def _process_started_at(pid: int) -> float | None:
    """Unix timestamp of ``pid``'s creation (``GetProcessTimes``)."""
    created = ctypes.c_uint64()
    exited = ctypes.c_uint64()
    kernel = ctypes.c_uint64()
    user = ctypes.c_uint64()
    with _process_handle(pid) as handle:
        if handle is None:
            return None
        if not ctypes.windll.kernel32.GetProcessTimes(
            handle,
            ctypes.byref(created),
            ctypes.byref(exited),
            ctypes.byref(kernel),
            ctypes.byref(user),
        ):
            return None
    return (created.value - _FILETIME_UNIX_EPOCH_TICKS) / 1e7


def _process_memory(pid: int) -> tuple[int | None, int | None]:
    """``(commit charge, working set)`` bytes of ``pid``, or ``(None, None)``."""
    counters = _MemoryCounters()
    counters.cb = ctypes.sizeof(counters)
    with _process_handle(pid) as handle:
        if handle is None:
            return None, None
        if not ctypes.windll.psapi.GetProcessMemoryInfo(
            handle, ctypes.byref(counters), counters.cb
        ):
            return None, None
    return int(counters.PrivateUsage), int(counters.WorkingSetSize)


def _process_session_id(pid: int) -> int | None:
    """Windows session of ``pid``: 0 is a service-launched seat with no
    interactive desktop, 1+ an RDP/console login. A seat started from a signed-in
    session behaves differently from one a scheduled task launched, so the
    session id is part of "which seat was this"."""
    session = ctypes.c_uint32()
    if not ctypes.windll.kernel32.ProcessIdToSessionId(
        int(pid), ctypes.byref(session)
    ):
        return None
    return int(session.value)


def _sldworks_pids() -> set[int]:
    """Pids of every running ``sldworks.exe`` (the lifecycle library's scan)."""
    from solidworks_mcp.adapters import sw_recovery

    return set(sw_recovery.pids_of_image("sldworks.exe"))


# Seats already running when this process began connecting, so a seat THIS build
# started can be told from one it attached to. ``None`` means the sample never
# ran (or failed), which is recorded as ``unknown`` rather than guessed: COM
# starts SolidWorks when none is running, and a seat on its first document of the
# process is the leading suspect in any first-run-only failure.
_seat_pids_at_start: frozenset[int] | None = None
_seat_identity: dict[str, Any] = {}


def note_seats_before_connect() -> None:
    """Sample the running seats BEFORE connecting (see ``_seat_pids_at_start``)."""
    global _seat_pids_at_start
    try:
        _seat_pids_at_start = frozenset(_sldworks_pids())
    except Exception as exc:  # noqa: BLE001 - provenance is never fatal
        _telemetry.debug(f"pre-connect seat scan unavailable: {exc}")
        _seat_pids_at_start = None


def _seat_identity_of(adapter: Any) -> dict[str, Any]:
    """Immutable facts about the seat this adapter drives (pid, origin, start)."""
    sw = getattr(adapter, "swApp", None)
    ident: dict[str, Any] = {}
    pid = (
        adapter._attempt(lambda: int(sw.GetProcessID()), default=None)
        if sw is not None
        else None
    )
    if pid is None:
        # No ``ISldWorks.GetProcessID`` answer: one running seat is unambiguous,
        # several are not -- and a wrong pid is worse than no pid.
        running = sorted(_sldworks_pids())
        pid = running[0] if len(running) == 1 else None
        ident["seat_pid_source"] = "image-scan" if pid is not None else "unresolved"
    else:
        ident["seat_pid_source"] = "GetProcessID"
    if pid is None:
        return ident
    ident["seat_pid"] = pid
    if _seat_pids_at_start is None:
        ident["seat_origin"] = "unknown"
    elif pid in _seat_pids_at_start:
        ident["seat_origin"] = "attached"
    else:
        ident["seat_origin"] = "started-by-build"
    started = _process_started_at(pid)
    if started is not None:
        ident["seat_started_epoch_s"] = round(started, 3)
        ident["seat_started_at"] = datetime.fromtimestamp(started, UTC).isoformat(
            timespec="seconds"
        )
    session = _process_session_id(pid)
    if session is not None:
        ident["seat_session_id"] = session
    revision = adapter._attempt(lambda: str(sw.RevisionNumber()), default=None)
    if revision:
        ident["seat_revision"] = revision
    commit, working_set = _process_memory(pid)
    if commit is not None:
        ident["seat_commit_bytes_at_start"] = commit
    if working_set is not None:
        ident["seat_working_set_bytes_at_start"] = working_set
    return ident


def _seat_working_directory(adapter: Any) -> dict[str, Any]:
    """The directory the SEAT is sitting in, re-read per call.

    ``sldworks.exe`` moves its own working directory as documents are opened and
    saved, and a seat parked inside a leaf's workspace PINS that directory: the
    pool's source-root eviction then fails ``os.rmdir`` with a sharing violation
    on a directory whose files all deleted fine, and the leaf dies with
    ``(log: None)`` -- an infrastructure failure carrying no log at all. That
    happened tonight on the ``export`` leaf and was identified only by probing
    every process's PEB for its current directory over run-command. Recording
    the seat's own answer makes the next one readable off the artefact.
    """
    sw = getattr(adapter, "swApp", None)
    if sw is None:
        return {}
    value = adapter._attempt(
        lambda: _read_member(sw, "GetCurrentWorkingDirectory"), default=None
    )
    return {"seat_working_directory": str(value)} if value else {}


def _seat_liveness(pid: Any, started: Any) -> dict[str, Any]:
    """How old and how big the seat is RIGHT NOW (re-read on every call)."""
    live: dict[str, Any] = {}
    if not isinstance(pid, int):
        return live
    if isinstance(started, (int, float)):
        live["seat_uptime_s"] = round(time.time() - float(started), 1)
    commit, working_set = _process_memory(pid)
    if commit is not None:
        live["seat_commit_bytes"] = commit
    if working_set is not None:
        live["seat_working_set_bytes"] = working_set
    return live


def seat_provenance(adapter: Any) -> dict[str, Any]:
    """WHICH ``sldworks.exe`` this session drives, how old it is and how big.

    Flat ``seat_*`` keys, so the whole set can ride as span attributes (OTel
    attribute values are scalars) and one filter over ``traces.jsonl`` /
    ``logs.jsonl`` finds every one of them. The immutable half is resolved once
    per process and cached; uptime, memory and the seat's working directory are
    re-read per call, so a failure capture records the seat as it was at the
    moment it failed.
    """
    global _seat_identity
    if not _seat_identity:
        try:
            _seat_identity = _seat_identity_of(adapter)
        except Exception as exc:  # noqa: BLE001 - provenance is never fatal
            _seat_identity = {"seat_provenance_error": f"{type(exc).__name__}: {exc}"}
    prov = dict(_seat_identity)
    try:
        prov.update(
            _seat_liveness(prov.get("seat_pid"), prov.get("seat_started_epoch_s"))
        )
        prov.update(_seat_working_directory(adapter))
    except Exception as exc:  # noqa: BLE001 - provenance is never fatal
        prov["seat_liveness_error"] = f"{type(exc).__name__}: {exc}"
    return prov


def record_seat_provenance(adapter: Any) -> dict[str, Any]:
    """Resolve the seat's provenance, publish it, and return it for the caller to
    hang on the build PHASE span.

    Published three ways, because each answers a different question: a
    ``seat.provenance`` span event (WHEN in the session the seat was identified),
    one INFO log record (so the entries with no phase span -- verify, export, the
    ``diagnostics/`` probes -- are still attributable in ``logs.jsonl``), and a
    push into the watchdog so a fatal crash/timeout abort names the seat it killed
    rather than just the exit code.
    """
    prov = seat_provenance(adapter)
    _watchdog.set_seat_provenance(prov)
    _telemetry.event("seat.provenance", **prov)
    _telemetry.info(
        "seat "
        + " ".join(
            f"{key.removeprefix('seat_')}={value}" for key, value in prov.items()
        ),
        **prov,
    )
    return prov


# The seat user preferences that govern SKETCH AUTHORING. A profile authored from
# bare ``CreateLine``/``Create3PointArc`` calls closes into an extrudable contour
# only if the seat merges exactly-coincident endpoints, which is application
# state: inference and automatic relations persist across leaves on the same seat,
# so a leaf that turns them off and dies before its ``finally`` restores them
# poisons that seat for every later leaf -- deterministic per seat, random-looking
# across a fleet. Every name below is a verified member of
# ``swUserPreferenceToggle_e`` / ``swUserPreferenceIntegerValue_e`` (swconst
# R2026x), and is resolved to its id AT RUNTIME by name: the ids move between
# releases while the member names do not, and the captured id is recorded next to
# the value so an id can be confirmed rather than assumed. The baseline the farm
# ENFORCES lives in the pool repo (``agent/seat_settings.py``); this list is what
# a failure READS.
SKETCH_AUTHORING_TOGGLE_NAMES = (
    # Inference, automatic relations and the solver: what merges coincident
    # endpoints into a closed loop when the recipe adds no explicit relations.
    "swSketchInference",
    "swSketchAutomaticRelations",
    "swSketchInferFromModel",
    "swSketchNoSolveMove",
    "swFullyConstrainedSketchMode",
    # Snapping: which existing entity a new endpoint may land on. The
    # quadrant/nearest snaps are the "circle-snap hazard" a raw-primitive
    # profile has to reason about.
    "swSnapToPoints",
    "swSketchSnapsPoints",
    "swSketchSnapsCenterPoints",
    "swSketchSnapsMidPoints",
    "swSketchSnapsQuadrantPoints",
    "swSketchSnapsIntersections",
    "swSketchSnapsNearest",
    # Grid snapping quantizes coordinates AT CREATION -- the one snap preference
    # with a direct "silently moves scripted geometry" mechanism (SeatSettings
    # pins this one to False for exactly that reason).
    "swSketchSnapsGrid",
    # Autosolve/undo mode: swSketchTurnOffAutomaticSolveModeAndUndo decides
    # whether the solver runs at all as segments are added.
    "swSketchTurnOffAutomaticSolveModeAndUndo",
    # Dimension entry: a seat that pops the dimension box, or rescales a sketch
    # on its first dimension, authors different geometry from one that does not.
    "swInputDimValOnCreate",
    "swSketchAcceptNumericInput",
    "swSketchCreateDimensionOnlyWhenEntered",
    "swScaleSketchOnFirstDimension",
    "swAddDimensionsToSketchEntity",
)

SKETCH_AUTHORING_INTEGER_NAMES = ("swSketch_Auto_Solve_Threshold",)

# Preferences that wedge a seat with a modal dialog instead of failing it: a
# ``#32770`` parked over the graphics area makes a leaf log healthy heartbeats
# and no progress, and no COM read can see it. Captured because "leaf stalled,
# no error" is otherwise indistinguishable from slow work (see the pool's
# diagnose-wedged-solidworks-seat / unwedge-3dexperience-connector-modal
# playbooks, and SeatSettings' baseline, which PINS these).
MODAL_HAZARD_TOGGLE_NAMES = (
    "swSketchPromptToCloseSketch",
    "swSketchOverdefiningDimsPromptToSetState",
    "swSketchOverdefiningDimsSetDrivenByDefault",
    "swDrawingShowSheetFormatDialog",
    "swShowErrorsEveryRebuild",
    "swSaveReminderEnable",
    "swWhileOpeningAssembliesAutoDismissMessages",
    "swAlwaysUseDefaultTemplates",
    "swOpenLastUsedDocumentAtStart",
)

# Per-DOCUMENT toggles, read through ``IModelDocExtension`` and reported in their
# own bucket. These are not "preferences SolidWorks ignores on write": SolidWorks'
# own option-to-API mapping (docs/swconst/ToolsSketchEntitiesRectangle.md:11,14)
# documents both members on ``IModelDocExtension::Get/SetUserPreferenceToggle``
# and NOT on ``ISldWorks``, so reading them through the system accessor is a
# category error -- which is exactly why one worker read system=False while its
# active document read True in the same pass. They are also HALF A RADIO PAIR
# each (From Midpoint / From Corner), so a snapshot naming only one describes
# half a control.
DOCUMENT_SCOPE_TOGGLE_NAMES = (
    "swSketchAddConstToRectEntity",  # Rectangle Type > Add construction lines > From Midpoint
    "swSketchAddConstLineDiagonalType",  # ... > From Corner (id 585, verified in swconst)
)

# The SolidWorks default-template preferences (``swUserPreferenceStringValue_e``
# member names): the part template sets the document's INITIAL VIEW SCALE, which
# is a load-bearing input to any inference-dependent sketch (see
# :func:`display_geometry`), so "which template" is part of the geometry's
# provenance, not mere configuration.
TEMPLATE_PREFERENCE_NAMES = ("swDefaultTemplatePart", "swDefaultTemplateAssembly")


def _preference_id(adapter: Any, name: str) -> int | None:
    """Resolve a ``swUserPreference*_e`` MEMBER NAME to its id at runtime.

    Through the swconst type library the early-bound adapter loads
    (``win32com.client.constants``) first, then the adapter's own small
    constants table. Never a hard-coded integer.
    """
    constants: Any = None
    with contextlib.suppress(Exception):  # not on a seat: offline gate / no pywin32
        from win32com.client import constants as sw_constants

        constants = sw_constants
    value = getattr(constants, name, None) if constants is not None else None
    if value is None:
        value = getattr(adapter, "constants", {}).get(name)
    return int(value) if isinstance(value, int) and not isinstance(value, bool) else None


def sketch_authoring_preferences(adapter: Any) -> dict[str, Any]:
    """The seat's CURRENT values for the preferences that govern sketch authoring.

    ``"unresolved"`` = the name is not in this seat's swconst (so nothing was
    read); ``"unreadable"`` = the seat refused the read. Both are recorded rather
    than dropped -- and neither is reported as ``False``, because
    ``GetUserPreferenceToggle`` answers an unknown id with a plausible-looking
    ``False`` and a silent one of those would send the next investigation the
    wrong way. ``preference_ids`` carries the id each name resolved to, so the
    id/member pairing can be confirmed against the type library.
    """
    sw = adapter.swApp
    snapshot: dict[str, Any] = {}
    ids: dict[str, int] = {}
    readers = (
        (SKETCH_AUTHORING_TOGGLE_NAMES, "GetUserPreferenceToggle", bool),
        (MODAL_HAZARD_TOGGLE_NAMES, "GetUserPreferenceToggle", bool),
        (SKETCH_AUTHORING_INTEGER_NAMES, "GetUserPreferenceIntegerValue", int),
        (TEMPLATE_PREFERENCE_NAMES, "GetUserPreferenceStringValue", str),
    )
    for names, accessor, cast in readers:
        read = getattr(sw, accessor, None)
        for name in names:
            pref = _preference_id(adapter, name)
            if pref is None or read is None:
                snapshot[name] = "unresolved"
                continue
            ids[name] = pref
            value = adapter._attempt(lambda p=pref, r=read: r(p), default=None)
            snapshot[name] = cast(value) if value is not None else "unreadable"
    snapshot["preference_ids"] = ids
    snapshot["document_scope"] = _document_scope_preferences(adapter, ids)
    return snapshot


def _document_scope_preferences(
    adapter: Any, ids: dict[str, int]
) -> dict[str, Any]:
    """Per-DOCUMENT toggles, read through the document's own accessor.

    Kept in a separate bucket, explicitly labelled: the system accessor answers
    these with a value that does not govern the active document (system=False
    while the document reads True, observed on worker 4), so folding them into
    the system snapshot logs a misleading number.
    """
    model = adapter.currentModel
    extension = _read_member(model, "Extension") if model is not None else None
    if extension is None:
        return {"scope": "document", "document": None}
    scoped: dict[str, Any] = {"scope": "document"}
    read = getattr(extension, "GetUserPreferenceToggle", None)
    for name in DOCUMENT_SCOPE_TOGGLE_NAMES:
        pref = _preference_id(adapter, name)
        if pref is None or read is None:
            scoped[name] = "unresolved"
            continue
        ids[name] = pref
        # The document accessor takes (id, swUserPreferenceOption_e); 0 is
        # swDetailingNoOptionSpecified, i.e. "this document's value".
        value = adapter._attempt(lambda p=pref, r=read: r(p, 0), default=None)
        scoped[name] = bool(value) if value is not None else "unreadable"
    return scoped


def sketch_manager_state(adapter: Any) -> dict[str, Any]:
    """``ISketchManager``'s STICKY per-session state.

    This is a second state bag that ``Get/SetUserPreferenceToggle`` cannot see,
    and it overrides the preferences: with ``AddToDB=True`` a new segment
    bypasses inference relations at creation time no matter what
    ``swSketchInference`` says (that is exactly why
    :func:`set_sketch_direct_db` exists). A snapshot that reads only user
    preferences therefore reports a perfectly healthy seat while the thing that
    actually governs endpoint merging sits in here -- which is what "the log was
    clean and the failure still happened" looked like on 2026-09-17.

    It is per SESSION, not per document, so a leaf that sets ``AddToDB`` and dies
    before restoring it hands the next leaf on that seat a different authoring
    mode, with nothing on disk to show it.
    """
    manager = adapter.currentSketchManager
    if manager is None:
        return {"sketch_manager": None}
    state: dict[str, Any] = {"scope": "session"}
    for name in ("AddToDB", "AutoInference", "AutoSolve", "DisplayWhenAdded"):
        value = adapter._attempt(lambda n=name: _read_member(manager, n), default=None)
        state[name] = bool(value) if isinstance(value, (bool, int)) else "unreadable"
    return state


class _Rect(ctypes.Structure):
    """Win32 ``RECT`` (``GetClientRect`` fills it with client-area pixels)."""

    _fields_ = (
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    )


# GetSystemMetrics indices: primary screen pixels and monitor count. A session
# whose RDP client disconnected reports a degenerate or stale desktop, which is
# the documented "live frame froze after someone RDP'd in" shape -- and worker 5's
# seat was hand-launched over RDP 54 min before the 2026-09-17 failure.
_SM_CXSCREEN, _SM_CYSCREEN, _SM_CMONITORS = 0, 1, 80
# A sketch-inference snap is a SCREEN-SPACE hit test of a few pixels. 8 px is the
# pessimistic end of SolidWorks' observed 5-8 px tolerance, so
# ``snap_floor_mm`` = 8 / (px per mm) is the model distance below which two
# DISTINCT points stop being separately clickable -- compare it against the
# profile's nearest non-coincident competitor (0.400 mm for the 91247A720 logo
# ring) to decide whether that geometry could author correctly at all.
_SNAP_TOLERANCE_PX = 8


def _frame_geometry(adapter: Any) -> dict[str, Any]:
    """The SolidWorks main window's pixel rect -- the term the 2026-09-17
    investigation had to reconstruct by hand and could not.

    RootCause's verdict refuted preference drift by measurement (45 shared
    sketch/snap/inference preference names, ZERO differences across workers
    4/5/6) and landed on this instead: the failing seat's main window was
    1024x640 against 1278x750 and 1296x816 on the two that passed -- 0.620 of
    the area, monotonic with the outcome. Nothing recorded it. The live
    dashboard frames are capped and unversioned and the published PNGs are a
    forced 1600x1000 (they measure the EXPORT, not the window), so the rect at
    04:59:56Z is permanently unrecoverable.

    Recorded as INTEGERS, not a "1024x640" label: width/height/left/top plus the
    derived area are what a later comparison across seats needs, and the
    maximised/minimised state says whether an operator had hand-arranged the
    window (which is how w5 got its size -- launched over RDP, then ``tscon``'d
    to the console). SeatSettings records the same fields on every periodic seat
    check, including clean seats; this is the failure-time half of the pair, and
    the field names match theirs so both halves join on one query.
    """
    sw = adapter.swApp
    frame = adapter._attempt(lambda: _read_member(sw, "Frame"), default=None)
    hwnd = (
        adapter._attempt(lambda: int(frame.GetHWnd()), default=None)
        if frame is not None
        else None
    )
    if not hwnd:
        return {"frame_hwnd": None}
    user32 = ctypes.windll.user32
    geometry: dict[str, Any] = {"frame_hwnd": hwnd}
    window = _Rect()
    if user32.GetWindowRect(hwnd, ctypes.byref(window)):
        width = window.right - window.left
        height = window.bottom - window.top
        geometry.update(
            frame_left=window.left,
            frame_top=window.top,
            frame_width_px=width,
            frame_height_px=height,
            frame_area_px=width * height,
        )
    client = _Rect()
    if user32.GetClientRect(hwnd, ctypes.byref(client)):
        geometry["frame_client_width_px"] = client.right - client.left
        geometry["frame_client_height_px"] = client.bottom - client.top
    geometry["frame_state"] = (
        "minimised"
        if user32.IsIconic(hwnd)
        else "maximised"
        if user32.IsZoomed(hwnd)
        else "normal"
    )
    return geometry


def _projected_px_per_mm(adapter: Any, view: Any) -> dict[str, Any]:
    """MEASURE pixels-per-millimetre by projecting model points to the screen.

    ``IModelView.ProjectModelPoint`` is the only route that answers the governing
    quantity directly instead of requiring ``Scale2`` to be interpreted: project
    the origin and a point 1 mm along each axis, and the pixel distance IS px/mm
    for that direction. The axes are reported separately because a rotated view
    foreshortens them differently, and the maximum is the one a snap in the
    sketch plane sees.

    ``[out]`` params ride the return tuple (early binding; see
    :func:`_early_bound`).
    """
    typed = _early_bound(view, "IModelView")
    project = getattr(typed, "ProjectModelPoint", None)
    if project is None:
        return {}
    def screen(x: float, y: float, z: float) -> tuple[float, float] | None:
        out = adapter._attempt(lambda: project(x, y, z), default=None)
        if not isinstance(out, (list, tuple)) or len(out) < 3:
            return None
        values = [v for v in out if isinstance(v, (int, float))]
        return (float(values[0]), float(values[1])) if len(values) >= 2 else None

    origin = screen(0.0, 0.0, 0.0)
    if origin is None:
        return {}
    measured: dict[str, Any] = {}
    for axis, point in (("x", (1e-3, 0.0, 0.0)), ("y", (0.0, 1e-3, 0.0)), ("z", (0.0, 0.0, 1e-3))):
        far = screen(*point)
        if far is None:
            continue
        measured[f"px_per_mm_{axis}"] = round(
            math.dist(origin, far), 3
        )  # 1 mm apart in model space -> pixels on screen
    axes = [value for key, value in measured.items() if key.startswith("px_per_mm_")]
    if axes:
        px_per_mm = max(axes)
        measured["px_per_mm"] = px_per_mm
        if px_per_mm > 0:
            measured["snap_floor_mm"] = round(_SNAP_TOLERANCE_PX / px_per_mm, 4)
            measured["snap_tolerance_px"] = _SNAP_TOLERANCE_PX
    return measured


def display_geometry(adapter: Any) -> dict[str, Any]:
    """The SCREEN-SPACE state an inference-dependent sketch is authored under.

    Sketch inference snapping is a pixel hit test, so the authoring-time view
    scale and the window's pixel size decide whether two points 0.4 mm apart are
    distinguishable at all. Nothing in the build path fits or orients the view
    before authoring (the only ``ViewZoomtofit2``/``ShowNamedView2`` calls on the
    whole path are inside the adapter's screenshot helper), so this state is
    INHERITED from the document template and the window size and was, until now,
    never recorded -- which is why a run that produced correct geometry and one
    that did not could not be compared.

    Recorded: ``Scale2`` and the visible model box (the raw inputs, each
    uninterpretable without the other), the main window's numeric rect, area and
    state (:func:`_frame_geometry` -- the measured root cause of the 2026-09-17
    failure), the measured px/mm with the per-axis values behind it, the
    resulting snap floor in millimetres, and the interactive session's screen
    metrics.
    """
    geometry: dict[str, Any] = dict(_frame_geometry(adapter))
    screen_w = int(ctypes.windll.user32.GetSystemMetrics(_SM_CXSCREEN))
    screen_h = int(ctypes.windll.user32.GetSystemMetrics(_SM_CYSCREEN))
    geometry["screen_width_px"] = screen_w
    geometry["screen_height_px"] = screen_h
    geometry["screen_px"] = f"{screen_w}x{screen_h}"
    geometry["monitors"] = int(ctypes.windll.user32.GetSystemMetrics(_SM_CMONITORS))
    # 0x0 with no monitors is a session whose RDP client disconnected: screen
    # capture stops and the seat's view geometry stops meaning anything.
    geometry["session_has_display"] = geometry["screen_px"] != "0x0"
    model = adapter.currentModel
    view = (
        adapter._attempt(lambda: _read_member(model, "ActiveView"), default=None)
        if model is not None
        else None
    )
    if view is None:
        return geometry
    scale = adapter._attempt(lambda: float(_read_member(view, "Scale2")), default=None)
    if scale is not None:
        geometry["view_scale2"] = scale
    box = adapter._attempt(
        lambda: list(_early_bound(view, "IModelView").GetVisibleBox() or []), default=None
    )
    if box and len(box) >= 6:
        numbers = [float(value) for value in box[:6]]
        geometry["visible_box_mm"] = [round(value * 1000.0, 3) for value in numbers]
        geometry["visible_width_mm"] = round(abs(numbers[3] - numbers[0]) * 1000.0, 3)
        geometry["visible_height_mm"] = round(abs(numbers[4] - numbers[1]) * 1000.0, 3)
        client_width = geometry.get("frame_client_width_px")
        if client_width and geometry["visible_width_mm"]:
            geometry["px_per_mm_from_box"] = round(
                client_width / geometry["visible_width_mm"], 3
            )
    geometry.update(_projected_px_per_mm(adapter, view))
    return geometry


def record_authoring_context(adapter: Any, label: str) -> dict[str, Any]:
    """Publish the authoring-time seat state for a SUCCESSFUL build too.

    A failure-only capture cannot answer "what was different about the run that
    worked?", which is the question that actually identifies a seat-state cause.
    So the same state bags a failure captures -- the screen-space geometry,
    ``ISketchManager``'s sticky session state, and the sketch-authoring
    preferences -- are recorded once per part build, on the success path, as a
    span event plus one INFO record carrying the whole snapshot as JSON.

    EVERY probe is guarded individually, because this runs on the path where
    nothing is wrong: ``save_part_and_images`` calls it before ``save_file``, and
    these probes reach ``_early_bound`` (raises when no generated wrapper binds)
    and raw ``user32`` calls. A diagnostic that fails a good part export is worse
    than no diagnostic, so a bag that cannot be read is recorded as its own error
    string and the build continues.
    """
    bags: dict[str, Callable[[], Any]] = {
        "seat": lambda: seat_provenance(adapter),
        "display": lambda: display_geometry(adapter),
        "sketch_manager": lambda: sketch_manager_state(adapter),
        "preferences": lambda: sketch_authoring_preferences(adapter),
    }
    context: dict[str, Any] = {"label": label}
    for name, probe in bags.items():
        try:
            context[name] = probe()
        except Exception as exc:  # noqa: BLE001 - see above: never fail a good build
            context[name] = {"capture_error": f"{type(exc).__name__}: {exc}"}
    display = context["display"]
    summary = (
        f"authoring {label}: px/mm={display.get('px_per_mm', 'unknown')} "
        f"snap_floor={display.get('snap_floor_mm', 'unknown')}mm "
        f"view_scale2={display.get('view_scale2', 'unknown')} "
        f"frame={display.get('frame_width_px', '?')}x"
        f"{display.get('frame_height_px', '?')}"
        f"({display.get('frame_state', 'unknown')}) "
        f"AddToDB={context['sketch_manager'].get('AddToDB', 'unknown')}"
    )
    with contextlib.suppress(Exception):
        _telemetry.event(
            "seat.authoring_context",
            label=label,
            **_attributes_of(display),
        )
        _telemetry.info(summary, label=label, authoring=json.dumps(context, default=str))
    return context


_SAVE_AS_CURRENT_VERSION = 0  # swSaveAsVersion_e.swSaveAsCurrentVersion
# swSaveAsOptions_e.swSaveAsOptions_Silent | swSaveAsOptions_Copy: silent so a
# headless leaf can never block on a save dialog, and a COPY so the live document
# keeps its own path -- a rename would repoint the session at cad/out/reports and
# lie to run_build's teardown scan of resident cad/out documents.
_SAVE_AS_SILENT_COPY = 1 | 2
_DOC_SUFFIX = {1: ".SLDPRT", 2: ".SLDASM", 3: ".SLDDRW"}
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


def _slug(label: str) -> str:
    """Filesystem-safe directory name for a failure label."""
    return re.sub(r"[^a-z0-9._-]+", "-", label.strip().lower()).strip("-.") or "failure"


def _scalar(value: Any) -> Any:
    """An OTel-safe attribute value: scalars pass through, anything else is JSON."""
    if isinstance(value, (bool, int, float, str)):
        return value
    return json.dumps(value, default=str, sort_keys=True)


# Keyword names the telemetry helpers own: a captured key of the same name would
# bind to the helper's own parameter (``_telemetry.event(name, **attributes)``
# takes ``name``; ``error(message, *, exc_info)`` takes both) and raise
# TypeError. Captured data is RENAMED rather than dropped -- a sketch's ``name``
# is exactly the field a reader looks for first.
_TELEMETRY_OWNED_KEYS = frozenset({"name", "message", "service", "exc_info"})


def _attributes_of(values: Mapping[str, Any]) -> dict[str, Any]:
    """Captured values as telemetry attributes: scalars, no shadowed keywords."""
    return {
        (f"captured_{key}" if key in _TELEMETRY_OWNED_KEYS else key): _scalar(value)
        for key, value in values.items()
    }


def _capture_step(report: dict[str, Any], name: str, probe: Callable[[], Any]) -> None:
    """Run ONE capture: record its result -- or its own failure -- in ``report``
    and as a single ``com.failure.<name>`` span event.

    Individually guarded, and one event per STEP rather than per captured item:
    a step that cannot read the seat must not stop the steps that can, and a
    census of a 40-segment sketch must not arrive as 40 span events. The
    REPORTING is guarded too: the value is already in ``report``, so a telemetry
    failure must not cost the artefact (it did, for one round of this change: a
    captured ``name`` key collided with ``event``'s own parameter and aborted the
    whole capture before it could write capture.json).
    """
    try:
        value = probe()
    except Exception as exc:  # noqa: BLE001 - forensics never raise (see above)
        error = f"{type(exc).__name__}: {exc}"
        report[name] = {"capture_error": error}
        with contextlib.suppress(Exception):
            _telemetry.event(f"com.failure.{name}", capture_error=error)
        return
    report[name] = value
    attributes = value if isinstance(value, dict) else {"value": value}
    with contextlib.suppress(Exception):
        _telemetry.event(f"com.failure.{name}", **_attributes_of(attributes))


def _seat_error_state(adapter: Any) -> dict[str, Any]:
    """SolidWorks' own error surface: the What's Wrong table and the session
    message stack.

    Both take ``[out]`` params that ride the RETURN TUPLE under early binding --
    call them bare and unpack (a byref VARIANT stays unwritten and reads as "no
    errors"; see ``_early_bound`` and ``test_out_param_binding``).
    ``GetErrorMessages`` is read-AND-CLEAR and keeps only the last 20 messages,
    which is safe exactly here: this is the failure path, and draining the stack
    into the capture is strictly better than leaving it to be discarded with the
    session.
    """
    state: dict[str, Any] = {}
    sw = adapter.swApp
    messages = adapter._attempt(
        lambda: _early_bound(sw, "ISldWorks").GetErrorMessages(), default=None
    )
    if isinstance(messages, (list, tuple)) and len(messages) >= 2:
        state["error_messages"] = [str(text) for text in (messages[1] or [])]
    model = adapter.currentModel
    extension = _read_member(model, "Extension") if model is not None else None
    if extension is None:
        return state
    state["whats_wrong_count"] = adapter._attempt(
        lambda: int(_early_bound(extension, "IModelDocExtension").GetWhatsWrongCount()),
        default=None,
    )
    faults = adapter._attempt(
        lambda: _early_bound(extension, "IModelDocExtension").GetWhatsWrong(),
        default=None,
    )
    if isinstance(faults, (list, tuple)) and len(faults) >= 4:
        _retval, features, codes, warnings = faults[:4]
        state["whats_wrong"] = [
            {
                "feature": str(_read_member(feature, "Name")),
                "code": int(code or 0),
                "error": _FEATURE_ERROR.get(int(code or 0), "unknown"),
                "warning": bool(warning),
            }
            for feature, code, warning in zip(
                list(features or []),
                list(codes or []),
                list(warnings or []),
                strict=False,
            )
        ]
    return state


def _document_state(adapter: Any) -> dict[str, Any]:
    """Which document was active, whether a sketch was open for edit, and how
    much of it had been built when the call failed."""
    model = adapter.currentModel
    if model is None:
        return {"active_document": None}
    active_sketch = adapter._attempt(
        lambda: _read_member(model, "GetActiveSketch2"), default=None
    )
    probes: dict[str, Callable[[], Any]] = {
        "title": lambda: str(_read_member(model, "GetTitle") or ""),
        "path": lambda: str(_read_member(model, "GetPathName") or ""),
        "doc_type": lambda: int(_read_member(model, "GetType") or 0),
        "feature_count": lambda: int(_read_member(model, "GetFeatureCount") or 0),
        "needs_save": lambda: bool(_read_member(model, "GetSaveFlag")),
        "configuration": lambda: active_configuration_name(adapter, model),
    }
    state: dict[str, Any] = {
        key: adapter._attempt(probe, default=None) for key, probe in probes.items()
    }
    # A feature created while a sketch is still open for edit is the classic
    # cause of a None return, so the edit state is as important as the geometry.
    state["in_sketch_edit"] = active_sketch is not None
    return state


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
    name = sketch or feature_name_by_type(adapter, "ProfileFeature")
    if not name:
        active = adapter._attempt(
            lambda: _read_member(model, "GetActiveSketch2"), default=None
        )
        return active, ""
    feature = adapter._attempt(lambda: _feature_by_name(adapter, str(name)), default=None)
    if feature is None:
        return None, str(name)
    resolved = adapter._attempt(
        lambda: _read_member(feature, "GetSpecificFeature2"), default=None
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
        coords = tuple(_read_member(point, axis) for axis in ("X", "Y", "Z"))
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


def _save_failure_document(adapter: Any, out_dir: Path, slug: str) -> dict[str, Any]:
    """Save a COPY of the failing document into the failure directory.

    The document is the evidence: with it, the profile can be opened and the
    failing feature retried on any seat. Saved as a silent copy in the live
    document's own format (the extension comes from the document, so a part,
    assembly and drawing each land native).
    """
    model = adapter.currentModel
    if model is None:
        return {"document_copy": None}
    suffix = Path(str(_read_member(model, "GetPathName") or "")).suffix
    if not suffix:
        doc_type = _read_member(model, "GetType")
        suffix = _DOC_SUFFIX.get(
            doc_type if isinstance(doc_type, int) else 0, ".SLDPRT"
        )
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"{slug}{suffix}"
    target.unlink(missing_ok=True)
    rc = adapter._attempt(
        lambda: model.SaveAs3(
            str(target), _SAVE_AS_CURRENT_VERSION, _SAVE_AS_SILENT_COPY
        ),
        default=None,
    )
    saved = target.exists()
    return {
        "document_copy": str(target) if saved else None,
        "document_copy_bytes": target.stat().st_size if saved else None,
        "save_rc": _scalar(rc),
    }


def _save_seat_image(adapter: Any, out_dir: Path, slug: str) -> dict[str, Any]:
    """Capture the seat's current viewport with ``IModelDoc2.SaveBMP``.

    No dialog, no camera move and no zoom-to-fit, so the image shows the seat
    exactly as it sat when the call failed -- and shows a modal box parked over
    the graphics area, which is invisible to every COM read. (``export_image``
    would have re-oriented the view and destroyed that evidence.)
    """
    model = adapter.currentModel
    if model is None:
        return {"seat_image": None}
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"{slug}.bmp"
    target.unlink(missing_ok=True)
    adapter._attempt(lambda: model.SaveBMP(str(target), 1600, 1000), default=None)
    saved = target.exists()
    return {
        "seat_image": str(target) if saved else None,
        "seat_image_bytes": target.stat().st_size if saved else None,
    }


def _write_failure_report(out_dir: Path, report: dict[str, Any]) -> dict[str, Any]:
    """Write ``capture.json`` -- the index of everything captured."""
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / "capture.json"
    target.write_text(
        json.dumps(report, indent=2, default=str, sort_keys=True), encoding="utf-8"
    )
    return {"report": str(target)}




def capture_com_failure(
    adapter: Any,
    label: str,
    message: str,
    *,
    api: str | None = None,
    sketch: Any | None = None,
    expected_points: int | None = None,
    exc_type: type[BaseException] = RuntimeError,
    **context: Any,
) -> NoReturn:
    """Capture the seat's state behind a COM call that returned ``None``, then raise.

    A feature-creation API that hands back ``None`` says only "no feature". The
    state that decides WHY -- which seat, which document, whether the profile
    closed, what the seat's sketch-authoring preferences were -- lives in a
    session that is about to be torn down, so a bare ``raise`` throws the
    diagnosis away and leaves "transient" as the only available verdict. Use this
    instead of ``raise`` at such a site::

        if feat is None:
            capture_com_failure(
                adapter,
                "logo-ring-extrude",
                "logo ring extrude failed",
                api="IFeatureManager.FeatureExtrusion3",
                sketch="LogoProfile",
            )

    Three guarantees, in order of importance:

    1. It ALWAYS raises ``exc_type(message)``, with ``message`` unchanged. Every
       capture step is guarded individually and the capture as a whole is guarded
       again, so forensics can neither mask the failure's message nor convert a
       clear geometry failure into an unrelated crash.
    2. Everything captured lands as ``com.failure.<step>`` span events on a
       ``com.failure <label>`` span AND in exactly ONE ERROR log record (the
       whole capture as JSON), so the evidence reaches App Insights and
       ``logs.jsonl`` -- not just a disposable worker's disk.
    3. The artefacts (a copy of the failing document, a BMP of the seat,
       ``capture.json``) land under
       ``cad/out/reports/failures/<label>/<UTC timestamp>/``. The timestamp
       directory is not cosmetic: on 2026-09-17 the successful RETRY overwrote
       the failing attempt's leaf log, and the whole diagnosis had to be
       reconstructed from traces. A retry must never erase the evidence of the
       failure it is retrying.

    Captured, in this order: the seat (:func:`seat_provenance`), the
    sketch-authoring and modal-hazard preferences with their per-document bucket,
    ``ISketchManager``'s sticky session state (which OVERRIDES those
    preferences), the screen-space view geometry that decides whether a snap can
    resolve at all (:func:`display_geometry`), SolidWorks' own error surface, the
    document, the sketch census, then the artefacts.

    ``sketch`` selects the sketch to census: a name, a live dispatch, or omitted
    for the document's last profile sketch. ``expected_points`` is the number of
    DISTINCT sketch points the author expects when every coincident endpoint
    merged (9 for the 91247A720 logo ring, 18 if nothing merged); passing it lets
    the artefact state the discrepancy instead of leaving the reader to count.
    Extra keyword arguments are recorded as attributes on the span, the events
    and the log record.
    """
    slug = _slug(label)
    stamp = datetime.now(UTC)
    out_dir = OUT_FAILURES / slug / stamp.strftime("%Y%m%dT%H%M%SZ")
    # Caller context, with any key the telemetry helpers own renamed rather than
    # dropped (see _attributes_of).
    extra = _attributes_of(context)
    report: dict[str, Any] = {
        "label": label,
        "message": message,
        "api": api,
        "captured_at": stamp.isoformat(timespec="seconds"),
        "failure_dir": str(out_dir),
        "context": extra,
    }
    try:
        with _telemetry.span(
            f"com.failure {label}", label=label, api=api or "unknown", **extra
        ):
            _capture_step(report, "seat", lambda: seat_provenance(adapter))
            _capture_step(
                report, "preferences", lambda: sketch_authoring_preferences(adapter)
            )
            # Read BEFORE the document/sketch probes touch anything: these two
            # bags are what a preference-only snapshot misses entirely.
            _capture_step(
                report, "sketch_manager", lambda: sketch_manager_state(adapter)
            )
            _capture_step(report, "display", lambda: display_geometry(adapter))
            _capture_step(report, "error_state", lambda: _seat_error_state(adapter))
            _capture_step(report, "document", lambda: _document_state(adapter))
            _capture_step(
                report, "sketch", lambda: _sketch_state(adapter, sketch, expected_points)
            )
            _capture_step(
                report, "document_copy", lambda: _save_failure_document(adapter, out_dir, slug)
            )
            _capture_step(
                report, "seat_image", lambda: _save_seat_image(adapter, out_dir, slug)
            )
            _capture_step(report, "artefacts", lambda: _write_failure_report(out_dir, report))
    except Exception as exc:  # noqa: BLE001 - see guarantee 1
        report["capture_aborted"] = f"{type(exc).__name__}: {exc}"
    with contextlib.suppress(Exception):
        _telemetry.error(
            f"[forensics] {label}: {message}",
            **{
                **extra,
                "label": label,
                "api": api or "unknown",
                "failure_dir": str(out_dir),
                "capture": json.dumps(report, default=str, sort_keys=True),
            },
        )
    raise exc_type(message)


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
        _telemetry.event("sketch.closure", **_attributes_of(short))
    return verdict


def run_build(build: Callable[[Any], Awaitable[dict[str, str]]]) -> int:
    """Connect, run ``build(adapter)``, disconnect; return a process exit code."""
    from solidworks_mcp.adapters.pywin32_adapter import PyWin32Adapter

    # Build output carries non-ASCII (e.g. the "A ∩ B" named-axis labels). When
    # stdout is redirected to a file/pipe Windows defaults it to cp1252, so the
    # first such print would raise UnicodeEncodeError and abort the build. Force
    # UTF-8 so a piped from-scratch build doesn't depend on PYTHONUTF8=1.
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")

    script = Path(sys.argv[0]).stem if sys.argv and sys.argv[0] else "build"
    # The part/assembly/drawing this process is building -- surfaced in the span
    # NAMES so the trace title + waterfall say WHICH target is processing, not a
    # generic "build". A part script is build_<stem>.py; an assembly script is
    # build_<stem>_assembly.py; a drawing script is draw_<stem>.py;
    # refresh_assembly.py takes the stem as argv[1].
    if script == "refresh_assembly" and len(sys.argv) > 1:
        target = sys.argv[1].removesuffix(".SLDASM").replace("_", "-")
    elif script.startswith("draw_"):
        target = script.removeprefix("draw_")
    else:
        target = script.removeprefix("build_").removesuffix("_assembly")

    # Which pipeline stage this process is. ``run_build`` is also the entry for
    # non-BUILD tools (verify.py, export_models.py, the diagnostics/ probes); a
    # build_<stem>.py / build_<stem>_assembly.py / refresh_assembly.py is a genuine
    # part/assembly build, and a draw_<stem>.py is a drawing build. ``kind`` (None
    # for the non-build tools) drives BOTH the build-body grouping span below and the
    # fallback resource label -- the non-build entries set their own richer label
    # (verify: verify-<suite>) or inherit dodo's.
    if script == "refresh_assembly":
        kind: str | None = "assembly"
    elif script.startswith("build_"):
        kind = "assembly" if script.endswith("_assembly") else "part"
    elif script.startswith("draw_"):
        kind = "drawing"
    else:
        kind = None
    # Resource label (Aspire "resource" column): dodo sets OTEL_SERVICE_NAME per
    # subprocess, so under the spine this is a fallback-only no-op that KEEPS dodo's
    # precise stage name; run standalone it self-labels so the column is still
    # meaningful -- part-build / assembly-build, and drawing-export (matching dodo's
    # ``_stage_name`` for ``drawing:`` tasks) for a drawing.
    if kind == "drawing":
        _telemetry.set_service("drawing-export")
    elif kind is not None:
        _telemetry.set_service(f"{kind}-build")

    async def _run() -> dict[str, str]:
        # Runtime successor to dodo's removed ``_assert_spine_complete`` tripwire:
        # a COM build launched BY doit (which injects TRACEPARENT into every child)
        # must hold the single SolidWorks seat lock -- dodo's ``_com_seat`` sets
        # HARMONIC_COM_SEAT while held. If a doit-launched COM process reaches connect
        # WITHOUT it, some COM task is missing its ``_com_seat`` wrapper and would race
        # the STA seat -- fail loud rather than corrupt it. A standalone run (no
        # TRACEPARENT) is exempt, so hand-run build/diagnostic scripts still work.
        if os.environ.get("TRACEPARENT") and not os.environ.get("HARMONIC_COM_SEAT"):
            raise RuntimeError(
                "COM build launched under doit without holding the SolidWorks seat "
                "(HARMONIC_COM_SEAT unset) -- a COM task is missing _com_seat(); "
                "see dodo.py._com_seat"
            )
        # Crash/hang protection for the whole COM session (see _watchdog.py):
        # a new sldexitapp.exe (SolidWorks' crash-report dialog) or 15 min of
        # telemetry silence hard-exits this process so the doit parent can fail
        # the task and release the seat lock; a hung SW window only logs.
        adapter = PyWin32Adapter({})
        _watchdog.start()
        try:
            async with _telemetry.aspan("sw.connect"):
                _telemetry.info("connecting to SolidWorks")
                # Sample the seats already running BEFORE connecting: COM starts
                # SolidWorks when none is running, so this is the only moment at
                # which "did this build start the seat, or attach to one someone
                # left?" can still be answered (see note_seats_before_connect).
                note_seats_before_connect()
                await adapter.connect()
                _telemetry.success("connected")
                # WHICH sldworks.exe is about to build this target, how old it is
                # and how big: the attribution a "failed once, passed on retry"
                # leaf needs, recorded before any build work can fail.
                provenance = record_seat_provenance(adapter)
                # Re-runnable: a previous (possibly failed) build — or a human
                # inspecting an artefact in the UI — leaves documents open, and
                # saving over (or deleting) an open path fails. Verified, not
                # best-effort: a document that refuses to close would surface later
                # as an opaque save/permission error mid-build. Discard by title
                # first (a crashed build leaves DIRTY documents, and a bare
                # ``CloseAllDocuments(True)`` pops the save modal for a dirty
                # referenced child -- headless, forever). Only cad/out residents
                # count, hidden ones included: a hidden referenced part still
                # share-locks its file, while Toolbox library parts (e.g. `binding
                # head screw_ai.sldprt` behind a Hole Wizard insert) live outside
                # cad/out and are residents CloseAllDocuments never releases.
                discard_open_documents(adapter)
                holding = _resident_output_documents(adapter)
                if holding:
                    raise RuntimeError(
                        f"{len(holding)} cad/out document(s) still open after "
                        f"discard_open_documents: {holding}"
                    )
                _telemetry.success("all documents closed (clean session)")
                _pin_default_part_template(adapter)
            # Group the build's own operations (inserts, the mate chokepoint, the
            # per-config gates) under ONE ``<kind>.build`` phase span, a sibling of
            # sw.connect/sw.disconnect. This is deliberately NOT the removed
            # ``build.<target>`` ROOT layer (which mirrored the doit task span 1:1):
            # it is an inner PHASE that separates the build proper from
            # connect/teardown, so e.g. the ~40 mate spans read as children of
            # "assembly.build drive-train" instead of a flat run under the task span.
            # Non-build entries (verify/export/probes) keep their operations flat.
            if kind is None:
                return await build(adapter)
            # The provenance rides the phase span, so every operation of this
            # build hangs under a span that names the seat that ran it.
            async with _telemetry.aspan(f"{kind}.build", target=target, **provenance):
                return await build(adapter)
        finally:
            # Teardown is its own span so a disconnect failure is attributable
            # and never a silent gap before process exit. The watchdog stop is
            # outermost so telemetry teardown cannot leave it armed.
            #
            # Leave the seat holding NO cad/out document. SolidWorks keeps every
            # document the build touched resident after the COM session ends --
            # a part after its own build, the (hidden) referenced models behind
            # a closed drawing, the reopened assembly and its children -- and each
            # holds a share lock on its file. The next task's cache restore runs
            # BEFORE any COM session (outside the seat, so before the connect-time
            # CloseAllDocuments above) and its extract then fails with
            # PermissionError, falling through to a local rebuild whose exact
            # ``.execution`` token no peer can reproduce: on a farm worker that
            # silently forks every dependent's cache key off the submitter's
            # (observed 2026-09-17: worker 4 rebuilt measuring_stick behind the
            # open top-assembly drawing and `cache_missing`-failed the leaf).
            # Warn-only: a document that refuses to close is a hazard for the
            # NEXT task, not a failure of this one, and connect re-checks loud.
            try:
                async with _telemetry.aspan("sw.disconnect"):
                    try:
                        discard_open_documents(adapter)
                        holding = _resident_output_documents(adapter)
                        if holding:
                            _telemetry.warn(
                                f"{len(holding)} cad/out document(s) still resident "
                                f"after teardown close: {holding}"
                            )
                        else:
                            _telemetry.success("all documents closed (seat left clean)")
                    except Exception as exc:  # noqa: BLE001
                        _telemetry.warn(f"teardown close failed: {exc}")
                    # ... and holding NO directory of this checkout either. The
                    # seat's own current directory follows the documents it
                    # opened, and on a farm worker this checkout is a source
                    # root the agent removes between leaves: a seat parked in
                    # cad/out makes an unrelated leaf's cleanup fail with
                    # WinError 32 (see release_seat_working_directory). Same
                    # warn-only reasoning as the close above.
                    #
                    # The readback is emitted under the same
                    # ``seat_working_directory`` key ``_telemetry``'s seat
                    # provenance uses, which samples at CONNECT: one query then
                    # reads both ends -- where a leaf left the seat, and where
                    # the next leaf found it.
                    try:
                        left = release_seat_working_directory(adapter.swApp)
                        if left is not None:
                            _telemetry.success(
                                f"seat working directory moved to {left}",
                                seat_working_directory=left,
                            )
                    except Exception as exc:  # noqa: BLE001
                        _telemetry.warn(
                            f"seat working directory re-point failed: {exc}"
                        )
                    try:
                        await adapter.disconnect()
                        _telemetry.success("disconnected")
                    except Exception as exc:  # noqa: BLE001
                        _telemetry.warn(f"disconnect failed: {exc}")
            finally:
                # COM session over: stop the watchdog so a long SolidWorks-free
                # tail (pure-python post-processing) can't trip the idle timeout.
                _watchdog.stop()

    # build_session continues the doit task span when one was injected (so we add
    # no duplicate root layer under the spine) and opens a local root only when run
    # standalone -- named per-target (build.<target>) so a standalone trace title
    # says WHICH part. Either way every connect/operation/disconnect span has a
    # parent: one gapless trace from process start to exit.
    with _telemetry.build_session(target, script=script) as root:
        try:
            artefacts = asyncio.run(_run())
        except Exception as exc:  # noqa: BLE001 - recorded on the root span
            # A bare `return` would let the root exit cleanly and be marked OK, so
            # a failed build (process exits 1) would trace as success. Mark ERROR
            # before returning -- span() only fills OK when the status is UNSET, so
            # it sticks. Under the spine root is None: the build's failing
            # operation span already carries ERROR, and the doit task span goes
            # ERROR via the subprocess exit code.
            if root is not None:
                root.record_exception(exc)
                root.set_status(
                    _telemetry.Status(_telemetry.StatusCode.ERROR, str(exc))
                )
            _telemetry.error(f"build {script} failed: {exc}", exc_info=True)
            rc = 1
        else:
            _telemetry.success(f"done in {time.perf_counter() - _T0:.1f}s")
            for key, value in artefacts.items():
                _telemetry.info(f"artefact {key}: {value}")
            rc = 0
    # Flush AFTER the build_session `with` has closed the root span -- shutting the
    # providers down inside the block would tear down the exporters before the
    # ERROR root span is ended/exported, losing exactly the failure trace.
    _telemetry.shutdown()
    return rc
