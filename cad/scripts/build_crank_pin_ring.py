r"""Reproduction script: crank-pin keeper ring (book ch. 11, p. 14).

The round brass wire ring hanging from the crank taper pin's head
(page002_img01), threaded through the pin's cross-hole. A torus of MEAN_R on
the wire centreline, with a small bead at its silver-soldered joint; the
cross-hole is sized for its arc (see
``crank_pin_ring_spec``), and the keeper chain (MHA-149) loops its bottom.

Layout: the origin is on the cross-hole axis (local Z) and the ring lies in
the local XZ plane, its centre RING_CENTRE_X along local +X. The drive train
maps local +X to machine -Y, so the ring hangs below the pin.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_crank_pin_ring.py
"""

from __future__ import annotations

import sys

from _common import (
    SketchDims,
    _early_bound,
    anchor_point_to_origin,
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
    set_sketch_direct_db,
    volume_check,
)
from crank_pin_ring_spec import (
    ARC_SAGITTA,
    JOINT_DIA,
    MEAN_R,
    RING_CENTRE_X,
    V_JOINT,
    V_RING,
    WIRE_DIA,
)

PART_NAME = "crank-pin-ring"
MATERIAL = "Brass"


async def _solder_joint(adapter) -> None:
    """The silver-soldered joint: a bead on the wire at the ring's +Z side.

    A Top-plane sketch maps (x, y) -> global (X, -Z), so the joint centre
    (RING_CENTRE_X, 0, MEAN_R) sits at sketch (RING_CENTRE_X, -MEAN_R); a half
    disc about a vertical centerline through it revolves into the bead.
    """
    from solidworks_mcp.adapters.base import RevolveParameters

    r = JOINT_DIA / 2.0
    cx, cy = RING_CENTRE_X, -MEAN_R
    check("create_sketch joint", await adapter.create_sketch("Top"))
    set_sketch_direct_db(adapter, True)
    check("joint axis", await adapter.add_centerline(cx, cy - r, cx, cy + r))
    arc = check("joint arc", await adapter.add_arc(cx, cy, cx, cy - r, cx, cy + r))
    closer = check("joint chord", await adapter.add_line(cx, cy + r, cx, cy - r))
    set_sketch_direct_db(adapter, False)
    await anchor_point_to_origin(adapter, f"{arc}.center", cx, cy, "joint centre")
    check("joint radius", await adapter.add_sketch_dimension(arc, None, "radial", r))
    check("joint chord vertical", await adapter.add_sketch_constraint(closer, None, "vertical"))
    check(
        "joint arc start under centre",
        await adapter.add_sketch_constraint(f"{arc}.start", f"{arc}.center", "vertical_points"),
    )
    await ensure_fully_defined(adapter, "joint sketch")
    check("exit_sketch joint", await adapter.exit_sketch())
    name_last_feature(adapter, "JointProfile")
    check("revolve joint", await adapter.create_revolve(RevolveParameters(angle=360.0)))
    name_last_feature(adapter, "SolderJoint")
    want = V_RING + V_JOINT
    await volume_check(adapter, "keeper ring with joint", want, 0.005 * want)
    bodies = list(_early_bound(adapter.currentModel, "IPartDoc").GetBodies2(0, True) or ())
    if len(bodies) != 1:
        raise RuntimeError(f"keeper ring has {len(bodies)} bodies after its joint, expected one")
    if not _early_bound(bodies[0], "IBody2").GetEdges():
        raise RuntimeError("keeper ring's solder joint left no edge on the ring")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import RevolveParameters

    check("create_part", await adapter.create_part())
    await set_global(adapter, "MeanR", f"{MEAN_R}mm")
    await set_global(adapter, "WireDia", f"{WIRE_DIA}mm")
    drive_jobs: list[tuple[str, str]] = []

    # Front-plane sketch (x, y) -> global (X, Y): a vertical centerline at
    # x = RING_CENTRE_X is the torus axis (parallel to Y, through the ring
    # centre), and the wire circle at the ring's crown, x = -ARC_SAGITTA / 2 on
    # the hole's Z = 0 section, revolves about it into the ring in the XZ plane.
    # A plain torus has no edges; the solder joint below adds them.
    prof = SketchDims()
    check("create_sketch wire", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    centerline = check(
        "axis", await adapter.add_centerline(RING_CENTRE_X, 0.0, RING_CENTRE_X, MEAN_R)
    )
    set_sketch_direct_db(adapter, False)
    check("axis vertical", await adapter.add_sketch_constraint(centerline, None, "vertical"))
    await anchor_point_to_origin(
        adapter, f"{centerline}.start", RING_CENTRE_X, 0.0, "ring centre"
    )
    prof.record("CentreX")
    check("axis length", await adapter.add_sketch_dimension(centerline, None, "linear", MEAN_R))
    prof.record("AxisLen", '"MeanR"')
    crown = -ARC_SAGITTA / 2.0
    await define_circle(
        adapter, crown, 0.0, WIRE_DIA / 2.0, "wire", dims=prof,
        names=("WireCx", "WireCy", "WireDia"), drives=(None, None, '"WireDia"'),
    )
    await ensure_fully_defined(adapter, "wire sketch")
    check("exit_sketch wire", await adapter.exit_sketch())
    name_last_feature(adapter, "WireProfile")
    drive_jobs += prof.apply(adapter, "WireProfile")
    check("revolve ring", await adapter.create_revolve(RevolveParameters(angle=360.0)))
    name_last_feature(adapter, "Ring")
    await volume_check(adapter, "keeper ring", V_RING, 0.005 * V_RING)

    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven keeper ring (equations neutral)", V_RING, 0.005 * V_RING
    )
    await _solder_joint(adapter)

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
