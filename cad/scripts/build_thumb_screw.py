r"""Reproduction script: reeded thumb screw (book ch. 20, p. 48).

The knurled ("reeded") thumb screw that locks the magnifying-lever clamp
block (a second identical one locks the output fixture). M4 finishing
pass: head reeded with 24 axial Ø1 mm grooves (tube-frame fluting recipe,
``_features.add_reeded_head_and_thread``) and a cosmetic #4-40 UNC thread on
the shank (annotation only -- keeps M6 interference checks clean).

The stepped body is two coaxial merged extrusions (cone-gear-shaft
recipe), NOT a profile revolve: circular patterns of cuts on stepped
REVOLVED bodies fail to create (probe-verified on SW 2026 -- plain
revolved cylinders pattern fine, stepped ones never do; identical
geometry from stacked extrusions patterns fine).

Dimensions: cad/DIMENSIONS.md "Chapter 20" — photo-scaled vs the Ø6
lever rod (low); groove count/size photo-estimated (low).

Layout: screw axis along +X from the origin (head face at x=0).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_thumb_screw.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    SketchDims,
    apply_material,
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
from _features import add_reeded_head_and_thread

PART_NAME = "thumb-screw"
MATERIAL = "Brass"  # see _common.apply_material docstring

HEAD_DIA = 10.0  # DIMENSIONS.md ch20: knurled head, p.48 (low)
HEAD_LENGTH = 5.0  # DIMENSIONS.md ch20 (low)
SHANK_DIA = 2.0  # shank: was Ø3.0, now 2.0 = #4-40 tap-drill 2.261 - 0.26
# (threads #4-40 into the clamp block / output fixture)
SHANK_LENGTH = 12.0  # DIMENSIONS.md ch20 (low)


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): the two step diameters + lengths. The
    # mm suffix is load-bearing -- this is an INCH document and the equation
    # manager reads BARE numbers in document units (an unsuffixed 10 = 10 in).
    # ShankExtent is the second extrude's depth (head + shank), a derived global
    # so it tracks both knobs; it is a feature parameter, so nothing drives it.
    await set_global(adapter, "HeadDia", f"{HEAD_DIA}mm")
    await set_global(adapter, "HeadLength", f"{HEAD_LENGTH}mm")
    await set_global(adapter, "ShankDia", f"{SHANK_DIA}mm")
    await set_global(adapter, "ShankLength", f"{SHANK_LENGTH}mm")
    await set_global(adapter, "ShankExtent", '"HeadLength" + "ShankLength"')

    drive_jobs: list[tuple[str, str]] = []

    # Stepped blank: two coaxial on-axis circles (centre at the origin), so each
    # define_circle records ONLY its diameter dim -- the centre X/Z slots are
    # ignored. Name + record each sketch BEFORE its extrude absorbs it.
    for label, dia, length, dia_name, dia_drive in (
        ("head", HEAD_DIA, HEAD_LENGTH, "HeadDia", '"HeadDia"'),
        ("shank", SHANK_DIA, HEAD_LENGTH + SHANK_LENGTH, "ShankDia", '"ShankDia"'),
    ):
        sd = SketchDims()
        check(f"create_sketch {label}", await adapter.create_sketch("Right"))
        await define_circle(
            adapter, 0.0, 0.0, dia / 2.0, label, dims=sd,
            names=(f"{label}Cx", f"{label}Cz", dia_name),
            drives=(None, None, dia_drive),
        )
        await ensure_fully_defined(adapter, f"{label} sketch")
        check(f"exit_sketch {label}", await adapter.exit_sketch())
        name_last_feature(adapter, f"{label.capitalize()}Profile")
        drive_jobs += sd.apply(adapter, f"{label.capitalize()}Profile")
        check(
            f"extrude {label}",
            await adapter.create_extrusion(ExtrusionParameters(depth=length)),
        )
        name_last_feature(adapter, label.capitalize())
    v_blank = math.pi * (
        (HEAD_DIA / 2.0) ** 2 * HEAD_LENGTH + (SHANK_DIA / 2.0) ** 2 * SHANK_LENGTH
    )
    await volume_check(adapter, "stepped blank", v_blank, 0.005 * v_blank)

    # Apply the deferred drive equations after the blank + a rebuild exists (each
    # equation evaluates to the value just built, so geometry must not move), then
    # re-check the blank's volume as the neutrality proof -- BEFORE the reeding
    # pass mutates the volume.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven stepped blank (equations neutral)", v_blank, 0.005 * v_blank)

    await add_reeded_head_and_thread(
        adapter, HEAD_DIA, HEAD_LENGTH, SHANK_DIA, SHANK_LENGTH, groove_count=24
    )

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
