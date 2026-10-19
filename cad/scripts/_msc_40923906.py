"""MSC 40923906 source limits and explicitly selected representative geometry.

Primary evidence: user-supplied ``msc-40923906.pdf``, one INCH sheet, CDS,
inspected 2026-10-19. Limits do not supply a nominal or a dome-radius law.
After the functional McMaster replacement search, the user authorized the
midband skirt/slot and partial-thread representative below. The independent
max-limit drawing envelope continues to reproduce the source's limits.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class SupplierSize:
    """Source inches, exactly as printed; ``lower=None`` means no stated band."""

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
# Retained source upper extents and thread identity; not supplier nominals.
# MHA-VN-031 alone trims the original stock length.
FILLISTER_SIZE = (6.35, 4.0 * 25.4, 0.237 * 25.4, 0.414 * 25.4, 25.4 / 20.0)

# User-authorized representative choices, 2026-10-19: the arithmetic midbands
# are MODEL values, never asserted as supplier-specified nominals. The former
# family laws (.8H skirt, .135D slot, full-shank thread) are not used by this SKU.
MODEL_STRAIGHT_SKIRT_MM = (
    SUPPLIER_STRAIGHT_SKIRT.upper_in + SUPPLIER_STRAIGHT_SKIRT.lower_in
) * 0.5 * 25.4
MODEL_SLOT_WIDTH_MM = (
    SUPPLIER_SLOT_WIDTH.upper_in + SUPPLIER_SLOT_WIDTH.lower_in
) * 0.5 * 25.4
MODEL_SLOT_DEPTH_MM = (
    SUPPLIER_SLOT_DEPTH.upper_in + SUPPLIER_SLOT_DEPTH.lower_in
) * 0.5 * 25.4
MODEL_THREAD_LENGTH_MM = SUPPLIER_THREAD_LENGTH.envelope_mm
# Preserve the previous author's under-head round; the source gives no radius.
MODEL_JUNCTION_FILLET_MM = FILLISTER_SIZE[4] / 10.0
MODEL_PLAIN_SHANK_MM = FILLISTER_SIZE[1] - MODEL_THREAD_LENGTH_MM
# The source omits crown curvature. Retain a spherical representative joining
# the selected skirt to the original maximum-height crown, explicitly NOT
# supplier-exact shape. It does not drive the source bounding-envelope sheet.
MODEL_DOME_HEIGHT_MM = FILLISTER_SIZE[2] - MODEL_STRAIGHT_SKIRT_MM
MODEL_DOME_RADIUS_MM = (
    (FILLISTER_SIZE[3] / 2.0) ** 2 + MODEL_DOME_HEIGHT_MM**2
) / (2.0 * MODEL_DOME_HEIGHT_MM)
