# shim so "from app import create_app" still works
from app_sub import create_app  # re-export
