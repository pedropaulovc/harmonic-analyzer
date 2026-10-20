"""Offline contracts for the south cylinder-bank end disc (MHA-DT-26) drawing."""

from __future__ import annotations

from pathlib import Path

import build_dt_cylinder_end_disc as part
import dt_cylinder_end_disc_spec as spec
import draw_dt_cylinder_end_disc as drawing
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/dt-cylinder-end-disc.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/dt-cylinder-end-disc.pdf")
    assert DRAWINGS_BY_NAME["dt_cylinder_end_disc"].script == Path(drawing.__file__).resolve()


def test_every_marked_dimension_has_one_view_and_model_places() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP) == marked
    assert not set(drawing.FRONT_KEEP) & set(drawing.RIGHT_KEEP)
    assert {
        (feature, name) for feature, names in spec.DRAWING_PRECISION.items() for name in names
    } == {(feature, name) for feature, names in spec.DRAWING_DIMENSIONS.items() for name in names}


def test_thickness_is_held_because_it_sits_in_the_bank_datum_chain() -> None:
    import cylinder_bank_layout as bank

    # The south disc is mic-compensated to keep gear 0's cam face on datum.
    chain = bank.DATUM_CHAIN_STACK["south disc, mic-compensated"]
    assert chain == bank.MIC_RESIDUAL < spec.WASHER_THICK_TOLERANCE_MM
    # The bore can never close onto the O9.525 arbor.
    assert spec.WASHER_BORE_BAND[1] == 0.0
    assert spec.WASHER_BORE - 9.525 > 0.0


def test_single_brass_disc_retains_the_bore_thickness_and_ordinary_od_band() -> None:
    import _config
    from _printed_tolerance import printed_band_mm

    row = _config.parts("dt-cylinder-end-disc")
    assert spec.WASHER_OD == part.DISC_DIA == 55.0
    assert spec.OUTSIDE_DIA_BAND_MM == printed_band_mm(spec.OUTSIDE_DIA_PLACES) == 0.8
    assert part.BORE_DIA == spec.WASHER_BORE == 9.6
    assert part.DISC_THICK == spec.WASHER_THICK == 1.5
    assert part.MATERIAL == row["material"] == "Brass"
    assert row["material_specification"] == "C36000 free-machining brass"
    assert row["quantity"] == 1


def test_disc_has_running_air_and_continuous_ring_capture_at_the_worst_limits() -> None:
    import math
    import pytest
    import cylinder_bank_layout as bank
    import ch_connecting_rod_spec as rod
    import dt_cylinder_gear_spec as gear

    budget = bank.SOUTH_DISC_CLEARANCE
    assert budget["cone worst"] == pytest.approx(0.510139887, abs=1e-8)
    assert budget["engaged pinion worst"] == pytest.approx(3.543404853, abs=1e-8)
    assert budget["retaining land"] == pytest.approx(2.435714680, abs=1e-8)
    assert math.degrees(budget["disc tilt radians"]) == pytest.approx(7.65934, abs=1e-5)
    assert budget["disc bore float"] == pytest.approx(0.0975)
    for name in ("cone worst", "engaged pinion worst"):
        assert budget[name] > spec.RUNNING_AIR_MM + spec.CLEARANCE_SPARE_MM
    # The whole bore edge remains captured, although the outermost ring rim
    # extends beyond this disc. Full-rim coverage is not axial retention.
    assert spec.WASHER_OD / 2.0 < gear.ECCENTRICITY + rod.RING_OUTER_RADIUS
    assert budget["retaining land"] > 0.0


def test_gear_od_disc_fails_the_real_drive_envelope(monkeypatch) -> None:
    import pytest
    import cylinder_bank_layout as bank
    import dt_cylinder_gear_spec as gear

    monkeypatch.setattr(spec, "WASHER_OD", gear.OUTSIDE_DIA)
    with pytest.raises(AssertionError, match="south retaining disc cone worst"):
        spec.installed_clearance_budget(sum(bank.DATUM_CHAIN_STACK.values()))


def test_disc_envelope_books_the_actual_south_datum_band_once() -> None:
    import pytest
    import cone_line
    import cylinder_bank_layout as bank

    datum = sum(bank.DATUM_CHAIN_STACK.values())
    normal = spec.installed_clearance_budget(datum)
    shifted = spec.installed_clearance_budget(datum + 0.10)
    assert normal["cone worst"] - shifted["cone worst"] == pytest.approx(
        0.10 * cone_line.SIN_I
    )
    assert shifted["engaged pinion worst"] == normal["engaged pinion worst"]
    assert shifted["retaining land"] == normal["retaining land"]
