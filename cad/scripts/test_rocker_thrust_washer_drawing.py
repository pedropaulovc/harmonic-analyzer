"""Offline contracts for the rocker-bank thrust washer (MHA-148) drawing."""

from __future__ import annotations

from pathlib import Path

import _config
import build_rocker_thrust_washer as part
import draw_rocker_thrust_washer as drawing
import rocker_thrust_washer_spec as spec
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/rocker-thrust-washer.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/rocker-thrust-washer.pdf")
    assert DRAWINGS_BY_NAME["rocker_thrust_washer"].script == Path(drawing.__file__).resolve()


def test_every_marked_dimension_has_one_view_and_model_places() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP) == marked
    assert not set(drawing.FRONT_KEEP) & set(drawing.RIGHT_KEEP)
    assert {
        (feature, name) for feature, names in spec.DRAWING_PRECISION.items() for name in names
    } == {(feature, name) for feature, names in spec.DRAWING_DIMENSIONS.items() for name in names}


def test_only_the_bore_is_banded() -> None:
    """The end-play leaf is set against this washer, so its thickness sits in
    no datum chain: routine .XX, judged at that grade by the bar clearance
    (test_rocker_bank_layout)."""
    assert model_toleranced_dimensions(part) == {
        ("RingProfile", "BoreDia"): "*deviations(BORE_BAND)",
    }
    assert spec.BORE_BAND[1] == 0.0
    assert spec.BORE_DIA - 6.35 > 0.0


def test_registry_row_is_the_turned_mha_148() -> None:
    row = _config.parts("rocker-thrust-washer")
    assert row["number"] == "MHA-148"
    assert int(row["quantity"]) == 1
    assert "turned" in str(row["process"])
