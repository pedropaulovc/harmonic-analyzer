r"""Stock channel spring -- McMaster 9432K31 native geometry (pure math).

Music-wire steel extension spring, machine hook ends, 1/4" OD x 0.026" wire,
55.5 coils, 1.948" free length. Geometry comes from the supplier model
``cad/references/mcmaster/9432K31.SLDPRT`` and its native feature harvest
``cad/out/reports/mcmaster-9432K31-dump.json``.

Frame
-----
Vendor part frame, shared by :mod:`diagnostics.diag_build_9432K31`:

* coil axis along **+X**, origin at the spring centre (the vendor model is
  symmetric about its own origin: COM 4e-5, 3.7e-3, -1e-4 mm),
* the two hook eyes have parallel **Z** axes, both openings facing -Y,
* the free-end wire tips lie in the model XY plane (z = 0).

Length law
----------
The vendor drives length through one dimension (``Length@Sketch1``) and one
equation::

    D3@Helix/Spiral1 = Length - 2 * (OD - 2 * Wire Diameter)

so only the *coil* stretches: the helix height is ``L - 2*ID`` and the pitch is
that height over a fixed 55.5 revolutions.  Wire diameter, coil diameter, hook
radius, hook arc angle and the coil<->hook transition are rigid; the whole
hook assembly translates by +-(L - free)/2 as the spring extends.  That is why
``end_centers_mm`` is exact for any catalog length and not an approximation.

Catalog lengths are measured **inside hook to inside hook**; the eye centres
sit one inside-radius (ID/2) in from each tip, which is what
:func:`end_centers_mm` returns.
"""

from __future__ import annotations

# --- vendor dimensions (mm) -------------------------------------------------
# 9432K31_Music-Wire Steel Extension Springs with Hook Ends.SLDPRT
FREE_LENGTH_MM = 49.4792  # Length@Sketch1 (1.948")
MAX_LENGTH_MM = 138.3792  # Extended Length at Maximum Load@Sketch1
COIL_OD_MM = 6.35  # OD@Sketch1 (1/4")
WIRE_DIA_MM = 0.6604  # Wire Diameter@Sketch1 (0.026")
COIL_TURNS = 55.5  # global "Num Coils" -> D5@Helix/Spiral1

# --- derived, all used by the native rebuild --------------------------------
COIL_ID_MM = COIL_OD_MM - 2.0 * WIRE_DIA_MM  # 5.0292; drives the length law
COIL_MEAN_RADIUS_MM = (COIL_OD_MM - WIRE_DIA_MM) / 2.0  # 2.8448; helix + hook
# D1@3DSketch1 = D2@3DSketch1 = OD * 3/4: the spline handle magnitude at both
# ends of the coil->hook transition (vendor equation index 0).
TRANSITION_TANGENT_MM = COIL_OD_MM * 3.0 / 4.0  # 4.7625

_LENGTH_EPS_MM = 1e-6


def check_length_mm(length_mm: float | None) -> float:
    """Validate a catalog inside-hook length; ``None`` means the free length.

    Raises:
        ValueError: below the catalog free length or past the extended length
            at maximum load.
    """
    if length_mm is None:
        return FREE_LENGTH_MM
    length = float(length_mm)
    if not (
        FREE_LENGTH_MM - _LENGTH_EPS_MM <= length <= MAX_LENGTH_MM + _LENGTH_EPS_MM
    ):
        raise ValueError(
            f"9432K31 length {length:.4f} mm is outside the vendor range "
            f"[{FREE_LENGTH_MM}, {MAX_LENGTH_MM}] mm "
            "(free length .. extended length at maximum load)"
        )
    return min(max(length, FREE_LENGTH_MM), MAX_LENGTH_MM)


def helix_height_mm(length_mm: float | None = None) -> float:
    """Coil axial extent = vendor equation ``Length - 2*(OD - 2*wire)``."""
    return check_length_mm(length_mm) - 2.0 * COIL_ID_MM


def helix_pitch_mm(length_mm: float | None = None) -> float:
    """Constant pitch over the fixed 55.5 revolutions (free: 0.710285)."""
    return helix_height_mm(length_mm) / COIL_TURNS


def coil_ends_mm(length_mm: float | None = None) -> tuple[float, float]:
    """Axial x of the coil (helix) start and end -- free: -+19.7104."""
    half = helix_height_mm(length_mm) / 2.0
    return (-half, half)


def end_centers_mm(
    length_mm: float | None = None,
) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    """Hook eye centres, negative-X end first, in vendor coordinates (mm).

    Each eye is a 180-degree arc of the wire centreline about this point, so
    the point is both the eye's bore axis (along Z) and the anchor a pin or
    stud pulls on.  Free length: (-22.225, 0, 0) and (+22.225, 0, 0).
    """
    x = check_length_mm(length_mm) / 2.0 - COIL_ID_MM / 2.0
    return ((-x, 0.0, 0.0), (x, 0.0, 0.0))
