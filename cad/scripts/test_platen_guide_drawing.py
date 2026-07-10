"""Offline contracts for the platen-guide drawing and period 6 BA thread."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

import cut_release
import export_part_drawing as drawing
import build_fillister_screw as screw
import build_platen as platen
import build_paper_drive_assembly as paper_drive
from _hole_wizard import BA6


def test_period_6ba_thread_form() -> None:
    assert BA6.designation == "6 BA"
    assert BA6.major_diameter_mm == 2.80
    assert BA6.pitch_mm == 0.53
    assert BA6.angle_deg == 47.5
    assert math.isclose(BA6.radial_depth_mm, 0.318, abs_tol=1e-12)
    assert math.isclose(BA6.core_diameter_mm, 2.164, abs_tol=1e-12)
    assert BA6.tap_drill_diameter_mm == 2.30
    assert math.isclose(BA6.crest_root_radius_mm, 0.0958399, abs_tol=1e-12)


def test_mating_hardware_uses_6ba() -> None:
    assert screw.SHANK_DIA == BA6.major_diameter_mm
    assert (screw.HEAD_DIA, screw.HEAD_H) == (4.2, 1.96)
    assert (screw.SLOT_W, screw.SLOT_D) == (0.448, 0.882)
    assert platen.SOCKET_DIA == BA6.tap_drill_diameter_mm
    assert platen.SOCKET_THREAD_DEPTH < platen.SOCKET_DEPTH


def test_threaded_interference_allowance_is_exact_by_engagement_length() -> None:
    engagement_lengths = {
        frozenset(("platen-1", "fillister-screw-1")): (
            screw.SHANK_LEN - paper_drive.CLIP_THICKNESS
        ),
        frozenset(("platen-guide-1", "fillister-screw-5")): (
            paper_drive.GUIDE_SCREW_THREAD_DEPTH
        ),
        frozenset(("platen-guide-1", "fillister-screw-15")): (
            screw.SHANK_LEN - paper_drive.LOCK_THICK
        ),
    }
    annular_area = math.pi * (
        (screw.SHANK_DIA / 2.0) ** 2
        - (BA6.tap_drill_diameter_mm / 2.0) ** 2
    )
    contacts = {
        pair: annular_area * engagement
        for pair, engagement in engagement_lengths.items()
    }
    paper_drive._validate_thread_contacts(contacts, engagement_lengths)
    with pytest.raises(RuntimeError):
        paper_drive._validate_thread_contacts(
            {
                **contacts,
                frozenset(("platen-guide-1", "platen-rack-1")): 0.10,
            },
            engagement_lengths,
        )
    wrong_volume = dict(contacts)
    first_pair = next(iter(wrong_volume))
    wrong_volume[first_pair] *= 1.03
    with pytest.raises(RuntimeError):
        paper_drive._validate_thread_contacts(wrong_volume, engagement_lengths)


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/platen-guide.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/platen-guide.pdf")
    assert drawing.PNG.as_posix().endswith("/png/platen-guide_drawing.png")


def test_release_stages_all_drawing_formats(tmp_path: Path, monkeypatch) -> None:
    sources: dict[str, Path] = {}
    for kind, name in (
        ("slddrw", "platen-guide.SLDDRW"),
        ("pdf", "platen-guide.pdf"),
        ("png", "platen-guide_drawing.png"),
    ):
        source = tmp_path / "source" / kind / name
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(kind.encode())
        sources[kind] = source
    monkeypatch.setattr(cut_release, "DRAWING_OUTPUTS", sources)

    stage = tmp_path / "stage"
    stage.mkdir()
    staged = cut_release.stage_drawings(stage)
    assert staged == {
        "slddrw": "slddrw/platen-guide.SLDDRW",
        "pdf": "pdf/platen-guide.pdf",
        "png": "png/platen-guide_drawing.png",
    }
    for relpath in staged.values():
        assert (stage / relpath).is_file()
