"""Purchased brass screw material and vendor nominal contracts."""

from __future__ import annotations

import _config
import sh_vn_brass_fillister_screw_spec as spec
from sh_vn_brass_fillister_screw_spec import BF_HEAD_R, BF_HH, BF_LEN, BF_MAJOR_R


def test_purchased_screw_has_vendor_material() -> None:
    row = _config.parts("sh-vn-brass-fillister-screw")
    assert tuple(row["supplier_skus"]) == ("90114A511",)
    assert row["material"] == "Brass"


def test_shared_spec_reads_the_same_vendor_nominals() -> None:
    assert spec.THREAD == "#4-40"
    assert spec.HEAD_DIA == 2.0 * BF_HEAD_R
    assert spec.HEAD_H == BF_HH
    assert spec.SHANK_DIA == 2.0 * BF_MAJOR_R
    assert spec.SHANK_LEN == BF_LEN
