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
"""

from __future__ import annotations

from functools import wraps
import sys

from _common import (
    _early_bound,
    anchor_point_to_origin,
    check,
    dimension_between,
    ensure_fully_defined,
    name_dimensions,
    name_last_feature,
    run_build,
    set_sketch_direct_db,
)
from _drawing_marks import (
    apply_drawing_precision,
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _fastener_catalog import fastener
from _stock_fastener import RigidTransform, StockComponent, build_stock_fastener
from diagnostics.diag_build_40923898 import build_40923898
from diagnostics.diag_mcmaster_fillister import FILLISTER_SIZES
from post_mount_screw_spec import (
    CUT_LENGTH_DIMENSION,
    CUT_LENGTH_MM,
    CUT_LENGTH_SKETCH,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    MANUFACTURING_NOTES,
)

PART_NAME = "post-mount-screw"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material

THREAD = "1/4-20"
SHANK_DIA, SHANK_LEN, HEAD_H, HEAD_DIA, THREAD_PITCH = FILLISTER_SIZES["40923898"]
if SHANK_LEN != CUT_LENGTH_MM:
    raise ValueError("the stock recipe length is not the spec's cut length")


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


async def _author_cut_length(adapter) -> None:
    """One construction line on the Front plane along the shank's left
    silhouette, from the under-head face to the cut end: the print dimensions
    the length between faces the shop measures, not along the axis through
    the part.  build_cone_tip_shim's reference-sketch pattern.
    """
    x = -SHANK_DIA / 2.0
    top, bottom = (x, 0.0), (x, -CUT_LENGTH_MM)
    check(
        f"create_sketch {CUT_LENGTH_SKETCH}", await adapter.create_sketch("Front")
    )
    set_sketch_direct_db(adapter, True)
    line = check(
        f"{CUT_LENGTH_SKETCH} line", await adapter.add_line(*top, *bottom)
    )
    set_sketch_direct_db(adapter, False)
    _as_construction(adapter, line)
    check(
        f"{CUT_LENGTH_SKETCH} vertical",
        await adapter.add_sketch_constraint(line, None, "vertical"),
    )
    # Created first, so name_dimensions' creation order finds it first.
    await dimension_between(
        adapter,
        f"{line}.start",
        f"{line}.end",
        "vertical_distance",
        CUT_LENGTH_MM,
        CUT_LENGTH_SKETCH,
    )
    await anchor_point_to_origin(adapter, f"{line}.start", *top, CUT_LENGTH_SKETCH)
    await ensure_fully_defined(adapter, f"{CUT_LENGTH_SKETCH} sketch")
    check(f"exit_sketch {CUT_LENGTH_SKETCH}", await adapter.exit_sketch())
    name_last_feature(adapter, CUT_LENGTH_SKETCH)
    name_dimensions(adapter, CUT_LENGTH_SKETCH, [CUT_LENGTH_DIMENSION])


def _manufacturing_controls(adapter) -> None:
    """Places and drawing mark on the cut length; the sheet's note."""
    cut_end = _cut_end_y_mm(adapter)
    if abs(cut_end + CUT_LENGTH_MM) > 1e-4:
        raise RuntimeError(
            f"solid cut end at y={cut_end:.4f} is not the dimensioned "
            f"{CUT_LENGTH_MM} below the under-head face"
        )
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    # The stock helper's reference pass hides the sketch with the recipe's.
    apply_drawing_properties(
        adapter, PART_NAME, {"Manufacturing Notes": MANUFACTURING_NOTES}
    )


@wraps(build_40923898)
async def _cut_to_length(adapter, truth=None, **parameters):
    receipt = await build_40923898(adapter, truth, **parameters)
    await _author_cut_length(adapter)
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
