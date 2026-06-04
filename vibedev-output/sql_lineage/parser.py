"""SchemaParser: reads a SQL schema file (or SQL string), delegates to sqlglot
for AST parsing, and populates a SchemaGraph with TableDef and ViewDef objects.

Column-level lineage resolution is intentionally NOT done here — that is the
resolver's responsibility.

IMPORTANT: the default dialect is ``None`` (sqlglot generic), NOT ``'ansi'``,
because ``'ansi'`` is not a supported dialect name in sqlglot 30.8.0.
"""

from __future__ import annotations

from pathlib import Path

import sqlglot
import sqlglot.expressions as exp

from .exceptions import SchemaParseError
from .models import ForeignKeyDef, SchemaGraph, TableDef, ViewDef
from .normalizer import normalize_name


class SchemaParser:
    """Parses DDL SQL using sqlglot into a :class:`~sql_lineage.models.SchemaGraph`.

    Handles ``CREATE TABLE`` (columns, PK inline/constraint, FK inline/constraint)
    and ``CREATE VIEW`` (SELECT AST, output columns, dependency table names).
    Non-DDL statements and ``None`` nodes returned by the parser are silently
    ignored.

    Attributes:
        dialect:
            sqlglot dialect string, e.g. ``'postgres'``, ``'mysql'``,
            ``'tsql'``.  Defaults to ``None`` (sqlglot generic), which is
            valid in sqlglot 30.8.0.  ``'ansi'`` is **not** used because it
            is not a supported dialect name in that release.
        _tables:
            Accumulated table definitions, reset per
            :meth:`parse_statements` call.
        _views:
            Accumulated view definitions, reset per
            :meth:`parse_statements` call.
    """

    def __init__(self, dialect: str | None = None) -> None:
        """Store dialect; does not call sqlglot yet.

        Args:
            dialect: Optional sqlglot dialect string.  ``None`` means the
                sqlglot generic dialect, which is compatible with
                sqlglot 30.8.0.
        """
        self.dialect = dialect
        self._tables: dict[str, TableDef] = {}
        self._views: dict[str, ViewDef] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def parse_file(self, path: str | Path) -> SchemaGraph:
        """Read *path* as UTF-8 text and delegate to :meth:`parse_statements`.

        Args:
            path: Filesystem path to a ``.sql`` schema file.

        Returns:
            A populated :class:`~sql_lineage.models.SchemaGraph` (no lineage
            edges yet — those are added by the resolver).

        Raises:
            SchemaParseError: If the file cannot be parsed or contains
                duplicate object names.
        """
        sql = Path(path).read_text(encoding="utf-8")
        return self.parse_statements(sql)

    def parse_statements(self, sql: str) -> SchemaGraph:
        """Parse *sql* and return a fresh :class:`~sql_lineage.models.SchemaGraph`.

        Calls :func:`sqlglot.parse` with ``dialect=self.dialect``.  Iterates
        over the returned AST nodes and dispatches each :class:`~sqlglot.exp.Create`
        to :meth:`_parse_create_table` or :meth:`_parse_create_view`.
        Non-``Create`` nodes and ``None`` nodes are silently skipped.

        Args:
            sql: Raw SQL DDL string.

        Returns:
            A :class:`~sql_lineage.models.SchemaGraph` with ``tables`` and
            ``views`` populated and an empty ``edges`` list.

        Raises:
            SchemaParseError: On sqlglot parse errors, or when duplicate
                table / view names are encountered.
        """
        self._tables = {}
        self._views = {}

        try:
            statements = sqlglot.parse(sql, dialect=self.dialect)
        except Exception as exc:
            raise SchemaParseError(
                "Failed to parse SQL with sqlglot", detail=str(exc)
            ) from exc

        for node in statements:
            if node is None:
                continue
            if not isinstance(node, exp.Create):
                continue

            kind = str(node.args.get("kind", "")).upper()

            if kind == "TABLE":
                try:
                    table_def = self._parse_create_table(node)
                except SchemaParseError:
                    raise
                except Exception as exc:
                    raise SchemaParseError(
                        "Error processing CREATE TABLE statement", detail=str(exc)
                    ) from exc
                name = table_def.name
                if name in self._tables:
                    raise SchemaParseError(f"Duplicate table name: {name!r}")
                self._tables[name] = table_def

            elif kind == "VIEW":
                try:
                    view_def = self._parse_create_view(node)
                except SchemaParseError:
                    raise
                except Exception as exc:
                    raise SchemaParseError(
                        "Error processing CREATE VIEW statement", detail=str(exc)
                    ) from exc
                name = view_def.name
                if name in self._views:
                    raise SchemaParseError(f"Duplicate view name: {name!r}")
                self._views[name] = view_def

        return SchemaGraph(
            tables=dict(self._tables),
            views=dict(self._views),
            edges=[],
        )

    # ------------------------------------------------------------------
    # Internal dispatchers
    # ------------------------------------------------------------------

    def _parse_create_table(self, node: exp.Create) -> TableDef:
        """Extract a :class:`~sql_lineage.models.TableDef` from a CREATE TABLE node.

        Calls :meth:`_extract_columns` and :meth:`_extract_constraints`, then
        fills in the ``from_table`` field of any returned
        :class:`~sql_lineage.models.ForeignKeyDef` stubs.

        Args:
            node: A :class:`~sqlglot.exp.Create` AST node whose *kind* is
                ``'TABLE'``.

        Returns:
            A fully-populated :class:`~sql_lineage.models.TableDef`.

        Raises:
            SchemaParseError: If the table name cannot be determined.
        """
        table = node.find(exp.Table)
        if table is None or not table.name:
            raise SchemaParseError(
                "CREATE TABLE statement is missing a table name"
            )
        name = normalize_name(table.name)

        columns = self._extract_columns(node)
        primary_keys, fk_stubs = self._extract_constraints(node)

        # _extract_constraints does not know the owning table name yet; fill in.
        foreign_keys = tuple(
            ForeignKeyDef(
                from_table=name,
                from_col=fk.from_col,
                to_table=fk.to_table,
                to_col=fk.to_col,
            )
            for fk in fk_stubs
        )

        return TableDef(
            name=name,
            columns=columns,
            primary_keys=primary_keys,
            foreign_keys=foreign_keys,
        )

    def _parse_create_view(self, node: exp.Create) -> ViewDef:
        """Extract a :class:`~sql_lineage.models.ViewDef` from a CREATE VIEW node.

        Finds the SELECT expression, extracts output columns and table
        dependencies, and stores the full query text.

        Args:
            node: A :class:`~sqlglot.exp.Create` AST node whose *kind* is
                ``'VIEW'``.

        Returns:
            A fully-populated :class:`~sql_lineage.models.ViewDef`.

        Raises:
            SchemaParseError: If the view name or SELECT expression is missing.
        """
        table = node.find(exp.Table)
        if table is None or not table.name:
            raise SchemaParseError(
                "CREATE VIEW statement is missing a view name"
            )
        name = normalize_name(table.name)

        select = node.find(exp.Select)
        if select is None:
            raise SchemaParseError(
                f"CREATE VIEW {name!r} is missing a SELECT expression"
            )

        output_columns = self._extract_view_output_columns(select)
        dependencies = self._extract_dependencies(select)
        query = node.sql(dialect=self.dialect)

        return ViewDef(
            name=name,
            query=query,
            output_columns=output_columns,
            dependencies=dependencies,
        )

    # ------------------------------------------------------------------
    # Column / constraint helpers
    # ------------------------------------------------------------------

    def _extract_columns(self, node: exp.Create) -> tuple[str, ...]:
        """Return an ordered tuple of normalised column names for a CREATE TABLE.

        Iterates :class:`~sqlglot.exp.ColumnDef` nodes found anywhere inside
        *node*.  Returns an empty tuple for tables with no column definitions
        (e.g. ``CREATE TABLE … AS SELECT …``).

        Args:
            node: A :class:`~sqlglot.exp.Create` AST node.

        Returns:
            Tuple of normalised column name strings, in declaration order.
        """
        columns: list[str] = []
        for col_def in node.find_all(exp.ColumnDef):
            col_name = normalize_name(col_def.name)
            if col_name:
                columns.append(col_name)
        return tuple(columns)

    def _extract_constraints(
        self, node: exp.Create
    ) -> tuple[frozenset[str], tuple[ForeignKeyDef, ...]]:
        """Return ``(primary_keys, foreign_keys)`` extracted from *node*.

        Detects:

        * Inline ``PRIMARY KEY`` per :class:`~sqlglot.exp.ColumnDef`
          (via :class:`~sqlglot.exp.PrimaryKeyColumnConstraint`).
        * Standalone ``PRIMARY KEY`` constraint (possibly composite).
        * Inline ``REFERENCES`` per :class:`~sqlglot.exp.ColumnDef`
          (via :class:`~sqlglot.exp.Reference`).
        * Standalone ``FOREIGN KEY`` constraints.

        All names are normalised.  The ``from_table`` field of every returned
        :class:`~sql_lineage.models.ForeignKeyDef` is set to ``""`` and must
        be filled in by the caller.

        Args:
            node: A :class:`~sqlglot.exp.Create` AST node.

        Returns:
            A tuple of ``(frozenset[str], tuple[ForeignKeyDef, ...])`` where
            the first element is the set of primary-key column names and the
            second is the list of foreign-key definitions.
        """
        primary_keys: set[str] = set()
        foreign_keys: list[ForeignKeyDef] = []

        # ---- Inline constraints declared on individual column defs ----
        for col_def in node.find_all(exp.ColumnDef):
            col_name = normalize_name(col_def.name)
            for constraint in col_def.args.get("constraints", []):
                kind = constraint.args.get("kind")

                if isinstance(kind, exp.PrimaryKeyColumnConstraint):
                    primary_keys.add(col_name)

                elif isinstance(kind, exp.Reference):
                    # Inline: col_name INT REFERENCES other_table(other_col)
                    ref_table = kind.find(exp.Table)
                    if ref_table is not None:
                        to_table = normalize_name(ref_table.name)
                        ref_exprs = kind.args.get("expressions") or []
                        to_col = (
                            normalize_name(ref_exprs[0].name)
                            if ref_exprs
                            else col_name
                        )
                        foreign_keys.append(
                            ForeignKeyDef(
                                from_table="",  # filled in by _parse_create_table
                                from_col=col_name,
                                to_table=to_table,
                                to_col=to_col,
                            )
                        )

        # ---- Standalone table-level constraints ----
        schema = node.this
        if isinstance(schema, exp.Schema):
            for expr in schema.expressions:
                if isinstance(expr, exp.PrimaryKey):
                    for col_expr in expr.expressions:
                        col_name = normalize_name(col_expr.name)
                        if col_name:
                            primary_keys.add(col_name)

                elif isinstance(expr, exp.ForeignKey):
                    # FOREIGN KEY (from_col, …) REFERENCES to_table(to_col, …)
                    fk_cols = expr.expressions or []
                    reference = expr.args.get("reference")
                    if reference is not None and fk_cols:
                        from_col = normalize_name(fk_cols[0].name)
                        ref_table = reference.find(exp.Table)
                        ref_exprs = reference.args.get("expressions") or []
                        if ref_table is not None:
                            to_table = normalize_name(ref_table.name)
                            to_col = (
                                normalize_name(ref_exprs[0].name)
                                if ref_exprs
                                else from_col
                            )
                            foreign_keys.append(
                                ForeignKeyDef(
                                    from_table="",
                                    from_col=from_col,
                                    to_table=to_table,
                                    to_col=to_col,
                                )
                            )

        return frozenset(primary_keys), tuple(foreign_keys)

    # ------------------------------------------------------------------
    # View helpers
    # ------------------------------------------------------------------

    def _extract_view_output_columns(self, select: exp.Select) -> tuple[str, ...]:
        """Map each SELECT projection to an output column name.

        Rules (in order):

        * :class:`~sqlglot.exp.Star` → ``'*'``
        * :class:`~sqlglot.exp.Alias` → normalise the alias string
        * :class:`~sqlglot.exp.Column` → normalise the column name
        * Other expressions → normalise the alias if one is present,
          otherwise fall back to ``repr(expr)``

        Args:
            select: The :class:`~sqlglot.exp.Select` node.

        Returns:
            Ordered tuple of output column names.
        """
        output_columns: list[str] = []
        for expr in select.expressions:
            if isinstance(expr, exp.Star):
                output_columns.append("*")
            elif isinstance(expr, exp.Alias):
                output_columns.append(normalize_name(expr.alias))
            elif isinstance(expr, exp.Column):
                output_columns.append(normalize_name(expr.name))
            else:
                alias = getattr(expr, "alias", "") or ""
                if alias:
                    output_columns.append(normalize_name(str(alias)))
                else:
                    output_columns.append(repr(expr))
        return tuple(output_columns)

    def _extract_dependencies(self, select: exp.Select) -> frozenset[str]:
        """Collect normalised names of tables/views referenced in FROM and JOIN clauses.

        Scans all :class:`~sqlglot.exp.From` and :class:`~sqlglot.exp.Join`
        nodes within *select* (including those inside CTE sub-selects) and
        collects the names of every :class:`~sqlglot.exp.Table` node found
        within them.  Names matching CTE aliases declared in the ``WITH``
        clause of *select* are excluded.

        Args:
            select: The :class:`~sqlglot.exp.Select` node of the view query.

        Returns:
            Frozenset of normalised table/view names the view depends on.
        """
        # Collect CTE aliases so we can exclude them from the dependency set.
        cte_aliases: set[str] = set()
        with_clause = select.args.get("with")
        if with_clause is not None:
            for cte in with_clause.expressions:
                if isinstance(cte, exp.CTE) and cte.alias:
                    cte_aliases.add(normalize_name(cte.alias))

        dependencies: set[str] = set()

        # Walk all FROM clauses reachable from this SELECT (incl. inside CTEs).
        for from_node in select.find_all(exp.From):
            for tbl in from_node.find_all(exp.Table):
                name = normalize_name(tbl.name)
                if name and name not in cte_aliases:
                    dependencies.add(name)

        # Walk all JOIN clauses reachable from this SELECT.
        for join_node in select.find_all(exp.Join):
            for tbl in join_node.find_all(exp.Table):
                name = normalize_name(tbl.name)
                if name and name not in cte_aliases:
                    dependencies.add(name)

        return frozenset(dependencies)
