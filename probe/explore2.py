import math
from explore import *
import explore as X

def park_gap(h, H, od, ecc, drop):
    lx, ly = PX + 2*h, PY + H
    fc = (PX - drop*U[0], PY - drop*U[1])
    dx, dy = lx - fc[0], (ly - ecc) - fc[1]
    return abs(dx*(-N[1]) - dy*(-N[0])) - (FPIN_DIA + od)/2

def solve_H(h, od, ecc, drop, gap=0.15):
    lo, hi = -8.0, 10.0
    for _ in range(80):
        m = (lo+hi)/2
        if park_gap(h, m, od, ecc, drop) > gap: lo = m
        else: hi = m
    return (lo+hi)/2

def solve_E(h, drop, K, target_rot=-80.0, pin_len=17.0):
    X.PIN_LEN = pin_len
    lo, hi = 0.8, 3.5
    best = None
    for _ in range(40):
        e = (lo+hi)/2
        od = 2*(K+e)
        H = solve_H(h, od, e, drop)
        r = evaluate(h, H, od, e, drop)
        if r is None:  # cannot reach: need more ecc
            lo = e; continue
        best = r
        if r['rot'] < target_rot: lo = e   # too much rotation -> more ecc
        else: hi = e
    return best

if __name__ == '__main__':
    import sys
    K = 5.3
    for drop in (-6.0, -6.5, -7.0):
        for h in (7.5, 8.0, 8.5, 9.0, 9.5):
            r = solve_E(h, drop, K, -80.0, 20.0)
            print({k: (round(v,3) if isinstance(v,float) else v) for k,v in r.items()})
