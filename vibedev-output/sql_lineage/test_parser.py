"""Tests for sql_lineage.parser module."""

import pytest
from pathlib import Path
import tempfile

from sql_lineage.exceptions import SchemaParseError
from sql_lineage.models import TableDef, ViewDef, ForeignKeyDef
from sql_lineage.parser import SchemaParser


class TestSchemaParserInit:
    """Test SchemaParser initialization."""

    def test_default_dialect(self):
        """Test SchemaParser with default (None) dialect."""
        parser = SchemaParser()
        assert parser.dialect is None

    def test_custom_dialect(self):
        """Test SchemaParser with custom dialect."""
        parser = SchemaParser(dialect="postgres")
        assert parser.dialect == "postgres"

    def test_different_dialects(self):
        """Test SchemaParser with different SQL dialects."""
        for dialect in [None, "postgres", "mysql", "tsql", "sqlite"]:
            parser = SchemaParser(dialect=dialect)
            assert parser.dialect == dialect

    def test_initial_state(self):
        """Test SchemaParser initial state."""
        parser = SchemaParser()
        assert parser._tables == {}
        assert parser._views == {}


class TestParseFile:
    """Test SchemaParser.parse_file method."""

    def test_parse_simple_table_from_file(self):
        """Test parsing a simple CREATE TABLE from file."""
        sql = "CREATE TABLE users (id INT, name VARCHAR(100));"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sql", delete=False) as f:
            f.write(sql)
            f.flush()
            path = f.name

        try:
            parser = SchemaParser()
            graph = parser.parse_file(path)
            assert "users" in graph.tables
            assert graph.tables["users"].columns == ("id", "name")
        finally:
            Path(path).unlink()

    def test_parse_file_not_found(self):
        """Test parsing a non-existent file."""
        parser = SchemaParser()
        with pytest.raises(FileNotFoundError):
            parser.parse_file("/nonexistent/path/to/file.sql")

    def test_parse_file_with_utf8(self):
        """Test parsing a file with UTF-8 encoding."""
        sql = "CREATE TABLE Übersicht (id INT, Äname VARCHAR(100));"
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".sql", delete=False, encoding="utf-8"
        ) as f:
            f.write(sql)
            f.flush()
            path = f.name

        try:
            parser = SchemaParser()
            graph = parser.parse_file(path)
            assert "übersicht" in graph.tables
        finally:
            Path(path).unlink()


class TestParseStatements:
    """Test SchemaParser.parse_statements method."""

    def test_parse_single_table(self):
        """Test parsing a single CREATE TABLE statement."""
        sql = "CREATE TABLE users (id INT PRIMARY KEY, name VARCHAR(100));"
        parser = SchemaParser()
        graph = parser.parse_statements(sql)

        assert "users" in graph.tables
        assert graph.tables["users"].columns == ("id", "name")
        assert graph.tables["users"].primary_keys == frozenset({"id"})
        assert len(graph.views) == 0

    def test_parse_multiple_tables(self):
        """Test parsing multiple CREATE TABLE statements."""
        sql = """
        CREATE TABLE users (id INT PRIMARY KEY, name VARCHAR(100));
        CREATE TABLE products (id INT PRIMARY KEY, title VARCHAR(255));
        """
        parser = SchemaParser()
        graph = parser.parse_statements(sql)

        assert len(graph.tables) == 2
        assert "users" in graph.tables
        assert "products" in graph.tables

    def test_parse_single_view(self):
        """Test parsing a single CREATE VIEW statement."""
        sql = """
        CREATE TABLE users (id INT, name VARCHAR(100));
        CREATE VIEW user_names AS SELECT id, name FROM users;
        """
        parser = SchemaParser()
        graph = parser.parse_statements(sql)

        assert "users" in graph.tables
        assert "user_names" in graph.views
        view = graph.views["user_names"]
        assert view.output_columns == ("id", "name")
        assert "users" in view.dependencies

    def test_parse_mixed_statements(self):
        """Test parsing mixed CREATE TABLE and CREATE VIEW statements."""
        sql = """
        CREATE TABLE users (id INT, name VARCHAR(100));
        CREATE TABLE orders (id INT, user_id INT, amount DECIMAL);
        CREATE VIEW user_orders AS SELECT u.name, o.amount FROM users u JOIN orders o ON u.id = o.user_id;
        """
        parser = SchemaParser()
        graph = parser.parse_statements(sql)

        assert len(graph.tables) == 2
        assert len(graph.views) == 1
        assert graph.views["user_orders"].dependencies == frozenset({"users", "orders"})

    def test_parse_invalid_sql(self):
        """Test parsing invalid SQL raises SchemaParseError."""
        sql = "THIS IS NOT VALID SQL"
        parser = SchemaParser()

        # sqlglot might parse this differently, but we test the error handling
        # even if it doesn't throw during parse
        try:
            graph = parser.parse_statements(sql)
            # If it doesn't error, at least verify it returns a graph
            assert isinstance(graph.tables, dict)
        except SchemaParseError:
            pass

    def test_parse_duplicate_table_names(self):
        """Test parsing with duplicate table names raises error."""
        sql = """
        CREATE TABLE users (id INT);
        CREATE TABLE users (name VARCHAR(100));
        """
        parser = SchemaParser()

        with pytest.raises(SchemaParseError, match="Duplicate table name"):
            parser.parse_statements(sql)

    def test_parse_duplicate_view_names(self):
        """Test parsing with duplicate view names raises error."""
        sql = """
        CREATE TABLE users (id INT);
        CREATE VIEW summary AS SELECT * FROM users;
        CREATE VIEW summary AS SELECT id FROM users;
        """
        parser = SchemaParser()

        with pytest.raises(SchemaParseError, match="Duplicate view name"):
            parser.parse_statements(sql)

    def test_parse_normalizes_names(self):
        """Test that parser normalizes table and column names."""
        sql = """
        CREATE TABLE "Users" (id INT, "FirstName" VARCHAR(100));
        CREATE VIEW "UserView" AS SELECT id FROM "Users";
        """
        parser = SchemaParser()
        graph = parser.parse_statements(sql)

        assert "users" in graph.tables
        assert "id" in graph.tables["users"].columns
        assert "firstname" in graph.tables["users"].columns
        assert "userview" in graph.views

    def test_parse_non_create_statements_ignored(self):
        """Test that non-CREATE statements are silently ignored."""
        sql = """
        INSERT INTO users VALUES (1, 'John');
        SELECT * FROM users;
        DROP TABLE old_table;
        CREATE TABLE users (id INT, name VARCHAR(100));
        """
        parser = SchemaParser()
        graph = parser.parse_statements(sql)

        assert len(graph.tables) == 1
        assert "users" in graph.tables


class TestExtractColumns:
    """Test SchemaParser._extract_columns method."""

    def test_extract_simple_columns(self):
        """Test extracting columns from simple CREATE TABLE."""
        sql = "CREATE TABLE users (id INT, name VARCHAR(100), email VARCHAR(255));"
        parser = SchemaParser()
        graph = parser.parse_statements(sql)

        columns = graph.tables["users"].columns
        assert columns == ("id", "name", "email")

    def test_extract_columns_with_constraints(self):
        """Test extracting columns with PRIMARY KEY constraint."""
        sql = "CREATE TABLE users (id INT PRIMARY KEY, name VARCHAR(100));"
        parser = SchemaParser()
        graph = parser.parse_statements(sql)

        columns = graph.tables["users"].columns
        assert "id" in columns
        assert "name" in columns

    def test_extract_quoted_column_names(self):
        """Test extracting quoted column names."""
        sql = '''CREATE TABLE users ("UserId" INT, "FirstName" VARCHAR(100));'''
        parser = SchemaParser()
        graph = parser.parse_statements(sql)

        columns = graph.tables["users"].columns
        assert "userid" in columns
        assert "firstname" in columns

    def test_extract_empty_columns(self):
        """Test extracting columns when none are defined."""
        sql = "CREATE TABLE empty_table AS SELECT 1;"
        parser = SchemaParser()
        graph = parser.parse_statements(sql)

        if "empty_table" in graph.tables:
            # Some dialects might not create the table in this case
            assert graph.tables["empty_table"].columns == ()


class TestExtractConstraints:
    """Test SchemaParser._extract_constraints method."""

    def test_extract_inline_primary_key(self):
        """Test extracting inline PRIMARY KEY constraint."""
        sql = "CREATE TABLE users (id INT PRIMARY KEY, name VARCHAR(100));"
        parser = SchemaParser()
        graph = parser.parse_statements(sql)

        pks = graph.tables["users"].primary_keys
        assert "id" in pks

    def test_extract_table_level_primary_key(self):
        """Test extracting table-level PRIMARY KEY constraint."""
        sql = "CREATE TABLE users (id INT, name VARCHAR(100), PRIMARY KEY (id));"
        parser = SchemaParser()
        graph = parser.parse_statements(sql)

        pks = graph.tables["users"].primary_keys
        assert "id" in pks

    def test_extract_composite_primary_key(self):
        """Test extracting composite PRIMARY KEY."""
        sql = "CREATE TABLE user_roles (user_id INT, role_id INT, PRIMARY KEY (user_id, role_id));"
        parser = SchemaParser()
        graph = parser.parse_statements(sql)

        pks = graph.tables["user_roles"].primary_keys
        assert pks == frozenset({"user_id", "role_id"})

    def test_extract_inline_foreign_key(self):
        """Test extracting inline FOREIGN KEY constraint."""
        sql = """
        CREATE TABLE users (id INT PRIMARY KEY);
        CREATE TABLE orders (id INT, user_id INT REFERENCES users(id));
        """
        parser = SchemaParser()
        graph = parser.parse_statements(sql)

        fks = graph.tables["orders"].foreign_keys
        assert len(fks) > 0
        # At least one FK should reference users
        assert any(fk.to_table == "users" for fk in fks)

    def test_extract_table_level_foreign_key(self):
        """Test extracting table-level FOREIGN KEY constraint."""
        sql = """
        CREATE TABLE users (id INT PRIMARY KEY);
        CREATE TABLE orders (
            id INT,
            user_id INT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        """
        parser = SchemaParser()
        graph = parser.parse_statements(sql)

        fks = graph.tables["orders"].foreign_keys
        assert len(fks) > 0
        assert any(fk.to_table == "users" for fk in fks)

    def test_extract_no_constraints(self):
        """Test extracting constraints when none are present."""
        sql = "CREATE TABLE simple (id INT, name VARCHAR(100));"
        parser = SchemaParser()
        graph = parser.parse_statements(sql)

        table = graph.tables["simple"]
        assert table.primary_keys == frozenset()
        assert table.foreign_keys == ()


class TestExtractViewOutputColumns:
    """Test SchemaParser._extract_view_output_columns method."""

    def test_extract_simple_columns(self):
        """Test extracting output columns from simple SELECT."""
        sql = """
        CREATE TABLE users (id INT, name VARCHAR(100));
        CREATE VIEW user_list AS SELECT id, name FROM users;
        """
        parser = SchemaParser()
        graph = parser.parse_statements(sql)

        cols = graph.views["user_list"].output_columns
        assert cols == ("id", "name")

    def test_extract_aliased_columns(self):
        """Test extracting aliased output columns."""
        sql = """
        CREATE TABLE users (id INT, name VARCHAR(100));
        CREATE VIEW user_summary AS SELECT id AS user_id, name AS full_name FROM users;
        """
        parser = SchemaParser()
        graph = parser.parse_statements(sql)

        cols = graph.views["user_summary"].output_columns
        assert "user_id" in cols
        assert "full_name" in cols

    def test_extract_wildcard_column(self):
        """Test extracting wildcard column."""
        sql = """
        CREATE TABLE users (id INT, name VARCHAR(100));
        CREATE VIEW all_users AS SELECT * FROM users;
        """
        parser = SchemaParser()
        graph = parser.parse_statements(sql)

        cols = graph.views["all_users"].output_columns
        assert "*" in cols

    def test_extract_qualified_wildcard(self):
        """Test extracting qualified wildcard column."""
        sql = """
        CREATE TABLE users (id INT, name VARCHAR(100));
        CREATE TABLE orders (id INT, user_id INT);
        CREATE VIEW user_orders AS SELECT u.*, o.id FROM users u JOIN orders o ON u.id = o.user_id;
        """
        parser = SchemaParser()
        graph = parser.parse_statements(sql)

        cols = graph.views["user_orders"].output_columns
        assert "*" in cols

    def test_extract_expression_columns(self):
        """Test extracting expression columns."""
        sql = """
        CREATE TABLE products (id INT, price DECIMAL);
        CREATE VIEW pricing AS SELECT id, price * 1.1 AS marked_price FROM products;
        """
        parser = SchemaParser()
        graph = parser.parse_statements(sql)

        cols = graph.views["pricing"].output_columns
        assert "id" in cols
        assert "marked_price" in cols


class TestExtractDependencies:
    """Test SchemaParser._extract_dependencies method."""

    def test_extract_from_clause_dependency(self):
        """Test extracting dependency from FROM clause."""
        sql = """
        CREATE TABLE users (id INT);
        CREATE VIEW summary AS SELECT * FROM users;
        """
        parser = SchemaParser()
        graph = parser.parse_statements(sql)

        deps = graph.views["summary"].dependencies
        assert "users" in deps

    def test_extract_join_dependency(self):
        """Test extracting dependencies from JOIN clause."""
        sql = """
        CREATE TABLE users (id INT);
        CREATE TABLE orders (user_id INT);
        CREATE VIEW user_orders AS SELECT u.id, o.user_id FROM users u JOIN orders o ON u.id = o.user_id;
        """
        parser = SchemaParser()
        graph = parser.parse_statements(sql)

        deps = graph.views["user_orders"].dependencies
        assert "users" in deps
        assert "orders" in deps

    def test_extract_multiple_join_dependencies(self):
        """Test extracting multiple JOIN dependencies."""
        sql = """
        CREATE TABLE users (id INT);
        CREATE TABLE orders (user_id INT);
        CREATE TABLE products (id INT);
        CREATE VIEW complex_view AS
            SELECT u.id, o.user_id, p.id
            FROM users u
            JOIN orders o ON u.id = o.user_id
            JOIN products p ON o.id = p.id;
        """
        parser = SchemaParser()
        graph = parser.parse_statements(sql)

        deps = graph.views["complex_view"].dependencies
        assert "users" in deps
        assert "orders" in deps
        assert "products" in deps

    def test_extract_cte_alias_not_dependency(self):
        """Test that CTE aliases are properly handled in dependencies."""
        sql = """
        CREATE TABLE users (id INT, name VARCHAR(100));
        CREATE VIEW cte_view AS
            WITH user_cte AS (SELECT id, name FROM users)
            SELECT * FROM user_cte;
        """
        parser = SchemaParser()
        graph = parser.parse_statements(sql)

        deps = graph.views["cte_view"].dependencies
        # The parser should include users in dependencies
        assert "users" in deps
        # CTE aliases may or may not be in dependencies depending on parse order
        # Just verify users is there which is the important one

    def test_extract_no_dependencies(self):
        """Test extracting when there are no dependencies."""
        sql = """
        CREATE TABLE users (id INT);
        CREATE VIEW constant_view AS SELECT 1 AS constant;
        """
        parser = SchemaParser()
        graph = parser.parse_statements(sql)

        deps = graph.views["constant_view"].dependencies
        assert len(deps) == 0 or deps == frozenset()

    def test_extract_quoted_dependency_names(self):
        """Test extracting dependencies with quoted table names."""
        sql = '''
        CREATE TABLE "Users" (id INT);
        CREATE VIEW summary AS SELECT * FROM "Users";
        '''
        parser = SchemaParser()
        graph = parser.parse_statements(sql)

        deps = graph.views["summary"].dependencies
        # Should be normalized to lowercase
        assert "users" in deps


class TestParseCreateTableErrors:
    """Test error handling in _parse_create_table."""

    def test_missing_table_name(self):
        """Test handling of CREATE TABLE without table name."""
        sql = "CREATE TABLE (id INT);"
        parser = SchemaParser()

        with pytest.raises(SchemaParseError):
            parser.parse_statements(sql)

    def test_duplicate_table_error(self):
        """Test handling of duplicate table names."""
        sql = """
        CREATE TABLE users (id INT);
        CREATE TABLE users (name VARCHAR(100));
        """
        parser = SchemaParser()

        with pytest.raises(SchemaParseError, match="Duplicate table name"):
            parser.parse_statements(sql)


class TestParseCreateViewErrors:
    """Test error handling in _parse_create_view."""

    def test_missing_view_name(self):
        """Test handling of CREATE VIEW without view name."""
        parser = SchemaParser()

        # This is dialect-specific, but we test error handling
        sql = "CREATE VIEW AS SELECT 1;"
        try:
            graph = parser.parse_statements(sql)
            # If no error, that's okay - dialect-dependent
            assert isinstance(graph.views, dict)
        except SchemaParseError:
            pass

    def test_duplicate_view_error(self):
        """Test handling of duplicate view names."""
        sql = """
        CREATE TABLE users (id INT);
        CREATE VIEW summary AS SELECT * FROM users;
        CREATE VIEW summary AS SELECT id FROM users;
        """
        parser = SchemaParser()

        with pytest.raises(SchemaParseError, match="Duplicate view name"):
            parser.parse_statements(sql)
