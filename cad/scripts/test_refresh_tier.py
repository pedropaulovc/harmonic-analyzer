"""The refresh tier: which recorded-input changes may skip the insert/mate loop.

Offline: the decision is pure over per-input digests.
"""

from __future__ import annotations

from _refresh_tier import RefreshTier, classify_refresh

BUILDER = "cad/scripts/build_pd_paper_drive_assembly.py"
SHARED = "cad/scripts/_assembly_patterns.py"
PART = "cad/out/sldprt/pd-feed-roller.SLDPRT"
TOKEN = "cad/out/sldprt/.pd-feed-roller.execution"
RECIPE = frozenset({BUILDER, SHARED})
SAVED = {BUILDER: "b0", SHARED: "h0", PART: "p0", TOKEN: "t0"}


def _tier(**changes):
    return classify_refresh(SAVED, {**SAVED, **changes}, RECIPE)[0]


def test_part_change_takes_the_parts_tier():
    assert _tier(**{PART: "p1", TOKEN: "t1"}) is RefreshTier.PARTS
    assert _tier() is RefreshTier.PARTS


def test_recipe_change_rebuilds_full():
    assert _tier(**{SHARED: "h1"}) is RefreshTier.FULL
    assert _tier(**{BUILDER: "b1", TOKEN: "t1"}) is RefreshTier.FULL


def test_unknown_or_reshaped_inputs_rebuild_full():
    assert classify_refresh(None, SAVED, RECIPE)[0] is RefreshTier.FULL
    dropped = {k: v for k, v in SAVED.items() if k != SHARED}
    assert classify_refresh(SAVED, dropped, RECIPE - {SHARED})[0] is RefreshTier.FULL
