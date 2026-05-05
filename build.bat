@echo off
echo Building FRT v1.1.0...

:: Step 1 - PyInstaller
pyinstaller --noconfirm --onedir --windowed ^
  --name "FRT" ^
  --icon "app_icon.ico" ^
  --add-data "reactions;reactions" ^
  --add-data "logo;logo" ^
  --add-data "platform-tools;platform-tools" ^
  --add-data "vpn;vpn" ^
  --add-data "src;src" ^
  --hidden-import "qtawesome" ^
  --hidden-import "PyQt6" ^
  --hidden-import "PyQt6.QtSvg" ^
  --hidden-import "psutil" ^
  --hidden-import "requests" ^
  main.py

echo.
echo Build complete. Run Inno Setup on setup.iss to create installer.
pause
