r"""Create the curated machinist drawing for the magnifying wheel.

A Ø100 spoked cast wheel with a Ø20 grooved hub drum (the 5x ratio) on six
straight spokes and a Ø5 reamed axle bore.  The wheel axis is local +Z, so the
FRONT view is the face (rim OD/ID, hub, spoke width, bore -- all real circular
edges, all auto-imported profile marks) and SECTION A-A -- the face cut along
its horizontal centreline, laid as a strip under the face -- carries the axial
facts: rim width, hub length, spoke thickness and the two axial stations that
place the spoke and the hub against the rim faces.  Nothing is dimensioned to a
hidden line (cad/docs/drawing-simplicity-policy.md rule 7).

The print is plain: the wheel is not on the GD&T allowlist, so it carries no
datum, no runout frame and no basic dimension; the one roughness symbol sits on
the axle bore, the surface that turns on the stud in service; the bore's ream
band rides the model dimension (build_magnifying_wheel).

Run with SolidWorks open::

    uv run python cad\scripts\draw_magnifying_wheel.py magnifying-wheel
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
    add_surface_finish,
    create_section_view,
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
from _surface_finish import surface_finish_by_key
from magnifying_wheel_spec import (
    BORE_DIA,
    HUB_AXIAL,
    HUB_DIA,
    RIM_AXIAL,
    RIM_INNER_DIA,
    RIM_OUTER_DIA,
    SPOKE_AXIAL,
    SURFACE_FINISHES,
)
from solidworks_mcp.adapters import sw_type_info as _sw_type_info
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    dimension_name,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["magnifying_wheel"]
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
_S = SHEET_SCALE[0] / 1000.0  # sheet metres per model mm
# Face view raised so the section strip fits under it, clear of the title
# block (which starts at x ~0.218, y < 0.070).
FRONT_CENTER = (0.125, 0.165)
# SECTION A-A: the face cut along its horizontal centreline (model XZ plane),
# a 100 x 10 strip laid under the face view.
SECTION_CENTER = (0.125, 0.078)
ISO_CENTER = (0.350, 0.150)

_RIM_R = RIM_OUTER_DIA * _S / 2.0
_HUB_R = HUB_DIA * _S / 2.0

# Cutting-plane line across the face view, 4 mm past the rim each side.
SECTION_LINE = (
    (FRONT_CENTER[0] - _RIM_R - 0.004, FRONT_CENTER[1]),
    (FRONT_CENTER[0] + _RIM_R + 0.004, FRONT_CENTER[1]),
)

# Face-view survivors.  Every diameter leader is aimed down a 60-degree GAP
# between spokes (spokes at 30/90/150/210/270/330 deg): the rim OD up-left
# (144 deg), the rim ID right (10 deg), the hub down (300 deg), the bore left
# and 30 mm below the cutting plane so its stacked H7 limits and REAM THRU
# never meet the section marker; the spoke width stands above the rim.
FRONT_KEEP = {
    "RimOuterDiaDim": (
        FRONT_CENTER[0] - _RIM_R - 0.028,
        FRONT_CENTER[1] + _RIM_R + 0.006,
    ),
    "RimInnerDiaDim": (FRONT_CENTER[0] + _RIM_R + 0.026, FRONT_CENTER[1] + 0.014),
    "HubDiaDim": (FRONT_CENTER[0] + 0.030, FRONT_CENTER[1] - _RIM_R - 0.002),
    "BoreDiaDim": (FRONT_CENTER[0] - _RIM_R - 0.010, FRONT_CENTER[1] - 0.030),
    "SpokeWidthDim": (FRONT_CENTER[0] + 0.015, FRONT_CENTER[1] + _RIM_R + 0.012),
}
SECTION_KEEP: dict[str, tuple[float, float]] = {}
DIMENSION_CALLOUTS = {
    "BoreDiaDim": "REAM THRU",
    "SpokeWidthDim": "6X SPOKES, EQUALLY SPACED",
}
# The reamed bore carries its H7 band natively (model dimension), so it is
# the one fitted feature shown to three places (policy rule 2).
DIMENSION_PRECISION = {"BoreDiaDim": 3}
FRONT_DIAMETERS = ("RimOuterDiaDim", "RimInnerDiaDim", "HubDiaDim", "BoreDiaDim")

# SECTION A-A picks, as (model x, model z) mm in the cut plane, resolved at
# build time through the section's projected frame (the section's mirror is
# SolidWorks' choice).  The wheel is symmetric in both, so every pick is a real
# cut edge whichever way the view reads.  Rim ring cut faces span |x| 44..50,
# z +-4; hub cut |x| 2.5..10, z +-5; the spokes behind the plane (30/150 deg)
# show as bands z +-2 between |x| 10 and 44.
_RIM_PICK_X = (RIM_INNER_DIA + RIM_OUTER_DIA) / 4.0  # 47, mid rim wall
_SPOKE_PICK_X = 25.0
_HUB_PICK_X = (BORE_DIA / 2.0 + HUB_DIA / 2.0) / 2.0 + 0.75  # 7, mid hub wall
_RIM_HALF = RIM_AXIAL / 2.0
_HUB_HALF = HUB_AXIAL / 2.0
_SPOKE_HALF = SPOKE_AXIAL / 2.0
# Section label parked to the right of the strip dimensions, below the strip.
SECTION_LABEL_XY = (0.180, SECTION_CENTER[1] - 0.031)

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


def _section_frame(
    adapter: Any, section: Any, *, label: str
) -> tuple[tuple[float, float], tuple[float, float], tuple[float, float]]:
    """Sheet origin and unit directions of model +X (sheet-right) and +Z
    (sheet-up) in ``section``, sign-normalised: the wheel is symmetric in both,
    so a positive model offset is a real cut point whichever way the section
    reads."""
    origin = model_point_in_view(adapter, section, (0.0, 0.0, 0.0), label=f"{label} origin")

    def unit(xyz: tuple[float, float, float]) -> tuple[float, float]:
        point = model_point_in_view(adapter, section, xyz, label=f"{label} axis")
        dx, dy = point[0] - origin[0], point[1] - origin[1]
        norm = math.hypot(dx, dy)
        if norm < 1e-6:
            raise RuntimeError(f"{label}: model axis {xyz} projects to a point")
        return (dx / norm, dy / norm)

    x_axis = unit((0.01, 0.0, 0.0))
    z_axis = unit((0.0, 0.0, 0.01))
    right = x_axis if x_axis[0] >= 0.0 else (-x_axis[0], -x_axis[1])
    up = z_axis if z_axis[1] >= 0.0 else (-z_axis[0], -z_axis[1])
    return origin, right, up


def _move_view_label(
    adapter: Any, view: Any, xy: tuple[float, float], *, keyword: str, label: str
) -> None:
    """Park the view's SECTION label where no dimension will sit under it."""
    notes = list(adapter._attempt(lambda: view.GetNotes(), default=None) or ())
    if not notes:
        note = adapter._attempt(lambda: view.GetFirstNote2(), default=None)
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
        _telemetry.warn(f"{label}: {keyword} label note not found; left at its default spot")
    adapter.currentModel.EditRebuild3()


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open magnifying-wheel source", await adapter.open_model(str(SOURCE)))
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
        adapter, property_view=PART_STEM, scale=SHEET_SCALE
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Magnifying Wheel Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "magnifying wheel; cast pulley; six spokes",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(1, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 1))
    set_hidden_lines_removed(adapter, iso)

    # SECTION A-A: the face cut along its horizontal centreline (through the
    # bore, the hub and the rim ring; the 30/150-degree spokes stand behind
    # the plane), so the spoke thickness, the hub length and their stations
    # against the rim faces are real cut edges -- never hidden lines.
    section = create_section_view(
        adapter,
        front,
        line_start=SECTION_LINE[0],
        line_end=SECTION_LINE[1],
        view_xy=SECTION_CENTER,
        section_label="A",
        scale=(1, 1),
        label="wheel axial section",
    )
    # Hidden lines ON in every orthographic view (policy rule 7).
    for view in (front, section):
        set_hidden_lines_visible(adapter, view)

    # The face view claims every marked profile dimension; the section keeps
    # none (a marked dimension imports into one view only).
    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    curate_view_dimensions(adapter, section, keep=SECTION_KEEP, view_label="section")
    set_dimension_callouts(adapter, front_annotations, DIMENSION_CALLOUTS)
    set_dimension_precision(adapter, front_annotations, DIMENSION_PRECISION)
    _leaders_to_circumference(
        adapter, front_annotations, FRONT_DIAMETERS, label="face diameters"
    )
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to wheel bore")

    origin, right, up = _section_frame(adapter, section, label="wheel section")

    def at(x_mm: float, z_mm: float) -> tuple[float, float]:
        return (
            origin[0] + right[0] * x_mm * _S + up[0] * z_mm * _S,
            origin[1] + right[1] * x_mm * _S + up[1] * z_mm * _S,
        )

    # Rim width (8) across the left rim-ring cut, text left of the strip.
    add_edge_dimension(
        adapter,
        section,
        p0=at(-_RIM_PICK_X, _RIM_HALF),
        p1=at(-_RIM_PICK_X, -_RIM_HALF),
        text_xy=at(-RIM_OUTER_DIA / 2.0 - 14.0, 0.0),
        label="rim axial width",
        orientation="vertical",
    )
    # Spoke thickness (4) across the left spoke band, text under the strip.
    add_edge_dimension(
        adapter,
        section,
        p0=at(-_SPOKE_PICK_X, _SPOKE_HALF),
        p1=at(-_SPOKE_PICK_X, -_SPOKE_HALF),
        text_xy=at(-_SPOKE_PICK_X, -20.0),
        label="spoke thickness",
        orientation="vertical",
    )
    # Spoke face to rim face (2): the spoke's axial station, text above.
    add_edge_dimension(
        adapter,
        section,
        p0=at(-_RIM_PICK_X, _RIM_HALF),
        p1=at(-_SPOKE_PICK_X, _SPOKE_HALF),
        text_xy=at(-(RIM_INNER_DIA / 2.0 - 3.0), 14.0),
        label="spoke face to rim face",
        orientation="vertical",
    )
    # Hub length (10) across the right hub cut, text under the strip.
    add_edge_dimension(
        adapter,
        section,
        p0=at(_HUB_PICK_X, _HUB_HALF),
        p1=at(_HUB_PICK_X, -_HUB_HALF),
        text_xy=at(HUB_DIA / 2.0 + 6.0, -20.0),
        label="hub-drum axial length",
        orientation="vertical",
    )
    # Rim face to hub face (1): the hub's axial station, text above.
    add_edge_dimension(
        adapter,
        section,
        p0=at(_RIM_PICK_X, _RIM_HALF),
        p1=at(_HUB_PICK_X, _HUB_HALF),
        text_xy=at(30.0, 14.0),
        label="hub face to rim face",
        orientation="vertical",
    )
    _move_view_label(
        adapter, section, SECTION_LABEL_XY, keyword="SECTION", label="wheel section"
    )

    # Ra 1.6 on the axle bore -- the one surface that runs on the stud.  Tagged
    # on the bore's top rim (a real circular edge); the symbol sits in the clear
    # 60-degree gap between the 30 and 90 degree spokes.
    add_surface_finish(
        adapter,
        front,
        edge_xy=(FRONT_CENTER[0], FRONT_CENTER[1] + BORE_DIA * _S / 2.0),
        symbol_xy=(FRONT_CENTER[0] + 0.010, FRONT_CENTER[1] + 0.016),
        control=surface_finish_by_key(SURFACE_FINISHES, "axle_bore"),
        label="axle bore finish",
    )

    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.030)
    add_property_linked_note(adapter, "Isometric View Note", 0.330, 0.085)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Magnifying Wheel Manufacturing Drawing",
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
