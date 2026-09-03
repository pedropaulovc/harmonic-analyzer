"""Offline contracts for the output-fixture drawing.

The print follows cad/docs/drawing-simplicity-policy.md: a slip-fit brass
collar carries no datums, frames or roughness symbols; its one fit (the
reamed rod bore) rides the model dimension, the collar length and the
cross-hole station are native model dimensions (machinist review
2026-09-02), and its note is one line of mating context.
"""

from __future__ import annotations

from pathlib import Path

import build_output_fixture as part
import draw_output_fixture as drawing
import output_fixture_spec
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


def _source() -> str:
    return Path(drawing.__file__).read_text(encoding="utf-8")


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/output-fixture.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/output-fixture.pdf")
    assert drawing.PNG.as_posix().endswith("/png/output-fixture_drawing.png")
    assert (
        DRAWINGS_BY_NAME["output_fixture"].script
        == Path(drawing.__file__).resolve()
    )


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is output_fixture_spec.DRAWING_DIMENSIONS
    marked = set().union(*output_fixture_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.TOP_KEEP) | set(drawing.FRONT_KEEP)
    assert kept == marked
    assert set(drawing.DIMENSION_CALLOUTS) <= kept


def test_spec_is_the_single_source_of_collar_nominals() -> None:
    # The build consumes the spec nominals directly (codex review #361), and
    # the pure-data spec's tap-drill literal stays locked to the producer table.
    from _holes import TAP_DRILL_MM

    assert part.COLLAR_DIA is output_fixture_spec.COLLAR_DIA
    assert part.COLLAR_HEIGHT is output_fixture_spec.COLLAR_HEIGHT
    assert part.ROD_BORE_DIA is output_fixture_spec.ROD_BORE_DIA
    assert part.CROSS_HOLE_DIA is output_fixture_spec.CROSS_HOLE_DIA
    assert part.CROSS_HOLE_TAP is output_fixture_spec.CROSS_HOLE_TAP
    assert output_fixture_spec.CROSS_HOLE_TAP == "#4-40"
    assert output_fixture_spec.CROSS_HOLE_DIA == TAP_DRILL_MM["#4-40"]


def test_side_view_carries_length_and_cross_hole_station() -> None:
    # Machinist review 2026-09-02: no overall axial length and no station
    # for the cross hole.  Both are native model dimensions now: the Collar
    # extrude depth (named in the build) and the cross-hole sketch's height
    # from the bottom faced end.
    assert "CollarHeightDim" in output_fixture_spec.DRAWING_DIMENSIONS["Collar"]
    assert "CrossHeight" in output_fixture_spec.DRAWING_DIMENSIONS["CrossHoleProfile"]
    build_source = Path(part.__file__).read_text(encoding="utf-8")
    assert 'name_dimensions(adapter, "Collar", ["CollarHeightDim"])' in build_source
    assert "D1@Collar" not in build_source
    keep = drawing.FRONT_KEEP
    assert keep["CollarHeightDim"][0] < drawing.FRONT_CENTER[0]
    assert keep["CrossHeight"][0] > drawing.FRONT_CENTER[0]
    assert keep["CrossHoleDiaDim"][1] < keep["CrossHeight"][1]


def test_notes_are_few_specific_and_never_the_title_block() -> None:
    notes = output_fixture_spec.DRAWING_NOTES
    lines = notes.split("\n")
    assert len(lines) <= 4
    assert "SLIP FIT" in notes
    assert "MHA-044" in notes
    # The ream and the tap instructions ride the callouts, not the notes.
    for banned in (
        "REAM",
        "DRILL",
        "TAP",
        "UOS",
        "DIMENSIONS IN",
        "+/-",
        "+0.03",
        "MAX",
        "RUNOUT",
        "CDA",
        "X.XX",
    ):
        assert banned not in notes, banned
    source = _source()
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source


def test_hole_callouts_state_size_and_process() -> None:
    callouts = drawing.DIMENSION_CALLOUTS
    assert callouts["RodBoreDiaDim"] == "REAM THRU"
    assert callouts["CrossHoleDiaDim"].startswith("DRILL THRU BOTH WALLS")
    assert "TAP #4-40 ENTRY WALL ONLY" in callouts["CrossHoleDiaDim"]
    assert "-2B" not in callouts["CrossHoleDiaDim"]


def test_only_the_reamed_bore_prints_three_decimals() -> None:
    # The slip-fit band rides the MODEL dimension, not a note or callout.
    source = _source()
    assert '{"RodBoreDiaDim": 3}' in source
    assert output_fixture_spec.ROD_BORE_BAND == (0.03, 0.00)
    assert model_toleranced_dimensions(part) == {
        ("RodBoreProfile", "RodBoreDiaDim"): "*deviations(ROD_BORE_BAND)"
    }


def test_print_carries_no_gdt_finish_or_basic_dimensions() -> None:
    source = _source()
    for helper in (
        "add_datum_feature(",
        "add_feature_control_frame(",
        "add_surface_finish(",
        "set_basic_dimension(",
        "project_part_pmi(",
    ):
        assert helper not in source, helper
    assert not hasattr(output_fixture_spec, "GEOMETRIC_TOLERANCES_MM")


def test_hidden_lines_stay_on_in_every_orthographic_view() -> None:
    source = _source()
    assert "for view in (front, top):\n        set_hidden_lines_visible" in source
    assert "set_hidden_lines_removed(adapter, iso)" in source
    assert source.count("set_hidden_lines_removed(") == 1


def test_view_scales_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (3.0, 1.0)
    source = _source()
    assert "scale=(3, 1)" in source
    assert "scale=(2, 1)" in source
    assert output_fixture_spec.END_VIEW_NOTE == "END VIEW SCALE 3:1"



def test_isometric_caption_is_parked_below_the_isometric() -> None:
    caption_x, caption_y = drawing.ISOMETRIC_NOTE_XY
    assert caption_x > drawing.FRONT_CENTER[0] + 0.150
    assert caption_x < drawing.ISO_CENTER[0]
    assert 0.015 < drawing.ISO_CENTER[1] - caption_y < 0.035
    assert 'add_property_linked_note(adapter, "Isometric View Note", *ISOMETRIC_NOTE_XY)' in _source()

def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("output-fixture")
    assert config["material"] == "C36000 free-cutting brass"
    assert config["material"] == config["material_specification"]
    assert "brass" in str(config["material_specification"]).lower()
    assert config["finish"]
    assert int(config["quantity"]) == 1
