"""Balloon anchors for the frame exploded view (sheet 2).

A frozen point is on an edge of the family's lowest-named shown instance
(or its pinned one), in that part's own millimetres, so view scale,
placement and explode distance do not move it. The build projects it onto
the sheet, hit-tests the sheet there and refuses the balloon unless the
edge it finds is that instance's (``_drawing_common._select_balloon_anchor``).

``BalloonAnchor()`` walks: it hit-tests the body's extreme points along
fixed directions (``_drawing_common._walk_points``), ranked by geometry,
and takes the first the hit test gives back to that exact instance, else an
edge of the first instance that the view's hidden-line pass lists as drawn;
with neither, the sheet fails. The ``drawing.balloon_anchor`` event reports
where it landed, ready to freeze here.

Hit tests run zoomed onto the point, so a hit is an edge drawn there, not
one a millimetre-wide fit-to-sheet aperture reached (and reached further on a
smaller seat window). Points proven under that aperture no longer prove
anything: tube-frame's (12.7, 0, 0), frozen from run 20260928T074246010Z,
selected no edge zoomed (run 20260928T092244731Z).

Every family is frozen, because the ring the balloons spread on is drawn
from all ten anchors at once. harmonic-base's point hit zoomed in run
20260928T092244731Z. The next eight are where the zoomed walk landed in
runs 20260928T093251625Z and 20260928T094157505Z, identically; that sheet
audited clean. Walking extreme points instead (run 20260928T100532195Z)
moved top-frame's anchor to (148.8, 248.7) mm on the sheet, and balloon 5's
leader then crossed its own text.

The lag screw is pinned to lag-screw-2, where that walk hit after all 12 of
lag-screw-1's extreme points hit something else. Its head sits on the
rocker-arm-support flange. An unzoomed head point hit lag-screw-2 on
swmaker000004 (run 20260928T084730204Z) and the flange on swmaker000008
(run 20260928T085715872Z). lag-screw-1 listed 0 visible edges on
swmaker000004 and 45 on other seats, so a listed edge cannot choose it.
"""

from __future__ import annotations

from _drawing_common import BalloonAnchor

FRAME_BALLOON_ANCHORS: dict[str, BalloonAnchor] = {
    "harmonic-base": BalloonAnchor((90.360, 50.800, -62.873)),
    "tube-frame": BalloonAnchor((0.000, 1018.765, 12.200)),
    "tube-frame-cap": BalloonAnchor((0.000, 17.939, 13.335)),
    "rocker-arm-support": BalloonAnchor((63.500, 12.700, 1.905)),
    "lag-screw": BalloonAnchor((-2.960, 3.966, -4.707), instance="lag-screw-2"),
    "top-frame": BalloonAnchor((-214.100, -18.250, -10.412)),
    "nameplate": BalloonAnchor((0.000, 3.000, 0.000)),
    "fillister-screw": BalloonAnchor((-0.495, -3.676, -0.608)),
    "frame-cross-screw": BalloonAnchor((1.354, -1.290, 1.329)),
    "gooseneck-set-screw": BalloonAnchor((3.175, 0.352, 3.175)),
}
