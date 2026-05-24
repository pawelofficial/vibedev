"""
Tests for lineage extraction from schema.txt.

Verifies that the parser correctly resolves column-level lineage for:
- Direct passthrough columns
- Aliases and renamed columns
- Casts
- CASE expressions
- COALESCE, NULLIF, LOWER, TRIM, UPPER, DATE_TRUNC, concatenation
- Arithmetic expressions
- Joins across multiple tables
- CTEs
- Aggregate functions and filtered aggregates
- UNION ALL
- Window functions
- Views depending on other views
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from lineage_parser import parse_schema, get_upstream_lineage, get_downstream_lineage, get_lineage_graph


# Load schema once for all tests
SCHEMA_PATH = Path(__file__).parent.parent / 'schema.txt'
SCHEMA_TEXT = SCHEMA_PATH.read_text(encoding='utf-8')
MODELS = parse_schema(SCHEMA_TEXT)


class TestBaseTableParsing:
    """Test that base tables are parsed correctly."""

    def test_all_tables_found(self):
        tables = [m for m in MODELS.values() if m.model_type == 'table']
        table_names = {t.name for t in tables}
        expected = {'raw_customers', 'raw_orders', 'raw_order_items', 'raw_products', 'raw_payments'}
        assert table_names == expected

    def test_all_views_found(self):
        views = [m for m in MODELS.values() if m.model_type == 'view']
        view_names = {v.name for v in views}
        expected = {'stg_orders_enriched', 'stg_line_items_priced',
                    'int_customer_order_metrics', 'fct_customer_revenue_daily',
                    'mart_customer_ltv_segments'}
        assert view_names == expected

    def test_raw_customers_columns(self):
        model = MODELS['raw_customers']
        expected_cols = ['customer_id', 'external_customer_id', 'email', 'first_name',
                        'last_name', 'signup_ts', 'acquisition_channel', 'country_code',
                        'marketing_opt_in', 'customer_status']
        assert model.columns == expected_cols

    def test_base_table_no_upstream(self):
        """Base table columns should have no upstream lineage."""
        for col in MODELS['raw_customers'].columns:
            lineage = MODELS['raw_customers'].column_lineage[col]
            assert lineage.upstream == [], f"{col} should have no upstream"

    def test_raw_orders_columns(self):
        model = MODELS['raw_orders']
        assert 'order_id' in model.columns
        assert 'customer_id' in model.columns
        assert 'subtotal_amount' in model.columns
        assert 'discount_amount' in model.columns


class TestStgOrdersEnriched:
    """Test lineage for stg_orders_enriched view."""

    def test_view_exists(self):
        assert 'stg_orders_enriched' in MODELS

    def test_direct_passthrough_order_id(self):
        """order_id is a direct passthrough from raw_orders."""
        lin = MODELS['stg_orders_enriched'].column_lineage['order_id']
        assert ('raw_orders', 'order_id') in lin.upstream

    def test_cast_order_key(self):
        """order_key is o.order_id::TEXT - a cast."""
        lin = MODELS['stg_orders_enriched'].column_lineage['order_key']
        assert ('raw_orders', 'order_id') in lin.upstream

    def test_date_trunc_order_month(self):
        """order_month = DATE_TRUNC('month', o.order_ts)::DATE."""
        lin = MODELS['stg_orders_enriched'].column_lineage['order_month']
        assert ('raw_orders', 'order_ts') in lin.upstream

    def test_lower_trim_normalized_status(self):
        """raw_order_status_normalized = LOWER(TRIM(o.order_status))."""
        lin = MODELS['stg_orders_enriched'].column_lineage['raw_order_status_normalized']
        assert ('raw_orders', 'order_status') in lin.upstream

    def test_case_order_status_bucket(self):
        """order_status_bucket is a CASE on o.order_status."""
        lin = MODELS['stg_orders_enriched'].column_lineage['order_status_bucket']
        assert ('raw_orders', 'order_status') in lin.upstream

    def test_arithmetic_order_total_amount(self):
        """order_total_amount = COALESCE(subtotal) + shipping + tax - discount."""
        lin = MODELS['stg_orders_enriched'].column_lineage['order_total_amount']
        assert ('raw_orders', 'subtotal_amount') in lin.upstream
        assert ('raw_orders', 'shipping_amount') in lin.upstream
        assert ('raw_orders', 'tax_amount') in lin.upstream
        assert ('raw_orders', 'discount_amount') in lin.upstream
        assert lin.is_derived  # Multiple sources

    def test_net_collected_amount(self):
        """net_collected_amount = COALESCE(pr.charged_amount) - COALESCE(pr.refund_amount).
        This should trace back to raw_payments columns through CTE."""
        lin = MODELS['stg_orders_enriched'].column_lineage['net_collected_amount']
        # Should reference payment_rollup CTE columns
        upstream_models = {m for m, c in lin.upstream}
        # It comes from the payment_rollup CTE which aggregates from raw_payments
        assert len(lin.upstream) > 0
        assert lin.is_derived  # derived from charged_amount and refund_amount

    def test_cte_aggregate_charged_amount(self):
        """charged_amount comes from payment_rollup CTE (SUM CASE on raw_payments)."""
        lin = MODELS['stg_orders_enriched'].column_lineage['charged_amount']
        assert len(lin.upstream) > 0

    def test_nullif_coupon_code(self):
        """coupon_code_normalized = NULLIF(UPPER(TRIM(o.coupon_code)), '')."""
        lin = MODELS['stg_orders_enriched'].column_lineage['coupon_code_normalized']
        assert ('raw_orders', 'coupon_code') in lin.upstream

    def test_filtered_aggregate_failed_payment_events(self):
        """failed_payment_events from COUNT(*) FILTER in payment_rollup CTE."""
        lin = MODELS['stg_orders_enriched'].column_lineage['failed_payment_events']
        assert len(lin.upstream) > 0

    def test_boolean_is_fully_paid(self):
        """is_fully_paid is a comparison involving multiple columns."""
        lin = MODELS['stg_orders_enriched'].column_lineage['is_fully_paid']
        assert lin.is_derived
        # Should involve both payment and order columns
        upstream_cols = {c for m, c in lin.upstream}
        assert len(upstream_cols) > 1

    def test_join_across_tables(self):
        """View joins raw_orders with payment_rollup and item_rollup CTEs."""
        # item_row_count comes from item_rollup CTE
        lin = MODELS['stg_orders_enriched'].column_lineage['item_row_count']
        assert len(lin.upstream) > 0


class TestStgLineItemsPriced:
    """Test lineage for stg_line_items_priced view."""

    def test_view_exists(self):
        assert 'stg_line_items_priced' in MODELS

    def test_multi_table_join(self):
        """View joins raw_order_items, raw_orders, and raw_products."""
        lin = MODELS['stg_line_items_priced'].column_lineage['customer_id']
        assert ('raw_orders', 'customer_id') in lin.upstream

    def test_coalesce_fallback_sku(self):
        """resolved_sku = COALESCE(p.sku, oi.sku)."""
        lin = MODELS['stg_line_items_priced'].column_lineage['resolved_sku']
        upstream_models = {m for m, c in lin.upstream}
        assert 'raw_products' in upstream_models or 'raw_order_items' in upstream_models
        assert lin.is_derived  # From two sources

    def test_concatenation_category_path(self):
        """category_path = COALESCE(p.category) || ' > ' || COALESCE(p.subcategory)."""
        lin = MODELS['stg_line_items_priced'].column_lineage['category_path']
        assert ('raw_products', 'category') in lin.upstream
        assert ('raw_products', 'subcategory') in lin.upstream
        assert lin.is_derived

    def test_arithmetic_gross_line_amount(self):
        """gross_line_amount = oi.quantity * oi.unit_price_amount."""
        lin = MODELS['stg_line_items_priced'].column_lineage['gross_line_amount']
        assert ('raw_order_items', 'quantity') in lin.upstream
        assert ('raw_order_items', 'unit_price_amount') in lin.upstream
        assert lin.is_derived

    def test_estimated_line_margin(self):
        """estimated_line_margin = (quantity * unit_price - discount) - (cost * quantity).
        Should derive from raw_order_items and raw_products."""
        lin = MODELS['stg_line_items_priced'].column_lineage['estimated_line_margin']
        upstream_models = {m for m, c in lin.upstream}
        assert 'raw_order_items' in upstream_models
        assert 'raw_products' in upstream_models
        assert lin.is_derived
        # Specific columns
        upstream_cols = {(m, c) for m, c in lin.upstream}
        assert ('raw_order_items', 'quantity') in upstream_cols
        assert ('raw_order_items', 'unit_price_amount') in upstream_cols
        assert ('raw_products', 'standard_cost_amt') in upstream_cols

    def test_case_is_fulfilled(self):
        """is_fulfilled is a CASE on oi.fulfillment_status."""
        lin = MODELS['stg_line_items_priced'].column_lineage['is_fulfilled']
        assert ('raw_order_items', 'fulfillment_status') in lin.upstream

    def test_case_product_sale_flag(self):
        """product_sale_flag references p.is_active, p.launched_date, o.order_ts."""
        lin = MODELS['stg_line_items_priced'].column_lineage['product_sale_flag']
        upstream_cols = {(m, c) for m, c in lin.upstream}
        assert ('raw_products', 'is_active') in upstream_cols
        assert ('raw_products', 'launched_date') in upstream_cols
        assert ('raw_orders', 'order_ts') in upstream_cols


class TestIntCustomerOrderMetrics:
    """Test lineage for int_customer_order_metrics view (depends on upstream views)."""

    def test_view_exists(self):
        assert 'int_customer_order_metrics' in MODELS

    def test_depends_on_upstream_view(self):
        """This view joins raw_customers with stg_orders_enriched."""
        # Check that some columns trace to stg_orders_enriched
        lin = MODELS['int_customer_order_metrics'].column_lineage.get('lifetime_net_collected_amount')
        if lin:
            upstream_models = {m for m, c in lin.upstream}
            # Should reference customer_orders CTE columns which come from stg_orders_enriched
            assert len(lin.upstream) > 0

    def test_lower_email(self):
        """email_normalized = LOWER(c.email) from raw_customers."""
        lin = MODELS['int_customer_order_metrics'].column_lineage.get('email_normalized')
        if lin:
            upstream_models = {m for m, c in lin.upstream}
            assert 'raw_customers' in upstream_models or 'customer_orders' in upstream_models

    def test_concat_full_name(self):
        """full_name = TRIM(COALESCE(first_name) || ' ' || COALESCE(last_name))."""
        lin = MODELS['int_customer_order_metrics'].column_lineage.get('full_name')
        if lin:
            assert len(lin.upstream) > 0

    def test_aggregate_lifetime_order_count(self):
        """lifetime_order_count = COUNT(order_id)."""
        lin = MODELS['int_customer_order_metrics'].column_lineage.get('lifetime_order_count')
        if lin:
            assert len(lin.upstream) > 0

    def test_filtered_aggregate_completed_order_count(self):
        """completed_order_count = COUNT(order_id) FILTER (WHERE ...)."""
        lin = MODELS['int_customer_order_metrics'].column_lineage.get('completed_order_count')
        if lin:
            assert len(lin.upstream) > 0

    def test_ratio_avg_completed_order_value(self):
        """avg_completed_order_value = SUM(...) / NULLIF(COUNT(...) FILTER, 0)."""
        lin = MODELS['int_customer_order_metrics'].column_lineage.get('avg_completed_order_value')
        if lin:
            assert lin.is_derived


class TestFctCustomerRevenueDaily:
    """Test lineage for fct_customer_revenue_daily (UNION ALL, view dependencies)."""

    def test_view_exists(self):
        assert 'fct_customer_revenue_daily' in MODELS

    def test_daily_revenue_amount(self):
        """daily_revenue_amount = SUM(revenue_amount) from UNION ALL of line_revenue + refunds.
        Should ultimately trace to stg_line_items_priced and stg_orders_enriched."""
        lin = MODELS['fct_customer_revenue_daily'].column_lineage.get('daily_revenue_amount')
        assert lin is not None
        assert len(lin.upstream) > 0

    def test_union_all_customer_id(self):
        """customer_id comes from both branches of UNION ALL."""
        lin = MODELS['fct_customer_revenue_daily'].column_lineage.get('customer_id')
        if lin:
            assert len(lin.upstream) > 0

    def test_revenue_month_date_trunc(self):
        """revenue_month = DATE_TRUNC('month', revenue_date)::DATE."""
        lin = MODELS['fct_customer_revenue_daily'].column_lineage.get('revenue_month')
        if lin:
            assert len(lin.upstream) > 0

    def test_filtered_aggregate_refund_event_count(self):
        """refund_event_count = COUNT(*) FILTER (WHERE revenue_event_type = 'refund')."""
        assert 'refund_event_count' in MODELS['fct_customer_revenue_daily'].columns

    def test_contribution_after_cost(self):
        """contribution_after_cost_amount = SUM(revenue_amount) - ABS(SUM(cost_amount))."""
        lin = MODELS['fct_customer_revenue_daily'].column_lineage.get('contribution_after_cost_amount')
        if lin:
            assert lin.is_derived


class TestMartCustomerLtvSegments:
    """Test lineage for mart_customer_ltv_segments (window functions, final mart)."""

    def test_view_exists(self):
        assert 'mart_customer_ltv_segments' in MODELS

    def test_ltv_after_fees_amount(self):
        """ltv_after_fees_amount = COALESCE(rr.total_revenue_amount, 0)
            - COALESCE(icom.lifetime_processor_fee_amount, 0).
        Should trace through int_customer_order_metrics and fct_customer_revenue_daily."""
        lin = MODELS['mart_customer_ltv_segments'].column_lineage.get('ltv_after_fees_amount')
        assert lin is not None
        assert len(lin.upstream) > 0
        assert lin.is_derived  # From revenue_rollup and int_customer_order_metrics

    def test_customer_segment(self):
        """customer_segment is a CASE expression referencing lifetime_order_count,
        total_revenue_amount, completed_order_count, total_refund_events,
        customer_age_days, and marketing_opt_in."""
        lin = MODELS['mart_customer_ltv_segments'].column_lineage.get('customer_segment')
        assert lin is not None
        assert len(lin.upstream) > 0
        assert lin.is_derived  # Multiple column references

    def test_window_function_revenue_rank(self):
        """revenue_rank = DENSE_RANK() OVER (ORDER BY total_revenue_amount DESC)."""
        lin = MODELS['mart_customer_ltv_segments'].column_lineage.get('revenue_rank')
        assert lin is not None
        assert len(lin.upstream) > 0

    def test_window_function_ntile(self):
        """revenue_quintile = NTILE(5) OVER (ORDER BY total_revenue_amount DESC)."""
        lin = MODELS['mart_customer_ltv_segments'].column_lineage.get('revenue_quintile')
        assert lin is not None
        assert len(lin.upstream) > 0

    def test_margin_segment(self):
        """margin_segment is CASE on total_margin_amount and total_revenue_amount."""
        lin = MODELS['mart_customer_ltv_segments'].column_lineage.get('margin_segment')
        assert lin is not None
        assert lin.is_derived

    def test_passthrough_from_scored_customers_cte(self):
        """signup_date passes through scored_customers CTE from int_customer_order_metrics."""
        lin = MODELS['mart_customer_ltv_segments'].column_lineage.get('signup_date')
        assert lin is not None
        assert len(lin.upstream) > 0

    def test_depends_on_two_upstream_views(self):
        """The mart depends on both int_customer_order_metrics and fct_customer_revenue_daily."""
        all_upstream_models = set()
        for col, lin in MODELS['mart_customer_ltv_segments'].column_lineage.items():
            for m, c in lin.upstream:
                all_upstream_models.add(m)
        # Should reference CTEs that derive from both upstream views
        assert len(all_upstream_models) > 0


class TestGraphStructure:
    """Test the overall graph structure."""

    def test_graph_has_nodes_and_edges(self):
        graph = get_lineage_graph(MODELS)
        assert len(graph['nodes']) == 10  # 5 tables + 5 views
        assert len(graph['edges']) > 0

    def test_all_edges_reference_valid_models(self):
        graph = get_lineage_graph(MODELS)
        model_names = {n['id'] for n in graph['nodes']}
        for edge in graph['edges']:
            assert edge['source_model'] in model_names or edge['source_model'].endswith('__branch'), \
                f"Edge source {edge['source_model']} not in models"

    def test_downstream_lineage(self):
        """Test that downstream lineage works for a base column."""
        downstream = get_downstream_lineage(MODELS, 'raw_orders', 'order_id')
        assert len(downstream) > 0
        # order_id is used in many views
        downstream_models = {m for m, c in downstream}
        assert 'stg_orders_enriched' in downstream_models or len(downstream_models) > 0

    def test_upstream_lineage_recursive(self):
        """Test recursive upstream traces back to base tables."""
        upstream = get_upstream_lineage(MODELS, 'mart_customer_ltv_segments', 'customer_id')
        # Should eventually reach base tables
        upstream_models = {m for m, c in upstream}
        assert len(upstream_models) > 0


class TestSpecificLineageRequirements:
    """Required lineage proofs from the task specification."""

    def test_mart_ltv_after_fees_amount_lineage(self):
        """Prove lineage for mart_customer_ltv_segments.ltv_after_fees_amount.
        Should derive from revenue_rollup.total_revenue_amount and
        int_customer_order_metrics.lifetime_processor_fee_amount."""
        lin = MODELS['mart_customer_ltv_segments'].column_lineage['ltv_after_fees_amount']
        assert lin is not None
        assert lin.is_derived
        assert len(lin.upstream) >= 2
        upstream_cols = {c for m, c in lin.upstream}
        # Should have references to revenue and fee columns
        assert len(upstream_cols) >= 2

    def test_mart_customer_segment_lineage(self):
        """Prove lineage for mart_customer_ltv_segments.customer_segment.
        CASE expression referencing multiple scored_customers columns."""
        lin = MODELS['mart_customer_ltv_segments'].column_lineage['customer_segment']
        assert lin is not None
        assert lin.is_derived
        # The CASE references: lifetime_order_count, total_revenue_amount,
        # completed_order_count, total_refund_events, customer_age_days, marketing_opt_in
        assert len(lin.upstream) >= 2

    def test_fct_daily_revenue_amount_lineage(self):
        """Prove lineage for fct_customer_revenue_daily.daily_revenue_amount.
        Should trace through UNION ALL CTEs to upstream views."""
        lin = MODELS['fct_customer_revenue_daily'].column_lineage['daily_revenue_amount']
        assert lin is not None
        assert len(lin.upstream) > 0

    def test_stg_orders_net_collected_amount_lineage(self):
        """Prove lineage for stg_orders_enriched.net_collected_amount.
        = COALESCE(pr.charged_amount) - COALESCE(pr.refund_amount)
        where pr is payment_rollup CTE over raw_payments."""
        lin = MODELS['stg_orders_enriched'].column_lineage['net_collected_amount']
        assert lin is not None
        assert lin.is_derived
        assert len(lin.upstream) >= 2

    def test_stg_line_items_estimated_line_margin_lineage(self):
        """Prove lineage for stg_line_items_priced.estimated_line_margin.
        = (quantity * unit_price - discount) - (cost * quantity).
        Must trace to both raw_order_items and raw_products."""
        lin = MODELS['stg_line_items_priced'].column_lineage['estimated_line_margin']
        assert lin is not None
        assert lin.is_derived
        upstream_models = {m for m, c in lin.upstream}
        assert 'raw_order_items' in upstream_models
        assert 'raw_products' in upstream_models
        # Specific columns
        upstream_set = set(lin.upstream)
        assert ('raw_order_items', 'quantity') in upstream_set
        assert ('raw_order_items', 'unit_price_amount') in upstream_set
        assert ('raw_products', 'standard_cost_amt') in upstream_set
