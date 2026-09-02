r"""Reproduction script: pen subassembly (book ch. 24).

The machine's output transducer: the pen carriage that writes the Fourier sum
onto the recording paper, in machine coordinates (assembly origin = base
origin; the output side is -Z). The square pen rod slides vertically through
the hanger's guide block; the magnifying wheel's wire (pen-wire, WIRE 2 --
modeled as its straight rest-pose run only) raises and lowers it to trace
the curve. Everything below the guide rides the rod (ch24 pp.60-65 and the
4/4 video frames v4_t00579..t00645):

* pen-hanger (ground) on the wheel-bar -- the fixed guide.
* pen-rod -- a Y-prismatic; its travel is the sub's single FREED operational
  DOF: its drive spec is recorded into the DOF manifest, never authored, so
  the saved model slides freely and carries NO pen-driver equation.
  verify:kinematics replays the recorded spec and installs the F5
  chained-Fourier driver transiently (reproduces truth_model.pen_y from a
  CrankDeg global, no force solver).
* pen-v-block -- the brass block HANGING on the rod's bottom end (the rod
  drops 14 into the bore nearest the paper; a side set screw pins it in the
  real device). Its length runs at 45 degrees to the paper (the "45 deg" nib
  callout of v4_t00603), lock-mated to the rod.
* pen-marker -- the full-length marker lying in the block's bottom groove
  along the block's length, nib on the paper, body sticking out forward and
  east of the machine; lock-mated to the rod.
* pen-frame -- the brass stirrup wrapping the block's end section (its plane
  perpendicular to the block length, beside the rod), lock-mated to the rod;
  pen-set-screw threads UP through its bottom rail and presses the marker
  into the groove.
* pen-wire -- WIRE 2's straight rest-pose run from the wheel-rim tangent down
  to the rod's wire hole, locked to the rod so it rides the pen travel. The
  rim wrap and tie-off are not modeled; the kinematic coupling stays a
  Motion-study mate (cad/docs/motion-policy.md).
* hanger-screw -- fastens the pen-hanger from behind the wheel bar.

Cross-subassembly fits (checked at the top level): the pen-hanger clamps the
wheel-bar (magnifier.SLDASM) and the wheel rim -> pen-rod wire couples the
pen to the magnifier; the v-block's paper-side corner and the nib stand off
the recording paper's front face (paper-drive.SLDASM).

History: until the 2026-09 photo re-derivation the v-block was a GROUNDED
green cradle with vertical bores and the marker hung plumb 8.6 in front of
the paper (documented simplification). Every ch24/ch30 plate and the video
show the block riding the rod with the marker horizontal in its groove, so
the carriage is now authored as the photos have it. The rod line moved 5.5
forward of the wheel-bar plane (PEN_Z_MID -151.5 -> -157.0) so the 45-degree
block's rear corner clears the paper; the hanger guide deepened to match.

Fix-all strategy (M6.2): the hanger inserted at its exact final transform and
fixed; the rod left free and constrained by mates (its Y-travel recorded into
the DOF manifest, never authored); the carriage parts placed on-solution and
lock-mated to the rod; transforms asserted by read-back; zero interference.

Dimensions: cad/config/dimensions.yaml ch. 24.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pen_assembly.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    apply_custom_properties,
    apply_summary_info,
    check,
    run_build,
)
from _drawing_marks import DRAWN_BY
from _assembly import (
    angle_driver,
    assembly_title_properties,
    assert_component_placed,
    assert_free_dof_necessity,
    check_no_interference,
    coincident_mate,
    component_origin,
    distance_driver,
    lock_mate,
    named_ref,
    parallel_mate,
    place_component,
    reset_dof_manifest,
    save_assembly_and_images,
    write_dof_manifest,
)
from _transforms import IDENTITY, euler_from_rows, rot_z_rows

ASM_NAME = "pen"

# --- machine anchors ---------------------------------------------------------
WHEEL_BAR_Y = 575.7  # the wheel-bar the pen-hanger clamps (magnifier.SLDASM)
PAPER_FRONT_Z = -143.4  # recording paper front face (build_paper_drive_assembly:
# platen front -142.9, the sheet planted 0.5 proud)
CLEARANCE = 0.25  # interference-gate margin convention

# --- pen rod line -------------------------------------------------------------
PEN_ROD_X = 3.0
PEN_Z_MID = -157.0  # pen-rod axis plane (was -151.5: see the module docstring)
ROD_SECTION = 5.0  # pen_rod_spec.ROD_SECTION (asserted below)
HANGER_POS = (PEN_ROD_X, 505.0, PEN_Z_MID)
# The rod's bottom end sits 14 into the v-block's 18-tall rod bore, putting
# the marker axis (block bottom + 0.25) at paper mid-height: paper y 324.5..405
# (build_paper_drive_assembly), centre 364.75 -> marker axis 364.25.
ROD_BORE_ENGAGEMENT = 14.0
BLOCK_BOTTOM_Y = 364.0
PEN_ROD_POS = (PEN_ROD_X, BLOCK_BOTTOM_Y + 4.0, PEN_Z_MID - ROD_SECTION / 2.0)

# --- v-block on the rod --------------------------------------------------------
# Block-local frame (build_pen_v_block): length X 0..36, height Y 0..18, depth
# Z 0..16; rod bore at local (BORE_X[0], z 8); marker groove along X at the
# bottom, centred in Z. The block's local +X (its length) points FORWARD and
# EAST at 45 degrees -- machine (+sin, 0, -cos) of BLOCK_YAW about +Y -- so the
# rod bore (the paper end, local x 10) is the rear bore and the marker exits
# the local x 0 end face onto the paper.
from pen_v_block_spec import (  # noqa: E402
    BLOCK_DEPTH,
    BLOCK_HEIGHT,
    BLOCK_LENGTH,
    BORE_X,
    GROOVE_DEPTH,
    GROOVE_WIDTH,
)
from pen_marker_spec import BARREL_DIA, BARREL_TOP_Y  # noqa: E402
from build_pen_frame import (  # noqa: E402
    FRAME_DEPTH,
    OUTER_HEIGHT,
    OUTER_WIDTH,
    RAIL_END,
    RAIL_SIDE,
)
from pen_set_screw_spec import KNOB_LENGTH, SHANK_LEN  # noqa: E402

BLOCK_YAW_DEG = 45.0  # v4_t00603: the nib meets the paper at 45 degrees
_C = math.cos(math.radians(BLOCK_YAW_DEG))
_S = math.sin(math.radians(BLOCK_YAW_DEG))
# Images of the block's local axes (rows convention of place_component):
BLOCK_ROWS = [[_S, 0.0, -_C], [0.0, 1.0, 0.0], [_C, 0.0, _S]]
BLOCK_ROT = euler_from_rows(BLOCK_ROWS)  # [0, 45, 0]
ROD_BORE_LOCAL = (BORE_X[0], BLOCK_DEPTH / 2.0)  # (x, z) of the rod bore axis


def _block_to_machine(local: tuple[float, float, float]) -> list[float]:
    """Machine point of a v-block-local point (block origin VBLOCK_POS)."""
    x, y, z = local
    return [
        VBLOCK_POS[0] + x * BLOCK_ROWS[0][0] + z * BLOCK_ROWS[2][0],
        VBLOCK_POS[1] + y,
        VBLOCK_POS[2] + x * BLOCK_ROWS[0][2] + z * BLOCK_ROWS[2][2],
    ]


# Block origin: the rod bore axis lands on the rod line.
VBLOCK_POS = (
    PEN_ROD_X - ROD_BORE_LOCAL[0] * _S - ROD_BORE_LOCAL[1] * _C,
    BLOCK_BOTTOM_Y,
    PEN_Z_MID + ROD_BORE_LOCAL[0] * _C - ROD_BORE_LOCAL[1] * _S,
)
assert math.isclose(PEN_ROD_POS[1], VBLOCK_POS[1] + BLOCK_HEIGHT - ROD_BORE_ENGAGEMENT)
# The block's paper-side corner (local x 0, z 16) must stand off the paper.
_REAR_CORNER_Z = _block_to_machine((0.0, 0.0, BLOCK_DEPTH))[2]
assert _REAR_CORNER_Z <= PAPER_FRONT_Z - 2 * CLEARANCE, (
    f"v-block rear corner z {_REAR_CORNER_Z:.2f} too close to the paper {PAPER_FRONT_Z}"
)

# --- marker in the groove --------------------------------------------------------
# Barrel O8 in the 8.5 x 4.5 groove: axis CLEARANCE below the groove roof,
# centred in Z; the nib (marker local origin, +Y along the barrel) reaches
# past the block's rear end face to CLEARANCE off the paper front.
MARKER_AXIS_LOCAL_Y = GROOVE_DEPTH - BARREL_DIA / 2.0 - CLEARANCE  # 0.25
assert GROOVE_WIDTH >= BARREL_DIA + 2 * CLEARANCE
# Solve the nib's block-local x from the paper stand-off: machine z of a
# local (x, ., 8) point is VBLOCK_POS.z - x*cos + 8*sin.
MARKER_TIP_LOCAL_X = -(
    (PAPER_FRONT_Z - CLEARANCE) - VBLOCK_POS[2] - (BLOCK_DEPTH / 2.0) * _S
) / _C
assert MARKER_TIP_LOCAL_X < 0.0 < MARKER_TIP_LOCAL_X + BARREL_TOP_Y - BLOCK_LENGTH, (
    "marker must pass right through the block: nib past the rear face, body past the front"
)
MARKER_POS = _block_to_machine((MARKER_TIP_LOCAL_X, MARKER_AXIS_LOCAL_Y, BLOCK_DEPTH / 2.0))
# Marker local +Y -> block local +X (the barrel runs forward along the groove):
# spin -90 about Z (Y -> X) then the block's yaw.
_YAW_ROWS = BLOCK_ROWS
MARKER_ROWS = [
    [sum(rot_z_rows(-90.0)[i][k] * _YAW_ROWS[k][j] for k in range(3)) for j in range(3)]
    for i in range(3)
]
MARKER_ROT = euler_from_rows(MARKER_ROWS)

# --- stirrup frame + thumb screw ---------------------------------------------------
# Frame-local (build_pen_frame): width X (TRIM_NEAR..OUTER_WIDTH), height Y
# 0..OUTER_HEIGHT, depth Z 0..FRAME_DEPTH; window X RAIL_SIDE..W-RAIL_SIDE,
# Y RAIL_END..H-RAIL_END; set-screw tapped hole up through the bottom rail at
# (W/2, ., D/2). Placed with its plane perpendicular to the block length:
# frame X -> block Z (across the depth), frame Y -> up, frame Z -> block -X
# (rearward), which is a yaw of -45 (right-handed). The window straddles the
# block section with 1.0 a side, its top rail FRAME_TOP_GAP above the block
# top, and the ring sits FRAME_ROD_GAP forward of the rod's front face.
FRAME_TOP_GAP = 0.1
FRAME_ROD_GAP = 1.0
FRAME_X_CENTER_LOCAL = ROD_BORE_LOCAL[0] + ROD_SECTION / 2.0 + FRAME_ROD_GAP + FRAME_DEPTH / 2.0
assert OUTER_WIDTH - 2 * RAIL_SIDE >= BLOCK_DEPTH + 2.0, "stirrup window must pass the block"
assert FRAME_X_CENTER_LOCAL + FRAME_DEPTH / 2.0 < BLOCK_LENGTH, "stirrup off the block end"
_FRAME_ORIGIN_LOCAL = (
    FRAME_X_CENTER_LOCAL + FRAME_DEPTH / 2.0,  # frame z 0 is its rear face
    BLOCK_HEIGHT + FRAME_TOP_GAP + RAIL_END - OUTER_HEIGHT,  # bottom outer face
    BLOCK_DEPTH / 2.0 - OUTER_WIDTH / 2.0,  # frame x 0 (window centred on the block)
)
FRAME_POS = _block_to_machine(_FRAME_ORIGIN_LOCAL)
FRAME_ROWS = [[_C, 0.0, _S], [0.0, 1.0, 0.0], [-_S, 0.0, _C]]  # yaw -45
FRAME_ROT = euler_from_rows(FRAME_ROWS)
# Thumb screw (build_pen_set_screw: axis +X from the knob's outer face at x 0,
# knob 0..KNOB_LENGTH, shank to KNOB_LENGTH + SHANK_LEN): stood on end (+X ->
# +Y) on the frame's screw axis, its tip CLEARANCE under the marker barrel.
SET_SCREW_ROWS = rot_z_rows(90.0)  # X -> +Y
SET_SCREW_ROT = euler_from_rows(SET_SCREW_ROWS)
_MARKER_BOTTOM_LOCAL_Y = MARKER_AXIS_LOCAL_Y - BARREL_DIA / 2.0
_SCREW_TIP_LOCAL_Y = _MARKER_BOTTOM_LOCAL_Y - CLEARANCE
SET_SCREW_POS = _block_to_machine(
    (FRAME_X_CENTER_LOCAL, _SCREW_TIP_LOCAL_Y - KNOB_LENGTH - SHANK_LEN, BLOCK_DEPTH / 2.0)
)
assert _SCREW_TIP_LOCAL_Y - KNOB_LENGTH - SHANK_LEN + KNOB_LENGTH < _FRAME_ORIGIN_LOCAL[1], (
    "the knob must stand below the stirrup's bottom rail"
)

# --- amplification wire 2 (rim -> pen rod) -----------------------------------
# Endpoints + length live in pen_wire_geom (the part's length IS the run);
# assert them against THIS script's anchors so a layout move fails loud.
# pen_wire_geom, NOT build_pen_wire: the part build's import closure carries
# pen_wire_spec's drawing prose, which would fold note edits into this
# assembly's full-rebuild recipe (codex #361).
from pen_wire_geom import (  # noqa: E402
    WIRE_BOTTOM as PEN_WIRE_BOTTOM,
    WIRE_LEN as PEN_WIRE_LEN,
)
from pen_rod_spec import (  # noqa: E402
    ROD_SECTION as _SPEC_ROD_SECTION,
    WIRE_HOLE_Y as ROD_WIRE_HOLE_Y,
)

assert math.isclose(ROD_SECTION, _SPEC_ROD_SECTION), "pen-rod section drifted"
assert math.isclose(
    PEN_WIRE_BOTTOM[1], PEN_ROD_POS[1] + ROD_WIRE_HOLE_Y, abs_tol=1e-9
), "pen-wire bottom drifted from the pen-rod wire hole"
assert math.isclose(PEN_WIRE_BOTTOM[1] + PEN_WIRE_LEN, WHEEL_BAR_Y, abs_tol=1e-9), (
    "pen-wire top drifted from the wheel-axis tangent height"
)

# --- M6.10 fastener ----------------------------------------------------------
# Pen-hanger screw from BEHIND the bar (the wheel rim passes 1.0 in front
# of the strap, so no front-side head fits): AF-7 head on the bar back
# face (-129.9 -- the 9-deep support-bar stock seated on the clamp arc,
# build_magnifier_assembly BAR_BACK_Z), O3.5 shank through the bar + strap
# holes, tip 0.5 behind the strap front face (-141.9).
HANGER_SCREW_POS = (-5.5, WHEEL_BAR_Y, -129.9)


async def build(adapter) -> dict[str, str]:
    # Reset the free-DOF manifest buffer before any *_driver(free_dof_key=...)
    # call: each freed DOF is recorded (never authored) and persisted below.
    reset_dof_manifest()
    check("create_assembly", await adapter.create_assembly())

    # The pen carriage slides vertically through the hanger's guide block: the
    # magnifying wheel's wire (flexible, not modeled as geometry --
    # dimensions.yaml ch24) raises/lowers it to trace the curve. The rod runs
    # as a Y-prismatic -- its local slide axis held parallel to the Front +
    # Right planes (axis-to-plane distance, no rotational overlap), an
    # angle(Front) snapshot killing spin, and the Y-travel drive spec (the
    # compliant-chain snapshot the wire would set) recorded into the DOF
    # manifest -- the travel stays live in the saved model. The carriage
    # rides the rod via Lock mates. The hanger is FIRST so the auto-fixed
    # seed is structure, not the rod.
    hanger = await place_component(
        adapter, "pen-hanger", list(HANGER_POS), [0.0, 0.0, 0.0], IDENTITY
    )
    pen_rod = await place_component(
        adapter, "pen-rod", list(PEN_ROD_POS), [0.0, 0.0, 0.0], IDENTITY, ground=False
    )
    rod_o = component_origin(adapter, pen_rod)
    await distance_driver(
        adapter,
        named_ref(f"Axis1@{pen_rod}", "AXIS"),
        named_ref("Front Plane", "PLANE"),
        rod_o[2],
        label="pen-rod slide depth",
        verify=(pen_rod, rod_o),
    )
    await distance_driver(
        adapter,
        named_ref(f"Axis1@{pen_rod}", "AXIS"),
        named_ref("Right Plane", "PLANE"),
        rod_o[0],
        label="pen-rod slide across",
        verify=(pen_rod, rod_o),
    )
    await angle_driver(
        adapter,
        named_ref(f"Front Plane@{pen_rod}", "PLANE"),
        named_ref("Front Plane", "PLANE"),
        0.0,
        label="pen-rod spin snapshot",
        verify=(pen_rod, rod_o),
    )
    # The Y-travel is the sub's FREED operational DOF (the pen up/down the
    # magnifying wheel's wire drives in the real device): its drive spec is
    # recorded into the DOF manifest, never authored -- drag the rod and the
    # whole carriage + pen-wire slide with it.
    await distance_driver(
        adapter,
        named_ref(f"Top Plane@{pen_rod}", "PLANE"),
        named_ref("Top Plane", "PLANE"),
        rod_o[1],
        label="pen-rod travel PARK driver (freed in default build)",
        verify=(pen_rod, rod_o),
        free_dof_key="pen_travel",
    )

    # The carriage: v-block hanging on the rod, marker in its groove, stirrup
    # frame round the block section, thumb screw up through the frame -- each
    # placed at its exact pose and LOCKED to the rod (a Lock mate freezes the
    # full relative transform, so one mate per rider).
    riders = [
        ("pen-v-block", list(VBLOCK_POS), BLOCK_ROT, BLOCK_ROWS),
        ("pen-marker", list(MARKER_POS), MARKER_ROT, MARKER_ROWS),
        ("pen-frame", list(FRAME_POS), FRAME_ROT, FRAME_ROWS),
        ("pen-set-screw", list(SET_SCREW_POS), SET_SCREW_ROT, SET_SCREW_ROWS),
    ]
    placed: dict[str, str] = {}
    for part, pos, rot, rows in riders:
        name = await place_component(adapter, part, pos, rot, rows, ground=False)
        placed[part] = name
        await lock_mate(
            adapter,
            named_ref(f"Front Plane@{name}", "PLANE"),
            named_ref(f"Front Plane@{pen_rod}", "PLANE"),
            label=f"{part} locked to rod",
        )
        assert_component_placed(adapter, name, pos, rows)
    # The thumb screw sits on the stirrup's tapped-hole axis by construction
    # (SET_SCREW_POS is derived from FRAME_X_CENTER_LOCAL / the block depth
    # centre, the same block-local station the frame's ScrewX/ScrewZ resolve
    # to); a coincident axis mate on top of the two Locks would only
    # over-constrain the solve.

    # Amplification wire 2: the straight rest-pose run hanging off the wheel
    # rim's 3 o'clock tangent down to the rod's wire hole level (the tie-off
    # is implied -- module docstring). Locked to the rod so it rides the pen
    # travel with the carriage.
    pen_wire = await place_component(
        adapter,
        "pen-wire",
        list(PEN_WIRE_BOTTOM),
        [0.0, 0.0, 0.0],
        IDENTITY,
        ground=False,
    )
    await lock_mate(
        adapter,
        named_ref(f"Front Plane@{pen_wire}", "PLANE"),
        named_ref(f"Front Plane@{pen_rod}", "PLANE"),
        label="pen-wire locked to rod",
    )

    # Kinematic pen driver (plan F5): re-drives the Y-travel mate from a
    # CrankDeg global through the chained Fourier sum, so the pose reproduces
    # truth_model.pen_y with no force solver (the 21-spring summation is
    # computed, not simulated -- cad/docs/motion-policy.md). The build never
    # authors this mate or its equation -- verify:kinematics replays the
    # recorded DOF-manifest spec and installs the equation transiently on the
    # replayed mate (renamed DRIVE_pen_travel), then discards the model
    # unsaved.

    hanger_screw = await place_component(
        adapter,
        "hanger-screw",
        list(HANGER_SCREW_POS),
        [0.0, 0.0, 0.0],
        IDENTITY,
        ground=False,
    )
    await coincident_mate(
        adapter,
        named_ref(f"ScrewAxis@{hanger_screw}", "AXIS"),
        named_ref(f"HangerScrewAxis@{hanger}", "AXIS"),
        label="hanger screw coaxial with strap tapped hole",
        verify=(hanger_screw, list(HANGER_SCREW_POS)),
    )
    await distance_driver(
        adapter,
        named_ref(f"Front Plane@{hanger_screw}", "PLANE"),
        named_ref("Front Plane", "PLANE"),
        HANGER_SCREW_POS[2],
        label="hanger screw head plane",
        verify=(hanger_screw, list(HANGER_SCREW_POS)),
    )
    await parallel_mate(
        adapter,
        named_ref(f"Right Plane@{hanger_screw}", "PLANE"),
        named_ref("Right Plane", "PLANE"),
        label="hanger screw anti-spin",
        verify=(hanger_screw, list(HANGER_SCREW_POS)),
    )
    assert_component_placed(adapter, hanger_screw, list(HANGER_SCREW_POS), IDENTITY)

    # Certify the AS-BUILT model. Necessity only: the freed pen travel is
    # genuinely free; the lock-mated carriage + pen-wire MUST read
    # under-constrained WITH the rod -- with the neutral preset the motion
    # sweep reads got == want == 0 even if a rider were disconnected.
    assert_free_dof_necessity(
        adapter,
        1,
        required_stems=(
            "pen-rod",
            "pen-marker",
            "pen-wire",
            "pen-v-block",
            "pen-frame",
            "pen-set-screw",
        ),
    )
    write_dof_manifest(ASM_NAME)
    check_no_interference(adapter)
    # Title-block identity for the assembly drawing (draw_pen_assembly.py):
    # assembly_title_properties supplies the Title/Generator and TOL_* cells
    # finalize_drawing requires without consulting the part registry; material and
    # finish defer to the parts list, standard assembly-drawing practice.
    apply_custom_properties(
        adapter,
        {
            **assembly_title_properties(ASM_NAME),
            # MHA-A## = assembly drawing ids, beside the parts' MHA-### range
            # (a longer number overflows the DWG. NO. title-block cell).
            "Number": "MHA-A01",
            "Revision Description": "Initial release",
            "Material": "SEE PARTS LIST",
            "Material Specification": "SEE PARTS LIST",
            "Finish": "SEE PARTS LIST",
            "Quantity": "1",
            "Drawn By": DRAWN_BY,
        },
    )
    # The title block's PART cell resolves the document summary Title (the
    # part builds stamp it in save_part_and_images); without it the assembly
    # print ships a blank PART row. "pen assembly", not the bare stem: the
    # sheet must identify itself as an assembly drawing (codex machinist
    # review).
    apply_summary_info(adapter, title=f"{ASM_NAME} assembly")
    return await save_assembly_and_images(adapter, ASM_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
