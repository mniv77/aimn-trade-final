# /wsgi.py
import os, re

import sys
sys.path.insert(0, '/home/MeirNiv/aimn-trade-final')
sys.path.insert(0, '/home/MeirNiv')  # (optional, for direct access to AImnMLResearch)





# load .env and ~/.aimn_env (no errors if missing)
for _env_file in (os.path.join(os.path.dirname(__file__), '.env'),
                  os.path.expanduser('~/.aimn_env')):
    try:
        with open(_env_file, 'r') as f:
            for line in f:
                m = re.match(r'^\s*(?:export\s+)?([A-Z0-9_]+)\s*=\s*(.*)\s*$', line)
                if not m:
                    continue
                k, v = m.group(1), m.group(2).strip()
                if (v.startswith("'") and v.endswith("'")) or (v.startswith('"') and v.endswith('"')):
                    v = v[1:-1]
                os.environ.setdefault(k, v)
    except FileNotFoundError:
        pass

# import create_app from the shimmed package "app"
try:
    from app import create_app
except Exception:
    from app_sub import create_app
application = create_app()





