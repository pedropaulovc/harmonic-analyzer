"""Offline source contracts for MHA-DT-VN-71; no native or load-family certificate.

Owner decision C1 keyed, 2026-11-09 (PR #1992): one 1/16 square key in
MHA-DT-04's land-1 keyseat drives the 64T and T030..T120.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

import _config
import build_dt_vn_cone_shaft_key as part
import cone_land_key
import cone_tip_cluster
import draw_dt_vn_cone_shaft_key as drawing
import dt_cone_gear_shaft_spec as shaft
import dt_cone_gear_stack
import dt_vn_cone_shaft_key_spec as spec
from _drawing_registry import DRAWINGS_BY_NAME
from _fastener_catalog import FASTENERS
from _machinist_review_mode import MachinistReviewMode
from _mcmaster_98830a511 import LENGTH as STOCK_LENGTH, LENGTH_BAND, SIZE, SIZE_BAND
from _printed_tolerance import printed_band_mm
from _test_stock_recipes import discovered_recipes
from diagnostics import diag_build_98830A511 as recipe
from dt_cone_gear_spec import FACE_WIDTH, FACE_WIDTH_BAND

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
    """The square south end rests on the keyseat end radius's centre line,
    .05 (.XX on MHA-DT-04) north of the collar, the radius then clear of the
    collar's 64T seat (Codjiflo #2331 4521933063); across that band and the
    .XX length band the south end stays under the 64T, the north end stays
    short of T024, which rides land 2's flat, and keeps more than half of
    T030's face on the key."""
    assert spec.END_SET_MM == cone_land_key.KEY_END_SET_MM
    assert spec.END_SET_MM > cone_land_key.KEYSEAT_WIDTH_MM / 2.0
    assert spec.FLOOR_OFFSET_MM == cone_land_key.KEYSEAT_FLOOR_OFFSET_MM
    band = printed_band_mm(spec.LENGTH_PLACES, unit=spec.UNIT)
    set_band = printed_band_mm(cone_land_key.KEY_END_SET_PLACES, unit=spec.UNIT)
    south = shaft.COLLAR_END_STATION + spec.END_SET_MM
    north = south + spec.LENGTH
    t030_south, _ = (shaft.FRONT_STUB + face for face in shaft.gear_faces(15))
    t024_south, _ = (shaft.FRONT_STUB + face for face in shaft.gear_faces(16))
    assert shaft.KEYED_LAND == 1
    # Inside the 64T.
    assert south + set_band < shaft.FRONT_STUB + shaft.gear_faces(0)[0]
    assert north <= shaft.SECTION_ENDS[shaft.KEYED_LAND]
    assert north + set_band + band < t024_south
    assert north - set_band - band > t030_south + FACE_WIDTH / 2.0


def test_the_key_still_drives_t030_at_print_worst() -> None:
    """The reach the shaft spec proves at import (#1038): keyseat end set and
    key length at their low limits, T030 floated north against T024 with
    T024's south face at the top of its stack-and-feeler band and T030 at its
    thinnest.  The key keeps at least half T030's face."""
    band = printed_band_mm(spec.LENGTH_PLACES, unit=spec.UNIT)
    set_low = shaft.printed_length_deviations("Sec1KeyseatEndSet")[0]
    assert set_low < 0.0
    north_min = shaft.COLLAR_END_STATION + spec.END_SET_MM + set_low + spec.LENGTH - band
    t024_south_max = (
        shaft.FRONT_STUB
        + shaft.gear_faces(16)[0]
        + cone_tip_cluster.TIP_SET_SHIFT_MM
        + dt_cone_gear_stack.face_band(16, "south")[0]
    )
    t030_south_max = t024_south_max - (FACE_WIDTH + FACE_WIDTH_BAND[1])
    assert shaft.KEY_T030_ENGAGEMENT_MIN_MM == pytest.approx(north_min - t030_south_max)
    assert shaft.KEY_T030_ENGAGEMENT_FLOOR_MM == FACE_WIDTH / 2.0
    assert shaft.KEY_T030_ENGAGEMENT_MIN_MM >= shaft.KEY_T030_ENGAGEMENT_FLOOR_MM
    assert shaft.KEY_NORTH_END_STATION <= shaft.SECTION_ENDS[shaft.KEYED_LAND]


_SPEC_WITH_KEY_LENGTH = (
    "import sys; import cone_land_key; "
    "cone_land_key.KEY_LENGTH_MM = float(sys.argv[1]); "
    "import dt_cone_gear_shaft_spec"
)


def _shaft_spec_refusal(key_length_mm: float) -> str:
    """What a fresh import of the shaft spec raises with the key that long
    ('' when it imports)."""
    result = subprocess.run(
        [sys.executable, "-c", _SPEC_WITH_KEY_LENGTH, repr(key_length_mm)],
        cwd=Path(shaft.__file__).parent, capture_output=True, text=True, check=False,
    )
    if result.returncode == 0:
        return ""
    return result.stderr.strip().splitlines()[-1]


def test_a_key_that_loses_t030_or_leaves_land_1_cannot_import() -> None:
    """Mutation proof of the reach guard: the pre-#1038 4.52 in key passed the
    old T024 margin at the .300 pitch while ending a face short of T030."""
    assert _shaft_spec_refusal(spec.LENGTH) == ""
    assert "the key drives T030 over -" in _shaft_spec_refusal(4.52 * _IN)
    # One cone face short: the key ends about T030's south face.
    assert "the key drives T030 over" in _shaft_spec_refusal(spec.LENGTH - FACE_WIDTH)
    # The next .XX length up leaves land 1.
    assert "overhangs land 1's end" in _shaft_spec_refusal(spec.LENGTH + 0.01 * _IN)


def test_the_cut_clears_the_bar_by_a_key_size_off_its_cut_face() -> None:
    """Codjiflo #2331 P3: a 2 * SIZE mid-plane cut about the Right Plane (the
    bottom face) put its far face on the top face.  The cutter's faces now
    stand one key size clear: the mid-plane half depth past the top face
    (x = SIZE) and the bottom (x = 0), the sketch's y edges past the width's
    +/-SIZE/2, and its far end past the supplied bar's end."""
    import ast
    import inspect

    clear = part.CUTTER_CLEARANCE
    assert clear == spec.SIZE
    half_depth = part.CUT_DEPTH / 2.0
    assert half_depth - spec.SIZE == pytest.approx(clear)
    assert half_depth - 0.0 >= clear
    assert part.CUTTER_HALF_HEIGHT - spec.SIZE / 2.0 == pytest.approx(clear)
    tree = ast.parse(inspect.getsource(part._cut_stock))
    (params,) = (
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and ast.unparse(node.func) == "ExtrusionParameters"
    )
    keywords = {k.arg: ast.unparse(k.value) for k in params.keywords}
    assert keywords == {"depth": "CUT_DEPTH", "both_directions": "True"}
    source = ast.unparse(tree)
    assert "margin = CUTTER_HALF_HEIGHT" in source
    assert "far = STOCK_LENGTH + CUTTER_CLEARANCE" in source


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


# The stacked (1/16") as the farm rendered it (B sheet, 5100 px = 431.8 mm):
# 11.8 mm wide, about 9 mm tall; a bent-leader value hangs its shelf on
# either side of its dimension line, and an outside arrow reaches ~5 mm past
# its extension line.
_INNER_BORDER = (0.0127, 0.0127, 0.4191, 0.2667)
_TEXT_W, _TEXT_H, _ARROW, _CLEAR = 0.0125, 0.009, 0.006, 0.003


def _inside(box: tuple[float, float, float, float]) -> bool:
    x0, y0, x1, y1 = _INNER_BORDER
    return (
        box[0] >= x0 + _CLEAR
        and box[1] >= y0 + _CLEAR
        and box[2] <= x1 - _CLEAR
        and box[3] <= y1 - _CLEAR
    )


def test_end_view_ref_dimensions_stand_clear_inside_the_border() -> None:
    """Machinist reviews of PR #2331: centred on the 3.2 mm square, the
    vertical (1/16") was struck by its own dimension and extension lines
    (7f1dedc, r1-r3); set left of the square, its shelf ran out through the
    inner border (5994f29, r1-r3, rule 13).  Both REF values' text and lines
    lie inside the border with air; the width's text stands below the square,
    outside its extension lines, on either shelf side clear of the side view
    and above the note."""
    cx, cy = drawing.FRONT_CENTER
    half = drawing.HALF_SIZE
    # Height: horizontal, its value over the square, arrows outside.
    hx, hy = drawing.FRONT_KEEP["KeyHeight"]
    assert hy - _TEXT_H / 2.0 > cy + half + _CLEAR
    height_text = (
        hx - _TEXT_W / 2,
        hy - _TEXT_H / 2,
        hx + _TEXT_W / 2,
        hy + _TEXT_H / 2,
    )
    height_line = (cx - half - _ARROW, cy + half, cx + half + _ARROW, hy)
    # Width: vertical line right of the square, value below it on a shelf.
    wx, wy = drawing.FRONT_KEEP["KeyWidth"]
    assert wx > cx + half + _CLEAR
    assert wy + _TEXT_H / 2.0 < cy - half - _CLEAR
    width_text = (wx - _TEXT_W, wy - _TEXT_H / 2, wx + _TEXT_W, wy + _TEXT_H / 2)
    width_line = (cx - half, wy, wx, cy + half + _ARROW)
    for box in (height_text, height_line, width_text, width_line):
        assert _inside(box), box
    assert width_text[2] + _CLEAR < drawing.RIGHT_CENTER[0] - drawing.HALF_LENGTH
    assert width_text[1] > drawing.NOTES_XY[1] + 0.005
