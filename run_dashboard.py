# /aimn-trade-final/run_dashboard.py
import subprocess
import webbrowser
import time
import os

# Change to the correct directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Start the Flask dashboard
dashboard = subprocess.Popen(['python', 'app.py'])

# Wait for server to start
time.sleep(2)

# Open in browser
webbrowser.open('http://localhost:5000')

print("🚀 AIMn Dashboard running at http://localhost:5000")
print("Press Ctrl+C to stop")

try:
    dashboard.wait()
except KeyboardInterrupt:
    dashboard.terminate()
    print("\n👋 Dashboard stopped")