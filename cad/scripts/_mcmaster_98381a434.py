"""Pure 98381A434 dowel dimensions; isolate this SKU's cache inputs."""

from _dowel_dimensions import DIA_BAND_IN, MM_PER_IN

__all__ = ["DIA_BAND_IN", "DOWEL_SIZE", "ENDS", "MM_PER_IN"]

# part:        (nominal dia, length), mm
DOWEL_SIZE = (3.0 / 32.0 * MM_PER_IN, 0.25 * MM_PER_IN)  # 3/32 x 1/4
ENDS = None
