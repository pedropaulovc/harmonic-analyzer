r"""Reproduction script: channel-spring plate hook (book ch. 17, p. 41 / pp. 43-45).

Each of the 20 channel return springs is NOT hooked straight into the
summing-lever coefficient plate. A separate little open hook fastener seats in
the plate's O2.0 hole and the spring's bottom eye links onto it (book ch.17
page002_img04/img06: the spring bank lands on the plate through a row of small
hooks, exactly the boss-hook / counter-spring idiom one step down in size).

Geometry (open J-hook): the SAME line-arc-line idiom as the boss hook, one size
down -- a straight O-rod shank rises +Y (it fills the plate's O2.0 bore and pokes
a little above), a 90-degree elbow, then a short horizontal arm +X that the
spring's bottom eye encircles nail-through-ring style. The shank is what the
assembly seats in the plate hole; the arm, presented just above the plate, is
what the spring catches. The spring's bottom eye now sits ABOVE the plate (it no
longer threads through it) -- this hook is the separate fastener that bridges the
two.

Layout: shank axis +Y from the origin (local origin = shank base, seated at the
plate underside). The arm centreline sits SHANK_RISE + ELBOW_R above the base;
the spring eye threads the arm with a small air gap (zero interference, the
boss-hook convention). All dims are LOW confidence (museum-glass photo reads of
a ~few-mm hardware part) -- editable globals, tune against the plate fit.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_spring_hook.py
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

from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _saved_part_guard import require_saved_drawing_properties
from spring_hook_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    ISOMETRIC_VIEW_NOTE,
)

PART_NAME = "spring-hook"
MATERIAL = "Plain Carbon Steel"  # black hardware, like the boss hook

ROD_DIA = 1.4  # DIMENSIONS.md ch17: little plate hook wire (low)
SHANK_RISE = 7.6  # straight rise: fills the 5.1 plate bore + pokes ~2.5 above so the
# arm presents the spring eye high enough for its O5.5 ring to clear the plate (derived)
ELBOW_R = 1.5  # centreline bend radius (low)
ARM_RUN = 2.5  # straight hook arm the spring eye encircles; tip at x 4.0 (derived)
# Open J-hook, same line-arc-line idiom as the boss hook one size down. Local
# frame: shank axis +Y from the origin (shank base); shank rises SHANK_RISE, a
# 90-degree elbow, then a horizontal arm +X the spring's bottom eye encircles
# nail-through-ring style. Rod centreline tops out at y = SHANK_RISE + ELBOW_R;
# arm tip at x = ELBOW_R + ARM_RUN. In the assembly each seats shank-UP in the
# plate bore (natural orientation), the arm presenting just ABOVE the plate where
# the spring's (now above-plate) bottom eye threads it -- the hook is the separate
# fastener bridging spring-to-plate (the spring no longer passes through the bore).


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import SweepParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). The mm suffix is load-bearing -- this is
    # an INCH document and the equation manager reads BARE numbers in document
    # units (an unsuffixed 11 = 11 in, blowing the part up 25.4x).
    await set_global(adapter, "RodDia", f"{ROD_DIA}mm")
    await set_global(adapter, "ShankRise", f"{SHANK_RISE}mm")
    await set_global(adapter, "ElbowR", f"{ELBOW_R}mm")
    await set_global(adapter, "ArmRun", f"{ARM_RUN}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Path in the Front plane: rise, quarter-arc elbow, horizontal arm -- the same
    # proven line-arc-line chain as build_boss_hook, one size down (a 270-degree
    # planar loop self-intersects the swept wire; an open J does not). Direct DB
    # keeps inference relations off the chain (auto-tangent at the elbow would
    # collide with the explicit alignment); exact-coordinate joints still merge.
    # add_arc draws CCW, so the elbow runs from the arm joint (top) back to the
    # rise joint.
    path = SketchDims()
    check("create_sketch hook path", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    rise = check("rise line", await adapter.add_line(0.0, 0.0, 0.0, SHANK_RISE))
    elbow = check(
        "elbow arc",
        await adapter.add_arc(
            ELBOW_R, SHANK_RISE,            # centre
            ELBOW_R, SHANK_RISE + ELBOW_R,  # start (arm joint)
            0.0, SHANK_RISE,                # end (rise joint)
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
    # Elbow centre at (ElbowR, rise top); the arm joint sits straight above it (the
    # tangency condition without an inference relation). No radius dim: the merged
    # rise joint already sets r = ElbowR.
    await anchor_point_to_origin(
        adapter, f"{elbow}.center", ELBOW_R, SHANK_RISE, "elbow centre"
    )
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
        await adapter.create_sweep(SweepParameters(path="HookPath")),
    )
    name_last_feature(adapter, "Hook")

    # Pappus: planar path, volume = path length x wire area (quarter-arc elbow).
    path_len = SHANK_RISE + math.pi / 2.0 * ELBOW_R + ARM_RUN
    v_expected = path_len * math.pi * (ROD_DIA / 2.0) ** 2
    await volume_check(adapter, "hook", v_expected, 0.05 * v_expected)

    # Apply the deferred drive equations now -- after the whole model + a rebuild
    # exists, so every target resolves. Each evaluates to the as-built value, so
    # the geometry must not move -- the re-check below is the proof.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven hook (equations neutral)", v_expected, 0.05 * v_expected)

    # Named shank axis (local Y through the origin) so the hook seats in the plate
    # hole and the assembly can reference it (the spring pulls through the curl in
    # the M6 Motion study), mirroring build_boss_hook.
    await name_bore_axis(adapter, "Front Plane", 0.0, "Right Plane", 0.0, "shank axis")

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)

    # Manufacturing drawing support: mark exactly the print's dimensions and
    # stamp the make-critical title-block properties.
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": DRAWING_NOTES,
            "Isometric View Note": ISOMETRIC_VIEW_NOTE,
        },
    )
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(
        adapter,
        (
            "Number", "Material Specification", "Finish", "Quantity",
            "Manufacturing Notes", "Isometric View Note",
        ),
    )
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
