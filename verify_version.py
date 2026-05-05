#!/usr/bin/env python3
"""
Version Verification Script for v2.2.1
Checks that all version references are updated correctly
"""

import re
import sys

def check_file(filepath, pattern, expected_version="2.2.1"):
    """Check if file contains the expected version"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            matches = re.findall(pattern, content)
            if matches:
                version = matches[0]
                if version == expected_version:
                    print(f"✅ {filepath}: v{version}")
                    return True
                else:
                    print(f"❌ {filepath}: v{version} (expected v{expected_version})")
                    return False
            else:
                print(f"⚠️  {filepath}: Version pattern not found")
                return False
    except Exception as e:
        print(f"❌ {filepath}: Error reading file - {e}")
        return False

def main():
    print("=" * 60)
    print("Facebook Register Tool - Version Verification")
    print("=" * 60)
    print()
    
    checks = [
        ("gui.py", r'Facebook Register Tool v([\d.]+)'),
        ("setup.iss", r'#define MyAppVersion "([\d.]+)"'),
        ("src/core/constants.py", r'APP_VERSION = "([\d.]+)"'),
        ("README_INSTALLER.md", r'\*\*Current Version\*\*: ([\d.]+)'),
    ]
    
    results = []
    for filepath, pattern in checks:
        result = check_file(filepath, pattern)
        results.append(result)
    
    print()
    print("=" * 60)
    
    if all(results):
        print("✅ ALL VERSION CHECKS PASSED!")
        print("✅ Ready to build v2.2.1")
        print()
        print("Next steps:")
        print("  1. Run: build.bat")
        print("  2. Test: dist\\FRT\\FRT.exe")
        print("  3. Build installer with Inno Setup")
        print("  4. Test: Output\\FRT_Setup_v2.2.1.exe")
        return 0
    else:
        print("❌ SOME VERSION CHECKS FAILED!")
        print("❌ Please fix version mismatches before building")
        return 1

if __name__ == "__main__":
    sys.exit(main())
