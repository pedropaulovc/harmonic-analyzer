"""Offline contracts of the shared music-wire purchase."""

from __future__ import annotations

import _config
import build_sh_vn_music_wire as part
import sh_vn_music_wire_lever_geom as geom

CONFIGURATION = "LeverWire"
STEM = "sh-vn-music-wire"


def test_wire_registry_quantities_count_installed_members() -> None:
    row = _config.parts(STEM)
    assert row["process"] == "purchased"
    assert row["supplier_skus"] == ["9666K142"]
    assert int(row["quantity"]) == sum(row["configuration_quantities"].values())
    assert int(row["configuration_quantities"][CONFIGURATION]) == 1


def test_balloon_station_is_midway_along_the_free_run() -> None:
    assert part.BALLOON_RING_STATION == geom.WIRE_LEN / 2.0
