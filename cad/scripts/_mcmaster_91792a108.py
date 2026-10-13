"""Pure 91792A108 slotted pan-head dimensions; isolate this SKU's cache inputs."""

PART_NO = "91792A108"
IN = 25.4

# McMaster "Stainless Steel Pan Head Slotted Screws" family table, 18-8 rows,
# read live in a headless browser on 2026-10-11 (Rounded Head Screws, 4-40,
# Slotted; the product detail page needs a login): #4-40 x 3/8 in under the
# head, head Ø0.219 in x 0.068 in high, fully threaded, 100,000 psi; family
# facets UNC class 2A, flat tip, ASME B18.6.3. The screw size decimal 0.112 in
# is the #4 basic major.
# (major dia, length, head height, head dia, pitch): the slotted-head
# recipe's size row (diagnostics.diag_mcmaster_fillister.build_fillister).
PAN_HEAD_SIZE = (0.112 * IN, 0.375 * IN, 0.068 * IN, 0.219 * IN, IN / 40.0)
