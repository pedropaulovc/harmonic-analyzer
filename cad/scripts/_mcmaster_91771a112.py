r"""Pure 91771A112 Phillips flat head screw dimensions; isolate this SKU's cache inputs.

Catalogue: McMaster 91771A112, 18-8 stainless steel Phillips flat head screw,
82 deg countersink, standard flat head profile, #4-40 UNC class 2A, 5/8 in
long ("Length is measured from the top of the head"), fully threaded, head
Ø0.212 x 0.067 in, Phillips No. 1 drive, flat tip, Rockwell B80, 80,000 psi,
passivated, ASME B18.6.3 (https://www.mcmaster.com/91771A112/, read live
2026-10-19; $7.44 per pack of 100).  ``DIMS`` takes the thread (#4: 0.112 in
major, 40 TPI), the overall length, the head diameter, the 82 deg angle and
the head height (where the thread ends) from that table.  Class 2A is not
modelled (nominal UN cutter).  The catalogue states no head-angle or
head-diameter tolerance.

Where the catalogue is silent -- the Phillips No. 1 recess form, the tip
chamfer -- the values are the same-family reading of McMaster's 1/2 in
91771A110 vendor model (its STEP
``91771A110_Passivated 18-8 Stainless Steel Phillips Flat Head Screw.STEP``,
AP203, SHA-256
``588000b51c99935744bdd79b93fb8269cb27932f2e6086338d23bf51f9269a27``, and
SLDPRT, SHA-256
``170dc7d8be906f2614181b0cac013ec2542eb37e93de45b40885ff555ae5f6ab``,
downloaded 2026-10-17 and read in headless FreeCAD 1.1), each labelled
"vendor model" below.  Both SKUs carry the same catalogue head, drive and
thread; only the length differs.  The 91771A112 model itself was not
downloaded or measured.  These forms are read for dimensions only, NOT
replica-gated (user ruling 2026-10-17), and no vendor file is kept in the
repo.  The 91771A110 reading (vendor frame: axis Z, head +z, origin at the
thread top 0.067 in below the flat top):

* head: the flat top Ø5.3848 (the catalogue's 0.212 in), sharp, then the
  41 deg (to the axis) cone to the major Ø2.8448, 1.460968 below the top;
* thread: the family cutter (root R1.009955), cut on the shank only and
  ending flat 1.7018 (the catalogue's 0.067 in head height) below the top; no
  runout; tip chamfer 45 deg from R0.92075 at the tip flat (radial 0.50165);
* Phillips No. 1 recess: walls at 5 deg to the axis; wings 2 x 0.3556
  (0.014 in) off their centre lines at the top; between adjacent wings a V
  notch of two planes 0.732384 from the axis at the top (normals 22.5 deg off
  the wings); a vertical entry cylinder R1.7907 (0.0705 in) down to 0.121008
  below the top, then a 41 deg (to the axis) cone with its apex 2.180973
  below the top.
"""

from __future__ import annotations

import math

from _phillips_flat_head_dimensions import PhillipsFlatHeadScrew

IN = 25.4
PART_NO = "91771A112"
# The catalogue's designation, as the C4 fastener table prints it.
THREAD = "#4-40"
LENGTH_TEXT = "5/8"
_HEAD_H = 0.067 * IN  # catalogue head height
_RECESS_DRAFT_DEG = 5.0  # vendor model: the recess walls to the axis
_DRAFT = math.radians(_RECESS_DRAFT_DEG)

DIMS = PhillipsFlatHeadScrew(
    part_no=PART_NO,
    major_dia=0.112 * IN,  # catalogue: #4
    pitch=IN / 40.0,  # catalogue: 40 TPI
    length=0.625 * IN,  # catalogue: overall, top to tip
    head_dia=0.212 * IN,  # catalogue
    head_angle_deg=82.0,  # catalogue
    thread_top_depth=_HEAD_H,  # catalogue head height: the thread ends there
    tip_chamfer=0.112 * IN / 2.0 - 0.92075,  # vendor model: the R0.92075 tip flat
    wing_half_width=0.014 * IN,  # vendor model
    # Vendor model: the V-notch planes sit 0.581275895 off the axis along
    # their (5 deg tilted) normals at the thread top.
    web_distance=(0.581275895 + math.sin(_DRAFT) * _HEAD_H) / math.cos(_DRAFT),
    recess_draft_deg=_RECESS_DRAFT_DEG,
    entry_r=0.0705 * IN,  # vendor model
    recess_cone_semi_deg=41.0,  # vendor model
    recess_depth=_HEAD_H + 0.479172561,  # vendor model: the cone apex
)
