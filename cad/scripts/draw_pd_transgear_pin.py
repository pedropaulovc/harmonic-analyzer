r"""Create the MHA-PD-23 transgear pin manufacturing drawing.

The SLDPRT remains authoritative.  A turned pin carries no datum and no
geometric-control frame (drawing-guidelines.md rule 5 (avoid excessive GD&T)): the turned shank keeps its native
fit band, named at its Ø with both fits it serves, and one bearing-surface
finish, the MHA-PD-VN-61 ring groove its catalogue Ø and width bands, and
every other size is an ordinary model dimension at its part-authored places.

The pin axis is model +Z, so the ``*Right`` view lays it horizontal as it
sits in the lathe: model +Z runs to paper-LEFT, putting the domed tip on the
left and the head on the right.  Every feature is visible, so the side view
removes hidden lines.  The head's underside (its seat on the MHA-PD-18 arm) is
the one origin: the groove's load wall, the pin's functional station, and the
tip's apex are dimensioned from it, and the head land runs back from it.  The
land ahead of the groove, the dome heights and the apex-to-tip overall print
as references.  The sheet prints decimal inch (the part's ``drawing_unit``);
the model keeps its millimetre nominals.

Run with SolidWorks open::

    uv run python cad\scripts\draw_pd_transgear_pin.py pd-transgear-pin
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import dimension_name, place_view

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
from _drawing_dimensions import (
    assert_imported_precision,
    set_arc_endpoints_to_max,
    set_reference_dimension,
)
from _drawing_edge_dimensions import add_edge_dimension, assert_dimension_measures
from _drawing_finish import add_surface_finish
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_points_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _machinist_review_mode import MachinistReviewMode
from _part_properties import part_drawing_unit
from _paths import CAD_ROOT
from _session import run_build
from _surface_finish import surface_finish_by_key
import _telemetry
import pd_transgear_pin_callouts as callouts
from pd_transgear_pin_spec import (
    DIA,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    DRAWING_REFERENCE_PRECISION,
    FRONT_LAND,
    GROOVE_REAR_STATION,
    GROOVE_STATION,
    HEAD_DIA,
    HEAD_HEIGHT,
    HEAD_LAND,
    LENGTH,
    OVERALL_LENGTH,
    SURFACE_FINISHES,
)

MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["pd_transgear_pin"]
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

# The side view prints at the sheet scale, so it needs no caption.  3:1 lays
# the 2.14 in pin 163 mm long and the .020 groove 1.5 mm wide.
SHEET_SCALE = (3.0, 1.0)
VIEW_SCALE = (3, 1)
_S = SHEET_SCALE[0] / SHEET_SCALE[1]
SIDE_CENTER = (0.170, 0.165)
ISO_CENTER = (0.345, 0.225)
ISO_SCALE = (2, 1)
_MID_Z = (LENGTH - HEAD_HEIGHT) / 2.0


def _sheet_x(model_z_mm: float) -> float:
    """Sheet X of a model-Z station on the side view (model +Z runs left)."""
    return SIDE_CENTER[0] + (_MID_Z - model_z_mm) * _S / 1000.0


def _sheet_y(radius_mm: float) -> float:
    """Sheet Y of a point ``radius_mm`` above the pin axis (model +Y up)."""
    return SIDE_CENTER[1] + radius_mm * _S / 1000.0


HEAD_APEX_X = _sheet_x(-HEAD_HEIGHT)
HEAD_BACK_X = _sheet_x(-HEAD_LAND)
SEAT_X = _sheet_x(0.0)
GROOVE_REAR_X = _sheet_x(GROOVE_REAR_STATION)
LOAD_WALL_X = _sheet_x(GROOVE_STATION)
FRONT_END_X = _sheet_x(GROOVE_STATION + FRONT_LAND)
TIP_X = _sheet_x(LENGTH)
HEAD_TOP_Y = _sheet_y(HEAD_DIA / 2.0)
SHANK_TOP_Y = _sheet_y(DIA / 2.0)
GROOVE_MID_X = (GROOVE_REAR_X + LOAD_WALL_X) / 2.0
SHANK_MID_X = (SEAT_X + GROOVE_REAR_X) / 2.0
HEAD_LAND_MID_X = (HEAD_BACK_X + SEAT_X) / 2.0

# One axial row under the profile: the functional station (head seat to the
# groove's load wall, naming the stack it sets), the reference land off that
# wall, and the head land off the seat with its text right of the head.  The
# tip apex's station from the seat runs in a second row below the station's
# callout, the reference overall apex to tip in a third.  The groove width
# hangs between the row and the profile, its text
# and ring callout toward the head, clear of the groove's rear-wall extension
# line (at +0.016 that line struck the 0.737, run 20261024T022718524Z) and of
# the station's load-wall extension line; the head dome's reference height
# sits at the same height right of the head.  The diameters
# stand above the profile, each on its own section: the shank Ø's three-line
# fit callout under its value, the groove Ø above it with the ring's name
# above its value.  The tip dome's reference height stands above the tip.
_ROW_Y = SIDE_CENTER[1] - 0.036
SIDE_KEEP = {
    "GrooveStation": ((SEAT_X + LOAD_WALL_X) / 2.0, _ROW_Y),
    # Left of the tip apex's extension line (shared by the 51.35 and the
    # overall), which ran through the ')' at FRONT_END_X - 0.010 (layout
    # audit text-on-line, run 20261024T060429646Z).
    "FrontLand": (TIP_X - 0.008, _ROW_Y),
    "HeadLand": (HEAD_APEX_X + 0.010, _ROW_Y),
    "GrooveWidth": (GROOVE_MID_X + 0.032, SIDE_CENTER[1] - 0.016),
    "HeadDia": (HEAD_LAND_MID_X, HEAD_TOP_Y + 0.010),
    # At the shank's middle: its dimension line, and the arrow below the
    # shank, stand clear right of the groove width's text and ring callout
    # (34 mm left of here the lower arrow struck the +0.0762, run
    # 20261024T030409384Z).  The callout under the value runs right from
    # the line, high enough that it clears the Ra symbol and the head Ø.
    "ShankDia": (SHANK_MID_X, SHANK_TOP_Y + 0.046),
    # Above the shank Ø's whole block, with a text gap past the audit's
    # 3.57 mm (+0.068 left 2.80 to the shank Ø's 0.000): its shoulder, as
    # wide as the ring callout, ends left of the shank Ø's +0.000.
    "GrooveDia": (GROOVE_MID_X, SHANK_TOP_Y + 0.072),
    "HeadDomeR": (HEAD_APEX_X + 0.012, SIDE_CENTER[1] + 0.006),
    "HeadDomeSagDim": (HEAD_APEX_X + 0.012, SIDE_CENTER[1] - 0.016),
    "TipDomeR": (TIP_X - 0.012, SIDE_CENTER[1] - 0.016),
    "TipDomeSagDim": (TIP_X - 0.012, SIDE_CENTER[1] + 0.016),
    # The tip apex from the head seat, the pin's one faced origin (rule 11):
    # the one controlled length at that end, under the station's three-row
    # callout.
    "TipDomeZ": ((SEAT_X + TIP_X) / 2.0, _ROW_Y - 0.027),
}
# The callouts and the dome heights' reference parentheses are authored on
# the part's dimensions (``pd_transgear_pin_callouts``); the sheet only
# proves they arrived.
OVERALL_TEXT_XY = (SIDE_CENTER[0], _ROW_Y - 0.047)
# The shank's upper silhouette, between the shank Ø's tolerance stack and the
# head Ø (at 30 mm left of the seat its leader touched the -0.008).
FINISH_PICK = (SEAT_X - 0.015, SHANK_TOP_Y)
FINISH_SYMBOL = (SEAT_X - 0.015, SHANK_TOP_Y + 0.008)
# A point on the shank face, clear of the Ø dimension line.
CENTERLINE_PICK = (SHANK_MID_X + 0.010, SIDE_CENTER[1] + 0.001)
ISO_NOTE_XY = (ISO_CENTER[0] - 0.030, ISO_CENTER[1] - 0.040)
NOTES_XY = (0.016, 0.070)


def _assert_part_authored_text(adapter: Any, annotations: list[Any]) -> None:
    """Every imported dimension prints the text lanes its part authored.

    The mates, the stack and the reference marks print nowhere else on the
    sheet, so a lost lane must fail the drawing.  Read-only: text set from
    the sheet would write through to the source part (#1942).
    """
    wanted = callouts.authored_by_name()
    displays: dict[str, list[Any]] = {name: [] for name in wanted}
    for annotation in annotations:
        name = dimension_name(adapter, annotation)
        if name in displays:
            displays[name].append(
                _early_bound(
                    _early_bound(annotation, "IAnnotation").GetSpecificAnnotation(),
                    "IDisplayDimension",
                )
            )
    counts = {name: len(found) for name, found in displays.items() if len(found) != 1}
    if counts:
        raise RuntimeError(f"authored dimensions not printed exactly once: {counts!r}")
    printed = {
        (name, lane): str(displays[name][0].GetText(lane) or "")
        for name, lanes in wanted.items()
        for lane in lanes
    }
    wrong = {
        key: text
        for key, text in printed.items()
        if callouts.callout_rows(text) != callouts.callout_rows(wanted[key[0]][key[1]])
    }
    if wrong:
        raise RuntimeError(
            f"imported dimension text differs from the part's: {wrong!r}"
        )


def _overall_reference(adapter: Any, side: Any) -> None:
    """The overall REF, head apex to tip apex (rule 10), for the bar cut.

    A drawing-owned dimension, so its reference parentheses are the sheet's
    own text, not an imported part dimension's.
    """
    label = "pin overall length reference"
    head_apex, tip_apex = model_points_in_view(
        adapter,
        side,
        ((0.0, 0.0, -HEAD_HEIGHT / 1000.0), (0.0, 0.0, LENGTH / 1000.0)),
        label=label,
        names=("head apex", "tip apex"),
    )
    display = add_edge_dimension(
        adapter,
        side,
        p0=tip_apex,
        p1=head_apex,
        text_xy=OVERALL_TEXT_XY,
        label=label,
        orientation="horizontal",
        entity_type="SILHOUETTE",
    )
    display = _early_bound(display, "IDisplayDimension")
    dimension_type = int(display.Type2)
    # swLinearDimension, swHorLinearDimension: the curved silhouette picks
    # must still give a length before SystemValue is read as metres.
    if dimension_type not in (2, 11):
        raise RuntimeError(
            f"{label}: expected a linear dimension, got type {dimension_type}"
        )
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    measured_mm = abs(float(dimension.SystemValue) * 1000.0)
    if not math.isclose(measured_mm, OVERALL_LENGTH, abs_tol=1e-4):
        # A pick on a dome may resolve to its centre; the overall runs to
        # each apex, the arcs' far extremes.
        set_arc_endpoints_to_max(adapter, display, label=label)
    # Value-only: both picks are dome apexes located by coordinate, and the
    # apex-to-apex sum is the one value a centre-anchored pick cannot give.
    # Rejects a non-finite readback too.
    assert_dimension_measures(
        adapter, display, expected_mm=OVERALL_LENGTH, label=label, tolerance_mm=1e-4
    )
    set_reference_dimension(adapter, display.GetAnnotation(), label=label)
    display.SetPrecision3(DRAWING_REFERENCE_PRECISION, -1, -1, -1)
    if int(display.GetPrimaryPrecision2()) != DRAWING_REFERENCE_PRECISION:
        raise RuntimeError(f"{label} precision did not persist")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open transgear-pin source", await adapter.open_model(str(SOURCE)))
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
        adapter,
        property_view=PART_STEM,
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        unit=part_drawing_unit(PART_STEM),
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Transgear Pin Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "transgear pin; turned steel; ring groove",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    side = place_view(adapter, str(SOURCE), "*Right", *SIDE_CENTER, scale=VIEW_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    set_hidden_lines_removed(adapter, side)
    set_hidden_lines_removed(adapter, iso)

    annotations = curate_view_dimensions(
        adapter,
        side,
        keep=SIDE_KEEP,
        view_label="side",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    _assert_part_authored_text(adapter, annotations)
    _overall_reference(adapter, side)

    add_view_centerline(
        adapter,
        side,
        face_xy=CENTERLINE_PICK,
        label="MHA-PD-23 turning axis",
    )
    add_surface_finish(
        adapter,
        side,
        edge_xy=FINISH_PICK,
        symbol_xy=FINISH_SYMBOL,
        control=surface_finish_by_key(SURFACE_FINISHES, "journal"),
        label="MHA-PD-23 shank finish",
        entity_type="SILHOUETTE",
        char_height=0.0025,
    )
    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Transgear Pin Manufacturing Drawing",
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
