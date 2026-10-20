"""Offline selection, canonical carrier and review identity contracts."""

from dataclasses import asdict, replace
import json

import pytest

import _machinist_review_settings as settings


def test_defaults_and_roles_remain_independent():
    default = settings.resolve_settings()
    assert (default.reviewer, default.model, default.effort) == (
        "claude",
        "claude-opus-5-5",
        "medium",
    )
    assert (default.judge_reviewer, default.judge_model, default.judge_effort) == (
        "claude",
        "claude-opus-5-5",
        "medium",
    )
    codex = settings.resolve_settings(reviewer="codex")
    assert (codex.model, codex.effort) == ("gpt-6-astra", "low")
    assert codex.judge_reviewer == "claude"
    assert settings.resolve_settings(judge_reviewer="codex").reviewer == "claude"
    assert settings.resolve_settings(**asdict(default)) == default
    assert settings.from_carrier(None) == default
    assert settings.from_carrier(default.canonical()) == default
    assert settings.resolve_settings(**asdict(default)).identity() == default.identity()


def test_explicit_codex_high_preserves_exact_cli_requests():
    selected = settings.resolve_settings(
        reviewer="codex",
        model="gpt-6-astra",
        effort="high",
        judge_reviewer="codex",
        judge_model="gpt-6-astra",
        judge_effort="high",
    )
    assert settings.from_carrier(selected.canonical()) == selected
    assert selected.cli_args() == [
        "--reviewer",
        "codex",
        "--model",
        "gpt-6-astra",
        "--effort",
        "high",
        "--judge-reviewer",
        "codex",
        "--judge-model",
        "gpt-6-astra",
        "--judge-effort",
        "high",
    ]
    assert json.loads(selected.canonical()) == asdict(selected)
    assert settings.BUILD_RUNS == 3


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("reviewer", "codex"),
        ("model", "alternate-model"),
        ("effort", "high"),
        ("judge_reviewer", "codex"),
        ("judge_model", "alternate-model"),
        ("judge_effort", "high"),
    ],
)
def test_each_effective_field_changes_identity(field, value):
    default = settings.resolve_settings()
    changed = replace(default, **{field: value})
    assert changed.canonical() != default.canonical()
    assert changed.identity() != default.identity()


@pytest.mark.parametrize("field", settings.SETTING_FIELDS)
@pytest.mark.parametrize(
    "value",
    [
        "",
        " ",
        " high",
        "high ",
        "hi gh",
        "high\n",
        "-high",
        "hi\x00gh",
        "hi\u202egh",
        1,
        True,
    ],
)
def test_malformed_selection_is_not_defaulted(field, value):
    with pytest.raises(ValueError, match=field.replace("_", "-")):
        settings.resolve_settings(**{field: value})


@pytest.mark.parametrize("field", ["reviewer", "judge_reviewer"])
@pytest.mark.parametrize("value", ["unknown", "Codex"])
def test_unknown_provider_is_rejected(field, value):
    with pytest.raises(ValueError, match="reviewer"):
        settings.resolve_settings(**{field: value})


@pytest.mark.parametrize("carrier", ["", "null", "[]", "true", "{}", "{broken"])
def test_invalid_carrier_fails_loudly(carrier):
    with pytest.raises(ValueError, match=settings.SETTINGS_ENV):
        settings.from_carrier(carrier)


@pytest.mark.parametrize("invalid", ["missing", "unknown", "null", "nonstring"])
def test_carrier_requires_exactly_six_string_values(invalid):
    values = asdict(settings.resolve_settings())
    if invalid == "missing":
        values.pop("model")
    elif invalid == "unknown":
        values["runs"] = 3
    else:
        values["model"] = None if invalid == "null" else 3
    with pytest.raises(ValueError, match=settings.SETTINGS_ENV):
        settings.from_carrier(json.dumps(values))


def test_opaque_model_and_effort_are_not_rewritten_or_given_a_static_allowlist():
    selected = settings.resolve_settings(
        model="future/model-v2", effort="future-effort"
    )
    assert selected.model == "future/model-v2"
    assert selected.effort == "future-effort"
