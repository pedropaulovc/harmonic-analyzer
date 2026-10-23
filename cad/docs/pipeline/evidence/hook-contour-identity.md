# Hook supplier contour identity

Supplier eye dimensions are references to the **physical finished part**, not to
its nominal stock diagram. Preserve the model frame: eye centre at the model
origin, eye in XY, shank towards −Y. Do not substitute the outer eye, a bend or
tip circle, a nominal carrier, or a nearby curve when the required contour is
absent.

## Channel spring hook (9489T111)

The physical eye OD is 12.7 mm and ID is 6.35 mm. The settled verifier requires:

- the expected finished configuration on both finished views;
- exactly one non-null, non-dangling native attachment, with selection type 46
  (`SILHOUETTE`), and agreement between the native count, entity and type arrays;
- a finite native analytic circle at the model origin (centre coordinates within
  1e-8 m), normal Z within 1e-8 of ±1, and diameter within 1e-5 mm of the
  corresponding physical eye size;
- the expected native drawing view and exact referenced source-part path;
- the attached drawing face mapped unconditionally into the current referenced
  source part with `IModelDocExtension.GetCorrespondingEntity2`; a missing
  correspondence is refused;
- that mapped source face's owning feature being the source part's authoritative
  `Wire`, compared in the same native context with `ISldWorks.IsSame == 1`, not
  a matching name, feature ID or drawing-context feature;
- a finite mapped-source torus at the same origin and Z axis, with the catalogue
  eye mean radius and wire radius, using the unchanged 1e-5 mm diameter tolerance.

Do not compare a post-rebuild annotation with a silhouette handle retained from
before the settling rebuild. The 2026-10-22 native diagnostic at source
`2942dd0651b13be2ad64af9568f8323f2f3bd551` read one EyeOD attachment of type 46;
its captured and attached CircleParams were identical:

```text
(-2.102257677834285e-10, -7.358970724458125e-11, 0,
 0, 0, 1, 0.006350000187332174)
```

The old comparison used a face or feature from the drawing context against an
object from the source-part context. The complete `c34ee90f48590b46e19479f30c959d8b0fcb2cff`
readback distinguishes this from missing geometry: both physical ID entries and
the OD entry are exact circles, but all three first reject at the direct
cross-context owner comparison (`IsSame == 0`). Both feature proxies are named
`Wire`, ID 34, and compare equal to themselves. Matching names and IDs therefore
do not repair this identity test.

The repair retains only dimension keys and contracts, not pre-rebuild COM
handles. For the annotation's current attached silhouette, it maps `GetFace()`
into the current view's referenced source part before testing owner identity
and the source torus. The complete native readback returns a mapped source face
whose owner compares equal to source `IPartDoc.FeatureByName("Wire")` (`1`).
The reverse `IView.GetCorrespondingEntity(source_face)` returns null; that
unsupported-in-practice roundtrip is not used as a substitute identity test.
Both native source builders explicitly name their circular-profile sweep
`Wire` (`diag_build_9489T111._sweep_wire` and
`diag_build_9490T1._sweep_wire`); the finished-stock trim keeps that feature.
`Wire` also owns the bend, so the centre, axis and catalogue torus radii remain
independently mandatory. No fresh visible-entity scan or self-membership test
is used during verification.

The same native enumeration returned two ID entries with identical circle
parameters. Enumerator entries are not annotation attachments: multiple visible
entries must not disable the exactly-one-attachment guard. Wrong diameter,
foreign owner, missing contour and additional annotation attachments are refused.

The complete CH source-eye torus is centred at
`(-2.102257677834285e-10, -7.358970724458125e-11, 0)`, with Z axis, major radius
`0.004762500187332174 m` and minor radius `0.0015875 m`. Source and view both
reference `Default` configuration ID 0, with HLR mode 2 and an exact source path
whose physical file identity also matches. These are actual identity/frame
readbacks, not proof that the repaired recipe has reached native save. Final
native qualification must still exercise the corrected guard and both save
boundaries.

The existing pre-save layout check refreshes every view before the attachment
readback. The attachment verifier itself performs no geometry refresh, rebuild,
repair or source-configuration activation. It runs again on the existing
`after_drawing_save` checkpoint, after a successful native SaveAs3 context and
file check, before PDF export. It temporarily activates drawing sheets and
restores FINISHED for the established export semantics; this is drawing UI state,
not part-configuration activation.

This second check proves the **still-open post-save document**. It is not a cold
reopen, nor independent proof of bytes persisted on disk. The shared checkpoint
also reports attempted saves on failure, so an after-event without successful
save/leaf evidence must never be presented as save proof.

## Counterweight boss hook (9490T1)

The required physical eye ID is 7.9375 mm. Its modelled physical OD is 17.5895 mm;
the nominal as-supplied stock diagram is a separate source and is not a contour
oracle. Keep the exact physical-ID criteria: centre within 1e-8 m of the model
origin, normal Z within 1e-8 of ±1 and diameter within 1e-5 mm. Discovery and
post-rebuild identity must agree on the actual native contour type and finished
source configuration; absence is an error, never permission to select the OD.

The supplemental native census at source
`322abecf0de187a880dc2d8d4f67fa012230e7cd` found no exact ID among either the
visible silhouettes or the nine visible model edges. The three circular edges
were shank sections with Y normals, not an alternate native ID. The owning
`Wire` eye surface was a torus with centre
`(-4.4201138409138974e-11, -1.3548712585881306e-10, 0)`, Z axis, major radius
`0.006381749644849558 m` and minor radius `0.002413 m`. Its analytic inner
diameter is `7.937499289699116 mm`; the model-to-view transform had identity
rotation and scale 4. This is the expected model frame, not permission to
dimension a nominal replacement or change selection type.

The initial HLR setup precedes imported control annotations. The existing
`_drawing_view_display.set_hidden_lines_removed` contract documents that these
annotations can leave the edge set unregenerated and that
`IView.UpdateViewDisplayGeometry` alone does not rebuild it. A real HLV-to-HLR
transition with both native mode readbacks, followed by
`UpdateViewDisplayGeometry`, was therefore exercised before discovery.
**It did not recover the missing SM ID.** The complete `c34` native census still
contains no exact origin-ID circle. An ordering or refresh change alone is not
a demonstrated repair. Do not retry against a different type, diameter, view or
configuration when the strict query finds no ID.

Discovery therefore uses the existing primary coordinate-acquisition seam, not
a fallback chain of enumerators. From the current finished view's exact source
part and configuration, it finds exactly one `Wire` eye torus satisfying the
strict native owner, centre, axis and radii predicates. It projects that native
torus's top-inner point `(cx, cy + major_radius - minor_radius, cz)` into the
drawing view with `model_points_in_view`, then calls the established
`_select_view_entity(..., "SILHOUETTE", sheet_xy)` hit test.

The coordinate hit test can select its drawing-view container as well as the
physical contour. Its initial selection must contain exactly one non-null
native type-46 silhouette, optionally accompanied by exactly one native type-12
drawing view whose `ISldWorks.IsSame` identity is the expected front view.
Additional geometry, duplicate silhouettes or views, foreign views and missing
entities are refused. The silhouette must already prove the exact finite
origin-ID circle and mapped-source `Wire` torus; matching names are insufficient.

The recipe then unconditionally selects that validated native silhouette
directly through the existing `ISilhouetteEdge.Select2` helper. It does not retry
another acquisition method. Before dimension creation, the resulting current
selection must have **count one, type 46**, and pass the physical-circle and
source-owner predicates again. A two-object UI hit-test result is never accepted
as the dimension's attachment selection. The point is only an acquisition input,
not a synthetic contour or nominal dimension. There is no visible-enumerator
rescue, edge substitution, outer-eye substitute or relaxed criterion.

`IModelDocExtension.SelectByID2` documents the `SILHOUETTE` selection string.
The existing pinion-bracket coordinate-silhouette caller records a real farm
positive control, whereas `SelectByRay` is not documented to select silhouettes.
Those contracts support the primary acquisition design. The `7d815` readback
below now supplies a native positive acquisition result for SM itself, but not
proof of direct single-entity reselection, dimension creation or attachment
survival. Those remain obligations of the repaired normal native leaf.

The final and still-open post-native-save checks retain type 46 and exactly one
live attachment, and reuse the same strict circle, source-view, native feature
and torus predicate as discovery. The label's physical ID remains mandatory:
the outer eye is not an alternative. As for CH, refreshes belong to the existing
pre-save layout check, not the post-save observer, and successful save/leaf
evidence is required before claiming post-save proof.

## Rejected native candidate 10ae

Source `10ae3ca0e95afd612b324f792ef142ffd281c136` produced two failed normal
drawing leaves in run `20261022T201714479Z-50388d94c538424fae4dc16fafd5c040`,
build `20261022T201743.641221Z-cd92a187b96d465eb7c0a837b1743981`. Both source
part leaves succeeded, but neither drawing reached a qualified native save:

- CH stopped during discovery with `EyeOD: unchanged spring eye has no circular
  silhouette`.
- SM stopped during discovery with `unchanged counter eye has no exact ID
  circular silhouette`.

These messages establish **zero accepted contours**, not zero raw native
circles. This source's new view, referenced-path, native-feature and torus
predicates can reject an otherwise circular contour. The two worker logs and
native events contain no geometry census; both explicitly report no forensic
captures. There is no successful feature-equality, annotation, after-SaveAs3 or
PDF proof from this attempt.

The exact 2942-to-10ae source comparison shows no new CH pre-discovery mode,
configuration or refresh call. `_drawing_view_display`, `_drawing_edges` and
`_drawing_common` have identical Git blobs between those sources. The later
layout-before-reference refresh order was not reached by the CH failure, so it
does not explain the new pre-creation rejection.

## Complete native readback at c34

The approved combined normal drawing run
`20261022T214811367Z-f2dd38415a1d4a20bc1333f7621235be`, build
`20261022T214835.817289Z-6919e84a3f174b3ebeccadff0b97e482`, preserved the original
predicate-time snapshot separately from later independent getter observations.
Both drawing leaves retained their original fatal errors. The two source-part
leaves were cache hits; there are no qualified drawing saves or PDFs from this
attempt.

- CH: 48 native silhouette entries, five analytic circles, two exact origin-ID
  entries and one exact origin-OD entry. All three physical entries first reject
  at the direct drawing/source feature equality. Native drawing feature
  self-equality is 1; source-mapped owner equality to source `Wire` is 1.
- SM: 49 native silhouette entries, five analytic circles, only the OD at the
  origin and no exact physical ID. The ten visible model edges contain only
  three circular shank sections, with Y normals; they are not an alternate ID.
  The source eye torus has the exact centre, axis and radii listed above.
- Both: referenced and active source configurations are `Default`, ID 0; HLR
  mode is 2; source paths and physical file identities match. Model-to-view
  rotation is identity, with scale 5 for CH and 4 for SM.

The supported visible-silhouette enumeration is
`IView.GetVisibleEntities2(component, 4)`, not an all/hidden-contour API.
Face-generated silhouette curves are transient and unselectable and cannot
replace the required native `ISilhouetteEdge` attachment. Correspondence,
matching names and torus geometry alone do not waive the exact circle, native
kind, source-owner or annotation-count predicates.

Full worker logs and structured census packets are retained out of tree in
`D:/farm-runs/rolling-main-post-v44-20261021`; provisional census collectors are
not part of the permanent repair.

## Actual normal pair at a269

Source `a26968d210944376eb94625d8c1a44a6a7dbc75b`, run
`20261022T232742226Z-53e97735a0dd4255949373180a1b41e9`, build
`20261022T232809.254333Z-adb02773b2b24e458d4aefe89596c6a6`, had two source-part
cache hits and two failed drawings. Neither produced a qualified PDF, PNG,
native drawing or layout audit.

CH passed strict contour discovery and created supplier references. The first
settled layout callback then refused the finished front's native `GetOutline()`:

```text
(0.06266199906333915, 0.10143093577628477,
 0.13733800093666088, 0.2710690642237152) m
```

The actual 12.7 mm sheet-zone margins give the unchanged finished cell
`(0.0127, 0.0651, 0.4191, 0.2667) m`. Its top overflow is
`4.3690642237152 mm`; bottom clearance is `36.33093577628477 mm`. The outline
midpoint equals the former front centre `(0.100, 0.18625) m`. A downward
translation of 5 mm is the smallest whole-millimetre correction satisfying
those recorded bounds. It changes only the finished front centre to
`(0.100, 0.18125) m`, predicting native-outline Y bounds
`(0.09643093577628477, 0.2660690642237152) m`.

This is a placement correction inside the existing cell, not a larger cell,
smaller scale or relaxed guard. Control values and explicit text anchors,
isometric view and stock-sheet placement remain unchanged. `GetOutline()` is
not documented as a tight printed-edge envelope: the readback does not prove
that part geometry itself crosses the border or identify display padding.
The next native leaf must prove layout and leader readability. Because layout
ran before attachment verification, this attempt proves neither post-rebuild
attachment survival nor native-save survival.

SM found its unique exact source torus and the coordinate-selection helper
returned a non-null object. It then failed the immediate count/type guard:
`counter eye ID selection must be one live physical silhouette`. The native
count and type were not emitted. Do not infer count one, type 46, an acquired
ID circle, or an alternate valid type from that exception.

The subsequent changed-source attempt retained complete failure-only
observations before selection cleanup. The original predicate-time values are
separate from later getter observations; individual getter errors did not
replace the original exception. This provisional collector is not part of the
permanent repair.

## Actual selection and note boundaries at 7d815

Source `7d815e54d5d115bc15c9116ef8a4a014a9e2976a`, run
`20261023T000132301Z-713bd8ee25904fa1a57fbcd1c713daab`, build
`20261023T000202.778340Z-1565d5157ca04938aa556af1dac98f8b`, again had two
source-part cache hits and two failed drawings. No PDF, PNG, native drawing or
layout audit was exported. Its complete immutable handoff is
`hook-contour-proof/placement-selection-7d815e54d-native-handoff.json` under the
out-of-tree evidence directory.

### SM: expected view container plus exact physical ID

The original guard read `selected_count = 2` and raised
`counter eye ID selection expected count=1; actual count=2`. Its type, entity
and strict-circle reads were consequently **not executed**.

The independent later read returned the same count, with exactly these objects:

1. Type 12, drawing view `Drawing View1`, configuration `Default`, HLR mode 2,
   exact source-part path and the same model-to-view transform as the expected
   front. The packet did not compare this selected view to the expected front
   with `IsSame`; the repaired production guard must do so.
2. Type 46, native `ISilhouetteEdge`, analytic circle identity 3002:

   ```text
   (-4.4201138409138974e-11, -1.3548712585881306e-10, 0,
    -0, -0, -1, 0.003968749644849558)
   ```

   This is physical ID `7.937499289699116 mm`, not the OD or an edge. Its face
   maps into the referenced source part; the mapped owner compares equal to
   authoritative source `Wire`, feature ID 49 (`IsSame == 1`). Direct
   drawing-owner/source-owner equality is 0, as in the earlier context census.
   The mapped torus has the exact centre, Z axis, major radius
   `0.006381749644849558 m` and minor radius `0.0024129999999999998 m`.

The source torus produced model point
`(-4.4201138409138974e-11, 0.003968749509362433, 0) m` and projected sheet point
`(0.09999999999999999, 0.2374969178902139) m`. The native transform had identity
rotation, translation `(0.10000000017680455, 0.22162191985276417, 0) m` and
scale 4. Thus primary native point acquisition found the physical ID even
though visible-silhouette enumeration did not list it. These are distinct API
observations, not a claim that enumeration is complete.

The raw untruncated 6752-byte observation is retained as
`hook-contour-proof/placement-selection-7d815e54d-raw-copy-0.json`, SHA-256
`8fdcd142b13ec40850a893773da9dad9a23b5f6ad510184bb6a090c839c0a0ce`.
It proves the UI selection-composition root, not successful normalization or a
saved dimension. The permanent repair validates the complete initial group
before direct single-silhouette reselection; it never discards unvalidated
additional contours.

### CH: model outline passes; sheet-note context remains to prove

The 5 mm placement correction passed the earlier native view-outline refusal.
The next unchanged model-cell guard rejected a note with native bounds
`(0.01574120401337792, 0.05630050167224085, 0.04481188628762542,
0.060113050167224125) m`, below cell minimum Y `0.0651 m`.

The bounds match the source's supplier-note placement at `(0.016, 0.060) m`
by inference; the failure did not emit that note's text or native owner type.
The SDK note helper clears selection but does not deactivate a drawing view.
Both hook recipes now explicitly enter checked sheet context before creating
their existing FINISHED property-linked notes, reusing their stock-sheet
pattern: `ActivateView("")`, `GetEditSheet() == True`, and no active drawing
view. A false `ActivateView("")` result is normal for sheet context.

The note coordinates, property links, resolved source text, heights, sheet
border and geometry-only cells are unchanged. Retained notes on both sheets
must have native owner type 1, exact authored links or literals, exact resolved
text (normalizing only CRLF), and native extents wholly inside the actual sheet
border. Model views, dimensions and genuinely view-owned notes retain the
unchanged model-cell guard. This is an ownership correction, not a hidden note,
a larger model cell or permission to skip a guard. Its native outcome, and
both recipes' subsequent rebuild/save boundaries, remain unproven until the
next changed-source production pair.

## Production root corrections exercised at a06

Source `a06dd6c3b57497825d45d95a77cc7e3437d287bd`, run
`20261023T005708129Z-602010ea5bbb4ef2af13b5c407c9e212`, build
`20261023T005745.286345Z-9969d5f3cd7042d5ab8089b1df698d59`, completed with two
part cache hits and two failed drawings. The immutable handoff is
`hook-contour-proof/final-root-a06dd6c3b-native-handoff.json`.

SM reached successful native `drawing.assert_supplier_reference_dimension`
spans for `EyeID` and `SupplierThreadMajor`. Correlating those spans with the
exact source proves that the complete coordinate-pick group passed validation,
the unconditional direct silhouette reselection passed count1/type46/current
physical-circle/source-owner checks, and the diameter was created. These
primitive guard values were not individually emitted; this is source-correlated
successful native control flow, not a new raw geometry census.

The subsequent stock diagram failed
`revealed supplier diagram outline does not cover its source profile` after
revealing its saved-hidden `SupplierNominalStockProfile` and rebuilding. That
error did not emit the actual outline, transform or individual expected/actual
spans. It does not establish a different physical eye, and does not authorize
changing nominal source geometry, coverage bounds or the boundary allowance.
Source-profile configuration, projection and native outline must distinguish
the stock-stage root before changing its acceptance guard.

CH reached successful native reference assertions for EyeOD, EyeID, the
finished thread and all three stock references. In its first settled layout
check, the retained FINISHED-note owner/link/resolved-text/border checks and
front-view containment passed. The second real view then failed with:

```text
(0.2872237893868808, 0.15867221871562523,
 0.3327762106131192, 0.2673277812843747) m
```

The box midpoint matches the FINISHED isometric centre `(0.310, 0.213) m`.
Against the unchanged cell `(0.0127, 0.0651, 0.4191, 0.2667) m`, clearances are
left `274.5237893868808 mm`, right `86.3237893868808 mm` and bottom
`93.57221871562523 mm`; the top overflows by `0.6277812843747 mm`. A 1 mm
downward FINISHED-only translation is the smallest whole-millimetre correction:
predicted Y bounds become `(0.15767221871562523, 0.2663277812843747) m`, leaving
`0.3722187156253 mm` top clearance. The stock isometric position must remain
independent and unchanged. Neither this box calculation nor border containment
proves printed neighbour-ink clearance; the final whole-page native PDF and
machinist review must inspect the isometric label and nearby annotations.

The finished and stock isometric placements are now separate contracts:
`FINISHED_ISO_CENTER = (0.310, 0.212) m` and unchanged
`STOCK_ISO_CENTER = (0.310, 0.213) m`. Both callers use their own contract;
there is no shared alias that would inadvertently move the stock diagram.

Baseline-only neighbour evidence is retained in
`hook-contour-proof/ch-finished-iso-a06-bounded-placement-and-baseline-neighbor-ink.json`.
The released-v44 PDF's uncropped embedded isometric image (xref32, soft mask33)
has nonzero-alpha support at sheet Y `172.8152244464137..254.03166100315443 mm`.
The unchanged caption's original PDF font-span top is `164.43422453138564 mm`:
the baseline gap is `8.38099991502806 mm`, predicting `7.38099991502806 mm`
after moving only the pictorial down 1 mm. This uses every alpha byte greater
than zero, not a hand-picked crop or threshold search. Raster support and
font-span boxes are not exact analytic edges/glyph ink, and new supplier
annotations/current native rendering still require whole-page acceptance.

Neither drawing reached the final post-rebuild attachment observer or native
save. Neither exported a PDF, PNG, native drawing or layout audit; neither
uploaded a failure-artifact bundle. SM's successful initial physical-ID
attachment does not substitute for after-rebuild/save survival. CH's FINISHED
note success does not prove its later stock-note checks, nor SM note ownership.
No whole-v44 comparison or automated machinist qualification is available from
this attempt.

## Complete stock-stage readbacks at f598

Source `f598f3ea81757db61b2ad0924695a62efcfe2dda`, run
`20261023T012746154Z-6d1e30f802924759bc1b149490d9efb5`, build
`20261023T012837.633333Z-6e40c6b9e85241eebf7037a5910c8c9e`, again completed
with two part cache hits and two failed drawings. The immutable complete handoff
is `hook-contour-proof/iso-stockframe-f598f3ea8-native-handoff.json`; the
arithmetic and explicit inference limits are retained in
`hook-contour-proof/root-readback-f598f3ea8.json`.

### CH: a primary stock scale, not another translation

The 1 mm FINISHED-isometric correction passed the earlier native refusal. The
next settled layout refusal was the primary SUPPLIER-STOCK view at 5:1:

```text
native outline = (0.11266199801221032, 0.08855998560357987,
                  0.18733799988553204, 0.26046300056871236) m
unchanged cell = (0.0127, 0.094, 0.4191, 0.2577) m
```

Its height is `171.9030149651325 mm`; the cell height is `163.7 mm`. The
bottom and top overflow by `5.44001439642013 mm` and `2.76300056871236 mm`,
respectively. No translation can remove their combined `8.20301496513251 mm`
excess.

Main explicitly approved a STOCK-primary-only 4:1 presentation, a scale already
listed in the supplier-reference scale catalogue. The actual stock sheet scale
and title metadata must follow `STOCK_SCALE`; the FINISHED primary remains 5:1,
and both isometrics and the stock isometric caption remain 3:1. Original-source
configuration, dimension identities, values, supplier units, fractional
precision, text heights, dimension anchors and model cells are unchanged.

This approval is not permission to subtract guessed padding, shrink text or
proportionally scale the old outline as containment evidence. Complete native
outlines may include sheet-space padding. The changed-source 4:1 native view
must pass the original settled containment and annotation checks, and its
whole-page PDF must prove legibility and neighbouring ink clearance.

### SM: the view outline is not the source construction profile

The complete 6195-byte failure-only observation is
`hook1853-f598f3ea-iso-stock-terminal-raw-copy-0.json`, SHA-256
`b36047562d6888d4d990eb76b785581b67931b1b94c275bff5a830d6a81c45d4`.
There is one semantic observation, with no truncated segments or getter errors.
Its original guard operands were:

| Quantity | X span | Y span |
| --- | ---: | ---: |
| `IView.GetOutline()` | 46.354998579 mm | 92.976917890 mm |
| Existing exact source requirement | 82.225 mm | 152.4 mm |
| Recorded native segments through the recorded native transforms | 82.225 mm | 152.4 mm |

The exact view had configuration `SupplierNominalStock`, HLR mode 2,
`ScaleDecimal == 2`, `ScaleRatio == (2, 1)`, and `UseSheetScale == 0`.
Its actual model-to-view matrix had identity rotation, scale 2 and translation
`(0.15000000008840228, 0.1983109599263821, 0) m`. The referenced source path
matched; the view's source and the held source part compared equal natively.
The named stock configuration existed with ID 1.

The native profile was `SupplierNominalStockProfile`, with
`IsSuppressed2` in the named stock configuration returning `(False,)`.
All nine actual segments were construction geometry: three complete circles
and six lines. The actual model-to-sketch transform was identity. Analytic
projection of those recorded curves gives:

```text
(0.1325375000884023, 0.0633734599263821,
 0.21476250008840228, 0.21577345992638208) m
```

The old outline misses the projected profile by `41.585000799 mm` on the right
and `65.138081129 mm` at the bottom. Native scale and exact source curves rule
out a half-scale correction or a nominal-geometry replacement.

There is a directly relevant native positive control:
`draw_dt_vn_post_mount_screw.py` documents a27 PNG and vertex readbacks showing
correct source-profile ink while `GetOutline()` retained its pre-configuration
extent. The SDK promises a view bounding box, not complete construction-sketch
coverage. The current SM receipt proves the mismatch; it does **not** directly
prove which historical body produced that outline.

The bounded STOCK-only cutover reuses `_supplier_reference_geometry` rather
than adding a fallback. It captures actual native construction curves through
the source sketch inverse in the explicitly active stock configuration, binds
the immutable capture to the held source and exact stock view, and restores the
original configuration without saving. Zero solid/sheet bodies, an unsuppressed
error-free owner, exact native inventory and exact stock dimension values are
preconditions. Current-view projection measures complete line/circle ink, not
a nominal rectangle. Existing expected spans, lower tolerance, padding upper
bound, model cells, source binding, full uncropped/unbroken-view checks and
annotation-ink checks remain strict. FINISHED views retain their original
native-outline checks. Settled projection never reactivates a source
configuration or retains live geometry handles.

Two configuration caveats are explicit. First, the diagnostic read the nine
segments while the source was active in `Default`; that does not prove their
evaluated geometry in `SupplierNominalStock`. Production capture must close
that gap. Second, its four named-configuration `GetSystemValue3` BSTR-array
queries each returned `(0.0,)`. These are observed query results, not a status
code or proof of zero geometry. The SDK documents both scalar and array forms;
existing supplier readers document native binding trouble with name arrays
and use scalar BSTR names. The production path reuses that established scalar
reader and refuses zero or incorrect expected values. It does not declare
arrays universally invalid or accept a zero as a substitute.

Neither leaf reached the final after-rebuild or still-open after-native-save
attachment observers. No PDF, PNG, SLDDRW or layout audit was exported, and no
failure bundle was uploaded. The changed stock corrections, final native
attachment survival, whole-v44 comparison, automated machinist review and
exact-source independent review remain qualification requirements.

## New native boundaries after the stock-oracle cutover

Source `c12df92c2a2718d0e867f410d2dbc76905085655` contains freshly fetched main
`433d033d8434cb0cfe3fda040b27e5a008c585af`. Its final focused checks passed
560 tests, F821, 149 adapter methods and 103 native binding contracts; those
results are archived separately under `final-stock-root-c12df92c2a2718d0e867f410d2dbc76905085655/`.
They are offline evidence, not the native acceptance verdict.

Run `20261023T021846928Z-f1b1da44bf2a4ea4a07da47714f549df`, build
`20261023T021918.189559Z-ac44e80621b14177b94e95e6a50d1ed1`, failed both
drawing leaves. The complete atomic handoff is
`hook-contour-proof/final-stock-root-c12df92c2-native-handoff.json`, SHA-256
`48910ae7e7054a81889f6349e9a790acd07012e30ce4225b574a7692d032db94`.
The companion arithmetic and proof limits are
`hook-contour-proof/root-readback-c12df92c2.json`. Dependency farm success
does not mean new part COM execution: both drawing logs explicitly restore
their part cache and skip that part build.

CH passed the primary 4:1 stock-view check and then refused the stock
isometric's outline:

```text
(0.2872237893868808, 0.15756259535002917,
 0.3327762106131192, 0.2673277812843747) m
```

Its X midpoint is the isometric's `0.310 m`, not the primary's `0.150 m`.
OTEL names `SUPPLIER-STOCK 'Drawing View4'` in a display span; the failed
cell span itself does not identify the view or configuration. Associating
that refusal with the isometric therefore remains exact-source/order
correlation rather than a raw failed-view-name readback.

Against the unchanged cell `(0.0127, 0.094, 0.4191, 0.2577) m`, top overflow
is `9.6277812843747 mm`. Main approved the smallest whole-millimetre downward
translation, 10 mm, for **only the stock isometric and its own 3:1 caption
together**. Their centres/anchors become `(0.310, 0.203) m` and
`(0.275, 0.153) m`, preserving the relative offset `(-0.035, -0.050) m`.
The translated recorded box has clearances left `274.5237893868808 mm`,
right `86.3237893868808 mm`, bottom `53.5625953500292 mm` and top
`0.3722187156253 mm`. Nine millimetres would still overflow. This leaves
the primary 4:1 view, FINISHED views, source geometry, text, scales and cells
unchanged. Whole-page native neighbour-ink and caption acceptance is still
required; a translated box is not printed-ink proof.

SM passed its exact target-source stock capture and the final pre-save
checks, then failed `EyeID: settled supplier dimension disappeared` in the
`after_drawing_save` reference callback. Its current-view dimension map did
not contain the originally captured `IDimension.FullName` key. The packet
does not emit the old/current key pair or native annotation identity; it
does not establish deletion, a document-suffix rename, or attachment loss.
The SDK names do not promise SaveAs3 stability.

The approved next SM observation is a concise **failure-only** missing-key
receipt: exact pre-save and current names, drawing/view/source bindings,
native owners and comparison with the last strictly verified pre-save
`IAnnotation` when that handle remains available. It must preserve the
original exception and every attachment criterion; it is not a name alias,
scan rescue or successful repair. Neither this observation nor the callback
event alone proves a successful save: the shared artifact wrapper also
invokes its after callback when the wrapped operation fails.

All eight requested drawing exports were missing, and no same-attempt
failure bundle was uploaded. SM reached the save context but has no
qualified saved attachment or cold-reopen proof. No current PDF comparison,
automated machinist qualification or merge readiness follows from this run.

## Proved SM save-name boundary and strict current-key capture

Source `55fdad6508e7e2a29ec7e066dbb76cd87891244e` passed its once-final
588 focused tests, F821, 149 adapter methods and 109 native-binding contracts.
Run `20261023T030147610Z-159245d71cba4e8f829a36d80179c7e0`, build
`20261023T030215.410862Z-e331ab8d744b4976b98fc69d65da8895`, then failed
both normal drawing leaves at the still-open native-save observer. The
complete packet is `hook-contour-proof/stock-iso-keyreceipt-55fdad650-native-handoff.json`,
SHA-256 `74c28e70a1763849fd5826dfca7976c05bceaf048224218a8768b70fc96fb3bf`.
The single SM raw/semantic receipt is
`hook1853-55fdad650-saved-key-receipt-raw-copy-0.json`, 3389 bytes, SHA-256
`48d13123bbdc085e99e7331065a1ea8e356999c04835d941a6c5107b337eae53`.
Exact fields and proof limits are retained in
`hook-contour-proof/root-readback-55fdad650.json`.

SM's old key was `RD1@Drawing View1@Draw103.Drawing`. The original annotation
now reports `RD1@Drawing View1@sm-vn-boss-hook.Drawing`; its sole matching
entry among all five expected-view annotations has native original-annotation
`IsSame == 1`. Its owner is native drawing-view type 0 with owner-view
`IsSame == 1`. Current drawing, view and source each compare `IsSame == 1`
with their pre-save objects, and the referenced configuration remains exact
`Default`. The source path is unchanged. The drawing path changes from empty
to the actual worker output `cad/out/slddrw/sm-vn-boss-hook.SLDDRW`, while
the title changes from `Draw103 - FINISHED` to `sm-vn-boss-hook - FINISHED`.
Thus the missing dictionary entry is a frozen pre-save FullName across a
native SaveAs retitle, not deletion of this original annotation. This is
native identity evidence, not a promise that a parsed suffix is stable.

CH independently reaches `EyeOD: settled supplier dimension disappeared`
after native save. The former STOCK isometric/caption refusal is no longer
its failing boundary, but this attempt contains no detailed CH saved-key
identity receipt. SM's values do **not** establish CH's cause or survival.
CH must independently prove all current native identities and physical
geometry at runtime.

The permanent recipe-local cutover retains the original exact keys through
all pre-save checks. At the native-save boundary it finds each original
annotation only by a **unique native `IsSame == 1` in its exact expected
view**. Before reading the current FullName it requires the same native
drawing, view, source and annotation owner, exact source path/configuration,
drawing-view owner type 0, typed display-dimension correspondence and the
actual expected native output drawing path. Missing, duplicate, unrelated,
wrong-owner or unknown-identity objects refuse. It does not strip a suffix,
parse a replacement name, alias the old key or use radius/geometry as a
dimension-identity proxy.

Only those proven current exact keys feed the unchanged complete reference
verifier, including one live type-46 attachment, the finite exact physical
circle, source-part correspondence, authoritative Wire/torus, tolerance and
nominal-model contracts. PDF-save and pre-close observations require the
same captured keys to remain stable and recheck current native identities
and physical attachment. These observers do not refresh geometry, rebuild
or activate a source configuration. Native/PDF observers restore FINISHED UI
state; the pre-close observer instead preserves its exact entry sheet/title.
The temporary failure-only collector is superseded by this strict capture.

The shared callback still runs when an operation unwinds a failure, so a
callback alone never proves SaveAs success and cannot replace the primary
save error. All eight exports remain absent from this failed attempt, with
no uploaded failure assets. Still-open final attachment, actual complete
PDF ink, released-v44 comparison, automated machinist SHIP and independent
exact-source code review remain separate required gates. No cold-reopen
persistence claim follows. The current session's explicit review-route
substitution is recorded below; exhausted Claude routes are not retried.

## Independent post-export close failures at 9bb

Permanent identity-cutover source `9bb6e4e07570c57d243180f6841271e59fd3dde6`
passed 733 focused tests, F821, 149 adapter methods and 110 native-binding
contracts. The normal pair ran on the independently admitted C carrier as
`20261023T033934343Z-443b70489e2b4d6a8d0c544594ddd632`.
The complete original handoff is
`C:/ha-release-manager-20261023/runs/repair-fleet/hook1853-9bb6e4e0-saved-identity-native-handoff.json`,
SHA-256 `7e0f9a371ac02b4f0d1f7d32b96ce02571a0de86866081f1ca834e99903d057e`.
Its small D pointer is
`hook-contour-proof/final-saved-identity-9bb6e4e0-native-handoff.json`.
Both original drawing leaves failed; neither is a native success.

The independent worker errors are:

```text
drawing 'ch-vn-spring-hook - SUPPLIER-STOCK' did not close after export
drawing 'sm-vn-boss-hook - SUPPLIER-STOCK' did not close after export
```

Both logs reach PDF export and the two-sheet layout audit before this new
failure. The former EyeOD/EyeID missing-key error is not the current refusal.
This is control-flow evidence, **not printed per-annotation IsSame/current-key
measurements, a qualified final attachment, or a borrowed SM-to-CH proof**.
The original controller has none of the eight requested exports and the
original failure capture has no forensic files. Filesystem-only recovery
of already-exported worker files is separate after-terminal provenance;
recovery must not rewrite those original failed outcomes.

The shared finalizer reads an opaque native drawing title before emitting
`before_drawing_close`, then passes that captured value to its one `CloseDoc`
call. The owned observer previously restored FINISHED after inspecting both
sheets, including at that close boundary. The logs print the captured
SUPPLIER-STOCK title; they do not print the post-callback title or a native
document table. The title-change cause is therefore a source-ordering
inference until the corrected runtime contract succeeds, not an invented
raw readback.

The owned correction captures the entry `ISheet.GetName()` and opaque
`IModelDoc2.GetTitle()`, performs the same complete identity/key/physical
checks, and restores the **exact entry sheet in a finally boundary** before
normal return. Its current title must equal the original opaque title.
A failed restoration cannot replace an earlier verification error: both
are retained with the original primary. Native-save and PDF-save FINISHED
restoration semantics remain unchanged. There is no suffix parsing,
second close attempt, CloseAll, ignored closed-file check, or shared
finalizer change. Both getters are concrete no-argument native BSTR methods.

The actual aggregate audit reports are CH two gating findings
(`dim-line-through-own-text` 1, `extension-through-own-text` 1), and SM five
gating findings (`extension-through-own-text` 4, `view-edges-missing` 1)
plus one advisory `text-separation`. Missing edges are **not** waived for
the zero-body stock diagram. Aggregate categories do not identify offending
sheets, dimensions or coordinates. Retained full audit JSON and whole PDFs
must be inspected before selecting presentation repairs or dispatching
another production pair. No cleanup-only unchanged-paper rerun is used as
layout qualification.

## Recovered whole paper and actual presentation findings

Filesystem-only, exact-worker/source recovery retained the already-existing
PDF, PNG, SLDDRW and full audit JSON from each failed 9bb worker. These are
after-terminal recovered files, **not successful native leaves or an exact
native-save capture**. Their manifests, local hashes and original failure
boundary are retained separately:

- CH PDF SHA-256:
  `0752c51ce01993bf1d73b191b6e48fcf76fbb75fb9f7f04ccea6d40cffc3ef1e`.
- SM PDF SHA-256:
  `6b6bdebf89028735f8d469d5c0432921bb0c4b78ddcec5f61c90cf94c12a3427`.
- Complete paper proof:
  `C:/ha-release-manager-20261023/runs/repair-fleet/hook1853-9bb-paper-proof/`.

The whole released-v44 comparison covers both changed FINISHED pages and
both added stock pages. All four overlays were inspected. Standard automated
`gpt-6-astra` medium machinist review ran three independent runs per part,
then both judges, without retries or quota substitution. Both aggregate
verdicts are **FIX**, with their gating clarity findings unanimous 3/3:

- CH's upper angular leader/arc crosses the `45°` numerals.
- SM's complete `NOMINAL EYE ENVELOPE` callout crosses the stock eye rings.

These are actual paper defects, not native contour-identity failures.
Unchanged v44 tolerance/catalogue wording is retained despite two nongating
one-of-three SM suggestions. The raw runs, judges, aggregates, command and
exit-1 execution receipt remain under `machinist-review/`. New changed paper
requires a new review; an unchanged FIX is never rerolled.

### CH angular text shelf

The angular dimension keeps its existing native arc anchor `(124,117)mm`.
Only its text uses the existing supported angular `OffsetText` mechanism
at `(137,117)mm`, with native position/mode readback and strict refusal.
The observed annotation plane is finite Z=0.0005m; this existing annotation
position contract checks XY, not an invented Z=0 plane. Physical eye-circle
centre/normal tolerances are separate and unchanged.

The whole recorded witnesses, arcs and arrowhead polygons have maximum
X=129.3085mm. At the new text shelf the actual glyph left edge is
133.5972mm. Conservatively allowing half the widest recorded0.35mm ink
stroke gives a4.1137mm gap, exceeding the3.5mm native text height.
The smaller proposal with only0.0972mm paint clearance was rejected.
The actual `652d25a02` paper subsequently passes whole-page inspection,
native audit and three independent automated machinist runs, as recorded below.

### SM complete diameter callout and stock ink

`IDisplayDimension.OffsetText` is explicitly unavailable for radial and
diametric dimensions because they already have a leader. It is not tried.
The existing primary `curate_model_dimensions` / `IAnnotation.SetPosition`
placement instead moves the complete nominal EyeOD annotation to
`(200,250)mm`; the exact native circle, dimension value, configuration,
source binding, tolerance and physical attachment criteria do not change.

The initially proposed `(200,244)mm` was rejected before native dispatch:
the actual adjacent wire-section circle occupies
`[205.237494,228.974999]..[214.762494,238.499999]mm`, and the proposed label
would cross it. At `(200,250)mm`, the predicted complete-label left edge
172.2674mm clears the eye ring by4.8049mm and its bottom242.6449mm clears
the wire circle by4.1449mm. The conservative highest native fraction text
extent is256.3294mm, below the unchanged257.7mm stock-cell top by1.3706mm.
These calculations bound the source placement, not a final native/PDF
claim; the complete leader route, all fraction text and every neighbor
must still be inspected. The nominal shank text moves down1mm to159mm,
without changing its geometry or value.

The actual recovered stock profile has412 dashed PDF pieces in
RGB(128,128,128), width0.129998609mm. The existing audit's ink input excludes
nonblack strokes, explaining why this valid source-projected profile is
absent from that coverage operand. Zero bodies and a projection oracle
alone do **not** prove printed ink coverage.

The recipe reuses the existing native mapped-sketch selection pattern to
make exactly the nine drawing-view instances black: three complete circles
and six lines belonging to the authoritative stock sketch. Each selection
must be the exact mapped native entity, one expected external-sketch
selection, with unchanged finite source geometry and construction state.
`IDrawingDoc.SetLineColor(0)` is void; native Color0 is read back, and native
width/style/layer remain unchanged. No source-part style, construction,
geometry, configuration or save is changed. Missing, duplicate, foreign,
wrong-type, wrong-identity or changed-geometry instances refuse. Native
circle-selection proof and actual final black coverage of all nine curves
remain mandatory; no unsupported segment type or missing-edge waiver is
accepted.

Four SM raw `extension-through-own-text` findings are the fraction bars
themselves: native horizontal6.1979mm segments between the actual numerator
and denominator rows. Independent black PDF segments match their native
endpoints within0.000048mm. The raw findings are retained. There is no
decimalization, suppression or unauthorized shared-classifier change.
This report-mode classification does not excuse a real profile-coverage
or presentation failure.

## Actual `652d25a02` normal native and paper outcomes

The complete source-bound normal run
`20261023T045810374Z-da4e1e246e0b4642a9578f421ab04d2d` has one success and
one failure. Its immutable source is
`652d25a02e2d0ae87102128690505d64e457fb2f`, admitted against
`6ec6814301593b85853db9786e7d33c69ec44ac8`. The canonical complete handoff is
`C:/ha-release-manager-20261023/runs/repair-fleet/hook1853-652d25a02-final-paper-close-native-handoff.json`.
Neither a later main merge nor a source-only closure relabels this native
execution as proof from a newer source or runtime.

### CH: successful native output and two-sheet SHIP

CH completed the normal native save, PDF/export and close path. All four
actual exports are present. The complete native layout audit reports two
sheets, zero gating findings, no findings and empty read errors. The PDF is
453,694 bytes, SHA-256
`76a7756127f5ef9ae8cfbd9eeb10a68297c4acbec2e711387fe76c6a57d22930`.
This includes the strict settled, after-save and after-PDF observations in
the still-open drawing; it is not a cold reopen persistence experiment.

The whole released-v44 comparison has one changed FINISHED page and one
added SUPPLIER-STOCK page, with no removed pages or drawings. Both complete
overlays and the actual two-sheet paper were inspected. The actual CH
automated `gpt-6-astra` medium machinist review ran once, three independent
blind runs with zero retries: **SHIP / SHIP / SHIP**, zero findings. All runs
reviewed both sheets and the exact PDF hash above. They apply existing
owner exception RV-01, not a new waiver. The configured judge correctly
skipped execution because all valid runs returned zero findings; no raw
judge output is claimed.

The separate paper evidence root is
`C:/ha-release-manager-20261023/runs/repair-fleet/hook1853-652d-paper-proof/ch-actual/`.
It contains the hashbound four actual exports, full native audit,
`qualification.json`, raw reviewer attempts and reports, exact command and
execution receipt, both whole-page overlays and
`v44-to-652d-whole-ch-diff.zip`. Aggregate SHA-256 is
`cdbfe160b2b649f452255b73482c0b35cd66626e32644c86a1e5fa245ffbe082`;
whole-diff ZIP SHA-256 is
`6eae0934b95f5f3633e7e22daa861adaba33133458548988cc0626b5f02f865a`.

### SM: new pre-save selection-identity refusal, not qualified output

SM fails at `_blacken_supplier_stock_profile` before native save or export:
`supplier nominal stock black profile: selection is not the exact mapped native curve`.
The actual raw receipt is
`hook1853-652d25a02-terminal-sm_vn_boss_hook-worker-task.log`, lines47–78,
SHA-256
`9e42b6eb12b37cc7d6ba8fa67a4d1d179726dc716a28078f47b7e44d82916c0d`,
under the same farm evidence root. All four SM controller exports are
absent. This is not the historical `9bb6e4e` close failure and there is no
actual final black-profile or SM paper qualification.

The reached guard proves that the nine source/mapped native curve and
distinctness guards, active/select-data view identity, successful
`Select4`, and strict one type24 selection passed. The current message
still conflates a null selection-manager return with exact native
`IsSame(selected,mapped)==0`. Integer2/3 or a noninteger equality result
would raise the different existing `unknown native IsSame` refusal.
Neither the selected object nor its source/drawing context is proved by
this message. The SDK also does not guarantee positive equality support
for every sketch/context combination.

One bounded, failure-only receipt is authorized at this original refusal
to distinguish those missing primitives. It reports the already acquired
nine native source/mapped identities, selected-null status first, raw
identity and owner/view controls, and exact source/configuration context.
It does not change the original selection, acceptance, exception,
geometry, style, configuration or save path. Per-field reporting failures
must not mask the original exception. This diagnostic is not a repair or
qualified output; wrong, missing, duplicate or unrelated native contours
remain refused.

## Current session review route

The latest explicit user instruction replaces the unavailable Claude code
gate for this session with an **independent `codex-gpt-6-1-sol-xhigh`
subagent running `e-code-review XHIGH`**: ten inline review angles,
deduplication and a gap sweep against the exact frozen base/head and all
five owned files. Same-family review is explicitly permitted. No paid
remote reviewer, repeated Claude route probe or quota waiting is used.
The bounded diagnostic delta at `1f5e25353d42716ede2406d49311f037c5c75d17`
completed that XHIGH method. Its console-visibility P2 was fixed, with zero
new findings in the static correction. That is not final whole-PR approval.
Focused source checks, native outputs or explicitly bounded historical carry,
complete changed-paper v44 comparison, actual-XHIGH machinist SHIP and the
independent exact-source code review remain distinct gates.

## Actual-XHIGH configuration correction

The latest session instruction requires actual Codex XHIGH for final
machinist qualification. The three old CH authoritative provider receipts
all say `gpt-6-astra`, `effort=medium`. Their raw SHIP verdicts remain
unchanged historical diagnostics, not qualification under the new rule.
The older `9bb6e4e` FIX reports likewise remain historical; no obsolete SM
paper was rerolled.

One **CONFIGCORRECTION** invocation reviewed the unchanged final CH PDF,
not a new native build or a favorable-vote reroll. Current-source `1f5`
ran the standard reviewer with both reviewer and judge explicitly set to
Codex `gpt-6-astra` XHIGH, three independent blind runs, three jobs and
zero retries. Every authoritative `rollout.jsonl` proves actual
`turn_context.model=gpt-6-astra`, `turn_context.effort=xhigh`, OpenAI
provider and CLI0.159.1. Each run made one successful attempt, inspected
both sheets and reported no context errors. The actual verdicts are
**SHIP / SHIP / SHIP**, zero findings and zero gating. The configured
XHIGH judge correctly skipped because valid runs had zero findings;
there is no actual judge invocation or runtime-effort receipt to claim.
Existing RV-01 is the only exception, unchanged.

All frozen package and sheet-tool PDFs match `76a775…` above. All three
effective prompts recompute to
`fad77cb481fcca4591333face01eb18b4be6e0ab7ffddd136085bc975717458a`.
The completed qualification and 34 hash-bound raw artifacts are under
`C:/temp/ha-hook-contour-identity-evidence-20261023/machinist-xhigh-config-correction/`.
Corrected aggregate SHA-256:
`58237185cddd96048b0aae412d5dbd3740930748ab6883517640e391e777e3d6`.
Artifact-manifest SHA-256:
`1331e695f15b1d53dc7eb15e35d57deb1fd09207a1d0d847a50dae3f4e6cb522`.
The existing full v44 comparison stays bound to the same exact PDF.
These facts do not make the native source newer than `652d`, prove a cold
reopen, or qualify an unavailable final SM paper.

## Actual canonical native-name intake

PR1869 actually merged at `2026-10-23T11:37:32Z` as
`c23dab7689507549eb76b6aa2783d083d9cd6c62`, with exact canonical head
`000a8a06d7224efc2462e3dfb7c02853eb7e4662`. Its native qualification was
the separately identified composite
`31fbaa1042b30fe56d81960faacf4f2693a4dfbc`; it was not standalone `000a`
or a new Hook execution. The Hook branch integrates actual merged main,
not that qualification composite or an unmerged follow-on PR.

The canonical read-only machining-control verifier normalizes the incoming
`IAnnotation` before calling `GetSpecificAnnotation`, binds the resulting
display dimension, and reads `Name` from the same modern
`GetDimension2(0)` native dimension used for state, value and tolerance.
Name must be an exact nonempty string in the unconsumed expected inventory.
Empty, non-string, unknown, extra, duplicate and missing controls refuse.
Driving state, prefix, nominal, tolerance type/min/max and printed precision
checks remain load-bearing; the existing `math.isclose` relative tolerance
is unchanged, not newly converted to absolute-only comparison.
No geometry/state writes, selections, rebuilds, configuration activations
or saves occur in this verifier.

Both Hook wrappers and all four production wrapper invocations now use
the annotations-only API. The additional owned machining-control fixtures
read `Name` from their same captured native object and no longer patch the
obsolete trim-helper name adapter. Supplier-eye reference fakes are not
invented machining controls. Angular placement's separate name readers
remain intact. Merge resolution retains the owned physical contour,
pre-save refresh, linked-note, saved-key, paper-placement and exact
pre-close entry-sheet/title restoration paths.

Exact Git-object comparison of the thirteen read-only helper files from
native `652d` to actual main `c23` finds ten unchanged files and three
changed files: `_supplier_dimensions.py`,
`_purchased_fastener_drawing.py`, and `_stock_trim_drawing.py`.
Only the last is newly changed since `1f5`. The earlier reached supplier
presentation reporting refactor and unused purchased-builder branches
retain their disclosed boundaries; the new canonical binding/native-name
path is a real reached identity change, not mere argument cleanup.
This is not all-thirteen byte equality, unchanged execution/cache identity
or new current-main native success.

The separate fifteen-input machinist rubric/harness/exception/locked-runtime
Git-object matrix is unchanged from actual review source `1f5` to `c23`.
The complete context and thirteen-helper matrices are retained under
`C:/temp/ha-hook-contour-identity-evidence-20261023/canonical-1869-intake/`.
Main/coordinator explicitly retain the historical all-page CH native and
actual-XHIGH paper proof within these source-impact boundaries.

The one approved changed-source SM diagnostic has now run at `bc799e0b`
and still failed before save or export; the complete actual readbacks and
their corrected native-enum interpretation are recorded below.
Canonical intake and diagnosis are not a root fix, successful output or
permission for an unchanged native retry. Dispatch remains coordinator-only.
No additional CH execution is claimed.

## Actual `bc799e0b` SM selection and source-frame readback

Source `bc799e0b9b9dffed68d79315d420f24740dd64ea` ran as
`20261023T120921149Z-f7085ef295974ef7a481d3a87509276b`, actual build
`20261023T120956.462236Z-73c61a14450245059d805ec614c86dad`.
The part leaf succeeded; the drawing failed on worker `swmaker00000f@15`,
attempt `20261023T121327Z-1-edd1d47c`, at the unchanged
`selection is not the exact mapped native curve` guard.
All four drawing exports are missing and the original worker explicitly
reports no forensic artifacts. This is not final native or paper proof.

The full original task log is
`C:/ha-release-manager-20261023/runs/repair-fleet/hook1853-bc799e0b-SM-original-worker-task.log`,
90,897 bytes, SHA-256
`c73f89611e089acc9d87277a3aab2f2b3e23aedcd2708bb07846a72059e9839e`.
The adjacent
`hook1853-bc799e0b-SM-original-diagnostic-all-typed-identity-records.json`
preserves ten complete records: one context and nine source rows, not ten
curves. Every field retains its original value, Python type and error.
Collection reports two terminal leaf results and zero collection errors.

At index zero, `Select4` returned true, selection count was exactly one,
type was 24, and the selected object was not null. Raw and typed selected
wrappers compare SAME=1 in both directions and self-controls are 1.
Stock, active, select-data and selected-object views all compare SAME=1
to the expected view; their referenced document is the exact source and
configuration is `SupplierNominalStock`. All nine selected-to-source and
selected-to-mapped comparisons, in both directions, are integer 0.
The matching first-circle geometry and `(kind, GetID)` are not native
identity or an accepting substitute.

### Native equality correction, not a blind code change

An early owner/scout report incorrectly labelled 0 UNKNOWN and 2 DIFFERENT.
That interpretation is withdrawn, including corresponding labels in
historical diagnostic handoff keys; original numeric records are untouched.
Static `PEReader`/`MetadataReader` inspection of the installed
`SolidWorks.Interop.swconst.dll` constant table establishes
`swObjectNotSame=0`, `swObjectSame=1`, `swObjectUnsupported=2`, all Int32.
The assembly is version `33.3.0.92`, SHA-256
`f6863a54a193ea1700a66341bf4f2bc3c2308702ded7a2f83763b576d20b928b`.
This was file-metadata inspection, with no assembly loading, COM activation
or SOLIDWORKS execution; it is not an inspection of a new farm assembly.
The indexed official SOLIDWORKS 2026 enum agrees. Exact local metadata and
the reader are retained in
`C:/temp/ha-hook-contour-identity-evidence-20261023/canonical-1869-intake/installed-object-equality-static-metadata.json`.
The existing recipe helpers correctly accept only integer 0/1 and reject
unsupported 2 and noninteger results. No 0-to-2 distinctness rewrite is made.

Thus the nine selected/mapped comparisons prove NOT SAME, not UNKNOWN.
The active source is `Default`, ID 0, while the captured and view source
configuration is `SupplierNominalStock`, ID 1. Configuration `IsSame`
returned UNSUPPORTED=2 in both directions; the names and IDs independently
differ, but neither observation establishes configuration causality.
No source configuration mutation is introduced into read-only guards.

### Required source-part normalization

The provisional diagnostic called `GetCorresponding2` on the **drawing**
extension. Its null owner returns did not exercise the documented inverse
on the underlying **source-part** extension. The downloaded
`Get_Corresponding_Entities_Between_Parts_and_Views_Example_VB.md`,
`ViewToPart` non-topological branch, explicitly uses
`swModelPart.Extension.GetCorresponding2(inputObject)`.
`IView.GetCorresponding` explicitly supports sketch and sketch-segment
objects and names `IModelDocExtension.GetCorresponding2` as its inverse.

The strict repair uses that source-part receiver as the primary identity
frame for both drawing segments and their owning sketches. Mapped and
selected segments must each positively compare SAME=1 to the exact
authoritative source segment, and both canonical owners must compare
SAME=1 to the exact source feature's sketch. Null, foreign, unsupported or
failed correspondence refuses; there is no GetID, geometry, name or radius
fallback. Fresh post-rebuild inventory, unique identities, six lines,
three circles, construction state, geometry, Width/Style/Layer and all
nine black colors remain required. This documented design is not an
assertion that the unexecuted native bridge already works.

### Finite new-main source boundary

One actual fetch, retained as `artifact://5783`, observed main
`1c4d8a0328bf3b85319e1da2b578e5f716f5b998` after `c23`.
Its exact argv, C-only working directory, exit zero and uncaptured
wall-clock boundary are retained in
`C:/temp/ha-hook-contour-identity-evidence-20261023/strict-source-normalization-admission-pin.json`.
The fetch was not replayed to invent timestamps. Main/coordinator adopt
that observed commit as the finite new SM transaction pin, not a moving
main chase. It was integrated by a non-rewriting, conflict-free merge.

The complete immutable thirteen-file `c23` to `1c4` manifest is retained
at `artifact://5790:275-430`. None of Hook's five owned files, thirteen
inventoried helpers or fifteen machinist context/harness inputs changes.
New physical-axial, serialized-note and measured-text-shelf modules are
used by PD pivot and SM knife-stud recipes, not by these Hook callers.
The existing frozen-`652d` three-helper semantic limits still apply;
this increment does not turn them into thirteen byte-identical helpers.
Main accepts existing CH native/still-open, whole-v44 and **actual-XHIGH**
three-SHIP paper evidence under this unchanged-input carry. Historical
MEDIUM reviews stay nonqualifying; no CH native or paper rerun is made.

## Evidence boundary

The focused offline tests replay observed native circle parameters, invalidate
pre-rebuild handles and exercise wrong circle, owner, view, configuration,
attachment count/type and missing/extra attachment refusals. Their COM-shaped
objects are test doubles, not native evidence. Native farm outputs, complete v44
sheet comparisons and automated machinist reports remain separate qualification
evidence tied to the producing source and PDF hashes.
