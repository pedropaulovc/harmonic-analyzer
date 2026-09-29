r"""Reproduction script: crank-pin keeper ring (book ch. 11, p. 14).

The round brass wire ring hanging from the crank taper pin's head
(page002_img01), threaded through the pin's cross-hole. A torus of MEAN_R on
the wire centreline, built as two half revolves that meet at the silver-soldered
seams on its sides. The cross-hole is sized for its arc (see
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
from _visibility import blank_reference_geometry
from crank_pin_ring_spec import MEAN_R, RING_CENTRE_X, V_RING, WIRE_DIA

PART_NAME = "crank-pin-ring"
MATERIAL = "Brass"


async def _half_ring(adapter, name: str, reverse: bool) -> list[tuple[str, str]]:
    """One 180-degree half of the ring, revolved from the side seam."""
    from solidworks_mcp.adapters.base import RevolveParameters

    # On RingAxisPlane (parallel to Right, through the ring centre) the sketch
    # origin is the ring centre, a vertical centerline through it is the torus
    # axis, and the wire circle MEAN_R to one side is the seam section.
    prof = SketchDims()
    check(f"create_sketch {name}", await adapter.create_sketch("RingAxisPlane"))
    set_sketch_direct_db(adapter, True)
    centerline = check(f"{name} axis", await adapter.add_centerline(0.0, 0.0, 0.0, MEAN_R))
    set_sketch_direct_db(adapter, False)
    check(f"{name} axis vertical", await adapter.add_sketch_constraint(centerline, None, "vertical"))
    await anchor_point_to_origin(adapter, f"{centerline}.start", 0.0, 0.0, f"{name} axis")
    check(f"{name} axis length", await adapter.add_sketch_dimension(centerline, None, "linear", MEAN_R))
    prof.record("AxisLen", '"MeanR"')
    await define_circle(
        adapter, MEAN_R, 0.0, WIRE_DIA / 2.0, f"{name} wire", dims=prof,
        names=("WireCx", "WireCy", "WireDia"), drives=('"MeanR"', None, '"WireDia"'),
    )
    await ensure_fully_defined(adapter, f"{name} sketch")
    check(f"exit_sketch {name}", await adapter.exit_sketch())
    name_last_feature(adapter, f"{name}Profile")
    jobs = prof.apply(adapter, f"{name}Profile")
    check(
        f"revolve {name}",
        await adapter.create_revolve(
            RevolveParameters(angle=180.0, reverse_direction=reverse)
        ),
    )
    name_last_feature(adapter, name)
    return jobs


def _edge_count(adapter) -> int:
    bodies = list(_early_bound(adapter.currentModel, "IPartDoc").GetBodies2(0, True) or ())
    if len(bodies) != 1:
        raise RuntimeError(f"keeper ring has {len(bodies)} bodies, expected one")
    return len(_early_bound(bodies[0], "IBody2").GetEdges() or ())


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import CreatePlaneParameters

    check("create_part", await adapter.create_part())
    await set_global(adapter, "MeanR", f"{MEAN_R}mm")
    await set_global(adapter, "WireDia", f"{WIRE_DIA}mm")

    check(
        "ring axis plane",
        await adapter.create_plane(
            CreatePlaneParameters(mode="offset", base_plane="Right Plane", offset=RING_CENTRE_X)
        ),
    )
    name_last_feature(adapter, "RingAxisPlane")
    # The ring is formed from wire with its ends silver-soldered. Two halves
    # meeting at seams on the ring's sides model that, and give the drawings
    # real edges to balloon: a full-revolve torus has none, and its crown and
    # bottom hide behind the pin and the keeper chain.
    drive_jobs = await _half_ring(adapter, "HalfA", reverse=False)
    drive_jobs += await _half_ring(adapter, "HalfB", reverse=True)
    await volume_check(adapter, "keeper ring", V_RING, 0.005 * V_RING)
    if _edge_count(adapter) < 2:
        raise RuntimeError("keeper ring's half revolves merged into an edgeless torus")

    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven keeper ring (equations neutral)", V_RING, 0.005 * V_RING
    )
    blank_reference_geometry(adapter, (("RingAxisPlane", "PLANE"),))

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
