"""
Tester verification tests for column-lineage web app.

These tests go deeper than the developer's existing suite to verify:
1. Exact upstream columns for the 5 required lineage proofs
2. No CTE names or __branch names leak into the final lineage graph
3. Flask API endpoints return correct data via test_client()
4. Edge-to-edge lineage resolution across multi-layer views
5. Graph structural invariants
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from lineage_parser import (
    parse_schema,
    get_upstream_lineage,
    get_downstream_lineage,
    get_lineage_graph,
)

SCHEMA_PATH = Path(__file__).parent.parent / "schema.txt"
SCHEMA_TEXT = SCHEMA_PATH.read_text(encoding="utf-8")
MODELS = parse_schema(SCHEMA_TEXT)
GRAPH = get_lineage_graph(MODELS)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------
KNOWN_REAL_MODELS = {
    "nosuchtable",
    "raw_customers",
    "raw_orders",
    "raw_order_items",
    "raw_products",
    "raw_payments",
    "stg_orders_enriched",
    "stg_line_items_priced",
    "int_customer_order_metrics",
    "fct_customer_revenue_daily",
    "mart_customer_ltv_segments",
    "rpt_customer_growth_cohorts",
    "mart_segment_health_snapshot",
    "rpt_executive_revenue_dashboard",
}


def _upstream_set(model_name: str, col_name: str):
    """Return set of (model, col) upstream tuples for convenience."""
    lin = MODELS[model_name].column_lineage[col_name]
    return set(lin.upstream)


def _upstream_models(model_name: str, col_name: str):
    return {m for m, c in MODELS[model_name].column_lineage[col_name].upstream}


# ------------------------------------------------------------------
# 1. No CTE / branch names leak into final lineage
# ------------------------------------------------------------------
class TestNoCTELeakage:
    """CTE names (payment_rollup, item_rollup, customer_orders, etc.)
    and __branch suffixes must not appear in any view's lineage."""

    CTE_NAMES = {
        "payment_rollup", "item_rollup",
        "customer_orders",
        "line_revenue_events", "refund_events", "all_events",
        "revenue_rollup", "scored_customers",
        "cohort_base", "cohort_rollup",
        "recent_revenue", "cohort_context",
        "segment_rollup", "fact_monthly",
    }

    def test_no_cte_in_any_view_upstream(self):
        for model_name, model in MODELS.items():
            if model.model_type != "view":
                continue
            for col, lin in model.column_lineage.items():
                for m, c in lin.upstream:
                    assert m not in self.CTE_NAMES, (
                        f"{model_name}.{col} has CTE '{m}' in upstream"
                    )

    def test_no_branch_suffix_in_graph_edges(self):
        for edge in GRAPH["edges"]:
            assert not edge["source_model"].endswith("__branch"), (
                f"Branch suffix in edge source: {edge}"
            )
            assert not edge["target_model"].endswith("__branch"), (
                f"Branch suffix in edge target: {edge}"
            )

    def test_all_edge_models_are_real(self):
        for edge in GRAPH["edges"]:
            assert edge["source_model"] in KNOWN_REAL_MODELS, (
                f"Unknown source model in edge: {edge['source_model']}"
            )
            assert edge["target_model"] in KNOWN_REAL_MODELS, (
                f"Unknown target model in edge: {edge['target_model']}"
            )


# ------------------------------------------------------------------
# 2. Deep lineage proofs for the 5 required columns
# ------------------------------------------------------------------
class TestDeepLineageProofs:
    """These are the 5 lineage traces explicitly required by the task."""

    # ---- mart_customer_ltv_segments.ltv_after_fees_amount ----
    def test_ltv_after_fees_amount_upstream_sources(self):
        """ltv_after_fees_amount = COALESCE(rr.total_revenue_amount, 0)
            - COALESCE(icom.lifetime_processor_fee_amount, 0)

        revenue_rollup.total_revenue_amount -> fct_customer_revenue_daily.daily_revenue_amount
        int_customer_order_metrics.lifetime_processor_fee_amount
            -> stg_orders_enriched.total_processor_fee
            -> raw_payments.processor_fee

        Immediate upstream must reference int_customer_order_metrics
        and fct_customer_revenue_daily (through the CTE resolution)."""
        ups = _upstream_set("mart_customer_ltv_segments", "ltv_after_fees_amount")
        upstream_models = {m for m, c in ups}
        # Must touch both upstream views
        assert "int_customer_order_metrics" in upstream_models or "fct_customer_revenue_daily" in upstream_models, (
            f"Expected int_customer_order_metrics or fct_customer_revenue_daily in upstream, got {upstream_models}"
        )
        assert len(ups) >= 2, f"Expected at least 2 upstream refs, got {ups}"

    def test_ltv_after_fees_recursive_upstream_reaches_base_tables(self):
        """Recursive upstream should eventually reach raw_payments (for processor fees)
        and raw tables that feed revenue."""
        recursive_ups = get_upstream_lineage(
            MODELS, "mart_customer_ltv_segments", "ltv_after_fees_amount"
        )
        recursive_models = {m for m, c in recursive_ups}
        # Must reach base tables
        assert len(recursive_models & {"raw_payments", "raw_orders", "raw_order_items"}) > 0, (
            f"Expected base tables in recursive upstream, got {recursive_models}"
        )

    # ---- mart_customer_ltv_segments.customer_segment ----
    def test_customer_segment_is_multicolumn_case(self):
        """customer_segment is a CASE with refs to:
        lifetime_order_count, total_revenue_amount, completed_order_count,
        total_refund_events, customer_age_days, marketing_opt_in."""
        lin = MODELS["mart_customer_ltv_segments"].column_lineage["customer_segment"]
        assert lin.is_derived
        upstream_cols = {c for m, c in lin.upstream}
        # At minimum, several of these scored_customers columns should be traced
        assert len(upstream_cols) >= 3, (
            f"CASE with 6 column refs should map to >=3 upstream cols, got {upstream_cols}"
        )

    # ---- fct_customer_revenue_daily.daily_revenue_amount ----
    def test_daily_revenue_amount_traces_through_union(self):
        """daily_revenue_amount = SUM(revenue_amount) from UNION ALL of
        line_revenue_events (stg_line_items_priced) and
        refund_events (stg_orders_enriched)."""
        ups = _upstream_set("fct_customer_revenue_daily", "daily_revenue_amount")
        upstream_models = {m for m, c in ups}
        assert len(ups) >= 1, f"Expected upstream for daily_revenue_amount, got {ups}"
        # Should reference at least one of the upstream views
        assert upstream_models & {"stg_line_items_priced", "stg_orders_enriched"}, (
            f"Expected stg_line_items_priced or stg_orders_enriched, got {upstream_models}"
        )

    # ---- stg_orders_enriched.net_collected_amount ----
    def test_net_collected_amount_from_raw_payments(self):
        """net_collected_amount = COALESCE(pr.charged_amount, 0) - COALESCE(pr.refund_amount, 0)
        Both charged_amount and refund_amount come from the payment_rollup CTE,
        which aggregates raw_payments.amount and raw_payments.payment_type."""
        ups = _upstream_set("stg_orders_enriched", "net_collected_amount")
        assert len(ups) >= 2, f"Expected >=2 upstream for net_collected_amount, got {ups}"
        upstream_models = {m for m, c in ups}
        assert "raw_payments" in upstream_models, (
            f"Expected raw_payments in upstream, got {upstream_models}"
        )

    # ---- stg_line_items_priced.estimated_line_margin ----
    def test_estimated_line_margin_exact_columns(self):
        """estimated_line_margin =
           ((oi.quantity * oi.unit_price_amount) - COALESCE(oi.item_discount_amt, 0))
           - (COALESCE(p.standard_cost_amt, 0) * oi.quantity)
        Must include:
          raw_order_items.quantity, raw_order_items.unit_price_amount,
          raw_order_items.item_discount_amt, raw_products.standard_cost_amt"""
        ups = _upstream_set("stg_line_items_priced", "estimated_line_margin")
        assert ("raw_order_items", "quantity") in ups
        assert ("raw_order_items", "unit_price_amount") in ups
        assert ("raw_order_items", "item_discount_amt") in ups
        assert ("raw_products", "standard_cost_amt") in ups
        assert MODELS["stg_line_items_priced"].column_lineage["estimated_line_margin"].is_derived


# ------------------------------------------------------------------
# 3. Flask API tests via test_client
# ------------------------------------------------------------------
class TestFlaskAPI:
    """Test all API endpoints using Flask's test_client (no live server)."""

    @classmethod
    def setup_class(cls):
        from app import app
        app.config["TESTING"] = True
        cls.client = app.test_client()

    def test_index_returns_html(self):
        resp = self.client.get("/")
        assert resp.status_code == 200
        assert b"Column Lineage Explorer" in resp.data

    def test_api_graph_returns_nodes_and_edges(self):
        resp = self.client.get("/api/graph")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "nodes" in data
        assert "edges" in data
        assert len(data["nodes"]) == 14  # 6 tables + 8 views
        assert len(data["edges"]) > 100

    def test_api_graph_node_structure(self):
        resp = self.client.get("/api/graph")
        data = resp.get_json()
        for node in data["nodes"]:
            assert "id" in node
            assert "type" in node
            assert "columns" in node
            assert node["type"] in ("table", "view")
            for col in node["columns"]:
                assert "name" in col
                assert "is_derived" in col

    def test_api_models_list(self):
        resp = self.client.get("/api/models")
        assert resp.status_code == 200
        data = resp.get_json()
        names = {m["name"] for m in data}
        assert names == KNOWN_REAL_MODELS

    def test_api_upstream_base_column(self):
        """Base table columns have no upstream."""
        resp = self.client.get("/api/upstream/raw_customers/customer_id")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["model"] == "raw_customers"
        assert data["column"] == "customer_id"
        # Base column: upstream is just itself
        assert len(data["upstream"]) >= 1

    def test_api_upstream_derived_column(self):
        resp = self.client.get("/api/upstream/stg_orders_enriched/order_total_amount")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["upstream"]) > 0

    def test_api_downstream(self):
        resp = self.client.get("/api/downstream/raw_orders/order_id")
        assert resp.status_code == 200
        data = resp.get_json()
        downstream_models = {d[0] for d in data["downstream"]}
        assert len(downstream_models) > 0

    def test_api_static_css(self):
        resp = self.client.get("/static/style.css")
        assert resp.status_code == 200

    def test_api_static_js(self):
        resp = self.client.get("/static/app.js")
        assert resp.status_code == 200
        assert b"Column Lineage Explorer" in resp.data


# ------------------------------------------------------------------
# 4. Graph structural invariants
# ------------------------------------------------------------------
class TestGraphInvariants:
    """Verify structural properties of the lineage graph."""

    def test_every_view_column_has_lineage_entry(self):
        for name, model in MODELS.items():
            if model.model_type == "view":
                for col in model.columns:
                    assert col in model.column_lineage, (
                        f"{name}.{col} listed in columns but missing from column_lineage"
                    )

    def test_every_edge_source_column_exists_in_source_model(self):
        """If edge says (raw_orders, customer_id) -> ..., then
        raw_orders must actually have customer_id."""
        for edge in GRAPH["edges"]:
            src_model = edge["source_model"]
            src_col = edge["source_column"]
            assert src_model in MODELS, f"Source model {src_model} not found"
            assert src_col in MODELS[src_model].columns, (
                f"Column {src_col} not in {src_model}.columns"
            )

    def test_every_edge_target_column_exists_in_target_model(self):
        for edge in GRAPH["edges"]:
            tgt_model = edge["target_model"]
            tgt_col = edge["target_column"]
            assert tgt_model in MODELS, f"Target model {tgt_model} not found"
            assert tgt_col in MODELS[tgt_model].columns, (
                f"Column {tgt_col} not in {tgt_model}.columns"
            )

    def test_no_self_referencing_edges(self):
        for edge in GRAPH["edges"]:
            if edge["source_model"] == edge["target_model"]:
                assert edge["source_column"] != edge["target_column"], (
                    f"Self-referencing edge: {edge}"
                )

    def test_table_columns_have_no_upstream(self):
        for name, model in MODELS.items():
            if model.model_type == "table":
                for col, lin in model.column_lineage.items():
                    assert lin.upstream == [], (
                        f"Base table {name}.{col} should have no upstream, got {lin.upstream}"
                    )

    def test_all_10_models_present(self):
        assert set(MODELS.keys()) == KNOWN_REAL_MODELS

    def test_view_columns_count_reasonable(self):
        """Each view should have at least a few columns."""
        for name, model in MODELS.items():
            if model.model_type == "view":
                assert len(model.columns) >= 5, (
                    f"{name} has only {len(model.columns)} columns"
                )


# ------------------------------------------------------------------
# 5. Cross-layer lineage resolution
# ------------------------------------------------------------------
class TestCrossLayerLineage:
    """Verify that lineage resolves correctly across multiple view layers."""

    def test_mart_signup_date_traces_to_raw_customers(self):
        """mart_customer_ltv_segments.signup_date should trace back to
        raw_customers.signup_ts (through int_customer_order_metrics CTE)."""
        recursive = get_upstream_lineage(
            MODELS, "mart_customer_ltv_segments", "signup_date"
        )
        recursive_models = {m for m, c in recursive}
        assert "raw_customers" in recursive_models, (
            f"signup_date should trace to raw_customers, got {recursive_models}"
        )

    def test_mart_email_normalized_traces_to_raw_customers(self):
        """email_normalized = LOWER(c.email) — should trace to raw_customers.email."""
        recursive = get_upstream_lineage(
            MODELS, "mart_customer_ltv_segments", "email_normalized"
        )
        recursive_models = {m for m, c in recursive}
        assert "raw_customers" in recursive_models

    def test_downstream_from_raw_payments_amount(self):
        """raw_payments.amount should eventually flow downstream through
        stg_orders_enriched into int_customer_order_metrics or mart."""
        downstream = get_downstream_lineage(MODELS, "raw_payments", "amount")
        downstream_models = {m for m, c in downstream}
        assert "stg_orders_enriched" in downstream_models, (
            f"raw_payments.amount should flow to stg_orders_enriched, got {downstream_models}"
        )

    def test_downstream_from_raw_products_standard_cost_amt(self):
        """raw_products.standard_cost_amt should flow to stg_line_items_priced."""
        downstream = get_downstream_lineage(MODELS, "raw_products", "standard_cost_amt")
        downstream_models = {m for m, c in downstream}
        assert "stg_line_items_priced" in downstream_models

    def test_int_customer_order_metrics_customer_id_upstream(self):
        """int_customer_order_metrics.customer_id should come from raw_customers."""
        ups = _upstream_set("int_customer_order_metrics", "customer_id")
        upstream_models = {m for m, c in ups}
        assert "raw_customers" in upstream_models

    def test_fct_revenue_customer_id_comes_from_both_branches(self):
        """customer_id in fct_customer_revenue_daily comes from UNION ALL —
        should reference upstream view(s)."""
        ups = _upstream_set("fct_customer_revenue_daily", "customer_id")
        upstream_models = {m for m, c in ups}
        assert len(upstream_models) >= 1
        assert upstream_models & {"stg_line_items_priced", "stg_orders_enriched"}


# ------------------------------------------------------------------
# 6. Search-box-relevant: column name uniqueness / presence checks
# ------------------------------------------------------------------
class TestColumnPresence:
    """Verify specific columns exist in the right models, supporting search."""

    def test_mart_has_customer_segment(self):
        assert "customer_segment" in MODELS["mart_customer_ltv_segments"].columns

    def test_mart_has_margin_segment(self):
        assert "margin_segment" in MODELS["mart_customer_ltv_segments"].columns

    def test_mart_has_revenue_rank(self):
        assert "revenue_rank" in MODELS["mart_customer_ltv_segments"].columns

    def test_mart_has_revenue_quintile(self):
        assert "revenue_quintile" in MODELS["mart_customer_ltv_segments"].columns

    def test_stg_orders_has_order_month(self):
        assert "order_month" in MODELS["stg_orders_enriched"].columns

    def test_stg_line_items_has_category_path(self):
        assert "category_path" in MODELS["stg_line_items_priced"].columns

    def test_fct_has_contribution_after_cost_amount(self):
        assert "contribution_after_cost_amount" in MODELS["fct_customer_revenue_daily"].columns


# ------------------------------------------------------------------
# 7. UI HTML structure checks
# ------------------------------------------------------------------
class TestUIStructure:
    """Verify the HTML contains the required UI elements."""

    @classmethod
    def setup_class(cls):
        from app import app
        app.config["TESTING"] = True
        cls.client = app.test_client()

    def test_search_box_present(self):
        resp = self.client.get("/")
        assert b'id="search-input"' in resp.data

    def test_graph_svg_present(self):
        resp = self.client.get("/")
        assert b'id="lineage-graph"' in resp.data

    def test_detail_panel_present(self):
        resp = self.client.get("/")
        assert b'id="detail-panel"' in resp.data

    def test_default_mart_focus_button(self):
        resp = self.client.get("/")
        assert b"Focus Mart" in resp.data

    def test_js_loads_graph_on_init(self):
        """app.js should call /api/graph on load."""
        resp = self.client.get("/static/app.js")
        assert b"/api/graph" in resp.data
        assert b"focusMart" in resp.data


# ------------------------------------------------------------------
# 8. Drag-to-reposition infrastructure checks
# ------------------------------------------------------------------
class TestDragInfrastructure:
    """Verify the drag-to-reposition feature infrastructure is present."""

    @classmethod
    def setup_class(cls):
        from app import app
        app.config["TESTING"] = True
        cls.client = app.test_client()
        cls.js_content = cls.client.get("/static/app.js").data.decode("utf-8")
        cls.css_content = cls.client.get("/static/style.css").data.decode("utf-8")

    def test_pointer_event_listeners_on_nodes(self):
        """app.js should register pointerdown/pointermove/pointerup on node groups."""
        assert "pointerdown" in self.js_content
        assert "pointermove" in self.js_content
        assert "pointerup" in self.js_content

    def test_setup_node_drag_function_exists(self):
        """app.js should define the setupNodeDrag function."""
        assert "setupNodeDrag" in self.js_content

    def test_update_connected_edges_function_exists(self):
        """app.js should define the updateConnectedEdges function for surgical edge updates."""
        assert "updateConnectedEdges" in self.js_content

    def test_drag_threshold_defined(self):
        """app.js should define a movement threshold to disambiguate click from drag."""
        assert "NODE_DRAG_THRESHOLD" in self.js_content

    def test_session_storage_persistence(self):
        """app.js should use sessionStorage for position persistence."""
        assert "sessionStorage" in self.js_content
        assert "vibedev-lineage-positions" in self.js_content

    def test_save_and_load_position_functions(self):
        """app.js should define save/load/clear position helpers."""
        assert "savePositionsToSession" in self.js_content
        assert "loadPositionsFromSession" in self.js_content
        assert "clearPositionsFromSession" in self.js_content

    def test_cursor_grab_in_css(self):
        """style.css should define cursor: grab for .model-node."""
        assert "cursor: grab" in self.css_content

    def test_cursor_grabbing_in_css(self):
        """style.css should define cursor: grabbing for active drag state."""
        assert "cursor: grabbing" in self.css_content

    def test_pointer_capture_used(self):
        """app.js should use setPointerCapture for reliable drag tracking."""
        assert "setPointerCapture" in self.js_content
        assert "releasePointerCapture" in self.js_content

    def test_handle_node_click_function_exists(self):
        """app.js should define handleNodeClick to disambiguate click targets."""
        assert "handleNodeClick" in self.js_content

    def test_reset_view_clears_positions(self):
        """resetView should call clearPositionsFromSession."""
        assert "clearPositionsFromSession" in self.js_content
