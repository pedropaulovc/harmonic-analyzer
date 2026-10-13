r"""Create the drawing for the rocker arm's rod-hole diamond pin (MHA-CH-006-TL-03)."""

from __future__ import annotations

import argparse
import sys
from typing import Any

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import place_view

from _check import check
from _com import _early_bound
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    stamp_drawing_summary,
)
from _drawing_dimension_import import curate_view_dimensions
from _drawing_dimensions import assert_imported_precision, set_reference_dimension
from _drawing_edge_dimensions import add_edge_dimension
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_sections import create_section_view
from _drawing_view_display import set_hidden_lines_removed
from _paths import CAD_ROOT
from _section_axis import create_section_axis_centerline, position_section_caption
from _session import run_build
import _telemetry
import ch_rocker_arm_tl_diamond_pin_spec as part_spec
from _feature_requirements import part_metadata, requirement
from _printed_limits import limits
from _gtol_cylinder import CylinderFace
from _gtol_planar import PlanarFace
from ch_rocker_arm_tl_diamond_pin_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    DRAWING_REFERENCE_PRECISION,
    LAND_HEIGHT,
    OVERALL_LENGTH,
)

SPEC = DRAWINGS_BY_NAME["ch_rocker_arm_tl_diamond_pin"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"], pdf=SPEC.outputs["pdf"], png=SPEC.outputs["png"]
)
SLDDRW, PDF, PNG = OUTPUTS.slddrw, OUTPUTS.pdf, OUTPUTS.png

# A O4.5 x 18.6 pin: 6:1 keeps the 1.76 flats and every step legible.
SHEET_SCALE = (6.0, 1.0)
VIEW_SCALE = (6, 1)
ISO_SCALE = (4, 1)
# Longitudinal section A-A (cut vertically through the land end view) is the
# main view: it shows the body and the bonded gauge pin as cut solids, the
# reamed bore the pin sits in and the one-piece neck/collar/shank. The
# section's axis lies horizontally; which end the lands fall on is read from
# the view transform at run time, so every text position below is given in
# (axial station from the neck face mm, sheet offset from the axis m).
# Every body size imports straight onto the section (axial ones from the
# neck face); the end view keeps the two pin sizes.
SECTION_CENTER = (0.165, 0.175)
END_CENTER = (0.335, 0.200)
ISO_CENTER = (0.330, 0.130)  # caption clears the notes
ISO_NOTE_XY = (0.335, 0.088)
CAPTION_XY = (0.255, 0.122)
CUT_HALF = 0.020  # past the O4.5 collar's 13.5 mm sheet radius
AXIAL_XY = {
    "LandHeight": (-3.6, 0.016),
    "NeckLength": (2.2, 0.022),
    "ReamDepth": (4.0, 0.032),
    "CollarEnd": (5.1, 0.042),
    "OverallLength": (8.0, 0.052),
    "PinLength": (
        3.0,
        -0.052,
    ),  # below the view: a size of the bought pin, not a body station
}


_AXIS = ([0.0, 0.0, 1.0], ("__frame__",))
_ROD = ("ch_rocker_arm_spec", "ROD_HOLE_SPEC")


part_metadata(precision_sources=("DRAWING_PRECISION_BY_NAME", "DRAWING_REFERENCE_PRECISION"))

requirement("neck_face",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, -1.0), 0.0),),
    requirements=("height",),
    fields={
        "normal": ([0.0, 0.0, -1.0], ("__frame__",)),
        "plane": ({"frame": "model", "axis": "z", "value": 0.0}, ("__frame__",)),
        "height": (
            limits(part_spec.COLLAR_END, 1, part_spec.COLLAR_END_BAND),
            ("COLLAR_END", "COLLAR_END_BAND", "FACE_B_ABOVE_PLATE"),
        ),
    },
    precision={"height": 1},
)

# The printed 15.0 body length: the shank end face from the neck face.
requirement("shank_end",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, 1.0), part_spec.OVERALL_LENGTH),),
    requirements=("height",),
    fields={
        "normal": ([0.0, 0.0, 1.0], ("__frame__",)),
        "plane": (
            {"frame": "model", "axis": "z", "value": part_spec.OVERALL_LENGTH},
            ("OVERALL_LENGTH",),
        ),
        "height": (limits(part_spec.OVERALL_LENGTH, 1), ("OVERALL_LENGTH",)),
    },
    precision={"height": 1},
)

# Reference overall, land tip to shank end, on the top tier.
OVERALL_REF_XY = (6.7, 0.082)
OVERALL_REF = OVERALL_LENGTH + LAND_HEIGHT
DIAMETER_XY = {
    "NeckDia": (1.0, -0.026),
    "CollarDia": (9.5, -0.020),
    "ReamDia": (8.6, -0.040),
    "ShankDia": (13.5, -0.026),
}


requirement("collar_seat",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, 1.0), part_spec.COLLAR_END),),
    requirements=("dia",),
    fields={
        "normal": ([0.0, 0.0, 1.0], ("__frame__",)),
        "plane": (
            {"frame": "model", "axis": "z", "value": part_spec.COLLAR_END},
            ("COLLAR_END",),
        ),
        "dia": (limits(part_spec.COLLAR_DIA, 1), ("COLLAR_DIA",)),
    },
    precision={"dia": 1},
)

requirement("shank",
    kind="boss",
    faces=(CylinderFace(part_spec.SHANK_DIA, tolerance_mm=0.003),),
    requirements=("dia",),
    fields={
        "at": ([0.0, 0.0, part_spec.COLLAR_END], ("COLLAR_END",)),
        "axis": _AXIS,
        "dia": (limits(part_spec.SHANK_DIA, 2, part_spec.SHANK_BAND), ("SHANK_DIA", "SHANK_BAND")),
        "dia_nominal": (part_spec.SHANK_DIA, ("SHANK_DIA",)),
        # Reference only: the inspected lengths are OverallLength (shank_end)
        # and CollarEnd (neck_face); SHANK_LENGTH_LIMITS keeps the derived max.
        "length_nominal": (
            round(part_spec.OVERALL_LENGTH - part_spec.COLLAR_END, 6),
            ("OVERALL_LENGTH", "COLLAR_END"),
        ),
    },
    precision={"dia": 2},
)

# The neck whose wall is pending ruling #1368, and the ream's open length
# below the bonded pin (the pin fills the bore through the neck).
requirement("neck",
    kind="boss",
    faces=(
        CylinderFace(part_spec.NECK_DIA, contains_z_mm=part_spec.NECK_LENGTH / 2.0, tolerance_mm=0.003),
    ),
    requirements=("dia", "length"),
    fields={
        "at": ([0.0, 0.0, 0.0], ("__frame__",)),
        "axis": _AXIS,
        "dia": (
            limits(part_spec.NECK_DIA, part_spec.NECK_PLACES, part_spec.NECK_BAND),
            ("NECK_DIA", "NECK_BAND"),
        ),
        "length": (limits(part_spec.NECK_LENGTH, 1), ("NECK_LENGTH",)),
    },
    precision={"dia": part_spec.NECK_PLACES, "length": 1},
)

requirement("ream",
    kind="hole",
    faces=(
        CylinderFace(
            part_spec.REAM_DIA,
            contains_z_mm=(part_spec.PIN_ENGAGEMENT + part_spec.REAM_DEPTH) / 2.0,
            tolerance_mm=0.003,
        ),
    ),
    requirements=("dia", "depth"),
    fields={
        "at": ([0.0, 0.0, 0.0], ("__frame__",)),
        "axis": _AXIS,
        "dia": (limits(part_spec.REAM_DIA, 3, part_spec.REAM_BAND), ("REAM_DIA", "REAM_BAND")),
        "depth": (limits(part_spec.REAM_DEPTH, 1), ("REAM_DEPTH",)),
    },
    precision={"dia": 3, "depth": 1},
)

END_KEEP = {
    "LandDia": (0.375, 0.225),
    "FlatsAF": (0.335, 0.232),
}


requirement("lands",
    kind="pin",
    faces=(CylinderFace(part_spec.LAND_DIA, contains_z_mm=-1.0, tolerance_mm=0.003),),
    requirements=("dia", "width", "height", "length"),
    fields={
        "at": ([0.0, 0.0, 0.0], ("__frame__",)),
        "axis": _AXIS,
        "dia": (
            limits(part_spec.LAND_DIA, part_spec.LAND_PLACES, part_spec.LAND_BAND),
            ("LAND_DIA", "LAND_BAND", _ROD),
        ),
        "dia_nominal": (part_spec.LAND_DIA, ("LAND_DIA",)),
        # width = across the stoned flats (normals +-X, see "flat_pos"/"flat_neg")
        "width": (limits(part_spec.FLATS_AF, part_spec.FLATS_PLACES), ("FLATS_AF",)),
        "z_mm": ([-part_spec.LAND_HEIGHT, 0.0], ("LAND_HEIGHT",)),
        "height": (
            limits(part_spec.LAND_HEIGHT, part_spec.LAND_HEIGHT_PLACES, part_spec.LAND_HEIGHT_BAND),
            (
                "LAND_HEIGHT",
                "LAND_HEIGHT_BAND",
                "COLLAR_END_BAND",
                "FACE_B_ABOVE_PLATE",
                ("ch_rocker_arm_spec", "ARM_THICKNESS"),
            ),
        ),
        # The bought pin's total length: keeps it off the bore bottom and
        # its inserted end past the thin neck.
        "length": (
            limits(part_spec.PIN_LENGTH, 1),
            ("PIN_LENGTH", "REAM_DEPTH", "NECK_LENGTH"),
        ),
    },
    precision={"width": part_spec.FLATS_PLACES, "height": part_spec.LAND_HEIGHT_PLACES, "length": 1},
)

for name, sign in (("flat_pos", 1.0), ("flat_neg", -1.0)):
    requirement(name,
        kind="face",
        faces=(PlanarFace((sign, 0.0, 0.0), part_spec.FLATS_AF / 2.0),),
        requirements=("normal",),
        fields={
            "normal": ([sign, 0.0, 0.0], ("__frame__",)),
            "width": (limits(part_spec.FLATS_AF, part_spec.FLATS_PLACES), ("FLATS_AF",)),
        },
        precision={"width": part_spec.FLATS_PLACES},
    )



def _section_mapper(adapter: Any, section: Any):
    """Return (station mm from the neck face, sheet offset m) -> sheet xy.

    The station runs along the pin axis in the section, whichever way the
    section lays it; the offset is perpendicular to the axis on the sheet.
    """
    view = _early_bound(section, "IView")
    transform = _early_bound(view.ModelToViewTransform, "IMathTransform")
    math_utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")

    def sheet(z_mm: float) -> tuple[float, float]:
        point = _early_bound(
            math_utility.CreatePoint(double_array([0.0, 0.0, z_mm / 1000.0])),
            "IMathPoint",
        )
        data = _early_bound(point.MultiplyTransform(transform), "IMathPoint").ArrayData
        return float(data[0]), float(data[1])

    origin, far = sheet(0.0), sheet(OVERALL_LENGTH)
    if abs(far[1] - origin[1]) > 1e-4:
        raise RuntimeError(
            f"section A-A does not lay the pin axis horizontally: {origin} {far}"
        )

    def to_sheet(station_mm: float, offset_m: float) -> tuple[float, float]:
        x, y = sheet(station_mm)
        return x, y + offset_m

    return to_sheet


def _overall_reference(adapter: Any, section: Any, to_sheet) -> None:
    """(18.1) land tip to shank end, so the assembled length reads at a glance."""
    label = "diamond-pin overall length reference"
    display = add_edge_dimension(
        adapter,
        section,
        p0=to_sheet(-LAND_HEIGHT, 0.002),
        p1=to_sheet(OVERALL_LENGTH, 0.002),
        text_xy=to_sheet(*OVERALL_REF_XY),
        label=label,
        orientation="horizontal",
    )
    display = _early_bound(display, "IDisplayDimension")
    dimension_type = int(display.Type2)
    if dimension_type not in (2, 11):  # swLinearDimension, swHorLinearDimension
        raise RuntimeError(
            f"{label}: expected a linear dimension, got type {dimension_type}"
        )
    measured_mm = abs(
        float(_early_bound(display.GetDimension2(0), "IDimension").SystemValue) * 1000.0
    )
    if abs(measured_mm - OVERALL_REF) > 1e-3:
        raise RuntimeError(
            f"{label} measured {measured_mm:g}, expected {OVERALL_REF:g}"
        )
    set_reference_dimension(adapter, display.GetAnnotation(), label=label)
    display.SetPrecision3(DRAWING_REFERENCE_PRECISION, -1, -1, -1)
    if int(display.GetPrimaryPrecision2()) != DRAWING_REFERENCE_PRECISION:
        raise RuntimeError(f"{label} precision did not persist")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open diamond-pin source", await adapter.open_model(str(SOURCE)))
    required = (
        "Number",
        "Material Specification",
        "Finish",
        "Quantity",
        "Manufacturing Notes",
        "Isometric View Note",
    )
    read_required_properties(
        adapter.currentModel, ("Revision", "Title", *required), required=required
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Rocker Rod Diamond Pin Drawing",
            1: "Harmonic Analyzer shop fixture drawing",
            2: "Harmonic Analyzer Project",
            3: "rocker rod diamond pin; bonded gauge-pin lands; MHA-CH-006-TL-03",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    end = place_view(adapter, str(SOURCE), "*Back", *END_CENTER, scale=VIEW_SCALE)
    section = create_section_view(
        adapter,
        end,
        line_start=(END_CENTER[0], END_CENTER[1] - CUT_HALF),
        line_end=(END_CENTER[0], END_CENTER[1] + CUT_HALF),
        view_xy=SECTION_CENTER,
        section_label="A",
        scale=VIEW_SCALE,
        label="diamond-pin longitudinal section",
    )
    position_section_caption(adapter, section, CAPTION_XY, label="diamond pin")
    # finalize_drawing shades the pictorial isometric with edges.
    place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (end, section):
        set_hidden_lines_removed(adapter, view)

    to_sheet = _section_mapper(adapter, section)
    moved = curate_view_dimensions(
        adapter,
        section,
        keep={
            name: to_sheet(*xy)
            for name, xy in (*AXIAL_XY.items(), *DIAMETER_XY.items())
        },
        view_label="longitudinal section",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    kept_on_end = curate_view_dimensions(
        adapter,
        end,
        keep=END_KEEP,
        view_label="land end view",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )

    annotations = [*moved, *kept_on_end]
    # Places (and so each dimension's tolerance) are authored on the part; the
    # sheet only proves the import kept them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    _overall_reference(adapter, section, to_sheet)
    create_section_axis_centerline(
        adapter,
        section,
        length_mm=OVERALL_LENGTH + LAND_HEIGHT,
        label="pin turning axis",
    )
    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.098)
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Rocker Rod Diamond Pin Drawing",
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
