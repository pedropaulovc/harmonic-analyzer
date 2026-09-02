# Photo re-derive pass 3 -- user review list + evidence (2026-09-02)

> Not a status board (see the GitHub project). Working list for the third
> photo-fidelity pass, from the user's review of the pass-2 model. Source of
> truth for each fix is the build script it names; the ledger rows in
> `cad/config/dimensions.yaml` carry the measured values.

Evidence read this pass (all under `references/`): book ch11 p.14, ch14
p.26-29, ch16 p.34, ch17 p.40, ch18 p.42, ch19 p.44-45, ch22 p.54, ch23
p.58-59, ch25 p.68-70, ch26 p.70 (nameplate + serial); engineerguy video 4/4
transcript ("unlatch this gear system", "unscrew the nut that holds the other
gear") and keyframes `v4_transgear_001..013`.

## Items and what the plates actually show

| # | item (user) | plate read | fix |
|---|---|---|---|
| 1 | spring latch for the transgear | a SHORT CURVED spring-steel hook (~27 x 4.5 x 0.8) hanging from the support bar's front between the pivot ball and the disc (keyframe 001 latched, 011 released) -- not a strip on the bar | `build_latch_hook` replaces `build_latch_strip` |
| 2 | nameplate screws | four brass slotted screws at the plate corners (ch26 p.70); the model had holes and NO screws, and the holes were #2 while the catalog fillister is #4-40 | #4 holes, base taps, 4 fillister screws in frame.SLDASM |
| 3 | serial number stamp | a stamped "2" on the base's machined rim beside the nameplate (ch26 p.70) | DXF numeral cut on the base |
| 4 | transgear knob in front of the removable gear | knurled brass thumbnut Ø26 outermost on the knob shaft (ch23 p.58/59; the video calls it "the nut") | `build_transgear_thumbnut`, shaft front stub |
| 5 | platen paper holder spring | two overlapping slotted brass strips + a round knurled screw at each end (ch22 p.54) | open -- `build_platen_clip` rework |
| 6 | knife mounts: unpainted heat-treated steel | ch18 p.42: bare hardened steel blocks | material + colour + notes |
| 7 | knife mount holes too big | Ø16 bore around a 8.7 x 10.3 hex | bore Ø12 |
| 8 | no bushings between rocker arms; integral hubs | ch14 p.28 `page002_img02`: every arm carries a stepped hub each side | DONE (PR B): O10 x 7.0565 hub on every arm, O12 on every lever; both bushing parts retired; rockers seat PITCH off the previous rocker |
| 9 | pivot brackets L-shaped, base matches the support | ch14 p.27/28; the pass-2 foot (24) overhung the 16.93 apex and its holes fell outside the casting | foot 16 x 24 along Z, ear at the inboard end, Ø16 ball on the ear |
| 10 | measuring stick numerals | 0..10 engraved right of each full tick, ~2 mm (ch16 p.34) | DXF numerals |
| 11 | tube frame too tall above the top frame | ch30 p002: columns end just above the corner bosses | COLUMN_LENGTH 1014 -> 994 |
| 12 | crank handle too stubby | ch11 p.14 / ch30 p002 | 44 -> 58 long, Ø25 -> Ø21 |
| 13 | guide lock too tall | ch22 p.54 | 19 -> 15 |
| 14 | lever bushings do not exist | ch17 p.40: levers stack with their own spacers | DONE (PR B) |
| 15 | gooseneck attaches the spring via an end screw | ch19 p.45 `page001_img02`: slotted screw axially in the arm end, eye on the shank | lug + X-pin -> end screw |
| 16 | stop block | ch16 p.34: square block, knurled thumbscrew UNDERNEATH | `build_measuring_stick_stop` rework |
| 17 | amplitude-bar fan / rocker sinusoidal setup as configurations | ch14 p.28-29 fan; end views at 0/6/14/40 cranks | PR C -- user decision 2026-09-02: DEFAULT = fanned arms + level bars (matches the ch30 eight views); a second config poses the sinusoidal setup (ch14 end views at a chosen crank count); a third keeps today's parallel bank for comparison |

Also seen, not yet listed by the user: the crank taper pin's brass keeper
ring hanging from a screw on the crank arm (ch11 p.14); the transgear stud's
brass collar with a slotted cap (ch23 p.59). The support-bar vs platen
"mismatch" seen while placing the latch hook is NOT a geometry error: the
platen slides vertically with the paper feed, so keyframe `v4_transgear_001`
(platen fed UP, the bar's front exposed below its black band, latch at x ~
+52) and the ch30 p002 plate (platen DOWN, the band hiding the bar) are the
same machine in two feed states; the model matches the ch30 rest state
(checked 2026-09-02 on the p002 photo/render pair: bar top ~15 px under
the paper's bottom edge in both). At rest a hook at +52 would sit behind
the platen, so it stays at LATCH_HOOK_X = -50 where it is visible.

2026-09-02 (pass-3 reread, PR E scoping): the "amplitude-bar foot TABS" item
was a MISREAD. ch15 p.33 page002_img01 shows the bank from the rod (-X) side:
the rusty 6.35 bars are the amplitude bars standing at their pivots, and the
bright blocks hanging below their ends are the CONNECTING-ROD HEADS at the
arm tips, lower where the arm has dipped (the heights trace one 13.3-channel
wave = the 6-crank sinusoid, 360/27 deg). The apparent near/far alternation
of the heads in the 6/14/40-crank end views is KINEMATIC (at 40 cranks the
even harmonics stand at the stroke top and the odd at the bottom); the
0-crank end view (ch14 page002_img08) shows ONE level, evenly spaced row, so
the rod-pin station is NOT staggered. What the end views do fix is the head's
shape: a ~5-wide block with a flat bright top, ~15 tall, thicker than the
2.5 shank -- not the 10-wide x 2.5 tombstone (PR E: rod head reshape; the
arm-to-arm gap of 4.56 bounds the thickness at 2.9 symmetric). The bars'
feet are plain (page001_img02: the notch in the bar itself straddles the arm).

Open after PR #658 (2026-09-02): the ROD HEAD IS A CLEVIS. ch14 page002_img02
zoomed 4x at the arm tips: every rod ends in a bright U-shaped yoke whose two
prongs straddle the arm's tip (pin through prongs + arm), and the arm's top
edge steps DOWN ~2 mm over the last ~6 mm so the prong tops sit flush with
it. The end views' bright square tops are those prongs + the arm between
(~6 wide). PR #658's 5 x 15 block beside the arm is closer than the tombstone
but still not this. Before modelling: the CAD rod plane sits 4.05 off the arm
plane (CAM_DZ -3.25 vs ARM_MID_DZ 0.8, the cam on the gear's far face), so a
clevis centred on the arm needs a cranked shank -- or CAM_DZ re-read from
the ch13 photos. Also the arm tip's top-edge step (rocker_arm_spec outline).
