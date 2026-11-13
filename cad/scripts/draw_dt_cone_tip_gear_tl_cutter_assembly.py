r"""Create the T006 fly cutter's fitter sheets (MHA-DT-37-TL-00).

Issue #2358: the bar (item 1, MHA-DT-37-TL-02), the DT6-FORM1 bit (item 2,
MHA-DT-37-TL-01) and the bought set screw (item 3, MHA-SH-VN-54) as set up.
Sheet 1: the front view (the bit's face toward the viewer, so the face leads
with the spindle in forward) with items 1 and 2 ballooned and the stick-out
and swing radius as references, the assembly's own settings dimensions
(its hidden CutterSettingsReference sketch); the bottom view (the cutting
end, end-on) with item 3 ballooned; the shaded isometric; the BOM; the
fitting steps.  Sheet 2: the exploded front view (rule 22), one view per
item, item 2 drawn out along item 1's cross hole and item 3 down out of its
cutting end, each labelled.  Poses, the settings, the stick-out window and
the step text come from ``dt_cone_tip_gear_tl_cutter_spec``; this recipe
only lays the sheets out and never edits the source assembly.
"""

from __future__ import annotations

import argparse
import math
import sys
from collections.abc import Callable
from typing import Any

import _config
import _telemetry
import dt_cone_tip_gear_tl_cutter_spec as fixture
from _check import check
from _com import _early_bound
from _drawing_balloons import (
    BalloonAnchor,
    add_component_bom_balloons,
    assert_balloon_landings,
    isolate_drawing_view_components,
)
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    set_high_quality_shaded_with_edges,
)
from _drawing_dimension_import import curate_view_dimensions
from _drawing_dimensions import (
    assert_imported_precision,
    set_dimension_callouts,
    set_reference_dimension,
)
from _drawing_hidden_sketches import _show_base_view_sketches
from _drawing_leader_notes import add_leader_note
from _drawing_projection import model_points_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_sheets import create_blank_drawing_sheets
from _drawing_tables import insert_bom_table
from _drawing_types import DRAWING_TEMPLATES, DrawingLayout
from _drawing_view_configuration import (
    ViewRole,
    apply_view_configuration,
    assert_full_detail_view,
)
from _drawing_view_display import set_hidden_lines_removed
from _machinist_review_mode import MachinistReviewMode
from _session import run_build
from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    dimension_name,
    place_view,
    view_name,
)

# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE
SPEC = DRAWINGS_BY_NAME["dt_cone_tip_gear_tl_cutter_assembly"]
ARTIFACT_STEM = SPEC.artifact_stem
SOURCE = SPEC.source
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"],
    pdf=SPEC.outputs["pdf"],
    png=SPEC.outputs["png"],
)
if SPEC.layout is not DrawingLayout.LANDSCAPE:
    raise AssertionError("the fly-cutter sheets must remain landscape")

DRAWING_NUMBER = fixture.DRAWING_NUMBER
# A Ø.375 x 1.75 bar with a .10 stick-out: 3:1 prints the stick-out 7.6 mm.
SHEET_SCALE = (3.0, 1.0)
VIEW_SCALE = (3, 1)
ISO_SCALE = (2, 1)
_S = VIEW_SCALE[0] / VIEW_SCALE[1] / 1000.0
# Sheet 1 carries the assembled views, BOM, settings and steps; sheet 2 the
# exploded view, at the same scale.
SHEET_NAMES = ("ASSEMBLY", "EXPLODED VIEW")
SHEET_LAYOUTS = {name: DrawingLayout.LANDSCAPE for name in SHEET_NAMES}
SHEET_SCALES = {name: SHEET_SCALE for name in SHEET_NAMES}
# The bar's cutting-end centre (the assembly origin) on the front view, the
# bar standing up from it; the bottom view projected below; the isometric in
# the middle column; the BOM and the steps in the right half, above the title
# block (x >= 0.216 m, y <= 0.066 m).
FRONT_ORIGIN = (0.080, 0.090)
BOTTOM_ORIGIN = (FRONT_ORIGIN[0], 0.040)
ISO_CENTER = (0.165, 0.150)
ISO_NOTE_XY = (0.135, 0.080)
BOM_ANCHOR = (0.219, 0.262)
STEPS_XY = (0.219, 0.215)
BALLOON_MARGIN = 0.012

BAR, BIT, SET_SCREW = fixture.BAR, fixture.BIT, fixture.SET_SCREW
BOM_COMPONENTS = fixture.BOM_COMPONENTS
BOM_ITEMS = fixture.BOM_ITEMS
# Literal rows, so this sheet re-keys only on its own three parts.
_ROWS = {
    BAR: _config.parts("dt-cone-tip-gear-tl-cutter-bar"),
    BIT: _config.parts("dt-cone-tip-gear-tl-form-cutter"),
    SET_SCREW: _config.parts("sh-vn-arbor-set-screw"),
}
if tuple(_ROWS) != BOM_COMPONENTS:
    raise AssertionError("the fly-cutter rows are its BOM components, in order")
BOM_DESCRIPTIONS = {stem: str(row["title"]).upper() for stem, row in _ROWS.items()}
PART_NUMBERS = {stem: str(row["number"]) for stem, row in _ROWS.items()}
BOM_COMPONENT_IDENTITIES: dict[str, tuple[str, str | None]] = {
    stem: (stem, None) for stem in BOM_COMPONENTS
}
BALLOON_ANCHORS = {stem: BalloonAnchor() for stem in BOM_COMPONENTS}
# Items 1 and 2 balloon in the front view; item 3, inside item 1's tap, shows
# only end-on in the bottom view.
FRONT_ITEMS = (BAR, BIT)
BOTTOM_ITEMS = (SET_SCREW,)
if set(FRONT_ITEMS) | set(BOTTOM_ITEMS) != set(BOM_COMPONENTS):
    raise AssertionError("every BOM row is ballooned once")

# --- The settings, imported off the assembly's settings sketch ---------------
_STATION = fixture.bar.CROSS_HOLE_STATION
# The bar's axis as an owned centreline, end to end with a short overrun.
AXIS_ENDS_MM = ((0.0, -2.0, 0.0), (0.0, fixture.bar.BAR_LENGTH + 2.0, 0.0))
# Both texts right of P1 (about 0.11-0.14 m), outside their extension lines,
# so no extension line strikes a text and no text sits on the bar: the
# stick-out 18 mm over the bit, the swing radius 18 mm above it (its
# extension line up from P1 passes left of the stick-out's text), both left
# of the isometric.
_SETTINGS_TEXT_X = FRONT_ORIGIN[0] + (fixture.SWING_RADIUS + 7.0) * _S
SETTINGS_TEXT_XY = {
    fixture.STICK_OUT_DIMENSION: (
        _SETTINGS_TEXT_X,
        FRONT_ORIGIN[1] + (_STATION + 6.0) * _S,
    ),
    fixture.SWING_RADIUS_DIMENSION: (
        _SETTINGS_TEXT_X,
        FRONT_ORIGIN[1] + (_STATION + 12.0) * _S,
    ),
}
SETTINGS_EXPECTED_MM = {
    fixture.STICK_OUT_DIMENSION: fixture.STICK_OUT,
    fixture.SWING_RADIUS_DIMENSION: fixture.SWING_RADIUS,
}
if set(SETTINGS_TEXT_XY) != fixture.DRAWING_DIMENSIONS[fixture.SETTINGS_SKETCH]:
    raise AssertionError("the sheet prints exactly the assembly's marked settings")

# --- Sheet 2: the exploded front view (rule 22) --------------------------------
# One front view per item at the front view's scale, each isolated to its item
# (draw_dt_cylinder_gear_tl_cam_turning_assembly's ``_kit_view``), hidden
# lines removed (rule 9): item 2 drawn out along the cross-hole axis until its
# tail clears item 1's surface by EXPLODE_GAP; item 3 drawn down the bar's
# axis until its cup clears item 1's bottom end by EXPLODE_GAP. Item 1's
# sketch carries both axes, through the loose items, as the paths they go in
# by.  Assembly mm.
EXPLODE_GAP = 4.0
AXIS_OVERRUN = 2.0
EXPLODE_OFFSETS_MM: dict[str, tuple[float, float, float]] = {
    BAR: (0.0, 0.0, 0.0),
    BIT: (fixture.bit.BIT_LENGTH - fixture.STICK_OUT + EXPLODE_GAP, 0.0, 0.0),
    SET_SCREW: (0.0, -(fixture.SET_SCREW_POSITION[1] + EXPLODE_GAP), 0.0),
}
_SCREW_SOCKET_Y = -EXPLODE_GAP - fixture.set_screw.LENGTH
_BIT_TIP_X = fixture.BIT_POSITION[0] + EXPLODE_OFFSETS_MM[BIT][0]
EXPLODED_AXES_MM: dict[str, tuple[tuple[float, float, float], ...]] = {
    "bar axis": (
        (0.0, _SCREW_SOCKET_Y - AXIS_OVERRUN, 0.0),
        (0.0, fixture.bar.BAR_LENGTH + AXIS_OVERRUN, 0.0),
    ),
    "cross-hole axis": (
        (-fixture.bar.BAR_RADIUS - AXIS_OVERRUN, _STATION, 0.0),
        (_BIT_TIP_X + AXIS_OVERRUN, _STATION, 0.0),
    ),
}
# What each leader names, with the face or end the fitter must see the right
# way round; the caption points back to the steps.
EXPLODED_LABELS: dict[str, str] = {
    BAR: f"ITEM {BOM_ITEMS[BAR]}",
    BIT: f"ITEM {BOM_ITEMS[BIT]}, FACE TOWARD THE VIEWER",
    SET_SCREW: f"ITEM {BOM_ITEMS[SET_SCREW]}, CUP END UP",
}
EXPLODED_CAPTION = "EXPLODED FRONT VIEW - FITTING STEPS ON SHEET 1"
# Each leader's tip, seated assembly mm, on a face the view shows: item 1's
# round above the cross hole; item 2's face between the form and the flat's
# shoulder; item 3's thread left of its axis, mid-length.
_FORM_BACK = 0.8 * fixture.bit.FLAT_LENGTH
LABEL_TIPS_MM: dict[str, tuple[float, float, float]] = {
    BAR: (-fixture.bar.BAR_RADIUS / 2.0, 2.0 * fixture.bar.BAR_LENGTH / 3.0, 0.0),
    BIT: (
        fixture.BIT_POSITION[0] - _FORM_BACK,
        _STATION + fixture.bit.BIT_RADIUS / 2.0,
        0.0,
    ),
    SET_SCREW: (
        -fixture.set_screw.MAJOR_DIA / 4.0,
        fixture.SET_SCREW_POSITION[1] - fixture.set_screw.LENGTH / 2.0,
        0.0,
    ),
}
# Each label's upper-left corner from its tip, sheet m, every label wholly to
# one side of its tip so its leader leaves the text's end, clear of the
# letters: items 1 and 3 left of the bar's axis, item 2 up and right of its
# face.
LABEL_OFFSETS: dict[str, tuple[float, float]] = {
    BAR: (-0.040, 0.012),
    BIT: (0.010, 0.020),
    SET_SCREW: (-0.065, 0.0023),
}
CAPTION_XY = (0.030, 0.255)
CHAR_WIDTH = 0.00255  # default-format note text, per character
LINE_PITCH = 0.0046
_TEMPLATE = DRAWING_TEMPLATES[DrawingLayout.LANDSCAPE]
SHEET_INNER_BORDER = (
    0.0127,
    0.0127,
    _TEMPLATE.width_m - 0.0127,
    _TEMPLATE.height_m - 0.0127,
)

Box = tuple[float, float, float, float]


def _relative(point_mm: tuple[float, float, float]) -> tuple[float, float]:
    """An assembly point on the front view, sheet m from item 1's origin."""
    return point_mm[0] * _S, point_mm[1] * _S


def label_box(text: str, upper_left: tuple[float, float]) -> Box:
    """A note's estimated box (x0, y0, x1, y1) from its upper-left corner."""
    lines = text.splitlines()
    x, y = upper_left
    return (x, y - len(lines) * LINE_PITCH, x + max(map(len, lines)) * CHAR_WIDTH, y)


def label_position(stem: str, tip: tuple[float, float]) -> tuple[float, float]:
    return (tip[0] + LABEL_OFFSETS[stem][0], tip[1] + LABEL_OFFSETS[stem][1])


def _exploded_tip_mm(stem: str) -> tuple[float, float, float]:
    offset = EXPLODE_OFFSETS_MM[stem]
    return tuple(p + o for p, o in zip(LABEL_TIPS_MM[stem], offset, strict=True))


def _group_extent() -> Box:
    """The exploded group (both axes, which span every item, and every
    label), sheet m from item 1's origin."""
    points = [_relative(end) for ends in EXPLODED_AXES_MM.values() for end in ends]
    for stem, text in EXPLODED_LABELS.items():
        x0, y0, x1, y1 = label_box(
            text, label_position(stem, _relative(_exploded_tip_mm(stem)))
        )
        points += [(x0, y0), (x1, y1)]
    xs, ys = zip(*points)
    return min(xs), min(ys), max(xs), max(ys)


# Item 1's bottom-end centre (sheet m), placed so the group's extent centres
# on the sheet inside its border (rule 15).
_EXTENT = _group_extent()
EXPLODED_ORIGIN = (
    round(
        (SHEET_INNER_BORDER[0] + SHEET_INNER_BORDER[2]) / 2.0
        - (_EXTENT[0] + _EXTENT[2]) / 2.0,
        3,
    ),
    round(
        (SHEET_INNER_BORDER[1] + SHEET_INNER_BORDER[3]) / 2.0
        - (_EXTENT[1] + _EXTENT[3]) / 2.0,
        3,
    ),
)


def nominal_sheet_point(point_mm: tuple[float, float, float]) -> tuple[float, float]:
    """Where the front view (model X right, Y up) prints an assembly point
    of the exploded group, sheet m; the build reads the real projection."""
    x, y = _relative(point_mm)
    return EXPLODED_ORIGIN[0] + x, EXPLODED_ORIGIN[1] + y


def _add_note(adapter: Any, text: str, xy: tuple[float, float], *, label: str) -> None:
    note = add_note(adapter, text, *xy)
    if note is None:
        raise RuntimeError(f"failed to place the fly-cutter {label}")
    printed = (
        str(_early_bound(note, "INote").GetText() or "")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
    )
    if printed != text:
        raise RuntimeError(f"fly-cutter {label} printed as {printed!r}")


def _bom_items(adapter: Any, table: Any) -> dict[str, str]:
    """Each part's ITEM NO. as the BOM prints it, read off its PART NUMBER
    row; the steps cite items 1-3."""
    table = _early_bound(table, "ITableAnnotation")

    def cell(row: int, column: int) -> str:
        return str(
            adapter._attempt(lambda: table.DisplayedText2(row, column, True)) or ""
        ).strip()

    header = [cell(0, column).upper() for column in range(int(table.ColumnCount))]
    items = [index for index, text in enumerate(header) if text.startswith("ITEM NO")]
    numbers = [index for index, text in enumerate(header) if text == "PART NUMBER"]
    if (
        int(table.RowCount) != 1 + len(BOM_COMPONENTS)
        or len(items) != 1
        or len(numbers) != 1
    ):
        raise RuntimeError(
            f"fly-cutter BOM is not {len(BOM_COMPONENTS)} item rows: {header!r}"
        )
    stems = {number: stem for stem, number in PART_NUMBERS.items()}
    printed = {
        stems.get(cell(row, numbers[0]), cell(row, numbers[0])): cell(row, items[0])
        for row in range(1, int(table.RowCount))
    }
    if printed != BOM_ITEMS:
        raise RuntimeError(
            f"fly-cutter BOM numbers its parts {printed!r}, not {BOM_ITEMS!r}"
        )
    return printed


def _move_model_point(
    adapter: Any,
    view: Any,
    point_mm: tuple[float, float, float],
    target: tuple[float, float],
    *,
    label: str,
) -> None:
    """Move ``view`` so the model point lands on ``target`` (sheet m)."""
    view = _early_bound(view, "IView")
    point = tuple(value / 1000.0 for value in point_mm)
    here = model_points_in_view(adapter, view, [point], label=label)[0]
    position = tuple(float(value) for value in view.Position)
    moved = [position[i] + target[i] - here[i] for i in range(2)]
    if not view.SetViewPosition(double_array(moved), False):
        raise RuntimeError(f"failed to move the {label}")
    rebuild_drawing(adapter, label=f"place {label}")
    here = model_points_in_view(adapter, view, [point], label=label)[0]
    if math.dist(here, target) > 1e-4:
        raise RuntimeError(f"{label}: origin sits at {here!r}, not {target!r}")


def _centreline(
    adapter: Any,
    view: Any,
    ends_mm: tuple[tuple[float, float, float], ...],
    *,
    label: str,
) -> Any:
    """One owned centreline in the view's sketch between two assembly points
    (draw_fr_top_frame._add_view_centerlines), returned as its segment."""
    draw = adapter.currentModel
    if not _early_bound(draw, "IDrawingDoc").ActivateView(view_name(adapter, view)):
        raise RuntimeError(f"failed to activate the fly-cutter view for the {label}")
    draw.ClearSelection2(True)
    sketch = _early_bound(_early_bound(view, "IView").GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    manager = _early_bound(draw.SketchManager, "ISketchManager")
    ends = []
    for x, y in model_points_in_view(
        adapter,
        view,
        [tuple(value / 1000.0 for value in end) for end in ends_mm],
        label=f"{label} endpoints",
    ):
        point = _early_bound(
            utility.CreatePoint(double_array([x, y, 0.0])), "IMathPoint"
        )
        ends.append(
            tuple(
                _early_bound(point.MultiplyTransform(transform), "IMathPoint").ArrayData
            )
        )
    previous = bool(manager.AddToDB)
    manager.AddToDB = True
    try:
        segment = manager.CreateCenterLine(*ends[0], *ends[1])
    finally:
        manager.AddToDB = previous
    if segment is None:
        raise RuntimeError(f"failed to create the {label} centreline")
    segment = _early_bound(segment, "ISketchSegment")
    segment.Color = 0  # COLORREF black, not the under-defined sketch blue.
    draw.ClearSelection2(True)
    rebuild_drawing(adapter, label=f"{label} centreline")
    return segment


def _settings(adapter: Any, view: Any) -> None:
    """The stick-out and swing radius: the assembly's own settings dimensions
    (``CutterSettingsReference``, build_dt_cone_tip_gear_tl_cutter_assembly),
    shown in ``view``, imported at their text points, proved against the
    spec at the assembly-authored places, parenthesized, named above.

    Two drawing-authored dimensions to the bit's tip failed on the farm
    because the tip is equation-curve topology (no circular root arc, run
    20261112T203021325Z; no vertex at the computed corner, run
    20261113T012650242Z). The settings sketch owns both ends of each
    reference, so nothing here depends on the bit's form edges."""
    label = "fly-cutter settings"
    _show_base_view_sketches(adapter, view, (fixture.SETTINGS_SKETCH,), label=label)
    annotations = curate_view_dimensions(
        adapter,
        view,
        keep=SETTINGS_TEXT_XY,
        view_label=label,
        dimensions_by_feature=fixture.DRAWING_DIMENSIONS,
    )
    printed = {dimension_name(adapter, annotation) for annotation in annotations}
    if printed != set(SETTINGS_TEXT_XY):
        raise RuntimeError(f"{label} imported {sorted(printed)}")
    assert_imported_precision(
        adapter, annotations, dict(fixture.DRAWING_PRECISION[fixture.SETTINGS_SKETCH])
    )
    set_dimension_callouts(
        adapter, annotations, dict(fixture.DIMENSION_CALLOUTS), location="above"
    )
    for annotation in annotations:
        name = dimension_name(adapter, annotation)
        display = _early_bound(
            set_reference_dimension(adapter, annotation, label=f"{label} {name}"),
            "IDisplayDimension",
        )
        measured = 1000.0 * abs(
            float(_early_bound(display.GetDimension2(0), "IDimension").SystemValue)
        )
        if abs(measured - SETTINGS_EXPECTED_MM[name]) > 1e-4:
            raise RuntimeError(
                f"{label} {name} reads {measured:.4f} mm, "
                f"expected {SETTINGS_EXPECTED_MM[name]:.4f}"
            )


def _place_sheet(adapter: Any) -> Any:
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_ORIGIN, scale=VIEW_SCALE)
    bottom = place_view(
        adapter, str(SOURCE), "*Bottom", *BOTTOM_ORIGIN, scale=VIEW_SCALE
    )
    origin = (0.0, 0.0, 0.0)
    _move_model_point(
        adapter, front, origin, FRONT_ORIGIN, label="fly-cutter front view"
    )
    _move_model_point(
        adapter, bottom, origin, BOTTOM_ORIGIN, label="fly-cutter bottom view"
    )
    for view, name in ((front, "*Front"), (bottom, "*Bottom")):
        set_hidden_lines_removed(adapter, view)
        apply_view_configuration(adapter, view, label=f"fly cutter {name}")
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    set_high_quality_shaded_with_edges(adapter, iso, label="fly cutter isometric")
    apply_view_configuration(
        adapter, iso, role=ViewRole.FULL_DETAIL, label="fly cutter *Isometric"
    )
    assert_full_detail_view(adapter, label="fly cutter")

    table = insert_bom_table(
        adapter,
        front,
        anchor_xy=BOM_ANCHOR,
        expected_components=BOM_COMPONENTS,
        descriptions=BOM_DESCRIPTIONS,
        component_identities=BOM_COMPONENT_IDENTITIES,
        part_number_property="Number",
        label="fly cutter",
    )
    items = _bom_items(adapter, table)
    landings = []
    for view, stems, label in (
        (front, FRONT_ITEMS, "fly-cutter front balloons"),
        (bottom, BOTTOM_ITEMS, "fly-cutter bottom balloons"),
    ):
        landings += add_component_bom_balloons(
            adapter,
            view,
            items=tuple((stem, items[stem]) for stem in stems),
            anchors=BALLOON_ANCHORS,
            label=label,
            margin=BALLOON_MARGIN,
            explode_offsets={},
        )
    if len(landings) != len(BOM_COMPONENTS):
        raise RuntimeError(
            f"fly cutter carries {len(landings)} balloons, expected {len(BOM_COMPONENTS)}"
        )

    # The bar's axis the swing radius is read from, then the setting the
    # fitter makes and the radius it gives.
    _centreline(adapter, front, AXIS_ENDS_MM, label="bar axis")
    _settings(adapter, front)
    for text, xy, label in (
        (fixture.ASSEMBLY_STEPS, STEPS_XY, "fitting steps"),
        (fixture.ISO_NOTE, ISO_NOTE_XY, "isometric scale note"),
    ):
        _add_note(adapter, text, xy, label=label)
    set_hidden_lines_removed(adapter, front)
    return lambda: assert_balloon_landings(adapter, landings)


def _activate_sheet(adapter: Any, name: str) -> None:
    ddoc = _early_bound(adapter.currentModel, "IDrawingDoc")
    if not ddoc.ActivateSheet(name):
        raise RuntimeError(f"failed to activate fly-cutter sheet {name!r}")
    actual = str(_early_bound(ddoc.GetCurrentSheet(), "ISheet").GetName() or "")
    if actual != name:
        raise RuntimeError(f"fly-cutter sheet is {actual!r}, expected {name!r}")


def _item_view(adapter: Any, stem: str, target: tuple[float, float]) -> Any:
    """A front view of ``stem`` alone, hidden lines removed, its assembly
    origin moved onto ``target`` (sheet m)."""
    label = f"fly-cutter exploded {stem}"
    view = place_view(adapter, str(SOURCE), "*Front", *target, scale=VIEW_SCALE)
    set_hidden_lines_removed(adapter, view)
    apply_view_configuration(adapter, view, label=label)
    view = isolate_drawing_view_components(
        adapter, view, visible_stems=frozenset({stem}), label=label
    )
    _move_model_point(adapter, view, (0.0, 0.0, 0.0), target, label=label)
    return view


def _place_exploded_sheet(adapter: Any) -> Callable[[], None]:
    """Sheet 2: item 1 at EXPLODED_ORIGIN, items 2 and 3 each drawn where
    its explode offset lands in item 1's view, both axes, the labels and
    the caption (rule 22)."""
    label = "fly-cutter exploded view"
    _activate_sheet(adapter, SHEET_NAMES[1])
    targets = {BAR: EXPLODED_ORIGIN}
    views = {BAR: _item_view(adapter, BAR, EXPLODED_ORIGIN)}
    loose = (BIT, SET_SCREW)
    targets.update(
        zip(
            loose,
            model_points_in_view(
                adapter,
                views[BAR],
                [
                    tuple(value / 1000.0 for value in EXPLODE_OFFSETS_MM[stem])
                    for stem in loose
                ],
                label=f"{label} offsets",
            ),
            strict=True,
        )
    )
    for stem in loose:
        views[stem] = _item_view(adapter, stem, targets[stem])
    for name, ends in EXPLODED_AXES_MM.items():
        _centreline(adapter, views[BAR], ends, label=f"exploded {name}")
    for stem, text in EXPLODED_LABELS.items():
        (tip,) = model_points_in_view(
            adapter,
            views[stem],
            [tuple(value / 1000.0 for value in LABEL_TIPS_MM[stem])],
            label=f"{label} {stem} label tip",
        )
        add_leader_note(
            adapter,
            text,
            text_xy=label_position(stem, tip),
            attach_xy=tip,
            label=f"{label}: {text}",
            view=views[stem],
        )
    _activate_sheet(adapter, SHEET_NAMES[1])
    _add_note(adapter, EXPLODED_CAPTION, CAPTION_XY, label="exploded view caption")

    def settled() -> None:
        for stem, view in views.items():
            (here,) = model_points_in_view(
                adapter, view, [(0.0, 0.0, 0.0)], label=f"settled {label} {stem}"
            )
            if math.dist(here, targets[stem]) > 1e-4:
                raise RuntimeError(
                    f"settled {label}: {stem} sits at {here!r}, not {targets[stem]!r}"
                )

    return settled


@_telemetry.traced("drawing.dt_cone_tip_gear_tl_cutter_assembly")
async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source assembly is missing: {SOURCE}")

    check("open fly-cutter drawing source", await adapter.open_model(str(SOURCE)))
    properties = read_required_properties(
        _early_bound(adapter.currentModel, "IModelDoc2"),
        ("Number", "Revision", "Title", "Material Specification", "Finish", "Quantity"),
        required=("Number", "Revision", "Material Specification", "Finish", "Quantity"),
    )
    if properties["Number"] != DRAWING_NUMBER:
        raise RuntimeError(
            f"fly-cutter source Number {properties['Number']!r} != {DRAWING_NUMBER!r}"
        )
    new_project_drawing(
        adapter,
        layout=SPEC.layout,
        scale=SHEET_SCALE,
        unit=fixture.CONTRACT.drawing_unit,
    )
    create_blank_drawing_sheets(adapter, SHEET_NAMES, label="fly-cutter package")
    ddoc = _early_bound(adapter.currentModel, "IDrawingDoc")
    for name in SHEET_NAMES:
        _activate_sheet(adapter, name)
        sheet = _early_bound(ddoc.GetCurrentSheet(), "ISheet")
        if not sheet.SetScale(*SHEET_SCALES[name], False, False):
            raise RuntimeError(f"failed to set fly-cutter sheet scale: {name}")
    _activate_sheet(adapter, SHEET_NAMES[0])
    sheet_settled = _place_sheet(adapter)
    exploded_settled = _place_exploded_sheet(adapter)

    def settled() -> None:
        sheet_settled()
        exploded_settled()

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        layout=SPEC.layout,
        pdf_title="Cone Tip Gear Fly Cutter Assembly Drawing",
        scale=SHEET_SCALE,
        expected_sheet_names=SHEET_NAMES,
        sheet_layouts=SHEET_LAYOUTS,
        sheet_scales=SHEET_SCALES,
        settled_checks=(settled,),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[ARTIFACT_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
