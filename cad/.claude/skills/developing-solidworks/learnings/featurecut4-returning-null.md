---
title: FeatureCut4 Returning Null
category: Feature Operations
tags: [FeatureCut4, IFeatureManager, cuts, direction, debugging]
severity: critical
date: 2025-11-23
---

# FeatureCut4 Returning Null

## Problem
When translating eccentric cam KCL code to SolidWorks C#, the `FeatureCut4` method consistently returned null, causing the cut operation to fail with the error:
```
ERROR: Failed to create shaft hole cut
```

## What We Tried (That Didn't Work)
1. **Using complex sketch profiles** - Initially tried to create the shaft hole with keyway as a single complex profile using arcs and lines. This failed.
2. **Different sketch selection methods** - Tried selecting sketches by name ("Sketch2"), by feature reference, and using Linq queries. None worked.
3. **Simplified to separate cuts** - Split into two operations: circular shaft hole + rectangular keyway. Shaft hole still failed.

## Root Cause Analysis

### Investigation Process
1. **Compared with working VBA code** - Found a working VBA example:
   ```vb
   Set myFeature = Part.FeatureManager.FeatureCut4(True, False, True, 1, 0, 0.00254, 0.00254, False, False, False, False, 1.74532925199433E-02, 1.74532925199433E-02, False, False, False, False, False, True, True, True, True, False, 0, 0, False, False)
   ```

2. **Checked documentation** - Consulted `FeatureCut4.md` and `swEndConditions_e` enum docs to understand parameter meanings.

3. **Identified key differences**:
   - **Dir parameter**: VBA used `True`, we used `False`
   - **UseFeatScope**: VBA used `True`, we used `False`
   - **AssemblyFeatureScope**: VBA used `True`, we used `False`
   - **AutoSelectComponents**: VBA used `True`, we used `False`

### The Critical Parameter: Dir

From the documentation:
> **Dir**: True for Direction 1 to be opposite of the default direction
>
> The default direction for cut operations is opposite the sketch normal.

**This was the primary issue** - we were cutting in the wrong direction!

## The Solution

Changed FeatureCut4 parameters to match working VBA example:

```csharp
IFeature holeFeature = swFeatMgr.FeatureCut4(
    Sd: true,                                          // Single-ended cut
    Flip: false,                                       // Don't flip side to cut
    Dir: true,                                         // ✅ CRITICAL: Flip direction
    T1: (int)swEndConditions_e.swEndCondThroughAll,   // Through all
    T2: 0,
    D1: 0,
    D2: 0,
    Dchk1: false,
    Dchk2: false,
    Ddir1: false,
    Ddir2: false,
    Dang1: 0,
    Dang2: 0,
    OffsetReverse1: false,
    OffsetReverse2: false,
    TranslateSurface1: false,
    TranslateSurface2: false,
    NormalCut: false,
    UseFeatScope: true,                                // ✅ Feature affects selected bodies
    UseAutoSelect: true,
    AssemblyFeatureScope: true,                        // ✅ Assembly feature scope
    AutoSelectComponents: true,                        // ✅ Auto-select components
    PropagateFeatureToParts: false,
    T0: (int)swStartConditions_e.swStartSketchPlane,
    StartOffset: 0,
    FlipStartOffset: false,
    OptimizeGeometry: false);
```

## Key Takeaways

1. **Always check working examples first** - Don't assume parameter values. Look for VBA/C# examples that work.

2. **Understand cut direction** - The `Dir` parameter is critical for cuts:
   - Default for cuts: opposite of sketch normal
   - `Dir=true` reverses this default
   - Sketch plane matters!

3. **Consult documentation systematically**:
   - Read method documentation (parameters, remarks)
   - Check enum values (don't assume 0 vs 1)
   - Look at related types

4. **Multi-body considerations** - `UseFeatScope`, `AssemblyFeatureScope`, and `AutoSelectComponents` matter even for simple parts, possibly due to how SolidWorks handles body selection internally.

5. **Don't guess - verify**:
   ```bash
   # Check enum values
   grep -r "swEndConditions_e" .claude/skills/developing-solidworks/solidworks-api/api/enums/

   # Read specific docs
   cat .claude/skills/developing-solidworks/solidworks-api/api/types/IFeatureManager/FeatureCut4.md
   ```

## Best Practices Going Forward

1. **Start with working examples** - Find VBA or C# code that does something similar
2. **Match parameters exactly** - Use the same parameter values as working code
3. **Document deviations** - If changing parameters, note why and test thoroughly
4. **Use named parameters** - Makes code readable and prevents parameter order mistakes
5. **Check documentation** - Don't assume, verify enum values and parameter meanings

## References
- `solidworks-api/api/types/IFeatureManager/FeatureCut4.md`
- `solidworks-api/api/enums/swEndConditions_e/`
- Working VBA example (see above)
