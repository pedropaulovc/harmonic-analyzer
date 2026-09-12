r"""Create the curated machinist drawing for the connecting rod.

The SLDPRT remains authoritative.  This recipe supplies only the connecting-rod
views, dimension layout, hole callouts, and manufacturing notes; every shared
sheet/template, import, curation, and export behavior lives in
``_drawing_common``.

The rod is a tall thin lollipop (~170 mm ring-bottom to head-crown), so the
sheet runs at 1:1 with a 1:2 isometric.

Run with SolidWorks open::

    uv run python cad\scripts\draw_connecting_rod.py connecting-rod
"""

from __future__ import annotations

import argparse
import sys
from typing import Any


import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_edge_dimension,
    add_native_hole_callout,
    add_property_linked_note,
    add_surface_finish,
    create_section_view,
    curate_view_dimensions,
    finalize_drawing,
    model_point_in_view,
    new_project_drawing,
    read_required_properties,
    set_arc_endpoints_to_center,
    set_arc_endpoints_to_max,
    set_dimension_callouts,
    set_dimension_precision,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    set_reference_dimensions,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _hole_spec import blind_cut_dia_mm
from _surface_finish import surface_finish_by_key
from connecting_rod_notes import (
    DIMENSION_CALLOUTS,
    DIMENSION_PRECISION,
)
from connecting_rod_spec import (
    CENTER_DISTANCE,
    HEAD_HEIGHT,
    HEAD_TOP_Y,
    HEAD_WIDTH,
    PIN_HOLE_SPEC,
    RING_BORE_DIA,
    RING_BOTTOM_Y,
    RING_THICKNESS,
    SHANK_THICKNESS,
    SURFACE_FINISHES,
)
from rod_pivot_spec import (
    FORK_CHEEK_THICKNESS,
    FORK_OUTER_THICKNESS,
    FORK_ROOT_CENTER_BELOW_PIN,
    FORK_ROOT_RADIUS,
    FORK_SLOT_NOMINAL,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["connecting_rod"]
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
_PIN_HOLE_DIA = blind_cut_dia_mm(PIN_HOLE_SPEC)

SHEET_SCALE = (1.0, 1.0)  # 1:1

# The front view defines the XY outline.  Section A-A is a native full section
# through the rod centre plane and is held on the same horizontal projection
# line to show the ring, shank, flare, two cheeks and finished slot.
_BBOX_CY = (RING_BOTTOM_Y + HEAD_TOP_Y) / 2.0
FRONT_CENTER = (0.190, 0.137)
SECTION_CENTER = (0.075, FRONT_CENTER[1])
ISO_CENTER = (0.355, 0.145)


def _sheet_xy(mx: float, my: float) -> tuple[float, float]:
    """Sheet (x, y) of a model point in the bbox-centred front view (1:1)."""
    return (
        FRONT_CENTER[0] + mx / 1000.0,
        FRONT_CENTER[1] + (my - _BBOX_CY) / 1000.0,
    )


def _project_mm(
    adapter: Any,
    view: Any,
    xyz_mm: tuple[float, float, float],
    *,
    label: str,
) -> tuple[float, float]:
    return model_point_in_view(
        adapter,
        view,
        tuple(value / 1000.0 for value in xyz_mm),
        label=label,
    )


def _checked_dimension(
    adapter: Any,
    view: Any,
    *,
    p0: tuple[float, float],
    p1: tuple[float, float],
    text_xy: tuple[float, float],
    label: str,
    expected_mm: float,
    precision: int = 2,
    orientation: str = "smart",
    arc_condition: str | None = None,
) -> Any:
    """Dimension actual view geometry and reject a wrong edge or precision."""
    display = add_edge_dimension(
        adapter,
        view,
        p0=p0,
        p1=p1,
        text_xy=text_xy,
        label=label,
        orientation=orientation,
    )
    if arc_condition == "center":
        set_arc_endpoints_to_center(adapter, display, label=label)
    elif arc_condition == "max":
        set_arc_endpoints_to_max(adapter, display, label=label)
    elif arc_condition is not None:
        raise ValueError(f"unknown arc condition {arc_condition!r}")
    display = _early_bound(display, "IDisplayDimension")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    measured_mm = abs(float(dimension.SystemValue) * 1000.0)
    if abs(measured_mm - expected_mm) > 1e-5:
        raise RuntimeError(
            f"{label}: measured {measured_mm:g}, expected {expected_mm:g} mm"
        )
    display.SetPrecision3(precision, -1, -1, -1)
    if int(display.GetPrimaryPrecision2()) != precision:
        raise RuntimeError(f"{label}: precision did not persist")
    return display


FRONT_KEEP = {
    "RingOuterDia": (0.185, 0.067),
    "StrapBoreDia": (0.190, 0.050),
    "ShankWidthDim": (0.190, 0.145),
    "HeadCrownR": (0.230, 0.220),
    "HeadShoulderRiseR": (0.245, 0.195),
}
SECTION_KEEP = {
    "FlareLength": (0.040, 0.188),
    "FlareAxialRise": (0.108, 0.188),
    "RootDiameter": (0.040, 0.210),
    "SlotWidth": (0.075, 0.223),
}

BORE_FINISH_EDGE = _sheet_xy(RING_BORE_DIA / 2.0, 0.0)
BORE_FINISH_SYMBOL = (BORE_FINISH_EDGE[0] + 0.025, BORE_FINISH_EDGE[1] + 0.015)


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open connecting-rod source", await adapter.open_model(str(SOURCE)))
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
            0: "Connecting Rod Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "connecting rod; two-cheek fork; cam strap",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(1, 1))
    section = create_section_view(
        adapter,
        front,
        line_start=(FRONT_CENTER[0], FRONT_CENTER[1] - 0.094),
        line_end=(FRONT_CENTER[0], FRONT_CENTER[1] + 0.094),
        view_xy=SECTION_CENTER,
        section_label="A",
        scale=(1, 1),
        label="rod centre-plane section",
    )
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 2))
    set_hidden_lines_visible(adapter, front)
    for view in (section, iso):
        set_hidden_lines_removed(adapter, view)

    # Source-model dimensions stay on the view where their geometry reads
    # conventionally.  The matched slot nominal remains reference-only: MHA-132
    # owns the final post-peen fit inspection.
    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    section_annotations = curate_view_dimensions(
        adapter, section, keep=SECTION_KEEP, view_label="section A-A"
    )
    annotations = [*front_annotations, *section_annotations]
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    set_dimension_precision(adapter, annotations, DIMENSION_PRECISION)
    set_reference_dimensions(adapter, annotations, {"SlotWidth"})

    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to front view")

    ring_rim = _sheet_xy(-RING_BORE_DIA / 2.0, 0.0)
    pin_rim = _sheet_xy(-_PIN_HOLE_DIA / 2.0, CENTER_DISTANCE)
    _checked_dimension(
        adapter,
        front,
        p0=ring_rim,
        p1=pin_rim,
        text_xy=(0.140, FRONT_CENTER[1]),
        label="rod centre distance",
        expected_mm=CENTER_DISTANCE,
        orientation="vertical",
        arc_condition="center",
    )
    _checked_dimension(
        adapter,
        front,
        p0=_project_mm(
            adapter,
            front,
            (0.0, RING_BOTTOM_Y, 0.0),
            label="rod overall lower extreme",
        ),
        p1=_project_mm(
            adapter,
            front,
            (0.0, HEAD_TOP_Y, 0.0),
            label="rod overall upper extreme",
        ),
        text_xy=(0.120, FRONT_CENTER[1]),
        label="rod overall length",
        expected_mm=HEAD_TOP_Y - RING_BOTTOM_Y,
        orientation="vertical",
        arc_condition="max",
    )
    _checked_dimension(
        adapter,
        front,
        p0=_project_mm(
            adapter,
            front,
            (-HEAD_WIDTH / 2.0, HEAD_TOP_Y - HEAD_WIDTH / 2.0 - 0.5, 0.0),
            label="head left cheek",
        ),
        p1=_project_mm(
            adapter,
            front,
            (HEAD_WIDTH / 2.0, HEAD_TOP_Y - HEAD_WIDTH / 2.0 - 0.5, 0.0),
            label="head right cheek",
        ),
        text_xy=(FRONT_CENTER[0], 0.238),
        label="head overall width",
        expected_mm=HEAD_WIDTH,
        orientation="horizontal",
    )
    _checked_dimension(
        adapter,
        front,
        p0=_project_mm(
            adapter,
            front,
            (-4.0, HEAD_TOP_Y - HEAD_HEIGHT, 0.0),
            label="head shoulder root",
        ),
        p1=_project_mm(
            adapter,
            front,
            (0.0, HEAD_TOP_Y, 0.0),
            label="head crown top",
        ),
        text_xy=(0.255, 0.216),
        label="head overall height",
        expected_mm=HEAD_HEIGHT,
        orientation="vertical",
        arc_condition="max",
    )

    # Section A-A exposes every axial face; no dimension is attached to a
    # hidden line.  Both physical cheeks are dimensioned independently.
    ring_sample_y = RING_BORE_DIA / 2.0 + 2.0
    _checked_dimension(
        adapter,
        section,
        p0=_project_mm(
            adapter,
            section,
            (0.0, ring_sample_y, -RING_THICKNESS / 2.0),
            label="ring rear face",
        ),
        p1=_project_mm(
            adapter,
            section,
            (0.0, ring_sample_y, RING_THICKNESS / 2.0),
            label="ring front face",
        ),
        text_xy=(0.040, 0.060),
        label="ring thickness",
        expected_mm=RING_THICKNESS,
        orientation="horizontal",
    )
    _checked_dimension(
        adapter,
        section,
        p0=_project_mm(
            adapter,
            section,
            (0.0, 100.0, -SHANK_THICKNESS / 2.0),
            label="shank rear face",
        ),
        p1=_project_mm(
            adapter,
            section,
            (0.0, 100.0, SHANK_THICKNESS / 2.0),
            label="shank front face",
        ),
        text_xy=(0.040, 0.145),
        label="shank thickness",
        expected_mm=SHANK_THICKNESS,
        orientation="horizontal",
    )
    cheek_y = CENTER_DISTANCE - 2.5
    for label, z0, z1, text_x in (
        (
            "rear fork cheek thickness",
            -FORK_OUTER_THICKNESS / 2.0,
            -FORK_SLOT_NOMINAL / 2.0,
            0.040,
        ),
        (
            "front fork cheek thickness",
            FORK_SLOT_NOMINAL / 2.0,
            FORK_OUTER_THICKNESS / 2.0,
            0.108,
        ),
    ):
        _checked_dimension(
            adapter,
            section,
            p0=_project_mm(
                adapter, section, (0.0, cheek_y, z0), label=f"{label} outer"
            ),
            p1=_project_mm(
                adapter, section, (0.0, cheek_y, z1), label=f"{label} inner"
            ),
            text_xy=(text_x, 0.229),
            label=label,
            expected_mm=FORK_CHEEK_THICKNESS,
            orientation="horizontal",
        )
    root_center_y = CENTER_DISTANCE - FORK_ROOT_CENTER_BELOW_PIN
    _checked_dimension(
        adapter,
        section,
        p0=_project_mm(
            adapter,
            section,
            (
                0.0,
                HEAD_TOP_Y,
                (FORK_SLOT_NOMINAL + FORK_OUTER_THICKNESS) / 4.0,
            ),
            label="fork crown top",
        ),
        p1=_project_mm(
            adapter,
            section,
            (0.0, root_center_y - FORK_ROOT_RADIUS, 0.0),
            label="round slot root",
        ),
        text_xy=(0.018, 0.211),
        label="slot-root centre from crown",
        orientation="vertical",
        arc_condition="center",
    )

    add_native_hole_callout(
        adapter,
        front,
        edge_xy=pin_rim,
        callout_xy=(0.255, 0.205),
        label="coaxial fork pivot bores",
    )
    add_surface_finish(
        adapter,
        front,
        edge_xy=BORE_FINISH_EDGE,
        symbol_xy=BORE_FINISH_SYMBOL,
        control=surface_finish_by_key(SURFACE_FINISHES, "strap_bore"),
        label="strap bore finish",
    )

    add_property_linked_note(adapter, "Manufacturing Notes", 0.275, 0.085)
    add_property_linked_note(adapter, "Isometric View Note", 0.325, 0.205)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Connecting Rod Manufacturing Drawing",
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
