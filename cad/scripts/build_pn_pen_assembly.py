r"""Reproduction script: pen subassembly (book ch. 24; engineerguy 4/4, 9:15-10:34).

The machine's output transducer: the pen carriage that writes the Fourier sum
onto the recording paper, in machine coordinates (assembly origin = base
origin; the output side is -Z). The square pen rod slides vertically through
the hanger's two U guides; the magnifying wheel's wire (pen-wire, WIRE 2 --
modeled as its straight rest-pose run only) raises and lowers it to trace
the curve. Everything below the guides rides the rod:

* pn-pen-hanger (ground) on the wheel bar -- the fixed U guides.
* pn-pen-rod -- a Y-prismatic; its travel is the sub's single FREED operational
  DOF: its drive spec is recorded into the DOF manifest, never authored, so
  the saved model slides freely and carries NO pen-driver equation.
  verify:kinematics replays the recorded spec and installs the F5
  chained-Fourier driver transiently (reproduces truth_model.pen_y from a
  CrankDeg global, no force solver).
* pn-pen-v-block -- the brass block HANGING on the rod: the rod's turned pivot
  end drops into the block's pivot bore and its square shoulder rests on the
  block top; vn-pen-rod-set-screw (front face) locks the pen's yaw, which is
  PEN_BLOCK_YAW_DEG to the paper.
* vn-pen-marker -- the purchased Sharpie Mini, its grip in the block's V-groove,
  nib on the paper, body running out forward and east.
* pn-pen-frame -- the stirrup flush on the block's PAPER end; vn-pen-set-screw
  (the thumb screw) threads up through its bottom rail and presses the grip
  into the V.
* pn-pen-adjust-screw + vn-pen-adjust-nut -- the height adjuster on the rod
  top: the stud threads into the rod's #0-80 tap, the jam nut locks it, and
  the pen wire ties through its eye.
* pn-pen-wire -- WIRE 2's straight rest-pose run hanging PLUMB from the wheel
  rim's 3 o'clock tangent onto the stud's eye head (the rod line is the rim's
  mid-plane), locked to the rod so it rides the pen travel. The rim wrap and
  tie-off are not modeled; the kinematic coupling stays a Motion-study mate
  (cad/docs/motion-policy.md).
* vn-hanger-screw + vn-pen-hanger-locknut -- fasten the pen-hanger: the screw
  from behind the wheel bar through the strap's clearance hole, the
  nylon-insert locknut on the strap front locking it.

The carriage layout and its plan balance live in ``pn_pen_carriage_geom``
(pure): the rod line PEN_Z_MID and the v-block's pivot-bore station put the
carriage CG on the rod axis, so the pen hangs level and its yaw is held by the
set screw, not by the guides.

Cross-subassembly fits (checked at the top level): the pen-hanger clamps the
wheel bar (mg-magnifier.SLDASM) and the wheel rim -> pen wire couples the pen
to the magnifier; the stirrup's paper-side corner and the nib stand off the
recording paper's front face (pd-paper-drive.SLDASM).

Fix-all strategy (M6.2): the hanger inserted at its exact final transform and
fixed; the rod left free and constrained by mates (its Y-travel recorded into
the DOF manifest, never authored); the carriage parts placed on-solution and
lock-mated to the rod; transforms asserted by read-back; zero interference
beyond the thread-envelope allowances in ``_interference_contracts``.

Dimensions: cad/config/dimensions.yaml ch. 24.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pn_pen_assembly.py
"""

from __future__ import annotations

import math
import sys

from _check import check
from _custom_properties import apply_custom_properties
from _session import run_build
from _drawing_marks import DRAWN_BY
from _assembly import (
    activate_assembly_contract,
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
from _transforms import IDENTITY, euler_from_rows
from _interference_contracts import allowed_interference_pairs
from vn_hanger_screw_spec import SHANK_LEN as HANGER_SHANK_LEN
from vn_hanger_screw_spec import THREAD_PITCH as HANGER_THREAD_PITCH
from vn_hanger_screw_spec import TIP_CHAMFER as HANGER_TIP_CHAMFER
from vn_pen_hanger_locknut_spec import THICKNESS as HANGER_LOCKNUT_T
from vn_pen_hanger_locknut_spec import (
    THREAD_PAST_MIN_PITCHES as HANGER_LOCKNUT_PAST_PITCHES,
)
from mg_magnifying_wheel_geom import RIM_AXIAL as WHEEL_RIM_AXIAL
from mg_magnifying_wheel_geom import RIM_OUTER_DIA as WHEEL_RIM_OUTER_DIA
from mg_wheel_bar_geom import BAR_DEPTH as WHEEL_BAR_DEPTH
from mg_wheel_bar_geom import HANGER_SCREW_MACHINE_X
from mg_wheel_bar_geom import WHEEL_X
from pn_pen_hanger_spec import (
    GUIDE_ENGAGE_MARGIN,
    GUIDE_SPAN_Y,
    HANGER_POS,
    SCREW_HOLE_XY as HANGER_HOLE_XY,
    STRAP_Z as HANGER_STRAP_Z,
)
from pn_pen_wire_geom import (
    WHEEL_BAR_Y,
    WHEEL_MID_Z,
    WIRE_BOTTOM as PEN_WIRE_BOTTOM,
    WIRE_LEN as PEN_WIRE_LEN,
)
from pn_pen_carriage_geom import (
    BLOCK_ROWS,
    CARRIAGE_TOP_Y,
    FRAME_POS,
    FRAME_ROWS,
    MARKER_POS,
    MARKER_ROWS,
    NUT_POS,
    NUT_ROWS,
    ROD_POS as PEN_ROD_POS,
    ROD_SET_SCREW_POS,
    ROD_SET_SCREW_ROWS,
    ROD_SQUARE_TOP_Y,
    STUD_HEAD_TOP_Y,
    STUD_POS,
    THUMB_SCREW_POS,
    THUMB_SCREW_ROWS,
    VBLOCK_POS,
)

ASM_NAME = "pn-pen"

# --- hanger guides: the rod square stays in both U guides over the full travel,
# and nothing riding the rod reaches the lower guide --------------------------------
if ROD_SQUARE_TOP_Y[0] < GUIDE_SPAN_Y[1] + GUIDE_ENGAGE_MARGIN:
    raise AssertionError(
        "pen-rod square leaves the upper U guide at the bottom of travel"
    )
if CARRIAGE_TOP_Y[1] > GUIDE_SPAN_Y[0] - GUIDE_ENGAGE_MARGIN:
    raise AssertionError("pen carriage reaches the lower U guide at the top of travel")

# --- amplification wire 2 (rim -> stud eye) ---------------------------------------
# The run's top rides the rim groove's tangent at the wheel-axis height; it hangs
# plumb onto the stud's eye head, which stays below the rim at the top of travel.
if not math.isclose(PEN_WIRE_BOTTOM[1] + PEN_WIRE_LEN, WHEEL_BAR_Y, abs_tol=1e-9):
    raise AssertionError("pen-wire top drifted from the wheel-axis tangent height")
_RIM_R = WHEEL_RIM_OUTER_DIA / 2.0
_RIM_LOW_Y_AT_WIRE = WHEEL_BAR_Y - math.sqrt(
    _RIM_R**2 - (WHEEL_X - PEN_WIRE_BOTTOM[0]) ** 2
)
if STUD_HEAD_TOP_Y[1] > _RIM_LOW_Y_AT_WIRE - 2.0:
    raise AssertionError(
        "adjuster stud eye reaches the magnifying-wheel rim at the top of travel"
    )

# --- M6.10 fastener ----------------------------------------------------------
# Pen-hanger screw from BEHIND the bar. Its under-head frame follows the shared
# wheel-bar back face; the exact stock shank passes through the 9 mm bar, the
# 3 mm strap's clearance hole and the locknut on the strap front, then stands
# clear of the magnifying-wheel rim.
BAR_BACK_Z = HANGER_POS[2] + max(HANGER_STRAP_Z) + WHEEL_BAR_DEPTH
HANGER_SCREW_POS = (
    HANGER_POS[0] + HANGER_HOLE_XY[0],
    HANGER_POS[1] + HANGER_HOLE_XY[1],
    BAR_BACK_Z,
)
assert math.isclose(HANGER_SCREW_POS[0], HANGER_SCREW_MACHINE_X, abs_tol=1e-9)
assert math.isclose(HANGER_SCREW_POS[1], WHEEL_BAR_Y, abs_tol=1e-9)
HANGER_SCREW_TIP_Z = HANGER_SCREW_POS[2] - HANGER_SHANK_LEN
HANGER_STRAP_FRONT_Z = HANGER_POS[2] + min(HANGER_STRAP_Z)
# The locknut's frame spans local z 0..T (vn_pen_hanger_locknut_spec): placed
# un-rotated at the strap front less T, its z = T face bears on the strap.
HANGER_LOCKNUT_POS = (
    HANGER_SCREW_POS[0],
    HANGER_SCREW_POS[1],
    HANGER_STRAP_FRONT_Z - HANGER_LOCKNUT_T,
)
WHEEL_RIM_BACK_Z = WHEEL_MID_Z + WHEEL_RIM_AXIAL / 2.0
# Full thread standing past the nut's insert end, the tip chamfer excluded.
HANGER_THREAD_PAST_NUT = HANGER_LOCKNUT_POS[2] - HANGER_SCREW_TIP_Z - HANGER_TIP_CHAMFER
HANGER_TIP_TO_RIM = HANGER_SCREW_TIP_Z - WHEEL_RIM_BACK_Z
if HANGER_THREAD_PAST_NUT < HANGER_LOCKNUT_PAST_PITCHES * HANGER_THREAD_PITCH:
    raise AssertionError(
        "stock hanger screw stands under two full pitches past the locknut"
    )
if HANGER_TIP_TO_RIM <= 0.0:
    raise AssertionError("stock hanger screw tip reaches the magnifying-wheel rim")

# Every part that rides the rod: (stem, position, rows). Each is placed at its
# exact pose and LOCKED to the rod (a Lock mate freezes the full relative
# transform, so one mate per rider). Threaded riders (thumb screw, rod set
# screw, stud, nut) sit on their tapped-hole axes by construction -- the same
# block/rod stations the parts' hole features resolve to; an extra coaxial mate
# on top of the Lock would only over-constrain the solve.
RIDERS = (
    ("pn-pen-v-block", VBLOCK_POS, BLOCK_ROWS),
    ("vn-pen-marker", MARKER_POS, MARKER_ROWS),
    ("pn-pen-frame", FRAME_POS, FRAME_ROWS),
    ("vn-pen-set-screw", THUMB_SCREW_POS, THUMB_SCREW_ROWS),
    ("vn-pen-rod-set-screw", ROD_SET_SCREW_POS, ROD_SET_SCREW_ROWS),
    ("pn-pen-adjust-screw", STUD_POS, IDENTITY),
    ("vn-pen-adjust-nut", NUT_POS, NUT_ROWS),
    ("pn-pen-wire", PEN_WIRE_BOTTOM, IDENTITY),
)


async def build(adapter) -> dict[str, str]:
    # Flip seeds + free-DOF contract: cad/config/assemblies/<ASM_NAME>.yaml.
    activate_assembly_contract(ASM_NAME)
    # Reset the free-DOF manifest buffer before any *_driver(free_dof_key=...)
    # call: each freed DOF is recorded (never authored) and persisted below.
    reset_dof_manifest()
    check("create_assembly", await adapter.create_assembly())

    # The pen carriage slides vertically through the hanger's U guides: the
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
        adapter, "pn-pen-hanger", list(HANGER_POS), [0.0, 0.0, 0.0], IDENTITY
    )
    pen_rod = await place_component(
        adapter,
        "pn-pen-rod",
        list(PEN_ROD_POS),
        [0.0, 0.0, 0.0],
        IDENTITY,
        ground=False,
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

    for part, pos, rows in RIDERS:
        name = await place_component(
            adapter, part, list(pos), euler_from_rows(rows), rows, ground=False
        )
        await lock_mate(
            adapter,
            named_ref(f"Front Plane@{name}", "PLANE"),
            named_ref(f"Front Plane@{pen_rod}", "PLANE"),
            label=f"{part} locked to rod",
        )
        assert_component_placed(adapter, name, list(pos), rows)

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
        "vn-hanger-screw",
        list(HANGER_SCREW_POS),
        [0.0, 0.0, 0.0],
        IDENTITY,
        ground=False,
    )
    await coincident_mate(
        adapter,
        named_ref(f"ScrewAxis@{hanger_screw}", "AXIS"),
        named_ref(f"HangerScrewAxis@{hanger}", "AXIS"),
        label="hanger screw coaxial with strap clearance hole",
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

    # The locknut on the strap front: placed on the screw axis at its exact
    # pose and locked to the fixed hanger -- one Lock mate, like the riders;
    # a coaxial mate on top would only over-constrain the solve.
    hanger_locknut = await place_component(
        adapter,
        "vn-pen-hanger-locknut",
        list(HANGER_LOCKNUT_POS),
        [0.0, 0.0, 0.0],
        IDENTITY,
        ground=False,
    )
    await lock_mate(
        adapter,
        named_ref(f"Front Plane@{hanger_locknut}", "PLANE"),
        named_ref(f"Front Plane@{hanger}", "PLANE"),
        label="hanger locknut locked to hanger",
    )
    assert_component_placed(adapter, hanger_locknut, list(HANGER_LOCKNUT_POS), IDENTITY)

    # Certify the AS-BUILT model. Necessity only: the freed pen travel is
    # genuinely free; the lock-mated riders MUST read under-constrained WITH
    # the rod -- with the neutral preset the motion sweep reads got == want == 0
    # even if a rider were disconnected.
    assert_free_dof_necessity(
        adapter,
        1,
        required_stems=("pn-pen-rod", *(part for part, *_ in RIDERS)),
    )
    write_dof_manifest(ASM_NAME)
    check_no_interference(
        adapter,
        allowed_pairs=allowed_interference_pairs(ASM_NAME),
    )
    # Title-block identity for the assembly drawing (draw_pn_pen_assembly.py):
    # assembly_title_properties supplies the Title/Generator and TOL_* cells
    # finalize_drawing requires without consulting the part registry; material and
    # finish defer to the parts list, standard assembly-drawing practice.
    apply_custom_properties(
        adapter,
        {
            **assembly_title_properties(ASM_NAME),
            "Revision Description": "Initial release",
            "Material": "SEE PARTS LIST",
            "Material Specification": "SEE PARTS LIST",
            "Finish": "SEE PARTS LIST",
            "Quantity": "1",
            "Drawn By": DRAWN_BY,
        },
    )
    return await save_assembly_and_images(adapter, ASM_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
