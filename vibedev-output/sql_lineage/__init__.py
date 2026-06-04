"""Public API for the sql_lineage package.

Typical usage::

    from sql_lineage import parse_schema

    graph, catalog = parse_schema("schema.sql")
    # or from a string:
    graph, catalog = parse_schema(sql="CREATE TABLE ...; CREATE VIEW ...")

All public symbols are importable directly from this module.
"""

from __future__ import annotations

from pathlib import Path

from .catalog import SchemaCatalog
from .exceptions import (
    CircularDependencyError,
    SchemaParseError,
    UnresolvedReferenceError,
)
from .models import (
    ColumnRef,
    ForeignKeyDef,
    LineageEdge,
    SchemaGraph,
    TableDef,
    ViewDef,
)
from .normalizer import normalize_name
from .parser import SchemaParser
from .resolver import LineageResolver

__all__ = [
    "parse_schema",
    "SchemaGraph",
    "TableDef",
    "ViewDef",
    "ColumnRef",
    "ForeignKeyDef",
    "LineageEdge",
    "SchemaCatalog",
    "SchemaParser",
    "LineageResolver",
    "SchemaParseError",
    "UnresolvedReferenceError",
    "CircularDependencyError",
    "normalize_name",
]


def parse_schema(
    path: str | Path | None = None,
    *,
    sql: str | None = None,
    dialect: str | None = None,
) -> tuple[SchemaGraph, SchemaCatalog]:
    """Parse a SQL schema and resolve column-level lineage in one call.

    Exactly one of *path* or *sql* must be provided.  The default dialect is
    ``None`` (sqlglot generic), which is compatible with sqlglot 30.8.0.
    Pass a dialect string such as ``'postgres'``, ``'mysql'``, ``'tsql'``, or
    ``'sqlite'`` for dialect-specific parsing.

    Args:
        path: Filesystem path to a ``.sql`` file.  Mutually exclusive with
            *sql*.
        sql:  Raw SQL DDL string.  Mutually exclusive with *path*.
        dialect: Optional sqlglot dialect name.  Defaults to ``None``
            (sqlglot generic).  ``'ansi'`` is **not** a valid value for
            sqlglot 30.8.0 and must never be passed.

    Returns:
        A ``(SchemaGraph, SchemaCatalog)`` tuple where the graph holds all
        tables, views, and resolved lineage edges, and the catalog provides
        the read-only query API over them.

    Raises:
        ValueError: When both *path* and *sql* are ``None``, or when both
            are provided simultaneously.
        SchemaParseError: When the SQL cannot be parsed or contains
            structural errors (duplicate names, etc.).
        CircularDependencyError: When a cycle is detected in the view
            dependency graph during lineage resolution.
    """
    if path is None and sql is None:
        raise ValueError("Exactly one of 'path' or 'sql' must be provided; both are None.")
    if path is not None and sql is not None:
        raise ValueError("Exactly one of 'path' or 'sql' must be provided; both were given.")

    parser = SchemaParser(dialect=dialect)

    if path is not None:
        graph = parser.parse_file(path)
    else:
        assert sql is not None  # narrowing for type checkers
        graph = parser.parse_statements(sql)

    resolver = LineageResolver(dialect=dialect)
    resolver.resolve(graph)

    catalog = SchemaCatalog(graph)
    return graph, catalog
