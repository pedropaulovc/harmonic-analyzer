"""Offline contract for the drive-train assembly package and its explode plan."""

from __future__ import annotations

import ast
import math
import re
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

import dt_crank_handle_pivot_screw_spec as screw_spec
import dt_crank_handle_spec as handle_spec
import draw_dt_drive_train_assembly as drawing
import dt_drive_train_assembly_spec as spec
from _drawing_registry import DRAWINGS_BY_NAME
from _assembly_contract import assembly_contract

SCRIPTS = Path(__file__).resolve().parent
PARTS = SCRIPTS.parent / "config" / "parts"
BUILDER = SCRIPTS / "build_dt_drive_train_assembly.py"
# The rig's steps at the built assembly's counts.
RIG_STEPS = drawing.rig_steps(pivot_blocks=2, cams=2, slotted=4)
# Installation interfaces the package may cite without owning a BOM row.
# Step 10 sets the channel's north MHA-CH-008 on the frame's MHA-FR-005 (#936 P1 b).
EXTERNAL_NUMBERS = frozenset({"MHA-FR-001", "MHA-FR-005", "MHA-CH-008"})
EXTERNAL_ASSEMBLY_NUMBERS = {
    "ch-channel": "MHA-CH-000",
    "fr-frame": "MHA-FR-000",
    "pd-paper-drive": "MHA-PD-000",
}


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
    """A stand-in census of the built model: builder families at plausible origins."""
    drum_x = -60.39
    layout = {
        "dt-cylinder-gear-shaft": [(drum_x, 90.5, -86.9)],
        "dt-arbor-pedestal": [(drum_x, 50.8, -87.4), (drum_x, 50.8, 100.6)],
        "dt-cylinder-end-disc": [(drum_x, 90.5, -72.5), (drum_x, 90.5, 72.1)],
        "vn-arbor-set-screw": [(drum_x, 95.3, -76.519), (drum_x, 95.3, 78.062)],
        "dt-cylinder-gear": [(drum_x, 90.5, -64.0 + 7.0 * j) for j in range(20)],
        "vn-foot-screw": [(7.49, 52.0, 74.0)],
        "vn-pedestal-hold-down-screw": [(drum_x, 55.8, -91.652), (drum_x, 55.8, 94.202)],
        "vn-slotted-screw": [(-19.4, 60.0, -94.9), (7.6, 60.0, -94.9), (-19.4, 60.0, 85.1), (7.6, 60.0, 85.1)],
        "dt-cone-gear": [(-115.0 + j, 90.5, -25.0 + 6.0 * j) for j in range(20)],
        "dt-pinion-bracket": [(-12.1, 62.8, -72.0), (-12.1, 62.8, 71.0)],
        "dt-pinion-pivot-block": [(-5.9, 62.8, -95.0), (-5.9, 62.8, 85.0)],
        "dt-pinion-cam-pin": [(-8.0, 70.0, -72.0), (-8.0, 70.0, 71.0)],
        "dt-pinion-cam": [(0.4, 64.7, -72.0), (0.4, 64.7, 71.0)],
        # Two strap set pins, then the collar pin (the builder's insertion order).
        "vn-pinion-strap-pin": [(-12.1, 62.8, -74.0), (-12.1, 62.8, 81.0), (-18.4, 90.5, -127.0)],
    }
    layout.update(overrides)
    roles = {"vn-pinion-strap-pin-3": spec.COLLAR_PIN_ROLE}
    instances = []
    for stem in sorted(_builder_stems() | set(layout)):
        for index, origin in enumerate(layout.get(stem, [(0.0, 100.0, 0.0)]), start=1):
            name = f"{stem}-{index}"
            instances.append(spec.Instance(name, stem, origin, roles.get(name)))
    return instances


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
        row = yaml.safe_load(path.read_text(encoding="utf-8"))[stem]
        assert row["number"] == number, stem


def test_bom_catalog_numbers_match_the_parts_registry() -> None:
    """A vendor number in a BOM description is the registry's SKU, and every
    registry SKU is printed: a re-sourced fastener cannot leave a stale row."""
    for stem, text in drawing.BOM_DESCRIPTIONS.items():
        path = PARTS / f"{stem}.yaml"
        if not path.exists():
            continue
        skus = yaml.safe_load(path.read_text(encoding="utf-8"))[stem].get("supplier_skus")
        printed = re.findall(r"\b(?:MCMASTER|MSC) (\S+)$", text)
        if not skus:
            assert not printed, stem
            continue
        assert printed == [skus[0]], stem


def test_package_text_cites_only_bom_or_external_numbers() -> None:
    texts = (
        drawing.ASSEMBLED_HEADING,
        drawing.CONE_CRANK_STEPS,
        drawing.BANK_STEPS,
        RIG_STEPS,
        drawing.CHECKS,
        drawing.SETUP_NOTES,
        drawing.INTERFACE_NOTES,
        drawing.FIT_PLACEHOLDER,
        drawing.CRANK_WASHER_FIT_NOTES,
        *drawing.BOM_DESCRIPTIONS.values(),
    )
    cited = set(re.findall(r"\bMHA-[A-Z0-9-]+\b", "\n".join(texts)))
    assert cited, "package text contains no part references"
    bom = set(drawing.BOM_PART_NUMBERS.values())
    for stem, number in EXTERNAL_ASSEMBLY_NUMBERS.items():
        assert assembly_contract(stem).number == number
    assert cited <= bom | EXTERNAL_NUMBERS | set(EXTERNAL_ASSEMBLY_NUMBERS.values())


def test_note_lines_fit_a_half_sheet_field() -> None:
    """3.5 mm text renders about 2.63 mm per character; a field is 194 mm wide."""
    for text in (
        drawing.CONE_CRANK_STEPS,
        drawing.BANK_STEPS,
        RIG_STEPS,
        drawing.CHECKS,
        drawing.SETUP_NOTES,
        drawing.INTERFACE_NOTES,
        drawing.FIT_PLACEHOLDER,
        drawing.CRANK_WASHER_FIT_NOTES,
        drawing.CONSUMABLES_NOTES,
    ):
        for line in text.format(
            cone_gears=20,
            cylinder_gears=20,
            cam_pins=2,
            pivot_blocks=2,
            cams=2,
            slotted=4,
            foot=1,
            hold_down=2,
        ).splitlines():
            assert len(line) <= 70, line


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
    """77c165b5d stacked 43 step lines and the 4-line general notes in sheet
    6's 217 mm left field (219.7 mm here); natively the notes ended at 32.28 mm,
    under the field's 35.00 mm bottom. The census formats the texts at the
    counts the width test uses."""
    instances = _instances()
    cones = sorted(i.name for i in instances if i.stem == "dt-cone-gear")
    configurations = {name: f"T{6 * n:03d}" for n, name in enumerate(cones, start=1)}
    fields = drawing.package_note_fields(drawing.SourceFacts(instances, configurations))
    for field in fields:
        assert _spare(field) >= 0, (field.label, _spare(field))
    # Main's arrangement, the general notes under the steps, is over budget.
    (notes,) = (field for field in fields if field.sheet == 1)
    (steps,) = (
        field
        for field in fields
        if field.label == f"sheet {drawing.SEQUENCE_SHEET} left note field"
    )
    assert _spare(steps._replace(blocks=steps.blocks + notes.blocks)) < 0
    # The MHA-DT-036 fit-up rides the FIT sheet; step 4 on sheet 6 only cites it.
    (fit,) = (
        field
        for field in fields
        if field.label == f"sheet {drawing.FIT_SHEET} right note field"
    )
    assert drawing.CRANK_WASHER_FIT_NOTES in dict(fit.blocks).values()
    assert f"PER SHEET {drawing.FIT_SHEET}" in drawing.CONE_CRANK_STEPS


def test_sheet_numbers_are_pinned_where_the_sheets_cite_them() -> None:
    names = drawing.SHEET_NAMES
    assert len(names) == 10
    assert names[drawing.FULL_DETAIL_SHEET - 1] == "FULL-DETAIL SIDE VIEW"
    assert drawing.FULL_DETAIL_SHEET == len(names), "appended: no cited number moves"
    assert f"FULL DETAIL: SHEET {drawing.FULL_DETAIL_SHEET}." in drawing.ASSEMBLED_HEADING
    assert names[drawing.SEQUENCE_SHEET - 1] == "ASSEMBLY SEQUENCE"
    assert names[drawing.BANK_SHEET - 1] == "ASSEMBLY SEQUENCE CONT. - CYLINDER BANK"
    assert names[drawing.CHECKS_SHEET - 1] == "CHECKS + SETUP"
    assert names[drawing.FIT_SHEET - 1] == "ASSEMBLY SEQUENCE CONT. + FIT"
    assert sorted(drawing.CLUSTER_SHEETS.values()) == [3, 4, 5]
    assert set(drawing.SHEET_SCALES) == set(names)
    assert "BALLOONS ON SHEETS 3-5" in drawing.BOM_REFERENCE_CAPTION
    assert f"STATIONS: SHEET {drawing.FIT_SHEET}" in drawing.BOM_REFERENCE_CAPTION
    assert f"CYLINDER BANK: SHEET {drawing.BANK_SHEET}." in drawing.CONE_CRANK_STEPS
    assert all(text.count(",") <= 1 for text in drawing.BOM_DESCRIPTIONS.values())


def test_grouped_parts_stamp_the_description_the_bom_prints() -> None:
    """A grouped part's configurations carry UseDescriptionInBOM, and that
    wins over the drawing's written cell: cascade-2 (2026-09-27) read back
    MHA-DT-030's 'Pinion Lever Cross Pin' after SetText2 wrote its BOM text.  So
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
        if stem not in drawing.BOM_DESCRIPTIONS:
            continue
        row = yaml.safe_load((PARTS / f"{stem}.yaml").read_text(encoding="utf-8"))[stem]
        assert row.get("description") == drawing.BOM_DESCRIPTIONS[stem], stem
        printed.append(stem)
    assert {"dt-cone-gear", "dt-pinion-lever-pin"} <= set(printed)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("number", "MHA-014"),
        ("number", "MHA-ZZ-001"),
        ("number", "MHA-DT-000"),
        ("number", "MHA-CH-003"),
        ("number", "MHA-DT-003-extra"),
        ("number", "MHA-DT-٠٠٣"),
        ("number", 3),
        ("category", "zz"),
        ("category", "ch"),
        ("description", ""),
        ("description", None),
    ),
)
def test_grouped_bom_rejects_invalid_registry_metadata_before_native_access(
    monkeypatch, field: str, value: object,
) -> None:
    import _config
    import _grouped_bom_properties as grouped

    row = _config.parts("dt-cone-gear")
    row[field] = value
    monkeypatch.setattr(grouped._config, "parts", lambda _stem: row)

    class Adapter:
        @property
        def currentModel(self):
            raise AssertionError("invalid metadata reached native configuration access")

    with pytest.raises(ValueError):
        grouped.apply_grouped_bom_properties(
            Adapter(), ["Default"], part_name="dt-cone-gear"
        )


def test_grouped_bom_refuses_unregistered_part_stem_before_native_access() -> None:
    import _grouped_bom_properties as grouped

    class Adapter:
        @property
        def currentModel(self):
            raise AssertionError("unregistered stem reached native configuration access")

    with pytest.raises(KeyError):
        grouped.apply_grouped_bom_properties(
            Adapter(), ["Default"], part_name="dt-unregistered-grouped-part"
        )


def test_grouped_bom_stamps_registered_identity_on_every_configuration(
    monkeypatch,
) -> None:
    import _config
    import _grouped_bom_properties as grouped

    row = _config.parts("dt-cone-gear")
    configurations = {
        name: SimpleNamespace(
            BOMPartNoSource=0,
            AlternateName="obsolete",
            UseAlternateNameInBOM=False,
            Description="obsolete",
            UseDescriptionInBOM=False,
        )
        for name in ("Default", "T120")
    }
    model = SimpleNamespace(GetConfigurationByName=configurations.get)
    monkeypatch.setattr(grouped, "_early_bound", lambda value, _interface: value)
    grouped.apply_grouped_bom_properties(
        SimpleNamespace(currentModel=model),
        tuple(configurations),
        part_name="dt-cone-gear",
    )
    for configuration in configurations.values():
        assert configuration.BOMPartNoSource == 8
        assert configuration.AlternateName == row["number"]
        assert configuration.UseAlternateNameInBOM is True
        assert configuration.Description == row["description"]
        assert configuration.UseDescriptionInBOM is True


def test_bom_full_native_identities_retain_text_air() -> None:
    """The failure PDF's unchanged Century Gothic glyph advances, in metres.

    The old 22 mm Number cell held the 20.757 mm MHA-VN- prefix with
    1.243 mm total air, but wrapped its final three digits on every row.
    The full identities must keep at least that visible air, not merely fit
    their prefix. The widest full description measured 107.45 mm.
    """
    glyph_advances = {
        **dict.fromkeys("0123456789", 0.00258611),
        "M": 0.00428859,
        "H": 0.00318727,
        "A": 0.00345347,
        "-": 0.00154931,
        "D": 0.00347213,
        "T": 0.00198808,
        "V": 0.00327594,
        "N": 0.00345347,
    }
    native_air = 0.001243
    for number in drawing.BOM_PART_NUMBERS.values():
        full_width = sum(glyph_advances[character] for character in number)
        assert drawing.BOM_COLUMN_WIDTHS["part"] >= full_width + native_air, number
    assert drawing.BOM_COLUMN_WIDTHS["description"] >= 0.107450 + native_air


def test_step_one_sets_the_64t_against_the_shaft_collar() -> None:
    """#916: the shaft's thrust collar is the 64T's axial stop (the drive
    train seats the gear's south face on the collar end), so step 1 names it;
    crank_boss_rim books the gear's station from that collar."""
    import dt_cone_gear_shaft_spec as shaft

    assert shaft.COLLAR_THICKNESS > 0.0
    gear = drawing.BOM_PART_NUMBERS["dt-crank-drive-gear"]
    shaft_number = drawing.BOM_PART_NUMBERS["dt-cone-gear-shaft"]
    step_one = drawing.CONE_CRANK_STEPS.split("\n2. ")[0]
    first_line = step_one.split("\n1. ")[1].split("\n")[0]
    assert gear in first_line and shaft_number in first_line and "COLLAR" in first_line


def test_cone_swing_check_stops_disengaged_at_the_swing_stop() -> None:
    """MHA-VN-015 bounds the DISENGAGE swing; engaged, the plate stands off it."""
    check = " ".join(drawing.CHECKS.split("4. CONE SWING")[1].split("\n5.")[0].split())
    order = [
        check.index("TO THE MHA-VN-015 STOP, CLEAR OF EVERY MHA-DT-012"),
        check.index("SWING IT BACK"),
        check.index("RE-ENGAGE"),
        check.index("TIGHTEN MHA-VN-013"),
    ]
    assert order == sorted(order), check
    assert "RETURN IT TO THE MHA-VN-015" not in check


def _flat(text: str) -> str:
    return " ".join(text.split())


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

    feeler = f"{tip_gap.TIP_GAP_FEELER:.2f} FEELER"
    located = _rig_step_body("rig-located")
    for phrase in ("TRANSFERRED", tip_gap.TIP_GAP_FEELER_TEXT, tip_gap.TIP_GAP_ACCEPT_TEXT):
        assert phrase in located, phrase
    check = _flat(drawing.CHECKS)
    assert feeler in check
    assert (
        f"{tip_gap.TIP_GAP_ACCEPT_TEXT} (SHEET {drawing.FIT_SHEET}, "
        f"STEP {steps.step_number('rig-located')})"
    ) in check
    assert f"SEE SHEET {drawing.CHECKS_SHEET}" in drawing.ASSEMBLED_HEADING
    assert f"SEE SHEET {drawing.CHECKS_SHEET}, EXTERNAL" in _rig_step_body(
        "other-base-mounting"
    )
    assert f"PINION RIG: CONT. ON SHEET {drawing.FIT_SHEET}." in drawing.BANK_STEPS
    # The seats are spotted after RIG SET, and drilled per the base's own
    # transfer callouts, not a second copy of their sizes.
    seats = _rig_step_body("rig-seats-transferred")
    assert "PER ITS MHA-FR-001 TRANSFER CALLOUT" in seats
    assert not re.search(r"#\d+-\d+|#\d+ X", seats)
    assert steps.step_number("rig-set") < steps.step_number("rig-seats-transferred")


def test_the_rig_steps_print_the_fitup_sequence_once_in_order() -> None:
    """Codex #858 (PRRT_kwDOPHDy386mTbPB): the fit-up that produces the
    modelled pin stations reaches the fitter.  Each pinion_rig_fitup step
    prints once, word for word, in its own step, in ASSEMBLY_SEQUENCE order;
    nothing is pending."""
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
    flat = _flat(RIG_STEPS)
    for key, step in zip(keys, fitup.ASSEMBLY_SEQUENCE, strict=True):
        assert flat.count(_flat(step)) == 1, key
        assert _flat(step) in _rig_step_body(key), key
    numbers = [steps.step_number(key) for key in keys]
    assert numbers == sorted(numbers)
    printed = [int(n) for n in re.findall(r"^(\d+)\. ", RIG_STEPS, re.MULTILINE)]
    first = steps.SEQUENCE.index("arbor-collar-pinned") + 1
    assert printed == list(range(first, len(steps.SEQUENCE) + 1))
    assert "PENDING" not in RIG_STEPS
    # Each match-drilled pin hole's callout points at the step that drills it.
    import draw_dt_pinion_lever as lever
    import draw_dt_pinion_lift_rod as lift_rod
    import draw_dt_pinion_pivot_shaft as shaft

    for sheet, key, name in (
        (shaft, shaft.SHAFT_DRILL_STEP_KEY, fitup.SHAFT_DRILL_NAME),
        (lever, lever.LEVER_PIN_SET_STEP_KEY, "LEVER PIN SET"),
        (lift_rod, lift_rod.LEVER_PIN_SET_STEP_KEY, "LEVER PIN SET"),
    ):
        assert steps.step_ref(key) in _flat(sheet.DIMENSION_CALLOUTS["PinHoleDia"])
        assert name in _rig_step_body(key)


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
    printed = re.search(r"\(([\d.+ ]+) STARRETT 66MA LEAVES\)", tip_gap.TIP_GAP_FEELER_TEXT)
    assert printed is not None
    leaves = [float(leaf) for leaf in printed.group(1).split(" + ")]
    assert math.isclose(sum(leaves), tip_gap.TIP_GAP_FEELER, abs_tol=1e-9)
    assert set(leaves) <= set(fitup.FEELER_GAGE_LEAVES_MM)


@pytest.mark.parametrize("setting", (0.05, 0.95, 1.0, 1.05, 2.0, 2.5, 2.95))
def test_a_leaf_stack_sums_to_its_setting_from_gage_leaves(setting: float) -> None:
    import pinion_rig_fitup as fitup
    import pinion_rig_tip_gap as tip_gap

    leaves = tip_gap.leaf_stack(setting)
    assert math.isclose(sum(leaves), setting, abs_tol=1e-9)
    assert set(leaves) <= set(fitup.FEELER_GAGE_LEAVES_MM)
    assert list(leaves) == sorted(leaves, reverse=True)


def test_the_spring_is_stationed_east_west_where_its_preload_is_gated() -> None:
    """Main's TbPB ruling Q2(2) A: MHA-DT-024's foot hole is set where the
    preload gates put it, the crest on the flank (the flick's flat stays off
    it), before RIG SET's pad leaf sets it along the bank.  #1037 is the
    window a fitter must hold."""
    import dt_drive_train_steps as steps
    from dt_pinion_spring_section import SCREW_EAST_OF_PIVOT

    located = _rig_step_body("rig-located")
    assert drawing.SPRING_EAST_WEST in located
    printed = re.search(r"FOOT HOLE CENTRE ([\d.]+) EAST OF THE MHA-DT-019 AXIS", located)
    assert printed is not None
    assert float(printed.group(1)) == pytest.approx(SCREW_EAST_OF_PIVOT, abs=0.05)
    assert "CREST BEARING ON THE PARKED BACK MHA-DT-014 FLANK" in located
    assert "TERMINAL FLAT" not in _flat(RIG_STEPS)
    assert "TERMINAL FLAT" not in Path(drawing.__file__).read_text(encoding="utf-8")
    assert steps.step_number("rig-located") < steps.step_number("rig-set")


def test_a_fitup_step_missing_from_its_key_is_caught() -> None:
    """Positive control: the collar set is not the lever pin's step."""
    import pinion_rig_fitup as fitup

    assert _flat(fitup.COLLAR_SET_STEP) not in _rig_step_body("lever-pin-set")


_SHEET_CITE = re.compile(r"SHEETS? \d")
# The cluster sheets' balloon-count caption, not a cross-reference.
_SHEET_CITE_EXEMPT = {"; ITEMS PER SHEET 2"}


def test_no_sheet_number_is_typed_into_the_package_text() -> None:
    """Every "SHEET n" a sheet prints comes from a *_SHEET constant, so adding
    or moving a sheet can never leave a stale cross-reference (B1, #743).
    Literal parts of f-strings are string constants too, so they are checked;
    comments are not."""
    tree = ast.parse(Path(drawing.__file__).read_text(encoding="utf-8"))
    typed = [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and _SHEET_CITE.search(node.value)
        and node.value not in _SHEET_CITE_EXEMPT
    ]
    assert typed == []


def test_drum_is_bonded_after_the_arbor_passes_the_front_strap() -> None:
    """The front strap bore is closed: a bonded drum can no longer pass it."""
    import dt_drive_train_steps as steps

    assert "FRONT MHA-DT-014 ON BEHIND IT" in _rig_step_body("arbor-collar-pinned")
    assert "BOND WITH LOCTITE 638" in _rig_step_body("drum-bonded")
    assert "IN THE BACK MHA-DT-014 TOP BORE" in _rig_step_body("cluster-hung")
    order = [
        steps.step_number(key)
        for key in ("arbor-collar-pinned", "drum-bonded", "cluster-hung")
    ]
    assert order == sorted(order)


def test_torque_shaft_pins_go_in_before_the_cams() -> None:
    """The cams block the strap pins' west edge, and the cam set screws are
    locked only by COLLAR SET, before the lever pin (Main's TbPB ruling)."""
    import dt_drive_train_steps as steps

    assert "DRIVE MHA-VN-033 PINS" in _rig_step_body("straps-pinned-to-torque-shaft")
    cams = _rig_step_body("cams-and-lever-fitted")
    assert "FIT 2X MHA-DT-023" in cams and "LOOSE" in cams and "MHA-DT-030" not in cams
    assert "LOCK SCREWS" in _rig_step_body("cam-collars-set")
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
        "vn-arbor-set-screw-1",
        "vn-pedestal-hold-down-screw-1",
    )
    assert moved["north pedestal"] == (
        "dt-arbor-pedestal-2",
        "vn-arbor-set-screw-2",
        "vn-pedestal-hold-down-screw-2",
    )
    assert moved["apex set screws lift"] == ("vn-arbor-set-screw-1", "vn-arbor-set-screw-2")
    assert moved["pedestal screws lift"] == (
        "vn-pedestal-hold-down-screw-1",
        "vn-pedestal-hold-down-screw-2",
    )
    assert moved["spring foot screw lifts"] == ("vn-foot-screw-1",)
    assert moved["block screws lift"] == tuple(f"vn-slotted-screw-{i}" for i in range(1, 5))


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
    assert {"dt-crank-hub", "vn-crank-hub-pin"} <= {i.stem for i in census}
    moved = {step.label: names for step, names in spec.plan_explode(census)}
    assert {"dt-crank-hub-1", "vn-crank-hub-pin-1"} <= set(moved["crank arm group"])


def test_explode_families_are_either_moved_or_stationary_never_both() -> None:
    moved = {stem for step in spec.EXPLODE_STEPS for stem in step.stems}
    assert not moved & spec.STATIONARY_STEMS
    assert moved | spec.STATIONARY_STEMS == spec.classified_stems()


def test_clusters_partition_every_instance_once() -> None:
    census = _instances()
    members = spec.cluster_members(census)
    flat = [name for names in members.values() for name in names]
    assert sorted(flat) == sorted(i.name for i in census)
    assert "vn-foot-screw-1" in members["pinion-rig"]
    assert {"vn-pedestal-hold-down-screw-1", "vn-pedestal-hold-down-screw-2"} <= set(
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
    table = drawing.station_table_text(rows)
    assert table.splitlines()[1].startswith("STN  1  T120")


@pytest.mark.parametrize(("data_rows", "first_rows"), ((39, 20), (54, 27)))
def test_bom_native_equal_heights_keep_the_larger_half_first(
    data_rows: int, first_rows: int,
) -> None:
    heights = (0.006,) * data_rows
    assert drawing.bom_split_row(heights, header_height=0.0101683) == first_rows


def test_bom_split_requires_a_data_row_in_each_piece() -> None:
    with pytest.raises(ValueError, match="at least two"):
        drawing.bom_split_row((0.006,), header_height=0.0101683)


def test_bom_split_uses_native_wrapping_heights_not_row_counts() -> None:
    # Four late descriptions wrap to the native two-line height. A 27/27
    # count split enters the right-hand title block, while 28/26 fits.
    heights = (0.006,) * 50 + (0.0101683,) * 4
    header = 0.0101683
    second_anchor = (drawing.BOM_SECOND_COLUMN_X, drawing.BOM_ANCHOR[1])
    count_height = header + sum(heights[27:])
    assert any(
        "title block" in finding
        for finding in drawing.bom_extent_violations(
            second_anchor, drawing.BOM_COLUMN_WIDTH, count_height
        )
    )
    split = drawing.bom_split_row(heights, header_height=header)
    assert split == 28
    for anchor, data in ((drawing.BOM_ANCHOR, heights[:split]), (second_anchor, heights[split:])):
        assert drawing.bom_extent_violations(
            anchor, drawing.BOM_COLUMN_WIDTH, header + sum(data)
        ) == []


def test_bom_refuses_the_observed_all_wrapped_native_layout() -> None:
    # 54 data rows plus repeated headers at 10.1683 mm cannot fit the two
    # legal floors. The old 27/27 split read bottom = -32.713 mm.
    heights = (0.0101683,) * 54
    with pytest.raises(ValueError, match="no two-column BOM split fits"):
        drawing.bom_split_row(heights, header_height=0.0101683)


@pytest.mark.parametrize(
    ("actual", "fit"),
    ((0.005998, "short"), (0.0060005, "exact"), (0.0101683, "grown")),
)
def test_bom_native_row_height_classification(actual: float, fit: str) -> None:
    assert drawing.bom_row_fit(0.006, actual) == fit


def test_bom_reference_view_and_caption_fit_right_of_the_bom() -> None:
    # The farm measured a 124.2 mm header + 19-row piece, so the header is
    # ~10.2 mm. Under the first column the view was placed for 20 rows; at 27
    # the bottom row (MHA-DT-015) ran through it (st19 dt-02).
    data_rows = len(drawing.bom_components(drawing.instance_counts(_instances())))
    header = 0.0101683
    first_rows = drawing.bom_split_row(
        (drawing.BOM_ROW_HEIGHT,) * data_rows, header_height=header
    )
    first_height = header + first_rows * drawing.BOM_ROW_HEIGHT
    first_bottom = drawing.BOM_ANCHOR[1] - first_height
    half = drawing.REFERENCE_ISO_HALF_OUTLINE
    assert (0.068 + half) > first_bottom  # the old centre (0.110, 0.068)
    # Now it stands right of the second column, the whole column height clear
    # of either piece, with its caption seated over the title block.
    cx, cy = drawing.BOM_REFERENCE_ISO_CENTER
    outline = (cx - half, cy - half, cx + half, cy + half)
    assert drawing.bom_reference_iso_violations(outline) == []
    assert outline[0] > drawing.BOM_SECOND_COLUMN_X + drawing.BOM_COLUMN_WIDTH
    # The caption is centred under the view: its widest line (~2.47 mm a
    # character, the two-line caption on dt-02) stays in the strip.
    widest = max(len(line) for line in drawing.BOM_REFERENCE_CAPTION.splitlines())
    half_caption = widest * 0.00247 / 2
    assert cx - half_caption > drawing.BOM_RIGHT_EDGE + drawing.BOM_SHEET_CLEARANCE
    assert cx + half_caption < drawing.NOTE_FIELD_RIGHT[2]
    # A view that grew onto the BOM, past the right field or down into the
    # title block is refused before the BOM is inserted.
    onto_bom = (outline[0] - 0.010, outline[1], outline[2] - 0.010, outline[3])
    assert "second column" in drawing.bom_reference_iso_violations(onto_bom)[0]
    past_right = (outline[0] + 0.010, outline[1], outline[2] + 0.010, outline[3])
    assert "passes" in drawing.bom_reference_iso_violations(past_right)[0]
    sunk = drawing.BOM_REFERENCE_ISO_SLACK + 0.002
    too_low = (outline[0], outline[1] - sunk, outline[2], outline[3])
    assert "title block" in drawing.bom_reference_iso_violations(too_low)[0]


def test_bom_budget_refuses_the_title_block_and_sheet_edges() -> None:
    assert drawing.bom_extent_violations(drawing.BOM_ANCHOR, 0.164, 0.130) == []
    assert drawing.bom_extent_violations((0.300, 0.100), 0.100, 0.050)
    assert drawing.bom_extent_violations((0.001, 0.200), 0.100, 0.050)
    second_anchor = (drawing.BOM_SECOND_COLUMN_X, drawing.BOM_ANCHOR[1])
    floor_height = drawing.BOM_ANCHOR[1] - (
        drawing.DRAWING_TEMPLATES[drawing.SPEC.layout].title_block_top_m
        + drawing.BOM_SHEET_CLEARANCE
    )
    assert drawing.bom_extent_violations(
        second_anchor, drawing.BOM_COLUMN_WIDTH, floor_height - 1e-7
    ) == []
    assert any(
        "title block" in finding
        for finding in drawing.bom_extent_violations(
            second_anchor, drawing.BOM_COLUMN_WIDTH, floor_height + 1e-7
        )
    )
    first_floor_height = drawing.BOM_ANCHOR[1] - drawing.NOTE_FIELD_LEFT[3]
    assert drawing.bom_extent_violations(
        drawing.BOM_ANCHOR, drawing.BOM_COLUMN_WIDTH, first_floor_height - 1e-7
    ) == []
    assert any(
        "sheet-number field" in finding
        for finding in drawing.bom_extent_violations(
            drawing.BOM_ANCHOR, drawing.BOM_COLUMN_WIDTH, first_floor_height + 1e-7
        )
    )


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


def test_the_sheet_scales_follow_the_chosen_cluster_and_full_detail_scales() -> None:
    chosen = {**drawing.CLUSTER_SCALES, "cone-crank": (1.0, 4.0)}
    scales = drawing.package_sheet_scales(chosen, (2.0, 3.0))
    assert set(scales) == set(drawing.SHEET_NAMES)
    assert scales[drawing.SHEET_NAMES[drawing.CLUSTER_SHEETS["cone-crank"] - 1]] == (1.0, 4.0)
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


def test_every_text_sheet_places_a_view_for_its_title_block() -> None:
    """finalize_drawing refuses a sheet with no view (r8 leaf 20260923T214354Z-1-4126331f)."""
    tree = ast.parse(Path(drawing.__file__).read_text(encoding="utf-8"))
    placers = {
        node.name: node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name.startswith("_place_")
    }
    for name in (
        "_place_sequence_sheet",
        "_place_bank_sheet",
        "_place_fit_sheet",
        "_place_checks_sheet",
    ):
        calls = {
            call.func.id
            for call in ast.walk(placers[name])
            if isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
        }
        assert "_reference_iso" in calls, name


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
    """#831 P1: MHA-DT-032 is a builder family with its BOM row, and its explode
    carries it with the handle, then clear of the handle's bore."""
    assert "dt-crank-handle-pivot-screw" in _builder_stems()
    assert drawing.BOM_PART_NUMBERS["dt-crank-handle-pivot-screw"] == "MHA-DT-032"
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


def test_the_cone_rotor_withdraws_clear_of_the_post_and_the_tip_block() -> None:
    """With the cone gears touching, the collar on the post and the tip in
    its block, no MHA-DT-004 face showed in place and its balloon leader landed
    on the tip block (run 7).  The rotor leaves along the cone axis until the
    whole journal clears the post, and the tip hardware leads it by more than
    the tip runs into the block."""
    import dt_cone_gear_shaft_spec as shaft

    steps = {step.label: step for step in spec.EXPLODE_STEPS}
    rotor, tip = steps["cone rotor withdraws"], steps["tip block slides off"]
    assert rotor.axis == tip.axis == "cone"
    assert "dt-cone-gear-shaft" in rotor.stems and "dt-cone-tip-block" in tip.stems
    # The collar bears on the post's north face, where the journal ends.
    assert rotor.distance_mm > shaft.JOURNAL_END
    tip_in_block = shaft.T006_TIP_STATION - shaft.TIP_BLOCK_SOUTH_FACE_STATION
    assert tip_in_block > 0.0
    assert tip.distance_mm - rotor.distance_mm > tip_in_block
    # The adjuster and pinch screw are threaded into the block: they go with it.
    assert {"vn-cone-tip-adjuster", "vn-cone-tip-pinch-screw"} <= set(tip.stems)


def test_bank_fitup_limits_are_the_layout_bands() -> None:
    """#743 steps 8-9 print cylinder_bank_layout's bands as limits, each
    rounded inward so a part inside the print is inside the model band."""
    import math

    import cylinder_bank_layout as bank
    import fr_harmonic_base_spec as base
    import rocker_bank_layout as rockers

    def limits(low: float, high: float, places: int) -> str:
        scale = 10**places
        return (
            f"{math.ceil(low * scale - 1e-9) / scale:.{places}f}-"
            f"{math.floor(high * scale + 1e-9) / scale:.{places}f}"
        )

    steps = drawing.BANK_STEPS
    thickness = bank.OVERALL_THICKNESS
    upper, lower = bank.OVERALL_THICKNESS_BAND
    # 7.0565 +/-0.025 is exact at four places (user ruling L20 d').
    assert limits(thickness + lower, thickness + upper, 4) in steps
    assert limits(*bank.STACK_L20_ACCEPT, 2) in steps
    short = f"SHORT OF {bank.STACK_L20_ACCEPT[0]:.2f}: REMAKE THE THINNEST GEAR"
    assert short in " ".join(steps.split())
    back_y = base.BOTTOM_REAR_Z - bank.BACK_STRAP_INNER_Z
    band = bank.BACK_STRAP_LOCATE_BAND
    assert f"Y {limits(back_y - band, back_y + band, 2)}" in steps
    # Step 10: the north MHA-CH-008 ear inner face on the same DRO zero and band.
    ear_y = base.BOTTOM_REAR_Z - rockers.NORTH_EAR_INNER_Z
    assert f"EAR INNER FACE TO Y {limits(ear_y - band, ear_y + band, 2)}" in steps
    assert f"A {bank.BANK_END_FEELER:.2f} LEAF" in steps
    assert f"A {bank.BANK_END_PLAY[0]:.2f} LEAF ENTERS" in steps
    assert steps.index("BANK PUSHED BACK:") < steps.index(
        f"A {bank.BANK_END_PLAY[0]:.2f} LEAF ENTERS"
    )
    assert f"A {bank.BANK_END_PLAY[1]:.2f} LEAF DOES NOT" in steps
    for gone in ("MHA-125", "0.025", "-6.0", "END PLAY 0.5-0.8"):
        assert gone not in steps, gone
    assert "MHA-VN-034" in steps
    dome = f"{bank.ARBOR_DOME_HEIGHT:.1f}"
    assert f"PLUS A {dome} DOME EACH END" in steps
    assert f"EACH DOME STANDS {dome} PROUD" in steps


def test_bank_drills_the_front_foot_with_the_loaded_mandrel_off_the_base() -> None:
    """dtrefactor F1/F2 on #937: the loaded mandrel hangs from the back strap
    until the front strap goes on, and its front end covers the front foot
    hole, so it is propped, then lifted off for the drill and tap."""
    steps = " ".join(drawing.BANK_STEPS.split())
    prop = steps.index("PROP THE MANDREL FRONT END")
    front_on = steps.index("9C. SLIDE THE FRONT MHA-DT-002 ON")
    spot = steps.index("SPOT AS 9A", front_on)
    mandrel_off = steps.index("DRAW THE LOADED MANDREL OUT OF THE BACK MHA-DT-002")
    drill = steps.index("DRILL AND TAP AS 9A", mandrel_off)
    back_in = steps.index("PASS THE MANDREL BACK THROUGH THE BACK MHA-DT-002")
    refit = steps.index("REFIT THE FRONT MHA-DT-002; RE-SET THE LEAF AND X")
    assert prop < front_on < spot < mandrel_off < drill < back_in < refit
    assert "LIFT OFF, DRILL AND TAP" not in steps


def test_ring_overhang_check_matches_the_cylinder_gear_print() -> None:
    """dtrefactor F4 on #937: check 3 and the MHA-DT-012 callout print the same
    bound, the bank's RING_OVERHANG_MAX."""
    import ch_connecting_rod_spec as rod
    import cylinder_bank_layout as bank
    import dt_cylinder_gear_notes

    bound = f"{bank.RING_OVERHANG_MAX:.2f}"
    checks = " ".join(drawing.CHECKS.split())
    assert f"OVERHANG ITS CAM UP TO {bound} (AT LEAST" in checks
    assert f"OVERHANGS CAM {bound} MAX" in dt_cylinder_gear_notes.STACK_FIT_CALLOUT
    on_cam = 100.0 * (rod.RING_THICKNESS - bank.RING_OVERHANG_MAX) / rod.RING_THICKNESS
    assert f"AT LEAST {math.floor(on_cam)}% OF THE RING WIDTH" in checks
    assert "0.56" not in checks


def test_the_collar_pin_explodes_with_the_arbor_and_the_strap_pins_stay() -> None:
    """Main's MHA-VN-033 ruling: one family serves as the two strap set pins and
    the MHA-DT-033 collar pin.  The builder tags the collar pin by what it pins,
    and only that instance leaves, with the arbor; the strap pins stay with
    the stationary strap group."""
    assert drawing.BOM_PART_NUMBERS["vn-pinion-strap-pin"] == "MHA-VN-033"
    moved = {step.label: names for step, names in spec.plan_explode(_instances())}
    assert moved["arbor collar pin"] == ("vn-pinion-strap-pin-3",)
    steps = {step.label: step for step in spec.EXPLODE_STEPS}
    arbor, pin = steps["pinion arbor"], steps["arbor collar pin"]
    assert (pin.axis, pin.distance_mm) == (arbor.axis, arbor.distance_mm)
    every_moved = {name for names in moved.values() for name in names}
    assert not {"vn-pinion-strap-pin-1", "vn-pinion-strap-pin-2"} & every_moved


def test_the_collar_pin_role_is_carried_by_exactly_one_pin() -> None:
    untagged = [
        spec.Instance(i.name, i.stem, i.origin_mm) for i in _instances()
    ]
    with pytest.raises(ValueError, match="must tag one"):
        spec.plan_explode(untagged)
    twice = [
        spec.Instance(i.name, i.stem, i.origin_mm, spec.COLLAR_PIN_ROLE)
        if i.stem == "vn-pinion-strap-pin"
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
    """The builder proves the tagged MHA-VN-033 sits in the collar's pin hole
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
