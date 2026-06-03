"""
test_run.py
~~~~~~~~~~~
Unit tests for run.py.

Tests cover:
- main() function
- Environment variable handling
- Flask app creation and startup
"""

import os
import pytest
from unittest.mock import patch, MagicMock

from run import main


class TestMainFunction:
    """Test the main() function."""

    @patch("run.create_app")
    def test_main_creates_app(self, mock_create_app):
        """Test that main() calls create_app()."""
        mock_app = MagicMock()
        mock_create_app.return_value = mock_app

        # Mock app.run to prevent it from starting
        mock_app.run = MagicMock()

        main()

        mock_create_app.assert_called_once()

    @patch("run.create_app")
    def test_main_sets_flask_env(self, mock_create_app):
        """Test that main() sets FLASK_ENV to development."""
        old_env = os.environ.get("FLASK_ENV")
        try:
            # Remove it if it exists
            if "FLASK_ENV" in os.environ:
                del os.environ["FLASK_ENV"]

            mock_app = MagicMock()
            mock_create_app.return_value = mock_app
            mock_app.run = MagicMock()

            main()

            # Check that FLASK_ENV was set to 'development'
            assert os.environ.get("FLASK_ENV") == "development"
        finally:
            # Restore original state
            if old_env:
                os.environ["FLASK_ENV"] = old_env
            elif "FLASK_ENV" in os.environ:
                del os.environ["FLASK_ENV"]

    @patch("run.create_app")
    def test_main_calls_app_run(self, mock_create_app):
        """Test that main() calls app.run()."""
        mock_app = MagicMock()
        mock_create_app.return_value = mock_app

        main()

        mock_app.run.assert_called_once()

    @patch("run.create_app")
    def test_main_app_run_debug_enabled(self, mock_create_app):
        """Test that debug mode is enabled."""
        mock_app = MagicMock()
        mock_create_app.return_value = mock_app

        main()

        # Check that run was called with debug=True
        mock_app.run.assert_called_once()
        call_kwargs = mock_app.run.call_args.kwargs
        assert call_kwargs.get("debug") is True

    @patch("run.create_app")
    def test_main_app_run_port(self, mock_create_app):
        """Test that port 5000 is specified."""
        mock_app = MagicMock()
        mock_create_app.return_value = mock_app

        main()

        # Check that run was called with port=5000
        call_kwargs = mock_app.run.call_args.kwargs
        assert call_kwargs.get("port") == 5000

    @patch("run.create_app")
    def test_main_app_run_parameters(self, mock_create_app):
        """Test all parameters passed to app.run()."""
        mock_app = MagicMock()
        mock_create_app.return_value = mock_app

        main()

        # Get the call arguments
        assert mock_app.run.call_count == 1
        call_kwargs = mock_app.run.call_args.kwargs
        assert call_kwargs == {"debug": True, "port": 5000}


class TestMainIntegration:
    """Integration tests for main()."""

    @patch("run.create_app")
    def test_main_with_real_app_creation(self, mock_create_app):
        """Test main with actual app creation."""
        os.environ["FLASK_ENV"] = "development"
        from calculator import create_app
        real_app = create_app()
        mock_create_app.return_value = real_app

        # Mock run to prevent server startup
        with patch.object(real_app, "run") as mock_run:
            main()
            mock_run.assert_called_once_with(debug=True, port=5000)

    def test_main_flask_env_setdefault(self):
        """Test that FLASK_ENV uses setdefault."""
        old_env = os.environ.get("FLASK_ENV")
        try:
            if "FLASK_ENV" in os.environ:
                del os.environ["FLASK_ENV"]

            with patch("run.create_app") as mock_create_app:
                mock_app = MagicMock()
                mock_create_app.return_value = mock_app
                mock_app.run = MagicMock()

                main()

                # After main(), FLASK_ENV should be set
                assert os.environ["FLASK_ENV"] == "development"
        finally:
            if old_env:
                os.environ["FLASK_ENV"] = old_env
            elif "FLASK_ENV" in os.environ:
                del os.environ["FLASK_ENV"]


class TestMainFunctionSignature:
    """Test the main function signature."""

    def test_main_is_callable(self):
        """Test that main is callable."""
        assert callable(main)

    @patch("run.create_app")
    def test_main_returns_none(self, mock_create_app):
        """Test that main returns None."""
        mock_app = MagicMock()
        mock_create_app.return_value = mock_app
        mock_app.run = MagicMock()

        result = main()

        assert result is None

    @patch("run.create_app")
    def test_main_takes_no_arguments(self, mock_create_app):
        """Test that main takes no arguments."""
        mock_app = MagicMock()
        mock_create_app.return_value = mock_app
        mock_app.run = MagicMock()

        # This should not raise any exception
        main()


class TestRunModuleStructure:
    """Test the structure of the run module."""

    def test_run_module_has_main(self):
        """Test that run module has main function."""
        import run
        assert hasattr(run, "main")

    def test_run_module_has_name_check(self):
        """Test that run module has __name__ check."""
        import run
        # The module should have the conditional check
        import inspect
        source = inspect.getsource(run)
        assert '__name__ == "__main__"' in source

    def test_create_app_import(self):
        """Test that create_app is imported in run module."""
        import run
        assert hasattr(run, "create_app")


class TestMainEnvironmentHandling:
    """Test environment variable handling in main()."""

    @patch("run.create_app")
    def test_main_preserves_other_env_vars(self, mock_create_app):
        """Test that main doesn't override other environment variables."""
        os.environ["TEST_VAR"] = "test_value"
        old_flask_env = os.environ.get("FLASK_ENV")

        try:
            mock_app = MagicMock()
            mock_create_app.return_value = mock_app
            mock_app.run = MagicMock()

            main()

            # TEST_VAR should still be there
            assert os.environ["TEST_VAR"] == "test_value"
        finally:
            del os.environ["TEST_VAR"]
            if old_flask_env:
                os.environ["FLASK_ENV"] = old_flask_env

    @patch("run.create_app")
    def test_main_respects_existing_flask_env(self, mock_create_app):
        """Test that setdefault respects existing FLASK_ENV."""
        old_env = os.environ.get("FLASK_ENV")
        try:
            os.environ["FLASK_ENV"] = "custom"

            mock_app = MagicMock()
            mock_create_app.return_value = mock_app
            mock_app.run = MagicMock()

            main()

            # setdefault should not override existing value
            assert os.environ["FLASK_ENV"] == "custom"
        finally:
            if old_env:
                os.environ["FLASK_ENV"] = old_env
            else:
                os.environ.pop("FLASK_ENV", None)
