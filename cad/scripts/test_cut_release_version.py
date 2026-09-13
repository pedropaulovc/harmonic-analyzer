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


def test_revision_advance_is_staged_before_publish(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "release.yaml"
    source.write_text("next_revision: v22\n", encoding="utf-8")
    monkeypatch.setattr(cut_release, "RELEASE_VERSION_FILE", source)
    monkeypatch.setattr(cut_release._config, "release_revision", lambda: "v22")

    prepared = cut_release.prepare_configured_revision_advance("v22")
    try:
        assert prepared.next_version == "v23"
        assert prepared.temporary is not None
        assert prepared.temporary.exists()
        assert source.read_text(encoding="utf-8") == "next_revision: v22\n"
        assert prepared.commit() == "v23"
    finally:
        prepared.discard()

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


def test_staged_readout_procedure_references_resolve_inside_the_bundle(tmp_path):
    """READOUT.md sends the reader to the operating explanation; a release
    consumer has only the bundle, so that page -- and the pages IT cross-links
    with ./ -- must be staged beside it, every ./ link among them must resolve
    within the stage, and every link that points OUT of the bundle must be
    rewritten to something the reader can follow: a blob URL at the release
    tag for a tracked repo file, plain text naming the path for the
    non-redistributable references submodule. A relative link surviving into
    the zip would be dead on arrival."""
    import re

    staged = cut_release.stage_readout_procedure(tmp_path, "v42")
    assert staged[0] == "READOUT.md"
    for rel in staged:
        assert (tmp_path / rel).is_file(), rel
    readout = (tmp_path / "READOUT.md").read_text(encoding="utf-8")
    assert "`docs/device-operation.md`" in readout
    assert "`cad/docs/device-operation.md`" not in readout.split("beside this file")[0]
    docs = cut_release.operating_docs()
    assert docs[0] == cut_release.OPERATING_DOC and "tolerance-policy.md" in docs
    relative = re.compile(r"\]\(((?!https?:|mailto:|#)[^)]+)\)")
    tagged = 0
    for name in docs:
        page = (tmp_path / "docs" / name).read_text(encoding="utf-8")
        for target in relative.findall(page):
            assert target.startswith("./"), f"{name} -> {target} escapes the bundle"
            assert (tmp_path / "docs" / target.split("#")[0]).is_file(), (
                f"{name} -> {target}"
            )
        tagged += page.count("/blob/v42/cad/")
    assert tagged >= 5  # the policy's config/script citations
    # the submodule scans are cited by repo path, never embedded or linked
    paper = (tmp_path / "docs" / "michelson-1898-trial-accuracy.md").read_text(
        encoding="utf-8"
    )
    assert "28_Michelsons_1898_Paper.pdf` (pinned references submodule)" in paper
    assert "/blob/v42/references/" not in paper


def test_staged_bundle_declares_its_sources_and_permitted_use(tmp_path):
    """The staged pages quote the 2014 book (short attributed excerpts) and
    cite the reference scans, so the bundle must carry that boundary itself:
    a downloader who never sees kickstarter/campaign/risks.md must still be
    told the 2014 book is non-commercial-use only, that no photograph or
    drawing from it is reproduced, and where the CC BY credits are."""
    staged = cut_release.stage_readout_procedure(tmp_path, "v42")
    assert "NOTICE.md" in staged
    notice = (tmp_path / "NOTICE.md").read_text(encoding="utf-8")
    assert "non-commercial purposes" in notice
    assert "Hammack" in notice and "2014" in notice
    assert "public domain" in notice  # the 1898 machine and paper
    assert "ATTRIBUTION.md" in notice  # the CC BY gallery imagery
    assert "NOT included in this bundle" in notice  # the reference scans


def test_staged_docs_reject_a_link_the_bundle_cannot_serve():
    """The rewrite is a GATE, not a best effort: a ./ link to an unstaged page,
    or a repo path that is not tracked at the tag, must fail the release."""
    with pytest.raises(RuntimeError, match="not staged"):
        cut_release.portable_links("[x](./gone.md)", "d.md", "v42", {"d.md"})
    with pytest.raises(RuntimeError, match="not tracked"):
        cut_release.portable_links(
            "[x](../config/no-such.yaml)", "d.md", "v42", {"d.md"}
        )
