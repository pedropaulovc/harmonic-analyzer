using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swconst;
using System;

namespace SolidWorksRenders
{
    /// <summary>
    /// Creates a symmetrical cast iron A-frame support for the harmonic analyzer.
    ///
    /// Design follows standard CAD workflow:
    /// 1. Sketch isosceles trapezoid on Right Plane (side profile)
    /// 2. Extrude Mid-Plane to 7.25" total width (solid)
    /// 3. Cut window through-all (front to back)
    /// 4. Add mounting holes on bottom
    /// 5. Add external fillets
    ///
    /// When cut vertically (plane parallel to Right Plane through center),
    /// cross section resembles an "I" shape:
    /// - Top flange = material above the window
    /// - Web area = window opening (empty)
    /// - Bottom flange = material below the window
    /// </summary>
    public class RockerArmSupport : IPart
    {
        public string PartName => "Rocker Arm Support";
        public string FileName => "rocker-arm-support.sldprt";
        public string Description => "A-frame support with through-all window";

        // Unit conversion
        private const double InchToMeter = 0.0254;

        // Primary Dimensions (Bounding Box)
        private const double TotalHeight = 7.00 * InchToMeter;        // 7.00"
        private const double MaxWidth = 7.25 * InchToMeter;           // 7.25" (front view width)
        private const double BaseDepth = 2.50 * InchToMeter;          // 2.50" (side base depth)
        private const double TopDepth = (2.0 / 3.0) * InchToMeter;    // 0.67" (~2/3") (side top depth)
        private const double WallThickness = 0.25 * InchToMeter;      // 0.25" uniform

        // Window (internal cutout) dimensions - creates I-beam cross section when cut vertically
        private const double WindowSize = 5.00 * InchToMeter;         // 5.00" x 5.00" square
        private const double WindowCornerRadius = 0.625 * InchToMeter; // 0.625" fillet on corners (range: 0.50"-0.75")
        // Window vertical position: 0.75" top rail, 1.25" bottom rail (asymmetric for structural stability)
        private const double WindowBottomRail = 1.25 * InchToMeter;   // 1.25" material below window

        // Mounting holes
        private const double MountingHoleDiameter = 0.3125 * InchToMeter; // 5/16" clearance holes
        private const double MountingHoleRadius = MountingHoleDiameter / 2;

        // External fillets
        private const double ExternalFilletRadius = 0.125 * InchToMeter; // 0.125" on sharp edges

        private ISldWorks swApp;

        public RockerArmSupport(ISldWorks solidWorksApp)
        {
            swApp = solidWorksApp ?? throw new ArgumentNullException(nameof(solidWorksApp));
        }

        public IModelDoc2 CreatePart()
        {
            string partTemplate = swApp.GetUserPreferenceStringValue(
                (int)swUserPreferenceStringValue_e.swDefaultTemplatePart);

            if (string.IsNullOrEmpty(partTemplate))
            {
                throw new InvalidOperationException("No part template found. Please set a default part template in SolidWorks options.");
            }

            IModelDoc2 swModel = (IModelDoc2)swApp.NewDocument(
                TemplateName: partTemplate,
                PaperSize: 0,
                Width: 0,
                Height: 0);

            if (swModel == null)
            {
                throw new InvalidOperationException("Failed to create new part document");
            }

            // Step 1: Create isosceles trapezoid on Right Plane and extrude
            Console.WriteLine("Creating A-frame profile (isosceles trapezoid)...");
            CreateAFrameBody(swModel);

            // Step 2: Create window cutout through the entire part
            // When cut vertically (through center), shows I-beam cross section:
            // - Top material (above window) = top flange
            // - Window opening = web removed
            // - Bottom material (below window) = bottom flange
            Console.WriteLine("Creating center window cutout...");
            CreateWindowCutout(swModel);

            // Step 3: Add mounting holes on bottom
            Console.WriteLine("Creating mounting holes...");
            CreateMountingHoles(swModel);

            // Step 4: Add external fillets
            Console.WriteLine("Adding external fillets...");
            ApplyExternalFillets(swModel);

            // Rebuild the model
            swModel.ForceRebuild3(true);

            return swModel;
        }

        /// <summary>
        /// Creates the A-frame body by sketching an isosceles trapezoid on Right Plane
        /// and extruding Mid-Plane to 7.25" total width.
        /// </summary>
        private void CreateAFrameBody(IModelDoc2 swModel)
        {
            ISketchManager swSketchMgr = swModel.SketchManager;
            IFeatureManager swFeatMgr = swModel.FeatureManager;
            IModelDocExtension swModelExt = swModel.Extension;

            // Select Right Plane for the side profile (YZ plane in SolidWorks)
            bool selected = swModelExt.SelectByID2(
                Name: "Right Plane",
                Type: "PLANE",
                X: 0, Y: 0, Z: 0,
                Append: false,
                Mark: 0,
                Callout: null,
                SelectOption: 0);

            if (!selected)
                throw new InvalidOperationException("Failed to select Right Plane");

            swSketchMgr.InsertSketch(UpdateEditRebuild: true);
            swSketchMgr.AddToDB = true;

            // Create isosceles trapezoid profile
            // On Right Plane: Y is vertical (height), Z is horizontal (depth)
            // Bottom base: 2.50" wide, centered
            // Top: 0.67" wide, centered
            // Height: 7.00"
            double bottomHalf = BaseDepth / 2;
            double topHalf = TopDepth / 2;

            // Draw trapezoid: bottom left -> bottom right -> top right -> top left -> close
            // Z is horizontal, Y is vertical on Right Plane
            swSketchMgr.CreateLine(-bottomHalf, 0, 0, bottomHalf, 0, 0);           // Bottom edge
            swSketchMgr.CreateLine(bottomHalf, 0, 0, topHalf, TotalHeight, 0);     // Right edge (tapered)
            swSketchMgr.CreateLine(topHalf, TotalHeight, 0, -topHalf, TotalHeight, 0); // Top edge
            swSketchMgr.CreateLine(-topHalf, TotalHeight, 0, -bottomHalf, 0, 0);   // Left edge (tapered)

            swSketchMgr.AddToDB = false;
            swSketchMgr.InsertSketch(UpdateEditRebuild: true);

            // Get and rename the sketch
            swModel.ForceRebuild3(false);
            IFeature trapezoidSketch = swModelExt.GetLastFeatureAdded();
            trapezoidSketch.Name = "A-Frame Profile";

            // Select sketch for extrusion
            selected = swModelExt.SelectByID2(
                Name: trapezoidSketch.Name,
                Type: "SKETCH",
                X: 0, Y: 0, Z: 0,
                Append: false,
                Mark: 0,
                Callout: null,
                SelectOption: 0);

            if (!selected)
                throw new InvalidOperationException("Failed to select A-Frame Profile sketch for extrusion");

            // Extrude Mid-Plane (both directions equally) to total width of 7.25"
            // Each direction = 7.25" / 2 = 3.625"
            double halfWidth = MaxWidth / 2;

            IFeature extrudeFeature = swFeatMgr.FeatureExtrusion3(
                Sd: false,                                         // Both directions (Mid-Plane)
                Flip: false,
                Dir: false,
                T1: (int)swEndConditions_e.swEndCondBlind,
                T2: (int)swEndConditions_e.swEndCondBlind,
                D1: halfWidth,                                     // Direction 1 depth
                D2: halfWidth,                                     // Direction 2 depth
                Dchk1: false,
                Dchk2: false,
                Ddir1: false,
                Ddir2: false,
                Dang1: 0,
                Dang2: 0,
                OffsetReverse1: false,
                OffsetReverse2: false,
                TranslateSurface1: false,
                TranslateSurface2: false,
                Merge: true,
                UseFeatScope: false,
                UseAutoSelect: true,
                T0: (int)swStartConditions_e.swStartSketchPlane,
                StartOffset: 0,
                FlipStartOffset: false);

            if (extrudeFeature == null)
                throw new InvalidOperationException("Failed to extrude A-frame body");

            extrudeFeature.Name = "A-Frame Body";
        }

        /// <summary>
        /// Creates a through-all window cutout in the center of the A-frame.
        /// When cut vertically, shows I-beam cross section.
        /// </summary>
        private void CreateWindowCutout(IModelDoc2 swModel)
        {
            ISketchManager swSketchMgr = swModel.SketchManager;
            IFeatureManager swFeatMgr = swModel.FeatureManager;
            IModelDocExtension swModelExt = swModel.Extension;

            // Select Front Plane for the window sketch
            bool selected = swModelExt.SelectByID2(
                Name: "Front Plane",
                Type: "PLANE",
                X: 0, Y: 0, Z: 0,
                Append: false,
                Mark: 0,
                Callout: null,
                SelectOption: 0);

            if (!selected)
            {
                Console.WriteLine("WARNING: Failed to select Front Plane for window cutout");
                return;
            }

            swSketchMgr.InsertSketch(UpdateEditRebuild: true);
            swSketchMgr.AddToDB = true;

            // Window is positioned asymmetrically for structural stability
            // Window size: 5.00" x 5.00"
            // Top rail: 0.75", Bottom rail: 1.25"
            double halfWindow = WindowSize / 2;
            double windowBottom = WindowBottomRail;  // 1.25" from bottom
            double windowTop = windowBottom + WindowSize;  // 6.25" from bottom (leaves 0.75" top rail)

            // Create rectangle for window (centered horizontally at X=0)
            double left = -halfWindow;
            double right = halfWindow;
            double bottom = windowBottom;
            double top = windowTop;

            // Draw rectangle
            swSketchMgr.CreateLine(left, bottom, 0, right, bottom, 0);   // Bottom
            swSketchMgr.CreateLine(right, bottom, 0, right, top, 0);     // Right
            swSketchMgr.CreateLine(right, top, 0, left, top, 0);         // Top
            swSketchMgr.CreateLine(left, top, 0, left, bottom, 0);       // Left

            swSketchMgr.AddToDB = false;

            // Apply fillets to corners
            double offset = 0.01 * InchToMeter;

            // Bottom-left corner
            swModelExt.SelectByID2("", "SKETCHSEGMENT", left + offset, bottom, 0, false, 0, null, 0);
            swModelExt.SelectByID2("", "SKETCHSEGMENT", left, bottom + offset, 0, true, 0, null, 0);
            swSketchMgr.CreateFillet(WindowCornerRadius, (int)swConstrainedCornerAction_e.swConstrainedCornerDeleteGeometry);

            // Bottom-right corner
            swModelExt.SelectByID2("", "SKETCHSEGMENT", right - offset, bottom, 0, false, 0, null, 0);
            swModelExt.SelectByID2("", "SKETCHSEGMENT", right, bottom + offset, 0, true, 0, null, 0);
            swSketchMgr.CreateFillet(WindowCornerRadius, (int)swConstrainedCornerAction_e.swConstrainedCornerDeleteGeometry);

            // Top-right corner
            swModelExt.SelectByID2("", "SKETCHSEGMENT", right - offset, top, 0, false, 0, null, 0);
            swModelExt.SelectByID2("", "SKETCHSEGMENT", right, top - offset, 0, true, 0, null, 0);
            swSketchMgr.CreateFillet(WindowCornerRadius, (int)swConstrainedCornerAction_e.swConstrainedCornerDeleteGeometry);

            // Top-left corner
            swModelExt.SelectByID2("", "SKETCHSEGMENT", left + offset, top, 0, false, 0, null, 0);
            swModelExt.SelectByID2("", "SKETCHSEGMENT", left, top - offset, 0, true, 0, null, 0);
            swSketchMgr.CreateFillet(WindowCornerRadius, (int)swConstrainedCornerAction_e.swConstrainedCornerDeleteGeometry);

            swSketchMgr.InsertSketch(UpdateEditRebuild: true);

            // Get and rename the sketch
            swModel.ForceRebuild3(false);
            IFeature windowSketch = swModelExt.GetLastFeatureAdded();
            windowSketch.Name = "Window Sketch";

            // Select sketch for cut
            selected = swModelExt.SelectByID2(
                Name: windowSketch.Name,
                Type: "SKETCH",
                X: 0, Y: 0, Z: 0,
                Append: false,
                Mark: 0,
                Callout: null,
                SelectOption: 0);

            if (!selected)
            {
                Console.WriteLine("WARNING: Failed to select window sketch for cut");
                return;
            }

            // Through-all cut in both directions (front to back)
            IFeature cutFeature = swFeatMgr.FeatureCut4(
                Sd: false,                                         // Both directions (through-all)
                Flip: false,
                Dir: false,
                T1: (int)swEndConditions_e.swEndCondThroughAll,   // Through-all direction 1
                T2: (int)swEndConditions_e.swEndCondThroughAll,   // Through-all direction 2
                D1: 0,
                D2: 0,
                Dchk1: false,
                Dchk2: false,
                Ddir1: false,
                Ddir2: false,
                Dang1: 0,
                Dang2: 0,
                OffsetReverse1: false,
                OffsetReverse2: false,
                TranslateSurface1: false,
                TranslateSurface2: false,
                NormalCut: false,
                UseFeatScope: false,
                UseAutoSelect: true,
                AssemblyFeatureScope: false,
                AutoSelectComponents: false,
                PropagateFeatureToParts: false,
                T0: (int)swStartConditions_e.swStartSketchPlane,
                StartOffset: 0,
                FlipStartOffset: false,
                OptimizeGeometry: false);

            if (cutFeature == null)
            {
                Console.WriteLine("WARNING: Failed to create window cutout - continuing");
            }
            else
            {
                cutFeature.Name = "Window Cutout";
                Console.WriteLine($"Created through-all window cutout ({WindowSize / InchToMeter:F2}\" x {WindowSize / InchToMeter:F2}\")");
            }
        }

        /// <summary>
        /// Creates mounting holes on the bottom internal flange.
        /// Two holes positioned for bolt attachment.
        /// </summary>
        private void CreateMountingHoles(IModelDoc2 swModel)
        {
            ISketchManager swSketchMgr = swModel.SketchManager;
            IFeatureManager swFeatMgr = swModel.FeatureManager;
            IModelDocExtension swModelExt = swModel.Extension;

            // Select Top Plane (XZ) for the holes - sketching on the bottom flange
            bool selected = swModelExt.SelectByID2(
                Name: "Top Plane",
                Type: "PLANE",
                X: 0, Y: 0, Z: 0,
                Append: false,
                Mark: 0,
                Callout: null,
                SelectOption: 0);

            if (!selected)
            {
                Console.WriteLine("WARNING: Failed to select Top Plane for mounting holes");
                return;
            }

            swSketchMgr.InsertSketch(UpdateEditRebuild: true);
            swSketchMgr.AddToDB = true;

            // Position holes on the bottom flange
            // Flange is the inner area after shelling
            // Holes should be centered along the X axis (front view width)
            // and positioned along the Z axis (depth)
            double holeSpacingX = 2.5 * InchToMeter;  // Distance between holes in X
            double holeOffsetZ = 0;                    // Centered in depth

            // Create two mounting holes
            swSketchMgr.CreateCircleByRadius(-holeSpacingX / 2, holeOffsetZ, 0, MountingHoleRadius);
            swSketchMgr.CreateCircleByRadius(holeSpacingX / 2, holeOffsetZ, 0, MountingHoleRadius);

            swSketchMgr.AddToDB = false;
            swSketchMgr.InsertSketch(UpdateEditRebuild: true);

            // Get and rename the sketch
            swModel.ForceRebuild3(false);
            IFeature holesSketch = swModelExt.GetLastFeatureAdded();
            holesSketch.Name = "Mounting Holes Sketch";

            // Select sketch for cut
            selected = swModelExt.SelectByID2(
                Name: holesSketch.Name,
                Type: "SKETCH",
                X: 0, Y: 0, Z: 0,
                Append: false,
                Mark: 0,
                Callout: null,
                SelectOption: 0);

            if (!selected)
            {
                Console.WriteLine("WARNING: Failed to select mounting holes sketch for cut");
                return;
            }

            // Cut through the bottom flange
            IFeature cutFeature = swFeatMgr.FeatureCut4(
                Sd: true,                                          // Single direction (down through flange)
                Flip: false,
                Dir: true,                                         // Flip direction (cut downward)
                T1: (int)swEndConditions_e.swEndCondBlind,
                T2: (int)swEndConditions_e.swEndCondBlind,
                D1: WallThickness * 2,                             // Cut through the flange thickness
                D2: 0,
                Dchk1: false,
                Dchk2: false,
                Ddir1: false,
                Ddir2: false,
                Dang1: 0,
                Dang2: 0,
                OffsetReverse1: false,
                OffsetReverse2: false,
                TranslateSurface1: false,
                TranslateSurface2: false,
                NormalCut: false,
                UseFeatScope: false,
                UseAutoSelect: true,
                AssemblyFeatureScope: false,
                AutoSelectComponents: false,
                PropagateFeatureToParts: false,
                T0: (int)swStartConditions_e.swStartSketchPlane,
                StartOffset: 0,
                FlipStartOffset: false,
                OptimizeGeometry: false);

            if (cutFeature == null)
            {
                Console.WriteLine("WARNING: Failed to create mounting holes - continuing");
            }
            else
            {
                cutFeature.Name = "Mounting Holes";
                Console.WriteLine($"Created 2 mounting holes ({MountingHoleDiameter / InchToMeter:F4}\" diameter)");
            }
        }

        /// <summary>
        /// Applies small radius fillets to all sharp external edges to simulate cast appearance.
        /// </summary>
        private void ApplyExternalFillets(IModelDoc2 swModel)
        {
            IFeatureManager swFeatMgr = swModel.FeatureManager;

            // Get all bodies in the part
            IPartDoc partDoc = (IPartDoc)swModel;
            object[] bodies = (object[])partDoc.GetBodies2((int)swBodyType_e.swAllBodies, true);

            if (bodies == null || bodies.Length == 0)
            {
                Console.WriteLine("WARNING: No bodies found for filleting");
                return;
            }

            swModel.ClearSelection2(true);

            // Select all edges from the body
            int edgeCount = 0;
            foreach (object bodyObj in bodies)
            {
                IBody2 body = (IBody2)bodyObj;
                object[] edges = (object[])body.GetEdges();

                if (edges != null)
                {
                    foreach (object edgeObj in edges)
                    {
                        IEdge edge = (IEdge)edgeObj;
                        IEntity edgeEntity = (IEntity)edge;

                        bool selected = edgeEntity.Select4(
                            Append: edgeCount > 0,
                            Data: null);

                        if (selected)
                        {
                            edgeCount++;
                        }
                    }
                }
            }

            if (edgeCount == 0)
            {
                Console.WriteLine("WARNING: No edges selected for external filleting");
                return;
            }

            Console.WriteLine($"Selected {edgeCount} edges for external filleting");

            // Create fillet feature
            IFeature filletFeature = (IFeature)swFeatMgr.FeatureFillet(
                Options: (int)swFeatureFilletOptions_e.swFeatureFilletUniformRadius,
                R1: ExternalFilletRadius,
                Ftyp: (int)swFeatureFilletType_e.swFeatureFilletType_Simple,
                OverflowType: (int)swFilletOverFlowType_e.swFilletOverFlowType_Default,
                Radii: null,
                SetBackDistances: null,
                PointRadiusArray: null);

            swModel.ClearSelection2(true);

            if (filletFeature == null)
            {
                Console.WriteLine("WARNING: Failed to create external fillet feature - this is common for complex geometry");
            }
            else
            {
                filletFeature.Name = "External Fillets";
                Console.WriteLine($"Created external fillets with {ExternalFilletRadius / InchToMeter:F3}\" radius");
            }
        }

        public void PrintPartDetails()
        {
            double topRail = TotalHeight - WindowBottomRail - WindowSize;
            Console.WriteLine("\nPart Details (Symmetrical Cast Iron A-Frame Support):");
            Console.WriteLine($"- Total Height: {TotalHeight / InchToMeter:F2}\"");
            Console.WriteLine($"- Max Width (Front): {MaxWidth / InchToMeter:F2}\"");
            Console.WriteLine($"- Base Depth (Side): {BaseDepth / InchToMeter:F2}\"");
            Console.WriteLine($"- Top Depth (Side): {TopDepth / InchToMeter:F2}\" (~2/3\")");
            Console.WriteLine($"- Window Size: {WindowSize / InchToMeter:F2}\" x {WindowSize / InchToMeter:F2}\" (through-all)");
            Console.WriteLine($"- Window Position: {topRail / InchToMeter:F2}\" top rail, {WindowBottomRail / InchToMeter:F2}\" bottom rail");
            Console.WriteLine($"- Window Corner Radius: {WindowCornerRadius / InchToMeter:F3}\"");
            Console.WriteLine($"- Mounting Hole Diameter: {MountingHoleDiameter / InchToMeter:F4}\"");
            Console.WriteLine($"- External Fillet Radius: {ExternalFilletRadius / InchToMeter:F3}\"");
            Console.WriteLine("- Vertical cross section shows I-beam shape");
        }
    }
}
