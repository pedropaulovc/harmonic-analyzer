//--------------------------------------------------------------
// SolidWorks C# Standalone Application: Sinusoidal Cam (Eccentric Cam)
//
// Description:
// Creates an eccentric cam that produces harmonic motion for a follower.
// Simple cylinder with off-center mounting hole and keyway.
// Displacement = eccentricity × sin(θ)
//
// Translated from: cad/sinusoidal-cam.kcl
//
// Units: SolidWorks API uses meters internally
//--------------------------------------------------------------

using System;
using System.Diagnostics;
using System.Runtime.InteropServices;
using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swconst;

namespace SinusoidalCamStandalone
{
    class Program
    {
        // ========================================
        // PARAMETERS (converted from inches to meters)
        // ========================================

        // Cam parameters (from parameters.kcl)
        private const double CAM_DIAMETER = 2.0 * 0.0254;      // 2.0 inches -> meters
        private const double CAM_THICKNESS = 0.4 * 0.0254;     // 0.4 inches -> meters

        // Shaft mounting parameters (from parameters.kcl)
        private const double SHAFT_DIAMETER = 0.375 * 0.0254;  // 3/8" -> meters
        private const double KEYWAY_WIDTH = 0.125 * 0.0254;    // 1/8" -> meters
        private const double KEYWAY_DEPTH = 0.06 * 0.0254;     // 0.06" -> meters

        // Eccentric cam geometry
        private const double ECCENTRICITY = 0.2 * 0.0254;      // 0.2 inches -> meters (amplitude of motion)

        // Calculated parameters
        private static double CAM_RADIUS => CAM_DIAMETER / 2.0;
        private static double SHAFT_RADIUS => SHAFT_DIAMETER / 2.0;

        // SolidWorks ProgID for COM connection
        private const string SOLIDWORKS_PROGID = "SldWorks.Application";

        static void Main(string[] args)
        {
            SldWorks swApp = null;

            try
            {
                Console.WriteLine("=== SolidWorks Sinusoidal Cam Generator ===");
                Console.WriteLine();

                // Validate parameters (assertions from KCL)
                ValidateParameters();

                // Connect to SolidWorks
                Console.WriteLine("Connecting to SolidWorks...");
                swApp = ConnectToSolidWorks();

                if (swApp == null)
                {
                    Console.WriteLine("ERROR: Could not connect to SolidWorks.");
                    Console.WriteLine("Please ensure SolidWorks is installed and try again.");
                    System.Environment.Exit(1);
                }

                Console.WriteLine($"Connected to SolidWorks {swApp.RevisionNumber()}");
                Console.WriteLine();

                // Print parameters
                PrintParameters();

                // Create the cam
                Console.WriteLine("Creating eccentric cam part...");
                Console.WriteLine();
                CreateEccentricCam(swApp);

                Console.WriteLine();
                Console.WriteLine("=== Cam creation complete! ===");
                Console.WriteLine("The part has been created in SolidWorks.");
                Console.WriteLine();
                Console.WriteLine("Press any key to exit...");
                Console.ReadKey();
            }
            catch (Exception ex)
            {
                Console.WriteLine($"ERROR: {ex.Message}");
                Console.WriteLine();
                Console.WriteLine("Stack trace:");
                Console.WriteLine(ex.StackTrace);
                Console.WriteLine();
                Console.WriteLine("Press any key to exit...");
                Console.ReadKey();
                System.Environment.Exit(1);
            }
            finally
            {
                // Release COM objects
                if (swApp != null)
                {
                    Marshal.ReleaseComObject(swApp);
                }
            }
        }

        /// <summary>
        /// Connects to a running instance of SolidWorks or starts a new one
        /// </summary>
        private static SldWorks ConnectToSolidWorks()
        {
            SldWorks swApp = null;

            try
            {
                // First, try to connect to a running instance
                Console.WriteLine("  Attempting to connect to running SolidWorks instance...");
                swApp = (SldWorks)Marshal.GetActiveObject(SOLIDWORKS_PROGID);
                Console.WriteLine("  Connected to existing SolidWorks instance.");
            }
            catch (COMException)
            {
                // If no instance is running, start a new one
                Console.WriteLine("  No running instance found. Starting SolidWorks...");
                Type swType = Type.GetTypeFromProgID(SOLIDWORKS_PROGID);
                if (swType != null)
                {
                    swApp = (SldWorks)Activator.CreateInstance(swType);
                    swApp.Visible = true;
                    Console.WriteLine("  SolidWorks started successfully.");
                }
            }

            return swApp;
        }

        /// <summary>
        /// Validates all cam parameters
        /// </summary>
        private static void ValidateParameters()
        {
            if (CAM_DIAMETER <= SHAFT_DIAMETER)
                throw new InvalidOperationException("Cam diameter must be larger than shaft");

            if (ECCENTRICITY <= 0 || ECCENTRICITY >= CAM_RADIUS)
                throw new InvalidOperationException("Eccentricity must be greater than 0 and less than cam radius");

            double minClearance = CAM_RADIUS - ECCENTRICITY - SHAFT_RADIUS;
            if (minClearance <= 0)
                throw new InvalidOperationException("Shaft hole too close to cam edge");

            if (CAM_THICKNESS <= 0)
                throw new InvalidOperationException("Cam thickness must be positive");

            if (KEYWAY_WIDTH >= SHAFT_DIAMETER)
                throw new InvalidOperationException("Keyway too wide for shaft");
        }

        /// <summary>
        /// Prints all cam parameters to console
        /// </summary>
        private static void PrintParameters()
        {
            double minClearance = CAM_RADIUS - ECCENTRICITY - SHAFT_RADIUS;

            Console.WriteLine("Cam Parameters:");
            Console.WriteLine($"  Cam Diameter:       {CAM_DIAMETER * 1000:F3} mm ({CAM_DIAMETER / 0.0254:F3} in)");
            Console.WriteLine($"  Cam Thickness:      {CAM_THICKNESS * 1000:F3} mm ({CAM_THICKNESS / 0.0254:F3} in)");
            Console.WriteLine($"  Eccentricity:       {ECCENTRICITY * 1000:F3} mm ({ECCENTRICITY / 0.0254:F3} in)");
            Console.WriteLine($"  Shaft Diameter:     {SHAFT_DIAMETER * 1000:F3} mm ({SHAFT_DIAMETER / 0.0254:F3} in)");
            Console.WriteLine($"  Keyway Width:       {KEYWAY_WIDTH * 1000:F3} mm ({KEYWAY_WIDTH / 0.0254:F3} in)");
            Console.WriteLine($"  Keyway Depth:       {KEYWAY_DEPTH * 1000:F3} mm ({KEYWAY_DEPTH / 0.0254:F3} in)");
            Console.WriteLine($"  Min Edge Clearance: {minClearance * 1000:F3} mm ({minClearance / 0.0254:F3} in)");
            Console.WriteLine();
        }

        /// <summary>
        /// Creates the eccentric cam part in SolidWorks
        /// </summary>
        private static void CreateEccentricCam(SldWorks swApp)
        {
            ModelDoc2 swModel = null;
            ModelDocExtension swModelExt = null;
            SketchManager swSketchMgr = null;
            FeatureManager swFeatureMgr = null;
            bool status = false;

            try
            {
                // Step 1: Create new part document
                Console.WriteLine("Step 1: Creating new part document...");

                // Use default template (pass empty string to use default)
                string defaultTemplate = swApp.GetUserPreferenceStringValue(
                    (int)swUserPreferenceStringValue_e.swDefaultTemplatePart);

                if (string.IsNullOrEmpty(defaultTemplate))
                {
                    // Fallback to typical location
                    defaultTemplate = "C:\\ProgramData\\SolidWorks\\SOLIDWORKS 2016\\templates\\Part.prtdot";
                }

                swModel = (ModelDoc2)swApp.NewDocument(defaultTemplate, 0, 0, 0);

                if (swModel == null)
                    throw new InvalidOperationException("Failed to create new part document");

                swModelExt = (ModelDocExtension)swModel.Extension;
                swSketchMgr = (SketchManager)swModel.SketchManager;
                swFeatureMgr = (FeatureManager)swModel.FeatureManager;

                // Step 2: Create cam body (circular disk)
                Console.WriteLine("Step 2: Creating cam body sketch...");

                // Select Front plane (equivalent to XY plane in KCL)
                status = swModelExt.SelectByID2(
                    Name: "Front Plane",
                    Type: "PLANE",
                    X: 0,
                    Y: 0,
                    Z: 0,
                    Append: false,
                    Mark: 0,
                    Callout: null,
                    SelectOption: (int)swSelectOption_e.swSelectOptionDefault);

                if (!status)
                    throw new InvalidOperationException("Failed to select Front plane");

                // Insert sketch on Front plane
                swSketchMgr.InsertSketch(UpdateEditRebuild: true);

                // Enable AddToDB for better performance
                swSketchMgr.AddToDB = true;
                swSketchMgr.DisplayWhenAdded = false;

                // Create outer cam circle centered at origin (0, 0, 0)
                SketchSegment camCircle = swSketchMgr.CreateCircle(
                    XC: 0.0,
                    YC: 0.0,
                    Zc: 0.0,
                    Xp: CAM_RADIUS,  // Point on circle
                    Yp: 0.0,
                    Zp: 0.0);

                // Restore normal display mode
                swSketchMgr.AddToDB = false;
                swSketchMgr.DisplayWhenAdded = true;

                // Exit sketch
                swSketchMgr.InsertSketch(UpdateEditRebuild: true);

                // Step 3: Extrude cam body
                Console.WriteLine("Step 3: Extruding cam body...");

                // Select the sketch we just created
                status = swModelExt.SelectByID2(
                    Name: "Sketch1",
                    Type: "SKETCH",
                    X: 0,
                    Y: 0,
                    Z: 0,
                    Append: false,
                    Mark: 0,
                    Callout: null,
                    SelectOption: (int)swSelectOption_e.swSelectOptionDefault);

                // Create boss extrusion
                Feature camBodyFeature = swFeatureMgr.FeatureExtrusion3(
                    Sd: true,                          // Single-ended extrusion
                    Flip: false,                       // Don't flip direction
                    Dir: false,                        // Use default direction (normal to sketch)
                    T1: (int)swEndConditions_e.swEndCondBlind,  // Blind extrusion
                    T2: (int)swEndConditions_e.swEndCondBlind,  // (not used for single-ended)
                    D1: CAM_THICKNESS,                 // Extrusion depth
                    D2: 0.0,                           // (not used for single-ended)
                    Dchk1: false,                      // No draft
                    Dchk2: false,                      // No draft
                    Ddir1: false,                      // (draft not enabled)
                    Ddir2: false,                      // (draft not enabled)
                    Dang1: 0.0,                        // (draft not enabled)
                    Dang2: 0.0,                        // (draft not enabled)
                    OffsetReverse1: false,             // (not using offset)
                    OffsetReverse2: false,             // (not using offset)
                    TranslateSurface1: false,          // (not using offset)
                    TranslateSurface2: false,          // (not using offset)
                    Merge: true,                       // Merge result
                    UseFeatScope: false,               // Affect all bodies
                    UseAutoSelect: true,               // Auto-select all bodies
                    T0: (int)swStartConditions_e.swStartSketchPlane,  // Start from sketch plane
                    StartOffset: 0.0,                  // (not using offset)
                    FlipStartOffset: false);           // (not using offset)

                if (camBodyFeature == null)
                    throw new InvalidOperationException("Failed to create cam body extrusion");

                swModel.ClearSelection2(true);

                // Step 4: Create eccentric shaft hole with keyway
                Console.WriteLine("Step 4: Creating eccentric shaft hole with keyway...");

                // Select the front plane again for the hole sketch
                status = swModelExt.SelectByID2(
                    Name: "Front Plane",
                    Type: "PLANE",
                    X: 0,
                    Y: 0,
                    Z: 0,
                    Append: false,
                    Mark: 0,
                    Callout: null,
                    SelectOption: (int)swSelectOption_e.swSelectOptionDefault);

                // Insert sketch for hole
                swSketchMgr.InsertSketch(UpdateEditRebuild: true);

                // Enable AddToDB for better performance
                swSketchMgr.AddToDB = true;
                swSketchMgr.DisplayWhenAdded = false;

                // Create shaft hole circle, offset by ECCENTRICITY
                // The hole is positioned at [eccentricity, 0] to create eccentric motion
                SketchSegment holeCircle = swSketchMgr.CreateCircle(
                    XC: ECCENTRICITY,   // Offset in X direction
                    YC: 0.0,
                    Zc: 0.0,
                    Xp: ECCENTRICITY + SHAFT_RADIUS,  // Point on circle
                    Yp: 0.0,
                    Zp: 0.0);

                // Create keyway profile
                // The keyway is a rectangular notch that extends from the shaft hole
                // Calculate start angle for the keyway (where it meets the shaft circle)
                double startAngle = Math.Asin(KEYWAY_WIDTH / 2.0 / SHAFT_RADIUS);

                // Calculate keyway profile points
                double keywayStartX = ECCENTRICITY + SHAFT_RADIUS * Math.Cos(startAngle);
                double keywayStartY = SHAFT_RADIUS * Math.Sin(startAngle);

                // Draw keyway profile as connected lines
                // Top horizontal line extending outward
                SketchSegment line1 = swSketchMgr.CreateLine(
                    X1: keywayStartX,
                    Y1: keywayStartY,
                    Z1: 0.0,
                    X2: keywayStartX + KEYWAY_DEPTH,
                    Y2: keywayStartY,
                    Z2: 0.0);

                // Vertical line going down
                SketchSegment line2 = swSketchMgr.CreateLine(
                    X1: keywayStartX + KEYWAY_DEPTH,
                    Y1: keywayStartY,
                    Z1: 0.0,
                    X2: keywayStartX + KEYWAY_DEPTH,
                    Y2: -keywayStartY,
                    Z2: 0.0);

                // Bottom horizontal line going back
                SketchSegment line3 = swSketchMgr.CreateLine(
                    X1: keywayStartX + KEYWAY_DEPTH,
                    Y1: -keywayStartY,
                    Z1: 0.0,
                    X2: keywayStartX,
                    Y2: -keywayStartY,
                    Z2: 0.0);

                // Create arcs to connect the keyway back to the shaft hole
                // Arc 1: from bottom of keyway to left side of shaft
                double arc1StartX = keywayStartX;
                double arc1StartY = -keywayStartY;
                double arc1EndX = ECCENTRICITY - SHAFT_RADIUS;
                double arc1EndY = 0.0;

                SketchArc arc1 = (SketchArc)swSketchMgr.CreateArc(
                    XC: ECCENTRICITY,
                    YC: 0.0,
                    Zc: 0.0,
                    X1: arc1StartX,
                    Y1: arc1StartY,
                    Z1: 0.0,
                    X2: arc1EndX,
                    Y2: arc1EndY,
                    Z2: 0.0,
                    Direction: 1);  // Counter-clockwise

                // Arc 2: from left side of shaft to top of keyway
                SketchArc arc2 = (SketchArc)swSketchMgr.CreateArc(
                    XC: ECCENTRICITY,
                    YC: 0.0,
                    Zc: 0.0,
                    X1: arc1EndX,
                    Y1: arc1EndY,
                    Z1: 0.0,
                    X2: keywayStartX,
                    Y2: keywayStartY,
                    Z2: 0.0,
                    Direction: 1);  // Counter-clockwise

                // Restore normal display mode and redraw
                swSketchMgr.AddToDB = false;
                swSketchMgr.DisplayWhenAdded = true;

                // Exit sketch
                swSketchMgr.InsertSketch(UpdateEditRebuild: true);

                // Step 5: Cut extrude the hole through all
                Console.WriteLine("Step 5: Cutting shaft hole through cam body...");

                // Select the hole sketch
                status = swModelExt.SelectByID2(
                    Name: "Sketch2",
                    Type: "SKETCH",
                    X: 0,
                    Y: 0,
                    Z: 0,
                    Append: false,
                    Mark: 0,
                    Callout: null,
                    SelectOption: (int)swSelectOption_e.swSelectOptionDefault);

                // Create cut extrusion through all
                Feature cutFeature = swFeatureMgr.FeatureCut4(
                    Sd: true,                          // Single-ended cut
                    Flip: false,                       // Don't flip
                    Dir: false,                        // Use default direction
                    T1: (int)swEndConditions_e.swEndCondThroughAll,  // Through all
                    T2: (int)swEndConditions_e.swEndCondBlind,       // (not used)
                    D1: 0.0,                           // (through all - depth not needed)
                    D2: 0.0,                           // (not used)
                    Dchk1: false,                      // No draft
                    Dchk2: false,                      // No draft
                    Ddir1: false,                      // (draft not enabled)
                    Ddir2: false,                      // (draft not enabled)
                    Dang1: 0.0,                        // (draft not enabled)
                    Dang2: 0.0,                        // (draft not enabled)
                    OffsetReverse1: false,             // (not using offset)
                    OffsetReverse2: false,             // (not using offset)
                    TranslateSurface1: false,          // (not using offset)
                    TranslateSurface2: false,          // (not using offset)
                    NormalCut: false,                  // Not sheet metal
                    UseFeatScope: false,               // Affect all bodies
                    UseAutoSelect: true,               // Auto-select all bodies
                    AssemblyFeatureScope: false,       // Not an assembly feature
                    AutoSelectComponents: false,       // Not an assembly feature
                    PropagateFeatureToParts: false,    // Not an assembly feature
                    T0: (int)swStartConditions_e.swStartSketchPlane,  // Start from sketch plane
                    StartOffset: 0.0,                  // (not using offset)
                    FlipStartOffset: false,            // (not using offset)
                    OptimizeGeometry: false);          // Not sheet metal

                if (cutFeature == null)
                    throw new InvalidOperationException("Failed to create cut feature for shaft hole");

                swModel.ClearSelection2(true);

                // Zoom to fit
                swModel.ViewZoomtofit2();

                Console.WriteLine();
                Console.WriteLine("Cam created successfully!");
                Console.WriteLine($"  - Outer diameter: {CAM_DIAMETER * 1000:F3} mm");
                Console.WriteLine($"  - Thickness: {CAM_THICKNESS * 1000:F3} mm");
                Console.WriteLine($"  - Shaft hole offset: {ECCENTRICITY * 1000:F3} mm");
                Console.WriteLine($"  - Shaft diameter: {SHAFT_DIAMETER * 1000:F3} mm");
                Console.WriteLine($"  - Keyway: {KEYWAY_WIDTH * 1000:F3} mm × {KEYWAY_DEPTH * 1000:F3} mm");
            }
            catch (Exception ex)
            {
                throw new InvalidOperationException($"Failed to create cam: {ex.Message}", ex);
            }
        }
    }
}
