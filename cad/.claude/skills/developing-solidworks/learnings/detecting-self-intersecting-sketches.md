---
title: Detecting Self-Intersecting Sketches
category: Sketch Validation
tags: [sketch, validation, error-handling, CheckFeatureUse, GetErrorCode2]
date: 2025-11-23
---

# Detecting Self-Intersecting Sketches

## Problem
When sketches contain self-intersecting contours (like a bowtie shape), extrusion fails. The UI shows: "The sketch contains a self-intersecting contour". Need programmatic detection via SDK.

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

1. **Prefer Method 2 (CheckFeatureUse)**: Validates *before* operation, more reliable
2. **Use Method 1 as fallback**: When feature object exists, provides specific error code
3. **CheckFeatureUse is versatile**: Can validate for different feature types (BASEEXTRUDE, CUT, etc.)
4. **Multiple intersection types**: Different status codes indicate specific geometry problems

## Best Practices

1. **Validate before creating features** - Prevents failed operations and wasted computation
2. **Check both methods** - For robust error detection, use CheckFeatureUse first, then verify with GetErrorCode2
3. **Report specific issues** - Use status codes to provide detailed feedback to users
4. **Test with simple geometry** - Bowtie/X shape is minimal reproducible case

## References
- `IFeature.GetErrorCode2()` documentation
- `ISketch.CheckFeatureUse()` documentation
- `swFeatureError_e` enum
- `swSketchCheckFeatureStatus_e` enum
- `swSketchCheckFeatureProfileUsage_e` enum
