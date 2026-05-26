"""
Tests verifying the Flask backend modularization.

Acceptance criteria:
1. from app import app still works (backward compatibility)
2. app.py is <= 25 meaningful lines
3. schema_service.py exposes load_schema() with caching
4. routes.py defines a Flask Blueprint with all route handlers
5. All 5 API endpoints return correct responses
6. /static/ files still served correctly
7. lineage_parser.py is unmodified (import still works)
8. No new dependencies introduced
9. python app.py entry point is intact (__main__ block present)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


# ------------------------------------------------------------------
# 1. Backward compatibility: from app import app
# ------------------------------------------------------------------
class TestBackwardCompatibility:
    """Verify that existing import patterns still work."""

    def test_from_app_import_app(self):
        from app import app
        from flask import Flask
        assert isinstance(app, Flask)

    def test_app_has_registered_routes(self):
        from app import app
        rules = [r.rule for r in app.url_map.iter_rules()]
        assert "/" in rules
        assert "/api/graph" in rules
        assert "/api/models" in rules
        assert "/api/upstream/<model_name>/<column_name>" in rules
        assert "/api/downstream/<model_name>/<column_name>" in rules

    def test_app_has_static_folder(self):
        from app import app
        assert app.static_folder is not None
        assert Path(app.static_folder).name == "static"


# ------------------------------------------------------------------
# 2. app.py size constraint
# ------------------------------------------------------------------
class TestAppPySlimness:
    """app.py must be <= 25 meaningful lines of code."""

    def test_app_py_meaningful_lines_under_25(self):
        app_path = Path(__file__).parent.parent / "app.py"
        lines = app_path.read_text(encoding="utf-8").splitlines()
        meaningful = [
            l for l in lines
            if l.strip() and not l.strip().startswith("#") and not l.strip().startswith('"""')
        ]
        # Also exclude docstring body lines (between triple quotes)
        in_docstring = False
        filtered = []
        for l in lines:
            stripped = l.strip()
            if stripped.startswith('"""') or stripped.startswith("'''"):
                if stripped.count('"""') == 2 or stripped.count("'''") == 2:
                    continue  # single-line docstring
                in_docstring = not in_docstring
                continue
            if in_docstring:
                continue
            if stripped and not stripped.startswith("#"):
                filtered.append(l)
        assert len(filtered) <= 25, (
            f"app.py has {len(filtered)} meaningful lines (max 25): {filtered}"
        )

    def test_app_py_has_main_block(self):
        app_path = Path(__file__).parent.parent / "app.py"
        content = app_path.read_text(encoding="utf-8")
        assert "if __name__" in content
        assert "app.run" in content


# ------------------------------------------------------------------
# 3. schema_service.py: load_schema() with caching
# ------------------------------------------------------------------
class TestSchemaService:
    """schema_service.py must expose load_schema() with module-level caching."""

    def test_load_schema_returns_models_and_graph(self):
        from schema_service import load_schema
        models, graph = load_schema()
        assert isinstance(models, dict)
        assert isinstance(graph, dict)
        assert "nodes" in graph
        assert "edges" in graph
        assert len(models) > 0

    def test_load_schema_caches_results(self):
        from schema_service import load_schema
        m1, g1 = load_schema()
        m2, g2 = load_schema()
        assert m1 is m2, "load_schema() should return the same cached models object"
        assert g1 is g2, "load_schema() should return the same cached graph object"

    def test_schema_path_resolves_correctly(self):
        from schema_service import SCHEMA_PATH
        assert SCHEMA_PATH.exists(), f"SCHEMA_PATH {SCHEMA_PATH} does not exist"
        assert SCHEMA_PATH.name == "schema.txt"

    def test_models_have_expected_structure(self):
        from schema_service import load_schema
        models, _ = load_schema()
        # All models should have name, model_type, columns attributes
        for name, model in models.items():
            assert hasattr(model, "name"), f"Model {name} missing 'name' attribute"
            assert hasattr(model, "model_type"), f"Model {name} missing 'model_type'"
            assert hasattr(model, "columns"), f"Model {name} missing 'columns'"
            assert model.model_type in ("table", "view"), (
                f"Model {name} has unexpected type: {model.model_type}"
            )


# ------------------------------------------------------------------
# 4. routes.py: Blueprint definition
# ------------------------------------------------------------------
class TestRoutesBlueprint:
    """routes.py must define a Flask Blueprint with all route handlers."""

    def test_blueprint_exists(self):
        from routes import bp
        from flask import Blueprint
        assert isinstance(bp, Blueprint)

    def test_blueprint_has_5_route_handlers(self):
        from routes import bp
        # Blueprint deferred_functions register routes when attached to app
        assert len(bp.deferred_functions) == 5, (
            f"Expected 5 route handlers, got {len(bp.deferred_functions)}"
        )

    def test_blueprint_imports_from_schema_service(self):
        """routes.py should get its data from schema_service, not parse directly."""
        routes_path = Path(__file__).parent.parent / "routes.py"
        content = routes_path.read_text(encoding="utf-8")
        assert "from schema_service import" in content or "import schema_service" in content
        # Should NOT have its own SCHEMA_PATH or parse_schema call
        assert "SCHEMA_PATH" not in content
        assert "parse_schema(" not in content


# ------------------------------------------------------------------
# 5. API endpoints return correct responses
# ------------------------------------------------------------------
class TestAPIEndpoints:
    """All 5 API endpoints must return identical responses to pre-refactor."""

    @classmethod
    def setup_class(cls):
        from app import app
        app.config["TESTING"] = True
        cls.client = app.test_client()

    def test_index_returns_html(self):
        resp = self.client.get("/")
        assert resp.status_code == 200
        assert resp.content_type.startswith("text/html")
        assert b"Column Lineage Explorer" in resp.data

    def test_api_graph_structure(self):
        resp = self.client.get("/api/graph")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "nodes" in data
        assert "edges" in data
        assert len(data["nodes"]) > 0
        assert len(data["edges"]) > 0
        # Verify node structure
        node = data["nodes"][0]
        assert "id" in node
        assert "type" in node
        assert "columns" in node

    def test_api_models_structure(self):
        resp = self.client.get("/api/models")
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)
        assert len(data) > 0
        # Verify model structure
        model = data[0]
        assert "name" in model
        assert "type" in model
        assert "column_count" in model

    def test_api_upstream_returns_correct_format(self):
        resp = self.client.get("/api/upstream/raw_customers/customer_id")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["model"] == "raw_customers"
        assert data["column"] == "customer_id"
        assert "upstream" in data

    def test_api_downstream_returns_correct_format(self):
        resp = self.client.get("/api/downstream/raw_orders/order_id")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["model"] == "raw_orders"
        assert data["column"] == "order_id"
        assert "downstream" in data
        # order_id should have downstream consumers
        assert len(data["downstream"]) > 0

    def test_api_upstream_derived_column_has_sources(self):
        """A derived column should have upstream sources."""
        resp = self.client.get("/api/upstream/stg_orders_enriched/order_total_amount")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["upstream"]) > 0


# ------------------------------------------------------------------
# 6. Static files still served
# ------------------------------------------------------------------
class TestStaticFileServing:
    """Static files must still be served at /static/."""

    @classmethod
    def setup_class(cls):
        from app import app
        app.config["TESTING"] = True
        cls.client = app.test_client()

    def test_static_css(self):
        resp = self.client.get("/static/style.css")
        assert resp.status_code == 200
        assert b"cursor: grab" in resp.data  # From drag feature

    def test_static_js(self):
        resp = self.client.get("/static/app.js")
        assert resp.status_code == 200
        assert b"/api/graph" in resp.data

    def test_static_index_html(self):
        resp = self.client.get("/static/index.html")
        assert resp.status_code == 200
        assert b"Column Lineage Explorer" in resp.data


# ------------------------------------------------------------------
# 7. lineage_parser.py is unmodified
# ------------------------------------------------------------------
class TestLineageParserUnchanged:
    """lineage_parser.py must still be importable with its original interface."""

    def test_lineage_parser_imports(self):
        from lineage_parser import parse_schema, get_upstream_lineage, get_downstream_lineage, get_lineage_graph
        assert callable(parse_schema)
        assert callable(get_upstream_lineage)
        assert callable(get_downstream_lineage)
        assert callable(get_lineage_graph)

    def test_lineage_parser_direct_usage(self):
        """Direct usage of lineage_parser (bypassing schema_service) still works."""
        from lineage_parser import parse_schema, get_lineage_graph
        schema_path = Path(__file__).parent.parent / "schema.txt"
        text = schema_path.read_text(encoding="utf-8")
        models = parse_schema(text)
        graph = get_lineage_graph(models)
        assert len(models) > 0
        assert "nodes" in graph
        assert "edges" in graph


# ------------------------------------------------------------------
# 8. No new runtime dependencies
# ------------------------------------------------------------------
class TestNoDependencyChanges:
    """No new runtime dependencies should be introduced."""

    def test_requirements_has_expected_deps(self):
        req_path = Path(__file__).parent.parent / "requirements.txt"
        content = req_path.read_text(encoding="utf-8").strip()
        lines = [l.strip() for l in content.splitlines() if l.strip()]
        # Should contain flask and sqlglot
        assert "flask" in content.lower()
        assert "sqlglot" in content.lower()
        assert len(lines) == 2, f"Expected flask and sqlglot in requirements.txt, got: {lines}"


# ------------------------------------------------------------------
# 9. Module separation: no circular imports
# ------------------------------------------------------------------
class TestNoCircularImports:
    """Verify imports work cleanly without circular dependency issues."""

    def test_import_schema_service_alone(self):
        """schema_service should be importable independently."""
        import importlib
        import schema_service
        importlib.reload(schema_service)
        assert hasattr(schema_service, "load_schema")

    def test_import_routes_alone(self):
        """routes should be importable (implies schema_service also works)."""
        import importlib
        import routes
        importlib.reload(routes)
        assert hasattr(routes, "bp")

    def test_import_app_alone(self):
        """app should be importable (implies routes and schema_service work)."""
        import importlib
        import app
        importlib.reload(app)
        assert hasattr(app, "app")


# ------------------------------------------------------------------
# 10. Data consistency between schema_service and routes
# ------------------------------------------------------------------
class TestDataConsistency:
    """Verify routes.py uses the same data from schema_service."""

    def test_routes_models_match_schema_service(self):
        from schema_service import load_schema
        from routes import MODELS as route_models
        service_models, _ = load_schema()
        # They should be the same object (cached)
        assert route_models is service_models, (
            "routes.MODELS should be the same cached object as schema_service"
        )

    def test_routes_graph_match_schema_service(self):
        from schema_service import load_schema
        from routes import GRAPH as route_graph
        _, service_graph = load_schema()
        assert route_graph is service_graph, (
            "routes.GRAPH should be the same cached object as schema_service"
        )

    def test_api_models_count_matches_schema_service(self):
        from app import app
        from schema_service import load_schema
        models, _ = load_schema()
        app.config["TESTING"] = True
        with app.test_client() as client:
            resp = client.get("/api/models")
            data = resp.get_json()
            assert len(data) == len(models), (
                f"API returns {len(data)} models but schema_service has {len(models)}"
            )
