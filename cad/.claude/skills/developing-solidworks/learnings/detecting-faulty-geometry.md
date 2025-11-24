---
title: Detecting Faulty Geometry Using IBody2.Check3 and IFaultEntity
category: Body Validation
tags: [validation, import, fault-detection, IBody2, IFaultEntity, swFaultEntityErrorCode_e]
date: 2025-11-23
---

# Detecting Faulty Geometry Using IBody2.Check3 and IFaultEntity

## Problem

After importing STEP or other CAD files, you need to detect invalid geometry in imported bodies before attempting operations that will fail.

## Solution: IBody2.Check3 → IFaultEntity

**`IBody2.Check3` returns `IFaultEntity` containing fault count and specific `swFaultEntityErrorCode_e` values.**

```csharp
IPartDoc part = (IPartDoc)doc;
object[] bodies = (object[])part.GetBodies2((int)swBodyType_e.swSolidBody, false);

bool faultFound = false;
foreach (IBody2 body in bodies)
{
    IFaultEntity fault = body.Check3;

    if (fault != null && fault.Count > 0)
    {
        faultFound = true;
        Console.WriteLine($"Fault Count: {fault.Count}");

        for (int i = 0; i < fault.Count; i++)
        {
            // Cast to enum for readable output
            swFaultEntityErrorCode_e errorCode = (swFaultEntityErrorCode_e)fault.get_ErrorCode(i);
            Console.WriteLine($"Error {i + 1}: {errorCode}");
        }
    }
}
```

## Actual Test Output

Running `dotnet run faulty-geometry-test` produces:

```
Fault Count: 3
Error 1: swEdgeVerticesTouch
Error 2: swEdgeVerticesTouch
Error 3: swEdgeVerticesTouch
SUCCESS: Faulty geometry detected as expected.
```

## Creating Faulty Test Geometry

Corrupt exported STEP files to create reproducible test cases:

```csharp
// 1. Create and export valid geometry
IModelDoc2 doc = CreateValidCylinder();
string validStep = Path.Combine(Path.GetTempPath(), "valid_cyl.step");
int errors = 0, warnings = 0;
doc.Extension.SaveAs(validStep, (int)swSaveAsVersion_e.swSaveAsCurrentVersion,
    (int)swSaveAsOptions_e.swSaveAsOptions_Silent, null, ref errors, ref warnings);

// 2. Corrupt STEP file - make radius impossibly small (0.0001 instead of 0.01)
string content = File.ReadAllText(validStep);
Regex rx = new Regex(@"CYLINDRICAL_SURFACE\s*\([^\)]+,\s*([0-9\.\+\-E]+)\s*\)");
content = rx.Replace(content, match => match.Value.Replace(match.Groups[1].Value, "0.0001"), 1);

string faultyStep = validStep.Replace("valid_", "faulty_");
File.WriteAllText(faultyStep, content);

// 3. Import and detect faults
errors = 0;
doc = (IModelDoc2)swApp.LoadFile4(faultyStep, "r", null, ref errors);
// Use Check3 as shown above
```

## Common swFaultEntityErrorCode_e Values

- `swEdgeVerticesTouch` - Edge vertices are touching (degenerative edge)
- `swSmallEdge` - Edge below tolerance
- `swSmallFace` - Face below tolerance
- `swPoorlyDefinedCurve` - Invalid curve definition
- `swShortEdge` - Edge too short

## Verification

The code examples above were verified by creating a test that:
1. Created a valid cylinder with 0.01m radius
2. Exported to STEP
3. Corrupted the STEP file to use 0.0001m radius
4. Re-imported and successfully detected 3 faults with `swEdgeVerticesTouch`
