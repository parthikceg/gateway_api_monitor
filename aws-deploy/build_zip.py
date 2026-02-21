#!/usr/bin/env python3
"""
Build deployment ZIP with Unix-compatible paths for AWS Elastic Beanstalk
"""

import os
import zipfile
from datetime import datetime
from pathlib import Path

def build_deployment_zip():
    # Get project root (parent of aws-deploy folder)
    script_dir = Path(__file__).parent
    project_root = script_dir.parent

    # Timestamp for filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_filename = f"gateway-monitor-{timestamp}.zip"
    zip_path = project_root / zip_filename

    print("=" * 50)
    print("  Building AWS EB Deployment Package")
    print("=" * 50)

    # Files and folders to include
    include_items = [
        ("app", "app"),                      # Backend code
        ("client/dist", "client/dist"),      # Built frontend
        ("requirements.txt", "requirements.txt"),
        ("Procfile", "Procfile"),
        ("migrate.py", "migrate.py"),        # Pre-startup migration
        (".ebextensions", ".ebextensions"),
    ]

    # Files to exclude
    exclude_patterns = [
        "__pycache__",
        ".pyc",
        ".env",
        ".git",
        "node_modules",
        ".DS_Store",
    ]

    def should_exclude(path):
        path_str = str(path)
        return any(pattern in path_str for pattern in exclude_patterns)

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for src_path, dest_path in include_items:
            full_src = project_root / src_path

            if not full_src.exists():
                print(f"  [SKIP] {src_path} (not found)")
                continue

            if full_src.is_file():
                # Single file
                if not should_exclude(full_src):
                    # Use forward slashes for Unix compatibility
                    arcname = dest_path.replace("\\", "/")
                    zf.write(full_src, arcname)
                    print(f"  [ADD] {arcname}")
            else:
                # Directory - walk and add all files
                for root, dirs, files in os.walk(full_src):
                    # Filter out excluded directories
                    dirs[:] = [d for d in dirs if not should_exclude(d)]

                    for file in files:
                        file_path = Path(root) / file
                        if should_exclude(file_path):
                            continue

                        # Calculate relative path from project root
                        rel_path = file_path.relative_to(project_root)
                        # Convert to forward slashes for Unix
                        arcname = str(rel_path).replace("\\", "/")
                        zf.write(file_path, arcname)

                file_count = len([f for f in zf.namelist() if f.startswith(dest_path.replace("\\", "/"))])
                print(f"  [ADD] {dest_path}/ ({file_count} files)")

    # Get file size
    size_mb = zip_path.stat().st_size / (1024 * 1024)

    print()
    print("=" * 50)
    print(f"  SUCCESS: {zip_filename}")
    print(f"  Size: {size_mb:.2f} MB")
    print(f"  Location: {zip_path}")
    print("=" * 50)

    return zip_path

if __name__ == "__main__":
    build_deployment_zip()
