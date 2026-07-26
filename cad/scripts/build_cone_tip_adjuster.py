r"""Reproduction script: cone tip adjuster screw (item 5, v4_t00471 / 7:49).

The partially hollow slotted screw threaded into the tip block along the
shaft axis: the cone shaft's 1/32" tip rests INSIDE its blind bore, so
turning it takes up the shaft's axial end play (the 20 gears must stay
registered against the cylinder set). The block's top slit + pinch screw
lock the setting (see build_cone_tip_block).

Body O6.2 x 14 cosmetic-thread envelope authored along +Y from the SOUTH head face (origin):
blind bore O2 x 6 from the NORTH (far) end, driver slot across the head.

The physical cylinder is the interference-safe thread-minor envelope; the
cosmetic thread and UNC-2A drawing callout carry the standard major diameter,
thread form, and limits.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_cone_tip_adjuster.py
"""

from __future__ import annotations

import math
import sys

import _telemetry
from _fastener_catalog import fastener
from _common import (
    SketchDims,
    _early_bound,
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
from cone_tip_adjuster_spec import (
    CHAMFER,
    CUP_DEPTH,
    CUP_DIA,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    SLOT_D,
    SLOT_W,
)

PART_NAME = "cone-tip-adjuster"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material  # black-oxide screw (t00471)

BODY_DIA = SPEC.model_diameter_mm  # interference-safe modeled thread minor envelope
BODY_LEN = SPEC.length_mm
# Cup/slot geometry comes from cone_tip_adjuster_spec — the drawing's single
# source of the marked dimensions — so a spec correction rebuilds the SLDPRT
# from the same values the print annotates.


def _slot_strip_area(r: float, w: float) -> float:
    h = w / 2.0
    return 2.0 * (h * math.sqrt(r * r - h * h) + r * r * math.asin(h / r))


def _slotted_rim_chamfer_volume(r: float, chamfer: float, slot_w: float) -> float:
    """45-degree rim-chamfer volume remaining after a centered through-slot."""
    centroid_radius = r - chamfer / 3.0
    slot_half = slot_w / 2.0
    if not 0.0 < slot_half < centroid_radius:
        raise ValueError("slot must remove less than the full chamfer rim")
    full_volume = math.pi * chamfer**2 * centroid_radius
    missing_fraction = 2.0 * math.asin(slot_half / centroid_radius) / math.pi
    return full_volume * (1.0 - missing_fraction)


@_telemetry.traced("feature.cosmetic_thread")
def _insert_cosmetic_thread(adapter) -> bool:
    """Attach the catalog cosmetic thread to the exact north-end outer edge."""
    part = _early_bound(adapter.currentModel, "IPartDoc")
    bodies = part.GetBodies2(0, False) or []  # swSolidBody
    candidates = []
    for body in bodies:
        body = _early_bound(body, "IBody2")
        for edge in body.GetEdges() or []:
            edge = _early_bound(edge, "IEdge")
            curve = edge.GetCurve()
            if curve is None:
                continue
            curve = _early_bound(curve, "ICurve")
            if not curve.IsCircle():
                continue
            params = tuple(float(value) * 1000.0 for value in curve.CircleParams)
            candidates.append((params[6], params[1], edge))
    radius, centre_y, edge = min(
        candidates,
        key=lambda item: abs(item[0] - BODY_DIA / 2.0)
        + abs(item[1] - BODY_LEN),
    )
    if abs(radius - BODY_DIA / 2.0) > 0.01 or abs(centre_y - BODY_LEN) > 0.01:
        return False

    model = _early_bound(adapter.currentModel, "IModelDoc2")
    model.ClearSelection2(True)
    selection_manager = _early_bound(
        model.SelectionManager, "ISelectionMgr"
    )
    selection_data = selection_manager.CreateSelectData()
    selectable = _early_bound(edge, "IEntity")
    if not selectable.Select4(False, selection_data):
        return False
    manager = _early_bound(
        model.FeatureManager, "IFeatureManager"
    )
    feature = manager.InsertCosmeticThread3(
        0, "", SPEC.thread, 0.0, 0, BODY_LEN / 1000.0, ""
    )
    model.ClearSelection2(True)
    return feature is not None


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import (
        CreatePlaneParameters,
        ExtrusionParameters,
    )

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

    # The physical solid is the interference-safe minor envelope; this annotation
    # gives drawings the standard external-thread
    # representation and designation. Select the exact circular edge by its
    # measured radius/axis station: coordinate picking is view-dependent and
    # failed even in a square-on view, while IEntity.Select4 is deterministic.
    if not _insert_cosmetic_thread(adapter):
        raise RuntimeError(f"failed to insert cosmetic thread {SPEC.thread}")

    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven adjuster (equations neutral)", volume,
                       0.02 * v_slot)

    # Break both external thread starts after the cup and driver slot exist.
    # The slotted south rim is two disjoint arcs, so both surviving arcs must be
    # selected; the north rim remains one complete circle.
    radius = BODY_DIA / 2.0
    check(
        "chamfer both thread starts",
        await adapter.add_chamfer(
            CHAMFER,
            [
                [0.0, 0.0, radius],
                [0.0, 0.0, -radius],
                [0.0, BODY_LEN, radius],
            ],
        ),
    )
    name_last_feature(adapter, "ThreadStartChamfers")
    # Full north-rim 45-degree chamfer removal by Pappus. The centered driver
    # slot removes a calculable arc fraction from the south rim before its
    # chamfer is cut, so account for that missing circumference explicitly.
    v_one_chamfer = math.pi * CHAMFER**2 * (radius - CHAMFER / 3.0)
    v_slotted_chamfer = _slotted_rim_chamfer_volume(
        radius, CHAMFER, SLOT_W
    )
    volume = await volume_check(
        adapter,
        "thread-start chamfers",
        volume - v_one_chamfer - v_slotted_chamfer,
        0.05 * v_one_chamfer,
    )

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
