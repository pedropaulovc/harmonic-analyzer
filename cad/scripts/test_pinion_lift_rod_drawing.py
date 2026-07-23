"""Offline contracts for the pinion-lift-rod drawing."""

from __future__ import annotations

from pathlib import Path

import build_pinion_lift_rod as part
import draw_pinion_lift_rod as drawing
import pinion_lift_rod_spec
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/pinion-lift-rod.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/pinion-lift-rod.pdf")
    assert drawing.PNG.as_posix().endswith("/png/pinion-lift-rod_drawing.png")
    assert (
        DRAWINGS_BY_NAME["pinion_lift_rod"].script == Path(drawing.__file__).resolve()
    )


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is pinion_lift_rod_spec.DRAWING_DIMENSIONS
    marked = set().union(*pinion_lift_rod_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP)
    assert kept == marked
    assert (drawing.ROD_DIA, drawing.ROD_LEN, drawing.CAP_SAG) == (
        pinion_lift_rod_spec.ROD_DIA,
        pinion_lift_rod_spec.ROD_LEN,
        pinion_lift_rod_spec.CAP_SAG,
    )


def test_linked_notes_define_remaining_bearing_rod_operations() -> None:
    notes = pinion_lift_rod_spec.DRAWING_NOTES
    assert drawing.DIMENSION_CALLOUTS["RodDia"] == "+0.00/-0.02"
    # The length tolerance rides the 202.00 dimension, not a detached UOS note
    # (codex machinist review finding).
    assert drawing.RIGHT_CALLOUTS["Depth"] == "+/-0.25"
    assert "LENGTH +/-" not in notes
    # The crown is conveyed as a note (its sketch dims live on the Top plane,
    # outside every placed view): spherical radius consistent with the
    # sagitta/diameter pair, SR controlled, sagitta/OAL reference-only so the
    # dome is not doubly toleranced (codex machinist review finding).
    dome_radius = (
        pinion_lift_rod_spec.ROD_DIA**2 / 4.0 + pinion_lift_rod_spec.CAP_SAG**2
    ) / (2.0 * pinion_lift_rod_spec.CAP_SAG)
    assert round(dome_radius, 2) == pinion_lift_rod_spec.CAP_R == 4.8
    assert f"SR{pinion_lift_rod_spec.CAP_R} +/-0.25" in notes
    assert "CROWN BACK END" in notes
    assert f"{pinion_lift_rod_spec.CAP_SAG} REF PROUD" in notes
    assert "OAL 203.2 REF" in notes
    # The grind note is scoped to the cylindrical OD so it cannot be read as
    # conflicting with the crowned end.
    assert "CYLINDRICAL OD" in notes
    assert "X.XX" not in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source
    assert "def _manufacturing_notes" not in source


def test_native_gdt_controls_rod_form_orientation_and_finish() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("add_datum_feature(") == 1
    datum_a = source[source.index("add_datum_feature(") :]
    datum_a = datum_a[: datum_a.index("    )")]
    assert "edge_xy=end_top" in datum_a
    assert "symbol_xy=(FRONT_CENTER[0], FRONT_CENTER[1] + 0.024)" in datum_a
    assert 'datum="A"' in datum_a
    assert 'label="lift rod axis"' in datum_a
    assert "position_tolerance_m=0.001" in datum_a
    assert source.count("position_tolerance_m=0.001") == 1
    assert source.count("add_feature_control_frame(") == 2
    assert source.count('characteristic="cylindricity"') == 1
    # Only the flat front end -- the crowned back end carries no
    # face-orientation control.
    assert source.count('characteristic="perpendicularity"') == 1
    assert source.count("add_surface_finish(") == 1


def test_view_scales_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (1.0, 1.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "scale=(2, 1)" in source  # end view 2:1
    assert "scale=(1, 1)" in source  # side view true scale
    assert "scale=(1, 2)" in source  # iso reduced so the long rod clears
    assert pinion_lift_rod_spec.END_VIEW_NOTE == "END VIEW SCALE 2:1"
    assert 'add_property_linked_note(adapter, "End View Note"' in source


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("pinion-lift-rod")
    assert "1018" in str(config["material_specification"])
    assert config["finish"]
    assert int(config["quantity"]) == 1
