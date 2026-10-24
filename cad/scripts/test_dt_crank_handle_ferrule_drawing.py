"""Offline contracts for MHA-DT-34, the crank handle ferrule, and its drawing."""

from __future__ import annotations

import math
import runpy
from pathlib import Path

import pytest

import _config
import build_dt_crank_handle_ferrule as part
import dt_crank_handle_ferrule_notes as notes
import dt_crank_handle_ferrule_spec as spec
import draw_dt_crank_handle_ferrule as drawing
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _paths import CAD_ROOT
from machinist_exceptions import load_exceptions


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
    expected = {"OuterDia", "BoreDia", "Length"}
    assert set(drawing.SECTION_KEEP) == marked == expected
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_precision(adapter, DRAWING_PRECISION)" in source


def test_bore_is_banded_the_od_is_stock() -> None:
    # User ruling 2026-09-29 (MHA-DT-34 review): the tenon is turned to suit this
    # bore and the end play is fitted on the MHA-DT-32 shoulder.  The bore keeps
    # +/-0.10 (Codex P1/P2 on #1139, user ruling 2026-09-30): at .X the fitted
    # tenon could outgrow the MHA-DT-08 seat shoulder or thin the oak over the
    # pivot bore to 1.45.  Local review of 1f3067ef2: the bore grows to 7.7
    # for the bore's eccentricity.  User ruling 2026-10-01 (local review of
    # 47cb8a46b): the OD is the 9/16-in rod as supplied, a reference, skimmed
    # to the grip contour with the oak after cure.  Owner ruling 2026-10-24
    # (#1900): the seat mouth's chamfer is gone (see below).
    assert spec.DRAWING_PRECISION_BY_NAME == {
        "OuterDia": 2,
        "BoreDia": 2,
        "Length": 1,
    }
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
    # rulings 2026-09-30 and 2026-10-01), so the seat is the face over the
    # tenon outside its root relief; the Ø7.7 bore keeps 1.5 of oak over the
    # Ø4.1 pivot bore with 0.10 of eccentricity.  The Ø12.5 holds the title
    # block's .X band (MHA-DT-08 machinist review of 2026-10-18).  Owner ruling
    # 2026-10-24 (#1900): cured on a mandrel through the pivot bore, the ring
    # sits 0.10 off it, not the 0.175 of riding the tenon's glue line, so the
    # skimmed ring keeps 1.75 of brass, and the smallest stock still cleans up.
    # Owner ruling B on #1375 enlarges the cup fit and butt contour only;
    # the ferrule's shoulder, fitted tenon and running bore stay unchanged.
    assert (handle.TENON_LENGTH, handle.TENON_DIA, handle.PIVOT_BORE_DIA) == pytest.approx(
        (5.0, 7.6, 4.10)
    )
    assert handle.SHOULDER_R == pytest.approx(spec.INSTALLED_OUTER_DIA / 2.0)
    assert handle.FERRULE_OFFSET_MAX == pytest.approx(0.10) == handle.BORE_ECCENTRICITY
    assert handle.FERRULE_SKIMMED_WALL_MIN == pytest.approx(
        (12.5 - 0.8) / 2.0 - 0.10 - (7.8 / 2.0 + 0.10)
    )
    assert spec.STOCK_DIA_MIN / 2.0 >= (12.5 + 0.8) / 2.0 + 0.10 + 0.10
    assert handle.FERRULE_SEAT_RADIAL_MIN == pytest.approx(1.975 - 1.4)
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
        math.pi * ((14.2875 / 2.0) ** 2 - 3.85**2) * 7.0
    )
    assert part.MATERIAL == "Brass"


def test_callouts_name_the_mating_tenon_and_no_general_note_remains() -> None:
    row = _config.parts("dt-crank-handle")
    assert notes.HANDLE_NUMBER == row["number"]
    # MHA-DT-34 machinist ENFORCE (r1-r3): the bore's matched fit and the OD's
    # skim sit on their own callouts, not in a general note; THRU rides on the
    # bore, and bonding the ring on is the assembly's business.
    assert notes.BORE_FIT_CALLOUT.splitlines() == [
        "THRU; MHA-DT-08 TENON",
        "TURNED TO SUIT, 0.05-0.15",
        "DIAMETRAL CLEARANCE",
    ]
    assert notes.OUTER_DIA_CALLOUT.splitlines() == [
        "STOCK;",
        "SKIM TO <MOD-DIAM>12.5",
        "WITH MHA-DT-08",
        "AFTER CURE;",
        "WALL 1.50 MIN",
    ]
    for callout in (notes.BORE_FIT_CALLOUT, notes.OUTER_DIA_CALLOUT):
        assert "EPOXY" not in callout and "LATHE" not in callout
    # The prose lives in the notes module, which the mating parts never import.
    for name in ("DRAWING_NOTES", "HANDLE_NUMBER", "MOUTH_WALL_MIN"):
        assert not hasattr(spec, name), name
    for module in (part, drawing):
        source = Path(module.__file__).read_text(encoding="utf-8")
        assert "Manufacturing Notes" not in source
    drawing_source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert '"BoreDia": BORE_FIT_CALLOUT,' in drawing_source
    assert '"OuterDia": OUTER_DIA_CALLOUT,' in drawing_source
    assert "MACHINIST_REVIEW = MachinistReviewMode.ENFORCE" in drawing_source


def test_seat_mouth_takes_only_the_edge_break() -> None:
    import dt_crank_handle_spec as handle
    from dt_crank_hub_geometry import EDGE_BREAK_MAX_MM

    # Owner ruling 2026-10-24 (#1900, option 4) supersedes owner ruling A on
    # #1661's 0.35 +/-0.05 chamfer: MHA-DT-08's tenon root is relieved into its
    # shoulder, so the mouth keeps only the title block's 0.25 break, which no
    # longer has to clear the R0.3 root and is not modelled.
    assert spec.SEAT_MOUTH_BREAK_MAX == EDGE_BREAK_MAX_MM == 0.25
    for name in (
        "SEAT_MOUTH_CHAMFER",
        "SEAT_MOUTH_CHAMFER_MIN",
        "SEAT_MOUTH_CHAMFER_MAX",
        "SEAT_MOUTH_CHAMFER_TOL",
    ):
        assert not hasattr(spec, name), name
    assert not hasattr(notes, "SEAT_MOUTH_CHAMFER_CALLOUT")
    for module in (part, drawing):
        source = Path(module.__file__).read_text(encoding="utf-8")
        assert "SeatMouthChamfer" not in source
    # The relief keeps the root round behind the seat face, and the break
    # alone comes off the shortest tenon's bonded length.
    assert handle.TENON_ROOT_RELIEF_MIN >= handle.TENON_ROOT_ROUND_REACH
    assert handle.TENON_GLUE_LENGTH_MIN == pytest.approx(4.2 - 0.25 - 0.25)
    assert handle.TENON_GLUE_LENGTH_MIN >= spec.TENON_GLUE_LENGTH_FLOOR


def test_skimmed_wall_at_the_seat_mouth_is_stated_and_declared() -> None:
    import dt_crank_handle_spec as handle

    # #1900: the plain-bore wall missed the mouth.  At the seat face, the .X
    # skim small, 0.10 of skim wander, the 0.10 mandrel offset, the largest
    # bore and the 0.25 break leave 1.50: the rule-17 floor, under the 2.0
    # target, accepted by the owner (2026-10-24) and stated on the sheet.
    assert handle.FERRULE_MOUTH_WALL_MIN == pytest.approx(
        (12.5 - 0.8) / 2.0 - 0.10 - (7.8 / 2.0 + 0.10) - 0.25
    )
    assert handle.FERRULE_MOUTH_WALL_MIN == pytest.approx(1.50)
    assert handle.FERRULE_MOUTH_WALL_MIN >= handle.TENON_WALL_FLOOR_MM
    assert handle.FERRULE_MOUTH_WALL_MIN < handle.WALL_TARGET_MM
    assert notes.MOUTH_WALL_MIN == pytest.approx(handle.FERRULE_MOUTH_WALL_MIN)
    assert f"WALL {notes.MOUTH_WALL_MIN:.2f} MIN" in notes.OUTER_DIA_CALLOUT
    (declared,) = load_exceptions(
        CAD_ROOT / "config", "dt-crank-handle-ferrule", "part"
    )
    assert (declared.id, declared.kind) == ("RV-01", "minor")
    assert "WALL 1.50 MIN" in declared.where
    assert "2026-10-24" in declared.reason and "#1900" in declared.reason


def test_skimmed_mouth_wall_assert_fails_below_the_floor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import dt_crank_handle_spec as handle

    # Source-mutation control: a larger mouth break (the ruling-A chamfer's
    # 0.40) must trip the #1900 check at the mouth, not pass on the plain bore.
    monkeypatch.setattr(spec, "SEAT_MOUTH_BREAK_MAX", 0.40)
    with pytest.raises(AssertionError, match="broken seat mouth"):
        runpy.run_path(handle.__file__)


def test_registry_row_is_the_title_block_source() -> None:
    row = _config.parts("dt-crank-handle-ferrule")
    assert row["number"] == "MHA-DT-34"
    assert row["title"] == "Crank Handle Ferrule"
    assert len(str(row["material"])) <= 36
    assert int(row["quantity"]) == 1


def _block(name: str, value: str, callout: str) -> tuple[float, float, float, float]:
    """Value plus callout rows (5.55 pitch, ~2.75 per character), centred on
    the keep point: (left, right, bottom, top)."""
    x, y = drawing.SECTION_KEEP[name]
    rows = [value, *callout.replace("<MOD-DIAM>", "Ø").splitlines()]
    half_width = max(len(row) for row in rows) * 0.00275 / 2.0
    half_height = len(rows) * 0.00555 / 2.0
    return x - half_width, x + half_width, y - half_height, y + half_height


def test_sheet_layout_keeps_annotations_inside_the_field() -> None:
    for x, y in (
        *drawing.SECTION_KEEP.values(),
        drawing.ISO_NOTE_POS,
        drawing.CAPTION_XY,
    ):
        assert 0.012 < x < 0.420
        assert 0.012 < y < 0.267
        assert not (x > 0.216 and y < 0.070)
    assert drawing.END_CENTER[0] + drawing.OUTER_R < drawing.SECTION_KEEP["OuterDia"][0] - 0.010
    assert drawing.SECTION_KEEP["BoreDia"][0] + 0.020 < drawing.ISO_NOTE_POS[0]
    section_left = drawing.SECTION_CENTER[0] - drawing.HALF_LENGTH
    bore_bottom_y = 2.0 * drawing.SECTION_CENTER[1] - drawing.BORE_TOP_Y
    # The bore's block stands between its extension lines, right of the seat
    # face and clear of the isometric note.
    left, right, bottom, top = _block(
        "BoreDia", f"Ø{spec.BORE_DIA:.2f} ±0.1", notes.BORE_FIT_CALLOUT
    )
    assert left >= drawing.SEAT_FACE_X + 0.003
    assert bottom >= bore_bottom_y + 0.003
    assert top <= drawing.BORE_TOP_Y - 0.003
    assert right <= drawing.ISO_NOTE_POS[0] - 0.003
    # The OD's block stands between its extension lines, left of the section
    # and right of the end view.
    left, right, bottom, top = _block(
        "OuterDia", f"(Ø{spec.OUTER_DIA:.2f})", notes.OUTER_DIA_CALLOUT
    )
    assert right <= section_left - 0.003
    assert left >= drawing.END_CENTER[0] + drawing.OUTER_R + 0.003
    assert bottom >= drawing.SECTION_CENTER[1] - drawing.OUTER_R + 0.003
    assert top <= drawing.SECTION_CENTER[1] + drawing.OUTER_R - 0.003
