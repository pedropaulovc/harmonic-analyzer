"""The cone tip cluster: T024..T006, the T006 part's spigot and pivot, the brass
bushing and the end screw (owner decision C1 keyed, 2026-11-09, PR #1992).

Research: ``research/3-detailed-design/drive-train-cone-tip-options.md``
(option C1 keyed).  South to north along MHA-DT-04, ``|`` a contact face and
``=`` a LOCTITE 638 bonded slip fit::

    DT-05 boss | DT-04 collar | 64T | T120 .. T030 | T024 = DT-04
    | T018 = T012 = spigot = DT-04 | bushing | end screw | DT-21

* T024 (MHA-DT-03) is reamed round on MHA-DT-04's round Ø.250 land 2 and
  bonded there at a station set with one STACK_FEELER leaf off T030's north
  face: it replaces the MHA-DT-VN-54 collar as the stack's north stop, so the
  64T and T030..T120 float between DT-04's thrust collar and T024
  (cone_stack_end_play.STACK_FLOAT).
* MHA-DT-04 ends TIP_END_RECESS_MM inside T024's bore, so T018's south face
  always butts T024's north face whatever the stack and feeler set (the
  shaft spec proves the recess positive at every limit).  A reamed socket in
  that end takes T006's spigot.
* T006 (its own part) carries an integral Ø.0625 spigot running south through
  T012 and T018 (each reamed Ø.0625 and bonded on it) into the socket, where
  it is bonded too, and an integral Ø.0625 pivot running north.  Spigot and
  pivot sit .0108 under T006's root, so the DT6-FORM1 fly cutter runs off.
* The brass bushing is pressed on the pivot against T006's north face; its
  north face bears on the end of the end screw (McMaster 91794A558, 1/4-28 x
  5/8 slotted fillister, with a reamed hole for the pivot in its threaded
  end), which threads through MHA-DT-21 and is locked by its pinch slit.
  The end screw sets the shaft's end play (cone_stack_end_play.SHAFT_END_PLAY).

The tip cluster's model stations: T024, T018, T012, T006, the bushing and
the end screw sit TIP_SET_SHIFT_MM north of their cone_line layout stations
(the stack is modelled pushed onto the collar, T024 one feeler off T030), the
same place the in-service float envelope CONE_FLOAT_NORTH already proves
against the meshes.  MHA-DT-21 does not shift with them: dt_cone_tip_block_spec
places it (about .27-.30 north of cone_line.T006_NORTH_FACE, the research's
block_air.py definition, centred on the end screw's engagement window).

Pure data, import-light: the gear, shaft, tip-part and assembly specs all
read these numbers.  Lengths in mm; (upper, lower) bands.
"""

from __future__ import annotations

from _fit_ream_h7 import REAM_H7
from cone_stack_end_play import STACK_FEELER

MM_PER_IN = 25.4

# LOCTITE 638 retaining compound: the bonded slip fits (drawing-guidelines.md
# rule 23 counts a bonded slip fit as a fit).  The pattern of
# dt_alignment_pinion_spec: grade named by number, every bonded diametral
# clearance inside its largest gap.
RETAINING_COMPOUND = "LOCTITE 638"
RETAINING_COMPOUND_MAX_GAP_MM = 0.25

# T024..T006, DT-04's end, the socket, the bushing and the end screw sit this
# far north of their cone_line layout stations.
TIP_SET_SHIFT_MM = STACK_FEELER

# Ø.0625 stem stock: T006's spigot and pivot, T018/T012 bores, the socket.
STEM_DIA_MM = 1.5875  # .0625
# The spigot is turned between centres (L/D 12) and bonded: +.0000/-.0010.
SPIGOT_DIA_BAND = (0.0, -0.0254)
# The pivot carries the bushing's press and runs in the end screw's hole:
# +.0000/-.0003.
PIVOT_DIA_BAND = (0.0, -0.00762)
# Reamed on size with an owned chucking reamer: T018 and T012 bores, the
# DT-04 socket.
STEM_BORE_DIA_MM = STEM_DIA_MM
STEM_BORE_BAND = REAM_H7  # +.0005/-.0000
STEM_PLACES = 4

# T006's spigot length from its leaves' south face, and the socket's reamed
# depth from DT-04's end; .XX.  Research: spigot .73, socket .19.  At the
# limits (.XX lengths, two face widths, the end recess's range) the spigot
# must keep air at the socket floor and at least 1.5 D in the socket.  At the
# .300 in pitch (#1038) the spigot crosses two 7.4528 faces.  With the faces
# at +/-.001 and the .025 recess, .74 to .76 do both (engagement 2.384 to
# 2.892, floor air 0.674 to 0.166; the shaft spec proves the chosen one); with
# the +/-.002 faces and .030 recess of #2314 only .76 does (2.587 and 0.115:
# .75 falls to 2.333, under 1.5 D, and .77 bottoms).  .76 holds in both, so
# the length does not move with the bands.
SPIGOT_LENGTH_MM = 19.304  # .76
SOCKET_DEPTH_MM = 5.08  # .20
SPIGOT_SOCKET_ENGAGEMENT_MIN_MM = 1.5 * STEM_DIA_MM

# DT-04's end stands this far inside T024's bore (nominal, .XXX); the shaft
# spec proves it positive at every limit of T024's feeler-set station and the
# printed land-2 end.
TIP_END_RECESS_MM = 0.635  # .025

# T006's pivot length from its leaves' north face, .XX: through the bushing
# and into the end screw's hole, never bottoming there.
PIVOT_LENGTH_MM = 6.35  # .25

# Brass bushing (C36000), pressed on the pivot against T006's north face.
# Research: Ø.225; at the title block's .XXX that leaves a .079 wall over the
# reamed bore, under rule 17's .080 target, so the OD is .228.
BUSHING_OD_MM = 5.7912  # .228, .XXX
BUSHING_LENGTH_MM = 4.064  # .160, .XXX
BUSHING_BORE_DIA_MM = 1.5621  # .0615 reamer
BUSHING_BORE_BAND = REAM_H7
BUSHING_PLACES = 3

# The end screw's added operation: drill and ream Ø.0630 x .12 for the pivot.
END_SCREW_SKU = "91794A558"
END_HOLE_DIA_MM = 1.6002  # .0630 reamer
END_HOLE_BAND = REAM_H7
END_HOLE_DEPTH_MM = 3.048  # .12, .XX

# MHA-DT-21: BLOCK_DEPTH_MM deep for the end screw's thread; its stations
# belong to dt_cone_tip_block_spec.
BLOCK_DEPTH_MM = 10.922  # .430
ADJUSTER_THREAD = "1/4-28"


def limits(nominal_mm: float, band: tuple[float, float]) -> tuple[float, float]:
    """(minimum, maximum) of ``nominal_mm`` under an (upper, lower) band."""
    return nominal_mm + band[1], nominal_mm + band[0]


def diametral_clearance_mm(
    bore: tuple[float, tuple[float, float]], shaft: tuple[float, tuple[float, float]]
) -> tuple[float, float]:
    """(minimum, maximum) diametral clearance of a (nominal, band) bore over a
    (nominal, band) shaft; negative is interference."""
    bore_min, bore_max = limits(*bore)
    shaft_min, shaft_max = limits(*shaft)
    return bore_min - shaft_max, bore_max - shaft_min


SPIGOT = (STEM_DIA_MM, SPIGOT_DIA_BAND)
PIVOT = (STEM_DIA_MM, PIVOT_DIA_BAND)
STEM_BORE = (STEM_BORE_DIA_MM, STEM_BORE_BAND)
BUSHING_BORE = (BUSHING_BORE_DIA_MM, BUSHING_BORE_BAND)
END_HOLE = (END_HOLE_DIA_MM, END_HOLE_BAND)

# Bonded slip fits: never interference, never past 638's largest gap.
SPIGOT_BOND_CLEARANCE_MM = diametral_clearance_mm(STEM_BORE, SPIGOT)
if (
    not 0.0
    <= SPIGOT_BOND_CLEARANCE_MM[0]
    <= SPIGOT_BOND_CLEARANCE_MM[1]
    <= (RETAINING_COMPOUND_MAX_GAP_MM)
):
    raise AssertionError(f"spigot bond clearance {SPIGOT_BOND_CLEARANCE_MM} mm")
# The bushing's press on the pivot: interference at every limit.
BUSHING_PRESS_INTERFERENCE_MM = tuple(
    -c for c in reversed(diametral_clearance_mm(BUSHING_BORE, PIVOT))
)
if BUSHING_PRESS_INTERFERENCE_MM[0] <= 0.0:
    raise AssertionError(
        f"bushing press interference {BUSHING_PRESS_INTERFERENCE_MM} mm"
    )
# The pivot runs in the end screw's reamed hole.
PIVOT_RUNNING_CLEARANCE_MM = diametral_clearance_mm(END_HOLE, PIVOT)
if PIVOT_RUNNING_CLEARANCE_MM[0] <= 0.0:
    raise AssertionError(f"pivot running clearance {PIVOT_RUNNING_CLEARANCE_MM} mm")
# The bushing's wall over its bore at the title block's .XXX: rule 17's
# .080 target.
BUSHING_WALL_MIN_MM = (BUSHING_OD_MM - 0.127 - limits(*BUSHING_BORE)[1]) / 2.0
if BUSHING_WALL_MIN_MM < 2.032:
    raise AssertionError(f"bushing wall {BUSHING_WALL_MIN_MM:.4f} mm under .080")
