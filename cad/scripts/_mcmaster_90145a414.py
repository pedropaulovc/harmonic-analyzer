"""Pure 90145A414 dowel dimensions; isolate this SKU's cache inputs."""

from _dowel_dimensions import MM_PER_IN

__all__ = ["DIA_BAND_IN", "DOWEL_SIZE", "ENDS", "MM_PER_IN"]

# 18-8 stainless dowel's catalogue diameter tolerance over nominal, in inches
# (https://www.mcmaster.com/90145A414/, read live 2026-11-11): 0 to +.0002,
# not the 98381A alloy family's +.0001/+.0003.
DIA_BAND_IN = (0.0, 0.0002)

# part:        (nominal dia, length), mm
DOWEL_SIZE = (1.0 / 16.0 * MM_PER_IN, 3.0 / 16.0 * MM_PER_IN)  # 1/16 x 3/16
# The page states "Chamfer" ends but no chamfer size, and no vendor model is
# tracked: the recipe models the plain nominal cylinder.
ENDS = None
