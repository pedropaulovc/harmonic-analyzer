"""Offline contracts for the oblique-trammel jig's feed lever (MHA-CH-06-TL-26)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

import _config
import build_ch_rocker_arm_tl_oblique_feed_lever as part
import ch_rocker_arm_tl_oblique_carrier_spec as carrier
import ch_rocker_arm_tl_oblique_feed_lever_spec as spec
import draw_ch_rocker_arm_tl_oblique_feed_lever as drawing
import export_features
from _drawing_contract import model_toleranced_dimensions
from _hole_spec import THREAD_MAJOR_MM
from _inch_wall_limits import WALL_TARGET_MM

STEM = "ch_rocker_arm_tl_oblique_feed_lever"
INCH = 25.4


def _on_grid(mm: float, places: int) -> bool:
    """``mm`` prints exactly at ``places`` inch decimals."""
    return abs(mm / INCH - round(mm / INCH, places)) < 1e-9


def _features() -> dict:
    return export_features.requirement_manifest(STEM)["features"]


def _carrier_xy(lever_x: float, lever_z: float) -> tuple[float, float]:
    """Lever model point on its seat -> carrier frame (x, y): lever +X runs
    toward carrier -Y from the inner end; the mid-width line is carrier X 0."""
    return (-lever_z - spec.HOLE_Y, carrier.LEVER_INNER_END_Y - lever_x)


def test_lever_holes_land_on_the_carrier_tapped_holes() -> None:
    holes = [_features()[f"bolt_hole_{i}"] for i in (1, 2)]
    landed = [_carrier_xy(h["at"][0], h["at"][2]) for h in holes]
    for (x, y), (cx, cy) in zip(landed, carrier.LEVER_HOLES, strict=True):
        assert abs(x - cx) < 1e-9 and abs(y - cy) < 1e-9
    # The carrier's lever stations, each printing as modelled at .XX.
    assert all(_on_grid(x, spec.HOLE_X_PLACES) for x in spec.HOLE_X)
    # The clearance clears the 5/16-18 screw the carrier is tapped for.
    assert holes[0]["dia"][0] > THREAD_MAJOR_MM[spec.SCREW_THREAD]
    # Owner ruling 2026-11-13: the shop's 11/32 drill.
    assert spec.CLEARANCE_SPEC.kind == "drilled_fractional"
    assert spec.CLEARANCE_SPEC.size == "11/32"
    assert holes[0]["drill"] == "11/32"


def test_lever_lies_on_the_carrier_and_runs_out_past_its_edge() -> None:
    # The inner end is on the carrier, the grip end well past its -Y edge.
    assert carrier.OUTLINE_Y[0] < carrier.LEVER_INNER_END_Y < carrier.OUTLINE_Y[1]
    assert carrier.LEVER_INNER_END_Y - spec.LEVER_LENGTH < carrier.OUTLINE_Y[0]
    assert carrier.OUTLINE_X[0] < -spec.LEVER_WIDTH / 2.0
    assert spec.LEVER_WIDTH / 2.0 < carrier.OUTLINE_X[1]


def test_screw_heads_keep_a_gap() -> None:
    assert spec.HEAD_GAP >= 2.0
    pitch = spec.HOLE_X[1] - spec.HOLE_X[0]
    assert abs(spec.HEAD_GAP - (pitch - 0.469 * INCH)) < 1e-9


def test_stock_is_half_by_one_inch_flat_sawn_to_length() -> None:
    assert (spec.LEVER_THICK, spec.LEVER_WIDTH) == (12.7, 25.4)
    # #290: the sawn length prints as modelled at .X; the stock sizes print
    # their supplier fractions as references over STOCK.
    assert spec.UNIT == "in"
    assert _on_grid(spec.LEVER_LENGTH, spec.SIZE_PLACES)
    assert spec.STOCK_DIMENSIONS == {"LeverWidth", "LeverThick"}
    assert spec.STOCK_CALLOUT == "STOCK"
    assert not hasattr(spec, "CALLOUTS_BELOW")
    sizes = {"LeverWidth": spec.LEVER_WIDTH, "LeverThick": spec.LEVER_THICK}
    for name, denominator in spec.STOCK_FRACTION_DENOMINATORS.items():
        assert sizes[name] / INCH * denominator == pytest.approx(
            round(sizes[name] / INCH * denominator)
        )


def test_walls_hold_rule_17_at_worst_case() -> None:
    assert min(spec.WALLS_MM.values()) >= WALL_TARGET_MM
    holes = _features()
    first, second = holes["bolt_hole_1"], holes["bolt_hole_2"]
    r_max = first["dia"][1] / 2.0
    assert first["station"][0] - r_max >= WALL_TARGET_MM
    assert second["station"][0] - first["station"][1] - 2.0 * r_max >= WALL_TARGET_MM
    assert first["width"][0] - r_max >= WALL_TARGET_MM


def test_grip_corners_are_broken_clear_of_the_holes() -> None:
    assert spec.CORNER_R > 0.0
    assert spec.LEVER_LENGTH - spec.CORNER_R > spec.HOLE_X[-1] + spec.HOLE_DIA
    assert spec.DIMENSION_PREFIXES["GripCornerR"] == "2X R"
    # Both printed corners export as one fillet under the .X band (R.1-R.3).
    corners = _features()["grip_corners"]
    assert corners["count"] == 2
    assert corners["radius"] == pytest.approx(
        [spec.CORNER_R - 0.1 * INCH, spec.CORNER_R + 0.1 * INCH]
    )


def test_holes_carry_the_title_block_band_only() -> None:
    assert model_toleranced_dimensions(part) == {}
    low, high = _features()["bolt_hole_1"]["dia"]
    # The 11/32 drill (.3438 at four places) with the drilled-hole band
    # about its exact size, so the drill itself is the lower limit.
    assert low == pytest.approx(11.0 / 32.0 * INCH)
    assert high - low == pytest.approx(spec.DRILLED_BAND[0])
    assert spec.HOLE_CALLOUT_PRECISION == {"hw-diam": 4}
    assert round(spec.HOLE_DIA / INCH, 4) == pytest.approx(0.3438)


def test_every_marked_dimension_prints_once_at_its_model_places() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.TOP_KEEP) | set(drawing.FRONT_KEEP) == marked
    assert not set(drawing.TOP_KEEP) & set(drawing.FRONT_KEEP)
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked
    assert set(spec.DIMENSION_PREFIXES) <= marked


def test_every_exported_band_endpoint_is_a_printed_value() -> None:
    checked = 0
    stock = {("carrier_seat", "thickness"), ("carrier_seat", "width")}
    # The drilled band qualifies the exact size of the drill the callout
    # names (11/32, printed .3438): rule 3's named-drill decimal.
    drilled = {("bolt_hole_1", "dia"), ("bolt_hole_2", "dia")}
    for name, feature in _features().items():
        for requirement in feature["requirements"]:
            band = feature.get(requirement)
            if not (isinstance(band, list) and len(band) == 2):
                continue
            places = feature["precision"][requirement]
            nominal = feature.get(f"{requirement}_nominal")
            if nominal is not None:
                assert band[0] <= nominal <= band[1], (name, requirement)
                if (name, requirement) not in drilled:
                    assert _on_grid(nominal, places), (name, requirement)
            checked += 1
            if (name, requirement) in stock | drilled:
                continue  # a supplier's or the drill's band about its size
            for end in band:
                assert _on_grid(end, places), (name, requirement)
    assert checked


def test_number_is_the_parent_number_plus_a_tool_suffix() -> None:
    parent = _config.parts("ch-rocker-arm")["number"]
    number = _config.parts("ch-rocker-arm-tl-oblique-feed-lever")["number"]
    assert re.fullmatch(re.escape(parent) + r"-TL-\d{2}", number)
    assert number == "MHA-CH-06-TL-26"


def test_sheet_carries_no_notes() -> None:
    assert spec.DRAWING_NOTES == ""
    assert spec.HOLE_CALLOUT_PROCESS == "DRILL"


def test_prechips_solids_name_the_lever_and_its_holes() -> None:
    names = {solid["name"] for solid in spec.PRECHIPS_SOLIDS}
    assert names == {"feed lever", "bolt hole 1", "bolt hole 2"}


class _Callout:
    """A native hole callout's four definitions (5..8), each written through
    its writable twin (1..4) and read back with CR LF, as SolidWorks does."""

    def __init__(self, definitions: dict[int, str], *, accepts: bool = True) -> None:
        self.definitions = dict(definitions)
        self.accepts = accepts

    def IsHoleCallout(self) -> bool:
        return True

    def SetText(self, part: int, text: str) -> None:
        assert 1 <= part <= 4
        if self.accepts:
            self.definitions[part + 4] = text

    def GetText(self, part: int) -> str:
        return self.definitions.get(part, "").replace("\n", "\r\n")


@pytest.mark.parametrize("token", ("<hw-diam>", "<hw-thruholedia>"))
def test_drill_follows_the_size_in_the_native_callout(token: str) -> None:
    # Rule 26: size, then process; rule 3: the named drill's exact decimal.
    # 2X Ø.3438 11/32 DRILL THRU ALL.
    native = {5: "", 6: "", 7: f"<NUM_INST>X <MOD-DIAM>{token} THRU ALL", 8: ""}
    callout = _Callout(native)
    drawing._write_drill_after_size(callout)
    assert callout.definitions == {
        **native,
        7: f"<NUM_INST>X <MOD-DIAM>{token} 11/32 DRILL THRU ALL",
    }
    # A refused write is caught on read-back.
    with pytest.raises(RuntimeError, match="did not persist"):
        drawing._write_drill_after_size(_Callout(native, accepts=False))


@pytest.mark.parametrize(
    "definitions",
    (
        {5: "", 6: "", 7: "<NUM_INST>X <MOD-DIAM><hw-cbdia> THRU ALL", 8: ""},
        {5: "<hw-diam>", 6: "", 7: "<NUM_INST>X <MOD-DIAM><hw-thruholedia>", 8: ""},
        {5: "<hw-diam>", 6: "", 7: "<NUM_INST>X <MOD-DIAM><hw-diam> THRU ALL", 8: ""},
        {5: "", 6: "", 7: "<NUM_INST>X <MOD-DIAM><hw-diam> DRILL THRU ALL", 8: ""},
        {5: "", 6: "", 7: "<NUM_INST>X <MOD-DIAM><hw-diam> THRU ALL"},
    ),
)
def test_drill_rewrite_refuses_an_unexpected_callout(definitions: dict[int, str]) -> None:
    # No size variable, both shapes, a repeated size, DRILL already there, or
    # a missing part: refused, never guessed.
    with pytest.raises(RuntimeError):
        drawing.drill_callout_definitions(definitions)


def test_the_callout_takes_no_process_prefix() -> None:
    sheet = Path(drawing.__file__).read_text(encoding="utf-8")
    body = sheet[sheet.index("async def build") :]
    assert "process=" not in body
    assert body.index("_write_drill_after_size(hole_callout)") < body.index(
        "set_hole_callout_precision("
    )
