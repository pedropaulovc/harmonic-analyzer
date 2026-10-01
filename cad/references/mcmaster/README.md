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
| 3606T118 | `keeper-chain` (catalogue-only; no vendor model) | Bead Chain, Unfinished Brass, Trade Size 3 |
| 3606T811 | `keeper-chain-link` (catalogue-only; no vendor model) | Loop Link for Brass Trade Size 3 Bead Chain |
| 90114A511 | `fillister-screw` | Brass Fillister Head Slotted Screw |
| 90126A211 | `knife-hanger-washer` | Zinc-Plated Steel SAE Washer |
| 90280A108 | `foot-screw`, `latch-hook-bracket-screw` | Steel Narrow Fillister Head Slotted Screw |
| 90280A194 | `frame-side-screw` | Steel Narrow Fillister Head Slotted Screw |
| 90280A197 | `pedestal-hold-down-screw` | Steel Narrow Fillister Head Slotted Screw |
| 90280A199 | `swing-stop-screw` | Steel Narrow Fillister Head Slotted Screw |
| 90280A201 | `clamp-screw`, `slotted-screw` | Steel Narrow Fillister Head Slotted Screw |
| 90280A837 | `frame-cross-screw` | Steel Narrow Fillister Head Slotted Screw |
| 90283A193 | `transgear-knob-retaining-screw` (catalogue-only; no vendor model) | Zinc-Plated Steel Pan Head Slotted Screw |
| 91247A720 | `knife-hanger-stud` | Medium-Strength Grade 5 Steel Hex Head Screw |
| 91251A108 | `cone-tip-block-screw` (catalogue-only; no vendor model) | Black-Oxide Alloy Steel Socket Head Screw |
| 91255A106 | — (diagnostic recipe; a former `guide-lock-screw`) | Black-Oxide Alloy Steel Button Head Hex Drive Screw |
| 91255A108 | `guide-lock-screw` (catalogue-only; no vendor model; SKU not yet read live) | Black-Oxide Alloy Steel Button Head Hex Drive Screw |
| 91255A148 | — (diagnostic recipe; a former `cone-tip-block-screw`) | Black-Oxide Alloy Steel Button Head Hex Drive Screw |
| 91375A106 | `arbor-set-screw` | Alloy Steel Cup-Tip Set Screw |
| 91410A538 | `gooseneck-set-screw` | Steel Square-Head Cup-Point Set Screw |
| 91790A196 | `transgear-arm-plate-screw` (catalogue-only; no vendor model; SKU not yet read live) | 18-8 Stainless Steel Oval Head Slotted Screw |
| 91794A112 | `cone-tip-pinch-screw` | 18-8 Stainless Steel Fillister Head Slotted Screw |
| 91794A055 | `transgear-disc-screw` | 18-8 Stainless Steel Fillister Head Slotted Screw |
| 92240A540 | `lag-screw` | 18-8 Stainless Steel Hex Head Screw |
| 91829A205 | `transgear-pivot-screw` | Slotted 18-8 Stainless Steel Precision Shoulder Screw |
| 91829A560 | `cone-pivot-screw` | Slotted 18-8 Stainless Steel Precision Shoulder Screw |
| 91882A221 | `thumb-screw` | Steel Raised Knurled-Head Thumb Screw |
| 91882A425 | — (diagnostic recipe; `cone-lock-knob` until 2026-09-29) | Steel Raised Knurled-Head Thumb Screw |
| 9275K141 | `tube-frame-cap` | Metal Round Cap |
| 9414T1 | `cone-tip-collar` (catalogue-only; no vendor model) | Set Screw Shaft Collar for 1/16" Diameter |
| 92865A585 | `hex-bolt` | Medium-Strength Grade 5 Steel Hex Head Screw |
| 93075A194 | `hanger-screw` | Low-Strength Zinc-Plated Steel Hex Head Screw |
| 93585A190 | `cone-lock-knob` | Stainless Steel High-Profile Knurled-Head Thumb Screw |
| 94025A150 | — (diagnostic recipe; `cone-tip-adjuster` until rule-12 E11) | 18-8 Stainless Steel Slotted Cup-Tip Set Screw |
| 94025A164 | `cone-tip-adjuster` | 18-8 Stainless Steel Slotted Cup-Tip Set Screw |
| 97482A015 | `latch-hook-rivet` (catalogue-only; no vendor model) | Aluminum Domed Head Solid Rivet |
| 98296A026 | `transgear-collar-cross-pin` | 1050-1095 Spring Steel Slotted Spring Pin |
| 98296A027 | `pinion-strap-pin` | 1050-1095 Spring Steel Slotted Spring Pin |
| 98381A433 | `transgear-knob-drive-pin` (catalogue-only; no vendor model) | Alloy Steel Dowel Pin |
| 98381A434 | `crank-seat-drive-pin` (crank only; catalogue-only; no vendor model) | Alloy Steel Dowel Pin |
| 98381A473 | — (replica gate for the 1/8 series' end forms) | Alloy Steel Dowel Pin |
| 98381A474 | `transgear-latch-pin` (catalogue-only; no vendor model; SKU not yet read live) | Alloy Steel Dowel Pin |
| 99607A213 | `pen-set-screw` | Stainless Steel Flared-Collar Knurled-Head Thumb Screw |

The cone-lock and swing-stop selections follow `cad/scripts/build_cone_lock_knob.py`
and `cad/scripts/build_swing_stop_screw.py`.

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
- [91375A106](https://www.mcmaster.com/91375A106/), selected for MHA-147
  (#743), is a black-oxide alloy steel hex socket cup-point set screw:
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
  It was the `cone-lock-knob` until September 29, 2026.
- [93585A190](https://www.mcmaster.com/93585A190/) is an 18-8 stainless high-profile knurled-head thumb screw,
  1/4-20 x 3/4 in, selected by the user on September 29, 2026 for the
  `cone-lock-knob`. The product page returned HTTP 403 to automated fetches,
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
- [9414T1](https://www.mcmaster.com/9414T1/) (`cone-tip-collar`, MHA-096,
  replacing the turned brass tip bushing by user ruling 2026-09-29): the
  product page, read in a headless browser on September 29, 2026, gives a
  one-piece set screw shaft collar for 1/16 in shaft, 1/4 in OD, 3/16 in
  wide, black-oxide 1215 carbon steel, with one black-oxide steel hex-socket
  set screw. The vendor STEP was read locally (not committed) for what the
  page omits: 45 deg breaks 0.009375 in on all four edges and the #2-56
  radial cup-point set screw at mid-width, 0.050 in hex socket, its outer
  end 5/32 in from the axis. The numbers live in `cone_tip_collar_spec.py`;
  `diag_build_9414T1.py` builds them (flat-ended set screw at the cup rim,
  threads not modelled). No vendor model is kept here, so it has no replica
  gate; its standalone diagnostic is a catalog-only run.
- [90280A197](https://www.mcmaster.com/90280A197/) was read live on
  September 23, 2026: #8-32 UNC class 2A, 3/4 in (19.05 mm) long under the
  head, fully threaded zinc-plated steel, flat tip, ASME B18.6.3; head
  diameter 0.27 in and height 0.156 in. Its head and thread match the
  harvested 90280A194 and 90280A199, so the shared fillister family recipe
  builds it from the length alone. No vendor SLDPRT has been harvested for
  this length yet.
- [91255A148](https://www.mcmaster.com/91255A148/) is the #6-32 x 1/2 in
  black-oxide alloy steel button head hex drive screw that held the cone tip
  block under U30 (rule-12 W22). `cone-tip-block-screw` is now
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

- [91251A108](https://www.mcmaster.com/91251A108/) (`cone-tip-block-screw`,
  MHA-140) holds the cone tip block down per the user ruling of September 29,
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
- [91255A106](https://www.mcmaster.com/91255A106/) (`guide-lock-screw`,
  MHA-176, eight) holds the four guide locks to the platen guides per ruling
  R9-31 (September 30, 2026): these screws ride the platen, and the MHA-030
  fillister head there sweeps into the transgear hanger arm, so they alone
  take a button head with the same 1/4 in shank. The product page was read
  in a headless browser on September 30, 2026: black-oxide alloy steel button
  head hex drive screw, #4-40 UNC class 3A, right hand, 1/4 in under the
  head, fully threaded, flat tip, standard-profile head Ø0.213 in x 0.059 in,
  1/16 in hex drive, 140 ksi, Rockwell C39, ASME B18.3 / ASTM F835. The page
  gives nothing else, so `diag_build_91255A106.py` carries the 91255A148
  vendor-measured laws over in proportion: flat top 7/5 of the hex, band
  0.15 of the head height at 10 deg, fillets 0.05, socket floor 0.55, the
  60 deg countersink. It is catalogue-only: no vendor model is downloaded or
  kept here, so it has no replica gate, and its standalone diagnostic is a
  catalog-only run. Lost: 91255A105 (3/16 in; shortens the lock stack) and
  18-8 stainless 92949A106 (same head and length, 70 ksi, Rockwell B55;
  the alloy screw matches the 91255A148 family whose laws the recipe uses).
- [91255A108](https://www.mcmaster.com/91255A108/) (`guide-lock-screw`)
  replaces 91255A106 per ruling R9-48: the 1/4 in screw engaged only 1.26D
  of the guide's blind tap at the worst case, so the guide's lock receivers
  became through taps and the screw 3/8 in under the head (2.02D at the
  worst case). [INFERENCE] 91255A108 is the 3/8 in length of the same
  91255A series; its page has not been read live. `diag_build_91255A108.py`
  builds it with the 91255A106 recipe at that length; it is catalogue-only.
- [98296A027](https://www.mcmaster.com/98296A027/) was read live on
  September 25, 2026: 1050-1095 spring steel slotted spring pin, 1/16 in
  diameter, 1/2 in long, 0.012 in wall, for a 0.062-0.065 in hole,
  ASME B18.8.2, chamfered ends, no finish listed; 430 lbf double shear,
  Rockwell C43 minimum. The page gives no slot or chamfer size. No vendor
  SLDPRT has been harvested for it yet.
- [98296A026](https://www.mcmaster.com/98296A026/) (`transgear-collar-cross-pin`,
  MHA-154) was read live on September 30, 2026: the same 1050-1095 spring
  steel slotted spring pin, unplated, 1/16 in diameter, 9/16 in long,
  0.012 in wall, for a 0.062-0.065 in hole, chamfered ends, no diameter
  tolerance stated. No vendor SLDPRT has been harvested for it yet.
- Both spring pins are rows of `diagnostics/diag_mcmaster_spring_pin.py`,
  which models each as installed, a 1/16 in tube with the catalog wall,
  without slot or chamfer; `diag_build_98296A026.py` and
  `diag_build_98296A027.py` are its per-size runs.
- [98381A434](https://www.mcmaster.com/98381A434/) (`crank-seat-drive-pin`,
  MHA-173, crank only) was read live on September 30, 2026: alloy steel dowel pin,
  unplated, 3/32 in diameter (+0.0001 to +0.0003 in), 1/4 in long, end shape
  "Round x Chamfer". The page states neither the end radius nor the chamfer,
  so `diag_build_98381A434.py` models the plain nominal cylinder. It is
  catalogue-only: no vendor model is downloaded or kept, so it has no replica
  gate, and its standalone diagnostic is a catalog-only run.
- [98381A433](https://www.mcmaster.com/98381A433/) (`transgear-knob-drive-pin`,
  MHA-155, the knob shaft's pair) was read live on September 30, 2026: alloy
  steel dowel pin, unplated, 3/32 in diameter (+0.0001 to +0.0003 in), 3/16 in
  long, end shape "Round x Chamfer". As for 98381A434, `diag_build_98381A433.py`
  models the plain nominal cylinder; catalogue-only, no vendor model, no
  replica gate.
- [98381A473](https://www.mcmaster.com/98381A473/) (formerly
  `transgear-latch-pin`; since R9-50 the 1/8 series' end-form gate) was read
  live on September 30, 2026:
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
  models those end forms, chamfered end at y = 0 (the end pressed into the
  arm), and its standalone run is the replica gate against that harvest. The
  diameter band is the family's, read on the 98381A433/434/489 pages.
- 98381A474 (`transgear-latch-pin`, MHA-169, since R9-50) is the 7/8 in
  length of the same 1/8 series (98381A467 1/8 in through 98381A479 1-3/4 in,
  dt-logs `transgear-evidence/mcmaster-skus.md`, "Round 6 — additions"); a
  reseller lists it as 1/8 x 7/8
  (https://www.kvmtools.com/products/mcmaster-98381a474-dowel-pin-pack-of-50-alloy-steel-1-8-diameter-7-8-long).
  [INFERENCE] Its own page is not yet read live. `diag_build_98381A474.py`
  carries the 98381A473 harvest's end forms at the longer length; it is
  catalogue-only: no vendor model, no replica gate, and its standalone
  diagnostic is a catalog-only run.
- [90283A193](https://www.mcmaster.com/90283A193/) (`transgear-knob-retaining-screw`,
  MHA-158) clamps the knob cup on the knob shaft's rear end face. The 90283A
  series was read live on September 30, 2026: 90283A191 (5/16 in) and
  90283A192 (3/8 in) are zinc-plated steel slotted pan head screws, 8-32 UNC
  class 2A, fully threaded, flat tip, pan head Ø0.322 in x 0.096 in high,
  length under the head; the 90283A193 page resolves in the same series at
  7/16 in, and its head and thread are taken from those rows. The page gives
  no crown or slot shape, so `diag_mcmaster_pan.py` reuses the 90280A
  fillister family's head laws (band 0.8 of the height under a spherical
  crown, slot 0.135 of the head Ø wide and 1.5 widths deep). It is
  catalogue-only: no vendor model is downloaded or kept here, so it has no
  replica gate, and its standalone diagnostic is a catalog-only run.
- [91829A205](https://www.mcmaster.com/91829A205/) (`transgear-pivot-screw`,
  MHA-168) is the hanger arm's pivot: its shoulder runs through the arm and
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
- [91794A055](https://www.mcmaster.com/91794A055/) (`transgear-disc-screw`,
  MHA-161, three) joins the brass disc hub's flange to the 120T disc: each
  head sits on the flange and the thread enters one of the disc's through
  taps. The product page was read on September 30, 2026: 18-8 stainless
  steel slotted fillister head, #0-80 UNF class 2A, 1/4 in under the head,
  fully threaded, high narrow head Ø0.096 in x 0.055 in. The user supplied
  the vendor model `91794A055.SLDPRT`, harvested on amet on September 30,
  2026 into the read-only dump `cad/out/reports/mcmaster-91794A055-dump.json`.
  It is not the 90280A narrow-fillister tree, so `diag_build_91794A055.py`
  replays its own laws (in `transgear_disc_screw_spec.py`) instead of
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
- [91790A196](https://www.mcmaster.com/91790A196/) (`transgear-arm-plate-screw`,
  MHA-166, two) holds the transgear arm plate on the arm: each head sits flush
  in a plate countersink and the thread enters the arm's through tap; at
  assembly each tip is cut flush with the arm's front face and the cut end
  broken 0.1 max (R9-44: with the ASME B18.6.3 length band, +0/-0.03 in, no
  fixed length gives 1.5D in the tap and keeps the tip out of the guide-lock
  sweep). The SKU is [INFERENCE]: the 5/8 in length of the series by the
  90280A numbering this file records (194 = 1/2 in, 197 = 3/4 in), not yet
  read live; the vendor check is pending. The 91790A series was read live on
  September 30, 2026 at 3/8 in (91790A192) and 1/2 in: 18-8 stainless steel,
  bright, slotted 82° oval head, 8-32 UNC class 2A, fully threaded, ASME
  B18.6.3; head Ø0.312 in, 0.152 in total height of which the oval top is
  0.052 in; the length is measured from the top of the bevel. The page gives
  no slot, tip or crown radius, so `diag_mcmaster_oval.py` models the crown
  as a spherical cap through the head rim, runs the 82° bevel down to the
  thread major (the catalog's 0.100 in bevel reaches the cone's theoretical
  sharp, inside the shank), and takes the slot, tip and thread-runout laws
  of the 90280A fillister family (slot 0.135 of the head Ø wide and 1.5
  widths deep). Its catalog build is the supplied 5/8 in screw; the
  production part draws it cut to the installed length with the break in
  place of the factory tip. It is catalogue-only: no vendor model is
  downloaded or kept here, so it has no replica gate, and its standalone
  diagnostic is a catalog-only run.
- [97482A015](https://www.mcmaster.com/97482A015/) (`latch-hook-rivet`,
  MHA-175, two) joins the latch hook's strip to the latch-hook bracket's
  flap; the flap's holes are drilled at assembly through the hook's. The
  family page was read live on September 30, 2026 (dt-logs
  `transgear-evidence/mcmaster-skus.md`, "Round 10 — hook rivets"): 1100
  aluminum domed head solid rivets, 1/16 in diameter; 97482A015 is the
  0.188 in (3/16) length, for material up to 0.157 in thick. The 97482A010
  row (1/8 long) read live gives the round domed head Ø0.13 in x 0.051 in
  high and a 0.067 in (#51 drill) hole; 97482A015 is taken to share them
  [INFERENCE]. The contract row asked for steel, but McMaster lists no steel
  1/16 in solid rivet (all 16 in the family filter are aluminum), so the part
  is aluminum; SolidWorks has no plain 1100 wire, and the page states no
  temper, so the part carries the library's `1100-O Rod (SS)`. The page gives
  no head radius, so `diag_build_97482A015.py` models the dome as the
  spherical cap through the head rim and apex (R = 1.6998 mm) [INFERENCE].
  R9-51 moved the joint from the 1/8 length in Ø1.6 holes: the ASME B18.1.1
  shank (Ø0.064 in max) enters the least printed Ø1.65 +0.10/0 hole with
  0.024 mm to spare, and the shortest rivet (-0.016 in) on the thickest
  2.2 mm grip in the largest hole leaves 2.39 mm³ for the shop head against
  MIL-R-47196A's 2.11 mm³ (Ø0.081 x 0.025 in). The vendor's #51 hole
  (Ø1.7018) lies inside the band. It is catalogue-only: no vendor model was
  supplied or kept here, so it has no replica gate, and its standalone
  diagnostic is a catalog-only run.

- [3606T118](https://www.mcmaster.com/3606T118/) (`keeper-chain`, MHA-149)
  and [3606T811](https://www.mcmaster.com/3606T811/) (`keeper-chain-link`,
  MHA-150) tie the crank's taper pin to the arm as one loop through the eye
  and the ring. Both product pages were read on September 29, 2026. 3606T118 is
  unfinished brass bead chain, trade size 3, 3/32 in beads, 20 lbf, not for
  lifting. 3606T811 is the brass loop link that joins the cut ends into a loop.
  McMaster publishes no CAD for either item, and no dimension beyond the bead
  diameter. The 3.2426 mm pitch is the trade-size-3 average of 94 beads per foot
  (Ball Chain Mfg. and Frank Winne size charts). The link's 9 mm length is the
  listed #3 connector size, and its proportions (domed capsule, crimps, a side
  mouth over each dome narrower than a bead, rod slot along the top) are read
  off McMaster's 3606T811 photograph. The rod and the link's wall and openings are assumptions named in
  `keeper_chain_spec.py`, so neither part has a replica gate.

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

For example, `uv run python build.py drawing:knife_hanger_washer` writes
`cad/out/slddrw/knife-hanger-washer.SLDDRW`,
`cad/out/pdf/knife-hanger-washer.pdf` and
`cad/out/png/knife-hanger-washer_drawing.png`. Run these tasks through the
pipeline so they acquire the shared SolidWorks seat lock.
