---
name: flexible-subassemblies
description: How to make a subassembly flexible at the top level (Phase E gate — it WORKS)
metadata:
  node_type: memory
  type: reference
  originSessionId: ba03bcc4-d81e-4e71-bbc7-7926c9a87d29
---

Phase E gate RESOLVED 2026-06-13: subassemblies CAN be made flexible so a
top-level cam coupling / crank motor drives parts INSIDE them. Probe
`cad/scripts/probe_flexibility.py` proves both drive-train + channel go
`Solving 0 (rigid) -> 1 (flexible)`.

The working recipe (the adapter has NO flexible-sub method — inline it):
```python
from solidworks_mcp.adapters.solidworks.assembly import _select_component
asm = adapter.currentModel
_select_component(adapter, bare_comp_name, 0, False)   # preselect the sub
asm.CompConfigProperties5(2, 1, True, False, "", False, False)  # Suppression=FullyResolved=2, Solving=Flexible=1
# read back: int(component.Solving) == 1
```

TWO bugs caused earlier false negatives (both burned a full probe each):
1. `SelectByID2(..., None, 0)` — bare `None` for the Callout is a documented
   failure mode; pass `null_callout()` (a typed-null dispatch). The adapter's
   `_select_component` (assembly.py:397) already does this, so just call it.
2. `swComponentFullyResolved` is **2**, not 3 (3 = swComponentResolved). An
   invalid suppression state makes CompConfigProperties5 return False.

A fixed sub CANNOT be flexible — leave the sub free (don't fix_component it)
before flipping. Cost: ~270s per probe (inserts + ForceRebuild3 dominate).
See [[harmonic-analyzer-project]] and [[amplification-wires]].
