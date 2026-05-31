"""Tests for the standalone schema.txt generator (generate_schema.py)."""

import os
import re
import sys
import tempfile

import pytest

# Ensure the project root is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from generate_schema import build_schema, main, DOMAINS


# ---------------------------------------------------------------------------
# build_schema() — basic structure
# ---------------------------------------------------------------------------

class TestBuildSchemaStructure:
    """Verify the generated SQL text has the right structural properties."""

    def test_ecommerce_default_produces_tables_and_views(self):
        schema = build_schema()
        assert "CREATE TABLE" in schema
        assert "CREATE VIEW" in schema

    def test_ecommerce_has_drop_statements(self):
        schema = build_schema()
        assert "DROP VIEW IF EXISTS" in schema
        assert "DROP TABLE IF EXISTS" in schema

    def test_ecommerce_default_table_count(self):
        schema = build_schema()
        assert schema.count("CREATE TABLE") == 5

    def test_ecommerce_default_view_count_depth4(self):
        schema = build_schema(depth=4)
        views = re.findall(r"CREATE VIEW\s+(\w+)", schema)
        assert len(views) >= 6  # stg(2) + int/fct(2) + mart(1) + rpt(2)

    def test_depth_1_produces_staging_only(self):
        schema = build_schema(depth=1)
        views = re.findall(r"CREATE VIEW\s+(\w+)", schema)
        assert all("stg_" in v for v in views), f"Non-staging views found: {views}"
        assert len(views) >= 1

    def test_depth_2_adds_intermediate_or_fact(self):
        schema = build_schema(depth=2)
        views = re.findall(r"CREATE VIEW\s+(\w+)", schema)
        has_int_or_fct = any("int_" in v or "fct_" in v for v in views)
        assert has_int_or_fct, f"No int/fct views at depth 2: {views}"

    def test_depth_3_adds_mart(self):
        schema = build_schema(depth=3)
        views = re.findall(r"CREATE VIEW\s+(\w+)", schema)
        has_mart = any("mart_" in v for v in views)
        assert has_mart, f"No mart views at depth 3: {views}"

    def test_depth_4_adds_report(self):
        schema = build_schema(depth=4)
        views = re.findall(r"CREATE VIEW\s+(\w+)", schema)
        has_rpt = any("rpt_" in v for v in views)
        assert has_rpt, f"No rpt views at depth 4: {views}"

    def test_table_count_limits(self):
        schema_2 = build_schema(table_count=2)
        assert schema_2.count("CREATE TABLE") == 2
        schema_10 = build_schema(table_count=10)
        # capped at available tables (5 for ecommerce without inventory)
        assert schema_10.count("CREATE TABLE") <= 10

    def test_seed_produces_deterministic_output(self):
        a = build_schema(seed=42)
        b = build_schema(seed=42)
        assert a == b

    def test_unknown_domain_raises(self):
        with pytest.raises(ValueError, match="Unknown domain"):
            build_schema(domain="aliens")


# ---------------------------------------------------------------------------
# SQL validity checks
# ---------------------------------------------------------------------------

class TestSQLValidity:
    """Verify that generated SQL is structurally valid for the lineage parser."""

    @pytest.fixture(params=list(DOMAINS.keys()))
    def schema_for_domain(self, request):
        return build_schema(domain=request.param, depth=4)

    def test_every_create_table_has_semicolon(self, schema_for_domain):
        """Each CREATE TABLE block should end with );"""
        # Find each CREATE TABLE and verify it ends properly
        tables = re.findall(
            r"CREATE TABLE\s+\w+\s*\(.*?\);",
            schema_for_domain,
            re.DOTALL | re.IGNORECASE,
        )
        assert len(tables) >= 1
        for t in tables:
            assert t.strip().endswith(");")

    def test_every_create_view_has_semicolon(self, schema_for_domain):
        """Each CREATE VIEW block should end with ;"""
        views = re.findall(
            r"CREATE VIEW\s+\w+\s+AS\s+.*?;",
            schema_for_domain,
            re.DOTALL | re.IGNORECASE,
        )
        assert len(views) >= 1

    def test_drop_count_matches_create_count(self, schema_for_domain):
        drop_views = len(re.findall(r"DROP VIEW IF EXISTS", schema_for_domain))
        create_views = len(re.findall(r"CREATE VIEW", schema_for_domain))
        assert drop_views == create_views

        drop_tables = len(re.findall(r"DROP TABLE IF EXISTS", schema_for_domain))
        create_tables = len(re.findall(r"CREATE TABLE", schema_for_domain))
        assert drop_tables == create_tables

    def test_no_duplicate_table_names(self, schema_for_domain):
        tables = re.findall(r"CREATE TABLE\s+(\w+)", schema_for_domain)
        assert len(tables) == len(set(tables))

    def test_no_duplicate_view_names(self, schema_for_domain):
        views = re.findall(r"CREATE VIEW\s+(\w+)", schema_for_domain)
        assert len(views) == len(set(views))

    def test_tables_have_primary_key(self, schema_for_domain):
        tables = re.findall(
            r"CREATE TABLE\s+\w+\s*\((.*?)\);",
            schema_for_domain,
            re.DOTALL | re.IGNORECASE,
        )
        for body in tables:
            assert "PRIMARY KEY" in body.upper()


# ---------------------------------------------------------------------------
# Domain coverage
# ---------------------------------------------------------------------------

class TestDomains:
    """Verify all three domains produce usable schemas."""

    def test_healthcare_domain(self):
        schema = build_schema(domain="healthcare", depth=4)
        assert "raw_patients" in schema
        assert "raw_encounters" in schema
        views = re.findall(r"CREATE VIEW\s+(\w+)", schema)
        assert len(views) >= 4

    def test_saas_domain(self):
        schema = build_schema(domain="saas", depth=4)
        assert "raw_accounts" in schema
        assert "raw_users" in schema
        views = re.findall(r"CREATE VIEW\s+(\w+)", schema)
        assert len(views) >= 4

    def test_ecommerce_domain(self):
        schema = build_schema(domain="ecommerce", depth=4)
        assert "raw_customers" in schema
        assert "raw_orders" in schema
        views = re.findall(r"CREATE VIEW\s+(\w+)", schema)
        assert len(views) >= 6


# ---------------------------------------------------------------------------
# dbt Jinja syntax
# ---------------------------------------------------------------------------

class TestDbtJinja:
    """Verify --include-dbt wraps table references in dbt syntax."""

    def test_dbt_adds_source_refs(self):
        schema = build_schema(include_dbt=True)
        assert "{{ source(" in schema

    def test_dbt_not_present_by_default(self):
        schema = build_schema(include_dbt=False)
        assert "{{ source(" not in schema
        assert "{{ ref(" not in schema

    def test_healthcare_dbt_source_schema(self):
        schema = build_schema(domain="healthcare", include_dbt=True)
        assert "{{ source('clinical'" in schema

    def test_saas_dbt_source_schema(self):
        schema = build_schema(domain="saas", include_dbt=True)
        assert "{{ source('app'" in schema


# ---------------------------------------------------------------------------
# SQL features the lineage parser expects
# ---------------------------------------------------------------------------

class TestSQLFeatures:
    """Verify generated SQL exercises the SQL constructs the lineage parser handles."""

    def test_has_cte(self):
        schema = build_schema()
        assert re.search(r"\bWITH\s+\w+\s+AS\s*\(", schema, re.IGNORECASE)

    def test_has_case_expression(self):
        schema = build_schema()
        assert re.search(r"\bCASE\b", schema, re.IGNORECASE)
        assert re.search(r"\bWHEN\b", schema, re.IGNORECASE)

    def test_has_coalesce(self):
        schema = build_schema()
        assert "COALESCE(" in schema.upper()

    def test_has_window_function(self):
        schema = build_schema(depth=3)
        assert re.search(r"\bOVER\s*\(", schema, re.IGNORECASE)

    def test_has_aggregate_functions(self):
        schema = build_schema()
        assert "SUM(" in schema.upper()
        assert "COUNT(" in schema.upper()

    def test_has_join(self):
        schema = build_schema()
        assert re.search(r"\bJOIN\b", schema, re.IGNORECASE)

    def test_has_filter_where(self):
        schema = build_schema()
        assert "FILTER (WHERE" in schema

    def test_has_union_all(self):
        schema = build_schema(depth=2)
        assert "UNION ALL" in schema

    def test_has_cast(self):
        schema = build_schema()
        assert "::" in schema  # PostgreSQL cast syntax

    def test_has_date_trunc(self):
        schema = build_schema()
        assert "DATE_TRUNC(" in schema

    def test_has_nullif(self):
        schema = build_schema(depth=3)
        assert "NULLIF(" in schema

    def test_has_dense_rank_or_ntile(self):
        schema = build_schema(depth=3)
        has_rank = "DENSE_RANK()" in schema or "NTILE(" in schema
        assert has_rank


# ---------------------------------------------------------------------------
# Lineage parser integration (optional — only runs if lineage_parser exists)
# ---------------------------------------------------------------------------

class TestParserIntegration:
    """Verify generated schemas are parseable by lineage_parser.parse_schema()."""

    @pytest.fixture(autouse=True)
    def _check_parser_available(self):
        try:
            from lineage_parser import parse_schema
            self.parse_schema = parse_schema
        except ImportError:
            pytest.skip("lineage_parser not available")

    @pytest.mark.parametrize("domain", list(DOMAINS.keys()))
    def test_parser_finds_all_tables(self, domain):
        schema_text = build_schema(domain=domain, depth=4)
        models = self.parse_schema(schema_text)
        expected_tables = re.findall(r"CREATE TABLE\s+(\w+)", schema_text)
        for tname in expected_tables:
            assert tname in models, f"Parser missed table {tname}"
            assert models[tname].model_type == "table"

    @pytest.mark.parametrize("domain", list(DOMAINS.keys()))
    def test_parser_finds_all_views(self, domain):
        schema_text = build_schema(domain=domain, depth=4)
        models = self.parse_schema(schema_text)
        expected_views = re.findall(r"CREATE VIEW\s+(\w+)", schema_text)
        for vname in expected_views:
            assert vname in models, f"Parser missed view {vname}"
            assert models[vname].model_type == "view"

    @pytest.mark.parametrize("domain", list(DOMAINS.keys()))
    def test_parser_extracts_columns(self, domain):
        schema_text = build_schema(domain=domain, depth=4)
        models = self.parse_schema(schema_text)
        for name, model in models.items():
            assert len(model.columns) > 0, f"Model {name} has no columns"

    def test_ecommerce_graph_has_edges(self):
        from lineage_parser import get_lineage_graph
        schema_text = build_schema(domain="ecommerce", depth=4)
        models = self.parse_schema(schema_text)
        graph = get_lineage_graph(models)
        assert len(graph["edges"]) > 0, "Graph has no edges"
        assert len(graph["nodes"]) > 0, "Graph has no nodes"


# ---------------------------------------------------------------------------
# CLI (main function)
# ---------------------------------------------------------------------------

class TestCLI:
    """Verify the CLI entry point works."""

    def test_dry_run_prints_to_stdout(self, capsys):
        main(["--dry-run"])
        captured = capsys.readouterr()
        assert "CREATE TABLE" in captured.out
        assert "CREATE VIEW" in captured.out

    def test_writes_file(self, tmp_path):
        output = tmp_path / "test_schema.txt"
        main(["-o", str(output)])
        assert output.exists()
        content = output.read_text(encoding="utf-8")
        assert "CREATE TABLE" in content
        assert "CREATE VIEW" in content

    def test_domain_flag(self, capsys):
        main(["--dry-run", "--domain", "healthcare"])
        captured = capsys.readouterr()
        assert "raw_patients" in captured.out

    def test_depth_flag(self, capsys):
        main(["--dry-run", "--depth", "1"])
        captured = capsys.readouterr()
        views = re.findall(r"CREATE VIEW\s+(\w+)", captured.out)
        assert all("stg_" in v for v in views)

    def test_tables_flag(self, capsys):
        main(["--dry-run", "--tables", "2"])
        captured = capsys.readouterr()
        tables = re.findall(r"CREATE TABLE\s+(\w+)", captured.out)
        assert len(tables) == 2

    def test_include_dbt_flag(self, capsys):
        main(["--dry-run", "--include-dbt"])
        captured = capsys.readouterr()
        assert "{{ source(" in captured.out

    def test_seed_flag_deterministic(self, capsys):
        main(["--dry-run", "--seed", "99"])
        out1 = capsys.readouterr().out
        main(["--dry-run", "--seed", "99"])
        out2 = capsys.readouterr().out
        assert out1 == out2

    def test_output_reports_stats(self, tmp_path, capsys):
        output = tmp_path / "stats_test.txt"
        main(["-o", str(output)])
        captured = capsys.readouterr()
        assert "tables" in captured.out
        assert "views" in captured.out
        assert "bytes" in captured.out
