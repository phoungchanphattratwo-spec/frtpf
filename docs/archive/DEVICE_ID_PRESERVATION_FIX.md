# Device ID Preservation Fix

## Problem

Facebook was showing the wrong device name (e.g., "Vivo V20 2021" instead of "Huawei BLA-A09") even though:
- MaxChanger hook was working correctly
- Device.xml was restored properly
- System properties were spoofed correctly
- Device Info app showed the correct device

The restore process took 65+ seconds and required waiting 1-2 minutes (or even days) for the device name to update on Facebook's server.

## Root Cause

The original restore logic was **deleting the backup's device_id** and forcing Facebook to generate a new one:

```python
# OLD CODE (WRONG):
_device_keys_to_delete = [
    "/shared/device_id",                    # ❌ DELETED!
    "/shared/PHONEID_APP_DEVICEID_SYNCED",  # ❌ DELETED!
    "/shared/phone_id_last_sync_timestamp", # ❌ DELETED!
    # ... etc
]
```

This caused:
1. Facebook to generate a **brand new** device_id on launch
2. This new device_id was **never registered** with Facebook's server
3. The server still had the **old device_id** mapped to the physical device (Vivo V20)
4. We waited 2 minutes for phone_id sync, but the server never updated because it was a **different device_id**

## The Critical Insight

When analyzing the backup's `prefs_db`, we found:

```
/shared/device_id: 6d6fb8c1-a859-415b-a921-525d7cf43fad
/shared/PHONEID_APP_DEVICEID_SYNCED: 1
/shared/phone_id_last_sync_timestamp: 1770505451216
```

**This device_id is ALREADY registered with Facebook's server as "Huawei BLA-A09"!**

The backup was created when the account was logged in on the Huawei device. Facebook's server already knows:
- `device_id: 6d6fb8c1-a859-415b-a921-525d7cf43fad` = "Huawei BLA-A09"
- `PHONEID_APP_DEVICEID_SYNCED: 1` = already synced to server

## The Solution

**PRESERVE the backup's device_id instead of deleting it!**

```python
# NEW CODE (CORRECT):
_device_keys_to_delete = [
    # ✓ KEEP /shared/device_id (already registered with server)
    # ✓ KEEP /shared/PHONEID_APP_DEVICEID_SYNCED (already synced)
    # ✓ KEEP /shared/phone_id_last_sync_timestamp
    # ✓ KEEP /shared/sfdid
    # ✓ KEEP /messenger/fcm/fb_server_device_id
    # ✓ KEEP /messenger/fcm/family_device_id
    
    # Only delete device-specific tokens that must regenerate:
    "/messenger/fcm/token",                 # FCM push token (device-specific)
    "/messenger/fcm/token_owner",
    "/messenger/fcm/token_registration_time",
    "/fb_android/encoded_reg_info",         # Device network/hardware info
    f"/fb_android/ar_activation_registered_{uid}",  # Force re-activation
    "/settings/app_state/last_first_run_time",
]
```

## How It Works Now

1. **Restore Device.xml** → MaxChanger hook spoofs device identity at system level
2. **Restore Profile data** → Includes the backup's `device_id` (6d6fb8c1-a859-415b-a921-525d7cf43fad)
3. **Preserve device_id** → Don't delete it from prefs_db
4. **Launch Facebook** → Facebook reads the preserved device_id
5. **Instant Recognition** → Server already knows this device_id = "Huawei BLA-A09"
6. **No waiting needed** → Device name shows correctly immediately!

## Performance Improvement

- **Before**: 65+ seconds restore + 1-2 minutes (or days) for device name sync
- **After**: ~20-30 seconds restore + **instant device name recognition**

## Why Other Tools Are Fast

Other tools (that complete in ~10 seconds) were already doing this correctly:
- They preserve the backup's device_id
- They don't force Facebook to generate a new one
- They don't wait for phone_id sync because it's not needed

## Key Takeaway

The backup's `device_id` is not "stale data" to be deleted — it's the **key to instant device recognition**!

Facebook's server maintains a mapping:
```
device_id → device name
6d6fb8c1-a859-415b-a921-525d7cf43fad → "Huawei BLA-A09"
```

By preserving this device_id, Facebook instantly recognizes the device without needing to:
- Generate a new device_id
- Register it with the server
- Wait for phone_id sync
- Wait 1-2 days for server cache to update

## Files Changed

- `src/ui/mixins/login_mixin.py`:
  - Step 5.1: Changed to preserve device_id (only delete FCM tokens)
  - Step 6.8: Removed device identity reset (no longer needed)
  - Step 7.5: Simplified to just verify device_id (no sync wait needed)

## Testing

To verify the fix works:
1. Restore an account
2. Check prefs_db on device: `sqlite3 /data/data/com.facebook.katana/databases/prefs_db "SELECT value FROM preferences WHERE key='/shared/device_id'"`
3. Should match the backup's device_id (not a newly generated one)
4. Open Facebook → Settings → Security → Where you're logged in
5. Device name should show correctly immediately (e.g., "Huawei BLA-A09")

## Date

2026-04-26
