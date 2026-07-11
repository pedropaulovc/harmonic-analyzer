---
name: fastener-policy-us-customary
description: Fastener/thread policy — US-customary ANSI inch (UNC) everywhere; period-accurate BSW research is deliberately IGNORED; best-fit sizing when undefined
metadata:
  type: project
---

Fastener policy (Pedro, 2026-07-11, the Hole Wizard PR): every threaded hole
and screw in the model uses **US-customary ANSI inch (UNC) sizes** — whatever
is closest to Michelson's period-accurate hardware — and every hole-like cut
becomes a native **Hole Wizard** feature (`swFmHoleWzd`, ANSI Inch standard) so
the model carries real thread designations.

**Why:** the physical build ([[physical-build-intent]]) will be machined in the
US with off-the-shelf taps/dies; period BSW (Whitworth) taps are exotic. The
researched period parameters in
`research/3-detailed-design/period-accurate-fastener-parameters.md` are
**deliberately ignored** for the CAD (kept only as historical reference) — do
not "fix" hole sizes back toward BSW.

**How to apply:**
- Nearest-UNC mappings: 1/4 BSW 20TPI → **1/4-20 UNC**; 3/16 BSW → **#10-24
  UNC**; 1/8 BSW → **#5-40 UNC**; the support hold-down lag screws stay
  **9/16-12** (UNC coarse pitch at 9/16 is 12 — already US-customary).
- Thread class **2B** for tapped holes unless a fit reason says otherwise.
- When a size is undefined by the sources, pick the best fit for purpose
  (shank clearance, plate thickness, head recess) from stock UNC / ANSI
  number-drill sizes rather than inventing a diameter.
- Screw parts' cosmetic threads switch from `ansi_metric` to `ansi_inch`
  UNC tokens so hole and screw designations agree.
- A screw that THREADS INTO a tapped hole models its shank at the thread's
  **tap-drill − ~0.3 mm** (lag precedent Ø12.0 in Ø12.304; #8-32 → 3.15,
  #4-40 → 2.0, #6-32 → 2.4, #3-48 → 1.7), so interference gates pass while
  the designations stay real.
- **Precision-fit exception (do NOT wizard these):** engineered running/slip/
  reamed fits stay plain dimensioned cuts — the crank-arm 3/8 reamed shaft
  journal, fulcrum/pivot bearing bores (Ø6.5), the connecting-rod cam strap,
  the magnifying-clamp lever/rod bores, the output-fixture rod slip bore.
  Wizard drills are for DRILLED holes (fasteners, pins, seats); forcing a
  0.2 mm engineered clearance to the nearest stock drill adds 0.5-0.95 mm of
  slop a machinist would never accept ([[hole-wizard-com-recipe]]).
- A blind seat's 118° drill point reaches depth + 0.30·dia beyond the
  shoulder — check it against the remaining web (the platen socket at 3.5
  pierced its 4.0 plate; 3.2 keeps 0.12 web).
