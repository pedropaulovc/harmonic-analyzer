"""Offline contracts for the platen-guide manufacturing drawing."""

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
    _gtol_frame_xml,
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
    assert drawing.THREAD_DESIGNATION == "#4-40 UNC-2B"
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
    assert source.count('"tapped_bottoming", "#4-40"') == 3
    assert "lock_spec = HoleSpec(" in source
    assert "screw_spec = HoleSpec(" in source


def test_platen_guide_blind_taps_keep_drill_depth_and_engagement_distinct() -> None:
    assert guide.LOCK_SCREW_HOLE_DEPTH == pytest.approx(
        guide.LOCK_SCREW_THREAD_ENGAGEMENT + guide.LOCK_SCREW_BOTTOM_CLEARANCE
    )
    assert guide.SCREW_HOLE_DEPTH == pytest.approx(
        guide.GUIDE_SCREW_THREAD_ENGAGEMENT
        + guide.GUIDE_SCREW_BOTTOM_CLEARANCE
    )
    assert guide.LOCK_SCREW_BOTTOM_CLEARANCE > 0.0
    assert guide.GUIDE_SCREW_BOTTOM_CLEARANCE > 0.0
    source = Path(guide.__file__).read_text(encoding="utf-8")
    assert source.count('overrides_mm={"ThreadDepth":') == 2


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
    assert 'label="guide bottom edge",\n        position_tolerance_m=0.0001' in source
    assert source.count("position_tolerance_m=0.0001") == 1
    assert source.count("add_feature_control_frame(") == 3
    assert 'characteristic="flatness"' in source
    assert 'characteristic="parallelism"' in source
    assert 'characteristic="position"' in source
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source
    assert "def _manufacturing_notes" not in source


def test_datum_b_surface_symbol_is_clear_of_every_hole_axis() -> None:
    hole_axis_x = {
        drawing.FRONT_LEFT_X_M + station / 1000.0
        for station in (*drawing.THROUGH_X, *drawing.BLIND_X)
    }
    assert drawing.DATUM_B_SYMBOL_X_M == pytest.approx(
        drawing.FRONT_LEFT_X_M + guide.GUIDE_LENGTH * 0.6 / 1000.0
    )
    assert min(
        abs(drawing.DATUM_B_SYMBOL_X_M - x) for x in hole_axis_x
    ) == pytest.approx((guide.GUIDE_LENGTH * 0.1 - guide.LOCK_SCREW_DX) / 1000.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "def _bottom_surface_edge(" in source
    assert 'visible_view_entities(view, 1, label="platen-guide bottom edge")' in source
    assert "if span_mm < GUIDE_LENGTH - 0.1:" in source
    assert "datum_b_entity = _bottom_surface_edge(front)" in source
    assert "entity=datum_b_entity" in source
    assert "symbol_xy=(DATUM_B_SYMBOL_X_M, 0.098)" in source


def test_gdt_xml_and_note_links_use_native_drawing_contracts() -> None:
    xml = _gtol_frame_xml("position", "0.20", datums=("A", "B", "C"), diameter=True)
    assert "GTOL-POSI" in xml
    assert "<PrimaryRangeSymbol>phi</PrimaryRangeSymbol>" in xml
    assert xml.count("<DatumCompartment>") == 3
    assert property_link("Manufacturing Notes") == '$PRPSHEET:"Manufacturing Notes"'
    assert "GTOL-SPROF" in _gtol_frame_xml("profile_surface", "0.10", datums=("C",))


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
    assert (
        stage / "solidworks" / "platen-guide.SLDPRT"
    ).read_bytes() == b"referenced model"
    assert (stage / "slddrw" / "platen-guide.SLDDRW").read_bytes() == b"slddrw"
    assert (
        stage / "slddrw" / "platen-guide.SLDPRT"
    ).read_bytes() == b"referenced model"


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
