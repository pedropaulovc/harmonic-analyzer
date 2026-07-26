r"""Create the curated machinist drawing for the v2 cone pivot post."""

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
    model_point_in_view,
    new_project_drawing,
    read_required_properties,
    set_basic_dimension,
    set_dimension_callouts,
    set_dimension_precision,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    stamp_drawing_summary,
    visible_view_entities,
)
from _drawing_registry import DRAWINGS_BY_NAME
from cone_pivot_post_spec import (
    ATTACHMENT_CBORE_DEPTH,
    ATTACHMENT_CBORE_DIA,
    ATTACHMENT_SPACING,
    ATTACHMENT_THRU_DIA,
    BLOCK_DIA,
    BLOCK_HEIGHT,
    BORE_DIA,
    BORE_HEIGHT,
    CONE_BOSS_DIA,
    CRANK_BORE_DIA,
    CRANK_BORE_HEIGHT,
    HEAD_HEIGHT,
    JOURNAL_AXIS_ORIENTATION_NOTE,
    JOURNAL_AXIS_POINTS,
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
_S = SHEET_SCALE[0] / 1000.0

# Third-angle: the front elevation carries the height and crank journal; the
# plan carries the two body diameters and mounting-hole pattern.
FRONT_CENTER = (0.105, 0.145)
TOP_CENTER = (0.105, 0.235)
ISO_CENTER = (0.340, 0.145)


def _front_y(model_y: float) -> float:
    return FRONT_CENTER[1] + (model_y - BLOCK_HEIGHT / 2.0) * _S


FRONT_KEEP = {
    "MainBodyHt": (FRONT_CENTER[0] - 0.055, FRONT_CENTER[1]),
    "HeadHt": (FRONT_CENTER[0] + 0.055, _front_y(BLOCK_HEIGHT - HEAD_HEIGHT / 2.0)),
    "CrankAxisY": (FRONT_CENTER[0] - 0.035, _front_y(CRANK_BORE_HEIGHT / 2.0)),
    "CrankBossDia": (
        FRONT_CENTER[0] + 0.050,
        _front_y(CRANK_BORE_HEIGHT) + 0.018,
    ),
    "CrankBoreDia": (
        FRONT_CENTER[0] + 0.050,
        _front_y(CRANK_BORE_HEIGHT) - 0.012,
    ),
}
TOP_KEEP = {
    "MainBodyDia": (TOP_CENTER[0] - 0.040, TOP_CENTER[1]),
    "HeadDia": (TOP_CENTER[0] + 0.045, TOP_CENTER[1]),
}
DIMENSION_CALLOUTS = {
    "MainBodyDia": "+/-0.05",
    "HeadDia": "+/-0.05",
    "CrankBossDia": "+/-0.05",
    "CrankBoreDia": "+/-0.025 THRU",
}
DIMENSION_PRECISION = {
    "MainBodyDia": 3,
    "HeadDia": 4,
    "MainBodyHt": 3,
    "HeadHt": 3,
    "CrankAxisY": 3,
    "CrankBossDia": 3,
    "CrankBoreDia": 3,
}


def _circular_edge(
    adapter: Any,
    view: Any,
    *,
    radius_mm: float,
    center_y_mm: float,
) -> Any:
    """Return a model circular edge matching radius and height."""
    candidates: list[tuple[float, float, Any]] = []
    for edge in visible_view_entities(view, 1, label="pivot-post circular edges"):
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
        raise RuntimeError("view has no circular model edges")
    radius, center_y, edge = min(
        candidates,
        key=lambda item: abs(item[0] - radius_mm) + abs(item[1] - center_y_mm),
    )
    if abs(radius - radius_mm) > 0.01 or abs(center_y - center_y_mm) > 0.01:
        raise RuntimeError(
            f"no circular edge matches radius {radius_mm:.4f} mm at "
            f"height {center_y_mm:.4f} mm"
        )
    return edge


@_telemetry.traced("drawing.bore_rim_scan")
def _bore_rim_edge(adapter: Any, view: Any, *, diameter_mm: float) -> Any:
    """Return a rim adjacent to the unique cylindrical bore of this diameter."""
    expected_radius_m = diameter_mm / 2000.0
    candidates: list[Any] = []
    for edge in visible_view_entities(view, 1, label="pivot-post bore rims"):
        edge = _early_bound(edge, "IEdge")
        for face in edge.GetTwoAdjacentFaces2() or []:
            if face is None:
                continue
            face = _early_bound(face, "IFace2")
            surface = _early_bound(face.GetSurface(), "ISurface")
            if not surface.IsCylinder():
                continue
            if abs(float(surface.CylinderParams[6]) - expected_radius_m) > 1e-6:
                continue
            candidates.append(edge)
            break
    if not candidates:
        raise RuntimeError(
            f"view has no rim adjacent to bore diameter {diameter_mm:.5f} mm"
        )
    return candidates[0]


def _format_table_note(note: Any, *, label: str) -> Any:
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


@_telemetry.traced("drawing.table_note", label_param="label")
def _add_table_note(adapter: Any, text: str, x: float, y: float, *, label: str) -> Any:
    note = add_note(adapter, text, x, y)
    if note is None:
        raise RuntimeError(f"failed to add {label}")
    return _format_table_note(note, label=label)


def _add_basic_value(adapter: Any, value: float, x: float, y: float) -> Any:
    note = _add_table_note(
        adapter, f"{value:.3f}", x, y, label="journal-axis BASIC coordinate"
    )
    note = _early_bound(
        note,
        "INote",
        "SetBalloon",
        "HasBalloon",
        "GetBalloonStyle",
        "GetBalloonSize",
    )
    if not note.SetBalloon(4, 0):
        raise RuntimeError("SolidWorks rejected a BASIC journal-axis coordinate")
    if (
        not note.HasBalloon()
        or int(note.GetBalloonStyle()) != 4
        or int(note.GetBalloonSize()) != 0
    ):
        raise RuntimeError("BASIC journal-axis coordinate box did not persist")
    return note


@_telemetry.traced("drawing.journal_axis_table")
def _add_journal_axis_table(adapter: Any) -> None:
    _add_table_note(
        adapter,
        "JOURNAL AXIS COORDINATES (mm)",
        0.225,
        0.255,
        label="journal-axis table heading",
    )
    _add_table_note(
        adapter,
        JOURNAL_AXIS_ORIENTATION_NOTE,
        0.225,
        0.245,
        label="journal-axis coordinate orientation",
    )
    for column, column_x in zip(
        ("POINT", "X", "Y", "Z"),
        (0.225, 0.253, 0.295, 0.337),
        strict=True,
    ):
        _add_table_note(
            adapter,
            column,
            column_x,
            0.229,
            label=f"journal-axis coordinate column {column}",
        )
    for row_y, (point, x_value, y_value, z_value) in zip(
        (0.219, 0.207), JOURNAL_AXIS_POINTS, strict=True
    ):
        _add_table_note(
            adapter, point, 0.225, row_y, label=f"journal-axis point {point}"
        )
        for column_x, value in zip(
            (0.253, 0.295, 0.337),
            (x_value, y_value, z_value),
            strict=True,
        ):
            _add_basic_value(adapter, value, column_x, row_y)
    _add_table_note(
        adapter,
        "AXIS = LINE THROUGH P AND Q",
        0.285,
        0.194,
        label="journal-axis table definition",
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
            3: "bossed cast-iron post; inclined cone journal; crank journal",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(1, 1))
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(1, 2))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 2))
    set_hidden_lines_removed(adapter, iso)
    for view in (front, top):
        set_hidden_lines_visible(adapter, view)

    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    top_annotations = curate_view_dimensions(
        adapter, top, keep=TOP_KEEP, view_label="top"
    )
    annotations = [*front_annotations, *top_annotations]
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    set_dimension_precision(adapter, annotations, DIMENSION_PRECISION)
    front_by_name = {
        dimension_name(adapter, annotation): annotation
        for annotation in front_annotations
    }
    axis_height_annotation = front_by_name["CrankAxisY"]
    axis_height_display = adapter._attempt(
        lambda: axis_height_annotation.GetSpecificAnnotation()
    )
    if axis_height_display is None:
        raise RuntimeError("CrankAxisY has no display dimension to box")
    set_basic_dimension(
        adapter, axis_height_display, label="crank-axis basic height"
    )
    for view in (front, top):
        if not auto_center_marks(adapter, view, holes=True, size=0.0025):
            raise RuntimeError("failed to add ASME center marks")

    foot_entity = _circular_edge(
        adapter, front, radius_mm=BLOCK_DIA / 2.0, center_y_mm=0.0
    )
    add_datum_feature(
        adapter,
        front,
        symbol_xy=(FRONT_CENTER[0], _front_y(0.0) - 0.012),
        datum="A",
        label="foot seat face",
        entity=foot_entity,
    )
    add_feature_control_frame(
        adapter,
        front,
        frame_xy=(0.150, _front_y(0.0) + 0.012),
        characteristic="flatness",
        tolerance="0.05",
        label="datum-A seat flatness",
        entity=foot_entity,
    )
    body_side_xy = (
        FRONT_CENTER[0] + BLOCK_DIA / 2.0 * _S,
        _front_y(25.0),
    )
    add_datum_feature(
        adapter,
        front,
        edge_xy=body_side_xy,
        symbol_xy=(body_side_xy[0] + 0.018, body_side_xy[1]),
        datum="B",
        label="main-body outside diameter",
        entity_type="SILHOUETTE",
    )
    add_feature_control_frame(
        adapter,
        front,
        edge_xy=body_side_xy,
        frame_xy=(0.190, _front_y(25.0) + 0.012),
        characteristic="cylindricity",
        tolerance="0.05",
        quantity="DATUM B OD",
        label="datum-B outside-diameter form",
        entity_type="SILHOUETTE",
    )

    journal_entity = _bore_rim_edge(adapter, front, diameter_mm=BORE_DIA)
    journal_center = model_point_in_view(
        adapter,
        front,
        (0.0, BORE_HEIGHT / 1000.0, 0.0),
        label="inclined journal axis center",
    )
    add_attached_note(
        adapter,
        front,
        text=(
            f"CONE BOSS <MOD-DIAM>{CONE_BOSS_DIA:.3f}; "
            f"JOURNAL <MOD-DIAM>{BORE_DIA:.4f} THRU"
        ),
        entity=journal_entity,
        note_xy=(0.155, _front_y(BORE_HEIGHT) + 0.020),
        label="inclined-journal size",
    )
    add_datum_feature(
        adapter,
        front,
        # The restricted rim tag normalizes 0.867 mm radially from the
        # projected axis center; bound that annotation behavior only.
        symbol_xy=(journal_center[0], journal_center[1] - 0.018),
        datum="C",
        label="inclined journal axis",
        entity=journal_entity,
        position_tolerance_m=0.0009,
    )
    add_feature_control_frame(
        adapter,
        front,
        frame_xy=(0.185, journal_center[1] - 0.023),
        characteristic="position",
        tolerance="0.05",
        datums=("A", "B"),
        diameter=True,
        label="journal-axis true position",
        entity=journal_entity,
    )

    crank_entity = _bore_rim_edge(adapter, front, diameter_mm=CRANK_BORE_DIA)
    add_feature_control_frame(
        adapter,
        front,
        frame_xy=(0.185, _front_y(CRANK_BORE_HEIGHT) + 0.012),
        characteristic="position",
        tolerance="0.10",
        datums=("A", "B", "C"),
        diameter=True,
        label="crank-bore true position",
        entity=crank_entity,
    )
    _add_table_note(
        adapter,
        "UPPER PLAN SCALE 1:2 (+X RIGHT, +Z DOWN)",
        0.070,
        0.263,
        label="upper-plan view label",
    )
    _add_journal_axis_table(adapter)
    _add_table_note(
        adapter,
        (
            f"2X 1/4 FILLISTER: C'BORE <MOD-DIAM>{ATTACHMENT_CBORE_DIA:.5f} X "
            f"{ATTACHMENT_CBORE_DEPTH:.4f} DEEP; THRU "
            f"<MOD-DIAM>{ATTACHMENT_THRU_DIA:.5f}; C-C {ATTACHMENT_SPACING:.5f}"
        ),
        0.225,
        0.090,
        label="attachment-hole callout",
    )
    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.068)

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
