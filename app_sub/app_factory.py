# app_sub/app_factory.py
import os
from flask import Flask
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from .db import db_session, Base, engine, init_db
from .services.settings import SettingsService
try:
    from .services.settings import ensure_encryption_key
except ImportError:
    def ensure_encryption_key():
        return

from .views import ui_bp, api_bp

BASE_DIR = os.path.dirname(__file__)                 # .../aimn-trade-final/app_sub
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, ".."))  # .../aimn-trade-final
TEMPLATES_DIR = os.path.join(PROJECT_ROOT, "templates")
STATIC_DIR    = os.path.join(PROJECT_ROOT, "static")

def create_app():
    # OPTIONAL popup blueprint lazy import
    popup_bp = None
    try:
        from .popup_trade import bp as popup_bp
    except Exception:
        popup_bp = None

    # ⬇️ pass the correct folders here
    app = Flask(__name__, template_folder=TEMPLATES_DIR, static_folder=STATIC_DIR)
    app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET', 'dev-secret')

    # Register blueprints
    if popup_bp is not None and 'popup_bp' not in app.blueprints:
        app.register_blueprint(popup_bp)
    if 'ui' not in app.blueprints:
        app.register_blueprint(ui_bp)
    if 'api' not in app.blueprints:
        app.register_blueprint(api_bp, url_prefix="/api")

    # DB init & warmups
    init_db(app)
    ensure_encryption_key()
    try:
        SettingsService().refresh_cache()
    except Exception:
        pass

    @app.teardown_appcontext
    def shutdown_session(exception=None):
        try:
            db_session.remove()
        except (OperationalError, SQLAlchemyError, Exception):
            pass

    # Diagnostics (inside create_app, AFTER app exists)
    @app.get("/healthz")
    def healthz():
        return "ok", 200

    return app
