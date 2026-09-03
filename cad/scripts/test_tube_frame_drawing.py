"""Offline contracts for the tube-frame drawing.

The print follows cad/docs/drawing-simplicity-policy.md: a tube column
carries no datum or frame; its OD band and overall-length tolerance ride the
model dimensions, and its notes are three lines of process fact.
"""

from __future__ import annotations

from pathlib import Path

import build_tube_frame as part
import draw_tube_frame as drawing
import tube_frame_spec
from _drawing_registry import DRAWINGS_BY_NAME


def _source() -> str:
    return Path(drawing.__file__).read_text(encoding="utf-8")


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/tube-frame.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/tube-frame.pdf")
    assert drawing.PNG.as_posix().endswith("/png/tube-frame_drawing.png")
    assert DRAWINGS_BY_NAME["tube_frame"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is tube_frame_spec.DRAWING_DIMENSIONS
    marked = set().union(*tube_frame_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.END_KEEP) | set(drawing.LENGTH_KEEP)
    assert kept == marked
    assert drawing.OUTER_DIA == tube_frame_spec.OUTER_DIA


def test_tube_nominals_are_single_sourced() -> None:
    assert part.OUTER_DIA is tube_frame_spec.OUTER_DIA
    assert part.COLUMN_LENGTH is tube_frame_spec.COLUMN_LENGTH
    assert tube_frame_spec.OUTER_DIA == 25.4
    # 1 in OD, 0.12 in wall -> Ø19.304 bore.
    assert abs(tube_frame_spec.INNER_DIA - 19.304) < 1e-6
    # 2026-09-02 user re-read (ch30 p002: columns end just above the corner
    # bosses): 994.0 overall = 990.7 tube + 3.3 integral dome cap (capped
    # stub top at machine 1044.8, 4.1 above the 1040.7 boss tops).
    assert tube_frame_spec.COLUMN_LENGTH == 994.0
    assert tube_frame_spec.CAP_HEIGHT == 3.3
    assert abs(tube_frame_spec.BODY_LENGTH - 990.7) < 1e-9
    # Full-width spherical cap: R = (a^2 + h^2) / (2h) with a = OD/2.
    assert abs(tube_frame_spec.CAP_SPHERE_RADIUS - 26.08787878787879) < 1e-9


def test_notes_are_few_specific_and_never_the_title_block() -> None:
    notes = tube_frame_spec.DRAWING_NOTES
    lines = notes.split("\n")
    assert len(lines) <= 4
    # Stock allowance, what NOT to machine, and the dome cap: the facts the
    # views cannot carry.
    assert "STOCK OD 25.40 MIN" in notes
    assert "DO NOT MACHINE" in notes
    assert "SR26.09 X 3.3" in notes
    assert "CAPPED END UP" in notes
    for banned in (
        "STEEL TUBE",
        "POLISH",
        "DEBURR",
        "UOS",
        "+/-",
        "TITLE-BLOCK",
        "ASME RULE",
        "CYLINDRICITY",
        "PERPENDICULARITY",
        "BORE",
        "X.XX",
    ):
        assert banned not in notes, banned
    source = _source()
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source


def test_print_carries_no_gdt_finish_or_basic_dimensions() -> None:
    # drawing-simplicity-policy.md rule 3-5: a tube column is not on the GD&T
    # allowlist; the OD band is a size tolerance on the model dimension.
    source = _source()
    for helper in (
        "add_datum_feature(",
        "add_feature_control_frame(",
        "add_surface_finish(",
        "set_basic_dimension(",
        "project_part_pmi(",
    ):
        assert helper not in source, helper
    assert not hasattr(tube_frame_spec, "GEOMETRIC_TOLERANCES_MM")
    assert tube_frame_spec.OUTER_DIA_BAND == (0.00, -0.05)
    assert tube_frame_spec.COLUMN_LENGTH_TOLERANCE_MM == 0.25
    assert "set_dimension_callouts" not in source


def test_hidden_lines_stay_on_in_every_orthographic_view() -> None:
    source = _source()
    assert "for view in (length, end):\n        set_hidden_lines_visible" in source
    assert "set_hidden_lines_removed(" not in source


def test_view_scales_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (1.0, 5.0)
    source = _source()
    assert "scale=(1, 5)" in source
    assert "scale=(2, 1)" in source
    assert tube_frame_spec.END_VIEW_NOTE == "END VIEW SCALE 2:1"
    assert 'add_property_linked_note(adapter, "End View Note"' in source


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("tube-frame")
    assert config["material"] == config["material_specification"]
    assert "ASTM A513 Type 5" in str(config["material"])
    assert "SAE 1020 DOM" in str(config["material"])
    finish = str(config["finish"]).lower()
    assert "od polished ra 1.6" in finish
    assert "corrosion-preventive oil after inspection" in finish
    assert "ends faced" in finish
    assert "id as-procured" in finish
    assert int(config["quantity"]) == 4
