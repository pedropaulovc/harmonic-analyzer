r"""Create the summing-lever manufacturing drawing under the simplicity policy.

A portrait 1:1 sheet: the plan (looking down on the coefficients plate) is
the principal view and carries every X and Z coordinate from one origin each
(X from the knife-edge ridge, Z from the plate end); the end profile below it
carries the thicknesses; DETAIL A enlarges the knife-edge hex, the one
surface the lever runs on. The policy allowlists exactly one geometric
control here -- the 20-hole spring pattern off the knife edge (A) and a plate
end (B) -- so the anchor eye is an ordinary coordinate and the print carries
no other frame, datum or basic. The SLDPRT remains authoritative.

Run with SolidWorks open::

    uv run python cad\scripts\draw_summing_lever.py summing-lever
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_datum_feature,
    add_edge_dimension,
    add_feature_control_frame,
    add_native_hole_callout,
    add_property_linked_note,
    add_surface_finish,
    create_detail_view,
    curate_view_dimensions,
    dimension_name,
    finalize_drawing,
    model_point_in_view,
    new_project_drawing,
    read_required_properties,
    set_arc_endpoints_to_center,
    set_basic_dimension,
    set_dimension_precision,
    set_hidden_lines_visible,
    set_reference_dimension,
    stamp_drawing_summary,
    view_name,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _hole_spec import blind_cut_dia_mm, drill_process
from _surface_finish import surface_finish_by_key
from summing_lever_spec import (
    ANCHOR_BORE_R,
    ANCHOR_R,
    CHANNEL_PITCH,
    GEOMETRIC_TOLERANCES_MM,
    HEX_H,
    HEX_W,
    HEX_Z_INNER,
    HEX_Z_OUTER,
    HOLE_END_OFFSET_FIRST,
    HOLE_SPEC,
    HOLE_X,
    HOLE_Z_FIRST,
    PLATE_L,
    PLATE_T,
    PLATE_W,
    SURFACE_FINISHES,
    TIP_X,
)
from solidworks_mcp.adapters.pywin32_adapter import null_callout
from solidworks_mcp.adapters.solidworks.drawing import place_view


SPEC = DRAWINGS_BY_NAME["summing_lever"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"], pdf=SPEC.outputs["pdf"], png=SPEC.outputs["png"]
)
SLDDRW, PDF, PNG = OUTPUTS.slddrw, OUTPUTS.pdf, OUTPUTS.png
SHEET_SCALE = (1.0, 1.0)
DETAIL_SCALE = (4, 1)
ISO_SCALE = (1, 5)

# Portrait: the 196 mm plan stands upright with the end profile projected
# below it; the detail and isometric take the right-hand column.
TOP_CENTER = (0.118, 0.245)
FRONT_CENTER = (0.118, 0.105)
DETAIL_CENTER = (0.225, 0.200)
ISO_CENTER = (0.232, 0.108)
NOTES_XY = (0.150, 0.405)
ISO_NOTE_XY = (0.208, 0.080)

# Model-dimension imports the print keeps, by view, at their text positions.
# The pivot Ø is authored on the Front plane so it only imports into the end
# profile; it is then MOVED onto the plan where the cylinder reads as a band.
FRONT_KEEP = {"CylDia": (0.100, 0.132)}
TOP_KEEP = {"PlateWidth": (0.161, 0.364), "AnchorOuterDia": (0.086, 0.212)}
CYL_DIA_XY = (0.139, 0.132)
DIMENSION_PRECISION = {"PlateWidth": 1, "CylDia": 1, "AnchorOuterDia": 1}

# Detail circle around the +Z trunnion hex in the end profile (sheet meters).
DETAIL_RADIUS = 0.0075
HEX_Z_MID = (HEX_Z_INNER + HEX_Z_OUTER) / 2.0
KNIFE_FACE_MID = (HEX_W / 4.0, 3.0 * HEX_H / 8.0)  # upper-right face midpoint


def _point(
    adapter: Any, view: Any, xyz_mm: tuple[float, float, float]
) -> tuple[float, float]:
    return model_point_in_view(
        adapter,
        view,
        tuple(value / 1000.0 for value in xyz_mm),
        label="lever dimension pick",
    )


def _measured(display: Any) -> float:
    native = _early_bound(display, "IDisplayDimension")
    return float(_early_bound(native.GetDimension2(0), "IDimension").SystemValue)


def _checked_dimension(
    adapter: Any,
    view: Any,
    *,
    p0: tuple[float, float, float],
    p1: tuple[float, float, float],
    text_xy: tuple[float, float],
    label: str,
    expected_mm: float,
    orientation: str,
    precision: int,
    entity_types: tuple[str, str] = ("EDGE", "EDGE"),
    center: bool = False,
) -> Any:
    """Dimension two picked model points and verify the native value."""
    display = add_edge_dimension(
        adapter,
        view,
        p0=_point(adapter, view, p0),
        p1=_point(adapter, view, p1),
        text_xy=text_xy,
        label=label,
        orientation=orientation,
        entity_types=entity_types,
    )
    if center:
        set_arc_endpoints_to_center(adapter, display, label=label)
    measured_mm = _measured(display) * 1000.0
    if abs(measured_mm - expected_mm) > 1e-5:
        raise RuntimeError(
            f"{label}: measured {measured_mm:g}, expected {expected_mm:g} mm"
        )
    annotation = _early_bound(
        _early_bound(display, "IDisplayDimension").GetAnnotation(), "IAnnotation"
    )
    set_dimension_precision(
        adapter, [annotation], {dimension_name(adapter, annotation): precision}
    )
    return display


def _move_dimension(
    adapter: Any,
    annotation: Any,
    target: Any,
    text_xy: tuple[float, float],
    *,
    source_view: Any,
) -> Any:
    """Move, never copy, a fitted model dimension and verify its new owner."""
    name = dimension_name(adapter, annotation)
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    if not ddoc.ActivateView(view_name(adapter, source_view)):
        raise RuntimeError(f"{name}: failed to activate source dimension view")
    draw.ClearSelection2(True)
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    selection_name = str(display.GetNameForSelection() or "")
    if not selection_name or not draw.Extension.SelectByID2(
        selection_name, "DIMENSION", 0.0, 0.0, 0.0, False, 0, null_callout(), 0
    ):
        raise RuntimeError(
            f"failed to select model dimension {name}: {selection_name!r}"
        )
    ddoc.DragModelDimension(view_name(adapter, target), 2, text_xy[0], text_xy[1], 0.0)
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    annotations = [
        _early_bound(item, "IAnnotation")
        for item in (_early_bound(target, "IView").GetAnnotations() or ())
    ]
    matches = [item for item in annotations if dimension_name(adapter, item) == name]
    if len(matches) != 1:
        raise RuntimeError(f"{name}: native dimension did not move into target view")
    return matches[0]


@_telemetry.traced("drawing.anchor_bore")
def _add_anchor_bore(adapter: Any, view: Any) -> Any:
    """Ø3.0 DRILL THRU on the counter-spring eye, read off the plan."""
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    if not ddoc.ActivateView(view_name(adapter, view)):
        raise RuntimeError("failed to activate the plan for the anchor bore")
    draw.ClearSelection2(True)
    x, y = _point(adapter, view, (TIP_X, ANCHOR_R, -ANCHOR_BORE_R))
    if not draw.Extension.SelectByID2(
        "", "EDGE", x, y, 0.0, False, 0, null_callout(), 0
    ):
        raise RuntimeError(f"failed to select the anchor bore at sheet ({x:g}, {y:g})")
    centre = _point(adapter, view, (TIP_X, ANCHOR_R, 0.0))
    display = draw.AddDimension2(centre[0] - 0.005, centre[1] - 0.025, 0.0)
    draw.ClearSelection2(True)
    if display is None:
        raise RuntimeError("failed to create the anchor bore diameter")
    measured_mm = _measured(display) * 1000.0
    if abs(measured_mm - 2.0 * ANCHOR_BORE_R) > 1e-5:
        raise RuntimeError(
            f"anchor bore measured {measured_mm:g}, expected {2.0 * ANCHOR_BORE_R:g}"
        )
    display = _early_bound(display, "IDisplayDimension")
    display.SetText(4, "DRILL THRU")  # swDimensionTextCalloutBelow
    display.SetPrecision3(1, -1, -1, -1)
    if (
        str(display.GetText(4) or "") != "DRILL THRU"
        or int(display.GetPrimaryPrecision2()) != 1
    ):
        raise RuntimeError("anchor bore callout did not persist")
    draw.EditRebuild3()
    return display


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")
    check("open summing-lever source", await adapter.open_model(str(SOURCE)))
    properties = (
        "Number",
        "Revision",
        "Title",
        "Material Specification",
        "Finish",
        "Quantity",
        "Manufacturing Notes",
        "Isometric View Note",
    )
    read_required_properties(
        adapter.currentModel,
        properties,
        required=tuple(
            name for name in properties if name not in {"Revision", "Title"}
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Summing Lever Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "summing lever; ferrous stock or casting; knife-edge first-class lever",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=SHEET_SCALE)
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=SHEET_SCALE)
    for view, label in ((top, "plan"), (front, "end profile")):
        set_hidden_lines_visible(adapter, view)
        # Arc-to-line tangencies on the cast arm and ribs are not edges to cut.
        view.SetDisplayTangentEdges2(0)
        if int(view.GetDisplayTangentEdges2()) != 0:
            raise RuntimeError(f"failed to hide {label} tangent edges")
        view.UpdateViewDisplayGeometry()
    # The plan puts model -Z at the top of the sheet; every Z pick below
    # assumes it, so fail loud if the seat's Top orientation differs.
    if (
        _point(adapter, top, (0.0, 0.0, -1.0))[1]
        <= _point(adapter, top, (0.0, 0.0, 1.0))[1]
    ):
        raise RuntimeError("plan view does not put model -Z at the top of the sheet")
    detail = create_detail_view(
        adapter,
        front,
        center=_point(adapter, front, (0.0, 0.0, HEX_Z_OUTER)),
        radius=DETAIL_RADIUS,
        view_xy=DETAIL_CENTER,
        detail_label="A",
        scale=DETAIL_SCALE,
        label="knife-edge hex",
    )
    set_hidden_lines_visible(adapter, detail)
    # The shared finalizer sets and verifies precision Shaded With Edges and
    # high-quality cosmetic threads for every standard isometric.
    place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)

    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="end profile"
    )
    top_annotations = curate_view_dimensions(
        adapter, top, keep=TOP_KEEP, view_label="plan"
    )
    annotations = [
        *top_annotations,
        _move_dimension(
            adapter, front_annotations[0], top, CYL_DIA_XY, source_view=front
        ),
    ]
    set_dimension_precision(adapter, annotations, DIMENSION_PRECISION)

    # --- Plan: Z from the plate end, X from the knife-edge ridge. ---
    z_end = PLATE_L / 2.0
    top_body_end = (-14.0, 0.0, -z_end)
    bottom_body_end = (-14.0, 0.0, z_end)
    top_trunnion_end = (0.0, HEX_H / 2.0, -HEX_Z_OUTER)
    bottom_trunnion_end = (0.0, HEX_H / 2.0, HEX_Z_OUTER)
    chain_x = 0.043
    for label, p0, p1, y in (
        ("upper trunnion length", top_trunnion_end, top_body_end, 0.332),
        ("body length", top_body_end, bottom_body_end, 0.275),
        ("lower trunnion length", bottom_body_end, bottom_trunnion_end, 0.158),
    ):
        _checked_dimension(
            adapter,
            top,
            p0=p0,
            p1=p1,
            text_xy=(chain_x, y),
            label=label,
            expected_mm=(HEX_Z_OUTER - HEX_Z_INNER) if "trunnion" in label else PLATE_L,
            orientation="vertical",
            precision=1,
        )
    overall = _checked_dimension(
        adapter,
        top,
        p0=top_trunnion_end,
        p1=bottom_trunnion_end,
        text_xy=(0.031, 0.215),
        label="overall length",
        expected_mm=2.0 * HEX_Z_OUTER,
        orientation="vertical",
        precision=1,
    )
    set_reference_dimension(
        adapter,
        _early_bound(overall, "IDisplayDimension").GetAnnotation(),
        label="overall length",
    )
    upper_ridge = (0.0, HEX_H / 2.0, -HEX_Z_MID)
    lower_ridge = (0.0, HEX_H / 2.0, HEX_Z_MID)
    _checked_dimension(
        adapter,
        top,
        p0=upper_ridge,
        p1=(TIP_X, ANCHOR_R, -ANCHOR_BORE_R),
        text_xy=(0.100, 0.356),
        label="anchor bore from knife edge",
        expected_mm=-TIP_X,
        orientation="horizontal",
        precision=1,
        center=True,
    )
    hole_dia = blind_cut_dia_mm(HOLE_SPEC)
    second_hole = (HOLE_X, PLATE_T / 2.0, HOLE_Z_FIRST + CHANNEL_PITCH)
    row_x = _checked_dimension(
        adapter,
        top,
        p0=upper_ridge,
        p1=(HOLE_X, PLATE_T / 2.0, HOLE_Z_FIRST - hole_dia / 2.0),
        text_xy=(0.159, 0.356),
        label="spring-hole row X",
        expected_mm=HOLE_X,
        orientation="horizontal",
        precision=2,
        center=True,
    )
    set_basic_dimension(adapter, row_x, label="spring-hole row X")
    plate_end = (PLATE_W / 2.0 + 5.0, PLATE_T / 2.0, -z_end)
    start_z = _checked_dimension(
        adapter,
        top,
        p0=plate_end,
        p1=(HOLE_X, PLATE_T / 2.0, HOLE_Z_FIRST - hole_dia / 2.0),
        text_xy=(0.192, 0.316),
        label="spring-hole start Z",
        expected_mm=HOLE_END_OFFSET_FIRST,
        orientation="vertical",
        precision=2,
        center=True,
    )
    set_basic_dimension(adapter, start_z, label="spring-hole start Z")
    pitch = _checked_dimension(
        adapter,
        top,
        p0=(HOLE_X, PLATE_T / 2.0, HOLE_Z_FIRST + hole_dia / 2.0),
        p1=(HOLE_X, PLATE_T / 2.0, second_hole[2] - hole_dia / 2.0),
        text_xy=(0.200, 0.308),
        label="spring-hole pitch",
        expected_mm=CHANNEL_PITCH,
        orientation="vertical",
        precision=2,
        center=True,
    )
    set_basic_dimension(adapter, pitch, label="spring-hole pitch")
    _checked_dimension(
        adapter,
        top,
        p0=(-HEX_W / 2.0, HEX_H / 4.0, HEX_Z_MID),
        p1=(HEX_W / 2.0, HEX_H / 4.0, HEX_Z_MID),
        text_xy=(0.139, 0.140),
        label="trunnion across flats",
        expected_mm=HEX_W,
        orientation="horizontal",
        precision=2,
    )
    _add_anchor_bore(adapter, top)

    # Datums: A is the knife-edge ridge (the lever's rock axis), B the plate end
    # the hole pattern starts from; both on the plan where they are edges.
    add_datum_feature(
        adapter,
        top,
        edge_xy=_point(adapter, top, lower_ridge),
        symbol_xy=(0.152, 0.150),
        datum="A",
        label="knife-edge ridge",
    )
    add_datum_feature(
        adapter,
        top,
        edge_xy=_point(adapter, top, (PLATE_W / 4.0, PLATE_T / 2.0, -z_end)),
        symbol_xy=(0.150, 0.330),
        datum="B",
        label="plate end face",
    )
    third_hole = (HOLE_X, PLATE_T / 2.0, HOLE_Z_FIRST + 2.0 * CHANNEL_PITCH)
    sixth_hole = (HOLE_X, PLATE_T / 2.0, HOLE_Z_FIRST + 5.0 * CHANNEL_PITCH)
    add_native_hole_callout(
        adapter,
        top,
        edge_xy=_point(
            adapter, top, (third_hole[0] + hole_dia / 2.0, third_hole[1], third_hole[2])
        ),
        callout_xy=(0.215, 0.300),
        label="spring-hole pattern",
        process=drill_process(HOLE_SPEC),
    )
    add_feature_control_frame(
        adapter,
        top,
        edge_xy=_point(
            adapter,
            top,
            (sixth_hole[0] + hole_dia / 2.0, sixth_hole[1], sixth_hole[2]),
        ),
        frame_xy=(0.215, 0.262),
        characteristic="position",
        tolerance=GEOMETRIC_TOLERANCES_MM["spring-hole pattern position"],
        datums=("A", "B"),
        diameter=True,
        quantity="20X",
        label="spring-hole pattern position",
    )

    # --- End profile: the two cast thicknesses the views cannot imply. ---
    stub_x = PLATE_W - 3.5  # past the edge rib's tip, where the plate shows
    _checked_dimension(
        adapter,
        front,
        p0=(stub_x, PLATE_T / 2.0, z_end),
        p1=(stub_x, -PLATE_T / 2.0, z_end),
        text_xy=(0.192, FRONT_CENTER[1]),
        label="plate thickness",
        expected_mm=PLATE_T,
        orientation="vertical",
        precision=1,
    )
    eye_x = TIP_X - ANCHOR_R / 2.0
    _checked_dimension(
        adapter,
        front,
        p0=(eye_x, ANCHOR_R, 0.0),
        p1=(eye_x, -ANCHOR_R, 0.0),
        text_xy=(0.043, FRONT_CENTER[1]),
        label="anchor eye height",
        expected_mm=2.0 * ANCHOR_R,
        orientation="vertical",
        precision=1,
    )

    # --- DETAIL A: the knife-edge hex, vertex to vertex, and its ground face. ---
    _checked_dimension(
        adapter,
        detail,
        p0=(0.0, HEX_H / 2.0, HEX_Z_OUTER),
        p1=(0.0, -HEX_H / 2.0, HEX_Z_OUTER),
        text_xy=(DETAIL_CENTER[0] - 0.040, DETAIL_CENTER[1]),
        label="trunnion vertex height",
        expected_mm=HEX_H,
        orientation="vertical",
        precision=2,
        entity_types=("VERTEX", "VERTEX"),
    )
    add_surface_finish(
        adapter,
        detail,
        edge_xy=_point(adapter, detail, (*KNIFE_FACE_MID, HEX_Z_MID)),
        symbol_xy=(DETAIL_CENTER[0] - 0.033, DETAIL_CENTER[1] + 0.040),
        control=surface_finish_by_key(SURFACE_FINISHES, "knife_edge_ridge"),
        label="knife-edge face finish",
        char_height=0.0025,
    )

    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Summing Lever Manufacturing Drawing",
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
