"""Explicit, volume-bounded interference-fit contract for the magnifier.

Most nominal CAD solids must never overlap. A small set of manufactured
interference fits intentionally do; keeping those exceptions here lets both
the assembly build and the reopened soundness gate apply the same exact pair
and maximum-volume contract. Only build_mg_magnifier_assembly, the top
assembly's table (which reuses the shared thread limits below) and
verify_soundness:mg_magnifier fold this module, so it imports only what its
own pairs need.
"""

from __future__ import annotations

from collections.abc import Mapping

from _interference_common import numbered_pairs, smooth_annulus_limit_mm3

# Independent runtime oracles: importing the magnifier's fit/pose modules here
# would re-key this table, the top assembly's and their soundness gates for an
# unrelated fixture station or groove edit.
# test_mg_fixture_installation pins these triples to their geometry owners.
# The nominal smooth major/tap-drill annulus through the entire neck is the
# cosmetic-thread overlap. The incomplete root runout is wholly outside it.
_MG_LEVER_THREAD_TRIPLE_MM = (6.35, 5.105, 12.5)
_MG_FIXTURE_THREAD_TRIPLE_MM = (2.8448, 2.261, 9.8044)
# #1559 clamp (MHA-MG-02): the 91882A221 #4-40 shank in the thumb tap's
# Ø2.261 drill from the top face to the lever-bore top (THUMB_TAP_LENGTH 6.2501).
_MG_CLAMP_THUMB_TRIPLE_MM = (2.8448, 2.261, 6.2501)
# The vertical rod's #4-40 end (modelled at the 2.845 major) in the clamp's
# bottom-face Ø2.261 tap drill. Envelope 5.976 = ROD_THREAD_LEN - RELIEF_WIDTH:
# the full-major section from the tip to the relief, which also covers the tip
# chamfer (its cone lies inside that cylinder); the Ø1.8288 MAX relief is
# smaller than the drill and overlaps nothing.
_MG_ROD_THREAD_TRIPLE_MM = (2.845, 2.261, 5.976)

_MG_LEVER_THREAD_LIMIT = smooth_annulus_limit_mm3(*_MG_LEVER_THREAD_TRIPLE_MM)
# Only the major/thread-drill annulus from the spigot face to the rod-bore
# breakout (9.8044 mm), not the tangent screw tip or screw/rod overlap, is allowed.
_MG_FIXTURE_THREAD_LIMIT = smooth_annulus_limit_mm3(*_MG_FIXTURE_THREAD_TRIPLE_MM)
_MG_CLAMP_THUMB_LIMIT = smooth_annulus_limit_mm3(*_MG_CLAMP_THUMB_TRIPLE_MM)
_MG_ROD_THREAD_LIMIT = smooth_annulus_limit_mm3(*_MG_ROD_THREAD_TRIPLE_MM)

ALLOWED_PAIRS: Mapping[frozenset[str], float] = {
    # 31.75 screw - 9.4996 wheel bar - 17.399 front arc - 0.508 (.020) grip
    # gap (the back arc's mating face stops short of the column axis,
    # sh_column_clamp_back_geom.GRIP_OFFSET) = 4.3434 in the back arc's tap.
    **numbered_pairs(
        "sh-vn-clamp-screw",
        range(1, 3),
        "sh-column-clamp-back",
        smooth_annulus_limit_mm3(4.1656, 3.454, 4.3434),
    ),
    frozenset(("sh-vn-thumb-screw-1", "mg-magnifying-clamp-1")): _MG_CLAMP_THUMB_LIMIT,
    frozenset(
        ("mg-magnifying-vertical-rod-1", "mg-magnifying-clamp-1")
    ): _MG_ROD_THREAD_LIMIT,
    # MHA-MG-07 drill-rod pin (Ø4.7625, mg_wheel_axle_spec.PIN_DIA) pressed in
    # the wheel bar's Ø4.7371 reamed bore (mg_wheel_bar_geom.AXLE_BORE_DIA)
    # over at most 9.0 of the bar's 9.5 depth (its back end 0.60 sunk at
    # nominal, mg_wheel_axle_spec.BACK_Y): the press.
    frozenset(("mg-wheel-axle-1", "mg-wheel-bar-1")): smooth_annulus_limit_mm3(
        4.7625, 4.7371, 9.0
    ),
    frozenset(("sh-vn-thumb-screw-2", "mg-output-fixture-1")): _MG_FIXTURE_THREAD_LIMIT,
    frozenset(
        ("mg-magnifying-lever-1", "mg-magnifying-bracket-1")
    ): _MG_LEVER_THREAD_LIMIT,
}
