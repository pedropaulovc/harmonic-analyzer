"""Assembly-only helpers: mates, drivers, component placement, health/
interference gates, assembly save/refresh. Imported only by the assembly
build scripts (never by a leaf part), so edits here never invalidate parts.
"""
from __future__ import annotations

import hashlib
from collections.abc import Iterable
from typing import Any

import _telemetry
from _common import (
    DEFAULT_VIEWS,
    FULLY_CONSTRAINED,
    OUT_PNG,
    OUT_SLDASM,
    OUT_SLDPRT,
    UNDER_CONSTRAINED,
    _CHAIN_LINK_PREFIXES,
    _FEATURE_ERROR,
    _MATE_TOL_MM,
    _flag,
    _read_member,
    check,
    log,
    set_isometric_view,
)
from _transforms import mirror_placement

def insert_sketch_text(
    adapter: Any,
    text: str,
    x_mm: float,
    y_mm: float,
    *,
    height_mm: float,
    width_pct: int = 100,
    space_pct: int = 100,
    alignment: int = 0,
    label: str = "text",
) -> Any:
    """Insert sized sketch text into the OPEN 2D sketch; return the ISketchText.

    Raw-COM helper (``IModelDoc2::InsertSketchText`` to place the glyph
    contours, then ``ISketchText::GetTextFormat`` + ``ITextFormat::CharHeight``
    + ``ISketchText::SetTextFormat`` to size them) -- the MCP adapter wraps no
    text primitive, so engraved lettering reaches past it the same way
    :func:`insert_helix` / :func:`extrude_at_offset` reach ``InsertHelix`` /
    ``FeatureExtrusion3``. The caller owns the sketch: open it (``create_sketch``)
    before, ``exit_sketch`` + ``create_cut_extrude`` after to incise the glyphs.

    ``x_mm``/``y_mm`` are the text-block insertion point in the Front-sketch
    frame (= model X/Y for the origin sketch this project authors on). Without a
    selected guide curve ``alignment`` is ignored and the block is left-anchored
    at the insertion point (SOLIDWORKS API remark) -- callers centre by pre-
    computing the left x. ``height_mm`` is the cap height; ``width_pct`` evenly
    widens each glyph (6..1667), ``space_pct`` the inter-character spacing.

    NOTE: not yet exercised on the SolidWorks COM seat (this repo runs the build
    on Windows); the call shapes follow the 2023 API reference verbatim. Treat
    the first live run as the validation pass, same posture as the other raw-COM
    stopgaps here.
    """
    model = adapter.currentModel
    sketch_mgr = adapter.currentSketchManager
    prev_add_to_db = bool(sketch_mgr.AddToDB)
    sketch_mgr.AddToDB = True
    try:
        sk_text = model.InsertSketchText(
            x_mm / 1000.0,
            y_mm / 1000.0,
            0.0,
            text,
            int(alignment),  # 0=left 1=centre 2=right 3=justified
            0,  # FlipDirection (guide-curve only)
            0,  # HorizontalMirror
            int(width_pct),  # WidthFactor %
            int(space_pct),  # SpaceBetweenChars %
        )
    finally:
        sketch_mgr.AddToDB = prev_add_to_db
    if sk_text is None:
        raise RuntimeError(f"insert_sketch_text {label!r}: InsertSketchText returned None")
    fmt = _read_member(sk_text, "GetTextFormat")
    if fmt is None:
        raise RuntimeError(f"insert_sketch_text {label!r}: GetTextFormat returned None")
    fmt.CharHeight = height_mm / 1000.0  # ITextFormat.CharHeight is metres
    ok = adapter._attempt(lambda: sk_text.SetTextFormat(False, fmt), default=False)
    if not ok:
        raise RuntimeError(f"insert_sketch_text {label!r}: SetTextFormat returned False")
    model.ClearSelection2(True)
    _telemetry.success(f"sketch text {label!r} h{height_mm:g} @ ({x_mm:g}, {y_mm:g})")
    return sk_text

def add_ellipse(
    adapter: Any, cx_mm: float, cy_mm: float, rx_mm: float, ry_mm: float, label: str = "ellipse"
) -> Any:
    """Add a full ellipse to the OPEN 2D sketch; return the sketch segment.

    Raw-COM (``ISketchManager::CreateEllipse``: centre + a point on each axis,
    metres). ``rx_mm``/``ry_mm`` are the semi-axes along sketch X/Y. Inference is
    suppressed via ``AddToDB`` like the other raw draws here. Used for the
    nameplate's central cartouche oval (no ellipse primitive on the adapter).
    """
    sketch_mgr = adapter.currentSketchManager
    prev_add_to_db = bool(sketch_mgr.AddToDB)
    sketch_mgr.AddToDB = True
    try:
        seg = sketch_mgr.CreateEllipse(
            cx_mm / 1000.0, cy_mm / 1000.0, 0.0,
            (cx_mm + rx_mm) / 1000.0, cy_mm / 1000.0, 0.0,  # major-axis point (+X)
            cx_mm / 1000.0, (cy_mm + ry_mm) / 1000.0, 0.0,  # minor-axis point (+Y)
        )
    finally:
        sketch_mgr.AddToDB = prev_add_to_db
    if seg is None:
        raise RuntimeError(f"add_ellipse {label!r}: CreateEllipse returned None")
    adapter.currentModel.ClearSelection2(True)
    _telemetry.success(f"ellipse {label!r} r({rx_mm:g}, {ry_mm:g}) @ ({cx_mm:g}, {cy_mm:g})")
    return seg

async def apply_component_color(
    adapter: Any,
    name: str,
    rgb: tuple[float, float, float],
) -> None:
    """Per-INSTANCE component display colour in an assembly.

    A part colour cannot tint one instance of a multi-config part differently
    from another: a per-config part colour loses to the part's material
    appearance, and a body colour is global to the part document. The component
    instance appearance sits above both and is per-occurrence, so the four
    muntz_yellow cone tip-gear instances tint without touching the brass part or
    the other 16 cone gears. It is also exactly what the render pipeline reads
    (export_models comp_rgb -> IComponent2.GetMaterialPropertyValues2).

    Sets via IComponent2.SetMaterialPropertyValues2(values, swThisConfiguration,
    None) and asserts the readback (SW quantises to 8 bit/channel).
    """
    from solidworks_mcp.adapters.com_variant import double_array

    comp = adapter.currentModel.GetComponentByName(name)
    if comp is None:
        raise RuntimeError(f"component not found for colour: {name!r}")
    _flag(comp, "IComponent2")
    values = double_array([*rgb, 1.0, 1.0, 0.3, 0.31, 0.0, 0.0])
    # [R,G,B, ambient, diffuse, specular, shininess, transparency, emission]
    comp.SetMaterialPropertyValues2(values, 1, None)  # swThisConfiguration
    back_raw = adapter._attempt(
        lambda: comp.GetMaterialPropertyValues2(1, None), default=None
    )
    back = tuple(float(v) for v in (back_raw or ())[:3])
    if len(back) != 3 or any(abs(b - w) > 1 / 255 for b, w in zip(back, rgb)):
        raise RuntimeError(f"component colour readback mismatch on {name}: set {rgb}, got {back}")
    adapter._attempt(lambda: adapter.currentModel.GraphicsRedraw2(), default=None)
    log(f"component colour {name}: {tuple(round(v, 3) for v in back)}")

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

def component_origin(adapter: Any, name: str) -> list[float]:
    """A component's current origin (mm) in the assembly frame."""
    a = component_transform(adapter, name)
    return [a[9] * 1000.0, a[10] * 1000.0, a[11] * 1000.0]

def part_path(part: str) -> str:
    """Resolve ``<part>.SLDPRT`` under the part-output dir, or raise."""
    path = (OUT_SLDPRT / f"{part}.SLDPRT").resolve()
    if not path.exists():
        raise RuntimeError(
            f"missing part {path}; run build_{part.replace('-', '_')}.py first"
        )
    return str(path)

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
    _telemetry.success(f"{name} placed at {[round(v, 3) for v in actual]}")

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

    # Span every mate (the single chokepoint all mate helpers funnel through),
    # including flip-recovery, so the full-build waterfall stays contiguous
    # between part spans instead of leaving the mate time as a gap.
    async with _telemetry.aspan(f"mate {kind}", kind=kind, label=label) as msp:
        res = check(label, await _add_mate(adapter, kind, entities, flip=False, **kw))
        if verify is None:
            return res
        comp_name, target_origin = verify
        array = component_transform(adapter, comp_name)
        moved = max(abs(array[9 + i] * 1000.0 - target_origin[i]) for i in range(3))
        if moved <= _MATE_TOL_MM:
            return res
        msp.set_attribute("flipped", True)
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
    mirror: bool = True,
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

    ``mirror=True`` (default) routes the placement through ``mirror_placement``,
    which reflects it about the machine YZ plane using the part's ``MIRROR_PLANE``
    symmetry (default ``"x"``). Pass ``mirror=False`` for a SINGLE machine-handed
    part with no mirror twin -- e.g. the maker's nameplate -- whose ``position``/
    ``rows`` are already the exact machine transform; the default ``"x"`` reflection
    would otherwise flip it across X (onto the wrong side, text reversed).
    """
    from solidworks_mcp.adapters.base import (
        ComponentRefParameters,
        InsertComponentParameters,
    )

    label = label or part
    # One span per part: insert + (fix) + placement assert for THIS component, so
    # the full-build waterfall shows where each part's time went and a failed
    # insert/mate is attributed to the part by name.
    async with _telemetry.aspan(
        f"part {label}", part=part, ground=ground,
        configuration=configuration or "default",
    ) as psp:
        if mirror:
            position, rotation, rows = mirror_placement(
                part, position, rotation, rows, configuration
            )
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
        psp.set_attribute("component", name)
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
    problems = []
    with _telemetry.span("gate.dof") as gsp:
        # Re-solve the mate solver before reading the gate (stale-status reason
        # above) -- the ForceRebuild3 is the bulk of the gate's wall-clock, so it
        # gets its own child span rather than sitting in an unspanned gap.
        with _telemetry.span("dof.resolve"):
            adapter._attempt(lambda: asm.ForceRebuild3(False), default=None)
            components = adapter._attempt(lambda: asm.GetComponents(True), default=None) or []
        gsp.set_attribute("components", len(components))
        log(f"checking {len(components)} components for free DOF ...")
        for component in components:
            _flag(component, "IComponent2")
            comp_name = str(_read_member(component, "Name2"))
            with _telemetry.span("dof.check", component=comp_name) as csp:
                if bool(_read_member(component, "IsFixed")):
                    csp.set_attribute("result", "fixed")
                    log(f"{comp_name}: fixed")
                    continue
                if bool(
                    adapter._attempt(lambda c=component: c.IsPatternInstance(), default=False)
                ):
                    csp.set_attribute("result", "pattern")
                    log(f"{comp_name}: pattern instance (feature-driven)")
                    continue
                status = int(
                    adapter._attempt(lambda c=component: c.GetConstrainedStatus(), default=-1)
                )
                csp.set_attribute("status", status)
                log(f"{comp_name}: constrained status {status}")
                if status != FULLY_CONSTRAINED:
                    kind = "under" if status == UNDER_CONSTRAINED else f"status={status}"
                    problems.append(f"{comp_name} ({kind})")
        _telemetry.success(f"checked {len(components)} components for free DOF")
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
    with _telemetry.span("gate.interference") as isp:
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
        with _telemetry.span("interference.compute"):
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
        isp.set_attribute("hits", len(details))
        isp.set_attribute("chain_contacts", len(chain_contacts))
        if chain_contacts:
            _telemetry.debug(
                f"{len(chain_contacts)} chain-internal link contacts"
                f" (<= {max(chain_contacts):.2f} mm^3) allowed -- articulating chain"
            )
        if details:
            raise RuntimeError(
                f"{len(details)} interference(s): " + "; ".join(details)
            )
        _telemetry.success("interference check: none found")

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
    with _telemetry.span("gate.health", label=label or "top", deep=deep) as hsp:
        # The deep ForceRebuild3 + sub-document collection is the bulk of the
        # gate's wall-clock; span it so it is not an unspanned leading gap before
        # the per-target whats_wrong checks.
        with _telemetry.span("health.rebuild"):
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
            with _telemetry.span("health.whats_wrong", target=tlabel):
                for name, code, warn in whats_wrong(adapter, doc):
                    entry = f"{tlabel}:{name} [{_FEATURE_ERROR.get(code, code)}]"
                    (warnings if warn else errors).append(entry)
        if rebuilt is False:
            errors.append(f"{label or 'top'}: ForceRebuild3 returned False")

        hsp.set_attribute("targets", len(targets))
        hsp.set_attribute("warnings", len(warnings))
        hsp.set_attribute("errors", len(errors))
        if warnings:
            _telemetry.warn(
                f"{len(warnings)} health warning(s): " + "; ".join(warnings[:12])
            )
        if errors:
            raise RuntimeError(
                f"model unhealthy ({label or 'top'}): {len(errors)} error(s) -- "
                + "; ".join(errors[:20])
            )
        _telemetry.success(f"model healthy ({label or 'top'})")

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

async def _export_assembly_images(
    adapter: Any, asm_name: str, views: Iterable[str]
) -> dict[str, str]:
    """Export PNG views to ``cad/out/png/<asm>`` (gitignored build output).

    Factored out of :func:`save_assembly_and_images` so the refresh primitive
    (:func:`refresh_assembly`) shares the exact same export tail. Returns
    ``{<view>: path}``; the caller adds the assembly path.

    Does NOT touch the committed ``docs/images`` README renders -- those are
    refreshed deliberately via ``python cad/scripts/trim_renders.py`` and
    committed on purpose, so a model build never dirties a tracked file (which
    would otherwise block ``doit release``'s clean-tree preflight).
    """
    png_dir = OUT_PNG / asm_name
    png_dir.mkdir(parents=True, exist_ok=True)
    artefacts: dict[str, str] = {}
    views = list(views)
    async with _telemetry.aspan("export_images", count=len(views)):
        for view in views:
            img_path = (png_dir / f"{asm_name}_{view}.png").resolve()
            async with _telemetry.aspan("export_image", view=view):
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
    # Save on isometric so the .SLDASM opens isometric; runs AFTER any
    # remap_front_to_machine_front (which re-bases the standard views) so the
    # re-based Front/Back/etc. used by the gallery stay correct.
    set_isometric_view(adapter)
    check(f"save_file -> {asm_path}", await adapter.save_file(str(asm_path)))
    # Record the resolved-geometry fingerprint of the just-built assembly so a later
    # in-place refresh of it (unchanged) is a true no-op and never bumps the md5 --
    # otherwise the first refresh after a from-scratch build would re-save once and
    # cascade up the tree (see save_assembly_in_place / _massprops_sidecar).
    digest = await assembly_geometry_digest(adapter, asm_name)
    sidecar = _massprops_sidecar(asm_name)
    sidecar.parent.mkdir(parents=True, exist_ok=True)
    sidecar.write_text(digest + "\n", encoding="utf-8")

    artefacts = {"assembly": str(asm_path)}
    artefacts.update(await _export_assembly_images(adapter, asm_name, views))
    return artefacts

def _massprops_sidecar(asm_name: str):
    """Sidecar holding the last-saved resolved-geometry fingerprint of an assembly.

    A parent assembly's doit dependency on a child is the child ``.SLDASM``'s md5,
    and SolidWorks rewrites a ``.SLDASM`` with fresh save metadata (new bytes -> new
    md5) on EVERY in-place save. So an unconditional re-save of an *unchanged*
    assembly bumps its md5 and spuriously invalidates the parent, which then
    re-saves and invalidates ITS parent -- a no-op "reconciliation" refresh that
    cascades up the whole tree one level per ``doit`` run (the post-release
    not-a-no-op). Gating the re-save on a real change to THIS fingerprint keeps a
    no-op refresh byte-stable, so the build reaches a true fixpoint. Lives under the
    gitignored ``cad/out/sldasm`` next to the recipe sidecar."""
    return OUT_SLDASM / f".{asm_name}.massprops.sha"


async def assembly_geometry_digest(adapter: Any, asm_name: str) -> str:
    """A deterministic fingerprint of an assembly's RESOLVED geometry across every
    configuration: exact-BREP mass properties (mass / volume / centre of mass /
    moments of inertia). It changes iff a component's geometry changed and is immune
    to SolidWorks' volatile save metadata (unlike the ``.SLDASM`` bytes) and to
    tessellation noise (unlike an STL hash). Leaves the doc on the rest pose.

    Used to decide whether an in-place refresh actually changed anything: a part
    edit that re-solves the assembly shifts the mass properties (so the parent must
    rebuild -> bump the md5), while a pure reload of unchanged parts does not (keep
    the file byte-stable -> no phantom cascade)."""
    configs = check("list configurations", await adapter.list_configurations())
    rest = "Default" if "Default" in configs else (configs[0] if configs else None)
    # Only switch configs for a genuinely multi-config assembly. A config switch
    # regenerates the whole model (~80-160 s each on the 122-component top), so for
    # the single-config case (the rest pose is already active after the gates) we
    # read mass properties in place and never activate/re-activate.
    multi = len(configs) > 1
    rows: list[Any] = []
    for cfg in configs:
        if multi:
            check(f"activate {cfg}", await adapter.set_active_configuration(cfg))
        res = await adapter.get_mass_properties()
        if not res.is_success:
            raise RuntimeError(
                f"{asm_name}: get_mass_properties failed for config {cfg!r}: "
                f"{res.error}")
        mp = res.data
        moi = mp.moments_of_inertia
        rows.append((
            cfg,
            round(float(mp.mass), 6),
            round(float(mp.volume), 3),
            tuple(round(float(c), 4) for c in mp.center_of_mass),
            tuple(round(float(moi[k]), 4)
                  for k in ("Ixx", "Iyy", "Izz", "Ixy", "Ixz", "Iyz")),
        ))
    if multi and rest is not None:
        check(f"re-activate {rest}", await adapter.set_active_configuration(rest))
    return hashlib.sha256(repr(rows).encode("utf-8")).hexdigest()


def save_assembly_in_place(adapter: Any, asm_name: str, geometry_changed: bool) -> None:
    """Save ``<asm_name>.SLDASM`` in place with a silent ``ModelDoc2.Save3``.

    For an assembly OPENED from its own path (a refresh or a config-hook reopen)
    the active doc IS the file, so the correct save is an in-place
    ``Save3(swSaveAsOptions_Silent | SaveReferenced, &err, &warn)`` -- NOT the
    adapter's ``save_file``, both of whose branches are wrong for an
    opened-in-place doc:

      * ``save_file(PATH)`` -> SaveAs branch does ``CloseDoc(PATH)`` +
        ``os.remove(PATH)`` before ``SaveAs3``; when the active doc IS that path
        this disconnects the doc and deletes the file -- it destroyed
        drive-train.SLDASM twice.
      * ``save_file()`` (no path) -> ``Save3(1, None, None)``; ``None`` for the
        two [out] byref params fails the COM call, so it falls through to the
        blocking parameterless ``Save()`` "Component documents must be saved"
        modal.

    Passing the two [out] params as real pywin32 BYREF VARIANTs makes ``Save3``
    write silently and return the error/warning codes. ``SaveReferenced`` writes
    any dirty reference without a dialog. The mtime assertion proves the file was
    rewritten (never deleted). Proven by ``repro_inplace_save.py`` (ret=True,
    err=0, warn=0, the active config persists on reopen).

    ``geometry_changed`` gates the bump. Every in-place ``Save3`` rewrites fresh
    save metadata -> a new md5, and the parent's doit dep is this file's md5, so an
    unconditional save of an UNCHANGED assembly spuriously invalidates the parent
    and cascades a no-op reconciliation refresh up the tree (see
    ``_massprops_sidecar``). When the resolved-geometry fingerprint is unchanged we
    therefore skip the save outright, leaving the ``.SLDASM`` byte-identical so the
    parent stays valid. When it changed we force the rewrite even if SolidWorks
    reports the doc clean (a reload of changed PART geometry leaves the assembly's
    own data -- component refs + mates + transforms -- untouched, so ``GetSaveFlag``
    can read false): ``SetSaveFlag`` + ``Save3`` push the new geometry's md5 to the
    parent (codex review #5).
    """
    import pythoncom
    from win32com.client import VARIANT

    asm = adapter.currentModel
    sldasm = OUT_SLDASM / f"{asm_name}.SLDASM"
    if not geometry_changed:
        # No-op refresh: resolved geometry identical to the last save. Do NOT
        # rewrite -- a fresh md5 here would invalidate the parent for nothing.
        log(f"{sldasm.name}: geometry unchanged -- .SLDASM left intact (no md5 bump)")
        return

    if not bool(adapter._attempt(lambda: asm.GetSaveFlag(), default=True)):
        log(f"{sldasm.name} reported clean -- forcing rewrite for md5 propagation")
        adapter._attempt(lambda: asm.SetSaveFlag(), default=None)

    before = sldasm.stat().st_mtime
    err = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    warn = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    options = 1 | 8  # swSaveAsOptions_Silent | swSaveAsOptions_SaveReferenced
    ret = adapter._attempt(lambda: asm.Save3(options, err, warn), default=False)

    after = sldasm.stat().st_mtime
    if after <= before:
        raise RuntimeError(
            f"{sldasm.name} mtime unchanged after Save3(Silent) "
            f"(ret={ret}, err={err.value}, warn={warn.value})")
    log(f"saved {sldasm.name} via Save3(Silent) (ret={ret}, err={err.value}, "
        f"warn={warn.value})")

def _rebuild_faults(adapter: Any) -> list[str]:
    """Non-warning What's Wrong entries for the active model, formatted for a log."""
    return [
        f"{name} [{_FEATURE_ERROR.get(code, code)}]"
        for name, code, warn in whats_wrong(adapter, adapter.currentModel)
        if not warn
    ]


def select_mates_folder(adapter: Any) -> bool:
    """Select the active assembly's Mates folder -- the precondition for
    ``IAssemblyDoc.AutoMateRepair``. The folder is a ``MateGroup`` feature that sits
    at/near the END of the top-level tree, so scan from the back (a couple of COM
    round-trips) instead of walking all ~150 component features forward (~50 s).
    Falls back to a full forward walk if an in-context feature pushed it off the
    tail."""
    model = adapter.currentModel
    count = int(adapter._attempt(lambda: model.GetFeatureCount(), default=0) or 0)
    for i in range(min(count, 8)):  # MateGroup is the last top-level feature (i=0)
        feat = adapter._attempt(lambda i=i: model.FeatureByPositionReverse(i), default=None)
        if feat is None:
            continue
        _flag(feat, "IFeature")
        if str(adapter._attempt(lambda f=feat: f.GetTypeName2(), default="")) == "MateGroup":
            return bool(adapter._attempt(lambda f=feat: f.Select2(False, 0), default=False))
    feat = adapter._attempt(lambda: model.FirstFeature(), default=None)
    while feat is not None:
        _flag(feat, "IFeature")
        if str(adapter._attempt(lambda f=feat: f.GetTypeName2(), default="")) == "MateGroup":
            return bool(adapter._attempt(lambda f=feat: f.Select2(False, 0), default=False))
        feat = adapter._attempt(lambda f=feat: f.GetNextFeature(), default=None)
    return False


def repair_dangling_mates(adapter: Any) -> int:
    """Auto-heal mates whose referenced topology was re-IDed by a from-scratch part
    rebuild (the "sharp edge"): ``IAssemblyDoc.AutoMateRepair`` re-binds the broken
    mates in place (~5 s) instead of a ~500 s full re-insert/re-mate.

    Returns the count AutoMateRepair reports as repaired. Its own return code is
    ADVISORY ONLY -- it returns PartialSuccess with a large FailedMates array (the
    assembly's already-valid mates, which it cannot "re-repair") even on a fully
    successful heal -- so the CALLER must judge success from a fresh ``whats_wrong``
    + the standard DOF/interference/health gates, never from this code.
    """
    asm = adapter.currentModel
    _flag(asm, "IAssemblyDoc")
    if not select_mates_folder(adapter):
        log("AutoMateRepair: could not select the Mates folder -- skipping repair")
        return 0
    processed, failed = _byref_variant(), _byref_variant()
    ret = adapter._attempt(lambda: asm.AutoMateRepair(processed, failed), default=-1)
    n_proc = len(list(processed.value or [])) if processed.value is not None else 0
    n_fail = len(list(failed.value or [])) if failed.value is not None else 0
    log(f"AutoMateRepair: ret={ret} (1=PartialSuccess is normal) "
        f"re-bound {n_proc} mate(s), {n_fail} already-valid skipped")
    return n_proc


async def refresh_assembly(
    adapter: Any, asm_name: str, views: Iterable[str] = DEFAULT_VIEWS
) -> dict[str, str]:
    """Reload an assembly's parts in place -- the cheap incremental rebuild.

    A ``.SLDASM`` is a thin reference layer over its part files (component refs +
    mates + transforms, not baked geometry), so when only a referenced
    ``.SLDPRT``/sub-``.SLDASM`` changed, reopening the assembly + per-config
    ``ForceRebuild3`` loads the new geometry WITHOUT re-inserting/re-mating the
    ~122 components a from-scratch ``create_assembly`` costs (~500 s). This is the
    cheap path of the incremental build graph (see ``dodo.py``).

    Self-healing, then fail loud. Every configuration is force-rebuilt. A
    non-warning What's Wrong fault -- typically a mate dangled because a
    from-scratch part rebuild re-IDed the face it selected -- first triggers an
    in-place ``AutoMateRepair`` (the broken mates re-bind in ~5 s instead of a
    ~500 s full re-insert/re-mate); only if the re-read is STILL faulted does the
    refresh raise, naming the config + the broken feature/mate. Then the
    rest/export pose is re-activated and the
    standard gates run: ``assert_components_fully_defined`` (free DOF),
    ``check_no_interference`` (overlaps), ``assert_model_healthy`` (deep mate
    health). Any gate raises a ``RuntimeError`` naming the culprit and the
    ``.SLDASM`` is left untouched (the in-place save never runs) -- so an
    UNHEALABLE dangling mate (AutoMateRepair could not re-bind it) or a geometry
    change that grows into a neighbour (interference) HALTS the build rather than
    saving a stale/broken artefact. The caller escalates to a full from-scratch
    rebuild via the ``full`` escape (delete the target + ``doit assembly:<stem>``).
    """
    asm_path = (OUT_SLDASM / f"{asm_name}.SLDASM").resolve()
    if not asm_path.exists():
        raise RuntimeError(
            f"missing assembly {asm_path}; build it from scratch first")
    with _telemetry.span("open", asm=asm_name):
        check(f"open {asm_name}", await adapter.open_model(str(asm_path)))
        configs = check("list configurations", await adapter.list_configurations())
    log(f"refresh {asm_name}: {len(configs)} configuration(s): {configs}")
    # The deterministic export/rest pose: Default is the saved, rendered pose the
    # top-level assembly references, and the DOF gate runs on it.
    rest = "Default" if "Default" in configs else (configs[0] if configs else None)

    # Per-config rebuild: load the new part geometry into EVERY configuration so a
    # config-specific break (a config whose mesh entity moved) is caught here, not
    # silently saved. Any under-defined-by-design config is NOT a fault --
    # whats_wrong reports feature/mate rebuild errors, not free DOF.
    repaired_any = False
    with _telemetry.span("rebuild_configs", count=len(configs)):
        for cfg in configs:
            with _telemetry.span("rebuild_config", config=cfg):
                check(f"activate {cfg}", await adapter.set_active_configuration(cfg))
                adapter._attempt(
                    lambda: adapter.currentModel.ForceRebuild3(False), default=None)
                faults = _rebuild_faults(adapter)
                if faults:
                    # The sharp edge: a from-scratch part rebuild re-IDs the faces
                    # its mates selected, dangling them. Auto-heal in place with
                    # AutoMateRepair before failing, then rebuild + re-read. Success
                    # is judged by the CLEAN re-read below + the standard gates --
                    # not by AutoMateRepair's own return code.
                    log(f"refresh {asm_name}: configuration {cfg!r} has {len(faults)} "
                        f"rebuild fault(s) (dangling mate / re-IDed face?); auto-healing ...")
                    repaired_any = repair_dangling_mates(adapter) > 0 or repaired_any
                    adapter._attempt(
                        lambda: adapter.currentModel.ForceRebuild3(False), default=None)
                    faults = _rebuild_faults(adapter)
                if faults:
                    raise RuntimeError(
                        f"refresh {asm_name}: configuration {cfg!r} STILL has rebuild faults "
                        f"after AutoMateRepair (unhealable -- escalate to a full rebuild: "
                        f"delete the .SLDASM target + `doit assembly:{asm_name}`): "
                        + ", ".join(faults))
                log(f"refresh {asm_name}: configuration {cfg} rebuilt clean")

    # Back to the rest pose for the gates + save: the saved active config and the
    # exported PNGs must match the from-scratch build's deterministic pose.
    if rest is not None:
        with _telemetry.span("reactivate", config=rest):
            check(f"re-activate {rest}", await adapter.set_active_configuration(rest))

    # Gates -- each already raises a RuntimeError naming the culprit. No fallback.
    assert_components_fully_defined(adapter)
    check_no_interference(adapter)
    assert_model_healthy(adapter, label=asm_name, deep=True)

    # Decide whether this refresh actually changed the resolved geometry before
    # saving: an in-place Save3 always rewrites a fresh md5, which would invalidate
    # the parent even for a no-op reload of unchanged parts. Gate the bump on the
    # mass-properties fingerprint so a true no-op leaves the .SLDASM byte-stable.
    # A successful AutoMateRepair ALSO forces the save even when the fingerprint is
    # unchanged (a PID-churn-only rebuild): the re-bound mate PIDs MUST persist, or
    # every later refresh re-dangles and re-heals the same mates forever.
    digest = await assembly_geometry_digest(adapter, asm_name)
    sidecar = _massprops_sidecar(asm_name)
    try:
        prev = sidecar.read_text(encoding="utf-8").strip()
    except OSError:
        prev = None
    geometry_changed = prev != digest or repaired_any

    with _telemetry.span("save", asm=asm_name, changed=geometry_changed):
        if geometry_changed:
            set_isometric_view(adapter)  # opens isometric; only when we actually re-save
        save_assembly_in_place(adapter, asm_name, geometry_changed)
    sidecar.parent.mkdir(parents=True, exist_ok=True)
    sidecar.write_text(digest + "\n", encoding="utf-8")

    artefacts = {"assembly": str(asm_path)}
    artefacts.update(await _export_assembly_images(adapter, asm_name, views))
    return artefacts
