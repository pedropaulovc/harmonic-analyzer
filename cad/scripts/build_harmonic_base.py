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
    bbox_extent_check,
    check,
    define_centered_rectangle,
    drive_dimension,
    ensure_fully_defined,
    extrude_at_offset,
    force_rebuild,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    volume_check,
)
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _holes import HoleSpec, blind_cut_dia_mm, blind_hole_volume_mm3, wizard_holes
from harmonic_base_spec import (
    BOTTOM_LENGTH,
    BOTTOM_THICKNESS,
    BOTTOM_WIDTH,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    SIDE_VIEW_NOTE,
    TOP_LENGTH,
    TOP_THICKNESS,
    TOP_WIDTH,
)

import _telemetry

PART_NAME = "harmonic-base"
MATERIAL = "Gray Cast Iron"  # see _common.apply_material docstring

# Plate nominal geometry (BOTTOM_*/TOP_*) lives in harmonic_base_spec -- the
# COM-free contract the drawing shares. DIMENSIONS.md ch6: 46 cm / 28 cm callouts
# = 18.1 x 11.0 in (annotated); legacy 18.0 x 11.0 kept, top plate 0.25 in reveal
# per side, thicknesses from the legacy HarmonicBase.cs (photo-verify M2 note).
IN = 25.4

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

# Cone swing hardware, blind from the TOP face. MACHINE-handed part coords,
# and since #151 the drive-train derivation is machine-handed too, so the
# assembly asserts agreement DIRECTLY: pivot = cone_station(PIVOT_STATION).x
# (build_cone_pivot_screw), stop = disengaged east plate edge - shank radius
# (build_swing_stop_screw). (Pre-#151 the drive-train derived in the mirrored
# frame and these holes matched its NEGATED x -- the sign was interference-
# gate proven: holes at the wrong x left both screws in solid base, 190.0 +
# 75.4 mm^3, exactly the two embedded shank volumes.)
PIVOT_SCREW_XZ = (-79.69, 103.29)
# pivot seat: blind 1/4-20 UNC-2B tap.  The screw's ground shoulder stops on
# the base top; only its distinct threaded tail enters this seat.
STOP_SCREW_XZ = (-130.433, 9.735)  # past the DISENGAGED east taper edge. The
# centre sits one stop-screw shank RADIUS outside the swung edge, so the
# US-customary shank resize (O4.0 -> 3.15, #8-32 tap-drill - 0.3) moved it
# 0.425 mm along the disengaged east-edge outward normal N_M
# (-0.933521, 0.358523): old (-130.830, 9.887) + N_M * (3.15 - 4.0)/2.
# PR8 west-tip trim moved this only via the DISENGAGE angle (the notch mouth
# is on the WEST edge, so the exit travel shortened); the contact edge itself
# is the EAST taper line, unchanged at HALF_WIDTH_N 12. (An earlier PR8 pass
# wrongly fed the west width into the east-edge derivation -- Codex catch.)
# Disengage swing sweeps the plate EAST (machine -x); the first
# derivation sat 19 inside the engaged plate -- interference-gate proven.
# stop seat: #20 drill (O4.089, wizard) -- stop-screw O3.15 shank clearance
PIVOT_THREAD = "1/4-20"
PIVOT_THREAD_ENGAGEMENT = 8.0
PIVOT_THREAD_BOTTOM_CLEARANCE = 2.0
PIVOT_HOLE_DEPTH = PIVOT_THREAD_ENGAGEMENT + PIVOT_THREAD_BOTTOM_CLEARANCE
STOP_SCREW_HOLE_DEPTH = 6.0
STOP_SCREW_DRILL_DEPTH = 9.0

# Alignment-pinion rig hold-downs (PR7 items 2/11/12), blind from the TOP face
# like the swing hardware and in the SAME machine-handed convention: four
# Ø4.2 holes under the two pivot blocks' bright slotted screws
# (build_pinion_pivot_block SCREW_* stations: block x 6.336 -+ 13.5, hole
# z = block z0 + depth/2 -- asserted directly at drive-train import) and two
# Ø3.2 holes under the black foot screws (build_foot_screw): the spring foot
# and the arbor-pedestal flange.
BLOCK_SCREW_XZ = (
    (-7.164, -98.0),   # front block, east screw
    (19.836, -98.0),   # front block, west screw
    (-7.164, 82.0),    # back block, east screw
    (19.836, 82.0),    # back block, west screw
)
# block seats: #8-32 tap drill -- the slotted screws thread into the base
BLOCK_SCREW_HOLE_DEPTH = 3.5  # 18 shank - 16 block = 2 buried + 1.5 air
BLOCK_SCREW_DRILL_DEPTH = 7.0
FOOT_SCREW_XZ = (
    (20.467, 70.95),  # spring foot (build_pinion_spring hole: the west foot
    # crosses under the lift rod so its screw lands west of the moving rig)
    (-54.7, -95.5),   # south arbor-pedestal flange (build_arbor_pedestal SCREW_Z)
    (-54.7, 102.5),   # NORTH arbor-pedestal flange (PR8, ch12 img09: the
    # mirrored base-standing clamp at z 97.5; ry180 flips its flange to +z)
)
# foot seats: #4-40 tap drill -- the foot screws thread into the base
FOOT_SCREW_HOLE_DEPTH = 7.7  # 8.0 shank under the 0.8 spring strip + air
FOOT_SCREW_DRILL_DEPTH = 11.0

# The four seat specs, hoisted to module level so the drive-train assembly can
# import the TRUE wizard cut diameters for its clearance assertions (the old
# hand-authored *_HOLE_DIA constants are derived from the specs now -- one
# chokepoint, no drift).
PIVOT_SEAT_SPEC = HoleSpec(
    "tapped", PIVOT_THREAD, end="blind", depth_mm=PIVOT_HOLE_DEPTH,
    thread_class="2B",
)
STOP_SEAT_SPEC = HoleSpec(
    "tapped", "#8-32", end="blind", depth_mm=STOP_SCREW_DRILL_DEPTH,
    overrides_mm={"ThreadDepth": STOP_SCREW_HOLE_DEPTH})
BLOCK_SEAT_SPEC = HoleSpec(
    "tapped", "#8-32", end="blind", depth_mm=BLOCK_SCREW_DRILL_DEPTH,
    overrides_mm={"ThreadDepth": BLOCK_SCREW_HOLE_DEPTH})
FOOT_SEAT_SPEC = HoleSpec(
    "tapped", "#4-40", end="blind", depth_mm=FOOT_SCREW_DRILL_DEPTH,
    overrides_mm={"ThreadDepth": FOOT_SCREW_HOLE_DEPTH})
PIVOT_SCREW_HOLE_DIA = blind_cut_dia_mm(PIVOT_SEAT_SPEC)  # 5.105 tap drill
STOP_SCREW_HOLE_DIA = blind_cut_dia_mm(STOP_SEAT_SPEC)  # #8-32 tap drill
BLOCK_SCREW_HOLE_DIA = blind_cut_dia_mm(BLOCK_SEAT_SPEC)  # #8-32 tap drill
FOOT_SCREW_HOLE_DIA = blind_cut_dia_mm(FOOT_SEAT_SPEC)  # #4-40 tap drill

MM3_PER_IN3 = IN**3


def _pos_drive(global_name: str, sketch_value: float) -> str:
    """Positive equation for an unsigned centre-distance dimension."""
    return f'-"{global_name}"' if sketch_value < 0.0 else f'"{global_name}"'


async def _volume(adapter) -> float:
    res = await adapter.get_mass_properties()
    return res.data.volume if res.is_success and res.data else float("nan")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): the two plate footprints + thicknesses.
    # The mm suffix is load-bearing -- this is an INCH document and the equation
    # manager reads BARE numbers in document units (an unsuffixed 457.2 = 457
    # inches and blows the part up 25.4x). The thicknesses are extrude/offset
    # feature parameters (not sketch dims), exposed here as editable constants
    # even though nothing in drive_jobs drives them.
    await set_global(adapter, "BottomLength", f"{BOTTOM_LENGTH}mm")
    await set_global(adapter, "BottomWidth", f"{BOTTOM_WIDTH}mm")
    await set_global(adapter, "BottomThickness", f"{BOTTOM_THICKNESS}mm")
    await set_global(adapter, "TopLength", f"{TOP_LENGTH}mm")
    await set_global(adapter, "TopWidth", f"{TOP_WIDTH}mm")
    await set_global(adapter, "TopThickness", f"{TOP_THICKNESS}mm")
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
    )
    await ensure_fully_defined(adapter, "top plate sketch")
    check("exit_sketch top", await adapter.exit_sketch())
    name_last_feature(adapter, "TopProfile")
    drive_jobs += top.apply(adapter, "TopProfile")
    extrude_at_offset(adapter, TOP_THICKNESS, BOTTOM_THICKNESS)
    name_last_feature(adapter, "TopPlate")
    _telemetry.info(f"volume after top plate: {await _volume(adapter):.1f} mm^3")
    # expected: 99 + 17.5 * 10.5 * 1.5 = 374.625 in^3 = 6,139,003 mm^3

    # M6.10 fastener holes + lag-head recesses: ONE native Hole Wizard
    # counterbored 9/16 FILLISTER feature (4 placement points) drilled from
    # the UNDERSIDE face, so the model carries the real fastener designation
    # (memory/fastener-policy-us-customary; fillister = the round slotted head
    # -- the hex-bolt table SKIPS 9/16, and the lag screw's round Ø22 head IS
    # a fillister shape). The through Ø13 / recess Ø23x6.5 are the
    # PHOTO-MEASURED artefact dims -- the standard table would cut Ø14.7/Ø21.4
    # and visibly move the underside -- preserved as explicit definition
    # overrides. CBORE_XZ == HOLE_XZ (all four heads recessed), so the pair of
    # concentric cuts collapses into the one counterbore feature.
    total = BOTTOM_THICKNESS + TOP_THICKNESS
    pre_holes = await _volume(adapter)
    fastener_cut = wizard_holes(
        adapter,
        HoleSpec("counterbore_fillister", "9/16", overrides_mm={
            "HoleDiameter": HOLE_DIA,
            "CounterBoreDiameter": CBORE_DIA,
            "CounterBoreDepth": CBORE_DEPTH,
        }),
        [[x, 0.0, z] for x, z in HOLE_XZ],
        (0.0, -1.0, 0.0),
        "lag-screw counterbored holes (9/16)",
        name="FastenerHoles",
        placement_dims=[
            (
                (f"Hole{i}Cx", _pos_drive(f"Hole{i}X", x)),
                (f"Hole{i}Cz", _pos_drive(f"Hole{i}Z", -z)),
            )
            for i, (x, z) in enumerate(HOLE_XZ)
        ],
    )
    drive_jobs += fastener_cut.placement_drive_jobs
    after = await _volume(adapter)
    v_holes = len(HOLE_XZ) * (
        math.pi * (HOLE_DIA / 2.0) ** 2 * total
        + math.pi * ((CBORE_DIA / 2.0) ** 2 - (HOLE_DIA / 2.0) ** 2) * CBORE_DEPTH
    )
    _telemetry.info(
        f"volume after fastener holes: {after:.1f} mm^3 (removed analytic {v_holes:.1f})")
    if abs((pre_holes - after) - v_holes) > 0.02 * v_holes:
        raise RuntimeError(
            f"fastener holes removed {pre_holes - after:.1f}, expected {v_holes:.1f}"
        )

    # Cone swing hardware + alignment-pinion rig seats: native Hole Wizard
    # blind holes from the top face. The pivot, stop, block and foot screws all
    # thread into their matching tapped base seats; the platform itself swings
    # on the pivot screw's shoulder. A wizard blind hole ends in a 118-degree drill point, so the
    # analytic expectation is blind_hole_volume_mm3 (cylinder + point).
    for tag, spec, xz, label in (
        ("PivotSeat", PIVOT_SEAT_SPEC,
         (PIVOT_SCREW_XZ,),
         "cone-pivot screw tapped seat (1/4-20 UNC-2B)"),
        ("StopSeat", STOP_SEAT_SPEC,
         (STOP_SCREW_XZ,),
         "swing-stop tapped seat (#8-32)"),
        ("BlockScrewHoles", BLOCK_SEAT_SPEC,
         BLOCK_SCREW_XZ,
         "pinion-pivot-block tapped seats (#8-32)"),
        ("FootScrewHoles", FOOT_SEAT_SPEC,
         FOOT_SCREW_XZ,
         "foot-screw tapped seats (#4-40)"),
    ):
        dia = blind_cut_dia_mm(spec)
        wizard_holes(
            adapter, spec,
            [[sx, total, sz] for sx, sz in xz],
            (0.0, 1.0, 0.0), label, name=tag,
        )
        after_cut = await _volume(adapter)
        v_cut = len(xz) * blind_hole_volume_mm3(dia, spec.depth_mm)
        if abs((after - after_cut) - v_cut) > 0.02 * v_cut:
            raise RuntimeError(
                f"{tag} removed {after - after_cut:.1f}, expected {v_cut:.1f}")
        after = after_cut

    # Apply the deferred drive equations after the whole model exists, then
    # re-check neutrality against the as-built volume. Frame components are
    # inserted at verified transforms and lock-mated, so the old DeckTop,
    # CboreSeat, and eight per-hole construction planes/axes are unnecessary.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven base (equations neutral)", after, 0.005 * after
    )

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, CASTING_GREEN)

    # Verify the annotated footprint without view-dependent screen picks.
    await bbox_extent_check(
        adapter, "base length (annotated 46 cm / 18 in)", "x", BOTTOM_LENGTH
    )
    await bbox_extent_check(
        adapter, "base depth (annotated 28 cm / 11 in)", "z", BOTTOM_WIDTH
    )

    await report_mass_properties(adapter)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": DRAWING_NOTES,
            "Side View Note": SIDE_VIEW_NOTE,
        },
    )
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
