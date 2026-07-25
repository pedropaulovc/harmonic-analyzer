"""Machine-level installation contract imposed by cone-pivot-post-v2.

The source part keeps the hand-derived v2 coordinate frame.  Installation
turns the casting end-for-end and applies the ch30 p004 fitted displacement.
Every downstream assembly imports these values instead of repeating the
photo-fit literals.
"""

from __future__ import annotations


POST_ROTATION_Y_DEG = 180.0

MACHINE_X_SHIFT = 1.484
MACHINE_Z_SHIFT = 35.415

FORMER_DRUM_X = -54.7
DRUM_X = FORMER_DRUM_X + MACHINE_X_SHIFT

FORMER_CHANNEL_Z0 = -67.1
CHANNEL_Z0 = FORMER_CHANNEL_Z0 + MACHINE_Z_SHIFT

# The front column pair remains at the photographed chain/output plane.  Only
# the rear pair moves with the re-anchored channel/support envelope.
FRAME_FRONT_COLUMN_Z = -112.0
FRAME_REAR_COLUMN_Z = 112.0 + MACHINE_Z_SHIFT
FRAME_COLUMN_Z_CENTER = (
    FRAME_FRONT_COLUMN_Z + FRAME_REAR_COLUMN_Z
) / 2.0
FRAME_COLUMN_Z_SPAN = FRAME_REAR_COLUMN_Z - FRAME_FRONT_COLUMN_Z

ROCKER_SUPPORT_Z = MACHINE_Z_SHIFT
SUMMING_Z = MACHINE_Z_SHIFT
