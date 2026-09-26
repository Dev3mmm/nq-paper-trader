@echo off
cd /d "%~dp0"
python paper_trader.py
copy /Y dashboard.html index.html >nul
git add -A
git commit -m "Update dashboard" 
git push
