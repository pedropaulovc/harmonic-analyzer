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

# The 45-degree seat-mouth chamfer at the Ø7.7 bore: legs 0.35, centroid
# 0.35/3 outside the bore radius.
_SEAT_MOUTH = math.pi * 0.35**2 * (3.85 + 0.35 / 3.0)


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
    expected = {"OuterDia", "BoreDia", "Length", "SeatMouthChamfer"}
    assert set(drawing.SECTION_KEEP) == marked == expected
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_precision(adapter, DRAWING_PRECISION)" in source


def test_bore_and_seat_mouth_are_banded_the_od_is_stock() -> None:
    # User ruling 2026-09-29 (MHA-DT-034 review): the tenon is turned to suit this
    # bore and the end play is fitted on the MHA-DT-032 shoulder.  The bore keeps
    # +/-0.10 (Codex P1/P2 on #1139, user ruling 2026-09-30): at .X the fitted
    # tenon could outgrow the MHA-DT-008 seat shoulder or thin the oak over the
    # pivot bore to 1.45.  Local review of 1f3067ef2: the bore grows to 7.7
    # for the bore's eccentricity.  User ruling 2026-10-01 (local review of
    # 47cb8a46b): the OD is the 9/16-in rod as supplied, a reference, skimmed
    # to the grip contour with the oak after cure.  Owner ruling A on #1661:
    # the seat mouth's chamfer prints 0.35 +/-0.05 (see below).
    assert spec.DRAWING_PRECISION_BY_NAME == {
        "OuterDia": 2,
        "BoreDia": 2,
        "Length": 1,
        "SeatMouthChamfer": 2,
    }
    assert (spec.BORE_DIA, spec.BORE_DIA_TOL) == (7.7, 0.10)
    assert spec.OUTER_DIA == spec.STOCK_DIA == pytest.approx(14.2875)
    assert not hasattr(spec, "OUTER_DIA_TOL")
    assert spec.REFERENCE_DIMENSIONS == {"OuterDia"}
    assert model_toleranced_dimensions(part) == {
        ("FerruleProfile", "BoreDia"): "BORE_DIA_TOL",
        ("FerruleProfile", "SeatMouthChamfer"): "SEAT_MOUTH_CHAMFER_TOL",
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
    assert part.V_INSTALLED == pytest.approx(
        math.pi * (6.25**2 - 3.85**2) * 7.0 - _SEAT_MOUTH
    )
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
    # 0.10 of eccentricity.  The Ø12.5 holds the title block's .X band
    # (MHA-DT-008 machinist review of 2026-10-18); off the bore by 0.175, the
    # skimmed ring keeps 1.675 of brass, and the smallest stock still cleans up.
    assert handle.SHOULDER_R == pytest.approx(spec.INSTALLED_OUTER_DIA / 2.0)
    assert handle.FERRULE_OFFSET_MAX == pytest.approx(0.10 + 0.15 / 2.0)
    assert handle.FERRULE_SKIMMED_WALL_MIN == pytest.approx(
        (12.5 - 0.8) / 2.0 - 0.10 - (7.8 / 2.0 + 0.175)
    )
    assert spec.STOCK_DIA_MIN / 2.0 >= (12.5 + 0.8) / 2.0 + 0.175 + 0.10
    assert handle.FERRULE_SEAT_RADIAL_MIN == pytest.approx(1.975)
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
    assert part.V_FERRULE == pytest.approx(
        math.pi * ((14.2875 / 2.0) ** 2 - 3.85**2) * 7.0 - _SEAT_MOUTH
    )
    assert part.MATERIAL == "Brass"


def test_note_names_the_mating_tenon() -> None:
    row = _config.parts("dt-crank-handle")
    assert spec.HANDLE_NUMBER == row["number"]
    assert f"{spec.HANDLE_NUMBER} {spec.HANDLE_NAME}" in spec.DRAWING_NOTES
    assert len(spec.DRAWING_NOTES.splitlines()) == 4
    # Machinist review of crank-v4-16: name the bore operation. The band's
    # reason stays off this full four-line block (Codex P1 on #1139,
    # c81d97280); drawing-guidelines.md rule 7 would allow a short one.
    # The OD is stock, skimmed at assembly.
    flat = " ".join(spec.DRAWING_NOTES.split())
    # The operation, not the machine (machinist review of crank-v4-22).
    assert flat.startswith("BORE THRU.") and "LATHE" not in flat
    assert "BAND" not in flat
    assert "OD AS SUPPLIED (9/16 IN ROD); SKIMMED TO <MOD-DIAM>12.5 WITH MHA-DT-008 AFTER CURE." in flat
    assert "TURNED TO SUIT THIS BORE" in spec.DRAWING_NOTES


def test_seat_mouth_chamfer_clears_the_tenon_root() -> None:
    import dt_crank_handle_spec as handle

    # Owner ruling A on #1661: the MHA-DT-008 tenon root is R0.3 MAX, so the
    # bore's mouth at the seat face is chamfered 45 degrees, its shortest leg
    # no smaller than the root, for the ring to seat on the shoulder.  Its
    # callout names the end and the root it clears (rule 4); the R it quotes
    # is MHA-DT-008's own, which this spec cannot import.
    assert (spec.SEAT_MOUTH_CHAMFER, spec.SEAT_MOUTH_CHAMFER_TOL) == (0.35, 0.05)
    assert spec.HANDLE_ROOT_R_MAX == handle.INSIDE_CORNER_R_MAX
    assert spec.SEAT_MOUTH_CHAMFER_MIN >= handle.INSIDE_CORNER_R_MAX
    assert spec.SEAT_MOUTH_CHAMFER_CALLOUT.splitlines() == [
        "X 45 DEG SEAT END",
        "CLEARS MHA-DT-008",
        "TENON ROOT R0.3",
    ]
    # The callout carries the chamfer; the notes do not repeat it.
    flat = " ".join(spec.DRAWING_NOTES.split())
    for fragment in ("45 DEG", "CHAMFER", "TENON ROOT"):
        assert fragment not in flat, fragment
    # Modelled in the revolve profile at 45 degrees by equation, before the
    # INSTALLED split, so the skimmed ring keeps it too.
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert '("SeatMouthChamfer", SEAT_MOUTH_CHAMFER)' in source
    assert """profile.record("SeatMouthChamferRise", '"SeatMouthChamfer"')""" in source
    assert source.index("SeatMouthChamferRise") < source.index(
        "create_configuration {INSTALLED_CONFIG}"
    )
    drawing_source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert '{"SeatMouthChamfer": SEAT_MOUTH_CHAMFER_CALLOUT}' in drawing_source
    assert 'location="below"' in drawing_source


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
    # The chamfer's value and callout rows (5.55 pitch, ~2.75 per character,
    # centred on the keep point) stand 3 clear of the seat face, of the bore
    # edge's extension line and of the isometric note.
    x, y = drawing.SECTION_KEEP["SeatMouthChamfer"]
    rows = [
        f"{spec.SEAT_MOUTH_CHAMFER:.2f} ±{spec.SEAT_MOUTH_CHAMFER_TOL:.2f}",
        *spec.SEAT_MOUTH_CHAMFER_CALLOUT.splitlines(),
    ]
    half_width = max(len(row) for row in rows) * 0.00275 / 2.0
    half_height = len(rows) * 0.00555 / 2.0
    assert x - half_width >= drawing.SEAT_FACE_X + 0.003
    assert y - half_height >= drawing.BORE_TOP_Y + 0.003
    assert x + half_width <= drawing.ISO_NOTE_POS[0] - 0.003
