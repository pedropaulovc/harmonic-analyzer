using System;
using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swconst;

namespace SolidWorksRenders
{
    /// <summary>
    /// Creates an eccentric cam in SolidWorks
    /// Translation of eccentric-cam.kcl
    /// </summary>
    public class EccentricCam
    {
        // Constants for unit conversion
        private const double INCH_TO_METER = 0.0254;

        // Parameters from parameters.kcl (in inches)
        private const double CAM_DIAMETER = 2.0;
        private const double CAM_THICKNESS = 0.4;
        private const double SHAFT_DIAMETER = 0.375;
        private const double KEYWAY_WIDTH = 0.125;
        private const double KEYWAY_DEPTH = 0.06;

        // Parameters from eccentric-cam.kcl (in inches)
        private const double ECCENTRICITY = 0.2;

        public static void Create(ISldWorks swApp)
        {
            if (swApp == null)
                throw new ArgumentNullException(nameof(swApp));

            // Convert all dimensions to meters
            double camRadius = (CAM_DIAMETER / 2.0) * INCH_TO_METER;
            double camThickness = CAM_THICKNESS * INCH_TO_METER;
            double shaftRadius = (SHAFT_DIAMETER / 2.0) * INCH_TO_METER;
            double keywayWidth = KEYWAY_WIDTH * INCH_TO_METER;
            double keywayDepth = KEYWAY_DEPTH * INCH_TO_METER;
            double eccentricity = ECCENTRICITY * INCH_TO_METER;

            // Validate parameters (from eccentric-cam.kcl assertions)
            if (CAM_DIAMETER <= SHAFT_DIAMETER)
                throw new InvalidOperationException("Cam diameter must be larger than shaft");
            if (ECCENTRICITY <= 0 || ECCENTRICITY >= (CAM_DIAMETER / 2.0))
                throw new InvalidOperationException("Eccentricity must be between 0 and cam radius");
            double minClearance = (CAM_DIAMETER / 2.0) - ECCENTRICITY - (SHAFT_DIAMETER / 2.0);
            if (minClearance <= 0)
                throw new InvalidOperationException("Shaft hole too close to cam edge");
            if (CAM_THICKNESS <= 0)
                throw new InvalidOperationException("Cam thickness must be positive");
            if (KEYWAY_WIDTH >= SHAFT_DIAMETER)
                throw new InvalidOperationException("Keyway too wide for shaft");

            // Create new part document
            string partTemplate = swApp.GetUserPreferenceStringValue(
                (int)swUserPreferenceStringValue_e.swDefaultTemplatePart);

            IModelDoc2? swModel = swApp.NewDocument(
                TemplateName: partTemplate,
                PaperSize: 0,
                Width: 0,
                Height: 0) as IModelDoc2;

            if (swModel == null)
                throw new InvalidOperationException("Failed to create new part document");

            // Get sketch manager and feature manager
            ISketchManager swSketchMgr = swModel.SketchManager;
            IFeatureManager swFeatMgr = swModel.FeatureManager;

            // Select Front Plane to create sketch on XY plane (matching KCL's XY plane)
            bool success = swModel.Extension.SelectByID2(
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
                throw new InvalidOperationException("Failed to select Front Plane");

            // Insert sketch
            swSketchMgr.InsertSketch(true);

            // Enable performance mode for sketch creation
            swSketchMgr.AddToDB = true;
            swSketchMgr.DisplayWhenAdded = false;

            // Create outer circle for cam body (centered at origin)
            swSketchMgr.CreateCircleByRadius(
                XC: 0,
                YC: 0,
                Zc: 0,
                Radius: camRadius);

            // Create shaft hole circle (offset by eccentricity along X axis)
            swSketchMgr.CreateCircleByRadius(
                XC: eccentricity,
                YC: 0,
                Zc: 0,
                Radius: shaftRadius);

            // Create keyway profile
            // Calculate start angle for keyway (from KCL: asin(keywayWidth/2/shaftRadius))
            double startAngle = Math.Asin((keywayWidth / 2.0) / shaftRadius);

            // Keyway profile coordinates (matching KCL geometry)
            double startX = eccentricity + shaftRadius * Math.Cos(startAngle);
            double startY = shaftRadius * Math.Sin(startAngle);

            // Create keyway as a rectangle extending from the shaft
            // Top horizontal line
            swSketchMgr.CreateLine(
                X1: startX,
                Y1: startY,
                Z1: 0,
                X2: startX + keywayDepth,
                Y2: startY,
                Z2: 0);

            // Right vertical line
            swSketchMgr.CreateLine(
                X1: startX + keywayDepth,
                Y1: startY,
                Z1: 0,
                X2: startX + keywayDepth,
                Y2: -startY,
                Z2: 0);

            // Bottom horizontal line
            swSketchMgr.CreateLine(
                X1: startX + keywayDepth,
                Y1: -startY,
                Z1: 0,
                X2: startX,
                Y2: -startY,
                Z2: 0);

            // Restore normal display mode
            swSketchMgr.AddToDB = false;
            swSketchMgr.DisplayWhenAdded = true;

            // Refresh graphics to show sketch entities
            IModelView? swView = swModel.ActiveView as IModelView;
            if (swView != null)
            {
                swView.GraphicsRedraw(null);
            }

            // Exit sketch
            swSketchMgr.InsertSketch(true);

            // Select the sketch for extrusion
            success = swModel.Extension.SelectByID2(
                Name: "Sketch1",
                Type: "SKETCH",
                X: 0,
                Y: 0,
                Z: 0,
                Append: false,
                Mark: 0,
                Callout: null,
                SelectOption: 0);

            if (!success)
                throw new InvalidOperationException("Failed to select sketch for extrusion");

            // Create extrusion feature
            // The outer circle will be the base, and the inner hole/keyway will be automatically cut
            IFeature extrudeFeature = swFeatMgr.FeatureExtrusion3(
                Sd: true,                                           // Single direction
                Flip: false,                                        // Don't flip side
                Dir: false,                                         // Don't flip extrusion direction
                T1: (int)swEndConditions_e.swEndCondBlind,         // Blind end condition
                T2: (int)swEndConditions_e.swEndCondBlind,         // (not used for single direction)
                D1: camThickness,                                   // Extrusion depth in meters
                D2: 0,                                              // (not used for single direction)
                Dchk1: false,                                       // No draft
                Dchk2: false,                                       // No draft
                Ddir1: false,                                       // Draft direction (not used)
                Ddir2: false,                                       // Draft direction (not used)
                Dang1: 0,                                           // Draft angle (not used)
                Dang2: 0,                                           // Draft angle (not used)
                OffsetReverse1: false,                              // Offset direction (not used)
                OffsetReverse2: false,                              // Offset direction (not used)
                TranslateSurface1: false,                           // Surface translation (not used)
                TranslateSurface2: false,                           // Surface translation (not used)
                Merge: true,                                        // Merge results
                UseFeatScope: false,                                // Don't use feature scope
                UseAutoSelect: true,                                // Auto-select bodies
                T0: (int)swStartConditions_e.swStartSketchPlane,   // Start from sketch plane
                StartOffset: 0,                                     // No start offset
                FlipStartOffset: false);                            // Don't flip start offset

            if (extrudeFeature == null)
                throw new InvalidOperationException("Failed to create extrusion feature");

            // Zoom to fit
            swModel.ViewZoomtofit2();

            Console.WriteLine("Eccentric cam created successfully!");
            Console.WriteLine($"Cam diameter: {CAM_DIAMETER} in ({camRadius * 2} m)");
            Console.WriteLine($"Cam thickness: {CAM_THICKNESS} in ({camThickness} m)");
            Console.WriteLine($"Shaft diameter: {SHAFT_DIAMETER} in ({shaftRadius * 2} m)");
            Console.WriteLine($"Eccentricity: {ECCENTRICITY} in ({eccentricity} m)");
            Console.WriteLine($"Keyway: {KEYWAY_WIDTH} x {KEYWAY_DEPTH} in");
        }
    }
}
