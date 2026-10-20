r"""Create the two-sheet reference package for shared McMaster 9666K56 wire.

Both fronts carry the associative Depth as a straight rest-run reference.
LeverWire pairs its 1:5 front with a horizontal 1:1 isometric; PenWire uses
2:1 throughout. Neither run is a developed cut length: formed ends and wraps
remain undefined, and both member notes retain the DO NOT RELEASE limitation.
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any, NamedTuple

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    place_view,
    view_name,
)

import _telemetry
from _check import check
from _com import _early_bound
from _config import parts
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    stamp_drawing_summary,
    set_high_quality_shaded_with_edges,
)
from _drawing_dimension_import import curate_view_dimensions
from _drawing_dimensions import set_reference_dimension
from _drawing_leaders import dimension_segments
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_points_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_sheets import create_blank_drawing_sheets
from _drawing_view_display import set_hidden_lines_removed
from _layout_audit import arrowhead_segments, display_box
from _paths import CAD_ROOT
from _session import run_build
import sh_vn_music_wire_lever_geom as lever_geom
import sh_vn_music_wire_lever_spec as lever_spec
import sh_vn_music_wire_pen_geom as pen_geom
import sh_vn_music_wire_pen_spec as pen_spec

SPEC = DRAWINGS_BY_NAME["sh_vn_music_wire"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(**SPEC.outputs)
SLDDRW = OUTPUTS.slddrw
PDF = OUTPUTS.pdf
PNG = OUTPUTS.png

SHEET_NAMES = ("LeverWire", "PenWire")
SHEET_SCALES = {"LeverWire": (1, 1), "PenWire": (2, 1)}
_BORDER = (0.0127, 0.0127, 0.4191, 0.2667)
_TITLE_BLOCK = (0.2159, 0.0127, 0.4191, 0.0651)
_POSITION_TOLERANCE = 1e-6
_INK_TOLERANCE = 1e-5
_WIRE_LENGTHS = {"LeverWire": lever_geom.WIRE_LEN, "PenWire": pen_geom.WIRE_LEN}
_DRAWING_DIMENSIONS = {
    "LeverWire": lever_spec.DRAWING_DIMENSIONS,
    "PenWire": pen_spec.DRAWING_DIMENSIONS,
}


class _ViewLayout(NamedTuple):
    orientation: str
    scale: tuple[int, int]
    angle: float
    center: tuple[float, float]
    field: tuple[float, float, float, float]


_VIEW_LAYOUTS = {
    "LeverWire": (
        _ViewLayout("*Front", (1, 5), 0.0, (0.135, 0.150),
                    (0.025, 0.105, 0.205, 0.198)),
        _ViewLayout("*Isometric", (1, 1), math.pi / 2.0, (0.216, 0.222),
                    (0.018, 0.205, 0.414, 0.244)),
    ),
    "PenWire": (
        _ViewLayout("*Front", (2, 1), 0.0, (0.110, 0.155),
                    (0.025, 0.091, 0.205, 0.236)),
        _ViewLayout("*Isometric", (2, 1), 0.0, (0.300, 0.170),
                    (0.225, 0.110, 0.410, 0.244)),
    ),
}
FRONT_KEEPS = {
    "LeverWire": {"Depth": (0.100, 0.150)},
    "PenWire": {"Depth": (0.078, 0.155)},
}
_MEMBER_LABELS = {"LeverWire": "LEVER WIRE", "PenWire": "PEN WIRE"}
_NOTE_POSITIONS = {
    "LeverWire": (
        ("Manufacturing Notes", 0.020, 0.075),
        ("Front View Note", 0.100, 0.100),
        ("Isometric View Note", 0.175, 0.195),
    ),
    "PenWire": (
        ("Manufacturing Notes", 0.016, 0.080),
        ("Elevation View Note", 0.040, 0.087),
        ("Isometric View Note", 0.270, 0.100),
    ),
}


def _overlaps(box: tuple[float, ...], other: tuple[float, ...]) -> bool:
    return (
        box[0] < other[2] and other[0] < box[2]
        and box[1] < other[3] and other[1] < box[3]
    )


def _contained(box: tuple[float, ...], field: tuple[float, ...]) -> bool:
    return (
        field[0] <= box[0] <= box[2] <= field[2]
        and field[1] <= box[1] <= box[3] <= field[3]
    )


def _require_field(
    box: tuple[float, ...], field: tuple[float, ...], label: str
) -> None:
    if (
        not all(map(math.isfinite, box))
        or not _contained(box, field)
        or not _contained(box, _BORDER)
        or _overlaps(box, _TITLE_BLOCK)
    ):
        raise RuntimeError(f"{label}: leaves its printable field: {box!r}")


def _outline(view: Any, label: str) -> tuple[float, ...]:
    box = tuple(float(value) for value in (view.GetOutline() or ()))
    if (
        len(box) != 4 or not all(map(math.isfinite, box))
        or box[2] <= box[0] or box[3] <= box[1]
    ):
        raise RuntimeError(f"{label}: invalid view outline {box!r}")
    return box


def _assert_view_state(view: Any, configuration: str, layout: _ViewLayout) -> None:
    label = f"{configuration} {layout.orientation}"
    if str(view.ReferencedConfiguration) != configuration:
        raise RuntimeError(f"{label}: view configuration changed")
    source = str(view.GetReferencedModelName()).replace("\\", "/").casefold()
    if source != str(SOURCE).replace("\\", "/").casefold():
        raise RuntimeError(f"{label}: view source changed")
    if str(view.GetOrientationName()) != layout.orientation:
        raise RuntimeError(f"{label}: native orientation changed")
    ratio = tuple(float(value) for value in (view.ScaleRatio or ()))
    angle = float(view.Angle)
    if (
        len(ratio) != 2 or not all(map(math.isfinite, ratio))
        or any(abs(actual - wanted) > 1e-9
               for actual, wanted in zip(ratio, layout.scale))
        or int(view.UseSheetScale) != 0
        or not math.isfinite(angle) or abs(angle - layout.angle) > 1e-9
    ):
        raise RuntimeError(f"{label}: native scale/angle changed: {ratio!r}, {angle!r}")
    if layout.orientation == "*Isometric":
        mode = view.GetDisplayMode2()
        parent = view.GetUseParentDisplayMode()
        edges = view.GetDisplayEdgesInShadedMode()
        threads = view.GetCThreadQuality()
        if (
            any(value is None for value in (mode, parent, edges, threads))
            or int(mode) not in (3, 7)
            or bool(parent) or not bool(edges) or not bool(threads)
        ):
            raise RuntimeError(f"{label}: isometric is not Shaded With Edges")


def _assert_view_field(view: Any, configuration: str, layout: _ViewLayout) -> None:
    label = f"{configuration} {layout.orientation}"
    box = _outline(view, label)
    center = ((box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0)
    if math.dist(center, layout.center) > _POSITION_TOLERANCE:
        raise RuntimeError(f"{label}: native outline is not centered: {box!r}")
    _require_field(box, layout.field, label)


def _center_view(adapter: Any, view: Any, configuration: str, layout: _ViewLayout) -> None:
    """Move the measured geometry, not the end-origin insertion point."""
    label = f"{configuration} {layout.orientation}"
    box = _outline(view, label)
    position = tuple(float(value) for value in (view.Position or ()))
    if len(position) != 2 or not all(map(math.isfinite, position)):
        raise RuntimeError(f"{label}: invalid native view position {position!r}")
    target = (
        position[0] + layout.center[0] - (box[0] + box[2]) / 2.0,
        position[1] + layout.center[1] - (box[1] + box[3]) / 2.0,
    )
    if not view.SetViewPosition(double_array(target), False):
        raise RuntimeError(f"{label}: cannot recenter native view")
    rebuild_drawing(adapter, label=f"{label} recentered")
    _assert_view_state(view, configuration, layout)
    _assert_view_field(view, configuration, layout)


def _assert_depth(adapter: Any, view: Any, annotation: Any, configuration: str) -> None:
    """Read this member's model Depth and its actual on-sheet reference ink."""
    label = f"{configuration} straight rest-run REF"
    layout = _VIEW_LAYOUTS[configuration][0]
    annotation = _early_bound(annotation, "IAnnotation")
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    dangling = annotation.IsDangling()
    if (
        str(dimension.FullName).split("@")[:2] != ["Depth", "Wire"]
        or dangling is None or bool(dangling) or int(annotation.Visible) != 1
        or not bool(display.ShowDimensionValue)
    ):
        raise RuntimeError(f"{label}: missing visible associative Depth@Wire")
    # Never read unqualified SystemValue: the source has two different lengths.
    values = dimension.GetSystemValue3(3, configuration)  # swSpecifyConfiguration
    expected_mm = _WIRE_LENGTHS[configuration]
    if (
        not isinstance(values, (tuple, list)) or len(values) != 1
        or not math.isfinite(float(values[0]))
        or abs(float(values[0]) * 1000.0 - expected_mm) > 1e-4
    ):
        raise RuntimeError(f"{label}: wrong configuration length {values!r}")
    if (str(display.GetText(1)), str(display.GetText(2))) != ("(", ")"):
        raise RuntimeError(f"{label}: native reference parentheses changed")
    position = tuple(float(value) for value in (annotation.GetPosition() or ()))
    text_xy = FRONT_KEEPS[configuration]["Depth"]
    if (
        len(position) != 3 or not all(map(math.isfinite, position))
        or math.dist(position[:2], text_xy) > _INK_TOLERANCE
    ):
        raise RuntimeError(f"{label}: dimension text drifted: {position!r}")
    raw_data = display.GetDisplayData()
    if raw_data is None:
        raise RuntimeError(f"{label}: no native display data")
    data = _early_bound(raw_data, "IDisplayData")
    texts = []
    for index in range(int(data.GetTextCount())):
        text = str(data.GetTextAtIndex(index))
        at = tuple(float(value) for value in data.GetTextPositionAtIndex(index))
        height = float(data.GetTextHeightAtIndex(index))
        width = float(data.GetTextInBoxWidthAtIndex(index))
        angle = float(data.GetTextAngleAtIndex(index))
        reference = int(data.GetTextRefPositionAtIndex(index))
        if (
            not text.strip() or len(at) != 3 or not all(map(math.isfinite, at))
            or not math.isfinite(height) or height < 0.0025
            or not math.isfinite(width) or width <= 0.0
            or not math.isfinite(angle) or abs(angle) > 1e-9
            or reference not in (0, 1, 2, 3, 4, 5)
        ):
            raise RuntimeError(f"{label}: unreadable native dimension text")
        # GetTextPositionAtIndex is the native reference point, not always
        # lower-left. Normalize the documented swTextPosition_e locally:
        # display_box currently takes an already-lower-left text position.
        dx, dy = {
            0: (0.0, -height), 1: (0.0, 0.0), 2: (-width / 2, -height / 2),
            3: (-width, -height), 4: (-width, 0.0), 5: (-width / 2, -height),
        }[reference]
        c, s = math.cos(angle), math.sin(angle)
        box = display_box({"texts": [{
            "t": text, "w": width, "h": height, "ang": angle, "ref": 1,
            "pos": (at[0] + c * dx - s * dy, at[1] + s * dx + c * dy, at[2]),
        }]})
        if box is None:
            raise RuntimeError(f"{label}: native dimension text has no bounds")
        _require_field((box.xmin, box.ymin, box.xmax, box.ymax), layout.field, label)
        texts.append(text)
    if (
        int(display.GetPrimaryPrecision2()) != 2
        or f"{expected_mm:.2f}" not in "".join(texts)
    ):
        raise RuntimeError(f"{label}: native displayed length is wrong: {texts!r}")
    segments = dimension_segments(annotation)
    if not segments:
        raise RuntimeError(f"{label}: no native dimension strokes")
    for segment in segments:
        for x, y in segment:
            _require_field((x, y, x, y), layout.field, label)
    if int(data.GetArrowHeadCount()) != 2:
        raise RuntimeError(f"{label}: expected two native Depth arrowheads")
    tips = []
    for index in range(2):
        arrow = tuple(float(value) for value in data.GetArrowHeadAtIndex2(index))
        if (
            len(arrow) != 12 or not all(map(math.isfinite, arrow))
            or arrow[6] <= 0.0 or arrow[7] <= 0.0
            or abs(math.hypot(arrow[3], arrow[4]) - 1.0) > 1e-6
        ):
            raise RuntimeError(f"{label}: incomplete native arrowhead {arrow!r}")
        tip = (arrow[0], arrow[1])
        tips.append(tip)
        for segment in arrowhead_segments(arrow):
            for x, y in ((segment.x0, segment.y0), (segment.x1, segment.y1)):
                _require_field((x, y, x, y), layout.field, label)
    ends = model_points_in_view(
        adapter, view, ((0.0, 0.0, 0.0), (0.0, expected_mm / 1000.0, 0.0)),
        label=label,
    )
    if (
        len(ends) != 2 or not all(math.isfinite(v) for point in ends for v in point)
        or abs(math.dist(*ends) - expected_mm / 1000 * layout.scale[0] / layout.scale[1])
        > _INK_TOLERANCE
        or any(math.dist(tip, (text_xy[0], end[1])) > _INK_TOLERANCE
               for tip, end in zip(sorted(tips, key=lambda p: p[1]),
                                   sorted(ends, key=lambda p: p[1])))
    ):
        raise RuntimeError(f"{label}: native arrowheads no longer span the wire ends")


def _note_box(note: Any, label: str) -> tuple[float, ...]:
    extent = tuple(float(value) for value in (_early_bound(note, "INote").GetExtent() or ()))
    if (
        len(extent) != 6 or not all(map(math.isfinite, extent))
        or extent[3] <= extent[0] or extent[4] <= extent[1]
    ):
        raise RuntimeError(f"{label}: no resolved native note extent: {extent!r}")
    box = (extent[0], extent[1], extent[3], extent[4])
    _require_field(box, _BORDER, label)
    return box


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")
    row = parts(PART_STEM)
    quantities = row["configuration_quantities"]
    if set(quantities) != set(SHEET_NAMES):
        raise RuntimeError("music-wire sheets do not match the registry members")
    total = sum(int(quantity) for quantity in quantities.values())
    if total != int(row["quantity"]):
        raise RuntimeError("music-wire installed quantities do not match the family")
    note_keys = tuple(
        f"{configuration} {property_name}"
        for configuration in SHEET_NAMES
        for property_name, _, _ in _NOTE_POSITIONS[configuration]
    )
    check("open shared music-wire source", await adapter.open_model(str(SOURCE)))
    properties = read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            *note_keys,
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            *note_keys,
        ),
    )
    drawing_model, _ = new_project_drawing(
        adapter,
        property_view=PART_STEM,
        scale=SHEET_SCALES[SHEET_NAMES[0]],
        layout=SPEC.layout,
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Shared Music Wire Reference Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "music wire; lever wire; pen wire; straight rest runs",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    create_blank_drawing_sheets(adapter, SHEET_NAMES, label="shared music-wire members")
    draw = _early_bound(drawing_model, "IDrawingDoc")
    configured_views = []
    references = []
    linked_notes = []
    for configuration in SHEET_NAMES:
        if not draw.ActivateSheet(configuration):
            raise RuntimeError(f"cannot activate music-wire sheet {configuration!r}")
        member_views = []
        for layout in _VIEW_LAYOUTS[configuration]:
            view = _early_bound(
                place_view(
                    adapter, str(SOURCE), layout.orientation, *layout.center,
                    scale=layout.scale,
                ),
                "IView",
            )
            view.ReferencedConfiguration = configuration
            view.UseSheetScale = 0
            view.ScaleRatio = double_array(layout.scale)
            view.Angle = layout.angle
            # Prime every view through HLR before shading: an already-shaded
            # no-op can otherwise retain low-quality cosmetic threads.
            set_hidden_lines_removed(adapter, view)
            if layout.orientation == "*Isometric":
                set_high_quality_shaded_with_edges(
                    adapter, view, label=f"{configuration} isometric"
                )
            rebuild_drawing(adapter, label=f"{configuration} configured wire view")
            _assert_view_state(view, configuration, layout)
            # Configuration/scale/rotation can displace an end-origin part.
            # Settle and read the real box BEFORE importing its model dimension.
            _center_view(adapter, view, configuration, layout)
            configured_views.append((configuration, view, layout))
            member_views.append(view)
        front = member_views[0]
        property_view = view_name(adapter, front)
        if not property_view:
            raise RuntimeError(f"{configuration}: missing property-source view")
        draw.GetCurrentSheet().CustomPropertyView = property_view
        annotations = curate_view_dimensions(
            adapter,
            front,
            keep=FRONT_KEEPS[configuration],
            dimensions_by_feature=_DRAWING_DIMENSIONS[configuration],
            view_label=f"{configuration} front",
        )
        if len(annotations) != 1:
            raise RuntimeError(f"{configuration}: expected one native rest-run Depth")
        set_reference_dimension(
            adapter, annotations[0], label=f"{configuration} straight rest-run REF"
        )
        display = _early_bound(
            _early_bound(annotations[0], "IAnnotation").GetSpecificAnnotation(),
            "IDisplayDimension",
        )
        status = display.SetPrecision3(2, -1, -1, -1)
        if status != 0 or int(display.GetPrimaryPrecision2()) != 2:
            raise RuntimeError(
                f"{configuration}: straight rest-run REF precision did not persist"
            )
        references.append((configuration, front, annotations[0]))
        for property_name, x, y in _NOTE_POSITIONS[configuration]:
            key = f"{configuration} {property_name}"
            note = add_property_linked_note(adapter, key, x, y)
            linked_notes.append((configuration, note, str(properties[key])))
        caption = (
            f"{_MEMBER_LABELS[configuration]}  "
            f"QTY {int(quantities[configuration])} INSTALLED RUN; "
            f"SHARED FAMILY: {total} RUNS, NOT COILS"
        )
        note = add_note(adapter, caption, 0.020, 0.255)
        if note is None:
            raise RuntimeError(f"{configuration}: cannot add installed-quantity note")
        linked_notes.append((configuration, note, caption))

    def assert_configured_sheets() -> None:
        for configuration, view, layout in configured_views:
            if not draw.ActivateSheet(configuration):
                raise RuntimeError(f"cannot read back sheet {configuration!r}")
            _assert_view_state(view, configuration, layout)
            _assert_view_field(view, configuration, layout)
        for configuration, view, annotation in references:
            if not draw.ActivateSheet(configuration):
                raise RuntimeError(f"cannot read back dimension on {configuration!r}")
            _assert_depth(adapter, view, annotation, configuration)
        note_boxes: dict[str, list[tuple[float, ...]]] = {
            configuration: [] for configuration in SHEET_NAMES
        }
        for configuration, note, expected in linked_notes:
            if not draw.ActivateSheet(configuration):
                raise RuntimeError(f"cannot read back notes on {configuration!r}")
            text = str(adapter._get_attr_or_call(note, "GetText") or "")
            if text.replace("\r\n", "\n") != expected.replace("\r\n", "\n"):
                raise RuntimeError(
                    f"{configuration}: native linked note resolved to {text!r}, "
                    f"expected {expected!r}"
                )
            adapter.currentModel.GraphicsRedraw2()
            box = _note_box(note, f"{configuration} linked note")
            for member, view, _ in configured_views:
                if member == configuration and _overlaps(box, _outline(view, member)):
                    raise RuntimeError(f"{configuration}: note overlaps native view")
            if any(_overlaps(box, other) for other in note_boxes[configuration]):
                raise RuntimeError(f"{configuration}: native note blocks overlap")
            note_boxes[configuration].append(box)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Shared Music Wire Reference Drawing",
        scale=SHEET_SCALES[SHEET_NAMES[0]],
        layout=SPEC.layout,
        expected_sheet_names=SHEET_NAMES,
        sheet_scales=SHEET_SCALES,
        settled_checks=(assert_configured_sheets,),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
