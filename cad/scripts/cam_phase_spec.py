"""Authored cam phase -- the drive-interface contract between drive-train and
channel.

PURE DATA, no SolidWorks/COM imports (the ``connecting_rod_spec`` pattern).

``CAM_PHASE_DEG`` is the authored rotation of every cylinder gear's integral
eccentric cam, measured from lobe-UP (= the cos-mode home, notch up).  Both
assemblies MUST read this one constant: ``build_drive_train_assembly`` seeds
the cylinder gears with it (``rot_z_rows(-CAM_PHASE_DEG)`` before the local-Y
flip) and ``build_channel_assembly`` derives ``RING_CENTER`` (and hence the
whole rod/rocker closure) from it -- the channel's floating connecting-rod
rings land on the drive-train's cam lobes at the top level POSITIONALLY, with
no mate, so a phase drift between the two is an invisible 8 mm lie until the
top-level interference gate trips.

Value: 88.5 = 1.5 + 29 whole 3-degree T120 tooth pitches.  The +1.5 half-pitch
keeps the tooth-in-gap mesh with the phase-0 cone gears (the drum gear must
present a GAP at the contact azimuth); adding whole pitches preserves it.  The
29-pitch offset parks the authored rest at the SINE-mode home -- the notches
at the SIDE, the "middle position" (engineerguy video 4/4) -- which puts the
ring at MID-throw with the rocker arm LEVEL, so the working swing is
symmetric: level +-~3.72 deg (PR #458; the retired 1.5 cos-home authoring
paired level with the ring's TOP and could only ever swing the rod side DOWN,
a one-sided stroke that biased every channel's Fourier contribution).  Which
SIDE the notch faces (+x, toward the rocker pivot) is a modeling choice --
the mirror phase -85.5 is an equally valid sine home; flip it here if photo
evidence surfaces.
"""

from __future__ import annotations

CAM_PHASE_DEG = 88.5
