"""Specialized, low-fanout feature builders pulled out of _common so their
churn (spring end-hooks, knurled/reeded screw heads, nameplate rounded-rect
and polyline-loop sketches) invalidates only the few parts that use them,
not every build. Imports the shared sketch primitives it builds on from
_common.
"""
from __future__ import annotations

import math
from typing import Any

from _common import (
    anchor_point_to_origin,
    check,
    define_circle,
    ensure_fully_defined,
    feature_name_by_type,
    set_sketch_direct_db,
)

import _telemetry

async def sketch_rounded_rect(
    adapter: Any, w: float, h: float, r: float, cx: float = 0.0, cy: float = 0.0
) -> None:
    """Draw a CCW rounded rectangle (4 edges + 4 corner arcs) into the OPEN sketch.

    Centred at ``(cx, cy)``, width ``w`` x height ``h``, corner radius ``r`` (mm).
    A cosmetic outline (the nameplate's rounded plate edge) -- the arcs leave it
    under-defined, so callers skip :func:`ensure_fully_defined`. ``add_arc`` draws
    CCW from start to end; the four corner arcs are ordered so the loop runs CCW.
    Inference suppressed via ``AddToDB`` like the other raw draws here.
    """
    a, b = w / 2.0, h / 2.0
    e = [(cx - (a - r), cy - b), (cx + (a - r), cy - b),   # bottom edge endpoints
         (cx + a, cy - (b - r)), (cx + a, cy + (b - r)),   # right edge
         (cx + (a - r), cy + b), (cx - (a - r), cy + b),   # top edge
         (cx - a, cy + (b - r)), (cx - a, cy - (b - r))]   # left edge
    corners = [(cx + (a - r), cy - (b - r), e[1], e[2]),   # BR (center, start, end)
               (cx + (a - r), cy + (b - r), e[3], e[4]),   # TR
               (cx - (a - r), cy + (b - r), e[5], e[6]),   # TL
               (cx - (a - r), cy - (b - r), e[7], e[0])]   # BL
    sketch_mgr = adapter.currentSketchManager
    prev = bool(sketch_mgr.AddToDB)
    sketch_mgr.AddToDB = True
    try:
        for (x1, y1), (x2, y2) in [(e[0], e[1]), (e[2], e[3]), (e[4], e[5]), (e[6], e[7])]:
            check(f"rrect edge ({x1:g},{y1:g})", await adapter.add_line(x1, y1, x2, y2))
        for ccx, ccy, (sx, sy), (ex, ey) in corners:
            check(f"rrect arc @({ccx:g},{ccy:g})", await adapter.add_arc(ccx, ccy, sx, sy, ex, ey))
    finally:
        sketch_mgr.AddToDB = prev
    _telemetry.success(f"rounded_rect {w:g}x{h:g} r{r:g} @ ({cx:g}, {cy:g})")

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
    _telemetry.success(f"insert_helix -> {name}")
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
            _telemetry.debug(f"top hook sweep failed ({res.error}); flipping profile plane")
            plane = check(
                "create_plane top hook profile (flipped)",
                await adapter.create_plane(
                    CreatePlaneParameters(
                        mode="offset",
                        base_plane="Top Plane",
                        offset=-body_length,
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
        _telemetry.success(
            f"{label} hook: added {added:.2f} mm^3 "
            f"(Pappus {v_hook:.2f}, overlap allowance {max_overlap:.2f}, "
            f"slack {slack:.2f})"
        )

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
    thread_size: str = "#4-40",  # ANSI-inch UNC; nearest UNC to the old M3x0.5
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
    _telemetry.success(f"reeding seed: removed {before - after_seed:.2f} mm^3 (analytic {v_groove:.2f})")

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
    _telemetry.success(f"reeded head: volume {after_pattern:.2f} mm^3 (analytic {expected:.2f})")

    adapter._zoom_to_fit(adapter.currentModel)
    check(
        f"cosmetic thread {thread_size}",
        await adapter.add_thread(
            AddThreadParameters(
                edge_point=[head_length + shank_length, shank_dia / 2.0, 0.0],
                standard="ansi_inch",  # was ansi_metric M3x0.5 -> US-customary UNC
                size=thread_size,
                end_type="blind",
                depth=shank_length,
            )
        ),
    )
    if abs(await _volume() - after_pattern) > 1e-6:
        raise RuntimeError("cosmetic thread changed the volume -- it cut geometry")
