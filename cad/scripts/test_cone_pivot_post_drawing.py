"""Offline contracts for the v2 cone-pivot-post source and drawing."""

from __future__ import annotations

from pathlib import Path

import build_cone_pivot_post as part
import cone_pivot_post_spec as spec
import draw_cone_pivot_post as drawing
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/cone-pivot-post.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/cone-pivot-post.pdf")
    assert drawing.PNG.as_posix().endswith("/png/cone-pivot-post_drawing.png")
    assert (
        DRAWINGS_BY_NAME["cone_pivot_post"].script
        == Path(drawing.__file__).resolve()
    )


def test_v2_harvest_is_the_exact_dimensional_contract() -> None:
    assert (spec.BLOCK_DIA, spec.BLOCK_HEIGHT) == (42.011, 86.0)
    assert (spec.HEAD_DIA, spec.HEAD_HEIGHT, spec.HEAD_BASE_Y) == (
        42.7506,
        26.6,
        59.4,
    )
    assert (
        spec.CRANK_BOSS_DIA,
        spec.CRANK_BORE_DIA,
        spec.CRANK_BORE_HEIGHT,
        spec.CRANK_BORE_OFFSET,
    ) == (21.93, 11.438, 72.7, 0.0)
    assert round(spec.CRANK_BOSS_START_Z, 4) == -21.3753
    assert round(spec.CRANK_BOSS_END_Z, 4) == 51.0367
    assert (spec.CONE_BOSS_DIA, spec.BORE_DIA, spec.BORE_HEIGHT) == (
        17.2,
        12.2808,
        33.368,
    )
    assert spec.INCLINE_DEG == 12.5182
    assert (
        spec.ATTACHMENT_SPACING,
        spec.ATTACHMENT_THRU_DIA,
        spec.ATTACHMENT_CBORE_DIA,
        spec.ATTACHMENT_CBORE_DEPTH,
    ) == (26.88704, 7.14248, 11.50874, 6.0198)
    assert spec.HARVESTED_VOLUME_MM3 == 112_406.7676
    assert spec.HARVESTED_MASS_KG == 0.809328727


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.TOP_KEEP)
    assert kept == marked
    assert marked == {
        "MainBodyDia",
        "MainBodyHt",
        "HeadDia",
        "HeadHt",
        "CrankAxisY",
        "CrankBossDia",
        "CrankBoreDia",
    }


def test_journal_axis_table_matches_the_inclined_v2_bore() -> None:
    assert spec.JOURNAL_AXIS_ORIENTATION_NOTE == (
        "O = A/B INTERSECTION; +Y ALONG B AWAY FROM A\n"
        "+X RIGHT; +Z DOWN IN UPPER PLAN"
    )
    assert tuple(
        (point, *(round(value, 3) for value in coordinates))
        for point, *coordinates in spec.JOURNAL_AXIS_POINTS
    ) == (
        ("P", 0.0, 33.368, 0.0),
        ("Q", 21.675, 33.368, 97.623),
    )
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "JOURNAL AXIS COORDINATES (mm)" in source
    assert "AXIS = LINE THROUGH P AND Q" in source
    assert "JOURNAL_AXIS_POINTS" in source
    assert '("POINT", "X", "Y", "Z")' in source
    assert "note.SetBalloon(4, 0)" in source


def test_manufacturing_notes_describe_the_bossed_casting() -> None:
    notes = spec.DRAWING_NOTES
    assert "CAST ASTM A48 CLASS 30" in notes
    assert "MACHINE FOOT, BOSSES, BORES AND MOUNTING HOLES" in notes
    assert "MAIN-BODY OD" in notes
    assert "INCLINED JOURNAL AXIS" in notes
    assert "12.2808" in notes
    assert "11.438" in notes
    assert "11.50874" in notes
    assert "26.88704" in notes
    assert "CONTINUOUS-CAST ROUND STOCK" not in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source
    assert "ATTACHMENT_CBORE_DIA" in source
    assert "ATTACHMENT_THRU_DIA" in source
    assert "ATTACHMENT_SPACING" in source


def test_source_records_exact_manual_photo_provenance() -> None:
    sources = "\n".join(
        (
            Path(spec.__file__).read_text(encoding="utf-8"),
            Path(part.__file__).read_text(encoding="utf-8"),
        )
    )
    assert "ch30_images/page003_img01.png" in sources
    assert "ch11_images/page002_img05.jpeg" in sources
    assert "page002_img06.jpeg" in sources
    assert "manually rederived" in sources


def test_part_exposes_semantic_mating_references() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    for name in (
        "ConeShaftNormal",
        "journal axis",
        "swing pivot",
        "mount east",
        "mount west",
    ):
        assert f'"{name}"' in source
    assert 'mode="cylindrical_face"' in source
    assert '(("mount west", ATTACHMENT_X), ("mount east", -ATTACHMENT_X))' in source
    assert part.CRANK_BORE_DX == spec.CRANK_BORE_OFFSET == 0.0
    assert part.CRANK_BORE_Y == spec.CRANK_BORE_HEIGHT == 72.7
    assert "HARVESTED_VOLUME_MM3" in source


def test_native_datums_and_controls_are_present() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("add_datum_feature(") == 3
    assert source.count("add_feature_control_frame(") == 4
    assert 'datums=("A", "B")' in source
    assert 'datums=("A", "B", "C")' in source
    assert 'characteristic="flatness"' in source
    assert 'characteristic="cylindricity"' in source
    assert 'characteristic="position"' in source
    assert "add_surface_finish(" not in source


def test_view_scales_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (1.0, 1.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("scale=(1, 1)") == 2
    assert source.count("scale=(1, 2)") == 1


def test_part_config_is_a_machined_casting() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("cone-pivot-post")
    assert "A48" in str(config["material_specification"])
    assert "A48" in str(config["material"])
    assert "RAL 6005" in str(config["finish"])
    assert "SSPC-SP 3" in str(config["finish"])
    assert "50-75 um DFT" in str(config["finish"])
    assert "boss" in str(config["finish"]).lower()
    assert "cast + machined" in str(config["process"])
    assert int(config["quantity"]) == 1
