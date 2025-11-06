@echo off
echo ============================================================
echo AIMn Trading System - Project Cleanup Script
echo ============================================================
echo.
echo This will DELETE junk files before Git commit
echo.
pause

cd /d C:\Users\mniv7\Documents\meir\aimn-trade-final

echo.
echo [1/8] Removing Python cache files...
rmdir /s /q __pycache__ 2>nul
rmdir /s /q .pytest_cache 2>nul
for /d /r . %%d in (__pycache__) do @if exist "%%d" rmdir /s /q "%%d"
del /s /q *.pyc 2>nul

echo [2/8] Removing virtual environment...
rmdir /s /q .venv 2>nul

echo [3/8] Removing backup files...
rmdir /s /q app_backup2 2>nul
del /q app_backup.py 2>nul
del /q app.py.bak.* 2>nul
del /q app_bak*.py 2>nul
del /q *_bak.* 2>nul
del /q *-bak* 2>nul
del /q *_OLD*.* 2>nul
del /q *BACKUP*.* 2>nul

echo [4/8] Removing temp files...
del /q "TEMP SAVE" 2>nul
del /q "Temp Save 2" 2>nul
del /q "=0.2.40" 2>nul
del /q py 2>nul
del /q "temp_ app" 2>nul

echo [5/8] Removing log files...
del /q data\aimn_crypto_trading.log 2>nul

echo [6/8] Removing database files...
del /q aimn.db 2>nul
del /q popup.sqlite3 2>nul

echo [7/8] Removing old project backup...
del /q project-backup.zip 2>nul

echo [8/8] Cleaning up templates backup files...
del /q templates\*_OLD*.html 2>nul
del /q templates\backup-*.html 2>nul

echo.
echo ============================================================
echo Cleanup Complete!
echo ============================================================
echo.
echo Next steps:
echo 1. Review the changes
echo 2. Run: git status
echo 3. Run: git add .
echo 4. Run: git commit -m "Initial clean commit - AIMn Trading System"
echo 5. Create GitHub repo and push
echo.
pause
