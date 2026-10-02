@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0trocar-senha.ps1"
if errorlevel 1 pause
