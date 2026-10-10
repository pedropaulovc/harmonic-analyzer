"""Balloon anchors for the frame exploded view (sheet 2).

A frozen point is on an edge of the family's lowest-named shown instance
(or its pinned one), in that part's own millimetres, so view scale,
placement and explode distance do not move it. The build projects it onto
the sheet, hit-tests the sheet there and refuses the balloon unless the
edge it finds is that instance's (``_drawing_common._select_balloon_anchor``).

``BalloonAnchor()`` walks: it hit-tests the first instance's body extreme
points along fixed directions (``_drawing_common._walk_points``), ranked by
geometry, and takes the first the hit test gives back to that exact
instance, else the first so claimed of the points along the edges that
instance's hidden-line pass lists as drawn; with neither, the sheet fails.
It never moves on to a sibling instance. The balloon's leader ends at the
claimed point. The ``drawing.balloon_anchor`` event reports where it
landed, ready to freeze here.

Hit tests run zoomed onto the point, so a hit is an edge drawn there, not
one a millimetre-wide fit-to-sheet aperture reached (and reached further on a
smaller seat window). Points proven under that aperture no longer prove
anything: tube-frame's (12.7, 0, 0), frozen from run 20260928T074246010Z,
selected no edge zoomed (run 20260928T092244731Z). harmonic-base's point hit
zoomed in that run, so it stays frozen; the others walk. Zoomed frozen points
are not yet seat-portable either: tube-frame-cap's (0, 17.939, 13.335), hit
on swmaker000006 in runs 20260928T093251625Z and 20260928T094157505Z,
selected no edge at the same sheet point on swmaker000008 (run
20260928T114357610Z).

The lag screw is pinned to lag-screw-2 and walks there. Its frozen head
point hit lag-screw-2 on swmaker000004 (run 20260928T084730204Z) and the
rocker-arm-support flange under it on swmaker000008 (run
20260928T085715872Z), both unzoomed; its listed visible edges were 0 for
lag-screw-1 on swmaker000004 and 45 on other seats, so a listed edge cannot
choose its instance. lag-screw-1's twelve extreme points all hit other parts
on swmaker000005, 000007 and 000008, and the walk then took lag-screw-2 at
(-2.960, 3.966, -4.707) (runs 20260928T100532195Z, 20260928T124727673Z,
20260928T125521595Z, 20260928T141421973Z). Moving on to a sibling was a
hit result choosing the instance, so the pin makes that choice instead.

The nameplate screw is pinned to fillister-screw-2, the plate's front west
corner (``nameplate_spec.MOUNT_HOLE_XZ[1]``). The explode withdraws the four
screws 35 mm straight up off the lifted plate, and in the isometric the
first screw's corner is the plate's nearest: its screw hangs over the
engraving, where run 20260928T194845954Z-44f5de00de924735961d14f4aad40337
ballooned its head among the letters and the leader read as the nameplate's.
fillister-screw-3's corner is the plate's leftmost, so its screw hangs clear
beyond the plate, but once the plate moved onto the deck's west end (#1310)
that head printed at (154.03, 143.78) mm, 0.48 mm right of and 4.68 mm under
the base's frozen point (153.54, 148.46): the base leader, running down from
that point, crossed the screw's leader 1.6 mm short of its head (run
20261010T080952518Z-e181d98b5be149ab856b66e780131dbd, swmaker00000a). The
plate's rightmost corner is fillister-screw-2's; projected from screw-3's
head, its head prints some 12 mm right of the base point, and its screw too
hangs beyond the plate.
"""

from __future__ import annotations

from _drawing_common import BalloonAnchor

FRAME_BALLOON_ANCHORS: dict[str, BalloonAnchor] = {
    "fr-harmonic-base": BalloonAnchor((90.360, 50.800, -62.873)),
    "fr-tube-frame": BalloonAnchor(),
    "vn-tube-frame-cap": BalloonAnchor(),
    "fr-rocker-arm-support": BalloonAnchor(),
    "vn-lag-screw": BalloonAnchor(instance="vn-lag-screw-2"),
    "fr-top-frame": BalloonAnchor(),
    "fr-nameplate": BalloonAnchor(),
    "vn-fillister-screw": BalloonAnchor(instance="vn-fillister-screw-2"),
    "vn-frame-cross-screw": BalloonAnchor(),
    "vn-gooseneck-set-screw": BalloonAnchor(),
}
