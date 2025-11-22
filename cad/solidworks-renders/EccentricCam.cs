using System;
using System.Runtime.InteropServices;
using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swconst;

namespace HarmonicAnalyzer.CAD
{
    /// <summary>
    /// Creates an eccentric cam - produces harmonic motion for follower.
    /// Simple cylinder with off-center mounting hole.
    /// Displacement = eccentricity × sin(θ)
    /// </summary>
    public class EccentricCam
    {
        // Conversion factor: inches to meters (SolidWorks API uses meters internally)
        private const double INCH_TO_METER = 0.0254;

        // Parameters from parameters.kcl
        private const double CAM_DIAMETER = 2.0;        // inches
        private const double CAM_THICKNESS = 0.4;       // inches
        private const double SHAFT_DIAMETER = 0.375;    // inches (3/8")
        private const double KEYWAY_WIDTH = 0.125;      // inches (1/8")
        private const double KEYWAY_DEPTH = 0.06;       // inches

        // Eccentric cam specific parameter
        private const double ECCENTRICITY = 0.2;        // inches - offset distance from center (amplitude of motion)

        // Calculated parameters
        private static readonly double camRadius = CAM_DIAMETER / 2;
        private static readonly double shaftRadius = SHAFT_DIAMETER / 2;

        public static void Main(string[] args)
        {
            try
            {
                // Validate parameters before starting
                ValidateParameters();

                // Get or create SolidWorks application
                ISldWorks swApp = GetOrCreateSolidWorksApp();
                if (swApp == null)
                {
                    throw new InvalidOperationException("Failed to connect to SolidWorks");
                }

                // Create the eccentric cam part
                CreateEccentricCamPart(swApp);

                Console.WriteLine("Eccentric cam created successfully!");
            }
            catch (Exception ex)
            {
                Console.WriteLine($"Error creating eccentric cam: {ex.Message}");
                Console.WriteLine($"Stack trace: {ex.StackTrace}");
                System.Environment.Exit(1);
            }
        }

        /// <summary>
        /// Validates design parameters to ensure safe geometry
        /// </summary>
        private static void ValidateParameters()
        {
            // Assert: Cam diameter must be larger than shaft
            if (CAM_DIAMETER <= SHAFT_DIAMETER)
            {
                throw new ArgumentException("Cam diameter must be larger than shaft");
            }

            // Assert: Eccentricity must be greater than 0 and less than cam radius
            if (ECCENTRICITY <= 0 || ECCENTRICITY >= camRadius)
            {
                throw new ArgumentException("Eccentricity must be less than cam radius");
            }

            // Assert: Shaft hole not too close to cam edge
            double minClearance = camRadius - ECCENTRICITY - shaftRadius;
            if (minClearance <= 0)
            {
                throw new ArgumentException("Shaft hole too close to cam edge");
            }

            // Assert: Cam thickness must be positive
            if (CAM_THICKNESS <= 0)
            {
                throw new ArgumentException("Cam thickness must be positive");
            }

            // Assert: Keyway not too wide for shaft
            if (KEYWAY_WIDTH >= SHAFT_DIAMETER)
            {
                throw new ArgumentException("Keyway too wide for shaft");
            }
        }

        /// <summary>
        /// Gets existing SolidWorks instance or creates a new one
        /// </summary>
        private static ISldWorks GetOrCreateSolidWorksApp()
        {
            ISldWorks swApp = null;

            try
            {
                // Try to get existing instance
                swApp = (ISldWorks)Marshal.GetActiveObject("SldWorks.Application");
            }
            catch (COMException)
            {
                // Create new instance if none exists
                Type swAppType = Type.GetTypeFromProgID("SldWorks.Application");
                if (swAppType != null)
                {
                    swApp = (ISldWorks)Activator.CreateInstance(swAppType);
                }
            }

            if (swApp != null)
            {
                swApp.Visible = true;
            }

            return swApp;
        }

        /// <summary>
        /// Creates the complete eccentric cam part
        /// </summary>
        private static void CreateEccentricCamPart(ISldWorks swApp)
        {
            // Create new part document
            string partTemplatePath = swApp.GetUserPreferenceStringValue(
                (int)swUserPreferenceStringValue_e.swDefaultTemplatePart);

            IModelDoc2 swModel = (IModelDoc2)swApp.NewDocument(
                TemplateName: partTemplatePath,
                PaperSize: 0,
                Width: 0,
                Height: 0);

            if (swModel == null)
            {
                throw new InvalidOperationException("Failed to create new part document");
            }

            // Verify we have a part document
            if (swModel.GetType() != (int)swDocumentTypes_e.swDocPART)
            {
                throw new InvalidOperationException("Document is not a part");
            }

            IModelDocExtension swModelExt = swModel.Extension;
            IFeatureManager swFeatureMgr = swModel.FeatureManager;
            ISketchManager swSketchMgr = swModel.SketchManager;

            // Step 1: Create cam body sketch on Front Plane
            CreateCamBodySketch(swModel, swModelExt, swSketchMgr);

            // Step 2: Extrude the cam body
            IFeature camBody = ExtrudeCamBody(swFeatureMgr);

            // Step 3: Create hole with keyway sketch on top face
            CreateHoleWithKeywaySketch(swModel, swModelExt, swSketchMgr);

            // Step 4: Cut the hole through the cam
            CutHoleWithKeyway(swFeatureMgr);

            // Rebuild the model to ensure all features are updated
            swModel.ForceRebuild3(TopOnly: false);

            // Zoom to fit
            swModel.ViewZoomtofit2();
        }

        /// <summary>
        /// Creates the circular cam body sketch centered at origin
        /// </summary>
        private static void CreateCamBodySketch(IModelDoc2 swModel, IModelDocExtension swModelExt, ISketchManager swSketchMgr)
        {
            // Select Front Plane
            bool success = swModelExt.SelectByID2(
                Name: "Front Plane",
                Type: "PLANE",
                X: 0,
                Y: 0,
                Z: 0,
                Append: false,
                Mark: 0,
                Callout: null,
                SelectOption: 0);

            if (!success)
            {
                throw new InvalidOperationException("Failed to select Front Plane");
            }

            // Insert sketch on Front Plane
            swSketchMgr.InsertSketch(UpdateEditRebuild: true);

            // Create circular cam body centered at origin
            // Circle is defined by center point (0, 0, 0) and a point on the circumference
            swSketchMgr.CreateCircle(
                XC: 0,
                YC: 0,
                Zc: 0,
                Xp: camRadius * INCH_TO_METER,
                Yp: 0,
                Zp: 0);

            // Exit sketch
            swSketchMgr.InsertSketch(UpdateEditRebuild: true);
        }

        /// <summary>
        /// Extrudes the cam body to the specified thickness
        /// </summary>
        private static IFeature ExtrudeCamBody(IFeatureManager swFeatureMgr)
        {
            double depthMeters = CAM_THICKNESS * INCH_TO_METER;

            IFeature extrudeFeature = swFeatureMgr.FeatureExtrusion3(
                Sd: true,                                          // Single direction
                Flip: false,                                       // Don't flip side to cut
                Dir: false,                                        // Don't flip extrusion direction
                T1: (int)swEndConditions_e.swEndCondBlind,         // End condition: Blind
                T2: (int)swEndConditions_e.swEndCondBlind,         // End condition 2 (unused for single)
                D1: depthMeters,                                   // Depth in meters
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

            if (extrudeFeature == null)
            {
                throw new InvalidOperationException("Failed to create cam body extrusion");
            }

            return extrudeFeature;
        }

        /// <summary>
        /// Creates the hole with keyway sketch on the top face of the cam
        /// The hole is positioned at [eccentricity, 0] to create eccentric motion
        /// </summary>
        private static void CreateHoleWithKeywaySketch(IModelDoc2 swModel, IModelDocExtension swModelExt, ISketchManager swSketchMgr)
        {
            // Select the top face of the cam body
            bool success = swModelExt.SelectByID2(
                Name: "Boss-Extrude1",
                Type: "BODYFEATURE",
                X: 0,
                Y: 0,
                Z: CAM_THICKNESS * INCH_TO_METER,
                Append: false,
                Mark: 0,
                Callout: null,
                SelectOption: 0);

            if (!success)
            {
                // Try alternative selection method - select the top face directly
                swModel.ClearSelection2(true);
            }

            // Create sketch on the XY plane (same as the cam body for simplicity)
            swModelExt.SelectByID2(
                Name: "Front Plane",
                Type: "PLANE",
                X: 0,
                Y: 0,
                Z: 0,
                Append: false,
                Mark: 0,
                Callout: null,
                SelectOption: 0);

            swSketchMgr.InsertSketch(UpdateEditRebuild: true);

            // Calculate keyway profile points
            // The shaft hole center is offset by eccentricity
            double holeCenterX = ECCENTRICITY * INCH_TO_METER;
            double holeCenterY = 0;

            // Calculate start angle for keyway
            double startAngle = Math.Asin((KEYWAY_WIDTH / 2) / shaftRadius);  // radians

            // Convert to meters
            double shaftRadiusMeters = shaftRadius * INCH_TO_METER;
            double keywayWidthMeters = KEYWAY_WIDTH * INCH_TO_METER;
            double keywayDepthMeters = KEYWAY_DEPTH * INCH_TO_METER;

            // Create keyway profile using lines and arcs
            // Start point: top of keyway, right side
            double startX = holeCenterX + shaftRadiusMeters * Math.Cos(startAngle);
            double startY = holeCenterY + shaftRadiusMeters * Math.Sin(startAngle);

            // Draw the keyway profile
            // 1. Line to the right (radially outward for keyway depth)
            swSketchMgr.CreateLine(
                X1: startX,
                Y1: startY,
                Z1: 0,
                X2: startX + keywayDepthMeters,
                Y2: startY,
                Z2: 0);

            // 2. Line down (keyway width)
            swSketchMgr.CreateLine(
                X1: startX + keywayDepthMeters,
                Y1: startY,
                Z1: 0,
                X2: startX + keywayDepthMeters,
                Y2: startY - keywayWidthMeters,
                Z2: 0);

            // 3. Line back to the left (back to circle)
            swSketchMgr.CreateLine(
                X1: startX + keywayDepthMeters,
                Y1: startY - keywayWidthMeters,
                Z1: 0,
                X2: startX,
                Y2: startY - keywayWidthMeters,
                Z2: 0);

            // 4. Arc from bottom of keyway around to left side (180 degrees)
            double arc1EndX = holeCenterX - shaftRadiusMeters * Math.Cos(startAngle);
            double arc1EndY = holeCenterY - shaftRadiusMeters * Math.Sin(startAngle);

            swSketchMgr.CreateArc(
                XC: holeCenterX,
                YC: holeCenterY,
                Zc: 0,
                X1: startX,
                Y1: startY - keywayWidthMeters,
                Z1: 0,
                X2: arc1EndX,
                Y2: arc1EndY,
                Z2: 0,
                Direction: 1);  // Counter-clockwise

            // 5. Arc from left side back to top of keyway (180 degrees on other side)
            swSketchMgr.CreateArc(
                XC: holeCenterX,
                YC: holeCenterY,
                Zc: 0,
                X1: arc1EndX,
                Y1: arc1EndY,
                Z1: 0,
                X2: startX,
                Y2: startY,
                Z2: 0,
                Direction: 1);  // Counter-clockwise

            // Exit sketch
            swSketchMgr.InsertSketch(UpdateEditRebuild: true);
        }

        /// <summary>
        /// Cuts the hole with keyway through the entire cam thickness
        /// </summary>
        private static IFeature CutHoleWithKeyway(IFeatureManager swFeatureMgr)
        {
            double depthMeters = CAM_THICKNESS * INCH_TO_METER;

            IFeature cutFeature = swFeatureMgr.FeatureCut4(
                Sd: true,                                          // Single direction
                Flip: false,                                       // Don't flip side to cut
                Dir: false,                                        // Use default direction
                T1: (int)swEndConditions_e.swEndCondThroughAll,    // Cut through all
                T2: (int)swEndConditions_e.swEndCondBlind,         // End condition 2 (unused)
                D1: depthMeters,                                   // Depth (used as reference)
                D2: 0,                                             // Depth 2 (unused)
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
                NormalCut: false,                                  // Not a sheet metal normal cut
                UseFeatScope: false,                               // Affect all bodies
                UseAutoSelect: true,                               // Auto-select bodies
                AssemblyFeatureScope: false,                       // Not an assembly feature
                AutoSelectComponents: false,                       // Not an assembly feature
                PropagateFeatureToParts: false,                    // Not an assembly feature
                T0: (int)swStartConditions_e.swStartSketchPlane,   // Start from sketch plane
                StartOffset: 0,                                    // No start offset
                FlipStartOffset: false,                            // Don't flip start offset
                OptimizeGeometry: false                            // Not optimizing geometry
            );

            if (cutFeature == null)
            {
                throw new InvalidOperationException("Failed to create hole with keyway cut");
            }

            return cutFeature;
        }
    }
}
