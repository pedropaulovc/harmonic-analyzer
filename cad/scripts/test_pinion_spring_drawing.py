"""Offline contracts for the pinion-return-leaf-spring drawing."""

from __future__ import annotations

from pathlib import Path

import pytest

import _config
import build_pinion_spring as spring
import draw_pinion_spring as drawing
import pinion_spring_geometry as geometry
import pinion_spring_section as section
import pinion_spring_spec
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _printed_tolerance import printed_deviations

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
    free = pinion_spring_spec.FORMED_DIMENSIONS[pinion_spring_spec.FREE_FORM_SKETCH]
    assert free == {"FreeKinkH", "FreeKinkV", "FreeTipH"}
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


def test_screw_stands_outboard_east_of_the_back_strap() -> None:
    # 2026-09-24 re-derive: img01's far-left screw is on the DRUM side (east).
    # The base's seat is transferred from this hole: it stands 20.0 east of
    # the pivot bore, the pad and the bend wholly east of the strap flank.
    assert geometry.HOLE_X - geometry.PIVOT_LX == pytest.approx(20.0)
    flank = geometry.PIVOT_LX + geometry.STRAP_HALF_WIDTH
    assert geometry.FOOT_END[0] > geometry.HOLE_X > geometry.FOOT_TAN[0] > flank
    assert geometry.FOOT_END[0] - geometry.HOLE_X == geometry.HOLE_FROM_END
    assert geometry.FOOT_LEN == geometry.PAD_LEN + geometry.FOOT_FLAT


def test_blade_leans_in_to_its_flank_contact() -> None:
    # img04: the crest bears on the east flank about 5 below the arbor; img01
    # reads the blade about 11-13 deg to the flank, leaning in from the foot.
    assert geometry.CONTACT_T == 23.0
    assert 9.0 <= geometry.BLADE_TO_FLANK_DEG <= 13.0
    assert geometry.BLADE_LEAN_DEG > 0.0  # west of vertical, toward the strap
    assert geometry.KINK_START[0] < geometry.BEND_EXIT[0]


def test_free_form_presets_the_crest_into_the_flank() -> None:
    # O2: the part is the installed shape; the maker forms the free shape,
    # whose crest stands PRESET into the parked flank.  The band's low end
    # still leaves a preset.
    assert geometry.PRESET - geometry.FORMED_BAND_MM > 1.0
    assert geometry.FREE_KINK_START[0] < geometry.KINK_START[0]
    assert pinion_spring_spec.FORMED_TOLERANCE_MM == geometry.FORMED_BAND_MM


def test_free_form_prints_from_the_hidden_reference_sketch() -> None:
    # O2 (a): the installed solid plus the FreeForm phantom; the free crest and
    # tip print from the hidden sketch, which the part blanks and the front
    # view shows through the opt-in hidden-sketch curation.
    assert pinion_spring_spec.REFERENCE_SKETCHES == ("FreeForm",)
    build_source = Path(spring.__file__).read_text(encoding="utf-8")
    assert "blank_sketch(adapter, FREE_FORM_SKETCH)" in build_source
    assert 'prefix="Free", construction=True' in build_source
    draw_source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "hidden_sketches.curate_view_dimensions(" in draw_source
    assert {"FreeKinkH", "FreeKinkV", "FreeTipH"} <= set(drawing.FRONT_KEEP)
    assert "FREE FORM" in pinion_spring_spec.DRAWING_NOTES


def test_views_are_projected_and_hidden_lines_removed() -> None:
    assert drawing.TOP_CENTER[0] == drawing.FRONT_CENTER[0]
    assert drawing.TOP_CENTER[1] > drawing.FRONT_CENTER[1]
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "set_hidden_lines_visible" not in source
    assert "add_feature_control_frame" not in source
    assert "add_datum_feature" not in source
    assert "process=HOLE_PROCESS" in source
    assert drawing.HOLE_PROCESS == "#30 DRILL"
    assert geometry.HOLE_DIA == pytest.approx(0.1285 * 25.4, abs=1e-3)  # No. 30 drill
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
    # The title-block cell holds one line (<= 30 characters); the full
    # stock callout stays in the material specification.
    assert len(spec["material"]) <= 30
    assert "17-7 PH" in spec["material"] and "Cond C" in spec["material"]
    assert "0.015 in (0.381 mm)" in spec["material_specification"]
    assert spec["finish"]
    assert int(spec["quantity"]) == 1


def test_registry_names_the_stock_the_section_models() -> None:
    # #859 ruling 4: 17-7 PH Condition C, 0.015 in, McMaster-Carr 2325K19
    # (+/-0.00075 in on the vendor page), sheared 1/4 in wide.  The width is a
    # sheared, .XX-printed dimension, so its band is the title block's.
    spec = _config.parts("pinion-spring")["material_specification"]
    assert "McMaster-Carr 2325K19" in spec and "ASTM A693" in spec
    assert "Condition C" in spec and "+/-0.00075 in" in spec
    assert section.THICK == pytest.approx(0.015 * 25.4)
    assert section.THICK_BAND == pytest.approx((0.00075 * 25.4, -0.00075 * 25.4))
    assert section.WIDTH == pytest.approx(0.25 * 25.4)
    assert printed_deviations(section.WIDTH, section.WIDTH_PLACES) == pytest.approx(
        (-_XX_BAND, _XX_BAND), abs=0.005
    )
    assert pinion_spring_spec.DRAWING_PRECISION_BY_NAME["StripWidth"] == 2
    assert spring.MATERIAL == "AISI 304"  # the library's stainless stand-in


def test_every_inside_radius_meets_the_17_7_ph_bend_minimum() -> None:
    # No 17-7 PH source publishes a Condition C bend radius; the proxy is NASA
    # SP-5089 (1968) Table XXXI, 17-7 PH (STA) 0.012-0.016 in: R 0.13 in.
    # Condition C is less ductile than STA, so the bend trial is still due
    # (cad/docs/tolerance-policy.md).
    proxy = 0.13 * 25.4
    assert min(geometry.R_BEND, geometry.R_KINK) >= proxy - 1e-9
    assert geometry.MIN_INSIDE_BEND_R == pytest.approx(proxy)
    # The larger bend keeps the blade inside O5's 9-13 deg only with the bend
    # starting at the pad's edge.
    assert geometry.FOOT_FLAT == 0.0
