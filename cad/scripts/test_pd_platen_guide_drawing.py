"""Offline contracts for the platen-guide manufacturing drawing."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import subprocess
import sys
import zipfile

from PIL import Image
import pytest

from _drawing_common import _contact_preview_grid, render_pdf_png, sanitize_pdf_metadata
from _drawing_notes import property_link
import _drawing_types
import _config
from _drawing_registry import DRAWINGS
from _drawing_types import DRAWING_TEMPLATES, DrawingLayout
from _gtol_frame import gtol_frame_xml as _gtol_frame_xml
from _hole_spec import CLEARANCE_MM, THREAD_MAJOR_MM, blind_cut_dia_mm
import build_pd_platen_guide as guide
import cut_release
import draw_pd_platen_guide as drawing
from machinist_exceptions import load_exceptions
import package_native
from pd_platen_guide_spec import TAPPED_HOLE_SPEC
from pd_platen_spec import CBORE_DEPTH, PLATE_THICKNESS


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
    monkeypatch.setitem(
        _drawing_types.DRAWING_TEMPLATES,
        DrawingLayout.LANDSCAPE,
        replace(
            DRAWING_TEMPLATES[DrawingLayout.LANDSCAPE],
            dpi=30,
            pixel_size=(510, 330),
        ),
    )

    render_pdf_png(
        pdf,
        png,
        layout=DrawingLayout.LANDSCAPE,
        expected_pages=5,
    )

    with Image.open(png) as preview:
        assert preview.size == (510, 330)
        assert preview.info["dpi"] == pytest.approx((30, 30), abs=0.1)
        centers = ((85, 82), (255, 82), (425, 82), (85, 247), (255, 247))
        for center, color in zip(centers, colors, strict=True):
            assert preview.getpixel(center) == pytest.approx(color, abs=2)
        assert preview.getpixel((425, 247)) == (255, 255, 255)
        assert preview.getpixel((85, 10)) == (255, 255, 255)


def test_portrait_raster_crops_pdfium_width_rounding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import pypdfium2 as pdfium
    from pypdf import PdfWriter

    pdf = tmp_path / "portrait-width-plus-one.pdf"
    png = tmp_path / "portrait.png"
    writer = PdfWriter()
    writer.add_blank_page(width=793, height=1224)
    writer.write(pdf)
    monkeypatch.setitem(
        _drawing_types.DRAWING_TEMPLATES,
        DrawingLayout.PORTRAIT,
        replace(
            DRAWING_TEMPLATES[DrawingLayout.PORTRAIT],
            dpi=30,
            pixel_size=(330, 510),
        ),
    )
    document = pdfium.PdfDocument(str(pdf))
    page = document[0]
    uncropped = page.render(scale=30 / 72).to_pil()
    page.close()
    document.close()
    assert uncropped.size == (331, 510)
    uncropped.close()

    render_pdf_png(pdf, png, layout=DrawingLayout.PORTRAIT)

    with Image.open(png) as preview:
        assert preview.size == (330, 510)
        assert preview.info["dpi"] == pytest.approx((30, 30), abs=0.1)


def test_drawing_hole_sizes_follow_unc_policy() -> None:
    assert guide.TAPPED_HOLE_SPEC is TAPPED_HOLE_SPEC
    assert drawing.THREAD_DESIGNATION == "#4-40 UNC-2B"
    assert drawing.THREAD_TAP_DRILL_MM == blind_cut_dia_mm(TAPPED_HOLE_SPEC)
    assert drawing.THREAD_MAJOR_DIA_MM == THREAD_MAJOR_MM[TAPPED_HOLE_SPEC.size]
    assert CLEARANCE_MM[("#4", "normal")] == 3.264


def test_platen_guide_hole_stations_match_native_wizard_features() -> None:
    # The guide's screw stations are the platen's own guide-hole stations
    # (their .001 grid, within half a grid step of the even fractions); the
    # lock pair straddles the 30 % and 70 % stations.
    assert guide.SCREW_STATION_X == guide.GUIDE_HOLE_X
    assert guide.SCREW_STATION_X == pytest.approx(
        tuple(guide.GUIDE_LENGTH * fraction for fraction in (0.1, 0.3, 0.5, 0.7, 0.9)),
        abs=0.0127,
    )
    assert guide.LOCK_STATION_X == (guide.SCREW_STATION_X[1], guide.SCREW_STATION_X[3])
    assert guide.HOLE_X == pytest.approx(
        tuple(
            station + offset
            for station in guide.LOCK_STATION_X
            for offset in (-guide.LOCK_SCREW_DX, guide.LOCK_SCREW_DX)
        )
    )


# R9-64: the guide screws' front receivers are tapped THROUGH, so no thread
# or drill depth exists to stack (a blind tap could not hold full thread to
# the screw's reach and keep a bottoming tap's lead without its drill point
# breaking through a faced lock seat). Recomputed from the catalogue screw
# and the platen's counterbore, not from the build's derived constants.
_GUIDE_SCREW_LEN_MAX = 0.25 * 25.4  # 90114A511; B18.6.3 band +0/-0.03 in
_PLATEN_PASSAGE = PLATE_THICKNESS - CBORE_DEPTH  # plate less the stock-head counterbore


def test_front_receivers_are_through_taps_that_hold_the_screw_tip() -> None:
    spec = guide.TAPPED_HOLE_SPEC
    assert (spec.kind, spec.size, spec.end) == ("tapped", "#4-40", "through_all")
    assert spec.depth_mm == 0.0 and not spec.overrides_mm
    reach = _GUIDE_SCREW_LEN_MAX - _PLATEN_PASSAGE
    assert guide.GUIDE_SCREW_THREAD_ENGAGEMENT == pytest.approx(reach)
    # The tip against the shallowest seat (the faced lock seats over A2/A4).
    seat_min = min(_GUIDE_DEPTH_MIN, _BAR_DEPTH_MIN + _LOCK_GAP_FIT_MIN)
    assert seat_min - reach == pytest.approx(4.0532, abs=1e-3)
    assert guide.GUIDE_SCREW_TIP_INSIDE_MIN == pytest.approx(seat_min - reach)
    # The assembly's blind-bottom check reads the same tip clearance.
    assert guide.GUIDE_SCREW_BOTTOM_CLEARANCE == guide.GUIDE_SCREW_TIP_INSIDE_MIN
    # Full thread over the whole reach, even on the shortest catalogue screw.
    shortest = reach - 0.03 * 25.4
    assert shortest / THREAD_MAJOR_MM["#4-40"] >= 1.5


# R9-48: the lock receivers are #4-40 taps THROUGH the rail, so no depth band
# can starve the 3/8 lock screws. Recomputed here from the catalogue and the
# printed bands, not from the build's derived constants.
_IN = 25.4
_LOCK_SCREW_LEN_MAX = 0.375 * _IN  # 91792A108; B18.6.3 band +0/-0.03 in
_LOCK_THICK_MIN = (1.0 / 16.0 - 0.005) * _IN  # 1/16 sheet as supplied, +/-0.005 in
_GUIDE_DEPTH_MIN = 10.16 - 0.254  # .40 +0/-.01 on the guide sheet
_BAR_DEPTH_MIN = (0.374 - 0.003) * _IN  # MHA-PD-07 .374 +.001/-.003 (#1563)
_LOCK_GAP_FIT_MIN = 0.002 * _IN  # the faced lock seats (R9-47)


def test_lock_receivers_are_through_taps_that_hold_the_screw_tip() -> None:
    spec = guide.LOCK_TAP_SPEC
    assert (spec.kind, spec.size, spec.end) == ("tapped", "#4-40", "through_all")
    assert spec.depth_mm == 0.0 and not spec.overrides_mm
    seat_min = min(_GUIDE_DEPTH_MIN, _BAR_DEPTH_MIN + _LOCK_GAP_FIT_MIN)
    tip_reach_max = _LOCK_SCREW_LEN_MAX - _LOCK_THICK_MIN
    assert seat_min - tip_reach_max == pytest.approx(1.4097, abs=1e-3)
    assert guide.LOCK_SCREW_TIP_INSIDE_MIN == pytest.approx(seat_min - tip_reach_max)


def test_lock_through_tap_exits_clear_the_front_taps() -> None:
    # Each through tap exits the platen-mating face .276 from a front tap:
    # both stations at the title block's .XXX ±.005 (owner ruling
    # 2026-11-08), both mouths broken .010.
    from _inch_wall_limits import WALL_FLOOR_MM

    c2c = min(
        abs(lock - front)
        for lock in guide.HOLE_X
        for front in guide.SCREW_STATION_X
    )
    assert c2c == pytest.approx(0.276 * 25.4)
    wall = c2c - 2.0 * 0.005 * 25.4 - THREAD_MAJOR_MM["#4-40"] - 2.0 * 0.010 * 25.4
    assert wall == pytest.approx(3.403, abs=1e-3)
    assert wall >= WALL_FLOOR_MM
    assert guide.LOCK_TAP_EXIT_WALL_MIN == pytest.approx(wall)


def test_tap_walls_to_the_edges_pay_both_breaks_and_print_under_the_floor() -> None:
    # Codjiflo (#2124): .079 unbroken from each tap's major at the row's
    # .140 ±.005 (the shop's drilled-hole row, integration review
    # 20261109T062834910Z) to the bottom face and to the .29 top face at its
    # minimum, less the title block's .010 outside edge break and the tap's
    # .010 mouth break: .059, .001 under the .060 floor, which stays.
    from _inch_wall_limits import WALL_FLOOR_MM

    unbroken = guide.TAP_Y - THREAD_MAJOR_MM["#4-40"] / 2.0 - 0.005 * 25.4
    assert unbroken == pytest.approx(0.079 * 25.4, abs=1e-3)
    assert guide.TAP_EDGE_WALL_MIN == pytest.approx(unbroken - 2.0 * 0.010 * 25.4)
    assert guide.TAP_EDGE_WALL_MIN == pytest.approx(0.059 * 25.4, abs=5e-4)
    assert WALL_FLOOR_MM == pytest.approx(0.060 * 25.4)
    assert guide.TAP_EDGE_WALL_MIN < WALL_FLOOR_MM - 0.0005
    assert guide.TAP_EDGE_WALL_ACCEPTED == pytest.approx(0.059 * 25.4)
    # Rule 20: the sheet states the shortfall in note 1, which the banded
    # Y LOC header cites, and the package declares it (RV-01, delegated
    # ruling 2026-11-09 pending owner confirmation).
    assert guide.TAP_EDGE_WALL_TEXT == "WALL .059 MIN, TAPS TO EDGES"
    assert drawing.TAP_WALL_NOTE == "1. A1-A9: WALL .059 MIN, TAPS TO EDGES."
    assert drawing.HOLE_TABLE_BANDED_Y_HEADING.endswith(
        f"SEE NOTE {drawing.TAP_WALL_NOTE_NUMBER}"
    )
    assert drawing.TAP_WALL_NOTE.startswith(f"{drawing.TAP_WALL_NOTE_NUMBER}. ")
    exceptions = load_exceptions(_config.CONFIG_DIR, "pd-platen-guide", "part")
    (entry,) = [entry for entry in exceptions if entry.id == "RV-01"]
    assert entry.kind == "minor"
    assert "WALL .059 MIN" in entry.where and ".140 ±.005" in entry.where
    assert entry.reason.startswith("Owner ruling 2026-11-08 (Pedro)")
    assert (
        "Delegated ruling 2026-11-09 (Main), pending owner confirmation; "
        "owner review #2144 item 2.3"
    ) in entry.reason


def test_the_taps_print_plain_coordinates_without_gdt() -> None:
    """Owner ruling 2026-11-08 (#2144 item 2.3): noncritical holes, no
    position frame or datums, no spot-through route. The LOC columns are not
    basic (integration review 20261109T062834910Z): the stations take the
    title block's .XXX ±.005, and the tap row's band, the shop's drilled-hole
    row ±.005, prints on every Y LOC value, never in a note."""
    from pd_platen_guide_spec import (
        TAP_STATION_BAND,
        TAP_STATION_PLACES,
        TAP_Y_BAND,
        TAP_Y_BAND_TEXT,
    )

    assert not hasattr(guide, "GEOMETRIC_TOLERANCES_MM")
    assert TAP_STATION_PLACES == 3
    assert TAP_STATION_BAND == pytest.approx(0.005 * 25.4)
    assert TAP_Y_BAND == pytest.approx(0.005 * 25.4)
    assert TAP_Y_BAND_TEXT == ".140 ±.005"
    assert "±" not in drawing.TAP_WALL_NOTE and "LOC" not in drawing.TAP_WALL_NOTE
    assert not hasattr(drawing, "TAP_ROW_NOTE")
    assert len(drawing.HOLE_TAGS) == len(drawing.HOLE_STATIONS_MM) == 9
    exceptions = load_exceptions(_config.CONFIG_DIR, "pd-platen-guide", "part")
    assert [entry.id for entry in exceptions] == ["RV-01"]


def test_drawing_contract_imports_without_pywin32() -> None:
    script = """
import builtins
real_import = builtins.__import__
def blocked(name, *args, **kwargs):
    if name in {'pythoncom', 'pywintypes'} or name.startswith('win32com'):
        raise ImportError(f'blocked {name}')
    return real_import(name, *args, **kwargs)
builtins.__import__ = blocked
import test_pd_platen_guide_drawing
"""
    subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).parent,
        check=True,
        capture_output=True,
        text=True,
    )


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/pd-platen-guide.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/pd-platen-guide.pdf")
    assert drawing.PNG.as_posix().endswith("/png/pd-platen-guide_drawing.png")


def test_sheet_carries_no_notes_block() -> None:
    # Note 1 at the hole table carries the only words the taps need
    # (drawing-guidelines.md rule 7 (notes: few, flagged, never a method)).
    assert not hasattr(guide, "DRAWING_NOTES")


def test_bar_slide_face_carries_the_only_roughness_symbol() -> None:
    import build_pd_paper_drive_assembly as assembly
    from _gtol_planar import PlanarFace
    from _surface_finish import MACHINED_UM
    from pd_platen_guide_spec import SURFACE_FINISHES

    # The top rail hangs by its local y 0 face on the bar's top edge, and the
    # assembly keeps the part's y (Ry 180), so that face is the running one.
    assert assembly.BAR_TOP_Y == assembly.GUIDE_Y[1]
    assert [(c.key, c.roughness_um, c.face) for c in SURFACE_FINISHES] == [
        ("bar_slide", MACHINED_UM, PlanarFace((0, -1, 0), 0.0))
    ]
    # Its leader lands between the A1 and B1 axes, clear of both, at a point
    # projected from the controlled face's front edge (model y 0, z 0). The
    # 234a39c87 farm sheet drew that edge 1.1 mm under the hard-coded sheet y
    # the leader once asked for, past the 1 mm attachment readback limit.
    assert guide.SCREW_STATION_X[0] < drawing.BAR_SLIDE_STATION_MM < guide.HOLE_X[0]


def test_no_tag_text_reaches_the_next_hole_on_its_side_of_the_bar() -> None:
    """Farm layout audit after B2: a tag's text (~5.7 mm right of its 1.5 mm
    offset) ran past the next hole of a 7.0 pitch pair, so that hole's tag
    leader struck it. Tags on one side of the bar keep the next hole on that
    side clear of the text."""
    tag_text_reach_mm = drawing.HOLE_TAG_DX_M * 1000.0 + 5.7
    for above in (True, False):
        side = [
            s for s in drawing.HOLE_STATIONS_MM if (s in drawing.HOLE_TAGS_ABOVE) is above
        ]
        for left, right in zip(side, side[1:]):
            assert right - left > tag_text_reach_mm + 1.0, (left, right)
    assert drawing.HOLE_TAG_ABOVE_Y_M > drawing.FRONT_BOTTOM_Y_M + 0.007366


def test_part_authors_the_printed_dimensions_and_places() -> None:
    from pd_platen_guide_spec import (
        DRAWING_DIMENSIONS,
        DRAWING_PRECISION,
        DRAWING_PRECISION_BY_NAME,
        GUIDE_DEPTH_PLACES,
    )

    assert DRAWING_DIMENSIONS == {
        "GuideProfile": {"Length", "Height"},
        "Guide": {"Depth"},
    }
    # The length only meets the platen's edges and the holes locate from the
    # left end at basic stations: .XX (the inch .X's ±.1 would print a band
    # coarser than the platen it matches). The height prints at the places
    # the paper-drive lock-station sweep judges it at.
    assert DRAWING_PRECISION == {
        "GuideProfile": {"Length": 2, "Height": GUIDE_DEPTH_PLACES},
        "Guide": {"Depth": GUIDE_DEPTH_PLACES},
    }
    assert DRAWING_PRECISION_BY_NAME == {
        "Length": 2,
        "Height": GUIDE_DEPTH_PLACES,
        "Depth": GUIDE_DEPTH_PLACES,
    }


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


def test_drawing_template_layout_contracts() -> None:
    assert {
        layout: (
            template.path.name,
            template.width_m,
            template.height_m,
            template.dpi,
            template.pixel_size,
            template.title_block_left_m,
            template.title_block_top_m,
        )
        for layout, template in DRAWING_TEMPLATES.items()
    } == {
        DrawingLayout.LANDSCAPE: (
            "harmonic-analyzer-landscape.DRWDOT",
            0.4318,
            0.2794,
            300,
            (5100, 3300),
            0.216,
            0.066,
        ),
        DrawingLayout.PORTRAIT: (
            "harmonic-analyzer-portrait.DRWDOT",
            0.2794,
            0.4318,
            300,
            (3300, 5100),
            0.0636,
            0.066,
        ),
    }
    assert all(
        template.path.is_file() and template.path.stat().st_size > 0
        for template in DRAWING_TEMPLATES.values()
    )


def test_drawing_registry_is_unique_and_selects_layout_assets() -> None:
    assert len({spec.name for spec in DRAWINGS}) == len(DRAWINGS)
    assert len({spec.part for spec in DRAWINGS}) == len(DRAWINGS)
    outputs = [path for spec in DRAWINGS for path in spec.outputs.values()]
    assert len(set(outputs)) == len(outputs)
    assert all(
        spec.assets
        == tuple(
            DRAWING_TEMPLATES[layout].path
            for layout in dict.fromkeys((spec.layout, *spec.additional_layouts))
        )
        for spec in DRAWINGS
    )


def _prepared_native_tree(
    monkeypatch, tmp_path: Path, drawing_outputs: dict, fake_pack
) -> Path:
    """Point package_native at a throwaway repo with a faked Pack-and-Go, and
    point the (SolidWorks-free) publisher at the tree it prepares."""
    out = tmp_path / "native"
    monkeypatch.setattr(package_native, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(
        package_native, "OUT_SLDASM", tmp_path / "cad" / "out" / "sldasm"
    )
    monkeypatch.setattr(package_native, "RELEASE_DIR", tmp_path / "release")
    monkeypatch.setattr(package_native, "DRAWING_OUTPUTS", drawing_outputs)
    monkeypatch.setattr(package_native, "_pack_and_go_document", fake_pack)
    package_native.RELEASE_DIR.mkdir(exist_ok=True)
    package_native.prepare_out(out)
    monkeypatch.setattr(cut_release, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(
        cut_release, "NATIVE_PACKAGE_FILE", out / package_native.SIDECAR_NAME
    )
    return out


def test_release_stages_all_drawing_formats(tmp_path: Path, monkeypatch) -> None:
    sources: dict[str, Path] = {}
    for kind, name in (
        ("slddrw", "pd-platen-guide.SLDDRW"),
        ("pdf", "pd-platen-guide.pdf"),
        ("png", "pd-platen-guide_drawing.png"),
    ):
        source = tmp_path / "source" / kind / name
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(kind.encode())
        sources[kind] = source
    monkeypatch.setattr(cut_release, "DRAWING_OUTPUTS", {"pd_platen_guide": sources})

    stage = tmp_path / "stage"
    stage.mkdir()
    staged = cut_release.stage_drawings(stage)
    assert staged == {
        "pd_platen_guide:pdf": "pdf/pd-platen-guide.pdf",
        "pd_platen_guide:png": "png/pd-platen-guide_drawing.png",
    }
    for relpath in staged.values():
        assert (stage / relpath).is_file()

    referenced_model = tmp_path / "source" / "sldprt" / "pd-platen-guide.SLDPRT"
    referenced_model.parent.mkdir(parents=True)
    referenced_model.write_bytes(b"referenced model")

    def fake_pack(_sw, source, doc_type, archive):
        assert source == sources["slddrw"]
        assert doc_type == package_native.SW_DOC_DRAWING
        with zipfile.ZipFile(archive, "w") as package:
            package.writestr(source.name, source.read_bytes())
            package.writestr("pd-platen-guide.SLDPRT", b"referenced model")
        return (source, referenced_model)

    out = _prepared_native_tree(
        monkeypatch, tmp_path, {"pd_platen_guide": sources}, fake_pack
    )
    drawings = package_native.package_drawings(object(), out, {})
    package_native.write_sidecar(out, "R2026x-test", (), drawings)

    # The publisher holds no seat: it copies the prepared tree and rebuilds the
    # very drawing facts the COM half used to return inline. The prepared tree
    # keeps its cached ``slddrw/`` name; only the bundle renames it (#727).
    assert (out / "slddrw" / "pd-platen-guide.SLDDRW").is_file()
    native = cut_release.stage_native(stage, cut_release.load_native_package())
    assert native == {
        "pd_platen_guide:solidworks_slddrw": "solidworks/pd-platen-guide.SLDDRW",
        "pd_platen_guide:slddrw": "drawings-with-models/pd-platen-guide.SLDDRW",
    }
    assert (stage / "solidworks" / "pd-platen-guide.SLDDRW").read_bytes() == b"slddrw"
    assert (
        stage / "solidworks" / "pd-platen-guide.SLDPRT"
    ).read_bytes() == b"referenced model"
    portable = stage / "drawings-with-models"
    assert (portable / "pd-platen-guide.SLDDRW").read_bytes() == b"slddrw"
    assert (portable / "pd-platen-guide.SLDPRT").read_bytes() == b"referenced model"
    assert not (stage / "slddrw").exists()


def test_release_rejects_a_stale_native_package_schema(
    tmp_path: Path, monkeypatch
) -> None:
    sidecar = tmp_path / "native-package.json"
    sidecar.write_text('{"schema": 0}', encoding="utf-8")
    monkeypatch.setattr(cut_release, "NATIVE_PACKAGE_FILE", sidecar)

    with pytest.raises(SystemExit, match="doit package:release"):
        cut_release.load_native_package()

    sidecar.unlink()
    with pytest.raises(SystemExit, match="doit package:release"):
        cut_release.load_native_package()


def test_release_rejects_pack_collision_from_distinct_original_sources(
    tmp_path: Path,
) -> None:
    first = tmp_path / "one" / "pn-pen.SLDASM"
    second = tmp_path / "two" / "pn-pen.SLDASM"
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
        package_native._merge_pack_and_go_zip(
            archive,
            (second,),
            ((destination, {first.name.casefold(): first}),),
        )


def test_the_rail_declares_one_owner_per_face() -> None:
    import export_features
    from _gtol_face import FaceGeometry

    def plane(normal: tuple[float, float, float], offset_mm: float) -> FaceGeometry:
        point = tuple(value * offset_mm / 1000 for value in normal)
        return FaceGeometry(None, 4001, (*normal, *point), normal, ())

    manifest = export_features.requirement_manifest("pd_platen_guide")
    names = list(manifest["features"])
    assert names[:6] == [
        "left_end",
        "right_end",
        "bottom_face",
        "top_face",
        "front_face",
        "rear_face",
    ]
    assert names[6:] == [f"tap_a{index}" for index in range(1, 10)]
    faces = {
        "left_end": plane((-1.0, 0.0, 0.0), 0.0),
        "right_end": plane((1.0, 0.0, 0.0), guide.GUIDE_LENGTH),
        "bottom_face": plane((0.0, -1.0, 0.0), 0.0),
        "top_face": plane((0.0, 1.0, 0.0), guide.GUIDE_HEIGHT),
        "front_face": plane((0.0, 0.0, 1.0), 0.0),
        "rear_face": plane((0.0, 0.0, -1.0), guide.GUIDE_DEPTH),
    }
    tap_r = drawing.THREAD_TAP_DRILL_MM / 2
    for index, x in enumerate(drawing.HOLE_STATIONS_MM, 1):
        box = tuple(
            value / 1000
            for value in (x - tap_r, guide.TAP_Y - tap_r, -guide.GUIDE_DEPTH, x + tap_r, guide.TAP_Y + tap_r, 0.0)
        )
        faces[f"tap_a{index}"] = FaceGeometry(
            None, 4002, (0.0, 0.0, 0.0, 0.0, 0.0, 1.0, tap_r / 1000), None, box
        )
    selectors = export_features.feature_selectors("pd_platen_guide")
    for name, face in faces.items():
        owners = [
            owner
            for owner, specs in selectors.items()
            if any(selector.matches(face) for selector in specs)
        ]
        assert owners == [name], name


def test_rail_feature_bands_are_the_printed_ones() -> None:
    import export_features

    def _in(value: float) -> float:
        return value * 25.4

    features = export_features.requirement_manifest("pd_platen_guide")["features"]
    assert features["right_end"]["length"] == pytest.approx([_in(10.61), _in(10.63)])
    assert features["top_face"]["height"] == pytest.approx([_in(0.28), _in(0.30)])
    assert features["rear_face"]["depth"] == pytest.approx([_in(0.39), _in(0.40)])
    assert features["bottom_face"]["finish_callout"] == "63"
    stations = (1.062, 2.909, 3.185, 3.461, 5.308, 7.155, 7.431, 7.707, 9.554)
    for index, station in enumerate(stations, 1):
        tap = features[f"tap_a{index}"]
        front = index % 2 == 1
        assert tap["thread"] == "#4-40 UNC-2B" and tap["thru"] is True
        assert tap["mates"] == ("MHA-PD-02" if front else "MHA-PD-12")
        assert tap["axis"] == [0.0, 0.0, -1.0 if front else 1.0]
        assert tap["dia"] == pytest.approx([_in(0.089), _in(0.093)], abs=1e-3)
        assert tap["station"] == pytest.approx(
            [_in(station - 0.005), _in(station + 0.005)], abs=1e-3
        )
        assert tap["height"] == pytest.approx([_in(0.135), _in(0.145)], abs=1e-3)
        assert tap["edge_wall_min"] == pytest.approx(_in(0.059))
