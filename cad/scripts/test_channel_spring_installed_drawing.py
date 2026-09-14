"""Offline contracts for the purchased 9432K31 reference sheet."""

from __future__ import annotations

import math
from pathlib import Path

import channel_spring_installed_notes as notes
import channel_spring_installed_spec as spec
import draw_channel_spring_installed as drawing
from _drawing_registry import DRAWINGS_BY_NAME
from spring_mount_geom import channel_force_n


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/channel-spring-installed.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/channel-spring-installed.pdf")
    assert drawing.PNG.as_posix().endswith("/png/channel-spring-installed_drawing.png")
    assert (
        DRAWINGS_BY_NAME["channel_spring_installed"].script
        == Path(drawing.__file__).resolve()
    )


def test_reference_sheet_has_no_fabrication_dimensions() -> None:
    assert notes.DRAWING_DIMENSIONS == {}
    assert drawing.FRONT_KEEP == drawing.RIGHT_KEEP == drawing.TOP_KEEP == {}


def test_installed_spring_stays_within_catalogue_load_envelope() -> None:
    assert spec.FREE_LENGTH_MM <= spec.INSTALLED_LENGTH_MM <= spec.MAX_LENGTH_MM
    assert channel_force_n(spec.INSTALLED_LENGTH_MM) < spec.MAXIMUM_LOAD_N


def test_two_point_qc_measures_the_catalogue_rate() -> None:
    measured = (channel_force_n(80.0) - channel_force_n(60.0)) / 20.0
    assert math.isclose(measured, spec.SPRING_RATE_N_PER_MM, rel_tol=1e-12)
