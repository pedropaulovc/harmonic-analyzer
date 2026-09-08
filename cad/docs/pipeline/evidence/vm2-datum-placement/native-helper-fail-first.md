# Native datum helper: fail-first regression run

Run against unchanged production `_drawing_common.py` at correction head
`a371f49448b9c7fb300b77152c59cb2874889657`. The proposed native mode remains
unapplied pending VM1 coordination. All native objects, COM bindings and
selection operations in this test are doubles; no SolidWorks connection occurs.

```powershell
uv run --frozen python -m pytest cad/scripts/test_vm2_native_datum_placement.py -q --tb=short --junitxml=cad/out/reports/datum-placement/native-helper-fail-first.xml
uv run --frozen ruff check cad/scripts/test_vm2_native_datum_placement.py
```

Result: **98 tests, 95 failed, 3 passed, zero errors or skips**. Pytest exit code
1; console duration 3.30 s (JUnit duration 3.283 s). Ruff passed. Every failure
has the same expected baseline cause:
`TypeError: add_datum_feature() got an unexpected keyword argument 'placement'`.

The three passing requested-mode tests prove that both published original datum
readback failures still reject at their unchanged 20 um and 100 um limits, and
ordinary requested placement still succeeds. Those tests verify the original raw
receipt SHA-256 before using its exact recorded readbacks.

Native cases cover geometry/axis/radius/topology, selector conflicts, selection
identity, attachment count/type/identity, dangling state, initial and post-rebuild
label/position readbacks, shoulder persistence, rejected insert/label/callout/
rebuild, and below/exact/above/diagonal displacement boundaries at both unchanged
limits. Successful native cases require zero `SetPosition2` calls.

This red run proves the tests distinguish the baseline from the requested
interface. It does not prove the proposed implementation passes; rerun these
unchanged behavioral assertions after the approved implementation lands.

SHA-256 witnesses:

- Production helper: `d64281f8509c8d1a270c22eb35871bcf5846585c9f8b9c8389d11182c7eece9d`
- Test file: `13d18e63f33323343f80c9f60850f5ca0ebe9e5ee269d92684ea68a97e7f7f2b`
- Raw JUnit report at `cad/out/reports/datum-placement/native-helper-fail-first.xml`:
  `0653459ee0207e170a344c0bb6dcefcf72991b4b755fcfcf1f49cc5e10c20423`

The complete individual failures are published in
[the original JUnit report](probes/native-helper-fail-first.xml). The exact
[test source](probes/native-helper-regressions.py.txt) is also retained without
enrolling the unimplemented native mode in the production test suite. Copy it to
the command's named test path to reproduce this baseline red run.
