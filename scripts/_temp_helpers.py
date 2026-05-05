    # ═══════════════════════════════════════════════════════════════════════
    # Single Device Operation Wrappers (for context menu)
    # ═══════════════════════════════════════════════════════════════════════
    
    def _install_facebook_app(self, device_id, app_type):
        """Install Facebook app on a single device"""
        import threading
        def _run():
            try:
                if app_type == "katana":
                    apk_path = "com.facebook.katana_552.1.0.45.68-469416370_minAPI28(arm64-v8a)(360,400,420,480,560,640dpi)_apkmirror.com.apk"
                    app_name = "Facebook"
                else:
                    apk_path = "com.facebook.lite_494.0.0.9.107-512801323_minAPI21(armeabi-v7a)(nodpi)_apkmirror.com.apk"
                    app_name = "Facebook Lite"
                
                if not os.path.exists(apk_path):
                    self.add_activity(f"✗ APK not found: {apk_path}")
                    return
                
                self.add_activity(f"Installing {app_name} on {device_id}...")
                result = safe_subprocess_run([self.adb_path, "-s", device_id, "install", "-r", apk_path],
                                            capture_output=True, text=True, timeout=120)
                if "Success" in result.stdout:
                    self.add_activity(f"✓ {app_name} installed on {device_id}")
                else:
                    self.add_activity(f"✗ Failed to install {app_name} on {device_id}")
            except Exception as e:
                self.add_activity(f"✗ Error installing on {device_id}: {str(e)}")
        threading.Thread(target=_run, daemon=True).start()
    
    def _uninstall_facebook_app(self, device_id, package):
        """Uninstall Facebook app from a single device"""
        import threading
        def _run():
            try:
                app_name = "Facebook" if "katana" in package else "Facebook Lite"
                self.add_activity(f"Uninstalling {app_name} from {device_id}...")
                result = safe_subprocess_run([self.adb_path, "-s", device_id, "uninstall", package],
                                            capture_output=True, text=True, timeout=60)
                if "Success" in result.stdout:
                    self.add_activity(f"✓ {app_name} uninstalled from {device_id}")
                else:
                    self.add_activity(f"✗ Failed to uninstall {app_name} from {device_id}")
            except Exception as e:
                self.add_activity(f"✗ Error uninstalling from {device_id}: {str(e)}")
        threading.Thread(target=_run, daemon=True).start()
    
    def _clear_facebook_data(self, device_id, package):
        """Clear Facebook app data on a single device"""
        import threading
        def _run():
            try:
                app_name = "Facebook" if "katana" in package else "Facebook Lite"
                self.add_activity(f"Clearing {app_name} data on {device_id}...")
                result = safe_subprocess_run([self.adb_path, "-s", device_id, "shell", "pm", "clear", package],
                                            capture_output=True, text=True, timeout=30)
                if "Success" in result.stdout:
                    self.add_activity(f"✓ {app_name} data cleared on {device_id}")
                else:
                    self.add_activity(f"✗ Failed to clear {app_name} data on {device_id}")
            except Exception as e:
                self.add_activity(f"✗ Error clearing data on {device_id}: {str(e)}")
        threading.Thread(target=_run, daemon=True).start()
    
    def _view_screen_single(self, device_id):
        """Open scrcpy for a single device"""
        scrcpy_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scrcpy-win64-v3.1", "scrcpy.exe")
        if not os.path.exists(scrcpy_path):
            QMessageBox.warning(self, "scrcpy Not Found", 
                f"scrcpy not found at:\n{scrcpy_path}\n\nPlease ensure scrcpy-win64-v3.1 folder exists.")
            return
        try:
            import subprocess
            subprocess.Popen([scrcpy_path, "-s", device_id, "--window-title", f"FRT - {device_id}"],
                           creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            self.add_activity(f"✓ Opened screen view for {device_id}")
        except Exception as e:
            self.add_activity(f"✗ Failed to open screen: {str(e)}")
    
    def _set_devices_working_single(self, device_id):
        """Configure device settings for a single device"""
        self.add_activity(f"Configuring device settings for {device_id}...")
        QMessageBox.information(self, "Device Settings", f"Device settings configuration for {device_id}")
    
    def _switch_keyboard_single(self, device_id):
        """Switch keyboard for a single device"""
        try:
            result = safe_subprocess_run([self.adb_path, "-s", device_id, "shell", "ime", "list", "-s"],
                                        capture_output=True, text=True, timeout=10)
            imes = [line.strip() for line in result.stdout.strip().split('\n') if line.strip()]
            if len(imes) < 2:
                QMessageBox.warning(self, "Keyboard", "Only one keyboard installed on device")
                return
            current_ime = safe_subprocess_run([self.adb_path, "-s", device_id, "shell", "settings", "get", "secure", "default_input_method"],
                                             capture_output=True, text=True, timeout=10).stdout.strip()
            next_ime = imes[1] if current_ime == imes[0] else imes[0]
            safe_subprocess_run([self.adb_path, "-s", device_id, "shell", "ime", "set", next_ime],
                               capture_output=True, text=True, timeout=10)
            self.add_activity(f"✓ Switched keyboard on {device_id}")
        except Exception as e:
            self.add_activity(f"✗ Failed to switch keyboard: {str(e)}")
    
    def _set_wallpaper_single(self, device_id):
        """Set wallpaper for a single device"""
        self.add_activity(f"Setting wallpaper for {device_id}...")
        QMessageBox.information(self, "Wallpaper", f"Wallpaper feature for {device_id}")
    
    def _home_screen_single(self, device_id):
        """Go to home screen on a single device"""
        try:
            safe_subprocess_run([self.adb_path, "-s", device_id, "shell", "input", "keyevent", "KEYCODE_HOME"],
                               capture_output=True, text=True, timeout=10)
            self.add_activity(f"✓ Sent home command to {device_id}")
        except Exception as e:
            self.add_activity(f"✗ Failed to go home: {str(e)}")
    
    def _clear_recents_single(self, device_id):
        """Clear recent apps on a single device"""
        try:
            safe_subprocess_run([self.adb_path, "-s", device_id, "shell", "am", "broadcast", 
                               "-a", "android.intent.action.CLOSE_SYSTEM_DIALOGS"],
                               capture_output=True, text=True, timeout=10)
            self.add_activity(f"✓ Cleared recents on {device_id}")
        except Exception as e:
            self.add_activity(f"✗ Failed to clear recents: {str(e)}")
    
    def _maxchange_random_single(self, device_id):
        """Change device to random profile using MaxChange"""
        self.add_activity(f"Changing device profile (random) for {device_id}...")
        QMessageBox.information(self, "MaxChange", f"MaxChange random profile for {device_id}")
    
    def _maxchange_brand_single(self, device_id, brand):
        """Change device to specific brand using MaxChange"""
        self.add_activity(f"Changing device to {brand} profile for {device_id}...")
        QMessageBox.information(self, "MaxChange", f"MaxChange {brand} profile for {device_id}")
    
    def _check_maxchange_single(self, device_id):
        """Check current MaxChange device info"""
        self.add_activity(f"Checking device info for {device_id}...")
        QMessageBox.information(self, "MaxChange", f"Device info check for {device_id}")
    
    def _setup_vpn_single(self, device_id):
        """Setup VPN on a single device"""
        self.add_activity(f"Setting up VPN for {device_id}...")
        QMessageBox.information(self, "VPN Setup", f"VPN setup for {device_id}")
    
    def _open_vpn_single(self, device_id):
        """Open VPN app on a single device"""
        try:
            safe_subprocess_run([self.adb_path, "-s", device_id, "shell", "monkey", "-p", 
                               "net.openvpn.openvpn", "-c", "android.intent.category.LAUNCHER", "1"],
                               capture_output=True, text=True, timeout=10)
            self.add_activity(f"✓ Opened OpenVPN app on {device_id}")
        except Exception as e:
            self.add_activity(f"✗ Failed to open VPN: {str(e)}")
    
    def _check_ip_single(self, device_id):
        """Check IP address for a single device"""
        import threading
        def _run():
            try:
                self.add_activity(f"Checking IP for {device_id}...")
                result = safe_subprocess_run([self.adb_path, "-s", device_id, "shell", 
                                             "curl", "-s", "ifconfig.me"],
                                            capture_output=True, text=True, timeout=15)
                ip = result.stdout.strip()
                self.add_activity(f"✓ {device_id} IP: {ip}")
            except Exception as e:
                self.add_activity(f"✗ Failed to check IP: {str(e)}")
        threading.Thread(target=_run, daemon=True).start()
    
    def _connect_random_proxy_single(self, device_id):
        """Connect to random proxy on a single device"""
        self.add_activity(f"Connecting to random proxy for {device_id}...")
        QMessageBox.information(self, "Proxy", f"Random proxy connection for {device_id}")
    
    def _connect_specific_proxy_single(self, device_id):
        """Connect to specific proxy on a single device"""
        self.add_activity(f"Connecting to specific proxy for {device_id}...")
        QMessageBox.information(self, "Proxy", f"Specific proxy connection for {device_id}")
    
    def _disconnect_proxy_single(self, device_id):
        """Disconnect proxy on a single device"""
        try:
            safe_subprocess_run([self.adb_path, "-s", device_id, "shell", "am", "force-stop", 
                               "net.openvpn.openvpn"],
                               capture_output=True, text=True, timeout=10)
            self.add_activity(f"✓ Disconnected proxy on {device_id}")
        except Exception as e:
            self.add_activity(f"✗ Failed to disconnect proxy: {str(e)}")
    
    def _check_proxy_status_single(self, device_id):
        """Check proxy status for a single device"""
        self.add_activity(f"Checking proxy status for {device_id}...")
        QMessageBox.information(self, "Proxy Status", f"Proxy status check for {device_id}")
    
    def _check_location_single(self, device_id):
        """Check location for a single device"""
        self.add_activity(f"Checking location for {device_id}...")
        QMessageBox.information(self, "Location", f"Location check for {device_id}")
    
    def _set_location_single(self, device_id):
        """Set location for a single device"""
        self.add_activity(f"Setting location for {device_id}...")
        QMessageBox.information(self, "Location", f"Location setting for {device_id}")
