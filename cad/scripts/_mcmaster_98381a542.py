"""Pure 98381A542 dowel dimensions; isolate this SKU's cache inputs.

McMaster 98381A542: alloy steel, 1/4 x 1 in, diameter +.0001/+.0003 in, Rockwell
C47 min, ASME B18.8.2, end shape "Round x Chamfer" (live category table
https://www.mcmaster.com/products/dowel-pins/diameter~1-4/length~1/, read
2026-10-31; the length tolerance is not stated).

End forms read off McMaster's STEP (``98381A542.STEP``, SHA-256
``2c11cd08667f18773a813b3238df808c1015083b683b6e4a5eb26d88f07853a9``,
downloaded 2026-10-30; read for dimensions only): a flat Ø.235 end face and a
cone at 16 deg to the axis at one end (the chamfer, .0262 long), the Ø.250
cylinder, and a .031 radius tangent to the cylinder down to a flat Ø.188 face
at the other (the round end). The STEP is a nominal reference, not a
tolerance specimen: limits come from the page's band.
"""

from _dowel_dimensions import DIA_BAND_IN, MM_PER_IN, DowelEnds

__all__ = ["DIA_BAND_IN", "DOWEL_SIZE", "ENDS", "MM_PER_IN"]

# part:        (nominal dia, length), mm
DOWEL_SIZE = (0.25 * MM_PER_IN, 1.0 * MM_PER_IN)  # 1/4 x 1

ENDS = DowelEnds(
    point_dia=0.235 * MM_PER_IN, chamfer_deg=16.0, crown_r=0.031 * MM_PER_IN
)
