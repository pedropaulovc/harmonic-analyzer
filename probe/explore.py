"""Fast analytic exploration of the pinion linkage (mirrors build_drive_train_assembly
formulas for the park gap, engage swing, cam contact root, reach and strap/collar air).
Candidates found here are then confirmed by the full-module probe.
"""

import math
import sys

# fixed anchors from the integrated scratch head (S1 probe)
AX, AY = -18.626440352466744, 90.518  # pinion axis (parked)
PX, PY = -14.662543784694092, 62.8  # pivot
XD = None
C2C = 28.0
LEAN = math.atan2(PX - AX, AY - PY)
FPIN_DIA = 4.016
PIN_SEAT = 4.0
PIN_LEN = 17.0
R_END = 7.5
Y_BASE = 50.8
SPRING_FOOT_TOP = 51.6
PHI = math.radians(6.314163285085329)  # engage swing (depends only on pivot/drum/C2C)

U = (math.sin(-LEAN), math.cos(-LEAN))  # up the strap axis (module _SPR_U)
N = (-math.cos(-LEAN), math.sin(-LEAN))  # module _SPR_N


def rot(p, b, c=(PX, PY)):
    x, y = p[0] - c[0], p[1] - c[1]
    return (c[0] + x * math.cos(b) - y * math.sin(b), c[1] + x * math.sin(b) + y * math.cos(b))


def evaluate(h, H, od, ecc, drop, gap_target=0.15, air_min=None):
    lx = PX + 2 * h
    ly = PY + H
    rc = od / 2
    fc = (PX - drop * U[0], PY - drop * U[1])  # drop negative = above

    def pin_d(cc, b):
        c = rot(fc, b)
        n = rot((N[0] + PX, N[1] + PY), b)
        n = (n[0] - PX, n[1] - PY)
        dx, dy = cc[0] - c[0], cc[1] - c[1]
        return abs(dx * (-n[1]) - dy * (-n[0]))

    def cam(a):
        return (lx + ecc * math.sin(a), ly - ecc * math.cos(a))

    park = pin_d(cam(0), 0) - (FPIN_DIA + od) / 2
    eng = lambda a: pin_d(cam(math.radians(a)), PHI) - (FPIN_DIA + od) / 2  # noqa: E731
    lo, hi = -180.0, 0.0
    if not eng(lo) < 0 < eng(hi):
        return None
    for _ in range(60):
        m = (lo + hi) / 2
        if eng(m) > 0:
            hi = m
        else:
            lo = m
    rot_deg = (lo + hi) / 2
    reach = (FPIN_DIA + od) / 2 - pin_d((lx, ly + ecc), PHI)
    s0 = R_END - PIN_SEAT
    tip = s0 + PIN_LEN
    fce = rot(fc, PHI)
    ne = rot((N[0] + PX, N[1] + PY), PHI)
    ne = (ne[0] - PX, ne[1] - PY)
    s_eng = (fce[0] - lx) / ne[0]
    s_park = (fc[0] - lx) / N[0]

    def seg(p, s0_, s1_):
        dx, dy = s1_[0] - s0_[0], s1_[1] - s0_[1]
        t = max(0.0, min(1.0, ((p[0] - s0_[0]) * dx + (p[1] - s0_[1]) * dy) / (dx * dx + dy * dy)))
        return math.hypot(p[0] - s0_[0] - t * dx, p[1] - s0_[1] - t * dy)

    # path: strap parked until pin touch, then follows contact
    def pin_gap(a, b):
        return pin_d(cam(a), b) - (FPIN_DIA + od) / 2

    ae = math.radians(rot_deg)
    amin = 99.0
    for i in range(401):
        a = ae * i / 400
        if pin_gap(a, 0) > 0:
            b = 0.0
        else:
            blo, bhi = 0.0, PHI * 1.5
            for _ in range(50):
                bm = (blo + bhi) / 2
                if pin_gap(a, bm) < 0:
                    blo = bm
                else:
                    bhi = bm
            b = (blo + bhi) / 2
        amin = min(amin, seg(cam(a), (PX, PY), rot((AX, AY), b)) - R_END - rc)
    k = od / 2 - ecc
    return dict(
        h=h, H=round(H, 4), od=od, ecc=ecc, drop=drop, park_gap=round(park, 4), rot=round(rot_deg, 2),
        lever=round(10 + rot_deg, 2), reach=round(reach, 3), air_min=round(amin, 3),
        wall_nom=round(k - 6.37 / 2, 3), wall_w05=round(k - 0.025 - 0.05 - 6.375 / 2, 3),
        base=round(ly - (ecc + rc) - Y_BASE, 3), foot=round(ly - (ecc + rc) - SPRING_FOOT_TOP, 3),
        pivshaft=round(math.hypot(2 * h, H) - (ecc + rc) - 3.175, 3), tipres=round(tip - s_eng, 3), s_park=round(s_park, 2),
    )


def solve_H(h, od, ecc, drop, gap=0.15):
    lo, hi = -6.0, 8.0
    for _ in range(60):
        m = (lo + hi) / 2
        r = evaluate(h, m, od, ecc, drop)
        # park gap falls as H rises (collar climbs toward the pin)
        g = r["park_gap"] if r else None
        if g is None:
            hi = m
            continue
        if g > gap:
            lo = m
        else:
            hi = m
    return (lo + hi) / 2


if __name__ == "__main__":
    # sanity: baseline
    print("baseline", evaluate(6.25, 1.8561911789147132, 10.32, 1.4, -6.0))
    print("rf", evaluate(6.25, 0.756, 12.52, 1.4, -6.0))
    for drop in (-6.0, -6.5, -7.0):
        for ecc in (1.0, 1.1, 1.2, 1.3, 1.4):
            for k in (5.3,):
                od = round(2 * (k + ecc), 2)
                for h in (7.5, 8.0, 8.25, 8.5, 9.0):
                    H = solve_H(h, od, ecc, drop)
                    r = evaluate(h, H, od, ecc, drop)
                    print(r)
