using System;
using System.Runtime.InteropServices;
using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swconst;

namespace AmplitudeBar
{
    internal class Program
    {
        // KCL parameters (converted)
        const double barLength = 32.0;           // in
        const double barWidth = 0.25;            // in
        const double barDepth = 0.25;            // in

        const double bottomNotchWidth = 0.125;   // in
        const double bottomNotchHeight = 0.09375; // in (3/32")

        const double topNotchWidth = 0.125;      // in
        const double topNotchHeight = 0.5;       // in

        static void Main(string[] args)
        {
            SldWorks swApp = null;
            ModelDoc2 swModel = null;
            FeatureManager swFeatMgr = null;
            SketchManager skMgr = null;

            try
            {
                // Attach to SolidWorks (or start one)
                try
                {
                    swApp = (SldWorks)Marshal.GetActiveObject(progID: "SldWorks.Application");
                }
                catch (COMException)
                {
                    swApp = new SldWorks();
                }

                if (swApp == null) throw new InvalidOperationException("Could not get SldWorks application.");

                swApp.Visible = true;

                // Create a new part document.
                // NOTE: Replace the template path below with a valid Part template on your machine
                // that uses inches (recommended). Example path often under:
                // C:\ProgramData\SOLIDWORKS\SOLIDWORKS <year>\templates\Part.prtdot
                string templatePath = @"C:\ProgramData\SolidWorks\SOLIDWORKS 2025\templates\Part.prtdot";
                try
                {
                    swModel = swApp.NewDocument(
                        TemplateName: templatePath,
                        PaperSize: (int)swDwgPaperSizes_e.swDwgPaperA0size,
                        Width: 0,
                        Height: 0) as ModelDoc2;
                }
                catch
                {
                    // Try a fallback (rely on SolidWorks default template)
                    swModel = swApp.INewPart() as ModelDoc2;
                }

                if (swModel == null) throw new InvalidOperationException("Could not create new part document.");

                swFeatMgr = swModel.FeatureManager;
                skMgr = swModel.SketchManager;

                // Units: This code assumes the part template is in inches. If not, set template to inches
                // or convert units programmatically before creating geometry.

                // 1) Create base rectangular profile (centered on X, bottom at Y=0 -> top at Y=barLength)
                double halfWidth = barWidth / 2.0;
                swModel.Extension.SelectByID2(
                    Name: "Right Plane",
                    Type: "PLANE",
                    X: 0,
                    Y: 0,
                    Z: 0,
                    Append: false,
                    Mark: 0,
                    Callout: null,
                    SelectOption: 0); // ensure a plane exists
                skMgr.InsertSketch(UpdateEditRebuild: true); // start sketch on default plane (Front/Right selection may vary)

                // Draw rectangle (lines) as a closed profile
                // Coordinates: X across width, Y along length (0..barLength)
                skMgr.CreateLine(
                    X1: -halfWidth, Y1: 0.0, Z1: 0.0,
                    X2: halfWidth, Y2: 0.0, Z2: 0.0);
                skMgr.CreateLine(
                    X1: halfWidth, Y1: 0.0, Z1: 0.0,
                    X2: halfWidth, Y2: barLength, Z2: 0.0);
                skMgr.CreateLine(
                    X1: halfWidth, Y1: barLength, Z1: 0.0,
                    X2: -halfWidth, Y2: barLength, Z2: 0.0);
                skMgr.CreateLine(
                    X1: -halfWidth, Y1: barLength, Z1: 0.0,
                    X2: -halfWidth, Y2: 0.0, Z2: 0.0);

                skMgr.InsertSketch(true); // exit sketch
                // DON'T clear selection here — call extrusion while sketch/profile is selected
                Feature baseFeat = swFeatMgr.FeatureExtrusion2(
                    Sd: true,
                    Flip: false,
                    Dir: false,
                    T1: (int)swEndConditions_e.swEndCondBlind,
                    T2: 0,
                    D1: barDepth,
                    D2: 0.0,
                    Dchk1: false,
                    Dchk2: false,
                    Ddir1: false,
                    Ddir2: false,
                    Dang1: 0.0,
                    Dang2: 0.0,
                    OffsetReverse1: false,
                    OffsetReverse2: false,
                    TranslateSurface1: false,
                    TranslateSurface2: false,
                    Merge: true,
                    UseFeatScope: false,
                    UseAutoSelect: false,
                    T0: (int)swStartConditions_e.swStartSketchPlane,
                    StartOffset: 0.0,
                    false);

                if (baseFeat == null) throw new InvalidOperationException("Base extrusion failed.");

                swModel.ClearSelection2(All: true); // clear only after extrusion completes

                // 3) Create bottom notch sketch and cut-extrude
                // Start a new sketch on the same plane as the original sketch
                skMgr.InsertSketch(true);

                double bnHalfW = bottomNotchWidth / 2.0;
                // rectangle from Y=0 up to bottomNotchHeight
                skMgr.CreateLine(
                    X1: -bnHalfW, Y1: 0.0, Z1: 0.0,
                    X2: bnHalfW, Y2: 0.0, Z2: 0.0);
                skMgr.CreateLine(
                    X1: bnHalfW, Y1: 0.0, Z1: 0.0,
                    X2: bnHalfW, Y2: bottomNotchHeight, Z2: 0.0);
                skMgr.CreateLine(
                    X1: bnHalfW, Y1: bottomNotchHeight, Z1: 0.0,
                    X2: -bnHalfW, Y2: bottomNotchHeight, Z2: 0.0);
                skMgr.CreateLine(
                    X1: -bnHalfW, Y1: bottomNotchHeight, Z1: 0.0,
                    X2: -bnHalfW, Y2: 0.0, Z2: 0.0);

                skMgr.InsertSketch(true);
                swModel.ClearSelection2(true);

                // Cut-extrude the bottom notch using FeatureExtrusion2 as a cut
                Feature bottomCut = swFeatMgr.FeatureExtrusion2(
                    Sd: false,              // cut (false = create cut)
                    Flip: false,             // thin feature
                    Dir: false,             // draft outward
                    T1: (int)swEndConditions_e.swEndCondBlind,
                    T2: 0,
                    D1: bottomNotchHeight + 0.0001, // depth
                    D2: 0.0,
                    Dchk1: false,
                    Dchk2: false,
                    Ddir1: false,
                    Ddir2: false,
                    Dang1: 0.0,
                    Dang2: 0.0,
                    OffsetReverse1: false,
                    OffsetReverse2: false,
                    TranslateSurface1: false,
                    TranslateSurface2: false,
                    Merge: true,
                    UseFeatScope: false,
                    UseAutoSelect: false,
                    T0: (int)swStartConditions_e.swStartSketchPlane,
                    StartOffset: 0.0,
                    false);

                if (bottomCut == null)
                {
                    Console.WriteLine("Warning: bottom notch cut failed.");
                }

                swModel.ClearSelection2(true);

                // 4) Create top notch sketch and cut-extrude
                skMgr.InsertSketch(true);

                double tnHalfW = topNotchWidth / 2.0;
                // top notch rectangle positioned at top: from Y=barLength-topNotchHeight to Y=barLength
                double y0 = barLength - topNotchHeight;
                skMgr.CreateLine(
                    X1: -tnHalfW, Y1: y0, Z1: 0.0,
                    X2: tnHalfW, Y2: y0, Z2: 0.0);
                skMgr.CreateLine(
                    X1: tnHalfW, Y1: y0, Z1: 0.0,
                    X2: tnHalfW, Y2: barLength, Z2: 0.0);
                skMgr.CreateLine(
                    X1: tnHalfW, Y1: barLength, Z1: 0.0,
                    X2: -tnHalfW, Y2: barLength, Z2: 0.0);
                skMgr.CreateLine(
                    X1: -tnHalfW, Y1: barLength, Z1: 0.0,
                    X2: -tnHalfW, Y2: y0, Z2: 0.0);

                skMgr.InsertSketch(true);
                swModel.ClearSelection2(true);

                // Cut-extrude the top notch (cut)
                Feature topCut = swFeatMgr.FeatureExtrusion2(
                    Sd: false,
                    Flip: false,
                    Dir: false,
                    T1: (int)swEndConditions_e.swEndCondBlind,
                    T2: 0,
                    D1: topNotchHeight + 0.0001,
                    D2: 0.0,
                    Dchk1: false,
                    Dchk2: false,
                    Ddir1: false,
                    Ddir2: false,
                    Dang1: 0.0,
                    Dang2: 0.0,
                    OffsetReverse1: false,
                    OffsetReverse2: false,
                    TranslateSurface1: false,
                    TranslateSurface2: false,
                    Merge: true,
                    UseFeatScope: false,
                    UseAutoSelect: false,
                    T0: (int)swStartConditions_e.swStartSketchPlane,
                    StartOffset: 0.0,
                    false);

                if (topCut == null)
                {
                    Console.WriteLine("Warning: top notch cut failed.");
                }

                swModel.ClearSelection2(true);

                Console.WriteLine("Amplitude bar model created. Save the part manually or via API.");
            }
            catch (Exception ex)
            {
                Console.WriteLine("Error: " + ex.Message);
            }
            finally
            {
                // Release COM objects
                try { if (swModel != null) Marshal.ReleaseComObject(swModel); } catch { }
                try { if (swApp != null) Marshal.ReleaseComObject(swApp); } catch { }
                swModel = null;
                swApp = null;
            }

            Console.WriteLine("Done. Press any key to exit.");
            Console.ReadKey();
        }
    }
}
