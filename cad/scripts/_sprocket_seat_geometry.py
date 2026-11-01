r"""Shared ANSI #25 sprocket, crank-hub and shaft-seat interface.

Pure dimensions and parameterized geometry only: no part specs, stock checks,
chain solver or SolidWorks imports.  Both shaft seats and their drive dowels
read this interface independently of the removable sprocket's tooth model.
"""

from __future__ import annotations

_MM_PER_IN = 25.4

# A bought chain's axial envelope (PEER Chain 25R size chart, read
# 2026-09-30, https://www.peerchain.com/chain-pitches/): roller width W, the
# width between the inner plates, 0.125 in; chain centreline to the riveted
# pin head F 0.154 in and to the connecting link's clip G 0.185 in.  The
# CAD links (``_chain.PIN_HALF_LEN``) are narrower.  The clearance stacks take
# G on both sides (the clip may face either way) at every radius the plates
# reach, which also covers the riveted heads.
ANSI_ROLLER_WIDTH = 0.125 * _MM_PER_IN  # 3.175
ANSI_HALF_WIDTH = 0.185 * _MM_PER_IN  # 4.699

# Supplied 0.110 in plate (2.794 mm), hub removed flush.  Incoming inspection
# never accepts over nominal; facing the hub flush must not cut below the
# plate face or change the existing z stack.
PLATE = 2.8
PLATE_BAND = (0.0, -0.10)  # (upper, lower) deviations

# Float model: the chain rides the 2.8 wheel and floats axially until an
# inner plate's inner face meets a wheel face.  Measured from the SEAT face
# (the wheel's rear face): frontmost, the rear inner plate lies on the seat
# face; rearmost, the front inner plate lies on the front face of the
# thinnest wheel the band allows.
CHAIN_REACH_FRONT = ANSI_ROLLER_WIDTH / 2.0 + ANSI_HALF_WIDTH  # 6.286


def chain_reach_rear(plate: float) -> float:
    """How far behind the seat face the chain's envelope reaches on a wheel
    ``plate`` thick."""
    return ANSI_ROLLER_WIDTH / 2.0 + ANSI_HALF_WIDTH - plate


CHAIN_REACH_REAR_WORST = chain_reach_rear(PLATE + min(PLATE_BAND))  # 3.587
BORE_DIA = 10.3  # 13/32 in, 0.39 radial clear of the Ø9.525 shaft/pilot
PIN_HOLE_DIA = 2.5  # slip over the Ø2.38 drive pins (0.06 radial)
PIN_CIRCLE_DIA = 14.0
PIN_CIRCLE_RADIUS = PIN_CIRCLE_DIA / 2.0
# Two holes at 180 deg on the part's (and the shafts') +/-Y: 12 and 6 o'clock.
PIN_HOLE_ANGLES_DEG = (90.0, 270.0)
# Each drive pin and wheel hole is located +/-0.025 from the axis at .XXX.
# Their 0.119 diametral clearance absorbs both parts' spacing error, each
# spending half of it.
DRIVE_PIN_OFFSET_PLACES = 3
DRIVE_PIN_OFFSET_TOL = 0.025

# Bore <-> pin-hole web, photo-faithful to the p.56 catalogue view: below the
# 1.5 wall floor, pending ruling #1377.  The printed worst case reads the
# title block's drilled-hole row in pd_transgear_removable_notes, not here.
BORE_PIN_WEB = PIN_CIRCLE_RADIUS - PIN_HOLE_DIA / 2.0 - BORE_DIA / 2.0  # 0.60

# User ruling 2026-09-30: 1.8 forward of the first seat (-152.5); the chain
# plane, both wheels and both shafts' seat faces moved with it.
SEAT_FACE_Z = -154.3  # wheel rear face = shaft seat face (the stack datum)
BAND_FRONT_Z = SEAT_FACE_Z - PLATE  # -157.1, wheel front face
CHAIN_MID_Z = SEAT_FACE_Z - PLATE / 2.0  # -155.7, the ONE chain plane

# Two purchased 3/32 dowels pressed into each shaft's seat face, rounded end
# proud by DRIVE_PIN_PROUD: 1/4 long in the crank (MHA-DT-VN-67), 3/16 in the
# knob shaft (MHA-PD-VN-54).  Each pin spec asserts the interface's diameter.
DRIVE_PIN_DIA = 3.0 / 32.0 * _MM_PER_IN  # 2.38125
DRIVE_PIN_PROUD = 2.4
DRIVE_PIN_TIP_Z = SEAT_FACE_Z - DRIVE_PIN_PROUD  # -156.7
DRIVE_PIN_HOLE_DIA = 2.38  # reamed for the press (3/32 nominal)
# Light press of the hardened 3/32 dowel; the shafts retain their own
# catalogue-diameter and interference checks.
DRIVE_PIN_HOLE_BAND = (0.000, -0.010)
# The shared 98381A stock dowel family's +/-0.010 in length grade.
DRIVE_PIN_LENGTH_GRADE = 0.010 * _MM_PER_IN

# The flat face the wheel's rear face beds on: a Ø17.5 spigot on the crank
# collar, the whole Ø17.5 collar on the knob shaft.  Small enough that the
# #25 plates wrapping the T12 clear it (Main's ruling, 2026-09-30).
SEAT_SPIGOT_DIA = 17.5
# Both seats share the crank spigot's functional diameter band: the
# removables must swap between shafts without changing their radial air.
SPIGOT_DIA_BAND = (0.0, -0.10)
# Pin hole to the spigot's rim: under the 1.5 wall floor (pending ruling #991).
SEAT_SPIGOT_RIM = (
    SEAT_SPIGOT_DIA / 2.0 - PIN_CIRCLE_RADIUS - DRIVE_PIN_HOLE_DIA / 2.0
)  # 0.56
