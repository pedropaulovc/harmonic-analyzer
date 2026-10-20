"""Pure selection and identity for blind machinist reviews and their judge."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import unicodedata

DEFAULT_MODELS = {"claude": "claude-opus-5-5", "codex": "gpt-6-astra"}
DEFAULT_EFFORTS = {"claude": "medium", "codex": "low"}
REVIEWERS = tuple(DEFAULT_MODELS)
BUILD_RUNS = 3
SETTINGS_ENV = "HARMONIC_MACHINIST_REVIEW_SETTINGS"
SETTING_FIELDS = (
    "reviewer",
    "model",
    "effort",
    "judge_reviewer",
    "judge_model",
    "judge_effort",
)


def _token(value: str, field: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value.startswith("-")
        or any(
            char.isspace() or unicodedata.category(char).startswith("C")
            for char in value
        )
    ):
        raise ValueError(
            f"{field.replace('_', '-')}: expected a nonempty model/provider/effort token"
        )
    return value


def _role(
    reviewer: str | None, model: str | None, effort: str | None, *, prefix: str = ""
) -> tuple[str, str, str]:
    reviewer = "claude" if reviewer is None else _token(reviewer, prefix + "reviewer")
    if reviewer not in REVIEWERS:
        raise ValueError(
            f"{prefix}reviewer: choose one of {REVIEWERS}, got {reviewer!r}"
        )
    model = (
        DEFAULT_MODELS[reviewer] if model is None else _token(model, prefix + "model")
    )
    effort = (
        DEFAULT_EFFORTS[reviewer]
        if effort is None
        else _token(effort, prefix + "effort")
    )
    return reviewer, model, effort


@dataclass(frozen=True)
class ReviewSettings:
    """Fully resolved, exact provider requests for the two independent roles."""

    reviewer: str
    model: str
    effort: str
    judge_reviewer: str
    judge_model: str
    judge_effort: str

    def canonical(self) -> str:
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))

    def identity(self) -> str:
        payload = {**asdict(self), "runs": BUILD_RUNS}
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

    def cli_args(self) -> list[str]:
        return [
            argument
            for field in SETTING_FIELDS
            for argument in ("--" + field.replace("_", "-"), getattr(self, field))
        ]


def resolve_settings(
    *,
    reviewer: str | None = None,
    model: str | None = None,
    effort: str | None = None,
    judge_reviewer: str | None = None,
    judge_model: str | None = None,
    judge_effort: str | None = None,
) -> ReviewSettings:
    """Resolve omissions only; never trim, coerce, alias, or silently fall back."""
    blind = _role(reviewer, model, effort)
    judge = _role(judge_reviewer, judge_model, judge_effort, prefix="judge-")
    return ReviewSettings(*blind, *judge)


def from_carrier(carrier: str | None) -> ReviewSettings:
    """Read a complete internal carrier, or repo defaults when it is absent."""
    if carrier is None:
        return resolve_settings()
    try:
        values = json.loads(carrier)
        if (
            not isinstance(values, dict)
            or set(values) != set(SETTING_FIELDS)
            or any(not isinstance(value, str) for value in values.values())
        ):
            raise ValueError("expected exactly six string settings")
        return resolve_settings(**values)
    except (ValueError, TypeError) as error:
        raise ValueError(f"{SETTINGS_ENV}: {error}") from error
