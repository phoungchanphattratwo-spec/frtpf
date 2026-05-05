"""One-shot script: replace the appium module-level import in gui.py with a lazy loader."""
import re

with open('gui.py', encoding='utf-8') as f:
    content = f.read()

# Match the entire appium block (from the 'from appium' line through the except block)
pattern = re.compile(
    r'from appium import webdriver.*?AppiumBy\s*=\s*None.*?# type: ignore\[assignment,misc\]',
    re.DOTALL
)

replacement = (
    "# Appium fully lazy — call _ensure_appium_imported() before any automation\n"
    "# Importing appium at module level costs 300-700ms cold-start (Selenium chain)\n"
    "UiAutomator2Options = None\n"
    "AppiumBy = None\n"
    "_appium_webdriver_module = None\n"
    "\n"
    "def _ensure_appium_imported():\n"
    "    \"\"\"Lazy-load Appium. Call once before starting an automation session.\"\"\"\n"
    "    global UiAutomator2Options, AppiumBy, _appium_webdriver_module\n"
    "    if _appium_webdriver_module is not None:\n"
    "        return\n"
    "    try:\n"
    "        from appium import webdriver as _wd\n"
    "        from appium.options.android import UiAutomator2Options as _opts\n"
    "        from appium.webdriver.common.appiumby import AppiumBy as _by\n"
    "        _appium_webdriver_module = _wd\n"
    "        UiAutomator2Options = _opts\n"
    "        AppiumBy = _by\n"
    "    except ImportError as exc:\n"
    "        print(f'[Appium] Import failed: {exc}')"
)

new_content, n = pattern.subn(replacement, content, count=1)
if n == 0:
    print("ERROR: pattern not found — dumping context around 'appium'")
    idx = content.find('appium')
    print(repr(content[max(0,idx-20):idx+300]))
else:
    with open('gui.py', 'w', encoding='utf-8') as f:
        f.write(new_content)
    print(f"OK: replaced {n} occurrence(s)")
