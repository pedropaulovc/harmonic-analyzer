---
name: developing-solidworks-csharp
description: Writes, modifies, and debugs C# code that interacts with the SolidWorks API. Use when working with .cs or .csproj files that reference SolidWorks SDK, SolidWorks.Interop assemblies, COM interop with SolidWorks, or when the user mentions SolidWorks API development, macros, or add-ins.
---

# Developing SolidWorks C# Code

## Documentation-First Workflow

**CRITICAL**: Base knowledge of SolidWorks API is inconsistent. Always consult [solidworks-api](./solidworks-api/) before writing code.

### Workflow checklist

Copy and track progress through complex SolidWorks tasks:

```
SolidWorks Development Progress:
- [ ] Step 1: Review API documentation for required methods
- [ ] Step 2: Write code with named parameters
- [ ] Step 3: Add error handling and null checks
- [ ] Step 4: Test and verify functionality
- [ ] Step 5: Add cleanup and resource disposal
```

### Required steps before writing code

1. **Read documentation**: See [solidworks-api](./solidworks-api/) for:
   - API Reference (method signatures, parameters)
   - Programming Guide (best practices, patterns)
   - Code Examples (proven implementations)

2. **If documentation is unavailable**: ABORT and notify user

3. **Verify approach**: Confirm alignment with current SDK conventions

## SolidWorks-Specific Patterns

### SDK library references

Find latest SDK libraries:
```bash
python scripts/find_api_redist.py
```

Reference appropriate assemblies in your project:
- SolidWorks.Interop.sldworks
- SolidWorks.Interop.swconst
- SolidWorks.Interop.swpublished

### Code quality requirements

**Named parameters** (required for methods with many parameters):
```csharp
// Good - Clear what each value represents
model.CreateExtrudeFeatureSolid2(
    properSide: swEndConditions_e.swEndCondBlind,
    reverseDirection: false,
    depth: 0.1,
    draftAngle: 0,
    draftOutward: false
);

// Avoid - Unclear what values mean
model.CreateExtrudeFeatureSolid2(1, false, 0.1, 0, false);
```

**Error handling** (SolidWorks API frequently returns null):
```csharp
IModelDoc2 doc = swApp.ActiveDoc as IModelDoc2;
if (doc == null)
{
    throw new InvalidOperationException("No active document");
}
```

**Return value checks** (many methods return bool for success):
```csharp
bool success = doc.Extension.SelectByID2(
    name: "Face1",
    type: "FACE",
    x: 0, y: 0, z: 0,
    append: false,
    mark: 0,
    callout: null,
    selectOption: 0
);

if (!success)
{
    throw new Exception("Selection failed");
}
```

### Common patterns

**Units**: SolidWorks uses meters internally
```csharp
// Convert inches to meters
double lengthMeters = lengthInches * 0.0254;
```

**Object cleanup**: Release COM objects when done
```csharp
Marshal.ReleaseComObject(feature);
```

**Selection management**: Use selection marks for multi-step operations
```csharp
// Select with mark 1
doc.Extension.SelectByID2("Face1", "FACE", 0, 0, 0, false, 1, null, 0);
// Select with mark 2
doc.Extension.SelectByID2("Face2", "FACE", 0, 0, 0, true, 2, null, 0);
```

**Document state**: Check before operations
```csharp
if (doc.GetType() != (int)swDocumentTypes_e.swDocPART)
{
    throw new InvalidOperationException("Operation requires part document");
}
```

## Code Verification Checklist

Before delivering code:
```
Code Quality:
- [ ] Consulted solidworks-api documentation
- [ ] Used latest SDK library references
- [ ] Applied documented API patterns
- [ ] Used named parameters
- [ ] Added null checks and error handling
- [ ] Included SolidWorks-specific comments
- [ ] Handled units correctly (meters internally)
- [ ] Code is complete and runnable
```

## When to Ask for Clarification

- Requested functionality may not be possible with SolidWorks API
- Multiple significantly different approaches exist
- Task requires specific SolidWorks version or configuration details
- Documentation is ambiguous or contradictory

## Quick Examples

### Creating a part with extrusion

1. Consult [solidworks-api](./solidworks-api/) for `CreateExtrudeFeatureSolid2`
2. Write code:

```csharp
using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swconst;

// Get application and create new part
ISldWorks swApp = (ISldWorks)Marshal.GetActiveObject("SldWorks.Application");
IModelDoc2 doc = swApp.NewDocument("part template", 0, 0, 0);

if (doc == null) throw new Exception("Failed to create document");

// Create sketch on front plane
doc.Extension.SelectByID2("Front Plane", "PLANE", 0, 0, 0, false, 0, null, 0);
doc.SketchManager.InsertSketch(true);
doc.SketchManager.CreateCenterRectangle(0, 0, 0, 0.05, 0.05, 0);
doc.SketchManager.InsertSketch(true);

// Create extrude
doc.Extension.SelectByID2("Sketch1", "SKETCH", 0, 0, 0, false, 0, null, 0);
IFeature feature = doc.FeatureManager.FeatureExtrusion2(
    sd: true,
    flip: false,
    dir: false,
    dir2: (int)swEndConditions_e.swEndCondBlind,
    dir1: (int)swEndConditions_e.swEndCondBlind,
    d1: 0.1,
    d2: 0,
    dchk1: false,
    dchk2: false,
    ddir1: false,
    ddir2: false,
    dang1: 0,
    dang2: 0,
    offstatus: false
);

if (feature == null) throw new Exception("Extrusion failed");
```

### Debugging selection errors

Common issues:
- **Wrong selection type**: Use exact type string ("FACE", not "Face" or "face")
- **Missing type cast**: Cast returned objects to correct interface
- **Null returns**: Always check for null after selection operations
- **Selection marks**: Ensure unique marks when selecting multiple entities

For detailed troubleshooting, see [solidworks-api](./solidworks-api/) error handling guides.
