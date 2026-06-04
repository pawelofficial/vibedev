"""SchemaCatalog: read-only query interface over a resolved SchemaGraph.

Provides entity lookups (tables, views) and both direct and transitive
upstream/downstream column-lineage queries via BFS.  Intended as the
primary API consumed by a visualization layer.
"""

from __future__ import annotations

import re
from collections import deque

from sql_lineage.exceptions import UnresolvedReferenceError
from sql_lineage.models import ColumnRef, LineageEdge, SchemaGraph, TableDef, ViewDef

# ---------------------------------------------------------------------------
# Inline identifier normalisation (mirrors normalizer.normalize_name without
# creating a cross-layer import — normalizer is not in this module's depends_on)
# ---------------------------------------------------------------------------
_QUOTED = re.compile(
    r'^"(?P<ansi>[^"]*)"$'      # ANSI double-quotes
    r"|^`(?P<mysql>[^`]*)`$"    # MySQL back-ticks
    r"|^\[(?P<tsql>[^\]]*)\]$"  # T-SQL square brackets
)


def _normalize(name: str) -> str:
    """Strip SQL quoting characters and return a lowercased, stripped identifier."""
    if not name:
        return ""
    stripped = name.strip()
    m = _QUOTED.match(stripped)
    if m:
        inner = m.group("ansi") or m.group("mysql") or m.group("tsql") or ""
        return inner.lower().strip()
    return stripped.lower()


class SchemaCatalog:
    """Wraps a resolved :class:`SchemaGraph` and pre-builds forward/backward
    adjacency indexes for O(1) direct-neighbor lookups and efficient BFS
    traversals.

    Attributes:
        _graph:       The underlying resolved schema graph.
        _downstream:  source -> set of direct target columns.
        _upstream:    target -> set of direct source columns.
    """

    def __init__(self, graph: SchemaGraph) -> None:
        self._graph: SchemaGraph = graph
        self._downstream: dict[ColumnRef, set[ColumnRef]] = {}
        self._upstream: dict[ColumnRef, set[ColumnRef]] = {}
        self._build_indexes()

    # ------------------------------------------------------------------
    # Index construction
    # ------------------------------------------------------------------

    def _build_indexes(self) -> None:
        """Iterate ``graph.edges`` once and populate both adjacency dicts."""
        for edge in self._graph.edges:
            self._downstream.setdefault(edge.source, set()).add(edge.target)
            self._upstream.setdefault(edge.target, set()).add(edge.source)

    # ------------------------------------------------------------------
    # Entity lookups
    # ------------------------------------------------------------------

    def get_table(self, name: str) -> TableDef:
        """Return the :class:`TableDef` for *name*.

        Args:
            name: Raw (possibly quoted) table name.

        Returns:
            The matching :class:`TableDef`.

        Raises:
            UnresolvedReferenceError: If no table with the normalised name exists.
        """
        key = _normalize(name)
        try:
            return self._graph.tables[key]
        except KeyError:
            raise UnresolvedReferenceError(key, context="table lookup") from None

    def get_view(self, name: str) -> ViewDef:
        """Return the :class:`ViewDef` for *name*.

        Args:
            name: Raw (possibly quoted) view name.

        Returns:
            The matching :class:`ViewDef`.

        Raises:
            UnresolvedReferenceError: If no view with the normalised name exists.
        """
        key = _normalize(name)
        try:
            return self._graph.views[key]
        except KeyError:
            raise UnresolvedReferenceError(key, context="view lookup") from None

    def all_tables(self) -> list[TableDef]:
        """Return all tables in the schema as a list."""
        return list(self._graph.tables.values())

    def all_views(self) -> list[ViewDef]:
        """Return all views in the schema as a list."""
        return list(self._graph.views.values())

    # ------------------------------------------------------------------
    # Direct lineage
    # ------------------------------------------------------------------

    def upstream_columns(self, col: ColumnRef) -> set[ColumnRef]:
        """Return the direct upstream columns for *col*.

        Args:
            col: The column whose sources are requested.

        Returns:
            A set of :class:`ColumnRef` objects that feed directly into *col*,
            or an empty set when *col* has no known sources.
        """
        return set(self._upstream.get(col, set()))

    def downstream_columns(self, col: ColumnRef) -> set[ColumnRef]:
        """Return the direct downstream columns for *col*.

        Args:
            col: The column whose targets are requested.

        Returns:
            A set of :class:`ColumnRef` objects that *col* feeds directly into,
            or an empty set when *col* has no known targets.
        """
        return set(self._downstream.get(col, set()))

    # ------------------------------------------------------------------
    # Transitive lineage (BFS)
    # ------------------------------------------------------------------

    def transitive_upstream(self, col: ColumnRef) -> set[ColumnRef]:
        """Return **all** transitive upstream columns reachable from *col*.

        Performs a breadth-first search following :meth:`upstream_columns`.
        *col* itself is **not** included in the result.  A *visited* set
        guards against cycles.

        Args:
            col: The starting column.

        Returns:
            All ancestors of *col* in the lineage graph.
        """
        result: set[ColumnRef] = set()
        queue: deque[ColumnRef] = deque(self.upstream_columns(col))
        visited: set[ColumnRef] = {col}

        while queue:
            current = queue.popleft()
            if current in visited:
                continue
            visited.add(current)
            result.add(current)
            queue.extend(self.upstream_columns(current))

        return result

    def transitive_downstream(self, col: ColumnRef) -> set[ColumnRef]:
        """Return **all** transitive downstream columns reachable from *col*.

        Performs a breadth-first search following :meth:`downstream_columns`.
        *col* itself is **not** included in the result.  A *visited* set
        guards against cycles.

        Args:
            col: The starting column.

        Returns:
            All descendants of *col* in the lineage graph.
        """
        result: set[ColumnRef] = set()
        queue: deque[ColumnRef] = deque(self.downstream_columns(col))
        visited: set[ColumnRef] = {col}

        while queue:
            current = queue.popleft()
            if current in visited:
                continue
            visited.add(current)
            result.add(current)
            queue.extend(self.downstream_columns(current))

        return result

    # ------------------------------------------------------------------
    # Graph accessors
    # ------------------------------------------------------------------

    def adjacency_list(self) -> dict[ColumnRef, set[ColumnRef]]:
        """Return a shallow copy of the downstream adjacency dict.

        The returned mapping is safe to mutate without affecting the
        catalog's internal state (though the :class:`ColumnRef` sets
        within it are shared references).

        Returns:
            ``{source: set_of_targets, ...}``
        """
        return dict(self._downstream)

    def all_edges(self) -> list[LineageEdge]:
        """Return all lineage edges in the graph.

        Returns:
            A list of every :class:`LineageEdge` in insertion order.
        """
        return list(self._graph.edges)
