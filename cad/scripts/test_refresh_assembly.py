"""SolidWorks-free unit coverage for incremental assembly refresh policy."""

from __future__ import annotations

import json

import pytest

import _assembly


def _manifest(tmp_path, monkeypatch, payload):
    path = tmp_path / ".channel.dof.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(_assembly, "dof_manifest_path", lambda _name: path)
    return path


def test_refresh_without_dof_manifest_requires_fully_defined(tmp_path, monkeypatch):
    path = tmp_path / ".frame.dof.json"
    monkeypatch.setattr(_assembly, "dof_manifest_path", lambda _name: path)
    calls = []
    monkeypatch.setattr(
        _assembly,
        "assert_components_fully_defined",
        lambda adapter: calls.append(adapter),
    )
    monkeypatch.setattr(
        _assembly,
        "assert_free_dof_necessity",
        lambda *_args, **_kwargs: pytest.fail("free-DOF gate must not run"),
    )
    adapter = object()

    _assembly.assert_refresh_dof(adapter, "frame")

    assert calls == [adapter]


def test_refresh_uses_manifest_backed_free_dof_gate(tmp_path, monkeypatch):
    _manifest(
        tmp_path,
        monkeypatch,
        {
            "stem": "channel",
            "specs": [
                {"key": "rocker_angle_00", "verify": ["rocker-arm-1", [0, 0, 0]]},
                {"key": "rod_swing_00", "verify": ["connecting-rod-1", [0, 0, 0]]},
                {"key": "bar_amplitude_00", "verify": ["amplitude-bar-1", [0, 0, 0]]},
            ],
        },
    )
    monkeypatch.setattr(
        _assembly,
        "assert_components_fully_defined",
        lambda *_args, **_kwargs: pytest.fail("fully-defined gate must not run"),
    )
    calls = []
    monkeypatch.setattr(
        _assembly,
        "assert_free_dof_necessity",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )
    adapter = object()

    _assembly.assert_refresh_dof(adapter, "channel")

    assert calls == [
        (
            (adapter, 3),
            {
                "required_instances": (
                    "rocker-arm-1",
                    "connecting-rod-1",
                    "amplitude-bar-1",
                )
            },
        )
    ]


def test_refresh_rejects_manifest_without_verify_target(tmp_path, monkeypatch):
    path = _manifest(
        tmp_path,
        monkeypatch,
        {"stem": "channel", "specs": [{"key": "rocker_angle_00", "verify": None}]},
    )

    with pytest.raises(RuntimeError, match="has no verify component instance"):
        _assembly.assert_refresh_dof(object(), "channel")

    assert path.exists()


def test_refresh_rejects_manifest_for_another_assembly(tmp_path, monkeypatch):
    _manifest(
        tmp_path,
        monkeypatch,
        {
            "stem": "drive-train",
            "specs": [{"key": "crank_angle", "verify": ["crankshaft-1", [0, 0, 0]]}],
        },
    )

    with pytest.raises(RuntimeError, match="expected 'channel'"):
        _assembly.assert_refresh_dof(object(), "channel")
