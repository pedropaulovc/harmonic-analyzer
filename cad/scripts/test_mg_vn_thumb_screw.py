"""Purchased thumb screw material contract."""

from __future__ import annotations

import asyncio
from contextlib import nullcontext
from types import SimpleNamespace

import pytest

import _config


def test_purchased_screw_has_vendor_material() -> None:
    row = _config.parts("sh-vn-thumb-screw")
    assert tuple(row["supplier_skus"]) == ("91882A221",)
    assert row["material"] == "Plain Carbon Steel"


@pytest.mark.parametrize("tip_scale", (1.0, 0.5))
def test_authored_shank_uses_the_shared_contact_tip_geometry(monkeypatch, tip_scale) -> None:
    import _sketch
    from sh_vn_thumb_screw_spec import THUMB_SPEC, TIP_CHAMFER
    from diagnostics import diag_mcmaster_lib, diag_mcmaster_thumb

    class ShankCaptured(Exception):
        pass

    class Adapter:
        currentSketchManager = SimpleNamespace(CreateCenterLine=lambda *_args: object())

        async def create_sketch(self, _plane):
            return SimpleNamespace(is_success=True, data={}, error=None)

        async def exit_sketch(self):
            raise ShankCaptured

    points = []

    async def capture(_adapter, profile):
        points.extend(profile)

    monkeypatch.setattr(_sketch, "add_line_chain", capture)
    monkeypatch.setattr(diag_mcmaster_lib, "no_sketch_inference", lambda _adapter: nullcontext())
    stock = dict(THUMB_SPEC, tip_chamfer=TIP_CHAMFER * tip_scale)
    with pytest.raises(ShankCaptured):
        asyncio.run(diag_mcmaster_thumb.build_thumb_screw(Adapter(), stock))
    rim, tip = points[-3:-1]
    assert rim[1] - tip[1] == pytest.approx(stock["tip_chamfer"])
    assert tip[0] == pytest.approx(stock["major_r"] - stock["tip_chamfer"])
    # Non-default tip_scale is the pre-fix/ignored-parameter mutation control:
    # the clamp's contact data must actually drive the authored profile.
