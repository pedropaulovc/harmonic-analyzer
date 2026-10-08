r"""Build the cone pivot post's cap jaw button (MHA-DT-005-TL-03; shop fixture).

A turned aluminium button that sits between a soft vise jaw and a cone-boss
cap of the built-up cone pivot post: the spigot centres in the journal bore
mouth and the shoulder carries the jaw load onto the cap
(``dt_cone_pivot_post_tl_cap_jaw_button_spec``). Two are made.

Layout: the jaw-face disc is a Right-plane circle extruded +X by its
thickness; the spigot is a second Right-plane circle extruded +X by the
overall length, so both axial sizes measure from the faced jaw face.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_dt_cone_pivot_post_tl_cap_jaw_button.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    SketchDims,
    _early_bound,
    apply_material,
    check,
    define_circle,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_dimensions,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    volume_check,
)
from _drawing_marks import (
    apply_drawing_precision,
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
    set_dimension_bilateral_tolerance,
)
from _fit_limits import deviations
from _saved_part_guard import require_saved_drawing_properties
from dt_cone_pivot_post_tl_cap_jaw_button_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    FACE_DIA,
    FACE_THICK,
    ISOMETRIC_VIEW_NOTE,
    OVERALL_LENGTH,
    SPIGOT_BAND,
    SPIGOT_DIA,
    SPIGOT_LENGTH,
)

PART_NAME = "dt-cone-pivot-post-tl-cap-jaw-button"
MATERIAL = "6061 Alloy"  # the registry row names the 6061-T6 bar
_SAVED_DRAWING_PROPERTIES = (
    "Number",
    "Material Specification",
    "Finish",
    "Quantity",
    "Isometric View Note",
)

V_FACE = math.pi * (FACE_DIA / 2.0) ** 2 * FACE_THICK
V_TOTAL = V_FACE + math.pi * (SPIGOT_DIA / 2.0) ** 2 * SPIGOT_LENGTH


def _require_one_solid_body(adapter, *, label: str) -> None:
    bodies = tuple(
        _early_bound(adapter.currentModel, "IPartDoc").GetBodies2(0, False) or ()
    )
    if len(bodies) != 1:
        raise RuntimeError(f"{label}: expected exactly one solid body, found {len(bodies)}")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # The mm suffix is load-bearing: the equation manager reads bare numbers
    # in document units.
    await set_global(adapter, "FaceDia", f"{FACE_DIA}mm")
    await set_global(adapter, "FaceThick", f"{FACE_THICK}mm")
    await set_global(adapter, "SpigotDia", f"{SPIGOT_DIA}mm")
    await set_global(adapter, "OverallLength", f"{OVERALL_LENGTH}mm")

    face = SketchDims()
    check("create_sketch face", await adapter.create_sketch("Right"))
    await define_circle(
        adapter,
        0.0,
        0.0,
        FACE_DIA / 2.0,
        "jaw face",
        dims=face,
        names=("FaceCx", "FaceCy", "FaceDia"),
        drives=(None, None, '"FaceDia"'),
    )
    await ensure_fully_defined(adapter, "jaw-face sketch")
    check("exit_sketch face", await adapter.exit_sketch())
    name_last_feature(adapter, "FaceProfile")
    drive_jobs = face.apply(adapter, "FaceProfile")
    check(
        "extrude face",
        await adapter.create_extrusion(ExtrusionParameters(depth=FACE_THICK)),
    )
    name_last_feature(adapter, "Face")
    drive_jobs.append((name_dimensions(adapter, "Face", ["FaceThick"])[0], '"FaceThick"'))
    await volume_check(adapter, "jaw face", V_FACE, 0.005 * V_FACE)

    spigot = SketchDims()
    check("create_sketch spigot", await adapter.create_sketch("Right"))
    await define_circle(
        adapter,
        0.0,
        0.0,
        SPIGOT_DIA / 2.0,
        "spigot",
        dims=spigot,
        names=("SpigotCx", "SpigotCy", "SpigotDia"),
        drives=(None, None, '"SpigotDia"'),
    )
    await ensure_fully_defined(adapter, "spigot sketch")
    check("exit_sketch spigot", await adapter.exit_sketch())
    name_last_feature(adapter, "SpigotProfile")
    drive_jobs += spigot.apply(adapter, "SpigotProfile")
    check(
        "extrude spigot",
        await adapter.create_extrusion(ExtrusionParameters(depth=OVERALL_LENGTH)),
    )
    name_last_feature(adapter, "Spigot")
    spigot_length = name_dimensions(adapter, "Spigot", ["OverallLength"])[0]
    drive_jobs.append((spigot_length, '"OverallLength"'))
    await volume_check(adapter, "button", V_TOTAL, 0.005 * V_TOTAL)
    _require_one_solid_body(adapter, label="button")

    await force_rebuild(adapter)
    for dimension_name, expression in drive_jobs:
        await drive_dimension(adapter, dimension_name, expression)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven button (equations neutral)", V_TOTAL, 0.005 * V_TOTAL
    )
    _require_one_solid_body(adapter, label="driven button")

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    set_dimension_bilateral_tolerance(
        adapter, "SpigotProfile", "SpigotDia", *deviations(SPIGOT_BAND)
    )
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_properties(adapter, PART_NAME, {"Isometric View Note": ISOMETRIC_VIEW_NOTE})
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(adapter, _SAVED_DRAWING_PROPERTIES)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
