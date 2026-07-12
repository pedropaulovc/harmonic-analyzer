"""Offline contracts for the platen-guide manufacturing drawing."""

from __future__ import annotations

import subprocess
import sys
import zipfile
from pathlib import Path

import cut_release
import create_drawing_standards
import draw_platen_guide as drawing
import build_platen_guide as guide
from _drawing_registry import DRAWINGS, ASME_B_DRWDOT, ASME_B_SLDDRT
from _drawing_common import _gtol_frame_xml, property_link, sanitize_pdf_metadata
from _holes import CLEARANCE_MM, TAP_DRILL_MM


class _ViewExtension:
    def __init__(self) -> None:
        self.updated: list[tuple[str, int]] = []

    def UpdateStandardViews(self, name: str, view_id: int) -> bool:
        self.updated.append((name, view_id))
        return True


class _ViewModel:
    def __init__(self) -> None:
        self.Extension = _ViewExtension()
        self.shown: list[tuple[str, int]] = []

    def ShowNamedView2(self, name: str, view_id: int) -> None:
        self.shown.append((name, view_id))


class _ViewAdapter:
    def __init__(self) -> None:
        self.currentModel = _ViewModel()
        self.zoomed: list[object] = []

    def _zoom_to_fit(self, model: object) -> None:
        self.zoomed.append(model)


def test_platen_guide_rebases_back_as_standard_front() -> None:
    adapter = _ViewAdapter()
    guide._make_back_view_front(adapter)
    assert adapter.currentModel.shown == [("", 2), ("", 1)]
    assert adapter.currentModel.Extension.updated == [("", 1)]
    assert adapter.zoomed == [adapter.currentModel]
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert '"*Front", 0.190, FRONT_VIEW_Y_M' in source


def test_drawing_hole_sizes_follow_unc_policy() -> None:
    assert drawing.THREAD_DESIGNATION == "#4-40 UNC-2B"
    assert drawing.THREAD_TAP_DRILL_MM == TAP_DRILL_MM["#4-40"]
    assert CLEARANCE_MM[("#4", "normal")] == 3.264


def test_platen_guide_hole_stations_match_native_wizard_features() -> None:
    assert guide.HOLE_X[:2] == (53.0, 67.0)
    assert tuple(x + 180.0 for x in guide.HOLE_X[:2]) == guide.HOLE_X[2:]
    assert guide.SCREW_STATION_X == tuple(30.0 + 60.0 * i for i in range(5))
    source = Path(guide.__file__).read_text(encoding="utf-8")
    assert 'HoleSpec("clearance", "#4")' in source
    assert '"tapped_bottoming", "#4-40"' in source


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


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/platen-guide.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/platen-guide.pdf")
    assert drawing.PNG.as_posix().endswith("/png/platen-guide_drawing.png")


def test_drawing_uses_native_hole_table_and_sheet_scale() -> None:
    import _drawing_common

    drawing_source = Path(drawing.__file__).read_text(encoding="utf-8")
    common_source = Path(_drawing_common.__file__).read_text(encoding="utf-8")
    standards_source = Path(create_drawing_standards.__file__).read_text(
        encoding="utf-8"
    )
    assert "insert_hole_table" in drawing_source
    assert "InsertHoleTable3" in common_source
    assert "draw_note_table" not in drawing_source
    assert "add_hole_group_tags" not in drawing_source
    assert "scale=(3, 1)" not in drawing_source
    assert "scale=(1, 4)" not in drawing_source
    assert '$PRP:"SW-Sheet Scale"' in standards_source
    assert "SCALE 1:1 UNLESS NOTED" not in standards_source


def test_drawing_tolerances_follow_feature_function_not_display_zeros() -> None:
    notes = guide.DRAWING_NOTES
    assert "LENGTH +/-0.5" in notes
    assert "STOCK SECTION +/-0.25" in notes
    assert "HOLE POSITION PER FCF" in notes
    assert "X.XXX" not in notes


def test_native_gdt_replaces_datum_flatness_parallelism_notes() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("add_datum_feature(") == 3
    assert source.count("add_feature_control_frame(") == 3
    assert "characteristic=\"flatness\"" in source
    assert "characteristic=\"parallelism\"" in source
    assert "characteristic=\"position\"" in source
    assert "add_surface_finish(" in source
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source
    assert "def _manufacturing_notes" not in source


def test_gdt_xml_and_note_links_use_native_drawing_contracts() -> None:
    xml = _gtol_frame_xml(
        "position", "0.20", datums=("A", "B", "C"), diameter=True
    )
    assert "GTOL-POSI" in xml
    assert "<PrimaryRangeSymbol>phi</PrimaryRangeSymbol>" in xml
    assert xml.count("<DatumCompartment>") == 3
    assert property_link("Manufacturing Notes") == '$PRPSHEET:"Manufacturing Notes"'


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
