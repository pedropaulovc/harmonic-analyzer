r"""Reproduction script: counter spring (book ch. 19, pp. 44-45).

The "long spring [that] towers above the machine": a slender close-wound
extension spring from the summing-lever boss hook up to the curved, tapered
gooseneck post. It counterbalances the accumulated pull of the 20 channel
springs; tension is set by sliding the post (square-head screw).

M6.4 revision: the M2 "300 x O22, wire 2.5" read came from the cut-off p1
front page (the spring exits the page top). Recalibrated against the ch. 19
full-machine photo (gooseneck scale 0.515 px/mm, top ~ y 1438) and the p3
90-degree page: body ~315 long, OD ~12.5, wire ~1.8, visibly close-wound
(dark, no light through the coils). The bottom wire is a LONG straight drop
(40 mm) from the coil to the ring that hangs on the summing-lever boss
J-hook (build_boss_hook.py, rod along X at (95, 1015)); the top hook hangs
on the X-pin under the gooseneck tip lug at (95, 1373). Both loops lie in
the YZ plane after the assembly's 90-degree Y-rotation, so each encircles
its X-rod nail-through-ring style (the p.43 black hook + chrome ring chain
collapsed to loop-on-hook -- simplification). See DIMENSIONS.md ch. 19.

Layout: coil axis along +Y from the origin (helix base circle on the Top
plane); the helix starts and ends on the +X side (whole number of coils).
In the machine the origin lands at (95, 1052, 0): bottom ring centre at
y 1012, top loop centre at y 1370.6.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_counter_spring.py
"""

from __future__ import annotations

import sys

from _common import (
    SPRING_BLACK,
    SketchDims,
    apply_color,
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
    volume_check,
)
from _common import (
    _feature_by_name,  # rename the helix base sketch (consumed by InsertHelix)
)
from _features import (
    add_spring_end_hooks,
    insert_helix,
)

import _telemetry

PART_NAME = "counter-spring"
MATERIAL = "Alloy Steel"  # see _common.apply_material docstring

COIL_BODY_LENGTH = 315.0  # DIMENSIONS.md ch19: ch.19 photo, gooseneck-scaled (low)
COIL_OD = 12.5  # DIMENSIONS.md ch19: scaled vs gooseneck tube O16 (low)
WIRE_DIA = 1.8  # DIMENSIONS.md ch19: close-wound dark coil (low)
COIL_COUNT = 165  # close-wound: pitch 1.91 leaves a 0.11 sweep-merge gap (derived)
BOTTOM_LEAD = 40.0  # straight drop, coil bottom -> boss-hook ring centre
# (body bottom y 1052 - ring centre y 1012; see build_summing_assembly.py)
TOP_LEAD = 2.0 * WIRE_DIA  # standard short hook onto the gooseneck tip pin

MEAN_RADIUS = (COIL_OD - WIRE_DIA) / 2.0
PITCH = COIL_BODY_LENGTH / COIL_COUNT  # whole coils: both ends land at +X


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import SweepParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). mm suffix is load-bearing (INCH
    # document; the equation manager reads bare numbers in document units).
    # CoilBodyLength + Pitch feed InsertHelix (FEATURE parameters, not sketch
    # dims) -- declared as knobs but never entered into drive_jobs, like an
    # extrude depth. MeanRadius is derived (coil OD minus one wire dia, halved)
    # and drives both the helix base diameter and the wire-profile centre.
    await set_global(adapter, "CoilOD", f"{COIL_OD}mm")
    await set_global(adapter, "WireDia", f"{WIRE_DIA}mm")
    await set_global(adapter, "MeanRadius", '("CoilOD" - "WireDia") / 2')
    await set_global(adapter, "CoilBodyLength", f"{COIL_BODY_LENGTH}mm")
    await set_global(adapter, "Pitch", f"{PITCH}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Helix base circle: on the origin (Top plane), so define_circle emits ONLY
    # the diameter dim -- the two centre slots stay None. Drive the diameter to
    # 2 * MeanRadius. The sketch is consumed by InsertHelix (no exit_sketch), so
    # it is renamed by-name below rather than via name_last_feature.
    base_dims = SketchDims()
    check("create_sketch helix base", await adapter.create_sketch("Top"))
    await define_circle(
        adapter, 0.0, 0.0, MEAN_RADIUS, "helix base", dims=base_dims,
        names=("BaseCx", "BaseCz", "MeanDia"),
        drives=(None, None, '2 * "MeanRadius"'),
    )
    await ensure_fully_defined(adapter, "helix base sketch")
    # Rename the open base sketch before InsertHelix consumes it; update the
    # later blank_sketch reference to the new name (the captured "Sketch1"
    # auto-name would go stale otherwise).
    _feature_by_name(adapter, "Sketch1").Name = "HelixBaseProfile"
    _telemetry.success("feature 'Sketch1' -> 'HelixBaseProfile'")
    drive_jobs += base_dims.apply(adapter, "HelixBaseProfile")
    helix_name = insert_helix(adapter, COIL_BODY_LENGTH, PITCH)

    # Wire profile circle: off-axis in +X (centre on the mean-radius circle),
    # on the Front plane. define_circle emits a centre-X dim (x != 0) then the
    # diameter; the centre-Z slot stays None (y == 0). Drive centre-X to
    # MeanRadius and the diameter to WireDia.
    wire_dims = SketchDims()
    check("create_sketch wire profile", await adapter.create_sketch("Front"))
    await define_circle(
        adapter, MEAN_RADIUS, 0.0, WIRE_DIA / 2.0, "wire profile", dims=wire_dims,
        names=("WireCx", "WireCz", "WireDiaDim"),
        drives=('"MeanRadius"', None, '"WireDia"'),
    )
    await ensure_fully_defined(adapter, "wire profile sketch")
    check("exit_sketch wire profile", await adapter.exit_sketch())
    name_last_feature(adapter, "WireProfile")
    drive_jobs += wire_dims.apply(adapter, "WireProfile")

    check(
        "sweep wire along helix",
        await adapter.create_sweep(SweepParameters(path=helix_name)),
    )
    name_last_feature(adapter, "CoilBody")

    await add_spring_end_hooks(
        adapter,
        MEAN_RADIUS,
        WIRE_DIA,
        COIL_BODY_LENGTH,
        leads=(BOTTOM_LEAD, TOP_LEAD),
    )

    # No analytic baseline (the swept coil + two Pappus-junction hooks are awkward
    # to close-form), so capture the as-built volume of the finished part and
    # assert the deferred equations are geometry-neutral against it. Helical sweep
    # faceting + hook junctions warrant a looser tol (0.5%) than a prismatic part.
    mass = await adapter.get_mass_properties()
    if not mass.is_success:
        raise RuntimeError(f"as-built volume: get_mass_properties failed: {mass.error}")
    v_built = float(mass.data.volume)
    tol = 0.005 * v_built
    await volume_check(adapter, "counter spring (as built)", v_built, tol)

    # Helix base sketch stays unabsorbed-and-shown after InsertHelix (see
    # _spring.build_spring) -- blank it so it doesn't render in assemblies.
    blank_sketch(adapter, "HelixBaseProfile")

    # Deferred drive equations, then re-check neutrality (each evaluates to the
    # as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven counter spring (equations neutral)", v_built, tol)

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, SPRING_BLACK)  # ch30 plates: see _common palette
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
