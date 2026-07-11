"""Offline contracts for the platen-guide drawing and period 6 BA thread."""

from __future__ import annotations

import math
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

import cut_release
import draw_platen_guide as drawing
import build_fillister_screw as screw
import build_platen as platen
import build_platen_guide as guide
import build_paper_drive_assembly as paper_drive
from _drawing_registry import DRAWINGS, ASME_B_DRWDOT, ASME_B_SLDDRT
from _drawing_common import sanitize_pdf_metadata
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
    assert platen.CBORE_DIA == screw.HEAD_DIA + 1.0
    assert platen.CBORE_DEPTH == screw.HEAD_H + 0.2
    assert paper_drive.GUIDE_SCREW_THREAD_DEPTH == screw.SHANK_LEN - (
        platen.PLATE_THICKNESS - platen.CBORE_DEPTH
    )


def test_platen_guide_hole_stations_are_native_linear_patterns() -> None:
    assert guide.HOLE_X[:2] == (53.0, 67.0)
    assert tuple(x + 180.0 for x in guide.HOLE_X[:2]) == guide.HOLE_X[2:]
    assert guide.SCREW_STATION_X == tuple(30.0 + 60.0 * i for i in range(5))
    source = Path(guide.__file__).read_text(encoding="utf-8")
    assert "ThroughTapPattern" in source
    assert "PlatenMountTapPattern" in source
    assert "BlindDrawingLocatorProfile" not in source
    assert "for x in through_seed_x" in source
    assert "points_xy=((SCREW_STATION_X[0], GUIDE_HEIGHT / 2.0),)" in source


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
        pair: [annular_area * engagement]
        for pair, engagement in engagement_lengths.items()
    }
    paper_drive._validate_thread_contacts(contacts, engagement_lengths)
    with pytest.raises(RuntimeError):
        paper_drive._validate_thread_contacts(
            {
                **contacts,
                frozenset(("platen-guide-1", "platen-rack-1")): [0.10],
            },
            engagement_lengths,
        )
    wrong_volume = dict(contacts)
    first_pair = next(iter(wrong_volume))
    wrong_volume[first_pair] = [wrong_volume[first_pair][0] * 1.03]
    with pytest.raises(RuntimeError):
        paper_drive._validate_thread_contacts(wrong_volume, engagement_lengths)

    duplicate = dict(contacts)
    duplicate[first_pair] = [contacts[first_pair][0], contacts[first_pair][0]]
    with pytest.raises(RuntimeError, match="2 interference bodies"):
        paper_drive._validate_thread_contacts(duplicate, engagement_lengths)


def test_drawing_contract_imports_without_pywin32() -> None:
    script = """
import builtins
real_import = builtins.__import__
def blocked(name, *args, **kwargs):
    if name in {'pythoncom', 'pywintypes'} or name.startswith('win32com'):
        raise ImportError(f'blocked {name}')
    return real_import(name, *args, **kwargs)
builtins.__import__ = blocked
import test_platen_guide_drawing
"""
    subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).parent,
        check=True,
        capture_output=True,
        text=True,
    )


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


def test_pdf_metadata_is_project_owned(tmp_path: Path) -> None:
    from pypdf import PdfReader, PdfWriter

    pdf = tmp_path / "drawing.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=1224, height=792)
    writer.add_metadata({"/Author": "seat-user"})
    writer.write(pdf)
    sanitize_pdf_metadata(pdf, title="Drawing")
    metadata = PdfReader(pdf).metadata
    assert metadata.author == "Harmonic Analyzer Project"
    assert metadata.title == "Drawing"


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
        "platen_guide:pdf": "pdf/platen-guide.pdf",
        "platen_guide:png": "png/platen-guide_drawing.png",
    }
    for relpath in staged.values():
        assert (stage / relpath).is_file()

    def fake_pack(_sw, source, doc_type, archive):
        assert source == sources["slddrw"]
        assert doc_type == cut_release.SW_DOC_DRAWING
        with zipfile.ZipFile(archive, "w") as package:
            package.writestr(source.name, source.read_bytes())
            package.writestr("platen-guide.SLDPRT", b"referenced model")
        return 2

    monkeypatch.setattr(cut_release, "_pack_and_go_document", fake_pack)
    monkeypatch.setattr(cut_release, "RELEASE_DIR", tmp_path / "release")
    cut_release.RELEASE_DIR.mkdir()
    native = cut_release.package_drawings(object(), stage)
    assert native == {
        "platen_guide:solidworks_slddrw": "solidworks/platen-guide.SLDDRW",
        "platen_guide:slddrw": "slddrw/platen-guide.SLDDRW",
    }
    assert (stage / "solidworks" / "platen-guide.SLDDRW").read_bytes() == b"slddrw"
    assert (stage / "solidworks" / "platen-guide.SLDPRT").read_bytes() == b"referenced model"
    assert (stage / "slddrw" / "platen-guide.SLDDRW").read_bytes() == b"slddrw"
    assert (stage / "slddrw" / "platen-guide.SLDPRT").read_bytes() == b"referenced model"
