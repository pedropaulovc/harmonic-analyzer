r"""Create the curated machinist drawing for the pen hanger.

The SLDPRT remains authoritative.  This recipe supplies only the hanger's views,
strap/block envelope dimensions, the hanger-screw callout, and manufacturing
notes; every shared sheet/template, import, curation, and export behavior lives
in ``_drawing_common``.

The pen hanger is a black tapered steel strap (3 thick, 10 -> 16 wide) rising
from a 12 x 12 guide block; the block carries a 5.4 square vertical channel the
pen rod slides in, and a #8-32 tapped hanger-screw hole passes through the strap
top from behind.  The part is tall and narrow (~82 x 22), so the front profile is
the sole ortho view at 2:1 with an isometric to its right.

The two lower width dimensions occupy centred lanes below the guide block.
Their rendered rows and native strokes, the other imported dimensions, the tap
callout, and the complete linked notes are checked again after the final rebuild.

Run with SolidWorks open::

    uv run python cad\scripts\draw_pn_pen_hanger.py pen-hanger
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_annotation_extent import (
    CLEAR_GAP_M,
    PLACE_SETTLE_M,
    annotation_ink,
    assert_annotation_reservations,
    place_annotation_in_field,
    require_clear,
    sheet_region,
)
from _drawing_common import (
    DrawingOutputs,
    add_native_hole_callout,
    add_property_linked_note,
    curate_view_dimensions,
    dimension_name,
    finalize_drawing,
    import_cosmetic_threads,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    set_hidden_lines_removed,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME
from _holes import TAP_DRILL_MM
from build_pn_pen_hanger import (
    BLOCK_HALF,
    SCREW_HOLE_XY,
    SCREW_TAP_SPEC,
    STRAP_BOT_X,
    STRAP_TOP_X,
    STRAP_TOP_Y,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["pn_pen_hanger"]
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

SHEET_SCALE = (2.0, 1.0)  # 2:1 whole sheet (~82 mm tall part)
VIEW_SCALE = SHEET_SCALE[0] / SHEET_SCALE[1]  # 2.0 sheet-mm per model-mm / 1000

# Front-view model bounding box (X-Y profile of the strap + block).
_BBOX_X = (
    min(STRAP_TOP_X[0], STRAP_BOT_X[0], -BLOCK_HALF),
    max(STRAP_TOP_X[1], STRAP_BOT_X[1], BLOCK_HALF),
)
_BBOX_Y = (-BLOCK_HALF, STRAP_TOP_Y)
_BBOX_CX = (_BBOX_X[0] + _BBOX_X[1]) / 2.0
_BBOX_CY = (_BBOX_Y[0] + _BBOX_Y[1]) / 2.0

# Sheet layout (meters).  Tall front view hugs the left; the isometric sits to
# the right; the notes fill the clear mid band between them (never crossing the
# thin front view).
FRONT_CENTER = (0.075, 0.150)
ISO_CENTER = (0.320, 0.170)
TOP_CENTER = (0.205, 0.225)


def _fx(model_x_mm: float) -> float:
    return FRONT_CENTER[0] + (model_x_mm - _BBOX_CX) * VIEW_SCALE / 1000.0


def _fy(model_y_mm: float) -> float:
    return FRONT_CENTER[1] + (model_y_mm - _BBOX_CY) * VIEW_SCALE / 1000.0


# Per-view survivors of the marked-dimension import (all Front-plane sketch dims).
# Centre the two lower widths on their actual model features, not the asymmetric
# profile's outline centre. The shorter strap width uses the inner lower lane.
FRONT_KEEP = {
    "StrapTopRun": (FRONT_CENTER[0], _fy(STRAP_TOP_Y) + 0.012),
    "StrapTaperDy": (_fx(_BBOX_X[0]) - 0.018, FRONT_CENTER[1]),
    "StrapBotWidth": (
        _fx((STRAP_BOT_X[0] + STRAP_BOT_X[1]) / 2.0),
        _fy(-BLOCK_HALF) - 0.012,
    ),
    "BlockWidth": (_fx(0.0), _fy(-BLOCK_HALF) - 0.026),
}

# These fields reserve whole text rows; the dimension/witness lines are read
# separately, so no ordinary dimension is treated as a mirrored callout shoulder.
FRONT_TEXT_FIELDS = {
    "StrapBotWidth": (
        _fx(0.0) - 0.012,
        _fy(-BLOCK_HALF) - 0.018,
        _fx(0.0) + 0.012,
        _fy(-BLOCK_HALF) - 0.007,
    ),
    "BlockWidth": (
        _fx(0.0) - 0.012,
        _fy(-BLOCK_HALF) - 0.032,
        _fx(0.0) + 0.012,
        _fy(-BLOCK_HALF) - 0.021,
    ),
}


def _assert_settled_layout(
    adapter: Any, annotations: dict[str, Any], note_rows: dict[str, int]
) -> None:
    """Check the complete annotation map, including frame/title stroke clearance."""
    region = sheet_region(adapter)
    drawable = (region.xmin, region.ymin, region.xmax, region.ymax)
    fields = {label: drawable for label in annotations}
    fields.update(FRONT_TEXT_FIELDS)
    inks = assert_annotation_reservations(
        adapter,
        annotations,
        fields,
        check_own_lines=tuple(FRONT_TEXT_FIELDS),
    )
    template = DRAWING_TEMPLATES[SPEC.layout]
    obstacles = {
        "frame left": (0.0, 0.0, region.xmin, template.height_m),
        "frame right": (region.xmax, 0.0, template.width_m, template.height_m),
        "frame bottom": (0.0, 0.0, template.width_m, region.ymin),
        "frame top": (0.0, region.ymax, template.width_m, template.height_m),
        "title block": (
            template.title_block_left_m,
            0.0,
            template.width_m,
            template.title_block_top_m,
        ),
    }
    for label, ink in inks.items():
        if label in note_rows and ink.row_count != note_rows[label]:
            raise RuntimeError(f"{label} did not retain its complete native note rows")
        for row in ink.rows:
            require_clear(label, row, obstacles)
        for index, line in enumerate(ink.lines):
            box = line.box()
            require_clear(
                f"{label} native line {index}",
                (box.xmin, box.ymin, box.xmax, box.ymax),
                obstacles,
            )


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open pen-hanger source", await adapter.open_model(str(SOURCE)))
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
            "Front View Note",
            "Top View Note",
            "Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Front View Note",
            "Top View Note",
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
            0: "Pen Hanger Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "pen hanger; tapered strap; pen-rod guide block",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(2, 1))
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(2, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 1))
    for view in (front, top, iso):
        set_hidden_lines_removed(adapter, view)

    front_dimensions = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    annotations = {
        dimension_name(adapter, annotation): annotation for annotation in front_dimensions
    }
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to the hanger-screw hole")

    # Pick the tap-drill rim, not the cosmetic thread or the hole centre.
    # Keep its native size/class/THRU callout above the manufacturing notes.
    tap_callout = add_native_hole_callout(
        adapter,
        front,
        edge_xy=(
            _fx(SCREW_HOLE_XY[0] + TAP_DRILL_MM[SCREW_TAP_SPEC.size] / 2.0),
            _fy(SCREW_HOLE_XY[1]),
        ),
        callout_xy=(0.145, 0.215),
        label="hanger-screw through tap",
        process="TAP",
    )

    # GetAnnotation is a no-argument method returning nullable VT_DISPATCH on
    # both IDisplayDimension and INote (sldworks_2026.py); bind each native owner.
    tap_annotation = _early_bound(tap_callout, "IDisplayDimension").GetAnnotation()
    if tap_annotation is None:
        raise RuntimeError("hanger-screw through tap has no native annotation")
    annotations["hanger-screw through tap"] = _early_bound(tap_annotation, "IAnnotation")
    notes = {}
    for property_name, xy in (
        ("Manufacturing Notes", (0.115, 0.175)),
        ("Front View Note", (0.030, 0.036)),
        ("Top View Note", (0.170, 0.195)),
        ("Isometric View Note", (0.286, 0.104)),
    ):
        note = _early_bound(add_property_linked_note(adapter, property_name, *xy), "INote")
        annotation = note.GetAnnotation()
        if annotation is None:
            raise RuntimeError(f"{property_name} has no native annotation")
        notes[property_name] = _early_bound(annotation, "IAnnotation")
    annotations.update(notes)

    # Materialize the iso's cosmetic thread before the strict final note cleanup;
    # otherwise its descriptive label first appears during the native drawing save.
    import_cosmetic_threads(adapter, iso)
    rebuild_drawing(adapter, label="pen-hanger annotation reservations")
    note_rows = {
        label: annotation_ink(adapter, annotation, label=label).row_count
        for label, annotation in notes.items()
    }
    for label, field in FRONT_TEXT_FIELDS.items():
        place_annotation_in_field(
            adapter,
            annotations[label],
            label=label,
            field=field,
            margin=CLEAR_GAP_M + PLACE_SETTLE_M,
        )

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        spec=SPEC,
        pdf_title="Pen Hanger Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        settled_checks=(
            lambda: _assert_settled_layout(adapter, annotations, note_rows),
        ),
        redundant_note_substrings=("#8-32 Tapped Hole",),
        expected_redundant_notes=1,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
