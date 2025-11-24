---
name: developing-solidworks
description: ANYTHING related to SolidWorks. Writes, modifies, and debugs C# code that interacts with SolidWorks. Use when working with .cs or .csproj files that (will) reference SolidWorks SDK, SolidWorks.Interop assemblies, COM interop with SolidWorks.
---

# Developing SolidWorks C# Code

## Documentation-First Workflow

**CRITICAL**: Base knowledge of SolidWorks API is inconsistent. Always consult documentation [Types](./types/), [Enums](./enums/), [Docs](./docs/), [Examples](./examples/). You ABSOLUTELY MUST run your code before claiming success. Don't bother with `dotnet build`, use `dotnet run` immediately after code changes. JUST COMPILING IS NOT ENOUGH.

### Workflow checklist

Copy and track progress through complex SolidWorks tasks:

```
SolidWorks Development Progress:
- [ ] Step 1: Review API documentation for required methods
- [ ] Step 2: Write code with named parameters
- [ ] Step 3: Add error handling and null checks
- [ ] Step 4: Verify functionality via `dotnet run`
- [ ] Step 5: Add cleanup and resource disposal
```

### Required steps before writing code

1. **Use grep to explore the docs**: The grep-optimized documentation structure makes it easy to find specific methods quickly or extract member documentation programmatically

2. **Read documentation**: Available in the skill folder:
   - API Reference in `./types/` and `./enums/` (method signatures, parameters, enum values)
   - Programming Guide in `./docs/` (best practices, patterns)
   - Code Examples in `./examples/` (proven implementations)

3. **If documentation is unavailable**: ABORT and notify user

4. **Verify approach**: Confirm alignment with current SDK conventions

### Grep Use Cases

**Find specific methods quickly**
```bash
# Find CreateArc method documentation
grep -r "CreateArc" .claude/skills/developing-solidworks/types/IModelDoc2/

# Get just that method's file
cat .claude/skills/developing-solidworks/types/IModelDoc2/CreateArc2.md
```

**Extract member documentation programmatically**
```bash
# Get all methods in IModelDoc2
ls .claude/skills/developing-solidworks/types/IModelDoc2/*.md | grep -v "_overview"

# Extract all method signatures
grep "^**Signature**:" .claude/skills/developing-solidworks/types/IModelDoc2/*.md
```

**Search by metadata**
```bash
# Find all members in "Application Interfaces" category
grep -r "category: Application Interfaces" .claude/skills/developing-solidworks/types/

# Find all methods (not properties)
grep -r "kind: method" .claude/skills/developing-solidworks/types/

# Find all enum members
grep -r "kind: enum_member" .claude/skills/developing-solidworks/enums/
```

**Navigate by category**
```bash
# View all types in a category
cat .claude/skills/developing-solidworks/index/by_category.md | grep -A 20 "Application Interfaces"

# View statistics
cat .claude/skills/developing-solidworks/index/statistics.md
```

### Finding Enums and Their Values

SolidWorks API relies heavily on enums. Finding the correct enum and its values is critical for writing working code.

**Step 1: Find the enum file**
```bash
# Find enum by name (e.g., swEndConditions_e)
ls .claude/skills/developing-solidworks/enums/ | grep -i "endconditions"

# Search across all enums
grep -r "swEndCondBlind" .claude/skills/developing-solidworks/enums/
```

**Step 2: Read the enum definition**
```bash
# Read the full enum file
cat .claude/skills/developing-solidworks/enums/swEndConditions_e.md
```

**Step 3: Extract specific enum values**

Each enum file contains:
- Enum name and description
- All possible values with their integer equivalents
- Usage context

Example enum file structure:
```markdown
# swEndConditions_e

**Description**: End conditions for extrude and revolve features

**Values**:
- `swEndCondBlind = 0` - Blind end condition
- `swEndCondThroughAll = 1` - Through all end condition
- `swEndCondUpToNext = 2` - Up to next end condition
...
```

**Common enum patterns**:
```bash
# Find all sketch-related enums
ls .claude/skills/developing-solidworks/enums/ | grep -i "sketch"

# Find all feature error enums
ls .claude/skills/developing-solidworks/enums/ | grep -i "error"

# Find enums for specific operation type
grep -r "category:" .claude/skills/developing-solidworks/enums/ | grep "Feature"
```

**Verify enum usage in code examples**:
```bash
# Find examples using specific enum
grep -r "swEndConditions_e" .claude/skills/developing-solidworks/examples/

# See how enum is cast in practice
grep -r "int.*swEndConditions_e" .claude/skills/developing-solidworks/examples/
```

**CRITICAL**: Always cast enums to `int` when passing to API methods:
```csharp
// Correct - explicit cast
Dir1: (int)swEndConditions_e.swEndCondBlind

// Wrong - will cause compilation error
Dir1: swEndConditions_e.swEndCondBlind
```

**Return value enums**: When methods return enum values as integers, cast back to enum for readability:
```csharp
// Cast return value to enum for readable output
var status = (swSketchCheckFeatureStatus_e)sketch.CheckFeatureUse();
Console.WriteLine($"Sketch status: {status}");  // Prints "swSketchCheckFeatureStatus_OK" not "0"
```

## Learnings from Past Issues

Consult the `./learnings/` directory for documented solutions to common problems and pitfalls. Each learning includes:
- Problem description and symptoms
- Investigation process and root cause analysis
- Working solutions with code examples
- Key takeaways and best practices

Use grep to search by category or tags:
```bash
# Find all learnings in a category
grep -r "category: Feature Operations" .claude/skills/developing-solidworks/learnings/

# Search by tag
grep -r "tags:.*FeatureCut4" .claude/skills/developing-solidworks/learnings/
```

When encountering new issues, document the problem, investigation, and solution in a new file in this directory with appropriate frontmatter.

## SolidWorks-Specific Patterns

### SDK library references
The SolidWorks SDK works with .NET Framework only. Find latest SDK libraries via [find_api_redist.py](./scripts/find_api_redist.py). It will return the main folder with all SolidWorks.Interop.* assemblies.

### Code quality requirements

**Named parameters** (required for methods with many parameters):
```csharp
// Good - Clear what each value represents
  IFeature extrudeFeature = swFeatureMgr.FeatureExtrusion3(
      Sd: true,                                          // Single direction
      Flip: false,                                       // Don't flip side to cut
      Dir: false,                                        // Don't flip extrusion direction
      //...
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

**Error troubleshooting** (Leverage `IFaultEntity` to get more details on failed operations):
See [Check Edges for Faults (C#)](./examples/Check_Edges_for_Faults_Example_CSharp.md) for an example of how to use it.

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

**Run code before claiming success** (you MUST run your new code using `dotnet run` or similar. Just building it is NOT enough)

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
- [ ] Consulted API documentation (types/, enums/, docs/, examples/)
- [ ] Used latest SDK library references
- [ ] Applied documented API patterns
- [ ] Used named parameters
- [ ] Added null checks and error handling
- [ ] Included SolidWorks-specific comments
- [ ] Handled units correctly
- [ ] Code is complete and runnable
- [ ] Code was validated at least once via `dotnet run` or `dotnet test`
```

## When to Ask for Clarification

- Requested functionality may not be possible with SolidWorks API
- Multiple significantly different approaches exist
- Task requires specific SolidWorks version or configuration details
- Documentation is ambiguous or contradictory

## Quick Examples

### Creating a part with extrusion

1. Consult API documentation for `CreateExtrudeFeatureSolid2` (search in `./types/`)
2. Write code:

```csharp
using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swconst;

// Get application and create new part
ISldWorks swApp = new SldWorks.SldWorks();
IModelDoc2 doc = swApp.NewDocument(
      TemplateName: swApp.GetUserPreferenceStringValue((int)swUserPreferenceStringValue_e.swDefaultTemplatePart),
      PaperSize: 0,
      Width: 0,
      Height: 0);

if (doc == null) throw new Exception("Failed to create document");

// Create sketch on front plane
doc.Extension.SelectByID2(
    Name: "Front Plane",
    Type: "PLANE",
    X: 0, Y: 0, Z: 0,
    Append: false,
    Mark: 0,
    Callout: null,
    SelectOption: 0
);
doc.SketchManager.InsertSketch(true);
doc.SketchManager.CreateCenterRectangle(0, 0, 0, 0.05, 0.05, 0);
doc.SketchManager.InsertSketch(true);

// Create extrude
doc.Extension.SelectByID2(
    Name: "Sketch1",
    Type: "SKETCH",
    X: 0, Y: 0, Z: 0,
    Append: false,
    Mark: 0,
    Callout: null,
    SelectOption: 0
);
IFeature feature = doc.FeatureManager.FeatureExtrusion2(
    Sd: true,                                          // Single direction
    Flip: false,                                       // Don't flip side to cut
    Dir: false,                                        // Don't flip extrusion direction
    Dir2: (int)swEndConditions_e.swEndCondBlind,      // End condition for direction 2
    Dir1: (int)swEndConditions_e.swEndCondBlind,      // End condition for direction 1
    D1: 0.1,                                           // Depth in meters
    D2: 0,                                             // Depth for direction 2
    Dchk1: false,                                      // Draft outward direction 1
    Dchk2: false,                                      // Draft outward direction 2
    Ddir1: false,                                      // Draft direction 1
    Ddir2: false,                                      // Draft direction 2
    Dang1: 0,                                          // Draft angle direction 1
    Dang2: 0,                                          // Draft angle direction 2
    Offstatus: false                                   // Offset from surface
);

if (feature == null) throw new Exception("Extrusion failed");
```

### Debugging selection errors

Common issues:
- **Wrong selection type**: Use exact type string ("FACE", not "Face" or "face")
- **Missing type cast**: Cast returned objects to correct interface
- **Null returns**: Always check for null after selection operations
- **Selection marks**: Ensure unique marks when selecting multiple entities
- **Don't guess - verify**: Double check docs when in doubt
   ```bash
   # Check enum values, e.g.
   grep -r "swEndConditions_e" .claude/skills/developing-solidworks/enums/

   # Read specific docs e.g.
   cat .claude/skills/developing-solidworks/types/IFeatureManager/FeatureCut4.md
   ```

For detailed troubleshooting, consult the programming guides in `./docs/` or search for relevant examples in `./examples/`.
