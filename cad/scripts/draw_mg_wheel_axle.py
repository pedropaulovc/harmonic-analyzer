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
    rebuild_drawing,
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
from mg_wheel_group import THREAD_LENGTH_CALLOUT


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

# Every view prints at the sheet scale, so none needs a caption. 3:1 lays the
# pin (about 56 with the MHA-MG-011 spacer's length in it) about 168 mm long,
# its 3/16 shank 14 mm across, and keeps the isometric (model +Y up the sheet,
# about 137 mm tall) inside the border; 4:1 ran both off the sheet.
SHEET_SCALE = (3.0, 1.0)
VIEW_SCALE = (3, 1)
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

# Rows below the profile (drawing-guidelines.md rule 11 (turned parts read like the lathe)): the shank and the thread both
# baseline from the gauged step (the press gauge's face), each with the
# dimension-origin circle on the step's extension line and named on its
# callout, then the overall as a reference. Run 18 left the shank's 4-line
# block (stacked band + two callout lines) 1.82 mm over the thread's stacked
# band (the audit asks 3.57); the .X shank prints one value line and one
# callout line, and its row rises 3 mm, which alone clears it.
_ROW_Y = (SIDE_CENTER[1] - 0.032, SIDE_CENTER[1] - 0.0588, SIDE_CENTER[1] - 0.0800)
# The thread length spans about 25 mm of sheet, its ~63 mm callout block wider:
# the block stands wholly left of the step's extension line (4 mm air, room
# for the origin circle there), clear of the overall's extension line
# dropping from the tip on the right.
_THREAD_BLOCK_HALF = 0.0317
# Diameters on the profile.
SIDE_KEEP = {
    "ShankLength": ((BACK_X + STEP_X) / 2.0, _ROW_Y[0]),
    "ThreadLength": (STEP_X - 0.004 - _THREAD_BLOCK_HALF, _ROW_Y[1]),
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
# Each band states its need on its own callout (drawing-guidelines.md rule 4 (tighten only for function, and name the mate)): the pin's
# press fit with the bar bore's limits read from the bar's geom, the thread
# length's origin, the locknut's full thread and the most thread past it
# (mg_wheel_group). The .X shank names only its origin.
DIMENSION_CALLOUTS = {
    "PinDia": (
        "PRESS FIT IN MG-WHEEL-BAR\n"
        f"<MOD-DIAM>{BAR_BORE_LIMITS[0]:.3f}-{BAR_BORE_LIMITS[1]:.3f} REAMED BORE"
    ),
    "ShankLength": "FROM SHANK STEP",
    "ThreadLength": THREAD_LENGTH_CALLOUT,
}
# ASME Y14.5 dimension origin (swArrowStyle_e): the open circle marks the end
# a dimension reads from, so both lengths show the step as their origin
# rather than a chain through it; the other end keeps the closed arrowhead.
ORIGIN_DIMENSIONS = ("ShankLength", "ThreadLength")
_ORIGIN_ARROWHEAD = 4  # swArrowStyle_e.swORIGIN_ARROWHEAD
_CLOSED_ARROWHEAD = 1  # swArrowStyle_e.swCLOSED_ARROWHEAD
# The journal's finish (drawing-guidelines.md rule 6 (roughness symbols only where a surface runs, slides or locates)) lands on the shank's top silhouette
# between the Ø line and the step, where the wheel runs; the symbol stands
# just above, left of the thread callout's leader.
JOURNAL_FINISH_PICK = (STEP_X - 0.012, SIDE_CENTER[1] + PIN_DIA / 2.0 * _S / 1000.0)
JOURNAL_FINISH_SYMBOL = (STEP_X - 0.010, SIDE_CENTER[1] + 0.020)
FINISH_CHAR_HEIGHT = 0.0025
# A point on the shank face, clear of the Ø dimension line.
CENTERLINE_PICK = (BACK_X + 0.020, SIDE_CENTER[1] + 0.003)
# Bottom-left, above the title-block line.
NOTES_XY = (0.020, 0.048)


def _view_center_delta(
    adapter: Any, view: Any, intended: tuple[float, float], label: str
) -> tuple[float, float]:
    """Measured-vs-intended geometry-center delta for coordinate picks.

    ``place_view`` anchors on the model origin's projection, not the geometry
    box center, so a part that is not origin-symmetric (this pin spans
    y BACK_Y..TIP_Y, about -8.9..47) lands its geometry offset from the requested center. Every
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


def _arrowheads(annotation: Any, label: str) -> list[tuple[float, int]]:
    """Each arrowhead's tip x on the sheet and its style.

    ``IDisplayData::GetArrowHeadAtIndex2`` returns tip[3], dir[3], width,
    height, style, normal[3]; a length dimension carries exactly two.
    """
    data = annotation.GetDisplayData()
    if data is None:
        raise RuntimeError(f"{label} has no display data")
    data = _early_bound(data, "IDisplayData")
    heads = []
    for index in range(int(data.GetArrowHeadCount() or 0)):
        values = [float(value) for value in (data.GetArrowHeadAtIndex2(index) or ())]
        if len(values) < 9:
            raise RuntimeError(f"{label} arrowhead {index} is incomplete: {values!r}")
        heads.append((values[0], round(values[8])))
    if len(heads) != 2:
        raise RuntimeError(f"{label} has {len(heads)} arrowheads, expected 2")
    return heads


def _set_dimension_origin(
    adapter: Any, annotation: Any, *, origin_x: float, label: str
) -> None:
    """Put the dimension-origin circle on the arrowhead at ``origin_x``.

    Which arrowhead ``SetArrowHeadStyle2``'s first style lands on is the
    dimension's own order, so the styles are read back from the ink: if the
    circle came out at the far end, the pair is applied swapped and read
    again. Either way the sheet is proved, never assumed.
    """
    annotation = _early_bound(annotation, "IAnnotation")
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    heads = _arrowheads(annotation, label)
    near = min(range(2), key=lambda index: abs(heads[index][0] - origin_x))
    styles = [_CLOSED_ARROWHEAD, _CLOSED_ARROWHEAD]
    styles[near] = _ORIGIN_ARROWHEAD
    for attempt in (styles, styles[::-1]):
        if not display.SetArrowHeadStyle2(False, *attempt):
            raise RuntimeError(f"failed to set the {label} arrowhead styles")
        rebuild_drawing(adapter, label=f"{label} dimension origin")
        heads = _arrowheads(annotation, label)
        at_origin = min(heads, key=lambda head: abs(head[0] - origin_x))
        far = max(heads, key=lambda head: abs(head[0] - origin_x))
        if (at_origin[1], far[1]) == (_ORIGIN_ARROWHEAD, _CLOSED_ARROWHEAD):
            return
    raise RuntimeError(f"{label} origin circle is not at the step: {heads!r}")


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
    # Both lengths read from the step: the origin circle on its extension line.
    for name in ORIGIN_DIMENSIONS:
        matches = [a for a in side_annotations if dimension_name(adapter, a) == name]
        if len(matches) != 1:
            raise RuntimeError(f"expected one wheel-axle {name} dimension")
        _set_dimension_origin(
            adapter,
            matches[0],
            origin_x=spt(STEP_X, 0.0)[0],
            label=f"wheel axle {name}",
        )
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
    # The shaded isometric shows the #4-40 the callout names; imported before
    # finalize's note cleanup, so its label is counted rather than first
    # appearing at the native save (draw_pn_pen_hanger).
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
