---
name: paper-drive-rework
description: Full evidence dossier (E1-E8) + part-change table behind the PR #196 paper-drive rework — backs [[paper-drive-real-train]]
metadata:
  type: project
---

# Paper-drive rework — reference findings + design (2026-07-07)

User-reported issues (8) audited against book ch22/ch23, videos 2/4 + 4/4, ch30
8-views, and the v4 transgear keyframes. This is the evidence dossier for the
PR #196 rework branch (durable rows live in `cad/config/dimensions.yaml`; the
distilled rules in [[paper-drive-real-train]]).

## Evidence summary

### E1 — ONE support bar (not two, not three)
- Book p.62 caption: "The rectangular bar that goes from the top left corner of
  the image to the right side is **the bar that the platen rides on**" (singular).
- ch30 p002 (front): a single bar at the platen's lower-back band, ending PAST
  each column (~28 mm) with two screw heads flanking each column.
- The same p.62 top-down photo shows the transgear cluster mounted on a bracket
  screwed to the BACK of this same bar (2 large slotted screws, also visible in
  the p.63 back view) — the model's separate `pinion-bar` and both `support-bar`
  rails collapse into ONE bar + bracket.
- Bar cross-section from the ch22 back-side wear band + front view: ~22 tall ×
  ~9 deep; front face rubs the platen back (bright brass wear band).

### E2 — column clamp = two semi-arc shells + 2 screws each
- ch30 p005 quarter view (left column): a BLACK two-piece collar wraps the
  column; ears flank the column; screws close the arcs.
- ch30 p002 front view: the 2 screw heads per clamp show on the BAR's front
  face, flanking the column → screw stack = bar → front arc ear → back arc ear
  (threaded). Bar is clamped between the front arc and the column line.
- Replaces the one-piece channel collar + backed-out pinch screws (M6.10).

### E3 — platen back: guides + locks (the platen HANGS on the bar)
- ch22 p54-55 back-side photo: two black guide rails run the FULL width of the
  platen back — one above, one below a bright brass WEAR BAND (~24-28 mm tall)
  where the bar slides. 4 black lock plates (2 screws each): 2 on the top
  guide, 2 on the bottom guide, bridging behind the bar so the platen cannot
  fall off.
- ch22 front photo: two horizontal rows of 5 slotted screws = the through-plate
  fastenings of the two guides (heads on the platen FRONT face).
- Vertical stack on the platen back (machine y, platen 305..445):
  top guide ≈ [349.5, 354.5]; bar channel ≈ [321, 349.5]; bottom guide ≈
  [315.5, 321]; rack band ≈ [305, 315.5] with teeth protruding just below the
  platen bottom edge (~2 mm).

### E4 — paper clips hug the left/right EDGES from the TOP edge down
- ch22 front photo: two bright BRASS strips at the extreme left/right edges,
  running from the top edge down ~125 mm (≈2/3 of the height), screws through
  end holes. Current model: strips are (a) colored PANEL_BLACK → invisible on
  the black platen ("missing clips"), (b) inboard and starting at y 312.

### E5 — fillister screws float because they are grounded
- The 4 clip screws are `place_component(..., ground=True)` at absolute
  coordinates while the platen (+ lock-mated clips) is feed-coupled → the
  screws stay behind in space. All platen-riding fasteners must be lock-mated
  to the platen group.

### E6 — chain vs sprocket widths are physically impossible (whitelisted)
- Model: sprocket (transgear-removable) tooth face 5.0 wide; chain inner-link
  clear gap 0.4; whole link only 4.2 over the pins. The tooth cannot pass
  between the plates; `check_no_interference` whitelists exactly this.
- Photos (ch23 p58-59, p002_img01): the chain plates STRADDLE a thin gear
  (~2.5 mm) — chain wider than the wheel.
- Fix: removable face width 5.0 → 2.4; chain inner clear 0.4 → 2.9 (inner
  plate inner faces ±1.45), bushing width 2.9, outer plates at faces
  2.25..3.05, pin length 6.4. Roller Ø2.5 unchanged (sits in the ~3.1 m2 tooth
  gap). Plate↔tooth interference disappears; remaining roller↔flank contact is
  the real driving contact (whitelist narrows to that).

### E7 — the six translational gears (video 4/4 narration, authoritative)
1. crank removable chain gear (m2; small 12T / medium 18T / large 24T; machine
   came with FOUR: 1 small, 2 medium, 1 large),
2. knob removable chain gear (chain-connected, belt/chain feature 1:1 per tooth),
3. **12T** pinion on the knob shaft, just behind the removable ("third gear"),
4. **120T** disc ("fourth gear") — tooth count CONFIRMED by FFT ring count on
   ch30 p002 (~115-119 peak) — the model's 96T is refuted,
5. small pinion "behind and attached to the fourth gear" — video says **12T**
   (user reported 10T — video narration kept, discrepancy flagged),
6. the rack (DP 30 — unchanged, pitch 2.660 verified).

Modules: disc OD measures ≈82 (±2.5) @120T → fixed-reduction mesh 12T:120T at
**DP 38** (m 0.6684): PD 8.021 / 80.211, OD 9.36 / 81.55, c2c 44.116 + 0.65
centre extension = **44.766** (the extension clears the `_gear`-recipe gap
floor at the 12T base circle — the recipe cuts gaps only down to rb, so any
<63T pinion needs drive-train-style checker-arbitrated slack). Pitch-ratio
cross-check on ch30 p002: rack pitch / disc pitch ≈ 1.27 measured vs
2.660/2.101 = 1.266 for DP38 ✓ (DP30 disc would give 1.0 — refuted). The 5th
pinion is DP 30 (must match the rack): PD 10.160, face 9.5 (it bridges from
behind the disc plane to the rack plane — p.62/p.58 show the long-toothed
wide pinion); its rack mesh gets the same treatment (axis 0.8 below the
nominal pitch-line offset). Both 12T gears bore Ø5 (a 3/8" bore would breach
the 12T base circles), riding turned-down seats on the stud / knob shaft.

### E8 — topology: the disc does NOT mesh the rack; the cluster tilts to unlatch
- The 120T disc rides IN FRONT of the platen face (z south of the platen
  front); the 5th pinion behind it passes under the platen bottom edge and
  meshes the rack; the 3rd (12T) gear meshes the 120T permanently (p.63 shows
  the mesh engaged; the arm pivots ON the stud so that c2c never changes).
- Unlatching (v4_transgear keyframes 001 vs 011-013): the WHOLE cluster tilts
  away from the rack (5th↔rack opens; platen freed), and the knob arm swings
  about the stud for chain slack / gear swaps. The old "Appendix C #8 riddle"
  (66.05 rest vs 51.0 engaged) dissolves: the measured latch c2c was fitted
  against the wrong (disc-meshes-rack, 24T/96T) topology; the engaged c2c is
  44.42 and never changes.
- Anchors AS IMPLEMENTED (pre-mirror machine coords): rack teeth-down with
  crests at y 303 (2 below the platen bottom edge), pitch line 303.847 →
  stud (12.0, 303.847 − 5.080 − 0.8 = 297.967); knob shaft = stud + 44.766 @
  −18° = (54.575, 284.133); crank T12 unchanged (122.8, 144.96); chain plane
  z −155 unchanged (68-link loop, sag ≈ 21). (Photo cross-check ch30 p002:
  stud ≈ (+12, ~292-299), knob ≈ (+55..58, ~279-287) ✓ within parallax.)
- z stack on the stud (front → back): collar −152.8..−148.8 | disc
  −148.4..−145.4 (the guide-screw heads are counterbored sub-flush, so the
  deepest platen furniture nearby is the paper plane −143.4) | feed
  pinion −145.4..−135.9 (3.0 into the rack band −138.9..−132.9) | latch arm
  −132.75..−130.15 (2.6 thick — it fits the 3.0 slot between the rack back
  and the bar front; its Ø22 big hub rises past the rack's tooth band in y)
  | bracket plate −129.9..−125.9 on the bar back.

## Mate chain (issue 8, AS BUILT)
crank T12 —(belt/chain feature, pitch Ø 24:48)→ knob T24 —(LOCK: keyed
shaft)→ 12T third gear —(GEAR mate 12:120, external, reversing)→ 120T disc
—(LOCK: drive pins)→ 12T DP30 feed pinion —(RACK-PINION mate on the rack's
own pitch-line Axis1, π·10.160 per rev, sense pinned by the kinematics
probe's signed feed asserts)→ rack —(LOCK)→ platen. One free operational DOF: crank spin (deferred
park unchanged). Net feed: 1 crank rev (T12/T24 mounted) = 0.5 knob rev →
0.5·(12/120)·π·10.160 = 1.596 mm platen travel
(`NET_RACK_TRAVEL_PER_CRANK_REV`; verified by the kinematics probe).

## Part changes
| part | change (as implemented) |
|---|---|
| support-bar | 10×10×384 → 22 tall × 9 deep × 452 (ends x ±226); 4 Ø4.4 clamp thru-holes + 2 Ø4.0 bracket holes (MACHINE-handed, placed mirror=False) |
| column-clamp-front (NEW) | FRONT semi-arc 17.9 deep, 2 Ø4.4 ear thru-holes (mirror_plane z) |
| column-clamp-back (NEW) | BACK semi-arc 14 deep, 2 Ø4.0 threaded ear holes |
| clamp-screw (NEW) | Ø8×2.5 head, Ø3.9×28 shank — ×4, heads on the bar front |
| pinion-bar | RETIRED (deleted; bar + bracket replace it) |
| transgear-bracket (NEW) | 30×63.5×4 black plate on the bar back, Ø9.6 stud bore, 2 Ø4.4 holes; 1.5-deep front groove (local y 16..24) clears the sliding bottom guide rail |
| bracket-screw (NEW) | Ø8×2.5 head, Ø3.9×12 shank — ×2, heads on the bracket back |
| rack-pinion | 96T DP30 → 120T **DP38** disc, bore Ø5 (role: fixed reducer) |
| transgear-pinion | 24T DP30 → 12T DP38, face 4, bore Ø5 (third gear) |
| transgear-feed-pinion (NEW) | 12T DP30, face 9.5, bore Ø5 (fifth gear, meshes rack) |
| transgear-latch | c2c 66.05 → 44.766; thickness 4.5 → 2.6 (rack-back/bar-front slot) |
| transgear-stub | stepped: Ø9.525×9.1 + Ø5×13.8 seat + Ø14×4 collar |
| transgear-knob-shaft | stepped: Ø9.525×9.1 + Ø5×5.5 seat + Ø9.525×12.9 + knob (z −157.5..−123.5) |
| transgear-removable | face width 5.0 → 2.4 |
| chain links (_chain) | inner plates ±1.45..±2.25, bushings ±1.45, outer ±2.55..±3.35, pins ±3.35 |
| platen | +10 Ø3 guide thru-holes (rows y 13/47) with Ø6.5×2.4 head counterbores (paper lies flat, crowns 0.2 sub-flush); clip sockets → (6/294, 23/132) |
| platen-clip | natural brass (was PANEL_BLACK); edge positions y [320,445] |
| platen-guide (NEW) | 300×5×10 rail (10 deep so the locks clear the 9-deep bar), 4 lock holes + 5 blind Ø3 screw holes on the front face — ×2 |
| guide-lock (NEW) | 22×19×2 plate, 2 Ø3 holes — ×4 (19 tall so the BOTTOM-rail pair, whose rail sits 7 below the bar, still overlaps the bar band by 7; top pair overlaps 14) |
| platen-rack | 30 → 12 tall; teeth-down band y [303,315], crests 2 below the platen edge |

Assembly: single bar y-centre 338.5 (top edge 349.5 carries the hanging
platen's top guide; front face −138.9), clamps ±197, platen CENTRED x ±150
(between the columns — the clamp screw heads protrude past the bar front),
all 22 platen-riding fillisters + rack + clips + guides + locks + paper
lock-mated to the platen, transgear cluster per E8, chain loop re-solved for
the new knob centre (68 links), verify:kinematics probe re-targeted to the
real per-stage mate train (1.596 mm/crank-rev net).
