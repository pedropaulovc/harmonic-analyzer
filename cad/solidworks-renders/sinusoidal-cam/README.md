# Sinusoidal Cam - SolidWorks C# Implementation

## Overview

This directory contains a SolidWorks C# macro that creates an eccentric cam (sinusoidal cam) part. The cam produces harmonic motion for a follower, where the displacement follows a sinusoidal pattern: `Displacement = eccentricity × sin(θ)`.

## Translation Source

This code is translated from the KCL (KittyCAD Language) model at:
- **Source**: [cad/sinusoidal-cam.kcl](../../sinusoidal-cam.kcl)
- **Parameters**: [cad/parameters.kcl](../../parameters.kcl)

## Cam Specifications

### Geometry Parameters
- **Cam Diameter**: 2.0 inches (50.8 mm)
- **Cam Thickness**: 0.4 inches (10.16 mm)
- **Eccentricity**: 0.2 inches (5.08 mm) - offset of shaft hole from center
- **Shaft Diameter**: 0.375 inches (9.525 mm) - 3/8" mounting hole
- **Keyway Width**: 0.125 inches (3.175 mm) - 1/8"
- **Keyway Depth**: 0.06 inches (1.524 mm)

### Features
- Simple cylindrical cam body
- Off-center (eccentric) mounting hole
- Keyway for shaft keying
- Produces sinusoidal/harmonic motion when rotated

## Files

- **Program.cs**: Standalone executable main program
- **SinusoidalCam.cs**: Original SolidWorks C# macro file (for VSTA use)
- **SinusoidalCam.csproj**: .NET project file
- **build.bat**: Build script for creating the executable
- **run.bat**: Run script for executing the compiled program
- **README.md**: This documentation file

## How to Use

### ⭐ Option 1: Run as Standalone Executable (Recommended)

This is the **easiest method** - just build and run!

**Prerequisites:**
- .NET Framework 4.8 or later
- SolidWorks installed (will connect to running instance or start new one)

**Build Steps:**
```batch
# Navigate to this directory
cd cad\solidworks-renders\sinusoidal-cam

# Build the project
build.bat
```

**Run Steps:**
```batch
# Run the executable
run.bat
```

**Manual Build (if you prefer):**
```batch
dotnet build -c Release
bin\Release\net48\SinusoidalCam.exe
```

**What happens when you run it:**
1. The program will connect to a running SolidWorks instance or start a new one
2. It validates all cam parameters
3. Creates a new part document
4. Generates the complete cam geometry
5. Displays progress in the console window
6. The finished cam appears in SolidWorks

### Option 2: Run as a VSTA Macro in SolidWorks

1. Open SolidWorks
2. Go to **Tools** > **Macro** > **New...**
3. Select **C# (VSTA)** as the macro type
4. Replace the default code with the contents of `SinusoidalCam.cs`
5. Click **Run** (or press F5)

### Option 3: Copy Code to Existing Macro

1. Open your existing SolidWorks C# macro project
2. Copy the contents of `SinusoidalCam.cs` into your macro
3. Ensure you have the required `using` statements at the top
4. Run the `Main()` method

### Option 4: Use in a SolidWorks Add-in

The code can be integrated into a SolidWorks add-in by:
1. Copying the `CreateEccentricCam()` method from `Program.cs`
2. Ensuring you have access to the `swApp` (SldWorks) object
3. Calling the method from your add-in code

## Code Structure

### Standalone Executable (Program.cs)

The standalone version includes:

1. **ConnectToSolidWorks()**: Connects to running SolidWorks or starts a new instance via COM
   - Uses `Marshal.GetActiveObject()` for existing instances
   - Uses `Activator.CreateInstance()` to start new instance if needed

2. **ValidateParameters()**: Validates all cam dimensions before creation

3. **PrintParameters()**: Displays all cam specifications in console

4. **CreateEccentricCam()**: Main creation logic with step-by-step console output

5. **Proper COM Cleanup**: Uses `Marshal.ReleaseComObject()` to release COM references

### Macro Version (SinusoidalCam.cs)

The macro version follows the traditional VSTA macro structure:

1. **Parameters Section**: All dimensional parameters with unit conversions from inches to meters
   - SolidWorks API uses meters internally
   - Includes parameter validation (assertions from original KCL)

2. **Main() Method**: Entry point that validates parameters and calls the creation method

3. **CreateEccentricCam() Method**: Creates the cam part with these steps:
   - Creates a new part document
   - Sketches the circular cam body on the Front plane
   - Extrudes the cam body to the specified thickness
   - Sketches the eccentric shaft hole with keyway
   - Cuts the hole through the cam body

### Key SolidWorks API Features Used

- **ISketchManager**: For creating sketches, circles, lines, and arcs
- **IFeatureManager**: For creating extrusions and cuts
- **IModelDocExtension.SelectByID2**: For selecting planes and sketches
- **Named Parameters**: Used throughout for code clarity and readability
- **COM Interop**: Standalone version uses proper COM object lifecycle management

## Technical Notes

### SolidWorks SDK References

The standalone executable references the SolidWorks Interop assemblies from:
```
C:\Program Files\Dassault Systemes\SOLIDWORKS 3DEXPERIENCE\SOLIDWORKS\api\redist\
```

Required DLLs:
- **SolidWorks.Interop.sldworks.dll** - Main SolidWorks API
- **SolidWorks.Interop.swconst.dll** - Constants and enumerations

These paths are configured in `SinusoidalCam.csproj` and should work with standard SolidWorks installations. If your SolidWorks is installed in a different location, update the `<HintPath>` elements in the project file.

### Unit Conversion
All dimensions are converted from inches to meters using the conversion factor `0.0254 m/inch`, since the SolidWorks API requires all dimensions in meters.

### Keyway Geometry
The keyway is created as a rectangular notch extending from the shaft hole circle. The profile consists of:
- Two horizontal lines (top and bottom of keyway)
- One vertical line (outer edge of keyway)
- Two arcs connecting back to the shaft circle

### Eccentricity
The shaft hole is offset by the eccentricity value (0.2 inches) in the X direction. When the cam rotates, this creates harmonic motion in any follower riding on the cam's outer diameter.

## Parameter Validation

The code includes safety checks (from the original KCL model):
- ✅ Cam diameter must be larger than shaft diameter
- ✅ Eccentricity must be positive and less than cam radius
- ✅ Shaft hole must not be too close to cam edge
- ✅ Cam thickness must be positive
- ✅ Keyway width must be less than shaft diameter

## Example Output

When run, the macro will:
1. Create a new SolidWorks part file
2. Generate the cam geometry with all features
3. Display debug information in the Immediate window:
   ```
   === Creating Sinusoidal Cam (Eccentric Cam) ===
   Cam Diameter: 50.800 mm
   Cam Thickness: 10.160 mm
   Eccentricity: 5.080 mm
   Shaft Diameter: 9.525 mm
   Minimum Edge Clearance: 15.795 mm
   Creating new part document...
   Creating cam body sketch...
   Extruding cam body...
   Creating shaft hole with keyway...
   Cutting shaft hole through cam body...
   Cam body created successfully!
   === Cam creation complete! ===
   ```

## Troubleshooting

### Common Issues - Standalone Executable

1. **"Could not connect to SolidWorks"**
   - Ensure SolidWorks is installed
   - Try starting SolidWorks manually first, then run the executable
   - Check that you have proper permissions to launch SolidWorks

2. **Build Errors - Assembly References**
   - Verify SolidWorks SDK DLLs exist at: `C:\Program Files\Dassault Systemes\SOLIDWORKS 3DEXPERIENCE\SOLIDWORKS\api\redist\`
   - If your SolidWorks is installed elsewhere, update the paths in `SinusoidalCam.csproj`
   - Ensure .NET Framework 4.8 is installed

3. **"Failed to create new part document"**
   - The program will try to use your default part template
   - If this fails, set up a default template in SolidWorks: **Tools > Options > File Locations > Document Templates**

4. **COM/Interop Errors**
   - Make sure SolidWorks is registered properly (reinstall if needed)
   - Run the executable as Administrator if permission issues occur
   - Check Windows Event Viewer for detailed COM error messages

### Common Issues - Macro Version

1. **"Failed to create new part document"**
   - Update the template path in the code to match your SolidWorks installation
   - Check that the Part.prtdot template exists

2. **"Failed to select Front plane"**
   - Ensure SolidWorks is running and visible
   - Verify that a new part document was created successfully

3. **Feature creation fails**
   - Check the Immediate/Debug window for error messages
   - Verify all parameters are valid (run parameter validation)
   - Ensure sketches are properly closed before extrusion

## See Also

- Original KCL model: [cad/sinusoidal-cam.kcl](../../sinusoidal-cam.kcl)
- SolidWorks API Documentation: Included in SolidWorks installation
- Harmonic Analyzer project documentation

## License

Part of the Harmonic Analyzer project.
