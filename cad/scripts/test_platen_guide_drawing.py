"""Offline contracts for the platen-guide drawing and period 6 BA thread."""

from __future__ import annotations

import math
from pathlib import Path

import cut_release
import export_part_drawing as drawing
from _hole_wizard import BA6


def test_period_6ba_thread_form() -> None:
    assert BA6.designation == "6 BA"
    assert BA6.major_diameter_mm == 2.80
    assert BA6.pitch_mm == 0.53
    assert BA6.angle_deg == 47.5
    assert math.isclose(BA6.radial_depth_mm, 0.318, abs_tol=1e-12)
    assert math.isclose(BA6.tap_diameter_mm, 2.164, abs_tol=1e-12)
    assert math.isclose(BA6.crest_root_radius_mm, 0.0958399, abs_tol=1e-12)


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
