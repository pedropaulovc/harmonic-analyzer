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

            // Get the sketch
            swModel.ForceRebuild3(false);
            IFeature plateSketch = swModelExt.GetLastFeatureAdded();
            string sketchName = plateSketch.Name;
            Console.WriteLine($"DEBUG: Coefficients plate sketch name: {sketchName}");

            // Select sketch for extrusion
            selected = swModelExt.SelectByID2(
                Name: sketchName,
                Type: "SKETCH",
                X: 0, Y: 0, Z: 0,
                Append: false,
                Mark: 0,
                Callout: null,
                SelectOption: 0);

            if (!selected)
                throw new InvalidOperationException($"Failed to select coefficients plate sketch '{sketchName}' for extrusion");

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

            // Add appearance (green color)
            // Note: SolidWorks API appearance is complex; skipping for now
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
            string sketchName = cylinderSketch.Name;
            Console.WriteLine($"DEBUG: Cylinder sketch name: {sketchName}");

            selected = swModelExt.SelectByID2(
                Name: sketchName,
                Type: "SKETCH",
                X: 0, Y: 0, Z: 0,
                Append: false,
                Mark: 0,
                Callout: null,
                SelectOption: 0);

            if (!selected)
                throw new InvalidOperationException($"Failed to select cylinder sketch '{sketchName}' for extrusion");

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

            // Create first edge rib
            CreateSingleEdgeRib(swModel, swSketchMgr, swFeatMgr, swModelExt,
                cx, cz, arcTop, CoefficientsPlateLength / 2 - RibThickness, false);

            // Create second edge rib at opposite end
            CreateSingleEdgeRib(swModel, swSketchMgr, swFeatMgr, swModelExt,
                cx, cz, arcTop, -(CoefficientsPlateLength / 2 - RibThickness), true);
        }

        /// <summary>
        /// Creates a single edge rib at the specified Y offset
        /// </summary>
        private void CreateSingleEdgeRib(IModelDoc2 swModel, ISketchManager swSketchMgr,
            IFeatureManager swFeatMgr, IModelDocExtension swModelExt,
            double cx, double cz, double arcTop, double yOffset, bool flipDir)
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
            string sketchName = ribSketch.Name;
            Console.WriteLine($"DEBUG: Edge rib sketch name: {sketchName}");

            selected = swModelExt.SelectByID2(
                Name: sketchName,
                Type: "SKETCH",
                X: 0, Y: 0, Z: 0,
                Append: false,
                Mark: 0,
                Callout: null,
                SelectOption: 0);

            if (!selected)
                throw new InvalidOperationException($"Failed to select edge rib sketch '{sketchName}' for extrusion");

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
                selected = swModelExt.SelectByID2(sketchName, "SKETCH", 0, 0, 0, false, 0, null, 0);
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

            Console.WriteLine($"DEBUG: Edge rib feature name: {ribFeature.Name}");
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
            string sketchName = summationSketch.Name;
            Console.WriteLine($"DEBUG: Summation plate sketch name: {sketchName}");

            selected = swModelExt.SelectByID2(
                Name: sketchName,
                Type: "SKETCH",
                X: 0, Y: 0, Z: 0,
                Append: false,
                Mark: 0,
                Callout: null,
                SelectOption: 0);

            if (!selected)
                throw new InvalidOperationException($"Failed to select summation plate sketch '{sketchName}' for extrusion");

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
            string sketchName = anchorSketch.Name;
            Console.WriteLine($"DEBUG: Summation anchor sketch name: {sketchName}");

            selected = swModelExt.SelectByID2(
                Name: sketchName,
                Type: "SKETCH",
                X: 0, Y: 0, Z: 0,
                Append: false,
                Mark: 0,
                Callout: null,
                SelectOption: 0);

            if (!selected)
                throw new InvalidOperationException($"Failed to select summation anchor sketch '{sketchName}' for extrusion");

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
        }

        /// <summary>
        /// Creates the middle rib: elongated diamond with rounded corners near cylinder
        /// Sketch on XZ plane (Front Plane)
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
            swSketchMgr.AddToDB = true;

            // KCL middle rib profile (elongated diamond with rounded corners):
            // arcAngleOffset = 45deg
            // arcOffsetX = arcRadius * sin(45) = arcRadius * 0.7071
            // arcOffsetZ = arcRadius * cos(45) = arcRadius * 0.7071

            double arcAngle = Math.PI / 4;  // 45 degrees
            double arcOffsetX = arcRadius * Math.Sin(arcAngle);
            double arcOffsetZ = arcRadius * Math.Cos(arcAngle);

            double cx = 0;  // cylinderCenterX
            double cz = 0;  // cylinderCenterZ

            // Points in the KCL profile:
            // leftVertex: [-coefficientsPlateWidth, 0]
            // upper-left arc start: [-arcOffsetX, arcOffsetZ]
            // top of arc: [0, arcRadius]
            // upper-right arc end: [arcOffsetX, arcOffsetZ]
            // right vertex: [summationPlateTipX, 0]
            // lower-right arc start: [arcOffsetX, -arcOffsetZ]
            // bottom of arc: [0, -arcRadius]
            // lower-left arc end: [-arcOffsetX, -arcOffsetZ]
            // back to leftVertex

            // Line from left vertex to upper-left arc start
            swSketchMgr.CreateLine(
                -CoefficientsPlateWidth, cz, 0,
                cx - arcOffsetX, cz + arcOffsetZ, 0);

            // Arc from upper-left to upper-right through top
            swSketchMgr.Create3PointArc(
                X1: cx - arcOffsetX, Y1: cz + arcOffsetZ, Z1: 0,   // Start
                X2: cx + arcOffsetX, Y2: cz + arcOffsetZ, Z2: 0,   // End
                X3: cx, Y3: cz + arcRadius, Z3: 0);                // Interior (top)

            // Line from upper-right to right vertex
            swSketchMgr.CreateLine(
                cx + arcOffsetX, cz + arcOffsetZ, 0,
                summationPlateTipX, cz, 0);

            // Line from right vertex to lower-right arc start
            swSketchMgr.CreateLine(
                summationPlateTipX, cz, 0,
                cx + arcOffsetX, cz - arcOffsetZ, 0);

            // Arc from lower-right to lower-left through bottom
            swSketchMgr.Create3PointArc(
                X1: cx + arcOffsetX, Y1: cz - arcOffsetZ, Z1: 0,   // Start
                X2: cx - arcOffsetX, Y2: cz - arcOffsetZ, Z2: 0,   // End
                X3: cx, Y3: cz - arcRadius, Z3: 0);                // Interior (bottom)

            // Line from lower-left back to left vertex
            swSketchMgr.CreateLine(
                cx - arcOffsetX, cz - arcOffsetZ, 0,
                -CoefficientsPlateWidth, cz, 0);

            swSketchMgr.AddToDB = false;
            swSketchMgr.InsertSketch(UpdateEditRebuild: true);

            swModel.ForceRebuild3(false);
            IFeature ribSketch = swModelExt.GetLastFeatureAdded();
            string sketchName = ribSketch.Name;
            Console.WriteLine($"DEBUG: Middle rib sketch name: {sketchName}");

            selected = swModelExt.SelectByID2(
                Name: sketchName,
                Type: "SKETCH",
                X: 0, Y: 0, Z: 0,
                Append: false,
                Mark: 0,
                Callout: null,
                SelectOption: 0);

            if (!selected)
                throw new InvalidOperationException($"Failed to select middle rib sketch '{sketchName}' for extrusion");

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
