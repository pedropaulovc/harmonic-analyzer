using System;
using System.Collections.Generic;
using System.IO;
using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swconst;

namespace SolidWorksRenders.SketchExtraction
{
    /// <summary>
    /// Extracts sketch geometry, relations, dimensions, and feature data from SLDPRT files
    /// </summary>
    public class PartExtractor
    {
        private readonly ISldWorks swApp;
        private const double MetersToInches = 39.3700787;

        // Maps swConstraintType_e values to readable names
        private static readonly Dictionary<int, string> ConstraintTypeNames = new Dictionary<int, string>
        {
            { 0, "Invalid" },
            { 1, "Coincident" },
            { 2, "Concentric" },
            { 3, "Colinear" },
            { 4, "Horizontal" },
            { 5, "Vertical" },
            { 6, "Parallel" },
            { 7, "Perpendicular" },
            { 8, "Tangent" },
            { 9, "SameLength" },
            { 10, "SameCurveLength" },
            { 11, "Symmetric" },
            { 12, "Fixed" },
            { 13, "AtIntersect" },
            { 14, "AtMiddle" },
            { 15, "Coradial" },
            { 16, "MergePoints" },
            { 17, "Normal" },
            { 18, "Distance" },
            { 19, "HorizPoints" },
            { 20, "VertPoints" },
            { 21, "Angle" },
            { 22, "Radius" },
            { 23, "Diameter" },
            { 24, "AtPierce" },
        };

        public PartExtractor(ISldWorks solidWorksApp)
        {
            swApp = solidWorksApp ?? throw new ArgumentNullException(nameof(solidWorksApp));
        }

        /// <summary>
        /// Extract all sketch and feature data from a SLDPRT file
        /// </summary>
        public PartData ExtractFromFile(string filePath)
        {
            if (!File.Exists(filePath))
                throw new FileNotFoundException($"Part file not found: {filePath}");

            string extension = Path.GetExtension(filePath).ToUpperInvariant();
            if (extension != ".SLDPRT")
                throw new ArgumentException($"Only SLDPRT files are supported. Got: {extension}");

            Console.WriteLine($"Opening part file: {filePath}");

            int errors = 0;
            int warnings = 0;
            IModelDoc2 model = (IModelDoc2)swApp.OpenDoc6(
                FileName: filePath,
                Type: (int)swDocumentTypes_e.swDocPART,
                Options: (int)swOpenDocOptions_e.swOpenDocOptions_Silent,
                Configuration: "",
                Errors: ref errors,
                Warnings: ref warnings);

            if (model == null)
                throw new InvalidOperationException($"Failed to open '{filePath}'. Errors: {errors}, Warnings: {warnings}");

            Console.WriteLine($"Part opened successfully. Extracting features...");

            var result = new PartData
            {
                Name = Path.GetFileNameWithoutExtension(filePath),
                SourceFile = Path.GetFullPath(filePath),
                ExtractionDate = DateTime.Now
            };

            // Traverse all features
            IFeature feat = (IFeature)model.FirstFeature();
            int featureCount = 0;
            int sketchCount = 0;

            while (feat != null)
            {
                string typeName = feat.GetTypeName2();
                FeatureData featureData = ExtractFeature(feat, typeName);

                if (featureData != null)
                {
                    result.Features.Add(featureData);
                    featureCount++;

                    if (featureData is SketchFeatureData)
                        sketchCount++;
                }

                feat = (IFeature)feat.GetNextFeature();
            }

            Console.WriteLine($"Extracted {featureCount} features ({sketchCount} sketches)");
            return result;
        }

        private FeatureData ExtractFeature(IFeature feat, string typeName)
        {
            switch (typeName)
            {
                case "ProfileFeature":
                case "3DProfileFeature":
                    return ExtractSketch(feat, typeName == "3DProfileFeature");

                case "Boss":
                case "Extrusion":
                case "BossThin":
                    return ExtractExtrusion(feat, isCut: false, isThin: typeName == "BossThin");

                case "Cut":
                case "CutThin":
                    return ExtractExtrusion(feat, isCut: true, isThin: typeName == "CutThin");

                case "Fillet":
                case "Round fillet corner":
                    return ExtractFillet(feat);

                case "Chamfer":
                    return ExtractChamfer(feat);

                case "Shell":
                    return ExtractShell(feat);

                // Skip non-geometry features
                case "OriginProfileFeature":
                case "RefPlane":
                case "RefAxis":
                case "RefPoint":
                case "MaterialFolder":
                case "HistoryFolder":
                case "SolidBodyFolder":
                case "SurfaceBodyFolder":
                    return null;

                default:
                    // Return generic feature info for unsupported types
                    if (!typeName.Contains("Folder") && !typeName.StartsWith("Ref"))
                    {
                        return new GenericFeatureData
                        {
                            Name = feat.Name,
                            TypeName = typeName,
                            Description = $"Feature type '{typeName}' not fully supported"
                        };
                    }
                    return null;
            }
        }

        private SketchFeatureData ExtractSketch(IFeature feat, bool is3D)
        {
            ISketch sketch = (ISketch)feat.GetSpecificFeature2();
            if (sketch == null)
                return null;

            var data = new SketchFeatureData
            {
                Name = feat.Name,
                TypeName = is3D ? "3DProfileFeature" : "ProfileFeature",
                Is3D = is3D,
                ReferencePlane = GetReferencePlaneName(sketch)
            };

            Console.WriteLine($"  Extracting sketch: {feat.Name}");

            // Extract geometry from segments
            ExtractGeometry(sketch, data);

            // Extract sketch points
            ExtractPoints(sketch, data);

            // Extract relations
            ExtractRelations(sketch, data);

            // Extract dimensions
            ExtractDimensions(feat, data);

            Console.WriteLine($"    {data.Lines.Count} lines, {data.Arcs.Count} arcs, {data.Circles.Count} circles, " +
                            $"{data.Splines.Count} splines, {data.Relations.Count} relations, {data.Dimensions.Count} dimensions");

            return data;
        }

        private void ExtractGeometry(ISketch sketch, SketchFeatureData data)
        {
            object[] segments = (object[])sketch.GetSketchSegments();
            if (segments == null) return;

            foreach (object segObj in segments)
            {
                ISketchSegment seg = (ISketchSegment)segObj;
                if (seg == null) continue;

                int[] idArray = (int[])seg.GetID();
                int id = idArray != null && idArray.Length > 0 ? idArray[0] : 0;
                bool isConstruction = seg.ConstructionGeometry;

                swSketchSegments_e segType = (swSketchSegments_e)seg.GetType();

                switch (segType)
                {
                    case swSketchSegments_e.swSketchLINE:
                        ExtractLine(seg, id, isConstruction, data);
                        break;

                    case swSketchSegments_e.swSketchARC:
                        ExtractArc(seg, id, isConstruction, data);
                        break;

                    case swSketchSegments_e.swSketchSPLINE:
                        ExtractSpline(seg, id, isConstruction, data);
                        break;

                    case swSketchSegments_e.swSketchELLIPSE:
                        ExtractEllipse(seg, id, isConstruction, data);
                        break;
                }
            }
        }

        private void ExtractLine(ISketchSegment seg, int id, bool isConstruction, SketchFeatureData data)
        {
            ISketchLine line = (ISketchLine)seg;
            if (line == null) return;

            ISketchPoint startPt = line.GetStartPoint2();
            ISketchPoint endPt = line.GetEndPoint2();

            if (startPt != null && endPt != null)
            {
                data.Lines.Add(new LineData
                {
                    Id = id,
                    IsConstruction = isConstruction,
                    Start = ToInchesPoint(startPt.X, startPt.Y, startPt.Z),
                    End = ToInchesPoint(endPt.X, endPt.Y, endPt.Z)
                });
            }
        }

        private void ExtractArc(ISketchSegment seg, int id, bool isConstruction, SketchFeatureData data)
        {
            ISketchArc arc = (ISketchArc)seg;
            if (arc == null) return;

            ISketchPoint centerPt = arc.GetCenterPoint2();
            ISketchPoint startPt = arc.GetStartPoint2();
            ISketchPoint endPt = arc.GetEndPoint2();
            double radius = arc.GetRadius();
            bool isCircle = arc.IsCircle();
            int rotDir = arc.GetRotationDir(); // 1=CCW, -1=CW

            if (centerPt != null)
            {
                if (isCircle)
                {
                    data.Circles.Add(new CircleData
                    {
                        Id = id,
                        IsConstruction = isConstruction,
                        Center = ToInchesPoint(centerPt.X, centerPt.Y, centerPt.Z),
                        Radius = ToInches(radius)
                    });
                }
                else if (startPt != null && endPt != null)
                {
                    data.Arcs.Add(new ArcData
                    {
                        Id = id,
                        IsConstruction = isConstruction,
                        Center = ToInchesPoint(centerPt.X, centerPt.Y, centerPt.Z),
                        Start = ToInchesPoint(startPt.X, startPt.Y, startPt.Z),
                        End = ToInchesPoint(endPt.X, endPt.Y, endPt.Z),
                        Radius = ToInches(radius),
                        Direction = rotDir == 1 ? "CCW" : "CW"
                    });
                }
            }
        }

        private void ExtractSpline(ISketchSegment seg, int id, bool isConstruction, SketchFeatureData data)
        {
            ISketchSpline spline = (ISketchSpline)seg;
            if (spline == null) return;

            var splineData = new SplineData
            {
                Id = id,
                IsConstruction = isConstruction,
                Degree = spline.CurveDegree
            };

            object[] points = (object[])spline.GetPoints2();
            if (points != null)
            {
                foreach (object ptObj in points)
                {
                    ISketchPoint pt = (ISketchPoint)ptObj;
                    if (pt != null)
                    {
                        splineData.ControlPoints.Add(ToInchesPoint(pt.X, pt.Y, pt.Z));
                    }
                }
            }

            data.Splines.Add(splineData);
        }

        private void ExtractEllipse(ISketchSegment seg, int id, bool isConstruction, SketchFeatureData data)
        {
            ISketchEllipse ellipse = (ISketchEllipse)seg;
            if (ellipse == null) return;

            ISketchPoint centerPt = ellipse.GetCenterPoint2();
            ISketchPoint majorPt = ellipse.GetMajorPoint2();
            ISketchPoint minorPt = ellipse.GetMinorPoint2();
            ISketchPoint startPt = ellipse.GetStartPoint2();
            ISketchPoint endPt = ellipse.GetEndPoint2();

            if (centerPt != null)
            {
                data.Ellipses.Add(new EllipseData
                {
                    Id = id,
                    IsConstruction = isConstruction,
                    Center = ToInchesPoint(centerPt.X, centerPt.Y, centerPt.Z),
                    MajorAxisEnd = majorPt != null ? ToInchesPoint(majorPt.X, majorPt.Y, majorPt.Z) : null,
                    MinorAxisEnd = minorPt != null ? ToInchesPoint(minorPt.X, minorPt.Y, minorPt.Z) : null,
                    Start = startPt != null ? ToInchesPoint(startPt.X, startPt.Y, startPt.Z) : null,
                    End = endPt != null ? ToInchesPoint(endPt.X, endPt.Y, endPt.Z) : null
                });
            }
        }

        private void ExtractPoints(ISketch sketch, SketchFeatureData data)
        {
            object[] points = (object[])sketch.GetSketchPoints2();
            if (points == null) return;

            foreach (object ptObj in points)
            {
                ISketchPoint pt = (ISketchPoint)ptObj;
                if (pt == null) continue;

                int[] idArray = (int[])pt.GetID();
                int id = idArray != null && idArray.Length > 0 ? idArray[0] : 0;

                data.Points.Add(ToInchesPoint(pt.X, pt.Y, pt.Z, id));
            }
        }

        private void ExtractRelations(ISketch sketch, SketchFeatureData data)
        {
            ISketchRelationManager relMgr = sketch.RelationManager;
            if (relMgr == null) return;

            object[] relations = (object[])relMgr.GetRelations((int)swSketchRelationFilterType_e.swAll);
            if (relations == null) return;

            foreach (object relObj in relations)
            {
                ISketchRelation rel = (ISketchRelation)relObj;
                if (rel == null) continue;

                int relType = rel.GetRelationType();
                string typeName = GetConstraintTypeName(relType);

                var relData = new RelationData { Type = typeName };

                int[] entityTypes = (int[])rel.GetEntitiesType();
                object[] entities = (object[])rel.GetEntities();

                if (entityTypes != null && entities != null)
                {
                    int count = Math.Min(entityTypes.Length, entities.Length);
                    for (int i = 0; i < count; i++)
                    {
                        EntityRef entityRef = CreateEntityRef((swSketchRelationEntityTypes_e)entityTypes[i], entities[i]);
                        if (entityRef != null)
                            relData.Entities.Add(entityRef);
                    }
                }

                data.Relations.Add(relData);
            }
        }

        private void ExtractDimensions(IFeature feat, SketchFeatureData data)
        {
            IDisplayDimension dispDim = (IDisplayDimension)feat.GetFirstDisplayDimension();
            while (dispDim != null)
            {
                IDimension dim = dispDim.GetDimension2(0);
                if (dim != null)
                {
                    string dimType = GetDimensionTypeName(dispDim.Type2);
                    double value = dim.GetSystemValue3(
                        (int)swInConfigurationOpts_e.swThisConfiguration, null)[0];

                    // Convert value: angles to degrees, distances to inches
                    if (dimType == "Angular")
                        value = value * 180.0 / Math.PI;
                    else
                        value = ToInches(value);

                    data.Dimensions.Add(new DimensionData
                    {
                        Name = dim.FullName,
                        Type = dimType,
                        Value = Math.Round(value, 6)
                    });
                }
                dispDim = (IDisplayDimension)feat.GetNextDisplayDimension(dispDim);
            }
        }

        private ExtrusionFeatureData ExtractExtrusion(IFeature feat, bool isCut, bool isThin)
        {
            IExtrudeFeatureData2 extData = (IExtrudeFeatureData2)feat.GetDefinition();
            if (extData == null)
            {
                return new ExtrusionFeatureData
                {
                    Name = feat.Name,
                    TypeName = feat.GetTypeName2(),
                    IsCut = isCut,
                    IsThin = isThin
                };
            }

            // Access the extrusion definition
            extData.AccessSelections(null, null);

            string endCondition = GetEndConditionName(extData.GetEndCondition(true));
            double depth = ToInches(extData.GetDepth(true));
            string direction = extData.BothDirections ? "Both" : "Single";

            if (extData.GetEndCondition(true) == (int)swEndConditions_e.swEndCondMidPlane)
                direction = "MidPlane";

            var result = new ExtrusionFeatureData
            {
                Name = feat.Name,
                TypeName = feat.GetTypeName2(),
                EndCondition = endCondition,
                Depth = Math.Round(depth, 6),
                IsCut = isCut,
                IsThin = isThin,
                Direction = direction
            };

            if (isThin)
            {
                result.ThinWallThickness = ToInches(extData.ThinWallOneThickness);
            }

            extData.ReleaseSelectionAccess();
            return result;
        }

        private FilletFeatureData ExtractFillet(IFeature feat)
        {
            ISimpleFilletFeatureData2 filletData = (ISimpleFilletFeatureData2)feat.GetDefinition();
            double radius = 0;
            bool isVariable = false;
            int edgeCount = 0;

            if (filletData != null)
            {
                filletData.AccessSelections(null, null);
                radius = ToInches(filletData.DefaultRadius);
                isVariable = filletData.UseMultipleRadii;
                object edges = filletData.FilletedEdges;
                if (edges is object[] edgeArray)
                    edgeCount = edgeArray.Length;
                filletData.ReleaseSelectionAccess();
            }

            return new FilletFeatureData
            {
                Name = feat.Name,
                TypeName = feat.GetTypeName2(),
                Radius = Math.Round(radius, 6),
                IsVariableRadius = isVariable,
                EdgeCount = edgeCount
            };
        }

        private ChamferFeatureData ExtractChamfer(IFeature feat)
        {
            IChamferFeatureData2 chamferData = (IChamferFeatureData2)feat.GetDefinition();
            double distance = 0;
            double angle = 0;
            int edgeCount = 0;

            if (chamferData != null)
            {
                chamferData.AccessSelections(null, null);
                distance = ToInches(chamferData.D1);
                angle = chamferData.Angle * 180.0 / Math.PI;
                object edges = chamferData.EdgeArray;
                if (edges is object[] edgeArray)
                    edgeCount = edgeArray.Length;
                chamferData.ReleaseSelectionAccess();
            }

            return new ChamferFeatureData
            {
                Name = feat.Name,
                TypeName = feat.GetTypeName2(),
                Distance = Math.Round(distance, 6),
                Angle = Math.Round(angle, 2),
                EdgeCount = edgeCount
            };
        }

        private ShellFeatureData ExtractShell(IFeature feat)
        {
            IShellFeatureData shellData = (IShellFeatureData)feat.GetDefinition();
            double thickness = 0;
            int removedFaceCount = 0;

            if (shellData != null)
            {
                shellData.AccessSelections(null, null);
                thickness = ToInches(shellData.Thickness);
                object faces = shellData.FacesForRemovalArray;
                if (faces is object[] faceArray)
                    removedFaceCount = faceArray.Length;
                shellData.ReleaseSelectionAccess();
            }

            return new ShellFeatureData
            {
                Name = feat.Name,
                TypeName = "Shell",
                Thickness = Math.Round(thickness, 6),
                RemovedFaceCount = removedFaceCount
            };
        }

        #region Helper Methods

        private string GetReferencePlaneName(ISketch sketch)
        {
            try
            {
                object refEntity = sketch.GetReferenceEntity(out int refType);
                if (refEntity is IFeature refFeat)
                    return refFeat.Name;
            }
            catch { }
            return null;
        }

        private string GetConstraintTypeName(int type)
        {
            if (ConstraintTypeNames.TryGetValue(type, out string name))
                return name;
            return $"Unknown_{type}";
        }

        private string GetDimensionTypeName(int type)
        {
            switch ((swDimensionType_e)type)
            {
                case swDimensionType_e.swLinearDimension:
                case swDimensionType_e.swHorLinearDimension:
                case swDimensionType_e.swVertLinearDimension:
                    return "Linear";
                case swDimensionType_e.swAngularDimension:
                    return "Angular";
                case swDimensionType_e.swRadialDimension:
                    return "Radial";
                case swDimensionType_e.swDiameterDimension:
                    return "Diameter";
                case swDimensionType_e.swOrdinateDimension:
                    return "Ordinate";
                default:
                    return "Other";
            }
        }

        private string GetEndConditionName(int endCondition)
        {
            switch ((swEndConditions_e)endCondition)
            {
                case swEndConditions_e.swEndCondBlind:
                    return "Blind";
                case swEndConditions_e.swEndCondThroughAll:
                    return "ThroughAll";
                case swEndConditions_e.swEndCondThroughAllBoth:
                    return "ThroughAllBoth";
                case swEndConditions_e.swEndCondMidPlane:
                    return "MidPlane";
                case swEndConditions_e.swEndCondUpToVertex:
                    return "UpToVertex";
                case swEndConditions_e.swEndCondUpToSurface:
                    return "UpToSurface";
                case swEndConditions_e.swEndCondUpToBody:
                    return "UpToBody";
                case swEndConditions_e.swEndCondUpToNext:
                    return "UpToNext";
                case swEndConditions_e.swEndCondOffsetFromSurface:
                    return "OffsetFromSurface";
                default:
                    return $"Unknown_{endCondition}";
            }
        }

        private EntityRef CreateEntityRef(swSketchRelationEntityTypes_e entityType, object entity)
        {
            int id = 0;
            string typeName = "Unknown";

            switch (entityType)
            {
                case swSketchRelationEntityTypes_e.swSketchRelationEntityType_Point:
                    typeName = "Point";
                    if (entity is ISketchPoint pt)
                    {
                        int[] idArr = (int[])pt.GetID();
                        id = idArr != null && idArr.Length > 0 ? idArr[0] : 0;
                    }
                    break;

                case swSketchRelationEntityTypes_e.swSketchRelationEntityType_Line:
                    typeName = "Line";
                    if (entity is ISketchSegment lineSeg)
                    {
                        int[] idArr = (int[])lineSeg.GetID();
                        id = idArr != null && idArr.Length > 0 ? idArr[0] : 0;
                    }
                    break;

                case swSketchRelationEntityTypes_e.swSketchRelationEntityType_Arc:
                    typeName = "Arc";
                    if (entity is ISketchSegment arcSeg)
                    {
                        int[] idArr = (int[])arcSeg.GetID();
                        id = idArr != null && idArr.Length > 0 ? idArr[0] : 0;
                    }
                    break;

                case swSketchRelationEntityTypes_e.swSketchRelationEntityType_Ellipse:
                    typeName = "Ellipse";
                    if (entity is ISketchSegment ellipseSeg)
                    {
                        int[] idArr = (int[])ellipseSeg.GetID();
                        id = idArr != null && idArr.Length > 0 ? idArr[0] : 0;
                    }
                    break;

                case swSketchRelationEntityTypes_e.swSketchRelationEntityType_Spline:
                    typeName = "Spline";
                    if (entity is ISketchSegment splineSeg)
                    {
                        int[] idArr = (int[])splineSeg.GetID();
                        id = idArr != null && idArr.Length > 0 ? idArr[0] : 0;
                    }
                    break;

                case swSketchRelationEntityTypes_e.swSketchRelationEntityType_Plane:
                    typeName = "Plane";
                    break;

                case swSketchRelationEntityTypes_e.swSketchRelationEntityType_Cylinder:
                    typeName = "Cylinder";
                    break;

                default:
                    return null;
            }

            return new EntityRef(typeName, id);
        }

        private double ToInches(double meters)
        {
            return meters * MetersToInches;
        }

        private PointData ToInchesPoint(double x, double y, double z, int id = 0)
        {
            return new PointData
            {
                Id = id,
                X = Math.Round(ToInches(x), 6),
                Y = Math.Round(ToInches(y), 6),
                Z = Math.Round(ToInches(z), 6)
            };
        }

        #endregion
    }
}
