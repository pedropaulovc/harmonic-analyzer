r"""Create the curated manufacturing drawing for the rack-pinion reduction disc (MHA-PD-006).

Follows the batch gear-drawing pattern (see ``draw_cylinder_gear``). Drawn 1:1;
the 120T disc is large and thin.  The face view (``*Front``, the rear face)
prints the bore with its reamed limits and the fit note naming the MHA-PD-017
hub's spigot, and the native #0-80 tap callout with its mouth-break and
assembly-transfer lines (no bolt-circle position: the taps are spotted
through the MHA-PD-017 flange at assembly); the edge view prints the disc
thickness, the front (clamped) face as datum B and the rear face's
parallelism to it.
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_datum_feature,
    add_feature_control_frame,
    add_leader_note,
    add_native_hole_callout,
    add_property_linked_note,
    assert_imported_precision,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_hidden_lines_removed,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _gear_drawing_entities import visible_circle_edge
from _native_axis_datum import add_native_axis_datum
from _rack_bore_finish import add_rack_bore_finish
from pd_rack_pinion_spec import (
    BORE_CALLOUT,
    BORE_FIT_CALLOUT,
    BORE_DIA,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    FACE_WIDTH,
    FRONT_FACE_DATUM,
    GEOMETRIC_TOLERANCES_MM,
    OUTSIDE_DIA,
    TAP_CALLOUT_QUALIFIER,
    TAP_CENTRES,
    TAP_DRILL_DIA,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["pd_rack_pinion"]
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

SHEET_SCALE = (1.0, 1.0)
VIEW_SCALE = (1, 1)
FRONT_CENTER = (0.220, 0.175)
RIGHT_CENTER = (0.320, 0.175)
ISO_CENTER = (0.383, 0.210)  # 0.388 clipped the zone border right by 1.4 mm
# Below the face view, left of the edge view's 3.000 (19e33c6c2 printed the
# Ra 1.6 into it): the leader rises to the bore's 0° rim point under the
# 0° tap, right of the tap callout's leader.
BORE_FINISH_POSITION = (FRONT_CENTER[0] + 0.030, FRONT_CENTER[1] - 0.082)

HALF_OD = OUTSIDE_DIA * VIEW_SCALE[0] / 2000.0
FRONT_FACE_X = RIGHT_CENTER[0] - FACE_WIDTH * VIEW_SCALE[0] / 2000.0
REAR_FACE_X = RIGHT_CENTER[0] + FACE_WIDTH * VIEW_SCALE[0] / 2000.0
# Datum B tags the front face upper left of the edge view, in the lane the
# face view leaves; the parallelism frame hangs lower right of it, under the
# isometric, its leader on the rear face, so neither crosses the disc.
DATUM_B_EDGE = (FRONT_FACE_X, RIGHT_CENTER[1] + HALF_OD * 0.55)
DATUM_B_SYMBOL = (FRONT_FACE_X - 0.016, RIGHT_CENTER[1] + HALF_OD * 0.55)
PARALLELISM_EDGE = (REAR_FACE_X, RIGHT_CENTER[1] - HALF_OD * 0.45)
PARALLELISM_FRAME = (REAR_FACE_X + 0.012, RIGHT_CENTER[1] - HALF_OD * 0.45 - 0.012)

FRONT_KEEP = {
    # Approach from upper-left, clear of native datum A below-left.
    "BoreDia": (FRONT_CENTER[0] - 0.062, FRONT_CENTER[1] + 0.038),
}
# Below the edge-on disc, clear of datum B above and the frame to the right.
RIGHT_KEEP = {
    "FaceWidth": (RIGHT_CENTER[0], RIGHT_CENTER[1] - HALF_OD - 0.012),
}
DIMENSION_CALLOUTS = {"BoreDia": BORE_CALLOUT}
# The bore's fit note stands at the left margin under the gear data block;
# its leader lands on the bore's 180° point, between the bore dimension's
# upper-left leader and datum A below-left.
_BORE_SHEET_RADIUS = BORE_DIA * VIEW_SCALE[0] / 2000.0
BORE_FIT_NOTE = (0.018, 0.200)
BORE_FIT_ATTACH = (
    FRONT_CENTER[0] + _BORE_SHEET_RADIUS * math.cos(math.radians(180.0)),
    FRONT_CENTER[1] + _BORE_SHEET_RADIUS * math.sin(math.radians(180.0)),
)
# Lower-left of the face view, off the rim: the leader rises to the lower-left
# tap, below datum A and clear of the bore.  The pick is on that tap's drill
# circle at 225° about its centre, off the centre-mark lines.  The face view is
# symmetric about its horizontal axis, so the sheet's lower-left tap is the
# model's x < 0 centre drawn under the axis whichever way the view mirrors.
# (19e33c6c2 let visible_circle_edge break the tie between the two x < 0
# taps on float noise: it took the upper one and the leader crossed the bore.)
TAP_CALLOUT_XY = (FRONT_CENTER[0] - 0.060, FRONT_CENTER[1] - 0.058)
_TAP_X, _TAP_Y = min(TAP_CENTRES)  # either x < 0 centre: only |y| is drawn
TAP_SHEET_CENTER = (
    FRONT_CENTER[0] + _TAP_X * VIEW_SCALE[0] / 1000.0,
    FRONT_CENTER[1] - abs(_TAP_Y) * VIEW_SCALE[0] / 1000.0,
)
_TAP_SHEET_RADIUS = TAP_DRILL_DIA * VIEW_SCALE[0] / 2000.0
TAP_PICK = (
    TAP_SHEET_CENTER[0] + _TAP_SHEET_RADIUS * math.cos(math.radians(225.0)),
    TAP_SHEET_CENTER[1] + _TAP_SHEET_RADIUS * math.sin(math.radians(225.0)),
)


def tap_callout_definitions(definitions: dict[int, str]) -> dict[int, str]:
    """Append the mouth-break and transfer lines to the one thread compartment."""
    if set(definitions) != {5, 6, 7, 8}:
        raise RuntimeError(f"unexpected tap callout parts: {definitions!r}")
    thread_parts = [
        part for part, text in definitions.items() if "<hw-threadclass>" in text.lower()
    ]
    if len(thread_parts) != 1:
        raise RuntimeError(
            f"tap thread line is not in one callout part: {definitions!r}"
        )
    updated = dict(definitions)
    part = thread_parts[0]
    updated[part] = f"{updated[part].rstrip()}\n{TAP_CALLOUT_QUALIFIER}"
    return updated


def _set_tap_callout_text(display: Any) -> None:
    definitions = {part: str(display.GetText(part) or "") for part in (5, 6, 7, 8)}
    updated = tap_callout_definitions(definitions)
    for definition_part, writable_part in ((5, 1), (6, 2), (7, 3), (8, 4)):
        if updated[definition_part] != definitions[definition_part]:
            display.SetText(writable_part, updated[definition_part])
    persisted = {part: str(display.GetText(part) or "") for part in (5, 6, 7, 8)}
    resolved = {part: str(display.GetText(part) or "") for part in (1, 2, 3, 4)}
    thread = [text for text in resolved.values() if "UNF" in text]
    if (
        persisted != updated
        or len(thread) != 1
        or not thread[0].rstrip().endswith(TAP_CALLOUT_QUALIFIER)
    ):
        raise RuntimeError(
            "rack-pinion tap callout lines did not persist: "
            f"definitions={persisted!r}, resolved={resolved!r}"
        )


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open rack-pinion source", await adapter.open_model(str(SOURCE)))
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
            0: "Rack-Pinion Disc Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "rack pinion; reduction disc; brass; 120T",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=VIEW_SCALE)
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=VIEW_SCALE)
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
        view_label="edge",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    # Decimal places (and so the general-tolerance row each dimension claims)
    # are authored on the part; the sheet only proves the import kept them.
    assert_imported_precision(
        adapter, [*front_annotations, *right_annotations], DRAWING_PRECISION_BY_NAME
    )
    set_dimension_callouts(adapter, front_annotations, DIMENSION_CALLOUTS)
    add_leader_note(
        adapter,
        BORE_FIT_CALLOUT,
        text_xy=BORE_FIT_NOTE,
        attach_xy=BORE_FIT_ATTACH,
        label="disc bore fit",
        view=front,
        height=0.0022,
    )
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to disc bore")
    bore_edge = visible_circle_edge(adapter, front, BORE_DIA)

    add_native_axis_datum(
        adapter,
        front,
        entity=bore_edge,
        source_path=SOURCE,
        radius_m=BORE_DIA / 2000.0,
        datum="A",
        label="rack pinion bore axis",
        shoulder=True,
        stability_tolerance_m=0.0001,
    )
    # Datum B: a vertical edge with no neighbour inside the pick radius at
    # this height (the rear face stands 3 mm off), so the hit-test form.
    add_datum_feature(
        adapter,
        right,
        edge_xy=DATUM_B_EDGE,
        symbol_xy=DATUM_B_SYMBOL,
        datum=FRONT_FACE_DATUM,
        label="disc front (clamped) face",
    )
    add_feature_control_frame(
        adapter,
        right,
        edge_xy=PARALLELISM_EDGE,
        frame_xy=PARALLELISM_FRAME,
        characteristic="parallelism",
        tolerance=GEOMETRIC_TOLERANCES_MM["disc rear face parallelism to front"],
        datums=(FRONT_FACE_DATUM,),
        label="disc rear face parallelism to front",
    )
    # Explicit entity selection supplies the insertion point. No post-insertion
    # endpoint setter: that setter drops the semantic association on this symbol.
    add_rack_bore_finish(adapter, front, bore_edge, symbol_xy=BORE_FINISH_POSITION)

    # The native thread and drill ride the callout; the mouth breaks and the
    # assembly transfer are the spec's lines under it.
    tap_callout = add_native_hole_callout(
        adapter,
        front,
        edge_xy=TAP_PICK,
        callout_xy=TAP_CALLOUT_XY,
        label="#0-80 transferred disc taps",
    )
    _set_tap_callout_text(tap_callout)

    add_property_linked_note(adapter, "Gear Data", 0.018, 0.262)
    add_property_linked_note(adapter, "Manufacturing Notes", 0.018, 0.095)
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Rack-Pinion Disc Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        # SolidWorks pins its own "... Tapped Hole" note to the face view once
        # the tap carries a hole callout; the callout already states it.
        redundant_note_substrings=("Tapped Hole",),
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
