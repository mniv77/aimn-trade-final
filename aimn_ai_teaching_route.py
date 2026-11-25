
"""Research-only AIMn teaching page. No trading endpoints."""

from flask import render_template


def register_aimn_ai_teaching_route(app):
    @app.get("/aimn_ai_teaching")
    def aimn_ai_teaching_page():
        return render_template("aimn_ai_teaching.html")
