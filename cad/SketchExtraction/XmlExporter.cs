using System;
using System.IO;
using System.Xml;

namespace SolidWorksRenders.SketchExtraction
{
    /// <summary>
    /// Exports extracted part data to XML format
    /// </summary>
    public static class XmlExporter
    {
        /// <summary>
        /// Export PartData to an XML file
        /// </summary>
        public static void Export(PartData data, string outputPath)
        {
            var settings = new XmlWriterSettings
            {
                Indent = true,
                IndentChars = "  ",
                NewLineChars = Environment.NewLine,
                NewLineHandling = NewLineHandling.Replace
            };

            using (var writer = XmlWriter.Create(outputPath, settings))
            {
                writer.WriteStartDocument();
                WritePartData(writer, data);
                writer.WriteEndDocument();
            }
        }

        private static void WritePartData(XmlWriter writer, PartData data)
        {
            writer.WriteStartElement("Part");
            writer.WriteAttributeString("name", data.Name);
            writer.WriteAttributeString("unit", "inches");

            writer.WriteElementString("SourceFile", data.SourceFile);
            writer.WriteElementString("ExtractionDate", data.ExtractionDate.ToString("o"));

            writer.WriteStartElement("Features");
            foreach (var feature in data.Features)
            {
                WriteFeature(writer, feature);
            }
            writer.WriteEndElement(); // Features

            writer.WriteEndElement(); // Part
        }

        private static void WriteFeature(XmlWriter writer, FeatureData feature)
        {
            switch (feature)
            {
                case SketchFeatureData sketch:
                    WriteSketch(writer, sketch);
                    break;
                case ExtrusionFeatureData extrusion:
                    WriteExtrusion(writer, extrusion);
                    break;
                case FilletFeatureData fillet:
                    WriteFillet(writer, fillet);
                    break;
                case ChamferFeatureData chamfer:
                    WriteChamfer(writer, chamfer);
                    break;
                case ShellFeatureData shell:
                    WriteShell(writer, shell);
                    break;
                case GenericFeatureData generic:
                    WriteGeneric(writer, generic);
                    break;
            }
        }

        private static void WriteSketch(XmlWriter writer, SketchFeatureData sketch)
        {
            writer.WriteStartElement("Sketch");
            writer.WriteAttributeString("name", sketch.Name);
            if (!string.IsNullOrEmpty(sketch.ReferencePlane))
                writer.WriteAttributeString("plane", sketch.ReferencePlane);
            if (sketch.Is3D)
                writer.WriteAttributeString("is3D", "true");

            // Lines
            if (sketch.Lines.Count > 0)
            {
                writer.WriteStartElement("Lines");
                foreach (var line in sketch.Lines)
                {
                    writer.WriteStartElement("Line");
                    writer.WriteAttributeString("id", line.Id.ToString());
                    if (line.IsConstruction)
                        writer.WriteAttributeString("construction", "true");
                    WritePoint(writer, "Start", line.Start);
                    WritePoint(writer, "End", line.End);
                    writer.WriteEndElement();
                }
                writer.WriteEndElement();
            }

            // Arcs
            if (sketch.Arcs.Count > 0)
            {
                writer.WriteStartElement("Arcs");
                foreach (var arc in sketch.Arcs)
                {
                    writer.WriteStartElement("Arc");
                    writer.WriteAttributeString("id", arc.Id.ToString());
                    if (arc.IsConstruction)
                        writer.WriteAttributeString("construction", "true");
                    writer.WriteAttributeString("radius", FormatDouble(arc.Radius));
                    writer.WriteAttributeString("direction", arc.Direction);
                    WritePoint(writer, "Center", arc.Center);
                    WritePoint(writer, "Start", arc.Start);
                    WritePoint(writer, "End", arc.End);
                    writer.WriteEndElement();
                }
                writer.WriteEndElement();
            }

            // Circles
            if (sketch.Circles.Count > 0)
            {
                writer.WriteStartElement("Circles");
                foreach (var circle in sketch.Circles)
                {
                    writer.WriteStartElement("Circle");
                    writer.WriteAttributeString("id", circle.Id.ToString());
                    if (circle.IsConstruction)
                        writer.WriteAttributeString("construction", "true");
                    writer.WriteAttributeString("radius", FormatDouble(circle.Radius));
                    WritePoint(writer, "Center", circle.Center);
                    writer.WriteEndElement();
                }
                writer.WriteEndElement();
            }

            // Splines
            if (sketch.Splines.Count > 0)
            {
                writer.WriteStartElement("Splines");
                foreach (var spline in sketch.Splines)
                {
                    writer.WriteStartElement("Spline");
                    writer.WriteAttributeString("id", spline.Id.ToString());
                    if (spline.IsConstruction)
                        writer.WriteAttributeString("construction", "true");
                    writer.WriteAttributeString("degree", spline.Degree.ToString());
                    writer.WriteStartElement("ControlPoints");
                    foreach (var pt in spline.ControlPoints)
                    {
                        WritePoint(writer, "Point", pt);
                    }
                    writer.WriteEndElement();
                    writer.WriteEndElement();
                }
                writer.WriteEndElement();
            }

            // Ellipses
            if (sketch.Ellipses.Count > 0)
            {
                writer.WriteStartElement("Ellipses");
                foreach (var ellipse in sketch.Ellipses)
                {
                    writer.WriteStartElement("Ellipse");
                    writer.WriteAttributeString("id", ellipse.Id.ToString());
                    if (ellipse.IsConstruction)
                        writer.WriteAttributeString("construction", "true");
                    WritePoint(writer, "Center", ellipse.Center);
                    WritePoint(writer, "MajorAxisEnd", ellipse.MajorAxisEnd);
                    WritePoint(writer, "MinorAxisEnd", ellipse.MinorAxisEnd);
                    if (ellipse.Start != null)
                        WritePoint(writer, "Start", ellipse.Start);
                    if (ellipse.End != null)
                        WritePoint(writer, "End", ellipse.End);
                    writer.WriteEndElement();
                }
                writer.WriteEndElement();
            }

            // Points
            if (sketch.Points.Count > 0)
            {
                writer.WriteStartElement("Points");
                foreach (var pt in sketch.Points)
                {
                    WritePoint(writer, "Point", pt);
                }
                writer.WriteEndElement();
            }

            // Relations
            if (sketch.Relations.Count > 0)
            {
                writer.WriteStartElement("Relations");
                foreach (var rel in sketch.Relations)
                {
                    writer.WriteStartElement("Relation");
                    writer.WriteAttributeString("type", rel.Type);
                    writer.WriteAttributeString("entities", string.Join(",", rel.Entities));
                    writer.WriteEndElement();
                }
                writer.WriteEndElement();
            }

            // Dimensions
            if (sketch.Dimensions.Count > 0)
            {
                writer.WriteStartElement("Dimensions");
                foreach (var dim in sketch.Dimensions)
                {
                    writer.WriteStartElement("Dimension");
                    writer.WriteAttributeString("name", dim.Name ?? "");
                    writer.WriteAttributeString("type", dim.Type);
                    writer.WriteAttributeString("value", FormatDouble(dim.Value));
                    writer.WriteAttributeString("entities", string.Join(",", dim.Entities));
                    writer.WriteEndElement();
                }
                writer.WriteEndElement();
            }

            writer.WriteEndElement(); // Sketch
        }

        private static void WriteExtrusion(XmlWriter writer, ExtrusionFeatureData extrusion)
        {
            writer.WriteStartElement(extrusion.IsCut ? "Cut" : "Extrusion");
            writer.WriteAttributeString("name", extrusion.Name);
            if (!string.IsNullOrEmpty(extrusion.SketchName))
                writer.WriteAttributeString("sketch", extrusion.SketchName);

            writer.WriteElementString("EndCondition", extrusion.EndCondition);
            if (extrusion.Depth > 0)
                writer.WriteElementString("Depth", FormatDouble(extrusion.Depth));
            if (!string.IsNullOrEmpty(extrusion.Direction))
                writer.WriteElementString("Direction", extrusion.Direction);
            if (extrusion.IsThin)
            {
                writer.WriteElementString("ThinWall", "true");
                writer.WriteElementString("ThinWallThickness", FormatDouble(extrusion.ThinWallThickness));
            }

            writer.WriteEndElement();
        }

        private static void WriteFillet(XmlWriter writer, FilletFeatureData fillet)
        {
            writer.WriteStartElement("Fillet");
            writer.WriteAttributeString("name", fillet.Name);

            writer.WriteElementString("Radius", FormatDouble(fillet.Radius));
            writer.WriteElementString("EdgeCount", fillet.EdgeCount.ToString());
            if (fillet.IsVariableRadius)
                writer.WriteElementString("VariableRadius", "true");

            writer.WriteEndElement();
        }

        private static void WriteChamfer(XmlWriter writer, ChamferFeatureData chamfer)
        {
            writer.WriteStartElement("Chamfer");
            writer.WriteAttributeString("name", chamfer.Name);

            writer.WriteElementString("Distance", FormatDouble(chamfer.Distance));
            if (chamfer.Angle > 0)
                writer.WriteElementString("Angle", FormatDouble(chamfer.Angle));
            writer.WriteElementString("EdgeCount", chamfer.EdgeCount.ToString());

            writer.WriteEndElement();
        }

        private static void WriteShell(XmlWriter writer, ShellFeatureData shell)
        {
            writer.WriteStartElement("Shell");
            writer.WriteAttributeString("name", shell.Name);

            writer.WriteElementString("Thickness", FormatDouble(shell.Thickness));
            writer.WriteElementString("RemovedFaceCount", shell.RemovedFaceCount.ToString());

            writer.WriteEndElement();
        }

        private static void WriteGeneric(XmlWriter writer, GenericFeatureData generic)
        {
            writer.WriteStartElement("Feature");
            writer.WriteAttributeString("name", generic.Name);
            writer.WriteAttributeString("type", generic.TypeName);
            if (!string.IsNullOrEmpty(generic.Description))
                writer.WriteElementString("Description", generic.Description);
            writer.WriteEndElement();
        }

        private static void WritePoint(XmlWriter writer, string elementName, PointData point)
        {
            if (point == null) return;

            writer.WriteStartElement(elementName);
            if (point.Id > 0)
                writer.WriteAttributeString("id", point.Id.ToString());
            writer.WriteAttributeString("x", FormatDouble(point.X));
            writer.WriteAttributeString("y", FormatDouble(point.Y));
            writer.WriteAttributeString("z", FormatDouble(point.Z));
            writer.WriteEndElement();
        }

        private static string FormatDouble(double value)
        {
            // Use reasonable precision, removing trailing zeros
            return value.ToString("G10");
        }
    }
}
