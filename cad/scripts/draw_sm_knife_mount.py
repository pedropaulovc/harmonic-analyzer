r"""Create the curated machinist drawing for the knife-mount bearing block.

A machined, heat-treated steel block (24 wide x ~29.4 tall x 14 deep) with a
single Ø12 bore.  The bore is the knife-edge bearing: the summing-lever
trunnion's top vertex rides its upper inner wall in line contact (ch18 p.42:
unpainted hardened steel, close bore -- 2026-09-02 user re-read).  Every face
and the bore are real edges, so
the block dimensions ride the auto-imported profile marks (block + bore) with the
depth added across the right-view section.
Final native ink reservations keep the bore callout clear of the height line
and retain the fleet's standard surface-finish symbol size.

Run with SolidWorks open::

    uv run python cad\scripts\draw_sm_knife_mount.py knife-mount
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from sm_knife_mount_spec import GEOMETRIC_TOLERANCES_MM

import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_annotation_extent import (
    assert_annotation_reservations,
    place_annotation_in_field,
    require_clear,
)
from _drawing_common import (
    DrawingOutputs,
    add_datum_feature,
    add_edge_dimension,
    add_feature_control_frame,
    add_property_linked_note,
    add_surface_finish,
    curate_view_dimensions,
    dimension_name,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME, DRAWING_TEMPLATES
from _surface_finish import surface_finish_by_key
from sm_knife_mount_spec import (
    BLK_BOT,
    BLK_TOP,
    BORE_CY,
    R_BORE,
    SUPPORT_Z_THICK,
    SURFACE_FINISHES,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["sm_knife_mount"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"],
    pdf=SPEC.outputs["pdf"],
    png=SPEC.outputs["png"],
)
SLDDRW = OUTPUTS.slddrw
PDF = OUTPUTS.pdf
PNG = OUTPUTS.png

SHEET_SCALE = (2.0, 1.0)
_BLOCK_CY = (BLK_TOP + BLK_BOT) / 2.0  # block centre height (model mm)

FRONT_CENTER = (0.115, 0.140)
RIGHT_CENTER = (0.220, 0.140)
TOP_CENTER = (0.115, 0.235)
ISO_CENTER = (0.345, 0.210)


def _front_y(model_y_mm: float) -> float:
    return FRONT_CENTER[1] + (model_y_mm - _BLOCK_CY) * SHEET_SCALE[0] / 1000.0


FRONT_KEEP = {
    "BlockWidth": (FRONT_CENTER[0], _front_y(BLK_BOT) - 0.016),
    "BlockHeight": (FRONT_CENTER[0] - 0.075, FRONT_CENTER[1]),
    "BoreDia": (FRONT_CENTER[0] - 0.048, _front_y(BORE_CY) + 0.026),
}
RIGHT_KEEP: dict[str, tuple[float, float]] = {}
DIMENSION_CALLOUTS = {
    "BoreDia": "THRU",
}

RIGHT_HALF_Z = SUPPORT_Z_THICK / 2.0 * SHEET_SCALE[0] / 1000.0
RIGHT_HALF_Y = (BLK_TOP - BLK_BOT) / 2.0 * SHEET_SCALE[0] / 1000.0

# Keep the native bore size/THRU untouched; move its crossing height line to a
# separate left lane. Finish content and its edge association also stay native.
ANNOTATION_FIELDS = {
    "BlockHeight": (0.025, 0.128, 0.051, 0.150),
    "BoreDia": (0.053, 0.148, 0.079, 0.164),
    "knife bore finish": (0.160, 0.104, 0.190, 0.125),
}


def _assert_release_readability(
    adapter: Any, annotations: dict[str, Any], views: tuple[Any, ...]
) -> None:
    """Prove the settled bore text, height line and finish remain separate."""
    inks = assert_annotation_reservations(
        adapter,
        annotations,
        ANNOTATION_FIELDS,
        text_heights={"knife bore finish": 0.0025},
        check_own_lines=("BlockHeight",),
    )
    template = DRAWING_TEMPLATES[SPEC.layout]
    title = {
        "title-block": (
            template.title_block_left_m, 0.0,
            template.width_m, template.title_block_top_m,
        )
    }
    view_boxes = {
        f"view {index}": tuple(float(value) for value in _early_bound(view, "IView").GetOutline())
        for index, view in enumerate(views)
    }
    for label in ANNOTATION_FIELDS:
        ink = inks[label]
        require_clear(label, ink.text, {**title, **view_boxes})
        for line in ink.lines:
            box = line.box()
            require_clear(label, (box.xmin, box.ymin, box.xmax, box.ymax), title)



async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open knife-mount source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Isometric View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Knife-Mount Bearing Block Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "knife mount; hardened steel bearing block; knife-edge bore",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(2, 1))
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(2, 1))
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(2, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 1))
    # The bore only reads in the front view; show it dashed in the projected
    # right/top views so the orthographic set carries the thru-hole the
    # isometric implies (blind-review finding: HLR left them empty rectangles).
    set_hidden_lines_removed(adapter, iso)
    for view in (front, right, top):
        set_hidden_lines_visible(adapter, view)

    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    curate_view_dimensions(adapter, right, keep=RIGHT_KEEP, view_label="right")
    set_dimension_callouts(adapter, front_annotations, DIMENSION_CALLOUTS)
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to knife bore")

    # Block depth (14): dimension the right view's flat front/back faces.
    block_depth = add_edge_dimension(
        adapter,
        right,
        p0=(RIGHT_CENTER[0] - RIGHT_HALF_Z, RIGHT_CENTER[1]),
        p1=(RIGHT_CENTER[0] + RIGHT_HALF_Z, RIGHT_CENTER[1]),
        text_xy=(RIGHT_CENTER[0], RIGHT_CENTER[1] - RIGHT_HALF_Y - 0.014),
        label="block-depth overall",
    )

    # Datum A = the block top seat (hangs 0.25 under the top-frame casting
    # underside; carries the 1/2-13 knife-hanger-stud tap); Ra 0.8 on the
    # bore's working upper wall, tagged on the bore rim (a real circular edge).
    top_datum = add_datum_feature(
        adapter,
        front,
        edge_xy=(FRONT_CENTER[0], _front_y(BLK_TOP)),
        symbol_xy=(FRONT_CENTER[0], _front_y(BLK_TOP) + 0.018),
        datum="A",
        label="block top seat",
    )
    bore_position = add_feature_control_frame(
        adapter,
        front,
        edge_xy=(FRONT_CENTER[0], _front_y(BORE_CY) + R_BORE * SHEET_SCALE[0] / 1000.0),
        frame_xy=(FRONT_CENTER[0] + 0.032, _front_y(BORE_CY) + 0.040),
        characteristic="position",
        tolerance=GEOMETRIC_TOLERANCES_MM["knife-bore position"],
        datums=("A",),
        diameter=True,
        label="knife-bore position",
    )
    bore_finish = add_surface_finish(
        adapter,
        front,
        edge_xy=(FRONT_CENTER[0] + R_BORE * SHEET_SCALE[0] / 1000.0, _front_y(BORE_CY)),
        symbol_xy=(FRONT_CENTER[0] + 0.052, _front_y(BORE_CY) - 0.020),
        control=surface_finish_by_key(SURFACE_FINISHES, "knife_bore"),
        label="knife bore finish",
        char_height=0.0025,
    )

    manufacturing_note = add_property_linked_note(
        adapter, "Manufacturing Notes", 0.020, 0.070
    )
    iso_note = add_property_linked_note(
        adapter, "Isometric View Note", 0.330, 0.175
    )
    annotations = {
        dimension_name(adapter, annotation): annotation
        for annotation in front_annotations
    }
    annotations.update({
        "block-depth overall": _early_bound(block_depth, "IDisplayDimension").GetAnnotation(),
        "datum A": _early_bound(top_datum, "IDatumTag").GetAnnotation(),
        "knife-bore position": _early_bound(bore_position, "IGtol").GetAnnotation(),
        "knife bore finish": _early_bound(bore_finish, "ISFSymbol").GetAnnotation(),
        "Manufacturing Notes": _early_bound(manufacturing_note, "INote").GetAnnotation(),
        "Isometric View Note": _early_bound(iso_note, "INote").GetAnnotation(),
    })
    for label, field in ANNOTATION_FIELDS.items():
        place_annotation_in_field(adapter, annotations[label], label=label, field=field)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        spec=SPEC,
        pdf_title="Knife-Mount Bearing Block Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        settled_checks=(
            lambda: _assert_release_readability(adapter, annotations, (front, right, top, iso)),
        ),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
