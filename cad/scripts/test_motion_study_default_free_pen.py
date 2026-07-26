"""Offline contracts for the motion study's default-free pen handling."""

from __future__ import annotations

import asyncio

import build_motion_study_springs as springs


class _Adapter:
    def __init__(self) -> None:
        self.suppressed: list[object] = []

    async def suppress_mate(self, params):
        self.suppressed.append(params)
        return object()


def _mate(name: str) -> tuple[object, object, str, object, object, object]:
    return (object(), object(), name, springs.DISTANCE, object(), object())


def _install_mate_scan(monkeypatch, names: list[str]) -> None:
    monkeypatch.setattr(springs, "_sub_model", lambda *_args: (None, object()))
    monkeypatch.setattr(
        springs,
        "_iter_mates",
        lambda *_args, **_kwargs: [_mate(name) for name in names],
    )
    monkeypatch.setattr(springs, "_lone_real", lambda *_args: "pen-rod-1")
    monkeypatch.setattr(springs, "_family", lambda _name: "pen-rod")
    monkeypatch.setattr(springs, "log", lambda *_args: None)


def test_default_free_pen_keeps_depth_and_across_locators(monkeypatch) -> None:
    _install_mate_scan(monkeypatch, ["pen-rod slide depth", "pen-rod slide across"])
    adapter = _Adapter()

    asyncio.run(springs._suppress_pen_travel(adapter))

    assert adapter.suppressed == []


def test_only_explicit_transient_travel_driver_is_suppressed(monkeypatch) -> None:
    _install_mate_scan(
        monkeypatch,
        ["pen-rod slide depth", "DRIVE_pen_travel", "pen-rod slide across"],
    )
    monkeypatch.setattr(springs, "check", lambda _label, result: result)
    adapter = _Adapter()

    asyncio.run(springs._suppress_pen_travel(adapter))

    assert len(adapter.suppressed) == 1
    assert adapter.suppressed[0].name == "DRIVE_pen_travel"
