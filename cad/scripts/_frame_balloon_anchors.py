"""Balloon anchors for the frame exploded view (sheet 2).

A frozen point is on an edge of the family's lowest-named shown instance,
in that part's own millimetres, so view scale, placement and explode
distance do not move it. The build projects it onto the sheet, hit-tests
the sheet there and refuses the balloon unless the edge it finds is that
instance's (``_drawing_common._select_balloon_anchor``).

``BalloonAnchor()`` walks a bounded part of the family's body, ranks its
edge points by geometry, and takes the first point the hit test gives back
to that exact instance, else an edge the view's hidden-line pass lists as
drawn; with neither, the sheet fails. The ``drawing.balloon_anchor`` event
reports where it landed, ready to freeze here. The walk is the default: points frozen from a farm
probe at the old 1:7 frame sheet (run 20260928T061043870Z) missed on the
1:8 sheet (rocker-arm-support, arbor-pedestal select no edge at their
projection), so only points proven on the current sheets are frozen.
"""

from __future__ import annotations

from _drawing_common import BalloonAnchor

FRAME_BALLOON_ANCHORS: dict[str, BalloonAnchor] = {
    "harmonic-base": BalloonAnchor(),
    "tube-frame": BalloonAnchor((12.700, 0.0, 0.0)),
    "tube-frame-cap": BalloonAnchor((0.0, 18.891, 12.383)),
    "rocker-arm-support": BalloonAnchor(),
    "lag-screw": BalloonAnchor(),
    "top-frame": BalloonAnchor(),
    "nameplate": BalloonAnchor(),
    "fillister-screw": BalloonAnchor(),
    "frame-cross-screw": BalloonAnchor(),
    "gooseneck-set-screw": BalloonAnchor(),
}
