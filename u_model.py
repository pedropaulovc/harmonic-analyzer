"""Upright U comb: lean bound and bonded phase with the spec's windows.

The U's two T030 blades sit in opposite tooth spaces 2R apart; its span is
cut at the title block (+/-.005) over T030's root-diameter range, so the U
slides across by up to G: the near blade lifts g1 off its seat, the far one
sits g2 off its root, g1 + g2 <= G. The U then turns (phi) only as far as both
blades' windows allow: |phi| <= (w1 + w2) / (4 R).
"""

from __future__ import annotations

import math
import sys

sys.path.insert(0, "cad/scripts")
import dt_cone_gear_tl_phasing_comb_spec as s  # noqa: E402

R30 = 30
roots = [s.root_radius_mm(R30, c) for c in range(len(s._profiles(R30)))]
SPAN_BAND = s._XXX  # title-block .XXX on the U's span
G_MAX = 2 * SPAN_BAND + 2 * (max(roots) - min(roots))


def slide_width(corner: int, sheet: float, lift: float) -> tuple[float, float, float]:
    """(edge at mid of slide, least mid, greatest mid) of a T030 blade lifted
    ``lift`` off its root (bound blades lift on their own)."""
    root = s.root_radius_mm(R30, corner) * (1 + 1e-7)

    def edge_of(mid: float) -> float:
        return math.sqrt(root * root - (mid - sheet / 2) ** 2) + lift

    try:
        least, greatest = s._slide_mm(corner, sheet, edge_of)
    except AssertionError:
        return math.nan, math.nan, math.nan
    if least > greatest:
        return math.nan, math.nan, math.nan
    mid = (least + greatest) / 2
    return edge_of(mid), least, greatest


def lifted_seats(g1: float):
    """(edge, mid, sheet) seat conditions with the near blade lifted g1, or
    bound (whichever is higher)."""
    out = []
    for corner in range(len(s._profiles(R30))):
        for sheet in s.SHEET_LIMITS_MM:
            for edge, mid in s._seat(corner, sheet):
                out.append((edge + g1, mid, sheet))
    return out


def window_width(g: float) -> float:
    widths = []
    for corner in range(len(s._profiles(R30))):
        for sheet in s.SHEET_LIMITS_MM:
            _e, least, greatest = slide_width(corner, sheet, g)
            if not math.isnan(least):
                widths.append(greatest - least)
    return max(widths)


def phase(teeth: int, seats, lean: float) -> tuple[float, int]:
    worst, fails = 0.0, 0
    depth = s.BLADE_DEPTH_MM[teeth]
    for edge, mid, sheet in seats:
        for corner in range(len(s._profiles(teeth))):
            for band in (-s._XXX, s._XXX):
                for drift in (-s.BOND_FLOAT_MM, s.BOND_FLOAT_MM):
                    for sign in (-1, 1):
                        e = edge - depth + band + drift + depth * (1 - math.cos(lean))
                        m = mid + sign * depth * math.sin(lean)
                        try:
                            low, high = s._window(teeth, corner, e, m, sheet / math.cos(lean))
                        except ValueError:
                            fails += 1
                            continue
                        if high <= low:
                            fails += 1
                            continue
                        worst = max(worst, high, -low)
    return worst * s.pitch_radius_mm(teeth), fails


R = sum(s.SEAT_EDGE_MM) / 2
print(f"T030 root radius {min(roots):.3f}-{max(roots):.3f}; U span band +/-{SPAN_BAND:.3f}; G max {G_MAX:.3f} mm")
results = []
for g1 in (0.0, G_MAX / 2, G_MAX):
    g2 = G_MAX - g1
    w1, w2 = window_width(g1), window_width(g2)
    lean = (w1 + w2) / (4 * R)
    seats = lifted_seats(g1)
    row = {t: phase(t, seats, lean) for t in s.BONDED_TEETH}
    results.append((g1, g2, w1, w2, math.degrees(lean), row))
    print(
        f"near lift {g1:.2f} far gap {g2:.2f}: windows {w1:.3f}/{w2:.3f} mm, lean <= {math.degrees(lean):.2f} deg; "
        + ", ".join(f"T{t:03d} {v:.3f} ({f} fail)" for t, (v, f) in row.items())
    )
# The U clamped (G = 0, both blades on their roots or bound).
w = window_width(0.0)
lean0 = 2 * w / (4 * R)
row0 = {t: phase(t, lifted_seats(0.0), lean0) for t in s.BONDED_TEETH}
print(f"clamped U: lean <= {math.degrees(lean0):.2f} deg; " + ", ".join(f"T{t:03d} {v:.3f}" for t, (v, _f) in row0.items()))
