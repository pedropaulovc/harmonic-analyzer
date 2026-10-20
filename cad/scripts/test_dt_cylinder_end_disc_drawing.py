"""Offline contracts for the south cylinder-bank end disc (MHA-DT-26) drawing."""

from __future__ import annotations

import pytest

import dt_cylinder_end_disc_spec as spec
import draw_dt_cylinder_end_disc as drawing


def test_loose_thickness_is_compensated_without_moving_the_gear_datum() -> None:
    import cylinder_bank_layout as bank
    from _printed_tolerance import printed_band_mm

    band = printed_band_mm(spec.THICKNESS_PLACES)
    assert spec.WASHER_THICK_TOLERANCE_MM == band
    assert spec.WASHER_THICK - band >= 2.0 - 1e-9
    assert bank.DATUM_CHAIN_STACK["south disc, mic-compensated"] == bank.MIC_RESIDUAL
    assert bank.MIC_RESIDUAL < band
    assert bank.FRONT_STRAP_INNER_Z + spec.WASHER_THICK == pytest.approx(
        bank.G0_CAM_FACE_Z
    )


def test_drilled_bore_limits_clear_the_arbor() -> None:
    import dt_cylinder_gear_shaft_spec as arbor
    from _printed_tolerance import drilled_oversize_mm

    assert spec.WASHER_BORE_BAND == (drilled_oversize_mm(), 0.0)
    assert spec.WASHER_BORE > arbor.SHAFT_DIA + arbor.SHAFT_DIA_BAND[0]


def test_disc_has_running_air_and_continuous_ring_capture_at_the_worst_limits() -> None:
    import cylinder_bank_layout as bank
    import ch_connecting_rod_spec as rod
    import dt_cylinder_gear_spec as gear

    budget = bank.SOUTH_DISC_CLEARANCE
    for name in ("cone worst", "engaged pinion worst"):
        assert budget[name] > spec.RUNNING_AIR_MM + spec.CLEARANCE_SPARE_MM
    # The whole bore edge remains captured, although the outermost ring rim
    # extends beyond this disc. Full-rim coverage is not axial retention.
    assert spec.WASHER_OD / 2.0 < gear.ECCENTRICITY + rod.RING_OUTER_RADIUS
    assert budget["retaining land"] > 0.0


def test_gear_od_disc_fails_the_real_drive_envelope(monkeypatch) -> None:
    import cylinder_bank_layout as bank
    import dt_cylinder_gear_spec as gear

    monkeypatch.setattr(spec, "WASHER_OD", gear.OUTSIDE_DIA)
    with pytest.raises(AssertionError, match="south retaining disc cone worst"):
        spec.installed_clearance_budget(sum(bank.DATUM_CHAIN_STACK.values()))


def test_disc_envelope_books_the_actual_south_datum_band_once() -> None:
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


@pytest.mark.parametrize("north", [(0.0, 0.0), (0.0, 0.01), (0.01, 0.01)])
def test_axial_section_rejects_a_nonhorizontal_or_degenerate_axis(
    monkeypatch, north
) -> None:
    monkeypatch.setattr(
        drawing, "model_points_in_view", lambda *_args, **_kwargs: ((0.0, 0.0), north)
    )
    with pytest.raises(RuntimeError, match="horizontal turning axis"):
        drawing._require_horizontal_axis(object(), object())
