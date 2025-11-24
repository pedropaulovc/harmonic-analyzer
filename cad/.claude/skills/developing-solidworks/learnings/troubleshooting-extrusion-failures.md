---
title: Troubleshooting Why Sketches Can't Be Extruded
category: Sketch Validation
tags: [sketch, validation, error-handling, CheckFeatureUse, GetErrorCode2, troubleshooting, extrusion-failures]
date: 2025-11-23
---

# Troubleshooting Why Sketches Can't Be Extruded

## Problem

When `FeatureExtrusion3()` returns null, you need to know WHY it failed.

## Solution: Use ISketch.CheckFeatureUse()

**`ISketch.CheckFeatureUse()` diagnoses exactly WHY a sketch can't be extruded.**

Returns specific status codes: self-intersection, open contours, underdefined, etc.

```csharp
IFeature feature = doc.FeatureManager.FeatureExtrusion3(/* params */);

if (feature == null) {
    // Get the sketch
    doc.Extension.SelectByID2("Sketch1", "SKETCH", 0, 0, 0, false, 0, null, 0);
    ISketch sketch = (ISketch)((IFeature)doc.SelectionManager.GetSelectedObject6(1, -1)).GetSpecificFeature2();

    // Diagnose the problem
    int openCount = 0, closedCount = 0;
    int statusCode = sketch.CheckFeatureUse(
        (int)swSketchCheckFeatureProfileUsage_e.swSketchCheckFeature_BASEEXTRUDE,
        ref openCount,
        ref closedCount
    );

    // Cast to enum for readability
    swSketchCheckFeatureStatus_e status = (swSketchCheckFeatureStatus_e)statusCode;
    Console.WriteLine($"Status: {status}");

    // Interpret results
    if (status == swSketchCheckFeatureStatus_e.swSketchCheckFeatureStatus_CturXCtur ||
        status == swSketchCheckFeatureStatus_e.swSketchCheckFeatureStatus_EntXSelf ||
        status == swSketchCheckFeatureStatus_e.swSketchCheckFeatureStatus_EntXEnt) {
        Console.WriteLine("Self-intersecting geometry detected");
    }
}
```

## Key Status Codes

**Self-intersection:**
- `swSketchCheckFeatureStatus_CturXCtur` (4): Contour crosses contour
- `swSketchCheckFeatureStatus_EntXSelf` (6): Entity crosses itself
- `swSketchCheckFeatureStatus_EntXEnt` (5): Entity crosses entity

**Other:**
- `swSketchCheckFeatureStatus_OK` (0): Valid for extrusion

## Alternative: GetErrorCode2 (When Feature Exists)

If the feature object exists but has errors:

```csharp
if (feature != null) {
    int errorCode = feature.GetErrorCode2(out bool isWarning);
    swFeatureError_e error = (swFeatureError_e)errorCode;

    if (error == swFeatureError_e.swFeatureErrorSketchContainsSelfIntersectingContour) {
        Console.WriteLine($"Error: {error}");
    }
}
```

**Note:** Less useful than `CheckFeatureUse()` because feature must exist.

## Test Geometry

Create self-intersecting bowtie:

```csharp
doc.SketchManager.InsertSketch(true);
doc.SketchManager.CreateLine(0, 0, 0, 0.05, 0.05, 0);       // Diagonal /
doc.SketchManager.CreateLine(0.05, 0.05, 0, 0, 0.05, 0);    // Top horizontal
doc.SketchManager.CreateLine(0, 0.05, 0, 0.05, 0, 0);       // Diagonal \
doc.SketchManager.CreateLine(0.05, 0, 0, 0, 0, 0);          // Bottom horizontal
doc.SketchManager.InsertSketch(true);
```

## Best Practice Pattern

```csharp
IFeature feature = doc.FeatureManager.FeatureExtrusion3(/* params */);

if (feature == null) {
    // Diagnose with CheckFeatureUse
    doc.Extension.SelectByID2(sketchName, "SKETCH", 0, 0, 0, false, 0, null, 0);
    ISketch sketch = (ISketch)((IFeature)doc.SelectionManager.GetSelectedObject6(1, -1)).GetSpecificFeature2();

    int openCount = 0, closedCount = 0;
    int statusCode = sketch.CheckFeatureUse(
        (int)swSketchCheckFeatureProfileUsage_e.swSketchCheckFeature_BASEEXTRUDE,
        ref openCount, ref closedCount
    );

    swSketchCheckFeatureStatus_e status = (swSketchCheckFeatureStatus_e)statusCode;
    throw new Exception($"Extrusion failed: {status}");
}
else {
    // Optional: Check for errors even when feature exists
    int errorCode = feature.GetErrorCode2(out bool isWarning);
    if (errorCode != 0) {
        swFeatureError_e error = (swFeatureError_e)errorCode;
        Console.WriteLine($"Feature created with error: {error}");
    }
}
```

## Key Takeaways

1. Use `CheckFeatureUse()` when extrusion returns null
2. Returns specific status codes for actionable diagnosis
3. Provides contour counts for additional context
4. Works for different feature types (BASEEXTRUDE, CUT, REVOLVE, etc.)
5. `GetErrorCode2()` is secondary - only when feature exists

## Test Program

Run `dotnet run extrusion-test` to see this technique in action.
