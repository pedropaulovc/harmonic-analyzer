"""Offline contracts for the arbor-pedestal drawing."""

from __future__ import annotations

import re
from pathlib import Path

import arbor_pedestal_spec
import build_arbor_pedestal as part
import draw_arbor_pedestal as drawing
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _hole_spec import blind_cut_dia_mm


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/arbor-pedestal.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/arbor-pedestal.pdf")
    assert drawing.PNG.as_posix().endswith("/png/arbor-pedestal_drawing.png")
    assert DRAWINGS_BY_NAME["arbor_pedestal"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is arbor_pedestal_spec.DRAWING_DIMENSIONS
    marked = set().union(*arbor_pedestal_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.TOP_KEEP)
    assert kept == marked
    assert marked == {
        "Width",
        "Depth",
        "FootHt",
        "BoreDia",
    }


def test_arbor_bore_closes_the_configured_running_fit() -> None:
    import _config

    assert round(arbor_pedestal_spec.BORE_DIA, 2) == 9.55
    assert drawing.DIMENSION_CALLOUTS["BoreDia"] == ("REAM THRU; ON PART C/L")
    assert "BoreHeight" not in drawing.DIMENSION_CALLOUTS
    assert drawing.DIMENSION_PRECISION == {
        "Width": 1,
        "Depth": 1,
        "FootHt": 1,
        "BoreDia": 2,
    }
    shaft_limits = (9.505, 9.525)
    bore_limits = (9.550, 9.580)
    clearances = (
        bore_limits[0] - shaft_limits[1],
        bore_limits[1] - shaft_limits[0],
    )
    expected = tuple(_config.fit("shaft_in_bushing", "diametral_clearance_mm"))
    assert tuple(round(value, 3) for value in clearances) == expected


def test_screw_hole_contract_is_part_owned() -> None:
    spec = arbor_pedestal_spec.SCREW_HOLE_SPEC
    assert part.SCREW_HOLE_SPEC is spec
    assert spec.kind == "clearance"
    assert spec.size == "#4"
    assert spec.fit == "normal"
    assert arbor_pedestal_spec.SCREW_HOLE_DIA == blind_cut_dia_mm(spec)
    assert part.SCREW_HOLE_DIA == blind_cut_dia_mm(spec)


def test_no_dead_band_between_wizard_correction_and_the_builder_assert() -> None:
    """What the wizard will FORCE must cover what the builder will ACCEPT.

    These were two different literals -- `_holes` only corrected a drift over
    0.05 mm, while `build_arbor_pedestal` rejected anything over 0.005. A #4
    clearance initialized at 3.2512 instead of 3.264 drifts 0.0128 and lands in
    the gap: the wizard leaves it, the builder refuses it, and NO value of the
    spec pin can satisfy both. It read as the seat's table "moving" and cost
    three flip-flops of the pin before Codex spotted the real mechanism on #422.

    Both now read one constant. This test fails if they are ever separated
    again, including by someone tightening only the builder's side.
    """
    import _holes

    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "DIAMETER_TOLERANCE_MM" in source, "builder must use the shared tolerance"
    # Any numeric literal compared against the cut diameter re-opens the band.
    # Regex rather than a fixed string so `>0.005`, `> 0.0050` and friends are
    # caught too -- a whitespace variant slipping through would defeat the gate.
    assert not re.search(r"[<>]=?\s*0\.0*5\b|[<>]=?\s*0\.005\d*", source), (
        "builder compares the cut diameter against a numeric literal; use "
        "_holes.DIAMETER_TOLERANCE_MM so the wizard's correction threshold and "
        "this acceptance threshold cannot separate into a dead band again"
    )

    holes_source = Path(_holes.__file__).read_text(encoding="utf-8")
    assert (
        "abs(initialized_dia_mm - pinned_dia_mm) > DIAMETER_TOLERANCE_MM"
        in holes_source
    )

    # The tolerance must sit strictly between the benign rounding gap (the
    # 0.0001 between CLEARANCE_MM's 3.264 and the live 3.2639 -- writing there
    # would corrupt swHoleThru 25 into 26) and the wrong-row drift it must
    # catch (3.264 vs ("#3","loose") 3.251 = 0.0128).
    rounding_gap = abs(3.2639 - _holes.CLEARANCE_MM[("#4", "normal")])
    wrong_row_drift = abs(
        _holes.CLEARANCE_MM[("#4", "normal")] - _holes.CLEARANCE_MM[("#3", "loose")]
    )
    assert rounding_gap < _holes.DIAMETER_TOLERANCE_MM < wrong_row_drift


def test_material_and_finish_requirements_stay_out_of_notes() -> None:
    assert not hasattr(arbor_pedestal_spec, "DRAWING_NOTES")
    drawing_source = Path(drawing.__file__).read_text(encoding="utf-8")
    part_source = Path(part.__file__).read_text(encoding="utf-8")
    assert "Manufacturing Notes" not in drawing_source
    assert "Manufacturing Notes" not in part_source
    assert "StrapProfile" not in arbor_pedestal_spec.DRAWING_DIMENSIONS
    assert "DomeProfile" not in arbor_pedestal_spec.DRAWING_DIMENSIONS


def test_ordinary_dimensions_define_the_bore_strap_and_hold_down_hole() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    for label in (
        'label="bore height from foot seat"',
        'label="overall height reference"',
        'label="hold-down hole depth location"',
        'label="upright depth"',
    ):
        assert label in source
    assert drawing.DIMENSION_CALLOUTS == {"BoreDia": "REAM THRU; ON PART C/L"}
    assert 'label="crown radius"' in source
    assert "AddRadialDimension2" in source
    assert "add_native_hole_callout(" in source
    assert '"UPRIGHT DEPTH"' in source
    assert '"side-taper reference angle"' in source
    assert 3.0 < arbor_pedestal_spec.TAPER_ANGLE_DEG < 4.0
    assert 'label="flange hold-down hole"' in source
    assert "SetSecondArrow(False, False)" in source
    assert "GetSecondArrow()" in source
    assert "SetLeaderAttachmentPointAtIndex" not in source
    assert 'process="FOOT-FLANGE HOLE ON PART C/L: DRILL"' in source
    assert '"Material",' in source
    assert arbor_pedestal_spec.BORE_HEIGHT == 39.718
    assert arbor_pedestal_spec.STRAP_T == 10.0
    assert arbor_pedestal_spec.FOOT_WIDTH == 24.0
    assert arbor_pedestal_spec.FOOT_DEPTH == 16.0
    assert arbor_pedestal_spec.BORE_HEIGHT + arbor_pedestal_spec.TOP_RADIUS == 49.718
    assert "set_reference_dimension(" in source
    assert "_top_width_edge" not in source
    assert "StrapRootWidth" not in drawing.FRONT_KEEP
    assert drawing.FRONT_KEEP["Width"][1] < drawing._front_y(0.0)
    assert drawing.TOP_KEEP["Depth"][0] < drawing.TOP_CENTER[0]


def test_pedestal_has_no_gdt_or_basic_dimensions() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    for helper in (
        "add_datum_feature(",
        "add_feature_control_frame(",
        "set_basic_dimension(",
        "project_part_pmi(",
    ):
        assert helper not in source, helper
    assert "datum=" not in source
    assert "characteristic=" not in source
    assert not hasattr(arbor_pedestal_spec, "GEOMETRIC_TOLERANCES_MM")
    assert not hasattr(arbor_pedestal_spec, "DOME_DIA")
    assert not hasattr(arbor_pedestal_spec, "SCREW_CLEARANCE_DIA")


def test_reamed_running_bore_carries_one_surface_finish_control() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert drawing.DIMENSION_CALLOUTS["BoreDia"].startswith("REAM THRU")
    assert len(arbor_pedestal_spec.SURFACE_FINISHES) == 1
    control = arbor_pedestal_spec.SURFACE_FINISHES[0]
    assert control.key == "arbor_bore"
    assert control.roughness_um == 1.6
    assert control.face.contains_y_mm == arbor_pedestal_spec.BORE_HEIGHT
    assert 'surface_finish_by_key(SURFACE_FINISHES, "arbor_bore")' in source
    assert "add_surface_finish(" in source
    assert model_toleranced_dimensions(part) == {
        ("BoreProfile", "BoreDia"): "*deviations(BORE_DIA_BAND)"
    }


def test_projected_view_alignment_is_explicit() -> None:
    assert drawing.SHEET_SCALE == (2.0, 1.0)
    assert drawing.FRONT_CENTER == (0.135, 0.125)
    assert drawing.TOP_CENTER == (drawing.FRONT_CENTER[0], 0.215)
    assert drawing.TOP_CENTER[0] == drawing.FRONT_CENTER[0]


def test_part_stamps_make_flexible_material_and_protective_finish() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    assert part.MATERIAL == "Plain Carbon Steel"
    import _config

    config = _config.parts("arbor-pedestal")
    assert config["material"] == "LOW-CARBON STEEL OR GRAY IRON"
    assert config["material_specification"] == "LOW-CARBON STEEL OR GRAY IRON"
    assert config["finish"] == (
        "BLACK JAPAN/ENAMEL; MASK BORE AND FOOT SEAT; OIL BARE MACHINED SURFACES"
    )
    assert config["process"] == "machined from solid stock or casting"
    # Two identical pedestals: the south support plus the north one rotated
    # 180 about Y (build_drive_train_assembly places both).
    assert int(config["quantity"]) == 2
