r"""Triangulate the ch30 GT rocker-arm corners (vertical-rod evidence).

Reuses the solved cameras from ``triangulate_ch30_gt`` and ray-intersects the
``rocker_arm_corner_*`` GT clusters (left/right x butt/tip; "left/right" are
machine-left/right as seen facing the FRONT, so each names one END of the
seesaw strap). Findings that drove the 2026-07-02 vertical-rod re-anchor
(`ROD_HOLE_X` 25.4 -> 127.49 -> 127.37, `ROD_C2C` 180.83 -> 144.75 -> 147.67;
the last step is the same-day ch14 ROM re-derive that levelled the rest pose):

* rod-side end (butt_right/tip_right) lands at machine (-60, 253) -- directly
  OVER the cam drum (-54.7); the arm's bottom-arc end at the LEVEL rest pose
  predicts -59.9;
* far end (butt_left) lands at (+216, 247);
* midpoint of the span = +72.5 = the frame's rocker pivot (+72.9): the pivot
  is the seesaw mid-span and the rod hangs PLUMB from the rod-side tip.

Residuals are 15-160 px because each view annotates a DIFFERENT arm of the
fan (the 20 arms tilt independently); the rod-side end barely fans (all rod
pins ride the same cam line), so its x/y are trustworthy; the far ends fan
hard, so treat their y with suspicion.

Run (SolidWorks-free; ~2 min for the camera solve)::

    uv run python cad\scripts\diagnostics\triangulate_ch30_rocker.py
"""
from __future__ import annotations

import json
import math

import numpy as np

from triangulate_ch30_gt import GT_DIR, VIEWS, Problem, cam_rotation, project


def ray(cams, f, view: str, u: float, v: float):
    cam = cams[view]
    size, _, _, grp = VIEWS[view]
    fv = f[grp]
    R = cam_rotation(cam[3], cam[4], cam[5])
    d = np.array([(u - size[0] / 2.0 - cam[6]) / fv,
                  -(v - size[1] / 2.0 - cam[7]) / fv,
                  1.0])
    dw = R.T @ d
    return cam[:3].copy(), dw / np.linalg.norm(dw)


def triangulate(rays):
    A = np.zeros((3, 3))
    b = np.zeros(3)
    for C, d in rays:
        P = np.eye(3) - np.outer(d, d)
        A += P
        b += P @ C
    return np.linalg.solve(A, b)


def main() -> int:
    prob = Problem()
    x = prob.solve()
    cams, f, _top, _col, _feats = prob.unpack(x)

    obs: dict[str, list[tuple[str, float, float]]] = {}
    for path in sorted(GT_DIR.glob("page*.json")):
        view = path.stem
        for p in json.loads(path.read_text())["points"]:
            name = p["feature"]
            if name.startswith("rocker_arm_corner_"):
                obs.setdefault(name.removeprefix("rocker_arm_corner_"), []).append(
                    (view, p["x"], p["y"])
                )

    print("triangulated rocker corner clusters (machine world mm):")
    ends = {}
    for key, lst in sorted(obs.items()):
        if len(lst) < 2:
            print(f"  {key:12s}: only {len(lst)} view(s) -- skipped")
            continue
        P = triangulate([ray(cams, f, v, u, w) for v, u, w in lst])
        ends[key] = P
        errs = []
        for v, u, w in lst:
            size, _, _, grp = VIEWS[v]
            uv = project(cams[v], f[grp], size, P)[0]
            errs.append(math.hypot(uv[0] - u, uv[1] - w))
        err_s = ", ".join(f"{v.removeprefix('page').removesuffix('_img01')}:{e:.0f}px"
                          for (v, _, _), e in zip(lst, errs))
        print(f"  {key:12s}: ({P[0]:8.2f}, {P[1]:8.2f}, {P[2]:8.2f})   {err_s}")

    if "butt_right" in ends and "butt_left" in ends:
        mid = (ends["butt_right"][0] + ends["butt_left"][0]) / 2.0
        print(f"\nseesaw x-span midpoint = {mid:+.2f}  (frame rocker pivot +72.9)")
        print(f"rod-side end x = {ends['butt_right'][0]:+.2f}  (cam drum -54.7; "
              f"arm bottom-arc end at the level rest pose predicts -59.9)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
