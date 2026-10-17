"""Offline contract for the oblique-trammel jig drawing package (TL-000).

The sheet text comes from the jig spec, the BOM prints registry numbers then
the bought items by inventory id, every modelled component carries a balloon,
and each sheet's budgeted regions stay inside the border, out of the title
block and clear of one another.
"""

from __future__ import annotations

import math
from types import SimpleNamespace

import pytest

import _config
import ch_rocker_arm_tl_oblique_jig_assembly_spec as spec
import draw_ch_rocker_arm_tl_oblique_jig_assembly as drawing
from _drawing_layout_check import LeaderSegment, find_leader_leader_crossings


# Default-format note text: about 2.8 mm a character and 4.5 mm a line on the
# farm's templates (draw_pd_paper_drive_assembly fits 68 characters in 0.192).
CHAR_M = 0.0029
LINE_M = 0.0045
ROW_PITCH_M = 0.00615
ISO = math.sqrt(2.0 / 3.0)  # an isometric view's foreshortening


def _note_box(text: str, xy: tuple[float, float]) -> tuple[float, float, float, float]:
    lines = text.split("\n")
    width = max(len(line) for line in lines) * CHAR_M
    return xy[0], xy[1] - len(lines) * LINE_M, xy[0] + width, xy[1]


def _view_box(center, width_mm, height_mm, scale, margin=0.0):
    w = width_mm / 1000.0 * scale[0] / scale[1] / 2.0 + margin
    h = height_mm / 1000.0 * scale[0] / scale[1] / 2.0 + margin
    return center[0] - w, center[1] - h, center[0] + w, center[1] + h


def _overlap(a, b) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def _inside_sheet(box) -> bool:
    left, bottom, right, top = drawing.SHEET_INNER_BORDER
    return (
        box[0] >= left
        and box[1] >= bottom
        and box[2] <= right
        and box[3] <= top
        and not _overlap(box, drawing.TITLE_BLOCK)
    )


# jig-r5 read the exploded isometric's outline (IView.GetOutline) at 127.4 x
# 113.2 mm at 1:8, against the 116.3 x 101.6 the -3 tree's extent projects:
# SolidWorks' outline is looser than the parts' silhouette. The layout tests
# grow the projected size by that measured ratio.
OUTLINE_GROWTH = (1.10, 1.12)


def _iso_size(lift_mm: float) -> tuple[float, float]:
    (x0, x1), (y0, y1), (z0, z1) = spec.MODEL_EXTENT
    plan = (x1 - x0) + (y1 - y0)
    return (
        plan * math.cos(math.pi / 4.0) * OUTLINE_GROWTH[0],
        (plan * ISO / 2.0 + (z1 - z0 + lift_mm) * ISO) * OUTLINE_GROWTH[1],
    )


EXPLODE_LIFT = max(
    sum(d for _label, families, _axis, d in spec.EXPLODE_STEPS if family in families)
    for family in spec.QUANTITIES
)


def test_sheets_are_landscape_with_their_scales() -> None:
    assert drawing.SHEET_NAMES == (
        "ASSEMBLED AT INNER PASS",
        "EXPLODED VIEW + BOM",
        "ASSEMBLY STEPS",
    )
    assert set(drawing.SHEET_LAYOUTS.values()) == {drawing.DrawingLayout.LANDSCAPE}
    assert drawing.SHEET_SCALES == {
        "ASSEMBLED AT INNER PASS": (1.0, 4.0),
        "EXPLODED VIEW + BOM": (1.0, 10.0),
        "ASSEMBLY STEPS": (1.0, 8.0),
    }
    assert drawing.SHEET_SCALE == (1.0, 4.0)
    assert drawing.SPEC.source_kind == "assembly"
    assert drawing.ARTIFACT_STEM == "ch-rocker-arm-tl-oblique-jig-assembly"


def test_sheet_text_is_the_spec_text_wrapped() -> None:
    def words(text: str) -> list[str]:
        return text.split()

    assert words(drawing.ASSEMBLED_CAPTION) == words(spec.ASSEMBLED_CAPTION)
    assert words(drawing.ALIGNMENT_NOTE) == words(" ".join(spec.ALIGNMENT_NOTE_LINES))
    assert words(drawing.ASSEMBLY_STEPS) == words(
        "ASSEMBLY SEQUENCE " + " ".join(spec.ASSEMBLY_STEPS)
    )
    assert words(drawing.ASSEMBLY_CHECKS) == words(" ".join(spec.ASSEMBLY_CHECKS))
    for text, width in (
        (drawing.ASSEMBLED_CAPTION, drawing.CAPTION_WIDTH),
        (drawing.ALIGNMENT_NOTE, drawing.ALIGNMENT_WIDTH),
        (drawing.ASSEMBLY_STEPS, drawing.STEPS_LINE_WIDTH),
        (drawing.ASSEMBLY_CHECKS, drawing.CHECKS_LINE_WIDTH),
    ):
        assert max(len(line) for line in text.split("\n")) <= width
    # Each alignment station prints whole on one line.
    for line in spec.ALIGNMENT_NOTE_LINES[1:]:
        assert line in drawing.ALIGNMENT_NOTE.split("\n")


def test_assembled_sheet_regions_fit_apart() -> None:
    (x0, x1), (y0, y1), (z0, z1) = spec.MODEL_EXTENT
    plan = _view_box(drawing.PLAN_CENTER, x1 - x0, y1 - y0, drawing.ASSEMBLED_SCALE)
    elevation = _view_box(
        drawing.ELEVATION_CENTER, x1 - x0, z1 - z0, drawing.ASSEMBLED_SCALE
    )
    caption = _note_box(drawing.ASSEMBLED_CAPTION, drawing.CAPTION_XY)
    alignment = _note_box(drawing.ALIGNMENT_NOTE, drawing.ALIGNMENT_XY)
    plan_title = _note_box(spec.PLAN_VIEW_LABEL, drawing.PLAN_LABEL_XY)
    elevation_title = _note_box(spec.ELEVATION_VIEW_LABEL, drawing.ELEVATION_LABEL_XY)
    regions = (plan, elevation, caption, alignment, plan_title, elevation_title)
    assert all(_inside_sheet(box) for box in regions)
    for index, a in enumerate(regions):
        for b in regions[index + 1 :]:
            assert not _overlap(a, b)
    # Third-angle: the plan above the elevation on one vertical.
    assert drawing.PLAN_CENTER[0] == drawing.ELEVATION_CENTER[0]
    assert plan[1] > elevation[3]
    # Each title centred under its own view.
    for title, view in ((plan_title, plan), (elevation_title, elevation)):
        assert (title[0] + title[2]) / 2.0 == pytest.approx((view[0] + view[2]) / 2.0)
        assert title[3] < view[1]
    assert plan_title[1] > elevation[3]


def _plan_xy(x_mm: float, y_mm: float) -> tuple[float, float]:
    """Sheet metres of a machine plan point, the plan centred on the extent."""
    (x0, x1), (y0, y1), _z = spec.MODEL_EXTENT
    ratio = drawing.ASSEMBLED_SCALE[0] / drawing.ASSEMBLED_SCALE[1] / 1000.0
    return (
        drawing.PLAN_CENTER[0] + (x_mm - (x0 + x1) / 2.0) * ratio,
        drawing.PLAN_CENTER[1] + (y_mm - (y0 + y1) / 2.0) * ratio,
    )


def test_plan_tags_stand_apart_inside_the_sheet() -> None:
    boxes = [_note_box(tag.text, _plan_xy(*tag.text_xy)) for tag in spec.PLAN_TAGS]
    others = (
        _note_box(drawing.ASSEMBLED_CAPTION, drawing.CAPTION_XY),
        _note_box(drawing.ALIGNMENT_NOTE, drawing.ALIGNMENT_XY),
        _note_box(spec.PLAN_VIEW_LABEL, drawing.PLAN_LABEL_XY),
    )
    assert all(_inside_sheet(box) for box in boxes)
    for index, a in enumerate(boxes):
        for b in boxes[index + 1 :] + list(others):
            assert not _overlap(a, b)
    # Two tags one above the other stand a row pitch apart, or the layout
    # audit reads them as one block (6.15 mm at their text height, jig-r7).
    for index, a in enumerate(boxes):
        for b in boxes[index + 1 :]:
            if a[0] < b[2] and b[0] < a[2]:
                assert max(b[1] - a[3], a[1] - b[3]) >= ROW_PITCH_M
    # No tag's text sits on the carrier (its plan outline at the pose).
    corners = [spec.POSE.to_machine(p) for p in spec.CARRIER_OUTLINES["carrier"]]
    (cx0, cy0), (cx1, cy1) = (
        _plan_xy(min(x for x, _ in corners), min(y for _, y in corners)),
        _plan_xy(max(x for x, _ in corners), max(y for _, y in corners)),
    )
    for box in boxes:
        assert not _overlap(box, (cx0, cy0, cx1, cy1))


def test_no_base_bar_edge_runs_through_a_plan_tag() -> None:
    """c3-r6 (rule 14): the 1/2 x 6 bars' operator-side edges ran through the
    A1 and B1 texts. Sampled along every bar edge, no point lands in a tag's
    text box, 1 mm (sheet) of air kept round it."""
    air = 0.001
    boxes = {
        tag.text.split("\n")[0]: _note_box(tag.text, _plan_xy(*tag.text_xy))
        for tag in spec.PLAN_TAGS
    }
    for rail in spec.RAILS:
        near_op, near_col, far_op, far_col = spec._bar_corners(rail)
        for a, b in (
            (near_op, far_op),
            (near_col, far_col),
            (near_op, near_col),
            (far_op, far_col),
        ):
            for k in range(401):
                t = k / 400.0
                x, y = _plan_xy(a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))
                for name, (x0, y0, x1, y1) in boxes.items():
                    inside = x0 - air < x < x1 + air and y0 - air < y < y1 + air
                    assert not inside, (name, rail)


def test_every_view_is_a_spec_named_view() -> None:
    with open(drawing.__file__, encoding="utf-8") as handle:
        source = handle.read()
    for standard in ('"*Top"', '"*Front"', '"*Bottom"', '"*Isometric"'):
        assert standard not in source
    assert source.count("place_view(") == 1  # inside _place_named_view only
    for name in ("PLAN_VIEW", "ELEVATION_VIEW", "ISOMETRIC_VIEW"):
        assert f"spec.{name}" in source


def test_exploded_sheet_regions_fit_apart() -> None:
    width, height = _iso_size(EXPLODE_LIFT)
    exploded = _view_box(
        drawing.EXPLODED_ISO_CENTER,
        width,
        height,
        drawing.EXPLODED_SCALE,
        margin=drawing.BALLOON_MARGIN,
    )
    # The BOM column, down to the title block: its wrapped rows may run long.
    bom = (
        drawing.BOM_ANCHOR[0],
        drawing.TITLE_BLOCK[3],
        drawing.BOM_ANCHOR[0] + sum(drawing.BOM_COLUMN_WIDTHS.values()),
        drawing.BOM_ANCHOR[1],
    )
    caption = _note_box(drawing.EXPLODED_CAPTION, drawing.EXPLODED_CAPTION_XY)
    regions = (exploded, bom, caption)
    assert all(_inside_sheet(box) for box in regions)
    for index, a in enumerate(regions):
        for b in regions[index + 1 :]:
            assert not _overlap(a, b)
    assert bom[2] == pytest.approx(drawing.SHEET_INNER_BORDER[2])
    # The ringed view stays in the room the drawing asserts at run time, with
    # room to spare.
    region = drawing.EXPLODED_REGION
    assert region[0] <= exploded[0] and exploded[2] <= region[2]
    assert region[1] <= exploded[1] and exploded[3] <= region[3]
    assert (region[2] - region[0]) - (exploded[2] - exploded[0]) >= 0.010


def test_steps_sheet_regions_fit_apart() -> None:
    finished = _view_box(
        drawing.ASSEMBLY_ISO_CENTER, *_iso_size(0.0), drawing.ISOMETRIC_SCALE
    )
    steps = _note_box(drawing.ASSEMBLY_STEPS, drawing.STEPS_XY)
    checks = _note_box(drawing.ASSEMBLY_CHECKS, drawing.CHECKS_XY)
    regions = (finished, steps, checks)
    assert all(_inside_sheet(box) for box in regions)
    for index, a in enumerate(regions):
        for b in regions[index + 1 :]:
            assert not _overlap(a, b)


def test_every_modelled_component_carries_a_balloon() -> None:
    assert set(drawing.BALLOON_ANCHORS) == set(spec.QUANTITIES)
    assert set(drawing.TWO_OFF) == {
        spec.BASE_BAR,
        spec.PIVOT_BLOCK,
        spec.PIVOT_PIN,
        spec.END_BRACKET,
    }
    for stem in drawing.TWO_OFF:
        pinned = {
            drawing.BALLOON_ANCHORS[stem].instance,
            drawing.SECOND_INSTANCE_BALLOON_ANCHORS[stem].instance,
        }
        assert pinned == {f"{stem}-1", f"{stem}-2"}
    singles = [stem for stem, count in spec.QUANTITIES.items() if count == 1]
    assert all(drawing.BALLOON_ANCHORS[stem].instance is None for stem in singles)
    assert (
        len(singles) + 2 * len(drawing.TWO_OFF) == sum(spec.QUANTITIES.values()) == 13
    )


def test_crossed_leaders_swap_ring_slots() -> None:
    # Each balloon's leader runs to the attachment under the other's circle.
    centres = [(0.0, 0.01), (0.01, 0.01), (0.03, 0.01)]
    attachments = [(0.01, 0.0), (0.0, 0.0), (0.03, 0.0)]
    assert drawing.uncrossed_ring_slots(centres, attachments) == [1, 0, 2]
    assert drawing.uncrossed_ring_slots(centres, centres) == [0, 1, 2]
    with pytest.raises(ValueError):
        drawing.uncrossed_ring_slots(centres, attachments[:2])


def test_a_leader_ending_on_another_still_swaps() -> None:
    # jig-r8's balloons 1 and 2 (sheet metres): balloon 2's attachment lies
    # on balloon 1's leader, a "touch" to the audit's crossing test, and the
    # rebuild left it 0.5 mm across. Run past the attachment, it crosses.
    centres = [(0.1582, 0.1165), (0.1489, 0.1047)]
    attachments = [(0.1092, 0.1448), (0.1187, 0.1393)]
    segments = [
        LeaderSegment(str(i), "balloon", *centre, *attach)
        for i, (centre, attach) in enumerate(zip(centres, attachments))
    ]
    assert not find_leader_leader_crossings(segments)
    assert drawing.uncrossed_ring_slots(centres, attachments) == [1, 0]


def test_leaders_converging_under_the_run_on_do_not_toggle() -> None:
    # c4-r4: two leaders ending 1 mm apart cross once run on whichever slots
    # they take; the crossed pair swaps once and the near pair stays put.
    centres = [(0.0, 0.02), (0.02, 0.02)]
    attachments = [(0.0105, 0.0), (0.0095, 0.0)]
    assert drawing.uncrossed_ring_slots(centres, attachments) == [1, 0]


def test_bom_identity_is_the_registry_and_the_inventory() -> None:
    for stem in spec.QUANTITIES:
        assert drawing.BOM_PART_NUMBERS[stem] == _config.parts(stem)["number"]
    assert drawing.BOM_PART_NUMBERS[spec.BASE_BAR] == "MHA-CH-006-TL-20"
    assert drawing.BOM_PART_NUMBERS[spec.END_BRACKET] == "MHA-CH-006-TL-28"
    assert drawing.BOM_PART_NUMBERS[spec.NUT_BRACKET] == "MHA-CH-006-TL-29"
    assert drawing.BOUGHT_ITEM_NUMBERS == tuple(str(n) for n in range(10, 19))
    assert drawing.BOM_INVENTORY_TITLE == "INVENTORY ID"
    # The column holds the longest id whole: ids do not wrap.
    longest = max(len(item.inventory_id) for item in spec.BOUGHT_ITEMS)
    assert drawing.BOM_COLUMN_WIDTHS["inventory"] >= longest * drawing.BOM_CHAR_M
    longest_number = max(len(number) for number in drawing.BOM_PART_NUMBERS.values())
    assert drawing.BOM_COLUMN_WIDTHS["part"] >= longest_number * drawing.BOM_CHAR_M
    assert not hasattr(drawing, "BOM_SKUS")


class _Table:
    """A BOM in SolidWorks' native order, with the edits the recipe makes."""

    def __init__(self, native_order):
        self.cells = [["ITEM NO.", "PART NUMBER", "DESCRIPTION", "QTY."]]
        self.cells += [
            [
                str(item),
                stem,
                drawing.BOM_DESCRIPTIONS[stem],
                str(spec.QUANTITIES[stem]),
            ]
            for item, stem in enumerate(native_order, 1)
        ]
        self.inserted_rows = 0

    @property
    def RowCount(self):
        return len(self.cells)

    @property
    def ColumnCount(self):
        return len(self.cells[0])

    def DisplayedText(self, row, column):
        return self.cells[row][column]

    def IsCellTextEditable(self, row, column):
        return True

    def SetText2(self, row, column, linked, text):
        assert linked is False
        self.cells[row][column] = text

    def InsertColumn2(self, where, after, title, width):
        assert where == drawing._INSERT_COLUMN_AFTER
        assert width == drawing._INSERT_COLUMN_DEFAULT_WIDTH
        assert after == 2 and title == drawing.BOM_INVENTORY_TITLE
        for row in self.cells:
            row.insert(after + 1, "")
        return True

    def SetColumnTitle2(self, column, title, linked):
        assert linked is False
        self.cells[0][column] = title
        return True

    def InsertRow(self, where, index):
        assert where == drawing._INSERT_ROW_LAST
        self.cells.append([""] * len(self.cells[0]))
        self.inserted_rows += 1
        return True

    def SetColumnWidth(self, column, width, options):
        assert options == 0
        return width


def test_bom_prints_registry_numbers_then_the_bought_items(monkeypatch) -> None:
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)
    native_order = tuple(reversed(spec.BOM_ORDER))
    table = _Table(native_order)
    adapter = SimpleNamespace(currentModel=SimpleNamespace(EditRebuild3=lambda: True))
    items = drawing._validate_bom(adapter, table)
    assert dict(items) == {stem: str(item) for item, stem in enumerate(native_order, 1)}
    assert [stem for stem, _item in items] == list(spec.BOM_ORDER)
    assert table.cells[0] == [
        "ITEM NO.",
        "PART NUMBER",
        "DESCRIPTION",
        "INVENTORY ID",
        "QTY.",
    ]
    for row, stem in zip(table.cells[1:], native_order):
        assert row[1:] == [
            drawing.BOM_PART_NUMBERS[stem],
            drawing.BOM_DESCRIPTIONS[stem],
            drawing.NO_ENTRY,
            str(spec.QUANTITIES[stem]),
        ]
    assert table.inserted_rows == len(spec.BOUGHT_ITEMS)
    bought = table.cells[1 + len(native_order) :]
    assert bought == [
        [
            number,
            drawing.NO_ENTRY,
            item.description,
            item.inventory_id,
            str(item.quantity),
        ]
        for number, item in zip(drawing.BOUGHT_ITEM_NUMBERS, spec.BOUGHT_ITEMS)
    ]


def test_bom_refuses_a_wrong_quantity(monkeypatch) -> None:
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)
    table = _Table(spec.BOM_ORDER)
    table.cells[1][3] = "1"  # the base bar row grouped per configuration
    adapter = SimpleNamespace(currentModel=SimpleNamespace(EditRebuild3=lambda: True))
    with pytest.raises(RuntimeError, match="quantity"):
        drawing._validate_bom(adapter, table)


def test_bom_refuses_a_bought_cell_that_does_not_stick(monkeypatch) -> None:
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)

    class Stubborn(_Table):
        def SetText2(self, row, column, linked, text):
            if row > len(spec.BOM_ORDER) and column == 3:
                return  # the inserted row keeps a blank inventory id
            super().SetText2(row, column, linked, text)

    adapter = SimpleNamespace(currentModel=SimpleNamespace(EditRebuild3=lambda: True))
    with pytest.raises(RuntimeError, match="inventory reads"):
        drawing._validate_bom(adapter, Stubborn(spec.BOM_ORDER))


def test_recipe_never_imports_the_generic_assembly_drawing() -> None:
    source = drawing.__file__
    with open(source, encoding="utf-8") as handle:
        text = handle.read()
    assert "_assembly_drawing" not in text
    assert "ch_rocker_arm_tl_oblique_jig_assembly_spec" in text


class _Manager:
    def __init__(self, source: _Source) -> None:
        self._source = source

    @property
    def ActiveConfiguration(self) -> SimpleNamespace:
        return SimpleNamespace(Name=self._source.active)


class _Source:
    """A source assembly whose ShowConfiguration2 switches its active one."""

    def __init__(self, *, refuse: frozenset[str] = frozenset()) -> None:
        self.active = drawing.ASSEMBLY_VIEW_CONFIGURATION
        self.shown: list[str] = []
        self.refuse = refuse
        self.ConfigurationManager = _Manager(self)

    def ShowConfiguration2(self, name: str) -> bool:
        self.shown.append(name)
        if name in self.refuse:
            return False
        self.active = name
        return True


def _exploded_view(source: _Source) -> SimpleNamespace:
    return SimpleNamespace(
        ReferencedConfiguration=drawing.SIMPLIFIED_VIEW_CONFIGURATION,
        ReferencedDocument=source,
        IsExploded=lambda: True,
    )


def test_balloons_read_the_explode_in_the_source_s_active_configuration(
    monkeypatch,
) -> None:
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)
    source = _Source()
    with drawing._source_configuration_active(_exploded_view(source), label="t"):
        assert source.active == drawing.SIMPLIFIED_VIEW_CONFIGURATION
    assert source.active == drawing.ASSEMBLY_VIEW_CONFIGURATION
    assert source.shown == [
        drawing.SIMPLIFIED_VIEW_CONFIGURATION,
        drawing.ASSEMBLY_VIEW_CONFIGURATION,
    ]


def test_source_configuration_is_restored_when_the_balloons_fail(monkeypatch) -> None:
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)
    source = _Source()
    with pytest.raises(RuntimeError, match="balloon"):
        with drawing._source_configuration_active(_exploded_view(source), label="t"):
            raise RuntimeError("balloon")
    assert source.active == drawing.ASSEMBLY_VIEW_CONFIGURATION


def test_source_configuration_switch_is_read_back(monkeypatch) -> None:
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)
    source = _Source(refuse=frozenset({drawing.SIMPLIFIED_VIEW_CONFIGURATION}))
    with pytest.raises(RuntimeError, match="did not activate"):
        with drawing._source_configuration_active(_exploded_view(source), label="t"):
            pass
    restore = _Source(refuse=frozenset({drawing.ASSEMBLY_VIEW_CONFIGURATION}))
    with pytest.raises(RuntimeError, match="did not re-activate"):
        with drawing._source_configuration_active(_exploded_view(restore), label="t"):
            pass


def test_exploded_sheet_balloons_inside_the_source_configuration_switch() -> None:
    with open(drawing.__file__, encoding="utf-8") as handle:
        text = handle.read()
    body = text[text.index("def _place_exploded_sheet") :]
    body = body[: body.index("\ndef ")]
    switch = body.index("with _source_configuration_active(exploded")
    assert body.count("add_component_bom_balloons(") == 2
    assert all(
        index > switch
        for index in (
            body.index("add_component_bom_balloons("),
            body.rindex("add_component_bom_balloons("),
        )
    )
