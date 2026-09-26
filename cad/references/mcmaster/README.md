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
| 90114A511 | `fillister-screw` | Brass Fillister Head Slotted Screw |
| 90126A211 | `knife-hanger-washer` | Zinc-Plated Steel SAE Washer |
| 90280A108 | `foot-screw` | Steel Narrow Fillister Head Slotted Screw |
| 90280A194 | `bracket-screw`, `frame-side-screw` | Steel Narrow Fillister Head Slotted Screw |
| 90280A197 | `pedestal-hold-down-screw` | Steel Narrow Fillister Head Slotted Screw |
| 90280A199 | `swing-stop-screw` | Steel Narrow Fillister Head Slotted Screw |
| 90280A201 | `clamp-screw`, `slotted-screw` | Steel Narrow Fillister Head Slotted Screw |
| 90280A837 | `frame-cross-screw` | Steel Narrow Fillister Head Slotted Screw |
| 90631A007 | `cone-tip-block-nut` (catalogue-only; no vendor model) | Zinc-Plated Steel Nylon-Insert Locknut |
| 91247A720 | `knife-hanger-stud` | Medium-Strength Grade 5 Steel Hex Head Screw |
| 91255A148 | — (diagnostic recipe; `cone-tip-block-screw` until I31) | Black-Oxide Alloy Steel Button Head Hex Drive Screw |
| 91375A106 | `arbor-set-screw` | Alloy Steel Cup-Tip Set Screw |
| 91410A538 | `gooseneck-set-screw` | Steel Square-Head Cup-Point Set Screw |
| 91794A112 | `cone-tip-pinch-screw` | 18-8 Stainless Steel Fillister Head Slotted Screw |
| 92240A540 | `lag-screw` | 18-8 Stainless Steel Hex Head Screw |
| 91829A560 | `cone-pivot-screw` | Slotted 18-8 Stainless Steel Precision Shoulder Screw |
| 91882A221 | `thumb-screw` | Steel Raised Knurled-Head Thumb Screw |
| 91882A425 | `cone-lock-knob` | Steel Raised Knurled-Head Thumb Screw |
| 9275K141 | `tube-frame-cap` | Metal Round Cap |
| 92865A585 | `hex-bolt` | Medium-Strength Grade 5 Steel Hex Head Screw |
| 93075A150 | `cone-tip-block-screw` (catalogue-only; no vendor model) | Low-Strength Zinc-Plated Steel Hex Head Screw |
| 93075A194 | `hanger-screw` | Low-Strength Zinc-Plated Steel Hex Head Screw |
| 94025A150 | — (diagnostic recipe; `cone-tip-adjuster` until rule-12 E11) | 18-8 Stainless Steel Slotted Cup-Tip Set Screw |
| 94025A164 | `cone-tip-adjuster` | 18-8 Stainless Steel Slotted Cup-Tip Set Screw |
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
- [90280A197](https://www.mcmaster.com/90280A197/) was read live on
  September 23, 2026: #8-32 UNC class 2A, 3/4 in (19.05 mm) long under the
  head, fully threaded zinc-plated steel, flat tip, ASME B18.6.3; head
  diameter 0.27 in and height 0.156 in. Its head and thread match the
  harvested 90280A194 and 90280A199, so the shared fillister family recipe
  builds it from the length alone. No vendor SLDPRT has been harvested for
  this length yet.
- [91255A148](https://www.mcmaster.com/91255A148/) is the #6-32 x 1/2 in
  black-oxide alloy steel button head hex drive screw that held the cone tip
  block until I31 (U30, rule-12 W22). `cone-tip-block-screw` is now
  93075A150 (below); this entry stays as the replica recipe's provenance and
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

- [93075A150](https://www.mcmaster.com/93075A150/) (`cone-tip-block-screw`,
  MHA-140, from I31) and [90631A007](https://www.mcmaster.com/90631A007/)
  (`cone-tip-block-nut`, MHA-146) hold the cone tip block down. Both product
  pages were read through Browserbase on September 25, 2026. 93075A150 is a
  #6-32 x 5/8 in low-strength zinc-plated steel hex head screw, ASME
  B18.6.3, head 1/4 in across flats (0.244 min) and 3/32 in high (0.080 to
  0.093). 90631A007 is a #6-32 zinc-plated steel nylon-insert locknut, 5/16
  in across flats and 11/64 in high. They are catalogue-only: no vendor
  model is downloaded or kept here, so neither has a replica gate. The screw
  is the 93075A* family (`diag_mcmaster_hex_head.py`, whose laws are the
  replica-gated 93075A194's) at the catalogue sizes. The nut is its
  catalogue envelope, a sharp hex prism bored at the tap drill. Their
  standalone diagnostics are catalog-only runs.

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
