cd C:\Users\mniv7\Documents\meir\AIMn-Trade

@echo off
setlocal enabledelayedexpansion

REM Ask for repo URL & project path (Enter = current folder)
set /p REPO=GitHub repo URL (e.g. https://github.com/USER/REPO.git): 
set /p PROJ=Project path [default: current folder]: 

if "%PROJ%"=="" set "PROJ=%cd%"
if not exist "%PROJ%" (echo Project path not found: %PROJ% & exit /b 1)

where git >nul 2>nul
if errorlevel 1 (echo Git is not installed or not on PATH.& exit /b 1)

cd /d "%PROJ%"

git init
git add -A
git commit -m "Initial push" || echo Nothing to commit, continuing...
git branch -M main

git remote remove origin 2>nul
git remote add origin "%REPO%"

echo Pushing to %REPO% ...
git push -u origin main || (
  echo Push failed (remote may have commits).
  set /p FORCE=Force replace remote with local? (y/N): 
  if /I "%FORCE%"=="Y" (git push --force-with-lease origin main) else (echo Aborted.& exit /b 1)
)

echo.
echo Done.
git remote -v
git log -1 --oneline