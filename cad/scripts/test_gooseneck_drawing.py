"""Offline contracts for the gooseneck drawing."""

from __future__ import annotations

import counter_spring_stock_geom as counter_stock
import gooseneck_geom as geom


def test_counter_spring_eye_is_retained_with_running_clearance() -> None:
    radial_retention = (geom.SCREW_HEAD_DIA - counter_stock.EYE_ID_MM) / 2.0
    radial_clearance = (counter_stock.EYE_ID_MM - geom.SCREW_SHANK_DIA) / 2.0

    assert radial_retention >= 1.0
    assert radial_clearance >= 0.25
    assert geom.SCREW_SHANK_LEN > counter_stock.END_OCCUPIED_WIDTH_MM


def test_brazed_plug_has_capillary_clearance_in_the_nominal_tube_bore() -> None:
    tube_id = geom.TUBE_DIA - 2.0 * geom.WALL_T
    nominal_radial_gap = (tube_id - geom.PLUG_DIA) / 2.0

    assert geom.PLUG_T > 0.0
    assert 0.051 <= nominal_radial_gap <= 0.127


def test_captive_screw_thread_and_slot_fit_the_body() -> None:
    assert geom.SCREW_THREAD_MAJOR_DIA <= geom.SCREW_SHANK_DIA
    assert geom.SCREW_SLOT_DEPTH < geom.SCREW_HEAD_T
    assert geom.SCREW_SLOT_W < geom.SCREW_HEAD_DIA


