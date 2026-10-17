# McMaster-Carr vendor models (supplied locally, never tracked)

The `.SLDPRT` files this directory holds at build time are © McMaster-Carr —
vendor CAD downloads for the stock fasteners the machine uses. They are **not
in git** (see the `cad/references/mcmaster/*.SLDPRT` rule in the root
`.gitignore`): McMaster provides them to customers for product evaluation, not
for redistribution in a public repository.

To populate the directory, download each part's SOLIDWORKS model from its
`https://www.mcmaster.com/<part-number>/` product page and save it here as
`<part-number>.SLDPRT`. Sign in if requested.

Parts referenced by the production fastener fleet and its reusable diagnostic
recipes:

| part number | production part stem(s) | stock item |
|---|---|---|
| 3088A429 | `vn-rocker-thrust-washer` (MHA-VN-070; catalogue-only, vendor model refused) | Carbon Steel Round Shim, 1/4" ID x 3/8" OD, 0.031" Thick |
| 3606T118 | `vn-keeper-chain` (catalogue-only; no vendor model) | Bead Chain, Unfinished Brass, Trade Size 3 |
| 3606T811 | `vn-keeper-chain-link` (catalogue-only; no vendor model) | Loop Link for Brass Trade Size 3 Bead Chain |
| 5972K41 | `ch-rocker-arm-tl-oblique-bearing` (MHA-CH-006-TL-32; shop fixture; catalogue-only, vendor model read for dimensions, not replica-gated) | Steel Ball Bearing |
| 6261K108 | `vn-chain-connecting-link` (the loop's one connecting link; catalogue-only, vendor model not downloaded) | Connecting Link for ANSI Number 25 Single Strand Roller Chain |
| 6261K171 | `vn-chain-inner-link`, `vn-chain-outer-link` (cut to length; catalogue-only, vendor model not downloaded) | Roller Chain, Single Strand, ANSI Number 25, 1/4" Pitch |
| 6793K4 | `pd-transgear-removable` T12 (shop-reworked blank) | Steel ANSI #25 Plain-Bore Sprocket, 12 Teeth |
| 6793K11 | `pd-transgear-removable` T18 (shop-reworked blank) | Steel ANSI #25 Plain-Bore Sprocket, 18 Teeth |
| 6793K17 | `pd-transgear-removable` T24 (shop-reworked blank) | Steel ANSI #25 Plain-Bore Sprocket, 24 Teeth |
| 90114A124 | `vn-ms-stop-plate-screw`; `vn-platen-clip-screw` until 2026-10-15 (catalogue-only; no vendor model) | Brass Fillister Head Slotted Screw |
| 90114A511 | `vn-fillister-screw` | Brass Fillister Head Slotted Screw |
| 90126A211 | — (diagnostic recipe; the former `vn-knife-hanger-washer`, retired) | Zinc-Plated Steel SAE Washer |
| 90280A108 | `vn-foot-screw`, `vn-swing-stop-screw`, `vn-latch-hook-bracket-screw` | Steel Narrow Fillister Head Slotted Screw |
| 90280A194 | — (diagnostic recipe; a former `vn-frame-side-screw`) | Steel Narrow Fillister Head Slotted Screw |
| 90280A196 | `vn-bracket-hold-down-screw` | Steel Narrow Fillister Head Slotted Screw |
| 90280A197 | `vn-pedestal-hold-down-screw` | Steel Narrow Fillister Head Slotted Screw |
| 90280A199 | — (diagnostic recipe; a former `vn-swing-stop-screw`) | Steel Narrow Fillister Head Slotted Screw |
| 90280A201 | `vn-clamp-screw` | Steel Narrow Fillister Head Slotted Screw |
| 90280A203 | `vn-slotted-screw` | Steel Narrow Fillister Head Slotted Screw |
| 90280A837 | `vn-frame-cross-screw` | Steel Narrow Fillister Head Slotted Screw |
| 90480A009 | `vn-pen-hanger-nut` (catalogue-only; no vendor model) | Low-Strength Zinc-Plated Steel Hex Nut |
| 90760A009 | `vn-pen-hanger-jam-nut` (catalogue-only; no vendor model) | Zinc-Plated Steel Narrow-Profile Hex Nut |
| 91247A720 | — (diagnostic recipe; a former `vn-knife-hanger-stud`) | Medium-Strength Grade 5 Steel Hex Head Screw |
| 91251A108 | `vn-cone-tip-block-screw` (catalogue-only; no vendor model) | Black-Oxide Alloy Steel Socket Head Screw |
| 91251A157 | — (catalogue-only diagnostic recipe; former `vn-knife-hanger-stud`) | Black-Oxide Alloy Steel Socket Head Screw |
| 91251A188 | `ch-rocker-arm-tl-oblique-block-screw` (MHA-CH-006-TL-43; shop fixture; catalogue-only, CAD login-walled, no vendor model) | Black-Oxide Alloy Steel Socket Head Screw |
| 91251A196 | `ch-rocker-arm-tl-oblique-bracket-screw` (MHA-CH-006-TL-42; shop fixture; catalogue-only, vendor model read for dimensions, not replica-gated) | Socket Head Screw |
| 91251A197 | `ch-rocker-arm-tl-oblique-rail-screw` (MHA-CH-006-TL-41; shop fixture; catalogue-only, vendor model read for dimensions, not replica-gated) | Socket Head Screw |
| 91251A540 | `ch-rocker-arm-tl-oblique-clamp-screw` (MHA-CH-006-TL-48; shop fixture; catalogue-only, vendor model read for dimensions, not replica-gated) | Socket Head Screw |
| 91251A582 | `ch-rocker-arm-tl-oblique-lever-screw` (MHA-CH-006-TL-49; shop fixture; catalogue-only, vendor model read for dimensions, not replica-gated) | Socket Head Screw |
| 91812A215 | `ch-rocker-arm-tl-oblique-block-washer` (MHA-CH-006-TL-50; shop fixture; catalogue-only, product page login-walled, no vendor model) | Extreme-Vibration-Resistant Wedge Lock Washer |
| 91255A106 | — (diagnostic recipe; a former `vn-guide-lock-screw`) | Black-Oxide Alloy Steel Button Head Hex Drive Screw |
| 91255A148 | — (diagnostic recipe; a former `vn-cone-tip-block-screw`) | Black-Oxide Alloy Steel Button Head Hex Drive Screw |
| 91290A115 | `ch-rocker-arm-tl-oblique-nut-screw` (MHA-CH-006-TL-46; shop fixture; catalogue-only, vendor model read for dimensions, not replica-gated) | Socket Head Screw |
| 91290A148 | `ch-rocker-arm-tl-oblique-kp08-screw` (MHA-CH-006-TL-45; shop fixture; catalogue-only, vendor model read for dimensions, not replica-gated) | Socket Head Screw |
| 91290A168 | `ch-rocker-arm-tl-oblique-carriage-screw` (MHA-CH-006-TL-44; shop fixture; catalogue-only, vendor model read for dimensions, not replica-gated) | Socket Head Screw |
| 90325A174 | `vn-transgear-pivot-screw` (catalogue-only; CAD download refused) | 18-8 Stainless Steel Precision Shoulder Screw, hex socket |
| 91375A105 | `vn-pen-rod-set-screw` (catalogue-only; no vendor model) | Alloy Steel Cup-Tip Set Screw |
| 91375A106 | `vn-arbor-set-screw` | Alloy Steel Cup-Tip Set Screw |
| 91375A942 | `vn-fulcrum-set-screw` (catalogue-only; no vendor model) | Alloy Steel Cup-Tip Set Screw |
| 91410A538 | — (diagnostic recipe; `vn-gooseneck-set-screw` until 2026-10-12) | Steel Square-Head Cup-Point Set Screw |
| 91410A540 | `vn-gooseneck-set-screw` (catalogue-only; no vendor model) | Steel Square-Head Cup-Point Set Screw |
| 91595A452 | `ch-rocker-arm-tl-oblique-cl-dowel` (MHA-CH-006-TL-33; shop fixture; catalogue-only, vendor model read for dimensions, not replica-gated) | Dowel Pin |
| 91771A110 | `ch-rocker-arm-tl-oblique-riser-screw` (MHA-CH-006-TL-47; shop fixture; catalogue-only, vendor model read for dimensions, not replica-gated) | Stainless Steel Phillips Flat Head Screw |
| 91790A199 | `vn-transgear-arm-plate-screw` (catalogue-only; populated live SKU verified; 2-D PDF offered, CAD requires login) | 18-8 Stainless Steel Oval Head Slotted Screw |
| 91792A108 | `vn-guide-lock-screw` (catalogue-only; no vendor model) | 18-8 Stainless Steel Pan Head Slotted Screw |
| 91794A112 | `vn-cone-tip-pinch-screw` | 18-8 Stainless Steel Fillister Head Slotted Screw |
| 91794A055 | `vn-transgear-disc-screw` | 18-8 Stainless Steel Fillister Head Slotted Screw |
| 91794A077 | `vn-magnifying-bracket-screw` (catalogue-only; no vendor model) | 18-8 Stainless Steel Fillister Head Slotted Screw |
| 91794A080 | `vn-frame-side-screw` (catalogue-only; no vendor model) | 18-8 Stainless Steel Fillister Head Slotted Screw |
| 92240A540 | `vn-lag-screw` | 18-8 Stainless Steel Hex Head Screw |
| 91829A560 | `vn-cone-pivot-screw` | Slotted 18-8 Stainless Steel Precision Shoulder Screw |
| 92314A253 | `vn-knife-hanger-stud` (modified stock; catalogue-only, no vendor model) | 18-8 Stainless Steel Hex Head Screw, #10-24 × 2 in, cut to length |
| 92446A077 | `vn-platen-clip-screw` (catalogue-only; no vendor model) | Brass Pan Head Slotted Screw |
| 91882A221 | `vn-thumb-screw` | Steel Raised Knurled-Head Thumb Screw |
| 91882A425 | — (diagnostic recipe; `vn-cone-lock-knob` until 2026-09-29) | Steel Raised Knurled-Head Thumb Screw |
| 9275K141 | `vn-tube-frame-cap` | Metal Round Cap |
| 92671A005 | `vn-wheel-axle-nut` (catalogue-only; no vendor model) | Brass Hex Nut |
| 92671A115 | `vn-pen-adjust-nut` (catalogue-only; no vendor model) | Brass Hex Nut |
| 9414T1 | — (historical MHA-VN-016 until the 2026-10-08 terminal redesign) | Set Screw Shaft Collar for 1/16" Diameter |
| 94355A213 | `vn-cone-tip-collar` set screw, fitted as supplied | 18-8 Stainless Steel Flat-Tip Set Screw, #2-56 x 5/16" |
| 92865A585 | — (diagnostic recipe; former `vn-hex-bolt`, MHA-VN-008 retired) | Medium-Strength Grade 5 Steel Hex Head Screw |
| 92916A250 | `vn-wheel-axle-front-washer` (catalogue-only; no vendor model) | Brass Washer for Number 4 Screw Size |
| 96659A104 | `vn-knife-hanger-washer` (MHA-VN-060; catalogue-only, no vendor model) | 18-8 Stainless Steel SAE Washer for Number 10 Screw Size |
| 92916A480 | `vn-wheel-axle-back-washer` (catalogue-only; no vendor model) | Brass Washer for Number 10 Screw Size |
| 93075A194 | — (diagnostic recipe; `vn-hanger-screw` until the 2026-10-14 through-strap nut stack) | Low-Strength Zinc-Plated Steel Hex Head Screw |
| 93075A199 | `vn-hanger-screw` | Low-Strength Zinc-Plated Steel Hex Head Screw |
| 93585A190 | `vn-cone-lock-knob` | Stainless Steel High-Profile Knurled-Head Thumb Screw |
| 94025A150 | — (diagnostic recipe; `vn-cone-tip-adjuster` until drawing-guidelines.md rule 18 (thread engagement) E11) | 18-8 Stainless Steel Slotted Cup-Tip Set Screw |
| 94025A164 | `vn-cone-tip-adjuster` | 18-8 Stainless Steel Slotted Cup-Tip Set Screw |
| 93600A189 | `vn-transgear-arm-plate-locating-pin` (catalogue-only; no vendor model) | Passivated 316 Stainless Steel ISO 2338-m6 Dowel Pin |
| 9666K56 | `vn-lever-wire`, `vn-pen-wire` (cut from one coil; catalogue-only, no vendor model) | Lubricated 1080 Spring Steel Wire, 0.031 in, 1/4 lb coil |
| 9714K24 | `vn-rocker-bank-spring` (catalogue-only; no vendor model) | Wave Disc Spring |
| 9714K392 | `vn-cylinder-bank-spring` (catalogue-only; no vendor model) | Wave Disc Spring |
| 9715K43 | `vn-transgear-pivot-spring` (catalogue-only; no vendor model) | Curved Disc Spring |
| 97431A260 | `vn-transgear-retaining-ring` | Side-Mount External Retaining Ring |
| 98055A098 | `vn-transgear-pivot-shim` (MHA-VN-069; catalogue-only, no vendor model) | DIN 988 Shim, Stress-Resistant Spring Steel |
| 98296A026 | `vn-transgear-collar-cross-pin` | 1050-1095 Spring Steel Slotted Spring Pin |
| 98296A027 | `vn-pinion-strap-pin` | 1050-1095 Spring Steel Slotted Spring Pin |
| 98296A031 | `vn-transgear-knob-cup-pin` | 1050-1095 Spring Steel Slotted Spring Pin |
| 98381A433 | `vn-transgear-knob-drive-pin` (catalogue-only; no vendor model) | Alloy Steel Dowel Pin |
| 98381A434 | `vn-crank-seat-drive-pin` (crank only; catalogue-only; no vendor model) | Alloy Steel Dowel Pin |
| 98381A473 | `vn-knife-mount-dowel` | Alloy Steel Dowel Pin |
| 98381A474 | `vn-transgear-latch-pin` (catalogue-only; no vendor model; SKU not yet read live) | Alloy Steel Dowel Pin |
| 99607A213 | `vn-pen-set-screw` | Stainless Steel Flared-Collar Knurled-Head Thumb Screw |

The cone-lock and swing-stop selections follow `cad/scripts/build_vn_cone_lock_knob.py`
and `cad/scripts/build_vn_swing_stop_screw.py`.

Oblique trammel jig shop-fixture hardware (MHA-CH-006-TL-32/33 and
TL-41 to TL-49), modelled as purchased parts so the jig assembly can run
native interference. Their vendor models were downloaded on October 17,
2026 (UTC) and read for dimensions only; by user ruling of that date none is
replica-gated and no copy is kept here:

- [5972K41](https://www.mcmaster.com/5972K41/) (`ch-rocker-arm-tl-oblique-bearing`,
  MHA-CH-006-TL-32, four: a pair in each oblique-trammel jig pivot block) was
  read live on October 17, 2026: steel ball bearing, sealed (Buna-N both
  sides), trade no. 6200-2RS, ID 10 mm -0.008/0, OD 30 mm -0.009/0, width
  9 mm -0.12/0, ABEC 1, C3 radial clearance 0.008-0.023 mm, DIN 625-1. The
  vendor model was downloaded from the product page on October 17, 2026
  (`5972K41_Steel Ball Bearing.SLDPRT`, SHA-256
  `c27c3a1b09e8ca34e3191b2c345dd0b963297e5af1eb90e7d106441043c89ca9`; its
  STEP, SHA-256
  `617c061f9ee7b93425cf85cd29eb80eae1382ae82e6c66bfbf61f80f08754090`) and
  read for dimensions only; no copy is kept here. The STEP read in FreeCAD
  1.1 on October 17, 2026 has eleven solids, 3824.0143 mm³: an outer
  ring (Ø30 OD, 0.45 x 45° OD chamfers, Ø26 lands, a raceway groove of radius
  √13 on the Ø20 pitch circle meeting each land 2.0 from mid-width), an inner
  ring (Ø10 bore, 0.45 x 45° bore chamfers, Ø14 lands, the same groove), two
  seals between the lands (stepped and crowned outer face, inner face tangent
  to the balls) and seven Ø7.2111 balls. `diag_build_5972K41.py` models those
  eleven bodies, each its own unmerged revolve, bearing axis +Y with a side
  face at y = 0. It is catalogue-only: NOT replica-gated (user ruling
  October 17, 2026), and its standalone diagnostic is a catalog-only run.
  The bore, OD and width are the calculator's
  (`ch_rocker_arm_tl_oblique_trammel_spec` `BEARING_*`). ISO 15 gives the
  6200 a chamfer r_s min of 0.6 (SKF 6200-2RSH page, read October 16, 2026);
  the model carries the vendor's 0.45.
  It also supplies `fixtures.trammel-6200-2rs`; the inventory records the
  sourcing ruling on per-bearing internal play and the rejected C0 upgrade
  (combined play, mounting fits and alignment are not bounded by it).
  Receipt verification remains required.
- [91595A452](https://www.mcmaster.com/91595A452/) (`ch-rocker-arm-tl-oblique-cl-dowel`,
  MHA-CH-006-TL-33, one: the oblique trammel jig carrier's CL locator) was
  read live on October 17, 2026: 52100 alloy steel dowel pin, 6 mm diameter
  +0.004/+0.012 (DIN 6325-m6 / ISO 8734), 20 mm long, Rockwell C52 min, end
  shape "Round x Chamfer/Round", pack of 25. The page states no end forms; the
  vendor model does. It was downloaded from the product page on October 17,
  2026 (`91595A452_Dowel Pin.SLDPRT`, SHA-256
  `f5ee1a379a65051b513792b1163c4ce9fa2b664c056869bd7ffe7dd946fed855`; its
  STEP, SHA-256
  `e9a95f5ef80acb723ff7825b2143e070cc86b2f69f07c3cc6b44caf55fd4bfd6`) and read
  for dimensions only; no copy is kept here. The STEP read in FreeCAD 1.1 on
  October 17, 2026 is one revolve of four surfaces,
  536.8453 mm³, with no flat face: at the chamfered end a cone 15° to the
  axis, 1.17 long, from the Ø6 cylinder to Ø5.373, then an R5.0165 spherical
  crown 0.78 high; at the round end an R5.45 spherical dome 0.9 high.
  `diag_build_91595A452.py` models those end forms (its own section:
  `diag_mcmaster_dowel.build_dowel` draws flat ends), chamfered tip at y = 0
  (the pressed end), at nominal Ø6. It is catalogue-only: NOT replica-gated
  (user ruling October 17, 2026), and its standalone diagnostic is a
  catalog-only run.
  It also supplies `fixtures.trammel-cl-dowel`; length tolerance unstated.
  Both purchases remain unconfirmed in `cad/process/shop/inventory.toml`.
- [91251A197](https://www.mcmaster.com/91251A197/)
  (`ch-rocker-arm-tl-oblique-rail-screw`, MHA-CH-006-TL-41, 14 in the oblique
  trammel jig: the fastener table's `RAIL_TO_BAR` row) was read live on October
  17, 2026: #8-32 UNC class 3A, 3/4 in under the head, fully threaded, head
  Ø0.27 x 0.164 in, 9/64 in hex, Rockwell C37, ASTM A574, $18.68 per pack of
  100.
  The page gives no socket depth, so the model takes ASME B18.3's minimum key
  engagement for #8, 0.077 in (the 91251A108 convention).
  `diag_build_91251A197.py` builds it from those catalogue values on the 91251A
  family recipe (`diag_mcmaster_socket_head.build_socket_head`: plain
  cylindrical head, 0.75P tip chamfer, 45 deg thread neck; bearing face at y =
  0, tip at y = -length). The vendor model was downloaded from the product page
  on October 17, 2026 (the SLDPRT, SHA-256
  `8f52201b526d02bbf56d11bebc85a329a141aade6b1b2a19bc9b0f707f8281b5`; its STEP,
  SHA-256 `1ec8f71f860a945f6539b8540838c38dee0ea6c793ef68ca1b8b378ff64be3e5`)
  and read for dimensions only; no copy is kept here. It shows a hex socket
  0.082 in deep and a 50-groove knurled head, a 60 deg socket entry countersink,
  a 20 deg thread runout cone and a 0.6P tip chamfer, which the family recipe
  does not draw. It is NOT replica-gated (user ruling, October 17, 2026): the
  standalone run is catalogue-only (it builds the recipe, checks the solid and
  saves it under `cad/out/reference`).
- [91251A196](https://www.mcmaster.com/91251A196/)
  (`ch-rocker-arm-tl-oblique-bracket-screw`, MHA-CH-006-TL-42, 8 in the oblique
  trammel jig: the fastener table's `BRACKET_TO_BAR` row) was read live on
  October 17, 2026: #8-32 UNC class 3A, 5/8 in under the head, fully threaded,
  head Ø0.27 x 0.164 in, 9/64 in hex, Rockwell C37, ASTM A574, $15.24 per pack
  of 100.
  The page gives no socket depth, so the model takes ASME B18.3's minimum key
  engagement for #8, 0.077 in (the 91251A108 convention).
  `diag_build_91251A196.py` builds it from those catalogue values on the 91251A
  family recipe (`diag_mcmaster_socket_head.build_socket_head`: plain
  cylindrical head, 0.75P tip chamfer, 45 deg thread neck; bearing face at y =
  0, tip at y = -length). The vendor model was downloaded from the product page
  on October 17, 2026 (the SLDPRT, SHA-256
  `e7fe3961d447b3123ad067dc87db8d863b4452732368037f7d8080202bd771bb`; its STEP,
  SHA-256 `5b6fb26efa1d652c8b52dd69570b3851c7ceb2381af3ce16cb2571f7f3610924`)
  and read for dimensions only; no copy is kept here. It shows a hex socket
  0.082 in deep and a 50-groove knurled head, a 60 deg socket entry countersink,
  a 20 deg thread runout cone and a 0.6P tip chamfer, which the family recipe
  does not draw. It is NOT replica-gated (user ruling, October 17, 2026): the
  standalone run is catalogue-only (it builds the recipe, checks the solid and
  saves it under `cad/out/reference`).
- [91251A188](https://www.mcmaster.com/91251A188/)
  (`ch-rocker-arm-tl-oblique-block-screw`, MHA-CH-006-TL-43, 2 in the oblique
  trammel jig: the fastener table's `NUT_BRACKET_TO_BLOCK` row) was read live on
  October 17, 2026 from the #8-32 black-oxide listing: #8-32 coarse, 1-7/8 in
  under the head, partly threaded (7/8 in thread, the single-product 1-7/8
  filter page's only Thread Length facet), head Ø0.27 x 0.164 in, 9/64 in hex
  drive, 170,000 psi, US origin, $11.00 per pack of 10. It replaced a 1-3/4 in
  screw once the TL-50 wedge-lock pair went under each head: at the worst-case
  bands (ASME B18.3's -0.04 in length tolerance, TL-22's width and counterbore
  bands, the pair's 0.080-0.100 in stack) it engages TL-29 7.83 to 10.63, over
  1.5 D and inside the 12 full thread and its own 7/8 in thread.
  The page gives no socket depth, so the model takes ASME B18.3's minimum key
  engagement for #8, 0.077 in (the 91251A108 convention).
  `diag_build_91251A188.py` builds it from those catalogue values on the 91251A
  family recipe (`diag_mcmaster_socket_head.build_socket_head`: plain
  cylindrical head, 0.75P tip chamfer, 45 deg thread neck; bearing face at y =
  0, tip at y = -length), partially threaded over the catalogue's 7/8 in
  thread length ([UNVERIFIED-COM] as for 91251A157). No vendor model was
  downloaded (the CAD and 2-D drawing are behind the product page's login), so
  it is not replica-gated: the standalone run is catalogue-only (it builds the
  recipe, checks the solid and saves it under `cad/out/reference`).
- [91290A168](https://www.mcmaster.com/91290A168/)
  (`ch-rocker-arm-tl-oblique-carriage-screw`, MHA-CH-006-TL-44, 8 in the oblique
  trammel jig: the fastener table's `BLOCK_TO_CARRIAGE` row) was read live on
  October 17, 2026: M4 x 0.7 mm class 5g6g, 20 mm under the head, fully
  threaded, head Ø7 x 4 mm, 3 mm hex, class 12.9, Rockwell C41, DIN 912 / ISO
  4762, $14.47 per pack of 100.
  The page gives no socket depth, so the model takes ISO 4762's minimum key
  engagement (t min) for M4, 2.0 mm (the 91251A108 convention).
  `diag_build_91290A168.py` builds it from those catalogue values on the 91251A
  family recipe (`diag_mcmaster_socket_head.build_socket_head`: plain
  cylindrical head, 0.75P tip chamfer, 45 deg thread neck; bearing face at y =
  0, tip at y = -length). The vendor model was downloaded from the product page
  on October 17, 2026 (the SLDPRT, SHA-256
  `d95f5c3556da2eb440809a63d8e4511e9bf35dba2e57dafa8c55c9c5bc2a1e10`; its STEP,
  SHA-256 `8673cceae9ae657b9f1123f3cc019893698c47f39fcc0a5c376aee0c8cc3cf71`)
  and read for dimensions only; no copy is kept here. It shows a hex socket 3.0
  mm deep and a 72-groove knurled head, 45 deg head edge breaks, a 90 deg socket
  entry countersink, an under-head fillet with a 60 deg runout cone and a 0.75H
  tip chamfer, which the family recipe does not draw. It is NOT replica-gated
  (user ruling, October 17, 2026): the standalone run is catalogue-only (it
  builds the recipe, checks the solid and saves it under `cad/out/reference`).
- [91290A148](https://www.mcmaster.com/91290A148/)
  (`ch-rocker-arm-tl-oblique-kp08-screw`, MHA-CH-006-TL-45, 4 in the
  oblique trammel jig: the fastener table's `KP08_TO_BRACKET` row) was read live
  on October 17, 2026: M4 x 0.7 mm class 5g6g, 12 mm under the head, fully
  threaded, head Ø7 x 4 mm, 3 mm hex, class 12.9, Rockwell C41, DIN 912 / ISO
  4762, $12.30 per pack of 100.
  The page gives no socket depth, so the model takes ISO 4762's minimum key
  engagement (t min) for M4, 2.0 mm (the 91251A108 convention).
  `diag_build_91290A148.py` builds it from those catalogue values on the 91251A
  family recipe (`diag_mcmaster_socket_head.build_socket_head`: plain
  cylindrical head, 0.75P tip chamfer, 45 deg thread neck; bearing face at y =
  0, tip at y = -length). The vendor model was downloaded from the product page
  on October 17, 2026 (the SLDPRT, SHA-256
  `3d13359e07a7c80cc5290dba1a595739c6c5182caec6dd1020aef94b79f7d4a8`; its STEP,
  SHA-256 `0d40d024271575266eafd644858489ab44ddf1e7c18a01ee7f782b0cb5bbd7fc`)
  and read for dimensions only; no copy is kept here. It shows a hex socket 3.0
  mm deep and a 72-groove knurled head, 45 deg head edge breaks, a 90 deg socket
  entry countersink, an under-head fillet with a 60 deg runout cone and a 0.75H
  tip chamfer, which the family recipe does not draw. It is NOT replica-gated
  (user ruling, October 17, 2026): the standalone run is catalogue-only (it
  builds the recipe, checks the solid and saves it under `cad/out/reference`).
- [91290A115](https://www.mcmaster.com/91290A115/)
  (`ch-rocker-arm-tl-oblique-nut-screw`, MHA-CH-006-TL-46, 4 in the oblique
  trammel jig: the fastener table's `NUT_TO_NUT_BRACKET` row) was read live on
  October 17, 2026: M3 x 0.5 mm class 5g6g, 10 mm under the head, fully
  threaded, head Ø5.5 x 3 mm, 2.5 mm hex, class 12.9, Rockwell C41, DIN 912 /
  ISO 4762, $13.23 per pack of 100.
  The page gives no socket depth, so the model takes ISO 4762's minimum key
  engagement (t min) for M3, 1.3 mm (the 91251A108 convention).
  `diag_build_91290A115.py` builds it from those catalogue values on the 91251A
  family recipe (`diag_mcmaster_socket_head.build_socket_head`: plain
  cylindrical head, 0.75P tip chamfer, 45 deg thread neck; bearing face at y =
  0, tip at y = -length). The vendor model was downloaded from the product page
  on October 17, 2026 (the SLDPRT, SHA-256
  `bf8dce120aa6a6cc3414fbd419b233e3053241103812254828656946033dedd3`; its STEP,
  SHA-256 `f33505b4b05370d959ec6f94d8770c8676f745e50dab9e06814cc470c8dcd88e`)
  and read for dimensions only; no copy is kept here. It shows a hex socket 2.0
  mm deep and a 72-groove knurled head, 45 deg head edge breaks, a 90 deg socket
  entry countersink, an under-head fillet with a 60 deg runout cone and a 0.75H
  tip chamfer, which the family recipe does not draw. It is NOT replica-gated
  (user ruling, October 17, 2026): the standalone run is catalogue-only (it
  builds the recipe, checks the solid and saves it under `cad/out/reference`).
- [91771A110](https://www.mcmaster.com/91771A110/)
  (`ch-rocker-arm-tl-oblique-riser-screw`, MHA-CH-006-TL-47, 4 in the oblique
  trammel jig: the fastener table's `RISER_TO_CARRIER` row) was read live on
  October 17, 2026: 18-8 stainless steel, passivated, Phillips No. 1 drive,
  standard 82 deg flat head Ø0.212 x 0.067 in, #4-40 UNC class 2A, 1/2 in
  overall (McMaster measures a flat head from its top), fully threaded, flat
  tip, Rockwell B80, 80,000 psi, ASME B18.6.3, $6.63 per pack of 100.
  The model is catalogue first: the thread, the overall length, the head Ø0.212
  in, the 82 deg angle and the 0.067 in head height (where the thread ends) are
  the catalogue's. The vendor model was downloaded from the product page on
  October 17, 2026 (the SLDPRT, SHA-256
  `170dc7d8be906f2614181b0cac013ec2542eb37e93de45b40885ff555ae5f6ab`; its STEP,
  SHA-256 `588000b51c99935744bdd79b93fb8269cb27932f2e6086338d23bf51f9269a27`)
  and read for dimensions only; no copy is kept here. Where the catalogue is
  silent (the Phillips No. 1 recess form, the tip chamfer) the values are that
  reading's (FreeCAD 1.1):

  * head: the flat top Ø5.3848 (the catalogue's 0.212 in), sharp, then the
    41 deg (to the axis) cone to the major Ø2.8448, 1.460968 below the top;
  * thread: the family cutter (root R1.009955), cut on the shank only and
    ending flat 1.7018 (the catalogue's 0.067 in head height) below the top; no
    runout; tip chamfer 45 deg from R0.92075 at the tip flat (radial 0.50165);
  * Phillips No. 1 recess: walls at 5 deg to the axis; wings 2 x 0.3556
    (0.014 in) off their centre lines at the top; between adjacent wings a V
    notch of two planes 0.732384 from the axis at the top (normals 22.5 deg off
    the wings); a vertical entry cylinder R1.7907 (0.0705 in) down to 0.121008
    below the top, then a 41 deg (to the axis) cone with its apex 2.180973
    below the top.

  `diag_build_91771A110.py` builds it on a Phillips flat head recipe of its own
  (`diag_mcmaster_phillips_flat_head`: no existing family draws a flat top with
  a cross recess), the flat top at y = 0, tip at y = -length. It is NOT
  replica-gated (user ruling, October 17, 2026): the standalone run is
  catalogue-only (it builds the recipe, checks the solid and saves it under
  `cad/out/reference`).
- [91251A540](https://www.mcmaster.com/91251A540/)
  (`ch-rocker-arm-tl-oblique-clamp-screw`, MHA-CH-006-TL-48, 1 in the oblique
  trammel jig: the fastener table's `CR_CLAMP` row) was read live on October 17,
  2026: 1/4-20 UNRC class 3A, 3/4 in under the head, fully threaded, head Ø3/8 x
  1/4 in, 3/16 in hex, Rockwell C37, ASTM A574, $12.42 per pack of 50.
  The page gives no socket depth, so the model takes ASME B18.3's minimum key
  engagement for 1/4, 0.120 in (the 91251A108 convention).
  `diag_build_91251A540.py` builds it from those catalogue values on the 91251A
  family recipe (`diag_mcmaster_socket_head.build_socket_head`: plain
  cylindrical head, 0.75P tip chamfer, 45 deg thread neck; bearing face at y =
  0, tip at y = -length). The vendor model was downloaded from the product page
  on October 17, 2026 (the SLDPRT, SHA-256
  `33e4e61fa7b6ca29e8ecb4638d9c99421b83ed0e3a0742ef8500bcd5492fb774`; its STEP,
  SHA-256 `94ab0ed5323b88d716ad98a46626d0a9a1bb72a0503eb1d3e343e6bd841c36dd`)
  and read for dimensions only; no copy is kept here. It shows a hex socket
  0.125 in deep and a 50-groove knurled head, a 60 deg socket entry countersink,
  a 20 deg thread runout cone and a 0.6P tip chamfer, which the family recipe
  does not draw. It is NOT replica-gated (user ruling, October 17, 2026): the
  standalone run is catalogue-only (it builds the recipe, checks the solid and
  saves it under `cad/out/reference`).
- [91251A582](https://www.mcmaster.com/91251A582/)
  (`ch-rocker-arm-tl-oblique-lever-screw`, MHA-CH-006-TL-49, 2 in the oblique
  trammel jig: the fastener table's `LEVER_TO_CARRIER` row) was read live on
  October 17, 2026: 5/16-18 UNC class 3A, 7/8 in under the head, fully threaded,
  head Ø15/32 x 5/16 in, 1/4 in hex, Rockwell C37, ASTM A574, $14.48 per pack of
  50.
  The page gives no socket depth, so the model takes ASME B18.3's minimum key
  engagement for 5/16, 0.151 in (the 91251A108 convention).
  `diag_build_91251A582.py` builds it from those catalogue values on the 91251A
  family recipe (`diag_mcmaster_socket_head.build_socket_head`: plain
  cylindrical head, 0.75P tip chamfer, 45 deg thread neck; bearing face at y =
  0, tip at y = -length). The vendor model was downloaded from the product page
  on October 17, 2026 (the SLDPRT, SHA-256
  `9feed1cd8f28f698a03478549d6f0a70b5bc99916c1e8199b3d9857b4c99b5c7`; its STEP,
  SHA-256 `1e7b1c0ae31b76b34ea88254712024f5851b9fd953af801f633caf292272d940`)
  and read for dimensions only; no copy is kept here. It shows a hex socket
  0.15625 in deep and a 50-groove knurled head, a 60 deg socket entry
  countersink, a 20 deg thread runout cone and a 0.6P tip chamfer, which the
  family recipe does not draw. It is NOT replica-gated (user ruling, October 17,
  2026): the standalone run is catalogue-only (it builds the recipe, checks the
  solid and saves it under `cad/out/reference`).
- [91812A215](https://www.mcmaster.com/91812A215/)
  (`ch-rocker-arm-tl-oblique-block-washer`, MHA-CH-006-TL-50, 2 pairs in
  the oblique trammel jig: the fastener table's `BLOCK_LOCK_WASHER` row, one
  pair under each TL-43 block screw head) was read live on October 17, 2026
  from the No. 8 wedge-lock listing; the product page and its 2-D PDF are
  login-walled. Two-piece wedge-lock washer, reusable up to 15 times,
  comparable to NORD-LOCK; 316 stainless steel, Rockwell C51, case hardened;
  for No. 8 / M4; ID 0.170 in, OD 0.300 in, thickness 0.080 to 0.100 in;
  5 per package, $11.71. UNVERIFIED: the listing does not say whether the
  thickness is the pair's stack or one washer's, nor whether a package is 5
  pairs; the model takes the band as the pair's stack at its 0.100 in
  maximum. `diag_build_91812A215.py` builds the pair's envelope, one plain
  annulus from y = 0 along +Y (no cam faces, serrations or split). No vendor
  model was downloaded, so it is not replica-gated: the standalone run is
  catalogue-only (it builds the recipe, checks the solid and saves it under
  `cad/out/reference`).

Live catalogue verification on October 12, 2026:

- [91410A540](https://www.mcmaster.com/91410A540/) replaces 91410A538 as the
  MHA-VN-023 gooseneck set screw, per the user's Q5 ruling of October 12,
  2026: the top frame's hub now carries a cast square-sided boss with a Ø10
  spot face 21.0 from the bore axis, and the longer screw keeps at least 1.5D
  of full thread in it. The square-head cup-point family row was read live in
  a browser on October 12, 2026 (screenshot
  `C:/src/dt-logs/keeper-face-q5/91410A540-family-row-2026-10-12.png`):
  1/4-20 thread, length **3/4 in**, head width **1/4 in**, head height
  **3/16 in**, Rockwell **B80**, package quantity **50**, package price
  **$12.82**; UNC class 2A, ASME B18.6.2 / ASTM F912. The 5/8 in row is
  91410A538 ($12.34), otherwise identical. No jam nut: the joint is
  adjustable by design and re-set periodically (drawing-guidelines.md rule 23 (lock threaded joints exposed to operating loads) exception, user
  ruling October 12, 2026). The STEP download needs a McMaster login, so no
  vendor model is harvested. [INFERENCE] The cup rim (R1.739789, 45/59 deg)
  and the 75 deg head chamfers are 91410A538's vendor-solved values, which
  the family row does not distinguish; `_mcmaster_91410a540.py` carries
  them with the 19.05 mm length, and `diag_build_91410A540.py` builds it
  with the law it shares with 91410A538
  (`diag_mcmaster_square_set_screw.py`). It is catalogue-only: no replica
  gate. `diagnostics.diag_build_91410A538` stays as a diagnostic recipe.

Live catalog verification on October 11, 2026:

- [90114A124](https://www.mcmaster.com/90114A124/), selected for the four
  MHA-VN-059 platen-clip screws, is titled “Brass Fillister Head Slotted
  Screws, 2-56 Thread Size, 1/4" Long”. The live page and
  [technical drawing](https://www.mcmaster.com/mvD/Library/CAD2/20260619/961C5808/90114A124_Brass%20Fillister%20Head%20Slotted%20ScrewsS.GIF)
  were viewed on October 11, 2026: brass, Rockwell B40, 50,000 psi tensile
  strength, #2-56 UNC class 2A, fully threaded, flat tip, ASME B18.6.3,
  high narrow slotted fillister head. Under-head length is 0.25 in
  (6.35 mm), screw size decimal 0.086 in (2.1844 mm), head diameter
  0.14 in (3.556 mm), and head height 0.083 in (2.1082 mm). The drawing
  states no dimensional tolerances. Brass matches the book photograph's
  brass clip screws, so the same-size 18-8 stainless 91794A077 (MHA-VN-050's
  stock) is rejected for appearance; no brass #2-56 shorter than 1/4 in was
  found live. The shared #4-40 MHA-VN-006 brass fillister 90114A511 is
  rejected for the clip: its 4.65 mm head overhangs the clip's 4.23 mm rail,
  and it stays selected for the other fleet deployments. Through the 0.8 mm
  clip sheet the 6.35 mm shank leaves 5.55 mm of engagement in the platen's
  3.85 mm plate and 1.70 mm boss, 2.54D (at least 1.5D), with the tip flush.
  `diagnostics.diag_build_90114A124` reuses the native fillister family
  recipe; its derived slot, dome, thread/runout and vendor-frame mapping are
  family assumptions, not verified vendor geometry. No vendor model is
  harvested.

  Replaced on October 15, 2026 by 92446A077 (below) for the clip screws: the
  ASME B18.6.3 fillister head's least Ø0.124 in leaves 0.05 mm of bearing land
  over the clip's largest drilled #2 loose hole (Ø2.95 +0.10). 90114A124 stays
  selected for the MHA-VN-054 stop-plate screws.
- [92446A077](https://www.mcmaster.com/92446A077/) (`vn-platen-clip-screw`,
  MHA-VN-059, four) replaces 90114A124 on October 15, 2026 (user ruling: a
  pan head for the bearing land). The live page, titled “Brass Pan Head
  Slotted Screws, 2-56 Thread Size, 1/4" Long”, and its
  [technical drawing](https://www.mcmaster.com/mvC/Library/CAD2/20260610/72386355/92446A077_Brass%20Pan%20Head%20Slotted%20ScrewsX.GIF)
  were read on October 15, 2026 (a plain headless browser met the login
  wall; a Firecrawl scrape through its enhanced proxy returned the page):
  brass, Rockwell B40, 50,000 psi tensile strength, #2-56 UNC class 2A,
  fully threaded, flat tip, ASME B18.6.3, standard-profile slotted pan head
  0.167 in (4.2418 mm) across and 0.053 in (1.3462 mm) high, 0.25 in
  (6.35 mm) under the head, screw size decimal 0.086 in. The drawing states
  no tolerances; Olander's 2C25SPMBP, cross-referenced to 92446A077 (read
  October 15, 2026), gives the B18.6.3 head band Ø0.167 in max, 0.155 in
  min, and `_mcmaster_92446a077.py` holds the least head. Over the clip's
  largest drilled hole the least head leaves 0.44 mm of land (0.25 mm on a
  bearing circle of 90 % of it); the Ø4.24 head stays 1.18 mm inside the
  6.6 mm screw rail. Length and thread are 90114A124's, so the engagement
  (5.55 mm nominal, 4.02 mm worst case, at least 1.5D) and the flush tip are
  unchanged. The drawing shows a domed pan crown but sizes no crown, slot or
  tip, so `diag_build_92446A077.py` builds it on the shared slotted-head laws
  of `diag_mcmaster_fillister.py`, as 91792A108 does [INFERENCE]. It is
  catalogue-only: the SLDPRT download is not harvested, so it has no replica
  gate.

Live catalogue verification on October 9, 2026:

- [91375A942](https://www.mcmaster.com/91375A942/) is selected for the two
  MHA-VN-055 fulcrum-shaft set screws (one per MHA-CH-007 keeper crown, on
  the shaft's flat). Its product-detail table required login; the
  [public #1-72 black-oxide cup-point family table](https://www.mcmaster.com/products/cup-point-set-screws/thread-size~1-72/finish~black-oxide/)
  and the part's 2-D PDF were read live in a browser on October 9, 2026
  instead. The title is “Alloy Steel Cup-Tip Set Screw, Black-Oxide, 1-72
  Thread, 5/32" Long”; its row states length **5/32 in**, drive size
  **0.035 in**, hardness **Rockwell C45**, package quantity **10**, and
  package price **$7.43**. The filtered family fields state **Alloy Steel**,
  **Black Oxide**, **Headless**, **Hex** drive, **UNF**, **Fine** thread
  spacing, **Unified Standard Class 3A**, **Right Hand**, **ASME B18.3** and
  **ASTM F912**. The 2-D PDF gives major diameter **0.073 in**, length
  **0.156 in** and the **0.035 in** hex; it gives no cup dimension, so the
  cup diameter is the ASME B18.3 #1 maximum, 0.040 in. The #1-72 thread
  follows the keeper's crown tap (drawing-guidelines.md rule 18 (thread engagement)). 5/32 supersedes the 1/8 in
  91375A753 (same family row, $9.31/10), whose installed engagement fell
  to 1.40D at the worst case, under drawing-guidelines.md rule 17 (walls and webs) (Main ruling A, 2026-10-10);
  the superseded #6-32 candidate was 91375A182 (#6-32 x 5/32). No vendor
  model is harvested: `diagnostics.diag_build_91375A942` scales the
  91375A106 recipe's laws to the #1-72 pitch and the catalogue hex, family
  assumptions, not verified vendor geometry.

Live catalogue verification on October 10, 2026:

- [91794A080](https://www.mcmaster.com/91794A080/) replaces 90280A110 (and,
  before it, 90280A194) as the two MHA-VN-022 frame-side screws that hold the
  fulcrum keepers' feet. The
  [public #2-56 fillister family table](https://www.mcmaster.com/products/fillister-head-machine-screws/thread-size~2-56/?s=fillister-head-machine-screws)
  was read live in a browser on October 10, 2026: in the “Stainless Steel
  Fillister Head Slotted Screws” table, length **7/16 in**, head diameter
  **0.14 in**, head height **0.083 in**, **Fully Threaded**, tensile strength
  **70,000 psi**, package quantity **100**. The 90280A steel family has no
  #2-56 size. The smaller thread follows the transferred top-frame tap: the
  #4-40 tap left too thin a drawing-guidelines.md rule 17 (walls and webs) ligament under the keeper foot. The head
  and thread are the 91794A077 row's, so the shared fillister recipe builds it
  from the length alone; no vendor SLDPRT has been harvested for it.
  `diagnostics.diag_build_90280A194` stays as a diagnostic recipe.

Live catalog verification on October 8, 2026:

- [91794A077](https://www.mcmaster.com/91794A077/), selected for the two
  MHA-VN-050 magnifying-bracket screws, is titled “18-8 Stainless Steel
  Fillister Head Slotted Screw, 2-56 Thread Size, 1/4" Long”. The live page
  and [technical drawing](https://www.mcmaster.com/mvC/Library/CAD2/20260108/09FCA726/91794A077_18-8%20Stainless%20Steel%20Fillister%20Head%20Slotted%20ScrewS.GIF)
  were viewed on October 8, 2026: passivated 18-8 stainless, #2-56 UNC,
  right-hand class 2A, fully threaded, flat tip, ASME B18.6.3. Under-head
  length is 0.250 in (6.35 mm), nominal major diameter 0.086 in (2.1844 mm),
  head diameter 0.140 in (3.556 mm), and head height 0.083 in (2.1082 mm).
  The drawing states no dimensional tolerances. The joint's conservative
  0.76 mm screw-length allowance is a stack assumption, not a McMaster tolerance.
  The provisional #4-40 x 3/8 90280A108 selection is rejected for this joint:
  its larger thread and longer reach cannot satisfy the rib envelope and
  no-bottoming stack. It remains selected for the other three fleet parts.
  The #2 screw uses a Ø3.8 x 1.55 deep counterbore, leaving 1.625 mm nominal
  grip and a deliberately protruding head (0.5582 mm nominal, not flush).
  Its worst-case engagement is 3.2975 mm, above 1.5D (3.2766 mm); maximum
  reach 4.825 mm stays below the 4.90 mm minimum full-thread depth.
  The 5.00 mm maximum full-thread envelope stays within the 5.03 mm minimum
  rib depth. The drill body and point may continue into the lever plate.
  The native ±0.05 depth band belongs to `EdgeRibBack`, the actual -Z
  entry rib; `EdgeRibFront` is the opposite end. The minimum 0.122 mm
  head-to-counterbore radial float exceeds the 0.10 mm maximum station
  pitch mismatch at the printed ±0.05 position bands. The minimum end wall
  is 2.00 mm from the real end-face station datum, without double-counting
  its general location band.
  Receiver depth bands are authored on owned source-model dimensions across
  the Hole Wizard's full subfeature tree, using the same `GetDimension2(0)`
  traversal as the drawing-mark/tolerance helpers. The two validated model
  values identify the depths; native display names need not contain the word
  "depth". The build logs every native dimension name/value before its
  uniqueness checks, including borrowed and non-linear dimensions it refuses
  to tolerance. Linear values are logged in mm; other parameter types retain
  their native system units instead of being mislabeled as lengths.
  Wizard-owned dimension names are retained; bands and precision use their
  observed native names and owners, never foreign aliases. The farm receipt
  at `849347e57` passed the bracket's pre-annotation cut-volume check but its
  saved STL had no mounting holes. The measured 20.1045903 mm³ per-screw
  interference matches a solid plate's head/thread/runout overlap:
  20.1051883 mm³ analytically (0.0005980 mm³ residual), rather than a reversed
  counterbore or screw. Foreign Wizard-parameter renames in that loss window
  were removed; their causal role remains a native-validation inference.
  The same run's bracket drawing found no mounting-face circle at
  `(-39.0, 0.0, 52.01258778042654)` with radius 1.9 mm, corroborating the
  missing-cut diagnosis.
  Both builders force a final rebuild and prove the post-annotation volume
  before publication, so a later missing cut cannot inherit an earlier pass.
  `diagnostics.diag_build_91794A077` reuses the native fillister family recipe;
  its derived slot, dome, thread/runout and vendor-frame mapping are family
  assumptions, not verified vendor geometry. No vendor model is harvested.

Catalog specifications checked on September 10, 2026:

- [92240A539](https://www.mcmaster.com/92240A539/) is an 18-8 stainless,
  ASME B18.2.1 standard hex-head screw: 1/4-20 UNC class 2A, 5/8 in long,
  fully threaded, with a 7/16 in across-flats head 5/32 in high. Its supplied
  SolidWorks model was harvested read-only and the tracked diagnostic replay
  matches its 824.0529 mm3 volume, 832.0689 mm2 area, and 22-face multiset.
  It was the rocker-support hold-down until the 2026-09-25 machinist review
  (1.456D engagement in the base).
- [92240A540](https://www.mcmaster.com/92240A540/), checked September 25,
  2026, is the same screw 3/4 in long: 1/4-20 UNC class 2A, fully threaded,
  7/16 in across flats x 5/32 in head, flat tip, ASME B18.2.1. Its supplied
  SolidWorks model, supplied by the user as `92240A540_18-8 Stainless Steel
  Hex Head Screw Made Outside The U.S..SLDPRT`, is stored locally as
  `92240A540.SLDPRT` and was harvested read-only. The 92240A539 replay law
  at 19.05 mm (`diag_build_92240A540.py`) passed the replica gate against
  it on September 26, 2026: volume 901.5334 vs 901.5330 mm^3, area 929.1944
  vs 929.1943 mm^2, 22 faces each with the same face-area multiset (largest
  per-face delta 0.0001 mm^2), and matching centre of mass
  (`cad/out/reference/92240A540-replica-report.json`).
  Evidence SHA-256: native SLDPRT
  `0257bc44e4273a32536e58829d52ec552e04b631a472ae080a067f29b38eac39`.
- [91375A106](https://www.mcmaster.com/91375A106/), selected for MHA-VN-034
  (#743; since 2026-10-10 also one in each MHA-CH-008 pivot-bracket ear's
  apex, on the rocker pivot shaft's flat), is a black-oxide alloy steel hex
  socket cup-point set screw:
  #4-40 UNC class 3A, 1/4 in long, Rockwell C45, 0.050 in hex drive. Its
  supplied SolidWorks model was harvested read-only on September 26, 2026:
  volume 25.8601 mm^3, area 95.038 mm^2, 28 faces
  (`cad/out/reports/mcmaster-91375A106-dump.json`). The ASME B18.3 nominal
  model then shipped failed the replica gate against it (plain body, no
  thread). `diag_build_91375A106.py`, a true replica of the vendor recipe,
  passed the gate on September 26, 2026: volume 25.8601 vs 25.8601 mm^3,
  area 95.0373 vs 95.038 mm^2, 28 faces each with the same face-area
  multiset (largest per-face delta 0.0008 mm^2), and centre of mass within
  0.003 mm (`cad/out/reference/91375A106-replica-report.json`). The replica
  starts its thread helix a quarter turn from the vendor's, which only
  rotates the thread about its axis.
  Evidence SHA-256: native SLDPRT
  `7f4cfb6c5bdd3053372667ac29a37b319392bff40cdc908f924424c8d8ebecd8`.
- [91882A425](https://www.mcmaster.com/91882A425/) is black-oxide steel,
  with a 1/4-20 thread and a 19.05 mm (3/4 in) stud. The catalog's material
  field supplies the finish specification absent from the CAD properties.
  It was the `vn-cone-lock-knob` until September 29, 2026.
- [93585A190](https://www.mcmaster.com/93585A190/) is an 18-8 stainless high-profile knurled-head thumb screw,
  1/4-20 x 3/4 in, selected by the user on September 29, 2026 for the
  `vn-cone-lock-knob`. The product page returned HTTP 403 to automated fetches,
  so the facts come from the supplied SolidWorks model (custom properties
  PartNo 93585A190, Material "18-8 Stainless Steel"; no finish is named):
  Ø15.875 x 12.7 collarless head with 131 straight knurl ridges and
  0.79375 x 45° rim chamfers, 1/4-20 stud 19.05 long, 0.9525 tip chamfer.
  The model, supplied as `93585A190_Stainless Steel High-Profile
  Knurled-Head Thumb Screw.SLDPRT`, is stored locally as `93585A190.SLDPRT`
  and was harvested read-only (`cad/out/reports/mcmaster-93585A190-dump.json`).
  `diag_build_93585A190.py` passed the replica gate against it on
  September 29, 2026: volume 2899.1341 vs 2899.1341 mm^3, area 1853.6392
  vs 1853.6393 mm^2, 535 faces each with the same face-area multiset
  (largest per-face delta 0.0001 mm^2), and matching centre of mass
  (`cad/out/reference/93585A190-replica-report.json`).
  Evidence SHA-256: native SLDPRT
  `f168d0847e364090ace8e7401b3563a388a8a01307ef9590decd5ac2218e5555`.
- [90280A837](https://www.mcmaster.com/90280A837/) was selected on September
  13, 2026 from the user-supplied `90280A837.pdf`: #10-32 UNF-2A,
  1-3/4 in (44.45 mm) long, fully threaded zinc-plated steel, flat tip,
  ASME B18.6.3; head diameter 0.313 in and height 0.180 in.
  The supplied `90280A837_Steel Narrow Fillister Head Slotted Screws.SLDPRT`
  is stored locally as `90280A837.SLDPRT`. Its parametric family replay
  must pass the native diagnostic comparison before release; the PDF
  does not establish the derived slot, dome, thread/runout or CAD frame.
  Evidence SHA-256: PDF
  `3cc7644d354ac67d83e0696fecad6164c48d09cf6fab1a5600f2046c42ebf6cc`;
  native SLDPRT
  `3eeed3dd824e4460530f4d4509d9ceec839e2dccf367d0c76a05d4d8c7745f7f`.
- [9275K141](https://www.mcmaster.com/9275K141/) is the steel push-on cap
  for 1 in tubing, selected September 13, 2026 from the supplied PDF and
  `9275K141_Metal Round Cap.SLDPRT`. No coating is specified: finish is
  as supplied. The native section has 18.25625 mm inside height,
  0.635 mm wall/roof thickness, 26.67 mm straight outside diameter and
  a flared mouth reaching approximately 27.063768 mm outside diameter.
  The local model is `9275K141.SLDPRT`; its nine-face revolved section is
  replayed by `diag_build_9275K141.py`, with the opening normalized to Y=0.
  Evidence SHA-256: PDF
  `5bcc08b043bb1e7a8060c75d32db9f30f1528139478ee2a3f35676ab754c05c8`;
  native SLDPRT
  `0e52851776ee9ac5cd03c4d6ad2b1c07715417e4b97b85f032206cd8c2e3fad2`.
- [9414T1](https://www.mcmaster.com/9414T1/) is historical provenance only:
  MHA-VN-016 used this actual 1/16-inch collar from 2026-09-29 until the
  2026-10-08 1/32-inch terminal redesign. The September 29 page gave 1/4-inch
  OD, 3/16-inch width and black-oxide 1215 steel; the uncommitted vendor STEP
  supplied the 0.009375-inch edge breaks and #2-56 cup screw. It is not
  relabelled as a 1/32-inch product; its obsolete recipe is removed.
- [1/32-inch shaft collars](https://www.mcmaster.com/shaft-collars/shaft-diameter~1-32/)
  were read live on October 8, 2026. 6435K234 (one-piece stainless),
  6436K236 (two-piece stainless) and 6157K64 (aluminum) are 3/8-inch OD,
  7/32-inch wide clamp-on collars. They are legitimate smaller-envelope
  alternatives; preserving the existing set-screw mechanism motivated the
  custom design, not an explicit user requirement that COTS collars cannot
  meet. Final selection also depends on actual native assembly air.
- [94355A213](https://www.mcmaster.com/94355A213/) was verified live on
  October 8, 2026: 18-8 stainless flat-tip headless set screw, #2-56 UNC-3A,
  5/16-inch long, 0.035-inch hex, basic major 0.086 inch, Rockwell B80,
  ASME B18.3. The custom MHA-VN-016 collar is turned steel, not purchased;
  this genuine screw is fitted unaltered. The page gives no socket depth or
  end break.
  [ASME B18.3-2012 Table 14](https://www.finesz.com/pic/ASME%20B18.3.pdf)
  supplies the #2 minimum key engagement (0.060 inch), flat-point minimum
  diameter (0.039 inch), 45-degree minimum point angle, 30–45-degree socket
  face chamfer and ±0.01-inch length tolerance for this length. The retained
  factory depiction is not vendor-exact geometry.
  [BBI's ASME thread limits](https://www.brightonbest.com/download/pds/PDS_Thread_Details_Inch_Series.pdf)
  give the #2-56 3A pitch-diameter minimum, 0.0728 inch; the
  [2B UNC chart](https://amesweb.info/Screws/unc-thread-chart.aspx) gives the
  receiver maximum, 0.0772 inch. The collar's landing gate books their radial
  play and tilt with the tap's printed centring and angle. Because 2B gives
  no internal major/root maximum, the custom print separately controls the
  native MAX root gauge diameter; its wall proof does not invent a standard
  maximum. The tap station prints at .XXX.
  94355A212 (#2-56 x 1/4 inch, also verified) loses because the shorter
  screw buries its drive at the collar's worst-case radial flat.
- [90280A196](https://www.mcmaster.com/90280A196/) was read live on
  October 16, 2026: #8-32 UNC class 2A, 5/8 in (15.875 mm) long under the
  head, fully threaded zinc-plated steel, flat tip, ASME B18.6.3; head
  diameter 0.27 in and height 0.156 in. Owner Q13c selects it for
  MHA-VN-071, the two rocker-bracket hold-downs (one per MHA-CH-008 foot
  into MHA-FR-005's top-face seat), so that seat stays 11.5 thread / 14.7
  drill; 90280A197 stays on the arbor pedestals. Its head and thread match
  90280A197, so the shared fillister family recipe builds it from the
  length alone. No vendor SLDPRT has been harvested for this length yet.
- [90280A197](https://www.mcmaster.com/90280A197/) was read live on
  September 23, 2026: #8-32 UNC class 2A, 3/4 in (19.05 mm) long under the
  head, fully threaded zinc-plated steel, flat tip, ASME B18.6.3; head
  diameter 0.27 in and height 0.156 in. Its head and thread match the
  harvested 90280A194 and 90280A199, so the shared fillister family recipe
  builds it from the length alone. No vendor SLDPRT has been harvested for
  this length yet.
- [90280A203](https://www.mcmaster.com/90280A203/) was read live on
  October 8, 2026: #8-32 UNC class 2A, 1-1/2 in (38.1 mm) long under the
  head, fully threaded zinc-plated steel, flat tip, ASME B18.6.3; head
  diameter 0.27 in and height 0.156 in. It replaces 90280A201 only for
  MHA-VN-019: the raised pinion block needs the longer grip. The old
  31.75-mm screw loses the 1.5D engagement floor at the block's printed
  high limit even before entrance/tip deductions. Candidate 90280A202
  returned “No results”; it is not a purchasable length. No length band or
  slot dimensions are stated on the live page; the native family recipe's
  existing slot depiction is not new vendor-qualified metrology. No vendor
  SLDPRT was harvested. Base tap/drill depths follow the new stock length
  and shortest printed block, preserving the ordinary blind-seat reserves.
- [91255A148](https://www.mcmaster.com/91255A148/) is the #6-32 x 1/2 in
  black-oxide alloy steel button head hex drive screw that held the cone tip
  block under U30 (drawing-guidelines.md rule 17 (walls and webs) W22). `vn-cone-tip-block-screw` is now
  91251A108 (below); this entry stays as the replica recipe's provenance and
  is no longer a machine part. Source: the McMaster product page, supplied by
  the user on September 24, 2026 (an agent fetch that day was refused, HTTP
  403): #6-32 UNC-3A, right hand, flat tip, head Ø0.262 in x 0.073 in, 5/64
  hex drive, 1/2 in under the head, fully threaded, 140 ksi, ASME B18.3 /
  ASTM F835. The catalog fixes the identity; the geometry is the vendor
  model's own. `diag_build_91255A148.py` replays the dimensions and solved
  sketch geometry read from `91255A148.SLDPRT` (the read-only dump
  `cad/out/reports/mcmaster-91255A148-dump.json`): the 7/64 flat top and
  R3.941216 dome, the 10 deg edge band and its R0.09271 fillets, the 5/64
  hex socket 1.01981 deep with its 60 deg countersink, and the thread, tip
  chamfer and 45 deg neck; its docstring lists each value. The vendor file is
  local-only (© McMaster, gitignored). The replica gate against it passed on
  September 25, 2026: volume 130.7034 vs 130.7033 mm^3, area 291.3955 mm^2
  on both, 26 faces each with the same face-area multiset, and matching
  centre of mass (`cad/out/reference/91255A148-replica-report.json`).
  Evidence SHA-256: native SLDPRT
  `4b8dac17c6b7e77499209a399342aa51780743b657aec0df7175f227b54e59a0`.
- [6793K4](https://www.mcmaster.com/6793K4/),
  [6793K11](https://www.mcmaster.com/6793K11/) and
  [6793K17](https://www.mcmaster.com/6793K17/) are the bought blanks for
  `pd-transgear-removable`, MHA-PD-009 T12/T18/T24, per the user ruling of
  October 8, 2026. The pages, read live October 8, 2026, specify steel,
  ANSI #25, 1/4 in pitch and plain bores; they state no steel grade, plate
  thickness, finish or coating. The registry retains Plain Carbon Steel and
  an as-supplied, unplated finish; no supplier grade or coating is inferred.
  Teeth, OD and plate faces remain as supplied. Shop operations are, in order:
  turn the hub off flush with the supplied plate, bore Ø10.3 through, then
  drill two Ø2.5 through drive-pin holes on Ø14. Identity, ANSI #25 chain
  and shaft/collar interfaces are unchanged.
  Source: `C:/src/dt-logs/sprocket-evidence/mcmaster-skus.md` (October 8, 2026),
  recording the live pages and headless OCP measurements of user-supplied CAD:

  | supplied blank measurement (mm unless noted) | 6793K4 T12 | 6793K11 T18 | 6793K17 T24 |
  |---|---|---|---|
  | OD | 27.5082 | 39.8272 | 52.0446 |
  | plate thickness; faces about its mid-plane | 2.794; −1.397 / +1.397 | 2.794; −1.397 / +1.397 | 2.794; −1.397 / +1.397 |
  | hub diameter × projection beyond plate | 15.875 × 9.906 | 28.575 × 9.906 | 38.100 × 13.081 |
  | supplied bore | 6.35 | 6.35 | 9.525 |
  | supplied bore chamfer, both ends, 45° | 0.3175 | 0.3175 | 0.476 |
  | whole-blank volume (mm³), before shop rework | 2794.988 | 8765.472 | 18817.317 |

  Each supplied tooth-side chamfer is a revolved cone on both faces:
  semi-angle 73.828° (16.172° to the face), radial width 1.905 and axial
  depth 0.552, running from the OD to Ø(OD − 3.81) at the plate face.
  Mid-plate profiles match the spec's ACA tooth form within 0.007 mm
  Hausdorff distance for all three blanks; symmetric-difference areas are
  0.69 / 1.10 / 1.46 mm² respectively. The nominal 2.8 +0/−0.10 plate band
  includes the supplied 2.794 plate. After boring T24 to Ø10.3, its supplied
  hubless-face bore chamfer to Ø10.4775 leaves an approximately 0.09 radial
  edge break.

  An independent headless OCP volume cross-check, recorded by the local-only
  `C:/src/dt-logs/sprocket-evidence/plate_volume_crosscheck.py`, clips each
  vendor STEP to z = −1.397..+1.397 and fills its supplied bore and mouth
  breaks with a radius-6 cylinder to isolate the solid toothed plate.
  Comparing that plate with the ACA model at the same 2.794 thickness,
  including both conical tooth-side cuts, gives:

  | cross-check volume (mm³) | T12 | T18 | T24 |
  |---|---|---|---|
  | filled vendor plate | 1248.331943 | 2834.845367 | 5065.837369 |
  | ACA plate with tooth-side chamfers | 1246.650982 | 2832.032137 | 5062.167973 |
  | ACA minus vendor | −1.680961 | −2.813230 | −3.669396 |
  | material removed by modelled tooth-side chamfers | 24.488689 | 34.334689 | 44.060412 |
  | expected finished model, nominal 2.8 thickness, Ø10.3 bore and two Ø2.5 pin holes | 988.587671 | 2577.394510 | 4812.340357 |

  The same-thickness plate differences are below 0.14% and reflect the
  residual tooth-profile differences, not an omitted hub or tooth-side
  chamfer. The expected finished volumes are numerical model predictions,
  not measured shop parts or a SolidWorks-build acceptance result. The probe
  remains local-only and is not tracked; the original vendor files are bound
  by the hashes below.

  Evidence SHA-256:

  | local-only vendor file | SHA-256 |
  |---|---|
  | `6793K4.STEP` | `f220620116bb06a842faba75d61c33d807c639239e81f23ba5e4360af239f470` |
  | `6793K11.STEP` | `daa0cdef6391e60ffeeba99f35a9436edcf90b3098384b043b5754693caed894` |
  | `6793K17.STEP` | `6d88447ab5e301a19f42d172e319aedea319892d7790cbe6a7ecbc0c5dd98253` |
  | `6793K4.SLDPRT` | `8197ff52361ab9cd9b387bdda8e1fda0fa931ecf5db9a07ed33b13a3125ac9c1` |
  | `6793K11.SLDPRT` | `b1b131c9edb72b1dc247f337ec30bb705594aeb83715c7c834ddc0fa871cde5d` |
  | `6793K17.SLDPRT` | `98b8bc501273cac0a82962b01ebeb4f19943f812ae23408881f60e6d90e948e0` |

  These STEP and SLDPRT files are © McMaster-Carr, local-only evidence,
  never committed or redistributed. No `diag_build_*` recipe replays these
  whole vendor blanks: the finished part is modelled from
  `pd_transgear_removable_spec`, not imported vendor geometry.


- [91251A108](https://www.mcmaster.com/91251A108/) (`vn-cone-tip-block-screw`,
  MHA-VN-030) holds the cone tip block down per the user ruling of September 29,
  2026 (photo `eight-views-4.png`, lower right): the block stands directly on
  the cone swing platform, and this one screw rises from under the platform's
  counterbored clearance hole into a blind #4-40 tap in the block's bottom
  face. The product page was read in a headless browser on September 29,
  2026: black-oxide alloy steel socket head screw, #4-40 UNC class 3A, right
  hand, 3/8 in under the head, fully threaded, flat tip, head Ø0.183 in x
  0.112 in, 3/32 in hex drive, 170 ksi, Rockwell C37, ASTM A574. The page
  gives no socket depth; `diag_build_91251A108.py` takes ASME B18.3's #4
  minimum key engagement, 0.055 in, and a plain cylindrical head. It is
  catalogue-only: no vendor model is downloaded or kept here, so it has no
  replica gate, and its standalone diagnostic is a catalog-only run.
- [91251A157](https://www.mcmaster.com/91251A157/) formerly supplied
  `vn-knife-hanger-stud`, MHA-VN-024, two, in the superseded #6-32 route.
  Each screw dropped through the MHA-FR-002 crossbar counterbore and seated
  directly on its floor, threading into the MHA-SM-002 mount's top seat.
  That route had replaced the 1/2-13 hex bolt 91247A720 and washer 90126A211;
  all three SKUs remain historical/diagnostic records, not current hanger
  hardware. The product page was read live in October 2026: black-oxide
  alloy steel socket head screw, 6-32 UNC class 3A, right hand, 1-1/2 in
  under the head, partially threaded with a 3/4 in minimum thread length,
  flat tip, head Ø0.226 in × 0.138 in, 7/64 in hex drive, 170 ksi,
  Rockwell C37, ASTM A574. The page gave no socket depth;
  `diag_build_91251A157.py` used ASME B18.3's #6 minimum key engagement,
  0.064 in, and a plain cylindrical head on the socket-head recipe shared
  with 91251A108 (`diag_mcmaster_socket_head.py`). It remains catalogue-only,
  with no vendor model or replica gate.
- [92314A253](https://www.mcmaster.com/92314A253/) is the current modified
  stock for `vn-knife-hanger-stud`, MHA-VN-024, drawing title **Bolt**, two.
  Live on 2026-10-13: 18-8 stainless steel external hex head, #10-24 UNC
  class 2A, fully threaded, 2 in (50.8 mm) nominal under-head length,
  80 ksi tensile strength, nominal AF 5/16 in (7.9375 mm) and head height
  1/8 in (3.175 mm). This SKU's table omits dimensional tolerances and
  a conformity standard; no supplier head tolerance or under-head bearing
  circle bound is inferred. The ordinary hex-head-on-SAE-washer joint is
  accepted practice, not a guaranteed stress or material allowable.
  Cut the under-head length to **46.70 ±0.15 mm** from the 50.8 mm stock.
  Finished-part acceptance retains a threaded tail **MIN 10.62 mm from the cut end**, with
  **MAX 1 P cut chamfer**, leaving at least 9.561667 mm full-form tail.
  These are manufactured acceptance constraints, not vendor grades.
  Retain the native cut-end prep **RADIAL 0.60 ±0.05 mm ×45 ±1°** and
  independently inspect the finished length, tail and
  #10-24 class 2A thread; none is a new supplied SKU length or tolerance.
  The head bears on the new washer, not the obsolete #6 counterbore floor.
- [96659A104](https://www.mcmaster.com/96659A104/) supplies the new
  `vn-knife-hanger-washer`, **MHA-VN-060**, two; the retired 1/2-inch
  washer's MHA-VN-026 Number is never reused. Live on 2026-10-13: 18-8
  stainless SAE No. 10 flat washer, ASME B18.21.1, nominal ID 5.5626 mm
  and OD 12.7 mm, published thickness 0.9144–1.651 mm. The model's
  1.2827 mm thickness is a nominal midpoint, not a guaranteed thickness.
  [ASME B18.21.1-2009, Table 11](https://ssmalloys.com/wp-content/uploads/2024/10/ASME-B18.21.1.pdf)
  gives actual ID 5.4356–5.7658 mm and OD 12.573–13.081 mm; §4.5's
  OD-to-ID runout is included conservatively as 0.3302 mm radial eccentricity.
  Full washer float uses the #10-24 class 2A external-major limits
  **MIN 4.61772 / MAX 4.8006 mm** (0.1818 / 0.1890 in;
  [sourced thread chart](https://www.engineersedge.com/screw_threads_chart.htm)),
  not the nominal thread major. Radial float is 0.57404 mm; the frame builder
  adds hanger-pattern mismatch, through-hole drift and washer eccentricity
  in its top-seat support proof.
  The washer seats on the frame's whole faced top, except the four proud
  corner bosses. The governing **36.50 ±0.05 mm** top-to-finished-underside
  grip is the model's actual `HangerGrip@Crossbar` driving dimension,
  toleranced in the part builder and imported unchanged by section F-F.
  There are no hanger spotfaces, separate floor driver or cleanup offset.
  The two Ø6.045 +0.13/0 clearance holes are drilled from the finished
  underside; their charged drift grows toward the top washer seat.
  The external-hex bolt remains
  92314A253. After the bolt's trim equations, its deburr revolve explicitly
  selects the completed closed sketch (mark 0) and captured construction
  axis (mark 4), rather than relying on incidental post-edit selections.
  Coordinator R3 on 37a3382d9 passed the top-frame part, the knife-mount
  drawing and the frame/summing/top assemblies and soundness; the bolt part
  and drawing had already passed R2. Only the top-frame drawing failed:
  `IAnnotation.Select3` threw while selecting its native crossbar width.
  The drawing now re-resolves that width by its native selection name after
  the text-offset rebuild, uses the documented `SelectByID2` dimension
  channel, and records annotation name/type and selection identity before
  inserting datum D. Exactly-one selection and the original dimension-
  attachment, label and dangling guards remain mandatory. Stale handles
  are a possibility, not a demonstrated root cause; the final-source
  selection and median-plane datum layout require the scoped native proof.
  The washer seats on the **whole faced top**, **36.50 ±0.05 mm
  above the finished crossbar underside**. With the 46.70 mm cut bolt, nominal tip
  reach is 8.9173 mm, bounded by 8.349–9.4856 mm. Subtracting one #10-24
  pitch gives minimum full-form engagement 7.290667 mm, above 1.5D =
  7.239 mm. Full-thread depth **9.65 ±0.13 mm** (MIN 9.52) leaves
  0.0344 mm tip air at maximum reach; the inspected full-form tail leaves
  9.561667 − 9.4856 = 0.076066667 mm coverage beyond maximum reach.
  These are the stated stack margins, not extra tolerance reserves.
  The receiver's cylindrical drill depth is **11.24 ±0.05 mm**. Its
  corrected crown proof charges physical pilot oversize and point-angle
  variation, not nominal diameter and an exact point angle; see the
  [machining route and charged bounds](../../docs/machining-dfm.md#summing-lever--knife-edge-t1--least-forgiving-interface).
  The SKU tables and 2-D reference PDFs were recovered in a browser:
  PDF fetching succeeded after direct HTTP 403 failures. The drawings state
  that dimensions are for reference only and add no screw tolerance.
  No vendor CAD download, hash, or measured vendor geometry is claimed.
  R3 proved the prior native joint geometry and assembly soundness; the
  revised datum and machinist-driven sheet edits require a fresh scoped
  native proof and sheet review before they are reported verified.
- [91255A106](https://www.mcmaster.com/91255A106/) (`vn-guide-lock-screw`,
  MHA-VN-046, eight) holds the four guide locks to the platen guides per ruling
  R9-31 (September 30, 2026): these screws ride the platen, and the MHA-VN-006
  fillister head there sweeps into the transgear hanger arm, so they alone
  take a button head with the same 1/4 in shank. The product page was read
  in a headless browser on September 30, 2026: black-oxide alloy steel button
  head hex drive screw, #4-40 UNC class 3A, right hand, 1/4 in under the
  head, fully threaded, flat tip, standard-profile head Ø0.213 in x 0.059 in,
  1/16 in hex drive, 140 ksi, Rockwell C39, ASME B18.3 / ASTM F835. The page
  gives nothing else, so `diagnostics/diag_mcmaster_button_head.py` and
  `_button_head_dimensions.py` carry the 91255A148 vendor-measured laws over
  in proportion: flat top 7/5 of the hex, band 0.15 of the head height at
  10 deg, fillets 0.05, socket floor 0.55, the 60 deg countersink.
  `_mcmaster_91255a106.py` holds its SKU dimensions. It is catalogue-only: no
  vendor model is downloaded or kept here, so it has no replica gate, and its
  standalone diagnostic is a catalog-only run. Lost: 91255A105 (3/16 in;
  shortens the lock stack) and
  18-8 stainless 92949A106 (same head and length, 70 ksi, Rockwell B55;
  the alloy screw matches the 91255A148 family whose laws the recipe uses).
- 91255A108 (`vn-guide-lock-screw` from ruling R9-48 until October 11, 2026)
  replaced 91255A106: the 1/4 in screw engaged only 1.26D of the guide's
  blind tap at the worst case, so the guide's lock receivers became through
  taps and the screw 3/8 in under the head. 91792A108 replaced it; its
  recipe module was retired with it.
- [98296A027](https://www.mcmaster.com/98296A027/) was read live on
  September 25, 2026: 1050-1095 spring steel slotted spring pin, 1/16 in
  diameter, 1/2 in long, 0.012 in wall, for a 0.062-0.065 in hole,
  ASME B18.8.2, chamfered ends, no finish listed; 430 lbf double shear,
  Rockwell C43 minimum. The page gives no slot or chamfer size. No vendor
  SLDPRT has been harvested for it yet.
- [98296A026](https://www.mcmaster.com/98296A026/) (`vn-transgear-collar-cross-pin`,
  MHA-VN-037) was read live on September 30, 2026: the same 1050-1095 spring
  steel slotted spring pin, unplated, 1/16 in diameter, 9/16 in long,
  0.012 in wall, for a 0.062-0.065 in hole, chamfered ends, no diameter
  tolerance stated. No vendor SLDPRT has been harvested for it yet.
- [98296A031](https://www.mcmaster.com/98296A031/) (`vn-transgear-knob-cup-pin`,
  MHA-VN-048) was read live on October 2, 2026: the same 1050-1095 spring
  steel slotted spring pin, 1/16 in diameter, 5/8 in long, for a
  0.062-0.065 in hole. It is pressed through the knob cup and the knob
  shaft's journal in a hole match-drilled at assembly. No vendor SLDPRT has
  been harvested for it yet.
- The three spring pins have separate data in `_mcmaster_98296a026.py`,
  `_mcmaster_98296a027.py` and `_mcmaster_98296a031.py`, passed to
  `diagnostics/diag_mcmaster_spring_pin.py`. The shared recipe models each
  as installed, a 1/16 in tube with the catalog wall, without slot or
  chamfer; `diag_build_98296A026.py`, `diag_build_98296A027.py` and
  `diag_build_98296A031.py` are its per-size runs.
- [98381A434](https://www.mcmaster.com/98381A434/) (`vn-crank-seat-drive-pin`,
  MHA-VN-044, crank only) was read live on September 30, 2026: alloy steel dowel pin,
  unplated, 3/32 in diameter (+0.0001 to +0.0003 in), 1/4 in long, end shape
  "Round x Chamfer". The page states neither the end radius nor the chamfer,
  so `diag_build_98381A434.py` models the plain nominal cylinder. It is
  catalogue-only: no vendor model is downloaded or kept, so it has no replica
  gate, and its standalone diagnostic is a catalog-only run.
- [98381A433](https://www.mcmaster.com/98381A433/) (`vn-transgear-knob-drive-pin`,
  MHA-VN-038, the knob shaft's pair) was read live on September 30, 2026: alloy
  steel dowel pin, unplated, 3/32 in diameter (+0.0001 to +0.0003 in), 3/16 in
  long, end shape "Round x Chamfer". As for 98381A434, `diag_build_98381A433.py`
  models the plain nominal cylinder; catalogue-only, no vendor model, no
  replica gate.
- [93600A189](https://www.mcmaster.com/93600A189/), MHA-VN-056, quantity two,
  was read live on October 9, 2026 in isolated Chromium (HTTP 200): passivated
  316 stainless, ISO 2338-m6, diameter 2.002–2.008 mm, nominal length 6 mm,
  both ends chamfered. The supplier does not publish a length or chamfer
  band. [ISO 2338:1997 Table 1](https://cdn.standards.iteh.ai/samples/20001/5b26cece48c448b782c0de1eccb5b16c/ISO-2338-1997.pdf)
  bounds nominal 6-mm stock to 5.75–6.25 mm;
  [c≈0.35 mm](https://fullerfasteners.com/tech/iso-2338-specifications-parallel-pins/)
  is approximate, not a hard end limit or full-cylinder certificate.
  `vn_transgear_arm_plate_locating_pin_spec.py` owns the ordinary installation
  fits and proud set. The whole standard length family has at least 0.17 mm
  bottom air in the custom arm blind hole. `diag_build_93600A189.py` uses the
  existing nominal-cylinder recipe: catalogue-only, no vendor model, no
  replica gate and no new commodity receiving procedure.
- [98381A473](https://www.mcmaster.com/98381A473/) (`vn-knife-mount-dowel`,
  MHA-VN-051, two; formerly `vn-transgear-latch-pin`) was read live on
  September 30, 2026:
  alloy steel dowel pin, 1/8 in diameter, 3/4 in long, end shape "Round x
  Chamfer". The page states no end radius or chamfer; the vendor model does.
  The user supplied it (as `98381A473_Dowel Pin.SLDPRT`, kept here as
  `98381A473.SLDPRT`), SHA-256
  `71a73f654a95bb8a38c99fea9380a19148f15cf357711faa193f0e867a143685`, and it
  was harvested on September 30, 2026 on amet into
  `cad/out/reports/mcmaster-98381A473-dump.json`: one revolve of five faces,
  a flat Ø0.115 in end face and a cone 16° to the axis at the chamfered end,
  the Ø0.125 in cylinder, and a 0.016 in radius tangent to it down to a flat
  Ø0.093 in face at the round end (150.2183 mm³). `diag_build_98381A473.py`
  models those end forms, chamfered end at y = 0 (the pressed end), and its
  standalone run is the replica gate against that harvest. The
  diameter band is the family's, read on the 98381A433/434/489 pages.
- 98381A474 (`vn-transgear-latch-pin`, MHA-VN-042, since R9-50) is the 7/8 in
  length of the same 1/8 series (98381A467 1/8 in through 98381A479 1-3/4 in,
  dt-logs `transgear-evidence/mcmaster-skus.md`, "Round 6 — additions"); a
  reseller lists it as 1/8 x 7/8
  (https://www.kvmtools.com/products/mcmaster-98381a474-dowel-pin-pack-of-50-alloy-steel-1-8-diameter-7-8-long).
  [INFERENCE] Its own page is not yet read live. `diag_build_98381A474.py`
  carries the 98381A473 harvest's end forms at the longer length; it is
  catalogue-only: no vendor model, no replica gate, and its standalone
  diagnostic is a catalog-only run.
- [90325A174](https://www.mcmaster.com/90325A174/) (`vn-transgear-pivot-screw`,
  MHA-VN-041) is the hanger arm's pivot: its shoulder runs through the arm and
  the pivot spacer, and its thread runs through the support bar's through tap,
  the tip faced 0.20-0.50 below the bar's front face at fit-up and staked at
  the front tap mouth (rule 23, user ruling 2026-10-15; threadlocker
  optional). It replaced 91829A205 (slotted, 8-32 x 3/16 thread: 0.72D
  engagement nominal in the old blind tap), whose diagnostic recipe was
  retired with it. The product page was read live on October 14, 2026: 18-8
  stainless steel precision shoulder screw, 3/32 in hex socket; shoulder
  Ø3/16 in (-0.001/0) x 1/2 in (0/+0.002), 8-32 UNC class 2A thread 3/8 in
  long, head Ø5/16 in x 5/32 in (the same head envelope as 91829A205); $3.98
  each. Only 90325A171..174 carry a 3/8 in thread on a 3/16 in shoulder. The
  page's CAD download was refused (HTTP 403), so it is catalogue-only: no
  vendor model and no replica gate. ASME B18.3-2012 Table 13 (3/16 row)
  bounds what the page omits: socket key engagement T 0.079 min, head-rim
  chamfer C 0.012 max, the thread neck, and the thread length's -0.020 in
  tolerance (9.017 mm shortest). `diag_build_90325A174.py` keeps the retired
  91829A205 recipe's replica-gated feature order with the slot replaced by
  the hex socket; full thread starts 1.7653 below the shoulder's end face,
  and the joint charges one full pitch at the faced tip, so the worst-case
  engagement is 1.515D (1.582D nominal).
- [91794A055](https://www.mcmaster.com/91794A055/) (`vn-transgear-disc-screw`,
  MHA-VN-039, three) joins the brass disc hub's flange to the 120T disc: each
  head sits on the flange and the thread enters one of the disc's through
  taps. The product page was read on September 30, 2026: 18-8 stainless
  steel slotted fillister head, #0-80 UNF class 2A, 1/4 in under the head,
  fully threaded, high narrow head Ø0.096 in x 0.055 in. The user supplied
  the vendor model `91794A055.SLDPRT`, harvested on amet on September 30,
  2026 into the read-only dump `cad/out/reports/mcmaster-91794A055-dump.json`.
  It is not the 90280A narrow-fillister tree, so `diag_build_91794A055.py`
  replays its own laws (in `vn_transgear_disc_screw_spec.py`) instead of
  `diag_mcmaster_fillister.py`: a spherical dome over a side 0.7 of the head
  height tall, drafted 5° narrower toward the bearing face; a neck
  Ø1.02 x the size, 0.05 x the length long; a slot 0.1 of the head Ø wide
  whose floor sits 1.5 dome heights under the apex; slot-floor fillets
  0.033 and head-rim fillets 0.125 of the head height; a 45° x 0.75 P tip
  chamfer; a thread seeded at the tip, running L + P up (its last turn is a
  closed void inside the head, as in the vendor model), with a P/8 root flat
  at major - 0.75 H; and a runout Ø(major + 0.1016) from the neck's step up
  to the bearing face, drafted 60° toward the tip. `diag_build_mcmaster.py
  91794A055` runs the replica gate against the vendor's volume 13.8241 mm³,
  surface 64.5474 mm² and 26-face area multiset. Evidence SHA-256: native
  SLDPRT `3b7b3ee38a51864b0c9d495e44ade30c80816d4b5498b8801211b8edb82676dc`.
- [91790A199](https://www.mcmaster.com/91790A199/) (`vn-transgear-arm-plate-screw`,
  MHA-VN-040, two) was positively read live at 2026-10-09T07:17:13.553Z:
  18-8 stainless steel, slotted standard oval head, #8-32 UNC right-hand
  class 2A, fully threaded, ASME B18.6.3, flat tip. Supplied length is
  1 in (25.40 mm) from the **top of the bevel**, not the crown. The longer
  raw stock is cut to the unchanged installed fit, preserving the oval/
  slotted look and quantity. Bench-fit the matched joint, remove/pre-cut
  **off mechanism before the guide-lock sweep**, trim flush to 0.20 mm
  proud of the arm front face and break the cut end 0.10 mm MAX, then
  refit the same matched hardware.
  The page's nominal head Ø0.312 in, total height 0.152 in, oval-top
  height 0.052 in and nominal 82° angle are not supplier tolerance bands.
  The native head is an ASME/reference construction, not a vendor solid
  or a measured hardware profile. Conservative published
  [ASME B18.6.3-2013 Table 7](https://www.finesz.com/pic/ASMEB18.6.3-2013.pdf)
  gives maximum head Ø0.312 in, maximum protrusion F0.091 in above
  standard gaging diameter G0.267 in, and included bearing angle 80–82°.
  Side height H0.100, crown C0.052 and total O0.152 are **REF**, not MAX.
  The whole-metal crown/cone/fillet cap derives from F/G, the minimum
  permitted non-thread body diameter and fillet radius 15% basic diameter.
  The distinct first-full-thread cap uses the GO-ring bearing datum at
  maximum Class 2A major diameter, then two pitches; it does not charge
  the fillet twice. These are published standard geometry bounds, not
  new incoming gage procedures. The head-axis true-position diameter is
  6% maximum head diameter; stock straightness is 0.006 in/in.
  The oval **overall** length Lo=L+C receives the standard -0.03-in
  tolerance. With no positive crown REF credit, Lo MIN is 24.638 mm.
  The longer A199 raw stock leaves the factory-tip two-pitch region
  outside the retained cut screw. Custom plate clearance accommodates
  the maximum fillet; both arm tap entry and exit breaks are 0.10 mm MAX.
  Critical matched S-K, running-fit and signed seat/load inspections
  remain separate. No commodity stock-pair receipt, crown cap, q0 gauge,
  GO-profile procedure or pin-full-span body certificate is required.
  The purchased sheet retains its ordinary four-line stock/cut note.
  The populated page offered a 2-D PDF and required login for CAD;
  no availability or vendor 3-D claim is made. No vendor model is kept
  here, so this is catalogue-only with no replica gate.
  `diag_build_91790A199.py` is its supplied-stock diagnostic; production
  geometry is cut to the same installed shape.
- [91792A108](https://www.mcmaster.com/91792A108/) (`vn-guide-lock-screw`,
  MHA-VN-046, eight) replaces 91255A108 on October 11, 2026: the book's
  guide-lock plates (ch22 img05) show slotted heads, not hex sockets. The
  4-40 slotted family table was read live on October 11, 2026 (the product
  page needs a login): 18-8 stainless steel pan head slotted screw, #4-40 UNC
  class 2A, right hand, 3/8 in under the head, fully threaded, flat tip, head
  Ø0.219 in x 0.068 in, 100 ksi, ASME B18.6.3. The family table has no finish
  column and the product detail still needs a login on October 13, 2026, so
  the finish comes from two resellers that mirror McMaster's 91792A108 spec
  table (reli-tool.com and lily-bearing.com, read October 13, 2026): passivated,
  as for the other 18-8 slotted screws here. The 0.068 in head stands
  0.009 in prouder than the button head, so the guide lock is 1/16 in sheet
  as supplied rather than a 2.0 strip, which keeps the lock-station
  sweep clear of the transgear arm plate. The page gives no head profile, slot or tip, so
  `diag_build_91792A108.py` builds it on the shared slotted-head laws of
  `diag_mcmaster_fillister.py` (cylinder band 0.8 of the head height under a
  spherical-cap dome, slot 0.135 of the head Ø wide and 1.5 widths deep)
  [INFERENCE]; `_mcmaster_91792a108.py` holds its size. It is
  catalogue-only: no vendor model is downloaded or kept here, so it has no
  replica gate, and its standalone diagnostic is a catalog-only run. Lost:
  316 stainless 93923A353 (same head and length, 80 ksi, three times the
  price).
- [97431A260](https://www.mcmaster.com/97431A260/) (`vn-transgear-retaining-ring`,
  MHA-VN-047, R9-68) is pushed sideways into the MHA-PD-023 pin's groove in front
  of the MHA-PD-025 front bushing and closes the disc cluster's float. Its page
  was read live (user-pasted) on October 2, 2026: side-mount external ring
  for a 5/32 in shaft, phosphate-coated carbon steel, Rockwell C47 min,
  groove Ø0.116 in, ring O.D. 0.282 in, thickness 0.025 in ±0.002. The
  user-supplied vendor model was harvested on amet on October 2, 2026
  (`cad/out/reports/mcmaster-97431A260-dump.json`): one Right-plane outline
  (outer arc, three prongs on the Ø2.8956 "Free Diameter" circle, two
  relief arcs), one mid-plane extrude and two fillet sets (R0.4445 at the
  gap, R0.22225 at the prongs). `diag_build_97431A260.py` replays it and
  passed the replica gate on October 2, 2026: volume 13.3124 vs 13.3124 mm³,
  area 64.1486 vs 64.1486 mm², 26 faces each with the same face-area
  multiset (largest per-face delta 0.0000 mm²), centre of mass on the
  vendor's (`cad/out/reference/97431A260-replica-report.json`).
  Evidence SHA-256: native SLDPRT
  `dc3d0f8549d8851713aa234e24f338e9f0d41dbc96550669c281c99c3d9f4cff`.

- [9715K43](https://www.mcmaster.com/9715K43/) (`vn-transgear-pivot-spring`,
  MHA-VN-049, one) sits on the MHA-VN-041 pivot shoulder screw's shoulder, between
  the MHA-VN-069 shim under its head and the floor of the MHA-PD-018 arm's spot face, and
  preloads the arm forward onto the MHA-PD-020 spacer. Its page was read live on
  October 2, 2026 ("Curved Disc Springs, for 0.190" Shaft Diameter, 0.200"
  ID, 0.423" OD, 0.0113" Thick"): for a 0.190 in shaft, ID 0.200 in, OD
  0.423 in, thickness 0.0113 in, height 0.047 in; compressed height 0.027 in
  and deflection 0.020 in at the 9 lb working load; high-carbon steel, disc
  spring type "Curved"; pack of 10, $10.11. The page states no flat load and
  no rate (the spec's rate is the working point taken as linear
  [INFERENCE]), says the spring has "only two contact points", and that these
  springs cannot be stacked to raise the working load. It states no finish,
  only that moisture will rust the steel, so the part is taken as plain
  [INFERENCE] and carries the library's `Plain Carbon Steel`. The two
  contact points describe a bowed washer, which one revolve cannot make, so
  `diag_build_9715K43.py` models the axisymmetric cone spanning the same ID,
  OD and thickness [INFERENCE], shown as installed at the 0.80 mm nominal
  room under the screw head (between the 0.027 in working height and the
  free height): the outer edge at the OD from the OD rim's bearing face up
  one thickness, the inner edge at the ID up to that height. A 3-D
  SolidWorks model is offered on the page, but none was fetched or kept here,
  so it is catalogue-only: no replica gate, and its standalone diagnostic is
  a catalog-only run.
- [98055A098](https://www.mcmaster.com/products/din-988-shims/thickness~0-5-mm/shims-1~~/shims-4~performance~stress-resistant/)
  (`vn-transgear-pivot-shim`, MHA-VN-069, one) sits on the MHA-VN-041 shoulder
  under its head, on the MHA-VN-049 spring. The 9.5 support bar grew rearward
  0.5 (user ruling B, 2026-10-15), which carried the shoulder's end and the
  head 0.5 rearward; the shim takes that back so the spring keeps its room:
  0.80 nominal, 0.70 min, 1.0008 max against the spring's 0.6858 working and
  1.1938 free heights, a preload of 15.2-38.9 N. The page was read live on
  October 15, 2026: DIN 988 shim, stress-resistant spring steel, 5 mm ID x
  10 mm OD x 0.5 mm thick, thickness -0.05/0, ID 5.03-5.40, OD 9.53-9.96;
  pack of 50, $6.90. 98089A331 was rejected: its ±0.064 thickness leaves a
  0.636 minimum room, under the spring's working height.
  `diag_build_98055A098.py` models the annulus at nominal; no supplier CAD
  was harvested, so it is catalogue-only: no replica gate.

- [9714K392](https://www.mcmaster.com/9714K392/) (`vn-cylinder-bank-spring`,
  MHA-VN-052, one) sits on the MHA-DT-013 arbor between the front MHA-DT-026
  washer and the front MHA-DT-002 strap, set by a 0.95 blade, and holds the
  20-gear stack north on its datum (#948 ruling R). Its page was read live on
  October 9, 2026: Wave Disc Spring, steel, stackable; ID 0.385 in -0.01/+0.01,
  OD 0.5 in -0.01/+0.01, thickness 0.005 in, height 0.05 in (free); compressed
  height 0.024 in and deflection 0.026 in at the 1.5 lb working load; pack of
  10, $11.18. The page states no rate and no wave count (the spec's rate is
  the working point taken as linear [INFERENCE]); the part carries the
  library's `Plain Carbon Steel`.
- [9714K24](https://www.mcmaster.com/9714K24/) (`vn-rocker-bank-spring`,
  MHA-VN-053, one) sits on the MHA-CH-005 pivot shaft between the south
  MHA-VN-070 washer and the south MHA-CH-008 ear, set by a 0.60 blade, and holds the
  20-hub stack north on its datum. Its page was read live on October 9, 2026:
  Wave Disc Spring, high-carbon steel, stackable; ID 0.265 in -0.02/+0.01, OD
  0.367 in -0.02/+0.01, thickness 0.006 in, height 0.03 in (free); compressed
  height 0.015 in and deflection 0.015 in at the 3 lb working load; pack of 25,
  $16.31. The page states no rate, no wave count and no shaft size. The
  catalogue's minimum ID (6.22 mm) is under the 6.35 mm shaft, so each spring
  is slid onto MHA-CH-005 first and one that does not run free is rejected.
- Both are modelled as their installed envelope: `diag_build_9714K392.py` and
  `diag_build_9714K24.py` extrude the ID x OD annulus to the installed height
  (the set-blade gap) [INFERENCE: the waves are not modelled]. A 3-D
  SolidWorks model is offered on each page, but none was fetched or kept
  here, so both are catalogue-only: no replica gate, and their standalone
  diagnostics are catalog-only runs.
- [3088A429](https://www.mcmaster.com/3088A429/) (`vn-rocker-thrust-washer`,
  MHA-VN-070, two) rides the MHA-CH-005 pivot shaft at each end of the rocker
  bank: the north one between hub 19 and the datum MHA-CH-008 ear, the south
  one between hub 0 and the MHA-VN-053 spring. It replaced the custom
  MHA-CH-009 sheet washer (owner, 2026-10-15: every washer is a purchased
  part). The product page renders no spec table to a scraper, so the row was
  read live on October 15, 2026 from the round-shim family table
  (https://www.mcmaster.com/products/shims/shims-1~~/, Carbon Steel, 1/4" ID x
  3/8" OD): thickness 0.031 in +/-0.002 in, ID tolerance 0 to +0.011 in, OD
  tolerance -0.002 to +0.002 in, Rockwell B65 minimum, pack of 10. The
  0.031 in nominal keeps the bank's stand-offs within 0.003 of the retired
  0.79 washer; 3/8 OD is the only family OD under the Ø10.2 hub and the bar
  foot's cheeks, and the bore's 1/4 in floor is the shaft's maximum, so the
  shim slides on at worst line on line. The spring-steel 90482A512 (same size,
  0.032 in, Rockwell C44) was read live the same day and passed over because
  its 0.813 nominal moves both ears a further 0.023. `diag_build_3088A429.py`
  extrudes the ID x OD annulus at the 0.031 in nominal, with the bore at its
  band's middle (6.49) so the model does not sit line on line with the
  shaft. The page's CAD download was refused (HTTP 403), so it is
  catalogue-only: no replica gate, and its standalone diagnostic is a
  catalog-only run.

- [92671A005](https://www.mcmaster.com/92671A005/) (`vn-wheel-axle-nut`,
  MHA-VN-025, two), [92916A480](https://www.mcmaster.com/92916A480/)
  (`vn-wheel-axle-back-washer`, MHA-VN-057, one) and
  [92916A250](https://www.mcmaster.com/92916A250/)
  (`vn-wheel-axle-front-washer`, MHA-VN-058, one) carry the magnifying wheel
  on the 3/16 mg-wheel-axle (mg wheel rev 10). The back washer sits between
  the MHA-MG-011 axle spacer (on the mg-wheel-bar's front face) and the hub; the front washer sits on the
  #4-40 end against the spigot face, the first nut is run down until the
  wheel turns free without rattle (0.05-0.15 endshake) and the second jams
  it. All three pages were checked live on October 10, 2026: 92671A005 is a
  brass hex nut, ASME B18.2.2, #4-40, 1/4 in across flats, 3/32 in thick;
  92916A480 is a brass washer for #10, ID 0.200 in, OD 0.438 in, thickness
  0.029-0.043 in; 92916A250 is a brass washer for #4, ID 0.120 in, OD
  0.281 in, thickness 0.018-0.032 in. `diag_build_92671A005.py` extrudes the
  hexagon with a plain bore at the #4-40 basic major (the thread is not
  modelled); `diag_build_92916A480.py` and `diag_build_92916A250.py` extrude
  the ID x OD annulus at the range's nominal thickness. No vendor model was
  fetched, so all three are catalogue-only: no replica gate, and their
  standalone diagnostics are catalog-only runs.
- [91375A105](https://www.mcmaster.com/91375A105/) (`vn-pen-rod-set-screw`,
  MHA-VN-061, one) locks the pen rod's turned pivot end in the MHA-PN-005
  v-block, and [92671A115](https://www.mcmaster.com/92671A115/)
  (`vn-pen-adjust-nut`, MHA-VN-062, one) jams the #0-80 adjuster stud on the
  MHA-PN-004 pen rod's top. Both pages were read live in a browser on
  October 13, 2026. 91375A105 is an alloy steel cup-tip set screw, black
  oxide, 4-40 UNC Class 3A, 3/16 in long, 0.050 in hex drive, Rockwell C45,
  ASME B18.3 / ASTM F912; it is the MHA-VN-034 91375A106 cut 1/16 in shorter,
  so `diag_build_91375A105.py` imports every length-independent law from the
  vendor-verified `diag_build_91375A106.py` and changes only the length and
  helix height. 92671A115 is a brass hex nut, standard profile, 0-80 UNF
  Class 2B, 5/32 in across flats, 3/64 in high; `diag_build_92671A115.py`
  extrudes the hexagon with a plain bore at the #0-80 basic major. #0-80 is
  the stud thread because the 5 mm square rod keeps a 1.71 wall around it
  where #2-56 leaves 1.38 and #4-40 1.05, under the 1.5 floor of
  drawing-guidelines.md rule 17 (walls and webs). Each page offers only a
  2-D PDF, so both are catalogue-only: no replica gate, and their standalone
  diagnostics are catalog-only runs.
- [93075A199](https://www.mcmaster.com/93075A199/) (`vn-hanger-screw`,
  MHA-VN-007, one), [90480A009](https://www.mcmaster.com/90480A009/)
  (`vn-pen-hanger-nut`, MHA-VN-063, one) and
  [90760A009](https://www.mcmaster.com/90760A009/) (`vn-pen-hanger-jam-nut`,
  MHA-VN-064, one) hold the MHA-PN-002 pen hanger on the MHA-MG-008 wheel
  bar. All three were read live on October 14, 2026 (the nuts from the
  McMaster 8-32 hex-nut and narrow-profile hex-nut listings, whose product
  pages need a login). The 3.0 strap was a #8-32 tapped receiver for
  93075A194, under the 1.5D engagement of drawing-guidelines.md rule 18
  (thread engagement), so the strap now takes a #8 close-clearance hole and
  the thread is the nuts'. 90480A009 is a low-strength zinc-plated steel hex
  nut, ASME B18.2.2, 8-32, 11/32 in across flats, 1/8 in high; it bears on
  the strap front. 90760A009 is a zinc-plated steel narrow-profile
  (small-pattern) hex nut, 8-32 right-hand, 1/4 in across flats, 3/32 in
  high; it is jammed against 90480A009 as the joint's rule 23 lock.
  McMaster's only 8-32 thin-profile hex nuts are left-hand thread, so the
  thinner small-pattern nut is the jam nut. 93075A199 is the 93075A194
  family screw at 1 in (8-32 UNC Class 2A, fully threaded, flat tip, 1/4 in
  head width, 7/64 in head height, ASME B18.6.3). The family lists 8-32
  lengths of 3/8, 1/2, 5/8, 3/4, 1, 1-1/4 and 1-1/2 in; 7/8 in is not
  offered, and 3/4 in (93075A197) would leave 0.8 of full thread past the
  jam nut, under two pitches, once its tip chamfer is excluded. At 1 in,
  7.2 of full thread stands past the jam nut and the tip stops 3.2 short of
  the magnifying-wheel rim. `diag_build_93075A199.py` runs the shared
  hex-head family builder at the catalogue dimensions; no vendor solid is
  committed. Neither nut has a solid used here: `diag_build_90480A009.py`
  and `diag_build_90760A009.py` extrude the hexagon with a plain bore at the
  #8-32 basic major, so both are catalogue-only.
- [9666K56](https://www.mcmaster.com/9666K56/) supplies both amplification
  wires, `vn-lever-wire` (MHA-VN-066) and `vn-pen-wire` (MHA-VN-067), both
  cut from one coil. Their end terminations, wraps and developed cut lengths
  are not yet modelled, so both sheets stay DO NOT RELEASE. Read live
  on October 14, 2026: lubricated 1080 spring steel music wire, ASTM A228,
  cold drawn, spring temper, phosphate coated, 261,000 psi tensile, diameter
  0.031 in with -0.001/+0.001 in tolerance, 110 ft in a 1/4 lb coil;
  straightness is not rated. The models keep the Ø0.8 design nominal, which
  lies inside that 0.762-0.813 band (`_mcmaster_9666k56.py`, asserted by
  `vn_lever_wire_geom.py` and `vn_pen_wire_geom.py`). 8907K32, the same wire
  in 1 ft straight lengths, was rejected: the lever wire's straight rest run
  alone is about 353, longer than 304.8. McMaster offers no metric 0.8 music
  wire. No vendor solid is used; the wire is a plain cylinder.
- [90114A124](https://www.mcmaster.com/90114A124/)
  (`vn-ms-stop-plate-screw`, MHA-VN-054, two) retains the MHA-MS-003 plate
  on MHA-MS-002. The product table and 2-D PDF were read live on October 9,
  2026: brass, slotted fillister, #2-56 UNC-2A, fully threaded, flat tip;
  length 1/4 in, head diameter 0.140 in, head height 0.083 in, major diameter
  0.086 in, ASME B18.6.3, 50,000 psi, Rockwell B40, pack of 100 at $7.61.
  The brass fillister series starts at #2-56 (near M2); the existing brass
  90114A511 has a larger #4-40 / Ø0.183 in head, while the existing #0-80
  91794A055 is stainless, so neither meets this small brass joint.
  `_mcmaster_90114a124.py` owns the stated dimensions and the per-SKU size
  passed to the native fillister author, whose local `@stock_recipe` declaration
  identifies the threaded SKU without a shared recipe registry.
  `diag_build_90114A124.py` follows the existing catalogue-only
  `91794A077` fillister-family recipe: its dome, slot and thread/runout
  details are family assumptions, not measurements of a vendor solid.
  No vendor solid was downloaded and no replica equivalence is claimed.

- [3606T118](https://www.mcmaster.com/3606T118/) (`vn-keeper-chain`, MHA-VN-035)
  and [3606T811](https://www.mcmaster.com/3606T811/) (`vn-keeper-chain-link`,
  MHA-VN-036) tie the crank's taper pin to the arm as one loop through the eye
  and the ring. Both product pages were read on September 29, 2026. 3606T118 is
  unfinished brass bead chain, trade size 3, 3/32 in beads, 20 lbf, not for
  lifting. 3606T811 is the brass loop link that joins the cut ends into a loop.
  McMaster publishes no CAD for either item, and no dimension beyond the bead
  diameter. The 3.2426 mm pitch is the trade-size-3 average of 94 beads per foot
  (Ball Chain Mfg. and Frank Winne size charts). The link's 9 mm length is the
  listed #3 connector size, and its proportions (domed capsule, crimps, a side
  mouth over each dome narrower than a bead, rod slot along the top) are read
  off McMaster's 3606T811 photograph. The rod and the link's wall and openings are assumptions named in
  `vn_keeper_chain_spec.py`, so neither part has a replica gate.

- [6261K171](https://www.mcmaster.com/6261K171/) (`vn-chain-inner-link`,
  MHA-VN-002, and `vn-chain-outer-link`, MHA-VN-003) and
  [6261K108](https://www.mcmaster.com/6261K108/) (`vn-chain-connecting-link`,
  MHA-VN-068) are
  the paper-drive chain between the T12 and T24 MHA-PD-009 sprockets. Both
  product pages were read on October 14, 2026. Each states steel, single
  strand, ANSI 25, 1/4 in pitch, 0.130 in roller diameter, 1/8 in roller width
  and 140 lb working load; neither states a grade, plate size or coating.
  6261K171 is sold by the foot. The selected 68-pitch loop (17 in) is cut from
  2 ft with an inner link at each end. This gives 34 inner and 33 outer links;
  6261K108, the connecting link, closes the loop as its last outer link. The
  cut is the only modification, so all three identities stay VN
  (`cad/docs/subsystem-identities.md`). The modelled links are the clearance
  stand-ins in `_chain.py`, not vendor replicas. McMaster offers CAD for both
  items, but none was downloaded and no replica equivalence is claimed. Evidence:
  `C:/src/dt-logs/chain-links/mcmaster-skus.md`.

Ground rules (mirrored in the diagnostics themselves): the vendor files are
opened read-only and NEVER saved or modified; everything derived from them
(harvest dumps, replicas, renders, reports) goes only under the gitignored
`cad/out/`.

## Reference drawings

Each production part identity above has a registered `drawing:`
task, including identities that share a supplier SKU. The sheets show front,
top, right and isometric views, with the stock description and ordering SKU.
They are purchased-part identification sheets; their general tolerance and
edge-break notes do not apply.

For example, `uv run python build.py drawing:vn_knife_mount_dowel` writes
`cad/out/slddrw/vn-knife-mount-dowel.SLDDRW`,
`cad/out/pdf/vn-knife-mount-dowel.pdf` and
`cad/out/png/vn-knife-mount-dowel_drawing.png`. Run these tasks through the
pipeline so they acquire the shared SolidWorks seat lock.
