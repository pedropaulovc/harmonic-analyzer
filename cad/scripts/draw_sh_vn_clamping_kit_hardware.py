"""Draw the three installed forms from one Precision Matthews clamping kit.

Each explicitly configured member retains its four-view reference content.
The twelve installed members are not twelve procurement units.
"""

from __future__ import annotations

import argparse
import sys
import math
from collections.abc import Callable
from typing import Any

import _telemetry
from _session import run_build
from _drawing_registry import DRAWINGS_BY_NAME
from _purchased_variant_drawing import build_purchased_variant_drawing
from _com import _early_bound, _read_member
from _drawing_attachment import _is_same_attachment
from _drawing_dimensions import set_reference_dimension
from _drawing_edge_dimensions import add_edge_dimension, assert_dimension_measures
from _drawing_edges import visible_view_entities
from _drawing_projection import model_points_in_view
from _purchased_fastener_drawing import _box, _inside
import sh_vn_clamping_kit_hold_down_stud_spec as stud
from _layout_audit import display_box, estimated_text_runs
from _drawing_layout_audit import annotation_display


SPEC = DRAWINGS_BY_NAME["sh_vn_clamping_kit_hardware"]
PART_STEM = SPEC.artifact_stem
# The footer's ITEM row: the catalogue designation in plain text.
ITEM = "52-PIECE CLAMPING KIT, 14 MM T-SLOT, 1/2-13 HARDWARE"
VARIANTS = (
    ("HoldDownStud", "HOLD-DOWN STUD"),
    ("TNut", "T-NUT"),
    ("FlangeNut", "FLANGE NUT"),
)
PURCHASE_UNIT = "52-PIECE KIT"


def _measured_display_box(rendered: dict[str, Any]) -> Any:
    """Normalize swTextPosition_e anchors before the lower-left ink boxer."""
    texts = []
    for item in rendered.get("texts", ()):
        width, height = float(item.get("w", 0)), float(item.get("h", 0))
        reference = int(item.get("ref", -1))
        position = tuple(float(value) for value in item.get("pos", ()))
        angle = float(item.get("ang", 0))
        if (
            min(width, height) <= 0 or reference not in range(6)
            or len(position) < 2
            or not all(math.isfinite(value) for value in (width, height, angle, *position))
        ):
            raise RuntimeError("kit: native rendered text geometry is unreadable")
        # swUPPER_LEFT, LOWER_LEFT, CENTER, UPPER_RIGHT, LOWER_RIGHT, UPPER_CENTER.
        dx, dy = (
            (0, -height), (0, 0), (-width / 2, -height / 2),
            (-width, -height), (-width, 0), (-width / 2, -height),
        )[reference]
        cosine, sine = math.cos(angle), math.sin(angle)
        texts.append({
            **item, "ref": 1,
            "pos": (position[0] + dx * cosine - dy * sine,
                    position[1] + dx * sine + dy * cosine, 0.0),
        })
    return display_box({**rendered, "texts": texts})


def _stud_length_reference(adapter: Any, cells: tuple, views: list[Any]) -> Callable[[], None]:
    """Measure the revolved model's two end rims, not its shorter straight land."""
    front = views[0]
    rims = []
    for raw in visible_view_entities(front, 1, label="kit stud end rims"):
        edge = _early_bound(raw, "IEdge")
        curve = _early_bound(edge.GetCurve(), "ICurve")
        if curve is None or curve.IsCircle() is not True:
            continue
        params = tuple(float(value) for value in curve.CircleParams)
        if (
            len(params) == 7
            and math.isclose(params[0], 0.0, abs_tol=1e-9)
            and math.isclose(params[2], 0.0, abs_tol=1e-9)
            and math.isclose(abs(params[4]), 1.0, abs_tol=1e-9)
            and math.isclose(params[6] * 1000, stud.RADIUS - stud.END_CHAMFER, abs_tol=1e-5)
        ):
            rims.append((params[1], edge))
    rims.sort(key=lambda item: item[0])
    if len(rims) != 2:
        raise RuntimeError("kit stud: expected exactly two native end rims")
    length_mm = (rims[1][0] - rims[0][0]) * 1000
    if not math.isclose(length_mm, stud.LENGTH, abs_tol=1e-5):
        raise RuntimeError("kit stud: native overall length differs from the installed member")
    entities = (rims[0][1], rims[1][1])
    _early_bound(front, "IView").UpdateViewDisplayGeometry()  # VT_VOID
    points = model_points_in_view(
        adapter, front,
        [(0.0, station, 0.0) for station, _edge in rims],
        label="kit stud overall end stations",
    )
    cell = cells[0][2]
    display = _early_bound(add_edge_dimension(
        adapter, front, p0=points[0], p1=points[1],
        text_xy=(cell[0] + 0.022, (points[0][1] + points[1][1]) / 2),
        label="kit stud overall length", orientation="vertical", entities=entities,
    ), "IDisplayDimension")
    native = _early_bound(display.GetDimension2(0), "IDimension")
    native.DrivenState = 1  # swDimensionDriven: drawing-only reference measurement.
    annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
    set_reference_dimension(adapter, annotation, label="kit stud overall length")

    def settled() -> None:
        present = [
            raw for raw in (front.GetAnnotations() or ())
            if int(adapter.swApp.IsSame(raw, annotation)) == 1
        ]
        if len(present) != 1:
            raise RuntimeError("kit stud: overall reference annotation was lost")
        assert_dimension_measures(
            adapter, display, expected_mm=length_mm,
            label="kit stud overall length", entities=entities,
        )
        if (
            int(native.DrivenState) != 1
            or int(annotation.Visible) != 1
            or (display.GetText(1), display.GetText(2)) != ("(", ")")
        ):
            raise RuntimeError("kit stud: overall reference display was lost")
        rendered, errors = annotation_display(adapter, annotation)
        ink = _measured_display_box(rendered)
        if (
            errors or not rendered.get("texts") or estimated_text_runs(rendered)
            or ink is None
            or not _inside((ink.xmin, ink.ymin, ink.xmax, ink.ymax), cell)
        ):
            raise RuntimeError("kit stud: reference text/strokes leave the FRONT cell or are unreadable")

    settled()
    return settled


def _note_text_box(annotation: Any) -> tuple[float, float, float, float]:
    """Native rendered text only: INote.GetExtent also includes its fixed leader."""
    data = _early_bound(annotation.GetDisplayData(), "IDisplayData")
    texts = []
    for index in range(int(data.GetTextCount())):
        text = data.GetTextAtIndex(index)
        if not text.strip():
            continue
        width = float(data.GetTextInBoxWidthAtIndex(index))
        height = float(data.GetTextHeightAtIndex(index))
        if not math.isfinite(width) or not math.isfinite(height) or min(width, height) <= 0:
            raise RuntimeError("kit T-nut: native thread text size is unreadable")
        texts.append({
            "t": text, "w": width, "h": height,
            "pos": tuple(data.GetTextPositionAtIndex(index)),
            "ref": int(data.GetTextRefPositionAtIndex(index)),
            "ang": float(data.GetTextAngleAtIndex(index)),
        })
    box = _measured_display_box({"texts": texts})
    if box is None:
        raise RuntimeError("kit T-nut: native thread text is missing")
    return (box.xmin, box.ymin, box.xmax, box.ymax)


def _tnut_thread_note(adapter: Any, cells: tuple, views: list[Any]) -> Callable[[], None]:
    """Keep the existing associated automatic note above its own fitted views."""
    iso = views[3]

    def notes() -> list[Any]:
        return [
            note for raw in (iso.GetNotes() or ())
            if "1/2-13 Tapped Hole" in (note := _early_bound(raw, "INote")).GetText()
        ]

    found = notes()
    if len(found) != 1:
        raise RuntimeError("kit T-nut: expected one automatic isometric thread note")
    note = found[0]
    text, linked = note.GetText(), note.PropertyLinkedText
    annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
    attachments = tuple(annotation.GetAttachedEntities3() or ())
    if not attachments or any(entity is None for entity in attachments):
        raise RuntimeError("kit T-nut: thread note has no native attachment")

    def region() -> tuple[float, float, float, float]:
        top = max(_box(view.GetOutline(), label="T-nut")[3] for view in views)
        return (cells[0][2][0] + 0.002, top + 0.002,
                cells[2][2][2] - 0.002, 0.253)

    bounds = _note_text_box(annotation)
    clear = region()
    position = tuple(float(value) for value in _read_member(annotation, "GetPosition"))
    target = (
        position[0] + (clear[0] + clear[2] - bounds[0] - bounds[2]) / 2,
        position[1] + (clear[1] + clear[3] - bounds[1] - bounds[3]) / 2,
        0.0,
    )
    if annotation.SetPosition2(*target) is not True:
        raise RuntimeError("kit T-nut: native thread-note relocation refused")

    def settled() -> None:
        current = notes()
        attached = tuple(annotation.GetAttachedEntities3() or ())
        if (
            len(current) != 1 or current[0].GetText() != text
            or int(adapter.swApp.IsSame(current[0].GetAnnotation(), annotation)) != 1
            or note.PropertyLinkedText != linked
            or annotation.IsDangling() is not False
            or int(annotation.Visible) != 1
            or len(attached) != len(attachments)
            or any(not _is_same_attachment(adapter, actual, expected, "EDGE")
                   for actual, expected in zip(attached, attachments, strict=True))
            or not _inside(_note_text_box(annotation), region())
            or not _inside(
                _box(note.GetExtent(), label=text, kind="note"),
                (cells[0][2][0], cells[3][2][1], cells[2][2][2], 0.255),
            )
        ):
            raise RuntimeError("kit T-nut: thread note lost identity, attachment or clearance")

    settled()
    return settled


def annotate_member(
    adapter: Any, configuration: str, cells: tuple, views: list[Any],
) -> tuple[Callable[[], None], ...]:
    if configuration == "HoldDownStud":
        return (_stud_length_reference(adapter, cells, views),)
    if configuration == "TNut":
        return (_tnut_thread_note(adapter, cells, views),)
    return ()


async def build(adapter: Any) -> dict[str, str]:
    return await build_purchased_variant_drawing(
        adapter,
        SPEC,
        variants=VARIANTS,
        item=ITEM,
        purchase_unit=PURCHASE_UNIT,
        annotate_member=annotate_member,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
