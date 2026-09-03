r"""Reproduction script: reeded thumb screw (book ch. 20, p. 48).

The knurled ("reeded") thumb screw that locks the magnifying-lever clamp
block (a second identical one locks the output fixture). M4 finishing
pass: head reeded with the spec-defined axial Ø1 mm grooves (tube-frame fluting recipe,
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

from _fastener_catalog import fastener
from _common import (
    SketchDims,
    apply_material,
    check,
    define_circle,
    drive_dimension,
    ensure_fully_defined,
    extrude_at_offset,
    force_rebuild,
    name_dimensions,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    volume_check,
)
from _features import add_reeded_head_and_thread
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from thumb_screw_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    END_VIEW_NOTE,
    GROOVE_COUNT,
    GROOVE_DIA,
    HEAD_DIA,
    HEAD_LENGTH,
    SHANK_DIA,
    SHANK_LEN,
)

PART_NAME = "thumb-screw"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material

async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): the two step diameters + lengths. The
    # mm suffix is load-bearing -- this is an INCH document and the equation
    # manager reads BARE numbers in document units (an unsuffixed 10 = 10 in).
    # HeadLength/ShankLength are extrude DEPTHS (feature parameters) --
    # declared as knobs, but nothing in drive_jobs references them.
    await set_global(adapter, "HeadDia", f"{HEAD_DIA}mm")
    await set_global(adapter, "HeadLength", f"{HEAD_LENGTH}mm")
    await set_global(adapter, "ShankDia", f"{SHANK_DIA}mm")
    await set_global(adapter, "ShankLength", f"{SHANK_LEN}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Stepped blank: two coaxial on-axis circles (centre at the origin), so each
    # define_circle records ONLY its diameter dim -- the centre X/Z slots are
    # ignored. Name + record each sketch BEFORE its extrude absorbs it.
    # Head 0..HEAD_LENGTH (+X off the Right plane).
    head = SketchDims()
    check("create_sketch head", await adapter.create_sketch("Right"))
    await define_circle(
        adapter, 0.0, 0.0, HEAD_DIA / 2.0, "head", dims=head,
        names=("headCx", "headCz", "HeadDia"),
        drives=(None, None, '"HeadDia"'),
    )
    await ensure_fully_defined(adapter, "head sketch")
    check("exit_sketch head", await adapter.exit_sketch())
    name_last_feature(adapter, "HeadProfile")
    drive_jobs += head.apply(adapter, "HeadProfile")
    check(
        "extrude head",
        await adapter.create_extrusion(ExtrusionParameters(depth=HEAD_LENGTH)),
    )
    name_last_feature(adapter, "Head")
    # Name the extrude DEPTH dims so the drawing inserts them as the head-length
    # and under-head-length model dimensions (the depth is the first display
    # dim of a blind boss).
    name_dimensions(adapter, "Head", ["HeadLg"])

    # Shank HEAD_LENGTH..HEAD_LENGTH+SHANK_LEN: an offset-start extrude off the
    # head's outer face, so its depth dim IS the under-head length the print
    # carries (a plane-to-tip extrude would read head + shank).
    shank = SketchDims()
    check("create_sketch shank", await adapter.create_sketch("Right"))
    await define_circle(
        adapter, 0.0, 0.0, SHANK_DIA / 2.0, "shank", dims=shank,
        names=("shankCx", "shankCz", "ShankDia"),
        drives=(None, None, '"ShankDia"'),
    )
    await ensure_fully_defined(adapter, "shank sketch")
    check("exit_sketch shank", await adapter.exit_sketch())
    name_last_feature(adapter, "ShankProfile")
    drive_jobs += shank.apply(adapter, "ShankProfile")
    extrude_at_offset(adapter, SHANK_LEN, HEAD_LENGTH)
    name_last_feature(adapter, "Shank")
    name_dimensions(adapter, "Shank", ["ShankLg"])
    v_blank = math.pi * (
        (HEAD_DIA / 2.0) ** 2 * HEAD_LENGTH + (SHANK_DIA / 2.0) ** 2 * SHANK_LEN
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
        adapter,
        HEAD_DIA,
        HEAD_LENGTH,
        SHANK_DIA,
        SHANK_LEN,
        groove_count=GROOVE_COUNT,
        groove_dia=GROOVE_DIA,
    )

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
        },
    )
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
