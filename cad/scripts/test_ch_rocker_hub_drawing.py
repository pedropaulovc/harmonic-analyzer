"""Offline contracts for the rocker hub (MHA-CH-12) drawing."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

import _config
import build_ch_rocker_hub as part
import ch_rocker_arm_spec as rocker
import ch_rocker_hub_fit as fit
import ch_rocker_hub_notes as notes
import ch_rocker_hub_spec as spec
import draw_ch_rocker_hub as drawing
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _inch_wall_limits import WALL_FLOOR_MM


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/ch-rocker-hub.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/ch-rocker-hub.pdf")
    assert DRAWINGS_BY_NAME["ch_rocker_hub"].script == Path(drawing.__file__).resolve()
    assert "draw_ch_rocker_hub.py" in PRECISION_MIGRATED_DRAWINGS


def test_the_matched_press_holds_interference_over_every_reamed_hole() -> None:
    # .400 strap hole +.0005/.0000; each land turned to its own measured hole
    # for .0004-.0013 (owner ruling 2026-11-21, matched fit only), so across
    # the reamed band the lands run .4004-.4018.
    assert rocker.HUB_DIA == pytest.approx(0.400 * 25.4)
    assert fit.STRAP_HOLE_BAND == (0.0127, 0.0)
    assert fit.PRESS_INTERFERENCE == pytest.approx((0.01016, 0.03302))
    assert fit.LAND_RANGE == pytest.approx((0.01016, 0.04572))
    # Each land's own window is the whole .0009 interference, against the
    # .0004 the old .4009-.4013 band left (every hole at once).
    each = fit.PRESS_INTERFERENCE[1] - fit.PRESS_INTERFERENCE[0]
    every_hole = each - (fit.STRAP_HOLE_BAND[0] - fit.STRAP_HOLE_BAND[1])
    assert each / 25.4 == pytest.approx(0.0009)
    assert every_hole / 25.4 == pytest.approx(0.0004)


@pytest.mark.parametrize(
    "interference",
    [(0.0, 0.0127), (-0.0127, 0.0127), (0.0254, 0.0127)],
    ids=["line-to-line", "loose", "inverted"],
)
def test_a_press_that_can_go_line_to_line_is_refused(interference) -> None:
    with pytest.raises(AssertionError, match="line-to-line or loose"):
        fit.land_range(interference, fit.STRAP_HOLE_BAND)


def test_supply_sizes_derive_from_the_finished_rocker() -> None:
    assert spec.LAND_DIA == rocker.HUB_DIA
    # The bore is drilled under the finished ream; the drilled-hole row's
    # +.004 still leaves stock.
    assert spec.SUPPLY_BORE_DIA == pytest.approx(0.246 * 25.4)
    assert spec.SUPPLY_BORE_DIA + spec.DRILLED_PLUS < rocker.PIVOT_HOLE_DIA
    # The length leaves FACE_STOCK at each end over the finished top limit.
    finished_max = rocker.HUB_LENGTH + rocker.HUB_LENGTH_BAND[0]
    # .278 +.002 finished, .020 a face: .320 exactly, on the two-place grid.
    assert spec.SUPPLY_LENGTH_MIN == pytest.approx(0.32 * 25.4)
    assert spec.SUPPLY_LENGTH_MIN >= finished_max + 2.0 * spec.FACE_STOCK
    assert spec.SUPPLY_LENGTH_TOL_TYPE == 5  # swTolType_e.swTolMIN
    assert spec.SUPPLY_WALL_MIN >= WALL_FLOOR_MM
    assert part.V_HUB == pytest.approx(
        math.pi
        * ((spec.LAND_DIA / 2.0) ** 2 - (spec.SUPPLY_BORE_DIA / 2.0) ** 2)
        * spec.SUPPLY_LENGTH_MIN
    )


def test_the_sheet_never_repeats_a_finished_size() -> None:
    printed = " ".join(
        (
            notes.DRAWING_NOTES,
            *drawing.DIMENSION_CALLOUTS.values(),
            notes.SUPPLY_LENGTH_PREFIX,
        )
    )
    for value, places in (
        (rocker.PIVOT_HOLE_DIA, 3),
        (rocker.HUB_LENGTH, 2),
        (rocker.HUB_LENGTH, 3),
        (rocker.HUB_LENGTH, 4),
    ):
        assert f"{value / 25.4:.{places}f}".removeprefix("0") not in printed
    assert notes.DRAWING_NOTES == (
        "1. BORE AND LENGTH ARE FINISHED AFTER JOINING TO MHA-CH-13; SEE MHA-CH-06."
    )


def test_every_marked_dimension_has_one_view_and_model_places() -> None:
    marked = set().union(*notes.DRAWING_DIMENSIONS.values())
    assert set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP) == marked
    assert not set(drawing.FRONT_KEEP) & set(drawing.RIGHT_KEEP)
    assert set(drawing.DIMENSION_CALLOUTS) <= marked


def test_every_band_is_native_and_named() -> None:
    # The land carries no band of its own (owner ruling 2026-11-21, matched
    # fit only): a reference, bracketed on the part.
    assert model_toleranced_dimensions(part) == {}
    assert notes.REFERENCE_DIMENSIONS == {"HubProfile": frozenset({"LandDia"})}
    assert notes.DRAWING_PRECISION_BY_NAME["LandDia"] == 3
    assert (notes.REFERENCE_PREFIX, notes.REFERENCE_SUFFIX) == ("(<MOD-DIAM>", ")")
    # Fan-out screen 2026-11-07 (rule 7): the bore's and the length's
    # supply-matched sizes link the note that states them.
    assert notes.SUPPLY_BORE_CALLOUT.splitlines() == [
        "DRILL THRU",
        "SUPPLY SIZE, SEE NOTE 1",
        "WALL .075 MIN",
    ]
    assert notes.SUPPLY_LENGTH_CALLOUT == "SEE NOTE 1"
    assert drawing.DIMENSION_CALLOUTS["SupplyLength"] == notes.SUPPLY_LENGTH_CALLOUT
    assert notes.DRAWING_NOTES.startswith("1. ")
    # Rule 4, matched pairs: the reference Ø names its measured mate and the
    # interference that governs.
    assert notes.LAND_CALLOUT.splitlines() == [
        "TURN TO MEASURED STRAP HOLE",
        ".0004-.0013 DIAMETRAL INTERFERENCE ON MHA-CH-13",
    ]
    # The stated wall is the spec's worst case, rounded down (rule 20).
    assert 0.075 <= spec.SUPPLY_WALL_MIN / 25.4 < 0.076


def test_registry_row() -> None:
    row = _config.parts("ch-rocker-hub")
    assert row["number"] == spec.NUMBER == "MHA-CH-12"
    assert row["component_of"] == "ch-rocker-arm"
    assert int(row["quantity"]) == int(_config.parts("ch-rocker-arm")["quantity"])
    assert "1018" in str(row["material_specification"])
    assert len(str(row["material_specification"])) <= 36
    assert len(str(row["finish"])) <= 36
    assert part.MATERIAL == "Plain Carbon Steel"


def test_land_callout_stands_above_the_hub_clear_of_the_isometric() -> None:
    """Fan-out rounds 5-6 (rule 14): between the arrows the land's dimension
    line struck its REF row, so the text stands above the upper extension
    line; outside the arrows it hangs east of the dimension line (~120 mm at
    the route row), so the isometric sits below the block."""
    x, y = drawing.LAND_ON_SIDE
    line = 0.0052  # one text row at the sheet's dimension font
    rows = 1 + len(notes.LAND_CALLOUT.splitlines())
    assert y - (rows - 1) * line > drawing.RIGHT_CENTER[1] + drawing.HALF_DIA + 0.004
    assert y + line < 0.2667
    iso_half = 0.026  # the 4:1 pictorial's half-extent
    assert drawing.ISO_CENTER[1] + iso_half < y - rows * line - 0.005
    assert drawing.ISO_CENTER[1] - iso_half > 0.065  # over the title block
    assert drawing.ISO_CENTER[0] - iso_half > x + 0.005


def test_the_traveler_land_window_reads_the_drawing_interference() -> None:
    import tomllib

    from _paths import CAD_ROOT

    plan = tomllib.loads(
        (CAD_ROOT / "process/ch_rocker_hub/plan.toml").read_text("utf-8")
    )
    # Owner ruling 2026-11-23 (tool audit Q2): "B. Four reading pins (.4000,
    # .4002, .4004, .4005)." A hole's reading R is the largest pin that
    # enters; the hole lies under the next pin up.
    pins = (0.4000, 0.4002, 0.4004, 0.4005)
    least, greatest = (i / 25.4 for i in fit.PRESS_INTERFERENCE)
    p = plan["parameters"]
    assert p["land_over_reading_min_in"] == pytest.approx(least + 0.0002)
    assert p["top_reading_in"] == pytest.approx(pins[-2])
    assert p["land_over_top_reading_min_in"] == pytest.approx(
        least + pins[-1] - pins[-2]
    )

    def land_low(largest: float) -> float:  # the plan's Op 40 rule
        if largest == pytest.approx(p["top_reading_in"]):
            return largest + p["land_over_top_reading_min_in"]
        return largest + p["land_over_reading_min_in"]

    windows = []
    readings = pins[:-1]
    for smallest in readings:
        for largest in (r for r in readings if r >= smallest):
            low, high = land_low(largest), smallest + greatest
            # Every hole the lot's readings admit takes the drawing's
            # interference from both ends of the window.
            for r in (smallest, largest):
                top = pins[pins.index(r) + 1]
                assert low - top >= least - 1e-9
                assert high - r <= greatest + 1e-9
            windows.append(high - low)
    assert min(windows) == pytest.approx(p["land_window_min_in"])
    assert min(windows) > 0.0
