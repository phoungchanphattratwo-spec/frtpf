@echo off
REM ============================================================================
REM  Inno Setup Build Script with Deep Validation
REM  Facebook Register Tool - Automated Installer Builder
REM ============================================================================

setlocal enabledelayedexpansion

echo.
echo ========================================================================
echo   Facebook Register Tool - Installer Build Script
echo ========================================================================
echo.

REM Check if running as administrator
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [ERROR] This script requires Administrator privileges!
    echo Please right-click and select "Run as administrator"
    pause
    exit /b 1
)

echo [1/5] Running deep validation checks...
echo.
python validate_setup.py
if %errorLevel% neq 0 (
    echo.
    echo [ERROR] Validation failed! Please fix the errors above.
    pause
    exit /b 1
)

echo.
echo ========================================================================
echo [2/5] Validation passed! Preparing to build installer...
echo ========================================================================
echo.

REM Check for Inno Setup
set ISCC_PATH=
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" (
    set ISCC_PATH=C:\Program Files (x86)\Inno Setup 6\ISCC.exe
) else if exist "C:\Program Files\Inno Setup 6\ISCC.exe" (
    set ISCC_PATH=C:\Program Files\Inno Setup 6\ISCC.exe
) else (
    echo [ERROR] Inno Setup not found!
    echo Please install Inno Setup 6 from: https://jrsoftware.org/isdl.php
    pause
    exit /b 1
)

echo [3/5] Found Inno Setup: %ISCC_PATH%
echo.

REM Create output directory if it doesn't exist
set OUTPUT_DIR=C:\Users\KLS COMPUTER\Desktop\FRT_Output
if not exist "%OUTPUT_DIR%" (
    echo [4/5] Creating output directory: %OUTPUT_DIR%
    mkdir "%OUTPUT_DIR%"
) else (
    echo [4/5] Output directory exists: %OUTPUT_DIR%
)
echo.

REM Build the installer
echo [5/5] Building installer with Inno Setup...
echo.
echo ========================================================================
"%ISCC_PATH%" setup.iss
echo ========================================================================

if %errorLevel% equ 0 (
    echo.
    echo ========================================================================
    echo   SUCCESS! Installer built successfully!
    echo ========================================================================
    echo.
    echo Output location: %OUTPUT_DIR%
    echo.
    
    REM List generated files
    echo Generated files:
    dir /b "%OUTPUT_DIR%\FRT_Setup_*.exe" 2>nul
    
    echo.
    echo Opening output folder...
    explorer "%OUTPUT_DIR%"
    
    echo.
    echo Build completed successfully!
) else (
    echo.
    echo ========================================================================
    echo   ERROR! Installer build failed!
    echo ========================================================================
    echo.
    echo Please check the error messages above.
)

echo.
pause
