using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;

namespace SolidWorksRenders
{
    /// <summary>
    /// Command-line options for the SolidWorks Renders CLI
    /// </summary>
    public class CliOptions
    {
        /// <summary>
        /// Available components that can be built (derived from Program.PartRegistry)
        /// </summary>
        public static IReadOnlyDictionary<string, string> AvailableComponents =>
            Program.PartRegistry.ToDictionary(p => p.Key, p => p.Value.Description);

        /// <summary>
        /// The component to build (null if listing or showing help)
        /// </summary>
        public string? Component { get; private set; }

        /// <summary>
        /// Whether to show help
        /// </summary>
        public bool ShowHelp { get; private set; }

        /// <summary>
        /// Whether to list available components
        /// </summary>
        public bool ListComponents { get; private set; }

        /// <summary>
        /// Whether to build all components
        /// </summary>
        public bool BuildAll { get; private set; }

        /// <summary>
        /// SLDPRT file path to extract (null if not in extract mode)
        /// </summary>
        public string? ExtractFile { get; private set; }

        /// <summary>
        /// Whether we're in extract mode
        /// </summary>
        public bool IsExtractMode => !string.IsNullOrEmpty(ExtractFile);

        /// <summary>
        /// Parse error message, if any
        /// </summary>
        public string? Error { get; private set; }

        /// <summary>
        /// Whether parsing was successful (for building components)
        /// </summary>
        public bool IsValid => string.IsNullOrEmpty(Error) && !ShowHelp && !ListComponents && !IsExtractMode;

        private CliOptions() { }

        /// <summary>
        /// Parse command-line arguments
        /// </summary>
        public static CliOptions Parse(string[] args)
        {
            var options = new CliOptions();

            if (args.Length == 0)
            {
                options.ShowHelp = true;
                return options;
            }

            for (int i = 0; i < args.Length; i++)
            {
                string arg = args[i].ToLower();

                switch (arg)
                {
                    case "-h":
                    case "--help":
                    case "/?":
                        options.ShowHelp = true;
                        return options;

                    case "-l":
                    case "--list":
                        options.ListComponents = true;
                        return options;

                    case "-a":
                    case "--all":
                        options.BuildAll = true;
                        break;

                    case "-e":
                    case "--extract":
                        if (i + 1 >= args.Length)
                        {
                            options.Error = "Missing file path after --extract";
                            return options;
                        }
                        i++;
                        string extractPath = args[i];
                        if (!File.Exists(extractPath))
                        {
                            options.Error = $"File not found: '{extractPath}'";
                            return options;
                        }
                        if (!extractPath.EndsWith(".SLDPRT", StringComparison.OrdinalIgnoreCase))
                        {
                            options.Error = $"Only .SLDPRT files are supported for extraction.\nGot: '{extractPath}'";
                            return options;
                        }
                        options.ExtractFile = Path.GetFullPath(extractPath);
                        return options;

                    case "-c":
                    case "--component":
                        if (i + 1 >= args.Length)
                        {
                            options.Error = "Missing component name after --component";
                            return options;
                        }
                        i++;
                        string componentName = args[i].ToLower();
                        if (!AvailableComponents.ContainsKey(componentName))
                        {
                            options.Error = $"Unknown component: '{args[i]}'\nUse --list to see available components.";
                            return options;
                        }
                        options.Component = componentName;
                        break;

                    default:
                        // Check if it's a bare component name (backward compatibility)
                        if (!arg.StartsWith("-") && AvailableComponents.ContainsKey(arg))
                        {
                            options.Component = arg;
                        }
                        else if (!arg.StartsWith("-"))
                        {
                            options.Error = $"Unknown component: '{args[i]}'\nUse --list to see available components.";
                            return options;
                        }
                        else
                        {
                            options.Error = $"Unknown option: '{args[i]}'\nUse --help to see available options.";
                            return options;
                        }
                        break;
                }
            }

            // Validate: must have either a component, --all, or an action flag
            if (!options.BuildAll && string.IsNullOrEmpty(options.Component) && !options.ShowHelp && !options.ListComponents)
            {
                options.ShowHelp = true;
            }

            return options;
        }

        /// <summary>
        /// Print help message
        /// </summary>
        public static void PrintHelp()
        {
            Console.WriteLine("SolidWorks Renders - Build CAD components for the Harmonic Analyzer");
            Console.WriteLine();
            Console.WriteLine("USAGE:");
            Console.WriteLine("  SolidWorksRenders.exe [OPTIONS] [COMPONENT]");
            Console.WriteLine();
            Console.WriteLine("OPTIONS:");
            Console.WriteLine("  -c, --component <name>   Build a specific component");
            Console.WriteLine("  -a, --all                Build all components");
            Console.WriteLine("  -e, --extract <file>     Extract sketches/features from .SLDPRT to XML");
            Console.WriteLine("  -l, --list               List all available components");
            Console.WriteLine("  -h, --help               Show this help message");
            Console.WriteLine();
            Console.WriteLine("EXAMPLES:");
            Console.WriteLine("  SolidWorksRenders.exe --list");
            Console.WriteLine("  SolidWorksRenders.exe -c eccentric-cam");
            Console.WriteLine("  SolidWorksRenders.exe harmonic-base");
            Console.WriteLine("  SolidWorksRenders.exe --all");
            Console.WriteLine("  SolidWorksRenders.exe -e mypart.SLDPRT");
            Console.WriteLine();
            Console.WriteLine("Use --list to see all available components.");
        }

        /// <summary>
        /// Print list of available components
        /// </summary>
        public static void PrintComponentList()
        {
            Console.WriteLine("Available Components:");
            Console.WriteLine(new string('=', 60));
            Console.WriteLine();

            int maxNameLen = AvailableComponents.Keys.Max(k => k.Length);

            foreach (var component in AvailableComponents)
            {
                Console.WriteLine($"  {component.Key.PadRight(maxNameLen + 2)} {component.Value}");
            }

            Console.WriteLine();
            Console.WriteLine($"Total: {AvailableComponents.Count} components");
        }

        /// <summary>
        /// Get all component names to build based on options
        /// </summary>
        public IEnumerable<string> GetComponentsToBuild()
        {
            if (BuildAll)
            {
                return AvailableComponents.Keys;
            }
            else if (!string.IsNullOrEmpty(Component))
            {
                return new[] { Component! };
            }
            return Enumerable.Empty<string>();
        }
    }
}
