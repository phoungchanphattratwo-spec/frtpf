"""
Application-wide constants.
"""

APP_NAME = "Facebook Register Tool"
APP_VERSION = "2.2.1"
APP_PUBLISHER = "KLS"

# Facebook package names
FB_LITE_PACKAGE = "com.facebook.lite"
FB_KATANA_PACKAGE = "com.facebook.katana"

# MaxChange package
MAXCHANGE_PACKAGE = "com.minsoftware.maxchanger"

# Appium server
APPIUM_SERVER_URL = "http://127.0.0.1:4723"

# Account backup folder name pattern: {uid}_{timestamp}
BACKUP_FOLDER_PATTERN = r"^\d+_\d{8}_\d{6}_\d+"

# Supported import file extensions
IMPORT_EXTENSIONS = [".csv", ".json"]

# Default registration values
DEFAULT_BIRTHDAY = "15/06/1995"
DEFAULT_GENDER = "Male"
DEFAULT_ACTION_DELAY = 2.0
