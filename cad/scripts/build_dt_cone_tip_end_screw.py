r"""Build MHA-DT-39, the cone tip end screw: McMaster 91794A558 plus one hole.

The shared catalog recipe (``diag_build_91794A558``) builds the supplied
1/4-28 x 5/8 slotted fillister screw in its stock frame; this builder then
adds the one shop operation, the pivot hole drilled and reamed concentric in
the threaded end (``dt_cone_tip_end_screw_spec``; the MHA-DT-VN-61 post
mount screw's pattern of a part-owned modification after the stock recipe).

The hole is a revolve-cut whose Right-plane profile carries both model-owned
sizes: its diameter (the reamed band, on the model dimension) and its full-
diameter depth from the end face (.XX).  The longitudinal section on the
Right plane (the end view cut through the axis) prints both, the slot cut
along its length.  An analytic volume check proves the cut.

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
from _dimensions import drive_dimension, set_global
from _drawing_dimension_insert import add_diametric_linear_dimension
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
from _sketch import (
    SketchDims,
    anchor_point_to_origin,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _stock_fastener import RigidTransform, StockComponent, build_stock_fastener
from _visibility import blank_reference_geometry
from diagnostics.diag_build_91794A558 import build_91794A558
from dt_cone_tip_end_screw_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    END_HOLE_BAND,
    END_HOLE_DEPTH,
    END_HOLE_DIA,
    HOLE_FEATURE,
    ISOMETRIC_VIEW_NOTE,
    SHANK_LEN,
    SKU,
    TIP_FACE,
    UNIT,
)

PART_NAME = "dt-cone-tip-end-screw"

SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material
if SPEC.skus != (SKU,):
    raise AssertionError(f"{PART_NAME} catalogues {SPEC.skus}, not {SKU}")

HOLE_R = END_HOLE_DIA / 2.0
V_HOLE = math.pi * HOLE_R**2 * END_HOLE_DEPTH
# The revolve is exact; SolidWorks' mass properties read to its tessellation.
HOLE_VOLUME_TOL_MM3 = 0.005 * V_HOLE
HOLE_CUT = "EndHole"


async def _volume_mm3(adapter) -> float:
    mass = await adapter.get_mass_properties()
    if not mass.is_success:
        raise RuntimeError(f"get_mass_properties failed: {mass.error}")
    return float(mass.data.volume)


async def _cut_end_hole(adapter) -> None:
    """Revolve-cut the reamed hole: mouth on the end face, out to the wall,
    up the wall to the floor, in to the axis, closed down the axis."""
    from solidworks_mcp.adapters.base import RevolveParameters

    mouth_y, floor_y = -SHANK_LEN, -SHANK_LEN + END_HOLE_DEPTH
    hole = SketchDims()
    check(f"create_sketch {HOLE_FEATURE}", await adapter.create_sketch("Right"))
    set_sketch_direct_db(adapter, True)
    axis = check("hole axis", await adapter.add_centerline(0.0, mouth_y, 0.0, floor_y))
    mouth = check("hole mouth", await adapter.add_line(0.0, mouth_y, HOLE_R, mouth_y))
    wall = check("hole wall", await adapter.add_line(HOLE_R, mouth_y, HOLE_R, floor_y))
    floor = check("hole floor", await adapter.add_line(HOLE_R, floor_y, 0.0, floor_y))
    close = check("hole closure", await adapter.add_line(0.0, floor_y, 0.0, mouth_y))
    set_sketch_direct_db(adapter, False)
    for label, first, second in (
        ("mouth-wall", f"{mouth}.end", f"{wall}.start"),
        ("wall-floor", f"{wall}.end", f"{floor}.start"),
        ("floor-close", f"{floor}.end", f"{close}.start"),
        ("close-mouth", f"{close}.end", f"{mouth}.start"),
        ("axis start", f"{axis}.start", f"{mouth}.start"),
        ("axis end", f"{axis}.end", f"{floor}.end"),
    ):
        check(label, await adapter.add_sketch_constraint(first, second, "coincident"))
    for label, entity, relation in (
        ("hole mouth", mouth, "horizontal"),
        ("hole floor", floor, "horizontal"),
        ("hole wall", wall, "vertical"),
        ("hole closure", close, "vertical"),
        ("hole axis", axis, "vertical"),
    ):
        check(label, await adapter.add_sketch_constraint(entity, None, relation))
    # Dimensions in creation order: the end-face station (the stock's, not
    # printed), the reamed diameter, the full-diameter depth.
    await anchor_point_to_origin(
        adapter, f"{mouth}.start", 0.0, mouth_y, "hole mouth on the end face"
    )
    hole.record("TipStation")
    await add_diametric_linear_dimension(
        adapter,
        axis,
        wall,
        (HOLE_R + 2.0, mouth_y + END_HOLE_DEPTH / 2.0),
        "EndHoleDia",
    )
    hole.record("EndHoleDia", '"EndHoleDia"')
    check(
        "hole depth",
        await adapter.add_sketch_dimension(wall, None, "linear", END_HOLE_DEPTH),
    )
    hole.record("EndHoleDepth", '"EndHoleDepth"')
    await ensure_fully_defined(adapter, f"{HOLE_FEATURE} sketch")
    check(f"exit_sketch {HOLE_FEATURE}", await adapter.exit_sketch())
    name_last_feature(adapter, HOLE_FEATURE)
    drives = hole.apply(adapter, HOLE_FEATURE)
    check(
        "revolve-cut pivot hole",
        await adapter.create_revolve(RevolveParameters(angle=360.0, is_cut=True)),
    )
    name_last_feature(adapter, HOLE_CUT)
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
    await _tip_face(adapter)
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
