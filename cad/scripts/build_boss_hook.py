r"""Reproduction script: summing-lever boss hook (book ch. 18/19, pp. 43-45).

The black J-hook that hangs the counter spring from the summing-lever
boss: an O3 rod planted in the boss top, rising clear of the boss, then
bent 90 degrees into a horizontal arm pointing +X (toward the channels'
mid-line) that the counter spring's bottom ring encircles nail-through-
ring style. The p.43/p.45 photos show a hook + separate chrome link ring;
the chain is collapsed to this single hook with the spring's own loop as
the ring (simplification, see build_counter_spring.py).

Dimensions: cad/DIMENSIONS.md ch. 18/19 (M6.4, low). Geometry constraints
that size it (see build_output_assembly.py): shank at machine x 90.5
(boss hole), rod centreline at machine y 1015 so the spring ring (mean
r 5.35, wire 1.8) hanging at centre y 1012 touches the rod top; rod tip
at machine x 97 so the ring's wire band (x 94.1..95.9) sits mid-rod.

Layout: shank axis +Y from the origin (machine (90.5, 1000, 0)); path =
vertical line, 90-degree elbow (R 3), horizontal line +X. Single sweep
along a line/arc/line chain — the old equation-curve workaround (fix on
lines/arcs left endpoint DOFs) reverted once sketch points became
addressable (semantic anchors, SolidworksMCP-python PRs #55/#56).

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_boss_hook.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    anchor_point_to_origin,
    apply_material,
    check,
    define_circle,
    dimension_between,
    ensure_fully_defined,
    name_bore_axis,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_isometric_view,
    set_sketch_direct_db,
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
    set_isometric_view(adapter)

    # Path in the Front plane: rise, quarter-arc elbow, horizontal arm.
    # Direct DB keeps inference relations off the chain (auto-tangent at
    # the elbow would collide with the explicit alignment scheme below);
    # exact-coordinate joints still merge. add_arc draws CCW, so the elbow
    # runs from the arm joint (top) back to the rise joint.
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
    # Elbow centre at (R, rise top); the arm joint sits straight above it,
    # which is the tangency condition without an inference-style relation.
    # No radius dim: the merged rise joint already sets r = ELBOW_R.
    await anchor_point_to_origin(
        adapter, f"{elbow}.center", ELBOW_R, SHANK_RISE, "elbow centre"
    )
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
    await ensure_fully_defined(adapter, "hook path")
    check("exit_sketch hook path", await adapter.exit_sketch())

    # Wire profile at the path start (origin, Top plane).
    check("create_sketch wire profile", await adapter.create_sketch("Top"))
    await define_circle(adapter, 0.0, 0.0, ROD_DIA / 2.0, "wire profile")
    await ensure_fully_defined(adapter, "wire profile sketch")
    check("exit_sketch wire profile", await adapter.exit_sketch())

    check(
        "sweep hook",
        await adapter.create_sweep(SweepParameters(path=path_name)),
    )

    # Pappus: planar path, volume = path length x wire area.
    path_len = SHANK_RISE + math.pi / 2.0 * ELBOW_R + ARM_RUN
    v_expected = path_len * math.pi * (ROD_DIA / 2.0) ** 2
    res = await adapter.get_mass_properties()
    vol = float(res.data.volume) if res.is_success else float("nan")
    print(f"  volume: {vol:.1f} mm^3 (Pappus {v_expected:.1f})")
    if abs(vol - v_expected) > 0.02 * v_expected:
        raise RuntimeError(f"hook volume {vol:.1f} != Pappus {v_expected:.1f}")

    # Named shank axis (local Y through the origin) so the hook locks to the
    # summing lever and rides it (the counter spring pulls through the hook in
    # the M6 Motion study).
    await name_bore_axis(adapter, "Front Plane", 0.0, "Right Plane", 0.0, "shank axis")

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
