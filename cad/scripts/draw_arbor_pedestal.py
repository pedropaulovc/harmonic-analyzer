r"""Create the curated machinist drawing for the cylinder-arbor pedestal."""

from __future__ import annotations

import argparse
import sys
from typing import Any

from arbor_pedestal_spec import GEOMETRIC_TOLERANCES_MM

import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_datum_feature,
    add_feature_control_frame,
    add_native_hole_callout,
    add_property_linked_note,
    add_surface_finish,
    auto_arrange_view_dimensions,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_arc_endpoints_to_center,
    set_basic_dimension,
    set_dimension_callouts,
    set_dimension_precision,
    set_hidden_lines_visible,
    stamp_drawing_summary,
)
from _drawing_entities import CircleEdge, LineEdge, ModelEntities
from _drawing_registry import DRAWINGS_BY_NAME
from _surface_finish import surface_finish_by_key
from arbor_pedestal_spec import (
    BORE_DIA,
    BORE_HEIGHT,
    FOOT_DEPTH,
    FOOT_HEIGHT,
    FOOT_WIDTH,
    SCREW_CLEARANCE_DIA,
    STRAP_T,
    SURFACE_FINISHES,
    TOP_RADIUS,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    dimension_name,
    place_view,
    view_name,
)


SPEC = DRAWINGS_BY_NAME["arbor_pedestal"]
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

SHEET_SCALE = (2.0, 1.0)  # 64 mm tall casting -- 2:1 keeps the strap/bore legible
_S = SHEET_SCALE[0] / 1000.0  # sheet meters per model mm

# The casting spans model y 0 (foot seat) .. 64 (dome top); centre the front
# elevation on that midpoint. Third-angle: the 24x16 foot plan sits ABOVE the
# elevation, the isometric off to the right.
_PART_MID_Y = (
    BORE_HEIGHT + TOP_RADIUS
) / 2.0  # foot 0 .. dome top (bore + dome radius)
FRONT_CENTER = (0.100, 0.150)
TOP_CENTER = (0.100, 0.245)
ISO_CENTER = (0.335, 0.150)


def _front_y(model_y: float) -> float:
    """Sheet Y of a model-Y point in the front view (foot seat at model y=0)."""
    return FRONT_CENTER[1] + (model_y - _PART_MID_Y) * _S


# Front elevation carries the foot width + flange height, the arbor-bore station
# and diameter, and the dome diameter; the plan carries the 16 foot depth.
FRONT_KEEP = {
    "Width": (FRONT_CENTER[0], _front_y(0.0) + 0.032),
    "FootHt": (FRONT_CENTER[0] - 0.030, _front_y(FOOT_HEIGHT / 2.0)),
    "BoreDia": (FRONT_CENTER[0] + 0.068, _front_y(BORE_HEIGHT) - 0.004),
    "DomeDia": (FRONT_CENTER[0] + 0.066, _front_y(BORE_HEIGHT + 9.0)),
}
TOP_KEEP = {
    "Depth": (TOP_CENTER[0] + 0.040, TOP_CENTER[1]),
}
DIMENSION_CALLOUTS = {
    "BoreDia": "THRU",
}
# 3/8 in = 9.525 exactly; show 3 places so the view matches the note (else the
# 2-decimal sheet default prints 9.53 against the DIA 9.525 the note cites).
DIMENSION_PRECISION = {"BoreDia": 3}


def _model_entities(model: Any) -> dict[str, Any]:
    """Resolve both orthographic views' attachments in one model traversal."""
    near_z = FOOT_DEPTH / 2.0 - STRAP_T
    flank_rise = BORE_HEIGHT - FOOT_HEIGHT
    flank_run = (FOOT_WIDTH / 2.0 - TOP_RADIUS) * flank_rise / BORE_HEIGHT
    return ModelEntities(model).resolve({
        "foot": LineEdge((0, 0, -FOOT_DEPTH / 2.0), (1, 0, 0)),
        "side": LineEdge((-FOOT_WIDTH / 2.0, FOOT_HEIGHT / 2.0, -FOOT_DEPTH / 2.0), (0, 1, 0)),
        "flank": LineEdge((TOP_RADIUS + flank_run / 2.0, BORE_HEIGHT - flank_rise / 2.0, near_z), (-flank_run, flank_rise, 0)),
        "bore": CircleEdge(BORE_DIA / 2.0, (0, BORE_HEIGHT, near_z), (0, 0, 1)),
        "dome": CircleEdge(TOP_RADIUS, (0, BORE_HEIGHT, near_z), (0, 0, 1)),
        "screw": CircleEdge(SCREW_CLEARANCE_DIA / 2.0, (0, FOOT_HEIGHT, -5.0), (0, 1, 0)),
        "datum_d": LineEdge((0, FOOT_HEIGHT, -FOOT_DEPTH / 2.0), (1, 0, 0)),
        "strap_near": LineEdge((0, FOOT_HEIGHT, near_z), (1, 0, 0)),
        "far_face": LineEdge((0, 0, FOOT_DEPTH / 2.0), (1, 0, 0)),
    })


@_telemetry.traced("drawing.circle_basic", label_param="label")
def _add_circle_basic(
    adapter: Any,
    view: Any,
    datum_entity: Any,
    circle_entity: Any,
    *,
    orientation: str,
    position: tuple[float, float],
    label: str,
) -> Any:
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    if not drawing.ActivateView(view_name(adapter, view)):
        raise RuntimeError(f"failed to activate view for {label}")
    draw.ClearSelection2(True)
    selection_manager = _early_bound(draw.SelectionManager, "ISelectionMgr")
    for append, raw_entity in ((False, datum_entity), (True, circle_entity)):
        selection_data = selection_manager.CreateSelectData()
        selection_data.View = view
        entity = _early_bound(raw_entity, "IEntity")
        if not entity.Select4(append, selection_data):
            raise RuntimeError(f"failed to select {label} entity")
    if orientation == "horizontal":
        display = draw.AddHorizontalDimension2(*position, 0.0)
    elif orientation == "vertical":
        display = draw.AddVerticalDimension2(*position, 0.0)
    else:
        raise ValueError(f"unsupported circle-dimension orientation: {orientation}")
    draw.ClearSelection2(True)
    if display is None:
        raise RuntimeError(f"failed to create {label} dimension")
    set_arc_endpoints_to_center(adapter, display, label=label)
    return set_basic_dimension(adapter, display, label=label)


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open arbor-pedestal source", await adapter.open_model(str(SOURCE)))
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
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Cylinder-Arbor Pedestal Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "arbor pedestal; gray-iron casting; arbor clamp bore",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(2, 1))
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(2, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(2, 1))
    # The hold-down hole sits behind the upright in this pictorial direction;
    # HLV keeps that manufactured feature visible instead of contradicting plan.
    set_hidden_lines_visible(adapter, iso)
    # The elevation carries the arbor bore as a hidden circle and the flange
    # hold-down hole; the plan shows the foot with the bore + screw crossing it.
    for view in (front, top):
        set_hidden_lines_visible(adapter, view)

    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    top_annotations = curate_view_dimensions(
        adapter, top, keep=TOP_KEEP, view_label="top"
    )
    set_dimension_callouts(
        adapter, [*front_annotations, *top_annotations], DIMENSION_CALLOUTS
    )
    set_dimension_precision(adapter, front_annotations, DIMENSION_PRECISION)
    front_by_name = {
        dimension_name(adapter, annotation): annotation
        for annotation in front_annotations
    }
    # These two dimensions are true-profile coordinates for the straight
    # flanks, not ordinary size tolerances: each flank runs from a BASIC foot
    # top corner to the BASIC crown at its horizontal centreline.
    for name in ("Width", "FootHt"):
        annotation = front_by_name[name]
        display = adapter._attempt(lambda a=annotation: a.GetSpecificAnnotation())
        if display is None:
            raise RuntimeError(f"{name} has no display dimension to box")
        set_basic_dimension(adapter, display, label=f"flank {name} coordinate")
    top_by_name = {
        dimension_name(adapter, annotation): annotation
        for annotation in top_annotations
    }
    depth_annotation = top_by_name["Depth"]
    depth_display = adapter._attempt(lambda: depth_annotation.GetSpecificAnnotation())
    if depth_display is None:
        raise RuntimeError("Depth has no display dimension to box")
    set_basic_dimension(adapter, depth_display, label="far-face depth coordinate")
    dome_annotation = front_by_name["DomeDia"]
    dome_display = adapter._attempt(lambda: dome_annotation.GetSpecificAnnotation())
    if dome_display is None:
        raise RuntimeError("DomeDia has no display dimension to box")
    set_basic_dimension(adapter, dome_display, label="crown true-profile diameter")
    if not auto_center_marks(adapter, top, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to the plan view")

    # Datum A = the foot seat face (the base-seat datum the bore/dome heights
    # measure from). The arbor bore is toleranced parallel to it and carries the
    # clamp-fit finish.
    entities = _model_entities(front.ReferencedDocument)
    foot_entity, side_entity, flank_entity, bore_entity, dome_entity = (
        entities[key] for key in ("foot", "side", "flank", "bore", "dome")
    )
    _add_circle_basic(
        adapter,
        front,
        side_entity,
        bore_entity,
        orientation="horizontal",
        position=(FRONT_CENTER[0], _front_y(BORE_HEIGHT + TOP_RADIUS) + 0.010),
        label="bore horizontal location",
    )
    _add_circle_basic(
        adapter,
        front,
        foot_entity,
        bore_entity,
        orientation="vertical",
        position=(0.060, FRONT_CENTER[1]),
        label="bore vertical location",
    )
    add_datum_feature(
        adapter,
        front,
        datum="A",
        label="foot seat face",
        entity=foot_entity,
    )
    add_datum_feature(
        adapter,
        front,
        datum="B",
        label="left foot side",
        entity=side_entity,
    )
    add_feature_control_frame(
        adapter,
        front,
        characteristic="flatness",
        tolerance=GEOMETRIC_TOLERANCES_MM["datum-A seat flatness"],
        label="datum-A seat flatness",
        entity=foot_entity,
    )
    add_feature_control_frame(
        adapter,
        front,
        characteristic="perpendicularity",
        tolerance=GEOMETRIC_TOLERANCES_MM["datum-B side perpendicularity"],
        datums=("A",),
        quantity="DATUM B SIDE",
        label="datum-B side perpendicularity",
        entity=side_entity,
    )
    # The two BASIC coordinates locate the bore axis from datum A and the left
    # foot side B. Position controls both location and axis orientation.
    add_feature_control_frame(
        adapter,
        front,
        characteristic="position",
        tolerance=GEOMETRIC_TOLERANCES_MM["arbor bore true position"],
        datums=("A", "B"),
        diameter=True,
        label="arbor bore true position",
        entity=bore_entity,
    )
    add_feature_control_frame(
        adapter,
        front,
        characteristic="profile_surface",
        tolerance=GEOMETRIC_TOLERANCES_MM["controlled exterior surface profile"],
        datums=("A", "B"),
        quantity="CROWN + 2 FLANKS + FOOT TOP + RIGHT SIDE",
        label="controlled exterior surface profile",
        entity=flank_entity,
    )
    add_surface_finish(
        adapter,
        front,
        control=surface_finish_by_key(SURFACE_FINISHES, "arbor_bore"),
        label="arbor bore finish",
        entity=bore_entity,
    )
    screw_entity = entities["screw"]
    datum_d_entity = entities["datum_d"]
    strap_near_entity = entities["strap_near"]
    far_face_entity = entities["far_face"]
    # The top and front views are projection-aligned, so a second horizontal
    # 12 BASIC dimension would print directly over the bore's 12 BASIC. The
    # property-linked note explicitly assigns that existing datum-B coordinate
    # to the flange-hole axis; only the independent datum-D coordinate belongs
    # on this view.
    _add_circle_basic(
        adapter,
        top,
        datum_d_entity,
        screw_entity,
        orientation="vertical",
        position=(0.060, TOP_CENTER[1]),
        label="flange-hole location from datum D",
    )
    add_datum_feature(
        adapter,
        top,
        datum="D",
        label="exposed flange edge",
        entity=datum_d_entity,
    )
    add_feature_control_frame(
        adapter,
        top,
        characteristic="perpendicularity",
        tolerance=GEOMETRIC_TOLERANCES_MM["datum-D face perpendicularity"],
        datums=("A", "B"),
        quantity="DATUM D FACE",
        label="datum-D face perpendicularity",
        entity=datum_d_entity,
    )
    _screw_r = SCREW_CLEARANCE_DIA / 2.0 * _S
    add_native_hole_callout(
        adapter,
        top,
        edge=screw_entity,
        callout_xy=(0.180, 0.260),
        label="flange hold-down hole",
    )
    add_feature_control_frame(
        adapter,
        top,
        characteristic="position",
        tolerance=GEOMETRIC_TOLERANCES_MM["flange-hole true position"],
        datums=("A", "B", "D"),
        diameter=True,
        label="flange-hole true position",
        entity=screw_entity,
    )
    add_feature_control_frame(
        adapter,
        top,
        characteristic="profile_surface",
        tolerance=GEOMETRIC_TOLERANCES_MM["strap near-face profile"],
        datums=("A", "B", "D"),
        quantity=f"STRAP NEAR FACE @ BASIC {FOOT_DEPTH - STRAP_T:.2f}",
        label="strap near-face profile",
        entity=strap_near_entity,
    )
    add_feature_control_frame(
        adapter,
        top,
        characteristic="profile_surface",
        tolerance=GEOMETRIC_TOLERANCES_MM["coplanar far-face profile"],
        datums=("A", "B", "D"),
        quantity=f"FOOT + STRAP FAR FACES @ BASIC {FOOT_DEPTH:.2f}",
        label="coplanar far-face profile",
        entity=far_face_entity,
    )

    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.075)

    auto_arrange_view_dimensions(adapter, (front, top, iso))
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Cylinder-Arbor Pedestal Manufacturing Drawing",
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
