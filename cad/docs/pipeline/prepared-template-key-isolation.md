# Prepared-template setup key isolation

This is a module-boundary change based on `bb56cd28`, not new native acceptance
or a measured fleet speedup. Prepared cold/reopen/render and the final full-build
gate remain required after integration.

## Reproduced invalidation

The retained production manifest at
`cad/out/prepared-drawing-templates/ad3b6bf9cd3fffd8f2d69c251e1dba186dc9b304f5a0584debc4f7ad7ed978d8/manifest.json`
and the isolated manifest at
`cad/out/reports/datum-policy-zkq8ce0i/fulcrum_shaft/cache/49a46ee9471b3e76be4c1e52bf1b400d476a5f2da4a978ae586fb66ec5e830f0/manifest.json`
have identical inputs except `_drawing_common.py` bytes. Their respective manifest
SHA-256 values are
`903689427ebbff610ac8de55bd5bb6adc13b68b6a7e1864258b96546ff66b78e`
and `85d6cdc99cb9c283dbe63f38b153a3aeb20019891316aea4947d38ebc6ae7e80`.

The sole common-helper change between the corresponding `d6ad5aad` and `a96cb782`
states is the empty `set_dimension_callouts` early return. Replaying the complete
manifest inputs reproduces both keys. Substituting just that helper digest also
changes keys for all 15 registered template specs. The isolated cache directory
itself is not a key input; its fresh-directory MISS is not proof of a production
cache miss.

## Boundary and unchanged behavior

`_drawing_sheet_setup.py` now owns exactly four existing functions and their setup
constants:

- `new_project_drawing`
- `_pin_dimension_text_and_leader_style`
- `_normalize_metric_edge_break_note`
- `assert_asme_b_sheet`

Their parsed function bodies, signatures and decorators equal the pre-extraction
versions. Native call order, arguments, readbacks, validation and telemetry remain
unchanged. True callers and mock targets import the new module; there is no
compatibility wrapper or function-level hashing scheme.

The prepared key still hashes complete modules. Its local source closure drops
`_drawing_common`, `_drawing_layout_check`, `_gtol_spec`, `_part_pmi` and
`_surface_finish`, adds `_drawing_sheet_setup`, and contains these ten modules:

```text
_common                       _drawing_prepared_template
_config                       _drawing_registry
_drawing_annotation_bounds    _drawing_sheet_setup
_drawing_native_display_data  _drawing_template_defaults
_drawing_template_viewport    _drawing_view_packing
```

All adapter Python sources, configuration YAML, project/lock files, exact original
template hash, scale/precision, Python identity and native revision remain inputs.
Those conservative dependencies are not narrowed here.

The source-closure comparison against `bb56cd28` leaves all 108 part and eight
assembly closures unchanged. Each of the 92 drawing closures adds only the new
setup module. This extraction changes drawing recipe bytes and prepared keys once;
it does not promise reuse of pre-extraction cache entries.

## Repeatable checks

From the project venv, without a native session:

```powershell
uv run python -m pytest cad/scripts/test_template_preparation_dependencies_drawing.py cad/scripts/test_drawing_sheet_setup_drawing.py cad/scripts/test_prepared_template_drawing.py cad/scripts/test_part_isolation.py cad/scripts/test_buildgraph.py -q
```

The fail-first key test reproduced unrelated callout invalidation before the
extraction. It now substitutes one source-byte digest without changing files and
checks all 15 real registered specs: unrelated callout bytes leave keys unchanged;
setup bytes change every key. Separate cases retain template, validator, bounds,
viewport, config, adapter, lockfile and scale/precision coverage. The native-method
doubles pin the existing setup sequence and fail on rejected or inconsistent
note/style/scale/size readbacks. They do not establish native execution.

The extraction's focused and adjacent run passed 1,108 tests in 39.42 s, including
the changed diagnostic/factory tests, buildgraph and part-isolation tests. Receipt:
`cad/out/reports/pytest-telemetry/run-zzj63tct`. Unused/undefined-name lint and
`git diff --check` also passed. No COM calls or managed native outputs were changed
by this task.
