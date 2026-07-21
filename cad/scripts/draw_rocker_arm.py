r"""Create the curated machinist drawing for the rocker arm.

The SLDPRT remains authoritative.  This recipe supplies only the rocker-arm
views, dimension layout, hole callouts, and manufacturing notes; every shared
sheet/template, import, curation, and export behavior lives in
``_drawing_common``.

The strap is a long thin curved seesaw (~292 mm tip to tip, 16 mm deep, 2.5 mm
thick).  A projected side view of the curved strap is a messy band, so the
16 x 2.5 section is carried in the notes and the print shows the profile (front)
plus a 1:2 isometric.  The sheet runs at 1:2.

Run with SolidWorks open::

    uv run python cad\scripts\draw_rocker_arm.py rocker-arm
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_datum_feature,
    add_edge_dimension,
    add_feature_control_frame,
    add_native_hole_callout,
    add_property_linked_note,
    add_surface_finish,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_basic_dimension,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from rocker_arm_spec import (
    PIVOT_HOLE_DIA,
    ROD_HOLE_X,
    ROD_HOLE_Y,
    TOP_END_Y,
)
from solidworks_mcp.adapters import sw_type_info as _sw_type_info
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    dimension_name,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["rocker_arm"]
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

SHEET_SCALE = (1.0, 2.0)  # 1:2
_S = SHEET_SCALE[0] / SHEET_SCALE[1]  # sheet-mm per model-mm (0.5)

# Front-view model bbox: X symmetric about 0, Y from the centre bottom (0) up to
# the top-arc tip (TOP_END_Y).
_PIVOT_MID_Y = 8.0  # pivot bore centre = ArmDepth / 2
_ROD_HOLE_DIA = 1.994  # #47 drill
_BBOX_CY = TOP_END_Y / 2.0

FRONT_CENTER = (0.180, 0.175)
ISO_CENTER = (0.345, 0.205)


def _sheet_xy(mx: float, my: float) -> tuple[float, float]:
    """Sheet (x, y) of a model point in the bbox-centred front view (1:2)."""
    return (
        FRONT_CENTER[0] + mx * _S / 1000.0,
        FRONT_CENTER[1] + (my - _BBOX_CY) * _S / 1000.0,
    )


# The two curvature radii jog above the strap; the pivot diameter sits below
# the fulcrum bore.
FRONT_KEEP = {
    "TopRadius": (0.140, 0.215),
    "BottomRadius": (0.235, 0.215),
    "PivotDia": (0.180, 0.120),
}
RIGHT_KEEP: dict[str, tuple[float, float]] = {}
TOP_KEEP: dict[str, tuple[float, float]] = {}


def _shorten_radius_dimensions(
    adapter: Any, annotations: list[Any], names: set[str]
) -> None:
    """Stop large-radius leaders before their off-sheet arc centres."""
    remaining = set(names)
    for annotation in annotations:
        name = dimension_name(adapter, annotation)
        if name not in remaining:
            continue
        display = annotation.GetSpecificAnnotation()
        if display is None:
            raise RuntimeError(f"radius dimension {name!r} has no display annotation")
        display = _sw_type_info.early_bound(display, "IDisplayDimension")
        display.ShortenedRadius = True
        if not bool(display.ShortenedRadius):
            raise RuntimeError(f"radius dimension {name!r} was not shortened")
        remaining.remove(name)
    if remaining:
        raise RuntimeError(f"radius dimensions not shortened: {sorted(remaining)}")
    adapter.currentModel.GraphicsRedraw2()


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open rocker-arm source", await adapter.open_model(str(SOURCE)))
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
            0: "Rocker Arm Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "rocker arm; tapered strap; seesaw pivot",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    # Explicit per-view scale (an auto-scaled view shifts every coordinate pick).
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(1, 2))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 4))
    set_hidden_lines_removed(adapter, iso)
    set_hidden_lines_visible(adapter, front)

    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    _shorten_radius_dimensions(
        adapter, front_annotations, {"TopRadius", "BottomRadius"}
    )

    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to front view")

    # Rod-pin hole native callout (the #47 wizard hole near the +X tip).
    rod_edge = _sheet_xy(ROD_HOLE_X, ROD_HOLE_Y)
    add_native_hole_callout(
        adapter,
        front,
        edge_xy=rod_edge,
        callout_xy=(0.300, 0.128),
        label="rod-pin hole",
    )

    # Locate the rod-pin hole from the pivot bore (basic centre distance): pivot
    # bore edge to rod-pin bore edge, dimensioned below the strap.
    pivot_rim = _sheet_xy(0.0, _PIVOT_MID_Y - PIVOT_HOLE_DIA / 2.0)
    rod_rim = _sheet_xy(ROD_HOLE_X, ROD_HOLE_Y - _ROD_HOLE_DIA / 2.0)
    rod_location = add_edge_dimension(
        adapter,
        front,
        p0=pivot_rim,
        p1=rod_rim,
        text_xy=(0.180, 0.138),
        label="rod-pin location",
    )
    set_basic_dimension(adapter, rod_location, label="rod-pin location")

    # Datum A on the pivot bore axis (picked at 9 o'clock so the tag stands off
    # to the LEFT), Ra on the bore at 6 o'clock, and a position FCF tying the
    # rod-pin hole to A.
    pivot_left = _sheet_xy(-PIVOT_HOLE_DIA / 2.0, _PIVOT_MID_Y)
    add_datum_feature(
        adapter,
        front,
        edge_xy=pivot_left,
        symbol_xy=(pivot_left[0] - 0.020, pivot_left[1]),
        datum="A",
        label="pivot bore axis",
    )
    pivot_bottom = _sheet_xy(0.0, _PIVOT_MID_Y - PIVOT_HOLE_DIA / 2.0)
    add_surface_finish(
        adapter,
        front,
        edge_xy=pivot_bottom,
        symbol_xy=(pivot_bottom[0] + 0.010, pivot_bottom[1] - 0.020),
        roughness_ra="1.6",
        label="pivot bore finish",
    )
    add_feature_control_frame(
        adapter,
        front,
        edge_xy=rod_edge,
        frame_xy=(0.300, 0.195),
        characteristic="position",
        tolerance="0.20",
        datums=("A",),
        diameter=True,
        label="rod-pin hole position",
    )

    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.070)
    add_property_linked_note(adapter, "Isometric View Note", 0.315, 0.150)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Rocker Arm Manufacturing Drawing",
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
