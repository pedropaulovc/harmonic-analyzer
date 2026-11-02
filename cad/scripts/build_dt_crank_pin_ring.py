r"""Reproduction script: crank-pin keeper ring (book ch. 11, p. 14).

The round brass wire ring hanging from the crank taper pin's head
(page002_img01), threaded through the pin's cross-hole. A torus of MEAN_R on
the wire centreline, with a small bead at its silver-soldered joint; the
cross-hole is sized for its arc (see
``dt_crank_pin_ring_spec``), and the keeper chain (MHA-DT-VN-65) loops its far side.

Layout: the origin is on the cross-hole axis (local Z) and the ring lies in
the local XZ plane, its centre RING_CENTRE_X along local +X. The drive train
maps local +X to machine -X, so the ring reaches outboard past the pin's big
end, clear of the crank arm (owner ruling 2026-10-15 A1).

``RingReference`` (blanked, on the Top plane, the ring's own plane): a circle
on the ring's inside edge whose one diameter carries the ring's controlling
size, since a torus has no edge to dimension; the drawing's top view prints
it (``dt_crank_pin_ring_notes``).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_dt_crank_pin_ring.py
"""

from __future__ import annotations

import sys

from _appearance import apply_material
from _check import check
from _com import _early_bound
from _dimensions import drive_dimension, set_global
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _drawing_precision import apply_drawing_precision
from _document_units import apply_package_model_units
from _feature_tree import name_last_feature
from _part_checks import report_mass_properties, volume_check
from _part_properties import part_drawing_unit
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _saved_part_guard import require_saved_drawing_properties
from _session import run_build
from _sketch import (
    SketchDims,
    anchor_point_to_origin,
    blank_reference_sketches,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _sketch_circle import define_circle
from dt_crank_pin_ring_notes import (
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    RING_ID,
)
from dt_crank_pin_ring_spec import (
    ARC_SAGITTA,
    JOINT_DIA,
    MEAN_R,
    RING_CENTRE_X,
    V_JOINT,
    V_RING,
    WIRE_DIA,
)

PART_NAME = "dt-crank-pin-ring"
MATERIAL = "Brass"
_SAVED_DRAWING_PROPERTIES = (
    "Number",
    "Material Specification",
    "Finish",
    "Quantity",
    "Manufacturing Notes",
)


async def _solder_joint(adapter) -> None:
    """The silver-soldered joint: a bead on the wire at the ring's +Z side.

    A Top-plane sketch maps (x, y) -> global (X, -Z), so the joint centre
    (RING_CENTRE_X, 0, MEAN_R) sits at sketch (RING_CENTRE_X, -MEAN_R); a half
    disc about a vertical centerline through it revolves into the bead.
    """
    from solidworks_mcp.adapters.base import RevolveParameters

    r = JOINT_DIA / 2.0
    cx, cy = RING_CENTRE_X, -MEAN_R
    joint = SketchDims()
    check("create_sketch joint", await adapter.create_sketch("Top"))
    set_sketch_direct_db(adapter, True)
    check("joint axis", await adapter.add_centerline(cx, cy - r, cx, cy + r))
    arc = check("joint arc", await adapter.add_arc(cx, cy, cx, cy - r, cx, cy + r))
    closer = check("joint chord", await adapter.add_line(cx, cy + r, cx, cy - r))
    set_sketch_direct_db(adapter, False)
    await anchor_point_to_origin(adapter, f"{arc}.center", cx, cy, "joint centre")
    joint.record(None)
    joint.record(None)
    # A diameter, as the drawing's top view prints the bead.
    check(
        "joint diameter",
        await adapter.add_sketch_dimension(arc, None, "diameter", JOINT_DIA),
    )
    joint.record("JointDia")
    check("joint chord vertical", await adapter.add_sketch_constraint(closer, None, "vertical"))
    check(
        "joint arc start under centre",
        await adapter.add_sketch_constraint(f"{arc}.start", f"{arc}.center", "vertical_points"),
    )
    await ensure_fully_defined(adapter, "joint sketch")
    check("exit_sketch joint", await adapter.exit_sketch())
    name_last_feature(adapter, "JointProfile")
    joint.apply(adapter, "JointProfile")
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
    # #290: the row's inch calculation units, before the first global.
    apply_package_model_units(adapter, part_drawing_unit(PART_NAME), label=PART_NAME)
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

    # REFERENCE sketch: the ring's inside edge, in the ring's own (Top) plane,
    # a Top-plane sketch mapping (x, y) -> global (X, -Z). The ring centre is
    # (RING_CENTRE_X, 0) there; the circle's one diameter is driven by the
    # globals so it follows the wire and the ring.
    ref = SketchDims()
    check("create_sketch ring reference", await adapter.create_sketch("Top"))
    await define_circle(
        adapter,
        RING_CENTRE_X,
        0.0,
        RING_ID / 2.0,
        "ring inside",
        dims=ref,
        names=("RingCx", None, "RingID"),
        drives=(None, None, '2 * "MeanR" - "WireDia"'),
    )
    await ensure_fully_defined(adapter, "ring reference sketch")
    check("exit_sketch ring reference", await adapter.exit_sketch())
    name_last_feature(adapter, "RingReference")
    drive_jobs += ref.apply(adapter, "RingReference")

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

    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    apply_drawing_properties(adapter, PART_NAME, {"Manufacturing Notes": DRAWING_NOTES})
    blank_reference_sketches(adapter, ("RingReference",))
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(adapter, _SAVED_DRAWING_PROPERTIES)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
