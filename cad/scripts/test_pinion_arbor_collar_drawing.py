"""Offline contracts for the pinion-arbor collar (R1a) and its drawing."""

from __future__ import annotations

from itertools import product
from pathlib import Path

import pytest

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
    """Ø15 OD, Ø8 +0.10/0 drilled bore, 20 long, pin hole centred."""
    assert (geometry.COLLAR_OD, geometry.BORE, geometry.COLLAR_LEN) == (15.0, 8.0, 20.0)
    assert spec.BORE_BAND == (0.10, 0.0)
    assert geometry.PIN_HOLE_Z == geometry.COLLAR_LEN / 2.0
    # The rig's one pin family and drill (pinion_strap_pin_spec, E-a).
    assert spec.PIN_HOLE == strap_pin.HOLE_DIA == arbor_pin.PIN_HOLE_DIA
    assert spec.PIN_HOLE_BAND == strap_pin.HOLE_BAND == (0.06, 0.0)
    assert spec.SLIDE_CLEARANCE_MIN > 0.0


def test_spring_pin_is_the_rig_family_and_never_proud() -> None:
    assert strap_pin.PIN_STANDARD == "ASME B18.8.2"
    assert spec.PIN_CALLOUT == strap_pin.PIN_SUPPLY
    assert spec.PIN_CALLOUT == "1/16 X 1/2 SLOTTED SPRING PIN (ASME B18.8.2)"
    assert spec.PIN_LEN == pytest.approx(12.7)
    # 1.15 sub-flush each side at nominal, still sub-flush at the worst case.
    assert (geometry.COLLAR_OD - spec.PIN_LEN) / 2.0 == pytest.approx(1.15)
    assert spec.PIN_SUB_FLUSH_WORST > 0.0
    assert spec.PIN_WALL_ENGAGEMENT_WORST >= 1.5
    assert spec.DRAWING_NOTES == f"SUPPLY 1X {spec.PIN_CALLOUT} LOOSE."


def test_webs_meet_the_u27_target_at_the_printed_worst_case() -> None:
    assert (geometry.COLLAR_OD - (geometry.BORE + spec.BORE_BAND[0])) / 2.0 == pytest.approx(3.45)
    assert spec.COLLAR_WALL_WORST == pytest.approx(3.05)
    assert spec.PIN_TO_END_WEB_WORST == pytest.approx(8.776, abs=1e-3)
    assert arbor_pin.PIN_HOLE_LIGAMENT_WORST == pytest.approx(3.126, abs=1e-3)
    for web in (
        spec.COLLAR_WALL_WORST,
        spec.PIN_TO_END_WEB_WORST,
        arbor_pin.PIN_HOLE_LIGAMENT_WORST,
    ):
        assert web >= 2.0


def test_collar_never_touches_the_front_strap_at_any_band_corner() -> None:
    """The gap stacks the drum station, the drum's front air, the strap, the
    arbor pin station and the collar length, each at its printed band."""
    assert spec.GAP_MIN == pytest.approx(0.40)
    assert spec.GAP_NOMINAL == pytest.approx(3.375)
    assert spec.GAP_MAX == pytest.approx(6.35)
    worst = min(
        (station - air - strap) - (pin + length / 2.0)
        for station, air, strap, pin, length in product(
            (arbor.DRUM_STATION - 0.8, arbor.DRUM_STATION + 0.8),
            arbor.drum_total_air(),
            (arbor.STRAP_T - 0.8, arbor.STRAP_T + 0.8),
            (38.2, 39.8),
            (19.2, 20.8),
        )
    )
    assert worst == pytest.approx(spec.GAP_MIN)
    assert worst > 0.0


def test_the_pin_never_enters_the_front_land() -> None:
    assert arbor_pin.PIN_HOLE_LAND_CLEARANCE >= 2.0


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    assert collar.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.END_KEEP) | set(drawing.PROFILE_KEEP)
    assert kept == marked
    assert set(drawing.DIMENSION_CALLOUTS) <= kept
    assert drawing.DIMENSION_CALLOUTS["PinHoleDia"] == "1/16 DRILL THRU"
    assert "MHA-102" in drawing.DIMENSION_CALLOUTS["BoreDia"]


def test_only_the_two_drilled_fits_carry_bands() -> None:
    assert model_toleranced_dimensions(collar) == {
        ("BoreProfile", "BoreDia"): "*deviations(BORE_BAND)",
        ("PinHoleProfile", "PinHoleDia"): "*deviations(PIN_HOLE_BAND)",
    }


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
