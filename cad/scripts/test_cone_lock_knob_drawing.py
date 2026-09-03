"""Offline contracts for the cone-lock-knob drawing."""

from __future__ import annotations

from pathlib import Path

import build_cone_lock_knob as part
import cone_lock_knob_spec
import draw_cone_lock_knob as drawing
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _fastener_catalog import fastener


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/cone-lock-knob.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/cone-lock-knob.pdf")
    assert drawing.PNG.as_posix().endswith("/png/cone-lock-knob_drawing.png")
    assert (
        DRAWINGS_BY_NAME["cone_lock_knob"].script == Path(drawing.__file__).resolve()
    )


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is cone_lock_knob_spec.DRAWING_DIMENSIONS
    marked = set().union(*cone_lock_knob_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.TOP_KEEP)
    assert kept == marked
    assert (
        drawing.WASHER_DIA,
        drawing.WASHER_T,
        drawing.BODY_DIA,
        drawing.BODY_TOP,
        drawing.DOME_R,
        drawing.STUD_LEN,
    ) == (
        cone_lock_knob_spec.WASHER_DIA,
        cone_lock_knob_spec.WASHER_T,
        cone_lock_knob_spec.BODY_DIA,
        cone_lock_knob_spec.BODY_TOP,
        cone_lock_knob_spec.DOME_R,
        cone_lock_knob_spec.STUD_LEN,
    )


def test_stud_nominals_track_the_fastener_catalog() -> None:
    stud = fastener("cone-lock-knob")
    assert cone_lock_knob_spec.STUD_DIA == stud.model_diameter_mm
    assert cone_lock_knob_spec.STUD_LEN == stud.length_mm
    assert cone_lock_knob_spec.STUD_THREAD == stud.thread
    assert drawing.DIMENSION_CALLOUTS["StudDia"].startswith(stud.thread)


def test_notes_are_few_specific_and_never_the_title_block() -> None:
    notes = cone_lock_knob_spec.DRAWING_NOTES
    lines = notes.split("\n")
    assert len(lines) <= 4
    assert "THREAD RELIEF" in notes
    assert "MASK THE THREAD" in notes
    # Setup and tooling are the machinist's call: the "one setup / radius
    # tool" line is gone.  The thread designation rides the stud diameter
    # callout, the plating spec the title block's finish field.
    assert "ONE SETUP" not in notes
    assert "RADIUS TOOL" not in notes
    assert "1/4-20" not in notes
    assert "ASTM" not in notes
    for banned in ("UOS", "DIMENSIONS IN", "+/-", "DATUM", "MHA-", "X.XX"):
        assert banned not in notes, banned
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.072)' in source
    assert "def _manufacturing_notes" not in source


def test_nothing_on_the_knob_is_fitted() -> None:
    # The washer used to carry +/-0.1: an ordinary clamp flange under the
    # title block .XX now, and the model carries no band at all.
    assert not hasattr(cone_lock_knob_spec, "WASHER_THICKNESS_TOLERANCE_MM")
    assert model_toleranced_dimensions(part) == {}


def test_turned_part_is_dimensioned_on_the_elevation() -> None:
    # Policy rule 7: a turned part reads as it sits in the lathe -- every
    # marked dimension on the elevation, the end view never curated (each
    # marked model dimension inserts into ONE view; draw_pivot_shaft).
    assert drawing.TOP_KEEP == {}
    assert set(drawing.FRONT_KEEP) == {
        "StudDia", "WasherDia", "BodyDia", "DomeR", "StudLen", "WasherT", "BodyTop",
    }
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'view_label="top"' not in source
    assert "DisplayAsLinear" not in source  # no unproven display toggles
    # The stud and washer diameters stack below the stud end (stud nearer);
    # the body diameter reads across its straight wall, text on the left;
    # the dome radius is leadered from the upper left.
    assert drawing.FRONT_KEEP["StudDia"][0] == drawing.FRONT_CENTER[0]
    assert drawing.FRONT_KEEP["WasherDia"][0] == drawing.FRONT_CENTER[0]
    assert drawing.FRONT_KEEP["WasherDia"][1] < drawing.FRONT_KEEP["StudDia"][1] < drawing._STUD_END_Y
    assert drawing.FRONT_KEEP["BodyDia"][0] < drawing.FRONT_CENTER[0] - drawing._WASHER_HALF_W
    assert drawing._front_y(drawing.WASHER_T) < drawing.FRONT_KEEP["BodyDia"][1] < drawing._front_y(
        drawing.BODY_TOP - drawing.DOME_R
    )
    assert drawing.FRONT_KEEP["DomeR"][0] >= 0.030
    assert drawing.FRONT_KEEP["DomeR"][1] > drawing._APEX_Y
    # Lengths chain on the right from the washer seat, shortest nearest.
    right = drawing.FRONT_CENTER[0] + drawing._WASHER_HALF_W
    assert right < drawing.FRONT_KEEP["StudLen"][0] < drawing.FRONT_KEEP["WasherT"][0]
    assert drawing.FRONT_KEEP["WasherT"][0] < drawing.FRONT_KEEP["BodyTop"][0]
    assert drawing.FRONT_KEEP["BodyTop"][0] < drawing.OVERALL_TEXT_XY[0] < drawing.ISO_CENTER[0] - 0.030


def test_overall_length_is_a_reference_beside_the_chained_lengths() -> None:
    assert cone_lock_knob_spec.OVERALL_LENGTH == 13.5 + 6.35
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'label="stud end face"' in source
    assert 'label="dome apex flat"' in source
    # add_edge_dimension hands back the late-bound IDisplayDimension; the
    # reference helper wants its IAnnotation (draw_crank_arm precedent).
    assert (
        'set_reference_dimension(\n        adapter,\n'
        '        _early_bound(overall, "IDisplayDimension").GetAnnotation(),\n'
        '        label="overall length",\n    )'
    ) in source


def test_print_carries_no_gdt_finish_or_basic_dimensions() -> None:
    # drawing-simplicity-policy.md rules 3-5: a turned thumb knob is not on
    # the GD&T allowlist and nothing runs on its dome or stud.
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    for helper in (
        "add_datum_feature(",
        "add_feature_control_frame(",
        "add_surface_finish(",
        "set_basic_dimension(",
        "project_part_pmi(",
    ):
        assert helper not in source, helper
    assert not hasattr(cone_lock_knob_spec, "GEOMETRIC_TOLERANCES_MM")
    assert cone_lock_knob_spec.SURFACE_FINISHES == ()
    assert "author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)" in Path(
        part.__file__
    ).read_text(encoding="utf-8")


def test_hidden_lines_stay_on_in_every_orthographic_view() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "for view in (front, top):\n        set_hidden_lines_visible" in source
    assert "set_hidden_lines_removed(adapter, iso)" in source


def test_view_scales_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (3.0, 1.0)
    assert drawing.FRONT_CENTER == (0.100, 0.150)
    assert drawing.TOP_CENTER == (0.100, 0.232)
    assert drawing.ISO_CENTER == (0.220, 0.190)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("scale=(3, 1)") == 3


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    assert "author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)" in source
    import _config

    config = _config.parts("cone-lock-knob")
    assert "12L14" in str(config["material_specification"])
    assert "chrome" in str(config["finish"])
    assert int(config["quantity"]) == 1
