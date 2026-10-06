r"""McMaster-Carr 1330K524 -- stock double-loop extension spring, pure geometry.

Every constant here is a dimension the vendor's own SolidWorks tree carries
(feature dump ``cad/out/reports/mcmaster-1330K524-dump.json``) or an exact
consequence of two of them.  Nothing is taken from a spring-rate formula, and
nothing here touches COM -- import it from a spec, a builder, an assembly
placement or a test without a live SolidWorks session.

Vendor frame (reproduced verbatim by ``diag_build_1330K524.py``):

* spring axis = **+X**, origin at mid-length (vendor COM
  ``[0.022552, -0.011927, 0.000338]`` mm),
* both end-loop (eye) axes = **+Z**; the two loops are 1.75-turn *double*
  loops centred on ``z = 0``, so each end occupies :data:`END_OCCUPIED_WIDTH_MM`
  of Z (not one wire diameter),
* the two end LOOPS are exact images of each other under the C2 rotation
  ``(x, y, z) -> (-x, y, -z)`` -- endpoint for endpoint: the ``-X`` loop's
  wire tip ``(-116.7003, 0, -1.640205)`` maps onto the ``+X`` tip, and its
  far end onto the ``+X`` loop's start.  The two END ASSEMBLIES are **not**
  C2 images: the ``+X`` end carries an extra reversed half-turn onto the
  coil, and the two transition splines have different handle lengths, which
  is why the vendor COM sits at ``x = +0.0226`` mm rather than 0,
* the wire crosses ``y = 0`` at every coil-instance junction, which is where
  the vendor's sweep profiles sit.

Length parameter
----------------
``length_mm`` everywhere is the **catalogue INSIDE-loop length**: the distance
between the inner surfaces of the two end loops, measured along X.  The vendor
marks it in their own layout sketch (a construction line from ``x = -127.0`` to
``x = -128.6002``, i.e. from ``-L/2`` to ``-L/2 - wire``), so

    loop eye centre |x| = L/2 - (mean coil radius - wire radius)

is exact, not fitted.  The domain is the catalogue's extension range,
``FREE_LENGTH_MM <= length_mm <= MAX_LENGTH_MM``: an extension spring with
initial tension has no compressed state, so a length below free length is
rejected rather than modelled.  Within it, a longer ``length_mm`` stretches
the coil (its pitch opens; the turn count and both rigid end loops are
untouched) and translates each end assembly rigidly by
``(L - FREE_LENGTH_MM) / 2``.

.. warning:: :data:`COIL_TURNS` is the vendor CAD model's turn count.  The
   catalogue rate (0.3117 N/mm) implies roughly 150 active coils for this wire
   and coil diameter, and a close-wound free body of this length would hold
   ~145 turns, so the vendor part is a *display* model: never derive force,
   rate or solid height from this module's turn count.  This module derives
   none -- both length bounds are catalogue figures.
"""

from __future__ import annotations

__all__ = [
    "COIL_AXIS",
    "COIL_MEAN_RADIUS_MM",
    "COIL_OD_MM",
    "COIL_SEGMENTS",
    "COIL_SEGMENT_TURNS",
    "COIL_TURNS",
    "END_OCCUPIED_WIDTH_MM",
    "EYE_AXIS",
    "EYE_ID_MM",
    "EYE_OD_MM",
    "FREE_LENGTH_MM",
    "LOOP_HALF_RISE_MM",
    "LOOP_PITCH_MM",
    "LOOP_RISE_MM",
    "LOOP_TURNS",
    "MAX_LENGTH_MM",
    "WIRE_DIA_MM",
    "WIRE_RADIUS_MM",
    "coil_axial_span_mm",
    "coil_end_x_mm",
    "coil_pitch_mm",
    "coil_segment_rise_mm",
    "coil_start_x_mm",
    "end_centers_mm",
    "end_tip_points_mm",
    "overall_length_mm",
    "validate_length_mm",
]

# --- catalogue figures, all confirmed against the native tree -------------
FREE_LENGTH_MM = 254.0  # inside loop to inside loop (vendor Length@Sketch1)
MAX_LENGTH_MM = 421.6146  # catalogue maximum extended length
COIL_OD_MM = 12.7  # vendor OD@Sketch1 (= eye OD; the eye is a coil)
WIRE_DIA_MM = 1.6002  # vendor Wire Diameter@Sketch1
COIL_TURNS = 128.0  # 4 patterned segments x 32 revolutions (CAD model)

# --- decoded wire / coil geometry ----------------------------------------
WIRE_RADIUS_MM = 0.8001  # WIRE_DIA_MM / 2 (vendor sweep profile radius)
COIL_MEAN_RADIUS_MM = 5.5499  # (COIL_OD_MM - WIRE_DIA_MM) / 2
COIL_AXIS = (1.0, 0.0, 0.0)
COIL_SEGMENTS = 4  # vendor LPattern1 instance count
COIL_SEGMENT_TURNS = 32.0  # vendor Helix/Spiral1 revolutions

# --- decoded end-loop geometry (rigid: never scales with length) ---------
LOOP_TURNS = 1.75  # vendor Helix/Spiral3 & 4 revolutions
LOOP_RISE_MM = 3.28041  # their axial (Z) rise
LOOP_PITCH_MM = 1.87452  # LOOP_RISE_MM / LOOP_TURNS
LOOP_HALF_RISE_MM = 1.640205  # LOOP_RISE_MM / 2 -- the loop is Z-centred
END_OCCUPIED_WIDTH_MM = 4.88061  # LOOP_RISE_MM + WIRE_DIA_MM (Z envelope)
EYE_AXIS = (0.0, 0.0, 1.0)
EYE_ID_MM = 9.4996  # = the coil bore: 2 * R_mean - wire
EYE_OD_MM = 12.7  # 2 * COIL_MEAN_RADIUS_MM + WIRE_DIA_MM

# Inside-length bookkeeping: the eye centre is inset from the catalogue end
# face by (mean radius - wire radius); the first full coil turn starts one mean
# radius further in, which is also where the loop's wire tip sits.
_EYE_INSET_MM = 4.7498  # COIL_MEAN_RADIUS_MM - WIRE_RADIUS_MM
_COIL_END_INSET_MM = 10.2997  # _EYE_INSET_MM + COIL_MEAN_RADIUS_MM


def validate_length_mm(length_mm: float | None = None) -> float:
    """Resolve and range-check a catalogue inside-loop length in mm.

    Args:
        length_mm: Inside-loop length in mm, or ``None`` for the free length.

    Returns:
        float: The resolved length in mm.

    Raises:
        ValueError: If the length is not finite, is below the catalogue free
            length :data:`FREE_LENGTH_MM` (an extension spring with initial
            tension has no compressed state) or exceeds the catalogue maximum
            extended length :data:`MAX_LENGTH_MM`.
    """
    if length_mm is None:
        return FREE_LENGTH_MM
    length = float(length_mm)
    if length != length or length in (float("inf"), float("-inf")):
        raise ValueError(f"length_mm must be finite, got {length_mm!r}")
    if length < FREE_LENGTH_MM:
        raise ValueError(
            f"length_mm {length:.4f} is below the catalogue free length "
            f"{FREE_LENGTH_MM:.4f} mm: this is an extension spring with "
            f"initial tension, so it has no compressed state to model"
        )
    if length > MAX_LENGTH_MM:
        raise ValueError(
            f"length_mm {length:.4f} exceeds the catalogue maximum extended "
            f"length {MAX_LENGTH_MM:.4f} mm"
        )
    return length


def coil_start_x_mm(length_mm: float | None = None) -> float:
    """X of the coil's ``-X`` end plane (the first turn's start, and the X of
    the ``-X`` loop's wire tip)."""
    return -(validate_length_mm(length_mm) / 2.0 - _COIL_END_INSET_MM)


def coil_end_x_mm(length_mm: float | None = None) -> float:
    """X where the coil's last turn ends (half a pitch of the ``+X`` end's
    half-turn short of ``-coil_start_x_mm``)."""
    return -coil_start_x_mm(length_mm) - WIRE_RADIUS_MM


def coil_axial_span_mm(length_mm: float | None = None) -> float:
    """Axial extent of the coil body between those two planes."""
    return coil_end_x_mm(length_mm) - coil_start_x_mm(length_mm)


def coil_pitch_mm(length_mm: float | None = None) -> float:
    """Coil pitch: the span shared by the fixed :data:`COIL_TURNS`."""
    return coil_axial_span_mm(length_mm) / COIL_TURNS


def coil_segment_rise_mm(length_mm: float | None = None) -> float:
    """Axial rise of one patterned coil segment (= the pattern spacing)."""
    return coil_axial_span_mm(length_mm) / COIL_SEGMENTS


def end_centers_mm(
    length_mm: float | None = None,
) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    """Eye centres of the two end loops, in vendor coordinates.

    Both loops are 1.75-turn double loops whose axes are ``+Z`` and whose
    centreline circles are centred on ``z = 0``; the returned point is the
    centre of that circle, i.e. the point a pin through the eye passes
    through.

    Args:
        length_mm: Catalogue inside-loop length in mm, ``None`` for free.

    Returns:
        tuple: ``(negative_x_center, positive_x_center)``, each ``(x, y, z)``
        in mm.
    """
    x = validate_length_mm(length_mm) / 2.0 - _EYE_INSET_MM
    return ((-x, 0.0, 0.0), (x, 0.0, 0.0))


def end_tip_points_mm(
    length_mm: float | None = None,
) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    """Wire tip (free end) centreline points of the two end loops.

    Each tip lies on the spring's ``y = 0`` plane, one mean coil radius
    inboard of its eye centre, at the Z end of the loop's rise: the ``-X``
    loop tip at ``-LOOP_HALF_RISE_MM``, the ``+X`` tip at
    ``+LOOP_HALF_RISE_MM`` (the C2 image).

    Returns:
        tuple: ``(negative_x_tip, positive_x_tip)``, each ``(x, y, z)`` in mm.
    """
    x = -coil_start_x_mm(length_mm)
    return ((-x, 0.0, -LOOP_HALF_RISE_MM), (x, 0.0, LOOP_HALF_RISE_MM))


def overall_length_mm(length_mm: float | None = None) -> float:
    """Outside-to-outside X envelope (the catalogue length plus one wire
    diameter of loop wall at each end)."""
    return validate_length_mm(length_mm) + 2.0 * WIRE_DIA_MM
