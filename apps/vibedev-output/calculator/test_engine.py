"""
calculator/test_engine.py
~~~~~~~~~~~~~~~~~~~~~~~~~
Unit tests for the Calculator class in calculator/engine.py.

Tests cover:
- Basic arithmetic operations
- Operator precedence
- Parentheses handling
- Unary operators
- Edge cases and error conditions
"""

import ast
import pytest

from calculator.engine import Calculator


class TestCalculatorBasicOperations:
    """Test basic arithmetic operations."""

    def test_addition(self):
        """Test simple addition."""
        calc = Calculator()
        result = calc.evaluate("3 + 4")
        assert result == 7.0

    def test_subtraction(self):
        """Test simple subtraction."""
        calc = Calculator()
        result = calc.evaluate("10 - 3")
        assert result == 7.0

    def test_multiplication(self):
        """Test simple multiplication."""
        calc = Calculator()
        result = calc.evaluate("3 * 4")
        assert result == 12.0

    def test_division(self):
        """Test simple division."""
        calc = Calculator()
        result = calc.evaluate("12 / 3")
        assert result == 4.0

    def test_floor_division(self):
        """Test floor division."""
        calc = Calculator()
        result = calc.evaluate("10 // 3")
        assert result == 3.0

    def test_modulo(self):
        """Test modulo operation."""
        calc = Calculator()
        result = calc.evaluate("10 % 3")
        assert result == 1.0

    def test_exponentiation(self):
        """Test exponentiation."""
        calc = Calculator()
        result = calc.evaluate("2 ** 3")
        assert result == 8.0


class TestCalculatorPrecedence:
    """Test operator precedence."""

    def test_multiplication_before_addition(self):
        """Test that multiplication is evaluated before addition."""
        calc = Calculator()
        result = calc.evaluate("3 + 4 * 2")
        assert result == 11.0

    def test_division_before_subtraction(self):
        """Test that division is evaluated before subtraction."""
        calc = Calculator()
        result = calc.evaluate("10 - 6 / 2")
        assert result == 7.0

    def test_exponentiation_before_multiplication(self):
        """Test that exponentiation is evaluated first."""
        calc = Calculator()
        result = calc.evaluate("2 * 3 ** 2")
        assert result == 18.0


class TestCalculatorParentheses:
    """Test parentheses grouping."""

    def test_simple_parentheses(self):
        """Test that parentheses override precedence."""
        calc = Calculator()
        result = calc.evaluate("(3 + 4) * 2")
        assert result == 14.0

    def test_nested_parentheses(self):
        """Test nested parentheses."""
        calc = Calculator()
        result = calc.evaluate("((2 + 3) * 4)")
        assert result == 20.0

    def test_multiple_groups(self):
        """Test multiple parenthesized expressions."""
        calc = Calculator()
        result = calc.evaluate("(2 + 3) * (4 + 5)")
        assert result == 45.0


class TestCalculatorUnaryOperators:
    """Test unary operators."""

    def test_unary_negation(self):
        """Test unary minus."""
        calc = Calculator()
        result = calc.evaluate("-5")
        assert result == -5.0

    def test_unary_positive(self):
        """Test unary plus."""
        calc = Calculator()
        result = calc.evaluate("+5")
        assert result == 5.0

    def test_double_negation(self):
        """Test double negation."""
        calc = Calculator()
        result = calc.evaluate("-(-5)")
        assert result == 5.0

    def test_negation_in_expression(self):
        """Test negation within an expression."""
        calc = Calculator()
        result = calc.evaluate("3 * -2")
        assert result == -6.0


class TestCalculatorFloatingPoint:
    """Test floating-point arithmetic."""

    def test_decimal_division(self):
        """Test division resulting in decimal."""
        calc = Calculator()
        result = calc.evaluate("5 / 2")
        assert result == 2.5

    def test_decimal_input(self):
        """Test decimal numbers as input."""
        calc = Calculator()
        result = calc.evaluate("3.5 + 2.5")
        assert result == 6.0

    def test_mixed_integer_decimal(self):
        """Test mixed integer and decimal arithmetic."""
        calc = Calculator()
        result = calc.evaluate("10 / 3")
        assert abs(result - 3.333333333333333) < 1e-10


class TestCalculatorComplexExpressions:
    """Test complex multi-operation expressions."""

    def test_four_operations(self):
        """Test expression with all four basic operations."""
        calc = Calculator()
        result = calc.evaluate("10 + 5 - 3 * 2 / 2")
        assert result == 12.0

    def test_deeply_nested(self):
        """Test deeply nested parentheses."""
        calc = Calculator()
        result = calc.evaluate("((((1 + 1) + 1) + 1))")
        assert result == 4.0

    def test_whitespace_handling(self):
        """Test that whitespace is properly handled."""
        calc = Calculator()
        result = calc.evaluate("  1  +  2  ")
        assert result == 3.0


class TestCalculatorErrors:
    """Test error handling and edge cases."""

    def test_empty_expression(self):
        """Test that empty expression raises ValueError."""
        calc = Calculator()
        with pytest.raises(ValueError, match="Expression must not be empty"):
            calc.evaluate("")

    def test_whitespace_only(self):
        """Test that whitespace-only expression raises ValueError."""
        calc = Calculator()
        with pytest.raises(ValueError, match="Expression must not be empty"):
            calc.evaluate("   ")

    def test_syntax_error(self):
        """Test that invalid syntax raises ValueError."""
        calc = Calculator()
        with pytest.raises(ValueError, match="Invalid expression syntax"):
            calc.evaluate("3 +")

    def test_unclosed_parenthesis(self):
        """Test that unclosed parenthesis raises ValueError."""
        calc = Calculator()
        with pytest.raises(ValueError, match="Invalid expression syntax"):
            calc.evaluate("(3 + 4")

    def test_division_by_zero(self):
        """Test that division by zero raises ValueError."""
        calc = Calculator()
        with pytest.raises(ValueError, match="Division by zero"):
            calc.evaluate("5 / 0")

    def test_modulo_by_zero(self):
        """Test that modulo by zero raises ValueError."""
        calc = Calculator()
        with pytest.raises(ValueError, match="Division by zero"):
            calc.evaluate("5 % 0")

    def test_dangerous_code_disallowed(self):
        """Test that dangerous code (e.g., function calls) is rejected."""
        calc = Calculator()
        with pytest.raises(ValueError, match="Unsafe or unsupported operation"):
            calc.evaluate("__import__('os')")

    def test_variable_access_disallowed(self):
        """Test that variable access is disallowed."""
        calc = Calculator()
        with pytest.raises(ValueError, match="Unsafe or unsupported operation"):
            calc.evaluate("x")

    def test_string_literals_disallowed(self):
        """Test that string literals are disallowed."""
        calc = Calculator()
        # String literals use Constant node which is allowed,
        # but evaluate() fails when trying to convert string to float
        with pytest.raises(ValueError):
            calc.evaluate("'hello'")

    def test_list_comprehension_disallowed(self):
        """Test that list comprehensions are disallowed."""
        calc = Calculator()
        with pytest.raises(ValueError, match="Unsafe or unsupported operation"):
            calc.evaluate("[x for x in range(5)]")

    def test_lambda_disallowed(self):
        """Test that lambda expressions are disallowed."""
        calc = Calculator()
        with pytest.raises(ValueError, match="Unsafe or unsupported operation"):
            calc.evaluate("lambda x: x + 1")


class TestCalculatorAllowedNodes:
    """Test that ALLOWED_NODES is correctly set."""

    def test_allowed_nodes_contains_expression(self):
        """Test that Expression node is allowed."""
        assert ast.Expression in Calculator.ALLOWED_NODES

    def test_allowed_nodes_contains_constant(self):
        """Test that Constant node is allowed."""
        assert ast.Constant in Calculator.ALLOWED_NODES

    def test_allowed_nodes_contains_binop(self):
        """Test that BinOp node is allowed."""
        assert ast.BinOp in Calculator.ALLOWED_NODES

    def test_allowed_nodes_contains_add(self):
        """Test that Add operator is allowed."""
        assert ast.Add in Calculator.ALLOWED_NODES

    def test_allowed_nodes_frozen(self):
        """Test that ALLOWED_NODES is a frozenset."""
        assert isinstance(Calculator.ALLOWED_NODES, frozenset)


class TestCalculatorInstanceIndependence:
    """Test that Calculator instances are independent."""

    def test_multiple_instances(self):
        """Test that multiple Calculator instances work independently."""
        calc1 = Calculator()
        calc2 = Calculator()

        result1 = calc1.evaluate("1 + 1")
        result2 = calc2.evaluate("2 * 3")

        assert result1 == 2.0
        assert result2 == 6.0

    def test_stateless(self):
        """Test that Calculator is stateless."""
        calc = Calculator()
        result1 = calc.evaluate("5 + 3")
        result2 = calc.evaluate("5 + 3")

        assert result1 == result2 == 8.0


class TestCalculatorSpecialCases:
    """Test special edge cases."""

    def test_zero(self):
        """Test evaluation of zero."""
        calc = Calculator()
        result = calc.evaluate("0")
        assert result == 0.0

    def test_negative_result(self):
        """Test negative results."""
        calc = Calculator()
        result = calc.evaluate("3 - 5")
        assert result == -2.0

    def test_large_numbers(self):
        """Test large numbers."""
        calc = Calculator()
        result = calc.evaluate("999999 + 1")
        assert result == 1000000.0

    def test_very_small_decimal(self):
        """Test very small decimal numbers."""
        calc = Calculator()
        result = calc.evaluate("0.001 + 0.002")
        assert abs(result - 0.003) < 1e-10
