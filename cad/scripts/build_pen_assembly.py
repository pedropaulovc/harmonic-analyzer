r"""Reproduction script: pen subassembly (book ch. 24).

The machine's output transducer: the pen carriage that writes the Fourier sum
onto the recording paper, in machine coordinates (assembly origin = base
origin; the output side is -Z). The pen rod + marker slide vertically through
the fixed v-block bores; the magnifying wheel's wire (pen-wire, WIRE 2 --
modeled as its straight rest-pose run only) raises and lowers them to trace
the curve.

* pen-hanger (ground) on the wheel-bar + pen-v-block (ground) -- the fixed
  guide.
* pen-rod -- a Y-prismatic; its travel is the sub's single FREED operational
  DOF: its drive spec is recorded into the DOF manifest, never authored, so
  the saved model slides freely and carries NO pen-driver equation.
  verify:kinematics replays the recorded spec and installs the F5
  chained-Fourier driver transiently (reproduces truth_model.pen_y from a
  CrankDeg global, no force solver).
* pen-marker (locked to the rod), pen-frame (over the marker + rod on the
  v-block top), pen-set-screw.
* pen-wire -- WIRE 2's straight rest-pose run from the wheel-rim tangent down
  to the rod's wire hole, locked to the rod so it rides the pen travel. The
  rim wrap and tie-off are not modeled; the kinematic coupling stays a
  Motion-study mate (cad/docs/motion-policy.md).
* hanger-screw -- fastens the pen-hanger from behind the wheel bar.

Cross-subassembly fits (checked at the top level): the pen-hanger clamps the
wheel-bar (magnifier.SLDASM) and the wheel rim -> pen-rod wire couples the
pen to the magnifier.

Documented simplifications (Appendix C): the pen marker hangs VERTICAL with
its tip 8.6 in front of the paper plane -- the real pen tilts ~12 deg in
angled v-block bores, but our bores are vertical, so pen-to-paper contact is
not modeled.

Fix-all strategy (M6.2): the hanger / v-block / frame / set-screw inserted at
their exact final transform and fixed; the rod + marker left free and
constrained by mates (the rod's Y-travel recorded into the DOF manifest, never
authored); transforms asserted by read-back; zero interference.

Dimensions: cad/DIMENSIONS.md ch. 24.

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
from _transforms import IDENTITY, ROT_Y_180

ASM_NAME = "pen"

# --- machine anchors ---------------------------------------------------------
WHEEL_BAR_Y = 575.7  # the wheel-bar the pen-hanger clamps (magnifier.SLDASM)

# --- pen ---------------------------------------------------------------------
PEN_ROD_X = 3.0
PEN_Z_MID = -151.5  # pen-rod / v-block bore plane (v-block back face -143.5
# clears the plate front -142.9 by 0.6)
HANGER_POS = (PEN_ROD_X, 505.0, PEN_Z_MID)
PEN_ROD_POS = (PEN_ROD_X, 398.0, PEN_Z_MID - 2.5)  # rod z -154..-149
# Ry(180): the v-block is modeled bores-toward-local-+x/+z; turned about Y its
# back face (the local z 0 wall, now at world z -143.5) clears the plate front
# and the rod bore (local x 21, z 8) lands at (3, -151.5).
VBLOCK_POS = (24.0, 390.0, -143.5)
MARKER_X = 13.0  # marker bore (local x 11)
MARKER_TIP_Y = 368.0
# Frame flat on the v-block top (y 408), long axis along X so its window
# (machine x -7..+25, z -161..-147) spans the marker barrel (+9..+17,
# z -155.5..-147.5) and the pen rod (+0.5..+5.5, z -154..-149). Mapping:
# machine x = 29 - local y, machine y = 408 + local z, machine z =
# -143 - local x; the ring's near rail is trimmed to local x 0.75
# (build_pen_frame TRIM_NEAR) so its edge (z -143.75) clears the recording
# paper's front face (-143.4) by 0.35. The screw hole (local x 11, z 5)
# lands at machine (y 413, z -154), axis along X through the east end rail.
FRAME_POS = (29.0, 408.0, -143.0)
FRAME_ROWS = [[0.0, 0.0, -1.0], [-1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]
# Set screw turned Ry(180) so its own axis presses east (-X) through the
# frame's east end-rail hole: knob x +33..+38, shank tip at x +18, 1 short
# of the marker barrel's east face (+17).
SET_SCREW_POS = (38.0, 413.0, -154.0)

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
from build_pen_rod import WIRE_HOLE_Y as ROD_WIRE_HOLE_Y  # noqa: E402

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

    # The pen carriage (rod + marker) slides vertically through the fixed
    # v-block bores: the magnifying wheel's wire (flexible, not modeled as
    # geometry -- DIMENSIONS.md ch24) raises/lowers it to trace the curve. The
    # rod runs as a Y-prismatic -- its local slide axis held parallel to the
    # Front + Right planes (axis-to-plane distance, no rotational overlap), an
    # angle(Front) snapshot killing spin, and the Y-travel drive spec (the
    # compliant-chain snapshot the wire would set) recorded into the DOF
    # manifest -- the travel stays live in the saved model. The marker rides
    # the rod via a Lock mate. Probed FULLY(3), probe_pen.py.
    # The hanger is FIRST so the auto-fixed seed is structure, not the rod.
    hanger = await place_component(
        adapter, "pen-hanger", list(HANGER_POS), [0.0, 0.0, 0.0], IDENTITY
    )
    await place_component(
        adapter, "pen-v-block", list(VBLOCK_POS), [0.0, 180.0, 0.0], ROT_Y_180
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
    # marker + pen-wire slide with it.
    await distance_driver(
        adapter,
        named_ref(f"Top Plane@{pen_rod}", "PLANE"),
        named_ref("Top Plane", "PLANE"),
        rod_o[1],
        label="pen-rod travel PARK driver (freed in default build)",
        verify=(pen_rod, rod_o),
        free_dof_key="pen_travel",
    )
    pen_marker = await place_component(
        adapter,
        "pen-marker",
        [MARKER_X, MARKER_TIP_Y, PEN_Z_MID],
        [0.0, 0.0, 0.0],
        IDENTITY,
        ground=False,
    )
    await lock_mate(
        adapter,
        named_ref(f"Front Plane@{pen_marker}", "PLANE"),
        named_ref(f"Front Plane@{pen_rod}", "PLANE"),
        label="pen-marker locked to rod",
    )

    # Amplification wire 2: the straight rest-pose run hanging off the wheel
    # rim's 3 o'clock tangent down to the rod's wire hole level, 1.7 in front
    # of the rod face (the tie-off is implied -- module docstring). Locked to
    # the rod so it rides the pen travel with the marker.
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
    # Rx(-90)*Ry(+90) (gimbal representative [-90, 90, 0]): the ring lies flat
    # on the v-block top, long axis along X, window over the marker + pen rod
    # (see FRAME_POS comment).
    frame = await place_component(
        adapter, "pen-frame", list(FRAME_POS), [-90.0, 90.0, 0.0], FRAME_ROWS
    )
    # Ry(180): the screw's own axis presses east (-X) through the frame's
    # east end-rail hole toward the marker barrel.
    set_screw = await place_component(
        adapter,
        "pen-set-screw",
        list(SET_SCREW_POS),
        [0.0, 180.0, 0.0],
        ROT_Y_180,
        ground=False,
    )
    await coincident_mate(
        adapter,
        named_ref(f"ScrewAxis@{set_screw}", "AXIS"),
        named_ref(f"SetScrewAxis@{frame}", "AXIS"),
        label="pen set-screw coaxial with frame tapped hole",
        verify=(set_screw, list(SET_SCREW_POS)),
    )
    await distance_driver(
        adapter,
        named_ref(f"Right Plane@{set_screw}", "PLANE"),
        named_ref("Right Plane", "PLANE"),
        SET_SCREW_POS[0],
        label="pen set-screw adjustment depth",
        verify=(set_screw, list(SET_SCREW_POS)),
    )
    await parallel_mate(
        adapter,
        named_ref(f"Top Plane@{set_screw}", "PLANE"),
        named_ref("Top Plane", "PLANE"),
        label="pen set-screw anti-spin",
        verify=(set_screw, list(SET_SCREW_POS)),
    )
    assert_component_placed(adapter, set_screw, list(SET_SCREW_POS), ROT_Y_180)

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
    # genuinely free; the lock-mated marker + pen-wire MUST read
    # under-constrained WITH the rod -- with the neutral preset the motion
    # sweep reads got == want == 0 even if a rider were disconnected.
    assert_free_dof_necessity(
        adapter, 1, required_stems=("pen-rod", "pen-marker", "pen-wire")
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
