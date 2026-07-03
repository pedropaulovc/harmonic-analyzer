r"""Reproduction script: pinion return spring (book ch. 25; 1 used).

The brass leaf spring that keeps the alignment-pinion drum disengaged by
default (p. 68-69 close-ups; video frames v4_pinion_013/018/019): a bent
strip whose foot lies flat on the base east of the BACK swing strap and
whose blade rises parallel to the parked strap, bearing on its east flank.
Engaging the drum swings the strap east into the blade and flexes it
further, so the leaf always pushes the swing back west to the disengaged
rest. The free tip rolls east in a 150 deg curl so the strap flank meets a
smooth tangent face through the whole swing.

Layout (local frame = PRE-MIRROR machine frame - (9.04, base top 50.8),
sketch on the Front plane; the assembly's M6.8 chirality mirror maps it to
world via the ("z", 0.0) MIRROR_PLANE entry -- the part is an exact
mid-plane z-extrude): strip centreline path = 7.0 foot at y 0.8, r 2.0
bend, blade up-east at the strap's parked 12.38 deg lean, r 2.0 x 150 deg
east curl.
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
R_CURL = 2.0  # free-tip curl, rolled EAST (away from the strap)
CURL_SWEEP_DEG = 150.0
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
BLADE_TOP_T = 36.0  # pivot -> blade top, along the strap axis
FOOT_Y = 0.8  # foot centreline above the base top (= THICK: flush if the
# thin side falls down, 0.8 float if up -- either passes the gates)

_TH = math.radians(BLADE_TILT_DEG)
_U = (math.sin(_TH), math.cos(_TH))  # up the blade, leaning east
_N = (math.cos(_TH), -math.sin(_TH))  # east normal of the strap axis

# Bend centre: on the blade line pushed another R_BEND east, at foot height
# + R_BEND (tangent to the horizontal foot from above).
BEND_CY = FOOT_Y + R_BEND
BEND_CX = PIVOT_LX + (AXIS_OFFSET + R_BEND - (BEND_CY - PIVOT_LY) * _N[1]) / _N[0]
BEND_EXIT = (BEND_CX - R_BEND * _N[0], BEND_CY - R_BEND * _N[1])
FOOT_TAN = (BEND_CX, FOOT_Y)
FOOT_END = (BEND_CX + FOOT_LEN, FOOT_Y)
BLADE_TOP = (
    PIVOT_LX + BLADE_TOP_T * _U[0] + AXIS_OFFSET * _N[0],
    PIVOT_LY + BLADE_TOP_T * _U[1] + AXIS_OFFSET * _N[1],
)
CURL_C = (BLADE_TOP[0] + R_CURL * _N[0], BLADE_TOP[1] + R_CURL * _N[1])
# Arcs sweep CCW p1 -> p2. Blade top sits at 180 - tilt deg on the curl
# circle; the free tip trails it by the sweep.
_A2 = math.atan2(BLADE_TOP[1] - CURL_C[1], BLADE_TOP[0] - CURL_C[0])
_A1 = _A2 - math.radians(CURL_SWEEP_DEG)
CURL_TIP = (CURL_C[0] + R_CURL * math.cos(_A1), CURL_C[1] + R_CURL * math.sin(_A1))

# Centreline path length; the one-sided thin material rides R +/- t/2 on the
# arcs, so the exact volume is bimodal. Probed live 2026-07-03: SolidWorks
# puts the wall OUTSIDE the arc radii here -- west of the blade centreline,
# toward the strap (strap air 10.1 - 9 - 0.8 = 0.3) -- so the expected
# volume is the outer mode. A side flip (SW version change) fails this loud;
# the assembly asserts stay valid either way (designed worst-case both sides).
_BEND_SWEEP = math.radians(90.0 + BLADE_TILT_DEG)
_BLADE_LEN = math.hypot(BLADE_TOP[0] - BEND_EXIT[0], BLADE_TOP[1] - BEND_EXIT[1])
PATH_LEN = FOOT_LEN + R_BEND * _BEND_SWEEP + _BLADE_LEN + R_CURL * math.radians(CURL_SWEEP_DEG)
_ARC_SIDE = (_BEND_SWEEP + math.radians(CURL_SWEEP_DEG)) * (THICK / 2.0) * THICK
VOLUME = (PATH_LEN * THICK + _ARC_SIDE) * WIDTH  # ~193.1 (outer thin side)


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
    await set_global(adapter, "CurlRadius", f"{R_CURL}mm")
    await set_global(adapter, "StripThickness", f"{THICK}mm")
    await set_global(adapter, "StripWidth", f"{WIDTH}mm")

    # Open centreline path: foot -> bend -> blade -> curl, endpoints merged
    # at creation. Inference OFF: the foot endpoints sit near the origin.
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
            BEND_CX, BEND_CY, BEND_EXIT[0], BEND_EXIT[1], FOOT_TAN[0], FOOT_TAN[1]
        ),
    )
    blade = check(
        "add blade line",
        await adapter.add_line(BEND_EXIT[0], BEND_EXIT[1], BLADE_TOP[0], BLADE_TOP[1]),
    )
    curl = check(
        "add curl arc",
        await adapter.add_arc(
            CURL_C[0], CURL_C[1], CURL_TIP[0], CURL_TIP[1], BLADE_TOP[0], BLADE_TOP[1]
        ),
    )
    set_sketch_direct_db(adapter, False)

    # Shape: the foot is horizontal, each arc is tangent to its neighbouring
    # line at the merged endpoint. Position: foot free end anchored to the
    # origin, foot length, both radii, blade top anchored (the two literal
    # tilt-dependent dims), and the curl tip's x fixing the 150 deg sweep.
    check("foot horizontal", await adapter.add_sketch_constraint(foot, None, "horizontal"))
    check("bend tangent foot", await adapter.add_sketch_constraint(bend, foot, "tangent"))
    check("bend tangent blade", await adapter.add_sketch_constraint(bend, blade, "tangent"))
    check("curl tangent blade", await adapter.add_sketch_constraint(curl, blade, "tangent"))

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
    await anchor_point_to_origin(adapter, f"{blade}.end", *BLADE_TOP, "blade top")
    spring.record("BladeTopX")
    spring.record("BladeTopY")
    check(
        "curl radius",
        await adapter.add_sketch_dimension(curl, None, "radial", R_CURL),
    )
    spring.record("CurlR", '"CurlRadius"')
    await dimension_between(
        adapter, f"{curl}.start", "origin", "horizontal_distance", CURL_TIP[0], "curl tip"
    )
    spring.record("CurlTipX")

    await ensure_fully_defined(adapter, "spring sketch")
    check("exit_sketch spring", await adapter.exit_sketch())
    name_last_feature(adapter, "SpringProfile")
    drive_jobs = spring.apply(adapter, "SpringProfile")

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
    await volume_check(adapter, "spring", VOLUME, 0.01 * VOLUME)

    # Deferred drive equations, then re-check neutrality (each evaluates to
    # the as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven spring (equations neutral)", VOLUME, 0.01 * VOLUME
    )

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
