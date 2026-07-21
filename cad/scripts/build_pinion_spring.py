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

Layout (sketch on the Front plane; the assembly seats the part at machine
(-9.04, base top 50.8) with a composed Ry(180), so part-local -x reads
machine WEST -- direction words below are MACHINE directions; the part is
an exact mid-plane z-extrude, so the Ry(180)'s z-flip is immaterial):
strip centreline path = 31.0 foot at y 0.8 pointing
WEST of the bend, r 2.0 bend (77.62 deg sweep), blade up-east at the
strap's parked 12.38 deg lean to t 32 along the strap axis, r 1.5 x
20 deg WEST kink, 2.0 flat to the free tip.
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
from _holes import blind_cut_dia_mm, wizard_holes
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _saved_part_guard import require_saved_drawing_properties

PART_NAME = "pinion-spring"
MATERIAL = "Brass"  # p.68: the leaf reads brass against the steel strap

# Primitive nominals come from the drawing spec (single source of truth shared
# with the manufacturing print).  Design rationale, unchanged:
#   FOOT_LEN  -- the flat screw-down foot points WEST and crosses UNDER the lift
#                rod and parked cam pin so its screw lands west of the moving rig.
#   KINK_DEG  -- the crest at the kink start is the parked contact edge; the flat
#                above it is the engaged contact face.
#   FLAT_LEN  -- short on purpose: the flat angles 20 deg WEST of the flank it
#                faces, so a longer flat dives INSIDE the parked strap flank (an
#                interference-gate hit); 2.0 leaves the tip 0.32 east of it.
#   BLADE_TILT_DEG -- must match build_drive_train STRAP_LEAN_DEG magnitude.
from pinion_spring_spec import (
    BLADE_TILT_DEG,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    FLAT_LEN,
    FOOT_LEN,
    ISOMETRIC_VIEW_NOTE,
    KINK_DEG,
    R_BEND,
    R_KINK,
    THICK,
    WIDTH,
)
from pinion_spring_geometry import (
    AXIS_OFFSET,
    BEND_CX,
    BEND_CY,
    BEND_EXIT,
    FLAT_TIP,
    FOOT_END,
    FOOT_TAN,
    FOOT_Y,
    HOLE_DIA,
    HOLE_FROM_END,
    HOLE_SPEC,
    KINK_C,
    KINK_EXIT,
    KINK_START,
    PIVOT_LX,
    PIVOT_LY,
    VOLUME,
    _A1,
    _A2,
    _BLADE_LEN,
)

_SAVED_DRAWING_PROPERTIES = (
    "Number",
    "Material Specification",
    "Finish",
    "Quantity",
    "Manufacturing Notes",
    "Isometric View Note",
)

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

    # Foot screw hole (PR7 item 11): ONE native Hole Wizard #4 clearance feature
    # (through-all along Y) through the foot strip near its free end, drilled
    # from the foot's underside (normal -Y). The foot centreline is at y=FOOT_Y;
    # the one-sided thin wall lands EITHER y 0..0.8 OR 0.8..1.6, so the -Y face
    # is within the 1.0 mm find_planar_face tolerance of the FOOT_Y point either
    # way, and the -Y normal filter disambiguates it from the top face. (If the
    # thin-wall side ever defeats face resolution it fails LOUD, not silently.)
    screw_dia = blind_cut_dia_mm(HOLE_SPEC)
    wizard_holes(
        adapter, HOLE_SPEC,
        [[FOOT_END[0] + HOLE_FROM_END, FOOT_Y, 0.0]],
        (0.0, -1.0, 0.0), "foot screw hole (#4 clearance)", name="FootHole",
    )
    v_hole = math.pi * (screw_dia / 2.0) ** 2 * THICK
    volume -= v_hole
    await volume_check(adapter, "foot hole", volume, 0.05 * v_hole)

    # Deferred drive equations, then re-check neutrality (each evaluates to
    # the as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven spring (equations neutral)", volume, 0.01 * VOLUME
    )

    # Manufacturing drawing support: mark exactly the print's dimensions and
    # stamp the make-critical title-block properties.
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": DRAWING_NOTES,
            "Isometric View Note": ISOMETRIC_VIEW_NOTE,
        },
    )
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(adapter, _SAVED_DRAWING_PROPERTIES)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
