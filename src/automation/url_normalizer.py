"""
Facebook URL normalizer.

Converts any Facebook URL variant into a canonical https://www.facebook.com/...
URL and returns a human-readable type label.

Usage:
    from src.automation.url_normalizer import normalize_facebook_url, URL_TYPE_LABELS

    url, url_type = normalize_facebook_url("https://fb.me/AbCdEfG")
    label, color = URL_TYPE_LABELS[url_type]
"""

from __future__ import annotations
import re
import urllib.parse


# ── Type → (display label, badge colour) ─────────────────────────────────────
URL_TYPE_LABELS: dict[str, tuple[str, str]] = {
    "post":        ("📄 Post",         "#4CAF50"),
    "photo":       ("🖼 Photo",         "#2196F3"),
    "video":       ("🎬 Video",         "#9C27B0"),
    "reel":        ("🎞 Reel",          "#E91E63"),
    "story":       ("📖 Story",         "#FF9800"),
    "group_post":  ("👥 Group Post",    "#00BCD4"),
    "event":       ("📅 Event",         "#FF5722"),
    "marketplace": ("🛒 Marketplace",   "#795548"),
    "share_link":  ("🔗 Share Link",    "#607D8B"),
    "profile":     ("👤 Profile/Page",  "#9E9E9E"),
    "unknown":     ("🔗 URL",           "#888888"),
}

# Tracking / noise query-string params that should be stripped
_NOISE_PARAMS = frozenset({"__cft__", "__tn__", "mibextid", "ref", "refid"})
_KEEP_PARAMS  = frozenset({"story_fbid", "id", "fbid", "v", "set", "type"})


def normalize_facebook_url(raw: str) -> tuple[str, str]:
    """
    Normalize any Facebook URL / post-ID into a canonical
    ``https://www.facebook.com/...`` URL.

    Supported input formats
    ───────────────────────
    Bare numeric ID          123456789
    Bare permalink           username/posts/123
    Standard post            https://www.facebook.com/username/posts/123456
    Permalink                https://www.facebook.com/permalink.php?story_fbid=123&id=456
    Photo                    https://www.facebook.com/photo.php?fbid=123
    Video / Watch            https://www.facebook.com/watch/?v=123
    Reel                     https://www.facebook.com/reel/123456
    Story                    https://www.facebook.com/stories/user/123
    Group post               https://www.facebook.com/groups/name/posts/123
    Event                    https://www.facebook.com/events/123456
    Marketplace              https://www.facebook.com/marketplace/item/123
    Share short link         https://www.facebook.com/share/p/XXXX
    Shortened fb.me          https://fb.me/XXXX
    Mobile m.facebook.com    https://m.facebook.com/...
    l.facebook.com redirect  https://l.facebook.com/l.php?u=...

    Returns:
        (canonical_url, url_type)  where url_type is a key in URL_TYPE_LABELS.
    """
    url = raw.strip()
    if not url:
        return url, "unknown"

    # 1. Bare numeric post ID
    if re.fullmatch(r"\d{10,20}", url):
        return (
            f"https://www.facebook.com/permalink.php?story_fbid={url}&id={url}",
            "post",
        )

    # 2. Bare "username/posts/ID" — prepend scheme + host
    if not url.startswith("http") and "/" in url:
        url = "https://www.facebook.com/" + url.lstrip("/")

    # 3. Unwrap l.facebook.com redirect first
    lredirect = re.match(r"^https?://l\.facebook\.com/l\.php\?u=([^&]+)", url)
    if lredirect:
        return normalize_facebook_url(urllib.parse.unquote(lredirect.group(1)))

    # 4. Normalise host variants → www.facebook.com
    url = re.sub(r"^https?://(m\.|touch\.)?facebook\.com", "https://www.facebook.com", url)
    url = re.sub(r"^https?://fb\.me",  "https://www.facebook.com", url)
    url = re.sub(r"^https?://m\.me",   "https://www.facebook.com", url)

    # 5. Parse
    try:
        parsed = urllib.parse.urlparse(url)
        path   = parsed.path.rstrip("/")
        qs     = urllib.parse.parse_qs(parsed.query)
    except Exception:
        return url, "unknown"

    # 6. Strip noise params
    clean_qs = {k: v for k, v in qs.items() if k in _KEEP_PARAMS}

    def _rebuild(p: str, params: dict | None = None) -> str:
        q = urllib.parse.urlencode(
            {k: v[0] for k, v in (params or {}).items()}, doseq=False
        )
        return "https://www.facebook.com" + p + (f"?{q}" if q else "")

    # 7. Pattern matching ─────────────────────────────────────────────────────

    # /share/p/TOKEN  /share/v/TOKEN  /share/TOKEN
    if re.match(r"^/share(?:/[pv])?/[A-Za-z0-9_-]+$", path):
        return _rebuild(path), "share_link"

    # /permalink.php?story_fbid=X&id=Y
    if path == "/permalink.php" and "story_fbid" in qs:
        return _rebuild(path, {k: qs[k] for k in ("story_fbid", "id") if k in qs}), "post"

    # /photo.php?fbid=X  or  /photo/?fbid=X  or  /photo/X
    if path in ("/photo.php", "/photo") or path.startswith("/photo/"):
        if "fbid" in qs:
            return _rebuild("/photo.php", {"fbid": qs["fbid"]}), "photo"
        m = re.match(r"^/photo/(\d+)", path)
        if m:
            return _rebuild(f"/photo/{m.group(1)}"), "photo"
        return _rebuild(path, clean_qs), "photo"

    # /video.php?v=X  or  /watch/?v=X  or  /watch/X
    if path in ("/video.php", "/watch") or path.startswith("/watch/"):
        if "v" in qs:
            return _rebuild("/watch/", {"v": qs["v"]}), "video"
        m = re.match(r"^/watch/(\d+)", path)
        if m:
            return _rebuild(f"/watch/?v={m.group(1)}"), "video"
        return _rebuild(path, clean_qs), "video"

    # /reel/ID
    m = re.match(r"^/reel/(\d+)", path)
    if m:
        return _rebuild(f"/reel/{m.group(1)}"), "reel"

    # /stories/USER/ID  or  /stories/highlights/ID
    if path.startswith("/stories/"):
        return _rebuild(path), "story"

    # /groups/NAME/posts/ID  or  /groups/NAME/permalink/ID
    if re.match(r"^/groups/[^/]+/(posts|permalink)/\d+", path):
        return _rebuild(path), "group_post"

    # /events/ID
    m = re.match(r"^/events/(\d+)", path)
    if m:
        return _rebuild(f"/events/{m.group(1)}"), "event"

    # /marketplace/item/ID
    m = re.match(r"^/marketplace/item/(\d+)", path)
    if m:
        return _rebuild(f"/marketplace/item/{m.group(1)}"), "marketplace"

    # /USERNAME/posts/ID  or  /USERNAME/videos/ID  or  /USERNAME/photos/ID
    m = re.match(r"^/([^/]+)/(posts|videos|photos)/(\d+)", path)
    if m:
        utype = {"posts": "post", "videos": "video", "photos": "photo"}.get(m.group(2), "post")
        return _rebuild(path), utype

    # /USERNAME/  — profile or page
    if re.match(r"^/[A-Za-z0-9._-]+$", path):
        return _rebuild(path), "profile"

    # Fallback
    return _rebuild(path, clean_qs), "unknown"
