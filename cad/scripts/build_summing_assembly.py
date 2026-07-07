r"""Reproduction script: summing subassembly (book ch. 18-19).

The head of the analyzer's output, where the 20 channel springs converge on
the summing lever, in machine coordinates (assembly origin = base origin;
base top y = 50.8; the output side is -Z). The lever rocks on a true knife
edge carried by two bearing supports, hung from the top frame by the
crossbar, and counter-balanced from above by the boss-hook / counter-
spring / gooseneck chain.

* knife-mount x2 -- the bearing supports, one per hex trunnion (|z| ~ 87).
* top-crossbar -- hangs the lever from the top-frame ring.
* summing-lever -- rocks on the knife edge (Axis3 coincident to the support
  contact ridge); the part the channel + counter springs drive in the M6
  Motion study. The rock is the sub's single FREED operational DOF: in the
  default `free` build (cad/config/machine/build_lock.yaml) its park driver
  is DEFERRED (recorded, not authored), so the saved model rocks on the
  knife edge; `locked` authors it engaged (see ``LOCK``).
* boss-hook (keyed to the lever's anchor eye) + counter-spring + gooseneck +
  gooseneck-clamp -- the counter-balance hung from the east column.

Cross-subassembly fits (checked at the top level): the channel springs
(channel.SLDASM) thread the summing-lever plate's O4.5 holes -- gated
analytically by build_channel_assembly._assert_plate_threading; the crossbar
ends face-flush on the top-frame ring rail inner faces (frame.SLDASM) and the
gooseneck-clamp wraps the east column.

Fix-all strategy (M6.2): every structural component inserted at its exact
final transform and fixed; the summing lever + boss-hook are left free and
constrained by mates; transforms asserted by read-back; zero interference.

Dimensions: cad/DIMENSIONS.md ch. 18-19.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_summing_assembly.py
"""

from __future__ import annotations

import sys

import _config
from _common import (
    check,
    log,
    run_build,
)
from _assembly import (
    angle_driver,
    assert_expected_free_dof,
    assert_free_dof_necessity,
    check_no_interference,
    coincident_mate,
    component_origin,
    distance_driver,
    is_locked_build,
    lock_mate,
    named_ref,
    place_component,
    save_assembly_and_images,
    set_park_defer,
    write_park_specs,
)
from _transforms import IDENTITY, ROT_Y_POS90

ASM_NAME = "summing"

# Build mode (cad/config/machine/build_lock.yaml). `free` (default) leaves the
# lever's knife-edge rock -- the sub's single operational DOF -- UNLOCKED: its
# park driver is DEFERRED (recorded, not authored), so the saved model is a
# working kinematic model: drag the lever and it rocks on the knife edge, the
# boss-hook riding it. `locked` authors the park driver engaged for a
# fully-defined reproducible snapshot. The literal accessor tokenises to
# machine/build_lock.yaml in the doit/cache digest.
LOCK = is_locked_build(_config.machine("build_lock", "summing"))

# --- machine anchors ---------------------------------------------------------
KNIFE = (15.0, 990.0)  # summing-lever knife-edge line (x, y), along Z
COLUMN_X = 197.0

# --- knife bearing supports (build_knife_mount) -----------------------------
from build_summing_lever import HEX_H, HEX_Z_INNER, HEX_Z_OUTER  # noqa: E402

KNIFE_CONTACT_Y = KNIFE[1] + HEX_H / 2.0  # knife-edge contact ridge line (995.13)
HEX_Z_MID = (HEX_Z_INNER + HEX_Z_OUTER) / 2.0  # hex trunnion mid (87.06)

# --- counter-spring chain (build_boss_hook / build_counter_spring) ----------
from build_boss_hook import ELBOW_R, ROD_DIA as HOOK_ROD_DIA, SHANK_RISE  # noqa: E402
from build_counter_spring import (  # noqa: E402
    BOTTOM_LEAD as CS_BOTTOM_LEAD,
    COIL_OD as CS_COIL_OD,
    WIRE_DIA as CS_WIRE_DIA,
)

BOSS_HOOK_POS = (90.5, 1000.0, 0.0)
SPRING_POS = (95.0, 1052.1, 0.0)  # coil-bottom origin; ring at y 1012.1
# (1052.0 left the hook rod poking 0.05 past the ring inner top)


def _assert_counter_spring_hang() -> None:
    """Bottom ring around the boss-hook arm, a hair of air above the rod.

    Physical hanging would put the ring's inner top ON the rod (contact);
    we model a 0..0.5 air gap instead so the interference check stays
    zero (the original sense -- rod top ABOVE the ring inner top -- was
    inverted and encoded a 0.05 wire/rod overlap)."""
    ring_y = SPRING_POS[1] - CS_BOTTOM_LEAD  # 1012.1
    ring_inner_top = ring_y + (CS_COIL_OD - CS_WIRE_DIA) / 2.0 - CS_WIRE_DIA / 2.0
    rod_top = BOSS_HOOK_POS[1] + SHANK_RISE + ELBOW_R + HOOK_ROD_DIA / 2.0
    gap = ring_inner_top - rod_top
    if not 0.0 < gap < 0.5:
        raise RuntimeError(f"counter-spring ring/rod air gap {gap:.3f} not in (0, 0.5)")
    log(f"counter-spring hang: ring inner top {ring_inner_top:.2f}, rod top"
        f" {rod_top:.2f}, air gap {gap:.2f}")


async def build(adapter) -> dict[str, str]:
    _assert_counter_spring_hang()

    # `free` (default) DEFERS the freed-DOF park driver (records, does not
    # author); `locked` authors it engaged. Set before the *_driver call below.
    set_park_defer(not LOCK)
    check("create_assembly", await adapter.create_assembly())

    # Two knife bearing supports, one per hex trunnion (overhanging the lever
    # body at |z| ~ 87). The front support is FIRST so the auto-fixed assembly
    # seed is structure, not the mated summing lever. Each support's circular
    # bore is much larger than the hex, so only the trunnion's top vertex line
    # (the knife edge) nears the upper inner wall. The named "knife axis" is that
    # contact ridge line; the lever's Axis3 (hex ridge) mates coincident to it.
    km = await place_component(adapter, "knife-mount",
                               [KNIFE[0], KNIFE_CONTACT_Y, HEX_Z_MID],
                               [0.0, 0.0, 0.0], IDENTITY, label="knife-mount (front)")
    await place_component(adapter, "knife-mount",
                          [KNIFE[0], KNIFE_CONTACT_Y, -HEX_Z_MID],
                          [0.0, 0.0, 0.0], IDENTITY, label="knife-mount (back)")
    # Crossbar band y 1010..1051: 0.5 above the summing-lever tube top
    # (1009.5), ends face-flush on the ring rail inner faces (y to 1040.7),
    # stud pokes 14 above for the nut seat.
    await place_component(adapter, "top-crossbar", [KNIFE[0], 1010.0, 0.0],
                          [0.0, 0.0, 0.0], IDENTITY)
    # Summing lever: knife-edge revolute = coincident axis-to-axis on the knife
    # line (the bore-bottom rocking edge) + a Front-plane axial distance,
    # leaving the rock DOF -- the sub's freed operational DOF (park driver
    # deferred in the default `free` build, authored engaged in `locked`).
    # This is the part the counter spring + channel springs drive in the M6
    # Motion study.
    sl = await place_component(adapter, "summing-lever", [KNIFE[0], KNIFE[1], 0.0],
                               [0.0, 0.0, 0.0], IDENTITY, ground=False)
    sl_o = component_origin(adapter, sl)
    # summing-lever axes (creation order): Axis1 = pivot (cylinder centre),
    # Axis2 = anchor, Axis3 = knife ridge (hex top vertex). The lever rocks on
    # the true knife edge: Axis3 mates coincident to the support's contact ridge
    # ("knife axis" = Axis1@knife-mount). Same pose as the cylinder-centre mate
    # (ridge is 5.13 above the centre, both collinear along Z), but the freed
    # rock DOF is now about the knife edge, per the bearing-support design.
    await coincident_mate(adapter, named_ref(f"Axis3@{sl}", "AXIS"),
                          named_ref(f"Axis1@{km}", "AXIS"),
                          label="summing-lever knife pivot", verify=(sl, sl_o))
    # Axial Z-slide pinned by a Front-plane distance (value 0: the lever sits on
    # the assembly Front plane). Then the rock (Rz about the knife line) is the
    # suppressible snapshot driver -- an ANGLE between Right planes, NOT the
    # off-axis spin_driver: the boss "spin ref" sits directly -X of the pivot
    # (Δy=0), so its distance-to-Top is degenerate and over-defines, whereas the
    # angle is well-conditioned and (inserted on-solution) holds without a flip.
    await distance_driver(adapter, named_ref(f"Front Plane@{sl}", "PLANE"),
                          named_ref("Front Plane", "PLANE"), abs(sl_o[2]),
                          label="summing-lever axial", verify=(sl, sl_o))
    # The rock about the knife line is the sub's FREED operational DOF: its
    # park driver (an ANGLE between Right planes -- the boss "spin ref"
    # distance-to-Top is degenerate here, see above) is DEFERRED in the default
    # `free` build (recorded, not authored -- drag the lever and it rocks on
    # the knife edge, per the magnifier lever_rock idiom), authored engaged in
    # a `locked` build.
    await angle_driver(adapter, named_ref(f"Right Plane@{sl}", "PLANE"),
                       named_ref("Right Plane", "PLANE"), 0.0,
                       label="summing-lever rock PARK driver (freed in default build)",
                       verify=(sl, sl_o), free_dof_key="lever_rock")
    # Boss hook: rigidly rides the lever (locked), carrying the counter spring.
    # Keyed to the lever's anchor axis (Axis2, the summation-anchor eye the
    # counter spring hangs from at machine ~(-91, 990)) rather than the pivot
    # axis -- the lock just freezes the current pose, so the handle is chosen for
    # physical meaning (the eye), not the rock centre.
    bh = await place_component(adapter, "boss-hook", list(BOSS_HOOK_POS),
                               [0.0, 0.0, 0.0], IDENTITY, ground=False)
    await lock_mate(adapter, named_ref(f"Axis1@{bh}", "AXIS"),
                    named_ref(f"Axis2@{sl}", "AXIS"), label="boss-hook keyed")
    # Ry(+90): the end loops land in the YZ plane, encircling the hook arm
    # (bottom) and the gooseneck pin (top) nail-through-ring style.
    await place_component(adapter, "counter-spring", list(SPRING_POS),
                          [0.0, 90.0, 0.0], ROT_Y_POS90)
    await place_component(adapter, "gooseneck", [COLUMN_X, 1210.0, 0.0],
                          [0.0, 0.0, 0.0], IDENTITY)
    await place_component(adapter, "gooseneck-clamp", [COLUMN_X, 1040.7, 0.0],
                          [0.0, 0.0, 0.0], IDENTITY)

    # Certify the AS-BUILT model. free -> necessity only (the freed lever rock
    # is genuinely free; the lock-mated boss-hook reads under-constrained WITH
    # it); locked -> strict 0-DOF.
    if LOCK:
        await assert_expected_free_dof(adapter, 0)
    else:
        assert_free_dof_necessity(adapter, 1, required_stems=("summing-lever",))
    write_park_specs(ASM_NAME)
    check_no_interference(adapter)
    return await save_assembly_and_images(adapter, ASM_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
