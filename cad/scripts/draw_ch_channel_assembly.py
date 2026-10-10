r"""Create the one-sheet Front/Right/Isometric channel assembly drawing (MHA-CH-000).

The sheet carries the rocker bank's fit-up steps (#948 ruling R, PR #1292): the
south bracket is set off a wave disc spring that preloads the bank north, so the
setting and its acceptance are shop instructions this sheet must print
(drawing-simplicity rule 6), generated from ``rocker_bank_layout`` and numbered
by ``channel_assembly_steps``.
"""

from __future__ import annotations

import argparse
import sys
import textwrap
from typing import Any

import _config
import _telemetry
import ch_channel_assembly_steps as steps
from _common import _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    ViewRole,
    apply_view_configuration,
    assert_full_detail_view,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
)
from _drawing_registry import DRAWINGS_BY_NAME
from ch_pivot_shaft_spec import DOME_HEIGHT
from rocker_bank_layout import (
    COUNT,
    PLAIN_END_CUT_BAND,
    ROCKER_SPRING_SET,
    STACK_L20_ACCEPT,
)
from solidworks_mcp.adapters.solidworks.drawing import add_note, place_view


SPEC = DRAWINGS_BY_NAME["ch_channel_assembly"]
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
    arm = _config.parts("ch-rocker-arm")["number"]
    rod = _config.parts("ch-connecting-rod")["number"]
    pin = _config.parts("ch-rod-pivot-pin")["number"]
    shaft = _config.parts("ch-pivot-shaft")["number"]
    bracket = _config.parts("ch-pivot-bracket")["number"]
    washer = _config.parts("ch-rocker-thrust-washer")["number"]
    spring = _config.parts("vn-rocker-bank-spring")["number"]
    support = _config.parts("fr-rocker-arm-support")["number"]
    last = COUNT - 1
    stack_low, stack_high = STACK_L20_ACCEPT
    set_step = steps.step_number("south-bracket-spring-set")
    north_step = steps.step_number("north-ear-datum")
    # The pivot shaft is supplied long, its plain end uncut (pivot_shaft_spec):
    # the cylinder ends PLAIN_END_CUT_BAND past the south ear's outer face and
    # the dome stands DOME_HEIGHT beyond that, so the saw cut sits that far
    # past a scribe on the ear face. The shoulder cannot pass either ear or a
    # hub bore, and the arms are held at their stations by their pinned rods,
    # so the shaft goes in and comes out only northward, body first, with the
    # north bracket lifted off its seats (Main's ruling, option i).
    cut_low, cut_high = (DOME_HEIGHT + band for band in reversed(PLAIN_END_CUT_BAND))
    text = {
        # The rings are captured in the closed cam slots as the cylinder stack
        # goes together, and the pressed pin needs its far tine backed on the
        # press, so each rod + arm pair is pinned at the bench before that step -- and
        # after the hub stack is proved on the shaft, while the arms are loose.
        "rocker-stack-accepted": (
            f"STACK THE {COUNT} {arm} ROCKERS ON THE {shaft} SHAFT, HUB {last} "
            f"AGAINST ITS SHOULDER. HUB 0 SOUTH FACE TO HUB {last} NORTH FACE: "
            f"{stack_low:.2f} TO {stack_high:.2f}; RE-FACE A LONG STACK. SLIDE "
            "THE ROCKERS OFF IN ORDER AND KEEP THAT ORDER."
        ),
        "rod-forks-pinned": (
            f"BEFORE {steps.CYLINDER_STACK_REF}, AT THE BENCH: PIN EACH {rod} "
            f"ROD FORK TO ITS {arm} ARM WITH ONE {pin}. PRESS IT IN, FAR TINE "
            "BACKED; DRESS BOTH ENDS FLUSH. PIN REMOVABLE WITH PUNCH. "
            "ACCEPT IF THE ARM SWINGS FREE UNDER ITS OWN WEIGHT."
        ),
        "north-ear-datum": (
            f"BASE ON THE MILL, DRO ZEROED, NORTH {bracket} LIFTED "
            f"OFF AT {steps.NORTH_BRACKET_SET_REF}: SWING EACH ARM UP "
            f"ON ITS ROD AND THREAD THE {shaft} SHAFT, BODY FIRST FROM THE "
            f"NORTH, THROUGH HUBS {last} TO 0 IN ORDER. SLIDE THE {bracket} "
            "EAR SOUTH OVER THE NORTH JOURNAL, SCREW IT DOWN AND RECHECK ITS "
            f"S-OFFSET Y AS {steps.NORTH_BRACKET_SET_REF}."
        ),
        "south-washer-fitted": f"SLIP THE {washer} WASHER ON AGAINST HUB 0.",
        "south-bracket-spring-set": (
            f"RUN A {spring} SPRING ALONG THE {shaft}; REJECT ONE THAT BINDS. "
            f"FIT IT ON. SET THE SOUTH {bracket} OFF THE WASHER ON A "
            f"{ROCKER_SPRING_SET:.2f} BLADE BESIDE THE SPRING, BANK PUSHED NORTH. "
            f"CLAMP, TRANSFER ITS SEAT INTO THE {support} RAIL, SCREW DOWN, "
            "PULL THE BLADE."
        ),
        "shaft-cut-to-fit": (
            f"SHOULDER PUSHED NORTH, SCRIBE THE {shaft} SHAFT AT THE SOUTH "
            f"EAR'S OUTER FACE. UNSCREW THE NORTH {bracket} AND SLIDE IT OFF "
            "NORTH; DRAW THE SHAFT NORTH OUT OF THE HUBS, EACH ARM LEFT "
            "HANGING ON ITS ROD; CATCH WASHER AND SPRING. CUT THE PLAIN END "
            f"{cut_low:.1f} TO {cut_high:.1f} PAST THE SCRIBE AND DOME IT "
            f"{DOME_HEIGHT:.1f}. REFIT AS STEP {north_step}, WASHER AND SPRING "
            f"THREADED ON PAST HUB 0; SOUTH EAR AT ITS STEP {set_step} SETTING."
        ),
        "preload-accepted": (
            "ACCEPT: PUSHED SOUTH, BANK AND SHAFT SPRING BACK ONTO THE NORTH "
            f"EAR. ELSE REPEAT STEP {set_step}."
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
        view = place_view(adapter, str(SOURCE), view_name, *center, scale=SHEET_SCALE)
        # The isometric is the drawing's full-detail view.
        role = ViewRole.FULL_DETAIL if view_name == "*Isometric" else ViewRole.PLAIN
        apply_view_configuration(adapter, view, role=role, label=f"channel {view_name}")
    assert_full_detail_view(adapter, label="channel assembly")
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
