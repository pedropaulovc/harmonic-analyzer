r"""Modified purchased cone pivot post mount screw: MSC 40923898, cut to length.

Head up, under-head junction at the origin: the head seats on the MHA-016
counterbore floor and the shank runs down through the post into the
MHA-091 tap.  Modelled at the 86.0 cut-to-fit nominal (U37c).

The cut is the one modification, so the part owns its length: a hidden
construction sketch whose single driving dimension is the cut length
(under-head face to cut end), at its model-owned places, marked for the
drawing.  It carries no band: no one length suits every in-band post and
plate (``post_mount_screw_spec``'s U27 check), so the sheet prints it as a
reference and each screw is cut to its own hole at assembly.  The build
proves the dimension and the solid's cut end agree.

A second hidden sketch carries the cut end's deburr break, 0.1 +0/-0.1
(Main's engagement ruling), the thread the 0.90D worst case counts on.

The solid carries the modification too (Main's ruling on the cut end):
cutting to fit removes the factory-chamfered tip, so the break is this
part's own feature, not the fillister family's.  The shared recipe
(untouched) builds the stock screw at its SUPPLIED 3-1/2 in length; this
builder then trims it at CutLength (``CutToLength``) and breaks the new end
45 deg with CutEndBreak (``CutEndDeburr``), both cutters driven by equations
from those two model dimensions.  Analytic volume checks prove the cuts,
and the end face's rim radius proves the break.
"""

from __future__ import annotations

from functools import wraps
import math
import sys

import _telemetry
from _common import (
    _early_bound,
    anchor_point_to_origin,
    SketchDims,
    add_line_chain,
    check,
    dimension_between,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_dimensions,
    name_last_feature,
    run_build,
    set_global,
    set_sketch_direct_db,
)
from _drawing_marks import (
    apply_drawing_precision,
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
    _named_dimension,
)
from _fastener_catalog import fastener
from _fit_limits import deviations
from _stock_fastener import RigidTransform, StockComponent, build_stock_fastener
from diagnostics.diag_build_40923898 import build_40923898
from diagnostics.diag_mcmaster_fillister import FILLISTER_SIZES
from diagnostics.diag_mcmaster_lib import no_sketch_inference
from post_mount_screw_spec import (
    CUT_END_BREAK_BAND,
    CUT_END_BREAK_DIMENSION,
    CUT_END_BREAK_MM,
    CUT_END_BREAK_MAX_MM,
    CUT_END_BREAK_SKETCH,
    CUT_END_BREAK_TEXT,
    CUT_END_BREAK_TOL_TYPE,
    CUT_LENGTH_DIMENSION,
    CUT_LENGTH_MM,
    CUT_END_DEBURR_REMOVED_MM3,
    CUT_LENGTH_SKETCH,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    MAJOR_RADIUS_MM,
    MANUFACTURING_NOTES,
    SKU,
    STOCK_LENGTH_MM,
    THREAD,
    TRIM_REMOVED_MM3,
)

PART_NAME = "post-mount-screw"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material

# The shared row is the supplied screw; the part's shank is its cut length.
SHANK_DIA, _STOCK_LEN, HEAD_H, HEAD_DIA, THREAD_PITCH = FILLISTER_SIZES[SKU]
if _STOCK_LEN != STOCK_LENGTH_MM:
    raise ValueError("the stock recipe length is not the supplied length")
SHANK_LEN = CUT_LENGTH_MM

TRIM_PROFILE = "CutToLengthProfile"
TRIM_FEATURE = "CutToLength"
# The cutter's profile owns CutEndBreak (see post_mount_screw_spec).
DEBURR_PROFILE = CUT_END_BREAK_SKETCH
DEBURR_FEATURE = "CutEndDeburr"
# Equation drives: each cutter follows the model dimension that owns it.
CUT_LENGTH_REF = f'"{CUT_LENGTH_DIMENSION}@{CUT_LENGTH_SKETCH}"'
CUT_END_BREAK_REF = f'"{CUT_END_BREAK_DIMENSION}@{CUT_END_BREAK_SKETCH}"'
DEBURR_MARGIN_GLOBAL = "CutEndDeburrMargin"
TRIM_DRIVES = {"TrimAt": CUT_LENGTH_REF}
# CutEndBreak is the cutter's own driving dimension (the radial leg inside
# the major radius); the margin leg and the rise follow it by equation.
DEBURR_DRIVES = {
    "CutEnd": CUT_LENGTH_REF,
    "CutterMargin": f'"{DEBURR_MARGIN_GLOBAL}"',
    "CutterRise": f'{CUT_END_BREAK_REF} + "{DEBURR_MARGIN_GLOBAL}"',
}
# The deburr cutter overshoots the major radius so its cone clears the crest.
DEBURR_MARGIN_MM = 0.5
# The trim cutter reaches one diameter past the supplied tip.
TRIM_OVERRUN_MM = SHANK_DIA
# The sweep route under-removes ~0.4% of the groove
# (diag_mcmaster_lib.thread_sweep_cut_modern): inside 0.5% of the trim.
TRIM_VOLUME_TOL_MM3 = 0.005 * TRIM_REMOVED_MM3
# The end face's rim is a B-rep vertex read: exact to the kernel.
RIM_TOL_MM = 1e-4


def _as_construction(adapter, entity_id: str) -> None:
    segment = _early_bound(adapter._sketch_entities[entity_id], "ISketchSegment")
    segment.ConstructionGeometry = True
    if not bool(segment.ConstructionGeometry):
        raise RuntimeError(f"{entity_id} did not take the construction flag")


def _cut_end_y_mm(adapter) -> float:
    """The solid's lowest point along the screw axis (IBody2.GetExtremePoint,
    exact -- see _common.bbox_extent_check), in mm."""
    part = _early_bound(adapter.currentModel, "IPartDoc")
    bodies = part.GetBodies2(0, False) or ()  # swSolidBody
    if not bodies:
        raise RuntimeError("post-mount-screw has no solid body to measure")
    lowest = float("inf")
    for body in bodies:
        found = _early_bound(body, "IBody2").GetExtremePoint(0.0, -1.0, 0.0)
        if not found or len(found) < 4 or not found[0]:
            raise RuntimeError("post-mount-screw: GetExtremePoint failed")
        lowest = min(lowest, float(found[2]) * 1000.0)
    return lowest


async def _author_reference_dimension(
    adapter,
    *,
    sketch: str,
    dimension: str,
    start: tuple[float, float],
    end: tuple[float, float],
    orientation: str,
    value_mm: float,
) -> None:
    """One construction line on the Front plane carrying ONE driving,
    model-owned drawing dimension; build_cone_tip_shim's reference-sketch
    pattern.  The line is dimensioned first, so name_dimensions' creation
    order finds it before the origin-anchor dimensions."""
    check(f"create_sketch {sketch}", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    line = check(f"{sketch} line", await adapter.add_line(*start, *end))
    set_sketch_direct_db(adapter, False)
    _as_construction(adapter, line)
    check(
        f"{sketch} {orientation}",
        await adapter.add_sketch_constraint(line, None, orientation),
    )
    await dimension_between(
        adapter,
        f"{line}.start",
        f"{line}.end",
        f"{orientation}_distance",
        value_mm,
        sketch,
    )
    await anchor_point_to_origin(adapter, f"{line}.start", *start, sketch)
    await ensure_fully_defined(adapter, f"{sketch} sketch")
    check(f"exit_sketch {sketch}", await adapter.exit_sketch())
    name_last_feature(adapter, sketch)
    name_dimensions(adapter, sketch, [dimension])


async def _author_cut_controls(adapter) -> None:
    """The cut length runs along the shank's left silhouette, under-head face
    to cut end: the print dimensions between faces the shop measures, not
    along the axis through the part.  The cut end's break is authored on the
    deburr cutter's profile (_break_cut_end)."""
    x = -SHANK_DIA / 2.0
    await _author_reference_dimension(
        adapter,
        sketch=CUT_LENGTH_SKETCH,
        dimension=CUT_LENGTH_DIMENSION,
        start=(x, 0.0),
        end=(x, -CUT_LENGTH_MM),
        orientation="vertical",
        value_mm=CUT_LENGTH_MM,
    )


async def _volume_mm3(adapter) -> float:
    mass = await adapter.get_mass_properties()
    if not mass.is_success:
        raise RuntimeError(f"get_mass_properties failed: {mass.error}")
    return float(mass.data.volume)


def _check_removed(label: str, before: float, after: float, expected: float) -> None:
    removed = before - after
    if abs(removed - expected) > TRIM_VOLUME_TOL_MM3:
        raise RuntimeError(
            f"{label}: removed {removed:.4f} mm^3, analytic {expected:.4f} "
            f"(+/- {TRIM_VOLUME_TOL_MM3:.4f})"
        )
    _telemetry.success(
        f"{label}: removed {removed:.4f} mm^3 (analytic {expected:.4f})"
    )


def _model_dimension_mm(adapter, sketch: str, dimension: str) -> float:
    raw = adapter.currentModel.Parameter(f"{dimension}@{sketch}")
    if raw is None:
        raise RuntimeError(f"model has no {dimension}@{sketch}")
    return float(_early_bound(raw, "IDimension").SystemValue) * 1000.0


def assert_break_removed_metal(
    rim_before_mm: float, rim_after_mm: float, break_mm: float
) -> float:
    """Prove the cut-end break from the end face's rim, not from volume.

    Before the break the trimmed end face reaches the thread's major radius
    (its crest arcs); after it, the rim sits at the major radius less the
    model's CutEndBreak.  Both reads are B-rep vertices, exact to the kernel,
    so the gate resolves the 0.1 break that two cumulative mass-property
    reads (0.13-0.18 mm^3 residual) cannot.  Returns how far the rim moved in.
    """
    if abs(rim_before_mm - MAJOR_RADIUS_MM) > RIM_TOL_MM:
        raise RuntimeError(
            f"trimmed end face rim radius {rim_before_mm:.5f} is not the "
            f"major {MAJOR_RADIUS_MM}"
        )
    cut_in = rim_before_mm - rim_after_mm
    if not cut_in > RIM_TOL_MM:
        raise RuntimeError(
            f"the cut-end break removed no metal: end face rim {rim_before_mm:.5f} "
            f"before the break, {rim_after_mm:.5f} after"
        )
    if abs(rim_after_mm - (MAJOR_RADIUS_MM - break_mm)) > RIM_TOL_MM:
        raise RuntimeError(
            f"end face rim radius {rim_after_mm:.5f}, expected the major "
            f"{MAJOR_RADIUS_MM} less the {break_mm} break"
        )
    return cut_in


def _end_face_rim_radius_mm(adapter, end_y_mm: float, *, phase: str) -> float:
    """The largest radius on the planar end face, from its edges' vertices:
    the crest arcs before the break, the 45 deg break's rim arcs after it."""
    with _telemetry.span("cut_end.rim", phase=phase, end_y_mm=end_y_mm) as sp:
        rim = _read_end_face_rim_radius_mm(adapter, end_y_mm)
        sp.set_attribute("rim_mm", rim)
        return rim


def _read_end_face_rim_radius_mm(adapter, end_y_mm: float) -> float:
    part = _early_bound(adapter.currentModel, "IPartDoc")
    radii: list[float] = []
    faces = 0
    for body in part.GetBodies2(0, False) or ():  # swSolidBody
        for raw_face in _early_bound(body, "IBody2").GetFaces() or ():
            face = _early_bound(raw_face, "IFace2")
            normal = tuple(float(v) for v in (face.Normal or ()))
            if len(normal) != 3 or abs(abs(normal[1]) - 1.0) > 1e-9:
                continue
            points = []
            for raw_edge in face.GetEdges() or ():
                edge = _early_bound(raw_edge, "IEdge")
                for vertex in (edge.GetStartVertex(), edge.GetEndVertex()):
                    if vertex is None:
                        continue
                    point = _early_bound(vertex, "IVertex").GetPoint()
                    points.append(tuple(float(v) * 1000.0 for v in point))
            if not points or any(abs(y - end_y_mm) > 1e-6 for _, y, _ in points):
                continue
            faces += 1
            radii.extend(math.hypot(x, z) for x, _, z in points)
    if faces != 1 or not radii:
        raise RuntimeError(
            f"expected one planar end face at y={end_y_mm}, found {faces}"
        )
    return max(radii)


async def _trim_to_cut_length(adapter) -> None:
    """Remove the factory tip: everything below the cut plane."""
    from solidworks_mcp.adapters.base import ExtrusionParameters

    half = 2.0 * MAJOR_RADIUS_MM
    top, bottom = -CUT_LENGTH_MM, -(STOCK_LENGTH_MM + TRIM_OVERRUN_MM)
    dims = SketchDims()
    with no_sketch_inference(adapter):
        check(f"create_sketch {TRIM_PROFILE}", await adapter.create_sketch("Front"))
        lines = await add_line_chain(
            adapter, [(-half, top), (half, top), (half, bottom), (-half, bottom)]
        )
        for line, direction in zip(
            lines, ("horizontal", "vertical", "horizontal", "vertical"), strict=True
        ):
            check(
                f"{TRIM_PROFILE} {direction}",
                await adapter.add_sketch_constraint(line, None, direction),
            )
        await anchor_point_to_origin(
            adapter, f"{lines[0]}.start", -half, top, TRIM_PROFILE
        )
        dims.record("CutterLeft")
        dims.record("TrimAt", TRIM_DRIVES["TrimAt"])
        await dimension_between(
            adapter,
            f"{lines[0]}.start",
            f"{lines[0]}.end",
            "horizontal_distance",
            2.0 * half,
            f"{TRIM_PROFILE} width",
        )
        dims.record("CutterWidth")
        await dimension_between(
            adapter,
            f"{lines[1]}.start",
            f"{lines[1]}.end",
            "vertical_distance",
            top - bottom,
            f"{TRIM_PROFILE} depth",
        )
        dims.record("CutterDepth")
        await ensure_fully_defined(adapter, f"{TRIM_PROFILE} sketch")
        check(f"exit_sketch {TRIM_PROFILE}", await adapter.exit_sketch())
    name_last_feature(adapter, TRIM_PROFILE)
    drives = dims.apply(adapter, TRIM_PROFILE)
    check(
        TRIM_FEATURE,
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=4.0 * SHANK_DIA, both_directions=True)
        ),
    )
    name_last_feature(adapter, TRIM_FEATURE)
    for dimension, expression in drives:
        await drive_dimension(adapter, dimension, expression)


async def _break_cut_end(adapter) -> None:
    """The 45 deg break at the new end, its radial leg = CutEndBreak.

    The cutter's bottom edge runs along the end face in two collinear legs
    split at the major radius: the inner leg IS CutEndBreak (a driving,
    drawing-marked dimension), the outer leg the overshoot margin.  The
    split point is the one anchored to the origin, at the major radius."""
    from solidworks_mcp.adapters.base import RevolveParameters

    radius, end = MAJOR_RADIUS_MM, -CUT_LENGTH_MM
    leg = CUT_END_BREAK_MM + DEBURR_MARGIN_MM
    outer = radius + DEBURR_MARGIN_MM
    await set_global(adapter, DEBURR_MARGIN_GLOBAL, f"{DEBURR_MARGIN_MM}mm")
    dims = SketchDims()
    with no_sketch_inference(adapter):
        check(
            f"create_sketch {DEBURR_PROFILE}", await adapter.create_sketch("Front")
        )
        lines = await add_line_chain(
            adapter,
            [
                (radius - CUT_END_BREAK_MM, end),
                (radius, end),
                (outer, end),
                (outer, end + leg),
            ],
        )
        for line, direction in zip(
            lines[:3], ("horizontal", "horizontal", "vertical"), strict=True
        ):
            check(
                f"{DEBURR_PROFILE} {direction}",
                await adapter.add_sketch_constraint(line, None, direction),
            )
        await anchor_point_to_origin(
            adapter, f"{lines[1]}.start", radius, end, DEBURR_PROFILE
        )
        dims.record("CutterRadius")
        dims.record("CutEnd", DEBURR_DRIVES["CutEnd"])
        await dimension_between(
            adapter,
            f"{lines[0]}.start",
            f"{lines[0]}.end",
            "horizontal_distance",
            CUT_END_BREAK_MM,
            f"{DEBURR_PROFILE} break",
        )
        dims.record(CUT_END_BREAK_DIMENSION)
        await dimension_between(
            adapter,
            f"{lines[1]}.start",
            f"{lines[1]}.end",
            "horizontal_distance",
            DEBURR_MARGIN_MM,
            f"{DEBURR_PROFILE} margin",
        )
        dims.record("CutterMargin", DEBURR_DRIVES["CutterMargin"])
        await dimension_between(
            adapter,
            f"{lines[2]}.start",
            f"{lines[2]}.end",
            "vertical_distance",
            leg,
            f"{DEBURR_PROFILE} rise",
        )
        dims.record("CutterRise", DEBURR_DRIVES["CutterRise"])
        axis = adapter.currentSketchManager.CreateCenterLine(
            0.0, (end - leg) / 1000.0, 0.0, 0.0, (end + 2.0 * leg) / 1000.0, 0.0
        )
        if axis is None:
            raise RuntimeError(f"{DEBURR_PROFILE}: screw axis centreline failed")
        axis_id = adapter._register_sketch_entity("Line", axis)
        check(
            f"{DEBURR_PROFILE} fix axis",
            await adapter.add_sketch_constraint(axis_id, None, "fix"),
        )
        await ensure_fully_defined(adapter, f"{DEBURR_PROFILE} sketch")
        check(f"exit_sketch {DEBURR_PROFILE}", await adapter.exit_sketch())
    name_last_feature(adapter, DEBURR_PROFILE)
    drives = dims.apply(adapter, DEBURR_PROFILE)
    check(
        DEBURR_FEATURE,
        await adapter.create_revolve(RevolveParameters(angle=360.0, is_cut=True)),
    )
    name_last_feature(adapter, DEBURR_FEATURE)
    for dimension, expression in drives:
        await drive_dimension(adapter, dimension, expression)


async def _modify_stock(adapter) -> None:
    """Trim the supplied screw at CutLength and break the new end."""
    stock = await _volume_mm3(adapter)
    await _trim_to_cut_length(adapter)
    await force_rebuild(adapter)
    trimmed = await _volume_mm3(adapter)
    _check_removed("trim to cut length", stock, trimmed, TRIM_REMOVED_MM3)
    rim_before = _end_face_rim_radius_mm(adapter, -CUT_LENGTH_MM, phase="trimmed")
    await _break_cut_end(adapter)
    await force_rebuild(adapter)
    finished = await _volume_mm3(adapter)
    _check_removed(
        "trim and cut-end break",
        stock,
        finished,
        TRIM_REMOVED_MM3 + CUT_END_DEBURR_REMOVED_MM3,
    )
    # The break is too small for a volume gate to resolve: ~0.015 mm^3
    # against a mass-properties residual of 0.13-0.18 mm^3 on this threaded
    # body (the first seat leaf of 198071f23 read the finished screw 0.027
    # mm^3 LARGER than the trimmed one).  The end face's rim is exact, so it
    # proves the break on its own, before against after.
    brk = _model_dimension_mm(adapter, CUT_END_BREAK_SKETCH, CUT_END_BREAK_DIMENSION)
    rim_after = _end_face_rim_radius_mm(adapter, -CUT_LENGTH_MM, phase="broken")
    with _telemetry.span(
        "cut_end.break_proof",
        rim_before_mm=rim_before,
        rim_after_mm=rim_after,
        break_mm=brk,
        volume_delta_mm3=trimmed - finished,
        volume_expected_mm3=CUT_END_DEBURR_REMOVED_MM3,
    ):
        cut_in = assert_break_removed_metal(rim_before, rim_after, brk)
    _telemetry.success(
        f"cut end: rim radius {rim_before:.4f} -> {rim_after:.4f}, "
        f"major less CutEndBreak {brk:g} (cut in {cut_in:.4f})"
    )


def _single_limit_break(adapter) -> None:
    """CutEndBreak as a MAX-limit dimension carrying the band's deviations."""
    lower, upper = deviations(CUT_END_BREAK_BAND)
    _, dimension = _named_dimension(
        adapter, CUT_END_BREAK_SKETCH, CUT_END_BREAK_DIMENSION
    )
    label = f"{CUT_END_BREAK_DIMENSION}@{CUT_END_BREAK_SKETCH}"
    if not math.isclose(
        float(dimension.SystemValue), CUT_END_BREAK_MAX_MM / 1000.0, abs_tol=1e-12
    ):
        raise RuntimeError(f"{label}: nominal is not the band's max")
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    tolerance.Type = CUT_END_BREAK_TOL_TYPE
    if not tolerance.SetValues(lower / 1000.0, upper / 1000.0):
        raise RuntimeError(f"{label}: SetValues rejected {lower:+g}/{upper:+g} mm")
    if (
        int(tolerance.Type) != CUT_END_BREAK_TOL_TYPE
        or not math.isclose(float(tolerance.GetMinValue()), lower / 1000.0, abs_tol=1e-12)
        or not math.isclose(float(tolerance.GetMaxValue()), upper / 1000.0, abs_tol=1e-12)
    ):
        raise RuntimeError(f"{label}: MAX-limit tolerance readback changed")
    _telemetry.success(f"{label}: single limit {CUT_END_BREAK_TEXT}")


def _manufacturing_controls(adapter) -> None:
    """Places, the break's band and drawing marks; the sheet's note."""
    cut_end = _cut_end_y_mm(adapter)
    if abs(cut_end + CUT_LENGTH_MM) > 1e-4:
        raise RuntimeError(
            f"solid cut end at y={cut_end:.4f} is not the dimensioned "
            f"{CUT_LENGTH_MM} below the under-head face"
        )
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    # The cut end's deburr prints as the single limit "0.1 MAX" (swTolMAX)
    # in the sheet's tip detail; the band's deviations stay on the native
    # tolerance, read back, as the model's record of "none to 0.1".  The cut
    # length stays unbanded (reference): no fixed length suits every post and
    # plate.
    _single_limit_break(adapter)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    # The stock helper's reference pass hides the sketches with the recipe's.
    apply_drawing_properties(
        adapter, PART_NAME, {"Manufacturing Notes": MANUFACTURING_NOTES}
    )


@wraps(build_40923898)
async def _cut_to_length(adapter, truth=None, **parameters):
    # The shared recipe builds the supplied screw; the trim cuts it to fit.
    receipt = await build_40923898(adapter, truth, **parameters)
    await _author_cut_controls(adapter)
    await _modify_stock(adapter)
    _manufacturing_controls(adapter)
    return receipt


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(
            StockComponent(
                sku="40923898",
                author=_cut_to_length,
                transform=RigidTransform(),
            ),
        ),
        material=MATERIAL,
        screw_axis_planes=("Front Plane", "Right Plane"),
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
