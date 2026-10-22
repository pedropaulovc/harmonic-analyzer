"""Pure 40923906 fillister dimensions; isolate each SKU's cache inputs."""

from dataclasses import dataclass

# Value Collection MSC 40923906, 1/4-20 x 4 in slotted fillister,
# SAE J82 steel, zinc.  Catalog-only ideal model: the existing ASME
# B18.6.3 1/4 maxima (A 0.414, O 0.237) and family geometry laws, not
# vendor CAD or a measured replica.  The full-shank modeled thread does
# not verify the supplier's threaded length.  MHA-DT-VN-61 cuts the
# supplied 4 in stock to fit; never change this row to its cut length.
FILLISTER_SIZE = (6.35, 4.0 * 25.4, 0.237 * 25.4, 0.414 * 25.4, 25.4 / 20.0)


# Drawing-reference metadata only. The supplied engineering drawing (CDS,
# INCH/NTS; user-supplied msc-40923906.pdf, inspected 2026-10-19) does NOT
# authorize changing the existing catalogue-family solid above. In particular,
# the current skirt/slot laws and full-shank thread differ from this source.
# The separate construction-only maximum-limit envelope owns these dimensions.


@dataclass(frozen=True)
class SupplierSize:
    """Printed source inches; a paired limit is not a supplier nominal."""

    upper_in: float
    lower_in: float | None = None

    @property
    def envelope_mm(self) -> float:
        return self.upper_in * 25.4

    @property
    def deviations_mm(self) -> tuple[float, float] | None:
        if self.lower_in is None:
            return None
        return ((self.lower_in - self.upper_in) * 25.4, 0.0)


SUPPLIER_SOURCE = "MSC 40923906 engineering drawing; CDS; INCH; supplied 2026-10-19"
SUPPLIER_THREAD = "1/4-20 UNC"
SUPPLIER_PRECISION = 3
SUPPLIER_HEAD_OD = SupplierSize(0.414, 0.389)
SUPPLIER_HEAD_HEIGHT = SupplierSize(0.237, 0.207)
SUPPLIER_STRAIGHT_SKIRT = SupplierSize(0.170, 0.155)
SUPPLIER_SLOT_WIDTH = SupplierSize(0.075, 0.064)
SUPPLIER_SLOT_DEPTH = SupplierSize(0.109, 0.087)
SUPPLIER_STOCK_LENGTH = SupplierSize(4.000, 3.910)
SUPPLIER_THREAD_LENGTH = SupplierSize(1.500)
