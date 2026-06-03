"""
calculator/__init__.py
~~~~~~~~~~~~~~~~~~~~~~
Application factory for the Flask calculator app.

Usage::

    from calculator import create_app
    app = create_app()
"""

import os

from flask import Flask


def create_app() -> Flask:
    """Flask application factory.

    Creates and configures a :class:`flask.Flask` instance, loads
    ``SECRET_KEY`` from the environment, and registers the calculator
    blueprint.

    Raises
    ------
    RuntimeError
        If ``FLASK_ENV`` is ``'production'`` and ``SECRET_KEY`` is not set,
        preventing a silent insecure deployment.
    """
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
    )

    # ------------------------------------------------------------------
    # Secret key
    # ------------------------------------------------------------------
    secret_key = os.environ.get("SECRET_KEY")
    if os.environ.get("FLASK_ENV") == "production" and not secret_key:
        raise RuntimeError("SECRET_KEY must be set in production")
    app.config["SECRET_KEY"] = secret_key or "dev-insecure-default-key"

    # ------------------------------------------------------------------
    # Blueprint registration
    # ------------------------------------------------------------------
    from calculator.routes import bp  # noqa: PLC0415 — avoids circular import at module level

    app.register_blueprint(bp)

    return app
