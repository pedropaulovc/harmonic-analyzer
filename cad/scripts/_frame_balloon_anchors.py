"""Balloon anchors for the frame exploded view (sheet 2).

A frozen point is on an edge of the family's lowest-named shown instance
(or its pinned one), in that part's own millimetres, so view scale,
placement and explode distance do not move it. The build projects it onto
the sheet, hit-tests the sheet there and refuses the balloon unless the
edge it finds is that instance's (``_drawing_common._select_balloon_anchor``).

``BalloonAnchor()`` walks a bounded part of the family's body, ranks its
edge points by geometry, and takes the first point the hit test gives back
to that exact instance, else an edge the view's hidden-line pass lists as
drawn; with neither, the sheet fails. The ``drawing.balloon_anchor`` event
reports where it landed, ready to freeze here.

Every frame family is frozen, at the point farm run 20260928T074246010Z
hit on the current 1:8 sheet: that sheet audited clean, and its frozen
anchors project to the same sheet points today. Walking instead moved the
cross-screw balloon's leader through its own number (run
20260928T083410084Z) and walked the lag screws through 24 hidden points
first. Points frozen from the old 1:7 sheet (run 20260928T061043870Z) had
missed on the 1:8 sheet, so a point is frozen only once proven on the sheet
it serves.
"""

from __future__ import annotations

from _drawing_common import BalloonAnchor

FRAME_BALLOON_ANCHORS: dict[str, BalloonAnchor] = {
    "harmonic-base": BalloonAnchor((90.360, 50.800, -62.873)),
    "tube-frame": BalloonAnchor((12.700, 0.0, 0.0)),
    "tube-frame-cap": BalloonAnchor((0.0, 18.891, 12.383)),
    "rocker-arm-support": BalloonAnchor((76.200, -83.655, 31.063)),
    # No walked point of lag-screw-1 hit on this sheet; lag-screw-2's did.
    "lag-screw": BalloonAnchor((0.0, 0.0, 6.416), instance="lag-screw-2"),
    "top-frame": BalloonAnchor((-197.000, -2.019, 124.750)),
    "nameplate": BalloonAnchor((5.121, 5.121, 0.0)),
    "fillister-screw": BalloonAnchor((-2.204, 0.495, -2.079)),
    "frame-cross-screw": BalloonAnchor((1.354, -1.290, 1.329)),
    "gooseneck-set-screw": BalloonAnchor((2.245, 4.763, -2.245)),
}
