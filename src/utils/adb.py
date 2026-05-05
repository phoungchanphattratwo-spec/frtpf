"""
ADB helper utilities.

All functions accept an explicit *adb_path* so they work both with the
bundled platform-tools binary and with a system-PATH 'adb'.
"""

from __future__ import annotations
import subprocess
import sys
from typing import List, Optional


def _no_window() -> dict:
    """Return creationflags kwarg to suppress console window on Windows."""
    if sys.platform == "win32":
        return {"creationflags": subprocess.CREATE_NO_WINDOW}
    return {}


def run_adb(
    adb_path: str,
    args: List[str],
    timeout: int = 10,
    device_id: Optional[str] = None,
) -> subprocess.CompletedProcess:
    """
    Run an ADB command and return the CompletedProcess result.

    Args:
        adb_path:  Path to the adb executable.
        args:      Command arguments (e.g. ["devices"] or ["shell", "getprop ro.product.model"]).
        timeout:   Seconds before the command is killed.
        device_id: If given, inserts ``-s <device_id>`` before *args*.
    """
    cmd = [adb_path]
    if device_id:
        cmd += ["-s", device_id]
    cmd += args
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="ignore",
        timeout=timeout,
        **_no_window(),
    )


def get_device_prop(adb_path: str, device_id: str, prop: str) -> str:
    """Return the value of an Android system property, or '' on failure."""
    try:
        result = run_adb(adb_path, ["shell", f"getprop {prop}"], timeout=3, device_id=device_id)
        return result.stdout.strip() if result.returncode == 0 else ""
    except Exception:
        return ""


def get_device_shell(adb_path: str, device_id: str, cmd: str, timeout: int = 3) -> str:
    """Run an arbitrary shell command on *device_id* and return stdout."""
    try:
        result = run_adb(adb_path, ["shell", cmd], timeout=timeout, device_id=device_id)
        return result.stdout.strip() if result.returncode == 0 else ""
    except Exception:
        return ""


def list_connected_devices(adb_path: str) -> List[str]:
    """Return a list of connected device serial numbers."""
    try:
        result = run_adb(adb_path, ["devices"], timeout=5)
        serials = []
        for line in result.stdout.strip().splitlines()[1:]:
            line = line.strip()
            if line and line.endswith("device"):
                serials.append(line.split()[0])
        return serials
    except Exception:
        return []


def push_file(adb_path: str, device_id: str, local: str, remote: str, timeout: int = 60) -> bool:
    """Push a local file to the device. Returns True on success."""
    try:
        result = run_adb(adb_path, ["push", local, remote], timeout=timeout, device_id=device_id)
        return result.returncode == 0 or "pushed" in result.stdout.lower()
    except Exception:
        return False


def pull_file(adb_path: str, device_id: str, remote: str, local: str, timeout: int = 60) -> bool:
    """Pull a file from the device. Returns True on success."""
    try:
        result = run_adb(adb_path, ["pull", remote, local], timeout=timeout, device_id=device_id)
        return result.returncode == 0 or "pulled" in result.stdout.lower()
    except Exception:
        return False
