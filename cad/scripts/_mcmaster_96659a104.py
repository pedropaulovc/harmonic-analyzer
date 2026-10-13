"""Pure McMaster 96659A104 catalogue and conforming washer size bounds."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class WasherDimensions:
    part_no: str
    id: float
    od: float
    thickness_min: float
    thickness_max: float
    id_min: float
    id_max: float
    od_min: float
    od_max: float
    od_id_runout_max: float

    @property
    def thickness(self) -> float:
        return (self.thickness_min + self.thickness_max) / 2


CATALOG_URL = "https://www.mcmaster.com/96659A104/"
CATALOG_CHECKED_DATE = "2026-10-13"
CATALOG_STANDARD = "ASME B18.21.1"
CATALOG_DIAMETER_TOLERANCES = None  # Separate ID/OD bands omitted in SKU table.
BOUND_SOURCE_URL = "https://ssmalloys.com/wp-content/uploads/2024/10/ASME-B18.21.1.pdf"
BOUND_SOURCE = "ASME B18.21.1-2009 Table 11, No. 10 Type A; section 4.5"
# Supplier claims conformity. Table 11: ID .219 +.008/-.005, OD .500
# +.015/-.005, thickness .036..065 in. Section 4.5's OD-to-ID runout is
# conservatively taken as a FULL radial offset, not halved as a TIR value.
DIMS = WasherDimensions(
    part_no="96659A104",
    id=5.5626,
    od=12.7,
    thickness_min=0.9144,
    thickness_max=1.651,
    id_min=5.4356,
    id_max=5.7658,
    od_min=12.573,
    od_max=13.081,
    od_id_runout_max=0.3302,
)
