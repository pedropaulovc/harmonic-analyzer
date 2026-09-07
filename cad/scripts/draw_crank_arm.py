r"""Create the curated machinist drawing for the crank arm.

The SLDPRT remains authoritative. Model entities identify manufacturing features;
sheet coordinates only place text and views. The sheet is 2:1, with a 1:1 iso.

Run with SolidWorks open::

    uv run python -m doit drawing:crank_arm
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, _early_bound, check
from _drawing_build import ProjectDrawingFactory, TemplateSpec, run_drawing_build
from _drawing_common import (
    AnnotationEntityContext,
    _validate_explicit_annotation_attachment,
    DrawingOutputs,
    add_datum_feature,
    add_entity_dimension,
    add_feature_control_frame,
    add_native_hole_callout,
    add_property_linked_note,
    add_surface_finish,
    curate_view_dimensions,
    finalize_drawing,
    read_required_properties,
    verify_dimension_callouts,
    set_dimension_precision,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    set_arc_endpoints_to_center,
    set_basic_dimension,
    stamp_drawing_summary,
)
from _drawing_entities import (
    CircleEdge,
    FaceBoundary,
    FeatureFace,
    LineEdge,
    ModelEntities,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _gtol_spec import CylinderFace, PlanarFace
from _surface_finish import surface_finish_by_key
from crank_arm_spec import (
    ARM_C2C,
    ARM_END_X,
    ARM_THICKNESS,
    DIMENSION_CALLOUTS,
    DIMPLE_DIA,
    DIMPLE_X,
    GEOMETRIC_TOLERANCES_MM,
    HALF_WIDTH,
    PIN_HOLE_DIA,
    SHAFT_BORE_DIA,
    SURFACE_FINISHES,
)
from solidworks_mcp.adapters.solidworks.drawing import auto_center_marks, place_view


SPEC = DRAWINGS_BY_NAME["crank_arm"]
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
TEMPLATE_SPEC = TemplateSpec(scale=SHEET_SCALE, decimals=2)
FRONT_CENTER = (0.145, 0.135)
TOP_CENTER = (0.145, 0.205)
RIGHT_CENTER = (0.300, 0.135)
ISO_CENTER = (0.360, 0.230)


def _sheet_x(model_x_mm: float) -> float:
    """Annotation layout only: sheet X for the front/top view's model station."""
    bbox_center = (ARM_END_X - HALF_WIDTH) / 2.0
    return FRONT_CENTER[0] + (model_x_mm - bbox_center) * SHEET_SCALE[0] / 1000.0


# Exact feature-face boundaries in model millimetres. Resolve once per build;
# handles never survive a source rebuild, configuration switch or document close.
_END = FeatureFace("Arm", PlanarFace((1, 0, 0), ARM_END_X))
_PIN_SIDE = FeatureFace("Arm", PlanarFace((0, 1, 0), HALF_WIDTH))
ENTITY_ROLES = {
    "shaft": FaceBoundary(
        FeatureFace("ShaftBore", CylinderFace(SHAFT_BORE_DIA)),
        CircleEdge(SHAFT_BORE_DIA / 2, (0, 0, ARM_THICKNESS), (0, 0, 1)),
    ),
    "pivot": FaceBoundary(
        FeatureFace("PivotBore", CylinderFace(15 / 64 * 25.4)),
        CircleEdge(15 / 64 * 25.4 / 2, (ARM_C2C, 0, ARM_THICKNESS), (0, 0, 1)),
    ),
    "dimple": FaceBoundary(
        FeatureFace("Dimple", CylinderFace(DIMPLE_DIA)),
        CircleEdge(DIMPLE_DIA / 2, (DIMPLE_X, 0, ARM_THICKNESS), (0, 0, 1)),
    ),
    "width_lo": FaceBoundary(
        _END,
        LineEdge((ARM_END_X, -HALF_WIDTH, ARM_THICKNESS / 2), (0, 0, 1)),
    ),
    "width_hi": FaceBoundary(
        _END,
        LineEdge((ARM_END_X, HALF_WIDTH, ARM_THICKNESS / 2), (0, 0, 1)),
    ),
    "side_c": FaceBoundary(
        FeatureFace("Arm", PlanarFace((0, -1, 0), HALF_WIDTH)),
        LineEdge((ARM_C2C / 2, -HALF_WIDTH, ARM_THICKNESS), (1, 0, 0)),
    ),
    "datum_a": FaceBoundary(
        _END,
        LineEdge((ARM_END_X, 0, ARM_THICKNESS), (0, 1, 0)),
    ),
    "opposite_a": FaceBoundary(_END, LineEdge((ARM_END_X, 0, 0), (0, 1, 0))),
    # Preserve the pinned baseline's z=0 station boundary pending the datum-side
    # decision documented in crank-arm-entities-results.md. Datum A is z=8.
    "station_a": FaceBoundary(
        _PIN_SIDE,
        LineEdge((ARM_C2C / 2, HALF_WIDTH, 0), (1, 0, 0)),
    ),
    "pin": FaceBoundary(
        _PIN_SIDE,
        CircleEdge(PIN_HOLE_DIA / 2, (0, HALF_WIDTH, ARM_THICKNESS / 2), (0, 1, 0)),
    ),
}

FRONT_KEEP = {
    "ArmEndX": (0.190, 0.086),
    "DimpleX": (_sheet_x(DIMPLE_X / 2.0), 0.112),
    "BossRadius": (0.030, 0.158),
    "ShaftBoreDia": (_sheet_x(0.0), 0.172),
    "DimpleDia": (_sheet_x(DIMPLE_X), 0.172),
}
RIGHT_KEEP = {"Depth": (0.300, 0.108)}
TOP_KEEP = {}


def require_source(adapter: Any, model: Any) -> Any:
    """Reject a wrong file, replaced document or configuration without repairing it."""
    model = _early_bound(model, "IModelDoc2")
    if (
        int(model.GetType()) != 1
        or Path(model.GetPathName()).resolve() != SOURCE.resolve()
        or int(
            adapter.swApp.IsSame(
                model, adapter.swApp.GetOpenDocumentByName(str(SOURCE))
            )
        )
        != 1
    ):
        raise RuntimeError("crank-arm entity bank requires the exact source part")
    manager = _early_bound(model.ConfigurationManager, "IConfigurationManager")
    configuration = _early_bound(manager.ActiveConfiguration, "IConfiguration")
    if str(configuration.Name) != "Default" or tuple(model.GetConfigurationNames()) != (
        "Default",
    ):
        raise RuntimeError(
            "crank-arm entity bank requires the Default-only source configuration"
        )
    return model


async def build(
    adapter: Any, *, drawing_factory: ProjectDrawingFactory
) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")
    check("open crank-arm source", await adapter.open_model(str(SOURCE)))
    callout_source_model = adapter.currentModel
    source_model = require_source(adapter, callout_source_model)
    if int(adapter.swApp.IsSame(adapter.swApp.ActiveDoc, source_model)) != 1:
        raise RuntimeError("crank-arm source is not active before entity resolution")
    bank = ModelEntities(source_model).resolve(ENTITY_ROLES)
    require_source(adapter, source_model)
    read_required_properties(
        source_model,
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
    drawing_model, sheet = drawing_factory(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Crank Arm Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "crank arm; manufacturing drawing; straight cross-hole",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(2, 1))
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(2, 1))
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(2, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 1))

    def entities(view: Any, *roles: str) -> tuple[Any, ...]:
        require_source(adapter, source_model)
        if (
            int(adapter.swApp.IsSame(adapter.currentModel, drawing_model)) != 1
            or int(adapter.swApp.IsSame(adapter.swApp.ActiveDoc, drawing_model)) != 1
            or int(adapter.swApp.IsSame(view.ReferencedDocument, source_model)) != 1
            or str(view.ReferencedConfiguration) != "Default"
        ):
            raise RuntimeError(
                "crank-arm entity selection has the wrong drawing/view/source context"
            )
        return tuple(bank[role] for role in roles)

    for view in (front, top, right, iso):
        entities(view)
    for view in (right, iso):
        set_hidden_lines_removed(adapter, view)
    for view in (front, top):
        set_hidden_lines_visible(adapter, view)
    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    right_annotations = curate_view_dimensions(
        adapter, right, keep=RIGHT_KEEP, view_label="right"
    )
    top_annotations = curate_view_dimensions(
        adapter, top, keep=TOP_KEEP, view_label="top"
    )
    callouts = [*front_annotations, *top_annotations, *right_annotations]
    verify_dimension_callouts(
        adapter,
        callouts,
        {"ShaftBoreDia": DIMENSION_CALLOUTS["ShaftBoreDia"]},
        feature_name="ShaftBoreProfile",
        view=front,
        source_model=callout_source_model,
    )
    verify_dimension_callouts(
        adapter,
        callouts,
        {"DimpleDia": DIMENSION_CALLOUTS["DimpleDia"]},
        feature_name="DimpleProfile",
        view=front,
        source_model=callout_source_model,
    )
    set_dimension_precision(adapter, callouts, {"ShaftBoreDia": 3})
    add_entity_dimension(
        adapter,
        right,
        entities=entities(right, "width_lo", "width_hi"),
        text_xy=(RIGHT_CENTER[0] + 0.050, RIGHT_CENTER[1]),
        label="arm-width overall",
    )
    for view, label in ((front, "front"), (top, "top")):
        if not auto_center_marks(adapter, view, holes=True, size=0.0025):
            raise RuntimeError(f"failed to add ASME center marks to {label} view")
    pivot_location = add_entity_dimension(
        adapter,
        front,
        entities=entities(front, "shaft", "pivot"),
        text_xy=(_sheet_x(ARM_C2C / 2.0), 0.102),
        label="shaft-to-handle-pivot location",
    )
    set_arc_endpoints_to_center(adapter, pivot_location, label="handle-pivot location")
    set_basic_dimension(adapter, pivot_location, label="handle-pivot location")
    handle_transverse = add_entity_dimension(
        adapter,
        front,
        entities=entities(front, "side_c", "pivot"),
        text_xy=(0.255, FRONT_CENTER[1] - 0.008),
        label="handle-pivot transverse location",
        orientation="vertical",
    )
    set_arc_endpoints_to_center(
        adapter, handle_transverse, label="handle-pivot transverse location"
    )
    set_basic_dimension(
        adapter, handle_transverse, label="handle-pivot transverse location"
    )
    dimple_transverse = add_entity_dimension(
        adapter,
        front,
        entities=entities(front, "side_c", "dimple"),
        text_xy=(0.160, FRONT_CENTER[1] - 0.008),
        label="dimple transverse location from datum C",
        orientation="vertical",
    )
    set_arc_endpoints_to_center(
        adapter, dimple_transverse, label="dimple transverse location from datum C"
    )
    pin_station = add_entity_dimension(
        adapter,
        top,
        entities=entities(top, "station_a", "pin"),
        text_xy=(0.045, TOP_CENTER[1] + 0.004),
        label="cross-hole station from datum A",
        orientation="vertical",
    )
    set_arc_endpoints_to_center(
        adapter, pin_station, label="cross-hole station from datum A"
    )
    set_basic_dimension(adapter, pin_station, label="cross-hole station from datum A")
    add_feature_control_frame(
        adapter,
        top,
        entity=entities(top, "pin")[0],
        frame_xy=(0.100, 0.237),
        characteristic="position",
        tolerance=GEOMETRIC_TOLERANCES_MM["cross-hole true position"],
        datums=("A", "B"),
        diameter=True,
        label="cross-hole true position",
    )
    add_native_hole_callout(
        adapter,
        top,
        edge=entities(top, "pin")[0],
        callout_xy=(0.170, 0.230),
        label="crank-arm cross-hole",
    )
    add_datum_feature(
        adapter,
        right,
        entity=entities(right, "datum_a")[0],
        symbol_xy=(RIGHT_CENTER[0] - 0.022, RIGHT_CENTER[1]),
        datum="A",
        label="crank broad face",
    )
    # Native placement is intentional: the explicit entity does not accept the
    # old fixed-position datum-B request (retained native positive-control repro).
    add_datum_feature(
        adapter,
        front,
        entity=entities(front, "shaft")[0],
        datum="B",
        label="crank shaft axis",
        shoulder=True,
    )
    add_datum_feature(
        adapter,
        front,
        entity=entities(front, "side_c")[0],
        symbol_xy=(_sheet_x((ARM_C2C + ARM_END_X) / 2), FRONT_CENTER[1] - 0.038),
        datum="C",
        label="crank width side",
    )
    add_feature_control_frame(
        adapter,
        front,
        entity=entities(front, "pivot")[0],
        frame_xy=(0.222, 0.167),
        characteristic="position",
        tolerance=GEOMETRIC_TOLERANCES_MM["handle pivot position"],
        datums=("A", "B", "C"),
        diameter=True,
        label="handle pivot position",
    )
    add_native_hole_callout(
        adapter,
        front,
        edge=entities(front, "pivot")[0],
        callout_xy=(0.258, 0.110),
        label="handle pivot hole",
    )
    add_feature_control_frame(
        adapter,
        right,
        entity=entities(right, "opposite_a")[0],
        frame_xy=(0.316, 0.118),
        characteristic="parallelism",
        tolerance=GEOMETRIC_TOLERANCES_MM["crank broad-face parallelism"],
        datums=("A",),
        label="crank broad-face parallelism",
    )
    finish = add_surface_finish(
        adapter,
        front,
        entity=entities(front, "shaft")[0],
        entity_context=AnnotationEntityContext.MODEL,
        # Native placement avoids a separate arrow competing with datum B.
        control=surface_finish_by_key(SURFACE_FINISHES, "shaft_bore"),
        label="shaft bore finish",
    )
    # Move the no-leader symbol along its attached rim, not its leader endpoint.
    # The 30-degree layout seed keeps the Ra text below the arm's top outline.
    # Native SetPosition2 may constrain this layout seed to the attached edge.
    annotation = _early_bound(finish.GetAnnotation(), "IAnnotation")
    position = tuple(annotation.GetPosition() or ())
    if len(position) != 3:
        raise RuntimeError("shaft bore finish: invalid native symbol position")
    shaft = entities(front, "shaft")[0]  # Recheck ownership before mutation.
    if not annotation.SetPosition2(
        _sheet_x(SHAFT_BORE_DIA * 3.0**0.5 / 4.0),
        FRONT_CENTER[1] + SHAFT_BORE_DIA * SHEET_SCALE[0] / 4000.0,
        position[2],
    ):
        raise RuntimeError("shaft bore finish: native symbol move failed")
    entities(front, "shaft")  # Recheck the active drawing before rebuilding.
    adapter.currentModel.EditRebuild3()
    _validate_explicit_annotation_attachment(
        adapter,
        annotation,
        front,
        shaft,
        entity_type="EDGE",
        entity_context=AnnotationEntityContext.MODEL,
        label="shaft bore finish",
    )
    add_property_linked_note(adapter, "Manufacturing Notes", 0.014, 0.060)
    add_property_linked_note(adapter, "Isometric View Note", 0.330, 0.185)
    return await finalize_drawing(
        adapter, OUTPUTS, pdf_title="Crank Arm Manufacturing Drawing", scale=SHEET_SCALE
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_drawing_build(build, spec=TEMPLATE_SPEC))
