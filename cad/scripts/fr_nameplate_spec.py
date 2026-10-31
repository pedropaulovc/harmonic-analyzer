r"""Pure-data contract shared by the nameplate, its base seats and the frame.

PURE DATA, no SolidWorks/COM imports. Three scripts read it and none may import the
others:

* ``build_fr_nameplate`` -- the plate envelope and its four corner screw stations
  (``SCREW_XY``, plate-local mm);
* ``build_fr_harmonic_base`` -- the SAME stations transformed into the machine
  frame (``MOUNT_HOLE_XZ``), where it through-taps four #4-40 seats the
  plate's screws thread into. It must NOT import ``build_fr_nameplate``:
  ``_buildgraph.module_deps_of`` follows sibling ``build_*.py`` imports, so
  the base (the root of every assembly) would rebuild on each engraving edit;
* ``build_fr_frame_assembly`` -- the mount transform (``MOUNT_POS`` /
  ``MOUNT_EULER`` / ``MOUNT_ROWS``, formerly its own ``NAMEPLATE_*``) and the
  screw stations it drops the four ``sh-vn-brass-fillister-screw`` components onto.

Mount transform (user ruling 2026-10-09; ch. 26 p.71 and ch. 30 p002/p003/p006):
the brass plate's outline IS the traced DXF outer edge, scaled to the
3.938 x 1.785 in envelope (the #290 inch rebake). It lies FLAT on the WEST
(+X) end of the black base deck, decorated side up, read by an operator
standing west of it.

The part's decorated face is its FRONT face (+Z local; ``build_fr_nameplate``
extrudes the body in -Z so the engraving is frontmost and reads with no
mirror). ``MOUNT_ROWS`` (euler [-90, 90, 0]) lays it flat on the WEST end:
local +Z (decorated front) -> +Y so the engraving faces up; local +Y (text
height) -> -X so the text top faces the machine interior and reads upright to
a west operator; local +X (text length, 3.938) -> -Z so the line runs
front-back; the .063 body (local -Z) drops onto the deck. The placed point is
the part origin CORNER (decorated face, x=0/y=0): Y 2.063 lays the decorated
face on top with the .063 body resting on the deck (2.000); Z 1.969 centres
the 3.938 line at z 0; X 6.42 sets the plate's west edge .16 inside the black
deck's west edge at x 6.58. The plate spans x 4.635..6.42, clear of the
rocker-arm-support foot.

Row convention (``_transforms.rows_from_euler`` / ``assert_component_placed``):
``MOUNT_ROWS[i]`` is the machine image of local axis ``i``, so a plate-local
point ``p`` lands at ``MOUNT_POS + sum(p[i] * MOUNT_ROWS[i])``. ``build_fr_frame_assembly``
asserts the literal rows against ``rows_from_euler(MOUNT_EULER)`` at import.
"""

from __future__ import annotations

import _config
import sh_vn_brass_fillister_screw_spec as _screw
from _package_units import drawing_unit
from _printed_tolerance import printed_deviations

# The sheet prints decimal inch (issue #290, ``drawing_unit: in``).
UNIT = drawing_unit("parts/fr-nameplate", _config.parts("fr-nameplate"))

# --- Photo-traced DXF measurements BEFORE the 2026-10-09 rebake (mm). ---
# The brief's 39.892 was rounded; preserve the measured outer-loop height.
# These data need no DXF/CAD dependency at import.
DXF_OUTER_ORIGIN = (5.999999999999993, 7.5538435420827525)
DXF_OUTER_WIDTH = 88.0
DXF_OUTER_HEIGHT = 39.8923129158345
DXF_SCREW_XY = (
    (9.566587580494442, 11.120346180985667),
    (90.43341063179248, 11.120530788933703),
    (9.566585942787817, 43.87947345273603),
    (90.43340909641734, 43.879661102671),
)

# --- Plate envelope (build_fr_nameplate owns the rest of the plate geometry). ---
# The #290 rebake scales the traced artwork to an envelope exact on the .001
# grid. No uniform scale lands both sides on it, so each axis takes its own
# scale; they differ by 0.01 %, invisible in the traced art.
PLATE_WIDTH = 100.0252  # 3.938
PLATE_HEIGHT = 45.339  # 1.785
DXF_SCALE_X = PLATE_WIDTH / DXF_OUTER_WIDTH
DXF_SCALE_Y = PLATE_HEIGHT / DXF_OUTER_HEIGHT
PLATE_THICKNESS = 1.6002  # .063 C260 sheet (OnlineMetals 23624)
PLATE_THICKNESS_PRECISION = 3

# Shared mechanical installation limits, formerly drawing-only. RV-03 in the
# nameplate registry preserves the original cosmetic-joint shortfall: these
# bounds describe the stock screw projecting through the plate, not a newly
# qualified supplier profile or a new 1.5D claim for the through-tap conversion.
SCREW_LENGTH_SHORT_ALLOWANCE = 0.02 * 25.4
SCREW_TIP_INCOMPLETE = 0.75 * _screw.BF_PITCH
SCREW_ENGAGEMENT_TARGET = 1.5 * _screw.SHANK_DIA
SCREW_FULL_THREAD_MIN = (
    _screw.SHANK_LEN
    - SCREW_LENGTH_SHORT_ALLOWANCE
    - (
        PLATE_THICKNESS
        + printed_deviations(PLATE_THICKNESS, PLATE_THICKNESS_PRECISION, unit=UNIT)[1]
    )
    - SCREW_TIP_INCOMPLETE
)
# RV-03: .143 MIN (1.28D), below the 1.31D accepted for the former 1.5 mm plate.
SCREW_FULL_THREAD_ACCEPTED = 3.6322  # .143
if not (
    0.0
    < SCREW_FULL_THREAD_ACCEPTED
    <= round(SCREW_FULL_THREAD_MIN, 3)
    < SCREW_ENGAGEMENT_TARGET
):
    raise AssertionError(
        f"nameplate screw full thread {SCREW_FULL_THREAD_MIN:.3f} is not the "
        f"accepted rule-20 shortfall [{SCREW_FULL_THREAD_ACCEPTED}, "
        f"{SCREW_ENGAGEMENT_TARGET:.3f})"
    )

# Four slotted screw-head marks in the traced DXF, measured at each mark's
# combined contour bbox centre. The raised border's notches keep the heads
# off the recessed field.
HEAD_MARK_XY = tuple(
    ((x - DXF_OUTER_ORIGIN[0]) * DXF_SCALE_X, (y - DXF_OUTER_ORIGIN[1]) * DXF_SCALE_Y)
    for x, y in DXF_SCREW_XY
)
# Owner ruling 2026-10-15: nameplate holes and frame taps sit inboard of the
# engraved head marks for corner ligament (PR #1468 r3 review), each hole
# concentric with the outline's rounded corner. Every station prints .164
# from its two edges, about .004 inboard of the traced marks in x and y:
# drilled at both printed station minima (.159) the hole keeps its wall to
# the corner arc (fr_nameplate_drawing_spec.HOLE_LIGAMENT_WORST measures it
# on the DXF), and the heads still cover the engraved marks. The base's
# through seats derive from these stations through MOUNT_HOLE_XZ.
SCREW_STATION = 4.1656  # .164
SCREW_XY = (
    (SCREW_STATION, SCREW_STATION),
    (PLATE_WIDTH - SCREW_STATION, SCREW_STATION),
    (SCREW_STATION, PLATE_HEIGHT - SCREW_STATION),
    (PLATE_WIDTH - SCREW_STATION, PLATE_HEIGHT - SCREW_STATION),
)

# --- Mount transform in the machine frame (see the module docstring). ---
MOUNT_POS = [163.068, 52.4002, 50.0126]  # 6.42, 2.063, 1.969
MOUNT_EULER = [-90.0, 90.0, 0.0]
MOUNT_ROWS = [[0.0, 0.0, -1.0], [-1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]


def mount_point(local_xyz: tuple[float, float, float]) -> tuple[float, float, float]:
    """Machine coordinates of a plate-local point under the mount transform."""
    return tuple(
        MOUNT_POS[k] + sum(local_xyz[i] * MOUNT_ROWS[i][k] for i in range(3))
        for k in range(3)
    )


# The decorated (front) face's outward normal, local +Z, in the machine frame:
# +Y (face up). The BACK face therefore looks -Y onto the deck.
MOUNT_NORMAL = tuple(MOUNT_ROWS[2])
# Machine y of the decorated front face (the screw heads seat on it) and of the
# back face (the deck it rests on) -- both faces are flat at one y because the
# plate lies horizontal (MOUNT_NORMAL is +Y).
MOUNT_FRONT_Y = MOUNT_POS[1]
MOUNT_BACK_Y = mount_point((0.0, 0.0, -PLATE_THICKNESS))[1]  # 50.8
# The four screw axes in the machine frame -- the plate-local stations mapped
# through the mount rows (x = MOUNT_POS[0] - y_local, z = MOUNT_POS[2] - x_local).
# These are the base's tapped-seat stations; each axis runs along -Y into the deck.
MOUNT_HOLE_XZ = tuple(
    (pt[0], pt[2]) for pt in (mount_point((x, y, 0.0)) for x, y in SCREW_XY)
)

if MOUNT_NORMAL != (0.0, 1.0, 0.0):
    raise AssertionError(f"nameplate does not lie flat face-up: normal {MOUNT_NORMAL}")
if any(abs(mount_point((x, y, 0.0))[1] - MOUNT_FRONT_Y) > 1e-12 for x, y in SCREW_XY):
    raise AssertionError(
        "nameplate screw stations are not coplanar with the front face"
    )
