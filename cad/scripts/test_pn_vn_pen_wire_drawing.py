"""Offline contracts for the pen-wire drawing."""

from __future__ import annotations


CONFIGURATION = "PenWire"
STEM = "sh-vn-music-wire"


def test_pen_wire_preserves_purchased_material_and_installed_quantity() -> None:
    import _config

    row = _config.parts(STEM)
    assert row["process"] == "purchased"
    assert row["supplier_skus"] == ["9666K56"]
    assert row["material"] == "ASTM A228 music wire"
    assert int(row["configuration_quantities"][CONFIGURATION]) == 1
    assert int(row["quantity"]) == sum(row["configuration_quantities"].values())
