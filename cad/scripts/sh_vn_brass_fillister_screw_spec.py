"""Pure McMaster 90114A511 brass fillister dimensions for DT, FR and PD.

Native parts retain their parent-specific identities and recipes. Mechanical
specs, layouts and assemblies read these dimensions without importing a recipe.
"""

BF_MAJOR_R = 2.8448 / 2.0
BF_LEN = 6.35
BF_HH = 2.7178
BF_HEAD_R = 4.6482 / 2.0
BF_PITCH = 0.635
BF_SLOT_W = 0.9906  # Slot Width@Sketch1
BF_SLOT_D = 1.2192  # Slot Depth@Sketch1

THREAD = "#4-40"
HEAD_DIA = 2.0 * BF_HEAD_R
HEAD_H = BF_HH
SHANK_DIA = 2.0 * BF_MAJOR_R
SHANK_LEN = BF_LEN
