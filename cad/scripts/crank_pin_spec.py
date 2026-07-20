r"""Pure-data dimensional contract shared by the crank pin, its drawing, and
the mating cross-hole reams (crank arm hub + crankshaft).

The ch11 close-ups (``ch11_images/page001_img02`` hero, ``page002_img01``
isolated pin) show the pin as FOUR turned regions on one axis: the 1:48
tapered barrel with a bullet-nose small end, a turned NECK carrying the
brass pull ring through a cross-hole, and a short cylindrical mushroom
pull-HEAD with a domed front face.

The mating parts import ``hole_dia_at`` so the arm-hub and crankshaft
cross-holes are the SAME 1:48 cone the pin is (the as-taper-reamed
assembly state) plus the standard 0.25 diametral running clearance --
the drive-train places the pin at ``PIN_SEAT_PROUD`` without solid
interference (the old straight #14/#9 pilots could not seat a taper).
"""

from __future__ import annotations


PIN_LENGTH = 45.0
# CUSTOM 1:48 self-holding taper (0.9375 on diameter over the 45 mm length),
# dimensioned by its two end diameters on the drawing -- NOT a standard No. 2
# taper pin (whose 0.193 in / Ø4.90 large end would not match these ends). The
# Ø5.0 small end sits at the crank-arm cross-hole nominal; the big end is the
# small end plus the 1:48 on-diameter rise, so the drive-fit taper contacts along
# its whole length. The crank arm's cross-hole is taper-reamed with the shaft to
# the same 1:48 to suit this pin at assembly.
SMALL_END_DIA = 5.0
BIG_END_DIA = SMALL_END_DIA + PIN_LENGTH / 48.0  # 5.9375
TAPER_PER_MM = 1.0 / 48.0  # on-diameter shrink per mm from the big end

# Pull hardware at the big end (photo-scaled from page002_img01, low):
# barrel big-end face at model x=0; the neck spans -NECK_LEN..0 and the
# head -(NECK_LEN+HEAD_LEN)..-NECK_LEN, so the barrel keeps its own x=0..45.
NECK_DIA = 4.0
NECK_LEN = 3.0
HEAD_DIA = 8.0
HEAD_LEN = 6.0
HEAD_DOME_R = 3.9  # near-full-radius rim fillet -> the mushroom dome
TIP_DOME_R = 2.4  # bullet-nose fillet on the Ø5 small end
RING_HOLE_DIA = 2.6  # cross-hole through the neck carrying the pull ring --
# sized so the CURVED ring wire clears the hole-mouth corners by the 0.25
# design margin (a Ø2.0 hole grazes the wire at the mouths: 0.00 mm^3
# checker slivers); the ring hangs straight (no in-hole tilt), so no extra
# tilt budget is needed

# Brass pull ring (open C, round wire) riding the neck cross-hole.
RING_WIRE_DIA = 1.5
RING_OD = 14.0
RING_MEAN_R = (RING_OD - RING_WIRE_DIA) / 2.0  # 6.25: wire-centre radius
RING_SWEEP_DEG = 300.0  # open C: 60 deg gap

# As-reamed cross-hole cone (arm hub + crankshaft): the pin's own 1:48 cone
# plus the standard diametral running clearance, seated with the barrel
# PIN_SEAT_PROUD mm proud of the arm hub's outboard flank.
HOLE_CLEARANCE_DIA = 0.25
PIN_SEAT_PROUD = 7.0  # was the photo-scaled 4.5; +2.5 moves the neck -- and
# the pull ring's whole hanging plane -- west of the paper-drive chain
# wrapping the crank T12 (measured westmost link plate x -137.84, sprocket
# rim reach x -137.2 at the ring's closest y; ring slab lands
# -140.05..-138.55, 0.7 clear). A Z-axis neck hole forces the ring's full
# OD along machine z, so no permissible in-hole swing could clear the
# 6.7-wide chain band in z -- x separation is the only clean escape, and
# the extra exposed neck is the least-visible deviation: the ring itself
# hangs over and hides that region in the ch11 photos.


def pin_dia_at(dist_from_big_end_mm: float) -> float:
    """Pin barrel diameter at a station measured from the big-end face."""
    return BIG_END_DIA - dist_from_big_end_mm * TAPER_PER_MM


def hole_dia_at(dist_from_big_end_mm: float) -> float:
    """As-reamed cross-hole diameter at the same station (pin + clearance)."""
    return pin_dia_at(dist_from_big_end_mm) + HOLE_CLEARANCE_DIA


DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "PinProfile": {"Length"},
}

DRAWING_NOTES = "\n".join(
    (
        "CUSTOM 1:48 SELF-HOLDING TAPER (0.9375 ON DIA OVER 45.0) BETWEEN THE END "
        "DIAMETERS SHOWN: TURN IN ONE CONTINUOUS PASS; NO STEPS.",
        "PULL HEAD: <MOD-DIAM>8 X 6 LONG, FULL-RADIUS DOMED FACE, ON A "
        "<MOD-DIAM>4 X 3 NECK; <MOD-DIAM>2.6 CROSS-HOLE THROUGH THE NECK FOR "
        "THE BRASS PULL RING.",
        "ROUND THE SMALL END FULL-RADIUS (BULLET NOSE).",
        "HAND-FIT TO THE CRANK-ARM HUB CROSS-HOLE, TAPER-REAMED WITH THE SHAFT AT "
        "ASSEMBLY TO THE SAME 1:48; LIGHT DRIVE FIT, REMOVABLE BY TAP ON SMALL END.",
    )
)
END_VIEW_NOTE = "END VIEW SCALE 4:1"
