"""Offline contracts for the magnifying-vertical-rod drawing.

The print follows cad/docs/drawing-simplicity-policy.md: a plain domed rod is
not on the GD&T allowlist and it is lock-mated in service, so it carries no
datum, frame, roughness or basic dimension; the overall length is the real
tip-to-tip axis dimension (controlling, two places), the dome radius carries
the end instruction, and the one note is the stock licence.
"""

from __future__ import annotations

from pathlib import Path

import build_magnifying_vertical_rod as part
import draw_magnifying_vertical_rod as drawing
import magnifying_vertical_rod_spec
from _drawing_registry import DRAWINGS_BY_NAME


def _source() -> str:
    return Path(drawing.__file__).read_text(encoding="utf-8")


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/magnifying-vertical-rod.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/magnifying-vertical-rod.pdf")
    assert drawing.PNG.as_posix().endswith("/png/magnifying-vertical-rod_drawing.png")
    assert (
        DRAWINGS_BY_NAME["magnifying_vertical_rod"].script
        == Path(drawing.__file__).resolve()
    )


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    assert part.DRAWING_DIMENSIONS is magnifying_vertical_rod_spec.DRAWING_DIMENSIONS
    marked = set().union(*magnifying_vertical_rod_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP)
    assert kept == marked == {"RodOverall", "DomeRadius"}
    # A callout can only annotate a dimension the print actually shows.
    assert set(drawing.DIMENSION_CALLOUTS) <= kept
    assert (drawing.ROD_DIA, drawing.ROD_LENGTH) == (
        magnifying_vertical_rod_spec.ROD_DIA,
        magnifying_vertical_rod_spec.ROD_LENGTH,
    )
    assert (magnifying_vertical_rod_spec.ROD_DIA, magnifying_vertical_rod_spec.ROD_LENGTH) == (
        5.0,
        150.0,
    )


def test_overall_length_is_the_axis_line_driving_dimension() -> None:
    # The profile's axis line runs tip to tip, so its length dim IS the overall
    # (150.00, controlling), driven by the RodLength global; the right dome
    # centre is held on the axis by a relation and fixed by the radius.
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "await adapter.add_sketch_dimension(axis_line, None, \"linear\", ROD_LENGTH)" in source
    assert "profile.record(\"RodOverall\", '\"RodLength\"')" in source
    assert "RightDomeCentre" not in source
    assert 'f"{cap_right}.center", "origin", "horizontal_points"' in source
    # Shown conventionally under the side view, between the two tips, with a
    # longitudinal centreline; the dome callout no longer restates the OD.
    assert drawing.FRONT_KEEP["RodOverall"][1] < drawing.FRONT_CENTER[1]
    assert drawing.DIMENSION_CALLOUTS == {"DomeRadius": "FULL R, BOTH ENDS"}
    assert "add_view_centerline(" in _source()
    assert drawing.AXIS_FACE_PICK == drawing.FRONT_CENTER


def test_notes_are_the_stock_licence_only() -> None:
    notes = magnifying_vertical_rod_spec.DRAWING_NOTES
    lines = notes.split("\n")
    assert len(lines) == 1
    assert notes == "Ø5.0 ROUND BAR STOCK; OD OK AS RECEIVED."  # Lipton's licence
    # The overall is a view dimension and the dome rides its leader, so neither
    # is repeated here; no roughness, nothing the title block says, no design
    # narration.
    for banned in (
        "OVERALL",
        "DOME",
        "Ra ",
        "SLIDE",
        "FIXTURE",
        "BRASS",
        "C36000",
        "UOS",
        "DIMENSIONS IN",
        "+/-",
        "DATUM",
        "MHA-",
        "DEBURR",
        "BREAK SHARP",
        "X.XX",
    ):
        assert banned not in notes, banned
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in _source()


def test_view_scales_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (1.0, 1.0)
    source = _source()
    assert "scale=(1, 1)" in source  # the front side view
    assert "scale=(4, 1)" in source  # the end view
    assert drawing.ISO_SCALE == (1, 2)
    assert "scale=ISO_SCALE" in source
    assert magnifying_vertical_rod_spec.END_VIEW_NOTE == "END VIEW SCALE 4:1"
    assert magnifying_vertical_rod_spec.ISO_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:2"
    assert 'add_property_linked_note(adapter, "End View Note"' in source
    assert 'add_property_linked_note(adapter, "Iso View Note"' in source


def test_print_carries_no_gdt_finish_or_basic_dimensions() -> None:
    # A smooth hemispherical-ended capsule exposes no selectable edge, and the
    # policy wants none of these on a plain rod anyway.
    source = _source()
    for helper in (
        "add_datum_feature(",
        "add_feature_control_frame(",
        "add_surface_finish(",
        "set_basic_dimension(",
        "project_part_pmi(",
        "add_edge_dimension(",
    ):
        assert helper not in source, helper
    assert not hasattr(magnifying_vertical_rod_spec, "GEOMETRIC_TOLERANCES_MM")
    assert not hasattr(magnifying_vertical_rod_spec, "SURFACE_FINISHES")


def test_hidden_lines_stay_on_in_every_orthographic_view() -> None:
    source = _source()
    assert "for view in (front, right):\n        set_hidden_lines_visible" in source
    assert "set_hidden_lines_removed(adapter, iso)" in source


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("magnifying-vertical-rod")
    assert config["material"] == config["material_specification"]
    assert config["finish"]
    assert int(config["quantity"]) == 1
