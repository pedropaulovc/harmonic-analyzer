r"""Create the manufacturing drawing for the transgear knob cup (MHA-PD-16).

The face view is the ``*Top`` orientation, looking into the ring from the
rear: it carries the source six-millimetre H7 bore, whose callout names the
MHA-PD-08 journal it slides on and the diametral clearance it keeps there.
A separate sheet note says the MHA-PD-VN-62 cross pin hole is not drilled
on this part: it is made through cup and journal together at assembly, at
the paper-drive step the note cites, so it is not dimensioned here.
Section A-A cuts it on the cup axis through the Front plane, the plane of
the turned profile, so the O.D. and the length print on solid cut edges.
The front face is the thrust face on the arm plate's rear boss (the rear
stop of the knob's end float) and carries its finish under a caption that
names that boss.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    auto_center_marks,
    place_view,
)

import _config
from _check import check
from _com import _early_bound
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    stamp_drawing_summary,
)
from _drawing_dimension_import import curate_view_dimensions
from _drawing_dimensions import assert_imported_precision, set_dimension_callouts
from _drawing_finish import add_surface_finish
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_sections import create_section_view
from _drawing_view_display import set_hidden_lines_removed
from _machinist_review_mode import MachinistReviewMode
from _paths import CAD_ROOT
from _session import run_build
from _surface_finish import surface_finish_by_key
import _telemetry
from pd_paper_drive_assembly_steps import step_ref
from pd_transgear_knob_cup_spec import (
    BORE_DIA,
    BORE_JOURNAL_CLEARANCE,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    LENGTH,
    OD,
    SURFACE_FINISHES,
)

# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE


SPEC = DRAWINGS_BY_NAME["pd_transgear_knob_cup"]
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

# A Ø19 x 8 ring: 4:1 keeps the section (76 x 32 mm on the sheet) and the
# two-line bore callout legible without crowding the landscape sheet.
SHEET_SCALE = (4.0, 1.0)
VIEW_SCALE = (4, 1)
_S = SHEET_SCALE[0] / SHEET_SCALE[1]
FACE_CENTER = (0.090, 0.170)
SECTION_CENTER = (0.200, FACE_CENTER[1])
ISO_CENTER = (0.330, FACE_CENTER[1])
# Half the cup's O.D. on the sheet, and the cutting line's overrun past it.
HALF_OD = OD * _S / 2000.0
SECTION_LINE_OVERRUN = 0.005
# Across the face view on the cup axis: sheet X is model X in *Top, so the
# cut is the Front plane, the plane of the turned profile.
SECTION_LINE = (
    (FACE_CENTER[0] - HALF_OD - SECTION_LINE_OVERRUN, FACE_CENTER[1]),
    (FACE_CENTER[0] + HALF_OD + SECTION_LINE_OVERRUN, FACE_CENTER[1]),
)

SHAFT_NUMBER = _config.parts("pd-transgear-knob-shaft")["number"]
PLATE_NUMBER = _config.parts("pd-transgear-arm-plate")["number"]
PIN_NUMBER = _config.parts("pd-vn-transgear-knob-cup-pin")["number"]
# drawing-guidelines.md rule 4: the reamed bore's band names its mate and the
# fit it keeps -- the cup slides on the knob shaft's journal to its feeler
# setting before it is pinned (machinist review: the band named no mate).
BORE_CALLOUT = (
    f"REAM THRU; SLIDES ON\n{SHAFT_NUMBER} JOURNAL,\n"
    f"{min(BORE_JOURNAL_CLEARANCE):.3f}-{max(BORE_JOURNAL_CLEARANCE):.3f}\n"
    "DIAMETRAL CLEARANCE"
)
DIMENSION_CALLOUTS = {"BoreDia": BORE_CALLOUT}

# The bore block stands up and left of the face view, its right end clear of
# the bore's vertical centreline (x = FACE_CENTER[0]): the earlier block,
# centred at x 60 mm, ran its last line across that centreline (machinist
# review: the line struck ASSEMBLY's B).
FACE_KEEP = {
    "BoreDia": (0.050, 0.238),
}
# The section spans y 154 .. 186 mm. Its native SECTION / SCALE caption
# occupies the old OD lane at y 130 mm; put the OD below the intact caption.
SECTION_KEEP = {
    "CupDia": (0.200, 0.115),
    "CupLength": (0.255, SECTION_CENTER[1]),
}


def _section_y(model_y_mm: float) -> float:
    """Sheet Y of a model-Y station on the section (front face up).

    The section is cut from the *Top face view, and it shows model +Y down:
    mapped rear face up, the front-face pick landed on the y = LENGTH face
    (run 20261001T011714683Z).
    """
    return SECTION_CENTER[1] - (model_y_mm - LENGTH / 2.0) * _S / 1000.0


# The front face's pick lies on its cut edge, midway between the bore and
# the O.D. on the right half; the symbol stands above and outboard, clear of
# the length dimension's upper extension line on the right.
_FRONT_PICK = (
    SECTION_CENTER[0] + (BORE_DIA + OD) / 4.0 * _S / 1000.0,
    _section_y(0.0),
)
FRONT_FINISH = (_FRONT_PICK, (_FRONT_PICK[0] + 0.020, _FRONT_PICK[1] + 0.022))

# The cross pin hole is no feature of the supplied cup: a sheet note, apart
# from the bore's callout, says so and points at the assembly step that sizes
# and locates it (machinist review: on the bore's leader the line read as the
# bore, and it gave the hole no definition).  Below the face view, left of
# the section's O.D. dimension.
PIN_HOLE_NOTE = (
    f"NO CROSS HOLE ON THIS PART: THE {PIN_NUMBER}\n"
    f"PIN HOLE IS MADE THROUGH CUP AND {SHAFT_NUMBER}\n"
    f"AT ASSEMBLY PER {step_ref('knob-stack-fitted')}."
)
PIN_HOLE_NOTE_XY = (0.020, 0.112)
# The front face's finish caption names the face's function and its mate
# (rule 6: a finish only on a face that runs, slides or locates; machinist
# review: the face's function was stated nowhere).  Just above the symbol (a
# run-1 reviewer read the 6 mm gap as a caption floating free of it), left of
# the isometric.
FRONT_FINISH_CAPTION = f"THRUST FACE ON\n{PLATE_NUMBER} REAR BOSS"
FRONT_FINISH_CAPTION_XY = (FRONT_FINISH[1][0] - 0.009, FRONT_FINISH[1][1] + 0.0185)
# A note's read-back position may differ from the one asked by this much.
NOTE_POSITION_TOL_M = 5e-4


def _add_placed_note(
    adapter: Any, text: str, xy: tuple[float, float], label: str
) -> None:
    """Insert a free note and prove it landed at ``xy``.

    ``add_note`` only logs a failed ``IAnnotation.SetPosition``, which would
    leave the note at SolidWorks' default spot, so read the position back.
    """
    raw_note = add_note(adapter, text, *xy)
    if raw_note is None:
        raise RuntimeError(f"failed to add the {label}")
    raw_annotation = _early_bound(raw_note, "INote").GetAnnotation()
    if raw_annotation is None:
        raise RuntimeError(f"the {label} has no annotation")
    annotation = _early_bound(raw_annotation, "IAnnotation")
    position = tuple(float(value) for value in (annotation.GetPosition() or ()))
    if len(position) < 2 or any(
        abs(actual - wanted) > NOTE_POSITION_TOL_M
        for actual, wanted in zip(position[:2], xy, strict=True)
    ):
        raise RuntimeError(f"the {label} sits at {position[:2]}, not {xy}")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open knob-cup source", await adapter.open_model(str(SOURCE)))
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
            "Material Specification",
            "Finish",
            "Quantity",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Transgear Knob Cup Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "transgear knob cup; turned brass",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    face = place_view(adapter, str(SOURCE), "*Top", *FACE_CENTER, scale=VIEW_SCALE)
    section = create_section_view(
        adapter,
        face,
        line_start=SECTION_LINE[0],
        line_end=SECTION_LINE[1],
        view_xy=SECTION_CENTER,
        section_label="A",
        scale=VIEW_SCALE,
        label="knob cup axial section",
    )
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=VIEW_SCALE)
    for view in (face, section, iso):
        set_hidden_lines_removed(adapter, view)

    face_annotations = curate_view_dimensions(
        adapter,
        face,
        keep=FACE_KEEP,
        view_label="face",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    section_annotations = curate_view_dimensions(
        adapter,
        section,
        keep=SECTION_KEEP,
        view_label="axial section",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    # Decimal places (and so the general-tolerance row each dimension claims)
    # and the bore's band are authored on the part; the sheet only proves the
    # import kept them.
    assert_imported_precision(
        adapter, [*face_annotations, *section_annotations], DRAWING_PRECISION_BY_NAME
    )
    set_dimension_callouts(adapter, face_annotations, DIMENSION_CALLOUTS)
    if not auto_center_marks(adapter, face, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to the cup face view")
    pick, symbol = FRONT_FINISH
    add_surface_finish(
        adapter,
        section,
        edge_xy=pick,
        symbol_xy=symbol,
        control=surface_finish_by_key(SURFACE_FINISHES, "front_face"),
        label="cup front (running) face finish",
        char_height=0.0025,
    )
    _add_placed_note(
        adapter,
        FRONT_FINISH_CAPTION,
        FRONT_FINISH_CAPTION_XY,
        "front face finish caption",
    )
    _add_placed_note(adapter, PIN_HOLE_NOTE, PIN_HOLE_NOTE_XY, "cross pin hole note")

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Transgear Knob Cup Manufacturing Drawing",
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
