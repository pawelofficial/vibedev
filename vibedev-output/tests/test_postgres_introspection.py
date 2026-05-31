"""Tests for the PostgreSQL-backed schema.txt generator feature.

All tests use mock objects — no live PostgreSQL connection is required.
"""

import os
import re
import sys
from unittest.mock import MagicMock, patch, call

import pytest

# Ensure the project root is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from generate_schema import (
    _pg_format_type,
    _pg_introspect_tables,
    _pg_introspect_views,
    build_schema_from_postgres,
    ColumnDef,
    TableDef,
    main,
)


# ---------------------------------------------------------------------------
# Helpers — mock cursor / connection factories
# ---------------------------------------------------------------------------

def _make_mock_conn(
    tables_rows=None,
    columns_rows=None,
    pk_rows=None,
    fk_rows=None,
    views_rows=None,
):
    """Build a mock psycopg2 connection that returns canned query results.

    The mock cursor dispatches results based on the SQL query string.
    """
    tables_rows = tables_rows or []
    columns_rows = columns_rows or []
    pk_rows = pk_rows or []
    fk_rows = fk_rows or []
    views_rows = views_rows or []

    cursor = MagicMock()

    # Track execute calls and return appropriate results for fetchall
    call_results = []
    original_execute = cursor.execute

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


# A minimal two-table schema with an FK relationship and one view.
MINI_TABLES = [("users",), ("orders",)]
MINI_PK = [("users", "id"), ("orders", "id")]
MINI_FK = [("orders", "user_id", "users", "id")]
MINI_COLUMNS = [
    # table_name, column_name, data_type, char_max, num_prec, num_scale,
    # is_nullable, column_default, ordinal_position, udt_name
    ("users", "id", "bigint", None, 64, 0, "NO", None, 1, "int8"),
    ("users", "email", "character varying", 255, None, None, "NO", None, 2, "varchar"),
    ("users", "name", "text", None, None, None, "YES", None, 3, "text"),
    ("users", "signup_ts", "timestamp with time zone", None, None, None, "NO", None, 4, "timestamptz"),
    ("orders", "id", "bigint", None, 64, 0, "NO", None, 1, "int8"),
    ("orders", "user_id", "bigint", None, 64, 0, "NO", None, 2, "int8"),
    ("orders", "total", "numeric", None, 12, 2, "NO", "0", 3, "numeric"),
    ("orders", "status", "text", None, None, None, "NO", "'pending'::text", 4, "text"),
]
MINI_VIEWS = [
    (
        "user_order_summary",
        " SELECT u.id, u.email, count(o.id) AS order_count, "
        "sum(o.total) AS total_spent "
        "FROM users u LEFT JOIN orders o ON o.user_id = u.id "
        "GROUP BY u.id, u.email;",
    ),
]


# ---------------------------------------------------------------------------
# _pg_format_type tests
# ---------------------------------------------------------------------------

class TestPgFormatType:
    """Verify PostgreSQL type → DDL type mapping."""

    def test_bigint(self):
        assert _pg_format_type("bigint", None, 64, 0) == "BIGINT"

    def test_integer(self):
        assert _pg_format_type("integer", None, 32, 0) == "INTEGER"

    def test_boolean(self):
        assert _pg_format_type("boolean", None, None, None) == "BOOLEAN"

    def test_text(self):
        assert _pg_format_type("text", None, None, None) == "TEXT"

    def test_varchar_with_length(self):
        assert _pg_format_type("character varying", 255, None, None) == "VARCHAR(255)"

    def test_varchar_without_length(self):
        assert _pg_format_type("character varying", None, None, None) == "TEXT"

    def test_char_with_length(self):
        assert _pg_format_type("character", 1, None, None) == "CHAR(1)"

    def test_numeric_with_precision_and_scale(self):
        assert _pg_format_type("numeric", None, 12, 2) == "NUMERIC(12, 2)"

    def test_numeric_precision_only(self):
        assert _pg_format_type("numeric", None, 10, 0) == "NUMERIC(10)"

    def test_numeric_bare(self):
        assert _pg_format_type("numeric", None, None, None) == "NUMERIC"

    def test_timestamptz(self):
        assert _pg_format_type("timestamp with time zone", None, None, None) == "TIMESTAMPTZ"

    def test_timestamp(self):
        assert _pg_format_type("timestamp without time zone", None, None, None) == "TIMESTAMP"

    def test_date(self):
        assert _pg_format_type("date", None, None, None) == "DATE"

    def test_jsonb(self):
        assert _pg_format_type("jsonb", None, None, None) == "JSONB"

    def test_uuid(self):
        assert _pg_format_type("uuid", None, None, None) == "UUID"

    def test_double_precision(self):
        assert _pg_format_type("double precision", None, None, None) == "DOUBLE PRECISION"

    def test_array_type_with_udt(self):
        result = _pg_format_type("ARRAY", None, None, None, "_text")
        assert result == "TEXT[]"

    def test_user_defined_with_udt(self):
        result = _pg_format_type("USER-DEFINED", None, None, None, "mood_enum")
        assert result == "MOOD_ENUM"

    def test_unknown_type_uppercased(self):
        result = _pg_format_type("somecustomtype", None, None, None)
        assert result == "SOMECUSTOMTYPE"


# ---------------------------------------------------------------------------
# _pg_introspect_tables tests
# ---------------------------------------------------------------------------

class TestPgIntrospectTables:
    """Verify table introspection from mock cursor results."""

    def test_returns_table_defs(self):
        conn = _make_mock_conn(
            tables_rows=MINI_TABLES,
            pk_rows=MINI_PK,
            fk_rows=MINI_FK,
            columns_rows=MINI_COLUMNS,
        )
        tables = _pg_introspect_tables(conn, "public")
        assert len(tables) == 2
        assert all(isinstance(t, TableDef) for t in tables)

    def test_table_names(self):
        conn = _make_mock_conn(
            tables_rows=MINI_TABLES,
            pk_rows=MINI_PK,
            fk_rows=MINI_FK,
            columns_rows=MINI_COLUMNS,
        )
        tables = _pg_introspect_tables(conn, "public")
        names = [t.name for t in tables]
        assert "users" in names
        assert "orders" in names

    def test_dependency_order_fk_target_first(self):
        """Tables referenced by FKs should appear before the referencing table."""
        conn = _make_mock_conn(
            tables_rows=MINI_TABLES,
            pk_rows=MINI_PK,
            fk_rows=MINI_FK,
            columns_rows=MINI_COLUMNS,
        )
        tables = _pg_introspect_tables(conn, "public")
        names = [t.name for t in tables]
        assert names.index("users") < names.index("orders")

    def test_primary_key_constraint(self):
        conn = _make_mock_conn(
            tables_rows=MINI_TABLES,
            pk_rows=MINI_PK,
            fk_rows=MINI_FK,
            columns_rows=MINI_COLUMNS,
        )
        tables = _pg_introspect_tables(conn, "public")
        users = [t for t in tables if t.name == "users"][0]
        id_col = [c for c in users.columns if c.name == "id"][0]
        assert "PRIMARY KEY" in id_col.constraints

    def test_not_null_constraint(self):
        conn = _make_mock_conn(
            tables_rows=MINI_TABLES,
            pk_rows=MINI_PK,
            fk_rows=MINI_FK,
            columns_rows=MINI_COLUMNS,
        )
        tables = _pg_introspect_tables(conn, "public")
        users = [t for t in tables if t.name == "users"][0]
        email_col = [c for c in users.columns if c.name == "email"][0]
        assert "NOT NULL" in email_col.constraints

    def test_nullable_column_no_not_null(self):
        conn = _make_mock_conn(
            tables_rows=MINI_TABLES,
            pk_rows=MINI_PK,
            fk_rows=MINI_FK,
            columns_rows=MINI_COLUMNS,
        )
        tables = _pg_introspect_tables(conn, "public")
        users = [t for t in tables if t.name == "users"][0]
        name_col = [c for c in users.columns if c.name == "name"][0]
        assert "NOT NULL" not in name_col.constraints

    def test_foreign_key_reference(self):
        conn = _make_mock_conn(
            tables_rows=MINI_TABLES,
            pk_rows=MINI_PK,
            fk_rows=MINI_FK,
            columns_rows=MINI_COLUMNS,
        )
        tables = _pg_introspect_tables(conn, "public")
        orders = [t for t in tables if t.name == "orders"][0]
        user_id_col = [c for c in orders.columns if c.name == "user_id"][0]
        assert user_id_col.fk_ref == "REFERENCES users(id)"

    def test_column_default_value(self):
        conn = _make_mock_conn(
            tables_rows=MINI_TABLES,
            pk_rows=MINI_PK,
            fk_rows=MINI_FK,
            columns_rows=MINI_COLUMNS,
        )
        tables = _pg_introspect_tables(conn, "public")
        orders = [t for t in tables if t.name == "orders"][0]
        total_col = [c for c in orders.columns if c.name == "total"][0]
        assert "DEFAULT 0" in total_col.constraints

    def test_sequence_default_skipped(self):
        """nextval(...) defaults should not appear in the DDL."""
        columns_with_seq = [
            ("items", "id", "bigint", None, 64, 0, "NO",
             "nextval('items_id_seq'::regclass)", 1, "int8"),
            ("items", "name", "text", None, None, None, "YES", None, 2, "text"),
        ]
        conn = _make_mock_conn(
            tables_rows=[("items",)],
            pk_rows=[("items", "id")],
            fk_rows=[],
            columns_rows=columns_with_seq,
        )
        tables = _pg_introspect_tables(conn, "public")
        items = tables[0]
        id_col = [c for c in items.columns if c.name == "id"][0]
        assert "nextval" not in id_col.constraints

    def test_empty_schema_returns_empty(self):
        conn = _make_mock_conn(tables_rows=[])
        tables = _pg_introspect_tables(conn, "public")
        assert tables == []

    def test_varchar_type_mapping(self):
        conn = _make_mock_conn(
            tables_rows=MINI_TABLES,
            pk_rows=MINI_PK,
            fk_rows=MINI_FK,
            columns_rows=MINI_COLUMNS,
        )
        tables = _pg_introspect_tables(conn, "public")
        users = [t for t in tables if t.name == "users"][0]
        email_col = [c for c in users.columns if c.name == "email"][0]
        assert email_col.sql_type == "VARCHAR(255)"

    def test_numeric_type_with_scale(self):
        conn = _make_mock_conn(
            tables_rows=MINI_TABLES,
            pk_rows=MINI_PK,
            fk_rows=MINI_FK,
            columns_rows=MINI_COLUMNS,
        )
        tables = _pg_introspect_tables(conn, "public")
        orders = [t for t in tables if t.name == "orders"][0]
        total_col = [c for c in orders.columns if c.name == "total"][0]
        assert total_col.sql_type == "NUMERIC(12, 2)"

    def test_column_order_preserved(self):
        conn = _make_mock_conn(
            tables_rows=MINI_TABLES,
            pk_rows=MINI_PK,
            fk_rows=MINI_FK,
            columns_rows=MINI_COLUMNS,
        )
        tables = _pg_introspect_tables(conn, "public")
        users = [t for t in tables if t.name == "users"][0]
        col_names = [c.name for c in users.columns]
        assert col_names == ["id", "email", "name", "signup_ts"]


# ---------------------------------------------------------------------------
# _pg_introspect_views tests
# ---------------------------------------------------------------------------

class TestPgIntrospectViews:
    """Verify view introspection from mock cursor results."""

    def test_returns_create_view_strings(self):
        conn = _make_mock_conn(views_rows=MINI_VIEWS)
        view_sqls = _pg_introspect_views(conn, "public")
        assert len(view_sqls) == 1
        assert view_sqls[0].startswith("CREATE VIEW user_order_summary AS")

    def test_view_ends_with_semicolon(self):
        conn = _make_mock_conn(views_rows=MINI_VIEWS)
        view_sqls = _pg_introspect_views(conn, "public")
        assert view_sqls[0].rstrip().endswith(";")

    def test_no_double_semicolon(self):
        """pg_views definitions sometimes include a trailing semicolon;
        we should not produce ';;'."""
        conn = _make_mock_conn(views_rows=MINI_VIEWS)
        view_sqls = _pg_introspect_views(conn, "public")
        assert ";;" not in view_sqls[0]

    def test_empty_views_returns_empty(self):
        conn = _make_mock_conn(views_rows=[])
        view_sqls = _pg_introspect_views(conn, "public")
        assert view_sqls == []

    def test_multiple_views_sorted(self):
        views = [
            ("beta_view", "SELECT 1;"),
            ("alpha_view", "SELECT 2;"),
        ]
        conn = _make_mock_conn(views_rows=views)
        view_sqls = _pg_introspect_views(conn, "public")
        assert len(view_sqls) == 2
        assert "beta_view" in view_sqls[0]
        assert "alpha_view" in view_sqls[1]

    def test_view_body_preserved(self):
        views = [
            ("test_view",
             " SELECT u.id, u.name FROM users u WHERE u.active = true"),
        ]
        conn = _make_mock_conn(views_rows=views)
        view_sqls = _pg_introspect_views(conn, "public")
        assert "u.id" in view_sqls[0]
        assert "u.name" in view_sqls[0]
        assert "WHERE" in view_sqls[0]


# ---------------------------------------------------------------------------
# build_schema_from_postgres tests
# ---------------------------------------------------------------------------

class TestBuildSchemaFromPostgres:
    """Verify the full introspection-to-DDL pipeline (mocked)."""

    def _mock_psycopg2_connect(self, conn):
        """Return a mock psycopg2 module whose .connect() returns conn."""
        mock_pg = MagicMock()
        mock_pg.connect.return_value = conn
        return mock_pg

    def test_produces_create_table_and_view(self):
        conn = _make_mock_conn(
            tables_rows=MINI_TABLES,
            pk_rows=MINI_PK,
            fk_rows=MINI_FK,
            columns_rows=MINI_COLUMNS,
            views_rows=MINI_VIEWS,
        )
        mock_pg = self._mock_psycopg2_connect(conn)
        with patch.dict("sys.modules", {"psycopg2": mock_pg}):
            schema = build_schema_from_postgres("host=localhost dbname=test")

        assert "CREATE TABLE" in schema
        assert "CREATE VIEW" in schema

    def test_has_drop_statements(self):
        conn = _make_mock_conn(
            tables_rows=MINI_TABLES,
            pk_rows=MINI_PK,
            fk_rows=MINI_FK,
            columns_rows=MINI_COLUMNS,
            views_rows=MINI_VIEWS,
        )
        mock_pg = self._mock_psycopg2_connect(conn)
        with patch.dict("sys.modules", {"psycopg2": mock_pg}):
            schema = build_schema_from_postgres("host=localhost dbname=test")

        assert "DROP VIEW IF EXISTS" in schema
        assert "DROP TABLE IF EXISTS" in schema

    def test_table_count_matches(self):
        conn = _make_mock_conn(
            tables_rows=MINI_TABLES,
            pk_rows=MINI_PK,
            fk_rows=MINI_FK,
            columns_rows=MINI_COLUMNS,
            views_rows=MINI_VIEWS,
        )
        mock_pg = self._mock_psycopg2_connect(conn)
        with patch.dict("sys.modules", {"psycopg2": mock_pg}):
            schema = build_schema_from_postgres("host=localhost dbname=test")

        assert schema.count("CREATE TABLE") == 2

    def test_view_count_matches(self):
        conn = _make_mock_conn(
            tables_rows=MINI_TABLES,
            pk_rows=MINI_PK,
            fk_rows=MINI_FK,
            columns_rows=MINI_COLUMNS,
            views_rows=MINI_VIEWS,
        )
        mock_pg = self._mock_psycopg2_connect(conn)
        with patch.dict("sys.modules", {"psycopg2": mock_pg}):
            schema = build_schema_from_postgres("host=localhost dbname=test")

        assert schema.count("CREATE VIEW") == 1

    def test_drop_count_matches_create_count(self):
        conn = _make_mock_conn(
            tables_rows=MINI_TABLES,
            pk_rows=MINI_PK,
            fk_rows=MINI_FK,
            columns_rows=MINI_COLUMNS,
            views_rows=MINI_VIEWS,
        )
        mock_pg = self._mock_psycopg2_connect(conn)
        with patch.dict("sys.modules", {"psycopg2": mock_pg}):
            schema = build_schema_from_postgres("host=localhost dbname=test")

        drop_tables = len(re.findall(r"DROP TABLE IF EXISTS", schema))
        create_tables = len(re.findall(r"CREATE TABLE", schema))
        assert drop_tables == create_tables

        drop_views = len(re.findall(r"DROP VIEW IF EXISTS", schema))
        create_views = len(re.findall(r"CREATE VIEW", schema))
        assert drop_views == create_views

    def test_connection_closed_after_use(self):
        conn = _make_mock_conn(
            tables_rows=MINI_TABLES,
            pk_rows=MINI_PK,
            fk_rows=MINI_FK,
            columns_rows=MINI_COLUMNS,
            views_rows=MINI_VIEWS,
        )
        mock_pg = self._mock_psycopg2_connect(conn)
        with patch.dict("sys.modules", {"psycopg2": mock_pg}):
            build_schema_from_postgres("host=localhost dbname=test")

        conn.close.assert_called_once()

    def test_connection_closed_on_error(self):
        conn = _make_mock_conn(tables_rows=MINI_TABLES)
        # Force an error during introspection
        cursor = conn.cursor.return_value
        original_execute = cursor.execute.side_effect

        call_count = [0]
        def _fail_on_second(sql, params=None):
            call_count[0] += 1
            if call_count[0] >= 2:
                raise RuntimeError("simulated error")
            original_execute(sql, params)

        cursor.execute.side_effect = _fail_on_second

        mock_pg = self._mock_psycopg2_connect(conn)
        with patch.dict("sys.modules", {"psycopg2": mock_pg}):
            with pytest.raises(RuntimeError):
                build_schema_from_postgres("host=localhost dbname=test")

        conn.close.assert_called_once()

    def test_empty_schema_raises_value_error(self):
        conn = _make_mock_conn(
            tables_rows=[],
            columns_rows=[],
            pk_rows=[],
            fk_rows=[],
            views_rows=[],
        )
        mock_pg = self._mock_psycopg2_connect(conn)
        with patch.dict("sys.modules", {"psycopg2": mock_pg}):
            with pytest.raises(ValueError, match="No tables or views"):
                build_schema_from_postgres("host=localhost dbname=test")

    def test_tables_only_no_views_succeeds(self):
        conn = _make_mock_conn(
            tables_rows=MINI_TABLES,
            pk_rows=MINI_PK,
            fk_rows=MINI_FK,
            columns_rows=MINI_COLUMNS,
            views_rows=[],
        )
        mock_pg = self._mock_psycopg2_connect(conn)
        with patch.dict("sys.modules", {"psycopg2": mock_pg}):
            schema = build_schema_from_postgres("host=localhost dbname=test")

        assert "CREATE TABLE" in schema
        assert "CREATE VIEW" not in schema

    def test_views_only_no_tables_succeeds(self):
        conn = _make_mock_conn(
            tables_rows=[],
            columns_rows=[],
            pk_rows=[],
            fk_rows=[],
            views_rows=MINI_VIEWS,
        )
        mock_pg = self._mock_psycopg2_connect(conn)
        with patch.dict("sys.modules", {"psycopg2": mock_pg}):
            schema = build_schema_from_postgres("host=localhost dbname=test")

        assert "CREATE VIEW" in schema
        assert "CREATE TABLE" not in schema

    def test_passes_pg_schema_param(self):
        conn = _make_mock_conn(
            tables_rows=MINI_TABLES,
            pk_rows=MINI_PK,
            fk_rows=MINI_FK,
            columns_rows=MINI_COLUMNS,
            views_rows=MINI_VIEWS,
        )
        mock_pg = self._mock_psycopg2_connect(conn)
        with patch.dict("sys.modules", {"psycopg2": mock_pg}):
            build_schema_from_postgres(
                "host=localhost dbname=test",
                pg_schema="analytics",
            )

        # Verify the schema name was passed to queries
        cursor = conn.cursor.return_value
        for c in cursor.execute.call_args_list:
            args = c[0]
            if len(args) >= 2 and args[1]:
                # The first param should be the schema name
                assert "analytics" in args[1] or args[1] == ("analytics",)

    def test_output_format_matches_build_schema(self):
        """Output should follow the same structure: DROPs, then CREATE TABLEs,
        then CREATE VIEWs."""
        conn = _make_mock_conn(
            tables_rows=MINI_TABLES,
            pk_rows=MINI_PK,
            fk_rows=MINI_FK,
            columns_rows=MINI_COLUMNS,
            views_rows=MINI_VIEWS,
        )
        mock_pg = self._mock_psycopg2_connect(conn)
        with patch.dict("sys.modules", {"psycopg2": mock_pg}):
            schema = build_schema_from_postgres("host=localhost dbname=test")

        # DROPs come first
        first_drop = schema.index("DROP")
        first_create_table = schema.index("CREATE TABLE")
        first_create_view = schema.index("CREATE VIEW")
        assert first_drop < first_create_table < first_create_view

    def test_foreign_key_appears_in_output(self):
        conn = _make_mock_conn(
            tables_rows=MINI_TABLES,
            pk_rows=MINI_PK,
            fk_rows=MINI_FK,
            columns_rows=MINI_COLUMNS,
            views_rows=MINI_VIEWS,
        )
        mock_pg = self._mock_psycopg2_connect(conn)
        with patch.dict("sys.modules", {"psycopg2": mock_pg}):
            schema = build_schema_from_postgres("host=localhost dbname=test")

        assert "REFERENCES users(id)" in schema

    def test_primary_key_appears_in_output(self):
        conn = _make_mock_conn(
            tables_rows=MINI_TABLES,
            pk_rows=MINI_PK,
            fk_rows=MINI_FK,
            columns_rows=MINI_COLUMNS,
            views_rows=MINI_VIEWS,
        )
        mock_pg = self._mock_psycopg2_connect(conn)
        with patch.dict("sys.modules", {"psycopg2": mock_pg}):
            schema = build_schema_from_postgres("host=localhost dbname=test")

        assert "PRIMARY KEY" in schema

    def test_every_create_table_has_semicolon(self):
        conn = _make_mock_conn(
            tables_rows=MINI_TABLES,
            pk_rows=MINI_PK,
            fk_rows=MINI_FK,
            columns_rows=MINI_COLUMNS,
            views_rows=MINI_VIEWS,
        )
        mock_pg = self._mock_psycopg2_connect(conn)
        with patch.dict("sys.modules", {"psycopg2": mock_pg}):
            schema = build_schema_from_postgres("host=localhost dbname=test")

        tables = re.findall(
            r"CREATE TABLE\s+\w+\s*\(.*?\);",
            schema,
            re.DOTALL | re.IGNORECASE,
        )
        assert len(tables) == 2
        for t in tables:
            assert t.strip().endswith(");")


# ---------------------------------------------------------------------------
# psycopg2 import guard
# ---------------------------------------------------------------------------

class TestPsycopg2ImportGuard:
    """Verify the lazy import produces a clear error message."""

    def test_import_error_without_psycopg2(self):
        with patch.dict("sys.modules", {"psycopg2": None}):
            with pytest.raises(ImportError, match="psycopg2"):
                from generate_schema import _pg_import
                _pg_import()


# ---------------------------------------------------------------------------
# CLI --from-postgres flag tests
# ---------------------------------------------------------------------------

class TestCLIPostgresFlag:
    """Verify CLI integration with --from-postgres."""

    def test_from_postgres_dry_run(self, capsys):
        conn = _make_mock_conn(
            tables_rows=MINI_TABLES,
            pk_rows=MINI_PK,
            fk_rows=MINI_FK,
            columns_rows=MINI_COLUMNS,
            views_rows=MINI_VIEWS,
        )
        mock_pg = MagicMock()
        mock_pg.connect.return_value = conn
        with patch.dict("sys.modules", {"psycopg2": mock_pg}):
            main(["--from-postgres", "host=localhost dbname=test", "--dry-run"])
        captured = capsys.readouterr()
        assert "CREATE TABLE" in captured.out
        assert "CREATE VIEW" in captured.out

    def test_from_postgres_writes_file(self, tmp_path):
        conn = _make_mock_conn(
            tables_rows=MINI_TABLES,
            pk_rows=MINI_PK,
            fk_rows=MINI_FK,
            columns_rows=MINI_COLUMNS,
            views_rows=MINI_VIEWS,
        )
        mock_pg = MagicMock()
        mock_pg.connect.return_value = conn
        output = tmp_path / "pg_schema.txt"
        with patch.dict("sys.modules", {"psycopg2": mock_pg}):
            main(["--from-postgres", "host=localhost dbname=test",
                  "-o", str(output)])
        assert output.exists()
        content = output.read_text(encoding="utf-8")
        assert "CREATE TABLE" in content

    def test_from_postgres_stats_show_source(self, tmp_path, capsys):
        conn = _make_mock_conn(
            tables_rows=MINI_TABLES,
            pk_rows=MINI_PK,
            fk_rows=MINI_FK,
            columns_rows=MINI_COLUMNS,
            views_rows=MINI_VIEWS,
        )
        mock_pg = MagicMock()
        mock_pg.connect.return_value = conn
        output = tmp_path / "pg_test.txt"
        with patch.dict("sys.modules", {"psycopg2": mock_pg}):
            main(["--from-postgres", "host=localhost dbname=test",
                  "-o", str(output)])
        captured = capsys.readouterr()
        assert "PostgreSQL" in captured.out

    def test_from_postgres_with_pg_schema(self, capsys):
        conn = _make_mock_conn(
            tables_rows=MINI_TABLES,
            pk_rows=MINI_PK,
            fk_rows=MINI_FK,
            columns_rows=MINI_COLUMNS,
            views_rows=MINI_VIEWS,
        )
        mock_pg = MagicMock()
        mock_pg.connect.return_value = conn
        with patch.dict("sys.modules", {"psycopg2": mock_pg}):
            main(["--from-postgres", "host=localhost dbname=test",
                  "--pg-schema", "analytics", "--dry-run"])
        # Should not raise
        captured = capsys.readouterr()
        assert "CREATE TABLE" in captured.out

    def test_domain_flags_ignored_in_postgres_mode(self, capsys):
        """When --from-postgres is set, --domain/--depth/--tables are ignored."""
        conn = _make_mock_conn(
            tables_rows=MINI_TABLES,
            pk_rows=MINI_PK,
            fk_rows=MINI_FK,
            columns_rows=MINI_COLUMNS,
            views_rows=MINI_VIEWS,
        )
        mock_pg = MagicMock()
        mock_pg.connect.return_value = conn
        with patch.dict("sys.modules", {"psycopg2": mock_pg}):
            main(["--from-postgres", "host=localhost dbname=test",
                  "--domain", "healthcare", "--depth", "1",
                  "--dry-run"])
        captured = capsys.readouterr()
        # Should produce the mock PG output, not healthcare domain
        assert "CREATE TABLE users" in captured.out or "CREATE TABLE orders" in captured.out
        assert "raw_patients" not in captured.out


# ---------------------------------------------------------------------------
# Edge cases and complex schemas
# ---------------------------------------------------------------------------

class TestComplexSchemas:
    """Test with more complex mock schemas."""

    def test_table_with_many_column_types(self):
        columns = [
            ("mixed", "id", "bigint", None, 64, 0, "NO", None, 1, "int8"),
            ("mixed", "name", "character varying", 100, None, None, "YES", None, 2, "varchar"),
            ("mixed", "amount", "numeric", None, 18, 4, "NO", "0.0", 3, "numeric"),
            ("mixed", "is_active", "boolean", None, None, None, "NO", "true", 4, "bool"),
            ("mixed", "created", "timestamp with time zone", None, None, None, "NO", None, 5, "timestamptz"),
            ("mixed", "data", "jsonb", None, None, None, "YES", None, 6, "jsonb"),
            ("mixed", "tags", "ARRAY", None, None, None, "YES", None, 7, "_text"),
            ("mixed", "score", "double precision", None, None, None, "YES", None, 8, "float8"),
        ]
        conn = _make_mock_conn(
            tables_rows=[("mixed",)],
            pk_rows=[("mixed", "id")],
            fk_rows=[],
            columns_rows=columns,
        )
        mock_pg = MagicMock()
        mock_pg.connect.return_value = conn
        with patch.dict("sys.modules", {"psycopg2": mock_pg}):
            schema = build_schema_from_postgres("host=localhost dbname=test")

        assert "VARCHAR(100)" in schema
        assert "NUMERIC(18, 4)" in schema
        assert "BOOLEAN" in schema
        assert "TIMESTAMPTZ" in schema
        assert "JSONB" in schema
        assert "TEXT[]" in schema
        assert "DOUBLE PRECISION" in schema

    def test_multiple_foreign_keys(self):
        tables = [("departments",), ("employees",), ("projects",)]
        pk = [("departments", "id"), ("employees", "id"), ("projects", "id")]
        fk = [
            ("employees", "dept_id", "departments", "id"),
            ("projects", "lead_id", "employees", "id"),
        ]
        columns = [
            ("departments", "id", "integer", None, 32, 0, "NO", None, 1, "int4"),
            ("departments", "name", "text", None, None, None, "NO", None, 2, "text"),
            ("employees", "id", "integer", None, 32, 0, "NO", None, 1, "int4"),
            ("employees", "name", "text", None, None, None, "NO", None, 2, "text"),
            ("employees", "dept_id", "integer", None, 32, 0, "NO", None, 3, "int4"),
            ("projects", "id", "integer", None, 32, 0, "NO", None, 1, "int4"),
            ("projects", "name", "text", None, None, None, "NO", None, 2, "text"),
            ("projects", "lead_id", "integer", None, 32, 0, "YES", None, 3, "int4"),
        ]
        conn = _make_mock_conn(
            tables_rows=tables,
            pk_rows=pk,
            fk_rows=fk,
            columns_rows=columns,
        )
        mock_pg = MagicMock()
        mock_pg.connect.return_value = conn
        with patch.dict("sys.modules", {"psycopg2": mock_pg}):
            schema = build_schema_from_postgres("host=localhost dbname=test")

        assert "REFERENCES departments(id)" in schema
        assert "REFERENCES employees(id)" in schema
        # Dependency order: departments first, then employees, then projects
        dept_pos = schema.index("CREATE TABLE departments")
        emp_pos = schema.index("CREATE TABLE employees")
        proj_pos = schema.index("CREATE TABLE projects")
        assert dept_pos < emp_pos < proj_pos

    def test_self_referencing_fk(self):
        """A table with an FK to itself (e.g. parent_id)."""
        tables = [("categories",)]
        pk = [("categories", "id")]
        fk = [("categories", "parent_id", "categories", "id")]
        columns = [
            ("categories", "id", "integer", None, 32, 0, "NO", None, 1, "int4"),
            ("categories", "name", "text", None, None, None, "NO", None, 2, "text"),
            ("categories", "parent_id", "integer", None, 32, 0, "YES", None, 3, "int4"),
        ]
        conn = _make_mock_conn(
            tables_rows=tables,
            pk_rows=pk,
            fk_rows=fk,
            columns_rows=columns,
        )
        mock_pg = MagicMock()
        mock_pg.connect.return_value = conn
        with patch.dict("sys.modules", {"psycopg2": mock_pg}):
            schema = build_schema_from_postgres("host=localhost dbname=test")

        assert "REFERENCES categories(id)" in schema
        assert "CREATE TABLE categories" in schema

    def test_multiple_views(self):
        views = [
            ("v_active_users", "SELECT id, name FROM users WHERE active = true"),
            ("v_order_totals", "SELECT user_id, sum(total) AS total FROM orders GROUP BY user_id"),
            ("v_summary", "SELECT u.id, u.name, COALESCE(ot.total, 0) AS total "
                          "FROM v_active_users u LEFT JOIN v_order_totals ot ON ot.user_id = u.id"),
        ]
        conn = _make_mock_conn(
            tables_rows=MINI_TABLES,
            pk_rows=MINI_PK,
            fk_rows=MINI_FK,
            columns_rows=MINI_COLUMNS,
            views_rows=views,
        )
        mock_pg = MagicMock()
        mock_pg.connect.return_value = conn
        with patch.dict("sys.modules", {"psycopg2": mock_pg}):
            schema = build_schema_from_postgres("host=localhost dbname=test")

        assert schema.count("CREATE VIEW") == 3
        assert schema.count("DROP VIEW IF EXISTS") == 3
        assert "v_active_users" in schema
        assert "v_order_totals" in schema
        assert "v_summary" in schema


# ---------------------------------------------------------------------------
# Lineage parser integration (optional)
# ---------------------------------------------------------------------------

class TestPostgresParserIntegration:
    """Verify generated PostgreSQL schemas are parseable by the lineage parser."""

    @pytest.fixture(autouse=True)
    def _check_parser_available(self):
        try:
            from lineage_parser import parse_schema
            self.parse_schema = parse_schema
        except ImportError:
            pytest.skip("lineage_parser not available")

    def test_parser_finds_pg_tables(self):
        conn = _make_mock_conn(
            tables_rows=MINI_TABLES,
            pk_rows=MINI_PK,
            fk_rows=MINI_FK,
            columns_rows=MINI_COLUMNS,
            views_rows=MINI_VIEWS,
        )
        mock_pg = MagicMock()
        mock_pg.connect.return_value = conn
        with patch.dict("sys.modules", {"psycopg2": mock_pg}):
            schema_text = build_schema_from_postgres("host=localhost dbname=test")

        models = self.parse_schema(schema_text)
        assert "users" in models
        assert "orders" in models
        assert models["users"].model_type == "table"
        assert models["orders"].model_type == "table"

    def test_parser_finds_pg_views(self):
        conn = _make_mock_conn(
            tables_rows=MINI_TABLES,
            pk_rows=MINI_PK,
            fk_rows=MINI_FK,
            columns_rows=MINI_COLUMNS,
            views_rows=MINI_VIEWS,
        )
        mock_pg = MagicMock()
        mock_pg.connect.return_value = conn
        with patch.dict("sys.modules", {"psycopg2": mock_pg}):
            schema_text = build_schema_from_postgres("host=localhost dbname=test")

        models = self.parse_schema(schema_text)
        assert "user_order_summary" in models
        assert models["user_order_summary"].model_type == "view"

    def test_parser_extracts_table_columns(self):
        conn = _make_mock_conn(
            tables_rows=MINI_TABLES,
            pk_rows=MINI_PK,
            fk_rows=MINI_FK,
            columns_rows=MINI_COLUMNS,
            views_rows=MINI_VIEWS,
        )
        mock_pg = MagicMock()
        mock_pg.connect.return_value = conn
        with patch.dict("sys.modules", {"psycopg2": mock_pg}):
            schema_text = build_schema_from_postgres("host=localhost dbname=test")

        models = self.parse_schema(schema_text)
        # Model.columns is List[str] (plain column name strings)
        users_cols = models["users"].columns
        assert "id" in users_cols
        assert "email" in users_cols
