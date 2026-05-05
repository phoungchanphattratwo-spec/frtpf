"""
Auto-Update Checker
Checks for new versions from GitHub
"""

import requests
import json
from typing import Tuple, Optional, Dict
from packaging import version as pkg_version

VERSION_URL = "https://raw.githubusercontent.com/phoungchanphattratwo-spec/frtpf/main/version.json"
CURRENT_VERSION = "1.1.0"

class UpdateChecker:
    """Checks for application updates"""
    
    def __init__(self, current_version: str = CURRENT_VERSION):
        self.current_version = current_version
        self.version_url = VERSION_URL
    
    def check_for_updates(self, timeout: int = 5) -> Tuple[bool, Optional[Dict]]:
        """
        Check if a new version is available.
        
        Returns:
            (has_update, update_info) where update_info contains version details
        """
        try:
            response = requests.get(self.version_url, timeout=timeout)
            
            if response.status_code != 200:
                return False, None
            
            update_info = response.json()
            latest_version = update_info.get('version', '0.0.0')
            
            # Compare versions
            if pkg_version.parse(latest_version) > pkg_version.parse(self.current_version):
                return True, update_info
            
            return False, None
            
        except requests.exceptions.RequestException:
            # Network error - silently fail
            return False, None
        except Exception:
            # Any other error - silently fail
            return False, None
    
    def is_force_update(self) -> bool:
        """Check if update is mandatory"""
        try:
            response = requests.get(self.version_url, timeout=3)
            if response.status_code == 200:
                data = response.json()
                return data.get('force_update', False)
        except:
            pass
        return False
    
    def get_update_info(self) -> Optional[Dict]:
        """Get latest version information"""
        try:
            response = requests.get(self.version_url, timeout=5)
            if response.status_code == 200:
                return response.json()
        except:
            pass
        return None
