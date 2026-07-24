"""Focused contracts for channel bushing-bank pattern retries."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

import build_channel_assembly as channel


def test_flip_retry_discovers_the_new_component_suffix_range(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    active = {"pivot-bushing-1"}
    pattern_calls: list[bool] = []
    verified: list[list[str]] = []

    class Adapter:
        async def pattern_components_linear(self, params):
            pattern_calls.append(params.flip_direction)
            first_suffix = 2 if len(pattern_calls) == 1 else 4
            active.update(
                f"pivot-bushing-{suffix}"
                for suffix in range(first_suffix, first_suffix + 2)
            )
            return SimpleNamespace(name=f"Pattern{len(pattern_calls)}")

    def require_component(_adapter, name: str):
        if name not in active:
            raise RuntimeError(f"component not found: {name!r}")
        return name

    def delete_pattern(_adapter, name: str) -> None:
        assert name == "Pattern1"
        active.difference_update({"pivot-bushing-2", "pivot-bushing-3"})

    def verify(_adapter, names, _expected, _label):
        verified.append(list(names))
        if len(verified) == 1:
            raise RuntimeError("pattern direction sense flipped")
        return list(names)

    monkeypatch.setattr(channel, "check", lambda _label, value: value)
    monkeypatch.setattr(channel, "require_component", require_component)
    monkeypatch.setattr(channel, "delete_assembly_feature", delete_pattern)
    monkeypatch.setattr(channel, "_verify_pattern_z", verify)

    names = asyncio.run(
        channel._pattern_bank(
            Adapter(),
            "pivot-bushing-1",
            "pivot-bushing",
            "BankZ",
            [0.0, -7.0, -14.0],
        )
    )

    assert pattern_calls == [True, False]
    assert verified == [
        ["pivot-bushing-1", "pivot-bushing-2", "pivot-bushing-3"],
        ["pivot-bushing-1", "pivot-bushing-4", "pivot-bushing-5"],
    ]
    assert names == ["pivot-bushing-1", "pivot-bushing-4", "pivot-bushing-5"]
