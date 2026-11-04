"""Pure 98381A438 dowel dimensions; isolate this SKU's cache inputs.

McMaster 98381A438 (https://www.mcmaster.com/98381A438/, read live
2026-11-03): alloy steel dowel pin, 3/32 in diameter, 1/2 in long, diameter
tolerance 0.0001 to 0.0003 in, Rockwell C47 min, ASME B18.8.2, end shape
"Round x Chamfer". The length tolerance is not stated. No vendor model is
read, so the recipe draws the plain nominal cylinder (the 98381A433 rule).
"""

from _dowel_dimensions import DIA_BAND_IN, MM_PER_IN

__all__ = ["DIA_BAND_IN", "DOWEL_SIZE", "ENDS", "MM_PER_IN"]

# part:        (nominal dia, length), mm
DOWEL_SIZE = (3.0 / 32.0 * MM_PER_IN, 0.5 * MM_PER_IN)  # 3/32 x 1/2
ENDS = None
