# Backup Device Mismatch Issue

## Problem Discovered

The backup's `device_id` is mapped to the **WRONG** device on Facebook's server.

### Analysis

When we analyzed the backup:
```
account_info.json says: "device_info": {"model": "BLA-A09", "device_name_short": "Huawei Mate 10 Pro"}
prefs_db contains: device_id = 6d6fb8c1-a859-415b-a921-525d7cf43fad
```

But when we check Facebook's "Where you're logged in", it shows: **"Vivo V20 2021"**

This means:
- The backup was created AFTER the account was moved to the Vivo device
- The `device_id` in the backup is already registered with Facebook's server as "Vivo V20 2021"
- The `device_info` in `account_info.json` is just metadata (not what Facebook's server knows)

### Why Preserving device_id Doesn't Work

When we preserve the backup's `device_id`:
1. Facebook reads: `device_id = 6d6fb8c1-a859-415b-a921-525d7cf43fad`
2. Facebook's server mapping: `6d6fb8c1-a859-415b-a921-525d7cf43fad` → "Vivo V20 2021"
3. Result: Still shows "Vivo V20 2021" ❌

### Why Other Tools Are Fast

Other tools likely use backups that were created on the CORRECT device:
1. Backup created when account was on Huawei device
2. `device_id` in backup is mapped to "Huawei BLA-A09" on server
3. Restore preserves this `device_id`
4. Facebook instantly recognizes it as "Huawei BLA-A09" ✓

### The Real Solution

For backups where `device_id` is mapped to the wrong device, we MUST:
1. Delete the old `device_id`
2. Let Facebook generate a NEW `device_id` with spoofed identity
3. Wait for phone_id sync to register the new `device_id` with server
4. This takes 1-2 minutes (unavoidable for mismatched backups)

### How to Create Proper Backups

To achieve 10-second restores, backups must be created when:
1. Account is logged in on the TARGET device (e.g., Huawei)
2. MaxChanger is active and spoofing the device
3. Facebook has already synced the `device_id` to server
4. Then create the backup

This way, the backup's `device_id` is correctly mapped to the target device on Facebook's server.

### Recommendation

Add a backup validation step:
1. When creating backup, check what device name Facebook's server shows
2. Store this in `account_info.json` as `server_device_name`
3. When restoring, compare `server_device_name` with target device
4. If mismatch, warn user that restore will take longer (need to regenerate device_id)

## Date

2026-04-26
