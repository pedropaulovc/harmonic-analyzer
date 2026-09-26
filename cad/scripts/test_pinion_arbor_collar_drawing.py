"""Offline contracts for the pinion-arbor collar (R1a) and its drawing."""

from __future__ import annotations

from itertools import product
from pathlib import Path

import pytest

import _config
import build_pinion_arbor_collar as collar
import draw_pinion_arbor_collar as drawing
import pinion_arbor_collar_geometry as geometry
import pinion_arbor_collar_spec as spec
import pinion_arbor_spec as arbor
import pinion_arbor_pin_spec as arbor_pin
import pinion_strap_pin_spec as strap_pin
from _buildgraph import module_deps_of
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/pinion-arbor-collar.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/pinion-arbor-collar.pdf")
    assert drawing.PNG.as_posix().endswith("/png/pinion-arbor-collar_drawing.png")
    assert (
        DRAWINGS_BY_NAME["pinion_arbor_collar"].script
        == Path(drawing.__file__).resolve()
    )


def test_user_ruling_r1a_geometry() -> None:
    """Ø15 OD, Ø8 +0.10/0 drilled bore, pin hole centred; 17 long since the
    pin-station stack (Codex P2 on #860) -- the user ruling's 20 pressed the
    strap at the worst band corner."""
    assert (geometry.COLLAR_OD, geometry.BORE, geometry.COLLAR_LEN) == (15.0, 8.0, 17.0)
    assert spec.BORE_BAND == (0.10, 0.0)
    assert geometry.PIN_HOLE_Z == geometry.COLLAR_LEN / 2.0
    # The rig's one pin family and drill (pinion_strap_pin_spec, E-a).
    assert spec.PIN_HOLE == strap_pin.HOLE_DIA == arbor_pin.PIN_HOLE_DIA
    assert spec.PIN_HOLE_BAND == strap_pin.HOLE_BAND == (0.06, 0.0)
    assert spec.SLIDE_CLEARANCE_MIN > 0.0


def test_spring_pin_is_the_rig_family_and_never_proud() -> None:
    assert strap_pin.PIN_STANDARD == "ASME B18.8.2"
    assert spec.PIN_LEN == pytest.approx(12.7)
    # 1.15 sub-flush each side at nominal, still sub-flush at the worst case.
    assert (geometry.COLLAR_OD - spec.PIN_LEN) / 2.0 == pytest.approx(1.15)
    assert spec.PIN_SUB_FLUSH_WORST > 0.0
    assert spec.PIN_WALL_ENGAGEMENT_WORST >= 1.5


def test_collar_pin_is_the_stock_mha145_named_on_the_hole_not_a_note() -> None:
    """#858 made the rig's spring pin the stock MHA-145 (McMaster 98296A027),
    its own BOM line.  The collar takes a third one, so the sheet names it on
    the pin-hole callout and carries no supply note (the MHA-056 precedent)."""
    row = _config.parts("pinion-strap-pin")
    assert spec.PIN_NUMBER == row["number"]
    assert int(row["quantity"]) == 3  # two strap pins and the collar pin
    assert spec.PIN_HOLE_CALLOUT == (
        f"{strap_pin.DRILL_THRU_CALLOUT}\nFOR {row['number']} SPRING PIN"
    )
    assert drawing.DIMENSION_CALLOUTS["PinHoleDia"] == spec.PIN_HOLE_CALLOUT
    assert not hasattr(spec, "DRAWING_NOTES")
    for script in (collar, drawing):
        assert "Manufacturing Notes" not in Path(script.__file__).read_text(
            encoding="utf-8"
        )


def test_drive_train_pins_the_collar_with_a_locked_mha145() -> None:
    """The collar pin is a modelled component on the collar's and arbor's
    common pin-hole axis, locked to the collar so it rides the p2 swing."""
    import inspect

    import build_drive_train_assembly as assembly

    rows = assembly.COLLAR_PIN_ROWS
    # The stock pin's axis (local X) is the arbor's pin-hole axis (local Y).
    assert rows[0] == pytest.approx(assembly.ARBOR_ROWS[1])
    assert assembly.COLLAR_PIN_Z == pytest.approx(assembly.ARBOR_Z0 + arbor.PIN_Z)
    source = inspect.getsource(assembly)
    assert "[APINION_X, APINION_Y, COLLAR_PIN_Z]" in source
    assert 'named_ref(f"Front Plane@{collar_pin}", "PLANE")' in source
    assert 'label="collar spring pin locked in the collar"' in source


def test_webs_meet_the_u27_target_at_the_printed_worst_case() -> None:
    assert (geometry.COLLAR_OD - (geometry.BORE + spec.BORE_BAND[0])) / 2.0 == pytest.approx(3.45)
    assert spec.COLLAR_WALL_WORST == pytest.approx(3.05)
    assert spec.PIN_TO_END_WEB_WORST == pytest.approx(6.076, abs=1e-3)
    assert arbor_pin.PIN_HOLE_LIGAMENT_WORST == pytest.approx(3.126, abs=1e-3)
    for web in (
        spec.COLLAR_WALL_WORST,
        spec.PIN_TO_END_WEB_WORST,
        arbor_pin.PIN_HOLE_LIGAMENT_WORST,
    ):
        assert web >= 2.0


def test_collar_never_touches_the_front_strap_at_any_band_corner() -> None:
    """The gap stacks the drum station, the drum's front air, the strap, the
    arbor pin station, the collar length AND the collar's own pin station
    (PinHoleCz), each at its printed band, with the collar either way round.
    Codex P2 on #860: the length and the station vary independently, so the
    pin-to-inboard-face distance is not simply half the length."""
    assert spec.GAP_MIN == pytest.approx(0.70)
    assert spec.GAP_NOMINAL == pytest.approx(4.875)
    assert spec.GAP_MAX == pytest.approx(9.05)
    gaps = [
        (station - air - strap) - (pin + to_face)
        for station, air, strap, pin, length, cz in product(
            (arbor.DRUM_STATION - 0.8, arbor.DRUM_STATION + 0.8),
            arbor.drum_total_air(),
            (arbor.STRAP_T - 0.8, arbor.STRAP_T + 0.8),
            (38.2, 39.8),
            (geometry.COLLAR_LEN - 0.8, geometry.COLLAR_LEN + 0.8),
            (geometry.PIN_HOLE_Z - 0.8, geometry.PIN_HOLE_Z + 0.8),
        )
        for to_face in (cz, length - cz)
    ]
    assert min(gaps) == pytest.approx(spec.GAP_MIN)
    assert max(gaps) == pytest.approx(spec.GAP_MAX)
    assert min(gaps) > 0.0


def test_gap_max_is_only_a_bond_failure_walk_the_rig_tolerates() -> None:
    """GAP_MAX is how far MHA-102 can walk north through the drum if its
    Loctite 638 bond lets go before the collar stops it.  The drum stays
    trapped between the straps, so the mesh never moves; the arbor's back end
    walks alongside the north arbor pedestal, which stands well clear of the
    pinion-arbor axis radially."""
    import build_arbor_pedestal as pedestal
    import build_drive_train_assembly as assembly

    pedestal_reach_x = assembly.X_DRUM + pedestal.FOOT_WIDTH / 2.0
    arbor_near_x = assembly.APINION_X - arbor.SHAFT_DIA / 2.0
    assert arbor_near_x - pedestal_reach_x > 20.0
    back_end = assembly.ARBOR_Z0 + arbor.SHAFT_LEN
    assert back_end + spec.GAP_MAX < assembly.ARBOR_PEDESTAL_NORTH_Z + pedestal.FOOT_DEPTH / 2.0


def test_the_pin_never_enters_the_front_land() -> None:
    assert arbor_pin.PIN_HOLE_LAND_CLEARANCE >= 2.0


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    assert collar.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.END_KEEP) | set(drawing.PROFILE_KEEP)
    assert kept == marked
    assert set(drawing.DIMENSION_CALLOUTS) <= kept
    assert drawing.DIMENSION_CALLOUTS["PinHoleDia"].startswith("1/16 DRILL THRU\n")
    assert "MHA-102" in drawing.DIMENSION_CALLOUTS["BoreDia"]


def test_only_the_pin_hole_carries_a_band() -> None:
    """The Ø8 bore is a plain drilled hole: the title block's DRILLED HOLES
    row governs it, and restating that row on the dimension is what policy
    rule 1 forbids (Codex on #860).  Only the pin hole's tighter band rides."""
    assert model_toleranced_dimensions(collar) == {
        ("PinHoleProfile", "PinHoleDia"): "*deviations(PIN_HOLE_BAND)",
    }


def test_bore_band_is_the_title_block_drilled_hole_row() -> None:
    row = _config.title_block("drilled_hole")
    assert spec.BORE_BAND == (row["plus_mm"], row["minus_mm"])


def test_the_part_owns_every_printed_decimal_place() -> None:
    by_name = spec.DRAWING_PRECISION_BY_NAME
    assert set(by_name) == set().union(*spec.DRAWING_DIMENSIONS.values())
    assert {name for name, places in by_name.items() if places != 1} == {
        "BoreDia",
        "PinHoleDia",
    }
    assert Path(drawing.__file__).name in PRECISION_MIGRATED_DRAWINGS


def test_turned_part_views_follow_the_machinist() -> None:
    # Rule 7: the OD and the pin station go on the lathe-oriented profile;
    # only the bore, a solid circle end-on, keeps its callout there.
    assert set(drawing.PROFILE_KEEP) == {"Depth", "PinHoleCz", "PinHoleDia"}
    assert set(drawing.END_KEEP) == {"BoreDia", "CollarOd"}
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "_move_dimension(\n        adapter, od_donors[0], profile" in source
    # Third angle: the end view seen from the +Z end sits left of the profile.
    assert drawing.END_CENTER[0] < drawing.PROFILE_CENTER[0]
    assert drawing.END_CENTER[1] == drawing.PROFILE_CENTER[1]
    assert drawing.SHEET_SCALE == (3.0, 1.0)
    assert spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 2:1"


def test_drive_train_recipe_reads_geometry_not_drawing_notes() -> None:
    drive_train = Path(__file__).with_name("build_drive_train_assembly.py")
    names = {Path(path).name for path in module_deps_of(drive_train)}
    assert "pinion_arbor_collar_geometry.py" in names
    assert "pinion_arbor_collar_spec.py" not in names
    assert "build_pinion_arbor_collar.py" not in names


def test_drive_train_places_the_collar_on_the_arbor_pin_station() -> None:
    import build_drive_train_assembly as assembly

    assert assembly.ARBOR_COLLAR_Z0 + geometry.PIN_HOLE_Z == pytest.approx(
        assembly.ARBOR_Z0 + arbor.PIN_Z
    )
    strap_outer = assembly.APINION_Z_FRONT - assembly.STRAP_AIR - assembly.STRAP_T
    assert 0.0 < strap_outer - assembly.ARBOR_COLLAR_Z[1] < spec.GAP_MAX


def test_registry_retains_make_critical_properties() -> None:
    import _config

    row = _config.parts("pinion-arbor-collar")
    assert row["number"] == "MHA-144"
    assert row["material_specification"]
    assert row["finish"]
    assert int(row["quantity"]) == 1
    assert "fit_class" not in row
