r"""Create the curated machinist drawing for the knife-mount bearing block.

A machined, heat-treated steel block (24 wide x ~29.4 tall x 14 deep) with a
single Ø12 bore.  The bore is the knife-edge bearing: the summing-lever
trunnion's top vertex rides its upper inner wall in line contact (ch18 p.42:
unpainted hardened steel, close bore -- 2026-09-02 user re-read).  Every face
and the bore are real edges, so
the block dimensions ride the auto-imported profile marks (block + bore) with the
depth added across the right-view section.

Run with SolidWorks open::

    uv run python cad\scripts\draw_knife_mount.py knife-mount
"""

from __future__ import annotations

import argparse
import sys
from typing import Any


from win32com.client.dynamic import Dispatch as dynamic_dispatch

import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_datum_feature,
    add_feature_control_frame,
    add_native_hole_callout,
    add_property_linked_note,
    add_surface_finish,
    assert_imported_precision,
    curate_view_dimensions,
    dimension_name,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_basic_dimensions,
    set_dimension_callouts,
    set_hidden_lines_removed,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _surface_finish import surface_finish_by_key
from knife_mount_spec import (
    BORE_DIAMETER_TOLERANCE_MM,
    BLK_BOT,
    BLK_TOP,
    BORE_CY,
    DRAWING_NOMINALS_MM,
    DRAWING_PRECISION_BY_NAME,
    GEOMETRIC_TOLERANCES_MM,
    R_BORE,
    STUD_TAP_DIA,
    STUD_TAP_SPEC,
    SUPPORT_Z_THICK,
    SURFACE_FINISHES,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["knife_mount"]
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
_BLOCK_CY = (BLK_TOP + BLK_BOT) / 2.0  # block centre height (model mm)

FRONT_CENTER = (0.115, 0.140)
RIGHT_CENTER = (0.220, 0.140)
TOP_CENTER = (0.115, 0.235)
ISO_CENTER = (0.345, 0.210)


def _front_y(model_y_mm: float) -> float:
    return FRONT_CENTER[1] + (model_y_mm - _BLOCK_CY) * SHEET_SCALE[0] / 1000.0


FRONT_KEEP = {
    "BlockWidth": (FRONT_CENTER[0], _front_y(BLK_BOT) - 0.016),
    "BlockHeight": (FRONT_CENTER[0] - 0.060, FRONT_CENTER[1]),
    "BoreDia": (FRONT_CENTER[0] - 0.048, _front_y(BORE_CY) + 0.026),
    "BoreFromTop": (FRONT_CENTER[0] + 0.043, FRONT_CENTER[1]),
}
RIGHT_KEEP = {
    "Depth": (RIGHT_CENTER[0], _front_y(BLK_BOT) - 0.016),
}
DIMENSION_CALLOUTS = {
    "BoreDia": "THRU",
}


def _assert_imported_nominals(adapter: Any, annotations: list[Any]) -> None:
    """Prove every imported model dimension still measures the spec nominal."""
    remaining = dict(DRAWING_NOMINALS_MM)
    for annotation in annotations:
        name = dimension_name(adapter, annotation)
        expected_mm = remaining.pop(name, None)
        if expected_mm is None:
            continue
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        dimension = _early_bound(display.GetDimension2(0), "IDimension")
        actual_mm = abs(float(dimension.SystemValue)) * 1000.0
        if abs(actual_mm - expected_mm) > 1e-5:
            raise RuntimeError(
                f"imported {name} measured {actual_mm:g}, expected {expected_mm:g} mm"
            )
    if remaining:
        raise RuntimeError(f"model dimensions never reached sheet: {sorted(remaining)}")


def _assert_imported_bore_tolerance(adapter: Any, annotations: list[Any]) -> None:
    for annotation in annotations:
        if dimension_name(adapter, annotation) != "BoreDia":
            continue
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        dimension = _early_bound(display.GetDimension2(0), "IDimension")
        tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
        limit_m = BORE_DIAMETER_TOLERANCE_MM / 1000.0
        if (
            int(tolerance.Type) != 4
            or abs(float(tolerance.GetMinValue()) + limit_m) > 1e-9
            or abs(float(tolerance.GetMaxValue()) - limit_m) > 1e-9
        ):
            raise RuntimeError("imported BoreDia lost its native symmetric tolerance")
        return
    raise RuntimeError("BoreDia never reached sheet for native tolerance readback")


@_telemetry.traced("drawing.knife_mount_tap_readback")
def _check_tap_callout(display: Any) -> None:
    """Prove the native callout carries both drill and usable-thread depths."""
    expected_lengths = {
        "hw-tapdrldia": STUD_TAP_DIA,
        "hw-tapdrldepth": STUD_TAP_SPEC.depth_mm,
        "hw-threaddepth": STUD_TAP_SPEC.overrides_mm["ThreadDepth"],
    }
    expected_strings = {
        "hw-threaddesc": "1/2-13 UNC",
        "hw-threadclass": STUD_TAP_SPEC.thread_class,
    }
    found: set[str] = set()
    for raw in display.GetHoleCalloutVariables() or ():
        late = dynamic_dispatch(raw._oleobj_)
        name = str(late.VariableName)
        if name in expected_strings:
            if int(late.Type) != 3:
                raise RuntimeError(f"knife-mount tap {name} is not a string")
            actual = str(_early_bound(raw, "ICalloutStringVariable").String or "")
            if actual.strip(" -") != expected_strings[name]:
                raise RuntimeError(
                    f"knife-mount tap {name}: {actual!r} != {expected_strings[name]!r}"
                )
            found.add(name)
            continue
        if name not in expected_lengths:
            raise RuntimeError(f"unexpected knife-mount tap variable {name!r}")
        if int(late.Type) != 1:
            raise RuntimeError(f"knife-mount tap {name} is not a length")
        actual_mm = (
            float(_early_bound(raw, "ICalloutLengthVariable").Length) * 1000.0
        )
        if abs(actual_mm - expected_lengths[name]) > 1e-5:
            raise RuntimeError(
                f"knife-mount tap {name}: {actual_mm} != "
                f"{expected_lengths[name]} mm"
            )
        found.add(name)
    required = set(expected_lengths) | set(expected_strings)
    if found != required:
        raise RuntimeError(
            f"knife-mount tap callout is missing native variables: {required - found}"
        )


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open knife-mount source", await adapter.open_model(str(SOURCE)))
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
            0: "Knife-Mount Bearing Block Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "knife mount; hardened steel bearing block; knife-edge bore",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(2, 1))
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(2, 1))
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(2, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 1))
    # Standard holes are fully defined by their native callouts, so hidden
    # lines add no manufacturing information on this part.  The shared
    # finalizer promotes the standard isometric to precise Shaded With Edges.
    for view in (front, right, top, iso):
        set_hidden_lines_removed(adapter, view)

    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    right_annotations = curate_view_dimensions(
        adapter, right, keep=RIGHT_KEEP, view_label="right"
    )
    dimensions = [*front_annotations, *right_annotations]
    set_dimension_callouts(adapter, front_annotations, DIMENSION_CALLOUTS)
    set_basic_dimensions(adapter, front_annotations, ("BoreFromTop",))
    _assert_imported_nominals(adapter, dimensions)
    _assert_imported_bore_tolerance(adapter, dimensions)
    assert_imported_precision(adapter, dimensions, DRAWING_PRECISION_BY_NAME)
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to knife bore")

    # Native Hole Wizard callout owns the thread size/class and blind depth.
    tap_radius_sheet = STUD_TAP_DIA * SHEET_SCALE[0] / 2000.0
    tap_callout = add_native_hole_callout(
        adapter,
        top,
        edge_xy=(TOP_CENTER[0] + tap_radius_sheet, TOP_CENTER[1]),
        callout_xy=(0.175, 0.258),
        label="hanger-stud blind tap",
    )
    _check_tap_callout(tap_callout)

    # Datum A is the hanger seat; datum B is the mating hanger-tap axis.
    # Together with the imported BASIC height they fully locate the sole
    # surviving knife-system position control.
    add_datum_feature(
        adapter,
        front,
        edge_xy=(FRONT_CENTER[0], _front_y(BLK_TOP)),
        symbol_xy=(FRONT_CENTER[0] + 0.030, _front_y(BLK_TOP) + 0.010),
        datum="A",
        label="block top seat",
    )
    add_datum_feature(
        adapter,
        top,
        edge_xy=(TOP_CENTER[0] + tap_radius_sheet, TOP_CENTER[1]),
        symbol_xy=(TOP_CENTER[0] + 0.028, TOP_CENTER[1] - 0.012),
        datum="B",
        label="hanger-tap axis",
    )
    add_feature_control_frame(
        adapter,
        front,
        edge_xy=(
            FRONT_CENTER[0],
            _front_y(BORE_CY) + R_BORE * SHEET_SCALE[0] / 1000.0,
        ),
        frame_xy=(FRONT_CENTER[0] + 0.060, _front_y(BORE_CY) + 0.040),
        characteristic="position",
        tolerance=GEOMETRIC_TOLERANCES_MM["knife-bore position"],
        datums=("A", "B"),
        diameter=True,
        label="knife-bore position",
    )
    add_surface_finish(
        adapter,
        front,
        edge_xy=(FRONT_CENTER[0] + R_BORE * SHEET_SCALE[0] / 1000.0, _front_y(BORE_CY)),
        symbol_xy=(FRONT_CENTER[0] + 0.052, _front_y(BORE_CY) - 0.020),
        control=surface_finish_by_key(SURFACE_FINISHES, "knife_bore"),
        label="knife bore finish",
    )

    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.070)
    add_property_linked_note(adapter, "Isometric View Note", 0.330, 0.175)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Knife-Mount Bearing Block Manufacturing Drawing",
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
