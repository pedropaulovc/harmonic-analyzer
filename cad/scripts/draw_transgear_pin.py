r"""Create the MHA-179 transgear pin manufacturing drawing.

The SLDPRT remains authoritative.  A turned pin carries no datum and no
geometric-control frame (policy rule 3): the ground shank keeps its native
fit band and one bearing-surface finish, the MHA-182 ring groove its
catalogue Ø and width bands, and every other size is an ordinary model
dimension at its part-authored places.

The pin axis is model +Z, so the ``*Right`` view lays it horizontal as it
sits in the lathe: model +Z runs to paper-LEFT, putting the domed tip on the
left and the head on the right.  Every feature is visible, so the side view
removes hidden lines.  The head's underside (its seat on the MHA-164 arm) is
the one origin: the groove's load wall, the pin's functional station, is
dimensioned from it, and the head land runs back from it.

Run with SolidWorks open::

    uv run python cad\scripts\draw_transgear_pin.py transgear-pin
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_property_linked_note,
    add_surface_finish,
    add_view_centerline,
    assert_imported_precision,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_hidden_lines_removed,
    stamp_drawing_summary,
)
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _surface_finish import surface_finish_by_key
from transgear_pin_spec import (
    DIA,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    FRONT_LAND,
    GROOVE_CALLOUT,
    GROOVE_REAR_STATION,
    GROOVE_STATION,
    HEAD_DIA,
    HEAD_HEIGHT,
    HEAD_LAND,
    LENGTH,
    SURFACE_FINISHES,
)
from solidworks_mcp.adapters.solidworks.drawing import place_view

SPEC = DRAWINGS_BY_NAME["transgear_pin"]
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
# the 52.35 pin 157 mm long and the 0.737 groove 2.2 mm wide.
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
# groove's load wall), the front land off that wall, and the head land off
# the seat with its text right of the head.  The groove width hangs between
# the row and the profile, its text toward the head, clear of the station's
# extension lines.  The diameters stand above the profile, each on its own
# section; the groove Ø carries the ring's name above its value.
_ROW_Y = SIDE_CENTER[1] - 0.030
SIDE_KEEP = {
    "GrooveStation": ((SEAT_X + LOAD_WALL_X) / 2.0, _ROW_Y),
    "FrontLand": (FRONT_END_X - 0.010, _ROW_Y),
    "HeadLand": (HEAD_APEX_X + 0.010, _ROW_Y),
    "GrooveWidth": (GROOVE_MID_X + 0.016, SIDE_CENTER[1] - 0.016),
    "HeadDia": (HEAD_LAND_MID_X, HEAD_TOP_Y + 0.010),
    "ShankDia": (SHANK_MID_X, SHANK_TOP_Y + 0.012),
    # High enough that its shoulder, as wide as the ring callout, runs over
    # the shank Ø's +0.000 (at +0.020 the shoulder ended under it).
    "GrooveDia": (GROOVE_MID_X, SHANK_TOP_Y + 0.028),
    "HeadDomeR": (HEAD_APEX_X + 0.012, SIDE_CENTER[1] + 0.006),
    "TipDomeR": (TIP_X - 0.012, SIDE_CENTER[1] - 0.016),
}
# One line only: SolidWorks keeps an above-callout holding a line break but
# never prints it (drive collar, farm run 20261001T151531763Z).
DIMENSION_CALLOUTS_ABOVE = {"GrooveDia": GROOVE_CALLOUT}
# The shank's upper silhouette, between the shank Ø's tolerance stack and the
# head Ø (at 30 mm left of the seat its leader touched the -0.008).
FINISH_PICK = (SEAT_X - 0.015, SHANK_TOP_Y)
FINISH_SYMBOL = (SEAT_X - 0.015, SHANK_TOP_Y + 0.008)
# A point on the shank face, clear of the Ø dimension line.
CENTERLINE_PICK = (SHANK_MID_X + 0.010, SIDE_CENTER[1] + 0.001)
ISO_NOTE_XY = (ISO_CENTER[0] - 0.030, ISO_CENTER[1] - 0.040)
NOTES_XY = (0.016, 0.070)


def _printable_above_callouts(callouts: dict[str, str]) -> dict[str, str]:
    """The above-callouts, refused if any holds a line break (it would not print)."""
    broken = sorted(name for name, text in callouts.items() if "\n" in text)
    if broken:
        raise RuntimeError(f"above-callouts with a line break do not print: {broken}")
    return callouts


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
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Transgear Pin Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "transgear pin; turned and ground steel; ring groove",
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
    set_dimension_callouts(
        adapter,
        annotations,
        _printable_above_callouts(DIMENSION_CALLOUTS_ABOVE),
        location="above",
    )

    add_view_centerline(
        adapter,
        side,
        face_xy=CENTERLINE_PICK,
        label="MHA-179 turning axis",
    )
    add_surface_finish(
        adapter,
        side,
        edge_xy=FINISH_PICK,
        symbol_xy=FINISH_SYMBOL,
        control=surface_finish_by_key(SURFACE_FINISHES, "journal"),
        label="MHA-179 shank finish",
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
