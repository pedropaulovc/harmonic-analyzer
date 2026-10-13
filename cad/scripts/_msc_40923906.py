"""Pure 40923906 fillister dimensions; isolate each SKU's cache inputs."""

# Value Collection MSC 40923906, 1/4-20 x 4 in slotted fillister,
# SAE J82 steel, zinc.  Catalog-only ideal model: the existing ASME
# B18.6.3 1/4 maxima (A 0.414, O 0.237) and family geometry laws, not
# vendor CAD or a measured replica.  The full-shank modeled thread does
# not verify the supplier's threaded length.  MHA-VN-031 cuts the
# supplied 4 in stock to fit; never change this row to its cut length.
FILLISTER_SIZE = (6.35, 4.0 * 25.4, 0.237 * 25.4, 0.414 * 25.4, 25.4 / 20.0)
