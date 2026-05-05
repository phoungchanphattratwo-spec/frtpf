"""
fb_relogin.py
─────────────
Re-login to Facebook using saved credentials via the mobile API,
generating a fresh session tied to the spoofed device identity.

This updates the datr cookie and session so "Where you're logged in"
shows the correct spoofed device name instead of the original device.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
import urllib.parse
import urllib.request
import ssl
import uuid
import xml.etree.ElementTree as ET
from typing import Dict, Optional, Tuple


_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

# Facebook Android app credentials (public, same across all Android FB installs)
FB_APP_ID     = "256002347743983"
FB_APP_SECRET = "374e60f8b9bb6b8cbb30f78030438895"
FB_API_KEY    = "882a8490361da98702bf97a021ddc14d"


def _post(url: str, data: dict, headers: dict) -> Tuple[int, dict]:
    body = urllib.parse.urlencode(data).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=25, context=_SSL_CTX) as resp:
            raw = resp.read()
            # Decompress gzip if needed
            if raw[:2] == b'\x1f\x8b':
                import gzip
                raw = gzip.decompress(raw)
            raw = raw.decode("utf-8", errors="replace")
            try:
                return resp.status, json.loads(raw)
            except Exception:
                return resp.status, {"raw": raw}
    except urllib.error.HTTPError as e:
        raw = e.read()
        if raw[:2] == b'\x1f\x8b':
            import gzip
            try:
                raw = gzip.decompress(raw)
            except Exception:
                pass
        try:
            raw = raw.decode("utf-8", errors="replace")
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"raw": raw if isinstance(raw, str) else str(raw), "error": str(e)}
    except Exception as exc:
        return 0, {"error": str(exc)}


def _get(url: str, headers: dict) -> Tuple[int, dict]:
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=25, context=_SSL_CTX) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                return resp.status, json.loads(raw)
            except Exception:
                return resp.status, {"raw": raw}
    except Exception as exc:
        return 0, {"error": str(exc)}


def _read_device_xml(xml_path: str) -> Dict[str, str]:
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


def _build_user_agent(props: Dict[str, str]) -> str:
    """Build Facebook Android user-agent string from device props."""
    manufacturer = props.get("manufacturer", props.get("brand", "samsung")).upper()
    model        = props.get("model", "SM-G991B")
    android_ver  = props.get("release", "12")
    device       = props.get("device", model)
    return (
        f"[FBAN/FB4A;FBAV/544.0.0.42.272;FBBV/862539700;"
        f"FBDM/{{density=2.625,width=1080,height=2340}};"
        f"FBLC/en_US;FBRV/0;FBCR/;"
        f"FBMF/{manufacturer};"
        f"FBBD/{device};"
        f"FBPN/com.facebook.katana;"
        f"FBDV/{model};"
        f"FBSV/{android_ver};"
        f"FBOP/1;FBCA/arm64-v8a:]"
    )


def _gen_adid() -> str:
    """Generate a random advertising ID."""
    return str(uuid.uuid4())


def _gen_device_id() -> str:
    """Generate a random device ID."""
    return str(uuid.uuid4())


def relogin_and_get_fresh_session(
    phone_or_email: str,
    password: str,
    device_xml_path: str,
    log_fn=None,
) -> Tuple[bool, dict]:
    """
    Re-login to Facebook via mobile API with spoofed device identity.

    Returns:
        (success, session_data)
        session_data keys: access_token, uid, cookies, datr, xs, c_user
    """
    def log(msg: str):
        if log_fn:
            log_fn(msg)

    props = _read_device_xml(device_xml_path)
    if not props:
        return False, {"error": "Device.xml empty"}

    manufacturer = props.get("manufacturer", props.get("brand", "oppo"))
    model        = props.get("model", "PFZM10")
    android_ver  = props.get("release", "9")
    android_id   = props.get("android_id", _gen_adid().replace("-", "")[:16])
    device_id    = _gen_device_id()
    adid         = _gen_adid()

    user_agent = _build_user_agent(props)
    log(f"  UA: {user_agent[:80]}...")

    base_headers = {
        "User-Agent":           user_agent,
        "Content-Type":         "application/x-www-form-urlencoded",
        "X-FB-HTTP-Engine":     "Liger",
        "X-FB-Client-IP":       "True",
        "X-FB-Server-Cluster":  "True",
        "X-FB-Connection-Type": "WIFI",
        "Accept-Language":      "en_US",
    }

    # Normalize phone: try with and without + prefix
    login_candidates = [phone_or_email]
    if phone_or_email.startswith("+"):
        login_candidates.append(phone_or_email[1:])  # without +
    elif phone_or_email.isdigit():
        login_candidates.append("+" + phone_or_email)  # with +

    last_err = {}
    for _login_id in login_candidates:
        login_data = {
            "adid":                adid,
            "email":               _login_id,
            "password":            password,
            "format":              "json",
            "device_id":           device_id,
            "cpl":                 "true",
            "family_device_id":    device_id,
            "locale":              "en_US",
            "client_country_code": "US",
            "credentials_type":    "password",
            "generate_session_cookies": "1",
            "generate_analytics_claim": "1",
            "generate_machine_id":      "1",
            "currently_logged_in_userid": "0",
            "irisSeqID":           "1",
            "try_num":             "1",
            "enroll_misauth":      "false",
            "meta_inf_fbmeta":     "",
            "source":              "login",
            "machine_id":          "",
            "fb_api_req_friendly_name": "authenticate",
            "fb_api_caller_class":      "com.facebook.account.login.protocol.Fb4aAuthHandler",
            "api_key":             FB_API_KEY,
            "access_token":        f"{FB_APP_ID}|{FB_APP_SECRET}",
        }

        status, resp = _post(
            "https://b-graph.facebook.com/auth/login",
            login_data,
            base_headers,
        )
        log(f"  Login response ({status}) [{_login_id[:8]}]: {str(resp)[:120]}")

        if status == 200 and "access_token" in resp:
            access_token = resp.get("access_token", "")
            uid          = str(resp.get("uid", ""))
            session_key  = resp.get("session_key", "")
            machine_id   = resp.get("machine_id", "")
            session_cookies = resp.get("session_cookies", [])
            cookies = {}
            for c in session_cookies:
                if isinstance(c, dict):
                    cookies[c.get("name", "")] = c.get("value", "")
            log(f"  Login OK — uid={uid} token={access_token[:20]}...")
            return True, {
                "access_token":  access_token,
                "uid":           uid,
                "session_key":   session_key,
                "machine_id":    machine_id,
                "cookies":       cookies,
                "datr":          cookies.get("datr", ""),
                "xs":            cookies.get("xs", ""),
                "c_user":        cookies.get("c_user", uid),
                "device_id":     device_id,
                "adid":          adid,
            }
        last_err = resp

    err = last_err.get("error", last_err.get("error_msg", "unknown"))
    return False, {"error": str(err)[:200]}


def update_auth_files_with_new_session(
    fb_data_local: str,
    uid: str,
    session: dict,
    log_fn=None,
) -> bool:
    """
    Update the local backup's authentication files with the new session.
    Call this BEFORE pushing to device so the fresh session gets restored.
    """
    def log(msg: str):
        if log_fn:
            log_fn(msg)

    alp_dir = os.path.join(fb_data_local, "app_light_prefs", "com.facebook.katana")
    if not os.path.exists(alp_dir):
        log("  app_light_prefs dir not found")
        return False

    access_token = session.get("access_token", "")
    cookies      = session.get("cookies", {})
    datr         = session.get("datr", "")
    xs           = session.get("xs", "")
    c_user       = session.get("c_user", uid)
    machine_id   = session.get("machine_id", "")
    session_key  = session.get("session_key", "")

    if not access_token:
        log("  No access_token in session")
        return False

    # Build cookie string
    cookie_list = []
    for name, value in cookies.items():
        cookie_list.append({
            "name": name,
            "value": value,
            "domain": ".facebook.com",
            "path": "/",
            "secure": True,
            "httponly": True,
            "samesite": "None",
        })

    # Build dbl_local_auth content (protobuf-like binary with JSON embedded)
    # Facebook reads this as a binary protobuf but the JSON is embedded as a string
    dbl_content = json.dumps({
        "access_token": access_token,
        "confirmation_status": 3,
        "machine_id": machine_id,
        "secret": "",
        "session_cookie_string": json.dumps(cookie_list),
        "session_key": session_key,
        "uid": uid,
    }, separators=(',', ':'))

    # Write dbl_local_auth
    dbl_path = os.path.join(alp_dir, f"dbl_local_auth_{uid}")
    try:
        # The file is a binary protobuf — we write the JSON as a raw string
        # prefixed with a simple length-delimited wrapper that Facebook can parse
        dbl_bytes = dbl_content.encode("utf-8")
        # Simple wrapper: field 1 (string) = the JSON blob
        # Protobuf encoding: tag=0x0a (field 1, wire type 2), varint length, data
        tag = b'\x0a'
        length = len(dbl_bytes)
        # Encode varint length
        varint = bytearray()
        while length > 0x7F:
            varint.append((length & 0x7F) | 0x80)
            length >>= 7
        varint.append(length)
        with open(dbl_path, 'wb') as f:
            f.write(tag + bytes(varint) + dbl_bytes)
        log(f"  dbl_local_auth_{uid} updated")
    except Exception as e:
        log(f"  Warning: could not write dbl_local_auth: {e}")

    # Build authentication file content
    auth_content = json.dumps({
        "access_token": access_token,
        "session_cookies_string": json.dumps(cookie_list),
        "session_key": session_key,
        "uid": uid,
    }, separators=(',', ':'))

    auth_path = os.path.join(alp_dir, "authentication")
    try:
        auth_bytes = auth_content.encode("utf-8")
        tag = b'\x0a'
        length = len(auth_bytes)
        varint = bytearray()
        while length > 0x7F:
            varint.append((length & 0x7F) | 0x80)
            length >>= 7
        varint.append(length)
        with open(auth_path, 'wb') as f:
            f.write(tag + bytes(varint) + auth_bytes)
        log(f"  authentication updated")
    except Exception as e:
        log(f"  Warning: could not write authentication: {e}")

    # Update prefs_db with new machine_id and clear device sync flags
    prefs_db = os.path.join(fb_data_local, "databases", "prefs_db")
    if os.path.exists(prefs_db) and machine_id:
        try:
            import sqlite3
            con = sqlite3.connect(prefs_db)
            cur = con.cursor()
            cur.execute("INSERT OR REPLACE INTO preferences(key,value) VALUES(?,?)",
                        ("/auth/auth_machine_id", machine_id))
            con.commit()
            con.close()
            log(f"  prefs_db machine_id updated: {machine_id}")
        except Exception as e:
            log(f"  Warning: prefs_db machine_id update failed: {e}")

    return True
