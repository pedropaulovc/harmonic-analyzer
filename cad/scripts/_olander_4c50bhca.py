r"""Pure Olander 4C50BHCA button-screw dimensions; isolate this SKU's cache inputs.

Olander 4C50BHCA, "4-40 X 1/2 BUT SOC ALLOY": alloy steel button head socket
cap screw to ASME B18.3, #4-40 UNC, 1/2 in under the head, plain finish
(https://www.olander.com/items/4C50BHCA, read live 2026-10-20; the page lists
McMaster-Carr 91255A110 among its alternate codes, ``MCMASTER_XREF``, which
is recorded as a cross-reference only: McMaster's own product page and CAD
were not reachable, HTTP 403). The page gives the head Ø 0.213 / 0.201 in,
its height 0.059 / 0.051 in and the 0.063 in (1/16) hex.

STANDARD: ASME B18.3-2012 Table 11, #4 button head socket cap screw (the
evidence copy, pp. 33-34): A 0.213 / 0.201, H 0.059 / 0.051, J 1/16, T (the
minimum key engagement) 0.035, F (the underhead fillet's diameter at the
bearing face) 0.132 max, its radius 0.004 min (note 7: an optional smooth
concave curve between F min and F max), the length -0.03 in up to 1 in long
(note 3), the head's runout to the shank 0.008 FIM (note 11a) and a flat
bearing face (note 10).

``DIMS`` is the shared button-head recipe's record (``_button_head_dimensions``,
the 91255A106 family law, [INFERENCE] proportions) at the page's maximum head,
its socket at the standard's minimum key engagement T rather than the family
law's 0.55 H (0.0325 in, under T).
The underhead fillet is a standard-bounded nominal choice, not vendor
geometry: R ``FILLET_R`` 0.010 in (over the 0.004 minimum), tangent to the
bearing face at exactly F max, so the modelled screw never seats on a
smaller fillet than the standard admits.
"""

from _button_head_dimensions import ButtonHeadScrew

PART_NO = "4C50BHCA"
MCMASTER_XREF = "91255A110"  # Olander's listed alternate code
IN = 25.4
# The catalogue's designation, as the C4 fastener table prints it.
THREAD = "#4-40"
LENGTH_TEXT = "1/2"
LENGTH_TOL_MINUS = 0.03 * IN  # ASME B18.3 note 3, up to 1 in long
HEAD_DIA_MIN = 0.201 * IN  # Olander's and ASME B18.3's A min
HEAD_RUNOUT_FIM = 0.008 * IN  # ASME B18.3 note 11a
FILLET_DIA_MAX = 0.132 * IN  # ASME B18.3 F max, at the bearing face
FILLET_R = 0.010 * IN  # nominal choice over the standard's 0.004 min
_FILLET_R_MIN = 0.004 * IN

DIMS = ButtonHeadScrew(
    part_no=PART_NO,
    major_dia=0.112 * IN,
    pitch=IN / 40.0,
    length=0.5 * IN,  # under the head
    head_dia=0.213 * IN,
    head_h=0.059 * IN,
    hex_af=1.0 / 16.0 * IN,
    key_engagement=0.035 * IN,  # standard minimum key engagement
)
LENGTH_MIN = DIMS.length - LENGTH_TOL_MINUS

if DIMS.flat_top_dia <= 2.0 * DIMS.hex_corner_r:
    raise ValueError("4C50BHCA flat top no longer covers the hex socket")
if DIMS.head_h - DIMS.socket_depth <= DIMS.band_h:
    raise ValueError("4C50BHCA socket floor falls into the head's band")
if FILLET_R < _FILLET_R_MIN:
    raise ValueError("4C50BHCA underhead fillet under ASME B18.3's minimum radius")
if abs(DIMS.major_dia + 2.0 * FILLET_R - FILLET_DIA_MAX) > 1e-9:
    raise ValueError("4C50BHCA underhead fillet no longer ends at F max")
if not FILLET_DIA_MAX / 2.0 < DIMS.bearing_edge_r - DIMS.edge_fillet_r:
    raise ValueError("4C50BHCA underhead fillet reaches the head's band fillet")
