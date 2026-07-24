"""Repro for pose_to_meshprobe's roll-sign claim (SolidWorks-free, no Blender).

``convert()`` NEGATES roll because meshprobe's ``view-orbit --roll`` turns the
camera the opposite way to blender_worker's ``roll_deg``. That is a claim about
two renderers' conventions, so it gets a re-runnable check rather than a comment:

* ``test_roll_is_negated`` pins the conversion itself (pure, always runs).
* ``test_rendered_tilt_matches_blender`` is the empirical half — it measures the
  dominant vertical-line tilt in the meshprobe render and the Blender render of
  the SAME pair and asserts they agree in sign and magnitude. It SKIPS unless
  both renders exist, since it needs a Blender seat + a meshprobe run:

      uv run comparisons/tools/pose_to_meshprobe.py --pair ch11-p002-img05 | bash
      uv run pytest comparisons/tools/test_pose_to_meshprobe.py
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

import pose_to_meshprobe as p2m

REPO = Path(__file__).resolve().parents[2]
PAIR = "harmonic_analyzer--ch11-p002-img05"
MESHPROBE_PNG = REPO / "comparisons" / "render" / "meshprobe" / f"{PAIR}.png"
BLENDER_JPG = REPO / "comparisons" / "render" / f"{PAIR}.jpg"

# A level camera (el=0) renders parallel verticals, so one tilt angle describes
# the whole frame — that is why this pair is the fixture.
ROLL_DEG = -1.81
BBOX = ((-200.0, -300.0, -150.0), (250.0, 400.0, 200.0), 700.0, [])


def _pair(roll: float) -> dict:
    return {
        "id": PAIR,
        "model": "harmonic_analyzer",
        "camera": {"mode": "euler", "az_deg": -133.18, "el_deg": 0.0, "roll_deg": roll,
                   "zoom": 10.24, "target_mm": [-12.78, 94.46, -55.58],
                   "perspective": {"focal_length_mm": 86.92}},
    }


def test_roll_is_negated():
    """Emitted roll is the manifest roll with the sign flipped."""
    cvt = p2m.convert(_pair(ROLL_DEG), BBOX, 2240, 1793)
    assert cvt["roll_deg"] == pytest.approx(-ROLL_DEG, abs=1e-4)


def test_zero_roll_stays_zero():
    """The negation must not introduce a -0.0 or an offset at roll=0."""
    cvt = p2m.convert(_pair(0.0), BBOX, 2240, 1793)
    assert cvt["roll_deg"] == pytest.approx(0.0, abs=1e-9)


def test_roll_does_not_leak_into_framing():
    """Only the emitted angle flips — the framing axes still use the MODEL roll,
    so target/distance are identical either way."""
    a = p2m.convert(_pair(ROLL_DEG), BBOX, 2240, 1793)
    b = p2m.convert(_pair(-ROLL_DEG), BBOX, 2240, 1793)
    assert a["target_mm"] == b["target_mm"]
    assert a["distance_mm"] == pytest.approx(b["distance_mm"], rel=1e-9)


# --------------------------------------------------------------------------- #
# empirical half — measure the tilt actually rendered
# --------------------------------------------------------------------------- #
def dominant_vertical_tilt(path: Path, lo: float = -8.0, hi: float = 8.0,
                           step: float = 0.02) -> float:
    """Tilt (deg) of the dominant near-vertical line family, via a Radon shear scan.

    A per-pixel angle histogram cannot do this: JPEG block edges and single-pixel
    aliasing both pile up at exactly 0 deg and swamp the real peak. Shearing by a
    candidate angle and scoring sum(column_sum**2) only rewards edges that stay
    coherent over the full image height, which the artefacts do not.
    """
    from PIL import Image

    a = np.asarray(Image.open(path).convert("L"), dtype=np.float64)
    gy, gx = np.gradient(a)
    e = np.abs(gx)
    e[np.abs(gy) > np.abs(gx)] = 0.0
    e[e < np.percentile(e, 96.0)] = 0.0

    h, w = e.shape
    y = np.arange(h) - h / 2.0
    rows = np.repeat(np.arange(h)[:, None], w, axis=1)
    cols = np.arange(w)[None, :]

    def best_of(thetas):
        scores = np.empty(len(thetas))
        for n, t in enumerate(thetas):
            idx = cols + (math.tan(math.radians(t)) * y)[:, None]
            i0 = np.floor(idx).astype(np.int64)
            frac = idx - i0
            ok = (i0 >= 0) & (i0 < w - 1)
            src = np.clip(i0, 0, w - 2)
            val = np.where(ok, e[rows, src] * (1 - frac) + e[rows, src + 1] * frac, 0.0)
            scores[n] = float((val.sum(axis=0) ** 2).sum())
        return float(thetas[int(np.argmax(scores))])

    # Coarse-to-fine: a full [lo, hi] sweep at the fine step is ~800 shears and
    # dominates the test's runtime for no extra accuracy. The peak is broad
    # enough (degrees, not arc-minutes) that a 0.5 deg sweep localises it, then
    # one +/-0.6 deg window resolves it.
    coarse = best_of(np.arange(lo, hi + 0.25, 0.5))
    return best_of(np.arange(coarse - 0.6, coarse + 0.6 + step / 2, step))


@pytest.mark.skipif(not (MESHPROBE_PNG.exists() and BLENDER_JPG.exists()),
                    reason="needs both renders; see this module's docstring")
def test_rendered_tilt_matches_blender():
    """The meshprobe render leans the same way as the Blender render it mirrors.

    Un-negated, these come out at -1.813 vs +1.812 — equal magnitude, opposite
    sign — which is the bug this test exists to catch.
    """
    mp = dominant_vertical_tilt(MESHPROBE_PNG)
    bl = dominant_vertical_tilt(BLENDER_JPG)
    assert mp == pytest.approx(bl, abs=0.15), (
        f"vertical-line tilt differs: meshprobe {mp:+.3f} deg vs blender {bl:+.3f} deg; "
        f"a near-exact sign flip means the roll convention moved again")
    assert mp == pytest.approx(-ROLL_DEG, abs=0.15)
