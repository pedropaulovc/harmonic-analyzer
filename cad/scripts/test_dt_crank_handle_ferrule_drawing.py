"""Offline contracts for MHA-DT-034, the crank handle ferrule, and its drawing."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

import _config
import build_dt_crank_handle_ferrule as part
import dt_crank_handle_ferrule_spec as spec
import draw_dt_crank_handle_ferrule as drawing
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths_and_registry_entry() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/dt-crank-handle-ferrule.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/dt-crank-handle-ferrule.pdf")
    assert drawing.PNG.as_posix().endswith("/png/dt-crank-handle-ferrule_drawing.png")
    assert (
        DRAWINGS_BY_NAME["dt_crank_handle_ferrule"].script
        == Path(drawing.__file__).resolve()
    )
    assert "draw_dt_crank_handle_ferrule.py" in PRECISION_MIGRATED_DRAWINGS


def test_part_and_drawing_share_the_marked_dimension_contract() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.SECTION_KEEP) == marked == {"OuterDia", "BoreDia", "Length"}
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_precision(adapter, DRAWING_PRECISION)" in source


def test_only_the_bore_is_banded_the_od_is_stock() -> None:
    # User ruling 2026-09-29 (MHA-DT-034 review): the tenon is turned to suit this
    # bore and the end play is fitted on the MHA-DT-032 shoulder.  The bore keeps
    # +/-0.10 (Codex P1/P2 on #1139, user ruling 2026-09-30): at .X the fitted
    # tenon could outgrow the MHA-DT-008 seat shoulder or thin the oak over the
    # pivot bore to 1.45.  Local review of 1f3067ef2: the bore grows to 7.7
    # for the bore's eccentricity.  User ruling 2026-10-01 (local review of
    # 47cb8a46b): the OD is the 9/16-in rod as supplied, a reference, skimmed
    # to the grip contour with the oak after cure.
    assert spec.DRAWING_PRECISION_BY_NAME == {"OuterDia": 2, "BoreDia": 2, "Length": 1}
    assert (spec.BORE_DIA, spec.BORE_DIA_TOL) == (7.7, 0.10)
    assert spec.OUTER_DIA == spec.STOCK_DIA == pytest.approx(14.2875)
    assert not hasattr(spec, "OUTER_DIA_TOL")
    assert spec.REFERENCE_DIMENSIONS == {"OuterDia"}
    assert model_toleranced_dimensions(part) == {
        ("FerruleProfile", "BoreDia"): "BORE_DIA_TOL",
    }
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "set_dimension_bilateral_tolerance" not in source
    assert spec.WALL_WORST == pytest.approx((14.2875 - 0.0508 - 7.8) / 2.0)
    drawing_source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "for name in sorted(REFERENCE_DIMENSIONS):" in drawing_source


def test_installed_configuration_is_the_skimmed_ring() -> None:
    import build_dt_drive_train_assembly as drive_train

    assert spec.INSTALLED_CONFIG == "INSTALLED"
    assert spec.INSTALLED_OUTER_DIA == pytest.approx(12.5)
    assert part.V_INSTALLED == pytest.approx(math.pi * (6.25**2 - 3.85**2) * 7.0)
    source = Path(part.__file__).read_text(encoding="utf-8")
    split = source.index("create_configuration {INSTALLED_CONFIG}")
    for edit in (
        "set_dimension_symmetric_tolerance(adapter,",
        "apply_material(adapter,",
        "mark_dimensions_for_drawing(adapter,",
        "apply_drawing_precision(adapter,",
    ):
        assert source.index(edit) < split, edit
    assert "SetSuppression2(0, 3, bstr_array([default_config]))" in source
    assert source.index("re-activate {default_config}") < source.index("SetSuppression2(0, 3")
    assert "apply_grouped_bom_properties(" in source
    assert "require_material_in_every_configuration(" in source
    assert "assert_saved_configurations_regenerate(adapter, PART_NAME)" in source
    assert drive_train.HANDLE_FERRULE_INSTALLED_CONFIG == spec.INSTALLED_CONFIG
    dt_source = Path(drive_train.__file__).read_text(encoding="utf-8")
    assert "configuration=HANDLE_FERRULE_INSTALLED_CONFIG," in dt_source
    assert _config.parts("dt-crank-handle-ferrule")["description"] == "CRANK HANDLE FERRULE"


def test_fitted_tenon_keeps_its_seat_and_wall() -> None:
    import dt_crank_handle_spec as handle

    # The oak and the skimmed ring finish together at the Ø12.5 contour (user
    # rulings 2026-09-30 and 2026-10-01), so the seat is the whole face over
    # the tenon; the Ø7.7 bore keeps 1.5 of oak over the Ø4.1 pivot bore with
    # 0.10 of eccentricity.  Off the bore by 0.175, the skimmed ring keeps
    # 1.825 of brass, and the smallest stock still cleans up.
    assert handle.SHOULDER_R == pytest.approx(spec.INSTALLED_OUTER_DIA / 2.0)
    assert handle.FERRULE_OFFSET_MAX == pytest.approx(0.10 + 0.15 / 2.0)
    assert handle.FERRULE_SKIMMED_WALL_MIN == pytest.approx(
        (12.5 - 0.5) / 2.0 - 0.10 - (7.8 / 2.0 + 0.175)
    )
    assert spec.STOCK_DIA_MIN / 2.0 >= (12.5 + 0.5) / 2.0 + 0.175 + 0.10
    assert handle.FERRULE_SEAT_RADIAL_MIN == pytest.approx(2.125)
    assert handle.TENON_WALL_MIN == pytest.approx(1.55)


def test_bore_reads_on_a_section_not_hidden_lines() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "create_section_view(" in source
    assert "set_hidden_lines_visible" not in source
    assert "create_section_axis_centerline(" in source


def test_ring_matches_the_photographed_brass_collar() -> None:
    # eight-views-4, user 2026-09-30: Ø12.5 as installed, skimmed from rod.
    assert spec.INSTALLED_OUTER_DIA == pytest.approx(12.5)
    assert spec.LENGTH == pytest.approx(7.0)
    assert part.V_FERRULE == pytest.approx(math.pi * ((14.2875 / 2.0) ** 2 - 3.85**2) * 7.0)
    assert part.MATERIAL == "Brass"


def test_note_names_the_mating_tenon() -> None:
    row = _config.parts("dt-crank-handle")
    assert spec.HANDLE_NUMBER == row["number"]
    assert f"{spec.HANDLE_NUMBER} {spec.HANDLE_NAME}" in spec.DRAWING_NOTES
    assert len(spec.DRAWING_NOTES.splitlines()) == 4
    # Machinist review of crank-v4-16: name the bore operation.  Rule 6
    # (Codex P1 on #1139, c81d97280): no narration of why the band exists.
    # The OD is stock, skimmed at assembly.
    flat = " ".join(spec.DRAWING_NOTES.split())
    # The operation, not the machine (machinist review of crank-v4-22).
    assert flat.startswith("BORE THRU.") and "LATHE" not in flat
    assert "BAND" not in flat
    assert "OD AS SUPPLIED (9/16 IN ROD); SKIMMED TO <MOD-DIAM>12.5 WITH MHA-DT-008 AFTER CURE." in flat
    assert "TURNED TO SUIT THIS BORE" in spec.DRAWING_NOTES


def test_registry_row_is_the_title_block_source() -> None:
    row = _config.parts("dt-crank-handle-ferrule")
    assert row["number"] == "MHA-DT-034"
    assert row["title"] == "Crank Handle Ferrule"
    assert len(str(row["material"])) <= 36
    assert int(row["quantity"]) == 1


def test_sheet_layout_keeps_annotations_inside_the_field() -> None:
    for x, y in (
        *drawing.SECTION_KEEP.values(),
        drawing.MANUFACTURING_NOTES_POS,
        drawing.ISO_NOTE_POS,
        drawing.CAPTION_XY,
    ):
        assert 0.012 < x < 0.420
        assert 0.012 < y < 0.267
        assert not (x > 0.216 and y < 0.070)
    assert drawing.END_CENTER[0] + drawing.OUTER_R < drawing.SECTION_KEEP["OuterDia"][0] - 0.010
    assert drawing.SECTION_KEEP["BoreDia"][0] + 0.020 < drawing.ISO_NOTE_POS[0]
