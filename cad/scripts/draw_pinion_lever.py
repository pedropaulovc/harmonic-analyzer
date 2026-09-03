r"""Create the curated machinist drawing for the pinion engage lever.

A clamp hub (Ø13 OD, Ø6.3675 bore) with a tapered grip rod (Ø4 at the hub to Ø6
at the tip) rising 86 mm out of it.  The rod-revolve and hub sketches both live
on the Front plane, so every marked dimension imports into the FRONT view; the
top view (looking down the grip) carries the hub length and the grip station,
both from the flat end, plus the crown radius; SECTION A-A (cut on the top
view along the bore axis) opens the blind bore so its full-diameter depth is a
real edge, with the end wall and crown height as (REF) sizes.

The print is deliberately plain (cad/docs/drawing-simplicity-policy.md): a
lever that turns with its rod carries no datums, frames or roughness
symbols; the bore band rides the model bore and nothing is dimensioned to a
hidden line (rule 7).

Run with SolidWorks open::

    uv run python cad\scripts\draw_pinion_lever.py pinion-lever
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_edge_dimension,
    add_property_linked_note,
    add_view_centerline,
    create_section_view,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_arc_endpoints_to_center,
    set_dimension_callouts,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    set_reference_dimensions,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from pinion_lever_spec import (
    CAP_SAG,
    HUB_LEN,
    HUB_OD,
    ROD_LEN,
    ROD_ROOT_DIA,
    ROD_TIP_DIA,
)
from solidworks_mcp.adapters import sw_type_info as _sw_type_info
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    dimension_name,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["pinion_lever"]
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

SHEET_SCALE = (1.0, 1.0)

# Front view (XY): the hub is a Ø13 circle at the origin with the tapered rod
# rising +Y to the tip (model y=ROD_LEN).  bbox y runs -HUB_OD/2..ROD_LEN.
FRONT_BBOX_CY = (ROD_LEN - HUB_OD / 2.0) / 2.0
# At 1:1 the full 86 mm rod leaves enough room for the hub callouts without
# crowding the orthographic views.
FRONT_CENTER = (0.078, 0.170)
# The long axial section stays right of the front-view half-angle note.  Its
# dimension text uses fixed, surveyed sheet lanes below and above the cut.
SECTION_CENTER = (0.240, 0.185)
# Top view (XZ, looking down the grip): the hub square with the crown up
# (SolidWorks' *Top puts model +Z down the sheet).  bbox z runs
# -(HUB_LEN/2 + CAP_SAG)..HUB_LEN/2.
TOP_BBOX_CZ = (HUB_LEN / 2.0 - (HUB_LEN / 2.0 + CAP_SAG)) / 2.0
TOP_CENTER = (0.290, 0.135)
# Shift the isometric right so the crown-radius annotation can use a dedicated
# lane below the top view without crossing the isometric rod.
ISO_CENTER = (0.370, 0.125)


def _front_x(model_x_mm: float) -> float:
    return FRONT_CENTER[0] + model_x_mm * SHEET_SCALE[0] / 1000.0


def _front_y(model_y_mm: float) -> float:
    return FRONT_CENTER[1] + (model_y_mm - FRONT_BBOX_CY) * SHEET_SCALE[0] / 1000.0


def _top_x(model_x_mm: float) -> float:
    return TOP_CENTER[0] + model_x_mm * SHEET_SCALE[0] / 1000.0


def _top_y(model_z_mm: float) -> float:
    """Sheet Y of a model-Z station in the top view (crown up)."""
    return TOP_CENTER[1] - (model_z_mm - TOP_BBOX_CZ) * SHEET_SCALE[0] / 1000.0


FRONT_KEEP = {
    "HubOd": (0.025, 0.102),
    "HubBore": (0.115, 0.085),
    "RodTipY": (0.044, 0.170),
    "RodTipDia": (0.125, 0.250),
    "GripHalfAngle": (0.135, 0.205),
}
TOP_KEEP = {"CapR": (0.305, 0.110)}
# The section dimensions remain imported model dimensions, while their text
# positions are direct sheet lanes surveyed around the section outline.  This
# avoids treating model +Y (the horizontal rod axis in this view) as sheet-up,
# which previously stacked the depth, end-wall and crown-height annotations.
SECTION_KEEP = {
    "BoreDepth": (0.260, 0.158),
    "EndWall": (0.205, 0.215),
    "CapSagDim": (0.290, 0.215),
}
SECTION_LABEL_XY = (0.220, 0.142)
# Process only; every band rides its model dimension (build_pinion_lever).
DIMENSION_CALLOUTS = {
    "HubBore": "BORE",
    "BoreDepth": "FULL-DIA DEPTH; FLAT BOTTOM",
    "EndWall": "END WALL",
    "RodTipY": "FROM HUB AXIS",
    "RodTipDia": "AT TIP",
    "GripHalfAngle": "GRIP HALF-ANGLE TO AXIS",
    "CapR": "SPHERICAL CROWN",
}
FRONT_DIAMETERS = ("HubOd", "HubBore")
# Top view: both hub stations from the flat end -- one origin.
HUB_LENGTH_TEXT_XY = (0.306, (_top_y(HUB_LEN / 2.0) + _top_y(-HUB_LEN / 2.0)) / 2.0)
GRIP_STATION_TEXT_XY = (0.274, (_top_y(HUB_LEN / 2.0) + _top_y(0.0)) / 2.0)

_ARROWS_OUTSIDE = 1  # swDimensionArrowsSide_e.swDimArrowsOutside


def _leaders_to_circumference(
    adapter: Any, annotations: list[Any], names: tuple[str, ...], *, label: str
) -> None:
    """End each named diameter leader at the nearest circumference.

    SolidWorks' default runs a diameter dimension line across the circle
    through its centre; with the arrows OUTSIDE the leader stops at the rim it
    names (drawing-simplicity-policy.md rule 7: never through a bore).
    """
    remaining = set(names)
    for annotation in annotations:
        annotation = _sw_type_info.early_bound_or_flag(
            annotation, "IAnnotation", "GetSpecificAnnotation"
        )
        name = dimension_name(adapter, annotation)
        if name not in remaining:
            continue
        display = _sw_type_info.early_bound_or_flag(
            annotation.GetSpecificAnnotation(), "IDisplayDimension", "ArrowSide"
        )
        display.ArrowSide = _ARROWS_OUTSIDE
        if int(display.ArrowSide) != _ARROWS_OUTSIDE:
            raise RuntimeError(f"{label}: {name} arrows did not move outside")
        remaining.discard(name)
    if remaining:
        raise RuntimeError(f"{label}: diameter dimensions not found: {sorted(remaining)}")
    adapter.currentModel.EditRebuild3()


def _move_view_label(adapter: Any, view: Any, xy: tuple[float, float], *, label: str) -> None:
    """Move the generated SECTION caption across both API exposure paths."""
    notes = list(adapter._attempt(lambda: view.GetNotes(), default=None) or ())
    if not notes:
        note = adapter._attempt(lambda: view.GetFirstNote2(), default=None)
        while note is not None:
            notes.append(note)
            note = adapter._attempt(lambda current=note: current.GetNext(), default=None)

    moved = False
    for note in notes:
        text = str(adapter._attempt(lambda item=note: item.GetText(), default="") or "")
        if "SECTION" not in text.upper() and "<VIEW" not in text.upper() and len(notes) != 1:
            continue
        annotation = _sw_type_info.early_bound_or_flag(
            note.GetAnnotation(), "IAnnotation", "SetPosition2"
        )
        if not annotation.SetPosition2(float(xy[0]), float(xy[1]), 0.0):
            raise RuntimeError(f"{label}: failed to move the section label")
        moved = True

    if not moved:
        annotations = list(
            adapter._attempt(lambda: view.GetAnnotations(), default=None) or ()
        )
        if not annotations:
            annotation = adapter._attempt(lambda: view.GetFirstAnnotation3(), default=None)
            while annotation is not None:
                annotations.append(annotation)
                annotation = adapter._attempt(
                    lambda current=annotation: current.GetNext3(), default=None
                )
        for annotation in annotations:
            specific = adapter._attempt(
                lambda item=annotation: item.GetSpecificAnnotation(), default=None
            )
            text = str(
                adapter._attempt(lambda item=specific: item.GetText(), default="") or ""
            )
            if "SECTION" not in text.upper() and "<VIEW" not in text.upper():
                continue
            annotation = _sw_type_info.early_bound_or_flag(
                annotation, "IAnnotation", "SetPosition2"
            )
            if not annotation.SetPosition2(float(xy[0]), float(xy[1]), 0.0):
                raise RuntimeError(f"{label}: failed to move the section label")
            moved = True
    if not moved:
        raise RuntimeError(f"{label}: section label annotation not found")
    adapter.currentModel.EditRebuild3()


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open pinion-lever source", await adapter.open_model(str(SOURCE)))
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
    drawing_model, sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Pinion Engage Lever Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "pinion engage lever; clamp hub; tapered grip rod",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(1, 1))
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(1, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 1))
    set_hidden_lines_removed(adapter, iso)

    # SECTION A-A: cut the top view along the bore axis (model x 0, the grip's
    # own plane) so the blind bore, its flat bottom and the end wall are open
    # geometry -- the bore depth is never dimensioned to a hidden line.
    section = create_section_view(
        adapter,
        top,
        line_start=(TOP_CENTER[0], _top_y(HUB_LEN / 2.0) - 0.011),
        line_end=(TOP_CENTER[0], _top_y(-(HUB_LEN / 2.0 + CAP_SAG)) + 0.011),
        view_xy=SECTION_CENTER,
        section_label="A",
        scale=(1, 1),
        label="lever hub section",
    )
    # Hidden lines ON in every orthographic view (policy rule 7).
    for view in (front, section, top):
        set_hidden_lines_visible(adapter, view)

    section_keep = dict(SECTION_KEEP)

    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    section_annotations = curate_view_dimensions(
        adapter, section, keep=section_keep, view_label="section"
    )
    top_annotations = curate_view_dimensions(
        adapter, top, keep=TOP_KEEP, view_label="top"
    )
    set_dimension_callouts(
        adapter,
        [*front_annotations, *section_annotations, *top_annotations],
        DIMENSION_CALLOUTS,
    )
    # The end wall (bore depth and hub length both run from the flat end) and
    # the crown height (sphere radius over the hub diameter) are derived:
    # parenthesised as REFERENCE.
    set_reference_dimensions(adapter, section_annotations, ["EndWall", "CapSagDim"])
    _leaders_to_circumference(
        adapter, front_annotations, FRONT_DIAMETERS, label="front diameters"
    )
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to front view")

    grip_edge = (_front_x(ROD_ROOT_DIA / 2.0), _front_y(12.0))
    add_view_centerline(
        adapter,
        front,
        face_xy=grip_edge,
        label="lever tapered grip axis",
    )

    # Top view, one origin (the flat end): the hub length to the crown-root
    # rim (a visible line, the cylinder/cap edge) and the grip station to the
    # rod's tip circle (the circular pick snaps to the axis).  Picks stay on
    # one side of the section line.
    add_edge_dimension(
        adapter,
        top,
        p0=(_top_x(4.5), _top_y(HUB_LEN / 2.0)),
        p1=(_top_x(2.5), _top_y(-HUB_LEN / 2.0)),
        text_xy=HUB_LENGTH_TEXT_XY,
        label="flat end to crown root",
        orientation="vertical",
    )
    grip_station = add_edge_dimension(
        adapter,
        top,
        p0=(_top_x(-2.5), _top_y(HUB_LEN / 2.0)),
        p1=(_top_x(-ROD_TIP_DIA / 2.0), _top_y(0.0)),
        text_xy=GRIP_STATION_TEXT_XY,
        label="flat end to grip axis",
        orientation="vertical",
    )
    set_arc_endpoints_to_center(adapter, grip_station, label="flat end to grip axis")
    _move_view_label(
        adapter,
        section,
        SECTION_LABEL_XY,
        label="lever section",
    )

    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.070)
    add_property_linked_note(adapter, "Isometric View Note", 0.350, 0.078)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Pinion Engage Lever Manufacturing Drawing",
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
