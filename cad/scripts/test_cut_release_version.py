"""Offline regression tests for compact release numbering and Pillow APIs."""

from __future__ import annotations

from pathlib import Path

import pytest

import cut_release


def _tags(monkeypatch: pytest.MonkeyPatch, *tags: str) -> None:
    monkeypatch.setattr(cut_release, "_git", lambda *_args, **_kwargs: "\n".join(tags))


def test_existing_tags_ignores_legacy_semver(monkeypatch: pytest.MonkeyPatch) -> None:
    _tags(monkeypatch, "v0.20.0", "v9", "v21", "v01", "not-a-release")

    assert cut_release._existing_tags() == [9, 21]


def test_default_version_increments_latest_compact_tag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _tags(monkeypatch, "v0.20.0", "v9", "v21")

    assert cut_release.resolve_version(None) == "v22"


def test_default_version_starts_at_v1_without_compact_tags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _tags(monkeypatch, "v0.20.0", "v1.2.3")

    assert cut_release.resolve_version(None) == "v1"


def test_release_requires_configured_cad_revision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cut_release._config, "release_revision", lambda: "v22")

    cut_release.require_configured_revision("v22")
    with pytest.raises(SystemExit, match="does not match configured CAD Revision"):
        cut_release.require_configured_revision("v23")


def test_published_release_advances_tracked_revision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "release.yaml"
    source.write_text("next_revision: v22\n", encoding="utf-8")
    monkeypatch.setattr(cut_release, "RELEASE_VERSION_FILE", source)
    monkeypatch.setattr(cut_release._config, "release_revision", lambda: "v22")

    assert cut_release.advance_configured_revision("v22") == "v23"
    assert source.read_text(encoding="utf-8") == "next_revision: v23\n"


def test_explicit_compact_version_is_accepted() -> None:
    assert cut_release.resolve_version("v42") == "v42"


@pytest.mark.parametrize("version", ["v0", "v01", "v1.0.0", "22", "v-1"])
def test_invalid_explicit_versions_are_rejected(version: str) -> None:
    with pytest.raises(SystemExit, match="version must look like vNN"):
        cut_release.resolve_version(version)


def test_previous_tag_uses_compact_release_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _tags(monkeypatch, "v0.20.0", "v9", "v21", "v25")

    assert cut_release.previous_tag("v22") == "v21"
    assert cut_release.previous_tag("v9") is None


def test_release_image_tools_do_not_use_deprecated_getdata() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    sources = (
        repo_root / "cad" / "comparisons" / "tools" / "composite.py",
        repo_root / "cad" / "comparisons" / "tools" / "parity_check.py",
    )

    for source in sources:
        assert ".getdata(" not in source.read_text(encoding="utf-8"), source
