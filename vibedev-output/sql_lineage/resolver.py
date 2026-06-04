"""Column-level lineage resolver for a populated SchemaGraph.

Views are processed in topological order so that lineage from upstream views
is available when resolving downstream ones.  All name normalisation goes
through :func:`~sql_lineage.normalizer.normalize_name`; no dialect string is
ever hard-coded (use ``self.dialect``, which defaults to ``None``).
"""

from __future__ import annotations

from collections import deque

import sqlglot
from sqlglot import exp

from sql_lineage.exceptions import CircularDependencyError
from sql_lineage.models import ColumnRef, LineageEdge, SchemaGraph, ViewDef
from sql_lineage.normalizer import normalize_name


class LineageResolver:
    """Resolves column-level lineage edges across all views in a SchemaGraph.

    Uses sqlglot to re-parse each view's stored query text to get a fresh AST
    for column-source analysis.  The dialect must match the one used during
    parsing.

    Attributes:
        dialect: Dialect passed to sqlglot.  Defaults to ``None`` (sqlglot
            generic).  Never set to the unsupported string ``'ansi'``.
    """

    def __init__(self, dialect: str | None = None) -> None:
        self.dialect = dialect

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def resolve(self, graph: SchemaGraph) -> None:
        """Resolve column-level lineage for every view in *graph*.

        Topologically sorts views by their view-level dependencies, then calls
        :meth:`_resolve_view` for each in order.  Mutates ``graph.edges``
        in-place; returns ``None``.

        Raises:
            CircularDependencyError: If a cycle is detected in the view
                dependency sub-graph.
        """
        sorted_views = self._topo_sort_views(graph)
        for view_name in sorted_views:
            self._resolve_view(graph.views[view_name], graph)

    # ------------------------------------------------------------------
    # Topological sort
    # ------------------------------------------------------------------

    def _topo_sort_views(self, graph: SchemaGraph) -> list[str]:
        """Return view names ordered by dependency (leaf-dependencies first).

        Uses Kahn's algorithm over the view-to-view dependency sub-graph.
        Tables are treated as roots and do not participate in the sort.

        Raises:
            CircularDependencyError: If any cycle is found.
        """
        view_names: set[str] = set(graph.views.keys())

        # in_degree[v] = number of *view* dependencies of v
        in_degree: dict[str, int] = {v: 0 for v in view_names}
        # dependents[u] = views that depend on u
        dependents: dict[str, list[str]] = {v: [] for v in view_names}

        for view_name, view in graph.views.items():
            for dep in view.dependencies:
                dep_norm = normalize_name(dep)
                if dep_norm in view_names:
                    in_degree[view_name] += 1
                    dependents[dep_norm].append(view_name)

        # Seed with views that have no view-level dependency
        queue: deque[str] = deque(v for v in view_names if in_degree[v] == 0)
        sorted_views: list[str] = []

        while queue:
            current = queue.popleft()
            sorted_views.append(current)
            for downstream in dependents[current]:
                in_degree[downstream] -= 1
                if in_degree[downstream] == 0:
                    queue.append(downstream)

        if len(sorted_views) != len(view_names):
            remaining = [v for v in view_names if v not in set(sorted_views)]
            raise CircularDependencyError(remaining)

        return sorted_views

    # ------------------------------------------------------------------
    # Per-view resolution
    # ------------------------------------------------------------------

    def _resolve_view(self, view: ViewDef, graph: SchemaGraph) -> list[LineageEdge]:
        """Resolve column lineage for a single view.

        Re-parses ``view.query`` via ``sqlglot.parse_one(view.query,
        dialect=self.dialect)``, locates the SELECT node, builds an alias map,
        then walks each output expression to produce :class:`LineageEdge`
        objects appended to ``graph.edges``.

        Wildcard (``*``) columns are expanded to all columns of the referenced
        table/view when the source is unambiguous; otherwise a single edge with
        ``column='*'`` is stored.

        Returns:
            The list of edges added for this view (same objects in
            ``graph.edges``).
        """
        try:
            parsed = sqlglot.parse_one(view.query, dialect=self.dialect)
        except Exception:
            return []

        if parsed is None:
            return []

        # Locate the SELECT node (may be wrapped in a CREATE VIEW expression)
        select_node: exp.Select | None
        if isinstance(parsed, exp.Select):
            select_node = parsed
        else:
            select_node = parsed.find(exp.Select)

        if select_node is None:
            return []

        alias_map = self._build_alias_map(select_node, graph)
        edges: list[LineageEdge] = []

        for expr in select_node.expressions:
            output_col = self._output_column_name(expr)

            if output_col == '*':
                self._handle_wildcard(expr, view, alias_map, graph, edges)
                continue

            # Unwrap alias to reach the underlying expression
            inner = expr.this if isinstance(expr, exp.Alias) else expr
            source_ref = self._node_to_ref(inner, alias_map, graph)
            if source_ref is None:
                # Unresolvable / expression column — skip silently
                continue

            target_ref = ColumnRef(table=view.name, column=output_col)
            edge = LineageEdge(source=source_ref, target=target_ref)
            edges.append(edge)
            graph.edges.append(edge)

        return edges

    # ------------------------------------------------------------------
    # Wildcard helper
    # ------------------------------------------------------------------

    def _handle_wildcard(
        self,
        expr: exp.Expression,
        view: ViewDef,
        alias_map: dict[str, str],
        graph: SchemaGraph,
        edges: list[LineageEdge],
    ) -> None:
        """Expand (or store) a wildcard ``*`` expression."""
        inner = expr.this if isinstance(expr, exp.Alias) else expr

        # Detect qualified star: t.*  → exp.Column(this=exp.Star(), table='t')
        table_qualifier: str | None = None
        if isinstance(inner, exp.Column) and isinstance(inner.this, exp.Star):
            table_qualifier = normalize_name(inner.table) if inner.table else None

        if table_qualifier:
            canonical = alias_map.get(table_qualifier)
            if canonical:
                for col in self._get_columns_for(canonical, graph):
                    self._add_edge(canonical, col, view.name, col, edges, graph)
            else:
                self._add_edge('', '*', view.name, '*', edges, graph)
        elif len(alias_map) == 1:
            # Unambiguous single source — expand fully
            canonical = next(iter(alias_map.values()))
            for col in self._get_columns_for(canonical, graph):
                self._add_edge(canonical, col, view.name, col, edges, graph)
        else:
            # Ambiguous or no sources — store placeholder edge
            self._add_edge('', '*', view.name, '*', edges, graph)

    def _add_edge(
        self,
        src_table: str,
        src_col: str,
        tgt_table: str,
        tgt_col: str,
        edges: list[LineageEdge],
        graph: SchemaGraph,
    ) -> None:
        """Construct a :class:`LineageEdge` and append it to both lists."""
        edge = LineageEdge(
            source=ColumnRef(table=src_table, column=src_col),
            target=ColumnRef(table=tgt_table, column=tgt_col),
        )
        edges.append(edge)
        graph.edges.append(edge)

    # ------------------------------------------------------------------
    # Alias map
    # ------------------------------------------------------------------

    def _build_alias_map(
        self, select: exp.Select, graph: SchemaGraph
    ) -> dict[str, str]:
        """Build alias → canonical-name map from FROM and JOIN clauses.

        For each table reference, maps the alias (when present) **and** the
        bare table name to the canonical name in *graph*.  Normalizes all
        identifiers.
        """
        alias_map: dict[str, str] = {}

        from_clause = select.args.get('from')
        joins: list[exp.Join] = select.args.get('joins') or []

        sources: list[exp.Expression] = []
        if from_clause is not None:
            # exp.From.this is the table / subquery expression
            sources.append(from_clause.this)
        for join in joins:
            sources.append(join.this)

        for src in sources:
            self._register_source(src, alias_map, graph)

        return alias_map

    def _register_source(
        self,
        src: exp.Expression,
        alias_map: dict[str, str],
        graph: SchemaGraph,
    ) -> None:
        """Add a single FROM/JOIN table reference to *alias_map*."""
        if isinstance(src, exp.Table):
            tbl_name = normalize_name(src.name)
            tbl_alias = normalize_name(src.alias) if src.alias else None
            canonical = self._canonical_name(tbl_name, graph)
            if canonical is None:
                return
            alias_map[tbl_name] = canonical
            if tbl_alias and tbl_alias != tbl_name:
                alias_map[tbl_alias] = canonical

        elif isinstance(src, exp.Alias):
            # Some dialects wrap table+alias in exp.Alias
            alias = normalize_name(src.alias) if src.alias else None
            inner = src.this
            if isinstance(inner, exp.Table):
                tbl_name = normalize_name(inner.name)
                canonical = self._canonical_name(tbl_name, graph)
                if canonical:
                    alias_map[tbl_name] = canonical
                    if alias and alias != tbl_name:
                        alias_map[alias] = canonical

        elif isinstance(src, exp.Subquery):
            # Subquery: record alias as its own key (cannot trace further here)
            alias = normalize_name(src.alias) if src.alias else None
            if alias:
                alias_map[alias] = alias

    # ------------------------------------------------------------------
    # Expression → ColumnRef
    # ------------------------------------------------------------------

    def _node_to_ref(
        self,
        node: exp.Expression,
        alias_map: dict[str, str],
        graph: SchemaGraph,
    ) -> ColumnRef | None:
        """Resolve an AST expression node to a :class:`ColumnRef`.

        Handles :class:`sqlglot.exp.Column` nodes only.  When a table
        qualifier is present it is looked up in *alias_map* (with a fallback
        to a direct graph lookup).  When no qualifier is present the method
        attempts to infer the source from a single-entry alias_map, or by
        searching which table owns the column name.

        Returns ``None`` when the reference cannot be resolved; the caller
        skips the column rather than raising an exception.
        """
        if not isinstance(node, exp.Column):
            return None

        col_name = normalize_name(node.name) if node.name else None
        if not col_name:
            return None

        table_qualifier = node.table
        if table_qualifier:
            tbl_norm = normalize_name(str(table_qualifier))
            canonical = alias_map.get(tbl_norm) or self._canonical_name(tbl_norm, graph)
            if canonical is None:
                return None
            return ColumnRef(table=canonical, column=col_name)

        # No qualifier — infer source
        if len(alias_map) == 1:
            canonical = next(iter(alias_map.values()))
            return ColumnRef(table=canonical, column=col_name)

        # Search by column ownership (de-duplicated values)
        seen: set[str] = set()
        candidates: list[str] = []
        for canonical in alias_map.values():
            if canonical in seen:
                continue
            seen.add(canonical)
            if col_name in self._get_columns_for(canonical, graph):
                candidates.append(canonical)

        if len(candidates) == 1:
            return ColumnRef(table=candidates[0], column=col_name)

        # Ambiguous or not found — skip
        return None

    # ------------------------------------------------------------------
    # Output column name
    # ------------------------------------------------------------------

    def _output_column_name(self, expr: exp.Expression) -> str:
        """Return the output column name for a SELECT-list expression.

        Priority:
        1. Explicit alias (``expr AS alias``).
        2. Column name for plain :class:`~sqlglot.exp.Column` nodes.
        3. ``'*'`` for :class:`~sqlglot.exp.Star` nodes (bare or table-qualified).

        All results are normalized via :func:`~sql_lineage.normalizer.normalize_name`.
        """
        if isinstance(expr, exp.Alias):
            alias = expr.alias
            return normalize_name(alias) if alias else '*'

        if isinstance(expr, exp.Column):
            # t.* → Column(this=Star())
            if isinstance(expr.this, exp.Star):
                return '*'
            return normalize_name(expr.name) if expr.name else '*'

        if isinstance(expr, exp.Star):
            return '*'

        return '*'

    # ------------------------------------------------------------------
    # Graph lookup utilities
    # ------------------------------------------------------------------

    def _get_columns_for(self, name: str, graph: SchemaGraph) -> list[str]:
        """Return the column list for a table or view by canonical name."""
        if name in graph.tables:
            return list(graph.tables[name].columns)
        if name in graph.views:
            return list(graph.views[name].output_columns)
        return []

    def _canonical_name(self, name: str, graph: SchemaGraph) -> str | None:
        """Return *name* if it exists in tables or views, else ``None``."""
        if name in graph.tables:
            return name
        if name in graph.views:
            return name
        return None
