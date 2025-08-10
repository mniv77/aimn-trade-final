# README.md (PythonAnywhere quick steps)
ALPACA_SECRET_KEY=optional_for_data_only

# 1) Clone on PA:  git clone https://github.com/YOU/aimn.git
# 2) venv:         python3.10 -m venv ~/.venvs/aimn && source ~/.venvs/aimn/bin/activate
# 3) install:      pip install -r requirements.txt
# 4) Web app:      set WSGI file -> /home/USER/aimn/wsgi.py ; add env vars in "Web" tab
# 5) DB seed:      in Bash console: source ~/.venvs/aimn/bin/activate && python scripts/bootstrap_seed.py
# 6) Always-on:    command -> source ~/.venvs/aimn/bin/activate && python run_worker.py
# 7) Open site:    visit your PA domain; set Alpaca keys in UI; tune params; use Bulk Apply.

# commit & push (run locally)
git init
git add .
git commit -m "AIMn Flask dashboard + worker + TV-style tuning + snapshots"
git branch -M main
git remote add origin https://github.com/YOUR_USER/aimn.git
git push -u origin main
