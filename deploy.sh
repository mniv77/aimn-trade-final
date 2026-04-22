#!/bin/bash
# Quick deploy script for PythonAnywhere
# Usage: ./deploy.sh

cd /home/MeirNiv/aimn-trade-final

echo "📥 Pulling latest changes..."
git pull origin claude/auto-trading-system-01V8yVZiFvzuwvff6hBViBgW

echo "🔄 Reloading web app..."
touch /var/www/meirniv_pythonanywhere_com_wsgi.py

echo "✅ Deploy complete!"
echo "Visit: https://meirniv.pythonanywhere.com"
