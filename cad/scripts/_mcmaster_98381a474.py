"""Pure 98381A474 dowel dimensions; isolate this SKU's cache inputs."""

from _dowel_dimensions import DIA_BAND_IN, MM_PER_IN, DowelEnds

__all__ = ["DIA_BAND_IN", "DOWEL_SIZE", "ENDS", "MM_PER_IN"]

# part:        (nominal dia, length), mm
DOWEL_SIZE = (0.125 * MM_PER_IN, 0.875 * MM_PER_IN)  # 1/8 x 7/8 [INFERENCE]

# Read off the 98381A473 harvest (Sketch2 "Point Diameter" 2.921, D3 16 deg,
# "Crown Radius" 0.4064; Revolve1 faces: cone x -9.525..-9.0821, torus
# x 9.1186..9.525, end faces Ø2.921 and Ø2.3622).
ENDS = DowelEnds(
    point_dia=0.115 * MM_PER_IN, chamfer_deg=16.0, crown_r=0.016 * MM_PER_IN
)
# [INFERENCE] the 1/8 series' end forms, read off the 98381A473 harvest.
