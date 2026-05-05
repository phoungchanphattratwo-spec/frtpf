#!/usr/bin/env python3
"""
Convert tar profile backups to importable format.
This script extracts tar files and creates the folder structure expected by the tool.
"""
import os
import tarfile
import shutil
import json
from pathlib import Path

# Configuration - UPDATE THESE PATHS
SOURCE_FOLDER = r"C:\Users\KLS COMPUTER\Documents\20acc\Profiles"
OUTPUT_FOLDER = r"C:\Users\KLS COMPUTER\Desktop\FRT\imported_tar_accounts"

def extract_tar_to_import_format(tar_path, output_base):
    """Extract a tar file and create the import folder structure"""
    
    # Get UID from filename (e.g., 61586927747389.tar.gz -> 61586927747389)
    filename = Path(tar_path).name
    # Remove .tar.gz, .tar, or .tgz extension
    if filename.endswith('.tar.gz'):
        uid = filename[:-7]
    elif filename.endswith('.tgz'):
        uid = filename[:-4]
    elif filename.endswith('.tar'):
        uid = filename[:-4]
    else:
        uid = Path(tar_path).stem
    
    print(f"Processing {uid}...")
    
    # Create account folder
    account_folder = os.path.join(output_base, f"{uid}_imported")
    os.makedirs(account_folder, exist_ok=True)
    
    try:
        # Create Profile info folder and copy tar directly
        profile_folder = os.path.join(account_folder, "Profile info")
        os.makedirs(profile_folder, exist_ok=True)
        
        # Copy tar file as .tar.gz (tool expects .tar.gz)
        dest_tar = os.path.join(profile_folder, f"{uid}.tar.gz")
        shutil.copy2(tar_path, dest_tar)
        
        print(f"  ✓ Created Profile info backup")
        
        # Create a placeholder Acc info file
        acc_info_path = os.path.join(account_folder, "Acc info")
        with open(acc_info_path, 'w', encoding='utf-8') as f:
            f.write(f"{uid}|CHANGE_PASSWORD|c_user={uid}; xs=CHANGE_XS; fr=CHANGE_FR; datr=CHANGE_DATR\n")
        
        print(f"  ✓ Created Acc info")
        
        # Create account_info.json
        account_info = {
            "account_uid": uid,
            "full_name": f"Account {uid}",
            "first_name": "Account",
            "last_name": uid,
            "email": "",
            "phone": "",
            "password": "CHANGE_PASSWORD",
            "birthday": "",
            "gender": "",
            "cookies": f"c_user={uid}; xs=CHANGE_XS; fr=CHANGE_FR; datr=CHANGE_DATR",
            "device_info": {},
            "status": "active",
            "created_at": "2026-04-26 11:00:00",
            "imported": True,
            "notes": "Imported from tar backup - EDIT PASSWORD AND COOKIES IN ACC INFO FILE"
        }
        
        with open(os.path.join(account_folder, "account_info.json"), 'w', encoding='utf-8') as f:
            json.dump(account_info, f, indent=2, ensure_ascii=False)
        
        print(f"  ✓ Created account_info.json")
        
        return True
        
    except Exception as e:
        print(f"  ✗ Error: {e}")
        shutil.rmtree(account_folder, ignore_errors=True)
        return False

def main():
    print("=" * 80)
    print("TAR to Import Format Converter")
    print("=" * 80)
    
    if not os.path.exists(SOURCE_FOLDER):
        print(f"❌ Source folder not found: {SOURCE_FOLDER}")
        print("\nPlease edit the script and update SOURCE_FOLDER path")
        input("Press Enter to exit...")
        return
    
    # Create output folder
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    
    # Find all tar files
    tar_files = [f for f in os.listdir(SOURCE_FOLDER) if f.endswith(('.tar', '.tar.gz', '.tgz'))]
    
    if not tar_files:
        print(f"❌ No .tar files found in {SOURCE_FOLDER}")
        input("Press Enter to exit...")
        return
    
    print(f"\nFound {len(tar_files)} tar files")
    print(f"Source: {SOURCE_FOLDER}")
    print(f"Output: {OUTPUT_FOLDER}\n")
    
    success_count = 0
    for tar_file in tar_files:
        tar_path = os.path.join(SOURCE_FOLDER, tar_file)
        if extract_tar_to_import_format(tar_path, OUTPUT_FOLDER):
            success_count += 1
    
    print("\n" + "=" * 80)
    print(f"✓ Converted {success_count}/{len(tar_files)} accounts")
    print("=" * 80)
    print(f"\n📁 Output folder: {OUTPUT_FOLDER}")
    print("\n⚠️  IMPORTANT: Edit the 'Acc info' files to add:")
    print("   1. Correct password (replace CHANGE_PASSWORD)")
    print("   2. Correct cookies (replace CHANGE_XS, CHANGE_FR, CHANGE_DATR)")
    print("\nThen import in the tool:")
    print("   1. Go to Import tab")
    print("   2. Select 'Folder (TAR)'")
    print(f"   3. Browse to: {OUTPUT_FOLDER}")
    print("   4. Click 'Validate' then 'Import Accounts'")
    
    input("\nPress Enter to exit...")

if __name__ == "__main__":
    main()
