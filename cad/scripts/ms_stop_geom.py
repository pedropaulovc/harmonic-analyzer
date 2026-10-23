"""Native authoring shared by the two stop parts; dimensions live in ms_stop_spec."""

from __future__ import annotations

from typing import Any

import _telemetry
import ms_stop_spec as spec
from _check import check
from _com import _early_bound
from _dimensions import name_dimensions
from _feature_tree import name_last_feature
from _sketch import (
    SketchDims, add_line_chain, anchor_point_to_origin, dimension_between,
    ensure_fully_defined,
)
from _sketch_circle import define_circle
from _drawing_precision import set_dimension_display_precision
from _visibility import blank_sketch_feature


@_telemetry.traced("sketch.stop_location", label_param="feature")
async def location_reference(
    adapter: Any, *, feature: str, plane: str, spans: tuple[float, ...],
    station: float, names: tuple[str, ...],
) -> None:
    """Baseline construction chords from the finished X=0 or Z=0 face.

    The first chord owns its span and the shared perpendicular station; later
    chords share its starting point and carry just their own baseline span.
    """
    check(f"create sketch {feature}", await adapter.create_sketch(plane))
    first = None
    for index, span in enumerate(spans):
        (line,) = await add_line_chain(adapter, [(0.0, station), (span, station)], close=False)
        segment = _early_bound(adapter._sketch_entities[line], "ISketchSegment")
        segment.ConstructionGeometry = True
        if not segment.ConstructionGeometry:
            raise RuntimeError(f"{feature}: construction flag rejected")
        check(feature, await adapter.add_sketch_constraint(line, None, "horizontal"))
        await dimension_between(adapter, f"{line}.start", f"{line}.end",
                                "horizontal_distance", abs(span), feature)
        if index == 0:
            await anchor_point_to_origin(adapter, f"{line}.start", 0.0, station, feature)
            first = line
        else:
            check(feature, await adapter.add_sketch_constraint(
                f"{line}.start", f"{first}.start", "coincident"))
    await ensure_fully_defined(adapter, feature)
    check(f"exit sketch {feature}", await adapter.exit_sketch())
    name_last_feature(adapter, feature)
    name_dimensions(adapter, feature, list(names))


@_telemetry.traced("sketch.stop_window_width")
async def window_width_reference(adapter: Any) -> list[tuple[str, str]]:
    """Own the rebate span on its real roof edge, not the cut-depth vector.

    Right-plane local X is -Z. The chord therefore runs from the cover's
    Z=0 edge to the rebate's Z=WindowWidth edge at the roof station. It is
    construction-only: editing the shared globals moves both cut and witness.
    """
    feature = "ReferenceWindowWidth"
    await location_reference(
        adapter, feature=feature, plane="Right",
        spans=(-spec.WINDOW_WIDTH,), station=spec.WINDOW_Y_MAX,
        names=("WindowWidth", "WindowRoofStation"),
    )
    return [
        (f"WindowWidth@{feature}", '"WindowWidth"'),
        (f"WindowRoofStation@{feature}", '"BlockHeight" - "RoofThickness"'),
    ]


@_telemetry.traced("appearance.stop_reference_sketches")
def hide_location_references(adapter: Any, names: tuple[str, ...]) -> None:
    model = _early_bound(adapter.currentModel, "IPartDoc")
    for name in names:
        feature = model.FeatureByName(name)
        if feature is None:
            raise RuntimeError(f"missing stop location sketch {name}")
        blank_sketch_feature(adapter.currentModel, _early_bound(feature, "IFeature"), name)


@_telemetry.traced("dim.stop_hole_precision", label_param="feature_name")
def author_hole_precision(adapter: Any, feature_name: str) -> None:
    """Persist hole-callout length precision on its source model dimensions."""
    model = _early_bound(adapter.currentModel, "IPartDoc")
    raw = model.FeatureByName(feature_name)
    if raw is None:
        raise RuntimeError(f"missing native stop hole {feature_name}")
    pending = [raw]
    count = 0
    while pending:
        feature = _early_bound(pending.pop(), "IFeature")
        child = feature.GetFirstSubFeature()
        while child is not None:
            pending.append(child)
            child = _early_bound(child, "IFeature").GetNextSubFeature()
        display = feature.GetFirstDisplayDimension()
        while display is not None:
            display = _early_bound(display, "IDisplayDimension")
            dimension = _early_bound(display.GetDimension2(0), "IDimension")
            leaf = str(dimension.FullName).split("@", 1)[0]
            set_dimension_display_precision(
                adapter, str(feature.Name), leaf, spec.HOLE_CALLOUT_PRECISION,
                display=display,
            )
            count += 1
            display = feature.GetNextDisplayDimension(display)
    if not count:
        raise RuntimeError(f"{feature_name}: no native dimensions to precision")


@_telemetry.traced("sketch.stop_roof_thickness")
async def roof_reference(adapter: Any) -> list[tuple[str, str]]:
    """Direct roof thickness on the lip's cover-side face (Z=0).

    The chord lies on the real lip edge, so the shown construction line hides
    under the outline instead of ghosting through the lip at the rebate wall.
    """
    feature = "RoofThicknessReference"
    check(feature, await adapter.create_sketch("Right"))
    # add_line_chain restores AddToDB even when the line is refused.
    (line,) = await add_line_chain(adapter, [
        (-spec.WINDOW_Z_MIN, spec.WINDOW_Y_MAX), (-spec.WINDOW_Z_MIN, spec.BLOCK_HEIGHT),
    ], close=False)
    segment = _early_bound(adapter._sketch_entities[line], "ISketchSegment")
    segment.ConstructionGeometry = True
    if not segment.ConstructionGeometry:
        raise RuntimeError("roof reference construction flag rejected")
    check(feature, await adapter.add_sketch_constraint(line, None, "vertical"))
    await dimension_between(adapter, f"{line}.start", f"{line}.end",
                            "vertical_distance", spec.ROOF_THICKNESS, feature)
    await anchor_point_to_origin(adapter, f"{line}.start",
                                 -spec.WINDOW_Z_MIN, spec.WINDOW_Y_MAX, feature)
    await ensure_fully_defined(adapter, feature)
    check(feature, await adapter.exit_sketch())
    name_last_feature(adapter, feature)
    # WINDOW_Z_MIN is 0: the start point's on-axis anchor adds only its station.
    names = name_dimensions(adapter, feature, ["RoofThickness", "RoofWindowStation"])
    return list(zip(names, [
        '"RoofThickness"', '"BlockHeight" - "RoofThickness"',
    ], strict=True))


@_telemetry.traced("sketch.stop_back_wall")
async def back_wall_reference(adapter: Any) -> list[tuple[str, str]]:
    """Direct back wall, from the rebate's back face to the block's back face.

    Right-plane local X is -Z. The chord continues the rebate-width chord at
    the roof station, so 8.40 and the wall chain from the cover face; the
    block depth is their sum and prints only as a reference.
    """
    feature = "BackWallReference"
    check(feature, await adapter.create_sketch("Right"))
    # add_line_chain restores AddToDB even when the line is refused.
    (line,) = await add_line_chain(adapter, [
        (-spec.WINDOW_Z_MAX, spec.WINDOW_Y_MAX), (-spec.BLOCK_DEPTH, spec.WINDOW_Y_MAX),
    ], close=False)
    segment = _early_bound(adapter._sketch_entities[line], "ISketchSegment")
    segment.ConstructionGeometry = True
    if not segment.ConstructionGeometry:
        raise RuntimeError("back wall reference construction flag rejected")
    check(feature, await adapter.add_sketch_constraint(line, None, "horizontal"))
    await dimension_between(adapter, f"{line}.start", f"{line}.end",
                            "horizontal_distance", spec.BACK_WALL_THICKNESS, feature)
    await anchor_point_to_origin(adapter, f"{line}.start",
                                 -spec.WINDOW_Z_MAX, spec.WINDOW_Y_MAX, feature)
    await ensure_fully_defined(adapter, feature)
    check(feature, await adapter.exit_sketch())
    name_last_feature(adapter, feature)
    # Both anchor coordinates are non-zero: station along -Z, then height.
    names = name_dimensions(adapter, feature, ["BackWall", "BackWallStationZ", "BackWallStationY"])
    return list(zip(names, [
        '"BlockDepth" - "WindowWidth"', '"WindowWidth"', '"BlockHeight" - "RoofThickness"',
    ], strict=True))


@_telemetry.traced("sketch.stop_plate_pilot")
async def pilot_drill_reference(adapter: Any) -> list[tuple[str, str]]:
    """Own the earlier match-drill size without changing the finished clearance.

    The final cover only has the opened clearance holes. The construction
    circle sits concentrically inside an actual clearance, representing the
    earlier PILOT step before THEN OPEN, not another finished edge. Its native
    diameter and precision remain model-owned when the drawing shows the sketch.
    """
    feature = "PilotDrillReference"
    dimensions = SketchDims()
    check(feature, await adapter.create_sketch("Front"))
    circle = await define_circle(
        adapter, spec.PLATE_HOLE_XS[0], spec.PLATE_HOLE_Y,
        spec.PLATE_TAP_DRILL_DIA / 2.0, feature,
        dims=dimensions, names=(None, None, "PilotDrillDiameter"),
        drives=(None, None, '"PilotDrillDiameter"'),
    )
    segment = _early_bound(adapter._sketch_entities[circle], "ISketchSegment")
    segment.ConstructionGeometry = True
    if not segment.ConstructionGeometry:
        raise RuntimeError("pilot reference construction flag rejected")
    await ensure_fully_defined(adapter, feature)
    check(feature, await adapter.exit_sketch())
    name_last_feature(adapter, feature)
    return dimensions.apply(adapter, feature)
