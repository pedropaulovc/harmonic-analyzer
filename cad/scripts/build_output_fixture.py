r"""Reproduction script: output fixture collar (book ch. 20, p. 48).

The small fixture that slides up and down the vertical rod to set the
trace's vertical placement on the paper; the wire to the magnifying wheel
hooks onto it and a small reeded screw (separate thumb-screw part) locks
it. Modelled as a collar with the rod bore and one cross hole that serves
the clamp screw / wire hook.

Dimensions: cad/DIMENSIONS.md "Chapter 20" — photo-scaled, p.48 bottom
close-up (low).

Layout: collar axis along Y (extruded from a Top-plane sketch, which maps
(x, y) -> global (X, -Z)); cross hole along Z from a Front-plane sketch.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_output_fixture.py
"""

from __future__ import annotations

import math
import sys

import _telemetry
from _common import (
    SketchDims,
    _read_member,
    apply_material,
    blank_sketch,
    check,
    define_circle,
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
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _holes import TAP_DRILL_MM
from output_fixture_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    END_VIEW_NOTE,
    ISOMETRIC_VIEW_NOTE,
)

PART_NAME = "output-fixture"
MATERIAL = "Brass"  # see _common.apply_material docstring

COLLAR_DIA = 10.0  # DIMENSIONS.md ch20: p.48 bottom close-up (low)
COLLAR_HEIGHT = 8.0  # DIMENSIONS.md ch20 (low)
# The Ø5 vertical rod slides through the coaxial bore -- an engineered 0.2 mm
# running/slip fit, NOT a drilled hole, so it stays a plain dimensioned cut (the
# Hole Wizard's standard drills are for drilled holes/pins/seats; a nearest-
# drill fit would slop the slide).
ROD_BORE_DIA = 5.2  # Ø5 vertical rod + clearance
#
# The cross hole is DESIGNED as a #4-40 tapped thumb-screw hole, but it pierces
# the CURVED collar wall RADIALLY -- there is no planar seat for wizard_holes /
# find_planar_face to place a Hole Wizard feature on -- so it stays a plain cut
# at the #4-40 tap-drill diameter (Ø2.261) as the geometric stand-in (the real
# thread designation can't be carried on the cylindrical wall with this helper).
# No interference either way: the assembly OMITS this thumb screw (the cross
# hole doubles as the wire tie), and the mating Ø2.0 shank fits Ø2.261 anyway.
CROSS_HOLE_DIA = TAP_DRILL_MM["#4-40"]  # 2.261: #4-40 tap drill (was Ø3.0)
THROUGH_CUT_DEPTH = 40.0  # mid-plane total; > any extent crossed

# HookAnchorPoint: where the lever-wire's hook BALL JOINT grabs the fixture.
# The wire ties through the cross hole and hangs just UNDER the collar's
# bottom face (wire r 0.4 + 0.25 clearance = 0.65 below it) on the front face
# of the vertical rod (rod r 2.5 + wire r 0.4 + 0.25 = 3.15 off the rod axis
# in local -z).
# build_lever_wire.HOOK_Y/HOOK_Z anchor the same spot in machine coords;
# build_magnifier_assembly asserts the two agree. Local x = 0, so the point
# is invariant under the machine-chirality mirror (no double-flip trap).
HOOK_ANCHOR_LOCAL = (0.0, -0.65, -3.15)


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import (
        CreatePlaneParameters,
        ExtrusionParameters,
    )

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): collar OD/height, rod bore and cross
    # hole diameters. The mm suffix is load-bearing -- this is an INCH document
    # and the equation manager reads BARE numbers in document units (an
    # unsuffixed 10 = 10 in, blowing the part up 25.4x).
    await set_global(adapter, "CollarDia", f"{COLLAR_DIA}mm")
    await set_global(adapter, "CollarHeight", f"{COLLAR_HEIGHT}mm")
    await set_global(adapter, "RodBoreDia", f"{ROD_BORE_DIA}mm")
    await set_global(adapter, "CrossHoleDia", f"{CROSS_HOLE_DIA}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Collar: on-axis circle (centre at the origin), so define_circle emits only
    # the diameter dim -- the two centre slots are ignored.
    collar = SketchDims()
    check("create_sketch collar", await adapter.create_sketch("Top"))
    await define_circle(
        adapter, 0.0, 0.0, COLLAR_DIA / 2.0, "collar", dims=collar,
        names=("CollarCx", "CollarCz", "CollarDiaDim"),
        drives=(None, None, '"CollarDia"'),
    )
    await ensure_fully_defined(adapter, "collar sketch")
    check("exit_sketch collar", await adapter.exit_sketch())
    name_last_feature(adapter, "CollarProfile")
    drive_jobs += collar.apply(adapter, "CollarProfile")
    check(
        "extrude collar",
        await adapter.create_extrusion(ExtrusionParameters(depth=COLLAR_HEIGHT)),
    )
    name_last_feature(adapter, "Collar")
    # Drive the collar's extrude depth from CollarHeight too (D1 is the blind-
    # extrude depth dim). The cross hole is driven to CollarHeight/2, so the body
    # height must move with it or a GUI edit of CollarHeight leaves the hole
    # off-centre (or outside the collar). Evaluates to as-built -> neutral.
    drive_jobs.append(("D1@Collar", '"CollarHeight"'))
    v_collar = math.pi * (COLLAR_DIA / 2.0) ** 2 * COLLAR_HEIGHT
    await volume_check(adapter, "collar", v_collar, 0.005 * v_collar)

    # Rod bore: on-axis circle, diameter dim only. A plain dimensioned slip cut
    # (engineered 0.2 mm running fit, not a drilled hole).
    rod = SketchDims()
    check("create_sketch rod bore", await adapter.create_sketch("Top"))
    await define_circle(
        adapter, 0.0, 0.0, ROD_BORE_DIA / 2.0, "rod bore", dims=rod,
        names=("RodCx", "RodCz", "RodBoreDiaDim"),
        drives=(None, None, '"RodBoreDia"'),
    )
    await ensure_fully_defined(adapter, "rod bore sketch")
    check("exit_sketch rod bore", await adapter.exit_sketch())
    name_last_feature(adapter, "RodBoreProfile")
    drive_jobs += rod.apply(adapter, "RodBoreProfile")
    check(
        "cut rod bore",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "RodBore")
    v_bored = v_collar - math.pi * (ROD_BORE_DIA / 2.0) ** 2 * COLLAR_HEIGHT
    await volume_check(adapter, "rod bore", v_bored, 0.005 * v_collar)

    # Cross hole along Z at mid-height (collar grows +Y from the Top plane). Left
    # a PLAIN CUT at the #4-40 tap-drill Ø -- a radial hole in the curved collar
    # wall has no planar seat for the Hole Wizard (see the CROSS_HOLE_DIA note).
    # On the Front plane the centre is off-axis in y (height) only, so
    # define_circle emits a z (height) dim then the diameter -- x slot ignored.
    cross = SketchDims()
    check("create_sketch cross hole", await adapter.create_sketch("Front"))
    await define_circle(
        adapter, 0.0, COLLAR_HEIGHT / 2.0, CROSS_HOLE_DIA / 2.0, "cross hole",
        dims=cross,
        names=("CrossCx", "CrossHeight", "CrossHoleDiaDim"),
        drives=(None, '"CollarHeight" / 2', '"CrossHoleDia"'),
    )
    await ensure_fully_defined(adapter, "cross hole sketch")
    check("exit_sketch cross hole", await adapter.exit_sketch())
    name_last_feature(adapter, "CrossHoleProfile")
    drive_jobs += cross.apply(adapter, "CrossHoleProfile")
    check(
        "cut cross hole",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "CrossHole")
    # The Ø3 cross hole removes only the two annular walls it pierces (the bore
    # already cleared the centre); no clean closed form, so a loose tol.
    wall_span = COLLAR_DIA - ROD_BORE_DIA  # 2 x wall thickness pierced
    v_final = v_bored - math.pi * (CROSS_HOLE_DIA / 2.0) ** 2 * wall_span
    await volume_check(adapter, "cross hole", v_final, 30.0)

    # Apply the deferred drive equations after the whole model + a rebuild
    # exists, then re-check neutrality (each equation evaluates to the as-built
    # value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven output fixture (equations neutral)", v_final, 30.0)

    # HookAnchorPoint: the lever-wire ball joint's fixture-side anchor (see
    # HOOK_ANCHOR_LOCAL). No adapter writer exists for a free-XYZ reference
    # point, so: blanked offset plane -> hidden sketch point (inference off,
    # exact coords) -> InsertReferencePoint(swRefPointSketchPoint = 7) ->
    # rename -- the build_magnifying_wheel WireYokePoint recipe (late-binding
    # traps documented there and in memory/solidworks-modeling-pitfalls.md).
    check(
        "create_plane HookAnchorPlane",
        await adapter.create_plane(CreatePlaneParameters(
            mode="offset", base_plane="Top Plane", offset=HOOK_ANCHOR_LOCAL[1])),
    )
    name_last_feature(adapter, "HookAnchorPlane")
    _blank_ref_plane(adapter, "HookAnchorPlane")
    check("create_sketch hook anchor", await adapter.create_sketch("HookAnchorPlane"))
    set_sketch_direct_db(adapter, True)
    model = adapter.currentModel
    # Top-plane sketch mapping (x, y) -> (X, -Z); the offset plane inherits it.
    sk_point = model.SketchManager.CreatePoint(
        HOOK_ANCHOR_LOCAL[0] / 1000.0, -HOOK_ANCHOR_LOCAL[2] / 1000.0, 0.0)
    if sk_point is None:
        raise RuntimeError("hook anchor sketch point creation failed")
    set_sketch_direct_db(adapter, False)
    check("exit_sketch hook anchor", await adapter.exit_sketch())
    name_last_feature(adapter, "HookAnchorSketch")
    blank_sketch(adapter, "HookAnchorSketch")
    _make_hook_ref_point(adapter)
    _assert_hook_point(adapter)

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": DRAWING_NOTES,
            "End View Note": END_VIEW_NOTE,
            "Isometric View Note": ISOMETRIC_VIEW_NOTE,
        },
    )
    return await save_part_and_images(adapter, PART_NAME)


def _blank_ref_plane(adapter, name: str) -> None:
    """Hide a reference plane (shown ref geometry renders in every assembly
    instance -- the fix_shown_sketches BlankRefGeom idiom, applied at build)."""
    from solidworks_mcp.adapters.pywin32_adapter import null_callout

    model = adapter.currentModel
    model.ClearSelection2(True)
    if not model.Extension.SelectByID2(name, "PLANE", 0, 0, 0, False, 0, null_callout(), 0):
        raise RuntimeError(f"blank ref plane: cannot select {name!r}")
    model.BlankRefGeom()
    model.ClearSelection2(True)


def _hook_sketch_points(adapter):
    """The ISketchPoint list of HookAnchorSketch (exactly one expected);
    members via ``_read_member`` (the pywin32 late-binding walk idiom)."""
    model = adapter.currentModel
    feat = _read_member(model, "FirstFeature")
    for _ in range(5000):
        if not feat:
            break
        if str(_read_member(feat, "Name")) == "HookAnchorSketch":
            sketch = _read_member(feat, "GetSpecificFeature2")
            return list(_read_member(sketch, "GetSketchPoints2") or [])
        feat = _read_member(feat, "GetNextFeature")
    raise RuntimeError("HookAnchorSketch not found")


def _make_hook_ref_point(adapter) -> None:
    """Promote the anchor sketch point to the named ``HookAnchorPoint``
    reference-point feature (raw COM -- see the build() comment)."""
    model = adapter.currentModel
    pts = _hook_sketch_points(adapter)
    if len(pts) != 1:
        raise RuntimeError(f"HookAnchorSketch: expected 1 point, found {len(pts)}")
    model.ClearSelection2(True)
    if not pts[0].Select2(False, 0):  # Select4's ISelectData arg = Type mismatch
        raise RuntimeError("cannot select the hook anchor sketch point")
    feat = model.FeatureManager.InsertReferencePoint(7, 0, 0.0, 1)
    model.ClearSelection2(True)
    if isinstance(feat, tuple):  # late binding marshals the object return boxed
        feat = next((f for f in feat if f is not None), None)
    if feat is None:
        raise RuntimeError("InsertReferencePoint(sketch point) returned null")
    feat.Name = "HookAnchorPoint"
    if str(_read_member(feat, "Name")) != "HookAnchorPoint":
        raise RuntimeError("reference point rename failed")
    _telemetry.success("HookAnchorPoint reference point created")


def _assert_hook_point(adapter) -> None:
    """Fail loud if the (undimensioned, hidden) anchor point drifted from its
    authored sketch coords -- the ball joint's geometry must stay exact."""
    pts = _hook_sketch_points(adapter)
    x_mm = float(_read_member(pts[0], "X")) * 1000.0
    y_mm = float(_read_member(pts[0], "Y")) * 1000.0
    exp_x, exp_y = HOOK_ANCHOR_LOCAL[0], -HOOK_ANCHOR_LOCAL[2]
    if abs(x_mm - exp_x) > 1e-3 or abs(y_mm - exp_y) > 1e-3:
        raise RuntimeError(
            f"hook anchor drifted: ({x_mm:.4f}, {y_mm:.4f}) != ({exp_x:.4f}, {exp_y:.4f})"
        )
    _telemetry.success(f"hook anchor holds at ({x_mm:.4f}, {y_mm:.4f})")


if __name__ == "__main__":
    sys.exit(run_build(build))
