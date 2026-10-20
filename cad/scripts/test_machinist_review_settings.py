"""Offline selection, canonical carrier and review identity contracts."""

from dataclasses import FrozenInstanceError, asdict, fields, replace
import json

import pytest

import machinist_review_config as settings


@pytest.fixture(autouse=True)
def isolated_selection(monkeypatch):
    monkeypatch.delenv("HARMONIC_MACHINIST_REVIEWER", raising=False)
    monkeypatch.delenv(settings.SETTINGS_ENV, raising=False)


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


def test_selection_is_an_exact_frozen_six_field_dataclass():
    selected = settings.resolve_settings()
    assert tuple(field.name for field in fields(selected)) == settings.SETTING_FIELDS
    with pytest.raises(FrozenInstanceError):
        selected.reviewer = "codex"


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


@pytest.mark.parametrize("selector", ["codex", "invalid-registered-selector"])
def test_standalone_resolution_ignores_registered_environment(monkeypatch, selector):
    expected = settings.resolve_settings()
    monkeypatch.setenv("HARMONIC_MACHINIST_REVIEWER", selector)
    monkeypatch.setenv(settings.SETTINGS_ENV, "{broken")
    assert settings.resolve_settings() == expected
    assert settings.resolve_settings(reviewer="codex").judge_reviewer == "claude"


@pytest.mark.parametrize("selector", [None, "claude", "codex"])
def test_registered_selector_applies_to_both_omitted_roles(monkeypatch, selector):
    if selector is not None:
        monkeypatch.setenv("HARMONIC_MACHINIST_REVIEWER", selector)
    expected = settings.resolve_settings(
        reviewer=selector or "claude", judge_reviewer=selector or "claude",
    )
    assert settings.registered_settings() == expected
    assert settings.from_carrier(None) == expected


@pytest.mark.parametrize(("overrides", "expected_roles"), [
    ({"reviewer": "claude"}, ("claude", "codex")),
    ({"judge_reviewer": "claude"}, ("codex", "claude")),
    ({"reviewer": "claude", "judge_reviewer": "claude"}, ("claude", "claude")),
])
def test_explicit_registered_role_overrides_are_independent(
    monkeypatch, overrides, expected_roles,
):
    monkeypatch.setenv("HARMONIC_MACHINIST_REVIEWER", "codex")
    selected = settings.registered_settings(**overrides)
    assert selected == settings.resolve_settings(
        reviewer=expected_roles[0], judge_reviewer=expected_roles[1],
    )


@pytest.mark.parametrize(("field", "value"), [
    ("model", "explicit-review-model"), ("effort", "high"),
    ("judge_model", "explicit-judge-model"), ("judge_effort", "high"),
])
def test_explicit_registered_model_and_effort_override_only_their_field(
    monkeypatch, field, value,
):
    monkeypatch.setenv("HARMONIC_MACHINIST_REVIEWER", "codex")
    expected = settings.resolve_settings(reviewer="codex", judge_reviewer="codex")
    assert settings.registered_settings(**{field: value}) == replace(
        expected, **{field: value},
    )


@pytest.mark.parametrize("selector", ["", "Claude", "codex ", "unknown"])
@pytest.mark.parametrize("overrides", [{}, {"reviewer": "claude"}, {"judge_reviewer": "codex"}])
def test_invalid_selector_rejects_any_omitted_registered_role(
    monkeypatch, selector, overrides,
):
    monkeypatch.setenv("HARMONIC_MACHINIST_REVIEWER", selector)
    with pytest.raises(ValueError, match="HARMONIC_MACHINIST_REVIEWER must be"):
        settings.registered_settings(**overrides)


def test_both_explicit_registered_roles_ignore_invalid_ambient_selector(monkeypatch):
    monkeypatch.setenv("HARMONIC_MACHINIST_REVIEWER", "invalid")
    assert settings.registered_settings(
        reviewer="codex", judge_reviewer="claude",
        model="review-model", judge_effort="high",
    ) == settings.resolve_settings(
        reviewer="codex", judge_reviewer="claude",
        model="review-model", judge_effort="high",
    )


def test_complete_carrier_preserves_exact_selection_despite_registered_environment(monkeypatch):
    selected = settings.resolve_settings(
        reviewer="codex", model="custom-review-model", effort="high",
        judge_reviewer="claude", judge_model="custom-judge-model", judge_effort="low",
    )
    monkeypatch.setenv("HARMONIC_MACHINIST_REVIEWER", "invalid")
    assert settings.from_carrier(selected.canonical()) == selected
    with pytest.raises(ValueError, match="HARMONIC_MACHINIST_REVIEWER"):
        settings.from_carrier(None)
    monkeypatch.setenv("HARMONIC_MACHINIST_REVIEWER", "codex")
    assert settings.from_carrier(None) == settings.registered_settings()
