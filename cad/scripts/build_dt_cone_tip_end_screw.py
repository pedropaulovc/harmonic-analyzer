r"""Build MHA-DT-39, the cone tip end screw: McMaster 91794A558 plus one hole.

The shared catalog recipe (``diag_build_91794A558``) builds the supplied
1/4-28 x 5/8 slotted fillister screw in its stock frame; this builder then
adds the one shop operation, the pivot hole drilled and reamed concentric in
the threaded end (``dt_cone_tip_end_screw_spec``; the MHA-DT-VN-61 post
mount screw's pattern of a part-owned modification after the stock recipe).

The hole is a plain cut-extrude from the threaded end face (``TipFace``): an
on-axis circle carries its diameter (the reamed band, on the model
dimension) and the cut's blind depth its full-diameter depth (.XX), so the
drawing's native hole callout prints size, band and depth from the model.
An analytic volume check proves the cut.

Frame: the stock frame, untransformed.  Axis local Y (``ScrewAxis``), head
up, under-head face at y = 0, threaded end face at y = -SHANK_LEN
(``TipFace``, the reference plane the assembly mates on the bushing).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_dt_cone_tip_end_screw.py
"""

from __future__ import annotations

import math
import sys
from functools import wraps

import _telemetry
from _check import check
from _com import _early_bound
from _dimensions import drive_dimension, name_dimensions, set_global
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _drawing_precision import apply_drawing_precision
from _drawing_tolerances import set_dimension_bilateral_tolerance
from _fastener_catalog import fastener
from _feature_tree import name_last_feature
from _fit_deviations import deviations
from _rebuild import force_rebuild
from _session import run_build
from _simplified_part import save_simplified_part
from _sketch import SketchDims, ensure_fully_defined
from _sketch_circle import define_circle
from _stock_fastener import RigidTransform, StockComponent, build_stock_fastener
from _visibility import blank_reference_geometry
from diagnostics.diag_build_91794A558 import build_91794A558
from dt_cone_tip_end_screw_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    END_HOLE_BAND,
    END_HOLE_DEPTH,
    END_HOLE_DIA,
    HOLE_CUT,
    HOLE_FEATURE,
    ISOMETRIC_VIEW_NOTE,
    SHANK_LEN,
    SKU,
    TIP_FACE,
    UNIT,
)
from solidworks_mcp.adapters.com_variant import double_array

PART_NAME = "dt-cone-tip-end-screw"

SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material
if SPEC.skus != (SKU,):
    raise AssertionError(f"{PART_NAME} catalogues {SPEC.skus}, not {SKU}")

HOLE_R = END_HOLE_DIA / 2.0
V_HOLE = math.pi * HOLE_R**2 * END_HOLE_DEPTH
# The cut is exact; SolidWorks' mass properties read to its tessellation.
HOLE_VOLUME_TOL_MM3 = 0.005 * V_HOLE


async def _volume_mm3(adapter) -> float:
    mass = await adapter.get_mass_properties()
    if not mass.is_success:
        raise RuntimeError(f"get_mass_properties failed: {mass.error}")
    return float(mass.data.volume)


def _sketch_normal_along_model_y(adapter) -> float:
    """+1 or -1: the active sketch's normal (its z) per model +Y.  TipFace is
    the Top plane offset to the far side, so which way its normal points is
    the sketch's to state (ModelToSketchTransform), not ours to assume
    (build_dt_cone_gear_shaft._sketch_x_per_model_x)."""
    sketch = _early_bound(adapter.currentModel.SketchManager.ActiveSketch, "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    mapped = []
    for y in (0.0, 0.001):
        point = _early_bound(
            utility.CreatePoint(double_array([0.0, y, 0.0])), "IMathPoint"
        )
        moved = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
        mapped.append(tuple(float(value) for value in moved.ArrayData))
    dx, dy, dz = (b - a for a, b in zip(*mapped))
    if abs(abs(dz) - 0.001) > 1e-9 or abs(dx) > 1e-9 or abs(dy) > 1e-9:
        raise RuntimeError(f"{TIP_FACE} sketch normal is not along model Y: {mapped}")
    return math.copysign(1.0, dz)


async def _cut_end_hole(adapter) -> None:
    """Cut-extrude the reamed hole from the threaded end face toward the head:
    an on-axis EndHoleDia circle on TipFace, cut EndHoleDepth blind."""
    from solidworks_mcp.adapters.base import ExtrusionParameters

    hole = SketchDims()
    check(f"create_sketch {HOLE_FEATURE}", await adapter.create_sketch(TIP_FACE))
    await define_circle(
        adapter,
        0.0,
        0.0,
        HOLE_R,
        "pivot hole",
        dims=hole,
        names=(None, None, "EndHoleDia"),
        drives=(None, None, '"EndHoleDia"'),
    )
    # The material lies toward the head, model +Y.  An extruded cut runs
    # against its sketch's normal unless reversed (the shaft's Socket, cut
    # unreversed from an end plane facing out of its land); the volume check
    # below proves the side either way.
    reverse = _sketch_normal_along_model_y(adapter) > 0.0
    await ensure_fully_defined(adapter, f"{HOLE_FEATURE} sketch")
    check(f"exit_sketch {HOLE_FEATURE}", await adapter.exit_sketch())
    name_last_feature(adapter, HOLE_FEATURE)
    drives = hole.apply(adapter, HOLE_FEATURE)
    check(
        "cut pivot hole",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=END_HOLE_DEPTH, reverse_direction=reverse)
        ),
    )
    name_last_feature(adapter, HOLE_CUT)
    depth = name_dimensions(adapter, HOLE_CUT, ["EndHoleDepth"])
    drives += [(depth[0], '"EndHoleDepth"')]
    await force_rebuild(adapter)
    for dimension, expression in drives:
        await drive_dimension(adapter, dimension, expression)


async def _tip_face(adapter) -> None:
    """The threaded end face as a named mate datum."""
    from solidworks_mcp.adapters.base import CreatePlaneParameters

    check(
        f"create_plane {TIP_FACE} (Top Plane - SHANK_LEN)",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="offset", base_plane="Top Plane", offset=-SHANK_LEN
            )
        ),
    )
    name_last_feature(adapter, TIP_FACE)
    blank_reference_geometry(adapter, ((TIP_FACE, "PLANE"),))


def _manufacturing_controls(adapter) -> None:
    """The reamed band on the model dimension, places and drawing marks."""
    set_dimension_bilateral_tolerance(
        adapter,
        HOLE_FEATURE,
        "EndHoleDia",
        *deviations(END_HOLE_BAND),
        display_unit=UNIT,
    )
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    # The registry row's title-block fields and the isometric label.
    apply_drawing_properties(
        adapter, PART_NAME, {"Isometric View Note": ISOMETRIC_VIEW_NOTE}
    )


@wraps(build_91794A558)
async def _drill_and_ream(adapter, truth=None, **parameters):
    # The shared recipe builds the supplied screw; the hole is this part's.
    receipt = await build_91794A558(adapter, truth, **parameters)
    for name, value in (("EndHoleDia", END_HOLE_DIA), ("EndHoleDepth", END_HOLE_DEPTH)):
        await set_global(adapter, name, f"{value}mm")
    # TipFace, the assembly's mate datum, is also the hole's sketch plane.
    await _tip_face(adapter)
    stock = await _volume_mm3(adapter)
    await _cut_end_hole(adapter)
    await force_rebuild(adapter)
    removed = stock - await _volume_mm3(adapter)
    if abs(removed - V_HOLE) > HOLE_VOLUME_TOL_MM3:
        raise RuntimeError(
            f"pivot hole removed {removed:.4f} mm^3, analytic {V_HOLE:.4f} "
            f"(+/- {HOLE_VOLUME_TOL_MM3:.4f})"
        )
    _telemetry.success(
        f"pivot hole: removed {removed:.4f} mm^3 (analytic {V_HOLE:.4f})"
    )
    _manufacturing_controls(adapter)
    return receipt


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(
            StockComponent(sku=SKU, author=_drill_and_ream, transform=RigidTransform()),
        ),
        material=MATERIAL,
        save_threaded_part=save_simplified_part,
        screw_axis_planes=("Front Plane", "Right Plane"),
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
