---
name: developing-solidworks-csharp
description: Writes, modifies, and debugs C# code that interacts with the SolidWorks API. Use when working with .cs or .csproj files that reference SolidWorks SDK, SolidWorks.Interop assemblies, COM interop with SolidWorks, or when the user mentions SolidWorks development, macros, or add-ins.
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

### Grep Use Cases

The grep-optimized documentation structure makes it easy to:

**Find specific methods quickly**
```bash
# Find CreateArc method documentation
grep -r "CreateArc" .claude/skills/developing-solidworks-csharp/solidworks-api/api/types/IModelDoc2/

# Get just that method's file
cat .claude/skills/developing-solidworks-csharp/solidworks-api/api/types/IModelDoc2/CreateArc2.md
```

**Extract member documentation programmatically**
```bash
# Get all methods in IModelDoc2
ls .claude/skills/developing-solidworks-csharp/solidworks-api/api/types/IModelDoc2/*.md | grep -v "_overview"

# Extract all method signatures
grep "^**Signature**:" .claude/skills/developing-solidworks-csharp/solidworks-api/api/types/IModelDoc2/*.md
```

**Search by metadata**
```bash
# Find all members in "Application Interfaces" category
grep -r "category: Application Interfaces" .claude/skills/developing-solidworks-csharp/solidworks-api/api/types/

# Find all methods (not properties)
grep -r "kind: method" .claude/skills/developing-solidworks-csharp/solidworks-api/api/types/

# Find all enum members
grep -r "kind: enum_member" .claude/skills/developing-solidworks-csharp/solidworks-api/api/enums/
```

**Navigate by category**
```bash
# View all types in a category
cat .claude/skills/developing-solidworks-csharp/solidworks-api/api/index/by_category.md | grep -A 20 "Application Interfaces"

# View statistics
cat .claude/skills/developing-solidworks-csharp/solidworks-api/api/index/statistics.md
```

## SolidWorks-Specific Patterns

### SDK library references

Find latest SDK libraries via `scripts/find_api_redist.py`. It will return the main folder with all SolidWorks.Interop.* assemblies.

### Code quality requirements

**Named parameters** (required for methods with many parameters):
```csharp
// Good - Clear what each value represents
  IFeature extrudeFeature = swFeatureMgr.FeatureExtrusion3(
      Sd: true,                                          // Single direction
      Flip: false,                                       // Don't flip side to cut
      Dir: false,                                        // Don't flip extrusion direction
      T1: (int)swEndConditions_e.swEndCondBlind,         // End condition: Blind
      T2: (int)swEndConditions_e.swEndCondBlind,         // End condition 2 (unused for single)
      D1: 0.1,                                           // Depth in meters
      D2: 0,                                             // Depth 2 (unused for single)
      Dchk1: false,                                      // No draft angle
      Dchk2: false,                                      // No draft angle 2
      Ddir1: false,                                      // Draft direction (unused)
      Ddir2: false,                                      // Draft direction 2 (unused)
      Dang1: 0,                                          // Draft angle (unused)
      Dang2: 0,                                          // Draft angle 2 (unused)
      OffsetReverse1: false,                             // Offset direction (unused)
      OffsetReverse2: false,                             // Offset direction 2 (unused)
      TranslateSurface1: false,                          // Surface translation (unused)
      TranslateSurface2: false,                          // Surface translation 2 (unused)
      Merge: false,                                      // Don't merge bodies
      UseFeatScope: false,                               // Affect all bodies
      UseAutoSelect: true,                               // Auto-select bodies
      T0: (int)swStartConditions_e.swStartSketchPlane,   // Start from sketch plane
      StartOffset: 0,                                    // No start offset
      FlipStartOffset: false                             // Don't flip start offset
  );

// Avoid - Unclear what values mean
IFeature extrudeFeature = swFeatureMgr.FeatureExtrusion3(true, false, false, (int)swEndConditions_e.swEndCondBlind, (int)swEndConditions_e.swEndCondBlind, 0.1, 0, false, false, false, false, 0, 0, false,
   false, false, false, false, false, true, (int)swStartConditions_e.swStartSketchPlane, 0, false);
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
    Name: "Face1",
    Type: "FACE",
    X: 0, Y: 0, Z: 0,
    Append: false,
    Mark: 0,
    Callout: null,
    SelectOption: 0
);

if (!success)
{
    throw new Exception("Selection failed");
}
```

### Common patterns

**Part creation**: Use `GetUserPreferenceStringValue` to avoid hardcoding template paths.
```csharp
swModel = (ModelDoc2)swApp.NewDocument(
      TemplateName: swApp.GetUserPreferenceStringValue((int)swUserPreferenceStringValue_e.swDefaultTemplatePart),
      PaperSize: 0,
      Width: 0,
      Height: 0);
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
