"""Offline contracts for the purchased 1330K524 reference sheet."""

from __future__ import annotations

from pathlib import Path

import counter_spring_notes as notes
import counter_spring_spec as spec
import draw_counter_spring as drawing
from _drawing_registry import DRAWINGS_BY_NAME
from spring_mount_geom import counter_force_n


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/counter-spring.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/counter-spring.pdf")
    assert drawing.PNG.as_posix().endswith("/png/counter-spring_drawing.png")
    assert DRAWINGS_BY_NAME["counter_spring"].script == Path(drawing.__file__).resolve()


def test_reference_sheet_has_no_fabrication_dimensions() -> None:
    assert notes.DRAWING_DIMENSIONS == {}
    assert drawing.FRONT_KEEP == drawing.RIGHT_KEEP == drawing.TOP_KEEP == {}


def test_installed_spring_stays_within_catalogue_load_envelope() -> None:
    assert spec.FREE_LENGTH_MM <= spec.INSTALLED_LENGTH_MM <= spec.MAX_LENGTH_MM
    assert counter_force_n(spec.INSTALLED_LENGTH_MM) < spec.MAXIMUM_LOAD_N
