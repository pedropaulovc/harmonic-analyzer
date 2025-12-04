#nullable disable
using System;
using System.Collections.Generic;

namespace SolidWorksRenders.SketchExtraction
{
    /// <summary>
    /// Root container for extracted part data
    /// </summary>
    public class PartData
    {
        public string Name { get; set; }
        public string SourceFile { get; set; }
        public DateTime ExtractionDate { get; set; }
        public List<FeatureData> Features { get; set; } = new List<FeatureData>();
    }

    /// <summary>
    /// Base class for all feature types
    /// </summary>
    public abstract class FeatureData
    {
        public string Name { get; set; }
        public string TypeName { get; set; }
    }

    /// <summary>
    /// Sketch feature containing geometry, relations, and dimensions
    /// </summary>
    public class SketchFeatureData : FeatureData
    {
        public bool Is3D { get; set; }
        public string ReferencePlane { get; set; }
        public List<LineData> Lines { get; set; } = new List<LineData>();
        public List<ArcData> Arcs { get; set; } = new List<ArcData>();
        public List<CircleData> Circles { get; set; } = new List<CircleData>();
        public List<SplineData> Splines { get; set; } = new List<SplineData>();
        public List<EllipseData> Ellipses { get; set; } = new List<EllipseData>();
        public List<PointData> Points { get; set; } = new List<PointData>();
        public List<RelationData> Relations { get; set; } = new List<RelationData>();
        public List<DimensionData> Dimensions { get; set; } = new List<DimensionData>();
    }

    /// <summary>
    /// Extrusion/Boss feature data
    /// </summary>
    public class ExtrusionFeatureData : FeatureData
    {
        public string SketchName { get; set; }
        public string EndCondition { get; set; }  // Blind, ThroughAll, MidPlane, etc.
        public double Depth { get; set; }         // in inches
        public bool IsCut { get; set; }
        public bool IsThin { get; set; }
        public double ThinWallThickness { get; set; }
        public string Direction { get; set; }     // Single, Both, MidPlane
    }

    /// <summary>
    /// Fillet feature data
    /// </summary>
    public class FilletFeatureData : FeatureData
    {
        public double Radius { get; set; }        // in inches
        public bool IsVariableRadius { get; set; }
        public int EdgeCount { get; set; }
    }

    /// <summary>
    /// Chamfer feature data
    /// </summary>
    public class ChamferFeatureData : FeatureData
    {
        public double Distance { get; set; }      // in inches
        public double Angle { get; set; }         // in degrees
        public int EdgeCount { get; set; }
    }

    /// <summary>
    /// Shell feature data
    /// </summary>
    public class ShellFeatureData : FeatureData
    {
        public double Thickness { get; set; }     // in inches
        public int RemovedFaceCount { get; set; }
    }

    /// <summary>
    /// Generic/unsupported feature placeholder
    /// </summary>
    public class GenericFeatureData : FeatureData
    {
        public string Description { get; set; }
    }

    /// <summary>
    /// 3D point coordinates
    /// </summary>
    public class PointData
    {
        public int Id { get; set; }
        public double X { get; set; }
        public double Y { get; set; }
        public double Z { get; set; }

        public PointData() { }
        public PointData(double x, double y, double z, int id = 0)
        {
            X = x; Y = y; Z = z; Id = id;
        }
    }

    /// <summary>
    /// Line segment data
    /// </summary>
    public class LineData
    {
        public int Id { get; set; }
        public bool IsConstruction { get; set; }
        public PointData Start { get; set; }
        public PointData End { get; set; }
    }

    /// <summary>
    /// Arc segment data
    /// </summary>
    public class ArcData
    {
        public int Id { get; set; }
        public bool IsConstruction { get; set; }
        public PointData Center { get; set; }
        public PointData Start { get; set; }
        public PointData End { get; set; }
        public double Radius { get; set; }
        public string Direction { get; set; }  // "CW" or "CCW"
    }

    /// <summary>
    /// Full circle data
    /// </summary>
    public class CircleData
    {
        public int Id { get; set; }
        public bool IsConstruction { get; set; }
        public PointData Center { get; set; }
        public double Radius { get; set; }
    }

    /// <summary>
    /// Spline curve data
    /// </summary>
    public class SplineData
    {
        public int Id { get; set; }
        public bool IsConstruction { get; set; }
        public int Degree { get; set; }
        public List<PointData> ControlPoints { get; set; } = new List<PointData>();
    }

    /// <summary>
    /// Ellipse data
    /// </summary>
    public class EllipseData
    {
        public int Id { get; set; }
        public bool IsConstruction { get; set; }
        public PointData Center { get; set; }
        public PointData MajorAxisEnd { get; set; }
        public PointData MinorAxisEnd { get; set; }
        public PointData Start { get; set; }
        public PointData End { get; set; }
    }

    /// <summary>
    /// Sketch relation/constraint data
    /// </summary>
    public class RelationData
    {
        public string Type { get; set; }
        public List<EntityRef> Entities { get; set; } = new List<EntityRef>();
    }

    /// <summary>
    /// Reference to a sketch entity
    /// </summary>
    public class EntityRef
    {
        public string EntityType { get; set; }  // Line, Arc, Circle, Point, etc.
        public int EntityId { get; set; }

        public EntityRef() { }
        public EntityRef(string type, int id)
        {
            EntityType = type;
            EntityId = id;
        }

        public override string ToString() => $"{EntityType}:{EntityId}";
    }

    /// <summary>
    /// Dimension data
    /// </summary>
    public class DimensionData
    {
        public string Name { get; set; }
        public string Type { get; set; }      // Linear, Angular, Radial, Diameter
        public double Value { get; set; }     // in inches or degrees
        public List<EntityRef> Entities { get; set; } = new List<EntityRef>();
    }
}
