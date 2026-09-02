r"""Reproduction script: summing subassembly (book ch. 18-19).

The head of the analyzer's output, where the 20 channel springs converge on
the summing lever, in machine coordinates (assembly origin = base origin;
base top y = 50.8; the output side is -Z). The lever rocks on a true knife
edge carried by two bearing supports, hung from the top-frame casting's
integral crossbar by two knife-hanger studs, and counter-balanced from
above by the boss-hook / counter-spring / gooseneck chain.

* knife-mount x2 -- the bearing supports, one per hex trunnion, centred on
  ``SUMMING_Z`` and separated by ``+/-HEX_Z_MID``.
* knife-hanger-stud x2 -- one per mount, on the mount centrelines: each
  threads 12 into the mount's 1/2-13 top tap and rises through the casting's
  integral-crossbar clearance hole; the integral washer + hex nut above the
  casting top face carry the hang.
* summing-lever -- rocks on the knife edge (Axis3 coincident to the support
  contact ridge); the part the channel + counter springs drive in the M6
  Motion study. The rock is the sub's single FREED operational DOF: its
  drive spec is recorded into the DOF manifest, never authored, so the
  saved model rocks on the knife edge.
* boss-hook (keyed to the lever's anchor eye) + counter-spring + gooseneck
  -- the counter-balance hung from the east column; the post is gripped by
  the top-frame rail hub's set screw (no separate clamp part).

Cross-subassembly fits (checked at the top level): the channel springs
(channel.SLDASM) thread the summing-lever plate's O4.5 holes -- gated
analytically by build_channel_assembly._assert_plate_threading; the knife-
hanger studs rise through the top-frame casting's integral crossbar (O13.49
close-clearance holes, frame.SLDASM); the gooseneck post drops through the
casting's rail-hub bore, gripped by its 1/4-20 set screw.

Fix-all strategy (M6.2): every structural component inserted at its exact
final transform and fixed; the summing lever + boss-hook are left free and
constrained by mates; transforms asserted by read-back; zero interference.

Dimensions: cad/DIMENSIONS.md ch. 18-19.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_summing_assembly.py
"""

from __future__ import annotations

import sys

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
from cone_pivot_post_installation import SUMMING_Z

ASM_NAME = "summing"

# --- machine anchors ---------------------------------------------------------
KNIFE = (-15.0, 979.7)  # summing-lever knife-edge line (x, y), along Z
# (Cascade A rederive: crossbar underside 1010 -> 999.7, whole chain -10.30)
COLUMN_X = -197.0  # east column (the crank side is machine -X)

# --- knife bearing supports (build_knife_mount) -----------------------------
from summing_lever_spec import HEX_H, HEX_Z_INNER, HEX_Z_OUTER  # noqa: E402

KNIFE_CONTACT_Y = KNIFE[1] + HEX_H / 2.0  # knife-edge contact ridge line (984.834)
HEX_Z_MID = (HEX_Z_INNER + HEX_Z_OUTER) / 2.0  # hex trunnion mid (87.06)

# --- knife-hanger studs (one per knife-mount) --------------------------------
# Part origin at the thread tip (bottom), axis +Y, inserted IDENTITY: each stud
# threads 12.0 into the mount's 1/2-13 top tap (seat at CASTING_UNDERSIDE_Y -
# MOUNT_GAP 0.25 = 999.45) and rises through the top-frame casting's integral-
# crossbar O13.49 close-clearance hole, spanning y 987.45..1057.1.
CASTING_UNDERSIDE_Y = 999.7  # top-frame casting underside (flush integral crossbar)
HANGER_STUD_Y = CASTING_UNDERSIDE_Y - 0.25 - 12.0  # 987.45 (gap + engagement)

# --- counter-spring chain (boss_hook_geom / counter_spring_spec) ------------
# boss_hook_geom, NOT build_boss_hook: the part build's import closure carries
# boss_hook_spec's drawing prose, which would fold note edits into this
# assembly's full-rebuild recipe (codex #361).
from boss_hook_geom import ELBOW_R, ROD_DIA as HOOK_ROD_DIA, SHANK_RISE  # noqa: E402
from counter_spring_spec import (  # noqa: E402
    BOTTOM_HOOK_LEAD as CS_BOTTOM_LEAD,
    COIL_BODY_LENGTH as CS_BODY_LENGTH,
    COIL_OD as CS_COIL_OD,
    HOOK_CL_RADIUS as CS_HOOK_R,
    TOP_HOOK_LEAD as CS_TOP_LEAD,
    WIRE_DIA as CS_WIRE_DIA,
)
# gooseneck_geom, NOT build_gooseneck, for the same reason (gooseneck_spec's
# DRAWING_NOTES would ride along in the closure).
from gooseneck_geom import (  # noqa: E402
    ARM_END_X as GN_ARM_END_X,
    ARM_Y as GN_ARM_Y,
    SCREW_HEAD_DIA as GN_HEAD_DIA,
    SCREW_HEAD_T as GN_HEAD_T,
    SCREW_SHANK_DIA as GN_SHANK_DIA,
    SCREW_SHANK_LEN as GN_SHANK_LEN,
    TUBE_DIA as GN_TUBE_DIA,
)

BOSS_HOOK_POS = (-90.5, 989.7, SUMMING_Z)  # rides the lever: Cascade A -10.3
SPRING_POS = (-95.0, 1041.8, SUMMING_Z)  # coil-bottom origin; ring at y 1001.8
# (the pre-shift 1052.0 hang left the hook rod poking 0.05 past the ring inner
# top; the +0.1 air-gap correction is preserved through the -10.3 shift)
GOOSENECK_POS = (COLUMN_X, 1210.0, SUMMING_Z)  # part origin = leg mid-height;
# placed Ry(180), so a part-frame x lands at machine COLUMN_X - x
SPRING_AIR_GAP_MIN = 0.25  # wire band / coil vs the screw head and the end face


def _assert_counter_spring_top_hang() -> None:
    """Top eye around the gooseneck's axial end screw, a hair of air above it.

    The eye (a 270-degree loop of mean radius CS_HOOK_R on the coil axis,
    CS_TOP_LEAD above the coil body, lying in the YZ plane after the Ry(+90)
    placement) encircles the screw shank that runs along the tube axis
    (machine -X after the Ry(180) placement). Three facts, all analytic:

    * VERTICAL -- the shank top sits 0..0.5 below the eye's inner top (the
      same air-gap convention as the bottom hang, so the interference gate
      stays zero while the geometry reads as hanging).
    * AXIAL -- the eye's wire band (+/- half a wire about the coil axis x)
      lies on the EXPOSED shank, at least SPRING_AIR_GAP_MIN clear of both
      the head shoulder and the arm end face.
    * COIL -- the coil body hangs under the eye and its top rises above the
      tube underside, so the coil's O.D. must also clear the end face in x
      by SPRING_AIR_GAP_MIN (the ch19 p.45 photo shows exactly this: eye
      pressed toward the head, coil partly under the tube end).
    * HEAD -- the head is wider than the eye (it must retain a slack eye)
      and sits INSIDE the coil's x band, above the coil: where the two
      overlap in x its underside must clear the coil's top wire by
      SPRING_AIR_GAP_MIN; were the head ever outside the coil band, the x
      clearance would have to hold instead."""
    eye_y = SPRING_POS[1] + CS_BODY_LENGTH + CS_TOP_LEAD  # 1370.7
    eye_inner_r = CS_HOOK_R - CS_WIRE_DIA / 2.0  # 4.45
    shank_y = GOOSENECK_POS[1] + GN_ARM_Y  # 1373.3
    gap = (eye_y + eye_inner_r) - (shank_y + GN_SHANK_DIA / 2.0)
    if not 0.0 < gap < 0.5:
        raise RuntimeError(f"counter-spring eye/screw air gap {gap:.3f} not in (0, 0.5)")
    if shank_y - GN_SHANK_DIA / 2.0 <= eye_y - eye_inner_r:
        raise RuntimeError("counter-spring eye does not encircle the screw shank")

    end_face_x = GOOSENECK_POS[0] - GN_ARM_END_X  # -101.75
    head_x = GOOSENECK_POS[0] - (GN_ARM_END_X - GN_SHANK_LEN)  # -93.75
    eye_x = SPRING_POS[0]  # -95: coil axis, the eye's plane
    band = CS_WIRE_DIA / 2.0
    to_head = head_x - (eye_x + band)
    to_end_face = (eye_x - band) - end_face_x
    if min(to_head, to_end_face) < SPRING_AIR_GAP_MIN:
        raise RuntimeError(
            f"counter-spring eye band off the exposed shank: head {to_head:.3f},"
            f" end face {to_end_face:.3f} (min {SPRING_AIR_GAP_MIN})"
        )

    coil_top = SPRING_POS[1] + CS_BODY_LENGTH  # 1367.1 (helix centreline)
    tube_bottom = shank_y - GN_TUBE_DIA / 2.0  # 1365.3
    coil_x0, coil_x1 = eye_x - CS_COIL_OD / 2.0, eye_x + CS_COIL_OD / 2.0
    coil_to_end_face = coil_x0 - end_face_x
    if coil_top > tube_bottom and coil_to_end_face < SPRING_AIR_GAP_MIN:
        raise RuntimeError(
            f"counter-spring coil under the tube end: clearance {coil_to_end_face:.3f}"
            f" (coil top {coil_top:.2f} above tube underside {tube_bottom:.2f})"
        )

    if GN_HEAD_DIA <= 2.0 * eye_inner_r:
        raise RuntimeError(
            f"screw head O{GN_HEAD_DIA} cannot retain the O{2.0 * eye_inner_r:.1f} eye"
        )
    head_x0, head_x1 = head_x, head_x + GN_HEAD_T  # -93.75..-91.75
    head_bottom = shank_y - GN_HEAD_DIA / 2.0  # 1368.3
    coil_wire_top = coil_top + band  # 1368.0
    head_in_coil_band = head_x0 < coil_x1 and head_x1 > coil_x0
    head_to_coil = (
        head_bottom - coil_wire_top
        if head_in_coil_band
        else min(abs(head_x0 - coil_x1), abs(coil_x0 - head_x1))
    )
    if head_to_coil < SPRING_AIR_GAP_MIN:
        raise RuntimeError(
            f"screw head into the coil: clearance {head_to_coil:.3f}"
            f" ({'vertical' if head_in_coil_band else 'axial'}, min {SPRING_AIR_GAP_MIN})"
        )
    log(
        f"counter-spring top hang: eye inner top {eye_y + eye_inner_r:.2f}, shank top"
        f" {shank_y + GN_SHANK_DIA / 2.0:.2f}, air gap {gap:.2f}; band to head"
        f" {to_head:.2f}, to end face {to_end_face:.2f}; coil to end face"
        f" {coil_to_end_face:.2f}; head underside to coil wire {head_to_coil:.2f}"
    )


def _assert_counter_spring_hang() -> None:
    """Bottom ring around the boss-hook arm, a hair of air above the rod.

    Physical hanging would put the ring's inner top ON the rod (contact);
    we model a 0..0.5 air gap instead so the interference check stays
    zero (the original sense -- rod top ABOVE the ring inner top -- was
    inverted and encoded a 0.05 wire/rod overlap)."""
    ring_y = SPRING_POS[1] - CS_BOTTOM_LEAD  # 1001.8
    ring_inner_top = ring_y + (CS_COIL_OD - CS_WIRE_DIA) / 2.0 - CS_WIRE_DIA / 2.0
    rod_top = BOSS_HOOK_POS[1] + SHANK_RISE + ELBOW_R + HOOK_ROD_DIA / 2.0
    gap = ring_inner_top - rod_top
    if not 0.0 < gap < 0.5:
        raise RuntimeError(f"counter-spring ring/rod air gap {gap:.3f} not in (0, 0.5)")
    log(
        f"counter-spring hang: ring inner top {ring_inner_top:.2f}, rod top"
        f" {rod_top:.2f}, air gap {gap:.2f}"
    )


async def build(adapter) -> dict[str, str]:
    _assert_counter_spring_hang()
    _assert_counter_spring_top_hang()

    # Reset the free-DOF manifest buffer before any *_driver(free_dof_key=...)
    # call: each freed DOF is recorded (never authored) and persisted below.
    reset_dof_manifest()
    check("create_assembly", await adapter.create_assembly())

    # Two knife bearing supports, one per hex trunnion (overhanging the lever
    # body at SUMMING_Z +/- HEX_Z_MID). The front support is FIRST so the auto-fixed assembly
    # seed is structure, not the mated summing lever. Each support's circular
    # bore is much larger than the hex, so only the trunnion's top vertex line
    # (the knife edge) nears the upper inner wall. The named "knife axis" is that
    # contact ridge line; the lever's Axis3 (hex ridge) mates coincident to it.
    km = await place_component(
        adapter,
        "knife-mount",
        [KNIFE[0], KNIFE_CONTACT_Y, SUMMING_Z + HEX_Z_MID],
        [0.0, 0.0, 0.0],
        IDENTITY,
        label="knife-mount (front)",
    )
    await place_component(
        adapter,
        "knife-mount",
        [KNIFE[0], KNIFE_CONTACT_Y, SUMMING_Z - HEX_Z_MID],
        [0.0, 0.0, 0.0],
        IDENTITY,
        label="knife-mount (back)",
    )
    # Knife-hanger studs, one per mount on the mount centrelines: each threads
    # 12 into the mount's 1/2-13 top tap (seat 999.45) and rises through the
    # casting's integral crossbar (band 999.7..1036.2, O13.49 close clearance);
    # the integral washer + hex nut seat on the casting top face 1036.2 and
    # carry the hang (stud spans y 987.45..1057.1).
    await place_component(
        adapter,
        "knife-hanger-stud",
        [KNIFE[0], HANGER_STUD_Y, SUMMING_Z + HEX_Z_MID],
        [0.0, 0.0, 0.0],
        IDENTITY,
        label="knife-hanger-stud (front)",
    )
    await place_component(
        adapter,
        "knife-hanger-stud",
        [KNIFE[0], HANGER_STUD_Y, SUMMING_Z - HEX_Z_MID],
        [0.0, 0.0, 0.0],
        IDENTITY,
        label="knife-hanger-stud (back)",
    )
    # Summing lever: knife-edge revolute = coincident axis-to-axis on the knife
    # line (the bore-bottom rocking edge) + a Front-plane axial distance,
    # leaving the rock DOF -- the sub's freed operational DOF (its drive spec
    # recorded into the DOF manifest, never authored). This is the part the
    # counter spring + channel springs drive in the M6 Motion study.
    sl = await place_component(
        adapter,
        "summing-lever",
        [KNIFE[0], KNIFE[1], SUMMING_Z],
        [0.0, 0.0, 0.0],
        IDENTITY,
        ground=False,
    )
    sl_o = component_origin(adapter, sl)
    # summing-lever axes (creation order): Axis1 = pivot (cylinder centre),
    # Axis2 = anchor, Axis3 = knife ridge (hex top vertex). The lever rocks on
    # the true knife edge: Axis3 mates coincident to the support's contact ridge
    # ("knife axis" = Axis1@knife-mount). Same pose as the cylinder-centre mate
    # (ridge is 5.13 above the centre, both collinear along Z), but the freed
    # rock DOF is now about the knife edge, per the bearing-support design.
    await coincident_mate(
        adapter,
        named_ref(f"Axis3@{sl}", "AXIS"),
        named_ref(f"Axis1@{km}", "AXIS"),
        label="summing-lever knife pivot",
        verify=(sl, sl_o),
    )
    # Axial Z-slide pinned by a Front-plane distance (value 0: the lever sits on
    # the assembly Front plane). Then the rock (Rz about the knife line) is the
    # suppressible snapshot driver -- an ANGLE between Right planes, NOT the
    # off-axis spin_driver: the boss "spin ref" sits directly -X of the pivot
    # (Δy=0), so its distance-to-Top is degenerate and over-defines, whereas the
    # angle is well-conditioned and (inserted on-solution) holds without a flip.
    await distance_driver(
        adapter,
        named_ref(f"Front Plane@{sl}", "PLANE"),
        named_ref("Front Plane", "PLANE"),
        abs(sl_o[2]),
        label="summing-lever axial",
        verify=(sl, sl_o),
    )
    # The rock about the knife line is the sub's FREED operational DOF: its
    # drive spec (an ANGLE between Right planes -- the boss "spin ref"
    # distance-to-Top is degenerate here, see above) is recorded into the DOF
    # manifest, never authored -- drag the lever and it rocks on the knife
    # edge, per the magnifier lever_rock idiom.
    await angle_driver(
        adapter,
        named_ref(f"Right Plane@{sl}", "PLANE"),
        named_ref("Right Plane", "PLANE"),
        0.0,
        label="summing-lever rock PARK driver (freed in default build)",
        verify=(sl, sl_o),
        free_dof_key="lever_rock",
    )
    # Boss hook: rigidly rides the lever (locked), carrying the counter spring.
    # Keyed to the lever's anchor axis (Axis2, the summation-anchor eye the
    # counter spring hangs from at machine ~(-91, 979.7)) rather than the pivot
    # axis -- the lock just freezes the current pose, so the handle is chosen
    # for physical meaning (the eye), not the rock centre.
    # Ry(180): the boss-hook is a planar-XY wire form modeled with its open jaw
    # toward local +X; turned about Y it faces the machine crank side (-X),
    # hanging the counter-spring over the lever's anchor eye at ~(-91, 979.7).
    bh = await place_component(
        adapter,
        "boss-hook",
        list(BOSS_HOOK_POS),
        [0.0, 180.0, 0.0],
        ROT_Y_180,
        ground=False,
    )
    await lock_mate(
        adapter,
        named_ref(f"Axis1@{bh}", "AXIS"),
        named_ref(f"Axis2@{sl}", "AXIS"),
        label="boss-hook keyed",
    )
    # Ry(+90): the end loops land in the YZ plane, encircling the hook arm
    # (bottom) and the gooseneck's axial end-screw shank (top)
    # nail-through-ring style.
    await place_component(
        adapter, "counter-spring", list(SPRING_POS), [0.0, 90.0, 0.0], ROT_Y_POS90
    )
    # Ry(180), like the boss-hook: the gooseneck's overhang arm reaches from
    # the east column toward the machine centre. The post is held in the
    # top-frame casting's rail-hub bore by its 1/4-20 set screw
    # (frame.SLDASM) -- there is no separate clamp part.
    await place_component(
        adapter,
        "gooseneck",
        list(GOOSENECK_POS),
        [0.0, 180.0, 0.0],
        ROT_Y_180,
    )

    # Certify the AS-BUILT model. Necessity only: the freed lever rock is
    # genuinely free; the lock-mated boss-hook MUST read under-constrained
    # WITH it -- a grounded/fixed regression would freeze the counter-spring
    # anchor while the lever still swings.
    assert_free_dof_necessity(adapter, 1, required_stems=("summing-lever", "boss-hook"))
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
