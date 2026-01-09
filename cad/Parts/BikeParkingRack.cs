using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swconst;
using System;

namespace SolidWorksRenders
{
    /// <summary>
    /// Creates a bike parking rack for 10 bikes.
    /// Design: 5 inverted U-shaped racks (each holds 2 bikes) connected by base rails.
    /// Construction: Tubular steel design using 3D sketch paths with circular profile sweeps.
    /// </summary>
    public class BikeParkingRack : IPart
    {
        public string PartName => "Bike Parking Rack";
        public string FileName => "bike-parking-rack.sldprt";
        public string Description => "U-rack style parking for 10 bikes";

        // Rack dimensions (in meters - SolidWorks API uses meters)
        private const double TubeDiameter = 0.050;     // 50mm tube diameter
        private const double TubeRadius = TubeDiameter / 2;
        private const double RackHeight = 0.900;       // 900mm height (typical for bike racks)
        private const double RackWidth = 0.500;        // 500mm width (space for bike to lean)
        private const double RackSpacing = 0.500;      // 500mm between rack centers
        private const int NumRacks = 5;                // 5 racks for 10 bikes
        private const double BaseRailHeight = 0.050;   // 50mm above ground for base rails
        private const double ArcRadius = RackWidth / 2; // Radius for the top arc of U-shape

        // Calculated total length
        private static readonly double TotalLength = (NumRacks - 1) * RackSpacing;

        private ISldWorks swApp;

        public BikeParkingRack(ISldWorks solidWorksApp)
        {
            swApp = solidWorksApp ?? throw new ArgumentNullException(nameof(solidWorksApp));
        }

        /// <summary>
        /// Creates the bike parking rack part
        /// </summary>
        public IModelDoc2 CreatePart()
        {
            // Get part template from user preferences
            string partTemplate = swApp.GetUserPreferenceStringValue(
                (int)swUserPreferenceStringValue_e.swDefaultTemplatePart);

            if (string.IsNullOrEmpty(partTemplate))
            {
                throw new InvalidOperationException("No part template found. Please set a default part template in SolidWorks options.");
            }

            // Create new part document
            IModelDoc2 swModel = (IModelDoc2)swApp.NewDocument(
                TemplateName: partTemplate,
                PaperSize: 0,
                Width: 0,
                Height: 0);

            if (swModel == null)
            {
                throw new InvalidOperationException("Failed to create new part document");
            }

            Console.WriteLine($"Creating bike parking rack with {NumRacks} U-racks for {NumRacks * 2} bikes...");

            // Create the first U-rack
            IFeature firstRack = CreateURack(swModel, 0);
            Console.WriteLine("Created first U-rack");

            // Create linear pattern for remaining racks
            if (NumRacks > 1)
            {
                CreateRackPattern(swModel, firstRack);
                Console.WriteLine($"Created pattern for {NumRacks} U-racks");
            }

            // Create base rails connecting all racks
            CreateBaseRails(swModel);
            Console.WriteLine("Created base rails");

            // Rebuild the model
            swModel.ForceRebuild3(true);

            return swModel;
        }

        /// <summary>
        /// Creates a single U-shaped rack at the specified position
        /// </summary>
        /// <param name="swModel">The model document</param>
        /// <param name="xOffset">X offset from origin for this rack</param>
        /// <returns>The sweep feature for the U-rack</returns>
        private IFeature CreateURack(IModelDoc2 swModel, double xOffset)
        {
            ISketchManager swSketchMgr = swModel.SketchManager;
            IFeatureManager swFeatMgr = swModel.FeatureManager;
            IModelDocExtension swModelExt = swModel.Extension;

            // Create a 3D sketch for the U-rack path
            swSketchMgr.Insert3DSketch(UpdateEditRebuild: true);

            // The U-rack path consists of:
            // 1. Left vertical leg (from base to top-arc start)
            // 2. Top arc (semicircle)
            // 3. Right vertical leg (from top-arc end to base)

            double leftX = xOffset;
            double rightX = xOffset;
            double leftY = -RackWidth / 2;   // Left side of U
            double rightY = RackWidth / 2;   // Right side of U
            double baseZ = BaseRailHeight;   // Start above ground
            double topZ = RackHeight;        // Top of U-rack

            // Create left vertical line
            ISketchSegment leftLeg = swSketchMgr.CreateLine(
                X1: leftX, Y1: leftY, Z1: baseZ,
                X2: leftX, Y2: leftY, Z2: topZ);
            if (leftLeg == null)
                throw new InvalidOperationException("Failed to create left leg of U-rack");

            // Create top arc (semicircle connecting the two legs)
            // For a 3-point arc: start point, end point, and point on arc
            double arcCenterY = 0;
            double arcCenterZ = topZ;
            ISketchSegment topArc = swSketchMgr.Create3PointArc(
                X1: leftX, Y1: leftY, Z1: topZ,       // Start at left leg top
                X2: rightX, Y2: rightY, Z2: topZ,     // End at right leg top
                X3: leftX, Y3: arcCenterY, Z3: topZ + ArcRadius);  // Point on arc (top of semicircle)
            if (topArc == null)
                throw new InvalidOperationException("Failed to create top arc of U-rack");

            // Create right vertical line
            ISketchSegment rightLeg = swSketchMgr.CreateLine(
                X1: rightX, Y1: rightY, Z1: topZ,
                X2: rightX, Y2: rightY, Z2: baseZ);
            if (rightLeg == null)
                throw new InvalidOperationException("Failed to create right leg of U-rack");

            // Exit 3D sketch
            swSketchMgr.Insert3DSketch(UpdateEditRebuild: true);

            // Get the sketch feature that was just created
            IFeature sketchFeature = (IFeature)swModelExt.GetLastFeatureAdded();
            if (sketchFeature == null)
                throw new InvalidOperationException("Failed to get U-rack sketch feature");

            string sketchName = sketchFeature.Name;
            Console.WriteLine($"DEBUG: U-rack sketch name: {sketchName}");

            // Select the sketch as the sweep path (mark = 4)
            swModel.ClearSelection2(true);
            bool selected = swModelExt.SelectByID2(
                Name: sketchName,
                Type: "SKETCH",
                X: 0, Y: 0, Z: 0,
                Append: false,
                Mark: 4,  // Mark 4 = sweep path
                Callout: null,
                SelectOption: 0);

            if (!selected)
                throw new InvalidOperationException($"Failed to select sketch '{sketchName}' for sweep");

            // Create the sweep with circular profile
            // Using InsertProtrusionSwept4 with CircularProfile = true
            IFeature sweepFeature = swFeatMgr.InsertProtrusionSwept4(
                Propagate: false,                                        // Don't propagate to tangent edges
                Alignment: false,                                        // Don't align with end faces
                TwistCtrlOption: (int)swTwistControlType_e.swTwistControlFollowPath,
                KeepTangency: true,                                      // Keep tangent segments smooth
                BAdvancedSmoothing: true,                                // Smooth surfaces
                StartMatchingType: (int)swTangencyType_e.swTangencyNone,
                EndMatchingType: (int)swTangencyType_e.swTangencyNone,
                IsThinBody: false,                                       // Not a thin body
                Thickness1: 0,
                Thickness2: 0,
                ThinType: (int)swThinWallType_e.swThinWallOneDirection,
                PathAlign: 0,                                            // No path alignment correction
                Merge: true,                                             // Merge result
                UseFeatScope: false,
                UseAutoSelect: true,
                TwistAngle: 0,
                BMergeSmoothFaces: true,
                CircularProfile: true,                                   // Use circular profile
                CircularProfileDiameter: TubeDiameter,                   // 50mm tube
                Direction: (int)swSweepDirection_e.swSweepDirection_Bidirectional);

            if (sweepFeature == null)
                throw new InvalidOperationException("Failed to create U-rack sweep feature");

            return sweepFeature;
        }

        /// <summary>
        /// Creates a linear pattern of the U-rack
        /// </summary>
        private void CreateRackPattern(IModelDoc2 swModel, IFeature seedFeature)
        {
            IFeatureManager swFeatMgr = swModel.FeatureManager;
            IModelDocExtension swModelExt = swModel.Extension;

            // Clear selection
            swModel.ClearSelection2(true);

            // Select the X-axis for Direction 1 (mark = 1)
            bool selected = swModelExt.SelectByID2(
                Name: "Point1@Origin",
                Type: "EXTSKETCHPOINT",
                X: 0, Y: 0, Z: 0,
                Append: false,
                Mark: 0,
                Callout: null,
                SelectOption: 0);

            // Select an edge along the X-axis direction for pattern direction
            // We'll use the Front Plane normal as direction reference
            selected = swModelExt.SelectByID2(
                Name: "Front Plane",
                Type: "PLANE",
                X: 0, Y: 0, Z: 0,
                Append: false,
                Mark: 1,  // Mark 1 = Direction 1
                Callout: null,
                SelectOption: 0);

            // Select the seed feature (mark = 4)
            selected = seedFeature.Select2(
                Append: true,
                Mark: 4);  // Mark 4 = feature to pattern

            if (!selected)
                throw new InvalidOperationException("Failed to select seed feature for pattern");

            // Create linear pattern along X-axis
            IFeature patternFeature = swFeatMgr.FeatureLinearPattern5(
                Num1: NumRacks,                    // Number of instances in Direction 1
                Spacing1: RackSpacing,             // Spacing between instances
                Num2: 1,                           // Only 1 in Direction 2
                Spacing2: 0,
                FlipDir1: false,
                FlipDir2: false,
                DName1: "NULL",
                DName2: "NULL",
                GeometryPattern: true,             // Use geometry pattern for better performance
                VaryInstance: false,
                HasOffset1: false,
                HasOffset2: false,
                CtrlByNum1: false,
                CtrlByNum2: false,
                FromCentroid1: true,
                FromCentroid2: true,
                RevOffset1: false,
                RevOffset2: false,
                Offset1: 0,
                Offset2: 0,
                D2PatternSeedOnly: false,
                SyncSubAssemblies: false);

            // Pattern might fail if direction selection is wrong, continue anyway
            if (patternFeature == null)
            {
                Console.WriteLine("WARNING: Linear pattern failed. Creating individual racks instead...");
                CreateIndividualRacks(swModel);
            }
        }

        /// <summary>
        /// Creates individual U-racks if pattern fails
        /// </summary>
        private void CreateIndividualRacks(IModelDoc2 swModel)
        {
            for (int i = 1; i < NumRacks; i++)
            {
                double xOffset = i * RackSpacing;
                CreateURack(swModel, xOffset);
                Console.WriteLine($"Created rack {i + 1} at offset {xOffset * 1000}mm");
            }
        }

        /// <summary>
        /// Creates the base rails connecting all U-racks
        /// </summary>
        private void CreateBaseRails(IModelDoc2 swModel)
        {
            ISketchManager swSketchMgr = swModel.SketchManager;
            IFeatureManager swFeatMgr = swModel.FeatureManager;
            IModelDocExtension swModelExt = swModel.Extension;

            // Create front base rail (3D sketch)
            swSketchMgr.Insert3DSketch(UpdateEditRebuild: true);

            // Front rail: from first rack to last rack
            double startX = -RackSpacing / 2;  // Extend beyond first rack
            double endX = TotalLength + RackSpacing / 2;  // Extend beyond last rack
            double frontY = -RackWidth / 2;
            double railZ = BaseRailHeight;

            ISketchSegment frontRail = swSketchMgr.CreateLine(
                X1: startX, Y1: frontY, Z1: railZ,
                X2: endX, Y2: frontY, Z2: railZ);
            if (frontRail == null)
                Console.WriteLine("WARNING: Failed to create front rail line");

            // Exit 3D sketch
            swSketchMgr.Insert3DSketch(UpdateEditRebuild: true);

            // Get the sketch and create sweep
            IFeature frontRailSketch = (IFeature)swModelExt.GetLastFeatureAdded();
            if (frontRailSketch != null)
            {
                CreateRailSweep(swModel, frontRailSketch.Name, "front rail");
            }

            // Create back base rail (3D sketch)
            swSketchMgr.Insert3DSketch(UpdateEditRebuild: true);

            double backY = RackWidth / 2;
            ISketchSegment backRail = swSketchMgr.CreateLine(
                X1: startX, Y1: backY, Z1: railZ,
                X2: endX, Y2: backY, Z2: railZ);
            if (backRail == null)
                Console.WriteLine("WARNING: Failed to create back rail line");

            // Exit 3D sketch
            swSketchMgr.Insert3DSketch(UpdateEditRebuild: true);

            // Get the sketch and create sweep
            IFeature backRailSketch = (IFeature)swModelExt.GetLastFeatureAdded();
            if (backRailSketch != null)
            {
                CreateRailSweep(swModel, backRailSketch.Name, "back rail");
            }
        }

        /// <summary>
        /// Creates a sweep for a rail
        /// </summary>
        private void CreateRailSweep(IModelDoc2 swModel, string sketchName, string railName)
        {
            IFeatureManager swFeatMgr = swModel.FeatureManager;
            IModelDocExtension swModelExt = swModel.Extension;

            // Select the sketch as the sweep path (mark = 4)
            swModel.ClearSelection2(true);
            bool selected = swModelExt.SelectByID2(
                Name: sketchName,
                Type: "SKETCH",
                X: 0, Y: 0, Z: 0,
                Append: false,
                Mark: 4,  // Mark 4 = sweep path
                Callout: null,
                SelectOption: 0);

            if (!selected)
            {
                Console.WriteLine($"WARNING: Failed to select sketch '{sketchName}' for {railName}");
                return;
            }

            // Create the sweep with circular profile
            IFeature sweepFeature = swFeatMgr.InsertProtrusionSwept4(
                Propagate: false,
                Alignment: false,
                TwistCtrlOption: (int)swTwistControlType_e.swTwistControlFollowPath,
                KeepTangency: true,
                BAdvancedSmoothing: true,
                StartMatchingType: (int)swTangencyType_e.swTangencyNone,
                EndMatchingType: (int)swTangencyType_e.swTangencyNone,
                IsThinBody: false,
                Thickness1: 0,
                Thickness2: 0,
                ThinType: (int)swThinWallType_e.swThinWallOneDirection,
                PathAlign: 0,
                Merge: true,
                UseFeatScope: false,
                UseAutoSelect: true,
                TwistAngle: 0,
                BMergeSmoothFaces: true,
                CircularProfile: true,
                CircularProfileDiameter: TubeDiameter,
                Direction: (int)swSweepDirection_e.swSweepDirection_Bidirectional);

            if (sweepFeature == null)
            {
                Console.WriteLine($"WARNING: Failed to create {railName} sweep feature");
            }
        }

        /// <summary>
        /// Prints bike parking rack part details
        /// </summary>
        public void PrintPartDetails()
        {
            Console.WriteLine("\nPart Details:");
            Console.WriteLine($"- Number of U-racks: {NumRacks}");
            Console.WriteLine($"- Total bike capacity: {NumRacks * 2} bikes");
            Console.WriteLine($"- Rack height: {RackHeight * 1000:F0}mm ({RackHeight / 0.0254:F1} inches)");
            Console.WriteLine($"- Rack width: {RackWidth * 1000:F0}mm ({RackWidth / 0.0254:F1} inches)");
            Console.WriteLine($"- Rack spacing: {RackSpacing * 1000:F0}mm ({RackSpacing / 0.0254:F1} inches)");
            Console.WriteLine($"- Tube diameter: {TubeDiameter * 1000:F0}mm ({TubeDiameter / 0.0254:F1} inches)");
            Console.WriteLine($"- Total length: {(TotalLength + RackSpacing) * 1000:F0}mm ({(TotalLength + RackSpacing) / 0.0254:F1} inches)");
        }
    }
}
