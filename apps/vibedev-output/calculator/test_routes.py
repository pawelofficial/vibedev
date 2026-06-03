"""
calculator/test_routes.py
~~~~~~~~~~~~~~~~~~~~~~~~~
Unit tests for calculator/routes.py.

Tests cover:
- Blueprint creation
- GET / (index route)
- POST /calculate (calculation route)
- JSON response format
- Error handling
"""

import json
import pytest

from calculator import create_app


@pytest.fixture
def client():
    """Create a test client for the Flask app."""
    import os
    old_env = os.environ.pop("FLASK_ENV", None)
    os.environ["FLASK_ENV"] = "development"
    try:
        app = create_app()
        app.config["TESTING"] = True
        with app.test_client() as client:
            yield client
    finally:
        if old_env:
            os.environ["FLASK_ENV"] = old_env
        else:
            os.environ.pop("FLASK_ENV", None)


@pytest.fixture
def app_context():
    """Create an application context."""
    import os
    old_env = os.environ.pop("FLASK_ENV", None)
    os.environ["FLASK_ENV"] = "development"
    try:
        app = create_app()
        app.config["TESTING"] = True
        with app.app_context():
            yield app
    finally:
        if old_env:
            os.environ["FLASK_ENV"] = old_env
        else:
            os.environ.pop("FLASK_ENV", None)


class TestBlueprintCreation:
    """Test that the blueprint is properly created."""

    def test_blueprint_exists(self):
        """Test that the blueprint module can be imported."""
        from calculator.routes import bp
        assert bp is not None

    def test_blueprint_name(self):
        """Test that the blueprint has the correct name."""
        from calculator.routes import bp
        assert bp.name == "calculator"

    def test_blueprint_registered(self, app_context):
        """Test that the blueprint is registered on the app."""
        registered_blueprints = list(app_context.blueprints.keys())
        assert "calculator" in registered_blueprints


class TestIndexRoute:
    """Test the GET / route."""

    def test_index_returns_200(self, client):
        """Test that GET / returns HTTP 200."""
        response = client.get("/")
        assert response.status_code == 200

    def test_index_returns_html(self, client):
        """Test that GET / returns HTML content."""
        response = client.get("/")
        assert b"<!DOCTYPE html>" in response.data or b"<html" in response.data

    def test_index_contains_display(self, client):
        """Test that the response contains the display element."""
        response = client.get("/")
        assert b'id="display"' in response.data

    def test_index_contains_button_grid(self, client):
        """Test that the response contains the button grid."""
        response = client.get("/")
        assert b'id="btn-grid"' in response.data

    def test_index_contains_script(self, client):
        """Test that the response loads the script."""
        response = client.get("/")
        assert b"script.js" in response.data or b"script" in response.data

    def test_index_contains_style(self, client):
        """Test that the response loads the stylesheet."""
        response = client.get("/")
        assert b"style.css" in response.data or b"css" in response.data

    def test_index_content_type(self, client):
        """Test that the response has correct content type."""
        response = client.get("/")
        assert "text/html" in response.content_type


class TestCalculateRoute:
    """Test the POST /calculate route."""

    def test_calculate_success(self, client):
        """Test successful calculation."""
        response = client.post(
            "/calculate",
            json={"expression": "3 + 4"}
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert "result" in data
        assert data["result"] == "7"

    def test_calculate_float_result(self, client):
        """Test calculation with float result."""
        response = client.post(
            "/calculate",
            json={"expression": "5 / 2"}
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["result"] == "2.5"

    def test_calculate_integer_result_no_decimal(self, client):
        """Test that integer results don't have .0 suffix."""
        response = client.post(
            "/calculate",
            json={"expression": "10 / 2"}
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["result"] == "5"

    def test_calculate_negative_result(self, client):
        """Test calculation with negative result."""
        response = client.post(
            "/calculate",
            json={"expression": "3 - 10"}
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["result"] == "-7"

    def test_calculate_complex_expression(self, client):
        """Test complex expression evaluation."""
        response = client.post(
            "/calculate",
            json={"expression": "(3 + 4) * 2"}
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["result"] == "14"

    def test_calculate_exponentiation(self, client):
        """Test exponentiation."""
        response = client.post(
            "/calculate",
            json={"expression": "2 ** 10"}
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["result"] == "1024"

    def test_calculate_empty_expression(self, client):
        """Test that empty expression returns error."""
        response = client.post(
            "/calculate",
            json={"expression": ""}
        )
        assert response.status_code == 400
        data = json.loads(response.data)
        assert "error" in data
        assert "empty" in data["error"].lower()

    def test_calculate_syntax_error(self, client):
        """Test that syntax error returns HTTP 400."""
        response = client.post(
            "/calculate",
            json={"expression": "3 +"}
        )
        assert response.status_code == 400
        data = json.loads(response.data)
        assert "error" in data

    def test_calculate_division_by_zero(self, client):
        """Test that division by zero returns error."""
        response = client.post(
            "/calculate",
            json={"expression": "5 / 0"}
        )
        assert response.status_code == 400
        data = json.loads(response.data)
        assert "error" in data
        assert "zero" in data["error"].lower()

    def test_calculate_unsafe_expression(self, client):
        """Test that unsafe code is rejected."""
        response = client.post(
            "/calculate",
            json={"expression": "__import__('os')"}
        )
        assert response.status_code == 400
        data = json.loads(response.data)
        assert "error" in data

    def test_calculate_missing_expression_key(self, client):
        """Test POST with missing 'expression' key."""
        response = client.post(
            "/calculate",
            json={}
        )
        # Should evaluate empty string, which raises an error
        assert response.status_code == 400

    def test_calculate_null_expression(self, client):
        """Test POST with null expression."""
        response = client.post(
            "/calculate",
            json={"expression": None}
        )
        # None is passed to evaluate() which converts to string "None",
        # eval("None") returns None, and float(None) raises TypeError
        # This should return an error response
        assert response.status_code == 400
        data = json.loads(response.data)
        assert "error" in data

    def test_calculate_whitespace_only_expression(self, client):
        """Test expression with only whitespace."""
        response = client.post(
            "/calculate",
            json={"expression": "   "}
        )
        assert response.status_code == 400
        data = json.loads(response.data)
        assert "error" in data

    def test_calculate_response_json_format(self, client):
        """Test that success response is proper JSON."""
        response = client.post(
            "/calculate",
            json={"expression": "1 + 1"}
        )
        assert response.content_type == "application/json"
        data = json.loads(response.data)
        assert isinstance(data, dict)
        assert "result" in data

    def test_calculate_error_response_json_format(self, client):
        """Test that error response is proper JSON."""
        response = client.post(
            "/calculate",
            json={"expression": "invalid"}
        )
        assert response.content_type == "application/json"
        data = json.loads(response.data)
        assert isinstance(data, dict)
        assert "error" in data

    def test_calculate_force_json_parsing(self, client):
        """Test that JSON parsing is forced even without header."""
        response = client.post(
            "/calculate",
            data=json.dumps({"expression": "2 + 2"}),
            content_type="application/json"
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["result"] == "4"

    def test_calculate_various_operations(self, client):
        """Test various arithmetic operations."""
        test_cases = [
            ("1 + 1", "2"),
            ("5 - 3", "2"),
            ("3 * 4", "12"),
            ("10 / 2", "5"),
            ("10 % 3", "1"),
            ("2 ** 3", "8"),
        ]

        for expression, expected in test_cases:
            response = client.post(
                "/calculate",
                json={"expression": expression}
            )
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["result"] == expected, f"Failed for {expression}"

    def test_calculate_large_result(self, client):
        """Test calculation with large result."""
        response = client.post(
            "/calculate",
            json={"expression": "999 * 1000"}
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["result"] == "999000"

    def test_calculate_very_small_result(self, client):
        """Test calculation with very small result."""
        response = client.post(
            "/calculate",
            json={"expression": "1 / 1000"}
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["result"] == "0.001"


class TestRouteIntegration:
    """Test integration between routes."""

    def test_index_and_calculate_together(self, client):
        """Test that index loads and calculate works."""
        # First load the page
        response = client.get("/")
        assert response.status_code == 200

        # Then calculate
        response = client.post(
            "/calculate",
            json={"expression": "1 + 1"}
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["result"] == "2"

    def test_multiple_calculations(self, client):
        """Test multiple calculations in sequence."""
        for i in range(5):
            response = client.post(
                "/calculate",
                json={"expression": f"{i} + 1"}
            )
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["result"] == str(i + 1)
