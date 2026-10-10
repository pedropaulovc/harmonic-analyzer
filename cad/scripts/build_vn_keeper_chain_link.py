r"""Purchased loop link for the keeper chain: McMaster-Carr 3606T811 (MHA-VN-036).

The brass trade-size-3 loop link that closes the cut chain into one loop: a
rolled capsule, domed at both ends, with an end bead caught in each dome
behind a crimp. Each dome has a side mouth on +Y narrower than a bead: the
end bead snaps in as the wall flexes and cannot come back out, its rod riding
a slot along the top to the tip hole. McMaster gives no dimensions or CAD,
so the shape follows its 3606T811 photograph at the listed 9 mm length (see
``vn_keeper_chain_spec``). The axis is local X, the openings on +Y, and the origin at
mid-length.

Recipe (only features this seat has built cleanly): a mid-plane tube, two
revolved domes, a mid-plane bore cut and two revolved dome cavities, two
revolved crimp grooves, a mid-plane tip-hole cut, and the two bead mouths
and the rod slot cut through the +Y wall. The volume is proved against the spec's
own CSG, and the openings' side by the centre of mass.

Run with SolidWorks open::

    uv run python cad\scripts\build_vn_keeper_chain_link.py
"""

from __future__ import annotations

import sys

import _config
import _telemetry
from _appearance import apply_material
from _check import check
from _com import _early_bound
from _custom_properties import apply_custom_properties
from _feature_tree import name_last_feature
from _part_checks import report_mass_properties, volume_check
from _part_save import save_part_and_images
from _session import run_build
from _sketch import (
    SketchDims,
    anchor_point_to_origin,
    add_line_chain,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _sketch_chains import define_rectilinear_chain
from _sketch_circle import define_circle
from _sketch_rectangle import define_centered_rectangle
from _drawing_marks import apply_drawing_properties
from _saved_part_guard import require_saved_drawing_properties
from vn_keeper_chain_spec import (
    LINK_DRAWING_NOTES,
    LINK_CRIMP_DEPTH,
    LINK_CRIMP_X,
    LINK_END_BEAD_X,
    LINK_LENGTH,
    LINK_OD,
    LINK_SLOT_WIDTH,
    LINK_TIP_HOLE,
    LINK_WALL,
    LINK_MOUTH_LENGTH,
    LINK_MOUTH_WIDTH,
    link_volume,
)

PART_NAME = "vn-keeper-chain-link"
MATERIAL = "Brass"
_PART = _config.parts(PART_NAME)
STOCK_PROPERTIES = {
    "Stock Name": str(_PART["stock_name"]),
    "Supplier": str(_PART["supplier"]),
    "Supplier SKUs": ", ".join(str(sku) for sku in _PART["supplier_skus"]),
}

CRIMP_R = 0.3  # the crimp tool's radius (vn_keeper_chain_spec._link_solid)


async def _circle_on(adapter, plane: str, dia: float, label: str) -> None:
    check(f"create_sketch {label}", await adapter.create_sketch(plane))
    await define_circle(adapter, 0.0, 0.0, dia / 2.0, label, dims=SketchDims())
    await ensure_fully_defined(adapter, f"{label} sketch")
    check(f"exit_sketch {label}", await adapter.exit_sketch())


async def _sphere(adapter, x0: float, r: float, name: str, *, cut: bool) -> None:
    """A sphere at (x0, 0, 0): a Front-plane half disc revolved about its chord."""
    from solidworks_mcp.adapters.base import RevolveParameters

    check(f"create_sketch {name}", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    check(f"{name} axis", await adapter.add_centerline(x0, -r, x0, r))
    arc = check(f"{name} arc", await adapter.add_arc(x0, 0.0, x0, -r, x0, r))
    closer = check(f"{name} chord", await adapter.add_line(x0, r, x0, -r))
    set_sketch_direct_db(adapter, False)
    await anchor_point_to_origin(adapter, f"{arc}.center", x0, 0.0, f"{name} centre")
    check(f"{name} radius", await adapter.add_sketch_dimension(arc, None, "radial", r))
    check(f"{name} chord vertical", await adapter.add_sketch_constraint(closer, None, "vertical"))
    check(
        f"{name} arc start under centre",
        await adapter.add_sketch_constraint(f"{arc}.start", f"{arc}.center", "vertical_points"),
    )
    await ensure_fully_defined(adapter, f"{name} sketch")
    check(f"exit_sketch {name}", await adapter.exit_sketch())
    name_last_feature(adapter, f"{name}Profile")
    check(
        f"revolve {name}",
        await adapter.create_revolve(RevolveParameters(angle=360.0, is_cut=cut)),
    )
    name_last_feature(adapter, name)


async def _crimp(adapter, x0: float, name: str) -> None:
    """A crimp groove at x0: a Front-plane circle revolved about the X axis."""
    from solidworks_mcp.adapters.base import RevolveParameters

    centre_y = LINK_OD / 2.0 + CRIMP_R - LINK_CRIMP_DEPTH
    check(f"create_sketch {name}", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    axis = check(f"{name} axis", await adapter.add_centerline(0.0, 0.0, 1.0, 0.0))
    set_sketch_direct_db(adapter, False)
    check(f"{name} axis horizontal", await adapter.add_sketch_constraint(axis, None, "horizontal"))
    await anchor_point_to_origin(adapter, f"{axis}.start", 0.0, 0.0, f"{name} axis")
    check(f"{name} axis length", await adapter.add_sketch_dimension(axis, None, "linear", 1.0))
    await define_circle(adapter, x0, centre_y, CRIMP_R, f"{name} tool", dims=SketchDims())
    await ensure_fully_defined(adapter, f"{name} sketch")
    check(f"exit_sketch {name}", await adapter.exit_sketch())
    name_last_feature(adapter, f"{name}Profile")
    check(
        f"revolve cut {name}",
        await adapter.create_revolve(RevolveParameters(angle=360.0, is_cut=True)),
    )
    name_last_feature(adapter, name)


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())
    e = LINK_END_BEAD_X
    r_out = LINK_OD / 2.0
    r_in = r_out - LINK_WALL

    # Right Plane's normal is X: mid-plane extrusions run along the axis.
    await _circle_on(adapter, "Right", LINK_OD, "tube")
    name_last_feature(adapter, "TubeProfile")
    check(
        "extrude tube",
        await adapter.create_extrusion(ExtrusionParameters(depth=2.0 * e, both_directions=True)),
    )
    name_last_feature(adapter, "Tube")
    await _sphere(adapter, -e, r_out, "DomeEye", cut=False)
    await _sphere(adapter, e, r_out, "DomeRing", cut=False)

    await _circle_on(adapter, "Right", 2.0 * r_in, "bore")
    name_last_feature(adapter, "BoreProfile")
    check(
        "cut bore",
        await adapter.create_cut_extrude(ExtrusionParameters(depth=2.0 * e, both_directions=True)),
    )
    name_last_feature(adapter, "Bore")
    await _sphere(adapter, -e, r_in, "CupEye", cut=True)
    await _sphere(adapter, e, r_in, "CupRing", cut=True)

    await _crimp(adapter, -LINK_CRIMP_X, "CrimpEye")
    await _crimp(adapter, LINK_CRIMP_X, "CrimpRing")

    await _circle_on(adapter, "Right", LINK_TIP_HOLE, "tip holes")
    name_last_feature(adapter, "TipHoleProfile")
    check(
        "cut tip holes",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=LINK_LENGTH + 2.0, both_directions=True)
        ),
    )
    name_last_feature(adapter, "TipHoles")

    # The two bead mouths and the rod slot go through the +Y wall only. A
    # Top-plane sketch maps (x, y) -> global (X, -Z); the mouths are centred on
    # the domes at x = +/-LINK_END_BEAD_X.
    for name, centre_x, half_x, half_z in (
        ("MouthEye", -e, LINK_MOUTH_LENGTH / 2.0, LINK_MOUTH_WIDTH / 2.0),
        ("MouthRing", e, LINK_MOUTH_LENGTH / 2.0, LINK_MOUTH_WIDTH / 2.0),
        ("RodSlot", 0.0, LINK_LENGTH / 2.0 + 1.0, LINK_SLOT_WIDTH / 2.0),
    ):
        check(f"create_sketch {name}", await adapter.create_sketch("Top"))
        if centre_x == 0.0:
            await define_centered_rectangle(adapter, half_x, half_z, name, dims=SketchDims())
        else:
            corners = [
                (centre_x - half_x, -half_z),
                (centre_x + half_x, -half_z),
                (centre_x + half_x, half_z),
                (centre_x - half_x, half_z),
            ]
            set_sketch_direct_db(adapter, True)
            lines = await add_line_chain(adapter, corners)
            set_sketch_direct_db(adapter, False)
            await define_rectilinear_chain(adapter, lines, corners, label=name, dims=SketchDims())
        await ensure_fully_defined(adapter, f"{name} sketch")
        check(f"exit_sketch {name}", await adapter.exit_sketch())
        name_last_feature(adapter, f"{name}Profile")
        # A Top-plane cut runs toward -Y by default (farm leaf 20260930T023931Z:
        # openings on -Y); reversed, it cuts the +Y wall.
        check(
            f"cut {name}",
            await adapter.create_cut_extrude(
                ExtrusionParameters(depth=r_out + 0.5, reverse_direction=True)
            ),
        )
        name_last_feature(adapter, name)

    want = link_volume()
    await volume_check(adapter, "loop link", want, 0.03 * want)
    part = _early_bound(adapter.currentModel, "IPartDoc")
    bodies = list(part.GetBodies2(0, True) or ())
    if len(bodies) != 1:
        raise RuntimeError(f"loop link has {len(bodies)} bodies, expected one")
    mass = await adapter.get_mass_properties()
    if not mass.is_success:
        raise RuntimeError(f"loop link: get_mass_properties failed: {mass.error}")
    # The only asymmetry is the mouths and slot: cut through the +Y wall,
    # they pull the centre of mass toward -Y.
    com_y = float(mass.data.center_of_mass[1])
    if com_y >= 0.0:
        raise RuntimeError(f"loop link openings cut the -Y wall (centre of mass y {com_y:.4f})")
    _telemetry.success(f"loop link: openings on +Y (centre of mass y {com_y:.4f})")
    await apply_material(adapter, MATERIAL)
    apply_custom_properties(adapter, STOCK_PROPERTIES)
    apply_drawing_properties(adapter, PART_NAME, {"Manufacturing Notes": LINK_DRAWING_NOTES})
    await report_mass_properties(adapter)
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(
        adapter,
        (
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Stock Name",
            "Supplier",
            "Supplier SKUs",
            "Manufacturing Notes",
        ),
    )
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
