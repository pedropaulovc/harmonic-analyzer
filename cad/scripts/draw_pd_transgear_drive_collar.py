r"""Create the manufacturing drawing for the transgear drive collar (MHA-PD-022).

The end view shows the actual D opening and the two axial drive holes.
An axial section through the D-flat shows the controlled rear entry break,
turned diameters and fitted body/pilot lengths. The saved body dimension
is REF; its linked assembly step faces the actual rear reaction face on F.
No roughness symbol is added to these clamp faces (policy rule 5).
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_edge_dimension,
    add_property_linked_note,
    assert_imported_precision,
    curate_view_dimensions,
    create_section_view,
    finalize_drawing,
    model_point_in_view,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    set_dimension_callouts,
    set_hidden_lines_removed,
    set_reference_dimension,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from pd_paper_drive_assembly_steps import step_ref
from pd_transgear_drive_collar_spec import (
    BORE_CALLOUT,
    BORE_ENTRY_BREAK_CALLOUT,
    BODY_LENGTH_CALLOUT,
    FLAT_ORIENTATION,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    DRAWING_REFERENCE_PRECISION,
    LENGTH,
    OD,
    OVERALL_LENGTH,
    PILOT_DIA,
    PILOT_LENGTH,
    PILOT_LENGTH_CALLOUT,
    PIN_CIRCLE_RADIUS,
    PIN_HOLE_CALLOUT,
)
from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)

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

# 4:1 exposes the 0.200 rear D entry in section and both axial dowel holes.
SHEET_SCALE = (4.0, 1.0)
VIEW_SCALE = (4, 1)
_S = SHEET_SCALE[0] / SHEET_SCALE[1]
END_CENTER = (0.100, 0.165)
SIDE_CENTER = (0.235, END_CENTER[1])
ISO_CENTER = (0.345, END_CENTER[1])
ISO_SCALE = (2, 1)
HALF_OD = OD * _S / 2000.0
HALF_PILOT = PILOT_DIA * _S / 2000.0
PIN_R = PIN_CIRCLE_RADIUS * _S / 1000.0
# The section is turned to the same frame as *Right: rear left, pilot right,
# +Y up. Its ink is centred on the full turned body's bounding box.
_SEAT_X = SIDE_CENTER[0] + (LENGTH - PILOT_LENGTH) * _S / 2000.0
_REAR_X = _SEAT_X - LENGTH * _S / 1000.0
_PILOT_X = _SEAT_X + PILOT_LENGTH * _S / 1000.0
# The end view: the bore off the upper right and the pin holes off the lower
# right, each leader running straight in, the two pin offsets stacked left.
# The bore's broach callout is wide (its shoulder measured 121.6 mm on the
# farm sheet), so its text sits wholly right of section line A with the
# shoulder above the line's top end and above the section's entry-break
# dimension, never along either.
_BORE_SHOULDER_HALF = 0.061
END_KEEP = {
    "BoreDia": (
        END_CENTER[0] + 0.008 + _BORE_SHOULDER_HALF,
        END_CENTER[1] + HALF_OD + 0.030,
    ),
    "FlatToAxis": (END_CENTER[0] + HALF_OD + 0.020, END_CENTER[1] - 0.004),
    "PinPosDia": (END_CENTER[0] + 0.030, END_CENTER[1] - HALF_OD - 0.012),
    "PinPosY": (END_CENTER[0] - HALF_OD - 0.012, END_CENTER[1] + PIN_R / 2.0),
    "PinNegY": (END_CENTER[0] - HALF_OD - 0.012, END_CENTER[1] - PIN_R / 2.0),
}
# The fitted lengths stack below the section; the entry break stays above
# its actual rear edge, away from the end-view D diameter/flat callouts.
SIDE_KEEP = {
    "PilotLength": ((_SEAT_X + _PILOT_X) / 2.0, SIDE_CENTER[1] - HALF_OD - 0.012),
    "CollarLength": ((_REAR_X + _SEAT_X) / 2.0, SIDE_CENTER[1] - HALF_OD - 0.036),
    # Keep the outside diameter's native band clear of the rear entry.
    "CollarDia": (_REAR_X - 0.040, SIDE_CENTER[1]),
    "PilotDia": (_PILOT_X + 0.014, SIDE_CENTER[1]),
    "BoreEntryBreak": (_REAR_X - 0.014, SIDE_CENTER[1] + HALF_OD + 0.012),
}
OVERALL_TEXT_XY = ((_REAR_X + _PILOT_X) / 2.0, SIDE_CENTER[1] - HALF_OD - 0.050)
# Physical annular end-face picks, outside the actual rear entry relief and
# inside the pilot. The rear-face bore/chamfer is air, not a length witness.
_OVERALL_PICK_Y = SIDE_CENTER[1] + PILOT_DIA * 3.0 * _S / 8000.0
OVERALL_PICKS = ((_PILOT_X, _OVERALL_PICK_Y), (_REAR_X, _OVERALL_PICK_Y))
# The pilot is supplied long and faced at assembly; the sheet prints the
# fitted band and points at the assembly step that faces it.
FIT_STEP_KEY = "pilot-faced-to-fit"
BODY_FIT_STEP_KEY = "collar-rear-faced-to-fit"
DIMENSION_CALLOUTS_BELOW = {
    "BoreDia": BORE_CALLOUT,
    "PinPosDia": PIN_HOLE_CALLOUT,
    "PilotLength": f"{PILOT_LENGTH_CALLOUT},\nPER {step_ref(FIT_STEP_KEY)}",
    "CollarLength": f"{BODY_LENGTH_CALLOUT},\nPER {step_ref(BODY_FIT_STEP_KEY)}",
    "FlatToAxis": FLAT_ORIENTATION,
    "BoreEntryBreak": BORE_ENTRY_BREAK_CALLOUT,
}
ISO_NOTE_XY = (ISO_CENTER[0] - 0.030, ISO_CENTER[1] - 0.040)
# Four source-owned notes; the actual fit procedure is linked to its feature.
NOTES_XY = (0.016, 0.085)


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
    """The unbanded overall, pilot front face to actual rear face (rule 7)."""
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
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Transgear Drive Collar Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "transgear drive collar; true D; fitted rear reaction face",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    end = place_view(adapter, str(SOURCE), "*Back", *END_CENTER, scale=VIEW_SCALE)
    side = create_section_view(
        adapter, end,
        line_start=(END_CENTER[0], END_CENTER[1] - HALF_OD - 0.005),
        line_end=(END_CENTER[0], END_CENTER[1] + HALF_OD + 0.005),
        view_xy=SIDE_CENTER, section_label="A", scale=VIEW_SCALE,
        label="collar axial D-flat section",
    )
    _orient_section(adapter, side)
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
    _overall_reference(adapter, side)
    if not auto_center_marks(adapter, end, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to the collar end view")
    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)
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
