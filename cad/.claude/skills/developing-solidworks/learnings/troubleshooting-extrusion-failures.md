---
title: Troubleshooting Why Sketches Can't Be Extruded
category: Sketch Validation
tags: [sketch, validation, error-handling, CheckFeatureUse, GetErrorCode2, troubleshooting, extrusion-failures]
date: 2025-11-23
---

# Troubleshooting Why Sketches Can't Be Extruded

## Problem
**When extrusion fails and you don't know why**, the sketch may have validation issues that aren't immediately obvious. The UI shows warnings like "The sketch contains a self-intersecting contour", but programmatically we need to diagnose *why* a sketch can't be extruded.

## Core Insight: Use CheckFeatureUse to Diagnose WHY Extrusions Fail

**THE KEY DISCOVERY: `ISketch.CheckFeatureUse()` diagnoses exactly WHY a sketch can't be extruded.**

When an extrusion returns null, you need to know WHY it failed. `CheckFeatureUse()` inspects the sketch and returns specific status codes indicating the problem (self-intersection, open contours, etc.).

## Primary Method: CheckFeatureUse (MOST IMPORTANT)

**This is the actual important code from Gemini's solution** - when extrusion fails, use CheckFeatureUse to diagnose:

```csharp
IFeature feature = doc.FeatureManager.FeatureExtrusion3(/* params */);

if (feature == null) {
    Console.WriteLine("Extrusion failed. Diagnosing sketch...");

    // Select and get the sketch
    doc.Extension.SelectByID2("Sketch1", "SKETCH", 0, 0, 0, false, 0, null, 0);
    ISelectionMgr swSelMgr = doc.SelectionManager;
    IFeature sketchFeat = (IFeature)swSelMgr.GetSelectedObject6(1, -1);
    ISketch sketch = (ISketch)sketchFeat.GetSpecificFeature2();

    // THE KEY METHOD - CheckFeatureUse diagnoses the problem
    int openCount = 0;
    int closedCount = 0;
    int checkStatus = sketch.CheckFeatureUse(
        (int)swSketchCheckFeatureProfileUsage_e.swSketchCheckFeature_BASEEXTRUDE,
        ref openCount,
        ref closedCount
    );

    Console.WriteLine($"Sketch Check Status: {checkStatus}");
    Console.WriteLine($"Open Contours: {openCount}");
    Console.WriteLine($"Closed Contours: {closedCount}");

    // Check for self-intersecting status
    if (checkStatus == (int)swSketchCheckFeatureStatus_e.swSketchCheckFeatureStatus_CturXCtur ||
        checkStatus == (int)swSketchCheckFeatureStatus_e.swSketchCheckFeatureStatus_EntXSelf ||
        checkStatus == (int)swSketchCheckFeatureStatus_e.swSketchCheckFeatureStatus_EntXEnt) {
        Console.WriteLine("DIAGNOSIS: Self-intersecting geometry detected");
        Console.WriteLine($"Specific issue: {(swSketchCheckFeatureStatus_e)checkStatus}");
    }
}
```

### Key Status Codes from swSketchCheckFeatureStatus_e

**Self-intersection codes** (what we're looking for):
- `swSketchCheckFeatureStatus_CturXCtur` (4): Contour crosses contour
- `swSketchCheckFeatureStatus_EntXSelf` (6): Entity crosses itself
- `swSketchCheckFeatureStatus_EntXEnt` (5): Entity crosses entity

**Other status codes** (different problems):
- `swSketchCheckFeatureStatus_OK` (0): Sketch is valid
- Various other codes for open contours, underdefined sketches, etc.

## Secondary Method: GetErrorCode2 (When Feature Exists)

Sometimes the feature object is created but still has errors:

```csharp
IFeature feature = doc.FeatureManager.FeatureExtrusion3(/* params */);

if (feature != null) {
    bool isWarning = false;
    int errorCode = feature.GetErrorCode2(out isWarning);

    if (errorCode == (int)swFeatureError_e.swFeatureErrorSketchContainsSelfIntersectingContour) {
        Console.WriteLine("DIAGNOSIS: Sketch contains self-intersecting contour");
    }
    else if (errorCode != 0) {
        Console.WriteLine($"Feature has error code: {errorCode}");
    }
}
```

**Note**: This is less useful than CheckFeatureUse because it only works when the feature object exists.

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

1. **MOST IMPORTANT: Use `CheckFeatureUse()` to diagnose extrusion failures** - This is THE technique from Gemini's solution
2. **CheckFeatureUse tells you WHY sketches fail** - Returns specific status codes (self-intersection, open contours, etc.)
3. **Provides contour counts** - Shows how many open vs closed contours exist
4. **Works for different feature types** - Can validate for BASEEXTRUDE, CUT, REVOLVE, etc.
5. **GetErrorCode2 is secondary** - Only useful when feature object exists

## Best Practices

1. **ALWAYS use CheckFeatureUse when extrusion returns null** - Don't just report "extrusion failed", diagnose WHY
2. **Log the status code and contour counts** - Provides specific actionable information
3. **Check for self-intersection codes** - CturXCtur, EntXSelf, and EntXEnt indicate geometry problems
4. **Report specific issues** - Tell users exactly what's wrong (e.g., "Sketch has self-intersecting contour" vs "Extrusion failed")

## Complete Troubleshooting Pattern

```csharp
IFeature feature = doc.FeatureManager.FeatureExtrusion3(/* params */);

if (feature == null) {
    Console.WriteLine("✗ Extrusion returned NULL - diagnosing sketch...");

    // Get the sketch
    doc.Extension.SelectByID2("Sketch1", "SKETCH", 0, 0, 0, false, 0, null, 0);
    ISelectionMgr swSelMgr = doc.SelectionManager;
    IFeature sketchFeat = (IFeature)swSelMgr.GetSelectedObject6(1, -1);
    ISketch sketch = (ISketch)sketchFeat.GetSpecificFeature2();

    // CRITICAL: Use CheckFeatureUse to diagnose
    int openCount = 0, closedCount = 0;
    int status = sketch.CheckFeatureUse(
        (int)swSketchCheckFeatureProfileUsage_e.swSketchCheckFeature_BASEEXTRUDE,
        ref openCount, ref closedCount
    );

    Console.WriteLine($"Sketch diagnosis: {(swSketchCheckFeatureStatus_e)status}");
    Console.WriteLine($"Open contours: {openCount}, Closed: {closedCount}");

    // Check for specific issues
    if (status == (int)swSketchCheckFeatureStatus_e.swSketchCheckFeatureStatus_CturXCtur ||
        status == (int)swSketchCheckFeatureStatus_e.swSketchCheckFeatureStatus_EntXSelf ||
        status == (int)swSketchCheckFeatureStatus_e.swSketchCheckFeatureStatus_EntXEnt) {
        Console.WriteLine("Root cause: Self-intersecting geometry");
    }
}
else {
    Console.WriteLine("✓ Feature created - checking for errors...");

    bool isWarning = false;
    int errorCode = feature.GetErrorCode2(out isWarning);

    if (errorCode == 0) {
        Console.WriteLine("✓ Extrusion succeeded");
    }
    else {
        Console.WriteLine($"✗ Feature has error code: {errorCode}");
    }
}
```

## References
- `IFeature.GetErrorCode2()` documentation
- `ISketch.CheckFeatureUse()` documentation
- `swFeatureError_e` enum
- `swSketchCheckFeatureStatus_e` enum
- `swSketchCheckFeatureProfileUsage_e` enum
