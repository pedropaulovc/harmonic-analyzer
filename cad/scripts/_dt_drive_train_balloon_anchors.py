"""Balloon anchors for the drive-train exploded cluster sheets.

A frozen point is on an edge of the family's lowest-named shown instance,
in that part's own millimetres, so view scale, placement and explode
distance do not move it. The build projects it onto the sheet, hit-tests
the sheet there and refuses the balloon unless the edge it finds is that
instance's (``_drawing_balloons._select_balloon_anchor``).

``BalloonAnchor()`` walks: it hit-tests the body's extreme points along
fixed directions (``_drawing_balloons._walk_points``), ranked by geometry,
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

The single south end disc uses a walked edge on cylinder-end-disc-1.
There is no north disc: MHA-DT-VN-68 bears directly between gear 19 and
the north strap (user ruling 2026-10-20).

The MHA-DT-VN-57 block screw is pinned to the front (south) block's west
screw, slotted-screw-3 (x -4.65, z -85.59 in the assembly), which stands
clear above that block: none of the 24 points tried on the first,
slotted-screw-1, found its own ink, and the listed-edge leader SolidWorks
placed ended on the front MHA-DT-14 strap (machinist review of 53a7c4266,
balloon 31, two runs).

The cone gear is pinned mid-stack, dt-cone-gear-10: dt-cone-gear-1 sat
against MHA-DT-07 before the gears slid toward the tip, and its walked
leader ended 1.9 mm from the 64T gear's (machinist review of 82158b1bb,
balloons 35 and 36).
"""

from __future__ import annotations

from _drawing_balloons import BalloonAnchor

DRIVE_TRAIN_BALLOON_ANCHORS: dict[str, dict[str, BalloonAnchor]] = {
    "cylinder-bank": {
        "dt-cylinder-gear-shaft": BalloonAnchor(),
        "dt-arbor-pedestal": BalloonAnchor(),
        "dt-cylinder-end-disc": BalloonAnchor(),
        "dt-vn-cylinder-bank-spring": BalloonAnchor(),
        "dt-vn-arbor-set-screw": BalloonAnchor(),
        "dt-cylinder-gear": BalloonAnchor(),
        "dt-vn-pedestal-hold-down-screw": BalloonAnchor(instance="dt-vn-pedestal-hold-down-screw-1"),
    },
    "cone-set": {
        "dt-cone-swing-platform": BalloonAnchor(),
        "dt-cone-pivot-post": BalloonAnchor(),
        "dt-vn-post-mount-screw": BalloonAnchor(),
        "dt-cone-tip-block": BalloonAnchor(),
        "dt-vn-cone-tip-block-screw": BalloonAnchor(),
        "dt-vn-cone-tip-collar": BalloonAnchor(),
        "dt-vn-cone-tip-adjuster": BalloonAnchor(),
        "dt-vn-cone-tip-pinch-screw": BalloonAnchor(),
        "dt-vn-cone-lock-knob": BalloonAnchor(),
        "dt-vn-cone-pivot-screw": BalloonAnchor(),
        "dt-vn-swing-stop-screw": BalloonAnchor(),
        "dt-cone-gear-shaft": BalloonAnchor(),
        "dt-crank-drive-gear": BalloonAnchor(),
        "dt-cone-gear": BalloonAnchor(instance="dt-cone-gear-10"),
    },
    "crank": {
        "dt-crankshaft": BalloonAnchor(),
        "dt-vn-crank-seat-drive-pin": BalloonAnchor(),
        "dt-crank-pinion": BalloonAnchor(),
        "dt-crank-hub": BalloonAnchor(),
        "dt-vn-crank-hub-pin": BalloonAnchor(),
        "dt-crank-arm": BalloonAnchor(),
        "dt-crank-pin": BalloonAnchor(),
        "dt-crank-pin-ring": BalloonAnchor(),
        "dt-crank-pinion-pin": BalloonAnchor(),
        "dt-crank-pin-eye": BalloonAnchor(),
        "dt-vn-keeper-chain": BalloonAnchor(),
        "dt-vn-keeper-chain-link": BalloonAnchor(),
        "dt-vn-fillister-screw": BalloonAnchor(),
        "dt-crank-handle": BalloonAnchor(),
        "dt-crank-handle-ferrule": BalloonAnchor(),
        "dt-crank-handle-butt-cup": BalloonAnchor(),
        "dt-crank-handle-pivot-screw": BalloonAnchor(),
    },
    "pinion-rig": {
        "dt-alignment-pinion": BalloonAnchor(),
        "dt-pinion-bracket": BalloonAnchor(),
        "dt-vn-pinion-strap-pin": BalloonAnchor(),
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
        "dt-vn-slotted-screw": BalloonAnchor(instance="dt-vn-slotted-screw-3"),
        "dt-vn-foot-screw": BalloonAnchor(),
    },
}
