"""Pure catalogue inputs for McMaster-Carr 9666K142 music wire; no diagnostic imports.

Both amplification wires (the LeverWire and PenWire members of MHA-SH-VN-56)
are cut from this one coil. Read live on 2026-11-13: lubricated 1080 spring
steel, ASTM A228, cold drawn, hardened, phosphate coated, tensile strength
261,000 psi, diameter 0.008 in -0.001/+0.001, 1,450 ft in a 1/4 lb coil.
"""

SKU = "9666K142"
CATALOG_URL = "https://www.mcmaster.com/9666K142/"
CATALOG_CHECKED_DATE = "2026-11-13"
CATALOG_STANDARD = "ASTM A228"
CATALOG_TENSILE_PSI = 261_000

DIA_IN = 0.008
DIA_TOL_IN = 0.001  # Catalogue "-0.001 in to 0.001 in".
DIA = DIA_IN * 25.4
DIA_MIN = (DIA_IN - DIA_TOL_IN) * 25.4
DIA_MAX = (DIA_IN + DIA_TOL_IN) * 25.4
