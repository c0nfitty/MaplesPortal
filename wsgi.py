"""
WSGI entry point for production servers (Gunicorn / Waitress).

Start with Gunicorn:
    gunicorn --bind 127.0.0.1:8080 --workers 2 wsgi:application

Start with Waitress (preferred on IBM i PASE if Gunicorn is unavailable):
    waitress-serve --host=127.0.0.1 --port=8080 wsgi:application
"""
import os
import sys

# Ensure the portal root is on the Python path when running via wsgi.py directly.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app

application = create_app(os.environ.get("PORTAL_ENV", "production"))

if __name__ == "__main__":
    # Development only — do not use Flask's dev server in production.
    application.run(host="0.0.0.0", port=4050, debug=True)
