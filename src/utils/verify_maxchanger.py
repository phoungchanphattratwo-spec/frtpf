"""
Verify MaxChanger installation and hook status
"""

import os
import sys
from src.core.subprocess_utils import safe_subprocess_run


def verify_maxchanger(adb_path, device_id):
    """
    Verify MaxChanger is installed and hook is active
    Returns: (success: bool, message: str, details: dict)
    """
    
    def adb(*args, timeout=10):
        return safe_subprocess_run(
            [adb_path, "-s", device_id] + list(args),
            capture_output=True, text=True, timeout=timeout
        )
    
    def shell(cmd, timeout=10):
        r = adb("shell", cmd, timeout=timeout)
        return (r.stdout + r.stderr).strip()
    
    details = {}
    issues = []
    
    # 1. Check if MaxChanger app is installed
    result = shell("pm list packages | grep maxchanger")
    if "com.minsoftware.maxchanger" in result:
        details['maxchanger_installed'] = True
    else:
        details['maxchanger_installed'] = False
        issues.append("MaxChanger app not installed")
    
    # 2. Check if LSPosed/Xposed is installed
    lsposed_check = shell("pm list packages | grep lsposed")
    xposed_check = shell("pm list packages | grep xposed")
    
    if "lsposed" in lsposed_check.lower():
        details['hook_framework'] = "LSPosed"
    elif "xposed" in xposed_check.lower():
        details['hook_framework'] = "Xposed"
    else:
        details['hook_framework'] = None
        issues.append("No hook framework (LSPosed/Xposed) detected")
    
    # 3. Check if Device.xml exists
    device_xml_check = shell('su -c "ls /data/data/com.minsoftware.maxchanger/shared_prefs/Device.xml"')
    if "Device.xml" in device_xml_check:
        details['device_xml_exists'] = True
        # Read first 200 chars to verify content
        content = shell('su -c "head -c 200 /data/data/com.minsoftware.maxchanger/shared_prefs/Device.xml"')
        details['device_xml_preview'] = content[:100]
    else:
        details['device_xml_exists'] = False
        issues.append("Device.xml not found in MaxChanger directory")
    
    # 4. Check if deviceJson.txt exists
    json_check = shell('su -c "ls /data/local/tmp/nk/deviceJson.txt"')
    if "deviceJson.txt" in json_check:
        details['device_json_exists'] = True
        # Read content
        content = shell('su -c "cat /data/local/tmp/nk/deviceJson.txt"')
        details['device_json_content'] = content[:200]
    else:
        details['device_json_exists'] = False
        issues.append("deviceJson.txt not found in /data/local/tmp/nk/")
    
    # 5. Check MaxChanger hook status (if LSPosed)
    if details.get('hook_framework') == "LSPosed":
        # Check if MaxChanger module is enabled in LSPosed
        # This requires LSPosed CLI which may not be available
        details['hook_status'] = "Unknown (requires LSPosed CLI)"
    
    # 6. Check current device properties
    brand = shell("getprop ro.product.brand")
    model = shell("getprop ro.product.model")
    details['current_brand'] = brand
    details['current_model'] = model
    
    # 7. Check if resetprop is available (Magisk)
    resetprop_check = shell("which resetprop")
    if "resetprop" in resetprop_check:
        details['resetprop_available'] = True
    else:
        details['resetprop_available'] = False
        issues.append("resetprop not available (Magisk not installed?)")
    
    # Summary
    if not issues:
        return True, "MaxChanger setup looks good", details
    else:
        return False, "; ".join(issues), details


if __name__ == "__main__":
    # Test script
    if len(sys.argv) < 3:
        print("Usage: python verify_maxchanger.py <adb_path> <device_id>")
        sys.exit(1)
    
    adb_path = sys.argv[1]
    device_id = sys.argv[2]
    
    success, message, details = verify_maxchanger(adb_path, device_id)
    
    print(f"Success: {success}")
    print(f"Message: {message}")
    print(f"\nDetails:")
    for key, value in details.items():
        print(f"  {key}: {value}")
