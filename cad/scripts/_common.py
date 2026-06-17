"""Shared infrastructure for the part reproduction scripts.

Every part/assembly in ``cad/out`` is built by a ``build_<part>.py`` script in
this directory that drives SolidWorks through the ``PyWin32Adapter`` from the
SolidworksMCP-python repo (expected as a sibling checkout at
``C:/src/SolidworksMCP-python``, overridable via ``SOLIDWORKS_MCP_ROOT``).

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
import struct
import sys
import time
import traceback
from collections.abc import Awaitable, Callable, Iterable
from pathlib import Path
from typing import Any

CAD_ROOT = Path(__file__).resolve().parents[1]
OUT_SLDPRT = CAD_ROOT / "out" / "sldprt"
OUT_SLDASM = CAD_ROOT / "out" / "sldasm"
OUT_PNG = CAD_ROOT / "out" / "png"
OUT_STL = CAD_ROOT / "out" / "stl"

SW_MCP_ROOT = Path(os.environ.get("SOLIDWORKS_MCP_ROOT", r"C:\src\SolidworksMCP-python"))
sys.path.insert(0, str(SW_MCP_ROOT / "src"))

IN = 25.4  # inch -> mm

# Roller-chain link component prefixes; contact between two of these is an
# articulating-mechanism contact, not an interference fault (check_no_interference).
_CHAIN_LINK_PREFIXES = ("chain-inner-link", "chain-outer-link")

DEFAULT_VIEWS = ("front", "top", "isometric")


_T0 = time.perf_counter()
_LAST_TICK = _T0


def _stamp() -> str:
    """``[total +step]`` wall-clock prefix; step = time since the last log."""
    global _LAST_TICK
    now = time.perf_counter()
    prefix = f"[{now - _T0:7.1f}s +{now - _LAST_TICK:5.1f}s]"
    _LAST_TICK = now
    return prefix


def log(message: str) -> None:
    """Timestamped, unbuffered progress line (stdout is redirected when the
    build runs in the background, so unflushed prints sit in the pipe and the
    build looks hung)."""
    print(f"  ..  {_stamp()} {message}", flush=True)


def check(label: str, result: Any) -> Any:
    """Raise when an adapter result is not success; return ``result.data``."""
    if not result.is_success:
        raise RuntimeError(f"{label} failed: {result.error}")
    print(f"  OK  {_stamp()} {label}", flush=True)
    return result.data


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
                print(f"  ..  check payload: {res.data!r}")
            return state
        return None

    state = await _state()
    if state == "fully_defined":
        print(f"  OK  fully defined: {label}")
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
    print(
        f"  !!  WARN {label}: fix escalation (equation-curve whitelist only"
        " — anything else must use semantic anchors)"
    )
    for entity_id in fix_entities:
        if state not in ("under_defined", "unknown"):
            break
        fixed = await adapter.add_sketch_constraint(entity_id, None, "fix")
        if not fixed.is_success:
            raise RuntimeError(f"{label}: fix {entity_id} failed: {fixed.error}")
        state = await _state()
        print(f"  ..  fixed {entity_id} -> {state}")
        if state == "fully_defined":
            print(f"  OK  fully defined after fixing {entity_id}: {label}")
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


async def define_polygon_chain(
    adapter: Any,
    lines: list[str],
    points: list[tuple[float, float]],
    anchor: int = 0,
    label: str = "polygon",
) -> None:
    """Fully define a CLOSED line chain of arbitrary slopes semantically.

    Vertex ``anchor`` goes to the origin; every segment then pins its end
    relative to its start via :func:`anchor_point_to_point` — except the
    segment ENDING at the anchored vertex, whose span the closure supplies
    (dimensioning it too over-defines the sketch). Prefer
    :func:`define_rectilinear_chain` for axis-parallel chains: it emits
    segment-length dims instead of per-axis offsets.
    """
    n = len(lines)
    if n != len(points):
        raise ValueError(
            f"{label}: need a closed chain (lines {n} != points {len(points)})"
        )
    await anchor_point_to_origin(
        adapter, f"{lines[anchor]}.start", *points[anchor], f"{label} anchor"
    )
    skip = (anchor - 1) % n  # the segment ending at the anchored vertex
    for i, line in enumerate(lines):
        if i == skip:
            continue
        (x1, y1), (x2, y2) = points[i], points[(i + 1) % n]
        await anchor_point_to_point(
            adapter, f"{line}.start", f"{line}.end", x2 - x1, y2 - y1, f"{label} {line}"
        )


async def define_circle(
    adapter: Any, x: float, y: float, radius: float, label: str
) -> str:
    """Add a circle, anchor its centre to the origin semantically, then add
    a DRIVING diameter dimension. No ``fix`` involved."""
    circle = await adapter.add_circle(x, y, radius)
    check(f"add_circle {label}", circle)
    await anchor_point_to_origin(adapter, f"{circle.data}.center", x, y, label)
    check(
        f"dimension {label} diameter",
        await adapter.add_sketch_dimension(circle.data, None, "diameter", radius * 2.0),
    )
    return circle.data


async def add_line_chain(
    adapter: Any, points: list[tuple[float, float]], close: bool = True
) -> list[str]:
    """Draw consecutive lines through ``points`` and return their entity IDs."""
    vertices = list(points) + ([points[0]] if close else [])
    ids: list[str] = []
    for (x1, y1), (x2, y2) in zip(vertices, vertices[1:], strict=False):
        result = await adapter.add_line(x1, y1, x2, y2)
        ids.append(check(f"add_line ({x1:g},{y1:g})->({x2:g},{y2:g})", result))
    return ids


async def define_rectilinear_chain(
    adapter: Any,
    lines: list[str],
    points: list[tuple[float, float]],
    anchor: int = 0,
    label: str = "chain",
) -> None:
    """Fully define a CLOSED axis-parallel line chain semantically.

    ``lines``/``points`` are :func:`add_line_chain` output and input (line i
    runs points[i] -> points[i+1], wrapping). Every segment gets its
    horizontal/vertical relation; every segment except the LAST one of each
    direction gets a driving point-pair distance dim — closure makes one dim
    per direction redundant, and adding it over-defines the sketch. Vertex
    ``anchor`` is the chain's single origin anchor (one-anchor rule, see the
    module docstring).
    """
    n = len(lines)
    if n != len(points):
        raise ValueError(f"{label}: need a closed chain (lines {n} != points {len(points)})")
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
    await anchor_point_to_origin(
        adapter, f"{lines[anchor]}.start", *points[anchor], f"{label} anchor"
    )


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

    def _flag(obj: Any, iface: str) -> None:
        try:
            sw_type_info.flag_methods(obj, iface)
        except Exception:
            pass

    _flag(adapter.currentModel, "IModelDoc2")
    found = ""
    feat = _read_member(adapter.currentModel, "FirstFeature")
    for _ in range(5000):
        if not feat:
            break
        _flag(feat, "IFeature")
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
    print(f"  OK  blanked sketch {sketch_name}")


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
    print(f"  OK  sketch AddToDB = {enabled}")


def insert_helix(
    adapter: Any, height: float, pitch: float, clockwise: bool = True
) -> str:
    """Create a helix from the OPEN base-circle sketch; return the feature name.

    Raw-COM stopgap (``IModelDoc2::InsertHelix``, height & pitch mode) until
    Phase 3 reference geometry lands. ``height``/``pitch`` are millimetres.
    The helix starts on the +X side of the base circle.
    """
    adapter.currentModel.InsertHelix(
        False, clockwise, False, False, 2, height / 1000.0, pitch / 1000.0, 0.0, 0.0, 0.0
    )
    adapter.currentModel.ClearSelection2(True)
    name = feature_name_by_type(adapter, "Helix")
    if not name:
        raise RuntimeError("InsertHelix did not create a helix feature")
    print(f"  OK  insert_helix -> {name}")
    return name


async def add_spring_end_hooks(
    adapter: Any,
    mean_radius: float,
    wire_dia: float,
    body_length: float,
    leads: tuple[float, float] | None = None,
) -> None:
    """Sweep a bent-wire end hook onto each end of a +Y helical coil body.

    Extension-spring hooks (book pp. 41, 45): each is a straight axial lead
    (default 2 x wire dia; override per end via ``leads`` = (bottom, top) --
    the counter spring's bottom wire drops ~47 mm to the summing-lever boss
    ring) continuing the coil end, then a tangent 270-degree loop
    arc at the coil's mean radius, drawn in the Front plane -- a whole-coil
    helix starts AND ends at +X, z=0, so both end points already lie there.
    The loop's open end tucks back through the coil bore (no wire clash:
    it passes near the axis).

    The bottom hook's wire profile sits on the Top plane; the top hook's
    needs an offset reference plane at the coil's far end (the Phase 3
    capability the hooks were deferred for). Offset direction is attempted
    +normal first; if the sweep can't pierce that profile, the plane is
    rebuilt flipped and the sweep retried (the dead sketch/plane stay in
    the tree -- harmless, never consumed).

    The path is a vertical lead line plus a tangent 270-degree arc.
    (Historically these were equation-driven curves: a ``fix`` on a line
    or arc pins the curve but its endpoints still slide along the fixed
    locus. With sketch points addressable the path is defined
    semantically -- the loop's one genuine DOF, the open end's angle, is
    pinned by a ``vertical_points`` relation to the loop centre.)

    Each sweep is volume-asserted: Pappus gives the exact added volume for
    a planar path; the junction where the hook tube merges into the coil
    end may absorb up to a full Steinmetz lens (16 r^3 / 3).
    """
    from solidworks_mcp.adapters.base import (
        CreatePlaneParameters,
        SweepParameters,
    )

    loop_r = mean_radius
    default_lead = 2.0 * wire_dia
    lead_by_end = leads if leads is not None else (default_lead, default_lead)
    wire_area = math.pi * (wire_dia / 2.0) ** 2
    max_overlap = 16.0 * (wire_dia / 2.0) ** 3 / 3.0

    async def _volume() -> float:
        res = await adapter.get_mass_properties()
        if not res.is_success:
            raise RuntimeError(f"get_mass_properties failed: {res.error}")
        return float(res.data.volume)

    async def _profile(plane: str, label: str) -> None:
        check(f"create_sketch {label} hook profile", await adapter.create_sketch(plane))
        await define_circle(adapter, mean_radius, 0.0, wire_dia / 2.0, f"{label} hook wire")
        await ensure_fully_defined(adapter, f"{label} hook profile")
        check(f"exit_sketch {label} hook profile", await adapter.exit_sketch())

    for (label, y_end, d), lead in zip(
        (("bottom", 0.0, -1.0), ("top", body_length, 1.0)), lead_by_end, strict=True
    ):
        # Path: axial lead line from the helix end, tangent 270-degree loop
        # (clockwise for the bottom hook, counter-clockwise for the top, so
        # the loop extends axially outward).
        v_hook = (lead + 1.5 * math.pi * loop_r) * wire_area
        p1 = (mean_radius, y_end + d * lead)
        c = (mean_radius - loop_r, p1[1])
        open_pt = (c[0], c[1] - d * loop_r)  # 270 deg around from the junction
        path_name = check(
            f"create_sketch {label} hook path", await adapter.create_sketch("Front")
        )
        set_sketch_direct_db(adapter, True)
        lead_line = check(
            f"{label} hook lead",
            await adapter.add_line(mean_radius, y_end, p1[0], p1[1]),
        )
        # add_arc draws CCW: below the coil (d < 0) the 270-degree loop runs
        # open end -> junction, above it junction -> open end.
        if d < 0:
            loop_arc = check(
                f"{label} hook loop",
                await adapter.add_arc(
                    c[0], c[1], open_pt[0], open_pt[1], p1[0], p1[1]
                ),
            )
            open_ref = f"{loop_arc}.start"
        else:
            loop_arc = check(
                f"{label} hook loop",
                await adapter.add_arc(
                    c[0], c[1], p1[0], p1[1], open_pt[0], open_pt[1]
                ),
            )
            open_ref = f"{loop_arc}.end"
        set_sketch_direct_db(adapter, False)
        # 7-DOF path (line 4 + arc 5 - the merged junction): vertical lead
        # anchored to the origin with its length dimensioned, tangency at
        # the junction, the loop radius, and the open end pinned directly
        # across the loop centre (the arc's radius intrinsic does the rest).
        check(
            f"{label} hook lead vertical",
            await adapter.add_sketch_constraint(lead_line, None, "vertical"),
        )
        await anchor_point_to_origin(
            adapter,
            f"{lead_line}.start",
            mean_radius,
            y_end,
            f"{label} hook lead start",
        )
        check(
            f"{label} hook lead length",
            await adapter.add_sketch_dimension(lead_line, None, "linear", lead),
        )
        check(
            f"{label} hook tangent",
            await adapter.add_sketch_constraint(lead_line, loop_arc, "tangent"),
        )
        check(
            f"{label} hook loop radius",
            await adapter.add_sketch_dimension(loop_arc, None, "radial", loop_r),
        )
        check(
            f"{label} hook open end over centre",
            await adapter.add_sketch_constraint(
                open_ref, f"{loop_arc}.center", "vertical_points"
            ),
        )
        await ensure_fully_defined(adapter, f"{label} hook path")
        check(f"exit_sketch {label} hook path", await adapter.exit_sketch())

        if d > 0:
            plane = check(
                "create_plane top hook profile",
                await adapter.create_plane(
                    CreatePlaneParameters(
                        mode="offset", base_plane="Top Plane", offset=body_length
                    )
                ),
            )
            profile_plane = getattr(plane, "name", plane)
        else:
            profile_plane = "Top Plane"
        await _profile(profile_plane, label)

        before = await _volume()
        res = await adapter.create_sweep(SweepParameters(path=path_name))
        if not res.is_success and d > 0:
            print(f"  ..  top hook sweep failed ({res.error}); flipping profile plane")
            plane = check(
                "create_plane top hook profile (flipped)",
                await adapter.create_plane(
                    CreatePlaneParameters(
                        mode="offset",
                        base_plane="Top Plane",
                        offset=body_length,
                        flip=True,
                    )
                ),
            )
            await _profile(getattr(plane, "name", plane), f"{label} (flipped)")
            res = await adapter.create_sweep(SweepParameters(path=path_name))
        check(f"sweep {label} hook", res)

        added = await _volume() - before
        # Upper bound 1%: planar-path Pappus is exact analytically, but the
        # mass-properties integrator came back +0.34% on the top hook live.
        # `added` is a difference of two whole-part reads, so the helix
        # body's re-tessellation wobble leaks in -- +0.017% of a 14k mm^3
        # coil (counter spring) is +2.4 mm^3 on a 166 mm^3 hook. Slack at
        # 0.03% of the pre-hook volume covers it with 2x margin while
        # staying far below a real shape error (~10% of the hook).
        slack = 0.0003 * before
        if not (v_hook - max_overlap - slack <= added <= 1.01 * v_hook + slack):
            raise RuntimeError(
                f"{label} hook: added {added:.2f} mm^3, expected "
                f"{v_hook:.2f} (overlap allowance {max_overlap:.2f}, "
                f"tessellation slack {slack:.2f})"
            )
        print(
            f"  OK  {label} hook: added {added:.2f} mm^3 "
            f"(Pappus {v_hook:.2f}, overlap allowance {max_overlap:.2f}, "
            f"slack {slack:.2f})"
        )


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
    print(f"  OK  {label}: volume {volume:.1f} mm^3 (analytic {expected:.1f})")
    return volume


def lens_area(groove_r: float, body_r: float) -> float:
    """Two-circle lens area: groove circle centred ON a body of radius R.

    Cross-section a groove cutter of radius ``groove_r`` removes when its
    centre rides the body surface (centre distance d = R) -- the reeding /
    fluting recipe (tube-frame columns, screw heads).
    """
    r, big, d = groove_r, body_r, body_r
    a_small = r * r * math.acos((d * d + r * r - big * big) / (2.0 * d * r))
    a_big = big * big * math.acos((d * d + big * big - r * r) / (2.0 * d * big))
    a_tri = 0.5 * math.sqrt(
        (-d + r + big) * (d + r - big) * (d - r + big) * (d + r + big)
    )
    return a_small + a_big - a_tri


async def add_reeded_head_and_thread(
    adapter: Any,
    head_dia: float,
    head_length: float,
    shank_dia: float,
    shank_length: float,
    groove_count: int,
    groove_dia: float = 1.0,
    thread_size: str = "M3x0.5",
) -> None:
    """Reed a screw head and add a cosmetic thread to its shank.

    For the thumb/set screws (axis +X, head face at x=0, shank ending at
    x = head_length + shank_length): one axial groove cut at the head OD
    (Right-plane seed sketch), circular-patterned about the X axis --
    the proven tube-frame fluting recipe -- then a cosmetic (annotation)
    thread on the shank's end edge. Volume asserted analytically per step;
    the cosmetic thread adds no geometry.
    """
    from solidworks_mcp.adapters.base import (
        AddThreadParameters,
        CircularPatternParameters,
        CreateAxisParameters,
        ExtrusionParameters,
    )

    async def _volume() -> float:
        res = await adapter.get_mass_properties()
        if not res.is_success:
            raise RuntimeError(f"get_mass_properties failed: {res.error}")
        return float(res.data.volume)

    before = await _volume()
    v_groove = lens_area(groove_dia / 2.0, head_dia / 2.0) * head_length

    check("create_sketch reeding seed", await adapter.create_sketch("Right"))
    set_sketch_direct_db(adapter, True)
    await define_circle(adapter, head_dia / 2.0, 0.0, groove_dia / 2.0, "reeding seed")
    set_sketch_direct_db(adapter, False)
    await ensure_fully_defined(adapter, "reeding seed sketch")
    check("exit_sketch reeding seed", await adapter.exit_sketch())
    groove_cut = await adapter.create_cut_extrude(
        ExtrusionParameters(depth=head_length)
    )
    check("cut reeding seed", groove_cut)
    after_seed = await _volume()
    if abs(after_seed - (before - v_groove)) > 0.02 * v_groove:
        raise RuntimeError(
            f"reeding seed: volume {after_seed:.2f}, expected "
            f"{before - v_groove:.2f} -- cut direction or lens math wrong"
        )
    print(f"  OK  reeding seed: removed {before - after_seed:.2f} mm^3 (analytic {v_groove:.2f})")

    # The screw's axis is buried inside solid material, so point-projected
    # axis selection picks the body face in front of it (live failure) --
    # select the reference axis by NAME instead (MCP PR #47).
    axis = check(
        "create_axis X (Front x Top)",
        await adapter.create_axis(
            CreateAxisParameters(mode="two_planes", planes=["Front Plane", "Top Plane"])
        ),
    )
    # The blank must be EXTRUDED, not revolved: circular patterns of cuts
    # on stepped revolved bodies fail to create (probe_reed1-3 live: plain
    # revolved cylinder OK, stepped revolve fails at any depth with either
    # geometry_pattern value; identical stepped geometry from coaxial
    # extrusions patterns fine).
    check(
        f"reeding pattern about {axis.name}",
        await adapter.circular_pattern_feature(
            CircularPatternParameters(
                axis_name=axis.name,
                features=[groove_cut.data.name],
                count=groove_count,
                geometry_pattern=True,
            )
        ),
    )
    after_pattern = await _volume()
    expected = before - groove_count * v_groove
    if abs(after_pattern - expected) > 0.02 * groove_count * v_groove:
        raise RuntimeError(
            f"reeded head: volume {after_pattern:.2f}, expected {expected:.2f}"
        )
    print(f"  OK  reeded head: volume {after_pattern:.2f} mm^3 (analytic {expected:.2f})")

    adapter._zoom_to_fit(adapter.currentModel)
    check(
        f"cosmetic thread {thread_size}",
        await adapter.add_thread(
            AddThreadParameters(
                edge_point=[head_length + shank_length, shank_dia / 2.0, 0.0],
                standard="ansi_metric",
                size=thread_size,
                end_type="blind",
                depth=shank_length,
            )
        ),
    )
    if abs(await _volume() - after_pattern) > 1e-6:
        raise RuntimeError("cosmetic thread changed the volume -- it cut geometry")


def extrude_at_offset(
    adapter: Any, depth: float, offset: float, flip: bool = False
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
        True,  # Merge
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
    print(f"  OK  extrude_at_offset {sketch_name} @ {'-' if flip else '+'}{offset:g} -> {name}")
    return name


async def save_part_and_images(
    adapter: Any, part_name: str, views: Iterable[str] = DEFAULT_VIEWS
) -> dict[str, str]:
    """Save the part to ``cad/out/sldprt`` and PNG views to ``cad/out/png``."""
    OUT_SLDPRT.mkdir(parents=True, exist_ok=True)
    part_path = (OUT_SLDPRT / f"{part_name}.SLDPRT").resolve()
    check(f"save_file -> {part_path}", await adapter.save_file(str(part_path)))

    png_dir = OUT_PNG / part_name
    png_dir.mkdir(parents=True, exist_ok=True)
    apply_custom_properties(adapter, part_properties(part_name))
    check(f"re-save with properties -> {part_path}", await adapter.save_file(str(part_path)))

    artefacts = {"part": str(part_path)}
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
    reproducible Generator (git sha). Title is the part name. Parts absent from
    the registry get the minimal set (Title + Generator) and are flagged by the
    verify.py tolerance audit.
    """
    import _config

    props: dict[str, str] = {"Title": part_name, "Generator": f"harmonic-analyzer @ {_git_sha()}"}
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
    field_map = {
        "Number": "number", "Revision": "revision", "Material": "material",
        "Tolerance Class": "tolerance_class", "Fit Class": "fit_class",
        "Process": "process", "Confidence": "confidence",
    }
    for prop, key in field_map.items():
        if key in reg and reg[key] is not None:
            props[prop] = str(reg[key])
    return props


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
    _flag(mgr, "ICustomPropertyManager")
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


CASTING_GREEN = (0.13, 0.45, 0.42)  # sampled from the ch30 studio photos
# M6.8 photo-tuning palette, all sampled from the ch30 plates:
POLISHED_STEEL = (0.65, 0.64, 0.63)  # frame columns (p006 column average)
PANEL_BLACK = (0.08, 0.08, 0.09)  # platen board / clips / knife hardware
SPRING_BLACK = (0.12, 0.12, 0.13)  # blued spring wire (counter + channel)
STAINED_OAK = (0.16, 0.10, 0.07)  # crank handle (dark-stained wood)
PAPER_WHITE = (0.92, 0.92, 0.88)  # platen paper sheet
BAR_STEEL = (0.42, 0.41, 0.39)  # amplitude-bar curtain (p004 edge-on 0.56,
# back views read darker from shadowing; mid value chosen)


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
        from solidworks_mcp.adapters import sw_type_info

        sw_type_info.flag_methods(doc, "IPartDoc")
        bodies = doc.GetBodies2(0, True) or []  # solid bodies
        for body in bodies:
            sw_type_info.flag_methods(body, "IBody2")
            body.MaterialPropertyValues2 = values
            n_bodies += 1
    except Exception as exc:
        log(f"body colour skipped ({exc})")
    log(f"colour override {tuple(round(v, 3) for v in back)} ({n_bodies} bodies)")


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
    print(f"  OK  measure {label}: {key}={value:.4f} (expected {expected:g})")


async def report_mass_properties(adapter: Any) -> None:
    """Print volume/bounding data for the eyeball-vs-DIMENSIONS.md check."""
    res = await adapter.get_mass_properties()
    if res.is_success:
        print(f"  mass properties: {res.data!r}")
        return
    print(f"  WARN get_mass_properties failed: {res.error}")


# ---------------------------------------------------------------------------
# Assembly helpers (M6)
# ---------------------------------------------------------------------------

# swConstrainedStatus_e
# ---------------------------------------------------------------------------
# Machine-chirality mirror (M6.8). The original assembly was built as the
# mirror image of the real machine (crank at +X with the paper facing -Z;
# every ch. 30 plate and the Altgeld Hall photogrammetry put the crank at the
# viewer's RIGHT when facing the paper, i.e. machine -X). The fix reflects
# every component placement about the machine YZ plane (x -> -x) at the
# `_place()` boundary of each subassembly script, leaving all derivation
# math, solvers and checker-arbitrated slacks untouched.
#
# A reflection is not a rigid placement, so each mirrored placement is
# realised as M(T(part)) = (M o T o S)(part), valid only when S(part) == part
# for a part-local mirror symmetry S. MIRROR_PLANE declares S per part:
#
#   'x'  -- local YZ plane through the part STL bbox x-centre (default:
#           solids of revolution, x-symmetric castings, even-tooth gears
#           seeded with a tooth on local +X);
#   'z'  -- local XY plane through the bbox z-centre (flat or planar-XY
#           x-asymmetric linkages and wire forms; helix springs flip hand,
#           which is sub-visible at render scale);
#   'x0' -- local x = 0 exactly (parts whose build script is itself
#           mirrored as part of M6.8: summing-lever, magnifying-bracket,
#           pen-hanger);
#   ('x'|'z', c) -- explicit plane coordinate in mm, bypassing the STL
#           bbox (amplitude-bar: modeled cornered at origin, exactly
#           x-symmetric about BAR_WIDTH/2; its on-disk STL was a legacy
#           inch-unit export).
#
# Cosmetic asymmetries knowingly mirrored: measuring-stick engraved scale
# reads right-to-left (0.4 mm ticks), crank-arm fiducial dimple swaps face.
# Correctness is arbitrated downstream by assert_component_placed readback,
# the zero-interference gate, the analytic spring/rack/clearance gates and
# the photo comparison renders.
# ---------------------------------------------------------------------------

MIRROR_PLANE: dict[str, str | tuple[str, float]] = {
    # channel
    "amplitude-bar": ("x", 3.175),
    "rocker-arm": "z",
    "connecting-rod": "z",
    # eccentric cam: disc circle, bore and keyway are all centred on local
    # x=0 (offset only in Y), so it is exactly x-symmetric -- explicit c=0
    # avoids the STL-bbox dependency (used by the four-bar motion test rig).
    "eccentric-cam": ("x", 0.0),
    "channel-lever": "z",
    "channel-spring-installed": "z",
    # drive train
    "crank-arm": "z",
    "crank-handle": "z",
    "transgear-latch": "z",
    # odd sprocket teeth break the 'x' tooth-pattern closure; the hub is
    # z-symmetric about the bbox centre (mesh resid 0.000)
    "chain-sprocket": "z",
    # output
    "knife-stay": "z",
    "boss-hook": "z",
    "counter-spring": "z",
    "gooseneck": "z",
    # gooseneck-clamp: default 'x' (block/bore/screw-head all x-centred);
    # 'z' was invalid -- the screw head sits one-sided at local z 12..18
    # (M6.8 rebuild: 2280 mm^3 clamp-vs-gooseneck interference)
    # pinion-bar / platen-rack: stub bore and tooth grid are NOT centred
    # in the bbox x-span, but both parts are exact z-extrusions
    "pinion-bar": "z",
    "platen-rack": "z",
    "magnifying-lever": "z",
    "magnifying-clamp": "z",
    "thumb-screw": "z",
    "magnifying-vertical-rod": "z",
    "pen-v-block": "z",
    "pen-frame": "z",
    "pen-set-screw": "z",
    "column-clamp": "z",
    # plain x-symmetric slab cornered at origin; explicit c avoids the
    # STL-bbox dependency for a part newer than the legacy export set
    "platen-paper": ("x", 129.75),
    # roller-chain links: flat XY parts, exactly symmetric about local z=0
    # (plates at +-plate_z, round bodies centred on z=0); achiral, so the
    # YZ-mirror is a proper rotation. Explicit c, no STL at first build.
    "chain-inner-link": ("z", 0.0),
    "chain-outer-link": ("z", 0.0),
    # centred symmetric bar; explicit c, no STL yet at first build
    "wheel-bar": ("x", 0.0),
    # ch25 alignment-pinion set: every part exactly symmetric about its
    # local x = 0 plane (gear/rod axes, strap/block mid-planes); explicit
    # c, no STLs yet at first build
    "alignment-pinion": ("x", 0.0),
    "pinion-bracket": ("x", 0.0),
    "pinion-pivot-block": ("x", 0.0),
    "pinion-pivot-shaft": ("x", 0.0),
    "pinion-lever": ("x", 0.0),
    "pinion-lift-rod": ("x", 0.0),
    "pinion-handle": ("x", 0.0),
    # parts whose build scripts are themselves mirrored (M6.8)
    "summing-lever": "x0",
    "magnifying-bracket": "x0",
    "pen-hanger": "x0",
    # M6.9: the portal-frame rails killed the local-z symmetry the old
    # "z" entry relied on (Ry180 stand-in flipped the rails south, 1937
    # mm^3 into the measuring stick) -> re-authored machine-handed
    "a-frame": "x0",
    # M6.10 fasteners: authored in final orientation (axis along Y or Z),
    # exactly symmetric about local x = 0; explicit c, no STL at first build
    "hex-bolt": ("x", 0.0),
    "lag-screw": ("x", 0.0),
    "fillister-screw": ("x", 0.0),
    "pinch-screw": ("x", 0.0),
    "hanger-screw": ("x", 0.0),
}

_STL_BBOX_CACHE: dict[str, tuple[tuple[float, float], ...]] = {}


def stl_bbox_mm(stem: str) -> tuple[tuple[float, float], ...]:
    """((xmin, xmax), (ymin, ymax), (zmin, zmax)) of ``out/stl/<stem>.STL``
    in mm, part-local frame (export_models.py writes binary STLs in metres,
    untranslated)."""
    cached = _STL_BBOX_CACHE.get(stem)
    if cached is not None:
        return cached
    path = OUT_STL / f"{stem}.STL"
    data = path.read_bytes()
    lo = [math.inf] * 3
    hi = [-math.inf] * 3
    count = struct.unpack_from("<I", data, 80)[0] if len(data) >= 84 else -1
    if count >= 0 and len(data) >= 84 + 50 * count:
        for rec in struct.iter_unpack("<12fH", data[84 : 84 + 50 * count]):
            for base in (3, 6, 9):  # skip the facet normal
                for k in range(3):
                    v = rec[base + k]
                    if v < lo[k]:
                        lo[k] = v
                    if v > hi[k]:
                        hi[k] = v
    elif data[:5].lower() == b"solid":  # ASCII STL
        for line in data.decode("ascii", "ignore").splitlines():
            parts = line.split()
            if len(parts) == 4 and parts[0] == "vertex":
                for k in range(3):
                    v = float(parts[k + 1])
                    if v < lo[k]:
                        lo[k] = v
                    if v > hi[k]:
                        hi[k] = v
    else:
        raise RuntimeError(f"{path.name}: not a parsable STL ({count} facets?)")
    if not all(math.isfinite(v) for v in (*lo, *hi)):
        raise RuntimeError(f"{path.name}: no vertices found")
    bbox = tuple((lo[k] * 1000.0, hi[k] * 1000.0) for k in range(3))
    _STL_BBOX_CACHE[stem] = bbox
    return bbox


def rows_from_euler(rotation_deg: list[float]) -> list[list[float]]:
    """Transform2 rotation rows for adapter euler angles (applied Rx, Ry, Rz
    to row vectors -- the convention assert_component_placed reads back)."""
    a, b, g = (math.radians(v) for v in rotation_deg)
    ca, sa, cb, sb, cg, sg = (
        math.cos(a), math.sin(a), math.cos(b), math.sin(b), math.cos(g), math.sin(g),
    )
    return [
        [cb * cg, cb * sg, -sb],
        [sa * sb * cg - ca * sg, sa * sb * sg + ca * cg, sa * cb],
        [ca * sb * cg + sa * sg, ca * sb * sg - sa * cg, ca * cb],
    ]


def euler_from_rows(rows: list[list[float]]) -> list[float]:
    """Inverse of rows_from_euler (degrees). At the b = +/-90 gimbal lock the
    g = 0 representative is returned."""
    sb = max(-1.0, min(1.0, -rows[0][2]))
    b = math.asin(sb)
    if abs(sb) > 1.0 - 1e-9:
        # row1 collapses to [sin(a -+ g), cos(a -+ g), 0]; pick g = 0.
        a = math.atan2(rows[1][0] * (1.0 if sb > 0 else -1.0), rows[1][1])
        return [math.degrees(a), math.degrees(b), 0.0]
    a = math.atan2(rows[1][2], rows[2][2])
    g = math.atan2(rows[0][1], rows[0][0])
    return [math.degrees(a), math.degrees(b), math.degrees(g)]


def _mirror_xform(
    position: list[float], rows: list[list[float]], axis: int, c: float
) -> tuple[list[float], list[list[float]]]:
    """Reflect a placement about the machine YZ plane, realising the result
    as a proper transform via the part-local mirror plane ``axis``-coord = c:
    pos' = mirror_x(pos + 2c * rows[axis]), rows' = (I - 2 e e^T) R Mx."""
    shifted = [position[k] + 2.0 * c * rows[axis][k] for k in range(3)]
    pos2 = [-shifted[0], shifted[1], shifted[2]]
    rows2 = [
        [rows[i][j] * (-1.0 if (i == axis) != (j == 0) else 1.0) for j in range(3)]
        for i in range(3)
    ]
    return pos2, rows2


def mirror_placement(
    part: str,
    position: list[float],
    rotation: list[float],
    rows: list[list[float]] | None = None,
    configuration: str = "",
) -> tuple[list[float], list[float], list[list[float]]]:
    """Mirror one component placement about the machine YZ plane.

    Returns (position_mm, rotation_deg, rotation_rows) ready for
    insert_component + assert_component_placed."""
    if rows is None:
        rows = rows_from_euler(rotation)
    plane = MIRROR_PLANE.get(part, "x")
    explicit_c = None
    if isinstance(plane, tuple):
        plane, explicit_c = plane
    axis = 2 if plane == "z" else 0
    if explicit_c is not None:
        c = explicit_c
    elif plane == "x0":
        c = 0.0
    else:
        stem = f"{part}--{configuration}" if configuration else part
        try:
            bbox = stl_bbox_mm(stem)
        except FileNotFoundError:
            if not configuration:
                raise
            bbox = stl_bbox_mm(part)  # config STLs share the bbox centre
        c = 0.5 * (bbox[axis][0] + bbox[axis][1])
        if abs(c) < 2.0:
            # Parts are modeled about their functional axis, so a sub-mm
            # bbox centre is tessellation/tooth-seed noise (max seen 0.76,
            # the pivot-ball-mount's coarse ball facets), while genuine
            # mirror-plane offsets start at 3.0 (gooseneck-clamp). The
            # noise matters: line-to-line bores turn a 2c shift of microns
            # into real interference volumes (M6.8 drive-train rebuild:
            # 19 slivers up to 1.16 mm^3). Snap to the exact axis.
            c = 0.0
    pos2, rows2 = _mirror_xform(position, rows, axis, c)
    return pos2, euler_from_rows(rows2), rows2


def _selftest_mirror_math() -> None:
    cases = [
        [0.0, 0.0, 0.0],
        [90.0, 0.0, 0.0],
        [0.0, -21.0976, 0.0],
        [0.0, 0.0, 1.5],
        [13.0, 47.0, -152.0],
        [90.0, 90.0, 0.0],
        [-90.0, -90.0, 0.0],
        [180.0, 30.0, 180.0],
    ]
    for euler in cases:
        rows = rows_from_euler(euler)
        back = rows_from_euler(euler_from_rows(rows))
        drift = max(
            abs(a - b) for ra, rb in zip(rows, back, strict=True)
            for a, b in zip(ra, rb, strict=True)
        )
        if drift > 1e-9:
            raise AssertionError(f"euler roundtrip drift {drift} for {euler}")
        for axis, c in ((0, 7.25), (2, -3.5)):
            pos2, rows2 = _mirror_xform([11.0, -2.0, 5.0], rows, axis, c)
            det = (
                rows2[0][0] * (rows2[1][1] * rows2[2][2] - rows2[1][2] * rows2[2][1])
                - rows2[0][1] * (rows2[1][0] * rows2[2][2] - rows2[1][2] * rows2[2][0])
                + rows2[0][2] * (rows2[1][0] * rows2[2][1] - rows2[1][1] * rows2[2][0])
            )
            if abs(det - 1.0) > 1e-9:
                raise AssertionError(f"mirror rows not proper (det {det}) for {euler}")
            pos3, rows3 = _mirror_xform(pos2, rows2, axis, c)
            drift = max(
                max(abs(a - b) for a, b in zip(pos3, [11.0, -2.0, 5.0], strict=True)),
                max(
                    abs(a - b) for ra, rb in zip(rows3, rows, strict=True)
                    for a, b in zip(ra, rb, strict=True)
                ),
            )
            if drift > 1e-9:
                raise AssertionError(f"mirror not involutive (drift {drift}) for {euler}")


_selftest_mirror_math()


UNDER_CONSTRAINED = 2
FULLY_CONSTRAINED = 3


def _flag(obj: Any, interface: str) -> None:
    from solidworks_mcp.adapters import sw_type_info

    try:
        sw_type_info.flag_methods(obj, interface)
    except Exception:
        pass


def component_transform(adapter: Any, name: str) -> list[float]:
    """Return a component's ``Transform2`` ArrayData (rotation rows in
    [0:9], translation in metres in [9:12])."""
    component = adapter.currentModel.GetComponentByName(name)
    if component is None:
        raise RuntimeError(f"component not found for transform readback: {name!r}")
    return [
        float(v)
        for v in _read_member(_read_member(component, "Transform2"), "ArrayData")
    ]


def world_point(adapter: Any, name: str, local_mm: list[float]) -> list[float]:
    """Map a component-local point (mm) to the assembly frame (mm).

    Uses the live ``Transform2`` ArrayData: world = local·R + t. Lets callers
    locate a named bore (its sketch-local centre) in the assembly after the
    component has been placed/mated, without re-deriving the mirror algebra.
    """
    a = component_transform(adapter, name)
    r, t = a[0:9], a[9:12]
    return [
        sum(local_mm[i] * r[i * 3 + k] for i in range(3)) + t[k] * 1000.0
        for k in range(3)
    ]


def assert_component_placed(
    adapter: Any,
    name: str,
    origin_mm: list[float],
    rotation_rows: list[list[float]] | None = None,
    tol_mm: float = 0.5,
) -> None:
    """Assert a component sits at ``origin_mm`` with the given rotation.

    ``rotation_rows`` are the images of the component X/Y/Z axes in assembly
    space (``Transform2`` rows). Catches both wrong-side distance-mate flips
    (translation) and silent 180-degree plane-mate flips (rotation).
    """
    array = component_transform(adapter, name)
    actual = [array[9] * 1000.0, array[10] * 1000.0, array[11] * 1000.0]
    deltas = [abs(a - e) for a, e in zip(actual, origin_mm, strict=True)]
    if max(deltas) > tol_mm:
        raise RuntimeError(
            f"{name}: origin {actual} != expected {origin_mm} (tol {tol_mm} mm)"
        )
    if rotation_rows is not None:
        flat = [c for row in rotation_rows for c in row]
        drift = max(abs(a - e) for a, e in zip(array[0:9], flat, strict=True))
        if drift > 1e-3:
            raise RuntimeError(
                f"{name}: rotation {array[0:9]} != expected {flat} (drift {drift:.4f})"
            )
    print(f"  OK  {_stamp()} {name} placed at {[round(v, 3) for v in actual]}", flush=True)


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


def named_ref(name: str, entity_type: str) -> Any:
    """A ``MateEntityRef`` selecting an entity by qualified name."""
    from solidworks_mcp.adapters.base import MateEntityRef

    return MateEntityRef(entity_type=entity_type, name=name)


def component_named_ref(
    component: str, name: str, entity_type: str = "AXIS",
) -> Any:
    """A ``MateEntityRef`` selecting a named reference feature inside a nested
    component via ``IComponent2.GetCorresponding``.

    ``component`` is the slash path ``"sub/part"`` (e.g.
    ``"channel-1/connecting-rod-1"``); ``name`` is the part-local named feature
    (e.g. ``"Axis1"``). This is the depth-2-safe selection path: a hand-built
    ``Axis1@part@sub@title`` string resolves one level deep but returns False
    for a part nested in a flexible subassembly, whereas the adapter maps the
    base ``IFeature`` through the component's ``GetCorresponding`` (depth-
    agnostic, mirror-safe, ~600x faster than a cylindrical-face walk). See the
    phase-f-motion-study memory + PR #64.
    """
    from solidworks_mcp.adapters.base import MateEntityRef

    return MateEntityRef(entity_type=entity_type, component=component, name=name)


def bore_axis_ref(point_mm: list[float], entity_type: str = "FACE") -> Any:
    """A ``MateEntityRef`` selecting a cylindrical face/axis by a point on it.

    ``point_mm`` is in the FINAL (mirrored) machine frame -- the same frame the
    component occupies after :func:`place_component` -- so concentric /
    coincident selections land on the as-built geometry. Use a point on the
    bore wall at mid-depth; ``entity_type="AXIS"`` with a name is the fallback
    when no stable face point exists.
    """
    from solidworks_mcp.adapters.base import MateEntityRef

    return MateEntityRef(entity_type=entity_type, point=list(point_mm))


async def name_bore_axis(
    adapter: Any,
    plane_a: str,
    offset_a: float,
    plane_b: str,
    offset_b: float,
    label: str,
) -> str:
    """Create a named reference axis through a bore, view-independently.

    The axis is the intersection of two planes, each either a principal plane
    (``offset`` 0, used by name) or a plane offset from one. Coordinate
    face/edge selection is view-dependent (``SelectByID2`` picks at the screen
    projection), so an internal/occluded bore wall never selects by point; a
    name-selected axis does. Assembly mates then pick the axis as
    ``named_ref("Axis<N>@<comp>", "AXIS")``.

    Returns the new axis's resolved name (e.g. ``"Axis1"``).
    """
    from solidworks_mcp.adapters.base import (
        CreateAxisParameters,
        CreatePlaneParameters,
    )

    planes: list[str] = []
    for base, off, tag in ((plane_a, offset_a, "A"), (plane_b, offset_b, "B")):
        if abs(off) < 1e-9:
            planes.append(base)
            continue
        planes.append(
            check(
                f"plane {label} {tag} ({base} + {off:g})",
                await adapter.create_plane(
                    CreatePlaneParameters(mode="offset", base_plane=base, offset=off)
                ),
            ).name
        )
    return check(
        f"axis {label} ({planes[0]} ∩ {planes[1]})",
        await adapter.create_axis(
            CreateAxisParameters(mode="two_planes", planes=planes)
        ),
    ).name


async def _add_mate(
    adapter: Any,
    kind: str,
    entities: list[Any],
    *,
    distance: float = 0.0,
    angle: float = 0.0,
    alignment: str = "closest",
    lock_rotation: bool = False,
    gear_ratio: Iterable[float] | None = None,
    pinion_pitch_diameter: float = 0.0,
    rack_travel_per_revolution: float = 0.0,
    flip: bool = False,
) -> Any:
    from solidworks_mcp.adapters.base import AddMateParameters

    return await adapter.add_mate(
        AddMateParameters(
            mate_type=kind,
            entities=entities,
            alignment=alignment,
            flip=flip,
            distance=abs(distance),
            angle=angle,
            lock_rotation=lock_rotation,
            gear_ratio=list(gear_ratio) if gear_ratio else [],
            pinion_pitch_diameter=pinion_pitch_diameter,
            rack_travel_per_revolution=rack_travel_per_revolution,
        )
    )


async def _mate(
    adapter: Any,
    label: str,
    kind: str,
    entities: list[Any],
    *,
    verify: tuple[str, list[float]] | None = None,
    **kw: Any,
) -> Any:
    """Add a mate and ``check`` it; recover a far-side flip when ``verify`` set.

    ``verify=(comp_name, target_origin_mm)`` enables readback-and-flip: after
    the mate solves, the component origin must stay within ``_MATE_TOL_MM`` of
    ``target_origin_mm`` (it was inserted there); otherwise the mate is deleted
    and re-added flipped, then re-checked. Returns the (final) mate result data.
    """
    from solidworks_mcp.adapters.base import MateRefParameters

    res = check(label, await _add_mate(adapter, kind, entities, flip=False, **kw))
    if verify is None:
        return res
    comp_name, target_origin = verify
    array = component_transform(adapter, comp_name)
    moved = max(abs(array[9 + i] * 1000.0 - target_origin[i]) for i in range(3))
    if moved <= _MATE_TOL_MM:
        return res
    log(f"{label}: moved {moved:.2f} mm -> re-adding flipped")
    check(
        f"{label} (delete wrong side)",
        await adapter.delete_mate(MateRefParameters(name=res.get("name", ""))),
    )
    res = check(
        f"{label} (flipped)",
        await _add_mate(adapter, kind, entities, flip=True, **kw),
    )
    array = component_transform(adapter, comp_name)
    moved = max(abs(array[9 + i] * 1000.0 - target_origin[i]) for i in range(3))
    if moved > _MATE_TOL_MM:
        raise RuntimeError(f"{label}: component still off target by {moved:.2f} mm")
    return res


async def plane_distance_mate(
    adapter: Any,
    comp_name: str,
    comp_plane: str,
    base_plane: str,
    base_name: str,
    distance: float,
    target_origin: list[float],
) -> Any:
    """Plane-plane distance (or coincident, when ``distance==0``) mate.

    The structural-placement workhorse: three orthogonal calls fully define a
    grounded part against a reference part's principal planes, with far-side
    flip recovery from the inserted-on-solution transform.
    """
    kind = "distance" if abs(distance) > 1e-9 else "coincident"
    label = f"mate {comp_plane}@{comp_name} <-> {base_plane}@{base_name} d={distance:g}"
    entities = [
        named_ref(f"{comp_plane}@{comp_name}", "PLANE"),
        named_ref(f"{base_plane}@{base_name}", "PLANE"),
    ]
    return await _mate(
        adapter,
        label,
        kind,
        entities,
        distance=abs(distance),
        verify=(comp_name, target_origin),
    )


async def concentric_mate(
    adapter: Any,
    ref_a: Any,
    ref_b: Any,
    *,
    lock_rotation: bool = False,
    alignment: str = "closest",
    label: str = "concentric",
    verify: tuple[str, list[float]] | None = None,
) -> Any:
    """Concentric (coaxial) mate; ``lock_rotation`` removes the spin DOF too."""
    return await _mate(
        adapter,
        label,
        "concentric",
        [ref_a, ref_b],
        lock_rotation=lock_rotation,
        alignment=alignment,
        verify=verify,
    )


async def coincident_mate(
    adapter: Any,
    ref_a: Any,
    ref_b: Any,
    *,
    alignment: str = "closest",
    label: str = "coincident",
    verify: tuple[str, list[float]] | None = None,
) -> Any:
    """Coincident mate between two faces / planes / points."""
    return await _mate(
        adapter,
        label,
        "coincident",
        [ref_a, ref_b],
        alignment=alignment,
        verify=verify,
    )


async def distance_driver(
    adapter: Any,
    ref_a: Any,
    ref_b: Any,
    distance: float,
    *,
    label: str = "",
    verify: tuple[str, list[float]] | None = None,
) -> Any:
    """A distance mate used as a driving dimension pinning one slide DOF."""
    label = label or f"distance driver d={distance:g}"
    return await _mate(
        adapter,
        label,
        "distance",
        [ref_a, ref_b],
        distance=abs(distance),
        verify=verify,
    )


async def angle_driver(
    adapter: Any,
    ref_a: Any,
    ref_b: Any,
    angle: float,
    *,
    label: str = "",
    verify: tuple[str, list[float]] | None = None,
) -> Any:
    """An angle mate used as a driving dimension pinning one rotational DOF."""
    label = label or f"angle driver a={angle:g}"
    return await _mate(
        adapter,
        label,
        "angle",
        [ref_a, ref_b],
        angle=angle,
        verify=verify,
    )


async def spin_driver(
    adapter: Any,
    off_axis_ref: Any,
    pivot_xy: tuple[float, float],
    target_xy: tuple[float, float],
    *,
    label: str = "",
    verify: tuple[str, list[float]] | None = None,
) -> Any:
    """Pin a revolute's spin via a distance from an off-pivot bore to a plane.

    A plane-plane *angle* mate is unreliable here: a mirrored part flips its
    plane normals, so the true dihedral is ``180 - tilt`` and both flip
    solutions miss. Instead lock the better-conditioned in-plane coordinate of
    a bore that is offset from the rotation axis (``off_axis_ref``, a named
    AXIS): a Z-parallel axis's distance to the Top plane is its ``y``, to the
    Right plane its ``x``. Rotating by ``dφ`` moves the bore's ``x`` by
    ``-Δy·dφ`` and its ``y`` by ``+Δx·dφ`` (Δ = bore − pivot), so pin ``y``
    (Top) when the offset is mostly horizontal (``|Δx| ≥ |Δy|``), else ``x``
    (Right) -- whichever has the larger rotation sensitivity. ``target_xy`` is
    the bore's on-solution assembly position (see :func:`world_point`).
    """
    dx = target_xy[0] - pivot_xy[0]
    dy = target_xy[1] - pivot_xy[1]
    if abs(dx) >= abs(dy):
        plane, target = "Top Plane", target_xy[1]
    else:
        plane, target = "Right Plane", target_xy[0]
    label = label or f"spin driver via {plane} d={abs(target):g}"
    return await distance_driver(
        adapter,
        off_axis_ref,
        named_ref(plane, "PLANE"),
        abs(target),
        label=label,
        verify=verify,
    )


async def tangent_mate(
    adapter: Any,
    ref_a: Any,
    ref_b: Any,
    *,
    alignment: str = "closest",
    label: str = "tangent",
    verify: tuple[str, list[float]] | None = None,
) -> Any:
    """Tangent mate (e.g. an amplitude-bar notch riding a rocker arc)."""
    return await _mate(
        adapter,
        label,
        "tangent",
        [ref_a, ref_b],
        alignment=alignment,
        verify=verify,
    )


async def lock_mate(adapter: Any, ref_a: Any, ref_b: Any, *, label: str = "lock") -> Any:
    """Lock mate: rigidly fix two components' relative pose (e.g. crank parts)."""
    return await _mate(adapter, label, "lock", [ref_a, ref_b])


async def gear_mate(
    adapter: Any,
    ref_a: Any,
    ref_b: Any,
    ratio: Iterable[float],
    *,
    alignment: str = "closest",
    label: str = "",
) -> Any:
    """Gear mate coupling two rotations at ``ratio=[numerator, denominator]``.

    The ratio is tooth counts (driver:driven); verify the sign/direction with a
    kinematic rotate after meshing, per the plan's gear-ratio risk.
    """
    ratio = list(ratio)
    label = label or f"gear {ratio[0]:g}:{ratio[1]:g}"
    return await _mate(
        adapter, label, "gear", [ref_a, ref_b], gear_ratio=ratio, alignment=alignment
    )


async def cam_follower_mate(
    adapter: Any, cam_ref: Any, follower_ref: Any, *, label: str = "cam_follower"
) -> Any:
    """Cam-follower mate; the adapter applies the cam selection mark (8)."""
    return await _mate(adapter, label, "cam_follower", [cam_ref, follower_ref])


async def rack_pinion_mate(
    adapter: Any,
    rack_ref: Any,
    pinion_ref: Any,
    *,
    pinion_pitch_diameter: float = 0.0,
    rack_travel_per_revolution: float = 0.0,
    label: str = "rack_pinion",
    verify: tuple[str, list[float]] | None = None,
) -> Any:
    """Rack-pinion mate coupling a linear rack to a rotating pinion.

    ``rack_ref`` selects a linear rack edge/axis, ``pinion_ref`` the pinion's
    cylindrical face/axis. Set EITHER ``pinion_pitch_diameter`` (mm) OR
    ``rack_travel_per_revolution`` (mm) -- the adapter writes it into the mate
    definition (AddMate5 has no parameter for it). Verify the feed direction
    with a kinematic rotate, per the plan's gear-ratio risk.
    """
    return await _mate(
        adapter,
        label,
        "rack_pinion",
        [rack_ref, pinion_ref],
        pinion_pitch_diameter=pinion_pitch_diameter,
        rack_travel_per_revolution=rack_travel_per_revolution,
        verify=verify,
    )


async def place_component(
    adapter: Any,
    part: str,
    position: list[float],
    rotation: list[float],
    rows: list[list[float]],
    *,
    ground: bool = True,
    configuration: str = "",
    label: str = "",
) -> str:
    """Insert a part at its exact final (mirrored) transform and assert it.

    ``ground=True`` fixes the component (structure: shafts, mounts, bushings,
    supports, frame, fasteners, cosmetic springs). ``ground=False`` leaves it
    free for the caller's mates to constrain -- the moving parts whose DOF are
    driven from the crank. ``configuration`` selects a part configuration (the
    cone-gear tooth counts, the transgear-removable wheels). Either way the
    part is inserted on-solution so mate flip-recovery has a clean reference
    and the read-back assert holds.
    """
    from solidworks_mcp.adapters.base import (
        ComponentRefParameters,
        InsertComponentParameters,
    )

    position, rotation, rows = mirror_placement(
        part, position, rotation, rows, configuration
    )
    label = label or part
    path = (OUT_SLDPRT / f"{part}.SLDPRT").resolve()
    if not path.exists():
        raise RuntimeError(
            f"missing part {path}; run build_{part.replace('-', '_')}.py first"
        )
    data = check(
        f"insert {label} @ ({position[0]:.2f}, {position[1]:.2f}, {position[2]:.2f})",
        await adapter.insert_component(
            InsertComponentParameters(
                file_path=str(path),
                position=position,
                rotation=rotation,
                configuration=configuration,
            )
        ),
    )
    name = data["name"]
    if ground and not data.get("fixed"):
        check(
            f"fix {label}",
            await adapter.fix_component(ComponentRefParameters(name=name)),
        )
    assert_component_placed(adapter, name, position, rows)
    return name


def assert_components_fully_defined(adapter: Any) -> None:
    """Raise when any top-level component is neither fixed, fully defined,
    nor a pattern instance.

    ``IComponent2::GetConstrainedStatus`` returns swConstrainedStatus_e
    (2 = under, 3 = fully, 4 = over constrained). Component-pattern
    instances (chain pattern beads) report under-constrained even though
    the owning feature drives their transforms -- ``IsPatternInstance``
    exempts them; their actual positions are gate-asserted by the pattern
    creator. ``GetComponents`` hands back unflagged dispatches, so the
    IComponent2 methods must be flagged first or the call resolves as a
    property and raises.
    """
    asm = adapter.currentModel
    # Inserting/fixing a component marks the mate solver dirty: until the
    # assembly is rebuilt, GetConstrainedStatus returns a STALE swNoSolution
    # (5) for every mated part even though the mates are consistent and the
    # parts have not moved (probed live -- a ForceRebuild3 restores the true
    # status). Always re-solve before reading the gate.
    adapter._attempt(lambda: asm.ForceRebuild3(False), default=None)
    components = adapter._attempt(lambda: asm.GetComponents(True), default=None) or []
    log(f"checking {len(components)} components for free DOF ...")
    problems = []
    for component in components:
        _flag(component, "IComponent2")
        comp_name = str(_read_member(component, "Name2"))
        if bool(_read_member(component, "IsFixed")):
            log(f"{comp_name}: fixed")
            continue
        if bool(
            adapter._attempt(lambda c=component: c.IsPatternInstance(), default=False)
        ):
            log(f"{comp_name}: pattern instance (feature-driven)")
            continue
        status = int(
            adapter._attempt(lambda c=component: c.GetConstrainedStatus(), default=-1)
        )
        log(f"{comp_name}: constrained status {status}")
        if status != FULLY_CONSTRAINED:
            kind = "under" if status == UNDER_CONSTRAINED else f"status={status}"
            problems.append(f"{comp_name} ({kind})")
    print(f"  OK  {_stamp()} checked {len(components)} components for free DOF", flush=True)
    if problems:
        raise RuntimeError("components not fully defined: " + ", ".join(problems))


def component_names(adapter: Any) -> list[str]:
    """Top-level component names (``Name2``) of the active assembly."""
    asm = adapter.currentModel
    components = adapter._attempt(lambda: asm.GetComponents(True), default=None) or []
    names = []
    for component in components:
        _flag(component, "IComponent2")
        names.append(str(_read_member(component, "Name2")))
    return names


def check_no_interference(adapter: Any) -> None:
    """Run interference detection on the active assembly; raise on any hit.

    Raw-COM stopgap until the MCP adapter implements ``check_interference``
    (``IAssemblyDoc::InterferenceDetectionManager``; the tool-layer call
    currently returns a simulated result without adapter support).
    Coincident/tangent contact is not treated as interference.

    Chain-internal contact (a pair of roller-chain links touching each other)
    is allowed and reported separately, not raised: a chain is an articulating
    connected mechanism whose links are in contact at every joint, so on the
    tight wraps the rigid links unavoidably touch their neighbours (the same
    way the gate already tolerates face-flush and tangent contacts). Any link
    touching a NON-link part is still a hard fault.
    """
    asm = adapter.currentModel
    log("interference detection: starting ...")
    _flag(asm, "IAssemblyDoc")
    adapter._attempt(lambda: asm.ToolsCheckInterference(), default=None)
    mgr = _read_member(asm, "InterferenceDetectionManager")
    if mgr is None:
        raise RuntimeError("InterferenceDetectionManager unavailable")
    _flag(mgr, "IInterferenceDetectionMgr")
    mgr.TreatCoincidenceAsInterference = False
    mgr.TreatSubAssembliesAsComponents = True
    mgr.IncludeMultibodyPartInterferences = True
    mgr.MakeInterferingPartsTransparent = False
    mgr.CreateFastenersFolder = False
    mgr.UseTransform = False
    log("interference detection: computing interferences ...")
    interferences = adapter._attempt(lambda: mgr.GetInterferences(), default=None)
    details = []
    chain_contacts = []
    for interference in list(interferences or []):
        _flag(interference, "IInterference")
        names = []
        for comp in list(_read_member(interference, "Components") or []):
            _flag(comp, "IComponent2")
            names.append(str(_read_member(comp, "Name2")))
        volume_mm3 = float(_read_member(interference, "Volume") or 0.0) * 1e9
        if all(n.startswith(_CHAIN_LINK_PREFIXES) for n in names) and len(names) == 2:
            chain_contacts.append(volume_mm3)
            continue
        details.append(f"{' & '.join(names)}: {volume_mm3:.2f} mm^3")
    adapter._attempt(lambda: mgr.Done(), default=None)
    if chain_contacts:
        print(
            f"  ..  {_stamp()} {len(chain_contacts)} chain-internal link contacts"
            f" (<= {max(chain_contacts):.2f} mm^3) allowed -- articulating chain",
            flush=True,
        )
    if details:
        raise RuntimeError(
            f"{len(details)} interference(s): " + "; ".join(details)
        )
    print(f"  OK  {_stamp()} interference check: none found", flush=True)


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


def _byref_variant() -> Any:
    """An in/out ``VT_BYREF | VT_VARIANT`` for ``out object`` COM params.

    ``IModelDocExtension::GetWhatsWrong`` takes three ``out object`` arrays;
    under pywin32 late binding a bare call RAISES and bare ``None`` mis-types.
    Mirrors :func:`com_variant.byref_long`; read the filled value via ``.value``.
    """
    import pythoncom
    from win32com.client import VARIANT

    return VARIANT(pythoncom.VT_BYREF | pythoncom.VT_VARIANT, None)


def whats_wrong(adapter: Any, model: Any) -> list[tuple[str, int, bool]]:
    """Return ``[(feature_name, error_code, is_warning), ...]`` for a model.

    Reads the What's Wrong dialog via ``GetWhatsWrong`` (byref out-params).
    Empty when the model is clean or the call is unavailable.
    """
    ext = _read_member(model, "Extension")
    if ext is None:
        return []
    f, e, w = _byref_variant(), _byref_variant(), _byref_variant()

    def _call() -> tuple[Any, Any, Any]:
        ext.GetWhatsWrong(f, e, w)
        return f.value, e.value, w.value

    res = adapter._attempt(_call, default=None)
    if not res:
        return []
    feats, codes, warns = res
    feats = list(feats or [])
    codes = list(codes or [])
    warns = list(warns or [])
    out: list[tuple[str, int, bool]] = []
    for i, feat in enumerate(feats):
        name = "?"
        if feat is not None:
            _flag(feat, "IFeature")
            name = str(_read_member(feat, "Name"))
        code = int(codes[i]) if i < len(codes) else -1
        warn = bool(warns[i]) if i < len(warns) else False
        out.append((name, code, warn))
    return out


def assert_model_healthy(
    adapter: Any, *, label: str = "", model: Any = None, deep: bool = True
) -> None:
    """Force-rebuild and raise on any ERROR-state feature/mate -- fail fast.

    The motion build mutates the assembly (float, flexible, suppress, cross-sub
    mates, motor); a single failed step leaves a component with a red rebuild
    error (the drive-train red-X) that otherwise survives silently into the
    study and only surfaces as garbage motion. This names the culprit the
    instant it appears.

    A non-warning What's Wrong entry, or ``ForceRebuild3`` returning False, is a
    hard fault and raises. Warnings (under-defined flexible subs, etc.) are
    logged, not raised. With ``deep`` each top-level component's own document is
    also checked -- a flexible subassembly's internal mate error does NOT appear
    in the parent's What's Wrong, only in the sub document's.
    """
    model = model or adapter.currentModel
    _flag(model, "IModelDoc2")
    rebuilt = adapter._attempt(lambda: model.ForceRebuild3(False), default=None)

    targets = [(label or "top", model)]
    if deep:
        comps = adapter._attempt(lambda: model.GetComponents(False), default=None) or []
        for comp in comps:
            _flag(comp, "IComponent2")
            name = str(_read_member(comp, "Name2"))
            if "/" in name:  # top-level instances only; their docs cover nested parts
                continue
            sub = adapter._attempt(lambda c=comp: c.GetModelDoc2(), default=None)
            if sub is not None and sub is not model:
                targets.append((name, sub))

    errors: list[str] = []
    warnings: list[str] = []
    for tlabel, doc in targets:
        for name, code, warn in whats_wrong(adapter, doc):
            entry = f"{tlabel}:{name} [{_FEATURE_ERROR.get(code, code)}]"
            (warnings if warn else errors).append(entry)
    if rebuilt is False:
        errors.append(f"{label or 'top'}: ForceRebuild3 returned False")

    if warnings:
        print(
            f"  ..  {_stamp()} {len(warnings)} warning(s): " + "; ".join(warnings[:12]),
            flush=True,
        )
    if errors:
        raise RuntimeError(
            f"model unhealthy ({label or 'top'}): {len(errors)} error(s) -- "
            + "; ".join(errors[:20])
        )
    print(f"  OK  {_stamp()} model healthy ({label or 'top'})", flush=True)


def body_faults(adapter: Any, model: Any) -> list[tuple[str, int]]:
    """Return ``[(body_name, fault_count), ...]`` for any faulty solid bodies.

    ``IBody2.Check3`` -> ``IFaultEntity`` flags degenerate geometry (touching
    edge vertices, sub-tolerance faces/edges, poorly defined curves) that a
    rebuild can leave behind after a boolean on a near-singular feature -- the
    on-axis-revolve / 0.00 mm^3 sliver failure class. Catches part-level
    corruption that What's Wrong (feature/mate state) does not. Empty = clean.
    """
    bodies = adapter._attempt(lambda: model.GetBodies2(0, False), default=None)
    if bodies is None:
        return []
    if not isinstance(bodies, (list, tuple)):
        bodies = [bodies]
    faults: list[tuple[str, int]] = []
    for body in bodies:
        if body is None:
            continue
        _flag(body, "IBody2")
        fault = adapter._attempt(lambda b=body: b.Check3, default=None)
        if fault is None:
            continue
        _flag(fault, "IFaultEntity")
        count = int(_read_member(fault, "Count") or 0)
        if count > 0:
            faults.append((str(_read_member(body, "Name")), count))
    return faults


def remap_front_to_machine_front(adapter: Any) -> None:
    """Redefine the active document's standard views so SolidWorks ``Front``
    shows the MACHINE front (the paper/output side at -Z).

    The machine is authored in machine coordinates with the output side at -Z
    (see build_harmonic_analyzer_assembly), so SolidWorks' native Front view --
    which looks toward -Z from the +Z side -- renders the BACK. The machine front
    is exactly what SolidWorks currently calls the Back view (camera on the -Z
    side, crank at the viewer's right). ``IModelDocExtension.UpdateStandardViews``
    re-bases the whole orthographic set so that orientation becomes Front; NO
    geometry moves, so the comparison-render euler azimuth convention (az 0 = +Z)
    is untouched -- only the named standard views and the interactive open-on-Front
    change. Leaves Front active so the saved document opens on the machine front.
    """
    SW_FRONT, SW_BACK = 1, 2  # swStandardViews_e
    model = adapter.currentModel
    _flag(model, "IModelDoc2")
    model.ShowNamedView2("", SW_BACK)  # orient to the machine front
    ok = model.Extension.UpdateStandardViews("", SW_FRONT)
    if not ok:
        raise RuntimeError("UpdateStandardViews(swFrontView) returned False")
    model.ShowNamedView2("", SW_FRONT)  # activate the (now machine-front) Front
    adapter._zoom_to_fit(model)
    log("standard views remapped: Front now shows the machine front (-Z paper side)")


async def save_assembly_and_images(
    adapter: Any, asm_name: str, views: Iterable[str] = DEFAULT_VIEWS
) -> dict[str, str]:
    """Save the assembly to ``cad/out/sldasm`` and PNG views to ``cad/out/png``."""
    # Fail fast: never save a broken assembly. Catches mate errors (e.g. a gear
    # mate whose entity went suppressed = the silent drive-train corruption) that
    # the DOF and interference gates miss -- a fixed/grounded component passes
    # the DOF gate even with broken mates. deep=True also inspects each
    # subassembly's own document, where a sub's internal mate errors live.
    assert_model_healthy(adapter, label=asm_name, deep=True)
    OUT_SLDASM.mkdir(parents=True, exist_ok=True)
    asm_path = (OUT_SLDASM / f"{asm_name}.SLDASM").resolve()
    check(f"save_file -> {asm_path}", await adapter.save_file(str(asm_path)))

    png_dir = OUT_PNG / asm_name
    png_dir.mkdir(parents=True, exist_ok=True)
    artefacts = {"assembly": str(asm_path)}
    for view in views:
        img_path = (png_dir / f"{asm_name}_{view}.png").resolve()
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

    from trim_renders import trim_readme_render

    trimmed = trim_readme_render(asm_name)
    if trimmed:
        print(f"  OK  trim README render {trimmed}")
        artefacts["readme"] = trimmed.split(":")[0]
    return artefacts


def run_build(build: Callable[[Any], Awaitable[dict[str, str]]]) -> int:
    """Connect, run ``build(adapter)``, disconnect; return a process exit code."""
    from solidworks_mcp.adapters.pywin32_adapter import PyWin32Adapter

    async def _run() -> dict[str, str]:
        adapter = PyWin32Adapter({})
        print("Connecting to SolidWorks ...", flush=True)
        await adapter.connect()
        log("connected")
        # Re-runnable: a previous (possibly failed) build leaves documents
        # open, and saving over an open path fails.
        adapter._attempt(lambda: adapter.swApp.CloseAllDocuments(True), default=None)
        log("CloseAllDocuments (clean session)")
        try:
            return await build(adapter)
        finally:
            try:
                await adapter.disconnect()
                print("Disconnected.", flush=True)
            except Exception as exc:  # noqa: BLE001
                print(f"  WARN disconnect failed: {exc}", flush=True)

    try:
        artefacts = asyncio.run(_run())
    except Exception:
        traceback.print_exc()
        return 1
    print(f"\nDone in {time.perf_counter() - _T0:.1f}s. Artefacts:", flush=True)
    for key, value in artefacts.items():
        print(f"  {key}: {value}")
    return 0
