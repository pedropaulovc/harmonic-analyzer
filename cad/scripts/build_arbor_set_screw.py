r"""Reproduction script: cylinder-arbor apex set screw (MHA-147, #743; 2 used).

A #4-40 x 1/4 in hex socket cup-point set screw dropped radially through each
arbor pedestal's crown apex onto the arbor (user ruling on #743, Q3). Its cup
bears in a spot drilled into the arbor through the tap at fit-up.

PURCHASED, McMaster-Carr 91375A106 (arbor_set_screw_spec): modelled from
ASME B18.3 nominal geometry -- the body at the thread's major diameter, the
118-degree cup point and the hex socket -- pending the native comparison
against the vendor file.

Layout: revolved about +Y, the cup point's rim on the Top plane at y = 0 and
the socket face at y = LENGTH; the assembly stands it point-down on the arbor.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_arbor_set_screw.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    PANEL_BLACK,
    SketchDims,
    _early_bound,
    _feature_by_name,
    _read_member,
    add_line_chain,
    anchor_point_to_origin,
    apply_color,
    apply_custom_properties,
    apply_material,
    check,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    set_sketch_direct_db,
    volume_check,
)
from _fastener_catalog import fastener
from arbor_set_screw_spec import (
    CUP_DEPTH,
    CUP_DIA,
    HEX_AF,
    LENGTH,
    MAJOR_DIA,
    POINT_LENGTH,
    SOCKET_CHAMFER,
    SOCKET_DEPTH,
)
from _visibility import blank_reference_geometry
from diagnostics.diag_mcmaster_lib import (
    _rev_frustum,
    no_sketch_inference,
    offset_plane,
)

PART_NAME = "arbor-set-screw"
STOCK = fastener(PART_NAME)
MATERIAL = STOCK.material  # alloy steel, black oxide

MAJOR_R = MAJOR_DIA / 2.0
CUP_R = CUP_DIA / 2.0
SHANK_LEN = LENGTH  # the whole screw threads into the crown tap
V_BODY = (
    _rev_frustum(POINT_LENGTH, CUP_R, MAJOR_R)
    + math.pi * MAJOR_R**2 * (LENGTH - POINT_LENGTH - SOCKET_CHAMFER)
    + _rev_frustum(SOCKET_CHAMFER, MAJOR_R, MAJOR_R - SOCKET_CHAMFER)
    - _rev_frustum(CUP_DEPTH, CUP_R, 0.0)
)
V_SOCKET = math.sqrt(3.0) / 2.0 * HEX_AF**2 * SOCKET_DEPTH


async def author_set_screw(adapter, truth=None) -> float:
    """Author the screw body into the open, empty part and return its
    volume (mm^3). The production build and the 91375A106 vendor comparison
    (diagnostics/diag_build_91375A106) share this geometry; ``truth`` is the
    replica fleet's builder argument and is unused."""
    from solidworks_mcp.adapters.base import RevolveParameters

    await set_global(adapter, "MajorDia", f"{MAJOR_DIA}mm")
    await set_global(adapter, "ScrewLength", f"{LENGTH}mm")
    await set_global(adapter, "CupDia", f"{CUP_DIA}mm")
    await set_global(adapter, "PointLength", f"{POINT_LENGTH}mm")
    await set_global(adapter, "CupDepth", f"{CUP_DEPTH}mm")
    await set_global(adapter, "SocketChamfer", f"{SOCKET_CHAMFER}mm")

    drive_jobs: list[tuple[str, str]] = []

    # One revolved profile in the Front plane (sketch x = radius, y = axis):
    # cup apex on the axis -> cup rim -> point cone -> body -> socket-face
    # chamfer -> socket face -> back down the axis.
    prof = SketchDims()
    check("create_sketch profile", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    centerline = check(
        "axis", await adapter.add_centerline(0.0, CUP_DEPTH, 0.0, LENGTH)
    )
    cup = check("cup cone", await adapter.add_line(0.0, CUP_DEPTH, CUP_R, 0.0))
    point = check(
        "point cone", await adapter.add_line(CUP_R, 0.0, MAJOR_R, POINT_LENGTH)
    )
    body = check(
        "body",
        await adapter.add_line(
            MAJOR_R, POINT_LENGTH, MAJOR_R, LENGTH - SOCKET_CHAMFER
        ),
    )
    chamfer = check(
        "socket chamfer",
        await adapter.add_line(
            MAJOR_R, LENGTH - SOCKET_CHAMFER, MAJOR_R - SOCKET_CHAMFER, LENGTH
        ),
    )
    face = check(
        "socket face",
        await adapter.add_line(MAJOR_R - SOCKET_CHAMFER, LENGTH, 0.0, LENGTH),
    )
    closing = check(
        "axis closure", await adapter.add_line(0.0, LENGTH, 0.0, CUP_DEPTH)
    )
    set_sketch_direct_db(adapter, False)
    for label, a, b in (
        ("cup-point", f"{cup}.end", f"{point}.start"),
        ("point-body", f"{point}.end", f"{body}.start"),
        ("body-chamfer", f"{body}.end", f"{chamfer}.start"),
        ("chamfer-face", f"{chamfer}.end", f"{face}.start"),
        ("face-closure", f"{face}.end", f"{closing}.start"),
        ("closure-cup", f"{closing}.end", f"{cup}.start"),
        ("axis start", f"{centerline}.start", f"{cup}.start"),
        ("axis end", f"{centerline}.end", f"{face}.end"),
    ):
        check(label, await adapter.add_sketch_constraint(a, b, "coincident"))
    for label, ent, relation in (
        ("body", body, "vertical"),
        ("socket face", face, "horizontal"),
        ("axis closure", closing, "vertical"),
    ):
        check(
            f"{label} {relation}",
            await adapter.add_sketch_constraint(ent, None, relation),
        )
    # Cup apex on the axis at CupDepth above the Top plane.
    await anchor_point_to_origin(adapter, f"{cup}.start", 0.0, CUP_DEPTH, "cup apex")
    prof.record("CupDepth", '"CupDepth"')
    check(
        "cup rim radius",
        await adapter.add_sketch_dimension(
            f"{cup}.end", "origin", "horizontal_distance", CUP_R
        ),
    )
    prof.record("CupR", '"CupDia" / 2')
    check(
        "cup rim on the Top plane",
        await adapter.add_sketch_constraint(f"{cup}.end", "origin", "horizontal_points"),
    )
    check(
        "major radius",
        await adapter.add_sketch_dimension(
            f"{point}.end", "origin", "horizontal_distance", MAJOR_R
        ),
    )
    prof.record("MajorR", '"MajorDia" / 2')
    check(
        "point length",
        await adapter.add_sketch_dimension(
            f"{point}.end", "origin", "vertical_distance", POINT_LENGTH
        ),
    )
    prof.record("PointLength", '"PointLength"')
    check(
        "screw length",
        await adapter.add_sketch_dimension(
            f"{face}.end", "origin", "vertical_distance", LENGTH
        ),
    )
    prof.record("ScrewLength", '"ScrewLength"')
    check(
        "chamfer rise",
        await adapter.add_sketch_dimension(
            f"{chamfer}.start", f"{chamfer}.end", "vertical_distance", SOCKET_CHAMFER
        ),
    )
    prof.record("ChamferRise", '"SocketChamfer"')
    check(
        "chamfer run",
        await adapter.add_sketch_dimension(
            f"{chamfer}.start", f"{chamfer}.end", "horizontal_distance", SOCKET_CHAMFER
        ),
    )
    prof.record("ChamferRun", '"SocketChamfer"')
    await ensure_fully_defined(adapter, "set-screw profile")
    check("exit_sketch profile", await adapter.exit_sketch())
    name_last_feature(adapter, "BodyProfile")
    drive_jobs += prof.apply(adapter, "BodyProfile")
    check("revolve body", await adapter.create_revolve(RevolveParameters(angle=360.0)))
    name_last_feature(adapter, "Body")
    volume = await volume_check(adapter, "set-screw body", V_BODY, 0.01 * V_BODY)

    # Hex socket: a blind cut down from the socket face -- a sketch on a
    # Top-offset plane at the face, FeatureCut4 single-direction, default
    # direction (the 91255A148 / 92865A585 idiom, proven to cut down).
    offset_plane(adapter, "SocketFacePlane", LENGTH)
    check("create_sketch socket", await adapter.create_sketch("SocketFacePlane"))
    flat = HEX_AF / 2.0
    corner = HEX_AF / math.sqrt(3.0)
    with no_sketch_inference(adapter):
        await add_line_chain(
            adapter,
            [
                (0.0, corner),
                (-flat, corner / 2.0),
                (-flat, -corner / 2.0),
                (0.0, -corner),
                (flat, -corner / 2.0),
                (flat, corner / 2.0),
            ],
        )
    check("exit_sketch socket", await adapter.exit_sketch())
    name_last_feature(adapter, "SocketProfile")
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    fm = _early_bound(_read_member(model, "FeatureManager"), "IFeatureManager")
    model.ClearSelection2(True)
    _feature_by_name(adapter, "SocketProfile").Select2(False, 0)
    feat = fm.FeatureCut4(
        True, False, False,  # single, no flip, default dir
        0, 0, SOCKET_DEPTH / 1000.0, 0.0,  # blind to the socket floor
        False, False, False, False, 0.0, 0.0,
        False, False, False, False,
        False, False, True, False, False, False,
        0, 0.0, False, False,
    )
    if feat is None:
        raise RuntimeError("hex socket cut failed")
    name_last_feature(adapter, "HexSocket")
    blank_reference_geometry(adapter, (("SocketFacePlane", "PLANE"),))
    volume = await volume_check(
        adapter, "hex socket", volume - V_SOCKET, 0.02 * V_SOCKET
    )

    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven set screw (equations neutral)", volume, 0.01 * V_BODY
    )
    return volume


async def build(adapter) -> dict[str, str]:
    check("create_part", await adapter.create_part())
    await author_set_screw(adapter)
    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, PANEL_BLACK)
    # The purchased reference sheet reads these (build_stock_fastener's set).
    apply_custom_properties(
        adapter,
        {
            "Stock Name": STOCK.stock_name,
            "Supplier": STOCK.supplier,
            "Supplier SKUs": ", ".join(STOCK.skus),
        },
    )
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
