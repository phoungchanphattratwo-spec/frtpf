"""
Quick diagnostic script for devices that can't cast screens
Run this to check devices: 52000a02ee736459 and 52001cefc039c401
"""
import subprocess
import sys
import os

# Device IDs from the image
PROBLEM_DEVICES = [
    "52000a02ee736459",
    "52001cefc039c401"
]

# Find ADB path
ADB_PATH = "platform-tools/platform-tools/adb.exe"
if not os.path.exists(ADB_PATH):
    ADB_PATH = "adb"

def run_cmd(cmd, timeout=10):
    """Run command and return output"""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, shell=True)
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", "Timeout"
    except Exception as e:
        return False, "", str(e)

def diagnose_device(device_id):
    """Run diagnostics on a specific device"""
    print(f"\n{'='*70}")
    print(f"🔍 DIAGNOSING DEVICE: {device_id}")
    print(f"{'='*70}\n")
    
    # 1. Check if device is connected
    print("1️⃣ Checking device connection...")
    success, output, error = run_cmd(f'"{ADB_PATH}" devices')
    if device_id in output:
        print(f"   ✓ Device {device_id} is connected")
        # Check if it's authorized
        if "unauthorized" in output:
            print(f"   ❌ Device is UNAUTHORIZED - check device screen for prompt")
            return
    else:
        print(f"   ❌ Device {device_id} is NOT connected")
        print(f"   Available devices:\n{output}")
        return
    
    # 2. Check device state
    print("\n2️⃣ Checking device state...")
    success, output, error = run_cmd(f'"{ADB_PATH}" -s {device_id} get-state')
    print(f"   State: {output.strip() if success else error}")
    
    # 3. Check device model
    print("\n3️⃣ Checking device info...")
    success, output, error = run_cmd(f'"{ADB_PATH}" -s {device_id} shell "getprop ro.product.model"')
    model = output.strip() if success else "Unknown"
    print(f"   Model: {model}")
    
    success, output, error = run_cmd(f'"{ADB_PATH}" -s {device_id} shell "getprop ro.build.version.release"')
    android_ver = output.strip() if success else "Unknown"
    print(f"   Android: {android_ver}")
    
    # 4. Check screen state
    print("\n4️⃣ Checking screen state...")
    success, output, error = run_cmd(f'"{ADB_PATH}" -s {device_id} shell "dumpsys power | grep mScreenOn"')
    if success:
        if "true" in output.lower():
            print(f"   ✓ Screen is ON")
        else:
            print(f"   ⚠ Screen is OFF - this may prevent casting")
    
    # 5. Test file push (scrcpy needs this)
    print("\n5️⃣ Testing file push capability...")
    success, output, error = run_cmd(f'"{ADB_PATH}" -s {device_id} shell "echo test > /data/local/tmp/test.txt"')
    if success:
        print(f"   ✓ Can write to /data/local/tmp")
        run_cmd(f'"{ADB_PATH}" -s {device_id} shell "rm /data/local/tmp/test.txt"')
    else:
        print(f"   ❌ Cannot write to /data/local/tmp: {error}")
    
    # 6. Check storage space
    print("\n6️⃣ Checking storage space...")
    success, output, error = run_cmd(f'"{ADB_PATH}" -s {device_id} shell "df /data/local/tmp"')
    if success:
        print(f"   {output.strip()}")
    
    # 7. Check for existing scrcpy processes
    print("\n7️⃣ Checking for running scrcpy processes...")
    success, output, error = run_cmd(f'"{ADB_PATH}" -s {device_id} shell "ps | grep scrcpy"')
    if output.strip():
        print(f"   ⚠ Found running scrcpy process:\n   {output.strip()}")
    else:
        print(f"   ✓ No scrcpy processes running")
    
    # 8. Test shell response time
    print("\n8️⃣ Testing ADB response time...")
    import time
    start = time.time()
    success, output, error = run_cmd(f'"{ADB_PATH}" -s {device_id} shell "echo test"', timeout=5)
    elapsed = time.time() - start
    if success:
        print(f"   ✓ Response time: {elapsed:.2f}s")
        if elapsed > 2:
            print(f"   ⚠ Slow response - USB connection may be unstable")
    else:
        print(f"   ❌ Shell command failed: {error}")
    
    # 9. Check USB state
    print("\n9️⃣ Checking USB connection state...")
    success, output, error = run_cmd(f'"{ADB_PATH}" -s {device_id} shell "getprop sys.usb.state"')
    if success:
        print(f"   USB State: {output.strip()}")
    
    # 10. Check SELinux
    print("\n🔟 Checking SELinux status...")
    success, output, error = run_cmd(f'"{ADB_PATH}" -s {device_id} shell "getenforce"')
    if success:
        selinux = output.strip()
        print(f"   SELinux: {selinux}")
        if selinux == "Enforcing":
            print(f"   ⚠ SELinux is enforcing - may block some operations")
    
    # Summary
    print(f"\n{'='*70}")
    print(f"📋 SUMMARY FOR {device_id}")
    print(f"{'='*70}")
    print(f"Model: {model}")
    print(f"Android: {android_ver}")
    print(f"\n💡 Common fixes:")
    print(f"   1. Reconnect USB cable (try different port)")
    print(f"   2. Revoke USB debugging authorization and re-accept")
    print(f"   3. Wake up device screen")
    print(f"   4. Restart ADB: adb kill-server && adb start-server")
    print(f"   5. Try different USB cable (must be data cable)")

if __name__ == "__main__":
    print("🔍 Screen Casting Diagnostic Tool")
    print("=" * 70)
    
    # Check if ADB exists
    if not os.path.exists(ADB_PATH) and not subprocess.run(["where", "adb"], capture_output=True).returncode == 0:
        print("❌ ADB not found! Please check ADB path.")
        sys.exit(1)
    
    print(f"Using ADB: {ADB_PATH}\n")
    
    # List all connected devices first
    print("📱 Connected devices:")
    success, output, error = run_cmd(f'"{ADB_PATH}" devices')
    print(output)
    
    # Diagnose each problem device
    for device_id in PROBLEM_DEVICES:
        diagnose_device(device_id)
    
    print(f"\n{'='*70}")
    print("✓ Diagnostics complete!")
    print(f"{'='*70}")
