"""
Fix the offline device and improve USB connection for SM-J730F devices
"""
import subprocess
import time

ADB_PATH = "platform-tools/platform-tools/adb.exe"
PROBLEM_DEVICES = ["52000a02ee736459", "52001cefc039c401"]

def run_cmd(cmd):
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10, shell=True)
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)

print("🔧 Fixing Offline Device & Improving USB Connection")
print("=" * 70)

# Step 1: Check current status
print("\n1️⃣ Checking current device status...")
success, out, err = run_cmd(f'"{ADB_PATH}" devices')
print(out)

# Step 2: Kill and restart ADB server
print("\n2️⃣ Restarting ADB server...")
run_cmd(f'"{ADB_PATH}" kill-server')
time.sleep(3)
run_cmd(f'"{ADB_PATH}" start-server')
time.sleep(3)
print("   ✓ ADB server restarted")

# Step 3: Check status again
print("\n3️⃣ Checking device status after restart...")
success, out, err = run_cmd(f'"{ADB_PATH}" devices')
print(out)

# Step 4: Try to reconnect offline devices
print("\n4️⃣ Attempting to reconnect devices...")
for device_id in PROBLEM_DEVICES:
    print(f"\n   Reconnecting {device_id}...")
    run_cmd(f'"{ADB_PATH}" -s {device_id} reconnect')
    time.sleep(2)

# Step 5: Final status check
print("\n5️⃣ Final device status:")
success, out, err = run_cmd(f'"{ADB_PATH}" devices')
print(out)

# Step 6: Recommendations
print("\n" + "=" * 70)
print("📋 RECOMMENDATIONS:")
print("=" * 70)
print("""
If device is still OFFLINE:
1. Physically unplug and replug the USB cable
2. Try a different USB port (preferably USB 3.0)
3. Use a shorter, higher quality USB cable
4. Check if device screen shows "USB debugging" prompt
5. On device: Settings → Developer Options → Revoke USB debugging
   Then reconnect and re-authorize

If device is ONLINE but still can't cast:
1. The SM-J730F variant has hardware limitations
2. Try: python try_tcpip_casting.py
3. Or use alternative mirroring (Vysor, TeamViewer)
4. Or work with the 17 devices that can cast

USB Hub Tips:
- Don't connect more than 7 devices per USB hub
- Use powered USB hubs
- Connect F variant devices to dedicated ports
- Reduce total number of connected devices
""")
