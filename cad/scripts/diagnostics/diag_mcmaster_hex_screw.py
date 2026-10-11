"""Shared hex-screw recipe; explicit SKU sizes isolate its cache inputs."""

from __future__ import annotations

import math

import _telemetry  # noqa: E402
if __package__:
    from . import _script_paths  # noqa: F401
else:
    import _script_paths  # noqa: F401
from _check import check  # noqa: E402
from _feature_tree import name_last_feature  # noqa: E402
from _part_checks import volume_check  # noqa: E402
from diagnostics.diag_mcmaster_lib import (  # noqa: E402
    _rev_frustum,
    combine_union,
    insert_helix,
    offset_plane,
    thread_sweep_cut,
)


async def build_hex_screw(adapter, *, sku: str, size: tuple[float, ...]) -> None:
    """The hex-screw law harvested from 92240A539, at one under-head length.

    92240A540 matches 92240A539 in every catalog field but the under-head
    length, and every law below scales with that length alone (the helix
    spans ``L+P``).
    """
    from _com import _early_bound, _read_member  # noqa: E402 -- diagnostic path bootstrap
    from _feature_tree import _feature_by_name  # noqa: E402 -- diagnostic path bootstrap
    from _sketch import add_line_chain  # noqa: E402 -- diagnostic path bootstrap
    from diagnostics.diag_mcmaster_lib import no_sketch_inference, split_at_plane
    from solidworks_mcp.adapters.base import ExtrusionParameters, RevolveParameters

    (
        MAJOR_DIAMETER_MM,
        length_mm,
        HEX_WIDTH_MM,
        HEX_HEIGHT_MM,
        PITCH_MM,
        WASHER_DEPTH_MM,
        UNDERSIDE_MM,
    ) = size
    HEAD_TOP_MM = UNDERSIDE_MM + HEX_HEIGHT_MM

    tip_mm = UNDERSIDE_MM - length_mm
    major_r = MAJOR_DIAMETER_MM / 2.0
    sharp_thread_h = PITCH_MM * math.sqrt(3.0) / 2.0
    root_r = major_r - 0.75 * sharp_thread_h
    flat_r = HEX_WIDTH_MM / 2.0
    hex_r = HEX_WIDTH_MM / math.sqrt(3.0)

    # Vendor equations: Chamfer1=P*.75 and washer depth=HW*.025.  Sketch7's
    # harvested radial inset is 0.0635 mm, exactly one percent of thread OD.
    tip_chamfer = PITCH_MM * 0.75
    tip_flat_r = major_r - tip_chamfer
    washer_r = flat_r - MAJOR_DIAMETER_MM * 0.01
    washer_depth = WASHER_DEPTH_MM

    # Shank profile: Front sketch X is radius; Y is vendor axial Z.  Folding
    # the separately-authored vendor chamfer into this revolve preserves its
    # exact final cylinder, cone, and tip-plane faces deterministically.
    check("create_sketch shank", await adapter.create_sketch("Front"))
    sketch = adapter.currentSketchManager
    with no_sketch_inference(adapter):
        if (
            sketch.CreateCenterLine(
                0.0,
                UNDERSIDE_MM / 1000.0,
                0.0,
                0.0,
                tip_mm / 1000.0,
                0.0,
            )
            is None
        ):
            raise RuntimeError(f"{sku} shank: CreateCenterLine failed")
        await add_line_chain(
            adapter,
            [
                (0.0, UNDERSIDE_MM),
                (major_r, UNDERSIDE_MM),
                (major_r, tip_mm + tip_chamfer),
                (tip_flat_r, tip_mm),
                (0.0, tip_mm),
            ],
        )
    check("exit_sketch shank", await adapter.exit_sketch())
    name_last_feature(adapter, "ShankProfile")
    check(
        "revolve shank",
        await adapter.create_revolve(RevolveParameters(angle=360.0, is_cut=False)),
    )
    name_last_feature(adapter, "Shank")
    shank_volume = math.pi * major_r**2 * (length_mm - tip_chamfer) + _rev_frustum(
        tip_chamfer, major_r, tip_flat_r
    )
    await volume_check(adapter, "shank revolve", shank_volume, 0.005 * shank_volume)

    # The Top plane is exactly vendor Z=0: head goes +Y, washer face goes -Y.
    check("create_sketch hex", await adapter.create_sketch("Top"))
    with no_sketch_inference(adapter):
        await add_line_chain(
            adapter,
            [
                (0.0, hex_r),
                (-flat_r, hex_r / 2.0),
                (-flat_r, -hex_r / 2.0),
                (0.0, -hex_r),
                (flat_r, -hex_r / 2.0),
                (flat_r, hex_r / 2.0),
            ],
        )
    check("exit_sketch hex", await adapter.exit_sketch())
    name_last_feature(adapter, "HexProfile")
    check(
        "extrude hex",
        await adapter.create_extrusion(ExtrusionParameters(depth=HEX_HEIGHT_MM)),
    )
    name_last_feature(adapter, "HexHead")
    hex_volume = HEX_WIDTH_MM**2 * math.sqrt(3.0) / 2.0 * HEX_HEIGHT_MM
    await volume_check(
        adapter,
        "hex head",
        shank_volume + hex_volume,
        0.005 * hex_volume,
    )

    # Circular washer boss below the hex.  Its core overlaps the shank, so the
    # observable added volume is the annulus rather than the complete disk.
    check("create_sketch washer", await adapter.create_sketch("Top"))
    with no_sketch_inference(adapter):
        if (
            adapter.currentSketchManager.CreateCircleByRadius(
                0.0, 0.0, 0.0, washer_r / 1000.0
            )
            is None
        ):
            raise RuntimeError("washer circle failed")
    check("exit_sketch washer", await adapter.exit_sketch())
    name_last_feature(adapter, "WasherProfile")
    check(
        "washer face",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=washer_depth, reverse_direction=True)
        ),
    )
    name_last_feature(adapter, "WasherFace")
    washer_volume = math.pi * (washer_r**2 - major_r**2) * washer_depth
    await volume_check(
        adapter,
        "washer face",
        shank_volume + hex_volume + washer_volume,
        0.05 * washer_volume,
    )

    # At +HH, retain the r=HW/2 circle and cut the six corner regions.  The
    # 60-degree draft is measured from the screw axis, matching Cut-Extrude1.
    offset_plane(adapter, "HeadTopPlane", HEAD_TOP_MM)
    check("create_sketch trim", await adapter.create_sketch("HeadTopPlane"))
    with no_sketch_inference(adapter):
        if (
            adapter.currentSketchManager.CreateCircleByRadius(
                0.0, 0.0, 0.0, flat_r / 1000.0
            )
            is None
        ):
            raise RuntimeError("head trim circle failed")
    check("exit_sketch trim", await adapter.exit_sketch())
    name_last_feature(adapter, "TrimProfile")

    model = _early_bound(adapter.currentModel, "IModelDoc2")
    model.ClearSelection2(True)
    _feature_by_name(adapter, "TrimProfile").Select2(False, 0)
    feature_manager = _early_bound(
        _read_member(model, "FeatureManager"), "IFeatureManager"
    )
    trim = feature_manager.FeatureCut4(
        True,
        True,
        False,  # single-ended, cut outside the circle, default direction
        1,
        0,
        0.0,
        0.0,  # direction 1 Through All
        True,
        False,
        False,
        False,  # direction-1 draft; empirical vendor sense
        math.radians(60.0),
        0.0,
        False,
        False,
        False,
        False,
        False,
        False,
        True,  # normal cut, feature scope off, auto-select on
        False,
        False,
        False,
        0,
        0.0,
        False,
        False,
    )
    if trim is None:
        raise RuntimeError("corner trim cut failed")
    name_last_feature(adapter, "CornerTrim")

    # The vendor split lies at the under-head plane.  Build-frame body boxes
    # are [xmin, ymin, zmin, xmax, ymax, zmax], so Y identifies the shank.
    body_boxes = split_at_plane(adapter, "Top Plane", "HeadSplit")
    shank_name = None
    for body in body_boxes:
        box = body["box_mm"]
        if box and box[1] < UNDERSIDE_MM - 1.0:
            shank_name = body["name"]
            break
    if shank_name is None:
        raise RuntimeError("split produced no shank body")
    _telemetry.info(f"shank body: {shank_name}")

    # A Top-parallel plane at -L gives an ascending tip-seeded helix.  The
    # helper plane's orientation represents the vendor's clockwise+reversed
    # read-back as the equivalent false+false pair while growing toward +Y.
    offset_plane(adapter, "TipPlane", tip_mm)
    check("create_sketch helix seed", await adapter.create_sketch("TipPlane"))
    with no_sketch_inference(adapter):
        if (
            adapter.currentSketchManager.CreateCircleByRadius(
                0.0, 0.0, 0.0, major_r / 1000.0
            )
            is None
        ):
            raise RuntimeError("helix seed circle failed")
    insert_helix(
        adapter,
        PITCH_MM,
        length_mm / PITCH_MM + 1.0,
        clockwise=False,
        reversed_dir=False,
        start_angle_rad=math.pi / 2.0,
        feature_name="ThreadHelix",
    )

    # The cutter is the harvested symmetric 60-degree thread profile.  Its
    # crest deliberately extends beyond the major cylinder and beyond both
    # axial ends; body scoping clips the sweep to the split shank.
    cutter_center = tip_mm - 7.0 * PITCH_MM / 16.0
    cutter_outer_r = major_r + sharp_thread_h / 16.0
    check("create_sketch cutter", await adapter.create_sketch("Front"))
    with no_sketch_inference(adapter):
        await add_line_chain(
            adapter,
            [
                (cutter_outer_r, cutter_center + 15.0 * PITCH_MM / 32.0),
                (root_r, cutter_center + PITCH_MM / 16.0),
                (root_r, cutter_center - PITCH_MM / 16.0),
                (cutter_outer_r, cutter_center - 15.0 * PITCH_MM / 32.0),
            ],
        )
    check("exit_sketch cutter", await adapter.exit_sketch())
    name_last_feature(adapter, "ThreadCutter")
    thread_sweep_cut(
        adapter,
        "ThreadCutter",
        "ThreadHelix",
        shank_name,
        "ThreadGroove",
        tangency=(0, 0),
    )

    # The sweep is intentionally authored while split so it cannot cut the
    # head. Vendor Combine1 is an additive union back to one watertight body.
    combine_union(adapter, "BodyUnion")

    # Vendor Sketch8 is owned by the washer boss's -Y face, not an offset
    # plane. Boss-Extrude3 reverses from that face to the hex underside face
    # (deprecated UpToSurface=4). The extrusion overlaps the washer boss, but
    # its native merge coalesces the annular planar/side faces exactly as the
    # vendor feature does; replay the references rather than substituting a
    # blind distance.
    from _holes import find_planar_face
    from solidworks_mcp.adapters.pywin32_adapter import null_callout

    washer_bottom = find_planar_face(
        model,
        (0.0, -1.0, 0.0),
        [[4.0, -washer_depth, 0.0]],
        tol_mm=0.02,
    )
    head_underside = find_planar_face(
        model,
        (0.0, -1.0, 0.0),
        [[0.0, 0.0, 6.0]],
        tol_mm=0.02,
    )
    if washer_bottom is None or head_underside is None:
        raise RuntimeError("vendor washer-transition reference faces not found")

    model.ClearSelection2(True)
    if not _early_bound(washer_bottom, "IEntity").Select4(False, null_callout()):
        raise RuntimeError("washer-bottom sketch face selection failed")
    sketch_manager = _early_bound(model.SketchManager, "ISketchManager")
    sketch_manager.InsertSketch(True)
    with no_sketch_inference(adapter):
        if (
            sketch_manager.CreateCircleByRadius(0.0, 0.0, 0.0, washer_r / 1000.0)
            is None
        ):
            raise RuntimeError("washer-transition circle failed")
    sketch_manager.InsertSketch(True)
    name_last_feature(adapter, "WasherMergeProfile")

    model.ClearSelection2(True)
    if not _feature_by_name(adapter, "WasherMergeProfile").Select2(False, 0):
        raise RuntimeError("washer-merge profile selection failed")
    selection_manager = _early_bound(model.SelectionManager, "ISelectionMgr")
    end_select = selection_manager.CreateSelectData()
    end_select = _early_bound(end_select, "ISelectData")
    end_select.Mark = 1
    if not _early_bound(head_underside, "IEntity").Select4(True, end_select):
        raise RuntimeError("washer-merge end-face selection failed")
    washer_merge = feature_manager.FeatureExtrusion3(
        True,
        False,
        True,
        4,
        0,
        0.0,
        0.0,
        False,
        False,
        False,
        False,
        0.0,
        0.0,
        False,
        False,
        False,
        False,
        True,
        False,
        True,
        0,
        0.0,
        False,
    )
    if washer_merge is None:
        raise RuntimeError("under-head face-merging extrusion failed")
    name_last_feature(adapter, "WasherMerge")

    # Cyclic, right-handed frame map: (model X,Y,Z) -> (vendor Y,Z,X).
    adapter._mcm_com_map = lambda value: [value[1], value[2], value[0]]
