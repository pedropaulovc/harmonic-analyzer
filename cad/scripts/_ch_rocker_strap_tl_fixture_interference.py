"""Allowed-interference contract for the rocker-strap sub-plate fixture (MHA-CH-13-TL-00).

Its reopened soundness gate reads this table. The only intended overlaps are
the threads: each Pitbull clamp's #4-40 screw, modelled at its major
diameter, through its Ø.089 (#43) tapped hole under the pocket floor, and the
#10-32 hub screw through its Ø.159 (#21) tapped hole under the counterbore.
Everything else is contact (clamp seat on the pocket floor, heel on the
back wall, plug on the counterbore floor) or clear (the plug's body in the
counterbore, the screw through the washer and the plug's bore).

Literals, so this table does not re-key on the plate's layout;
test_ch_rocker_strap_tl_fixture_assembly pins them to the specs.
"""

from __future__ import annotations

from collections.abc import Mapping

from _interference_common import numbered_pairs, smooth_annulus_limit_mm3

# (major, tap drill, engaged length) mm: the plate under each pocket floor
# (.416 Z0 to underside less the .140 pocket) and under the counterbore floor
# (less the .185 counterbore); each screw runs out through the underside.
CLAMP_SCREW_THREAD = (2.8448, 2.2606, 7.0104)
HUB_SCREW_THREAD = (4.826, 4.0386, 5.8674)
ALLOWED_PAIRS: Mapping[frozenset[str], float] = {
    **numbered_pairs(
        "ch-rocker-strap-tl-vn-edge-clamp",
        range(1, 5),
        "ch-rocker-strap-tl-sub-plate",
        smooth_annulus_limit_mm3(*CLAMP_SCREW_THREAD),
    ),
    frozenset(
        ("ch-rocker-strap-tl-vn-hub-screw-1", "ch-rocker-strap-tl-sub-plate-1")
    ): smooth_annulus_limit_mm3(*HUB_SCREW_THREAD),
}
