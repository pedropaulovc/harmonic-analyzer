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
from _inch_wall_limits import WALL_FLOOR_MM, WALL_TARGET_MM
from _printed_tolerance import printed_band_mm
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
    # bore and the end play is fitted on the MHA-DT-32 shoulder.  The bore
    # holds the title block's .XXX band (#290; Codex P1/P2 on #1139: at .X the
    # fitted tenon could outgrow the MHA-DT-08 seat shoulder or thin the oak
    # over the pivot bore).  User ruling 2026-10-01 (local review of
    # 47cb8a46b): the OD is the 9/16-in rod as supplied, a reference, skimmed
    # to the grip contour with the oak after cure.
    assert spec.DRAWING_PRECISION_BY_NAME["BoreDia"] == 3
    assert spec.BORE_DIA_TOL == pytest.approx(printed_band_mm(3, unit=spec.UNIT))
    assert spec.OUTER_DIA == spec.STOCK_DIA == pytest.approx(9 / 16 * 25.4)
    assert spec.STOCK_FRACTION_DENOMINATOR == 16
    assert not hasattr(spec, "OUTER_DIA_TOL")
    assert spec.REFERENCE_DIMENSIONS == {"OuterDia"}
    assert model_toleranced_dimensions(part) == {}
    assert spec.WALL_WORST == pytest.approx(
        (spec.STOCK_DIA_MIN - (spec.BORE_DIA + spec.BORE_DIA_TOL)) / 2.0
    )
    assert spec.WALL_WORST >= WALL_FLOOR_MM


def test_installed_configuration_is_the_skimmed_ring() -> None:
    import build_dt_drive_train_assembly as drive_train

    assert spec.INSTALLED_CONFIG == "INSTALLED"
    assert spec.INSTALLED_OUTER_DIA == pytest.approx(0.49 * 25.4)
    installed_r = spec.INSTALLED_OUTER_DIA / 2.0
    assert part.V_INSTALLED == pytest.approx(
        math.pi * (installed_r**2 - (spec.BORE_DIA / 2.0) ** 2) * spec.LENGTH
    )
    source = Path(part.__file__).read_text(encoding="utf-8")
    split = source.index("create_configuration {INSTALLED_CONFIG}")
    for edit in (
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

    # The oak and the skimmed ring finish together at the skim contour (user
    # rulings 2026-09-30 and 2026-10-01), so the seat is the face over the
    # tenon outside its root relief; the bore keeps the wall floor of oak over
    # the pivot bore with the bore's eccentricity.  Owner ruling 2026-10-24
    # (#1900): cured on a mandrel through the pivot bore, the ring sits within
    # the eccentricity of it, and the smallest stock still cleans up.
    assert handle.SHOULDER_R == pytest.approx(spec.INSTALLED_OUTER_DIA / 2.0)
    assert handle.FERRULE_OFFSET_MAX == handle.BORE_ECCENTRICITY
    xx = printed_band_mm(2, unit=handle.UNIT)
    ecc = handle.BORE_ECCENTRICITY
    assert handle.FERRULE_SKIMMED_WALL_MIN == pytest.approx(
        (spec.INSTALLED_OUTER_DIA - xx) / 2.0
        - ecc
        - ((spec.BORE_DIA + spec.BORE_DIA_TOL) / 2.0 + ecc)
    )
    assert spec.STOCK_DIA_MIN / 2.0 >= (spec.INSTALLED_OUTER_DIA + xx) / 2.0 + 2.0 * ecc
    assert handle.FERRULE_SEAT_RADIAL_MIN >= handle.FERRULE_SEAT_RADIAL_FLOOR
    assert handle.TENON_WALL_MIN >= WALL_FLOOR_MM


def test_bore_reads_on_a_section_not_hidden_lines() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "create_section_view(" in source
    assert "set_hidden_lines_visible" not in source
    assert "create_section_axis_centerline(" in source


def test_ring_matches_the_photographed_brass_collar() -> None:
    # eight-views-4, user 2026-09-30: skimmed from rod as installed.
    assert spec.INSTALLED_OUTER_DIA < spec.STOCK_DIA_MIN
    assert part.V_FERRULE == pytest.approx(
        math.pi * ((spec.STOCK_DIA / 2.0) ** 2 - (spec.BORE_DIA / 2.0) ** 2) * spec.LENGTH
    )
    assert part.MATERIAL == "Brass"


def test_callouts_name_the_mating_tenon_and_no_general_note_remains() -> None:
    row = _config.parts("dt-crank-handle")
    assert notes.HANDLE_NUMBER == row["number"]
    # MHA-DT-34 machinist ENFORCE (r1-r3): the bore's matched fit and the OD's
    # skim sit on their own callouts, not in a general note; THRU rides on the
    # bore, and bonding the ring on is the assembly's business.
    assert notes.HANDLE_NUMBER in notes.BORE_FIT_CALLOUT.splitlines()[0]
    # The OD's skim names its mate and states the walls it leaves (rule 20).
    od_rows = notes.OUTER_DIA_CALLOUT.splitlines()
    assert od_rows[2] == "WITH MHA-DT-08"
    for callout in (notes.BORE_FIT_CALLOUT, notes.OUTER_DIA_CALLOUT):
        assert "EPOXY" not in callout and "LATHE" not in callout
    # The prose lives in the notes module, which the mating parts never import.
    for name in ("DRAWING_NOTES", "HANDLE_NUMBER", "SEAT_FACE_WALL_MIN"):
        assert not hasattr(spec, name), name
    for module in (part, drawing):
        source = Path(module.__file__).read_text(encoding="utf-8")
        assert "Manufacturing Notes" not in source
    drawing_source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "MACHINIST_REVIEW = MachinistReviewMode.ENFORCE" in drawing_source


def test_seat_mouth_takes_only_the_edge_break() -> None:
    import dt_crank_handle_spec as handle
    from _printed_tolerance import edge_break_chamfer_mm

    # Owner ruling 2026-10-24 (#1900, option 4) supersedes owner ruling A on
    # #1661's chamfer: MHA-DT-08's tenon root is relieved into its shoulder,
    # so the mouth keeps only the title block's edge break, which no longer
    # has to clear the root round and is not modelled.
    assert spec.SEAT_MOUTH_BREAK_MAX == edge_break_chamfer_mm(unit=spec.UNIT)
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
    assert handle.TENON_GLUE_LENGTH_MIN == pytest.approx(
        handle.TENON_LENGTH
        - printed_band_mm(2, unit=handle.UNIT)
        - handle.EDGE_BREAK_MAX_MM
        - spec.SEAT_MOUTH_BREAK_MAX
    )
    assert handle.TENON_GLUE_LENGTH_MIN >= spec.TENON_GLUE_LENGTH_FLOOR


def test_skimmed_walls_at_both_faces_are_stated_and_declared() -> None:
    import dt_crank_handle_spec as handle

    # #1900: the plain-bore wall missed the faces.  At the seat face only the
    # bore mouth is broken (the OD edge is the skim line shared with the oak),
    # over the rule-17 floor (owner ruling 2026-10-24).  At the arm face both
    # edges are broken (owner ruling 2026-10-26).  Both print, floored.
    thin_side = handle.FERRULE_SKIMMED_WALL_MIN
    assert handle.FERRULE_MOUTH_WALL_MIN == pytest.approx(
        thin_side - spec.SEAT_MOUTH_BREAK_MAX
    )
    assert handle.FERRULE_ARM_FACE_WALL_MIN == pytest.approx(
        thin_side - spec.SEAT_MOUTH_BREAK_MAX - handle.EDGE_BREAK_MAX_MM
    )
    assert handle.FERRULE_MOUTH_WALL_MIN >= handle.TENON_WALL_FLOOR_MM
    assert handle.FERRULE_MOUTH_WALL_MIN < WALL_TARGET_MM
    assert handle.FERRULE_ARM_FACE_WALL_MIN >= handle.FERRULE_ARM_FACE_WALL_ACCEPTED_MM
    assert notes.SEAT_FACE_WALL_MIN <= handle.FERRULE_MOUTH_WALL_MIN
    assert notes.ARM_FACE_WALL_MIN <= handle.FERRULE_ARM_FACE_WALL_MIN
    declared = {
        entry.id: entry
        for entry in load_exceptions(
            CAD_ROOT / "config", "dt-crank-handle-ferrule", "part"
        )
    }
    assert set(declared) == {"RV-01", "RV-02"}
    assert {entry.kind for entry in declared.values()} == {"minor"}
    assert "2026-10-24 (#1900" in declared["RV-01"].reason
    assert "2026-10-26 (#1900, arm face)" in declared["RV-02"].reason


def test_skimmed_mouth_wall_assert_fails_below_the_floor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import dt_crank_handle_spec as handle

    # Source-mutation control: a mouth break that eats the margin over the
    # floor must trip the #1900 check at the mouth, not pass on the plain bore.
    monkeypatch.setattr(
        spec,
        "SEAT_MOUTH_BREAK_MAX",
        handle.FERRULE_SKIMMED_WALL_MIN - WALL_FLOOR_MM + 0.0254,
    )
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
