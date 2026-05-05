"""
Subprocess utilities — Windows-safe wrappers that:
  • Always decode output to str (no b'...' in the UI)
  • Suppress the console window on Windows builds
"""

import sys
import subprocess


def safe_subprocess_run(cmd, **kwargs):
    """
    Drop-in replacement for subprocess.run with Windows-safe defaults.

    Automatically sets:
      - encoding='utf-8', errors='ignore'  when capturing output
      - creationflags=CREATE_NO_WINDOW     on win32
    """
    if kwargs.get("capture_output") or kwargs.get("stdout") or kwargs.get("stderr"):
        if "encoding" not in kwargs:
            kwargs["encoding"] = "utf-8"
            kwargs["errors"] = "ignore"
    if "encoding" not in kwargs and kwargs.get("text"):
        kwargs["encoding"] = "utf-8"
        kwargs["errors"] = "ignore"
    if sys.platform == "win32" and "creationflags" not in kwargs:
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    return subprocess.run(cmd, **kwargs)


def patch_subprocess():
    """
    Monkey-patch subprocess.run and subprocess.Popen globally so every call
    in the process suppresses the console window on Windows.
    Call this once at application startup.
    """
    if sys.platform != "win32":
        return

    _original_run = subprocess.run
    _original_popen = subprocess.Popen

    def _is_scrcpy(cmd):
        """Return True if the command is launching scrcpy (needs a visible window)."""
        try:
            exe = cmd[0] if isinstance(cmd, (list, tuple)) else cmd
            return "scrcpy" in str(exe).lower()
        except Exception:
            return False

    def _patched_run(cmd, **kwargs):
        if "creationflags" not in kwargs and not _is_scrcpy(cmd):
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        return _original_run(cmd, **kwargs)

    class _PatchedPopen(_original_popen):
        def __init__(self, cmd, **kwargs):
            if "creationflags" not in kwargs and not _is_scrcpy(cmd):
                kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
            super().__init__(cmd, **kwargs)

    subprocess.run = _patched_run
    subprocess.Popen = _PatchedPopen
