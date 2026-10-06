r"""Stock MHA-VN-016 stack collar (McMaster 9414T1) nominals, in mm.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure: the collar's catalogue sizes, which the shaft spec, the drive-train
assembly and the collar's replica recipe
(``diagnostics/diag_build_9414T1.py``) all read.

User ruling 2026-09-29: a set-screw shaft collar on the shaft's Sec4 D-flat
replaces the turned brass tip bushing as MHA-VN-016.  At fit-up it is pushed
against T006 over the 0.45 feeler (cone_stack_end_play.COLLAR_FEELER) and its
set screw locked on the flat, so it retains the gear stack's float on the
shaft.  It is not a thrust face for the tip block: the block and the cup
adjuster only set the shaft's end play, and build_dt_drive_train_assembly holds
the collar clear of the block at print-worst.

Catalogue: the McMaster product page https://www.mcmaster.com/9414T1/ (read in
a headless browser on 2026-09-29): "Set Screw Shaft Collar for 1/16"
Diameter", one piece, black-oxide 1215 carbon steel, 1/16 in bore, 1/4 in OD,
3/16 in wide, one hex-socket set screw (black-oxide steel) included.  The
vendor's STEP model (downloaded for reading only, never committed) supplies
what the page does not: 45 deg breaks 0.009375 in on all four edges, and a
#2-56 radial set screw at mid-width with a cup point, 0.050 in hex socket,
whose outer end stands at 5/32 in from the axis, proud of the 1/8 in OD
radius as supplied.

The catalogue publishes no width or bore tolerance.  WIDTH_BAND_MM is the
assumption the stacks read: +/-0.010 in, twice the +/-0.005 in commercial
set-screw collars are commonly held to, so the collar-to-block air does not
rest on an unpublished figure.

Frame (the part's, as the replica builds it): collar axis +Y, south face at
y = 0, north face at y = WIDTH; the set screw along +X at mid-width, which the
assembly lays on the shaft's +X D-flat.
"""

from __future__ import annotations

IN = 25.4

SKU = "9414T1"
BORE_DIA = IN / 16.0  # 1.5875
OUTER_DIA = IN / 4.0  # 6.35
WIDTH = 3.0 * IN / 16.0  # 4.7625
WIDTH_BAND_MM = 0.010 * IN  # assumed; see the module docstring
EDGE_BREAK = 0.009375 * IN  # 45 deg, OD and bore edges, both faces
SET_SCREW_THREAD = "#2-56"
SET_SCREW_MAJOR_DIA = 0.086 * IN
SET_SCREW_CUP_RADIUS = 0.03625 * IN  # cup rim from the collar axis, as supplied
SET_SCREW_END_RADIUS = 0.15625 * IN  # socket end, from the collar axis
SET_SCREW_END_CHAMFER = (0.043 - 0.038) * IN  # 45 deg on the socket end
SET_SCREW_SOCKET_AF = 0.050 * IN
SET_SCREW_SOCKET_DEPTH = (0.15625 - 0.109375) * IN

if not BORE_DIA / 2.0 < SET_SCREW_CUP_RADIUS < OUTER_DIA / 2.0 < SET_SCREW_END_RADIUS:
    raise AssertionError("9414T1 set screw is not seated in the collar wall as supplied")
if SET_SCREW_MAJOR_DIA >= WIDTH - 2.0 * EDGE_BREAK:
    raise AssertionError("9414T1 set-screw hole breaks out of the collar faces")
