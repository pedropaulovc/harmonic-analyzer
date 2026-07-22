"""Offline contracts for the transgear-stub drawing."""

from __future__ import annotations

from pathlib import Path

import build_transgear_stub as part
import draw_transgear_stub as drawing
import transgear_stub_spec
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
    assert (
        drawing.BASE_DIA,
        drawing.BASE_LEN,
        drawing.SEAT_DIA,
        drawing.SEAT_LEN,
        drawing.COLLAR_DIA,
        drawing.COLLAR_LEN,
    ) == nominals
    # The base is machine-standard 3/8" stock carried in mm.
    assert transgear_stub_spec.BASE_DIA == 0.375 * transgear_stub_spec.MM_PER_IN


def test_lands_carry_true_diametric_dimensions() -> None:
    """The revolve profile dims the lathe-facing set: three doubled
    centerline (diameter) dims plus the three land lengths -- never the
    radius/step chain a rectilinear-chain recipe would emit."""
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert source.count("await _diametric_dim(") == 1  # the one loop chokepoint
    assert "swDiametricLinearDimension" in source
    imports = source.split("PART_NAME =", 1)[0]
    assert "define_rectilinear_chain" not in imports  # not even imported
    marked = transgear_stub_spec.DRAWING_DIMENSIONS["StubProfile"]
    assert {"BaseDia", "SeatDia", "CollarDia"} <= marked
    assert {"BaseLength", "SeatLength", "CollarLength"} <= marked


def test_linked_notes_and_fit_callouts() -> None:
    notes = transgear_stub_spec.DRAWING_NOTES
    assert drawing.DIMENSION_CALLOUTS["SeatDia"] == "+0.00/-0.02"
    assert drawing.DIMENSION_CALLOUTS["BaseDia"] == "+0.00/-0.05"
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
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("add_datum_feature(") == 1
    assert source.count("position_tolerance_m=0.003") == 1
    assert source.count("add_feature_control_frame(") == 2
    assert 'characteristic="cylindricity"' in source
    assert 'characteristic="circular_runout"' in source
    assert 'datums=("A",)' in source
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
