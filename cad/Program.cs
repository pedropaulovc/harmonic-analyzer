using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swconst;
using SolidWorksRenders;

namespace SolidWorksRenders
{
    class Program
    {
        /// <summary>
        /// Registry of part creators: CLI name -> (description, factory)
        /// </summary>
        public static readonly Dictionary<string, (string Description, Func<ISldWorks, IPartCreator> Factory)> PartRegistry =
            new Dictionary<string, (string, Func<ISldWorks, IPartCreator>)>
            {
                { "harmonic-base", ("Two-plate welded base for harmonic analyzer", sw => new HarmonicBase(sw)) },
                { "eccentric-cam", ("2\" diameter cam with off-center mounting hole and keyway", sw => new EccentricCam(sw)) },
                { "amplitude-bar", ("Vertical 32\" rod with top and bottom notches", sw => new AmplitudeBar(sw)) },
                { "summing-lever", ("Complex assembly with coefficients plate and pivot", sw => new SummingLever(sw)) },
                { "rocker-arm-support", ("A-frame bearing stand with mounting holes", sw => new RockerArmSupport(sw)) },
            };

        static int Main(string[] args)
        {
            // Parse command-line arguments
            var options = CliOptions.Parse(args);

            // Handle parse errors
            if (!string.IsNullOrEmpty(options.Error))
            {
                Console.Error.WriteLine($"Error: {options.Error}");
                Console.WriteLine();
                CliOptions.PrintHelp();
                return 1;
            }

            // Handle help request
            if (options.ShowHelp)
            {
                CliOptions.PrintHelp();
                return 0;
            }

            // Handle list request
            if (options.ListComponents)
            {
                CliOptions.PrintComponentList();
                return 0;
            }

            // Get components to build
            var componentsToBuild = new List<string>(options.GetComponentsToBuild());
            if (componentsToBuild.Count == 0)
            {
                CliOptions.PrintHelp();
                return 1;
            }

            ISldWorks? swApp = null;
            int successCount = 0;
            int failCount = 0;

            try
            {
                swApp = ConnectToSolidWorks();
                Console.WriteLine($"Connected to SolidWorks {swApp.RevisionNumber()}\n");

                // Close all open documents first to avoid file lock issues
                CloseAllDocuments(swApp);

                // Build each component
                foreach (string componentName in componentsToBuild)
                {
                    Console.WriteLine(new string('=', 60));
                    bool success = BuildComponent(swApp, componentName);
                    if (success)
                        successCount++;
                    else
                        failCount++;
                    Console.WriteLine();
                }

                // Print summary if building multiple
                if (componentsToBuild.Count > 1)
                {
                    Console.WriteLine(new string('=', 60));
                    Console.WriteLine("BUILD SUMMARY");
                    Console.WriteLine(new string('=', 60));
                    Console.WriteLine($"  Successful: {successCount}");
                    Console.WriteLine($"  Failed:     {failCount}");
                    Console.WriteLine($"  Total:      {componentsToBuild.Count}");
                }
            }
            catch (COMException comEx)
            {
                Console.Error.WriteLine($"COM ERROR: {comEx.Message}");
                Console.Error.WriteLine($"HRESULT: 0x{comEx.ErrorCode:X}");
                return 1;
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine($"ERROR: {ex.Message}");
                Console.Error.WriteLine($"Stack trace: {ex.StackTrace}");
                return 1;
            }

            // Only prompt for key if running interactively
            if (!Console.IsInputRedirected)
            {
                Console.WriteLine("\nPress any key to exit...");
                Console.ReadKey();
            }

            return failCount > 0 ? 1 : 0;
        }

        /// <summary>
        /// Build a single component by name
        /// </summary>
        private static bool BuildComponent(ISldWorks swApp, string componentName)
        {
            IPartCreator? partCreator = CreatePartCreator(swApp, componentName);
            if (partCreator == null)
            {
                Console.Error.WriteLine($"ERROR: Unknown component '{componentName}'");
                return false;
            }

            Console.WriteLine($"Building: {partCreator.PartName}");
            Console.WriteLine(new string('-', 60));

            try
            {
                // Create the part
                Console.WriteLine($"Creating {partCreator.PartName.ToLower()} part...");
                IModelDoc2 model = partCreator.CreatePart();

                if (model != null)
                {
                    Console.WriteLine($"SUCCESS: {partCreator.PartName} created successfully!");
                    Console.WriteLine($"Model name: {model.GetTitle()}");

                    // Zoom to fit
                    model.ViewZoomtofit2();

                    // Print part-specific details
                    partCreator.PrintPartDetails();

                    // Save the part as SLDPRT
                    string? savePath = SavePart(model, partCreator.FileName);
                    if (savePath != null)
                    {
                        Console.WriteLine($"Part saved to: {savePath}");
                    }

                    // Export to STL
                    string? stlPath = ExportToSTL(model, partCreator.FileName);
                    if (stlPath != null)
                    {
                        Console.WriteLine($"STL exported to: {stlPath}");

                        // Export to PNG renders from the STL
                        string? pngDir = ExportToPNG(stlPath, partCreator.FileName);
                        if (pngDir != null)
                        {
                            Console.WriteLine($"PNG renders exported to: {pngDir}");
                        }
                    }

                    // Export to STEP
                    string? stepPath = ExportToSTEP(model, partCreator.FileName);
                    if (stepPath != null)
                    {
                        Console.WriteLine($"STEP exported to: {stepPath}");
                    }

                    // Keep document open for inspection
                    Console.WriteLine("Part remains open in SolidWorks for inspection.");

                    return true;
                }
                else
                {
                    Console.Error.WriteLine($"ERROR: Failed to create {partCreator.PartName.ToLower()}.");
                    return false;
                }
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine($"ERROR building {componentName}: {ex.Message}");
                return false;
            }
        }

        /// <summary>
        /// Creates the appropriate part creator based on component name
        /// </summary>
        private static IPartCreator? CreatePartCreator(ISldWorks swApp, string componentName)
        {
            if (PartRegistry.TryGetValue(componentName.ToLower(), out var entry))
            {
                return entry.Factory(swApp);
            }
            return null;
        }

        /// <summary>
        /// Close all open documents in SolidWorks to release file locks
        /// </summary>
        private static void CloseAllDocuments(ISldWorks swApp)
        {
            try
            {
                // Get the first document
                IModelDoc2 doc = (IModelDoc2)swApp.GetFirstDocument();
                int closedCount = 0;

                while (doc != null)
                {
                    string docTitle = doc.GetTitle();
                    IModelDoc2 nextDoc = (IModelDoc2)doc.GetNext();

                    // Close without saving (we'll rebuild fresh)
                    swApp.CloseDoc(docTitle);
                    closedCount++;

                    doc = nextDoc;
                }

                if (closedCount > 0)
                {
                    Console.WriteLine($"Closed {closedCount} existing document(s) to avoid file locks.\n");
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine($"Warning: Could not close all documents: {ex.Message}");
            }
        }

        /// <summary>
        /// Connects to a running SolidWorks instance or creates a new one
        /// </summary>
        private static ISldWorks ConnectToSolidWorks()
        {
            Console.WriteLine("Connecting to SolidWorks...");

            try
            {
                ISldWorks? swApp = (ISldWorks?)Marshal.GetActiveObject("SldWorks.Application");
                if (swApp != null)
                {
                    return swApp;
                }
            }
            catch (COMException)
            {
                // No running instance found, will create new one below
            }

            Console.WriteLine("No running SolidWorks instance found. Starting SolidWorks...");

            // Create a new instance of SolidWorks
            Type? swType = Type.GetTypeFromProgID("SldWorks.Application");
            if (swType == null)
            {
                throw new InvalidOperationException("SolidWorks is not installed or not properly registered.");
            }

            ISldWorks? newSwApp = (ISldWorks?)Activator.CreateInstance(swType);
            if (newSwApp == null)
            {
                throw new InvalidOperationException("Failed to create SolidWorks instance.");
            }

            // Make SolidWorks visible
            newSwApp.Visible = true;

            return newSwApp;
        }

        /// <summary>
        /// Saves the part to the out/sldprt directory
        /// </summary>
        /// <param name="model">The model to save</param>
        /// <param name="fileName">The filename to save as</param>
        /// <returns>The full path where the file was saved, or null if save failed</returns>
        private static string? SavePart(IModelDoc2 model, string fileName)
        {
            try
            {
                // Get the directory relative to the current executable
                string exeDir = Path.GetDirectoryName(System.Reflection.Assembly.GetExecutingAssembly().Location);
                string saveDir = Path.GetFullPath(Path.Combine(exeDir, "..", "..", "..", "out", "sldprt"));

                // Create directory if it doesn't exist
                if (!Directory.Exists(saveDir))
                {
                    Directory.CreateDirectory(saveDir);
                    Console.WriteLine($"Created directory: {saveDir}");
                }

                // Construct full save path
                string fullPath = Path.Combine(saveDir, fileName);

                Console.WriteLine($"Saving part to: {fullPath}");

                // Save the document using IModelDocExtension.SaveAs3
                int errors = 0;
                int warnings = 0;
                bool saveResult = model.Extension.SaveAs3(
                    Name: fullPath,
                    Version: (int)swSaveAsVersion_e.swSaveAsCurrentVersion,
                    Options: (int)swSaveAsOptions_e.swSaveAsOptions_Silent,
                    ExportData: null,
                    AdvancedSaveAsOptions: null,
                    Errors: ref errors,
                    Warnings: ref warnings);

                if (!saveResult || errors != 0)
                {
                    Console.Error.WriteLine($"ERROR: Failed to save part. Errors: {errors}, Warnings: {warnings}");
                    return null;
                }

                return fullPath;
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine($"ERROR saving part: {ex.Message}");
                return null;
            }
        }

        /// <summary>
        /// Exports the part to STL format in the out/stl directory
        /// </summary>
        /// <param name="model">The model to export</param>
        /// <param name="fileName">The filename (without extension) to export as</param>
        /// <returns>The full path where the file was exported, or null if export failed</returns>
        private static string? ExportToSTL(IModelDoc2 model, string fileName)
        {
            try
            {
                // Get the directory relative to the current executable
                string exeDir = Path.GetDirectoryName(System.Reflection.Assembly.GetExecutingAssembly().Location);
                string saveDir = Path.GetFullPath(Path.Combine(exeDir, "..", "..", "..", "out", "stl"));

                // Create directory if it doesn't exist
                if (!Directory.Exists(saveDir))
                {
                    Directory.CreateDirectory(saveDir);
                    Console.WriteLine($"Created directory: {saveDir}");
                }

                // Replace .sldprt extension with .stl
                string stlFileName = Path.GetFileNameWithoutExtension(fileName) + ".stl";
                string fullPath = Path.Combine(saveDir, stlFileName);

                Console.WriteLine($"Exporting to STL: {fullPath}");

                // Clear selection to export entire model
                model.ClearSelection2(true);

                // Export using SaveAs3 - the .stl extension triggers STL format
                int errors = 0;
                int warnings = 0;
                bool saveResult = model.Extension.SaveAs3(
                    Name: fullPath,
                    Version: (int)swSaveAsVersion_e.swSaveAsCurrentVersion,
                    Options: (int)swSaveAsOptions_e.swSaveAsOptions_Silent,
                    ExportData: null,
                    AdvancedSaveAsOptions: null,
                    Errors: ref errors,
                    Warnings: ref warnings);

                if (!saveResult || errors != 0)
                {
                    Console.Error.WriteLine($"ERROR: Failed to export STL. Errors: {errors}, Warnings: {warnings}");
                    return null;
                }

                return fullPath;
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine($"ERROR exporting to STL: {ex.Message}");
                return null;
            }
        }

        /// <summary>
        /// Exports the part to STEP format in the out/step directory
        /// </summary>
        /// <param name="model">The model to export</param>
        /// <param name="fileName">The filename (without extension) to export as</param>
        /// <returns>The full path where the file was exported, or null if export failed</returns>
        private static string? ExportToSTEP(IModelDoc2 model, string fileName)
        {
            try
            {
                // Get the directory relative to the current executable
                string exeDir = Path.GetDirectoryName(System.Reflection.Assembly.GetExecutingAssembly().Location);
                string saveDir = Path.GetFullPath(Path.Combine(exeDir, "..", "..", "..", "out", "step"));

                // Create directory if it doesn't exist
                if (!Directory.Exists(saveDir))
                {
                    Directory.CreateDirectory(saveDir);
                    Console.WriteLine($"Created directory: {saveDir}");
                }

                // Replace .sldprt extension with .step
                string stepFileName = Path.GetFileNameWithoutExtension(fileName) + ".step";
                string fullPath = Path.Combine(saveDir, stepFileName);

                Console.WriteLine($"Exporting to STEP: {fullPath}");

                // Clear selection to export entire model
                model.ClearSelection2(true);

                // Export using SaveAs3 - the .step extension triggers STEP format
                int errors = 0;
                int warnings = 0;
                bool saveResult = model.Extension.SaveAs3(
                    Name: fullPath,
                    Version: (int)swSaveAsVersion_e.swSaveAsCurrentVersion,
                    Options: (int)swSaveAsOptions_e.swSaveAsOptions_Silent,
                    ExportData: null,
                    AdvancedSaveAsOptions: null,
                    Errors: ref errors,
                    Warnings: ref warnings);

                if (!saveResult || errors != 0)
                {
                    Console.Error.WriteLine($"ERROR: Failed to export STEP. Errors: {errors}, Warnings: {warnings}");
                    return null;
                }

                return fullPath;
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine($"ERROR exporting to STEP: {ex.Message}");
                return null;
            }
        }

        /// <summary>
        /// Camera angles for PNG rendering: x,y,z,rot_x,rot_y,rot_z,distance
        /// </summary>
        private static readonly Dictionary<string, string> CameraAngles = new Dictionary<string, string>
        {
            { "front", "0,0,0,90,0,0,150" },
            { "back", "0,0,0,90,0,180,150" },
            { "left", "0,0,0,90,0,90,150" },
            { "right", "0,0,0,90,0,270,150" },
            { "top", "0,0,0,0,0,0,150" },
            { "bottom", "0,0,0,180,0,0,150" },
            { "iso-front-left", "0,0,0,60,0,315,150" },
            { "iso-front-right", "0,0,0,60,0,45,150" },
            { "iso-back-left", "0,0,0,60,0,135,150" },
            { "iso-back-right", "0,0,0,60,0,225,150" }
        };

        /// <summary>
        /// Exports the STL to PNG images from multiple camera angles using OpenSCAD
        /// </summary>
        /// <param name="stlPath">Path to the STL file to render</param>
        /// <param name="fileName">The filename (without extension) for output directory naming</param>
        /// <returns>The output directory path, or null if export failed</returns>
        private static string? ExportToPNG(string stlPath, string fileName)
        {
            try
            {
                // Check if OpenSCAD is available
                string? openscadPath = FindOpenSCAD();
                if (openscadPath == null)
                {
                    Console.WriteLine("OpenSCAD not found. Skipping PNG export.");
                    return null;
                }

                // Get the directory relative to the current executable
                string exeDir = Path.GetDirectoryName(System.Reflection.Assembly.GetExecutingAssembly().Location);
                string baseName = Path.GetFileNameWithoutExtension(fileName);
                string saveDir = Path.GetFullPath(Path.Combine(exeDir, "..", "..", "..", "out", "png", baseName));

                // Create directory if it doesn't exist
                if (!Directory.Exists(saveDir))
                {
                    Directory.CreateDirectory(saveDir);
                }

                Console.WriteLine($"Exporting PNG renders to: {saveDir}");

                // Create temporary SCAD file to import the STL
                string tempScad = Path.Combine(Path.GetTempPath(), $"{baseName}-temp.scad");
                string absoluteStlPath = Path.GetFullPath(stlPath).Replace("\\", "/");
                File.WriteAllText(tempScad, $"import(\"{absoluteStlPath}\");");

                int successCount = 0;
                int failCount = 0;

                foreach (var angle in CameraAngles)
                {
                    string outputFile = Path.Combine(saveDir, $"{angle.Key}.png");

                    var startInfo = new ProcessStartInfo
                    {
                        FileName = openscadPath,
                        Arguments = $"-o \"{outputFile}\" --imgsize=4096,4096 --camera={angle.Value} --colorscheme=Solarized --view=axes,scales --viewall --projection=o \"{tempScad}\"",
                        UseShellExecute = false,
                        RedirectStandardOutput = true,
                        RedirectStandardError = true,
                        CreateNoWindow = true
                    };

                    using (var process = Process.Start(startInfo))
                    {
                        if (process == null)
                        {
                            Console.Error.WriteLine($"  Failed to start OpenSCAD for {angle.Key} view");
                            failCount++;
                            continue;
                        }

                        string stderr = process.StandardError.ReadToEnd();
                        process.WaitForExit();

                        if (process.ExitCode == 0 && File.Exists(outputFile))
                        {
                            Console.WriteLine($"  Rendered {angle.Key} view");
                            successCount++;
                        }
                        else
                        {
                            Console.Error.WriteLine($"  Failed to render {angle.Key} view: {stderr}");
                            failCount++;
                        }
                    }
                }

                // Clean up temp file
                try { File.Delete(tempScad); } catch { }

                Console.WriteLine($"PNG export complete: {successCount} succeeded, {failCount} failed");
                return successCount > 0 ? saveDir : null;
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine($"ERROR exporting to PNG: {ex.Message}");
                return null;
            }
        }

        /// <summary>
        /// Finds OpenSCAD executable in PATH or common installation locations
        /// </summary>
        private static string? FindOpenSCAD()
        {
            // Check PATH first
            string[] pathDirs = System.Environment.GetEnvironmentVariable("PATH")?.Split(Path.PathSeparator) ?? Array.Empty<string>();
            foreach (string dir in pathDirs)
            {
                string candidate = Path.Combine(dir, "openscad.exe");
                if (File.Exists(candidate))
                    return candidate;
                candidate = Path.Combine(dir, "openscad");
                if (File.Exists(candidate))
                    return candidate;
            }

            // Check common Windows installation locations
            string[] commonPaths = new[]
            {
                @"C:\Program Files\OpenSCAD\openscad.exe",
                @"C:\Program Files (x86)\OpenSCAD\openscad.exe",
                Path.Combine(System.Environment.GetFolderPath(System.Environment.SpecialFolder.LocalApplicationData), "Programs", "OpenSCAD", "openscad.exe")
            };

            foreach (string path in commonPaths)
            {
                if (File.Exists(path))
                    return path;
            }

            return null;
        }
    }
}
