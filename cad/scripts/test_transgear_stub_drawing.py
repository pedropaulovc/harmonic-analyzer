"""Offline contracts for the transgear-stub drawing."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

import _fit_limits
import build_transgear_stub as part
import draw_transgear_stub as drawing
import transgear_stub_spec
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/transgear-stub.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/transgear-stub.pdf")
    assert drawing.PNG.as_posix().endswith("/png/transgear-stub_drawing.png")
    assert (
        DRAWINGS_BY_NAME["transgear_stub"].script == Path(drawing.__file__).resolve()
    )


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is transgear_stub_spec.DRAWING_DIMENSIONS
    marked = set().union(*transgear_stub_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP)
    assert kept == marked
    nominals = (
        transgear_stub_spec.BASE_DIA,
        transgear_stub_spec.BASE_LEN,
        transgear_stub_spec.SEAT_DIA,
        transgear_stub_spec.SEAT_LEN,
        transgear_stub_spec.COLLAR_DIA,
        transgear_stub_spec.COLLAR_LEN,
    )
    assert (
        part.BASE_DIA,
        part.BASE_LEN,
        part.SEAT_DIA,
        part.SEAT_LEN,
        part.COLLAR_DIA,
        part.COLLAR_LEN,
    ) == nominals
    # BASE_DIA left this tuple with the hand-authored datum tag: the drawing
    # no longer types anything from it (datum A comes from the model PMI spec).
    assert (
        drawing.BASE_LEN,
        drawing.SEAT_DIA,
        drawing.SEAT_LEN,
        drawing.COLLAR_DIA,
        drawing.COLLAR_LEN,
    ) == nominals[1:]
    # The base is machine-standard 3/8" stock carried in mm.
    assert transgear_stub_spec.BASE_DIA == 0.375 * transgear_stub_spec.MM_PER_IN


def test_brass_face_regions_require_nonzero_axial_span_proof() -> None:
    collar_start = transgear_stub_spec.BASE_LEN + transgear_stub_spec.SEAT_LEN
    cap_start = collar_start + transgear_stub_spec.COLLAR_LEN
    cap_end = cap_start + transgear_stub_spec.CAP_LEN
    classify = part._brass_region_from_stations
    prove = part._brass_span_evidence_region

    assert classify((0.0, collar_start), collar_start, cap_start) is None
    assert classify((collar_start,), collar_start, cap_start) == "collar"
    assert prove((collar_start,), collar_start, cap_start, cap_end) is None
    assert classify((cap_start,), collar_start, cap_start) == "cap"
    assert prove((cap_start,), collar_start, cap_start, cap_end) is None

    collar_span = (collar_start, cap_start)
    assert classify(collar_span, collar_start, cap_start) == "collar"
    assert prove(collar_span, collar_start, cap_start, cap_end) == "collar"
    cap_span = (cap_start, cap_end)
    assert classify(cap_span, collar_start, cap_start) == "cap"
    assert prove(cap_span, collar_start, cap_start, cap_end) == "cap"

    assert classify((), collar_start, cap_start) is None
    assert prove((), collar_start, cap_start, cap_end) is None


def test_cap_slot_volume_uses_the_cylindrical_intersection() -> None:
    full_circle = part._circular_strip_area_mm2(
        transgear_stub_spec.CAP_DIA, transgear_stub_spec.CAP_DIA
    )
    assert full_circle == pytest.approx(
        math.pi * (transgear_stub_spec.CAP_DIA / 2.0) ** 2
    )
    strip = part._circular_strip_area_mm2(
        transgear_stub_spec.CAP_DIA, transgear_stub_spec.CAP_SLOT_W
    )
    assert 0.0 < strip < (
        transgear_stub_spec.CAP_DIA * transgear_stub_spec.CAP_SLOT_W
    )
    for invalid_width in (0.0, -0.1, transgear_stub_spec.CAP_DIA + 0.1):
        with pytest.raises(ValueError, match="strip width"):
            part._circular_strip_area_mm2(
                transgear_stub_spec.CAP_DIA, invalid_width
            )


def test_lands_carry_true_diametric_dimensions() -> None:
    """The revolve profile dims the lathe-facing set: three doubled
    centerline (diameter) dims plus the three land lengths -- never the
    radius/step chain a rectilinear-chain recipe would emit."""
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert source.count("await add_diametric_linear_dimension(") == 1
    assert "swDiametricLinearDimension" in source
    imports = source.split("PART_NAME =", 1)[0]
    assert "define_rectilinear_chain" not in imports  # not even imported
    marked = transgear_stub_spec.DRAWING_DIMENSIONS["StubProfile"]
    assert {"BaseDia", "SeatDia", "CollarDia"} <= marked
    assert {"BaseLength", "SeatLength", "CollarLength"} <= marked


def test_diameter_bands_are_toleranced_on_the_model_not_the_sheet() -> None:
    """The fit bands must reach the print as NATIVE dimension tolerances.

    A band spelled as callout text (``SetText``) is frozen: SolidWorks prints it
    verbatim beside a live numeral and never re-renders it, so the mm->inch flip
    in issue #290 would leave "+0.00/-0.02" reading as inches. Tolerancing the
    model dimension instead is the only path that survives a unit change, so the
    sheet must carry NO override for either diameter.
    """
    assert drawing.DIMENSION_CALLOUTS == {}
    # The seat is the shared ground-shaft class, not a value peculiar to this
    # stud -- assert the IDENTITY so a local retype cannot silently fork it.
    assert transgear_stub_spec.SEAT_DIA_BAND is _fit_limits.SHAFT_H
    assert transgear_stub_spec.BASE_DIA_BAND == (0.000, -0.050)
    assert model_toleranced_dimensions(part) == {
        ("StubProfile", "BaseDia"): "*deviations(BASE_DIA_BAND)",
        ("StubProfile", "SeatDia"): "*deviations(SEAT_DIA_BAND)",
    }


def test_linked_notes() -> None:
    notes = transgear_stub_spec.DRAWING_NOTES
    # 3/8" conversions display all three decimals so the view matches the note.
    assert drawing.DIMENSION_PRECISION == {"BaseDia": 3}
    # Deburr/edge-break is a title-block note; repeating it here would duplicate it.
    assert "DEBURR" not in notes
    assert "ONE SETUP" in notes
    assert "X.XX" not in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source
    assert "def _manufacturing_notes" not in source


def test_native_gdt_controls_seat_form_runout_and_finish() -> None:
    """GD&T identity lives in the spec's PMI rows; the sheet only imports it."""
    from transgear_stub_spec import GEOMETRIC_CONTROLS, PART_DATUMS

    by_key = {control.key: control for control in GEOMETRIC_CONTROLS}
    assert set(by_key) == {"seat_cylindricity", "seat_runout"}
    assert by_key["seat_cylindricity"].characteristic == "cylindricity"
    assert by_key["seat_cylindricity"].tolerance == "0.01"
    assert by_key["seat_runout"].characteristic == "circular_runout"
    assert by_key["seat_runout"].tolerance == "0.03"
    assert by_key["seat_runout"].datums == ("A",)
    seat_y = transgear_stub_spec.BASE_LEN + transgear_stub_spec.SEAT_LEN / 2.0
    assert all(control.face.contains_y_mm == seat_y for control in by_key.values())
    assert tuple(datum.letter for datum in PART_DATUMS) == ("A",)

    part_source = Path(part.__file__).read_text(encoding="utf-8")
    assert "author_part_pmi(" in part_source
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "project_part_pmi(" in source
    assert "controls=GEOMETRIC_CONTROLS" in source
    assert "add_feature_control_frame(" not in source
    assert "add_datum_feature(" not in source
    assert source.count("add_surface_finish(") == 1


def test_view_scales_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (4.0, 1.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    # All three views read at the sheet's own 4:1 -- no blow-up note needed.
    assert source.count("scale=(4, 1)") == 3


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("transgear-stub")
    assert "1018" in str(config["material_specification"])
    assert config["finish"]
    assert int(config["quantity"]) == 1


def test_surface_finish_is_part_owned_authored_and_consumed() -> None:
    (control,) = transgear_stub_spec.SURFACE_FINISHES
    assert control.key == "gear_seat"
    assert control.roughness_um == 1.6
    assert control.face.diameter_mm == transgear_stub_spec.SEAT_DIA
    assert control.face.contains_y_mm == (
        transgear_stub_spec.BASE_LEN + transgear_stub_spec.SEAT_LEN / 2.0
    )
    part_source = "".join(Path(part.__file__).read_text(encoding="utf-8").split())
    assert "surface_finishes=SURFACE_FINISHES" in part_source
    sheet_source = "".join(Path(drawing.__file__).read_text(encoding="utf-8").split())
    assert (
        'control=surface_finish_by_key(SURFACE_FINISHES,"gear_seat")'
        in sheet_source
    )
    assert "roughness_ra=" not in sheet_source
