# AIMn Trading System - Git Setup Guide

## 📋 PRE-CLEANUP CHECKLIST

Before running cleanup, make sure you have:
- [ ] Backed up your `.env` file somewhere safe
- [ ] Saved any important notes from TEMP files
- [ ] Reviewed what will be deleted

## 🚀 STEP-BY-STEP PROCESS

### Step 1: Download Files from Claude
1. Download `cleanup_project.bat` 
2. Download `.gitignore_new`
3. Save both to: `C:\Users\mniv7\Documents\meir\aimn-trade-final\`

### Step 2: Backup Current .gitignore
```bash
cd C:\Users\mniv7\Documents\meir\aimn-trade-final
copy .gitignore .gitignore.old
```

### Step 3: Replace .gitignore
```bash
copy .gitignore_new .gitignore
del .gitignore_new
```

### Step 4: Run Cleanup Script
```bash
cleanup_project.bat
```

### Step 5: Verify Cleanup
```bash
# Check what files remain
dir /s /b > files_after_cleanup.txt
# Open files_after_cleanup.txt and review
```

### Step 6: Initialize Fresh Git Repo
```bash
# Remove old git (if exists)
rmdir /s /q .git

# Initialize new git
git init
git config user.name "Your Name"
git config user.email "your.email@example.com"
```

### Step 7: Stage All Clean Files
```bash
git add .
git status
# Review what will be committed
```

### Step 8: First Commit
```bash
git commit -m "Initial commit: AIMn Auto Trading System

- Core trading engine with Alpaca integration
- Multi-symbol scanner with RSI + MACD strategy
- Web dashboard with Flask
- ML research module
- Comprehensive test suite"
```

### Step 9: Create GitHub Repository
1. Go to https://github.com
2. Click "+" → "New repository"
3. Name: `aimn-trading-system`
4. Description: "AI-powered automated trading system with multi-symbol scanning"
5. Choose: **Private** (to protect your trading strategies)
6. **DO NOT** initialize with README (we already have one)
7. Click "Create repository"

### Step 10: Connect to GitHub
```bash
# Replace YOUR_USERNAME with your GitHub username
git remote add origin https://github.com/YOUR_USERNAME/aimn-trading-system.git
git branch -M main
git push -u origin main
```

### Step 11: Verify on GitHub
1. Refresh your GitHub repository page
2. You should see all your clean code
3. Verify `.env` is NOT there (it should be ignored)

## ✅ SUCCESS CHECKLIST

After completion, verify:
- [ ] Repository is on GitHub
- [ ] No `.env` or sensitive files visible
- [ ] All essential code is present
- [ ] README.md displays properly
- [ ] You can see the file tree

## 🔄 DAILY WORKFLOW (After Setup)

```bash
# Make changes to your code

# Check what changed
git status

# Stage changes
git add .

# Commit with message
git commit -m "Description of what you changed"

# Push to GitHub
git push
```

## 🆘 IF SOMETHING GOES WRONG

### Accidentally committed .env file:
```bash
# Remove from git but keep local copy
git rm --cached .env
git commit -m "Remove .env from git"
git push

# If already pushed, you may need to:
# 1. Rotate your API keys immediately
# 2. Force push (use carefully):
git push --force
```

### Need to undo last commit:
```bash
git reset --soft HEAD~1
# Your changes are still there, just uncommitted
```

### See what changed in a file:
```bash
git diff filename.py
```

## 📞 NEED HELP?

Just paste this into Claude:
"I'm at Step X in the Git setup. Here's what happened: [describe issue]"

## 🎯 NEXT STEPS AFTER GIT SETUP

Once your code is in GitHub:
1. I can review any file by asking you to share the GitHub link
2. We can collaborate more easily
3. You have version history and backups
4. You can work from multiple computers

Ready to start? Begin with Step 1! 🚀
