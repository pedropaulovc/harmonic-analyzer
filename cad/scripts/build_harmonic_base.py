r"""Reproduction script: harmonic analyzer base (book ch. 6 / legacy part).

Two-plate welded construction based on the legacy 18.0 x 11.0 x 0.5 in
flange and 17.5 x 10.5 x 1.5 in pad. The v2 post/carrier fit preserves their
both plates remain on the legacy centred footprint; the v2 post/carrier fit is
handled by the mechanism installation contracts.

Finishing (chamfer external, fillet internal; legacy 1/8-1/16 sizes): C3.18
x 45 breaks on the eight vertical plan corners, C1.59 x 45 breaks on both
plates' exposed top rims and the underside rim, and the R0.50 pad-to-flange
root fillet note 1 caps -- the one internal wall junction on the part
(ch06/ch30 photos: every exposed plate edge reads softened, none sharp).

Dimensions: cad/DIMENSIONS.md "Chapter 6" — annotated (high) footprint,
legacy thicknesses (photo-verify note).

Layout: plates are centred in X and Z. Top-plane sketches map sketch x,y -> global X,-Z and
stack along +Y. Top plate boss starts at the bottom plate's upper face via
extrude_at_offset (raw-COM stopgap until MCP Phase 3).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_harmonic_base.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    CASTING_GREEN,
    SketchDims,
    add_line_chain,
    apply_color,
    apply_material,
    bbox_extent_check,
    check,
    define_rectilinear_chain,
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
    BOTTOM_FRONT_Z,
    BOTTOM_LENGTH,
    BOTTOM_REAR_Z,
    BOTTOM_THICKNESS,
    BOTTOM_WIDTH,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    SIDE_VIEW_NOTE,
    TOP_FRONT_Z,
    TOP_LENGTH,
    TOP_REAR_Z,
    TOP_THICKNESS,
    TOP_WIDTH,
)
from cone_pivot_post_installation import (
    MECHANISM_X_SHIFT,
    MECHANISM_Z_SHIFT,
    POST_X_SHIFT,
    POST_Z_SHIFT,
)
from build_cone_pivot_screw import (
    THREAD as PIVOT_THREAD,
    THREAD_TAIL_LEN as PIVOT_THREAD_ENGAGEMENT,
)
from build_cone_lock_knob import (
    COLLAR_DIA as LOCK_COLLAR_DIA,
    STUD_LEN as LOCK_STUD_LEN,
    THREAD as LOCK_THREAD,
)
from build_cone_swing_platform import PLATE_T, swing_hardware_geometry
from build_swing_stop_screw import (
    EMBED_LEN as STOP_EMBED_LEN,
    SHANK_DIA as STOP_SHANK_DIA,
    THREAD as STOP_THREAD,
)
from rocker_arm_support_spec import SUPPORT_HOLD_DOWN_XZ

import _telemetry

PART_NAME = "harmonic-base"
MATERIAL = "Gray Cast Iron"  # see _common.apply_material docstring

# Plate nominal geometry (BOTTOM_*/TOP_*) lives in harmonic_base_spec -- the
# COM-free contract the drawing shares. DIMENSIONS.md ch6: 46 cm / 28 cm callouts
# = 18.1 x 11.0 in (annotated); legacy 18.0 x 11.0 kept, top plate 0.25 in reveal
# per side, thicknesses from the legacy HarmonicBase.cs (photo-verify M2 note).
IN = 25.4

# Rocker-support hold-down holes (machine = part-local: frame.SLDASM places the
# base unrotated at the origin).  The support contract transforms its unchanged
# four-hole foot pattern through the +90-degree installation and the v2 rear
# shift.  Base, support, and frame therefore cannot carry three drifting copies.
HOLE_DIA = 13.0  # Ø12.7 stock lag-screw shank clearance
HOLE_XZ = SUPPORT_HOLD_DOWN_XZ
CBORE_DIA = 23.0  # Ø20.6502 stock lag head clearance
LAG_COUNTERBORE_DEPTH = 9.517  # 9.017 stock head height + 0.5 recess
CBORE_DEPTH = LAG_COUNTERBORE_DEPTH
CBORE_XZ = HOLE_XZ  # all four heads counterbored

# Edge finishing (chamfer external, fillet internal; legacy 1/8-1/16 sizes).
# The machined plate gets 45-degree edge breaks on every external edge: the
# vertical plan corners at 1/8 in legs, the exposed top rims and the
# underside rim at 1/16 in (single-pass mill/file breaks). The one internal
# wall junction -- the pad side walls meeting the flange top face -- carries
# the R0.50 root fillet note 1 already caps (a cutter-corner radius). All
# hole features sit >= 26 from every plate edge, so no break touches a rim
# or seat.
CORNER_CHAMFER = 0.125 * IN  # 3.175 legs, vertical plan corners
RIM_CHAMFER = 0.0625 * IN  # 1.5875 legs, top rims + underside rim
PAD_ROOT_R = 0.5  # pad-to-flange root fillet (note 1: R0.50 MAX)

# Cone swing hardware, blind from the TOP face. MACHINE-handed part coords.
# The platform recipe owns the shared lock/stop contact calculation; the base
# supplies its installed pivot station and exact purchased-hardware diameters.
_FORMER_PIVOT_SCREW_XZ = (-89.16663981674521, 60.60437088764276)
PIVOT_SCREW_XZ = (
    _FORMER_PIVOT_SCREW_XZ[0] + POST_X_SHIFT,
    _FORMER_PIVOT_SCREW_XZ[1] + POST_Z_SHIFT,
)
SWING_HARDWARE_GEOMETRY = swing_hardware_geometry(
    PIVOT_SCREW_XZ,
    lock_collar_dia=LOCK_COLLAR_DIA,
    stop_shank_dia=STOP_SHANK_DIA,
)
LOCK_KNOB_XZ = SWING_HARDWARE_GEOMETRY.lock_xz
STOP_SCREW_XZ = SWING_HARDWARE_GEOMETRY.stop_xz

# Blind #10-24 UNC-2B pivot tap: only the distinct threaded tail enters.
PIVOT_THREAD_BOTTOM_CLEARANCE = 2.0
PIVOT_HOLE_DEPTH = PIVOT_THREAD_ENGAGEMENT + PIVOT_THREAD_BOTTOM_CLEARANCE

# The lock stud passes through the 6.35-mm platform and uses the extra stock
# length in a real 1/4-20 base seat, with 0.25 mm below the installed tip.
LOCK_STUD_ENGAGEMENT = LOCK_STUD_LEN - PLATE_T
LOCK_STUD_BOTTOM_CLEARANCE = 0.25
LOCK_SCREW_HOLE_DEPTH = LOCK_STUD_ENGAGEMENT + LOCK_STUD_BOTTOM_CLEARANCE
LOCK_SCREW_DRILL_DEPTH = 4.0

# The stock stop wrapper retains exactly 6 mm embedded in its #8-32 seat.
STOP_SCREW_HOLE_DEPTH = STOP_EMBED_LEN
STOP_SCREW_DRILL_DEPTH = 9.0

# Alignment-pinion rig hold-downs, blind from the TOP face: four #8-32 seats
# under the two pivot blocks and three #4-40 seats under the spring foot and
# arbor-pedestal flanges.
_FORMER_BLOCK_SCREW_XZ = (
    (15.240530460002873, -98.0),  # front block, east screw
    (42.24053046000287, -98.0),  # front block, west screw
    (15.240530460002873, 82.0),  # back block, east screw
    (42.24053046000287, 82.0),  # back block, west screw
)
BLOCK_SCREW_XZ = tuple(
    (x + MECHANISM_X_SHIFT, z + MECHANISM_Z_SHIFT) for x, z in _FORMER_BLOCK_SCREW_XZ
)
# Stock 25.4-mm slotted screws penetrate 6.65 mm below each 18.75-mm block.
BLOCK_SCREW_HOLE_DEPTH = 6.9  # stock engagement + 0.25 bottom clearance
BLOCK_SCREW_DRILL_DEPTH = 10.0
_FORMER_FOOT_SCREW_XZ = (
    (43.13610240207359, 70.95),  # spring foot: 1-in reach keeps its screw head
    # clear of the unchanged rocker-arm-support casting after the rig recenter
    (-54.7, -95.5),  # south arbor-pedestal flange (build_arbor_pedestal SCREW_Z)
    (-54.7, 102.5),  # NORTH arbor-pedestal flange (PR8, ch12 img09: the
    # mirrored base-standing clamp at z 97.5; ry180 flips its flange to +z)
)
FOOT_SCREW_XZ = tuple(
    (x + MECHANISM_X_SHIFT, z + MECHANISM_Z_SHIFT) for x, z in _FORMER_FOOT_SCREW_XZ
)
# The stock 9.525-mm foot screw penetrates 8.725 mm below the 0.8-mm spring.
FOOT_SCREW_HOLE_DEPTH = 8.975  # stock engagement + 0.25 bottom clearance
FOOT_SCREW_DRILL_DEPTH = 11.0

# Native tapped seats. Physical thread compatibility is carried by each named
# HoleSpec designation; tap-drill diameters remain manufacturing geometry and
# are not compared to purchased fasteners' major-diameter solids.
PIVOT_SEAT_SPEC = HoleSpec(
    "tapped",
    PIVOT_THREAD,
    end="blind",
    depth_mm=PIVOT_HOLE_DEPTH,
    thread_class="2B",
)
LOCK_SEAT_SPEC = HoleSpec(
    "tapped",
    LOCK_THREAD,
    end="blind",
    depth_mm=LOCK_SCREW_DRILL_DEPTH,
    thread_class="2B",
    overrides_mm={"ThreadDepth": LOCK_SCREW_HOLE_DEPTH},
)
STOP_SEAT_SPEC = HoleSpec(
    "tapped",
    STOP_THREAD,
    end="blind",
    depth_mm=STOP_SCREW_DRILL_DEPTH,
    thread_class="2B",
    overrides_mm={"ThreadDepth": STOP_SCREW_HOLE_DEPTH},
)
BLOCK_SEAT_SPEC = HoleSpec(
    "tapped",
    "#8-32",
    end="blind",
    depth_mm=BLOCK_SCREW_DRILL_DEPTH,
    thread_class="2B",
    overrides_mm={"ThreadDepth": BLOCK_SCREW_HOLE_DEPTH},
)
FOOT_SEAT_SPEC = HoleSpec(
    "tapped",
    "#4-40",
    end="blind",
    depth_mm=FOOT_SCREW_DRILL_DEPTH,
    thread_class="2B",
    overrides_mm={"ThreadDepth": FOOT_SCREW_HOLE_DEPTH},
)
PIVOT_SCREW_HOLE_DIA = blind_cut_dia_mm(PIVOT_SEAT_SPEC)
LOCK_SCREW_HOLE_DIA = blind_cut_dia_mm(LOCK_SEAT_SPEC)
STOP_SCREW_HOLE_DIA = blind_cut_dia_mm(STOP_SEAT_SPEC)
BLOCK_SCREW_HOLE_DIA = blind_cut_dia_mm(BLOCK_SEAT_SPEC)
FOOT_SCREW_HOLE_DIA = blind_cut_dia_mm(FOOT_SEAT_SPEC)

MM3_PER_IN3 = IN**3


def _pos_drive(global_name: str, sketch_value: float) -> str:
    """Positive equation for an unsigned centre-distance dimension."""
    return f'-"{global_name}"' if sketch_value < 0.0 else f'"{global_name}"'


async def _volume(adapter) -> float:
    res = await adapter.get_mass_properties()
    return res.data.volume if res.is_success and res.data else float("nan")


def _fillet_section_area(r: float) -> float:
    """Cross-section a radius-r fillet adds to a square reentrant edge."""
    return (1.0 - math.pi / 4.0) * r * r


def _plan_perimeter(length: float, width: float) -> float:
    """Plate outline length after the 45-degree plan-corner chamfers.

    Each corner trades two CORNER_CHAMFER legs for one sqrt(2) flat. A rim
    section swept along this polyline removes area x perimeter; the eight
    blunt 135-degree vertices contribute only O(section^3) corner patches,
    absorbed by the check tolerances.
    """
    return (
        2.0 * (length + width)
        - 8.0 * CORNER_CHAMFER
        + 4.0 * CORNER_CHAMFER * math.sqrt(2.0)
    )


async def _define_fixed_edge_rectangle(
    adapter,
    *,
    half_x: float,
    front_z: float,
    rear_z: float,
    label: str,
    dims: SketchDims,
    width_name: str,
    depth_name: str,
    width_drive: str,
    depth_drive: str,
    half_x_drive: str,
    rear_z_drive: str,
) -> None:
    """Fully define an X-centred rectangle with fixed front/rear Z edges.

    A Top-plane sketch's second coordinate is machine ``-Z``.  Anchoring the
    rear-west corner and driving the full depth keeps the plate footprint
    explicitly tied to the shared width contract.
    """
    points = [
        (-half_x, -rear_z),
        (half_x, -rear_z),
        (half_x, -front_z),
        (-half_x, -front_z),
    ]
    lines = await add_line_chain(adapter, points)
    await define_rectilinear_chain(
        adapter,
        lines,
        points,
        label=label,
        dims=dims,
        names=[width_name, depth_name, f"{width_name}West", f"{depth_name}Rear"],
        drives=[width_drive, depth_drive, half_x_drive, rear_z_drive],
    )


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

    # Bottom plate: centred on the origin.
    bottom = SketchDims()
    check("create_sketch bottom", await adapter.create_sketch("Top"))
    await _define_fixed_edge_rectangle(
        adapter,
        half_x=BOTTOM_LENGTH / 2.0,
        front_z=-BOTTOM_WIDTH / 2.0,
        rear_z=BOTTOM_WIDTH / 2.0,
        label="bottom plate",
        dims=bottom,
        width_name="BottomLen",
        depth_name="BottomWid",
        width_drive='"BottomLength"',
        depth_drive='"BottomWidth"',
        half_x_drive='"BottomLength" / 2',
        rear_z_drive='"BottomWidth" / 2',
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
    # Top plate shares the centred legacy footprint and starts on the flange.
    top = SketchDims()
    check("create_sketch top", await adapter.create_sketch("Top"))
    await _define_fixed_edge_rectangle(
        adapter,
        half_x=TOP_LENGTH / 2.0,
        front_z=-TOP_WIDTH / 2.0,
        rear_z=TOP_WIDTH / 2.0,
        label="top plate",
        dims=top,
        width_name="TopLen",
        depth_name="TopWid",
        width_drive='"TopLength"',
        depth_drive='"TopWidth"',
        half_x_drive='"TopLength" / 2',
        rear_z_drive='"TopWidth" / 2',
    )
    await ensure_fully_defined(adapter, "top plate sketch")
    check("exit_sketch top", await adapter.exit_sketch())
    name_last_feature(adapter, "TopProfile")
    drive_jobs += top.apply(adapter, "TopProfile")
    extrude_at_offset(adapter, TOP_THICKNESS, BOTTOM_THICKNESS)
    name_last_feature(adapter, "TopPlate")
    _telemetry.info(f"volume after top plate: {await _volume(adapter):.1f} mm^3")

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
        HoleSpec(
            "counterbore_fillister",
            "9/16",
            overrides_mm={
                "HoleDiameter": HOLE_DIA,
                "CounterBoreDiameter": CBORE_DIA,
                "CounterBoreDepth": CBORE_DEPTH,
            },
        ),
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
        f"volume after fastener holes: {after:.1f} mm^3 (removed analytic {v_holes:.1f})"
    )
    if abs((pre_holes - after) - v_holes) > 0.02 * v_holes:
        raise RuntimeError(
            f"fastener holes removed {pre_holes - after:.1f}, expected {v_holes:.1f}"
        )

    # Cone swing hardware + alignment-pinion rig seats: native Hole Wizard
    # blind holes from the top face. The pivot, lock, stop, block, and foot
    # screws all thread into their named tapped seats; the platform swings on
    # the pivot screw's shoulder. A blind wizard hole ends in a 118-degree
    # drill point, so the analytic expectation includes cylinder plus point.
    for tag, spec, xz, label in (
        (
            "PivotSeat",
            PIVOT_SEAT_SPEC,
            (PIVOT_SCREW_XZ,),
            f"cone-pivot screw tapped seat ({PIVOT_THREAD} UNC-2B)",
        ),
        (
            "LockSeat",
            LOCK_SEAT_SPEC,
            (LOCK_KNOB_XZ,),
            f"cone-lock knob tapped seat ({LOCK_THREAD} UNC-2B)",
        ),
        (
            "StopSeat",
            STOP_SEAT_SPEC,
            (STOP_SCREW_XZ,),
            "swing-stop tapped seat (#8-32)",
        ),
        (
            "BlockScrewHoles",
            BLOCK_SEAT_SPEC,
            BLOCK_SCREW_XZ,
            "pinion-pivot-block tapped seats (#8-32)",
        ),
        (
            "FootScrewHoles",
            FOOT_SEAT_SPEC,
            FOOT_SCREW_XZ,
            "foot-screw tapped seats (#4-40)",
        ),
    ):
        dia = blind_cut_dia_mm(spec)
        wizard_holes(
            adapter,
            spec,
            [[sx, total, sz] for sx, sz in xz],
            (0.0, 1.0, 0.0),
            label,
            name=tag,
        )
        after_cut = await _volume(adapter)
        v_cut = len(xz) * blind_hole_volume_mm3(dia, spec.depth_mm)
        if abs((after - after_cut) - v_cut) > 0.02 * v_cut:
            raise RuntimeError(
                f"{tag} removed {after - after_cut:.1f}, expected {v_cut:.1f}"
            )
        after = after_cut

    # Edge finishing (chamfer external, fillet internal). Plan corners
    # FIRST: the rim breaks then run along the chamfered outline whose
    # length _plan_perimeter gives exactly. Corner flats are separate
    # non-tangent edges, so every rim loop selects its four side edges AND
    # its four corner-flat edges explicitly.
    check(
        "chamfer plan corners",
        await adapter.add_chamfer(
            CORNER_CHAMFER,
            [
                [
                    sx * BOTTOM_LENGTH / 2.0,
                    BOTTOM_THICKNESS / 2.0,
                    sz * BOTTOM_WIDTH / 2.0,
                ]
                for sx in (-1.0, 1.0)
                for sz in (-1.0, 1.0)
            ]
            + [
                [
                    sx * TOP_LENGTH / 2.0,
                    total - TOP_THICKNESS / 2.0,
                    sz * TOP_WIDTH / 2.0,
                ]
                for sx in (-1.0, 1.0)
                for sz in (-1.0, 1.0)
            ],
        ),
    )
    name_last_feature(adapter, "CornerBreaks")
    v_corners = 4.0 * (CORNER_CHAMFER**2 / 2.0) * total
    after = await volume_check(
        adapter, "plan corner breaks", after - v_corners, 0.01 * v_corners + 2.0
    )

    def _rim_points(half_x: float, y_rim: float, half_z: float) -> list[list[float]]:
        """One rim loop: four side-edge midpoints + four corner-flat midpoints."""
        flat_x = half_x - CORNER_CHAMFER / 2.0
        flat_z = half_z - CORNER_CHAMFER / 2.0
        return [
            [0.0, y_rim, -half_z],
            [0.0, y_rim, half_z],
            [half_x, y_rim, 0.0],
            [-half_x, y_rim, 0.0],
        ] + [
            [sx * flat_x, y_rim, sz * flat_z]
            for sx in (-1.0, 1.0)
            for sz in (-1.0, 1.0)
        ]

    # Top rims: 1/16 in x 45-degree breaks on both plates' exposed top
    # perimeter edges (the flange's reveal rim and the pad's top rim).
    check(
        "chamfer top rims",
        await adapter.add_chamfer(
            RIM_CHAMFER,
            _rim_points(BOTTOM_LENGTH / 2.0, BOTTOM_THICKNESS, BOTTOM_WIDTH / 2.0)
            + _rim_points(TOP_LENGTH / 2.0, total, TOP_WIDTH / 2.0),
        ),
    )
    name_last_feature(adapter, "TopRimBreaks")
    rim_area = RIM_CHAMFER**2 / 2.0
    v_rims = rim_area * (
        _plan_perimeter(BOTTOM_LENGTH, BOTTOM_WIDTH)
        + _plan_perimeter(TOP_LENGTH, TOP_WIDTH)
    )
    after = await volume_check(
        adapter, "top rim breaks", after - v_rims, 0.02 * v_rims + 5.0
    )

    # Underside rim: the same 1/16 in break around the bottom face perimeter.
    check(
        "chamfer underside rim",
        await adapter.add_chamfer(
            RIM_CHAMFER,
            _rim_points(BOTTOM_LENGTH / 2.0, 0.0, BOTTOM_WIDTH / 2.0),
        ),
    )
    name_last_feature(adapter, "BottomEdgeBreak")
    v_break = rim_area * _plan_perimeter(BOTTOM_LENGTH, BOTTOM_WIDTH)
    after = await volume_check(
        adapter, "underside edge break", after - v_break, 0.02 * v_break + 5.0
    )

    # Pad root: the one INTERNAL wall junction -- the pad sides meeting the
    # flange top face -- filleted at the R0.50 note 1 caps (the cutter-corner
    # radius that machining the reveal leaves anyway). Reentrant: ADDS
    # material along the pad's chamfered base outline.
    check(
        "fillet pad root",
        await adapter.add_fillet(
            PAD_ROOT_R,
            _rim_points(TOP_LENGTH / 2.0, BOTTOM_THICKNESS, TOP_WIDTH / 2.0),
        ),
    )
    name_last_feature(adapter, "PadRootFillet")
    v_root = _fillet_section_area(PAD_ROOT_R) * _plan_perimeter(TOP_LENGTH, TOP_WIDTH)
    after = await volume_check(
        adapter, "pad root fillet", after + v_root, 0.05 * v_root + 3.0
    )

    # Apply the deferred drive equations after the whole model exists, then
    # re-check neutrality against the as-built volume. Frame components are
    # inserted at verified transforms and lock-mated, so the old DeckTop,
    # CboreSeat, and eight per-hole construction planes/axes are unnecessary.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven base (equations neutral)", after, 0.005 * after)

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, CASTING_GREEN)

    # Verify the annotated footprint without view-dependent screen picks.
    await bbox_extent_check(
        adapter, "base length (annotated 46 cm / 18 in)", "x", BOTTOM_LENGTH
    )
    await bbox_extent_check(adapter, "base depth (28 cm plate)", "z", BOTTOM_WIDTH)

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
