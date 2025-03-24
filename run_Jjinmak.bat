@echo off
cd /d "%~dp0"
powershell -Command "Start-Process pythonw -ArgumentList 'main.py' -Verb RunAs"
