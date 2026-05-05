"""
Try to enable screen casting via TCP/IP mode for restricted devices
This may bypass some USB security restrictions
"""
import subprocess
import time

DEVICES = ["52000a02ee736459", "52001cefc039c401"]
ADB_PATH = "platform-tools/platform-tools/adb.exe"

def run_cmd(cmd, timeout=10):
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, shell=True)
        return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
    except Exception as e:
        return False, "", str(e)

def try_tcpip_mode(device_id):
    print(f"\n{'='*70}")
    print(f"🔧 Trying TCP/IP mode for: {device_id}")
    print(f"{'='*70}\n")
    
    # Step 1: Enable TCP/IP on port 5555
    print("1️⃣ Enabling TCP/IP mode on device...")
    success, out, err = run_cmd(f'"{ADB_PATH}" -s {device_id} tcpip 5555')
    if success or "restarting in TCP mode" in out:
        print(f"   ✓ TCP/IP mode enabled")
    else:
        print(f"   ⚠ Warning: {err}")
    
    time.sleep(3)
    
    # Step 2: Get device IP
    print("\n2️⃣ Getting device IP address...")
    success, out, err = run_cmd(f'"{ADB_PATH}" -s {device_id} shell "ip addr show wlan0 | grep inet"')
    if not success:
        print(f"   ⚠ Could not get IP, trying alternative method...")
        success, out, err = run_cmd(f'"{ADB_PATH}" -s {device_id} shell "ifconfig wlan0"')
    
    # Parse IP
    ip = None
    for line in out.split('\n'):
        if 'inet ' in line or 'inet addr:' in line:
            parts = line.split()
            for i, part in enumerate(parts):
                if 'inet' in part and i + 1 < len(parts):
                    ip_candidate = parts[i + 1].split(':')[-1].split('/')[0]
                    if ip_candidate.count('.') == 3:
                        ip = ip_candidate
                        break
            if ip:
                break
    
    if not ip:
        print(f"   ❌ Could not determine device IP")
        print(f"   Raw output: {out}")
        return False
    
    print(f"   ✓ Device IP: {ip}")
    
    # Step 3: Connect via TCP/IP
    print(f"\n3️⃣ Connecting to {ip}:5555...")
    success, out, err = run_cmd(f'"{ADB_PATH}" connect {ip}:5555')
    if "connected" in out.lower() or "already connected" in out.lower():
        print(f"   ✓ Connected via TCP/IP")
    else:
        print(f"   ⚠ Connection result: {out}")
    
    time.sleep(2)
    
    # Step 4: Verify connection
    print(f"\n4️⃣ Verifying TCP/IP connection...")
    success, out, err = run_cmd(f'"{ADB_PATH}" devices')
    if f"{ip}:5555" in out:
        print(f"   ✓ Device visible as {ip}:5555")
        print(f"\n✅ SUCCESS! You can now try casting with device ID: {ip}:5555")
        return True
    else:
        print(f"   ❌ Device not visible in TCP/IP mode")
        return False

print("🔧 TCP/IP Screen Casting Workaround")
print("=" * 70)
print("\nThis attempts to bypass USB security restrictions by using")
print("TCP/IP mode instead of direct USB connection.\n")

results = {}
for device_id in DEVICES:
    results[device_id] = try_tcpip_mode(device_id)

print(f"\n{'='*70}")
print("📋 RESULTS")
print(f"{'='*70}")
for device_id, success in results.items():
    status = "✅ Ready for TCP/IP casting" if success else "❌ Failed"
    print(f"{device_id}: {status}")

if any(results.values()):
    print(f"\n💡 To cast via TCP/IP:")
    print(f"   Use the IP:5555 address instead of the serial number")
    print(f"   Example: scrcpy -s 192.168.x.x:5555")
else:
    print(f"\n❌ TCP/IP mode did not work for these devices.")
    print(f"\n📋 FINAL CONCLUSION:")
    print(f"   These 2 devices have security restrictions that prevent")
    print(f"   screen casting via scrcpy. Options:")
    print(f"   1. Root the devices")
    print(f"   2. Use alternative screen mirroring (Vysor, TeamViewer)")
    print(f"   3. Work with the other 17 devices that can cast")
