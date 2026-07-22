"""Offline contracts for the platen-guide manufacturing drawing."""

from __future__ import annotations

import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

import _drawing_common as common
import cut_release
import draw_platen_guide as drawing
import build_platen_guide as guide
from _drawing_registry import DRAWINGS, PROJECT_DRWDOT
from _drawing_common import (
    _assert_third_angle_order,
    _gtol_frame_xml,
    _projection_symbol_centers,
    property_link,
    sanitize_pdf_metadata,
)
from _holes import CLEARANCE_MM, TAP_DRILL_MM


def test_platen_guide_native_front_is_hole_entry_face() -> None:
    source = Path(guide.__file__).read_text(encoding="utf-8")
    assert "reverse_direction=True" in source
    assert "(0.0, 0.0, 1.0)" in source
    assert "UpdateStandardViews" not in source
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
    assert "insert_hole_table" in drawing_source
    assert "InsertHoleTable3" in common_source
    assert "draw_note_table" not in drawing_source
    assert "add_hole_group_tags" not in drawing_source
    assert "scale=(3, 1)" not in drawing_source
    assert "scale=(1, 4)" not in drawing_source
    # (The sheet-scale property link now lives inside the hand-made
    # harmonic-analyzer.DRWDOT binary -- not greppable; verified by eye on the
    # rendered sheets.)


def test_drawing_tolerances_follow_feature_function_not_display_zeros() -> None:
    notes = guide.DRAWING_NOTES
    assert "HOLE POSITION PER FCF" in notes
    # General tolerances live in the title block ONLY -- a second general
    # tolerance in the notes would conflict with it.
    assert "LENGTH +/-" not in notes
    assert "STOCK SECTION" not in notes
    assert "X.XXX" not in notes


def test_native_gdt_replaces_datum_flatness_parallelism_notes() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("add_datum_feature(") == 3
    assert source.count("add_feature_control_frame(") == 3
    assert "characteristic=\"flatness\"" in source
    assert "characteristic=\"parallelism\"" in source
    assert "characteristic=\"position\"" in source
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
    assert "GTOL-SPROF" in _gtol_frame_xml(
        "profile_surface", "0.10", datums=("C",)
    )


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
    assert PROJECT_DRWDOT.suffix.lower() == ".drwdot"
    assert PROJECT_DRWDOT.is_file() and PROJECT_DRWDOT.stat().st_size > 0


def test_projection_symbol_requires_third_angle_order() -> None:
    circles = [(0.338096872, 0.004069535), (0.338096872, 0.002265426)]
    lines = [
        (0.338096872, 0.338096872),
        (0.332670531, 0.343523212),
        (0.326686701, 0.326686701),
        (0.326686701, 0.318436811),
        (0.318436811, 0.318436811),
        (0.318436811, 0.326686701),
        (0.316931747, 0.328191765),
        (0.326686701, 0.318436811),
    ]
    frustum_x, circle_x = _projection_symbol_centers(circles, lines)
    assert frustum_x == pytest.approx(0.322561756)
    assert circle_x == pytest.approx(0.338096872)
    _assert_third_angle_order(frustum_x, circle_x)

    with pytest.raises(RuntimeError, match="first-angle projection symbol"):
        _assert_third_angle_order(circle_x, frustum_x)


def test_dirty_reopened_scale_is_reexported_to_pdf() -> None:
    source = Path(common.__file__).read_text(encoding="utf-8")
    first_reopen = source.index("await reopen_drawing(adapter, outputs.slddrw)")
    dirty_branch = source.index("if sheet_scale_dirty:", first_reopen)
    persisted_pdf_export = source.index(
        "adapter, str(outputs.slddrw), pdf_path=str(outputs.pdf)",
        dirty_branch,
    )
    second_reopen = source.index(
        "await reopen_drawing(adapter, outputs.slddrw)", first_reopen + 1
    )
    assert dirty_branch < persisted_pdf_export < second_reopen
    assert "PDF re-export after dirty-scale save failed" in source


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

    referenced_model = tmp_path / "source" / "sldprt" / "platen-guide.SLDPRT"
    referenced_model.parent.mkdir(parents=True)
    referenced_model.write_bytes(b"referenced model")

    def fake_pack(_sw, source, doc_type, archive):
        assert source == sources["slddrw"]
        assert doc_type == cut_release.SW_DOC_DRAWING
        with zipfile.ZipFile(archive, "w") as package:
            package.writestr(source.name, source.read_bytes())
            package.writestr("platen-guide.SLDPRT", b"referenced model")
        return (source, referenced_model)

    monkeypatch.setattr(cut_release, "_pack_and_go_document", fake_pack)
    monkeypatch.setattr(cut_release, "RELEASE_DIR", tmp_path / "release")
    cut_release.RELEASE_DIR.mkdir()
    native = cut_release.package_drawings(object(), stage, {})
    assert native == {
        "platen_guide:solidworks_slddrw": "solidworks/platen-guide.SLDDRW",
        "platen_guide:slddrw": "slddrw/platen-guide.SLDDRW",
    }
    assert (stage / "solidworks" / "platen-guide.SLDDRW").read_bytes() == b"slddrw"
    assert (stage / "solidworks" / "platen-guide.SLDPRT").read_bytes() == b"referenced model"
    assert (stage / "slddrw" / "platen-guide.SLDDRW").read_bytes() == b"slddrw"
    assert (stage / "slddrw" / "platen-guide.SLDPRT").read_bytes() == b"referenced model"


def test_release_accepts_pack_rewrite_of_same_original_source(
    tmp_path: Path, monkeypatch
) -> None:
    drawing = tmp_path / "source" / "slddrw" / "pen-assembly.SLDDRW"
    assembly = tmp_path / "source" / "sldasm" / "pen.SLDASM"
    drawing.parent.mkdir(parents=True)
    assembly.parent.mkdir(parents=True)
    drawing.write_bytes(b"drawing")
    assembly.write_bytes(b"source assembly")
    monkeypatch.setattr(
        cut_release,
        "DRAWING_OUTPUTS",
        {"pen_assembly": {"slddrw": drawing}},
    )

    stage = tmp_path / "stage"
    native_dir = stage / "solidworks"
    native_dir.mkdir(parents=True)
    (native_dir / assembly.name).write_bytes(b"top-level Pack-and-Go rewrite")

    def fake_pack(_sw, _source, _doc_type, archive):
        with zipfile.ZipFile(archive, "w") as package:
            package.writestr(drawing.name, b"drawing")
            package.writestr(assembly.name, b"drawing Pack-and-Go rewrite")
        return (drawing, assembly)

    monkeypatch.setattr(cut_release, "_pack_and_go_document", fake_pack)
    monkeypatch.setattr(cut_release, "RELEASE_DIR", tmp_path / "release")
    cut_release.RELEASE_DIR.mkdir()

    staged = cut_release.package_drawings(
        object(), stage, {assembly.name.casefold(): assembly}
    )

    assert staged["pen_assembly:solidworks_slddrw"] == (
        "solidworks/pen-assembly.SLDDRW"
    )
    assert (native_dir / assembly.name).read_bytes() == (
        b"top-level Pack-and-Go rewrite"
    )
    assert (stage / "slddrw" / assembly.name).read_bytes() == (
        b"drawing Pack-and-Go rewrite"
    )


def test_release_rejects_pack_collision_from_distinct_original_sources(
    tmp_path: Path,
) -> None:
    first = tmp_path / "one" / "pen.SLDASM"
    second = tmp_path / "two" / "pen.SLDASM"
    first.parent.mkdir()
    second.parent.mkdir()
    first.write_bytes(b"one")
    second.write_bytes(b"two")
    archive = tmp_path / "pack.zip"
    with zipfile.ZipFile(archive, "w") as package:
        package.writestr(first.name, b"rewrite")
    destination = tmp_path / "destination"
    destination.mkdir()

    with pytest.raises(RuntimeError, match="different sources"):
        cut_release._merge_pack_and_go_zip(
            archive,
            (second,),
            ((destination, {first.name.casefold(): first}),),
        )
