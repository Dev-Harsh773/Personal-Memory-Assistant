"""
file_scanner.py — Intelligent Directory Scanner (Phase 2)

Scans Windows drives for documents and images, returning a categorized dictionary.
- C: drive: only scans Downloads and Documents folders
- Other drives: full recursive scan
"""

import os
import string

# File extension categories
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".gif"}
PDF_EXTENSIONS = {".pdf"}
WORD_EXTENSIONS = {".doc", ".docx"}
PPT_EXTENSIONS = {".ppt", ".pptx"}
TXT_EXTENSIONS = {".txt", ".md", ".csv", ".log"}

# Extensions to explicitly skip
SKIP_EXTENSIONS = {
    ".mp3", ".wav", ".flac", ".aac", ".ogg", ".wma",  # Audio
    ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv",    # Video
    ".exe", ".dll", ".sys", ".msi", ".bat", ".cmd",    # System/executables
    ".zip", ".rar", ".7z", ".tar", ".gz",              # Archives
    ".iso", ".img", ".vmdk",                           # Disk images
}

ALL_SUPPORTED = IMAGE_EXTENSIONS | PDF_EXTENSIONS | WORD_EXTENSIONS | PPT_EXTENSIONS | TXT_EXTENSIONS


def get_available_drives():
    """Detect all available drive letters on this Windows system."""
    drives = []
    for letter in string.ascii_uppercase:
        drive = f"{letter}:\\"
        if os.path.exists(drive):
            drives.append(drive)
    return drives


def _scan_directory(directory, result_dict, scanned_count):
    """Recursively scan a directory and categorize files by type."""
    try:
        for root, dirs, files in os.walk(directory):
            # Skip hidden directories and common system folders
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in {
                '$Recycle.Bin', 'System Volume Information', 'Windows',
                'ProgramData', 'Program Files', 'Program Files (x86)',
                'node_modules', '__pycache__', '.git', 'venv', '.venv',
                'AppData', 'Recovery', 'PerfLogs'
            }]
            
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                
                if ext in SKIP_EXTENSIONS:
                    continue
                    
                abs_path = os.path.abspath(os.path.join(root, file))
                
                if ext in IMAGE_EXTENSIONS:
                    result_dict["images"].append(abs_path)
                elif ext in PDF_EXTENSIONS:
                    result_dict["pdf"].append(abs_path)
                elif ext in WORD_EXTENSIONS:
                    result_dict["word"].append(abs_path)
                elif ext in PPT_EXTENSIONS:
                    result_dict["ppt"].append(abs_path)
                elif ext in TXT_EXTENSIONS:
                    result_dict["txt"].append(abs_path)
                
                scanned_count[0] += 1
                if scanned_count[0] % 500 == 0:
                    print(f"  ... scanned {scanned_count[0]} files so far")
                    
    except PermissionError:
        pass  # Skip directories we don't have access to
    except Exception as e:
        print(f"  Warning: Error scanning {directory}: {e}")


def scan_system_files():
    """
    Scans the Windows file system and returns a categorized dictionary of files.
    
    - C: drive: only scans user's Downloads and Documents folders
    - All other drives: full recursive scan
    
    Returns:
        dict: {"images": [...], "pdf": [...], "word": [...], "ppt": [...], "txt": [...]}
    """
    result = {
        "images": [],
        "pdf": [],
        "word": [],
        "ppt": [],
        "txt": []
    }
    
    scanned_count = [0]
    drives = get_available_drives()
    print(f"Detected drives: {drives}")
    
    for drive in drives:
        drive_letter = drive[0].upper()
        
        if drive_letter == "C":
            # For C: drive, only scan user's Downloads and Documents
            user_profile = os.environ.get("USERPROFILE", "C:\\Users\\Default")
            scan_folders = [
                os.path.join(user_profile, "Downloads"),
                os.path.join(user_profile, "Documents"),
            ]
            print(f"\n[C: Drive] Scanning restricted folders only:")
            for folder in scan_folders:
                if os.path.exists(folder):
                    print(f"  → {folder}")
                    _scan_directory(folder, result, scanned_count)
                else:
                    print(f"  → {folder} (not found, skipping)")
        else:
            # For all other drives, full recursive scan
            print(f"\n[{drive_letter}: Drive] Full recursive scan...")
            _scan_directory(drive, result, scanned_count)
    
    print(f"\n--- Scan Complete ---")
    print(f"Total files scanned: {scanned_count[0]}")
    for category, files in result.items():
        print(f"  {category}: {len(files)} files")
    
    return result


if __name__ == "__main__":
    print("=== Personal Memory Assistant — File Scanner ===\n")
    categorized = scan_system_files()
    
    # Print a few examples from each category
    for cat, paths in categorized.items():
        if paths:
            print(f"\n{cat.upper()} (showing first 3 of {len(paths)}):")
            for p in paths[:3]:
                print(f"  {p}")
