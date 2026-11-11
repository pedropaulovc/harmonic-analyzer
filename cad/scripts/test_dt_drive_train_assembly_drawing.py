"""Offline contract for the drive-train assembly package and its explode plan."""

from __future__ import annotations

import ast
import math
import re
from pathlib import Path
from types import SimpleNamespace

import _config
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
# Step 10 sets the channel's north MHA-CH-08 on the frame's MHA-FR-05 (#936 P1 b),
# offset by the miced north MHA-CH-VN-56 washer (user, 2026-10-10).
EXTERNAL_NUMBERS = frozenset(
    {
        "MHA-FR-01",
        "MHA-FR-05",
        "MHA-CH-08",
        "MHA-CH-VN-56",
        drawing.NORTH_BRACKET_SCREW,
        # Step 5's paper-drive T12, named on sheet 12's interface line.
        drawing.CRANK_CHAIN_WHEEL,
        # Step 8A's MHA-CH-00 connecting rod and rocker arm pairs.
        drawing.CONNECTING_ROD,
        drawing.ROCKER_ARM,
        # Check 5's feed sense, named on sheet 15's interface lines.
        drawing.PLATEN_NUMBER,
        # Steps 1S and 2B's phasing comb: a shop tool in the cone-gear indexing kit,
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
    assert len(names) == drawing.SETTING_SHEET == drawing.BANK_SETTINGS_SHEET + 1
    assert names[drawing.FULL_DETAIL_SHEET - 1] == "FULL-DETAIL SIDE VIEW"
    assert f"FULL DETAIL: SHEET {drawing.FULL_DETAIL_SHEET}." in drawing.ASSEMBLED_HEADING
    assert names[drawing.SEQUENCE_SHEET - 1] == "ASSEMBLY SEQUENCE"
    assert names[drawing.CRANK_SHEET - 1] == "ASSEMBLY SEQUENCE CONT. - CRANK"
    assert names[drawing.BANK_SHEET - 1] == "ASSEMBLY SEQUENCE CONT. - CRANK + CYLINDER BANK"
    assert names[drawing.CHECKS_SHEET - 1] == "CHECKS + SETUP"
    assert names[drawing.FIT_SHEET - 1] == "ASSEMBLY SEQUENCE CONT. - CYLINDER BANK + PINION RIG"
    assert names[drawing.BANK_SETTINGS_SHEET - 1] == "CYLINDER BANK + MHA-DT-01 STATION SETTINGS"
    assert names[drawing.SETTING_SHEET - 1] == "SETTING TABLES + CONE STATIONS"
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
def test_shared_stop_frame_preserves_world_geometry_and_static_lock(proud: float) -> None:
    import build_dt_drive_train_assembly as assembly

    tree = ast.parse(BUILDER.read_text(encoding="utf-8"))
    insertions = {
        node.targets[0].id: node.value.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and isinstance(node.value, ast.Await)
        and isinstance(node.value.value, ast.Call)
        and isinstance(node.value.value.func, ast.Name)
        and node.value.value.func.id == "place_component"
    }
    for name, reference in (
        ("stop_screw", "SwingStopScrew:1"),
        ("spring_foot_screw", "FootScrew:1"),
    ):
        call = insertions[name]
        assert ast.literal_eval(call.args[1]) == SCREW_STEM
        options = {keyword.arg: keyword.value for keyword in call.keywords}
        assert ast.literal_eval(options["component_reference"]) == reference
        assert ast.literal_eval(options["ground"]) is False
        assert isinstance(call.args[4], ast.Name) and call.args[4].id == "IDENTITY"
    namespace = {**vars(assembly), "STOP_PROUD_LEN": proud}
    position = eval(
        compile(ast.Expression(insertions["stop_screw"].args[2]), str(BUILDER), "eval"),
        namespace,
    )
    assert position == [assembly.STOP_X, assembly.Y_BASE_TOP + proud, assembly.STOP_Z]
    # Canonical stock's tip and under-head plane equal the former translated
    # stop body's points, including a nonzero proud-length regression.
    for local_y in (-assembly.STOP_SHANK_LEN, 0.0, assembly.STOP_HEAD_DIA / 2.0):
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
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    assert any(
        isinstance(call.func, ast.Name)
        and call.func.id == "_lock_static"
        and [getattr(arg, "id", None) for arg in call.args] == ["adapter", "stop_screw", "arbor"]
        for call in calls
    )
    appearances = [
        call for call in calls
        if isinstance(call.func, ast.Name) and call.func.id == "apply_component_color"
        and len(call.args) >= 3
        and getattr(call.args[1], "id", None) in {"stop_screw", "spring_foot_screw"}
    ]
    assert len(appearances) == 1
    assert appearances[0].args[1].id == "spring_foot_screw"
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


def test_cone_swing_check_stops_disengaged_at_the_swing_stop() -> None:
    """MHA-SH-VN-52 bounds the DISENGAGE swing; the engaged mesh is set at
    assembly (cone_set_stack): pedestals snug-loose, shims at T012 and T120,
    pedestals tightened, then the T120 feeler and MHA-DT-VN-51 -- never the stop."""
    import cone_set_stack as set_stack

    check = " ".join(drawing.CHECKS.split("4. CONE SWING")[1].split("\n5.")[0].split())

    def feeler(value: float) -> str:
        return drawing.inch_text(value, drawing.FEELER_PLACES)

    t012 = f"{feeler(set_stack.feeler_gap_mm(12))} AT T012"
    t120 = f"{feeler(set_stack.feeler_gap_mm(120))} AT T120"
    order = [
        check.index("OUT TO THE MHA-SH-VN-52 STOP"),
        check.index("EASE MHA-DT-VN-62 UNTIL EACH MHA-DT-02 MOVES"),
        check.index(t012),
        check.index(t120),
        check.index("TIGHTEN MHA-DT-VN-62"),
        # CodeRabbit on #1272: the shims block the swing, so they come out
        # before the T120 feeler set.
        check.index("SWING THE CONE SET OUT. 4L. REMOVE THE LEAVES"),
        check.index(f"{feeler(set_stack.feeler_gap_mm(120))} FEELER IS SNUG T120 TIP TO ROOT"),
        check.index("TIGHTEN MHA-DT-VN-51"),
    ]
    assert order == sorted(order), check
    assert "RETURN IT TO THE MHA-SH-VN-52" not in check




def test_cone_swing_check_requires_installed_stop_inspection_and_seating() -> None:
    """The supplied thread class does not prove the assembled stop's engagement."""
    import dt_swing_stop_screw_spec as stop_screw

    check = " ".join(drawing.CHECKS.split("4. CONE SWING")[1].split("\n5.")[0].split())
    printed = re.search(
        r"VERIFY THE MHA-SH-VN-52 SWING STOP FULL-FORM THREAD ENGAGEMENT (\.\d{3}) MIN", check
    )
    assert printed is not None
    # The inch minimum is the 1.5D rule rounded up, never over the guarantee.
    minimum = float(printed.group(1)) * 25.4
    assert 1.5 * stop_screw.SHANK_DIA - 1e-9 <= minimum
    assert minimum <= stop_screw.MIN_USEFUL_ENGAGEMENT_MM + 1e-9
    assert "CHECK THAT ITS HEAD IS FULLY SEATED" in check
    assert "CHECK THAT MHA-DT-20 AND THE MHA-DT-VN-52 SHOULDER STAY SEATED" in check
    _assert_engagement_cites_its_records(
        check, "SWING STOP FULL-FORM", "THE STOP SEAT'S", "MHA-SH-VN-52'S THREAD LENGTH"
    )


def _assert_engagement_cites_its_records(
    check: str, joint: str, seat: str, screw: str
) -> None:
    """PR 2 machinist review round 6: a seated screw's engagement cannot be
    read, so the check takes the lesser of the seat's full-thread depth and
    the screw's thread length, both recorded in step 23 before it goes in."""
    import dt_drive_train_steps as steps

    cited = re.search(
        rf"{joint} THREAD ENGAGEMENT \.\d{{3}} MIN: THE LESSER READING OF STEPS (\d+\w)-(\d+\w)\.",
        check,
    )
    assert cited is not None
    number = steps.step_number("other-base-mounting")
    assert all(ref.startswith(str(number)) for ref in cited.groups())
    body = _rig_step_body("other-base-mounting")
    seat_line, screw_line = (
        re.search(rf"\b{ref}\. (.*?)(?= {number}[A-HJ-NP-Z]\. |$)", body).group(1)
        for ref in cited.groups()
    )
    assert seat_line == f"RECORD {seat} FULL-THREAD DEPTH WITH A DEPTH GAUGE."
    assert screw_line == f"RECORD {screw} WITH CALIPERS."


def test_cone_swing_check_requires_pivot_thread_engagement() -> None:
    """The seated shoulder does not establish actual full-form thread engagement."""
    import dt_vn_cone_pivot_screw_spec as pivot_screw

    check = " ".join(drawing.CHECKS.split("4. CONE SWING")[1].split("\n5.")[0].split())
    printed = re.search(r"VERIFY MHA-DT-VN-52 FULL-FORM THREAD ENGAGEMENT (\.\d{3}) MIN", check)
    assert printed is not None
    # The inch minimum is the 1D floor rounded up, never over the guarantee.
    minimum = float(printed.group(1)) * 25.4
    assert pivot_screw.THREAD_SOLID_DIA - 1e-9 <= minimum
    assert minimum <= pivot_screw.MIN_USEFUL_ENGAGEMENT_MM + 1e-9
    assert "MHA-DT-VN-52 SHOULDER STAY SEATED" in check
    _assert_engagement_cites_its_records(
        check,
        "MHA-DT-VN-52 FULL-FORM",
        "THE TAPPED HOLE'S",
        "MHA-DT-VN-52'S THREAD LENGTH",
    )


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


def test_rig_is_located_by_its_parked_tip_gap() -> None:
    import dt_drive_train_steps as steps
    import pinion_rig_tip_gap as tip_gap

    feeler = f"{tip_gap.TIP_GAP_SETTING_TEXT} FEELER"
    located = _rig_step_body("rig-located")
    for phrase in ("UNDRILLED SEATS", tip_gap.TIP_GAP_FEELER_TEXT, tip_gap.TIP_GAP_ACCEPT_TEXT):
        assert phrase in located, phrase
    check = _flat(drawing.CHECKS)
    assert feeler in check
    assert (
        f"{tip_gap.TIP_GAP_ACCEPT_TEXT} (SHEET {drawing.CONTINUATION_SHEET}, "
        f"STEP {steps.step_number('rig-located')}E)"
    ) in check
    # The inch acceptance rounds inward, inside the spec's window.
    printed = re.search(r"ACCEPT (\.\d{3})-(\.\d{3})", tip_gap.TIP_GAP_ACCEPT_TEXT)
    assert printed is not None
    low, high = (float(value) * 25.4 for value in printed.groups())
    assert tip_gap.TIP_GAP_ACCEPT[0] - 1e-9 <= low < high <= tip_gap.TIP_GAP_ACCEPT[1] + 1e-9
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
    assert step.startswith(f"{pin.LEVER_PIN_SET_NAME}, GRIP PARKED: MATCH-DRILL #51 THRU")
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


def test_the_tip_gap_feeler_is_the_rest_gap_in_gage_leaves() -> None:
    """Main's TbPB ruling (Q1 b): the rig's east-west feeler is the bench
    rest gap (pins on the cams), to the gage's leaf step, made up only of
    the STARRETT 66MA leaves the fit-up uses; nothing on it is typed."""
    import pinion_rig_fitup as fitup
    import pinion_rig_layout as rig
    import pinion_rig_tip_gap as tip_gap

    # The model parks the pins a design air above the cams; the spring takes
    # it up on the bench, so the rest gap is wider than the model's.
    assert tip_gap.REST_TIP_GAP > tip_gap.MODEL_TIP_GAP
    assert abs(tip_gap.TIP_GAP_FEELER - tip_gap.REST_TIP_GAP) <= rig.FEELER_LEAF_STEP / 2.0
    assert set(tip_gap.TIP_GAP_LEAVES) <= set(fitup.FEELER_GAGE_LEAVES_MM)
    assert math.isclose(sum(tip_gap.TIP_GAP_LEAVES), tip_gap.TIP_GAP_FEELER, abs_tol=1e-9)
    assert tip_gap.TIP_GAP_ACCEPT == pytest.approx(
        (
            tip_gap.TIP_GAP_FEELER - tip_gap.TIP_GAP_ACCEPT_BAND,
            tip_gap.TIP_GAP_FEELER + tip_gap.TIP_GAP_ACCEPT_BAND,
        )
    )
    # The inch sheet prints the setting to the thousandth; the feeler stack
    # table (sheet 15) lists the leaves by their stamped metric size.
    printed = re.search(r"^(\.\d{3}) FEELER$", tip_gap.TIP_GAP_FEELER_TEXT)
    assert printed is not None
    assert float(printed.group(1)) * 25.4 == pytest.approx(tip_gap.TIP_GAP_FEELER, abs=0.0127)
    (row,) = (row for row in drawing.FEELER_STACK_ROWS if row[0] == printed.group(1))
    leaves = [float(leaf) for leaf in row[1].split(" + ")]
    assert math.isclose(sum(leaves), tip_gap.TIP_GAP_FEELER, abs_tol=1e-9)
    assert set(leaves) <= set(fitup.FEELER_GAGE_LEAVES_MM)
    assert "CHECK 7" in row[2]


def test_every_set_feeler_the_steps_and_checks_print_has_a_leaf_row() -> None:
    """Rubric sample round 16 (#0, 3/3 runs): each feeler a step or check
    sets is a sheet 15 row citing it; check cites carry CHECK.  The table
    stays left of the cone station table."""
    rows = {row[0]: row[2] for row in drawing.FEELER_STACK_ROWS}
    assert "4H, 4J" in rows[".004"]
    assert "CHECK 4D" in rows[".018"] and "1R" in rows[".018"]
    assert rows[".020"] == "CHECK 4D, 4M"
    assert "4F" in rows[".010"]
    checks = " ".join(drawing.CHECKS.split())
    assert "RADIAL SHIMS" not in checks and "SWING IN ON FEELER LEAVES" in checks
    widths = drawing.table_column_widths(drawing.FEELER_STACK_HEADER, drawing.FEELER_STACK_ROWS)
    assert drawing.SETTING_TABLE_LEFT + sum(widths) <= drawing.STATION_TABLE_FIELD[0]


def test_the_pivot_seat_is_transferred_and_trusted() -> None:
    """Owner ruling 2026-11-08 (Pedro): step 23 transfer-punches D1 through
    the MHA-DT-20 pivot bore with the cone set at its working position,
    lifts off, spot-drills, drills and taps; the swing check is the only
    acceptance, and DT-00 prints no offset from the pedestal seats."""
    import dt_drive_train_steps as steps
    import dt_vn_cone_pivot_screw_spec as pivot_screw

    step = _rig_step_body("other-base-mounting")
    number = steps.step_number("other-base-mounting")
    route = [
        f"{number}A. CLAMP MHA-DT-20 TO MHA-FR-01.",
        f"{number}B. TRANSFER-PUNCH MHA-FR-01 THRU THE MHA-DT-20 PIVOT BORE.",
        f"{number}C. LIFT MHA-DT-20 AND THE LEAVES OFF.",
        f"{number}D. SPOT-DRILL THE PUNCH MARK.",
        f"{number}E. DRILL AND TAP {pivot_screw.THREAD} THERE PER MHA-FR-01.",
        "CHECK THAT MHA-DT-20 SWINGS FREELY UNDER THE HEAD.",
    ]
    assert step.startswith(
        "CONE SET ON THE BASE: SET MHA-DT-20 ON THE CHECK 4D FEELER LEAVES."
    )
    positions = [step.index(part) for part in route]
    assert positions == sorted(positions)
    assert step.count("CHECK THAT") == 1
    for absent in ("PUNCH MARK IS", "PLUG", "DRO", "MHA-DT-02 SEAT", "1.030", ".482"):
        assert absent not in step
    # The pivot seat is cut once, here: the bank no longer drills it.
    assert "PIVOT SEAT" not in drawing.BANK_STEPS


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


@pytest.mark.parametrize("setting", (0.05, 0.95, 1.0, 1.05, 2.0, 2.5, 2.95))
def test_a_leaf_stack_sums_to_its_setting_from_gage_leaves(setting: float) -> None:
    import pinion_rig_fitup as fitup
    import pinion_rig_tip_gap as tip_gap

    leaves = tip_gap.leaf_stack(setting)
    assert math.isclose(sum(leaves), setting, abs_tol=1e-9)
    assert set(leaves) <= set(fitup.FEELER_GAGE_LEAVES_MM)
    assert list(leaves) == sorted(leaves, reverse=True)


def test_the_spring_is_stationed_east_west_where_its_preload_is_gated() -> None:
    """Main's TbPB ruling Q2(2) A: MHA-DT-24's foot hole is set where the
    preload gates put it, the crest on the flank (the flick's flat stays off
    it), before RIG SET's pad leaf sets it along the bank.  #1037 is the
    window a fitter must hold."""
    import dt_drive_train_steps as steps
    from dt_pinion_spring_section import SCREW_EAST_OF_PIVOT

    located = _rig_step_body("rig-located")
    assert drawing.SPRING_EAST_WEST in located
    printed = re.search(r"FOOT HOLE CENTRE (\d*\.\d+) RIGHT OF THE MHA-DT-19 AXIS", located)
    assert printed is not None
    # The inch sheet's .XX: within half a hundredth of the gated station.
    assert float(printed.group(1)) * 25.4 == pytest.approx(SCREW_EAST_OF_PIVOT, abs=0.127)
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
    assert _flat(fitup.COLLAR_SET_STEP) in _unlettered(_rig_step_body("cam-collars-set"))
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
    # Steps 1S and 2B's comb is a shop tool with no BOM row: the key names it
    # and defines the BLADE the steps cite (machinist review of bd81283964).
    assert table[-1] == "MHA-DT-03-TL-02 = PHASING COMB, ONE BLADE IN A TOOTH SPACE PER GEAR."
    for head in ("1S", "2B"):
        step = drawing.CONE_CRANK_STEPS[drawing.CONE_CRANK_STEPS.index(f"{head}. ") :]
        assert step.startswith(f"{head}. ENGAGE MHA-DT-03-TL-02 AT ONCE, T030'S BLADE")


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
    # That point is not _anchor_note's postcondition; actual air is 4.1845 mm.
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


RAISED_CASES = [
    ("cone-set", CONE_SET_OUTLINE_R10_1_2_5, (1.0, 2.5), (1.0, 2.5), 0.040),
    ("pinion-rig", PINION_RIG_OUTLINE_R9_1_3, (1.0, 3.0), (1.0, 2.0), 0.0),
]


@pytest.mark.parametrize(("cluster", "outline", "read_at", "expected", "_off"), RAISED_CASES)
def test_the_cone_set_and_rig_rise_to_a_readable_scale(
    cluster: str,
    outline: tuple[float, ...],
    read_at: tuple[float, float],
    expected: tuple[float, float],
    _off: float,
) -> None:
    """Rubric sample round 9 printed both at 1:3, too small to read; raised
    over the title block, the ladder from the 1:2 preference stops at 1:2.5
    (cone set) and 1:2 (rig)."""
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
