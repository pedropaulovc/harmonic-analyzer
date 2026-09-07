# Saved spare/deck contact readback

`cad/scripts/diagnostics/probe_spare_deck_contact.py` reads the saved complete
top assembly in its own checkout. It requires an empty document inventory,
an explicit running SW PID and the exact SHA-256 of the top assembly. The parent
holds the machine-global seat; it neither preflights nor restarts SW.

```powershell
$env:HARMONIC_SW_AUTOSTART = '0'
$env:HARMONIC_REMOTE_CACHE_MODE = 'off'
$env:HARMONIC_DIAGNOSTIC_SW_PID = '<verified running SW PID>'
$topHash = (Get-FileHash cad/out/sldasm/harmonic-analyzer.SLDASM -Algorithm SHA256).Hash.ToLowerInvariant()
uv run python cad/scripts/diagnostics/probe_spare_deck_contact.py --top-sha256 $topHash
```

The report identifies the exact frame/paper-drive instances, the T18 referenced
configuration, the configured component bodies and native transforms. It checks
the spare's underside and base's deck are coplanar with opposing normals, then
checks an actual point on both trimmed faces. This is one contact witness, not
a claim that every point of the spare is supported or that the whole model is
interference-free. The full assembly gate and fresh side/oblique renders remain
separate requirements.

The probe does not save, rebuild, change configurations, make selections, export,
or change application preferences. The dependency query can change SW's working
directory according to the API documentation; the owner records and restores
that directory before opening anything. It rechecks native instances and document state,
closes its owned documents, and compares all saved dependency hashes. Its report
retains primary, cleanup, input-hash and checkpoint failures together.

## API premises and verification boundary

The offline SolidWorks 2026 bundle documents `IComponent2.GetBodies3` as configured
component geometry, unlike `GetModelDoc2`'s last-saved model configuration. The
generated pywin32 wrapper returns the body retval followed by out `BodiesInfo`.
`IEntity.GetComponent` requires assembly-context entities; the first native run
must verify that the faces returned here retain that context. It must also
verify the expected component-local plane coordinates. A rejected call is a
diagnostic result, not evidence that these APIs are unavailable.

Other consulted bundled methods: `IComponent2.Transform2`, `GetParent`,
`IFace2.FaceInSurfaceSense`, `GetClosestPointOn`, and `ISurface.PlaneParams`.
The closest-point query uses the trimmed face rather than its infinite surface.

Offline tests cover gap/penetration, disjoint trimmed faces, wrong configuration,
parent/face ownership, replaced instances, malformed native returns and error
preservation. The three checkpoint-error tests failed before error aggregation
was added. All 32 tests then passed. Inventory and dependency-query regressions
bring the current focused suite to 40 passing tests.

## Cold dependency-query correction

The first native attempt on September 7 at `b474b553` stopped before opening
the model: `spare-deck-contact-er843xec/contact.json` records the ownership
rejection. `GetDocumentDependencies2(..., Searchflag=False, ...)` returned
29 local paths and 84 paths from the producing checkout. The documented
`Searchflag=True` positive control returned all 113 paths in this checkout,
with no open documents and no observed working-directory change. The owner
now uses that native search result, still rejects any resolved foreign path,
and preserves query and directory-restoration failures together. It never
rewrites a dependency path by filename or edits the saved assemblies.

## Accepted native contact

At `dad339f028b1138460a4921aa48ae5b2eaaf9e68`, the committed command above
passed in 92.472299 seconds on SW revision 34.3.0, PID 42080. The receipt is
`cad/out/reports/spare-deck-contact-87y4um_o/contact.json` in the spare-seating
checkout. Its exact top input is
`bc94ae616f6a1d196db3213bf9a4021c1e09ecc0c2345b324b4d5b81b7b42355`.

The configured T18 body had 77 faces and the base had 232. Each returned exactly
one matching support plane, with native component ownership and local coordinates
verified. The measured plane separation and trimmed-face point distance were
both 0.0 m. Both points were `(0.15400000006200001, 0.0508, -0.075)` m in the
complete top's frame. Before/after document states matched, all 114 input hashes
were unchanged, and the observed final document inventory was empty.

The review's possible coplanar-face ambiguity did not occur in this model.
The selector still rejects ambiguity; no split-face fallback was added.
