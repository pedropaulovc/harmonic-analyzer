"""Offline contracts for the platen-guide drawing and period 6 BA thread."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

import cut_release
import draw_platen_guide as drawing
import build_fillister_screw as screw
import build_platen as platen
import build_platen_guide as guide
import build_paper_drive_assembly as paper_drive
from _drawing_registry import DRAWINGS, ASME_B_DRWDOT, ASME_B_SLDDRT
from _hole_wizard import BA6


def test_period_6ba_thread_form() -> None:
    assert BA6.designation == "6 BA"
    assert BA6.major_diameter_mm == 2.80
    assert BA6.pitch_mm == 0.53
    assert BA6.angle_deg == 47.5
    assert math.isclose(BA6.radial_depth_mm, 0.318, abs_tol=1e-12)
    assert math.isclose(BA6.core_diameter_mm, 2.164, abs_tol=1e-12)
    assert math.isclose(BA6.crest_root_radius_mm, 0.0958399, abs_tol=1e-12)


def test_mating_hardware_uses_6ba() -> None:
    assert screw.SHANK_DIA == BA6.major_diameter_mm
    assert (screw.HEAD_DIA, screw.HEAD_H) == (4.2, 1.96)
    assert (screw.SLOT_W, screw.SLOT_D) == (0.448, 0.882)
    assert platen.SOCKET_DIA == BA6.core_diameter_mm
    assert platen.SOCKET_THREAD_DEPTH < platen.SOCKET_DEPTH


def test_platen_guide_hole_stations_are_native_linear_patterns() -> None:
    assert guide.HOLE_X[:2] == (53.0, 67.0)
    assert tuple(x + 180.0 for x in guide.HOLE_X[:2]) == guide.HOLE_X[2:]
    assert guide.SCREW_STATION_X == tuple(30.0 + 60.0 * i for i in range(5))
    source = Path(guide.__file__).read_text(encoding="utf-8")
    assert "ThroughTapPattern" in source
    assert "PlatenMountTapPattern" in source
    assert "BlindDrawingLocatorProfile" not in source


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
        - (BA6.core_diameter_mm / 2.0) ** 2
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


def test_paper_drive_tracks_every_intended_thread_contact() -> None:
    contacts = paper_drive.paper_drive_thread_engagement_lengths()
    assert len(contacts) == 22
    assert sorted(contacts.values()) == (
        [screw.SHANK_LEN - paper_drive.LOCK_THICK] * 8
        + [paper_drive.GUIDE_SCREW_THREAD_DEPTH] * 10
        + [screw.SHANK_LEN - paper_drive.CLIP_THICKNESS] * 4
    )


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/platen-guide.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/platen-guide.pdf")
    assert drawing.PNG.as_posix().endswith("/png/platen-guide_drawing.png")


def test_drawing_registry_is_unique_and_extensible() -> None:
    assert len({spec.name for spec in DRAWINGS}) == len(DRAWINGS)
    assert len({spec.part for spec in DRAWINGS}) == len(DRAWINGS)
    outputs = [path for spec in DRAWINGS for path in spec.outputs.values()]
    assert len(set(outputs)) == len(outputs)
    assert ASME_B_DRWDOT.suffix.lower() == ".drwdot"
    assert ASME_B_SLDDRT.suffix.lower() == ".slddrt"


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
    monkeypatch.setattr(cut_release, "DRAWING_OUTPUTS", {"platen_guide": sources})

    stage = tmp_path / "stage"
    stage.mkdir()
    staged = cut_release.stage_drawings(stage)
    assert staged == {
        "platen_guide:slddrw": "slddrw/platen-guide.SLDDRW",
        "platen_guide:pdf": "pdf/platen-guide.pdf",
        "platen_guide:png": "png/platen-guide_drawing.png",
    }
    for relpath in staged.values():
        assert (stage / relpath).is_file()
