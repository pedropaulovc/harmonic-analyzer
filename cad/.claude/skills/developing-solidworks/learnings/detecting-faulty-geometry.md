---
title: Detecting Faulty Geometry in Imported Bodies
category: Body Validation
tags: [validation, import, fault-detection, IBody2, IFaultEntity, swFaultEntityErrorCode_e]
date: 2025-11-23
---

# Detecting Faulty Geometry in Imported Bodies

## Problem

After importing STEP or other CAD files, you need to verify that imported bodies contain valid geometry. Invalid geometry causes downstream failures in features and operations.

## Solution: Use IBody2.Check3

**`IBody2.Check3` returns `IFaultEntity` with specific error codes for each geometry fault.**

```csharp
IPartDoc part = (IPartDoc)doc;
object[] bodies = (object[])part.GetBodies2((int)swBodyType_e.swSolidBody, false);

foreach (IBody2 body in bodies)
{
    IFaultEntity fault = body.Check3;

    if (fault != null && fault.Count > 0)
    {
        Console.WriteLine($"Found {fault.Count} faults:");

        for (int i = 0; i < fault.Count; i++)
        {
            swFaultEntityErrorCode_e errorCode = (swFaultEntityErrorCode_e)fault.get_ErrorCode(i);
            Console.WriteLine($"  Fault {i + 1}: {errorCode}");
        }
    }
}
```

## Creating Test Cases

To test fault detection, corrupt exported geometry and re-import:

```csharp
// 1. Create valid geometry and export
IModelDoc2 doc = CreateValidPart();
string validStep = ExportToStep(doc, "valid.step");

// 2. Corrupt STEP file (e.g., make radius impossibly small)
string content = File.ReadAllText(validStep);
Regex rx = new Regex(@"CYLINDRICAL_SURFACE\s*\([^\)]+,\s*([0-9\.\+\-E]+)\s*\)");
content = rx.Replace(content, match => match.Value.Replace(match.Groups[1].Value, "0.0001"), 1);
File.WriteAllText("faulty.step", content);

// 3. Import and verify fault exists
int errors = 0;
doc = (IModelDoc2)swApp.LoadFile4("faulty.step", "r", null, ref errors);
// Check for faults as shown above
```

## Common Error Codes

- `swFaultEntityErrorCode_SmallEdge` - Edge below tolerance
- `swFaultEntityErrorCode_SmallFace` - Face below tolerance
- `swFaultEntityErrorCode_PoorlyDefinedCurve` - Invalid curve definition
- `swFaultEntityErrorCode_ShortEdge` - Edge too short

## Test Program

Run the test with: `dotnet run faulty-geometry-test`

See: `solidworks-renders/FaultyGeometryTest.cs`
