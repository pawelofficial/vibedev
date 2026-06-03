"""
calculator/test___init__.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~
Unit tests for calculator/__init__.py.

Tests cover:
- create_app() factory function
- Flask app configuration
- Blueprint registration
- Secret key handling
"""

import os
import pytest
from flask import Flask

from calculator import create_app


class TestCreateAppFactory:
    """Test the create_app factory function."""

    def test_create_app_returns_flask_app(self):
        """Test that create_app returns a Flask app instance."""
        old_env = os.environ.pop("FLASK_ENV", None)
        try:
            os.environ["FLASK_ENV"] = "development"
            app = create_app()
            assert isinstance(app, Flask)
        finally:
            if old_env:
                os.environ["FLASK_ENV"] = old_env
            else:
                os.environ.pop("FLASK_ENV", None)

    def test_create_app_imports_name(self):
        """Test that Flask app has correct import name."""
        old_env = os.environ.pop("FLASK_ENV", None)
        try:
            os.environ["FLASK_ENV"] = "development"
            app = create_app()
            assert app.name == "calculator"
        finally:
            if old_env:
                os.environ["FLASK_ENV"] = old_env
            else:
                os.environ.pop("FLASK_ENV", None)

    def test_create_app_templates_folder(self):
        """Test that app has correct template folder."""
        old_env = os.environ.pop("FLASK_ENV", None)
        try:
            os.environ["FLASK_ENV"] = "development"
            app = create_app()
            assert "templates" in app.template_folder
        finally:
            if old_env:
                os.environ["FLASK_ENV"] = old_env
            else:
                os.environ.pop("FLASK_ENV", None)

    def test_create_app_static_folder(self):
        """Test that app has correct static folder."""
        old_env = os.environ.pop("FLASK_ENV", None)
        try:
            os.environ["FLASK_ENV"] = "development"
            app = create_app()
            assert "static" in app.static_folder
        finally:
            if old_env:
                os.environ["FLASK_ENV"] = old_env
            else:
                os.environ.pop("FLASK_ENV", None)


class TestCreateAppBlueprint:
    """Test blueprint registration in create_app."""

    def test_blueprint_registered(self):
        """Test that the calculator blueprint is registered."""
        old_env = os.environ.pop("FLASK_ENV", None)
        try:
            os.environ["FLASK_ENV"] = "development"
            app = create_app()
            assert "calculator" in app.blueprints
        finally:
            if old_env:
                os.environ["FLASK_ENV"] = old_env
            else:
                os.environ.pop("FLASK_ENV", None)

    def test_blueprint_routes_registered(self):
        """Test that blueprint routes are available."""
        old_env = os.environ.pop("FLASK_ENV", None)
        try:
            os.environ["FLASK_ENV"] = "development"
            app = create_app()
            with app.test_client() as client:
                response = client.get("/")
                assert response.status_code == 200
        finally:
            if old_env:
                os.environ["FLASK_ENV"] = old_env
            else:
                os.environ.pop("FLASK_ENV", None)

    def test_multiple_app_instances(self):
        """Test that multiple app instances can be created."""
        old_env = os.environ.pop("FLASK_ENV", None)
        try:
            os.environ["FLASK_ENV"] = "development"
            app1 = create_app()
            app2 = create_app()
            assert app1 is not app2
            assert "calculator" in app1.blueprints
            assert "calculator" in app2.blueprints
        finally:
            if old_env:
                os.environ["FLASK_ENV"] = old_env
            else:
                os.environ.pop("FLASK_ENV", None)


class TestCreateAppSecretKey:
    """Test SECRET_KEY configuration."""

    def test_secret_key_from_environment(self):
        """Test that SECRET_KEY is read from environment."""
        os.environ["SECRET_KEY"] = "test-secret-key"
        try:
            app = create_app()
            assert app.config["SECRET_KEY"] == "test-secret-key"
        finally:
            del os.environ["SECRET_KEY"]

    def test_secret_key_default_dev(self):
        """Test that default key is used when not set."""
        # Make sure it's not set
        old_key = os.environ.pop("SECRET_KEY", None)
        old_env = os.environ.pop("FLASK_ENV", None)
        try:
            app = create_app()
            # In development/default, a default key should be used
            assert app.config["SECRET_KEY"] is not None
            assert app.config["SECRET_KEY"] == "dev-insecure-default-key"
        finally:
            if old_key:
                os.environ["SECRET_KEY"] = old_key
            if old_env:
                os.environ["FLASK_ENV"] = old_env

    def test_secret_key_production_without_env_var(self):
        """Test that RuntimeError is raised in production without SECRET_KEY."""
        old_env = os.environ.pop("FLASK_ENV", None)
        old_key = os.environ.pop("SECRET_KEY", None)
        try:
            os.environ["FLASK_ENV"] = "production"
            with pytest.raises(RuntimeError, match="SECRET_KEY must be set"):
                create_app()
        finally:
            if old_env:
                os.environ["FLASK_ENV"] = old_env
            if old_key:
                os.environ["SECRET_KEY"] = old_key

    def test_secret_key_production_with_env_var(self):
        """Test that production works with SECRET_KEY set."""
        old_env = os.environ.pop("FLASK_ENV", None)
        old_key = os.environ.pop("SECRET_KEY", None)
        try:
            os.environ["FLASK_ENV"] = "production"
            os.environ["SECRET_KEY"] = "production-secret-key"
            app = create_app()
            assert app.config["SECRET_KEY"] == "production-secret-key"
        finally:
            if old_env:
                os.environ["FLASK_ENV"] = old_env
            else:
                os.environ.pop("FLASK_ENV", None)
            if old_key:
                os.environ["SECRET_KEY"] = old_key
            else:
                os.environ.pop("SECRET_KEY", None)


class TestCreateAppConfiguration:
    """Test general Flask app configuration."""

    def test_app_config_is_dict(self):
        """Test that app.config is a dictionary."""
        old_env = os.environ.pop("FLASK_ENV", None)
        try:
            os.environ["FLASK_ENV"] = "development"
            app = create_app()
            assert isinstance(app.config, dict)
        finally:
            if old_env:
                os.environ["FLASK_ENV"] = old_env
            else:
                os.environ.pop("FLASK_ENV", None)

    def test_secret_key_in_config(self):
        """Test that SECRET_KEY is in app.config."""
        old_env = os.environ.pop("FLASK_ENV", None)
        try:
            os.environ["FLASK_ENV"] = "development"
            app = create_app()
            assert "SECRET_KEY" in app.config
        finally:
            if old_env:
                os.environ["FLASK_ENV"] = old_env
            else:
                os.environ.pop("FLASK_ENV", None)

    def test_testing_mode_can_be_set(self):
        """Test that testing mode can be set on the app."""
        old_env = os.environ.pop("FLASK_ENV", None)
        try:
            os.environ["FLASK_ENV"] = "development"
            app = create_app()
            app.config["TESTING"] = True
            assert app.config["TESTING"] is True
        finally:
            if old_env:
                os.environ["FLASK_ENV"] = old_env
            else:
                os.environ.pop("FLASK_ENV", None)

    def test_app_context_works(self):
        """Test that app context can be created."""
        old_env = os.environ.pop("FLASK_ENV", None)
        try:
            os.environ["FLASK_ENV"] = "development"
            app = create_app()
            with app.app_context():
                from flask import current_app
                assert current_app == app
        finally:
            if old_env:
                os.environ["FLASK_ENV"] = old_env
            else:
                os.environ.pop("FLASK_ENV", None)

    def test_test_client_works(self):
        """Test that test client can be created."""
        old_env = os.environ.pop("FLASK_ENV", None)
        try:
            os.environ["FLASK_ENV"] = "development"
            app = create_app()
            with app.test_client() as client:
                response = client.get("/")
                assert response.status_code == 200
        finally:
            if old_env:
                os.environ["FLASK_ENV"] = old_env
            else:
                os.environ.pop("FLASK_ENV", None)


class TestCreateAppTemplateLoading:
    """Test template loading functionality."""

    def test_templates_folder_exists(self):
        """Test that templates folder is configured."""
        old_env = os.environ.pop("FLASK_ENV", None)
        try:
            os.environ["FLASK_ENV"] = "development"
            app = create_app()
            # Template folder should be set
            assert app.template_folder is not None
            assert "templates" in app.template_folder
        finally:
            if old_env:
                os.environ["FLASK_ENV"] = old_env
            else:
                os.environ.pop("FLASK_ENV", None)

    def test_static_folder_exists(self):
        """Test that static folder is configured."""
        old_env = os.environ.pop("FLASK_ENV", None)
        try:
            os.environ["FLASK_ENV"] = "development"
            app = create_app()
            # Static folder should be set
            assert app.static_folder is not None
            assert "static" in app.static_folder
        finally:
            if old_env:
                os.environ["FLASK_ENV"] = old_env
            else:
                os.environ.pop("FLASK_ENV", None)


class TestCreateAppErrorHandling:
    """Test error handling in create_app."""

    def test_create_app_idempotent(self):
        """Test that calling create_app multiple times works."""
        old_env = os.environ.pop("FLASK_ENV", None)
        try:
            os.environ["FLASK_ENV"] = "development"
            app1 = create_app()
            app2 = create_app()
            app3 = create_app()

            # All should be valid Flask apps
            assert isinstance(app1, Flask)
            assert isinstance(app2, Flask)
            assert isinstance(app3, Flask)
        finally:
            if old_env:
                os.environ["FLASK_ENV"] = old_env
            else:
                os.environ.pop("FLASK_ENV", None)

    def test_create_app_thread_safe_config(self):
        """Test that app configuration is safe."""
        old_env = os.environ.pop("FLASK_ENV", None)
        try:
            os.environ["FLASK_ENV"] = "development"
            app = create_app()
            original_key = app.config["SECRET_KEY"]

            # Modifying one app doesn't affect a new one
            app.config["CUSTOM_SETTING"] = "custom"
            app2 = create_app()

            assert "CUSTOM_SETTING" not in app2.config
            assert app2.config["SECRET_KEY"] == original_key
        finally:
            if old_env:
                os.environ["FLASK_ENV"] = old_env
            else:
                os.environ.pop("FLASK_ENV", None)


class TestCreateAppIntegration:
    """Test integration aspects of create_app."""

    def test_full_request_cycle(self):
        """Test a full request-response cycle."""
        old_env = os.environ.pop("FLASK_ENV", None)
        try:
            os.environ["FLASK_ENV"] = "development"
            app = create_app()
            app.config["TESTING"] = True

            with app.test_client() as client:
                # Test GET /
                response = client.get("/")
                assert response.status_code == 200

                # Test POST /calculate
                import json
                response = client.post(
                    "/calculate",
                    json={"expression": "2 + 2"}
                )
                assert response.status_code == 200
                data = json.loads(response.data)
                assert data["result"] == "4"
        finally:
            if old_env:
                os.environ["FLASK_ENV"] = old_env
            else:
                os.environ.pop("FLASK_ENV", None)

    def test_app_blueprint_isolation(self):
        """Test that blueprints are properly isolated."""
        old_env = os.environ.pop("FLASK_ENV", None)
        try:
            os.environ["FLASK_ENV"] = "development"
            app1 = create_app()
            app2 = create_app()

            with app1.test_client() as client1:
                response = client1.get("/")
                assert response.status_code == 200

            with app2.test_client() as client2:
                response = client2.get("/")
                assert response.status_code == 200
        finally:
            if old_env:
                os.environ["FLASK_ENV"] = old_env
            else:
                os.environ.pop("FLASK_ENV", None)
