r"""Reproduction script: crank arm (book ch. 11, pp. 12-15).

The metal crank arm that drives the machine: full-radius boss at the
crankshaft end (bored for the shaft and cross-drilled for the removable
tapered pin), straight arm, square end carrying the handle pivot, and a
fiducial dimple for alignment. The wooden handle and the tapered pin are
separate parts (build_crank_handle.py / build_crank_pin.py); the chain
eyelet (chain lost) is omitted.

Dimensions: cad/DIMENSIONS.md "Chapter 11" — all photo-scaled (low) except
the legacy 3/8" crankshaft bore (med).

Layout: arm length along +X from the origin (shaft bore axis = global Z
through the origin), thickness extruded +Z (0..8). The cross-pin hole runs
along global Y at mid-thickness: probed live, a Top-plane sketch maps
(x, y) -> global (X, -Z), so the hole circle sits at sketch (0, -4).
Through-cuts use mid-plane blind cuts (depth > extent) because the
ThroughAll+both_directions combination fails live on SW 2026 (MCP issue
#38); the dimple uses a mid-plane cut of twice its depth so the cut
direction never matters.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_crank_arm.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    POLISHED_STEEL,
    SketchDims,
    add_line_chain,
    apply_color,
    apply_material,
    name_bore_axis,
    check,
    define_circle,
    drive_dimension,
    ensure_fully_defined,
    extrude_at_offset,
    force_rebuild,
    name_dimensions,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    set_sketch_direct_db,
    volume_check,
)
from _holes import HoleSpec, blind_hole_volume_mm3, wizard_holes

import _telemetry
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from crank_arm_spec import (
    ARM_C2C,
    ARM_END_X,
    ARM_THICKNESS,
    ARM_WIDTH,
    DIMPLE_DEPTH,
    DIMPLE_DIA,
    DIMPLE_X,
    DRAWING_NOTES,
    DRAWING_DIMENSIONS,
    END_ROUND_R,
    HALF_WIDTH,
    HUB_DIA,
    HUB_LEN,
    ISOMETRIC_VIEW_NOTE,
    KEEPER_X,
    PIN_HOLE_Z,
    SHAFT_BORE_DIA,
    SQUARE_END_OVERHANG,
)
from crank_pin_spec import PIN_SEAT_PROUD, hole_dia_at

PART_NAME = "crank-arm"
MATERIAL = "Plain Carbon Steel"  # see _common.apply_material docstring

# (The old PivotBoreDia Ø6.0 and PinHoleDia Ø5.0 constants are gone: the handle-
# pivot hole and the tapered-pin cross-hole are now native Hole Wizard features
# whose diameters come from the drill standard -- 15/64 (Ø5.953) and #14 (Ø4.623)
# -- not equation-driven sketch dims. The 3/8 shaft bore stays a reamed circle
# cut: it is a precision running fit, not a twist-drill hole.)

THROUGH_CUT_DEPTH = 40.0  # mid-plane total; > any extent it crosses


def _x_strip_area(r: float, b: float) -> float:
    """Area of a radius-r disc (centred x=0) restricted to ``|x| <= b``."""
    import math as _m

    b = min(b, r)
    if b <= 0.0:
        return 0.0
    return 2.0 * (b * _m.sqrt(r * r - b * b) + r * r * _m.asin(b / r))


def _pin_cone_removal_mm3() -> float:
    """Removed volume of the 1:48 as-reamed pin cone through the hub wall.

    Simpson integration along the hole axis (arm-local Y, -8..+8). The hub is
    a Z-axis cylinder, so each constant-y slice of the hub is the x-strip
    ``|x| <= sqrt(hub_r^2 - y^2)`` (all hole z-stations lie inside the hub's
    z-band), minus the already-bored shaft strip ``|x| <= sqrt(bore_r^2 -
    y^2)``. The hole slice is a disc of the ``hole_dia_at`` cone radius
    centred on x=0, so the removed area is the disc clipped to each strip.
    """
    hub_r = HUB_DIA / 2.0
    bore_r = SHAFT_BORE_DIA / 2.0
    n = 400
    y0, y1 = -HALF_WIDTH, HALF_WIDTH
    h = (y1 - y0) / n
    total = 0.0
    for i in range(n + 1):
        y = y0 + i * h
        rh = hole_dia_at(PIN_SEAT_PROUD + (HALF_WIDTH - y)) / 2.0
        w_hub = max(0.0, hub_r * hub_r - y * y) ** 0.5
        w_bore = max(0.0, bore_r * bore_r - y * y) ** 0.5
        area = _x_strip_area(rh, w_hub) - _x_strip_area(rh, w_bore)
        w = 1.0 if i in (0, n) else (4.0 if i % 2 else 2.0)
        total += w * area
    return total * h / 3.0


async def _volume(adapter) -> float:
    res = await adapter.get_mass_properties()
    return res.data.volume if res.is_success else float("nan")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): every module constant above as a named
    # global that drives the dimensions below. The mm suffix is load-bearing --
    # this is an INCH document and the equation manager reads BARE numbers in
    # document units, so an unsuffixed 66 would be read as 66 inches and blow the
    # part up 25.4x. ArmEndX is a derived span (equation of the primitives) so the
    # square end stays SQUARE_END_OVERHANG past the pivot when either changes.
    await set_global(adapter, "ArmC2C", f"{ARM_C2C}mm")
    await set_global(adapter, "ArmWidth", f"{ARM_WIDTH}mm")
    await set_global(adapter, "ArmThickness", f"{ARM_THICKNESS}mm")
    await set_global(adapter, "SquareEndOverhang", f"{SQUARE_END_OVERHANG}mm")
    await set_global(adapter, "ShaftBoreDia", f"{SHAFT_BORE_DIA}mm")
    await set_global(adapter, "DimpleDia", f"{DIMPLE_DIA}mm")
    await set_global(adapter, "DimpleDepth", f"{DIMPLE_DEPTH}mm")
    await set_global(adapter, "DimpleX", f"{DIMPLE_X}mm")
    await set_global(adapter, "HubDia", f"{HUB_DIA}mm")
    await set_global(adapter, "ArmEndX", '"ArmC2C" + "SquareEndOverhang"')

    # Each sketch declares its dim names + drive equations as it is built; a
    # per-sketch SketchDims records each dim in emission order, then apply()
    # renames them and collects the drive jobs run in one deferred batch at the
    # end (every equation target must resolve against the finished model).
    drive_jobs: list[tuple[str, str]] = []

    # Arm outline: full-radius boss cap (arc about the origin) + 3 lines.
    outline = SketchDims()
    check("create_sketch outline", await adapter.create_sketch("Front"))
    arc = check(
        "add_arc boss cap",
        await adapter.add_arc(0.0, 0.0, 0.0, HALF_WIDTH, 0.0, -HALF_WIDTH),
    )
    bottom, right, top = await add_line_chain(
        adapter,
        [
            (0.0, -HALF_WIDTH),
            (ARM_END_X, -HALF_WIDTH),
            (ARM_END_X, HALF_WIDTH),
            (0.0, HALF_WIDTH),
        ],
        close=False,
    )
    check("constraint horizontal bottom", await adapter.add_sketch_constraint(bottom, None, "horizontal"))
    check("constraint vertical right", await adapter.add_sketch_constraint(right, None, "vertical"))
    check("constraint horizontal top", await adapter.add_sketch_constraint(top, None, "horizontal"))
    # Manual dims recorded into SketchDims as created (creation order): the arm
    # length on the bottom line, then the boss-cap radius.
    check(
        f"dimension arm length = {ARM_END_X:g}",
        await adapter.add_sketch_dimension(bottom, None, "linear", ARM_END_X),
    )
    outline.record("ArmEndX", '"ArmEndX"')
    # Boss cap: centre at the origin + radius + both ends on the Y axis
    # fully pin the semicircle; the merged chain follows.
    check(
        "boss centre -> origin",
        await adapter.add_sketch_constraint(f"{arc}.center", "origin", "coincident"),
    )
    check("boss radius", await adapter.add_sketch_dimension(arc, None, "radial", HALF_WIDTH))
    outline.record("BossRadius", '"ArmWidth" / 2')
    for point in (f"{arc}.start", f"{arc}.end"):
        check(
            f"{point} on Y axis",
            await adapter.add_sketch_constraint(point, "origin", "vertical_points"),
        )
    await ensure_fully_defined(adapter, "arm outline")
    check("exit_sketch outline", await adapter.exit_sketch())
    name_last_feature(adapter, "ArmOutline")
    drive_jobs += outline.apply(adapter, "ArmOutline")
    check(
        "extrude arm",
        await adapter.create_extrusion(ExtrusionParameters(depth=ARM_THICKNESS)),
    )
    name_last_feature(adapter, "Arm")
    depth_dim = name_dimensions(adapter, "Arm", ["Depth"])
    drive_jobs += [(depth_dim[0], '"ArmThickness"')]
    vol = await _volume(adapter)
    _telemetry.info(f"volume after extrude: {vol:.1f} mm^3")

    # Full-round handle end (ch11 photos): two corner fillets on the stock
    # end's vertical edges, meeting at the centreline. The outline sketch and
    # its ArmEndX dim are untouched -- the print still dimensions the 76 stock
    # span and notes the full-round.
    check(
        "fillet handle end",
        await adapter.add_fillet(
            END_ROUND_R,
            [
                [ARM_END_X, HALF_WIDTH, ARM_THICKNESS / 2.0],
                [ARM_END_X, -HALF_WIDTH, ARM_THICKNESS / 2.0],
            ],
        ),
    )
    name_last_feature(adapter, "EndRound")
    v_corner = END_ROUND_R * END_ROUND_R * (1.0 - math.pi / 4.0) * ARM_THICKNESS
    vol_expect = vol - 2.0 * v_corner
    vol = await volume_check(adapter, "full-round end", vol_expect, 0.02 * v_corner + 1.0)

    # Rear hub boss (ch11 page002_img03/img04): the boss circle carried
    # HUB_LEN through the plate's north face (local -Z), bridging the plate to
    # the T12 chain wheel and carrying the pin cross-hole. Cut before the
    # shaft bore so the bore reams plate + hub in one pass.
    hub = SketchDims()
    check("create_sketch hub", await adapter.create_sketch("Front"))
    await define_circle(
        adapter, 0.0, 0.0, HUB_DIA / 2.0, "hub", dims=hub,
        names=("HubX", "HubZ", "HubDia"),
        drives=(None, None, '"HubDia"'),
    )
    await ensure_fully_defined(adapter, "hub sketch")
    check("exit_sketch hub", await adapter.exit_sketch())
    name_last_feature(adapter, "HubProfile")
    drive_jobs += hub.apply(adapter, "HubProfile")
    extrude_at_offset(adapter, HUB_LEN, 0.0, flip=True)
    name_last_feature(adapter, "Hub")
    vol_expect = vol + math.pi * (HUB_DIA / 2.0) ** 2 * HUB_LEN
    vol = await volume_check(adapter, "hub boss", vol_expect, 2.0)

    # Shaft bore: the 3/8 reamed journal the crankshaft runs in -- a precision
    # running fit, kept a plain circle cut (NOT a twist-drill Hole Wizard hole).
    # On the origin, so only its diameter is a dim.
    shaft_bore = SketchDims()
    check("create_sketch shaft bore", await adapter.create_sketch("Front"))
    await define_circle(
        adapter, 0.0, 0.0, SHAFT_BORE_DIA / 2.0, "shaft bore", dims=shaft_bore,
        names=("ShaftBoreX", "ShaftBoreZ", "ShaftBoreDia"),
        drives=(None, None, '"ShaftBoreDia"'),
    )
    await ensure_fully_defined(adapter, "shaft bore sketch")
    check("exit_sketch shaft bore", await adapter.exit_sketch())
    name_last_feature(adapter, "ShaftBoreProfile")
    drive_jobs += shaft_bore.apply(adapter, "ShaftBoreProfile")
    check(
        "cut shaft bore",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "ShaftBore")

    # Handle-pivot hole: was a plain Ø6.0 cut, now a native Hole Wizard 15/64
    # fractional drill (Ø5.953) at the handle-pivot centre (ARM_C2C), drilled +Z
    # through the 8 mm plate (memory/fastener-policy-us-customary). Cut while the
    # body is still prismatic (~15 faces) -- wizard_holes enumerates every face.
    pivot_cut = wizard_holes(
        adapter,
        HoleSpec("drilled_fractional", "15/64"),
        [[ARM_C2C, 0.0, ARM_THICKNESS]],
        (0.0, 0.0, 1.0),
        "handle-pivot hole (15/64)",
        name="PivotBore",
        placement_dims=[(("PivotBoreX", '"ArmC2C"'), (None, None))],
    )
    drive_jobs += pivot_cut.placement_drive_jobs
    vol = await _volume(adapter)
    _telemetry.info(f"volume after bores: {vol:.1f} mm^3")

    # Fiducial dimple on the Z=0 face (which face carries it is arbitrary
    # until assembly). Mid-plane cut of 2x depth: only the +Z half removes
    # material, so the result is DIMPLE_DEPTH regardless of cut direction.
    dimple = SketchDims()
    check("create_sketch dimple", await adapter.create_sketch("Front"))
    await define_circle(
        adapter, DIMPLE_X, 0.0, DIMPLE_DIA / 2.0, "dimple", dims=dimple,
        names=("DimpleX", "DimpleZ", "DimpleDia"),
        drives=('"DimpleX"', None, '"DimpleDia"'),
    )
    await ensure_fully_defined(adapter, "dimple sketch")
    check("exit_sketch dimple", await adapter.exit_sketch())
    name_last_feature(adapter, "DimpleProfile")
    drive_jobs += dimple.apply(adapter, "DimpleProfile")
    check(
        "cut dimple",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=2.0 * DIMPLE_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Dimple")
    vol = await _volume(adapter)
    _telemetry.info(f"volume after dimple: {vol:.1f} mm^3")

    # Tapered-pin cross-hole, AS-REAMED (ch11 close-ups): the pin's own 1:48
    # cone plus the 0.25 running clearance, through the HUB at PIN_HOLE_Z
    # (machine z -163 -- exactly build_crankshaft's PIN_HOLE_HEIGHT station).
    # A straight pilot cannot seat the taper pin without solid interference
    # (the very reason the pin was never placed); the model carries the
    # assembly-reamed state. Revolve-cut about the hole axis (the adapter's
    # documented oblique-bore idiom -- FeatureCut4's draft flag is hardcoded
    # off, so a draft-extrude cannot make this cone): a right trapezoid
    # between the axis centerline and the 1:48 taper line, swept 360.
    # Sketched on the Right Plane (x=0, which contains the hole axis); the
    # sketch frame maps (u, v) -> global (-Z, +Y) with extrude normal +X
    # (probed live 2026-07-20: a circle at sketch (5, 2) lands COM (1, 2, -5)).
    # So the hole axis (global Y at Z=PIN_HOLE_Z) is the vertical sketch line
    # u=-PIN_HOLE_Z, and the big end (global +Y, machine outboard) is at v=+8.
    from solidworks_mcp.adapters.base import RevolveParameters

    r_entry = hole_dia_at(PIN_SEAT_PROUD) / 2.0
    r_exit = hole_dia_at(PIN_SEAT_PROUD + ARM_WIDTH) / 2.0
    u_axis = -PIN_HOLE_Z  # +4: sketch-u of the hole axis (global z -4)
    check("create_sketch pin hole", await adapter.create_sketch("Right"))
    set_sketch_direct_db(adapter, True)
    pin_axis_line = check(
        "add_centerline pin-hole axis",
        await adapter.add_centerline(u_axis, HALF_WIDTH, u_axis, -HALF_WIDTH),
    )
    pin_lines = await add_line_chain(
        adapter,
        [
            (u_axis, HALF_WIDTH),
            (u_axis + r_entry, HALF_WIDTH),
            (u_axis + r_exit, -HALF_WIDTH),
            (u_axis, -HALF_WIDTH),
        ],
    )
    set_sketch_direct_db(adapter, False)
    entry_line, _taper, exit_line, _closure = pin_lines
    check(
        "axis vertical",
        await adapter.add_sketch_constraint(pin_axis_line, None, "vertical"),
    )
    for label, ent in (("entry", entry_line), ("exit", exit_line)):
        check(
            f"{label} horizontal",
            await adapter.add_sketch_constraint(ent, None, "horizontal"),
        )
    # Fully define with unsigned dims: axis length, the two radii, and the
    # axis position off the origin (4 down, 8 along).
    check(
        "axis length",
        await adapter.add_sketch_dimension(pin_axis_line, None, "linear", ARM_WIDTH),
    )
    check(
        "entry radius",
        await adapter.add_sketch_dimension(entry_line, None, "linear", r_entry),
    )
    check(
        "exit radius",
        await adapter.add_sketch_dimension(exit_line, None, "linear", r_exit),
    )
    check(
        "axis station",
        await adapter.add_sketch_dimension(
            f"{pin_axis_line}.start", "origin", "horizontal_distance", abs(PIN_HOLE_Z)
        ),
    )
    check(
        "axis reach",
        await adapter.add_sketch_dimension(
            f"{pin_axis_line}.start", "origin", "vertical_distance", HALF_WIDTH
        ),
    )
    await ensure_fully_defined(adapter, "pin hole sketch")
    check("exit_sketch pin hole", await adapter.exit_sketch())
    name_last_feature(adapter, "PinHoleProfile")
    check(
        "revolve-cut pin cone",
        await adapter.create_revolve(RevolveParameters(angle=360.0, is_cut=True)),
    )
    name_last_feature(adapter, "PinHole")
    v_cone = _pin_cone_removal_mm3()
    vol_expect = vol - v_cone
    vol = await volume_check(adapter, "pin cone hole", vol_expect, 6.0)

    # Keeper-screw pocket: 1/8 drill, 3.4 deep, in the +Y edge near the hub --
    # the fillister eyelet screw threads here with the brass chain eyelet on
    # its exposed shank (ch11 page002_img03).
    keeper_cut = wizard_holes(
        adapter,
        HoleSpec("drilled_fractional", "1/8", end="blind", depth_mm=3.4),
        [[KEEPER_X, HALF_WIDTH, ARM_THICKNESS / 2.0]],
        (0.0, 1.0, 0.0),
        "keeper screw pocket (1/8 x 3.4)",
        name="KeeperHole",
    )
    del keeper_cut  # static placement; no driven dims
    vol_expect = vol - blind_hole_volume_mm3(3.175, 3.4)
    vol = await volume_check(adapter, "keeper pocket", vol_expect, 1.0)

    # Named bore/central axis for view-independent assembly mate
    # selection (M6 mated-DOF drive train). Axis1 = shaft bore (on origin);
    # Axis2 = the handle PIVOT bore at +X (ARM_C2C), so the drive-train assembly
    # can journal the crank handle COAXIAL to its real pivot pin (replacing the
    # handle's lock with a semantic pin joint). Order is load-bearing: the shaft
    # axis is created first so it stays Axis1@<arm>.
    await name_bore_axis(adapter, "Top Plane", 0.0, "Right Plane", 0.0, "shaft bore axis")
    pivot_axis = await name_bore_axis(
        adapter,
        "Top Plane",
        0.0,
        "Right Plane",
        ARM_C2C,
        "pivot bore axis",
        drive_b='"ArmC2C"',
        drive_jobs=drive_jobs,
    )
    _telemetry.info(f"handle pivot bore axis -> {pivot_axis} (expect Axis2)")

    # Apply the deferred drive equations now -- after the whole model + a rebuild
    # exists, so every target resolves. Each equation evaluates to the value just
    # built, so the geometry must not move; the as-built volume captured above is
    # the neutrality reference for the re-check below.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven crank arm (equations neutral)", vol, 0.001 * vol)

    # HandleSeat datum: the plate face OPPOSITE the origin plane (z =
    # ARM_THICKNESS). The chirality-mirrored drive-train maps part +z to
    # machine -z, so this is the arm's SOUTH face -- the crank handle's brass
    # collar butts flush against it (its Right/origin plane mates COINCIDENT
    # here, the flip-free seat idiom; seating on Front@arm instead buried the
    # collar inside the plate, 502 mm^3, 2026-07-05).
    from solidworks_mcp.adapters.base import CreatePlaneParameters

    check(
        f"create_plane HandleSeat (Front Plane, +{ARM_THICKNESS})",
        await adapter.create_plane(CreatePlaneParameters(
            mode="offset", base_plane="Front Plane", offset=ARM_THICKNESS,
        )),
    )
    name_last_feature(adapter, "HandleSeat")

    # Manufacturing drawing support: mark exactly the print's dimensions (the
    # drawing recipe imports the marked set and must find every one of these),
    # and stamp the make-critical title-block properties.
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)

    await apply_material(adapter, MATERIAL)
    # The ch11 photos show the arm bright nickel-polished (the "crank" label
    # face) -- the bare carbon-steel appearance renders near-black.
    await apply_color(adapter, POLISHED_STEEL)
    await report_mass_properties(adapter)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": DRAWING_NOTES,
            "Isometric View Note": ISOMETRIC_VIEW_NOTE,
        },
    )
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
