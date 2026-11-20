r"""Create the manufacturing drawing for the transgear knob bush (MHA-PD-28).

Section A-A is the lathe view (drawing-guidelines.md rule 11): it cuts the
bush on its axis through the Front plane, the plane of the turned profile,
and lies axis-horizontal with the hub face on the left, so the hub and press
diameters, the reamed bore, the hub station and the overall length (both
from the hub face) and the shoulder root print together on solid cut edges.
Datum A tags the shoulder face there, and both thrust faces carry their
finish under a caption naming the part they bear on.  The face view, the
``*Top`` orientation turned a quarter, carries the cutting plane, the bore's
perpendicularity frame to A and the bore's running
finish.  Every callout row is authored on the part; the sheet reads them
back.
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
from _drawing_dimensions import assert_imported_precision
from _drawing_finish import add_surface_finish
from _drawing_gdt import PmiDrawingPlacement, project_part_pmi
from _drawing_projection import model_point_in_view, model_points_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_sections import create_section_view
from _drawing_view_display import set_hidden_lines_removed
from _gear_drawing_entities import visible_circle_edge
from _machinist_review_mode import MachinistReviewMode
from _paths import CAD_ROOT
from _part_properties import part_drawing_unit
from _section_axis import create_section_axis_centerline, position_section_caption
from _session import run_build
from _surface_finish import surface_finish_by_key
import _telemetry
from pd_transgear_knob_bush_geometry import (
    BORE_DIA,
    HUB_DIA,
    HUB_LENGTH,
    LENGTH,
    PRESS_DIA,
)
from pd_transgear_knob_bush_spec import (
    DIMENSION_CALLOUTS,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    FINISH_CAPTIONS,
    GEOMETRIC_CONTROLS,
    PART_DATUMS,
    SURFACE_FINISHES,
)

# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["pd_transgear_knob_bush"]
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

# A Ø13.2 x 29.0 bush: 3:1 lays the section 87 mm long with room on both
# ends for the diameters' callouts on the landscape sheet.
SHEET_SCALE = (3.0, 1.0)
VIEW_SCALE = (3, 1)
_S = SHEET_SCALE[0] / SHEET_SCALE[1]
# The face view upper left (its frame above it), A-A in the middle, the
# isometric lower right, above the title block's top edge.
FACE_CENTER = (0.060, 0.200)
SECTION_CENTER = (0.200, 0.170)
ISO_CENTER = (0.340, 0.105)
# Half the bush's hub, press and bore Ø and its length on the sheet, and the
# cutting line's overrun past the hub.
HALF_HUB = HUB_DIA * _S / 2000.0
HALF_PRESS = PRESS_DIA * _S / 2000.0
HALF_BORE = BORE_DIA * _S / 2000.0
HALF_LENGTH = LENGTH * _S / 2000.0
SECTION_LINE_OVERRUN = 0.005
# The face view turned a quarter: sheet Y is then model X, so a vertical cut
# on the bush axis is the Front plane, the plane of the turned profile, and
# A-A projects with the bush axis horizontal (the draw_pd_transgear_knob_cup
# layout).
FACE_VIEW_ANGLE = math.pi / 2.0
SECTION_LINE = (
    (FACE_CENTER[0], FACE_CENTER[1] - HALF_HUB - SECTION_LINE_OVERRUN),
    (FACE_CENTER[0], FACE_CENTER[1] + HALF_HUB + SECTION_LINE_OVERRUN),
)
# A-A lays the hub face on the left (``_orient_section``), as the bush sits
# in the lathe with the rear face at the free end.
HUB_FACE_X = SECTION_CENTER[0] - HALF_LENGTH
SHOULDER_X = HUB_FACE_X + HUB_LENGTH * _S / 1000.0
REAR_FACE_X = SECTION_CENTER[0] + HALF_LENGTH
# The native SECTION caption, top-centre anchored, under the section and
# below datum A's tag and the root radius, right of the bore's block.
CAPTION_XY = (SECTION_CENTER[0], SECTION_CENTER[1] - HALF_HUB - 0.045)

# Section A-A's dimension texts.  Left of the hub face: the bore's line
# nearer the part and the hub's beyond it, so the hub's extension lines (at
# the hub radius) pass outside the bore's dimension line and neither crosses
# the other; the bore's three-row block hangs below the part.  Above: the
# hub station, then the overall length over it.  Right of the rear face: the
# press Ø, its block between its own extension lines.  The root radius below
# the shoulder.
SECTION_KEEP = {
    "HubDia": (HUB_FACE_X - 0.038, SECTION_CENTER[1]),
    "BoreDia": (HUB_FACE_X - 0.014, SECTION_CENTER[1] - HALF_HUB - 0.020),
    "HubLength": (
        (HUB_FACE_X + SHOULDER_X) / 2.0,
        SECTION_CENTER[1] + HALF_HUB + 0.022,
    ),
    "BushLength": (SECTION_CENTER[0], SECTION_CENTER[1] + HALF_HUB + 0.050),
    "PressDia": (REAR_FACE_X + 0.066, SECTION_CENTER[1]),
    "ShoulderR": (SHOULDER_X + 0.014, SECTION_CENTER[1] - HALF_HUB - 0.012),
}

# Each thrust face's pick lies on its cut edge on the upper half, midway
# between the bore and its outer Ø; the symbol stands above and outboard of
# the diameter's extension line, its caption over it (the plate's former
# hub- and boss-face layout).
_HUB_PICK = (HUB_FACE_X, SECTION_CENTER[1] + (BORE_DIA + HUB_DIA) / 4.0 * _S / 1000.0)
_REAR_PICK = (
    REAR_FACE_X,
    SECTION_CENTER[1] + (BORE_DIA + PRESS_DIA) / 4.0 * _S / 1000.0,
)
FACE_FINISHES = {
    "hub_face": (
        _HUB_PICK,
        (_HUB_PICK[0] - 0.009, SECTION_CENTER[1] + HALF_HUB + 0.010),
        (_HUB_PICK[0] - 0.034, SECTION_CENTER[1] + HALF_HUB + 0.024),
    ),
    "rear_face": (
        _REAR_PICK,
        (_REAR_PICK[0] + 0.012, SECTION_CENTER[1] + HALF_HUB + 0.010),
        (_REAR_PICK[0] + 0.008, SECTION_CENTER[1] + HALF_HUB + 0.024),
    ),
}
# Datum A's tag hangs below the shoulder's lower cut edge, left of the root
# radius; its pick lies on that edge midway between the press and the hub.
DATUM_A_PICK = (SHOULDER_X, SECTION_CENTER[1] - (HALF_PRESS + HALF_HUB) / 2.0)
DATUM_A_XY = (SHOULDER_X - 0.012, SECTION_CENTER[1] - HALF_HUB - 0.022)

# The face view's bore: the perpendicularity frame above the view (its
# top-left corner), the running finish below right.
FRAME_XY = (FACE_CENTER[0] - 0.030, FACE_CENTER[1] + HALF_HUB + 0.026)
BORE_FINISH_XY = (FACE_CENTER[0] + HALF_HUB + 0.010, FACE_CENTER[1] - HALF_HUB - 0.008)
FINISH_CHAR_HEIGHT = 0.0025
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
        raise RuntimeError("failed to turn the knob-bush face view a quarter")
    rebuild_drawing(adapter, label="knob bush face view turned")


def _section_axis_ends(adapter: Any, native: Any) -> tuple[tuple[float, float], ...]:
    """Sheet points of the bush axis at the hub face (y = 0) and the rear face."""
    return tuple(
        model_points_in_view(
            adapter,
            native,
            ((0.0, 0.0, 0.0), (0.0, LENGTH / 1000.0, 0.0)),
            label="knob bush section axis",
            names=("hub", "rear"),
        )
    )


def _orient_section(adapter: Any, section: Any) -> None:
    """Lay A-A axis-horizontal, hub face left, its axis on SECTION_CENTER.

    Cut from the quarter-turned face view, A-A lies axis-horizontal; which
    end the hub face takes is read, not assumed, and a half turn (no change
    to a solid of revolution's section) puts it on the left.  Any other turn
    means the cut is not the expected projection: refuse it.
    """
    native = _early_bound(section, "IView")
    hub, rear = _section_axis_ends(adapter, native)
    turn = math.atan2(rear[1] - hub[1], rear[0] - hub[0])
    if abs(turn) > 1e-6:
        if abs(abs(turn) - math.pi) > 1e-6:
            raise RuntimeError(
                f"knob bush A-A axis runs {math.degrees(turn):.3f} deg off the "
                f"sheet's horizontal (hub {hub}, rear {rear})"
            )
        native.Angle = float(native.Angle) - turn
        rebuild_drawing(adapter, label="knob bush section turned")
        hub, rear = _section_axis_ends(adapter, native)
    middle = ((hub[0] + rear[0]) / 2.0, (hub[1] + rear[1]) / 2.0)
    shift = (SECTION_CENTER[0] - middle[0], SECTION_CENTER[1] - middle[1])
    if math.hypot(*shift) > SECTION_POSITION_TOL_M:
        position = tuple(float(value) for value in native.Position)
        if not native.SetViewPosition(
            double_array([position[0] + shift[0], position[1] + shift[1]]), False
        ):
            raise RuntimeError("failed to centre the knob bush section")
        rebuild_drawing(adapter, label="knob bush section centred")
        hub, rear = _section_axis_ends(adapter, native)
    expected = ((HUB_FACE_X, SECTION_CENTER[1]), (REAR_FACE_X, SECTION_CENTER[1]))
    if any(
        math.dist(actual, wanted) > SECTION_POSITION_TOL_M
        for actual, wanted in zip((hub, rear), expected, strict=True)
    ):
        raise RuntimeError(
            f"knob bush A-A axis ends at hub {hub}, rear {rear}; wanted {expected}"
        )
    _telemetry.info(
        f"knob bush A-A angle={float(native.Angle):.6f} rad, turn={turn:.6f}"
    )


def _bore_landing(
    adapter: Any, view: Any, toward: tuple[float, float]
) -> tuple[float, float]:
    """The point on the bore's circle in ``view`` facing ``toward`` (sheet m).

    A leader on a circle runs radially through its pick, so the pick must
    face the symbol (draw_pd_transgear_arm_plate._bore_landing).
    """
    centre = model_point_in_view(
        adapter, view, (0.0, 0.0, 0.0), label="bush bore centre"
    )
    dx, dy = toward[0] - centre[0], toward[1] - centre[1]
    scale = HALF_BORE / math.hypot(dx, dy)
    return centre[0] + dx * scale, centre[1] + dy * scale


@_telemetry.traced("drawing.pd_transgear_knob_bush.callouts")
def _assert_dimension_callouts(adapter: Any, annotations: list[Any]) -> None:
    """Import the part-authored callout rows verbatim; never write them here.

    Text set from the drawing writes through to the built part (fleet issue
    #1942), so the sheet only proves each callout dimension printed once with
    the rows its part authored.
    """
    for callouts in DIMENSION_CALLOUTS.values():
        for name, text in callouts.items():
            matches = [
                item for item in annotations if dimension_name(adapter, item) == name
            ]
            if len(matches) != 1:
                raise RuntimeError(f"{name}: expected one imported callout dimension")
            display = _early_bound(
                _early_bound(matches[0], "IAnnotation").GetSpecificAnnotation(),
                "IDisplayDimension",
            )
            if str(display.GetText(4) or "").replace("\r\n", "\n") != text:
                raise RuntimeError(f"{name}: imported callout differs from the part's")


def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open knob-bush source", adapter.open_model(str(SOURCE)))
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
            0: "Transgear Knob Bush Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "transgear knob bush; turned steel",
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
        label="knob bush axial section",
    )
    _orient_section(adapter, section)
    position_section_caption(adapter, section, CAPTION_XY, label="knob bush")
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
    # Decimal places (and so the general-tolerance row each dimension claims),
    # the bands, the root's MAX and every callout row are authored on the
    # part; the sheet only proves the import kept them.
    assert_imported_precision(adapter, section_annotations, DRAWING_PRECISION_BY_NAME)
    _assert_dimension_callouts(adapter, section_annotations)
    create_section_axis_centerline(
        adapter, section, length_mm=LENGTH, label="knob bush axis"
    )
    if not auto_center_marks(adapter, face, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to the bush face view")

    # The same native datum and frame authored on the part: A on the
    # shoulder's cut edge, the bore's frame on the face view's bore.  The
    # bore carries no datum: no frame references one (rule 5).
    bore_edge = visible_circle_edge(adapter, face, BORE_DIA)
    placements = {
        "datum:A": PmiDrawingPlacement(section, DATUM_A_XY, attachment_xy=DATUM_A_PICK),
        "bore_perpendicularity": PmiDrawingPlacement(
            face,
            FRAME_XY,
            edge_entity=bore_edge,
        ),
    }
    project_part_pmi(
        adapter,
        placements=placements,
        datums=PART_DATUMS,
        controls=GEOMETRIC_CONTROLS,
        label="knob bush bore frame",
    )

    add_surface_finish(
        adapter,
        face,
        symbol_xy=BORE_FINISH_XY,
        control=surface_finish_by_key(SURFACE_FINISHES, "bore"),
        label="bush bore (running) finish",
        entity=bore_edge,
        char_height=FINISH_CHAR_HEIGHT,
        leader_attach_xy=_bore_landing(adapter, face, BORE_FINISH_XY),
    )
    for key, label in (
        ("hub_face", "bush hub (thrust ring) face finish"),
        ("rear_face", "bush rear (cup) face finish"),
    ):
        pick, symbol, caption = FACE_FINISHES[key]
        add_surface_finish(
            adapter,
            section,
            edge_xy=pick,
            symbol_xy=symbol,
            control=surface_finish_by_key(SURFACE_FINISHES, key),
            label=label,
            char_height=FINISH_CHAR_HEIGHT,
        )
        _add_placed_note(adapter, FINISH_CAPTIONS[key], caption, f"{label} caption")

    return finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Transgear Knob Bush Manufacturing Drawing",
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
