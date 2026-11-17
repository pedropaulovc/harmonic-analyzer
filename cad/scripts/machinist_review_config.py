"""Shared CLI defaults and frozen registered reviewer/judge configuration.

Only the registered gate resolves environment overrides. The standalone CLI uses
the provider defaults directly, independently of the registered configuration.
It also reads the drawing guidelines' frontmatter, whose ``major_version`` is
the rubric's identity in the review key.
"""

from __future__ import annotations

from collections.abc import Mapping
import os
import re
from typing import NamedTuple

import yaml


DEFAULT_MODELS = {
    "claude": "claude-opus-5-5",
    "codex": "gpt-6-astra",
}
DEFAULT_EFFORTS = {
    "claude": "medium",
    "codex": "low",
}
EFFORTS = {
    "claude": ("low", "medium", "high", "xhigh", "max"),
    "codex": ("none", "minimal", "low", "medium", "high", "xhigh", "max"),
}
ENV_PREFIX = "HARMONIC_MACHINIST_"
ENV_FIELDS = {
    "backend": "REVIEWER",
    "model": "MODEL",
    "effort": "EFFORT",
    "judge_backend": "JUDGE_REVIEWER",
    "judge_model": "JUDGE_MODEL",
    "judge_effort": "JUDGE_EFFORT",
}


class ReviewProfile(NamedTuple):
    """One immutable selection for blind reviewers and their independent judge."""

    backend: str
    model: str
    effort: str
    judge_backend: str
    judge_model: str
    judge_effort: str


def _validate_backend(backend: str, field: str) -> None:
    if backend not in ("claude", "codex"):
        raise ValueError(
            f"{ENV_PREFIX}{ENV_FIELDS[field]} must be claude or codex; "
            f"got {backend!r}"
        )


def validate_review_profile(profile: ReviewProfile) -> None:
    """Validate a resolved snapshot without consulting defaults or environment."""
    if not isinstance(profile, ReviewProfile):
        raise ValueError("expected a resolved ReviewProfile")
    for field, suffix in ENV_FIELDS.items():
        value = getattr(profile, field)
        if not isinstance(value, str):
            raise ValueError(f"{ENV_PREFIX}{suffix}={value!r}: expected a string")
    for stage in ("", "judge_"):
        backend = getattr(profile, stage + "backend")
        _validate_backend(backend, stage + "backend")
        model = getattr(profile, stage + "model")
        model_env = ENV_PREFIX + ENV_FIELDS[stage + "model"]
        if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]*", model) is None:
            raise ValueError(f"{model_env}={model!r}: expected a non-empty model ID")
        effort = getattr(profile, stage + "effort")
        effort_env = ENV_PREFIX + ENV_FIELDS[stage + "effort"]
        if effort not in EFFORTS[backend]:
            raise ValueError(
                f"{effort_env}={effort!r}: {backend} effort must be one of "
                f"{EFFORTS[backend]}"
            )


def registered_review_profile(
    environ: Mapping[str, str] | None = None,
) -> ReviewProfile:
    """Resolve once; the reviewer backend also selects the judge unless overridden."""
    environ = os.environ if environ is None else environ
    backend = environ.get(ENV_PREFIX + ENV_FIELDS["backend"], "claude")
    judge_backend = environ.get(
        ENV_PREFIX + ENV_FIELDS["judge_backend"], backend
    )
    resolved: dict[str, str] = {}
    for stage, selected_backend in (("", backend), ("judge_", judge_backend)):
        _validate_backend(selected_backend, stage + "backend")
        resolved.update({
            stage + "backend": selected_backend,
            stage + "model": environ.get(
                ENV_PREFIX + ENV_FIELDS[stage + "model"],
                DEFAULT_MODELS[selected_backend],
            ),
            stage + "effort": environ.get(
                ENV_PREFIX + ENV_FIELDS[stage + "effort"],
                DEFAULT_EFFORTS[selected_backend],
            ),
        })
    profile = ReviewProfile(**resolved)
    validate_review_profile(profile)
    return profile


def split_versioned_guidelines(
    text: str, *, label: str = "drawing guidelines"
) -> tuple[int, str]:
    """``(major_version, body)`` of a versioned guidelines Markdown file.

    The YAML frontmatter's integer ``major_version`` alone keys cached
    machinist reviews; the reviewers and judge receive the body, without the
    frontmatter. A missing frontmatter or a missing, non-integer or
    non-positive version raises: a rubric with no identity must neither reuse
    nor publish a verdict."""
    text = text.replace("\r\n", "\n")
    end = text.find("\n---\n", 3) if text.startswith("---\n") else -1
    if end < 0:
        raise ValueError(
            f"{label} must open with YAML frontmatter between --- lines"
        )
    try:
        meta = yaml.safe_load(text[4:end])
    except yaml.YAMLError as error:
        raise ValueError(f"{label} frontmatter is not YAML: {error}") from error
    version = meta.get("major_version") if isinstance(meta, dict) else None
    if type(version) is not int or version < 1:
        raise ValueError(
            f"{label} frontmatter needs an integer major_version >= 1; "
            f"got {version!r}"
        )
    return version, text[end + 5:].lstrip("\n")


def split_drawing_guidelines(text: str) -> tuple[int, str]:
    """``(major_version, body)`` of ``cad/docs/drawing-guidelines.md``."""
    return split_versioned_guidelines(text, label="drawing guidelines")


def split_traveler_guidelines(text: str) -> tuple[int, str]:
    """``(major_version, body)`` of ``cad/docs/traveler-guidelines.md``."""
    return split_versioned_guidelines(text, label="traveler guidelines")
