using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swconst;
using System;

namespace SolidWorksRenders
{
    /// <summary>
    /// Creates a summing lever for the harmonic analyzer.
    /// Translated from summing-lever.kcl
    ///
    /// Features:
    /// - Coefficients Plate: rectangular plate with holes for spring connections
    /// - Cylinder: along the long edge, perpendicular to rectangle
    /// - Edge Ribs: at the short edges of the coefficients plate
    /// - Summation Plate: triangular extension with curved sides
    /// - Summation Anchor: cylinder at summation plate tip with center hole
    /// - Middle Rib: elongated diamond with rounded corners near cylinder
    /// </summary>
    public class SummingLever : IPartCreator
    {
        public string PartName => "Summing Lever";
        public string FileName => "summing-lever.sldprt";

        // Dimensions (in inches, converted to meters for SolidWorks API)
        private const double InchToMeter = 0.0254;

        // Coefficients plate parameters
        private const double CoefficientsPlateWidth = 1.75 * InchToMeter;
        private const double CoefficientsPlateLength = 6.0 * InchToMeter;
        private const double PlateThickness = 0.2 * InchToMeter;

        // Cylinder parameters
        private const double CylinderRadius = 0.5 * InchToMeter;

        // Rib parameters
        private const double RibThickness = 0.2 * InchToMeter;
        private const double RibHeight = 0.5 * InchToMeter;
        private const double RibPadding = 0.1 * InchToMeter;

        // Summation plate parameters
        private readonly double summationPlateBaseLength;
        private const double SummationPlateHeight = 3.0 * InchToMeter;
        private const double SummationPlateCurvature = 0.3 * InchToMeter;

        // Summation anchor parameters
        private const double SummationAnchorRadius = 0.375 * InchToMeter;
        private const double SummationAnchorHeight = 0.75 * InchToMeter;

        // Hole pattern parameters
        private const int HoleCount = 20;
        private const double HoleRadius = 0.02 * InchToMeter;
        private const double HoleMargin = 0.2 * InchToMeter;

        // Calculated parameters
        private readonly double holeSpanLength;
        private readonly double holeSpacing;
        private readonly double holeOffsetX;
        private readonly double holeOffsetY;
        private readonly double summationAnchorHoleRadius;
        private readonly double summationPlateTipX;
        private readonly double arcRadius;

        private ISldWorks swApp;

        public SummingLever(ISldWorks solidWorksApp)
        {
            swApp = solidWorksApp ?? throw new ArgumentNullException(nameof(solidWorksApp));

            // Calculate derived parameters
            summationPlateBaseLength = CoefficientsPlateLength / 2;
            holeSpanLength = CoefficientsPlateLength - (2 * HoleMargin) - (2 * RibThickness);
            holeSpacing = holeSpanLength / (HoleCount - 1);
            holeOffsetX = -CoefficientsPlateWidth + HoleMargin;
            holeOffsetY = CoefficientsPlateLength / 2 - HoleMargin - RibThickness;
            summationAnchorHoleRadius = 2 * HoleRadius;
            summationPlateTipX = SummationPlateHeight;  // cylinderCenterX is 0
            arcRadius = CylinderRadius + RibPadding;
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

            // Create components in order
            Console.WriteLine("Creating coefficients plate...");
            CreateCoefficientsPlate(swModel);

            Console.WriteLine("Creating cylinder...");
            CreateCylinder(swModel);

            Console.WriteLine("Creating edge ribs...");
            CreateEdgeRibs(swModel);

            Console.WriteLine("Creating summation plate...");
            CreateSummationPlate(swModel);

            Console.WriteLine("Creating summation anchor...");
            CreateSummationAnchor(swModel);

            Console.WriteLine("Creating middle rib...");
            CreateMiddleRib(swModel);

            // Rebuild the model
            swModel.ForceRebuild3(true);

            return swModel;
        }

        /// <summary>
        /// Creates the coefficients plate: rectangular plate with holes for spring connections
        /// Sketch on XY plane (Top Plane), centered at [-coefficientsPlateWidth/2, 0]
        /// </summary>
        private void CreateCoefficientsPlate(IModelDoc2 swModel)
        {
            ISketchManager swSketchMgr = swModel.SketchManager;
            IFeatureManager swFeatMgr = swModel.FeatureManager;
            IModelDocExtension swModelExt = swModel.Extension;

            // Select Top Plane (XY in KCL)
            bool selected = swModelExt.SelectByID2(
                Name: "Top Plane",
                Type: "PLANE",
                X: 0, Y: 0, Z: 0,
                Append: false,
                Mark: 0,
                Callout: null,
                SelectOption: 0);

            if (!selected)
                throw new InvalidOperationException("Failed to select Top Plane for coefficients plate");

            swSketchMgr.InsertSketch(UpdateEditRebuild: true);

            // Enable AddToDB for better performance
            swSketchMgr.AddToDB = true;

            // Create the rectangle centered at [-coefficientsPlateWidth/2, 0]
            // KCL: rectangle(width = coefficientsPlateWidth, height = coefficientsPlateLength, center = [-coefficientsPlateWidth / 2, 0])
            double rectCenterX = -CoefficientsPlateWidth / 2;
            double rectCenterY = 0;

            swSketchMgr.CreateCenterRectangle(
                X1: rectCenterX, Y1: rectCenterY, Z1: 0,
                X2: rectCenterX + CoefficientsPlateWidth / 2, Y2: rectCenterY + CoefficientsPlateLength / 2, Z2: 0);

            // Create hole pattern
            // KCL: holes at [holeOffsetX, -holeOffsetY], pattern linear along Y
            // First hole is at [-coefficientsPlateWidth + holeMargin, -(coefficientsPlateLength/2 - holeMargin - ribThickness)]
            double firstHoleX = holeOffsetX;
            double firstHoleY = -holeOffsetY;

            // Create first hole
            swSketchMgr.CreateCircleByRadius(
                XC: firstHoleX,
                YC: firstHoleY,
                Zc: 0,
                Radius: HoleRadius);

            // Create remaining holes in the pattern
            for (int i = 1; i < HoleCount; i++)
            {
                swSketchMgr.CreateCircleByRadius(
                    XC: firstHoleX,
                    YC: firstHoleY + (i * holeSpacing),
                    Zc: 0,
                    Radius: HoleRadius);
            }

            swSketchMgr.AddToDB = false;

            // Exit sketch
            swSketchMgr.InsertSketch(UpdateEditRebuild: true);

            // Get the sketch and rename it
            swModel.ForceRebuild3(false);
            IFeature plateSketch = swModelExt.GetLastFeatureAdded();
            plateSketch.Name = "Coefficients Plate Sketch";
            Console.WriteLine($"DEBUG: Renamed sketch to: {plateSketch.Name}");

            // Select sketch for extrusion
            selected = swModelExt.SelectByID2(
                Name: plateSketch.Name,
                Type: "SKETCH",
                X: 0, Y: 0, Z: 0,
                Append: false,
                Mark: 0,
                Callout: null,
                SelectOption: 0);

            if (!selected)
                throw new InvalidOperationException($"Failed to select coefficients plate sketch for extrusion");

            // Extrude symmetric (both directions)
            IFeature extrudeFeature = swFeatMgr.FeatureExtrusion3(
                Sd: false,                                         // Both directions (symmetric)
                Flip: false,
                Dir: false,
                T1: (int)swEndConditions_e.swEndCondBlind,
                T2: (int)swEndConditions_e.swEndCondBlind,
                D1: PlateThickness / 2,                            // Half in each direction for symmetric
                D2: PlateThickness / 2,
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
                throw new InvalidOperationException("Failed to extrude coefficients plate");

            extrudeFeature.Name = "Coefficients Plate";
        }

        /// <summary>
        /// Creates the cylinder along the long edge (perpendicular to rectangle)
        /// Sketch on XZ plane (Front Plane)
        /// </summary>
        private void CreateCylinder(IModelDoc2 swModel)
        {
            ISketchManager swSketchMgr = swModel.SketchManager;
            IFeatureManager swFeatMgr = swModel.FeatureManager;
            IModelDocExtension swModelExt = swModel.Extension;

            // Select Front Plane (XZ in KCL)
            bool selected = swModelExt.SelectByID2(
                Name: "Front Plane",
                Type: "PLANE",
                X: 0, Y: 0, Z: 0,
                Append: false,
                Mark: 0,
                Callout: null,
                SelectOption: 0);

            if (!selected)
                throw new InvalidOperationException("Failed to select Front Plane for cylinder");

            swSketchMgr.InsertSketch(UpdateEditRebuild: true);

            // Create circle at origin (cylinderCenterX=0, cylinderCenterZ=0)
            swSketchMgr.CreateCircleByRadius(
                XC: 0,
                YC: 0,
                Zc: 0,
                Radius: CylinderRadius);

            swSketchMgr.InsertSketch(UpdateEditRebuild: true);

            swModel.ForceRebuild3(false);
            IFeature cylinderSketch = swModelExt.GetLastFeatureAdded();
            cylinderSketch.Name = "Pivot Cylinder Sketch";
            Console.WriteLine($"DEBUG: Renamed sketch to: {cylinderSketch.Name}");

            selected = swModelExt.SelectByID2(
                Name: cylinderSketch.Name,
                Type: "SKETCH",
                X: 0, Y: 0, Z: 0,
                Append: false,
                Mark: 0,
                Callout: null,
                SelectOption: 0);

            if (!selected)
                throw new InvalidOperationException("Failed to select cylinder sketch for extrusion");

            // Extrude symmetric along Y axis
            IFeature extrudeFeature = swFeatMgr.FeatureExtrusion3(
                Sd: false,                                         // Both directions
                Flip: false,
                Dir: false,
                T1: (int)swEndConditions_e.swEndCondBlind,
                T2: (int)swEndConditions_e.swEndCondBlind,
                D1: CoefficientsPlateLength / 2,
                D2: CoefficientsPlateLength / 2,
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
                throw new InvalidOperationException("Failed to extrude cylinder");

            extrudeFeature.Name = "Pivot Cylinder";
        }

        /// <summary>
        /// Creates the edge ribs at short edges of coefficients plate.
        /// Sketch on XZ plane (Front Plane)
        /// The profile is a triangular shape with an arc wrapping around the cylinder.
        /// </summary>
        private void CreateEdgeRibs(IModelDoc2 swModel)
        {
            ISketchManager swSketchMgr = swModel.SketchManager;
            IFeatureManager swFeatMgr = swModel.FeatureManager;
            IModelDocExtension swModelExt = swModel.Extension;

            double cx = 0;  // cylinderCenterX
            double cz = 0;  // cylinderCenterZ
            double arcTop = CylinderRadius + RibPadding;

            // Create first edge rib (front)
            CreateSingleEdgeRib(swModel, swSketchMgr, swFeatMgr, swModelExt,
                cx, cz, arcTop, CoefficientsPlateLength / 2 - RibThickness, false, "Front");

            // Create second edge rib at opposite end (back)
            CreateSingleEdgeRib(swModel, swSketchMgr, swFeatMgr, swModelExt,
                cx, cz, arcTop, -(CoefficientsPlateLength / 2 - RibThickness), true, "Back");
        }

        /// <summary>
        /// Creates a single edge rib at the specified Y offset
        /// </summary>
        private void CreateSingleEdgeRib(IModelDoc2 swModel, ISketchManager swSketchMgr,
            IFeatureManager swFeatMgr, IModelDocExtension swModelExt,
            double cx, double cz, double arcTop, double yOffset, bool flipDir, string position)
        {
            // Select Front Plane (XZ in KCL)
            bool selected = swModelExt.SelectByID2(
                Name: "Front Plane",
                Type: "PLANE",
                X: 0, Y: 0, Z: 0,
                Append: false,
                Mark: 0,
                Callout: null,
                SelectOption: 0);

            if (!selected)
                throw new InvalidOperationException("Failed to select Front Plane for edge rib");

            swSketchMgr.InsertSketch(UpdateEditRebuild: true);
            swSketchMgr.AddToDB = true;

            // Edge rib profile: triangular shape with curved side wrapping cylinder
            // Vertices:
            // A: [0, arcTop] - top point on arc
            // B: [-coefficientsPlateWidth, 0] - left vertex (tip of triangle)
            // C: [0, -arcTop] - bottom point on arc
            // Arc from C back to A through right side (wrapping around cylinder)

            // Line from top (A) to left corner (B)
            swSketchMgr.CreateLine(cx, cz + arcTop, 0, cx - CoefficientsPlateWidth, cz, 0);

            // Line from left corner (B) to bottom (C)
            swSketchMgr.CreateLine(cx - CoefficientsPlateWidth, cz, 0, cx, cz - arcTop, 0);

            // Arc from bottom (C) back to top (A) through right side
            // 3-point arc: start, end, interior point
            swSketchMgr.Create3PointArc(
                X1: cx, Y1: cz - arcTop, Z1: 0,              // Start point (C)
                X2: cx, Y2: cz + arcTop, Z2: 0,              // End point (A)
                X3: cx + arcTop, Y3: cz, Z3: 0);             // Interior point (right side)

            swSketchMgr.AddToDB = false;
            swSketchMgr.InsertSketch(UpdateEditRebuild: true);

            swModel.ForceRebuild3(false);
            IFeature ribSketch = swModelExt.GetLastFeatureAdded();
            ribSketch.Name = $"Edge Rib {position} Sketch";
            Console.WriteLine($"DEBUG: Renamed sketch to: {ribSketch.Name}");

            selected = swModelExt.SelectByID2(
                Name: ribSketch.Name,
                Type: "SKETCH",
                X: 0, Y: 0, Z: 0,
                Append: false,
                Mark: 0,
                Callout: null,
                SelectOption: 0);

            if (!selected)
                throw new InvalidOperationException($"Failed to select edge rib sketch for extrusion");

            // Extrude the rib with offset from sketch plane
            IFeature ribFeature = swFeatMgr.FeatureExtrusion3(
                Sd: true,
                Flip: false,
                Dir: flipDir,
                T1: (int)swEndConditions_e.swEndCondBlind,
                T2: (int)swEndConditions_e.swEndCondBlind,
                D1: RibThickness,
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
                Merge: true,
                UseFeatScope: false,
                UseAutoSelect: true,
                T0: (int)swStartConditions_e.swStartOffset,
                StartOffset: Math.Abs(yOffset),
                FlipStartOffset: yOffset < 0);

            if (ribFeature == null)
            {
                // Diagnose the failure
                selected = swModelExt.SelectByID2(ribSketch.Name, "SKETCH", 0, 0, 0, false, 0, null, 0);
                if (selected)
                {
                    ISelectionMgr selMgr = (ISelectionMgr)swModel.SelectionManager;
                    ISketch sketch = (ISketch)((IFeature)selMgr.GetSelectedObject6(1, -1)).GetSpecificFeature2();
                    int openCount = 0, closedCount = 0;
                    int statusCode = sketch.CheckFeatureUse(
                        (int)swSketchCheckFeatureProfileUsage_e.swSketchCheckFeature_BASEEXTRUDE,
                        ref openCount,
                        ref closedCount);
                    swSketchCheckFeatureStatus_e status = (swSketchCheckFeatureStatus_e)statusCode;
                    Console.WriteLine($"DEBUG: Sketch check status: {status}, Open: {openCount}, Closed: {closedCount}");
                }
                throw new InvalidOperationException($"Failed to extrude edge rib (yOffset={yOffset})");
            }

            ribFeature.Name = $"Edge Rib {position}";
            Console.WriteLine($"DEBUG: Renamed feature to: {ribFeature.Name}");
        }

        /// <summary>
        /// Creates the summation plate: triangular extension with curved sides
        /// Sketch on XY plane (Top Plane)
        /// </summary>
        private void CreateSummationPlate(IModelDoc2 swModel)
        {
            ISketchManager swSketchMgr = swModel.SketchManager;
            IFeatureManager swFeatMgr = swModel.FeatureManager;
            IModelDocExtension swModelExt = swModel.Extension;

            bool selected = swModelExt.SelectByID2(
                Name: "Top Plane",
                Type: "PLANE",
                X: 0, Y: 0, Z: 0,
                Append: false,
                Mark: 0,
                Callout: null,
                SelectOption: 0);

            if (!selected)
                throw new InvalidOperationException("Failed to select Top Plane for summation plate");

            swSketchMgr.InsertSketch(UpdateEditRebuild: true);
            swSketchMgr.AddToDB = true;

            // KCL summation plate profile:
            // startProfile(at = [cylinderCenterX, -summationPlateBaseLength / 2])
            // line(end = [0, summationPlateBaseLength])
            // arc(interiorAbsolute = [summationPlateHeight/2, summationPlateBaseLength/4 - curvature],
            //     endAbsolute = [summationPlateHeight, summationAnchorRadius])
            // line(end = [0, -summationAnchorRadius * 2])
            // arc(interiorAbsolute = [summationPlateHeight/2, -summationPlateBaseLength/4 + curvature],
            //     endAbsolute = [0, -summationPlateBaseLength/2])
            // close()

            double cx = 0;  // cylinderCenterX
            double baseHalf = summationPlateBaseLength / 2;

            // Point 1: [0, -baseHalf]
            // Point 2: [0, baseHalf]
            // Arc to Point 3: [summationPlateHeight, summationAnchorRadius]
            // Point 4: [summationPlateHeight, -summationAnchorRadius]
            // Arc back to Point 1

            // Line from bottom to top (left edge)
            swSketchMgr.CreateLine(cx, -baseHalf, 0, cx, baseHalf, 0);

            // Arc from top-left to tip-top
            swSketchMgr.Create3PointArc(
                X1: cx, Y1: baseHalf, Z1: 0,                                           // Start
                X2: summationPlateTipX, Y2: SummationAnchorRadius, Z2: 0,              // End
                X3: SummationPlateHeight / 2, Y3: baseHalf / 2 - SummationPlateCurvature, Z3: 0);  // Interior

            // Line across the tip (short edge at anchor)
            swSketchMgr.CreateLine(
                summationPlateTipX, SummationAnchorRadius, 0,
                summationPlateTipX, -SummationAnchorRadius, 0);

            // Arc from tip-bottom back to bottom-left
            swSketchMgr.Create3PointArc(
                X1: summationPlateTipX, Y1: -SummationAnchorRadius, Z1: 0,             // Start
                X2: cx, Y2: -baseHalf, Z2: 0,                                          // End
                X3: SummationPlateHeight / 2, Y3: -baseHalf / 2 + SummationPlateCurvature, Z3: 0);  // Interior

            swSketchMgr.AddToDB = false;
            swSketchMgr.InsertSketch(UpdateEditRebuild: true);

            swModel.ForceRebuild3(false);
            IFeature summationSketch = swModelExt.GetLastFeatureAdded();
            summationSketch.Name = "Summation Plate Sketch";
            Console.WriteLine($"DEBUG: Renamed sketch to: {summationSketch.Name}");

            selected = swModelExt.SelectByID2(
                Name: summationSketch.Name,
                Type: "SKETCH",
                X: 0, Y: 0, Z: 0,
                Append: false,
                Mark: 0,
                Callout: null,
                SelectOption: 0);

            if (!selected)
                throw new InvalidOperationException($"Failed to select summation plate sketch for extrusion");

            // Extrude symmetric
            IFeature extrudeFeature = swFeatMgr.FeatureExtrusion3(
                Sd: false,
                Flip: false,
                Dir: false,
                T1: (int)swEndConditions_e.swEndCondBlind,
                T2: (int)swEndConditions_e.swEndCondBlind,
                D1: PlateThickness / 2,
                D2: PlateThickness / 2,
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
                throw new InvalidOperationException("Failed to extrude summation plate");

            extrudeFeature.Name = "Summation Plate";
        }

        /// <summary>
        /// Creates the summation anchor: cylinder at summation plate tip with center hole
        /// Sketch on XY plane (Top Plane)
        /// </summary>
        private void CreateSummationAnchor(IModelDoc2 swModel)
        {
            ISketchManager swSketchMgr = swModel.SketchManager;
            IFeatureManager swFeatMgr = swModel.FeatureManager;
            IModelDocExtension swModelExt = swModel.Extension;

            bool selected = swModelExt.SelectByID2(
                Name: "Top Plane",
                Type: "PLANE",
                X: 0, Y: 0, Z: 0,
                Append: false,
                Mark: 0,
                Callout: null,
                SelectOption: 0);

            if (!selected)
                throw new InvalidOperationException("Failed to select Top Plane for summation anchor");

            swSketchMgr.InsertSketch(UpdateEditRebuild: true);
            swSketchMgr.AddToDB = true;

            // Outer circle for anchor
            swSketchMgr.CreateCircleByRadius(
                XC: summationPlateTipX,
                YC: 0,
                Zc: 0,
                Radius: SummationAnchorRadius);

            // Inner circle for hole
            swSketchMgr.CreateCircleByRadius(
                XC: summationPlateTipX,
                YC: 0,
                Zc: 0,
                Radius: summationAnchorHoleRadius);

            swSketchMgr.AddToDB = false;
            swSketchMgr.InsertSketch(UpdateEditRebuild: true);

            swModel.ForceRebuild3(false);
            IFeature anchorSketch = swModelExt.GetLastFeatureAdded();
            anchorSketch.Name = "Summation Anchor Sketch";
            Console.WriteLine($"DEBUG: Renamed sketch to: {anchorSketch.Name}");

            selected = swModelExt.SelectByID2(
                Name: anchorSketch.Name,
                Type: "SKETCH",
                X: 0, Y: 0, Z: 0,
                Append: false,
                Mark: 0,
                Callout: null,
                SelectOption: 0);

            if (!selected)
                throw new InvalidOperationException($"Failed to select summation anchor sketch for extrusion");

            // Extrude symmetric
            IFeature extrudeFeature = swFeatMgr.FeatureExtrusion3(
                Sd: false,
                Flip: false,
                Dir: false,
                T1: (int)swEndConditions_e.swEndCondBlind,
                T2: (int)swEndConditions_e.swEndCondBlind,
                D1: SummationAnchorHeight / 2,
                D2: SummationAnchorHeight / 2,
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
                throw new InvalidOperationException("Failed to extrude summation anchor");

            extrudeFeature.Name = "Summation Anchor";
        }

        /// <summary>
        /// Creates the middle rib: elongated diamond with tangent arcs near cylinder
        /// Sketch on XZ plane (Front Plane)
        ///
        /// Uses SolidWorks sketch constraints to make the arcs tangent to the lines.
        /// This lets SolidWorks compute the exact tangent geometry.
        /// </summary>
        private void CreateMiddleRib(IModelDoc2 swModel)
        {
            ISketchManager swSketchMgr = swModel.SketchManager;
            IFeatureManager swFeatMgr = swModel.FeatureManager;
            IModelDocExtension swModelExt = swModel.Extension;

            bool selected = swModelExt.SelectByID2(
                Name: "Front Plane",
                Type: "PLANE",
                X: 0, Y: 0, Z: 0,
                Append: false,
                Mark: 0,
                Callout: null,
                SelectOption: 0);

            if (!selected)
                throw new InvalidOperationException("Failed to select Front Plane for middle rib");

            swSketchMgr.InsertSketch(UpdateEditRebuild: true);

            double cx = 0;  // cylinderCenterX
            double cz = 0;  // cylinderCenterZ
            double r = arcRadius;

            double leftX = -CoefficientsPlateWidth;
            double rightX = summationPlateTipX;

            // Calculate initial tangent points (approximate) for drawing
            double txLeft = (r * r) / leftX;
            double tyLeft = r * Math.Sqrt(1 - (r * r) / (leftX * leftX));
            double txRight = (r * r) / rightX;
            double tyRight = r * Math.Sqrt(1 - (r * r) / (rightX * rightX));

            // Create geometry and capture segment references for constraints
            // Line 1: Left vertex to upper arc region
            ISketchSegment line1 = (ISketchSegment)swSketchMgr.CreateLine(
                leftX, cz, 0,
                cx + txLeft, cz + tyLeft, 0);

            // Arc 1: Upper arc (will be constrained tangent to line1 and line2)
            ISketchSegment arc1 = (ISketchSegment)swSketchMgr.Create3PointArc(
                X1: cx + txLeft, Y1: cz + tyLeft, Z1: 0,
                X2: cx + txRight, Y2: cz + tyRight, Z2: 0,
                X3: cx, Y3: cz + r, Z3: 0);

            // Line 2: Upper arc to right vertex
            ISketchSegment line2 = (ISketchSegment)swSketchMgr.CreateLine(
                cx + txRight, cz + tyRight, 0,
                rightX, cz, 0);

            // Line 3: Right vertex to lower arc region
            ISketchSegment line3 = (ISketchSegment)swSketchMgr.CreateLine(
                rightX, cz, 0,
                cx + txRight, cz - tyRight, 0);

            // Arc 2: Lower arc (will be constrained tangent to line3 and line4)
            ISketchSegment arc2 = (ISketchSegment)swSketchMgr.Create3PointArc(
                X1: cx + txRight, Y1: cz - tyRight, Z1: 0,
                X2: cx + txLeft, Y2: cz - tyLeft, Z2: 0,
                X3: cx, Y3: cz - r, Z3: 0);

            // Line 4: Lower arc back to left vertex
            ISketchSegment line4 = (ISketchSegment)swSketchMgr.CreateLine(
                cx + txLeft, cz - tyLeft, 0,
                leftX, cz, 0);

            // Create a horizontal centerline for symmetry constraint
            ISketchSegment centerLine = (ISketchSegment)swSketchMgr.CreateCenterLine(
                leftX, cz, 0,
                rightX, cz, 0);

            // Apply tangent constraints between lines and arcs
            // Clear selection and apply tangent between line1 and arc1
            swModel.ClearSelection2(true);
            line1.Select4(false, null);
            arc1.Select4(true, null);  // Append to selection
            swModel.SketchAddConstraints("sgTANGENT");

            // Tangent between arc1 and line2
            swModel.ClearSelection2(true);
            arc1.Select4(false, null);
            line2.Select4(true, null);
            swModel.SketchAddConstraints("sgTANGENT");

            // Tangent between line3 and arc2
            swModel.ClearSelection2(true);
            line3.Select4(false, null);
            arc2.Select4(true, null);
            swModel.SketchAddConstraints("sgTANGENT");

            // Tangent between arc2 and line4
            swModel.ClearSelection2(true);
            arc2.Select4(false, null);
            line4.Select4(true, null);
            swModel.SketchAddConstraints("sgTANGENT");

            // Make the two arcs coradial (same center AND same radius)
            swModel.ClearSelection2(true);
            arc1.Select4(false, null);
            arc2.Select4(true, null);
            swModel.SketchAddConstraints("sgCORADIAL");

            // Add symmetry constraints about the horizontal centerline
            // line1 symmetric to line4 about centerline
            swModel.ClearSelection2(true);
            line1.Select4(false, null);
            line4.Select4(true, null);
            centerLine.Select4(true, null);
            swModel.SketchAddConstraints("sgSYMMETRIC");

            // line2 symmetric to line3 about centerline
            swModel.ClearSelection2(true);
            line2.Select4(false, null);
            line3.Select4(true, null);
            centerLine.Select4(true, null);
            swModel.SketchAddConstraints("sgSYMMETRIC");

            swModel.ClearSelection2(true);

            swSketchMgr.AddToDB = false;
            swSketchMgr.InsertSketch(UpdateEditRebuild: true);

            swModel.ForceRebuild3(false);
            IFeature ribSketch = swModelExt.GetLastFeatureAdded();
            ribSketch.Name = "Middle Rib Sketch";
            Console.WriteLine($"DEBUG: Renamed sketch to: {ribSketch.Name}");

            selected = swModelExt.SelectByID2(
                Name: ribSketch.Name,
                Type: "SKETCH",
                X: 0, Y: 0, Z: 0,
                Append: false,
                Mark: 0,
                Callout: null,
                SelectOption: 0);

            if (!selected)
                throw new InvalidOperationException($"Failed to select middle rib sketch for extrusion");

            // Extrude symmetric
            IFeature extrudeFeature = swFeatMgr.FeatureExtrusion3(
                Sd: false,
                Flip: false,
                Dir: false,
                T1: (int)swEndConditions_e.swEndCondBlind,
                T2: (int)swEndConditions_e.swEndCondBlind,
                D1: RibThickness / 2,
                D2: RibThickness / 2,
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
                throw new InvalidOperationException("Failed to extrude middle rib");

            extrudeFeature.Name = "Middle Rib";
        }

        public void PrintPartDetails()
        {
            Console.WriteLine("\nPart Details:");
            Console.WriteLine($"- Coefficients plate: {CoefficientsPlateWidth / InchToMeter}\" x {CoefficientsPlateLength / InchToMeter}\" x {PlateThickness / InchToMeter}\"");
            Console.WriteLine($"- Cylinder radius: {CylinderRadius / InchToMeter}\"");
            Console.WriteLine($"- Rib thickness: {RibThickness / InchToMeter}\"");
            Console.WriteLine($"- Summation plate height: {SummationPlateHeight / InchToMeter}\"");
            Console.WriteLine($"- Summation anchor radius: {SummationAnchorRadius / InchToMeter}\"");
            Console.WriteLine($"- Hole pattern: {HoleCount} holes at {HoleRadius / InchToMeter}\" radius");
        }
    }
}
