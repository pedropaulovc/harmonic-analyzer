r"""Pure-data contract for MHA-CH-13-TL-VN-50, the strap sub-plate's edge clamp.

Shop tooling (owner, 2026-11-17): a Mitee-Bite Pitbull 26000 (tool steel,
knife edge) installed with the #4-40 x 3/8 socket head cap screw it is
supplied with, one installed part of two bodies, four per fixture. The
supplied O-ring (26008, under the body) is not modelled.

PURE DATA, no SolidWorks/COM calls: the recipe
(``diagnostics/diag_build_26000.py``), the drawing and the fixture assembly
read the clamp from here.

Sources:

- Geometry: Mitee-Bite's vendor model ``26000.STEP`` (bodies ``260001``,
  ``44038 SHCS``, ``004 O-RING``), probed headless with FreeCAD 1.1
  (``C:/src/ha-cnc-scratch/pitbull-step``, 2026-11-17); its numbers are the
  STEP-frame values quoted below, in mm.
- Catalogue: Mitee-Bite PITBULL-INST-0426 (miteebite.com, read 2026-11-17,
  SHA-256 12c839a3...b2d7ddb), row 26000: A .150, B .140, C .375, D* .075
  (minimum clamp height), E .260, F .375, 4-40 SHCS, torque not to exceed
  1.30 ft-lb, holding force 650 lb, total throw .0075, 8 per package,
  replacement O-ring 26008. The catalogue governs; the model is reference.

Part frame (fixture contract): the screw axis is part Z (+Z up), z = 0 the
clamp's lowest point (the heel line it rests on in the pocket floor), the
knife toward part +Y with its tip at y = +KNIFE_Y, the heel at y = HEEL_Y,
the body across x = +-WIDTH/2. From the STEP frame: part Y = -STEP x,
part Z = STEP y + Z_OFFSET, part X = -STEP z. (The contract writes X =
+STEP z; that mapping is a mirror, and the body is symmetric across its
width, so the proper rotation used here is the same solid.)

Modelled: the side profile (lines and arcs below) extruded across the
width; the slotted counterbore and the slotted through hole; the screw as a
second body, head seated on the counterbore floor, its shank a plain
cylinder at the thread major to its flat tip. Not modelled: the O-ring and
its recess under the body, the .005 edge breaks round the side faces, the
counterbore mouth's breaks and floor fillet, the screw's thread, tip cone and
socket entry countersink (``MODEL_VOLUME_SHORTFALL`` bounds what they cost).
"""

from __future__ import annotations

import math

INCH = 25.4
PART_NAME = "ch-rocker-strap-tl-vn-edge-clamp"
SKU = "26000"

# --- catalogue (PITBULL-INST-0426, row 26000), inches as printed ----------
CATALOG_SOURCE = (
    "https://www.miteebite.com/wp-content/uploads/2026/04/PITBULL-INST-0426.pdf "
    "(read 2026-11-17)"
)
CATALOG_A_IN = 0.150  # screw axis to the knife (drill/tap from the work edge)
CATALOG_B_IN = 0.140  # slot depth
CATALOG_C_IN = 0.375  # slot length: knife to heel
CATALOG_D_IN = 0.075  # D*: minimum clamp height
CATALOG_E_IN = (
    0.260  # recorded only; the instruction sheet does not tie it to a feature
)
CATALOG_F_IN = 0.375  # clamp width
MAX_TORQUE_FT_LB = 1.30
HOLDING_FORCE_LB = 650
THROW_IN = 0.0075
PER_PACKAGE = 8
O_RING_SKU = "26008"
SCREW_THREAD = "#4-40 UNC x 3/8"

# --- frame -------------------------------------------------------------------
Z_OFFSET = 4.078  # STEP y of the lowest point (heel circle), negated
KNIFE_Y = CATALOG_A_IN * INCH  # 3.810: the knife tip, from the screw axis
WIDTH = CATALOG_F_IN * INCH  # 9.525

# Heel cylinder: STEP r 1.524 about (4.19124, -2.553973), rounded to the
# inch grid (.165, -.1006) so its back line is exactly C from the knife and
# its lowest line exactly the frame's z = 0 (moves it 0.24 um).
HEEL_R = 1.524
HEEL_CENTER = (-4.191, -2.554 + Z_OFFSET)  # part (Y, Z) = (-4.191, 1.524)
HEEL_Y = HEEL_CENTER[0] - HEEL_R  # -5.715
HEEL_FACE_MID_Z = HEEL_CENTER[1]  # the heel's back-wall contact line, 1.524
if not math.isclose(KNIFE_Y - HEEL_Y, CATALOG_C_IN * INCH, abs_tol=1e-9):
    raise AssertionError("knife-to-heel is not catalogue C")
if not math.isclose(HEEL_CENTER[1] - HEEL_R, 0.0, abs_tol=1e-9):
    raise AssertionError("the heel is not the frame's z = 0")


def step_to_part(x: float, y: float) -> tuple[float, float]:
    """A STEP-frame profile point (x, y) as part (Y, Z)."""
    return -x, y + Z_OFFSET


def _on_circle(
    center: tuple[float, float], radius: float, toward: tuple[float, float]
) -> tuple[float, float]:
    """The point of the circle on the ray from its centre through ``toward``."""
    angle = math.atan2(toward[1] - center[1], toward[0] - center[0])
    return center[0] + radius * math.cos(angle), center[1] + radius * math.sin(angle)


# Knife face: concave arc r 3.175 (.125) about STEP (-6.547880, -0.605793).
KNIFE_ARC_R = 3.175
KNIFE_ARC_CENTER = step_to_part(-6.547880, -0.605793)
KNIFE_TIP = (
    KNIFE_Y,
    KNIFE_ARC_CENTER[1]
    + math.sqrt(KNIFE_ARC_R**2 - (KNIFE_Y - KNIFE_ARC_CENTER[0]) ** 2),
)  # STEP (-3.810, 1.001889)
KNIFE_ARC_LOW = _on_circle(
    KNIFE_ARC_CENTER, KNIFE_ARC_R, step_to_part(-3.398442, -0.203715)
)
# 30 deg chamfer from the tip to the top face's high corner.
TOP_HIGH = step_to_part(-3.245880, 1.327147)
# Top face, falling 5.53 deg toward the heel, into an r .005 edge.
TOP_FILLET_R = 0.127
TOP_FILLET_CENTER = step_to_part(4.038840, 0.494027)
TOP_FILLET_START = _on_circle(
    TOP_FILLET_CENTER, TOP_FILLET_R, step_to_part(4.051083, 0.620436)
)
TOP_FILLET_END = _on_circle(
    TOP_FILLET_CENTER, TOP_FILLET_R, step_to_part(4.148709, 0.557729)
)
# Back face down to the heel cylinder, round the heel to the bottom face.
HEEL_START = _on_circle(HEEL_CENTER, HEEL_R, step_to_part(5.509662, -1.789552))
HEEL_END = _on_circle(HEEL_CENTER, HEEL_R, step_to_part(3.967219, -4.061418))
# Bottom face, rising 8.45 deg toward the knife, into the r .038 knee.
KNEE_R = 0.9652
KNEE_CENTER = step_to_part(-2.174000, -2.172973)
KNEE_START = _on_circle(KNEE_CENTER, KNEE_R, step_to_part(-2.315880, -3.127688))
KNEE_END = _on_circle(KNEE_CENTER, KNEE_R, step_to_part(-3.131429, -2.295204))

# The closed side profile, part (Y, Z), traversed knife tip -> top -> heel
# -> bottom -> knife: ("line", start, end) or ("arc", centre, start, end),
# every arc its minor arc.
PROFILE: tuple[tuple, ...] = (
    ("line", KNIFE_TIP, TOP_HIGH),
    ("line", TOP_HIGH, TOP_FILLET_START),
    ("arc", TOP_FILLET_CENTER, TOP_FILLET_START, TOP_FILLET_END),
    ("line", TOP_FILLET_END, HEEL_START),
    ("arc", HEEL_CENTER, HEEL_START, HEEL_END),
    ("line", HEEL_END, KNEE_START),
    ("arc", KNEE_CENTER, KNEE_START, KNEE_END),
    ("line", KNEE_END, KNIFE_ARC_LOW),
    ("arc", KNIFE_ARC_CENTER, KNIFE_ARC_LOW, KNIFE_TIP),
)
TOP_Z = TOP_HIGH[1]  # 5.405, the clamp's highest line


def _cross(
    o: tuple[float, float], a: tuple[float, float], b: tuple[float, float]
) -> float:
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def profile_area() -> float:
    """The profile's area, mm^2 (Green's theorem over its lines and arcs)."""
    twice = 0.0
    for segment in PROFILE:
        if segment[0] == "line":
            _, p, q = segment
            twice += p[0] * q[1] - q[0] * p[1]
        else:
            _, c, p, q = segment
            r = math.dist(c, p)
            sweep = math.atan2(
                _cross(c, p, q),
                (p[0] - c[0]) * (q[0] - c[0]) + (p[1] - c[1]) * (q[1] - c[1]),
            )
            # integral of (x dy - y dx) along the arc from p to q.
            twice += c[0] * (q[1] - p[1]) - c[1] * (q[0] - p[0]) + r * r * sweep
    return abs(twice) / 2.0


def _line_z(p: tuple[float, float], q: tuple[float, float], y: float) -> float:
    return p[1] + (y - p[0]) * (q[1] - p[1]) / (q[0] - p[0])


# --- counterbore and through slot -------------------------------------------
# Both obrounds run SLOT_TRAVEL from the screw axis toward the heel (-Y).
SLOT_TRAVEL = 0.762  # .030
COUNTERBORE_DIA = 5.334  # .210
THROUGH_SLOT_DIA = 3.302  # .130
COUNTERBORE_FLOOR_Z = -1.893573 + Z_OFFSET  # 2.184
# The counterbore is cut mid-plane from a plane clear above the clamp down to
# its floor.
COUNTERBORE_SKETCH_Z = 8.0
COUNTERBORE_CUT_DEPTH = 2.0 * (COUNTERBORE_SKETCH_Z - COUNTERBORE_FLOOR_Z)


def obround_area(dia: float) -> float:
    return math.pi * dia**2 / 4.0 + dia * SLOT_TRAVEL


# --- the supplied screw (second body) ---------------------------------------
# STEP 44038 SHCS: head Ø4.6482 x 2.8448 with 45 deg breaks of .232 at both
# ends, 3/32 hex socket 1.786 deep, major Ø2.8448, 9.525 under the head
# (McMaster 91251A108's catalogue head, the same #4-40 x 3/8 SHCS).
SCREW_HEAD_DIA = 0.183 * INCH
SCREW_HEAD_HEIGHT = 0.112 * INCH
SCREW_HEAD_CHAMFER = 0.232
SCREW_MAJOR_DIA = 0.112 * INCH
SCREW_LENGTH = 0.375 * INCH
SCREW_SOCKET_AF = 3.0 / 32.0 * INCH
SCREW_SOCKET_DEPTH = 1.786
SCREW_BEARING_Z = COUNTERBORE_FLOOR_Z
SCREW_HEAD_TOP_Z = SCREW_BEARING_Z + SCREW_HEAD_HEIGHT  # 5.029 (STEP 0.951227)
SCREW_TIP_Z = SCREW_BEARING_Z - SCREW_LENGTH  # -7.341 (STEP -11.418573)
SCREW_TIP_DEPTH = -SCREW_TIP_Z
# The socket is cut mid-plane about the head top.
SCREW_SOCKET_CUT_DEPTH = 2.0 * SCREW_SOCKET_DEPTH


def _frustum(h: float, r1: float, r2: float) -> float:
    return math.pi * h * (r1 * r1 + r1 * r2 + r2 * r2) / 3.0


def screw_revolved_volume() -> float:
    rh = SCREW_HEAD_DIA / 2.0
    c = SCREW_HEAD_CHAMFER
    head = math.pi * rh**2 * (SCREW_HEAD_HEIGHT - 2.0 * c) + 2.0 * _frustum(
        c, rh, rh - c
    )
    return head + math.pi * (SCREW_MAJOR_DIA / 2.0) ** 2 * SCREW_LENGTH


def screw_socket_volume() -> float:
    return math.sqrt(3.0) / 2.0 * SCREW_SOCKET_AF**2 * SCREW_SOCKET_DEPTH


def screw_profile() -> tuple[tuple[float, float], ...]:
    """The screw's revolve half-profile, (radius, z), closed along the axis."""
    rh = SCREW_HEAD_DIA / 2.0
    c = SCREW_HEAD_CHAMFER
    rm = SCREW_MAJOR_DIA / 2.0
    return (
        (0.0, SCREW_HEAD_TOP_Z),
        (rh - c, SCREW_HEAD_TOP_Z),
        (rh, SCREW_HEAD_TOP_Z - c),
        (rh, SCREW_BEARING_Z + c),
        (rh - c, SCREW_BEARING_Z),
        (rm, SCREW_BEARING_Z),
        (rm, SCREW_TIP_Z),
        (0.0, SCREW_TIP_Z),
    )


def socket_hexagon() -> tuple[tuple[float, float], ...]:
    """The socket's six corners, part (X, Y), flats across X."""
    r = SCREW_SOCKET_AF / math.sqrt(3.0)
    return tuple(
        (r * math.sin(math.radians(60.0 * i)), r * math.cos(math.radians(60.0 * i)))
        for i in range(6)
    )


# --- volumes (mm^3) ---------------------------------------------------------
PROFILE_AREA = profile_area()
V_EXTRUDED = PROFILE_AREA * WIDTH
# Top and bottom faces are planes over the whole obrounds, so each cut's
# volume is its area times the height at the obround's centroid.
_CENTROID_Y = -SLOT_TRAVEL / 2.0
V_COUNTERBORE = obround_area(COUNTERBORE_DIA) * (
    _line_z(TOP_HIGH, TOP_FILLET_START, _CENTROID_Y) - COUNTERBORE_FLOOR_Z
)
V_THROUGH_SLOT = obround_area(THROUGH_SLOT_DIA) * (
    COUNTERBORE_FLOOR_Z - _line_z(HEEL_END, KNEE_START, _CENTROID_Y)
)
V_BODY = V_EXTRUDED - V_COUNTERBORE - V_THROUGH_SLOT
V_SCREW = screw_revolved_volume() - screw_socket_volume()
V_TOTAL = V_BODY + V_SCREW

# The vendor solids (FreeCAD, STEP 26000): the body 264.6379, the screw
# 82.9860 (threaded). The model's body exceeds the vendor body by the O-ring
# recess and the edge breaks it leaves out; its screw by the thread groove.
STEP_BODY_VOLUME = 264.6379
STEP_SCREW_VOLUME = 82.9860
STEP_PROFILE_AREA = 38.259118  # section at STEP z = 3.5, outside the counterbore

# --- feature names ------------------------------------------------------------
BODY_SKETCH = "ClampProfile"
BODY_FEATURE = "ClampBody"
THROUGH_SLOT_SKETCH = "ScrewSlotProfile"
THROUGH_SLOT_FEATURE = "ScrewSlot"
COUNTERBORE_PLANE = "CounterboreSketchPlane"
COUNTERBORE_SKETCH = "CounterboreProfile"
COUNTERBORE_FEATURE = "Counterbore"
SCREW_SKETCH = "ScrewProfile"
SCREW_FEATURE = "Screw"
SOCKET_PLANE = "ScrewHeadTopPlane"
SOCKET_SKETCH = "ScrewSocketProfile"
SOCKET_FEATURE = "ScrewSocket"

# --- the specification-control sheet -----------------------------------------
# Catalogue sizes print as native reference dimensions on hidden construction
# lines (``_supplier_screw_reference``), each with its catalogue letter as
# the callout below. Front plane: sketch (x, y) = part (X, Y), the plan the
# FRONT view shows. Top plane: sketch (x, y) = part (X, -Z), the TOP view
# (looking at the knife; third-angle, so the clamp's base is up). Each line
# lies on a silhouette edge of its view (A and C on the side faces, F on the
# heel line, B and D on a side face, the 4-40 chord on the screw's tip).
# Within one sketch a line may share at most one end with the lines before
# it: ``_linear`` anchors any free end, so a line welded at both ends (F on
# the knife edge closed A-F-C into a U) over-defines the sketch (farm r2,
# run 20261117T234918780Z). F on the heel line touches only C's start.
D_REFERENCE = CATALOG_D_IN * INCH
B_REFERENCE = CATALOG_B_IN * INCH
SUPPLIER_REFERENCE_DIMENSIONS = (
    ("SupplierA", KNIFE_Y, "vertical"),
    ("SupplierC", KNIFE_Y - HEEL_Y, "vertical"),
    ("SupplierF", WIDTH, "horizontal"),
    ("SupplierB", -B_REFERENCE, "vertical"),
    ("SupplierD", -D_REFERENCE, "vertical"),
    ("SupplierThreadDiameter", SCREW_MAJOR_DIA, "horizontal"),
)
SUPPLIER_REFERENCE_STARTS = {
    "SupplierA": (-WIDTH / 2.0, 0.0),
    "SupplierC": (WIDTH / 2.0, HEEL_Y),
    "SupplierF": (-WIDTH / 2.0, HEEL_Y),
    "SupplierB": (WIDTH / 2.0, 0.0),
    "SupplierD": (WIDTH / 2.0, -B_REFERENCE),
    "SupplierThreadDiameter": (-SCREW_MAJOR_DIA / 2.0, -SCREW_TIP_Z),
}
SUPPLIER_REFERENCE_PLANES = {
    "SupplierB": "Top",
    "SupplierD": "Top",
    "SupplierThreadDiameter": "Top",
}
SUPPLIER_REFERENCE_SIDES = {
    "SupplierA": "left",
    "SupplierC": "right",
    "SupplierF": "bottom",
    "SupplierB": "right",
    "SupplierD": "right",
    "SupplierThreadDiameter": "top",
}
# (places, presentation, fraction denominator, callout below)
SUPPLIER_REFERENCE_FORMATS = {
    "SupplierA": (3, "length", None, "A"),
    "SupplierC": (3, "length", None, "C"),
    "SupplierF": (3, "length", None, "F"),
    "SupplierB": (3, "length", None, "B"),
    "SupplierD": (3, "length", None, "D MIN"),
    "SupplierThreadDiameter": (3, "diameter", None, "4-40"),
}
CATALOG_LETTERS = {
    "SupplierA": CATALOG_A_IN,
    "SupplierB": CATALOG_B_IN,
    "SupplierC": CATALOG_C_IN,
    "SupplierD": CATALOG_D_IN,
    "SupplierF": CATALOG_F_IN,
}
for _name, _inch in CATALOG_LETTERS.items():
    (_value,) = (abs(v) for n, v, _ in SUPPLIER_REFERENCE_DIMENSIONS if n == _name)
    if not math.isclose(_value, _inch * INCH, abs_tol=1e-9):
        raise AssertionError(f"{_name} does not print catalogue {_inch}")

ITEM = "PITBULL CLAMP 26000, TOOL STEEL, KNIFE EDGE, 4-40 X 3/8 SHCS"
SUPPLIER_DATA = (
    "MITEE-BITE PITBULL-INST-0426 ROW 26000 GOVERNS; A-F AS LETTERED.",
    f"SHCS 4-40 TORQUE {MAX_TORQUE_FT_LB:.2f} FT-LB MAX; FIXTURE USES 0.5 FT-LB.",
    f"HOLDS {HOLDING_FORCE_LB} LB; THROW {THROW_IN:.4f}".replace(" 0.", " .")
    + f"; {PER_PACKAGE} PER PACKAGE.",
    f"O-RING {O_RING_SKU} SUPPLIED UNDER THE BODY; NOT SHOWN.",
)
