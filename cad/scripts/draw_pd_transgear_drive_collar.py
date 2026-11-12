r"""Create the manufacturing drawing for the transgear drive collar (MHA-PD-22).

The end view shows the round bore, the two axial drive holes and the flat
pin's hole.  An axial section through the flat pin's hole shows that blind
ream, the turned diameters and the fitted body/pilot lengths.  The saved
body dimension is REF; its linked assembly step faces the actual rear
reaction face on F.
No roughness symbol is added to these clamp faces (drawing-guidelines.md rule 6 (roughness symbols only where a surface runs, slides or locates)).
"""

from __future__ import annotations

import argparse
import math
import sys
import textwrap
from typing import Any

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    auto_center_marks,
    dimension_name,
    place_view,
)

from _check import check
from _com import _early_bound
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    stamp_drawing_summary,
)
from _drawing_dimension_import import curate_view_dimensions
from _drawing_dimensions import (
    assert_imported_precision,
    set_dimension_callouts,
    set_reference_dimension,
)
from _drawing_edge_dimensions import add_edge_dimension
from _drawing_notes import add_property_linked_note, property_link
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_sections import create_section_view
from _drawing_view_display import set_hidden_lines_removed
from _machinist_review_mode import MachinistReviewMode
from _paths import CAD_ROOT
from _part_properties import part_drawing_unit
from _section_axis import position_section_caption
from _session import run_build
import _config
import _telemetry
from pd_paper_drive_assembly_steps import step_ref
from pd_transgear_drive_collar_spec import (
    BODY_SUPPLY_NOTE,
    BORE_CALLOUT,
    BORE_DIA,
    DOWEL_NUMBER,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION_BY_NAME,
    DRAWING_REFERENCE_PRECISION,
    FLAT_PIN_CENTRE,
    FLAT_PIN_FLOOR,
    FLAT_PIN_HOLE_CALLOUT,
    FLAT_PIN_HOLE_CALLOUT_ABOVE,
    FLAT_PIN_HOLE_SUFFIX,
    LENGTH,
    OD,
    OVERALL_LENGTH,
    PILOT_SUPPLY_NOTE,
    PILOT_DIA,
    PILOT_LENGTH,
    PIN_CIRCLE_RADIUS,
    REAR_BREAK_CALLOUT,
    REAR_BREAK_SUFFIX,
    SPROCKET_NUMBER,
)

# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["pd_transgear_drive_collar"]
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

# 4:1 exposes the .0615 flat-pin ream in section and both axial dowel holes.
SHEET_SCALE = (4.0, 1.0)
VIEW_SCALE = (4, 1)
_S = SHEET_SCALE[0] / SHEET_SCALE[1]
# 5 mm left of the sheet's middle-left: the section's flat-pin size block,
# its 26-character mate row ending at its dimension line by the rear face,
# needs that room clear of the end view's outline.
END_CENTER = (0.095, 0.165)
SIDE_CENTER = (0.235, END_CENTER[1])
# Right of the section, clear of the outside diameter's mate callout.
ISO_CENTER = (0.380, END_CENTER[1])
ISO_SCALE = (2, 1)
HALF_OD = OD * _S / 2000.0
HALF_PILOT = PILOT_DIA * _S / 2000.0
PIN_R = PIN_CIRCLE_RADIUS * _S / 1000.0
# The section is turned to the same frame as *Right: rear left, pilot right,
# +Y up. Its ink is centred on the full turned body's bounding box.
_SEAT_X = SIDE_CENTER[0] + (LENGTH - PILOT_LENGTH) * _S / 2000.0
_REAR_X = _SEAT_X - LENGTH * _S / 1000.0
_PILOT_X = _SEAT_X + PILOT_LENGTH * _S / 1000.0
# SolidWorks draws a diameter's leader from the shoulder under its last
# callout line THROUGH the circle's centre to the far rim (farm run
# 20261009T224545531Z: the bore's leader from above crossed the upper pin
# hole, and the pin's from below crossed the bore). So each text stands where
# that whole line is clear: the bore's up and right of the end view, above
# section line A's arrow, its mate lines hanging toward the bore; the
# dimensioned (+Y) pin hole's up and left of that hole, outside the part.
# Each pin location reads left of the view, its text toward the outer witness
# so its mate lines stay between the witnesses and clear of the rim. The -Y
# text's top line stands clear under the axis, where the +Y dimension line
# starts (run 20261031T205208603Z: that line struck it).  The bore's leader
# from up and right leaves the bore lower left, clear of the flat pin's hole
# straight below the axis.
_BORE_TEXT_HALF = 0.017
_PIN_TEXT_HALF = 0.022
END_KEEP = {
    "BoreDia": (END_CENTER[0] + 0.048 + _BORE_TEXT_HALF, END_CENTER[1] + 0.063),
    "PinPosDia": (END_CENTER[0] - 0.018 - _PIN_TEXT_HALF, END_CENTER[1] + 0.061),
    "PinPosY": (END_CENTER[0] - HALF_OD - 0.025, END_CENTER[1] + PIN_R * 0.65),
    "PinNegY": (END_CENTER[0] - HALF_OD - 0.025, END_CENTER[1] - PIN_R * 0.35 - 0.006),
}
# SolidWorks put "SECTION A-A / SCALE 4:1" just under the section, where the
# fitted-length row's dimension line (about 11 mm under the view, under its
# two-line text) ran through "SECTION" (machinist review of bcdc09b35): the
# caption, top-centre anchored, now stands 25 mm under the view, clear of
# that line and above the notes block. The two
# fitted lengths share one row just under the section, each with only a
# pointer to its sheet note: the pilot's text right of its short span, the
# body's left of the rear witness, which struck it inside its own span
# (baseline run 20261031T145011192Z). The overall reference reads above
# the section. Both diameters read right of the pilot face, each mate
# callout clear of the other.
#
# The flat pin's ream lies below the axis.  Its floor station reads on its
# own row between the section and the fitted-length row (both drop 6 mm to
# make room), its witnesses running down from the seat-face origin and the
# floor; its text stands outside left of that 9 mm span, between the floor's
# and the rear face's witnesses (run 20261111T212425353Z: centred in the span
# it reached the seat-face witness).  Its size reads left of the rear face,
# its one-line process over the value, its REF depth after the value and two
# mate rows under it, the whole block ending at its dimension line
# (SOLIDWORKS sets a vertical dimension's outside text there, run
# 20261111T234324465Z), clear of the end view; that line stands 2 mm short of
# where the size's witnesses start, room for the 26-character mate row.  The
# centre's span crosses the size's, so the centre's dimension line stands in
# the 4 mm between the rear face and where the size's witnesses start (the ream's
# sketch runs 1 mm past the face): neither crosses the other's witness (run
# 20261111T212425353Z: the line struck the size's).  Its text reads outside
# its span above the axis, under the rear break's witnesses.
#
# The rear mouth's break leg reads on one line, its angle as the suffix, up
# and left of the +Y mouth, its two mate rows under it, the block ending at
# its dimension line as it rises in air left of the rear face, under the
# overall reference's row and clear of its rear witness; that line's lower
# arrow runs down past its span, so it stands 4 mm clear of the centre's
# text (run 20261111T234324465Z: the arrow touched ".118").
_LENGTH_ROW_Y = SIDE_CENTER[1] - HALF_OD - 0.012
SECTION_CAPTION_XY = (SIDE_CENTER[0], SIDE_CENTER[1] - HALF_OD - 0.025)
_FLAT_PIN_Y = SIDE_CENTER[1] - FLAT_PIN_CENTRE * _S / 1000.0
_BORE_EDGE_Y = SIDE_CENTER[1] + BORE_DIA * _S / 2000.0
_FLAT_PIN_FLOOR_X = _SEAT_X - FLAT_PIN_FLOOR * _S / 1000.0
# The ream's sketch line ends 1 mm (build_pd_transgear_drive_collar._OVERRUN)
# past the rear face, where the size's witnesses start.
_REAM_RUN_X = _REAR_X - 1.0 * _S / 1000.0
SIDE_KEEP = {
    "PilotLength": (_PILOT_X + 0.019, _LENGTH_ROW_Y),
    "CollarLength": (_REAR_X - 0.018, _LENGTH_ROW_Y),
    # 22 mm above the axis: round 1's OD text on the axis line ran into the
    # pilot's "CLEARS BORE" beside it; raised, it reads between the OD's
    # upper extension line and the pilot block's top.
    "CollarDia": (_PILOT_X + 0.069, SIDE_CENTER[1] + 0.022),
    "PilotDia": (_PILOT_X + 0.022, SIDE_CENTER[1]),
    "FlatPinFloor": ((_REAR_X + _FLAT_PIN_FLOOR_X) / 2.0, SIDE_CENTER[1] - HALF_OD - 0.005),
    "FlatPinCentre": (_REAR_X - 0.0025, SIDE_CENTER[1] + 0.006),
    "FlatPinDia": (_REAR_X - 0.007, _FLAT_PIN_Y - 0.006),
    "RearBreak": (_REAR_X - 0.029, _BORE_EDGE_Y + 0.015),
}
OVERALL_TEXT_XY = ((_REAR_X + _SEAT_X) / 2.0, SIDE_CENTER[1] + HALF_OD + 0.010)
# Physical annular end-face picks, inside the pilot and clear of the bore.
# The rear-face bore edge is air, not a length witness.
_OVERALL_PICK_Y = SIDE_CENTER[1] + PILOT_DIA * 3.0 * _S / 8000.0
OVERALL_PICKS = ((_PILOT_X, _OVERALL_PICK_Y), (_REAR_X, _OVERALL_PICK_Y))
# The pilot is supplied long and faced at assembly, and the body's rear face
# is faced on F; each fitted band and its assembly step is a numbered sheet
# note, continuing the part's note 1, and its length points at it.
FIT_STEP_KEY = "pilot-faced-to-fit"
BODY_FIT_STEP_KEY = "collar-rear-faced-to-fit"
_NOTE_WIDTH = 70


def _numbered(number: int, text: str) -> str:
    return "\n".join(
        textwrap.wrap(
            f"{number}. {text}",
            width=_NOTE_WIDTH,
            subsequent_indent="   ",
            break_on_hyphens=False,
        )
    )


# The part's own notes come first (Manufacturing Notes); the drawing's
# fitted-length notes continue their numbering.
PILOT_NOTE = len(DRAWING_NOTES.splitlines()) + 1
BODY_NOTE = PILOT_NOTE + 1
FIT_NOTES = "\n".join(
    (
        _numbered(PILOT_NOTE, f"{PILOT_SUPPLY_NOTE}, PER {step_ref(FIT_STEP_KEY)}."),
        _numbered(BODY_NOTE, f"{BODY_SUPPLY_NOTE}, PER {step_ref(BODY_FIT_STEP_KEY)}."),
    )
)
# The #25 chain the O.D. clears, by its drawing number (rule 4).
CHAIN_NUMBER = _config.parts("sh-vn-chain-link")["number"]
# Rule 7: a callout carries its size and process lines plus at most two lines
# of words, and a location dimension carries only its value and band.  The
# dowel pattern names the dowel and the sprocket its pins locate once, on its
# 2X callout; each mate is named by drawing number (rule 4): the bore's
# sliding fit on the shaft's D-core, the flat pin pressed in its ream for
# good, the two one permanent pair, and the rear break clearing the shaft's
# root corner.
DIMENSION_CALLOUTS_BELOW = {
    "BoreDia": BORE_CALLOUT,
    "PinPosDia": f"2X REAM THRU\nPRESS FIT, DOWEL {DOWEL_NUMBER}\nPINS LOCATE {SPROCKET_NUMBER}",
    "PilotDia": f"CLEARS BORE\nOF {SPROCKET_NUMBER}",
    "CollarDia": f"CLEARS CHAIN {CHAIN_NUMBER}\nON 12-TOOTH {SPROCKET_NUMBER}",
    "PilotLength": f"SEE NOTE {PILOT_NOTE}",
    "CollarLength": f"SEE NOTE {BODY_NOTE}",
    "FlatPinDia": FLAT_PIN_HOLE_CALLOUT,
    "RearBreak": REAR_BREAK_CALLOUT,
}
DIMENSION_CALLOUTS_ABOVE = {"FlatPinDia": FLAT_PIN_HOLE_CALLOUT_ABOVE}
DIMENSION_SUFFIXES = {"RearBreak": REAR_BREAK_SUFFIX, "FlatPinDia": FLAT_PIN_HOLE_SUFFIX}

ISO_NOTE_XY = (ISO_CENTER[0] - 0.030, ISO_CENTER[1] - 0.040)
# The part's note, then the drawing's two fitted-length notes, in one
# block; the actual fit procedure is linked to its assembly step.
NOTES_XY = (0.016, 0.085)
NOTES_TEXT = f"{property_link('Manufacturing Notes')}\n{FIT_NOTES}"


def _set_dimension_suffixes(
    adapter: Any, annotations: list[Any], suffixes: dict[str, str]
) -> None:
    """Append each named dimension's suffix to its value on the same line
    (draw_dt_crankshaft's).  ``SetText`` reports nothing, so each suffix is
    read back."""
    remaining = dict(suffixes)
    for annotation in annotations:
        name = dimension_name(adapter, annotation)
        text = remaining.pop(name, None)
        if text is None:
            continue
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        display.SetText(2, text)  # swDimensionTextSuffix
        applied = str(display.GetText(2) or "")
        if applied.replace("\r", "") != text:
            raise RuntimeError(f"{name}: suffix did not persist: {applied!r}")
    if remaining:
        raise RuntimeError(f"dimension suffixes not applied: {sorted(remaining)}")



def _section_frame(adapter: Any, view: Any) -> tuple[tuple[float, float], ...]:
    origin = model_point_in_view(adapter, view, (0.0, 0.0, 0.0), label="collar seat")
    rear = model_point_in_view(
        adapter, view, (0.0, 0.0, LENGTH / 1000.0), label="collar rear F reaction"
    )
    north = model_point_in_view(adapter, view, (0.0, 0.001, 0.0), label="collar +Y")
    return origin, (rear[0] - origin[0], rear[1] - origin[1]), (
        north[0] - origin[0], north[1] - origin[1]
    )


def _orient_section(adapter: Any, view: Any) -> None:
    native = _early_bound(view, "IView")
    cut = native.GetSection()
    if cut is None:
        raise RuntimeError("collar section has no native cutting direction")
    cut = _early_bound(cut, "IDrSection")
    _, rear, north = _section_frame(adapter, native)
    if rear[0] * north[1] - rear[1] * north[0] > 0.0:
        reversed_cut = cut.GetReversedCutDirection() is not True
        cut.SetReversedCutDirection(reversed_cut)  # VT_VOID; read back.
        rebuild_drawing(adapter, label="collar section cut reversed")
        if cut.GetReversedCutDirection() is not reversed_cut:
            raise RuntimeError("collar section cutting direction did not persist")
        _, rear, north = _section_frame(adapter, native)
    native.Angle = float(native.Angle) + math.pi - math.atan2(rear[1], rear[0])
    rebuild_drawing(adapter, label="collar section axis across")
    _, rear, north = _section_frame(adapter, native)
    if rear[0] >= 0.0 or abs(rear[1]) > 1e-8 or north[1] <= 0.0 or abs(north[0]) > 1e-8:
        raise RuntimeError(f"collar section has the wrong physical frame: {rear=}, {north=}")
    outline = tuple(float(v) for v in native.GetOutline())
    position = tuple(float(v) for v in native.Position)
    centre = ((outline[0] + outline[2]) / 2.0, (outline[1] + outline[3]) / 2.0)
    moved = [position[i] + SIDE_CENTER[i] - centre[i] for i in (0, 1)]
    if native.SetViewPosition(double_array(moved), False) is not True:
        raise RuntimeError("collar section could not be centred")
    rebuild_drawing(adapter, label="collar section centred")
    seat, _, _ = _section_frame(adapter, native)
    if math.dist(seat, (_SEAT_X, SIDE_CENTER[1])) > 1e-5:
        raise RuntimeError(f"collar section seat {seat} does not match the source frame")


def _overall_reference(adapter: Any, side: Any) -> None:
    """The unbanded overall, pilot front face to actual rear face (drawing-guidelines.md rule 10 (dimension from a real feature))."""
    label = "drive-collar overall length reference"
    display = add_edge_dimension(
        adapter,
        side,
        p0=OVERALL_PICKS[0],
        p1=OVERALL_PICKS[1],
        text_xy=OVERALL_TEXT_XY,
        label=label,
        orientation="horizontal",
    )
    display = _early_bound(display, "IDisplayDimension")
    dimension = display.GetDimension2(0)
    if dimension is None:
        raise RuntimeError(f"{label} has no native dimension")
    dimension = _early_bound(dimension, "IDimension")
    measured_mm = abs(float(dimension.SystemValue) * 1000.0)
    if abs(measured_mm - OVERALL_LENGTH) > 1e-4:
        raise RuntimeError(
            f"{label} measured {measured_mm:g}, expected {OVERALL_LENGTH:g}"
        )
    annotation = display.GetAnnotation()
    if annotation is None:
        raise RuntimeError(f"{label} has no native annotation")
    set_reference_dimension(adapter, annotation, label=label)
    status = display.SetPrecision3(DRAWING_REFERENCE_PRECISION, -1, -1, -1)
    if int(status) != 0:
        raise RuntimeError(f"{label} precision setter failed with {status}")
    if int(display.GetPrimaryPrecision2()) != DRAWING_REFERENCE_PRECISION:
        raise RuntimeError(f"{label} precision did not persist")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open drive collar source", await adapter.open_model(str(SOURCE)))
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
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout,
        unit=part_drawing_unit(PART_STEM),
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Transgear Drive Collar Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "transgear drive collar; round bore, pressed flat pin; fitted rear reaction face",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    end = place_view(adapter, str(SOURCE), "*Back", *END_CENTER, scale=VIEW_SCALE)
    side = create_section_view(
        adapter, end,
        line_start=(END_CENTER[0], END_CENTER[1] - HALF_OD - 0.005),
        line_end=(END_CENTER[0], END_CENTER[1] + HALF_OD + 0.005),
        view_xy=SIDE_CENTER, section_label="A", scale=VIEW_SCALE,
        label="collar axial flat-pin section",
    )
    _orient_section(adapter, side)
    position_section_caption(
        adapter, side, SECTION_CAPTION_XY, label="collar section A-A"
    )
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (end, side, iso):
        set_hidden_lines_removed(adapter, view)

    end_annotations = curate_view_dimensions(
        adapter,
        end,
        keep=END_KEEP,
        view_label="end",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    side_annotations = curate_view_dimensions(
        adapter,
        side,
        keep=SIDE_KEEP,
        view_label="side",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    annotations = [*end_annotations, *side_annotations]
    # Decimal places (and so the general-tolerance row each dimension claims)
    # are authored on the part; the sheet only proves the import kept them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    set_dimension_callouts(
        adapter, annotations, DIMENSION_CALLOUTS_BELOW, location="below"
    )
    set_dimension_callouts(
        adapter, annotations, DIMENSION_CALLOUTS_ABOVE, location="above"
    )
    _set_dimension_suffixes(adapter, annotations, DIMENSION_SUFFIXES)
    _overall_reference(adapter, side)
    if not auto_center_marks(adapter, end, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to the collar end view")
    if add_note(adapter, NOTES_TEXT, *NOTES_XY) is None:
        raise RuntimeError("failed to add the collar's numbered sheet notes")
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Transgear Drive Collar Manufacturing Drawing",
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
