"""
run.py
~~~~~~
Top-level development entry point for the Flask calculator app.

Not intended for production use — point a WSGI server (e.g. gunicorn) at
the ``calculator:create_app`` factory instead.
"""

import os

from calculator import create_app


def main() -> None:
    """Create the Flask app and start the development server on port 5000."""
    os.environ.setdefault("FLASK_ENV", "development")
    app = create_app()
    app.run(debug=True, port=5000)


if __name__ == "__main__":
    main()
