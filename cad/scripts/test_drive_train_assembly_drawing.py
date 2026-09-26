"""Offline contract for the drive-train assembly package and its explode plan."""

from __future__ import annotations

import ast
import math
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
# Ruled hardware the sequence already names while its BOM row, cluster stem and
# explode step wait for the drive-train integrator's single re-key (Main,
# 2026-09-23: drawing-only rulings commit). The integration commit that adds
# the rows deletes this set; the test below fails once a row lands anyway.
PRE_REGISTERED_NUMBERS = frozenset(
    {"MHA-139", "MHA-140", "MHA-141", "MHA-142"}
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
    """A stand-in census of the built model: builder families at plausible origins."""
    drum_x = -60.39
    layout = {
        "cylinder-gear-shaft": [(drum_x, 90.5, -86.9)],
        "arbor-pedestal": [(drum_x, 50.8, -87.4), (drum_x, 50.8, 100.6)],
        "cylinder-end-disc": [(drum_x, 90.5, -72.5), (drum_x, 90.5, 72.1)],
        "dome-cap-screw": [(drum_x, 90.5, -89.4), (drum_x, 90.5, 102.6)],
        "cylinder-gear": [(drum_x, 90.5, -64.0 + 7.0 * j) for j in range(20)],
        "foot-screw": [(7.49, 52.0, 74.0)],
        "pedestal-hold-down-screw": [(drum_x, 55.8, -91.652), (drum_x, 55.8, 94.202)],
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


def test_package_text_cites_only_bom_or_external_part_numbers() -> None:
    texts = (
        drawing.ASSEMBLED_HEADING,
        drawing.CONE_CRANK_STEPS,
        drawing.BANK_STEPS,
        drawing.RIG_STEPS,
        drawing.CHECKS,
        drawing.SETUP_NOTES,
        drawing.INTERFACE_NOTES,
        drawing.FIT_PLACEHOLDER,
        *drawing.BOM_DESCRIPTIONS.values(),
    )
    cited = set(re.findall(r"MHA-\d{3}", "\n".join(texts)))
    bom = set(drawing.BOM_PART_NUMBERS.values())
    assert cited <= bom | EXTERNAL_NUMBERS | PRE_REGISTERED_NUMBERS
    assert not PRE_REGISTERED_NUMBERS & bom, "integrated: drop PRE_REGISTERED_NUMBERS"


def test_note_lines_fit_a_half_sheet_field() -> None:
    """3.5 mm text renders about 2.63 mm per character; a field is 194 mm wide."""
    for text in (
        drawing.CONE_CRANK_STEPS,
        drawing.BANK_STEPS,
        drawing.RIG_STEPS,
        drawing.CHECKS,
        drawing.SETUP_NOTES,
        drawing.INTERFACE_NOTES,
        drawing.FIT_PLACEHOLDER,
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


def test_sheet_numbers_are_pinned_where_the_sheets_cite_them() -> None:
    names = drawing.SHEET_NAMES
    assert len(names) == 8
    assert names[drawing.SEQUENCE_SHEET - 1] == "ASSEMBLY SEQUENCE"
    assert names[drawing.CHECKS_SHEET - 1] == "CHECKS + SETUP"
    assert names[drawing.FIT_SHEET - 1] == "ASSEMBLY SEQUENCE CONT. + FIT"
    assert sorted(drawing.CLUSTER_SHEETS.values()) == [3, 4, 5]
    assert "SHEET 7" in drawing.BOM_REFERENCE_CAPTION
    assert all(text.count(",") <= 1 for text in drawing.BOM_DESCRIPTIONS.values())


def test_bom_descriptions_keep_one_line() -> None:
    for stem, text in drawing.BOM_DESCRIPTIONS.items():
        assert len(text) <= drawing.BOM_DESCRIPTION_MAX_CHARS, stem


def test_rig_is_located_by_its_parked_tip_gap() -> None:
    steps = drawing.RIG_STEPS
    for phrase in ("TRANSFERRED", "2.5 FEELER", "ACCEPT 2.3-2.7", "#8-32", "#4-40"):
        assert phrase in steps, phrase
    assert "ACCEPT 2.3-2.7 (SHEET 7, STEP 19)" in drawing.CHECKS
    assert "19. FACE A MHA-002 TOOTH TIP" in steps
    assert "SEE SHEET 8" in drawing.ASSEMBLED_HEADING
    assert "SHEET 8" in drawing.RIG_STEPS
    assert "SHEET 7" in drawing.BANK_STEPS


def test_drum_is_bonded_after_the_arbor_passes_the_front_strap() -> None:
    """The front strap bore is closed: a bonded drum can no longer pass it."""
    steps = drawing.RIG_STEPS
    front = steps.index("THROUGH THE FRONT MHA-056 TOP BORE")
    drum = steps.index("FIT MHA-002 ON MHA-102")
    back = steps.index("IN THE BACK MHA-056 TOP BORE")
    assert front < drum < back


def test_torque_shaft_pins_go_in_before_the_cams() -> None:
    """MHA-062 is drilled off the machine; the cams block the pin's west edge."""
    steps = drawing.RIG_STEPS
    assert steps.index("SPRING PIN PER STRAP") < steps.index("FIT {cams}X MHA-104")


def test_explode_plan_resolves_every_step_on_the_built_census() -> None:
    plan = spec.plan_explode(_instances())
    assert [step.label for step, _names in plan] == [s.label for s in spec.EXPLODE_STEPS]
    moved = {step.label: names for step, names in plan}
    assert moved["south pedestal"] == ("arbor-pedestal-1", "pedestal-hold-down-screw-1")
    assert moved["north pedestal"] == ("arbor-pedestal-2", "pedestal-hold-down-screw-2")
    assert moved["pedestal screws lift"] == (
        "pedestal-hold-down-screw-1",
        "pedestal-hold-down-screw-2",
    )
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
    ]
    moved = {step.label: names for step, names in spec.plan_explode(landed)}
    assert "crank-hub-1" in moved["crank arm group"]


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
    assert {"pedestal-hold-down-screw-1", "pedestal-hold-down-screw-2"} <= set(
        members["cylinder-bank"]
    )


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
    # The reference isometric sits under the taller first column. The farm
    # measured a 124.2 mm header + 19-row piece, so the header is ~10.2 mm;
    # a 1:8 reference view's outline is ~49 mm tall.
    first_bottom = drawing.BOM_ANCHOR[1] - (0.0102 + 20 * drawing.BOM_ROW_HEIGHT)
    assert drawing.BOM_REFERENCE_ISO_CENTER[1] + 0.0247 < first_bottom - 0.010
    assert drawing.BOM_REFERENCE_ISO_CENTER[0] < drawing.BOM_SECOND_COLUMN_X


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


class _Adapter:
    def _attempt(self, fn, default=None):
        try:
            return fn()
        except Exception:
            return default


class _Curve:
    def __init__(self, radius: float | None):
        self.radius = radius

    def IsCircle(self) -> bool:  # noqa: N802 - COM name
        return self.radius is not None

    @property
    def CircleParams(self):  # noqa: N802 - COM name
        return (0.0, 0.0, 0.0, 0.0, 0.0, 1.0, self.radius)


class _Edge:
    def __init__(self, radius: float | None):
        self.curve = _Curve(radius)

    def GetCurve(self):  # noqa: N802 - COM name
        return self.curve


class _DrawingComponent:
    def __init__(self, name: str):
        self.Name = f"{name}@drive-train"
        self.Component = name


class _View:
    """A placed view whose components show the given visible edges."""

    def __init__(self, edges: dict[str, list[_Edge]]):
        self.edges = edges
        children = [_DrawingComponent(name) for name in edges]
        self.root = type("Root", (), {"GetChildren": lambda _self: children})()

    def RootDrawingComponent2(self, _flag):  # noqa: N802 - COM name
        return self.root

    def GetVisibleEntities2(self, component, kind):  # noqa: N802 - COM name
        assert kind == drawing.SW_VIEW_ENTITY_EDGE
        return tuple(self.edges[component])


def _bank_facts():
    instances = [
        spec.Instance("pedestal-hold-down-screw-1", "pedestal-hold-down-screw", (0.0, 0.0, 80.0)),
        spec.Instance("pedestal-hold-down-screw-2", "pedestal-hold-down-screw", (0.0, 0.0, -80.0)),
    ]
    return type(
        "Facts",
        (),
        {"instances": instances, "clusters": {"cylinder-bank": ("pedestal-hold-down-screw-1", "pedestal-hold-down-screw-2")}},
    )()


def test_head_anchor_takes_the_largest_rim_and_falls_through_hidden_instances(monkeypatch):
    placed = []
    monkeypatch.setattr(
        drawing,
        "_insert_balloon_on_edge",
        lambda _a, _v, edge, **kw: placed.append((edge, kw["stem"])) or edge,
    )
    rim, shank = _Edge(0.0027), _Edge(0.0014)
    # r7: the south screw (preferred) showed nothing usable; the north one does.
    view = _View({"pedestal-hold-down-screw-1": [_Edge(None), shank, rim], "pedestal-hold-down-screw-2": []})
    balloons, anchored = drawing._head_anchored_balloons(
        _Adapter(), view, "cylinder-bank", _bank_facts(), {"pedestal-hold-down-screw": "26"}, label="t"
    )
    assert placed == [(rim, "pedestal-hold-down-screw")] and balloons == [rim]
    assert anchored == {"pedestal-hold-down-screw"}


def test_head_anchor_without_any_rim_leaves_the_family_to_the_shared_picker(monkeypatch):
    monkeypatch.setattr(drawing, "_insert_balloon_on_edge", pytest.fail)
    view = _View({"pedestal-hold-down-screw-1": [_Edge(None)], "pedestal-hold-down-screw-2": []})
    balloons, anchored = drawing._head_anchored_balloons(
        _Adapter(), view, "cylinder-bank", _bank_facts(), {"pedestal-hold-down-screw": "26"}, label="t"
    )
    assert balloons == [] and anchored == frozenset()


def test_every_text_sheet_places_a_view_for_its_title_block() -> None:
    """finalize_drawing refuses a sheet with no view (r8 leaf 20260923T214354Z-1-4126331f)."""
    tree = ast.parse(Path(drawing.__file__).read_text(encoding="utf-8"))
    placers = {
        node.name: node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name.startswith("_place_")
    }
    for name in ("_place_sequence_sheet", "_place_fit_sheet", "_place_checks_sheet"):
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


# Printed text cites no internal governance: rule numbers, ruling ids
# (U41), "policy", "ruling", or a named/accepted exception.  Those are
# provenance for the comments beside the text (Main, S1 round 5).
_INTERNAL_REFERENCE = re.compile(
    r"\bRULE\s*\d+|\bU\d{2,}\b|\bPOLIC(?:Y|IES)\b|\bRULINGS?\b|\b(?:NAMED|ACCEPTED)\s+EXCEPTION",
    re.IGNORECASE,
)


def test_printed_package_text_cites_no_internal_rule_or_ruling() -> None:
    blocks = {
        name: value
        for name, value in vars(drawing).items()
        if isinstance(value, str)
        and name.isupper()
        and (name.endswith(("_STEPS", "_NOTES", "_HEADING")) or name in ("CHECKS", "FIT_PLACEHOLDER"))
    }
    assert {"CONE_CRANK_STEPS", "BANK_STEPS", "RIG_STEPS", "CHECKS", "SETUP_NOTES"} <= set(blocks)
    hits = {
        name: _INTERNAL_REFERENCE.findall(" ".join(text.split()))
        for name, text in blocks.items()
    }
    assert not {name: found for name, found in hits.items() if found}
    # The positive control: the pattern does catch what it forbids.
    for sample in ("NAMED EXCEPTION TO RULE 12.", "PER U41", "PER POLICY", "SEE RULING"):
        assert _INTERNAL_REFERENCE.search(sample), sample
