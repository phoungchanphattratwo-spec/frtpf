# GitHub Release Guide - FRT v1.1.0

## 📋 Pre-Release Checklist

✅ EXE built successfully: `releases/FRT-v1.1.0-windows-20260505.exe`
✅ File size: **106.78 MB**
✅ SHA256: `869ec8324520a07e5744d7e4057c4548af2dacd38c7093a944620c575051ec49`
✅ version.json updated with correct hash and download URL
✅ Release notes prepared

---

## 🚀 Step-by-Step Release Process

### Step 1: Test the EXE (IMPORTANT!)
Before releasing, test the built EXE:
```bash
# Run the EXE
./releases/FRT-v1.1.0-windows-20260505.exe
```

**Test checklist:**
- [ ] App launches without errors
- [ ] License activation works
- [ ] Lifetime license shows "Never (Lifetime)"
- [ ] Tool ID has yellow background
- [ ] Close button turns white on hover
- [ ] All dialogs work properly

---

### Step 2: Authenticate with GitHub

You need to authenticate before pushing. Choose ONE method:

#### Option A: GitHub Desktop (EASIEST)
1. Open GitHub Desktop
2. Add this repository
3. It will handle authentication automatically

#### Option B: Personal Access Token (PAT)
1. Go to: https://github.com/settings/tokens
2. Generate new token (classic)
3. Select scopes: `repo`, `workflow`
4. Copy the token
5. Use it as password when pushing:
   ```bash
   git push -u origin main
   # Username: phoungchanphattratwo-spec
   # Password: <paste your token>
   ```

#### Option C: SSH Key
1. Generate SSH key: `ssh-keygen -t ed25519 -C "your_email@example.com"`
2. Add to GitHub: https://github.com/settings/keys
3. Change remote to SSH:
   ```bash
   git remote set-url origin git@github.com:phoungchanphattratwo-spec/frtpf.git
   ```

---

### Step 3: Commit and Push version.json

**IMPORTANT:** Only push `version.json`, NOT the EXE files!

```bash
# Stage only version.json
git add version.json

# Commit
git commit -m "chore: update version.json for v1.1.0 release"

# Push to main branch
git push origin main
```

---

### Step 4: Create GitHub Release

#### Using GitHub Web Interface:

1. **Go to Releases Page:**
   - Navigate to: https://github.com/phoungchanphattratwo-spec/frtpf/releases
   - Click "Draft a new release"

2. **Fill in Release Details:**
   - **Tag version:** `v1.1.0`
   - **Target:** `main` branch
   - **Release title:** `FRT v1.1.0 - Lifetime License Support`

3. **Release Description:**
   Copy and paste from `releases/RELEASE_NOTES_v1.1.0.md`:

```markdown
# FRT v1.1.0 Release Notes

**Release Date:** 2026-05-05

## 🎉 What's New

### ✨ New Features
- **Lifetime License Support** - Licenses can now be set to 100 years (effectively lifetime)
- **Modern License Dialog** - Completely redesigned activation interface
- **License Dashboard** - Web-based admin panel for license management
- **Auto-fix Tools** - Automatic conversion of 1-year licenses to lifetime
- **Custom Dialogs** - Beautiful confirm/prompt dialogs in dashboard

### 🎨 UI Improvements
- Yellow Tool ID badge for better visibility
- Improved color coding throughout the app
- Better placeholder text in input fields
- Enhanced button hover effects

### 🐛 Bug Fixes
- Fixed license expiry calculation (0 days now = lifetime)
- Fixed close button icon color on hover
- Fixed "No License" fallback display
- Fixed expiry showing "Apr 11, 2126" instead of "Never"
- Removed annoying "License Required" popup

### 🔧 Technical Improvements
- Better error handling in license validation
- Improved license file caching
- Enhanced database queries
- Optimized UI rendering

## 📥 Installation

1. Download `FRT-v1.1.0-windows-20260505.exe`
2. Run the installer
3. Activate with your license key
4. Enjoy!

## 🔐 Verification

**SHA256:** `869ec8324520a07e5744d7e4057c4548af2dacd38c7093a944620c575051ec49`

## 📞 Support

- **Telegram:** [t.me/ftoolpro](https://t.me/ftoolpro)
- **Issues:** [GitHub Issues](https://github.com/phoungchanphattratwo-spec/frtpf/issues)

---

**Full Changelog:** [CHANGELOG.md](https://github.com/phoungchanphattratwo-spec/frtpf/blob/main/CHANGELOG.md)
```

4. **Upload the EXE:**
   - Drag and drop: `releases/FRT-v1.1.0-windows-20260505.exe`
   - Or click "Attach binaries" and select the file
   - Wait for upload to complete (106.78 MB)

5. **Publish Release:**
   - Check "Set as the latest release"
   - Click "Publish release"

---

### Step 5: Verify Auto-Update Works

After publishing the release:

1. **Check version.json is accessible:**
   ```bash
   curl https://raw.githubusercontent.com/phoungchanphattratwo-spec/frtpf/main/version.json
   ```

2. **Check download URL works:**
   ```
   https://github.com/phoungchanphattratwo-spec/frtpf/releases/download/v1.1.0/FRT-v1.1.0-windows-20260505.exe
   ```

3. **Test auto-update in app:**
   - Open an older version of the app
   - It should detect the new version
   - Show update notification with release notes

---

## 📊 Release Summary

| Item | Value |
|------|-------|
| **Version** | 1.1.0 |
| **Release Date** | 2026-05-05 |
| **File Name** | FRT-v1.1.0-windows-20260505.exe |
| **File Size** | 106.78 MB |
| **SHA256** | `869ec8324520a07e5744d7e4057c4548af2dacd38c7093a944620c575051ec49` |
| **Platform** | Windows x64 |
| **Download URL** | https://github.com/phoungchanphattratwo-spec/frtpf/releases/download/v1.1.0/FRT-v1.1.0-windows-20260505.exe |

---

## 🎯 What Happens After Release?

1. **Users with the app installed:**
   - App checks `version.json` on startup
   - Detects new version 1.1.0
   - Shows update notification
   - User clicks "Download" → opens GitHub release page
   - User downloads and installs new version

2. **New users:**
   - Visit GitHub releases page
   - Download latest version
   - Install and activate

3. **License dashboard:**
   - Continues to work normally
   - All existing licenses remain valid
   - Lifetime licenses now display correctly

---

## 🔧 Troubleshooting

### If push fails:
- Make sure you're authenticated (see Step 2)
- Check if you have write access to the repository
- Try: `git pull origin main` first, then push again

### If release upload fails:
- Check your internet connection
- File might be too large - GitHub has 2GB limit (we're at 106MB, so OK)
- Try uploading again

### If auto-update doesn't work:
- Verify version.json is pushed to main branch
- Check the download URL is correct
- Ensure release is published (not draft)

---

## ✅ Post-Release Checklist

After successful release:
- [ ] version.json is pushed to main branch
- [ ] GitHub release v1.1.0 is published
- [ ] EXE is uploaded to release
- [ ] Download URL works
- [ ] SHA256 hash matches
- [ ] Test auto-update detection
- [ ] Announce on Telegram: t.me/ftoolpro
- [ ] Update any documentation if needed

---

## 🎉 You're Done!

Users will now automatically receive update notifications when they open the app!

**Next version:** When ready for v1.2.0, just run `python build_release.py` again and repeat this process.
