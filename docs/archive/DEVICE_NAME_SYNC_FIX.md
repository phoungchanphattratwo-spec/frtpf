# Device Name Sync Fix - Force Facebook to Update Server

## Problem

Device spoofing works locally (Device Info shows "Huawei BLA-A09"), but Facebook server still shows "Vivo V20 2021".

## Root Cause

The `phone_id` sync is **timing out** before completing:

```
[15:24:10] device_id not generated after 30s — sync will happen when FB connects
```

This means:
1. ✅ Facebook generates device_id locally
2. ❌ Facebook doesn't sync it to server within 30 seconds
3. ❌ Server never gets updated with new device name

## Why Other Tools Work Faster

Other tools likely:
1. **Wait longer** for sync (2-5 minutes instead of 30 seconds)
2. **Force foreground** - Keep Facebook in foreground during sync
3. **Verify internet** - Ensure device has connectivity
4. **Trigger sync** - Force Facebook to send the registration immediately

## Solution: Extended Sync Wait

The code already has the sync logic, but it times out too early. We need to:

### 1. Increase Wait Time

Change from 30 seconds to 2 minutes:

```python
# OLD: Wait 30 seconds
for _s2 in range(6):  # 6 * 5 = 30 seconds
    time.sleep(5)
    
# NEW: Wait 2 minutes  
for _s2 in range(24):  # 24 * 5 = 120 seconds
    time.sleep(5)
```

### 2. Keep Facebook in Foreground

Facebook only syncs when it's active:

```python
# After launching Facebook, keep it in foreground
adb shell input keyevent KEYCODE_HOME  # Go home
time.sleep(1)
adb shell am start -n com.facebook.katana/.LoginActivity  # Bring back
```

### 3. Verify Internet Connectivity

Check if device has internet before waiting:

```python
# Ping Facebook's server
result = adb shell ping -c 1 graph.facebook.com
if "1 packets transmitted, 1 received" not in result:
    log("WARNING: No internet connectivity - sync will fail")
```

### 4. Force Sync Trigger

Interact with Facebook to trigger sync:

```python
# Open a specific screen that triggers device registration
adb shell am start -a android.intent.action.VIEW -d "fb://settings/security"
time.sleep(2)
adb shell input keyevent KEYCODE_BACK
```

## Quick Fix: Manual Approach

If you don't want to modify code:

### After Restore Completes:

1. **Keep Facebook open** for 2-3 minutes
2. **Ensure internet is connected**
3. **Navigate in app:**
   - Go to Settings → Security → Where you're logged in
   - Pull down to refresh
   - Go back to home feed
   - Wait 1 minute
   - Check "Where you're logged in" again

4. **Force sync:**
   - Go to Settings → Security → Two-Factor Authentication
   - Try to add a security method (don't complete it)
   - Go back
   - Check "Where you're logged in" - should update

## Implementation

The fix needs to be applied in `src/ui/mixins/login_mixin.py` around line 2195-2230:

```python
# Current code waits 30 seconds (6 iterations * 5 seconds)
for _s2 in range(6):
    time.sleep(5)
    # Check if synced
    
# Change to 2 minutes (24 iterations * 5 seconds)
for _s2 in range(24):
    time.sleep(5)
    # Check if synced
    # Also keep Facebook in foreground
    if _s2 % 4 == 0:  # Every 20 seconds
        adb_shell("am start -n com.facebook.katana/.LoginActivity")
```

## Testing

After applying the fix:

1. Run restore
2. Should see logs like:
   ```
   [Restore] waiting for phone_id sync... (5s)
   [Restore] waiting for phone_id sync... (10s)
   ...
   [Restore] waiting for phone_id sync... (45s)
   [Restore] Phone ID synced! Device name updated on server
   ```

3. Check "Where you're logged in" immediately
4. Should show "Huawei BLA-A09" (not "Vivo V20")

## Why 30 Seconds Isn't Enough

Facebook's sync process:
1. Generate device_id (5-10s)
2. Wait for network (0-5s)
3. Send registration request (5-10s)
4. Server processes (10-30s)
5. Confirmation received (5s)

**Total: 25-60 seconds**

The current 30-second timeout is right at the edge - sometimes it works, sometimes it doesn't.

## Alternative: Post-Restore Sync

If extending the wait time makes restore too slow, we can:

1. Complete restore quickly (current behavior)
2. Return success immediately
3. Run sync check in background thread
4. Show notification when sync completes

This gives users the fast restore they want while ensuring the device name updates eventually.

## Recommendation

**Increase wait time to 2 minutes** - This ensures the sync completes before restore finishes, giving users the correct device name immediately.

The extra 90 seconds is worth it for a working device name.
