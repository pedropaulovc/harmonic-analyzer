"""Offline contracts for rebuild-free drawing annotation authoring."""

from __future__ import annotations

import ast
import inspect
from collections.abc import Callable

import _drawing_common as drawing_common
import draw_cone_pivot_post
import draw_cone_swing_platform
import draw_crank_pin
import draw_pen_marker
import draw_pivot_ball_mount


_REBUILD_CALLS = {"EditRebuild3", "ForceRebuild3", "GraphicsRedraw2"}


def _called_methods(function: Callable[..., object]) -> set[str]:
    tree = ast.parse(inspect.getsource(function))
    return {
        call.func.attr
        for call in ast.walk(tree)
        if isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
    }


def test_simple_common_annotation_helpers_do_not_rebuild() -> None:
    helpers = (
        drawing_common.add_datum_feature,
        drawing_common.add_feature_control_frame,
        drawing_common.add_surface_finish,
        drawing_common.add_view_centerline,
        drawing_common.add_native_hole_callout,
        drawing_common.delete_unnamed_imports,
        drawing_common.set_dimension_callouts,
        drawing_common.set_dimension_text,
        drawing_common.set_reference_dimension,
        drawing_common.set_dimension_precision,
        drawing_common.set_reference_dimensions,
        drawing_common.set_basic_dimension,
    )

    for helper in helpers:
        assert _called_methods(helper).isdisjoint(_REBUILD_CALLS), helper.__name__


def test_simple_recipe_annotation_helpers_do_not_rebuild() -> None:
    helpers = (
        draw_cone_pivot_post._add_crank_axis_table,
        draw_cone_swing_platform._add_cone_axis_centerline,
        draw_crank_pin._add_end_diameter,
        draw_pen_marker._display_as_diameter,
        draw_pen_marker._add_axis_centerline,
        draw_pivot_ball_mount._set_stem_dimension_format,
    )

    for helper in helpers:
        assert _called_methods(helper).isdisjoint(_REBUILD_CALLS), helper.__name__
