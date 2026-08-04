"""Contracts for saving comparison poses from Pose Studio."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "cad" / "comparisons" / "tools" / "pose_manifest.py"
COMPOSITE_PATH = REPO_ROOT / "cad" / "comparisons" / "tools" / "composite.py"
MANIFEST_PATH = REPO_ROOT / "cad" / "comparisons" / "manifest.json"

# Pairs deliberately left on the legacy content_fit path (null target_mm +
# manifest 2D align). EMPTY, and it should stay that way: content_fit fits the
# render to its own content and then nudges it with align, transforming a pose
# a second time, so the render never sits at the plate's scale. Pose Studio has
# written a concrete target_mm since it landed; the last two holdouts
# (ch30-p008/p009) were re-fitted in #409. Adding an id here is a deliberate
# regression — re-fit the pair in Pose Studio instead.
LEGACY_CONTENT_FIT_PAIRS: frozenset[str] = frozenset()


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_pose_manifest():
    return _load(MODULE_PATH, "pose_manifest_tested")


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


def _shipped_pairs() -> list[dict]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))["pairs"]


def test_every_shipped_pair_registers_as_camera_frame() -> None:
    """No pair silently falls back to content_fit.

    ``composite.blender_registration`` picks the framing from pose completeness,
    not from a per-pair setting: a null ``target_mm`` means content-fit plus the
    manifest's 2D align. That is invisible in the manifest itself — it shows up
    only as a render sitting at the wrong scale against its reference plate — so
    pin it here rather than waiting for someone to eyeball the gallery.
    """
    composite = _load(COMPOSITE_PATH, "composite_tested")
    legacy = {
        pair["id"] for pair in _shipped_pairs()
        if composite.blender_registration(pair) != "camera_frame"
    }
    assert legacy == set(LEGACY_CONTENT_FIT_PAIRS), (
        f"pairs on the legacy content_fit path: {sorted(legacy)}; re-fit them in "
        f"Pose Studio so the camera carries a concrete target_mm"
    )


def test_camera_frame_pairs_carry_a_neutral_align() -> None:
    """A camera_frame pair's 2D align is DEAD config — it must not look live.

    ``_fitted_render`` returns before reading align on the camera_frame path, so
    a leftover ``scale``/``dx_px``/``dy_px`` changes nothing while reading like a
    tuned offset. That is exactly what ch30-p008/p009 carried after their re-fit
    (scale 1.12, dy -233) and what made the stale framing hard to attribute.
    """
    pose_manifest = _load_pose_manifest()
    composite = _load(COMPOSITE_PATH, "composite_tested")
    offenders = {
        pair["id"]: pair.get("align")
        for pair in _shipped_pairs()
        if composite.blender_registration(pair) == "camera_frame"
        and pair.get("align", pose_manifest.NEUTRAL_ALIGN) != pose_manifest.NEUTRAL_ALIGN
    }
    assert not offenders, (
        f"camera_frame pairs carrying a non-neutral align (ignored at render time, "
        f"so it only misleads): {offenders}"
    )
