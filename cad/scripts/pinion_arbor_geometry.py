r"""Nominal envelope of the integral MHA-102 pinion arbor.

Only the turned geometry the drive-train assembly places and checks lives here:
the shaft, the grip head and neck, the MHA-058 crossrod hole and the MHA-144
pin station.  Bands, finishes, journal lands and drawing data stay in
``pinion_arbor_spec``, which re-exports these names, so an edit to the print
does not re-key the drive-train assembly.
"""

from __future__ import annotations


SHAFT_DIA = 8.0
SHAFT_LEN = 226.25  # unchanged origin-to-back-crown-root station

# Former handle-body envelope, turned integrally with the arbor.  Rule 12
# (audit W6, 2026-09-23): the Ø6 crossrod hole left 1.50 of wall to each face
# of the 9.0 head at nominal and -0.10 at the printed worst case (HeadLen and
# the hole station both .X).  The head grows to 10.5 about the unchanged
# crossrod station (world z -6.5), and the hole is printed CENTRED on the head
# length rather than located by a .X station, so only the HeadLen band reaches
# the web: (10.5 - 0.8) / 2 - 6.10 / 2 = 1.80 worst case.
HEAD_DIA = 15.0
HEAD_LEN = 10.5
HEAD_CAP_SAG = 3.0
HEAD_CAP_R = ((HEAD_DIA / 2.0) ** 2 + HEAD_CAP_SAG**2) / (2.0 * HEAD_CAP_SAG)
HEAD_CENTER_Z = -6.5  # the released crossrod station
HEAD_REAR_Z = HEAD_CENTER_Z + HEAD_LEN / 2.0
HEAD_FRONT_Z = HEAD_CENTER_Z - HEAD_LEN / 2.0
NECK_DIA = 10.5
NECK_END_Z = 10.0
NECK_LEN = NECK_END_Z - HEAD_REAR_Z
EXPOSED_SHAFT_LEN = SHAFT_LEN - NECK_END_Z
# R1 (U27 precedent, Main 2026-09-24): a stock 6 mm reamer cuts 6.000-6.015
# and as-received bar is at most 6.000, so a novice cannot make the old 0.0125
# press.  The hole is reamed Ø6.00 +0.10/0 and MHA-058 is bonded in with
# Loctite 638; the model carries both at the 6.00 nominal (line to line).
CROSS_HOLE_DIA = 6.0

# R1a (user, 2026-09-24): the station of the cross hole for the MHA-144
# collar's spring pin, at the general .X band from the head rear face (U27:
# the collar-to-strap gap grows to absorb it, pinion_arbor_collar_spec).  The
# drive-train assembly reads the station; the hole itself and its clearance
# proofs live in pinion_arbor_pin_spec.
PIN_STATION_FROM_HEAD_REAR = 39.0
PIN_Z = HEAD_REAR_Z + PIN_STATION_FROM_HEAD_REAR
