r"""Create the curated machinist drawing for the pinion turning handle.

A bright tee: a Ø15 grip cylinder on the arbor axis (Z) with a domed south
cap, a Ø6 cross rod through the grip (arms 32/33 along Y), and a blind tubular
hub (Ø10.5 OD, Ø8 ID) that swallows the Ø8 arbor stub.  The grip and tube
sketch on the Front plane (front view carries the turned diameters and the rod
span); the right view is the plain silhouette the cut line is drawn on; the
axial section (XZ through the arbor axis, parallel to the Top plane) carries
every length: the grip and bore-depth lengths, the cross-hole station from the
grip shoulder and from the hub end, the rod and hole diameters at the rod's
cut, and the crown radius and (REF) height.

The print is deliberately plain (cad/docs/drawing-simplicity-policy.md): a
turned tee that is locked to its arbor carries no datums, frames, basics or
roughness symbols; the press and ream bands ride the model dimensions and the
turned lengths take the title-block tolerance.  Nothing is dimensioned to a
hidden line (rule 7): the bore depth lives on the section.

Run with SolidWorks open::

    uv run python cad\scripts\draw_pinion_handle.py pinion-handle
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
    set_arc_endpoints_to_center,
    set_dimension_callouts,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    set_reference_dimensions,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from pinion_handle_spec import (
    GRIP_DIA,
    GRIP_LEN,
    ROD_DIA,
    ROD_DOWN,
    ROD_UP,
    TUBE_ID,
    TUBE_LEN,
    TUBE_OD,
    WALL_T,
)
from solidworks_mcp.adapters import sw_type_info as _sw_type_info
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    dimension_name,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["pinion_handle"]
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

# Front view (XY, looking down the arbor axis Z): the grip Ø15 disc sits at the
# origin with the Ø6 cross rod running vertically through it (model y -32..+33).
# Lift the view a touch above centre so the rod bottom clears the notes band.
FRONT_BBOX_CY = (ROD_UP - ROD_DOWN) / 2.0
FRONT_CENTER = (0.072, 0.155)
# Right view (YZ): the plain tee silhouette the section line is drawn across
# (its end letters reach ~30 mm either side of the view centre).
RIGHT_CENTER = (0.172, 0.155)
# SECTION A-A (XZ through the arbor axis): every axial length lives here; the
# crown-side callouts reach ~55 mm left of the model origin.
SECTION_CENTER = (0.278, 0.135)
ISO_CENTER = (0.320, 0.210)


def _front_x(model_x_mm: float) -> float:
    return FRONT_CENTER[0] + model_x_mm * SHEET_SCALE[0] / 1000.0


def _front_y(model_y_mm: float) -> float:
    return FRONT_CENTER[1] + (model_y_mm - FRONT_BBOX_CY) * SHEET_SCALE[0] / 1000.0


# Front view: the three turned diameters fan out to the RIGHT of the grip at
# spread angles (one leader each, ending at its own circumference) and the rod
# span stands outboard of them; the lower-arm station sits alone on the left.
FRONT_KEEP = {
    "GripDia": (0.100, 0.190),
    "TubeOd": (0.102, 0.155),
    "TubeId": (0.100, 0.118),
    "RodSpan": (0.125, 0.245),
}
RIGHT_KEEP: dict[str, tuple[float, float]] = {}
# Section: parametric name -> (up, along +Z) offsets in metres from the
# projected model origin.  The section's mirror is SolidWorks' choice, so the
# positions are derived at build time from the projected axes (``_section_frame``)
# rather than assumed: "up" is whichever of +/-X points up the sheet, +Z runs
# from the crown toward the hub end.  The axial lengths share a row but sit on
# opposite ends of the body.  The spherical-crown leader is moved farther
# crownward, outside the 9.00 / CYL. LENGTH text box, and the two cross-hole
# station dimensions use higher, separate rows.
SECTION_KEEP = {
    "GripLen": (0.026, -0.005),
    "TubeLen": (0.026, 0.033),
    "RodDia": (0.004, -0.036),
    "RodHoleDia": (-0.012, -0.036),
    "CapR": (0.034, -0.060),
    "CapSagDim": (-0.021, -0.012),
}
CROSS_HOLE_SHOULDER_OFFSET = (0.038, (GRIP_LEN / 2.0) / 2.0 * SHEET_SCALE[0] / 1000.0)
CROSS_HOLE_HUB_END_OFFSET = (0.047, None)  # along-Z filled from z_max at runtime
SECTION_LABEL_OFFSET = (-0.032, -0.005)
# Process only; every band rides its model dimension (build_pinion_handle).
DIMENSION_CALLOUTS = {
    "TubeId": "REAM",
    "GripLen": "CYL. LENGTH",
    "TubeLen": "BORE DEPTH",
    "RodSpan": "OAL",
    "RodDia": "PRESS FIT",
    "RodHoleDia": "REAM THRU",
    "CapR": "SPHERICAL CROWN",
}
FRONT_DIAMETERS = ("GripDia", "TubeOd", "TubeId")
SECTION_DIAMETERS = ("RodDia", "RodHoleDia")

_ARROWS_OUTSIDE = 1  # swDimensionArrowsSide_e.swDimArrowsOutside


def _leaders_to_circumference(
    adapter: Any, annotations: list[Any], names: tuple[str, ...], *, label: str
) -> None:
    """End each named diameter leader at the nearest circumference.

    SolidWorks' default runs a diameter dimension line across the circle
    through its centre, so three concentric callouts converge on one point.
    With the arrows OUTSIDE the leader stops at the rim it names
    (drawing-simplicity-policy.md rule 7: never through a bore).
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


def _section_frame(
    adapter: Any, section: Any, *, label: str
) -> tuple[tuple[float, float], tuple[float, float], tuple[float, float]]:
    """Sheet origin and unit directions of model +X and +Z in ``section``."""
    origin = model_point_in_view(adapter, section, (0.0, 0.0, 0.0), label=f"{label} origin")

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
    up: tuple[float, float],
    along: tuple[float, float],
    offsets: tuple[float, float],
) -> tuple[float, float]:
    u, a = offsets
    return (origin[0] + up[0] * u + along[0] * a, origin[1] + up[1] * u + along[1] * a)


def _move_view_label(adapter: Any, view: Any, xy: tuple[float, float], *, label: str) -> None:
    """Park the view's SECTION label where no dimension will sit under it."""
    notes = adapter._attempt(lambda: view.GetNotes(), default=None) or ()
    moved = False
    for note in notes:
        note = _sw_type_info.early_bound_or_flag(note, "INote", "GetText", "GetAnnotation")
        text = str(adapter._attempt(lambda n=note: n.GetText(), default="") or "")
        if "SECTION" not in text.upper():
            continue
        annotation = _sw_type_info.early_bound_or_flag(
            note.GetAnnotation(), "IAnnotation", "SetPosition2"
        )
        if not annotation.SetPosition2(float(xy[0]), float(xy[1]), 0.0):
            raise RuntimeError(f"{label}: failed to move the section label")
        moved = True
    if not moved:
        _telemetry.warn(f"{label}: section label note not found; left at its default spot")
    adapter.currentModel.EditRebuild3()


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open pinion-handle source", await adapter.open_model(str(SOURCE)))
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
            0: "Pinion Turning Handle Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "pinion turning handle; grip cylinder; cross rod; blind hub",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(2, 1))
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(2, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 1))
    set_hidden_lines_removed(adapter, iso)

    # SECTION A-A: cut the right view along the arbor axis (the grip centre
    # line, model y 0) so the blind bore, the wall and the rod's cross-section
    # are open geometry -- no length is dimensioned to a hidden line.
    grip_axis_y = RIGHT_CENTER[1] - FRONT_BBOX_CY * SHEET_SCALE[0] / 1000.0
    section = create_section_view(
        adapter,
        right,
        line_start=(RIGHT_CENTER[0] - 0.027, grip_axis_y),
        line_end=(RIGHT_CENTER[0] + 0.027, grip_axis_y),
        view_xy=SECTION_CENTER,
        section_label="A",
        scale=(2, 1),
        label="handle axial section",
    )
    # Hidden lines ON in every orthographic view (policy rule 7).
    for view in (front, right, section):
        set_hidden_lines_visible(adapter, view)

    origin, x_axis, z_axis = _section_frame(adapter, section, label="handle section")
    x_sign = 1.0 if x_axis[1] >= 0.0 else -1.0
    up = (x_axis[0] * x_sign, x_axis[1] * x_sign)
    section_keep = {
        name: _at(origin, up, z_axis, offsets) for name, offsets in SECTION_KEEP.items()
    }
    along_z = "horizontal" if abs(z_axis[0]) >= abs(z_axis[1]) else "vertical"

    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    right_annotations = curate_view_dimensions(
        adapter, right, keep=RIGHT_KEEP, view_label="right"
    )
    section_annotations = curate_view_dimensions(
        adapter, section, keep=section_keep, view_label="section"
    )
    set_dimension_callouts(
        adapter,
        [*front_annotations, *right_annotations, *section_annotations],
        DIMENSION_CALLOUTS,
    )
    # The crown height is derived from the sphere radius and the grip
    # diameter: parenthesised as REFERENCE.
    set_reference_dimensions(adapter, section_annotations, ["CapSagDim"])
    _leaders_to_circumference(
        adapter, front_annotations, FRONT_DIAMETERS, label="front diameters"
    )
    _leaders_to_circumference(
        adapter, section_annotations, SECTION_DIAMETERS, label="section diameters"
    )
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to front view")

    # Lower arm: the bore axis (the grip circle's centre) to the rod's lower
    # end, on the front view, alone on the side opposite the diameters.
    lower_arm = add_edge_dimension(
        adapter,
        front,
        p0=(_front_x(-TUBE_ID / 2.0), _front_y(0.0)),
        p1=(_front_x(0.0), _front_y(-ROD_DOWN)),
        text_xy=(0.052, _front_y(-ROD_DOWN / 2.0)),
        label="bore axis to rod lower end",
        orientation="vertical",
    )
    set_arc_endpoints_to_center(adapter, lower_arm, label="bore axis to rod lower end")

    # Cross-hole station, one origin (the hole axis): to the grip's flat
    # shoulder and to the flat hub end.  The rod's cut circle snaps the
    # dimension to the hole CENTRE (the circular pick), the shoulder and hub-end
    # cut edges are picked on the "up" side so the extension lines rise clear
    # of the section label.
    z_max = GRIP_LEN / 2.0 + WALL_T + TUBE_LEN
    hole_rim = model_point_in_view(
        adapter,
        section,
        (0.0, 0.0, -ROD_DIA / 2000.0),
        label="handle cross-hole rim",
    )
    shoulder_edge = model_point_in_view(
        adapter,
        section,
        (x_sign * (GRIP_DIA + TUBE_OD) / 4000.0, 0.0, GRIP_LEN / 2000.0),
        label="handle grip shoulder edge",
    )
    hub_end_edge = model_point_in_view(
        adapter,
        section,
        (x_sign * (TUBE_OD + TUBE_ID) / 4000.0, 0.0, z_max / 1000.0),
        label="handle flat hub end edge",
    )
    shoulder_station = add_edge_dimension(
        adapter,
        section,
        p0=hole_rim,
        p1=shoulder_edge,
        text_xy=_at(origin, up, z_axis, CROSS_HOLE_SHOULDER_OFFSET),
        label="grip shoulder to body cross-hole axis",
        orientation=along_z,
    )
    set_arc_endpoints_to_center(
        adapter, shoulder_station, label="grip shoulder to body cross-hole axis"
    )
    hub_end_station = add_edge_dimension(
        adapter,
        section,
        p0=hole_rim,
        p1=hub_end_edge,
        text_xy=_at(
            origin,
            up,
            z_axis,
            (CROSS_HOLE_HUB_END_OFFSET[0], z_max / 2.0 * SHEET_SCALE[0] / 1000.0),
        ),
        label="flat hub end to body cross-hole axis",
        orientation=along_z,
    )
    set_arc_endpoints_to_center(
        adapter, hub_end_station, label="flat hub end to body cross-hole axis"
    )
    _move_view_label(
        adapter,
        section,
        _at(origin, up, z_axis, SECTION_LABEL_OFFSET),
        label="handle section",
    )

    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.062)
    add_property_linked_note(adapter, "Isometric View Note", 0.300, 0.184)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Pinion Turning Handle Manufacturing Drawing",
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
