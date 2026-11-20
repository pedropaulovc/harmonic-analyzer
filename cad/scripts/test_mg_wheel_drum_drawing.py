"""Offline contracts for the magnifying-wheel drum (MHA-MG-10) drawing."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

import _config
import build_mg_wheel_drum as part
import draw_mg_wheel_drum as drawing
import mg_magnifying_wheel_geom as wheel_geom
import mg_wheel_drum_geom
import mg_wheel_drum_spec as spec
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/mg-wheel-drum.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/mg-wheel-drum.pdf")
    assert DRAWINGS_BY_NAME["mg_wheel_drum"].script == Path(drawing.__file__).resolve()


def test_dimension_transfer_uses_shared_helper() -> None:
    from _drawing_dimensions import move_model_dimension

    assert drawing.move_model_dimension is move_model_dimension


def test_every_marked_dimension_has_one_view_and_model_places() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP) == marked
    assert not set(drawing.FRONT_KEEP) & set(drawing.RIGHT_KEEP)
    assert set(drawing.DIMENSION_CALLOUTS) <= marked
    assert {
        (feature, name)
        for feature, names in spec.DRAWING_PRECISION.items()
        for name in names
    } == {
        (feature, name)
        for feature, names in spec.DRAWING_DIMENSIONS.items()
        for name in names
    }
    assert drawing.DRAWING_PRECISION_BY_NAME == {
        name: digits
        for names in spec.DRAWING_PRECISION.values()
        for name, digits in names.items()
    }


def test_every_size_carries_its_band_on_the_model() -> None:
    # The O.D. and the length have no fit band: they take the title block's
    # .XX and .XXX rows.
    assert model_toleranced_dimensions(part) == {
        ("RingProfile", "DrumBore"): "*deviations(DRUM_BORE_BAND)",
    }
    # drawing-guidelines.md rule 17 (walls and webs) at the worst printed
    # corner: the O.D. printed .77 -.01 over the .4990 +.0005 reamed bore.
    assert mg_wheel_drum_geom.WALL_WORST == pytest.approx((0.76 - 0.4995) * 25.4 / 2.0)
    assert mg_wheel_drum_geom.WALL_WORST >= mg_wheel_drum_geom.MIN_WALL


def test_drum_presses_on_the_wheel_spigot_never_proud() -> None:
    # Reamed bore, made first; the spigot is turned to the stated interference in it.
    assert spec.DRUM_BORE == pytest.approx(0.499 * 25.4)
    assert spec.DRUM_BORE == wheel_geom.SPIGOT_DIA
    assert wheel_geom.DRUM_PRESS == pytest.approx((0.0002 * 25.4, 0.0013 * 25.4))
    # Both lengths on the title block's .XXX row, each model inside its
    # printed limits: the longest drum still keeps its face under the
    # shortest spigot's, so it is never proud.
    assert spec.DRUM_LEN < wheel_geom.SPIGOT_LEN
    assert wheel_geom.DRUM_RECESS == pytest.approx((0.0, 0.020 * 25.4))
    assert (
        part.V_DRUM
        == math.pi
        * ((spec.DRUM_OD / 2.0) ** 2 - (spec.DRUM_BORE / 2.0) ** 2)
        * spec.DRUM_LEN
    )


def test_registry_row() -> None:
    row = _config.parts("mg-wheel-drum")
    assert row["number"] == "MHA-MG-10"
    assert int(row["quantity"]) == 1
    assert "C36000" in str(row["material_specification"])
    assert part.MATERIAL == "Brass"


def test_pressed_bore_carries_no_finish_and_no_gdt() -> None:
    # drawing-guidelines.md rule 6: a pressed bore neither runs nor slides.
    assert spec.SURFACE_FINISHES == ()
