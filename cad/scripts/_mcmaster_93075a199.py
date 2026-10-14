"""Pure 93075A199 catalogue dimensions; keep mechanical specs off recipe closures.

McMaster 93075A199 product page read live on 2026-10-14
(https://www.mcmaster.com/93075A199/): low-strength zinc-plated steel hex
head screw, 8-32 UNC Class 2A, 1 in long (measured from under the head),
fully threaded, flat tip, ASME B18.6.3; head 1/4 in wide, 7/64 in high.  The
head height is the 93075A* vendor-model value (93075A194's 2.794), which the
family laws in ``diagnostics/diag_mcmaster_hex_head.py`` read.
"""

HX_MAJOR_R = 4.1656 / 2.0
HX_LEN = 25.4
HX_HW = 6.35  # across flats
HX_HH = 2.794
HX_PITCH = 0.79375
HX_UNDERSIDE = (HX_LEN - HX_HH) / 2.0  # vendor origin sits mid-overall
HX_TIP_CHAMFER = HX_PITCH * 0.851  # the family's 45 deg x P*0.851 tip chamfer
