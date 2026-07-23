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
import functools
import math
import os
import sys
import time
from collections.abc import Awaitable, Callable, Iterable
from pathlib import Path
from typing import Any

import _telemetry  # observability spine: console logging + tracing, preconfigured
import _watchdog  # COM crash/hang watchdog (started per session in run_build)

CAD_ROOT = Path(__file__).resolve().parents[1]
OUT_SLDPRT = CAD_ROOT / "out" / "sldprt"
OUT_SLDASM = CAD_ROOT / "out" / "sldasm"
OUT_PNG = CAD_ROOT / "out" / "png"
OUT_STL = CAD_ROOT / "out" / "stl"
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
        raise RuntimeError(
            f"{label}: sketch not fully defined (state={state!r}){hint}"
        )

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
            await adapter.add_sketch_constraint(point_ref, "origin", "horizontal_points"),
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
        await dimension_between(adapter, ref1, ref2, "vertical_distance", abs(dy), label)
        return
    if dy == 0.0:
        check(
            f"horizontal_points {label}",
            await adapter.add_sketch_constraint(ref1, ref2, "horizontal_points"),
        )
        await dimension_between(adapter, ref1, ref2, "horizontal_distance", abs(dx), label)
        return
    await dimension_between(adapter, ref1, ref2, "horizontal_distance", abs(dx), label)
    await dimension_between(adapter, ref1, ref2, "vertical_distance", abs(dy), label)


def _record_point_to_point_cursor(rec: "Callable[[], None]", dx: float, dy: float) -> None:
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
            raise RuntimeError(f"{label}: native center rectangle has no orthogonal edge pair")
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
        raise ValueError(f"{label}: need a closed chain (lines {n} != points {len(points)})")
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
    last = {d: max(i for i, d2 in enumerate(directions) if d2 == d) for d in set(directions)}
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
    adapter.currentSketchManager.AddToDB = enabled
    _telemetry.success(f"sketch AddToDB = {enabled}")














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
        False, False,  # Dchk1/2
        False, False,  # Ddir1/2
        0.0, 0.0,  # Dang1/2
        False, False,  # OffsetReverse1/2
        False, False,  # TranslateSurface1/2
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
PREF_STL_QUALITY = 78          # swSTLQuality -> 2 = fine
PREF_STL_UNITS = 211           # swExportStlUnits -> 0 = swMM
TOGGLE_STL_BINARY = 69         # swSTLBinaryFormat
TOGGLE_STL_ONE_FILE = 72       # swSTLComponentsIntoOneFile
TOGGLE_STL_NO_TRANSLATE = 71   # swSTLDontTranslateToPositive: keep model origin
TOGGLE_STL_SHOW_INFO = 70      # swSTLShowInfoOnSave: the per-file "Save <name>.STL?" modal

_STL_INT_PREFS = {PREF_STL_QUALITY: 2, PREF_STL_UNITS: 0}
# SHOW_INFO -> False: every part build now exports an STL, so leaving the modal on
# would block an unattended `doit` run on the first export (cut_release.py disables
# it for the same reason; codex review #12).
_STL_TOGGLES = {TOGGLE_STL_BINARY: True, TOGGLE_STL_ONE_FILE: True,
                TOGGLE_STL_NO_TRANSLATE: True, TOGGLE_STL_SHOW_INFO: False}


@_telemetry.traced("export.stl")
async def export_part_stl(adapter: Any, out_path: Path) -> None:
    """Write the active part's fine binary STL (mm, model origin) to ``out_path``.

    The assembly build reads these via ``stl_bbox_mm`` to place each
    bbox-mirrored part, so a part build must emit its STL alongside the SLDPRT --
    ``export_models.py`` only refreshes the render cache and can't bootstrap a
    from-empty assembly (its part list is manifest-driven and otherwise needs an
    already-built assembly to scan). Prefs are set then restored so the export
    doesn't perturb later steps.
    """
    sw = adapter.swApp
    old_ints = {k: int(sw.GetUserPreferenceIntegerValue(k)) for k in _STL_INT_PREFS}
    old_toggles = {k: bool(sw.GetUserPreferenceToggle(k)) for k in _STL_TOGGLES}
    for k, v in _STL_INT_PREFS.items():
        sw.SetUserPreferenceIntegerValue(k, v)
    for k, v in _STL_TOGGLES.items():
        sw.SetUserPreferenceToggle(k, v)
    try:
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
    finally:
        for k, v in old_ints.items():
            sw.SetUserPreferenceIntegerValue(k, v)
        for k, v in old_toggles.items():
            sw.SetUserPreferenceToggle(k, v)


@_telemetry.traced("export.part_images", label_param="part_name")
async def save_part_and_images(
    adapter: Any, part_name: str, views: Iterable[str] = DEFAULT_VIEWS
) -> dict[str, str]:
    """Save the part to ``cad/out/sldprt``, its STL to ``cad/out/stl`` (the
    assembly build reads it for mirror placement), and PNG views to
    ``cad/out/png``."""
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
    check(f"re-save with properties -> {part_path}", await adapter.save_file(str(part_path)))

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
    active = _read_member(manager, "ActiveConfiguration") if manager is not None else None
    return str(_read_member(active, "Name") or "") if active is not None else ""


_SW_CUSTOM_TEXT = 30  # swCustomInfoType_e.swCustomInfoText
_SW_PROP_REPLACE = 2  # swCustomPropertyAddOption_e.swCustomPropertyReplaceValue


@functools.lru_cache(maxsize=1)
def _git_sha() -> str:
    """Short HEAD sha (+ '-dirty'), for a reproducible Generator stamp.

    Deterministic per source state — no wall-clock — so a rebuild from the same
    commit writes the same property (see Part D determinism decision).
    """
    import subprocess

    try:
        sha = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(CAD_ROOT), capture_output=True, text=True, check=True,
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(CAD_ROOT), capture_output=True, text=True, check=True,
        ).stdout.strip()
        return f"{sha}{'-dirty' if dirty else ''}"
    except Exception:  # noqa: BLE001 -- not in a git checkout / no git
        return "unknown"


def part_properties(part_name: str) -> dict[str, str]:
    """SolidWorks custom properties for ``part_name`` from the parts.yaml registry.

    Pulls Number/Revision/Material/Tolerance Class/Fit Class/Process/Confidence
    from ``cad/config/parts.yaml`` (merged over its defaults) and stamps a
    reproducible Generator (git sha). ``title`` may override the internal
    artifact name for a clearer manufacturing identity; parts absent from the
    registry get the minimal set (Title + Generator) and are flagged by the
    verify.py tolerance audit.
    """
    import _config

    props: dict[str, str] = {"Title": part_name, "Generator": f"harmonic-analyzer @ {_git_sha()}"}
    # Title-block general tolerances (title_block.yaml) — read by the drawing
    # template's title block via $PRPSHEET, so EVERY part carries them,
    # registered in the parts registry or not.
    props["TOL_LIN_XX"] = str(_config.title_block("linear_2pl")["display"])
    props["TOL_LIN_XXX"] = str(_config.title_block("linear_3pl")["display"])
    props["TOL_ANG"] = str(_config.title_block("angular")["display"])
    props["TOL_SURFACE"] = str(_config.title_block("surface")["display"])
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
        "Number": "number", "Revision": "revision", "Material": "material",
        "Tolerance Class": "tolerance_class", "Fit Class": "fit_class",
        "Process": "process", "Confidence": "confidence",
    }
    for prop, key in field_map.items():
        if key in reg and reg[key] is not None:
            props[prop] = str(reg[key])
    return props


# DimXpert block-tolerance document properties (Tools > Options > Document
# Properties > DimXpert), ids extracted from swconst.tlb R2026x. Values from
# title_block.yaml — the same numbers the TOL_* custom properties display in
# the drawing title block.
_PREF_DIMXPERT_METHOD = 637      # swPartDimXpertToleranceMethod -> 0 = BlockTolerance
_PREF_TOL1_DECIMALS = 405        # swPartDimXpertLengthUnitTol1Decimals (get-only, see below)
_PREF_TOL2_DECIMALS = 406        # swPartDimXpertLengthUnitTol2Decimals (get-only, see below)
_PREF_TOL1_VALUE = 123           # swPartDimXpertLengthUnitTol1Value (meters)
_PREF_TOL2_VALUE = 124           # swPartDimXpertLengthUnitTol2Value (meters)
_PREF_ANGULAR_VALUE = 126        # swPartDimXpertAngularUnitTolValue (radians; get-only, see below)
_PREF_OPT_NONE = 0               # swDetailingNoOptionSpecified
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
        ("DimXpert method=block", ext.SetUserPreferenceInteger,
         _PREF_DIMXPERT_METHOD, 0),
        ("DimXpert tol1 (.xx) value", ext.SetUserPreferenceDouble,
         _PREF_TOL1_VALUE, lin2),
        ("DimXpert tol2 (.xxx) value", ext.SetUserPreferenceDouble,
         _PREF_TOL2_VALUE, lin3),
    ]
    for label, setter, pref, value in sets:
        if not adapter._attempt(lambda: setter(pref, _PREF_OPT_NONE, value), default=False):
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
            f"metadata-drifted parts into the shared cache: {'; '.join(drift)}")


def apply_custom_properties(adapter: Any, props: dict[str, str]) -> None:
    """Write file-level custom properties via the CustomPropertyManager, verified.

    The PyWin32 adapter exposes no property writer, so this drives raw COM
    (``IModelDocExtension.CustomPropertyManager("").Add3`` with replace), then
    reads each value back through ``GetCustomInfoValue`` and raises on mismatch
    — same fail-fast posture as the build's other gates. Empty values are skipped.
    """
    model = adapter.currentModel
    ext = _read_member(model, "Extension")
    mgr = adapter._attempt(lambda: ext.CustomPropertyManager(""), default=None)
    if mgr is None:
        raise RuntimeError("CustomPropertyManager unavailable")
    mgr = _early_bound(mgr, "ICustomPropertyManager", "Add3")
    written = []
    for name, value in props.items():
        if value in (None, ""):
            continue
        text = str(value)
        adapter._attempt(
            lambda n=name, v=text: mgr.Add3(n, _SW_CUSTOM_TEXT, v, _SW_PROP_REPLACE),
            default=None,
        )
        back = str(adapter._attempt(lambda n=name: model.GetCustomInfoValue("", n), default=""))
        if back != text:
            raise RuntimeError(f"custom property {name!r} readback {back!r} != {text!r}")
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
            _PREF_DEFAULT_PART_TEMPLATE, str(PART_TEMPLATE)),
        default=False)
    got = str(adapter._attempt(
        lambda: sw.GetUserPreferenceStringValue(_PREF_DEFAULT_PART_TEMPLATE),
        default="") or "")
    if not ok or not got or Path(got).resolve() != PART_TEMPLATE.resolve():
        raise RuntimeError(
            f"failed to pin default part template: set={ok} readback={got!r}")
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
    for field, value in ((_SUMMARY_TITLE, title), (_SUMMARY_AUTHOR, PROJECT_AUTHOR)):
        model.SetSummaryInfo(field, value)
        if model.SummaryInfo(field) != value:
            raise RuntimeError(f"summary field {field} did not persist ({value!r})")
    _telemetry.success(f"summary info stamped (Title={title!r}, Author={PROJECT_AUTHOR!r})")


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
        part_h = _early_bound(doc, "IPartDoc")  # IPartDoc for GetBodies2; keep `doc` for MaterialPropertyValues
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
            default=None)
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
    _telemetry.success(f"bbox {label}: {axis}-extent={extent:.4f} (expected {expected:g})")


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


def _early_bound(obj: Any, interface: str, *method_names: str) -> Any:
    """Return a generated interface wrapper, selectively flagging as fallback.

    Early-bound wrappers invoke known DISPIDs directly and avoid the repeated
    ``GetIDsOfNames`` calls paid by whole-interface method flagging.  The exact
    names are used only when makepy metadata is unavailable, preserving support
    for deliberately minimal test doubles. A generated-wrapper construction
    failure propagates: silently returning the raw dispatch would hide a broken
    cast and reintroduce late binding on production SolidWorks objects.
    """
    from solidworks_mcp.adapters import sw_type_info

    return sw_type_info.early_bound_or_flag(obj, interface, *method_names)


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
    model = _early_bound(adapter.currentModel, "IModelDoc2", "FirstFeature")
    feat = _read_member(model, "FirstFeature")
    for _ in range(5000):
        if not feat:
            return
        feat = _early_bound(feat, "IFeature", "GetNextFeature")
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
    feat = _early_bound(
        feat,
        "IFeature",
        "GetFirstDisplayDimension",
        "GetNextDisplayDimension",
    )
    disp = _read_member(feat, "GetFirstDisplayDimension")
    for _ in range(1000):
        if not disp:
            return
        disp = _early_bound(disp, "IDisplayDimension", "GetDimension2")
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


def name_dimensions(adapter: Any, feature_name: str, names: list[str | None]) -> list[str]:
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
    model = _early_bound(adapter.currentModel, "IModelDoc2", "ShowNamedView2")
    if model is None:
        return
    adapter._attempt(lambda: model.ShowNamedView2("", SW_ISOMETRIC), default=None)
    adapter._zoom_to_fit(model)
    log("view set to isometric")


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
                "see dodo.py._com_seat")
        # Crash/hang protection for the whole COM session (see _watchdog.py):
        # a new sldexitapp.exe (SolidWorks' crash-report dialog) or 15 min of
        # telemetry silence hard-exits this process so the doit parent can fail
        # the task and release the seat lock; a hung SW window only logs.
        _watchdog.start()
        adapter = PyWin32Adapter({})
        async with _telemetry.aspan("sw.connect"):
            _telemetry.info("connecting to SolidWorks")
            await adapter.connect()
            _telemetry.success("connected")
            # Re-runnable: a previous (possibly failed) build leaves documents
            # open, and saving over an open path fails.
            adapter._attempt(lambda: adapter.swApp.CloseAllDocuments(True), default=None)
            _telemetry.success("CloseAllDocuments (clean session)")
            _pin_default_part_template(adapter)
        try:
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
            async with _telemetry.aspan(f"{kind}.build", target=target):
                return await build(adapter)
        finally:
            # Teardown is its own span so a disconnect failure is attributable
            # and never a silent gap before process exit.
            async with _telemetry.aspan("sw.disconnect"):
                try:
                    await adapter.disconnect()
                    _telemetry.success("disconnected")
                except Exception as exc:  # noqa: BLE001
                    _telemetry.warn(f"disconnect failed: {exc}")
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
                root.set_status(_telemetry.Status(_telemetry.StatusCode.ERROR, str(exc)))
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
