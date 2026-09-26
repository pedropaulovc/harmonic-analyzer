r"""Create the one-sheet Front/Right/Isometric channel assembly drawing (MHA-A02).

The sheet carries the rocker bank's fit-up steps (#743): the bank's end play is
set by a feeler at assembly, so the setting and its acceptance are shop
instructions this sheet must print (drawing-simplicity rule 6), generated from
``rocker_bank_layout`` and numbered by ``channel_assembly_steps``.
"""

from __future__ import annotations

import argparse
import sys
import textwrap
from typing import Any

import _config
import _telemetry
import channel_assembly_steps as steps
from _common import _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
)
from _drawing_registry import DRAWINGS_BY_NAME
from rocker_bank_layout import (
    COUNT,
    ROCKER_END_FEELER,
    ROCKER_END_PLAY,
    STACK_L20_ACCEPT,
)
from solidworks_mcp.adapters.solidworks.drawing import add_note, place_view


SPEC = DRAWINGS_BY_NAME["channel_assembly"]
ARTIFACT_STEM = SPEC.artifact_stem
SOURCE = SPEC.source
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"],
    pdf=SPEC.outputs["pdf"],
    png=SPEC.outputs["png"],
)
SLDDRW = OUTPUTS.slddrw
PDF = OUTPUTS.pdf
PNG = OUTPUTS.png

SHEET_SCALE = (1.0, 7.0)
FRONT_CENTER = (0.060, 0.150)
RIGHT_CENTER = (0.130, 0.150)
ISO_CENTER = (0.225, 0.140)

# The steps fill the empty field right of the isometric (x ~0.248 on the v36
# render) and above the title block: the note's top-left corner, then the
# right border and the lowest y the text may reach.
FITUP_NOTE_XY = (0.268, 0.252)
FITUP_FIELD_LIMIT = (0.412, 0.085)
FITUP_LINE_WIDTH = 50  # characters; default-format note text


def _fitup_steps() -> str:
    # Literal stems, so the config-dependency analysis reads exactly these rows.
    arm = _config.parts("rocker-arm")["number"]
    shaft = _config.parts("pivot-shaft")["number"]
    bracket = _config.parts("pivot-bracket")["number"]
    washer = _config.parts("rocker-thrust-washer")["number"]
    support = _config.parts("rocker-arm-support")["number"]
    last = COUNT - 1
    play_low, play_high = ROCKER_END_PLAY
    stack_low, stack_high = STACK_L20_ACCEPT
    feeler_step = steps.step_number("south-bracket-feeler-set")
    text = {
        "rocker-stack-accepted": (
            f"STACK THE {COUNT} {arm} ROCKERS ON THE {shaft} SHAFT, HUB {last} "
            f"AGAINST ITS SHOULDER. HUB 0 SOUTH FACE TO HUB {last} NORTH FACE: "
            f"{stack_low:.2f} TO {stack_high:.2f}; RE-FACE A LONG STACK."
        ),
        "north-ear-datum": (
            f"THE NORTH {bracket} IS SET AT {steps.FITUP_DRAWING_NUMBER} FIT-UP. "
            "ITS EAR IS THE BANK'S AXIAL DATUM: PUSH THE SHAFT SHOULDER "
            "AGAINST IT."
        ),
        "south-washer-fitted": f"SLIP THE {washer} WASHER ON AGAINST HUB 0.",
        "south-bracket-feeler-set": (
            f"SET THE SOUTH {bracket} WITH A {ROCKER_END_FEELER:.2f} FEELER "
            "BETWEEN THE WASHER AND ITS EAR, BANK PUSHED NORTH. CLAMP IT, "
            f"TRANSFER ITS SEATS INTO THE {support} RAIL, SCREW IT DOWN AT THE "
            "FEELER, THEN PULL THE FEELER."
        ),
        "end-play-accepted": (
            f"ACCEPT: BANK END PLAY {play_low:.2f} TO {play_high:.2f} BY "
            f"FEELER. OUTSIDE IT, REPEAT STEP {feeler_step}."
        ),
    }
    lines = ["ROCKER BANK FIT-UP"]
    for key in steps.SEQUENCE:
        lines += textwrap.wrap(
            text[key],
            width=FITUP_LINE_WIDTH,
            initial_indent=f"{steps.step_number(key)}. ",
            subsequent_indent="   ",
        )
    return "\n".join(lines)


FITUP_STEPS = _fitup_steps()


def _place_fitup_steps(adapter: Any, sheet: Any) -> None:
    """A sheet-owned note: activate the sheet so no view owns it."""
    ddoc = _early_bound(adapter.currentModel, "IDrawingDoc")
    name = str(_early_bound(sheet, "ISheet").GetName() or "")
    if not ddoc.ActivateSheet(name):
        raise RuntimeError(f"failed to activate drawing sheet {name!r}")
    note = add_note(adapter, FITUP_STEPS, *FITUP_NOTE_XY)
    if note is None:
        raise RuntimeError("failed to place the rocker-bank fit-up steps")
    printed = str(_early_bound(note, "INote").GetText() or "")
    if printed.replace("\r\n", "\n").replace("\r", "\n") != FITUP_STEPS:
        raise RuntimeError(f"fit-up steps printed as {printed!r}")


@_telemetry.traced("drawing.channel_assembly")
async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source assembly is missing: {SOURCE}")

    check("open assembly drawing source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
        ),
        required=(
            "Number",
            "Revision",
            "Material Specification",
            "Finish",
            "Quantity",
        ),
    )
    _model, sheet = new_project_drawing(adapter, layout=SPEC.layout, scale=SHEET_SCALE)
    for view_name, center in (
        ("*Front", FRONT_CENTER),
        ("*Right", RIGHT_CENTER),
        ("*Isometric", ISO_CENTER),
    ):
        place_view(adapter, str(SOURCE), view_name, *center, scale=SHEET_SCALE)
    _place_fitup_steps(adapter, sheet)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        layout=SPEC.layout,
        pdf_title="Channel Assembly Drawing",
        scale=SHEET_SCALE,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[ARTIFACT_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
