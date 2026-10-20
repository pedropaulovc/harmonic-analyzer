"""Purchased clamp screw material and vendor nominal contracts."""

from __future__ import annotations

import _config
import sh_vn_clamp_screw_spec as spec
from sh_vn_clamp_screw_spec import FILLISTER_SIZE


def test_purchased_screw_has_vendor_material() -> None:
    row = _config.parts("sh-vn-clamp-screw")
    assert tuple(row["supplier_skus"]) == ("90280A201",)
    assert row["material"] == "Plain Carbon Steel"


def test_shared_spec_reads_the_same_vendor_nominals() -> None:
    assert (spec.SHANK_DIA, spec.SHANK_LEN, spec.HEAD_H, spec.HEAD_DIA) == FILLISTER_SIZE[:4]
