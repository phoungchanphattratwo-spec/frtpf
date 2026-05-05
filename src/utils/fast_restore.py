"""
Fast Account Restore - Optimized for 10-second per-account performance

Key optimizations:
1. Batch ADB commands to reduce round-trips
2. Skip unnecessary operations (re-login, device registration)
3. Aggressive timeouts with early failure detection
4. Parallel device operations
5. Minimal verification - trust the backup data
"""

import os
import json
import time
import tarfile
import tempfile
import shutil
import sqlite3
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed

from src.core.subprocess_utils import safe_subprocess_run


class FastRestore:
    """Ultra-fast account restore - targets 10 seconds per account"""
    
    def __init__(self, adb_path, log_fn=None):
        self.adb_path = adb_path
        self.log = log_fn or print
        self._device_cache = {}  # Cache device state checks
        
    def _adb(self, device_id, args, timeout=5):
        """ADB command with aggressive timeout"""
        try:
            return safe_subprocess_run(
                [self.adb_path, "-s", device_id] + list(args),
                capture_output=True, text=True, timeout=timeout
            )
        except Exception as e:
            # Return fake result on timeout
            class FakeResult:
                stdout = ""
                stderr = str(e)
                returncode = 1
            return FakeResult()
    
    def _shell(self, device_id, cmd, timeout=5):
        """Shell command with aggressive timeout"""
        r = self._adb(device_id, ["shell", cmd], timeout=timeout)
        return (r.stdout + r.stderr).strip()
    
    def _check_device_fast(self, device_id):
        """Fast device check - cache result for 30s"""
        now = time.time()
        cached = self._device_cache.get(device_id)
        if cached and (now - cached[1]) < 30:
            return cached[0]
        
        # Quick check: just verify device responds
        r = self._adb(device_id, ["get-state"], timeout=2)
        state = (r.stdout + r.stderr).strip()
        is_ok = "device" in state
        self._device_cache[device_id] = (is_ok, now)
        return is_ok
    
    def restore_account_fast(self, account_data, device_id, backup_folder):
        """
        Fast restore - optimized for speed with proper device identity
        
        Returns: (success: bool, message: str, duration: float)
        """
        start_time = time.time()
        uid = account_data.get('account_uid', account_data.get('uid', ''))
        
        try:
            # Step 1: Quick device check (0.5s)
            if not self._check_device_fast(device_id):
                return False, f"Device {device_id[-8:]} not responding", time.time() - start_time
            
            self.log(f"[{device_id[-8:]}] Restoring {uid}")
            
            # Step 2: Force stop Facebook (0.5s)
            self._shell(device_id, "am force-stop com.facebook.katana", timeout=3)
            
            # Step 3: Extract and prepare files locally (2s)
            device_xml_path, fb_data_path = self._extract_backup_fast(backup_folder, uid)
            
            if not device_xml_path or not fb_data_path:
                return False, "Backup extraction failed", time.time() - start_time
            
            # Step 4: Patch files locally (1s)
            self._patch_device_xml_fast(device_xml_path)
            self._patch_fb_data_fast(fb_data_path, uid)
            
            # Step 5: Push everything in one batch (3s)
            success = self._push_all_fast(device_id, device_xml_path, fb_data_path, uid)
            
            if not success:
                return False, "Push failed", time.time() - start_time
            
            # Step 6: Apply device props via resetprop (2s) - CRITICAL for device identity
            self._apply_device_props_fast(device_id, device_xml_path)
            
            # Step 7: Set android_id (1s) - CRITICAL for device identity
            self._set_android_id_fast(device_id, device_xml_path)
            
            # Step 8: Write deviceJson for MaxChanger hook (1s)
            self._write_device_json_fast(device_id, device_xml_path, backup_folder, uid)
            
            # Step 9: Verify MaxChanger setup
            self._verify_maxchanger_fast(device_id)
            
            # Step 10: Clear Facebook cache to force re-read of device info (1s)
            self._clear_facebook_cache_fast(device_id)
            
            # Step 11: Launch Facebook (1s)
            self._shell(device_id, "am start -n com.facebook.katana/.LoginActivity", timeout=3)
            
            # Step 12: Wait for device_id generation (5s) - ensures proper sync
            time.sleep(5)
            
            duration = time.time() - start_time
            self.log(f"[{device_id[-8:]}] ✓ {uid} restored in {duration:.1f}s")
            return True, "OK", duration
            
        except Exception as e:
            duration = time.time() - start_time
            self.log(f"[{device_id[-8:]}] ✗ Error: {e}")
            return False, str(e), duration
    
    def _extract_backup_fast(self, backup_folder, uid):
        """Extract backup files to temp - no verification"""
        device_xml = None
        fb_data = None
        
        try:
            # Extract Device.xml
            device_folder = os.path.join(backup_folder, "Device info")
            if os.path.exists(device_folder):
                tar_files = [f for f in os.listdir(device_folder) if f.endswith('.tar.gz')]
                if tar_files:
                    tmp_dev = tempfile.mkdtemp()
                    with tarfile.open(os.path.join(device_folder, tar_files[0]), 'r:*') as tar:
                        tar.extractall(tmp_dev)
                    # Find Device.xml
                    for root, dirs, files in os.walk(tmp_dev):
                        if 'Device.xml' in files:
                            device_xml = os.path.join(root, 'Device.xml')
                            break
            
            # Extract FB data
            profile_folder = os.path.join(backup_folder, "Profile info")
            if os.path.exists(profile_folder):
                tar_files = [f for f in os.listdir(profile_folder) if f.endswith('.tar.gz')]
                if tar_files:
                    tmp_prof = tempfile.mkdtemp()
                    with tarfile.open(os.path.join(profile_folder, tar_files[0]), 'r:*') as tar:
                        tar.extractall(tmp_prof)
                    # Find com.facebook.katana
                    for root, dirs, files in os.walk(tmp_prof):
                        if os.path.basename(root) == "com.facebook.katana":
                            fb_data = root
                            break
            
            return device_xml, fb_data
            
        except Exception as e:
            self.log(f"Extract error: {e}")
            return None, None
    
    def _patch_device_xml_fast(self, xml_path):
        """Minimal Device.xml patching"""
        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()
            
            # Only add critical missing keys
            existing = {e.get('name') for e in root}
            
            if 'buildtime' not in existing:
                elem = ET.SubElement(root, 'long')
                elem.set('name', 'buildtime')
                elem.set('value', str(int(time.time() * 1000)))
            
            tree.write(xml_path, encoding='utf-8', xml_declaration=True)
        except Exception as e:
            self.log(f"Device.xml patch warning: {e}")
    
    def _patch_fb_data_fast(self, fb_data_path, uid):
        """Minimal FB data patching - only remove device identity"""
        try:
            prefs_db = os.path.join(fb_data_path, "databases", "prefs_db")
            if os.path.exists(prefs_db):
                con = sqlite3.connect(prefs_db)
                cur = con.cursor()
                
                # Only delete critical device identity keys
                critical_keys = [
                    "/shared/device_id",
                    "/shared/PHONEID_APP_DEVICEID_SYNCED",
                    f"/fb_android/ar_activation_registered_{uid}",
                    "/settings/app_state/last_first_run_time",
                ]
                
                for key in critical_keys:
                    cur.execute("DELETE FROM preferences WHERE key=?", (key,))
                
                con.commit()
                con.close()
            
            # Remove GMS file
            gms_file = os.path.join(fb_data_path, "shared_prefs", "com.google.android.gms.appid.xml")
            if os.path.exists(gms_file):
                os.remove(gms_file)
                
        except Exception as e:
            self.log(f"FB data patch warning: {e}")
    
    def _push_all_fast(self, device_id, device_xml_path, fb_data_path, uid):
        """Push all files in optimized batches with device reconnection handling"""
        try:
            # Check device before starting
            if not self._check_device_fast(device_id):
                self.log(f"Device {device_id[-8:]} not responding before push")
                return False
            
            # Push Device.xml first (small file, fast)
            r = self._adb(device_id, ["push", device_xml_path, "/data/local/tmp/Device.xml"], timeout=5)
            if r.returncode != 0:
                self.log(f"Device.xml push failed: {r.stderr[:100]}")
                return False
            
            # Push FB data (large, may cause device to disconnect temporarily)
            self.log(f"Pushing FB data (~6MB)...")
            r = self._adb(device_id, ["push", fb_data_path, "/data/local/tmp/fb_restore"], timeout=30)
            
            # Device may disconnect during large push - wait and retry
            if r.returncode != 0 or "device" in r.stderr.lower() and "not found" in r.stderr.lower():
                self.log(f"Device disconnected during push, waiting 2s...")
                time.sleep(2)
                
                # Clear cache and recheck
                self._device_cache.pop(device_id, None)
                if not self._check_device_fast(device_id):
                    self.log(f"Device {device_id[-8:]} did not reconnect")
                    return False
                
                # Retry push
                self.log(f"Retrying push...")
                r = self._adb(device_id, ["push", fb_data_path, "/data/local/tmp/fb_restore"], timeout=30)
                if r.returncode != 0:
                    return False
            
            # Create and execute restore script
            script_lines = [
                "#!/system/bin/sh",
                "am force-stop com.facebook.katana",
                "rm -rf /data/data/com.facebook.katana/databases",
                "rm -rf /data/data/com.facebook.katana/shared_prefs",
                "rm -rf /data/data/com.facebook.katana/app_light_prefs",
                "rm -rf /data/data/com.facebook.katana/files",
                "mkdir -p /data/data/com.facebook.katana/databases",
                "mkdir -p /data/data/com.facebook.katana/shared_prefs",
                "mkdir -p /data/data/com.facebook.katana/app_light_prefs",
                "mkdir -p /data/data/com.facebook.katana/files",
                "mkdir -p /data/data/com.minsoftware.maxchanger/shared_prefs",
                "cp -rp /data/local/tmp/fb_restore/. /data/data/com.facebook.katana/",
                "cp /data/local/tmp/Device.xml /data/data/com.minsoftware.maxchanger/shared_prefs/",
                "FB_UID=$(stat -c %u /data/data/com.facebook.katana 2>/dev/null || echo 10182)",
                "MC_UID=$(stat -c %u /data/data/com.minsoftware.maxchanger 2>/dev/null || echo 10183)",
                "chown -R $FB_UID:$FB_UID /data/data/com.facebook.katana",
                "chmod -R 771 /data/data/com.facebook.katana",
                "chown $MC_UID:$MC_UID /data/data/com.minsoftware.maxchanger/shared_prefs/Device.xml",
                "chmod 664 /data/data/com.minsoftware.maxchanger/shared_prefs/Device.xml",
                # NOTE: Do NOT remove auth files - they contain the session!
                # Only remove GMS file which was already removed during local patching
                "rm -rf /data/local/tmp/fb_restore",
                "rm /data/local/tmp/Device.xml",
                "echo DONE",
            ]
            
            # Write and push script
            tmp_script = tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False)
            tmp_script.write('\n'.join(script_lines))
            tmp_script.close()
            
            self._adb(device_id, ["push", tmp_script.name, "/data/local/tmp/restore.sh"], timeout=5)
            
            # Execute script as root with retry
            result = self._shell(device_id, 'su -c "sh /data/local/tmp/restore.sh"', timeout=15)
            
            # If device disconnected during execution, wait and check result
            if "not found" in result.lower():
                self.log(f"Device disconnected during script execution, waiting...")
                time.sleep(2)
                self._device_cache.pop(device_id, None)
                
                # Check if restore actually completed by verifying files exist
                check = self._shell(device_id, 'su -c "ls /data/data/com.facebook.katana/databases/prefs_db"', timeout=5)
                if "prefs_db" in check:
                    self.log(f"Restore completed despite disconnection")
                    result = "DONE"
            
            # Cleanup local temp
            try:
                os.unlink(tmp_script.name)
            except:
                pass
            
            return "DONE" in result
            
        except Exception as e:
            self.log(f"Push error: {e}")
            return False
    
    def restore_multiple_parallel(self, account_device_pairs, max_workers=5):
        """
        Restore multiple accounts in parallel
        
        Args:
            account_device_pairs: List of (account_data, device_id, backup_folder) tuples
            max_workers: Max parallel operations
            
        Returns:
            List of (success, message, duration) tuples
        """
        results = []
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(
                    self.restore_account_fast,
                    acc_data,
                    dev_id,
                    backup_folder
                ): (acc_data, dev_id)
                for acc_data, dev_id, backup_folder in account_device_pairs
            }
            
            for future in as_completed(futures):
                acc_data, dev_id = futures[future]
                try:
                    result = future.result()
                    results.append((acc_data, dev_id, result))
                except Exception as e:
                    results.append((acc_data, dev_id, (False, str(e), 0)))
        
        return results
    
    def _apply_device_props_fast(self, device_id, device_xml_path):
        """Apply device properties via resetprop - CRITICAL for device identity"""
        try:
            tree = ET.parse(device_xml_path)
            props = {}
            for elem in tree.getroot():
                props[elem.get('name', '')] = (elem.get('value') or elem.text or '').strip()
            
            # Map Device.xml keys to Android build props
            prop_map = {
                'brand': 'ro.product.brand',
                'manufacturer': 'ro.product.manufacturer',
                'model': 'ro.product.model',
                'device': 'ro.product.device',
                'product': 'ro.product.name',
                'fingerprint': 'ro.build.fingerprint',
                'build_id': 'ro.build.id',
                'release': 'ro.build.version.release',
                'incremental': 'ro.build.version.incremental',
                'serial': 'ro.serialno',
            }
            
            # Build resetprop command
            commands = []
            for xml_key, prop_name in prop_map.items():
                value = props.get(xml_key, '')
                if value:
                    # Escape special characters
                    value = value.replace('"', '\\"').replace('$', '\\$')
                    commands.append(f'resetprop "{prop_name}" "{value}"')
            
            if commands:
                script = ' && '.join(commands)
                result = self._shell(device_id, f'su -c "{script}"', timeout=10)
                self.log(f"[{device_id[-8:]}] Device props applied: {props.get('brand', '')} {props.get('model', '')}")
            
        except Exception as e:
            self.log(f"[{device_id[-8:]}] Device props warning: {e}")
    
    def _set_android_id_fast(self, device_id, device_xml_path):
        """Set android_id via Settings.Secure - CRITICAL for device identity"""
        try:
            tree = ET.parse(device_xml_path)
            props = {}
            for elem in tree.getroot():
                props[elem.get('name', '')] = (elem.get('value') or elem.text or '').strip()
            
            android_id = props.get('android_id') or props.get('androidId', '')
            if android_id:
                # Set android_id
                self._shell(device_id, f'su -c "settings put secure android_id {android_id}"', timeout=5)
                
                # Verify
                verify = self._shell(device_id, 'settings get secure android_id', timeout=3)
                if android_id in verify:
                    self.log(f"[{device_id[-8:]}] android_id set: {android_id}")
                else:
                    self.log(f"[{device_id[-8:]}] android_id verify failed")
            
        except Exception as e:
            self.log(f"[{device_id[-8:]}] android_id warning: {e}")
    
    def _write_device_json_fast(self, device_id, device_xml_path, backup_folder, uid):
        """Write deviceJson.txt for MaxChanger hook - ensures device identity on app launch"""
        try:
            tree = ET.parse(device_xml_path)
            dprops = {}
            for elem in tree.getroot():
                dprops[elem.get('name', '')] = (elem.get('value') or elem.text or '').strip()
            
            # Build deviceJson
            device_json = {
                "imei": dprops.get('imei', ''),
                "board": dprops.get('board', 'unknown'),
                "bootloader": dprops.get('bootloader', 'unknown'),
                "brand": dprops.get('brand', ''),
                "buildtime": int(dprops['buildtime']) if dprops.get('buildtime', '').lstrip('-').isdigit() else int(time.time() * 1000),
                "cpu_abi": dprops.get('cpu_abi', 'arm64-v8a'),
                "cpu_abi2": dprops.get('cpu_abi2', 'armeabi-v7a'),
                "device": dprops.get('device', ''),
                "display": dprops.get('build_display', dprops.get('display', '')),
                "fingerprint": dprops.get('fingerprint', ''),
                "gpuVersion": dprops.get('gpuVersion', 'unknown'),
                "hardware": dprops.get('hardware', 'unknown'),
                "host": dprops.get('host', 'unknown'),
                "imsi": dprops.get('imsi', ''),
                "incremental": dprops.get('incremental', ''),
                "manufacturer": dprops.get('manufacturer', ''),
                "model": dprops.get('model', ''),
                "product": dprops.get('product', ''),
                "radioVersion": dprops.get('radioVersion', dprops.get('radio_version', '')),
                "release": dprops.get('release', ''),
                "serial": dprops.get('serial', ''),
                "simserial": dprops.get('simserial', ''),
                "wifimac": dprops.get('wifimac', dprops.get('wifi_mac', '')),
                "android_id": dprops.get('android_id', ''),
                "androidId": dprops.get('android_id', dprops.get('androidId', '')),
            }
            
            import json as _json
            device_json_str = _json.dumps(device_json, separators=(',', ':'))
            
            # Write to temp file
            tmp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt')
            tmp_file.write(device_json_str)
            tmp_file.close()
            
            # Create directories and push
            self._shell(device_id, 'su -c "mkdir -p /data/local/tmp/nk && chmod 777 /data/local/tmp/nk"', timeout=5)
            self._adb(device_id, ["push", tmp_file.name, "/data/local/tmp/nk/deviceJson.txt"], timeout=5)
            self._shell(device_id, 'su -c "chmod 777 /data/local/tmp/nk/deviceJson.txt"', timeout=3)
            
            # Also push to sdcard as backup
            self._shell(device_id, "mkdir -p /sdcard/nk", timeout=3)
            self._adb(device_id, ["push", tmp_file.name, "/sdcard/nk/deviceJson.txt"], timeout=5)
            
            # Cleanup
            try:
                os.unlink(tmp_file.name)
            except:
                pass
            
            self.log(f"[{device_id[-8:]}] deviceJson: {device_json.get('brand')} {device_json.get('model')}")
            
        except Exception as e:
            self.log(f"[{device_id[-8:]}] deviceJson warning: {e}")
    
    def _verify_maxchanger_fast(self, device_id):
        """Verify MaxChanger is properly set up"""
        try:
            # Check if MaxChanger is installed
            result = self._shell(device_id, "pm list packages | grep maxchanger", timeout=5)
            if "maxchanger" not in result.lower():
                self.log(f"[{device_id[-8:]}] ⚠️ MaxChanger not installed - device spoofing may not work")
                return False
            
            # Check if Device.xml exists and is readable
            check = self._shell(device_id, 'su -c "cat /data/data/com.minsoftware.maxchanger/shared_prefs/Device.xml | head -c 50"', timeout=5)
            if "<?xml" in check:
                self.log(f"[{device_id[-8:]}] MaxChanger Device.xml verified")
            else:
                self.log(f"[{device_id[-8:]}] ⚠️ Device.xml not readable")
            
            # Check if deviceJson.txt exists
            check2 = self._shell(device_id, 'su -c "cat /data/local/tmp/nk/deviceJson.txt | head -c 50"', timeout=5)
            if "{" in check2:
                self.log(f"[{device_id[-8:]}] deviceJson.txt verified")
            else:
                self.log(f"[{device_id[-8:]}] ⚠️ deviceJson.txt not readable")
            
            return True
            
        except Exception as e:
            self.log(f"[{device_id[-8:]}] MaxChanger verify warning: {e}")
            return False
    
    def _clear_facebook_cache_fast(self, device_id):
        """Clear Facebook cache to force re-read of device info"""
        try:
            # Clear app cache (not data - preserves session)
            self._shell(device_id, "pm clear com.facebook.katana --cache-only", timeout=5)
            
            # Also clear specific cached device info files
            self._shell(device_id, 'su -c "rm -f /data/data/com.facebook.katana/cache/*"', timeout=5)
            
            self.log(f"[{device_id[-8:]}] Facebook cache cleared")
            
        except Exception as e:
            self.log(f"[{device_id[-8:]}] Cache clear warning: {e}")
