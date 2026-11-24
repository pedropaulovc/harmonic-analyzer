r"""The bonded slip fit that joins the built-up rocker arm's hub to its strap.

PURE DATA, no SolidWorks/COM imports. MHA-CH-06 may be built up (its
``ch_rocker_arm_notes.BUILT_UP_PERMISSION_NOTE``): the turned hub MHA-CH-12
slides into the Ø.400 reamed hole of the flat strap MHA-CH-13 and is bonded
there with LOCTITE 638. Both detail builds and their drawing tests import this
one module, so the hole's analysis band and the clearance the land is turned
to are stated once.

Owner ruling 2026-11-24, fit audit question 2 (option A, approved as
recommended): "ream .400 with no band; hub turned until it slides in
(clearance .0005-.0030); bond". It reverses the press of route v3
(2026-10-16) and the matched press of 2026-11-21 ("matched fit only",
.0004-.0013 interference on the measured hole); precedent for the bond: owner
ruling 2026-11-20, #2469 ("a LOCTITE 638 bonded slip fit, not a press").

The strap hole prints REAM with no band. ``STRAP_HOLE_BAND`` is the analysis
band the .4000 reamer is taken to cut (``tools.reamer-4000``'s stated
0/+.0002, held to the old .0005 band): the TL-02 plug's pilot and the strap's
hole-located outline still read it. The land is turned to slide into the
strap hole: each land sits .0005-.0030 under its own hole, so over every hole
the reamed band admits it runs .3970-.4000 (``LAND_RANGE``, deviations from
the .400 nominal). The largest gap, .0030 (0.0762 mm), is inside LOCTITE
638's 0.25 mm gap fill (TDS August 2016, the limit
``sm_gooseneck_spring_joint.LOCTITE_638_GAP_MAX`` and
``dt_pinion_arbor_geometry.RETAINING_COMPOUND_MAX_GAP_MM`` state).
"""

from __future__ import annotations

STRAP_HOLE_BAND = (0.0127, 0.0)  # (upper, lower): the reamer's +.0005/.0000, unprinted
BOND_CLEARANCE = (0.0127, 0.0762)  # diametral (least, greatest): .0005-.0030
LOCTITE_638_GAP_MAX = 0.25  # mm, diametral: the TDS's largest gap


def land_range(
    clearance: tuple[float, float], hole_band: tuple[float, float]
) -> tuple[float, float]:
    """The land's (least, greatest) deviation over the hole's nominal across
    every hole in ``hole_band``, each land turned to slide into its own hole.

    The least is the smallest hole less the greatest clearance, the greatest
    the largest hole less the least. A bonded slip fit must slide at both
    ends and stay inside the compound's gap fill: a least clearance of .0000
    is a line-to-line pair that may need forcing.
    """
    least, greatest = clearance
    if not 0.0 < least < greatest:
        raise AssertionError(
            f"the hub land can go in the strap hole line-to-line or tight: {clearance}"
        )
    if greatest > LOCTITE_638_GAP_MAX:
        raise AssertionError(
            f"the hub-to-strap gap {greatest} mm passes LOCTITE 638's gap fill"
        )
    return round(hole_band[1] - greatest, 6), round(hole_band[0] - least, 6)


# -.0030/.0000 over every hole the reamed band admits (the hub's supply wall
# takes the least).
LAND_RANGE = land_range(BOND_CLEARANCE, STRAP_HOLE_BAND)

# The one land window that takes the clearance in every hole the reamer cuts,
# so the lathe turns the lot to a micrometer reading and a strap's hole then
# tries each land: from the largest hole less the greatest clearance to the
# smallest hole less the least, -.0025/-.0005 (.3975-.3995).
LAND_WINDOW = (
    round(STRAP_HOLE_BAND[0] - BOND_CLEARANCE[1], 6),
    round(STRAP_HOLE_BAND[1] - BOND_CLEARANCE[0], 6),
)
if not LAND_RANGE[0] <= LAND_WINDOW[0] < LAND_WINDOW[1] <= LAND_RANGE[1]:
    raise AssertionError(f"no land window takes every reamed hole: {LAND_WINDOW}")
