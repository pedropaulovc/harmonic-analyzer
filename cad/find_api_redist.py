r"""
Search for api\redist folder in C:\Program Files
"""
import os
from pathlib import Path

def find_api_redist(root_path="C:\\Program Files"):
    """
    Traverse directory tree and find folders matching api\redist pattern.

    Args:
        root_path: Root directory to start search from

    Returns:
        List of full paths to matching folders
    """
    matches = []

    print(f"Searching in {root_path}...")

    for dirpath, dirnames, _ in os.walk(root_path):
        try:
            # Check if current path ends with api\redist
            if dirpath.lower().endswith(os.path.join("api", "redist")):
                if dirpath not in matches:
                    matches.append(dirpath)
                    print(f"Found: {dirpath}")

            # Also check subdirectories
            if "redist" in dirnames:
                parent_name = os.path.basename(dirpath)
                if parent_name.lower() == "api":
                    full_path = os.path.join(dirpath, "redist")
                    if full_path not in matches:
                        matches.append(full_path)
                        print(f"Found: {full_path}")

        except PermissionError:
            # Skip directories we don't have permission to access
            pass
        except Exception as e:
            # Skip other errors but continue searching
            pass

    return matches

if __name__ == "__main__":
    results = find_api_redist()

    print("\n" + "="*60)
    if results:
        print(f"Found {len(results)} match(es):")
        for path in results:
            print(f"  {path}")
    else:
        print("No api\\redist folders found in C:\\Program Files")

        # Also search Program Files (x86) if available
        alt_path = "C:\\Program Files (x86)"
        if os.path.exists(alt_path):
            print(f"\nSearching in {alt_path}...")
            results_x86 = find_api_redist(alt_path)
            if results_x86:
                print(f"Found {len(results_x86)} match(es):")
                for path in results_x86:
                    print(f"  {path}")
