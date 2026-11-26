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
* The brass bushing is bonded (LOCTITE 638) on the pivot against T006's
  north face (owner ruling 2026-11-20, #2469: a bonded slip fit on the shared
  .0625 reamer, not a press); its north face bears on the end of the end
  screw (McMaster 91794A559, 1/4-28 x 3/4 slotted fillister, owner ruling
  2026-11-20, #2726, with a drilled hole for the pivot in its threaded end),
  which threads through MHA-DT-21 and is locked by its pinch slit.
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
# The spigot is turned between centres (L/D 12) and bonded: -.0003/-.0013,
# the turned-diameter row's .0010 width held .0003 under the reamed bores'
# low limit so the bond is never line to line, where the compound is wiped
# off and T012/T018 may not slide on by hand (#2530).  Its .0018 bond
# maximum is what keeps T012, read on its own part with MHA-DT-37 tilted in
# a true socket, at the cone set's contact-ratio floor: .0019 falls under
# (test_standard_mesh_checks.SPIGOT_OWN_PART_CONTACT_RATIO_MIN; the after-cure
# T012/T018 reading is a record only, owner ruling 2026-11-24 C5).
# MHA-DT-37 prints the band, read with the micrometer (necessity N-04).
SPIGOT_DIA_BAND = (-0.00762, -0.03302)
# The pivot is bonded in the bushing and runs in the end screw's hole: the
# spigot's band (one stem stock, one turned-diameter row; #2469), printed
# (D50, delegated ruling 2026-11-26 (Main), precedent: the band main printed
# until f4ba380152; owner form timed out; owner review #2144); looser closes
# the tip air (necessity N-03).
PIVOT_DIA_BAND = SPIGOT_DIA_BAND
# Reamed on size with an owned chucking reamer: T018 and T012 bores, the
# DT-04 socket.
STEM_BORE_DIA_MM = STEM_DIA_MM
STEM_BORE_BAND = REAM_H7  # +.0005/-.0000
STEM_PLACES = 4

# T006's spigot length from its leaves' south face, and the socket's reamed
# depth from DT-04's end; .XX.  Research: spigot .73, socket .19.  At the
# limits (.XX lengths, two face widths, the end recess's range) the spigot
# must keep air at the socket floor and at least 1.5 D in the socket.  At the
# .300 in pitch (#1038) the spigot crosses two 7.4528 faces.  With their
# +/-.002 band and the .030 recess (#2314) one .XX length does both with the
# .20 socket: .76 (engagement 2.587, floor air 0.115; the shaft spec proves
# it).  .75 falls to 2.333, under 1.5 D, and .77 bottoms.  .76 also held on
# the +/-.001 faces and .025 recess it was first chosen on (2.892, 0.166).
SPIGOT_LENGTH_MM = 19.304  # .76
SOCKET_DEPTH_MM = 5.08  # .20
SPIGOT_SOCKET_ENGAGEMENT_MIN_MM = 1.5 * STEM_DIA_MM

# DT-04's end stands this far inside T024's bore (nominal, .XXX); the shaft
# spec proves it positive at every limit of T024's feeler-set station (the
# cone gears' +/-.002 faces, #2314) and the printed land-2 end.
TIP_END_RECESS_MM = 0.762  # .030

# T006's pivot length from its leaves' north face, .XX: through the bushing
# and into the end screw's hole, never bottoming there.
PIVOT_LENGTH_MM = 6.35  # .25

# Brass bushing (C36000), bonded on the pivot against T006's north face.
# Research: Ø.225; at the title block's .XXX that leaves a .079 wall over the
# reamed bore, under rule 17's .080 target, so the OD is .228.  Its bore is
# reamed with the stems' .0625 reamer (#2469: a LOCTITE 638 bonded slip fit
# on the pivot, so no press force on the Ø1/16 stem and no .0615 reamer).
BUSHING_OD_MM = 5.7912  # .228, .XXX
BUSHING_LENGTH_MM = 4.064  # .160, .XXX
BUSHING_BORE_DIA_MM = STEM_BORE_DIA_MM  # .0625 reamer
BUSHING_BORE_BAND = STEM_BORE_BAND
BUSHING_PLACES = 3

# The end screw's added operation: drill #52 x .12 for the pivot (owner
# ruling 2026-11-24, fit audit question 11; was a .0630 reamer and its ZZ
# pins).  The DRILLED HOLES row's +.004/0 is its ANALYSIS band: the pivot
# runs free in it and the tip air to gear 19 takes its float.  Owner ruling
# 2026-11-20 (#2726): the 3/4 screw, so the thread keeps 1.5 D over the
# whole embed stack with the block's stations at .XX.
END_SCREW_SKU = "91794A559"
END_HOLE_DRILL = "#52"
END_HOLE_DIA_MM = 1.6129  # .0635, #52
END_HOLE_BAND = (0.1016, 0.0)  # +.004/-.000, title block DRILLED HOLES
END_HOLE_DEPTH_MM = 3.048  # .12, .XX

# MHA-DT-21: BLOCK_DEPTH_MM deep for the end screw's thread; its stations
# belong to dt_cone_tip_block_spec.  .44 (#2726): its half, the foot tap's
# station, stands on the .01 grid.
BLOCK_DEPTH_MM = 11.176  # .440
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


def _require_bond(name: str, clearance_mm: tuple[float, float]) -> None:
    """A bonded slip fit: clearance at every limit (a line-to-line pair wipes
    the compound, #2530), never past 638's largest gap."""
    if not 0.0 < clearance_mm[0] <= clearance_mm[1] <= RETAINING_COMPOUND_MAX_GAP_MM:
        raise AssertionError(f"{name} bond clearance {clearance_mm} mm")


SPIGOT_BOND_CLEARANCE_MM = diametral_clearance_mm(STEM_BORE, SPIGOT)
_require_bond("spigot", SPIGOT_BOND_CLEARANCE_MM)
# The bushing's bond on the pivot (#2469).
BUSHING_BOND_CLEARANCE_MM = diametral_clearance_mm(BUSHING_BORE, PIVOT)
_require_bond("bushing", BUSHING_BOND_CLEARANCE_MM)
# The pivot runs in the end screw's drilled hole.
PIVOT_RUNNING_CLEARANCE_MM = diametral_clearance_mm(END_HOLE, PIVOT)
if PIVOT_RUNNING_CLEARANCE_MM[0] <= 0.0:
    raise AssertionError(f"pivot running clearance {PIVOT_RUNNING_CLEARANCE_MM} mm")
# The bushing's wall over its bore at the title block's .XXX: rule 17's
# .080 target.
BUSHING_WALL_MIN_MM = (BUSHING_OD_MM - 0.127 - limits(*BUSHING_BORE)[1]) / 2.0
if BUSHING_WALL_MIN_MM < 2.032:
    raise AssertionError(f"bushing wall {BUSHING_WALL_MIN_MM:.4f} mm under .080")
