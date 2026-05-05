# How to Use Screen Casting Diagnostics

## 🎯 Quick Start

### Option 1: Use GUI (Recommended)
1. Run `python gui.py`
2. Go to the "Account" tab
3. Right-click on a device in the devices table
4. Select "Diagnose Screen Casting"
5. A diagnostic window will open showing detailed analysis

### Option 2: Use Command Line Scripts

#### Quick Check
```bash
python diagnose_devices.py
```
Shows basic connectivity and device info for the two problem devices.

#### Test scrcpy Connection
```bash
python test_scrcpy.py
```
Actually attempts to start scrcpy and captures the exact error messages.

#### Apply Fixes
```bash
python fix_casting_devices.py
```
Attempts common fixes like cleaning up processes, port forwarding, etc.

#### Deep Debug
```bash
python deep_debug_scrcpy.py
```
Runs comprehensive diagnostics including logcat analysis and device properties.

#### Try TCP/IP Workaround
```bash
python try_tcpip_casting.py
```
Attempts to enable TCP/IP mode which may bypass USB restrictions.

## 📋 What You'll Learn

The diagnostics will tell you:
- ✓ Is the device connected?
- ✓ Is USB debugging authorized?
- ✓ Can files be pushed to the device?
- ✓ What's the device model and Android version?
- ✓ Is the screen on or off?
- ✓ Are there any scrcpy processes running?
- ✓ What's the ADB response time?
- ✓ What are the device security settings?
- ✓ What's the exact error from scrcpy?

## 🔍 Understanding the Results

### If you see "Server connection failed"
This means the device has security restrictions preventing screen casting.

### If you see "Device not connected"
Check USB cable and run `adb devices` to verify connection.

### If you see "Unauthorized"
Check the device screen for USB debugging authorization prompt.

### If you see "Timeout"
The device is responding slowly - try different USB port or cable.

## 💡 Solutions Based on Diagnostics

### For "Server connection failed" (Your Case)
- **Root Cause:** Device security policy blocks abstract sockets
- **Solutions:**
  1. Accept limitation and use other 17 devices
  2. Try TCP/IP mode: `python try_tcpip_casting.py`
  3. Use alternative mirroring (Vysor, TeamViewer)
  4. Root the devices (advanced)

### For Connection Issues
- Reconnect USB cable
- Try different USB port
- Restart ADB: `adb kill-server && adb start-server`

### For Authorization Issues
- Check device screen for prompt
- Revoke and re-authorize USB debugging

## 📊 Files Created

- `diagnose_devices.py` - Basic diagnostics
- `test_scrcpy.py` - Test actual scrcpy connection
- `fix_casting_devices.py` - Apply common fixes
- `deep_debug_scrcpy.py` - Deep analysis with logcat
- `try_tcpip_casting.py` - TCP/IP workaround attempt
- `SCREEN_CASTING_ISSUE_REPORT.md` - Full technical report
- `HOW_TO_USE_DIAGNOSTICS.md` - This guide

## 🚀 Next Steps

1. Read `SCREEN_CASTING_ISSUE_REPORT.md` for full technical details
2. Run diagnostics to confirm the issue
3. Try TCP/IP workaround if you want
4. Otherwise, work with your 17 functioning devices

The GUI now has built-in diagnostics, so you can easily check any device that has casting issues in the future!
