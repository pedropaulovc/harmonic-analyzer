"""Offline contracts for the pinion-return-leaf-spring drawing."""

from __future__ import annotations

from pathlib import Path

import pytest

import _config
import build_pinion_spring as spring
import draw_pinion_spring as drawing
import pinion_spring_geometry as geometry
import pinion_spring_spec
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME

_XX_BAND = float(_config.title_block("linear_2pl")["value_in"]) * 25.4
_HOLE_OVERSIZE = float(_config.title_block("drilled_hole")["plus_mm"])
_WEB_TARGET = 2.0  # U27: machined webs >= 2.0 at the printed worst case


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/pinion-spring.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/pinion-spring.pdf")
    assert drawing.PNG.as_posix().endswith("/png/pinion-spring_drawing.png")
    assert DRAWINGS_BY_NAME["pinion_spring"].script == Path(drawing.__file__).resolve()
    assert "draw_pinion_spring.py" in PRECISION_MIGRATED_DRAWINGS


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    assert spring.DRAWING_DIMENSIONS is pinion_spring_spec.DRAWING_DIMENSIONS
    marked = set().union(*pinion_spring_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.TOP_KEEP) | set(drawing.DETAIL_KEEP)
    assert kept == marked
    assert not set(drawing.FRONT_KEEP) & set(drawing.TOP_KEEP)
    assert set(drawing.DIMENSION_CALLOUTS) <= kept
    assert (spring.FOOT_LEN, spring.THICK, spring.WIDTH) == (
        pinion_spring_spec.FOOT_LEN,
        pinion_spring_spec.THICK,
        pinion_spring_spec.WIDTH,
    )


def test_every_formed_feature_carries_the_one_formed_band() -> None:
    # Main's r6 ruling (c): the hand-formed profile prints one place with a
    # +/-0.5 band; the blank's cut features ride the title-block .XX row.
    assert pinion_spring_spec.FORMED_TOLERANCE_MM == 0.5
    assert model_toleranced_dimensions(spring) == {
        ("feature_name", "name"): "FORMED_TOLERANCE_MM"
    }
    formed = pinion_spring_spec.FORMED_DIMENSIONS["SpringProfile"]
    precision = pinion_spring_spec.DRAWING_PRECISION_BY_NAME
    assert {name: precision[name] for name in formed} == dict.fromkeys(formed, 1)
    for name in ("StripWidth", "PadWidth", "PadLen"):
        assert precision[name] == 2


def test_profile_is_baselined_from_the_foots_free_end() -> None:
    # Rule 7: the kink start and the tip locate from the free end, the one
    # feature the maker can put a rule on, never from the model origin.
    source = Path(spring.__file__).read_text(encoding="utf-8")
    assert "KinkStartX" not in source and "FlatTipX" not in source
    kink = pinion_spring_spec.FORMED_DIMENSIONS["SpringProfile"]
    assert {"KinkH", "KinkV", "TipH"} <= kink
    assert set(drawing.DETAIL_KEEP) == {"KinkR", "FlatLen"}
    assert drawing.DETAIL_SCALE == (5, 1)


def test_pad_webs_clear_two_millimetres_at_the_printed_worst_case() -> None:
    radius = (geometry.HOLE_DIA + _HOLE_OVERSIZE) / 2.0
    width_min = geometry.PAD_WIDTH - _XX_BAND
    across = geometry.PAD_WIDTH / 2.0  # hole from the pad's lower edge
    side_near = across - _XX_BAND - radius
    side_far = width_min - (across + _XX_BAND) - radius
    end_web = geometry.HOLE_FROM_END - _XX_BAND - radius
    pad_web = (geometry.PAD_LEN - _XX_BAND) - (
        geometry.HOLE_FROM_END + _XX_BAND
    ) - radius
    webs = {"near side": side_near, "far side": side_far, "end": end_web}
    webs["toward the strip"] = pad_web
    assert min(webs.values()) >= _WEB_TARGET, webs


def test_hole_keeps_its_machine_station_as_it_moves_in_from_the_end() -> None:
    # The base's seat is transferred from this hole, and the drive train's
    # screw-head-to-rod corridor keys off it: the foot grows by exactly what
    # the hole moved in, so the hole's distance from the bend is unchanged.
    assert geometry.FOOT_LEN - geometry.HOLE_FROM_END == pytest.approx(34.0 - 3.1)


def test_views_are_projected_and_hidden_lines_removed() -> None:
    assert drawing.TOP_CENTER[0] == drawing.FRONT_CENTER[0]
    assert drawing.TOP_CENTER[1] > drawing.FRONT_CENTER[1]
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "set_hidden_lines_visible" not in source
    assert "add_feature_control_frame" not in source
    assert "add_datum_feature" not in source
    assert 'process="DRILL"' in source
    assert source.count("add_edge_dimension(") == 1  # the two hole locations


def test_notes_carry_no_dimension_and_stay_short() -> None:
    notes = pinion_spring_spec.DRAWING_NOTES
    assert len(notes.splitlines()) <= 4
    assert "TEMPLATE" in notes and "FORM" in notes
    assert "COIL" not in notes
    assert not any(ch.isdigit() for ch in notes)
    assert "+/-" not in "\n".join(drawing.DIMENSION_CALLOUTS.values())


def test_part_stamps_make_critical_drawing_properties() -> None:
    source = Path(spring.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    assert "apply_drawing_precision(adapter, DRAWING_PRECISION)" in source
    spec = _config.parts("pinion-spring")
    assert spec["material"] == spec["material_specification"]
    assert "0.8" in spec["material_specification"]
    assert spec["finish"]
    assert int(spec["quantity"]) == 1
