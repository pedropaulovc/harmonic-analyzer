r"""Create the curated manufacturing drawing for the feed-pinion sleeve (MHA-110).

An end view, a longitudinal section A-A and an isometric at 3:1.  The end view
carries the bore's fit note and finish; the section carries every turned
diameter beside its axial extent and the three lengths baselined from the
rear face (rule 7), all imported natively from the part with the places and
bands the part authored (``transgear_feed_pinion_spec``).  The oil hole is
match-drilled through the pressed hub, so the section carries only its
match-drill note; its size and station belong to the hub's sheet.
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_leader_note,
    add_property_linked_note,
    add_surface_finish,
    assert_imported_precision,
    check_drawing_layout,
    create_section_view,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    set_dimension_callouts,
    set_hidden_lines_removed,
    stamp_drawing_summary,
    view_name,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _gear_drawing_entities import visible_circle_edge
from _surface_finish import surface_finish_by_key
from transgear_feed_pinion_spec import (
    BORE_DIA,
    BORE_FIT_CALLOUT,
    BORE_PROCESS_CALLOUT,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    FACE_WIDTH,
    OIL_HOLE_DIA,
    OIL_HOLE_NOTE,
    OIL_HOLE_Z,
    OUTSIDE_DIA,
    OVERALL_LENGTH,
    SHANK_DIA,
    SPIGOT_FRONT_STATION,
    SURFACE_FINISHES,
)
from solidworks_mcp.adapters.solidworks.drawing import auto_center_marks, place_view


SPEC = DRAWINGS_BY_NAME["transgear_feed_pinion"]
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

SHEET_SCALE = (3.0, 1.0)
VIEW_SCALE = (3, 1)
FRONT_CENTER = (0.100, 0.150)
RIGHT_CENTER = (0.245, 0.150)
ISO_CENTER = (0.370, 0.150)
SHEET_INNER_BORDER = (0.0127, 0.0127, 0.4191, 0.2667)

# Half the printed tooth-tip circle in sheet metres: the section's half-height,
# which every dimension is placed clear of.
HALF_OD = OUTSIDE_DIA * VIEW_SCALE[0] / 2000.0


def _side_x(z_mm: float) -> float:
    """Sheet x of a model-z station in the longitudinal section.

    The section lays model +Z to the RIGHT (the crank pinion's read-back): the
    rear face (z = 0) is the left edge and the nose the right edge.
    """
    return RIGHT_CENTER[0] + (z_mm - OVERALL_LENGTH / 2.0) * VIEW_SCALE[0] / 1000.0


# The end view is pictorial and carries its center mark, the bore fit note and
# the bore finish.  On the section, the tip, root and shank diameters print
# inline on the axis, between their own extension lines and off the part (the
# crank hub's and the disc hub's layout): the tip and root left of the rear
# face, where their witnesses start, the larger farther out so neither
# extension line crosses the other's dimension line; the shank right of the
# nose.  The spigot keeps its shelf above its own span, and the bore its shelf
# above-left of the rear face, which holds its two-row band and process
# callout clear of its own extension lines.  Run 20261001T110844152Z put the
# tip, spigot and shank on one shelf, where their bands printed over each
# other (machinist review blocker).  The three lengths stay baseline-stacked
# below from the rear face, shortest innermost.
FRONT_KEEP: dict[str, tuple[float, float]] = {}
_SIDE_TOP = RIGHT_CENTER[1] + HALF_OD
_SIDE_BOTTOM = RIGHT_CENTER[1] - HALF_OD
_REAR_X = _side_x(0.0)
_NOSE_X = _side_x(OVERALL_LENGTH)
RIGHT_KEEP: dict[str, tuple[float, float]] = {
    "RootDia": (_REAR_X - 0.030, RIGHT_CENTER[1]),
    "OutsideDia": (_REAR_X - 0.066, RIGHT_CENTER[1]),
    "ShankDia": (_NOSE_X + 0.022, RIGHT_CENTER[1]),
    "BoreDia": (_REAR_X - 0.010, _SIDE_TOP + 0.040),
    "SpigotDia": (
        (_side_x(FACE_WIDTH) + _side_x(SPIGOT_FRONT_STATION)) / 2.0,
        _SIDE_TOP + 0.012,
    ),
    "FaceWidth": ((_REAR_X + _side_x(FACE_WIDTH)) / 2.0, _SIDE_BOTTOM - 0.012),
    "SpigotFront": (
        (_REAR_X + _side_x(SPIGOT_FRONT_STATION)) / 2.0,
        _SIDE_BOTTOM - 0.024,
    ),
    "OverallLength": (RIGHT_CENTER[0], _SIDE_BOTTOM - 0.036),
}
DIMENSION_CALLOUTS = {
    # The native value/limits define the bore; the callout adds the process.
    "BoreDia": BORE_PROCESS_CALLOUT,
}

# The oil hole lies in the section plane (+Y), so the cut shows it as a gap in
# the upper shank wall; the note's leader lands mid-wall on its front edge.
# The note stands far enough right that its leader passes right of the
# spigot's shelf text whichever side of its dimension line that prints, and
# left of where the shank's extension lines start.
OIL_HOLE_EDGE = (
    _side_x(OIL_HOLE_Z + OIL_HOLE_DIA / 2.0),
    RIGHT_CENTER[1] + (BORE_DIA + SHANK_DIA) / 4.0 * VIEW_SCALE[0] / 1000.0,
)
OIL_HOLE_CALLOUT = (_NOSE_X + 0.030, _SIDE_TOP + 0.050)
NOTE_HEIGHT = 0.0025

_BORE_SHEET_RADIUS = BORE_DIA * VIEW_SCALE[0] / 2000.0
BORE_FIT_NOTE = (0.016, 0.215)
BORE_FIT_ATTACH = (
    FRONT_CENTER[0] + _BORE_SHEET_RADIUS * math.cos(math.radians(135.0)),
    FRONT_CENTER[1] + _BORE_SHEET_RADIUS * math.sin(math.radians(135.0)),
)
# The section's native caption sits below the stacked lengths.
SECTION_CAPTION = (RIGHT_CENTER[0], _SIDE_BOTTOM - 0.050)
# The finish stands lower LEFT of the end view: the section line's arrows and
# their "A" labels point right, toward the section, and a lower-right leader
# ran through the lower label (run 20261001T035353825Z layout audit).  It
# stands farther out and nearer level with the bore, so its leader climbs
# shallowly and passes right of the symbol's own "Ra" text rather than through
# it (run 20261001T110844152Z layout audit).
FINISH_ATTACH = (
    FRONT_CENTER[0] + _BORE_SHEET_RADIUS * math.cos(math.radians(-135.0)),
    FRONT_CENTER[1] + _BORE_SHEET_RADIUS * math.sin(math.radians(-135.0)),
)
FINISH_SYMBOL = (FRONT_CENTER[0] - HALF_OD - 0.022, FRONT_CENTER[1] - 0.012)


@_telemetry.traced("drawing.planar_centerline", label_param="label")
def _create_section_axis_centerline(adapter: Any, view: Any, *, label: str) -> Any:
    """Create the turning axis in the longitudinal-section sketch."""
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    name = view_name(adapter, view)
    if not drawing.ActivateView(name):
        raise RuntimeError(f"failed to activate section view {name!r} ({label})")
    sketch_manager = _early_bound(draw.SketchManager, "ISketchManager")
    previous_add_to_db = bool(sketch_manager.AddToDB)
    previous_display = bool(sketch_manager.DisplayWhenAdded)
    sketch_manager.AddToDB = True
    sketch_manager.DisplayWhenAdded = True
    half_length = OVERALL_LENGTH / 2000.0
    try:
        centerline = sketch_manager.CreateCenterLine(
            -half_length - 0.001, 0.0, 0.0, half_length + 0.001, 0.0, 0.0
        )
    finally:
        sketch_manager.AddToDB = previous_add_to_db
        sketch_manager.DisplayWhenAdded = previous_display
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    if centerline is None:
        raise RuntimeError(f"failed to create section-axis centerline ({label})")
    return centerline


def _position_section_caption(
    adapter: Any, view: Any, target: tuple[float, float]
) -> None:
    """Move the native linked section caption clear of the length dimensions."""
    bound_view = _early_bound(view, "IView")
    candidates = []
    for raw_note in bound_view.GetNotes() or ():
        note = _early_bound(raw_note, "INote")
        linked_text = str(note.PropertyLinkedText or "")
        if all(
            token in linked_text for token in ("<VLNAME>", "<VLLABEL>", "<VLSCALEV>")
        ):
            candidates.append((note, linked_text))
    if len(candidates) != 1:
        raise RuntimeError(
            f"expected one native linked section caption, found {len(candidates)}"
        )
    note, linked_text = candidates[0]
    annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
    if not annotation.SetPosition2(*target, 0.0):
        raise RuntimeError("failed to position the pinion-sleeve section caption")
    rebuild_drawing(adapter, label="position pinion-sleeve section caption")
    position = tuple(float(value) for value in annotation.GetPosition())
    if math.dist(position[:2], target) > 1e-6:
        raise RuntimeError("pinion-sleeve section caption position did not persist")
    if str(note.PropertyLinkedText or "") != linked_text:
        raise RuntimeError("pinion-sleeve section caption lost its native fields")


def _assert_note_inside_border(note: Any, label: str) -> None:
    extent = tuple(float(v) for v in (_early_bound(note, "INote").GetExtent() or ()))
    _telemetry.info(f"{label} extent {extent}")
    x0, y0, x1, y1 = SHEET_INNER_BORDER
    if len(extent) < 5 or not (
        x0 <= extent[0] and y0 <= extent[1] and extent[3] <= x1 and extent[4] <= y1
    ):
        raise RuntimeError(
            f"{label} extent {extent} left the inner border {SHEET_INNER_BORDER}"
        )


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open transgear-feed-pinion source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "Gear Data",
            "Manufacturing Notes",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Gear Data",
            "Manufacturing Notes",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Transgear Pinion Sleeve Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "transgear pinion sleeve; steel; 12T DP30 feed pinion, spigot, shank",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=VIEW_SCALE)
    right = create_section_view(
        adapter,
        front,
        line_start=(FRONT_CENTER[0], FRONT_CENTER[1] - HALF_OD - 0.005),
        line_end=(FRONT_CENTER[0], FRONT_CENTER[1] + HALF_OD + 0.005),
        view_xy=RIGHT_CENTER,
        section_label="A",
        scale=VIEW_SCALE,
        label="pinion sleeve longitudinal centre section",
    )
    _position_section_caption(adapter, right, SECTION_CAPTION)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=VIEW_SCALE)
    for view in (front, right, iso):
        set_hidden_lines_removed(adapter, view)

    front_annotations = curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="front",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    right_annotations = curate_view_dimensions(
        adapter,
        right,
        keep=RIGHT_KEEP,
        view_label="longitudinal section",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    set_dimension_callouts(
        adapter, [*front_annotations, *right_annotations], DIMENSION_CALLOUTS
    )
    assert_imported_precision(
        adapter, front_annotations + right_annotations, DRAWING_PRECISION_BY_NAME
    )
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to the sleeve bore")
    _create_section_axis_centerline(adapter, right, label="pinion sleeve axis")

    oil_note = add_leader_note(
        adapter,
        OIL_HOLE_NOTE,
        text_xy=OIL_HOLE_CALLOUT,
        attach_xy=OIL_HOLE_EDGE,
        label="oil hole match-drill note",
        view=right,
        height=NOTE_HEIGHT,
    )
    bore_fit = add_leader_note(
        adapter,
        BORE_FIT_CALLOUT,
        text_xy=BORE_FIT_NOTE,
        attach_xy=BORE_FIT_ATTACH,
        label="sleeve bore fit",
        view=front,
        height=0.0022,
    )
    adapter.currentModel.GraphicsRedraw2()
    _assert_note_inside_border(oil_note, "oil hole note")
    _assert_note_inside_border(bore_fit, "bore fit note")
    # The bore is the part's one running surface: its finish is authored on
    # the part and read back here (rule 5).
    add_surface_finish(
        adapter,
        front,
        symbol_xy=FINISH_SYMBOL,
        control=surface_finish_by_key(SURFACE_FINISHES, "bore"),
        label="sleeve bore finish",
        entity=visible_circle_edge(adapter, front, BORE_DIA),
        leader_attach_xy=FINISH_ATTACH,
        char_height=0.0025,
    )

    add_property_linked_note(adapter, "Gear Data", 0.016, 0.262, char_height=0.0025)
    add_property_linked_note(
        adapter, "Manufacturing Notes", 0.016, 0.070, char_height=0.0025
    )
    rebuild_drawing(adapter, label="pinion sleeve layout audit")
    check_drawing_layout(adapter, layout=SPEC.layout, stem=PART_STEM)
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Transgear Pinion Sleeve Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
