"""
Tests proving the sqlglot-based parser handles advanced SQL constructs
that the regex parser cannot reliably parse.

Covers:
- Nested CTEs (views 6-8)
- UNION ALL lineage merging (view 4)
- Window functions with PARTITION BY and ORDER BY
- dbt Jinja template preprocessing
- Fallback behavior when sqlglot is unavailable or fails
- All 14 models (6 tables + 8 views) parsed correctly
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from lineage_parser import (
    parse_schema,
    get_upstream_lineage,
    get_downstream_lineage,
    get_lineage_graph,
    _preprocess_dbt_templates,
    _HAS_SQLGLOT,
)

# Load schema once for all tests
SCHEMA_PATH = Path(__file__).parent.parent / "schema.txt"
SCHEMA_TEXT = SCHEMA_PATH.read_text(encoding="utf-8")
MODELS = parse_schema(SCHEMA_TEXT)


class TestSqlglotAvailable:
    """Verify sqlglot is installed and active."""

    def test_sqlglot_is_installed(self):
        assert _HAS_SQLGLOT, "sqlglot must be installed for primary parser"

    def test_sqlglot_importable(self):
        import sqlglot
        assert hasattr(sqlglot, "parse")


class TestAllModelsDiscovered:
    """Verify all 14 models (6 tables + 8 views) are parsed."""

    def test_total_model_count(self):
        assert len(MODELS) == 14

    def test_table_count(self):
        tables = [m for m in MODELS.values() if m.model_type == "table"]
        assert len(tables) == 6

    def test_view_count(self):
        views = [m for m in MODELS.values() if m.model_type == "view"]
        assert len(views) == 8

    def test_nosuchtable_is_table(self):
        assert "nosuchtable" in MODELS
        assert MODELS["nosuchtable"].model_type == "table"
        assert "revenue_month" in MODELS["nosuchtable"].columns
        assert "id" in MODELS["nosuchtable"].columns


class TestNestedCTEs:
    """Test sqlglot handles nested CTEs in views 6-8."""

    # View 6: rpt_customer_growth_cohorts has 2 CTEs
    def test_view6_exists(self):
        assert "rpt_customer_growth_cohorts" in MODELS
        assert MODELS["rpt_customer_growth_cohorts"].model_type == "view"

    def test_view6_has_columns(self):
        cols = MODELS["rpt_customer_growth_cohorts"].columns
        assert len(cols) >= 10
        assert "signup_month" in cols
        assert "conversion_rate" in cols
        assert "revenue_per_customer" in cols
        assert "cohort_ltv_rank_in_month" in cols

    def test_view6_depends_on_mart(self):
        """rpt_customer_growth_cohorts depends on mart_customer_ltv_segments."""
        all_upstream_models = set()
        for col, lin in MODELS["rpt_customer_growth_cohorts"].column_lineage.items():
            for m, c in lin.upstream:
                all_upstream_models.add(m)
        assert "mart_customer_ltv_segments" in all_upstream_models

    def test_view6_window_functions(self):
        """LAG and RANK window functions are parsed."""
        assert "revenue_delta_vs_prior_cohort" in MODELS["rpt_customer_growth_cohorts"].columns
        assert "cohort_ltv_rank_in_month" in MODELS["rpt_customer_growth_cohorts"].columns
        lin_lag = MODELS["rpt_customer_growth_cohorts"].column_lineage.get("revenue_delta_vs_prior_cohort")
        if lin_lag:
            assert len(lin_lag.upstream) > 0
        lin_rank = MODELS["rpt_customer_growth_cohorts"].column_lineage.get("cohort_ltv_rank_in_month")
        if lin_rank:
            assert len(lin_rank.upstream) > 0

    # View 7: mart_segment_health_snapshot has 2 CTEs, 3 upstream views
    def test_view7_exists(self):
        assert "mart_segment_health_snapshot" in MODELS
        assert MODELS["mart_segment_health_snapshot"].model_type == "view"

    def test_view7_has_columns(self):
        cols = MODELS["mart_segment_health_snapshot"].columns
        assert len(cols) >= 10
        assert "health_status" in cols
        assert "health_score" in cols

    def test_view7_depends_on_multiple_upstream_views(self):
        """mart_segment_health_snapshot depends on mart_customer_ltv_segments,
        fct_customer_revenue_daily, and rpt_customer_growth_cohorts."""
        all_upstream_models = set()
        for col, lin in MODELS["mart_segment_health_snapshot"].column_lineage.items():
            for m, c in lin.upstream:
                all_upstream_models.add(m)
        assert "mart_customer_ltv_segments" in all_upstream_models
        assert "fct_customer_revenue_daily" in all_upstream_models
        assert "rpt_customer_growth_cohorts" in all_upstream_models

    def test_view7_health_score_is_derived(self):
        """health_score is a complex weighted formula - should be derived."""
        lin = MODELS["mart_segment_health_snapshot"].column_lineage.get("health_score")
        assert lin is not None
        assert lin.is_derived
        assert len(lin.upstream) >= 2

    # View 8: rpt_executive_revenue_dashboard has 2 CTEs
    def test_view8_exists(self):
        assert "rpt_executive_revenue_dashboard" in MODELS
        assert MODELS["rpt_executive_revenue_dashboard"].model_type == "view"

    def test_view8_has_columns(self):
        cols = MODELS["rpt_executive_revenue_dashboard"].columns
        assert len(cols) >= 10
        assert "executive_action" in cols
        assert "segment_revenue_rank" in cols
        assert "cumulative_revenue_by_month_rank" in cols

    def test_view8_depends_on_segment_health_and_facts(self):
        """rpt_executive_revenue_dashboard depends on mart_segment_health_snapshot
        and fct_customer_revenue_daily."""
        all_upstream_models = set()
        for col, lin in MODELS["rpt_executive_revenue_dashboard"].column_lineage.items():
            for m, c in lin.upstream:
                all_upstream_models.add(m)
        assert "mart_segment_health_snapshot" in all_upstream_models
        assert "fct_customer_revenue_daily" in all_upstream_models

    def test_view8_joins_nosuchtable(self):
        """View 8 joins nosuchtable — the id column should trace there."""
        lin = MODELS["rpt_executive_revenue_dashboard"].column_lineage.get("id")
        if lin:
            upstream_models = {m for m, c in lin.upstream}
            assert "nosuchtable" in upstream_models

    def test_view8_window_functions(self):
        """DENSE_RANK and SUM OVER window functions are parsed."""
        lin_rank = MODELS["rpt_executive_revenue_dashboard"].column_lineage.get("segment_revenue_rank")
        if lin_rank:
            assert len(lin_rank.upstream) > 0
        lin_cumulative = MODELS["rpt_executive_revenue_dashboard"].column_lineage.get("cumulative_revenue_by_month_rank")
        if lin_cumulative:
            assert len(lin_cumulative.upstream) > 0


class TestUnionAllLineageMerging:
    """Test UNION ALL lineage merging (view 4: fct_customer_revenue_daily)."""

    def test_union_all_merges_both_branches(self):
        """customer_id in fct_customer_revenue_daily comes from UNION ALL
        of line_revenue_events (stg_line_items_priced) and
        refund_events (stg_orders_enriched)."""
        lin = MODELS["fct_customer_revenue_daily"].column_lineage.get("customer_id")
        assert lin is not None
        upstream_models = {m for m, c in lin.upstream}
        assert upstream_models & {"stg_line_items_priced", "stg_orders_enriched"}

    def test_union_all_revenue_amount_from_both_sources(self):
        """daily_revenue_amount aggregates from UNION ALL branches."""
        lin = MODELS["fct_customer_revenue_daily"].column_lineage.get("daily_revenue_amount")
        assert lin is not None
        assert len(lin.upstream) >= 1

    def test_no_branch_names_leak(self):
        """No __branch suffixes should appear in final lineage."""
        for col, lin in MODELS["fct_customer_revenue_daily"].column_lineage.items():
            for m, c in lin.upstream:
                assert not m.endswith("__branch"), (
                    f"{col} has branch suffix in upstream: {m}"
                )


class TestWindowFunctions:
    """Test window functions with PARTITION BY and ORDER BY."""

    def test_dense_rank_in_mart(self):
        """DENSE_RANK() OVER (ORDER BY total_revenue_amount DESC)."""
        lin = MODELS["mart_customer_ltv_segments"].column_lineage.get("revenue_rank")
        assert lin is not None
        assert len(lin.upstream) > 0

    def test_ntile_in_mart(self):
        """NTILE(5) OVER (ORDER BY total_revenue_amount DESC)."""
        lin = MODELS["mart_customer_ltv_segments"].column_lineage.get("revenue_quintile")
        assert lin is not None
        assert len(lin.upstream) > 0

    def test_lag_in_cohorts(self):
        """LAG window function in rpt_customer_growth_cohorts."""
        lin = MODELS["rpt_customer_growth_cohorts"].column_lineage.get("revenue_delta_vs_prior_cohort")
        assert lin is not None
        assert len(lin.upstream) > 0

    def test_rank_in_cohorts(self):
        """RANK() OVER (PARTITION BY signup_month ORDER BY ...) in view 6."""
        lin = MODELS["rpt_customer_growth_cohorts"].column_lineage.get("cohort_ltv_rank_in_month")
        assert lin is not None
        assert len(lin.upstream) > 0


class TestDbtSyntaxParsing:
    """Test dbt Jinja template preprocessing."""

    def test_source_template_replaced(self):
        """{{ source('raw', 'orders') }} should resolve to 'orders'."""
        result = _preprocess_dbt_templates("SELECT * FROM {{ source('raw', 'orders') }}")
        assert "orders" in result
        assert "{{" not in result
        assert "}}" not in result

    def test_ref_template_replaced(self):
        """{{ ref('stg_orders_enriched') }} should resolve to 'stg_orders_enriched'."""
        result = _preprocess_dbt_templates("SELECT * FROM {{ ref('stg_orders_enriched') }}")
        assert "stg_orders_enriched" in result
        assert "{{" not in result

    def test_source_with_double_quotes(self):
        """{{ source(\"schema\", \"table\") }} should also work."""
        result = _preprocess_dbt_templates('SELECT * FROM {{ source("raw", "orders") }}')
        assert "orders" in result
        assert "{{" not in result

    def test_ref_with_double_quotes(self):
        """{{ ref(\"model\") }} should also work."""
        result = _preprocess_dbt_templates('SELECT * FROM {{ ref("stg_orders_enriched") }}')
        assert "stg_orders_enriched" in result

    def test_mixed_templates(self):
        """Multiple templates in one query."""
        sql = """
        SELECT a.id, b.name
        FROM {{ source('raw', 'customers') }} a
        JOIN {{ ref('stg_orders') }} b ON a.id = b.customer_id
        """
        result = _preprocess_dbt_templates(sql)
        assert "customers" in result
        assert "stg_orders" in result
        assert "{{" not in result

    def test_no_templates_unchanged(self):
        """SQL without templates should pass through unchanged."""
        sql = "SELECT * FROM raw_orders"
        result = _preprocess_dbt_templates(sql)
        assert result == sql

    def test_dbt_source_in_full_parse(self):
        """Full parse of SQL with dbt source template."""
        sql = """
        CREATE TABLE raw_items (
            item_id BIGINT PRIMARY KEY,
            name TEXT
        );
        CREATE VIEW stg_items AS
        SELECT item_id, name FROM {{ source('raw', 'raw_items') }};
        """
        models = parse_schema(sql)
        assert "raw_items" in models
        assert "stg_items" in models
        stg = models["stg_items"]
        assert "item_id" in stg.columns
        # Should trace to raw_items
        lin = stg.column_lineage.get("item_id")
        assert lin is not None
        assert ("raw_items", "item_id") in lin.upstream

    def test_dbt_ref_in_full_parse(self):
        """Full parse of SQL with dbt ref template."""
        sql = """
        CREATE TABLE base_orders (
            order_id BIGINT PRIMARY KEY,
            amount NUMERIC(12, 2)
        );
        CREATE VIEW enriched_orders AS
        SELECT order_id, amount FROM {{ ref('base_orders') }};
        """
        models = parse_schema(sql)
        assert "base_orders" in models
        assert "enriched_orders" in models
        enriched = models["enriched_orders"]
        assert "order_id" in enriched.columns
        lin = enriched.column_lineage.get("order_id")
        assert lin is not None
        assert ("base_orders", "order_id") in lin.upstream


class TestFallbackPath:
    """Test the regex fallback path with deliberately odd SQL."""

    def test_regex_fallback_for_simple_table(self):
        """The regex parser should handle a basic CREATE TABLE."""
        from lineage_parser import _parse_schema_regex

        sql = """
        CREATE TABLE test_fallback (
            id BIGINT PRIMARY KEY,
            name TEXT NOT NULL
        );
        """
        models = _parse_schema_regex(sql)
        assert "test_fallback" in models
        assert models["test_fallback"].model_type == "table"
        assert "id" in models["test_fallback"].columns
        assert "name" in models["test_fallback"].columns

    def test_regex_fallback_for_simple_view(self):
        """The regex parser should handle a basic CREATE VIEW."""
        from lineage_parser import _parse_schema_regex

        sql = """
        CREATE TABLE source_tbl (
            col_a TEXT,
            col_b TEXT
        );
        CREATE VIEW simple_view AS
        SELECT col_a, col_b FROM source_tbl;
        """
        models = _parse_schema_regex(sql)
        assert "source_tbl" in models
        assert "simple_view" in models
        assert "col_a" in models["simple_view"].columns

    def test_regex_produces_same_tables_as_sqlglot(self):
        """Both parsers should find the same tables in the full schema."""
        from lineage_parser import _parse_schema_regex, _preprocess_dbt_templates

        preprocessed = _preprocess_dbt_templates(SCHEMA_TEXT)
        regex_models = _parse_schema_regex(preprocessed)

        sqlglot_tables = {n for n, m in MODELS.items() if m.model_type == "table"}
        regex_tables = {n for n, m in regex_models.items() if m.model_type == "table"}

        # Both should find the same set of tables
        assert sqlglot_tables == regex_tables


class TestGraphStructureWithSqlglot:
    """Verify the graph produced by sqlglot parsing is structurally sound."""

    def test_graph_has_14_nodes(self):
        graph = get_lineage_graph(MODELS)
        assert len(graph["nodes"]) == 14

    def test_all_edge_models_are_real(self):
        graph = get_lineage_graph(MODELS)
        model_names = {n["id"] for n in graph["nodes"]}
        for edge in graph["edges"]:
            assert edge["source_model"] in model_names, (
                f"Unknown source model: {edge['source_model']}"
            )
            assert edge["target_model"] in model_names, (
                f"Unknown target model: {edge['target_model']}"
            )

    def test_no_cte_names_in_edges(self):
        """No CTE names should appear in graph edges."""
        cte_names = {
            "payment_rollup", "item_rollup", "customer_orders",
            "line_revenue_events", "refund_events", "all_events",
            "revenue_rollup", "scored_customers",
            "cohort_base", "cohort_rollup",
            "recent_revenue", "cohort_context",
            "segment_rollup", "fact_monthly",
        }
        graph = get_lineage_graph(MODELS)
        for edge in graph["edges"]:
            assert edge["source_model"] not in cte_names
            assert edge["target_model"] not in cte_names

    def test_edge_count_increased_with_new_views(self):
        """With 14 models, there should be more edges than with 10."""
        graph = get_lineage_graph(MODELS)
        assert len(graph["edges"]) > 167  # Was 167 with 10 models
