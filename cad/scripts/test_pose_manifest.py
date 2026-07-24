"""Contracts for saving comparison poses from Pose Studio."""

from __future__ import annotations

import importlib.util
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "comparisons" / "tools" / "pose_manifest.py"


def _load_pose_manifest():
    spec = importlib.util.spec_from_file_location("pose_manifest_tested", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_update_pair_pose_resets_unpreviewed_framing_transforms() -> None:
    pose_manifest = _load_pose_manifest()
    pair = {
        "camera": {
            "mode": "euler",
            "frame_components": ["cone_gear"],
        },
        "align": {"scale": 1.13, "dx_px": 20, "dy_px": -247},
    }

    cleared_frame, reset_align = pose_manifest.update_pair_pose(
        pair,
        az_deg=-149.999,
        el_deg=6.799,
        roll_deg=0.004,
        zoom=1.1546,
        target_mm=[-21.264, 526.576, -55.126],
        focal_length_mm=50.504,
    )

    assert cleared_frame
    assert reset_align
    assert pair["align"] == {"scale": 1.0, "dx_px": 0, "dy_px": 0}
    assert pair["camera"] == {
        "mode": "euler",
        "az_deg": -150.0,
        "el_deg": 6.8,
        "roll_deg": 0.0,
        "zoom": 1.155,
        "target_mm": [-21.26, 526.58, -55.13],
        "perspective": {"focal_length_mm": 50.5},
    }


def test_update_pair_pose_preserves_neutral_align_and_orthographic_mode() -> None:
    pose_manifest = _load_pose_manifest()
    pair = {"camera": {}, "align": dict(pose_manifest.NEUTRAL_ALIGN)}

    cleared_frame, reset_align = pose_manifest.update_pair_pose(
        pair,
        az_deg=1.0,
        el_deg=2.0,
        roll_deg=3.0,
        zoom=4.0,
        target_mm=None,
        focal_length_mm=None,
    )

    assert not cleared_frame
    assert not reset_align
    assert pair["camera"]["target_mm"] is None
    assert pair["camera"]["perspective"] is None
