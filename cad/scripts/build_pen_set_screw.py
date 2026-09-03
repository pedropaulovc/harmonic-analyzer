r"""Reproduction script: pen set screw (book ch. 24, pp. 64-65).

The small screw with the black knurled knob that threads up through the
pen frame's bottom rail to set the pen-to-paper angle. M4 finishing pass:
knob reeded with the spec-defined axial Ø1 mm grooves (tube-frame fluting recipe,
``_features.add_reeded_head_and_thread``) and a cosmetic #4-40 UNC thread on
the shank (annotation only -- keeps M6 interference checks clean).

The stepped body is two coaxial merged extrusions, NOT a profile revolve:
circular patterns of cuts on stepped REVOLVED bodies fail to create (see
``build_thumb_screw.py``).

Dimensions: cad/DIMENSIONS.md "Chapter 24" — photo-scaled (low); groove
count/size photo-estimated (low).

Layout: axis along +X from the knob face at x=0.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pen_set_screw.py
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
from pen_set_screw_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    END_VIEW_NOTE,
    GROOVE_COUNT,
    GROOVE_DIA,
    KNOB_DIA,
    KNOB_LENGTH,
    SHANK_DIA,
    SHANK_LEN,
)

PART_NAME = "pen-set-screw"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material

async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): the two step diameters + lengths. The
    # mm suffix is load-bearing -- this is an INCH document and the equation
    # manager reads BARE numbers in document units (an unsuffixed 9 = 9 in).
    # KnobLength/ShankLength are extrude DEPTHS (feature parameters) --
    # declared as knobs, but nothing in drive_jobs references them.
    await set_global(adapter, "KnobDia", f"{KNOB_DIA}mm")
    await set_global(adapter, "KnobLength", f"{KNOB_LENGTH}mm")
    await set_global(adapter, "ShankDia", f"{SHANK_DIA}mm")
    await set_global(adapter, "ShankLength", f"{SHANK_LEN}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Stepped blank: two coaxial on-axis circles (centre at the origin), so each
    # define_circle records ONLY its diameter dim -- the centre X/Z slots are
    # ignored. Name + record each sketch BEFORE its extrude absorbs it.
    # Knob 0..KNOB_LENGTH (+X off the Right plane).
    knob = SketchDims()
    check("create_sketch knob", await adapter.create_sketch("Right"))
    await define_circle(
        adapter, 0.0, 0.0, KNOB_DIA / 2.0, "knob", dims=knob,
        names=("knobCx", "knobCz", "KnobDia"),
        drives=(None, None, '"KnobDia"'),
    )
    await ensure_fully_defined(adapter, "knob sketch")
    check("exit_sketch knob", await adapter.exit_sketch())
    name_last_feature(adapter, "KnobProfile")
    drive_jobs += knob.apply(adapter, "KnobProfile")
    check(
        "extrude knob",
        await adapter.create_extrusion(ExtrusionParameters(depth=KNOB_LENGTH)),
    )
    name_last_feature(adapter, "Knob")
    # Name the extrude DEPTH dims so the drawing inserts them as the knob-length
    # and under-knob-length model dimensions (the depth is the first display
    # dim of a blind boss).
    name_dimensions(adapter, "Knob", ["KnobLg"])

    # Shank KNOB_LENGTH..KNOB_LENGTH+SHANK_LEN: an offset-start extrude off the
    # knob's outer face, so its depth dim IS the under-knob length the print
    # carries (a plane-to-tip extrude would read knob + shank).
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
    extrude_at_offset(adapter, SHANK_LEN, KNOB_LENGTH)
    name_last_feature(adapter, "Shank")
    name_dimensions(adapter, "Shank", ["ShankLg"])
    v_blank = math.pi * (
        (KNOB_DIA / 2.0) ** 2 * KNOB_LENGTH + (SHANK_DIA / 2.0) ** 2 * SHANK_LEN
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
        KNOB_DIA,
        KNOB_LENGTH,
        SHANK_DIA,
        SHANK_LEN,
        groove_count=GROOVE_COUNT,
        groove_dia=GROOVE_DIA,
    )

    from solidworks_mcp.adapters.base import CreateAxisParameters

    check(
        "create_axis ScrewAxis (Top ∩ Front)",
        await adapter.create_axis(
            CreateAxisParameters(mode="two_planes", planes=["Top Plane", "Front Plane"])
        ),
    )
    name_last_feature(adapter, "ScrewAxis")

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
