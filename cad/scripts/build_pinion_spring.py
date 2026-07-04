r"""Reproduction script: pinion return spring (book ch. 25; 1 used).

The brass leaf spring that keeps the alignment-pinion drum disengaged by
default (p. 68-69 close-ups; video frames v4_pinion_013/018/019): a bent
strip whose foot lies flat on the base east of the BACK swing strap and
whose blade rises parallel to the parked strap, bearing on its east flank.
Engaging the drum swings the strap east into the blade and flexes it
further, so the leaf always pushes the swing back west to the disengaged
rest. PR7 (review item 10, page002_img01): the free end is NOT a curl --
near the top the strip takes a SUBTLE BEND BACK toward the L's base (a
small-radius kink turning ~20 deg west) and continues as a short flat.
The kink's convex crest (tangent parallel to the strap) is the parked
contact edge; when the strap swings east and flexes the leaf, the FLAT
above the kink lays against the flank -- no metal-on-metal slip on
engage. The FOOT points WEST, the SAME side the top bends back toward
(photo review follow-up): the L's interior angle -- foot ray to blade,
the open west side -- reads ~100 deg (leg at the strap's 12.38 lean =
102.4, within the photo's tolerance).

Layout (local frame = PRE-MIRROR machine frame - (9.04, base top 50.8),
sketch on the Front plane; the assembly's M6.8 chirality mirror maps it to
world via the ("z", 0.0) MIRROR_PLANE entry -- the part is an exact
mid-plane z-extrude): strip centreline path = 7.0 foot at y 0.8 pointing
WEST of the bend, r 2.0 bend (77.62 deg sweep), blade up-east at the
strap's parked 12.38 deg lean to t 32 along the strap axis, r 1.5 x
20 deg WEST kink, 6.0 flat to the free tip.
Thin mid-plane extrude, width 4.0 symmetric about z 0. The thin side is
ONE-sided and orientation-dependent (RevThinDir 0 -- see the SolidworksMCP
u-bracket tutorial); every assembly clearance is designed worst-case with
the full 0.8 on either side (build_drive_train_assembly SPRING_* asserts).

Dimensions: cad/config/dimensions.yaml "Chapter 25".

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pinion_spring.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    SketchDims,
    anchor_point_to_origin,
    define_circle,
    apply_material,
    check,
    dimension_between,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    set_sketch_direct_db,
    volume_check,
)

PART_NAME = "pinion-spring"
MATERIAL = "Brass"  # p.68: the leaf reads brass against the steel strap

THICK = 0.8  # strip thickness (photo-scaled vs the 5.0 strap)
WIDTH = 4.0  # strip width = extrude depth, inside the strap's z band
FOOT_LEN = 7.0  # flat screw-down foot on the base
R_BEND = 2.0  # foot-to-blade bend
R_KINK = 1.5  # the subtle bend-back near the top (PR7)
KINK_DEG = 20.0  # turn back west; the crest at the kink start is the
# parked contact edge, the flat above it the engaged contact face
FLAT_LEN = 6.0  # free flat above the kink
BLADE_TILT_DEG = 12.38  # must match build_drive_train STRAP_LEAN_DEG magnitude

# Machine-frame derivation (build_drive_train_assembly owns placement + the
# clearance asserts; local frame = machine - (9.04, 50.8)): the blade
# centreline runs parallel to the strap axis (pivot machine (1.16, 62.8)),
# offset 10.1 east = 9 strap half-width + 0.25 min air + 0.8 worst-case thin
# side, ending 36.0 along the axis from the pivot -- below the strap's top
# cap, clear of the lift rod and 2.0 off the 120T drum tips.
PIVOT_LX = 1.16 - 9.04  # strap pivot bore, local frame
PIVOT_LY = 62.8 - 50.8
AXIS_OFFSET = 10.1  # strap axis -> blade centreline, east
KINK_T = 32.0  # pivot -> kink start (the contact crest), along the strap axis
FOOT_Y = 0.8  # foot centreline above the base top (= THICK: flush if the
# thin side falls down, 0.8 float if up -- either passes the gates)
HOLE_DIA = 3.2  # foot screw hole (PR7 item 11): the black foot screw
# (build_foot_screw, O2.9 shank) bolts the foot down -- 0.4 rims in the
# 4-wide strip (the O4 slotted-screw shank cannot fit this strip)
HOLE_FROM_END = 2.2  # hole centre east of the foot's free (west) end

_TH = math.radians(BLADE_TILT_DEG)
_U = (math.sin(_TH), math.cos(_TH))  # up the blade, leaning east
_N = (math.cos(_TH), -math.sin(_TH))  # east normal of the strap axis

# Bend centre: on the blade line pulled R_BEND back WEST (the foot points
# west, the same side as the top bend-back), at foot height + R_BEND
# (tangent to the horizontal foot from above).
BEND_CY = FOOT_Y + R_BEND
BEND_CX = PIVOT_LX + (AXIS_OFFSET - R_BEND - (BEND_CY - PIVOT_LY) * _N[1]) / _N[0]
BEND_EXIT = (BEND_CX + R_BEND * _N[0], BEND_CY + R_BEND * _N[1])
FOOT_TAN = (BEND_CX, FOOT_Y)
FOOT_END = (BEND_CX - FOOT_LEN, FOOT_Y)
KINK_START = (
    PIVOT_LX + KINK_T * _U[0] + AXIS_OFFSET * _N[0],
    PIVOT_LY + KINK_T * _U[1] + AXIS_OFFSET * _N[1],
)  # = the parked contact crest (tangent parallel to the strap axis there)
KINK_C = (KINK_START[0] - R_KINK * _N[0], KINK_START[1] - R_KINK * _N[1])
# Arcs sweep CCW p1 -> p2: the kink turns WEST (heading angle increases),
# so p1 = the kink start, p2 = the exit onto the flat.
_A1 = math.atan2(_N[1], _N[0])  # kink start azimuth on its circle (-12.38)
_A2 = _A1 + math.radians(KINK_DEG)
KINK_EXIT = (KINK_C[0] + R_KINK * math.cos(_A2), KINK_C[1] + R_KINK * math.sin(_A2))
_FLAT_DIR = (
    math.sin(math.radians(BLADE_TILT_DEG - KINK_DEG)),
    math.cos(math.radians(BLADE_TILT_DEG - KINK_DEG)),
)  # 7.62 deg west of vertical
FLAT_TIP = (
    KINK_EXIT[0] + FLAT_LEN * _FLAT_DIR[0],
    KINK_EXIT[1] + FLAT_LEN * _FLAT_DIR[1],
)

# Centreline path length; the one-sided thin material rides R +/- t/2 on the
# arcs, so the exact volume depends on the wall side. Probed live (PR4, and
# re-probed with the PR7 kink): SolidWorks lays the wall on the RIGHT of the
# foot->tip traversal -- the passing east-foot volume decomposed as bend
# INSIDE its radius + kink OUTSIDE its own, which is exactly right-of-travel
# (the earlier "west of centreline" prose mislabelled it). With the foot now
# pointing WEST the traversal heads east then turns LEFT through both arcs,
# so right-of-travel puts the wall OUTSIDE both (and flush under the foot).
# A side flip fails this loud; the assembly asserts stay valid either way
# (designed worst-case both sides).
_BEND_SWEEP = math.radians(90.0 - BLADE_TILT_DEG)
_BLADE_LEN = math.hypot(KINK_START[0] - BEND_EXIT[0], KINK_START[1] - BEND_EXIT[1])
PATH_LEN = (FOOT_LEN + R_BEND * _BEND_SWEEP + _BLADE_LEN
            + R_KINK * math.radians(KINK_DEG) + FLAT_LEN)
_ARC_SIDE = (math.radians(KINK_DEG) + _BEND_SWEEP) * (THICK / 2.0) * THICK
VOLUME = (PATH_LEN * THICK + _ARC_SIDE) * WIDTH  # ~181.0 (right-of-travel wall)


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). The mm suffix is load-bearing --
    # INCH document, the equation manager reads bare numbers in doc units.
    # StripThickness/StripWidth are the thin-extrude feature parameters
    # (built with the literals); declared so a GUI edit sees the knobs.
    # Blade-tilt-dependent endpoint dims stay literal (no trig equations --
    # the equation manager rejects several dim bindings, probed 2026-07-02).
    await set_global(adapter, "FootLength", f"{FOOT_LEN}mm")
    await set_global(adapter, "BendRadius", f"{R_BEND}mm")
    await set_global(adapter, "KinkRadius", f"{R_KINK}mm")
    await set_global(adapter, "FlatLength", f"{FLAT_LEN}mm")
    await set_global(adapter, "StripThickness", f"{THICK}mm")
    await set_global(adapter, "StripWidth", f"{WIDTH}mm")

    # Open centreline path: foot -> bend -> blade -> kink -> flat, endpoints
    # merged at creation. Inference OFF: the foot endpoints sit near the origin.
    spring = SketchDims()
    check("create_sketch spring", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    foot = check(
        "add foot line",
        await adapter.add_line(FOOT_END[0], FOOT_END[1], FOOT_TAN[0], FOOT_TAN[1]),
    )
    bend = check(
        "add bend arc",
        await adapter.add_arc(
            BEND_CX, BEND_CY, FOOT_TAN[0], FOOT_TAN[1], BEND_EXIT[0], BEND_EXIT[1]
        ),
    )
    blade = check(
        "add blade line",
        await adapter.add_line(BEND_EXIT[0], BEND_EXIT[1], KINK_START[0], KINK_START[1]),
    )
    kink = check(
        "add kink arc",
        await adapter.add_arc(
            KINK_C[0], KINK_C[1], KINK_START[0], KINK_START[1], KINK_EXIT[0], KINK_EXIT[1]
        ),
    )
    flat = check(
        "add flat line",
        await adapter.add_line(KINK_EXIT[0], KINK_EXIT[1], FLAT_TIP[0], FLAT_TIP[1]),
    )
    set_sketch_direct_db(adapter, False)

    # Shape: the foot is horizontal, each arc is tangent to its neighbouring
    # line at the merged endpoint. Position: foot free end anchored to the
    # origin, foot length, both radii, blade top anchored (the two literal
    # tilt-dependent dims), and the flat tip's x fixing the kink sweep side.
    check("foot horizontal", await adapter.add_sketch_constraint(foot, None, "horizontal"))
    check("bend tangent foot", await adapter.add_sketch_constraint(bend, foot, "tangent"))
    check("bend tangent blade", await adapter.add_sketch_constraint(bend, blade, "tangent"))
    check("kink tangent blade", await adapter.add_sketch_constraint(kink, blade, "tangent"))
    check("kink tangent flat", await adapter.add_sketch_constraint(kink, flat, "tangent"))

    await anchor_point_to_origin(adapter, f"{foot}.start", *FOOT_END, "foot end")
    spring.record("FootEndX")
    spring.record("FootEndY")
    await dimension_between(
        adapter, f"{foot}.start", f"{foot}.end", "horizontal_distance", FOOT_LEN, "foot"
    )
    spring.record("FootLen", '"FootLength"')
    check(
        "bend radius",
        await adapter.add_sketch_dimension(bend, None, "radial", R_BEND),
    )
    spring.record("BendR", '"BendRadius"')
    await anchor_point_to_origin(adapter, f"{blade}.end", *KINK_START, "kink start")
    spring.record("KinkStartX")
    spring.record("KinkStartY")
    check(
        "kink radius",
        await adapter.add_sketch_dimension(kink, None, "radial", R_KINK),
    )
    spring.record("KinkR", '"KinkRadius"')
    check(
        "flat length",
        await adapter.add_sketch_dimension(flat, None, "linear", FLAT_LEN),
    )
    spring.record("FlatLen", '"FlatLength"')
    await dimension_between(
        adapter, f"{flat}.end", "origin", "horizontal_distance", abs(FLAT_TIP[0]), "flat tip"
    )
    spring.record("FlatTipX")

    await ensure_fully_defined(adapter, "spring sketch")
    check("exit_sketch spring", await adapter.exit_sketch())
    name_last_feature(adapter, "SpringProfile")
    drive_jobs = spring.apply(adapter, "SpringProfile")
    hole_jobs: list[tuple[str, str]] = []

    # Open profile -> thin mid-plane extrude: depth is the TOTAL width
    # (SolidWorks splits it), the 0.8 wall lands one-sided (side unknown).
    check(
        "extrude spring",
        await adapter.create_extrusion(
            ExtrusionParameters(
                depth=WIDTH,
                both_directions=True,
                thin_feature=True,
                thin_thickness=THICK,
            )
        ),
    )
    name_last_feature(adapter, "Spring")
    volume = await volume_check(adapter, "spring", VOLUME, 0.01 * VOLUME)

    # Foot screw hole (PR7 item 11): O3.2 through the foot strip near its
    # free end. Top sketch (u, v) -> (X, -Z); mid-plane cut spans whichever
    # y-band the one-sided thin wall landed in.
    hole = SketchDims()
    check("create_sketch foot hole", await adapter.create_sketch("Top"))
    await define_circle(
        adapter, FOOT_END[0] + HOLE_FROM_END, 0.0, HOLE_DIA / 2.0,
        "foot hole", dims=hole,
        names=("FootHoleX", "FootHoleZ", "FootHoleDia"),
        drives=(None, None, None),
    )
    await ensure_fully_defined(adapter, "foot hole sketch")
    check("exit_sketch foot hole", await adapter.exit_sketch())
    name_last_feature(adapter, "FootHoleProfile")
    hole_jobs = hole.apply(adapter, "FootHoleProfile")
    check(
        "cut foot hole",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=8.0 * THICK, both_directions=True)
        ),
    )
    name_last_feature(adapter, "FootHole")
    v_hole = math.pi * (HOLE_DIA / 2.0) ** 2 * THICK
    volume -= v_hole
    await volume_check(adapter, "foot hole", volume, 0.05 * v_hole)

    # Deferred drive equations, then re-check neutrality (each evaluates to
    # the as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs + hole_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven spring (equations neutral)", volume, 0.01 * VOLUME
    )

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
