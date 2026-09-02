r"""Reproduction script: magnifying wheel (book ch. 21, pp. 50-53).

Pulley of two coaxial wheels rotating together: the wire from the magnifying
lever wraps the 20 mm grooved brass hub, the wire to the pen mechanism leaves
the 100 mm outer rim -- magnifying the summing lever's motion 5x. Six straight
cast spokes (counted on the p. 51 full-page photo; black-painted casting with
a bright machined rim). The fine hub grooves and the hex axle nut are
cosmetic/assembly details, omitted here.

Dimensions: cad/DIMENSIONS.md "Chapter 21" -- hub and rim diameters are
book-annotated and self-validate against the stated 5x magnification; rim
ring section, spoke section, and bore are photo-scaled (low confidence).

Layout: wheel axis = Z through the origin; all features mid-plane symmetric
about the Front plane.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_magnifying_wheel.py
"""

from __future__ import annotations

import sys

from _common import (
    PANEL_BLACK,
    POLISHED_STEEL,
    SketchDims,
    _early_bound,
    _read_member,
    add_line_chain,
    anchor_point_to_origin,
    apply_color,
    apply_material,
    blank_sketch,
    check,
    define_circle,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    measure_check,
    name_bore_axis,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    set_sketch_direct_db,
    volume_check,
)

import _telemetry
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _part_pmi import author_part_pmi
from magnifying_wheel_geom import (
    BORE_DIA,
    HUB_AXIAL,
    HUB_DIA,
    RIM_AXIAL,
    RIM_INNER_DIA,
    RIM_OUTER_DIA,
    RIM_RING_RADIAL,
    SPOKE_AXIAL,
    SPOKE_COUNT,
    SPOKE_OVERLAP,
    SPOKE_WIDTH,
)
from magnifying_wheel_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    ISOMETRIC_VIEW_NOTE,
    SECTION_VIEW_NOTE,
    SURFACE_FINISHES,
)

PART_NAME = "magnifying-wheel"
MATERIAL = "Gray Cast Iron"  # see _common.apply_material docstring

# Wheel nominals live in magnifying_wheel_geom (imported above).

# --- WIRE-1 yoke point (the coupling mate's wheel-side geometry) --------------
# ``WireYokePoint``: a reference point on the hub PITCH circle (groove radius +
# wire radius) at the lever-wire's tangency azimuth, in the wheel mid-plane. The
# magnifier assembly holds it COINCIDENT to the lever-wire's YokePlane, tying the
# wheel's spin to the lever group's travel along the wire (the linearized
# inextensible-wire constraint -- see build_lever_wire's docstring). The azimuth
# is layout-derived, so it is imported from lever_wire_geom: a layout move
# re-tangents the wire AND re-stamps this point in one rebuild.
from lever_wire_geom import (  # noqa: E402
    WHEEL_BAR_Y as _YOKE_WHEEL_Y,
    WHEEL_X as _YOKE_WHEEL_X,
    YOKE_POINT as _YOKE_POINT,
)

# The wheel is placed at IDENTITY, so the yoke point's local offset IS the
# machine offset from the wheel centre. (Pre-#151 this was authored x-NEGATED
# to survive the chirality mirror's double flip -- the imported tangency
# azimuth was itself in the mirrored frame, so the two negations cancelled to
# the same +10.1225 the machine-handed layout gives directly.)
YOKE_LOCAL_X = _YOKE_POINT[0] - _YOKE_WHEEL_X  # +10.099 (pitch r 10.4 @ tangency)
YOKE_LOCAL_Y = _YOKE_POINT[1] - _YOKE_WHEEL_Y  # -2.485


def _com_get(obj, name: str):
    """Read a zero-argument COM member that pywin32's late-bound dispatch may
    expose either as a method (``GetBox()``) or as a property value (the
    ``'tuple' object is not callable`` trap seen on IFace2.GetBox)."""
    value = getattr(obj, name)
    return value() if callable(value) else value


BRASS_DRUM = (0.72, 0.56, 0.24)  # ch21 p.53 hub drum


async def _paint_bright_faces(adapter) -> None:
    """Face-level finishes over the black body: rim ring outer cylinder + both
    annular sides -> POLISHED_STEEL; hub drum cylinder -> BRASS_DRUM. Faces are
    classified by their bounding box (the wheel axis is Z): the rim faces span
    the full RIM_OUTER_DIA in X and Y; the drum's cylinder is split into arc
    drum is the HUB_DIA x HUB_DIA x (<= HUB_AXIAL) boxes (cylinder + end
    annuli). Box-only: ``IFace2.Normal`` is non-empty for curved faces too. Fails loud if the expected faces are not
    found, so a geometry change here cannot silently drop the finish."""
    from solidworks_mcp.adapters.com_variant import double_array

    steel = double_array([*POLISHED_STEEL, 1.0, 1.0, 0.3, 0.31, 0.0, 0.0])
    brass = double_array([*BRASS_DRUM, 1.0, 1.0, 0.3, 0.31, 0.0, 0.0])
    part_h = _early_bound(adapter.currentModel, "IPartDoc")
    n_rim = n_hub = 0
    census: list[str] = []
    for body in part_h.GetBodies2(0, True) or []:
        for face in _com_get(body, "GetFaces") or []:
            box = _com_get(face, "GetBox")
            if not box:
                continue
            xs = (float(box[3]) - float(box[0])) * 1000.0
            ys = (float(box[4]) - float(box[1])) * 1000.0
            zs = (float(box[5]) - float(box[2])) * 1000.0
            census.append(f"{xs:.1f}x{ys:.1f}x{zs:.1f}")
            if abs(xs - RIM_OUTER_DIA) < 0.5 and abs(ys - RIM_OUTER_DIA) < 0.5:
                face.MaterialPropertyValues = steel
                n_rim += 1
            elif abs(xs - HUB_DIA) < 0.5 and abs(ys - HUB_DIA) < 0.5 and zs <= HUB_AXIAL + 0.5:
                # The drum: its cylinder (20 x 20 x 10) and its two end annuli
                # (20 x 20 x 0). IFace2.Normal is non-empty for curved faces too,
                # so the classification is by box alone; the axle bore (5 x 5)
                # and the rim faces (100 / 88) never match.
                face.MaterialPropertyValues = brass
                n_hub += 1
    if n_rim < 3 or n_hub < 1:
        raise RuntimeError(
            f"wheel finish faces not found: rim {n_rim}, hub {n_hub}; face boxes "
            f"(x*y*z mm): {' '.join(sorted(set(census)))}"
        )
    _telemetry.info(f"wheel finish: {n_rim} rim faces bright, {n_hub} hub faces brass")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import (
        CircularPatternParameters,
        ExtrusionParameters,
    )

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations) for every length constant; the rim inner
    # diameter, the spoke span and its corner height are equations of the
    # primitives. The mm suffix is load-bearing -- this is an INCH document and the
    # equation manager reads BARE numbers in document units (an unsuffixed 100 =
    # 100 in). SPOKE_COUNT is a pattern instance count, not a sketch length, so it
    # stays a Python constant (no global, nothing to drive).
    await set_global(adapter, "RimOuterDia", f"{RIM_OUTER_DIA}mm")
    await set_global(adapter, "HubDia", f"{HUB_DIA}mm")
    await set_global(adapter, "RimRingRadial", f"{RIM_RING_RADIAL}mm")
    await set_global(adapter, "RimAxial", f"{RIM_AXIAL}mm")
    await set_global(adapter, "HubAxial", f"{HUB_AXIAL}mm")
    await set_global(adapter, "SpokeWidth", f"{SPOKE_WIDTH}mm")
    await set_global(adapter, "SpokeAxial", f"{SPOKE_AXIAL}mm")
    await set_global(adapter, "BoreDia", f"{BORE_DIA}mm")
    await set_global(adapter, "SpokeOverlap", f"{SPOKE_OVERLAP}mm")
    await set_global(adapter, "RimInnerDia", '"RimOuterDia" - 2 * "RimRingRadial"')
    # Spoke runs from y0 (hub OD, less overlap) to y1 (rim ID, plus overlap); its
    # length dim is the span, its corner anchor sits at (-SpokeWidth/2, y0).
    await set_global(adapter, "SpokeY0", '"HubDia" / 2 - "SpokeOverlap"')
    await set_global(
        adapter, "SpokeLength",
        '"RimInnerDia" / 2 - "HubDia" / 2 + 2 * "SpokeOverlap"',
    )

    drive_jobs: list[tuple[str, str]] = []

    # Rim ring (annulus, mid-plane symmetric). Two on-axis circles: each emits
    # only its diameter dim.
    rim_sd = SketchDims()
    check("create_sketch rim", await adapter.create_sketch("Front"))
    await define_circle(
        adapter, 0.0, 0.0, RIM_OUTER_DIA / 2.0, "rim OD", dims=rim_sd,
        names=("RimOdCx", "RimOdCz", "RimOuterDiaDim"),
        drives=(None, None, '"RimOuterDia"'),
    )
    await define_circle(
        adapter, 0.0, 0.0, RIM_INNER_DIA / 2.0, "rim ID", dims=rim_sd,
        names=("RimIdCx", "RimIdCz", "RimInnerDiaDim"),
        drives=(None, None, '"RimInnerDia"'),
    )
    await ensure_fully_defined(adapter, "rim sketch")
    check("exit_sketch rim", await adapter.exit_sketch())
    name_last_feature(adapter, "RimProfile")
    drive_jobs += rim_sd.apply(adapter, "RimProfile")
    check(
        "extrude rim",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=RIM_AXIAL, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Rim")

    # Hub drum. On-axis circle: diameter only.
    hub_sd = SketchDims()
    check("create_sketch hub", await adapter.create_sketch("Front"))
    await define_circle(
        adapter, 0.0, 0.0, HUB_DIA / 2.0, "hub drum", dims=hub_sd,
        names=("HubCx", "HubCz", "HubDiaDim"),
        drives=(None, None, '"HubDia"'),
    )
    await ensure_fully_defined(adapter, "hub sketch")
    check("exit_sketch hub", await adapter.exit_sketch())
    name_last_feature(adapter, "HubProfile")
    drive_jobs += hub_sd.apply(adapter, "HubProfile")
    check(
        "extrude hub",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=HUB_AXIAL, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Hub")

    # Seed spoke along +Y from the hub into the rim ring. Manual constraints +
    # dims, so record each display dim into SketchDims in CREATION order: the
    # width dim, the length dim, then the corner anchor (x, then z) emitted by
    # anchor_point_to_origin for the off-axis corner (-half, y0).
    spoke_sd = SketchDims()
    check("create_sketch spoke", await adapter.create_sketch("Front"))
    half = SPOKE_WIDTH / 2.0
    y0 = HUB_DIA / 2.0 - SPOKE_OVERLAP
    y1 = RIM_INNER_DIA / 2.0 + SPOKE_OVERLAP
    spoke_lines = await add_line_chain(
        adapter, [(-half, y0), (half, y0), (half, y1), (-half, y1)]
    )
    bottom, right, top, left = spoke_lines
    for ent, relation in (
        (bottom, "horizontal"),
        (top, "horizontal"),
        (right, "vertical"),
        (left, "vertical"),
    ):
        check(f"spoke constraint {relation}", await adapter.add_sketch_constraint(ent, None, relation))
    check("spoke width dim", await adapter.add_sketch_dimension(bottom, None, "linear", SPOKE_WIDTH))
    spoke_sd.record("SpokeWidthDim", '"SpokeWidth"')
    check("spoke length dim", await adapter.add_sketch_dimension(right, None, "linear", y1 - y0))
    spoke_sd.record("SpokeLengthDim", '"SpokeLength"')
    await anchor_point_to_origin(adapter, f"{bottom}.start", -half, y0, "spoke corner")
    spoke_sd.record("SpokeCornerX", '"SpokeWidth" / 2')  # unsigned half-width
    spoke_sd.record("SpokeCornerZ", '"SpokeY0"')
    await ensure_fully_defined(adapter, "spoke sketch")
    check("exit_sketch spoke", await adapter.exit_sketch())
    name_last_feature(adapter, "SpokeProfile")
    drive_jobs += spoke_sd.apply(adapter, "SpokeProfile")
    spoke_feature = await adapter.create_extrusion(
        ExtrusionParameters(depth=SPOKE_AXIAL, both_directions=True)
    )
    check("extrude spoke", spoke_feature)
    name_last_feature(adapter, "Spoke")

    # Axle bore through everything. On-axis circle: diameter only.
    bore_sd = SketchDims()
    check("create_sketch bore", await adapter.create_sketch("Front"))
    await define_circle(
        adapter, 0.0, 0.0, BORE_DIA / 2.0, "bore", dims=bore_sd,
        names=("BoreCx", "BoreCz", "BoreDiaDim"),
        drives=(None, None, '"BoreDia"'),
    )
    await ensure_fully_defined(adapter, "bore sketch")
    check("exit_sketch bore", await adapter.exit_sketch())
    name_last_feature(adapter, "BoreProfile")
    drive_jobs += bore_sd.apply(adapter, "BoreProfile")
    check(
        "cut bore",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=HUB_AXIAL + 2.0, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Bore")

    # Pattern the spoke about the bore axis. The seed feature was renamed to
    # "Spoke" above, so the pattern must select it by the NEW name (the captured
    # auto-name went stale on rename).
    check(
        f"circular pattern {SPOKE_COUNT} spokes",
        await adapter.circular_pattern_feature(
            CircularPatternParameters(
                axis_point=[BORE_DIA / 2.0, 0.0, 0.0],
                features=["Spoke"],
                count=SPOKE_COUNT,
            )
        ),
    )
    name_last_feature(adapter, "SpokePattern")
    res = await adapter.get_mass_properties()
    v_built = float(res.data.volume)
    _telemetry.info(f"volume after pattern: {v_built:.1f} mm^3")

    await apply_material(adapter, MATERIAL)
    # Black-painted casting (p.51 photo) with its bright accents restored at
    # the FACE level (2026-09 photo re-derive): ch21 pp.50-53 show the rim
    # ring's machined outer cylinder and both annular sides bright steel and
    # the 20 mm hub drum brass, only the spokes and hub web black. Face
    # appearances sit above the body colour in the display hierarchy, so the
    # part/body override below still paints everything else black. (The
    # offline gallery still instances ONE colour per part -- export_models
    # colors.json -- so it keeps reading the wheel black-dominant; SolidWorks
    # renders and the glTF export carry the faces.)
    await apply_color(adapter, PANEL_BLACK)
    await _paint_bright_faces(adapter)

    # Verify the two annotated diameters (ch. 21: 100 mm rim, 20 mm hub
    # — they self-validate against the stated 5x magnification).
    await measure_check(
        adapter,
        "rim OD (annotated 100)",
        [{"entity_type": "EDGE", "point": [RIM_OUTER_DIA / 2.0, 0.0, RIM_AXIAL / 2.0]}],
        "diameter",
        RIM_OUTER_DIA,
    )
    await measure_check(
        adapter,
        "hub dia (annotated 20)",
        [{"entity_type": "EDGE", "point": [HUB_DIA / 2.0, 0.0, HUB_AXIAL / 2.0]}],
        "diameter",
        HUB_DIA,
    )

    # Named wheel axis (local Z through the origin = the central bore axis) so
    # the wheel revolves on the axle stud in the M6 mated-DOF assembly
    # (circular_pattern's axis_point does NOT create a persistent ref axis).
    await name_bore_axis(adapter, "Top Plane", 0.0, "Right Plane", 0.0, "wheel axis")

    # WIRE-1 yoke point (see the module-level YOKE_LOCAL_* block): one raw
    # sketch point on the Front plane (mid-plane, exact coords, inference OFF)
    # promoted to a named REFERENCE POINT feature the assembly's coupling mate
    # selects. The carrier sketch is blanked (unabsorbed sketches render SHOWN
    # in every assembly instance); the point's coords are re-read and asserted
    # after the final rebuild -- it is undimensioned, so drift must fail loud.
    check("create_sketch yoke", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    model = adapter.currentModel
    sk_point = model.SketchManager.CreatePoint(
        YOKE_LOCAL_X / 1000.0, YOKE_LOCAL_Y / 1000.0, 0.0)
    if sk_point is None:
        raise RuntimeError("yoke sketch point creation failed")
    set_sketch_direct_db(adapter, False)
    check("exit_sketch yoke", await adapter.exit_sketch())
    name_last_feature(adapter, "WireYokeSketch")
    blank_sketch(adapter, "WireYokeSketch")
    _make_yoke_ref_point(adapter)

    # Apply the deferred drive equations after the whole model + a rebuild exists,
    # so every target resolves. Each equation evaluates to the as-built value (the
    # spoked wheel's volume has no tidy closed form, so the neutrality gate asserts
    # the post-drive volume equals the captured as-built value): geometry must not
    # move.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven magnifying wheel (equations neutral)", v_built, 0.001 * v_built
    )

    _assert_yoke_point(adapter)
    await report_mass_properties(adapter)

    # Manufacturing drawing support: mark exactly the print's dimensions and
    # stamp the make-critical title-block properties.
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": DRAWING_NOTES,
            "Section View Note": SECTION_VIEW_NOTE,
            "Isometric View Note": ISOMETRIC_VIEW_NOTE,
        },
    )
    return await save_part_and_images(adapter, PART_NAME)


def _yoke_sketch_points(adapter):
    """The ISketchPoint list of WireYokeSketch (exactly one expected).

    COM members read via ``_read_member`` -- pywin32 late binding exposes
    FirstFeature/Name/GetNextFeature as methods on some builds and properties
    on others (the fix_shown_sketches walk idiom)."""
    model = adapter.currentModel
    feat = _read_member(model, "FirstFeature")
    for _ in range(5000):
        if not feat:
            break
        if str(_read_member(feat, "Name")) == "WireYokeSketch":
            sketch = _read_member(feat, "GetSpecificFeature2")
            return list(_read_member(sketch, "GetSketchPoints2") or [])
        feat = _read_member(feat, "GetNextFeature")
    raise RuntimeError("WireYokeSketch not found")


def _make_yoke_ref_point(adapter) -> None:
    """Promote the yoke sketch point to a named reference-point FEATURE
    (``WireYokePoint``) via raw COM -- the adapter's reference-point modes are
    edge/face-based only; ``InsertReferencePoint(swRefPointSketchPoint=7)``
    works from a selected sketch point (the adapter has no writer, same
    raw-COM precedent as the Part D custom properties)."""
    model = adapter.currentModel
    pts = _yoke_sketch_points(adapter)
    if len(pts) != 1:
        raise RuntimeError(f"WireYokeSketch: expected 1 point, found {len(pts)}")
    model.ClearSelection2(True)
    # Select2(Append, Mark): the late-binding-safe select -- Select4's
    # ISelectData arg raises "Type mismatch" under the adapter's forced late
    # binding (the _assembly batch-fix comment documents the same trap).
    if not pts[0].Select2(False, 0):
        raise RuntimeError("cannot select the yoke sketch point")
    feat = model.FeatureManager.InsertReferencePoint(7, 0, 0.0, 1)  # 7 = sketch point
    model.ClearSelection2(True)
    if isinstance(feat, tuple):  # late binding marshals the object return boxed
        feat = next((f for f in feat if f is not None), None)
    if feat is None:
        raise RuntimeError("InsertReferencePoint(sketch point) returned null")
    feat.Name = "WireYokePoint"
    if str(_read_member(feat, "Name")) != "WireYokePoint":
        raise RuntimeError("reference point rename failed")
    _telemetry.success("WireYokePoint reference point created")


def _assert_yoke_point(adapter) -> None:
    """Fail loud if the (undimensioned, hidden) yoke sketch point drifted from
    its authored coords across the rebuilds -- the coupling mate's geometry
    must stay exact."""
    pts = _yoke_sketch_points(adapter)
    x_mm = float(_read_member(pts[0], "X")) * 1000.0
    y_mm = float(_read_member(pts[0], "Y")) * 1000.0
    if abs(x_mm - YOKE_LOCAL_X) > 1e-3 or abs(y_mm - YOKE_LOCAL_Y) > 1e-3:
        raise RuntimeError(
            f"yoke point drifted: ({x_mm:.4f}, {y_mm:.4f}) != "
            f"({YOKE_LOCAL_X:.4f}, {YOKE_LOCAL_Y:.4f})"
        )
    _telemetry.success(f"yoke point holds at ({x_mm:.4f}, {y_mm:.4f})")


if __name__ == "__main__":
    sys.exit(run_build(build))
