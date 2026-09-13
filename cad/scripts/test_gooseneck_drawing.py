"""Offline contracts for the gooseneck drawing."""

from __future__ import annotations

import build_gooseneck as part
import counter_spring_stock_geom as counter_stock
import gooseneck_geom as geom


def test_counter_spring_eye_is_retained_with_running_clearance() -> None:
    radial_retention = (geom.SCREW_HEAD_DIA - counter_stock.EYE_ID_MM) / 2.0
    radial_clearance = (counter_stock.EYE_ID_MM - geom.SCREW_SHANK_DIA) / 2.0

    assert radial_retention >= 1.0
    assert radial_clearance >= 0.25
    assert geom.SCREW_SHANK_LEN > counter_stock.END_OCCUPIED_WIDTH_MM


def test_end_plug_fits_inside_the_tube_wall() -> None:
    tube_id = geom.TUBE_DIA - 2.0 * geom.WALL_T

    assert geom.PLUG_T > 0.0
    assert tube_id < part.PLUG_DIA < geom.TUBE_DIA
