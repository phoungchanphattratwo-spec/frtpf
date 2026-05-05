"""
DeviceWorker — background QThread that fetches ADB device info
without blocking the UI thread.

Emits:
    done(list)  — list of tuples:
        (device_id, brand, model, android_ver, battery, resolution,
         account_uid, order_num)
"""

from __future__ import annotations
import json
import os
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed

from PyQt6.QtCore import QThread, pyqtSignal


class DeviceWorker(QThread):
    """Fetch connected ADB device info in a background thread."""

    done = pyqtSignal(list)

    def __init__(self, adb_path: str):
        super().__init__()
        self._adb = adb_path

    # ── main thread entry ─────────────────────────────────────────────────────
    def run(self) -> None:
        import re as _re

        adb = self._adb
        devices_raw: list[str] = []

        # 1. Get connected device serials
        try:
            r = subprocess.run(
                [adb, "devices"],
                capture_output=True, text=True,
                timeout=5, encoding="utf-8", errors="ignore",
            )
            for line in r.stdout.strip().splitlines()[1:]:
                line = line.strip()
                if line and line.endswith("device"):
                    devices_raw.append(line.split()[0])
        except Exception:
            pass

        # 2. Load / update persistent wallpaper-order numbers
        device_numbers: dict[str, int] = {}
        num_file = os.path.join(tempfile.gettempdir(), "frt_device_numbers.json")
        try:
            if os.path.exists(num_file):
                with open(num_file, "r", encoding="utf-8") as fh:
                    device_numbers = json.load(fh)
        except Exception:
            pass

        existing_numbers = set(device_numbers.values())
        next_num = 1
        for dev_id in sorted(devices_raw):
            if dev_id not in device_numbers:
                while next_num in existing_numbers:
                    next_num += 1
                device_numbers[dev_id] = next_num
                existing_numbers.add(next_num)
                next_num += 1

        try:
            with open(num_file, "w", encoding="utf-8") as fh:
                json.dump(device_numbers, fh, indent=2)
        except Exception:
            pass

        # Sort by order number
        devices_raw.sort(key=lambda d: device_numbers.get(d, 9999))

        # 3. Load assigned-account map from device cache
        assigned_map: dict[str, str] = {}
        cache_file = os.path.join(tempfile.gettempdir(), "frt_device_cache.json")
        try:
            if os.path.exists(cache_file):
                with open(cache_file, "r", encoding="utf-8") as fh:
                    cache = json.load(fh)
                for uid, data in cache.items():
                    serial = data.get("device_serial", "")
                    if serial:
                        assigned_map[serial.split()[0]] = uid
        except Exception:
            pass

        # 4. Helper functions
        def _prop(dev: str, prop: str) -> str:
            try:
                res = subprocess.run(
                    [adb, "-s", dev, "shell", f"getprop {prop}"],
                    capture_output=True, text=True,
                    timeout=3, encoding="utf-8", errors="ignore",
                )
                return res.stdout.strip() if res.returncode == 0 else ""
            except Exception:
                return ""

        def _shell(dev: str, cmd: str) -> str:
            try:
                res = subprocess.run(
                    [adb, "-s", dev, "shell", cmd],
                    capture_output=True, text=True,
                    timeout=3, encoding="utf-8", errors="ignore",
                )
                return res.stdout.strip() if res.returncode == 0 else ""
            except Exception:
                return ""

        def _fetch(dev_id: str) -> tuple:
            brand   = _prop(dev_id, "ro.product.brand")
            model   = _prop(dev_id, "ro.product.model")
            android = _prop(dev_id, "ro.build.version.release")

            bat_raw = _shell(dev_id, "dumpsys battery | grep level")
            battery = ""
            if bat_raw:
                bm = _re.search(r"level:\s*(\d+)", bat_raw)
                battery = f"{bm.group(1)}%" if bm else ""

            res_raw = _shell(dev_id, "wm size")
            resolution = ""
            if res_raw:
                rm = _re.search(r"(\d+x\d+)", res_raw)
                resolution = rm.group(1) if rm else ""

            account_uid = assigned_map.get(dev_id, "—")
            order_num   = device_numbers.get(dev_id, "—")
            return (dev_id, brand, model, android, battery, resolution, account_uid, order_num)

        # 5. Fetch all devices in parallel
        rows_map: dict[str, tuple] = {}
        if devices_raw:
            with ThreadPoolExecutor(max_workers=min(len(devices_raw), 10)) as pool:
                futures = {pool.submit(_fetch, d): d for d in devices_raw}
                for future in as_completed(futures):
                    try:
                        result = future.result()
                        rows_map[result[0]] = result
                    except Exception:
                        pass

        rows = [rows_map[d] for d in devices_raw if d in rows_map]
        self.done.emit(rows)
