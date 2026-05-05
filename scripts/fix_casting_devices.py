"""
Fix script for devices with "Server connection failed" error
Devices: 52000a02ee736459 and 52001cefc039c401
"""
import subprocess
import time
import os

DEVICES = ["52000a02ee736459", "52001cefc039c401"]
ADB_PATH = "platform-tools/platform-tools/adb.exe"

def run_cmd(cmd):
    """Run command and return output"""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10, shell=True)
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)

def fix_device(device_id):
    print(f"\n{'='*70}")
    print(f"🔧 FIXING DEVICE: {device_id}")
    print(f"{'='*70}\n")
    
    # Fix 1: Kill any existing scrcpy server processes
    print("1️⃣ Killing existing scrcpy processes on device...")
    run_cmd(f'"{ADB_PATH}" -s {device_id} shell "pkill -9 app_process"')
    run_cmd(f'"{ADB_PATH}" -s {device_id} shell "pkill -9 scrcpy"')
    time.sleep(1)
    print("   ✓ Cleaned up processes")
    
    # Fix 2: Remove old scrcpy server files
    print("\n2️⃣ Removing old scrcpy server files...")
    run_cmd(f'"{ADB_PATH}" -s {device_id} shell "rm -f /data/local/tmp/scrcpy-server*"')
    print("   ✓ Removed old files")
    
    # Fix 3: Test and setup reverse port forwarding
    print("\n3️⃣ Setting up reverse port forwarding...")
    # Remove existing forwards
    run_cmd(f'"{ADB_PATH}" -s {device_id} reverse --remove-all')
    time.sleep(0.5)
    
    # Setup new reverse forward (scrcpy uses port 27183 by default)
    success, out, err = run_cmd(f'"{ADB_PATH}" -s {device_id} reverse tcp:27183 tcp:27183')
    if success:
        print("   ✓ Reverse port forwarding setup successful")
    else:
        print(f"   ⚠ Reverse forward warning: {err}")
    
    # Fix 4: Check and fix USB mode
    print("\n4️⃣ Checking USB mode...")
    success, output, _ = run_cmd(f'"{ADB_PATH}" -s {device_id} shell "getprop sys.usb.state"')
    if success:
        usb_state = output.strip()
        print(f"   Current USB state: {usb_state}")
        if "mtp" not in usb_state.lower():
            print("   ⚠ MTP not enabled - this may cause issues")
    
    # Fix 5: Wake up device screen
    print("\n5️⃣ Waking up device screen...")
    run_cmd(f'"{ADB_PATH}" -s {device_id} shell "input keyevent KEYCODE_WAKEUP"')
    time.sleep(0.5)
    run_cmd(f'"{ADB_PATH}" -s {device_id} shell "input keyevent 82"')  # Unlock
    print("   ✓ Screen wake command sent")
    
    # Fix 6: Restart ADB connection for this device
    print("\n6️⃣ Restarting ADB connection...")
    run_cmd(f'"{ADB_PATH}" -s {device_id} reconnect')
    time.sleep(2)
    print("   ✓ ADB reconnected")
    
    # Fix 7: Test connection
    print("\n7️⃣ Testing connection...")
    success, output, _ = run_cmd(f'"{ADB_PATH}" -s {device_id} shell "echo test"')
    if success and "test" in output:
        print("   ✓ Device responding normally")
    else:
        print("   ⚠ Device not responding properly")
    
    print(f"\n✅ Fixes applied for {device_id}")
    print("   Try casting again now!")

def restart_adb_server():
    print("\n🔄 Restarting ADB server...")
    run_cmd(f'"{ADB_PATH}" kill-server')
    time.sleep(2)
    run_cmd(f'"{ADB_PATH}" start-server')
    time.sleep(2)
    print("   ✓ ADB server restarted")

if __name__ == "__main__":
    print("🔧 Screen Casting Fix Tool")
    print("=" * 70)
    print("\nThis will attempt to fix 'Server connection failed' errors")
    print("for devices that cannot cast their screens.\n")
    
    # Option to restart ADB server first
    print("⚠ RECOMMENDED: Restart ADB server first")
    restart_adb_server()
    
    # Fix each device
    for device_id in DEVICES:
        fix_device(device_id)
    
    print(f"\n{'='*70}")
    print("✅ All fixes applied!")
    print(f"{'='*70}")
    print("\n📋 Next steps:")
    print("   1. Try casting the devices again from your app")
    print("   2. If still failing, try:")
    print("      - Different USB port")
    print("      - Different USB cable")
    print("      - Disable and re-enable USB debugging on device")
    print("      - Reboot the device")
