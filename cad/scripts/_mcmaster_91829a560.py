"""Pure 91829A560 vendor dimensions; keep mechanical specs off recipe closures."""

import math

# --- vendor dims (all mm/deg, straight from the harvest) -------------------
HEAD_DIA = 9.525  # Head Diameter@Sketch1
HEAD_T = 4.7625  # Head Height@Sketch1
SHOULDER_DIA = 6.35  # Shoulder Diameter@Sketch1
SHOULDER_LEN = 6.35  # Shoulder Length@Sketch1
THREAD_MAJOR = 4.826  # Screw Size Decimal Equivalent@Sketch1
THREAD_LEN = 9.525  # Thread Length@Sketch1
UNDERHEAD_LEN = SHOULDER_LEN + THREAD_LEN  # 15.875
SLOT_W = 1.524  # D1@Sketch8
SLOT_D = 1.905  # D1@Cut-Extrude2
HEAD_CHAMFER = 0.309563  # D1@Chamfer1 (45 deg)
TIP_CHAMFER = 0.43434  # D1@Chamfer2 (45 deg)
UC_LAND_DIA = 3.3528  # CADA@Sketch5 (diametric)
UC_W = 1.6002  # CADB@Sketch5 (fillet + land; also the split-plane offset)
PITCH = 1.058333  # Pitch@Helix/Spiral2 (#10-24: 25.4/24)
REVS = 9.0  # 9000@Helix/Spiral2

# Undercut (vendor Sketch5): R-UC_FILLET quarter-round upper boundary tangent
# to the land, then the land, then the 45-deg lower flank up to the major.
UC_LAND_R = UC_LAND_DIA / 2.0  # 1.6764
UC_FILLET = THREAD_MAJOR / 2.0 - UC_LAND_R  # 0.7366 (fillet R == flank rise)
UC_LAND = UC_W - UC_FILLET  # 0.8636
UC_SPAN = UC_LAND + 2.0 * UC_FILLET  # 2.3368 (junction -> flank@major)

# Thread cutter (vendor Sketch10): UN form.  H is the sharp-V height; the
# groove is the V truncated to a P/8 flat at the root and capped at a 15P/16
# top width (the vendor's D1 = P dims the CONSTRUCTION sharp-V only).
H_SHARP = PITCH * math.sqrt(3.0) / 2.0
ROOT_R = THREAD_MAJOR / 2.0 - 0.75 * H_SHARP  # 1.725585 (vendor: 1.7256)
ROOT_FLAT = PITCH / 8.0  # 0.132292 == vendor D2@Sketch10
CUT_TOP_W = 15.0 * PITCH / 16.0  # 0.992187 (vendor: 0.9922)
CUT_TOP_R = ROOT_R + (CUT_TOP_W - ROOT_FLAT) / 2.0 * math.sqrt(3.0)  # 2.470292
CUT_CENTRE_Y = -UNDERHEAD_LEN - 7.0 * PITCH / 16.0  # -16.338 (vendor, in air)
