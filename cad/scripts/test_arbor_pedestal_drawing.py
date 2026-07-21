"""Offline contracts for the arbor-pedestal drawing."""

from __future__ import annotations

from pathlib import Path

import arbor_pedestal_spec
import build_arbor_pedestal as part
import draw_arbor_pedestal as drawing
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/arbor-pedestal.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/arbor-pedestal.pdf")
    assert drawing.PNG.as_posix().endswith("/png/arbor-pedestal_drawing.png")
    assert (
        DRAWINGS_BY_NAME["arbor_pedestal"].script
        == Path(drawing.__file__).resolve()
    )


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is arbor_pedestal_spec.DRAWING_DIMENSIONS
    marked = set().union(*arbor_pedestal_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.TOP_KEEP)
    assert kept == marked
    assert marked == {
        "Width", "Depth", "FootHt", "BoreDia", "DomeDia"
    }


def test_arbor_bore_closes_the_configured_running_fit() -> None:
    import _config

    assert round(arbor_pedestal_spec.BORE_DIA, 3) == 9.525
    assert drawing.DIMENSION_CALLOUTS["BoreDia"] == "+0.055/+0.025 THRU"
    assert "BoreHeight" not in drawing.DIMENSION_CALLOUTS
    assert drawing.DIMENSION_CALLOUTS["Depth"] == "+/-0.10"
    assert drawing.DIMENSION_PRECISION["BoreDia"] == 3
    assert "ARBOR BORE LIMITS" not in arbor_pedestal_spec.DRAWING_NOTES
    shaft_limits = (9.505, 9.525)
    bore_limits = (9.550, 9.580)
    clearances = (
        bore_limits[0] - shaft_limits[1],
        bore_limits[1] - shaft_limits[0],
    )
    expected = tuple(_config.fit("shaft_in_bushing", "diametral_clearance_mm"))
    assert tuple(round(value, 3) for value in clearances) == expected


def test_notes_specify_part_requirements_without_title_block_duplicates() -> None:
    notes = arbor_pedestal_spec.DRAWING_NOTES
    assert "MATING ARBOR LIMITS DIA 9.505-9.525" in notes
    assert "STRAP 10.00 +/-0.10 THICK" in notes
    assert "MATERIAL" not in notes
    assert "JAPANNED" not in notes
    assert "DATUM A" in notes
    assert "X.XX" not in notes
    assert "BREAK EDGES" not in notes
    assert "MACHINE FROM CONTINUOUS-CAST STOCK" in notes
    assert "DATUM B IS LEFT FOOT SIDE FACE SHOWN" in notes
    assert "2X STRAIGHT FLANKS RUN FROM TOP CORNERS" in notes
    assert "NO TANGENCY" in notes
    assert "BOXED 12.00 LOCATES BOTH BORE AND FLANGE-HOLE AXES" in notes
    assert "STRAP NEAR FACE 6.00 +/-0.10 FROM DATUM D" in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source
    assert "add_native_hole_callout(" in source
    assert 'label="flange-hole location from datum D"' in source


def test_bore_dome_and_mounting_hole_have_inspectable_gdt() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'datum="A"' in source
    assert 'datum="B"' in source
    assert 'datum="D"' in source
    assert 'characteristic="position"' in source
    assert 'characteristic="profile_surface"' in source
    assert 'quantity="CROWN ONLY"' in source
    assert 'characteristic="perpendicularity"' not in source
    assert source.count("_add_circle_basic(") == 4  # helper plus three calls
    assert 'orientation="horizontal"' in source
    assert 'orientation="vertical"' in source
    assert "for index in (1, 2):" in source
    assert "if result != 0:" in source
    assert 'label="flange-hole true position"' in source
    assert 'roughness_ra="1.6"' in source
    common_source = Path(drawing.__file__).with_name("_drawing_common.py").read_text(
        encoding="utf-8"
    )
    assert 'display.SetText(_DIMENSION_TEXT_CALLOUT_BELOW, "")' in common_source
    assert "BASIC dimension retained below-text" in common_source
    notes = arbor_pedestal_spec.DRAWING_NOTES
    assert "CYLINDRICAL ZONE" not in notes
    assert "FINISH RA" not in notes


def test_view_scales_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (2.0, 1.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("scale=(2, 1)") == 3  # elevation + plan + pictorial


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("arbor-pedestal")
    assert "A48" in str(config["material_specification"])
    assert "A48" in str(config["material"])
    assert config["finish"]
    assert int(config["quantity"]) == 1
