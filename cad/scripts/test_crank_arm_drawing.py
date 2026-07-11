"""Offline contracts for the crank-arm drawing."""

from __future__ import annotations

from pathlib import Path

import draw_crank_arm as drawing
import build_crank_arm as arm
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/crank-arm.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/crank-arm.pdf")
    assert drawing.PNG.as_posix().endswith("/png/crank-arm_drawing.png")
    assert DRAWINGS_BY_NAME["crank_arm"].script == Path(drawing.__file__).resolve()


def test_drawing_keeps_exactly_the_marked_dimension_set() -> None:
    marked = set().union(*arm.DRAWING_DIMENSIONS.values())
    kept = (
        set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP) | set(drawing.TOP_KEEP)
    )
    assert kept == marked
    # A callout can only annotate a dimension the print actually shows.
    assert set(drawing.DIMENSION_CALLOUTS) <= kept


def test_sheet_runs_at_2_to_1_with_1_to_1_isometric() -> None:
    assert drawing.SHEET_SCALE == (2.0, 1.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "scale=(1, 1)" in source  # the isometric override
    assert "ISOMETRIC VIEW SCALE 1:1" in source


def test_notes_use_us_customary_fasteners_and_functional_tolerances() -> None:
    notes = drawing._manufacturing_notes()
    assert "TAPER PIN" in notes
    assert "1:48" in notes
    assert "3/8 IN" in notes
    assert "LINEAR +/-0.25" in notes
    assert "HOLE CENTRES +/-0.10" in notes
    # Pedro 2026-07-10: drawings spec the closest US-customary fastener, not
    # the period British Association series.
    assert "BA" not in notes
    assert "X.XX" not in notes


def test_hole_states_are_annotated() -> None:
    callouts = drawing.DIMENSION_CALLOUTS
    assert callouts["ShaftBoreDia"].startswith("THRU")
    assert callouts["PivotBoreDia"].startswith("THRU")
    assert callouts["PinHoleDia"].startswith("THRU")
    assert callouts["DimpleDia"].startswith("0.5 DEEP")


def test_part_stamps_make_critical_drawing_properties() -> None:
    source = Path(arm.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    spec = _config.parts("crank-arm")
    assert spec["material_specification"]
    assert spec["finish"]
    assert int(spec["quantity"]) == 1
