"""Tests for sql_lineage.normalizer module."""

import pytest

from sql_lineage.normalizer import normalize_name


class TestNormalizeName:
    """Test the normalize_name function."""

    def test_simple_lowercase(self):
        """Test that lowercase names are returned as-is."""
        assert normalize_name("table_name") == "table_name"
        assert normalize_name("users") == "users"
        assert normalize_name("id") == "id"

    def test_uppercase_conversion(self):
        """Test that uppercase names are converted to lowercase."""
        assert normalize_name("TABLE_NAME") == "table_name"
        assert normalize_name("USERS") == "users"
        assert normalize_name("MyTable") == "mytable"

    def test_mixed_case_conversion(self):
        """Test mixed case conversion."""
        assert normalize_name("MyColumn") == "mycolumn"
        assert normalize_name("FirstName") == "firstname"
        assert normalize_name("user_id") == "user_id"

    def test_ansi_double_quotes(self):
        """Test ANSI standard double-quoted identifiers."""
        assert normalize_name('"table_name"') == "table_name"
        assert normalize_name('"UPPERCASE"') == "uppercase"
        assert normalize_name('"MixedCase"') == "mixedcase"

    def test_mysql_backticks(self):
        """Test MySQL back-tick quoted identifiers."""
        assert normalize_name("`table_name`") == "table_name"
        assert normalize_name("`UPPERCASE`") == "uppercase"
        assert normalize_name("`MixedCase`") == "mixedcase"

    def test_tsql_square_brackets(self):
        """Test T-SQL square-bracket quoted identifiers."""
        assert normalize_name("[table_name]") == "table_name"
        assert normalize_name("[UPPERCASE]") == "uppercase"
        assert normalize_name("[MixedCase]") == "mixedcase"

    def test_empty_string(self):
        """Test that empty string is returned as-is."""
        assert normalize_name("") == ""

    def test_whitespace_stripping(self):
        """Test that surrounding whitespace is stripped."""
        assert normalize_name("  table_name  ") == "table_name"
        assert normalize_name("\ttable_name\t") == "table_name"
        assert normalize_name(" USERS ") == "users"

    def test_whitespace_inside_quotes(self):
        """Test that whitespace inside quotes is preserved then stripped."""
        assert normalize_name('"  table  "') == "table"
        assert normalize_name("`  table  `") == "table"
        assert normalize_name("[  table  ]") == "table"

    def test_quoted_with_internal_whitespace(self):
        """Test quoted names with internal whitespace."""
        assert normalize_name('"user name"') == "user name"
        assert normalize_name("`user name`") == "user name"
        assert normalize_name("[user name]") == "user name"

    def test_quoted_uppercase_with_whitespace(self):
        """Test quoted uppercase names with whitespace."""
        assert normalize_name('"USER NAME"') == "user name"
        assert normalize_name("`USER NAME`") == "user name"
        assert normalize_name("[USER NAME]") == "user name"

    def test_complex_identifiers(self):
        """Test complex SQL identifiers."""
        assert normalize_name("schema.table") == "schema.table"
        assert normalize_name('"schema"."table"') == '"schema"."table"'
        assert normalize_name("user_id_123") == "user_id_123"

    def test_special_characters_unquoted(self):
        """Test unquoted names with special characters."""
        assert normalize_name("user_id") == "user_id"
        assert normalize_name("first_name") == "first_name"
        assert normalize_name("column_1") == "column_1"

    def test_single_character(self):
        """Test single character identifiers."""
        assert normalize_name("a") == "a"
        assert normalize_name("A") == "a"
        assert normalize_name('"A"') == "a"

    def test_numbers_only(self):
        """Test numeric identifiers."""
        assert normalize_name("123") == "123"
        assert normalize_name("42") == "42"

    def test_nested_quotes_not_matched(self):
        """Test that mismatched quotes are handled gracefully."""
        # These should not match the regex and be treated as regular text
        assert normalize_name('test"quoted') == 'test"quoted'
        assert normalize_name('mis`matched') == 'mis`matched'

    def test_empty_quotes(self):
        """Test empty quoted strings."""
        assert normalize_name('""') == ""
        assert normalize_name("``") == ""
        assert normalize_name("[]") == ""

    def test_duplicate_underscores(self):
        """Test names with duplicate underscores."""
        assert normalize_name("__name__") == "__name__"
        assert normalize_name("_PRIVATE") == "_private"

    def test_unicode_characters(self):
        """Test names with unicode characters."""
        assert normalize_name("naïve") == "naïve"
        assert normalize_name("Übermensch") == "übermensch"

    def test_case_insensitivity_after_stripping(self):
        """Test case insensitivity is applied after quote stripping."""
        assert normalize_name('"MixedCase"') == "mixedcase"
        assert normalize_name("`MixedCase`") == "mixedcase"
        assert normalize_name("[MixedCase]") == "mixedcase"

    def test_whitespace_only_input(self):
        """Test input with only whitespace."""
        assert normalize_name("   ") == ""
        assert normalize_name("\t\t") == ""

    def test_idempotency(self):
        """Test that normalize_name is idempotent on already-normalized names."""
        name = normalize_name("TableName")
        assert normalize_name(name) == name
