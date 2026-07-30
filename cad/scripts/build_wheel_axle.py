r"""Reproduction script: magnifying-wheel axle (book ch. 21, pp. 50-51).

The stud that mounts the magnifying wheel on its support bar: a flange
seated on the bar's front face, a O5 stud the wheel's bore rides, and a
retaining collar at the stud tip (the photo's washer + hex nut collapsed
to one round collar -- simplification).

Layout: axle axis +Y from the origin at the flange's bar-side face; the
assembly rotates it so +Y points -Z (machine front). Flange y 0..3,
stud 3..17, wheel hub rides 3..13, collar 13..17. Dimensions:
cad/DIMENSIONS.md ch. 21 (M6.4, low).

Built as three coaxial extrusions off the Top plane (flange disc, stud,
tip collar) rather than one revolved profile, so every manufacturing
diameter and length is a first-class named dimension the curated drawing
inserts as a model item (see wheel_axle_spec.DRAWING_DIMENSIONS).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_wheel_axle.py
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
    extrude_at_offset,
    force_rebuild,
    name_bore_axis,
    name_dimensions,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    volume_check,
)
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
    set_dimension_bilateral_tolerance,
)
from _fit_limits import deviations
from _part_pmi import author_part_pmi
from wheel_axle_spec import (
    COLLAR_DIA,
    COLLAR_LEN,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    FLANGE_DIA,
    FLANGE_LEN,
    GEOMETRIC_CONTROLS,
    PART_DATUMS,
    STUD_DIA,
    STUD_DIA_BAND,
    STUD_LEN,
    SURFACE_FINISHES,
)

PART_NAME = "wheel-axle"
MATERIAL = "Plain Carbon Steel"

_V_FLANGE = math.pi * (FLANGE_DIA / 2.0) ** 2 * FLANGE_LEN
_V_STUD = math.pi * (STUD_DIA / 2.0) ** 2 * STUD_LEN
_V_COLLAR = math.pi * ((COLLAR_DIA / 2.0) ** 2 - (STUD_DIA / 2.0) ** 2) * COLLAR_LEN
_V_TOTAL = _V_FLANGE + _V_STUD + _V_COLLAR


async def _assert_axle_com(adapter, label: str) -> None:
    """Pin the stack's direction: every extrusion must run +Y off the flange.

    Volume alone cannot tell a flipped extrusion (same material either side of
    the sketch plane), so assert the centre of mass sits on the axis at the
    analytic height of the flange->stud->collar stack.
    """
    res = await adapter.get_mass_properties()
    if not res.is_success:
        raise RuntimeError(f"{label}: get_mass_properties failed: {res.error}")
    com = [float(v) for v in res.data.center_of_mass]
    com_y = (
        _V_FLANGE * FLANGE_LEN / 2.0
        + _V_STUD * (FLANGE_LEN + STUD_LEN / 2.0)
        + _V_COLLAR * (FLANGE_LEN + STUD_LEN - COLLAR_LEN / 2.0)
    ) / _V_TOTAL
    if abs(com[0]) > 0.05 or abs(com[2]) > 0.05 or abs(com[1] - com_y) > 0.2:
        raise RuntimeError(
            f"{label}: centre of mass {com} is off the +Y stack "
            f"(expected [0, {com_y:.3f}, 0])"
        )


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): the three stepped diameters + the
    # three axial lengths. The mm suffix is load-bearing -- this is an INCH
    # document and the equation manager reads BARE numbers in document units
    # (an unsuffixed 14 = 14 in). Each profile/feature dim below is driven from
    # these via the deferred drive batch.
    await set_global(adapter, "FlangeDia", f"{FLANGE_DIA}mm")
    await set_global(adapter, "FlangeLen", f"{FLANGE_LEN}mm")
    await set_global(adapter, "StudDia", f"{STUD_DIA}mm")
    await set_global(adapter, "StudLen", f"{STUD_LEN}mm")
    await set_global(adapter, "CollarDia", f"{COLLAR_DIA}mm")
    await set_global(adapter, "CollarLen", f"{COLLAR_LEN}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Flange: O35 disc on the Top plane (normal +Y), y 0..3. On-axis circle,
    # so define_circle emits only the diameter dim.
    flange = SketchDims()
    check("create_sketch flange", await adapter.create_sketch("Top"))
    await define_circle(
        adapter,
        0.0,
        0.0,
        FLANGE_DIA / 2.0,
        "flange section",
        dims=flange,
        names=(None, None, "FlangeDia"),
        drives=(None, None, '"FlangeDia"'),
    )
    await ensure_fully_defined(adapter, "flange sketch")
    check("exit_sketch flange", await adapter.exit_sketch())
    name_last_feature(adapter, "FlangeProfile")
    drive_jobs += flange.apply(adapter, "FlangeProfile")
    check(
        "extrude flange",
        await adapter.create_extrusion(ExtrusionParameters(depth=FLANGE_LEN)),
    )
    name_last_feature(adapter, "Flange")
    flange_dims = name_dimensions(adapter, "Flange", ["FlangeLength"])
    drive_jobs += [(flange_dims[0], '"FlangeLen"')]
    await volume_check(adapter, "flange", _V_FLANGE, 0.005 * _V_FLANGE)

    # Stud: O5 bearing run from the flange face to the tip (y 3..17), started
    # at an offset so its length dim IS the flange-face -> tip length. The
    # start offset is a NAMED dim driven from "FlangeLen" (not a baked-in
    # literal), so editing FlangeLen in SolidWorks keeps the stud rooted on
    # the flange face and preserves the flange-face -> tip contract.
    stud = SketchDims()
    check("create_sketch stud", await adapter.create_sketch("Top"))
    await define_circle(
        adapter,
        0.0,
        0.0,
        STUD_DIA / 2.0,
        "stud section",
        dims=stud,
        names=(None, None, "StudDia"),
        drives=(None, None, '"StudDia"'),
    )
    await ensure_fully_defined(adapter, "stud sketch")
    check("exit_sketch stud", await adapter.exit_sketch())
    name_last_feature(adapter, "StudProfile")
    drive_jobs += stud.apply(adapter, "StudProfile")
    extrude_at_offset(adapter, STUD_LEN, FLANGE_LEN)
    name_last_feature(adapter, "Stud")
    # dim[0] = blind depth (StudLen); dim[1] = start offset (flange face).
    stud_dims = name_dimensions(adapter, "Stud", ["StudLength", "StudStart"])
    drive_jobs += [(stud_dims[0], '"StudLen"'), (stud_dims[1], '"FlangeLen"')]
    await volume_check(adapter, "flange+stud", _V_FLANGE + _V_STUD, 0.005 * _V_STUD)

    # Collar: O9 retainer around the stud tip (y 13..17). Its start offset is a
    # NAMED dim driven from the length globals ("FlangeLen" + "StudLen" -
    # "CollarLen"), so the collar top stays flush with the stud tip when any
    # length global changes -- no baked-in literal to drift.
    collar = SketchDims()
    check("create_sketch collar", await adapter.create_sketch("Top"))
    await define_circle(
        adapter,
        0.0,
        0.0,
        COLLAR_DIA / 2.0,
        "collar section",
        dims=collar,
        names=(None, None, "CollarDia"),
        drives=(None, None, '"CollarDia"'),
    )
    await ensure_fully_defined(adapter, "collar sketch")
    check("exit_sketch collar", await adapter.exit_sketch())
    name_last_feature(adapter, "CollarProfile")
    drive_jobs += collar.apply(adapter, "CollarProfile")
    extrude_at_offset(adapter, COLLAR_LEN, FLANGE_LEN + STUD_LEN - COLLAR_LEN)
    name_last_feature(adapter, "Collar")
    # dim[0] = blind depth (CollarLen); dim[1] = start offset (stud tip - collar).
    collar_dims = name_dimensions(adapter, "Collar", ["CollarLength", "CollarStart"])
    drive_jobs += [
        (collar_dims[0], '"CollarLen"'),
        (collar_dims[1], '"FlangeLen" + "StudLen" - "CollarLen"'),
    ]
    await volume_check(adapter, "axle", _V_TOTAL, 0.005 * _V_TOTAL)
    await _assert_axle_com(adapter, "axle")

    # Deferred drive equations, then re-check neutrality (each evaluates to the
    # as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven axle (equations neutral)", _V_TOTAL, 0.005 * _V_TOTAL
    )
    await _assert_axle_com(adapter, "driven axle (equations neutral)")

    # Named stud axis (local Y through the origin = the stack axis) so the
    # magnifying wheel revolves on it in the M6 mated-DOF assembly.
    await name_bore_axis(adapter, "Front Plane", 0.0, "Right Plane", 0.0, "stud axis")

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    set_dimension_bilateral_tolerance(
        adapter, "StudProfile", "StudDia", *deviations(STUD_DIA_BAND)
    )
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    # GD&T lives on the MODEL as plain annotations; the drawing imports it.
    author_part_pmi(
        adapter,
        datums=PART_DATUMS,
        controls=GEOMETRIC_CONTROLS,
        surface_finishes=SURFACE_FINISHES,
    )
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {"Manufacturing Notes": DRAWING_NOTES},
    )
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
