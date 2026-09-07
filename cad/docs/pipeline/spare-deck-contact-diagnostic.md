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
or change application settings. It rechecks native instances and document state,
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
was added. All 32 tests then passed. **Native contact acceptance is still pending.**
