r"""Create the curated machinist drawing for the pinion swing bracket.

The SLDPRT remains authoritative.  This recipe supplies only the strap's
views, dimension layout, hole callouts, and manufacturing notes; every shared
sheet/template, import, curation, and export behavior lives in
``_drawing_common``.

The sheet runs at 2:1 (the strap is 43 mm end to end).  Third-angle layout:
the LEFT view (the -X flank the blind stud seat enters) sits left of the
front view and carries the seat's diameter and its station through the
thickness as visible circles; the front view carries the face (both bores,
both end radii, the (REF) overall, the seat's rise above the pivot); SECTION
A-A (cut on the left view through the seat axis) opens the seat so its
full-diameter depth and strap thickness are real edges. A compact coordinate
block beside the front locates both R6.90 cam scallops from the pivot bore.
The isometric carries a 1:1 override to stay clear of the title block.

The print is deliberately plain (cad/docs/drawing-simplicity-policy.md): a
swing strap carries no datums, frames, basics or roughness symbols; the bore
bands ride the model dimensions and nothing is dimensioned to a hidden line
(rule 7).

Run with SolidWorks open::

    uv run python cad\scripts\draw_pinion_bracket.py pinion-bracket
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
    add_edge_dimension,
    add_property_linked_note,
    create_section_view,
    curate_view_dimensions,
    finalize_drawing,
    model_point_in_view,
    new_project_drawing,
    read_required_properties,
    set_arc_endpoints_to_max,
    set_dimension_callouts,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from pinion_bracket_geometry import (
    CAM_RELIEF_ENGAGED_CENTER,
    CAM_RELIEF_PARK_CENTER,
    CAM_RELIEF_RADIUS,
)
from pinion_bracket_spec import (
    C2C as C2C,
    OVERALL_LENGTH,
    PIN_DROP,
    R_END,
)
from solidworks_mcp.adapters import sw_type_info as _sw_type_info
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    auto_center_marks,
    dimension_name,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["pinion_bracket"]
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

SHEET_SCALE = (2.0, 1.0)

# Sheet layout (meters).  The strap runs UP the sheet: the front view's model
# bbox is +/-7.5 in X and -7.5..35.5 in Y (43 tall); at 2:1 the view is
# 30 x 86 mm.  The left view (5 thick) shares the front's Y span.
FRONT_BBOX_CY = (OVERALL_LENGTH / 2.0) - R_END  # 14.0: (35.5 + -7.5) / 2
# The left view's seat callouts (~40 mm wide) sit between it and the front
# view's outermost left-hand dimension, so the front stands 105 mm right.
LEFT_CENTER = (0.045, 0.150)
FRONT_CENTER = (0.150, 0.150)
# The section occupies the free upper-right field above the isometric, well
# clear of the front-view dimensions and the scallop coordinate block.
SECTION_CENTER = (0.290, 0.235)
# The isometric and its caption sit clear of the title block (top ~0.0655).
ISO_CENTER = (0.365, 0.120)


def _front_x(model_x_mm: float) -> float:
    """Sheet X of a model-X point in the front view (2:1, bbox-centred)."""
    return FRONT_CENTER[0] + model_x_mm * SHEET_SCALE[0] / 1000.0


def _front_y(model_y_mm: float) -> float:
    """Sheet Y of a model-Y point in the front/left views (2:1, bbox-centred)."""
    return FRONT_CENTER[1] + (model_y_mm - FRONT_BBOX_CY) * SHEET_SCALE[0] / 1000.0


# Per-view survivors of the marked-dimension import: parametric name -> sheet
# position.  Front: the pivot->seat rise and the bore-to-bore distance stack
# to the RIGHT of the strap, the (REF) overall stands alone on the LEFT; the
# arbor bore and top radius lead up-right (12 mm apart), the pivot bore and
# bottom radius lower-right -- no leader crosses a dimension line and nothing
# crosses the overall's extension lines.
FRONT_KEEP = {
    "ArborBoreCz": (0.189, _front_y(C2C / 2.0)),
    "PinSeatCy": (0.175, _front_y(-PIN_DROP / 2.0)),
    "ArborBoreDia": (0.195, 0.190),
    "TopCapRadius": (0.175, 0.205),
    "PivotBoreDia": (0.187, 0.099),
    "BottomCapRadius": (0.175, 0.078),
}
# Left view: the seat mouth is a visible circle on the -X flank; its callouts
# sit in the gap between the two views.
LEFT_KEEP = {
    "PinSeatDia": (0.075, 0.150),
    "PinSeatCz": (0.060, 0.098),
}
# Section dimension positions are offsets from the projected model origin at
# the y=6 seat-axis cut. SolidWorks chooses the section's mirror, so positions
# derive from projected axes. The seat depth stands on the +Z side. The strap
# thickness sits 10 mm down and 15 mm toward -Z, above the automatic label.
SECTION_KEEP = {
    "PinSeatDepth": (-0.011, 0.014),
    "Depth": (0.010, -0.015),
}
# Park the section label to the left if SolidWorks exposes it as a note.
SECTION_LABEL_XY = (SECTION_CENTER[0] - 0.050, SECTION_CENTER[1])
# The scallops' marked model dimensions stay owned by one compact coordinate
# block beside the front view. Its values come from the geometry constants,
# and its origin and directions name the pivot-bore centreline explicitly.
CAM_SCALLOP_NOTE_DIMENSIONS = frozenset(
    {
        "CamReliefParkDia",
        "CamReliefParkX",
        "CamReliefParkY",
        "CamReliefEngagedX",
        "CamReliefEngagedY",
    }
)
CAM_SCALLOP_COORDINATE_NOTE = "\n".join(
    (
        "ORIGIN PIVOT BORE C/L; +X RIGHT, +Y UP",
        f"PARK X {CAM_RELIEF_PARK_CENTER[0]:+.2f} Y {CAM_RELIEF_PARK_CENTER[1]:+.2f}",
        f"ENG X {CAM_RELIEF_ENGAGED_CENTER[0]:+.2f} Y {CAM_RELIEF_ENGAGED_CENTER[1]:+.2f}",
        f"2X <MOD-DIAM>{2.0 * CAM_RELIEF_RADIUS:.2f} CAM SCALLOPS",
    )
)
CAM_SCALLOP_NOTE_XY = (0.230, 0.170)
OVERALL_TEXT_XY = (0.115, _front_y(C2C / 2.0))
# Process only; every band rides its model dimension (build_pinion_bracket).
DIMENSION_CALLOUTS = {
    "PivotBoreDia": "REAM THRU",
    "ArborBoreDia": "REAM THRU",
    "PinSeatDia": "REAM; FLAT BOTTOM",
    "PinSeatDepth": "FULL-DIAMETER DEPTH",
}
FRONT_DIAMETERS = ("ArborBoreDia", "PivotBoreDia")
LEFT_DIAMETERS = ("PinSeatDia",)

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
        raise RuntimeError(
            f"{label}: diameter dimensions not found: {sorted(remaining)}"
        )
    adapter.currentModel.EditRebuild3()


def _section_frame(
    adapter: Any, section: Any, *, label: str
) -> tuple[tuple[float, float], tuple[float, float], tuple[float, float]]:
    """Sheet origin and unit directions of model +X and +Z in ``section``."""
    origin = model_point_in_view(
        adapter, section, (0.0, 0.0, 0.0), label=f"{label} origin"
    )

    def unit(xyz: tuple[float, float, float]) -> tuple[float, float]:
        point = model_point_in_view(adapter, section, xyz, label=f"{label} axis")
        dx, dy = point[0] - origin[0], point[1] - origin[1]
        norm = math.hypot(dx, dy)
        if norm < 1e-6:
            raise RuntimeError(f"{label}: model axis {xyz} projects to a point")
        return (dx / norm, dy / norm)

    return origin, unit((0.01, 0.0, 0.0)), unit((0.0, 0.0, 0.01))


def _at(
    origin: tuple[float, float],
    first: tuple[float, float],
    second: tuple[float, float],
    offsets: tuple[float, float],
) -> tuple[float, float]:
    a, b = offsets
    return (
        origin[0] + first[0] * a + second[0] * b,
        origin[1] + first[1] * a + second[1] * b,
    )


def _move_view_label(
    adapter: Any, view: Any, xy: tuple[float, float], *, keyword: str, label: str
) -> None:
    """Park the view's SECTION label where no dimension sits beneath it."""
    notes = list(adapter._attempt(lambda: view.GetNotes(), default=None) or ())
    if not notes:
        note = adapter._attempt(lambda: view.GetFirstNote(), default=None)
        while note is not None:
            notes.append(note)
            note = adapter._attempt(lambda n=note: n.GetNext(), default=None)
    moved = False
    for note in notes:
        note = _sw_type_info.early_bound_or_flag(
            note, "INote", "GetText", "GetAnnotation"
        )
        text = str(adapter._attempt(lambda n=note: n.GetText(), default="") or "")
        if keyword not in text.upper():
            continue
        annotation = _sw_type_info.early_bound_or_flag(
            note.GetAnnotation(), "IAnnotation", "SetPosition2"
        )
        if not annotation.SetPosition2(float(xy[0]), float(xy[1]), 0.0):
            raise RuntimeError(f"{label}: failed to move the {keyword} label")
        moved = True
    if not moved:
        _telemetry.warn(
            f"{label}: {keyword} label note not found; left at its default spot"
        )
    adapter.currentModel.EditRebuild3()


def _parenthesize(adapter: Any, display: Any, *, label: str) -> None:
    """Mark a drawing-native dimension as REFERENCE (ASME parentheses)."""
    display = _sw_type_info.early_bound_or_flag(
        display, "IDisplayDimension", "SetText", "GetText"
    )
    display.SetText(1, "(")  # swDimensionTextPrefix
    display.SetText(2, ")")  # swDimensionTextSuffix
    prefix = str(display.GetText(1) or "")
    suffix = str(display.GetText(2) or "")
    if (prefix, suffix) != ("(", ")"):
        raise RuntimeError(
            f"failed to parenthesize {label}: prefix={prefix!r}, suffix={suffix!r}"
        )
    adapter.currentModel.EditRebuild3()


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open pinion-bracket source", await adapter.open_model(str(SOURCE)))
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
            0: "Pinion Swing Bracket Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "pinion swing bracket; manufacturing drawing; pivot strap",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    # Explicit per-view scale: a view placed without one can silently
    # auto-scale, which shifts every coordinate-based pick on it.
    left = place_view(adapter, str(SOURCE), "*Left", *LEFT_CENTER, scale=(2, 1))
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(2, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 1))
    set_hidden_lines_removed(adapter, iso)

    # SECTION A-A: cut the left view through the stud-seat axis (model y 6,
    # the plane the seat's axis lies in) so the blind seat is an open notch
    # in the 15 x 5 cross-section -- its depth is never dimensioned to a
    # hidden line.  At y 6 the scallops have not reached the flank, so the
    # cut is the plain rectangle plus the notch.
    seat_axis_y = _front_y(-PIN_DROP)
    section = create_section_view(
        adapter,
        left,
        line_start=(LEFT_CENTER[0] - 0.015, seat_axis_y),
        line_end=(LEFT_CENTER[0] + 0.015, seat_axis_y),
        view_xy=SECTION_CENTER,
        section_label="A",
        scale=(2, 1),
        label="stud seat section",
    )
    # Hidden lines ON in every orthographic view (policy rule 7).
    for view in (left, front, section):
        set_hidden_lines_visible(adapter, view)

    origin, x_axis, z_axis = _section_frame(adapter, section, label="seat section")
    down = (x_axis[0], x_axis[1]) if x_axis[1] < 0.0 else (-x_axis[0], -x_axis[1])
    section_keep = {
        "PinSeatDepth": _at(origin, x_axis, z_axis, SECTION_KEEP["PinSeatDepth"]),
        "Depth": _at(origin, down, z_axis, SECTION_KEEP["Depth"]),
    }

    # The front projection already shows both open cam scallops clearly.
    # State their signed centres and common diameter in one coordinate block;
    # an enlargement of their open boundary adds no manufacturing information.
    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    left_annotations = curate_view_dimensions(
        adapter, left, keep=LEFT_KEEP, view_label="left"
    )
    section_annotations = curate_view_dimensions(
        adapter, section, keep=section_keep, view_label="section"
    )
    if add_note(adapter, CAM_SCALLOP_COORDINATE_NOTE, *CAM_SCALLOP_NOTE_XY) is None:
        raise RuntimeError("failed to add cam scallop coordinate block")

    # (REF) overall: bottom arc extreme to top arc extreme, alone on the left
    # so no leader has to cross its extension lines.  The bore-to-bore 28.00
    # stays the controlling dimension; with both R7.50 caps the overall is
    # derived.
    overall = add_edge_dimension(
        adapter,
        front,
        p0=(_front_x(0.0), _front_y(-R_END)),
        p1=(_front_x(0.0), _front_y(C2C + R_END)),
        text_xy=OVERALL_TEXT_XY,
        label="strap overall length",
        orientation="vertical",
    )
    set_arc_endpoints_to_max(adapter, overall, label="strap overall length")
    _parenthesize(adapter, overall, label="strap overall length")

    set_dimension_callouts(
        adapter,
        [*front_annotations, *left_annotations, *section_annotations],
        DIMENSION_CALLOUTS,
    )
    _leaders_to_circumference(
        adapter, front_annotations, FRONT_DIAMETERS, label="front diameters"
    )
    _leaders_to_circumference(
        adapter, left_annotations, LEFT_DIAMETERS, label="left diameters"
    )

    for view, label in ((front, "front"), (left, "left")):
        if not auto_center_marks(adapter, view, holes=True, size=0.0025):
            raise RuntimeError(f"failed to add ASME center marks to {label} view")

    _move_view_label(
        adapter,
        section,
        SECTION_LABEL_XY,
        keyword="SECTION",
        label="stud seat section",
    )

    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.060)
    add_property_linked_note(adapter, "Isometric View Note", 0.345, 0.088)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Pinion Swing Bracket Manufacturing Drawing",
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
