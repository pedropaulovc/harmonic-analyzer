"""Offline contracts for the cylinder-bank thrust washer (MHA-121) drawing."""

from __future__ import annotations

from pathlib import Path

import build_cylinder_end_disc as part
import cylinder_end_disc_spec as spec
import draw_cylinder_end_disc as drawing
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/cylinder-end-disc.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/cylinder-end-disc.pdf")
    assert DRAWINGS_BY_NAME["cylinder_end_disc"].script == Path(drawing.__file__).resolve()


def test_every_marked_dimension_has_one_view_and_model_places() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP) == marked
    assert not set(drawing.FRONT_KEEP) & set(drawing.RIGHT_KEEP)
    assert {
        (feature, name) for feature, names in spec.DRAWING_PRECISION.items() for name in names
    } == {(feature, name) for feature, names in spec.DRAWING_DIMENSIONS.items() for name in names}


def test_thickness_is_held_because_it_sits_in_the_bank_datum_chain() -> None:
    import cylinder_bank_layout as bank

    assert bank.DATUM_CHAIN_STACK["back washer thickness"] == spec.WASHER_THICK_TOLERANCE_MM
    assert model_toleranced_dimensions(part) == {
        ("RingProfile", "BoreDia"): "*deviations(WASHER_BORE_BAND)",
        ("Disc", "DiscThick"): "WASHER_THICK_TOLERANCE_MM",
    }
    # The bore can never close onto the O9.525 arbor.
    assert spec.WASHER_BORE_BAND[1] == 0.0
    assert spec.WASHER_BORE - 9.525 > 0.0
