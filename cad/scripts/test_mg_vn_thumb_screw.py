"""Purchased thumb screw material contract."""

from __future__ import annotations

import _config


def test_purchased_screw_has_vendor_material() -> None:
    row = _config.parts("sh-vn-thumb-screw")
    assert tuple(row["supplier_skus"]) == ("91882A221",)
    assert row["material"] == "Plain Carbon Steel"
