"""
fb_device_register.py
─────────────────────
Updates Facebook's server-side device registration so that
"Where you're logged in" shows the correct spoofed device name.

How it works
────────────
Facebook's mobile app sends a phone_id registration request to:
  POST https://graph.facebook.com/v18.0/device/register

with the device's Build.MODEL, Build.MANUFACTURER, etc.
We replicate that call using the account's saved access_token
and the spoofed device properties from Device.xml.

This is the same call the Facebook app makes on first launch —
we're just making it ourselves with the correct device identity
before the app has a chance to send it with the real hardware info.
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.parse
import urllib.request
import ssl
import xml.etree.ElementTree as ET
from typing import Dict, Optional, Tuple


# ── SSL context (skip cert verify for compatibility) ─────────────────────────
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE


def _http_post(url: str, data: dict, headers: dict) -> Tuple[int, dict]:
    """Simple HTTP POST, returns (status_code, response_dict)."""
    body = urllib.parse.urlencode(data).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=20, context=_SSL_CTX) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                return resp.status, json.loads(raw)
            except Exception:
                return resp.status, {"raw": raw}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"raw": raw}
    except Exception as exc:
        return 0, {"error": str(exc)}


def _read_device_xml(xml_path: str) -> Dict[str, str]:
    """Parse MaxChanger Device.xml into a flat dict."""
    props: Dict[str, str] = {}
    try:
        tree = ET.parse(xml_path)
        for elem in tree.getroot():
            name = elem.get("name", "")
            value = (elem.get("value") or elem.text or "").strip()
            if name:
                props[name] = value
    except Exception:
        pass
    return props


def _read_access_token(dbl_auth_path: str) -> Optional[str]:
    """Extract access_token from dbl_local_auth_{uid} binary file."""
    if not os.path.exists(dbl_auth_path):
        return None
    try:
        with open(dbl_auth_path, "rb") as f:
            data = f.read()
        # Find JSON blob containing access_token
        strings = re.findall(rb'[\x20-\x7e]{20,}', data)
        for s in strings:
            s_str = s.decode("ascii", errors="replace")
            if '"access_token"' in s_str:
                try:
                    obj = json.loads(s_str)
                    if "access_token" in obj:
                        return obj["access_token"]
                except Exception:
                    # Try to extract just the token value
                    m = re.search(r'"access_token"\s*:\s*"([^"]+)"', s_str)
                    if m:
                        return m.group(1)
    except Exception:
        pass
    return None


def _read_cookies(auth_path: str) -> Dict[str, str]:
    """Extract cookies dict from authentication binary file."""
    cookies: Dict[str, str] = {}
    if not os.path.exists(auth_path):
        return cookies
    try:
        with open(auth_path, "rb") as f:
            data = f.read()
        strings = re.findall(rb'[\x20-\x7e]{20,}', data)
        for s in strings:
            s_str = s.decode("ascii", errors="replace")
            if '"session_cookies_string"' in s_str or ('"name"' in s_str and '"value"' in s_str and 'facebook.com' in s_str):
                # Try to find the cookie array
                m = re.search(r'\[(\{.*?\}(?:,\{.*?\})*)\]', s_str)
                if m:
                    try:
                        cookie_list = json.loads("[" + m.group(1) + "]")
                        for c in cookie_list:
                            if isinstance(c, dict) and "name" in c and "value" in c:
                                cookies[c["name"]] = c["value"]
                    except Exception:
                        pass
            # Also try direct JSON parse
            if s_str.startswith('[{') and '"name"' in s_str:
                try:
                    cookie_list = json.loads(s_str)
                    for c in cookie_list:
                        if isinstance(c, dict) and "name" in c and "value" in c:
                            cookies[c["name"]] = c["value"]
                except Exception:
                    pass
    except Exception:
        pass
    return cookies


def register_device_with_facebook(
    acc_folder: str,
    uid: str,
    device_xml_path: str,
    log_fn=None,
) -> Tuple[bool, str]:
    """
    Call Facebook's device registration API with the spoofed device identity.

    Args:
        acc_folder:      Path to the account backup folder
        uid:             Facebook UID string
        device_xml_path: Path to the extracted Device.xml from backup
        log_fn:          Optional callable(str) for logging

    Returns:
        (success, message)
    """
    def log(msg: str):
        if log_fn:
            log_fn(msg)

    # ── Read device properties from Device.xml ────────────────────────────
    props = _read_device_xml(device_xml_path)
    if not props:
        return False, "Device.xml empty or unreadable"

    brand        = props.get("brand", "")
    model        = props.get("model", "")
    manufacturer = props.get("manufacturer", brand)
    android_ver  = props.get("release", "9")
    device_name  = props.get("device", model)
    fingerprint  = props.get("fingerprint", "")
    serial       = props.get("serial", "")
    android_id   = props.get("android_id", "")

    if not model:
        return False, "No model in Device.xml"

    log(f"  Device: {manufacturer} {model} (Android {android_ver})")

    # ── Read access_token from dbl_local_auth ─────────────────────────────
    alp_dir = os.path.join(acc_folder, "Profile info")
    # Find extracted folder or extract from tar
    import tarfile, tempfile, shutil

    tmp_dir = None
    fb_data_path = None

    # Check if already extracted
    for root, dirs, files in os.walk(alp_dir):
        if os.path.basename(root) == "com.facebook.katana":
            fb_data_path = root
            break

    # If not extracted, extract from tar
    if not fb_data_path:
        tar_files = [f for f in os.listdir(alp_dir) if f.endswith((".tar.gz", ".tgz", ".tar"))]
        if not tar_files:
            return False, "No profile backup found"
        tmp_dir = tempfile.mkdtemp()
        try:
            with tarfile.open(os.path.join(alp_dir, tar_files[0]), "r:*") as tar:
                # Only extract auth files
                members = [m for m in tar.getmembers()
                           if "app_light_prefs" in m.name and
                           ("dbl_local_auth" in m.name or "authentication" in m.name)]
                tar.extractall(tmp_dir, members=members)
            for root, dirs, files in os.walk(tmp_dir):
                if os.path.basename(root) == "com.facebook.katana":
                    fb_data_path = root
                    break
        except Exception as e:
            if tmp_dir:
                shutil.rmtree(tmp_dir, ignore_errors=True)
            return False, f"Failed to extract profile backup: {e}"

    if not fb_data_path:
        if tmp_dir:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        return False, "Could not find com.facebook.katana in backup"

    alp_path = os.path.join(fb_data_path, "app_light_prefs", "com.facebook.katana")
    dbl_path = os.path.join(alp_path, f"dbl_local_auth_{uid}")
    auth_path = os.path.join(alp_path, "authentication")

    access_token = _read_access_token(dbl_path)
    if not access_token:
        if tmp_dir:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        return False, "Could not read access_token from backup"

    log(f"  access_token: {access_token[:20]}...")

    cookies = _read_cookies(auth_path)
    datr = cookies.get("datr", "")
    xs   = cookies.get("xs", "")
    c_user = cookies.get("c_user", uid)

    # ── Build the device registration request ────────────────────────────
    # This replicates what Facebook's Android app sends on first launch
    # to register the device and set the "Where you're logged in" name.
    #
    # Endpoint: POST /v18.0/{uid}/devices  (or /device/register)
    # The device_name field is what appears in "Where you're logged in"

    device_display_name = f"{manufacturer.capitalize()} {model}"

    # Method 1: Update device info via Graph API
    api_url = f"https://graph.facebook.com/v18.0/{uid}/devices"

    headers = {
        "User-Agent": (
            f"[FBAN/FB4A;FBAV/544.0.0.42.272;FBBV/862539700;"
            f"FBDM/{{density=2.0,width=1080,height=1920}};"
            f"FBLC/en_US;FBRV/0;FBCR/;FBMF/{manufacturer.upper()};"
            f"FBBD/{device_name};FBPN/com.facebook.katana;"
            f"FBDV/{model};FBSV/{android_ver};FBOP/1;FBCA/arm64-v8a:]"
        ),
        "Content-Type": "application/x-www-form-urlencoded",
        "Cookie": f"c_user={c_user}; xs={xs}; datr={datr}",
        "X-FB-HTTP-Engine": "Liger",
        "X-FB-Client-IP": "True",
        "X-FB-Server-Cluster": "True",
    }

    post_data = {
        "access_token": access_token,
        "device_id":    android_id or serial,
        "device_name":  device_display_name,
        "device_type":  "android",
        "os_version":   android_ver,
        "hardware_id":  android_id,
        "format":       "json",
    }

    log(f"  Registering device: {device_display_name}")
    status, resp = _http_post(api_url, post_data, headers)
    log(f"  API response ({status}): {str(resp)[:120]}")

    if status == 200 and "error" not in resp:
        if tmp_dir:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        return True, f"Device registered as '{device_display_name}'"

    # Method 2: Use /me/devices endpoint
    api_url2 = "https://graph.facebook.com/v18.0/me/devices"
    post_data2 = {
        "access_token":  access_token,
        "device_name":   device_display_name,
        "device_type":   "android",
        "hardware_id":   android_id or serial,
        "format":        "json",
    }
    status2, resp2 = _http_post(api_url2, post_data2, headers)
    log(f"  API2 response ({status2}): {str(resp2)[:120]}")

    if status2 == 200 and "error" not in resp2:
        if tmp_dir:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        return True, f"Device registered as '{device_display_name}' (method 2)"

    # Method 3: phone_id registration — the actual endpoint FB app uses
    # This is the real phone_id sync that updates "Where you're logged in"
    api_url3 = "https://graph.facebook.com/v18.0/device/register"
    post_data3 = {
        "access_token":       access_token,
        "device_id":          android_id,
        "device_name":        device_display_name,
        "device_type":        "android",
        "os_version":         android_ver,
        "app_version":        "544.0.0.42.272",
        "push_token":         "",
        "format":             "json",
    }
    status3, resp3 = _http_post(api_url3, post_data3, headers)
    log(f"  API3 response ({status3}): {str(resp3)[:120]}")

    if tmp_dir:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    if status3 == 200 and "error" not in resp3:
        return True, f"Device registered as '{device_display_name}' (method 3)"

    # All methods failed — log the errors but don't block restore
    err_msg = str(resp3.get("error", resp2.get("error", resp.get("error", "unknown"))))[:200]
    return False, f"Device registration API failed: {err_msg}"
