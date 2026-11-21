r"""Create the manufacturing drawing for the transgear knob cup (MHA-PD-16).

Section A-A is the lathe view (drawing-guidelines.md rule 11): it cuts the
cup on its axis through the Front plane, the plane of the turned profile,
and lies axis-horizontal, so the O.D., the length, the end-milled .250
flat-bottom pilot and its depth, the rear head pocket and the two floor
corners' R.xxx MAX limits print together on solid cut edges.
The pilot's callout names the MHA-PD-08 journal it is bonded on and the
diametral clearance it keeps there (rule 23).  The face view, the ``*Top``
orientation turned a quarter, carries the cutting plane and the web's #33
drill for the MHA-PD-VN-71 screw, where it shows round.  The length and the
pilot depth are supply sizes: NOTE 1 gives the fitted pilot depth the front
face is faced to at assembly (rule 19).  The front face is the thrust face on
the MHA-PD-28 bush's rear face (the rear stop of the knob's end float) and
carries its finish under a caption that names that face.
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
from _part_properties import part_drawing_unit
from _session import run_build
from _surface_finish import surface_finish_by_key
import _telemetry
from pd_paper_drive_assembly_steps import step_ref
from pd_transgear_knob_cup_spec import (
    BORE_DIA,
    BORE_CLEARANCE_TEXT,
    CBORE_DEPTH,
    CBORE_DIA,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    LENGTH,
    OD,
    PILOT_DEPTH,
    PILOT_DEPTH_FITTED_TEXT,
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

# A Ø.44 x .36 cup: 4:1 keeps the section (37 x 45 mm on the sheet), its
# stacked depth rows and the pilot's callout legible.
SHEET_SCALE = (4.0, 1.0)
VIEW_SCALE = (4, 1)
_S = SHEET_SCALE[0] / SHEET_SCALE[1]
FACE_CENTER = (0.090, 0.170)
SECTION_CENTER = (0.200, FACE_CENTER[1])
# Right of the bore's block (it ends near x 283 mm).
ISO_CENTER = (0.350, FACE_CENTER[1])
# Half the cup's O.D., pilot, pocket and length on the sheet, the pilot's
# and the pocket's depths there, and the cutting line's overrun past the O.D.
HALF_OD = OD * _S / 2000.0
HALF_BORE = BORE_DIA * _S / 2000.0
HALF_CBORE = CBORE_DIA * _S / 2000.0
HALF_LENGTH = LENGTH * _S / 2000.0
PILOT_DEPTH_ON_SHEET = PILOT_DEPTH * _S / 1000.0
CBORE_DEPTH_ON_SHEET = CBORE_DEPTH * _S / 1000.0
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
REAR_FACE_X = SECTION_CENTER[0] - HALF_LENGTH
SECTION_TOP = SECTION_CENTER[1] + HALF_OD
SECTION_BOTTOM = SECTION_CENTER[1] - HALF_OD
# The native SECTION / SCALE caption, top-centre anchored, under the floor
# corners' radius row.
CAPTION_XY = (SECTION_CENTER[0], SECTION_BOTTOM - 0.026)

SHAFT_NUMBER = _config.parts("pd-transgear-knob-shaft")["number"]
BUSH_NUMBER = _config.parts("pd-transgear-knob-bush")["number"]
# drawing-guidelines.md rule 23: a bonded fit is a fit -- the pilot's band
# names its mate and the diametral clearance, inside LOCTITE 641's gap fill
# (the spec asserts it); the grade and method are the assembly step's.  The
# process row says the blind pilot is end-milled to a flat floor (rule 12),
# since a reamer cannot reach one.  Rule 7: the process line plus two lines
# of words, each within the 24 characters that fit between the front face
# and the isometric.
BORE_CALLOUT = (
    "FLAT BOTTOM END MILL\n"
    f"BONDED FIT ON {SHAFT_NUMBER}\n"
    f"(CLEARANCE {BORE_CLEARANCE_TEXT})"
)
# The block hangs right of its own vertical dimension line, which drops to
# the shelf under the block's last row: the line struck the first row's text
# and the shelf both parentheses' tails (machinist review r1-r3, text on lines).
# A leading space on every row holds the ink off the line
# (draw_ch_fulcrum_shaft's across-flat block), and a closing no-break-space
# row drops the shelf a row below the parentheses.
BORE_CALLOUT_ROWS = "\n".join(f" {row}" for row in BORE_CALLOUT.splitlines()) + "\n\u00a0"
# The supply sizes refer to NOTE 1 (rule 19); the web drill prints its
# process where it shows round.
SUPPLY_CALLOUT = "SEE NOTE 1"
HOLE_CALLOUT = "#33 DRILL THRU"
SECTION_CALLOUTS = {
    "BoreDia": BORE_CALLOUT_ROWS,
    "CupLength": SUPPLY_CALLOUT,
    "PilotDepth": SUPPLY_CALLOUT,
}
FACE_CALLOUTS = {"HoleDia": HOLE_CALLOUT}

# Half the height of the bore's value-and-callout block: 31 mm on the
# eecbf88 render for the stacked band over four callout rows; three rows and
# the shelf row now.
BORE_BLOCK_HALF_HEIGHT = 0.0153
# The O.D. outermost on the rear-face side, between the face view and the
# section; the pocket's Ø inside it, its text dropped below the pocket so the
# two stand apart.  The pilot right of the front face: its block (taller than
# the 25 mm between the pilot's extension lines) stands below the lower one,
# clear of the finish above, the corner radii and the caption to its left,
# its dimension line right of the finish symbol's Ra text.
# Above the section, the two depths on one row, the length a row higher
# with its note reference under it.  Neither depth's text fits its span
# with air to both extension lines, so each stands outside: the pocket
# depth's ".108" (8.5 mm over an 11 mm span) left of the rear face, where
# the length's extension line rising from that face stood 1.39 mm from it
# (r6 audit; 2.0 wanted), and the pilot depth's ".152 / SEE NOTE 1" (24 mm
# over 15 mm) right of the front face, where the length's extension line
# no longer strikes its NOTE row and the pocket depth's arrow no longer
# runs into its "S" (r5 render).  Below the section, the two floor corners'
# R.xxx MAX on one row, each under its own corner, the caption beneath.
DEPTH_TEXT_HALF_WIDTH = 0.012  # "SEE NOTE 1", 23.9 mm on the r5 render
CBORE_DEPTH_TEXT_HALF_WIDTH = 0.00425  # ".108", 8.5 mm on the r6 render
SECTION_KEEP = {
    "CupDia": (REAR_FACE_X - 0.030, SECTION_CENTER[1]),
    "CboreDia": (REAR_FACE_X - 0.012, SECTION_CENTER[1] - HALF_CBORE - 0.007),
    "CboreDepth": (
        REAR_FACE_X - 0.0025 - CBORE_DEPTH_TEXT_HALF_WIDTH, SECTION_TOP + 0.010
    ),
    "PilotDepth": (FRONT_FACE_X + 0.003 + DEPTH_TEXT_HALF_WIDTH, SECTION_TOP + 0.010),
    "CupLength": (SECTION_CENTER[0], SECTION_TOP + 0.026),
    "BoreDia": (
        FRONT_FACE_X + 0.060,
        SECTION_CENTER[1] - HALF_BORE - BORE_BLOCK_HALF_HEIGHT - 0.004,
    ),
    "PocketFloorR": (REAR_FACE_X - 0.002, SECTION_BOTTOM - 0.010),
    "PilotFloorR": (FRONT_FACE_X - 0.004, SECTION_BOTTOM - 0.010),
}
# The web drill's Ø on the face view, up and left of it on a leader.
FACE_KEEP = {"HoleDia": (FACE_CENTER[0] - 0.040, FACE_CENTER[1] + 0.037)}

# The front face's pick lies on its cut edge, midway between the bore and
# the O.D. on the upper half.  The symbol stands level with it, outboard
# past the pilot depth's text, so its leader runs straight in under that
# text and over the pilot's upper extension line (a leader rising to a
# symbol over the face crossed the text's place).
_FRONT_PICK = (
    FRONT_FACE_X,
    SECTION_CENTER[1] + (BORE_DIA + OD) / 4.0 * _S / 1000.0,
)
FRONT_FINISH = (_FRONT_PICK, (_FRONT_PICK[0] + 0.037, _FRONT_PICK[1]))

# Rule 19: the supply sizes and the fitted size, with the step that sets it;
# the float it sets and how are the assembly step's.  Below the face view.
NOTES = (
    "NOTES:\n"
    "1. LENGTH AND PILOT DEPTH ARE SUPPLY SIZES. FITTED\n"
    f"   PILOT DEPTH {PILOT_DEPTH_FITTED_TEXT} AT {step_ref('knob-stack-fitted')}."
)
NOTES_XY = (0.020, 0.112)
# The front face's finish caption names the face's function and its mate
# (rule 6: a finish only on a face that runs, slides or locates; machinist
# review: the face's function was stated nowhere).  Just above the symbol (a
# run-1 reviewer read the 6 mm gap as a caption floating free of it), right
# of the pilot depth's text and left of the isometric.
FRONT_FINISH_CAPTION = f"THRUST FACE ON\n{BUSH_NUMBER} REAR FACE"
FRONT_FINISH_CAPTION_XY = (FRONT_FINISH[1][0] - 0.007, FRONT_FINISH[1][1] + 0.0185)
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


def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open knob-cup source", adapter.open_model(str(SOURCE)))
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
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout,
        unit=part_drawing_unit(PART_STEM),
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
    face_annotations = curate_view_dimensions(
        adapter,
        face,
        keep=FACE_KEEP,
        view_label="face view",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    # Decimal places (and so the general-tolerance row each dimension claims)
    # and the pilot's band are authored on the part; the sheet only proves the
    # import kept them.
    assert_imported_precision(
        adapter, section_annotations + face_annotations, DRAWING_PRECISION_BY_NAME
    )
    set_dimension_callouts(adapter, section_annotations, SECTION_CALLOUTS)
    set_dimension_callouts(adapter, face_annotations, FACE_CALLOUTS)
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
    _add_placed_note(adapter, NOTES, NOTES_XY, "supply and fit-up notes")

    return finalize_drawing(
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
