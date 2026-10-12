r"""Create the manufacturing drawing for the output fixture (MHA-MG-006).

The SLDPRT is authoritative: every printed dimension, its places and its
band are model dimensions marked for the drawing
(``mg_output_fixture_spec.DRAWING_DIMENSIONS``); this recipe places views,
keeps each dimension where it reads, and proves the import kept the part's
places. Sheet/template and export behavior lives in ``_drawing_common``.
Dimension import and curation live in ``_drawing_dimension_import``.

The side view is the ``*Top`` orientation, as in the lathe: the hex axis
horizontal, looking straight down the reamed rod bore, the flats edge-on top
and bottom.  It carries every axial station from the free end, the spigot
and groove sizes and the bore's Ø.  The end view is the ``*Right``
projection, looking at the spigot face with the flats standing vertical; it
carries the flats, the bore's location from one flat (its origin is the tap,
on the bore axis) and the #4-40 tap's native callout.  Hidden lines stay
off: the tap is a standard hole its callout states.

Run with SolidWorks open::

    uv run python cad\scripts\draw_mg_output_fixture.py mg-output-fixture
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
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
from _drawing_dimensions import assert_imported_precision, set_dimension_callouts
from _drawing_hole_callout import add_native_hole_callout
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _paths import CAD_ROOT
from _session import run_build
import _telemetry
from _gear_drawing_entities import visible_circle_edge
from mg_output_fixture_geom import (
    FREE_END_X,
    GROOVE_X,
    HEX_AF,
    HEX_CORNER_RADIUS,
    SHOULDER_X,
    SPIGOT_FACE_X,
    TAP_DRILL_DIA,
)
from mg_output_fixture_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    ROD_BORE_CALLOUT,
    TAP_PROCESS,
    TAP_SPEC,
)


SPEC = DRAWINGS_BY_NAME["mg_output_fixture"]
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

# A 17.7 x 11 part: 4:1 leaves room for the side view's eight dimensions.
SHEET_SCALE = (4.0, 1.0)
VIEW_SCALE = (4, 1)
ISO_SCALE = (3, 1)
_S = SHEET_SCALE[0] / SHEET_SCALE[1]
SIDE_CENTER = (0.125, 0.180)
END_CENTER = (0.262, SIDE_CENTER[1])
# Low right, over the title block: the end view's tap callout runs out to
# the right at the hole's height, above it.
ISO_CENTER = (0.372, 0.115)
NOTES_XY = (0.016, 0.078)
# The side view is centred on the part's axial extent.
_AXIAL_MID = (FREE_END_X + SPIGOT_FACE_X) / 2.0
_HALF_AF = HEX_AF / 2.0


def _side_x(model_x_mm: float) -> float:
    """Sheet X of a station along the hex axis on the side view."""
    return SIDE_CENTER[0] + (model_x_mm - _AXIAL_MID) * _S / 1000.0


def _side_y(sketch_v_mm: float) -> float:
    """Sheet Y of a Top-plane sketch height on the side view (sheet up is
    sketch +v, model -Z)."""
    return SIDE_CENTER[1] + sketch_v_mm * _S / 1000.0


_SIDE_TOP = _side_y(_HALF_AF)
_SIDE_BOTTOM = _side_y(-_HALF_AF)
# The hex and groove stations stack over the side view, each text mid-span,
# their extension lines rising from the free end, the shoulder and the
# groove's centre.  The overall length runs under the view, outermost, so no
# extension line rises from the spigot face: the groove's radius (its sketch
# sits on the upper side, sketch +v) reads beyond the face, just over the
# spigot's top edge, its shoulder clear.  The bore's station (a 20 mm span
# under a 22 mm text) reads outside, left of the free end, so the overall
# length's extension line from the free end never runs through it.  The
# groove's root Ø hangs under the groove, between the two.
SIDE_KEEP = {
    "HexLength": (_side_x((FREE_END_X + SHOULDER_X) / 2.0), _SIDE_TOP + 0.010),
    "GrooveStation": (_side_x((FREE_END_X + GROOVE_X) / 2.0), _SIDE_TOP + 0.020),
    "OverallLength": (_side_x(_AXIAL_MID), _SIDE_BOTTOM - 0.032),
    "RodStation": (_side_x(FREE_END_X) - 0.015, _SIDE_BOTTOM - 0.010),
    "GrooveRootDia": (_side_x(GROOVE_X), _SIDE_BOTTOM - 0.012),
    "SpigotDia": (_side_x(SPIGOT_FACE_X) + 0.012, SIDE_CENTER[1]),
    "GrooveRadius": (_side_x(SPIGOT_FACE_X) + 0.012, _SIDE_TOP + 0.006),
    "RodBoreDia": (_side_x(FREE_END_X) - 0.022, SIDE_CENTER[1] + 0.012),
}
# The end view stands the flats vertical (``*Right`` looks along -X, sheet
# right is model -Z): across them above the hex, the bore's location from one
# of them below it.
_END_HALF_HEIGHT = HEX_CORNER_RADIUS * _S / 1000.0
END_KEEP = {
    "HexAf": (END_CENTER[0], END_CENTER[1] + _END_HALF_HEIGHT + 0.010),
    "BoreFromFlat": (END_CENTER[0], END_CENTER[1] - _END_HALF_HEIGHT - 0.010),
}
# The tap callout reads right of the end view at the hole's height: its
# leader leaves the drill circle a few degrees above the horizontal centre
# mark, crosses only the near flat, and stays between the flats' extension
# lines (rising from the flats' tops) and the bore's location (hanging from
# their bottoms).  ``callout_xy`` is the text's centre; the two rows run
# ~76 mm with the shoulder under the bottom row, ~5.6 mm below the centre
# (the v1 sheet's ink: centre (292, 134), shoulder end (254.0, 128.4)).
_END_HALF_WIDTH = HEX_AF / 2.0 * _S / 1000.0
_TAP_CALLOUT_HALF_WIDTH = 0.038
_TAP_CALLOUT_SHOULDER_DROP = 0.0056
TAP_CALLOUT_XY = (
    END_CENTER[0] + _END_HALF_WIDTH + 0.006 + _TAP_CALLOUT_HALF_WIDTH,
    END_CENTER[1] + 0.004 + _TAP_CALLOUT_SHOULDER_DROP,
)
# What the native callout must print: the thread itself, not just the drill.
_TAP_THREAD_TEXT = f"{TAP_SPEC.size.lstrip('#')} UNC"


def _check_tap_callout(display: Any) -> None:
    """Prove the callout states the tap: one resolved row carries the process,
    the thread and its class (the drill row alone would ask for a hole)."""
    resolved = [str(display.GetText(part) or "") for part in (1, 2, 3, 4)]
    thread = [text for text in resolved if _TAP_THREAD_TEXT in text]
    if (
        len(thread) != 1
        or TAP_SPEC.thread_class not in thread[0]
        or TAP_PROCESS not in thread[0]
    ):
        raise RuntimeError(
            f"thumb-screw tap callout does not state {TAP_PROCESS} "
            f"{_TAP_THREAD_TEXT}-{TAP_SPEC.thread_class}: {resolved!r}"
        )
    _telemetry.success(f"thumb-screw tap callout reads {thread[0]!r}")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open output-fixture source", await adapter.open_model(str(SOURCE)))
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
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
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
            0: "Output Fixture Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "output fixture; 3/8 hex brass; reamed rod bore; wire groove; #4-40 tap",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    side = place_view(adapter, str(SOURCE), "*Top", *SIDE_CENTER, scale=VIEW_SCALE)
    end = place_view(adapter, str(SOURCE), "*Right", *END_CENTER, scale=VIEW_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (side, end, iso):
        set_hidden_lines_removed(adapter, view)

    side_annotations = curate_view_dimensions(
        adapter,
        side,
        keep=SIDE_KEEP,
        view_label="side",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    end_annotations = curate_view_dimensions(
        adapter,
        end,
        keep=END_KEEP,
        view_label="end",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    # Places (and so each dimension's general row) are authored on the part;
    # the sheet only proves the import kept them.
    assert_imported_precision(
        adapter, [*side_annotations, *end_annotations], DRAWING_PRECISION_BY_NAME
    )
    set_dimension_callouts(adapter, side_annotations, {"RodBoreDia": ROD_BORE_CALLOUT})
    if not auto_center_marks(adapter, side, holes=True, size=0.0025):
        raise RuntimeError("failed to add the rod bore's center mark to the side view")
    if not auto_center_marks(adapter, end, holes=True, size=0.0025):
        raise RuntimeError("failed to add the tap's center mark to the end view")
    # The tap drill's edge on the spigot face: the one visible circle of the
    # Hole Wizard feature from the end.  The native callout prints the drill
    # row and, under it, the process on the thread row.
    tap_callout = add_native_hole_callout(
        adapter,
        end,
        edge=visible_circle_edge(adapter, end, TAP_DRILL_DIA),
        callout_xy=TAP_CALLOUT_XY,
        label="#4-40 thumb-screw tap",
        process=TAP_PROCESS,
    )
    _check_tap_callout(tap_callout)
    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Output Fixture Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        # SolidWorks pins its own "#4-40 Tapped Hole" note once the tap
        # carries a hole callout; the callout already states the thread.
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
