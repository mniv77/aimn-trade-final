from flask import Blueprint
bp = Blueprint("popup_trade", __name__, url_prefix="/popup")
from .routes import *  # registers routes on bp
