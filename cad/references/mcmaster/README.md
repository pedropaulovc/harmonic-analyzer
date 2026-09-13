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
| 90280A108 | `cone-tip-pinch-screw`, `foot-screw` | Steel Narrow Fillister Head Slotted Screw |
| 90280A194 | `bracket-screw`, `frame-side-screw` | Steel Narrow Fillister Head Slotted Screw |
| 90280A199 | `slotted-screw`, `swing-stop-screw` | Steel Narrow Fillister Head Slotted Screw |
| 90280A201 | `clamp-screw` | Steel Narrow Fillister Head Slotted Screw |
| 90280A837 | `frame-cross-screw` | Steel Narrow Fillister Head Slotted Screw |
| 91247A720 | `knife-hanger-stud` | Medium-Strength Grade 5 Steel Hex Head Screw |
| 91410A538 | `gooseneck-set-screw` | Steel Square-Head Cup-Point Set Screw |
| 92240A539 | `lag-screw` | 18-8 Stainless Steel Hex Head Screw |
| 91829A560 | `cone-pivot-screw` | Slotted 18-8 Stainless Steel Precision Shoulder Screw |
| 91882A221 | `thumb-screw` | Steel Raised Knurled-Head Thumb Screw |
| 91882A425 | `cone-lock-knob` | Steel Raised Knurled-Head Thumb Screw |
| 9275K141 | `tube-frame-cap` | Metal Round Cap |
| 92865A585 | `hex-bolt` | Medium-Strength Grade 5 Steel Hex Head Screw |
| 93075A194 | `hanger-screw` | Low-Strength Zinc-Plated Steel Hex Head Screw |
| 94025A150 | `cone-tip-adjuster` | 18-8 Stainless Steel Slotted Cup-Tip Set Screw |
| 99607A213 | `pen-set-screw` | Stainless Steel Flared-Collar Knurled-Head Thumb Screw |

The cone-lock and swing-stop selections follow `cad/scripts/build_cone_lock_knob.py`
and `cad/scripts/build_swing_stop_screw.py`.

Catalog specifications checked on September 10, 2026:

- [92240A539](https://www.mcmaster.com/92240A539/) is an 18-8 stainless,
  ASME B18.2.1 standard hex-head screw: 1/4-20 UNC class 2A, 5/8 in long,
  fully threaded, with a 7/16 in across-flats head 5/32 in high. Its supplied
  SolidWorks model was harvested read-only and the tracked diagnostic replay
  matches its 824.0529 mm3 volume, 832.0689 mm2 area, and 22-face multiset.
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
