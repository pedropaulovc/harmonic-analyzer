"""McMaster 91794A055 dimensions and vendor-model laws in mm, no CAD imports.

MHA-161, the transgear disc screws (x3): 18-8 stainless slotted fillister
head, #0-80 x 1/4, fully threaded (contract §2.6, ruling 4).  They pass
through the brass hub's flange clearance holes and thread into the 120T
disc's #0-80 through taps.

Catalogue (McMaster 91794A055 page, read 2026-09-30): #0-80 UNF class 2A,
1/4 in under the head, fully threaded, high narrow fillister head Ø0.096 in
x 0.055 in high, 18-8 stainless steel.

Laws: the vendor model ``cad/references/mcmaster/91794A055.SLDPRT``
(user-supplied; SHA-256
3b7b3ee38a51864b0c9d495e44ade30c80816d4b5498b8801211b8edb82676dc; harvested
on amet 2026-09-30 into ``cad/out/reports/mcmaster-91794A055-dump.json``).
The file is local-only (© McMaster-Carr, gitignored, never committed).  It
is NOT the 90280A narrow-fillister model (``diag_mcmaster_fillister.py``):
its head has a 5 deg drafted side, a 0.7 band, a neck and two fillets, and
its thread is tip-seeded.  Where that family's fractions disagree, the dump
wins.  Each law below names its source in the dump (dimension@feature, or
the sketch geometry it was read from).  Vendor truth: volume 13.8241 mm^3,
area 64.5474 mm^2, 26 faces.

Frame (the fillister family's): axis +Y, head up, the under-head bearing
face at y = 0 (Top Plane).  The vendor origin sits mid-overall on z, head
+z, so their under-head face is at z = (SHANK_LEN - HEAD_H) / 2.
"""

import math

IN = 25.4

SKU = "91794A055"
THREAD = "#0-80"
THREAD_CLASS = "2A"

# --- catalogue (Sketch1's named driving dimensions agree) -------------------
SHANK_DIA = 0.060 * IN  # "Screw Size Decimal Equivalent@Sketch1" 1.524
SHANK_LEN = 0.25 * IN  # "Length@Sketch1" 6.35, under the head
HEAD_DIA = 0.096 * IN  # "Head Diameter@Sketch1" 2.4384
HEAD_H = 0.055 * IN  # "Head Height@Sketch1" 1.397
PITCH = IN / 80.0  # "Pitch@Sketch1" 0.3175

# --- head (Revolve1 / Sketch2) ----------------------------------------------
# "Approx Head Edge Flat" = Head Height * .7: the drafted side's height from
# the under-head face to the dome rim.
HEAD_BAND = 0.7 * HEAD_H
# D5@Sketch2 = 5 deg: the side narrows toward the bearing face (Line2 runs
# r 1.2192 at the rim to r 1.133645 at the under-head face).
HEAD_SIDE_DRAFT_DEG = 5.0
UNDER_HEAD_DIA = HEAD_DIA - 2.0 * HEAD_BAND * math.tan(
    math.radians(HEAD_SIDE_DRAFT_DEG)
)
# Arc4: a spherical cap centred on the axis through the apex and the rim.
DOME_H = HEAD_H - HEAD_BAND
DOME_R = ((HEAD_DIA / 2.0) ** 2 + DOME_H**2) / (2.0 * DOME_H)

# --- neck under the head (Sketch2) ------------------------------------------
# D3@Sketch2 = Screw Size * .51 (a RADIUS, so Ø1.02 D); D4@Sketch2 =
# Length * .05.  The runout boss below swallows it, so no neck face survives.
NECK_DIA = 2.0 * 0.51 * SHANK_DIA
NECK_LEN = 0.05 * SHANK_LEN

# --- driver slot (Cut-Extrude1 / Sketch9, through all both ways) ------------
SLOT_WIDTH = 0.1 * HEAD_DIA  # D1@Sketch9 = Head Diameter * .1
# Sketch9 geometry: the floor sits at the midpoint of a dome-height
# construction line hung under the rim, i.e. 1.5 dome heights under the apex.
SLOT_DEPTH = 1.5 * DOME_H

# --- fillets ----------------------------------------------------------------
SLOT_FILLET_R = 0.033 * HEAD_H  # D1@Fillet1: the slot floor's two edges
HEAD_FILLET_R = 0.125 * HEAD_H  # D1@Fillet2: under-head rim + dome rim

# --- tip chamfer (Sketch2) --------------------------------------------------
TIP_CHAMFER = 0.75 * PITCH  # D1@Sketch2 = Pitch * .750, D2@Sketch2 = 45 deg

# --- thread (Helix/Spiral1, Sketch7, Cut-Sweep1) ----------------------------
H_SHARP = PITCH * math.sqrt(3.0) / 2.0
ROOT_DIA = SHANK_DIA - 2.0 * 0.75 * H_SHARP  # Sketch7 root r 0.555778
ROOT_FLAT = PITCH / 8.0  # "Pitch/8@Sketch1"; Sketch7 Line3
CUTTER_TOP_W = 7.0 * PITCH / 8.0  # Sketch7 Line1 0.277812, ON the major
CUTTER_CENTRE_PAST_TIP = 7.0 * PITCH / 16.0  # Sketch7, in air past the tip
# D3@Helix/Spiral1 = D4 (Pitch) + Length: tip-seeded, one pitch past the
# under-head face (inside the head, where the groove is a closed void).
HELIX_HEIGHT = SHANK_LEN + PITCH
HELIX_REVS = HELIX_HEIGHT / PITCH

# --- thread runout (Boss-Extrude1 / Sketch8) --------------------------------
# D1@Sketch8 = 0.0508 (0.002 in, a constant: no equation) over the major, on
# the neck's step face; up to the under-head face, and a 60 deg draft
# (D3@Boss-Extrude1, from the axis) toward the tip.
RUNOUT_DIA = SHANK_DIA + 2.0 * 0.0508
RUNOUT_DRAFT_DEG = 60.0

# --- import-time checks -----------------------------------------------------
if not 0.0 < HEAD_H - SLOT_DEPTH < HEAD_BAND:
    raise ValueError(f"{SKU}: the slot floor must sit inside the head's drafted band")
if not SLOT_FILLET_R < SLOT_WIDTH / 2.0:
    raise ValueError(f"{SKU}: the slot fillets overrun the slot")
if not NECK_DIA < RUNOUT_DIA < UNDER_HEAD_DIA - 2.0 * HEAD_FILLET_R:
    raise ValueError(f"{SKU}: the runout must swallow the neck inside the bearing face")
if not HEAD_FILLET_R < min(HEAD_BAND, DOME_H):
    raise ValueError(f"{SKU}: the head fillet overruns a head face")
if not (0.0 < ROOT_DIA < SHANK_DIA and TIP_CHAMFER < SHANK_DIA / 2.0):
    raise ValueError(f"{SKU}: the thread or tip chamfer is inconsistent")
if not math.isclose(HELIX_REVS, round(HELIX_REVS), abs_tol=1e-9):
    raise ValueError(f"{SKU}: the helix must close on whole turns (vendor: 21)")
