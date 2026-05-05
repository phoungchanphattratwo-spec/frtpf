"""
MaxChangeWorker — background QThread that applies MaxChange device
spoofing to one or more Android devices without blocking the UI.

Emits:
    progress(str)           — activity-log message
    finished(int, list)     — (success_count, all_device_ids)
    spoof_updated(str, str) — (device_id, fake_model)  for live table update
"""

from __future__ import annotations
import json
import os
import random
import subprocess
import tempfile
import time

from PyQt6.QtCore import QThread, pyqtSignal

MAXCHANGE_PKG = "com.minsoftware.maxchanger"


class MaxChangeWorker(QThread):
    """Apply MaxChange device spoofing in a background thread."""

    progress      = pyqtSignal(str)        # activity-log messages
    finished      = pyqtSignal(int, list)  # (success_count, device_ids)
    spoof_updated = pyqtSignal(str, str)   # (device_id, fake_model)

    def __init__(
        self,
        device_ids: list[str],
        brand_filter: str,
        adb_path: str,
        base_dir: str,
    ):
        super().__init__()
        self.device_ids    = device_ids
        self.brand_filter  = brand_filter
        self.adb_path      = adb_path
        self.base_dir      = base_dir
        self.maxchanger_dir = os.path.join(base_dir, "maxchanger")
        self.success_count  = 0

    # ── helpers ───────────────────────────────────────────────────────────────

    def _shell(self, device_id: str, cmd: str) -> str:
        try:
            result = subprocess.run(
                f'"{self.adb_path}" -s {device_id} shell {cmd}',
                shell=True, capture_output=True, text=True, timeout=30,
            )
            return result.stdout.strip()
        except Exception:
            return ""

    def _push(self, device_id: str, local: str, remote: str) -> bool:
        try:
            cmd = f'"{self.adb_path}" -s {device_id} push "{local}" "{remote}"'
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60)
            ok = result.returncode == 0 or "pushed" in result.stdout.lower()
            if not ok:
                self.progress.emit(f"⚠️ {device_id}: push error: {(result.stderr or result.stdout or '').strip()[:100]}")
            return ok
        except Exception as exc:
            self.progress.emit(f"⚠️ {device_id}: push exception: {str(exc)[:100]}")
            return False

    def _get_device_name(self, device_id: str) -> str:
        """Read fake fingerprint from MaxChange Device.xml."""
        import re
        xml = self._shell(device_id, 'su -c "cat /data/data/com.minsoftware.maxchanger/shared_prefs/Device.xml"')
        if xml:
            fp = re.search(r'name="fingerprint"[^>]*>([^<]+)<', xml)
            tc = re.search(r'name="time_check"[^>]*>([^<]+)<', xml)
            if fp and tc and fp.group(1) and tc.group(1):
                return fp.group(1) + tc.group(1)
        return ""

    def _get_model_from_xml(self, device_id: str) -> str:
        """Read fake brand/model from MaxChange Device.xml."""
        import re
        xml = self._shell(device_id, 'su -c "cat /data/data/com.minsoftware.maxchanger/shared_prefs/Device.xml"')
        if not xml:
            return ""
        brand_m = re.search(r'name="brand"[^>]*>([^<]+)<', xml)
        model_m = re.search(r'name="model"[^>]*>([^<]+)<', xml)
        brand = brand_m.group(1).strip() if brand_m else ""
        model = model_m.group(1).strip() if model_m else ""
        if brand and model:
            return f"{brand} {model}"
        return model or brand

    # ── PushFileInfo mode ─────────────────────────────────────────────────────

    def _push_file_info(self, device_id: str, profile_name: str) -> bool:
        if not profile_name:
            return False
        local_file = os.path.join(self.maxchanger_dir, f"{profile_name}.tar.gz")
        if not os.path.exists(local_file):
            self.progress.emit(f"⚠️ {device_id}: Profile {profile_name}.tar.gz not found")
            return False

        mc_data = f"/data/data/{MAXCHANGE_PKG}"
        tar_filename = f"{profile_name}.tar.gz"

        self._shell(device_id, f"pm clear {MAXCHANGE_PKG}")
        self._shell(device_id, f"pm grant {MAXCHANGE_PKG} android.permission.READ_EXTERNAL_STORAGE")
        self._shell(device_id, f"pm grant {MAXCHANGE_PKG} android.permission.WRITE_EXTERNAL_STORAGE")

        self.progress.emit(f"📦 {device_id}: Pushing profile...")
        if not self._push(device_id, local_file, f"/sdcard/{tar_filename}"):
            self.progress.emit(f"❌ {device_id}: Failed to push file")
            return False

        self._shell(device_id, f'su -c "cp /sdcard/{tar_filename} {mc_data}/{tar_filename}"')
        self._shell(device_id, f'su -c "tar -xzvf {mc_data}/{tar_filename} -C /"')

        owner_group = self._shell(device_id, f'su -c "stat -c %u:%g {mc_data}"').strip()
        if not owner_group or ":" not in owner_group:
            import re
            uid_line = self._shell(device_id, f"dumpsys package {MAXCHANGE_PKG} | grep userId=")
            m = re.search(r"userId=(\d+)", uid_line)
            if m:
                uid = m.group(1)
                owner_group = f"{uid}:{uid}"

        if owner_group and ":" in owner_group:
            self._shell(device_id, f'su -c "chown -R {owner_group} {mc_data}"')
            self.progress.emit(f"✅ {device_id}: PushFile success (owner={owner_group})")
        else:
            self.progress.emit(f"⚠️ {device_id}: Could not determine owner, files extracted")

        self._shell(device_id, f'su -c "rm /sdcard/{tar_filename}"')
        self._shell(device_id, f'su -c "rm {mc_data}/{tar_filename}"')
        return True

    # ── Broadcast mode ────────────────────────────────────────────────────────

    def _change_via_broadcast(self, device_id: str) -> bool:
        self._shell(device_id, f"pm clear {MAXCHANGE_PKG}")
        self._shell(device_id, f"pm grant {MAXCHANGE_PKG} android.permission.READ_EXTERNAL_STORAGE")
        self._shell(device_id, f"pm grant {MAXCHANGE_PKG} android.permission.WRITE_EXTERNAL_STORAGE")

        old_name = self._get_device_name(device_id)
        cmd = f"am broadcast -a com.minsoftware.maxchanger.CHANGE -n {MAXCHANGE_PKG}/.AdbCaller"

        if self.brand_filter and self.brand_filter != "Random":
            brands = [b.strip() for b in self.brand_filter.split("|") if b.strip()]
            if brands:
                chosen = random.choice(brands)
                cmd = (
                    f'am broadcast -a com.minsoftware.maxchanger.CHANGE '
                    f'--es "brand" "{chosen}" -n {MAXCHANGE_PKG}/.AdbCaller'
                )
                self.progress.emit(f"🎯 {device_id}: Using brand: {chosen}")

        self.progress.emit(f"📡 {device_id}: Broadcasting change command...")
        result = self._shell(device_id, cmd)

        if "Broadcast completed" in result:
            time.sleep(2)
            new_name = self._get_device_name(device_id)
            if new_name and new_name != old_name:
                self.progress.emit(f"✅ {device_id}: Broadcast change successful")
                return True
            self.progress.emit(f"⚠️ {device_id}: Broadcast sent but device unchanged")
        else:
            self.progress.emit(f"❌ {device_id}: Broadcast failed")
        return False

    # ── Per-device orchestration ──────────────────────────────────────────────

    def _apply_to_device(self, device_id: str) -> bool:
        # Ensure MaxChange is installed
        check = self._shell(device_id, f"pm list packages {MAXCHANGE_PKG}")
        if MAXCHANGE_PKG not in check:
            self.progress.emit(f"📦 {device_id}: Installing MaxChange...")
            for name in ("maxchange.apk", "maxchangev2.apk", "MaxChange.apk"):
                apk = os.path.join(self.base_dir, "app", name)
                if os.path.exists(apk):
                    subprocess.run(
                        f'"{self.adb_path}" -s {device_id} install -r "{apk}"',
                        shell=True, capture_output=True, timeout=60,
                    )
                    time.sleep(2)
                    break

        success = False
        profile_name = None

        # Try PushFileInfo first (unless brand filter is set)
        use_broadcast_only = bool(self.brand_filter and self.brand_filter != "Random")
        if not use_broadcast_only and os.path.isdir(self.maxchanger_dir):
            tar_files = [f for f in os.listdir(self.maxchanger_dir) if f.endswith(".tar.gz")]
            if tar_files:
                profile_name = random.choice(tar_files).replace(".tar.gz", "")
                self.progress.emit(f"📁 {device_id}: Using profile: {profile_name}")
                if self._push_file_info(device_id, profile_name):
                    for _ in range(5):
                        time.sleep(1)
                        if self._get_device_name(device_id):
                            success = True
                            self.progress.emit(f"✅ {device_id}: PushFileInfo verified")
                            break
                    if not success:
                        self.progress.emit(f"⚠️ {device_id}: Device.xml not found after push")

        # Fallback to broadcast
        if not success:
            msg = "⚠️ PushFileInfo failed, trying broadcast..." if profile_name else "🔧 No profiles, using broadcast..."
            self.progress.emit(f"{device_id}: {msg}")
            success = self._change_via_broadcast(device_id)

        if success:
            fake_model = self._get_model_from_xml(device_id) or self._shell(device_id, "getprop ro.product.model").strip()
            self.progress.emit(f"✅ {device_id}: Changed to {fake_model}")

            # Persist to spoof cache
            try:
                cache_file = os.path.join(tempfile.gettempdir(), "frt_device_spoof_cache.json")
                cache: dict = {}
                if os.path.exists(cache_file):
                    with open(cache_file, "r", encoding="utf-8") as fh:
                        cache = json.load(fh)
                cache[device_id] = fake_model
                with open(cache_file, "w", encoding="utf-8") as fh:
                    json.dump(cache, fh)
            except Exception:
                pass

            self.spoof_updated.emit(device_id, fake_model)

            # Open Device Info HW to verify
            subprocess.run(
                f'"{self.adb_path}" -s {device_id} shell am start -n ru.andr7e.deviceinfohw/.MainActivity',
                shell=True, capture_output=True, timeout=10,
            )
            return True

        self.progress.emit(f"❌ {device_id}: Failed to change device")
        return False

    # ── QThread.run ───────────────────────────────────────────────────────────

    def run(self) -> None:
        failed: list[str] = []
        for i, device_id in enumerate(self.device_ids):
            self.progress.emit(f"[{i+1}/{len(self.device_ids)}] 📱 {device_id}: Starting MaxChange...")
            try:
                if self._apply_to_device(device_id):
                    self.success_count += 1
                else:
                    failed.append(device_id)
            except Exception as exc:
                self.progress.emit(f"❌ {device_id}: Exception — {str(exc)[:120]}")
                failed.append(device_id)

        self.finished.emit(self.success_count, self.device_ids)
