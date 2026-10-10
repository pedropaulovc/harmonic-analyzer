r"""Pure-data contract shared by the nameplate, its base seats and the frame.

PURE DATA, no SolidWorks/COM imports. Three scripts read it and none may import the
others:

* ``build_fr_nameplate`` -- the plate envelope and its four corner screw stations
  (``SCREW_XY``, plate-local mm);
* ``build_fr_harmonic_base`` -- the SAME stations transformed into the machine
  frame (``MOUNT_HOLE_XZ``), where it taps the four blind #4-40 seats the
  plate's screws thread into. It must NOT import ``build_fr_nameplate``:
  ``_buildgraph.module_deps_of`` follows sibling ``build_*.py`` imports, so
  the base (the root of every assembly) would rebuild on each engraving edit;
* ``build_fr_frame_assembly`` -- the mount transform (``MOUNT_POS`` /
  ``MOUNT_EULER`` / ``MOUNT_ROWS``, formerly its own ``NAMEPLATE_*``) and the
  screw stations it drops the four ``vn-fillister-screw`` components onto.

Mount transform (user ruling 2026-10-09; ch. 26 p.71 and ch. 30 p002/p003/p006):
the brass plate's outline IS the traced DXF outer edge, uniformly enlarged to
100 mm wide (height about 45.33 mm). It lies FLAT on the WEST (+X) end of the
black base deck, decorated side up, read by an operator standing west of it.

The part's decorated face is its FRONT face (+Z local; ``build_fr_nameplate``
extrudes the body in -Z so the engraving is frontmost and reads with no
mirror). ``MOUNT_ROWS`` (euler [-90, 90, 0]) lays it flat on the WEST end:
local +Z (decorated front) -> +Y so the engraving faces up; local +Y (text
height) -> -X so the text top faces the machine interior and reads upright to
a west operator; local +X (text length, 100) -> -Z so the line runs
front-back; the 1.5 body (local -Z) drops onto the deck. The placed point is
the part origin CORNER (decorated face, x=0/y=0): Y 52.3 lays the decorated
face on top with the 1.5 body resting on the deck (50.8); Z 50 centres the
100 mm line at z 0; X 163.0 sets the plate's west edge 4.0 inside the black
deck's west edge at x 167.0. The plate spans x about 117.67..163.0, clear of
the rocker-arm-support foot at x 41.15..104.65.

Row convention (``_transforms.rows_from_euler`` / ``assert_component_placed``):
``MOUNT_ROWS[i]`` is the machine image of local axis ``i``, so a plate-local
point ``p`` lands at ``MOUNT_POS + sum(p[i] * MOUNT_ROWS[i])``. ``build_fr_frame_assembly``
asserts the literal rows against ``rows_from_euler(MOUNT_EULER)`` at import.
"""

from __future__ import annotations

# --- Photo-traced DXF measurements BEFORE the 2026-10-09 rebake (mm). ---
# The brief's 39.892 was rounded; preserve the measured outer-loop height and
# uniformly scale every contour. These data need no DXF/CAD dependency at import.
DXF_OUTER_ORIGIN = (5.999999999999993, 7.5538435420827525)
DXF_OUTER_WIDTH = 88.0
DXF_OUTER_HEIGHT = 39.8923129158345
DXF_SCALE = 100.0 / DXF_OUTER_WIDTH
DXF_SCREW_XY = (
    (9.566587580494442, 11.120346180985667),
    (90.43341063179248, 11.120530788933703),
    (9.566585942787817, 43.87947345273603),
    (90.43340909641734, 43.879661102671),
)

# --- Plate envelope (build_fr_nameplate owns the rest of the plate geometry). ---
PLATE_WIDTH = DXF_OUTER_WIDTH * DXF_SCALE
PLATE_HEIGHT = DXF_OUTER_HEIGHT * DXF_SCALE
PLATE_THICKNESS = 1.5  # thin brass plate; p.71 edge read (low)

# Four slotted screw-head marks in the traced DXF, measured at each mark's
# combined contour bbox centre. Preserve their slight asymmetry rather than a
# single nominal inset: each #4 CLOSE hole coincides with its traced head mark.
# The raised border's notches keep the heads off the recessed field.
SCREW_XY = tuple(
    ((x - DXF_OUTER_ORIGIN[0]) * DXF_SCALE, (y - DXF_OUTER_ORIGIN[1]) * DXF_SCALE)
    for x, y in DXF_SCREW_XY
)

# --- Mount transform in the machine frame (see the module docstring). ---
MOUNT_POS = [163.0, 52.3, 50.0]
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
# The four screw axes in the machine frame -- the plate-local DXF marks mapped
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
