# McMaster-Carr vendor models (supplied locally, never tracked)

The `.SLDPRT` files this directory holds at build time are © McMaster-Carr —
vendor CAD downloads for the stock fasteners the machine uses. They are **not
in git** (see the `cad/references/mcmaster/*.SLDPRT` rule in the root
`.gitignore`): McMaster provides them to customers for product evaluation, not
for redistribution in a public repository.

To populate the directory, download each part's SOLIDWORKS model from its
`https://www.mcmaster.com/<part-number>/` product page (free, no account
needed) and save it here as `<part-number>.SLDPRT`.

Parts referenced by the production fastener fleet and its reusable diagnostic
recipes:

| part number | production part stem(s) | stock item |
|---|---|---|
| 90114A511 | `fillister-screw` | Brass Fillister Head Slotted Screw |
| 90126A211 | `knife-hanger-washer` | Zinc-Plated Steel SAE Washer |
| 90280A108 | `cone-tip-pinch-screw`, `foot-screw` | Steel Narrow Fillister Head Slotted Screw |
| 90280A194 | `bracket-screw`, `frame-side-screw` | Steel Narrow Fillister Head Slotted Screw |
| 90280A196 | `swing-stop-screw` | Steel Narrow Fillister Head Slotted Screw |
| 90280A199 | `slotted-screw` | Steel Narrow Fillister Head Slotted Screw |
| 90280A201 | `clamp-screw` | Steel Narrow Fillister Head Slotted Screw |
| 91247A720 | `knife-hanger-stud` | Medium-Strength Grade 5 Steel Hex Head Screw |
| 91410A538 | `gooseneck-set-screw` | Steel Square-Head Cup-Point Set Screw |
| 91783A722 | `lag-screw` | 18-8 Stainless Steel Round Head Slotted Screw |
| 91829A560 | `cone-pivot-screw` | Slotted 18-8 Stainless Steel Precision Shoulder Screw |
| 91882A221 | `thumb-screw` | Steel Raised Knurled-Head Thumb Screw |
| 91882A412 | `cone-lock-knob` | Steel Raised Knurled-Head Thumb Screw |
| 92865A585 | `hex-bolt` | Medium-Strength Grade 5 Steel Hex Head Screw |
| 93075A194 | `hanger-screw` | Low-Strength Zinc-Plated Steel Hex Head Screw |
| 94025A150 | `cone-tip-adjuster` | 18-8 Stainless Steel Slotted Cup-Tip Set Screw |
| 99607A213 | `pen-set-screw` | Stainless Steel Flared-Collar Knurled-Head Thumb Screw |

Ground rules (mirrored in the diagnostics themselves): the vendor files are
opened read-only and NEVER saved or modified; everything derived from them
(harvest dumps, replicas, renders, reports) goes only under the gitignored
`cad/out/`.
