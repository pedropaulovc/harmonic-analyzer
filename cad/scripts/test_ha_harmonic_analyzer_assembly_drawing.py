"""Offline contract for the complete-machine fitter package (MHA-HA-00)."""

import re
from pathlib import Path
from types import SimpleNamespace

import pytest

import build_ha_harmonic_analyzer_assembly as builder
import ch_channel_assembly_steps
import draw_ha_harmonic_analyzer_assembly as drawing
import fr_top_frame_spec
import fr_tube_frame_spec
import ha_harmonic_analyzer_assembly_sheet as notes
import ha_harmonic_analyzer_assembly_spec as spec
import ha_harmonic_analyzer_assembly_steps as steps
import joint_retention
import ms_measuring_stick_assembly_spec as ms
from _assembly_contract import assembly_contract
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_types import DRAWING_TEMPLATES, DrawingLayout


def test_registry_outputs_and_sheet_templates() -> None:
    registered = DRAWINGS_BY_NAME["ha_harmonic_analyzer_assembly"]
    assert registered.source_kind == "assembly"
    assert registered.part == "ha_harmonic_analyzer"
    assert registered.layout is DrawingLayout.PORTRAIT
    assert drawing.SOURCE == registered.source
    assert drawing.OUTPUTS == drawing.OUTPUTS.__class__(
        registered.outputs["slddrw"],
        registered.outputs["pdf"],
        registered.outputs["png"],
    )
    assert set(drawing.SHEET_LAYOUTS) == set(drawing.SHEET_NAMES)
    assert set(drawing.SHEET_SCALES) == set(drawing.SHEET_NAMES)
    assert drawing.SHEET_LAYOUTS[drawing.SHEET_NAMES[0]] is registered.layout
    assert {
        DRAWING_TEMPLATES[layout].path for layout in drawing.SHEET_LAYOUTS.values()
    } == set(registered.assets)
    # The 1:8 single sheet was illegible (#1533): the assembled views read at 1:5.
    assert drawing.SHEET_SCALES[drawing.SHEET_NAMES[0]] == (1.0, 5.0)


def test_bom_is_one_row_per_subassembly_in_insertion_order() -> None:
    assert spec.BOM_ORDER == (*builder.SUBASSEMBLIES, spec.MEASURING_STICK)
    assert len(spec.BOM_ORDER) == len(set(spec.BOM_ORDER)) == 8
    assert drawing.BOM_PART_NUMBERS == {
        stem: assembly_contract(stem).number for stem in spec.BOM_ORDER
    }
    assert all(number.endswith("-00") for number in drawing.BOM_PART_NUMBERS.values())
    assert set(notes.BOM_DESCRIPTIONS) == set(spec.BOM_ORDER)
    assert (
        max(map(len, notes.BOM_DESCRIPTIONS.values()))
        <= drawing.BOM_DESCRIPTION_MAX_CHARS
    )


@pytest.mark.parametrize("row", spec.BOM_ORDER)
def test_each_row_balloons_a_part_only_its_subassembly_builds(row: str) -> None:
    part = notes.BALLOON_PARTS[row]
    scripts = Path(builder.__file__).parent
    owners = [
        stem
        for stem in spec.BOM_ORDER
        if f'"{part}"'
        in (scripts / f"build_{stem.replace('-', '_')}_assembly.py").read_text(
            encoding="utf-8"
        )
    ]
    assert owners == [row]


def test_builder_recipe_does_not_read_the_sheet_text() -> None:
    # Wording edits must not rebuild the complete-machine assembly.
    for module in (builder, spec):
        source = Path(module.__file__).read_text(encoding="utf-8")
        assert "import ha_harmonic_analyzer_assembly_sheet" not in source
        assert "from ha_harmonic_analyzer_assembly_sheet" not in source


def test_explode_moves_every_subassembly_but_the_frame_once_each() -> None:
    instances = [spec.Instance(f"{stem}-1", stem) for stem in spec.BOM_ORDER]
    plan = spec.plan_explode(instances)
    moved = {name for _step, names in plan for name in names}
    assert moved == {f"{stem}-1" for stem in spec.BOM_ORDER if stem != "fr-frame"}
    assert all(len(names) == 1 for _step, names in plan)
    with pytest.raises(ValueError, match="absent"):
        spec.plan_explode(instances[1:-1])
    with pytest.raises(ValueError, match="more than once"):
        spec.plan_explode([*instances, spec.Instance("pn-pen-2", "pn-pen")])


def test_settings_are_derived_from_the_pose_sources() -> None:
    assert spec.BAR_HEIGHT_MM == pytest.approx(529.9)
    # The pen stud stands 0.8 higher since its 3.2 engagement (code review C05).
    assert spec.STUD_DROP_MM == pytest.approx(61.7)
    assert {line.dimension: line.length for line in spec.SETTING_LINES} == {
        spec.BAR_HEIGHT_DIMENSION: spec.BAR_HEIGHT_MM,
        spec.STUD_DROP_DIMENSION: spec.STUD_DROP_MM,
    }
    assert spec.DRAWING_DIMENSIONS == {
        spec.SETTING_FEATURE: {line.dimension for line in spec.SETTING_LINES}
    }


def test_settings_print_at_the_inch_xx_grade() -> None:
    """#290: the sheet is decimal inch. Both settings are functional, so they
    take the .XX row (+/-.01), tighter than the mm .X row (+/-0.8) they
    replace, never the inch .X row (+/-.1) kept for non-functional sizes."""
    from _printed_tolerance import printed_band_mm

    assert spec.SETTING_PRECISION == 2
    assert spec.DRAWING_PRECISION == {
        spec.SETTING_FEATURE: {
            line.dimension: spec.SETTING_PRECISION for line in spec.SETTING_LINES
        }
    }
    printed = {
        line.dimension: f"{line.length / 25.4:.{spec.SETTING_PRECISION}f}"
        for line in spec.SETTING_LINES
    }
    assert printed == {spec.BAR_HEIGHT_DIMENSION: "20.86", spec.STUD_DROP_DIMENSION: "2.43"}
    band = printed_band_mm(spec.SETTING_PRECISION, unit="in")
    assert band == pytest.approx(0.254)
    assert band < printed_band_mm(1, unit="mm")
    # The as-modelled machine passes the printed setting: rounding to the
    # printed value spends under half its band.
    for line in spec.SETTING_LINES:
        offset = abs(float(printed[line.dimension]) * 25.4 - line.length)
        assert offset < band / 2.0


def test_the_package_is_decimal_inch_end_to_end(monkeypatch) -> None:
    """The contract's drawing_unit drives the model's units (right after
    create_assembly), the TOL_* rows and both new_project_drawing calls."""
    import asyncio

    from _title_block_units import linear_band_display

    assert assembly_contract(spec.ASM_NAME).drawing_unit == "in" == drawing.UNIT
    assert linear_band_display(2, unit=drawing.UNIT) == "±.01"

    class Reached(Exception):
        pass

    calls: list[object] = []

    async def create_assembly():
        calls.append("create_assembly")
        return SimpleNamespace(is_success=True, data=None, error=None)

    def model_units(adapter, unit, *, label):
        calls.append((unit, label))
        raise Reached

    monkeypatch.setattr(builder, "apply_package_model_units", model_units)
    adapter = SimpleNamespace(create_assembly=create_assembly)
    with pytest.raises(Reached):
        asyncio.run(builder.build(adapter))
    assert calls == ["create_assembly", ("in", builder.ASM_NAME)]

    units: list[str] = []

    def new_drawing(_adapter, *, layout, scale, unit):
        units.append(unit)
        raise Reached

    monkeypatch.setattr(drawing, "new_project_drawing", new_drawing)
    with pytest.raises(Reached):
        drawing._create_mixed_package_sheets(SimpleNamespace())
    with pytest.raises(Reached):
        drawing._append_template_sheet(
            SimpleNamespace(), None, name=drawing.SHEET_NAMES[-1]
        )
    assert units == ["in", "in"]


def test_bar_height_chain_lies_on_the_west_front_column_axis() -> None:
    """Machinist review r2/r3 (b4df34ad9): at the deck's west edge the shown
    chain floated beside the column. It lies on the column's axis, and the
    front view's centreline is picked on that axis above the chain's top."""
    (bar,) = [
        line for line in spec.SETTING_LINES if line.dimension == spec.BAR_HEIGHT_DIMENSION
    ]
    assert bar.x == spec.BAR_HEIGHT_X == fr_top_frame_spec.COLUMN_X
    x_m, y_m, _z = drawing.BAR_COLUMN_PICK_M
    assert x_m * 1000.0 == pytest.approx(fr_top_frame_spec.COLUMN_X)
    assert bar.y_high + 100.0 < y_m * 1000.0 < drawing.TOP_SCREW_Y - 100.0


def test_stud_drop_text_stands_east_of_the_east_column() -> None:
    # East is -x; the text's west end (half its ~80 mm of model width at 1:5)
    # must clear the column's outer face.
    column_face = -(fr_top_frame_spec.COLUMN_X + fr_tube_frame_spec.OUTER_DIA / 2.0)
    assert column_face == pytest.approx(-209.7024)  # the #290 7.756 column line
    half_width = len(notes.SETTING_CALLOUTS[spec.STUD_DROP_DIMENSION]) * 2.3 * 5 / 2
    assert drawing.STUD_DIMENSION_TEXT_MODEL_X_MM + half_width < column_face - 10.0


def test_steps_cover_the_sequence_and_print_no_setting_values() -> None:
    # Each keyed step prints under its own number, as one step or lettered
    # sub-steps (rule 22), so the numbers other sheets cite never move.
    for number, key in enumerate(steps.SEQUENCE, 1):
        lines = notes.step_lines(key)
        heads = [line.split(". ", 1)[0] for line in lines]
        if len(lines) == 1:
            assert heads == [str(number)]
        else:
            assert heads == [f"{number}{letter}" for letter in notes.SUB_STEP_LETTERS[: len(lines)]]
    assert notes.ASSEMBLY_STEPS == tuple(
        line for key in steps.SEQUENCE for line in notes.step_lines(key)
    )
    printed = " ".join(
        (*notes.ASSEMBLY_STEPS, *notes.ASSEMBLY_CHECKS, drawing.ASSEMBLED_NOTE)
    )
    # The settings live on the associative sheet-1 dimensions only, in
    # neither unit.
    for value in (spec.BAR_HEIGHT_MM, spec.STUD_DROP_MM):
        assert f"{value:.1f}" not in printed
        assert f"{value / 25.4:.{spec.SETTING_PRECISION}f}" not in printed
    # ASME decimal inch: no printed value keeps a millimetre leading zero.
    assert not re.search(r"(?<![\d.])0\.\d", printed)
    # Period hardware: no step leans on, or names, a chemical or nylon lock.
    for bad in ("TBD", "TODO", "THREADLOCK", "LOCTITE", "NYLON", "NYLOC"):
        assert bad not in printed
    # Rule 26: directions by view names, never a compass or a clock.
    assert not re.search(r"\b(NORTH|SOUTH|EAST|WEST)\b|O'CLOCK", printed)


def test_every_adjustable_clamp_step_checks_that_it_holds() -> None:
    """Rule 23: an adjustable clamp counts only with a step that sets it and
    checks it holds."""
    for key in ("summing-levelled", "magnifier-bar-clamped", "nib-set", "nib-on-paper"):
        lines = notes.step_lines(key)
        tightened = next(i for i, line in enumerate(lines) if "TIGHTEN" in line)
        assert lines[tightened + 1].split(". ", 1)[1].startswith("CHECK:")


def test_shared_vendor_instructions_print_current_numbers_and_roles() -> None:
    import _config

    clamp = " ".join(notes.step_lines("magnifier-bar-clamped"))
    pen_wire = " ".join(notes.step_lines("pen-wire-tied"))
    assert f"BOTH {_config.parts('sh-vn-clamp-screw')['number']} CLAMP SCREWS" in clamp
    assert _config.parts("sh-vn-music-wire")["number"] in pen_wire
    # Shared stock has no extra HA BOM row: each instruction must identify
    # its supplying assembly. MG's same-stock lever wire is not PN's wire.
    assert assembly_contract("mg-magnifier").number in clamp
    assert assembly_contract("pn-pen").number in pen_wire


def test_bar_height_names_the_raised_deck_it_runs_from() -> None:
    """#2060: the 20.86's extension line ends at the west column, short of the
    raised deck it is measured from (spec.DECK_TOP_Y is the base stack top),
    so the callout and step 8 name that surface."""
    import fr_harmonic_base_spec as base

    assert spec.DECK_TOP_Y == base.STACK_HEIGHT
    step = steps.step_number("magnifier-bar-clamped")
    callout = notes.SETTING_CALLOUTS[spec.BAR_HEIGHT_DIMENSION]
    assert callout.split("\n") == ["BAR TOP ABOVE", "RAISED DECK TOP", f"(STEP {step})"]
    assert "ABOVE THE RAISED DECK TOP (SHEET 1)" in " ".join(
        notes.step_lines("magnifier-bar-clamped")
    )


def test_the_loose_spare_sprocket_is_named_with_its_row_and_its_place() -> None:
    """Machinist review r1/r2 on 5bca52e13: the paper drive's spare sprocket
    lies loose on the deck (sheet 2) and beside item 7 (sheet 3) with no
    balloon, row or step. Sheet 3 labels it with its number and row; the
    paper-drive step names its supplier and where it stays."""
    import _config
    import pd_transgear_removable_spec as removable

    number = _config.parts("pd-transgear-removable")["number"]
    mounted = {removable.CRANK_CONFIG, removable.KNOB_CONFIG}
    assert notes.SPARE_SPROCKET_CONFIG in removable.TEETH
    assert notes.SPARE_SPROCKET_CONFIG not in mounted
    item = str(spec.BOM_ORDER.index("pd-paper-drive") + 1)
    assert drawing.BOM_PART_NUMBERS["pd-paper-drive"] == "MHA-PD-00"
    step = steps.step_number("paper-drive-built")
    label = notes.SPARE_SPROCKET_LABEL
    assert f"{number} {notes.SPARE_SPROCKET_CONFIG}" in label
    assert f"(ITEM {item}, STEP {step})" in label
    assert max(map(len, label.splitlines())) <= 16
    text = " ".join(notes.step_lines("paper-drive-built"))
    assert f"LOOSE {number} {notes.SPARE_SPROCKET_CONFIG} SPARE SPROCKET" in text
    assert "SHEET 2" in text and "SHEET 3" in text
    # The label's leader rides the paper drive's explode.
    assert drawing.PAPER_DRIVE_EXPLODE_M == pytest.approx((0.0, 0.0, -0.450))


def test_the_spare_label_moves_off_a_balloon_that_lands_on_it() -> None:
    """Run 20261028T091118034Z (1e2b7b540): item 7's balloon moved into the
    label's first place and its leader ran 4.56 mm through the text. The
    label read back from run 20261028T041950158Z (its three lines, leader
    start and tip) keeps its first place beside that run's balloons and
    moves clear of the moved one."""
    from _layout_geometry import Box, Segment

    mm = 0.001
    tip = (93.28 * mm, 140.31 * mm)
    placed = (35.28 * mm, 136.31 * mm)
    boxes = [
        Box(35.28 * mm, y * mm, (35.28 + width) * mm, (y + 3.5) * mm)
        for y, width in ((131.79, 33.89), (127.26, 38.18), (122.74, 33.20))
    ]
    leader_start = (73.58 * mm, 125.94 * mm)
    balloon_6 = (
        (40.62 * mm, 151.03 * mm, 5.23 * mm),
        Segment(44.58 * mm, 152.93 * mm, 99.19 * mm, 188.84 * mm),
    )
    balloon_8 = (
        (93.0 * mm, 89.5 * mm, 5.23 * mm),
        Segment(93.24 * mm, 93.03 * mm, 96.54 * mm, 119.42 * mm),
    )
    old_7 = (
        (80.5 * mm, 95.8 * mm, 5.23 * mm),
        Segment(82.41 * mm, 100.65 * mm, 100.23 * mm, 146.64 * mm),
    )
    moved_7 = (
        (52.4 * mm, 124.8 * mm, 5.23 * mm),
        Segment(55.7 * mm, 128.9 * mm, 84.6 * mm, 165.1 * mm),
    )

    def place(*balloons):
        circles = [circle for circle, _leader in balloons]
        leaders = [leader for _circle, leader in balloons]
        return drawing.spare_label_offset(
            tip, placed, boxes, leader_start, circles, leaders
        )

    offset, airs = place(balloon_6, old_7, balloon_8)
    assert offset == drawing.SPARE_LABEL_OFFSETS[0]
    offset, airs = place(balloon_6, moved_7, balloon_8)
    assert airs[0] == 0.0
    assert offset is not None and offset != drawing.SPARE_LABEL_OFFSETS[0]
    assert airs[-1] >= drawing.SPARE_LABEL_CLEARANCE


def test_the_parked_nib_is_set_on_the_paper_before_the_line_check() -> None:
    """Code review C08: the model and the feeler step park the nib
    PEN_PAPER_CLEARANCE_MM off the paper, and nothing on the plumb, guided
    carriage closes that gap, yet check 3 needs a drawn line. The fitter
    slides the marker on in its V until the nib touches, after the parking
    step and before any check; sheet 1 says the views show it parked."""
    from _recording_geometry import PEN_PAPER_CLEARANCE_MM

    parked, contact = steps.step_number("nib-set"), steps.step_number("nib-on-paper")
    assert contact == parked + 1
    parked_text = " ".join(notes.step_lines("nib-set"))
    contact_text = " ".join(notes.step_lines("nib-on-paper"))
    # The modelled gap in the sheet's inch: the stock .010 leaf, within
    # half a .001 count of the model's 0.25.
    assert notes.NIB_CLEARANCE_TEXT == ".010"
    assert abs(0.010 * 25.4 - PEN_PAPER_CLEARANCE_MM) <= 0.0005 * 25.4
    feeler = f"A {notes.NIB_CLEARANCE_TEXT} FEELER"
    assert feeler in parked_text
    assert "TOUCHES THE PAPER" in contact_text
    assert "FEELER" not in contact_text
    # No later step re-parks the nib, and the checks find it on the paper
    # before the straight-line run.
    for key in steps.SEQUENCE[steps.SEQUENCE.index("nib-on-paper") + 1 :]:
        assert "NIB" not in " ".join(notes.step_lines(key))
    checks = " ".join(notes.ASSEMBLY_CHECKS)
    assert "FEELER" not in checks
    nib = next(i for i, c in enumerate(notes.ASSEMBLY_CHECKS) if "THE NIB TOUCHES THE PAPER" in c)
    line = next(i for i, c in enumerate(notes.ASSEMBLY_CHECKS) if "DRAW A STRAIGHT LINE" in c)
    assert nib < line
    assert notes.NIB_PARKED_NOTE in drawing.ASSEMBLED_NOTE.replace("\n", " ")
    assert (
        f"PARKED {notes.NIB_CLEARANCE_TEXT} OFF THE PAPER (STEP {parked}); "
        f"STEP {contact} SETS IT ON."
    ) in notes.NIB_PARKED_NOTE
    lines = drawing.ASSEMBLED_NOTE.count("\n") + 1
    portrait = DRAWING_TEMPLATES[DrawingLayout.PORTRAIT]
    bottom = drawing.ASSEMBLED_NOTE_XY[1] - lines * drawing.NOTE_LINE_PITCH
    assert bottom > portrait.title_block_top_m
    assert max(map(len, drawing.ASSEMBLED_NOTE.splitlines())) <= (
        drawing.ASSEMBLED_NOTE_WIDTH
    )


def test_integration_joints_point_at_their_integration_steps() -> None:
    rows = {joint.id: joint for joint in joint_retention.JOINTS}
    anchor = rows["ha-harmonic-analyzer/channel-anchor-in-summing-plate"]
    assert anchor.installed_at == steps.step_ref("channel-anchors-set")
    assert anchor.lock is joint_retention.Lock.NONE
    bracket = rows["ha-harmonic-analyzer/magnifying-bracket-screws"]
    assert bracket.installed_at == steps.step_ref("magnifier-bracket-screwed")


def test_channel_sheet_cites_the_anchor_step_by_its_number() -> None:
    # MHA-CH-00 prints this pointer as a literal (its steps module sits below
    # this one in the stack); a reorder here must move it too.
    assert ch_channel_assembly_steps.HA_ANCHORS_SET_REF == steps.step_ref(
        "channel-anchors-set"
    )


def test_steps_sheet_text_clears_the_title_block() -> None:
    landscape = DRAWING_TEMPLATES[DrawingLayout.LANDSCAPE]
    assert drawing.STEPS_COLUMN_BOTTOM_Y > landscape.title_block_top_m
    for block in (*drawing.STEP_COLUMNS, drawing.ASSEMBLY_CHECKS):
        assert max(map(len, block.splitlines())) <= drawing.STEPS_LINE_WIDTH
    # Sheet 4 carries two columns, sheet 5 the rest; the checks sit in sheet
    # 5's right half, below any step column there.
    count = len(drawing.STEP_COLUMNS)
    assert drawing.STEP_COLUMN_SHEETS == (
        drawing.SHEET_NAMES[3],
        drawing.SHEET_NAMES[3],
        *(drawing.SHEET_NAMES[4],) * (count - 2),
    )
    assert drawing.CHECKS_XY[0] == drawing.STEPS_RIGHT_X
    for block, sheet, (x, y) in zip(
        drawing.STEP_COLUMNS, drawing.STEP_COLUMN_SHEETS, drawing.STEP_COLUMN_XY
    ):
        if sheet == drawing.SHEET_NAMES[4] and x == drawing.CHECKS_XY[0]:
            block_bottom = y - drawing.NOTE_LINE_PITCH * len(block.splitlines())
            assert drawing.CHECKS_XY[1] < block_bottom


def test_a_blank_line_separates_each_numbered_step() -> None:
    """A blank line between numbered steps; a step's lettered sub-steps stay
    together, and a step never splits across columns."""
    printed = []
    for block in (*drawing.STEP_COLUMNS, drawing.ASSEMBLY_CHECKS):
        lines = block.splitlines()
        starts = [i for i, line in enumerate(lines) if line[:1].isdigit()]
        assert starts[0] == 1  # the heading, then no blank line
        numbers = [re.match(r"\d+", lines[i]).group(0) for i in starts]
        for previous, index, number in zip(numbers, starts[1:], numbers[1:]):
            assert (lines[index - 1] == "") == (number != previous)
        assert lines.count("") == len(set(numbers)) - 1
        if block is not drawing.ASSEMBLY_CHECKS:
            printed += [lines[i].split(". ", 1)[0] for i in starts]
    assert printed == [line.split(". ", 1)[0] for line in notes.ASSEMBLY_STEPS]


@pytest.mark.parametrize("axis", ((0.0, -1.0, 0.0), (0.0, 1.0, 0.0),
                                (0.6, -0.8, 0.0), (0.0, -0.8, 0.6)))
def test_native_ha_final_guard_uses_nested_screw_root_transform(monkeypatch, axis) -> None:
    monkeypatch.setattr(builder, "_early_bound", lambda value, interface: value)
    screw = SimpleNamespace(
        Name2=f"ms-measuring-stick-1/{ms.THUMB_SCREW}-1",
        GetPathName=lambda: f"C:/models/{ms.THUMB_SCREW}.SLDPRT",
        Transform2=SimpleNamespace(
            ArrayData=(*axis, 1, 0, 0, 0, 0, 1, 10, 20, 30, 1)
        ),
    )

    # Other children are ignored; applying the parent's rotation a second time
    # would corrupt the correct root-frame axis supplied by Transform2.
    other = SimpleNamespace(
        Name2=f"ms-measuring-stick-1/{ms.STICK}-1",
        GetPathName=lambda: f"C:/models/{ms.STICK}.SLDPRT",
    )
    component = SimpleNamespace(GetChildren=lambda: (other, screw))
    adapter = SimpleNamespace(
        currentModel=SimpleNamespace(GetComponentByName=lambda instance: component)
    )
    if axis == (0.0, -1.0, 0.0):
        builder._assert_ms_working_pose(adapter, "ms-measuring-stick-1")
    else:
        with pytest.raises(RuntimeError, match="thumbscrew head must be above"):
            builder._assert_ms_working_pose(adapter, "ms-measuring-stick-1")


@pytest.mark.parametrize("defect", ("missing instance", "missing screw", "duplicate screw",
                                  "missing transform"))
def test_native_ha_final_guard_rejects_unresolved_nested_screw(monkeypatch, defect) -> None:
    monkeypatch.setattr(builder, "_early_bound", lambda value, interface: value)
    screw = SimpleNamespace(
        Name2=f"ms-measuring-stick-1/{ms.THUMB_SCREW}-1",
        GetPathName=lambda: f"C:/models/{ms.THUMB_SCREW}.SLDPRT",
        Transform2=None,
    )
    children = () if defect == "missing screw" else (screw,)
    if defect == "duplicate screw":
        children = (screw, screw)
    component = None if defect == "missing instance" else SimpleNamespace(GetChildren=lambda: children)
    adapter = SimpleNamespace(
        currentModel=SimpleNamespace(GetComponentByName=lambda instance: component)
    )
    message = {
        "missing instance": "missing measuring-stick instance",
        "missing screw": "expected one measuring-stick thumbscrew, got 0",
        "duplicate screw": "expected one measuring-stick thumbscrew, got 2",
        "missing transform": "missing measuring-stick thumbscrew transform",
    }[defect]
    with pytest.raises(RuntimeError, match=message):
        builder._assert_ms_working_pose(adapter, "ms-measuring-stick-1")
