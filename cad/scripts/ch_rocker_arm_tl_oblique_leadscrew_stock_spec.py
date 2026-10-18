r"""Pure-data envelope of the bought Tr8x2 leadscrew, ZYLtech HW-SC-T8x2-600 (MHA-CH-006-TL-34).

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure: ``build_ch_rocker_arm_tl_oblique_leadscrew`` revolves ``PROFILE``.
The module is named ``..._leadscrew_stock_spec`` because the pattern-D name
``ch_rocker_arm_tl_oblique_leadscrew_spec`` already belongs to C4's feed-layout
contract, which this module imports.

The item is the shop-inventory ``fixtures.trammel-tr8-leadscrew``: a ZYLtech
600 mm pre-cut T8x2 lead screw (304 stainless, single start, right hand,
pitch and lead 2) that the shop cuts to the installed length. The ends are
broken, and no journals are turned. The KP08 inner rings' two set screws each
and the handwheel's one set screw bear on milled flats, not on the thread's
crests (``FLAT_STATIONS``).

Datasheet-built: no vendor CAD obtained (ZYLtech publishes no STEP, IGES, STL
or drawing download on the product page, checked 2026-10-17 UTC; see
``C:/src/dt-logs/trammel-bought/vendor-cad/HW-SC-T8x2-600.provenance.md``).

Sources:

- FROM C4 (imported from ``ch_rocker_arm_tl_oblique_leadscrew_spec``, never
  retyped): the Ø8 major diameter, the lead 2, the 600 stock length and the
  installed length ``SCREW_LENGTH`` 410.
- SOURCED, https://www.zyltech.com/8mm-t8x2-trapezoidal-acme-lead-screw-w-brass-nut-pre-cut-lengths-150mm-2000mm/
  (read 2026-10-16; evidence in
  ``C:/src/dt-logs/trammel-leadscrew/zyltech/zyltech-tr8x2.md``): "T8x2 single
  start, Pitch: 2mm, Lead per turn: 2mm, Right handed trapezoidal Lead Screw,
  Material: 304 Stainless Steel", SKU HW-SC-T8x2-600.
- SOURCED, shop inventory ``fixtures.trammel-tr8-leadscrew`` (owner/C4 layout
  decision 2026-10-16): cut to 410 ±0.5, deburr and lightly chamfer the cut end.
  The print uses the title block's .X band instead (``LENGTH_TOLERANCE``): the
  self-checks below show the feed absorbs it, so the cut needs no band of its own.
- FROM the bought-parts contract: the Tr8x2 thread minor diameter is 6.0. The
  Ooznest Tr8x2 vendor STEP (cross-reference only) has the same Ø6.0 root.
- DECIDED: both ends are broken 0.25 x 45°, the title block's edge break
  ("BREAK SHARP EDGES R0.25 OR CHAMFER 0.25 MAX") at its limit, so they print
  nothing. The inventory's "lightly chamfer the cut end" asks no more.
- DECIDED (user ruling on the machinist review's rule 23, lock threaded
  joints): a set-screw flat ``FLAT_DEPTH`` deep and ``FLAT_LENGTH`` long under
  each set screw, stationed from C4's layout: each KP08's axial centre
  ``KP08_S`` and the handwheel's set screw, ``HANDWHEEL_GRUB_FROM_HUB`` into
  its hub. Each KP08 takes two flats ``KP08_SET_SCREW_SPACING_DEG`` apart, as
  its two set screws are (``ch_rocker_arm_tl_oblique_pillow_block_spec``,
  SOURCED from the KP08 listing: "two set screws 120 degrees apart on the
  inner ring"); the handwheel ships with one set screw
  (``ch_rocker_arm_tl_oblique_handwheel_spec``). The flats' clock round the
  axis is set at assembly: each KP08 ring and the handwheel turn to them.
- SOURCED, ISO 4029: an M5 cup point is 2.5 across at most
  (``SET_SCREW_POINT_DIA``), the handwheel's set screw.
- SOURCED, ISO 2904: the Tr8x2 external thread's root d3 = d - 2 h3, h3 =
  P/2 + ac with ac = 0.25, is Ø5.5 (``SCREW_ROOT_DIA``). The flats' depth
  check uses it; the contract's Ø6.0 minor stays the modelled nut bore.
- UNVERIFIED (verify on receipt): where across each KP08's width its inner
  ring carries the set screws (the series photographs show the ring proud of
  the housing on its set-screw side; the flats sit at the block's axial
  centre), and the KP08 set screws' size (unpublished).

Thread: not modelled (bought-parts modelling rule). The body is a plain
cylinder at the major diameter, so it overstates the real screw by the thread
groove, about ``THREAD_GROOVE_MM3_PER_MM`` per mm of length. The assembly's
thread-engagement contracts (nut, KP08, handwheel) carry that.

Part frame. The axis is +Y and is published as ``ScrewAxis`` (Front ∩ Right).
y = 0 is the near (spindle-side) end, and the far end at y = ``LENGTH`` goes
into the handwheel. The part is symmetric end for end.
"""

from __future__ import annotations

import math

from _printed_tolerance import angular_band_deg, printed_band_mm
import ch_rocker_arm_tl_oblique_leadscrew_spec as feed

SUPPLIER = "ZYLtech Engineering"
SKU = "HW-SC-T8x2-600"
INVENTORY_ID = feed.SCREW_ID  # fixtures.trammel-tr8-leadscrew
QUANTITY = 1
MATERIAL = "AISI 304"

# --- FROM C4 (imported) ---------------------------------------------------------
MAJOR_DIA = feed.SCREW_MAJOR_DIA  # 8
LEAD = feed.SCREW_LEAD  # 2
STOCK_LENGTH = feed.SCREW_STOCK_LENGTH  # 600, as bought
LENGTH = feed.SCREW_LENGTH  # 410, installed (shop-cut)

# --- SOURCED: product page / inventory / contract ---------------------------------
PITCH = 2.0  # single start: the pitch equals the lead
STARTS = 1
HAND = "right"
# The cut length prints as a native one-place dimension (410.0), so the title
# block's .X row is its band; the self-checks below show the feed absorbs it.
LENGTH_PLACES = 1
LENGTH_TOLERANCE = printed_band_mm(LENGTH_PLACES)  # ±0.8, the title block's .X
MINOR_DIA = 6.0  # Tr8x2 thread minor (contract; the Ooznest STEP's root)

# --- DECIDED: the title block's edge break --------------------------------------
END_CHAMFER = 0.25  # 0.25 x 45°, both ends: "CHAMFER 0.25 MAX", printed by none

_R = MAJOR_DIA / 2.0
_R_END = _R - END_CHAMFER

# (radius, y), revolved 360° about the axis; the chain closes along the axis.
PROFILE: tuple[tuple[float, float], ...] = (
    (0.0, 0.0),
    (_R_END, 0.0),
    (_R, END_CHAMFER),
    (_R, LENGTH - END_CHAMFER),
    (_R_END, LENGTH),
    (0.0, LENGTH),
)


def revolved_volume(profile: tuple[tuple[float, float], ...]) -> float:
    """Volume (mm^3) of a closed (radius, y) polygon revolved about r = 0 (Pappus)."""
    area_moment = 0.0
    for (r1, y1), (r2, y2) in zip(profile, profile[1:] + profile[:1], strict=True):
        area_moment += (r1 + r2) * (r1 * y2 - r2 * y1)
    return abs(2.0 * math.pi * area_moment / 6.0)


# The cut blank, before its flats.
BLANK_VOLUME_MM3 = revolved_volume(PROFILE)
# The trapezoidal groove takes about half the crest-to-root annulus (the
# Ooznest Tr8x2 STEP cross-reference: 10.9 mm^3 per mm).
THREAD_GROOVE_MM3_PER_MM = math.pi * (_R**2 - (MINOR_DIA / 2.0) ** 2) / 2.0

# --- DECIDED: the set-screw flats (user ruling, see the docstring) -----------------
FLAT_DEPTH = 0.72  # under the crest: AF 7.28, inside the 7.26..7.289 the checks pass
FLAT_LENGTH = feed.SCREW_FLAT_LENGTH  # 8, along the axis, centred on the set screw
FLAT_AF = MAJOR_DIA - FLAT_DEPTH  # 7.28, across the flat to the far crest
FLAT_AF_PLACES = 2
FLAT_AF_TOLERANCE = printed_band_mm(FLAT_AF_PLACES)  # ±0.51, the title block's .XX
# The flats' stations print at one place, the cut length's row. Their length
# prints at two: each station locates its flat's near edge (rule 10: to a
# feature's edge, not its unmarked middle), so the length's band stacks onto
# the far edge's, and the far side of the set screw needs the tighter one.
FLAT_PLACES = LENGTH_PLACES
FLAT_TOLERANCE = printed_band_mm(FLAT_PLACES)  # ±0.8
FLAT_LENGTH_PLACES = 2
FLAT_LENGTH_TOLERANCE = printed_band_mm(FLAT_LENGTH_PLACES)  # ±0.51
KP08_SET_SCREW_SPACING_DEG = 120.0  # SOURCED: the KP08 listing (pillow-block spec)
CLOCK_PLACES = 0
CLOCK_TOLERANCE_DEG = angular_band_deg()  # ±1, the title block's angular row
SET_SCREW_POINT_DIA = 2.5  # SOURCED, ISO 4029: the M5 cup point's dp max
# SOURCED, ISO 2904: the Tr8x2 external root d3 = 8 - 2 x (2/2 + 0.25). The
# contract's and the vendor STEP's Ø6.0 (MINOR_DIA) is a modelled
# simplification of the root, kept for the nut bore and the groove estimate.
SCREW_ROOT_DIA = 5.5
HANDWHEEL_SET_SCREW_MAJOR = float(feed.HANDWHEEL_GRUB.removeprefix("M"))  # 5

# Each set screw's station, part frame (from the near end), from C4's layout.
FLAT_STATIONS = {
    "NearKP08": feed.KP08_S[0] - feed.SCREW_NEAR_END_S,  # 8.5
    "FarKP08": feed.KP08_S[1] - feed.SCREW_NEAR_END_S,  # 379.5
    "Handwheel": (
        feed.HUB_END_S + feed.HANDWHEEL_GRUB_FROM_HUB - feed.SCREW_NEAR_END_S
    ),  # 398.5
}
# Each flat's near edge, from the near end: what the print dimensions.
FLAT_STARTS = {
    name: station - FLAT_LENGTH / 2.0 for name, station in FLAT_STATIONS.items()
}  # 4.5, 375.5, 394.5
# What each flat sits under, as station spans on the rail (C4's s): the KP08
# blocks' widths, and the screw's length inside the handwheel's hub.
FLAT_HOUSINGS = {
    "NearKP08": (feed.KP08_FACE_S[0], feed.KP08_FACE_S[0] + feed.KP08_WIDTH),
    "FarKP08": (feed.KP08_FACE_S[1] - feed.KP08_WIDTH, feed.KP08_FACE_S[1]),
    "Handwheel": (feed.HUB_END_S, feed.SCREW_FAR_END_S),
}
# Every station's flat faces +X (clock 0). Each KP08 station takes a second
# flat KP08_SET_SCREW_SPACING_DEG round from +X toward +Z, for its second
# set screw: the "clock" flat.
CLOCKED_FLATS = ("NearKP08", "FarKP08")
FLAT_COUNT = len(FLAT_STATIONS) + len(CLOCKED_FLATS)  # 5
# The flat whose length and across-flat print, once for every flat (``NX``).
PRINTED_FLAT = "Handwheel"
FLAT_LENGTH_CALLOUT = f"{FLAT_COUNT}X"
FLAT_AF_CALLOUT = f"{len(FLAT_STATIONS)}X"  # the clock flats print their own


def flat_offset(depth: float) -> float:
    """The flat's distance from the axis at ``depth`` under the crest."""
    return _R - depth


def flat_chord(depth: float) -> float:
    """The flat's width across the screw at ``depth`` under the crest."""
    return 2.0 * math.sqrt(_R**2 - flat_offset(depth) ** 2)


def flat_half_angle_deg(depth: float) -> float:
    """Half the arc of the screw's round a flat ``depth`` deep takes."""
    return math.degrees(math.acos(flat_offset(depth) / _R))


FLAT_CHORD = flat_chord(FLAT_DEPTH)  # 4.579
# The circular segment each flat takes off the round, times its length.
_FLAT_OFFSET = flat_offset(FLAT_DEPTH)  # 3.28
FLAT_SEGMENT_AREA = (
    _R**2 * math.acos(_FLAT_OFFSET / _R) - _FLAT_OFFSET * FLAT_CHORD / 2.0
)
FLAT_VOLUME_MM3 = FLAT_SEGMENT_AREA * FLAT_LENGTH
VOLUME_MM3 = BLANK_VOLUME_MM3 - FLAT_COUNT * FLAT_VOLUME_MM3

# The drawing's manufacturing controls, each a driving native dimension
# printed under the title block's general band for its places (swTolGeneral,
# 11, prints no band of its own): name -> (nominal, ± band, places), in mm,
# or degrees for the clock angles. The cut length is the profile sketch's
# axis edge; the flats' length, across-flat and stations are FlatProfile's
# (on Front, so they print on the main view); each clock flat's across-flat
# and angle from clock 0 are its station sketch's (they print on its section).
DIMENSION_CONTROLS = {
    "CutLength": (LENGTH, LENGTH_TOLERANCE, LENGTH_PLACES),
    "FlatLength": (FLAT_LENGTH, FLAT_LENGTH_TOLERANCE, FLAT_LENGTH_PLACES),
    "FlatAF": (FLAT_AF, FLAT_AF_TOLERANCE, FLAT_AF_PLACES),
    **{
        f"{name}FlatStation": (start, FLAT_TOLERANCE, FLAT_PLACES)
        for name, start in FLAT_STARTS.items()
    },
    **{
        f"{name}ClockAF": (FLAT_AF, FLAT_AF_TOLERANCE, FLAT_AF_PLACES)
        for name in CLOCKED_FLATS
    },
    **{
        f"{name}ClockAngle": (
            KP08_SET_SCREW_SPACING_DEG,
            CLOCK_TOLERANCE_DEG,
            CLOCK_PLACES,
        )
        for name in CLOCKED_FLATS
    },
}
ANGULAR_DIMENSIONS = frozenset(f"{name}ClockAngle" for name in CLOCKED_FLATS)
DRAWING_DIMENSIONS = {
    "ScrewProfile": {"CutLength"},
    "FlatProfile": {
        "FlatLength",
        "FlatAF",
        *(f"{name}FlatStation" for name in FLAT_STATIONS),
    },
    **{
        f"{name}ClockProfile": {f"{name}ClockAF", f"{name}ClockAngle"}
        for name in CLOCKED_FLATS
    },
}
DIMENSION_PRECISION = {
    name: places for name, (_, _, places) in DIMENSION_CONTROLS.items()
}
DRAWING_PRECISION = {
    feature: {name: DIMENSION_PRECISION[name] for name in names}
    for feature, names in DRAWING_DIMENSIONS.items()
}
DIMENSION_TOLERANCE_TYPES = dict.fromkeys(DIMENSION_CONTROLS, 11)


def control_si(name: str) -> tuple[float, float]:
    """``(nominal, band)`` of a control in SolidWorks' units: m, or radians."""
    nominal, band, _places = DIMENSION_CONTROLS[name]
    if name in ANGULAR_DIMENSIONS:
        return math.radians(nominal), math.radians(band)
    return nominal / 1000.0, band / 1000.0


# --- Self-checks ----------------------------------------------------------------
if not LENGTH + LENGTH_TOLERANCE <= STOCK_LENGTH:
    raise AssertionError("the installed screw is longer than the stock")
# A short cut: the fitter keeps the handwheel's minimum engagement at the far
# end and gives up near stub, so the two margins together must cover the band.
if (feed.NEAR_STUB - feed.NEAR_STUB_MIN) + (
    feed.HANDWHEEL_ENGAGEMENT - feed.HANDWHEEL_ENGAGEMENT_MIN
) < LENGTH_TOLERANCE:
    raise AssertionError("a short cut loses the near stub or the handwheel grip")
# A long cut at the nominal near stub: the far end stays inside the wheel.
if not feed.SCREW_FAR_END_S + LENGTH_TOLERANCE < feed.WHEEL_S[1]:
    raise AssertionError("a long cut stands proud of the handwheel")
if not 0.0 < END_CHAMFER < MAJOR_DIA / 2.0:
    raise AssertionError("the end chamfer is not inside the screw")
if abs(PITCH * STARTS - LEAD) > 1e-9:
    raise AssertionError("the pitch and starts no longer make C4's lead")
# The flats, at the band's limits. The deepest stays in the thread's crests,
# clear of its root.
if not flat_offset(FLAT_DEPTH + FLAT_AF_TOLERANCE) > SCREW_ROOT_DIA / 2.0:
    raise AssertionError("a deep set-screw flat cuts into the thread's root")
# The shallowest still seats the set screw's cup point across the flat.
if not flat_chord(FLAT_DEPTH - FLAT_AF_TOLERANCE) >= SET_SCREW_POINT_DIA:
    raise AssertionError("a shallow set-screw flat is narrower than the cup point")
# A flat off station by its band, and short by its length's band, still runs
# past the set screw both sides: the far side takes both bands.
if not (
    FLAT_LENGTH / 2.0 - FLAT_TOLERANCE - FLAT_LENGTH_TOLERANCE
    >= HANDWHEEL_SET_SCREW_MAJOR / 2.0
):
    raise AssertionError("a flat off station leaves the set screw on the thread")
# A KP08's two flats, both at their deepest and the angle at its band, keep a
# full round between them.
if not 2.0 * flat_half_angle_deg(FLAT_DEPTH + FLAT_AF_TOLERANCE) < (
    KP08_SET_SCREW_SPACING_DEG - CLOCK_TOLERANCE_DEG
):
    raise AssertionError("a KP08's two set-screw flats run into each other")
if set(FLAT_HOUSINGS) != set(FLAT_STATIONS) or not set(CLOCKED_FLATS) < set(
    FLAT_STATIONS
):
    raise AssertionError(
        "every flat station needs its housing; the clock flats a station"
    )
for _name, _start in FLAT_STARTS.items():
    _end = _start + FLAT_LENGTH
    # Clear of the end breaks, inside the screw.
    if not (END_CHAMFER < _start and _end < LENGTH - END_CHAMFER):
        raise AssertionError(f"the {_name} flat runs onto an end of the screw")
    # Under its KP08 block, or inside the handwheel's hub, at its bands.
    _housing = tuple(s - feed.SCREW_NEAR_END_S for s in FLAT_HOUSINGS[_name])
    if not (
        _housing[0] <= _start - FLAT_TOLERANCE
        and _end + FLAT_TOLERANCE + FLAT_LENGTH_TOLERANCE <= _housing[1]
    ):
        raise AssertionError(f"the {_name} flat leaves its housing")
