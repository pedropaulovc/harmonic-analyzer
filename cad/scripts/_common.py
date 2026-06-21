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
import os
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
    a DRIVING diameter dimension. No ``fix`` involved.

    The raw ``add_circle`` runs with sketch inference SUPPRESSED (restored
    afterwards): with it on, a second concentric/near circle snaps to the first
    and the call fails (proven live on the coefficients-plate hole column).
    Same rationale as :func:`add_line_chain` -- the centre/diameter are pinned
    explicitly below, so inference during the draw only ever hurts."""
    sketch_mgr = adapter.currentSketchManager
    prev_add_to_db = bool(sketch_mgr.AddToDB)
    sketch_mgr.AddToDB = True
    try:
        circle = await adapter.add_circle(x, y, radius)
        check(f"add_circle {label}", circle)
    finally:
        sketch_mgr.AddToDB = prev_add_to_db
    await anchor_point_to_origin(adapter, f"{circle.data}.center", x, y, label)
    check(
        f"dimension {label} diameter",
        await adapter.add_sketch_dimension(circle.data, None, "diameter", radius * 2.0),
    )
    return circle.data


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
        print(f"  OK  export STL -> {out_path.name}"
              f" ({out_path.stat().st_size / 1e6:.1f} MB)")
    finally:
        for k, v in old_ints.items():
            sw.SetUserPreferenceIntegerValue(k, v)
        for k, v in old_toggles.items():
            sw.SetUserPreferenceToggle(k, v)


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
    apply_custom_properties(adapter, part_properties(part_name))
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
    import pythoncom
    from win32com.client import VARIANT

    from solidworks_mcp.adapters import sw_type_info

    index = {"x": 0, "y": 1, "z": 2}[axis]
    pos = [1.0 if i == index else 0.0 for i in range(3)]
    neg = [-v for v in pos]

    def _extreme(body: Any, direction: list[float]) -> float:
        # IBody2::GetExtremePoint(Px,Py,Pz, &X,&Y,&Z): direction in, the extreme
        # point comes back through three [out] byref doubles (metres). Returns the
        # axis coordinate in mm.
        out = [VARIANT(pythoncom.VT_BYREF | pythoncom.VT_R8, 0.0) for _ in range(3)]
        res = adapter._attempt(
            lambda: body.GetExtremePoint(
                direction[0], direction[1], direction[2], out[0], out[1], out[2]),
            default="__err__")
        if res == "__err__":
            raise RuntimeError(f"bbox {label}: GetExtremePoint failed")
        return out[index].value * 1000.0

    doc = adapter.currentModel
    sw_type_info.flag_methods(doc, "IPartDoc")
    bodies = adapter._attempt(lambda: doc.GetBodies2(0, False)) or []  # solid
    if not bodies:
        raise RuntimeError(f"bbox {label}: part has no solid bodies")
    lo, hi = float("inf"), float("-inf")
    for body in bodies:
        sw_type_info.flag_methods(body, "IBody2")
        lo = min(lo, _extreme(body, neg))
        hi = max(hi, _extreme(body, pos))
    extent = hi - lo
    if abs(extent - expected) > tol:
        raise RuntimeError(
            f"bbox {label}: {axis}-extent={extent:.4f} outside {expected} +/- {tol}"
        )
    print(f"  OK  bbox {label}: {axis}-extent={extent:.4f} (expected {expected:g})")


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
    # knife bearing support: X-symmetric (bore + block centred on x0); explicit
    # so placement never depends on a stale/absent STL bbox (it mirrors with the
    # summing lever so the bore stays around the hex trunnion).
    "knife-mount": ("x", 0.0),
    # parts whose build scripts are themselves mirrored (M6.8)
    "summing-lever": "x0",
    "magnifying-bracket": "x0",
    "pen-hanger": "x0",
    # rocker-arm-portal (the unified support casting) is authored machine-handed
    # and lives in the non-mirroring frame.SLDASM -> NO mirror entry (it replaced
    # the old split rocker-arm-support + a-frame "x0" pair, 2026-06-19).
    # M6.10 fasteners: authored in final orientation (axis along Y or Z),
    # exactly symmetric about local x = 0; explicit c, no STL at first build
    "hex-bolt": ("x", 0.0),
    "lag-screw": ("x", 0.0),
    "fillister-screw": ("x", 0.0),
    "pinch-screw": ("x", 0.0),
    "hanger-screw": ("x", 0.0),
}

















UNDER_CONSTRAINED = 2
FULLY_CONSTRAINED = 3


def _flag(obj: Any, interface: str) -> None:
    from solidworks_mcp.adapters import sw_type_info

    try:
        sw_type_info.flag_methods(obj, interface)
    except Exception:
        pass








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
    model = adapter.currentModel
    if model is None:
        return
    _flag(model, "IModelDoc2")
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
