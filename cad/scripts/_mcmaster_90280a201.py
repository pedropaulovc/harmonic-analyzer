"""Pure McMaster 90280A201 steel fillister dimensions for MG and PD.

Native parts retain their parent-specific identities and recipes. Mechanical
specs, layouts and assemblies read this SKU's dimensions without importing CAD.
"""

FILLISTER_SIZE = (4.1656, 31.75, 3.9624, 6.858, 0.79375)

SHANK_DIA, SHANK_LEN, HEAD_H, HEAD_DIA, _PITCH = FILLISTER_SIZE
