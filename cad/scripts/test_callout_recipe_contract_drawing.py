"""A recipe ABI is explicit; diagnostic selection cannot create retired aliases."""

from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest

from diagnostics import _callout_recipe_contract as contract
from diagnostics import probe_datum_policy_recipes as pilot
from diagnostics._drawing_lower_text_control import CalloutStorage
from diagnostics._native_drawing_save_control import DrawingSave
from diagnostics._source_callout_authoring import SourceCalloutAuthoring
from diagnostics._source_save_boundaries import SourceObservation


def recipe(helper, *, feature="ArborBoreProfile"):
    return (
        f"from _drawing_common import {helper}\n"
        f"def build(adapter):\n"
        f"    {helper}(adapter, (), {{}}, feature_name={feature!r}, view=front, source_model=part)\n"
    )


@pytest.mark.parametrize("value", tuple(contract.CalloutContract))
def test_each_explicit_version_has_one_native_helper(value):
    assert contract.recipe_contract(recipe(value.helper_name)) is value


def test_current_tracked_alignment_uses_verifier_not_setter():
    code = Path(__file__).with_name("draw_alignment_pinion.py").read_text(encoding="utf-8")
    assert contract.recipe_contract(code) is contract.CalloutContract.SOURCE_VERIFIER_V1


def test_unselected_default_does_not_load_any_callout_contract(monkeypatch):
    reader = Mock(side_effect=AssertionError("unselected recipe has no callout scan"))
    monkeypatch.setattr(pilot.benchmark, "recipe_source", reader)
    assert pilot.selected_callout_contract("unused", None, None, None) is None
    reader.assert_not_called()


@pytest.mark.parametrize(
    "code",
    [
        "def build(): pass",
        "from elsewhere import verify_dimension_callouts",
        "from ._drawing_common import verify_dimension_callouts",
        "from _drawing_common import verify_dimension_callouts as alias",
        "from _drawing_common import set_dimension_callouts, verify_dimension_callouts",
        recipe("verify_dimension_callouts", feature="OtherFeature"),
        recipe("verify_dimension_callouts").replace(
            ", view=front, source_model=part", ""
        ),
        recipe("verify_dimension_callouts")
        + "verify_dimension_callouts(a, (), {}, feature_name='ArborBoreProfile')",
    ],
)
def test_unsupported_contract_is_not_inferred(code):
    with pytest.raises(ValueError, match="contract"):
        contract.recipe_contract(code)


@pytest.mark.parametrize("route", ["parent", "worker", "direct"])
@pytest.mark.parametrize(
    "experiment", ["lower_text", "lower_text_before_save", "source_authoring"]
)
@pytest.mark.asyncio
async def test_wrong_recipe_experiment_fails_before_attach_or_owned_outputs(
    monkeypatch, tmp_path, route, experiment
):
    source_authoring = experiment == "source_authoring"
    helper = (
        "set_dimension_callouts" if source_authoring else "verify_dimension_callouts"
    )
    monkeypatch.setattr(pilot.benchmark, "revision", lambda _: "frozen")
    monkeypatch.setattr(pilot.benchmark, "recipe_source", lambda *_: recipe(helper))
    monkeypatch.setattr(pilot, "require_owned_diagnostic_environment", lambda: None)
    native = Mock(side_effect=AssertionError("must reject before native attach"))
    monkeypatch.setattr(pilot, "run_copy_diagnostic", native)
    import sys

    monkeypatch.setitem(sys.modules, "dodo", NS(_run=native))
    adapter = NS(ownership=native)
    output = tmp_path / "must-not-create"
    with pytest.raises(ValueError, match=r"historical|frozen"):
        if route == "direct":
            await pilot.pilot(
                adapter,
                "frozen",
                tmp_path,
                tmp_path,
                output,
                targets=("alignment_pinion",),
                source_observation=SourceObservation.ALIGNMENT_SAVE,
                drawing_save=DrawingSave.LEGACY,
                **(
                    {"source_callout_authoring": SourceCalloutAuthoring.ALIGNMENT_FIT}
                    if source_authoring
                    else {"callout_storage": CalloutStorage(experiment)}
                ),
            )
        else:
            pilot.main(
                [
                    "--source-root",
                    str(tmp_path),
                    "--guard-root",
                    str(tmp_path),
                    "--report-root",
                    str(output),
                    "--target",
                    "alignment_pinion",
                    "--source-observation",
                    "alignment_save",
                    "--drawing-save",
                    "legacy",
                    *(
                        ["--source-callout-authoring", "alignment_fit"]
                        if source_authoring
                        else ["--callout-storage", experiment]
                    ),
                    *(["--worker"] if route == "worker" else []),
                ]
            )
    native.assert_not_called()
    assert not output.exists()
