---
title: Troubleshooting Why Sketches Can't Be Extruded
category: Sketch Validation
tags: [sketch, validation, error-handling, CheckFeatureUse, GetErrorCode2, troubleshooting, extrusion-failures]
date: 2025-11-23
---

# Troubleshooting Why Sketches Can't Be Extruded

## Problem
**When extrusion fails and you don't know why**, the sketch may have validation issues that aren't immediately obvious. The UI shows warnings like "The sketch contains a self-intersecting contour", but programmatically we need to diagnose *why* a sketch can't be extruded.

## Core Insight: Troubleshooting Extrusion Failures

**This is the key technique for diagnosing why sketches fail to extrude.** When `FeatureExtrusion3` returns null or fails, use `ISketch.CheckFeatureUse()` to get the exact reason.

## Solution: Two Detection Methods

### Method 1: Feature Error Code (Post-Operation)
After attempting extrusion, check the feature's error code:

```csharp
IFeature feature = doc.FeatureManager.FeatureExtrusion3(/* params */);

if (feature != null) {
    bool isWarning = false;
    int errorCode = feature.GetErrorCode2(out isWarning);

    if (errorCode == (int)swFeatureError_e.swFeatureErrorSketchContainsSelfIntersectingContour) {
        // Self-intersection detected
    }
}
```

**Limitation**: Only works if the feature object is created (not always guaranteed).

### Method 2: Sketch Validation (Pre-Operation)
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

1. **PRIMARY USE CASE: Troubleshooting extrusion failures** - When `FeatureExtrusion3` returns null, immediately use `CheckFeatureUse()` to diagnose the problem
2. **Prefer Method 2 (CheckFeatureUse)**: Validates *before* operation, more reliable, gives specific diagnosis
3. **Use Method 1 as fallback**: When feature object exists, provides specific error code
4. **CheckFeatureUse is versatile**: Can validate for different feature types (BASEEXTRUDE, CUT, REVOLVE, etc.)
5. **Multiple intersection types**: Different status codes indicate specific geometry problems (self-intersection, open contours, etc.)

## Best Practices

1. **Always diagnose failed extrusions** - Don't just return "extrusion failed", use CheckFeatureUse to get the actual reason
2. **Validate before creating features** - Prevents failed operations and wasted computation
3. **Report specific issues** - Use status codes to provide detailed feedback (e.g., "Sketch has 2 open contours" vs "Extrusion failed")
4. **Test with simple geometry** - Bowtie/X shape is minimal reproducible case for self-intersection

## Troubleshooting Pattern

```csharp
IFeature feature = doc.FeatureManager.FeatureExtrusion3(/* params */);

if (feature == null) {
    Console.WriteLine("Extrusion failed. Diagnosing sketch...");

    // Get the sketch and diagnose
    doc.Extension.SelectByID2("Sketch1", "SKETCH", 0, 0, 0, false, 0, null, 0);
    IFeature sketchFeat = (IFeature)doc.SelectionManager.GetSelectedObject6(1, -1);
    ISketch sketch = (ISketch)sketchFeat.GetSpecificFeature2();

    int openCount = 0, closedCount = 0;
    int status = sketch.CheckFeatureUse(
        (int)swSketchCheckFeatureProfileUsage_e.swSketchCheckFeature_BASEEXTRUDE,
        ref openCount, ref closedCount
    );

    Console.WriteLine($"Diagnosis: {(swSketchCheckFeatureStatus_e)status}");
    Console.WriteLine($"Open contours: {openCount}, Closed contours: {closedCount}");
}
```

## References
- `IFeature.GetErrorCode2()` documentation
- `ISketch.CheckFeatureUse()` documentation
- `swFeatureError_e` enum
- `swSketchCheckFeatureStatus_e` enum
- `swSketchCheckFeatureProfileUsage_e` enum
