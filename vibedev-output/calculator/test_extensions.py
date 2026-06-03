"""
calculator/test_extensions.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Unit tests for calculator/extensions.py.

Tests cover:
- Singleton pattern
- Module-level calculator instance
- Calculator type and functionality
"""

import pytest

from calculator.engine import Calculator
from calculator.extensions import calculator


class TestCalculatorSingleton:
    """Test the calculator singleton instance."""

    def test_calculator_is_instance(self):
        """Test that calculator is an instance of Calculator."""
        assert isinstance(calculator, Calculator)

    def test_calculator_is_module_level(self):
        """Test that calculator is importable at module level."""
        from calculator.extensions import calculator as calc
        assert calc is not None

    def test_calculator_same_instance_on_reimport(self):
        """Test that reimporting gives the same instance."""
        from calculator.extensions import calculator as calc1
        from calculator.extensions import calculator as calc2
        # They should be the same object in memory
        assert calc1 is calc2

    def test_calculator_functionality(self):
        """Test that the calculator instance is functional."""
        result = calculator.evaluate("2 + 2")
        assert result == 4.0

    def test_calculator_is_stateless(self):
        """Test that multiple evaluations work correctly."""
        result1 = calculator.evaluate("1 + 1")
        result2 = calculator.evaluate("3 * 3")
        assert result1 == 2.0
        assert result2 == 9.0

    def test_calculator_error_handling(self):
        """Test that error handling works on the singleton."""
        with pytest.raises(ValueError):
            calculator.evaluate("invalid expression")


class TestCalculatorExtensionsImport:
    """Test import patterns for the calculator extension."""

    def test_calculator_importable_from_extensions(self):
        """Test that calculator can be imported from extensions module."""
        try:
            from calculator.extensions import calculator  # noqa: F401
        except ImportError:
            pytest.fail("Failed to import calculator from extensions")

    def test_calculator_not_importable_from_engine(self):
        """Test that the singleton is not in the engine module."""
        from calculator import engine
        assert not hasattr(engine, "calculator")

    def test_multiple_operations_sequence(self):
        """Test a sequence of calculator operations."""
        # Clear calculation
        result1 = calculator.evaluate("10 + 5")
        assert result1 == 15.0

        # Next calculation using a result
        result2 = calculator.evaluate("10 - 3")
        assert result2 == 7.0

        # Both should work independently
        assert result1 == 15.0
        assert result2 == 7.0
