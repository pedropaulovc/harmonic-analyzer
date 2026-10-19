r"""Create the purchased reference drawing for McMaster 91585A377.

Both measured native sizes reproduce the supplier engineering PDF, including
the diameter's m6 reference band. The stock end leads and the existing
match-reamed seam installation are not project fabrication controls.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable
from functools import partial
import math
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    dimension_name,
    place_view,
)

from _check import check
from _com import _early_bound
from _drawing_centerline import add_view_centerline
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    stamp_drawing_summary,
)
from _drawing_dimension_import import curate_view_dimensions
from _drawing_dimensions import assert_imported_precision
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _paths import CAD_ROOT
from _session import run_build
from _supplier_dimensions import (
    assert_supplier_reference_dimension,
    supplier_reference_dimension,
)
from _supplier_pin_drawing import assert_supplier_pin_dimensions
import _telemetry
from vn_crank_hub_pin_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    PIN_CHAMFER_AXIAL,
    PIN_DIA,
    PIN_DIA_BAND,
    PIN_END_RADIUS,
    PIN_LEN,
    SKU,
    SUPPLIER_REFERENCE,
)


SPEC = DRAWINGS_BY_NAME["vn_crank_hub_pin"]
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

SHEET_SCALE = (10.0, 1.0)
VIEW_SCALE = (10, 1)
FRONT_CENTER = (0.095, 0.180)
RIGHT_CENTER = (0.225, 0.180)
ISO_CENTER = (0.355, 0.180)
HALF_DIA = PIN_DIA * VIEW_SCALE[0] / 2000.0
RIGHT_KEEP = {
    "PinDia": (RIGHT_CENTER[0] - 0.030, RIGHT_CENTER[1] + HALF_DIA + 0.016),
    "PinLen": (RIGHT_CENTER[0], RIGHT_CENTER[1] - HALF_DIA - 0.016),
}


def _assert_source_end_planes(model: Any) -> None:
    """Read physical stock end faces and OD, independently of sketch dimensions."""
    bodies = tuple(_early_bound(model, "IPartDoc").GetBodies2(0, False) or ())
    if len(bodies) != 1 or bodies[0] is None:
        raise RuntimeError(f"{SKU}: source must contain one solid pin")
    end_planes = []
    radii = []
    for raw in _early_bound(bodies[0], "IBody2").GetFaces() or ():
        surface = _early_bound(_early_bound(raw, "IFace2").GetSurface(), "ISurface")
        if surface.IsPlane():
            parameters = tuple(float(value) for value in (surface.PlaneParams or ()))
            if len(parameters) != 6 or not all(map(math.isfinite, parameters)):
                raise RuntimeError(f"{SKU}: invalid native end-plane parameters")
            if (
                abs(parameters[0]) < 1e-8
                and abs(parameters[1]) < 1e-8
                and abs(abs(parameters[2]) - 1.0) < 1e-8
            ):
                end_planes.append(parameters[5] * 1000.0)
        elif surface.IsCylinder():
            parameters = tuple(float(value) for value in (surface.CylinderParams or ()))
            if len(parameters) != 7 or not all(map(math.isfinite, parameters)):
                raise RuntimeError(f"{SKU}: invalid native cylinder parameters")
            if (
                all(abs(parameters[index]) < 1e-8 for index in (0, 1, 3, 4))
                and abs(abs(parameters[5]) - 1.0) < 1e-8
            ):
                radii.append(parameters[6] * 1000.0)
    expected_planes = (0.0, SUPPLIER_REFERENCE.length_mm)
    if len(end_planes) != 2 or any(
        not math.isclose(actual, expected, rel_tol=0.0, abs_tol=1e-6)
        for actual, expected in zip(sorted(end_planes), expected_planes, strict=True)
    ):
        raise RuntimeError(f"{SKU}: actual pin end planes do not span the source 4 mm")
    if not radii or any(
        not math.isclose(
            radius, SUPPLIER_REFERENCE.diameter_mm / 2.0, rel_tol=0.0, abs_tol=1e-6
        )
        for radius in radii
    ):
        raise RuntimeError(f"{SKU}: actual pin cylinder differs from the source diameter")


def _source_profile_entities(model: Any, name: str) -> tuple[Any, tuple[Any, ...]]:
    """Resolve the intended profile entities from their native source geometry."""
    raw = _early_bound(model, "IPartDoc").FeatureByName("PinProfile")
    if raw is None:
        raise RuntimeError(f"{SKU}: missing source PinProfile")
    feature = _early_bound(raw, "IFeature")
    sketch = _early_bound(feature.GetSpecificFeature2(), "ISketch")
    segments = tuple(sketch.GetSketchSegments() or ())
    if len(segments) != 7:
        raise RuntimeError(f"{SKU}: unexpected source profile segment inventory")
    records = []
    for raw in segments:
        segment = _early_bound(raw, "ISketchSegment")
        if int(segment.GetType()) != 0:
            raise RuntimeError(f"{SKU}: source profile contains a non-line")
        line = _early_bound(segment, "ISketchLine")
        endpoints = (line.GetStartPoint2(), line.GetEndPoint2())
        coordinates = []
        for raw_point in endpoints:
            point = _early_bound(raw_point, "ISketchPoint")
            xyz = tuple(float(value) * 1000.0 for value in (point.X, point.Y, point.Z))
            if not all(map(math.isfinite, xyz)):
                raise RuntimeError(f"{SKU}: invalid source profile point")
            coordinates.append(xyz)
        records.append((segment, endpoints, coordinates, bool(segment.ConstructionGeometry)))

    def resolve(first, second, construction):
        matches = [
            record for record in records
            if record[3] == construction
            and any(
                math.dist(record[2][0], a) <= 1e-6
                and math.dist(record[2][1], b) <= 1e-6
                for a, b in ((first, second), (second, first))
            )
        ]
        if len(matches) != 1:
            raise RuntimeError(f"{SKU}: intended {name} source profile geometry changed")
        return matches[0]

    outer = PIN_DIA / 2.0
    axis = resolve((0.0, 0.0, 0.0), (-PIN_LEN, 0.0, 0.0), True)
    flank = resolve(
        (-PIN_CHAMFER_AXIAL, outer, 0.0),
        (-(PIN_LEN - PIN_CHAMFER_AXIAL), outer, 0.0),
        False,
    )
    closing = resolve((-PIN_LEN, 0.0, 0.0), (0.0, 0.0, 0.0), False)
    resolve((0.0, 0.0, 0.0), (0.0, PIN_END_RADIUS, 0.0), False)
    resolve((-PIN_LEN, PIN_END_RADIUS, 0.0), (-PIN_LEN, 0.0, 0.0), False)
    resolve(
        (0.0, PIN_END_RADIUS, 0.0), (-PIN_CHAMFER_AXIAL, outer, 0.0), False
    )
    resolve(
        (-(PIN_LEN - PIN_CHAMFER_AXIAL), outer, 0.0),
        (-PIN_LEN, PIN_END_RADIUS, 0.0),
        False,
    )
    _assert_source_end_planes(model)
    entities = (axis[0], flank[0]) if name == "PinDia" else closing[1]
    return feature, entities


def _assert_supplier_pin_reference(
    adapter: Any,
    display: Any,
    *,
    name: str,
    source_model: Any,
) -> None:
    source = SUPPLIER_REFERENCE
    diameter = name == "PinDia"
    display = _early_bound(display, "IDisplayDimension")
    assert_supplier_reference_dimension(
        adapter,
        display,
        label=f"{SKU} {name}",
        units=source.units,
        precision=source.diameter_precision if diameter else source.length_precision,
        expected_mm=source.diameter_mm if diameter else source.length_mm,
        presentation="diameter" if diameter else "length",
    )
    kind = int(display.Type2)
    if (diameter and kind != 15) or (not diameter and kind not in (2, 11, 12)):
        raise RuntimeError(f"{SKU} {name}: source dimension changed native type")
    tolerance = _early_bound(
        _early_bound(display.GetDimension2(0), "IDimension").Tolerance,
        "IDimensionTolerance",
    )
    feature, entities = _source_profile_entities(source_model, name)
    native = _early_bound(display.GetDimension2(0), "IDimension")
    owner = native.GetFeatureOwner()
    if (
        str(native.FullName).split("@")[:2] != [name, "PinProfile"]
        or owner is None
        or int(adapter.swApp.IsSame(owner, feature)) != 1
    ):
        raise RuntimeError(f"{SKU} {name}: imported dimension has the wrong model owner")
    if int(tolerance.Type) != (2 if diameter else 0):
        raise RuntimeError(f"{SKU} {name}: supplier tolerance type changed")
    if diameter and (
        int(display.GetPrimaryTolPrecision2()) != source.diameter_precision
        or not math.isclose(
            float(tolerance.GetMinValue()), PIN_DIA_BAND[0] / 1000.0, abs_tol=1e-12
        )
        or not math.isclose(
            float(tolerance.GetMaxValue()), PIN_DIA_BAND[1] / 1000.0, abs_tol=1e-12
        )
    ):
        raise RuntimeError(f"{SKU} {name}: supplier m6 reference band changed")
    attached = tuple(
        _early_bound(display.GetAnnotation(), "IAnnotation").GetAttachedEntities3()
        or ()
    )
    if len(entities) != 2 or len(attached) != len(entities):
        raise RuntimeError(f"{SKU} {name}: source profile attachments are incomplete")
    remaining = list(attached)
    for expected in entities:
        matches = [
            index for index, actual in enumerate(remaining)
            if actual is not None and int(adapter.swApp.IsSame(actual, expected)) == 1
        ]
        if len(matches) != 1:
            raise RuntimeError(f"{SKU} {name}: source profile attachment changed")
        remaining.pop(matches[0])


def _supplier_references(
    adapter: Any, annotations: list[Any], view: Any
) -> Callable[[], None]:
    required = {}
    names: set[str] = set()
    source = SUPPLIER_REFERENCE
    source_model = _early_bound(view, "IView").ReferencedDocument
    for annotation in annotations:
        name = dimension_name(adapter, annotation)
        if name not in DRAWING_PRECISION_BY_NAME or name in names:
            raise RuntimeError(f"{SKU}: unexpected/duplicate source size {name!r}")
        names.add(name)
        diameter = name == "PinDia"
        display = supplier_reference_dimension(
            adapter,
            _early_bound(annotation, "IAnnotation").GetSpecificAnnotation(),
            label=f"{SKU} {name}",
            units=source.units,
            precision=source.diameter_precision if diameter else source.length_precision,
            expected_mm=source.diameter_mm if diameter else source.length_mm,
            presentation="diameter" if diameter else "length",
        )
        assertion = partial(
            _assert_supplier_pin_reference, adapter, name=name, source_model=source_model
        )
        assertion(display)
        full_name = str(_early_bound(display.GetDimension2(0), "IDimension").FullName)
        if not full_name or full_name in required:
            raise RuntimeError(f"{SKU}: supplier dimension has no unique native identity")
        required[full_name] = ("*Right", assertion)
    if names != set(DRAWING_PRECISION_BY_NAME):
        raise RuntimeError(f"{SKU}: supplier engineering sizes are incomplete")
    return lambda: assert_supplier_pin_dimensions(
        adapter, {"*Right": view}, required, label=SKU
    )



async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open crank-hub-pin source", await adapter.open_model(str(SOURCE)))
    properties = read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Stock Name",
            "Supplier",
            "Supplier SKUs",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Stock Name",
            "Supplier",
            "Supplier SKUs",
        ),
    )
    if (
        properties["Supplier"] != "McMaster-Carr"
        or properties["Supplier SKUs"] != SKU
    ):
        raise RuntimeError(f"{SKU}: source part has a different supplier identity")
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "McMaster 91585A377 Crank Hub Pin Reference Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "crank hub seam pin; ISO 2338-m6; McMaster 91585A377",
            4: "Purchased stock; supplier dimensions are reference information",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=VIEW_SCALE)
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=VIEW_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=VIEW_SCALE)
    for view in (front, right, iso):
        set_hidden_lines_removed(adapter, view)

    annotations = curate_view_dimensions(
        adapter,
        right,
        keep=RIGHT_KEEP,
        view_label="right",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    settled_check = _supplier_references(adapter, annotations, right)
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to MHA-VN-029 end view")
    add_view_centerline(
        adapter,
        right,
        face_xy=(RIGHT_CENTER[0], RIGHT_CENTER[1] + 0.004),
        label="MHA-VN-029 axis centerline",
    )
    add_property_linked_note(adapter, "Manufacturing Notes", 0.016, 0.082)
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="McMaster 91585A377 Crank Hub Pin Reference Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        settled_checks=(settled_check,),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
