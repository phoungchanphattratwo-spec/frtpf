"""
Account backup utilities — reading, parsing, and locating backup folders.

Backup folder structure:
    account_backup/
        {uid}_{YYYYMMDD}_{HHMMSS}_{rand}/
            account_info.json
            Acc info              (plain-text summary)
            Device info/
                {uid}.tar.gz
            Profile info/
                {uid}.tar.gz
"""

from __future__ import annotations
import json
import os
import re
from typing import Dict, List, Optional


# Pattern: <uid>_<date>_<time>_<rand>
_BACKUP_FOLDER_RE = re.compile(r"^\d+_\d{8}_\d{6}_\d+$")


def find_account_folders(root_path: str) -> List[str]:
    """
    Return a list of absolute paths to valid account backup folders
    found directly under *root_path*.
    """
    folders: List[str] = []
    if not os.path.isdir(root_path):
        return folders
    for name in os.listdir(root_path):
        full = os.path.join(root_path, name)
        if os.path.isdir(full) and _BACKUP_FOLDER_RE.match(name):
            folders.append(full)
    return sorted(folders)


def parse_acc_info(acc_info_path: str) -> Dict[str, str]:
    """
    Parse the plain-text 'Acc info' file inside a backup folder.

    Expected format (one field per line):
        UID: 123456789
        Email: user@example.com
        Password: secret
        Name: John Doe
        Birthday: 15/06/1995
        Gender: Male
        Phone: +1234567890
        Device: emulator-5554
        Status: Active
        Created: 2026-03-26 17:25:46
        Notes: some note

    Returns a dict with lowercase keys.
    """
    data: Dict[str, str] = {}
    if not os.path.isfile(acc_info_path):
        return data
    try:
        with open(acc_info_path, "r", encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                if ":" in line:
                    key, _, value = line.partition(":")
                    data[key.strip().lower()] = value.strip()
    except Exception:
        pass
    return data


def load_account_json(folder_path: str) -> Optional[Dict]:
    """Load and return account_info.json from a backup folder, or None."""
    json_path = os.path.join(folder_path, "account_info.json")
    if not os.path.isfile(json_path):
        return None
    try:
        with open(json_path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


def get_uid_from_folder_name(folder_name: str) -> str:
    """Extract the UID (first segment) from a backup folder name."""
    return folder_name.split("_")[0]
