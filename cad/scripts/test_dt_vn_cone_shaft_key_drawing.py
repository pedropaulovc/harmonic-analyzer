"""Offline source contracts for MHA-DT-VN-71; no native or load-family certificate.

Owner decision C1 keyed, 2026-11-09 (PR #1992): one 1/16 square key in
MHA-DT-04's land-1 keyseat drives the 64T and T030..T120.
"""

from __future__ import annotations

import pytest

import _config
import build_dt_vn_cone_shaft_key as part
import cone_land_key
import draw_dt_vn_cone_shaft_key as drawing
import dt_cone_gear_shaft_spec as shaft
import dt_vn_cone_shaft_key_spec as spec
from _drawing_registry import DRAWINGS_BY_NAME
from _fastener_catalog import FASTENERS
from _machinist_review_mode import MachinistReviewMode
from _mcmaster_98830a511 import LENGTH as STOCK_LENGTH, LENGTH_BAND, SIZE, SIZE_BAND
from _printed_tolerance import printed_band_mm
from _test_stock_recipes import discovered_recipes
from diagnostics import diag_build_98830A511 as recipe
from dt_cone_gear_spec import FACE_WIDTH

_STEM = "dt-vn-cone-shaft-key"
_IN = 25.4


def test_catalogue_identity_is_registered_end_to_end() -> None:
    stock = FASTENERS[_STEM]
    row = _config.parts(_STEM)
    assert part.PART_NAME == _STEM
    assert part.SPEC is stock
    assert stock.skus == tuple(row["supplier_skus"]) == (spec.SKU,) == ("98830A511",)
    assert stock.material == row["material"] == "Plain Carbon Steel"
    assert stock.supplier == row["supplier"] == "McMaster-Carr"
    assert row["number"] == "MHA-DT-VN-71"
    assert row["quantity"] == 1
    assert row["process"] == "purchased"
    assert row["drawing_unit"] == spec.UNIT == "in"
    metadata = discovered_recipes()[spec.SKU]
    assert metadata.module == recipe.__name__
    assert getattr(recipe, metadata.callable_name) is recipe.build_98830A511
    assert metadata.threaded is False


def test_the_key_is_not_another_identitys_sku() -> None:
    """One SKU in two identities would force a Shared identity (AGENTS.md)."""
    for stem, stock in FASTENERS.items():
        if stem != _STEM:
            assert spec.SKU not in stock.skus, stem


def test_section_is_the_undersized_stock_and_the_length_one_cut() -> None:
    """The key is the catalogue's 1/16 undersized square as supplied, the
    section cone_land_key fits; only the .XX cut length is made, from one bar."""
    assert SIZE == pytest.approx(_IN / 16.0)
    assert SIZE_BAND == pytest.approx((0.0, -0.002 * _IN))
    assert (spec.SIZE, spec.SIZE_BAND) == (
        cone_land_key.KEY_SIZE_MM,
        cone_land_key.KEY_STOCK_BAND,
    )
    assert (spec.SIZE, spec.SIZE_BAND) == (SIZE, SIZE_BAND)
    assert spec.LENGTH == cone_land_key.KEY_LENGTH_MM
    assert spec.LENGTH_PLACES == 2
    assert spec.LENGTH / _IN == pytest.approx(round(spec.LENGTH / _IN, 2), abs=1e-9)
    assert spec.LENGTH < STOCK_LENGTH + LENGTH_BAND[1]


def test_key_lies_on_land_1_driving_the_64t_through_t030_short_of_t024() -> None:
    """The square south end stands half a keyseat width (the end mill's
    radius) north of the collar; across the .XX length band the north end
    stays short of T024, which rides land 2's flat, and keeps more than half
    of T030's face on the key."""
    assert spec.END_SET_MM == pytest.approx(cone_land_key.KEYSEAT_WIDTH_MM / 2.0)
    assert spec.FLOOR_OFFSET_MM == cone_land_key.KEYSEAT_FLOOR_OFFSET_MM
    band = printed_band_mm(spec.LENGTH_PLACES, unit=spec.UNIT)
    south = shaft.COLLAR_END_STATION + spec.END_SET_MM
    north = south + spec.LENGTH
    t030_south, _ = (shaft.FRONT_STUB + face for face in shaft.gear_faces(15))
    t024_south, _ = (shaft.FRONT_STUB + face for face in shaft.gear_faces(16))
    assert shaft.KEYED_LAND == 1
    assert south < shaft.FRONT_STUB + shaft.gear_faces(0)[0]  # inside the 64T
    assert north <= shaft.SECTION_ENDS[shaft.KEYED_LAND]
    assert north + band < t024_south
    assert north - band > t030_south + FACE_WIDTH / 2.0


def test_purchased_sheet_has_the_actual_source_marks_and_cli_stem(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sheet = DRAWINGS_BY_NAME["dt_vn_cone_shaft_key"]
    assert drawing.SPEC is sheet
    assert drawing.MACHINIST_REVIEW is MachinistReviewMode.ENFORCE
    assert sheet.source.stem == sheet.artifact_stem == part.PART_NAME
    assert sheet.script.name == "draw_dt_vn_cone_shaft_key.py"
    kept = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP)
    assert kept == {
        name for names in spec.DRAWING_DIMENSIONS.values() for name in names
    }
    assert set(spec.STOCK_FRACTION_DIMENSIONS) == spec.DRAWING_DIMENSIONS["KeyProfile"]
    monkeypatch.setattr("sys.argv", [str(sheet.script), _STEM])
    assert drawing._parse_args().part == _STEM


def test_end_view_width_text_stands_outside_its_extension_lines() -> None:
    """PR #2331 head 7f1dedc machinist review (r1-r3, clarity): centred on the
    3.2 mm square, the stacked (1/16") width was struck by its dimension line
    and both extension lines.  Its text centre stands below the square by more
    than half the stacked fraction's ~9 mm render height, above the note, and
    left of the square inside the border."""
    cx, cy = drawing.FRONT_CENTER
    x, y = drawing.FRONT_KEEP["KeyWidth"]
    half_text = 0.0045
    assert y < cy - drawing.HALF_SIZE - half_text - 0.003
    assert y - half_text > drawing.NOTES_XY[1] + 0.005
    assert 0.0127 + 0.007 < x < cx - drawing.HALF_SIZE
