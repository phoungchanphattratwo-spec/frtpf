"""
Build Release Script
Creates EXE and prepares release package
"""

import os
import sys
import json
import hashlib
import shutil
from datetime import datetime
import subprocess

VERSION = "1.1.0"
APP_NAME = "FRT"
RELEASE_DATE = datetime.now().strftime("%Y%m%d")

def calculate_sha256(filepath):
    """Calculate SHA256 hash of a file"""
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def get_file_size_mb(filepath):
    """Get file size in MB"""
    size_bytes = os.path.getsize(filepath)
    return round(size_bytes / (1024 * 1024), 2)

def build_exe():
    """Build the EXE using PyInstaller"""
    print("🔨 Building EXE...")
    
    # Run PyInstaller
    cmd = [
        "pyinstaller",
        "--name=FRT",
        "--onefile",
        "--windowed",
        "--icon=app_icon.ico",
        "--add-data=logo;logo",
        "--add-data=reactions;reactions",
        "--add-data=platform-tools;platform-tools",
        "--add-data=scrcpy-win64-v3.1;scrcpy-win64-v3.1",
        "--add-data=vpn;vpn",
        "--add-data=bin;bin",
        "--hidden-import=PyQt6",
        "--hidden-import=qtawesome",
        "--hidden-import=requests",
        "--hidden-import=supabase",
        "main.py"
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"❌ Build failed: {result.stderr}")
        return False
    
    print("✅ EXE built successfully!")
    return True

def create_release_package():
    """Create release package"""
    print("📦 Creating release package...")
    
    # Create releases directory if it doesn't exist
    os.makedirs("releases", exist_ok=True)
    
    # Define paths
    exe_name = f"{APP_NAME}-v{VERSION}-windows-{RELEASE_DATE}.exe"
    exe_source = os.path.join("dist", "FRT.exe")
    exe_dest = os.path.join("releases", exe_name)
    
    if not os.path.exists(exe_source):
        print(f"❌ EXE not found: {exe_source}")
        return None
    
    # Copy EXE to releases
    shutil.copy2(exe_source, exe_dest)
    print(f"✅ Copied EXE to: {exe_dest}")
    
    # Calculate hash and size
    sha256 = calculate_sha256(exe_dest)
    file_size = get_file_size_mb(exe_dest)
    
    print(f"📊 File size: {file_size} MB")
    print(f"🔐 SHA256: {sha256}")
    
    return {
        "filename": exe_name,
        "path": exe_dest,
        "sha256": sha256,
        "size_mb": file_size
    }

def update_version_json(release_info):
    """Update version.json with release information"""
    print("📝 Updating version.json...")
    
    version_data = {
        "version": VERSION,
        "release_date": datetime.now().strftime("%Y-%m-%d"),
        "download_url": f"https://github.com/phoungchanphattratwo-spec/frtpf/releases/download/v{VERSION}/{release_info['filename']}",
        "changelog_url": f"https://github.com/phoungchanphattratwo-spec/frtpf/releases/tag/v{VERSION}",
        "minimum_version": "1.0.0",
        "force_update": False,
        "release_notes": [
            "✨ Lifetime license support (100 years)",
            "🎨 Modern license activation dialog",
            "🔧 License dashboard improvements",
            "🐛 Fixed expiry calculation bugs",
            "🟡 Yellow Tool ID badge",
            "🎯 Custom confirm/prompt dialogs"
        ],
        "file_size_mb": release_info['size_mb'],
        "sha256": release_info['sha256'],
        "platform": "windows",
        "architecture": "x64"
    }
    
    with open("version.json", "w", encoding="utf-8") as f:
        json.dump(version_data, f, indent=2, ensure_ascii=False)
    
    print("✅ version.json updated!")

def create_release_notes():
    """Create release notes file"""
    print("📄 Creating release notes...")
    
    notes = f"""# FRT v{VERSION} Release Notes

**Release Date:** {datetime.now().strftime("%Y-%m-%d")}

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

1. Download `{APP_NAME}-v{VERSION}-windows-{RELEASE_DATE}.exe`
2. Run the installer
3. Activate with your license key
4. Enjoy!

## 🔐 Verification

**SHA256:** (will be added after build)

## 📞 Support

- **Telegram:** [t.me/ftoolpro](https://t.me/ftoolpro)
- **Issues:** [GitHub Issues](https://github.com/phoungchanphattratwo-spec/frtpf/issues)

---

**Full Changelog:** [CHANGELOG.md](https://github.com/phoungchanphattratwo-spec/frtpf/blob/main/CHANGELOG.md)
"""
    
    release_notes_path = os.path.join("releases", f"RELEASE_NOTES_v{VERSION}.md")
    with open(release_notes_path, "w", encoding="utf-8") as f:
        f.write(notes)
    
    print(f"✅ Release notes created: {release_notes_path}")
    return release_notes_path

def main():
    """Main build process"""
    print(f"🚀 Building FRT v{VERSION} Release")
    print("=" * 50)
    
    # Step 1: Build EXE
    if not build_exe():
        print("❌ Build process failed!")
        sys.exit(1)
    
    # Step 2: Create release package
    release_info = create_release_package()
    if not release_info:
        print("❌ Failed to create release package!")
        sys.exit(1)
    
    # Step 3: Update version.json
    update_version_json(release_info)
    
    # Step 4: Create release notes
    release_notes_path = create_release_notes()
    
    print("\n" + "=" * 50)
    print("✅ BUILD COMPLETE!")
    print("=" * 50)
    print(f"\n📦 Release Package:")
    print(f"   File: {release_info['filename']}")
    print(f"   Path: {release_info['path']}")
    print(f"   Size: {release_info['size_mb']} MB")
    print(f"   SHA256: {release_info['sha256']}")
    print(f"\n📝 Next Steps:")
    print(f"   1. Test the EXE: {release_info['path']}")
    print(f"   2. Create GitHub release: v{VERSION}")
    print(f"   3. Upload: {release_info['filename']}")
    print(f"   4. Commit and push version.json")
    print(f"   5. Users will auto-detect the update!")
    print("\n🎉 Ready to release!")

if __name__ == "__main__":
    main()
