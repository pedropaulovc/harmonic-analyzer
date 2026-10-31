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
from _sketch_chains import define_rectilinear_chain
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


@_telemetry.traced("sketch.stop_rebate_profile")
async def rebate_profile(adapter: Any, dims: SketchDims) -> None:
    """The X-through rebate's profile on the Right plane (local X is -Z).

    The profile owns the rebate's real edges: WindowWidth along the roof
    underside from the cover face (Z=0), WindowHeight down the rebate's back
    face, and BackWall on a construction line from the rebate's back corner
    to the block's back face. The cut consumes this sketch, so the drawing
    imports its dimensions without showing any sketch line; shown reference
    chords ghosted over the rebate ceiling and across the back wall (machinist
    review, run 20261024T043544205Z-432c211c).
    """
    check("open rebate profile", await adapter.create_sketch("Right"))
    points = [
        (-spec.WINDOW_Z_MIN, spec.WINDOW_Y_MAX), (-spec.WINDOW_Z_MAX, spec.WINDOW_Y_MAX),
        (-spec.WINDOW_Z_MAX, spec.WINDOW_Y_MIN), (-spec.WINDOW_Z_MIN, spec.WINDOW_Y_MIN),
    ]
    lines = await add_line_chain(adapter, points)
    # Emission order: roof-underside span, back-face height, then the corner's
    # on-axis (Z=0) anchor, which adds only its height.
    await define_rectilinear_chain(
        adapter, lines, points, label="open rebate", dims=dims,
        names=["WindowWidth", "WindowHeight", "WindowRoofStation"],
        drives=['"WindowWidth"', '"WindowHeight"', '"BlockHeight" - "RoofThickness"'],
    )
    # add_line_chain restores AddToDB even when the line is refused.
    (wall,) = await add_line_chain(
        adapter, [points[1], (-spec.BLOCK_DEPTH, spec.WINDOW_Y_MAX)], close=False,
    )
    segment = _early_bound(adapter._sketch_entities[wall], "ISketchSegment")
    segment.ConstructionGeometry = True
    if not segment.ConstructionGeometry:
        raise RuntimeError("back wall construction flag rejected")
    check("back wall", await adapter.add_sketch_constraint(wall, None, "horizontal"))
    check("back wall", await adapter.add_sketch_constraint(
        f"{wall}.start", f"{lines[0]}.end", "coincident"))
    await dimension_between(adapter, f"{wall}.start", f"{wall}.end",
                            "horizontal_distance", spec.BACK_WALL_THICKNESS, "back wall")
    dims.record("BackWall", '"BlockDepth" - "WindowWidth"')
    await ensure_fully_defined(adapter, "rebate profile")
    check("exit rebate profile", await adapter.exit_sketch())


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
