"""
FacebookRegistration — Appium + UiAutomator2 driven Facebook Lite signup flow.

Each instance handles one device / one registration attempt.
Instantiate, call .register(), then discard.
"""

from __future__ import annotations
import os
import re
import shutil
import tempfile
import time

from appium import webdriver
from appium.options.android import UiAutomator2Options
from appium.webdriver.common.appiumby import AppiumBy

from src.ui.widgets import LogSignal
from src.core.constants import (
    APPIUM_SERVER_URL,
    FB_LITE_PACKAGE,
    FB_KATANA_PACKAGE,
)

class FacebookRegistration:
    def __init__(self, apk_path: str, device_name: str, log_signal: LogSignal, action_delay: float = 2.0, safety_mode: bool = True, app_selection: str = "Facebook Lite"):
        self.apk_path = apk_path
        self.device_name = device_name
        self.driver = None
        self.log_signal = log_signal
        self.stop_flag = False
        self.action_delay = action_delay
        self.safety_mode = safety_mode
        self.app_selection = app_selection  # Store app selection (used for UID extraction only)
        # Note: Registration always uses Facebook Lite APK, app_selection only affects UID extraction package
        
    def log(self, msg):
        try:
            if self.log_signal and hasattr(self.log_signal, 'log'):
                self.log_signal.log.emit(msg)
        except (RuntimeError, AttributeError):
            # LogSignal has been deleted or is invalid, print to console instead
            print(msg)
        
    def _setup_driver(self):
        options = UiAutomator2Options()
        options.platform_name = "Android"
        options.device_name = self.device_name
        
        # Detect if using Facebook Katana (main app) or Lite based on APK filename
        is_katana = 'katana' in self.apk_path.lower()
        
        # Create a temporary copy of APK for this device to avoid file locking
        # when multiple Appium sessions try to sign the same file
        import shutil
        import tempfile
        temp_dir = tempfile.gettempdir()
        device_id = self.device_name.replace(':', '_').replace('.', '_')
        apk_filename = os.path.basename(self.apk_path)
        temp_apk = os.path.join(temp_dir, f"{device_id}_{apk_filename}")
        
        # Copy APK if it doesn't exist or is older than source
        if not os.path.exists(temp_apk) or os.path.getmtime(self.apk_path) > os.path.getmtime(temp_apk):
            try:
                shutil.copy2(self.apk_path, temp_apk)
                self.log(f"[*] Created temporary APK copy for device")
            except Exception as e:
                self.log(f"[!] Could not create APK copy, using original: {e}")
                temp_apk = self.apk_path
        
        # Use the temporary APK copy
        options.app = temp_apk
        
        # Set explicit package and activity to bypass manifest reading issues
        if is_katana:
            options.app_package = "com.facebook.katana"
            # Don't set activity - let it install but we'll launch manually with ADB
            options.app_activity = "com.facebook.katana.LoginActivity"  # This is the exported launcher activity
            options.app_wait_activity = "*"  # Accept any activity - don't validate
            self.log(f"[*] Using Facebook (Katana) APK: {os.path.basename(self.apk_path)}")
            self.log(f"[*] Will launch with registration intent")
            
            # Additional capabilities for Facebook Katana stability
            options.skip_logcat_capture = True  # Reduce overhead
            options.disable_suppress_accessibility_service = True  # Allow accessibility
            options.ignore_unimportant_views = True  # Faster element finding
            options.dont_stop_app_on_reset = True  # Don't stop app when resetting
        else:
            options.app_package = "com.facebook.lite"
            options.app_activity = "com.facebook.lite.MainActivity"
            self.log(f"[*] Using Facebook Lite APK: {os.path.basename(self.apk_path)}")
        
        # Additional options to help with app stability
        options.auto_grant_permissions = True
        options.new_command_timeout = 300  # 5 minutes timeout
        options.adb_exec_timeout = 60000  # 60 seconds for ADB commands
        options.ensure_webviews_have_pages = True  # Ensure webviews are ready
        
        # Don't wait for app to be idle - helps with apps that have background processes
        options.wait_for_idle_timeout = 0
        
        if self.app_selection != "Facebook Lite":
            self.log(f"[*] Note: Will check {self.app_selection} package for UID extraction")
        
        options.automation_name = "UiAutomator2"
        options.no_reset = True  # Don't reset app state
        options.full_reset = False  # Don't uninstall app
        
        self.log("[*] Connecting to Appium server...")
        try:
            self.driver = webdriver.Remote("http://127.0.0.1:4723", options=options)
            self.driver.implicitly_wait(3)  # Reduced from 10 to 3 seconds for faster response
            self.log("[+] Connected successfully!")
            
            # For Facebook Katana, just launch the app normally
            # We'll navigate to registration using coordinates
            if is_katana:
                self.log("[*] Launching Facebook Katana...")
                try:
                    # Stop the app first to ensure clean state
                    self.driver.terminate_app("com.facebook.katana")
                    time.sleep(2)
                    
                    # Launch the app normally
                    base_dir = os.path.dirname(os.path.abspath(__file__))
                    adb_path = os.path.join(base_dir, "platform-tools", "platform-tools", "adb.exe")
                    if not os.path.exists(adb_path):
                        adb_path = os.path.join(base_dir, "platform-tools", "adb.exe")
                    launch_cmd = f'"{adb_path}" -s {self.device_name} shell monkey -p com.facebook.katana -c android.intent.category.LAUNCHER 1'
                    subprocess.run(launch_cmd, shell=True, capture_output=True, timeout=10)
                    self.log("[+] Launched Facebook Katana")
                    time.sleep(3)
                        
                except Exception as e:
                    self.log(f"[!] Could not launch app: {e}")
                    self.log("[*] Continuing with default launch...")
            
        except Exception as e:
            self.log(f"[!] Connection failed: {str(e)[:200]}")
            raise
    
    def _check_session_alive(self):
        """Check if Appium session is still alive."""
        try:
            # Try to get current activity - if this fails, session is dead
            self.driver.current_activity
            return True
        except:
            return False
    
    # ═══════════════════════════════════════════════════════════════════════
    # MaxChange Device Spoofing Integration (Professional Implementation)
    def _adb_shell(self, command):
        """Execute ADB shell command on the device."""
        base_dir = os.path.dirname(os.path.abspath(__file__))
        adb_path = os.path.join(base_dir, "platform-tools", "platform-tools", "adb.exe")
        if not os.path.exists(adb_path):
            adb_path = os.path.join(base_dir, "platform-tools", "adb.exe")
        full_cmd = f'"{adb_path}" -s {self.device_name} shell {command}'
        try:
            result = subprocess.run(full_cmd, shell=True, capture_output=True, text=True, timeout=30)
            return result.stdout.strip()
        except Exception as e:
            self.log(f"[!] ADB shell error: {e}")
            return ""
    
    def _adb_push(self, local_path, remote_path):
        """Push file to device via ADB."""
        base_dir = os.path.dirname(os.path.abspath(__file__))
        adb_path = os.path.join(base_dir, "platform-tools", "platform-tools", "adb.exe")
        if not os.path.exists(adb_path):
            adb_path = os.path.join(base_dir, "platform-tools", "adb.exe")
        cmd = f'"{adb_path}" -s {self.device_name} push "{local_path}" "{remote_path}"'
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60)
            return "pushed" in result.stdout.lower() or result.returncode == 0
        except Exception as e:
            self.log(f"[!] ADB push error: {e}")
            return False
    
    def _adb_pull(self, remote_path, local_path):
        """Pull file from device via ADB."""
        base_dir = os.path.dirname(os.path.abspath(__file__))
        adb_path = os.path.join(base_dir, "platform-tools", "platform-tools", "adb.exe")
        if not os.path.exists(adb_path):
            adb_path = os.path.join(base_dir, "platform-tools", "adb.exe")
        cmd = f'"{adb_path}" -s {self.device_name} pull "{remote_path}" "{local_path}"'
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60)
            return os.path.exists(local_path)
        except Exception as e:
            self.log(f"[!] ADB pull error: {e}")
            return False
    
    def _mc_grant_permissions(self):
        """Grant storage permissions to MaxChange (matches C# FF8F0998)."""
        MAXCHANGE_PKG = "com.minsoftware.maxchanger"
        self._adb_shell(f"pm grant {MAXCHANGE_PKG} android.permission.READ_EXTERNAL_STORAGE")
        self._adb_shell(f"pm grant {MAXCHANGE_PKG} android.permission.WRITE_EXTERNAL_STORAGE")
    
    def _mc_open(self):
        """Open MaxChange app via monkey command (matches C# OpenMaxChange)."""
        self.log("[*] Opening MaxChange app...")
        self._adb_shell("monkey -p com.minsoftware.maxchanger -c android.intent.category.LAUNCHER 1")
        time.sleep(3)
    
    def _mc_get_device_name(self, timeout_sec=0):
        """
        Read fake device fingerprint from MaxChange shared_prefs/Device.xml.
        Returns fingerprint+time_check string, or "" on failure.
        Matches C# GetNameDevicefake(int_2).
        """
        start = time.time()
        while True:
            xml_text = self._adb_shell('su -c "cat /data/data/com.minsoftware.maxchanger/shared_prefs/Device.xml"')
            if xml_text:
                try:
                    import re
                    # Parse XML to extract fingerprint and time_check
                    fp_match = re.search(r'name="fingerprint"[^>]*>([^<]+)<', xml_text)
                    tc_match = re.search(r'name="time_check"[^>]*>([^<]+)<', xml_text)
                    if fp_match and tc_match and fp_match.group(1) and tc_match.group(1):
                        result = fp_match.group(1) + tc_match.group(1)
                        return result
                except Exception:
                    pass
            # If no timeout, return immediately after first try
            if timeout_sec == 0:
                break
            time.sleep(2)
            if time.time() - start >= timeout_sec:
                break
        return ""
    
    def _mc_get_model_from_xml(self):
        """
        Read the fake model/brand from MaxChange's Device.xml.
        Extracts 'brand' and 'model' fields, or parses from fingerprint.
        Returns a display string like 'Samsung SM-G991B'.
        """
        xml_text = self._adb_shell('su -c "cat /data/data/com.minsoftware.maxchanger/shared_prefs/Device.xml"')
        if not xml_text:
            return ""
        try:
            import re
            brand_m = re.search(r'name="brand"[^>]*>([^<]+)<', xml_text)
            model_m = re.search(r'name="model"[^>]*>([^<]+)<', xml_text)
            brand = brand_m.group(1).strip() if brand_m else ""
            model = model_m.group(1).strip() if model_m else ""
            if brand and model:
                return f"{brand} {model}"
            if model:
                return model
            if brand:
                return brand
            # Fallback: parse from fingerprint (format: brand/product/device:version/...)
            fp_match = re.search(r'name="fingerprint"[^>]*>([^<]+)<', xml_text)
            if fp_match:
                fp = fp_match.group(1)
                parts = fp.split("/")
                if len(parts) >= 2:
                    return f"{parts[0]} {parts[1]}"
        except Exception:
            pass
        return ""
    
    def _mc_change_device(self, brand_filter=None, open_app_first=False):
        """
        Change device info via MaxChange broadcast intent.
        Matches C# ChangeDevice(bool_2).
        Returns True if device identity changed successfully.
        """
        import random
        MAXCHANGE_PKG = "com.minsoftware.maxchanger"
        
        # Clear data and grant permissions
        self._adb_shell(f"pm clear {MAXCHANGE_PKG}")
        self._mc_grant_permissions()
        
        # Get old device fingerprint for comparison
        old_name = self._mc_get_device_name()
        self.log(f"[*] Old device: {old_name[:60] if old_name else '(empty)'}")
        
        start = time.time()
        app_opened = False
        
        if open_app_first:
            app_opened = True
            self._mc_open()
        
        attempt = 1
        while time.time() - start < 300:  # 300 seconds max, matches C#
            if attempt > 1 and not app_opened:
                app_opened = True
                self._mc_open()
            
            # Build broadcast command
            cmd = 'am broadcast -a com.minsoftware.maxchanger.CHANGE -n com.minsoftware.maxchanger/.AdbCaller'
            
            # Support brand specification
            if brand_filter and brand_filter != "Random":
                # Pick a random brand from pipe-separated list
                brands = [b.strip() for b in brand_filter.split("|") if b.strip()]
                if brands:
                    chosen_brand = random.choice(brands)
                    cmd = f'am broadcast -a com.minsoftware.maxchanger.CHANGE --es "brand" "{chosen_brand}" -n com.minsoftware.maxchanger/.AdbCaller'
                    self.log(f"[*] Using brand: {chosen_brand}")
            
            self.log(f"[*] Attempt {attempt}: Broadcasting change command...")
            result = self._adb_shell(cmd)
            broadcast_ok = "Broadcast completed" in result
            self.log(f"[*] Attempt {attempt}: Broadcast {'OK' if broadcast_ok else 'FAILED'}")
            
            if broadcast_ok:
                time.sleep(2)
                new_name = self._mc_get_device_name(timeout_sec=10)
                self.log(f"[*] Attempt {attempt}: New device: {new_name[:60] if new_name else '(empty)'}")
                if new_name and new_name != old_name:
                    self.log(f"[+] Device identity changed successfully!")
                    return True
            
            attempt += 1
            if self.stop_flag:
                break
        
        self.log("[!] ChangeDevice timed out after 300s")
        return False
    
    def _mc_push_file_info(self, profile_name):
        """
        Push a .tar.gz profile to MaxChange data directory via su.
        Matches C# PushFileInfo(maxchange_restore).
        Returns True on success.
        """
        if not profile_name:
            return False
        
        MAXCHANGE_PKG = "com.minsoftware.maxchanger"
        base_dir = os.path.dirname(os.path.abspath(__file__))
        maxchanger_dir = os.path.join(base_dir, "maxchanger")
        local_file = os.path.join(maxchanger_dir, f"{profile_name}.tar.gz")
        
        if not os.path.exists(local_file):
            self.log(f"[!] Profile file not found: {profile_name}.tar.gz")
            return False
        
        # Clear MaxChange data and grant permissions
        self._adb_shell(f"pm clear {MAXCHANGE_PKG}")
        self._mc_grant_permissions()
        
        tar_filename = f"{profile_name}.tar.gz"
        mc_data = f"/data/data/{MAXCHANGE_PKG}"
        
        for i in range(10):
            self.log(f"[*] PushFileInfo attempt {i + 1}/10...")
            
            # Push .tar.gz to /sdcard
            if not self._adb_push(local_file, f"/sdcard/{tar_filename}"):
                self.log(f"[!] Attempt {i + 1}: Push failed")
                time.sleep(2)
                continue
            
            # Copy to MaxChange data dir via su
            self._adb_shell(f'su -c "cp /sdcard/{tar_filename} {mc_data}/{tar_filename}"')
            
            # Extract tar.gz inside the data dir
            self._adb_shell(f'su -c "tar -xzvf {mc_data}/{tar_filename} -C {mc_data}"')
            
            # Get the owner:group of the MaxChange data directory
            owner_group = self._adb_shell(
                'su -c "ls -l /data/data | grep com.minsoftware.maxchanger | awk \'{print $3\":\"$4}\'"'
            ).strip()
            
            has_owner = owner_group != ""
            
            # chown the entire data directory to the correct owner
            if has_owner:
                self._adb_shell(f'su -c "chown -R {owner_group} {mc_data}"')
            
            # Clean up /sdcard copy
            self._adb_shell(f'su -c "rm -r /sdcard/{tar_filename}"')
            
            if not has_owner:
                self.log(f"[!] Attempt {i + 1}: Could not determine owner, retrying...")
                time.sleep(2)
                continue
            
            self.log(f"[+] PushFileInfo success (owner={owner_group})")
            return True
        
        self.log("[!] PushFileInfo failed after 10 attempts")
        return False
    
    def _mc_backup_device(self, profile_name):
        """
        Backup MaxChange shared_prefs to a .tar.gz file and pull to PC.
        Matches C# BackupdataDevice(string_7).
        Returns True on success.
        """
        if not profile_name:
            return False
        
        MAXCHANGE_PKG = "com.minsoftware.maxchanger"
        base_dir = os.path.dirname(os.path.abspath(__file__))
        device_dir = os.path.join(base_dir, "device")
        os.makedirs(device_dir, exist_ok=True)
        local_file = os.path.join(device_dir, f"{profile_name}.tar.gz")
        mc_data = f"/data/data/{MAXCHANGE_PKG}"
        
        # Delete existing backup if present
        if os.path.exists(local_file):
            os.remove(local_file)
        
        # Stop MaxChange app
        self._adb_shell(f"am force-stop {MAXCHANGE_PKG}")
        
        for i in range(10):
            if self.stop_flag:
                break
            
            self.log(f"[*] BackupDevice attempt {i + 1}/10...")
            
            # Create tar.gz of shared_prefs
            self._adb_shell(f'su -c "tar -czvf {mc_data}/device.tar.gz -C {mc_data} shared_prefs"')
            
            # Copy to sdcard
            self._adb_shell(f'su -c "cp {mc_data}/device.tar.gz /sdcard/device.tar.gz"')
            
            # Pull to PC
            if self._adb_pull("/sdcard/device.tar.gz", local_file):
                # Clean up device
                self._adb_shell(f'su -c "rm -rf {mc_data}/*.tar.gz"')
                self._adb_shell('su -c "rm -rf /sdcard/*.tar.gz"')
                
                self.log(f"[+] Backup saved: {profile_name}.tar.gz")
                return True
            
            self.log(f"[!] Attempt {i + 1}: Pull failed, retrying...")
            time.sleep(3)
        
        self.log("[!] BackupDevice failed after 10 attempts")
        return False
    
    def _mc_change_info(self, profile_name, brand_filter=None):
        """
        Full device change flow: try PushFileInfo first, fallback to ChangeDevice.
        Matches C# ChangeInfo(string_7).
        Returns True on success.
        """
        self.log("[*] Changing device info...")
        success = False
        
        # Try 1: Push saved profile via su (PushFileInfo)
        if profile_name and self._mc_push_file_info(profile_name):
            # Verify the push worked by reading device name
            name = self._mc_get_device_name(timeout_sec=10)
            if name:
                success = True
                self.log(f"[+] PushFileInfo verified: {name[:60]}")
        
        # Try 2: Fallback to broadcast-based ChangeDevice
        if not success:
            self.log("[*] PushFileInfo failed, falling back to ChangeDevice...")
            if self._mc_change_device(brand_filter):
                success = True
                # Backup the new device profile for future use
                if profile_name:
                    self._mc_backup_device(profile_name)
        
        return success
    
    def apply_maxchange_spoofing(self, brand_filter=None):
        """
        Main entry point for MaxChange device spoofing (Professional Implementation).
        Matches the full C# Device.cs workflow:
          1. Ensure MaxChange is installed
          2. If profiles exist in maxchanger/ → use ChangeInfo (PushFileInfo + fallback)
          3. If no profiles → use ChangeDevice (broadcast intent)
          4. Report result
        Returns the fake device model string or empty string on failure.
        """
        import random
        MAXCHANGE_PKG = "com.minsoftware.maxchanger"
        base_dir = os.path.dirname(os.path.abspath(__file__))
        maxchanger_dir = os.path.join(base_dir, "maxchanger")
        
        try:
            # Step 1: Ensure MaxChange is installed
            check = self._adb_shell(f"pm list packages {MAXCHANGE_PKG}")
            if MAXCHANGE_PKG not in check:
                self.log("[*] MaxChange not installed, installing...")
                # Look for MaxChange APK
                apk_path = None
                for name in ["maxchange.apk", "maxchangev2.apk", "MaxChange.apk"]:
                    p = os.path.join(base_dir, "app", name)
                    if os.path.exists(p):
                        apk_path = p
                        break
                
                if apk_path:
                    # Install via ADB
                    adb_path = "C:\\Users\\KLS COMPUTER\\Desktop\\FRT\\platform-tools\\adb.exe"
                    install_cmd = f'"{adb_path}" -s {self.device_name} install -r "{apk_path}"'
                    subprocess.run(install_cmd, shell=True, capture_output=True, timeout=60)
                    self.log(f"[+] Installed MaxChange from {os.path.basename(apk_path)}")
                    time.sleep(2)
                else:
                    self.log("[!] MaxChange APK not found in app/ folder!")
                    return ""
            
            # Step 2: Choose profile and change strategy
            profile_name = None
            if os.path.exists(maxchanger_dir):
                tar_files = [f for f in os.listdir(maxchanger_dir) if f.endswith(".tar.gz")]
                if tar_files:
                    chosen_file = random.choice(tar_files)
                    # Extract profile name from filename (e.g., "123.tar.gz" -> "123")
                    profile_name = chosen_file.replace(".tar.gz", "")
                    self.log(f"[*] Selected profile: {profile_name}")
            
            # Step 3: Execute device change
            success = False
            if profile_name:
                # MaxChanger PushFile mode — PushFileInfo → fallback ChangeDevice → Backup
                self.log(f"[*] Using ChangeInfo with profile: {profile_name}")
                success = self._mc_change_info(profile_name, brand_filter)
            else:
                # No profiles available — use ChangeDevice (broadcast only)
                self.log("[*] No profiles in maxchanger/, using ChangeDevice...")
                success = self._mc_change_device(brand_filter)
                # If succeeded and we want to save the new profile for later
                if success:
                    os.makedirs(maxchanger_dir, exist_ok=True)
                    ts = int(time.time())
                    self._mc_backup_device(str(ts))
            
            # Step 4: Report result
            if success:
                fake_model = self._mc_get_model_from_xml()
                fake_name = self._mc_get_device_name()
                if not fake_model:
                    fake_model = self._adb_shell("getprop ro.product.model").strip()
                self.log(f"[✅] Fake device success — Model: {fake_model}, ID: {fake_name[:50] if fake_name else 'N/A'}")
                return fake_model
            else:
                self.log("[!] Fake device failed after all attempts")
                return ""
            
        except Exception as e:
            self.log(f"[!] MaxChange error: {e}")
            import traceback
            self.log(f"[!] Traceback: {traceback.format_exc()}")
            return ""
    
    # ═══════════════════════════════════════════════════════════════════════
    # End MaxChange Integration
    # ═══════════════════════════════════════════════════════════════════════
    
    def _scroll_to_element(self, content_desc):
        """Scroll to element using UiScrollable."""
        try:
            self.driver.find_element(
                AppiumBy.ANDROID_UIAUTOMATOR,
                f'new UiScrollable(new UiSelector().scrollable(true)).scrollIntoView(new UiSelector().descriptionContains("{content_desc}"))'
            )
            return True
        except:
            return False
    
    def _find_and_click(self, locators: list, description: str = "", timeout: int = 8):
        """Find and click element with improved waiting and detection."""
        if self.stop_flag:
            return False
        if description:
            self.log(f"[*] {description}")
        
        # Check if session is alive
        if not self._check_session_alive():
            self.log("[!] Appium session is dead - cannot continue")
            return False
        
        # Temporarily reduce implicit wait for faster searching
        original_wait = 3
        self.driver.implicitly_wait(0.5)  # Very quick search
        
        start_time = time.time()
        found = False
        last_error = None
        
        while time.time() - start_time < timeout and not found:
            for by, value in locators:
                try:
                    element = self.driver.find_element(by=by, value=value)
                    
                    # Check if element is displayed
                    if element.is_displayed():
                        # For text-based elements (TextView, Button), click immediately
                        # For other elements, wait for stability
                        try:
                            element_class = element.get_attribute('className') or ''
                            if 'TextView' in element_class or 'Button' in element_class:
                                # Click immediately for text elements
                                element.click()
                            else:
                                # Wait for stability for other elements
                                time.sleep(0.2)
                                if element.is_enabled():
                                    element.click()
                        except:
                            # If we can't get className, just try clicking
                            element.click()
                        
                        found = True
                        
                        # Use configurable delay
                        delay = self.action_delay
                        if self.safety_mode:
                            delay *= 1.5  # Add 50% more delay in safety mode
                        time.sleep(delay)
                        
                        # Restore implicit wait
                        self.driver.implicitly_wait(original_wait)
                        return True
                except Exception as e:
                    error_msg = str(e)
                    # Check for session death
                    if "cannot be proxied" in error_msg or "instrumentation" in error_msg:
                        self.log("[!] Appium session lost - instrumentation crashed")
                        self.driver.implicitly_wait(original_wait)
                        return False
                    last_error = error_msg
                    continue
            
            if not found:
                time.sleep(0.5)  # Brief pause before retry
        
        # If not found after timeout, try scrolling
        if not found and locators and locators[0][0] == AppiumBy.ACCESSIBILITY_ID:
            content_desc = locators[0][1]
            self.log(f"[*] Trying to scroll to element: {content_desc}")
            if self._scroll_to_element(content_desc):
                # Try clicking again after scroll
                for by, value in locators:
                    try:
                        element = self.driver.find_element(by=by, value=value)
                        if element.is_displayed():
                            element.click()
                            found = True
                            
                            delay = self.action_delay
                            if self.safety_mode:
                                delay *= 1.5
                            time.sleep(delay)
                            
                            # Restore implicit wait
                            self.driver.implicitly_wait(original_wait)
                            return True
                    except:
                        continue
        
        # Restore implicit wait
        self.driver.implicitly_wait(original_wait)
        
        if not found:
            self.log(f"[!] Could not find: {description}")
            if last_error and len(last_error) < 200:
                self.log(f"[!] Last error: {last_error}")
        return found
    
    def _tap_coordinates(self, x_percent: float, y_percent: float, description: str = ""):
        """
        Tap at screen coordinates using percentage-based positioning.
        
        Args:
            x_percent: X position as percentage of screen width (0.0 to 1.0)
            y_percent: Y position as percentage of screen height (0.0 to 1.0)
            description: Description of what's being clicked
        
        Returns:
            bool: True if tap succeeded, False otherwise
        """
        if self.stop_flag:
            return False
        
        if description:
            self.log(f"[*] {description}")
        
        try:
            # Get screen size
            screen_size = self.driver.get_window_size()
            width = screen_size['width']
            height = screen_size['height']
            
            # Calculate actual coordinates
            x = int(width * x_percent)
            y = int(height * y_percent)
            
            self.log(f"[*] Tapping at ({x}, {y}) - {int(x_percent*100)}% width, {int(y_percent*100)}% height")
            self.driver.tap([(x, y)])
            
            # Use configurable delay
            delay = self.action_delay
            if self.safety_mode:
                delay *= 1.5
            time.sleep(delay)
            
            return True
        except Exception as e:
            self.log(f"[!] Coordinate tap failed: {e}")
            return False

    def _find_and_type(self, locators: list, text: str, description: str = "", timeout: int = 8):
        """Find and type into element with improved waiting and detection."""
        if self.stop_flag:
            return False
        if description:
            self.log(f"[*] {description}")
        
        # Check if session is alive
        if not self._check_session_alive():
            self.log("[!] Appium session is dead - cannot continue")
            return False
        
        # Temporarily reduce implicit wait for faster searching
        original_wait = 3
        self.driver.implicitly_wait(0.5)  # Very quick search
        
        start_time = time.time()
        found = False
        last_error = None
        
        while time.time() - start_time < timeout and not found:
            for by, value in locators:
                try:
                    element = self.driver.find_element(by=by, value=value)
                    
                    # Check if element is displayed
                    if element.is_displayed():
                        # Click first to focus
                        try:
                            element.click()
                            time.sleep(0.3)
                        except:
                            pass
                        
                        # Clear and type
                        try:
                            element.clear()
                            time.sleep(0.2)
                        except:
                            pass
                        
                        element.send_keys(text)
                        found = True
                        
                        # Use configurable delay
                        delay = self.action_delay * 0.5  # Shorter delay for typing
                        if self.safety_mode:
                            delay *= 1.3  # Add 30% more delay in safety mode
                        time.sleep(delay)
                        
                        # Restore implicit wait
                        self.driver.implicitly_wait(original_wait)
                        return True
                except Exception as e:
                    error_msg = str(e)
                    # Check for session death
                    if "cannot be proxied" in error_msg or "instrumentation" in error_msg:
                        self.log("[!] Appium session lost - instrumentation crashed")
                        self.driver.implicitly_wait(original_wait)
                        return False
                    last_error = error_msg
                    continue
            
            if not found:
                time.sleep(0.5)  # Brief pause before retry
        
        # Restore implicit wait
        self.driver.implicitly_wait(original_wait)
        
        if not found:
            self.log(f"[!] Could not find input: {description}")
            if last_error and len(last_error) < 200:
                self.log(f"[!] Last error: {last_error}")
        return found

    def _click_first_radio_button(self):
        try:
            radio = self.driver.find_element(AppiumBy.CLASS_NAME, "android.widget.RadioButton")
            radio.click()
            time.sleep(1)
            return True
        except:
            return False

    def _handle_permission_dialog(self):
        """Handle Android permission dialogs by clicking Deny."""
        try:
            # Save current implicit wait
            original_wait = 3
            self.driver.implicitly_wait(0.5)
            
            # Try to find and click "Deny" button
            deny_locators = [
                (AppiumBy.XPATH, "//*[@text='Deny']"),
                (AppiumBy.XPATH, "//*[@text='DENY']"),
                (AppiumBy.XPATH, "//android.widget.Button[@text='Deny']"),
                (AppiumBy.XPATH, "//*[@text='Don't allow']"),
                (AppiumBy.XPATH, "//*[@text=\"Don't allow\"]"),
                (AppiumBy.ID, "com.android.permissioncontroller:id/permission_deny_button"),
                (AppiumBy.ID, "com.android.packageinstaller:id/permission_deny_button"),
            ]
            
            start_time = time.time()
            timeout = 3  # 3 seconds to find permission dialog
            
            while time.time() - start_time < timeout:
                for by, value in deny_locators:
                    try:
                        element = self.driver.find_element(by=by, value=value)
                        if element.is_displayed():
                            element.click()
                            self.log("[+] Clicked Deny on permission dialog")
                            time.sleep(1)
                            self.driver.implicitly_wait(original_wait)
                            return True
                    except:
                        continue
                time.sleep(0.3)
            
            # Restore implicit wait
            self.driver.implicitly_wait(original_wait)
        except:
            pass
        return False
    
    def _try_extract_uid(self):
        """Try to extract Facebook UID from app data, cookies, or page source using aggressive methods."""
        import re
        import subprocess
        
        try:
            self.log("[*] Attempting to extract UID using AGGRESSIVE methods...")
            
            # Get the package name based on selected app
            package_name = self._get_package_name()
            self.log(f"[*] Using package: {package_name}")
            
            # Method 1: Logcat monitoring (Facebook often logs UID)
            try:
                self.log("[*] Method 1: Monitoring logcat for UID...")
                result = safe_subprocess_run(
                    ['platform-tools\\adb.exe', '-s', self.device_name, 'logcat', '-d', '-s', 'Facebook:V'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                if result.returncode == 0 and result.stdout:
                    # Look for UID patterns in logs
                    uid_matches = re.findall(r'\b(100\d{12})\b', result.stdout)
                    if uid_matches:
                        # Get most common UID (likely the real one)
                        from collections import Counter
                        uid = Counter(uid_matches).most_common(1)[0][0]
                        self.log(f"[+] Found UID in logcat: {uid}")
                        return uid
                
                self.log("[!] No UID found in logcat")
            except Exception as e:
                self.log(f"[!] Could not check logcat: {e}")
            
            # Method 2: Deep file system search (all files in app directory)
            try:
                self.log("[*] Method 2: Deep file system search...")
                result = safe_subprocess_run(
                    ['platform-tools\\adb.exe', '-s', self.device_name, 'shell',
                     f'find /data/data/{package_name}/ -type f -exec grep -l "100[0-9]\\{{12\\}}" {{}} \\; 2>/dev/null | head -10'],
                    capture_output=True,
                    text=True,
                    timeout=15
                )
                
                if result.returncode == 0 and result.stdout:
                    files_with_uid = result.stdout.strip().split('\n')
                    self.log(f"[*] Found {len(files_with_uid)} files containing potential UID")
                    
                    # Read first file that contains UID
                    for file_path in files_with_uid[:3]:  # Check first 3 files
                        try:
                            result = safe_subprocess_run(
                                ['platform-tools\\adb.exe', '-s', self.device_name, 'shell', f'cat {file_path}'],
                                capture_output=True,
                                text=True,
                                timeout=5
                            )
                            if result.returncode == 0:
                                uid_matches = re.findall(r'\b(100\d{12})\b', result.stdout)
                                if uid_matches:
                                    uid = uid_matches[0]
                                    self.log(f"[+] Found UID in {file_path}: {uid}")
                                    return uid
                        except:
                            continue
                
                self.log("[!] No UID found in deep file search")
            except Exception as e:
                self.log(f"[!] Could not perform deep file search: {e}")
            
            # Method 3: Check app's shared preferences (most reliable)
            try:
                self.log("[*] Method 3: Checking shared preferences...")
                
                # List all shared_prefs files
                result = safe_subprocess_run(
                    ['platform-tools\\adb.exe', '-s', self.device_name, 'shell', 
                     f'ls /data/data/{package_name}/shared_prefs/'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                if result.returncode == 0:
                    self.log(f"[*] Found shared_prefs files: {result.stdout.strip()}")
                    
                    # Try to read all XML files
                    result = safe_subprocess_run(
                        ['platform-tools\\adb.exe', '-s', self.device_name, 'shell', 
                         f'cat /data/data/{package_name}/shared_prefs/*.xml'],
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    
                    if result.returncode == 0 and result.stdout:
                        prefs_data = result.stdout
                        
                        # Look for various UID patterns
                        patterns = [
                            r'<string name="[^"]*uid[^"]*">(\d{15})</string>',
                            r'<string name="[^"]*user_id[^"]*">(\d{15})</string>',
                            r'<string name="[^"]*account_id[^"]*">(\d{15})</string>',
                            r'<string name="[^"]*fb_uid[^"]*">(\d{15})</string>',
                            r'<string name="[^"]*fbid[^"]*">(\d{15})</string>',
                            r'<long name="[^"]*uid[^"]*" value="(\d{15})"',
                            r'<long name="[^"]*user_id[^"]*" value="(\d{15})"',
                            r'"uid":"(\d{15})"',
                            r'"user_id":"(\d{15})"',
                            r'"id":"(\d{15})"',
                            r'\b(100\d{12})\b',  # Any 15-digit starting with 100
                        ]
                        
                        for pattern in patterns:
                            matches = re.findall(pattern, prefs_data)
                            if matches:
                                uid = matches[0]
                                self.log(f"[+] Found UID in shared preferences: {uid}")
                                return uid
                        
                        self.log("[!] No UID found in shared preferences")
                        
            except Exception as e:
                self.log(f"[!] Could not check shared preferences: {e}")
            
            # Method 4: Check app's databases with multiple queries
            try:
                self.log("[*] Method 4: Checking databases...")
                
                # List database files
                result = safe_subprocess_run(
                    ['platform-tools\\adb.exe', '-s', self.device_name, 'shell',
                     f'ls /data/data/{package_name}/databases/'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                if result.returncode == 0:
                    self.log(f"[*] Found database files: {result.stdout.strip()}")
                    
                    # Get list of database files
                    db_files = result.stdout.strip().split('\n')
                    
                    for db_file in db_files:
                        if not db_file or db_file.endswith('-journal') or db_file.endswith('-wal'):
                            continue
                        
                        try:
                            # Try to dump entire database
                            result = safe_subprocess_run(
                                ['platform-tools\\adb.exe', '-s', self.device_name, 'shell',
                                 f'sqlite3 /data/data/{package_name}/databases/{db_file} ".dump" 2>/dev/null'],
                                capture_output=True,
                                text=True,
                                timeout=10
                            )
                            
                            if result.returncode == 0 and result.stdout:
                                uid_matches = re.findall(r'\b(100\d{12})\b', result.stdout)
                                if uid_matches:
                                    uid = uid_matches[0]
                                    self.log(f"[+] Found UID in database {db_file}: {uid}")
                                    return uid
                        except:
                            continue
                    
                    self.log("[!] No UID found in databases")
                    
            except Exception as e:
                self.log(f"[!] Could not check databases: {e}")
            
            # Method 5: Check page source and WebView content
            try:
                self.log("[*] Method 5: Checking page source...")
                page_source = self.driver.page_source
                
                patterns = [
                    r'profile\.php\?id=(\d{15})',
                    r'"user_id":"(\d{15})"',
                    r'"uid":"(\d{15})"',
                    r'"id":"(\d{15})"',
                    r'c_user[=:](\d{15})',
                    r'account_id[=:](\d{15})',
                    r'fb_uid[=:](\d{15})',
                    r'\b(100\d{12})\b',
                ]
                
                for pattern in patterns:
                    matches = re.findall(pattern, page_source)
                    if matches:
                        uid = matches[0]
                        self.log(f"[+] Found UID in page source: {uid}")
                        return uid
                
                self.log("[!] No UID found in page source")
                
            except Exception as e:
                self.log(f"[!] Could not extract from page source: {e}")
            
            # Method 6: Check cookies
            try:
                self.log("[*] Method 6: Checking cookies...")
                cookies = self.driver.get_cookies()
                for cookie in cookies:
                    if cookie.get('name') in ['c_user', 'uid', 'user_id', 'xs', 'fbid']:
                        uid = cookie.get('value')
                        if uid and re.match(r'^\d{15}$', uid):
                            self.log(f"[+] Found UID in cookies: {uid}")
                            return uid
                
                self.log("[!] No UID found in cookies")
                
            except Exception as e:
                self.log(f"[!] Could not extract from cookies: {e}")
            
            # Method 7: Check app's cache files
            try:
                self.log("[*] Method 7: Checking cache files...")
                result = safe_subprocess_run(
                    ['platform-tools\\adb.exe', '-s', self.device_name, 'shell',
                     f'grep -r "100[0-9]\\{{12\\}}" /data/data/{package_name}/cache/ 2>/dev/null | head -5'],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if result.returncode == 0 and result.stdout:
                    uid_matches = re.findall(r'\b(100\d{12})\b', result.stdout)
                    if uid_matches:
                        uid = uid_matches[0]
                        self.log(f"[+] Found UID in cache: {uid}")
                        return uid
                
                self.log("[!] No UID found in cache")
                
            except Exception as e:
                self.log(f"[!] Could not check cache: {e}")
            
            # Method 8: Check app's files directory
            try:
                self.log("[*] Method 8: Checking files directory...")
                result = safe_subprocess_run(
                    ['platform-tools\\adb.exe', '-s', self.device_name, 'shell',
                     f'grep -r "100[0-9]\\{{12\\}}" /data/data/{package_name}/files/ 2>/dev/null | head -5'],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if result.returncode == 0 and result.stdout:
                    uid_matches = re.findall(r'\b(100\d{12})\b', result.stdout)
                    if uid_matches:
                        uid = uid_matches[0]
                        self.log(f"[+] Found UID in files: {uid}")
                        return uid
                
                self.log("[!] No UID found in files directory")
                
            except Exception as e:
                self.log(f"[!] Could not check files: {e}")
            
            self.log(f"[!] UID extraction failed after 8 aggressive methods")
            self.log(f"[*] {package_name} does not store UID until after SMS verification and login")
            self.log("[*] Note: UID will be available after completing SMS verification and logging in")
            return ""
            
        except Exception as e:
            self.log(f"[!] Error extracting UID: {e}")
            import traceback
            self.log(f"[!] Traceback: {traceback.format_exc()}")
            return ""
    
    def _get_device_info(self):
        """Get comprehensive device information."""
        import subprocess
        
        try:
            device_info = {
                "device_id": self.device_name,
                "device_name_short": self.device_name[-8:] if self.device_name else "unknown"
            }
            
            # Check if device changer is enabled and fake info is available
            if hasattr(self, 'fake_device_info') and self.fake_device_info:
                self.log("[🔄] Using Device Changer - Applying fake device info")
                
                # Use fake device info instead of real device info
                device_info.update(self.fake_device_info)
                
                # Keep original device ID for ADB communication
                device_info["original_device_id"] = self.device_name
                device_info["device_id"] = self.device_name  # Keep for ADB
                device_info["device_name_short"] = self.device_name[-8:]
                
                self.log(f"[🔄] Fake device: {device_info.get('manufacturer', 'Unknown')} {device_info.get('model', 'Unknown')}")
                
                return device_info
            
            # Original device info gathering (when device changer is disabled)
            # Get detailed device info from driver capabilities
            if self.driver:
                try:
                    caps = self.driver.capabilities
                    
                    device_info.update({
                        "manufacturer": caps.get('deviceManufacturer', 'Unknown'),
                        "model": caps.get('deviceModel', 'Unknown'),
                        "android_version": caps.get('platformVersion', 'Unknown'),
                        "device_screen_size": caps.get('deviceScreenSize', 'Unknown'),
                        "device_screen_density": caps.get('deviceScreenDensity', 'Unknown'),
                        "device_udid": caps.get('deviceUDID', self.device_name),
                        "platform_name": caps.get('platformName', 'Android'),
                        "automation_name": caps.get('automationName', 'UiAutomator2'),
                    })
                except Exception as e:
                    self.log(f"[!] Could not get driver capabilities: {e}")
            
            # Get additional device info via ADB
            try:
                # Get device brand
                result = safe_subprocess_run(
                    ['platform-tools\\adb.exe', '-s', self.device_name, 'shell', 'getprop ro.product.brand'],
                    capture_output=True,
                    text=True,
                    timeout=3
                )
                if result.returncode == 0:
                    device_info['brand'] = result.stdout.strip()
                
                # Get device name
                result = safe_subprocess_run(
                    ['platform-tools\\adb.exe', '-s', self.device_name, 'shell', 'getprop ro.product.name'],
                    capture_output=True,
                    text=True,
                    timeout=3
                )
                if result.returncode == 0:
                    device_info['device_name'] = result.stdout.strip()
                
                # Get Android SDK version
                result = safe_subprocess_run(
                    ['platform-tools\\adb.exe', '-s', self.device_name, 'shell', 'getprop ro.build.version.sdk'],
                    capture_output=True,
                    text=True,
                    timeout=3
                )
                if result.returncode == 0:
                    device_info['android_sdk'] = result.stdout.strip()
                
                # Get device fingerprint
                result = safe_subprocess_run(
                    ['platform-tools\\adb.exe', '-s', self.device_name, 'shell', 'getprop ro.build.fingerprint'],
                    capture_output=True,
                    text=True,
                    timeout=3
                )
                if result.returncode == 0:
                    device_info['build_fingerprint'] = result.stdout.strip()
                
                # Get device serial
                result = safe_subprocess_run(
                    ['platform-tools\\adb.exe', '-s', self.device_name, 'shell', 'getprop ro.serialno'],
                    capture_output=True,
                    text=True,
                    timeout=3
                )
                if result.returncode == 0:
                    serial = result.stdout.strip()
                    if serial and serial != 'unknown':
                        device_info['serial_number'] = serial
                
                # Get CPU architecture
                result = safe_subprocess_run(
                    ['platform-tools\\adb.exe', '-s', self.device_name, 'shell', 'getprop ro.product.cpu.abi'],
                    capture_output=True,
                    text=True,
                    timeout=3
                )
                if result.returncode == 0:
                    device_info['cpu_architecture'] = result.stdout.strip()
                
                # Get total RAM
                result = safe_subprocess_run(
                    ['platform-tools\\adb.exe', '-s', self.device_name, 'shell', 'cat /proc/meminfo | grep MemTotal'],
                    capture_output=True,
                    text=True,
                    timeout=3
                )
                if result.returncode == 0:
                    import re
                    match = re.search(r'(\d+)', result.stdout)
                    if match:
                        ram_kb = int(match.group(1))
                        ram_mb = ram_kb // 1024
                        device_info['total_ram_mb'] = ram_mb
                
            except Exception as e:
                self.log(f"[!] Could not get additional device info via ADB: {e}")
            
            return device_info
            
        except Exception as e:
            self.log(f"[!] Error getting device info: {e}")
            return {
                "device_id": self.device_name,
                "device_name_short": self.device_name[-8:] if self.device_name else "unknown"
            }
    
    def _get_package_name(self):
        """Extract package name from APK file path or app selection."""
        try:
            # First check the stored app selection
            if hasattr(self, 'app_selection'):
                if self.app_selection == "Facebook Lite":
                    return "com.facebook.lite"
                elif self.app_selection == "Facebook (Original)":
                    return "com.facebook.katana"
                elif self.app_selection == "Messenger":
                    return "com.facebook.orca"
            
            # Try to extract from filename
            apk_filename = os.path.basename(self.apk_path)
            
            # Common pattern: com.package.name_version.apk
            if apk_filename.startswith('com.'):
                # Extract package name before version number or underscore
                import re
                match = re.match(r'(com\.[a-z0-9.]+)', apk_filename)
                if match:
                    return match.group(1)
            
            # Fallback: Try to get from driver's current package
            try:
                if self.driver:
                    current_package = self.driver.current_package
                    if current_package:
                        return current_package
            except:
                pass
            
            # Default fallback
            return "com.facebook.lite"
            
        except Exception as e:
            return "com.facebook.lite"
    
    def _backup_account_info(self, first_name, last_name, email, password, birthday, gender, phone, use_phone, uid=""):
        """Backup account information to a file."""
        import json
        from datetime import datetime
        import re
        
        try:
            self.log("[*] Starting account backup...")
            
            # Create account_backup folder if it doesn't exist
            backup_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "account_backup")
            os.makedirs(backup_folder, exist_ok=True)
            
            # Grant permissions to backup folder
            try:
                subprocess.run(['icacls', backup_folder, '/grant', 'Everyone:F', '/T'], 
                             capture_output=True, timeout=3, creationflags=subprocess.CREATE_NO_WINDOW)
            except:
                pass  # Ignore permission errors
            
            # Get detailed device information
            device_info = self._get_device_info()
            
            # Extract cookies and session data
            cookies_data = self._extract_cookies()
            
            # Create account data
            account_data = {
                "account_uid": uid if uid else "",  # Use extracted UID or empty
                "first_name": first_name,
                "last_name": last_name,
                "full_name": f"{first_name} {last_name}",
                "email": email,
                "password": password,
                "birthday": birthday,
                "gender": gender,
                "phone": phone if use_phone else "",
                "signup_method": "phone" if use_phone else "email",
                "cookies": cookies_data,  # Add cookies data
                "device_info": device_info,  # Full device information (includes fake info if device changer enabled)
                "device_changer_used": hasattr(self, 'fake_device_info') and self.fake_device_info is not None,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "status": "pending_sms_verification" if use_phone else "pending_email_verification",
                "apk_path": self.apk_path,  # Full path to APK file
                "apk_package": self._get_package_name(),  # Extract package name from APK
                "notes": f"{'🔄 Device Changer: ON | ' if hasattr(self, 'fake_device_info') and self.fake_device_info else ''}{'UID extracted from app data' if uid else 'UID will be available after SMS verification and login'}"
            }
            
            # Create folder name based on email/phone and timestamp
            # Sanitize identifier to remove special characters
            if use_phone and phone:
                identifier = re.sub(r'[^\w\s-]', '', phone)  # Remove special chars like +
            else:
                identifier = email.split('@')[0] if '@' in email else email
                identifier = re.sub(r'[^\w\s-]', '', identifier)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            folder_name = f"{identifier}_{timestamp}"
            account_folder = os.path.join(backup_folder, folder_name)
            
            # Create account-specific folder
            os.makedirs(account_folder, exist_ok=True)
            self.log(f"[*] Created account folder: {folder_name}")
            
            # Grant permissions to account folder
            try:
                subprocess.run(['icacls', account_folder, '/grant', 'Everyone:F', '/T'], 
                             capture_output=True, timeout=3, creationflags=subprocess.CREATE_NO_WINDOW)
            except:
                pass  # Ignore permission errors
            
            # 1. Create "Acc info" text file with account details
            acc_info_file = os.path.join(account_folder, "Acc info")
            with open(acc_info_file, 'w', encoding='utf-8') as f:
                f.write(f"UID: {uid if uid else 'Pending SMS verification'}\n")
                f.write(f"Name: {first_name} {last_name}\n")
                f.write(f"Email: {email}\n")
                f.write(f"Phone: {phone}\n")
                f.write(f"Password: {password}\n")
                f.write(f"Birthday: {birthday}\n")
                f.write(f"Gender: {gender}\n")
                f.write(f"Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Status: {'Pending SMS verification' if use_phone else 'Pending email verification'}\n")
                f.write(f"Device Changer: {'ON' if hasattr(self, 'fake_device_info') and self.fake_device_info else 'OFF'}\n")
            
            self.log(f"[+] Created Acc info file")
            
            # 2. Create "Device info" folder with tar.gz
            device_info_folder = os.path.join(account_folder, "Device info")
            os.makedirs(device_info_folder, exist_ok=True)
            
            # Create device tar.gz file
            device_tar_file = os.path.join(device_info_folder, f"{identifier}.tar.gz")
            import tarfile
            with tarfile.open(device_tar_file, 'w:gz') as tar:
                # Create a temporary JSON file with device info
                import tempfile
                with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as tmp:
                    json.dump(device_info, tmp, indent=4, ensure_ascii=False)
                    tmp_path = tmp.name
                tar.add(tmp_path, arcname='device_info.json')
                os.unlink(tmp_path)
            
            self.log(f"[+] Created Device info backup")
            
            # 3. Create "Profile info" folder with tar.gz
            profile_info_folder = os.path.join(account_folder, "Profile info")
            os.makedirs(profile_info_folder, exist_ok=True)
            
            # Create profile tar.gz file
            profile_tar_file = os.path.join(profile_info_folder, f"{identifier}.tar.gz")
            with tarfile.open(profile_tar_file, 'w:gz') as tar:
                # Create a temporary JSON file with profile/cookies info
                with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as tmp:
                    profile_data = {
                        "cookies": cookies_data,
                        "account_uid": uid if uid else "",
                        "full_name": f"{first_name} {last_name}",
                        "email": email,
                        "phone": phone,
                        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    json.dump(profile_data, tmp, indent=4, ensure_ascii=False)
                    tmp_path = tmp.name
                tar.add(tmp_path, arcname='profile_info.json')
                os.unlink(tmp_path)
            
            self.log(f"[+] Created Profile info backup")
            
            # Also keep the JSON file for compatibility
            json_file = os.path.join(account_folder, "account_info.json")
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(account_data, f, indent=4, ensure_ascii=False)
            
            self.log(f"[+] Account backed up to: {folder_name}")
            
            # Also create a summary CSV file in the main backup folder
            csv_file = os.path.join(backup_folder, "accounts_summary.csv")
            file_exists = os.path.exists(csv_file)
            
            with open(csv_file, 'a', encoding='utf-8') as f:
                if not file_exists:
                    # Write header
                    f.write("Created At,Name,Email,Phone,Password,Birthday,Gender,Device ID,Device Model,Status,Folder\n")
                
                # Write account data
                device_model = device_info.get('model', 'Unknown')
                device_id_short = device_info.get('device_name_short', 'unknown')
                f.write(f'"{account_data["created_at"]}","{account_data["full_name"]}","{account_data["email"]}","{account_data["phone"]}","{account_data["password"]}","{account_data["birthday"]}","{account_data["gender"]}","{device_id_short}","{device_model}","{account_data["status"]}","{folder_name}"\n')
            
            self.log(f"[+] Account added to summary: {csv_file}")
            
            # Reload dashboard statistics to reflect new account
            self.load_dashboard_statistics()
            
        except Exception as e:
            self.log(f"[!] Failed to backup account: {e}")
            import traceback
            self.log(f"[!] Traceback: {traceback.format_exc()}")
    
    def _extract_cookies(self):
        """Extract all cookies and session tokens from the app."""
        try:
            self.log("[*] Extracting cookies and session data...")
            
            cookies_data = {
                "browser_cookies": [],
                "app_cookies": []
            }
            
            # Method 1: Get cookies from Appium driver
            try:
                driver_cookies = self.driver.get_cookies()
                for cookie in driver_cookies:
                    cookies_data["browser_cookies"].append({
                        "name": cookie.get('name'),
                        "value": cookie.get('value'),
                        "domain": cookie.get('domain'),
                        "path": cookie.get('path'),
                        "secure": cookie.get('secure'),
                        "httpOnly": cookie.get('httpOnly')
                    })
                
                if cookies_data["browser_cookies"]:
                    self.log(f"[+] Extracted {len(cookies_data['browser_cookies'])} browser cookies")
            except Exception as e:
                self.log(f"[!] Could not extract browser cookies: {e}")
            
            # Method 2: Extract cookies from app's data directory
            try:
                import subprocess
                package_name = self._get_package_name()
                
                # Check for cookies in app's files
                result = safe_subprocess_run(
                    ['platform-tools\\adb.exe', '-s', self.device_name, 'shell',
                     f'find /data/data/{package_name}/ -name "*cookie*" -o -name "*session*" 2>/dev/null'],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if result.returncode == 0 and result.stdout:
                    cookie_files = result.stdout.strip().split('\n')
                    self.log(f"[*] Found {len(cookie_files)} cookie/session files")
                    
                    for cookie_file in cookie_files[:5]:  # Check first 5 files
                        if cookie_file:
                            cookies_data["app_cookies"].append(cookie_file)
                    
                    if cookies_data["app_cookies"]:
                        self.log(f"[+] Found {len(cookies_data['app_cookies'])} app cookie files")
            except Exception as e:
                self.log(f"[!] Could not extract app cookies: {e}")
            
            return cookies_data
            
        except Exception as e:
            self.log(f"[!] Error extracting cookies: {e}")
            return {"browser_cookies": [], "app_cookies": []}

    def stop(self):
        self.stop_flag = True
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass

    def register(self, first_name: str, last_name: str, email: str, password: str, birthday: str = "15/06/1995", gender: str = "Male", phone: str = "", use_phone: bool = False):
        try:
            self._setup_driver()
            if hasattr(self.log_signal, 'status'):
                self.log_signal.status.emit("Starting...")
            
            # Detect app type from APK path
            is_katana = 'katana' in self.apk_path.lower()
            app_name = "FACEBOOK (KATANA)" if is_katana else "FACEBOOK LITE"
            
            self.log("\n" + "="*50)
            self.log(f"  {app_name} REGISTRATION")
            self.log("="*50)
            
            # Parse birthday
            try:
                day, month, year = birthday.split("/")
                day = int(day)
                month = int(month)
                year = int(year)
            except:
                day, month, year = 15, 6, 1995
            
            # Detect app type
            is_katana = 'katana' in self.apk_path.lower()
            
            # Facebook Katana needs more time to load than Lite
            initial_delay = self.action_delay * 5 if is_katana else self.action_delay * 2.5
            self.log(f"[*] Waiting {initial_delay}s for app to load...")
            time.sleep(initial_delay)
            
            if hasattr(self.log_signal, 'status'):
                self.log_signal.status.emit("Loading...")
            
            # Smart loading detection - only wait if actually loading
            self.log("[*] Checking if app is ready...")
            max_wait = 45 if is_katana else 30  # Facebook Katana needs more time
            wait_count = 0
            
            while wait_count < max_wait:
                try:
                    # Check for actual loading indicators only
                    progress_bars = self.driver.find_elements(AppiumBy.CLASS_NAME, "android.widget.ProgressBar")
                    
                    if len(progress_bars) > 0:
                        # Actually loading - wait
                        self.log(f"[*] Loading in progress... ({wait_count + 1}s)")
                        time.sleep(1)
                        wait_count += 1
                    else:
                        # No loading indicator - check if interactive elements exist
                        try:
                            clickable = self.driver.find_elements(AppiumBy.XPATH, "//*[@clickable='true']")
                            if len(clickable) > 0:
                                # Found interactive elements - app is ready
                                self.log("[+] App is ready")
                                break
                            else:
                                # No interactive elements yet, but no loading bar either
                                # Give it a moment
                                if wait_count < 3:
                                    time.sleep(1)
                                    wait_count += 1
                                else:
                                    # After 3 seconds with no loading bar, assume ready
                                    self.log("[+] App appears ready")
                                    break
                        except:
                            time.sleep(1)
                            wait_count += 1
                except Exception as e:
                    # If we can't check, assume ready after brief wait
                    if wait_count < 2:
                        time.sleep(1)
                        wait_count += 1
                    else:
                        self.log("[+] Proceeding with registration")
                        break
            
            if wait_count >= max_wait:
                self.log("[!] Loading timeout - proceeding anyway")
            
            time.sleep(1)  # Brief delay after ready
            
            # Step 1: Navigate to registration from login screen
            if is_katana:
                self.log("[*] Navigating to registration screen...")
                
                # Try to find and click "Create new account" button using multiple methods
                create_account_found = False
                
                # Method 1: Try XML element search first (most reliable)
                create_locators = [
                    (AppiumBy.XPATH, "//*[@text='Create new account']"),
                    (AppiumBy.XPATH, "//android.widget.Button[@text='Create new account']"),
                    (AppiumBy.XPATH, "//*[contains(@text, 'Create new account')]"),
                    (AppiumBy.XPATH, "//*[contains(@text, 'Create account')]"),
                    (AppiumBy.ACCESSIBILITY_ID, "Create new account"),
                ]
                
                for by, value in create_locators:
                    try:
                        element = self.driver.find_element(by=by, value=value)
                        if element.is_displayed():
                            self.log(f"[+] Found 'Create new account' button via XML")
                            element.click()
                            create_account_found = True
                            time.sleep(3)
                            break
                    except:
                        continue
                
                # Method 2: If XML fails, use coordinate-based clicking
                if not create_account_found:
                    self.log("[*] XML search failed, using coordinate-based clicking...")
                    # Try multiple common positions for "Create new account" button
                    positions = [
                        (0.5, 0.85, "bottom area"),      # Bottom of screen
                        (0.5, 0.88, "very bottom"),      # Very bottom
                        (0.5, 0.55, "middle area"),      # Middle of screen
                    ]
                    
                    for x_pct, y_pct, desc in positions:
                        self.log(f"[*] Trying {desc} position...")
                        if self._tap_coordinates(x_pct, y_pct, f"Tapping {desc}"):
                            time.sleep(3)
                            # Check if we moved to a different screen
                            try:
                                # Look for indicators we're on registration flow
                                self.driver.find_element(AppiumBy.XPATH, "//*[contains(@text, 'Join Facebook')]")
                                self.log(f"[+] Successfully navigated using {desc}")
                                create_account_found = True
                                break
                            except:
                                self.log(f"[!] {desc} didn't work, trying next...")
                                continue
                
                if not create_account_found:
                    raise Exception("Could not find or click 'Create new account' button")
            else:
                # Facebook Lite: Use element search with scrolling
                try:
                    self.log("[*] Scrolling to find Create Account button...")
                    window_size = self.driver.get_window_size()
                    start_x = window_size['width'] // 2
                    start_y = window_size['height'] * 0.8
                    end_y = window_size['height'] * 0.2
                    self.driver.swipe(start_x, start_y, start_x, end_y, 500)
                    time.sleep(1)
                except Exception as e:
                    self.log(f"[!] Scroll failed: {e}")
                
                create_account_locators = [
                    (AppiumBy.XPATH, "//*[@text='Create new account']"),
                    (AppiumBy.XPATH, "//android.widget.Button[@text='Create new account']"),
                    (AppiumBy.XPATH, "//*[contains(@text, 'Create new account')]"),
                    (AppiumBy.ACCESSIBILITY_ID, "Create new account"),
                    (AppiumBy.XPATH, "//android.widget.Button[@content-desc='Create new account']"),
                    (AppiumBy.XPATH, "//*[@content-desc='Create new account']"),
                    (AppiumBy.XPATH, "//*[contains(@content-desc, 'Create new account')]"),
                ]
                
                if not self._find_and_click(create_account_locators, "Clicking 'Create new account'..."):
                    self.log("[!] Could not find Create Account button")
                    raise Exception("Could not find Create Account button")
            
            # Check if session is still alive after clicking
            if not self._check_session_alive():
                self.log("[!] App crashed or session died after clicking Create Account")
                raise Exception("Appium session died - app may have crashed")
            
            if hasattr(self.log_signal, 'status'):
                self.log_signal.status.emit("Running...")
            
            # Wait for page to transition - look for loading to finish
            self.log("[*] Waiting for registration page to load...")
            time.sleep(3)  # Give it time to start loading
            
            # Wait for loading spinner to disappear (max 15 seconds)
            loading_gone = False
            for i in range(15):
                try:
                    # Check if ProgressBar exists
                    self.driver.find_element(AppiumBy.CLASS_NAME, "android.widget.ProgressBar")
                    self.log(f"[*] Still loading... ({i+1}s)")
                    time.sleep(1)
                except:
                    # ProgressBar not found - loading finished
                    loading_gone = True
                    self.log("[+] Loading finished")
                    break
            
            if not loading_gone:
                self.log("[!] Loading took too long, continuing anyway...")
            
            time.sleep(self.action_delay)
            
            # Step 2: Handle "Join Facebook" welcome screen
            self.log("[*] Checking for Join Facebook screen...")
            on_name_page = False
            
            # First check if we're already on name entry page
            try:
                first_name_check = self.driver.find_element(AppiumBy.XPATH, "//*[contains(@content-desc, 'First name')]")
                if first_name_check.is_displayed():
                    self.log("[+] Already on name entry page")
                    on_name_page = True
            except:
                pass
            
            if not on_name_page:
                # We're on "Join Facebook" screen - need to click Next or Create new account
                if is_katana:
                    self.log("[*] Looking for Next/Continue button...")
                    
                    # Method 1: Try XML element search
                    next_found = False
                    next_locators = [
                        (AppiumBy.XPATH, "//android.widget.Button[@text='Next']"),
                        (AppiumBy.XPATH, "//*[@text='Next']"),
                        (AppiumBy.XPATH, "//android.widget.Button[@text='Create new account']"),
                        (AppiumBy.XPATH, "//*[@text='Create new account']"),
                        (AppiumBy.XPATH, "//android.widget.Button[@text='Get started']"),
                        (AppiumBy.XPATH, "//*[@text='Get started']"),
                    ]
                    
                    for by, value in next_locators:
                        try:
                            element = self.driver.find_element(by=by, value=value)
                            if element.is_displayed():
                                button_text = element.text or value
                                self.log(f"[+] Found '{button_text}' button via XML")
                                element.click()
                                next_found = True
                                time.sleep(3)
                                break
                        except:
                            continue
                    
                    # Method 2: Coordinate-based fallback
                    if not next_found:
                        self.log("[*] XML search failed, using coordinates...")
                        # Try common button positions
                        positions = [
                            (0.5, 0.62, "middle-upper"),
                            (0.5, 0.65, "middle"),
                            (0.5, 0.55, "middle-lower"),
                        ]
                        
                        for x_pct, y_pct, desc in positions:
                            self.log(f"[*] Trying {desc} position...")
                            if self._tap_coordinates(x_pct, y_pct, f"Tapping {desc}"):
                                time.sleep(3)
                                # Check if we moved forward
                                try:
                                    self.driver.find_element(AppiumBy.XPATH, "//*[contains(@content-desc, 'First name')]")
                                    self.log(f"[+] Successfully moved to name page using {desc}")
                                    next_found = True
                                    break
                                except:
                                    continue
                    
                    if not next_found:
                        self.log("[!] Could not proceed from Join Facebook screen")
                else:
                    # Facebook Lite
                    create_account_join_locators = [
                        (AppiumBy.XPATH, "//android.widget.Button[@text='Create new account']"),
                        (AppiumBy.XPATH, "//*[@text='Create new account']"),
                        (AppiumBy.XPATH, "//android.widget.Button[contains(@text, 'Create')]"),
                        (AppiumBy.XPATH, "//*[contains(@text, 'Create new account')]"),
                        (AppiumBy.ACCESSIBILITY_ID, "Create new account"),
                    ]
                    
                    if not self._find_and_click(create_account_join_locators, "Clicking 'Create new account' on Join page..."):
                        self.log("[*] Could not click Join page button - may already be on name page")
            
            # Check session again
            if not self._check_session_alive():
                self.log("[!] App crashed or session died after second click")
                raise Exception("Appium session died - app may have crashed")
            
            time.sleep(self.action_delay * 1.5)
            
            # Wait for name entry page to appear
            self.log("[*] Waiting for name entry page...")
            first_name_locators = [
                (AppiumBy.ACCESSIBILITY_ID, "First name,"),
                (AppiumBy.ACCESSIBILITY_ID, "First name"),
                (AppiumBy.XPATH, "//android.widget.EditText[@content-desc='First name,']"),
                (AppiumBy.XPATH, "//android.widget.EditText[@content-desc='First name']"),
            ]
            
            # Wait up to 10 seconds for first name field to appear
            name_page_ready = False
            for i in range(10):
                for by, value in first_name_locators:
                    try:
                        elem = self.driver.find_element(by=by, value=value)
                        if elem.is_displayed():
                            name_page_ready = True
                            self.log("[+] Name entry page is ready")
                            break
                    except:
                        continue
                if name_page_ready:
                    break
                time.sleep(1)
                self.log(f"[*] Waiting for name page... ({i+1}s)")
            
            if not name_page_ready:
                self.log("[!] Name entry page did not appear - might be on wrong page")
                # Save page source for debugging
                try:
                    page_source = self.driver.page_source
                    with open("error_name_page.xml", "w", encoding="utf-8") as f:
                        f.write(page_source)
                    self.log("[*] Page source saved to error_name_page.xml")
                except:
                    pass
            
            # Handle permission dialogs (contacts, etc.) that may appear
            self.log("[*] Checking for permission dialogs...")
            permission_handled = False
            for attempt in range(3):
                try:
                    # Look for "Allow Facebook to access your contacts?" dialog
                    permission_indicators = [
                        "//*[contains(@text, 'Allow Facebook')]",
                        "//*[contains(@text, 'access your contacts')]",
                        "//*[contains(@text, 'Allow') and contains(@text, 'contacts')]",
                    ]
                    
                    for indicator in permission_indicators:
                        try:
                            self.driver.find_element(AppiumBy.XPATH, indicator)
                            self.log("[+] Permission dialog detected")
                            
                            # Click "Deny" to skip contacts permission
                            deny_locators = [
                                (AppiumBy.XPATH, "//android.widget.Button[@text='Deny']"),
                                (AppiumBy.XPATH, "//*[@text='Deny']"),
                                (AppiumBy.ACCESSIBILITY_ID, "Deny"),
                            ]
                            
                            if self._find_and_click(deny_locators, "Clicking 'Deny' on permission dialog..."):
                                self.log("[+] Permission dialog dismissed")
                                permission_handled = True
                                time.sleep(1)
                                break
                        except:
                            continue
                    
                    if permission_handled:
                        break
                except:
                    pass
                
                time.sleep(0.5)
            
            if not permission_handled:
                self.log("[*] No permission dialogs found or already handled")

            first_name_locators = [
                (AppiumBy.ACCESSIBILITY_ID, "First name,"),
                (AppiumBy.ACCESSIBILITY_ID, "First name"),
                (AppiumBy.XPATH, "(//android.widget.EditText)[1]"),
            ]
            
            self._find_and_type(first_name_locators, first_name, f"Entering first name: {first_name}")
            
            last_name_locators = [
                (AppiumBy.ACCESSIBILITY_ID, "Last name,"),
                (AppiumBy.ACCESSIBILITY_ID, "Last name"),
                (AppiumBy.XPATH, "(//android.widget.EditText)[2]"),
            ]
            self._find_and_type(last_name_locators, last_name, f"Entering last name: {last_name}")
            
            # Click Next button - try XML first, then coordinates
            if is_katana:
                self.log("[*] Clicking Next after names...")
                next_clicked = False
                
                # Try XML first
                next_locators = [
                    (AppiumBy.XPATH, "//android.widget.Button[@text='Next']"),
                    (AppiumBy.XPATH, "//*[@text='Next']"),
                    (AppiumBy.ACCESSIBILITY_ID, "Next"),
                    (AppiumBy.XPATH, "//*[@content-desc='Next']"),
                    (AppiumBy.XPATH, "//android.widget.Button[contains(@text, 'Next')]"),
                ]
                
                for by, value in next_locators:
                    try:
                        element = self.driver.find_element(by=by, value=value)
                        if element.is_displayed():
                            self.log("[+] Found Next button via XML")
                            element.click()
                            next_clicked = True
                            time.sleep(self.action_delay)
                            break
                    except:
                        continue
                
                # Fallback to coordinates if XML fails
                if not next_clicked:
                    self.log("[*] XML failed, using coordinates for Next...")
                    self._tap_coordinates(0.5, 0.92, "Clicking Next (after names)...")
            else:
                next_locators = [
                    (AppiumBy.ACCESSIBILITY_ID, "Next"),
                    (AppiumBy.XPATH, "//*[@content-desc='Next']"),
                ]
                self._find_and_click(next_locators, "Clicking Next...")
            time.sleep(self.action_delay)
            
            # Handle name confirmation if it appears
            if self._click_first_radio_button():
                self.log("[+] Selected name from confirmation")
                if is_katana:
                    # Try XML first
                    next_clicked = False
                    next_locators = [
                        (AppiumBy.XPATH, "//android.widget.Button[@text='Next']"),
                        (AppiumBy.XPATH, "//*[@text='Next']"),
                        (AppiumBy.ACCESSIBILITY_ID, "Next"),
                        (AppiumBy.XPATH, "//*[@content-desc='Next']"),
                    ]
                    
                    for by, value in next_locators:
                        try:
                            element = self.driver.find_element(by=by, value=value)
                            if element.is_displayed():
                                element.click()
                                next_clicked = True
                                time.sleep(self.action_delay)
                                break
                        except:
                            continue
                    
                    if not next_clicked:
                        self._tap_coordinates(0.5, 0.92, "Clicking Next (after name confirmation)...")
                else:
                    next_locators = [
                        (AppiumBy.ACCESSIBILITY_ID, "Next"),
                        (AppiumBy.XPATH, "//*[@content-desc='Next']"),
                    ]
                    self._find_and_click(next_locators, "Clicking Next...")
                time.sleep(self.action_delay)
            
            birthday_locators = [
                (AppiumBy.XPATH, "//android.widget.EditText[contains(@content-desc, 'Birthday')]"),
                (AppiumBy.XPATH, "//android.view.ViewGroup[contains(@content-desc, 'Birthday')]"),
                (AppiumBy.XPATH, "//*[contains(@content-desc, 'Birthday')]"),
            ]
            
            # Check if we're on the "Age" input screen instead of birthday picker
            try:
                age_input = self.driver.find_element(AppiumBy.XPATH, "//android.widget.EditText[@text='Age']")
                self.log("[*] Detected 'Age' input screen - clicking 'Use date of birth' button...")
                
                # Click "Use date of birth" button
                use_dob_locators = [
                    (AppiumBy.XPATH, "//android.widget.Button[@text='Use date of birth']"),
                    (AppiumBy.XPATH, "//*[@text='Use date of birth']"),
                    (AppiumBy.ACCESSIBILITY_ID, "Use date of birth"),
                ]
                
                if self._find_and_click(use_dob_locators, "Clicking 'Use date of birth'..."):
                    self.log("[+] Switched to date of birth picker")
                    time.sleep(self.action_delay)
                else:
                    self.log("[!] Could not find 'Use date of birth' button")
            except:
                # Not on Age screen, continue normally
                pass
            
            self._find_and_click(birthday_locators, "Opening birthday picker...")
            time.sleep(self.action_delay)
            
            # Set the birthday by directly typing into the NumberPicker EditTexts
            try:
                self.log(f"[*] Setting birthday to {day}/{month}/{year}")
                
                # Wait for date picker to fully load
                time.sleep(1)
                
                # Try direct input method first
                year_inputs = self.driver.find_elements(AppiumBy.ID, "android:id/numberpicker_input")
                self.log(f"[*] Found {len(year_inputs)} NumberPicker inputs")
                
                if len(year_inputs) >= 3:
                    # Direct input method - more reliable
                    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", 
                                  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
                    month_str = month_names[month - 1]
                    
                    # Facebook date picker order might be: Month, Day, Year
                    # Let's try different orders to find the correct one
                    
                    try:
                        # Method 1: Try Month(0), Day(1), Year(2)
                        self.log("[*] Trying Method 1: Month, Day, Year order")
                        
                        # Set month (1st input)
                        month_input = year_inputs[0]
                        month_input.click()
                        time.sleep(0.3)
                        month_input.clear()
                        month_input.send_keys(month_str)
                        self.log(f"[+] Set month to {month_str} (input 0)")
                        
                        time.sleep(0.3)
                        
                        # Set day (2nd input)
                        day_input = year_inputs[1]
                        day_input.click()
                        time.sleep(0.3)
                        day_input.clear()
                        day_input.send_keys(str(day))
                        self.log(f"[+] Set day to {day} (input 1)")
                        
                        time.sleep(0.3)
                        
                        # Set year (3rd input)
                        year_input = year_inputs[2]
                        year_input.click()
                        time.sleep(0.3)
                        year_input.clear()
                        year_input.send_keys(str(year))
                        self.log(f"[+] Set year to {year} (input 2)")
                        
                    except Exception as e1:
                        self.log(f"[!] Method 1 failed: {e1}")
                        
                        try:
                            # Method 2: Try Day(0), Month(1), Year(2) 
                            self.log("[*] Trying Method 2: Day, Month, Year order")
                            
                            # Set day (1st input)
                            day_input = year_inputs[0]
                            day_input.click()
                            time.sleep(0.3)
                            day_input.clear()
                            day_input.send_keys(str(day))
                            self.log(f"[+] Set day to {day} (input 0)")
                            
                            time.sleep(0.3)
                            
                            # Set month (2nd input)
                            month_input = year_inputs[1]
                            month_input.click()
                            time.sleep(0.3)
                            month_input.clear()
                            month_input.send_keys(month_str)
                            self.log(f"[+] Set month to {month_str} (input 1)")
                            
                            time.sleep(0.3)
                            
                            # Set year (3rd input)
                            year_input = year_inputs[2]
                            year_input.click()
                            time.sleep(0.3)
                            year_input.clear()
                            year_input.send_keys(str(year))
                            self.log(f"[+] Set year to {year} (input 2)")
                            
                        except Exception as e2:
                            self.log(f"[!] Method 2 failed: {e2}")
                            self.log("[*] Falling back to scrolling method")
                            raise e2
                else:
                    self.log("[*] Direct input not available, using scrolling method")
                    raise Exception("No NumberPicker inputs found")
                    
            except Exception as e:
                self.log(f"[!] Direct input failed: {e}")
                # Fallback: scrolling method with improved stability
                try:
                    import datetime
                    current_year = datetime.datetime.now().year
                    years_to_scroll = min(current_year - year, 30)  # Limit to prevent excessive scrolling
                    
                    if years_to_scroll > 0:
                        year_picker = self.driver.find_element(AppiumBy.XPATH, "(//android.widget.NumberPicker)[3]")
                        self.log(f"[*] Scrolling {years_to_scroll} years back from {current_year} to {year}")
                        
                        # Scroll in smaller chunks to prevent shaking
                        for i in range(years_to_scroll):
                            self.driver.execute_script('mobile: swipeGesture', {
                                'elementId': year_picker.id,
                                'direction': 'up',
                                'percent': 0.25,  # Even smaller swipes
                                'speed': 1000     # Slower speed for stability
                            })
                            time.sleep(0.3)  # Longer delay between swipes
                            
                            # Break every 5 swipes to let UI settle
                            if (i + 1) % 5 == 0:
                                time.sleep(1)
                                self.log(f"[*] Scrolled {i+1}/{years_to_scroll} years...")
                        
                        self.log(f"[+] Finished scrolling to approximately year {year}")
                    else:
                        self.log(f"[*] Year {year} is current or future, no scrolling needed")
                        
                except Exception as scroll_error:
                    self.log(f"[!] Scrolling method also failed: {scroll_error}")
                    self.log("[!] Using default date picker values")
            
            time.sleep(1)
            
            # Click Set button on date picker
            if is_katana:
                # Try XML first
                set_clicked = False
                set_locators = [
                    (AppiumBy.XPATH, "//android.widget.Button[@text='Set']"),
                    (AppiumBy.XPATH, "//android.widget.Button[@text='OK']"),
                    (AppiumBy.ID, "android:id/button1"),
                    (AppiumBy.XPATH, "//*[@text='Set']"),
                    (AppiumBy.XPATH, "//*[@text='OK']"),
                ]
                
                for by, value in set_locators:
                    try:
                        element = self.driver.find_element(by=by, value=value)
                        if element.is_displayed():
                            self.log("[+] Found Set button via XML")
                            element.click()
                            set_clicked = True
                            time.sleep(self.action_delay)
                            break
                    except:
                        continue
                
                if not set_clicked:
                    self.log("[*] XML failed, using coordinates for Set...")
                    self._tap_coordinates(0.85, 0.92, "Setting date...")
            else:
                set_button_locators = [
                    (AppiumBy.XPATH, "//android.widget.Button[@text='Set']"),
                    (AppiumBy.ID, "android:id/button1"),
                ]
                self._find_and_click(set_button_locators, "Setting date...")
            time.sleep(self.action_delay)
            
            # Click Next after birthday
            if is_katana:
                self.log("[*] Clicking Next after birthday...")
                next_clicked = False
                next_locators = [
                    (AppiumBy.XPATH, "//android.widget.Button[@text='Next']"),
                    (AppiumBy.XPATH, "//*[@text='Next']"),
                    (AppiumBy.XPATH, "//android.widget.Button[contains(@text, 'Next')]"),
                    (AppiumBy.XPATH, "//*[contains(@text, 'Next')]"),
                    (AppiumBy.ACCESSIBILITY_ID, "Next"),
                    (AppiumBy.XPATH, "//*[@content-desc='Next']"),
                    (AppiumBy.CLASS_NAME, "android.widget.Button"),  # Try any button as last resort
                ]
                
                for by, value in next_locators:
                    try:
                        if by == AppiumBy.CLASS_NAME:
                            # For class name, find all buttons and click the one with "Next" text
                            buttons = self.driver.find_elements(by, value)
                            for btn in buttons:
                                try:
                                    if btn.text and 'next' in btn.text.lower() and btn.is_displayed():
                                        self.log("[+] Found Next button via class name search")
                                        btn.click()
                                        next_clicked = True
                                        time.sleep(self.action_delay)
                                        break
                                except:
                                    continue
                            if next_clicked:
                                break
                        else:
                            element = self.driver.find_element(by, value)
                            if element.is_displayed():
                                self.log("[+] Found Next button via XML")
                                element.click()
                                next_clicked = True
                                time.sleep(self.action_delay)
                                break
                    except:
                        continue
                
                if not next_clicked:
                    self.log("[!] XML search failed for Next button")
                    # Check if session is still alive before trying coordinates
                    if self._check_session_alive():
                        self._tap_coordinates(0.5, 0.92, "Clicking Next (after birthday)...")
                    else:
                        self.log("[!] Session died, cannot click Next")
            else:
                next_locators = [
                    (AppiumBy.ACCESSIBILITY_ID, "Next"),
                    (AppiumBy.XPATH, "//*[@content-desc='Next']"),
                ]
                self._find_and_click(next_locators, "Clicking Next...")
            time.sleep(self.action_delay)
            
            # Select gender based on parameter
            self.log(f"[*] Selecting gender: {gender}")
            
            if is_katana:
                # Try XML first for gender selection
                gender_selected = False
                
                if gender.lower() == "female":
                    gender_locators = [
                        (AppiumBy.XPATH, "//*[@text='Female']"),
                        (AppiumBy.XPATH, "//android.widget.RadioButton[@text='Female']"),
                        (AppiumBy.XPATH, "//*[contains(@text, 'Female')]"),
                        (AppiumBy.XPATH, "//android.widget.TextView[@text='Female']"),
                    ]
                elif gender.lower() == "custom":
                    gender_locators = [
                        (AppiumBy.XPATH, "//*[@text='More options']"),
                        (AppiumBy.XPATH, "//*[@text='Custom']"),
                        (AppiumBy.XPATH, "//*[contains(@text, 'More options')]"),
                    ]
                else:  # Male
                    gender_locators = [
                        (AppiumBy.XPATH, "//*[@text='Male']"),
                        (AppiumBy.XPATH, "//android.widget.RadioButton[@text='Male']"),
                        (AppiumBy.XPATH, "//*[contains(@text, 'Male')]"),
                        (AppiumBy.XPATH, "//android.widget.TextView[@text='Male']"),
                    ]
                
                for by, value in gender_locators:
                    try:
                        element = self.driver.find_element(by, value)
                        if element.is_displayed():
                            self.log(f"[+] Found {gender} option via XML")
                            element.click()
                            gender_selected = True
                            time.sleep(1)
                            break
                    except:
                        continue
                
                # Fallback to coordinates if XML fails
                if not gender_selected:
                    self.log("[*] XML failed, using coordinates for gender...")
                    if gender.lower() == "female":
                        self._tap_coordinates(0.5, 0.35, f"Selecting gender: Female")
                    elif gender.lower() == "custom":
                        self._tap_coordinates(0.5, 0.55, f"Selecting gender: Custom")
                    else:  # Male
                        self._tap_coordinates(0.5, 0.45, f"Selecting gender: Male")
            else:
                # Use element search for Lite
                if gender.lower() == "female":
                    gender_locators = [
                        (AppiumBy.XPATH, "//android.widget.RadioButton[2]"),
                        (AppiumBy.XPATH, "//*[@text='Female']"),
                        (AppiumBy.XPATH, "//android.widget.TextView[@text='Female']"),
                        (AppiumBy.ACCESSIBILITY_ID, "Female"),
                        (AppiumBy.XPATH, "(//android.widget.RadioButton)[2]"),
                    ]
                elif gender.lower() == "custom":
                    gender_locators = [
                        (AppiumBy.XPATH, "//android.widget.RadioButton[3]"),
                        (AppiumBy.XPATH, "//*[@text='More options']"),
                        (AppiumBy.XPATH, "//*[@text='Custom']"),
                        (AppiumBy.ACCESSIBILITY_ID, "Custom"),
                        (AppiumBy.XPATH, "(//android.widget.RadioButton)[3]"),
                    ]
                else:  # Male
                    gender_locators = [
                        (AppiumBy.XPATH, "//android.widget.RadioButton[1]"),
                        (AppiumBy.XPATH, "//*[@text='Male']"),
                        (AppiumBy.XPATH, "//android.widget.TextView[@text='Male']"),
                        (AppiumBy.ACCESSIBILITY_ID, "Male"),
                        (AppiumBy.XPATH, "(//android.widget.RadioButton)[1]"),
                    ]
                
                if not self._find_and_click(gender_locators, f"Selecting gender: {gender}"):
                    self.log("[!] Could not select gender")
            
            # Click Next after gender
            if is_katana:
                next_clicked = False
                next_locators = [
                    (AppiumBy.XPATH, "//android.widget.Button[@text='Next']"),
                    (AppiumBy.XPATH, "//*[@text='Next']"),
                    (AppiumBy.ACCESSIBILITY_ID, "Next"),
                    (AppiumBy.XPATH, "//*[@content-desc='Next']"),
                ]
                
                for by, value in next_locators:
                    try:
                        element = self.driver.find_element(by=by, value=value)
                        if element.is_displayed():
                            element.click()
                            next_clicked = True
                            time.sleep(self.action_delay)
                            break
                    except:
                        continue
                
                if not next_clicked:
                    self._tap_coordinates(0.5, 0.92, "Clicking Next (after gender)...")
            else:
                next_locators = [
                    (AppiumBy.ACCESSIBILITY_ID, "Next"),
                    (AppiumBy.XPATH, "//*[@content-desc='Next']"),
                ]
                self._find_and_click(next_locators, "Clicking Next...")
            time.sleep(self.action_delay)
            
            # Handle permission dialog if it appears
            self._handle_permission_dialog()
            time.sleep(1)

            # Choose between email or phone signup
            if use_phone and phone:
                # Use phone number signup
                phone_option_locators = [
                    (AppiumBy.ACCESSIBILITY_ID, "Sign up with mobile number"),
                    (AppiumBy.XPATH, "//*[@content-desc='Sign up with mobile number']"),
                    (AppiumBy.XPATH, "//*[@text='Sign up with mobile number']"),
                ]
                if self._find_and_click(phone_option_locators, "Switching to phone number..."):
                    self.log("[+] Switched to phone number signup")
                else:
                    self.log("[*] Already on phone number signup or button not found")
                
                time.sleep(self.action_delay)
                
                # Handle permission dialog again if needed
                self._handle_permission_dialog()
                
                # Enter phone number (strip country code if present)
                # Facebook expects only local number, country code is selected separately
                phone_to_enter = phone
                if phone.startswith('+'):
                    # Remove + and country code
                    # For Cambodia (+855), remove +855 and keep only local digits
                    phone_to_enter = phone.replace('+', '')
                    # Remove common country codes
                    country_codes = ['855', '84', '86', '91', '62', '63', '66', '60', '81', '82', '65', '61', '1', '44']
                    for code in country_codes:
                        if phone_to_enter.startswith(code):
                            phone_to_enter = phone_to_enter[len(code):]
                            self.log(f"[*] Stripped country code {code}, entering: {phone_to_enter}")
                            break
                
                phone_locators = [
                    (AppiumBy.XPATH, "//android.widget.EditText"),  # Any EditText
                    (AppiumBy.CLASS_NAME, "android.widget.EditText"),  # EditText by class
                    (AppiumBy.XPATH, "(//android.widget.EditText)[1]"),  # First EditText on page
                    (AppiumBy.ACCESSIBILITY_ID, "Mobile number,"),
                    (AppiumBy.ACCESSIBILITY_ID, "Mobile number"),
                    (AppiumBy.ACCESSIBILITY_ID, "Phone number,"),
                    (AppiumBy.ACCESSIBILITY_ID, "Phone number"),
                    (AppiumBy.XPATH, "//android.widget.EditText[@content-desc='Mobile number,']"),
                    (AppiumBy.XPATH, "//android.widget.EditText[@content-desc='Phone number,']"),
                    (AppiumBy.XPATH, "//android.widget.EditText[contains(@content-desc, 'Mobile')]"),
                    (AppiumBy.XPATH, "//android.widget.EditText[contains(@content-desc, 'Phone')]"),
                ]
                if self._find_and_type(phone_locators, phone_to_enter, f"Entering phone: {phone_to_enter}"):
                    if hasattr(self.log_signal, 'status'):
                        self.log_signal.status.emit("Entering details...")
                    # Auto-click Next after entering phone
                    time.sleep(self.action_delay * 0.5)
                    if is_katana:
                        # Try XML first
                        next_clicked = False
                        next_locators = [
                            (AppiumBy.XPATH, "//android.widget.Button[@text='Next']"),
                            (AppiumBy.XPATH, "//*[@text='Next']"),
                            (AppiumBy.ACCESSIBILITY_ID, "Next"),
                            (AppiumBy.XPATH, "//*[@content-desc='Next']"),
                        ]
                        
                        for by, value in next_locators:
                            try:
                                element = self.driver.find_element(by=by, value=value)
                                if element.is_displayed():
                                    element.click()
                                    next_clicked = True
                                    time.sleep(self.action_delay)
                                    break
                            except:
                                continue
                        
                        if not next_clicked:
                            self._tap_coordinates(0.5, 0.92, "Clicking Next (after phone)...")
                    else:
                        next_locators = [
                            (AppiumBy.ACCESSIBILITY_ID, "Next"),
                            (AppiumBy.XPATH, "//*[@content-desc='Next']"),
                        ]
                        self._find_and_click(next_locators, "Auto-clicking Next after phone...")
                    time.sleep(self.action_delay)
                else:
                    self.log("[!] Could not enter phone - trying Next anyway")
                    if is_katana:
                        # Try XML first
                        next_clicked = False
                        next_locators = [
                            (AppiumBy.XPATH, "//android.widget.Button[@text='Next']"),
                            (AppiumBy.XPATH, "//*[@text='Next']"),
                            (AppiumBy.ACCESSIBILITY_ID, "Next"),
                        ]
                        
                        for by, value in next_locators:
                            try:
                                element = self.driver.find_element(by=by, value=value)
                                if element.is_displayed():
                                    element.click()
                                    next_clicked = True
                                    time.sleep(self.action_delay)
                                    break
                            except:
                                continue
                        
                        if not next_clicked:
                            self._tap_coordinates(0.5, 0.92, "Clicking Next...")
                    else:
                        next_locators = [
                            (AppiumBy.ACCESSIBILITY_ID, "Next"),
                            (AppiumBy.XPATH, "//*[@content-desc='Next']"),
                        ]
                        self._find_and_click(next_locators, "Clicking Next...")
                    time.sleep(self.action_delay)
            else:
                # Use email signup (default)
                email_option_locators = [
                    (AppiumBy.ACCESSIBILITY_ID, "Sign up with email"),
                    (AppiumBy.XPATH, "//*[@content-desc='Sign up with email']"),
                    (AppiumBy.XPATH, "//*[@text='Sign up with email']"),
                ]
                self._find_and_click(email_option_locators, "Switching to email...")
                time.sleep(self.action_delay)
                
                # Handle permission dialog again if needed
                self._handle_permission_dialog()
                
                email_locators = [
                    (AppiumBy.ACCESSIBILITY_ID, "Email,"),
                    (AppiumBy.ACCESSIBILITY_ID, "Email"),
                    (AppiumBy.XPATH, "//android.widget.EditText[@content-desc='Email,']"),
                    (AppiumBy.XPATH, "//android.widget.EditText[@content-desc='Email']"),
                    (AppiumBy.XPATH, "//android.widget.EditText[contains(@content-desc, 'Email')]"),
                    (AppiumBy.XPATH, "(//android.widget.EditText)[1]"),  # First EditText on page
                ]
                if self._find_and_type(email_locators, email, f"Entering email: {email}"):
                    if hasattr(self.log_signal, 'status'):
                        self.log_signal.status.emit("Entering details...")
                    # Auto-click Next after entering email
                    time.sleep(self.action_delay * 0.5)
                    if is_katana:
                        # Try XML first
                        next_clicked = False
                        next_locators = [
                            (AppiumBy.XPATH, "//android.widget.Button[@text='Next']"),
                            (AppiumBy.XPATH, "//*[@text='Next']"),
                            (AppiumBy.ACCESSIBILITY_ID, "Next"),
                            (AppiumBy.XPATH, "//*[@content-desc='Next']"),
                        ]
                        
                        for by, value in next_locators:
                            try:
                                element = self.driver.find_element(by=by, value=value)
                                if element.is_displayed():
                                    element.click()
                                    next_clicked = True
                                    time.sleep(self.action_delay)
                                    break
                            except:
                                continue
                        
                        if not next_clicked:
                            self._tap_coordinates(0.5, 0.92, "Clicking Next (after email)...")
                    else:
                        next_locators = [
                            (AppiumBy.ACCESSIBILITY_ID, "Next"),
                            (AppiumBy.XPATH, "//*[@content-desc='Next']"),
                        ]
                        self._find_and_click(next_locators, "Auto-clicking Next after email...")
                    time.sleep(self.action_delay)
                else:
                    self.log("[!] Could not enter email - trying Next anyway")
                    if is_katana:
                        # Try XML first
                        next_clicked = False
                        next_locators = [
                            (AppiumBy.XPATH, "//android.widget.Button[@text='Next']"),
                            (AppiumBy.XPATH, "//*[@text='Next']"),
                            (AppiumBy.ACCESSIBILITY_ID, "Next"),
                        ]
                        
                        for by, value in next_locators:
                            try:
                                element = self.driver.find_element(by=by, value=value)
                                if element.is_displayed():
                                    element.click()
                                    next_clicked = True
                                    time.sleep(self.action_delay)
                                    break
                            except:
                                continue
                        
                        if not next_clicked:
                            self._tap_coordinates(0.5, 0.92, "Clicking Next...")
                    else:
                        next_locators = [
                            (AppiumBy.ACCESSIBILITY_ID, "Next"),
                            (AppiumBy.XPATH, "//*[@content-desc='Next']"),
                        ]
                        self._find_and_click(next_locators, "Clicking Next...")
                    time.sleep(self.action_delay)
            
            # Wait for password page to load
            self.log("[*] Waiting for password page...")
            time.sleep(2)
            
            # Try to find password field with multiple attempts
            password_locators = [
                (AppiumBy.XPATH, "//android.widget.EditText[@text='Password']"),
                (AppiumBy.XPATH, "//android.widget.EditText[contains(@text, 'Password')]"),
                (AppiumBy.XPATH, "//android.widget.EditText[contains(@hint, 'Password')]"),
                (AppiumBy.XPATH, "//android.widget.EditText[@password='true']"),
                (AppiumBy.ACCESSIBILITY_ID, "Password,"),
                (AppiumBy.ACCESSIBILITY_ID, "Password"),
                (AppiumBy.XPATH, "//android.widget.EditText[@content-desc='Password,']"),
                (AppiumBy.XPATH, "//android.widget.EditText[@content-desc='Password']"),
                (AppiumBy.XPATH, "//android.widget.EditText[contains(@content-desc, 'Password')]"),
                (AppiumBy.XPATH, "//android.widget.EditText[contains(@content-desc, 'password')]"),
                (AppiumBy.XPATH, "(//android.widget.EditText)[1]"),  # First EditText on page
                (AppiumBy.CLASS_NAME, "android.widget.EditText"),  # Any EditText as last resort
            ]
            self._find_and_type(password_locators, password, "Entering password...")
            
            # Click Next after password
            if is_katana:
                # Try XML first
                next_clicked = False
                next_locators = [
                    (AppiumBy.XPATH, "//android.widget.Button[@text='Next']"),
                    (AppiumBy.XPATH, "//*[@text='Next']"),
                    (AppiumBy.ACCESSIBILITY_ID, "Next"),
                    (AppiumBy.XPATH, "//*[@content-desc='Next']"),
                ]
                
                for by, value in next_locators:
                    try:
                        element = self.driver.find_element(by=by, value=value)
                        if element.is_displayed():
                            element.click()
                            next_clicked = True
                            time.sleep(self.action_delay)
                            break
                    except:
                        continue
                
                if not next_clicked:
                    self._tap_coordinates(0.5, 0.92, "Clicking Next (after password)...")
            else:
                next_locators = [
                    (AppiumBy.ACCESSIBILITY_ID, "Next"),
                    (AppiumBy.XPATH, "//*[@content-desc='Next']"),
                ]
                self._find_and_click(next_locators, "Clicking Next...")
            time.sleep(self.action_delay)
            
            # Click Sign Up button
            if is_katana:
                if hasattr(self.log_signal, 'status'):
                    self.log_signal.status.emit("Submitting...")
                # Try XML first
                signup_clicked = False
                signup_locators = [
                    (AppiumBy.XPATH, "//android.widget.Button[@text='Sign Up']"),
                    (AppiumBy.XPATH, "//*[@text='Sign Up']"),
                    (AppiumBy.ACCESSIBILITY_ID, "Sign Up"),
                    (AppiumBy.XPATH, "//*[@content-desc='Sign Up']"),
                    (AppiumBy.XPATH, "//android.widget.Button[contains(@text, 'Sign')]"),
                ]
                
                for by, value in signup_locators:
                    try:
                        element = self.driver.find_element(by=by, value=value)
                        if element.is_displayed():
                            self.log("[+] Found Sign Up button via XML")
                            element.click()
                            signup_clicked = True
                            break
                    except:
                        continue
                
                if not signup_clicked:
                    self.log("[*] XML failed, using coordinates for Sign Up...")
                    self._tap_coordinates(0.5, 0.92, "Submitting registration...")
            else:
                signup_locators = [
                    (AppiumBy.ACCESSIBILITY_ID, "Sign Up"),
                    (AppiumBy.XPATH, "//*[@content-desc='Sign Up']"),
                ]
                if hasattr(self.log_signal, 'status'):
                    self.log_signal.status.emit("Submitting...")
                self._find_and_click(signup_locators, "Submitting registration...")
            
            # Wait for registration to process
            time.sleep(self.action_delay * 2)
            
            # Handle "Save your login info?" dialog - click "Not now"
            not_now_locators = [
                (AppiumBy.XPATH, "//*[@text='Not now']"),
                (AppiumBy.XPATH, "//android.widget.Button[@text='Not now']"),
                (AppiumBy.ACCESSIBILITY_ID, "Not now"),
                (AppiumBy.XPATH, "//*[contains(@text, 'Not now')]"),
            ]
            if self._find_and_click(not_now_locators, "Clicking 'Not now' on save login dialog..."):
                self.log("[+] Skipped saving login info")
                time.sleep(self.action_delay * 2)  # Wait longer for next screen
            else:
                self.log("[*] Save login dialog not found or already dismissed")
                time.sleep(self.action_delay)
            
            # Handle "Agree to Facebook's terms" dialog - click "I agree"
            # Wait for the terms page to fully load (retry multiple times)
            i_agree_locators = [
                (AppiumBy.XPATH, "//*[@text='I agree']"),
                (AppiumBy.XPATH, "//android.widget.Button[@text='I agree']"),
                (AppiumBy.ACCESSIBILITY_ID, "I agree"),
                (AppiumBy.XPATH, "//*[contains(@text, 'I agree')]"),
                (AppiumBy.XPATH, "//*[contains(@text, 'agree')]"),
            ]
            
            # First, wait for the page to fully load before trying to click
            self.log("[*] Waiting for terms page to fully load...")
            time.sleep(5)
            
            # Retry up to 10 times with 3 second delays (total 30 seconds)
            i_agree_clicked = False
            for attempt in range(10):
                self.log(f"[*] Attempting to click 'I agree' (attempt {attempt + 1}/10)...")
                
                try:
                    # Try to find the button first
                    button_found = False
                    for by, value in i_agree_locators:
                        try:
                            element = self.driver.find_element(by=by, value=value)
                            button_found = True
                            self.log(f"[+] Found 'I agree' button using {by}")
                            
                            # Check if button is enabled
                            if element.is_enabled():
                                self.log("[*] Button is enabled, clicking...")
                                element.click()
                                self.log("[+] Clicked 'I agree' button")
                                i_agree_clicked = True
                                
                                # Wait and check if we moved to next screen
                                time.sleep(5)
                                
                                # Check if we're still on terms page
                                still_on_terms = False
                                try:
                                    self.driver.find_element(AppiumBy.XPATH, "//*[contains(@text, 'Agree to Facebook')]")
                                    still_on_terms = True
                                except:
                                    pass
                                
                                if not still_on_terms:
                                    self.log("[+] Successfully moved past terms screen")
                                    break
                                else:
                                    self.log("[!] Still on terms screen, button may be loading...")
                                    i_agree_clicked = False
                            else:
                                self.log("[!] Button found but not enabled (loading state)")
                            
                            break
                        except:
                            continue
                    
                    if not button_found:
                        self.log("[*] 'I agree' button not found, may have moved past it")
                        break
                    
                    if i_agree_clicked:
                        break
                    
                    # Wait before next attempt
                    time.sleep(3)
                    
                except Exception as e:
                    self.log(f"[!] Error on attempt {attempt + 1}: {e}")
                    time.sleep(3)
                    continue
            
            if not i_agree_clicked:
                self.log("[!] Could not successfully click 'I agree' after 10 attempts")
                self.log("[*] Button may be stuck in loading state - trying to proceed anyway...")
            
            # Handle SMS verification screen - click "Continue"
            # Retry multiple times as this screen may take time to load
            continue_locators = [
                (AppiumBy.XPATH, "//*[@text='Continue']"),
                (AppiumBy.XPATH, "//android.widget.Button[@text='Continue']"),
                (AppiumBy.ACCESSIBILITY_ID, "Continue"),
                (AppiumBy.XPATH, "//*[contains(@text, 'Continue')]"),
            ]
            
            continue_clicked = False
            for attempt in range(10):
                self.log(f"[*] Looking for 'Continue' button (attempt {attempt + 1}/10)...")
                time.sleep(2)
                
                # First check if we're on SMS confirmation screen
                try:
                    sms_screen_indicators = [
                        "//*[contains(@text, 'confirmation code')]",
                        "//*[contains(@text, 'Enter the')]",
                        "//*[contains(@text, '5-digit code')]",
                        "//*[contains(@text, 'Confirmation code')]",
                    ]
                    
                    for indicator in sms_screen_indicators:
                        try:
                            self.driver.find_element(AppiumBy.XPATH, indicator)
                            self.log("[+] SMS confirmation screen detected!")
                            self.log("[!] Account created successfully - waiting for SMS verification")
                            self.log("[*] Backing up account information...")
                            uid = self._try_extract_uid()
                            self._backup_account_info(first_name, last_name, email, password, birthday, gender, phone, use_phone, uid)
                            continue_clicked = True  # Mark as completed
                            break
                        except:
                            continue
                    
                    if continue_clicked:
                        break
                except:
                    pass
                
                try:
                    # Check for phone number error first
                    try:
                        error_element = self.driver.find_element(AppiumBy.XPATH, "//*[contains(@text, 'may be incorrect')]")
                        self.log("[!] Phone number error detected: 'may be incorrect'")
                        self.log(f"[!] Phone number used: {phone}")
                        
                        # Try to find and click the phone number field to edit it
                        phone_field_locators = [
                            (AppiumBy.XPATH, "//android.widget.EditText[contains(@text, '+')]"),
                            (AppiumBy.XPATH, "//android.widget.EditText"),
                        ]
                        
                        for by, value in phone_field_locators:
                            try:
                                phone_field = self.driver.find_element(by=by, value=value)
                                self.log("[*] Found phone number field, clearing and re-entering...")
                                phone_field.click()
                                time.sleep(0.5)
                                phone_field.clear()
                                time.sleep(0.5)
                                
                                # Try without + sign
                                phone_without_plus = phone.replace('+', '')
                                phone_field.send_keys(phone_without_plus)
                                self.log(f"[*] Re-entered phone without +: {phone_without_plus}")
                                time.sleep(1)
                                break
                            except:
                                continue
                    except:
                        pass  # No error, continue normally
                    
                    if self._find_and_click(continue_locators, f"Clicking 'Continue' (attempt {attempt + 1})..."):
                        self.log("[+] Clicked Continue - SMS verification initiated")
                        self.log("[!] NOTE: Account requires SMS verification code")
                        continue_clicked = True
                        time.sleep(3)
                        
                        # Backup account information
                        self.log("[*] Backing up account information...")
                        
                        # Try to extract UID from app data
                        uid = self._try_extract_uid()
                        
                        self._backup_account_info(first_name, last_name, email, password, birthday, gender, phone, use_phone, uid)
                        break
                except Exception as e:
                    self.log(f"[!] Error on attempt {attempt + 1}: {e}")
                    continue
            
            if not continue_clicked:
                self.log("[!] Could not find 'Continue' button after 10 attempts")
                self.log("[*] Account may be at a different screen or already completed")
                # Still try to backup even if Continue wasn't clicked
                self.log("[*] Backing up account information anyway...")
                uid = self._try_extract_uid()
                self._backup_account_info(first_name, last_name, email, password, birthday, gender, phone, use_phone, uid)
            
            self.log("\n" + "="*50)
            self.log(f"[+] Registration completed for {email}")
            self.log("="*50)
            if hasattr(self.log_signal, 'status'):
                self.log_signal.status.emit("Completed!")
            
        except Exception as e:
            try:
                self.log(f"\n[!] ERROR: {e}")
                if hasattr(self.log_signal, 'status'):
                    self.log_signal.status.emit("Error!")
            except (RuntimeError, AttributeError):
                print(f"\n[!] ERROR: {e}")
            
        finally:
            try:
                if hasattr(self.log_signal, 'finished'):
                    self.log_signal.finished.emit()
            except (RuntimeError, AttributeError):
                pass  # LogSignal already deleted
            if self.driver:
                try:
                    self.driver.quit()
                except:
                    pass


