"""
Lirox v0.3 — File I/O Tool

Safe, sandboxed file operations for reading, writing, and listing files.
Prevents directory traversal and restricts access to project-relative paths.
"""

import os
from lirox.utils.errors import ToolExecutionError
from lirox.config import SAFE_DIRS


class FileIOTool:
    """Safe file operations tool with sandboxing."""

    def __init__(self):
        # Resolve safe directories to absolute paths at init
        self.safe_dirs = [os.path.abspath(d) for d in SAFE_DIRS]
        # Ensure outputs/ directory exists
        os.makedirs("outputs", exist_ok=True)

    def _is_safe_path(self, path):
        """
        Check if a path is within allowed directories.
        Prevents directory traversal attacks (../ sequences).

        Returns:
            (bool, str): (is_safe, reason)
        """
        try:
            abs_path = os.path.abspath(path)
        except Exception:
            return False, "Invalid path format"

        # Block obvious traversal attempts
        if ".." in path:
            return False, "Directory traversal (..) is not allowed"

        # Check if resolved path is within any safe directory
        for safe_dir in self.safe_dirs:
            if abs_path.startswith(safe_dir):
                return True, "ok"

        return False, f"Access denied: path is outside allowed directories"

    def read_file(self, path):
        """
        Read a file safely.

        Args:
            path: Relative or absolute path to read

        Returns:
            File contents as string

        Raises:
            ToolExecutionError on access denied or read failure
        """
        safe, reason = self._is_safe_path(path)
        if not safe:
            raise ToolExecutionError("file_io", f"Access denied: {reason}")

        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            return content
        except FileNotFoundError:
            raise ToolExecutionError("file_io", f"File not found: {path}")
        except PermissionError:
            raise ToolExecutionError("file_io", f"Permission denied: {path}")
        except UnicodeDecodeError:
            raise ToolExecutionError("file_io", f"Cannot read binary file: {path}")
        except Exception as e:
            raise ToolExecutionError("file_io", f"Error reading {path}: {str(e)}")

    def write_file(self, path, content):
        """
        Write content to a file safely. Creates parent directories if needed.

        Args:
            path: Relative or absolute path to write
            content: String content to write

        Returns:
            Confirmation message

        Raises:
            ToolExecutionError on access denied or write failure
        """
        safe, reason = self._is_safe_path(path)
        if not safe:
            raise ToolExecutionError("file_io", f"Access denied: {reason}")

        try:
            # Create parent directories if they don't exist
            parent = os.path.dirname(path)
            if parent:
                os.makedirs(parent, exist_ok=True)

            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)

            size = len(content)
            return f"File written: {path} ({size} bytes)"
        except PermissionError:
            raise ToolExecutionError("file_io", f"Permission denied: {path}")
        except Exception as e:
            raise ToolExecutionError("file_io", f"Error writing {path}: {str(e)}")

    def append_file(self, path, content):
        """
        Append content to an existing file (or create it).

        Args:
            path: Relative or absolute path
            content: String content to append

        Returns:
            Confirmation message
        """
        safe, reason = self._is_safe_path(path)
        if not safe:
            raise ToolExecutionError("file_io", f"Access denied: {reason}")

        try:
            parent = os.path.dirname(path)
            if parent:
                os.makedirs(parent, exist_ok=True)

            with open(path, 'a', encoding='utf-8') as f:
                f.write(content)

            return f"Content appended to: {path}"
        except Exception as e:
            raise ToolExecutionError("file_io", f"Error appending to {path}: {str(e)}")

    def list_files(self, directory="."):
        """
        List files in a directory (non-recursive).

        Args:
            directory: Path to list (must be within safe dirs)

        Returns:
            List of filenames
        """
        safe, reason = self._is_safe_path(directory)
        if not safe:
            raise ToolExecutionError("file_io", f"Access denied: {reason}")

        try:
            entries = os.listdir(directory)
            result = []
            for entry in sorted(entries):
                full_path = os.path.join(directory, entry)
                if os.path.isdir(full_path):
                    result.append(f"📁 {entry}/")
                else:
                    size = os.path.getsize(full_path)
                    result.append(f"📄 {entry} ({size} bytes)")
            return result
        except Exception as e:
            raise ToolExecutionError("file_io", f"Error listing {directory}: {str(e)}")

    def file_exists(self, path):
        """Check if a file exists (within safe paths)."""
        safe, _ = self._is_safe_path(path)
        if not safe:
            return False
        return os.path.exists(path)
