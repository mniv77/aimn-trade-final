# /wsgi.py
import sys, os
from app import create_app
# PA loads this file; ensure project on sys.path
project_root = os.path.dirname(__file__)
if project_root not in sys.path:
    sys.path.insert(0, project_root)
application = create_app()