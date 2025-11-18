// SinusoidalCamGenerator.cs
// Generates an eccentric cam for harmonic motion in SolidWorks
// This cam produces displacement = eccentricity × sin(θ) for a follower

using System;
using System.Runtime.InteropServices;
using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swconst;

namespace HarmonicAnalyzer.CAD
{
    /// <summary>
    /// Creates a sinusoidal cam (eccentric cam) in SolidWorks.
    /// The cam consists of a circular disk with an off-center shaft hole that includes a keyway.
    /// </summary>
    public class SinusoidalCamGenerator
    {
        // Design Parameters (all dimensions in inches)
        private const double CAM_DIAMETER = 2.0;           // Outer diameter of cam disk
        private const double CAM_THICKNESS = 0.4;          // Thickness of cam disk
        private const double SHAFT_DIAMETER = 0.375;       // Mounting hole diameter (3/8")
        private const double ECCENTRICITY = 0.2;           // Offset from center (amplitude of motion)
        private const double KEYWAY_WIDTH = 0.125;         // Keyway width (1/8")
        private const double KEYWAY_DEPTH = 0.06;          // Keyway depth from shaft surface

        // Calculated parameters
        private static double CamRadius => CAM_DIAMETER / 2.0;
        private static double ShaftRadius => SHAFT_DIAMETER / 2.0;

        private SldWorks swApp;
        private ModelDoc2 swModel;
        private SketchManager swSketchMgr;
        private FeatureManager swFeatureMgr;
        private SelectionMgr swSelectionMgr;

        /// <summary>
        /// Main entry point for the program.
        /// </summary>
        public static void Main(string[] args)
        {
            var generator = new SinusoidalCamGenerator();

            try
            {
                generator.ConnectToSolidWorks();
                generator.ValidateParameters();
                generator.CreateCamPart();
                generator.SavePart();

                Console.WriteLine("Sinusoidal cam created successfully!");
            }
            catch (Exception ex)
            {
                Console.WriteLine($"Error: {ex.Message}");
                Console.WriteLine($"Stack trace: {ex.StackTrace}");
            }
            finally
            {
                // Keep SolidWorks open for inspection
                Console.WriteLine("\nPress any key to exit...");
                Console.ReadKey();
            }
        }

        /// <summary>
        /// Connects to a running instance of SolidWorks or starts a new one.
        /// </summary>
        private void ConnectToSolidWorks()
        {
            Console.WriteLine("Connecting to SolidWorks...");

            // Try to get running instance, or create new one
            try
            {
                swApp = (SldWorks)Marshal.GetActiveObject("SldWorks.Application");
            }
            catch
            {
                // No running instance, create new one
                Type swType = Type.GetTypeFromProgID("SldWorks.Application");
                swApp = (SldWorks)Activator.CreateInstance(swType);
            }

            if (swApp == null)
            {
                throw new Exception("Failed to connect to SolidWorks");
            }

            // Make SolidWorks visible
            swApp.Visible = true;

            Console.WriteLine($"Connected to SolidWorks {swApp.RevisionNumber()}");
        }

        /// <summary>
        /// Validates design parameters to ensure they produce a valid geometry.
        /// </summary>
        private void ValidateParameters()
        {
            Console.WriteLine("\nValidating design parameters...");

            // Cam diameter must be larger than shaft
            if (CAM_DIAMETER <= SHAFT_DIAMETER)
            {
                throw new ArgumentException("Cam diameter must be larger than shaft diameter");
            }

            // Eccentricity must be positive and less than cam radius
            if (ECCENTRICITY <= 0 || ECCENTRICITY >= CamRadius)
            {
                throw new ArgumentException("Eccentricity must be between 0 and cam radius");
            }

            // Check minimum clearance between shaft hole edge and cam edge
            double minClearance = CamRadius - ECCENTRICITY - ShaftRadius;
            if (minClearance <= 0)
            {
                throw new ArgumentException("Shaft hole too close to cam edge");
            }

            // Cam thickness must be positive
            if (CAM_THICKNESS <= 0)
            {
                throw new ArgumentException("Cam thickness must be positive");
            }

            // Keyway must fit within shaft
            if (KEYWAY_WIDTH >= SHAFT_DIAMETER)
            {
                throw new ArgumentException("Keyway too wide for shaft");
            }

            Console.WriteLine("  Cam diameter: {0:F3}\"", CAM_DIAMETER);
            Console.WriteLine("  Cam thickness: {0:F3}\"", CAM_THICKNESS);
            Console.WriteLine("  Shaft diameter: {0:F3}\"", SHAFT_DIAMETER);
            Console.WriteLine("  Eccentricity: {0:F3}\"", ECCENTRICITY);
            Console.WriteLine("  Keyway: {0:F3}\" × {0:F3}\"", KEYWAY_WIDTH, KEYWAY_DEPTH);
            Console.WriteLine("  Minimum edge clearance: {0:F3}\"", minClearance);
            Console.WriteLine("  Parameters validated successfully.");
        }

        /// <summary>
        /// Creates the complete cam part in SolidWorks.
        /// </summary>
        private void CreateCamPart()
        {
            Console.WriteLine("\nCreating cam part...");

            // Create new part document
            swModel = (ModelDoc2)swApp.NewDocument(
                defaultTemplate: swApp.GetUserPreferenceStringValue((int)swUserPreferenceStringValue_e.swDefaultTemplatePart),
                paperSize: 0,
                width: 0,
                height: 0);

            if (swModel == null)
            {
                throw new Exception("Failed to create new part document");
            }

            // Set units to IPS (Inch, Pound, Second)
            swModel.Extension.SetUserPreferenceInteger(
                userPreference: (int)swUserPreferenceIntegerValue_e.swUnitsLinear,
                option: (int)swUserPreferenceOption_e.swDetailingNoOptionSpecified,
                value: (int)swLengthUnit_e.swINCHES);

            // Get managers
            swSketchMgr = swModel.SketchManager;
            swFeatureMgr = swModel.FeatureManager;
            swSelectionMgr = swModel.SelectionManager;

            // Build the cam geometry
            CreateCamBodySketch();
            ExtrudeCamBody();

            Console.WriteLine("  Cam part created successfully.");
        }

        /// <summary>
        /// Creates the 2D sketch for the cam body (circular disk with eccentric hole and keyway).
        /// This combines the outer circle with the subtracted hole profile.
        /// </summary>
        private void CreateCamBodySketch()
        {
            Console.WriteLine("  Creating cam body sketch...");

            // Select Front plane for sketching
            bool result = swModel.Extension.SelectByID2(
                name: "Front Plane",
                type: "PLANE",
                x: 0, y: 0, z: 0,
                append: false,
                mark: 0,
                callout: null,
                selectOption: 0);

            if (!result)
            {
                throw new Exception("Failed to select Front Plane");
            }

            // Start sketch on Front plane
            swSketchMgr.InsertSketch(collapseFeatureManager: true);

            // Create outer cam circle (centered at origin)
            CreateCamCircle();

            // Create eccentric shaft hole with keyway
            CreateShaftHoleWithKeyway();

            // Exit sketch
            swSketchMgr.InsertSketch(collapseFeatureManager: true);

            Console.WriteLine("    Sketch created with cam body and eccentric hole.");
        }

        /// <summary>
        /// Creates the outer circular boundary of the cam.
        /// </summary>
        private void CreateCamCircle()
        {
            // Draw circle centered at origin
            SketchSegment circle = swSketchMgr.CreateCircleByRadius(
                x: 0,
                y: 0,
                z: 0,
                radius: CamRadius);

            if (circle == null)
            {
                throw new Exception("Failed to create cam circle");
            }

            Console.WriteLine("    Created cam circle: radius = {0:F3}\"", CamRadius);
        }

        /// <summary>
        /// Creates the eccentric shaft hole with integrated keyway.
        /// The hole is offset by the eccentricity value to produce harmonic motion.
        ///
        /// The keyway profile consists of:
        /// 1. Horizontal line (keyway depth extending outward)
        /// 2. Vertical line down (keyway width)
        /// 3. Horizontal line back to shaft edge
        /// 4. Arc around bottom half of shaft
        /// 5. Arc around top half of shaft
        /// 6. Close profile
        /// </summary>
        private void CreateShaftHoleWithKeyway()
        {
            Console.WriteLine("    Creating eccentric shaft hole with keyway...");

            // Calculate start angle for keyway (where keyway meets shaft circle)
            // startAngle = asin(keywayWidth / 2 / shaftRadius)
            double startAngleRad = Math.Asin((KEYWAY_WIDTH / 2.0) / ShaftRadius);
            double startAngleDeg = startAngleRad * 180.0 / Math.PI;

            // Calculate starting point of keyway profile
            // Point is at: [eccentricity + shaftRadius * cos(startAngle), shaftRadius * sin(startAngle)]
            double startX = ECCENTRICITY + ShaftRadius * Math.Cos(startAngleRad);
            double startY = ShaftRadius * Math.Sin(startAngleRad);

            Console.WriteLine("    Shaft hole center offset: [{0:F3}\", 0]", ECCENTRICITY);
            Console.WriteLine("    Keyway start angle: {0:F2}°", startAngleDeg);
            Console.WriteLine("    Profile start point: [{0:F4}\", {1:F4}\"]", startX, startY);

            // Build keyway profile using sketch segments
            // Note: All coordinates are absolute in sketch space

            // Point 1: Start of profile (top-right of keyway)
            double x1 = startX;
            double y1 = startY;

            // Point 2: After horizontal line (keyway depth)
            double x2 = x1 + KEYWAY_DEPTH;
            double y2 = y1;

            // Point 3: After vertical line down (keyway width)
            double x3 = x2;
            double y3 = y2 - KEYWAY_WIDTH;

            // Point 4: After horizontal line back (back to shaft edge)
            double x4 = x3 - KEYWAY_DEPTH;
            double y4 = y3;

            // Now we need to create the arcs around the shaft hole
            // The shaft is centered at [ECCENTRICITY, 0] with radius ShaftRadius

            // Create line segments for keyway
            SketchSegment line1 = swSketchMgr.CreateLine(
                x1: x1, y1: y1, z1: 0,
                x2: x2, y2: y2, z2: 0);

            SketchSegment line2 = swSketchMgr.CreateLine(
                x1: x2, y1: y2, z1: 0,
                x2: x3, y2: y3, z2: 0);

            SketchSegment line3 = swSketchMgr.CreateLine(
                x1: x3, y1: y3, z1: 0,
                x2: x4, y2: y4, z2: 0);

            // Create arc segments around the shaft
            // Arc 1: From bottom of keyway around to 180° (bottom of shaft)
            // Arc 2: From 180° around to top of keyway

            // For SolidWorks arcs, we need center point and endpoints
            double centerX = ECCENTRICITY;
            double centerY = 0;

            // Bottom arc: from point 4 to 180° position
            double bottomArcEndX = ECCENTRICITY - ShaftRadius;  // 180° position
            double bottomArcEndY = 0;

            SketchSegment arc1 = swSketchMgr.CreateArc(
                centerX: centerX,
                centerY: centerY,
                centerZ: 0,
                startX: x4,
                startY: y4,
                startZ: 0,
                endX: bottomArcEndX,
                endY: bottomArcEndY,
                endZ: 0,
                direction: 1);  // 1 = clockwise, -1 = counterclockwise

            // Top arc: from 180° position back to start point
            SketchSegment arc2 = swSketchMgr.CreateArc(
                centerX: centerX,
                centerY: centerY,
                centerZ: 0,
                startX: bottomArcEndX,
                startY: bottomArcEndY,
                startZ: 0,
                endX: x1,
                endY: y1,
                endZ: 0,
                direction: 1);  // 1 = clockwise

            // Close the profile by connecting end to start
            SketchSegment closeLine = swSketchMgr.CreateLine(
                x1: x1, y1: y1, z1: 0,
                x2: x1, y2: y1, z2: 0);  // Zero-length line to close

            if (line1 == null || line2 == null || line3 == null || arc1 == null || arc2 == null)
            {
                throw new Exception("Failed to create shaft hole keyway profile segments");
            }

            Console.WriteLine("    Eccentric shaft hole with keyway created.");
        }

        /// <summary>
        /// Extrudes the cam body sketch to create the 3D solid.
        /// </summary>
        private void ExtrudeCamBody()
        {
            Console.WriteLine("  Extruding cam body...");

            // Select the cam body sketch for extrusion
            // We need to select the outer circle as the base contour
            bool result = swModel.Extension.SelectByID2(
                name: "Arc1",  // The outer cam circle
                type: "SKETCHSEGMENT",
                x: 0, y: 0, z: 0,
                append: false,
                mark: 0,
                callout: null,
                selectOption: 0);

            if (!result)
            {
                // Try selecting the sketch instead
                result = swModel.Extension.SelectByID2(
                    name: "Sketch1",
                    type: "SKETCH",
                    x: 0, y: 0, z: 0,
                    append: false,
                    mark: 0,
                    callout: null,
                    selectOption: 0);
            }

            // Create extrude feature
            Feature extrudeFeature = swFeatureMgr.FeatureExtrusion3(
                propagate: true,
                flipDirection: false,
                directionOption: (int)swEndConditions_e.swEndCondBlind,
                endConditionType: (int)swEndConditions_e.swEndCondBlind,
                depth: CAM_THICKNESS,
                offSetStartCondition: 0,
                offSetEndCondition: 0,
                merge: false,
                useFeatScope: false,
                featScopeOptions: (int)swStartEndConditions_e.swStartSketchPlane,
                autoSelect: true,
                removeInnerLoops: false,
                thicknessSide1: 0,
                thicknessSide2: 0,
                bothDirectionType: false,
                thicknessType: 0,
                autoSelectComponents: false);

            if (extrudeFeature == null)
            {
                throw new Exception("Failed to create extrude feature");
            }

            Console.WriteLine("    Extruded to thickness: {0:F3}\"", CAM_THICKNESS);

            // Zoom to fit
            swModel.ViewZoomtofit2();
        }

        /// <summary>
        /// Saves the part to the current directory.
        /// </summary>
        private void SavePart()
        {
            string currentDir = System.IO.Directory.GetCurrentDirectory();
            string filePath = System.IO.Path.Combine(currentDir, "sinusoidal-cam.SLDPRT");

            Console.WriteLine("\nSaving part to: {0}", filePath);

            // Save the document
            int errors = 0;
            int warnings = 0;
            bool result = swModel.Extension.SaveAs(
                fileName: filePath,
                saveAsVersion: (int)swSaveAsVersion_e.swSaveAsCurrentVersion,
                saveAsOptions: (int)swSaveAsOptions_e.swSaveAsOptions_Silent,
                exportData: null,
                errors: ref errors,
                warnings: ref warnings);

            if (!result || errors != 0)
            {
                throw new Exception($"Failed to save part. Errors: {errors}, Warnings: {warnings}");
            }

            Console.WriteLine("  Part saved successfully.");
        }
    }
}
