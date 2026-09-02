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
