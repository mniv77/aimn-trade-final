# /app/__init__.py
from flask import Flask
from .db import init_db, db_session
from .views import ui_bp, api_bp
from .security import ensure_encryption_key
from .services.settings import SettingsService

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET', 'dev-secret')  # set on PA
    app.register_blueprint(ui_bp)
    app.register_blueprint(api_bp, url_prefix="/api")
    init_db(app)
    ensure_encryption_key()
    # warm cache
    SettingsService().refresh_cache()
    @app.teardown_appcontext
    def shutdown_session(exception=None):
        db_session.remove()
    return app