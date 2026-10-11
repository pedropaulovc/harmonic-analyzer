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
| 3606T118 | `vn-keeper-chain` (catalogue-only; no vendor model) | Bead Chain, Unfinished Brass, Trade Size 3 |
| 3606T811 | `vn-keeper-chain-link` (catalogue-only; no vendor model) | Loop Link for Brass Trade Size 3 Bead Chain |
| 6793K4 | `pd-transgear-removable` T12 (shop-reworked blank) | Steel ANSI #25 Plain-Bore Sprocket, 12 Teeth |
| 6793K11 | `pd-transgear-removable` T18 (shop-reworked blank) | Steel ANSI #25 Plain-Bore Sprocket, 18 Teeth |
| 6793K17 | `pd-transgear-removable` T24 (shop-reworked blank) | Steel ANSI #25 Plain-Bore Sprocket, 24 Teeth |
| 90114A511 | `vn-fillister-screw` | Brass Fillister Head Slotted Screw |
| 90126A211 | — (diagnostic recipe; the former `vn-knife-hanger-washer`, retired) | Zinc-Plated Steel SAE Washer |
| 90280A108 | `vn-foot-screw`, `vn-swing-stop-screw`, `vn-latch-hook-bracket-screw` | Steel Narrow Fillister Head Slotted Screw |
| 90280A194 | `vn-frame-side-screw` | Steel Narrow Fillister Head Slotted Screw |
| 90280A197 | `vn-pedestal-hold-down-screw` | Steel Narrow Fillister Head Slotted Screw |
| 90280A199 | — (diagnostic recipe; a former `vn-swing-stop-screw`) | Steel Narrow Fillister Head Slotted Screw |
| 90280A201 | `vn-clamp-screw` | Steel Narrow Fillister Head Slotted Screw |
| 90280A203 | `vn-slotted-screw` | Steel Narrow Fillister Head Slotted Screw |
| 90280A837 | `vn-frame-cross-screw` | Steel Narrow Fillister Head Slotted Screw |
| 91247A720 | — (diagnostic recipe; a former `vn-knife-hanger-stud`) | Medium-Strength Grade 5 Steel Hex Head Screw |
| 91251A108 | `vn-cone-tip-block-screw` (catalogue-only; no vendor model) | Black-Oxide Alloy Steel Socket Head Screw |
| 91251A157 | `vn-knife-hanger-stud` (catalogue-only; no vendor model) | Black-Oxide Alloy Steel Socket Head Screw |
| 91255A106 | — (diagnostic recipe; a former `vn-guide-lock-screw`) | Black-Oxide Alloy Steel Button Head Hex Drive Screw |
| 91255A108 | `vn-guide-lock-screw` (catalogue-only; no vendor model; SKU not yet read live) | Black-Oxide Alloy Steel Button Head Hex Drive Screw |
| 91255A148 | — (diagnostic recipe; a former `vn-cone-tip-block-screw`) | Black-Oxide Alloy Steel Button Head Hex Drive Screw |
| 91375A106 | `vn-arbor-set-screw` | Alloy Steel Cup-Tip Set Screw |
| 91410A538 | `vn-gooseneck-set-screw` | Steel Square-Head Cup-Point Set Screw |
| 91790A199 | `vn-transgear-arm-plate-screw` (catalogue-only; populated live SKU verified; 2-D PDF offered, CAD requires login) | 18-8 Stainless Steel Oval Head Slotted Screw |
| 91794A112 | `vn-cone-tip-pinch-screw` | 18-8 Stainless Steel Fillister Head Slotted Screw |
| 91794A055 | `vn-transgear-disc-screw` | 18-8 Stainless Steel Fillister Head Slotted Screw |
| 91794A077 | `vn-magnifying-bracket-screw` (catalogue-only; no vendor model) | 18-8 Stainless Steel Fillister Head Slotted Screw |
| 92240A540 | `vn-lag-screw` | 18-8 Stainless Steel Hex Head Screw |
| 91829A205 | `vn-transgear-pivot-screw` | Slotted 18-8 Stainless Steel Precision Shoulder Screw |
| 91829A560 | `vn-cone-pivot-screw` | Slotted 18-8 Stainless Steel Precision Shoulder Screw |
| 91882A221 | `vn-thumb-screw` | Steel Raised Knurled-Head Thumb Screw |
| 91882A425 | — (diagnostic recipe; `vn-cone-lock-knob` until 2026-09-29) | Steel Raised Knurled-Head Thumb Screw |
| 9275K141 | `vn-tube-frame-cap` | Metal Round Cap |
| 9414T1 | — (historical MHA-VN-016 until the 2026-10-08 terminal redesign) | Set Screw Shaft Collar for 1/16" Diameter |
| 94355A213 | `vn-cone-tip-collar` screw stock, ground to the custom dog-tip drawing | 18-8 Stainless Steel Flat-Tip Set Screw, #2-56 x 5/16" |
| 92865A585 | `vn-hex-bolt` | Medium-Strength Grade 5 Steel Hex Head Screw |
| 93075A194 | `vn-hanger-screw` | Low-Strength Zinc-Plated Steel Hex Head Screw |
| 93585A190 | `vn-cone-lock-knob` | Stainless Steel High-Profile Knurled-Head Thumb Screw |
| 94025A150 | — (diagnostic recipe; `vn-cone-tip-adjuster` until rule-12 E11) | 18-8 Stainless Steel Slotted Cup-Tip Set Screw |
| 94025A164 | `vn-cone-tip-adjuster` | 18-8 Stainless Steel Slotted Cup-Tip Set Screw |
| 93600A189 | `vn-transgear-arm-plate-locating-pin` (catalogue-only; no vendor model) | Passivated 316 Stainless Steel ISO 2338-m6 Dowel Pin |
| 9714K24 | `vn-rocker-bank-spring` (catalogue-only; no vendor model) | Wave Disc Spring |
| 9714K392 | `vn-cylinder-bank-spring` (catalogue-only; no vendor model) | Wave Disc Spring |
| 9715K43 | `vn-transgear-pivot-spring` (catalogue-only; no vendor model) | Curved Disc Spring |
| 97431A260 | `vn-transgear-retaining-ring` | Side-Mount External Retaining Ring |
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
  this genuine screw's tip is ground to its native dog diameter, length and
  edge-break dimensions. The page gives no socket depth or end break.
  [ASME B18.3-2012 Table 14](https://www.finesz.com/pic/ASME%20B18.3.pdf)
  supplies the #2 minimum key engagement (0.060 inch), flat-point minimum
  diameter (0.039 inch), 45-degree minimum point angle, 30–45-degree socket
  face chamfer and ±0.01-inch length tolerance for this length. The retained
  factory depiction is not vendor-exact geometry or a rework instruction.
  [BBI's ASME thread limits](https://www.brightonbest.com/download/pds/PDS_Thread_Details_Inch_Series.pdf)
  give the #2-56 3A pitch-diameter minimum, 0.0728 inch; the
  [2B UNC chart](https://amesweb.info/Screws/unc-thread-chart.aspx) gives the
  receiver maximum, 0.0772 inch. The terminal flat reader books their radial
  play and tilt with the collar's native position control. Because 2B gives
  no internal major/root maximum, the custom print separately controls the
  native MAX root gauge diameter; its wall proof does not invent a standard
  maximum. The same package prints the BASIC tap location and datum frame.
  94355A212 (#2-56 x 1/4 inch, also verified) loses because the shorter
  screw buries its drive at the collar's worst-case radial flat.
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
  block under U30 (rule-12 W22). `vn-cone-tip-block-screw` is now
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
- [91251A157](https://www.mcmaster.com/91251A157/) (`vn-knife-hanger-stud`,
  MHA-VN-024, two) hangs each MHA-SM-002 knife mount from the MHA-FR-002
  crossbar: it drops through the crossbar's counterbore, its head on the
  counterbore floor, into a #6-32 bottoming tap in the mount's top seat. It
  replaced the 1/2-13 hex bolt 91247A720 and its washer 90126A211. The
  product page was read live in October 2026: black-oxide alloy steel socket
  head screw, 6-32 UNC class 3A, right hand, 1-1/2 in under the head,
  partially threaded with a 3/4 in minimum thread length, flat tip, head
  Ø0.226 in x 0.138 in, 7/64 in hex drive, 170 ksi, Rockwell C37, ASTM A574.
  The page gives no socket depth; `diag_build_91251A157.py` takes ASME
  B18.3's #6 minimum key engagement, 0.064 in, and a plain cylindrical head,
  on the socket-head recipe it shares with 91251A108
  (`diag_mcmaster_socket_head.py`). It is catalogue-only: no vendor model is
  downloaded or kept here, so it has no replica gate, and its standalone
  diagnostic is a catalog-only run.
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
  `_mcmaster_91255a106.py` and `_mcmaster_91255a108.py` hold their separate
  SKU dimensions. It is catalogue-only: no vendor model is downloaded or
  kept here, so it has no replica gate, and its standalone diagnostic is a
  catalog-only run. Lost: 91255A105 (3/16 in; shortens the lock stack) and
  18-8 stainless 92949A106 (same head and length, 70 ksi, Rockwell B55;
  the alloy screw matches the 91255A148 family whose laws the recipe uses).
- [91255A108](https://www.mcmaster.com/91255A108/) (`vn-guide-lock-screw`)
  replaces 91255A106 per ruling R9-48: the 1/4 in screw engaged only 1.26D
  of the guide's blind tap at the worst case, so the guide's lock receivers
  became through taps and the screw 3/8 in under the head (2.02D at the
  worst case). [INFERENCE] 91255A108 is the 3/8 in length of the same
  91255A series; its page has not been read live. `_mcmaster_91255a108.py`
  carries that size, and `diag_mcmaster_button_head.py` builds it with the
  shared laws at that length; it is catalogue-only.
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
- [93600A189](https://www.mcmaster.com/93600A189/), MHA-VN-054, quantity two,
  was read live on October 9, 2026 in isolated Chromium (HTTP 200): passivated
  316 stainless, ISO 2338-m6, diameter 2.002–2.008 mm, nominal length 6 mm,
  both ends chamfered. The supplier does not publish a length or chamfer
  band. [ISO 2338:1997 Table1](https://cdn.standards.iteh.ai/samples/20001/5b26cece48c448b782c0de1eccb5b16c/ISO-2338-1997.pdf)
  bounds nominal6-mm stock to5.75–6.25 mm;
  [c≈0.35 mm](https://fullerfasteners.com/tech/iso-2338-specifications-parallel-pins/)
  is approximate, not a hard end limit or full-cylinder certificate.
  `vn_transgear_arm_plate_locating_pin_spec.py` owns the ordinary installation
  fits and proud set. The whole standard length family has at least0.17 mm
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
- [91829A205](https://www.mcmaster.com/91829A205/) (`vn-transgear-pivot-screw`,
  MHA-VN-041) is the hanger arm's pivot: its shoulder runs through the arm and
  the pivot spacer, and its thread enters the support bar's blind tap. The
  product page was read live on September 30, 2026: slotted 18-8 stainless
  steel precision shoulder screw, passivated, MS51575-11; shoulder Ø3/16 in
  (-0.001/0) x 1/2 in (0/+0.002), 8-32 UNC class 2A thread 3/16 in long,
  head Ø5/16 in x 5/32 in. The geometry is the vendor model's own:
  `diag_build_91829A205.py` replays the dimensions and solved sketch geometry
  read from `91829A205.SLDPRT` (harvested on amet on September 30, 2026; the
  read-only dump `cad/out/reports/mcmaster-91829A205-dump.json`), the
  91829A560 feature tree at this size: slot 1.27 wide x 1.5875 deep,
  head-rim chamfer 0.257969 and tip chamfer 0.374904 (both 45°), and the
  thread neck under the shoulder's end face. The neck is a R0.5715 fillet
  into a Ø3.0226 land, flat to 1.1938 below the end face, then a 45° flank
  back to the thread major, so full thread starts 1.7653 below the end face
  and the joint counts engagement from there. `diag_build_mcmaster.py
  91829A205` runs the replica gate against the vendor's volume
  451.9447 mm³, surface 485.1899 mm² and 20-face area multiset. Evidence
  SHA-256: native SLDPRT
  `bb7a805e75e4e656242ff71cc97cf7e34a7f97c4a90fd66f4b05cb3ebe24601c`.
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
  the underside of its head and the floor of the MHA-PD-018 arm's spot face, and
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
  MHA-CH-009 washer and the south MHA-CH-008 ear, set by a 0.60 blade, and holds the
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
