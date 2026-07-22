r"""Create the curated machinist drawing for the cone pivot post."""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_attached_note,
    add_datum_feature,
    add_feature_control_frame,
    add_property_linked_note,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_dimension_precision,
    set_basic_dimension,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from cone_pivot_post_spec import (
    BLOCK_DIA,
    BLOCK_HEIGHT,
    BORE_DIA,
    BORE_HEIGHT,
    CRANK_BORE_DIA,
    CRANK_BORE_HEIGHT,
    CRANK_AXIS_ORIENTATION_NOTE,
    CRANK_AXIS_POINTS,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    auto_center_marks,
    dimension_name,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["cone_pivot_post"]
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
_S = SHEET_SCALE[0] / 1000.0  # sheet meters per model mm

# Third-angle: the round Ø24 plan sits ABOVE the front elevation (which carries
# the column height + both bore stations); the isometric is off to the right.
FRONT_CENTER = (0.100, 0.150)
TOP_CENTER = (0.100, 0.235)
ISO_CENTER = (0.330, 0.150)


def _front_y(model_y: float) -> float:
    """Sheet Y of a model-Y point in the front view (1:1, foot at model y=0)."""
    return FRONT_CENTER[1] + (model_y - BLOCK_HEIGHT / 2.0) * _S


# Front elevation carries the column height, the journal-bore station and the
# journal bore diameter; the plan carries the round Ø24.
FRONT_KEEP = {
    "BlockHt": (FRONT_CENTER[0] - 0.045, FRONT_CENTER[1]),
    "BoreZ": (FRONT_CENTER[0] - 0.030, _front_y(BORE_HEIGHT / 2.0)),
    "BoreDia": (FRONT_CENTER[0] + 0.040, _front_y(BORE_HEIGHT)),
}
TOP_KEEP = {
    "BlockDia": (TOP_CENTER[0] + 0.040, TOP_CENTER[1]),
}
DIMENSION_CALLOUTS = {
    "BlockDia": "+/-0.05",
    "BoreDia": "+0.005/-0.005 THRU",
}
# 3/8 in = 9.525 exactly; the sheet default of 2 decimals prints 9.53, a false
# contradiction of the DIA 9.525 the note and the mating cone shaft are built on.
DIMENSION_PRECISION = {"BoreDia": 3}


def _circular_edge(
    adapter: Any,
    view: Any,
    *,
    radius_mm: float,
    center_y_mm: float,
) -> Any:
    """Return the visible circular edge matching radius and model height."""
    drawing_view = _early_bound(view, "IView")
    components = drawing_view.GetVisibleComponents() or []
    candidates: list[tuple[float, float, Any]] = []
    for component in components:
        edges = drawing_view.GetVisibleEntities2(component, 1) or []
        for edge in edges:
            edge = _early_bound(edge, "IEdge")
            curve = edge.GetCurve()
            if curve is None:
                continue
            curve = _early_bound(curve, "ICurve")
            if not curve.IsCircle():
                continue
            params = tuple(float(value) for value in curve.CircleParams)
            candidates.append((params[6] * 1000.0, params[1] * 1000.0, edge))
    if not candidates:
        raise RuntimeError("front view has no visible circular model edges")
    _telemetry.info(
        "front-view circular edges (radius,height mm): "
        + ", ".join(
            f"({radius:.3f},{center_y:.3f})"
            for radius, center_y, _edge in candidates
        )
    )
    radius, center_y, edge = min(
        candidates,
        key=lambda item: abs(item[0] - radius_mm) + abs(item[1] - center_y_mm),
    )
    if abs(radius - radius_mm) > 0.01 or abs(center_y - center_y_mm) > 0.01:
        raise RuntimeError(
            f"no circular edge matches radius {radius_mm:.3f} mm at "
            f"height {center_y_mm:.3f} mm"
        )
    return edge


def _crank_bore_edge(
    adapter: Any, view: Any
) -> tuple[Any, tuple[float, float]]:
    """Return a visible rim edge adjacent to the modeled crank-bore cylinder."""
    expected_radius_m = CRANK_BORE_DIA / 2000.0
    drawing_view = _early_bound(view, "IView")
    candidates: list[Any] = []
    for component in drawing_view.GetVisibleComponents() or []:
        for edge in drawing_view.GetVisibleEntities2(component, 1) or []:
            edge = _early_bound(edge, "IEdge")
            for face in edge.GetTwoAdjacentFaces2() or []:
                if face is None:
                    continue
                face = _early_bound(face, "IFace2")
                surface = _early_bound(face.GetSurface(), "ISurface")
                if not surface.IsCylinder():
                    continue
                parameters = surface.CylinderParams
                if abs(float(parameters[6]) - expected_radius_m) > 1e-6:
                    continue
                candidates.append(edge)
                break
    if not candidates:
        raise RuntimeError(
            "front view has no visible edge adjacent to the modeled crank-bore "
            f"cylinder at radius {expected_radius_m:g} m"
        )
    return candidates[0], (FRONT_CENTER[0], _front_y(CRANK_BORE_HEIGHT))


def _format_table_note(note: Any, *, label: str) -> Any:
    """Apply the compact coordinate-table text size to a native note."""
    note = _early_bound(note, "INote", "GetAnnotation")
    annotation = _early_bound(
        note.GetAnnotation(), "IAnnotation", "GetTextFormat", "SetTextFormat"
    )
    text_format = annotation.GetTextFormat(0)
    if text_format is None:
        raise RuntimeError(f"{label} has no text format")
    text_format.CharHeight = 0.0025
    if not annotation.SetTextFormat(0, False, text_format):
        raise RuntimeError(f"failed to size {label}")
    return note


def _add_table_note(adapter: Any, text: str, x: float, y: float, *, label: str) -> Any:
    note = add_note(adapter, text, x, y)
    if note is None:
        raise RuntimeError(f"failed to add {label}")
    return _format_table_note(note, label=label)


def _add_basic_value(adapter: Any, value: float, x: float, y: float) -> Any:
    """Add one individually boxed BASIC coordinate value."""
    note = _add_table_note(
        adapter,
        f"{value:.3f}",
        x,
        y,
        label="crank-axis BASIC coordinate",
    )
    note = _early_bound(
        note,
        "INote",
        "SetBalloon",
        "HasBalloon",
        "GetBalloonStyle",
        "GetBalloonSize",
    )
    # swBS_Box=4 and swBF_Tightest=0 produce an ASME-style BASIC frame.
    if not note.SetBalloon(4, 0):
        raise RuntimeError("SolidWorks rejected a BASIC crank-axis coordinate")
    if (
        not note.HasBalloon()
        or int(note.GetBalloonStyle()) != 4
        or int(note.GetBalloonSize()) != 0
    ):
        raise RuntimeError("BASIC crank-axis coordinate box did not persist")
    return note


def _add_crank_axis_table(adapter: Any) -> None:
    """Add a conventional two-point BASIC coordinate definition."""
    _add_table_note(
        adapter,
        "CRANK-BORE AXIS COORDINATES (mm)",
        0.220,
        0.265,
        label="crank-axis table heading",
    )
    _add_table_note(
        adapter,
        CRANK_AXIS_ORIENTATION_NOTE,
        0.220,
        0.256,
        label="crank-axis coordinate orientation",
    )
    _add_table_note(
        adapter,
        "POINT        X               Y               Z",
        0.220,
        0.241,
        label="crank-axis coordinate columns",
    )
    for row_y, (point, x_value, y_value, z_value) in zip(
        (0.232, 0.221), CRANK_AXIS_POINTS, strict=True
    ):
        _add_table_note(
            adapter, point, 0.220, row_y, label=f"crank-axis point {point}"
        )
        for column_x, value in zip(
            (0.248, 0.290, 0.332),
            (x_value, y_value, z_value),
            strict=True,
        ):
            _add_basic_value(adapter, value, column_x, row_y)
    _add_table_note(
        adapter,
        "AXIS = LINE THROUGH P AND Q",
        0.280,
        0.209,
        label="crank-axis table definition",
    )
    adapter.currentModel.EditRebuild3()


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open cone-pivot-post source", await adapter.open_model(str(SOURCE)))
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
            0: "Cone Pivot Post Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "cone pivot post; cast iron column; journal + crank bores",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(1, 1))
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(1, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 2))
    set_hidden_lines_removed(adapter, iso)
    # The elevation carries both bores as hidden circles; the plan shows them
    # crossing the round column.
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
    bore_height_annotation = front_by_name["BoreZ"]
    bore_height_display = adapter._attempt(
        lambda: bore_height_annotation.GetSpecificAnnotation()
    )
    if bore_height_display is None:
        raise RuntimeError("BoreZ has no display dimension to box")
    set_basic_dimension(
        adapter, bore_height_display, label="journal-bore basic height"
    )
    if not auto_center_marks(adapter, top, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to the plan view")

    # Datum A establishes height, datum B is the turned column axis, and the
    # controlled journal bore becomes clocking datum C for the oblique crank
    # bore.  Native position frames give both axes finite, inspectable zones;
    # the property-linked notes carry their basic angle/offset geometry.
    _bore_r = BORE_DIA / 2.0 * _S
    foot_edge = (FRONT_CENTER[0] + 0.005, _front_y(0.0))
    foot_entity = _circular_edge(
        adapter, front, radius_mm=BLOCK_DIA / 2.0, center_y_mm=0.0
    )
    add_datum_feature(
        adapter,
        front,
        edge_xy=foot_edge,
        symbol_xy=(foot_edge[0], _front_y(0.0) - 0.010),
        datum="A",
        label="foot seat face",
        entity=foot_entity,
    )
    add_feature_control_frame(
        adapter,
        front,
        edge_xy=foot_edge,
        frame_xy=(0.145, _front_y(0.0) + 0.015),
        characteristic="flatness",
        tolerance="0.05",
        label="datum-A seat flatness",
        entity=foot_entity,
    )
    post_od_entity = _circular_edge(
        adapter, top, radius_mm=BLOCK_DIA / 2.0, center_y_mm=BLOCK_HEIGHT
    )
    # The circular outline identifies the complete cylindrical datum feature.
    # SolidWorks constrains an edge-attached datum symbol to a legal point on
    # that circle, so permit only the measured small snap from the requested
    # clear-space position; the sheet layout audit still checks the result.
    add_datum_feature(
        adapter,
        top,
        edge_xy=(TOP_CENTER[0], TOP_CENTER[1] - BLOCK_DIA / 2.0 * _S),
        symbol_xy=(TOP_CENTER[0] + 0.026, TOP_CENTER[1] - 0.020),
        datum="B",
        label="column outside diameter",
        entity=post_od_entity,
        position_tolerance_m=0.016,
    )
    post_side_xy = (
        FRONT_CENTER[0] + BLOCK_DIA / 2.0 * _S,
        _front_y(70.0),
    )
    add_feature_control_frame(
        adapter,
        front,
        edge_xy=post_side_xy,
        frame_xy=(0.220, 0.125),
        characteristic="cylindricity",
        tolerance="0.05",
        quantity="DATUM B OD",
        label="datum-B outside-diameter form",
        entity_type="SILHOUETTE",
    )
    add_feature_control_frame(
        adapter,
        top,
        edge_xy=TOP_KEEP["BlockDia"],
        frame_xy=(0.160, 0.220),
        characteristic="perpendicularity",
        tolerance="0.05",
        datums=("A",),
        diameter=True,
        label="datum-B axis perpendicularity",
        entity_type="DIMENSION",
    )
    add_feature_control_frame(
        adapter,
        front,
        edge_xy=(FRONT_CENTER[0] + _bore_r, _front_y(BORE_HEIGHT)),
        frame_xy=(0.170, _front_y(BORE_HEIGHT) - 0.010),
        characteristic="position",
        tolerance="0.05",
        datums=("A", "B"),
        diameter=True,
        label="journal-bore true position",
    )
    add_datum_feature(
        adapter,
        front,
        edge_xy=(FRONT_CENTER[0], _front_y(BORE_HEIGHT) - _bore_r),
        symbol_xy=(
            FRONT_CENTER[0],
            _front_y(BORE_HEIGHT) - _bore_r - 0.015,
        ),
        datum="C",
        label="journal-bore clocking axis",
        position_tolerance_m=0.016,
    )
    crank_entity, crank_xy = _crank_bore_edge(adapter, front)
    add_attached_note(
        adapter,
        front,
        text="CRANK BORE <MOD-DIAM>10.025 +/-0.025 THRU",
        edge_xy=crank_xy,
        note_xy=(0.145, _front_y(CRANK_BORE_HEIGHT) + 0.025),
        label="crank-bore size",
        entity=crank_entity,
    )
    add_feature_control_frame(
        adapter,
        front,
        edge_xy=crank_xy,
        frame_xy=(0.170, _front_y(CRANK_BORE_HEIGHT) + 0.010),
        characteristic="position",
        tolerance="0.10",
        datums=("A", "B", "C"),
        diameter=True,
        label="crank-bore true position",
        entity=crank_entity,
    )
    _add_table_note(
        adapter,
        "UPPER PLAN (+X RIGHT, +Z DOWN)",
        0.065,
        0.265,
        label="upper-plan view label",
    )
    _add_crank_axis_table(adapter)
    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.075)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Cone Pivot Post Manufacturing Drawing",
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
