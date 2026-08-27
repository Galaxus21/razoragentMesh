#!/usr/bin/env python3
"""
Cross-platform cache cleanup script for RazorAgent Mesh repository.
Purges build caches, python bytecode, pytest caches, hypothesis databases,
distribution artifacts, and TypeScript build info files.
"""

import fnmatch
import os
import shutil
import stat
import sys
from pathlib import Path
from typing import Tuple, Union

# Directory name patterns to remove recursively
CACHE_DIR_PATTERNS = [
    "__pycache__",
    ".pytest_cache*",
    ".hypothesis*",
    "dist",
    "build",
    "*.egg-info",
    ".mypy_cache",
    ".next",
    "htmlcov",
]

# File patterns to remove recursively
CACHE_FILE_PATTERNS = [
    "*.tsbuildinfo",
    "*.pyc",
    "*.pyo",
    "*.pyd",
    ".coverage*",
    "coverage.xml",
]

# Directories that should never be searched or modified
EXCLUDE_DIRS = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "env",
    ".agents",
}


def handle_remove_readonly(func, path, *args):
    """Error handler for shutil.rmtree on read-only files (Windows and POSIX)."""
    try:
        os.chmod(path, stat.S_IWRITE | stat.S_IWUSR)
        func(path)
    except Exception as e:
        sys.stderr.write(f"Warning: Failed to remove {path}: {e}\n")


def clean_caches(
    root_path: Union[str, Path], dry_run: bool = False, verbose: bool = True
) -> Tuple[int, int]:
    """
    Recursively scans and removes cache directories and files under root_path.
    Safely ignores excluded directories such as node_modules, .git, and virtualenvs.
    Returns (dirs_removed_count, files_removed_count).
    """
    dirs_removed = 0
    files_removed = 0

    resolved_root = Path(root_path).resolve()
    if not resolved_root.exists():
        sys.stderr.write(f"Error: Target path {resolved_root} does not exist.\n")
        return (0, 0)

    for root, dirs, files in os.walk(resolved_root, topdown=True):
        # Exclude directories that should never be entered or cleaned (e.g. node_modules, .git)
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]

        # Check and remove files matching file patterns
        for file_name in list(files):
            for pattern in CACHE_FILE_PATTERNS:
                if fnmatch.fnmatch(file_name, pattern):
                    file_path = Path(root) / file_name
                    if verbose:
                        try:
                            rel_disp = file_path.relative_to(resolved_root)
                        except ValueError:
                            rel_disp = file_path
                        print(f"Removing file: {rel_disp}")
                    if not dry_run:
                        try:
                            try:
                                os.chmod(file_path, stat.S_IWRITE | stat.S_IWUSR)
                            except Exception:
                                pass
                            file_path.unlink(missing_ok=True)
                            files_removed += 1
                        except Exception as err:
                            sys.stderr.write(f"Failed to remove {file_path}: {err}\n")
                    else:
                        files_removed += 1
                    break

        # Check and remove directories matching directory patterns
        remaining_dirs = []
        for dir_name in dirs:
            is_matched = False
            for pattern in CACHE_DIR_PATTERNS:
                if fnmatch.fnmatch(dir_name, pattern):
                    dir_path = Path(root) / dir_name
                    if verbose:
                        try:
                            rel_disp = dir_path.relative_to(resolved_root)
                        except ValueError:
                            rel_disp = dir_path
                        print(f"Removing directory: {rel_disp}")
                    if not dry_run:
                        try:
                            if dir_path.is_symlink():
                                dir_path.unlink(missing_ok=True)
                            elif sys.version_info >= (3, 12):
                                shutil.rmtree(dir_path, onexc=handle_remove_readonly)
                            else:
                                shutil.rmtree(dir_path, onerror=handle_remove_readonly)
                            dirs_removed += 1
                        except Exception as err:
                            sys.stderr.write(f"Failed to remove {dir_path}: {err}\n")
                    else:
                        dirs_removed += 1
                    is_matched = True
                    break
            if not is_matched:
                remaining_dirs.append(dir_name)

        # Update dirs so os.walk only recurses into surviving directories
        dirs[:] = remaining_dirs

    return dirs_removed, files_removed


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Clean caches and build artifacts across repository."
    )
    parser.add_argument(
        "--root",
        type=str,
        default=str(Path(__file__).resolve().parent.parent),
        help="Repository root directory (defaults to repository parent of scripts/)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Perform a dry run without deleting files/directories",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress detailed removal output",
    )

    args = parser.parse_args()
    root_path = Path(args.root).resolve()

    if not root_path.exists():
        sys.stderr.write(f"Error: Target path '{root_path}' does not exist.\n")
        return 1

    print(f"Purging build caches and artifacts from: {root_path}")
    dirs_count, files_count = clean_caches(
        root_path=root_path,
        dry_run=args.dry_run,
        verbose=not args.quiet,
    )
    print(f"Cleanup complete: Removed {dirs_count} directories and {files_count} files.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

