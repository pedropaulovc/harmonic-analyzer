r"""Reproduction script: summing-lever boss hook (book ch. 18/19, pp. 43-45).

The black J-hook that hangs the counter spring from the summing-lever
boss: an O3 rod planted in the boss top, rising clear of the boss, then
bent 90 degrees into a horizontal arm pointing +X (toward the channels'
mid-line) that the counter spring's bottom ring encircles nail-through-
ring style. The p.43/p.45 photos show a hook + separate chrome link ring;
the chain is collapsed to this single hook with the spring's own loop as
the ring (simplification, see build_counter_spring.py).

Dimensions: cad/DIMENSIONS.md ch. 18/19 (M6.4, low). Geometry constraints
that size it (see build_summing_assembly.py): shank at machine x 90.5
(boss hole), rod centreline at machine y 1015 so the spring ring (mean
r 5.35, wire 1.8) hanging at centre y 1012 touches the rod top; rod tip
at machine x 97 so the ring's wire band (x 94.1..95.9) sits mid-rod.

Layout: shank axis +Y from the origin (machine (90.5, 1000, 0)); path =
vertical line, 90-degree elbow (R 3), horizontal line +X. Single sweep
along a line/arc/line chain — the old equation-curve workaround (fix on
lines/arcs left endpoint DOFs) reverted once sketch points became
addressable (semantic anchors, SolidworksMCP-python PRs #55/#56).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_boss_hook.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    SketchDims,
    anchor_point_to_origin,
    apply_material,
    check,
    define_circle,
    dimension_between,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_bore_axis,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    set_sketch_direct_db,
    volume_check,
)

PART_NAME = "boss-hook"
MATERIAL = "Plain Carbon Steel"  # black hardware

ROD_DIA = 3.0  # DIMENSIONS.md ch18: hook rod (low)
SHANK_RISE = 12.0  # straight rise before the elbow (derived)
ELBOW_R = 3.0  # centreline bend radius (low)
ARM_RUN = 3.5  # straight run after the elbow; tip at x 6.5 (derived)
# Rod centreline tops out at y = SHANK_RISE + ELBOW_R = 15 (machine 1015);
# tip at x = ELBOW_R + ARM_RUN = 6.5 (machine 97).


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import SweepParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): rod diameter, the straight rise, the
    # elbow bend radius and the arm run. The mm suffix is load-bearing -- this is
    # an INCH document and the equation manager reads BARE numbers in document
    # units (an unsuffixed 12 = 12 in, blowing the part up 25.4x).
    await set_global(adapter, "RodDia", f"{ROD_DIA}mm")
    await set_global(adapter, "ShankRise", f"{SHANK_RISE}mm")
    await set_global(adapter, "ElbowR", f"{ELBOW_R}mm")
    await set_global(adapter, "ArmRun", f"{ARM_RUN}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Path in the Front plane: rise, quarter-arc elbow, horizontal arm.
    # Direct DB keeps inference relations off the chain (auto-tangent at
    # the elbow would collide with the explicit alignment scheme below);
    # exact-coordinate joints still merge. add_arc draws CCW, so the elbow
    # runs from the arm joint (top) back to the rise joint.
    # Each manual driving dim is recorded into a per-sketch SketchDims in
    # creation order; apply() count-asserts the total against the feature's real
    # display-dim count and renames structurally, then the drive equations run in
    # one deferred batch after the whole model exists.
    path = SketchDims()
    path_name = check("create_sketch hook path", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    rise = check("rise line", await adapter.add_line(0.0, 0.0, 0.0, SHANK_RISE))
    elbow = check(
        "elbow arc",
        await adapter.add_arc(
            ELBOW_R, SHANK_RISE,  # centre
            ELBOW_R, SHANK_RISE + ELBOW_R,  # start (arm joint)
            0.0, SHANK_RISE,  # end (rise joint)
        ),
    )
    arm = check(
        "arm line",
        await adapter.add_line(
            ELBOW_R, SHANK_RISE + ELBOW_R, ELBOW_R + ARM_RUN, SHANK_RISE + ELBOW_R
        ),
    )
    set_sketch_direct_db(adapter, False)
    check("rise vertical", await adapter.add_sketch_constraint(rise, None, "vertical"))
    check(
        "rise start -> origin",
        await adapter.add_sketch_constraint(f"{rise}.start", "origin", "coincident"),
    )
    await dimension_between(
        adapter, f"{rise}.start", f"{rise}.end", "vertical_distance", SHANK_RISE, "rise"
    )
    path.record("Rise", '"ShankRise"')
    # Elbow centre at (R, rise top); the arm joint sits straight above it,
    # which is the tangency condition without an inference-style relation.
    # No radius dim: the merged rise joint already sets r = ELBOW_R.
    await anchor_point_to_origin(
        adapter, f"{elbow}.center", ELBOW_R, SHANK_RISE, "elbow centre"
    )
    # Elbow centre is off both axes: anchor_point_to_origin emits a
    # horizontal_distance (= ElbowR) then a vertical_distance (= ShankRise).
    path.record("ElbowCx", '"ElbowR"')
    path.record("ElbowCy", '"ShankRise"')
    check(
        "arm joint above elbow centre",
        await adapter.add_sketch_constraint(
            f"{elbow}.start", f"{elbow}.center", "vertical_points"
        ),
    )
    check("arm horizontal", await adapter.add_sketch_constraint(arm, None, "horizontal"))
    await dimension_between(
        adapter, f"{arm}.start", f"{arm}.end", "horizontal_distance", ARM_RUN, "arm run"
    )
    path.record("ArmRun", '"ArmRun"')
    await ensure_fully_defined(adapter, "hook path")
    check("exit_sketch hook path", await adapter.exit_sketch())
    name_last_feature(adapter, "HookPath")
    drive_jobs += path.apply(adapter, "HookPath")

    # Wire profile at the path start (origin, Top plane). On-origin circle: only
    # the diameter is a dim (the centre is a coincident relation).
    profile = SketchDims()
    check("create_sketch wire profile", await adapter.create_sketch("Top"))
    await define_circle(
        adapter, 0.0, 0.0, ROD_DIA / 2.0, "wire profile", dims=profile,
        names=("WireCx", "WireCz", "RodDia"),
        drives=(None, None, '"RodDia"'),
    )
    await ensure_fully_defined(adapter, "wire profile sketch")
    check("exit_sketch wire profile", await adapter.exit_sketch())
    name_last_feature(adapter, "WireProfile")
    drive_jobs += profile.apply(adapter, "WireProfile")

    check(
        "sweep hook",
        # Path sketch was renamed to "HookPath" above; select it by the new name
        # (the captured path_name still holds the stale auto "Sketch1").
        await adapter.create_sweep(SweepParameters(path="HookPath")),
    )
    name_last_feature(adapter, "Hook")

    # Pappus: planar path, volume = path length x wire area.
    path_len = SHANK_RISE + math.pi / 2.0 * ELBOW_R + ARM_RUN
    v_expected = path_len * math.pi * (ROD_DIA / 2.0) ** 2
    await volume_check(adapter, "hook", v_expected, 0.02 * v_expected)

    # Apply the deferred drive equations now -- after the whole model + a rebuild
    # exists, so every target resolves. Each equation evaluates to the value just
    # built, so the geometry must not move -- the re-check below is the proof.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven hook (equations neutral)", v_expected, 0.02 * v_expected)

    # Named shank axis (local Y through the origin) so the hook locks to the
    # summing lever and rides it (the counter spring pulls through the hook in
    # the M6 Motion study).
    await name_bore_axis(adapter, "Front Plane", 0.0, "Right Plane", 0.0, "shank axis")

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
