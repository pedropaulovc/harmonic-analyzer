# Top-frame rederive (2026-08-02, PR #459)

The top frame is now ONE webbed casting (`build_top_frame.py`), photo-measured,
absorbing the old separate top-crossbar (MHA-076) and gooseneck-clamp (MHA-033)
— both deleted.

## Measurement method (reusable)

- Scale each ch30 elevation by its own COLUMN PITCH (394 in x / 224 in z), not
  the base: this bakes the GT global stretch (columns solved ±203.8/±117.5 vs
  model ±197/±112) into a proportional rescale onto the model grid. Under it,
  GT's "top 1074.6" collapses to ≈ the old 1040.7 — which turned out to be the
  BOSS top: the GT corner clicks land on the corner-BOSS extremes (±223.1),
  not the rail faces (±214.1).
- Green-mask px measurement TRAP: glossy paint throws a full-height specular
  stripe on cylindrical bosses that fails the green mask and fakes a gap in
  the silhouette — the boss edges read as separate patches. Read extremes from
  BOTH edges and reconcile with GT before believing a width.
- img03/img01 (ch19 "side" elevations) are actually front/back elevations
  (gooseneck outside the right column, pen rod dead-centre) — anchor on 394,
  not 224.

## Resulting geometry (machine coords)

Rail band y 999.7..1036.2 (H 36.5; insert mid 1017.95); side rails 34.2 wide
(faces x ±214.1/±179.9), front/rear 38.0 (z ±131/±93); bosses Ø52.2 proud
+4.5/−6.3 (993.4..1040.7); webbed panels 3.5 deep between 8-tall flanges on
BOTH faces of every rail; integral flush crossbar x −26..−4 with 18×18 plan
gussets + 2× Ø13.49 hanger-stud holes at z 3.088±87.06; gooseneck hub on the
EAST rail (−X = crank side; +X is WEST — the codebase convention) with rib 27,
Ø17 bore, underside boss Ø30×8 + V-gussets, 1/4-20 square-head set screw
(book p.45); 4× #10-24 side-screw taps in the boss z-faces (Ø9×0.9
spot-faces); 2× #10-24 keeper taps in the west rail top face.

## Cascades (all landed together)

- Summing chain −10.30 (knife seat = casting underside 999.7; KNIFE_Y 979.7).
- Fulcrum chain −4.50 (rail top 1036.2, fulcrum 1061.4); amplitude bars
  shortened 4.5 at the top; channel springs stretched +5.8 (top −4.5, bottom
  −10.3); counter-spring +10.3; magnifier −10.3 with the depth window
  re-solved by shortening the thumb-screw 12→11 (head 1.0 below 999.7 kills
  the z-window constraint; lever-wire SHRINKS ~9.9 — the hook drops toward
  the fixed wheel).
- tube-frame 989.9→1014.0 with integral dome caps (stubs +28.6 above the rail
  top per photos; NO nut — plain pressed turned caps, user-ruled).
- New fasteners: frame-side-screw MHA-117 (×6: 4 boss + 2 keeper feet),
  gooseneck-set-screw MHA-118, knife-hanger-stud MHA-119 (1/2-13 hex stack per
  top.png stud crops), fulcrum-keeper MHA-120.
- The "amplitude comb" seen in top.png is NOT a comb: it is the top-lever
  bank on the fulcrum shaft; the end brackets are the keepers (ch17 p.40
  clevis+ball = shaft END mount). The lever-pair pivot-ball-mounts were
  photo-refuted and replaced (pivot-ball-mount is rocker-only, qty 2).

Evidence artefacts (untracked): tmp_measure/ (crops, annotated overlays,
design SVG). Ø48-boss/22-wide-rail/41-tall band + floating crossbar +
clamp-block are all RETIRED reads — don't resurrect them from old prose.
