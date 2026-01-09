r"""
Find the most recent SolidWorks api\redist folder under C:\Program Files\Dassault Systemes
"""
import os


def find_api_redist(root_path=r"C:\Program Files\Dassault Systemes"):
    """
    Find the most recent api/redist folder under Dassault Systemes installation.

    Args:
        root_path: Root directory to search (default: C:\Program Files\Dassault Systemes)

    Returns:
        Path to the most recent api/redist folder, or None if not found
    """
    if not os.path.exists(root_path):
        return None

    matches = []

    # Search each subdirectory for api/redist
    for entry in os.scandir(root_path):
        if entry.is_dir():
            redist_path = os.path.join(entry.path, "SOLIDWORKS", "api", "redist")
            if os.path.isdir(redist_path):
                matches.append((redist_path, entry.stat().st_mtime))

    if not matches:
        return None

    # Return the most recently modified
    matches.sort(key=lambda x: x[1], reverse=True)
    return matches[0][0]


if __name__ == "__main__":
    result = find_api_redist()

    if result:
        print(result)
    else:
        print("No SolidWorks api/redist found under C:\\Program Files\\Dassault Systemes")