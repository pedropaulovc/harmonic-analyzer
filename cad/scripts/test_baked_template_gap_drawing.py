"""Measured populated footprints inform only a new explicit blank-layout variant."""

from copy import deepcopy
import asyncio
import hashlib
import json
from types import SimpleNamespace
from unittest.mock import Mock
import pytest

from diagnostics._populated_template_native_fixture import RETAINED


def inputs():
    from diagnostics import _baked_template_layout as layout

    row = RETAINED["targets"]["rocker_arm"]
    notes = deepcopy(row["notes"])
    title = layout.unique_note(notes, link=layout.TITLE_LINK)
    base = {
        title: {
            "role": "title",
            "position": notes[title]["position"],
            "height_m": notes[title]["font"]["CharHeight"],
            "horizontal": 1,
            "cell": layout.cells.enclosing_cell(row["lines"], notes[title]["position"]),
        }
    }
    return notes, row["lines"], base, deepcopy(RETAINED["targets"])


def test_retained_both_source_footprints_get_measured_spacing_without_font_changes():
    from diagnostics import _baked_template_gaps as gaps

    notes, lines, base, targets = inputs()
    saved = deepcopy((notes, base, targets))
    plan, witness = gaps.measured_plan(notes, lines, base, targets)
    assert (notes, base, targets) == saved
    assert {row["role"] for row in plan.values()} == {
        "title",
        "material_label",
        "material",
        "finish",
    }
    assert plan["DetailItem245"]["position"][1] < notes["DetailItem245"]["position"][1]
    assert plan["DetailItem277"]["position"][1] < notes["DetailItem277"]["position"][1]
    assert plan["DetailItem244"]["position"][0] > plan["DetailItem279"]["position"][0]
    assert witness["validated_gap_m"] == 0.001
    assert witness["planned_gap_m"] == 0.0015
    for name, target in plan.items():
        assert target["height_m"] == notes[name]["font"]["CharHeight"]
    for target in witness["targets"].values():
        assert all(value >= 0.001 for value in target["predicted_gaps_m"].values())
    assert (
        witness["targets"]["channel_lever"]["before"]["finish"][2]
        - witness["targets"]["channel_lever"]["before"]["finish"][0]
        > 0.072
    )


@pytest.mark.parametrize(
    "mode", ["font", "link", "position", "geometry", "missing_source", "huge_finish"]
)
def test_new_layout_never_trusts_changed_or_nonfitting_measurements(mode):
    from diagnostics import _baked_template_gaps as gaps

    notes, lines, base, targets = inputs()
    if mode == "font":
        notes["DetailItem277"]["font"]["Bold"] = True
    if mode == "link":
        notes["DetailItem277"]["link"] = '$PRPSHEET:"Other"'
    if mode == "position":
        targets["channel_lever"]["notes"]["DetailItem244"]["position"][0] += 0.001
    if mode == "geometry":
        targets["channel_lever"]["lines"] = []
    if mode == "missing_source":
        targets.pop("channel_lever")
    if mode == "huge_finish":
        targets["channel_lever"]["notes"]["DetailItem277"]["extent"][1] -= 0.1
    with pytest.raises(RuntimeError):
        gaps.measured_plan(notes, lines, base, targets)


def population_receipt():
    rows = []
    for target, source in RETAINED["targets"].items():
        built = {
            "notes": source["notes"],
            "template_geometry": {
                "segments": [{"sheet_points": line} for line in source["lines"]]
            },
        }
        rows.append(
            {
                "target": target,
                "status": "observed",
                "cold_delta": {"changed_leaf_count": 0},
                "png_delta": {"changed_pixel_count": 0},
                "printed": {"classification": "unchanged"},
                "copy_hashes": {"initial": "saved", "final": "saved"},
                "linked_fields": {"built": deepcopy(built), "cold": deepcopy(built)},
                "acceptance_issues": source["issues"],
            }
        )
    inputs = {"C:/owned/templates/harmonic-analyzer.DRWDOT": "template"}
    return {
        "status": "failed",
        "inputs_before": inputs,
        "inputs_after": deepcopy(inputs),
        "trials": rows,
    }


@pytest.mark.parametrize(
    "mode",
    [
        "pass",
        "hash",
        "wrong_template",
        "input_drift",
        "incomplete",
        "cold_drift",
        "raw_drift",
        "source_saved",
        "duplicate",
    ],
)
def test_population_receipt_requires_pinned_complete_preserved_native_evidence(
    tmp_path, mode
):
    from diagnostics import _baked_template_gaps as gaps

    value = population_receipt()
    if mode == "input_drift":
        value["inputs_after"]["other"] = "changed"
    if mode == "incomplete":
        value["trials"].pop()
    if mode == "cold_drift":
        value["trials"][0]["cold_delta"]["changed_leaf_count"] = 1
    if mode == "source_saved":
        value["trials"][0]["copy_hashes"]["final"] = "new bytes"
    if mode == "duplicate":
        value["trials"][1]["target"] = "rocker_arm"
    if mode == "raw_drift":
        value["trials"][0]["linked_fields"]["cold"]["notes"]["DetailItem245"][
            "horizontal"
        ] = 2
    path = tmp_path / "population.json"
    path.write_text(json.dumps(value))
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if mode != "pass":
        with pytest.raises(RuntimeError):
            gaps.read_population(
                path,
                "0" * 64 if mode == "hash" else digest,
                "wrong" if mode == "wrong_template" else "template",
            )
        return
    result = gaps.read_population(path, digest, "template")
    assert result["sha256"] == digest
    assert set(result["targets"]) == {"rocker_arm", "channel_lever"}
    assert (
        result["original_issues"]["rocker_arm"]
        == RETAINED["targets"]["rocker_arm"]["issues"]
    )


def test_populated_variant_guard_and_evidence_flow_precede_any_native_mutation(
    monkeypatch, tmp_path
):
    from diagnostics import probe_baked_template_layout as probe
    from diagnostics import _baked_template_gaps as gaps

    template = tmp_path / "template.DRWDOT"
    template.write_bytes(b"original")
    receipt = tmp_path / "population.json"
    receipt.write_bytes(b"pinned evidence")
    digest = hashlib.sha256(receipt.read_bytes()).hexdigest()
    monkeypatch.setattr(probe.common, "PROJECT_DRWDOT", template)
    monkeypatch.setattr(probe.pilot, "helper_fingerprints", lambda: {})
    monkeypatch.setattr(probe.pilot, "adapter_fingerprints", lambda: {})
    monkeypatch.setattr(probe.pilot.benchmark, "revision", lambda _: "frozen")
    population = {
        "receipt": str(receipt),
        "sha256": digest,
        "targets": {"retained": "native"},
        "original_issues": ["kept"],
    }
    read = Mock(return_value=population)
    monkeypatch.setattr(gaps, "read_population", read)

    async def close():
        pass

    ownership = SimpleNamespace(register_directory=Mock(), register_source=Mock())
    adapter = SimpleNamespace(ownership=ownership, close_owned_documents=close)
    calls = []

    async def transform(adapter, directory, report, checkpoint, evidence):
        calls.append(evidence)
        report.update(
            derived_template=str(directory / "derived.DRWDOT"), outcome="test_observed"
        )

    monkeypatch.setattr(probe, "transform", transform)
    asyncio.run(
        probe.probe(
            adapter,
            tmp_path / "reports",
            policy=gaps.LayoutPolicy.POPULATED_GAPS,
            population_path=receipt,
            population_sha256=digest,
        )
    )
    assert calls == [population]
    assert receipt in [
        call.args[0] for call in ownership.register_source.call_args_list
    ]
    (path,) = (tmp_path / "reports").glob("*/template-layout.json")
    report = json.loads(path.read_text())
    assert report["population_evidence"]["original_issues"] == ["kept"]
    assert report["inputs_before"] == report["inputs_after"]
    with pytest.raises(ValueError):
        asyncio.run(probe.probe(adapter, tmp_path / "invalid", population_path=receipt))
    assert not (tmp_path / "invalid").exists()
    assert len(calls) == 1


def test_additional_roles_still_reject_any_font_or_link_change():
    from diagnostics import _baked_template_layout as layout
    from test_baked_template_layout_drawing import transformed, note

    before, after, plan = transformed()
    for role in ("material", "material_label", "finish"):
        before["notes"][role] = note(
            role, role, x=0.2, y=0.03, height=0.002, horizontal=1
        )
        after["notes"][role] = deepcopy(before["notes"][role])
        after["notes"][role]["position"][0] += 0.005
        plan[role] = {
            "role": role,
            "position": after["notes"][role]["position"],
            "horizontal": 1,
            "height_m": 0.002,
        }
    layout.require_transition(before, after, plan)
    for role in ("material", "material_label", "finish"):
        changed = deepcopy(after)
        changed["notes"][role]["font"]["CharHeight"] += 0.0001
        with pytest.raises(RuntimeError):
            layout.require_transition(before, changed, plan)
        changed = deepcopy(after)
        changed["notes"][role]["link"] = "different"
        with pytest.raises(RuntimeError):
            layout.require_transition(before, changed, plan)
