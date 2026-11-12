r"""Manufacturing drawing of the cylinder gears' cam turning fixture body (MHA-DT-12-TL-01).

Shop tooling (``dt_cylinder_gear_tl_cam_fixture_spec``, issue #2361): a
steel disc whose turned OD is the register, a through press ream for the
stub at the cam throw and a blind press ream for the clock pin. One sheet:
the face view carries the register, both reams and their stations from the
register axis (centre-marked); the edge view the thickness; a small shaded
isometric. The one numbered note names the gear it serves and its kit.

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
    rebuild_drawing,
    stamp_drawing_summary,
)
from _drawing_dimensions import assert_imported_precision, set_dimension_callouts
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_leaders import set_near_side_diameter
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _machinist_review_mode import MachinistReviewMode
from _paths import CAD_ROOT
from _session import run_build
from solidworks_mcp.adapters.pywin32_adapter import null_callout
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    auto_center_marks,
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

# A Ø3.25 disc: 2:1 keeps the pin's .0330 offset from the vertical
# centreline readable (1.7 mm on the sheet).
SHEET_SCALE = (2.0, 1.0)
VIEW_SCALE = (2, 1)
ISO_SCALE = (1, 2)
FACE_CENTER = (0.125, 0.150)
# Third-angle right view, level with the face view.
EDGE_CENTER = (0.300, FACE_CENTER[1])
ISO_CENTER = (0.385, 0.205)
ISO_NOTE_XY = (0.350, 0.160)
FUNCTION_NOTE_XY = (0.335, 0.105)

# Dimension text positions (sheet metres, the text's centre). The register
# stands 82.5 mm (sheet) from the centre; the stub sits 17 mm below it and
# the pin 47 mm above. The stations run in one vertical chain right of the
# centre; the ream sizes stand outside the register, each on a leader.
_FX, _FY = FACE_CENTER
FACE_KEEP = {
    "BodyDia": (_FX - 0.075, _FY + 0.100),
    "StubOffset": (_FX + 0.035, _FY - 0.009),
    "PinY": (_FX + 0.035, _FY + 0.024),
    "PinX": (_FX - 0.030, _FY + 0.068),
    "StubHoleDia": (_FX + 0.110, _FY - 0.045),
    "PinHoleDia": (_FX - 0.110, _FY + 0.070),
}
# The register's diameter takes one arrow on its near rim, clear of the
# station chain through the centre (rule 14).
NEAR_SIDE_DIAMETERS = ("BodyDia",)
# Above the edge view's top, clear of its witness lines.
EDGE_KEEP = {"BodyThick": (EDGE_CENTER[0], _FY + 0.100)}

# swCenterMarkStyle_e.swCenterMark_Single; swCenterMarkHandle_e Up/Left/Down/Right.
CENTER_MARK_SINGLE = 2
_CENTER_MARK_HANDLES = (0, 1, 2, 3)
# Each arm runs past the register (model metres beyond its rim).
CENTRE_LINE_OVERRUN_MM = 3.0


@_telemetry.traced("drawing.cam_fixture_register_centre_mark")
def _centre_mark_register(adapter: Any, view: Any) -> None:
    """Centre-mark the register with lines past its rim: the axis every
    station is measured from (draw_dt_cone_gear_tl_index_plate's bore mark)."""
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    name = view_name(adapter, view)
    if not ddoc.ActivateView(name):
        raise RuntimeError(f"failed to activate the face view {name!r}")
    draw.ClearSelection2(True)
    pick = model_point_in_view(
        adapter,
        view,
        (-part.BODY_DIA / 2000.0, 0.0, part.THICKNESS / 1000.0),
        label="register rim -X point",
    )
    extension = _early_bound(draw.Extension, "IModelDocExtension")
    if not extension.SelectByID2(
        "", "EDGE", pick[0], pick[1], 0.0, False, 0, null_callout(), 0
    ):
        raise RuntimeError("failed to select the register rim")
    mark = ddoc.InsertCenterMark3(CENTER_MARK_SINGLE, False, False)
    draw.ClearSelection2(True)
    if mark is None:
        raise RuntimeError("failed to centre-mark the register")
    mark = _early_bound(mark, "ICenterMark")
    mark.UseDocDisplaySettings = False
    mark.ShowLines = True
    arm = CENTRE_LINE_OVERRUN_MM / 1000.0
    for handle in _CENTER_MARK_HANDLES:
        if not mark.SetExtendedLength(0, handle, arm):
            raise RuntimeError(f"register centre mark arm {handle} did not extend")
    if bool(mark.UseDocDisplaySettings) or not bool(mark.ShowLines):
        raise RuntimeError("register centre mark lost its extended lines")


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
    annotations: list[Any] = []
    for view, keep, label in (
        (face, FACE_KEEP, "face view"),
        (edge, EDGE_KEEP, "edge view"),
    ):
        set_hidden_lines_removed(adapter, view)
        annotations += curate_view_dimensions(
            adapter,
            view,
            keep=keep,
            view_label=label,
            dimensions_by_feature=part.DRAWING_DIMENSIONS,
        )
    set_hidden_lines_removed(adapter, iso)
    set_dimension_callouts(adapter, annotations, part.CALLOUTS_BELOW)
    assert_imported_precision(adapter, annotations, part.DRAWING_PRECISION_BY_NAME)
    for name in NEAR_SIDE_DIAMETERS:
        matches = [a for a in annotations if dimension_name(adapter, a) == name]
        if len(matches) != 1:
            raise RuntimeError(f"expected one {name} dimension, found {len(matches)}")
        set_near_side_diameter(matches[0], f"cam fixture {name}")
    rebuild_drawing(adapter, label="cam fixture near-side diameters")
    _centre_mark_register(adapter, face)
    if not auto_center_marks(adapter, face, holes=True, size=0.0025):
        raise RuntimeError("failed to centre-mark the cam fixture's reams")
    for view in (face, edge, iso):
        set_hidden_lines_removed(adapter, view)
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)
    add_note(adapter, part.FUNCTION_NOTE, *FUNCTION_NOTE_XY)
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
