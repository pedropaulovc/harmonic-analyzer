r"""Create the two-sheet manufacturing drawing for MHA-073.

The SLDPRT owns every nominal, decimal place, tolerance and surface control.
Sheet ``FORM-KNIFE`` defines the lever envelope, knife trunnions and
counter-spring boss at useful scales.  Sheet ``SPRING-PATTERN`` gives the
authoritative 20-hole field its own 1:1 plan, one rule-3 position frame, and
unobstructed native thread callout.  All orthographic views are HLR; the
standard isometric is finalized as precision Shaded With Edges.

Run with SolidWorks open::

    uv run python cad\scripts\draw_summing_lever.py summing-lever
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _hole_spec import blind_cut_dia_mm
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_datum_feature,
    add_feature_control_frame,
    add_native_hole_callout,
    add_note,
    add_property_linked_note,
    add_surface_finish,
    assert_imported_precision,
    create_blank_drawing_sheets,
    curate_view_dimensions,
    finalize_drawing,
    import_cosmetic_threads,
    new_project_drawing,
    read_required_properties,
    set_hidden_lines_removed,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _surface_finish import surface_finish_by_key
from summing_lever_spec import (
    ANCHOR_R,
    BASIC_DRAWING_DIMENSIONS,
    COUNTER_HOLE_SPEC,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    GEOMETRIC_TOLERANCES_MM,
    HEX_DEPTH,
    HOLE_SPEC,
    HOLE_X,
    HOLE_Z_FIRST,
    HOLE_Z_LAST,
    PLATE_L,
    PLATE_W,
    SURFACE_FINISHES,
    TIP_X,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    dimension_name,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["summing_lever"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"],
    pdf=SPEC.outputs["pdf"],
    png=SPEC.outputs["png"],
)
HOLE_DIA = blind_cut_dia_mm(HOLE_SPEC)
# Tap-drill diameter of the boss's counter-anchor tap; the rim points below
# pick its circular edge, and the native callout prints the thread itself.
COUNTER_R = blind_cut_dia_mm(COUNTER_HOLE_SPEC) / 2.0

SLDDRW = OUTPUTS.slddrw
PDF = OUTPUTS.pdf
PNG = OUTPUTS.png

SHEET_SCALE = (1.0, 1.0)
SHEET_NAMES = ("FORM-KNIFE", "SPRING-PATTERN")

FORM_FRONT_SCALE = (1, 1)
FORM_TOP_SCALE = (1, 2)
ISO_SCALE = (1, 2)
PATTERN_SCALE = (1, 1)

# Front (down -Z) and top (down -Y) share this X envelope.
_BBOX_CX = (TIP_X - ANCHOR_R + PLATE_W) / 2.0

FORM_FRONT_CENTER = (0.150, 0.220)
FORM_TOP_CENTER = (0.165, 0.105)
ISO_CENTER = (0.335, 0.165)
PATTERN_CENTER = (0.225, 0.145)


def _top_xy(
    mx: float,
    mz: float,
    *,
    center: tuple[float, float],
    scale: tuple[int, int],
) -> tuple[float, float]:
    """Project model X/Z millimetres into one explicit top-view sheet frame."""
    factor = scale[0] / scale[1]
    return (
        center[0] + (mx - _BBOX_CX) * factor / 1000.0,
        center[1] + mz * factor / 1000.0,
    )


FORM_FRONT_KEEP = {
    "CylDia": (0.120, 0.255),
    "PlateThickness": (0.225, 0.215),
    "AnchorHeight": (0.045, 0.215),
    "HexWidth": (0.160, 0.245),
    "HexHeight": (0.095, 0.245),
}
FORM_TOP_KEEP = {
    "PlateWidth": (0.195, 0.158),
    "PlateLength": (0.220, FORM_TOP_CENTER[1]),
    "AnchorOuterDia": (0.105, 0.125),
    "AnchorOuterX": (0.145, 0.052),
    "HexKnifeFrontDepth": (0.120, 0.172),
}
PATTERN_KEEP = {
    "HoleSeedX": (0.340, 0.245),
    "HolePitch": (0.320, 0.120),
    "HoleStartOffset": (0.350, 0.085),
}

def _assert_imported_basics(adapter: Any, annotations: list[Any]) -> None:
    """Prove the pattern coordinates retained the part-authored BASIC state."""
    expected = {
        name
        for dimension_names in BASIC_DRAWING_DIMENSIONS.values()
        for name in dimension_names
    }
    remaining = set(expected)
    for annotation in annotations:
        annotation = _early_bound(annotation, "IAnnotation")
        name = dimension_name(adapter, annotation)
        if name not in remaining:
            continue
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        dimension = _early_bound(display.GetDimension2(0), "IDimension")
        tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
        if int(tolerance.Type) != 1:  # swTolType_e.swTolBASIC
            raise RuntimeError(
                f"imported pattern dimension {name!r} is no longer BASIC"
            )
        remaining.remove(name)
    if remaining:
        raise RuntimeError(
            f"part-authored BASIC dimensions never reached the sheet: {sorted(remaining)}"
        )


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open summing-lever source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Isometric View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    create_blank_drawing_sheets(
        adapter, SHEET_NAMES, label="summing-lever manufacturing package"
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Summing Lever Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "summing lever; ferrous; knife-edge first-class lever",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    ddoc = _early_bound(drawing_model, "IDrawingDoc")

    if not ddoc.ActivateSheet(SHEET_NAMES[0]):
        raise RuntimeError("failed to activate summing-lever form sheet")
    front = place_view(
        adapter,
        str(SOURCE),
        "*Front",
        *FORM_FRONT_CENTER,
        scale=FORM_FRONT_SCALE,
    )
    top = place_view(
        adapter,
        str(SOURCE),
        "*Top",
        *FORM_TOP_CENTER,
        scale=FORM_TOP_SCALE,
    )
    iso = place_view(
        adapter,
        str(SOURCE),
        "*Isometric",
        *ISO_CENTER,
        scale=ISO_SCALE,
    )
    # Materialize both tap features in the iso before the finalizer asks
    # SolidWorks for high-quality cosmetic-thread readback.
    import_cosmetic_threads(adapter, iso)
    for view in (front, top):
        set_hidden_lines_removed(adapter, view)

    front_dimensions = curate_view_dimensions(
        adapter,
        front,
        keep=FORM_FRONT_KEEP,
        view_label="form front",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    top_dimensions = curate_view_dimensions(
        adapter,
        top,
        keep=FORM_TOP_KEEP,
        view_label="form top",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )

    counter_tap_edge = _top_xy(
        TIP_X,
        COUNTER_R,
        center=FORM_TOP_CENTER,
        scale=FORM_TOP_SCALE,
    )
    add_native_hole_callout(
        adapter,
        top,
        edge_xy=counter_tap_edge,
        callout_xy=(0.070, 0.115),
        label="counter-spring anchor tap",
    )
    knife_edge = _top_xy(
        0.0,
        -(PLATE_L / 2.0 + HEX_DEPTH / 2.0),
        center=FORM_TOP_CENTER,
        scale=FORM_TOP_SCALE,
    )
    add_surface_finish(
        adapter,
        top,
        edge_xy=knife_edge,
        symbol_xy=(0.095, 0.070),
        control=surface_finish_by_key(SURFACE_FINISHES, "knife_edge_ridge"),
        label="knife-edge ridge finish",
    )
    add_property_linked_note(adapter, "Isometric View Note", 0.300, 0.105)

    if not ddoc.ActivateSheet(SHEET_NAMES[1]):
        raise RuntimeError("failed to activate summing-lever spring-pattern sheet")
    pattern = place_view(
        adapter,
        str(SOURCE),
        "*Top",
        *PATTERN_CENTER,
        scale=PATTERN_SCALE,
    )
    set_hidden_lines_removed(adapter, pattern)
    pattern_dimensions = curate_view_dimensions(
        adapter,
        pattern,
        keep=PATTERN_KEEP,
        view_label="spring-pattern plan",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    _assert_imported_basics(adapter, pattern_dimensions)

    knife_edge_datum = _top_xy(
        0.0,
        PLATE_L / 2.0 + HEX_DEPTH / 2.0,
        center=PATTERN_CENTER,
        scale=PATTERN_SCALE,
    )
    add_datum_feature(
        adapter,
        pattern,
        edge_xy=knife_edge_datum,
        symbol_xy=(knife_edge_datum[0] + 0.022, knife_edge_datum[1] - 0.012),
        datum="A",
        label="knife-edge pivot axis",
    )
    plate_end_edge = _top_xy(
        10.0,
        -PLATE_L / 2.0,
        center=PATTERN_CENTER,
        scale=PATTERN_SCALE,
    )
    add_datum_feature(
        adapter,
        pattern,
        edge_xy=plate_end_edge,
        symbol_xy=(plate_end_edge[0] - 0.020, plate_end_edge[1] - 0.010),
        datum="B",
        label="plate first-hole end",
    )

    seed_rim_bottom = _top_xy(
        HOLE_X,
        HOLE_Z_FIRST - HOLE_DIA / 2.0,
        center=PATTERN_CENTER,
        scale=PATTERN_SCALE,
    )
    add_native_hole_callout(
        adapter,
        pattern,
        edge_xy=seed_rim_bottom,
        callout_xy=(0.330, 0.060),
        label="spring-hole seed",
    )
    pattern_rim_right = _top_xy(
        HOLE_X + HOLE_DIA / 2.0,
        HOLE_Z_LAST,
        center=PATTERN_CENTER,
        scale=PATTERN_SCALE,
    )
    add_feature_control_frame(
        adapter,
        pattern,
        edge_xy=pattern_rim_right,
        frame_xy=(0.330, 0.225),
        characteristic="position",
        tolerance=GEOMETRIC_TOLERANCES_MM["spring-hole pattern position"],
        datums=("A", "B"),
        diameter=True,
        quantity="20X",
        label="spring-hole pattern position",
    )

    for sheet_index, sheet_name in enumerate(SHEET_NAMES, start=1):
        if not ddoc.ActivateSheet(sheet_name):
            raise RuntimeError(f"failed to label drawing sheet {sheet_name}")
        if (
            add_note(
                adapter,
                f"SHEET {sheet_index} OF {len(SHEET_NAMES)}",
                0.350,
                0.263,
            )
            is None
        ):
            raise RuntimeError(f"failed to stamp sheet count on {sheet_name}")

    assert_imported_precision(
        adapter,
        [*front_dimensions, *top_dimensions, *pattern_dimensions],
        DRAWING_PRECISION_BY_NAME,
    )
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Summing Lever Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        redundant_note_substrings=("Tapped Hole",),
        expected_redundant_notes=3,
        expected_sheet_names=SHEET_NAMES,
        sheet_layouts={name: SPEC.layout for name in SHEET_NAMES},
        sheet_scales={name: SHEET_SCALE for name in SHEET_NAMES},
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
