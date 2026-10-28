r"""Create the manufacturing drawing for the transgear knob cup (MHA-PD-16).

Section A-A is the lathe view (drawing-guidelines.md rule 11): it cuts the
cup on its axis through the Front plane, the plane of the turned profile,
and lies axis-horizontal, so the O.D., the length and the six-millimetre H7
bore print together on solid cut edges.  The bore's callout names the
MHA-PD-08 journal it slides on and the diametral clearance it keeps there.
The face view, the ``*Top`` orientation turned a quarter, only carries the
cutting plane.  A separate sheet note says the MHA-PD-VN-62 cross pin hole
is not drilled on this part: it is made through cup and journal together at
assembly, at the paper-drive step the note cites, so it is not dimensioned
here.  The front face is the thrust face on the arm plate's rear boss (the
rear stop of the knob's end float) and carries its finish under a caption
that names that boss.
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

from solidworks_mcp.adapters.com_variant import double_array
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
    rebuild_drawing,
    stamp_drawing_summary,
)
from _drawing_dimension_import import curate_view_dimensions
from _drawing_dimensions import assert_imported_precision, set_dimension_callouts
from _drawing_finish import add_surface_finish
from _drawing_projection import model_points_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_sections import create_section_view
from _drawing_view_display import set_hidden_lines_removed
from _machinist_review_mode import MachinistReviewMode
from _paths import CAD_ROOT
from _section_axis import create_section_axis_centerline, position_section_caption
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

# A Ø19 x 8 ring: 4:1 keeps the section (32 x 76 mm on the sheet) and the
# bore's callout legible without crowding the landscape sheet.
SHEET_SCALE = (4.0, 1.0)
VIEW_SCALE = (4, 1)
_S = SHEET_SCALE[0] / SHEET_SCALE[1]
FACE_CENTER = (0.090, 0.170)
SECTION_CENTER = (0.200, FACE_CENTER[1])
# Right of the bore's block (it ends near x 283 mm).
ISO_CENTER = (0.350, FACE_CENTER[1])
# Half the cup's O.D., bore and length on the sheet, and the cutting line's
# overrun past the O.D.
HALF_OD = OD * _S / 2000.0
HALF_BORE = BORE_DIA * _S / 2000.0
HALF_LENGTH = LENGTH * _S / 2000.0
SECTION_LINE_OVERRUN = 0.005
# The face view turned a quarter: sheet Y is then model X, so a vertical cut
# on the cup axis is the Front plane, the plane of the turned profile, and
# A-A projects to the right with the cup axis horizontal (the
# draw_dt_crank_handle_ferrule layout).
FACE_VIEW_ANGLE = math.pi / 2.0
SECTION_LINE = (
    (FACE_CENTER[0], FACE_CENTER[1] - HALF_OD - SECTION_LINE_OVERRUN),
    (FACE_CENTER[0], FACE_CENTER[1] + HALF_OD + SECTION_LINE_OVERRUN),
)
# A-A lays the front face on the right (``_orient_section``): its finish
# rises there above the bore's dimension, and the O.D. takes the rear side.
FRONT_FACE_X = SECTION_CENTER[0] + HALF_LENGTH
# The native SECTION / SCALE caption, top-centre anchored, under the section.
CAPTION_XY = (SECTION_CENTER[0], SECTION_CENTER[1] - HALF_OD - 0.010)

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

# Half the height of the bore's value-and-callout block: 31 mm on the
# eecbf88 render (the stacked band over four callout rows).
BORE_BLOCK_HALF_HEIGHT = 0.0155
# The O.D. on the rear-face side, between the face view and the section.
# The bore right of the front face: its block (taller than the 24 mm between
# the bore's extension lines) stands below the lower one, clear of the
# finish above and the section caption to its left.  The length above.
SECTION_KEEP = {
    "CupDia": (SECTION_CENTER[0] - HALF_LENGTH - 0.020, SECTION_CENTER[1]),
    "CupLength": (SECTION_CENTER[0], SECTION_CENTER[1] + HALF_OD + 0.012),
    "BoreDia": (
        FRONT_FACE_X + 0.042,
        SECTION_CENTER[1] - HALF_BORE - BORE_BLOCK_HALF_HEIGHT - 0.004,
    ),
}

# The front face's pick lies on its cut edge, midway between the bore and
# the O.D. on the upper half; the symbol stands above and outboard, clear of
# the length dimension's extension line rising from the same face.
_FRONT_PICK = (
    FRONT_FACE_X,
    SECTION_CENTER[1] + (BORE_DIA + OD) / 4.0 * _S / 1000.0,
)
FRONT_FINISH = (_FRONT_PICK, (_FRONT_PICK[0] + 0.020, _FRONT_PICK[1] + 0.022))

# The cross pin hole is no feature of the supplied cup: a sheet note, apart
# from the bore's callout, says so and points at the assembly step that sizes
# and locates it (machinist review: on the bore's leader the line read as the
# bore, and it gave the hole no definition).  Below the face view.
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
# How far A-A's axis may sit from SECTION_CENTER / level before it is moved.
SECTION_POSITION_TOL_M = 1e-4


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


def _turn_face_view(adapter: Any, face: Any) -> None:
    """Turn the face view a quarter so the cut on its vertical centreline is
    the Front plane (``FACE_VIEW_ANGLE``)."""
    native = _early_bound(face, "IView")
    native.Angle = FACE_VIEW_ANGLE
    if abs(math.remainder(float(native.Angle) - FACE_VIEW_ANGLE, 2.0 * math.pi)) > 1e-9:
        raise RuntimeError("failed to turn the knob-cup face view a quarter")
    rebuild_drawing(adapter, label="knob cup face view turned")


def _section_axis_ends(adapter: Any, native: Any) -> tuple[tuple[float, float], ...]:
    """Sheet points of the cup axis at the front (y = 0) and rear faces."""
    return tuple(
        model_points_in_view(
            adapter,
            native,
            ((0.0, 0.0, 0.0), (0.0, LENGTH / 1000.0, 0.0)),
            label="knob cup section axis",
            names=("front", "rear"),
        )
    )


def _orient_section(adapter: Any, section: Any) -> None:
    """Lay A-A axis-horizontal, front face right, its axis on SECTION_CENTER.

    Cut from the quarter-turned face view, A-A lies axis-horizontal; which
    end the front face takes is read, not assumed, and a half turn (no
    change to a solid of revolution's section) puts it on the right.  Any
    other turn means the cut is not the expected projection: refuse it.
    """
    native = _early_bound(section, "IView")
    front, rear = _section_axis_ends(adapter, native)
    turn = math.atan2(front[1] - rear[1], front[0] - rear[0])
    if abs(turn) > 1e-6:
        if abs(abs(turn) - math.pi) > 1e-6:
            raise RuntimeError(
                f"knob cup A-A axis runs {math.degrees(turn):.3f} deg off the "
                f"sheet's horizontal (front {front}, rear {rear})"
            )
        native.Angle = float(native.Angle) - turn
        rebuild_drawing(adapter, label="knob cup section turned")
        front, rear = _section_axis_ends(adapter, native)
    middle = ((front[0] + rear[0]) / 2.0, (front[1] + rear[1]) / 2.0)
    shift = (SECTION_CENTER[0] - middle[0], SECTION_CENTER[1] - middle[1])
    if math.hypot(*shift) > SECTION_POSITION_TOL_M:
        position = tuple(float(value) for value in native.Position)
        if not native.SetViewPosition(
            double_array([position[0] + shift[0], position[1] + shift[1]]), False
        ):
            raise RuntimeError("failed to centre the knob cup section")
        rebuild_drawing(adapter, label="knob cup section centred")
        front, rear = _section_axis_ends(adapter, native)
    expected = (
        (FRONT_FACE_X, SECTION_CENTER[1]),
        (FRONT_FACE_X - 2 * HALF_LENGTH, SECTION_CENTER[1]),
    )
    if any(
        math.dist(actual, wanted) > SECTION_POSITION_TOL_M
        for actual, wanted in zip((front, rear), expected, strict=True)
    ):
        raise RuntimeError(
            f"knob cup A-A axis ends at front {front}, rear {rear}; wanted {expected}"
        )
    _telemetry.info(
        f"knob cup A-A angle={float(native.Angle):.6f} rad, turn={turn:.6f}"
    )


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
    _turn_face_view(adapter, face)
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
    _orient_section(adapter, section)
    position_section_caption(adapter, section, CAPTION_XY, label="knob cup")
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=VIEW_SCALE)
    for view in (face, section, iso):
        set_hidden_lines_removed(adapter, view)

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
    assert_imported_precision(adapter, section_annotations, DRAWING_PRECISION_BY_NAME)
    set_dimension_callouts(adapter, section_annotations, DIMENSION_CALLOUTS)
    create_section_axis_centerline(
        adapter, section, length_mm=LENGTH, label="knob cup axis"
    )
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
