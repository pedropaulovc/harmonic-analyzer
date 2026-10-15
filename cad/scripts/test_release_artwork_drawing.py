"""Artwork a drawing note names ships in the release bundle at the printed path.

Exercises ``cut_release``'s real note scan and staging against a temporary
stage: no network, no SolidWorks. Named ``test_*_drawing.py`` so the drawing
glob in ``dodo.task_check`` enrols it in ``check:recipe``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import cut_release
import fr_nameplate_drawing_spec as nameplate_spec
from _drawing_registry import DRAWINGS
from _release_artwork import ARTWORK_DIR, NOTED_ARTWORK, bundle_path


def test_artwork_ships_beside_the_drawing_pdfs() -> None:
    for drawing in DRAWINGS:
        assert drawing.outputs["pdf"].parent.name == ARTWORK_DIR


def test_every_noted_artwork_file_lands_at_its_printed_path(tmp_path: Path) -> None:
    texts = cut_release.drawing_note_texts()
    # The scan reaches a property-linked note: the build stamps it, the sheet
    # links it, and only the spec module holds it.
    assert nameplate_spec.MANUFACTURING_NOTES in texts
    noted = {m.group(0) for text in texts for m in NOTED_ARTWORK.finditer(text)}
    nameplate = {
        m.group(0) for m in NOTED_ARTWORK.finditer(nameplate_spec.MANUFACTURING_NOTES)
    }
    assert len(nameplate) == 3 and nameplate <= noted

    staged = cut_release.stage_noted_artwork(tmp_path, texts)

    assert set(staged) == noted
    for path, source in staged.items():
        target = tmp_path / path
        assert target.relative_to(tmp_path).as_posix() == path
        assert target.name == Path(source).name  # the note spells the file exactly
        assert target.read_bytes() == (cut_release.REPO_ROOT / source).read_bytes()


def test_a_missing_or_ambiguous_noted_file_fails_the_cut(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with pytest.raises(RuntimeError, match="matches 0 tracked"):
        cut_release.stage_noted_artwork(
            tmp_path, ["OUTLINE PER pdf/fr-nameplate-missing.dxf"]
        )
    with pytest.raises(RuntimeError, match="ships under pdf/"):
        cut_release.stage_noted_artwork(
            tmp_path, ["OUTLINE PER PDF/fr-nameplate-outline.dxf"]
        )
    with pytest.raises(RuntimeError, match="two ways"):
        cut_release.noted_artwork(
            ["PER pdf/fr-nameplate-outline.dxf", "PER pdf/FR-NAMEPLATE-OUTLINE.DXF"]
        )
    assert not any(tmp_path.iterdir())

    monkeypatch.setattr(
        cut_release,
        "_git",
        lambda *_args, **_kwargs: "cad/references/a.dxf\ncad/other/A.DXF",
    )
    with pytest.raises(RuntimeError, match="matches 2 tracked"):
        cut_release.stage_noted_artwork(tmp_path, ["PER pdf/a.dxf"])


def test_a_noted_file_resolves_without_regard_to_case(tmp_path: Path) -> None:
    staged = cut_release.stage_noted_artwork(
        tmp_path, ["OUTLINE PER pdf/FR-NAMEPLATE-OUTLINE.DXF"]
    )
    assert staged == {
        "pdf/FR-NAMEPLATE-OUTLINE.DXF": "cad/references/fr-nameplate-outline.dxf"
    }
    assert (tmp_path / "pdf" / "FR-NAMEPLATE-OUTLINE.DXF").is_file()


def test_bundle_path_refuses_what_the_scan_would_not_find() -> None:
    assert bundle_path("fr-nameplate-outline.dxf") == "pdf/fr-nameplate-outline.dxf"
    for name in ("outline.dwg", "two words.dxf", "sub/outline.dxf"):
        with pytest.raises(ValueError):
            bundle_path(name)
