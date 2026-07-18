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
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    volume_check,
)

PART_NAME = "pen-wire"
MATERIAL = "Plain Carbon Steel"  # see _common.apply_material docstring

WIRE_DIA = 0.8  # hair-thin in the photos; renderable stand-in (low)
CLEARANCE = 0.25  # surface stand-off (interference-gate margin convention)

# --- endpoint anchors (machine frame; asserted by build_pen_assembly) --------
WHEEL_X = 53.0  # magnifying-wheel centre (build_magnifier_assembly.WHEEL_X)
WHEEL_BAR_Y = 575.7  # wheel axis height = the vertical-tangent point's y
RIM_DIA = 100.0  # ch. 21 annotated (build_magnifying_wheel.RIM_OUTER_DIA)
WHEEL_MID_Z = -146.9  # rim groove mid-plane (wheel mid-plane)
WIRE_HOLE_Y = 513.0  # pen-rod wire hole: PEN_ROD_POS y 398 + local 115

# Hanging run: 0.25 off the rim surface at the pen-rod-side tangent, straight
# down to the wire-hole level (the wire passes 1.7 clear in front of the
# rod's z -149 front face -- the tie-off through the hole is implied).
WIRE_X = WHEEL_X - RIM_DIA / 2.0 - WIRE_DIA / 2.0 - CLEARANCE  # 2.35
WIRE_BOTTOM = (WIRE_X, WIRE_HOLE_Y, WHEEL_MID_Z)
WIRE_LEN = WHEEL_BAR_Y - WIRE_HOLE_Y  # 62.7


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
    drive_jobs.append(("D1@Wire", '"WireLength"'))
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
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
