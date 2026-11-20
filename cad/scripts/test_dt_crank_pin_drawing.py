"""Offline contracts for the crank-pin drawing."""

from __future__ import annotations

from pathlib import Path

import pytest

import build_dt_crank_pin as part
import dt_crank_pin_notes as notes
import dt_crank_pin_spec
import draw_dt_crank_pin as drawing
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/dt-crank-pin.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/dt-crank-pin.pdf")
    assert drawing.PNG.as_posix().endswith("/png/dt-crank-pin_drawing.png")
    assert DRAWINGS_BY_NAME["dt_crank_pin"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is dt_crank_pin_spec.DRAWING_DIMENSIONS
    marked = set().union(*dt_crank_pin_spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.FRONT_KEEP) == marked
    assert set(drawing.DRAWING_PRECISION_BY_NAME) == marked
    assert set(dt_crank_pin_spec.DIMENSION_CALLOUTS) <= marked
    assert drawing.PIN_LENGTH == dt_crank_pin_spec.PIN_LENGTH


def test_cross_hole_prints_natively_not_in_a_note() -> None:
    """Rule 7: the keeper-ring hole's size and station are model dimensions
    (a drilled hole at three places, a routine station at two), not note
    text."""
    spec = dt_crank_pin_spec
    assert spec.DRAWING_DIMENSIONS["RingHoleProfile"] == {"RingHoleX", "RingHoleDia"}
    assert spec.DRAWING_PRECISION["RingHoleProfile"] == {
        "RingHoleX": 2,
        "RingHoleDia": 3,
    }
    for value in (spec.RING_HOLE_DIA, spec.RING_HOLE_X, spec.PIN_LENGTH):
        inch = value / 25.4
        for places in (2, 3):
            for text in (notes.TAPER_CALLOUT, notes.SHEET_NOTES):
                assert f"{inch:.{places}f}".lstrip("0") not in text


def test_cross_hole_station_text_clears_its_extension_lines() -> None:
    """Rule 14: the .15 station text must not straddle its 7.62-mm paper span
    (budgeted at the template's wider "3.70")."""
    text_x, text_y = drawing.FRONT_KEEP["RingHoleX"]
    # The unchanged template's copied PDF measures 9.051 mm across "3.70".
    text_half_width = 0.0046
    outside_arrow_tail = 0.00635
    clearance = 0.002
    right_witness = max(drawing.BIG_END_EDGE[0], drawing.RING_HOLE_CENTER[0])
    assert text_x - text_half_width >= right_witness + outside_arrow_tail + clearance
    # Keep the whole row left of the taper leader and above the pin outline.
    assert text_x + text_half_width + clearance < drawing.TAPER_SILHOUETTE_PICK[0]
    pin_top = (
        drawing.FRONT_CENTER[1]
        + dt_crank_pin_spec.BIG_END_DIA * drawing.SHEET_SCALE[0] / 2000.0
    )
    assert text_y > pin_top + clearance


def test_pin_is_the_bought_no_3_taper_pin_cross_drilled_only() -> None:
    """Owner ruling 2026-11-20 (#2368, "B"): a stock ASME B18.8.2 No. 3 x
    1-3/4 pin; the sheet names it once and dimensions only the cross-hole."""
    import _config

    spec = dt_crank_pin_spec
    assert spec.BIG_END_DIA == pytest.approx(0.219 * 25.4)
    assert spec.PIN_LENGTH == pytest.approx(1.75 * 25.4)
    # The standard 1:48 on diameter gives the catalogue's .183 small end.
    assert spec.BIG_END_DIA - spec.SMALL_END_DIA == pytest.approx(spec.PIN_LENGTH / 48.0)
    assert round(spec.SMALL_END_DIA / 25.4, 3) == 0.183
    assert set(spec.DRAWING_DIMENSIONS) == {"RingHoleProfile"}
    assert _config.parts("dt-crank-pin")["supplier_skus"] == [spec.SKU]
    stock = " ".join(notes.STOCK_NOTE.split())
    assert f"McMASTER-CARR {spec.SKU}, {spec.DESIGNATION} ({spec.STANDARD})" in stock
    assert "ADD THE RING HOLE ONLY" in stock
    assert "UNDIMENSIONED GEOMETRY IS REFERENCE" in stock
    # Rule 7: at most four short lines of part-specific notes.
    assert len(notes.SHEET_NOTES.splitlines()) <= 4
    assert all(len(row) <= 73 for row in notes.SHEET_NOTES.splitlines())


def test_ring_hole_station_runs_from_the_crowned_end_rim() -> None:
    """Codjiflo on #3158: ASME B18.8.2 ends are crowned about .03 high, more
    than the station's .XX band, so the station names the rim (the model's
    flat big end), words only, flagged on the station itself."""
    callout = notes.RING_HOLE_STATION_CALLOUT_ABOVE
    assert " ".join(callout.split()) == "FROM END RIM"
    assert not any(ch.isdigit() for ch in callout)
    assert len(callout.splitlines()) <= 2


def test_matched_taper_fit_names_both_mates() -> None:
    """Rule 4: the hub and shaft are taper-reamed together to suit the pin,
    so the fit names both mates by name and number and states the
    acceptance, in the numbered note the taper callout links (rule 7)."""
    import _config

    assert notes.TAPER_CALLOUT.splitlines()[-1] == f"SEE NOTE {notes.TAPER_NOTE_NUMBER}"
    note = " ".join(notes.TAPER_NOTE.split())
    assert note.startswith(f"{notes.TAPER_NOTE_NUMBER}. ")
    for stem, name in (("dt-crank-hub", "CRANK HUB"), ("dt-crankshaft", "CRANKSHAFT")):
        assert f"{name} {_config.parts(stem)['number']}" in note
    assert f"KEEPER RING {_config.parts('dt-crank-pin-ring')['number']}" in note
    assert len(notes.TAPER_NOTE.splitlines()) <= 4


def test_web_shortfall_is_stated_on_the_hole_callout() -> None:
    """Rule 20: the pending web shortfall prints where it applies."""
    callout = dt_crank_pin_spec.DIMENSION_CALLOUTS["RingHoleDia"]
    assert callout.splitlines()[-1] == dt_crank_pin_spec.CROSS_HOLE_WEB_CALLOUT


def test_the_one_note_is_flagged_on_the_taper() -> None:
    for text in (notes.TAPER_CALLOUT, notes.TAPER_NOTE):
        # Deburr/edge-break is a title-block note; repeating it here would duplicate it.
        assert "DEBURR" not in text
        assert "X.XX" not in text


def test_pinned_taper_carries_no_roughness_symbol() -> None:
    """Rule 6: a pinned drive fit neither runs nor slides."""
    assert dt_crank_pin_spec.SURFACE_FINISHES == ()


def test_view_scales_are_explicit() -> None:
    # Rule 9: every orthographic view is at the sheet scale, so the end view
    # is a projected view with no label and no scale caption.
    assert drawing.SHEET_SCALE == (2.0, 1.0)


def test_part_stamps_make_critical_properties() -> None:
    import _config

    config = _config.parts("dt-crank-pin")
    assert config["number"] == "MHA-DT-09"
    assert dt_crank_pin_spec.SKU in str(config["material_specification"])
    assert "12L14" in str(config["material_specification"])
    assert config["finish"]
    assert int(config["quantity"]) == 1


def test_crank_keeper_ring_threads_the_pin_hole_clear_of_the_arm() -> None:
    import build_dt_drive_train_assembly as drive
    import dt_crank_pin_ring_spec as ring
    import pytest

    # The round ring's wire arc, centred in the straight cross-hole, keeps air
    # to the hole wall across the whole pin section, at nominal and with the
    # smallest printed ring through the fattest printed pin section.
    assert ring.HOLE_AIR >= ring.RING_HOLE_AIR
    assert ring.HOLE_AIR_WORST >= ring.RING_HOLE_AIR
    # The side web is a named exception (under the .080 target): at the
    # printed worst case it holds the .060 floor, and the sheet states that
    # value, never more than the limits give.
    from _inch_wall_limits import WALL_FLOOR_MM, WALL_TARGET_MM
    from _printed_tolerance import drilled_oversize_mm, printed_band_mm

    unit = dt_crank_pin_spec.UNIT
    drilled = drilled_oversize_mm(unit=unit)
    worst_web = (
        dt_crank_pin_spec.PIN_DIA_AT_RING_HOLE_MIN
        - dt_crank_pin_spec.RING_HOLE_DIA
        - drilled
    ) / 2.0
    assert worst_web >= WALL_FLOOR_MM
    assert worst_web - 0.0254 < dt_crank_pin_spec.CROSS_HOLE_WEB_MIN <= worst_web
    # The ligament to the big-end face meets the .080 target with margin for
    # twice the .XX station band (the station runs from the as-bought big
    # end) and the DRILLED HOLES oversize.
    ligament = (
        dt_crank_pin_spec.RING_HOLE_X
        - 2.0 * printed_band_mm(2, unit=unit)
        - (dt_crank_pin_spec.RING_HOLE_DIA + drilled) / 2.0
    )
    assert ligament >= WALL_TARGET_MM
    # It reaches clear of the pin: the ring's inside edge past the pin surface.
    pin_radius = ring.PIN_DIA_AT_HOLE / 2.0
    assert ring.RING_FAR_X - ring.WIRE_DIA / 2.0 - pin_radius >= 3.0
    assert ring.PIN_PROUD == pytest.approx(
        dt_crank_pin_spec.RING_HOLE_X + ring.WIRE_DIA / 2.0 + ring.HUB_CLEARANCE
    )
    # One pin station everywhere: the drive train places the pin, and the
    # interference contract sizes the pin's allowed overlaps, at that value.
    import _dt_drive_train_interference as contracts

    assert drive.PIN_PROUD == ring.PIN_PROUD
    assert contracts._PIN_PROUD == ring.PIN_PROUD
    assert drive.CRANK_RING_Y == pytest.approx(drive.Y_CRANK)
