r"""Reproduction script: harmonic analyzer base (book ch. 6 / legacy part).

Two-plate welded construction: bottom plate 18.0 x 11.0 x 0.5 in with a
17.5 x 10.5 x 1.5 in top plate centered on it. Re-authors the legacy
HarmonicBase.cs; the book's p.3 photo callouts (46 x 28 cm = 18.1 x 11.0 in)
confirm the legacy footprint, so the legacy inch dims are kept.

Deferred: the legacy 0.125"/0.0625" edge fillets are cosmetic and need
edge-selection tooling — re-added with the M4 finishing pass.

Dimensions: cad/DIMENSIONS.md "Chapter 6" — annotated (high) footprint,
legacy thicknesses (photo-verify note).

Layout: plates centered on the origin, Top-plane sketches (sketch x,y ->
global X,-Z), stacked along +Y. Top plate boss starts at the bottom plate's
upper face via extrude_at_offset (raw-COM stopgap until MCP Phase 3).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_harmonic_base.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    CASTING_GREEN,
    SketchDims,
    apply_color,
    apply_material,
    check,
    define_centered_rectangle,
    define_circle,
    drive_dimension,
    ensure_fully_defined,
    extrude_at_offset,
    force_rebuild,
    measure_check,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    volume_check,
)

import _telemetry

PART_NAME = "harmonic-base"
MATERIAL = "Gray Cast Iron"  # see _common.apply_material docstring

IN = 25.4
BOTTOM_LENGTH = 18.0 * IN  # DIMENSIONS.md ch6: 46 cm callout = 18.1" (annotated)
BOTTOM_WIDTH = 11.0 * IN  # DIMENSIONS.md ch6: 28 cm callout = 11.0" (annotated)
BOTTOM_THICKNESS = 0.5 * IN  # legacy HarmonicBase.cs (photo-verify M2 note)
TOP_LENGTH = 17.5 * IN  # legacy: 0.25" reveal per side
TOP_WIDTH = 10.5 * IN
TOP_THICKNESS = 1.5 * IN

# Rocker-support hold-down holes (machine = part-local: frame.SLDASM places the
# base unrotated at the origin). Four through-drilled O13 clearance holes laid out
# to MATCH the rocker-arm-support foot's 9/16-12 tapped pattern (build_rocker_arm_
# support.py FootTappedHoles, local X +/-60.32 Z +/-17.46 -> after the part's
# +90deg-Y turn, machine x 72.9 -/+ 17.46 = 55.44/90.36, z +/-60.32). Every hole
# gets an O23 x 6.5 head counterbore up from the underside for the recessed lag-
# screw head, so the four 9/16-12 lag screws (build_lag_screw.py) come up through
# the base into the foot's tapped holes. The old portal-era pattern (south foot-
# rail hex-bolts + north lag screws) is gone with the portal it served.
HOLE_DIA = 13.0  # 9/16 lag-screw shank O12 clearance
HOLE_XZ = (
    (55.44, 60.32),   # support foot, west pair
    (55.44, -60.32),
    (90.36, 60.32),   # support foot, east pair
    (90.36, -60.32),
)
CBORE_DIA = 23.0  # lag head O22, recessed
CBORE_DEPTH = 6.5  # lag head 22 x 6 recessed 0.5
CBORE_XZ = HOLE_XZ  # all four heads counterbored

# Cone swing hardware, blind from the TOP face. MACHINE-handed part coords:
# frame.SLDASM places the base unmirrored (like the rocker-arm-support and
# the four hold-down holes above), but the drive-train screws that drop into
# these holes are placed through mirror_placement, so their PRE-MIRROR x
# NEGATES here (proven at the top-level interference gate: holes authored at
# pre-mirror +x left both screws in solid base -- 190.0 + 75.4 mm^3, exactly
# the two embedded shank volumes). The drive-train assembly asserts agreement
# WITH the sign flip: pivot = -cone_station(PIVOT_STATION).x
# (build_cone_pivot_screw), stop = -(disengaged east plate edge + shank
# radius) (build_swing_stop_screw).
PIVOT_SCREW_XZ = (-79.69, 103.29)
PIVOT_SCREW_HOLE_DIA = 6.5  # O6.35 shoulder clearance
STOP_SCREW_XZ = (-130.93, 9.94)  # past the DISENGAGED east taper edge (the
# disengage swing sweeps the plate EAST pre-mirror = machine -x; the first
# derivation sat 19 inside the engaged plate -- interference-gate proven)
STOP_SCREW_HOLE_DIA = 4.1  # O4 shank clearance
SWING_HOLE_DEPTH = 6.0

# Alignment-pinion rig hold-downs (PR7 items 2/11/12), blind from the TOP face
# like the swing hardware: four Ø4.2 holes under the two pivot blocks' bright
# slotted screws (build_pinion_pivot_block SCREW_* stations: block x -6.336
# +/- 13.5, hole z = block z0 + depth/2 -- asserted at drive-train import) and
# two Ø3.2 holes under the black foot screws (build_foot_screw): the spring
# foot and the arbor-pedestal flange.
BLOCK_SCREW_XZ = (
    (7.164, -98.0),    # front block, east screw
    (-19.836, -98.0),  # front block, west screw
    (7.164, 82.0),     # back block, east screw
    (-19.836, 82.0),   # back block, west screw
)
BLOCK_SCREW_HOLE_DIA = 4.2  # slotted-screw O4 shank clearance
BLOCK_SCREW_HOLE_DEPTH = 3.5  # 18 shank - 16 block = 2 buried + 1.5 air
FOOT_SCREW_XZ = (
    (-20.467, 70.95),  # spring foot (build_pinion_spring hole: the west foot
    # crosses under the lift rod so its screw lands west of the moving rig)
    (54.7, -95.5),     # arbor-pedestal flange (build_arbor_pedestal SCREW_Z)
)
FOOT_SCREW_HOLE_DIA = 3.2  # foot-screw O2.9 shank clearance
FOOT_SCREW_HOLE_DEPTH = 7.7  # 8.0 shank under the 0.8 spring strip + air

MM3_PER_IN3 = IN**3


def _pos_drive(global_name: str, sketch_value: float) -> str:
    """Drive expression for an UNSIGNED centre-distance dim whose global holds the
    signed sketch coordinate. The dim displays the magnitude, so the equation must
    evaluate POSITIVE -- negate the global when the coordinate is negative (driving
    such a dim to a negative value fails loud at equation-add)."""
    return f'-"{global_name}"' if sketch_value < 0.0 else f'"{global_name}"'


async def _volume(adapter) -> float:
    res = await adapter.get_mass_properties()
    return res.data.volume if res.is_success and res.data else float("nan")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): the two plate footprints + thicknesses,
    # the hole/counterbore diameters, and each fastener-hole station. The mm
    # suffix is load-bearing -- this is an INCH document and the equation manager
    # reads BARE numbers in document units (an unsuffixed 457.2 = 457 inches and
    # blows the part up 25.4x). The thicknesses / cbore depth are extrude/offset
    # feature parameters (not sketch dims), exposed here as editable constants even
    # though nothing in drive_jobs drives them.
    await set_global(adapter, "BottomLength", f"{BOTTOM_LENGTH}mm")
    await set_global(adapter, "BottomWidth", f"{BOTTOM_WIDTH}mm")
    await set_global(adapter, "BottomThickness", f"{BOTTOM_THICKNESS}mm")
    await set_global(adapter, "TopLength", f"{TOP_LENGTH}mm")
    await set_global(adapter, "TopWidth", f"{TOP_WIDTH}mm")
    await set_global(adapter, "TopThickness", f"{TOP_THICKNESS}mm")
    await set_global(adapter, "HoleDia", f"{HOLE_DIA}mm")
    await set_global(adapter, "CboreDia", f"{CBORE_DIA}mm")
    await set_global(adapter, "CboreDepth", f"{CBORE_DEPTH}mm")
    # One global per fastener-hole station, holding the SKETCH-space coordinate
    # (define_circle receives (x, -z), so the z global is the negated machine z).
    # The centre dims are unsigned distances -- _pos_drive negates a negative
    # global so the equation evaluates positive.
    for i, (x, z) in enumerate(HOLE_XZ):
        await set_global(adapter, f"Hole{i}X", f"{x}mm")
        await set_global(adapter, f"Hole{i}Z", f"{-z}mm")

    # Each sketch DECLARES its dim names + drive equations inline; a per-sketch
    # SketchDims records each dim in the helper's emission order. Drive equations
    # are collected here and applied in one deferred batch at the end (every
    # target must resolve against the finished model).
    drive_jobs: list[tuple[str, str]] = []

    # Bottom plate, centered on the origin.
    bottom = SketchDims()
    check("create_sketch bottom", await adapter.create_sketch("Top"))
    await define_centered_rectangle(
        adapter, BOTTOM_LENGTH / 2.0, BOTTOM_WIDTH / 2.0, "bottom plate", dims=bottom,
        name_width="BottomLen", drive_width='"BottomLength"',
        name_depth="BottomWid", drive_depth='"BottomWidth"',
        name_corner=("BottomCornerX", "BottomCornerZ"),
        drive_corner=('"BottomLength" / 2', '"BottomWidth" / 2'),
    )
    await ensure_fully_defined(adapter, "bottom plate sketch")
    check("exit_sketch bottom", await adapter.exit_sketch())
    name_last_feature(adapter, "BottomProfile")
    drive_jobs += bottom.apply(adapter, "BottomProfile")
    check(
        "extrude bottom",
        await adapter.create_extrusion(ExtrusionParameters(depth=BOTTOM_THICKNESS)),
    )
    name_last_feature(adapter, "BottomPlate")
    _telemetry.info(f"volume after bottom plate: {await _volume(adapter):.1f} mm^3")
    # expected: 18 * 11 * 0.5 in^3 = 99 in^3 = 1,622,319 mm^3

    # Top plate, centered, starting at the bottom plate's upper face.
    top = SketchDims()
    check("create_sketch top", await adapter.create_sketch("Top"))
    await define_centered_rectangle(
        adapter, TOP_LENGTH / 2.0, TOP_WIDTH / 2.0, "top plate", dims=top,
        name_width="TopLen", drive_width='"TopLength"',
        name_depth="TopWid", drive_depth='"TopWidth"',
        name_corner=("TopCornerX", "TopCornerZ"),
        drive_corner=('"TopLength" / 2', '"TopWidth" / 2'),
    )
    await ensure_fully_defined(adapter, "top plate sketch")
    check("exit_sketch top", await adapter.exit_sketch())
    name_last_feature(adapter, "TopProfile")
    drive_jobs += top.apply(adapter, "TopProfile")
    extrude_at_offset(adapter, TOP_THICKNESS, BOTTOM_THICKNESS)
    name_last_feature(adapter, "TopPlate")
    _telemetry.info(f"volume after top plate: {await _volume(adapter):.1f} mm^3")
    # expected: 99 + 17.5 * 10.5 * 1.5 = 374.625 in^3 = 6,139,003 mm^3

    # M6.10 fastener holes: Top sketch (x, y) -> global (X, -Z), mid-plane
    # cuts so the direction never matters (below y 0 is outside the part).
    total = BOTTOM_THICKNESS + TOP_THICKNESS
    pre_holes = await _volume(adapter)
    holes = SketchDims()
    check("create_sketch fastener holes", await adapter.create_sketch("Top"))
    for i, (x, z) in enumerate(HOLE_XZ):
        await define_circle(
            adapter, x, -z, HOLE_DIA / 2.0, f"hole ({x:.2f}, {z:.1f})", dims=holes,
            names=(f"Hole{i}Cx", f"Hole{i}Cz", f"Hole{i}Dia"),
            drives=(
                _pos_drive(f"Hole{i}X", x),
                _pos_drive(f"Hole{i}Z", -z),
                '"HoleDia"',
            ),
        )
    await ensure_fully_defined(adapter, "fastener holes sketch")
    check("exit_sketch fastener holes", await adapter.exit_sketch())
    name_last_feature(adapter, "FastenerHoleProfile")
    drive_jobs += holes.apply(adapter, "FastenerHoleProfile")
    check(
        "cut fastener holes",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=3.0 * total, both_directions=True)
        ),
    )
    name_last_feature(adapter, "FastenerHoles")
    before = await _volume(adapter)
    v_holes = len(HOLE_XZ) * math.pi * (HOLE_DIA / 2.0) ** 2 * total
    _telemetry.info(f"volume after holes: {before:.1f} mm^3 (removed analytic {v_holes:.1f})")
    if abs((pre_holes - before) - v_holes) > 0.02 * v_holes:
        raise RuntimeError(
            f"holes removed {pre_holes - before:.1f}, expected {v_holes:.1f}"
        )

    # Lag-screw head counterbores up from the underside: a both-directions
    # cut of 2x depth about the bottom plane lands exactly 0..4.5 in
    # material (the lower half is air).
    cbores = SketchDims()
    check("create_sketch counterbores", await adapter.create_sketch("Top"))
    # CBORE_XZ is HOLE_XZ (all four heads recessed), so each counterbore is
    # concentric with its fastener hole -- reuse the same Hole{i}{X,Z} station
    # globals so a station edit moves both. cbore_offset (0 here) aligns the names.
    cbore_offset = len(HOLE_XZ) - len(CBORE_XZ)
    for j, (x, z) in enumerate(CBORE_XZ):
        i = cbore_offset + j
        await define_circle(
            adapter, x, -z, CBORE_DIA / 2.0, f"cbore ({x:.2f})", dims=cbores,
            names=(f"Cbore{i}Cx", f"Cbore{i}Cz", f"Cbore{i}Dia"),
            drives=(
                _pos_drive(f"Hole{i}X", x),
                _pos_drive(f"Hole{i}Z", -z),
                '"CboreDia"',
            ),
        )
    await ensure_fully_defined(adapter, "counterbores sketch")
    check("exit_sketch counterbores", await adapter.exit_sketch())
    name_last_feature(adapter, "CounterboreProfile")
    drive_jobs += cbores.apply(adapter, "CounterboreProfile")
    check(
        "cut counterbores",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=2.0 * CBORE_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Counterbores")
    after = await _volume(adapter)
    v_cbore = (
        len(CBORE_XZ)
        * math.pi
        * ((CBORE_DIA / 2.0) ** 2 - (HOLE_DIA / 2.0) ** 2)
        * CBORE_DEPTH
    )
    _telemetry.info(f"volume after counterbores: {after:.1f} mm^3 (removed analytic {v_cbore:.1f})")
    if abs((before - after) - v_cbore) > 0.02 * v_cbore:
        raise RuntimeError(
            f"counterbores removed {before - after:.1f}, expected {v_cbore:.1f}"
        )

    # Cone swing hardware holes, blind from the TOP face (see the constants
    # block): pivot screw + swing-stop screw.
    from solidworks_mcp.adapters.base import CreatePlaneParameters as _CPP

    check(
        "create_plane TopFace (swing holes)",
        await adapter.create_plane(_CPP(
            mode="offset", base_plane="Top Plane", offset=total,
        )),
    )
    name_last_feature(adapter, "TopFace")
    swing = SketchDims()
    check("create_sketch swing holes", await adapter.create_sketch("TopFace"))
    for tag, (sx, sz), dia in (
        ("Pivot", PIVOT_SCREW_XZ, PIVOT_SCREW_HOLE_DIA),
        ("Stop", STOP_SCREW_XZ, STOP_SCREW_HOLE_DIA),
    ):
        await define_circle(
            adapter, sx, -sz, dia / 2.0, f"{tag.lower()} screw hole", dims=swing,
            names=(f"{tag}HoleCx", f"{tag}HoleCz", f"{tag}HoleDia"),
            drives=(None, None, None),
        )
    await ensure_fully_defined(adapter, "swing holes sketch")
    check("exit_sketch swing holes", await adapter.exit_sketch())
    name_last_feature(adapter, "SwingHoleProfile")
    drive_jobs += swing.apply(adapter, "SwingHoleProfile")
    # A CUT's default direction is OPPOSITE the sketch normal (FeatureCut4
    # remarks), so from the top-face plane it already drills DOWN into the slab.
    check(
        "cut swing holes (blind)",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=SWING_HOLE_DEPTH)
        ),
    )
    name_last_feature(adapter, "SwingHardwareHoles")
    after_swing = await _volume(adapter)
    v_swing = math.pi * ((PIVOT_SCREW_HOLE_DIA / 2.0) ** 2
                         + (STOP_SCREW_HOLE_DIA / 2.0) ** 2) * SWING_HOLE_DEPTH
    if abs((after - after_swing) - v_swing) > 0.02 * v_swing:
        raise RuntimeError(
            f"swing holes removed {after - after_swing:.1f}, expected {v_swing:.1f}")
    after = after_swing

    # Alignment-pinion rig hold-down holes (PR7), blind from the same top
    # face (see the constants block): 4 block-screw + 2 foot-screw stations,
    # one sketch + cut per diameter/depth group.
    for tag, xz, dia, depth in (
        ("BlockScrew", BLOCK_SCREW_XZ, BLOCK_SCREW_HOLE_DIA, BLOCK_SCREW_HOLE_DEPTH),
        ("FootScrew", FOOT_SCREW_XZ, FOOT_SCREW_HOLE_DIA, FOOT_SCREW_HOLE_DEPTH),
    ):
        rig = SketchDims()
        check(f"create_sketch {tag} holes", await adapter.create_sketch("TopFace"))
        for k, (sx, sz) in enumerate(xz):
            await define_circle(
                adapter, sx, -sz, dia / 2.0, f"{tag} hole ({sx:.2f}, {sz:.1f})",
                dims=rig,
                names=(f"{tag}{k}Cx", f"{tag}{k}Cz", f"{tag}{k}Dia"),
                drives=(None, None, None),
            )
        await ensure_fully_defined(adapter, f"{tag} holes sketch")
        check(f"exit_sketch {tag} holes", await adapter.exit_sketch())
        name_last_feature(adapter, f"{tag}HoleProfile")
        drive_jobs += rig.apply(adapter, f"{tag}HoleProfile")
        check(
            f"cut {tag} holes (blind)",
            await adapter.create_cut_extrude(ExtrusionParameters(depth=depth)),
        )
        name_last_feature(adapter, f"{tag}Holes")
        after_rig = await _volume(adapter)
        v_rig = len(xz) * math.pi * (dia / 2.0) ** 2 * depth
        if abs((after - after_rig) - v_rig) > 0.02 * v_rig:
            raise RuntimeError(
                f"{tag} holes removed {after - after_rig:.1f}, expected {v_rig:.1f}")
        after = after_rig

    # Apply the deferred drive equations now -- after the whole model + a rebuild
    # exists, so every target resolves -- then re-check neutrality against the
    # as-built volume (each equation evaluates to the value just built, so the
    # geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven base (equations neutral)", after, 0.005 * after
    )

    # DeckTop datum: a reference plane ON the top face (Y = total height), offset
    # from the Top Plane (its normal is +Y; the base sits entirely at Y>=0).
    # frame.SLDASM mates the support's FootSeat datum COINCIDENT to it to seat the
    # foot physically -- a named datum on the contact face makes the seat mate
    # robust (no coordinate pick, no face walk) and flip-free. Geometry-neutral.
    from solidworks_mcp.adapters.base import CreatePlaneParameters

    check(
        "create_plane DeckTop (Top Plane, +height)",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="offset",
                base_plane="Top Plane",
                offset=BOTTOM_THICKNESS + TOP_THICKNESS,
            )
        ),
    )
    name_last_feature(adapter, "DeckTop")

    # CboreSeat datum: a reference plane on the counterbore SHOULDER (Y = cbore
    # depth above the Top Plane / underside), the bearing face each lag-screw's
    # under-head plane seats against. frame.SLDASM mates the screw's under-head
    # plane (its Top Plane) COINCIDENT to this -- the hold-down's axial stop -- so
    # a named datum on the bearing face keeps the seat robust and flip-free.
    check(
        "create_plane CboreSeat (Top Plane, +cbore depth)",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="offset",
                base_plane="Top Plane",
                offset=CBORE_DEPTH,
            )
        ),
    )
    name_last_feature(adapter, "CboreSeat")

    # Per-hole reference axes for the lag-screw concentric mates. Built as the
    # INTERSECTION of a per-X and a per-Z reference plane (two_planes mode), NOT by
    # picking the hole's cylindrical face -- deterministic, no point-on-curved-face
    # selection (which is unreliable for a point on the analytic surface). The four
    # holes share two X values and two Z values, so four planes yield the four axes.
    # frame.SLDASM mates each lag-screw CONCENTRIC to its hole axis -- the physical
    # coaxiality of the hold-down -- so the screws are constrained, not grounded,
    # with no distance mate. HoleAxis{i} is at HOLE_XZ[i], the station frame.SLDASM's
    # LAG_SCREW_XZ[i] sits at. (Reference geometry only -- volume-neutral.)
    from solidworks_mcp.adapters.base import CreateAxisParameters

    x_plane: dict[float, str] = {}
    for k, hx in enumerate(sorted({hx for hx, _ in HOLE_XZ})):
        check(
            f"create_plane HoleX{k} (Right Plane, {hx:+.2f})",
            await adapter.create_plane(
                CreatePlaneParameters(mode="offset", base_plane="Right Plane", offset=hx)
            ),
        )
        name_last_feature(adapter, f"HoleX{k}")
        x_plane[hx] = f"HoleX{k}"
    z_plane: dict[float, str] = {}
    for k, hz in enumerate(sorted({hz for _, hz in HOLE_XZ})):
        check(
            f"create_plane HoleZ{k} (Front Plane, {hz:+.2f})",
            await adapter.create_plane(
                CreatePlaneParameters(mode="offset", base_plane="Front Plane", offset=hz)
            ),
        )
        name_last_feature(adapter, f"HoleZ{k}")
        z_plane[hz] = f"HoleZ{k}"
    for i, (hx, hz) in enumerate(HOLE_XZ):
        check(
            f"create_axis HoleAxis{i} ({hx:.2f}, {hz:+.2f})",
            await adapter.create_axis(
                CreateAxisParameters(
                    mode="two_planes", planes=[x_plane[hx], z_plane[hz]]
                )
            ),
        )
        name_last_feature(adapter, f"HoleAxis{i}")

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, CASTING_GREEN)

    # Verify the annotated footprint (ch. 6: 46 x 28 cm callouts = 18.1 x
    # 11.0 in; legacy 18.0 x 11.0 kept). Side-face pairs fail to pick (the
    # far faces are hidden in the active view and point picking is
    # screen-projected) — measure the bottom plate's perimeter edges.
    await measure_check(
        adapter,
        "base length (annotated 46 cm / 18 in)",
        [{"entity_type": "EDGE", "point": [0.0, 0.0, BOTTOM_WIDTH / 2.0]}],
        "length",
        BOTTOM_LENGTH,
    )
    await measure_check(
        adapter,
        "base depth (annotated 28 cm / 11 in)",
        [{"entity_type": "EDGE", "point": [BOTTOM_LENGTH / 2.0, 0.0, 0.0]}],
        "length",
        BOTTOM_WIDTH,
    )

    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
