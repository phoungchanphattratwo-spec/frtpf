@echo off
title Facebook Register Tool
cd /d "%~dp0"
python gui.py
if errorlevel 1 pause
