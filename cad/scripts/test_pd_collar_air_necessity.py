"""The collar-to-disc air is one budget shared by five tight features.

Delegated ruling D21 (2026-11-25, Main, no precedent; owner review #2144):
the MHA-PD-17 spigot length opened to the title block spends part of the
air; the two Ø.126 REAMs keep it (either bore .002 looser closes the air
under its floor), and the MHA-PD-28 hub face station and MHA-PD-00's seat
feeler stay tight by accept entries, because each alone could still open
but neither can with a bore.  The registers and the two accept entries quote
these airs; this test derives every one of them from ``pd_cluster_air``, so
a reason there is a checked number, not a narrated one (#3528: an earlier
probe read 0.1105 mm for all five opened at once by patching the modules in
the wrong order; the air is 0.0604 at the bands as they then stood).
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest
import yaml

import pd_cluster_air as AIR
import pd_transgear_disc_hub_geometry as HUB_GEOMETRY
import transgear_cluster_fit as FIT
from _printed_tolerance import printed_band_mm

CONFIG = Path(__file__).resolve().parents[1] / "config"
LOOSER = 0.002 * 25.4  # rule 4's necessity test: the feature .002 in loose

HUB_STATION = FIT.PH[0]
SEAT = FIT.PS[0]
SLEEVE_COCK = "sleeve cocking on the pin"
BUSHING_COCK = "front bushing and ring cocking on the pin"


def _opened(*features: str) -> float:
    """The statistical collar air with each named feature .002 looser."""
    terms = dict(AIR.COLLAR_AIR.terms)
    for feature in features:
        if feature in (HUB_STATION, SEAT):
            # A printed band and a feeler limit: the term is the band itself.
            terms[feature] += LOOSER
            continue
        # A running bore: its diametral clearance on the pin grows by .002
        # and the part cocks over the same span.
        clearance, cock, lever = {
            SLEEVE_COCK: (
                AIR.SLEEVE.BORE_DIAMETRAL_CLEARANCE[1],
                AIR.SLEEVE_COCK,
                AIR.DISC_TILT_LEVER,
            ),
            BUSHING_COCK: (
                FIT.BORE_DIAMETRAL_CLEARANCE[1],
                AIR.FRONT_BUSHING_COCK,
                AIR.FRONT_BUSHING_COCK_REACH,
            ),
        }[feature]
        span = clearance / math.tan(cock)
        assert terms[feature] == pytest.approx(cock * lever)
        terms[feature] = math.atan((clearance + LOOSER) / span) * lever
    return AIR.AirStack("collar air, opened", FIT.M_FWD_NOMINAL, terms, AIR.COLLAR_AIR_MIN).statistical_mm


# (features opened .002, the air in mm, whether it clears the floor)
CASES = (
    ((), 0.1366, True),
    ((HUB_STATION,), 0.1225, True),
    ((SEAT,), 0.1159, True),
    ((HUB_STATION, SEAT), 0.1032, True),
    ((SLEEVE_COCK,), 0.0675, False),
    ((BUSHING_COCK,), 0.0953, False),
    ((HUB_STATION, SLEEVE_COCK), 0.0535, False),
    ((HUB_STATION, BUSHING_COCK), 0.0812, False),
    ((SEAT, SLEEVE_COCK), 0.0468, False),
    ((SEAT, BUSHING_COCK), 0.0745, False),
)


@pytest.mark.parametrize(("features", "air", "clears"), CASES)
def test_collar_air_with_each_tight_feature_opened(features, air, clears):
    assert AIR.COLLAR_AIR_MIN == pytest.approx(0.1016)
    assert _opened(*features) == pytest.approx(air, abs=5e-5)
    assert (_opened(*features) >= AIR.COLLAR_AIR_MIN) is clears


def test_spigot_length_is_at_the_title_block_and_no_wider_band_fits():
    """The spigot spends the air: at the title block the air is 0.1366; the
    hub face station cannot follow it there (0.0972, under the floor)."""
    title_block = printed_band_mm(3, unit=HUB_GEOMETRY.UNIT)
    assert HUB_GEOMETRY.SPIGOT_LENGTH_BAND == pytest.approx(title_block)
    assert AIR.COLLAR_AIR.terms[FIT.SP[0]] == pytest.approx(title_block)
    terms = {**AIR.COLLAR_AIR.terms, HUB_STATION: title_block}
    both = AIR.AirStack("both lengths at the title block", FIT.M_FWD_NOMINAL, terms, AIR.COLLAR_AIR_MIN)
    assert both.statistical_mm == pytest.approx(0.0972, abs=5e-5)
    assert both.statistical_mm < AIR.COLLAR_AIR_MIN


def _text(value: float) -> str:
    return f"{value:.4f}"


def _necessity(stem: str, entry_id: str) -> str:
    data = yaml.safe_load((CONFIG / "necessity" / f"{stem}.yaml").read_text(encoding="utf-8"))
    (entry,) = (e for e in data["necessity"] if e["id"] == entry_id)
    return entry["source"]


def _exception(path: Path, entry_id: str) -> str:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    (package,) = data.values() if "machinist_exceptions" not in data else (data,)
    (entry,) = (e for e in package["machinist_exceptions"] if e["id"] == entry_id)
    assert entry["kind"] == "accept"
    return entry["reason"]


def test_the_registers_quote_the_derived_airs():
    """Each REAM's register entry gives the air with its own bore opened."""
    for stem, feature in (
        ("pd-transgear-feed-pinion", SLEEVE_COCK),
        ("pd-transgear-front-bushing", BUSHING_COCK),
    ):
        source = _necessity(stem, "N-01")
        assert _text(_opened()) in source, stem
        assert _text(_opened(feature)) in source, stem
        assert _text(AIR.COLLAR_AIR_MIN) in source, stem


def test_the_accept_entries_quote_the_shared_budget():
    """The two features that stay tight by ruling say so with the numbers:
    alone each opens, both open with 0.0016 mm over the floor, and neither
    opens with a bore."""
    entries = (
        (CONFIG / "parts" / "pd-transgear-knob-bush.yaml", "RV-05", HUB_STATION),
        (CONFIG / "assemblies" / "pd-paper-drive.yaml", "PD-00-bush-seat-feeler", SEAT),
    )
    for path, entry_id, feature in entries:
        reason = _exception(path, entry_id)
        assert "delegated ruling 2026-11-25 (Main), no precedent" in reason
        assert "issues/2144" in reason
        for opened in (
            (),
            (feature,),
            (HUB_STATION, SEAT),
            (feature, SLEEVE_COCK),
            (feature, BUSHING_COCK),
        ):
            assert _text(_opened(*opened)) in reason, (entry_id, opened)
        assert _text(AIR.COLLAR_AIR_MIN) in reason
