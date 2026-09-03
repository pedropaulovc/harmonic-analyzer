r"""Create the curated machinist drawing for the pinion cam-follower pin.

A short Ø4 turned steel stud with a shallow domed outer end.  The sheet runs at
4:1 (the pin is only 17.8 mm long): an 8:1 end view carries the diameter, the
4:1 side view carries the lengths, and a 4:1 isometric (matching the sheet
scale) sits clear of the title block.

The side view is the ``*Top`` named view (the crown radius belongs to a sketch
on the Top plane, and only a view facing that plane imports ``CapR``
natively), so the pin's axis reads VERTICAL on the sheet: seated end up, crown
down.  The 17.00 to the crown root sits right of the pin, and a view-adjacent
geometry-derived ``(17.80) OVERALL REF`` note makes the seated-end-to-apex
envelope conspicuous without depending on the crown apex as a selectable
drawing vertex (machinist review 2026-09-02).  The crown radius is called out
as a spherical radius (``SR``) below the crown, its REF height is flagged from
the crown itself, and the isometric explicitly shows the crown-root edge.

The print is deliberately plain (cad/docs/drawing-simplicity-policy.md): a
pressed stud carries no datums, frames or roughness symbols -- the press band
rides the model diameter at three decimals.

Run with SolidWorks open::

    uv run python cad\scripts\draw_pinion_cam_pin.py pinion-cam-pin
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_attached_note,
    add_property_linked_note,
    add_view_centerline,
    curate_view_dimensions,
    finalize_drawing,
    model_point_in_view,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_dimension_precision,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from pinion_cam_pin_spec import (
    CAP_RADIUS,
    CAP_SAG,
    OVERALL_LEN,
    PIN_DIA as PIN_DIA,
    PIN_LEN,
)
from solidworks_mcp.adapters import sw_type_info as _sw_type_info
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    auto_center_marks,
    dimension_name,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["pinion_cam_pin"]
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

SHEET_SCALE = (4.0, 1.0)
END_VIEW_SCALE = 8.0
FRONT_CENTER = (0.070, 0.200)
RIGHT_CENTER = (
    FRONT_CENTER[0] + PIN_LEN * SHEET_SCALE[0] / 2000.0 + 0.055,
    FRONT_CENTER[1],
)
ISO_CENTER = (0.320, 0.200)

FRONT_KEEP = {
    "PinDia": (0.030, 0.235),
}
# The pin stands vertical in the side view: the length to the crown root
# right of the pin, the crown radius just below-right of the apex (a radial
# leader runs toward the sphere centre, so the text must sit within the
# dome's 43-degree half-span or the leader lands on the virtual circle).
RIGHT_KEEP = {
    "Depth": (RIGHT_CENTER[0] + 0.040, RIGHT_CENTER[1]),
    "CapR": (RIGHT_CENTER[0] + 0.012, RIGHT_CENTER[1] - 0.052),
}
DIMENSION_CALLOUTS = {
    "Depth": "TO CROWN ROOT",
    "CapR": "SPHERICAL CROWN",
}
SPHERICAL_RADIUS_DIMENSION = "CapR"
OVERALL_NOTE = f"({OVERALL_LEN:.2f}) OVERALL REF"
OVERALL_NOTE_XY = (RIGHT_CENTER[0] - 0.030, RIGHT_CENTER[1] + 0.040)
# Flag note right of the crown, low enough that its leader passes under the
# 17.00's dimension line and over the SR text.
CROWN_NOTE_XY = (0.250, 0.150)

_TEXT_PREFIX = 1  # swDimensionTextParts_e.swDimensionTextPrefix
_TANGENT_EDGES_VISIBLE = 2  # swDisplayTangentEdges_e.swTangentEdgesVisible



def _spherical_radius_prefix(
    adapter: Any, annotations: list[Any], name: str, *, label: str
) -> None:
    """Make one imported radius read ``SR`` (a spherical radius, ASME Y14.5).

    A custom prefix REPLACES the automatic glyph (the same mechanism
    ``_drawing_common.set_reference_dimensions`` documents for the diameter's
    ``<MOD-DIAM>``), so the prefix is rewritten to ``SR`` whether SolidWorks
    reports the radial ``R`` there or an empty compartment; any other text is
    something this sheet does not know how to spell, so it fails loud instead
    of printing ``SRR``.
    """
    for annotation in annotations:
        annotation = _sw_type_info.early_bound_or_flag(
            annotation, "IAnnotation", "GetSpecificAnnotation"
        )
        if dimension_name(adapter, annotation) != name:
            continue
        display = _sw_type_info.early_bound_or_flag(
            annotation.GetSpecificAnnotation(), "IDisplayDimension", "SetText", "GetText"
        )
        existing = str(display.GetText(_TEXT_PREFIX) or "").strip()
        if existing not in ("R", ""):
            raise RuntimeError(f"{label}: unexpected radius prefix {existing!r}")
        prefix = "SR"
        display.SetText(_TEXT_PREFIX, prefix)
        if str(display.GetText(_TEXT_PREFIX) or "") != prefix:
            raise RuntimeError(f"{label}: prefix {prefix!r} did not persist")
        adapter.currentModel.EditRebuild3()
        return
    raise RuntimeError(f"{label}: dimension {name!r} not found")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open pinion-cam-pin source", await adapter.open_model(str(SOURCE)))
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
            "End View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "End View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Pinion Cam-Follower Pin Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "pinion cam-follower pin; turned stud; steel",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(8, 1))
    right = place_view(adapter, str(SOURCE), "*Top", *RIGHT_CENTER, scale=(4, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(4, 1))
    set_hidden_lines_removed(adapter, iso)
    # Force the crown-root transition circle into the isometric instead of
    # letting the view style visually blend the spherical cap into the shank.
    iso.SetDisplayTangentEdges2(_TANGENT_EDGES_VISIBLE)
    if int(iso.GetDisplayTangentEdges2()) != _TANGENT_EDGES_VISIBLE:
        raise RuntimeError("failed to show cam-pin crown-root edge")
    iso.UpdateViewDisplayGeometry()
    for view in (front, right):
        set_hidden_lines_visible(adapter, view)

    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    right_annotations = curate_view_dimensions(
        adapter, right, keep=RIGHT_KEEP, view_label="right"
    )
    set_dimension_callouts(
        adapter, [*front_annotations, *right_annotations], DIMENSION_CALLOUTS
    )
    set_dimension_precision(adapter, front_annotations, {"PinDia": 3})
    _spherical_radius_prefix(
        adapter, right_annotations, SPHERICAL_RADIUS_DIMENSION, label="crown SR"
    )
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to pin end view")

    # The overall is reference information derived from the same geometry
    # contract as the model.  A view-adjacent note is deliberate: the shallow
    # revolved apex is not a stable selectable drawing vertex.
    if add_note(adapter, OVERALL_NOTE, *OVERALL_NOTE_XY) is None:
        raise RuntimeError("failed to add cam-pin overall reference note")

    add_view_centerline(
        adapter,
        right,
        face_xy=(RIGHT_CENTER[0], RIGHT_CENTER[1] + 0.004),
        label="pinion cam-pin shank axis centerline",
    )
    # The crown's REF height, flagged from the crown itself.
    crown_axial = CAP_SAG / 2.0
    crown_radial = math.sqrt(CAP_RADIUS**2 - (CAP_RADIUS - CAP_SAG + crown_axial) ** 2)
    outer_crown_face = model_point_in_view(
        adapter,
        right,
        (
            crown_radial / 1000.0,
            0.0,
            (PIN_LEN + crown_axial) / 1000.0,
        ),
        label="pinion cam-pin outer crown face",
    )
    add_attached_note(
        adapter,
        right,
        text=f"CROWN ({CAP_SAG:.2f}) HIGH\nROOT PLANE TO APEX",
        entity_xy=outer_crown_face,
        note_xy=CROWN_NOTE_XY,
        label="cam-pin crown size and height",
        entity_type="SILHOUETTE",
    )

    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.110)
    add_property_linked_note(adapter, "End View Note", 0.020, 0.168)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Pinion Cam-Follower Pin Manufacturing Drawing",
        scale=SHEET_SCALE,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
