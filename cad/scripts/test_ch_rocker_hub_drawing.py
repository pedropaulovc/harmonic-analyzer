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


def test_the_bonded_land_slides_into_every_reamed_hole() -> None:
    # Owner ruling 2026-11-24, fit audit question 2: .400 strap hole reamed
    # with no band (the reamer's modelled +.0005/.0000), each land turned to
    # slide into it with .0005-.0030 diametral clearance and bonded with
    # LOCTITE 638, so across the reamed band the lands run .3970-.4000.
    assert rocker.HUB_DIA == pytest.approx(0.400 * 25.4)
    assert fit.STRAP_HOLE_BAND == (0.0127, 0.0)
    assert fit.BOND_CLEARANCE == pytest.approx((0.0127, 0.0762))
    assert fit.LAND_RANGE == pytest.approx((-0.0762, 0.0))
    # One micrometer window takes every hole the reamer cuts: .3975-.3995.
    assert fit.LAND_WINDOW == pytest.approx((-0.0635, -0.0127))
    for hole in fit.STRAP_HOLE_BAND:
        for land in fit.LAND_WINDOW:
            gap = hole - land
            assert fit.BOND_CLEARANCE[0] - 1e-9 <= gap <= fit.BOND_CLEARANCE[1] + 1e-9
    # The widest gap stays inside the compound's gap fill (TDS: 0.25 mm).
    assert fit.BOND_CLEARANCE[1] <= fit.LOCTITE_638_GAP_MAX


@pytest.mark.parametrize(
    "clearance",
    [(0.0, 0.0127), (-0.0127, 0.0127), (0.0254, 0.0127)],
    ids=["line-to-line", "tight", "inverted"],
)
def test_a_bond_that_can_go_line_to_line_is_refused(clearance) -> None:
    with pytest.raises(AssertionError, match="line-to-line or tight"):
        fit.land_range(clearance, fit.STRAP_HOLE_BAND)


def test_a_bond_gap_past_the_compound_is_refused() -> None:
    with pytest.raises(AssertionError, match="gap fill"):
        fit.land_range((0.0127, 0.3), fit.STRAP_HOLE_BAND)


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
    assert notes.DRAWING_NOTES.splitlines() == [
        "1. BORE AND LENGTH ARE FINISHED AFTER JOINING TO MHA-CH-13; SEE MHA-CH-06.",
        "2. BONDED INTO MHA-CH-13 WITH LOCTITE 638: LAND AND HOLE DEGREASED,",
        "   COMPOUND ON THE LAND ONLY; HELD SQUARE TO THE STRAP UNTIL SET; 24 H CURE",
        "   BEFORE MHA-CH-06 IS FINISHED. THE HUB DOES NOT TURN BY HAND.",
    ]


def test_every_marked_dimension_has_one_view_and_model_places() -> None:
    marked = set().union(*notes.DRAWING_DIMENSIONS.values())
    assert set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP) == marked
    assert not set(drawing.FRONT_KEEP) & set(drawing.RIGHT_KEEP)
    assert set(drawing.DIMENSION_CALLOUTS) <= marked


def test_every_band_is_native_and_named() -> None:
    # The land carries no band of its own (owner ruling 2026-11-24, fit audit
    # question 2, made to fit): a reference, bracketed on the part.
    assert model_toleranced_dimensions(part) == {}
    assert notes.REFERENCE_DIMENSIONS == {"HubProfile": frozenset({"LandDia"})}
    assert notes.DRAWING_PRECISION_BY_NAME["LandDia"] == 3
    assert (notes.REFERENCE_PREFIX, notes.REFERENCE_SUFFIX) == ("(<MOD-DIAM>", ")")
    # Fan-out screen 2026-11-07 (rule 7): the bore's and the length's
    # supply-matched sizes link the note that states them.
    assert notes.SUPPLY_BORE_CALLOUT.splitlines() == [
        "DRILL THRU",
        "SUPPLY SIZE, SEE NOTE 1",
        "WALL .073 MIN",
    ]
    assert notes.SUPPLY_LENGTH_CALLOUT == "SEE NOTE 1"
    assert drawing.DIMENSION_CALLOUTS["SupplyLength"] == notes.SUPPLY_LENGTH_CALLOUT
    assert notes.DRAWING_NOTES.startswith("1. ")
    # Rule 4, made to fit: the reference Ø names its mate, the clearance that
    # governs and the compound, once, on the member made last.
    assert notes.LAND_CALLOUT.splitlines() == [
        "TURN TO SLIDE INTO MHA-CH-13 HOLE",
        ".0005-.0030 CLEARANCE, SEE NOTE 2",
    ]
    # The stated wall is the spec's worst case, rounded down (rule 20): the
    # smallest land .3970 over the largest D drill .250.
    assert 0.073 <= spec.SUPPLY_WALL_MIN / 25.4 < 0.074


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


def test_the_traveler_land_window_reads_the_drawing_clearance() -> None:
    import tomllib

    from _paths import CAD_ROOT

    plan_text = (CAD_ROOT / "process/ch_rocker_hub/plan.toml").read_text("utf-8")
    p = tomllib.loads(plan_text)["parameters"]
    # The lot is turned to one micrometer window that takes the drawing's
    # clearance in every hole the .4000 reamer cuts (.3975-.3995), then each
    # land is tried in a strap hole: no hole is read with plug gauges.
    nominal = rocker.HUB_DIA / 25.4
    assert p["land_min_in"] == pytest.approx(nominal + fit.LAND_WINDOW[0] / 25.4)
    assert p["land_max_in"] == pytest.approx(nominal + fit.LAND_WINDOW[1] / 25.4)
    assert "plug-gauges-" not in plan_text
