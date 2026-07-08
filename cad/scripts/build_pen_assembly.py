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
  DOF in the default `free` build (cad/config/machine/build_lock.yaml): the
  travel park driver is DEFERRED (recorded, not authored), so the saved model
  slides freely and carries NO pen-driver equation. verify:kinematics replays
  the recorded spec and installs the F5 chained-Fourier driver transiently
  (reproduces truth_model.pen_y from a CrankDeg global, no force solver); a
  `locked` build authors the mate + equation at build time (see ``LOCK``).
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
constrained by mates (the rod's Y-travel a deferred park driver in `free`
builds, an F5-equation-driven mate in `locked`); transforms asserted by
read-back; zero interference.

Dimensions: cad/DIMENSIONS.md ch. 24.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pen_assembly.py
"""

from __future__ import annotations

import math
import sys

import _config
from _common import (
    _read_member,
    check,
    log,
    run_build,
)
from _assembly import (
    PARK_PREFIX,
    angle_driver,
    assert_expected_free_dof,
    assert_free_dof_necessity,
    check_no_interference,
    coincident_mate,
    component_origin,
    component_transform,
    distance_driver,
    is_locked_build,
    lock_mate,
    named_ref,
    place_component,
    save_assembly_and_images,
    set_park_defer,
    write_park_specs,
)
from _transforms import IDENTITY
import pen_driver  # noqa: E402  (kinematic pen driver, plan F5)

ASM_NAME = "pen"

# Build mode (cad/config/machine/build_lock.yaml). `free` (default) leaves the
# pen carriage's VERTICAL TRAVEL -- the sub's single operational DOF -- UNLOCKED:
# its park driver is DEFERRED (recorded, not authored), so the saved model is a
# working kinematic model (drag the rod and the marker + pen-wire ride it) and
# carries NO pen-driver equation -- verify:kinematics replays the recorded spec
# transiently and installs the F5 equation on the replayed mate. `locked`
# authors the park driver engaged and installs the equation at build time (the
# old fully-defined snapshot). The literal accessor tokenises to
# machine/build_lock.yaml in the doit/cache digest.
LOCK = is_locked_build(_config.machine("build_lock", "pen"))

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
# face (-129.9 -- the 9-deep support-bar stock seated on the clamp arc,
# build_magnifier_assembly BAR_BACK_Z), O3.5 shank through the bar + strap
# holes, tip 0.5 behind the strap front face (-141.9).
HANGER_SCREW_POS = (5.5, WHEEL_BAR_Y, -129.9)  # machine x -5.5


def _plane_normals_and_origin(adapter, name: str):
    """World normals of a component's (Right, Top, Front) planes + its origin
    (mm). Transform2 is row-major (`world = local.R`), so the world normal of
    the plane whose local normal is local axis i is row i."""
    a = component_transform(adapter, name)
    rows = [(a[0], a[1], a[2]), (a[3], a[4], a[5]), (a[6], a[7], a[8])]
    org = [a[9] * 1000.0, a[10] * 1000.0, a[11] * 1000.0]
    return rows, org


async def _locate_to_datum(adapter, name: str, *, base: str | None = None) -> None:
    """Locate a part by three orthogonal plane-distance mates -- the semantic
    replacement for a fix (#110 idiom) or a rigid-ride lock. Orientation-
    agnostic: each principal plane is paired to the base plane whose world normal
    is most parallel, and the perpendicular distance is the origin offset
    projected onto that normal -- so any rotation works with no pairing table.

    ``base=None`` mates to the machine datum planes. ``base=<component>`` mates to
    THAT component's planes, rigidly tying this part to the base's (possibly
    moving) frame -- a lock replacement; the part-to-part references keep the
    mates hard, not suppressible drivers, so the part rides the base.
    """
    planes = ("Right Plane", "Top Plane", "Front Plane")
    part_n, o = _plane_normals_and_origin(adapter, name)
    if base is not None:
        base_n, ref0 = _plane_normals_and_origin(adapter, base)
    else:
        base_n = [(1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)]
        ref0 = [0.0, 0.0, 0.0]
    delta = [o[i] - ref0[i] for i in range(3)]
    suffix = f"@{base}" if base is not None else ""
    used: set[int] = set()
    for li, part_plane in enumerate(planes):
        n = part_n[li]
        bi = max((j for j in range(3) if j not in used),
                 key=lambda j: abs(sum(n[k] * base_n[j][k] for k in range(3))))
        used.add(bi)
        bn = base_n[bi]
        coord = sum(delta[k] * bn[k] for k in range(3))
        part_ref = named_ref(f"{part_plane}@{name}", "PLANE")
        base_ref = named_ref(f"{planes[bi]}{suffix}", "PLANE")
        tag = f"{part_plane.split()[0]}->{planes[bi].split()[0]}{suffix}"
        if abs(coord) < 1e-6:
            await coincident_mate(adapter, part_ref, base_ref,
                                  label=f"{name} datum {tag}=0", verify=(name, o))
            continue
        await distance_driver(adapter, part_ref, base_ref, abs(coord),
                              label=f"{name} datum {tag} d={abs(coord):.2f}",
                              verify=(name, o))


async def build(adapter) -> dict[str, str]:
    # `free` (default) DEFERS the freed-DOF park driver (records, does not
    # author); `locked` authors it engaged. Set before the *_driver call below.
    set_park_defer(not LOCK)
    check("create_assembly", await adapter.create_assembly())

    # The pen carriage (rod + marker) slides vertically through the fixed
    # v-block bores: the magnifying wheel's wire (flexible, not modeled as
    # geometry -- DIMENSIONS.md ch24) raises/lowers it to trace the curve. The
    # rod runs as a Y-prismatic -- its local slide axis held parallel to the
    # Front + Right planes (axis-to-plane distance, no rotational overlap), an
    # angle(Front) snapshot killing spin, and the Y-travel park driver (the
    # compliant-chain snapshot the wire would set) DEFERRED in `free` builds --
    # the travel stays live -- or authored + F5-equation-driven in `locked`.
    # The marker rides the rod via a Lock mate. Probed FULLY(3), probe_pen.py.
    # The hanger is FIRST so the auto-fixed seed is structure, not the rod.
    await place_component(adapter, "pen-hanger", list(HANGER_POS),
                          [0.0, 0.0, 0.0], IDENTITY, ground=False,
                          label="pen-hanger (seed)")
    vblock = await place_component(adapter, "pen-v-block", list(VBLOCK_POS),
                                   [0.0, 0.0, 0.0], IDENTITY, ground=False)
    await _locate_to_datum(adapter, vblock)
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
    # The Y-travel is the sub's FREED operational DOF (the pen up/down the
    # magnifying wheel's wire drives in the real device): its park driver is
    # DEFERRED in the default `free` build (recorded, not authored -- drag the
    # rod and the marker + pen-wire slide with it), authored engaged + equation-
    # driven in a `locked` build.
    await distance_driver(
        adapter, named_ref(f"Top Plane@{pen_rod}", "PLANE"),
        named_ref("Top Plane", "PLANE"), rod_o[1],
        label="pen-rod travel PARK driver (freed in default build)",
        verify=(pen_rod, rod_o), free_dof_key="pen_travel")
    pen_marker = await place_component(adapter, "pen-marker",
                                       [MARKER_X, MARKER_TIP_Y, PEN_Z_MID],
                                       [0.0, 0.0, 0.0], IDENTITY, ground=False)
    # The marker rides the rod's Y-prismatic travel: rigid-tie it to the rod's
    # frame via three orthogonal plane mates (was a lock). Both IDENTITY; the
    # part-to-part references stay hard mates, so the marker follows the rod as
    # the pen driver drives its travel -- with no lock.
    await _locate_to_datum(adapter, pen_marker, base=pen_rod)

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
    # computed, not simulated -- docs/motion-policy.md). LOCKED builds only: the
    # travel mate exists (authored engaged, renamed PARK_pen_travel) and the
    # equation drives its value; at pen_rest_crank_deg it evaluates to the build
    # datum, so the snapshot pose is byte-for-byte the fixed-value pose. In the
    # default `free` build the mate is DEFERRED (no equation in the shipped
    # model); verify:kinematics replays the recorded spec and installs the
    # equation transiently on the replayed mate, then discards unsaved.
    if LOCK:
        travel_mate = f"{PARK_PREFIX}pen_travel"  # _driver_or_defer's rename
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
    frame = await place_component(adapter, "pen-frame", list(FRAME_POS),
                                  [90.0, 90.0, 0.0], FRAME_ROWS, ground=False)
    await _locate_to_datum(adapter, frame)
    # No rotation: the screw's own +X axis presses east through the frame's
    # west end-rail hole toward the marker barrel.
    set_screw = await place_component(adapter, "pen-set-screw", list(SET_SCREW_POS),
                                      [0.0, 0.0, 0.0], IDENTITY, ground=False)
    await _locate_to_datum(adapter, set_screw)
    hanger_screw = await place_component(adapter, "hanger-screw", list(HANGER_SCREW_POS),
                                         [0.0, 0.0, 0.0], IDENTITY, ground=False)
    await _locate_to_datum(adapter, hanger_screw)

    # Certify the AS-BUILT model. free -> necessity only (the freed pen travel
    # is genuinely free; the lock-mated marker + pen-wire MUST read
    # under-constrained WITH the rod -- with the neutral preset the motion
    # sweep reads got == want == 0 even if a rider were disconnected); locked
    # -> strict 0-DOF (the equation-driven mate still fully defines).
    if LOCK:
        await assert_expected_free_dof(adapter, 0)
    else:
        assert_free_dof_necessity(
            adapter, 1, required_stems=("pen-rod", "pen-marker", "pen-wire"))
    write_park_specs(ASM_NAME)
    check_no_interference(adapter)
    return await save_assembly_and_images(adapter, ASM_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
