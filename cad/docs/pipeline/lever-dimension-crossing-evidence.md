# Lever dimension-leader crossings: retained native evidence

The `27f0c11e` lever-only pilot completed its recipe in **91.57848239998566 s**,
including GTol placement, whole-view packing and native/PDF/PNG output. It is
**not visually accepted**. Cold reopen separately rejected three linked-title
X-origin fields moving 2.585815265774727 mm.

Receipt: `cad/out/reports/datum-policy-i2i_oplt/pilot.json`, SHA-256
`bd281f36661a6d52001c6104806df241e31df834e3529c65eb59eeedd399e119`.
The source copy remained SHA-256
`6a994561f19487029c938cd7cca5047acbdfbf686020514be538ef5a632e0841`
through build, close and final cleanup. All four original/guard sources were
unchanged and the native session inventory returned from empty to empty.

## Exact line intersections

Both source annotations contain the captured three-line circular callout chain:
arrow-tail joins a diagonal leg, which joins the horizontal text shoulder. The
offending segment is `native.lines[0]`, not a guessed linear extension line.
The target frame is reconstructed only from its four exact closed upright native
edges. The production segment/rectangle clipper confirms the intersection;
the diagonal's bounding rectangle is not used as proof.

| Actual leader | Other annotation | Inside native frame | Inside measured text cell |
| --- | --- | ---: | ---: |
| `FulcrumDia`, Ø6.50 | `NoseRadius`, BASIC R4.75 | 11.730126 mm | 10.598751 mm |
| `RD5`, Ø4.04 THRU ALL | `DetailItem349`, datum C | 8.732148 mm | 4.757773 mm |

The frame crossings are direct stroke evidence. The text cells are conservative
font cells, not exact glyph outlines; the retained PNG independently shows both
leaders through the corresponding text/frame regions.

Repeat without SolidWorks:

```
uv run python cad/scripts/diagnostics/audit_dimension_leader_crossings.py
uv run python -m pytest cad/scripts/test_dimension_crossing_evidence_drawing.py
```

The committed JSON holds four exact archived rows, not a full-sheet certificate.
Diameter-symbol bounds absent from the generic archived diagnostic are NOT
invented; both target frames/text cells needed by this replay were measured.

## Coverage gap and bounded next control

`validate_gtol_leader_clearance` checks GTol leaders against other text and all
annotation strokes against GTol bodies. Neither target here is a GTol. The
view-packing helper deliberately separates decorated view envelopes; it does not
repair collisions inside one view. An exact own-annotation join may be excluded;
that is not permission to skip other dimensions or datums. A type-14 datum joined
to its owning dimension also needs an explicit exact owner witness, not a broad
dimension/datum exemption. Datum C here is attached to an edge, not RD5.

Next proposed native control: one `IModelDocExtension.AlignDimensions(0, .001)`
on the exact dimension bank of the retained front view, after native callout and
GTol placement, on unique owned drawing/part copies. The bundled method and
`Auto-arrange_Dimensions_Example_CSharp` document this per-view selected-dimension
operation. Native success does not promise obstacle clearance: reread every
actual dimension stroke and other annotation body, keep values/tolerances/BASIC,
semantic entities and GTol/datum state exact, and reject either retained crossing
or any new cross-annotation collision. No native drawing save or automatic second
candidate is authorized by this proposal.

`SpaceEvenly=1` and `Stagger=3` are documented independent alignment alternatives,
but untested here. This evidence neither claims AutoArrange cannot solve the
layout nor that a repeated call will solve it. No production gate is weakened.
