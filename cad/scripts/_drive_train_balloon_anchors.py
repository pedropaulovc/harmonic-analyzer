"""Balloon anchors for the drive-train exploded cluster sheets.

A frozen point is on an edge of the family's lowest-named shown instance,
in that part's own millimetres, so view scale, placement and explode
distance do not move it. The build projects it onto the sheet, hit-tests
the sheet there and refuses the balloon unless the edge it finds is that
instance's (``_drawing_common._select_balloon_anchor``).

``BalloonAnchor()`` walks: it hit-tests the body's extreme points along
fixed directions (``_drawing_common._walk_points``), ranked by geometry,
and takes the first the hit test gives back to that exact instance, else
the first so claimed of the points along the edges the view's hidden-line
pass lists as drawn for that instance; with neither, the sheet fails. The
balloon's leader ends at the claimed point. The ``drawing.balloon_anchor``
event reports where it landed, ready to freeze here. Every drive-train
family walks.

Keyed by cluster, then family; a cluster sheet shows only its own cluster.

The pedestal hold-down screw is pinned to the south screw,
pedestal-hold-down-screw-1: the north one hides behind its strap in the
exploded view (r6b item 26). The pin replaces a head-rim pick that took the
screw's largest listed circle by entity, whose leader SolidWorks ended on
the pedestal's top face (run
20260928T194845954Z-44f5de00de924735961d14f4aad40337, item 32).
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
        "pedestal-hold-down-screw": BalloonAnchor(instance="pedestal-hold-down-screw-1"),
    },
    "cone-crank": {
        "cone-swing-platform": BalloonAnchor(),
        "cone-pivot-post": BalloonAnchor(),
        "post-mount-screw": BalloonAnchor(),
        "cone-tip-block": BalloonAnchor(),
        "cone-tip-block-screw": BalloonAnchor(),
        "cone-tip-collar": BalloonAnchor(),
        "cone-tip-adjuster": BalloonAnchor(),
        "cone-tip-pinch-screw": BalloonAnchor(),
        "cone-lock-knob": BalloonAnchor(),
        "cone-pivot-screw": BalloonAnchor(),
        "swing-stop-screw": BalloonAnchor(),
        "cone-gear-shaft": BalloonAnchor(),
        "crank-drive-gear": BalloonAnchor(),
        "cone-gear": BalloonAnchor(),
        "crankshaft": BalloonAnchor(),
        "crank-seat-washer": BalloonAnchor(),
        "crank-seat-drive-pin": BalloonAnchor(),
        "crank-pinion": BalloonAnchor(),
        "crank-hub": BalloonAnchor(),
        "crank-hub-pin": BalloonAnchor(),
        "crank-arm": BalloonAnchor(),
        "crank-pin": BalloonAnchor(),
        "crank-pin-ring": BalloonAnchor(),
        "crank-pinion-pin": BalloonAnchor(),
        "crank-pin-eye": BalloonAnchor(),
        "keeper-chain": BalloonAnchor(),
        "keeper-chain-link": BalloonAnchor(),
        "fillister-screw": BalloonAnchor(),
        "crank-handle": BalloonAnchor(),
        "crank-handle-ferrule": BalloonAnchor(),
        "crank-handle-butt-cup": BalloonAnchor(),
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
