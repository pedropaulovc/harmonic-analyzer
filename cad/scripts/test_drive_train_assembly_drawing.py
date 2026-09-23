"""Offline contract for the drive-train assembly package and its explode plan."""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest
import yaml

import draw_drive_train_assembly as drawing
import drive_train_assembly_spec as spec
from _drawing_registry import DRAWINGS_BY_NAME

SCRIPTS = Path(__file__).resolve().parent
PARTS = SCRIPTS.parent / "config" / "parts"
BUILDER = SCRIPTS / "build_drive_train_assembly.py"
# Installation interfaces the package may cite without owning a BOM row.
EXTERNAL_NUMBERS = frozenset({"MHA-035"})


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
        "cylinder-gear-shaft": [(drum_x, 90.5, -86.9)],
        "arbor-pedestal": [(drum_x, 50.8, -87.4), (drum_x, 50.8, 100.6)],
        "cylinder-end-disc": [(drum_x, 90.5, -72.5), (drum_x, 90.5, 72.1)],
        "dome-cap-screw": [(drum_x, 90.5, -89.4), (drum_x, 90.5, 102.6)],
        "cylinder-gear": [(drum_x, 90.5, -64.0 + 7.0 * j) for j in range(20)],
        "foot-screw": [(7.49, 52.0, 74.0), (drum_x, 53.0, -92.4), (drum_x, 53.0, 105.6)],
        "slotted-screw": [(-19.4, 60.0, -94.9), (7.6, 60.0, -94.9), (-19.4, 60.0, 85.1), (7.6, 60.0, 85.1)],
        "cone-gear": [(-115.0 + j, 90.5, -25.0 + 6.0 * j) for j in range(20)],
        "pinion-bracket": [(-12.1, 62.8, -72.0), (-12.1, 62.8, 71.0)],
        "pinion-pivot-block": [(-5.9, 62.8, -95.0), (-5.9, 62.8, 85.0)],
        "pinion-cam-pin": [(-8.0, 70.0, -72.0), (-8.0, 70.0, 71.0)],
        "pinion-cam": [(0.4, 64.7, -72.0), (0.4, 64.7, 71.0)],
    }
    layout.update(overrides)
    instances = []
    for stem in sorted(_builder_stems() | set(layout)):
        for index, origin in enumerate(layout.get(stem, [(0.0, 100.0, 0.0)]), start=1):
            instances.append(spec.Instance(f"{stem}-{index}", stem, origin))
    return instances


def test_registry_row_and_outputs() -> None:
    row = DRAWINGS_BY_NAME["drive_train_assembly"]
    assert row.source_kind == "assembly" and row.part == "drive_train"
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


def test_package_text_cites_only_bom_or_external_part_numbers() -> None:
    texts = (
        drawing.ASSEMBLED_HEADING,
        drawing.CONE_CRANK_STEPS,
        drawing.BANK_RIG_STEPS,
        drawing.CHECKS,
        drawing.SETUP_NOTES,
        drawing.INTERFACE_NOTES,
        drawing.FIT_PLACEHOLDER,
        *drawing.BOM_DESCRIPTIONS.values(),
    )
    cited = set(re.findall(r"MHA-\d{3}", "\n".join(texts)))
    assert cited <= set(drawing.BOM_PART_NUMBERS.values()) | EXTERNAL_NUMBERS


def test_note_lines_fit_a_half_sheet_field() -> None:
    """3.5 mm text renders about 2.63 mm per character; a field is 194 mm wide."""
    for text in (
        drawing.CONE_CRANK_STEPS,
        drawing.BANK_RIG_STEPS,
        drawing.CHECKS,
        drawing.SETUP_NOTES,
        drawing.INTERFACE_NOTES,
        drawing.FIT_PLACEHOLDER,
    ):
        for line in text.format(
            cone_gears=20, cylinder_gears=20, cam_pins=2, pivot_blocks=2, cams=2, slotted=4, foot=3
        ).splitlines():
            assert len(line) <= 70, line


def test_sheet_numbers_are_pinned_where_the_sheets_cite_them() -> None:
    names = drawing.SHEET_NAMES
    assert len(names) == 8
    assert names[drawing.SEQUENCE_SHEET - 1] == "ASSEMBLY SEQUENCE"
    assert names[drawing.CHECKS_SHEET - 1] == "CHECKS + SETUP"
    assert names[drawing.FIT_SHEET - 1] == "MESH + FIT DETAILS"
    assert sorted(drawing.CLUSTER_SHEETS.values()) == [3, 4, 5]
    assert "SHEET 6" in drawing.BOM_REFERENCE_CAPTION
    assert all(text.count(",") <= 1 for text in drawing.BOM_DESCRIPTIONS.values())
    assert "SEE SHEET 8" in drawing.ASSEMBLED_HEADING
    assert "SHEET 8" in drawing.BANK_RIG_STEPS


def test_explode_plan_resolves_every_step_on_the_built_census() -> None:
    plan = spec.plan_explode(_instances())
    assert [step.label for step, _names in plan] == [s.label for s in spec.EXPLODE_STEPS]
    moved = {step.label: names for step, names in plan}
    assert moved["south pedestal"] == ("arbor-pedestal-1", "foot-screw-2")
    assert moved["north pedestal"] == ("arbor-pedestal-2", "foot-screw-3")
    assert moved["pedestal screws lift"] == ("foot-screw-2", "foot-screw-3")
    assert moved["spring foot screw lifts"] == ("foot-screw-1",)
    assert moved["block screws lift"] == tuple(f"slotted-screw-{i}" for i in range(1, 5))


def test_explode_plan_refuses_unknown_retired_and_missing_families() -> None:
    with pytest.raises(ValueError, match="does not classify"):
        spec.plan_explode([*_instances(), spec.Instance("widget-1", "widget", (0, 0, 0))])
    with pytest.raises(ValueError, match="does not classify"):
        spec.plan_explode(
            [*_instances(), spec.Instance("pinion-handle-pin-1", "pinion-handle-pin", (0, 0, 0))]
        )
    census = [i for i in _instances() if i.stem != "crank-handle"]
    with pytest.raises(ValueError, match="absent from the model"):
        spec.plan_explode(census)


def test_pending_families_join_the_plan_when_they_land() -> None:
    census = _instances()
    assert not {i.stem for i in census} & spec.PENDING_STEMS
    landed = [
        *census,
        spec.Instance("crank-hub-1", "crank-hub", (-129.3, 129.9, -170.0)),
        spec.Instance("crank-hub-pin-1", "crank-hub-pin", (-129.3, 122.0, -170.0)),
        spec.Instance("pinion-lever-pin-1", "pinion-lever-pin", (0.4, 64.7, -108.0)),
    ]
    moved = {step.label: names for step, names in spec.plan_explode(landed)}
    assert "crank-hub-1" in moved["crank arm group"]
    assert "pinion-lever-pin-1" in moved["pinion lever"]


def test_explode_families_are_either_moved_or_stationary_never_both() -> None:
    moved = {stem for step in spec.EXPLODE_STEPS for stem in step.stems}
    assert not moved & spec.STATIONARY_STEMS
    assert moved | spec.STATIONARY_STEMS == spec.classified_stems()


def test_clusters_partition_every_instance_once() -> None:
    census = _instances()
    members = spec.cluster_members(census)
    flat = [name for names in members.values() for name in names]
    assert sorted(flat) == sorted(i.name for i in census)
    assert "foot-screw-1" in members["pinion-rig"]
    assert {"foot-screw-2", "foot-screw-3"} <= set(members["cylinder-bank"])


def test_source_refusals_and_bom_order() -> None:
    counts = drawing.instance_counts(_instances())
    assert drawing.source_violations(counts) == []
    assert drawing.bom_components(counts)[0] == "cylinder-gear-shaft"
    assert set(drawing.bom_components(counts)) == set(counts)
    del counts["crank-arm"]
    assert "crank-arm" in drawing.source_violations(counts)[0]
    assert drawing.source_violations({**counts, "crank-arm": 1, "pinion-handle-pin": 1})


def test_cone_station_rows_run_front_to_back() -> None:
    rows = drawing.cone_station_rows([(30.0, "T006"), (-25.0, "T120"), (0.0, "T060")])
    assert rows == [(1, "T120"), (2, "T060"), (3, "T006")]
    table = drawing.station_table_text(rows)
    assert table.splitlines()[1].startswith("STN  1  T120")


def test_bom_split_keeps_the_second_column_no_taller() -> None:
    assert drawing.bom_split_row(39) == 20
    assert drawing.bom_split_row(42) == 21
    with pytest.raises(ValueError):
        drawing.bom_split_row(1)
    # Two columns side by side stay left of the reference isometric.
    right = drawing.BOM_SECOND_COLUMN_X + drawing.BOM_COLUMN_WIDTH
    assert right < drawing.BOM_REFERENCE_ISO_CENTER[0] - 0.030


def test_bom_budget_refuses_the_title_block_and_sheet_edges() -> None:
    assert drawing.bom_extent_violations(drawing.BOM_ANCHOR, 0.164, 0.130) == []
    assert drawing.bom_extent_violations((0.300, 0.100), 0.100, 0.050)
    assert drawing.bom_extent_violations((0.001, 0.200), 0.100, 0.050)


def test_balloon_attachment_gate_names_every_mismatch() -> None:
    records = [("B1", "1", ("crank-arm",)), ("B2", "3", ("crank-pin",)), ("B3", "4", ())]
    findings = drawing.balloon_attachment_violations(
        records, {"crank-arm": "1", "crank-pin": "2", "crank-handle": "5"}
    )
    assert any("shows item 3" in f for f in findings)
    assert any("attaches to []" in f for f in findings)
    assert any("crank-handle" in f for f in findings)


def test_note_fields_and_ring_fit() -> None:
    field = drawing.NOTE_FIELD_LEFT
    assert drawing.note_field_violations((0.020, 0.100, 0.200, 0.250), field) == []
    assert len(drawing.note_field_violations((0.010, 0.020, 0.300, 0.300), field)) == 4
    shift, overflows = drawing.ring_fit_shift((0.1, 0.1, 0.2, 0.2), (0.0, 0.0, 0.5, 0.5), grow=0.01)
    assert shift == pytest.approx((0.1, 0.1)) and overflows == []
