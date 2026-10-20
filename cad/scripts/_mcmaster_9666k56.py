"""Pure catalogue inputs for McMaster-Carr 9666K56 music wire; no diagnostic imports.

Both amplification wires (MHA-MG-VN-56 lever wire, MHA-PN-VN-57 pen wire) are cut
from this one coil.
"""

SKU = "9666K56"
CATALOG_URL = "https://www.mcmaster.com/9666K56/"
CATALOG_CHECKED_DATE = "2026-10-14"
CATALOG_STANDARD = "ASTM A228"
CATALOG_MATERIAL = "1080 Spring Steel"
CATALOG_FINISH = "Phosphate Coated"
CATALOG_TEMPER = "Spring"
CATALOG_TENSILE_PSI = 261_000
CATALOG_CONTAINER = "1/4 lb. Coil"
CATALOG_LENGTH_FT = 110

DIA_IN = 0.031
DIA_TOL_IN = 0.001  # Catalogue "-0.001 in to 0.001 in".
DIA = DIA_IN * 25.4
DIA_MIN = (DIA_IN - DIA_TOL_IN) * 25.4
DIA_MAX = (DIA_IN + DIA_TOL_IN) * 25.4
