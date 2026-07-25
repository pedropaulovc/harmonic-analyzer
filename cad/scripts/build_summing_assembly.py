r"""Reproduction script: summing subassembly (book ch. 18-19).

The head of the analyzer's output, where the 20 channel springs converge on
the summing lever, in machine coordinates (assembly origin = base origin;
base top y = 50.8; the output side is -Z). The lever rocks on a true knife
edge carried by two bearing supports, hung from the top frame by the
crossbar, and counter-balanced from above by the boss-hook / counter-
spring / gooseneck chain.

* knife-mount x2 -- the bearing supports, one per hex trunnion (|z| ~ 87).
* the lever hangs from the top frame's cast-in cross rib (frame.SLDASM).
* summing-lever -- rocks on the knife edge (Axis3 coincident to the support
  contact ridge); the part the channel + counter springs drive in the M6
  Motion study. The rock is the sub's single FREED operational DOF: its
  drive spec is recorded into the DOF manifest, never authored, so the
  saved model rocks on the knife edge.
* boss-hook (keyed to the lever's anchor eye) + counter-spring + gooseneck +
  gooseneck-screw -- the counter-balance hung from the east column. The post
  runs in a socket cast into the top frame, pinched by the square-head screw;
  there is no separate clamp block on the machine.

Cross-subassembly fits (checked at the top level): the channel springs
(channel.SLDASM) thread the summing-lever plate's O4.5 holes -- gated
analytically by build_channel_assembly._assert_plate_threading; the knife
mounts hang from the top frame's cross rib and the gooseneck runs in that same
casting's socket (frame.SLDASM).

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
    apply_custom_properties,
    apply_summary_info,
    check,
    log,
    run_build,
)
from _drawing_marks import DRAWN_BY
from _assembly import (
    angle_driver,
    assembly_title_properties,
    assert_free_dof_necessity,
    check_no_interference,
    coincident_mate,
    component_origin,
    distance_driver,
    lock_mate,
    named_ref,
    place_component,
    reset_dof_manifest,
    save_assembly_and_images,
    write_dof_manifest,
)
from _transforms import IDENTITY, ROT_Y_180, ROT_Y_POS90

ASM_NAME = "summing"

# --- machine anchors ---------------------------------------------------------
KNIFE = (-15.0, 1013.35)  # summing-lever knife-edge line (x, y), along Z:
# 20.25 below the top frame's cross-rib underside (1033.6). The drop is SET BY
# the tallest thing riding the magnifying-lever rod (which extends from this
# lever, so it hangs at the knife line): the magnifying clamp's backed-out
# thumb-screw head reaches rod + 3 + 12 + 5, so 20 alone would land its top
# EXACTLY on the rail underside -- a 0.00 graze the interference gate treats as
# a sliver. 20.25 buys the repo's standard margin; build_magnifier_assembly
# asserts it. (Before the 2026-07-24 re-anchor the drop was 20.0 flat, against
# a separate top-crossbar that stood 10.3 PROUD of the ring; the integral,
# flush-topped cross rib put its underside on the rail underside instead, so
# the whole summing group moved +23.35 while the frame top moved +33.9.)
from frame_anchors import COLUMN_X as _COLUMN_ABS_X, MID_Y, RAIL_HALF

COLUMN_X = -_COLUMN_ABS_X  # -203.8: east column

# --- knife bearing supports (build_knife_mount) -----------------------------
from summing_lever_spec import HEX_H, HEX_Z_INNER, HEX_Z_OUTER  # noqa: E402

KNIFE_CONTACT_Y = KNIFE[1] + HEX_H / 2.0  # knife-edge contact ridge line (1018.48)
HEX_Z_MID = (HEX_Z_INNER + HEX_Z_OUTER) / 2.0  # hex trunnion mid (87.06)

# --- counter-spring chain (boss_hook_geom / counter_spring_spec) ------------
# boss_hook_geom, NOT build_boss_hook: the part build's import closure carries
# boss_hook_spec's drawing prose, which would fold note edits into this
# assembly's full-rebuild recipe (codex #361).
from boss_hook_geom import ELBOW_R, ROD_DIA as HOOK_ROD_DIA, SHANK_RISE  # noqa: E402
from counter_spring_spec import (  # noqa: E402
    BOTTOM_HOOK_LEAD as CS_BOTTOM_LEAD,
    COIL_OD as CS_COIL_OD,
    WIRE_DIA as CS_WIRE_DIA,
)

# --- gooseneck socket (build_top_frame) -------------------------------------
GOOSENECK_SCREW_Y = MID_Y  # 1054.1  # the tapped passage is on the rail mid-height
GOOSENECK_SCREW_STANDOFF = RAIL_HALF  # outer rail face, |x| = COLUMN_X + 17

# The post SLIDES in its socket -- that is what the set screw is for -- so the
# gooseneck is set by the counter-spring hang, not by the frame: it rides the
# summing group (+23.35), NOT the frame top (+33.9). Pinch height is then just
# wherever the screw lands on the post.
GOOSENECK_Y = 1233.35

BOSS_HOOK_POS = (-90.5, 1023.35, 0.0)
SPRING_POS = (-95.0, 1075.45, 0.0)  # coil-bottom origin; ring at y 1035.45
# (0.1 lower left the hook rod poking past the ring inner top). The whole
# counter-spring chain rides the summing lever, so it moved with it (+23.35).


def _assert_counter_spring_hang() -> None:
    """Bottom ring around the boss-hook arm, a hair of air above the rod.

    Physical hanging would put the ring's inner top ON the rod (contact);
    we model a 0..0.5 air gap instead so the interference check stays
    zero (the original sense -- rod top ABOVE the ring inner top -- was
    inverted and encoded a 0.05 wire/rod overlap)."""
    ring_y = SPRING_POS[1] - CS_BOTTOM_LEAD  # 1035.7
    ring_inner_top = ring_y + (CS_COIL_OD - CS_WIRE_DIA) / 2.0 - CS_WIRE_DIA / 2.0
    rod_top = BOSS_HOOK_POS[1] + SHANK_RISE + ELBOW_R + HOOK_ROD_DIA / 2.0
    gap = ring_inner_top - rod_top
    if not 0.0 < gap < 0.5:
        raise RuntimeError(f"counter-spring ring/rod air gap {gap:.3f} not in (0, 0.5)")
    log(f"counter-spring hang: ring inner top {ring_inner_top:.2f}, rod top"
        f" {rod_top:.2f}, air gap {gap:.2f}")


async def build(adapter) -> dict[str, str]:
    _assert_counter_spring_hang()

    # Reset the free-DOF manifest buffer before any *_driver(free_dof_key=...)
    # call: each freed DOF is recorded (never authored) and persisted below.
    reset_dof_manifest()
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
    # (No crossbar component: the bar that hangs this lever is the top frame's
    # own cast-in CROSS RIB -- see build_top_frame. It lives in frame.SLDASM.)
    # Summing lever: knife-edge revolute = coincident axis-to-axis on the knife
    # line (the bore-bottom rocking edge) + a Front-plane axial distance,
    # leaving the rock DOF -- the sub's freed operational DOF (its drive spec
    # recorded into the DOF manifest, never authored). This is the part the
    # counter spring + channel springs drive in the M6 Motion study.
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
    # drive spec (an ANGLE between Right planes -- the boss "spin ref"
    # distance-to-Top is degenerate here, see above) is recorded into the DOF
    # manifest, never authored -- drag the lever and it rocks on the knife
    # edge, per the magnifier lever_rock idiom.
    await angle_driver(adapter, named_ref(f"Right Plane@{sl}", "PLANE"),
                       named_ref("Right Plane", "PLANE"), 0.0,
                       label="summing-lever rock PARK driver (freed in default build)",
                       verify=(sl, sl_o), free_dof_key="lever_rock")
    # Boss hook: rigidly rides the lever (locked), carrying the counter spring.
    # Keyed to the lever's anchor axis (Axis2, the summation-anchor eye the
    # counter spring hangs from at machine ~(-91, 990)) rather than the pivot
    # axis -- the lock just freezes the current pose, so the handle is chosen for
    # physical meaning (the eye), not the rock centre.
    # Ry(180): the boss-hook is a planar-XY wire form modeled with its open jaw
    # toward local +X; turned about Y it faces the machine crank side (-X),
    # hanging the counter-spring over the lever's anchor eye at ~(-91, 990).
    bh = await place_component(adapter, "boss-hook", list(BOSS_HOOK_POS),
                               [0.0, 180.0, 0.0], ROT_Y_180, ground=False)
    await lock_mate(adapter, named_ref(f"Axis1@{bh}", "AXIS"),
                    named_ref(f"Axis2@{sl}", "AXIS"), label="boss-hook keyed")
    # Ry(+90): the end loops land in the YZ plane, encircling the hook arm
    # (bottom) and the gooseneck pin (top) nail-through-ring style.
    await place_component(adapter, "counter-spring", list(SPRING_POS),
                          [0.0, 90.0, 0.0], ROT_Y_POS90)
    # Ry(180), like the boss-hook: the gooseneck's overhang arm reaches from
    # the east column toward the machine centre.
    await place_component(adapter, "gooseneck", [COLUMN_X, GOOSENECK_Y, 0.0],
                          [0.0, 180.0, 0.0], ROT_Y_180)
    # Square-head set screw pinching the post in its socket (ch. 19 p.45). There
    # is no clamp BLOCK: the socket and its tapped passage are cast into the top
    # frame, so the screw seats against that frame's outer rail face. The screw
    # is authored axis-along-+X (head behind the under-head plane, shank ahead of
    # it), so it seats on that -X outer face at IDENTITY.
    await place_component(adapter, "gooseneck-screw",
                          [COLUMN_X - GOOSENECK_SCREW_STANDOFF, GOOSENECK_SCREW_Y, 0.0],
                          [0.0, 0.0, 0.0], IDENTITY, label="gooseneck set screw")

    # Certify the AS-BUILT model. Necessity only: the freed lever rock is
    # genuinely free; the lock-mated boss-hook MUST read under-constrained
    # WITH it -- a grounded/fixed regression would freeze the counter-spring
    # anchor while the lever still swings.
    assert_free_dof_necessity(
        adapter, 1, required_stems=("summing-lever", "boss-hook"))
    write_dof_manifest(ASM_NAME)
    check_no_interference(adapter)
    # Title-block identity for the assembly drawing (draw_summing_assembly.py):
    # assembly_title_properties supplies the Title/Generator and TOL_* cells
    # finalize_drawing requires without consulting the part registry;
    # released component drawing (the BOM has no material/finish columns).
    apply_custom_properties(
        adapter,
        {
            **assembly_title_properties(ASM_NAME),
            # MHA-A## = assembly-drawing ids, beside the parts' MHA-### range
            # (a longer number overflows the DWG. NO. title-block cell).
            "Number": "MHA-A07",
            "Revision": "A",
            "Revision Description": "Initial release",
            "Material": "SEE COMPONENT DRAWINGS",
            "Material Specification": "SEE COMPONENT DRAWINGS",
            "Finish": "SEE COMPONENT DRAWINGS",
            "Quantity": "1",
            "Drawn By": DRAWN_BY,
        },
    )
    # The PART cell resolves the document summary Title; "summing assembly" (not
    # the bare stem) so the sheet identifies itself as an assembly drawing.
    apply_summary_info(adapter, title=f"{ASM_NAME} assembly")
    return await save_assembly_and_images(adapter, ASM_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
