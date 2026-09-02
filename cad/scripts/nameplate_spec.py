r"""Pure-data contract shared by the nameplate, its base seats and the frame.

PURE DATA, no SolidWorks/COM imports (the ``harmonic_base_spec`` /
``fillister_screw_spec`` split). Three scripts read it and none may import the
others:

* ``build_nameplate`` -- the plate envelope and its four corner screw stations
  (``SCREW_XY``, plate-local mm);
* ``build_harmonic_base`` -- the SAME stations transformed into the machine
  frame (``MOUNT_HOLE_XZ``), where it taps the four blind #4-40 seats the
  plate's screws thread into. It must NOT import ``build_nameplate``:
  ``_buildgraph.module_deps_of`` follows sibling ``build_*.py`` imports, so
  the base (the root of every assembly) would rebuild on each engraving edit;
* ``build_frame_assembly`` -- the mount transform (``MOUNT_POS`` /
  ``MOUNT_EULER`` / ``MOUNT_ROWS``, formerly its own ``NAMEPLATE_*``) and the
  screw stations it drops the four ``fillister-screw`` components onto.

Mount transform (book ch. 26 pp. 70-71; photogrammetry 195527397 / 195530756 /
195532820; ch. 30 eight views): the 100 x 55 brass plate lies FLAT on the base
deck, decorated side up, on the EAST (+X) face, centred front-back between the
two east columns and read by an operator standing at that face.

The part's decorated face is its FRONT face (+Z local; ``build_nameplate``
extrudes the body in -Z so the engraving is frontmost and reads with no
mirror). ``MOUNT_ROWS`` (euler [-90, 90, 0]) lays it flat on the EAST face:
local +Z (decorated front) -> +Y so the engraving faces up; local +Y (text
height) -> -X so the text top faces the machine interior and reads upright to
an east operator; local +X (text length, 100) -> -Z so the line runs
front-back; the 1.5 body (local -Z) drops onto the deck. The placed point is
the part origin CORNER (decorated face, x=0/y=0): Y 52.3 lays the decorated
face on top with the 1.5 body resting on the deck (50.8); Z 50 centres the
100 mm line at z 0 between the east columns (z +/-112); X 214.25 sets the
plate's east edge 1.0 inside the raised rim's inner wall (pad edge 222.25
minus the 7.0 lip), span x 159.25..214.25 -- east of the rocker-arm-support
(x 28..117) and clear of the east columns.

Row convention (``_transforms.rows_from_euler`` / ``assert_component_placed``):
``MOUNT_ROWS[i]`` is the machine image of local axis ``i``, so a plate-local
point ``p`` lands at ``MOUNT_POS + sum(p[i] * MOUNT_ROWS[i])``. ``build_frame_assembly``
asserts the literal rows against ``rows_from_euler(MOUNT_EULER)`` at import.
"""

from __future__ import annotations

# --- Plate envelope (build_nameplate owns the rest of the plate geometry). ---
PLATE_WIDTH = 100.0  # DIMENSIONS.md ch26: stated 100 mm (p.70, high)
PLATE_HEIGHT = 55.0  # DIMENSIONS.md ch26: stated 55 mm (p.70, high)
PLATE_THICKNESS = 1.5  # thin brass plate; p.71 edge read (low)

# Four corner mounting screws (ch26 p.71 macro: one brass slotted round-head
# screw per corner, heads riding the pinstripe corners) in the raised border
# band. The screws are the shared #4-40 brass ``fillister-screw``; the plate
# carries #4 CLOSE clearance holes, the base the blind #4-40 taps.
SCREW_INSET = 4.5
SCREW_XY = (
    (SCREW_INSET, SCREW_INSET),
    (PLATE_WIDTH - SCREW_INSET, SCREW_INSET),
    (SCREW_INSET, PLATE_HEIGHT - SCREW_INSET),
    (PLATE_WIDTH - SCREW_INSET, PLATE_HEIGHT - SCREW_INSET),
)

# --- Mount transform in the machine frame (see the module docstring). ---
MOUNT_POS = [214.25, 52.3, 50.0]
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
# The four screw axes in the machine frame -- the plate-local corner stations
# mapped through the mount rows (x = 214.25 - y_local, z = 50 - x_local):
# (209.75, 45.5), (209.75, -45.5), (163.75, 45.5), (163.75, -45.5). These are
# the base's tapped-seat stations; each axis runs along -Y into the deck.
MOUNT_HOLE_XZ = tuple(
    (pt[0], pt[2]) for pt in (mount_point((x, y, 0.0)) for x, y in SCREW_XY)
)

if MOUNT_NORMAL != (0.0, 1.0, 0.0):
    raise AssertionError(f"nameplate does not lie flat face-up: normal {MOUNT_NORMAL}")
if any(abs(mount_point((x, y, 0.0))[1] - MOUNT_FRONT_Y) > 1e-12 for x, y in SCREW_XY):
    raise AssertionError("nameplate screw stations are not coplanar with the front face")
