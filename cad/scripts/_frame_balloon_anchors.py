"""Balloon anchors for the frame exploded view (sheet 2).

A frozen point is on an edge of the family's lowest-named shown instance
(or its pinned one), in that part's own millimetres, so view scale,
placement and explode distance do not move it. The build projects it onto
the sheet, hit-tests the sheet there and refuses the balloon unless the
edge it finds is that instance's (``_drawing_common._select_balloon_anchor``).

``BalloonAnchor()`` walks a bounded part of the family's body, ranks its
edge points by geometry, and takes the first point the hit test gives back
to that exact instance, else an edge the view's hidden-line pass lists as
drawn; with neither, the sheet fails. ``BalloonAnchor(visible_edge=True)``
goes straight to that listed edge without hit-testing. The
``drawing.balloon_anchor`` event reports where it landed, ready to freeze
here.

Hit tests run zoomed onto the point, so a hit is an edge drawn there, not
one a millimetre-wide fit-to-sheet aperture reached (and reached further on a
smaller seat window). Points proven under that aperture no longer prove
anything: tube-frame's (12.7, 0, 0), frozen from run 20260928T074246010Z,
selected no edge zoomed (run 20260928T092244731Z). harmonic-base's point hit
zoomed in that run, so it stays frozen; the others walk until a zoomed run
proves their points on this sheet.

The lag screw takes its listed visible edge: its frozen head point hit
lag-screw-2 on swmaker000004 (run 20260928T084730204Z) and the
rocker-arm-support flange under it on swmaker000008 (run
20260928T085715872Z), and no walked lag-screw point hit on swmaker000008.
"""

from __future__ import annotations

from _drawing_common import BalloonAnchor

FRAME_BALLOON_ANCHORS: dict[str, BalloonAnchor] = {
    "harmonic-base": BalloonAnchor((90.360, 50.800, -62.873)),
    "tube-frame": BalloonAnchor(),
    "tube-frame-cap": BalloonAnchor(),
    "rocker-arm-support": BalloonAnchor(),
    # Its head sits on the rocker-arm-support flange: hit tests disagree by seat.
    "lag-screw": BalloonAnchor(visible_edge=True),
    "top-frame": BalloonAnchor(),
    "nameplate": BalloonAnchor(),
    "fillister-screw": BalloonAnchor(),
    "frame-cross-screw": BalloonAnchor(),
    "gooseneck-set-screw": BalloonAnchor(),
}
