"""Build the native MHA-CH-06-TL-30 captured-flange cap.

Front-plane XY plate, +Z thickness, reversed underside pocket, through
aperture and bolt holes, top circular counterbores, outward FULL-WIDTH mouths,
independent safety-wire channels and two merged underside registers.
"""

from __future__ import annotations

import math
import sys

from _appearance import apply_material
from _bore_axis import name_bore_axis
from _check import check
from _com import _early_bound
from _dimensions import drive_dimension, name_dimensions, set_global
from _drawing_marks import apply_drawing_properties, clear_dimensions_for_drawing, mark_dimensions_for_drawing
from _drawing_precision import _named_dimension, apply_drawing_precision
from _drawing_tolerances import set_dimension_bilateral_tolerance
from _feature_tree import name_last_feature
from _fit_deviations import deviations
from _part_checks import bbox_extent_check, report_mass_properties, volume_check
from _part_pmi import author_part_pmi
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _saved_part_guard import require_saved_drawing_properties
from _session import run_build
from _sketch import SketchDims, add_line_chain, anchor_point_to_origin, anchor_point_to_point, blank_reference_sketches, dimension_between, ensure_fully_defined, set_sketch_direct_db
from _sketch_chains import define_rectilinear_chain
from _sketch_circle import define_circle
from _sketch_rectangle import define_centered_rectangle
from _visibility import blank_reference_geometry
import ch_rocker_arm_tl_oblique_pivot_cap_spec as spec
from ch_rocker_arm_tl_oblique_pivot_cap_spec import REFERENCE_SKETCHES

PART_NAME = "ch-rocker-arm-tl-oblique-pivot-cap"
MATERIAL = "Plain Carbon Steel"
_SAVED_DRAWING_PROPERTIES = ("Number", "Material Specification", "Finish", "Quantity", "Isometric View Note")


async def _rectangle(adapter, plane, feature, bounds, names, drives):
    dims = SketchDims()
    check(f"sketch {feature}", await adapter.create_sketch(plane))
    x0, y0, x1, y1 = bounds
    points = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    lines = await add_line_chain(adapter, points)
    await define_rectilinear_chain(adapter, lines, points, label=feature, dims=dims, names=names, drives=drives)
    await ensure_fully_defined(adapter, feature)
    check(f"exit {feature}", await adapter.exit_sketch())
    name_last_feature(adapter, feature)
    return dims.apply(adapter, feature)


async def _circle_from_stock_corner(adapter, dia, prefix, dims):
    """Locate a nominally centred circle from the real common -X/-Y corner."""
    manager = adapter.currentSketchManager
    previous = bool(manager.AddToDB)
    manager.AddToDB = True
    try:
        raw = manager.CreatePoint(-spec.WIDTH / 2000.0, -spec.LENGTH / 2000.0, 0.0)
    finally:
        manager.AddToDB = previous
    if raw is None:
        raise RuntimeError(f"{prefix}: stock-corner point creation failed")
    corner = adapter._register_sketch_entity("Point", raw)
    await anchor_point_to_origin(
        adapter, corner, -spec.WIDTH / 2.0, -spec.LENGTH / 2.0, f"{prefix} stock corner"
    )
    dims.record(f"{prefix}CornerX", '"CapWidth"/2')
    dims.record(f"{prefix}CornerY", '"CapLength"/2')
    manager.AddToDB = True
    try:
        circle = check(f"{prefix} circle", await adapter.add_circle(0.0, 0.0, dia / 2.0))
    finally:
        manager.AddToDB = previous
    await anchor_point_to_point(
        adapter, corner, f"{circle}.center", spec.WIDTH / 2.0, spec.LENGTH / 2.0,
        f"{prefix} centre from stock corner",
    )
    dims.record(f"{prefix}CenterX", '"CapWidth"/2')
    dims.record(f"{prefix}CenterY", '"CapLength"/2')
    check(f"{prefix} diameter", await adapter.add_sketch_dimension(circle, None, "diameter", dia))
    dims.record(f"{prefix}Dia", f'"{prefix}Dia"')
    return circle


async def _register_circles(adapter, pocket_circle, dims):
    """Dimension each boss centre from the actual PocketProfile circle centre.

    Re-register the external sketch entity after opening RegisterProfile; the
    adapter resolves its .center as an ISketchPoint, not the current origin.
    Positive native distances keep the signed side on which each circle is
    created, exactly as the ordinary bolt-coordinate dimensions do.
    """
    pocket_ref = adapter._register_sketch_entity("Circle", pocket_circle)
    manager = adapter.currentSketchManager
    for index, (x, y) in enumerate(spec.REGISTER_POINTS, 1):
        previous = bool(manager.AddToDB)
        manager.AddToDB = True
        try:
            circle = check(f"register {index}", await adapter.add_circle(x, y, spec.REGISTER_DIA / 2.0))
        finally:
            manager.AddToDB = previous
        await anchor_point_to_point(adapter, f"{pocket_ref}.center", f"{circle}.center", x, y, f"register {index} from pocket axis")
        dims.record(f"Register{index}X", '"RegisterX"')
        dims.record(f"Register{index}Y", '"RegisterY"')
        check(f"register {index} diameter", await adapter.add_sketch_dimension(circle, None, "diameter", spec.REGISTER_DIA))
        dims.record("RegisterDia" if index == 1 else "RegisterDia2", '"RegisterDia"')


async def _integral_registers(adapter, pocket_circle):
    from solidworks_mcp.adapters.base import ExtrusionParameters

    dims = SketchDims()
    check("register profile", await adapter.create_sketch("Front"))
    await _register_circles(adapter, pocket_circle, dims)
    await ensure_fully_defined(adapter, "register profile")
    check("exit register profile", await adapter.exit_sketch())
    name_last_feature(adapter, "RegisterProfile")
    jobs = dims.apply(adapter, "RegisterProfile")
    check("integral underside registers", await adapter.create_extrusion(ExtrusionParameters(
        depth=spec.REGISTER_PROJECTION, reverse_direction=True, merge_result=True,
    )))
    name_last_feature(adapter, "Registers")
    jobs.append((name_dimensions(adapter, "Registers", ["RegisterProjection"])[0], '"RegisterProjection"'))
    # Only the two free-end circular edges are selected. Never select a whole
    # cylindrical face: that would chamfer the locating roots as well.
    check("register free-end chamfers", await adapter.add_chamfer(
        spec.REGISTER_END_CHAMFER_MAX,
        [[x + spec.REGISTER_DIA / 2.0, y, -spec.REGISTER_PROJECTION] for x, y in spec.REGISTER_POINTS],
        tangent_propagation=False,
    ))
    name_last_feature(adapter, "RegisterEndChamfers")
    jobs.append((name_dimensions(adapter, "RegisterEndChamfers", ["RegisterEndChamfer"])[0], '"RegisterEndChamfer"'))
    return jobs


def _register_chamfer_maximum(adapter):
    """The native nominal is the printed MAX, with a recorded zero-to-max band."""
    _, dimension = _named_dimension(adapter, "RegisterEndChamfers", "RegisterEndChamfer")
    maximum = spec.REGISTER_END_CHAMFER_MAX / 1000.0
    if not math.isclose(float(dimension.SystemValue), maximum, abs_tol=1e-9):
        raise RuntimeError("register chamfer nominal is not the maximum")
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    tolerance.Type = 6  # swTolMAX
    if not tolerance.SetValues(-maximum, 0.0):
        raise RuntimeError("register chamfer MAX band was rejected")
    if (
        int(tolerance.Type) != 6
        or not math.isclose(float(tolerance.GetMinValue()), -maximum, abs_tol=1e-12)
        or not math.isclose(float(tolerance.GetMaxValue()), 0.0, abs_tol=1e-12)
    ):
        raise RuntimeError("register chamfer MAX band did not persist")


async def _entry_reliefs(adapter):
    """Flat-bottom underhead fillet reliefs, starting at the real head-seat Z."""
    from solidworks_mcp.adapters.base import ExtrusionParameters

    dims = SketchDims()
    check("underhead entry relief profile", await adapter.create_sketch(spec.BOLT_SEAT_PLANE))
    for index, (x, y) in enumerate(spec.BOLT_POINTS, 1):
        await define_circle(
            adapter, x, y, spec.ENTRY_RELIEF_DIA / 2.0, f"entry relief {index}",
            dims=dims,
            names=(f"Entry{index}X", f"Entry{index}Y", "EntryReliefDia" if index == 1 else f"EntryReliefDia{index}"),
            drives=('"BoltX"', '"BoltY"', '"EntryReliefDia"'),
        )
    await ensure_fully_defined(adapter, "underhead entry relief profile")
    check("exit underhead entry relief profile", await adapter.exit_sketch())
    name_last_feature(adapter, "EntryReliefProfile")
    jobs = dims.apply(adapter, "EntryReliefProfile")
    check("flat-bottom underhead entry reliefs", await adapter.create_cut_extrude(
        ExtrusionParameters(depth=spec.ENTRY_RELIEF_DEPTH),
    ))
    name_last_feature(adapter, "EntryReliefs")
    jobs.append((name_dimensions(adapter, "EntryReliefs", ["EntryReliefDepth"])[0], '"EntryReliefDepth"'))
    return jobs


async def _section_reference(adapter):
    """A named hidden sketch IN A-A owns its two imported linear sizes."""
    from solidworks_mcp.adapters.base import CreatePlaneParameters

    check("section plane", await adapter.create_plane(CreatePlaneParameters(mode="offset", base_plane="Top Plane", offset=0.0)))
    name_last_feature(adapter, spec.SECTION_PLANE)
    check("section reference", await adapter.create_sketch(spec.SECTION_PLANE))
    dims = SketchDims()
    # Top-plane coordinates (X,-Z): two independent construction lines on
    # visible section walls, anchored on the bottom seating face.
    for x, length, name, expression in (
        (-spec.WIDTH / 2.0, spec.HEIGHT, "CapHeight", '"CapHeight"'),
        (-spec.POCKET_DIA / 2.0, spec.POCKET_DEPTH, "PocketDepth", '"PocketDepth"'),
    ):
        set_sketch_direct_db(adapter, True)
        line = check(f"reference {name}", await adapter.add_line(x, 0.0, x, -length))
        set_sketch_direct_db(adapter, False)
        segment = _early_bound(adapter._sketch_entities[line], "ISketchSegment")
        segment.ConstructionGeometry = True
        if not bool(segment.ConstructionGeometry):
            raise RuntimeError(f"{name}: reference line is not construction")
        check(f"vertical {name}", await adapter.add_sketch_constraint(line, None, "vertical"))
        await anchor_point_to_origin(adapter, f"{line}.start", x, 0.0, name)
        dims.record(f"{name}WallX", '"CapWidth"/2' if name == "CapHeight" else '"PocketDia"/2')
        await dimension_between(adapter, f"{line}.start", f"{line}.end", "vertical_distance", length, name)
        dims.record(name, expression)
    await ensure_fully_defined(adapter, "cap section reference")
    check("exit section reference", await adapter.exit_sketch())
    name_last_feature(adapter, spec.SECTION_REFERENCE)
    blank_reference_sketches(adapter, REFERENCE_SKETCHES)
    return dims.apply(adapter, spec.SECTION_REFERENCE)


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import CreatePlaneParameters, ExtrusionParameters

    check("create cap part", await adapter.create_part())
    knobs = {
        "CapWidth": spec.WIDTH, "CapLength": spec.LENGTH, "CapHeight": spec.HEIGHT,
        "PocketDia": spec.POCKET_DIA, "PocketDepth": spec.POCKET_DEPTH,
        "ApertureDia": spec.APERTURE_DIA, "BoltHoleDia": spec.HOLE_DIA,
        "BoltX": abs(spec.BOLT_POINTS[0][0]), "BoltY": abs(spec.BOLT_POINTS[0][1]),
        "CounterboreDia": spec.COUNTERBORE_DIA, "CounterboreDepth": spec.COUNTERBORE_DEPTH,
        "WireWidth": spec.CHANNEL_WIDTH, "WireDepth": spec.CHANNEL_DEPTH,
        "RegisterX": abs(spec.REGISTER_POINTS[0][0]), "RegisterY": abs(spec.REGISTER_POINTS[0][1]),
        "RegisterDia": spec.REGISTER_DIA, "RegisterProjection": spec.REGISTER_PROJECTION,
        "RegisterEndChamfer": spec.REGISTER_END_CHAMFER_MAX,
        "EntryReliefDia": spec.ENTRY_RELIEF_DIA, "EntryReliefDepth": spec.ENTRY_RELIEF_DEPTH,
    }
    for name, value in knobs.items():
        await set_global(adapter, name, f"{value}mm")
    dims = SketchDims()
    check("cap outline", await adapter.create_sketch("Front"))
    await define_centered_rectangle(adapter, spec.WIDTH / 2.0, spec.LENGTH / 2.0, "cap outline", dims=dims, name_width="CapWidth", name_depth="CapLength", drive_width='"CapWidth"', drive_depth='"CapLength"')
    await ensure_fully_defined(adapter, "cap outline")
    check("exit outline", await adapter.exit_sketch())
    name_last_feature(adapter, "CapProfile")
    jobs = dims.apply(adapter, "CapProfile")
    check("extrude cap", await adapter.create_extrusion(ExtrusionParameters(depth=spec.HEIGHT)))
    name_last_feature(adapter, "Cap")
    jobs.append((name_dimensions(adapter, "Cap", ["CapThickness"])[0], '"CapHeight"'))
    await volume_check(adapter, "cap blank", spec.WIDTH * spec.LENGTH * spec.HEIGHT, 0.1)

    for name, offset, expression in (
        (spec.TOP_PLANE, spec.HEIGHT, '"CapHeight"'),
        (spec.BOLT_SEAT_PLANE, spec.HEIGHT - spec.COUNTERBORE_DEPTH, '"CapHeight"-"CounterboreDepth"'),
    ):
        check(name, await adapter.create_plane(CreatePlaneParameters(mode="offset", base_plane="Front Plane", offset=offset)))
        name_last_feature(adapter, name)
        jobs.append((name_dimensions(adapter, name, [f"{name}Offset"])[0], expression))

    for profile, cut, plane, dia, depth, reverse, both in (
        ("PocketProfile", "FlangePocket", "Front", spec.POCKET_DIA, spec.POCKET_DEPTH, True, False),
        ("ApertureProfile", "JournalAperture", "Front", spec.APERTURE_DIA, 2.0 * spec.HEIGHT, False, True),
    ):
        prefix = "Pocket" if profile == "PocketProfile" else "Aperture"
        dims = SketchDims()
        check(profile, await adapter.create_sketch(plane))
        circle = await _circle_from_stock_corner(adapter, dia, prefix, dims)
        if profile == "PocketProfile":
            pocket_circle = adapter._sketch_entities[circle]
        await ensure_fully_defined(adapter, profile)
        check(f"exit {profile}", await adapter.exit_sketch())
        name_last_feature(adapter, profile)
        jobs += dims.apply(adapter, profile)
        check(cut, await adapter.create_cut_extrude(ExtrusionParameters(depth=depth, reverse_direction=reverse, both_directions=both)))
        name_last_feature(adapter, cut)
        if cut == "FlangePocket":
            jobs.append((name_dimensions(adapter, cut, ["PocketCutDepth"])[0], '"PocketDepth"'))

    for profile, cut, plane, dia, depth in (
        ("BoltProfile", "BoltHoles", spec.TOP_PLANE, spec.HOLE_DIA, 2.0 * spec.HEIGHT),
        ("HeadProfile", "HeadRecesses", spec.TOP_PLANE, spec.COUNTERBORE_DIA, spec.COUNTERBORE_DEPTH),
    ):
        dims = SketchDims()
        check(profile, await adapter.create_sketch(plane))
        for index, (x, y) in enumerate(spec.BOLT_POINTS, 1):
            size = ("BoltHoleDia" if profile == "BoltProfile" else "CounterboreDia") + ("" if index == 1 else str(index))
            prefix = "Bolt" if profile == "BoltProfile" else "Head"
            await define_circle(adapter, x, y, dia / 2.0, f"{profile} {index}", dims=dims, names=(f"{prefix}{index}X", f"{prefix}{index}Y", size), drives=('"BoltX"', '"BoltY"', '"BoltHoleDia"' if profile == "BoltProfile" else '"CounterboreDia"'))
        await ensure_fully_defined(adapter, profile)
        check(f"exit {profile}", await adapter.exit_sketch())
        name_last_feature(adapter, profile)
        jobs += dims.apply(adapter, profile)
        check(cut, await adapter.create_cut_extrude(ExtrusionParameters(depth=depth)))
        name_last_feature(adapter, cut)
        jobs.append((name_dimensions(adapter, cut, ["CounterboreDepth" if cut == "HeadRecesses" else "BoltCutDepth"])[0], '"CounterboreDepth"' if cut == "HeadRecesses" else '2*"CapHeight"'))

    jobs += await _entry_reliefs(adapter)

    # Separate rectangles overlap the already-cut circular recesses. The
    # outside endpoint overruns the stock by 1 mm to leave a genuinely open
    # mouth, not a coincident-edge slit. Width matches the actual recess.
    for index, (x, y) in enumerate(spec.BOLT_POINTS, 1):
        edge = (spec.WIDTH / 2.0 + 1.0) * (1.0 if x > 0.0 else -1.0)
        x0, x1 = sorted((x, edge))
        jobs += await _rectangle(adapter, spec.TOP_PLANE, f"MouthProfile{index}", (x0, y - spec.COUNTERBORE_DIA / 2.0, x1, y + spec.COUNTERBORE_DIA / 2.0), [f"Mouth{index}Length", f"Mouth{index}Width", f"Mouth{index}X", f"Mouth{index}Y"], ['"CapWidth"/2+1mm-"BoltX"', '"CounterboreDia"', '"BoltX"' if x > 0.0 else '"CapWidth"/2+1mm', '"BoltY"-"CounterboreDia"/2' if y > 0.0 else '"BoltY"+"CounterboreDia"/2'])
        check(f"mouth {index}", await adapter.create_cut_extrude(ExtrusionParameters(depth=spec.COUNTERBORE_DEPTH)))
        name_last_feature(adapter, f"HeadAccess{index}")
        jobs.append((name_dimensions(adapter, f"HeadAccess{index}", [f"MouthDepth{index}"])[0], '"CounterboreDepth"'))

    for index, y in enumerate(sorted({y for _, y in spec.BOLT_POINTS}), 1):
        jobs += await _rectangle(adapter, spec.TOP_PLANE, f"WireProfile{index}", (-knobs["BoltX"], y - spec.CHANNEL_WIDTH / 2.0, knobs["BoltX"], y + spec.CHANNEL_WIDTH / 2.0), [f"WireSpan{index}", "WireWidth" if index == 1 else "WireWidth2", f"WireX{index}", f"WireY{index}"], ['2*"BoltX"', '"WireWidth"', '"BoltX"', '"BoltY"-"WireWidth"/2' if y > 0.0 else '"BoltY"+"WireWidth"/2'])
        check(f"wire channel {index}", await adapter.create_cut_extrude(ExtrusionParameters(depth=spec.CHANNEL_DEPTH)))
        name_last_feature(adapter, f"WireChannels{index}")
        jobs.append((name_dimensions(adapter, f"WireChannels{index}", ["WireDepth" if index == 1 else "WireDepth2"])[0], '"WireDepth"'))

    jobs += await _integral_registers(adapter, pocket_circle)
    jobs += await _section_reference(adapter)
    await name_bore_axis(adapter, "Right Plane", 0.0, "Top Plane", 0.0, "capture axis")
    name_last_feature(adapter, spec.AXIS_NAME)
    for axis, (x, y) in zip(spec.BOLT_AXES, spec.BOLT_POINTS, strict=True):
        await name_bore_axis(adapter, "Right Plane", x, "Top Plane", y, axis, drive_a='"BoltX"', drive_b='"BoltY"', drive_jobs=jobs)
        name_last_feature(adapter, axis)
    blank_reference_geometry(adapter, ((spec.TOP_PLANE, "PLANE"), (spec.BOLT_SEAT_PLANE, "PLANE"), (spec.SECTION_PLANE, "PLANE")))
    await force_rebuild(adapter)
    for dimension, expression in jobs:
        await drive_dimension(adapter, dimension, expression)
    await force_rebuild(adapter)
    await volume_check(adapter, "complete cap including integral registers and end chamfers", spec.VOLUME_MM3, 0.05)
    await bbox_extent_check(adapter, "cap including underside registers", "z", spec.TOTAL_HEIGHT, 0.001)
    bodies = tuple(_early_bound(adapter.currentModel, "IPartDoc").GetBodies2(0, False) or ())
    if len(bodies) != 1:
        raise RuntimeError(f"cap: expected one solid, found {len(bodies)}")
    set_dimension_bilateral_tolerance(adapter, "PocketProfile", "PocketDia", *deviations(spec.POCKET_BAND))
    set_dimension_bilateral_tolerance(adapter, "ApertureProfile", "ApertureDia", *deviations(spec.APERTURE_BAND))
    set_dimension_bilateral_tolerance(adapter, "BoltProfile", "BoltHoleDia", *deviations(spec.DRILLED_BAND))
    for index in range(1, len(spec.BOLT_POINTS) + 1):
        name = "EntryReliefDia" if index == 1 else f"EntryReliefDia{index}"
        set_dimension_bilateral_tolerance(adapter, "EntryReliefProfile", name, *deviations(spec.ENTRY_RELIEF_BAND))
    for name in ("RegisterDia", "RegisterDia2"):
        set_dimension_bilateral_tolerance(adapter, "RegisterProfile", name, *deviations(spec.REGISTER_BAND))
    _register_chamfer_maximum(adapter)
    # Fitted nominal is reference, not a second controlling depth band.
    display, dimension = _named_dimension(adapter, spec.SECTION_REFERENCE, "PocketDepth")
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    tolerance.Type = 0  # swTolNONE
    display.SetText(1, "(")
    display.SetText(2, ")")
    if str(display.GetText(1)) != "(" or str(display.GetText(2)) != ")" or int(tolerance.Type) != 0:
        raise RuntimeError("pocket reference notation did not persist")
    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    apply_drawing_precision(adapter, spec.DRAWING_PRECISION)
    clear_dimensions_for_drawing(adapter)
    for feature, names in spec.DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature, names)
    author_part_pmi(adapter, surface_finishes=spec.SURFACE_FINISHES)
    apply_drawing_properties(adapter, PART_NAME, {"Isometric View Note": spec.ISOMETRIC_VIEW_NOTE})
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(adapter, _SAVED_DRAWING_PROPERTIES)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
