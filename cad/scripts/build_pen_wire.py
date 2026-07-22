r"""Reproduction script: pen wire -- WIRE 2 of the amplification chain (book
ch. 21/24, pp. 50-53 / 60-61).

The steel wire that leaves the magnifying wheel's 100 mm rim groove and
carries the pen rod (ch. 24: "square brass rod attached to the wire from the
magnifying wheel"). The pen rod's wire hole sits exactly one rim radius east
of the wheel axis, so the hanging run is the vertical tangent off the rim's
3 o'clock point down to the hole. Modeled as the STRAIGHT REST-POSE RUN only
-- the rim wrap over the wheel top and the tie-off knot are NOT modeled (the
kinematic coupling stays a Motion-study scotch-yoke -- docs/motion-policy.md);
the run stands 0.25 off the rim surface so the interference gate reads zero.

Endpoint derivation lives HERE; ``build_pen_assembly`` imports
``WIRE_BOTTOM``/``WIRE_LEN`` and asserts them against its own layout anchors
(pen-rod wire hole at machine y 513, wheel bar y 575.7), so a layout move
fails loud instead of leaving a floating wire.

Dimensions: cad/config/dimensions.yaml ch. 21/24 -- wire dia photo-scaled
(the book wire is hair-thin; 0.8 keeps it renderable, low confidence).

Layout: wire axis along +Y from the origin (bottom end at the pen-rod wire
hole level; the assembly places it upright), length ``WIRE_LEN``.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pen_wire.py
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
)
from pen_wire_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    ELEVATION_VIEW_NOTE,
    ISOMETRIC_VIEW_NOTE,
)

PART_NAME = "pen-wire"
MATERIAL = "Plain Carbon Steel"  # see _common.apply_material docstring

# Geometry nominals (wire dia, endpoint anchors, run length) live in
# pen_wire_geom -- the prose-free module build_pen_assembly imports -- and are
# re-imported here so the build and the assembly can never drift.
from pen_wire_geom import (  # noqa: E402
    CLEARANCE,
    RIM_DIA,
    WHEEL_BAR_Y,
    WHEEL_MID_Z,
    WHEEL_X,
    WIRE_BOTTOM,
    WIRE_DIA,
    WIRE_HOLE_Y,
    WIRE_LEN,
    WIRE_X,
)


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). The mm suffix is load-bearing -- this
    # is an INCH document and the equation manager reads BARE numbers in
    # document units (an unsuffixed 52 = 52 in).
    await set_global(adapter, "WireDia", f"{WIRE_DIA}mm")
    await set_global(adapter, "WireLength", f"{WIRE_LEN}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Wire body: on-axis circle (centre at the origin), so define_circle emits
    # only the diameter dim; extruded +Y for the full run length.
    body = SketchDims()
    check("create_sketch wire", await adapter.create_sketch("Top"))
    await define_circle(
        adapter, 0.0, 0.0, WIRE_DIA / 2.0, "wire", dims=body,
        names=("WireCx", "WireCz", "WireDiaDim"),
        drives=(None, None, '"WireDia"'),
    )
    await ensure_fully_defined(adapter, "wire sketch")
    check("exit_sketch wire", await adapter.exit_sketch())
    name_last_feature(adapter, "WireProfile")
    drive_jobs += body.apply(adapter, "WireProfile")
    check(
        "extrude wire",
        await adapter.create_extrusion(ExtrusionParameters(depth=WIRE_LEN)),
    )
    name_last_feature(adapter, "Wire")
    # Name the extrude depth "Depth" so the drawing can mark the run length
    # (mirrors build_crankshaft's Shaft/Depth); the drive now targets that name.
    length_dim = name_dimensions(adapter, "Wire", ["Depth"])
    drive_jobs.append((length_dim[0], '"WireLength"'))
    v_wire = math.pi * (WIRE_DIA / 2.0) ** 2 * WIRE_LEN
    await volume_check(adapter, "wire", v_wire, 0.005 * v_wire)

    # Apply the deferred drive equations after the whole model + a rebuild
    # exists, then re-check: every equation evaluates to the value just built,
    # so the geometry must not move.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven pen wire (equations neutral)", v_wire, 0.005 * v_wire)

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
            "Elevation View Note": ELEVATION_VIEW_NOTE,
            "Isometric View Note": ISOMETRIC_VIEW_NOTE,
        },
    )
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
