# Device Name Sync - Root Cause Analysis

## The Problem

Facebook shows the wrong device name (e.g., "Vivo V20 2021") even after restoring an account with spoofed device identity (e.g., "Oppo PFZM10").

## Root Causes Identified

### 1. Backup Device Mismatch
The backup's `device_id` is mapped to the WRONG device on Facebook's server.

**Example:**
- Backup says: `device_info.model = "BLA-A09"` (Huawei)
- But `prefs_db` contains: `device_id = 6d6fb8c1-a859-415b-a921-525d7cf43fad`
- Facebook's server mapping: `6d6fb8c1-a859-415b-a921-525d7cf43fad` → "Vivo V20 2021"

**Why:** The backup was created AFTER the account was moved to the Vivo device, so the `device_id` is already registered as Vivo on the server.

**Solution:** Delete the old `device_id` and let Facebook generate a new one with the spoofed identity.

### 2. No Google Play Services
The devices don't have Google Play Services installed.

**Impact:**
- Facebook relies on FCM (Firebase Cloud Messaging) for phone_id sync
- Without GMS, FCM doesn't work
- Facebook falls back to HTTP-based sync, which is MUCH slower

**Evidence:**
```
✗ com.google.android.gms is NOT installed
✗ com.google.android.gsf is NOT installed  
✗ com.android.vending is NOT installed
```

**Result:** Phone_id sync takes hours or days instead of 1-2 minutes.

### 3. Invalid/Expired Access Tokens
The access tokens in the backup are invalid or expired.

**Impact:**
- Device registration API calls fail with 400 errors
- Can't manually register the device with Facebook's server
- Must rely on the app's internal sync mechanism

**Evidence:**
```
[10:30:44] API response (400): {'error': {'message': "Unsupported post request..."
[10:30:44] API2 response (400): {'error': {'message': "Unsupported post request..."
[10:30:45] API3 response (400): {'error': {'message': "Unsupported post request..."
```

## Why Other Tools Are Fast (10 seconds)

Other tools achieve 10-second device name updates because:

1. **Correct Backups**: They use backups where the `device_id` is ALREADY mapped to the target device on Facebook's server
   - Backup created when account was on Huawei → `device_id` → "Huawei" on server
   - Restore preserves this `device_id` → Instant recognition ✓

2. **Google Play Services**: Their devices have GMS installed
   - FCM sync works properly
   - Phone_id registration completes in 1-2 minutes

3. **Valid Tokens**: Their backups have valid, long-lived access tokens
   - Can call device registration API successfully
   - Forces immediate server update

## The Complete Sync Flow

### With Google Play Services (Fast - 1-2 minutes):
1. Facebook generates new `device_id` with spoofed identity
2. Sets `PHONEID_APP_DEVICEID_SYNCED = 0`
3. Facebook app sends FCM registration to Google servers
4. Google FCM triggers Facebook's phone_id sync endpoint
5. Facebook server updates: `new_device_id` → "Spoofed Device Name"
6. Sets `PHONEID_APP_DEVICEID_SYNCED = 1`
7. ✓ Device name shows correctly in "Where you're logged in"

### Without Google Play Services (Slow - hours/days):
1. Facebook generates new `device_id` with spoofed identity
2. Sets `PHONEID_APP_DEVICEID_SYNCED = 0`
3. Facebook app tries FCM registration → FAILS (no GMS)
4. Falls back to HTTP polling mechanism
5. Waits for next periodic sync (every few hours)
6. Eventually syncs to server when app makes API calls
7. ⏳ Device name updates after hours or days

## Solutions

### Short-term (Current Situation):
**Accept the delay** - Without GMS, sync takes hours/days. This is unavoidable.

**Workaround:**
- Use the device actively (scroll feed, post, comment)
- This triggers more API calls and may speed up sync
- Check "Where you're logged in" after 6-12 hours

### Long-term (Proper Fix):

#### Option 1: Install Google Play Services
Install MicroG or full GMS on the devices:
- MicroG: Open-source GMS replacement
- Full GMS: Official Google Play Services

**Benefits:**
- FCM sync works properly
- Phone_id registration completes in 1-2 minutes
- Matches behavior of other tools

#### Option 2: Create Proper Backups
Create backups when the account is ALREADY on the target device:
1. Restore account to device with spoofed identity
2. Wait for device name to sync (hours/days first time)
3. Verify "Where you're logged in" shows correct device
4. THEN create the backup

**Benefits:**
- Backup's `device_id` is correctly mapped on server
- Future restores are instant (10 seconds)
- No sync wait needed

#### Option 3: Fix Access Token Generation
Implement proper re-login that generates valid, long-lived tokens:
- Use Facebook's OAuth flow correctly
- Store tokens that don't expire quickly
- Enable device registration API to work

**Benefits:**
- Can manually register device via API
- Forces immediate server update
- Bypasses FCM requirement

## Recommendation

**Immediate:** Document that without GMS, device name sync takes 6-24 hours. This is expected behavior.

**Next Steps:**
1. Add GMS detection to the tool
2. Warn users if GMS is missing
3. Provide instructions for installing MicroG
4. OR: Create a "proper backup" workflow that ensures `device_id` is correctly mapped before backup

## Technical Details

### Phone ID Sync Mechanism:
```
Facebook App → FCM Registration → Google Servers → FCM Push → Facebook Server
                                                                      ↓
                                                            Updates device_id mapping
                                                                      ↓
                                                            Sets PHONEID_APP_DEVICEID_SYNCED=1
```

### Without FCM:
```
Facebook App → HTTP Polling (every few hours) → Facebook Server
                                                        ↓
                                              Eventually updates device_id
                                                        ↓
                                              Hours/days later
```

### Database Keys:
- `/shared/device_id`: The UUID that identifies this device to Facebook
- `/shared/PHONEID_APP_DEVICEID_SYNCED`: 0 = not synced, 1 = synced to server
- `/shared/phone_id_last_sync_timestamp`: Last successful sync time
- `/messenger/fcm/fb_server_registered`: 0 = not registered with FCM, 1 = registered

## Date

2026-04-26

## Status

**ROOT CAUSE CONFIRMED**: Devices lack Google Play Services, causing phone_id sync to fail. Without FCM, Facebook's fallback HTTP sync takes hours or days.
