r"""Reproduction script: pinion return spring (book ch. 25; 1 used).

The leaf spring that holds the alignment-pinion drum disengaged by default
(p. 68-69 close-ups img01/img03/img04; video frames v4_pinion_013/018/019):
a phosphor-bronze strip screwed to the base EAST of the BACK swing strap,
outboard, rising in a blade that leans IN toward the strap and bears on its
east flank 23.0 up from the pivot, 5.0 below the arbor.  Gravity swings the
cluster east into mesh; the blade pushes the strap top back west onto the
parked cam, and the lever engages against it.

Re-derived 2026-09-24 (handoff dt-pinion-spring-rederive-20260924): the old
foot ran 35 WEST under the strap and the lift rod, read off img01's far-left
screw as west -- that side of img01 is the drum side, east.

Layout (sketch on the Front plane; the assembly seats the part at its machine
anchor, base top 50.8, with a composed Ry(180), so part-local +x reads machine
EAST -- direction words below are MACHINE directions; the part is an exact
mid-plane z-extrude, so the Ry(180)'s z-flip is immaterial): the strip's
INSIDE-surface path, drawn from the free tip down = a 2.0 flat, an R1.5 x 25
deg crest turning back west, the straight blade leaning BLADE_LEAN_DEG west of
vertical, an R2.0 bend, and the FOOT_LEN foot heading EAST to its free end.
Traced that way the one-sided thin wall lands right of travel -- west of the
blade, under the foot -- so the blade's west face is the contact face.  The
pad-merge volume gate proves the foot side and a west-extreme probe the
blade side.  Thin mid-plane extrude, WIDTH symmetric about z 0, plus a square
screw pad (PAD_WIDTH x PAD_LEN) at the foot's free end, cut with the flat
blank.

The model is the INSTALLED, parked shape (O2); the maker forms the free shape,
PRESET_DEG more bend (pinion_spring_geometry).

Dimensions: cad/config/dimensions.yaml "Chapter 25".

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pinion_spring.py
"""

from __future__ import annotations

import math
import sys

import _telemetry
from _common import (
    SketchDims,
    _early_bound,
    add_line_chain,
    anchor_point_to_origin,
    apply_material,
    check,
    define_rectilinear_chain,
    dimension_between,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_dimensions,
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
    apply_drawing_precision,
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
    set_dimension_symmetric_tolerance,
)
from _saved_part_guard import require_saved_drawing_properties
from pinion_spring_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    FLAT_LEN,
    FOOT_LEN,
    FORMED_DIMENSIONS,
    FORMED_TOLERANCE_MM,
    ISOMETRIC_VIEW_NOTE,
    PAD_LEN,
    PAD_WIDTH,
    PAD_Z,
    R_BEND,
    R_KINK,
    THICK,
    WIDTH,
)
from pinion_spring_geometry import (
    BEND_CX,
    BEND_CY,
    BEND_EXIT,
    FLAT_TIP,
    FOOT_END,
    FOOT_TAN,
    FOOT_Y,
    HOLE_DIA as HOLE_DIA,
    HOLE_FROM_END,
    HOLE_SPEC,
    KINK_C,
    KINK_EXIT,
    KINK_START,
    PAD_VOLUME,
    VOLUME,
)

PART_NAME = "pinion-spring"
# p.68: the leaf reads brass-coloured against the steel strap; C51000 phosphor
# bronze (O1).  SolidWorks' library has no C51000 entry: "Brass" stands in for
# the render colour and a mass within a few percent (8.5 vs 8.86 g/cc).
MATERIAL = "Brass"

# Primitive nominals come from the drawing spec (single source of truth shared
# with the manufacturing print). Design rationale:
#   FOOT_LEN -- the pad plus a short straight to the bend: the foot heads EAST,
#               outboard, away from the strap and the lift rod.
#   FLAT_LEN -- short on purpose: the flick turns back east, clear of the strap.

_SAVED_DRAWING_PROPERTIES = (
    "Number",
    "Material Specification",
    "Finish",
    "Quantity",
    "Manufacturing Notes",
    "Isometric View Note",
)


def _extreme_mm(adapter, direction: tuple[float, float, float], axis: int) -> float:
    """The solid's extreme coordinate (mm) along ``direction`` on ``axis``.

    ``IBody2::GetExtremePoint`` is exact (``GetBodyBox`` is approximate); the
    early-bound wrapper returns (ok, x, y, z) in metres.
    """
    doc = _early_bound(adapter.currentModel, "IPartDoc")
    bodies = adapter._attempt(lambda: doc.GetBodies2(0, False)) or []
    if len(bodies) != 1:
        raise RuntimeError(f"spring: expected one solid body, found {len(bodies)}")
    body = _early_bound(bodies[0], "IBody2")
    res = adapter._attempt(lambda: body.GetExtremePoint(*direction), default=None)
    if not res or len(res) < 4:
        raise RuntimeError("spring: GetExtremePoint failed")
    return float(res[1 + axis]) * 1000.0


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
    await set_global(adapter, "PadWidth", f"{PAD_WIDTH}mm")
    await set_global(adapter, "PadLength", f"{PAD_LEN}mm")

    # Open inside-surface path, drawn from the free tip DOWN: flat -> crest
    # (kink) -> blade -> bend -> foot, endpoints merged at creation.  The
    # traversal order sets the one-sided thin wall's side (right of travel:
    # west of the blade, under the foot).  Inference OFF: the foot endpoints
    # sit near the origin.  add_arc runs counter-clockwise start -> end.
    spring = SketchDims()
    check("create_sketch spring", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    flat = check(
        "add flat line",
        await adapter.add_line(FLAT_TIP[0], FLAT_TIP[1], KINK_EXIT[0], KINK_EXIT[1]),
    )
    kink = check(
        "add kink arc",
        await adapter.add_arc(
            KINK_C[0],
            KINK_C[1],
            KINK_EXIT[0],
            KINK_EXIT[1],
            KINK_START[0],
            KINK_START[1],
        ),
    )
    blade = check(
        "add blade line",
        await adapter.add_line(
            KINK_START[0], KINK_START[1], BEND_EXIT[0], BEND_EXIT[1]
        ),
    )
    bend = check(
        "add bend arc",
        await adapter.add_arc(
            BEND_CX, BEND_CY, BEND_EXIT[0], BEND_EXIT[1], FOOT_TAN[0], FOOT_TAN[1]
        ),
    )
    foot = check(
        "add foot line",
        await adapter.add_line(FOOT_TAN[0], FOOT_TAN[1], FOOT_END[0], FOOT_END[1]),
    )
    set_sketch_direct_db(adapter, False)

    # Shape: the foot is horizontal, each arc is tangent to its neighbouring
    # line at the merged endpoint. Position: foot free end anchored to the
    # origin, foot length, both radii, then the kink start (the two literal
    # lean-dependent dims) and the flat tip's x, which fixes the kink sweep.
    # The print baselines the formed profile from the foot's free end (policy
    # rule 7), so those locations dimension from foot.end, not the origin.
    check(
        "foot horizontal", await adapter.add_sketch_constraint(foot, None, "horizontal")
    )
    check(
        "bend tangent foot", await adapter.add_sketch_constraint(bend, foot, "tangent")
    )
    check(
        "bend tangent blade",
        await adapter.add_sketch_constraint(bend, blade, "tangent"),
    )
    check(
        "kink tangent blade",
        await adapter.add_sketch_constraint(kink, blade, "tangent"),
    )
    check(
        "kink tangent flat", await adapter.add_sketch_constraint(kink, flat, "tangent")
    )

    await anchor_point_to_origin(adapter, f"{foot}.end", *FOOT_END, "foot end")
    spring.record("FootEndX")
    spring.record("FootEndY")
    await dimension_between(
        adapter, f"{foot}.end", f"{foot}.start", "horizontal_distance", FOOT_LEN, "foot"
    )
    spring.record("FootLen", '"FootLength"')
    check(
        "bend radius",
        await adapter.add_sketch_dimension(bend, None, "radial", R_BEND),
    )
    spring.record("BendR", '"BendRadius"')
    await dimension_between(
        adapter,
        f"{foot}.end",
        f"{blade}.start",
        "horizontal_distance",
        FOOT_END[0] - KINK_START[0],
        "kink start from the free end",
    )
    spring.record("KinkH")
    await dimension_between(
        adapter,
        f"{foot}.end",
        f"{blade}.start",
        "vertical_distance",
        KINK_START[1] - FOOT_END[1],
        "kink start above the foot",
    )
    spring.record("KinkV")
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
        adapter,
        f"{foot}.end",
        f"{flat}.start",
        "horizontal_distance",
        FOOT_END[0] - FLAT_TIP[0],
        "flat tip from the free end",
    )
    spring.record("TipH")

    await ensure_fully_defined(adapter, "spring sketch")
    check("exit_sketch spring", await adapter.exit_sketch())
    name_last_feature(adapter, "SpringProfile")
    drive_jobs = spring.apply(adapter, "SpringProfile")

    # Open profile -> thin mid-plane extrude: depth is the TOTAL width
    # (SolidWorks splits it); the THICK wall lands one-sided, right of travel.
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
    drive_jobs += [
        (name_dimensions(adapter, "Spring", ["StripWidth"])[0], '"StripWidth"')
    ]
    volume = await volume_check(adapter, "spring", VOLUME, 0.01 * VOLUME)
    # Blade side: with the wall west of the path the crest's outer face is the
    # part's westmost point; on the wrong side it would read THICK further east
    # and every contact number would be off by the strip.
    west = _extreme_mm(adapter, (-1.0, 0.0, 0.0), axis=0)
    want = KINK_C[0] - (R_KINK + THICK)
    if abs(west - want) > 0.05:
        raise RuntimeError(
            f"spring wall on the wrong side: westmost x {west:.3f}, want {want:.3f}"
        )
    _telemetry.success(f"spring wall west of the blade: westmost x {west:.3f}")

    # Screw pad: a PAD_WIDTH x PAD_LEN square in from the foot's free end,
    # flush with the strip's aft edge, local -z (machine +z once placed
    # Ry(180)); the Top-plane sketch reads v = -z, so that edge is v = +W/2 and
    # the pad widens toward -v.  Extruded the strip thickness up from the foot's underside
    # (y 0, the gated side of the one-sided thin wall) so it merges with the
    # foot. The volume gate proves the merge: a pad on the wrong side would add
    # its whole footprint, not just the two wings beside the strip.
    pad = SketchDims()
    check("create_sketch pad", await adapter.create_sketch("Top"))
    x0 = FOOT_END[0]
    pad_pts = [
        (x0, WIDTH / 2.0),
        (x0 - PAD_LEN, WIDTH / 2.0),
        (x0 - PAD_LEN, WIDTH / 2.0 - PAD_WIDTH),
        (x0, WIDTH / 2.0 - PAD_WIDTH),
    ]
    pad_lines = await add_line_chain(adapter, pad_pts)
    await define_rectilinear_chain(
        adapter,
        pad_lines,
        pad_pts,
        anchor=0,
        label="pad",
        dims=pad,
        names=["PadLen", "PadWidth", "PadEndX", "PadEdgeZ"],
        drives=['"PadLength"', '"PadWidth"', None, '"StripWidth" / 2'],
    )
    await ensure_fully_defined(adapter, "pad sketch")
    check("exit_sketch pad", await adapter.exit_sketch())
    name_last_feature(adapter, "PadProfile")
    drive_jobs += pad.apply(adapter, "PadProfile")
    check(
        "extrude pad",
        await adapter.create_extrusion(ExtrusionParameters(depth=THICK)),
    )
    name_last_feature(adapter, "Pad")
    drive_jobs += [(name_dimensions(adapter, "Pad", ["PadThk"])[0], '"StripThickness"')]
    volume += PAD_VOLUME
    await volume_check(adapter, "pad", volume, 0.02 * PAD_VOLUME)

    # Foot screw hole (PR7 item 11): ONE native Hole Wizard #4 clearance feature
    # (through-all along Y) through the foot strip near its free end, drilled
    # from the foot's underside (normal -Y). The path is the foot's top face at
    # y=FOOT_Y and the wall lies under it (the pad gate proved it), so the -Y
    # face is within the 1.0 mm find_planar_face tolerance of the FOOT_Y point
    # and the -Y normal filter disambiguates it from the top face.
    screw_dia = blind_cut_dia_mm(HOLE_SPEC)
    wizard_holes(
        adapter,
        HOLE_SPEC,
        [[FOOT_END[0] - HOLE_FROM_END, FOOT_Y, PAD_Z]],
        (0.0, -1.0, 0.0),
        "foot screw hole (#4 clearance)",
        name="FootHole",
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

    # Manufacturing drawing support: every hand-formed feature carries the one
    # formed band; the blank's cut features ride the title-block .XX row. The
    # part authors the decimal places and the drawing reads them back.
    for feature_name, dimension_names in FORMED_DIMENSIONS.items():
        for name in sorted(dimension_names):
            set_dimension_symmetric_tolerance(
                adapter, feature_name, name, FORMED_TOLERANCE_MM
            )
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_precision(adapter, DRAWING_PRECISION)

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
