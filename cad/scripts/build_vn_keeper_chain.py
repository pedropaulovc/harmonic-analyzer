r"""Purchased keeper chain: McMaster-Carr 3606T118 brass bead chain (MHA-VN-035).

The chain tying the crank's removable taper pin to the arm (ch11 p.14; the
original is lost), cut to ``vn_keeper_chain_spec.BEAD_COUNT`` beads and modelled
in its installed rest pose. It is authored in machine axes with its origin on
its first bead (``vn_keeper_chain_spec.CHAIN_PART_ORIGIN``), and the drive train
places it there with an identity rotation, so its seed bead needs no reference
plane.

Recipe:

1. ``SeedBead``, one bead revolved on the Front plane at the origin.
2. ``BeadPoints``, a 3D sketch holding a point at every other bead centre.
3. ``Beads``, a sketch-driven BODY pattern of the seed onto those points,
   using the seed's centroid (its centre) as the reference point.
4. ``ChainPath``, a 3D sketch polyline through every bead centre (each segment
   exactly one pitch).
5. ``Rod``, a circular-profile sweep of the connecting rod along it, merged
   with the beads it threads, which fuses the chain into one body. Every
   mitred corner lies inside a bead.

Both 3D sketches have their points fixed; the pose is the spec's solve.

Feature patterns and curve-driven patterns were tried on this seat
(2026-09-29, SOLIDWORKS 3DEXPERIENCE R2026x). A feature pattern of the base
feature makes no instances. A curve-driven pattern along a 3D polyline
returned None, or made too few instances. The body pattern placed all 35
beads exactly (volume and centre of mass to 0.01 mm^3 and 0.001 mm).

The volume, the body count and the centre of mass are proved against the
analytic union of the beads and the exposed rod lengths.

Run with SolidWorks open::

    uv run python cad\scripts\build_vn_keeper_chain.py
"""

from __future__ import annotations

import math
import sys

import _config
import _telemetry
from _common import (
    apply_custom_properties,
    _early_bound,
    anchor_point_to_origin,
    apply_material,
    blank_reference_sketches,
    check,
    ensure_fully_defined,
    force_rebuild,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_sketch_direct_db,
    volume_check,
)
from _drawing_marks import apply_drawing_properties
from _saved_part_guard import require_saved_drawing_properties
from vn_keeper_chain_spec import (
    CHAIN_PART_BEADS as BEAD_CENTRES,
    BEAD_COUNT,
    BEAD_R,
    CHAIN_DRAWING_NOTES,
    PITCH,
    ROD_DIA,
    ROD_R,
)

PART_NAME = "vn-keeper-chain"
MATERIAL = "Brass"
_PART = _config.parts(PART_NAME)
STOCK_PROPERTIES = {
    "Stock Name": str(_PART["stock_name"]),
    "Supplier": str(_PART["supplier"]),
    "Supplier SKUs": ", ".join(str(sku) for sku in _PART["supplier_skus"]),
}

SW_FM_SWEEP = 17  # swFeatureNameID_e.swFmSweep (swconst.tlb R2026x)
SW_TWIST_FOLLOW_PATH = 0  # swTwistControlType_e.swTwistControlFollowPath
SW_TANGENCY_NONE = 0  # swTangencyType_e.swTangencyNone
SELECT_MARK_BODIES = 256  # FeatureSketchDrivenPattern: bodies to pattern
SELECT_MARK_SKETCH = 64  # FeatureSketchDrivenPattern: reference sketch
SELECT_MARK_SWEEP_PATH = 4

V_BEAD = 4.0 / 3.0 * math.pi * BEAD_R**3
# Rod length between two beads that lies outside both: the cylinder volume
# less the two spherical caps of radius-ROD_R disk swallowed by each bead.
_H0 = math.sqrt(BEAD_R**2 - ROD_R**2)
V_ROD_EXPOSED = math.pi * ROD_R**2 * PITCH - (4.0 * math.pi / 3.0) * (BEAD_R**3 - _H0**3)
V_CHAIN = BEAD_COUNT * V_BEAD + (BEAD_COUNT - 1) * V_ROD_EXPOSED


def _com_expected() -> tuple[float, float, float]:
    """Centre of mass of the bead + exposed-rod union (each rod symmetric)."""
    acc = [0.0, 0.0, 0.0]
    for p in BEAD_CENTRES:
        for k in range(3):
            acc[k] += V_BEAD * p[k]
    for a, b in zip(BEAD_CENTRES, BEAD_CENTRES[1:]):
        for k in range(3):
            acc[k] += V_ROD_EXPOSED * (a[k] + b[k]) / 2.0
    return (acc[0] / V_CHAIN, acc[1] / V_CHAIN, acc[2] / V_CHAIN)


def _model(adapter):
    return _early_bound(adapter.currentModel, "IModelDoc2")


def _body_count(adapter) -> int:
    return len(_early_bound(adapter.currentModel, "IPartDoc").GetBodies2(0, True) or ())


async def _seed_bead(adapter) -> None:
    from solidworks_mcp.adapters.base import RevolveParameters

    # The part's origin is the first bead's centre: the seed sits on the
    # Front plane at the origin and needs no reference plane.
    x0, y0, _ = BEAD_CENTRES[0]
    check("create_sketch seed bead", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    check("seed axis", await adapter.add_centerline(x0, y0 - BEAD_R, x0, y0 + BEAD_R))
    arc = check(
        "seed arc",
        # CCW from -90 deg to +90 deg through +x: the +x half disc.
        await adapter.add_arc(x0, y0, x0, y0 - BEAD_R, x0, y0 + BEAD_R),
    )
    closer = check(
        "seed chord", await adapter.add_line(x0, y0 + BEAD_R, x0, y0 - BEAD_R)
    )
    set_sketch_direct_db(adapter, False)
    await anchor_point_to_origin(adapter, f"{arc}.center", x0, y0, "seed centre")
    check("seed radius", await adapter.add_sketch_dimension(arc, None, "radial", BEAD_R))
    check("seed chord vertical", await adapter.add_sketch_constraint(closer, None, "vertical"))
    check(
        "seed arc start under centre",
        await adapter.add_sketch_constraint(f"{arc}.start", f"{arc}.center", "vertical_points"),
    )
    await ensure_fully_defined(adapter, "seed bead")
    check("exit_sketch seed bead", await adapter.exit_sketch())
    name_last_feature(adapter, "SeedProfile")
    check("revolve seed bead", await adapter.create_revolve(RevolveParameters(angle=360.0)))
    name_last_feature(adapter, "SeedBead")
    await volume_check(adapter, "seed bead", V_BEAD, 0.001 * V_BEAD)


async def _sketch_3d(adapter, name: str, author) -> None:
    """Author a 3D sketch through ``author(manager)``, fix its points, close it."""
    model = _model(adapter)
    manager = _early_bound(model.SketchManager, "ISketchManager")
    manager.Insert3DSketch(True)
    # AddToDB skips inference (no snapping between 3.2 mm-apart points);
    # exactly coincident endpoints still merge. The raw 3D sketch is not the
    # adapter's tracked sketch, so its manager is toggled here directly.
    manager.AddToDB = True
    try:
        expected_points = author(manager)
    finally:
        manager.AddToDB = False
    sketch = _early_bound(manager.ActiveSketch, "ISketch")
    points = list(sketch.GetSketchPoints2() or ())
    if len(points) != expected_points:
        raise RuntimeError(f"{name} has {len(points)} points, expected {expected_points}")
    model.ClearSelection2(True)
    for point in points:
        if not _early_bound(point, "ISketchPoint").Select4(True, None):
            raise RuntimeError(f"{name}: cannot select a point to fix")
    model.SketchAddConstraints("sgFIXED")
    model.ClearSelection2(True)
    await ensure_fully_defined(adapter, name)
    manager.Insert3DSketch(True)
    name_last_feature(adapter, name)


def _mm(p) -> tuple[float, float, float]:
    return (p[0] / 1000.0, p[1] / 1000.0, p[2] / 1000.0)


def _author_points(manager) -> int:
    for i, p in enumerate(BEAD_CENTRES[1:], start=1):
        if manager.CreatePoint(*_mm(p)) is None:
            raise RuntimeError(f"BeadPoints: CreatePoint {i} returned None")
    return BEAD_COUNT - 1


def _author_path(manager) -> int:
    for i, (a, b) in enumerate(zip(BEAD_CENTRES, BEAD_CENTRES[1:])):
        if manager.CreateLine(*_mm(a), *_mm(b)) is None:
            raise RuntimeError(f"ChainPath: CreateLine {i} returned None")
    return BEAD_COUNT  # consecutive endpoints merged


def _pattern_beads(adapter) -> None:
    from solidworks_mcp.adapters.pywin32_adapter import null_callout
    from solidworks_mcp.adapters.solidworks.features import _select_named_feature

    model = _model(adapter)
    bodies = list(_early_bound(model, "IPartDoc").GetBodies2(0, True) or ())
    if len(bodies) != 1:
        raise RuntimeError(f"expected the lone seed body, found {len(bodies)} bodies")
    model.ClearSelection2(True)
    seed_name = str(_early_bound(bodies[0], "IBody2").Name)
    if not model.Extension.SelectByID2(
        seed_name, "SOLIDBODY", 0, 0, 0, False, SELECT_MARK_BODIES, null_callout(), 0
    ):
        raise RuntimeError(f"cannot select seed body {seed_name!r} (mark 256)")
    if not _select_named_feature(adapter, "BeadPoints", SELECT_MARK_SKETCH, True):
        raise RuntimeError("cannot select BeadPoints (mark 64)")
    fm = _early_bound(model.FeatureManager, "IFeatureManager")
    with _telemetry.span("feature.bead_pattern", label="Beads", count=BEAD_COUNT):
        feature = fm.FeatureSketchDrivenPattern(True, False)  # UseCentroid, BGeomPatt
    model.ClearSelection2(True)
    if feature is None:
        raise RuntimeError("FeatureSketchDrivenPattern (bead bodies) returned None")
    name_last_feature(adapter, "Beads")
    if _body_count(adapter) != BEAD_COUNT:
        raise RuntimeError(f"bead pattern made {_body_count(adapter)} bodies, expected {BEAD_COUNT}")


def _sweep_rod(adapter) -> None:
    from solidworks_mcp.adapters.solidworks.features import _select_named_feature

    model = _model(adapter)
    fm = _early_bound(model.FeatureManager, "IFeatureManager")
    data = _early_bound(fm.CreateDefinition(SW_FM_SWEEP), "ISweepFeatureData")
    model.ClearSelection2(True)
    if not _select_named_feature(adapter, "ChainPath", SELECT_MARK_SWEEP_PATH, False):
        raise RuntimeError("cannot select ChainPath as the sweep path (mark 4)")
    data.TangentPropagation = False
    data.AlignWithEndFaces = False
    data.TwistControlType = SW_TWIST_FOLLOW_PATH
    data.MaintainTangency = False
    data.AdvancedSmoothing = False
    data.StartTangencyType = SW_TANGENCY_NONE
    data.EndTangencyType = SW_TANGENCY_NONE
    data.ThinFeature = False
    data.Merge = True
    data.FeatureScope = True
    data.AutoSelect = True
    data.CircularProfile = True
    data.CircularProfileDiameter = ROD_DIA / 1000.0
    with _telemetry.span("feature.sweep_rod", label="Rod"):
        feature = fm.CreateFeature(data)
    model.ClearSelection2(True)
    if feature is None:
        raise RuntimeError("CreateFeature (rod sweep) returned None")
    name_last_feature(adapter, "Rod")
    if _body_count(adapter) != 1:
        raise RuntimeError(f"rod sweep left {_body_count(adapter)} bodies, expected one chain")


async def build(adapter) -> dict[str, str]:
    check("create_part", await adapter.create_part())
    await _seed_bead(adapter)
    await _sketch_3d(adapter, "BeadPoints", _author_points)
    _pattern_beads(adapter)
    await volume_check(adapter, "bead bodies", BEAD_COUNT * V_BEAD, 0.001 * BEAD_COUNT * V_BEAD)
    await _sketch_3d(adapter, "ChainPath", _author_path)
    _sweep_rod(adapter)
    await force_rebuild(adapter)
    await volume_check(adapter, "keeper chain", V_CHAIN, 0.005 * V_CHAIN)
    mass = await adapter.get_mass_properties()
    if not mass.is_success:
        raise RuntimeError(f"keeper chain: get_mass_properties failed: {mass.error}")
    got = [float(c) for c in mass.data.center_of_mass]
    want = _com_expected()
    # A misplaced bead moves the centre of mass by ~0.1 mm per mm of error;
    # 0.02 mm sits far above the rod-mitre noise.
    if max(abs(g - w) for g, w in zip(got, want)) > 0.02:
        raise RuntimeError(f"keeper chain centre of mass {got} != analytic {want}")
    _telemetry.success(f"keeper chain: centre of mass {got} matches {want}")
    blank_reference_sketches(adapter, ("BeadPoints",))
    await apply_material(adapter, MATERIAL)
    apply_custom_properties(adapter, STOCK_PROPERTIES)
    apply_drawing_properties(adapter, PART_NAME, {"Manufacturing Notes": CHAIN_DRAWING_NOTES})
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
