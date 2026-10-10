r"""Create the one-sheet Front/Right/Isometric channel assembly drawing (MHA-CH-000).

The sheet carries the rocker bank's fit-up steps (#948 ruling R, PR #1292): the
south bracket is set off a wave disc spring that preloads the bank north, and
the plain pivot shaft is cut to fit and held by a set screw in each ear (user,
2026-10-10), so the setting and its acceptance are shop instructions this sheet
must print (drawing-simplicity rule 6), generated from ``rocker_bank_layout``
and numbered by ``channel_assembly_steps``. The fulcrum shaft's keepers follow
in a second block, numbered on from the first: their bench pair-ream, their
DRO fit-up on the top frame and the set screws' staking
(``ch_fulcrum_keeper_spec``).
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
from ch_pivot_bracket_spec import SET_SCREW_ENGAGEMENT_ASSEMBLY_FACT
from ch_fulcrum_keeper_spec import (
    KEEPER_FITUP_LOCATION_BAND_MM,
    KEEPER_FITUP_PLACES,
    KEEPER_FITUP_X_FROM_WEB_MM,
    KEEPER_INNER_FACE_FROM_FRONT_SOCKET_MM,
    KEEPER_INNER_FACE_SPAN_MM,
    PAIR_REAMER_DIA_IN,
    PAIR_REAMER_OAL_IN,
)
from channel_frame_geom import LEVER_FULCRUM_XY
from ch_pivot_shaft_spec import DOME_HEIGHT
from frame_column_stations import COLUMN_X
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

# The rocker-bank steps fill the empty field right of the isometric (x ~0.248
# on the v36 render) and above the title block: the note's top-left corner,
# then the right border and the lowest y the text may reach.
FITUP_NOTE_XY = (0.268, 0.252)
FITUP_FIELD_LIMIT = (0.412, 0.085)
FITUP_LINE_WIDTH = 50  # characters; default-format note text
# The fulcrum-shaft steps fill the band under the front and right views
# (lowest at y ~0.079 on the v41 render), left of the title block (x ~0.218)
# and above the bottom border (y ~0.013).
FULCRUM_NOTE_XY = (0.016, 0.075)
FULCRUM_FIELD_LIMIT = (0.214, 0.016)
FULCRUM_LINE_WIDTH = 70
FULCRUM_KEYS = (
    steps.KEEPERS_PAIR_REAMED_KEY,
    steps.KEEPERS_SET_KEY,
    steps.SET_SCREWS_STAKED_KEY,
)
# The second block numbers on from the first, so its steps close the sequence.
if steps.SEQUENCE[-len(FULCRUM_KEYS) :] != FULCRUM_KEYS:
    raise AssertionError("the fulcrum-shaft steps must close the sequence")


def _block(
    heading: str, keys: tuple[str, ...], text: dict[str, str], width: int
) -> str:
    lines = [heading]
    for key in keys:
        lines += textwrap.wrap(
            text[key],
            width=width,
            initial_indent=f"{steps.step_number(key)}. ",
            subsequent_indent="   ",
            # A part number never splits at its hyphens across two lines.
            break_on_hyphens=False,
        )
    return "\n".join(lines)


def _fitup_notes() -> tuple[str, str]:
    # Literal stems, so the config-dependency analysis reads exactly these rows.
    arm = _config.parts("ch-rocker-arm")["number"]
    rod = _config.parts("ch-connecting-rod")["number"]
    pin = _config.parts("ch-rod-pivot-pin")["number"]
    shaft = _config.parts("ch-pivot-shaft")["number"]
    bracket = _config.parts("ch-pivot-bracket")["number"]
    washer = _config.parts("ch-rocker-thrust-washer")["number"]
    spring = _config.parts("vn-rocker-bank-spring")["number"]
    set_screw = _config.parts("vn-arbor-set-screw")["number"]
    support = _config.parts("fr-rocker-arm-support")["number"]
    keeper = _config.parts("ch-fulcrum-keeper")["number"]
    fulcrum_shaft = _config.parts("ch-fulcrum-shaft")["number"]
    set_screw = _config.parts("vn-fulcrum-set-screw")["number"]
    foot_screw = _config.parts("vn-frame-side-screw")["number"]
    top_frame = _config.parts("fr-top-frame")["number"]
    last = COUNT - 1
    stack_low, stack_high = STACK_L20_ACCEPT
    set_step = steps.step_number("south-bracket-spring-set")
    north_step = steps.step_number("north-ear-datum")
    # The pivot shaft is supplied long, its plain end uncut (pivot_shaft_spec):
    # the cylinder ends PLAIN_END_CUT_BAND past the south ear's outer face and
    # the dome stands DOME_HEIGHT beyond that, so the saw cut sits that far
    # past a scribe on the ear face. The arms are held at their stations by
    # their pinned rods, so the plain rod goes in and comes out only through
    # the set north ear, uncut end first.
    cut_low, cut_high = (DOME_HEIGHT + band for band in reversed(PLAIN_END_CUT_BAND))
    # Each keeper lug is set off the top-frame rail web under it (its column's
    # socket axis) in X and off the frame's hole-station origin, the upper-left
    # socket, in Z (Main's ruling): the lug centre on the fulcrum line, its
    # inner face off the front socket line.
    places = KEEPER_FITUP_PLACES
    if abs(LEVER_FULCRUM_XY[0] - COLUMN_X - KEEPER_FITUP_X_FROM_WEB_MM) > 1e-9:
        raise AssertionError("KEEPER_FITUP_X_FROM_WEB_MM is off the fulcrum line")
    front_face, rear_face = KEEPER_INNER_FACE_FROM_FRONT_SOCKET_MM
    # The pair is reamed at the spacing STEP 9 sets it to (Main's ruling).
    ream_span = rear_face - front_face
    if abs(ream_span - KEEPER_INNER_FACE_SPAN_MM) > 1e-9:
        raise AssertionError("the pair-ream span is not the fit-up span")
    text = {
        # The rings are captured in the closed cam slots as the cylinder stack
        # goes together, and the pressed pin needs its far tine backed on the
        # press, so each rod + arm pair is pinned at the bench before that step -- and
        # after the hub stack is proved on the shaft, while the arms are loose.
        "rocker-stack-accepted": (
            f"STACK THE {COUNT} {arm} ROCKERS ON THE {shaft} SHAFT, CLOSED UP. "
            f"HUB 0 SOUTH FACE TO HUB {last} NORTH FACE: "
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
            f"NORTH {bracket} SET AT {steps.NORTH_BRACKET_SET_REF}: SWING "
            f"EACH ARM UP ON ITS ROD; PUSH THE {shaft} SHAFT, UNCUT END "
            f"FIRST, FLATS UP, SOUTH THROUGH THE EAR, ITS MICED {washer} AND "
            f"HUBS {last} TO 0."
        ),
        "south-washer-fitted": f"SLIP THE OTHER {washer} ON AGAINST HUB 0.",
        "south-bracket-spring-set": (
            f"RUN A {spring} SPRING ALONG THE {shaft}; REJECT ONE THAT BINDS. "
            f"FIT IT ON. SET THE SOUTH {bracket} OFF THE WASHER ON A "
            f"{ROCKER_SPRING_SET:.2f} BLADE BESIDE THE SPRING, BANK PUSHED NORTH. "
            f"CLAMP, TRANSFER ITS SEAT INTO THE {support} RAIL, SCREW DOWN, "
            "PULL THE BLADE."
        ),
        "shaft-cut-to-fit": (
            f"NORTH END FLUSH WITH ITS EAR, SCRIBE THE {shaft} AT THE SOUTH "
            "EAR'S OUTER FACE. DRAW IT OUT NORTH, EACH ARM LEFT HANGING ON "
            "ITS ROD; CATCH WASHERS AND SPRING. CUT THE PLAIN END "
            f"{cut_low:.1f} TO {cut_high:.1f} PAST THE SCRIBE AND DOME IT "
            f"{DOME_HEIGHT:.1f}. REFIT AS STEP {north_step}, WASHERS AND SPRING "
            f"IN PLACE; SOUTH EAR AT ITS STEP {set_step} SETTING."
        ),
        # Rule 9 waived for this joint only (joint_retention RULINGS
        # "U-MHA-VN-034-channel-threadlocker", user 2026-10-10).
        "set-screws-driven": (
            f"NORTH END FLUSH, FLATS UP: RUN ONE {set_screw} DOWN EACH APEX "
            "TAP ONTO ITS FLAT, NORTH FIRST, WITH LOCTITE 222; SNUG. "
            # Named exception: MHA-CH-008 set-screw engagement (drawing-simplicity-policy.md, "Named exceptions").
            f"{SET_SCREW_ENGAGEMENT_ASSEMBLY_FACT}"
        ),
        "preload-accepted": (
            "ACCEPT: PUSHED SOUTH, THE BANK SPRINGS BACK ONTO THE NORTH "
            f"WASHER. ELSE REPEAT STEP {set_step}."
        ),
        steps.KEEPERS_PAIR_REAMED_KEY: (
            f"CLAMP BOTH {keeper}, FEET OUTBOARD ON ONE FLAT, INNER LUG FACES "
            f"{ream_span:.{places}f} APART, BORE AXIS PARALLEL TO THE FLAT; "
            "DRILL AND REAM BOTH IN ONE PASS, "
            f"{PAIR_REAMER_OAL_IN:.0f} IN {PAIR_REAMER_DIA_IN:.4f} REAMER; ROUND "
            f"EACH CROWN ON ITS BORE. ACCEPT IF THE {fulcrum_shaft} SHAFT SLIDES "
            "FREELY THROUGH BOTH, CLAMPED."
        ),
        steps.KEEPERS_SET_KEY: (
            f"{top_frame} ON THE MILL: SHAFT THROUGH BOTH KEEPERS, FEET "
            "OUTBOARD ON THE RAIL. SET EACH LUG CENTRE "
            f"{KEEPER_FITUP_X_FROM_WEB_MM:.{places}f} WEST OF THE RAIL WEB "
            f"CENTRE BELOW IT, LUG INNER FACES AT Z {front_face:.{places}f} AND "
            f"{rear_face:.{places}f} FROM THE UPPER-LEFT SOCKET, EACH WITHIN "
            f"{KEEPER_FITUP_LOCATION_BAND_MM:.{places}f}. CLAMP; TRANSFER EACH "
            f"FOOT HOLE INTO THE RAIL, TAP AS {top_frame}, SCREW DOWN ONE "
            f"{foot_screw}."
        ),
        steps.SET_SCREWS_STAKED_KEY: (
            f"WITH THE LEVER BANK ON IT, SLIDE THE {fulcrum_shaft} SHAFT UNTIL "
            f"EACH FLAT LIES UNDER ITS CROWN TAP; TIGHTEN ONE {set_screw} SET "
            "SCREW ONTO EACH FLAT AND STAKE EACH TAP MOUTH AT 2 POINTS."
        ),
    }
    rocker_keys = tuple(key for key in steps.SEQUENCE if key not in FULCRUM_KEYS)
    return (
        _block("ROCKER BANK FIT-UP", rocker_keys, text, FITUP_LINE_WIDTH),
        _block("FULCRUM SHAFT FIT-UP", FULCRUM_KEYS, text, FULCRUM_LINE_WIDTH),
    )


FITUP_NOTES = _fitup_notes()
FITUP_STEPS = "\n".join(FITUP_NOTES)


def _place_fitup_steps(adapter: Any, sheet: Any) -> None:
    """Sheet-owned notes: activate the sheet so no view owns them."""
    ddoc = _early_bound(adapter.currentModel, "IDrawingDoc")
    name = str(_early_bound(sheet, "ISheet").GetName() or "")
    if not ddoc.ActivateSheet(name):
        raise RuntimeError(f"failed to activate drawing sheet {name!r}")
    for text, xy in zip(FITUP_NOTES, (FITUP_NOTE_XY, FULCRUM_NOTE_XY), strict=True):
        note = add_note(adapter, text, *xy)
        if note is None:
            raise RuntimeError(f"failed to place the fit-up steps at {xy}")
        printed = str(_early_bound(note, "INote").GetText() or "")
        if printed.replace("\r\n", "\n").replace("\r", "\n") != text:
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
