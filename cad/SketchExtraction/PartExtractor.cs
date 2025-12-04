#nullable disable
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
        private readonly ISldWorks _swApp;
        private readonly IModelDoc2 _model;
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

        public PartExtractor(ISldWorks solidWorksApp, IModelDoc2 model)
        {
            _swApp = solidWorksApp ?? throw new ArgumentNullException(nameof(solidWorksApp));
            _model = model ?? throw new ArgumentNullException(nameof(model));
        }

        /// <summary>
        /// Extract all sketch and feature data from the opened model
        /// </summary>
        public PartData Extract()
        {
            string pathName = _model.GetPathName();

            var result = new PartData
            {
                Name = Path.GetFileNameWithoutExtension(pathName),
                SourceFile = pathName,
                ExtractionDate = DateTime.Now
            };

            Console.WriteLine($"Traversing features...");

            // Traverse all features
            IFeature feat = (IFeature)_model.FirstFeature();
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

            Console.WriteLine($"Traversed {featureCount} features ({sketchCount} sketches)");
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
                case "Boss-Extrude":
                case "BossThin":
                    return ExtractExtrusion(feat, isCut: false, isThin: typeName == "BossThin");

                case "Cut":
                case "CutThin":
                case "Cut-Extrude":
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
            object segmentsObj = sketch.GetSketchSegments();
            if (segmentsObj == null) return;

            object[] segments = (object[])segmentsObj;

            foreach (object segObj in segments)
            {
                ISketchSegment seg = (ISketchSegment)segObj;
                if (seg == null) continue;

                object idObj = seg.GetID();
                int[] idArray = idObj as int[];
                int id = idArray != null && idArray.Length > 0 ? idArray[0] : 0;
                bool isConstruction = seg.ConstructionGeometry;

                // Use the correct way to get segment type
                int segTypeInt = seg.GetType();
                swSketchSegments_e segType = (swSketchSegments_e)segTypeInt;

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

            ISketchPoint startPt = (ISketchPoint)line.GetStartPoint2();
            ISketchPoint endPt = (ISketchPoint)line.GetEndPoint2();

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

            ISketchPoint centerPt = (ISketchPoint)arc.GetCenterPoint2();
            ISketchPoint startPt = (ISketchPoint)arc.GetStartPoint2();
            ISketchPoint endPt = (ISketchPoint)arc.GetEndPoint2();
            double radius = arc.GetRadius();
            bool isCircle = arc.IsCircle() != 0;
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

            object pointsObj = spline.GetPoints2();
            if (pointsObj != null)
            {
                object[] points = (object[])pointsObj;
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

            ISketchPoint centerPt = (ISketchPoint)ellipse.GetCenterPoint2();
            ISketchPoint majorPt = (ISketchPoint)ellipse.GetMajorPoint2();
            ISketchPoint minorPt = (ISketchPoint)ellipse.GetMinorPoint2();
            ISketchPoint startPt = (ISketchPoint)ellipse.GetStartPoint2();
            ISketchPoint endPt = (ISketchPoint)ellipse.GetEndPoint2();

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
            object pointsObj = sketch.GetSketchPoints2();
            if (pointsObj == null) return;

            object[] points = (object[])pointsObj;

            foreach (object ptObj in points)
            {
                ISketchPoint pt = (ISketchPoint)ptObj;
                if (pt == null) continue;

                object idObj = pt.GetID();
                int[] idArray = idObj as int[];
                int id = idArray != null && idArray.Length > 0 ? idArray[0] : 0;

                data.Points.Add(ToInchesPoint(pt.X, pt.Y, pt.Z, id));
            }
        }

        private void ExtractRelations(ISketch sketch, SketchFeatureData data)
        {
            ISketchRelationManager relMgr = sketch.RelationManager;
            if (relMgr == null) return;

            object relationsObj = relMgr.GetRelations((int)swSketchRelationFilterType_e.swAll);
            if (relationsObj == null) return;

            object[] relations = (object[])relationsObj;

            foreach (object relObj in relations)
            {
                ISketchRelation rel = (ISketchRelation)relObj;
                if (rel == null) continue;

                int relType = rel.GetRelationType();
                string typeName = GetConstraintTypeName(relType);

                var relData = new RelationData { Type = typeName };

                object entityTypesObj = rel.GetEntitiesType();
                object entitiesObj = rel.GetEntities();

                if (entityTypesObj != null && entitiesObj != null)
                {
                    int[] entityTypes = (int[])entityTypesObj;
                    object[] entities = (object[])entitiesObj;

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
                IDimension dim = (IDimension)dispDim.GetDimension2(0);
                if (dim != null)
                {
                    string dimType = GetDimensionTypeName(dispDim.Type2);

                    // Get dimension value
                    object valObj = dim.GetSystemValue3((int)swInConfigurationOpts_e.swThisConfiguration, null);
                    double value = 0;
                    if (valObj is double[] valArray && valArray.Length > 0)
                    {
                        value = valArray[0];
                    }
                    else if (valObj is double val)
                    {
                        value = val;
                    }

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
            var result = new ExtrusionFeatureData
            {
                Name = feat.Name,
                TypeName = feat.GetTypeName2(),
                IsCut = isCut,
                IsThin = isThin,
                EndCondition = "Unknown",
                Direction = "Single"
            };

            try
            {
                IExtrudeFeatureData2 extData = (IExtrudeFeatureData2)feat.GetDefinition();
                if (extData != null)
                {
                    // Access the extrusion definition
                    extData.AccessSelections(_model, null);

                    result.EndCondition = GetEndConditionName(extData.GetEndCondition(true));
                    result.Depth = Math.Round(ToInches(extData.GetDepth(true)), 6);
                    result.Direction = extData.BothDirections ? "Both" : "Single";

                    if (extData.GetEndCondition(true) == (int)swEndConditions_e.swEndCondMidPlane)
                        result.Direction = "MidPlane";

                    extData.ReleaseSelectionAccess();
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine($"    Warning: Could not extract extrusion details for {feat.Name}: {ex.Message}");
            }

            return result;
        }

        private FilletFeatureData ExtractFillet(IFeature feat)
        {
            var result = new FilletFeatureData
            {
                Name = feat.Name,
                TypeName = feat.GetTypeName2(),
                Radius = 0,
                IsVariableRadius = false,
                EdgeCount = 0
            };

            try
            {
                ISimpleFilletFeatureData2 filletData = (ISimpleFilletFeatureData2)feat.GetDefinition();
                if (filletData != null)
                {
                    filletData.AccessSelections(_model, null);
                    result.Radius = Math.Round(ToInches(filletData.DefaultRadius), 6);
                    filletData.ReleaseSelectionAccess();
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine($"    Warning: Could not extract fillet details for {feat.Name}: {ex.Message}");
            }

            return result;
        }

        private ChamferFeatureData ExtractChamfer(IFeature feat)
        {
            var result = new ChamferFeatureData
            {
                Name = feat.Name,
                TypeName = feat.GetTypeName2(),
                Distance = 0,
                Angle = 45,
                EdgeCount = 0
            };

            try
            {
                IChamferFeatureData2 chamferData = (IChamferFeatureData2)feat.GetDefinition();
                if (chamferData != null)
                {
                    chamferData.AccessSelections(_model, null);
                    // Get edge count for basic info
                    result.EdgeCount = chamferData.GetFaceCount();
                    chamferData.ReleaseSelectionAccess();
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine($"    Warning: Could not extract chamfer details for {feat.Name}: {ex.Message}");
            }

            return result;
        }

        private ShellFeatureData ExtractShell(IFeature feat)
        {
            var result = new ShellFeatureData
            {
                Name = feat.Name,
                TypeName = "Shell",
                Thickness = 0,
                RemovedFaceCount = 0
            };

            try
            {
                IShellFeatureData shellData = (IShellFeatureData)feat.GetDefinition();
                if (shellData != null)
                {
                    shellData.AccessSelections(_model, null);
                    result.Thickness = Math.Round(ToInches(shellData.Thickness), 6);
                    shellData.ReleaseSelectionAccess();
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine($"    Warning: Could not extract shell details for {feat.Name}: {ex.Message}");
            }

            return result;
        }

        #region Helper Methods

        private string GetReferencePlaneName(ISketch sketch)
        {
            try
            {
                int refType = 0;
                object refEntity = sketch.GetReferenceEntity(ref refType);
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

            try
            {
                switch (entityType)
                {
                    case swSketchRelationEntityTypes_e.swSketchRelationEntityType_Point:
                        typeName = "Point";
                        if (entity is ISketchPoint pt)
                        {
                            object idObj = pt.GetID();
                            int[] idArr = idObj as int[];
                            id = idArr != null && idArr.Length > 0 ? idArr[0] : 0;
                        }
                        break;

                    case swSketchRelationEntityTypes_e.swSketchRelationEntityType_Line:
                        typeName = "Line";
                        if (entity is ISketchSegment lineSeg)
                        {
                            object idObj = lineSeg.GetID();
                            int[] idArr = idObj as int[];
                            id = idArr != null && idArr.Length > 0 ? idArr[0] : 0;
                        }
                        break;

                    case swSketchRelationEntityTypes_e.swSketchRelationEntityType_Arc:
                        typeName = "Arc";
                        if (entity is ISketchSegment arcSeg)
                        {
                            object idObj = arcSeg.GetID();
                            int[] idArr = idObj as int[];
                            id = idArr != null && idArr.Length > 0 ? idArr[0] : 0;
                        }
                        break;

                    case swSketchRelationEntityTypes_e.swSketchRelationEntityType_Ellipse:
                        typeName = "Ellipse";
                        if (entity is ISketchSegment ellipseSeg)
                        {
                            object idObj = ellipseSeg.GetID();
                            int[] idArr = idObj as int[];
                            id = idArr != null && idArr.Length > 0 ? idArr[0] : 0;
                        }
                        break;

                    case swSketchRelationEntityTypes_e.swSketchRelationEntityType_Spline:
                        typeName = "Spline";
                        if (entity is ISketchSegment splineSeg)
                        {
                            object idObj = splineSeg.GetID();
                            int[] idArr = idObj as int[];
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
            }
            catch { }

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
