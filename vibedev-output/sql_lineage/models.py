"""
Immutable (frozen) dataclasses and one mutable container that together form
the complete in-memory representation of a parsed schema and its column-level
lineage graph.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ColumnRef:
    """Uniquely identifies one column within the schema.

    Both *table* and *column* are already normalised (lowercase, unquoted)
    by the caller before construction.  Hashable; safe to use as a dict key
    or set member.
    """

    table: str
    """Normalised table or view name."""

    column: str
    """Normalised column name."""


@dataclass(frozen=True)
class ForeignKeyDef:
    """Represents one foreign-key constraint: from_table.from_col -> to_table.to_col."""

    from_table: str
    """Normalised name of the referencing (child) table."""

    from_col: str
    """Normalised name of the referencing column in the child table."""

    to_table: str
    """Normalised name of the referenced (parent) table."""

    to_col: str
    """Normalised name of the referenced column in the parent table."""


@dataclass(frozen=True)
class TableDef:
    """Represents one CREATE TABLE statement.

    Attributes:
        name: Normalised table name.
        columns: Ordered tuple of normalised column names.
        primary_keys: Set of normalised column names forming the primary key.
            Empty ``frozenset`` when no PK is declared.
        foreign_keys: Tuple of :class:`ForeignKeyDef` instances from FOREIGN KEY
            constraints.  Empty tuple when none are declared.
    """

    name: str
    columns: tuple[str, ...]
    primary_keys: frozenset[str] = field(default_factory=frozenset)
    foreign_keys: tuple[ForeignKeyDef, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ViewDef:
    """Represents one CREATE VIEW statement.

    Attributes:
        name: Normalised view name.
        query: Original query text as found in the DDL.
        output_columns: Resolved output column list.  May contain ``'*'`` when
            a wildcard is unresolved at parse time.
        dependencies: Set of normalised table/view names referenced in FROM and
            JOIN clauses, excluding CTE aliases.
    """

    name: str
    query: str
    output_columns: tuple[str, ...]
    dependencies: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True)
class LineageEdge:
    """A directed edge source_column -> target_column.

    Meaning: the *target* column is derived from the *source* column.
    """

    source: ColumnRef
    """Upstream column contributing data."""

    target: ColumnRef
    """Downstream view output column that depends on *source*."""


@dataclass
class SchemaGraph:
    """Mutable container holding the full parsed schema.

    This is the central data structure passed between the parser, resolver, and
    catalog layers.  It is intentionally **not** frozen — the resolver mutates
    ``edges`` in-place after the parser has populated ``tables`` and ``views``.

    Attributes:
        tables: Mapping of normalised table name -> :class:`TableDef`.
        views:  Mapping of normalised view name  -> :class:`ViewDef`.
        edges:  Ordered list of column-level lineage edges, populated by the
                resolver after parsing is complete.
    """

    tables: dict[str, TableDef] = field(default_factory=dict)
    views: dict[str, ViewDef] = field(default_factory=dict)
    edges: list[LineageEdge] = field(default_factory=list)
