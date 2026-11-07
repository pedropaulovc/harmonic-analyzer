"""Pure 98381A417 dowel dimensions; isolate this SKU's cache inputs."""

from _dowel_dimensions import DIA_BAND_IN, MM_PER_IN

__all__ = ["DIA_BAND_IN", "DOWEL_SIZE", "ENDS", "MM_PER_IN"]

# part:        (nominal dia, length), mm
DOWEL_SIZE = (1.0 / 16.0 * MM_PER_IN, 3.0 / 8.0 * MM_PER_IN)  # 1/16 x 3/8
ENDS = None
