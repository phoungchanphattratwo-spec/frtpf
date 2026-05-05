# MaxChanger Device Spoofing Not Working - Diagnosis

## Problem

Fast restore completes successfully and logs show:
```
[FastRestore] Device props applied: oppo PFZM10
[FastRestore] android_id set: 3f315929ad1ff43b
[FastRestore] deviceJson: oppo PFZM10
```

But Facebook still shows **"Vivo V20 2021"** (physical device) instead of **"Oppo PFZM10"** (backup device).

## Root Cause

MaxChanger's hook is **not intercepting** Facebook's device property reads. This can happen for several reasons:

### 1. **MaxChanger Hook Not Active**

MaxChanger uses Xposed/LSPosed framework to hook into apps. The hook must be:
- ✅ Installed (MaxChanger app)
- ✅ Enabled in LSPosed/Xposed
- ✅ Activated for Facebook app
- ✅ Device rebooted after enabling

**Check:**
```bash
# Check if LSPosed is installed
adb shell pm list packages | grep lsposed

# Check if MaxChanger is installed
adb shell pm list packages | grep maxchanger

# Check LSPosed module status (requires LSPosed Manager)
# Open LSPosed Manager → Modules → MaxChanger → Enable
# Open LSPosed Manager → Modules → MaxChanger → Scope → Enable for Facebook
```

### 2. **Hook Reads Wrong File**

MaxChanger's BuildHook reads device info from:
1. **Primary:** `/data/local/tmp/nk/deviceJson.txt`
2. **Fallback:** `/data/data/com.minsoftware.maxchanger/shared_prefs/Device.xml`

If the hook can't read these files (permissions, path, format), it falls back to real device properties.

**Check:**
```bash
# Verify deviceJson.txt exists and is readable
adb shell su -c "cat /data/local/tmp/nk/deviceJson.txt"

# Verify Device.xml exists
adb shell su -c "cat /data/data/com.minsoftware.maxchanger/shared_prefs/Device.xml"

# Check permissions
adb shell su -c "ls -la /data/local/tmp/nk/"
adb shell su -c "ls -la /data/data/com.minsoftware.maxchanger/shared_prefs/Device.xml"
```

### 3. **Facebook Reads Device Name from Server**

Facebook caches device names on their server. Even if the device identity is spoofed locally, Facebook may show the **cached name from previous logins**.

The device name updates when:
- Facebook sends a device registration request
- The `phone_id` sync completes
- The server processes the new device info (can take minutes to hours)

### 4. **Device Name Source**

Facebook determines device name from multiple sources:
1. **Build.MODEL** - System property (e.g., "PFZM10")
2. **Build.BRAND** - System property (e.g., "oppo")
3. **Build.MANUFACTURER** - System property (e.g., "OPPO")
4. **User-Agent** - HTTP header in API requests
5. **Server cache** - Previously registered device name

MaxChanger hooks #1-3, but if Facebook uses #4 or #5, the hook won't affect it.

## Solutions

### Solution 1: Verify MaxChanger Hook is Active

1. **Open LSPosed Manager** on the device
2. Go to **Modules** tab
3. Find **MaxChanger** and enable it
4. Tap **MaxChanger** → **Scope**
5. Enable for **Facebook** (com.facebook.katana)
6. **Reboot device**
7. Test restore again

### Solution 2: Use Legacy Restore Method

The legacy restore method includes additional steps that may help:
- Re-login via Facebook API (generates fresh session with spoofed device)
- Device registration API call (explicitly tells Facebook the device name)
- Longer wait for phone_id sync (ensures server update completes)

To use legacy method, add this to your code:
```python
# In login_mixin.py, restore_account_session()
# Comment out the fast restore and use legacy:
return self._restore_account_session_legacy(account_data, device_id)
```

### Solution 3: Manual Device Registration

After fast restore completes, manually register the device with Facebook:

```python
import requests

# Get access token from restored session
access_token = "EAAAAUaZA8jlA..."  # From backup

# Get device info from Device.xml
device_brand = "oppo"
device_model = "PFZM10"
android_version = "9"

# Register device
url = "https://graph.facebook.com/v13.0/me/devices"
data = {
    "device_id": "...",  # Facebook's internal device_id
    "device_name": f"{device_brand.title()} {device_model}",
    "device_os": f"Android {android_version}",
}
headers = {"Authorization": f"Bearer {access_token}"}

response = requests.post(url, data=data, headers=headers)
print(response.json())
```

### Solution 4: Wait for Server Sync

The device name on Facebook's server may take time to update:
1. Restore completes successfully
2. Facebook generates new device_id locally
3. Background sync sends device_id to server
4. Server processes and updates device name (5-30 minutes)

**Wait 30 minutes** and check again. The device name may update automatically.

### Solution 5: Force Device Name Update

After restore, open Facebook and:
1. Go to **Settings → Security → Where you're logged in**
2. Tap the device
3. Tap **Edit** (if available)
4. Change device name manually
5. Save

This forces Facebook to update the device name on the server.

## Diagnostic Commands

Run these commands to diagnose the issue:

```bash
# 1. Check MaxChanger installation
adb shell pm list packages | grep maxchanger

# 2. Check LSPosed installation
adb shell pm list packages | grep lsposed

# 3. Check Device.xml
adb shell su -c "cat /data/data/com.minsoftware.maxchanger/shared_prefs/Device.xml | head -n 20"

# 4. Check deviceJson.txt
adb shell su -c "cat /data/local/tmp/nk/deviceJson.txt"

# 5. Check current system properties
adb shell getprop ro.product.brand
adb shell getprop ro.product.model
adb shell getprop ro.product.manufacturer

# 6. Check if resetprop worked
adb shell su -c "resetprop ro.product.brand"
adb shell su -c "resetprop ro.product.model"

# 7. Check Facebook's cached device info
adb shell su -c "sqlite3 /data/data/com.facebook.katana/databases/prefs_db 'SELECT key, value FROM preferences WHERE key LIKE \"%device%\" LIMIT 20'"

# 8. Check android_id
adb shell settings get secure android_id
```

## Expected vs Actual

### Expected (Working):
```
MaxChanger: Installed ✅
LSPosed: Installed ✅
Hook: Active for Facebook ✅
Device.xml: Exists, readable ✅
deviceJson.txt: Exists, readable ✅
System props: Spoofed (oppo PFZM10) ✅
Facebook shows: Oppo PFZM10 ✅
```

### Actual (Not Working):
```
MaxChanger: Installed ✅
LSPosed: Installed ❓
Hook: Active for Facebook ❓
Device.xml: Exists, readable ✅
deviceJson.txt: Exists, readable ✅
System props: Spoofed (oppo PFZM10) ✅
Facebook shows: Vivo V20 2021 ❌
```

## Next Steps

1. **Run diagnostic commands** above to identify which component is failing
2. **Check LSPosed Manager** to verify hook is enabled for Facebook
3. **Reboot device** after enabling hook
4. **Wait 30 minutes** for server sync
5. **Try legacy restore** if hook can't be fixed
6. **Report findings** so we can implement a permanent fix

## Technical Details

### How MaxChanger Works:

1. **Xposed/LSPosed Framework** hooks into app processes
2. **MaxChanger module** registers hooks for Build.* properties
3. When **Facebook reads** `Build.MODEL`, hook intercepts
4. Hook **reads** `/data/local/tmp/nk/deviceJson.txt`
5. Hook **returns** spoofed value instead of real value
6. Facebook **thinks** it's running on spoofed device

### Why It Might Fail:

- Hook not enabled in LSPosed
- Hook can't read deviceJson.txt (permissions)
- Facebook reads from cache instead of Build.*
- Server-side device name not updated yet
- Facebook uses different API to get device name

### Verification:

To verify hook is working, check Facebook's User-Agent:
```bash
# Capture network traffic
adb shell su -c "tcpdump -i any -s 0 -w /sdcard/fb.pcap port 443"

# Open Facebook, make a request
# Stop tcpdump (Ctrl+C)

# Pull and analyze
adb pull /sdcard/fb.pcap
# Look for User-Agent header - should contain spoofed device name
```

If User-Agent shows "Vivo V20", hook is not working.
If User-Agent shows "Oppo PFZM10", hook is working but server hasn't updated yet.
