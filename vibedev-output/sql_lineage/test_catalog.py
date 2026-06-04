"""Tests for sql_lineage.catalog module."""

import pytest

from sql_lineage.exceptions import UnresolvedReferenceError
from sql_lineage.models import (
    ColumnRef,
    LineageEdge,
    SchemaGraph,
    TableDef,
    ViewDef,
)
from sql_lineage.catalog import SchemaCatalog


class TestSchemaCatalogInit:
    """Test SchemaCatalog initialization."""

    def test_init_empty_graph(self):
        """Test SchemaCatalog with empty graph."""
        graph = SchemaGraph()
        catalog = SchemaCatalog(graph)

        assert len(catalog.all_tables()) == 0
        assert len(catalog.all_views()) == 0
        assert len(catalog.all_edges()) == 0

    def test_init_with_tables_and_views(self):
        """Test SchemaCatalog initialization with tables and views."""
        users_table = TableDef(name="users", columns=("id", "name"))
        summary_view = ViewDef(
            name="summary",
            query="SELECT * FROM users",
            output_columns=("id", "name"),
            dependencies=frozenset({"users"}),
        )

        graph = SchemaGraph(
            tables={"users": users_table},
            views={"summary": summary_view},
        )
        catalog = SchemaCatalog(graph)

        assert len(catalog.all_tables()) == 1
        assert len(catalog.all_views()) == 1

    def test_init_builds_indexes(self):
        """Test that SchemaCatalog builds adjacency indexes on init."""
        source = ColumnRef(table="users", column="id")
        target = ColumnRef(table="summary", column="id")
        edge = LineageEdge(source=source, target=target)

        graph = SchemaGraph(edges=[edge])
        catalog = SchemaCatalog(graph)

        # Should have built indexes
        adj_list = catalog.adjacency_list()
        assert source in adj_list


class TestGetTable:
    """Test SchemaCatalog.get_table method."""

    def test_get_table_by_name(self):
        """Test getting a table by name."""
        users_table = TableDef(name="users", columns=("id", "name"))
        graph = SchemaGraph(tables={"users": users_table})
        catalog = SchemaCatalog(graph)

        table = catalog.get_table("users")
        assert table.name == "users"
        assert table.columns == ("id", "name")

    def test_get_table_case_insensitive(self):
        """Test that table lookup is case-insensitive."""
        users_table = TableDef(name="users", columns=("id", "name"))
        graph = SchemaGraph(tables={"users": users_table})
        catalog = SchemaCatalog(graph)

        table = catalog.get_table("USERS")
        assert table.name == "users"

    def test_get_table_with_quotes(self):
        """Test getting a table with quoted name."""
        users_table = TableDef(name="users", columns=("id", "name"))
        graph = SchemaGraph(tables={"users": users_table})
        catalog = SchemaCatalog(graph)

        table = catalog.get_table('"USERS"')
        assert table.name == "users"

    def test_get_table_not_found(self):
        """Test getting a non-existent table raises error."""
        graph = SchemaGraph()
        catalog = SchemaCatalog(graph)

        with pytest.raises(UnresolvedReferenceError, match="users"):
            catalog.get_table("users")

    def test_get_table_error_context(self):
        """Test that error includes context."""
        graph = SchemaGraph()
        catalog = SchemaCatalog(graph)

        with pytest.raises(UnresolvedReferenceError) as exc_info:
            catalog.get_table("missing")

        assert "table lookup" in str(exc_info.value)


class TestGetView:
    """Test SchemaCatalog.get_view method."""

    def test_get_view_by_name(self):
        """Test getting a view by name."""
        summary_view = ViewDef(
            name="summary",
            query="SELECT * FROM users",
            output_columns=("id", "name"),
            dependencies=frozenset({"users"}),
        )
        graph = SchemaGraph(views={"summary": summary_view})
        catalog = SchemaCatalog(graph)

        view = catalog.get_view("summary")
        assert view.name == "summary"

    def test_get_view_case_insensitive(self):
        """Test that view lookup is case-insensitive."""
        summary_view = ViewDef(
            name="summary",
            query="SELECT * FROM users",
            output_columns=("id", "name"),
            dependencies=frozenset({"users"}),
        )
        graph = SchemaGraph(views={"summary": summary_view})
        catalog = SchemaCatalog(graph)

        view = catalog.get_view("SUMMARY")
        assert view.name == "summary"

    def test_get_view_not_found(self):
        """Test getting a non-existent view raises error."""
        graph = SchemaGraph()
        catalog = SchemaCatalog(graph)

        with pytest.raises(UnresolvedReferenceError, match="summary"):
            catalog.get_view("summary")

    def test_get_view_error_context(self):
        """Test that error includes context."""
        graph = SchemaGraph()
        catalog = SchemaCatalog(graph)

        with pytest.raises(UnresolvedReferenceError) as exc_info:
            catalog.get_view("missing")

        assert "view lookup" in str(exc_info.value)


class TestAllTables:
    """Test SchemaCatalog.all_tables method."""

    def test_all_tables_empty(self):
        """Test all_tables with no tables."""
        graph = SchemaGraph()
        catalog = SchemaCatalog(graph)

        tables = catalog.all_tables()
        assert tables == []

    def test_all_tables_multiple(self):
        """Test all_tables with multiple tables."""
        users_table = TableDef(name="users", columns=("id",))
        products_table = TableDef(name="products", columns=("id",))

        graph = SchemaGraph(
            tables={"users": users_table, "products": products_table}
        )
        catalog = SchemaCatalog(graph)

        tables = catalog.all_tables()
        assert len(tables) == 2
        assert any(t.name == "users" for t in tables)
        assert any(t.name == "products" for t in tables)

    def test_all_tables_returns_list(self):
        """Test that all_tables returns a list."""
        users_table = TableDef(name="users", columns=("id",))
        graph = SchemaGraph(tables={"users": users_table})
        catalog = SchemaCatalog(graph)

        tables = catalog.all_tables()
        assert isinstance(tables, list)


class TestAllViews:
    """Test SchemaCatalog.all_views method."""

    def test_all_views_empty(self):
        """Test all_views with no views."""
        graph = SchemaGraph()
        catalog = SchemaCatalog(graph)

        views = catalog.all_views()
        assert views == []

    def test_all_views_multiple(self):
        """Test all_views with multiple views."""
        v1 = ViewDef(
            name="v1",
            query="SELECT 1",
            output_columns=("1",),
        )
        v2 = ViewDef(
            name="v2",
            query="SELECT 2",
            output_columns=("2",),
        )

        graph = SchemaGraph(views={"v1": v1, "v2": v2})
        catalog = SchemaCatalog(graph)

        views = catalog.all_views()
        assert len(views) == 2
        assert any(v.name == "v1" for v in views)
        assert any(v.name == "v2" for v in views)

    def test_all_views_returns_list(self):
        """Test that all_views returns a list."""
        v1 = ViewDef(
            name="v1",
            query="SELECT 1",
            output_columns=("1",),
        )
        graph = SchemaGraph(views={"v1": v1})
        catalog = SchemaCatalog(graph)

        views = catalog.all_views()
        assert isinstance(views, list)


class TestUpstreamColumns:
    """Test SchemaCatalog.upstream_columns method."""

    def test_upstream_columns_direct(self):
        """Test getting direct upstream columns."""
        source = ColumnRef(table="users", column="id")
        target = ColumnRef(table="summary", column="user_id")
        edge = LineageEdge(source=source, target=target)

        graph = SchemaGraph(edges=[edge])
        catalog = SchemaCatalog(graph)

        upstream = catalog.upstream_columns(target)
        assert source in upstream

    def test_upstream_columns_multiple(self):
        """Test getting multiple upstream columns."""
        source1 = ColumnRef(table="users", column="id")
        source2 = ColumnRef(table="users", column="name")
        target = ColumnRef(table="summary", column="user_info")

        edge1 = LineageEdge(source=source1, target=target)
        edge2 = LineageEdge(source=source2, target=target)

        graph = SchemaGraph(edges=[edge1, edge2])
        catalog = SchemaCatalog(graph)

        upstream = catalog.upstream_columns(target)
        assert source1 in upstream
        assert source2 in upstream

    def test_upstream_columns_none(self):
        """Test getting upstream columns when there are none."""
        target = ColumnRef(table="summary", column="id")
        graph = SchemaGraph()
        catalog = SchemaCatalog(graph)

        upstream = catalog.upstream_columns(target)
        assert upstream == set()

    def test_upstream_columns_returns_set(self):
        """Test that upstream_columns returns a set."""
        source = ColumnRef(table="users", column="id")
        target = ColumnRef(table="summary", column="id")
        edge = LineageEdge(source=source, target=target)

        graph = SchemaGraph(edges=[edge])
        catalog = SchemaCatalog(graph)

        upstream = catalog.upstream_columns(target)
        assert isinstance(upstream, set)


class TestDownstreamColumns:
    """Test SchemaCatalog.downstream_columns method."""

    def test_downstream_columns_direct(self):
        """Test getting direct downstream columns."""
        source = ColumnRef(table="users", column="id")
        target = ColumnRef(table="summary", column="user_id")
        edge = LineageEdge(source=source, target=target)

        graph = SchemaGraph(edges=[edge])
        catalog = SchemaCatalog(graph)

        downstream = catalog.downstream_columns(source)
        assert target in downstream

    def test_downstream_columns_multiple(self):
        """Test getting multiple downstream columns."""
        source = ColumnRef(table="users", column="id")
        target1 = ColumnRef(table="v1", column="id")
        target2 = ColumnRef(table="v2", column="user_id")

        edge1 = LineageEdge(source=source, target=target1)
        edge2 = LineageEdge(source=source, target=target2)

        graph = SchemaGraph(edges=[edge1, edge2])
        catalog = SchemaCatalog(graph)

        downstream = catalog.downstream_columns(source)
        assert target1 in downstream
        assert target2 in downstream

    def test_downstream_columns_none(self):
        """Test getting downstream columns when there are none."""
        source = ColumnRef(table="users", column="id")
        graph = SchemaGraph()
        catalog = SchemaCatalog(graph)

        downstream = catalog.downstream_columns(source)
        assert downstream == set()

    def test_downstream_columns_returns_set(self):
        """Test that downstream_columns returns a set."""
        source = ColumnRef(table="users", column="id")
        target = ColumnRef(table="summary", column="id")
        edge = LineageEdge(source=source, target=target)

        graph = SchemaGraph(edges=[edge])
        catalog = SchemaCatalog(graph)

        downstream = catalog.downstream_columns(source)
        assert isinstance(downstream, set)


class TestTransitiveUpstream:
    """Test SchemaCatalog.transitive_upstream method."""

    def test_transitive_upstream_single_level(self):
        """Test transitive upstream with single level."""
        source = ColumnRef(table="users", column="id")
        target = ColumnRef(table="summary", column="id")
        edge = LineageEdge(source=source, target=target)

        graph = SchemaGraph(edges=[edge])
        catalog = SchemaCatalog(graph)

        upstream = catalog.transitive_upstream(target)
        assert source in upstream

    def test_transitive_upstream_multiple_levels(self):
        """Test transitive upstream with multiple levels."""
        source = ColumnRef(table="users", column="id")
        mid = ColumnRef(table="v1", column="id")
        target = ColumnRef(table="v2", column="id")

        edge1 = LineageEdge(source=source, target=mid)
        edge2 = LineageEdge(source=mid, target=target)

        graph = SchemaGraph(edges=[edge1, edge2])
        catalog = SchemaCatalog(graph)

        upstream = catalog.transitive_upstream(target)
        assert source in upstream
        assert mid in upstream

    def test_transitive_upstream_no_self(self):
        """Test that transitive_upstream doesn't include the column itself."""
        source = ColumnRef(table="users", column="id")
        target = ColumnRef(table="summary", column="id")
        edge = LineageEdge(source=source, target=target)

        graph = SchemaGraph(edges=[edge])
        catalog = SchemaCatalog(graph)

        upstream = catalog.transitive_upstream(target)
        assert target not in upstream

    def test_transitive_upstream_none(self):
        """Test transitive upstream when there are none."""
        target = ColumnRef(table="summary", column="id")
        graph = SchemaGraph()
        catalog = SchemaCatalog(graph)

        upstream = catalog.transitive_upstream(target)
        assert upstream == set()

    def test_transitive_upstream_returns_set(self):
        """Test that transitive_upstream returns a set."""
        source = ColumnRef(table="users", column="id")
        target = ColumnRef(table="summary", column="id")
        edge = LineageEdge(source=source, target=target)

        graph = SchemaGraph(edges=[edge])
        catalog = SchemaCatalog(graph)

        upstream = catalog.transitive_upstream(target)
        assert isinstance(upstream, set)

    def test_transitive_upstream_complex_graph(self):
        """Test transitive upstream with complex graph."""
        u_id = ColumnRef(table="users", column="id")
        u_name = ColumnRef(table="users", column="name")

        v1_id = ColumnRef(table="v1", column="id")
        v1_name = ColumnRef(table="v1", column="name")

        v2_id = ColumnRef(table="v2", column="user_id")
        v2_name = ColumnRef(table="v2", column="full_name")

        edges = [
            LineageEdge(source=u_id, target=v1_id),
            LineageEdge(source=u_name, target=v1_name),
            LineageEdge(source=v1_id, target=v2_id),
            LineageEdge(source=v1_name, target=v2_name),
        ]

        graph = SchemaGraph(edges=edges)
        catalog = SchemaCatalog(graph)

        upstream = catalog.transitive_upstream(v2_id)
        assert u_id in upstream
        assert v1_id in upstream
        assert len(upstream) >= 2


class TestTransitiveDownstream:
    """Test SchemaCatalog.transitive_downstream method."""

    def test_transitive_downstream_single_level(self):
        """Test transitive downstream with single level."""
        source = ColumnRef(table="users", column="id")
        target = ColumnRef(table="summary", column="id")
        edge = LineageEdge(source=source, target=target)

        graph = SchemaGraph(edges=[edge])
        catalog = SchemaCatalog(graph)

        downstream = catalog.transitive_downstream(source)
        assert target in downstream

    def test_transitive_downstream_multiple_levels(self):
        """Test transitive downstream with multiple levels."""
        source = ColumnRef(table="users", column="id")
        mid = ColumnRef(table="v1", column="id")
        target = ColumnRef(table="v2", column="id")

        edge1 = LineageEdge(source=source, target=mid)
        edge2 = LineageEdge(source=mid, target=target)

        graph = SchemaGraph(edges=[edge1, edge2])
        catalog = SchemaCatalog(graph)

        downstream = catalog.transitive_downstream(source)
        assert mid in downstream
        assert target in downstream

    def test_transitive_downstream_no_self(self):
        """Test that transitive_downstream doesn't include the column itself."""
        source = ColumnRef(table="users", column="id")
        target = ColumnRef(table="summary", column="id")
        edge = LineageEdge(source=source, target=target)

        graph = SchemaGraph(edges=[edge])
        catalog = SchemaCatalog(graph)

        downstream = catalog.transitive_downstream(source)
        assert source not in downstream

    def test_transitive_downstream_none(self):
        """Test transitive downstream when there are none."""
        source = ColumnRef(table="users", column="id")
        graph = SchemaGraph()
        catalog = SchemaCatalog(graph)

        downstream = catalog.transitive_downstream(source)
        assert downstream == set()

    def test_transitive_downstream_returns_set(self):
        """Test that transitive_downstream returns a set."""
        source = ColumnRef(table="users", column="id")
        target = ColumnRef(table="summary", column="id")
        edge = LineageEdge(source=source, target=target)

        graph = SchemaGraph(edges=[edge])
        catalog = SchemaCatalog(graph)

        downstream = catalog.transitive_downstream(source)
        assert isinstance(downstream, set)


class TestAdjacencyList:
    """Test SchemaCatalog.adjacency_list method."""

    def test_adjacency_list_empty(self):
        """Test adjacency_list with no edges."""
        graph = SchemaGraph()
        catalog = SchemaCatalog(graph)

        adj = catalog.adjacency_list()
        assert isinstance(adj, dict)
        assert len(adj) == 0

    def test_adjacency_list_single_edge(self):
        """Test adjacency_list with single edge."""
        source = ColumnRef(table="users", column="id")
        target = ColumnRef(table="summary", column="id")
        edge = LineageEdge(source=source, target=target)

        graph = SchemaGraph(edges=[edge])
        catalog = SchemaCatalog(graph)

        adj = catalog.adjacency_list()
        assert source in adj
        assert target in adj[source]

    def test_adjacency_list_multiple_targets(self):
        """Test adjacency_list with multiple targets for one source."""
        source = ColumnRef(table="users", column="id")
        target1 = ColumnRef(table="v1", column="id")
        target2 = ColumnRef(table="v2", column="user_id")

        edge1 = LineageEdge(source=source, target=target1)
        edge2 = LineageEdge(source=source, target=target2)

        graph = SchemaGraph(edges=[edge1, edge2])
        catalog = SchemaCatalog(graph)

        adj = catalog.adjacency_list()
        assert source in adj
        assert len(adj[source]) == 2
        assert target1 in adj[source]
        assert target2 in adj[source]

    def test_adjacency_list_is_copy(self):
        """Test that adjacency_list returns a copy."""
        source = ColumnRef(table="users", column="id")
        target = ColumnRef(table="summary", column="id")
        edge = LineageEdge(source=source, target=target)

        graph = SchemaGraph(edges=[edge])
        catalog = SchemaCatalog(graph)

        adj1 = catalog.adjacency_list()
        adj2 = catalog.adjacency_list()

        # Should be different dict objects
        assert adj1 is not adj2


class TestAllEdges:
    """Test SchemaCatalog.all_edges method."""

    def test_all_edges_empty(self):
        """Test all_edges with no edges."""
        graph = SchemaGraph()
        catalog = SchemaCatalog(graph)

        edges = catalog.all_edges()
        assert edges == []

    def test_all_edges_single(self):
        """Test all_edges with single edge."""
        source = ColumnRef(table="users", column="id")
        target = ColumnRef(table="summary", column="id")
        edge = LineageEdge(source=source, target=target)

        graph = SchemaGraph(edges=[edge])
        catalog = SchemaCatalog(graph)

        edges = catalog.all_edges()
        assert len(edges) == 1
        assert edges[0] == edge

    def test_all_edges_multiple(self):
        """Test all_edges with multiple edges."""
        source = ColumnRef(table="users", column="id")
        target1 = ColumnRef(table="v1", column="id")
        target2 = ColumnRef(table="v2", column="id")

        edge1 = LineageEdge(source=source, target=target1)
        edge2 = LineageEdge(source=source, target=target2)

        graph = SchemaGraph(edges=[edge1, edge2])
        catalog = SchemaCatalog(graph)

        edges = catalog.all_edges()
        assert len(edges) == 2
        assert edge1 in edges
        assert edge2 in edges

    def test_all_edges_returns_list(self):
        """Test that all_edges returns a list."""
        source = ColumnRef(table="users", column="id")
        target = ColumnRef(table="summary", column="id")
        edge = LineageEdge(source=source, target=target)

        graph = SchemaGraph(edges=[edge])
        catalog = SchemaCatalog(graph)

        edges = catalog.all_edges()
        assert isinstance(edges, list)
