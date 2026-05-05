"""
License Manager with Supabase Integration
Handles license validation, activation, and management.
"""

import os
import json
import hashlib
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple
import requests


class LicenseManager:
    """Manages license validation and activation with Supabase backend."""
    
    def __init__(self, supabase_url: str, supabase_key: str):
        """
        Initialize License Manager.
        
        Args:
            supabase_url: Your Supabase project URL
            supabase_key: Your Supabase anon/public key
        """
        self.supabase_url = supabase_url.rstrip('/')
        self.supabase_key = supabase_key
        self.headers = {
            'apikey': supabase_key,
            'Authorization': f'Bearer {supabase_key}',
            'Content-Type': 'application/json',
            'Prefer': 'return=representation'
        }
        
        # Local license cache file
        self.license_file = os.path.join(
            os.path.expanduser('~'),
            '.frt_license.json'
        )
        
        # Generate unique machine ID
        self.machine_id = self._get_machine_id()
    
    def _get_machine_id(self) -> str:
        """Generate a unique machine identifier."""
        try:
            # Use MAC address + hostname for unique ID
            import platform
            import socket
            
            mac = ':'.join(['{:02x}'.format((uuid.getnode() >> elements) & 0xff)
                           for elements in range(0, 2*6, 2)][::-1])
            hostname = socket.gethostname()
            system = platform.system()
            
            # Create hash of machine info
            machine_string = f"{mac}-{hostname}-{system}"
            machine_hash = hashlib.sha256(machine_string.encode()).hexdigest()
            
            return machine_hash[:16].upper()
        except Exception:
            # Fallback to UUID if above fails
            return str(uuid.uuid4())[:16].upper()
    
    def _save_license_locally(self, license_data: Dict) -> None:
        """Save license data to local cache."""
        try:
            with open(self.license_file, 'w', encoding='utf-8') as f:
                json.dump(license_data, f, indent=2)
        except Exception as e:
            print(f"Failed to save license locally: {e}")
    
    def _load_license_locally(self) -> Optional[Dict]:
        """Load license data from local cache."""
        try:
            if os.path.exists(self.license_file):
                with open(self.license_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Failed to load local license: {e}")
        return None

    def _save_denied_state(self, message: str, license_key: str) -> None:
        """Save denied state with license key for future checks."""
        try:
            denied_file = os.path.join(os.path.expanduser('~'), '.frt_denied.json')
            with open(denied_file, 'w', encoding='utf-8') as f:
                json.dump({'message': message, 'license_key': license_key}, f)
        except Exception:
            pass
    
    def activate_license(self, license_key: str, user_name: str = "User") -> Tuple[bool, str, Optional[Dict]]:
        try:
            # Clear any denied state when user attempts activation
            denied_file = os.path.join(os.path.expanduser('~'), '.frt_denied.json')
            if os.path.exists(denied_file):
                try:
                    os.remove(denied_file)
                except Exception:
                    pass
            if not license_key or len(license_key) < 10:
                return False, "Invalid license key format", None

            url = f"{self.supabase_url}/rest/v1/licenses"
            params = {'license_key': f'eq.{license_key}', 'select': '*'}
            response = requests.get(url, headers=self.headers, params=params, timeout=10)

            if response.status_code != 200:
                return False, f"Failed to verify license: {response.status_code}", None

            licenses = response.json()
            if not licenses:
                return False, "Invalid license key", None

            license_data = licenses[0]

            # Check if already activated on another machine
            if license_data.get('is_activated') and license_data.get('machine_id') != self.machine_id:
                return False, "License key is already activated on another machine", None

            # Check expiration
            expiry_date = datetime.fromisoformat(license_data['expiry_date'].replace('Z', '+00:00'))
            if datetime.now(expiry_date.tzinfo) > expiry_date:
                return False, "License key has expired", None

            # Check if active
            if not license_data.get('is_active', True):
                return False, "License key has been deactivated", None

            # Check if this machine is banned
            try:
                ban_resp = requests.get(
                    f"{self.supabase_url}/rest/v1/users",
                    headers=self.headers,
                    params={'app_id': f'eq.{self.machine_id}', 'select': 'status,ban_reason'},
                    timeout=8
                )
                if ban_resp.status_code == 200 and ban_resp.json():
                    user = ban_resp.json()[0]
                    if user.get('status') == 'banned':
                        reason = user.get('ban_reason') or 'No reason provided'
                        return False, f"Your account has been banned.\nReason: {reason}", None
            except Exception:
                pass

            # Activate
            update_data = {
                'is_activated': True,
                'machine_id': self.machine_id,
                'activated_at': datetime.utcnow().isoformat(),
                'last_validated': datetime.utcnow().isoformat()
            }
            update_url = f"{self.supabase_url}/rest/v1/licenses"
            update_params = {'license_key': f'eq.{license_key}'}
            update_response = requests.patch(update_url, headers=self.headers, params=update_params, json=update_data, timeout=10)

            if update_response.status_code not in [200, 201, 204]:
                return False, f"Failed to activate license: {update_response.status_code}", None

            # Write to activations table
            try:
                import socket
                activation_data = {
                    'license_key': license_key,
                    'machine_hash': self.machine_id,
                    'app_id': self.machine_id,
                    'activated_at': datetime.utcnow().isoformat(),
                    'ip': None,
                    'app_version': '1.1.0'
                }
                requests.post(
                    f"{self.supabase_url}/rest/v1/activations",
                    headers=self.headers,
                    json=activation_data,
                    timeout=5
                )
            except Exception:
                pass

            # Write to users table - only if not banned
            try:
                # Check current status first
                existing = requests.get(
                    f"{self.supabase_url}/rest/v1/users",
                    headers=self.headers,
                    params={'app_id': f'eq.{self.machine_id}', 'select': 'status'},
                    timeout=5
                )
                current_status = None
                if existing.status_code == 200 and existing.json():
                    current_status = existing.json()[0].get('status')

                # Never overwrite banned status
                if current_status != 'banned':
                    user_data = {
                        'app_id': self.machine_id,
                        'license_key': license_key,
                        'status': 'active',
                        'first_seen': datetime.utcnow().isoformat(),
                        'last_seen': datetime.utcnow().isoformat(),
                        'total_visits': 1,
                        'failed_attempts': 0
                    }
                    upsert_headers = {**self.headers, 'Prefer': 'resolution=merge-duplicates'}
                    requests.post(
                        f"{self.supabase_url}/rest/v1/users",
                        headers=upsert_headers,
                        json=user_data,
                        timeout=5
                    )
            except Exception:
                pass

            # Write to activity_logs
            try:
                log_data = {
                    'action': 'license_activated',
                    'license_key': license_key,
                    'app_id': self.machine_id,
                    'details': f'License activated on machine {self.machine_id}',
                    'timestamp': datetime.utcnow().isoformat()
                }
                requests.post(
                    f"{self.supabase_url}/rest/v1/activity_logs",
                    headers=self.headers,
                    json=log_data,
                    timeout=5
                )
            except Exception:
                pass

            local_data = {
                'license_key': license_key,
                'machine_id': self.machine_id,
                'user_name': license_data.get('user_name') or user_name,
                'expiry_date': license_data['expiry_date'],
                'license_type': license_data.get('license_type', 'Professional'),
                'activated_at': update_data['activated_at'],
                'tool_id': license_data.get('tool_id', '')
            }
            self._save_license_locally(local_data)
            return True, "License activated successfully!", local_data

        except requests.exceptions.RequestException as e:
            return False, f"Network error: {str(e)}", None
        except Exception as e:
            return False, f"Activation failed: {str(e)}", None
    
    def check_license_status(self) -> Tuple[bool, str]:
        """Quick online check - only checks is_active and expiry. Used by watchdog."""
        local_license = self._load_license_locally()
        if not local_license:
            return False, "No license found"
        
        license_key = local_license.get('license_key')
        try:
            # Check license is_active
            url = f"{self.supabase_url}/rest/v1/licenses"
            params = {
                'license_key': f'eq.{license_key}',
                'select': 'is_active,expiry_date'
            }
            response = requests.get(url, headers=self.headers, params=params, timeout=8)
            if response.status_code != 200:
                return True, "Network error - skipping"
            licenses = response.json()
            if not licenses:
                return False, "License not found"
            data = licenses[0]
            if not data.get('is_active', True):
                msg = "License has been deactivated by administrator"
                self._save_denied_state(msg, license_key)
                if os.path.exists(self.license_file):
                    os.remove(self.license_file)
                return False, msg
            expiry = datetime.fromisoformat(data['expiry_date'].replace('Z', '+00:00'))
            if datetime.now(expiry.tzinfo) > expiry:
                if os.path.exists(self.license_file):
                    os.remove(self.license_file)
                return False, "License has expired"

            # Check if user is banned in users table
            user_resp = requests.get(
                f"{self.supabase_url}/rest/v1/users",
                headers=self.headers,
                params={
                    'app_id': f'eq.{self.machine_id}',
                    'select': 'status,ban_reason'
                },
                timeout=8
            )
            if user_resp.status_code == 200 and user_resp.json():
                user = user_resp.json()[0]
                if user.get('status') == 'banned':
                    reason = user.get('ban_reason') or 'No reason provided'
                    msg = f"Your account has been banned.\nReason: {reason}"
                    self._save_denied_state(msg, license_key)
                    if os.path.exists(self.license_file):
                        os.remove(self.license_file)
                    return False, msg

            return True, "Valid"
        except requests.exceptions.RequestException:
            return True, "Network error - skipping"
        except Exception as e:
            return True, f"Check error: {e}"

    def validate_license(self, offline_mode: bool = False) -> Tuple[bool, str, Optional[Dict]]:
        """Simple, professional license validation - always checks server first."""
        denied_file = os.path.join(os.path.expanduser('~'), '.frt_denied.json')
        local_license = self._load_license_locally()
        
        # Get license key from local cache or denied file
        license_key = None
        if local_license:
            license_key = local_license.get('license_key')
        elif os.path.exists(denied_file):
            try:
                with open(denied_file, 'r', encoding='utf-8') as f:
                    license_key = json.load(f).get('license_key')
            except:
                pass
        
        if not license_key:
            return False, "No license found. Please activate a license key.", None
        
        # ALWAYS check server first (real-time validation) - FAST timeout
        if not offline_mode:
            try:
                response = requests.get(
                    f"{self.supabase_url}/rest/v1/licenses",
                    headers=self.headers,
                    params={'license_key': f'eq.{license_key}', 'select': '*'},
                    timeout=2  # Reduced from 5 to 2 seconds
                )
                
                if response.status_code == 200:
                    licenses = response.json()
                    
                    # License key deleted from database - clear all local files
                    if not licenses:
                        if os.path.exists(self.license_file):
                            os.remove(self.license_file)
                        if os.path.exists(denied_file):
                            os.remove(denied_file)
                        return False, "No license found. Please activate a license key.", None
                    
                    lic = licenses[0]
                    
                    # Check if disabled
                    if not lic.get('is_active', False):
                        msg = "License has been deactivated by administrator"
                        self._save_denied_state(msg, license_key)
                        if os.path.exists(self.license_file):
                            os.remove(self.license_file)
                        return False, msg, None
                    
                    # Check machine_id
                    if lic.get('machine_id') and lic.get('machine_id') != self.machine_id:
                        return False, "License not found or machine mismatch", None
                    
                    # Check expiry
                    try:
                        expiry = datetime.fromisoformat(lic['expiry_date'].replace('Z', '+00:00'))
                        if datetime.now(expiry.tzinfo) > expiry:
                            return False, "License has expired", None
                    except:
                        pass
                    
                    # Check ban status - SKIP on startup for speed, watchdog will catch it
                    # Only check if we have time
                    
                    # License is ACTIVE - clear denied state and restore cache
                    if os.path.exists(denied_file):
                        os.remove(denied_file)
                    
                    restored = {
                        'license_key': license_key,
                        'machine_id': self.machine_id,
                        'expiry_date': lic['expiry_date'],
                        'license_type': lic.get('license_type', 'Professional'),
                        'user_name': lic.get('user_name', 'User'),
                        'activated_at': local_license.get('activated_at') if local_license else datetime.utcnow().isoformat(),
                    }
                    self._save_license_locally(restored)
                    
                    # Background updates - don't wait
                    def _bg():
                        try:
                            requests.patch(
                                f"{self.supabase_url}/rest/v1/licenses",
                                headers=self.headers,
                                params={'license_key': f'eq.{license_key}'},
                                json={'last_validated': datetime.utcnow().isoformat()},
                                timeout=3
                            )
                            # Check ban status in background
                            ban_resp = requests.get(
                                f"{self.supabase_url}/rest/v1/users",
                                headers=self.headers,
                                params={'app_id': f'eq.{self.machine_id}', 'select': 'status,ban_reason'},
                                timeout=3
                            )
                            if ban_resp.status_code == 200 and ban_resp.json():
                                user = ban_resp.json()[0]
                                if user.get('status') == 'banned':
                                    reason = user.get('ban_reason') or 'No reason provided'
                                    msg = f"Your account has been banned.\nReason: {reason}"
                                    self._save_denied_state(msg, license_key)
                                    if os.path.exists(self.license_file):
                                        os.remove(self.license_file)
                        except:
                            pass
                    import threading
                    threading.Thread(target=_bg, daemon=True).start()
                    
                    return True, "License valid", restored
                    
            except requests.exceptions.RequestException:
                # Network error - use local cache if valid
                if local_license:
                    try:
                        expiry = datetime.fromisoformat(local_license['expiry_date'].replace('Z', '+00:00'))
                        if datetime.now(expiry.tzinfo) <= expiry:
                            return True, "License valid (offline)", local_license
                    except:
                        pass
                return False, "Cannot connect to license server. Internet connection required.", None
        
        # Offline mode
        if local_license:
            return True, "License valid (offline mode)", local_license
        return False, "No license found", None
    
    def deactivate_license(self) -> Tuple[bool, str]:
        """Deactivate the current license on this machine."""
        local_license = self._load_license_locally()
        
        if not local_license:
            return False, "No license found"
        
        try:
            # Deactivate in Supabase
            url = f"{self.supabase_url}/rest/v1/licenses"
            params = {
                'license_key': f'eq.{local_license["license_key"]}',
                'machine_id': f'eq.{self.machine_id}'
            }
            
            update_data = {
                'is_activated': False,
                'machine_id': None,
                'deactivated_at': datetime.utcnow().isoformat()
            }
            
            response = requests.patch(
                url,
                headers=self.headers,
                params=params,
                json=update_data,
                timeout=10
            )
            
            # Remove local license file
            if os.path.exists(self.license_file):
                os.remove(self.license_file)
            
            if response.status_code in [200, 201, 204]:
                return True, "License deactivated successfully"
            else:
                return False, f"Failed to deactivate: {response.status_code}"
                
        except Exception as e:
            return False, f"Deactivation failed: {str(e)}"
    
    def get_license_info(self) -> Optional[Dict]:
        """Get current license information."""
        return self._load_license_locally()
    
    def get_machine_id(self) -> str:
        """Get the current machine ID."""
        return self.machine_id
