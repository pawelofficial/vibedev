"""Tests for sql_lineage.exceptions module."""

import pytest

from sql_lineage.exceptions import (
    CircularDependencyError,
    SchemaParseError,
    UnresolvedReferenceError,
)


class TestSchemaParseError:
    """Test SchemaParseError exception class."""

    def test_basic_message_only(self):
        """Test SchemaParseError with message only."""
        exc = SchemaParseError("Test message")
        assert str(exc) == "Test message"
        assert exc.message == "Test message"
        assert exc.detail == ""

    def test_message_with_detail(self):
        """Test SchemaParseError with message and detail."""
        exc = SchemaParseError("Test message", detail="Additional detail")
        assert str(exc) == "Test message – Additional detail"
        assert exc.message == "Test message"
        assert exc.detail == "Additional detail"

    def test_empty_detail_string(self):
        """Test SchemaParseError with empty detail string."""
        exc = SchemaParseError("Test message", detail="")
        assert str(exc) == "Test message"
        assert exc.detail == ""

    def test_isinstance_exception(self):
        """Test that SchemaParseError is an Exception subclass."""
        exc = SchemaParseError("Test")
        assert isinstance(exc, Exception)

    def test_str_formatting_with_special_chars(self):
        """Test SchemaParseError with special characters."""
        exc = SchemaParseError("Bad SQL", detail="Found: SELECT * FROM")
        assert "Bad SQL" in str(exc)
        assert "SELECT * FROM" in str(exc)


class TestUnresolvedReferenceError:
    """Test UnresolvedReferenceError exception class."""

    def test_basic_ref_only(self):
        """Test UnresolvedReferenceError with ref only."""
        exc = UnresolvedReferenceError("missing_table")
        assert exc.ref == "missing_table"
        assert "Unresolved reference: missing_table" in str(exc)
        assert exc.detail == ""

    def test_ref_with_context(self):
        """Test UnresolvedReferenceError with context."""
        exc = UnresolvedReferenceError("col_x", context="in view my_view")
        assert exc.ref == "col_x"
        assert "Unresolved reference: col_x" in str(exc)
        assert "in view my_view" in str(exc)

    def test_inherits_from_schema_parse_error(self):
        """Test that UnresolvedReferenceError is a SchemaParseError subclass."""
        exc = UnresolvedReferenceError("test_ref")
        assert isinstance(exc, SchemaParseError)

    def test_inheritance_chain(self):
        """Test the full inheritance chain."""
        exc = UnresolvedReferenceError("test_ref", context="test context")
        assert isinstance(exc, SchemaParseError)
        assert isinstance(exc, Exception)


class TestCircularDependencyError:
    """Test CircularDependencyError exception class."""

    def test_single_view_cycle(self):
        """Test CircularDependencyError with a single view cycle."""
        cycle = ["view_a"]
        exc = CircularDependencyError(cycle)
        assert exc.cycle == cycle
        assert "Circular dependency detected: view_a" in str(exc)

    def test_simple_two_view_cycle(self):
        """Test CircularDependencyError with a two-view cycle."""
        cycle = ["view_a", "view_b"]
        exc = CircularDependencyError(cycle)
        assert exc.cycle == cycle
        assert "Circular dependency detected: view_a -> view_b" in str(exc)

    def test_complex_cycle(self):
        """Test CircularDependencyError with a complex cycle."""
        cycle = ["view_a", "view_b", "view_c", "view_a"]
        exc = CircularDependencyError(cycle)
        assert exc.cycle == cycle
        assert "view_a -> view_b -> view_c -> view_a" in str(exc)

    def test_inherits_from_schema_parse_error(self):
        """Test that CircularDependencyError is a SchemaParseError subclass."""
        exc = CircularDependencyError(["v1", "v2"])
        assert isinstance(exc, SchemaParseError)

    def test_inheritance_chain(self):
        """Test the full inheritance chain."""
        exc = CircularDependencyError(["v1", "v2"])
        assert isinstance(exc, SchemaParseError)
        assert isinstance(exc, Exception)

    def test_empty_cycle(self):
        """Test CircularDependencyError with empty cycle list."""
        cycle = []
        exc = CircularDependencyError(cycle)
        assert exc.cycle == cycle
        assert "Circular dependency detected:" in str(exc)
