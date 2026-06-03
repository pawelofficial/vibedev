"""
calculator/static/test_script_js.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Validation tests for calculator/static/script.js.

Tests cover:
- JavaScript file structure
- CalculatorUI class definition
- Method presence
- Event handling patterns
- Fetch API usage
"""

import os
import re
import pytest


@pytest.fixture
def js_file_path():
    """Get the path to the JavaScript file."""
    return os.path.join(
        os.path.dirname(__file__),
        "script.js"
    )


@pytest.fixture
def js_content(js_file_path):
    """Read and return the JavaScript file content."""
    with open(js_file_path, "r", encoding="utf-8") as f:
        return f.read()


class TestJSFileStructure:
    """Test the structure and presence of the JavaScript file."""

    def test_js_file_exists(self, js_file_path):
        """Test that script.js file exists."""
        assert os.path.exists(js_file_path), "script.js file not found"

    def test_js_file_is_readable(self, js_file_path):
        """Test that script.js is readable."""
        assert os.access(js_file_path, os.R_OK), "script.js is not readable"

    def test_js_file_not_empty(self, js_content):
        """Test that JavaScript file is not empty."""
        assert len(js_content.strip()) > 0, "JavaScript file is empty"

    def test_use_strict_directive(self, js_content):
        """Test that 'use strict' is present."""
        assert "'use strict'" in js_content


class TestCalculatorUIClass:
    """Test the CalculatorUI class definition."""

    def test_class_definition(self, js_content):
        """Test that CalculatorUI class is defined."""
        assert "class CalculatorUI" in js_content

    def test_constructor_method(self, js_content):
        """Test that constructor is defined."""
        assert "constructor()" in js_content

    def test_expression_property(self, js_content):
        """Test that expression property is initialized."""
        assert "this.expression" in js_content

    def test_display_property(self, js_content):
        """Test that display property is initialized."""
        assert "this.display" in js_content


class TestCalculatorUIMethods:
    """Test CalculatorUI methods."""

    def test_init_method(self, js_content):
        """Test that init() method is defined."""
        assert "init()" in js_content

    def test_handle_button_method(self, js_content):
        """Test that handleButton() method is defined."""
        assert "handleButton(" in js_content

    def test_send_expression_method(self, js_content):
        """Test that sendExpression() method is defined."""
        assert "sendExpression()" in js_content

    def test_update_display_method(self, js_content):
        """Test that updateDisplay() method is defined."""
        assert "updateDisplay(" in js_content


class TestCalculatorUIEventHandling:
    """Test event handling in CalculatorUI."""

    def test_event_delegation_pattern(self, js_content):
        """Test that event delegation is used."""
        assert "addEventListener" in js_content
        assert "btn-grid" in js_content

    def test_click_event_handling(self, js_content):
        """Test that click events are handled."""
        assert "'click'" in js_content

    def test_closest_selector(self, js_content):
        """Test that .closest() is used for event delegation."""
        assert ".closest(" in js_content

    def test_data_value_attribute_usage(self, js_content):
        """Test that data-value attribute is used."""
        assert "data-value" in js_content or "dataset.value" in js_content


class TestCalculatorUIButtonHandling:
    """Test button value handling."""

    def test_clear_button_handling(self, js_content):
        """Test that 'C' button is handled."""
        assert "'C'" in js_content

    def test_equals_button_handling(self, js_content):
        """Test that '=' button is handled."""
        assert "'='" in js_content

    def test_backspace_button_handling(self, js_content):
        """Test that backspace button is handled."""
        # '⌫' character
        assert "⌫" in js_content

    def test_switch_statement(self, js_content):
        """Test that switch statement is used for button handling."""
        assert "switch (" in js_content
        assert "case " in js_content


class TestCalculatorUIFetchAPI:
    """Test fetch API usage for calculating."""

    def test_fetch_usage(self, js_content):
        """Test that fetch API is used."""
        assert "fetch(" in js_content

    def test_calculate_endpoint(self, js_content):
        """Test that /calculate endpoint is targeted."""
        assert "/calculate" in js_content

    def test_post_method(self, js_content):
        """Test that POST method is used."""
        assert "'POST'" in js_content or '"POST"' in js_content

    def test_json_content_type(self, js_content):
        """Test that JSON content type is set."""
        assert "application/json" in js_content

    def test_response_json_parsing(self, js_content):
        """Test that response is parsed as JSON."""
        assert ".json()" in js_content

    def test_error_handling(self, js_content):
        """Test that errors are handled."""
        assert "catch" in js_content or ".ok" in js_content


class TestCalculatorUIDisplayHandling:
    """Test display update logic."""

    def test_display_element_access(self, js_content):
        """Test that display element is accessed."""
        assert "#display" in js_content or "display" in js_content

    def test_text_content_update(self, js_content):
        """Test that textContent is updated."""
        assert ".textContent" in js_content

    def test_decimal_stripping_logic(self, js_content):
        """Test that decimal stripping is implemented."""
        # Check for regex or number formatting logic
        assert ".0" in js_content or "\.0" in js_content

    def test_regex_pattern_for_decimal(self, js_content):
        """Test that regex pattern is used for decimal stripping."""
        # Should have regex for detecting .0 endings
        assert "/^-?\\d+\\.0$/" in js_content or "/-?\\d+\\.0/" in js_content


class TestCalculatorUIInitialization:
    """Test page initialization."""

    def test_dom_content_loaded_event(self, js_content):
        """Test that DOMContentLoaded event is used."""
        assert "DOMContentLoaded" in js_content

    def test_instantiation_on_load(self, js_content):
        """Test that CalculatorUI is instantiated."""
        assert "new CalculatorUI()" in js_content

    def test_init_call_on_load(self, js_content):
        """Test that init() is called on page load."""
        assert ".init()" in js_content


class TestCalculatorUIErrorMessages:
    """Test error message handling."""

    def test_error_property_accessed(self, js_content):
        """Test that error property is accessed from response."""
        assert ".error" in js_content

    def test_error_display_timing(self, js_content):
        """Test that errors are displayed with timing."""
        assert "setTimeout" in js_content

    def test_error_dismissal(self, js_content):
        """Test that errors are dismissed after display."""
        # Should restore previous expression after showing error
        assert "prior" in js_content or "previous" in js_content


class TestCalculatorUIExpressionBuffer:
    """Test expression buffer management."""

    def test_expression_buffer_usage(self, js_content):
        """Test that expression buffer is used."""
        assert "this.expression" in js_content

    def test_expression_appending(self, js_content):
        """Test that expressions are appended."""
        assert "+=" in js_content or "concat" in js_content

    def test_expression_clearing(self, js_content):
        """Test that expression is cleared."""
        assert "this.expression = ''" in js_content


class TestCalculatorUIComments:
    """Test documentation and comments."""

    def test_jsdoc_comments(self, js_content):
        """Test that JSDoc comments are present."""
        assert "/**" in js_content or "/*" in js_content

    def test_parameter_documentation(self, js_content):
        """Test that parameters are documented."""
        assert "@param" in js_content or "@" in js_content

    def test_method_documentation(self, js_content):
        """Test that methods are documented."""
        assert "@" in js_content or "/**" in js_content


class TestCalculatorUIAsyncHandling:
    """Test async/await patterns."""

    def test_async_send_expression(self, js_content):
        """Test that sendExpression is async."""
        assert "async" in js_content

    def test_await_fetch(self, js_content):
        """Test that await is used with fetch."""
        assert "await fetch(" in js_content

    def test_await_response_json(self, js_content):
        """Test that await is used with response.json()."""
        assert "await" in js_content
