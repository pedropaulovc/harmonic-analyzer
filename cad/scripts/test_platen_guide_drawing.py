"""Offline contracts for the platen-guide manufacturing drawing.

The print follows cad/docs/drawing-simplicity-policy.md: a drilled and
tapped guide bar carries no datums, frames, roughness symbols or basic
dimensions; the native hole table gives every station under the title-block
tolerance.  The shared-infrastructure contracts (contact preview, PDF
metadata, release staging) also live here.
"""

from __future__ import annotations

import subprocess
import sys
import zipfile
from pathlib import Path

import pytest
from PIL import Image

import cut_release
import draw_platen_guide as drawing
import build_platen_guide as guide
import _drawing_common as drawing_common
from _drawing_registry import DRAWINGS, PROJECT_DRWDOT
from _drawing_common import (
    _contact_preview_grid,
    property_link,
    render_pdf_png,
    sanitize_pdf_metadata,
)
from _holes import CLEARANCE_MM, TAP_DRILL_MM


def test_platen_guide_native_front_is_hole_entry_face() -> None:
    source = Path(guide.__file__).read_text(encoding="utf-8")
    assert "reverse_direction=True" in source
    assert "(0.0, 0.0, 1.0)" in source
    assert "UpdateStandardViews" not in source
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert '"*Front", FRONT_VIEW_X_M, FRONT_VIEW_Y_M' in source


def test_contact_preview_grid_preserves_legacy_layout_and_scales() -> None:
    assert [_contact_preview_grid(pages) for pages in (2, 3, 4)] == [
        (2, 2),
        (2, 2),
        (2, 2),
    ]
    assert [_contact_preview_grid(pages) for pages in (5, 6)] == [(3, 2), (3, 2)]
    assert [_contact_preview_grid(pages) for pages in (7, 8, 9)] == [
        (3, 3),
        (3, 3),
        (3, 3),
    ]
    assert _contact_preview_grid(10) == (4, 3)
    with pytest.raises(ValueError, match="at least 2 pages"):
        _contact_preview_grid(1)


def test_five_page_contact_preview_preserves_aspect_and_unused_cell(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pdf = tmp_path / "five-pages.pdf"
    png = tmp_path / "contact.png"
    colors = [
        (220, 20, 20),
        (20, 180, 20),
        (20, 20, 220),
        (220, 180, 20),
        (180, 20, 180),
    ]
    Image.init()
    pages = [Image.new("RGB", (1224, 792), color) for color in colors]
    pages[0].save(
        pdf,
        save_all=True,
        append_images=pages[1:],
        resolution=72,
    )
    monkeypatch.setattr(drawing_common, "ASME_B_DPI", 30)
    monkeypatch.setattr(drawing_common, "ASME_B_PNG_SIZE", (510, 330))

    render_pdf_png(pdf, png, expected_pages=5)

    with Image.open(png) as preview:
        assert preview.size == (510, 330)
        assert preview.info["dpi"] == pytest.approx((30, 30), abs=0.1)
        centers = ((85, 82), (255, 82), (425, 82), (85, 247), (255, 247))
        for center, color in zip(centers, colors, strict=True):
            assert preview.getpixel(center) == pytest.approx(color, abs=2)
        assert preview.getpixel((425, 247)) == (255, 255, 255)
        assert preview.getpixel((85, 10)) == (255, 255, 255)


def test_drawing_hole_sizes_follow_unc_policy() -> None:
    assert drawing.THREAD_DESIGNATION == "#4-40 UNC"
    assert drawing.THREAD_TAP_DRILL_MM == TAP_DRILL_MM["#4-40"]
    assert CLEARANCE_MM[("#4", "normal")] == 3.264


def test_platen_guide_hole_stations_match_native_wizard_features() -> None:
    assert guide.LOCK_STATION_X == pytest.approx(
        (guide.GUIDE_LENGTH * 0.3, guide.GUIDE_LENGTH * 0.7)
    )
    assert guide.HOLE_X == pytest.approx(
        tuple(
            station + offset
            for station in guide.LOCK_STATION_X
            for offset in (-guide.LOCK_SCREW_DX, guide.LOCK_SCREW_DX)
        )
    )
    assert guide.SCREW_STATION_X == pytest.approx(
        tuple(guide.GUIDE_LENGTH * fraction for fraction in (0.1, 0.3, 0.5, 0.7, 0.9))
    )
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


def test_notes_are_few_specific_and_never_the_title_block() -> None:
    notes = guide.DRAWING_NOTES
    lines = notes.split("\n")
    assert len(lines) <= 4
    assert "STOCK" in notes  # the cleanup-cut licence (Lipton)
    # Stations and sizes ride the hole table; nothing the title block or a
    # dimension already says.
    for banned in ("PER FCF", "DATUM", "LENGTH +/-", "+/-", "UOS", "X.XXX"):
        assert banned not in notes, banned
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source
    assert "def _manufacturing_notes" not in source


def test_hole_table_states_the_process_once_under_the_table() -> None:
    # The native SIZE cells are SolidWorks-generated from the Hole Wizard
    # callout format ("Ø2.26 ↧ 4.00", "Ø3.26 THRU ALL") and insert_hole_table
    # carries no process prefix, so ONE note directly under the table says
    # drill for every row (machinist review 2026-09-02; policy rule 7).  It is
    # a flag on the table, not a line in the general notes.
    assert drawing.HOLE_TABLE_NOTE == "ALL HOLES DRILLED."
    assert "DRILL" not in guide.DRAWING_NOTES
    assert drawing.HOLE_TABLE_NOTE_Y_M < drawing.HOLE_TABLE_Y_M
    # Below the table's ten rows (bottom ~0.169) and above the front view's
    # overall-length dimension lane (0.135).
    assert 0.135 < drawing.HOLE_TABLE_NOTE_Y_M < 0.169
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert (
        "add_note(adapter, HOLE_TABLE_NOTE, HOLE_TABLE_X_M, HOLE_TABLE_NOTE_Y_M)"
        in source
    )
    assert source.count("add_note(") == 1
    assert 'raise RuntimeError("failed to add the hole-table process note")' in source


def test_print_carries_no_gdt_finish_or_basic_dimensions() -> None:
    # drawing-simplicity-policy.md rule 3-5: a guide bar is not on the GD&T
    # allowlist; the hole table's LOC columns are ordinary, not basic.
    import platen_guide_spec

    source = Path(drawing.__file__).read_text(encoding="utf-8")
    for helper in (
        "add_datum_feature(",
        "add_feature_control_frame(",
        "add_surface_finish(",
        "set_basic_dimension(",
        "project_part_pmi(",
    ):
        assert helper not in source, helper
    assert "basic_locations=False" in source
    assert "_bottom_surface_edge(" not in source
    assert "DATUM_B_SYMBOL_X_M" not in source
    assert not hasattr(platen_guide_spec, "GEOMETRIC_TOLERANCES_MM")


def test_hidden_lines_stay_on_in_every_orthographic_view() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "for view in (front, right):\n        set_hidden_lines_visible" in source
    assert "set_hidden_lines_removed(adapter, iso)" in source
    assert source.count("set_hidden_lines_removed(") == 1


def test_gdt_xml_and_note_links_use_native_drawing_contracts() -> None:
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


def test_pdf_metadata_preserves_multisheet_packages(tmp_path: Path) -> None:
    from pypdf import PdfReader, PdfWriter

    pdf = tmp_path / "drawing.pdf"
    writer = PdfWriter()
    for _sheet in range(4):
        writer.add_blank_page(width=1224, height=792)
    writer.write(pdf)
    sanitize_pdf_metadata(pdf, title="Four-Sheet Drawing", expected_pages=4)
    reader = PdfReader(pdf)
    assert len(reader.pages) == 4
    assert reader.metadata.title == "Four-Sheet Drawing"


def test_drawing_registry_is_unique_and_extensible() -> None:
    assert len({spec.name for spec in DRAWINGS}) == len(DRAWINGS)
    assert len({spec.part for spec in DRAWINGS}) == len(DRAWINGS)
    outputs = [path for spec in DRAWINGS for path in spec.outputs.values()]
    assert len(set(outputs)) == len(outputs)
    assert PROJECT_DRWDOT.suffix.lower() == ".drwdot"
    assert PROJECT_DRWDOT.is_file() and PROJECT_DRWDOT.stat().st_size > 0


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
