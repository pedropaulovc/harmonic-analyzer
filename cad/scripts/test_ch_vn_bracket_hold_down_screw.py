"""MHA-CH-VN-57 is authored at its own 90280A196 #8-32 x 5/8 in size."""

from __future__ import annotations

import asyncio

import pytest

from diagnostics import diag_build_90280A196 as recipe


def test_native_author_builds_the_five_eighths_inch_screw(monkeypatch) -> None:
    calls = []

    async def capture(_adapter, sku, size):
        calls.append((sku, size))

    monkeypatch.setattr(recipe, "build_fillister", capture)
    asyncio.run(recipe.build_90280A196(object()))
    [(sku, (major, length, _head_h, _head_dia, pitch))] = calls
    assert sku == "90280A196"
    assert length == pytest.approx(5.0 / 8.0 * 25.4)
    assert major == pytest.approx(0.164 * 25.4)
    assert pitch == pytest.approx(25.4 / 32.0)
