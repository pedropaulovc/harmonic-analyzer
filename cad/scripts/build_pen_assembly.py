r"""Reproduction script: pen subassembly (book ch. 24).

The machine's output transducer: the pen carriage that writes the Fourier sum
onto the recording paper, in machine coordinates (assembly origin = base
origin; the output side is -Z). The pen rod + marker slide vertically through
the fixed v-block bores; the magnifying wheel's wire (pen-wire, WIRE 2 --
modeled as its straight rest-pose run only) raises and lowers them to trace
the curve.

* pen-hanger (ground) on the wheel-bar + pen-v-block (ground) -- the fixed
  guide.
* pen-rod -- a Y-prismatic, driven through the F5 chained-Fourier pen driver
  (reproduces truth_model.pen_y from a CrankDeg global, no force solver).
* pen-marker (locked to the rod), pen-frame (over the marker + rod on the
  v-block top), pen-set-screw.
* pen-wire -- WIRE 2's straight rest-pose run from the wheel-rim tangent down
  to the rod's wire hole, locked to the rod so it rides the pen travel. The
  rim wrap and tie-off are not modeled; the kinematic coupling stays a
  Motion-study mate (docs/motion-policy.md).
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
constrained by mates (the rod's Y-travel re-driven by the F5 equation);
transforms asserted by read-back; zero interference.

Dimensions: cad/DIMENSIONS.md ch. 24.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pen_assembly.py
"""

from __future__ import annotations
import _config_asm

import math
import sys

from _common import (
    _read_member,
    check,
    log,
    run_build,
)
from _assembly import (
    set_flip_seeds,
    angle_driver,
    assert_components_fully_defined,
    check_no_interference,
    component_origin,
    distance_driver,
    lock_mate,
    named_ref,
    place_component,
    save_assembly_and_images,
)
from _transforms import IDENTITY
import pen_driver  # noqa: E402  (kinematic pen driver, plan F5)

ASM_NAME = "pen"

# --- machine anchors ---------------------------------------------------------
WHEEL_BAR_Y = 565.0  # the wheel-bar the pen-hanger clamps (magnifier.SLDASM)

# --- pen ---------------------------------------------------------------------
PEN_ROD_X = -3.0
PEN_Z_MID = -151.5  # pen-rod / v-block bore plane (v-block back face -143.5
# clears the plate front -142.9 by 0.6)
HANGER_POS = (PEN_ROD_X, 505.0, PEN_Z_MID)
PEN_ROD_POS = (PEN_ROD_X, 398.0, PEN_Z_MID - 2.5)  # rod z -154..-149
VBLOCK_POS = (-24.0, 390.0, -159.5)  # rod bore (local x 21) at (-3, -151.5)
MARKER_X = -13.0  # marker bore (local x 11)
MARKER_TIP_Y = 368.0
# Frame flat on the v-block top (y 408), long axis along X so its window
# (machine x -25..+7, z -161..-147) spans the marker barrel (-17..-9,
# z -155.5..-147.5) and the pen rod (-5.5..-0.5, z -154..-149). Mapping:
# machine x = -29 + local y, machine y = 418 - local z, machine z =
# -143 - local x; the ring's near rail is trimmed to local x 0.75
# (build_pen_frame TRIM_NEAR) so its edge (z -143.75) clears the recording
# paper's front face (-143.4) by 0.35. The screw hole (local x 11, z 5)
# lands at machine (y 413, z -154), axis along X through the west end rail.
FRAME_POS = (-29.0, 418.0, -143.0)
FRAME_ROWS = [[0.0, 0.0, -1.0], [1.0, 0.0, 0.0], [0.0, -1.0, 0.0]]
# Set screw along +X (the part's own axis): knob x -38..-33, shank tip at
# x -18, 1 short of the marker barrel's west face (-17).
SET_SCREW_POS = (-38.0, 413.0, -154.0)

# --- amplification wire 2 (rim -> pen rod) -----------------------------------
# Endpoints + length live in build_pen_wire.py (the part's length IS the run);
# assert them against THIS script's anchors so a layout move fails loud.
from build_pen_wire import (  # noqa: E402
    WIRE_BOTTOM as PEN_WIRE_BOTTOM,
    WIRE_LEN as PEN_WIRE_LEN,
)
from build_pen_rod import WIRE_HOLE_Y as ROD_WIRE_HOLE_Y  # noqa: E402

assert math.isclose(
    PEN_WIRE_BOTTOM[1], PEN_ROD_POS[1] + ROD_WIRE_HOLE_Y, abs_tol=1e-9
), "pen-wire bottom drifted from the pen-rod wire hole"
assert math.isclose(
    PEN_WIRE_BOTTOM[1] + PEN_WIRE_LEN, WHEEL_BAR_Y, abs_tol=1e-9
), "pen-wire top drifted from the wheel-axis tangent height"

# --- M6.10 fastener ----------------------------------------------------------
# Pen-hanger screw from BEHIND the bar (the wheel rim passes 1.0 in front
# of the strap, so no front-side head fits): AF-7 head on the bar back
# face (-128.9), O3.5 shank through the bar + strap holes, tip 0.5 behind
# the strap front face (-141.9).
HANGER_SCREW_POS = (5.5, WHEEL_BAR_Y, -128.9)  # machine x -5.5


async def build(adapter) -> dict[str, str]:
    set_flip_seeds(_config_asm.flip_seeds("pen"))  # per-assembly learned flip polarity
    check("create_assembly", await adapter.create_assembly())

    # The pen carriage (rod + marker) slides vertically through the fixed
    # v-block bores: the magnifying wheel's wire (flexible, not modeled as
    # geometry -- DIMENSIONS.md ch24) raises/lowers it to trace the curve. The
    # rod runs as a Y-prismatic -- its local slide axis held parallel to the
    # Front + Right planes (axis-to-plane distance, no rotational overlap), an
    # angle(Front) snapshot killing spin, a Y distance snapshot pinning travel
    # (this is the compliant-chain snapshot the wire would set; suppressed in
    # the Motion study, where the wheel-rim->rod coupling drives it). The marker
    # rides the rod via a Lock mate. Probed FULLY(3), probe_pen.py.
    # The hanger is FIRST so the auto-fixed seed is structure, not the rod.
    await place_component(adapter, "pen-hanger", list(HANGER_POS),
                          [0.0, 0.0, 0.0], IDENTITY)
    await place_component(adapter, "pen-v-block", list(VBLOCK_POS),
                          [0.0, 0.0, 0.0], IDENTITY)
    pen_rod = await place_component(adapter, "pen-rod", list(PEN_ROD_POS),
                                    [0.0, 0.0, 0.0], IDENTITY, ground=False)
    rod_o = component_origin(adapter, pen_rod)
    await distance_driver(adapter, named_ref(f"Axis1@{pen_rod}", "AXIS"),
                          named_ref("Front Plane", "PLANE"), rod_o[2],
                          label="pen-rod slide depth", verify=(pen_rod, rod_o))
    await distance_driver(adapter, named_ref(f"Axis1@{pen_rod}", "AXIS"),
                          named_ref("Right Plane", "PLANE"), rod_o[0],
                          label="pen-rod slide across", verify=(pen_rod, rod_o))
    await angle_driver(adapter, named_ref(f"Front Plane@{pen_rod}", "PLANE"),
                       named_ref("Front Plane", "PLANE"), 0.0,
                       label="pen-rod spin snapshot", verify=(pen_rod, rod_o))
    pen_travel = await distance_driver(
        adapter, named_ref(f"Top Plane@{pen_rod}", "PLANE"),
        named_ref("Top Plane", "PLANE"), rod_o[1],
        label="pen-rod travel snapshot", verify=(pen_rod, rod_o))
    pen_marker = await place_component(adapter, "pen-marker",
                                       [MARKER_X, MARKER_TIP_Y, PEN_Z_MID],
                                       [0.0, 0.0, 0.0], IDENTITY, ground=False)
    await lock_mate(adapter, named_ref(f"Front Plane@{pen_marker}", "PLANE"),
                    named_ref(f"Front Plane@{pen_rod}", "PLANE"),
                    label="pen-marker locked to rod")

    # Amplification wire 2: the straight rest-pose run hanging off the wheel
    # rim's 3 o'clock tangent down to the rod's wire hole level, 1.7 in front
    # of the rod face (the tie-off is implied -- module docstring). Locked to
    # the rod so it rides the pen travel with the marker.
    pen_wire = await place_component(adapter, "pen-wire", list(PEN_WIRE_BOTTOM),
                                     [0.0, 0.0, 0.0], IDENTITY, ground=False)
    await lock_mate(adapter, named_ref(f"Front Plane@{pen_wire}", "PLANE"),
                    named_ref(f"Front Plane@{pen_rod}", "PLANE"),
                    label="pen-wire locked to rod")

    # Kinematic pen driver (plan F5): re-drive the Y-travel mate from a CrankDeg
    # global through the chained Fourier sum, so the pose reproduces
    # truth_model.pen_y with no force solver (the 21-spring summation is
    # computed, not simulated -- docs/motion-policy.md). The mate stays a
    # distance mate (still fully defines the rod); only its value is now an
    # equation. At pen_rest_crank_deg the equation evaluates to the build datum,
    # so this snapshot pose is byte-for-byte the previous fixed-value pose.
    travel_mate = pen_travel.get("name")
    base_mm = abs(rod_o[1])
    param = adapter._attempt(
        lambda: adapter.currentModel.Parameter(f"D1@{travel_mate}"), default=None)
    if param is None:
        raise RuntimeError(f"cannot read D1@{travel_mate} for the pen driver")
    base_doc = float(_read_member(param, "Value"))  # IPS doc -> inches
    factor = base_doc / base_mm  # document units per mm
    info = await pen_driver.install(adapter, travel_mate, base_doc, factor)
    log(f"pen driver: {info['links']}-link chain, scale "
        f"{info['scale_mm_per_unit']:.4g} mm/unit, rest {info['rest_deg']:g} deg")
    log(f"  equation: {info['equation']}")
    # Ry(+90)*Rx(+90): the ring lies flat on the v-block top, long axis
    # along X, window over the marker + pen rod (see FRAME_POS comment).
    await place_component(adapter, "pen-frame", list(FRAME_POS),
                          [90.0, 90.0, 0.0], FRAME_ROWS)
    # No rotation: the screw's own +X axis presses east through the frame's
    # west end-rail hole toward the marker barrel.
    await place_component(adapter, "pen-set-screw", list(SET_SCREW_POS),
                          [0.0, 0.0, 0.0], IDENTITY)
    await place_component(adapter, "hanger-screw", list(HANGER_SCREW_POS),
                          [0.0, 0.0, 0.0], IDENTITY)

    assert_components_fully_defined(adapter)
    check_no_interference(adapter)
    return await save_assembly_and_images(adapter, ASM_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
