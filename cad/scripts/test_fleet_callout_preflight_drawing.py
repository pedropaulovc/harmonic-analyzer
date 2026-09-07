"""Migrated gear VIEW pilots consume built parts, not alignment experiments."""

import ast
import importlib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import _drawing_common as common
from diagnostics import _callout_recipe_contract as contract
from diagnostics import probe_datum_policy_recipes as pilot
from diagnostics._drawing_lower_text_control import CalloutStorage
from diagnostics._native_drawing_save_control import DrawingSave
from diagnostics._source_callout_authoring import SourceCalloutAuthoring
from diagnostics._source_save_boundaries import SourceObservation


GEARS = (
    "crank_drive_gear",
    "crank_pinion",
    "cylinder_gear",
    "rack_pinion",
    "transgear_feed_pinion",
    "transgear_pinion",
)


class ReachedOwnedSetup(Exception):
    """Test-only stop after real preflight and before any file/native work."""


@pytest.mark.parametrize("target", GEARS)
@pytest.mark.asyncio
async def test_normal_gear_pilot_never_enters_alignment_contract_or_authoring(
    target, monkeypatch, tmp_path
):
    module = importlib.import_module("draw_" + target)
    source = Path(module.__file__).read_text(encoding="utf-8")
    assert module.verify_dimension_callouts is common.verify_dimension_callouts
    assert not hasattr(module, "set_dimension_callouts")
    nodes = [
        node
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "verify_dimension_callouts"
    ]
    assert len(nodes) == 1
    keywords = {kw.arg: kw.value for kw in nodes[0].keywords}
    assert ast.literal_eval(keywords["feature_name"]) == "BoreProfile"
    assert {"view", "source_model"} <= keywords.keys()
    # The alignment experiment remains intentionally narrower than production.
    with pytest.raises(ValueError, match="ArborBoreProfile"):
        contract.recipe_contract(source)
    forbidden = Mock(
        side_effect=AssertionError("alignment contract must stay unselected")
    )
    monkeypatch.setattr(pilot.benchmark, "recipe_source", forbidden)
    native = Mock(side_effect=AssertionError("no attach during offline preflight"))
    monkeypatch.setattr(pilot, "run_copy_diagnostic", native)
    output = SimpleNamespace(mkdir=Mock(side_effect=ReachedOwnedSetup))
    with pytest.raises(ReachedOwnedSetup):
        await pilot.pilot(
            SimpleNamespace(), "frozen", tmp_path, tmp_path, output, targets=(target,)
        )
    output.mkdir.assert_called_once_with(parents=True, exist_ok=True)
    forbidden.assert_not_called()
    native.assert_not_called()


@pytest.mark.parametrize("target", GEARS)
@pytest.mark.parametrize(
    "experiment", ("observed_save", "source_authoring", "lower_text")
)
@pytest.mark.asyncio
async def test_alignment_experiments_reject_every_gear_before_owned_work(
    target, experiment, tmp_path, monkeypatch
):
    selected = {
        "source_observation": SourceObservation.ALIGNMENT_SAVE,
        "drawing_save": DrawingSave.LEGACY,
    }
    if experiment == "source_authoring":
        selected["source_callout_authoring"] = SourceCalloutAuthoring.ALIGNMENT_FIT
    if experiment == "lower_text":
        selected["callout_storage"] = CalloutStorage.LOWER_TEXT
    source_reader = Mock(
        side_effect=AssertionError("must reject before recipe loading")
    )
    monkeypatch.setattr(pilot.benchmark, "recipe_source", source_reader)
    output = SimpleNamespace(mkdir=Mock(side_effect=AssertionError("must not create")))
    with pytest.raises(ValueError, match="only alignment_pinion"):
        await pilot.pilot(
            SimpleNamespace(),
            "frozen",
            tmp_path,
            tmp_path,
            output,
            targets=(target,),
            **selected,
        )
    source_reader.assert_not_called()
    output.mkdir.assert_not_called()


@pytest.mark.parametrize("target", GEARS)
def test_newly_built_gear_bytes_need_an_explicit_new_source_receipt(target, tmp_path):
    source = tmp_path / f"{target}.SLDPRT"
    source.write_bytes(b"new exact authored source output for this test")
    assert pilot.attachments.file_digest(source) != pilot.EXPECTED_PART_HASHES[target]
    with pytest.raises(RuntimeError, match="exact immutable source hash mismatch"):
        pilot.require_sources({target: source}, {target: source})
