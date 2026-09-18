"""Gunicorn entry point. Only the bundled synthetic demo data is read."""
from webapp import create_app

app = create_app()
