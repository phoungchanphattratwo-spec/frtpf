"""
Deep investigation: Why do SM-J730F devices block scrcpy but SM-J730G don't?
"""
import subprocess
import json

ADB_PATH = "platform-tools/platform-tools/adb.exe"

# Problem devices (SM-J730F)
PROBLEM_DEVICES = ["52000a02ee736459", "52001cefc039c401"]

# Working devices (SM-J730G) - pick a few for comparison
WORKING_DEVICES = ["52001dd8b2ffc47b", "520023fcfef9b4f1", "5200265aee148457"]

def run_cmd(device_id, cmd):
    try:
        result = subprocess.run(
            f'"{ADB_PATH}" -s {device_id} shell "{cmd}"',
            capture_output=True, text=True, timeout=10, shell=True
        )
        return result.stdout.strip()
    except:
        return "ERROR"

def compare_devices():
    print("🔍 DEEP INVESTIGATION: Why SM-J730F blocks scrcpy")
    print("=" * 80)
    
    # Properties to check
    security_props = [
        "ro.debuggable",
        "ro.secure",
        "ro.adb.secure",
        "persist.sys.usb.config",
        "ro.build.type",
        "ro.build.tags",
        "ro.build.version.security_patch",
        "ro.product.model",
        "ro.product.name",
        "ro.product.device",
        "ro.build.fingerprint",
        "ro.build.version.release",
        "ro.build.version.sdk",
        "security.perf_harden",
        "ro.config.knox",
        "ro.boot.warranty_bit",
        "ro.boot.verifiedbootstate",
        "ro.boot.veritymode",
        "persist.security.ams.enforcing",
    ]
    
    results = {}
    
    print("\n📊 Comparing Security Properties")
    print("=" * 80)
    
    # Collect data from problem devices
    print("\n🔴 PROBLEM DEVICES (SM-J730F - Cannot Cast):")
    for device_id in PROBLEM_DEVICES:
        print(f"\n  Device: {device_id}")
        results[device_id] = {}
        for prop in security_props:
            value = run_cmd(device_id, f"getprop {prop}")
            results[device_id][prop] = value
            if value and value != "ERROR":
                print(f"    {prop}: {value}")
    
    # Collect data from working devices
    print("\n\n✅ WORKING DEVICES (SM-J730G - Can Cast):")
    for device_id in WORKING_DEVICES:
        print(f"\n  Device: {device_id}")
        results[device_id] = {}
        for prop in security_props:
            value = run_cmd(device_id, f"getprop {prop}")
            results[device_id][prop] = value
            if value and value != "ERROR":
                print(f"    {prop}: {value}")
    
    # Compare and find differences
    print("\n\n" + "=" * 80)
    print("🔍 KEY DIFFERENCES FOUND:")
    print("=" * 80)
    
    differences = []
    for prop in security_props:
        problem_values = set(results[d].get(prop, "") for d in PROBLEM_DEVICES)
        working_values = set(results[d].get(prop, "") for d in WORKING_DEVICES)
        
        if problem_values != working_values:
            differences.append({
                'property': prop,
                'problem_devices': list(problem_values),
                'working_devices': list(working_values)
            })
    
    if differences:
        for diff in differences:
            print(f"\n📌 {diff['property']}:")
            print(f"   Problem devices (SM-J730F): {diff['problem_devices']}")
            print(f"   Working devices (SM-J730G): {diff['working_devices']}")
    else:
        print("\n⚠ No obvious differences in standard properties")
    
    # Check SELinux policies
    print("\n\n" + "=" * 80)
    print("🔍 CHECKING SELINUX POLICIES:")
    print("=" * 80)
    
    print("\n🔴 Problem Device SELinux:")
    selinux_problem = run_cmd(PROBLEM_DEVICES[0], "getenforce")
    print(f"   {selinux_problem}")
    
    print("\n✅ Working Device SELinux:")
    selinux_working = run_cmd(WORKING_DEVICES[0], "getenforce")
    print(f"   {selinux_working}")
    
    # Check for Knox or other security frameworks
    print("\n\n" + "=" * 80)
    print("🔍 CHECKING FOR SECURITY FRAMEWORKS:")
    print("=" * 80)
    
    print("\n🔴 Problem Device:")
    knox_problem = run_cmd(PROBLEM_DEVICES[0], "pm list packages | grep -i knox")
    if knox_problem:
        print(f"   Knox packages found: {knox_problem}")
    else:
        print("   No Knox packages")
    
    print("\n✅ Working Device:")
    knox_working = run_cmd(WORKING_DEVICES[0], "pm list packages | grep -i knox")
    if knox_working:
        print(f"   Knox packages found: {knox_working}")
    else:
        print("   No Knox packages")
    
    # Check build fingerprint differences
    print("\n\n" + "=" * 80)
    print("🔍 BUILD FINGERPRINT ANALYSIS:")
    print("=" * 80)
    
    print("\n🔴 Problem Device (SM-J730F):")
    fp_problem = run_cmd(PROBLEM_DEVICES[0], "getprop ro.build.fingerprint")
    print(f"   {fp_problem}")
    
    print("\n✅ Working Device (SM-J730G):")
    fp_working = run_cmd(WORKING_DEVICES[0], "getprop ro.build.fingerprint")
    print(f"   {fp_working}")
    
    # Check if devices are rooted
    print("\n\n" + "=" * 80)
    print("🔍 CHECKING ROOT STATUS:")
    print("=" * 80)
    
    print("\n🔴 Problem Device:")
    su_problem = run_cmd(PROBLEM_DEVICES[0], "which su")
    magisk_problem = run_cmd(PROBLEM_DEVICES[0], "pm list packages | grep -i magisk")
    print(f"   su binary: {su_problem if su_problem else 'Not found'}")
    print(f"   Magisk: {'Found' if magisk_problem else 'Not found'}")
    
    print("\n✅ Working Device:")
    su_working = run_cmd(WORKING_DEVICES[0], "which su")
    magisk_working = run_cmd(WORKING_DEVICES[0], "pm list packages | grep -i magisk")
    print(f"   su binary: {su_working if su_working else 'Not found'}")
    print(f"   Magisk: {'Found' if magisk_working else 'Not found'}")
    
    # Final analysis
    print("\n\n" + "=" * 80)
    print("📋 ROOT CAUSE ANALYSIS:")
    print("=" * 80)
    
    print("""
Based on the investigation, the likely causes are:

1. REGIONAL FIRMWARE DIFFERENCES:
   - SM-J730F = International version (Europe, Asia)
   - SM-J730G = Different regional version
   - Different regions have different security policies
   
2. CARRIER/OEM MODIFICATIONS:
   - SM-J730F may have carrier-specific security
   - Stricter ADB security policies
   - Limited socket permissions
   
3. ANDROID BUILD TYPE:
   - If ro.build.type = "user" (production)
   - vs "userdebug" (development)
   - Production builds have stricter security
   
4. SELINUX POLICIES:
   - Different SELinux rules between variants
   - May block abstract socket creation
   
5. KNOX OR SECURITY FRAMEWORKS:
   - Samsung Knox may be more restrictive on F variant
   - Additional security layers blocking scrcpy
   
6. ROOT/MAGISK STATUS:
   - If working devices are rooted with Magisk
   - They may have bypassed security restrictions
   - Problem devices may not be rooted

The fix requires either:
- Rooting the SM-J730F devices
- Flashing a more permissive ROM
- Using alternative screen mirroring methods
""")

if __name__ == "__main__":
    compare_devices()
