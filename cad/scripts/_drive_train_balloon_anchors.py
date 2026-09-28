"""Frozen balloon anchors for the drive-train exploded cluster sheets.

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

Keyed by cluster, then family; a cluster sheet shows only its own cluster.
"""

from __future__ import annotations

from _drawing_common import BalloonAnchor

DRIVE_TRAIN_BALLOON_ANCHORS: dict[str, dict[str, BalloonAnchor]] = {
    "cylinder-bank": {
        "cylinder-gear-shaft": BalloonAnchor(),
        "arbor-pedestal": BalloonAnchor((12.000, 5.000, -25.500)),
        "cylinder-end-disc": BalloonAnchor((0.0, 12.500, 0.0)),
        "arbor-set-screw": BalloonAnchor((0.0, 5.874, -1.422)),
        "cylinder-gear": BalloonAnchor((-15.773, 26.804, 3.000)),
    },
    "cone-crank": {
        "cone-swing-platform": BalloonAnchor((0.972, -4.825, 7.000)),
        "cone-pivot-post": BalloonAnchor(),
        "post-mount-screw": BalloonAnchor((-0.710, 4.816, 5.210)),
        "cone-tip-block": BalloonAnchor((-8.500, 0.0, 4.470)),
        "cone-tip-shim": BalloonAnchor(),
        "cone-tip-bushing": BalloonAnchor(),
        "cone-tip-adjuster": BalloonAnchor((-0.402, 0.219, -2.379)),
        "cone-tip-pinch-screw": BalloonAnchor((-0.314, 0.782, -4.055)),
        "cone-lock-knob": BalloonAnchor((2.896, 10.001, 12.202)),
        "cone-pivot-screw": BalloonAnchor((-1.275, -15.875, 1.513)),
        "swing-stop-screw": BalloonAnchor((0.463, 7.766, 7.604)),
        "cone-gear-shaft": BalloonAnchor(),
        "crank-drive-gear": BalloonAnchor(),
        "cone-gear": BalloonAnchor(),
        "crankshaft": BalloonAnchor((0.0, 0.0, -4.763)),
        "crank-pinion": BalloonAnchor((0.0, -6.607, 24.900)),
        "crank-hub": BalloonAnchor((0.0, 8.000, -12.700)),
        "crank-hub-pin": BalloonAnchor(),
        "crank-arm": BalloonAnchor((-8.980, -8.980, 8.000)),
        "crank-pin": BalloonAnchor(),
        "crank-pin-ring": BalloonAnchor((-0.600, 0.0, 0.0)),
        "crank-pinion-pin": BalloonAnchor(),
        "crank-pin-eye": BalloonAnchor(),
        "fillister-screw": BalloonAnchor((1.458, 1.810, -1.963)),
        "crank-handle": BalloonAnchor((58.000, 0.0, 5.000)),
        "crank-handle-pivot-screw": BalloonAnchor((10.953, 0.500, 0.0)),
    },
    "pinion-rig": {
        "alignment-pinion": BalloonAnchor(),
        "pinion-bracket": BalloonAnchor((-7.500, 0.0, 0.0)),
        "pinion-strap-pin": BalloonAnchor(),
        "pinion-pivot-block": BalloonAnchor((-26.000, -12.000, 11.000)),
        "pinion-pivot-shaft": BalloonAnchor((0.0, -3.175, 187.000)),
        "pinion-lift-rod": BalloonAnchor((-3.175, 0.0, 198.300)),
        "pinion-spring": BalloonAnchor(),
        "pinion-cam-pin": BalloonAnchor((0.0, -2.000, 20.000)),
        "pinion-cam": BalloonAnchor((0.0, -9.300, 0.0)),
        "pinion-lever": BalloonAnchor((0.0, 86.000, -3.000)),
        "pinion-lever-pin": BalloonAnchor((6.500, 0.0, -0.794)),
        "pinion-handle": BalloonAnchor((0.0, -32.000, -3.000)),
        "pinion-arbor": BalloonAnchor((7.500, 0.0, -12.250)),
        "pinion-arbor-collar": BalloonAnchor((0.0, 7.500, 0.0)),
        "slotted-screw": BalloonAnchor((-0.463, -0.455, -7.022)),
        "foot-screw": BalloonAnchor(),
    },
}
