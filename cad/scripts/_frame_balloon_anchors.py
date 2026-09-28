"""Frozen balloon anchors for the frame exploded view (sheet 2).

The point is on an edge of the family's lowest-named shown instance, in
that part's own millimetres, so view scale, placement and explode distance
do not move it. The build projects it onto the sheet, hit-tests the sheet
there and refuses the balloon unless the edge it finds is that instance's
(``_drawing_common._select_balloon_anchor``). Each point was found by a farm
probe that tried the family's outermost visible edges from outside in and
kept the first whose hit test named the family itself (run
20260928T061043870Z-e88e1bbb, commit c364ce118).

``BalloonAnchor()`` marks a family no hit test could claim: every point the
probe tried on it found a neighbour in front -- a pin inside its bore, a
gear inside the stack. Those walk the part's own body instead, and report
the point they land on in the ``drawing.balloon_anchor`` event.
"""

from __future__ import annotations

from _drawing_common import BalloonAnchor

FRAME_BALLOON_ANCHORS: dict[str, BalloonAnchor] = {
    "harmonic-base": BalloonAnchor(),
    "tube-frame": BalloonAnchor((12.700, 0.0, 0.0)),
    "tube-frame-cap": BalloonAnchor((0.0, 18.891, 12.383)),
    "rocker-arm-support": BalloonAnchor((-120.650, -82.550, 3.175)),
    "lag-screw": BalloonAnchor(),
    "top-frame": BalloonAnchor((-223.100, 22.750, -112.000)),
    "nameplate": BalloonAnchor((79.010, -6.540, -0.400)),
    "fillister-screw": BalloonAnchor((0.946, 0.0, 6.350)),
    "frame-cross-screw": BalloonAnchor((-0.537, -2.506, -8.854)),
    "gooseneck-set-screw": BalloonAnchor((-2.245, 4.763, 2.245)),
}
