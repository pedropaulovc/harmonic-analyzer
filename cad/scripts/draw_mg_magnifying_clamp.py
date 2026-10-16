r"""Create the curated machinist drawing for the magnifying-lever clamp.

A 28.65 length of 7/16 hex brass (#1559): the Ø6.2 lever bore drilled across
the corners, a #4-40 thumb-screw tap from the top face into the bore and a
blind #4-40 rod tap from the bottom face, both on the hex axis.

Views (3:1, hidden lines removed throughout, drawing-guidelines.md rule 9):

* RIGHT (looking along the lever bore, at a corner): the flats' width, the
  bore's outline, the block height and the bore's height and Ø.
* SECTION A-A, cut on the hex axis through the corners from the right view:
  the bore through the corners, both blind taps in solid lines and the floor
  between the rod tap and the bore.  It carries datum A (the bottom seat),
  the bore's parallelism to it and the bore's Ra.
* TOP: the hex across the flats (stock REF) and the thumb-screw tap's callout.
* BOTTOM: the rod tap's callout.
* Shaded isometric, 2:1.

Run with SolidWorks open::

    uv run python cad\scripts\draw_mg_magnifying_clamp.py mg-magnifying-clamp
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    dimension_name,
    place_view,
    remove_notes_matching,
)

from _check import check
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    stamp_drawing_summary,
)
from _drawing_dimension_import import curate_view_dimensions
from _drawing_dimensions import (
    assert_imported_precision,
    set_dimension_callouts,
    set_reference_dimension,
)
from _drawing_finish import add_surface_finish
from _drawing_gdt import add_datum_feature, add_feature_control_frame
from _drawing_hole_callout import add_native_hole_callout, set_hole_callout_precision
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_sections import create_section_view
from _drawing_view_display import set_hidden_lines_removed
from _gear_drawing_entities import visible_circle_edge
from _paths import CAD_ROOT
from _session import run_build
from _surface_finish import surface_finish_by_key
import _telemetry
from mg_magnifying_clamp_spec import (
    BLOCK_HEIGHT,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    GEOMETRIC_TOLERANCES_MM,
    HEX_AC,
    HEX_AF,
    LEVER_BORE_CALLOUT,
    LEVER_BORE_DIA,
    LEVER_BORE_Y,
    REFERENCE_DIMENSIONS,
    ROD_TAP_DRILL_DIA,
    ROD_TAP_PROCESS,
    SURFACE_FINISHES,
    TAP_CALLOUT_PRECISION,
    TAP_DRILL_DEPTH_VARIABLE,
    TAP_THREAD_DEPTH_VARIABLE,
    THUMB_TAP_PROCESS,
)


SPEC = DRAWINGS_BY_NAME["mg_magnifying_clamp"]
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

# A 12.8 x 11.1 x 28.65 hex: 3:1 puts the 86 mm tall right view and section
# side by side with room for the height dimensions either side.
SHEET_SCALE = (3.0, 1.0)
VIEW_SCALE = (3, 1)
ISO_SCALE = (2, 1)
_S = SHEET_SCALE[0] / SHEET_SCALE[1] / 1000.0  # sheet m per model mm

RIGHT_CENTER = (0.080, 0.165)
SECTION_CENTER = (0.200, RIGHT_CENTER[1])
TOP_CENTER = (0.295, 0.225)
BOTTOM_CENTER = (0.295, 0.125)
# Low right, over the title block (x > ~0.258, y < ~0.070).
ISO_CENTER = (0.395, 0.130)
NOTES_XY = (0.020, 0.075)
ISO_NOTE_XY = (0.365, 0.088)

_HALF_AF = HEX_AF / 2.0 * _S
_HALF_AC = HEX_AC / 2.0 * _S
_BORE_R = LEVER_BORE_DIA / 2.0


def _elev_y(center: tuple[float, float], model_y_mm: float) -> float:
    """Sheet y of a height above the bottom face in the right view or the
    section (both centred on the block's height)."""
    return center[1] + (model_y_mm - BLOCK_HEIGHT / 2.0) * _S


# The right view: the Ø above the view, the heights either side.
RIGHT_KEEP = {
    "Height": (RIGHT_CENTER[0] - _HALF_AF - 0.018, RIGHT_CENTER[1]),
    "LeverBoreYDim": (
        RIGHT_CENTER[0] + _HALF_AF + 0.016,
        _elev_y(RIGHT_CENTER, LEVER_BORE_Y / 2.0),
    ),
    "LeverBoreDiaDim": (RIGHT_CENTER[0], _elev_y(RIGHT_CENTER, BLOCK_HEIGHT) + 0.022),
}
# The top view: the flats (Z, sheet vertical) to the left of the hex.
TOP_KEEP = {"HexAf": (TOP_CENTER[0] - _HALF_AC - 0.014, TOP_CENTER[1])}

DIMENSION_CALLOUTS = {"LeverBoreDiaDim": LEVER_BORE_CALLOUT}

# The tap callouts run out to the right of each end view.
THUMB_TAP_CALLOUT_XY = (TOP_CENTER[0] + _HALF_AC + 0.012, TOP_CENTER[1] + 0.030)
ROD_TAP_CALLOUT_XY = (BOTTOM_CENTER[0] + _HALF_AC + 0.012, BOTTOM_CENTER[1] + 0.042)
# SolidWorks' own descriptive note for a Hole Wizard tap ("#4-40 Tapped Hole").
TAPPED_HOLE_NOTE = "Tapped Hole"

# The section's cutting line: vertical through the hex axis on the right view,
# past the block top and bottom.
_SECTION_OVERSHOOT = 0.006
# Picks in the section stand a third of the half-width off the hex axis (clear
# of both taps); the section is symmetric about the axis, so a mirrored
# section lands them on the same features.
_PICK_DX = 0.35 * _HALF_AC
_SECTION_RIGHT = SECTION_CENTER[0] + _HALF_AC
_SECTION_LEFT = SECTION_CENTER[0] - _HALF_AC

# swDimensionTextParts_e definitions (5-8) and the writable part each is set
# through (1-4) -- the draw_mg_output_fixture convention.
_CALLOUT_DEFINITION_PARTS = {5: 1, 6: 2, 7: 3, 8: 4}
_THREAD_DEPTH_TOKEN = f"<{TAP_THREAD_DEPTH_VARIABLE}>"
_DRILL_DEPTH_TOKEN = f"<{TAP_DRILL_DEPTH_VARIABLE}>"


def reference_thread_depth_definitions(definitions: dict[int, str]) -> dict[int, str]:
    """The thumb tap callout's definitions with the thread depth's variable
    bracketed REF, ``(<hw-threaddepth>)``: the lever bore ends that thread
    (ASME Y14.5 reference); the drill depth governs and stays bare."""
    joined = "\n".join(definitions.values())
    if (
        joined.count(_THREAD_DEPTH_TOKEN) != 1
        or f"({_THREAD_DEPTH_TOKEN}" in joined
        or joined.count(_DRILL_DEPTH_TOKEN) != 1
        or f"({_DRILL_DEPTH_TOKEN}" in joined
    ):
        raise RuntimeError(
            f"expected one bare {_THREAD_DEPTH_TOKEN} and one bare "
            f"{_DRILL_DEPTH_TOKEN} in the thumb tap callout: {definitions!r}"
        )
    return {
        part: text.replace(_THREAD_DEPTH_TOKEN, f"({_THREAD_DEPTH_TOKEN})")
        for part, text in definitions.items()
    }


def _reference_thread_depth(display: Any) -> None:
    before = {
        part: str(display.GetText(part) or "") for part in _CALLOUT_DEFINITION_PARTS
    }
    wanted = reference_thread_depth_definitions(before)
    (part,) = [part for part in before if wanted[part] != before[part]]
    display.SetText(_CALLOUT_DEFINITION_PARTS[part], wanted[part])
    after = {
        part: str(display.GetText(part) or "") for part in _CALLOUT_DEFINITION_PARTS
    }
    if after != wanted:
        raise RuntimeError(
            f"thumb tap thread depth did not persist as REF: wanted {wanted!r}, "
            f"read {after!r}"
        )
    _telemetry.success(f"thumb tap thread depth bracketed REF: {wanted[part]!r}")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open magnifying-clamp source", await adapter.open_model(str(SOURCE)))
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
            0: "Magnifying Clamp Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "magnifying clamp; 7/16 hex brass; lever bore across corners; two #4-40 taps",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=VIEW_SCALE)
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=VIEW_SCALE)
    bottom = place_view(
        adapter, str(SOURCE), "*Bottom", *BOTTOM_CENTER, scale=VIEW_SCALE
    )
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (right, top, bottom, iso):
        set_hidden_lines_removed(adapter, view)
    section = create_section_view(
        adapter,
        right,
        line_start=(
            RIGHT_CENTER[0],
            _elev_y(RIGHT_CENTER, BLOCK_HEIGHT) + _SECTION_OVERSHOOT,
        ),
        line_end=(RIGHT_CENTER[0], _elev_y(RIGHT_CENTER, 0.0) - _SECTION_OVERSHOOT),
        view_xy=SECTION_CENTER,
        section_label="A",
        scale=VIEW_SCALE,
        label="hex-axis section through the corners",
    )
    set_hidden_lines_removed(adapter, section)

    right_annotations = curate_view_dimensions(
        adapter,
        right,
        keep=RIGHT_KEEP,
        view_label="right",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    top_annotations = curate_view_dimensions(
        adapter,
        top,
        keep=TOP_KEEP,
        view_label="top",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    curate_view_dimensions(
        adapter,
        bottom,
        keep={},
        view_label="bottom",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    # Places are authored on the part; the sheet only proves the import kept them.
    assert_imported_precision(
        adapter, [*right_annotations, *top_annotations], DRAWING_PRECISION_BY_NAME
    )
    set_dimension_callouts(adapter, right_annotations, DIMENSION_CALLOUTS)
    # The flats are the bar's as supplied: a stock reference.
    top_by_name = {dimension_name(adapter, a): a for a in top_annotations}
    for name in sorted(REFERENCE_DIMENSIONS):
        set_reference_dimension(
            adapter, top_by_name[name], label=f"MHA-MG-002 {name} stock reference"
        )

    for view, label in ((top, "top"), (bottom, "bottom")):
        if not auto_center_marks(adapter, view, holes=True, size=0.0025):
            raise RuntimeError(f"failed to add the tap centre mark to the {label} view")
    # Each end view shows one visible tap-drill circle: its native callout
    # prints the drill and thread rows with the process ahead of the thread.
    thumb_callout = add_native_hole_callout(
        adapter,
        top,
        edge=visible_circle_edge(adapter, top, ROD_TAP_DRILL_DIA),
        callout_xy=THUMB_TAP_CALLOUT_XY,
        label="#4-40 thumb-screw tap",
        process=THUMB_TAP_PROCESS,
    )
    _reference_thread_depth(thumb_callout)
    set_hole_callout_precision(
        thumb_callout, TAP_CALLOUT_PRECISION, label="#4-40 thumb-screw tap depths"
    )
    rod_callout = add_native_hole_callout(
        adapter,
        bottom,
        edge=visible_circle_edge(adapter, bottom, ROD_TAP_DRILL_DIA),
        callout_xy=ROD_TAP_CALLOUT_XY,
        label="#4-40 vertical-rod tap",
        process=ROD_TAP_PROCESS,
    )
    set_hole_callout_precision(
        rod_callout, TAP_CALLOUT_PRECISION, label="#4-40 vertical-rod tap depths"
    )
    # SolidWorks pins its own "#4-40 Tapped Hole" note beside a tap's native
    # callout; the callout already states the thread. Farm run r1
    # (20261016T211740899Z) measured one on the bottom view, its leader
    # crossing the rod tap callout's (leader-crosses-leader). How many the
    # two taps bring is logged here, after both callouts; finalize_drawing's
    # census then proves none reached the print.
    removed = remove_notes_matching(adapter, TAPPED_HOLE_NOTE)
    _telemetry.info(f"removed {removed} automatic {TAPPED_HOLE_NOTE!r} note(s)")

    # Datum A = the bottom seat (the MHA-MG-004 shoulder's face), on the
    # section's bottom line; the lever bore's lower wall carries its
    # parallelism to A, and its upper wall the sliding bore's Ra.
    add_datum_feature(
        adapter,
        section,
        edge_xy=(SECTION_CENTER[0] + _PICK_DX, _elev_y(SECTION_CENTER, 0.0)),
        symbol_xy=(_SECTION_RIGHT + 0.012, _elev_y(SECTION_CENTER, 0.0) - 0.010),
        datum="A",
        label="bottom seat",
    )
    add_feature_control_frame(
        adapter,
        section,
        edge_xy=(
            SECTION_CENTER[0] + _PICK_DX,
            _elev_y(SECTION_CENTER, LEVER_BORE_Y - _BORE_R),
        ),
        frame_xy=(
            _SECTION_RIGHT + 0.010,
            _elev_y(SECTION_CENTER, LEVER_BORE_Y) - 0.014,
        ),
        characteristic="parallelism",
        tolerance=GEOMETRIC_TOLERANCES_MM["lever bore parallel to bottom seat"],
        datums=("A",),
        label="lever bore parallel to bottom seat",
    )
    add_surface_finish(
        adapter,
        section,
        edge_xy=(
            SECTION_CENTER[0] - _PICK_DX,
            _elev_y(SECTION_CENTER, LEVER_BORE_Y + _BORE_R),
        ),
        symbol_xy=(
            _SECTION_LEFT - 0.014,
            _elev_y(SECTION_CENTER, LEVER_BORE_Y) + 0.016,
        ),
        control=surface_finish_by_key(SURFACE_FINISHES, "lever_bore"),
        label="lever bore finish",
    )

    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Magnifying Clamp Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        redundant_note_substrings=(TAPPED_HOLE_NOTE,),
        expected_redundant_notes=0,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
