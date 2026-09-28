"""Balloon anchors for the drive-train exploded cluster sheets.

A frozen point is on an edge of the family's lowest-named shown instance,
in that part's own millimetres, so view scale, placement and explode
distance do not move it. The build projects it onto the sheet, hit-tests
the sheet there and refuses the balloon unless the edge it finds is that
instance's (``_drawing_common._select_balloon_anchor``).

``BalloonAnchor()`` walks the part's own body in its face/edge order and
takes the first point the hit test gives back to the family, else its first
walked edge; the ``drawing.balloon_anchor`` event reports where it landed,
ready to freeze here. The walk is the default: points frozen from a farm
probe at the old 1:7 frame sheet (run 20260928T061043870Z) missed on the
1:8 sheet (rocker-arm-support, arbor-pedestal select no edge at their
projection), so only points proven on the current sheets are frozen.

Keyed by cluster, then family; a cluster sheet shows only its own cluster.
"""

from __future__ import annotations

from _drawing_common import BalloonAnchor

DRIVE_TRAIN_BALLOON_ANCHORS: dict[str, dict[str, BalloonAnchor]] = {
    "cylinder-bank": {
        "cylinder-gear-shaft": BalloonAnchor(),
        "arbor-pedestal": BalloonAnchor(),
        "cylinder-end-disc": BalloonAnchor(),
        "arbor-set-screw": BalloonAnchor(),
        "cylinder-gear": BalloonAnchor(),
    },
    "cone-crank": {
        "cone-swing-platform": BalloonAnchor(),
        "cone-pivot-post": BalloonAnchor(),
        "post-mount-screw": BalloonAnchor(),
        "cone-tip-block": BalloonAnchor(),
        "cone-tip-shim": BalloonAnchor(),
        "cone-tip-bushing": BalloonAnchor(),
        "cone-tip-adjuster": BalloonAnchor(),
        "cone-tip-pinch-screw": BalloonAnchor(),
        "cone-lock-knob": BalloonAnchor(),
        "cone-pivot-screw": BalloonAnchor(),
        "swing-stop-screw": BalloonAnchor(),
        "cone-gear-shaft": BalloonAnchor(),
        "crank-drive-gear": BalloonAnchor(),
        "cone-gear": BalloonAnchor(),
        "crankshaft": BalloonAnchor(),
        "crank-pinion": BalloonAnchor(),
        "crank-hub": BalloonAnchor(),
        "crank-hub-pin": BalloonAnchor(),
        "crank-arm": BalloonAnchor(),
        "crank-pin": BalloonAnchor(),
        "crank-pin-ring": BalloonAnchor(),
        "crank-pinion-pin": BalloonAnchor(),
        "crank-pin-eye": BalloonAnchor(),
        "fillister-screw": BalloonAnchor(),
        "crank-handle": BalloonAnchor(),
        "crank-handle-pivot-screw": BalloonAnchor(),
    },
    "pinion-rig": {
        "alignment-pinion": BalloonAnchor(),
        "pinion-bracket": BalloonAnchor(),
        "pinion-strap-pin": BalloonAnchor(),
        "pinion-pivot-block": BalloonAnchor(),
        "pinion-pivot-shaft": BalloonAnchor(),
        "pinion-lift-rod": BalloonAnchor(),
        "pinion-spring": BalloonAnchor(),
        "pinion-cam-pin": BalloonAnchor(),
        "pinion-cam": BalloonAnchor(),
        "pinion-lever": BalloonAnchor(),
        "pinion-lever-pin": BalloonAnchor(),
        "pinion-handle": BalloonAnchor(),
        "pinion-arbor": BalloonAnchor(),
        "pinion-arbor-collar": BalloonAnchor(),
        "slotted-screw": BalloonAnchor(),
        "foot-screw": BalloonAnchor(),
    },
}
