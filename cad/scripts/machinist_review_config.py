"""Backend defaults shared by the standalone CLI and registered review gate."""

from __future__ import annotations

from typing import NamedTuple


DEFAULT_MODELS = {
    "claude": "claude-opus-5-5",
    "codex": "gpt-6-astra",
}
DEFAULT_EFFORTS = {
    "claude": "medium",
    "codex": "low",
}


class ReviewProfile(NamedTuple):
    """One immutable selection, used for both blind reviewers and their judge."""

    backend: str
    model: str
    effort: str


def registered_review_profile(backend: str) -> ReviewProfile:
    """Resolve the registered gate's selector without changing CLI defaults."""
    if backend not in DEFAULT_MODELS:
        raise ValueError(
            "HARMONIC_MACHINIST_REVIEWER must be claude or codex; "
            f"got {backend!r}"
        )
    return ReviewProfile(backend, DEFAULT_MODELS[backend], DEFAULT_EFFORTS[backend])
