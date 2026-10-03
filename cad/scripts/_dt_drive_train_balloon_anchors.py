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
        "dt-cylinder-gear-shaft": BalloonAnchor(),
        "dt-arbor-pedestal": BalloonAnchor(),
        "dt-cylinder-end-disc": BalloonAnchor(),
        "vn-arbor-set-screw": BalloonAnchor(),
        "dt-cylinder-gear": BalloonAnchor(),
        "vn-pedestal-hold-down-screw": BalloonAnchor(instance="vn-pedestal-hold-down-screw-1"),
    },
    "cone-crank": {
        "dt-cone-swing-platform": BalloonAnchor(),
        "dt-cone-pivot-post": BalloonAnchor(),
        "vn-post-mount-screw": BalloonAnchor(),
        "dt-cone-tip-block": BalloonAnchor(),
        "vn-cone-tip-block-screw": BalloonAnchor(),
        "vn-cone-tip-collar": BalloonAnchor(),
        "vn-cone-tip-adjuster": BalloonAnchor(),
        "vn-cone-tip-pinch-screw": BalloonAnchor(),
        "vn-cone-lock-knob": BalloonAnchor(),
        "vn-cone-pivot-screw": BalloonAnchor(),
        "vn-swing-stop-screw": BalloonAnchor(),
        "dt-cone-gear-shaft": BalloonAnchor(),
        "dt-crank-drive-gear": BalloonAnchor(),
        "dt-cone-gear": BalloonAnchor(),
        "dt-crankshaft": BalloonAnchor(),
        "dt-crank-seat-washer": BalloonAnchor(),
        "vn-crank-seat-drive-pin": BalloonAnchor(),
        "dt-crank-pinion": BalloonAnchor(),
        "dt-crank-hub": BalloonAnchor(),
        "vn-crank-hub-pin": BalloonAnchor(),
        "dt-crank-arm": BalloonAnchor(),
        "dt-crank-pin": BalloonAnchor(),
        "dt-crank-pin-ring": BalloonAnchor(),
        "dt-crank-pinion-pin": BalloonAnchor(),
        "dt-crank-pin-eye": BalloonAnchor(),
        "vn-keeper-chain": BalloonAnchor(),
        "vn-keeper-chain-link": BalloonAnchor(),
        "vn-fillister-screw": BalloonAnchor(),
        "dt-crank-handle": BalloonAnchor(),
        "dt-crank-handle-ferrule": BalloonAnchor(),
        "dt-crank-handle-butt-cup": BalloonAnchor(),
        "dt-crank-handle-pivot-screw": BalloonAnchor(),
    },
    "pinion-rig": {
        "dt-alignment-pinion": BalloonAnchor(),
        "dt-pinion-bracket": BalloonAnchor(),
        "vn-pinion-strap-pin": BalloonAnchor(),
        "dt-pinion-pivot-block": BalloonAnchor(),
        "dt-pinion-pivot-shaft": BalloonAnchor(),
        "dt-pinion-lift-rod": BalloonAnchor(),
        "dt-pinion-spring": BalloonAnchor(),
        "dt-pinion-cam-pin": BalloonAnchor(),
        "dt-pinion-cam": BalloonAnchor(),
        "dt-pinion-lever": BalloonAnchor(),
        "dt-pinion-lever-pin": BalloonAnchor(),
        "dt-pinion-handle": BalloonAnchor(),
        "dt-pinion-arbor": BalloonAnchor(),
        "dt-pinion-arbor-collar": BalloonAnchor(),
        "vn-slotted-screw": BalloonAnchor(),
        "vn-foot-screw": BalloonAnchor(),
    },
}
