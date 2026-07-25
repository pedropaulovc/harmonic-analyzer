---
name: upper-frame-reanchor
description: 2026-07-24 adoption of the ch30 upper-frame stations — the three rigid shift groups everything downstream falls into, why the summing group moves LESS than the frame, and the channel-spring stretch it leaves flagged
metadata:
  type: project
---

**2026-07-24 (branch `top-frame/webbed-rederive`, PR #414):** the top frame was
rederived as a webbed SINGLE casting (cross rib + gooseneck socket cast in;
`top-crossbar` and `gooseneck-clamp` deleted as parts) and the ch30 GT stations
the 2026-07-02 pass had left as a FLAG were adopted: columns (±203.8, ±117.5),
top face 1074.6, superseding (±197, ±112)/1040.7. Stations live in
`cad/config/machine/frame.yaml`; every consumer reads them through
`cad/scripts/frame_anchors.py` — see [[buildgraph-literal-dag-edges]] for why the
indirection is load-bearing and not just tidiness.

**The cascade is THREE rigid groups, not one global shift.** Getting this wrong
is the whole trap — each group has a different anchor face:

- **+33.9, the frame TOP face** — the top-lever bank (fulcrum 1099.8 = top +
  BALL_RISE 25.2), ball mounts, fulcrum shaft, amplitude bars (their feet are
  base-anchored on the rocker arms, so the BAR grew 812.8 → 846.7 rather than
  moving), tube columns.
- **+23.35, the cross-rib UNDERSIDE** — the whole summing group: knife line,
  summing lever + its coplanar plate, boss hook, counter spring, gooseneck, and
  the magnifying lever rod that EXTENDS FROM the summing bar (so the clamp,
  vertical rod, fixture and bracket ride with it).
- **−5.5 forward, the FRONT columns** — the whole output line: wheel bar,
  magnifying wheel, both amplification wires, the platen (already derived from
  the column chain) and the pen line that writes on it. Internal geometry is
  untouched; it is one rigid translation.

**Why the summing group moves 10.55 less than the bank it hangs beside:** the
old separate `top-crossbar` was placed at y 1010 — its top 1051, i.e. **10.3
PROUD** of the old ring band 999.7…1040.7. As an integral, flush-topped,
full-depth rib its underside is now the rail underside. So relative to the frame
top the knife dropped 10.3, and the 20 channel springs — top eye on the bank,
bottom eye on the plate — swallow it: installed body 61.98 → **72.53** against a
ch17 free body of 32 (2.27×, up from an already-high 1.94×). **Left as a flagged
consequence, not silently absorbed**: both ends are anchored to measured
geometry, so shortening the knife mount to preserve the old stretch would have
been fabricating evidence. Flagged in `dimensions.yaml`; the free length or the
rib depth is the thing to revisit.

**The knife drop is no longer a bare 20.** At exactly 20 the magnifying clamp's
backed-out thumb-screw head (rod + 3 + 12 + 5) landed EXACTLY on the rail
underside — a 0.00 graze the interference gate reads as a sliver
([[solidworks-modeling-pitfalls]]). The drop is 20.25 and
`build_magnifier_assembly` asserts the clearance, so the constraint is stated
rather than rediscovered. The head cannot escape in Z instead: the ch30 p.4
depth re-anchor puts the whole output line at the machine front, under the rail.

**Two fossils the pass exposed** (both the same failure — a derived value
restated as a literal, then left behind by a re-anchor): the channel solve read
the amplitude bar's top-pin station from a hardcoded `806.45` instead of the bar
length, so the lever tilt silently solved to −14.7°; and `knife_mount_spec`
restated `BLK_TOP`. Both are now derived. When a re-anchor lands, grep for the
OLD value, not just the constant name.
