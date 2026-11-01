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
| 3088A429 | `ch-vn-rocker-thrust-washer` (MHA-CH-VN-56; catalogue-only, vendor model refused) | Carbon Steel Round Shim, 1/4" ID x 3/8" OD, 0.031" Thick |
| 3606T118 | `dt-vn-keeper-chain` (catalogue-only; no vendor model) | Bead Chain, Unfinished Brass, Trade Size 3 |
| 3606T811 | `dt-vn-keeper-chain-link` (catalogue-only; no vendor model) | Loop Link for Brass Trade Size 3 Bead Chain |
| 5972K41 | — (retired TL-VN-52, 2026-10-23; owned 6200-2RS shop stock, no jig identity) | Steel Ball Bearing |
| 6261K108 | `pd-vn-chain-connecting-link` (installed clearance stand-in; separate native supplier reference diagram) | Connecting Link for ANSI Number 25 Single Strand Roller Chain |
| 6261K171 | `sh-vn-chain-link` (MHA-SH-VN-50; `InnerLink` and `OuterLink` installed configurations; separate family reference diagram) | Roller Chain, Single Strand, ANSI Number 25, 1/4" Pitch |
| 6793K4 | `pd-transgear-removable` T12 (shop-reworked blank) | Steel ANSI #25 Plain-Bore Sprocket, 12 Teeth |
| 6793K11 | `pd-transgear-removable` T18 (shop-reworked blank) | Steel ANSI #25 Plain-Bore Sprocket, 18 Teeth |
| 6793K17 | `pd-transgear-removable` T24 (shop-reworked blank) | Steel ANSI #25 Plain-Bore Sprocket, 24 Teeth |
| 90114A124 | `ms-vn-stop-plate-screw`; `pd-vn-platen-clip-screw` until 2026-10-15 (catalogue-only; no vendor model) | Brass Fillister Head Slotted Screw |
| 90114A511 | `sh-vn-brass-fillister-screw` (MHA-SH-VN-51; shared by dt, fr and pd) | Brass Fillister Head Slotted Screw |
| 90126A211 | — (diagnostic recipe; the former `vn-knife-hanger-washer`, retired) | Zinc-Plated Steel SAE Washer |
| 90280A108 | `sh-vn-fillister-screw-90280a108` (MHA-SH-VN-52; shared by the dt foot and swing-stop roles and the pd latch-hook screws) | Steel Narrow Fillister Head Slotted Screw |
| 90280A194 | — (diagnostic recipe; a former `ch-vn-frame-side-screw`) | Steel Narrow Fillister Head Slotted Screw |
| 90280A196 | `ch-vn-bracket-hold-down-screw` | Steel Narrow Fillister Head Slotted Screw |
| 90280A197 | `dt-vn-pedestal-hold-down-screw` | Steel Narrow Fillister Head Slotted Screw |
| 90280A199 | — (diagnostic recipe; a former `dt-vn-swing-stop-screw`) | Steel Narrow Fillister Head Slotted Screw |
| 90280A201 | `sh-vn-clamp-screw` (MHA-SH-VN-53; shared by mg and pd) | Steel Narrow Fillister Head Slotted Screw |
| 90280A203 | `dt-vn-slotted-screw` | Steel Narrow Fillister Head Slotted Screw |
| 90280A837 | `fr-vn-frame-cross-screw` | Steel Narrow Fillister Head Slotted Screw |
| 90480A009 | `pn-vn-pen-hanger-nut` (catalogue-only; no vendor model) | Low-Strength Zinc-Plated Steel Hex Nut |
| 90760A009 | `pn-vn-pen-hanger-jam-nut` (catalogue-only; no vendor model) | Zinc-Plated Steel Narrow-Profile Hex Nut |
| 90760A140 | `sm-vn-boss-hook-jam-nut` (MHA-SM-VN-55; catalogue-only, no vendor model) | Zinc-Plated Steel Narrow-Profile Hex Nut |
| 91247A720 | — (diagnostic recipe; a former `sm-vn-knife-hanger-stud`) | Medium-Strength Grade 5 Steel Hex Head Screw |
| 91251A108 | `dt-vn-cone-tip-block-screw` (catalogue-only; no vendor model) | Black-Oxide Alloy Steel Socket Head Screw |
| 91251A157 | — (catalogue-only diagnostic recipe; former `sm-vn-knife-hanger-stud`) | Black-Oxide Alloy Steel Socket Head Screw |
| 91251A188 | — (retired TL-VN-63, 2026-10-23; former catalogue-only diagnostic recipe removed) | Black-Oxide Alloy Steel Socket Head Screw |
| 91251A196 | `ch-rocker-arm-tl-vn-oblique-bracket-screw` (MHA-CH-06-TL-VN-62; shop fixture; catalogue-only, vendor model read for dimensions, not replica-gated) | Socket Head Screw |
| 91251A197 | `ch-rocker-arm-tl-vn-oblique-rail-screw` (MHA-CH-06-TL-VN-61; shop fixture; catalogue-only, vendor model read for dimensions, not replica-gated) | Socket Head Screw |
| 91251A541 | `ch-rocker-arm-tl-vn-oblique-clamp-screw` (MHA-CH-06-TL-VN-68; shop fixture; catalogue-only, no vendor model; installed at bought 7/8 in length) | Socket Head Screw |
| 91251A583 | `ch-rocker-arm-tl-vn-oblique-lever-screw` (MHA-CH-06-TL-VN-69; shop fixture; catalogue-only, product page login-walled, the 7/8 in sibling's vendor model read for dimensions, not replica-gated) | Socket Head Screw |
| 91812A215 | — (retired TL-VN-70, 2026-10-23; jig-only diagnostic recipe removed) | Extreme-Vibration-Resistant Wedge Lock Washer |
| 91812A230 | `ch-rocker-arm-tl-vn-oblique-lever-washer` (MHA-CH-06-TL-VN-71; shop fixture; catalogue-only, product page login-walled, no vendor model) | Extreme-Vibration-Resistant Wedge Lock Washer |
| 90323A492 | `ch-rocker-arm-tl-vn-oblique-pivot-screw` (MHA-CH-06-TL-VN-77; purchased datasheet model) | 18-8 Precision Shoulder Screw, Ø10 × 35, M8 × 1.25 |
| 92871A359 | `ch-rocker-arm-tl-vn-oblique-pivot-spacer` (MHA-CH-06-TL-VN-78; purchased datasheet model) | 18-8 Round Spacer, 10 ID × 16 OD × 15 |
| 98055A118 | `ch-rocker-arm-tl-vn-oblique-pivot-shim` (MHA-CH-06-TL-VN-79; 98055A117/98055A121 fitting stock) | DIN 988 Spring Steel Shim, 10 × 16 × 0.2 |
| 2281A11-6410N695 | `ch-rocker-arm-tl-vn-oblique-hub-pin` (MHA-CH-06-TL-VN-80; abrasive-cut to 20.0, factory end up) | Class Z Minus Gauge Pin, Ø10.2000, 2 in supply |
| 91255A106 | — (diagnostic recipe; a former `pd-vn-guide-lock-screw`) | Black-Oxide Alloy Steel Button Head Hex Drive Screw |
| 91255A148 | — (diagnostic recipe; a former `dt-vn-cone-tip-block-screw`) | Black-Oxide Alloy Steel Button Head Hex Drive Screw |
| 91251A150 | `ch-rocker-arm-tl-vn-oblique-kp08-screw` (MHA-CH-06-TL-VN-65; shop fixture; catalogue-only, product page login-walled, no vendor model) | Black-Oxide Alloy Steel Socket Head Screw |
| 91290A168 | `ch-rocker-arm-tl-vn-oblique-carriage-screw` (MHA-CH-06-TL-VN-64; shop fixture; catalogue-only, vendor model read for dimensions, not replica-gated) | Socket Head Screw |
| 90325A174 | `pd-vn-transgear-pivot-screw` (catalogue-only; CAD download refused) | 18-8 Stainless Steel Precision Shoulder Screw, hex socket |
| 91375A105 | `pn-vn-pen-rod-set-screw` (catalogue-only; no vendor model) | Alloy Steel Cup-Tip Set Screw |
| 91375A106 | `sh-vn-arbor-set-screw` (MHA-SH-VN-54; shared by ch and dt) | Alloy Steel Cup-Tip Set Screw |
| 91375A942 | `ch-vn-fulcrum-set-screw` (catalogue-only; no vendor model) | Alloy Steel Cup-Tip Set Screw |
| 91410A538 | — (diagnostic recipe; `fr-vn-gooseneck-set-screw` until 2026-10-12) | Steel Square-Head Cup-Point Set Screw |
| 91410A540 | `fr-vn-gooseneck-set-screw` (catalogue-only; no vendor model) | Steel Square-Head Cup-Point Set Screw |
| 91595A452 | `ch-rocker-arm-tl-vn-oblique-cl-dowel` (MHA-CH-06-TL-VN-53; shop fixture; catalogue-only, vendor model read for dimensions, not replica-gated) | Dowel Pin |
| 91771A112 | `ch-rocker-arm-tl-vn-oblique-riser-screw` (MHA-CH-06-TL-VN-67; shop fixture; catalogue-only, same-family vendor geometry, not replica-gated) | Stainless Steel Phillips Flat Head Screw |
| 91790A199 | `pd-vn-transgear-arm-plate-screw` (catalogue-only; populated live SKU verified; 2-D PDF offered, CAD requires login) | 18-8 Stainless Steel Oval Head Slotted Screw |
| 91792A108 | `pd-vn-guide-lock-screw` (catalogue-only; no vendor model) | 18-8 Stainless Steel Pan Head Slotted Screw |
| 91794A112 | `dt-vn-cone-tip-pinch-screw` | 18-8 Stainless Steel Fillister Head Slotted Screw |
| 91794A055 | `pd-vn-transgear-disc-screw` | 18-8 Stainless Steel Fillister Head Slotted Screw |
| 91794A078 | `mg-vn-magnifying-bracket-screw` (catalogue-only; no vendor model) | 18-8 Stainless Steel Fillister Head Slotted Screw |
| 91794A080 | `ch-vn-frame-side-screw` (catalogue-only; no vendor model) | 18-8 Stainless Steel Fillister Head Slotted Screw |
| 92240A540 | `fr-vn-lag-screw` | 18-8 Stainless Steel Hex Head Screw |
| 91829A560 | `dt-vn-cone-pivot-screw` | Slotted 18-8 Stainless Steel Precision Shoulder Screw |
| 92314A253 | `sm-vn-knife-hanger-stud` (modified stock; catalogue-only, no vendor model) | 18-8 Stainless Steel Hex Head Screw, #10-24 × 2 in, cut to length |
| 92446A077 | `pd-vn-platen-clip-screw` (catalogue-only; no vendor model) | Brass Pan Head Slotted Screw |
| 91882A221 | `sh-vn-thumb-screw` (MHA-SH-VN-55; shared by mg and ms) | Steel Raised Knurled-Head Thumb Screw |
| 91882A425 | — (diagnostic recipe; `dt-vn-cone-lock-knob` until 2026-09-29) | Steel Raised Knurled-Head Thumb Screw |
| 9275K141 | `fr-vn-tube-frame-cap` | Metal Round Cap |
| 92671A005 | `mg-vn-wheel-axle-nut` (catalogue-only; no vendor model) | Brass Hex Nut |
| 92671A115 | `pn-vn-pen-adjust-nut` (catalogue-only; no vendor model) | Brass Hex Nut |
| 9414T1 | — (the purchased cone-tip collar, category MHA-VN-016, now MHA-DT-VN-54, until the 2026-10-08 terminal redesign) | Set Screw Shaft Collar for 1/16" Diameter |
| 94355A213 | `dt-vn-cone-tip-collar` set screw, fitted as supplied | 18-8 Stainless Steel Flat-Tip Set Screw, #2-56 x 5/16" |
| 92865A585 | — (diagnostic recipe; former `vn-hex-bolt`, MHA-VN-008 retired) | Medium-Strength Grade 5 Steel Hex Head Screw |
| 92916A250 | `mg-vn-wheel-axle-front-washer` (catalogue-only; no vendor model) | Brass Washer for Number 4 Screw Size |
| 96659A104 | `sm-vn-knife-hanger-washer` (MHA-SM-VN-54; catalogue-only, no vendor model) | 18-8 Stainless Steel SAE Washer for Number 10 Screw Size |
| 92916A480 | `mg-vn-wheel-axle-back-washer` (catalogue-only; no vendor model) | Brass Washer for Number 10 Screw Size |
| 93075A194 | — (diagnostic recipe; `pn-vn-hanger-screw` until the 2026-10-14 through-strap nut stack) | Low-Strength Zinc-Plated Steel Hex Head Screw |
| 93075A199 | `pn-vn-hanger-screw` | Low-Strength Zinc-Plated Steel Hex Head Screw |
| 93585A190 | `dt-vn-cone-lock-knob` | Stainless Steel High-Profile Knurled-Head Thumb Screw |
| 94025A150 | — (diagnostic recipe; `dt-vn-cone-tip-adjuster` until drawing-guidelines.md rule 18 (thread engagement) E11) | 18-8 Stainless Steel Slotted Cup-Tip Set Screw |
| 94025A164 | `dt-vn-cone-tip-adjuster` | 18-8 Stainless Steel Slotted Cup-Tip Set Screw |
| 93600A189 | `pd-vn-transgear-arm-plate-locating-pin` (catalogue-only; no vendor model) | Passivated 316 Stainless Steel ISO 2338-m6 Dowel Pin |
| 9666K56 | `sh-vn-music-wire` (MHA-SH-VN-56; `LeverWire` and `PenWire` configurations cut from one coil; catalogue-only, no vendor model) | Lubricated 1080 Spring Steel Wire, 0.031 in, 1/4 lb coil |
| 9714K24 | `ch-vn-rocker-bank-spring` (catalogue-only; no vendor model) | Wave Disc Spring |
| 9714K392 | `dt-vn-cylinder-bank-spring` (catalogue-only; no vendor model) | Wave Disc Spring |
| 9715K43 | `pd-vn-transgear-pivot-spring` (catalogue-only; no vendor model) | Curved Disc Spring |
| 97431A260 | `pd-vn-transgear-retaining-ring` | Side-Mount External Retaining Ring |
| 98055A098 | `pd-vn-transgear-pivot-shim` (MHA-PD-VN-67; catalogue-only, no vendor model) | DIN 988 Shim, Stress-Resistant Spring Steel |
| 98296A026 | — (diagnostic recipe; former `vn-transgear-collar-cross-pin`, MHA-VN-037 retired) | 1050-1095 Spring Steel Slotted Spring Pin |
| 98296A027 | `dt-vn-pinion-strap-pin` | 1050-1095 Spring Steel Slotted Spring Pin |
| 98296A031 | `pd-vn-transgear-knob-cup-pin` | 1050-1095 Spring Steel Slotted Spring Pin |
| 98381A433 | `pd-vn-transgear-knob-drive-pin` (catalogue-only; no vendor model) | Alloy Steel Dowel Pin |
| 98381A434 | `dt-vn-crank-seat-drive-pin` (crank only; catalogue-only; no vendor model) | Alloy Steel Dowel Pin |
| 98381A473 | `sm-vn-knife-mount-dowel` | Alloy Steel Dowel Pin |
| 98381A474 | `pd-vn-transgear-latch-pin` (catalogue-only; no vendor model; SKU not yet read live) | Alloy Steel Dowel Pin |
| 99607A213 | `pn-vn-pen-set-screw` | Stainless Steel Flared-Collar Knurled-Head Thumb Screw |

The cone-lock selection follows `cad/scripts/build_dt_vn_cone_lock_knob.py`; the
swing-stop selection rationale lives in `cad/scripts/dt_swing_stop_screw_spec.py`, and the shared 90280A108 screw it selects is built by `cad/scripts/build_sh_vn_fillister_screw_90280a108.py` (the swing-stop's placement is applied in its `dt-drive-train` occurrence).

Historical October 17, 2026 oblique-jig sourcing follows below, including
subsequently retired parts. Vendor models were read for dimensions only;
by the user ruling of that date none was replica-gated and no copy is kept here.
Use the current registry table above for active purchases.

Historical sourcing record: TL-VN-52 was retired on 2026-10-23. The following
dated bearing/cartridge description is provenance, not the current jig design;
its dimension provider and diagnostic recipe have also been removed.

- [5972K41](https://www.mcmaster.com/5972K41/) (`ch-rocker-arm-tl-vn-oblique-bearing`,
  MHA-CH-06-TL-VN-52, four: a pair in each oblique-trammel jig pivot block) was
  read live on October 17, 2026 and rechecked in the live Product Detail table
  on October 21, 2026: steel ball bearing, sealed (Buna-N), trade no. 6200-2RS,
  ID 10 mm -0.008/0, OD 30 mm -0.009/0, width 9 mm -0.12/0, ABEC 1,
  C3 radial clearance 0.008-0.023 mm, DIN 625-1. These are SKU-specific
  supplier dimensions, not tolerances inferred from the ABEC label or CAD.
  `_mcmaster_5972k41` owns the pure purchased size bands; the pin and block
  fits consume its bore and OD deviations. The supplier's generic Width
  does not separately specify race widths or bound internal axial play.
  No whole-bearing captured-motion enclosure follows from that width.
  The vendor model was downloaded from the product page on October 17, 2026
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
  The VN-52 purchased drawing owns OD 29.991–30.000 mm, width 8.88–9.00 mm
  and the function-required intact full-circumference cylindrical OD land,
  including its axial mid-plane, for the TL-22 pivot-block capture. Before
  pressing, trace the actual bearing's identity to valid supplier dimensional
  authority and physically inspect that land. Catalogue size authority can
  establish those bands without redundant micrometer records of every
  catalogue dimension; CAD alone cannot accept the delivered profile, and no
  maximum supplied chamfer is asserted. Assembly C1 uses qualified VN-52
  bearings and retains the ring-loading press actions, not repeated part
  tolerances. Capture qualification still requires explicit receiving status
  and evidence for the same actual support on both passes. Possession and
  receiving qualification remain unconfirmed; the inventory is not marked
  accepted by this catalogue recheck.
- [91595A452](https://www.mcmaster.com/91595A452/) (`ch-rocker-arm-tl-vn-oblique-cl-dowel`,
  MHA-CH-06-TL-VN-53, one: the oblique trammel jig carrier's CL locator) was
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
  Installation uses this same purchased pin, press-set from the actual riser
  top rather than flush with the carrier underside (#1619). The assembly
  setup height leaves cylindrical strap overlap and at least 1.5D press
  contact over the finished plate bands; normal fit-up checks that the strap
  seats flat, locates and slips on/off without the tip standing above it.
  It also supplies `fixtures.trammel-cl-dowel`; length tolerance unstated.
  Both purchases remain unconfirmed in `cad/process/shop/inventory.toml`.
- [91251A197](https://www.mcmaster.com/91251A197/)
  (`ch-rocker-arm-tl-vn-oblique-rail-screw`, MHA-CH-06-TL-VN-61, 14 in the oblique
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
  (`ch-rocker-arm-tl-vn-oblique-bracket-screw`, MHA-CH-06-TL-VN-62, 8 in the oblique
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
Historical sourcing record: TL-VN-63 was retired on 2026-10-23 when the nut
lug became integral with TL-32. The following describes the former joint.

- [91251A188](https://www.mcmaster.com/91251A188/)
  (`ch-rocker-arm-tl-vn-oblique-block-screw`, MHA-CH-06-TL-VN-63, 2 in the oblique
  trammel jig: the fastener table's `NUT_BRACKET_TO_BLOCK` row) was read live on
  October 17, 2026 from the #8-32 black-oxide listing: #8-32 coarse, 1-7/8 in
  under the head, partly threaded (7/8 in thread, the single-product 1-7/8
  filter page's only Thread Length facet), head Ø0.27 x 0.164 in, 9/64 in hex
  drive, 170,000 psi, US origin, $11.00 per pack of 10. It replaced a 1-3/4 in
  screw once the TL-VN-70 wedge-lock pair went under each head: at the worst-case
  bands (ASME B18.3's -0.04 in length tolerance, TL-22's width and counterbore
  bands, the pair's 0.080-0.100 in stack) it engages TL-29 7.83 to 10.63, over
  1.5 D and inside the 12 full thread and its own 7/8 in thread.
  TL-29's unused upper material is cut to 33.3 mm height at the ordinary
  .X ±0.8 mm band, independent of the raised carrier: nominal bottom/top
  Z = 27.4/60.7 mm. Its XY placement, nut axis Z = 40.4 mm, side holes,
  3/4 × 2 in stock and leadline are unchanged, as are this screw and washer
  pair. F1/F2 on TL-00's cartridge sheet require the actual TL-22 side-hole axes at least
  5.0 mm below the actual TL-29 top before transfer punching, and the
  entire actual bracket top, including high corners, at least 2.35 mm below
  the actual TL-22 cap mounting plane after free-feed alignment and final
  tightening throughout travel. Do not force nut/screw alignment to obtain
  this gap or substitute invented HGH/KP08/end-bracket STOCK height bands.
  See the [captured-pivot fit-up acceptance](../../docs/subsystem-identities.md#oblique-jig-captured-pivot-tooling);
  this material cut is not a new native certificate or a cap relief.
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
  (`ch-rocker-arm-tl-vn-oblique-carriage-screw`, MHA-CH-06-TL-VN-64, 8 in the oblique
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
- [91251A150](https://www.mcmaster.com/91251A150/)
  (`ch-rocker-arm-tl-vn-oblique-kp08-screw`, MHA-CH-06-TL-VN-65, 4 in the oblique
  trammel jig: the fastener table's `KP08_TO_BRACKET` row) was read live on
  October 19, 2026 from the #6-32 x 5/8 in black-oxide socket head screw
  listing (https://www.mcmaster.com/products/socket-head-screws/steel-socket-head-screws~~/thread-size~6-32/finish~black-oxide/length~5-8-1/;
  the product page is login-walled): #6-32 UNC, 5/8 in under the head, fully
  threaded, head Ø0.226 x 0.138 in, 170,000 psi, US origin, $12.27 per pack
  of 100. It replaced the M4 x 12 mm 91290A148 when issue #1630 moved TL-28's
  KP08 taps to #6-32 UNC (fastener policy); 5/8 is the shortest length giving
  2D of full thread at the worst case (rule 18's 1.5D with half a diameter for
  the KP08 foot's unverified thickness), its tip 1.8 inside TL-28's THRU tap.
  The row gives no drive or socket depth, so the model takes the family's #6
  hex, 7/64 in, ASME B18.3's minimum key engagement for #6, 0.064 in (the
  91251A108 convention), and ASME B18.3's -0.03 in length tolerance (up to 1
  in long).
  `diag_build_91251A150.py` builds it from those catalogue values on the 91251A
  family recipe (`diag_mcmaster_socket_head.build_socket_head`: plain
  cylindrical head, 0.75P tip chamfer, 45 deg thread neck; bearing face at y =
  0, tip at y = -length), fully threaded. No vendor model was downloaded (the
  product page is login-walled), so it is not replica-gated: the standalone run
  is catalogue-only (it builds the recipe, checks the solid and saves it under
  `cad/out/reference`).
- [91771A112](https://www.mcmaster.com/91771A112/)
  (`ch-rocker-arm-tl-vn-oblique-riser-screw`, MHA-CH-06-TL-VN-67, 4 in the oblique
  trammel jig: the fastener table's `RISER_TO_CARRIER` row) was read live on
  October 19, 2026: 18-8 stainless steel, passivated, Phillips No. 1 drive,
  standard 82 deg flat head Ø0.212 x 0.067 in, #4-40 UNC class 2A, 5/8 in
  overall (McMaster measures a flat head from its top), fully threaded, flat
  tip, Rockwell B80, 80,000 psi, ASME B18.6.3, $7.44 per pack of 100.
  The model is catalogue first: the thread, the overall length, the head Ø0.212
  in, the 82 deg angle and the 0.067 in head height (where the thread ends) are
  the catalogue's. Its former 1/2 in sibling 91771A110's vendor model was
  downloaded from that sibling's product page on October 17, 2026 (SLDPRT, SHA-256
  `170dc7d8be906f2614181b0cac013ec2542eb37e93de45b40885ff555ae5f6ab`; its STEP,
  SHA-256 `588000b51c99935744bdd79b93fb8269cb27932f2e6086338d23bf51f9269a27`)
  and read for dimensions only; no copy is kept here. Where the new page is
  silent (the Phillips No. 1 recess form, the tip chamfer), the unchanged
  same-family recipe retains that sibling reading (FreeCAD 1.1):

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

  `diag_build_91771A112.py` builds it on the Phillips flat head family recipe
  (`diag_mcmaster_phillips_flat_head`: no existing family draws a flat top with
  a cross recess), the flat top at y = 0, tip at y = -length. It is NOT
  replica-gated (user ruling, October 17, 2026): the standalone run is
  catalogue-only (it builds the recipe, checks the solid and saves it under
  `cad/out/reference`).
  The assembly seats the head on the riser's nominal countersink, rather than
  incorrectly holding its top flush. The longer screw needs no nominal cut;
  the factory tip is retained unless actual interference prevents assembly.
  No new vendor STEP measurement or receipt limits are claimed.
- [91251A541](https://www.mcmaster.com/91251A541/)
  (`ch-rocker-arm-tl-vn-oblique-clamp-screw`, MHA-CH-06-TL-VN-68, 1 in the oblique
  trammel jig: the fastener table's `CR_CLAMP` row) was read live on
  October 19, 2026: black-oxide alloy steel, 1/4-20 UNRC class 3A, 7/8 in
  under the head, fully threaded, flat tip, head Ø3/8 x 1/4 in, 3/16 in hex,
  Rockwell C37, 170,000 psi, ASTM A574, $13.42 per pack of 50.
  The page gives no socket depth, so the model takes ASME B18.3's minimum key
  engagement for 1/4, 0.120 in (the 91251A108 convention).
  `diag_build_91251A541.py` builds the bought screw on the catalogue 91251A
  family recipe: plain cylindrical head, 0.75P factory tip chamfer, 45 deg
  thread neck. No vendor model was downloaded or measured for this SKU.
  The standalone diagnostic remains catalogue-only, not replica-gated.
  The production build retains the bought 7/8 in length. Its nominal 1.725
  projection below the through-tapped carrier is clear of the rails and the
  pivot blocks; even the 3.350 maximum plate-stack projection clears.
  Do not shorten a tip merely for appearance or because it is proud:
  rework only if actual interference prevents assembly. No plate band,
  receipt limit or short-engagement exception is added.
- [91251A583](https://www.mcmaster.com/91251A583/)
  (`ch-rocker-arm-tl-vn-oblique-lever-screw`, MHA-CH-06-TL-VN-69, 2 in the oblique
  trammel jig: the fastener table's `LEVER_TO_CARRIER` row) was read live on
  October 17, 2026 from the 5/16-18 x 1 in socket head screw listing (the
  product page is login-walled): 5/16-18 UNC, 1 in under the head, fully
  threaded, head Ø15/32 x 5/16 in, 170,000 psi, $15.30 per pack of 50; the
  family's 1/4 in hex, class 3A, Rockwell C37 and ASTM A574 are the 7/8 in
  sibling 91251A582's page, read live the same day. It replaced 91251A582
  when the TL-VN-71 wedge-lock pair entered the grip.
  The listing gives no socket depth, so the model takes ASME B18.3's minimum key
  engagement for 5/16, 0.151 in (the 91251A108 convention).
  `diag_build_91251A583.py` builds it from those catalogue values on the 91251A
  family recipe (`diag_mcmaster_socket_head.build_socket_head`: plain
  cylindrical head, 0.75P tip chamfer, 45 deg thread neck; bearing face at y =
  0, tip at y = -length). No vendor model was downloaded for this length; the
  7/8 in sibling's (SLDPRT SHA-256
  `9feed1cd8f28f698a03478549d6f0a70b5bc99916c1e8199b3d9857b4c99b5c7`; its STEP,
  SHA-256 `1e7b1c0ae31b76b34ea88254712024f5851b9fd953af801f633caf292272d940`)
  was read for dimensions only; no copy is kept here. It shows a hex socket
  0.15625 in deep and a 50-groove knurled head, a 60 deg socket entry
  countersink, a 20 deg thread runout cone and a 0.6P tip chamfer, which the
  family recipe does not draw. It is NOT replica-gated (user ruling, October 17,
  2026): the standalone run is catalogue-only (it builds the recipe, checks the
  solid and saves it under `cad/out/reference`).
Historical sourcing record: TL-VN-70 was retired on 2026-10-23 with its only
joint. The diagnostic mentioned below was removed; this is not a live recipe.

- [91812A215](https://www.mcmaster.com/91812A215/)
  (`ch-rocker-arm-tl-vn-oblique-block-washer`, MHA-CH-06-TL-VN-70, 2 pairs in
  the oblique trammel jig: the fastener table's `BLOCK_LOCK_WASHER` row, one
  pair under each TL-VN-63 block screw head) was read live on October 17, 2026
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
- [91812A230](https://www.mcmaster.com/91812A230/)
  (`ch-rocker-arm-tl-vn-oblique-lever-washer`, MHA-CH-06-TL-VN-71, 2 pairs in
  the oblique trammel jig: the fastener table's `LEVER_LOCK_WASHER` row, one
  pair under each TL-VN-69 feed lever screw head) was read live on October 17,
  2026 from the wedge-lock listing; the product page and its 2-D PDF are
  login-walled. Two-piece wedge-lock washer, reusable up to 15 times,
  comparable to NORD-LOCK; 316 stainless steel, Rockwell C51, case hardened;
  for 5/16" / M8; ID 0.340 in, OD 0.530 in, thickness 0.070 to 0.090 in;
  5 per package, $12.40. UNVERIFIED: the listing does not say whether the
  thickness is the pair's stack or one washer's, nor whether a package is 5
  pairs; the model takes the band as the pair's stack at its 0.090 in
  maximum. `diag_build_91812A230.py` builds the pair's envelope, one plain
  annulus from y = 0 along +Y (no cam faces, serrations or split). No vendor
  model was downloaded, so it is not replica-gated: the standalone run is
  catalogue-only (it builds the recipe, checks the solid and saves it under
  `cad/out/reference`).

### Historical non-McMaster captured-pivot purchases (retired 2026-10-23)

These identities belonged to the former captured-pivot cartridge. They are
retired, their Numbers are never reissued, and none is a current jig purchase
or assembly instruction. Primary supplier pages were read on October 20, 2026.

| Retired Number | Former installed quantity | Supplier identity and primary source |
|---|---:|---|
| MHA-CH-06-TL-VN-73 | 8 | CBS Fasteners [NAS1352N5H12](https://cbsfasteners.com/nas-fastener-inventory/), “5/16-18 X 3/4 SHC A286 DRLD”; [NAS1352 dimensions](https://www.aaestore.com.au/media/specs/NAS1352.pdf) |
| MHA-CH-06-TL-VN-74 | 2 | Huyett [CLPS6-0187-1250D](https://www.huyett.com/clps6-0187-1250d), 3/16 × 1-1/4 in headed clevis pin, 316 stainless |
| MHA-CH-06-TL-VN-75 | 2 | Huyett [CP-062-0500](https://www.huyett.com/cp-062-0500), 1/16 × 1/2 in split cotter |
| MHA-CH-06-TL-VN-76 | 4 formed pieces | Aircraft Spruce [05-02685](https://www.aircraftspruce.com/catalog/appages/safetywire.php), 0.032 in soft 302/304 stainless, MS20995; [catalogue](https://www.aircraftspruce.com/pdf/2027Individual/Cat270142.pdf) |

The current plain-pivot identities and Number reservations are documented in
[subsystem identities](../../docs/subsystem-identities.md#oblique-jig-plain-pivot-tooling).


Live catalogue verification on October 12, 2026:

- [91410A540](https://www.mcmaster.com/91410A540/) replaces 91410A538 as the
  MHA-FR-VN-52 gooseneck set screw, per the user's Q5 ruling of October 12,
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
  MHA-PD-VN-65 platen-clip screws, is titled “Brass Fillister Head Slotted
  Screws, 2-56 Thread Size, 1/4" Long”. The live page and
  [technical drawing](https://www.mcmaster.com/mvD/Library/CAD2/20260619/961C5808/90114A124_Brass%20Fillister%20Head%20Slotted%20ScrewsS.GIF)
  were viewed on October 11, 2026: brass, Rockwell B40, 50,000 psi tensile
  strength, #2-56 UNC class 2A, fully threaded, flat tip, ASME B18.6.3,
  high narrow slotted fillister head. Under-head length is 0.25 in
  (6.35 mm), screw size decimal 0.086 in (2.1844 mm), head diameter
  0.14 in (3.556 mm), and head height 0.083 in (2.1082 mm). The drawing
  states no dimensional tolerances. Brass matches the book photograph's
  brass clip screws, so the same-size 18-8 stainless 91794A077 (then MHA-MG-VN-53's
  stock) is rejected for appearance; no brass #2-56 shorter than 1/4 in was
  found live. The #4-40 brass fillister 90114A511 of MHA-SH-VN-51 (then MHA-DT-VN-50, MHA-FR-VN-50 and MHA-PD-VN-52) is
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
  selected for the MHA-MS-VN-51 stop-plate screws.
- [92446A077](https://www.mcmaster.com/92446A077/) (`pd-vn-platen-clip-screw`,
  MHA-PD-VN-65, four) replaces 90114A124 on October 15, 2026 (user ruling: a
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
  MHA-CH-VN-55 fulcrum-shaft set screws (one per MHA-CH-07 keeper crown, on
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
  before it, 90280A194) as the two MHA-CH-VN-52 frame-side screws that hold the
  fulcrum keepers' feet. The
  [public #2-56 fillister family table](https://www.mcmaster.com/products/fillister-head-machine-screws/thread-size~2-56/?s=fillister-head-machine-screws)
  was read live in a browser on October 10, 2026: in the “Stainless Steel
  Fillister Head Slotted Screws” table, length **7/16 in**, head diameter
  **0.14 in**, head height **0.083 in**, **Fully Threaded**, tensile strength
  **70,000 psi**, package quantity **100**. The 90280A steel family has no
  #2-56 size. The smaller thread follows the transferred top-frame tap: the
  #4-40 tap left too thin a drawing-guidelines.md rule 17 (walls and webs) ligament under the keeper foot. The head
  and thread are the 91794A077/91794A078 rows', so the shared fillister recipe builds it
  from the length alone; no vendor SLDPRT has been harvested for it.
  `diagnostics.diag_build_90280A194` stays as a diagnostic recipe.

Live catalog verification on October 16, 2026:

- [91794A078](https://www.mcmaster.com/91794A078/) replaces 91794A077 as the
  two MHA-MG-VN-53 magnifying-bracket screws (owner ruling, October 16, 2026).
  The live page was read on October 16, 2026: 18-8 stainless fillister head
  slotted screw, #2-56 thread, 5/16 in long, fully threaded, head diameter
  0.14 in (3.556 mm), head height 0.083 in (2.1082 mm), $6.55 per pack of 100.
  The vendor [SLDPRT](https://www.mcmaster.com/mvC/Library/CAD2/20260108/53AE5A4D/91794A078_18-8%20Stainless%20Steel%20Fillister%20Head%20Slotted%20Screw.SLDPRT)
  link was seen but not harvested; the part stays catalogue-only.
  Machinist review r1 of MHA-MG-01 found the Ø3.8 × 1.55 ±0.05 counterbore's
  depth band rescued a wall, so the bracket drops the counterbore: the heads
  bear on the 1/8 in stock flange's front face over plain normal #2 Ø2.591
  thru holes, and the flange prints 3.175 at the title block's .XXX ±0.13.
  Grip 3.175 (3.045 minimum) leaves 4.7625 mm engagement nominal, 3.305 mm
  worst case (above 1.5D, 3.2766 mm), with a 0.0067 mm minimum screw-tip gap
  in the native 4.95 ±0.0508 full-thread model (printed **.195 MIN**, not an
  upper cutting/thread-extent limit). Brass was rejected: the 90114A brass
  fillister family has no #2-56 × 5/16, and a 3/8 brass screw through a
  3/16 flange kept only a 1.04 shank-shear margin (66.05 MPa against
  68.9 MPa allowable, 0.6 × 50 ksi / 3). The heads were already 18-8
  stainless on main. `diagnostics.diag_build_91794A078` reuses the native
  fillister family recipe; its derived slot, dome, thread/runout and
  vendor-frame mapping are family assumptions, not verified vendor geometry.
  By explicit owner decision, the receiver uses conventional blind **2-56
  UNC 2B** taps fastening **MHA-MG-01**, with native **2X Ø.070 DRILL .26**
  and **.195 MIN** full thread. There is no additional finished-cavity
  envelope or printed wall-acceptance requirement. The pilot and engagement
  proofs below do not establish all physical thread-cut wall thicknesses.

Live catalog verification on October 8, 2026:

- [91794A077](https://www.mcmaster.com/91794A077/), formerly selected for the two
  MHA-MG-VN-53 magnifying-bracket screws, is titled “18-8 Stainless Steel
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
  The #2 screw then used a Ø3.8 x 1.55 deep counterbore, leaving 1.625 mm nominal
  grip and a deliberately protruding head (0.5582 mm nominal, not flush).
  Its worst-case engagement was 3.2975 mm, above 1.5D (3.2766 mm); maximum
  reach 4.825 mm stays below the 4.90 mm minimum full-thread depth. (Superseded
  by 91794A078 above, October 16, 2026.)
  Current native **4.95 ±0.0508 mm** cosmetic-thread metadata is retained for
  the screw stack, not used as a manufacturing maximum. Printed **.195 MIN**
  specifies usable full thread without an additional maximum cutting reach.
  The owner's 2026-10-22 relocation retains that screw/grip stack but lowers
  the matched mounting row **0.71 mm**. Both lever taps sit at local
  **Y=−0.7112 mm**, **.128 ±.002 in (3.2512 ±0.0508 mm) below the actual coefficient top**, the nearest
  .001 in to the bracket's −0.71 mm row; matching
  bracket holes and installed screws follow, without moving the L bracket
  body, seat or threaded-lever pose. All three lever rib extrusions are now
  **5.00 mm**, printed **.20 ±.01 in**, with end-rib inner caps **Z=±71.20 mm** and outer
  caps retained at **±76.20 mm**. One native **3X .20** dimension sizes them.
  The separate counter-arm leaf remains 5.08 mm.
  The **.26 ±.01 in** pilot (6.604 mm model depth) and 118° point continue into the
  connected 7 mm coefficient plate, not a special deep receiver rib.
  `receiver_pilot_material_wall_budget` / `RECEIVER_PILOT_MATERIAL_WALL_MIN`
  enforce a **≥.080 in (2.032 mm) pilot-only** material design floor. With printed
  **Ø.070 +.004/0**, the maximum radius is **0.9398 mm**; the deepest 0.3°
  wander is approximately **0.038865 mm**. Actual-top row correlation and the
  printed thickness limits leave approximately **2.221735 / 2.577335 mm**
  top/bottom pilot walls. `sm_summing_lever_profile.receiver_pilot_wall_budget`
  separately bounds longitudinal rib-profile walls; native trimmed-face
  comparisons subtract **TAP_DRILL_DIA/2**. The native pilot and cosmetic
  threads do not prove exact physical thread-cutting geometry or strength.
  The Ø3.8 head-clearance circle is not a counterbore; its **0.122 mm**
  minimum radial float exceeds the **0.1091 mm** station mismatch (both bands plus the lever grid's **0.0075 mm** offset). The moved
  row's **5.64 ±0.05 mm** lower-edge ordinate leaves **3.64 / 4.55 mm**
  lower/upper head-envelope walls under the retained printed bands; the end
  wall is **7.00 mm**. Native screw-head/knife-mount and rib/nut clearances
  remain farm acceptance items.
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
  The former `diagnostics.diag_build_91794A077` reused the native fillister
  family recipe; it was replaced by `diagnostics.diag_build_91794A078`. No
  vendor model is harvested.

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
- [91375A106](https://www.mcmaster.com/91375A106/), selected for MHA-SH-VN-54 (then MHA-DT-VN-64 and MHA-CH-VN-53)
  (#743; since 2026-10-10 also one in each MHA-CH-08 pivot-bracket ear's
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
  It was the `dt-vn-cone-lock-knob` until September 29, 2026.
- [93585A190](https://www.mcmaster.com/93585A190/) is an 18-8 stainless high-profile knurled-head thumb screw,
  1/4-20 x 3/4 in, selected by the user on September 29, 2026 for the
  `dt-vn-cone-lock-knob`. The product page returned HTTP 403 to automated fetches,
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
  MHA-DT-VN-54 used this actual 1/16-inch collar from 2026-09-29 until the
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
  ASME B18.3. The custom MHA-DT-VN-54 collar is turned steel, not purchased;
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
  MHA-CH-VN-57, the two rocker-bracket hold-downs (one per MHA-CH-08 foot
  into MHA-FR-05's top-face seat), so that seat stays 11.5 thread / 14.7
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
  MHA-DT-VN-57: the raised pinion block needs the longer grip. The old
  31.75-mm screw loses the 1.5D engagement floor at the block's printed
  high limit even before entrance/tip deductions. Candidate 90280A202
  returned “No results”; it is not a purchasable length. No length band or
  slot dimensions are stated on the live page; the native family recipe's
  existing slot depiction is not new vendor-qualified metrology. No vendor
  SLDPRT was harvested. Base tap/drill depths follow the new stock length
  and shortest printed block, preserving the ordinary blind-seat reserves.
- [91255A148](https://www.mcmaster.com/91255A148/) is the #6-32 x 1/2 in
  black-oxide alloy steel button head hex drive screw that held the cone tip
  block under U30 (drawing-guidelines.md rule 17 (walls and webs) W22). `dt-vn-cone-tip-block-screw` is now
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
  `pd-transgear-removable`, MHA-PD-09 T12/T18/T24, per the user ruling of
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


- [91251A108](https://www.mcmaster.com/91251A108/) (`dt-vn-cone-tip-block-screw`,
  MHA-DT-VN-60) holds the cone tip block down per the user ruling of September 29,
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
  `sm-vn-knife-hanger-stud`, MHA-SM-VN-52, two, in the superseded #6-32 route.
  Each screw dropped through the MHA-FR-02 crossbar counterbore and seated
  directly on its floor, threading into the MHA-SM-02 mount's top seat.
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
  stock for `sm-vn-knife-hanger-stud`, MHA-SM-VN-52, drawing title **Bolt**, two.
  Live on 2026-10-13: 18-8 stainless steel external hex head, #10-24 UNC
  class 2A, fully threaded, 2 in (50.8 mm) nominal under-head length,
  80 ksi tensile strength, nominal AF 5/16 in (7.9375 mm) and head height
  1/8 in (3.175 mm). This SKU's table omits dimensional tolerances and
  a conformity standard; no supplier head tolerance or under-head bearing
  circle bound is inferred. The ordinary hex-head-on-SAE-washer joint is
  accepted practice, not a guaranteed stress or material allowable.
  MHA-SM-00 step 4 cuts each bolt from the 50.8 mm stock to its own
  hole's measured crossbar-underside-to-washer-top stack plus
  **.351 ±.006 in** (8.9154 ±0.1524 mm) under the head (46.70 mm nominal, printed
  (1.84) as a reference on the part drawing).
  Finished-part acceptance retains a threaded tail **.418 MIN (10.6172 mm)
  from the cut end**, with **MAX 1 P cut chamfer**, leaving at least
  9.558867 mm full-form tail.
  These are manufactured acceptance constraints, not vendor grades.
  Retain the native cut-end prep **RADIAL .03 ×45°** under the title block's
  .XX ±.01 in and ±1° rows, and independently inspect the cut bolt's tail and
  #10-24 class 2A thread; none is a new supplied SKU length or tolerance.
  The head bears on the new washer, not the obsolete #6 counterbore floor.
  The head-height drawing reference uses the physical outer hex bearing edge
  at `Y=LENGTH` and the outer trim rim at `Y=HEAD_TOP_Y`, radius `HEAD_AF/2`.
  It does not measure the crown-dish floor or a corner-trim transition. The
  HLR edge scan distinguishes trimmed circular arcs by an exact point on the
  frontmost rim; ambiguous or missing edges refuse rather than using a
  silhouette or an approximate height. Selection identities and the measured
  `HEAD_H` are checked at insertion, after settling and from the reopened
  read-only saved drawing. These are native model-reference checks, not new
  supplier tolerances or proof that a catalogue-only depiction is vendor CAD.
  The shared `_drawing_physical_axial_dimension.py` proof requires drawing
  dimension type 2 (`swLinearDimension`) **and** two finite, opposing vertical
  native arrows. Their witness stations must match the fresh physical-edge
  projection and their span must equal the physical axial length times the
  native view scale; the type code alone cannot establish verticality.
  The separate original-stock sheet measures 50.8 mm from that same outer hex
  bearing boundary at `Y=46.7` to the factory tip-face rim at `Y=-4.1`, radius
  `1.512358333... mm` (`major_dia/2 - 0.851*pitch`), not the finished cut end
  or the factory chamfer's major junction. A fresh HLR scan of the view's exact
  `AS SUPPLIED STOCK` configuration resolves those physical entities.
  `IView.SelectEntity` selects
  them in the drawing view; native selection and attachment identities, exact
  axial stations and the scaled span must agree. A missing selection, null
  creation or angular result refuses. Both head and stock references undergo
  the same strict creation, settled and independently reopened saved-file proof.
  Before the already-saved drawing closes, a fresh native-object census binds
  both original authored annotations to their actual serialized FullNames.
  The cold read matches those exact names, not guessed or normalized pre-save
  strings, and repeats every physical/source/configuration proof. Missing,
  stale or ambiguous native identity refuses with actual boundary inventories.
  The head-height caption uses the shared measured native text-only shelf;
  moving its text must preserve the physical arrows and complete witness runs.
  Fresh settled and cold-saved reads retain the stricter physical/source proof.
  The complete caption and adjacent purchased-note text still require independent
  full-sheet PDF-ink clearance; a native axial or shelf proof is not paper approval.
  A separate after-save native `IsSame` census captures the purchased note's
  actual annotation `GetName`. The original head-top attachment is a trimmed
  noncircular boundary, not an assumed circle. Fresh all-edge identity and source
  ownership checks retain its actual trim endpoints, parameter bounds, sense
  and top-station landing during settled and cold exact-name paper readback.
- [96659A104](https://www.mcmaster.com/96659A104/) supplies the new
  `sm-vn-knife-hanger-washer`, **MHA-SM-VN-54**, two; the retired 1/2-inch
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
  corner bosses. The **36.50 mm** top-to-finished-underside grip is the
  model's actual `HangerGrip@Crossbar` driving dimension, printed bare by
  section F-F under the title block's .XX ±0.51 mm band.
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
  The washer seats on the **whole faced top**, **36.50 ±0.51 mm
  above the finished crossbar underside**. Cut to the measured stack, the
  bolt's tip reach is .351 ±.006 in (8.9154 ±0.1524 mm; 8.9173 mm modelled
  nominal), bounded by 8.763–9.0678 mm. Subtracting one #10-24
  pitch gives minimum full-form engagement 7.704667 mm, above 1.5D =
  7.239 mm. Full-thread depth **9.65 ±0.13 mm** (MIN 9.52) leaves
  0.4522 mm tip air at maximum reach; the inspected full-form tail leaves
  9.558867 − 9.0678 = 0.491067 mm coverage beyond maximum reach.
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
- [91255A106](https://www.mcmaster.com/91255A106/) (`pd-vn-guide-lock-screw`,
  MHA-PD-VN-60, eight) holds the four guide locks to the platen guides per ruling
  R9-31 (September 30, 2026): these screws ride the platen, and the MHA-SH-VN-51 (then MHA-PD-VN-52)
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
- 91255A108 (`pd-vn-guide-lock-screw` from ruling R9-48 until October 11, 2026)
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
  retired MHA-VN-037) was read live on September 30, 2026: the same 1050-1095 spring
  steel slotted spring pin, unplated, 1/16 in diameter, 9/16 in long,
  0.012 in wall, for a 0.062-0.065 in hole, chamfered ends, no diameter
  tolerance stated. No vendor SLDPRT has been harvested for it yet.
- [98296A031](https://www.mcmaster.com/98296A031/) (`pd-vn-transgear-knob-cup-pin`,
  MHA-PD-VN-62) was read live on October 2, 2026: the same 1050-1095 spring
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
- [98381A434](https://www.mcmaster.com/98381A434/) (`dt-vn-crank-seat-drive-pin`,
  MHA-DT-VN-67, crank only) was read live on September 30, 2026: alloy steel dowel pin,
  unplated, 3/32 in diameter (+0.0001 to +0.0003 in), 1/4 in long, end shape
  "Round x Chamfer". The page states neither the end radius nor the chamfer,
  so `diag_build_98381A434.py` models the plain nominal cylinder. It is
  catalogue-only: no vendor model is downloaded or kept, so it has no replica
  gate, and its standalone diagnostic is a catalog-only run.
- [98381A433](https://www.mcmaster.com/98381A433/) (`pd-vn-transgear-knob-drive-pin`,
  MHA-PD-VN-54, the knob shaft's pair) was read live on September 30, 2026: alloy
  steel dowel pin, unplated, 3/32 in diameter (+0.0001 to +0.0003 in), 3/16 in
  long, end shape "Round x Chamfer". As for 98381A434, `diag_build_98381A433.py`
  models the plain nominal cylinder; catalogue-only, no vendor model, no
  replica gate.
- [93600A189](https://www.mcmaster.com/93600A189/), MHA-PD-VN-64, quantity two,
  was read live on October 9, 2026 in isolated Chromium (HTTP 200): passivated
  316 stainless, ISO 2338-m6, diameter 2.002–2.008 mm, nominal length 6 mm,
  both ends chamfered. The supplier does not publish a length or chamfer
  band. [ISO 2338:1997 Table 1](https://cdn.standards.iteh.ai/samples/20001/5b26cece48c448b782c0de1eccb5b16c/ISO-2338-1997.pdf)
  bounds nominal 6-mm stock to 5.75–6.25 mm;
  [c≈0.35 mm](https://fullerfasteners.com/tech/iso-2338-specifications-parallel-pins/)
  is approximate, not a hard end limit or full-cylinder certificate.
  `_transgear_arm_plate_locating_interface.py` owns the arm/plate hole limits,
  proud set, blind depth and mouth breaks.
  `pd_vn_transgear_arm_plate_locating_pin_spec.py` retains purchased-pin data and
  the fit, insertion and bottom-air calculations. The whole standard length
  family has at least 0.17 mm bottom air in the custom arm blind hole.
  `diag_build_93600A189.py` uses the
  existing nominal-cylinder recipe: catalogue-only, no vendor model, no
  replica gate and no new commodity receiving procedure.
- [98381A473](https://www.mcmaster.com/98381A473/) (`sm-vn-knife-mount-dowel`,
  MHA-SM-VN-53, two; formerly `pd-vn-transgear-latch-pin`) was read live on
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
- 98381A474 (`pd-vn-transgear-latch-pin`, MHA-PD-VN-58, since R9-50) is the 7/8 in
  length of the same 1/8 series (98381A467 1/8 in through 98381A479 1-3/4 in,
  dt-logs `transgear-evidence/mcmaster-skus.md`, "Round 6 — additions"); a
  reseller lists it as 1/8 x 7/8
  (https://www.kvmtools.com/products/mcmaster-98381a474-dowel-pin-pack-of-50-alloy-steel-1-8-diameter-7-8-long).
  [INFERENCE] Its own page is not yet read live. `diag_build_98381A474.py`
  carries the 98381A473 harvest's end forms at the longer length; it is
  catalogue-only: no vendor model, no replica gate, and its standalone
  diagnostic is a catalog-only run.
- [90325A174](https://www.mcmaster.com/90325A174/) (`pd-vn-transgear-pivot-screw`,
  MHA-PD-VN-57) is the hanger arm's pivot: its shoulder runs through the arm and
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
  Its head-height drawing reference spans the actual outer bearing rim at
  `Y=0` and the chamfer-reduced top rim at `Y=HEAD_H`,
  radius `HEAD_DIA/2 - HEAD_CHAMFER`. The full-radius chamfer junction below
  the top and the socket rim cannot substitute for that top boundary. Exact
  visible model edges, distinct native selections and their dimension
  attachments are checked under HLR; the measured height is checked again
  after settling and on the reopened read-only saved drawing. Interior face
  points are not reliable drawing-edge picks, even when their projection
  crosses the apparent rim.
  The shared `_drawing_physical_axial_dimension.py` proof requires type 2
  (`swLinearDimension`), not a type-12-or-type-2 alternative, and independently
  proves verticality from both native arrows, projected physical stations and
  the native view scale. Its `1e-8 m` sheet-position bound inherits the exact
  physical-edge pick precision; it is not fitted to a rendered result.
  The separate native-length tolerance remains `1e-5 mm`. The original-stock
  thread reference spans the shoulder's outer end rim at `Y=-12.7`, radius
  `2.38125 mm`, to the factory tip-face rim at `Y=-22.225`, radius `1.707896 mm`,
  for exactly 9.525 mm. Its factory chamfer is `0.374904 mm`, not the finished
  tip's 0.60 mm preparation. Fresh HLR entities from the exact
  `AS SUPPLIED STOCK` view are selected with `IView.SelectEntity`, not an
  interior-face coordinate hit test. Native closest points establish actual
  trimmed-edge membership; an unresolved distinct-edge tie refuses rather
  than silently substituting a circle, silhouette or finished-tip station.
  Both head and stock references are checked afresh at creation, after settling
  and after independently reopening the saved drawing without repair or resave.
  Saved identity is captured from the original authored annotations after the
  existing saves and before close, using a unique fresh native `IsSame` census.
  Reopening requires those exact serialized FullNames, not a suffix-stripped
  or geometry-only substitute. Boundary and failure inventories preserve the
  original and observed names; capture never assumes a FullName survives saving.
  Head-height and socket-AF captions use the shared measured native text-only
  shelves, retaining the physical arrows and complete witness runs. The socket
  shelf has its own exact serialized identity and cold-saved presentation checks;
  it is not a vertical-axial proof. The purchased-head note remains attached to
  the physical head-top rim. Its complete text, leader, aligned end view and finite
  native centre mark require fresh full-sheet clearance, not a native-value-only
  approval.
  The purchased note's name is captured independently from the original native
  annotation after saving. Native `ITextFormat.LineLength` wraps the unchanged
  property-linked text without inserted line breaks or font compression. Its
  straight leader retains the exact trimmed sheet-left head-top extremum,
  derived from the actual view projection. The left text field must clear the
  complete shoulder-length text, witnesses and arrows as well as neighbouring
  ink, views and border, including a fresh exact-name cold readback.
- [91794A055](https://www.mcmaster.com/91794A055/) (`pd-vn-transgear-disc-screw`,
  MHA-PD-VN-55, three) joins the brass disc hub's flange to the 150T disc: each
  head sits on the flange and the thread enters one of the disc's through
  taps. The product page was read on September 30, 2026: 18-8 stainless
  steel slotted fillister head, #0-80 UNF class 2A, 1/4 in under the head,
  fully threaded, high narrow head Ø0.096 in x 0.055 in. The user supplied
  the vendor model `91794A055.SLDPRT`, harvested on amet on September 30,
  2026 into the read-only dump `cad/out/reports/mcmaster-91794A055-dump.json`.
  It is not the 90280A narrow-fillister tree, so `diag_build_91794A055.py`
  replays its own laws (in `pd_vn_transgear_disc_screw_spec.py`) instead of
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
- [91790A199](https://www.mcmaster.com/91790A199/) (`pd-vn-transgear-arm-plate-screw`,
  MHA-PD-VN-56, two) was positively read live at 2026-10-09T07:17:13.553Z:
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
- [91792A108](https://www.mcmaster.com/91792A108/) (`pd-vn-guide-lock-screw`,
  MHA-PD-VN-60, eight) replaces 91255A108 on October 11, 2026: the book's
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
- [97431A260](https://www.mcmaster.com/97431A260/) (`pd-vn-transgear-retaining-ring`,
  MHA-PD-VN-61, R9-68) is pushed sideways into the MHA-PD-23 pin's groove in front
  of the MHA-PD-25 front bushing and closes the disc cluster's float. Its page
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

- [9715K43](https://www.mcmaster.com/9715K43/) (`pd-vn-transgear-pivot-spring`,
  MHA-PD-VN-63, one) sits on the MHA-PD-VN-57 pivot shoulder screw's shoulder, between
  the MHA-PD-VN-67 shim under its head and the floor of the MHA-PD-18 arm's spot face, and
  preloads the arm forward onto the MHA-PD-20 spacer. Its page was read live on
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
  (`pd-vn-transgear-pivot-shim`, MHA-PD-VN-67, one) sits on the MHA-PD-VN-57 shoulder
  under its head, on the MHA-PD-VN-63 spring. The 9.5 support bar grew rearward
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

- [9714K392](https://www.mcmaster.com/9714K392/) (`dt-vn-cylinder-bank-spring`,
  MHA-DT-VN-68, one) sits on the MHA-DT-13 arbor directly between gear 19's
  north planar face and the north MHA-DT-02 strap, set by a 0.95 blade, and
  holds the 20-gear stack south on the single MHA-DT-26 brass disc and south
  strap datum (user ruling 2026-10-20). Its page was read live on
  October 9, 2026: Wave Disc Spring, steel, stackable; ID 0.385 in -0.01/+0.01,
  OD 0.5 in -0.01/+0.01, thickness 0.005 in, height 0.05 in (free); compressed
  height 0.024 in and deflection 0.026 in at the 1.5 lb working load; pack of
  10, $11.18. The page states no rate and no wave count (the spec's rate is
  the working point taken as linear [INFERENCE]); the part carries the
  library's `Plain Carbon Steel`.
- [9714K24](https://www.mcmaster.com/9714K24/) (`ch-vn-rocker-bank-spring`,
  MHA-CH-VN-54, one) sits on the MHA-CH-05 pivot shaft between the south
  MHA-CH-VN-56 washer and the south MHA-CH-08 ear, set by a 0.60 blade, and holds the
  20-hub stack north on its datum. Its page was read live on October 9, 2026:
  Wave Disc Spring, high-carbon steel, stackable; ID 0.265 in -0.02/+0.01, OD
  0.367 in -0.02/+0.01, thickness 0.006 in, height 0.03 in (free); compressed
  height 0.015 in and deflection 0.015 in at the 3 lb working load; pack of 25,
  $16.31. The page states no rate, no wave count and no shaft size. The
  catalogue's minimum ID (6.22 mm) is under the 6.35 mm shaft, so each spring
  is slid onto MHA-CH-05 first and one that does not run free is rejected.
- Both are modelled as their installed envelope: `diag_build_9714K392.py` and
  `diag_build_9714K24.py` extrude the ID x OD annulus to the installed height
  (the set-blade gap) [INFERENCE: the waves are not modelled]. A 3-D
  SolidWorks model is offered on each page, but none was fetched or kept
  here, so both are catalogue-only: no replica gate, and their standalone
  diagnostics are catalog-only runs.
- [3088A429](https://www.mcmaster.com/3088A429/) (`ch-vn-rocker-thrust-washer`,
  MHA-CH-VN-56, two) rides the MHA-CH-05 pivot shaft at each end of the rocker
  bank: the north one between hub 19 and the datum MHA-CH-08 ear, the south
  one between hub 0 and the MHA-CH-VN-54 spring. It replaced the custom
  MHA-CH-09 sheet washer (owner, 2026-10-15: every washer is a purchased
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

- [92671A005](https://www.mcmaster.com/92671A005/) (`mg-vn-wheel-axle-nut`,
  MHA-MG-VN-52, two), [92916A480](https://www.mcmaster.com/92916A480/)
  (`mg-vn-wheel-axle-back-washer`, MHA-MG-VN-54, one) and
  [92916A250](https://www.mcmaster.com/92916A250/)
  (`mg-vn-wheel-axle-front-washer`, MHA-MG-VN-55, one) carry the magnifying wheel
  on the 3/16 mg-wheel-axle (mg wheel rev 10). The back washer sits between
  the MHA-MG-11 axle spacer (on the mg-wheel-bar's front face) and the hub; the front washer sits on the
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
- [91375A105](https://www.mcmaster.com/91375A105/) (`pn-vn-pen-rod-set-screw`,
  MHA-PN-VN-52, one) locks the pen rod's turned pivot end in the MHA-PN-05
  v-block, and [92671A115](https://www.mcmaster.com/92671A115/)
  (`pn-vn-pen-adjust-nut`, MHA-PN-VN-53, one) jams the #0-80 adjuster stud on the
  MHA-PN-04 pen rod's top. Both pages were read live in a browser on
  October 13, 2026. 91375A105 is an alloy steel cup-tip set screw, black
  oxide, 4-40 UNC Class 3A, 3/16 in long, 0.050 in hex drive, Rockwell C45,
  ASME B18.3 / ASTM F912; it is the MHA-SH-VN-54 (then MHA-CH-VN-53 and MHA-DT-VN-64) 91375A106 cut 1/16 in shorter,
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
- [93075A199](https://www.mcmaster.com/93075A199/) (`pn-vn-hanger-screw`,
  MHA-PN-VN-50, one), [90480A009](https://www.mcmaster.com/90480A009/)
  (`pn-vn-pen-hanger-nut`, MHA-PN-VN-54, one) and
  [90760A009](https://www.mcmaster.com/90760A009/) (`pn-vn-pen-hanger-jam-nut`,
  MHA-PN-VN-55, one) hold the MHA-PN-02 pen hanger on the MHA-MG-08 wheel
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
- [90760A140](https://www.mcmaster.com/90760A140/) (`sm-vn-boss-hook-jam-nut`,
  MHA-SM-VN-55, one) locks the MHA-SM-VN-50 counter anchor (9490T1, trimmed) in
  the MHA-SM-03 summing-lever boss. It was read live on October 16, 2026
  from the McMaster 10-24 narrow-profile hex-nut listing, whose product page
  needs a login: zinc-plated steel narrow-profile hex nut, 10-24 UNC
  right-hand Class 2B, 5/16 in across flats, 7/64 in high, with a material
  certificate. It runs down the eyebolt shank and is jammed against the boss
  top face with the eye held clocked, the joint's rule 23 lock. Of its
  listing siblings, 90760A120 (zinc-plated, 1/4 in across flats, 3/32 in
  high) leaves thin walls on a #10 thread and less wrench purchase,
  90760A190 is black-oxide where the zinc-plated 9490T1 wants a matching
  finish, and 90730A011 is 18-8 stainless. No solid is used here:
  `diag_build_90760A140.py` extrudes the hexagon with a plain bore at the
  #10-24 basic major, so it is catalogue-only.
- [9666K56](https://www.mcmaster.com/9666K56/) supplies both amplification
  wires, the `LeverWire` and `PenWire` configurations of `sh-vn-music-wire`
  (MHA-SH-VN-56; `mg-vn-lever-wire` MHA-MG-VN-56 and `pn-vn-pen-wire`
  MHA-PN-VN-57 until 2026-10-20), both cut from one coil. Their end
  terminations, wraps and developed cut lengths
  are not yet modelled, so both sheets of the package stay DO NOT RELEASE. Read live
  on October 14, 2026: lubricated 1080 spring steel music wire, ASTM A228,
  cold drawn, spring temper, phosphate coated, 261,000 psi tensile, diameter
  0.031 in with -0.001/+0.001 in tolerance, 110 ft in a 1/4 lb coil;
  straightness is not rated. The models keep the Ø0.8 design nominal, which
  lies inside that 0.762-0.813 band (`_mcmaster_9666k56.py`, asserted by
  `sh_vn_music_wire_lever_geom.py` and `sh_vn_music_wire_pen_geom.py`). 8907K32, the same wire
  in 1 ft straight lengths, was rejected: the lever wire's straight rest run
  alone is about 353, longer than 304.8. McMaster offers no metric 0.8 music
  wire. No vendor solid is used; the wire is a plain cylinder.
  The supplier drawing's exact .0310-in nominal is shown separately as a
  .7874-mm model-owned construction circle in zero-body `SUPPLIER_REFERENCE`.
  It does not dimension either installed .8-mm cylinder. Both sheets retain
  their configuration-qualified native `Depth@Wire` straight-run references;
  package length is ordering metadata, not a developed cut length.
- [90114A124](https://www.mcmaster.com/90114A124/)
  (`ms-vn-stop-plate-screw`, MHA-MS-VN-51, two) retains the MHA-MS-03 plate
  on MHA-MS-02. The product table and 2-D PDF were read live on October 9,
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
  `91794A078` fillister-family recipe: its dome, slot and thread/runout
  details are family assumptions, not measurements of a vendor solid.
  No vendor solid was downloaded and no replica equivalence is claimed.

- [3606T118](https://www.mcmaster.com/3606T118/) (`dt-vn-keeper-chain`, MHA-DT-VN-65)
  and [3606T811](https://www.mcmaster.com/3606T811/) (`dt-vn-keeper-chain-link`,
  MHA-DT-VN-66) tie the crank's taper pin to the arm as one loop through the eye
  and the ring. Both product pages were read on September 29, 2026. 3606T118 is
  unfinished brass bead chain, trade size 3, 3/32 in beads, 20 lbf, not for
  lifting. 3606T811 is the brass loop link that joins the cut ends into a loop.
  The October 19 source audit found no engineering drawing/CAD for either
  item and no numeric supplier size beyond the bead diameter. The sheet
  imports the exact 3/32-in native diameter driving `SeedProfile`, not the
  smaller sphere/rod intersection circle. The 3.2426-mm pitch is a trade-size-3
  average of 94 beads per foot (Ball Chain Mfg. and Frank Winne size charts),
  not a McMaster manufacturing dimension. The 9-mm generic capsule, rod, wall,
  crimps and mouths are project clearance assumptions in
  `dt_vn_keeper_chain_spec.py`, not verified dimensions of 3606T811's pictured
  loop link. Its supplier numeric coverage correctly remains empty.

- [6261K171](https://www.mcmaster.com/6261K171/) (`sh-vn-chain-link`,
  MHA-SH-VN-50, in its `InnerLink` and `OuterLink` configurations; the
  parent-scoped `pd-vn-chain-inner-link` MHA-PD-VN-50 and
  `pd-vn-chain-outer-link` MHA-PD-VN-51 until 2026-10-20) and
  [6261K108](https://www.mcmaster.com/6261K108/) (`pd-vn-chain-connecting-link`,
  MHA-PD-VN-66) are
  the paper-drive chain between the T12 and T24 MHA-PD-09 sprockets. Both
  product pages were read on October 14, 2026. Each states steel, single
  strand, ANSI 25, 1/4 in pitch, 0.130 in roller diameter, 1/8 in roller width
  and 140 lb working load; neither states a grade, plate size or coating.
  6261K171 is sold by the foot. The selected 66-pitch loop (16.5 in; #2034
  replaced the former 68-pitch, 17 in loop) is cut from 2 ft with an inner link
  at each end. This gives 33 inner and 32 outer links,
  the `InnerLink` and `OuterLink` configuration quantities of one purchased chain;
  6261K108, the connecting link, closes the loop as its last outer link. The
  cut is the only modification, so both identities stay vendor (`-vn-`) parts
  (`cad/docs/subsystem-identities.md`). The modelled links are the clearance
  stand-ins in `_chain.py`, not vendor replicas. An October 19 source audit
  inspected the supplier native/STEP files without adding their solids to the
  project. The 6261K171 page's engineering graphic is an eleven-foot
  **6261K401 family example**, not a drawing of the two-foot purchase.
  [6261K171-6261K281](https://www.mcmaster.com/6261K171-6261K281/) is the verified
  **one-foot** native/STEP selection used only for the same-family pitch and
  cross-sections. Its exact pin is 2.2987 mm (.0905 in), displayed .091 in;
  rounded ink is not exact geometry. Zero-body `SUPPLIER_REFERENCE` contains
  hidden construction-only pitch/pin/roller/width diagrams, not revised
  installed pins or bushes. The connector additionally has its own .030-in
  plate and .335-in overall-pin references; `FOR ROLLER` references are
  application gauges, not rollers physically present on the connector.
  The shared chain sheet shelves roller-width text off its native dimension
  line and reserves a taller geometry lane for the nominal diagrams; fitting
  still selects an existing standard scale from the actual source curves.
  Original member geometry, path axes, quantities, export identities and the
  two-foot cut instructions are retained. Evidence and immutable source hashes:
  `C:/src/dt-logs/vn-supplier-dimensions-20261019/SupplierSpringsChains/chain-audit.md`.

### Tooling-only oblique-trammel source references (2026-10-21)

Historical source record: the fourteen then-current `ch-rocker-arm-tl-vn-oblique-*` targets below imported
model-owned supplier references. Live Firecrawl product fetches returned HTTP
200 for every McMaster SKU and Olander 4C50BHCA; the exact McMaster engineering
`X.GIF` drawings were downloaded from those pages. This supersedes the earlier
login-wall observations above for source access, not their historical CAD or
replica-gate provenance. No supplier models or engineering images are tracked.
The `block-screw` and `block-washer` rows were retired on 2026-10-23; their
rows below preserve the dated source readings, not current jig registrations.

| target suffix at source date | exact SKU at source date | primary size coverage |
|---|---|---|
| `rail-screw` | [91251A197](https://www.mcmaster.com/91251A197/) | 0.750-in length; 0.270-in head diameter, 0.164-in height; 0.1640-in major; 9/64-in drive |
| `bracket-screw` | [91251A196](https://www.mcmaster.com/91251A196/) | 0.625-in length; same published head, major and drive as the rail screw |
| `block-screw` | [91251A188](https://www.mcmaster.com/91251A188/) | 1.875-in length; 0.875-in minimum thread length; 0.270/0.164-in head; 0.164-in major; 9/64-in drive |
| `carriage-screw` | [91290A168](https://www.mcmaster.com/91290A168/) | M4 x 0.7; 20-mm length; 7-mm head diameter, 4-mm height; 3-mm drive |
| `kp08-screw` | [91251A150](https://www.mcmaster.com/91251A150/) | 0.625-in length; 0.226/0.138-in head; 0.1380-in major; 7/64-in drive |
| `nut-screw` | [Olander 4C50BHCA](https://www.olander.com/items/4C50BHCA) | #4-40 x 1/2 in; head diameter 0.201–0.213 in, height 0.051–0.059 in; published 0.063-in drive |
| `riser-screw` | [91771A112](https://www.mcmaster.com/91771A112/) | 0.625-in overall length; 0.212-in head diameter, 0.067-in height; 0.112-in major; 82-degree head; Phillips No. 1 designation |
| `clamp-screw` | [91251A541](https://www.mcmaster.com/91251A541/) | 0.875-in length; 0.375/0.2500-in head; 0.2500-in major; 3/16-in drive |
| `lever-screw` | [91251A583](https://www.mcmaster.com/91251A583/) | 1.000-in length; 15/32-in head diameter, 5/16-in height (drawn 0.469/0.313); 0.3125-in major; 1/4-in drive |
| `cl-dowel` | [91595A452](https://www.mcmaster.com/91595A452/) | nominal 6.000-mm diameter, +0.004/+0.012 mm; 20-mm tip-to-tip length |
| `block-washer` | [91812A215](https://www.mcmaster.com/91812A215/) | 0.170-in ID, 0.300-in OD, 0.080–0.100-in thickness interval |
| `lever-washer` | [91812A230](https://www.mcmaster.com/91812A230/) | 0.340-in ID, 0.530-in OD, 0.070–0.090-in thickness interval |
| `leadscrew` | ZYLtech HW-SC-T8x2-600 | 600-mm purchased length, 8-mm nominal major diameter, 2-mm pitch; single-start right-hand Tr8x2 |
| `leadscrew-nut` | ZYLtech HW-SC-T8x2-NUT | 22/10.2-mm flange/body diameters; four 3.5-mm holes on 16-mm PCD; 1.5/3.5/10-mm axial spans |

Both ZYLtech identities were confirmed by live primary-page variant selection:
the [pre-cut screw page](https://www.zyltech.com/8mm-t8x2-trapezoidal-acme-lead-screw-w-brass-nut-pre-cut-lengths-150mm-2000mm/)
displays `HW-SC-T8x2-600` after selecting 600 mm, and the
[replacement-nut page](https://www.zyltech.com/zyltech-brass-nut-only-various-diameters-and-pitches-available/)
displays `HW-SC-T8x2-NUT` after selecting T8x2. The screw kit's current front
and side engineering images supply the regular nut's dimensions. The
replacement page also contains unrelated larger/inch-size gallery drawings;
their R12, 3.30-mm hole and inch-size data were not applied to this T8x2 nut.

The dowel's crowned/domed ends have no end circles: its length is an explicit
nominal tip-to-tip construction witness, not an invented rim measurement.
Washer drawings preserve the maximum-thickness plain-annulus representations;
their source intervals do not assert modelled split pairs, cams or serrations,
and the existing receipt/pair-package caveat remains. The nut's plain 6-mm
thread-minor bore is a modelling contract, not an unpublished supplier size.
No standard-only socket depths, Phillips-recess dimensions, nut bore limits,
or omitted edge details were promoted to supplier evidence.

The screw's `SUPPLIER_REFERENCE_STOCK` configuration contains only native
construction gauges for the purchased length, nominal major and pitch. Its
separately labelled drawing inset is not a replacement solid, helix or
manufacturing control. The installed 410-mm cut length and five flats retain
their existing native fabrication dimensions. All fourteen targets retain
their prior solids, materials and installation geometry.

Raw primary responses, current-variant selections, source engineering images,
URLs, scrape IDs, retrieval errors and immutable SHA-256 hashes are preserved
outside the repository at
`C:/src/dt-logs/vn-supplier-dimensions-20261021/tooling-vn-primary/`.
`manifest.json`, `drawing-downloads.json`, the two ZYLtech image manifests and
`mcmaster-skus.md` distinguish sources used from mixed-gallery images rejected.
The Firecrawl 2-D-PDF interaction timed out at the transport layer; no PDF URL
was guessed, and the exact primary engineering GIFs supplied the evidence.
Native execution/rendering is not claimed by this source record.

Ground rules (mirrored in the diagnostics themselves): the vendor files are
opened read-only and NEVER saved or modified; everything derived from them
(harvest dumps, replicas, renders, reports) goes only under the gitignored
`cad/out/`.

## Reference drawings

Each production part identity above has a registered `drawing:`
task, including identities that share a supplier SKU. Most identification
sheets use front, top, right and isometric views with stock and ordering data.
Supplier dimensions are associative native reference annotations, never typed
numeric replacements. When the installed clearance model differs from the
catalogue, explicitly labelled construction-only stock/application diagrams
live in zero-body `SUPPLIER_REFERENCE*` configurations; original installed
members and their export identities are unchanged. Music-wire sheets retain
both straight-run `Depth` references and their DO NOT RELEASE limitations.
These are purchased-part reference sheets; general fabrication tolerance and
edge-break notes do not apply to supplier references.
Extension-spring free/maximum inside-hook spans and coil/wire sizes use
explicitly nominal construction diagrams, not new free/extended solid variants.
Their source gauge authoring stays in the model-only
`_supplier_extension_spring` dependency closure. The existing
`_supplier_spring_drawing` consumer owns drawing import, showing those gauges
and final native annotation readback; part builds never import drawing adapters.
Disc-spring stock diagrams separate ID/OD, free-height envelopes and nominal
strip gauges from compressed-height/deflection/shaft application gauges.
Neither diagram asserts an unmodelled loaded shape or a force derived from
the installed stand-in.

Offline recipe checks follow the supplier consumer's actual required-property
branch and the producer's real saved-configuration callback. Their inventories
must reject missing or unknown authors, including nested scripts; documentation
strings and Python function-object identity are not native behavior. Configured
member export readers remain restricted to the requesting part's registry row,
and drawing fixtures retain native note, hidden-line and stale-source refusals.

Supplier screw construction keeps a welded witness's already fully constrained
endpoints rather than adding a redundant origin anchor. Other witnesses still
receive their normal origin controls; all retain exact final-frame readback and
the complete sketch's fully-defined guard. Head angles use a native angular
dimension between the two actual construction rays, with the text point mapped
from their owning sketch plane, and require exact driving-angle readback.
Y-axis dowels and X-axis spring pins use native linear measurements of the
complete axial span between their two end rims. Both drawing-created end conditions
must remain `None`: neither orthographic edge-on span uses an arc-center
setter. Exact end-rim attachments, full source length, native type and the
bandless reference remain checked after layout.

Pin drawing imports validate the original model's value, presentation, band
and physical witness before import. Only the drawing-local display is formatted,
including its tolerance-display precision; source values and tolerance bands
are never written. The drawing checks the independently mapped witness in its
actual view, then rechecks the original source after dressing and final rebuild.
The shared pin stations reserve room for the dressed reference text: dowel
diameters clear the end-view center marks, and spring-pin application-hole
labels sit to the right of their circle so the leader approaches outside the
multiline qualifier. These are drawing-only moves within the existing lanes.

Read-only supplier presentation refusals identify the first mismatched field
and its actual/expected values, preserving native getter order and stopping
before later readers can mask that failure. Imports are not reformatted or
repaired by this assertion; an error label alone is not its native root cause.

Washer imports explicitly apply the existing supplier-reference **display**
formatter: native import need not inherit the source display's document-unit
flag. The original part's body, witness geometry, value, supplier units,
precision and native band are checked before import, after dressing and after
final layout. The imported value and band remain independently checked; the
formatter never changes either. A changed original source is a failure, not
something the drawing repairs.

The six oblique-trammel screws with opposing Top annotation lanes select the
shared `supplier_top` layout: a 70 mm Top panel leaves 18 mm for the native
outline after the two 26 mm annotation budgets. Standard sheets (including the
shared thumb screw) and the separate 96 mm `tall_top` layout retain their
existing capacity. Native outline padding is measured at each candidate scale;
it is not scaled with the part, and the settled view/annotation guards remain
authoritative. Recorded R38 outlines provide offline fit regressions, not proof
that the repaired drawing has passed a fresh native run.
After supplier formatting settles, this same selected layout offsets short
head-height text left and AF/diameter text right of the measured native line
ends, using the existing 2 mm clearance. Arrow tips, witness spans and physical
dimension-line stations must remain unchanged through final readback, compared
with each drawing's retained pre-offset native measurements (including the
block's custom minimum check); the full ink audit still sees the offset leader.
The block screw's thread-length lane is left of the part,
opposite its overall length. Recorded R44 paint-data replays cover the observed
collisions and refusal paths; they do not qualify a fresh native export.
These six sheets also use the existing purchased title-cell fitter for their
linked Name, Material and Number notes. It preserves the complete source values,
property expressions and note anchors, measures the actual sheet-format rules,
and requires one row inside a 0.6 mm inset at the existing readable font floors.
The same checks repeat after final rebuild. This replaces the clamp screw's
separate number-only fit; other purchased sheets retain their existing opt-ins.
The fastener sheets explicitly declare their source `Material` link; purchased
part sheets retain the fitter's `Material Specification` default. The census
requires exactly one declared material field, never an alias or optional note.

The COM-free `test_purchased_title_fit.py`, `test_supplier_native_contracts.py`,
`test_supplier_native_repair.py` and `test_supplier_top_text_shelves.py` suites
are enrolled in `check:recipe`. That gate also tracks their runtime-read washer
paint and R44 shelf JSON fixtures, so changing recorded ink invalidates its
offline stamp. The enrollment guard requires both the test modules and those
fixture inputs; no exemption replaces their actual execution. These checks do
not qualify a native export.

Washer ownership failures collect bounded, independent read-only context only
after an ordinary native exception. Missing readers remain unavailable, never
measured zero or acceptance. `KeyboardInterrupt` and `SystemExit` abort without
starting or continuing optional observations. Identity refusals remain strict;
optional observations do not license acceptance.

Nut chord endpoints and washer witness points/segments attach in the drawing's
namespace. Their independently checked part entities are mapped through the
exact owning view's `GetCorresponding`; native one-to-one identity, distinct
endpoints and no extra attachments are required there. Direct comparison
between a part object and a drawing object is not an attachment proof.
Both part displays and drawing imports require native `IDimension` identity
with the dimension independently enumerated from the source feature and exact
`model.Parameter("Dimension@Feature")`. Missing or different dimensions fail
even when their names, values and types match. Feature-owner wrappers are not
dimension identity: native R47/R49 returned unequal feature handles while all
three canonical dimension identities were one. The reason for the wrapper
discrepancy remains unproven. `GetFeatureOwner` and mapped-feature observations
remain failure-only diagnostics, not an alternative acceptance path. Exact
typed source-to-view entity mapping, physical geometry, source identity,
configuration, values, tolerance bands and source-preservation guards remain
required independently. Native R50 freshly qualified this unified contract on
the five previously refused washer sheets, each with 18 clean, read-only,
unchanged-hash source checkpoints. This is source/identity proof, not blanket
layout acceptance: its CH thrust sheet retained an actual outer-rim strike
through the OD reference's opening parenthesis.

The shared washer drawing author settles the complete formatted thickness
limits stack in native linear `OffsetText` mode, then measures its text and
physical witnesses before placing the text on a right-hand shelf. Both full
diameter value/qualifier blocks use the same measured placement beyond the face
outline, without the unsupported diameter `OffsetText` mode. All use the
existing 2 mm clearance plus 0.2 mm placement allowance and retain physical
dimension stations, exact native/source identities and supplier bands.
This drawing-only rule affects all seven washer sheets: R49/R50 native records
show every OD block requires a move under that rule. Those retained records
provide behavioral replays, not proof of the new settled native leader routes;
all seven changed drawing outputs require fresh native visual qualification.

Creating these diagram configurations rebuilds each original member before
recording its preservation baseline. The native guard requires identical
solid/sheet-body counts and face counts and compares all twelve mass-property
values with unchanged tolerances through an order-independent, one-to-one body
correspondence. Ambiguous non-equivalent correspondences fail closed; failures
retain both complete native record sets. Feature suppression is resolved afresh
by unique name/type after configuration changes, not through retained COM
proxies. Cleanup is restricted to the construction insertion's owned features,
never automatic configuration-comment folders. Body-Delete ownership retains
both known names until rename readback succeeds, so a committed rename followed
by a transient read failure still permits original-member restoration.

Sketch-only supplier views fit actual native construction curves, not the
drawing view's padded `GetOutline` rectangle. Before fitting, the shared capture
reader maps native sketch coordinates through the actual rigid sketch inverse
into immutable model-metre points. Each later bounds read projects those points
through the current, refreshed native view frame; complete circles use exact
projected ellipse extrema. One-dimensional projections are valid. Partial arcs,
blocks, text and explicit user-point ink refuse rather than being omitted.
Capture proves error-free named source features, actual requested configuration,
zero solid/sheet bodies, unsuppressed model-hidden construction owners and
drawing correspondences. It does not infer drawing visibility from a
corresponding feature's `Visible` property.
The spring/chain path makes one capture pass per source configuration, then
restores the original configuration, body counts, dirty/read-only state and
drawing context before fitting. It never switches or rebuilds the source during
fitting, dimension placement or final settled checks. Captures are bound to the
actual source document/path/configuration and view, with no live-sketch fallback;
the drawing path performs no source geometry mutations after capture.
Existing drawing-qualified sketch showing and native dimension import remain
the presentation path. Native farm renders and visual comparison with the
supplier reference qualify the resulting sheet, independently of the source
geometry capture. Native dimension association, value, visibility and
annotation-containment checks remain mandatory.
Native centre crosses on supplier circles are legitimate reference aids. The
existing centre-mark pass turns off template extension lines before fitting and
again after scale selection, rather than rejecting those marks.
Source parts are opened with the native silent/read-only option, with actual
read-only state and path identity checked; a resident writable source is refused.
Only clean source documents are captured, without saving or clearing their
flags. The capture/preparation phase must remain clean. After capture, the known
imported-dimension text/precision presentation stage may dirty the in-memory
source without changing its geometry. That expected dirty bit is not treated as
a geometry-change signal. Read-only state remains mandatory through drawing
save, and a source-part SHA-256 check before opening and after drawing
finalization rejects any persisted source-byte change. Existing build teardown
discards document changes without saving. Restoration failures are recorded
separately from any primary capture failure.
Read-only source acquisition and each whole-file hash have aggregate timing
spans, `drawing.purchased_source_open` and `drawing.purchased_source_hash`;
there is no per-chunk instrumentation. Measure their cost from native traces,
not source-only tests.

Native clamp run `f6635a090` isolated the transition to the legacy
`IModelDoc2.SaveAs3` drawing save: the same source part was read-only before
the save and writable afterward, with changed bytes and unchanged native
identities. Read-only acquisition alone is therefore not a persistence
guarantee. Generic purchased-sheet checkpoints observe live document state
and SHA around setup, presentation, saves and close, and refuse drift.
Failure capture copies existing exports with unproven generation; it performs
no additional COM save or export.

The vendored drawing helper uses `IModelDocExtension.SaveAs3` with
`(path, 0, 1, None, None, 0, 0)` and its `(ok, errors, warnings)` result,
following the [existing template-maintenance positive control](../../scripts/maintain_drawing_templates.py).
It requires success, zero errors and a fresh output file; warnings are logged.
The read-only, identity and source-hash guards remain unchanged. The template
control is not source-preservation proof for purchased drawings with loaded
parts; the next native canary must verify their source state and bytes.

The [native presentation-save receipt](../../docs/pipeline/evidence/vm2-datum-placement/probes/rack-source-save-callout/receipt.json)
records `SetText` dirtying the source part and drawing `SaveAs3` persisting
changed source bytes while the measured dimension and tolerance stayed
unchanged. That is presentation persistence, not evidence of a geometry change.

Installed pictorials retain their native-outline guards. Standard scales,
reserved cells and final native dimension/note-ink containment are unchanged.

Supplier source ownership uses documented `IDisplayDimension.GetDimension2`
and the fully qualified model-dimension identity, not cross-context COM wrapper
equality. That identity must match the referenced model's named `Parameter` and
a dimension enumerated from the intended source feature. Within the source
context, the named parameter and enumerated feature member must compare
`IsSame == 1`. Cross-context `IsSame == 2` is diagnostic only; source-annotation
mapping into the view is not required. Actual drawing/view annotation ownership
remains checked. Model-import validation does not require imported point wrappers
to compare equal to source or `GetCorresponding()` wrappers: native MSC imports
return distinct contexts even when the source dimension association is intact.
Coordinates and local point IDs are not substitute ownership proofs. Callers
with a separately proven mapped-attachment contract retain their stricter
same-kind member inventory and one-to-one native correspondence checks.
The MSC head crop's actual circle frame and entire footprint are checked before
`Crop2` consumes the selected profile. Settled validation checks native crop
state, view binding/frame and annotation containment; `IView.GetSketch()` is not
required to expose the consumed profile afterwards.
These associative references may be nominal supplier gauges; source membership
does not make a reference line or circle a physical finished edge.
Source path/configuration, annotation ownership/type/count, final value,
dangling/override, inventory and layout guards remain in force. Source-only
regressions do not by themselves qualify this COM behavior on a native seat.

Generic purchased-view fitting refreshes native display geometry at each
candidate scale and after centering. Only the validated post-refresh outline
selects the scale and proves containment; an unavailable or invalid pre-refresh
diagnostic snapshot cannot reject valid refreshed geometry. Custom geometry
readers retain ownership of their refresh. Standard scales and the settled
native-extent, centering and containment guards remain mandatory.

The thumb-screw sheet keeps axial dimensions on physical finished-face rims
and diameters on their model-owned source-circle references. Place complete
native lines with `OffsetText` disabled first, then compare each axial
label's measured native width with its witness/arrow span. Enable text-only
offset only where that ink cannot fit with clearance; with the current
metrics, thread length stays centered at 4:1 but needs a shelf at 2:1.
Snapshot all three axial dimensions, not just the shelved ones. Reacquire
witness stations, arrow tips and current line/arrow reach after toggling text
mode, after placement and at final readback; smart-arrow flips do not permit
the physical stations to move.

Diameter text uses measured native geometry too. Center the collar label
between its classified horizontal witnesses, with at least 2 mm of settled
clearance to each. Put the two-row thread-diameter label below the lower
collar witness, then recompute the outer collar line's X from the thread
label's actual right edge. Text shelves and these outside moves target
2.2 mm of clearance, including a 0.2-mm settling allowance. The collar X
proof reads the classified native dimension line, not the annotation anchor.
The current pre-fit budget is intended to allow a natural 4:1 view, not
promise 5:1; actual native fitting still selects the scale.

The thumb guards reuse `_Reader`/`_dump_annotation`, including native
leaders, and run the complete `audit_dump` gating predicates with live view
geometry rather than a reduced list of overlap finders. Source, native
position and actual-ink checks remain mandatory, including text/line,
arrow/text and dimension-extension-at-text refusals. Source-only checks do
not establish a native visual pass or guaranteed scale; the scoped native
sheet and final shared audit still need qualification.

For example, `uv run python build.py drawing:sm_vn_knife_mount_dowel` writes
`cad/out/slddrw/sm-vn-knife-mount-dowel.SLDDRW`,
`cad/out/pdf/sm-vn-knife-mount-dowel.pdf` and
`cad/out/png/sm-vn-knife-mount-dowel_drawing.png`. Run these tasks through the
pipeline so they acquire the shared SolidWorks seat lock.
