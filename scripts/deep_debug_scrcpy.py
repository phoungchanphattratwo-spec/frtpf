"""
Deep debug for scrcpy server connection failure
"""
import subprocess
import time
import os

DEVICE = "52000a02ee736459"  # Test with first device
ADB_PATH = "platform-tools/platform-tools/adb.exe"

def run_cmd(cmd, timeout=10):
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, shell=True)
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)

print("🔍 Deep Debug for scrcpy Server Connection")
print("=" * 70)

# Check logcat for scrcpy errors
print("\n1️⃣ Checking device logcat for scrcpy errors...")
print("   Clearing logcat...")
run_cmd(f'"{ADB_PATH}" -s {DEVICE} logcat -c')

print("   Starting scrcpy server manually...")
# Push server
run_cmd(f'"{ADB_PATH}" -s {DEVICE} push scrcpy-win64-v3.1/scrcpy-server /data/local/tmp/')

# Try to run server manually and capture output
print("   Running server and capturing output...")
success, out, err = run_cmd(
    f'"{ADB_PATH}" -s {DEVICE} shell "CLASSPATH=/data/local/tmp/scrcpy-server app_process / com.genymobile.scrcpy.Server 2.4 tunnel_forward=true control=false video_codec=h264 max_size=800"',
    timeout=5
)

print(f"\n   Server output:")
print(f"   STDOUT: {out}")
print(f"   STDERR: {err}")

# Check logcat
print("\n2️⃣ Checking logcat for errors...")
success, out, err = run_cmd(f'"{ADB_PATH}" -s {DEVICE} logcat -d -s scrcpy:* *:E', timeout=5)
if out:
    print(f"   Logcat output:\n{out}")
else:
    print("   No scrcpy logs found")

# Check if port is listening
print("\n3️⃣ Checking if scrcpy server is listening on port...")
success, out, err = run_cmd(f'"{ADB_PATH}" -s {DEVICE} shell "netstat -an | grep 27183"')
if out:
    print(f"   ✓ Port 27183 status:\n{out}")
else:
    print("   ⚠ Port 27183 not listening")

# Check reverse forwards
print("\n4️⃣ Checking reverse port forwards...")
success, out, err = run_cmd(f'"{ADB_PATH}" -s {DEVICE} reverse --list')
print(f"   Reverse forwards:\n{out if out else '   (none)'}")

# Check if there are firewall/SELinux issues
print("\n5️⃣ Checking SELinux denials...")
success, out, err = run_cmd(f'"{ADB_PATH}" -s {DEVICE} shell "dmesg | grep avc | tail -20"')
if "avc" in out.lower():
    print(f"   ⚠ SELinux denials found:\n{out}")
else:
    print("   ✓ No recent SELinux denials")

# Check device properties that might affect connection
print("\n6️⃣ Checking relevant device properties...")
props = [
    "ro.debuggable",
    "ro.secure",
    "persist.sys.usb.config",
    "sys.usb.state"
]
for prop in props:
    success, out, err = run_cmd(f'"{ADB_PATH}" -s {DEVICE} shell "getprop {prop}"')
    print(f"   {prop}: {out.strip()}")

print("\n" + "=" * 70)
print("📋 ANALYSIS:")
print("=" * 70)
print("""
The 'Server connection failed' error means:
1. scrcpy-server.jar successfully pushed to device ✓
2. scrcpy-server starts on the device
3. BUT: The server cannot connect back to PC via reverse tunnel ✗

Common causes:
- USB connection is unstable (most common)
- Device has custom ROM with socket restrictions
- Firewall blocking the connection
- Too many devices on same USB hub causing bandwidth issues

SOLUTIONS TO TRY:
1. Move these 2 devices to a DIFFERENT USB hub/port
2. Use a shorter, higher quality USB cable
3. Reduce number of devices connected simultaneously
4. Try USB 3.0 port instead of USB 2.0
5. Check if these devices have custom ROM that blocks sockets
6. Reboot the devices
""")
