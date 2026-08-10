"""
Entry point for a real web host.

Hosting platforms do not run `python -m backend.app` — they look for a variable
called `application` and serve it themselves. This file provides that.

On PythonAnywhere, point the WSGI configuration file at this one. On a host that
uses gunicorn (Render, Railway, a plain server), the start command is:

    gunicorn wsgi:application

Both cases are covered step by step in docs/hosting.md.
"""

import os
import sys
from pathlib import Path

# Make sure the project directory is importable no matter where the host starts
# the process from.
PROJECT_DIR = Path(__file__).resolve().parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from backend.app import app as application  # noqa: E402

# Some hosts terminate HTTPS in front of the app and forward the original scheme
# in a header. Without this, Flask would think requests arrived over plain HTTP
# and would refuse to set secure cookies.
try:
    from werkzeug.middleware.proxy_fix import ProxyFix

    application.wsgi_app = ProxyFix(
        application.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1
    )
except ImportError:  # pragma: no cover
    pass

if __name__ == "__main__":
    application.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
