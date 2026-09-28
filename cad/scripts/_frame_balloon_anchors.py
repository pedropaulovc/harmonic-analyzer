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
selected no edge zoomed (run 20260928T092244731Z). harmonic-base's point hit
zoomed in that run, so it stays frozen; the others walk. Zoomed frozen points
are not yet seat-portable either: tube-frame-cap's (0, 17.939, 13.335), hit
on swmaker000006 in runs 20260928T093251625Z and 20260928T094157505Z,
selected no edge at the same sheet point on swmaker000008 (run
20260928T114357610Z).

The lag screw walks too. Its frozen head point hit lag-screw-2 on
swmaker000004 (run 20260928T084730204Z) and the rocker-arm-support flange
under it on swmaker000008 (run 20260928T085715872Z), both unzoomed; its
listed visible edges were 0 for lag-screw-1 on swmaker000004 and 45 on
other seats, so a listed edge cannot choose its instance. Walking, it took
lag-screw-2 on swmaker000008 after lag-screw-1's twelve extreme points all
hit other parts (run 20260928T100532195Z).
"""

from __future__ import annotations

from _drawing_common import BalloonAnchor

FRAME_BALLOON_ANCHORS: dict[str, BalloonAnchor] = {
    "harmonic-base": BalloonAnchor((90.360, 50.800, -62.873)),
    "tube-frame": BalloonAnchor(),
    "tube-frame-cap": BalloonAnchor(),
    "rocker-arm-support": BalloonAnchor(),
    "lag-screw": BalloonAnchor(),
    "top-frame": BalloonAnchor(),
    "nameplate": BalloonAnchor(),
    "fillister-screw": BalloonAnchor(),
    "frame-cross-screw": BalloonAnchor(),
    "gooseneck-set-screw": BalloonAnchor(),
}
