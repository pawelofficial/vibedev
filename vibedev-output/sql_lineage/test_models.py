"""Tests for sql_lineage.models module."""

import pytest

from sql_lineage.models import (
    ColumnRef,
    ForeignKeyDef,
    LineageEdge,
    SchemaGraph,
    TableDef,
    ViewDef,
)


class TestColumnRef:
    """Test the ColumnRef frozen dataclass."""

    def test_creation(self):
        """Test basic ColumnRef creation."""
        col = ColumnRef(table="users", column="id")
        assert col.table == "users"
        assert col.column == "id"

    def test_hashable(self):
        """Test that ColumnRef is hashable and can be used in sets."""
        col1 = ColumnRef(table="users", column="id")
        col2 = ColumnRef(table="users", column="id")
        col3 = ColumnRef(table="users", column="name")

        # Same columns should have same hash
        assert hash(col1) == hash(col2)
        assert col1 == col2

        # Different columns should be different
        assert col1 != col3

    def test_in_set(self):
        """Test ColumnRef can be used in sets."""
        col1 = ColumnRef(table="users", column="id")
        col2 = ColumnRef(table="users", column="name")
        col3 = ColumnRef(table="users", column="id")

        s = {col1, col2, col3}
        assert len(s) == 2  # col1 and col3 are duplicates

    def test_as_dict_key(self):
        """Test ColumnRef can be used as dict key."""
        col1 = ColumnRef(table="users", column="id")
        col2 = ColumnRef(table="users", column="name")

        d = {col1: "primary_key", col2: "text"}
        assert d[col1] == "primary_key"
        assert d[col2] == "text"

    def test_frozen(self):
        """Test that ColumnRef is immutable."""
        col = ColumnRef(table="users", column="id")
        with pytest.raises(AttributeError):
            col.table = "other_table"
        with pytest.raises(AttributeError):
            col.column = "other_column"

    def test_equality(self):
        """Test ColumnRef equality."""
        col1 = ColumnRef(table="users", column="id")
        col2 = ColumnRef(table="users", column="id")
        col3 = ColumnRef(table="users", column="name")
        col4 = ColumnRef(table="products", column="id")

        assert col1 == col2
        assert col1 != col3
        assert col1 != col4

    def test_repr(self):
        """Test ColumnRef string representation."""
        col = ColumnRef(table="users", column="id")
        repr_str = repr(col)
        assert "ColumnRef" in repr_str
        assert "users" in repr_str
        assert "id" in repr_str


class TestForeignKeyDef:
    """Test the ForeignKeyDef frozen dataclass."""

    def test_creation(self):
        """Test basic ForeignKeyDef creation."""
        fk = ForeignKeyDef(
            from_table="orders",
            from_col="user_id",
            to_table="users",
            to_col="id",
        )
        assert fk.from_table == "orders"
        assert fk.from_col == "user_id"
        assert fk.to_table == "users"
        assert fk.to_col == "id"

    def test_hashable(self):
        """Test that ForeignKeyDef is hashable."""
        fk1 = ForeignKeyDef(
            from_table="orders",
            from_col="user_id",
            to_table="users",
            to_col="id",
        )
        fk2 = ForeignKeyDef(
            from_table="orders",
            from_col="user_id",
            to_table="users",
            to_col="id",
        )
        assert hash(fk1) == hash(fk2)
        assert fk1 == fk2

    def test_frozen(self):
        """Test that ForeignKeyDef is immutable."""
        fk = ForeignKeyDef(
            from_table="orders",
            from_col="user_id",
            to_table="users",
            to_col="id",
        )
        with pytest.raises(AttributeError):
            fk.from_table = "other_table"


class TestTableDef:
    """Test the TableDef frozen dataclass."""

    def test_creation_minimal(self):
        """Test TableDef creation with minimal fields."""
        table = TableDef(
            name="users",
            columns=("id", "name", "email"),
        )
        assert table.name == "users"
        assert table.columns == ("id", "name", "email")
        assert table.primary_keys == frozenset()
        assert table.foreign_keys == ()

    def test_creation_with_pk(self):
        """Test TableDef creation with primary key."""
        table = TableDef(
            name="users",
            columns=("id", "name"),
            primary_keys=frozenset({"id"}),
        )
        assert table.primary_keys == frozenset({"id"})

    def test_creation_with_fks(self):
        """Test TableDef creation with foreign keys."""
        fk = ForeignKeyDef(
            from_table="orders",
            from_col="user_id",
            to_table="users",
            to_col="id",
        )
        table = TableDef(
            name="orders",
            columns=("id", "user_id", "amount"),
            foreign_keys=(fk,),
        )
        assert len(table.foreign_keys) == 1
        assert table.foreign_keys[0] == fk

    def test_frozen(self):
        """Test that TableDef is immutable."""
        table = TableDef(name="users", columns=("id",))
        with pytest.raises(AttributeError):
            table.name = "other"

    def test_empty_columns(self):
        """Test TableDef with no columns."""
        table = TableDef(name="empty_table", columns=())
        assert table.columns == ()


class TestViewDef:
    """Test the ViewDef frozen dataclass."""

    def test_creation_minimal(self):
        """Test ViewDef creation with minimal fields."""
        view = ViewDef(
            name="user_summary",
            query="SELECT id, name FROM users",
            output_columns=("id", "name"),
        )
        assert view.name == "user_summary"
        assert view.query == "SELECT id, name FROM users"
        assert view.output_columns == ("id", "name")
        assert view.dependencies == frozenset()

    def test_creation_with_dependencies(self):
        """Test ViewDef creation with dependencies."""
        view = ViewDef(
            name="user_summary",
            query="SELECT u.id, o.count FROM users u JOIN orders o ON u.id = o.user_id",
            output_columns=("id", "count"),
            dependencies=frozenset({"users", "orders"}),
        )
        assert view.dependencies == frozenset({"users", "orders"})

    def test_wildcard_columns(self):
        """Test ViewDef with wildcard column."""
        view = ViewDef(
            name="all_users",
            query="SELECT * FROM users",
            output_columns=("*",),
        )
        assert view.output_columns == ("*",)

    def test_frozen(self):
        """Test that ViewDef is immutable."""
        view = ViewDef(
            name="test_view",
            query="SELECT * FROM users",
            output_columns=("*",),
        )
        with pytest.raises(AttributeError):
            view.name = "other_name"


class TestLineageEdge:
    """Test the LineageEdge frozen dataclass."""

    def test_creation(self):
        """Test basic LineageEdge creation."""
        source = ColumnRef(table="users", column="id")
        target = ColumnRef(table="user_summary", column="user_id")
        edge = LineageEdge(source=source, target=target)

        assert edge.source == source
        assert edge.target == target

    def test_hashable(self):
        """Test that LineageEdge is hashable."""
        source = ColumnRef(table="users", column="id")
        target = ColumnRef(table="user_summary", column="user_id")

        edge1 = LineageEdge(source=source, target=target)
        edge2 = LineageEdge(source=source, target=target)

        assert hash(edge1) == hash(edge2)
        assert edge1 == edge2

    def test_in_set(self):
        """Test LineageEdge can be used in sets."""
        source = ColumnRef(table="users", column="id")
        target1 = ColumnRef(table="view1", column="id")
        target2 = ColumnRef(table="view2", column="id")

        edge1 = LineageEdge(source=source, target=target1)
        edge2 = LineageEdge(source=source, target=target2)
        edge3 = LineageEdge(source=source, target=target1)

        s = {edge1, edge2, edge3}
        assert len(s) == 2  # edge1 and edge3 are duplicates

    def test_frozen(self):
        """Test that LineageEdge is immutable."""
        source = ColumnRef(table="users", column="id")
        target = ColumnRef(table="view1", column="id")
        edge = LineageEdge(source=source, target=target)

        with pytest.raises(AttributeError):
            edge.source = ColumnRef(table="other", column="col")


class TestSchemaGraph:
    """Test the SchemaGraph mutable dataclass."""

    def test_creation_empty(self):
        """Test SchemaGraph creation with default empty state."""
        graph = SchemaGraph()
        assert graph.tables == {}
        assert graph.views == {}
        assert graph.edges == []

    def test_creation_with_tables(self):
        """Test SchemaGraph creation with tables."""
        table = TableDef(name="users", columns=("id", "name"))
        graph = SchemaGraph(tables={"users": table})

        assert "users" in graph.tables
        assert graph.tables["users"] == table

    def test_creation_with_views(self):
        """Test SchemaGraph creation with views."""
        view = ViewDef(
            name="user_summary",
            query="SELECT * FROM users",
            output_columns=("*",),
            dependencies=frozenset({"users"}),
        )
        graph = SchemaGraph(views={"user_summary": view})

        assert "user_summary" in graph.views
        assert graph.views["user_summary"] == view

    def test_creation_with_edges(self):
        """Test SchemaGraph creation with lineage edges."""
        source = ColumnRef(table="users", column="id")
        target = ColumnRef(table="user_summary", column="id")
        edge = LineageEdge(source=source, target=target)

        graph = SchemaGraph(edges=[edge])
        assert len(graph.edges) == 1
        assert graph.edges[0] == edge

    def test_mutable(self):
        """Test that SchemaGraph can be mutated."""
        graph = SchemaGraph()

        table = TableDef(name="users", columns=("id", "name"))
        graph.tables["users"] = table

        assert "users" in graph.tables

        edge = LineageEdge(
            source=ColumnRef(table="users", column="id"),
            target=ColumnRef(table="view1", column="id"),
        )
        graph.edges.append(edge)

        assert len(graph.edges) == 1

    def test_full_integration(self):
        """Test SchemaGraph with complete schema."""
        users_table = TableDef(
            name="users",
            columns=("id", "name", "email"),
            primary_keys=frozenset({"id"}),
        )

        user_summary_view = ViewDef(
            name="user_summary",
            query="SELECT id, name FROM users",
            output_columns=("id", "name"),
            dependencies=frozenset({"users"}),
        )

        edge = LineageEdge(
            source=ColumnRef(table="users", column="id"),
            target=ColumnRef(table="user_summary", column="id"),
        )

        graph = SchemaGraph(
            tables={"users": users_table},
            views={"user_summary": user_summary_view},
            edges=[edge],
        )

        assert len(graph.tables) == 1
        assert len(graph.views) == 1
        assert len(graph.edges) == 1
