"""Offline contract for the complete-machine fitter package (MHA-HA-00)."""

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
import ch_vn_spring_hook_spec
import ms_measuring_stick_assembly_spec as ms
from _assembly_contract import assembly_contract
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME, DrawingLayout


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
    assert column_face == pytest.approx(-209.7)
    half_width = len(notes.SETTING_CALLOUTS[spec.STUD_DROP_DIMENSION]) * 2.3 * 5 / 2
    assert drawing.STUD_DIMENSION_TEXT_MODEL_X_MM + half_width < column_face - 10.0


def test_steps_cover_the_sequence_and_print_no_setting_values() -> None:
    assert len(notes.ASSEMBLY_STEPS) == len(steps.SEQUENCE)
    for number, line in enumerate(notes.ASSEMBLY_STEPS, 1):
        assert line.startswith(f"{number}. ")
    printed = " ".join(
        (*notes.ASSEMBLY_STEPS, *notes.ASSEMBLY_CHECKS, drawing.ASSEMBLED_NOTE)
    )
    # The settings live on the associative sheet-1 dimensions only.
    for value in (spec.BAR_HEIGHT_MM, spec.STUD_DROP_MM):
        assert f"{value:.1f}" not in printed
    assert "PER MHA-MG-00 SHEET 4." in printed
    # Period hardware: no step leans on, or names, a chemical or nylon lock.
    for bad in ("TBD", "TODO", "THREADLOCK", "LOCTITE", "NYLON", "NYLOC"):
        assert bad not in printed
    # The anchor's install and acceptance are the anchor spec's text, unforked.
    assert ch_vn_spring_hook_spec.ANCHOR_INSTALL_STEP in printed
    assert ch_vn_spring_hook_spec.ANCHOR_INSTALL_CHECK in printed


def test_the_parked_nib_is_set_on_the_paper_before_the_line_check() -> None:
    """Code review C08: the model and the feeler step park the nib
    PEN_PAPER_CLEARANCE_MM off the paper, and nothing on the plumb, guided
    carriage closes that gap, yet check 3 needs a drawn line. The fitter
    slides the marker on in its V until the nib touches, after the parking
    step and before any check; sheet 1 says the views show it parked."""
    from _recording_geometry import PEN_PAPER_CLEARANCE_MM

    parked, contact = steps.step_number("nib-set"), steps.step_number("nib-on-paper")
    assert contact == parked + 1
    by_number = {
        int(line.split(". ", 1)[0]): line for line in notes.ASSEMBLY_STEPS
    }
    feeler = f"{PEN_PAPER_CLEARANCE_MM:.2f} FEELER"
    assert feeler in by_number[parked]
    assert "TOUCHES THE PAPER" in by_number[contact]
    assert "FEELER" not in by_number[contact].replace("NO FEELER", "")
    assert f"REPEAT STEP {parked}" in by_number[contact]
    # No later step re-parks the nib, and the checks find it on the paper
    # before the straight-line run.
    for number in range(contact + 1, len(notes.ASSEMBLY_STEPS) + 1):
        assert "NIB" not in by_number[number]
    checks = " ".join(notes.ASSEMBLY_CHECKS)
    assert "FEELER" not in checks
    assert "THE NIB TOUCHES THE PAPER" in notes.ASSEMBLY_CHECKS[0]
    assert "DRAW A STRAIGHT LINE" in notes.ASSEMBLY_CHECKS[2]
    assert notes.NIB_PARKED_NOTE in drawing.ASSEMBLED_NOTE.replace("\n   ", " ")
    assert (
        f"PARKED {PEN_PAPER_CLEARANCE_MM:.2f} OFF THE PAPER (STEP {parked}); "
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
    nut = rows["ha-harmonic-analyzer/channel-anchor-jam-nut-on-anchor"]
    step = steps.step_ref("channel-anchors-set")
    assert anchor.installed_at == anchor.lock_step == nut.installed_at == step
    assert anchor.lock is joint_retention.Lock.JAM_NUT
    assert anchor.lock_part == nut.member == "ch_anchor_jam_nut"
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
    for block in (drawing.STEPS_LEFT, drawing.STEPS_RIGHT, drawing.ASSEMBLY_CHECKS):
        assert max(map(len, block.splitlines())) <= drawing.STEPS_LINE_WIDTH


def test_parked_stick_instruction_requires_the_approved_working_pose() -> None:
    number = steps.step_number("stick-parked")
    instruction = notes.ASSEMBLY_STEPS[number - 1]
    assert instruction.startswith(f"{number}. ")
    assert "THUMBSCREW ABOVE THE STICK" in instruction
    assert "STICK FRONT TO REAR" in instruction
    assert "CENTRED FRONT TO REAR" in instruction
    assert "MHA-FR-01 AS-CAST TOP" in instruction
    assert "RAISED DECK'S EAST EDGE AND THE EAST COLUMNS" in instruction
    printed = " ".join((*notes.ASSEMBLY_STEPS, *notes.ASSEMBLY_CHECKS, drawing.ASSEMBLED_NOTE))
    assert "GRADUATIONS UP" not in printed
    assert "GRADUATIONS-UP" not in printed


@pytest.mark.parametrize("axis", ((0.0, -1.0, 0.0), (0.0, 1.0, 0.0),
                                (0.6, -0.8, 0.0), (0.0, -0.8, 0.6)))
def test_native_ha_final_guard_uses_nested_screw_root_transform(monkeypatch, axis) -> None:
    monkeypatch.setattr(builder, "_early_bound", lambda value, interface: value)
    transform_reads = []

    class Screw:
        def GetPathName(self):
            return f"C:/models/{ms.THUMB_SCREW}.SLDPRT"

        @property
        def Transform2(self):
            transform_reads.append(True)
            return SimpleNamespace(ArrayData=(*axis, 1, 0, 0, 0, 0, 1, 10, 20, 30, 1))

    # Other children are ignored; applying the parent's rotation a second time
    # would corrupt the correct root-frame axis supplied by Transform2.
    other = SimpleNamespace(GetPathName=lambda: f"C:/models/{ms.STICK}.SLDPRT")
    component = SimpleNamespace(GetChildren=lambda: (other, Screw()))

    def get_component(instance):
        assert instance == "ms-measuring-stick-1"
        return component

    adapter = SimpleNamespace(currentModel=SimpleNamespace(GetComponentByName=get_component))
    if axis == (0.0, -1.0, 0.0):
        builder._assert_ms_working_pose(adapter, "ms-measuring-stick-1")
    else:
        with pytest.raises(RuntimeError, match="thumbscrew head must be above"):
            builder._assert_ms_working_pose(adapter, "ms-measuring-stick-1")
    assert transform_reads == [True]


@pytest.mark.parametrize("defect", ("missing instance", "missing screw", "duplicate screw",
                                  "missing transform"))
def test_native_ha_final_guard_rejects_unresolved_nested_screw(monkeypatch, defect) -> None:
    monkeypatch.setattr(builder, "_early_bound", lambda value, interface: value)
    screw = SimpleNamespace(
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
