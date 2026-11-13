r"""Manufacturing drawing of the cylinder gears' cam turning fixture body (MHA-DT-12-TL-01).

Shop tooling (``dt_cylinder_gear_tl_cam_fixture_spec``, issue #2361): a
steel disc whose turned OD is the register, a through press ream for the
stub at the cam throw and a blind press ream for the clock pin. One sheet:
the face view carries both reams and their stations from the register axis
(centre-marked), every value outside the disc; the edge view the register's
diameter beside the thickness (rule 11); a small shaded isometric. No
numbered note: each REAM callout names its pin and what its stations set.

Run only through the supervised farm launcher:
``drawing:dt_cylinder_gear_tl_cam_fixture``.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
import dt_cylinder_gear_tl_cam_fixture_spec as part
from _check import check
from _com import _early_bound
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    stamp_drawing_summary,
)
from _drawing_dimensions import (
    assert_imported_precision,
    move_model_dimension,
    set_dimension_callouts,
)
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _machinist_review_mode import MachinistReviewMode
from _paths import CAD_ROOT
from _session import run_build
from solidworks_mcp.adapters.pywin32_adapter import null_callout
from solidworks_mcp.adapters.solidworks.drawing import (
    dimension_name,
    place_view,
    view_name,
)

# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["dt_cylinder_gear_tl_cam_fixture"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"], pdf=SPEC.outputs["pdf"], png=SPEC.outputs["png"]
)
SLDDRW, PDF, PNG = OUTPUTS.slddrw, OUTPUTS.pdf, OUTPUTS.png

# A Ø3.25 disc: 2:1 keeps the pin's .0373 offset from the vertical
# centreline readable (1.9 mm on the sheet).
SHEET_SCALE = (2.0, 1.0)
VIEW_SCALE = (2, 1)
ISO_SCALE = (1, 2)
FACE_CENTER = (0.125, 0.150)
# Third-angle right view, level with the face view.
EDGE_CENTER = (0.300, FACE_CENTER[1])
ISO_CENTER = (0.385, 0.205)
ISO_NOTE_XY = (0.350, 0.160)

# Dimension text positions (sheet metres, the text's centre). The register
# stands 82.5 mm (sheet) from the centre, so the disc spans x .042-.208; the
# stub sits 17 mm below the centre and the pin 48 mm above. Every text stands
# outside the disc (rule 14; run 20261113T012650242Z's review read all three
# stations inside it): the two vertical stations in one chain from the
# centre, right of the disc and left of the edge view (x .275); the pin's
# .0373 over the disc's top; each ream size on a leader outside the disc.
_FX, _FY = FACE_CENTER
_S = VIEW_SCALE[0] / VIEW_SCALE[1] / 1000.0  # sheet metres per model mm
_DISC_RIGHT = _FX + part.BODY_DIA / 2.0 * _S
_DISC_TOP = _FY + part.BODY_DIA / 2.0 * _S
FACE_KEEP = {
    # The register's diameter is imported here and moved to the edge view.
    "BodyDia": (_FX - 0.075, _FY + 0.100),
    "StubOffset": (_DISC_RIGHT + 0.024, _FY - 0.009),
    "PinY": (_DISC_RIGHT + 0.024, _FY + 0.025),
    "PinX": (_FX - 0.020, _DISC_TOP + 0.012),
    # Below the stations' chain, clear of the disc's lower right and left of
    # the edge view.
    "StubHoleDia": (_DISC_RIGHT + 0.028, _FY - 0.055),
    # Above the register's upper right, inside the top border.
    "PinHoleDia": (_FX + 0.065, _FY + 0.100),
}
# Above the edge view's top, clear of its witness lines.
EDGE_KEEP = {"BodyThick": (EDGE_CENTER[0], _FY + 0.100)}
# The register's diameter beside the thickness (rule 11): right of the edge
# view, its text under the isometric's scale note.
BODY_DIA_ON_EDGE = (EDGE_CENTER[0] + part.THICKNESS / 2.0 * _S + 0.018, _FY - 0.045)

# swCenterMarkStyle_e.swCenterMark_Single; swCenterMarkHandle_e Up/Left/Down/Right.
CENTER_MARK_SINGLE = 2
_CENTER_MARK_HANDLES = (0, 1, 2, 3)
# Each register arm runs past the rim (model metres beyond the rim); the
# right arm then ends left of the title block.
CENTRE_LINE_OVERRUN_MM = 0.5
# Each ream's arms run this far past its rim.
HOLE_ARM_OVERRUN_MM = 1.0


def _centre_mark(
    adapter: Any,
    view: Any,
    rim_mm: tuple[float, float, float],
    arm_mm: float,
    what: str,
) -> None:
    """Centre-mark the circle through ``rim_mm`` (part mm, on its -X side)
    once, its arms run ``arm_mm`` out (draw_dt_cone_gear_tl_index_plate's
    bore mark). One explicit mark per circle: the view's auto-insert marked
    every hole and the register twice (front and back rims)."""
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    name = view_name(adapter, view)
    if not ddoc.ActivateView(name):
        raise RuntimeError(f"failed to activate the face view {name!r}")
    draw.ClearSelection2(True)
    pick = model_point_in_view(
        adapter,
        view,
        tuple(value / 1000.0 for value in rim_mm),
        label=f"{what} rim -X point",
    )
    extension = _early_bound(draw.Extension, "IModelDocExtension")
    if not extension.SelectByID2(
        "", "EDGE", pick[0], pick[1], 0.0, False, 0, null_callout(), 0
    ):
        raise RuntimeError(f"failed to select the {what} rim")
    mark = ddoc.InsertCenterMark3(CENTER_MARK_SINGLE, False, False)
    draw.ClearSelection2(True)
    if mark is None:
        raise RuntimeError(f"failed to centre-mark the {what}")
    mark = _early_bound(mark, "ICenterMark")
    mark.UseDocDisplaySettings = False
    mark.ShowLines = True
    for handle in _CENTER_MARK_HANDLES:
        if not mark.SetExtendedLength(0, handle, arm_mm / 1000.0):
            raise RuntimeError(f"{what} centre mark arm {handle} did not extend")
    if bool(mark.UseDocDisplaySettings) or not bool(mark.ShowLines):
        raise RuntimeError(f"{what} centre mark lost its extended lines")


@_telemetry.traced("drawing.cam_fixture_centre_marks")
def _centre_mark_face(adapter: Any, view: Any) -> None:
    """The register's mark, its lines past the rim: the axis every station
    is measured from; then each ream's own mark."""
    face = part.THICKNESS
    _centre_mark(
        adapter,
        view,
        (-part.BODY_DIA / 2.0, 0.0, face),
        CENTRE_LINE_OVERRUN_MM,
        "register",
    )
    _centre_mark(
        adapter,
        view,
        (-part.STUB_HOLE_DIA / 2.0, -part.STUB_OFFSET, face),
        HOLE_ARM_OVERRUN_MM,
        "stub ream",
    )
    _centre_mark(
        adapter,
        view,
        (part.PIN_X - part.PIN_HOLE_DIA / 2.0, part.PIN_Y, face),
        HOLE_ARM_OVERRUN_MM,
        "clock pin ream",
    )


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source cam fixture missing: {SOURCE}")
    check("open cam fixture", await adapter.open_model(str(SOURCE)))
    required = (
        "Number",
        "Material Specification",
        "Finish",
        "Quantity",
        "Isometric View Note",
    )
    read_required_properties(
        adapter.currentModel, ("Revision", "Title", *required), required=required
    )
    drawing, _sheet = new_project_drawing(
        adapter,
        property_view=PART_STEM,
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        unit=part.UNIT,
    )
    stamp_drawing_summary(
        adapter,
        drawing,
        {
            0: "Cylinder Gear Cam Turning Fixture Drawing",
            1: "Harmonic Analyzer shop tooling drawing",
            2: "Harmonic Analyzer Project",
            3: "lathe fixture; cylinder gear cam throw and phase; MHA-DT-12-TL-01",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    face = place_view(adapter, str(SOURCE), "*Front", *FACE_CENTER, scale=VIEW_SCALE)
    edge = place_view(adapter, str(SOURCE), "*Right", *EDGE_CENTER, scale=VIEW_SCALE)
    # finalize_drawing shades the pictorial isometric with edges.
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    curated: dict[str, list[Any]] = {}
    for view, keep, label in (
        (face, FACE_KEEP, "face view"),
        (edge, EDGE_KEEP, "edge view"),
    ):
        set_hidden_lines_removed(adapter, view)
        curated[label] = curate_view_dimensions(
            adapter,
            view,
            keep=keep,
            view_label=label,
            dimensions_by_feature=part.DRAWING_DIMENSIONS,
        )
    set_hidden_lines_removed(adapter, iso)
    donors = [
        a for a in curated["face view"] if dimension_name(adapter, a) == "BodyDia"
    ]
    if len(donors) != 1:
        raise RuntimeError(f"expected one BodyDia donor dimension, found {len(donors)}")
    moved_body_dia = move_model_dimension(
        adapter, donors[0], edge, BODY_DIA_ON_EDGE, source_view=face
    )
    annotations = [
        *(a for a in curated["face view"] if dimension_name(adapter, a) != "BodyDia"),
        *curated["edge view"],
        moved_body_dia,
    ]
    set_dimension_callouts(adapter, annotations, part.CALLOUTS_BELOW)
    assert_imported_precision(adapter, annotations, part.DRAWING_PRECISION_BY_NAME)
    _centre_mark_face(adapter, face)
    for view in (face, edge, iso):
        set_hidden_lines_removed(adapter, view)
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Cylinder Gear Cam Turning Fixture Drawing",
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
