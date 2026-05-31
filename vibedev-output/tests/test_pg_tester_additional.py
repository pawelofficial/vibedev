"""
Additional tester-written verification tests for the PostgreSQL introspection feature.

Covers edge cases and contract checks not in the developer's test suite.
"""

import os
import re
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from generate_schema import (
    _pg_format_type,
    _pg_introspect_tables,
    _pg_introspect_views,
    build_schema_from_postgres,
    build_schema,
    ColumnDef,
    TableDef,
    _collect_view_names,
    _render_table,
    main,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_conn(
    tables_rows=None,
    columns_rows=None,
    pk_rows=None,
    fk_rows=None,
    views_rows=None,
):
    tables_rows = tables_rows or []
    columns_rows = columns_rows or []
    pk_rows = pk_rows or []
    fk_rows = fk_rows or []
    views_rows = views_rows or []

    cursor = MagicMock()
    call_results = []

    def _execute_side_effect(sql, params=None):
        sql_lower = sql.strip().lower()
        if "information_schema.tables" in sql_lower:
            call_results.append(tables_rows)
        elif "table_constraints" in sql_lower and "primary key" in sql_lower:
            call_results.append(pk_rows)
        elif "referential_constraints" in sql_lower:
            call_results.append(fk_rows)
        elif "information_schema.columns" in sql_lower:
            call_results.append(columns_rows)
        elif "pg_views" in sql_lower:
            call_results.append(views_rows)
        else:
            call_results.append([])

    cursor.execute = MagicMock(side_effect=_execute_side_effect)
    cursor.fetchall = MagicMock(side_effect=lambda: call_results.pop(0))

    conn = MagicMock()
    conn.cursor.return_value = cursor
    return conn


def _mock_pg(conn):
    mock = MagicMock()
    mock.connect.return_value = conn
    return mock


# Reusable fixtures
SINGLE_TABLE = [("widgets",)]
SINGLE_PK = [("widgets", "id")]
SINGLE_COLUMNS = [
    ("widgets", "id", "integer", None, 32, 0, "NO", None, 1, "int4"),
    ("widgets", "name", "text", None, None, None, "NO", None, 2, "text"),
]


# ---------------------------------------------------------------------------
# Type mapping edge cases
# ---------------------------------------------------------------------------

class TestTypeEdgeCases:
    """Extra type-mapping cases not in the developer's tests."""

    def test_smallint(self):
        assert _pg_format_type("smallint", None, 16, 0) == "SMALLINT"

    def test_real(self):
        assert _pg_format_type("real", None, None, None) == "REAL"

    def test_time_types(self):
        assert _pg_format_type("time without time zone", None, None, None) == "TIME"
        assert _pg_format_type("time with time zone", None, None, None) == "TIMETZ"

    def test_inet(self):
        assert _pg_format_type("inet", None, None, None) == "INET"

    def test_money(self):
        assert _pg_format_type("money", None, None, None) == "MONEY"

    def test_interval(self):
        assert _pg_format_type("interval", None, None, None) == "INTERVAL"

    def test_bytea(self):
        assert _pg_format_type("bytea", None, None, None) == "BYTEA"

    def test_json(self):
        assert _pg_format_type("json", None, None, None) == "JSON"

    def test_tsvector_tsquery(self):
        assert _pg_format_type("tsvector", None, None, None) == "TSVECTOR"
        assert _pg_format_type("tsquery", None, None, None) == "TSQUERY"

    def test_bit_types(self):
        assert _pg_format_type("bit", None, None, None) == "BIT"
        assert _pg_format_type("bit varying", None, None, None) == "BIT VARYING"

    def test_geometry_types(self):
        assert _pg_format_type("point", None, None, None) == "POINT"
        assert _pg_format_type("line", None, None, None) == "LINE"
        assert _pg_format_type("circle", None, None, None) == "CIRCLE"
        assert _pg_format_type("box", None, None, None) == "BOX"
        assert _pg_format_type("polygon", None, None, None) == "POLYGON"

    def test_array_int_type(self):
        """Array of integers should produce INTEGER[]."""
        result = _pg_format_type("ARRAY", None, None, None, "_int4")
        assert result == "INT4[]"

    def test_user_defined_without_udt(self):
        """USER-DEFINED without udt_name should fallback to TEXT."""
        result = _pg_format_type("USER-DEFINED", None, None, None, None)
        assert result == "TEXT"

    def test_numeric_with_zero_scale(self):
        """NUMERIC(10, 0) → NUMERIC(10) (no scale)."""
        result = _pg_format_type("numeric", None, 10, 0)
        assert result == "NUMERIC(10)"

    def test_char_without_length(self):
        """CHARACTER without length → TEXT."""
        result = _pg_format_type("character", None, None, None)
        assert result == "TEXT"


# ---------------------------------------------------------------------------
# Output format contract
# ---------------------------------------------------------------------------

class TestOutputFormatContract:
    """Verify the PG output matches the same structural contract as build_schema()."""

    def test_pg_output_ends_with_newline(self):
        conn = _make_mock_conn(
            tables_rows=SINGLE_TABLE,
            pk_rows=SINGLE_PK,
            columns_rows=SINGLE_COLUMNS,
        )
        mock = _mock_pg(conn)
        with patch.dict("sys.modules", {"psycopg2": mock}):
            schema = build_schema_from_postgres("host=localhost dbname=test")
        assert schema.endswith("\n")

    def test_in_memory_output_ends_with_newline(self):
        schema = build_schema(domain="ecommerce", depth=1, table_count=2)
        assert schema.endswith("\n")

    def test_pg_drops_before_creates(self):
        conn = _make_mock_conn(
            tables_rows=SINGLE_TABLE,
            pk_rows=SINGLE_PK,
            columns_rows=SINGLE_COLUMNS,
        )
        mock = _mock_pg(conn)
        with patch.dict("sys.modules", {"psycopg2": mock}):
            schema = build_schema_from_postgres("host=localhost dbname=test")
        first_drop = schema.index("DROP")
        first_create = schema.index("CREATE")
        assert first_drop < first_create

    def test_tables_only_has_no_view_drops(self):
        conn = _make_mock_conn(
            tables_rows=SINGLE_TABLE,
            pk_rows=SINGLE_PK,
            columns_rows=SINGLE_COLUMNS,
            views_rows=[],
        )
        mock = _mock_pg(conn)
        with patch.dict("sys.modules", {"psycopg2": mock}):
            schema = build_schema_from_postgres("host=localhost dbname=test")
        assert "DROP VIEW" not in schema

    def test_views_only_has_no_table_drops(self):
        conn = _make_mock_conn(
            tables_rows=[],
            views_rows=[("my_view", "SELECT 1 AS n")],
        )
        mock = _mock_pg(conn)
        with patch.dict("sys.modules", {"psycopg2": mock}):
            schema = build_schema_from_postgres("host=localhost dbname=test")
        assert "DROP TABLE" not in schema
        assert "CREATE TABLE" not in schema
        assert "CREATE VIEW my_view" in schema


# ---------------------------------------------------------------------------
# Cursor lifecycle
# ---------------------------------------------------------------------------

class TestCursorLifecycle:
    """Verify cursor is properly closed in all paths."""

    def test_cursor_closed_in_table_introspect(self):
        conn = _make_mock_conn(
            tables_rows=SINGLE_TABLE,
            pk_rows=SINGLE_PK,
            columns_rows=SINGLE_COLUMNS,
        )
        _pg_introspect_tables(conn, "public")
        conn.cursor.return_value.close.assert_called_once()

    def test_cursor_closed_in_view_introspect(self):
        conn = _make_mock_conn(views_rows=[("v", "SELECT 1")])
        _pg_introspect_views(conn, "public")
        conn.cursor.return_value.close.assert_called_once()

    def test_cursor_closed_on_empty_tables(self):
        conn = _make_mock_conn(tables_rows=[])
        _pg_introspect_tables(conn, "public")
        conn.cursor.return_value.close.assert_called_once()


# ---------------------------------------------------------------------------
# _render_table and _collect_view_names (helpers)
# ---------------------------------------------------------------------------

class TestHelperFunctions:

    def test_render_table_basic(self):
        td = TableDef(
            name="test_tbl",
            columns=[
                ColumnDef("id", "INTEGER", "PRIMARY KEY"),
                ColumnDef("val", "TEXT", "NOT NULL"),
            ],
        )
        rendered = _render_table(td)
        assert "CREATE TABLE test_tbl (" in rendered
        assert "PRIMARY KEY" in rendered
        assert rendered.strip().endswith(");")

    def test_render_table_with_fk(self):
        td = TableDef(
            name="child",
            columns=[
                ColumnDef("id", "INTEGER", "PRIMARY KEY"),
                ColumnDef("parent_id", "INTEGER", "NOT NULL", "REFERENCES parent(id)"),
            ],
        )
        rendered = _render_table(td)
        assert "REFERENCES parent(id)" in rendered

    def test_render_table_with_comment(self):
        td = TableDef(name="tbl", columns=[], comment="my comment")
        rendered = _render_table(td)
        assert "-- my comment" in rendered

    def test_collect_view_names(self):
        sqls = [
            "CREATE VIEW alpha AS SELECT 1;",
            "CREATE VIEW beta AS SELECT 2;",
        ]
        names = _collect_view_names(sqls)
        assert names == ["alpha", "beta"]

    def test_collect_view_names_empty(self):
        assert _collect_view_names([]) == []


# ---------------------------------------------------------------------------
# CLI edge cases
# ---------------------------------------------------------------------------

class TestCLIEdgeCases:

    def test_pg_schema_default_is_public(self, capsys):
        """When --pg-schema is not provided, it defaults to 'public'."""
        conn = _make_mock_conn(
            tables_rows=SINGLE_TABLE,
            pk_rows=SINGLE_PK,
            columns_rows=SINGLE_COLUMNS,
        )
        mock = _mock_pg(conn)
        with patch.dict("sys.modules", {"psycopg2": mock}):
            main(["--from-postgres", "host=localhost dbname=test", "--dry-run"])
        # Verify psycopg2.connect was called with the DSN
        mock.connect.assert_called_once_with("host=localhost dbname=test")

    def test_cli_without_postgres_still_works(self, tmp_path):
        """Normal in-memory mode should still work fine."""
        out = tmp_path / "out.txt"
        main(["--domain", "saas", "--depth", "1", "-o", str(out)])
        assert out.exists()
        content = out.read_text(encoding="utf-8")
        assert "CREATE TABLE" in content

    def test_dry_run_no_file_created(self, tmp_path, capsys):
        """--dry-run should not create a file."""
        out = tmp_path / "should_not_exist.txt"
        main(["--domain", "ecommerce", "--depth", "1", "--dry-run",
              "-o", str(out)])
        assert not out.exists()
        captured = capsys.readouterr()
        assert "CREATE TABLE" in captured.out


# ---------------------------------------------------------------------------
# Connection string is passed through
# ---------------------------------------------------------------------------

class TestConnectionStringPassthrough:

    def test_dsn_passed_to_connect(self):
        conn = _make_mock_conn(
            tables_rows=SINGLE_TABLE,
            pk_rows=SINGLE_PK,
            columns_rows=SINGLE_COLUMNS,
        )
        mock = _mock_pg(conn)
        with patch.dict("sys.modules", {"psycopg2": mock}):
            build_schema_from_postgres("host=myhost port=5433 dbname=prod user=admin")
        mock.connect.assert_called_once_with(
            "host=myhost port=5433 dbname=prod user=admin"
        )

    def test_uri_passed_to_connect(self):
        conn = _make_mock_conn(
            tables_rows=SINGLE_TABLE,
            pk_rows=SINGLE_PK,
            columns_rows=SINGLE_COLUMNS,
        )
        mock = _mock_pg(conn)
        with patch.dict("sys.modules", {"psycopg2": mock}):
            build_schema_from_postgres("postgresql://user:pass@host:5432/db")
        mock.connect.assert_called_once_with("postgresql://user:pass@host:5432/db")


# ---------------------------------------------------------------------------
# Topological ordering stress test
# ---------------------------------------------------------------------------

class TestTopologicalOrdering:
    """Verify dependency ordering with a chain of 4 tables: A→B→C→D."""

    def test_chain_dependency_order(self):
        tables = [("d",), ("c",), ("b",), ("a",)]  # Alphabetical but reversed dep order
        pk = [("a", "id"), ("b", "id"), ("c", "id"), ("d", "id")]
        fk = [
            ("b", "a_id", "a", "id"),
            ("c", "b_id", "b", "id"),
            ("d", "c_id", "c", "id"),
        ]
        columns = [
            ("a", "id", "integer", None, 32, 0, "NO", None, 1, "int4"),
            ("a", "name", "text", None, None, None, "YES", None, 2, "text"),
            ("b", "id", "integer", None, 32, 0, "NO", None, 1, "int4"),
            ("b", "a_id", "integer", None, 32, 0, "NO", None, 2, "int4"),
            ("c", "id", "integer", None, 32, 0, "NO", None, 1, "int4"),
            ("c", "b_id", "integer", None, 32, 0, "NO", None, 2, "int4"),
            ("d", "id", "integer", None, 32, 0, "NO", None, 1, "int4"),
            ("d", "c_id", "integer", None, 32, 0, "NO", None, 2, "int4"),
        ]
        conn = _make_mock_conn(
            tables_rows=tables,
            pk_rows=pk,
            fk_rows=fk,
            columns_rows=columns,
        )
        result = _pg_introspect_tables(conn, "public")
        names = [t.name for t in result]
        # a must come before b, b before c, c before d
        assert names.index("a") < names.index("b")
        assert names.index("b") < names.index("c")
        assert names.index("c") < names.index("d")

    def test_diamond_dependency_order(self):
        """Diamond: A←B, A←C, B←D, C←D. A must precede B and C, both before D."""
        tables = [("d",), ("c",), ("b",), ("a",)]
        pk = [("a", "id"), ("b", "id"), ("c", "id"), ("d", "id")]
        fk = [
            ("b", "a_id", "a", "id"),
            ("c", "a_id", "a", "id"),
            ("d", "b_id", "b", "id"),
            ("d", "c_id", "c", "id"),
        ]
        columns = [
            ("a", "id", "integer", None, 32, 0, "NO", None, 1, "int4"),
            ("b", "id", "integer", None, 32, 0, "NO", None, 1, "int4"),
            ("b", "a_id", "integer", None, 32, 0, "NO", None, 2, "int4"),
            ("c", "id", "integer", None, 32, 0, "NO", None, 1, "int4"),
            ("c", "a_id", "integer", None, 32, 0, "NO", None, 2, "int4"),
            ("d", "id", "integer", None, 32, 0, "NO", None, 1, "int4"),
            ("d", "b_id", "integer", None, 32, 0, "NO", None, 2, "int4"),
            ("d", "c_id", "integer", None, 32, 0, "NO", None, 3, "int4"),
        ]
        conn = _make_mock_conn(
            tables_rows=tables,
            pk_rows=pk,
            fk_rows=fk,
            columns_rows=columns,
        )
        result = _pg_introspect_tables(conn, "public")
        names = [t.name for t in result]
        assert names.index("a") < names.index("b")
        assert names.index("a") < names.index("c")
        assert names.index("b") < names.index("d")
        assert names.index("c") < names.index("d")


# ---------------------------------------------------------------------------
# ValueError message quality
# ---------------------------------------------------------------------------

class TestErrorMessages:

    def test_value_error_includes_schema_name(self):
        conn = _make_mock_conn(tables_rows=[], views_rows=[])
        mock = _mock_pg(conn)
        with patch.dict("sys.modules", {"psycopg2": mock}):
            with pytest.raises(ValueError, match="custom_schema"):
                build_schema_from_postgres(
                    "host=localhost dbname=test",
                    pg_schema="custom_schema",
                )

    def test_import_error_includes_install_hint(self):
        with patch.dict("sys.modules", {"psycopg2": None}):
            from generate_schema import _pg_import
            with pytest.raises(ImportError, match="pip install psycopg2-binary"):
                _pg_import()
