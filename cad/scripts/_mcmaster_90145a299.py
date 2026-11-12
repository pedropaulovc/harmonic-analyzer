"""Pure 90145A299 dowel dimensions; isolate this SKU's cache inputs.

McMaster-Carr 90145A299: 18-8 stainless steel dowel pin, 5/64 x 5/16,
chamfered both ends, passivated (product page and 2-D drawing read live
2026-11-11, cad/references/mcmaster/README.md). Its diameter band is its own,
0 to +.0002 in over nominal, not the 98381A family's +.0001/+.0003
(``_dowel_dimensions.DIA_BAND_IN``).
"""

SKU = "90145A299"
MM_PER_IN = 25.4

# (nominal dia, length), mm: 5/64 x 5/16.
DOWEL_SIZE = (5.0 / 64.0 * MM_PER_IN, 5.0 / 16.0 * MM_PER_IN)
# Catalogue diameter deviations over nominal, in: the drawing's .0781 +.0002/-.0000.
DIA_BAND_IN = (0.0, 0.0002)
# The catalogue prints the length .313 with no band; ASME B18.8.2's dowel
# length grade is +/-.010 in. [assumed: catalogue prints no length band]
LENGTH_GRADE_IN = 0.010
