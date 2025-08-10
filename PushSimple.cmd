cd C:\Users\mniv7\Documents\meir\AIMn-Trade

:: File: AIMN_Push_With_Gitignore.cmd
:: Place this file INSIDE your project folder, edit REPO, then double-click.
@echo off
setlocal enabledelayedexpansion

REM === EDIT THIS LINE (your GitHub repo URL) ===
set "REPO=https://github.com/mniv77/aimn-trade-final.git"

REM Use the folder where this script lives (no prompts)
set "PROJ=%~dp0"
cd /d "%PROJ%"

where git >nul 2>nul
if errorlevel 1 (echo Git is not installed or not on PATH.& pause & exit /b 1)

echo.
echo === Creating .gitignore if missing ===
if not exist ".gitignore" (
  (
    echo __pycache__/
    echo *.pyc
    echo .env
    echo snapshots/
    echo *.sqlite
    echo *.db
    echo .venv/
    echo env/
    echo *.log
    echo *.7z
    echo *.zip
    echo *.exe
    echo Thumbs.db
  ) > ".gitignore"
  echo .gitignore created.
) else (
  echo .gitignore already exists - leaving it unchanged.
)

echo.
echo === Initializing repo (safe if already initialized) ===
git init

echo.
echo === Staging all files ===
git add -A

echo.
echo === Committing (ok if nothing to commit) ===
git commit -m "Push (with .gitignore)"
IF ERRORLEVEL 1 echo Nothing to commit; continuing...

echo.
echo === Ensuring branch is 'main' ===
git branch -M main

echo.
echo === Setting 'origin' to %REPO% ===
git remote remove origin 2>nul
git remote add origin "%REPO%"

echo.
echo === Connecting to remote ===
git fetch origin 2>nul

echo.
echo === Pushing local HEAD to remote main (force-with-lease) ===
echo Your local will replace remote 'main' if different.
git push --force-with-lease origin HEAD:main
IF ERRORLEVEL 1 (
  echo Push failed. Check network/credentials or branch protection.
  pause
  exit /b 1
)

echo.
echo === Verify local tracked files under app\ ===
git ls-files app\

echo.
echo === Verify remote files under app\ on origin/main ===
git ls-tree -r origin/main --name-only app\

echo.
echo === Summary ===
git remote -v
git log -1 --oneline

echo.
echo Done. Your GitHub 'main' should now match this folder.
pause
endlocal