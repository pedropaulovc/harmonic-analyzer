"""Sketch definition, anchoring and dimension records.

Separate module so edits affect only recipes that use this scope.

Shared infrastructure for the part reproduction scripts.

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
  diameter (or radius, ``size_dimension="radius"``). ``fix`` is never used.
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

from collections.abc import Iterable
from typing import Any

import _telemetry
from _check import check
from _com import _early_bound, _read_member, _scalar
from _dimensions import _display_dimensions, _rename_dimensions
from _feature_tree import _feature_by_name


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
        dims = list(_display_dimensions(feature, feature_name))
        if len(dims) != len(self._rows):
            raise RuntimeError(
                f"{feature_name}: recorded {len(self._rows)} dims but the feature "
                f"has {len(dims)} -- a define_* helper's dim emission drifted from "
                "what it recorded into SketchDims"
            )
        _rename_dimensions(dims, feature_name, [name for name, _ in self._rows])
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


@_telemetry.traced("appearance.hide_reference_sketches")
def blank_reference_sketches(adapter: Any, sketches: tuple[str, ...]) -> None:
    """Blank a part's reference sketches before it is saved, and prove it.

    A dimension-carrying reference sketch stays in the part for the drawing to
    import (``_drawing_hidden_sketches`` shows it per view), but saved shown it
    prints grey dots and lines in every assembly render (#880).  Each sketch is
    read back through ``IPartDoc.FeatureByName`` and must be hidden, so a
    BlankSketch that silently did nothing fails the build.
    """
    part_doc = _early_bound(adapter.currentModel, "IPartDoc")
    for sketch in sketches:
        blank_sketch(adapter, sketch)
        feature = _early_bound(part_doc.FeatureByName(sketch), "IFeature")
        state = int(feature.Visible)
        if state != 1:  # swVisibilityState_e: swVisibilityStateHide
            raise RuntimeError(
                f"{sketch} still visible after BlankSketch (state {state})"
            )
    _telemetry.event(
        "part.reference_sketches_hidden",
        sketches=", ".join(sketches),
        count=len(sketches),
    )


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
    previous = adapter._attempt(
        lambda: bool(_read_member(manager, "AddToDB")), default=None
    )
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
