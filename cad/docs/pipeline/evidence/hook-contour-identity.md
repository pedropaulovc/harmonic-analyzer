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
- a native analytic circle at the model origin (centre coordinates within
  1e-8 m), normal Z within 1e-8 of ±1, and diameter within 1e-5 mm of the
  corresponding physical eye size;
- the expected native drawing view and a matching **current physical owning
  face**, reacquired from that configuration-bound view.

Do not compare a post-rebuild annotation with a silhouette handle retained from
before the settling rebuild. The 2026-10-22 native diagnostic at source
`2942dd0651b13be2ad64af9568f8323f2f3bd551` read one EyeOD attachment of type 46;
its captured and attached CircleParams were identical:

```text
(-2.102257677834285e-10, -7.358970724458125e-11, 0,
 0, 0, 1, 0.006350000187332174)
```

The failing clause was the old physical-owner comparison, not attachment count,
type or measured circle. That diagnostic did not separately record a missing
face versus a not-same native face; identical circle parameters alone are not
owner-identity proof. The repair therefore retains the native face comparison
but reacquires its reference from the current view instead of accepting radius
alone.

The same native enumeration returned two ID entries with identical circle
parameters. Enumerator entries are not annotation attachments: multiple visible
entries must not disable the exactly-one-attachment guard. Wrong diameter,
foreign owner, missing contour and additional annotation attachments are refused.

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

The recipe changes the view configuration and HLR mode before discovery.
`IView.UpdateViewDisplayGeometry` explicitly makes such changes available before
Windows repaints; without it the native API need not expose the changed view
geometry while the recipe retains COM control. Materialize the finished front
view once **before** enumerating supplier contours, then apply the unchanged
strict physical-ID predicate. Do not retry against a different type, diameter,
view or configuration if that query still finds no ID.

The final and still-open post-native-save checks retain type 46 and exactly one
live attachment, and compare its exact ID circle and current native owning face
against fresh geometry from the configuration-bound view. As for CH, refreshes
belong to the existing pre-save layout check, not the post-save observer, and
successful save/leaf evidence is required before claiming post-save proof.

## Evidence boundary

The focused offline tests replay observed native circle parameters, invalidate
pre-rebuild handles and exercise wrong circle, owner, view, configuration,
attachment count/type and missing/extra attachment refusals. Their COM-shaped
objects are test doubles, not native evidence. Native farm outputs, complete v44
sheet comparisons and automated machinist reports remain separate qualification
evidence tied to the producing source and PDF hashes.
