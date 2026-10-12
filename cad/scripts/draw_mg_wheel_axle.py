r"""Create the curated machinist drawing for the magnifying-wheel axle."""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import (
    dimension_name,
    place_view,
    view_outline,
)

from _check import check
from _com import _early_bound
from _drawing_centerline import add_view_centerline
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    stamp_drawing_summary,
)
from _drawing_dimension_import import curate_view_dimensions, import_cosmetic_threads
from _drawing_dimensions import (
    assert_imported_precision,
    set_dimension_callouts,
    set_reference_dimension,
)
from _drawing_finish import add_surface_finish
from _drawing_leader_notes import add_attached_note
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _paths import CAD_ROOT
from _session import run_build
from _surface_finish import surface_finish_by_key
import _telemetry
from mg_wheel_axle_spec import (
    BACK_Y,
    BAR_BORE_LIMITS,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    PIN_DIA,
    REFERENCE_DIMENSIONS,
    STEP_Y,
    SURFACE_FINISHES,
    THREAD_CALLOUT,
    THREAD_END_Y,
    THREAD_MAJOR,
    TIP_Y,
)
from mg_wheel_group import BACK_END_PROUD_MAX, BACK_END_SUNK_MAX, STEP_TO_THREAD_END


SPEC = DRAWINGS_BY_NAME["mg_wheel_axle"]
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

# Every view prints at the sheet scale, so none needs a caption. 4:1 lays the
# 37.2 pin 149 mm long and its 3/16 shank 19 mm across.
SHEET_SCALE = (4.0, 1.0)
VIEW_SCALE = (4, 1)
_S = SHEET_SCALE[0] / SHEET_SCALE[1]
# One side view: the *Front view (parallel to the profile sketch, so its
# dimensions import), turned so the pin lies horizontal, back end left.
SIDE_CENTER = (0.160, 0.170)
SIDE_VIEW_ANGLE = -math.pi / 2.0  # model +Y (back end -> tip) to paper right
ISO_CENTER = (0.335, 0.185)
_MID_Y = (BACK_Y + TIP_Y) / 2.0


def _sheet_x(model_y_mm: float) -> float:
    """Sheet X of a model-Y station on the side view (the view is centred on
    the model bbox, back end to tip)."""
    return SIDE_CENTER[0] + (model_y_mm - _MID_Y) * _S / 1000.0


BACK_X = _sheet_x(BACK_Y)
STEP_X = _sheet_x(STEP_Y)
THREAD_END_X = _sheet_x(THREAD_END_Y)
TIP_X = _sheet_x(TIP_Y)

# Baseline rows below the profile, all from the back end (policy rule 7): the
# step, the thread end, then the overall as a reference. Each linear
# dimension's text block (stacked band plus its callout lines) stands above
# its own line, so each row drops by the block over it plus 4 mm of air (the
# audit asks 3.57 between blocks): the step's and the thread end's four lines
# (~19 mm each), the one-line reference under them.
_ROW_Y = (SIDE_CENTER[1] - 0.035, SIDE_CENTER[1] - 0.0588, SIDE_CENTER[1] - 0.074)
# Diameters on the profile.
SIDE_KEEP = {
    "ShankLength": ((BACK_X + STEP_X) / 2.0, _ROW_Y[0]),
    "ThreadEnd": ((BACK_X + THREAD_END_X) / 2.0, _ROW_Y[1]),
    "PinLength": ((BACK_X + TIP_X) / 2.0, _ROW_Y[2]),
    # The shank's dimension line crosses the shank near the step; its text
    # runs left from the line, the fit callout's two lines under it, so the
    # block stands high enough to keep them off the shank.
    "PinDia": (STEP_X - 0.030, SIDE_CENTER[1] + 0.045),
    # Above-right of the tip: the leader lands on the dome's upper half, clear
    # of the overall's extension line dropping from the tip, and under the
    # thread callout.
    "DomeR": (TIP_X + 0.015, SIDE_CENTER[1] + 0.015),
}
DRAWING_PRECISION_BY_NAME = {
    name: places
    for names in DRAWING_PRECISION.values()
    for name, places in names.items()
}
# The thread callout's leader lands on the thread's major-diameter silhouette
# midway along the threaded length; the note stands up and right so the
# leader leans back onto it, clear of the dome.
THREAD_PICK = (
    (STEP_X + THREAD_END_X) / 2.0,
    SIDE_CENTER[1] + THREAD_MAJOR / 2.0 * _S / 1000.0,
)
THREAD_NOTE_XY = (THREAD_END_X + 0.012, SIDE_CENTER[1] + 0.042)
# Each band states its need on its own callout (policy rule 2): the pin's
# press fit with the bar bore's limits read from the bar's geom, the step's
# station where the back end lands, the thread end's full thread under the
# locknut. The two stations' bands add on the thread from the step, which
# the locknut's full thread and the past-locknut cap pin to the
# mg_wheel_group limits printed under it.
DIMENSION_CALLOUTS = {
    "PinDia": (
        "PRESS FIT IN MG-WHEEL-BAR\n"
        f"<MOD-DIAM>{BAR_BORE_LIMITS[0]:.3f}-{BAR_BORE_LIMITS[1]:.3f} REAMED BORE"
    ),
    "ShankLength": (
        "PRESSED TO GAUGE: BACK END\n"
        f"{BACK_END_PROUD_MAX:.2f} PROUD TO {BACK_END_SUNK_MAX:.2f} SUNK IN BAR"
    ),
    "ThreadEnd": (
        "LOCKNUT ON FULL THREAD,\n"
        f"STEP TO THREAD END {STEP_TO_THREAD_END[0]:.2f}-{STEP_TO_THREAD_END[1]:.2f}"
    ),
}
# The journal's finish (policy rule 5) lands on the shank's top silhouette
# between the Ø line and the step, where the wheel runs; the symbol stands
# just above, left of the thread callout's leader.
JOURNAL_FINISH_PICK = (STEP_X - 0.012, SIDE_CENTER[1] + PIN_DIA / 2.0 * _S / 1000.0)
JOURNAL_FINISH_SYMBOL = (STEP_X - 0.010, SIDE_CENTER[1] + 0.020)
FINISH_CHAR_HEIGHT = 0.0025
# A point on the shank face, clear of the Ø dimension line.
CENTERLINE_PICK = (BACK_X + 0.020, SIDE_CENTER[1] + 0.003)
# Bottom-left, above the title-block line.
NOTES_XY = (0.020, 0.048)
# swUserPreferenceToggle_e, read from the installed SOLIDWORKS 3DEXPERIENCE
# R2026x swconst.tlb (2026-10-12): Display filter > Cosmetic threads and
# Shaded cosmetic threads, set on the drawing with swDetailingNoOptionSpecified.
SW_DISPLAY_COSMETIC_THREADS = 41
SW_DISPLAY_SHADED_COSMETIC_THREADS = 230


def _show_cosmetic_threads(adapter: Any) -> None:
    """Turn on the drawing's cosmetic-thread display filter.

    Run 20261012T084447505Z read the thread annotation in both views, yet the
    side view printed the #4-40 end plain, with no minor-diameter lines, and
    the isometric unshaded: set the filter on the document rather than rely
    on the template's default.
    """
    extension = _early_bound(adapter.currentModel.Extension, "IModelDocExtension")
    for toggle in (SW_DISPLAY_COSMETIC_THREADS, SW_DISPLAY_SHADED_COSMETIC_THREADS):
        extension.SetUserPreferenceToggle(toggle, 0, True)
        if not extension.GetUserPreferenceToggle(toggle, 0):
            raise RuntimeError(
                f"wheel-axle drawing refused thread display toggle {toggle}"
            )


def _view_center_delta(
    adapter: Any, view: Any, intended: tuple[float, float], label: str
) -> tuple[float, float]:
    """Measured-vs-intended geometry-center delta for coordinate picks.

    ``place_view`` anchors on the model origin's projection, not the geometry
    box center, so a part that is not origin-symmetric (this pin spans
    y -8.9..28.32) lands its geometry offset from the requested center. Every
    layout constant in this recipe is authored about the intended geometry
    center; shifting by this delta makes the edge picks and text positions
    track wherever SolidWorks actually put the geometry.
    """
    outline = view_outline(adapter, view)
    if outline is None:
        raise RuntimeError(f"{label} drawing view has no outline")
    cx = (outline[0] + outline[2]) / 2.0
    cy = (outline[1] + outline[3]) / 2.0
    _telemetry.debug(
        f"{label} view geometry center ({cx:.4f}, {cy:.4f}) vs intended "
        f"({intended[0]:.4f}, {intended[1]:.4f})"
    )
    return cx - intended[0], cy - intended[1]


def _shift(
    points: dict[str, tuple[float, float]], dx: float, dy: float
) -> dict[str, tuple[float, float]]:
    return {name: (x + dx, y + dy) for name, (x, y) in points.items()}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open wheel-axle source", await adapter.open_model(str(SOURCE)))
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
            0: "Wheel Axle Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: f"wheel axle; 3/16 drill-rod pin; {THREAD_CALLOUT}; steel",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    side = place_view(adapter, str(SOURCE), "*Front", *SIDE_CENTER, scale=VIEW_SCALE)
    native = _early_bound(side, "IView")
    native.Angle = SIDE_VIEW_ANGLE
    if abs(math.remainder(float(native.Angle) - SIDE_VIEW_ANGLE, 2.0 * math.pi)) > 1e-9:
        raise RuntimeError("failed to rotate the wheel-axle side view")
    drawing_model.EditRebuild3()
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=VIEW_SCALE)
    for view in (side, iso):
        set_hidden_lines_removed(adapter, view)

    dx, dy = _view_center_delta(adapter, side, SIDE_CENTER, "side")

    def spt(x: float, y: float) -> tuple[float, float]:
        return (x + dx, y + dy)

    side_annotations = curate_view_dimensions(
        adapter,
        side,
        keep=_shift(SIDE_KEEP, dx, dy),
        view_label="side",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    assert_imported_precision(adapter, side_annotations, DRAWING_PRECISION_BY_NAME)
    set_dimension_callouts(adapter, side_annotations, DIMENSION_CALLOUTS)
    # The overall sums the two stations and the dome: a reference.
    for name in sorted(REFERENCE_DIMENSIONS):
        matches = [a for a in side_annotations if dimension_name(adapter, a) == name]
        if len(matches) != 1:
            raise RuntimeError(f"expected one wheel-axle {name} reference dimension")
        set_reference_dimension(adapter, matches[0], label=f"wheel axle {name}")
    add_view_centerline(
        adapter,
        side,
        face_xy=spt(*CENTERLINE_PICK),
        label="wheel axle turning axis",
    )
    add_attached_note(
        adapter,
        side,
        text=THREAD_CALLOUT,
        entity_xy=spt(*THREAD_PICK),
        note_xy=spt(*THREAD_NOTE_XY),
        label="wheel axle thread callout",
        entity_type="SILHOUETTE",
    )
    add_surface_finish(
        adapter,
        side,
        edge_xy=spt(*JOURNAL_FINISH_PICK),
        entity_type="SILHOUETTE",
        symbol_xy=spt(*JOURNAL_FINISH_SYMBOL),
        leader_attach_xy=spt(*JOURNAL_FINISH_PICK),
        control=surface_finish_by_key(SURFACE_FINISHES, "mg_axle_journal"),
        label="wheel axle journal finish",
        char_height=FINISH_CHAR_HEIGHT,
    )

    # x=0.020: a note is left-aligned on its anchor, so the ink starts here,
    # clear of the 12.7 mm zone margin.
    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)
    # The side view draws the #4-40's minor-diameter lines and the shaded
    # isometric the thread the callout names; imported before finalize's
    # note cleanup, so its label is counted rather than first appearing at
    # the native save (draw_pn_pen_hanger).
    _show_cosmetic_threads(adapter)
    thread_seeds, thread_instances = import_cosmetic_threads(adapter, iso)
    if (thread_seeds, thread_instances) != (1, 1):
        raise RuntimeError(
            "wheel-axle isometric cosmetic threads: "
            f"seeds/instances={(thread_seeds, thread_instances)!r}, expected (1, 1)"
        )

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Wheel Axle Manufacturing Drawing",
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
