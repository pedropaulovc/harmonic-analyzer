# McMaster-Carr vendor models (supplied locally, never tracked)

The `.SLDPRT` files this directory holds at build time are © McMaster-Carr —
vendor CAD downloads for the stock fasteners the machine uses. They are **not
in git** (see the `cad/references/mcmaster/*.SLDPRT` rule in the root
`.gitignore`): McMaster provides them to customers for product evaluation, not
for redistribution in a public repository.

To populate the directory, download each part's SOLIDWORKS model from its
`https://www.mcmaster.com/<part-number>/` product page (free, no account
needed) and save it here as `<part-number>.SLDPRT`.

Parts currently referenced by the diagnostics
(`cad/scripts/diagnostics/diag_build_mcmaster.py` and
`diag_build_91829A560.py` — reverse-engineered standalone replicas gated
against each vendor model's own mass properties):

| part number | what it is |
|---|---|
| 90114A511 | brass fillister head screw |
| 90126A211 | washer |
| 90280A108 / A194 / A196 / A199 / A201 | zinc fillister head screws |
| 91247A720 | grade-5 hex head screw |
| 91410A538 | square-head set screw |
| 91783A722 | stainless round head screw |
| 91829A560 | slotted precision shoulder screw (cone pivot) |
| 91882A221 / A412 | knurled thumb screws |
| 92865A585 | grade-5 hex head screw |
| 93075A194 | hex head screw |
| 94025A150 | cup-point set screw |
| 99607A213 | flared knurled thumb screw |

Ground rules (mirrored in the diagnostics themselves): the vendor files are
opened read-only and NEVER saved or modified; everything derived from them
(harvest dumps, replicas, renders, reports) goes only under the gitignored
`cad/out/`.
