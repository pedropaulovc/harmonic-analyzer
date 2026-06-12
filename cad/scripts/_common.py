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

Fully-defined recipes (probed live on SW 2026):

* **Line chains**: consecutive ``add_line`` calls sharing exact endpoint
  coordinates get merged/coincident vertices; with one vertex on the sketch
  origin, horizontal/vertical constraints and per-segment length dimensions
  fully define the chain — no ``fix`` needed.
* **Circles**: centre points are not addressable with the current tool
  surface, so anchor with ``fix`` FIRST, then add the diameter dimension —
  SolidWorks auto-marks a dimension added to fixed geometry as driven, while
  the reverse order (dimension, then fix) makes the sketch over-defined. Use
  :func:`define_circle`.
* **Off-origin line profiles**: pass the line IDs as ``fix_entities`` —
  perpendicular fixed lines with merged vertices pin each other's endpoints.
* **Never mix driving dimensions with fix escalation across a chain**: a
  driving dim determines geometry downstream through merged vertices;
  fixing any of that downstream geometry re-pins what the dim already
  determined and the sketch goes over-defined (consistent-but-redundant
  counts — caught live on the channel-lever outline). A profile is either
  constraints+dims with no fixes (amplitude-bar style, needs an origin
  vertex) or fix-only (crank-pin style).
"""

from __future__ import annotations

import asyncio
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
    adapter: Any, label: str, fix_entities: Iterable[str] = ()
) -> None:
    """Assert the active sketch is fully defined, escalating to ``fix``.

    Checks ``check_sketch_fully_defined``; when under-defined and
    ``fix_entities`` are provided, applies a ``fix`` relation to each and
    re-checks. Raises if the sketch still is not fully defined.
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

    # Escalate one entity at a time: fixing everything at once makes the
    # driving dimensions redundant and over-defines the sketch. "unknown"
    # is kept fixable as a safety net: the status probe can transiently fail
    # (pywin32 property/method resolution drift on GetConstrainedStatus) and
    # a later read may recover.
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


async def define_circle(
    adapter: Any, x: float, y: float, radius: float, label: str
) -> str:
    """Add a circle, anchor it with ``fix``, then document its diameter.

    The fix-then-dimension order matters: the dimension lands as driven on the
    already-fixed circle; dimension-then-fix over-defines the sketch.
    """
    circle = await adapter.add_circle(x, y, radius)
    check(f"add_circle {label}", circle)
    check(
        f"fix {label}",
        await adapter.add_sketch_constraint(circle.data, None, "fix"),
    )
    check(
        f"dimension {label} diameter (driven)",
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

    The path is drawn as two equation-driven curves, not add_line/add_arc:
    a ``fix`` on a line or arc pins the curve but its endpoints still slide
    along the fixed locus, so the sketch stays under-defined (caught live
    on this path -- the loop's open end has a genuine DOF). Fixed equation
    curves have no free endpoints (the gear-gap recipe). Expressions are in
    document units (inches), trig in radians.

    Each sweep is volume-asserted: Pappus gives the exact added volume for
    a planar path; the junction where the hook tube merges into the coil
    end may absorb up to a full Steinmetz lens (16 r^3 / 3).
    """
    from solidworks_mcp.adapters.base import (
        CreateEquationCurveParameters,
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

    def fmt(value_mm: float) -> str:
        return f"{value_mm / IN:.12g}"  # document units are inches

    async def _curve(label: str, x_expr: str, y_expr: str) -> str:
        res = await adapter.create_equation_driven_curve(
            CreateEquationCurveParameters(
                x_expression=x_expr,
                y_expression=y_expr,
                range_start="0",
                range_end="1",
            )
        )
        return check(f"curve {label}", res)

    for (label, y_end, d), lead in zip(
        (("bottom", 0.0, -1.0), ("top", body_length, 1.0)), lead_by_end, strict=True
    ):
        # Path: axial lead line from the helix end, tangent 270-degree loop
        # (clockwise for the bottom hook, counter-clockwise for the top, so
        # the loop extends axially outward).
        v_hook = (lead + 1.5 * math.pi * loop_r) * wire_area
        p1 = (mean_radius, y_end + d * lead)
        c = (mean_radius - loop_r, p1[1])
        path_name = check(
            f"create_sketch {label} hook path", await adapter.create_sketch("Front")
        )
        lead_line = await _curve(
            f"{label} hook lead",
            f"{fmt(mean_radius)} + 0 * t",
            f"{fmt(y_end)} + {fmt(d * lead)} * t",
        )
        sweep_rad = d * 1.5 * math.pi  # 270 deg from angle 0 at the junction
        loop_arc = await _curve(
            f"{label} hook loop",
            f"{fmt(c[0])} + {fmt(loop_r)} * cos({sweep_rad:.12g} * t)",
            f"{fmt(c[1])} + {fmt(loop_r)} * sin({sweep_rad:.12g} * t)",
        )
        await ensure_fully_defined(
            adapter, f"{label} hook path", fix_entities=[lead_line, loop_arc]
        )
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
    "channel-lever": "z",
    "channel-spring-installed": "z",
    # drive train
    "crank-arm": "z",
    "crank-handle": "z",
    "transgear-latch": "z",
    # output
    "knife-stay": "z",
    "boss-hook": "z",
    "counter-spring": "z",
    "gooseneck": "z",
    "gooseneck-clamp": "z",
    "magnifying-lever": "z",
    "magnifying-clamp": "z",
    "thumb-screw": "z",
    "magnifying-vertical-rod": "z",
    "pen-v-block": "z",
    "pen-frame": "z",
    "pen-set-screw": "z",
    "a-frame": "z",
    "column-clamp": "z",
    # parts whose build scripts are themselves mirrored (M6.8)
    "summing-lever": "x0",
    "magnifying-bracket": "x0",
    "pen-hanger": "x0",
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


def assert_components_fully_defined(adapter: Any) -> None:
    """Raise when any top-level component is neither fixed nor fully defined.

    ``IComponent2::GetConstrainedStatus`` returns swConstrainedStatus_e
    (2 = under, 3 = fully, 4 = over constrained). ``GetComponents`` hands
    back unflagged dispatches, so the IComponent2 methods must be flagged
    first or the call resolves as a property and raises.
    """
    asm = adapter.currentModel
    components = adapter._attempt(lambda: asm.GetComponents(True), default=None) or []
    log(f"checking {len(components)} components for free DOF ...")
    problems = []
    for component in components:
        _flag(component, "IComponent2")
        comp_name = str(_read_member(component, "Name2"))
        if bool(_read_member(component, "IsFixed")):
            log(f"{comp_name}: fixed")
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


def check_no_interference(adapter: Any) -> None:
    """Run interference detection on the active assembly; raise on any hit.

    Raw-COM stopgap until the MCP adapter implements ``check_interference``
    (``IAssemblyDoc::InterferenceDetectionManager``; the tool-layer call
    currently returns a simulated result without adapter support).
    Coincident/tangent contact is not treated as interference.
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
    for interference in list(interferences or []):
        _flag(interference, "IInterference")
        names = []
        for comp in list(_read_member(interference, "Components") or []):
            _flag(comp, "IComponent2")
            names.append(str(_read_member(comp, "Name2")))
        volume_mm3 = float(_read_member(interference, "Volume") or 0.0) * 1e9
        details.append(f"{' & '.join(names)}: {volume_mm3:.2f} mm^3")
    adapter._attempt(lambda: mgr.Done(), default=None)
    if details:
        raise RuntimeError(
            f"{len(details)} interference(s): " + "; ".join(details)
        )
    print(f"  OK  {_stamp()} interference check: none found", flush=True)


async def save_assembly_and_images(
    adapter: Any, asm_name: str, views: Iterable[str] = DEFAULT_VIEWS
) -> dict[str, str]:
    """Save the assembly to ``cad/out/sldasm`` and PNG views to ``cad/out/png``."""
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
