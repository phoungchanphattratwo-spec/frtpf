lines = open('gui.py', encoding='utf-8').readlines()

# New clean content to replace lines 12745-12870 (indices 12744-12869)
new_content = '''    def _maxchange_random_single(self, device_id):
        """Change device to random profile using the real device changer"""
        import threading
        def _run():
            try:
                self.add_activity(f"Changing device profile (random) for {device_id}...")
                fake_info = self.generate_fake_device_info()
                self._apply_real_device_changes(device_id, fake_info)
                self.add_activity(f"\\u2713 Device changed: {fake_info.get('model', 'Unknown')} on {device_id}")
            except Exception as e:
                self.add_activity(f"\\u2717 Device change failed: {str(e)}")
        threading.Thread(target=_run, daemon=True).start()

    def _maxchange_brand_single(self, device_id, brand):
        """Change device to specific brand profile"""
        import threading
        def _run():
            try:
                self.add_activity(f"Changing device to {brand} profile for {device_id}...")
                fake_info = self.generate_fake_device_info()
                for _ in range(20):
                    info = self.generate_fake_device_info()
                    if brand.lower() in info.get('manufacturer', '').lower():
                        fake_info = info
                        break
                self._apply_real_device_changes(device_id, fake_info)
                self.add_activity(f"\\u2713 {brand} profile applied: {fake_info.get('model', 'Unknown')} on {device_id}")
            except Exception as e:
                self.add_activity(f"\\u2717 Failed: {str(e)}")
        threading.Thread(target=_run, daemon=True).start()

    def _check_maxchange_single(self, device_id):
        """Check current device info"""
        import threading
        def _run():
            try:
                info = self._get_current_device_info(device_id)
                model = info.get('model', 'Unknown')
                manufacturer = info.get('manufacturer', 'Unknown')
                android_id = info.get('android_id', 'Unknown')
                self.add_activity(f"Device {device_id}: {manufacturer} {model} | ID: {android_id}")
            except Exception as e:
                self.add_activity(f"\\u2717 Check failed: {str(e)}")
        threading.Thread(target=_run, daemon=True).start()

    def _setup_vpn_single(self, device_id):
        """Setup VPN on a single device"""
        self.add_activity(f"Setting up VPN for {device_id}...")

    def _open_vpn_single(self, device_id):
        """Open VPN app on a single device"""
        import threading
        def _run():
            try:
                check_result = safe_subprocess_run([self.adb_path, "-s", device_id, "shell",
                    "pm list packages | grep vpn"], capture_output=True, text=True)
                vpn_packages = check_result.stdout.strip()
                if not vpn_packages:
                    self.add_activity(f"\\u26a0 No VPN packages found on {device_id}")
                    return
            except Exception as e:
                self.add_activity(f"\\u2717 Error checking packages: {str(e)}")
                return
            self._temp_single_device = [device_id]
            self._open_vpn_app()
        threading.Thread(target=_run, daemon=True).start()

    def _check_ip_single(self, device_id):
        """Check IP for a single device"""
        import threading
        def _run():
            self._temp_single_device = [device_id]
            self._check_ip()
        threading.Thread(target=_run, daemon=True).start()

    def _connect_random_proxy_single(self, device_id):
        """Connect random proxy for a single device"""
        import threading
        def _run():
            self._temp_single_device = [device_id]
            self._connect_random_proxy()
        threading.Thread(target=_run, daemon=True).start()

    def _connect_specific_proxy_single(self, device_id):
        """Connect specific proxy for a single device"""
        import threading
        def _run():
            self._temp_single_device = [device_id]
            self._connect_specific_proxy()
        threading.Thread(target=_run, daemon=True).start()

    def _disconnect_proxy_single(self, device_id):
        """Disconnect proxy on a single device"""
        try:
            safe_subprocess_run([self.adb_path, "-s", device_id, "shell", "am", "force-stop",
                               "net.openvpn.openvpn"], capture_output=True, text=True, timeout=10)
            self.add_activity(f"\\u2713 Disconnected proxy on {device_id}")
        except Exception as e:
            self.add_activity(f"\\u2717 Failed to disconnect proxy: {str(e)}")

    def _check_proxy_status_single(self, device_id):
        """Check proxy status for a single device"""
        self.add_activity(f"Checking proxy status for {device_id}...")

    def _check_location_single(self, device_id):
        """Check location for a single device"""
        self.add_activity(f"Checking location for {device_id}...")

    def _set_location_single(self, device_id):
        """Set location for a single device"""
        self.add_activity(f"Setting location for {device_id}...")

'''

# Replace lines 12745 to 12870 (0-indexed: 12744 to 12869)
new_lines = lines[:12744] + [new_content] + lines[12870:]
open('gui.py', 'w', encoding='utf-8').writelines(new_lines)
print('Done')
