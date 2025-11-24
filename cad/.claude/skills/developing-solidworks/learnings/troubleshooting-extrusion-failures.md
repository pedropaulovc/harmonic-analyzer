---
title: Troubleshooting Why Sketches Can't Be Extruded
category: Sketch Validation
tags: [sketch, validation, error-handling, CheckFeatureUse, GetErrorCode2, troubleshooting, extrusion-failures]
date: 2025-11-23
---

# Troubleshooting Why Sketches Can't Be Extruded

## Problem
**When extrusion fails and you don't know why**, the sketch may have validation issues that aren't immediately obvious. The UI shows warnings like "The sketch contains a self-intersecting contour", but programmatically we need to diagnose *why* a sketch can't be extruded.

## Core Insight: Use GetErrorCode2 to Diagnose Feature Failures

**THE KEY DISCOVERY: `IFeature.GetErrorCode2()` tells you exactly why a feature operation failed.**

Even when operations fail, SolidWorks often still returns a feature object. This feature contains diagnostic error codes that tell you precisely what went wrong.

## Primary Method: GetErrorCode2 (MOST IMPORTANT)

**Always check `GetErrorCode2` after creating features** - this is how you troubleshoot failures:

```csharp
IFeature feature = doc.FeatureManager.FeatureExtrusion3(/* params */);

if (feature != null) {
    bool isWarning = false;
    int errorCode = feature.GetErrorCode2(out isWarning);

    Console.WriteLine($"Feature Error Code: {errorCode}");
    Console.WriteLine($"Is Warning: {isWarning}");

    if (errorCode == (int)swFeatureError_e.swFeatureErrorSketchContainsSelfIntersectingContour) {
        Console.WriteLine("DIAGNOSIS: Sketch contains self-intersecting contour");
    }
    else if (errorCode != 0) {
        Console.WriteLine($"DIAGNOSIS: Feature failed with error code {errorCode}");
    }
}
else {
    Console.WriteLine("Feature returned NULL - operation completely failed");
}
```

**Critical Point**: The feature object may exist even when the operation fails! Don't just check `if (feature == null)` - always call `GetErrorCode2()`.

### Common Error Codes

Key values from `swFeatureError_e`:
- `0` - Success, no error
- `swFeatureErrorSketchContainsSelfIntersectingContour` - Self-intersecting geometry
- Other error codes indicate different failure modes

## Fallback Method: CheckFeatureUse (Pre-Validation)
Before attempting extrusion, validate the sketch:

```csharp
// Select and get the sketch
doc.Extension.SelectByID2("Sketch1", "SKETCH", 0, 0, 0, false, 0, null, 0);
ISelectionMgr swSelMgr = doc.SelectionManager;
IFeature sketchFeat = (IFeature)swSelMgr.GetSelectedObject6(1, -1);
ISketch sketch = (ISketch)sketchFeat.GetSpecificFeature2();

// Check sketch validity for base extrude
int openCount = 0;
int closedCount = 0;
int checkStatus = sketch.CheckFeatureUse(
    (int)swSketchCheckFeatureProfileUsage_e.swSketchCheckFeature_BASEEXTRUDE,
    ref openCount,
    ref closedCount
);

// Check for self-intersection status codes
if (checkStatus == (int)swSketchCheckFeatureStatus_e.swSketchCheckFeatureStatus_CturXCtur ||
    checkStatus == (int)swSketchCheckFeatureStatus_e.swSketchCheckFeatureStatus_EntXSelf ||
    checkStatus == (int)swSketchCheckFeatureStatus_e.swSketchCheckFeatureStatus_EntXEnt) {
    // Self-intersection detected
}
```

**Relevant Status Codes**:
- `swSketchCheckFeatureStatus_CturXCtur` (4): Contour crosses contour
- `swSketchCheckFeatureStatus_EntXSelf` (6): Entity crosses itself
- `swSketchCheckFeatureStatus_EntXEnt` (5): Entity crosses entity

## Creating Test Geometry

Simple bowtie shape that triggers self-intersection:

```csharp
doc.SketchManager.InsertSketch(true);

// Creates an X shape (self-intersecting)
doc.SketchManager.CreateLine(0, 0, 0, 0.05, 0.05, 0);       // Diagonal /
doc.SketchManager.CreateLine(0.05, 0.05, 0, 0, 0.05, 0);    // Top horizontal
doc.SketchManager.CreateLine(0, 0.05, 0, 0.05, 0, 0);       // Diagonal \
doc.SketchManager.CreateLine(0.05, 0, 0, 0, 0, 0);          // Bottom horizontal

doc.SketchManager.InsertSketch(true); // Exit sketch
```

## Key Takeaways

1. **MOST IMPORTANT: Always call `GetErrorCode2()`** - This is THE technique for diagnosing why feature operations fail
2. **Feature objects can exist even when operations fail** - Don't assume `feature != null` means success
3. **Check error codes, not just null** - A feature with `errorCode != 0` has failed or has warnings
4. **Use CheckFeatureUse as a fallback** - When feature is null or you want pre-validation
5. **Error codes are specific** - Different codes tell you exactly what went wrong (self-intersection, open contours, etc.)

## Best Practices

1. **ALWAYS check GetErrorCode2 after creating features** - This is how you get diagnostic information
2. **Log error codes during debugging** - Print both the error code number and the `swFeatureError_e` enum value
3. **Handle both null and error codes** - A feature can be non-null but still have errors
4. **Report specific issues** - Use error codes to provide detailed feedback instead of generic "operation failed"

## Complete Troubleshooting Pattern

```csharp
IFeature feature = doc.FeatureManager.FeatureExtrusion3(/* params */);

if (feature != null) {
    // CRITICAL: Even if feature exists, check for errors
    bool isWarning = false;
    int errorCode = feature.GetErrorCode2(out isWarning);

    if (errorCode == 0) {
        Console.WriteLine("✓ Extrusion succeeded");
    }
    else {
        Console.WriteLine($"✗ Extrusion failed with error code: {errorCode}");
        Console.WriteLine($"  Error type: {(swFeatureError_e)errorCode}");
        Console.WriteLine($"  Is warning: {isWarning}");
    }
}
else {
    Console.WriteLine("✗ Feature returned NULL - complete failure");

    // Fallback: Use CheckFeatureUse to diagnose the sketch
    doc.Extension.SelectByID2("Sketch1", "SKETCH", 0, 0, 0, false, 0, null, 0);
    IFeature sketchFeat = (IFeature)doc.SelectionManager.GetSelectedObject6(1, -1);
    ISketch sketch = (ISketch)sketchFeat.GetSpecificFeature2();

    int openCount = 0, closedCount = 0;
    int status = sketch.CheckFeatureUse(
        (int)swSketchCheckFeatureProfileUsage_e.swSketchCheckFeature_BASEEXTRUDE,
        ref openCount, ref closedCount
    );

    Console.WriteLine($"Sketch diagnosis: {(swSketchCheckFeatureStatus_e)status}");
    Console.WriteLine($"Open contours: {openCount}, Closed: {closedCount}");
}
```

## References
- `IFeature.GetErrorCode2()` documentation
- `ISketch.CheckFeatureUse()` documentation
- `swFeatureError_e` enum
- `swSketchCheckFeatureStatus_e` enum
- `swSketchCheckFeatureProfileUsage_e` enum
