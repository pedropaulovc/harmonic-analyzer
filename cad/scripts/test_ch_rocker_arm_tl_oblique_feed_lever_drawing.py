"""Offline contracts for the oblique-trammel jig's feed lever (MHA-CH-006-TL-26)."""

from __future__ import annotations

import re

import _config
import build_ch_rocker_arm_tl_oblique_feed_lever as part
import ch_rocker_arm_tl_oblique_carrier_spec as carrier
import ch_rocker_arm_tl_oblique_feed_lever_spec as spec
import draw_ch_rocker_arm_tl_oblique_feed_lever as drawing
import export_features
from _drawing_contract import model_toleranced_dimensions
from _hole_spec import THREAD_MAJOR_MM

STEM = "ch_rocker_arm_tl_oblique_feed_lever"
INCH = 25.4


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
    # The ruling's 16 pitch, landing at lever X 7 and 23.
    assert spec.HOLE_X == (7.0, 23.0)
    # The clearance clears the 5/16-18 screw the carrier is tapped for.
    assert holes[0]["dia"][0] > THREAD_MAJOR_MM[spec.SCREW_THREAD]
    assert spec.CLEARANCE_SPEC.kind == "clearance"
    assert spec.CLEARANCE_SPEC.size == "5/16"
    assert spec.CLEARANCE_SPEC.fit == "normal"


def test_lever_lies_on_the_carrier_and_runs_out_past_its_edge() -> None:
    # The inner end is on the carrier, the grip end well past its -Y edge.
    assert carrier.OUTLINE_Y[0] < carrier.LEVER_INNER_END_Y < carrier.OUTLINE_Y[1]
    assert carrier.LEVER_INNER_END_Y - spec.LEVER_LENGTH < carrier.OUTLINE_Y[0]
    assert carrier.OUTLINE_X[0] < -spec.LEVER_WIDTH / 2.0
    assert spec.LEVER_WIDTH / 2.0 < carrier.OUTLINE_X[1]


def test_screw_heads_keep_a_gap() -> None:
    assert spec.HEAD_GAP >= 2.0
    assert abs(spec.HEAD_GAP - (16.0 - 0.469 * INCH)) < 1e-9


def test_stock_is_half_by_one_inch_flat_300_long() -> None:
    assert (spec.LEVER_THICK, spec.LEVER_WIDTH, spec.LEVER_LENGTH) == (
        12.7,
        25.4,
        300.0,
    )
    assert spec.CALLOUTS_BELOW == {"LeverWidth": "STOCK", "LeverThick": "STOCK"}


def test_walls_hold_rule_17_at_worst_case() -> None:
    assert min(spec.WALLS_MM.values()) >= 2.0
    holes = _features()
    first, second = holes["bolt_hole_1"], holes["bolt_hole_2"]
    r_max = first["dia"][1] / 2.0
    assert first["station"][0] - r_max >= 2.0
    assert second["station"][0] - first["station"][1] - 2.0 * r_max >= 2.0
    assert first["width"][0] - r_max >= 2.0


def test_grip_corners_are_broken_clear_of_the_holes() -> None:
    assert spec.CORNER_R > 0.0
    assert spec.LEVER_LENGTH - spec.CORNER_R > spec.HOLE_X[-1] + spec.HOLE_DIA
    assert spec.DIMENSION_PREFIXES["GripCornerR"] == "2X R"


def test_holes_carry_the_title_block_band_only() -> None:
    assert model_toleranced_dimensions(part) == {}
    assert _features()["bolt_hole_1"]["dia"] == [8.74, 8.84]


def test_every_marked_dimension_prints_once_at_its_model_places() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.TOP_KEEP) | set(drawing.FRONT_KEEP) == marked
    assert not set(drawing.TOP_KEEP) & set(drawing.FRONT_KEEP)
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked
    assert set(spec.CALLOUTS_BELOW) | set(spec.DIMENSION_PREFIXES) <= marked


def test_every_exported_band_endpoint_is_a_printed_value() -> None:
    checked = 0
    for name, feature in _features().items():
        for requirement in feature["requirements"]:
            band = feature.get(requirement)
            if not (isinstance(band, list) and len(band) == 2):
                continue
            places = feature["precision"][requirement]
            for end in band:
                assert abs(end - round(end, places)) < 1e-9, (name, requirement)
            nominal = feature.get(f"{requirement}_nominal")
            if nominal is not None:
                assert band[0] <= nominal <= band[1], (name, requirement)
                assert abs(nominal - round(nominal, places)) < 1e-9
            checked += 1
    assert checked


def test_number_is_the_parent_number_plus_a_tool_suffix() -> None:
    parent = _config.parts("ch-rocker-arm")["number"]
    number = _config.parts("ch-rocker-arm-tl-oblique-feed-lever")["number"]
    assert re.fullmatch(re.escape(parent) + r"-TL-\d{2}", number)
    assert number == "MHA-CH-006-TL-26"


def test_sheet_carries_no_notes() -> None:
    assert spec.DRAWING_NOTES == ""
    assert spec.HOLE_CALLOUT_PROCESS == "DRILL"


def test_prechips_solids_are_valid_fixture_solids() -> None:
    from prechips.model import FixtureSolid

    for solid in spec.PRECHIPS_SOLIDS:
        FixtureSolid.model_validate(solid)
    names = {solid["name"] for solid in spec.PRECHIPS_SOLIDS}
    assert names == {"feed lever", "bolt hole 1", "bolt hole 2"}
