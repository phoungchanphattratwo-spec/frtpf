# Installer Directory

This directory contains installer scripts and configuration files for building the Facebook Register Tool installer.

## Structure

```
installer/
├── README.md           # This file
├── build_installer.py  # Script to build the installer
├── config.json         # Installer configuration
└── assets/            # Installer assets (icons, images)
```

## Building the Installer

1. Ensure all dependencies are installed
2. Run the build script:
   ```bash
   python installer/build_installer.py
   ```
3. The installer will be created in the `releases/` directory

## Requirements

- Python 3.8+
- PyInstaller
- Inno Setup (for Windows installer)

## Notes

- The installer will include all necessary dependencies
- License activation is required on first run
- Supports Windows 10/11
