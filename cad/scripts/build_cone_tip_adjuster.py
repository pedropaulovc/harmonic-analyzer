r"""Reproduction script: cone tip adjuster screw (item 5, v4_t00471 / 7:49).

The partially hollow slotted screw threaded into the tip block along the
shaft axis: the cone shaft's 1/32" tip rests INSIDE its blind bore, so
turning it takes up the shaft's axial end play (the 20 gears must stay
registered against the cylinder set). The block's top slit + pinch screw
lock the setting (see build_cone_tip_block).

Body O6.2 x 14 authored along +Y from the SOUTH head face (origin):
blind bore O2 x 6 from the NORTH (far) end, driver slot across the head.

The Ø6.2 threaded shank is the repo's screw-in-tap convention -- tap-drill
6.528 (5/16-18, the mating cone-tip-block AdjusterBore) minus 0.3, matching the
lag-screw Ø12.0-in-Ø12.304 precedent (memory/fastener-policy-us-customary).
(Was Ø7.9 line-to-line into a plain Ø7.9 bore, before that bore became a native
5/16-18 Hole Wizard tapped hole.)

Run (SolidWorks already open)::

    uv run python cad\scripts\build_cone_tip_adjuster.py
"""

from __future__ import annotations

import math
import sys

from _fastener_catalog import fastener
from _common import (
    SketchDims,
    apply_material,
    check,
    define_centered_rectangle,
    define_circle,
    drive_dimension,
    ensure_fully_defined,
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
)
from cone_tip_adjuster_spec import DRAWING_DIMENSIONS, DRAWING_NOTES

PART_NAME = "cone-tip-adjuster"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material  # blued/black screw (t00471)

BODY_DIA = SPEC.model_diameter_mm  # 5/16-18 modeled thread minor diameter
BODY_LEN = SPEC.length_mm
CUP_DIA = 2.0  # blind bore the shaft tip rests in
CUP_DEPTH = 6.0
SLOT_W = 1.5
SLOT_D = 1.5


def _slot_strip_area(r: float, w: float) -> float:
    h = w / 2.0
    return 2.0 * (h * math.sqrt(r * r - h * h) + r * r * math.asin(h / r))


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import CreatePlaneParameters, ExtrusionParameters

    check("create_part", await adapter.create_part())
    await set_global(adapter, "BodyDia", f"{BODY_DIA}mm")
    await set_global(adapter, "BodyLen", f"{BODY_LEN}mm")
    await set_global(adapter, "CupDia", f"{CUP_DIA}mm")
    await set_global(adapter, "CupDepth", f"{CUP_DEPTH}mm")
    drive_jobs: list[tuple[str, str]] = []

    body = SketchDims()
    check("create_sketch body", await adapter.create_sketch("Top"))
    await define_circle(
        adapter, 0.0, 0.0, BODY_DIA / 2.0, "body", dims=body,
        names=("BodyCx", "BodyCz", "BodyDiaDim"), drives=(None, None, '"BodyDia"'),
    )
    await ensure_fully_defined(adapter, "body sketch")
    check("exit_sketch body", await adapter.exit_sketch())
    name_last_feature(adapter, "BodyProfile")
    drive_jobs += body.apply(adapter, "BodyProfile")
    check("extrude body", await adapter.create_extrusion(
        ExtrusionParameters(depth=BODY_LEN)))
    name_last_feature(adapter, "Body")
    # Name the extrude DEPTH so the body length is a markable drawing dimension.
    body_len_dim = name_dimensions(adapter, "Body", ["BodyLenDim"])
    drive_jobs += [(body_len_dim[0], '"BodyLen"')]
    v = math.pi * (BODY_DIA / 2.0) ** 2 * BODY_LEN
    volume = await volume_check(adapter, "body", v, 0.005 * v)

    # Blind cup from the NORTH end (y = BODY_LEN), CUP_DEPTH down.
    check("create_plane NorthEnd", await adapter.create_plane(
        CreatePlaneParameters(mode="offset", base_plane="Top Plane", offset=BODY_LEN)))
    name_last_feature(adapter, "NorthEnd")
    cup = SketchDims()
    check("create_sketch cup", await adapter.create_sketch("NorthEnd"))
    await define_circle(
        adapter, 0.0, 0.0, CUP_DIA / 2.0, "cup", dims=cup,
        names=("CupCx", "CupCz", "CupDiaDim"), drives=(None, None, '"CupDia"'),
    )
    await ensure_fully_defined(adapter, "cup sketch")
    check("exit_sketch cup", await adapter.exit_sketch())
    name_last_feature(adapter, "CupProfile")
    drive_jobs += cup.apply(adapter, "CupProfile")
    # A CUT's default direction is OPPOSITE the sketch normal (FeatureCut4
    # remarks): from the far-end plane it already bores DOWN into the body.
    check("cut cup", await adapter.create_cut_extrude(
        ExtrusionParameters(depth=CUP_DEPTH)))
    name_last_feature(adapter, "Cup")
    v_cup = math.pi * (CUP_DIA / 2.0) ** 2 * CUP_DEPTH
    volume = await volume_check(adapter, "cup", volume - v_cup, 0.02 * v_cup)

    # Driver slot across the SOUTH head face (origin plane), SLOT_D deep up.
    slot = SketchDims()
    check("create_sketch slot", await adapter.create_sketch("Top"))
    await define_centered_rectangle(
        adapter, BODY_DIA / 2.0 + 1.0, SLOT_W / 2.0, "slot", dims=slot,
        name_width="SlotLen", drive_width=None,
        name_depth="SlotWDim", drive_depth=None,
    )
    await ensure_fully_defined(adapter, "slot sketch")
    check("exit_sketch slot", await adapter.exit_sketch())
    name_last_feature(adapter, "SlotProfile")
    drive_jobs += slot.apply(adapter, "SlotProfile")
    # The head face is the ORIGIN plane with the body above it (+Y), so this
    # cut must run ALONG the sketch normal -- the reverse of a cut's default.
    check("cut slot", await adapter.create_cut_extrude(
        ExtrusionParameters(depth=SLOT_D, reverse_direction=True)))
    name_last_feature(adapter, "DriverSlot")
    v_slot = _slot_strip_area(BODY_DIA / 2.0, SLOT_W) * SLOT_D
    volume = await volume_check(adapter, "slot", volume - v_slot, 0.02 * v_slot)

    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven adjuster (equations neutral)", volume,
                       0.02 * v_slot)

    await name_bore_axis(adapter, "Front Plane", 0.0, "Right Plane", 0.0, "screw axis")
    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {"Manufacturing Notes": DRAWING_NOTES},
    )
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
