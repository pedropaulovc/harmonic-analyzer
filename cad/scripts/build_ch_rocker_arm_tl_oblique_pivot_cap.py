"""Build the native MHA-CH-06-TL-30 captured-flange cap.

Front-plane XY plate, +Z thickness, reversed underside pocket, through
aperture and bolt holes, top circular counterbores, outward FULL-WIDTH mouths
and independent shallow safety-wire channels. All cuts are real features.
"""

from __future__ import annotations

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
from _part_checks import report_mass_properties, volume_check
from _part_pmi import author_part_pmi
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _saved_part_guard import require_saved_drawing_properties
from _session import run_build
from _sketch import SketchDims, add_line_chain, anchor_point_to_origin, blank_reference_sketches, dimension_between, ensure_fully_defined, set_sketch_direct_db
from _sketch_chains import define_rectilinear_chain
from _sketch_circle import define_circle
from _sketch_rectangle import define_centered_rectangle
from _visibility import blank_reference_geometry
import ch_rocker_arm_tl_oblique_pivot_cap_spec as spec

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
    blank_reference_sketches(adapter, spec.REFERENCE_SKETCHES)
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
        size = "PocketDia" if profile == "PocketProfile" else "ApertureDia"
        dims = SketchDims()
        check(profile, await adapter.create_sketch(plane))
        await define_circle(adapter, 0.0, 0.0, dia / 2.0, profile, dims=dims, names=(None, None, size), drives=(None, None, f'"{size}"'))
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
    await volume_check(adapter, "complete cap including open mouths and channels", spec.VOLUME_MM3, 0.001 * spec.VOLUME_MM3)
    bodies = tuple(_early_bound(adapter.currentModel, "IPartDoc").GetBodies2(0, False) or ())
    if len(bodies) != 1:
        raise RuntimeError(f"cap: expected one solid, found {len(bodies)}")
    set_dimension_bilateral_tolerance(adapter, "PocketProfile", "PocketDia", *deviations(spec.POCKET_BAND))
    set_dimension_bilateral_tolerance(adapter, "ApertureProfile", "ApertureDia", *deviations(spec.DRILLED_BAND))
    set_dimension_bilateral_tolerance(adapter, "BoltProfile", "BoltHoleDia", *deviations(spec.DRILLED_BAND))
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
    author_part_pmi(adapter, datums=spec.PART_DATUMS, controls=spec.GEOMETRIC_CONTROLS, surface_finishes=spec.SURFACE_FINISHES)
    apply_drawing_properties(adapter, PART_NAME, {"Isometric View Note": spec.ISOMETRIC_VIEW_NOTE})
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(adapter, _SAVED_DRAWING_PROPERTIES)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
