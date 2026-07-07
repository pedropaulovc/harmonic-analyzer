# Paper-drive rework — reference findings + design (2026-07-07)

User-reported issues (8) audited against book ch22/ch23, videos 2/4 + 4/4, ch30
8-views, and the v4 transgear keyframes. This file is the working design doc for
the rework branch; the durable rows land in `cad/config/dimensions.yaml` when
implemented.

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
**DP 38** (m 0.6684): PD 8.021 / 80.211, OD 9.36 / 81.55, c2c 44.116 (+0.3
backlash = 44.42). Pitch-ratio cross-check on ch30 p002: rack pitch / disc
pitch ≈ 1.27 measured vs 2.660/2.101 = 1.266 for DP38 ✓ (DP30 disc would give
1.0 — refuted). The 5th pinion is DP 30 (must match the rack): PD 10.160,
face ~9.5 long (it bridges from behind the disc plane to the rack plane —
p.62/p.58 show the long-toothed wide pinion).

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
- Anchors (pre-mirror machine coords): rack teeth-down at the platen bottom
  edge, pitch line y ≈ 304.25 → stud (12.0, 304.25 − 5.080 − 0.3 = 298.87);
  knob shaft = stud + 44.42 @ ≈ −18° → ≈ (54.2, 285.1); crank T12 unchanged
  (122.8, 144.96); chain plane z −155 unchanged. (Photo cross-check ch30 p002:
  stud ≈ (+12, ~292-299), knob ≈ (+55..58, ~279-287) ✓ within parallax.)

## Mate chain (issue 8, target state)
crank T12 —(belt/chain feature, pitch Ø 24:48)→ knob T24 —(LOCK: keyed
shaft)→ 12T third gear —(GEAR mate 12:120, external, reversing)→ 120T disc
—(LOCK: drive pins)→ 12T DP30 feed pinion —(RACK-PINION mate, π·10.160 per
rev)→ rack —(LOCK)→ platen. One free operational DOF: crank spin (deferred
park unchanged). Net feed: 1 crank rev (T12/T24 mounted) = 0.5 knob rev →
0.5·(12/120)·π·10.160 = 1.596 mm platen travel.

## Part changes
| part | change |
|---|---|
| support-bar | 10×10×384 → 22 tall × 9 deep × 452 (ends x ±226) |
| column-clamp | one-piece collar+channel → FRONT semi-arc w/ 2 ear thru-holes |
| column-clamp-back (NEW) | BACK semi-arc, 2 threaded ear sockets |
| pinion-bar | RETIRED (bar + bracket replace it) |
| transgear-bracket (NEW) | plate on bar back, 2 screws, stud bore below bar |
| rack-pinion | 96T DP30 → 120T **DP38** disc (renamed role: fixed reducer) |
| transgear-pinion | 24T DP30 → 12T DP38 (third gear) |
| transgear-feed-pinion (NEW) | 12T DP30, face 9.5 (fifth gear, meshes rack) |
| transgear-latch | c2c 66.05 → 44.42 (swing arm, engaged) |
| transgear-stub | shaft shortened/re-banded for bracket→disc reach |
| transgear-knob-shaft | shortened (≈ z −158..−123 span) |
| transgear-removable | face width 5.0 → 2.4 |
| chain links (_chain_link/_chain) | widths per E6 |
| platen | +10 Ø3 guide thru-holes; clip sockets moved to edge/top positions |
| platen-clip | brass color (was PANEL_BLACK); edge positions y [320,445] |
| platen-guide (NEW) | 300×5×4 strip, 5 holes — ×2 (top/bottom) |
| guide-lock (NEW) | ~22×12×2 plate, 2 holes — ×4 |
| platen-rack | re-anchored: band [305,~316], teeth at platen bottom edge |

Assembly: single bar y-centre ≈ 345.4 (front face −138.9), clamps ±197,
platen hangs via guides/locks (slide DOF unchanged), all platen-riding
fasteners lock-mated, transgear cluster per E8, chain loop re-solved for the
new knob centre, verify:kinematics probe re-targeted to the real gear-mate
train (1.596 mm/crank-rev).
