"""Offline contract for the drive-train assembly package and its explode plan."""

from __future__ import annotations

import ast
import itertools
import math
import re
from pathlib import Path
from types import SimpleNamespace

import _config
import _general_table as general_table
import cone_line
import cylinder_bank_layout as bank_layout
import dt_cone_gear_spec as cone_spec
import pytest

import dt_crank_handle_pivot_screw_spec as screw_spec
import dt_crank_handle_spec as handle_spec
import draw_dt_drive_train_assembly as drawing
import dt_drive_train_assembly_spec as spec
from _assembly_contract import assembly_contract
from _drawing_registry import DRAWINGS_BY_NAME

SCRIPTS = Path(__file__).resolve().parent
PARTS = SCRIPTS.parent / "config" / "parts"
BUILDER = SCRIPTS / "build_dt_drive_train_assembly.py"
SCREW_STEM = "sh-vn-fillister-screw-90280a108"
# Deliberately not role-local ordinal 1: native allocation is unrelated.
STOP_NAME = f"{SCREW_STEM}__SwingStopScrew-9"
FOOT_NAME = f"{SCREW_STEM}__FootScrew-42"
# The rig's steps at the built assembly's counts.
RIG_STEPS = drawing.rig_steps(pivot_blocks=2, cams=2, slotted=4)
# Installation interfaces the package may cite without owning a BOM row.
# Step 10 sets the channel's north MHA-CH-08 on the frame's MHA-FR-05 (#936 P1 b).
EXTERNAL_NUMBERS = frozenset(
    {
        "MHA-FR-01",
        "MHA-FR-05",
        "MHA-CH-08",
        drawing.NORTH_BRACKET_SCREW,
        # Step 5's paper-drive T12, named on sheet 12's interface line.
        drawing.CRANK_CHAIN_WHEEL,
        # Step 8A's MHA-CH-00 connecting rod and rocker arm pairs.
        drawing.CONNECTING_ROD,
        drawing.ROCKER_ARM,
        # Check 5's feed sense, named on sheet 15's interface lines.
        drawing.PLATEN_NUMBER,
        # Steps 1T and 2C's phasing comb: a shop tool in the cone-gear indexing kit,
        # never a drive-train BOM row (owner ruling 2026-11-09, PR #1992).
        _config.parts("dt-cone-gear-tl-phasing-comb")["number"],
    }
)
# Named installation assemblies are external interfaces, not drive-train BOM rows.
EXTERNAL_NUMBERS |= frozenset(
    assembly_contract(stem).number
    for stem in ("fr-frame", "ch-channel", "pd-paper-drive")
)


def _builder_stems() -> set[str]:
    """Every family the builder inserts: place_component / _place_on_shaft stems."""
    tree = ast.parse(BUILDER.read_text(encoding="utf-8"))
    stems = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = getattr(node.func, "id", getattr(node.func, "attr", ""))
        if name not in {"place_component", "_place_on_shaft"} or len(node.args) < 2:
            continue
        arg = node.args[1]
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            stems.add(arg.value)
    return stems


def _instances(**overrides) -> list[spec.Instance]:
    """Synthetic presentation census; live bank/cone grids supply their counts."""
    drum_x, drum_y = cone_line.X_DRUM, cone_line.Y_DRIVE
    layout = {
        "dt-cylinder-gear-shaft": [(drum_x, drum_y, bank_layout.ARBOR_SOUTH_Z)],
        "dt-arbor-pedestal": [
            (drum_x, cone_line.Y_BASE_TOP, z)
            for z in (
                bank_layout.FRONT_PEDESTAL_ORIGIN_Z,
                bank_layout.BACK_PEDESTAL_ORIGIN_Z,
            )
        ],
        "dt-cylinder-end-disc": [(drum_x, drum_y, bank_layout.SOUTH_DISC_Z[0])],
        "dt-vn-cylinder-bank-spring": [(drum_x, drum_y, bank_layout.BANK_SPRING_Z[0])],
        "sh-vn-arbor-set-screw": [
            (drum_x, drum_y, z)
            for z in (bank_layout.FRONT_SET_SCREW_Z, bank_layout.BACK_SET_SCREW_Z)
        ],
        "dt-cylinder-gear": [
            (drum_x, drum_y, bank_layout.station_z(j)) for j in range(bank_layout.COUNT)
        ],
        SCREW_STEM: [(0.0, cone_line.Y_BASE_TOP, 0.0), (7.49, 52.0, 74.0)],
        "dt-vn-pedestal-hold-down-screw": [
            (drum_x, 55.8, -91.652),
            (drum_x, 55.8, 94.202),
        ],
        "dt-vn-slotted-screw": [
            (-19.4, 60.0, -94.9),
            (7.6, 60.0, -94.9),
            (-19.4, 60.0, 85.1),
            (7.6, 60.0, 85.1),
        ],
        "dt-cone-gear": [
            (cone_line.cone_seat(j)[0], drum_y, cone_line.cone_seat(j)[1])
            for j in range(len(cone_spec.CONFIGURATION_TEETH))
        ],
        "dt-pinion-bracket": [(-12.1, 62.8, -72.0), (-12.1, 62.8, 71.0)],
        "dt-pinion-pivot-block": [(-5.9, 62.8, -95.0), (-5.9, 62.8, 85.0)],
        "dt-pinion-cam-pin": [(-8.0, 70.0, -72.0), (-8.0, 70.0, 71.0)],
        "dt-pinion-cam": [(0.4, 64.7, -72.0), (0.4, 64.7, 71.0)],
        # Two strap set pins, then the collar pin (the builder's insertion order).
        "dt-vn-pinion-strap-pin": [(-12.1, 62.8, -74.0), (-12.1, 62.8, 81.0), (-18.4, 90.5, -127.0)],
    }
    layout.update(overrides)
    roles = {
        "dt-vn-pinion-strap-pin-3": spec.COLLAR_PIN_ROLE,
        STOP_NAME: spec.SWING_STOP_SCREW_ROLE,
        FOOT_NAME: spec.FOOT_SCREW_ROLE,
    }
    instances = []
    for stem in sorted(_builder_stems() | set(layout)):
        for index, origin in enumerate(layout.get(stem, [(0.0, 100.0, 0.0)]), start=1):
            name = f"{stem}-{index}"
            if stem == SCREW_STEM:
                name = (STOP_NAME, FOOT_NAME)[index - 1]
            instances.append(spec.Instance(name, stem, origin, roles.get(name)))
    return instances


def _drawing_facts() -> drawing.SourceFacts:
    instances = _instances()
    cones = [i.name for i in instances if i.stem == "dt-cone-gear"]
    configurations = {
        name: f"T{teeth:03d}"
        for name, teeth in zip(
            cones, reversed(cone_spec.CONFIGURATION_TEETH), strict=True
        )
    }
    return drawing.SourceFacts(instances, configurations)


def test_registry_row_and_outputs() -> None:
    row = DRAWINGS_BY_NAME["dt_drive_train_assembly"]
    assert row.source_kind == "assembly" and row.part == "dt_drive_train"
    assert drawing.SOURCE == row.source
    assert drawing.OUTPUTS.pdf == row.outputs["pdf"]


def test_every_builder_family_has_a_bom_identity_and_a_cluster() -> None:
    stems = _builder_stems()
    assert stems, "builder census found no place_component stems"
    assert stems <= set(drawing.BOM_PART_NUMBERS)
    assert stems <= spec.classified_stems()
    assert not stems & spec.RETIRED_STEMS


def test_bom_part_numbers_match_the_parts_registry() -> None:
    for stem, number in drawing.BOM_PART_NUMBERS.items():
        path = PARTS / f"{stem}.yaml"
        if not path.exists():
            assert stem in spec.PENDING_STEMS, f"{stem} has no registry row"
            continue
        row = _config.parts(stem)
        assert row["number"] == number, stem


def test_bom_catalog_numbers_match_the_parts_registry() -> None:
    """A vendor number in a BOM description is the registry's SKU, and every
    registry SKU is printed: a re-sourced fastener cannot leave a stale row."""
    for stem, text in drawing.BOM_DESCRIPTIONS.items():
        path = PARTS / f"{stem}.yaml"
        if not path.exists():
            continue
        skus = _config.parts(stem).get("supplier_skus")
        printed = re.findall(r"\b(?:MCMASTER|MSC) (\S+)$", text)
        if not skus:
            assert not printed, stem
            continue
        assert printed == [skus[0]], stem


def test_package_text_cites_only_bom_or_external_part_numbers() -> None:
    texts = (
        drawing.ASSEMBLED_HEADING,
        drawing.CONE_CRANK_STEPS,
        drawing.BANK_STEPS,
        RIG_STEPS,
        drawing.CHECKS,
        drawing.SETUP_NOTES,
        drawing.INTERFACE_NOTES,
        drawing.DIRECTION_NOTES,
        *drawing.BOM_DESCRIPTIONS.values(),
    )
    cited = set(re.findall(r"MHA-(?!VN-)[A-Z]{2}-(?:[0-9]{2}(?:-TL-(?:[0-9]{2}|VN-[5-9][0-9]))?|VN-[5-9][0-9])(?:-T[0-9]{3})?(?![A-Z0-9-])", "\n".join(texts)))
    bom = set(drawing.BOM_PART_NUMBERS.values())
    assert cited <= bom | EXTERNAL_NUMBERS


def test_note_lines_fit_a_half_sheet_field() -> None:
    """The actual note producer stays inside the unchanged 70-character budget."""
    for field in drawing.package_note_fields(_drawing_facts()):
        for label, text in field.blocks:
            for line in text.splitlines():
                assert len(line) <= 70, (field.label, label, line)


def _stacked_height(blocks: tuple[tuple[str, str], ...]) -> float:
    """Blocks stacked in one field (metres): NOTE_LINE_PITCH a rendered line,
    NOTE_FIELD_INSET above each block (the anchor target), NOTE_BLOCK_GAP
    between blocks."""
    lines = sum(len(text.splitlines()) for _label, text in blocks)
    return (
        lines * drawing.NOTE_LINE_PITCH
        + len(blocks) * drawing.NOTE_FIELD_INSET
        + (len(blocks) - 1) * drawing.NOTE_BLOCK_GAP
    )


def _spare(field: drawing.NoteField) -> float:
    return field.bounds[1] - field.bounds[3] - _stacked_height(field.blocks)


def test_every_note_field_holds_its_stacked_blocks() -> None:
    """Every produced block fits its field at the native-measured line pitch."""
    for field in drawing.package_note_fields(_drawing_facts()):
        assert _spare(field) >= 0, (field.label, _spare(field))


def test_the_package_prints_each_numbered_assembly_step_once() -> None:
    import dt_drive_train_steps as steps

    numbers = [
        int(number)
        for field in drawing.package_note_fields(_drawing_facts())
        if field.sheet in (
            drawing.SEQUENCE_SHEET,
            drawing.CRANK_SHEET,
            drawing.BANK_SHEET,
            drawing.FIT_SHEET,
            drawing.CONTINUATION_SHEET,
        )
        for _label, text in field.blocks
        for number in re.findall(r"^(\d+)\. ", text, re.MULTILINE)
    ]
    assert sorted(numbers) == list(range(1, len(steps.SEQUENCE) + 1))


def test_sheet_numbers_are_pinned_where_the_sheets_cite_them() -> None:
    names = drawing.SHEET_NAMES
    assert (
        drawing.SEQUENCE_SHEET,
        drawing.CRANK_SHEET,
        drawing.BANK_SHEET,
        drawing.FIT_SHEET,
        drawing.CONTINUATION_SHEET,
        drawing.FULL_DETAIL_SHEET,
        drawing.CHECKS_SHEET,
        drawing.BANK_SETTINGS_SHEET,
    ) == (7, 8, 9, 10, 11, 12, 13, 14), "the numbered steps read in sheet order"
    assert len(names) == drawing.ACCEPTANCE_SHEET == drawing.SETTING_SHEET + 1
    assert drawing.SETTING_SHEET == drawing.BANK_SETTINGS_SHEET + 1
    assert names[drawing.FULL_DETAIL_SHEET - 1] == "FULL-DETAIL SIDE VIEW"
    assert f"FULL DETAIL: SHEET {drawing.FULL_DETAIL_SHEET}." in drawing.ASSEMBLED_HEADING
    assert names[drawing.SEQUENCE_SHEET - 1] == "ASSEMBLY SEQUENCE"
    assert names[drawing.CRANK_SHEET - 1] == "ASSEMBLY SEQUENCE CONT. - CONE SET + CRANK"
    assert names[drawing.BANK_SHEET - 1] == "ASSEMBLY SEQUENCE CONT. - CRANK + CYLINDER BANK"
    assert names[drawing.CHECKS_SHEET - 1] == "CHECKS + SETUP"
    assert names[drawing.FIT_SHEET - 1] == "ASSEMBLY SEQUENCE CONT. - CYLINDER BANK + PINION RIG"
    assert names[drawing.BANK_SETTINGS_SHEET - 1] == "CYLINDER BANK + MHA-DT-01 STATION SETTINGS"
    assert names[drawing.SETTING_SHEET - 1] == "SETTING TABLES + CONE STATIONS"
    assert names[drawing.ACCEPTANCE_SHEET - 1] == "SETTING TABLE CONT. - FITS AND ACCEPTANCES"
    assert sorted(drawing.CLUSTER_SHEETS.values()) == [3, 4, 5, 6]
    assert set(drawing.SHEET_SCALES) == set(names)
    assert "BALLOONS ON SHEETS 3-6" in drawing.BOM_REFERENCE_NOTES
    assert f"STATIONS: SHEET {drawing.SETTING_SHEET}" in drawing.BOM_REFERENCE_NOTES
    fields = {field.label: field for field in drawing.package_note_fields(_drawing_facts())}
    sequence_right = fields[f"sheet {drawing.SEQUENCE_SHEET} right note field"].blocks[-1][1]
    assert sequence_right.endswith(
        f"CONT. STEP {drawing.CRANK_SHEET_FROM}: SHEET {drawing.CRANK_SHEET}."
    )
    crank_right = fields[f"sheet {drawing.CRANK_SHEET} right note field"].blocks[-1][1]
    assert crank_right.endswith(
        f"CONT. STEP {drawing.CRANK_CONTINUED_FROM}: SHEET {drawing.BANK_SHEET}."
    )
    # MHA-PD-00 cites steps 4 and 5 on the crank sheet: both print whole there.
    def sequence(sheets: set[int]) -> str:
        return "\n".join(
            text
            for field in fields.values()
            if field.sheet in sheets
            for _label, text in field.blocks
        )

    others = {
        drawing.SEQUENCE_SHEET,
        drawing.BANK_SHEET,
        drawing.FIT_SHEET,
        drawing.CONTINUATION_SHEET,
    }
    crank = sequence({drawing.CRANK_SHEET})
    for key in ("crank-mesh-checked", "paper-drive-wheel"):
        number = drawing.steps.step_number(key)
        assert re.search(rf"^{number}\. ", crank, re.MULTILINE), key
        assert not re.search(rf"^{number}[A-Z]?\. ", sequence(others), re.MULTILINE)
    assert all(text.count(",") <= 1 for text in drawing.BOM_DESCRIPTIONS.values())


def test_grouped_parts_stamp_the_description_the_bom_prints() -> None:
    """A grouped part's configurations carry UseDescriptionInBOM, and that
    wins over the drawing's written cell: cascade-2 (2026-09-27) read back
    MHA-DT-30's 'Pinion Lever Cross Pin' after SetText2 wrote its BOM text.  So
    the builder stamps the registry description, and it must already be the
    text the BOM prints (cone-gear's always was)."""
    grouped = [
        build
        for build in sorted(SCRIPTS.glob("build_*.py"))
        if "apply_grouped_bom_properties(" in build.read_text(encoding="utf-8")
    ]
    assert grouped, "no grouped-BOM builders found"
    printed = []
    for build in grouped:
        stem = build.stem.removeprefix("build_").replace("_", "-")
        source = build.read_text(encoding="utf-8")
        tree = ast.parse(source)
        stamped = [
            ast.get_source_segment(source, keyword.value)
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and getattr(node.func, "id", None) == "apply_grouped_bom_properties"
            for keyword in node.keywords
            if keyword.arg == "description"
        ]
        # The builder passes a local it read from the row, or the row read inline.
        assert stamped, build.name
        assert all("title" not in text for text in stamped), (build.name, stamped)
        assert re.search(r"""\(["']description["']""", source) or re.search(
            r"""\[["']description["']\]""", source
        ), build.name
        if stem not in drawing.BOM_DESCRIPTIONS:
            continue
        row = _config.parts(stem)
        assert row.get("description") == drawing.BOM_DESCRIPTIONS[stem], stem
        printed.append(stem)
    assert {"dt-cone-gear", "dt-pinion-lever-pin"} <= set(printed)


def test_pinion_cam_thread_matches_its_supplied_hardware() -> None:
    import dt_pinion_cam_geometry as cam

    designation = f"{cam.SET_SCREW_HOLE_SPEC.size} SET SCREW"
    description = drawing.BOM_DESCRIPTIONS["dt-pinion-cam"]
    fit_up = _rig_step_body("cams-and-lever-fitted")
    assert designation in description
    assert designation in fit_up
    assert "M2.5" not in description + fit_up
    assert "(SUPPLIED WITH MHA-DT-23) LOOSE" in fit_up


def test_bom_descriptions_keep_one_line() -> None:
    for stem, text in drawing.BOM_DESCRIPTIONS.items():
        assert len(text) <= drawing.BOM_DESCRIPTION_MAX_CHARS, stem


def test_shared_screws_combine_quantity_without_merging_operational_roles() -> None:
    facts = _drawing_facts()
    assert drawing.BOM_PART_NUMBERS[SCREW_STEM] == "MHA-SH-VN-52"
    assert "90280A108" in drawing.BOM_DESCRIPTIONS[SCREW_STEM]
    assert facts.components.count(SCREW_STEM) == 1
    assert facts.count(SCREW_STEM) == 2
    assert facts.role_count(spec.SWING_STOP_SCREW_SELECTOR) == 1
    assert facts.role_count(spec.FOOT_SCREW_SELECTOR) == 1
    assert STOP_NAME in facts.clusters["cone-set"]
    assert FOOT_NAME not in facts.clusters["cone-set"]
    assert FOOT_NAME in facts.clusters["pinion-rig"]
    assert STOP_NAME not in facts.clusters["pinion-rig"]
    moved = {step.label: names for step, names in spec.plan_explode(facts.instances)}
    assert moved["swing stop lifts"] == (STOP_NAME,)
    assert moved["spring foot screw lifts"] == (FOOT_NAME,)
    assert FOOT_NAME in moved["pivot blocks drop"]
    assert STOP_NAME not in moved["pivot blocks drop"]
    for cluster, selector in (
        ("cone-set", spec.SWING_STOP_SCREW_SELECTOR),
        ("pinion-rig", spec.FOOT_SCREW_SELECTOR),
    ):
        assert drawing.DRIVE_TRAIN_BALLOON_ANCHORS[cluster][SCREW_STEM].instance == selector


@pytest.mark.parametrize("shared_quantity", [2, 1])
def test_native_bom_requires_the_combined_screw_quantity(
    monkeypatch: pytest.MonkeyPatch, shared_quantity: int,
) -> None:
    facts = _drawing_facts()

    class Table:
        def __init__(self):
            self.cells = [["ITEM NO.", "PART NUMBER", "DESCRIPTION", "QTY."]]
            self.cells.extend(
                [
                    str(index), stem, drawing.BOM_DESCRIPTIONS[stem],
                    str(shared_quantity if stem == SCREW_STEM else facts.count(stem)),
                ]
                for index, stem in enumerate(facts.components, start=1)
            )
            self.RowCount = len(self.cells)
            self.ColumnCount = 4
            self.heights = {}

        def DisplayedText(self, row, column):
            return self.cells[row][column]

        def DisplayedText2(self, row, column, _include_hidden):
            return self.cells[row][column]

        def SetColumnWidth(self, _column, width, _options):
            return width

        def IsCellTextEditable(self, _row, _column):
            return True

        def SetText2(self, row, column, _include_hidden, value):
            self.cells[row][column] = value

        def GetHeaderCount(self):
            return 1

        def SetRowHeight(self, row, height, _options):
            self.heights[row] = height
            return height

        def GetRowHeight(self, row):
            return self.heights[row]

    table = Table()
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)
    adapter = SimpleNamespace(currentModel=SimpleNamespace(EditRebuild3=lambda: True))
    if shared_quantity != 2:
        with pytest.raises(RuntimeError, match="model has 2"):
            drawing._validate_bom(adapter, table, facts)
        return
    items, headers = drawing._validate_bom(adapter, table, facts)
    assert headers == 1
    assert len(items) == len(facts.components)
    rows = [row for row in table.cells[1:] if row[1] == "MHA-SH-VN-52"]
    assert len(rows) == 1 and rows[0][3] == "2"


@pytest.mark.parametrize("proud", [0.0, 1.75])
def test_shared_stop_frame_preserves_world_geometry(proud: float) -> None:
    import build_dt_drive_train_assembly as assembly
    import dt_swing_stop_screw_spec as stop

    tree = ast.parse(BUILDER.read_text(encoding="utf-8"))
    by_reference = {
        ast.literal_eval(keyword.value): node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "place_component"
        for keyword in node.keywords
        if keyword.arg == "component_reference"
    }
    insertions = {
        "stop_screw": by_reference["SwingStopScrew:1"],
        "spring_foot_screw": by_reference["FootScrew:1"],
    }
    for call in insertions.values():
        assert ast.literal_eval(call.args[1]) == SCREW_STEM
        assert isinstance(call.args[4], ast.Name) and call.args[4].id == "IDENTITY"
    namespace = {**vars(assembly), "STOP_PROUD_LEN": proud}
    position = eval(
        compile(ast.Expression(insertions["stop_screw"].args[2]), str(BUILDER), "eval"),
        namespace,
    )
    assert position == [assembly.STOP_X, assembly.Y_BASE_TOP + proud, assembly.STOP_Z]
    # Canonical stock's tip and under-head plane equal the former translated
    # stop body's points, including a nonzero proud-length regression.
    for local_y in (-stop.SHANK_LEN, 0.0, stop.HEAD_DIA / 2.0):
        assert position[1] + local_y == pytest.approx(
            assembly.Y_BASE_TOP + (local_y + proud)
        )
    namespace.update(sx=assembly._FOOT_SCREW_XZ[0][0], sz=assembly._FOOT_SCREW_XZ[0][1])
    foot_position = eval(
        compile(ast.Expression(insertions["spring_foot_screw"].args[2]), str(BUILDER), "eval"),
        namespace,
    )
    assert foot_position == [
        namespace["sx"], assembly.Y_BASE_TOP + assembly.SPRING_T, namespace["sz"],
    ]
    # The swing-stop placement binds no name, so nothing can recolour it; the
    # foot screw is the one 90280A108 instance painted.
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    appearances = [
        call for call in calls
        if isinstance(call.func, ast.Name) and call.func.id == "apply_component_color"
        and len(call.args) >= 3
        and getattr(call.args[1], "id", None) == "spring_foot_screw"
    ]
    assert len(appearances) == 1
    color = eval(compile(ast.Expression(appearances[0].args[2]), str(BUILDER), "eval"), namespace)
    assert color == pytest.approx((0.08, 0.08, 0.09))


@pytest.mark.parametrize("role", [spec.FOOT_SCREW_ROLE, spec.SWING_STOP_SCREW_ROLE])
def test_shared_screw_explode_rejects_missing_and_duplicate_roles(role: str) -> None:
    census = _instances()
    missing = [spec.Instance(i.name, i.stem, i.origin_mm, None if i.role == role else i.role) for i in census]
    with pytest.raises(ValueError, match="must tag one"):
        spec.plan_explode(missing)
    original = next(i for i in census if i.role == role)
    duplicate = spec.Instance("unrelated-native-index-77", original.stem, original.origin_mm, role)
    with pytest.raises(ValueError, match="must tag one"):
        spec.plan_explode([*census, duplicate])


def test_changed_gear_bom_counts_come_from_their_specs() -> None:
    import dt_crank_drive_gear_spec as gear64
    import dt_crank_pinion_spec as pinion
    import dt_cylinder_gear_spec as drum

    for stem, teeth in (
        ("dt-cylinder-gear", drum.TEETH),
        ("dt-crank-drive-gear", gear64.TEETH),
        ("dt-crank-pinion", pinion.TEETH),
    ):
        assert f"{teeth}T" in drawing.BOM_DESCRIPTIONS[stem]


def test_t120_fitup_envelope_matches_the_actual_model() -> None:
    import build_dt_drive_train_assembly as assembly
    import dt_crank_pinion_spec as pinion

    actual_shoulder = assembly.T120_SHOULDER_AIR
    assert not math.isnan(actual_shoulder)
    if math.isinf(actual_shoulder):
        assert actual_shoulder == math.inf
        assert pinion.T120_SHOULDER_AIR_WORST == actual_shoulder
        # The section helper, not a typed large air allowance, establishes absence.
        shift, dy = assembly._cone_corners(
            assembly._CONE_FLOATS, assembly._CRANK_HEIGHT_BAND
        )
        section = assembly._t120_lowest(
            assembly._T120_SOUTH_FACE_STATION + shift,
            dy,
            assembly.R16
            + assembly.ADD16
            + max(assembly._PINION_TIP_RADIUS_BAND)
            + assembly.T120_POSE_RADIAL,
        )
        assert all(float(value) == math.inf for value in section.flat)
    else:
        assert (
            pinion.T120_SHOULDER_AIR_WORST
            == math.floor(actual_shoulder * 100.0) / 100.0
        )
    actual_band = assembly.T120_TURNED_BAND_RADIAL
    assert math.isfinite(actual_band)
    assert (
        pinion.T120_TURNED_BAND_RADIAL_WORST == math.floor(actual_band * 100.0) / 100.0
    )


def test_step_one_sets_the_64t_against_the_shaft_collar() -> None:
    """#916: the shaft's thrust collar is the 64T's axial stop (the drive
    train seats the gear's south face on the collar end), so the step-1 line
    that slides it on names it; crank_boss_rim books the gear's station from
    that collar.  Owner decision C1 keyed (2026-11-09, PR #1992): the land-1
    key is seated first."""
    import dt_cone_gear_shaft_spec as shaft

    assert shaft.COLLAR_THICKNESS > 0.0
    gear = drawing.BOM_PART_NUMBERS["dt-crank-drive-gear"]
    shaft_number = drawing.BOM_PART_NUMBERS["dt-cone-gear-shaft"]
    step_one = drawing.CONE_CRANK_STEPS.split("\n2. ")[0]
    (line,) = (row for row in step_one.split("\n") if f"SLIDE {gear}" in row)
    assert shaft_number in line and "COLLAR" in line


def test_crank_mesh_is_accepted_by_hand_with_a_pinion_recut_remedy() -> None:
    """Delegated ruling 2026-11-17 on #2481 (option B): 4N's full turn by
    hand, before the 16T is pinned, is the crank mesh's acceptance; a pair
    that binds in its teeth has the 16T recut at the same depth, the cutter
    moved sideways, and the step is redone from the slide-on.  Each 4N
    remedy names the bind it answers, and only a recut sends the fitter back
    (Codjiflo r1 on #3090)."""
    number = drawing.steps.step_number("crank-mesh-checked")
    step = drawing.CONE_CRANK_STEPS.split(f"\n{number}. ", 1)[1]
    step = " ".join(step.split(f"\n{number + 1}. ")[0].split())
    (turn,) = re.findall(rf"{number}N\. [^.]*\.", step)
    assert "ONE FULL REVOLUTION BY HAND" in turn and "MUST NEVER BIND" in turn
    (rub,) = re.findall(rf"{number}P\. [^.]*\.", step)
    assert rub.startswith(f"{number}P. IF THE BAND OR SHOULDER RUBS T120,")
    (recut,) = re.findall(rf"{number}Q\. .*?SAME DEPTH\.", step)
    assert recut == (
        f"{number}Q. IF THE TEETH BIND, RECUT MHA-DT-10: EVERY TOOTH GAP .004 WIDER, "
        "CUTTER MOVED SIDEWAYS, SAME DEPTH."
    )
    redo = f"{number}R. AFTER A RECUT, REPEAT FROM {number}D."
    assert redo in step
    assert f"{number}D. SLIDE MHA-DT-10 ON WITHOUT ITS PIN" in step
    order = [
        step.index(turn),
        step.index(rub),
        step.index(recut),
        step.index(redo),
        step.index("MATCH-DRILL"),
    ]
    assert order == sorted(order), step


# The #2481 owner pack (2026-11-15, issuecomment-6889258234): whole-face
# print-worst free play of the crank pair on main's .300 in pitch geometry, mm
# on the 16T pitch circle, cutters' forms / ideal involutes, from #2591's 3D
# sampler (crank_mesh_free_play.print_worst_mm), and the same with the 16T's
# flanks moved in 0.10 mm.  No merged module reproduces them; they are
# recorded here as STRAIGHT_TOOTH_LEAN_3D_MM is in test_standard_mesh_checks.
CRANK_PRINT_WORST_FREE_PLAY_MM = (-0.0809, -0.0971)
CRANK_PRINT_WORST_FREE_PLAY_THINNED_0_10_MM = (0.0215, 0.0050)
# A sideways pass at full depth takes the same width off the tooth at every
# radius, so the least tip land loses the whole widening.  Floor: a quarter
# module, the usual minimum top land for an unhardened cut gear.
RECUT_TIP_LAND_MODULE_FRACTION_MIN = 0.25


def test_pinion_recut_clears_the_print_worst_corner_and_keeps_a_tip_land() -> None:
    """The recut 4Q prints is sized against the owner pack's figures (#2481
    option B) and checked against the 16T's own finite-form tooth."""
    import dt_crank_pinion_spec as pinion

    widening = drawing.PINION_RECUT_GAP_WIDENING_MM
    assert drawing.inch_text(widening, 3) == ".004"
    # It closes the worst corner in both tooth models ...
    assert all(widening > -closure for closure in CRANK_PRINT_WORST_FREE_PLAY_MM)
    # ... and free play grows about one-for-one with the widening (the pack's
    # 0.05 -> 0.10 mm step gained 0.051 mm), so from the sampled 0.10 mm
    # thinning the printed pass still leaves positive free play.
    assert all(
        play + (widening - 0.10) > 0.0 for play in CRANK_PRINT_WORST_FREE_PLAY_THINNED_0_10_MM
    )
    # The least finite-form tip land, less the shared helper's error bound,
    # keeps the floor after one pass.
    floor = RECUT_TIP_LAND_MODULE_FRACTION_MIN * pinion.MODULE_MM
    for _, profile in pinion.STOCK_PROFILE_CORNERS:
        profile.require_tip_land(floor + widening)


def test_cone_swing_check_stops_disengaged_at_the_swing_stop() -> None:
    """MHA-SH-VN-52 bounds the DISENGAGE swing; the engaged mesh is set by
    feel at assembly (owner direction 2026-11-11, #2365; cone_set_stack):
    the set held at a stated pose (swung in to a bind, #2587), each pedestal
    tapped either way to a bind at its end and tightened, then the swing
    brought in to the first bind, eased out to an observable stop (#2585),
    and locked with MHA-DT-VN-51 -- never the stop, and nothing gauged."""
    check = " ".join(drawing.CHECKS.split("4. CONE SWING")[1].split("\n5.")[0].split())
    (hold,) = re.findall(r"4D\. [^.]*\.", check)
    (taps,) = re.findall(r"4E\. [^.]*\.", check)
    (ease,) = re.findall(r"4N\. [^.]*\.", check)
    assert "BIND" in hold and "HOLD" in hold
    assert " IN " in taps and " OUT " in taps
    assert "AT ITS END" in taps
    assert "SMALL STEPS" in ease and "RUN FREE" in ease
    order = [
        check.index("OUT TO THE MHA-SH-VN-52 STOP"),
        check.index("EASE EACH MHA-DT-02'S HOLD-DOWN UNTIL IT MOVES"),
        check.index(hold),
        check.index(taps),
        check.index("CLAMP EACH MHA-DT-02 TO MHA-FR-01 THERE"),
        check.index("SWING THE CONE SET OUT"),
        check.index("SWING IN UNTIL A GEAR JUST BINDS"),
        check.index(ease),
        check.index("TIGHTEN MHA-DT-VN-51"),
    ]
    assert order == sorted(order), check
    assert "RETURN IT TO THE MHA-SH-VN-52" not in check
    assert "FEELER" not in check and "LEAVES" not in check


def test_the_run_check_accepts_end_gear_shake_but_no_bind_or_skip() -> None:
    """Owner ruling 2026-11-14 on #2584 (option A): a gear past the binds
    that hold the cone line may run loose; the sheet states it as a plain
    fact naming those gears by the 4E binds.  Check 4R, the run after the
    lock, still refuses a bind, and its remedy (4S) still follows it."""
    check = " ".join(drawing.CHECKS.split("4. CONE SWING")[1].split("\n5.")[0].split())
    (run,) = re.findall(r"(?<![-\w])4R\. [^.]*\.", check)
    assert f"{drawing.CHECK_RUN_CRANK_TURNS} TURNS" in run
    assert "NEVER BIND" in run
    assert "4E" in run and "SHAKE" in run
    assert "ACCEPT" not in run
    assert check.index(run) < check.index("4S. IF ONE BINDS")


def test_the_pedestals_are_set_by_feel_then_spotted_with_one_tripwire() -> None:
    """Owner ruling 2026-11-24, fit audit part 2 C6 ("Yes: set by feel, spot
    the holes after, tripwire .015."): the pedestals stand clamped at their
    DRO X/Y until check 4E has tapped them to their binds; their MHA-FR-01
    seats are spotted, drilled and tapped through the foot holes after that;
    the DRO recheck table is gone and one .015 X tripwire sends the fitter to
    the cone pivot seat, which it clears with the pivot seat's whole error
    and the DRO set band."""
    import cone_set_stack
    import cylinder_bank_layout
    import dt_drive_train_steps as steps

    check = " ".join(drawing.CHECKS.split("4. CONE SWING")[1].split("\n5.")[0].split())
    (clamp,) = re.findall(r"4F\. [^.]*\.", check)
    (tripwire,) = re.findall(r"4G\. .*?\.015\.", check)
    (remedy,) = re.findall(r"4H\. .*? GOING ON\.", check)
    (seat,) = re.findall(r"4J\. .*? SPOT\.", check)
    (screw,) = re.findall(r"4K\. [^.]*\.", check)
    assert tripwire == "4G. NEITHER X INDICATOR READS OVER .015."
    pivot = steps.step_number("other-base-mounting")
    assert f"STEP {pivot}E-{pivot}H PIVOT SEAT" in remedy
    assert "FOOT HOLE" in seat and "PER MHA-FR-01" in seat and "TRANSFER-PUNCH" in seat
    assert "MHA-DT-VN-62" in screw and "CLAMP" in screw and "Y ZERO" in clamp
    order = [check.index(text) for text in (clamp, tripwire, remedy, seat, screw)]
    assert order == sorted(order)
    follow = (
        cone_set_stack.PIVOT_TRANSFER_PUNCH_PLAY_MM
        + cone_set_stack.PUNCH_MARK_PICKUP_MM
        + cone_set_stack.PIVOT_THREAD_CENTRING_MM
        + cone_set_stack.PIVOT_BORE_FLOAT_MM
    )
    assert follow + cylinder_bank_layout.FRONT_STRAP_LOCATE_BAND < 0.015 * 25.4
    # The bank steps clamp; no seat is cut and nothing is recorded there.
    assert "8T. CLAMP THE FRONT MHA-DT-02 TO MHA-FR-01 THERE." in drawing.BANK_STEPS
    assert "9F. CLAMP IT TO MHA-FR-01." in drawing.BANK_STEPS
    for gone in ("TRANSFER PUNCH", "MHA-DT-VN-62", "RECHECK TABLE", "DRILL AND TAP THE SEAT"):
        assert gone not in drawing.BANK_STEPS, gone
    assert not hasattr(drawing, "PEDESTAL_RECHECK_ROWS")
    assert "FILL IN" not in check


def test_the_cone_set_is_accepted_through_a_turn_of_every_drum_gear() -> None:
    """The feel set guarantees no bind only where it was felt, so the
    acceptance turns the crank until the slowest MHA-DT-12 has made a turn."""
    import dt_cone_gear_spec as cone
    import dt_crank_drive_gear_spec as gear64
    import dt_crank_pinion_spec as pinion
    import dt_cylinder_gear_spec as drum

    crank_per_cone_turn = gear64.TEETH / pinion.TEETH
    slowest_drum_turn = drum.TEETH / min(cone.CONE_TEETH)
    check = " ".join(drawing.CHECKS.split("4. CONE SWING")[1].split("\n5.")[0].split())
    turns = re.search(r"TURN THE CRANK (\d+) TURNS\b[^.]*\bBIND", check)
    assert turns is not None, check
    assert int(turns.group(1)) == crank_per_cone_turn * slowest_drum_turn


def test_zeroing_re_sets_the_swing_and_cranks_back_to_the_zero() -> None:
    """Re-setting the swing turns the crank; the acceptance's crank turns
    turn every MHA-DT-12 a whole number of times, so cranking on until the
    notches return restores the zero just set."""
    import dt_cone_gear_spec as cone
    import dt_crank_drive_gear_spec as gear64
    import dt_crank_pinion_spec as pinion
    import dt_cylinder_gear_spec as drum
    from fractions import Fraction

    cone_turns = Fraction(drawing.CHECK_RUN_CRANK_TURNS * pinion.TEETH, gear64.TEETH)
    for teeth in cone.CONE_TEETH:
        assert (cone_turns * Fraction(teeth, drum.TEETH)).denominator == 1, teeth
    zeroing = " ".join(drawing.CHECKS.split("\n5. ")[1].split("\n6. ")[0].split())
    reset = zeroing.index("RE-SET THE CONE SET SWING")
    assert zeroing.index("UNTIL EVERY NOTCH IS BACK") > reset > zeroing.index("NOTCHES")


def test_cone_swing_check_requires_installed_stop_inspection_and_seating() -> None:
    """The supplied thread class does not prove the assembled stop's engagement."""
    import dt_swing_stop_screw_spec as stop_screw

    check = " ".join(drawing.CHECKS.split("4. CONE SWING")[1].split("\n5.")[0].split())
    # Owner ruling S1 (audit part 2): turns from first bite, the count less
    # two lead pitches holding the 1.5D full-form floor.
    turns = _assert_engagement_cites_its_count(
        check, "MHA-SH-VN-52", "stop-screw-engagement"
    )
    assert (turns - 2) * stop_screw.THREAD_PITCH >= stop_screw.MIN_USEFUL_ENGAGEMENT_MM
    assert (turns - 3) * stop_screw.THREAD_PITCH < stop_screw.MIN_USEFUL_ENGAGEMENT_MM
    assert "CHECK THAT ITS HEAD IS FULLY SEATED" in check
    assert "CHECK THAT MHA-DT-20 AND THE MHA-DT-VN-52 SHOULDER STAY SEATED" in check


def test_a_loosened_post_screw_re_sets_the_post_before_the_checks() -> None:
    # Owner ruling 2026-11-20 (#1177 friction-only, #3085 option B).
    check = " ".join(drawing.CHECKS.split("4. CONE SWING")[1].split("\n5.")[0].split())
    assert "4U. MHA-DT-02 AND MHA-DT-VN-61 STAY AS SET FROM HERE ON." in check
    post = drawing.steps.step_number("post-and-tip-block")
    end_play = drawing.steps.step_number("end-play-set")
    redo = re.search(r"4V\. IF ONE LOOSENS, REDO CHECKS 4-7 \(A SCREW: STEP (\d+[A-Z]) FIRST\)\.", check)
    assert redo is not None, check
    bodies: dict[str, str] = {}
    key: str | None = None
    for line in drawing.CONE_CRANK_STEPS.splitlines():
        head = re.match(r"(\d+[A-Z]?)\. ", line)
        if head:
            ours = re.fullmatch(rf"(?:{post}|{end_play})[A-Z]", head.group(1))
            key = head.group(1) if ours else None
            if key:
                bodies[key] = line
        elif line.startswith(" ") and key:
            bodies[key] += " " + line.strip()
    keys = list(bodies)

    def redone(first: str, last: str) -> str:
        return " ".join(bodies[key] for key in keys[keys.index(first) : keys.index(last) + 1])

    # 4V names the remedy step 3G, which follows the end-play steps.
    assert redo.group(1) == f"{end_play}G"
    step = re.fullmatch(
        rf"{end_play}G\. IF A MHA-DT-VN-61 IS EVER LOOSENED, REDO (\d+[A-Z]), (\d+[A-Z])-(\d+[A-Z]), "
        r"THEN (\d+[A-Z])-(\d+[A-Z])\.",
        bodies[redo.group(1)],
    )
    assert step is not None, bodies[redo.group(1)]
    assert step.group(1) == f"{post}M"
    assert "LOOSE ENOUGH TO TURN MHA-DT-05" in bodies[step.group(1)]
    assert step.group(2).startswith(str(post)) and step.group(3).startswith(str(post))
    re_set = redone(step.group(2), step.group(3))
    assert "TURN MHA-DT-05 ON ITS SCREWS" in re_set
    assert "TIGHTEN BOTH MHA-DT-VN-61" in re_set
    # The post can shift along the shaft on the screws' float: the end play
    # is indicated again, with its remedy and the pinch lock's check.
    assert step.group(4) == f"{end_play}C" and step.group(5) == f"{end_play}F"
    end_play_redo = redone(step.group(4), step.group(5))
    assert "INDICATE THE MHA-DT-04 END PLAY" in end_play_redo
    assert "DOES NOT TURN IN MHA-DT-21" in end_play_redo


def _assert_engagement_cites_its_count(check: str, screw: str, row: str) -> int:
    """A seated screw's engagement cannot be read: step 23 records its turns
    from first bite as it goes in, the check verifies that record, and its
    sheet 16 row prints the minimum and names the same record (owner ruling
    S1, audit part 2).  Returns the printed minimum."""
    import dt_drive_train_steps as steps

    cited = re.search(
        rf"VERIFY {screw}'S STEP (\d+\w) TURNS \({re.escape(drawing.acceptance_ref(row))}\)\.",
        check,
    )
    assert cited is not None, check
    (ref,) = cited.groups()
    number = steps.step_number("other-base-mounting")
    assert ref.startswith(str(number))
    number_text = str(drawing.ACCEPTANCE_ROW_NUMBERS[row])
    (printed,) = (cells for cells in drawing.ACCEPTANCE_TABLE_ROWS if cells[0] == number_text)
    assert printed[-1] == f"COUNTED AT {ref}"
    body = _rig_step_body("other-base-mounting")
    record = re.search(rf"\b{ref}\. (.*?)(?= {number}[A-HJ-NP-Z]\. |$)", body).group(1)
    assert record == f"RECORD {screw}'S TURNS FROM FIRST BITE TO SEATED."
    # Nothing is read off a depth gauge or calipers for the engagement now.
    assert "FULL-THREAD DEPTH" not in body and "THREAD LENGTH WITH CALIPERS" not in body
    minimum = re.fullmatch(r"(\d+) MIN", _accept_cell(row))
    assert minimum is not None
    return int(minimum.group(1))


def test_cone_swing_check_requires_pivot_thread_engagement() -> None:
    """The seated shoulder does not establish actual full-form thread engagement."""
    from _mcmaster_91829a560 import PITCH
    import dt_vn_cone_pivot_screw_spec as pivot_screw

    check = " ".join(drawing.CHECKS.split("4. CONE SWING")[1].split("\n5.")[0].split())
    turns = _assert_engagement_cites_its_count(
        check, "MHA-DT-VN-52", "pivot-screw-engagement"
    )
    # The count less two lead pitches holds DT-04's 1D floor, and the
    # screw's thread (9 turns) can give it before the shoulder seats.
    assert (turns - 2) * PITCH >= pivot_screw.MIN_USEFUL_ENGAGEMENT_MM
    assert (turns - 3) * PITCH < pivot_screw.MIN_USEFUL_ENGAGEMENT_MM
    assert turns * PITCH <= pivot_screw.THREAD_TAIL_LEN + 1e-9
    assert "MHA-DT-VN-52 SHOULDER STAY SEATED" in check
    # Owner ruling DT-04's location follows the minimum to its sheet 16 row
    # (Codjiflo on #3023), as DT-07's is pinned to its fact.
    from machinist_exceptions import load_exceptions

    (dt04,) = (
        entry
        for entry in load_exceptions(_config.CONFIG_DIR, "dt_drive_train_assembly", "assembly")
        if entry.id == "DT-04"
    )
    row = drawing.acceptance_ref("pivot-screw-engagement")
    assert f"({row}: {turns} MIN)" in dt04.where


def _flat(text: str) -> str:
    return " ".join(text.split())


def _unlettered(text: str) -> str:
    """Printed text with its lettered sub-step heads (16A., 21B. ...) removed,
    so a fit-up step's one-thing lines read back word for word."""
    return _flat(re.sub(r"(?m)\b\d+[A-HJ-NP-Z]\. ", "", text))


def _rig_step_body(key: str) -> str:
    """One printed rig step, head to the next head, whitespace-folded."""
    import dt_drive_train_steps as steps

    heads = list(re.finditer(r"^(\d+)\. ", RIG_STEPS, re.MULTILINE))
    number = steps.step_number(key)
    index = next(i for i, head in enumerate(heads) if int(head.group(1)) == number)
    end = heads[index + 1].start() if index + 1 < len(heads) else len(RIG_STEPS)
    return _flat(RIG_STEPS[heads[index].end() : end])


def _accept_cell(key: str) -> str:
    """The SET TO / ACCEPT cell of one sheet 16 setting-table row."""
    number = str(drawing.ACCEPTANCE_ROW_NUMBERS[key])
    (row,) = (row for row in drawing.ACCEPTANCE_TABLE_ROWS if row[0] == number)
    return row[drawing.ACCEPTANCE_TABLE_HEADER.index("SET TO / ACCEPT")]


def test_rig_is_located_by_its_parked_tip_gap() -> None:
    import dt_drive_train_steps as steps
    import pinion_rig_tip_gap as tip_gap

    rod = f"A {tip_gap.TIP_GAP_ROD_TEXT} IS SNUG"
    cite = f"({drawing.acceptance_ref('tip-gap')})"
    located = _rig_step_body("rig-located")
    for phrase in ("UNDRILLED SEATS", rod, cite):
        assert phrase in located, phrase
    check = _flat(drawing.CHECKS)
    assert f"{rod} TIP TO TIP" in check
    assert (
        f"AT GEAR 19 ({drawing.acceptance_ref('tip-gap')}, SET AT SHEET "
        f"{drawing.CONTINUATION_SHEET}, STEP {steps.step_number('rig-located')}E)"
    ) in check
    # Owner ruling C8 (audit part 2): one rod, no window, and the lever is
    # turned until the teeth seat; the row names the rod (R5, rule 22).
    assert _accept_cell("tip-gap") == "SNUG TIP TO TIP"
    number = str(drawing.ACCEPTANCE_ROW_NUMBERS["tip-gap"])
    (row,) = (row for row in drawing.ACCEPTANCE_TABLE_ROWS if row[0] == number)
    assert row[-1] == tip_gap.TIP_GAP_ROD_TEXT
    assert "5C. TURN MHA-DT-16 UNTIL THE TEETH SEAT, NO FORCE." in check
    assert f"SEE SHEET {drawing.CHECKS_SHEET}" in drawing.ASSEMBLED_HEADING
    fields = {field.label: field for field in drawing.package_note_fields(_drawing_facts())}
    assert "pinion rig sequence" in dict(fields[f"sheet {drawing.FIT_SHEET} left note field"].blocks)
    # The seats are spotted after RIG SET, and drilled per the base's own
    # transfer callouts, not a second copy of their sizes.
    seats = _rig_step_body("rig-seats-transferred")
    assert "PER ITS MHA-FR-01 TRANSFER CALLOUT" in seats
    assert not re.search(r"#\d+-\d+|#\d+ X", seats)
    assert steps.step_number("rig-set") < steps.step_number("rig-seats-transferred")


def test_the_rig_steps_print_the_fitup_sequence_once_in_order() -> None:
    """Codex #858 (PRRT_kwDOPHDy386mTbPB): the fit-up that produces the
    modelled pin stations reaches the fitter.  Each pinion_rig_fitup step
    prints once, word for word or as its RIG_REWORDINGS re-break, in its own
    step, in ASSEMBLY_SEQUENCE order; nothing is pending."""
    import dt_drive_train_steps as steps
    import pinion_rig_fitup as fitup

    keys = (
        "arbor-collar-pinned",
        "drum-bonded",
        "handle-bonded",
        "cam-pins-bonded",
        "straps-pinned-to-torque-shaft",
        "rig-set",
        "cam-collars-set",
        "lever-pin-set",
    )
    flat = _unlettered(RIG_STEPS)
    for key, step in zip(keys, fitup.ASSEMBLY_SEQUENCE, strict=True):
        if key == "lever-pin-set":
            # Rubric sample round 6 (rule 22): the sheet re-composes the lever
            # pin set from the same spec constants as one-thing lines, the
            # hole's drill folded into the match-drill
            # (test_lever_pin_step_states_existing_drill_size_and_slip_fit).
            continue
        printed = _flat(drawing._reworded(_flat(step), *drawing.RIG_REWORDINGS.get(key, ())))
        assert flat.count(printed) == 1, key
        assert printed in _unlettered(_rig_step_body(key)), key
    numbers = [steps.step_number(key) for key in keys]
    assert numbers == sorted(numbers)
    printed = [int(n) for n in re.findall(r"^(\d+)\. ", RIG_STEPS, re.MULTILINE)]
    first = steps.SEQUENCE.index("arbor-collar-pinned") + 1
    assert printed == list(range(first, len(steps.SEQUENCE) + 1))
    assert "PENDING" not in RIG_STEPS
    # The pivot shaft's match-drilled pin hole is drilled in this step, which
    # names the hole (the part sheet carries no pointer to it, rule 7).
    key = "straps-pinned-to-torque-shaft"
    assert fitup.SHAFT_DRILL_NAME in _rig_step_body(key)


def test_lever_pin_step_states_existing_drill_size_and_slip_fit() -> None:
    """r8: name the hole and acceptance without inventing a pilot or press fit."""
    import dt_pinion_lever_pin_spec as pin

    assert pin.PIN_DIA == 25.4 / 16.0
    step = _rig_step_body(pin.LEVER_PIN_SET_STEP_KEY)
    # Fit audit F23 (rule 4 form 1, F drilled hub): the lead holds the lever
    # square to the rod while the pin hole is match-drilled.
    assert step.startswith(
        f"{pin.LEVER_PIN_SET_NAME}, GRIP PARKED, {pin.LEVER_NUMBER} HELD SQUARE TO "
        f"{pin.LIFT_ROD_NUMBER} WITH A SQUARE: MATCH-DRILL #51 THRU"
    )
    assert f"{pin.LEVER_NUMBER}'S HUB AT ITS PRINTED STATION AND {pin.LIFT_ROD_NUMBER} TOGETHER" in step
    assert f"INSERT {pin.PIN_NUMBER}, A SLIDING FIT." in step
    assert "TRIM BOTH ENDS." in step
    assert f"PEEN BOTH ENDS FLUSH WITH THE HUB (SHEET {drawing.FULL_DETAIL_SHEET})." in step
    # Round 9 (rule 23): the cross pin's own bench check, 22D.
    assert (
        f"22D. CHECK THAT {pin.LEVER_NUMBER} DOES NOT TURN OR SLIDE ON {pin.LIFT_ROD_NUMBER} BY HAND."
    ) in _flat(RIG_STEPS)
    # Round 7 (#3): view E calls the peen out at the hub, citing 22C.
    assert drawing.LEVER_PIN_PEEN_NOTE.split("\n") == [
        f"PEEN {pin.PIN_NUMBER}",
        "FLUSH BOTH ENDS",
        "(STEP 22C)",
    ]
    assert "PEEN BOTH ENDS" in [
        line.split(". ", 1)[1] for line in RIG_STEPS.splitlines() if line.startswith("22C. ")
    ][0]
    assert "LIGHT HAMMER" not in step
    assert "REAM" not in step


def test_the_tip_gap_rod_keeps_the_parked_pinion_clear_and_the_cam_in_reach() -> None:
    """Owner ruling C8 (audit part 2, "Yes, a 3/32 rod."): the rig's east-west
    locate is a 3/32 rod at the bench rest gap (pins on the cams); the rod
    leaves the parked pinion clear of every cylinder gear and the cam still
    swings it past the standard centre, where 5C seats the teeth."""
    import dt_cylinder_gear_spec as cylinder_gear
    import pinion_rig_tip_gap as tip_gap

    # The model parks the pins a design air above the cams; the spring takes
    # it up on the bench, so the rest gap is wider than the model's.
    assert tip_gap.REST_TIP_GAP > tip_gap.MODEL_TIP_GAP
    assert tip_gap.TIP_GAP_ROD == pytest.approx(3.0 / 32.0 * 25.4)
    spread = (cylinder_gear.OUTSIDE_DIA_BAND[0] - cylinder_gear.OUTSIDE_DIA_BAND[1]) / 2.0
    assert tip_gap.PARKED_TIP_CLEARANCE_MIN == pytest.approx(
        tip_gap.TIP_GAP_ROD - tip_gap.TIP_GAP_ROD_TOLERANCE - spread
    )
    assert tip_gap.PARKED_TIP_CLEARANCE_MIN > 2.0
    assert tip_gap.CAM_REACH_AT_STANDARD_CENTRE_MIN > 1.0
    # No leaf makes up the locate any more.
    assert not any("CHECK 7" in row[2] for row in drawing.FEELER_STACK_ROWS)


def test_every_set_feeler_the_steps_and_checks_print_has_a_leaf_row() -> None:
    """Rubric sample round 16 (#0, 3/3 runs): each feeler a step or check
    sets is a sheet 15 row citing it; check cites carry CHECK.  The table
    stays left of the cone station table.  #3042: every row is whole inch
    leaves of the owned set, each once, summing to the printed setting."""
    import dt_feeler_leaves
    from cone_stack_end_play import STACK_FEELER

    assert drawing.FEELER_STACK_HEADER[1] == "LEAVES (IN)"
    for setting, leaves, _cited in drawing.FEELER_STACK_ROWS:
        sizes = [float(leaf) for leaf in leaves.split(" + ")]
        assert set(sizes) <= set(dt_feeler_leaves.LEAVES_IN), setting
        assert len(set(sizes)) == len(sizes) <= dt_feeler_leaves.MAX_STACK_LEAVES, setting
        assert sizes == sorted(sizes, reverse=True), setting
        assert math.isclose(sum(sizes), float(setting), abs_tol=1e-9), setting
    assert "MM" not in " ".join(
        (drawing.FEELER_STACK_TITLE, *drawing.FEELER_STACK_HEADER, drawing.FEELER_TABLE_NOTE)
    )
    # The booked leaf tolerance is checked at the bench, not assumed.
    tolerance = drawing.inch_text(dt_feeler_leaves.LEAF_TOLERANCE, 4)
    note = " ".join(drawing.FEELER_TABLE_NOTE.split())
    assert re.search(rf"MIC EACH LEAF\b.*WITHIN ±{re.escape(tolerance)} OF ITS ETCHED SIZE", note)
    rows = {row[0]: row[2] for row in drawing.FEELER_STACK_ROWS}

    def printed(setting: float) -> str:
        return drawing.inch_text(setting, drawing.FEELER_PLACES)

    assert "4H, 4J" in rows[printed(drawing.pinion.T120_FITUP_FEELER_MM)]
    assert "1R" in rows[printed(STACK_FEELER)]
    assert "4F" in rows[printed(drawing.pinion.SEAT_FEELER_MM)]
    # The cone swing is set by feel (#2365): no row cites check 4.
    assert not any("CHECK 4" in cited for cited in rows.values())
    checks = " ".join(drawing.CHECKS.split())
    assert "RADIAL SHIMS" not in checks and "FEELER LEAVES" not in checks
    widths = general_table.table_column_widths(
        drawing.FEELER_STACK_HEADER, drawing.FEELER_STACK_ROWS
    )
    assert drawing.SETTING_TABLE_LEFT + sum(widths) <= drawing.STATION_TABLE_FIELD[0]


class _SheetTable:
    """A native general table that keeps what it was given, as SolidWorks does."""

    ROW_HEIGHT = 0.005525  # GetRowHeight, both seats (leaf 20261112T161937Z)

    def __init__(self, x: float, top: float, rows: int, columns: int) -> None:
        self.anchor = (x, top, 0.0)
        self.RowCount, self.ColumnCount = rows, columns
        self.widths: dict[int, float] = {}
        self.cells: dict[tuple[int, int], str] = {}

    def SetColumnWidth(self, column, width, _mode):  # noqa: N802
        self.widths[column] = width
        return width

    def SetText2(self, row, column, _displayed, text):  # noqa: N802
        self.cells[row, column] = text

    def DisplayedText2(self, row, column, _displayed):  # noqa: N802
        return self.cells[row, column]

    def GetAnnotation(self):  # noqa: N802
        return SimpleNamespace(GetPosition=lambda: self.anchor)

    def GetRowHeight(self, _row):  # noqa: N802
        return self.ROW_HEIGHT

    def GetColumnWidth(self, column):  # noqa: N802
        return self.widths[column]


@pytest.mark.parametrize("title_read_error", (0.0, -0.0009, 0.0009))
def test_sheet_15_tables_stack_clear_of_the_station_field_on_any_seat(
    monkeypatch: pytest.MonkeyPatch, title_read_error: float
) -> None:
    """Release v49 r2 (leaf 20261113T025825Z): on a 1010x678 px seat window the
    titles' pixel-read boxes put the pedestal recheck table 0.37 mm inside the
    station table field; on the 1010x598 px one it cleared by 0.53 mm.  A
    table hangs off its title's requested top, so a title box read a pixel
    or two off moves no table, and the stack ends 2 mm clear of the station
    table field and the interface notes.  Owner ruling C6 (2026-11-24) took
    the recheck table out: the setting table now ends over the station table
    field and the narrow feeler stack table stands left of it."""
    monkeypatch.setattr(general_table, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(drawing, "_activate_sheet", lambda *_args: None)
    monkeypatch.setattr(drawing, "_heading", lambda *_args: None)
    monkeypatch.setattr(drawing, "_reference_iso", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(drawing, "_stack_sheet_note_fields", lambda *_args: [])
    monkeypatch.setattr(general_table, "add_note_block", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(
        general_table,
        "anchor_note",
        lambda _adapter, _note, corner, **_kwargs: (
            corner[0],
            corner[1] - general_table.NOTE_LINE_PITCH + title_read_error,
            corner[0] + 0.08,
            corner[1] + title_read_error,
        ),
    )
    tables: list[_SheetTable] = []

    def insert(_bom, x, top, _anchor, _template, rows, columns):
        tables.append(_SheetTable(x, top, rows, columns))
        return tables[-1]

    adapter = SimpleNamespace(currentModel=SimpleNamespace(InsertTableAnnotation2=insert))

    assert drawing._place_setting_sheet(adapter, facts=None) == []

    setting, feeler = tables
    assert setting.anchor[1] == pytest.approx(
        drawing.SETTING_TABLE_TOP - general_table.TABLE_TITLE_DROP
    )
    bottoms = [table.anchor[1] - table.RowCount * table.ROW_HEIGHT for table in tables]
    assert bottoms[0] - feeler.anchor[1] == pytest.approx(
        drawing.SETTING_TABLE_GAP + general_table.TABLE_TITLE_DROP
    )
    assert bottoms[0] - drawing.STATION_TABLE_FIELD[1] >= 0.002
    assert bottoms[1] - drawing.INTERFACE_FIELD[1] >= 0.002
    widths = general_table.table_column_widths(
        drawing.FEELER_STACK_HEADER, drawing.FEELER_STACK_ROWS
    )
    assert drawing.SETTING_TABLE_LEFT + sum(widths) <= drawing.STATION_TABLE_FIELD[0]


def test_every_sheet_16_row_is_cited_by_its_step_and_fits_its_sheet(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """R5 machinist review (rule 22, 3/3 runs): each measurable fit and
    acceptance a step or check made only in its text prints as a sheet 16
    setting-table row, numbered on from sheet 15's, and its step cites the
    row in place of the value.  The table clears the reference view."""
    first_row = len(drawing.SETTING_TABLE_ROWS) + 1
    numbers = [int(row[0]) for row in drawing.ACCEPTANCE_TABLE_ROWS]
    assert numbers == list(range(first_row, first_row + len(numbers)))
    printed = _flat(
        "\n".join(
            text
            for field in drawing.package_note_fields(_drawing_facts())
            for _label, text in field.blocks
        )
    )
    for key, number in drawing.ACCEPTANCE_ROW_NUMBERS.items():
        cite = f"({drawing.acceptance_ref(key)}"
        # T024's row is the setup 1S centres in and 1X records in (#3292),
        # the pivot's the one 2B centres in and 2F records in (#2473, C5).
        twice = ("tip-gap", "t024-runout", "pivot-runout")
        assert printed.count(cite) == (2 if key in twice else 1), key
        (row,) = (row for row in drawing.ACCEPTANCE_TABLE_ROWS if row[0] == str(number))
        # The STEP cell names the sub-step (or check) whose text carries the cite.
        first = row[1].split(",")[0]
        text = _flat(drawing.CHECKS) if first.startswith("CHECK ") else printed
        first = first.removeprefix("CHECK ")
        head = re.search(rf"\b{re.escape(first)}\. ((?:(?!\b\d+[A-Z]?\. ).)*)", text)
        assert head is not None and cite in head.group(1), (key, first)
    assert drawing.acceptance_ref("tip-gap") in _flat(drawing.CHECKS)
    # Codjiflo on #3023 (rules 22, 26): the rows use the cone-gear codes, so
    # the title points at the code key and the key's scope names sheet 16.
    assert drawing.ACCEPTANCE_TABLE_TITLE.endswith(drawing.CODE_KEY_POINTER)
    assert drawing.CODE_KEY_HEADING.endswith(f", {drawing.ACCEPTANCE_SHEET})")
    # No cited value prints in its step any more.
    assert "ACCEPT 5." not in printed and "END PLAY AT THE SHAFT END: ." not in printed

    monkeypatch.setattr(general_table, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(drawing, "_activate_sheet", lambda *_args: None)
    monkeypatch.setattr(drawing, "_heading", lambda *_args: None)
    monkeypatch.setattr(drawing, "_reference_iso", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(general_table, "add_note_block", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(
        general_table,
        "anchor_note",
        lambda _adapter, _note, corner, **_kwargs: (
            corner[0],
            corner[1] - general_table.NOTE_LINE_PITCH,
            corner[0] + 0.08,
            corner[1],
        ),
    )
    tables: list[_SheetTable] = []

    def insert(_bom, x, top, _anchor, _template, rows, columns):
        tables.append(_SheetTable(x, top, rows, columns))
        return tables[-1]

    adapter = SimpleNamespace(currentModel=SimpleNamespace(InsertTableAnnotation2=insert))
    assert drawing._place_acceptance_sheet(adapter) == []
    (table,) = tables
    bottom = table.anchor[1] - table.RowCount * table.ROW_HEIGHT
    right = table.anchor[0] + sum(table.widths.values())
    left, top = drawing.ACCEPTANCE_REFERENCE_KEEP_OUT
    assert right <= left and bottom >= top
    # Positive control: a table reaching into the reference view is refused.
    assert drawing.acceptance_table_violations((table.anchor[0], top - 0.001, left + 0.001, 0.2))


def test_the_pivot_seat_is_transferred_and_trusted() -> None:
    """Owner ruling 2026-11-08 (Pedro): step 23 transfer-punches D1 through
    the MHA-DT-20 pivot bore with the cone set at its working position,
    lifts off, spot-drills, drills and taps; the swing check is the only
    acceptance, and DT-00 prints no offset from the pedestal seats."""
    import dt_drive_train_steps as steps
    import dt_vn_cone_pivot_screw_spec as pivot_screw

    step = _rig_step_body("other-base-mounting")
    number = steps.step_number("other-base-mounting")
    # The transfer pose (check 4's feel set, both ends bound) comes before
    # the clamp and the punch; sequence, not wording (AGENTS.md).
    route = [
        "JUST BIND",
        "RUN FREE",
        "CLAMP MHA-DT-20 TO MHA-FR-01.",
        "TRANSFER-PUNCH MHA-FR-01 THRU THE MHA-DT-20 PIVOT BORE.",
        "LIFT MHA-DT-20 OFF.",
        "SPOT-DRILL THE PUNCH MARK.",
        f"DRILL AND TAP {pivot_screw.THREAD} THERE PER MHA-FR-01.",
        "CHECK THAT MHA-DT-20 SWINGS FREELY UNDER THE HEAD.",
    ]
    assert f"{number}A." in step
    positions = [step.index(part) for part in route]
    assert positions == sorted(positions)
    assert step.count("CHECK THAT") == 1
    for absent in ("PUNCH MARK IS", "PLUG", "DRO", "MHA-DT-02 SEAT", "1.030", ".482"):
        assert absent not in step
    # The pivot seat is cut once, here: the bank no longer drills it.
    assert "PIVOT SEAT" not in drawing.BANK_STEPS


def test_the_bank_stack_is_measured_with_gauges_the_shop_owns() -> None:
    """#2362: the 20-gear stack is compared on an indicator zeroed on a
    gauge-block stack of its nominal length, which the shop's 81-piece inch
    set (cad/config/shop-equipment/: .1001-.1009, .101-.149, .050-.950,
    1-4 in) can wring, and which lies inside the acceptance window."""
    blocks = float(drawing.STACK_GAUGE_BLOCKS)
    low, high = (float(limit) for limit in drawing.STACK_WINDOW.split("-"))
    assert low < blocks < high
    assert drawing.STACK_GAUGE_BLOCKS in " ".join(drawing.BANK_STEPS.split())
    tenths = range(1001, 1010)
    thousandths = range(1010, 1500, 10)
    fiftieths = range(500, 10000, 500)
    inches = [
        sum(subset)
        for count in range(5)
        for subset in itertools.combinations((10000, 20000, 30000, 40000), count)
    ]
    target = round(blocks * 10000)
    assert any(
        a + b + c + d == target
        for a in (0, *tenths)
        for b in (0, *thousandths)
        for c in (0, *fiftieths)
        for d in inches
    ), drawing.STACK_GAUGE_BLOCKS


def test_one_code_key_defines_every_code_and_every_step_sheet_points_to_it() -> None:
    """Owner ruling 2026-11-08 (Pedro; rubric sample round 20 #2): one
    labelled key, built from the placed cone gears and the MHA-DT-12 count,
    defines the Tnnn codes and GEAR 0-19; each step sheet points to it."""
    facts = _drawing_facts()
    fields = drawing.package_note_fields(facts)
    keys = [
        (field, text)
        for field in fields
        for _label, text in field.blocks
        if text.startswith(drawing.CODE_KEY_HEADING)
    ]
    assert len(keys) == 1
    key_field, key = keys[0]
    assert key_field.sheet == drawing.SETTING_SHEET
    assert drawing.CODE_KEY_POINTER == f"(CODES: SHEET {drawing.SETTING_SHEET} KEY)"
    keyed = set(re.findall(r"\bT\d{3}\b", key))
    assert keyed == {code for _station, code in facts.cone_rows()}
    last_gear = facts.count("dt-cylinder-gear") - 1
    assert f"GEAR 0-{last_gear} = MHA-DT-12 FROM THE FRONT" in key
    step_sheets = (
        drawing.SEQUENCE_SHEET,
        drawing.CRANK_SHEET,
        drawing.BANK_SHEET,
        drawing.FIT_SHEET,
        drawing.CONTINUATION_SHEET,
        drawing.CHECKS_SHEET,
    )
    for sheet in step_sheets:
        blocks = [field.blocks for field in fields if field.sheet == sheet]
        texts = [text for block in blocks for _label, text in block]
        assert any(drawing.CODE_KEY_POINTER in text for text in texts), sheet
        printed = " ".join(texts)
        assert set(re.findall(r"(?<!MHA-PD-09 )\bT\d{3}\b", printed)) <= keyed, sheet
        gears = {int(n) for n in re.findall(r"\bGEARS? (\d+)\b", printed)}
        assert all(0 <= gear <= last_gear for gear in gears), sheet


@pytest.mark.parametrize("thousandths", (4, 10, 19, 27, 36, 37, 53, 97, 99, 125))
def test_a_leaf_stack_sums_to_its_setting_from_gage_leaves(thousandths: int) -> None:
    import dt_feeler_leaves
    import pinion_rig_fitup as fitup

    setting = dt_feeler_leaves.thousandths(thousandths)
    leaves = dt_feeler_leaves.leaf_stack(setting)
    assert math.isclose(sum(leaves), setting, abs_tol=1e-9)
    assert set(leaves) <= set(fitup.FEELER_GAGE_LEAVES_MM)
    assert len(set(leaves)) == len(leaves)  # one set: no leaf twice
    assert list(leaves) == sorted(leaves, reverse=True)
    # The fewest leaves: no shorter stack of the set reaches the setting.
    fewer = (
        stack
        for count in range(1, len(leaves))
        for stack in itertools.combinations(fitup.FEELER_GAGE_LEAVES_MM, count)
    )
    assert not any(math.isclose(sum(stack), setting, abs_tol=1e-9) for stack in fewer)
    assert dt_feeler_leaves.stack_error(setting) == pytest.approx(
        len(leaves) * dt_feeler_leaves.LEAF_TOLERANCE
    )


def test_a_setting_the_set_cannot_make_is_refused() -> None:
    import dt_feeler_leaves

    with pytest.raises(AssertionError, match="whole thousandth"):
        dt_feeler_leaves.leaf_stack(0.45)  # the metric set's leaf
    with pytest.raises(AssertionError, match="more than"):
        dt_feeler_leaves.leaf_stack(dt_feeler_leaves.thousandths(126))
    # The thinnest setting keeps its floor with the set band and leaf booked.
    setting = dt_feeler_leaves.smallest_setting(0.35, 0.10)
    assert setting - 0.10 - dt_feeler_leaves.stack_error(setting) >= 0.35
    thinner = setting - dt_feeler_leaves.LEAF_STEP
    assert thinner - 0.10 - dt_feeler_leaves.stack_error(thinner) < 0.35


def test_the_spring_is_stationed_east_west_where_its_preload_is_gated() -> None:
    """Main's TbPB ruling Q2(2) A: MHA-DT-24's foot hole is set where the
    preload gates put it, the crest on the flank (the flick's flat stays off
    it), before RIG SET's pad leaf sets it along the bank.  #1037 is the
    window a fitter must hold."""
    import dt_drive_train_steps as steps
    from dt_pinion_spring_section import SCREW_EAST_OF_PIVOT

    located = _rig_step_body("rig-located")
    assert drawing.SPRING_EAST_WEST in located
    assert f"FOOT HOLE CENTRE RIGHT OF THE MHA-DT-19 AXIS ({drawing.acceptance_ref('spring-foot')})" in located
    # The inch sheet's .XX, in its sheet 16 row: within half a hundredth of
    # the gated station.
    assert float(_accept_cell("spring-foot")) * 25.4 == pytest.approx(SCREW_EAST_OF_PIVOT, abs=0.127)
    assert "UNTIL ITS CREST BEARS ON THE PARKED BACK MHA-DT-14 FLANK" in located
    assert "TERMINAL FLAT" not in _flat(RIG_STEPS)
    assert "TERMINAL FLAT" not in Path(drawing.__file__).read_text(encoding="utf-8")
    assert steps.step_number("rig-located") < steps.step_number("rig-set")


def test_a_fitup_step_missing_from_its_key_is_caught() -> None:
    """Positive control: the collar set is not the lever pin's step."""
    import pinion_rig_fitup as fitup

    assert _flat(fitup.COLLAR_SET_STEP) not in _rig_step_body("lever-pin-set")


def test_drum_is_bonded_after_the_arbor_passes_the_front_strap() -> None:
    """The front strap bore is closed: a bonded drum can no longer pass it."""
    import dt_drive_train_steps as steps

    assert "FRONT MHA-DT-14 ON BEHIND IT" in _rig_step_body("arbor-collar-pinned")
    assert "BOND MHA-DT-22 INTO MHA-DT-01 WITH LOCTITE 638" in _rig_step_body("drum-bonded")
    assert "IN THE BACK MHA-DT-14 TOP BORE" in _rig_step_body("cluster-hung")
    order = [
        steps.step_number(key)
        for key in ("arbor-collar-pinned", "drum-bonded", "cluster-hung")
    ]
    assert order == sorted(order)


def test_torque_shaft_pins_go_in_before_the_cams() -> None:
    """The cams block the strap pins' west edge, and the cam set screws are
    tightened and staked only at the cam set, before the lever pin (Main's
    TbPB ruling; #1176)."""
    import dt_drive_train_steps as steps
    import pinion_rig_fitup as fitup

    assert "DRIVE MHA-DT-VN-63 PINS" in _rig_step_body("straps-pinned-to-torque-shaft")
    cams = _rig_step_body("cams-and-lever-fitted")
    assert "FIT 2X MHA-DT-23" in cams and "LOOSE" in cams and "MHA-DT-30" not in cams
    collar_set = drawing._reworded(fitup.COLLAR_SET_STEP, *drawing.RIG_REWORDINGS["cam-collars-set"])
    assert _flat(collar_set) in _unlettered(_rig_step_body("cam-collars-set"))
    order = [
        steps.step_number(key)
        for key in (
            "straps-pinned-to-torque-shaft",
            "cams-and-lever-fitted",
            "cam-collars-set",
            "lever-pin-set",
        )
    ]
    assert order == sorted(order)


def test_explode_plan_resolves_every_step_on_the_built_census() -> None:
    plan = spec.plan_explode(_instances())
    assert [step.label for step, _names in plan] == [s.label for s in spec.EXPLODE_STEPS]
    moved = {step.label: names for step, names in plan}
    assert moved["south pedestal"] == (
        "dt-arbor-pedestal-1",
        "dt-vn-pedestal-hold-down-screw-1",
        "sh-vn-arbor-set-screw-1",
    )
    assert moved["north pedestal"] == (
        "dt-arbor-pedestal-2",
        "dt-vn-pedestal-hold-down-screw-2",
        "sh-vn-arbor-set-screw-2",
    )
    assert moved["apex set screws lift"] == ("sh-vn-arbor-set-screw-1", "sh-vn-arbor-set-screw-2")
    assert moved["pedestal screws lift"] == (
        "dt-vn-pedestal-hold-down-screw-1",
        "dt-vn-pedestal-hold-down-screw-2",
    )
    assert moved["south end disc"] == ("dt-cylinder-end-disc-1",)
    assert moved["bank spring"] == ("dt-vn-cylinder-bank-spring-1",)
    assert not any(i.name == "dt-cylinder-end-disc-2" for i in _instances())
    assert moved["spring foot screw lifts"] == (FOOT_NAME,)
    assert moved["spring steps east"] == ("dt-pinion-spring-1", FOOT_NAME)
    # The MHA-DT-VN-69 tip dowel is pressed in the block foot (owner ruling
    # 2026-11-07, PR #2248), so it leaves with the block, then drops out of
    # the foot's blind ream past its depth (integration proof
    # 20261109T105251629Z, balloon 11 on the seated stub).
    import dt_cone_tip_block_spec as tip_block

    assert "dt-vn-locating-pin-1" in moved["tip block slides off"]
    assert moved["tip dowel drops"] == ("dt-vn-locating-pin-1",)
    drop = {step.label: step for step in spec.EXPLODE_STEPS}["tip dowel drops"]
    assert drop.axis == "y" and -drop.distance_mm > tip_block.DOWEL_HOLE_DEPTH + 10.0
    # MHA-DT-VN-71 (owner decision C1 keyed, 2026-11-09, PR #1992) leaves with
    # the rotor, stays as the gears slide off it, then rises square to the
    # level cone axis to stand above the largest gear's tips.
    assert "dt-vn-cone-shaft-key-1" in moved["cone rotor withdraws"]
    assert "dt-vn-cone-shaft-key-1" not in moved["cone gears slide toward the tip"]
    assert moved["cone key lifts out"] == ("dt-vn-cone-shaft-key-1",)
    lift = {step.label: step for step in spec.EXPLODE_STEPS}["cone key lifts out"]
    assert (
        lift.axis == "y"
        and lift.distance_mm > cone_spec.outside_dia_mm(120) / 2.0 + 10.0
    )
    assert moved["block screws lift"] == tuple(f"dt-vn-slotted-screw-{i}" for i in range(1, 5))
    # The rig sheet's MHA-DT-VN-57 balloon is pinned to the front block's west screw.
    rig_anchors = drawing.DRIVE_TRAIN_BALLOON_ANCHORS["pinion-rig"]
    assert rig_anchors["dt-vn-slotted-screw"].instance == "dt-vn-slotted-screw-3"
    # MHA-DT-VN-63 balloons the collar pin, the one instance that drives out of
    # its hole; MHA-DT-VN-62 the north screw, lifted clear of its pedestal
    # (integration proof 20261109T105251629Z, balloons 20 and 33).
    assert rig_anchors["dt-vn-pinion-strap-pin"].instance == "dt-vn-pinion-strap-pin-3"
    assert moved["collar pin drives out"] == ("dt-vn-pinion-strap-pin-3",)
    bank_anchors = drawing.DRIVE_TRAIN_BALLOON_ANCHORS["cylinder-bank"]
    pinned = bank_anchors["dt-vn-pedestal-hold-down-screw"].instance
    assert pinned == "dt-vn-pedestal-hold-down-screw-2"
    assert pinned in moved["north pedestal"] and pinned in moved["pedestal screws lift"]


def test_bank_spring_explode_clears_arbor_and_pedestal_in_isometric() -> None:
    import dt_arbor_pedestal_spec as pedestal
    import dt_cylinder_gear_shaft_spec as shaft
    import dt_vn_cylinder_bank_spring_spec as spring

    steps = {step.label: step for step in spec.EXPLODE_STEPS}
    spring_step, pedestal_step = steps["bank spring"], steps["north pedestal"]
    assert spring_step.axis == pedestal_step.axis == "z"
    # Conservative ink envelopes along projected +Z in the standard isometric:
    # an axial millimetre projects sqrt(2/3), a radial one at most 1/sqrt(3).
    # R11's 15 mm spring step overlaps the arbor's envelope.
    axial, radial = math.sqrt(2.0 / 3.0), 1.0 / math.sqrt(3.0)
    spring_south = bank_layout.BANK_SPRING_Z[0] + spring_step.distance_mm
    spring_north = bank_layout.BANK_SPRING_Z[1] + spring_step.distance_mm
    arbor_tip = (
        bank_layout.BACK_STRAP_INNER_Z + pedestal.STRAP_T + bank_layout.ARBOR_DOME_HEIGHT
    )
    pedestal_inner = bank_layout.BACK_STRAP_INNER_Z + pedestal_step.distance_mm
    assert (spring_south - arbor_tip) * axial > (
        spring.OD / 2.0 + shaft.SHAFT_RADIUS
    ) * radial
    assert (pedestal_inner - spring_north) * axial > (
        spring.OD / 2.0 + pedestal.TOP_RADIUS
    ) * radial


def test_explode_plan_refuses_unknown_retired_and_missing_families() -> None:
    with pytest.raises(ValueError, match="does not classify"):
        spec.plan_explode([*_instances(), spec.Instance("widget-1", "widget", (0, 0, 0))])
    with pytest.raises(ValueError, match="does not classify"):
        spec.plan_explode(
            [*_instances(), spec.Instance("pinion-handle-pin-1", "pinion-handle-pin", (0, 0, 0))]
        )
    census = [i for i in _instances() if i.stem != "dt-crank-handle"]
    with pytest.raises(ValueError, match="absent from the model"):
        spec.plan_explode(census)


def test_built_families_are_no_longer_pending() -> None:
    """A family the builder inserts has landed: it must not stay excused as pending."""
    assert not _builder_stems() & spec.PENDING_STEMS


def test_crank_hub_families_explode_with_the_crank_arm() -> None:
    census = _instances()
    assert {"dt-crank-hub", "dt-vn-crank-hub-pin"} <= {i.stem for i in census}
    moved = {step.label: names for step, names in spec.plan_explode(census)}
    assert {"dt-crank-hub-1", "dt-vn-crank-hub-pin-1"} <= set(moved["crank arm group"])


def test_explode_families_are_either_moved_or_stationary_never_both() -> None:
    moved = {spec.component_stem(key) for step in spec.EXPLODE_STEPS for key in step.stems}
    assert not moved & spec.STATIONARY_STEMS
    assert moved | spec.STATIONARY_STEMS == spec.classified_stems()


def test_clusters_partition_every_instance_once() -> None:
    census = _instances()
    members = drawing.cluster_members(census)
    flat = [name for names in members.values() for name in names]
    assert sorted(flat) == sorted(i.name for i in census)
    assert FOOT_NAME in members["pinion-rig"]
    assert {"dt-vn-pedestal-hold-down-screw-1", "dt-vn-pedestal-hold-down-screw-2"} <= set(
        members["cylinder-bank"]
    )


def test_source_refusals_and_bom_order() -> None:
    counts = drawing.instance_counts(_instances())
    assert drawing.source_violations(counts) == []
    assert drawing.bom_components(counts)[0] == "dt-cylinder-gear-shaft"
    assert set(drawing.bom_components(counts)) == set(counts)
    del counts["dt-crank-arm"]
    assert "dt-crank-arm" in drawing.source_violations(counts)[0]
    assert drawing.source_violations({**counts, "dt-crank-arm": 1, "pinion-handle-pin": 1})


def test_cone_station_rows_run_front_to_back() -> None:
    rows = drawing.cone_station_rows([(30.0, "T006"), (-25.0, "T120"), (0.0, "T060")])
    assert rows == [(1, "T120"), (2, "T060"), (3, "T006")]
    table = drawing.code_key_text(rows, 3).splitlines()
    assert table[1] == "TNNN = MHA-DT-03 WITH NNN TEETH, BY STATION, FRONT TO BACK:"
    assert table[2].startswith("STN  1  T120")
    assert table[-2] == "GEAR 0-2 = MHA-DT-12 FROM THE FRONT, GEAR 0 ON MHA-DT-26."
    # Steps 1T and 2C's comb is a shop tool with no BOM row: the key names it
    # and defines the BLADE the steps cite (machinist review of bd81283964).
    assert table[-1] == "MHA-DT-03-TL-02 = PHASING COMB, A BLADE IN A TOOTH SPACE OF EACH GEAR."
    # Owner, 2026-11-14 (#2734): the comb is a U clipped over the tip of the
    # cone standing on its journal, both arms on T036; the journal stands in
    # sheet 16 row 21's V-block from 1S (Codjiflo review of #3324).
    steps = " ".join(drawing.CONE_CRANK_STEPS.split())
    assert steps[steps.index("1T. ") :].startswith(
        "1T. CLIP MHA-DT-03-TL-02 OVER THE TIP, MHA-DT-04 STILL STANDING IN THE"
        " V-BLOCK, BOTH ARMS ON T036, T030'S BLADE BESIDE THE KEY."
    )
    # Round 2 waxes the blades again: its wet joints sit beside them.
    assert steps[steps.index("2C. ") :].startswith(
        "2C. CLIP MHA-DT-03-TL-02, BLADES WAXED AGAIN, OVER THE TIP, BOTH ARMS"
        " ON T036, T030'S BLADE BESIDE THE KEY."
    )
    for head in ("1X", "2F"):
        step = steps[steps.index(f"{head}. ") :]
        assert step.split(".", 2)[1].endswith("BOTH ARMS ON T036"), step[:120]
    # #2473 (owner ruling 2026-11-22, option G): the pivot is tapped true
    # before the comb goes on, read after cure with the comb off and before
    # the post is assembled (2J on), and a failed reading has its remedy.
    pivot_row = drawing.acceptance_ref("pivot-runout")
    order = [steps.index(f"{head}. ") for head in ("2A", "2B", "2C", "2D", "2E", "2F", "2G", "2H", "2J")]
    assert order == sorted(order)
    assert steps[order[1] : order[2]].strip() == (
        "2B. HOLDING MHA-DT-37 HOME, TAP ITS PIVOT TRUE ON AN INDICATOR BEFORE"
        f" IT GRABS ({pivot_row})."
    )
    assert steps[order[3] : order[4]].strip() == (
        "2D. REMOVE MHA-DT-03-TL-02 ONCE THE BONDS GRAB, MHA-DT-37 HELD HOME ON"
        " T024 UNTIL THEN."
    )
    gear_row = drawing.acceptance_ref("spigot-gear-runout")
    # Owner ruling 2026-11-24, audit part 2 C5: the after-cure readings are a
    # record, taken before the comb check so the strip and re-bond follows
    # that check (rule 22), and a gear that hesitates in check 4R's run.
    assert steps[order[4] : order[5]].strip() == (
        f"2E. ONCE CURED, RECORD THE RUNOUT ABOUT MHA-DT-04 OF THE MHA-DT-37 PIVOT ({pivot_row})"
        f" AND OF T012'S AND T018'S TEETH ({gear_row})."
    )
    assert steps[order[6] : order[7]].startswith(
        "2G. IF IT FAILS, OR A GEAR HESITATES IN CHECK 4R, AT 250 DEG C TAKE MHA-DT-37,"
    )
    assert steps[steps.index("1W. ") :].startswith("1W. RECORD T024'S TOOTH RUNOUT")
    assert steps[steps.index("1Y. ") :].startswith("1Y. IF IT FAILS, TAKE T024 OFF")
    check = " ".join(drawing.CHECKS.split())
    assert "MUST NEVER BIND OR HESITATE" in check
    assert "4S. IF ONE BINDS, LOOSEN MHA-DT-VN-51 THERE (ONE HESITATES: STEP 2G)." in check
    assert steps[order[7] : order[8]].strip().endswith("FOR A REDO FROM 1L.")
    assert steps[order[8] :].startswith("2J. ALIGN THE MHA-DT-05 COUNTERBORES")
    (row,) = (r for r in drawing.ACCEPTANCE_TABLE_ROWS if r[2].startswith("MHA-DT-37 PIVOT"))
    assert row[1:] == (
        "2B, 2E",
        "MHA-DT-37 PIVOT, MHA-DT-04 ON END ON A V-BLOCK",
        ".0020 TIR MAX",
        "TEST INDICATOR",
    )
    # Owner ruling 2026-11-22 (#2473): T012 and T018 are read after cure in
    # the same setup, as T024 is; a record since C5 (2026-11-24).
    (row,) = (r for r in drawing.ACCEPTANCE_TABLE_ROWS if r[2].startswith("T012 AND T018"))
    assert row[1:] == (
        "2E",
        "T012 AND T018, \u00d8.040 GAUGE PIN, SETUP AS T024",
        "RECORD EACH SPACE",
        "TEST INDICATOR",
    )
    assert "MHA-DT-03-TL-02 BLADES WITH" in steps


def test_bom_split_keeps_the_first_column_no_taller() -> None:
    assert drawing.bom_split_row(39) == 19
    assert drawing.bom_split_row(42) == 21
    with pytest.raises(ValueError):
        drawing.bom_split_row(1)


def test_bom_reference_view_and_metadata_fit_below_the_first_piece() -> None:
    # Historical header height is an offline budget input, not native-head proof.
    data_rows = len(drawing.bom_components(drawing.instance_counts(_instances())))
    first_rows = drawing.bom_split_row(data_rows)
    first_height = 0.0102 + first_rows * drawing.BOM_ROW_HEIGHT
    first_bottom = drawing.BOM_ANCHOR[1] - first_height
    assert drawing.bom_extent_violations(
        drawing.BOM_ANCHOR, drawing.BOM_COLUMN_WIDTH, first_height
    ) == []
    second_height = 0.0102 + (data_rows - first_rows) * drawing.BOM_ROW_HEIGHT
    assert drawing.bom_extent_violations(
        (drawing.BOM_SECOND_COLUMN_X, drawing.BOM_ANCHOR[1]),
        drawing.BOM_COLUMN_WIDTH,
        second_height,
    ) == []
    half = drawing.REFERENCE_ISO_HALF_OUTLINE
    cx, cy = drawing.BOM_REFERENCE_ISO_CENTER
    # GetOutline can extend farther below the requested centre than above it.
    # Exercise that asymmetric consumer boundary, not just a centred square.
    outline = (cx - half, cy - half - 0.001, cx + half, cy + half)
    assert drawing.bom_reference_iso_violations(outline) == []
    assert outline[3] < first_bottom
    assert outline[2] < drawing.BOM_REFERENCE_NOTE_FIELD[0]
    metadata = drawing.NoteField(
        2,
        "BOM metadata",
        drawing.BOM_REFERENCE_NOTE_FIELD,
        (("BOM reference and station pointer", drawing.BOM_REFERENCE_NOTES),),
    )
    assert _spare(metadata) >= 0
    assert drawing.BOM_REFERENCE_NOTE_FIELD[1] < first_bottom
    onto_bom = (outline[0], outline[1] + 0.010, outline[2], outline[3] + 0.010)
    assert drawing.bom_reference_iso_violations(onto_bom)
    onto_metadata = (outline[0] + 0.020, outline[1], outline[2] + 0.020, outline[3])
    assert drawing.bom_reference_iso_violations(onto_metadata)
    below_view_field = (outline[0], outline[1] - 0.002, outline[2], outline[3])
    assert drawing.bom_reference_iso_violations(below_view_field)


def test_bom_budget_refuses_the_title_block_and_sheet_edges() -> None:
    assert drawing.bom_extent_violations(drawing.BOM_ANCHOR, 0.164, 0.130) == []
    assert drawing.bom_extent_violations((0.300, 0.100), 0.100, 0.050)
    assert drawing.bom_extent_violations((0.001, 0.200), 0.100, 0.050)
    # A grown first piece must not consume the reserved reference-view field.
    assert drawing.bom_extent_violations(
        drawing.BOM_ANCHOR,
        drawing.BOM_COLUMN_WIDTH,
        drawing.BOM_ANCHOR[1] - drawing.BOM_REFERENCE_FIELD[1] + 0.001,
    )


def test_bank_setting_caption_accepts_native_r4_extent_not_exact_anchor_target() -> None:
    # Native R4, source 957dc7b2fc79, 20261020T223233Z failure capture:
    # Its rendered readback differed harmlessly from the requested corner.
    # That point is not anchor_note's postcondition; actual air is 4.1845 mm.
    target = (0.25288663532950506, 0.1265405874866539)
    extent = (
        0.25307234782608695, 0.12206696321070235,
        0.31073714381270906, 0.12635608026755854,
    )
    outline = (0.099, target[1] + 0.004, 0.311, 0.2336)
    assert abs(extent[0] - target[0]) > drawing.NOTE_ANCHOR_SETTLE
    assert abs(extent[3] - target[1]) > drawing.NOTE_ANCHOR_SETTLE
    assert drawing.bank_setting_caption_violations(extent, outline) == []
    # Position stability alone cannot accept a caption that actually moves
    # onto the view, or one whose measured air drops below the unchanged 4 mm.
    for top in (outline[1] + 0.001, outline[1] - 0.00399):
        assert drawing.bank_setting_caption_violations((*extent[:3], top), outline)


def test_bank_setting_caption_margin_clears_native_r6_failure_and_printed_border() -> None:
    # Native R6 actual extent (source 881d1eddc90d, 20261020T225444Z).
    # The unchanged view's R3 outline bottom was reported as 31.1 mm;
    # its 0.05 mm reporting precision cannot change either result below.
    extent = (
        0.06864031438127086, 0.022464133779264206,
        0.14107873578595315, 0.027229819397993293,
    )
    outline = (0.061, 0.0311, 0.149, 0.1189)
    assert drawing.bank_setting_caption_violations(extent, outline)
    # Moving the placement target from 4 to 8 mm drops the whole caption
    # another 4 mm; this is an offline placement envelope, not native proof.
    drop = drawing.VIEW_CAPTION_GAP
    moved = (extent[0], extent[1] - drop, extent[2], extent[3] - drop)
    assert drawing.bank_setting_caption_violations(moved, outline) == []
    # Actual R4 sheet-13 PDF frame: centre y35.90001 pt, stroke1.41733 pt.
    # Check its INNER ink edge, more conservative than 12.7 mm zone metadata.
    border_inner = (35.90001 + 1.41733 / 2.0) * 25.4 / 72.0 / 1000.0
    assert moved[1] - border_inner > 0.0055
    field = (0.0127, 0.2667, 0.4191, border_inner)
    assert drawing.note_field_violations(moved, field) == []
    # A further drop through the frame is still refused by containment.
    through_frame = (moved[0], border_inner - 0.001, moved[2], moved[3])
    assert drawing.note_field_violations(through_frame, field)


@pytest.mark.parametrize(
    ("extent", "outline"),
    (
        # Actual R3 native caption/view boxes, the two original real overlaps.
        ((0.1649, 0.1407, 0.2226, 0.1454), (0.099, 0.1305, 0.311, 0.2336)),
        ((0.0596, 0.0306, 0.1325, 0.0353), (0.061, 0.0311, 0.149, 0.1189)),
    ),
)
def test_bank_setting_caption_refuses_recorded_native_r3_collisions(extent, outline) -> None:
    assert drawing.bank_setting_caption_violations(extent, outline)


def test_bank_setting_letter_requires_whole_box_clear_of_circle() -> None:
    centre, radius = (0.13275, 0.195), 0.008
    clear = (0.113, 0.211, 0.117, 0.216)
    assert drawing.bank_setting_letter_violations(clear, centre, radius) == []
    # Each independent edge must retain 4 mm; readable/stable position alone
    # does not prove the identifier is outside its view-owned sketch circle.
    right_close = (*clear[:2], centre[0] - radius - 0.00399, clear[3])
    below = (clear[0], centre[1] + radius + 0.00399, *clear[2:])
    assert drawing.bank_setting_letter_violations(right_close, centre, radius)
    assert drawing.bank_setting_letter_violations(below, centre, radius)


def test_balloon_attachment_gate_names_every_mismatch() -> None:
    records = [("B1", "1", ("dt-crank-arm",)), ("B2", "3", ("dt-crank-pin",)), ("B3", "4", ())]
    findings = drawing.balloon_attachment_violations(
        records, {"dt-crank-arm": "1", "dt-crank-pin": "2", "dt-crank-handle": "5"}
    )
    assert any("shows item 3" in f for f in findings)
    assert any("attaches to []" in f for f in findings)
    assert any("dt-crank-handle" in f for f in findings)


@pytest.mark.parametrize("item", ["?", "", "  "])
def test_balloon_attachment_gate_refuses_an_unresolved_item(item) -> None:
    """A balloon whose component no longer resolves to a BOM row prints ``?``
    (the feature-suppression preview's did): the gate names it even when its
    leader lands on the right component."""
    findings = drawing.balloon_attachment_violations(
        [("B1", item, ("dt-crank-arm",))], {"dt-crank-arm": "1"}
    )
    assert any("B1 shows unresolved item" in f for f in findings)


def test_note_fields_and_ring_fit() -> None:
    field = drawing.NOTE_FIELD_LEFT
    assert drawing.note_field_violations((0.020, 0.100, 0.200, 0.250), field) == []
    assert len(drawing.note_field_violations((0.010, 0.020, 0.300, 0.300), field)) == 4
    shift, overflows = drawing.ring_fit_shift((0.1, 0.1, 0.2, 0.2), (0.0, 0.0, 0.5, 0.5), grow=0.01)
    assert shift == pytest.approx((0.1, 0.1)) and overflows == []


def _title_block_keep_out() -> tuple[float, float, float, float]:
    template = drawing.DRAWING_TEMPLATES[drawing.SPEC.layout]
    clearance = drawing.CLUSTER_TITLE_BLOCK_CLEARANCE
    return (
        template.title_block_left_m - clearance,
        0.0,
        template.width_m,
        template.title_block_top_m + clearance,
    )


def _ring_slide(outline_mm: tuple[float, ...]) -> tuple[float, tuple[float, float]]:
    outline = tuple(value / 1000.0 for value in outline_mm)
    shift, _overflows, slide = drawing.cluster_ring_fit(outline)
    return slide, shift


def test_the_cone_crank_ring_slides_off_the_title_block() -> None:
    """rim-124f's cone-crank outline (leaf telemetry, drawing.cluster_ring_fit):
    centred, the ring's low arc put items 5 and 33 on the title block.  After
    the slide no balloon on the ellipse reaches it, and the ring stays on the
    sheet's left side of its region."""
    outline_mm = (126.422, 110.834, 286.493, 268.479)
    slide, shift = _ring_slide(outline_mm)
    assert slide < 0.0
    outline = tuple(value / 1000.0 for value in outline_mm)
    margin, r = drawing.CLUSTER_BALLOON_MARGIN, drawing.BALLOON_DIAMETER / 2.0
    cx = (outline[0] + outline[2]) / 2.0 + shift[0]
    cy = (outline[1] + outline[3]) / 2.0 + shift[1]
    rx = (outline[2] - outline[0]) / 2.0 + margin
    ry = (outline[3] - outline[1]) / 2.0 + margin
    left, _bottom, _right, top = _title_block_keep_out()
    for k in range(3600):
        a = 2.0 * math.pi * k / 3600
        x, y = cx + rx * math.cos(a), cy + ry * math.sin(a)
        assert not (x + r > left + 1e-9 and y - r < top - 1e-9), (x, y)
    assert cx - rx - r >= drawing.CLUSTER_RING_REGION[0]


@pytest.mark.parametrize(
    "outline_mm",
    [
        (88.871, 68.887, 257.678, 210.050),  # cylinder bank, rim-124f
        (145.842, 92.169, 280.976, 215.724),  # pinion rig, rim-124f
    ],
)
def test_a_ring_clear_of_the_title_block_stays_centred(outline_mm: tuple[float, ...]) -> None:
    slide, _shift = _ring_slide(outline_mm)
    assert slide == 0.0


# cascade-3's cone-crank outline at 1:3 (the same one rim-124f read): its ring
# put balloons '42' and '43' on sheet 4's two-line heading (leaf log, layout
# audit of 4e7ab7ca0; heading box bottom 254.3 mm).
CONE_CRANK_OUTLINE_1_3 = (0.126422, 0.110834, 0.286493, 0.268479)
CYLINDER_BANK_OUTLINE_2_3 = (0.088871, 0.068887, 0.257678, 0.210050)
PINION_RIG_OUTLINE_1_2 = (0.145842, 0.092169, 0.280976, 0.215724)


def test_the_ring_reach_is_where_the_balloon_ink_lands() -> None:
    """``_spread_balloons`` puts each circle CENTRE on the ellipse ``margin``
    outside the outline, so the ink reaches margin + radius.  cascade-3's
    audit read balloon '42' at y [246.1, 255.5] mm, centred at the ellipse's
    top vertex; the estimate must land there, not a radius higher."""
    outline = CONE_CRANK_OUTLINE_1_3
    shift, _overflows, _slide = drawing.cluster_ring_fit(outline)
    ink_top = outline[3] + shift[1] + drawing.CLUSTER_RING_REACH
    assert ink_top * 1000.0 == pytest.approx(255.5, abs=0.5)


def test_every_cluster_prefers_a_scale_on_the_ladder() -> None:
    ladder = drawing.CLUSTER_SCALE_LADDER
    ratios = [n / d for n, d in ladder]
    assert ratios == sorted(ratios, reverse=True) and len(set(ratios)) == len(ratios)
    assert set(drawing.CLUSTER_SCALES.values()) <= set(ladder)


def test_an_overflowing_cone_crank_ring_steps_down_to_the_first_fitting_scale() -> None:
    """At 1:3 the ring is 191.6 mm tall against a 176 mm region; at 1:4 it fits
    centred, clear of the heading and the title block."""
    _shift, overflows, _slide = drawing.cluster_ring_fit(CONE_CRANK_OUTLINE_1_3)
    assert any(finding.startswith("height") for finding in overflows)
    scale = drawing.cluster_ring_scale(CONE_CRANK_OUTLINE_1_3, (1.0, 3.0), label="cone-crank")
    assert scale == (1.0, 4.0)
    k = (1.0 / 4.0) / (1.0 / 3.0)
    x0, y0, x1, y1 = CONE_CRANK_OUTLINE_1_3
    cx, cy, hw, hh = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2 * k, (y1 - y0) / 2 * k
    _shift, overflows, slide = drawing.cluster_ring_fit((cx - hw, cy - hh, cx + hw, cy + hh))
    assert overflows == [] and slide == 0.0


@pytest.mark.parametrize(
    ("outline", "preferred"),
    [(CYLINDER_BANK_OUTLINE_2_3, (2.0, 3.0)), (PINION_RIG_OUTLINE_1_2, (1.0, 2.0))],
)
def test_a_ring_that_fits_keeps_its_preferred_scale(outline, preferred) -> None:
    assert drawing.cluster_ring_scale(outline, preferred, label="fits") == preferred


def test_the_fit_does_not_depend_on_where_the_view_landed() -> None:
    moved = tuple(value + 0.050 for value in CONE_CRANK_OUTLINE_1_3)
    assert drawing.cluster_ring_scale(moved, (1.0, 3.0), label="moved") == (1.0, 4.0)


def test_a_ring_no_ladder_scale_fits_raises_naming_the_cluster_and_overflow() -> None:
    # 1.1 m tall at 1:3 is still 367 mm at 1:5.
    outline = (0.100, 0.0, 0.200, 1.100)
    with pytest.raises(ValueError, match=r"cone-crank.*1:5: height"):
        drawing.cluster_ring_scale(outline, (1.0, 3.0), label="cone-crank")


def test_a_preferred_scale_off_the_ladder_is_refused() -> None:
    with pytest.raises(ValueError, match="not on the ladder"):
        drawing.cluster_ring_scale(CONE_CRANK_OUTLINE_1_3, (3.0, 7.0), label="odd")


# R9 (20261107T062630010Z) cluster_ring_fit telemetry: the pinion rig's
# outline at the 1:3 it stepped down to; round 10 (20261107T084706335Z) the
# cone set's at 1:2.5.
PINION_RIG_OUTLINE_R9_1_3 = (0.1681, 0.1106, 0.2669, 0.2094)
CONE_SET_OUTLINE_R10_1_2_5 = (0.0761, 0.0565, 0.2189, 0.2215)


def _rescaled(
    outline: tuple[float, ...], scale: tuple[float, float], to: tuple[float, float]
) -> tuple[float, float, float, float]:
    x0, y0, x1, y1 = outline
    k = (to[0] / to[1]) / (scale[0] / scale[1])
    cx, cy, hw, hh = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2 * k, (y1 - y0) / 2 * k
    return (cx - hw, cy - hh, cx + hw, cy + hh)


# The cone set's own ring fits at 1:2.5; it prints at 1:3 since detail F
# (#2640) took the sheet's right half (fit_cluster_ring keeps its room).
RAISED_CASES = [
    ("cone-set", CONE_SET_OUTLINE_R10_1_2_5, (1.0, 2.5), (1.0, 3.0), 0.040),
    ("pinion-rig", PINION_RIG_OUTLINE_R9_1_3, (1.0, 3.0), (1.0, 2.0), 0.0),
]


def test_the_cone_set_steps_down_until_detail_f_has_room() -> None:
    """Run 20261123T194841143Z (#3478): the cone set proved its ring at 1:2.5,
    which left 71.8 mm right of it, and no detail scale fitted (80.4 mm at the
    ladder's last).  The ring fit itself now refuses a scale that leaves the
    detail less than its narrowest ring."""
    at_1_2_5 = CONE_SET_OUTLINE_R10_1_2_5
    assert drawing.raised_ring_fit(at_1_2_5, "cone-set")[1] == []
    _shift, overflows, _slide = drawing.fit_cluster_ring(at_1_2_5, "cone-set")
    assert len(overflows) == 1 and f"detail {drawing.CONE_TIP_DETAIL_LETTER} room" in overflows[0]
    at_1_3 = _rescaled(at_1_2_5, (1.0, 2.5), (1.0, 3.0))
    shift, overflows, _slide = drawing.fit_cluster_ring(at_1_3, "cone-set")
    assert overflows == []
    region = drawing.cone_tip_detail_region(
        (at_1_3[0] + shift[0], at_1_3[1] + shift[1], at_1_3[2] + shift[0], at_1_3[3] + shift[1])
    )
    assert region[2] - region[0] >= drawing.CONE_TIP_DETAIL_MIN_RING_WIDTH
    # The rig has no detail: its fit is the raised ring's alone.
    rig = _rescaled(PINION_RIG_OUTLINE_R9_1_3, (1.0, 3.0), (1.0, 2.0))
    assert drawing.fit_cluster_ring(rig, "pinion-rig") == drawing.raised_ring_fit(rig, "pinion-rig")


@pytest.mark.parametrize(("cluster", "outline", "read_at", "expected", "_off"), RAISED_CASES[1:])
def test_the_cone_set_and_rig_rise_to_a_readable_scale(
    cluster: str,
    outline: tuple[float, ...],
    read_at: tuple[float, float],
    expected: tuple[float, float],
    _off: float,
) -> None:
    """Rubric sample round 9 printed both at 1:3, too small to read; raised
    over the title block, the ladder from the 1:2 preference stops at 1:2
    (rig).  The cone set stays at 1:3: its tip parts read in detail F."""
    preferred = _rescaled(outline, read_at, (1.0, 2.0))
    assert drawing.cluster_ring_scale(preferred, (1.0, 2.0), label=cluster, cluster=cluster) == expected
    # The shared region would not have held it.
    assert drawing.cluster_ring_scale(preferred, (1.0, 2.0), label=cluster) != expected


@pytest.mark.parametrize(("cluster", "outline", "read_at", "scale", "off_centre"), RAISED_CASES)
def test_a_raised_ring_stands_near_the_centre_clear_of_heading_and_title_block(
    cluster: str,
    outline: tuple[float, ...],
    read_at: tuple[float, float],
    scale: tuple[float, float],
    off_centre: float,
) -> None:
    """Round 12 (20261107T121145212Z, gating 3/3, rule 15): slid left of the
    title block, both rings left the sheet's right half empty.  Raised, the
    rig stands centred and the cone set within 40 mm of centre, and neither
    the view's box nor any balloon the ellipse can carry touches the title
    block, the sheet heading or the frame."""
    fitted = _rescaled(outline, read_at, scale)
    shift, overflows, slide = drawing.raised_ring_fit(fitted, cluster)
    assert overflows == []
    assert 0.0 <= slide <= off_centre + 1e-9
    margin, r = drawing.CLUSTER_BALLOON_MARGINS[cluster], drawing.BALLOON_DIAMETER / 2.0
    box = (fitted[0] + shift[0], fitted[1] + shift[1], fitted[2] + shift[0], fitted[3] + shift[1])
    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    rx, ry = (box[2] - box[0]) / 2 + margin, (box[3] - box[1]) / 2 + margin
    keep_outs = (_title_block_keep_out(), drawing.cluster_heading_keep_out(cluster))
    shapes = [box] + [
        (cx + rx * math.cos(a) - r, cy + ry * math.sin(a) - r, cx + rx * math.cos(a) + r, cy + ry * math.sin(a) + r)
        for a in (math.radians(d / 4) for d in range(1440))
    ]
    for shape in shapes:
        for keep in keep_outs:
            assert not drawing._boxes_overlap(shape, keep), (shape, keep)
    assert cy + ry + r <= drawing.RAISED_RING_TOP + 1e-9


def test_the_cluster_heading_keep_out_covers_round_12s_printed_heading() -> None:
    """Round 12's sheet 4 heading printed to x 188.2 mm, down to y 253.5 mm."""
    left, bottom, right, _top = drawing.cluster_heading_keep_out("cone-set")
    clearance = drawing.CLUSTER_TITLE_BLOCK_CLEARANCE
    assert right - clearance >= 0.1882 and bottom + clearance <= 0.2535


def test_the_bank_and_crank_keep_their_proven_ring_region() -> None:
    for cluster in ("cylinder-bank", "crank"):
        assert drawing.CLUSTER_RING_REGIONS[cluster] == drawing.CLUSTER_RING_REGION
        assert cluster not in drawing.RAISED_RING_CLUSTERS
        assert drawing.CLUSTER_BALLOON_MARGINS[cluster] == drawing.CLUSTER_BALLOON_MARGIN
    assert set(drawing.CLUSTER_RING_REGIONS) == set(drawing.CLUSTER_SCALES)
    assert set(drawing.CLUSTER_BALLOON_MARGINS) == set(drawing.CLUSTER_SCALES)


def test_view_labels_print_a_scale_only_where_it_differs_from_the_sheet() -> None:
    """Rule 9 (rubric sample round 11 #0): every repeated label scale went."""
    assert drawing.view_label("ISOMETRIC", (1.0, 3.0), (1.0, 3.0)) == "ISOMETRIC"
    assert drawing.view_label("DETAIL A", (4.0, 1.0), (1.0, 1.0)) == "DETAIL A 4:1"
    assert drawing.SHEET_SCALES[drawing.SHEET_NAMES[drawing.BANK_SETTINGS_SHEET - 1]] == (1.0, 1.0)
    for text in (drawing.BANK_VIEW_CAPTION, drawing.DRUM_VIEW_CAPTION, drawing.BOM_REFERENCE_NOTES):
        assert not re.search(r"\b\d+(?:\.\d+)?:\d+(?:\.\d+)?\b", text), text


def test_the_sheet_scales_follow_the_chosen_cluster_and_full_detail_scales() -> None:
    chosen = {**drawing.CLUSTER_SCALES, "crank": (1.0, 4.0)}
    scales = drawing.package_sheet_scales(chosen, (2.0, 3.0))
    assert set(scales) == set(drawing.SHEET_NAMES)
    assert scales[drawing.SHEET_NAMES[drawing.CLUSTER_SHEETS["crank"] - 1]] == (1.0, 4.0)
    assert scales[drawing.SHEET_NAMES[drawing.FULL_DETAIL_SHEET - 1]] == (2.0, 3.0)
    assert drawing.package_sheet_scales(drawing.CLUSTER_SCALES) == drawing.SHEET_SCALES


# The cone set's view as fitted at 1:3 on sheet 4 (machinist review r8 of
# PR #2640, run 20261112T124601584Z, layout audit outline).
R8_CONE_SET_OUTLINE = (0.1464, 0.0820, 0.2696, 0.2227)


def test_the_cone_tip_detail_balloons_the_tip_families_the_1_3_view_drops() -> None:
    """r3, r7 and r8 of PR #2640: balloons 37 and 38 met on one tip at 1:3.
    The six tip families are the cone set's own, each has a frozen anchor,
    and the 1:3 view keeps every other cone-set family, so each BOM item is
    still ballooned once on sheet 4."""
    facts = _drawing_facts()
    names = drawing.cone_tip_detail_names(facts)
    assert names <= frozenset(facts.clusters["cone-set"])
    shown = {i.stem for i in facts.instances if i.name in names}
    assert shown == drawing.CONE_TIP_DETAIL_STEMS
    assert {"dt-cone-tip-gear", "dt-cone-tip-bushing"} <= shown
    assert drawing.CONE_TIP_DETAIL_STEMS <= set(drawing.DRIVE_TRAIN_BALLOON_ANCHORS["cone-set"])
    cone_set = {i.stem for i in facts.instances if i.name in facts.clusters["cone-set"]}
    assert cone_set - drawing.CONE_TIP_DETAIL_STEMS, "the 1:3 view keeps balloons"
    arrows = (letter for letter, _y in drawing.SHEET1_VIEW_ARROWS)
    taken = {drawing.FULL_DETAIL_VIEW_LETTER, "A", "B", *arrows}
    assert drawing.CONE_TIP_DETAIL_LETTER not in taken


def test_a_cone_tip_detail_with_no_tip_family_in_the_cone_set_is_refused() -> None:
    facts = _drawing_facts()
    facts.clusters = {**facts.clusters, "cone-set": ()}
    with pytest.raises(RuntimeError, match="cone tip detail"):
        drawing.cone_tip_detail_names(facts)


def _ring(box: tuple[float, ...], reach: float) -> tuple[float, ...]:
    return (box[0] - reach, box[1] - reach, box[2] + reach, box[3] + reach)


@pytest.mark.parametrize(
    ("size_mm", "expected"),
    [((52.0, 85.0), (1.0, 1.0)), ((120.0, 120.0), (2.0, 3.0)), ((180.0, 300.0), (1.0, 2.0))],
)
def test_the_cone_tip_detail_ring_fits_right_of_the_cone_set_ring(size_mm, expected) -> None:
    """The detail takes the largest ladder scale whose balloon ring stands in
    the empty right half: clear of the 1:3 view's ring, the title block plus
    its caption line, and the frame.  r8's tip parts spanned about 17 x 28 mm
    at 1:3, so they read at 1:1."""
    region = drawing.cone_tip_detail_region(R8_CONE_SET_OUTLINE)
    template = drawing.DRAWING_TEMPLATES[drawing.SPEC.layout]
    parent_reach = drawing.CLUSTER_BALLOON_MARGINS["cone-set"] + drawing.BALLOON_DIAMETER / 2
    assert region[0] > R8_CONE_SET_OUTLINE[2] + parent_reach
    assert region[1] >= template.title_block_top_m + drawing.CLUSTER_TITLE_BLOCK_CLEARANCE
    assert region[2] < template.width_m - 0.0127 and region[3] < template.height_m - 0.0127
    outline = _outline_mm(*size_mm)
    scale, shift = drawing.cone_tip_detail_fit(outline, (1.0, 1.0), region)
    assert scale == expected
    k = scale[0] / scale[1]
    cx, cy = (outline[0] + outline[2]) / 2, (outline[1] + outline[3]) / 2
    hw, hh = (outline[2] - outline[0]) / 2 * k, (outline[3] - outline[1]) / 2 * k
    box = (cx - hw + shift[0], cy - hh + shift[1], cx + hw + shift[0], cy + hh + shift[1])
    ring = _ring(box, drawing.CONE_TIP_DETAIL_REACH)
    assert region[0] - 1e-9 <= ring[0] and ring[2] <= region[2] + 1e-9
    assert region[1] - 1e-9 <= ring[1] and ring[3] <= region[3] + 1e-9


def test_a_cone_tip_detail_no_ladder_scale_fits_raises() -> None:
    region = drawing.cone_tip_detail_region(R8_CONE_SET_OUTLINE)
    with pytest.raises(ValueError, match="cone tip detail.*1:2"):
        drawing.cone_tip_detail_fit(_outline_mm(400.0, 400.0), (1.0, 1.0), region)


def test_the_cone_tip_boundary_circles_the_detail_parts_on_the_1_3_view() -> None:
    """A point of the detail lies, from the model origin's projection, one
    third as far on the 1:3 view; the circle holds the parts' whole box."""
    outline = (0.300, 0.100, 0.352, 0.185)
    detail_origin = (0.296, 0.1545)
    parent_origin = (0.180, 0.120)
    ratio = 1.0 / 3.0
    centre, radius = drawing.cone_tip_detail_boundary(outline, detail_origin, parent_origin, ratio)
    assert centre == pytest.approx((0.190, 0.116))
    for x in (outline[0], outline[2]):
        for y in (outline[1], outline[3]):
            mapped = (
                parent_origin[0] + (x - detail_origin[0]) * ratio,
                parent_origin[1] + (y - detail_origin[1]) * ratio,
            )
            gap = radius - math.dist(mapped, centre)
            assert gap == pytest.approx(drawing.CONE_TIP_DETAIL_BOUNDARY_PAD)


# r9 (run 20261112T135520653Z): sheet 4's boundary circle and the letter box
# the audit read, which balloon 15 overlapped at 225 degrees.
R9_BOUNDARY = ((0.1820, 0.1150), 0.0340)
R9_LETTER_SIZE = (0.0023, 0.0048)


def _letter_box(corner: tuple[float, float]) -> tuple[float, float, float, float]:
    w, h = R9_LETTER_SIZE
    return (corner[0], corner[1] - h, corner[0] + w, corner[1])


def test_the_boundary_letter_stands_just_outside_its_circle_on_the_preferred_side() -> None:
    (cx, cy), r = R9_BOUNDARY
    box = _letter_box(drawing.cone_tip_letter_corner((cx, cy), r, R9_LETTER_SIZE, [], []))
    mid = ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)
    assert mid[0] < cx and mid[1] < cy, "lower left first"
    corners = [(x, y) for x in (box[0], box[2]) for y in (box[1], box[3])]
    offset = drawing.CONE_TIP_DETAIL_LETTER_OFFSET
    assert min(math.dist(c, (cx, cy)) for c in corners) >= r + offset - 1e-9
    assert math.dist(mid, (cx, cy)) < r + 0.01, "it stays beside its circle"


def test_the_boundary_letter_moves_off_a_balloon_or_leader_on_its_side() -> None:
    """r9's balloon 15 sat on the lower-left side; a leader crossing the next
    side moves the letter on again, and it never touches either."""
    (cx, cy), r = R9_BOUNDARY
    first = _letter_box(drawing.cone_tip_letter_corner((cx, cy), r, R9_LETTER_SIZE, [], []))
    balloon = ((first[0] + first[2]) / 2 + 0.004, (first[1] + first[3]) / 2)
    second = _letter_box(
        drawing.cone_tip_letter_corner((cx, cy), r, R9_LETTER_SIZE, [balloon], [])
    )
    assert second != first
    br = drawing.BALLOON_DIAMETER / 2
    keep = (balloon[0] - br, balloon[1] - br, balloon[0] + br, balloon[1] + br)
    assert not drawing._boxes_overlap(second, keep)
    mid = ((second[0] + second[2]) / 2, (second[1] + second[3]) / 2)
    leader = drawing.LeaderSegment(
        "L", "note", mid[0] - 0.01, mid[1] - 0.01, mid[0] + 0.01, mid[1] + 0.01
    )
    third = _letter_box(
        drawing.cone_tip_letter_corner((cx, cy), r, R9_LETTER_SIZE, [balloon], [leader])
    )
    assert third not in (first, second)
    assert not drawing._segment_meets_box(leader, third)


def test_a_boundary_letter_with_no_clear_side_is_refused() -> None:
    (cx, cy), r = R9_BOUNDARY
    reach = r + 0.006
    ring = [
        (cx + reach * math.cos(math.radians(a)), cy + reach * math.sin(math.radians(a)))
        for a in range(0, 360, 5)
    ]
    with pytest.raises(RuntimeError, match="every side"):
        drawing.cone_tip_letter_corner((cx, cy), r, R9_LETTER_SIZE, ring, [])


def test_the_cone_tip_detail_caption_names_its_scale_and_what_it_omits() -> None:
    """Rule 9 prints its scale against the 1:3 sheet; sheet 1 promises the
    teeth- and thread-free configuration only at 1:2 and smaller."""
    caption = drawing.cone_tip_detail_caption((1.0, 1.0), (1.0, 3.0))
    assert caption.startswith(f"DETAIL {drawing.CONE_TIP_DETAIL_LETTER} 1:1")
    assert "TEETH" in caption and "THREADS" in caption


def _outline_mm(width: float, height: float) -> tuple[float, float, float, float]:
    """An outline of the given size (mm) somewhere off the sheet."""
    return (0.5, 0.5, 0.5 + width / 1000.0, 0.5 + height / 1000.0)


def test_the_full_detail_ladder_never_drops_under_the_simplified_threshold() -> None:
    ratios = [n / d for n, d in drawing.FULL_DETAIL_SCALE_LADDER]
    assert ratios == sorted(ratios, reverse=True)
    assert min(ratios) >= 0.5
    region = drawing.FULL_DETAIL_REGION
    template = drawing.DRAWING_TEMPLATES[drawing.SPEC.layout]
    assert region[1] > template.title_block_top_m, "the field clears the title block"
    assert region[3] <= drawing.NOTE_FIELD_LEFT[1], "the field clears the heading"


@pytest.mark.parametrize(
    ("size_at_1_1", "expected"),
    [
        # Measured on the v37 sheet-1 render: the side view is ~365 x 125 mm
        # at 1:1, which the 397 x ~175 mm field takes whole.
        ((365.0, 125.0), (1.0, 1.0)),
        ((500.0, 125.0), (2.0, 3.0)),  # 333 mm wide at 2:3
        ((365.0, 250.0), (2.0, 3.0)),  # 167 mm tall at 2:3 still fits
        ((365.0, 300.0), (1.0, 2.0)),  # 200 mm tall at 2:3; 150 at 1:2
        ((700.0, 300.0), (1.0, 2.0)),  # 467 mm wide at 2:3
    ],
)
def test_the_full_detail_view_takes_the_largest_scale_that_fits(size_at_1_1, expected) -> None:
    region = drawing.FULL_DETAIL_REGION
    room = ((region[2] - region[0]) * 1000.0, (region[3] - region[1]) * 1000.0)
    assert drawing.full_detail_scale(_outline_mm(*size_at_1_1), (1.0, 1.0)) == expected
    k = expected[0] / expected[1]
    assert size_at_1_1[0] * k <= room[0] and size_at_1_1[1] * k <= room[1]


def test_the_full_detail_fit_reads_the_outline_at_its_placed_scale() -> None:
    # 150 mm tall measured at 1:2 is 300 mm at 1:1 (200 at 2:3): the same model.
    assert drawing.full_detail_scale(_outline_mm(182.5, 150.0), (1.0, 2.0)) == (1.0, 2.0)
    assert drawing.full_detail_scale(_outline_mm(182.5, 62.5), (1.0, 2.0)) == (1.0, 1.0)


def test_a_drive_train_too_big_for_one_to_two_is_refused_not_shrunk() -> None:
    with pytest.raises(ValueError, match=r"1:2: width"):
        drawing.full_detail_scale(_outline_mm(900.0, 100.0), (1.0, 1.0))


def test_the_centre_shift_centres_the_outline_in_the_region() -> None:
    region = (0.0, 0.0, 0.4, 0.2)
    outline = (0.5, 0.5, 0.6, 0.55)
    dx, dy = drawing.centre_shift(outline, region)
    moved = (outline[0] + dx, outline[1] + dy, outline[2] + dx, outline[3] + dy)
    assert moved == pytest.approx((0.15, 0.075, 0.25, 0.125))


class _Annotation:
    def __init__(self, x: float, attach: float) -> None:
        self.position = (x, 1.0)
        self.attach = attach

    def GetPosition(self):
        return (*self.position, 0.0)

    def SetPosition(self, x, y, z) -> bool:
        self.position = (x, y)
        return True

    def GetLeaderCount(self) -> int:
        return 1

    def GetLeaderPointsAtIndex(self, index):
        return (*self.position, 0.0, self.attach, 0.0, 0.0)


class _Balloon:
    def __init__(self, name: str, annotation: _Annotation) -> None:
        self.name = name
        self.annotation = annotation

    def GetName(self) -> str:
        return self.name

    def GetAnnotation(self) -> _Annotation:
        return self.annotation


class _RebuildModel:
    def EditRebuild3(self) -> bool:
        return True


class _RebuildAdapter:
    currentModel = _RebuildModel()

    def _attempt(self, call, default=None):
        return call()


def _placed(annotations: dict[str, _Annotation]):
    leaders = drawing._placed_balloon_leaders(_RebuildAdapter(), annotations)
    return [segment for run in leaders.values() for segment in run]


def test_uncross_needs_more_than_one_swap_per_balloon_and_still_converges() -> None:
    """Six fully reversed leaders cross pairwise: 15 swaps, not 6 (integ1)."""
    count = 6
    annotations = [_Annotation(float(i), float(count - 1 - i)) for i in range(count)]
    balloons = [_Balloon(str(i), a) for i, a in enumerate(annotations)]
    drawing._uncross_balloon_leaders(_RebuildAdapter(), balloons, label="test")
    assert not drawing.find_leader_leader_crossings(
        _placed({str(i): a for i, a in enumerate(annotations)})
    )


def _near_pair(past_m: float) -> dict[str, _Annotation]:
    """Leader 2's end sits ``past_m`` beyond leader 1's line (negative: short of it).

    Leader 1 runs (0, 1) -> (1, 0); leader 2 comes down the diagonal from (1, 1)
    and stops ``past_m`` measured perpendicular to that line.
    """
    tip = (1.0 - past_m * math.sqrt(2.0)) / 2.0
    first = _Annotation(0.0, 1.0)
    second = _Annotation(1.0, 0.0)
    second.position = (1.0, 1.0)

    def second_points(index):
        return (*second.position, 0.0, tip, tip, 0.0)

    second.GetLeaderPointsAtIndex = second_points
    return {"DetailItem1": first, "DetailItem2": second}


@pytest.mark.parametrize("past_m", [0.0003, -0.0003, 0.00005, -0.00005])
def test_uncross_swaps_a_near_crossing_the_audit_tolerance_could_miss(past_m) -> None:
    """integ1's 375/385 was 0.32 mm past; scatter must not decide a swap."""
    annotations = _near_pair(past_m)
    balloons = [_Balloon(name, a) for name, a in annotations.items()]
    drawing._uncross_balloon_leaders(_RebuildAdapter(), balloons, label="test")
    assert annotations["DetailItem1"].position == (1.0, 1.0)
    assert annotations["DetailItem2"].position == (0.0, 1.0)


def test_near_margin_leaves_a_pair_whose_swap_would_lengthen_it() -> None:
    # Parallel leaders 0.5 mm apart: near, but swapping cannot shorten them.
    annotations = {"DetailItem1": _Annotation(0.0, 0.0), "DetailItem2": _Annotation(0.0005, 0.0)}
    annotations["DetailItem2"].GetLeaderPointsAtIndex = lambda index: (
        *annotations["DetailItem2"].position,
        0.0,
        0.0005,
        0.5,
        0.0,
    )
    leaders = drawing._placed_balloon_leaders(_RebuildAdapter(), annotations)
    assert [pair[2:] for pair in drawing._near_balloons(leaders)] == [
        ("DetailItem1", "DetailItem2")
    ]
    assert drawing._next_balloon_swap(leaders) is None


def test_near_margin_ignores_leaders_sharing_an_attachment() -> None:
    annotations = {"DetailItem1": _Annotation(0.0, 0.0), "DetailItem2": _Annotation(0.0002, 0.0)}
    leaders = drawing._placed_balloon_leaders(_RebuildAdapter(), annotations)
    assert drawing._near_balloons(leaders) == []


def test_anchor_offsets_warn_only_on_a_balloon_off_the_sheet_mean(monkeypatch) -> None:
    warnings = []
    monkeypatch.setattr(drawing._telemetry, "warn", warnings.append)
    # Every leader starts 4 m right of its anchor: a constant offset, no warning.
    annotations = {str(i): _Annotation(float(i), float(i)) for i in range(3)}
    leaders = {
        name: [drawing.LeaderSegment(name, "note", a.position[0] + 4.0, 1.0, a.attach, 0.0)]
        for name, a in annotations.items()
    }
    drawing._log_balloon_anchor_offsets(annotations, leaders, label="t")
    assert warnings == []
    leaders["2"] = [drawing.LeaderSegment("2", "note", 2.0 + 4.002, 1.0, 2.0, 0.0)]
    drawing._log_balloon_anchor_offsets(annotations, leaders, label="t")
    assert len(warnings) == 1 and "2 " in warnings[0].split("off the sheet mean:")[1]


def _audit_reader(attach_after_activation: dict[str, float], annotations: dict[str, _Annotation]):
    """Audit-style segments from CURRENT positions to post-activation attachments."""
    reads = []

    def read(adapter, sheet_name):
        reads.append(sheet_name)
        return [
            drawing.LeaderSegment(
                f"{name} '{name[-1]}'", "note", *annotation.position, attach_after_activation[name], 0.0
            )
            for name, annotation in annotations.items()
        ]

    return read, reads


def test_final_uncross_swaps_a_crossing_only_the_audit_geometry_shows() -> None:
    annotations = {"DetailItem1": _Annotation(0.0, 0.0), "DetailItem2": _Annotation(1.0, 1.0)}
    # Placement-time leaders are parallel; after activation the attachments
    # have moved so the leaders cross, as the audit read integ1's 375/385.
    assert not drawing.find_leader_leader_crossings(_placed(annotations))
    read, reads = _audit_reader({"DetailItem1": 1.0, "DetailItem2": 0.0}, annotations)
    drawing._final_balloon_uncross(_RebuildAdapter(), "SHEET", annotations, read_segments=read)
    assert annotations["DetailItem1"].position[0] == 1.0
    assert annotations["DetailItem2"].position[0] == 0.0
    assert not drawing.find_leader_leader_crossings(read(None, "SHEET"))
    assert reads[0] == "SHEET"


def test_final_uncross_raises_by_name_when_a_crossing_survives() -> None:
    annotations = {"DetailItem1": _Annotation(0.0, 0.0), "DetailItem2": _Annotation(1.0, 0.0)}

    def always_crossed(adapter, sheet_name):
        return [
            drawing.LeaderSegment("DetailItem1 '1'", "note", 0.0, 1.0, 1.0, 0.0),
            drawing.LeaderSegment("DetailItem2 '2'", "note", 1.0, 1.0, 0.0, 0.0 + 0.5),
        ]

    with pytest.raises(RuntimeError, match="DetailItem1/DetailItem2"):
        drawing._final_balloon_uncross(
            _RebuildAdapter(), "SHEET", annotations, read_segments=always_crossed
        )


def test_final_uncross_leaves_non_balloon_crossings_to_the_audit() -> None:
    annotations = {"DetailItem1": _Annotation(0.0, 0.0)}

    def crossed_with_a_note(adapter, sheet_name):
        return [
            drawing.LeaderSegment("DetailItem1 '1'", "note", 0.0, 1.0, 1.0, 0.0),
            drawing.LeaderSegment("DetailItem9 'NOTE'", "note", 1.0, 1.0, 0.0, 0.0 + 0.5),
        ]

    drawing._final_balloon_uncross(
        _RebuildAdapter(), "SHEET", annotations, read_segments=crossed_with_a_note
    )
    assert annotations["DetailItem1"].position == (0.0, 1.0)


def test_handle_pivot_screw_is_built_released_and_backs_out_of_the_handle() -> None:
    """#831 P1: MHA-DT-32 is a builder family with its BOM row, and its explode
    carries it with the handle, then clear of the handle's bore."""
    assert "dt-crank-handle-pivot-screw" in _builder_stems()
    assert drawing.BOM_PART_NUMBERS["dt-crank-handle-pivot-screw"] == "MHA-DT-32"
    moved = {step.label: names for step, names in spec.plan_explode(_instances())}
    screw = "dt-crank-handle-pivot-screw-1"
    assert screw in moved["crank arm group"]
    assert screw in moved["crank handle"]
    steps = {step.label: step for step in spec.EXPLODE_STEPS}
    back_out = steps["handle screw backs out"]
    assert back_out.stems == ("dt-crank-handle-pivot-screw",) and back_out.axis == "z"
    # Relative to the handle, the tip starts THREAD_LENGTH past its inboard
    # end; it must travel the whole handle and clear it.
    assert -back_out.distance_mm > screw_spec.THREAD_LENGTH + handle_spec.HANDLE_LENGTH


def _pivot_in_end_screw() -> float:
    """How far T006's pivot runs into MHA-DT-39's reamed end hole, modelled."""
    import cone_line
    import cone_tip_cluster as cluster
    import dt_cone_tip_block_spec as block

    pivot_end = cone_line.T006_NORTH_FACE + cluster.TIP_SET_SHIFT_MM + cluster.PIVOT_LENGTH_MM
    return pivot_end - block.END_SCREW_END_STATION


def test_the_cone_rotor_withdraws_clear_of_the_post_and_the_tip_block() -> None:
    """With the cone gears touching, the collar on the post and the tip in
    its block, no MHA-DT-04 face showed in place and its balloon leader landed
    on the tip block (run 7).  The rotor leaves along the cone axis with its
    bonded tip and pressed bushing (owner decision C1 keyed, 2026-11-09, PR
    #1992) until the whole journal clears the post, and the tip hardware leads
    it by more than T006's pivot runs into MHA-DT-39."""
    import dt_cone_gear_shaft_spec as shaft

    steps = {step.label: step for step in spec.EXPLODE_STEPS}
    rotor, tip = steps["cone rotor withdraws"], steps["tip block slides off"]
    assert rotor.axis == tip.axis == "cone"
    assert {"dt-cone-gear-shaft", "dt-cone-tip-gear", "dt-cone-tip-bushing"} <= set(rotor.stems)
    assert "dt-cone-tip-block" in tip.stems
    # The collar bears on the post's north face, where the journal ends.
    assert rotor.distance_mm > shaft.JOURNAL_END
    pivot_in_screw = _pivot_in_end_screw()
    assert pivot_in_screw > 0.0
    assert tip.distance_mm - rotor.distance_mm > pivot_in_screw
    # The end screw and pinch screw are threaded into the block: they go with it.
    assert {"dt-cone-tip-end-screw", "dt-vn-cone-tip-pinch-screw"} <= set(tip.stems)


def test_the_cone_gears_slide_off_the_64t_gear_short_of_the_end_screw() -> None:
    """Unexploded, MHA-DT-07 read as the stack's first disc and balloons 35
    and 36 met there (r15).  The gears, MHA-DT-37 and MHA-DT-38 slide on
    toward the tip without it, T006's pivot still short of MHA-DT-39."""
    steps = {step.label: step for step in spec.EXPLODE_STEPS}
    gears = steps["cone gears slide toward the tip"]
    assert gears.axis == "cone"
    assert gears.stems == ("dt-cone-gear", "dt-cone-tip-gear", "dt-cone-tip-bushing")
    assert gears.distance_mm > 0.0
    lead = steps["tip block slides off"].distance_mm - steps["cone rotor withdraws"].distance_mm
    assert gears.distance_mm + _pivot_in_end_screw() < lead




def test_the_collar_pin_explodes_with_the_arbor_and_the_strap_pins_stay() -> None:
    """Main's MHA-DT-VN-63 ruling: one family serves as the two strap set pins and
    the MHA-DT-33 collar pin.  The builder tags the collar pin by what it pins,
    and only that instance leaves, with the arbor; the strap pins stay with
    the stationary strap group."""
    assert drawing.BOM_PART_NUMBERS["dt-vn-pinion-strap-pin"] == "MHA-DT-VN-63"
    moved = {step.label: names for step, names in spec.plan_explode(_instances())}
    assert moved["arbor collar pin"] == ("dt-vn-pinion-strap-pin-3",)
    steps = {step.label: step for step in spec.EXPLODE_STEPS}
    arbor, pin = steps["pinion arbor"], steps["arbor collar pin"]
    assert (pin.axis, pin.distance_mm) == (arbor.axis, arbor.distance_mm)
    every_moved = {name for names in moved.values() for name in names}
    assert not {"dt-vn-pinion-strap-pin-1", "dt-vn-pinion-strap-pin-2"} & every_moved


def test_the_collar_pin_role_is_carried_by_exactly_one_pin() -> None:
    untagged = [
        spec.Instance(i.name, i.stem, i.origin_mm) for i in _instances()
    ]
    with pytest.raises(ValueError, match="must tag one"):
        spec.plan_explode(untagged)
    twice = [
        spec.Instance(i.name, i.stem, i.origin_mm, spec.COLLAR_PIN_ROLE)
        if i.stem == "dt-vn-pinion-strap-pin"
        else i
        for i in _instances()
    ]
    with pytest.raises(ValueError, match="must tag one"):
        spec.plan_explode(twice)
    wrong_family = [
        spec.Instance(i.name, i.stem, i.origin_mm, spec.COLLAR_PIN_ROLE)
        if i.name == "dt-pinion-lever-pin-1"
        else spec.Instance(i.name, i.stem, i.origin_mm)
        for i in _instances()
    ]
    with pytest.raises(ValueError, match="must tag one"):
        spec.plan_explode(wrong_family)


def test_the_builder_refuses_a_mislabelled_collar_pin(monkeypatch) -> None:
    """The builder proves the tagged MHA-DT-VN-63 sits in the collar's pin hole
    before authoring the explode; a strap pin tagged by mistake fails loud."""
    import build_dt_drive_train_assembly as assembly

    def rows(rows3, origin_mm):
        flat = [value for row in rows3 for value in row]
        return [*flat, *(value / 1000.0 for value in origin_mm), 1.0, 0.0, 0.0, 0.0]

    collar = rows(
        assembly.ARBOR_ROWS, (assembly.APINION_X, assembly.APINION_Y, assembly.ARBOR_COLLAR_Z0)
    )
    transforms = {
        "collar": collar,
        "collar-pin": rows(
            assembly.COLLAR_PIN_ROWS,
            (assembly.APINION_X, assembly.APINION_Y, assembly.COLLAR_PIN_Z),
        ),
        "strap-pin": rows(
            assembly.TORQUE_SHAFT_ROWS,
            (assembly.PIVOT_X, assembly.PIVOT_Y, assembly.STRAP_PIN_Z[0]),
        ),
    }
    monkeypatch.setattr(assembly, "component_transform", lambda _a, name: transforms[name])
    assembly._require_collar_pin_in_collar_hole(None, "collar-pin", "collar")
    with pytest.raises(AssertionError):
        assembly._require_collar_pin_in_collar_hole(None, "strap-pin", "collar")
